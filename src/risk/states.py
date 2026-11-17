"""State propagation for the risk engine: the ONLY risk module that names a reason code (tech plan 17.7.1, 17.16; `risk/1.1` Rulings 2.5, 7.3, 7.4, 7.6).

A metric's state is the worst of its parts (Ruling 7.3): the window, the series' periods, the risk-free returns (for a metric that uses the rate), the benchmark levels and translations (for a benchmark
metric), the observation count and the degenerate cases. The single reason code is `performance` Ruling 1.5 UNCHANGED, with its (1.1) clause: only causes at the result's OWN level compete. So:

- an INSUFFICIENT_DATA result takes its code from the INSUFFICIENT_DATA parts and causes; a result made so by the count alone has NO code, even if a LIMITED stale input carries `STALE_DATA`;
- a LIMITED result takes its code from the LIMITED parts and causes, and has none when only the count made it LIMITED (`OBSERVATIONS_BELOW_STANDARD` carries no code). This is where it differs from
  `performance.states.PerformanceAggregation`, which gives every LIMITED result `STALE_DATA`: a count is not staleness;
- an AVAILABLE result carries `STALE_DATA` (one missed publication or session) or nothing.

Every cause stays in lineage whether or not it set the reason (Ruling 7.3). No reason code is requested (Ruling 7.6): a condition without a code is a DETAIL, named below (Ruling 7.4; a rename is a
convention change).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Sequence

from marketdata.states import LIMITED_FROM, NO_VALUE_FROM, InputState
from performance.results import Aggregate, Cause, Part, sorted_causes
from performance.states import pick_reason
from product_contract.metric_state import MetricResult
from product_contract.vocabulary import ReasonCode, SufficiencyState

# reason-code TEXT (the performance modules pass codes around as text)
STALE_DATA = ReasonCode.STALE_DATA.value
MISSING_BENCHMARK = ReasonCode.MISSING_BENCHMARK.value
SOURCE_CONFLICT = ReasonCode.SOURCE_CONFLICT.value
CALCULATION_ERROR = ReasonCode.CALCULATION_ERROR.value

AVAILABLE, LIMITED, INSUFFICIENT = SufficiencyState.AVAILABLE, SufficiencyState.LIMITED, SufficiencyState.INSUFFICIENT_DATA

# the detail names of Ruling 7.4
INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
OBSERVATIONS_BELOW_STANDARD = "OBSERVATIONS_BELOW_STANDARD"
NO_FULL_PERIOD = "NO_FULL_PERIOD"
WINDOW_BEFORE_INCEPTION = "WINDOW_BEFORE_INCEPTION"
WINDOW_BEFORE_SNAPSHOT = "WINDOW_BEFORE_SNAPSHOT"
PERIOD_INSUFFICIENT = "PERIOD_INSUFFICIENT"
STALE_PERIODS = "STALE_PERIODS"
ZERO_CAPITAL_PERIOD = "ZERO_CAPITAL_PERIOD"
RISK_FREE_STALE = "RISK_FREE_STALE"
RISK_FREE_UNAVAILABLE = "RISK_FREE_UNAVAILABLE"
NO_RISK_FREE_SOURCE = "NO_RISK_FREE_SOURCE"
NO_BENCHMARK_SELECTED = "NO_BENCHMARK_SELECTED"
BENCHMARK_SERIES_UNAVAILABLE = "BENCHMARK_SERIES_UNAVAILABLE"
BENCHMARK_NOT_TOTAL_RETURN = "BENCHMARK_NOT_TOTAL_RETURN"
BENCHMARK_NOT_COVERING_WINDOW = "BENCHMARK_NOT_COVERING_WINDOW"
BENCHMARK_STALE = "BENCHMARK_STALE"
BENCHMARK_SOURCE_CONFLICT = "BENCHMARK_SOURCE_CONFLICT"  # risk/1.2 Ruling 7.4: two sources disagree on the level used at a grid date, or an ETF proxy's corporate action is in DISAGREEMENT (reason SOURCE_CONFLICT; not built yet)
ZERO_VOLATILITY = "ZERO_VOLATILITY"
NO_DOWNSIDE_OBSERVATIONS = "NO_DOWNSIDE_OBSERVATIONS"
ZERO_BENCHMARK_VARIANCE = "ZERO_BENCHMARK_VARIANCE"
ZERO_PORTFOLIO_VARIANCE = "ZERO_PORTFOLIO_VARIANCE"
ZERO_TRACKING_ERROR = "ZERO_TRACKING_ERROR"
CALENDAR_COVERAGE_GAP = "CALENDAR_COVERAGE_GAP"
IDENTITY_FAILED = "IDENTITY_FAILED"  # an engine fault (RD-1, RD-3, RQ-1 failed at runtime): `CALCULATION_ERROR`, never a number

RISK_DETAIL_NAMES = frozenset({
    INSUFFICIENT_OBSERVATIONS, OBSERVATIONS_BELOW_STANDARD, NO_FULL_PERIOD, WINDOW_BEFORE_INCEPTION, WINDOW_BEFORE_SNAPSHOT, PERIOD_INSUFFICIENT, STALE_PERIODS, ZERO_CAPITAL_PERIOD, RISK_FREE_STALE,
    RISK_FREE_UNAVAILABLE, NO_RISK_FREE_SOURCE, NO_BENCHMARK_SELECTED, BENCHMARK_SERIES_UNAVAILABLE, BENCHMARK_NOT_TOTAL_RETURN, BENCHMARK_NOT_COVERING_WINDOW, BENCHMARK_STALE, BENCHMARK_SOURCE_CONFLICT, ZERO_VOLATILITY,
    NO_DOWNSIDE_OBSERVATIONS, ZERO_BENCHMARK_VARIANCE, ZERO_PORTFOLIO_VARIANCE, ZERO_TRACKING_ERROR, CALENDAR_COVERAGE_GAP,
})
"""The detail names of Ruling 7.4 (the fixtures' `details_include` is asserted restricted to these)."""


def fx_state_by_count(missed: int) -> InputState:
    """The FX count rule of `market-data` Ruling 1.6 for a count the benchmark leg adjusted (Current mode: a fixing not yet due is not missed, Ruling 5.8 item 5): 0 AVAILABLE, 1 AVAILABLE + STALE_DATA, 2 to 4
    LIMITED + STALE_DATA, 5 or more withheld (`MISSING_FX_HISTORY`)."""
    if missed <= 0:
        return InputState(AVAILABLE, None)
    if missed < LIMITED_FROM:
        return InputState(AVAILABLE, ReasonCode.STALE_DATA, f"{missed} fixing(s) missed")
    if missed < NO_VALUE_FROM:
        return InputState(LIMITED, ReasonCode.STALE_DATA, f"{missed} fixings missed")
    return InputState(INSUFFICIENT, ReasonCode.MISSING_FX_HISTORY, f"{missed} fixings missed: the rate is withheld (Ruling 1.6)")


def combine(parts: Sequence[Part]) -> Aggregate:
    """Ruling 7.3 over the parts of one metric: the worst state, the single reason from the causes at that state's own level, every cause kept."""
    causes = tuple(c for p in parts for c in p.causes)
    if any(p.state is INSUFFICIENT for p in parts):
        state = INSUFFICIENT
    elif any(p.state is LIMITED for p in parts):
        state = LIMITED
    else:
        state = AVAILABLE
    level = [p.reason for p in parts if p.state is state] + [c.reason for c in causes if c.state == state.value]
    reason = pick_reason(level)
    if state is AVAILABLE and reason != STALE_DATA:
        reason = None  # an AVAILABLE result carries only STALE_DATA (PD-0006)
    return Aggregate(state, reason, sorted_causes(causes))


def count_cause(ref: str, state: SufficiencyState, note: str, detail: str) -> Cause:
    """A cause with no reason code (the observation count, the degenerate cases, a window refusal): the state is set, the code stays none (Ruling 7.6)."""
    return Cause(ref, state.value, None, note, detail)


def count_part(ref: str, state: SufficiencyState, note: str, detail: str) -> Part:
    return Part(ref, state, None, (count_cause(ref, state, note, detail),))


def details_of(causes: Sequence[Cause]) -> tuple:
    return tuple(sorted({c.detail for c in causes if c.detail}))


def reason_enum(text: Optional[str]) -> Optional[ReasonCode]:
    return None if text is None else ReasonCode(text)


def metric_result(value: Optional[Decimal], state: SufficiencyState, reason: Optional[str]) -> MetricResult:
    """The product's envelope (PD-0025): a value iff the state is not INSUFFICIENT_DATA; the coupling rules of PD-0006 are its own."""
    return MetricResult(value, state, reason_enum(reason))
