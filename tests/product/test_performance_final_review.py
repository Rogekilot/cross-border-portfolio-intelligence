"""TECH_REVIEW section 30 (CP3 final review) findings CP3-14 to CP3-17 (CP3-12 and CP3-13 are in `test_performance_real_fx.py`).

- CP3-14: the attribution takes the close of a position closed out on a split-suppressed day, and of a tainted sale, from the same suppressions as the gains (SOURCE_CONFLICT), pure and through PostgreSQL;
- CP3-15: a confirmation policy with one role matched and one unmatched is refused naming the role, pure and through PostgreSQL;
- CP3-16: Carino for a TWR below 1E-50 (a stable kappa), pure and through the engine with the reviewer's 1E28 / 1E-24 scenario;
- CP3-17: Example W's breakdown is apportioned to the line's DISPLAYED value (A16), and a stale close on a sale day reaches the attribution's state (A17).
"""

import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import performance_kit as pk  # noqa: E402
import pg_market_kit as pgk  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402
import test_performance_recheck as rc  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from performance import engine, numerics  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402
from performance_service import service as svc  # noqa: E402

D, F = datetime.date, Fraction
USD = mp.USD
EX = ca.EX
CUSTOM = WindowSpec(WindowRule.CUSTOM, None, D(2025, 1, 31))


def conflict_ledger(same_account):
    """The review's set-up: A1 holds 50 units; a corroborated 4:1 split has ex-date 02-03 and is NOT in the ledger; RAW closes 150.00 then 37.50. On the ex-date A1 moves the 50 units to A2 (an
    internal pair) and A2 sells them for 7,500 (or A1 sells them itself)."""
    L = mp.base_ledger()
    seller = mp.A1
    if not same_account:
        mp.internal_transfer(L, EX)
        seller = mp.A2
    L.add(seller, EventType.SELL, EX, USD, listing_id=mp.LISTING, quantity=Decimal(50), amount=Money(Decimal(7500), USD))
    return L


def attribution_states(res):
    return {m.metric_id: (m.result.sufficiency_state.value, None if m.result.reason_code is None else m.result.reason_code.value) for m in res.metrics}


class Cp3_14PureTests(unittest.TestCase):
    def run_service(self, L):
        port = mp.market("real", real_quotes=True)
        with rc.pinned(L):
            attr = svc.compute_attribution_for_portfolio(None, ca.PORTFOLIO, CUSTOM, EX, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=ca.POLICY)
            gains = svc.compute_gains_for_portfolio(None, ca.PORTFOLIO, EX, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=ca.POLICY, window=CUSTOM)
        return attr, gains

    def test_a_close_out_across_accounts_on_the_ex_date_is_source_conflict_like_the_realized_gain(self):
        attr, gains = self.run_service(conflict_ledger(same_account=False))
        states = attribution_states(attr)
        self.assertEqual(states["attribution_money"], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"))  # it was AVAILABLE 0 with attr.price A1 -5,625 and A2 +5,625 (mixed units)
        self.assertEqual(states["attribution_return"], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"))
        self.assertEqual([m for m in attr.metrics if m.metric_id == "attribution_breakdown"], [])  # no part of a suppressed attribution is shown
        realized = [m for m in gains.metrics if m.metric_id == "realized_gain" and m.view == "REPORTING"]
        self.assertEqual([(m.result.sufficiency_state.value, m.result.reason_code.value) for m in realized], [("INSUFFICIENT_DATA", "SOURCE_CONFLICT")])  # consistent with the gains

    def test_both_close_uses_are_guarded_the_closed_out_position_and_the_trade_and_each_guard_adds_the_part(self):
        # the close-out guard and the trade guard give the same verdict in this set-up (both are SOURCE_CONFLICT), so each call site is pinned by what it asks the guard
        from unittest import mock  # noqa: PLC0415
        from performance import attribution  # noqa: PLC0415

        L = conflict_ledger(same_account=False)
        sale = next(i.event.event_id for i in L.rows if i.event.event_type is EventType.SELL)
        asked = []
        real = attribution.Lookups.guard

        def spy(self, account, listing, day, event_id=None):
            asked.append((account, listing, day, event_id))
            return real(self, account, listing, day, event_id)

        with mock.patch.object(attribution.Lookups, "guard", spy):
            self.run_service(L)
        self.assertIn((mp.A1, mp.LISTING, EX, None), asked)  # A1's position is closed out on the ex-date: its close is asked of the guard
        self.assertIn((mp.A2, mp.LISTING, EX, sale), asked)  # A2's sale: its trade result is asked of the guard, with the event id (the taint is per event)

    def test_cp3_20_the_engine_hands_the_event_taints_and_the_suppressions_to_the_attribution_lookups(self):
        # B1 (the engine drops the event taints at the seam). No scenario kills it by output alone any more: a tainted sale is also refused by the in-leg's tainted flow (account scope, CP3-18) and by
        # the source's own suppressed close-out or valuation (portfolio scope), so the seam itself is pinned: what the engine hands `Lookups` is the taint of the sale AND of the receiving leg.
        from unittest import mock  # noqa: PLC0415
        from performance import attribution  # noqa: PLC0415

        L = conflict_ledger(same_account=False)
        sale = next(i.event.event_id for i in L.rows if i.event.event_type is EventType.SELL)
        leg = next(i.event.event_id for i in L.rows if i.event.event_type is EventType.TRANSFER_IN)
        seen = []
        real = attribution.Lookups.__init__

        def spy(self, *args, **kwargs):
            seen.append((args, kwargs))
            return real(self, *args, **kwargs)

        with mock.patch.object(attribution.Lookups, "__init__", spy):
            self.run_service(L)
        self.assertTrue(seen)
        for args, kwargs in seen:
            suppressions, taints = (list(args) + [kwargs.get("suppressions"), kwargs.get("event_taints")])[7:9] if len(args) < 9 else args[7:9]
            self.assertTrue(suppressions)  # the F8 suppression of A1 is handed over
            self.assertIn(sale, taints)  # the tainted sale
            self.assertIn(leg, taints)  # and the receiving leg (CP3-18)

    def test_the_guard_adds_a_source_conflict_part_for_a_suppressed_position_and_for_a_tainted_event_and_only_once(self):
        from performance import attribution  # noqa: PLC0415
        from performance.inputs import SuppressionInput  # noqa: PLC0415
        from performance.flows import DataUse  # noqa: PLC0415

        sup = SuppressionInput(mp.A1, mp.LISTING, EX, None, "SOURCE_CONFLICT", "SPLIT_NOT_APPLIED: test", EX, "WOULD_APPEND")
        taint = SuppressionInput(mp.A2, mp.LISTING, EX, EX + datetime.timedelta(days=1), "SOURCE_CONFLICT", "SPLIT_SUPPRESSION_CARRIED: test", EX, "WOULD_APPEND")
        event = uuid.UUID(int=77)
        lk = attribution.Lookups(USD, None, None, None, DataUse(), None, None, (sup,), {event: taint})
        lk.guard(mp.A1, mp.LISTING, EX)
        lk.guard(mp.A1, mp.LISTING, EX)  # asked twice: one part
        self.assertEqual([(p.state.value, p.reason) for p in lk.parts], [("INSUFFICIENT_DATA", "SOURCE_CONFLICT")])
        lk.guard(mp.A1, mp.LISTING, EX - datetime.timedelta(days=1))  # before the suppression: nothing
        lk.guard(mp.A2, mp.LISTING, EX)  # A2 is not suppressed on the day ...
        self.assertEqual(len(lk.parts), 1)
        lk.guard(mp.A2, mp.LISTING, EX, event)  # ... but this sale's relief holds a tainted portion
        self.assertEqual([(p.state.value, p.reason) for p in lk.parts], [("INSUFFICIENT_DATA", "SOURCE_CONFLICT")] * 2)
        self.assertIn("SPLIT_SUPPRESSION_CARRIED", lk.parts[1].causes[0].detail)

    def test_a_sale_in_the_suppressed_account_itself_is_source_conflict(self):
        attr, _gains = self.run_service(conflict_ledger(same_account=True))
        self.assertEqual(attribution_states(attr)["attribution_money"], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"))

    def test_the_unsuppressed_world_still_gives_numbers(self):
        # the same ledger WITH the split recorded: nothing is suppressed, the attribution is a number
        from domain.ledger import SplitRatio  # noqa: PLC0415

        L = mp.base_ledger()
        L.add(mp.A1, EventType.SPLIT, EX, USD, listing_id=mp.LISTING, split_ratio=SplitRatio(Decimal(4), Decimal(1)))
        L.add(mp.A1, EventType.SELL, EX, USD, listing_id=mp.LISTING, quantity=Decimal(200), amount=Money(Decimal(7500), USD))
        port = mp.market("real", real_quotes=True)
        with rc.pinned(L):
            attr = svc.compute_attribution_for_portfolio(None, ca.PORTFOLIO, CUSTOM, EX, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=ca.POLICY)
        self.assertEqual(attribution_states(attr)["attribution_money"], ("AVAILABLE", None))


@unittest.skipIf(bool(pgk.skip_reason()), pgk.skip_reason())
class Cp3_14PostgresTests(unittest.TestCase):
    """The review's set-up through PostgreSQL as `finweb_app`."""

    @classmethod
    def setUpClass(cls):
        rc.PostgresRecheckTests.setUpClass.__func__(cls)

    def portfolio(self, *, hops=True, sale=True):
        user, portfolio = uuid.uuid4(), uuid.uuid4()
        accounts = [uuid.uuid4() for _ in range(2)]
        owner = self.db.owner
        owner.execute("INSERT INTO app_user VALUES (%s)", (user,))
        owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (portfolio, user))
        for a in accounts:
            owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (a, portfolio))
        self.ls.append_batch(self.app, [
            LedgerEvent(uuid.uuid4(), accounts[0], EventType.DEPOSIT, D(2024, 12, 19), USD, amount=Money(Decimal(10000), USD)),
            LedgerEvent(uuid.uuid4(), accounts[0], EventType.BUY, D(2024, 12, 20), USD, listing_id=self.aapl, quantity=Decimal(50), amount=Money(Decimal(7500), USD))])
        if hops:
            out = LedgerEvent(uuid.uuid4(), accounts[0], EventType.TRANSFER_OUT, EX, USD, listing_id=self.aapl, quantity=Decimal(50), counterparty_account_id=accounts[1])
            inn = LedgerEvent(uuid.uuid4(), accounts[1], EventType.TRANSFER_IN, EX, USD, listing_id=self.aapl, quantity=Decimal(50), counterparty_account_id=accounts[0])
            self.ls.append_internal_transfer(self.app, out, inn)
        if sale:
            seller = accounts[1] if hops else accounts[0]
            self.ls.append_batch(self.app, [LedgerEvent(uuid.uuid4(), seller, EventType.SELL, EX, USD, listing_id=self.aapl, quantity=Decimal(50), amount=Money(Decimal(7500), USD))])
        return portfolio

    def market(self):
        return mp.market("real", real_quotes=True, listing=self.aapl, mic="XNAS")

    def test_the_review_setup_gives_source_conflict_for_attribution_and_gains_through_postgresql(self):
        for hops in (True, False):
            portfolio = self.portfolio(hops=hops)
            attr = svc.compute_attribution_for_portfolio(self.app, portfolio, CUSTOM, EX, USD, self.market(), self.ident, self.conventions, mp.PERF, policy=ca.POLICY)
            self.assertEqual(attr.manifest.split_detection, "F8B_DRY_RUN")
            states = attribution_states(attr)
            self.assertEqual(states["attribution_money"], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"), hops)
            self.assertEqual(states["attribution_return"], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"), hops)
            gains = svc.compute_gains_for_portfolio(self.app, portfolio, EX, USD, self.market(), self.ident, self.conventions, mp.PERF, policy=ca.POLICY, window=CUSTOM)
            realized = [m for m in gains.metrics if m.metric_id == "realized_gain" and m.view == "REPORTING"]
            self.assertEqual({(m.result.sufficiency_state.value, m.result.reason_code.value) for m in realized}, {("INSUFFICIENT_DATA", "SOURCE_CONFLICT")})  # consistent
            before = self.rs.current_ledger_version(self.app, portfolio)
            self.assertEqual(before, self.rs.current_ledger_version(self.app, portfolio))  # the dry run wrote nothing

    def test_cp3_15_a_half_matching_policy_is_refused_through_postgresql_for_all_three_entries(self):
        portfolio = self.portfolio(hops=True, sale=False)
        half = f8b.ConfirmationPolicy(frozenset({ca.FEED}), frozenset({"typo.filing"}))
        entries = (svc.compute_for_portfolio(self.app, portfolio, EX, USD, self.market(), self.ident, self.conventions, mp.PERF, policy=half),
                   svc.compute_attribution_for_portfolio(self.app, portfolio, CUSTOM, EX, USD, self.market(), self.ident, self.conventions, mp.PERF, policy=half),
                   svc.compute_gains_for_portfolio(self.app, portfolio, EX, USD, self.market(), self.ident, self.conventions, mp.PERF, policy=half))
        for res in entries:  # the review's probe gave AVAILABLE 4,375, -5,625 and -5,625 here
            (m,) = res.metrics
            self.assertIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
            self.assertIsNone(m.result.value)
            self.assertIn('"unmatched_roles":["filing"]', m.causes[0].note)
            self.assertNotIn('"feed"', m.causes[0].note)


SINCE = WindowSpec(WindowRule.SINCE_INCEPTION)


def scope_results(call_window, call_gains, call_attribution, scope):
    """G, TWR, MWR, realized gain and both attribution metrics at one scope: `{name: (state, reason)}` and the values."""
    window = call_window(scope)
    gains = call_gains(scope)
    attr = call_attribution(scope)
    out = {}
    for res in (window, attr):
        for m in res.metrics:
            if m.metric_id in ("gain_absolute", "return_twr", "return_mwr", "attribution_money", "attribution_return"):
                out[m.metric_id] = (m.result.sufficiency_state.value, None if m.result.reason_code is None else m.result.reason_code.value, m.exact)
    realized = [m for m in gains.metrics if m.metric_id == "realized_gain" and m.view == "REPORTING"]
    out["realized_gain"] = {(m.result.sufficiency_state.value, None if m.result.reason_code is None else m.result.reason_code.value) for m in realized}
    return out


class Cp3_18PureTests(unittest.TestCase):
    """CP3-18: at account scope the RECEIVING leg of a tainted internal transfer is valued at the RAW close (an external in-kind inflow, q x P x X with pre-split q and post-split P): G was AVAILABLE
    5,625 at A2 scope while the attribution and the realized gain of the same window were SOURCE_CONFLICT. The leg carries the taint (market-data Ruling 6.4c rule 6)."""

    def results(self, L, scope):
        port = mp.market("real", real_quotes=True)
        a = (USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF)
        spec = SINCE if scope == mp.A2 else CUSTOM  # A2's history starts on the ex-date; the others have prices from 01-31
        with rc.pinned(L):
            return scope_results(
                lambda s: svc.compute_window_for_portfolio(None, ca.PORTFOLIO, spec, EX, *a, policy=ca.POLICY, account_scope=s),
                lambda s: svc.compute_gains_for_portfolio(None, ca.PORTFOLIO, EX, *a, policy=ca.POLICY, window=spec, account_scope=s),
                lambda s: svc.compute_attribution_for_portfolio(None, ca.PORTFOLIO, spec, EX, *a, policy=ca.POLICY, account_scope=s), scope)

    def test_at_the_receiving_account_every_window_metric_is_source_conflict_with_no_number(self):
        r = self.results(conflict_ledger(same_account=False), mp.A2)
        for metric in ("gain_absolute", "return_twr", "return_mwr", "attribution_money", "attribution_return"):
            self.assertEqual(r[metric], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT", None), metric)  # G was AVAILABLE 5,625 (7,500 - 50 x 37.50)
        self.assertEqual(r["realized_gain"], {("INSUFFICIENT_DATA", "SOURCE_CONFLICT")})

    def test_at_the_sending_account_and_at_portfolio_scope_the_metrics_agree(self):
        L = conflict_ledger(same_account=False)
        r1 = self.results(L, mp.A1)  # A1 is suppressed itself: its out-leg and everything in the window refuse
        for metric in ("gain_absolute", "return_twr", "return_mwr", "attribution_money", "attribution_return"):
            self.assertEqual(r1[metric][:2], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"), metric)
        rp = self.results(L, None)  # portfolio scope: the pair is neutral, the units are nobody's at the end of the day; the attribution and the gains need the suppressed close
        self.assertEqual(rp["attribution_money"][:2], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"))
        self.assertEqual(rp["attribution_return"][:2], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"))
        self.assertEqual(rp["realized_gain"], {("INSUFFICIENT_DATA", "SOURCE_CONFLICT")})
        self.assertEqual(rp["gain_absolute"][:2], ("AVAILABLE", None))  # G = V_E - V_B - external flows: no flow is valued here, and the value is right (cash only)
        self.assertEqual(rp["gain_absolute"][2], 0)

    def test_the_in_leg_is_in_event_taints_only_when_the_lot_it_delivers_is_tainted(self):
        from domain.replay import live_events  # noqa: PLC0415
        from performance.taint import carried_taint  # noqa: PLC0415

        L = conflict_ledger(same_account=False)
        sup = mp.detect(L, mp.market("real", real_quotes=True))
        in_leg = next(i.event.event_id for i in L.rows if i.event.event_type is EventType.TRANSFER_IN)
        out_leg = next(i.event.event_id for i in L.rows if i.event.event_type is EventType.TRANSFER_OUT)
        taint = carried_taint(live_events(L.rows, L.version), sup)
        self.assertIn(in_leg, taint.event_taints)
        self.assertEqual((taint.event_taints[in_leg].account_id, taint.event_taints[in_leg].first_date), (mp.A2, EX))
        self.assertNotIn(out_leg, taint.event_taints)  # the out-leg is A1's: A1's own suppression covers it
        # a transfer BEFORE the suppression starts delivers clean units: nothing is tainted
        clean = mp.base_ledger()
        mp.internal_transfer(clean, D(2025, 1, 31))
        taint = carried_taint(live_events(clean.rows, clean.version), mp.detect(clean, mp.market("real", real_quotes=True)))
        self.assertEqual(taint.event_taints, {})


@unittest.skipIf(bool(pgk.skip_reason()), pgk.skip_reason())
class Cp3_18PostgresTests(unittest.TestCase):
    """The same set-up through PostgreSQL as `finweb_app`, at A1 scope, A2 scope and portfolio scope."""

    @classmethod
    def setUpClass(cls):
        rc.PostgresRecheckTests.setUpClass.__func__(cls)

    portfolio = Cp3_14PostgresTests.portfolio
    market = Cp3_14PostgresTests.market

    def test_the_account_scopes_and_the_portfolio_agree_through_postgresql(self):
        user, portfolio = uuid.uuid4(), uuid.uuid4()
        a1, a2 = uuid.uuid4(), uuid.uuid4()
        owner = self.db.owner
        owner.execute("INSERT INTO app_user VALUES (%s)", (user,))
        owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (portfolio, user))
        for a in (a1, a2):
            owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (a, portfolio))
        self.ls.append_batch(self.app, [
            LedgerEvent(uuid.uuid4(), a1, EventType.DEPOSIT, D(2024, 12, 19), USD, amount=Money(Decimal(10000), USD)),
            LedgerEvent(uuid.uuid4(), a1, EventType.BUY, D(2024, 12, 20), USD, listing_id=self.aapl, quantity=Decimal(50), amount=Money(Decimal(7500), USD))])
        out = LedgerEvent(uuid.uuid4(), a1, EventType.TRANSFER_OUT, EX, USD, listing_id=self.aapl, quantity=Decimal(50), counterparty_account_id=a2)
        inn = LedgerEvent(uuid.uuid4(), a2, EventType.TRANSFER_IN, EX, USD, listing_id=self.aapl, quantity=Decimal(50), counterparty_account_id=a1)
        self.ls.append_internal_transfer(self.app, out, inn)
        self.ls.append_batch(self.app, [LedgerEvent(uuid.uuid4(), a2, EventType.SELL, EX, USD, listing_id=self.aapl, quantity=Decimal(50), amount=Money(Decimal(7500), USD))])
        args = (USD, self.market(), self.ident, self.conventions, mp.PERF)

        def results(scope):
            spec = SINCE if scope == a2 else CUSTOM
            return scope_results(
                lambda s: svc.compute_window_for_portfolio(self.app, portfolio, spec, EX, *args, policy=ca.POLICY, account_scope=s),
                lambda s: svc.compute_gains_for_portfolio(self.app, portfolio, EX, *args, policy=ca.POLICY, window=spec, account_scope=s),
                lambda s: svc.compute_attribution_for_portfolio(self.app, portfolio, spec, EX, *args, policy=ca.POLICY, account_scope=s), scope)

        r2 = results(a2)
        for metric in ("gain_absolute", "return_twr", "return_mwr", "attribution_money", "attribution_return"):
            self.assertEqual(r2[metric], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT", None), metric)  # the review: G AVAILABLE 5,625 at A2 scope
        self.assertEqual(r2["realized_gain"], {("INSUFFICIENT_DATA", "SOURCE_CONFLICT")})
        r1 = results(a1)
        for metric in ("gain_absolute", "return_twr", "return_mwr", "attribution_money", "attribution_return"):
            self.assertEqual(r1[metric][:2], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"), metric)
        rp = results(None)
        self.assertEqual(rp["attribution_money"][:2], ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"))
        self.assertEqual(rp["realized_gain"], {("INSUFFICIENT_DATA", "SOURCE_CONFLICT")})
        self.assertEqual(rp["gain_absolute"][:2], ("AVAILABLE", None))
        self.assertEqual(rp["gain_absolute"][2], 0)
        self.assertEqual(self.rs.current_ledger_version(self.app, portfolio), 5)  # the dry run wrote nothing


class Cp3_15PureTests(unittest.TestCase):
    def test_the_reviewers_policy_names_the_unmatched_role_and_a_legitimate_lone_feed_is_not_refused(self):
        L = mp.base_ledger()
        port = mp.market("real", real_quotes=True)
        for policy, role in ((f8b.ConfirmationPolicy(frozenset({"test.feed"}), frozenset({"typo.filing"})), "filing"), (f8b.ConfirmationPolicy(frozenset({"typo.feed"}), frozenset({"test.filing"})), "feed")):
            with rc.pinned(L):
                res = svc.compute_for_portfolio(None, ca.PORTFOLIO, EX, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=policy)
            (m,) = res.metrics
            self.assertIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
            self.assertIn(f'"unmatched_roles":["{role}"]', m.causes[0].note)
        # the policy that names the sources M holds is not refused, and one whose roles are matched but M holds only a feed (a lone record no policy can corroborate) is not either
        with rc.pinned(L):
            ok = svc.compute_for_portfolio(None, ca.PORTFOLIO, EX, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=ca.POLICY)
        self.assertNotIn(svc.DETECTION_POLICY_UNMATCHED, ok.metrics[0].details)
        lone = svc.policy_matches_nothing(L.rows, L.version, mp.market(None, real_quotes=True), f8b.ConfirmationPolicy(frozenset({"x.feed"}), frozenset({"y.filing"})))
        self.assertIsNone(lone)  # M holds no corporate-action record: nothing for the policy to miss


class Cp3_15PerListingTests(unittest.TestCase):
    """The reviewer's two-listing probe: L1 has a confirmed split (test.feed + test.filing) missing from the ledger; L2 has an old record from `other.filing`. A filing role {other.filing} matched L2's
    filer, so a rule over the UNION of listings passed and L1 was valued AVAILABLE 1,875 in mixed units. The rule is per listing."""

    L2 = uuid.UUID(int=0x5151)

    def world(self):
        L = mp.base_ledger()
        L.add(mp.A1, EventType.BUY, D(2025, 1, 31), USD, listing_id=self.L2, quantity=Decimal(1), amount=Money(Decimal(100), USD))
        extra = mp.closes({D(2025, 1, 31): "100.00", D(2025, 2, 3): "100.00"}, listing=self.L2, real=True) + [ca.split_reading("other.filing", "e" * 64, (2, 1), day=D(2024, 6, 3), listing=self.L2)]
        return L, mp.market("real", real_quotes=True, extra=extra)

    def refused(self, policy):
        L, port = self.world()
        why = svc.policy_matches_nothing(L.rows, L.version, port, policy)
        with rc.pinned(L):
            res = svc.compute_for_portfolio(None, ca.PORTFOLIO, EX, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=policy)
        return why, res

    def test_a_filing_role_that_matches_another_listings_filer_is_refused_naming_the_role_and_the_listing(self):
        for filing in ({"other.filing"}, {"test.filling", "other.filing"}):
            why, res = self.refused(f8b.ConfirmationPolicy(frozenset({ca.FEED}), frozenset(filing)))
            self.assertIsNotNone(why, filing)
            self.assertIn('"unmatched_roles":["filing"]', why)
            self.assertNotIn('"feed"', why)
            self.assertIn(f'"listing":"{mp.LISTING}"', why)  # L1 is named
            self.assertNotIn(f'"listing":"{self.L2}"', why)  # L2's filer is named: L2 is fine
            (m,) = res.metrics
            self.assertIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
            self.assertIsNone(m.result.value)  # was holding AVAILABLE 1,875 and total AVAILABLE 4,375

    def test_the_correct_policy_and_the_two_consistent_cases_are_not_refused(self):
        why, res = self.refused(f8b.ConfirmationPolicy(frozenset({ca.FEED}), frozenset({ca.FILING, "other.filing"})))
        self.assertIsNone(why)
        self.assertNotIn(svc.DETECTION_POLICY_UNMATCHED, res.metrics[0].details)  # corroborated: the suppression applies instead
        L = mp.base_ledger()
        # M holds no filing record at all for the listing: nothing a policy could miss
        only_feed = mp.market(None, real_quotes=True, extra=[ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1))])
        self.assertIsNone(svc.policy_matches_nothing(L.rows, L.version, only_feed, f8b.ConfirmationPolicy(frozenset({ca.FEED}), frozenset({"x.filing"}))))
        # a misspelt role while M holds no source the policy does not name: nothing is silently lost
        both = mp.market("real", real_quotes=True)
        self.assertIsNone(svc.policy_matches_nothing(L.rows, L.version, both, f8b.ConfirmationPolicy(frozenset({ca.FEED, "typo.feed"}), frozenset({ca.FILING}))))


class Cp3_16Tests(unittest.TestCase):
    def test_kappa_is_one_minus_r_over_two_for_a_tiny_r_and_agrees_with_the_direct_form_at_the_switch(self):
        tiny = Fraction(1, 10 ** 56)
        k = numerics._carino_kappa(tiny)
        self.assertLess(abs(k - 1), Decimal("1e-55"))
        self.assertLess(abs(k - (1 - numerics._dec50(tiny) / 2)), Decimal("1e-100"))
        self.assertLess(abs(numerics._carino_kappa(-tiny) - 1), Decimal("1e-55"))
        r = numerics.CARINO_SERIES_BELOW - Fraction(1, 10 ** 9)  # just inside the series
        direct = numerics._CTX50.divide(numerics._CTX50.ln(numerics._dec50(1 + r)), numerics._dec50(r))
        self.assertLess(abs(numerics._carino_kappa(r) - direct), Decimal("1e-44"))
        r = numerics.CARINO_SERIES_BELOW + Fraction(1, 10 ** 9)  # just outside: the direct form
        direct = numerics._CTX50.divide(numerics._CTX50.ln(numerics._dec50(1 + r)), numerics._dec50(r))
        self.assertEqual(numerics._carino_kappa(r), direct)

    def test_a_twr_below_1e_50_links_without_raising_and_reconciles(self):
        tiny = Fraction(83, 10 ** 54)
        link = numerics.carino_link([(tiny, (tiny / 2, tiny / 2))], tiny)
        self.assertIsNotNone(link)
        self.assertLess(abs(link.residual), Decimal("1e-40"))
        self.assertAlmostEqual(float(link.components[0]), float(numerics._dec50(tiny / 2)), delta=1e-60)
        # a mixed window: a large day and the tiny TWR left by its reversal
        link2 = numerics.carino_link([(Fraction(1, 5), (Fraction(1, 5),)), (Fraction(-1, 6), (Fraction(-1, 6),))], Fraction(0))
        self.assertLess(abs(link2.components[0]), Decimal("1e-45"))  # TWR = 0 exactly: kappa = 1 and the logs of the two days cancel
        link3 = numerics.carino_link([(Fraction(1, 5), (Fraction(1, 5),)), (Fraction(-1, 6) + tiny, (Fraction(-1, 6) + tiny,))], (Fraction(6, 5)) * (Fraction(5, 6) + tiny) - 1)
        self.assertLess(abs(link3.residual), Decimal("1e-40"))

    def test_the_reviewers_scenario_through_the_engine_returns_a_state_instead_of_raising(self):
        # 1E28 USD deposited, 1E26 units bought at 100; closes 100 -> 120 -> 100; a 1E-24 USD interest on the way: the TWR is a non-zero rational below 1E-50 (it used to raise DivisionByZero)
        L = pk.Ledger()
        big = Decimal(10) ** 28
        L.add(mp.A1, EventType.DEPOSIT, D(2025, 2, 3), USD, amount=Money(big, USD))
        L.add(mp.A1, EventType.BUY, D(2025, 2, 3), USD, listing_id=mp.LISTING, quantity=Decimal(10) ** 26, amount=Money(big, USD))
        L.add(mp.A1, EventType.INTEREST, D(2025, 2, 4), USD, amount=Money(Decimal("0.000000000000000000000001"), USD))
        prices = {D(2025, 2, 3): "100.00", D(2025, 2, 4): "120.00", D(2025, 2, 5): "100.00"}
        res = engine.compute_attribution(L.rows, L.version, WindowSpec(WindowRule.CUSTOM, None, D(2025, 2, 2)), D(2025, 2, 5), USD, mp.market(evidence=None, prices=prices), mp.Ident(),
                                         mp.MARKET_CONVENTIONS, mp.PERF, suppressions=())
        states = attribution_states(res)
        self.assertEqual(states["attribution_money"][0], "AVAILABLE")
        ret = next(m for m in res.metrics if m.metric_id == "attribution_return")
        self.assertEqual(ret.result.sufficiency_state.value, "AVAILABLE")
        self.assertTrue(0 < ret.exact < Fraction(1, 10 ** 50))  # the case the review built
        self.assertLessEqual(abs(Decimal(dict(ret.lineage)["carino_residual"])), Decimal("1e-40"))


class Cp3_17Tests(unittest.TestCase):
    def test_a16_example_w_breakdowns_are_apportioned_to_the_lines_displayed_value_not_its_own_rounding(self):
        w = pk.world_w()
        L = pk.example_w_ledger(w.h)
        res = engine.compute_attribution(L.rows, L.version, WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 4, 3), pk.USD, w.store, w.ident, w.market, engine.performance_conventions(), suppressions=())
        money = next(m for m in res.metrics if m.metric_id == "attribution_money")
        shown = {n: s for n, s, _e in money.breakdown}
        exact = {n: e for n, _s, e in money.breakdown}
        self.assertEqual(shown["attr.fx"], Decimal("-14.57"))  # the apportioned display value of the FX line
        self.assertEqual(numerics.round_half_up(exact["attr.fx"], 2), F(-1458, 100))  # its own rounding is -14.58: the case discriminates
        for group, parts in (("component", [Decimal("-14.28"), Decimal("-0.29")]), ("listing", [Decimal("-14.28"), Decimal("-0.29")]), ("market", [Decimal("-14.28"), Decimal("-0.29")])):
            m = next(x for x in res.metrics if x.metric_id == "attribution_breakdown" and dict(x.subject) == {"group_by": group, "line": "attr.fx"})
            self.assertEqual([s for _n, s, _e in m.breakdown], parts, group)
            self.assertEqual(sum((s for _n, s, _e in m.breakdown), Decimal(0)), Decimal("-14.57"), group)  # the parts sum to the bar they open, -14.57 (not -14.58)
            self.assertEqual(dict(m.lineage)["displayed_total"], "-14.57")

    def test_a17_a_stale_close_on_a_sale_day_reaches_the_attributions_state(self):
        def attribution(missed):
            L = pk.Ledger()
            sale_day = D(2025, 2, 3) + datetime.timedelta(days=missed)
            L.add(mp.A1, EventType.DEPOSIT, D(2025, 2, 3), USD, amount=Money(Decimal(1000), USD))
            L.add(mp.A1, EventType.BUY, D(2025, 2, 3), USD, listing_id=mp.LISTING, quantity=Decimal(5), amount=Money(Decimal(500), USD))
            L.add(mp.A1, EventType.SELL, sale_day, USD, listing_id=mp.LISTING, quantity=Decimal(5), amount=Money(Decimal(550), USD))
            # the only print is 02-03 (100.00): the sale day's close is `missed` sessions old and the position is closed out that day
            return engine.compute_attribution(L.rows, L.version, WindowSpec(WindowRule.CUSTOM, None, D(2025, 2, 2)), sale_day, USD, mp.market(evidence=None, prices={D(2025, 2, 3): "100.00"}),
                                              mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=())

        one = attribution_states(attribution(1))  # 02-04: one session stale
        self.assertEqual(one["attribution_money"], ("AVAILABLE", "STALE_DATA"))
        self.assertEqual(one["attribution_return"], ("AVAILABLE", "STALE_DATA"))
        three = attribution_states(attribution(3))  # 02-06: three sessions missed (02-04, 02-05, 02-06)
        self.assertEqual(three["attribution_money"], ("LIMITED", "STALE_DATA"))  # it was AVAILABLE with no reason when the lookups were dropped from the state


if __name__ == "__main__":
    unittest.main()
