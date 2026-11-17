"""The periodic return series: the spine of the CP4 risk and benchmark engine (`risk/1.0` Rulings 2.1 to 2.6; tech plan 17.3, 17.15).

A risk return series is a series of period TWRs from the SAME engine that computes the window TWR (`performance.returns.twr_segments`: segment form, flows neutralised, FX at the flow-date and
valuation-date fixings, the same states and freshness). It is NOT a second return definition (PD-0014 section 2.5). For grid points `g_0 < g_1 < ... < g_n` the period return of `(g_{k-1}, g_k]` is
`twr_segments(g_{k-1}, g_k, flows of that period, valuation, conventions)`; a statistic reads these, never recomputes them.

WHAT IS RULED (`risk/1.0`), AND WHERE:
- the grid (`performance.grid`: weekdays, Fridays, month-ends) and the window with its stubs (`g_0` the first grid date on or after `B`, `g_n` the last on or before `E`; the stubs are excluded and declared);
- a requested window is REFUSED when it cannot be served, never shortened (Ruling 7.2): there is no clipping. `MAX_AVAILABLE` is a SEPARATE request (`MaxAvailable`): the longest window ending at `g_n` in which every
  period is computable, labelled with why it starts where it does (Ruling 2.3);
- NO merging, dropping, filling or re-gridding of a period (Ruling 2.5): an insufficient period stays insufficient;
- a period with no capital on EVERY day is `INSUFFICIENT_DATA`, no reason, detail `ZERO_CAPITAL_PERIOD` (Ruling 2.4); a period with capital for part of its days is an ordinary observation. Exactly: a flow-free
  period whose single run is `0/0` (`ZERO_CAPITAL_RUN`). A period that holds a flow day cannot be entirely empty (a flow needs a positive base or a positive numerator), so a period that STARTS at value 0 and receives
  capital at the start of its first day is a normal observation (Ruling 2.4).

PRIMITIVE: the boundary valuations (`ReturnSeries.boundary_values`).

IDENTITIES (a failure is an engine fault and raises; it is never a metric):
- I-10 = RS-1 (Ruling 2.1): over every maximal run of consecutive exact periods `(g_i, g_j]`, `product(1 + r_k) = 1 + TWR(g_i, g_j]` EXACTLY (segment TWR telescopes);
- I-11 (coverage): the dates the builder asked the valuation for are EXACTLY the dates the periods require (the grid points, and `D - 1` and `D` for every flow day `D` inside a period): no hidden read.

Pure: no clock, no randomness, no float, no I/O.
"""

from __future__ import annotations

import bisect
import datetime
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Set, Tuple

from marketdata.canonical import canonical_json, sha256_hex
from performance.conventions import PerformanceConventionSet
from performance.flows import ValuedFlow
from performance.grid import (  # noqa: F401  (re-exported: the series API)
    GRID_RULE_ID,
    NO_FULL_PERIOD,
    Frequency,
    SeriesWindow,
    WeekdayFridayMonthEndGrid,
    effective_window,
)
from performance.manifest import ComputationManifest
from performance.results import EMPTY_FRESHNESS, Cause, FreshnessVector, WindowUsed
from performance.returns import ZERO_CAPITAL_RUN, twr_segments
from performance.states import STALE_DATA, Valued
from product_contract.vocabulary import SufficiencyState

SERIES_SCHEMA = "finweb.return_series/2"
ONE = Fraction(1)
ONE_DAY = datetime.timedelta(days=1)
PASS, FAIL, NOT_COMPUTABLE, NOT_RUN = "PASS", "FAIL", "NOT_COMPUTABLE", "NOT_RUN"
ZERO_CAPITAL_PERIOD = "ZERO_CAPITAL_PERIOD"
MAX_AVAILABLE = "MAX_AVAILABLE"
INCEPTION = "INCEPTION"
AFTER_INSUFFICIENT_PERIOD = "AFTER_INSUFFICIENT_PERIOD"


@dataclass(frozen=True)
class MaxAvailable:
    """The `MAX_AVAILABLE` request (Ruling 2.3): start from the since-inception grid points; if any period is INSUFFICIENT_DATA the base becomes the end of the LAST such period. Never an answer to a
    TRAILING_MONTHS request: it is its own request, answered over its own declared window."""


class BoundaryRuleError(ValueError):
    """The injected rule broke its contract (not strictly increasing, or a date outside the requested window `[B, E]`). An engine-side fault, never a data state."""


class SeriesIdentityError(RuntimeError):
    """I-10 or I-11 failed: the builder and the segment TWR disagree. An engine fault, raised loudly, never turned into a number."""


class BoundaryRule(Protocol):
    """The grid points of a series: every grid date in the REQUESTED window `[B, E]` (`window.start`, `window.end`), strictly increasing. `risk/1.0`'s rule is `performance.grid.WeekdayFridayMonthEndGrid`.
    The rule is part of the question: its id goes into the manifest."""

    rule_id: str

    def boundaries(self, frequency: Frequency, window: WindowUsed) -> Sequence[datetime.date]: ...


@dataclass(frozen=True)
class ExplicitBoundaries:
    """Grid points the CALLER chose. NOT a convention: tests, fixtures and the cost tool use it to sample a series on dates of their own choosing; the dates must lie in `[B, E]`."""

    dates: Tuple[datetime.date, ...]
    rule_id: str = "explicit-boundaries/caller-supplied"

    def boundaries(self, frequency: Frequency, window: WindowUsed) -> Sequence[datetime.date]:
        return self.dates


def validate_boundaries(window: WindowUsed, dates: Sequence[datetime.date]) -> Tuple[datetime.date, ...]:
    """The rule's contract: strictly increasing, and inside the requested window `[B, E]`. Fewer than two dates is NOT a violation: it is `NO_FULL_PERIOD`, a data state the caller reports."""
    out = tuple(dates)
    if any(not b < c for b, c in zip(out, out[1:])):
        raise BoundaryRuleError("the grid points must be strictly increasing")
    if out and (out[0] < window.start or out[-1] > window.end):
        raise BoundaryRuleError(f"the grid points must lie in the requested window [{window.start.isoformat()}, {window.end.isoformat()}], not {out[0].isoformat()} to {out[-1].isoformat()}")
    return out


# --- the series ---------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodReturn:
    """The return of `(start, end]`: a `Valued` (state, reason, exact value, causes, freshness) as `twr_segments` gives it, except that a period with no capital on every day is INSUFFICIENT_DATA with the
    detail `ZERO_CAPITAL_PERIOD` (Ruling 2.4). `zero_capital` says so."""

    start: datetime.date
    end: datetime.date
    valued: Valued
    details: Tuple[str, ...]
    flow_days: int
    zero_capital: bool

    @property
    def exact(self) -> Optional[Fraction]:
        return self.valued.exact

    def to_obj(self) -> Dict[str, Any]:
        v = self.valued
        return {"start": self.start, "end": self.end, "state": v.state.value, "reason": v.reason, "exact": v.exact, "details": list(self.details), "flow_days": self.flow_days,
                "zero_capital": self.zero_capital, "causes": [c.to_obj() for c in v.causes], "freshness": v.freshness.to_obj()}


@dataclass(frozen=True)
class SeriesAssessment:
    """Counts by state over the periods, kept so a statistic reads them and never re-derives a state. `available_stale` is AVAILABLE + STALE_DATA (one missed session or fixing)."""

    periods: int
    available: int
    available_stale: int
    limited: int
    insufficient: int
    zero_capital: int
    freshness: FreshnessVector
    first_insufficient_end: Optional[datetime.date]
    last_insufficient_end: Optional[datetime.date]

    def to_obj(self) -> Dict[str, Any]:
        return {"periods": self.periods, "available": self.available, "available_stale": self.available_stale, "limited": self.limited, "insufficient": self.insufficient,
                "zero_capital": self.zero_capital, "freshness": self.freshness.to_obj(), "first_insufficient_end": self.first_insufficient_end,
                "last_insufficient_end": self.last_insufficient_end}


def assess(periods: Sequence[PeriodReturn]) -> SeriesAssessment:
    available = stale = limited = insufficient = zero = 0
    fresh = EMPTY_FRESHNESS
    failed: List[datetime.date] = []
    for p in periods:
        v = p.valued
        fresh = fresh.union(v.freshness)
        zero += 1 if p.zero_capital else 0
        if v.state is SufficiencyState.INSUFFICIENT_DATA:
            insufficient += 1
            failed.append(p.end)
        elif v.state is SufficiencyState.LIMITED:
            limited += 1
        elif v.reason == STALE_DATA:
            stale += 1
        else:
            available += 1
    return SeriesAssessment(len(periods), available, stale, limited, insufficient, zero, fresh, failed[0] if failed else None, failed[-1] if failed else None)


@dataclass(frozen=True)
class ReturnSeries:
    window: WindowUsed                                  # the EFFECTIVE window: start g_0, end g_n; the requested start and months are kept on it
    grid: SeriesWindow                                  # the declaration of Ruling 2.3 (request, effective window, n, stubs, MAX_AVAILABLE start)
    frequency: str
    rule_id: str
    boundaries: Tuple[datetime.date, ...]               # g_0 .. g_n
    boundary_values: Tuple[Tuple[datetime.date, Valued], ...]  # the primitive: the total at each grid point
    periods: Tuple[PeriodReturn, ...]
    assessment: SeriesAssessment
    valuation_dates_read: Tuple[datetime.date, ...]     # every date the builder asked the valuation for (before any MAX_AVAILABLE truncation)
    required_dates: Tuple[datetime.date, ...]           # every date the periods require (I-11 says the two are equal)

    def to_obj(self) -> Dict[str, Any]:
        return {"schema": SERIES_SCHEMA, "window": self.window.to_obj(), "grid": self.grid.to_obj(), "frequency": self.frequency, "boundary_rule": self.rule_id, "boundaries": list(self.boundaries),
                "boundary_values": [{"date": d, "state": v.state.value, "reason": v.reason, "exact": v.exact} for d, v in self.boundary_values],
                "periods": [p.to_obj() for p in self.periods], "assessment": self.assessment.to_obj()}

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json(self.to_obj()).encode("utf-8"))


def boundaries_digest(boundaries: Sequence[datetime.date]) -> str:
    return sha256_hex(canonical_json([d for d in boundaries]).encode("utf-8"))


def _flows_by_date(flows: Sequence[ValuedFlow]) -> Tuple[List[datetime.date], List[ValuedFlow]]:
    ordered = sorted(flows, key=lambda f: f.event.event_date)  # stable: the order within a day never reaches a result (sums)
    return [f.event.event_date for f in ordered], ordered


def _slice(dates: List[datetime.date], ordered: List[ValuedFlow], start: datetime.date, end: datetime.date) -> List[ValuedFlow]:
    return ordered[bisect.bisect_right(dates, start):bisect.bisect_right(dates, end)]


def required_dates_of(start: datetime.date, end: datetime.date, flow_days: Sequence[datetime.date]) -> Set[datetime.date]:
    """The valuation dates `twr_segments` needs for `(start, end]` (performance/1.0 Ruling 5.2): the two ends, and for every flow day `D` both `D - 1` and `D`."""
    need = {start, end}
    for d in flow_days:
        need.add(d - ONE_DAY)
        need.add(d)
    return need


def _zero_capital_period(start: datetime.date, end: datetime.date, valued: Valued) -> Valued:
    cause = Cause(f"period:{start.isoformat()}..{end.isoformat()}", SufficiencyState.INSUFFICIENT_DATA.value, None,
                  f"{ZERO_CAPITAL_PERIOD}: the portfolio held no capital on any day of ({start.isoformat()}, {end.isoformat()}]", ZERO_CAPITAL_PERIOD)
    return Valued(SufficiencyState.INSUFFICIENT_DATA, None, None, tuple(sorted(set(valued.causes + (cause,)))), valued.freshness)


def build_series(
    declared: SeriesWindow, window: WindowUsed, dates: Tuple[datetime.date, ...], rule_id: str, flows: Sequence[ValuedFlow],
    valuation: Callable[[datetime.date], Valued], conventions: PerformanceConventionSet,
) -> ReturnSeries:
    """The series on the grid points `dates` (`g_0 ... g_n`, at least two). `declared` is the window declaration for them (`performance.grid.effective_window`); `window` the requested window (its rule, months and
    `B` go on the effective window). `valuation(day)` is the portfolio total `TV_R(day)` as a `Valued` (the engine's cached `_Run.total`); every period is `twr_segments` over its own slice of `flows`."""
    read: Set[datetime.date] = set()

    def recorded(day: datetime.date) -> Valued:
        read.add(day)
        return valuation(day)

    fdates, ordered = _flows_by_date(flows)
    required: Set[datetime.date] = set()
    periods: List[PeriodReturn] = []
    for a, b in zip(dates, dates[1:]):
        part = _slice(fdates, ordered, a, b)
        flow_days = sorted({f.event.event_date for f in part})
        required |= required_dates_of(a, b, flow_days)
        outcome = twr_segments(a, b, part, recorded, conventions)
        zero = not flow_days and ZERO_CAPITAL_RUN in outcome.details and outcome.valued.state is not SufficiencyState.INSUFFICIENT_DATA
        valued = _zero_capital_period(a, b, outcome.valued) if zero else outcome.valued
        details = tuple(sorted(set(outcome.details) | ({ZERO_CAPITAL_PERIOD} if zero else set())))
        periods.append(PeriodReturn(a, b, valued, details, len(flow_days), zero))
    values = tuple((d, recorded(d)) for d in dates)  # a grid point is always a required date, so this adds no read
    used = replace(window, start=dates[0], end=dates[-1], frequency=declared.frequency, rule=declared.rule, months=declared.months, since_snapshot=window.since_snapshot,
                   requested_months=declared.months, requested_start=declared.requested_base)
    return ReturnSeries(used, declared, declared.frequency, rule_id, dates, values, tuple(periods), assess(periods), tuple(sorted(read)), tuple(sorted(required)))


def apply_max_available(series: ReturnSeries) -> Tuple[Optional[ReturnSeries], Optional[Cause]]:
    """Ruling 2.3 `MAX_AVAILABLE`: from the since-inception series, if any period is INSUFFICIENT_DATA let `j` be the LAST such period; the base becomes `g_j` and the observations are the periods AFTER it.
    The declared window keeps `B` (so the start stub is `g_0 - B` for the new `g_0`) and says why it starts where it does: `INCEPTION`, or `AFTER_INSUFFICIENT_PERIOD` with that period's end and cause.
    Returns `(series, None)`, or `(None, cause)` when no full period follows the last insufficient one (`NO_FULL_PERIOD`)."""
    last = None
    for index, p in enumerate(series.periods):
        if p.valued.state is SufficiencyState.INSUFFICIENT_DATA:
            last = index
    declared = replace(series.grid, rule=MAX_AVAILABLE, months=None)
    if last is None:
        kept = replace(series, grid=replace(declared, max_available_start=INCEPTION), window=replace(series.window, rule=MAX_AVAILABLE, months=None, requested_months=None))
        return kept, None
    bad = series.periods[last]
    start_index = last + 1  # the grid point g_j is boundaries[last + 1]
    dates = series.boundaries[start_index:]
    why = next((c.detail or c.ref for c in bad.valued.causes), "")
    if len(dates) < 2:
        return None, Cause("window", SufficiencyState.INSUFFICIENT_DATA.value, None, f"{NO_FULL_PERIOD}: no full period follows the last insufficient period ending {bad.end.isoformat()}", NO_FULL_PERIOD)
    periods = series.periods[start_index:]
    declared = replace(declared, base_date=dates[0], last_period_end=dates[-1], observation_count=len(dates) - 1, stub_start_days=(dates[0] - declared.requested_base).days,
                       max_available_start=AFTER_INSUFFICIENT_PERIOD, max_available_after=bad.end, max_available_cause=why)
    window = replace(series.window, start=dates[0], end=dates[-1], rule=MAX_AVAILABLE, months=None, requested_months=None)
    return replace(series, window=window, grid=declared, boundaries=dates, boundary_values=series.boundary_values[start_index:], periods=periods, assessment=assess(periods)), None


# --- identities -----------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RunCheck:
    start: datetime.date
    end: datetime.date
    status: str


@dataclass(frozen=True)
class LinkReport:
    """I-10. `status`: PASS (every checkable run links exactly, at least one checked), FAIL (some run differs), NOT_COMPUTABLE (no run could be checked: no exact period, or no exact whole-run TWR)."""

    status: str
    runs: Tuple[RunCheck, ...]


def link_identity(series: ReturnSeries, flows: Sequence[ValuedFlow], valuation: Callable[[datetime.date], Valued], conventions: PerformanceConventionSet) -> LinkReport:
    """I-10 = RS-1, over every maximal run of consecutive periods that each have an exact return. The whole-run TWR is computed by `twr_segments` over the run's own window; it needs no date outside the
    union of the periods' required dates, so it reads nothing new."""
    dates, ordered = _flows_by_date(flows)
    runs: List[RunCheck] = []
    i, n = 0, len(series.periods)
    while i < n:
        if series.periods[i].exact is None:
            i += 1
            continue
        j = i
        product = ONE
        while j < n and series.periods[j].exact is not None:
            exact = series.periods[j].exact
            assert exact is not None
            product *= ONE + exact
            j += 1
        start, end = series.periods[i].start, series.periods[j - 1].end
        whole = twr_segments(start, end, _slice(dates, ordered, start, end), valuation, conventions).valued.exact
        status = NOT_COMPUTABLE if whole is None else (PASS if product == ONE + whole else FAIL)
        runs.append(RunCheck(start, end, status))
        i = j
    statuses = {r.status for r in runs}
    if FAIL in statuses:
        status = FAIL
    elif PASS in statuses:
        status = PASS
    else:
        status = NOT_COMPUTABLE
    return LinkReport(status, tuple(runs))


def coverage_identity(series: ReturnSeries) -> str:
    """I-11: the dates read are exactly the dates required."""
    return PASS if series.valuation_dates_read == series.required_dates else FAIL


# --- the result -----------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SeriesRefusal:
    """No series: the window could not be resolved or holds no full period. The cause carries the detail (`WINDOW_BEFORE_INCEPTION`, `WINDOW_BEFORE_SNAPSHOT`, `NO_FULL_PERIOD`, ...) and `reason` the reason-code text
    (None except `NOT_RECONSTRUCTABLE` before a snapshot)."""

    reason: Optional[str]
    cause: Cause


@dataclass(frozen=True)
class SeriesResult:
    """What `performance.engine.compute_return_series` returns: the series (or the refusal), the manifest of the QUESTION (the CP3 `ComputationManifest` of the window, with the request, the frequency, the grid rule
    id, the grid points' digest and the MAX_AVAILABLE start pinned in `numerics`, so all of them are part of `manifest_id`), the series digest (the ANSWER's identity) and the identity outcomes."""

    manifest: ComputationManifest
    series: Optional[ReturnSeries]
    refusal: Optional[SeriesRefusal]
    series_digest: str
    identities: Tuple[Tuple[str, str], ...]

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {"manifest_id": self.manifest.manifest_id, "manifest": self.manifest.to_obj(), "series_digest": self.series_digest,
                "series": None if self.series is None else self.series.to_obj(),
                "refusal": None if self.refusal is None else {"reason": self.refusal.reason, "cause": self.refusal.cause.to_obj()},
                "identities": [list(p) for p in self.identities]}

    def canonical_json(self) -> str:
        return canonical_json(self.to_canonical_dict())
