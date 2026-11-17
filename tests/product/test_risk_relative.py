"""CP4d increment 1: the benchmark-relative metrics and the comparability disclosure (`risk/1.4` Rulings 6.7 to 6.11, 6.13, 8; tech plan 17.20).

The golden fixture (`test_cp4_golden`) is the proof of the VALUES; this module is the proof of the properties the fixture does not state by itself: the exact relations between the recorded intermediates and the
values (Ruling 9.4), the identities as runtime checks that bite, the states of the degenerate cases, the disclosure's definition (a disclosure, never a state), and the metamorphic checks of Ruling 6.13.
"""

from __future__ import annotations

import dataclasses
import datetime
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import cp4_golden_kit as g  # noqa: E402
from performance.states import Valued  # noqa: E402
from product_contract.vocabulary import SufficiencyState as SS  # noqa: E402
from risk import comparability as comp  # noqa: E402
from risk import states as S  # noqa: E402
from risk.results import Comparability, LagPoint, Seam  # noqa: E402

D = datetime.date
A_WEEKLY = 52


def portfolio(part, prefix):
    r = g.shared_runner(part)
    (p,) = [p for p in r.data["portfolios"] if p["name"].startswith(prefix)]
    return r, p


def metric(part, prefix, aid, kind, **match):
    r, p = portfolio(part, prefix)
    a = next(a for a in p["assertions"] if a["id"] == aid)
    item = next(i for i in a["expect"] if i["kind"] == kind and all(i["request"].get(k) == v for k, v in match.items()))
    return r.risk(p, a, item, tuple(g.KIND_METRIC.values())).metric(g.KIND_METRIC[kind]), r, p, a, item


def inter(m):
    return dict(m.intermediates)


class IntermediateTests(unittest.TestCase):
    """Ruling 9.4 (1.4): each value is recomputable from the exact intermediates in its own record, with no re-run."""

    def setUp(self):
        self.beta, *_ = metric(2, "Q1 ", "Q1-B1", "beta", months=12)
        self.r2, *_ = metric(2, "Q1 ", "Q1-B1", "r_squared", months=12)
        self.alpha, *_ = metric(2, "Q1 ", "Q1-B1", "alpha_jensen", months=12)
        self.te, *_ = metric(2, "Q1 ", "Q1-B1", "tracking_error", months=12)
        self.ir, *_ = metric(2, "Q1 ", "Q1-B1", "information_ratio", months=12)

    def test_beta_and_r_squared_are_the_market_model_of_their_own_sums(self):
        b, r2 = inter(self.beta), inter(self.r2)
        self.assertEqual(self.beta.exact, b["sum_cross_deviations"] / b["sum_squared_deviations_benchmark"])
        self.assertEqual(self.r2.exact, r2["sum_cross_deviations"] ** 2 / (r2["sum_squared_deviations_benchmark"] * r2["sum_squared_deviations_return"]))
        self.assertEqual({k: b[k] for k in r2}, r2)  # one set of sums for both (the same window, the same returns)
        self.assertEqual(b["n"], 52)
        # v_beta = (S_rr - beta S_rb) / ((n - 2) S_bb), exactly; RB-1: beta^2 S_bb = R^2 S_rr
        self.assertEqual(b["v_beta"], (b["sum_squared_deviations_return"] - self.beta.exact * b["sum_cross_deviations"]) / ((52 - 2) * b["sum_squared_deviations_benchmark"]))
        self.assertEqual(self.beta.exact ** 2 * b["sum_squared_deviations_benchmark"], self.r2.exact * b["sum_squared_deviations_return"])

    def test_alpha_is_a_times_the_mean_excess_less_beta_times_the_benchmarks_and_is_shown_with_the_risk_free_mean(self):
        a = inter(self.alpha)
        self.assertEqual(self.alpha.exact, A_WEEKLY * (a["mean_excess"] - a["beta"] * a["mean_benchmark_excess"]))
        self.assertEqual(a["beta"], self.beta.exact)  # one beta everywhere (Ruling 6.7)
        self.assertEqual(a["mean_excess"] - a["mean_benchmark_excess"], inter(self.beta)["mean_return"] - inter(self.beta)["mean_benchmark_return"])  # rf-bar cancels in the difference of the means
        self.assertGreater(a["mean_risk_free"], 0)  # the rf-bar Ruling 6.8 requires alpha to be shown with

    def test_tracking_error_and_the_information_ratio_are_of_their_own_active_returns(self):
        t, i = inter(self.te), inter(self.ir)
        self.assertEqual(self.te.exact_square, A_WEEKLY * t["variance"])
        self.assertEqual(t["variance"], t["sum_squared_deviations"] / (t["n"] - 1))  # n - 1 (M-B5)
        self.assertEqual(self.ir.exact_square * i["variance"], A_WEEKLY * i["mean_active"] ** 2)  # RQ-1 on the information ratio
        self.assertEqual(self.ir.sign, 1 if i["mean_active"] > 0 else -1)
        self.assertNotEqual(self.ir.exact_square, A_WEEKLY * i["mean_active"] ** 2 / (t["sum_squared_deviations"] / t["n"]))  # not the population variance

    def test_the_active_return_is_the_difference_of_the_two_exact_legs_and_the_view_reconciles(self):
        m, r, p, a, item = metric(2, "Q1 ", "Q1-B1", "active_return", rule="CUSTOM")
        i = inter(m)
        self.assertEqual(m.exact, i["portfolio_twr"] - i["benchmark_return"])  # RA-1, arithmetic (M-B4)
        view = dict(m.decomposition)
        self.assertEqual(view["portfolio_twr"] - view["benchmark_return"], view["active_return"])  # the displayed difference is the difference of the displayed legs
        self.assertLessEqual(abs(view["active_return"] - m.value), Decimal("0.000000000001"))  # within one quantum of its own value
        bench, *_ = metric(2, "Q1 ", "Q1-B1", "benchmark_return", rule="CUSTOM")
        self.assertEqual(i["benchmark_return"], bench.exact)


class DegenerateTests(unittest.TestCase):
    """Ruling 6.12 and 6.7: the undefined cases are INSUFFICIENT_DATA with a detail and no code, and a zero is a value, never one of them."""

    def test_a_flat_benchmark_has_no_slope_and_no_r_squared_and_no_alpha_but_a_tracking_error(self):
        for kind in ("beta", "r_squared", "alpha_jensen"):
            m, *_ = metric(3, "R1 ", "R1-F1", kind)
            self.assertEqual((m.state, m.result.reason_code, m.value, S.ZERO_BENCHMARK_VARIANCE in m.details), (SS.INSUFFICIENT_DATA, None, None, True), kind)  # M-C14: never shown as 0
            self.assertIsNone(m.comparability)  # an INSUFFICIENT_DATA result carries no disclosure
        te, *_ = metric(3, "R1 ", "R1-F1", "tracking_error")
        self.assertEqual(te.state, SS.AVAILABLE if te.thresholds is None else te.state)
        self.assertIsNotNone(te.value)

    def test_a_portfolio_that_did_not_move_has_beta_zero_and_an_undefined_r_squared(self):
        beta, *_ = metric(2, "Q4 ", "Q4-C1", "beta", months=12)
        self.assertEqual((beta.exact, beta.value), (Fraction(0), Decimal("0E-12")))  # defined: 0
        r2, *_ = metric(2, "Q4 ", "Q4-C1", "r_squared", months=12)
        self.assertEqual((r2.state, r2.value, S.ZERO_PORTFOLIO_VARIANCE in r2.details), (SS.INSUFFICIENT_DATA, None, True))  # M-B21: not 0

    def test_the_benchmark_equal_to_the_portfolio_gives_beta_one_r_squared_one_te_zero_and_ir_undefined(self):
        beta, *_ = metric(2, "Q2 ", "Q2-T1", "beta", months=12)
        r2, *_ = metric(2, "Q2 ", "Q2-T1", "r_squared", months=12)
        te, *_ = metric(2, "Q2 ", "Q2-T1", "tracking_error", months=12)
        ir, *_ = metric(2, "Q2 ", "Q2-T1", "information_ratio", months=12)
        self.assertEqual((beta.exact, r2.exact, te.exact_square, ir.state, S.ZERO_TRACKING_ERROR in ir.details), (Fraction(1), Fraction(1), Fraction(0), SS.INSUFFICIENT_DATA, True))
        self.assertEqual(te.value, Decimal("0E-12"))  # a zero tracking error is a value


class IdentityTests(unittest.TestCase):
    """Ruling 6.13: an identity that fails at runtime is INSUFFICIENT_DATA + CALCULATION_ERROR, never a number."""

    def _fresh(self, r, p, a, item):
        from risk.engine import compute_risk  # noqa: PLC0415

        return compute_risk(r.events[p["name"]], r.version(p, a), g.spec_of(item["request"]), g.D(a["as_of"]), g.Frequency(item["frequency"]), g.CurrencyCode(p["reporting_currency"]), r.market.store, r.market.ident,
                            r.market.conventions, r.perf, suppressions=r.suppressions_for(p, r.version(p, a)), risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=r.catalog,
                            selections=g.selections_of(p, r.ids), selection_version=a.get("selection_log_version", 0), portfolio_id=r.ids(p["portfolio_id"]), metrics=("risk_active_return",)).metric("risk_active_return")

    def test_ra1_bites_when_the_engines_window_return_differs_from_the_series(self):
        import risk.engine as E  # noqa: PLC0415

        real = E.compute_twr_between

        def lying(*args, **kw):
            v = real(*args, **kw)
            return dataclasses.replace(v, exact=v.exact + Fraction(1, 10 ** 9))

        r, p = portfolio(2, "Q1 ")
        a = next(a for a in p["assertions"] if a["id"] == "Q1-B1")
        item = next(i for i in a["expect"] if i["kind"] == "active_return")
        with mock.patch("risk.engine.compute_twr_between", lying):
            m = self._fresh(r, p, a, item)
        self.assertEqual((m.state, m.result.reason_code.value, m.value, S.IDENTITY_FAILED in m.details), (SS.INSUFFICIENT_DATA, "CALCULATION_ERROR", None, True))
        self.assertIn(("identity:RS-1", "FAIL"), m.lineage)  # the failure is recorded (RS-1: the series' chained window return against the TWR engine's; CP4F: it was labelled RA-1)

    def test_the_identities_that_pass_are_recorded_in_the_lineage(self):
        m, *_ = metric(2, "Q1 ", "Q1-B1", "active_return", rule="CUSTOM")
        self.assertIn(("identity:RS-1", "PASS"), m.lineage)
        self.assertIn(("identity:RS-2", "PASS"), m.lineage)


class ComparabilityTests(unittest.TestCase):
    """Ruling 8: a DISCLOSURE, never a state; the seam fields are two sorted lists of calendar ids."""

    def test_a_us_portfolio_against_a_us_index_is_full(self):
        m, *_ = metric(2, "Q1 ", "Q1-B1", "beta", months=12)
        self.assertEqual(m.comparability.to_obj(), {"class": "FULL", "seam": None, "lagged": {"count": 0, "of": 53, "points": []}})
        self.assertEqual(m.state, SS.LIMITED)  # the state is the count's (n = 52), not the disclosure's

    def test_the_hong_kong_holding_against_a_new_york_index_has_a_seam_of_770_minutes_and_a_value_that_is_still_shown(self):
        m, *_ = metric(2, "Q2 ", "Q2-T2", "beta", months=12)
        seam = m.comparability.seam
        self.assertEqual((seam.portfolio_calendars, seam.benchmark_calendars, seam.max_offset_minutes_at_last_grid_date), (("SYN4_ECB", "SYN4_HKEX"), ("SYN4_NYSE",), 770))
        self.assertEqual((m.comparability.klass, m.state), ("LIMITED", SS.LIMITED))  # LIMITED comparability does NOT change the sufficiency state: 'LIMITED' here is the count's
        a, *_ = metric(2, "Q2 ", "Q2-T2", "active_return", rule="CUSTOM")
        self.assertEqual((a.comparability.klass, a.state), ("LIMITED", SS.AVAILABLE))  # an AVAILABLE value with a disclosure: never degraded to LIMITED by it

    def test_the_active_return_reads_two_grid_dates_and_a_statistic_all_of_them(self):
        a, *_ = metric(2, "Q1 ", "Q1-B3", "active_return", rule="CUSTOM")
        self.assertEqual(a.comparability.lagged_of, 2)
        self.assertEqual([(p.date, p.portfolio_lag, p.benchmark_lag) for p in a.comparability.points], [(D(2026, 1, 16), 0, 2)])  # the benchmark is two sessions behind, the portfolio is current
        b, *_ = metric(2, "Q1 ", "Q1-B1", "beta", months=12)
        self.assertEqual(b.comparability.lagged_of, 53)

    def test_cash_in_the_reporting_currency_has_no_market_instant_and_so_no_seam(self):
        m, *_ = metric(2, "Q4 ", "Q4-C1", "tracking_error", months=12)
        self.assertIsNone(m.comparability.seam)  # M-B13: an empty instant set is not a seam

    def test_the_object_refuses_an_inconsistent_class(self):
        with self.assertRaises(ValueError):
            Comparability("FULL", Seam(("A",), ("B",), 5), 0, 2, ())
        with self.assertRaises(ValueError):
            Comparability("LIMITED", None, 0, 2, ())
        with self.assertRaises(ValueError):
            Comparability("FULL", None, 1, 2, ())  # a count without its points
        Comparability("LIMITED", None, 1, 2, (LagPoint(D(2026, 1, 2), 0, 1),))

    def test_a_suppressed_metric_cannot_carry_a_disclosure(self):
        m, *_ = metric(2, "Q1 ", "Q1-U2", "beta", months=12)  # no benchmark selected
        self.assertEqual((m.state, m.comparability, m.decomposition), (SS.INSUFFICIENT_DATA, None, None))
        with self.assertRaises(ValueError):
            dataclasses.replace(m, comparability=Comparability("FULL", None, 0, 2, ()))

    def test_the_instant_helpers(self):
        self.assertIsNone(comp._close_instant(None, D(2026, 1, 2)))
        self.assertIsNone(comp._fixing_instant(None, D(2026, 1, 2)))


class StateTests(unittest.TestCase):
    """Ruling 7.3 for the benchmark parts: a stale benchmark degrades a two-leg metric, and a missing benchmark suppresses only the benchmark-dependent group."""

    def test_a_missing_benchmark_suppresses_the_relative_metrics_but_not_the_others(self):
        r, p = portfolio(2, "Q1 ")
        a = next(a for a in p["assertions"] if a["id"] == "Q1-U2")
        item = next(i for i in a["expect"] if i["kind"] == "volatility")
        res = r.risk(p, a, item, tuple(g.KIND_METRIC.values()))
        relative = [m for m in res.metrics if m.metric_id in g.RELATIVE_METRIC_IDS]
        self.assertEqual({(m.state, m.result.reason_code.value) for m in relative}, {(SS.INSUFFICIENT_DATA, "MISSING_BENCHMARK")})  # M-B20 would suppress every metric
        independent = {m.metric_id: m.state for m in res.metrics if m.metric_id not in g.RELATIVE_METRIC_IDS and m.metric_id != "benchmark_return"}
        self.assertTrue(any(s is not SS.INSUFFICIENT_DATA for s in independent.values()), independent)
        self.assertEqual(res.metric("risk_volatility").state, SS.LIMITED)

    def test_beta_r_squared_tracking_error_ir_and_active_return_read_no_risk_free_rate_and_alpha_does(self):
        # Ruling 6.7: total-return beta needs no rate (M-B3, M-B17 do not exist in this design); only alpha needs the risk-free catalog
        from risk.engine import compute_risk  # noqa: PLC0415

        r, p = portfolio(2, "Q1 ")
        a = next(a for a in p["assertions"] if a["id"] == "Q1-B1")
        item = next(i for i in a["expect"] if i["kind"] == "beta")

        def run(metrics):
            return compute_risk(r.events[p["name"]], r.version(p, a), g.spec_of(item["request"]), g.D(a["as_of"]), g.Frequency(item["frequency"]), g.CurrencyCode(p["reporting_currency"]), r.market.store,
                                r.market.ident, r.market.conventions, r.perf, suppressions=(), benchmark_catalog=r.catalog, selections=g.selections_of(p, r.ids), selection_version=1,
                                portfolio_id=r.ids(p["portfolio_id"]), metrics=metrics)

        for metric_id in ("risk_beta", "risk_r_squared", "risk_tracking_error", "risk_information_ratio", "risk_active_return"):
            self.assertEqual(run((metric_id,)).metric(metric_id).state, SS.LIMITED if metric_id != "risk_active_return" else SS.AVAILABLE, metric_id)
        with self.assertRaises(ValueError):
            run(("risk_alpha_jensen",))

    def test_a_benchmark_stale_by_two_sessions_limits_the_active_return_with_stale_data(self):
        m, *_ = metric(2, "Q1 ", "Q1-B3", "active_return", rule="CUSTOM")
        self.assertEqual((m.state, m.result.reason_code.value, S.BENCHMARK_STALE in m.details), (SS.LIMITED, "STALE_DATA", True))  # M-B19 would leave it AVAILABLE


if __name__ == "__main__":
    unittest.main()
