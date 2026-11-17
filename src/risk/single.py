"""The single-series metrics and the builder every risk metric goes through (`risk/1.1` Rulings 1.1, 2.5, 6.2 to 6.6, 7.1, 7.3, 7.5; tech plan 17.7, 17.16).

`MetricBuilder.build` is the ONE place a `RiskMetric` is made: it combines the parts into a state and a single reason (`risk.states.combine`, Ruling 7.3), suppresses the number unless the state allows one, presents it
(`10^-12`, half away from zero: Ruling 3.4 item 3; a square-root output by the exact integer root of `risk.sqrt`) and keeps every cause and detail. Nothing computes from a presented value.

Each metric's PARTS are, in the order of Ruling 7.3:
1. the window: a refused request is INSUFFICIENT_DATA with its detail (`WINDOW_BEFORE_INCEPTION`, `NO_FULL_PERIOD`, ...) and its reason (none, or `NOT_RECONSTRUCTABLE` before a snapshot);
2. the periods (Ruling 2.5): ANY insufficient period makes every statistic over the window INSUFFICIENT_DATA (`PERIOD_INSUFFICIENT`, the reason chosen by Ruling 1.5 among those periods' causes, each period listed
   with its cause); otherwise any LIMITED period makes it LIMITED + STALE_DATA (`STALE_PERIODS`, with the count `stale_period_count`); otherwise any AVAILABLE + STALE_DATA period makes it AVAILABLE + STALE_DATA.
   Nothing is dropped, filled or merged;
3. the risk-free returns, for a metric that uses the rate (Ruling 4.4);
4. the observation count against the registry's thresholds (Ruling 7.1: below `N1` INSUFFICIENT_DATA `INSUFFICIENT_OBSERVATIONS`, below `N3` LIMITED `OBSERVATIONS_BELOW_STANDARD`; neither carries a reason code);
5. the degenerate cases (Ruling 6.12: `ZERO_VOLATILITY`, `NO_DOWNSIDE_OBSERVATIONS`; a zero volatility or drawdown is a VALUE, never one of these).

The maximum drawdown is `risk.stats.max_drawdown` (Ruling 1.3: one function owns the rule), reconciled at runtime against the TWR engine (RD-1) and against a single period's fall (RD-3; Ruling 1.4): a failed
identity is an engine fault, `INSUFFICIENT_DATA` + `CALCULATION_ERROR`, never a number.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from performance.grid import SeriesWindow
from performance.numerics import round_half_up, to_decimal_money
from performance.results import Cause, Part
from performance.series import ReturnSeries, SeriesRefusal
from product_contract.vocabulary import SufficiencyState
from risk import states as S
from risk import stats
from risk.registry import REGISTRY, RiskRegistry
from risk.results import BenchmarkRef, Comparability, DrawdownFacts, RiskMetric
from risk.risk_free import PeriodRate
from risk.sqrt import DIGITS, sqrt_rounded

AVAILABLE, LIMITED, INSUFFICIENT = SufficiencyState.AVAILABLE, SufficiencyState.LIMITED, SufficiencyState.INSUFFICIENT_DATA

#: periods per year `A_f` (Ruling 3.1; the registry's `common` block states the same table, and a test ties the two)
PERIODS_PER_YEAR = {"DAILY": 260, "WEEKLY": 52, "MONTHLY": 12}

VOLATILITY, DOWNSIDE, DRAWDOWN, SHARPE, SORTINO = "risk_volatility", "risk_downside_deviation", "risk_max_drawdown", "risk_sharpe", "risk_sortino"
BENCHMARK_RETURN = "benchmark_return"
SINGLE_SERIES_METRICS = (VOLATILITY, DOWNSIDE, DRAWDOWN, SHARPE, SORTINO)
RATE_DEPENDENT = frozenset({DOWNSIDE, SHARPE, SORTINO})

RD1, RD3 = "RD-1", "RD-3"
RS2, RS1, RB1 = "RS-2", "RS-1", "RB-1"  # Ruling 6.13: the benchmark identities (relative metrics, `risk.relative`). RS-1 is the series' window return against the TWR engine's (CP4F: it was labelled RA-1)
PASS, FAIL = "PASS", "FAIL"


@dataclass(frozen=True)
class Value:
    """What a metric computed, before presentation: a rational, or `sign * sqrt(Q)` (Ruling 3.4 item 2)."""

    rational: Optional[Fraction] = None
    radicand: Optional[Fraction] = None
    sign: int = 1
    intermediates: Tuple[Tuple[str, Union[Fraction, datetime.date]], ...] = ()  # Ruling 9.4: the exact sums and means the value came from (a fixing date is a date)


@dataclass(frozen=True)
class Declared:
    """What every result declares about its question (Ruling 2.3): the request, the effective window and the count. `window` is None when the request was refused."""

    frequency: str
    rule: Optional[str]
    months: Optional[int]
    requested_base: Optional[datetime.date]
    window: Optional[SeriesWindow]
    synthetic: bool

    @property
    def n(self) -> Optional[int]:
        return None if self.window is None else self.window.observation_count


def periods_per_year(frequency: str) -> int:
    return PERIODS_PER_YEAR[frequency]


# --- parts ------------------------------------------------------------------------------------------------------------------------------------

def window_part(refusal: SeriesRefusal) -> Part:
    """A refused window (Ruling 2.3): INSUFFICIENT_DATA with the cause's detail and the refusal's own reason (None, or NOT_RECONSTRUCTABLE before a snapshot)."""
    return Part("window", INSUFFICIENT, refusal.reason, (refusal.cause,))


def series_parts(series: ReturnSeries) -> Tuple[List[Part], int]:
    """Ruling 2.5 as parts, and the number of LIMITED periods (`stale_period_count`). A clean period contributes nothing; every other one lists itself with its own causes."""
    parts: List[Part] = []
    limited = 0
    for p in series.periods:
        v = p.valued
        ref = f"period:{p.start.isoformat()}..{p.end.isoformat()}"
        if v.state is INSUFFICIENT:
            note = f"{S.PERIOD_INSUFFICIENT}: the return of ({p.start.isoformat()}, {p.end.isoformat()}] is INSUFFICIENT_DATA"
            parts.append(Part(ref, INSUFFICIENT, v.reason, (Cause(ref, INSUFFICIENT.value, v.reason, note, S.PERIOD_INSUFFICIENT),) + tuple(v.causes)))
        elif v.state is LIMITED:
            limited += 1
            note = f"{S.STALE_PERIODS}: the return of ({p.start.isoformat()}, {p.end.isoformat()}] is LIMITED"
            parts.append(Part(ref, LIMITED, v.reason, (Cause(ref, LIMITED.value, v.reason, note, S.STALE_PERIODS),) + tuple(v.causes)))
        elif v.reason == S.STALE_DATA:
            # CP4M-1: a stale period is a period "LIMITED or stale" (Ruling 7.4): STALE_PERIODS is its detail too (Ruling 7.3 (1.3) item 4: a lower-level coded cause stays in the details)
            note = f"{S.STALE_PERIODS}: the return of ({p.start.isoformat()}, {p.end.isoformat()}] used a price or fixing one session or fixing stale"
            parts.append(Part(ref, AVAILABLE, S.STALE_DATA, (Cause(ref, AVAILABLE.value, S.STALE_DATA, note, S.STALE_PERIODS),) + tuple(v.causes)))
    return parts, limited


def rate_parts(rates: Sequence[PeriodRate]) -> List[Part]:
    """Ruling 4.4: each risk-free return that is not clean lists itself with its cause (`RISK_FREE_STALE`, `RISK_FREE_UNAVAILABLE`, `NO_RISK_FREE_SOURCE`, `CALENDAR_COVERAGE_GAP`)."""
    out: List[Part] = []
    for r in rates:
        v = r.valued
        if v.state is AVAILABLE and v.reason is None:
            continue
        out.append(Part(f"risk_free:{r.start.isoformat()}..{r.end.isoformat()}", v.state, v.reason, tuple(v.causes)))
    return out


def count_parts(registry: RiskRegistry, metric_id: str, frequency: str, n: int) -> List[Part]:
    """Ruling 7.1: the observation count against the entry's thresholds, in the same unit. No reason code on either state."""
    m = registry.minimum_observations(metric_id, frequency)
    ref = f"observations:{frequency}"
    if n < m.insufficient_below:
        return [S.count_part(ref, INSUFFICIENT, f"{S.INSUFFICIENT_OBSERVATIONS}: {n} observation(s), the floor is {m.insufficient_below} at {frequency}", S.INSUFFICIENT_OBSERVATIONS)]
    if n < m.available_from:
        return [S.count_part(ref, LIMITED, f"{S.OBSERVATIONS_BELOW_STANDARD}: {n} observation(s), the standard is {m.available_from} at {frequency}", S.OBSERVATIONS_BELOW_STANDARD)]
    return []


# --- the builder ------------------------------------------------------------------------------------------------------------------------------

def present_rational(value: Fraction) -> Decimal:
    shown = to_decimal_money(round_half_up(value, DIGITS), DIGITS)
    assert shown is not None  # a quantized rational is a terminating decimal
    return shown


class MetricBuilder:
    def __init__(self, declared: Declared, registry: RiskRegistry = REGISTRY, benchmark: Optional[BenchmarkRef] = None):
        self.declared = declared
        self.registry = registry
        self.benchmark = benchmark

    def thresholds(self, metric_id: str) -> Optional[Tuple[int, int]]:
        m = self.registry.minimum_observations(metric_id, self.declared.frequency)
        return None if (m.insufficient_below, m.available_from) == (1, 1) else (m.insufficient_below, m.available_from)

    def build(self, metric_id: str, parts: Sequence[Part], value: Optional[Value], *, stale_period_count: Optional[int] = None, drawdown: Optional[DrawdownFacts] = None,
              lineage: Sequence[Tuple[str, str]] = (), comparability: Optional[Comparability] = None, decomposition: Optional[Tuple[Tuple[str, object], ...]] = None) -> RiskMetric:
        """`value` is None (or ignored) when the combined state is INSUFFICIENT_DATA. `comparability` and `decomposition` (two-leg metrics, Rulings 8.3 and 6.9 (1.1)) are kept only with a value."""
        agg = S.combine(parts)
        d = self.declared
        common = dict(metric_id=metric_id, method_key=self.registry.entry_key(metric_id), frequency=d.frequency, requested_rule=d.rule, requested_months=d.months, requested_base=d.requested_base,
                      window=d.window, observation_count=d.n, thresholds=self.thresholds(metric_id), causes=agg.causes, details=S.details_of(agg.causes), benchmark=self.benchmark,
                      lineage=tuple(sorted(lineage)), synthetic=d.synthetic)
        stale = stale_period_count if stale_period_count else None
        if agg.state is INSUFFICIENT or value is None:
            if agg.state is not INSUFFICIENT:
                raise ValueError(f"{metric_id}: a value is required for state {agg.state.value}")
            # the count of LIMITED periods stays (Ruling 2.5, and the fixture P7-F1: a suppressed statistic still says how many of its periods were stale)
            return RiskMetric(result=S.metric_result(None, INSUFFICIENT, agg.reason), exact=None, exact_square=None, sign=None, stale_period_count=stale, drawdown=None, **common)
        if value.rational is not None:
            result = S.metric_result(present_rational(value.rational), agg.state, agg.reason)
            return RiskMetric(result=result, exact=value.rational, exact_square=None, sign=None, intermediates=tuple(sorted(value.intermediates)), stale_period_count=stale, drawdown=drawdown,
                              comparability=comparability, decomposition=decomposition, **common)
        assert value.radicand is not None
        root = sqrt_rounded(value.radicand, value.sign if value.radicand != 0 else 0)
        shown = to_decimal_money(root.value, DIGITS)
        assert shown is not None
        return RiskMetric(result=S.metric_result(shown, agg.state, agg.reason), exact=None, exact_square=value.radicand, sign=root.sign, intermediates=tuple(sorted(value.intermediates)),
                          stale_period_count=stale, drawdown=None, comparability=comparability, decomposition=decomposition, **common)

    def fault(self, metric_id: str, parts: Sequence[Part], note: str, identity: str) -> RiskMetric:
        """An identity that must hold exactly did not (Ruling 1.4): INSUFFICIENT_DATA + CALCULATION_ERROR, no number. The failure is recorded in lineage (`identity:<id>` FAIL). CP4F-9: the unverified values in `note`
        are NOT put in the result (a refused metric presents no number, and a cause note is read by the evidence view and the AI layer); the cause names the identity only."""
        del note
        cause = Cause("identity", INSUFFICIENT.value, S.CALCULATION_ERROR, f"{S.IDENTITY_FAILED}: {identity} did not hold", S.IDENTITY_FAILED)
        return self.build(metric_id, list(parts) + [Part("identity", INSUFFICIENT, S.CALCULATION_ERROR, (cause,))], None, lineage=[(f"identity:{identity}", FAIL)])


# --- the metrics ----------------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SingleInputs:
    """What the single-series metrics read: the window's series (None when refused, with the refusal) and the risk-free returns (None when none were asked for)."""

    series: Optional[ReturnSeries]
    refusal: Optional[SeriesRefusal]
    rates: Optional[Tuple[PeriodRate, ...]]
    rate_series_id: Optional[str] = None
    rate_probe: Optional[PeriodRate] = None  # a refused window has no grid dates to take rates at: the window-independent `NO_RISK_FREE_SOURCE`, if it holds (Ruling 7.3 (1.5))


#: `reconcile(start, end)` is the TWR of `(start, end]` computed by the TWR engine DIRECTLY (RD-1); the engine supplies it, a test may supply another to show the check bites
Reconcile = Callable[[datetime.date, datetime.date], Optional[Fraction]]


def _base_parts(registry: RiskRegistry, metric_id: str, inputs: SingleInputs, declared: Declared, with_rates: bool) -> Tuple[List[Part], int, bool]:
    """The window, series, rate and count parts of one metric, and whether every number it needs exists (no INSUFFICIENT part)."""
    if inputs.series is None:
        assert inputs.refusal is not None
        refused = [window_part(inputs.refusal)]
        if with_rates and inputs.rate_probe is not None:
            refused += rate_parts([inputs.rate_probe])
        return refused, 0, False
    parts, stale = series_parts(inputs.series)
    if with_rates:
        assert inputs.rates is not None and len(inputs.rates) == inputs.series.grid.observation_count
        parts += rate_parts(inputs.rates)
    assert declared.n is not None
    parts += count_parts(registry, metric_id, declared.frequency, declared.n)
    return parts, stale, all(p.state is not INSUFFICIENT for p in parts)


def _returns(series: ReturnSeries) -> List[Fraction]:
    out: List[Fraction] = []
    for p in series.periods:
        assert p.exact is not None
        out.append(p.exact)
    return out


def _excess(returns: Sequence[Fraction], rates: Sequence[PeriodRate]) -> List[Fraction]:
    out: List[Fraction] = []
    for r, rf in zip(returns, rates):
        assert rf.exact is not None
        out.append(r - rf.exact)
    return out


def single_series_metrics(inputs: SingleInputs, declared: Declared, wanted: Sequence[str], *, registry: RiskRegistry = REGISTRY, benchmark: Optional[BenchmarkRef] = None,
                          reconcile: Optional[Reconcile] = None) -> Tuple[RiskMetric, ...]:
    """The requested metrics among volatility, downside deviation, maximum drawdown, Sharpe and Sortino, in metric-id order."""
    builder = MetricBuilder(declared, registry, benchmark)
    A = periods_per_year(declared.frequency)
    out: List[RiskMetric] = []
    for metric_id in sorted(set(wanted)):
        if metric_id not in SINGLE_SERIES_METRICS:
            raise ValueError(f"{metric_id!r} is not a single-series metric")
        rated = metric_id in RATE_DEPENDENT
        parts, stale, ok = _base_parts(registry, metric_id, inputs, declared, rated)
        lineage = [] if not (rated and inputs.rate_series_id) else [("risk_free_series", inputs.rate_series_id)]
        if not ok:
            out.append(builder.build(metric_id, parts, None, stale_period_count=stale, lineage=lineage))
            continue
        assert inputs.series is not None
        r = _returns(inputs.series)
        n = len(r)
        if metric_id == DRAWDOWN:
            out.append(_drawdown(builder, parts, stale, inputs.series, r, reconcile))
        elif metric_id == VOLATILITY:
            out.append(builder.build(metric_id, parts, Value(radicand=stats.volatility_radicand(r, A), intermediates=(("n", Fraction(n)), ("mean_return", stats.mean(r)), ("sum_squared_deviations", stats.sum_squared_deviations(r)),
                                                                                                                       ("variance", stats.sample_variance(r)))),
                                     stale_period_count=stale))
        elif metric_id == DOWNSIDE:
            assert inputs.rates is not None
            d = _excess(r, inputs.rates)
            shortfall = stats.shortfall_square_sum(d)
            out.append(builder.build(metric_id, parts, Value(radicand=stats.downside_radicand(d, A), intermediates=(("n", Fraction(n)), ("mean_excess", stats.mean(d)), ("mean_risk_free", _rate_mean(inputs.rates)),
                                                                                                                     ("shortfall_sum", shortfall))),
                                     stale_period_count=stale, lineage=lineage))
        else:  # Sharpe and Sortino
            assert inputs.rates is not None
            d = _excess(r, inputs.rates)
            variance = stats.sample_variance(r)
            dbar = stats.mean(d)
            shortfall = stats.shortfall_square_sum(d)
            # Ruling 9.4: the exact sums and means, so RQ-1 can be checked from the result without a re-run (and a later alpha has the risk-free mean Ruling 6.8 shows with it)
            inter = (("n", Fraction(n)), ("mean_excess", dbar), ("mean_return", stats.mean(r)), ("mean_risk_free", _rate_mean(inputs.rates)), ("shortfall_sum", shortfall), ("variance", variance))
            degenerate: List[Part] = []
            if variance == 0:
                degenerate.append(S.count_part("degenerate", INSUFFICIENT, f"{S.ZERO_VOLATILITY}: the portfolio's returns did not vary, a ratio of excess return to risk is undefined", S.ZERO_VOLATILITY))
            if metric_id == SORTINO and shortfall == 0:
                degenerate.append(S.count_part("degenerate", INSUFFICIENT, f"{S.NO_DOWNSIDE_OBSERVATIONS}: no period fell below the risk-free rate", S.NO_DOWNSIDE_OBSERVATIONS))
            if degenerate:
                out.append(builder.build(metric_id, parts + degenerate, None, stale_period_count=stale, lineage=lineage))
            elif metric_id == SHARPE:
                q = stats.sharpe_radicand(dbar, variance, A)
                out.append(_checked_ratio(builder, metric_id, parts, stale, lineage, q, dbar, lambda: q * variance == A * dbar * dbar, "Sharpe^2 s^2(r) = A dbar^2", inter))
            else:
                q = stats.sortino_radicand(dbar, shortfall, n, A)
                out.append(_checked_ratio(builder, metric_id, parts, stale, lineage, q, dbar, lambda: q * shortfall == A * dbar * dbar * n, "Sortino^2 sum min(0,d)^2 = A dbar^2 n", inter))
    return tuple(out)


def _rate_mean(rates: Sequence[PeriodRate]) -> Fraction:
    """The mean of the window's periodic risk-free returns (Ruling 6.8 shows it with a Jensen alpha); every period has one when a number exists."""
    values = []
    for rf in rates:
        assert rf.exact is not None
        values.append(rf.exact)
    return stats.mean(values)


def _checked_ratio(builder: MetricBuilder, metric_id: str, parts: Sequence[Part], stale: int, lineage: Sequence[Tuple[str, str]], q: Fraction, dbar: Fraction, holds: Callable[[], bool],
                   label: str, intermediates: Tuple[Tuple[str, Fraction], ...] = ()) -> RiskMetric:
    """RQ-1 (Ruling 6.13) on the exact radicand: the ratio's square times its denominator is `A dbar^2` (times n), with no rounding."""
    if not holds():
        return builder.fault(metric_id, parts, f"RQ-1 failed: {label}", "RQ-1")
    return builder.build(metric_id, parts, Value(radicand=q, sign=stats.sign_of(dbar), intermediates=intermediates), stale_period_count=stale, lineage=list(lineage) + [("identity:RQ-1", PASS)])


def _drawdown(builder: MetricBuilder, parts: Sequence[Part], stale: int, series: ReturnSeries, returns: Sequence[Fraction], reconcile: Optional[Reconcile]) -> RiskMetric:
    dd = stats.max_drawdown(returns)
    dates = series.boundaries
    lineage: List[Tuple[str, str]] = [("peak_rule", stats.PEAK_RULE), ("base_date", dates[0].isoformat())]
    # RD-3: a single period's fall is a drawdown
    if dd.value > min(stats.ZERO, min(returns)):
        return builder.fault(DRAWDOWN, parts, f"RD-3 failed: MDD {dd.value} is above the worst single period", RD3)
    lineage.append(("identity:RD-3", PASS))
    if dd.trough is None:
        facts = DrawdownFacts(None, None, None, stats.PEAK_RULE)
    else:
        assert dd.peak is not None
        peak_date, trough_date = dates[dd.peak], dates[dd.trough]
        facts = DrawdownFacts(peak_date, trough_date, None if dd.recovery is None else dates[dd.recovery], stats.PEAK_RULE)
        if reconcile is not None:  # RD-1: 1 + MDD = 1 + TWR(peak, trough] from the TWR engine, over a window the series was not asked for
            twr = reconcile(peak_date, trough_date)
            if twr is None or stats.ONE + dd.value != stats.ONE + twr:
                return builder.fault(DRAWDOWN, parts, f"RD-1 failed: MDD {dd.value} against the TWR of ({peak_date.isoformat()}, {trough_date.isoformat()}] = {twr}", RD1)
            lineage.append(("identity:RD-1", PASS))
    inter: Tuple[Tuple[str, Fraction], ...] = (("n", Fraction(len(returns))),)  # Ruling 9.4 (1.4): n, and W at the peak and at the trough (the dates are the facts)
    if dd.trough is not None:
        assert dd.peak is not None
        inter += (("wealth_peak", dd.wealth[dd.peak]), ("wealth_trough", dd.wealth[dd.trough]))
    return builder.build(DRAWDOWN, parts, Value(rational=dd.value, intermediates=inter), stale_period_count=stale, drawdown=facts, lineage=lineage)
