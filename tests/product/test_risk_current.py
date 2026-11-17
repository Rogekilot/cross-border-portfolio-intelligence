"""CP4d increment 2: Current mode for risk (`risk/1.4` Ruling 5.8 (1.3); `performance` Ruling 1.7 (1.12); tech plan 17.21).

The golden fixture (R7-C1, R7-C2 against R7-H1) proves the VALUES at two instants. This module proves the rest of the contract on the same world (part 3, portfolio R7: HKD reporting, one HKEX listing, the
US index translated from USD): what the manifest records, that a time not yet due is not a lag, that an instant after everything is due gives the historical answer, that a date that cannot be chosen refuses every
metric, and that a Current-mode result reproduces.
"""

from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import cp4_golden_kit as g  # noqa: E402
from product_contract.vocabulary import SufficiencyState as SS  # noqa: E402
from risk.engine import compute_risk_current, reproduce_risk  # noqa: E402
from risk.manifest import RiskReproductionStatus as St  # noqa: E402

D = datetime.date
METRICS = ("risk_beta", "risk_tracking_error", "risk_active_return", "benchmark_return")


def world():
    r = g.shared_runner(3)
    (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("R7 ")]
    return r, p


def assertion(p, aid, **over):
    return dict(next(a for a in p["assertions"] if a["id"] == aid), **over)


def item_of(a, kind):
    return next(i for i in a["expect"] if i["kind"] == kind)


class CurrentModeTests(unittest.TestCase):
    def run_at(self, instant, kind="beta"):
        r, p = world()
        a = assertion(p, "R7-C1", instant=instant, id=f"X-{instant}")
        return r, p, a, r.risk(p, a, item_of(a, kind), METRICS)

    def test_the_manifest_records_the_mode_the_instant_the_date_and_the_benchmark_day_and_fixing_used(self):
        r, p, a, res = self.run_at("2026-01-09T09:00:00Z")
        cur = res.manifest.current
        self.assertEqual((cur.valuation_mode, cur.as_of_rule, cur.as_of, res.manifest.end), ("CURRENT_AT_INSTANT", "D_c(t)", D(2026, 1, 9), D(2026, 1, 9)))
        self.assertEqual(cur.instant, g._utc("2026-01-09T09:00:00Z"))
        self.assertEqual(cur.parent_release_id, r.market.release.release_id)  # `M`, not `M_t`
        self.assertNotEqual(res.manifest.series.release_id, cur.parent_release_id)  # the series ran over `M_t`
        self.assertTrue(cur.excluded_files)  # the files retrieved after t are named
        bm = res.manifest.benchmark
        self.assertEqual((bm.level_date_gn, bm.fixing_date_gn), (D(2026, 1, 8), D(2026, 1, 8)))  # Ruling 5.8 item 6: Thursday's level and fixing, the Friday ones not being due

    def test_the_current_block_is_part_of_the_manifest_id(self):
        _r, _p, _a, res = self.run_at("2026-01-09T09:00:00Z")
        obj = res.manifest.to_obj()
        self.assertEqual(obj["current"]["as_of"], D(2026, 1, 9))
        self.assertEqual(obj["benchmark"]["level_date_gn"], D(2026, 1, 8))
        import dataclasses  # noqa: PLC0415

        other = dataclasses.replace(res.manifest, current=dataclasses.replace(res.manifest.current, instant=g._utc("2026-01-09T09:00:01Z")))
        self.assertNotEqual(other.manifest_id, res.manifest.manifest_id)  # the instant is an input: it is in the id

    def test_a_time_not_yet_due_is_not_a_lag_and_the_seam_is_measured_from_the_instants_actually_used(self):
        _r, _p, _a, res = self.run_at("2026-01-09T09:00:00Z")
        m = res.metric("risk_beta")
        self.assertEqual(m.comparability.lagged_count, 0)  # not LAGGED
        self.assertEqual(m.comparability.seam.max_offset_minutes_at_last_grid_date, 1140)  # the offset to Thursday's NYSE close and ECB fixing, not Friday's
        bench = res.metric("benchmark_return")
        self.assertEqual((bench.state, bench.result.reason_code), (SS.AVAILABLE, None))  # fresh, not stale: the 01-09 close and fixing do not exist yet

    def test_once_everything_is_due_the_current_answer_is_the_historical_one(self):
        r, p, a, res = self.run_at("2026-01-09T21:30:00Z")
        self.assertEqual(res.manifest.current.as_of, D(2026, 1, 9))
        hist = assertion(p, "R7-H1")
        h = r.risk(p, hist, item_of(hist, "beta"), METRICS)
        for metric_id in METRICS:
            self.assertEqual((res.metric(metric_id).exact, res.metric(metric_id).exact_square), (h.metric(metric_id).exact, h.metric(metric_id).exact_square), metric_id)
        self.assertEqual(res.metric("risk_beta").comparability.seam.max_offset_minutes_at_last_grid_date, 770)  # the same offset as the historical twin

    def test_current_mode_never_reads_what_did_not_exist_at_t(self):
        r, p, a, current = self.run_at("2026-01-09T09:00:00Z")
        hist = assertion(p, "R7-H1")
        h = r.risk(p, hist, item_of(hist, "beta"), METRICS)
        self.assertNotEqual(current.metric("benchmark_return").exact, h.metric("benchmark_return").exact)  # S3-3
        self.assertNotEqual(current.result_digest, h.result_digest)
        self.assertNotEqual(current.manifest.manifest_id, h.manifest.manifest_id)
        self.assertIsNone(h.manifest.current)  # a historical manifest names no Current block, and its id is unchanged by the field existing

    def test_the_end_is_the_portfolios_date_never_moved_by_the_benchmark(self):
        _r, _p, _a, early = self.run_at("2026-01-09T07:00:00Z")  # before the HKEX close: D_c(t) = 01-08
        self.assertEqual(early.manifest.current.as_of, D(2026, 1, 8))
        _r, _p, _a, later = self.run_at("2026-01-09T09:00:00Z")  # the HKEX close is past, the US close is not: E = 01-09 all the same
        self.assertEqual(later.manifest.current.as_of, D(2026, 1, 9))

    def test_a_date_that_cannot_be_chosen_refuses_every_metric_with_the_coverage_gap_and_no_reason(self):
        r, p, a, res = self.run_at("2030-01-02T00:00:00Z")  # beyond every calendar's coverage
        self.assertIsNone(res.manifest.current.as_of)
        self.assertTrue(res.manifest.current.as_of_causes)
        for m in res.metrics:
            self.assertEqual((m.state, m.result.reason_code, m.value, "CALENDAR_COVERAGE_GAP" in m.details), (SS.INSUFFICIENT_DATA, None, None, True), m.metric_id)
            self.assertIsNone(m.window, m.metric_id)  # no series at all: it is the date choice that was refused, not a price or a rate
            self.assertIn("current_date", {cause.ref for cause in m.causes}, m.metric_id)  # the cause is the date rule's own

    def test_a_current_mode_result_reproduces_and_needs_m_t_to_do_so(self):
        r, p, a, res = self.run_at("2026-01-09T09:00:00Z")
        events, version = r.events[p["name"]], r.version(p, a)
        kw = dict(suppressions=r.suppressions_for(p, version), risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=r.catalog, selections=g.selections_of(p, r.ids))
        report = reproduce_risk(res.manifest, res.result_digest, events, r.market.store, r.market.ident, r.market.conventions, r.perf, market_at=r.market.market_at, **kw)
        self.assertEqual((report.status, report.detail), (St.REPRODUCED, ""))
        with self.assertRaises(ValueError):  # no M_t: the question cannot be asked again, and it is said, not guessed
            reproduce_risk(res.manifest, res.result_digest, events, r.market.store, r.market.ident, r.market.conventions, r.perf, **kw)
        wrong = reproduce_risk(res.manifest, "0" * 64, events, r.market.store, r.market.ident, r.market.conventions, r.perf, market_at=r.market.market_at, **kw)
        self.assertEqual(wrong.status, St.RESULT_DIFFERS)

    def fx_gap_world(self, days):
        import copy  # noqa: PLC0415
        import test_cp1_reconstruction as cp1  # noqa: PLC0415

        data = copy.deepcopy(g.load_part(3))
        data["market_data"]["fx"].setdefault("gaps_by_currency", {})["USD"] = list(days)  # the benchmark (USD index) is translated into HKD at the ECB fixing: its USD quote is missing on these days
        ids = cp1.Ids(randomize=False)
        market = g.Market(data, ids)
        self.addCleanup(market.close)
        runner = g.Runner(data, market, ids)
        (p,) = [p for p in data["portfolios"] if p["name"].startswith("R7 ")]
        return runner, p, assertion(p, "R7-C1")

    def test_a_fixing_not_yet_published_is_not_missed_at_the_five_missed_boundary(self):
        """CP4F-6 (Ruling 5.8 item 5). R7-C1 is at 2026-01-09T09:00Z: the 01-09 fixing is not yet published. With the USD quotes of 01-05 to 01-08 absent, 4 fixings are missed (LIMITED + STALE_DATA, with
        the number), not 5 (INSUFFICIENT_DATA): the port withholds the rate at 5 before any not-yet-due adjustment, so the lookup is made at the latest fixing that IS due."""
        runner, p, a = self.fx_gap_world(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"])
        res = runner.risk(p, a, item_of(a, "beta"), METRICS)
        bret = res.metric("benchmark_return")
        self.assertEqual((bret.state, bret.result.reason_code.value), (SS.LIMITED, "STALE_DATA"))
        self.assertIsNotNone(bret.value)  # the number is shown, with the caveat
        self.assertEqual(res.metric("risk_beta").state, SS.LIMITED)
        self.assertNotIn("MISSING_FX_HISTORY", {m.result.reason_code.value for m in res.metrics if m.result.reason_code})

    def test_five_missed_fixings_that_are_all_due_are_still_withheld(self):
        runner, p, a = self.fx_gap_world(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"])
        res = runner.risk(p, a, item_of(a, "beta"), METRICS)
        bret = res.metric("benchmark_return")
        self.assertEqual((bret.state, bret.result.reason_code.value, bret.value), (SS.INSUFFICIENT_DATA, "MISSING_FX_HISTORY", None))

    def test_the_view_function_of_suppressions_is_called_with_the_view(self):
        r, p, a, _res = self.run_at("2026-01-09T09:00:00Z")
        seen = []

        def suppressions(view):
            seen.append(view.instant)
            return ()

        res = compute_risk_current(r.events[p["name"]], r.version(p, a), g.spec_of(item_of(a, "beta")["request"]), g._utc(a["instant"]), g.Frequency.WEEKLY, g.CurrencyCode("HKD"), r.market.market_at,
                                   r.market.ident, r.perf, suppressions=suppressions, risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=r.catalog, selections=g.selections_of(p, r.ids),
                                   selection_version=1, portfolio_id=r.ids(p["portfolio_id"]), metrics=("risk_beta",))
        self.assertEqual(seen, [g._utc("2026-01-09T09:00:00Z")])
        self.assertEqual(res.metric("risk_beta").state, SS.LIMITED)


if __name__ == "__main__":
    unittest.main()
