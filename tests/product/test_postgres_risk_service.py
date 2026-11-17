"""CP4d: the risk service (`risk_service.service`, `risk_service.groups`) against PostgreSQL as `finweb_app` (tech plan 17.21; UAT-03).

Opt-in, like every database test here (see `test_postgres_cp4_golden`). One disposable schema holds part 2 of the golden fixture (the ledger, the selection log and the release); each test appends what it needs to
ITS OWN portfolio (a copy of a fixture portfolio would share nothing), so tests run in any order.
"""

from __future__ import annotations

import dataclasses
import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import cp4_golden_kit as g  # noqa: E402
import pg_market_kit as pk  # noqa: E402
from test_postgres_cp4_golden import PgWorld  # noqa: E402
from domain.benchmark_selection import BenchmarkSelection, Origin, RecordType, SelectionVersionNotPinnableError  # noqa: E402
from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from performance.periods import WindowSpec, WindowRule  # noqa: E402
from persistence import benchmark_selection_store as sel_store  # noqa: E402
from persistence import ledger_replay_store, ledger_store  # noqa: E402
from risk_service import groups as grp  # noqa: E402
from risk_service import service as rsvc  # noqa: E402

D = datetime.date
_SKIP = pk.skip_reason()
USD = CurrencyCode("USD")


@unittest.skipIf(bool(_SKIP), _SKIP)
class RiskServiceTests(PgWorld, unittest.TestCase):
    PART = 2

    def setUp(self):
        r = self.runner
        (self.p,) = [p for p in r.data["portfolios"] if p["name"].startswith("Q1 ")]
        self.pid = r.portfolio_ids[self.p["name"]]
        self.spec = WindowSpec(WindowRule.TRAILING_MONTHS, 12)
        self.now = {"release_id": self.runner.market.store.release_id(), "as_of": D(2026, 1, 2)}  # the release and the as-of every view of these tests is for (`run_group` computes over them)

    def compute(self, metrics, ledger_version=None, selection_version=None, **kw):
        r = self.runner
        args = dict(policy=g.POLICY, risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=r.catalog, ledger_version=ledger_version, selection_version=selection_version, metrics=metrics,
                    allow_synthetic=True)
        args.update(kw)
        return rsvc.compute_risk_for_portfolio(self.app, self.pid, self.spec, D(2026, 1, 2), g.Frequency.WEEKLY, r.market.store, r.market.ident, r.market.conventions, r.perf, **args)

    def new_portfolio(self):
        """A portfolio of this schema with its own ledger (the fixture's Q1 events) and no selection: appended fresh, so a test can move its pins."""
        r = self.runner
        pid = uuid.uuid4()
        self.owner.execute("INSERT INTO portfolio VALUES (%s, %s, %s)", (pid, uuid.UUID("a1111111-1111-1111-1111-1111111111c4"), "USD"))
        account = uuid.uuid4()
        self.owner.execute("INSERT INTO account VALUES (%s, %s, %s)", (account, pid, "A1"))
        events = []
        for _seq, _label, _group, event in __import__("test_cp1_reconstruction").build_events(self.p, r.ids):
            events.append(dataclasses.replace(event, event_id=uuid.uuid4(), account_id=account))
        ledger_store.append_batch(self.app, events)
        return pid, account

    def run_group(self, pid, metrics, ledger_version, selection_version):
        r = self.runner
        return rsvc.compute_risk_for_portfolio(self.app, pid, self.spec, D(2026, 1, 2), g.Frequency.WEEKLY, r.market.store, r.market.ident, r.market.conventions, r.perf, policy=g.POLICY,
                                               risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=r.catalog, ledger_version=ledger_version, selection_version=selection_version,
                                               metrics=metrics, allow_synthetic=True)

    def select(self, pid, benchmark_id, on=D(2026, 3, 1)):
        return sel_store.append_selection(self.app, BenchmarkSelection(uuid.uuid4(), pid, RecordType.SELECT, on, benchmark_id=benchmark_id, origin=Origin.USER_CHOSEN)).selection_seq

    # -- the pins and the reporting currency ----------------------------------------------------------------------------------------------

    def test_currency_of_is_the_portfolios_own_row_and_an_unknown_portfolio_is_refused(self):
        self.assertEqual(rsvc.currency_of(self.app, self.pid), USD)
        with self.assertRaises(ledger_replay_store.PortfolioNotFoundError):
            rsvc.currency_of(self.app, uuid.uuid4())

    def test_the_ledger_and_selection_pins_refuse_a_version_that_is_not_committed(self):
        current = ledger_replay_store.current_ledger_version(self.app, self.pid)
        with self.assertRaises(ledger_replay_store.LedgerVersionNotCommittedError):
            rsvc.pin_ledger(self.app, self.pid, current + 1000)
        version = sel_store.current_selection_version(self.app, self.pid)
        with self.assertRaises(sel_store.SelectionVersionNotCommittedError):
            rsvc.pin_selection(self.app, self.pid, version + 1000)
        for bad in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                rsvc.pin_selection(self.app, self.pid, bad)
        self.assertEqual(rsvc.pin_selection(self.app, self.pid)[0], version)  # the default is the current committed version
        self.assertEqual(rsvc.pin_ledger(self.app, self.pid)[0], current)

    # -- the gates a product has and an engine does not ----------------------------------------------------------------------------------

    def test_a_user_portfolio_is_never_computed_from_a_synthetic_market_data_version(self):
        refused = self.compute(("risk_volatility",), allow_synthetic=False)
        self.assertIsInstance(refused, rsvc.RiskRefusal)
        self.assertEqual((refused.code, refused.state), (rsvc.SYNTHETIC_MARKET_DATA_REFUSED, "INSUFFICIENT_DATA"))  # no number, no manifest
        allowed = self.compute(("risk_volatility",))
        self.assertTrue(allowed.manifest.synthetic)  # the labelled opt-in leaves the label on the result

    def test_the_service_gives_the_engines_answer_for_the_pinned_inputs(self):
        # the same question asked of the engine directly over the same pinned rows: the digests agree (the service adds pins and gates, never a number)
        from risk.engine import compute_risk  # noqa: PLC0415

        r = self.runner
        version, events = rsvc.pin_ledger(self.app, self.pid)
        sel_version, rows = rsvc.pin_selection(self.app, self.pid)
        direct = compute_risk(events, version, self.spec, D(2026, 1, 2), g.Frequency.WEEKLY, USD, r.market.store, r.market.ident, r.market.conventions, r.perf,
                              suppressions=r.suppressions_for(self.p, version), risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=r.catalog, selections=rows, selection_version=sel_version,
                              portfolio_id=self.pid, metrics=("risk_beta", "risk_volatility"), detection="F8B_DRY_RUN", detection_policy=__import__("performance_service.service", fromlist=["x"]).policy_reference(g.POLICY))
        served = self.compute(("risk_beta", "risk_volatility"))
        self.assertEqual(served.result_digest, direct.result_digest)

    def test_a_selection_version_that_cuts_a_correction_pair_is_refused_through_the_service(self):
        pid, _account = self.new_portfolio()
        first = sel_store.append_selection(self.app, BenchmarkSelection(uuid.uuid4(), pid, RecordType.SELECT, D(2026, 1, 5), benchmark_id="SYN4_BM_US_TR", origin=Origin.USER_CHOSEN))
        rev = BenchmarkSelection(uuid.uuid4(), pid, RecordType.REVERSAL, D(2026, 1, 6), reverses_selection_id=first.selection.selection_id)
        rep = BenchmarkSelection(uuid.uuid4(), pid, RecordType.SELECT, D(2026, 1, 6), benchmark_id="SYN4_BM_US_TR_LATE", origin=Origin.USER_CHOSEN, corrects_selection_id=first.selection.selection_id)
        pair = sel_store.append_correction(self.app, rev, rep)
        with self.assertRaises(SelectionVersionNotPinnableError):
            self.run_group(pid, ("benchmark_return",), None, pair.reversal.selection_seq)  # the reversal without its replacement: no committed state had that content
        ok = self.run_group(pid, ("benchmark_return",), None, pair.replacement.selection_seq)
        self.assertEqual(ok.metric("benchmark_return").benchmark.benchmark_id, "SYN4_BM_US_TR_LATE")

    # -- UAT-03 --------------------------------------------------------------------------------------------------------------------------------

    def compute_for(self, pid):
        def compute(metrics, ledger, selection):
            return self.run_group(pid, metrics, ledger, selection)

        return compute

    def test_uat_03_changing_the_benchmark_recomputes_only_the_benchmark_group(self):
        pid, _account = self.new_portfolio()
        compute = self.compute_for(pid)
        self.select(pid, "SYN4_BM_US_TR")
        v0 = grp.compute_view(self.app, pid, compute, **self.now)
        self.assertEqual(grp.status(self.app, pid, v0, **self.now), grp.CURRENT)
        self.assertEqual(v0.benchmark.metric("risk_beta").benchmark.benchmark_id, "SYN4_BM_US_TR")
        # the groups partition the metrics: nothing is in both, and the benchmark group is the engine's own set
        self.assertEqual(set(grp.BENCHMARK_GROUP) & set(grp.INDEPENDENT_GROUP), set())
        self.assertTrue({"risk_volatility", "risk_max_drawdown"} <= set(grp.INDEPENDENT_GROUP) and {"risk_beta", "benchmark_return", "risk_active_return"} <= set(grp.BENCHMARK_GROUP))
        # the user changes the benchmark
        self.select(pid, "SYN4_BM_US_TR_LATE")
        self.assertEqual(grp.status(self.app, pid, v0, **self.now), grp.STALE_SELECTION)  # the old view is NOT current any more
        v1 = grp.refresh(self.app, pid, v0, compute, **self.now)
        self.assertIs(v1.independent, v0.independent)  # not recomputed: the same object
        self.assertEqual(grp.digests(v1)[0], grp.digests(v0)[0])
        self.assertNotEqual(grp.digests(v1)[1], grp.digests(v0)[1])  # the benchmark group moved
        self.assertEqual(v1.benchmark.metric("risk_beta").benchmark.benchmark_id, "SYN4_BM_US_TR_LATE")
        self.assertEqual(grp.status(self.app, pid, v1, **self.now), grp.CURRENT)
        # and recomputing the independent group from scratch at the new selection gives the very same digest: the selection is not one of its inputs
        again = self.run_group(pid, grp.INDEPENDENT_GROUP, v1.ledger_version, v1.selection_version)
        self.assertEqual(again.result_digest, v0.independent.result_digest)
        self.assertEqual(again.manifest.manifest_id, v0.independent.manifest.manifest_id)
        self.assertIsNone(again.manifest.benchmark)  # it names no benchmark at all
        # a refresh with nothing moved is the previous view
        self.assertIs(grp.refresh(self.app, pid, v1, compute, **self.now), v1)
        # the refreshed view is what a fresh computation gives (determinism)
        fresh = grp.compute_view(self.app, pid, compute, **self.now)
        self.assertEqual(grp.digests(fresh), grp.digests(v1))

    def test_uat_03_clearing_the_benchmark_suppresses_only_the_benchmark_group(self):
        pid, _account = self.new_portfolio()
        compute = self.compute_for(pid)
        self.select(pid, "SYN4_BM_US_TR")
        v0 = grp.compute_view(self.app, pid, compute, **self.now)
        sel_store.append_selection(self.app, BenchmarkSelection(uuid.uuid4(), pid, RecordType.CLEAR, D(2026, 3, 2)))
        v1 = grp.refresh(self.app, pid, v0, compute, **self.now)
        self.assertIs(v1.independent, v0.independent)
        states = {(m.state.value, m.result.reason_code.value if m.result.reason_code else None) for m in v1.benchmark.metrics}
        self.assertEqual(states, {("INSUFFICIENT_DATA", "MISSING_BENCHMARK")})  # no benchmark is ever substituted
        self.assertEqual(v1.independent.metric("risk_volatility").state, v0.independent.metric("risk_volatility").state)

    def test_uat_03_a_ledger_that_moved_recomputes_both_groups_and_no_old_view_stays_current(self):
        pid, account = self.new_portfolio()
        compute = self.compute_for(pid)
        self.select(pid, "SYN4_BM_US_TR")
        v0 = grp.compute_view(self.app, pid, compute, **self.now)
        ledger_store.append_event(self.app, LedgerEvent(event_id=uuid.uuid4(), account_id=account, event_type=EventType.DEPOSIT, event_date=D(2026, 2, 2), currency=USD, amount=Money(Decimal("1"), USD)))
        self.assertEqual(grp.status(self.app, pid, v0, **self.now), grp.STALE_LEDGER)
        self.select(pid, "SYN4_BM_US_TR_LATE")
        self.assertEqual(grp.status(self.app, pid, v0, **self.now), grp.STALE_BOTH)
        v1 = grp.refresh(self.app, pid, v0, compute, **self.now)
        self.assertIsNot(v1.independent, v0.independent)  # the ledger is an input of the independent group too
        self.assertNotEqual(v1.independent.manifest.manifest_id, v0.independent.manifest.manifest_id)
        self.assertEqual(v1.ledger_version, v0.ledger_version + 1)
        self.assertEqual(grp.status(self.app, pid, v1, **self.now), grp.CURRENT)

    def test_a_held_view_is_not_current_after_the_release_the_as_of_or_the_reporting_currency_moved(self):
        """CP4F-7: all five pins (ledger, selection, release, as-of, reporting currency) are inputs of every metric, so a view is CURRENT only if none has moved."""
        pid, _account = self.new_portfolio()
        compute = self.compute_for(pid)
        self.select(pid, "SYN4_BM_US_TR")
        v0 = grp.compute_view(self.app, pid, compute, **self.now)
        self.assertEqual((v0.release_id, v0.as_of, v0.reporting_currency), (self.now["release_id"], D(2026, 1, 2), "USD"))
        self.assertEqual(grp.status(self.app, pid, v0, **self.now), grp.CURRENT)
        other = dict(self.now, release_id="another-release")
        self.assertEqual(grp.status(self.app, pid, v0, **other), grp.STALE_RELEASE)  # the market data was rebuilt
        self.assertEqual(grp.status(self.app, pid, v0, release_id=self.now["release_id"], as_of=D(2026, 1, 9)), grp.STALE_AS_OF)  # the user moved the as-of date
        self.assertEqual(grp.status(self.app, pid, v0, release_id="another-release", as_of=D(2026, 1, 9)), grp.STALE_MULTIPLE)
        with self.assertRaises(ValueError):  # a recomputation that is not over the release the caller says is refused, never labelled current
            grp.refresh(self.app, pid, v0, compute, **other)
        with self.assertRaises(ValueError):
            grp.refresh(self.app, pid, v0, compute, release_id=self.now["release_id"], as_of=D(2026, 1, 9))
        self.owner.execute("UPDATE portfolio SET reporting_currency = %s WHERE portfolio_id = %s", ("HKD", pid))  # no immutability guard on the row: a future "report in HKD" setting
        self.assertEqual(grp.status(self.app, pid, v0, **self.now), grp.STALE_CURRENCY)
        v1 = grp.refresh(self.app, pid, v0, compute, **self.now)
        self.assertIsNot(v1.independent, v0.independent)  # the currency is an input of BOTH groups
        self.assertIsNot(v1.benchmark, v0.benchmark)
        self.assertEqual(v1.reporting_currency, "HKD")
        self.assertEqual(v1.independent.manifest.series.reporting_currency, "HKD")
        self.assertEqual(grp.status(self.app, pid, v1, **self.now), grp.CURRENT)

    def test_a_result_computed_at_an_old_pin_is_reproducible_after_the_selection_moved(self):
        # the pin is data: asking again at the OLD selection version gives the OLD answer, however the log has grown since (P9, UAT-03's other half)
        pid, _account = self.new_portfolio()
        v = self.select(pid, "SYN4_BM_US_TR")
        first = self.run_group(pid, ("risk_beta",), None, v)
        self.select(pid, "SYN4_BM_US_TR_LATE")
        again = self.run_group(pid, ("risk_beta",), None, v)
        self.assertEqual(again.result_digest, first.result_digest)
        self.assertEqual(again.manifest.benchmark.pin["version"], v)


if __name__ == "__main__":
    unittest.main()
