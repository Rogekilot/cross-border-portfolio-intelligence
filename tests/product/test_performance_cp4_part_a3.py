"""CP4 part A, round 3 (tech plan 16.26): review section 34 (CP4-6 to CP4-9) and the Quant's build-note rulings on `performance/1.12`.

- CP4-6: an F8-B run is ALL OR NOTHING (Ruling 6.4d item 5): it runs in one unit under the portfolio's ledger lock (`LedgerAccess.atomic`), so a refusal, or any exception, leaves the ledger as it was.
- CP4-7: every refusal, Current and historical, carries `identity_digest` and `source_registry_digest` over the view it read.
- `valuation_mode`: a distinct `CURRENT_AT_INSTANT`, recorded by every Current-mode manifest (computed or refused); the combinations of the build note are an engine fault otherwise.
- CP4-8: the registry digest is never "" (`read_release` requires the registry, applies `require_attested`, and refuses a stored row that disagrees with the pinned record).
- CP4-9: `D_c(t)` considers every money field of a live event dated `D`.
"""

import dataclasses
import datetime
import sys
import unittest
import unittest.mock
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_cp2c1_kit as k  # noqa: E402
import performance_kit as pk  # noqa: E402
import pg_market_kit as pgk  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402
import test_performance_cp4_part_a as a1  # noqa: E402
import test_performance_cp4_part_a2 as a2  # noqa: E402
import test_performance_final_review as fr  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402
import test_performance_recheck as rc  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.manifest import SourceRecord, SourceRegistry  # noqa: E402
from marketdata.market11 import UNBUILT, market11_conventions  # noqa: E402
from performance import current, engine  # noqa: E402
from performance.inputs import ValuationMode  # noqa: E402
from performance.manifest import ReproductionStatus  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402
from performance_service import service as svc  # noqa: E402
from persistence import market_data_store as mds  # noqa: E402

D = datetime.date
USD, HKD = mp.USD, CurrencyCode("HKD")
UTC = datetime.timezone.utc


# ===== CP4-6: all or nothing ====================================================================================================================

class Cp4_6Tests(unittest.TestCase):
    B = ca.OTHER_LISTING
    EX_B = D(2025, 3, 3)

    def readings(self):
        l1 = [ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1)), ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1))]  # L1: corroborated 4:1 at 2025-02-03, decided FIRST
        b = [ca.split_reading(ca.FEED, ca.FEED_SHA, (2, 1), day=self.EX_B, listing=self.B), ca.split_reading(ca.FILING, ca.FILING_SHA, (2, 1), day=self.EX_B, listing=self.B),
             ca.split_reading("third.feed", "f" * 64, (3, 1), day=self.EX_B, listing=self.B)]  # B: case (c) at 2025-03-03
        return l1 + b

    def run_f8b(self, ledger, listings=(ca.LISTING, ca.OTHER_LISTING)):
        return f8b.confirm_splits(ledger, ca.port_with(self.readings()), ca.PORTFOLIO, listings, D(2025, 1, 1), D(2025, 12, 31), ca.POLICY,
                                  {ca.LISTING: USD, self.B: USD}, calendars=ca.CALENDARS, exchange_of=ca.exchange_of)

    def test_the_reviewers_reproduction_l1_is_decided_then_b_refuses_and_the_ledger_is_exactly_as_before(self):
        bought = LedgerEvent(ca.eid(), ca.A1, EventType.BUY, D(2024, 12, 23), USD, listing_id=self.B, quantity=Decimal(50), amount=Money(Decimal(7500), USD))
        for race_on in (4, 5):  # the concurrent writer's BUY of B appears on the load AFTER L1's split was appended
            ledger = a2.RacingLedger(race_on, bought)
            ledger.add(LedgerEvent(ca.eid(), ca.A1, EventType.DEPOSIT, D(2024, 12, 20), USD, amount=Money(Decimal(10000), USD)))
            ledger.add(LedgerEvent(ca.eid(), ca.A1, EventType.BUY, D(2024, 12, 20), USD, listing_id=ca.LISTING, quantity=Decimal(50), amount=Money(Decimal(7500), USD)))
            before = [r.event.event_id for r in ledger.rows]
            with self.assertRaises(f8b.DetectionPolicyUnmatchedError) as ctx:
                self.run_f8b(ledger)
            self.assertEqual(a1.keys_of(ctx.exception.keys), [a1.key(self.B, self.EX_B, ["third.feed"], [])], race_on)
            self.assertEqual([r.event.event_id for r in ledger.rows], before + [bought.event_id], race_on)  # L1's appended split was rolled back; only the OTHER writer's BUY remains
            self.assertEqual(ledger.appended, [], race_on)
            self.assertEqual(ledger.load(ca.PORTFOLIO)[0], max(r.ledger_seq for r in ledger.rows), race_on)  # the committed version is the last row that exists
            self.assertFalse([r for r in ledger.rows if r.event.source_reference and r.event.source_reference.startswith("finweb.f8b")], race_on)

    def test_any_exception_after_an_append_rolls_the_whole_run_back_in_memory(self):
        ledger = ca.ledger_with_holdings(accounts=(ca.A1, ca.A2))  # two accounts hold L1: two appends for one corroborated split
        before = [r.event.event_id for r in ledger.rows]
        real = ledger.append
        calls = []

        def flaky(event):
            calls.append(event)
            if len(calls) == 2:
                raise RuntimeError("the second append fails")
            return real(event)

        ledger.append = flaky
        with self.assertRaises(RuntimeError):
            f8b.confirm_splits(ledger, ca.port_with(self.readings()[:2]), ca.PORTFOLIO, (ca.LISTING,), D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {ca.LISTING: USD},
                               calendars=ca.CALENDARS, exchange_of=ca.exchange_of)
        self.assertEqual(len(calls), 2)  # the first append happened inside the run ...
        self.assertEqual([r.event.event_id for r in ledger.rows], before)  # ... and is gone: nothing of the run is left
        self.assertEqual(ledger.appended, [])
        # the control: without the failure both appends stay
        ledger2 = ca.ledger_with_holdings(accounts=(ca.A1, ca.A2))
        report = f8b.confirm_splits(ledger2, ca.port_with(self.readings()[:2]), ca.PORTFOLIO, (ca.LISTING,), D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {ca.LISTING: USD},
                                    calendars=ca.CALENDARS, exchange_of=ca.exchange_of)
        self.assertEqual(len(ledger2.appended), 2)
        self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.APPENDED] * 2)

    def test_an_access_that_cannot_run_atomically_is_refused_and_nothing_is_appended(self):
        class NoAtomic:
            def __init__(self, inner):
                self.inner = inner

            def load(self, portfolio_id):
                return self.inner.load(portfolio_id)

            def append(self, event):
                return self.inner.append(event)

        ledger = ca.ledger_with_holdings()
        with self.assertRaises(TypeError):
            f8b.confirm_splits(NoAtomic(ledger), ca.port_with(self.readings()[:2]), ca.PORTFOLIO, (ca.LISTING,), D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {ca.LISTING: USD},
                               calendars=ca.CALENDARS, exchange_of=ca.exchange_of)
        self.assertEqual(ledger.appended, [])

    def test_the_read_only_accesses_have_a_no_op_atomic_so_detection_still_runs(self):
        import contextlib  # noqa: PLC0415

        for access in (svc.ReadOnlyLedgerAccess(None), svc.PinnedLedgerAccess(0, ())):
            self.assertIsInstance(access.atomic(ca.PORTFOLIO), type(contextlib.nullcontext()))


@unittest.skipIf(bool(pgk.skip_reason()), pgk.skip_reason())
class Cp4_6PostgresTests(unittest.TestCase):
    """The same property on PostgreSQL as `finweb_app`: one transaction under the portfolio lock, so a failure after the first append leaves no row and an unchanged ledger version."""

    @classmethod
    def setUpClass(cls):
        rc.PostgresRecheckTests.setUpClass.__func__(cls)

    def two_accounts(self):
        user, portfolio = uuid.uuid4(), uuid.uuid4()
        accounts = [uuid.uuid4(), uuid.uuid4()]
        owner = self.db.owner
        owner.execute("INSERT INTO app_user VALUES (%s)", (user,))
        owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (portfolio, user))
        for a in accounts:
            owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (a, portfolio))
        for a in accounts:
            self.ls.append_batch(self.app, [LedgerEvent(uuid.uuid4(), a, EventType.DEPOSIT, D(2024, 12, 19), USD, amount=Money(Decimal(10000), USD)),
                                            LedgerEvent(uuid.uuid4(), a, EventType.BUY, D(2024, 12, 20), USD, listing_id=self.aapl, quantity=Decimal(50), amount=Money(Decimal(7500), USD))])
        return portfolio

    def run_f8b(self, portfolio):
        port = mp.market(None, real_quotes=True, listing=self.aapl, mic="XNAS", extra=a1.feed_and_filing(self.aapl))
        return f8b.confirm_splits(f8b.PostgresLedgerAccess(self.app), port, portfolio, [self.aapl], D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {self.aapl: USD},
                                  calendars=self.conventions.freshness.calendars, exchange_of=self.ident.exchange_mic)

    def f8b_rows(self, portfolio):
        return self.db.owner.execute("SELECT count(*) FROM ledger_event WHERE portfolio_id = %s AND source_reference LIKE 'finweb.f8b%%'", (portfolio,)).fetchone()[0]

    def test_a_failure_after_the_first_append_leaves_the_ledger_exactly_as_before(self):
        portfolio = self.two_accounts()
        before = self.rs.current_ledger_version(self.app, portfolio)
        real = self.ls.append_system_event
        calls = []

        def flaky(conn, event, *, namespace):
            calls.append(event.event_id)
            if len(calls) == 2:
                raise RuntimeError("the second append fails")
            return real(conn, event, namespace=namespace)

        with unittest.mock.patch.object(f8b.ledger_store, "append_system_event", flaky), self.assertRaises(RuntimeError):
            self.run_f8b(portfolio)
        self.assertEqual(len(calls), 2)  # the first append DID run inside the run
        self.assertEqual(self.rs.current_ledger_version(self.app, portfolio), before)  # and is rolled back
        self.assertEqual(self.f8b_rows(portfolio), 0)

    def test_the_unfailed_run_appends_for_both_accounts_in_one_unit(self):
        portfolio = self.two_accounts()
        before = self.rs.current_ledger_version(self.app, portfolio)
        report = self.run_f8b(portfolio)
        self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.APPENDED] * 2)
        self.assertEqual(self.f8b_rows(portfolio), 2)
        self.assertGreater(self.rs.current_ledger_version(self.app, portfolio), before)
        again = self.run_f8b(portfolio)  # idempotent: nothing new
        self.assertEqual(self.f8b_rows(portfolio), 2)
        self.assertEqual([o.decision for o in again.outcomes], [f8b.SplitDecision.ALREADY_RECORDED] * 2)

    def test_a_policy_refusal_through_postgresql_appends_nothing_for_any_listing(self):
        portfolio = self.two_accounts()
        port = mp.market(None, real_quotes=True, listing=self.aapl, mic="XNAS", extra=a1.feed_and_filing(self.aapl) + [ca.split_reading("third.feed", "f" * 64, (2, 1), listing=self.aapl)])
        before = self.rs.current_ledger_version(self.app, portfolio)
        with self.assertRaises(f8b.DetectionPolicyUnmatchedError):
            f8b.confirm_splits(f8b.PostgresLedgerAccess(self.app), port, portfolio, [self.aapl], D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {self.aapl: USD},
                               calendars=self.conventions.freshness.calendars, exchange_of=self.ident.exchange_mic)
        self.assertEqual((self.rs.current_ledger_version(self.app, portfolio), self.f8b_rows(portfolio)), (before, 0))


# ===== CP4-7: every refusal carries both digests =====================================================================================================

class Cp4_7Tests(unittest.TestCase):
    def test_historical_refusals_carry_the_digests_the_computed_manifest_over_the_same_view_carries(self):
        L = mp.base_ledger()
        port = mp.market("real", real_quotes=True)
        with rc.pinned(L):
            computed = svc.compute_for_portfolio(None, ca.PORTFOLIO, D(2025, 1, 31), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=ca.POLICY)
            refused = svc.compute_for_portfolio(None, ca.PORTFOLIO, D(2025, 1, 31), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=a1.policy(filing=("typo.filing",)))
        self.assertIn(svc.DETECTION_POLICY_UNMATCHED, refused.metrics[0].details)
        self.assertTrue(refused.manifest.source_registry_digest)
        self.assertEqual(refused.manifest.source_registry_digest, computed.manifest.source_registry_digest)  # the same view, the same registry pin
        from performance.identity import RecordingResolver  # noqa: PLC0415

        nothing_asked = RecordingResolver(mp.Ident()).digest()
        self.assertNotIn(refused.manifest.identity_digest, ("", nothing_asked))  # it pins the exchange and currency of the listing the ledger names (the computed manifest asks for more)
        # the synthetic refusal of a computed result (belt and braces) carries the digests of that result
        synthetic = mp.market("synthetic", real_quotes=True)
        with rc.pinned(L):
            syn = svc.compute_for_portfolio(None, ca.PORTFOLIO, D(2025, 1, 31), USD, synthetic, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=ca.POLICY)
        self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, syn.metrics[0].details)
        self.assertEqual(syn.manifest.source_registry_digest, engine.registry_digest_of(synthetic))
        self.assertTrue(syn.manifest.identity_digest)

    def test_current_refusals_carry_the_digests_on_every_current_entry_and_for_both_causes(self):
        t = a2.utc_dt(2025, 2, 11, 23, 0)
        for third, synthetic, code in ((True, False, svc.DETECTION_POLICY_UNMATCHED), (False, True, svc.SYNTHETIC_MARKET_DATA_REFUSED)):
            market_at = a2.Cp4_2Tests.market_at(None, third=third, synthetic=synthetic)
            view = market_at.view(t)
            with rc.pinned(mp.base_ledger()):
                results = (svc.compute_current_for_portfolio(None, ca.PORTFOLIO, t, USD, mp.Ident(), market_at, mp.PERF, policy=ca.POLICY),
                           svc.compute_gains_current_for_portfolio(None, ca.PORTFOLIO, t, USD, mp.Ident(), market_at, mp.PERF, policy=ca.POLICY, window=fr.CUSTOM),
                           svc.compute_attribution_current_for_portfolio(None, ca.PORTFOLIO, t, fr.CUSTOM, USD, mp.Ident(), market_at, mp.PERF, policy=ca.POLICY))
            for res in results:
                self.assertIn(code, res.metrics[0].details)
                self.assertEqual(res.manifest.source_registry_digest, engine.registry_digest_of(view.port))  # M_t's registry
                self.assertTrue(res.manifest.identity_digest)


# ===== valuation_mode: CURRENT_AT_INSTANT =============================================================================================================

class ModeTests(unittest.TestCase):
    T_EARLY = a2.utc_dt(2025, 2, 6, 23, 0)
    T_LATE = a2.utc_dt(2025, 2, 11, 23, 0)

    def assert_mode(self, manifest, current):
        if current:
            self.assertEqual((manifest.valuation_mode, manifest.as_of_rule), ("CURRENT_AT_INSTANT", "D_c(t)"))
            self.assertIsNotNone(manifest.instant)
            self.assertIsNotNone(manifest.parent_release_id)
        else:
            self.assertEqual((manifest.valuation_mode, manifest.as_of_rule, manifest.instant, manifest.parent_release_id), ("HISTORICAL_AS_OF", "CALLER", None, None))

    def test_the_invariant_table_and_every_other_combination_is_an_engine_fault(self):
        view = a2.Cp4_2Tests.market_at(None).view(self.T_EARLY)
        t = self.T_EARLY
        check = engine._checked_mode
        H, C, LIVE = ValuationMode.HISTORICAL_AS_OF, ValuationMode.CURRENT_AT_INSTANT, ValuationMode.CURRENT_LIVE
        self.assertIs(check(H, "CALLER", None, None), H)
        self.assertIs(check(C, "D_c(t)", t, view), C)
        self.assertIs(check(H, "D_c(t)", t, view), C)  # the gains and attribution entries share one builder and name no mode: the Current fields make it Current
        self.assertIs(check(LIVE, "CALLER", None, None), LIVE)
        for bad in ((C, "CALLER", None, None), (C, "D_c(t)", None, view), (C, "D_c(t)", t, None), (H, "D_c(t)", None, None), (H, "CALLER", t, None), (H, "CALLER", None, view),
                    (H, "D_c(t)", t, None), (LIVE, "D_c(t)", t, view)):
            with self.assertRaises(engine.ManifestInvariantError, msg=str(bad)):
                check(*bad)
        with self.assertRaises(engine.ManifestInvariantError):  # an explicit Current request with no instant, through the engine entry
            engine.compute(mp.base_ledger().rows, 2, D(2025, 1, 31), USD, mp.market("real", real_quotes=True), mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=(),
                           mode=ValuationMode.CURRENT_AT_INSTANT)

    def test_every_current_entry_records_current_at_instant_computed_and_refused_and_every_historical_entry_records_historical(self):
        # Current entries (valuation, gains, attribution; the window metrics have no Current entry point): computed at T_EARLY, refused at T_LATE (the unclassified third.feed is in M_t then)
        for third, instant in ((False, self.T_EARLY), (True, self.T_LATE)):
            market_at = a2.Cp4_2Tests.market_at(None, third=third)
            with rc.pinned(mp.base_ledger()):
                results = (svc.compute_current_for_portfolio(None, ca.PORTFOLIO, instant, USD, mp.Ident(), market_at, mp.PERF, policy=ca.POLICY),
                           svc.compute_gains_current_for_portfolio(None, ca.PORTFOLIO, instant, USD, mp.Ident(), market_at, mp.PERF, policy=ca.POLICY, window=fr.CUSTOM),
                           svc.compute_attribution_current_for_portfolio(None, ca.PORTFOLIO, instant, fr.CUSTOM, USD, mp.Ident(), market_at, mp.PERF, policy=ca.POLICY))
            for res in results:
                self.assertEqual(svc.DETECTION_POLICY_UNMATCHED in res.metrics[0].details, third)  # computed vs refused
                self.assert_mode(res.manifest, True)
        # the four historical entries, computed and refused
        L = mp.base_ledger()
        for pol, refused in ((ca.POLICY, False), (a1.policy(filing=("typo.filing",)), True)):
            port = mp.market("real", real_quotes=True)
            args = (USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF)
            with rc.pinned(L):
                results = (svc.compute_for_portfolio(None, ca.PORTFOLIO, D(2025, 1, 31), *args, policy=pol),
                           svc.compute_window_for_portfolio(None, ca.PORTFOLIO, WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 1, 31), *args, policy=pol),
                           svc.compute_gains_for_portfolio(None, ca.PORTFOLIO, D(2025, 1, 31), *args, policy=pol, window=WindowSpec(WindowRule.SINCE_INCEPTION)),
                           svc.compute_attribution_for_portfolio(None, ca.PORTFOLIO, WindowSpec(WindowRule.SINCE_INCEPTION), D(2025, 1, 31), *args, policy=pol))
            for res in results:
                self.assertEqual(svc.DETECTION_POLICY_UNMATCHED in res.metrics[0].details, refused)
                self.assert_mode(res.manifest, False)

    def test_the_engine_coverage_gap_manifest_is_current_too_and_the_unsupported_live_request_is_not(self):
        w = pk.World(pk.example_w_readings(pk.x.lid(pk.x.identity(), "0700", "XHKG")))
        L = pk.Ledger().add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), HKD, listing_id=w.h, quantity=Decimal(100))
        gap = engine.compute_current(L.rows, L.version, a2.utc_dt(2025, 4, 5, 12, 0), USD, w.ident, w.market_at, mp.PERF, suppressions=())
        self.assert_mode(gap.manifest, True)
        live = pk.compute(L.rows, L.version, D(2025, 4, 2), USD, w.store, w.ident, w.market, mp.PERF, mode=ValuationMode.CURRENT_LIVE)
        self.assertEqual((live.manifest.valuation_mode, live.manifest.as_of_rule, live.manifest.instant), ("CURRENT_LIVE", "CALLER", None))  # still refused, still caller-dated

    def test_reproduce_treats_a_mode_difference_as_a_manifest_difference(self):
        market_at = a2.Cp4_2Tests.market_at(None)
        L = mp.base_ledger()
        res = engine.compute_current(L.rows, L.version, self.T_EARLY, USD, mp.Ident(), market_at, mp.PERF, suppressions=())
        self.assert_mode(res.manifest, True)
        ok = engine.reproduce(res.manifest, res.result_digest, L.rows, market_at.parent, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=(), market_at=market_at)
        self.assertEqual(ok.status, ReproductionStatus.REPRODUCED)
        for forged in (dataclasses.replace(res.manifest, valuation_mode="HISTORICAL_AS_OF"), dataclasses.replace(res.manifest, valuation_mode="CURRENT_LIVE")):
            report = engine.reproduce(forged, res.result_digest, L.rows, market_at.parent, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=(), market_at=market_at)
            self.assertEqual(report.status, ReproductionStatus.MANIFEST_DIFFERS, forged.valuation_mode)
        hist = pk.compute(L.rows, L.version, D(2025, 1, 31), USD, mp.market("real", real_quotes=True), mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF)
        current_label = dataclasses.replace(hist.manifest, valuation_mode="CURRENT_AT_INSTANT")  # a historical manifest claiming the Current mode
        report = engine.reproduce(current_label, hist.result_digest, L.rows, mp.market("real", real_quotes=True), mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=())
        self.assertEqual(report.status, ReproductionStatus.MANIFEST_DIFFERS)


@unittest.skipIf(bool(pgk.skip_reason()), pgk.skip_reason())
class ModePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rc.PostgresRecheckTests.setUpClass.__func__(cls)

    portfolio = fr.Cp3_14PostgresTests.portfolio

    def test_every_entry_records_its_mode_computed_and_refused_through_postgresql(self):
        portfolio = self.portfolio(hops=False, sale=False)
        pg = a2.Cp4_2PostgresTests
        for third, instant in ((False, a2.utc_dt(2025, 2, 6, 23, 0)), (True, a2.utc_dt(2025, 2, 11, 23, 0))):
            market_at = pg.market_at(self, third=third)
            results = (svc.compute_current_for_portfolio(self.app, portfolio, instant, USD, self.ident, market_at, mp.PERF, policy=ca.POLICY),
                       svc.compute_gains_current_for_portfolio(self.app, portfolio, instant, USD, self.ident, market_at, mp.PERF, policy=ca.POLICY, window=fr.CUSTOM),
                       svc.compute_attribution_current_for_portfolio(self.app, portfolio, instant, fr.CUSTOM, USD, self.ident, market_at, mp.PERF, policy=ca.POLICY))
            for res in results:
                self.assertEqual(svc.DETECTION_POLICY_UNMATCHED in res.metrics[0].details, third)
                self.assertEqual((res.manifest.valuation_mode, res.manifest.as_of_rule), ("CURRENT_AT_INSTANT", "D_c(t)"))
                self.assertTrue(res.manifest.identity_digest and res.manifest.source_registry_digest)
        for pol, refused in ((ca.POLICY, False), (a1.policy(filing=("typo.filing",)), True)):
            port = mp.market(None, real_quotes=True, listing=self.aapl, mic="XNAS", extra=a1.feed_and_filing(self.aapl))
            args = (USD, port, self.ident, self.conventions, mp.PERF)
            results = (svc.compute_for_portfolio(self.app, portfolio, a1.EX, *args, policy=pol),
                       svc.compute_window_for_portfolio(self.app, portfolio, fr.CUSTOM, a1.EX, *args, policy=pol),
                       svc.compute_gains_for_portfolio(self.app, portfolio, a1.EX, *args, policy=pol, window=fr.CUSTOM),
                       svc.compute_attribution_for_portfolio(self.app, portfolio, fr.CUSTOM, a1.EX, *args, policy=pol))
            for res in results:
                self.assertEqual(svc.DETECTION_POLICY_UNMATCHED in res.metrics[0].details, refused)
                self.assertEqual((res.manifest.valuation_mode, res.manifest.as_of_rule, res.manifest.instant, res.manifest.parent_release_id), ("HISTORICAL_AS_OF", "CALLER", None, None))
                self.assertTrue(res.manifest.identity_digest and res.manifest.source_registry_digest)


# ===== CP4-8: the PostgreSQL read path requires and checks the registry ================================================================================

@unittest.skipIf(bool(pgk.skip_reason()), pgk.skip_reason())
class Cp4_8PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_performance_cp3a as cp3a  # noqa: PLC0415

        cls.cp3a = cp3a
        cp3a.PostgresValuationTests.setUpClass.__func__(cls)

    def read(self, registry=None, **kw):
        return mds.read_release(self.app, self.world.release.release_id, exchange_of=self.world.ident.exchange_mic, **({} if registry is None else {"registry": registry}), **kw)

    def good(self):
        return SourceRegistry(self.world.store.source_registry_records())

    def test_omitting_the_registry_fails_closed(self):
        with self.assertRaises(TypeError):
            self.read()  # `registry` is a required keyword

    def test_a_source_the_registry_lacks_fails_closed(self):
        records = list(self.world.store.source_registry_records())
        with self.assertRaises(LookupError):
            self.read(SourceRegistry(records[1:]))

    def test_a_withdrawn_attestation_fails_closed_through_require_attested(self):
        records = [dataclasses.replace(r, synthetic=False, terms_check=None) if i == 0 else r for i, r in enumerate(self.world.store.source_registry_records())]
        with self.assertRaises(PermissionError):  # SourceTermsNotAttestedError (market-data Ruling 4.7)
            self.read(SourceRegistry(records))

    def test_a_registry_that_disagrees_with_the_stored_rows_is_refused_not_pinned(self):
        served = self.world.store._readings_in[0].source_id  # a source whose stored rows are read
        for change in (lambda r: dataclasses.replace(r, independence_group=r.independence_group + "-changed"), lambda r: dataclasses.replace(r, upstream_provider=r.upstream_provider + " (changed)")):
            records = [change(r) if r.source_id == served else r for r in self.world.store.source_registry_records()]
            with self.assertRaises(mds.RegistryDisagreesWithStoredRowsError):
                self.read(SourceRegistry(records))

    def test_the_consistent_registry_reads_and_pins_the_same_digest_as_the_in_memory_build(self):
        port = self.read(self.good())
        self.assertEqual(engine.registry_digest_of(port), engine.registry_digest_of(self.world.store))
        self.assertRegex(engine.registry_digest_of(port), r"^[0-9a-f]{64}$")


# ===== CP4-9: D_c(t) considers every money field of a live event dated D ===============================================================================

class Cp4_9Tests(unittest.TestCase):
    T12 = a2.utc_dt(2026, 10, 2, 12, 0)

    def setUp(self):
        days = a2.weekdays(D(2026, 9, 28), D(2026, 10, 9))
        self.ident = pk.x.identity()
        self.h, self.aapl = pk.x.lid(self.ident, "0700", "XHKG"), pk.x.lid(self.ident, "AAPL", "XNAS")
        self.calendars = CalendarSet([k.exchange_calendar("HKEX_SESSIONS", ("XHKG",), days, tz="Asia/Hong_Kong", default_close=datetime.time(16, 10)),
                                      k.exchange_calendar("NYSE_SESSIONS", ("XNYS", "XNAS"), days, tz="America/New_York"), k.ecb_calendar(days)])

    def choose(self, ledger, reporting=USD, t=None):
        return current.choose_current_date(t or self.T12, ledger.rows, ledger.version, self.calendars, self.ident.exchange_mic, reporting, self.ident.trading_currency)

    def conversion_ledger(self, sold=USD, bought=HKD, sold_amount="10", bought_amount="78"):
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2026, 9, 30), USD, amount=Money(Decimal(1000), USD))
        L.add(pk.A1, EventType.INTEREST_CHARGED, D(2026, 9, 30), HKD, amount=Money(Decimal(78), HKD))  # HKD ends 09-30 at -78
        L.add(pk.A1, EventType.CURRENCY_CONVERSION, D(2026, 10, 2), sold, amount=Money(Decimal(sold_amount), sold), bought_amount=Money(Decimal(bought_amount), bought))
        return L

    def test_the_reviewers_usd_to_hkd_conversion_closing_a_negative_hkd_balance_waits_for_the_fixing(self):
        L = self.conversion_ledger()  # sells 10 USD (the event's `amount`), buys 78 HKD (`bought_amount`): HKD ends the day at 0, nothing foreign is held
        self.assertEqual(self.choose(L).date, D(2026, 10, 1))  # was 2026-10-02: the conversion translated at the 10-01 fixing, STALE
        self.assertEqual(self.choose(L, t=a2.utc_dt(2026, 10, 2, 14, 30)).date, D(2026, 10, 2))  # after the 14:00 UTC publication
        control = self.conversion_ledger(sold=HKD, bought=USD, sold_amount="78", bought_amount="10")  # HKD as the SOLD side: already 10-01 before the fix
        self.assertEqual(self.choose(control).date, D(2026, 10, 1))

    def test_a_foreign_cost_basis_on_a_transfer_in_dated_d_counts(self):
        # R = HKD; an XHKG listing (HKD) arrives with a USD cost basis (a basis is in the EVENT's currency, so the event is in USD): XHKG closed at 08:10 UTC, so only the lot's basis
        # (the USD fixing of the acquisition date, Ruling 3.7) can hold the date back
        in_basis = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2026, 9, 30), HKD, amount=Money(Decimal(1000), HKD)).add(
            pk.A1, EventType.TRANSFER_IN, D(2026, 10, 2), USD, listing_id=self.h, quantity=Decimal(10), cost_basis=Money(Decimal(100), USD))
        self.assertEqual(self.choose(in_basis, reporting=HKD).date, D(2026, 10, 1))
        own_currency = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2026, 9, 30), HKD, amount=Money(Decimal(1000), HKD)).add(
            pk.A1, EventType.TRANSFER_IN, D(2026, 10, 2), HKD, listing_id=self.h, quantity=Decimal(10), cost_basis=Money(Decimal(780), HKD))
        self.assertEqual(self.choose(own_currency, reporting=HKD).date, D(2026, 10, 2))  # control: a basis in R and a listing in R need no fixing

    def test_every_money_field_of_a_ledger_event_is_considered(self):
        # a currency-bearing field added to LedgerEvent later must be seen by the date test: the fields that hold Money today are exactly the three handled
        money_fields = sorted(f.name for f in dataclasses.fields(LedgerEvent) if "Money" in str(f.type))
        self.assertEqual(money_fields, ["amount", "bought_amount", "cost_basis"])

    def test_the_conversion_is_not_translated_at_a_stale_fixing_at_the_chosen_date(self):
        L = self.conversion_ledger()
        fixings = {D(2026, 9, 29): {"USD": "1.1000", "HKD": "8.5800"}, D(2026, 9, 30): {"USD": "1.1000", "HKD": "8.5800"}, D(2026, 10, 1): {"USD": "1.1000", "HKD": "8.5810"}}  # HKD/USD 7.8 (inside the band)
        readings = [pk.fixing(day, ccy, rate) for day, rates in fixings.items() for ccy, rate in rates.items()]
        market_at = a2.RecordedMarketAt(readings, self.calendars, market11_conventions(self.calendars), self.ident.exchange_mic)
        res = engine.compute_current(L.rows, L.version, self.T12, USD, self.ident, market_at, mp.PERF, suppressions=())
        self.assertEqual(res.manifest.as_of, D(2026, 10, 1))  # the 10-02 conversion is not in the state, so no 10-02 event is translated at the 10-01 fixing
        for m in res.metrics:
            if m.metric_id in ("portfolio_value", "cash_value") and m.view == "REPORTING":
                self.assertEqual(m.freshness.summary if m.freshness is not None else "CURRENT", "CURRENT", (m.metric_id, m.subject))
        # the contrast the date test removes: a window ENDING on 10-02 does translate the 10-02 conversion, at the 10-01 fixing, and says STALE
        window = engine.compute_window(L.rows, L.version, WindowSpec(WindowRule.SINCE_INCEPTION), D(2026, 10, 2), USD, market_at.view(a2.utc_dt(2026, 10, 2, 12, 0)).port, self.ident,
                                       market_at.view(a2.utc_dt(2026, 10, 2, 12, 0)).conventions, mp.PERF, suppressions=())
        states = {m.result.reason_code.value if m.result.reason_code else None for m in window.metrics}
        self.assertTrue(states & {"STALE_DATA", "MISSING_FX_HISTORY"} or any(m.freshness is not None and m.freshness.summary == "STALE" for m in window.metrics), states)


# ===== market11.UNBUILT =================================================================================================================================

class UnbuiltTests(unittest.TestCase):
    def test_the_current_mode_item_stays_removed_because_items_2_to_5_are_built_and_tested(self):
        self.assertFalse([i for i in UNBUILT if "Current mode" in i])
        self.assertEqual(len(UNBUILT), 4)


if __name__ == "__main__":
    unittest.main()
