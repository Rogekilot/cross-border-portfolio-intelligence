"""CP4c: the single-series metrics and the state combination (`risk/single.py`, `risk/states.py`; `risk/1.2` Rulings 2.5, 3.4, 6.2 to 6.6, 6.12, 7.1, 7.3, 7.4).

Series are built by hand from exact returns, so every expectation here is arithmetic the reader can follow, independent of the market-data layer (the fixtures in `test_cp4_golden` cover the full path).
"""

import datetime
import re
import sys
import unittest
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from performance.grid import SeriesWindow  # noqa: E402
from performance.results import Cause, FreshnessVector, Part, WindowUsed  # noqa: E402
from performance.series import PeriodReturn, ReturnSeries, SeriesRefusal, assess  # noqa: E402
from performance.states import Valued  # noqa: E402
from product_contract.vocabulary import SufficiencyState as SS  # noqa: E402
from risk import single, stats  # noqa: E402
from risk import states as S  # noqa: E402
from risk.registry import REGISTRY  # noqa: E402
from risk.risk_free import PeriodRate  # noqa: E402
from risk.single import Declared, SingleInputs  # noqa: E402

D = datetime.date
FRIDAY = D(2025, 1, 3)
WEEK = datetime.timedelta(days=7)


def valued(exact, state=SS.AVAILABLE, reason=None, causes=()):
    return Valued(state, reason, None if state is SS.INSUFFICIENT_DATA else exact, tuple(causes))


def series_of(items, frequency="WEEKLY"):
    """A series on Friday grid points. Each item is an exact return (an AVAILABLE period) or a `Valued`."""
    dates = [FRIDAY + WEEK * i for i in range(len(items) + 1)]
    periods = []
    for a, b, item in zip(dates, dates[1:], items):
        v = item if isinstance(item, Valued) else valued(item)
        periods.append(PeriodReturn(a, b, v, (), 0, False))
    window = SeriesWindow("CUSTOM", None, frequency, "test", dates[0], dates[-1], dates[0], dates[-1], len(items), 0, 0)
    used = WindowUsed(dates[0], dates[-1], frequency, "CUSTOM")
    return ReturnSeries(used, window, frequency, "test", tuple(dates), tuple((d, valued(F(1))) for d in dates), tuple(periods), assess(periods), tuple(dates), tuple(dates))


def rates_for(series, rate=F(1, 10000), **kw):
    out = []
    for p in series.periods:
        if isinstance(rate, Valued):
            v = rate
        else:
            v = valued(rate)
        out.append(PeriodRate(p.start, p.end, p.start, 0, v, tuple(c.detail for c in v.causes if c.detail), "RF", (), (), True))
    return tuple(out)


def stale_cause(state, detail="RISK_FREE_STALE"):
    return Cause("risk_free:x", state.value, S.STALE_DATA, "stale", detail)


def declared_for(series, frequency="WEEKLY"):
    return Declared(frequency, "CUSTOM", None, series.boundaries[0], series.grid, True)


def run(items, wanted, frequency="WEEKLY", rate=F(1, 10000), rates=None, rate_series="RF", **kw):
    series = series_of(items, frequency)
    inputs = SingleInputs(series, None, rates_for(series, rate) if rates is None else rates(series), rate_series)
    return {m.metric_id: m for m in single.single_series_metrics(inputs, declared_for(series, frequency), wanted, **kw)}


def varied(n):
    """n returns that are not constant, with some below and some above a 1/10000 rate."""
    pattern = [F(1, 100), F(-1, 200), F(3, 400), F(-1, 100), F(1, 250), F(0), F(-3, 500)]
    return [pattern[i % len(pattern)] for i in range(n)]


ALL = ("risk_volatility", "risk_downside_deviation", "risk_max_drawdown", "risk_sharpe", "risk_sortino")


class CountThresholdTests(unittest.TestCase):
    """Ruling 7.1: below N1 no number, N1 to below N3 LIMITED with the value, from N3 no caveat. The numbers are the registry's, never the engine's."""

    def test_every_boundary_at_every_frequency(self):
        for frequency, (low, high) in (("WEEKLY", (51, 155)), ("MONTHLY", (11, 35)), ("DAILY", (259, 781))):
            self.assertEqual((REGISTRY.minimum_observations("risk_volatility", frequency).insufficient_below, REGISTRY.minimum_observations("risk_volatility", frequency).available_from), (low, high))
            for n, state, detail in ((low - 1, SS.INSUFFICIENT_DATA, "INSUFFICIENT_OBSERVATIONS"), (low, SS.LIMITED, "OBSERVATIONS_BELOW_STANDARD"), (high - 1, SS.LIMITED, "OBSERVATIONS_BELOW_STANDARD"),
                                     (high, SS.AVAILABLE, None)):
                m = run(varied(n), ("risk_volatility",), frequency)["risk_volatility"]
                self.assertEqual((m.state, m.details, m.observation_count, m.thresholds), (state, () if detail is None else (detail,), n, (low, high)), (frequency, n))
                self.assertIsNone(m.result.reason_code, (frequency, n))  # a count carries no reason code (Ruling 7.6)
                self.assertEqual(m.value is None, state is SS.INSUFFICIENT_DATA)

    def test_a_window_fact_has_no_statistical_minimum(self):
        m = run([F(-1, 10)], ("risk_max_drawdown",))["risk_max_drawdown"]
        self.assertEqual((m.state, m.value, m.thresholds, m.observation_count), (SS.AVAILABLE, Decimal("-0.1"), None, 1))

    def test_the_insufficient_result_carries_no_number_of_any_kind(self):
        m = run(varied(10), ("risk_volatility",))["risk_volatility"]
        self.assertEqual((m.value, m.exact, m.exact_square, m.sign), (None, None, None, None))


class StateCombinationTests(unittest.TestCase):
    """Ruling 7.3: the worst state; the single reason from the causes at the result's OWN level; every cause kept."""

    def stale_period(self, state=SS.LIMITED, exact=F(1, 100)):
        return valued(exact, state, S.STALE_DATA, (Cause("price", state.value, S.STALE_DATA, "2 sessions missed"),))

    def test_a_limited_period_makes_the_statistic_limited_with_stale_data_and_the_count(self):
        items = varied(155)
        items[10] = self.stale_period()
        items[20] = self.stale_period(exact=F(-1, 100))
        m = run(items, ("risk_volatility",))["risk_volatility"]
        self.assertEqual((m.state, m.result.reason_code.value, m.stale_period_count, m.details), (SS.LIMITED, "STALE_DATA", 2, ("STALE_PERIODS",)))

    def test_an_available_stale_period_is_available_with_stale_data_and_the_stale_periods_detail(self):
        # CP4M-1 (Ruling 7.4: STALE_PERIODS is "LIMITED or stale"; Ruling 7.3 (1.3) item 4): the reader is told a period was stale; the count is of LIMITED periods only (Ruling 2.5 item 2)
        items = varied(155)
        items[7] = self.stale_period(SS.AVAILABLE)
        m = run(items, ("risk_volatility",))["risk_volatility"]
        self.assertEqual((m.state, m.result.reason_code.value, m.stale_period_count, m.details), (SS.AVAILABLE, "STALE_DATA", None, ("STALE_PERIODS",)))

    def test_limited_by_count_with_an_available_stale_period_has_no_reason_but_lists_the_stale_period(self):
        # the Quant's M-C24 / R2-L2 reading (Ruling 7.3 (1.3)): the count is the LIMITED cause and carries no code; the AVAILABLE + STALE_DATA period is a lower-level cause and gives the reason NOTHING
        for n in (52, 100, 154):
            items = varied(n)
            items[7] = self.stale_period(SS.AVAILABLE)
            m = run(items, ("risk_volatility",))["risk_volatility"]
            self.assertEqual((m.state, m.result.reason_code, sorted(m.details)), (SS.LIMITED, None, ["OBSERVATIONS_BELOW_STANDARD", "STALE_PERIODS"]), n)
        items = varied(52)
        items[7] = self.stale_period(SS.AVAILABLE)
        dd = run(items, ("risk_max_drawdown",))["risk_max_drawdown"]  # a window fact has no count cause: AVAILABLE + STALE_DATA
        self.assertEqual((dd.state, dd.result.reason_code.value), (SS.AVAILABLE, "STALE_DATA"))

    def test_insufficient_by_count_has_no_reason_even_when_a_limited_input_carries_one(self):
        items = varied(40)
        items[3] = self.stale_period()
        m = run(items, ("risk_volatility",))["risk_volatility"]
        self.assertEqual((m.state, m.result.reason_code, m.stale_period_count), (SS.INSUFFICIENT_DATA, None, 1))
        self.assertEqual(sorted(m.details), ["INSUFFICIENT_OBSERVATIONS", "STALE_PERIODS"])  # every cause stays in lineage

    def test_an_insufficient_period_wins_and_its_reason_is_chosen_by_ruling_1_5_among_the_periods(self):
        fx = valued(None, SS.INSUFFICIENT_DATA, "MISSING_FX_HISTORY", (Cause("fx", "INSUFFICIENT_DATA", "MISSING_FX_HISTORY", "5 fixings missed"),))
        stale = valued(None, SS.INSUFFICIENT_DATA, "STALE_DATA", (Cause("price", "INSUFFICIENT_DATA", "STALE_DATA", "5 sessions missed"),))
        items = varied(60)
        items[5], items[6] = stale, fx
        m = run(items, ("risk_volatility", "risk_max_drawdown"))["risk_volatility"]
        self.assertEqual((m.state, m.result.reason_code.value, m.value), (SS.INSUFFICIENT_DATA, "MISSING_FX_HISTORY", None))  # MISSING_FX_HISTORY outranks STALE_DATA
        self.assertIn("PERIOD_INSUFFICIENT", m.details)
        self.assertEqual(len([c for c in m.causes if c.detail == "PERIOD_INSUFFICIENT"]), 2)  # every such period is listed with its own cause

    def test_a_period_insufficient_for_want_of_capital_has_no_reason(self):
        zero = valued(None, SS.INSUFFICIENT_DATA, None, (Cause("period", "INSUFFICIENT_DATA", None, "ZERO_CAPITAL_PERIOD", "ZERO_CAPITAL_PERIOD"),))
        items = varied(60)
        items[9] = zero
        m = run(items, ("risk_volatility",))["risk_volatility"]
        self.assertEqual((m.state, m.result.reason_code), (SS.INSUFFICIENT_DATA, None))
        self.assertEqual(sorted(m.details), ["OBSERVATIONS_BELOW_STANDARD", "PERIOD_INSUFFICIENT", "ZERO_CAPITAL_PERIOD"])  # 60 observations are also below the standard: every cause is listed (as fixture R9-Z1)

    def test_limited_by_count_and_by_a_stale_period_takes_the_stale_reason(self):
        items = varied(60)
        items[1] = self.stale_period()
        m = run(items, ("risk_volatility",))["risk_volatility"]
        self.assertEqual((m.state, m.result.reason_code.value), (SS.LIMITED, "STALE_DATA"))
        self.assertEqual(sorted(m.details), ["OBSERVATIONS_BELOW_STANDARD", "STALE_PERIODS"])

    def test_nothing_is_dropped_the_statistic_never_runs_on_the_rest(self):
        items = varied(60)
        items[3] = valued(None, SS.INSUFFICIENT_DATA, "MISSING_FX_HISTORY", (Cause("fx", "INSUFFICIENT_DATA", "MISSING_FX_HISTORY", "x"),))
        for m in run(items, ALL).values():
            self.assertEqual((m.state, m.value), (SS.INSUFFICIENT_DATA, None), m.metric_id)

    def test_combine_unit_rules(self):
        clean = Part("a", SS.AVAILABLE)
        limited = Part("b", SS.LIMITED, "STALE_DATA", (Cause("b", "LIMITED", "STALE_DATA", ""),))
        count = S.count_part("n", SS.LIMITED, "few", "OBSERVATIONS_BELOW_STANDARD")
        agg = S.combine([clean, count])
        self.assertEqual((agg.state, agg.reason), (SS.LIMITED, None))  # a count is not staleness: no STALE_DATA is invented (unlike CP3's rule)
        self.assertEqual(S.combine([clean, count, limited]).reason, "STALE_DATA")
        self.assertEqual((S.combine([clean]).state, S.combine([clean]).reason), (SS.AVAILABLE, None))
        avail_stale = Part("c", SS.AVAILABLE, "STALE_DATA", (Cause("c", "AVAILABLE", "STALE_DATA", ""),))
        self.assertEqual((S.combine([avail_stale]).state, S.combine([avail_stale]).reason), (SS.AVAILABLE, "STALE_DATA"))
        refused = Part("w", SS.INSUFFICIENT_DATA, "NOT_RECONSTRUCTABLE", (Cause("w", "INSUFFICIENT_DATA", "NOT_RECONSTRUCTABLE", "", "WINDOW_BEFORE_SNAPSHOT"),))
        self.assertEqual(S.combine([refused, limited]).reason, "NOT_RECONSTRUCTABLE")

    def test_the_detail_vocabulary_is_ruling_7_4_and_every_detail_a_metric_carries_is_in_it(self):
        self.assertEqual(len(S.RISK_DETAIL_NAMES), 23)
        items = varied(60)
        items[1] = self.stale_period()
        for m in run(items, ALL).values():
            self.assertTrue(set(m.details) <= S.RISK_DETAIL_NAMES | {""}, (m.metric_id, m.details))


class WindowRefusalTests(unittest.TestCase):
    def refusal(self, reason, detail):
        return SeriesRefusal(reason, Cause("window", "INSUFFICIENT_DATA", reason, f"{detail}: test", detail))

    def metrics(self, refusal):
        declared = Declared("WEEKLY", "TRAILING_MONTHS", 36, D(2022, 1, 5), None, True)
        return {m.metric_id: m for m in single.single_series_metrics(SingleInputs(None, refusal, None), declared, ALL)}

    def test_a_refused_window_suppresses_every_metric_with_its_detail(self):
        for m in self.metrics(self.refusal(None, "WINDOW_BEFORE_INCEPTION")).values():
            self.assertEqual((m.state, m.value, m.result.reason_code, m.details, m.window, m.requested_base), (SS.INSUFFICIENT_DATA, None, None, ("WINDOW_BEFORE_INCEPTION",), None, D(2022, 1, 5)), m.metric_id)

    def test_before_a_snapshot_the_reason_is_not_reconstructable(self):
        for m in self.metrics(self.refusal("NOT_RECONSTRUCTABLE", "WINDOW_BEFORE_SNAPSHOT")).values():
            self.assertEqual((m.state, m.result.reason_code.value, m.details), (SS.INSUFFICIENT_DATA, "NOT_RECONSTRUCTABLE", ("WINDOW_BEFORE_SNAPSHOT",)))


class DegenerateCaseTests(unittest.TestCase):
    def test_a_riskless_path_has_volatility_zero_a_value_and_no_ratio(self):
        m = run([F(0)] * 155, ALL)
        vol, dd = m["risk_volatility"], m["risk_max_drawdown"]
        self.assertEqual((vol.state, vol.value, vol.exact_square, vol.sign), (SS.AVAILABLE, Decimal("0.000000000000"), F(0), 0))  # zero is a fact, not a missing number
        self.assertEqual((dd.state, dd.value, dd.exact, dd.drawdown.peak_date), (SS.AVAILABLE, Decimal("0.000000000000"), F(0), None))
        for metric in ("risk_sharpe", "risk_sortino"):
            self.assertEqual((m[metric].state, m[metric].result.reason_code, m[metric].details), (SS.INSUFFICIENT_DATA, None, ("ZERO_VOLATILITY",)), metric)
        down = m["risk_downside_deviation"]  # every period fell short of the 1/10000 rate: positive, a fact about the rate, not a loss
        self.assertEqual((down.state, down.exact_square), (SS.AVAILABLE, F(52) * F(1, 10000) ** 2))

    def test_sortino_with_no_period_below_the_rate_names_it(self):
        m = run([F(1, 100) + F(i % 3, 1000) for i in range(155)], ALL)
        self.assertEqual((m["risk_sortino"].state, m["risk_sortino"].details), (SS.INSUFFICIENT_DATA, ("NO_DOWNSIDE_OBSERVATIONS",)))
        self.assertEqual((m["risk_downside_deviation"].state, m["risk_downside_deviation"].exact_square), (SS.AVAILABLE, F(0)))  # DD = 0 is a value
        self.assertEqual(m["risk_sharpe"].state, SS.AVAILABLE)  # Sharpe does not need a downside period

    def test_both_degenerate_causes_are_listed_when_both_hold(self):
        m = run([F(1, 10000) * 2] * 155, ("risk_sortino",))["risk_sortino"]
        self.assertEqual(sorted(m.details), ["NO_DOWNSIDE_OBSERVATIONS", "ZERO_VOLATILITY"])
        self.assertIsNone(m.result.reason_code)


class ValueTests(unittest.TestCase):
    def test_the_sharpe_is_the_signed_root_of_the_exact_radicand_and_matches_the_mean_over_the_volatility(self):
        items = varied(155)
        m = run(items, ("risk_sharpe", "risk_volatility", "risk_sortino", "risk_downside_deviation"))
        rf = F(1, 10000)
        d = [r - rf for r in items]
        dbar = sum(d, F(0)) / 155
        s2 = stats.sample_variance(items)
        self.assertEqual(m["risk_sharpe"].exact_square, F(52) * dbar * dbar / s2)
        self.assertEqual(m["risk_sharpe"].sign, 1 if dbar > 0 else -1)
        # RQ-1: Sharpe^2 s^2 = A dbar^2 on the EXACT radicand (no rounding anywhere)
        self.assertEqual(m["risk_sharpe"].exact_square * s2, 52 * dbar * dbar)
        shortfall = stats.shortfall_square_sum(d)
        self.assertEqual(m["risk_sortino"].exact_square * shortfall, 52 * dbar * dbar * 155)
        self.assertEqual(m["risk_downside_deviation"].exact_square, F(52) * shortfall / 155)
        # the identity the registry states: Sharpe = (A dbar) / (sqrt(A) s(r)) = annualized mean excess / volatility, so (Sharpe x vol)^2 = (A dbar)^2
        self.assertEqual(m["risk_sharpe"].exact_square * m["risk_volatility"].exact_square, (52 * dbar) ** 2)

    def test_a_negative_mean_excess_gives_a_negative_sign_and_a_zero_mean_gives_zero(self):
        items = [F(-1, 100) if i % 2 else F(1, 200) for i in range(155)]
        m = run(items, ("risk_sharpe",), rate=F(1, 1000))["risk_sharpe"]
        self.assertEqual(m.sign, -1)
        self.assertLess(m.value, 0)
        # a mean excess of exactly zero: alternate +x and -x around the rate
        rate = F(1, 1000)
        items = [rate + F(1, 100) if i % 2 == 0 else rate - F(1, 100) for i in range(156)]
        z = run(items, ("risk_sharpe",), rate=rate)["risk_sharpe"]
        self.assertEqual((z.exact_square, z.sign, z.value), (F(0), 0, Decimal("0.000000000000")))

    def test_presentation_is_half_away_from_zero_at_1e_12(self):
        self.assertEqual(single.present_rational(F(1, 2 * 10**12)), Decimal("0.000000000001"))  # an exact half quantum rounds up
        self.assertEqual(single.present_rational(F(-1, 2 * 10**12)), Decimal("-0.000000000001"))
        self.assertEqual(single.present_rational(F(1, 3)), Decimal("0.333333333333"))
        self.assertEqual(single.present_rational(F(-2, 3)), Decimal("-0.666666666667"))
        self.assertEqual(str(single.present_rational(F(3, 100))), "0.030000000000")  # carried with its twelve places

    def test_the_value_is_the_rounded_exact_value_never_a_float(self):
        m = run(varied(155), ("risk_max_drawdown",))["risk_max_drawdown"]
        self.assertIsInstance(m.value, Decimal)
        self.assertIsInstance(m.exact, F)
        self.assertEqual(m.value, single.present_rational(m.exact))

    def test_stats_come_from_exact_values_not_from_presented_ones(self):
        # two series whose periodic returns differ below the 12th decimal have different exact radicands though they may present alike
        a = [F(1, 100)] * 77 + [F(1, 200)] * 78
        b = [F(1, 100)] * 77 + [F(1, 200) + F(1, 10**15)] * 78
        ma, mb = run(a, ("risk_volatility",))["risk_volatility"], run(b, ("risk_volatility",))["risk_volatility"]
        self.assertNotEqual(ma.exact_square, mb.exact_square)

    def test_periods_per_year_is_the_registry_text(self):
        text = REGISTRY.entry("risk_volatility")["annualization_convention"]
        found = {name: int(n) for n, name in re.findall(r"(\d+) (DAILY|WEEKLY|MONTHLY)", text)}
        self.assertEqual(found, single.PERIODS_PER_YEAR)
        self.assertEqual(single.PERIODS_PER_YEAR, {"DAILY": 260, "WEEKLY": 52, "MONTHLY": 12})  # 252 is rejected (Ruling 3.1)

    def test_the_method_key_cites_the_registry_entry_and_its_id(self):
        m = run(varied(60), ("risk_volatility",))["risk_volatility"]
        self.assertEqual(m.method_key, "risk/1.11#risk_volatility")


class IntermediatesTests(unittest.TestCase):
    """CP4M-6 (Ruling 9.4): the exact sums and means a value came from are recorded, so an auditor can check RQ-1 and `Sharpe = annualized mean excess / volatility` from the result alone, without a re-run."""

    def setUp(self):
        self.items = varied(155)
        self.m = run(self.items, ALL)

    def inter(self, metric_id):
        return dict(self.m[metric_id].intermediates)

    def test_the_values_are_the_exact_means_and_sums(self):
        rf = F(1, 10000)
        d = [r - rf for r in self.items]
        self.assertEqual(self.inter("risk_volatility"), {"n": F(155), "mean_return": sum(self.items, F(0)) / 155, "sum_squared_deviations": centred(self.items), "variance": centred(self.items) / 154})
        self.assertEqual(self.inter("risk_sharpe"), {"n": F(155), "mean_excess": sum(d, F(0)) / 155, "mean_return": sum(self.items, F(0)) / 155, "mean_risk_free": rf, "shortfall_sum": sum((x * x for x in d if x < 0), F(0)),
                                                    "variance": centred(self.items) / 154})
        self.assertEqual(self.inter("risk_downside_deviation")["mean_risk_free"], rf)  # the mean the alpha of Ruling 6.8 is shown with
        self.assertEqual(set(self.inter("risk_downside_deviation")), {"n", "mean_excess", "mean_risk_free", "shortfall_sum"})
        self.assertEqual(set(self.inter("risk_sortino")), {"n", "mean_excess", "mean_return", "mean_risk_free", "shortfall_sum", "variance"})

    def test_rq1_and_the_stated_identities_are_checkable_from_the_result_alone(self):
        A, n = 52, 155
        sharpe, sortino, vol, down = (self.m[k] for k in ("risk_sharpe", "risk_sortino", "risk_volatility", "risk_downside_deviation"))
        s, so = dict(sharpe.intermediates), dict(sortino.intermediates)
        self.assertEqual(sharpe.exact_square * s["variance"], A * s["mean_excess"] ** 2)  # RQ-1, no re-run
        self.assertEqual(sortino.exact_square * so["shortfall_sum"], A * so["mean_excess"] ** 2 * n)
        self.assertEqual(vol.exact_square, A * dict(vol.intermediates)["variance"])
        self.assertEqual(down.exact_square, A * dict(down.intermediates)["shortfall_sum"] / n)
        # the mean excess return is the mean return less the mean risk-free return
        self.assertEqual(s["mean_excess"], s["mean_return"] - s["mean_risk_free"])

    def test_a_suppressed_metric_records_none_and_a_window_fact_without_levels_records_none(self):
        short = run(varied(10), ALL)
        for metric in short.values():
            if metric.value is None:
                self.assertEqual(metric.intermediates, (), metric.metric_id)
        dd = self.m["risk_max_drawdown"]
        self.assertEqual([k for k, _ in dd.intermediates], ["n", "wealth_peak", "wealth_trough"])  # Ruling 9.4 (1.4): n and W at the peak and the trough (the three dates are its facts)
        w = dict(dd.intermediates)
        self.assertEqual(w["wealth_trough"] / w["wealth_peak"] - 1, dd.exact)
        self.assertEqual(w["n"], 155)

    def test_they_are_in_the_canonical_form_and_so_in_the_digest(self):
        from risk.results import risk_digest  # noqa: PLC0415

        m = self.m["risk_sharpe"]
        obj = m.to_canonical_dict()
        self.assertEqual([n for n, _v in obj["intermediates"]], ["mean_excess", "mean_return", "mean_risk_free", "n", "shortfall_sum", "variance"])  # sorted by name
        import dataclasses  # noqa: PLC0415

        changed = dataclasses.replace(m, intermediates=(("mean_excess", F(1)),) + m.intermediates[1:])
        self.assertNotEqual(risk_digest((m,)), risk_digest((changed,)))

    def test_an_intermediate_is_an_exact_fraction_and_sorted(self):
        import dataclasses  # noqa: PLC0415

        m = self.m["risk_sharpe"]
        with self.assertRaises(ValueError):
            dataclasses.replace(m, intermediates=tuple(reversed(m.intermediates)))
        with self.assertRaises(TypeError):
            dataclasses.replace(m, intermediates=(("x", 0.5),))


def centred(values):
    mean = sum(values, F(0)) / len(values)
    return sum(((v - mean) ** 2 for v in values), F(0))


class RiskFreeStateTests(unittest.TestCase):
    def test_no_series_makes_only_the_rate_metrics_unavailable_and_says_why(self):
        cause = Cause("risk_free:x", "INSUFFICIENT_DATA", None, "no admitted series", "NO_RISK_FREE_SOURCE")
        missing = Valued(SS.INSUFFICIENT_DATA, None, None, (cause,))
        m = run(varied(155), ALL, rates=lambda s: rates_for(s, missing), rate_series=None)
        for metric in ("risk_downside_deviation", "risk_sharpe", "risk_sortino"):
            self.assertEqual((m[metric].state, m[metric].result.reason_code, "NO_RISK_FREE_SOURCE" in m[metric].details), (SS.INSUFFICIENT_DATA, None, True), metric)
        for metric in ("risk_volatility", "risk_max_drawdown"):
            self.assertIn(m[metric].state, (SS.AVAILABLE,), metric)  # they do not use the rate (Ruling 4.6)

    def test_a_rate_two_publications_stale_is_limited_stale_data_and_five_withhold_the_number(self):
        two = Valued(SS.LIMITED, "STALE_DATA", F(1, 10000), (stale_cause(SS.LIMITED),))
        five = Valued(SS.INSUFFICIENT_DATA, "STALE_DATA", None, (stale_cause(SS.INSUFFICIENT_DATA),))
        items = varied(155)
        limited = run(items, ("risk_sharpe",), rates=lambda s: rates_for(s, F(1, 10000))[:-1] + rates_for(s, two)[-1:])["risk_sharpe"]
        self.assertEqual((limited.state, limited.result.reason_code.value, "RISK_FREE_STALE" in limited.details), (SS.LIMITED, "STALE_DATA", True))
        withheld = run(items, ("risk_sharpe",), rates=lambda s: rates_for(s, F(1, 10000))[:-1] + rates_for(s, five)[-1:])["risk_sharpe"]
        self.assertEqual((withheld.state, withheld.value, withheld.result.reason_code.value), (SS.INSUFFICIENT_DATA, None, "STALE_DATA"))

    def test_the_rate_series_id_travels_with_a_rate_metric_only(self):
        m = run(varied(155), ("risk_sharpe", "risk_volatility"))
        self.assertIn(("risk_free_series", "RF"), m["risk_sharpe"].lineage)
        self.assertNotIn("risk_free_series", dict(m["risk_volatility"].lineage))

    def test_a_negative_rate_is_a_rate(self):
        m = run(varied(155), ("risk_downside_deviation",), rate=F(-1, 10000))["risk_downside_deviation"]
        self.assertEqual(m.state, SS.AVAILABLE)


class IdentityFaultTests(unittest.TestCase):
    def series_and_inputs(self, items):
        series = series_of(items)
        return series, SingleInputs(series, None, rates_for(series), "RF")

    def test_rd1_passes_when_the_tr_engine_agrees(self):
        items = [F(1, 10), F(-1, 10), F(2, 33)]
        series, inputs = self.series_and_inputs(items)
        dates = series.boundaries
        calls = []

        def twr(start, end):
            calls.append((start, end))
            return F(-1, 10) if (start, end) == (dates[1], dates[2]) else None

        m = single.single_series_metrics(inputs, declared_for(series), ("risk_max_drawdown",), reconcile=twr)[0]
        self.assertEqual((m.state, m.value, calls), (SS.AVAILABLE, Decimal("-0.1"), [(dates[1], dates[2])]))  # the reconciliation is asked over (peak, trough] exactly
        self.assertIn(("identity:RD-1", "PASS"), m.lineage)
        self.assertEqual((m.drawdown.peak_date, m.drawdown.trough_date, m.drawdown.recovery_date, m.drawdown.peak_rule), (dates[1], dates[2], None, "WITHIN_WINDOW_FROM_BASE"))

    def test_rd1_failing_is_a_calculation_error_and_no_number(self):
        series, inputs = self.series_and_inputs([F(1, 10), F(-1, 10), F(2, 33)])
        m = single.single_series_metrics(inputs, declared_for(series), ("risk_max_drawdown",), reconcile=lambda a, b: F(-99, 1000))[0]
        self.assertEqual((m.state, m.value, m.exact, m.result.reason_code.value, m.details), (SS.INSUFFICIENT_DATA, None, None, "CALCULATION_ERROR", ("IDENTITY_FAILED",)))
        self.assertIn(("identity:RD-1", "FAIL"), m.lineage)

    def test_rd1_with_no_twr_is_a_failure_too_the_series_was_all_exact(self):
        series, inputs = self.series_and_inputs([F(1, 10), F(-1, 10)])
        m = single.single_series_metrics(inputs, declared_for(series), ("risk_max_drawdown",), reconcile=lambda a, b: None)[0]
        self.assertEqual((m.state, m.result.reason_code.value), (SS.INSUFFICIENT_DATA, "CALCULATION_ERROR"))

    def test_rd3_failing_is_a_calculation_error(self):
        series, inputs = self.series_and_inputs([F(-1, 4), F(1, 10)])
        wrong = stats.Drawdown(F(-1, 10), 0, 1, None, stats.wealth_path([F(-1, 4), F(1, 10)]))  # a drawdown shallower than the first period's fall
        with mock.patch.object(single.stats, "max_drawdown", return_value=wrong):
            m = single.single_series_metrics(inputs, declared_for(series), ("risk_max_drawdown",))[0]
        self.assertEqual((m.state, m.result.reason_code.value), (SS.INSUFFICIENT_DATA, "CALCULATION_ERROR"))
        self.assertIn(("identity:RD-3", "FAIL"), m.lineage)

    def test_rq1_failing_is_a_calculation_error(self):
        series, inputs = self.series_and_inputs(varied(155))
        builder = single.MetricBuilder(declared_for(series))
        parts, stale, ok = single._base_parts(REGISTRY, "risk_sharpe", inputs, declared_for(series), True)
        m = single._checked_ratio(builder, "risk_sharpe", parts, stale, [], F(1), F(1), lambda: False, "test")
        self.assertEqual((m.state, m.result.reason_code.value, m.details), (SS.INSUFFICIENT_DATA, "CALCULATION_ERROR", ("IDENTITY_FAILED",)))

    def test_a_suppressed_drawdown_is_not_reconciled(self):
        called = []
        series = series_of([F(1, 10)] * 3)
        bad = valued(None, SS.INSUFFICIENT_DATA, "MISSING_FX_HISTORY", (Cause("fx", "INSUFFICIENT_DATA", "MISSING_FX_HISTORY", "x"),))
        series = series_of([F(1, 10), bad, F(1, 10)])
        m = single.single_series_metrics(SingleInputs(series, None, None), declared_for(series), ("risk_max_drawdown",), reconcile=lambda a, b: called.append(1))[0]
        self.assertEqual((m.state, called), (SS.INSUFFICIENT_DATA, []))


class BuilderTests(unittest.TestCase):
    def test_a_value_is_required_unless_the_state_is_insufficient(self):
        series = series_of(varied(60))
        builder = single.MetricBuilder(declared_for(series))
        with self.assertRaises(ValueError):
            builder.build("risk_volatility", [], None)

    def test_only_single_series_metrics_are_computed_here(self):
        series = series_of(varied(60))
        with self.assertRaises(ValueError):
            single.single_series_metrics(SingleInputs(series, None, None), declared_for(series), ("risk_beta",))

    def test_an_unknown_registry_entry_fails_closed(self):
        series = series_of(varied(60))
        with self.assertRaises(KeyError):
            single.MetricBuilder(declared_for(series)).build("risk_not_a_metric", [], None)

    def test_metrics_come_back_in_metric_id_order(self):
        m = single.single_series_metrics(SingleInputs(series_of(varied(60)), None, None), declared_for(series_of(varied(60))), ("risk_volatility", "risk_max_drawdown"))
        self.assertEqual([x.metric_id for x in m], ["risk_max_drawdown", "risk_volatility"])


if __name__ == "__main__":
    unittest.main()
