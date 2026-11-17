"""The CP3 midpoint RE-CHECK findings (`reviews/TECH_REVIEW.md` section 29): CP3-9, CP3-10, CP3-11, and Current mode's split detection over `M_t`
(performance/1.4 Ruling 1.7). Each test reproduces the reviewer's probe; the database tests run the same probe through PostgreSQL as `finweb_app`.
"""

import dataclasses
import datetime
import itertools
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_kit  # noqa: E402
import marketdata_exit_kit as x  # noqa: E402
import performance_kit as pk  # noqa: E402
import pg_market_kit as pgk  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from domain.replay import live_events  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.manifest import MarketDataRelease  # noqa: E402
from marketdata.port import MarketDataPort  # noqa: E402
from marketdata.store import InMemoryMarketData  # noqa: E402
from performance.engine import compute_current  # noqa: E402
from performance.inputs import MarketView  # noqa: E402
from performance.taint import carried_suppressions  # noqa: E402
from performance_service import service as svc  # noqa: E402
from product_contract.vocabulary import SufficiencyState  # noqa: E402

D = datetime.date
F = mp.F
A1, A2, A3, A4 = mp.A1, mp.A2, mp.A3, uuid.UUID(int=4)
USD, PERF, LISTING = mp.USD, mp.PERF, mp.LISTING
INSUFFICIENT = SufficiencyState.INSUFFICIENT_DATA
DAY = D(2025, 2, 5)


def pinned(L):
    return mock.patch.object(svc, "_pin", return_value=(L.version, tuple(L.rows)))


def hop(L, source, receiver):
    return mp.internal_transfer(L, DAY, source, receiver)


# ===== CP3-9: a same-day chain recorded in reverse order =======================================================================================

class SameDayChainTests(unittest.TestCase):
    HOPS = ((A1, A2), (A2, A3), (A3, A4))

    def ledger(self, order):
        L = mp.base_ledger()
        for i in order:
            hop(L, *self.HOPS[i])
        return L

    def carried(self, L, port):
        return carried_suppressions(live_events(L.rows, L.version), mp.detect(L, port))

    def test_the_review_probe_a2_to_a3_recorded_before_a1_to_a2_is_carried_to_a3(self):
        port = mp.market()
        natural, reverse = self.ledger((0, 1)), self.ledger((1, 0))
        for L in (natural, reverse):
            (a3,) = self.carried(L, port)  # (CP3d, Ruling 1.1a) A2 only passes the units on the day it receives them: its end-of-day book holds none, so it carries no suppression
            self.assertEqual((a3.account_id, a3.first_date, a3.end_exclusive), (A3, DAY, None))
            for day in (D(2025, 2, 6), D(2025, 2, 10)):
                total = mp.metric(mp.value(L, day, port, mp.detect(L, port)), "portfolio_value", "REPORTING")
                mp.insufficient_conflict(self, total, f"{day}")  # was AVAILABLE 4375 in the reverse order
        self.assertEqual(self.carried(natural, port), self.carried(reverse, port))  # the whole result is order independent, flags included

    def test_every_order_of_a_three_hop_same_day_chain_gives_the_same_carry(self):
        port = mp.market()
        results = {}
        for order in itertools.permutations(range(3)):
            L = self.ledger(order)
            results[order] = self.carried(L, port)
            self.assertEqual([c.account_id for c in results[order]], [A4], order)  # A2 and A3 are transit accounts of the day
            mp.insufficient_conflict(self, mp.metric(mp.value(L, D(2025, 2, 10), port, mp.detect(L, port)), "portfolio_value", "REPORTING"), str(order))
        self.assertEqual(len(set(results.values())), 1)  # metamorphic: permuting the same-day legs changes no output (Ruling 11.3(1))

    def test_a_longer_chain_over_two_days_and_a_cycle_on_one_day_terminate(self):
        port = mp.market()
        L = mp.base_ledger()
        mp.internal_transfer(L, D(2025, 2, 6), A3, A4)  # recorded first, dated later
        hop(L, A2, A3)
        hop(L, A1, A2)
        carried = self.carried(L, port)
        self.assertEqual({c.account_id: (c.first_date, c.end_exclusive) for c in carried}, {A3: (DAY, D(2025, 2, 6)), A4: (D(2025, 2, 6), None)})
        cyc = mp.base_ledger()
        hop(cyc, A1, A2)
        hop(cyc, A2, A1)  # the units go there and back on one day
        # a same-day transfer cycle is basis-unresolved under FIFO/1 (ledger-replay 0.5.9 (c)): no lot book, so no tainted lot to follow; it ends, deterministic, no exception
        self.assertEqual(self.carried(cyc, port), ())
        self.assertEqual(self.carried(cyc, port), self.carried(cyc, port))

    def test_a_chain_whose_account_ids_run_against_the_hops_is_carried_too(self):
        """The account ids run against the hops: the units start in A3 and move A3 -> A2 -> A1 on one day, in either entry order. Since CP3d the lot book (one fold per
        ledger version, independent of entry order) decides it: A1 ends the day holding the tainted lot, and A3 and A2 only pass it on."""
        for order in itertools.permutations(range(2)):
            L = pk.Ledger()
            L.add(A3, EventType.DEPOSIT, D(2024, 12, 20), USD, amount=Money(Decimal(10000), USD))
            L.add(A3, EventType.BUY, D(2024, 12, 20), USD, listing_id=LISTING, quantity=Decimal(50), amount=Money(Decimal(7500), USD))
            for i in order:
                hop(L, *((A3, A2), (A2, A1))[i])
            port = mp.market()
            sup = carried_suppressions(live_events(L.rows, L.version), mp.detect(L, port))
            self.assertEqual([c.account_id for c in sup], [A1], order)
            mp.insufficient_conflict(self, mp.metric(mp.value(L, D(2025, 2, 10), port, mp.detect(L, port)), "portfolio_value", "REPORTING"), str(order))

    def test_the_service_gives_the_same_suppressed_total_for_either_order(self):
        for order in ((0, 1), (1, 0)):
            L = self.ledger(order)
            with pinned(L):
                res = svc.compute_for_portfolio(None, ca.PORTFOLIO, D(2025, 2, 6), USD, mp.market("real", real_quotes=True), mp.Ident(), mp.MARKET_CONVENTIONS, PERF,
                                                policy=ca.POLICY)
            mp.insufficient_conflict(self, mp.metric(res, "portfolio_value", "REPORTING"), str(order))


# ===== CP3-10: the synthetic refusal does not depend on an optional attribute ==============================================================

class _Hidden:
    """The review's wrapper: forwards the `MarketDataPort` methods and `release`, and HIDES `contains_synthetic`."""

    def __init__(self, inner):
        self._inner, self.release = inner, inner.release

    def __getattr__(self, name):
        if name == "contains_synthetic":
            raise AttributeError(name)
        return getattr(self._inner, name)


class _Lying(_Hidden):
    contains_synthetic = False


class SyntheticRefusalTests(unittest.TestCase):
    def run_service(self, port, entry="value"):
        L = mp.base_ledger()
        with pinned(L):
            if entry == "window":
                return svc.compute_window_for_portfolio(None, ca.PORTFOLIO, mp.WindowSpec(mp.WindowRule.CUSTOM, None, D(2025, 1, 30)), D(2025, 1, 31), USD, port,
                                                        mp.Ident(), mp.MARKET_CONVENTIONS, PERF, policy=ca.POLICY)
            return svc.compute_for_portfolio(None, ca.PORTFOLIO, D(2025, 1, 31), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, PERF, policy=ca.POLICY)

    def test_the_port_interface_requires_the_member_and_both_stores_have_it(self):
        self.assertIn("contains_synthetic", MarketDataPort.__dict__)
        self.assertTrue(isinstance(InMemoryMarketData.contains_synthetic, property))

    def test_the_review_probe_a_wrapper_that_hides_it_is_refused_where_it_was_returning_available_10000(self):
        synthetic = mp.market(None)  # synthetic quotes
        self.assertTrue(synthetic.contains_synthetic)
        L = mp.base_ledger()
        direct = pk.compute(L.rows, L.version, D(2025, 1, 31), USD, _Hidden(synthetic), mp.Ident(), mp.MARKET_CONVENTIONS, PERF, suppressions=())
        self.assertEqual(mp.metric(direct, "portfolio_value", "REPORTING").exact, F(10000))  # the engine, called directly, is allowed ...
        self.assertTrue(direct.manifest.synthetic)  # ... and says synthetic (what the reviewer saw, with the old service gate, at AVAILABLE 10000)
        for entry in ("value", "window"):
            for port in (_Hidden(synthetic), _Lying(synthetic), synthetic):
                (m,) = self.run_service(port, entry).metrics
                self.assertEqual((m.result.value, m.result.sufficiency_state), (None, INSUFFICIENT), (entry, type(port).__name__))
                self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, m.details)

    def test_a_port_that_is_not_synthetic_is_not_refused_and_a_hiding_wrapper_over_it_is(self):
        real = mp.market(None, real_quotes=True)
        self.assertFalse(real.contains_synthetic)
        (ok,) = [m for m in self.run_service(real).metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"]
        self.assertEqual(ok.exact, F(10000))
        (hidden,) = self.run_service(_Hidden(real)).metrics  # it cannot say, so it is treated as synthetic: fail closed
        self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, hidden.details)


# ===== CP3-11: the confirmation policy is cited, and one that matches nothing is refused ===================================================

class DetectionPolicyTests(unittest.TestCase):
    NOBODY = f8b.ConfirmationPolicy(frozenset({"nobody.feed"}), frozenset({"nobody.filing"}))

    def run_service(self, port, policy, day=D(2025, 2, 3)):
        L = mp.base_ledger()
        with pinned(L):
            return svc.compute_for_portfolio(None, ca.PORTFOLIO, day, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, PERF, policy=policy)

    def test_the_review_probe_a_policy_naming_absent_sources_is_refused_not_a_mixed_unit_value(self):
        port = mp.market("real", real_quotes=True)
        res = self.run_service(port, self.NOBODY)
        (m,) = res.metrics
        self.assertEqual((m.result.value, m.result.sufficiency_state), (None, INSUFFICIENT))  # was AVAILABLE 1,875 at 02-03 (4,375 with the cash in the review)
        self.assertIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
        self.assertIn("test.feed", m.causes[0].note)  # the message names the sources M does hold
        self.assertEqual(dict(res.manifest.detection_policy)["feed"], "nobody.feed")  # and the policy is cited even on a refusal

    def test_the_policy_is_cited_in_the_manifest_and_changes_the_manifest_id(self):
        port = mp.market("real", real_quotes=True)
        good = self.run_service(port, ca.POLICY)
        mp.insufficient_conflict(self, mp.metric(good, "holding_value", "NATIVE"))  # detection works under the right policy
        cited = dict(good.manifest.detection_policy)
        self.assertEqual((cited["feed"], cited["filing"]), (ca.FEED, ca.FILING))
        self.assertEqual(len(cited["digest"]), 64)
        wider = f8b.ConfirmationPolicy(frozenset({ca.FEED, "extra.feed"}), frozenset({ca.FILING}))
        other = self.run_service(port, wider)
        self.assertNotEqual(dict(other.manifest.detection_policy)["digest"], cited["digest"])
        self.assertNotEqual(other.manifest.manifest_id, good.manifest.manifest_id)  # an input that changes the question is part of it
        from performance.manifest import ReproductionStatus  # noqa: PLC0415

        L = mp.base_ledger()
        again = pk.reproduce(good.manifest, good.result_digest, L.rows, port, mp.Ident(), mp.MARKET_CONVENTIONS, PERF, suppressions=mp.detect(L, port))
        self.assertEqual(again.status, ReproductionStatus.REPRODUCED)  # a reproduction re-runs under the same policy

    def test_where_m_holds_no_corporate_action_record_there_is_nothing_for_the_policy_to_miss(self):
        res = self.run_service(mp.market(None, real_quotes=True), self.NOBODY, day=D(2025, 1, 31))
        self.assertEqual(mp.metric(res, "portfolio_value", "REPORTING").exact, F(10000))
        self.assertEqual(dict(res.manifest.detection_policy)["feed"], "nobody.feed")

    def test_a_policy_that_recognises_one_role_only_is_refused_naming_the_unmatched_role_cp3_15(self):
        # (CP3-15, TECH_REVIEW section 30: this was `not refused`, and the half-matching policy valued the position in mixed units, AVAILABLE 4,375)
        half = f8b.ConfirmationPolicy(frozenset({ca.FEED}), frozenset({"nobody.filing"}))
        res = self.run_service(mp.market("real", real_quotes=True), half)
        (m,) = res.metrics
        self.assertIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
        self.assertEqual(m.result.value, None)
        self.assertIn('"unmatched_roles":["filing"]', m.causes[0].note)  # the unmatched role is named (market-data/1.11 Ruling 6.4d item 6)
        self.assertNotIn('"feed"', m.causes[0].note)


# ===== performance/1.4 Ruling 1.7: Current mode detects over M_t =============================================================================

class ProbeMarketAt:
    """`M_t` for the probe market: the readings whose retrieval time is at or before `t` (quotes AND corporate-action records), as a derived release."""

    def __init__(self, readings):
        self.readings = list(readings)
        with gate_kit.admitted_real_world(self.readings, mp.MIC):  # 1.16 Ruling 4.7 item 6: see gate_kit
            self.parent = InMemoryMarketData(MarketDataRelease(name="mt-probe", files=(), source_precedence=()), self.readings, exchange_of=lambda _l: mp.MIC,
                                             source_records=ca.k.records_for(self.readings))

    def view(self, instant):
        keep = [r for r in self.readings if r.observation.lineage.retrieved_at <= instant]
        kept = {r.file_sha256 for r in keep}
        left = tuple(sorted({r.file_sha256 for r in self.readings if r.observation.lineage.retrieved_at > instant} - kept))
        release = MarketDataRelease(name=f"mt-probe@{instant.isoformat()}", files=(), source_precedence=())
        with gate_kit.admitted_real_world(keep, mp.MIC):
            store = InMemoryMarketData(release, keep, exchange_of=lambda _l: mp.MIC, source_records=ca.k.records_for(keep))
        return MarketView(store, ca.CALENDARS, mp.MARKET_CONVENTIONS, self.parent.release_id(), left, instant)


class CurrentModeDetectionTests(unittest.TestCase):
    def readings(self):
        utc = datetime.timezone.utc
        quotes = []
        for day, price in mp.PRICES.items():
            r = pk.quote(LISTING, day, price, USD, "US", retrieved=datetime.datetime(2025, 2, 4, 0, 0, tzinfo=utc), sha="e" * 64)
            obs = dataclasses.replace(r.observation, lineage=dataclasses.replace(r.observation.lineage, usage_scope=ca.REAL))
            quotes.append(dataclasses.replace(r, observation=obs))
        evidence = []
        for r in (ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1)), ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1))):
            lin = dataclasses.replace(r.observation.lineage, retrieved_at=datetime.datetime(2025, 2, 10, 12, 0, tzinfo=utc))  # the evidence is retrieved 02-10
            evidence.append(dataclasses.replace(r, observation=dataclasses.replace(r.observation, lineage=lin)))
        return quotes + evidence

    def run_at(self, instant):
        L = mp.base_ledger()
        with pinned(L):
            return svc.compute_current_for_portfolio(None, ca.PORTFOLIO, instant, USD, mp.Ident(), ProbeMarketAt(self.readings()), PERF, policy=ca.POLICY)

    def test_detection_sees_only_the_files_retrieved_by_t(self):
        utc = datetime.timezone.utc
        early = self.run_at(datetime.datetime(2025, 2, 6, 23, 0, tzinfo=utc))  # before the evidence was retrieved: M_t holds no corporate-action record
        self.assertEqual(early.manifest.split_detection, "F8B_DRY_RUN")
        h = mp.metric(early, "holding_value", "NATIVE")
        self.assertEqual((h.exact, h.result.sufficiency_state.value), (F(1875), "AVAILABLE"))  # nothing was known at t: the value a computation at t could give
        self.assertEqual(early.manifest.excluded_files, tuple(sorted({ca.FEED_SHA, ca.FILING_SHA})))  # t, M and the excluded hashes are cited
        late = self.run_at(datetime.datetime(2025, 2, 11, 23, 0, tzinfo=utc))  # after: the evidence is in M_t, so detection suppresses
        mp.insufficient_conflict(self, mp.metric(late, "holding_value", "NATIVE"))
        self.assertEqual(late.manifest.excluded_files, ())
        self.assertNotEqual(late.manifest.split_suppressions_digest, early.manifest.split_suppressions_digest)

    def test_the_engine_alone_does_not_detect_it_runs_over_the_suppressions_it_is_given(self):
        L = mp.base_ledger()
        res = compute_current(L.rows, L.version, datetime.datetime(2025, 2, 11, 23, 0, tzinfo=datetime.timezone.utc), USD, mp.Ident(),
                              ProbeMarketAt(self.readings()), PERF, suppressions=())
        self.assertEqual(res.manifest.split_detection, "CALLER_SUPPLIED")  # the SERVICE is what runs detection over M_t (the test above)


# ===== the same probes through PostgreSQL as finweb_app ========================================================================================

_SKIP = pgk.skip_reason()


@unittest.skipIf(bool(_SKIP), _SKIP)
class PostgresRecheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from persistence import ledger_replay_store, ledger_store  # noqa: PLC0415

        cls.rs, cls.ls = ledger_replay_store, ledger_store
        cls.db = pgk.PgSchema().open()
        cls.addClassCleanup(cls.db.close)
        cls.ident = x.identity()
        pgk.insert_identity(cls.db.owner, cls.ident)
        cls.aapl = x.lid(cls.ident, "AAPL", "XNAS")
        cls.app = cls.db.app_connection()
        cls.addClassCleanup(cls.app.close)
        cls.calendars = market11_conventions(ca.CALENDARS)  # replaced below with an XNAS calendar
        import marketdata_cp2c1_kit as k  # noqa: PLC0415

        cls.conventions = market11_conventions(__import__("marketdata.calendars", fromlist=["CalendarSet"]).CalendarSet(
            [k.exchange_calendar("TEST_SESSIONS", ("XNAS",), ca.weekdays(D(2024, 6, 3), D(2026, 6, 30)))]))

    def portfolio(self, order, hops=((0, 1), (1, 2))):
        user, portfolio = uuid.uuid4(), uuid.uuid4()
        accounts = [uuid.uuid4() for _ in range(4)]
        owner = self.db.owner
        owner.execute("INSERT INTO app_user VALUES (%s)", (user,))
        owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (portfolio, user))
        for a in accounts:
            owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (a, portfolio))
        self.ls.append_batch(self.app, [
            LedgerEvent(uuid.uuid4(), accounts[0], EventType.DEPOSIT, D(2024, 12, 19), USD, amount=Money(Decimal(10000), USD)),
            LedgerEvent(uuid.uuid4(), accounts[0], EventType.BUY, D(2024, 12, 20), USD, listing_id=self.aapl, quantity=Decimal(50), amount=Money(Decimal(7500), USD))])
        for i in order:
            s, r = hops[i]
            out = LedgerEvent(uuid.uuid4(), accounts[s], EventType.TRANSFER_OUT, DAY, USD, listing_id=self.aapl, quantity=Decimal(50),
                              counterparty_account_id=accounts[r])
            inn = LedgerEvent(uuid.uuid4(), accounts[r], EventType.TRANSFER_IN, DAY, USD, listing_id=self.aapl, quantity=Decimal(50),
                              counterparty_account_id=accounts[s])
            self.ls.append_internal_transfer(self.app, out, inn)
        return portfolio

    def market(self, evidence="real", real_quotes=True):
        return mp.market(evidence, real_quotes=real_quotes, listing=self.aapl, mic="XNAS")

    def total(self, res):
        return mp.metric(res, "portfolio_value", "REPORTING")

    def test_cp3_9_the_reverse_order_chain_through_postgresql_is_suppressed_in_either_order(self):
        for order in ((0, 1), (1, 0)):
            portfolio = self.portfolio(order)
            for day in (D(2025, 2, 6), D(2025, 2, 10)):
                res = svc.compute_for_portfolio(self.app, portfolio, day, USD, self.market(), self.ident, self.conventions, PERF, policy=ca.POLICY)
                mp.insufficient_conflict(self, self.total(res), f"{order} {day}")  # the reviewer's probe gave AVAILABLE 4375 for (1, 0)
                self.assertEqual(res.manifest.split_detection, "F8B_DRY_RUN")

    def test_cp3_9_a_three_hop_chain_in_every_order_through_postgresql(self):
        hops = ((0, 1), (1, 2), (2, 3))
        digests = set()
        for order in itertools.permutations(range(3)):
            portfolio = self.portfolio(order, hops)
            res = svc.compute_for_portfolio(self.app, portfolio, D(2025, 2, 10), USD, self.market(), self.ident, self.conventions, PERF, policy=ca.POLICY)
            mp.insufficient_conflict(self, self.total(res), str(order))
            digests.add(res.manifest.split_suppressions_digest.__len__())
        self.assertEqual(digests, {64})

    def test_cp3_10_a_hiding_wrapper_is_refused_through_postgresql(self):
        portfolio = self.portfolio((0, 1))
        for port in (_Hidden(self.market()), _Hidden(self.market(None)), _Lying(self.market(None, real_quotes=False))):
            res = svc.compute_for_portfolio(self.app, portfolio, D(2025, 1, 31), USD, port, self.ident, self.conventions, PERF, policy=ca.POLICY)
            (m,) = res.metrics
            self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, m.details)

    def test_cp3_11_an_unmatched_policy_is_refused_through_postgresql(self):
        portfolio = self.portfolio((0, 1))
        res = svc.compute_for_portfolio(self.app, portfolio, D(2025, 2, 3), USD, self.market(), self.ident, self.conventions, PERF, policy=DetectionPolicyTests.NOBODY)
        self.assertIn(svc.DETECTION_POLICY_UNMATCHED, res.metrics[0].details)
        self.assertEqual(res.metrics[0].result.value, None)


if __name__ == "__main__":
    unittest.main()
