"""The benchmark-relative metrics (`risk/1.4` Rulings 6.7 to 6.11, 6.13, 7.3, 8; tech plan 17.20).

beta and R-squared (the market model on total returns), Jensen's alpha, active return, tracking error and the information ratio. Each is two-leg (Ruling 8.1): the portfolio's periodic returns `r_k` against the benchmark's
`b_k = L_R(g_k) / L_R(g_{k-1}) - 1` on the SAME grid, read from the benchmark's translated levels (`risk.benchmark`). Everything is an exact rational; a square-root output is `sign * sqrt(Q)` with `Q` exact.

THE PARTS of one metric, in the order of Ruling 7.3: the window and the series' periods (Ruling 2.5), the risk-free returns (alpha only), the benchmark levels and translations at every grid date the metric reads
(`g_0 ... g_n`; `g_0` and `g_n` only for the active return, Ruling 6.9 (1.1)), the observation count (Ruling 7.1), then the degenerate cases (Ruling 6.12). A refused benchmark (no selection, no series, a price-return
series, a window it does not cover) is `INSUFFICIENT_DATA` + `MISSING_BENCHMARK` whatever the portfolio's own state, and the portfolio's own details stay in the lineage (UAT-03: the portfolio's numbers do not change).

THE IDENTITIES that must hold exactly (Ruling 6.13), each a runtime check whose failure is `INSUFFICIENT_DATA` + `CALCULATION_ERROR`, never a number: RS-2 (`prod (1 + b_k) = L_R(g_n) / L_R(g_0)`), RB-1
(`0 <= R^2 <= 1` and `beta^2 S_bb = R^2 S_rr`), RS-1 (the series' chained window return equals the TWR engine's own; the active return's TWR leg), RQ-1 on the information ratio and the tracking error's square.

THE MANIFEST'S EXACT INTERMEDIATES (Ruling 9.4 (1.4)) ride on each metric (`RiskMetric.intermediates`, in the digest): n, the means, `S_rb`, `S_bb`, `S_rr`, `v_beta` for beta; for alpha `rf_bar`, `d_bar`, `x_bar` and `beta`
(with its own `S_rb`, `S_bb`); `a_bar`, `S_aa`, `s2(a)` for tracking error and the information ratio; the two exact legs for the active return. None is presented.
"""

from __future__ import annotations

import datetime
from fractions import Fraction
from typing import Callable, List, Optional, Sequence, Tuple

from marketdata.calendars import CalendarSet
from performance.numerics import apportion
from performance.results import Part
from performance.series import ReturnSeries, SeriesRefusal
from performance.states import Valued
from product_contract.vocabulary import SufficiencyState
from risk import states as S
from risk import stats
from risk.benchmark import BenchmarkLeg, BenchmarkRefusal
from risk.comparability import comparability
from risk.registry import REGISTRY, RiskRegistry
from risk.results import BenchmarkRef, RiskMetric
from risk.risk_free import PeriodRate
from risk.single import (
    DIGITS,
    PASS,
    RB1,
    RS1,
    RS2,
    Declared,
    MetricBuilder,
    SingleInputs,
    Value,
    _base_parts,
    count_parts,
    _rate_mean,
    _returns,
    periods_per_year,
    present_rational,
    window_part,
)

AVAILABLE, LIMITED, INSUFFICIENT = SufficiencyState.AVAILABLE, SufficiencyState.LIMITED, SufficiencyState.INSUFFICIENT_DATA

BETA, R_SQUARED, ALPHA, TRACKING_ERROR, INFORMATION_RATIO, ACTIVE_RETURN = (
    "risk_beta", "risk_r_squared", "risk_alpha_jensen", "risk_tracking_error", "risk_information_ratio", "risk_active_return")
RELATIVE_METRICS = (ACTIVE_RETURN, ALPHA, BETA, INFORMATION_RATIO, R_SQUARED, TRACKING_ERROR)
RATE_DEPENDENT_RELATIVE = frozenset({ALPHA})
#: `reconcile(start, end)`: the TWR of `(start, end]` from the TWR engine itself (RS-1)
Reconcile = Callable[[datetime.date, datetime.date], Optional[Fraction]]


def _level_parts(leg: BenchmarkLeg, dates: Sequence[datetime.date]) -> List[Part]:
    """The benchmark levels (and their translations) the metric reads: each that is not clean lists itself with its causes (Ruling 5.2, `BENCHMARK_STALE`)."""
    out: List[Part] = []
    for g in dates:
        v = leg.level_at(g).valued
        if v.state is AVAILABLE and v.reason is None:
            continue
        out.append(v.as_part(f"benchmark_level@{g.isoformat()}"))
    return out


def _benchmark_returns(leg: BenchmarkLeg, dates: Sequence[datetime.date]) -> Tuple[List[Fraction], Fraction, Fraction]:
    """`b_k` on consecutive grid dates from the translated levels, and the first and last translated level."""
    levels: List[Fraction] = []
    for g in dates:
        t = leg.level_at(g).translated
        assert t is not None and t > 0
        levels.append(t)
    return [levels[k] / levels[k - 1] - 1 for k in range(1, len(levels))], levels[0], levels[-1]


def relative_metrics(
    series: Optional[ReturnSeries], refusal: Optional[SeriesRefusal], rates: Optional[Tuple[PeriodRate, ...]], rate_series_id: Optional[str], leg: Optional[BenchmarkLeg],
    leg_refusal: Optional[BenchmarkRefusal], declared: Declared, wanted: Sequence[str], *, registry: RiskRegistry = REGISTRY, benchmark: Optional[BenchmarkRef] = None,
    reconcile: Optional[Reconcile] = None, calendars: Optional[CalendarSet] = None, window_twr: Optional[Callable[[datetime.date, datetime.date], Valued]] = None,
    rate_probe: Optional[PeriodRate] = None,
) -> Tuple[RiskMetric, ...]:
    builder = MetricBuilder(declared, registry, benchmark)
    A = periods_per_year(declared.frequency)
    inputs = SingleInputs(series, refusal, rates, rate_series_id, rate_probe)
    out: List[RiskMetric] = []
    for metric_id in sorted(set(wanted)):
        if metric_id not in RELATIVE_METRICS:
            raise ValueError(f"{metric_id!r} is not a benchmark-relative metric")
        parts, stale, ok = _base_parts(registry, metric_id, inputs, declared, metric_id in RATE_DEPENDENT_RELATIVE)
        engine_twr: Optional[Valued] = None
        if metric_id == ACTIVE_RETURN and series is not None and window_twr is not None:
            # Ruling 6.9 (1.1): the portfolio leg's state is that of `TWR(g_0, g_n]` (performance Ruling 5.5), the window return from the TWR engine itself, not the periods' causes
            engine_twr = window_twr(series.boundaries[0], series.boundaries[-1])
            parts = [engine_twr.as_part(f"portfolio:{series.boundaries[0].isoformat()}..{series.boundaries[-1].isoformat()}")] + count_parts(registry, metric_id, declared.frequency, declared.n)  # type: ignore[arg-type]
            stale, ok = 0, all(p.state is not INSUFFICIENT for p in parts)
        if metric_id == ACTIVE_RETURN and series is not None and any(p.zero_capital for p in series.periods):
            # Ruling 6.9 (1.5): the TWR's factor 1 over an empty period is an accounting convention; set against the benchmark's real return over the whole window it would be a measured 0 %. Refused, no
            # reason, the one detail; the benchmark return is unaffected (it has no portfolio leg). It combines with every other cause by Ruling 7.3.
            parts = parts + [S.count_part("zero_capital", INSUFFICIENT, f"{S.ZERO_CAPITAL_PERIOD}: the portfolio held no capital for a whole grid period of the window; an active return would turn the TWR's factor 1 into a measured 0 %",
                                          S.ZERO_CAPITAL_PERIOD)]
            ok = False
        lineage = [] if not (metric_id in RATE_DEPENDENT_RELATIVE and rate_series_id) else [("risk_free_series", rate_series_id)]
        if engine_twr is not None:  # Ruling 7.7 (1.6): the service reads the portfolio leg's own state here (a history gap the TWR reports, whatever its performance detail), never from a detail name
            lineage.append(("portfolio_leg_state", engine_twr.state.value))
        if leg_refusal is not None:  # no benchmark to compare with: MISSING_BENCHMARK, and the portfolio's own causes stay listed
            out.append(builder.build(metric_id, parts + [leg_refusal.part("benchmark")], None, stale_period_count=stale, lineage=lineage))
            continue
        if series is None or leg is None:
            out.append(builder.build(metric_id, parts, None, stale_period_count=stale, lineage=lineage))
            continue
        used = (series.boundaries[0], series.boundaries[-1]) if metric_id == ACTIVE_RETURN else series.boundaries
        parts += _level_parts(leg, used) + leg.span_parts(used)  # a ratio across a disputed corporate action of an ETF proxy has no factor (Ruling 5.5 (1.6))
        lineage.append(("benchmark_files", str(len(leg.consumed))))
        if not (ok and all(p.state is not INSUFFICIENT for p in parts)):
            out.append(builder.build(metric_id, parts, None, stale_period_count=stale, lineage=lineage))
            continue
        out.append(_one(builder, registry, metric_id, parts, stale, lineage, series, rates, leg, A, declared, reconcile, calendars, used, engine_twr))
    return tuple(out)


def _one(builder: MetricBuilder, registry: RiskRegistry, metric_id: str, parts: List[Part], stale: int, lineage: List[Tuple[str, str]], series: ReturnSeries, rates: Optional[Tuple[PeriodRate, ...]],
         leg: BenchmarkLeg, A: int, declared: Declared, reconcile: Optional[Reconcile], calendars: Optional[CalendarSet], used: Sequence[datetime.date], engine_twr: Optional[Valued] = None) -> RiskMetric:
    # CP4e: a window fact reads the TWR engine's window return (Ruling 6.9 (1.1)), not the periods. A period can be INSUFFICIENT_DATA for an INTERIOR valuation that is not an input of the TWR over `(g_0, g_n]`
    # (an interior grid date's missing fixing, say), so the active return over such a window has no period chain to check against the engine (RS-1 is then NOT_COMPUTABLE, said so in the lineage), and its value is
    # the engine's. (A window with a zero-capital period never gets here for the active return: Ruling 6.9 (1.5) refuses it, in `relative_metrics`.) Every other metric reads the periods and was refused before
    # reaching here (Ruling 2.5).
    chain_exists = all(p.exact is not None for p in series.periods)
    if not chain_exists and (metric_id != ACTIVE_RETURN or engine_twr is None or engine_twr.exact is None):
        return builder.fault(metric_id, parts, "a period without a return reached a statistic that reads the periods", "RP-1")
    r = _returns(series) if chain_exists else []
    n = len(r) if chain_exists else series.grid.observation_count
    b, first, last = _benchmark_returns(leg, used)  # a window fact reads `g_0` and `g_n` only: an interior level is not an input (a withheld or stale interior day does not touch it)
    prod = Fraction(1)
    for x in b:
        prod *= 1 + x
    if prod != last / first:  # RS-2
        return builder.fault(metric_id, parts, f"RS-2 failed: prod(1 + b_k) = {prod}, L_R(g_n) / L_R(g_0) = {last / first}", RS2)
    lineage = lineage + [("identity:RS-2", PASS)]
    comp = comparability(series, leg, used, calendars)

    def build(value: Optional[Value], extra: Sequence[Part] = (), **kw) -> RiskMetric:
        degenerate = list(extra)
        if degenerate:
            return builder.build(metric_id, parts + degenerate, None, stale_period_count=stale, lineage=lineage)
        return builder.build(metric_id, parts, value, stale_period_count=stale, lineage=lineage, comparability=comp, **kw)

    n_ = Fraction(n)
    if metric_id == ACTIVE_RETURN:
        twr = Fraction(1)
        for x in r:
            twr *= 1 + x
        twr -= 1
        bench = last / first - 1
        engine = engine_twr.exact if engine_twr is not None else (reconcile(series.boundaries[0], series.boundaries[-1]) if reconcile is not None else None)
        if not chain_exists:
            assert engine is not None
            twr = engine
            lineage = lineage + [("identity:RS-1", "NOT_COMPUTABLE")]
        elif engine_twr is not None or reconcile is not None:  # RS-1: the window return the series gives is the TWR engine's own
            if engine is None or engine != twr:
                return builder.fault(metric_id, parts, "RS-1 failed: the series' window return differs from the TWR engine's", RS1)
            lineage = lineage + [("identity:RS-1", PASS)]
        active = twr - bench
        shown = apportion(twr, [bench, active], DIGITS)  # Ruling 6.9 (1.1): the displayed difference is the difference of the displayed legs
        view = (("portfolio_twr", present_rational(twr)), ("benchmark_return", present_rational(shown[0])), ("active_return", present_rational(shown[1])))
        value = Value(rational=active, intermediates=(("benchmark_return", bench), ("n", n_), ("portfolio_twr", twr)))
        return builder.build(metric_id, parts, value, stale_period_count=stale, lineage=lineage, comparability=comp, decomposition=view)

    if metric_id in (TRACKING_ERROR, INFORMATION_RATIO):
        a = [x - y for x, y in zip(r, b)]
        abar, s_aa, variance = stats.mean(a), stats.sum_squared_deviations(a), stats.sample_variance(a)
        inter = (("n", n_), ("mean_active", abar), ("sum_squared_deviations", s_aa), ("variance", variance))
        if metric_id == TRACKING_ERROR:
            return build(Value(radicand=stats.volatility_radicand(a, A), intermediates=inter))
        if variance == 0:
            return build(None, [S.count_part("degenerate", INSUFFICIENT, f"{S.ZERO_TRACKING_ERROR}: the active returns did not vary, a ratio to their dispersion is undefined", S.ZERO_TRACKING_ERROR)])
        q = A * abar * abar / variance
        if q * variance != A * abar * abar:  # RQ-1 on the exact radicand
            return builder.fault(metric_id, parts, "RQ-1 failed: IR^2 s^2(a) = A abar^2", "RQ-1")
        return build(Value(radicand=q, sign=stats.sign_of(abar), intermediates=inter))

    # beta, R-squared and alpha share the market model
    rbar, bbar = stats.mean(r), stats.mean(b)
    s_rb, s_bb, s_rr = stats.sum_cross_deviations(r, b), stats.sum_squared_deviations(b), stats.sum_squared_deviations(r)
    market = (("n", n_), ("mean_return", rbar), ("mean_benchmark_return", bbar), ("sum_cross_deviations", s_rb), ("sum_squared_deviations_benchmark", s_bb), ("sum_squared_deviations_return", s_rr))
    degenerate: List[Part] = []
    if s_bb == 0:
        degenerate.append(S.count_part("degenerate_benchmark", INSUFFICIENT, f"{S.ZERO_BENCHMARK_VARIANCE}: the benchmark did not move, so there is no slope to estimate", S.ZERO_BENCHMARK_VARIANCE))
    if metric_id == R_SQUARED and s_rr == 0:
        degenerate.append(S.count_part("degenerate_portfolio", INSUFFICIENT, f"{S.ZERO_PORTFOLIO_VARIANCE}: the portfolio did not move, so its variance is not explained by anything (0/0)", S.ZERO_PORTFOLIO_VARIANCE))
    if degenerate:
        return build(None, degenerate)
    beta = s_rb / s_bb
    if metric_id == BETA:
        v_beta = (s_rr - beta * s_rb) / ((n - 2) * s_bb)  # exact; recorded for the insight layer, never presented
        if beta * beta * s_bb != beta * s_rb:  # beta^2 S_bb = beta S_rb exactly (the OLS normal equation behind RB-1)
            return builder.fault(metric_id, parts, "RB-1 failed: beta^2 S_bb differs from beta S_rb", RB1)
        return build(Value(rational=beta, intermediates=market + (("v_beta", v_beta),)))
    if metric_id == R_SQUARED:
        r2 = s_rb * s_rb / (s_bb * s_rr)
        if not (0 <= r2 <= 1) or beta * beta * s_bb != r2 * s_rr:  # RB-1
            return builder.fault(metric_id, parts, f"RB-1 failed: R^2 = {r2}, beta^2 S_bb = {beta * beta * s_bb}, R^2 S_rr = {r2 * s_rr}", RB1)
        return build(Value(rational=r2, intermediates=market))
    assert metric_id == ALPHA and rates is not None
    rf_bar = _rate_mean(rates)
    dbar, xbar = rbar - rf_bar, bbar - rf_bar
    alpha = A * (dbar - beta * xbar)
    inter = (("n", n_), ("mean_risk_free", rf_bar), ("mean_excess", dbar), ("mean_benchmark_excess", xbar), ("beta", beta), ("sum_cross_deviations", s_rb), ("sum_squared_deviations_benchmark", s_bb))
    return build(Value(rational=alpha, intermediates=inter))
