"""State propagation for the performance engine: the ONLY performance module that names a reason code (tech plan 16.1).

- `part_from_*`, `insufficient_part` turn the CP2 input states (`marketdata.states`) and CP1 replay results into `Part`s with `Cause`s.
- `PerformanceAggregation` is `performance/1.1` Rulings 1.4 and 1.5 (the placeholder worst-of rule of CP3a is replaced):
  1. any INSUFFICIENT_DATA part makes the whole INSUFFICIENT_DATA, with no value;
  2. otherwise any LIMITED part makes it LIMITED (+ STALE_DATA: within valuation only 2 to 4 stale sessions or fixings is LIMITED);
  3. otherwise AVAILABLE, and AVAILABLE + STALE_DATA if any part carries STALE_DATA (one missed session or fixing);
  the single reason code is the first PRESENT in the Ruling 1.5 order, over EVERY cause of every part; every cause stays in lineage.
- `build_metric` is the single place a `ComputedMetric` is made from a valued state, via `numerics.present`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Optional, Sequence, Tuple

from domain.currency import CurrencyCode
from marketdata.states import InputState
from performance.numerics import IRRATIONAL_WIDTH, PRESENTATION_TIE, PresentStatus, RoundingPoint, RoundingRule, present
from performance.registry import METRIC_IDS
from performance.results import (
    EMPTY_FRESHNESS,
    Aggregate,
    Cause,
    ComputedMetric,
    Excluded,
    FreshnessVector,
    Part,
    RATIONAL,
    WindowUsed,
    sorted_causes,
)
from product_contract.metric_state import MetricResult
from product_contract.vocabulary import ReasonCode, SufficiencyState

# Ruling 1.5 (performance/1.2), highest first (11 is "none": a cause with no code). performance/1.2 places MISSING_BENCHMARK 7th, after UNSUPPORTED_ASSET and
# before MISSING_COST_BASIS (it is not emitted by CP3).
REASON_PRIORITY: Tuple[ReasonCode, ...] = (
    ReasonCode.CALCULATION_ERROR, ReasonCode.LEDGER_INCONSISTENT, ReasonCode.NOT_RECONSTRUCTABLE,
    ReasonCode.SOURCE_CONFLICT, ReasonCode.UNRESOLVED_CONVENTION, ReasonCode.UNSUPPORTED_ASSET,
    ReasonCode.MISSING_BENCHMARK, ReasonCode.MISSING_COST_BASIS, ReasonCode.MISSING_PRICE_HISTORY,
    ReasonCode.MISSING_FX_HISTORY, ReasonCode.STALE_DATA,
)

MISSING_COST_BASIS = ReasonCode.MISSING_COST_BASIS.value
UNSUPPORTED_ASSET = ReasonCode.UNSUPPORTED_ASSET.value
LEDGER_INCONSISTENT = ReasonCode.LEDGER_INCONSISTENT.value
NOT_RECONSTRUCTABLE = ReasonCode.NOT_RECONSTRUCTABLE.value
UNRESOLVED_CONVENTION = ReasonCode.UNRESOLVED_CONVENTION.value
CALCULATION_ERROR = ReasonCode.CALCULATION_ERROR.value
STALE_DATA = ReasonCode.STALE_DATA.value
SOURCE_CONFLICT = ReasonCode.SOURCE_CONFLICT.value
MISSING_FX_HISTORY = ReasonCode.MISSING_FX_HISTORY.value
MISSING_PRICE_HISTORY = ReasonCode.MISSING_PRICE_HISTORY.value


def reason_enum(text: Optional[str]) -> Optional[ReasonCode]:
    return None if text is None else ReasonCode(text)


def part_from_input(ref: str, state: InputState) -> Part:
    reason = None if state.reason is None else state.reason.value
    clean = state.state is SufficiencyState.AVAILABLE and reason is None
    causes = () if clean else (Cause(ref, state.state.value, reason, state.note),)
    return Part(ref, state.state, reason, causes)


def part_from_metric(ref: str, result: MetricResult, details: Sequence[str] = ()) -> Part:
    """A CP1 replay value (a quantity or a cash balance) as a part."""
    reason = None if result.reason_code is None else result.reason_code.value
    if result.sufficiency_state is SufficiencyState.AVAILABLE and reason is None:
        return Part(ref, result.sufficiency_state, None, ())
    note = ",".join(sorted(details))
    return Part(ref, result.sufficiency_state, reason, (Cause(ref, result.sufficiency_state.value, reason, note),))


def insufficient_part(ref: str, reason: Optional[str], note: str, detail: str = "") -> Part:
    return Part(ref, SufficiencyState.INSUFFICIENT_DATA, reason,
                (Cause(ref, SufficiencyState.INSUFFICIENT_DATA.value, reason, note, detail),))


def limited_part(ref: str, reason: str, note: str) -> Part:
    return Part(ref, SufficiencyState.LIMITED, reason, (Cause(ref, SufficiencyState.LIMITED.value, reason, note),))


def replay_reason(detail: object) -> str:
    """The reason code TEXT replay shows for one `ReplayDetail` (its own priority table): a withheld relief record gives a gain the reason of its details (Ruling 3.8 (1.5) item 2)."""
    from domain.replay import reason_code_of  # noqa: PLC0415

    return reason_code_of([detail]).value  # type: ignore[list-item]


def pick_reason(reasons: Sequence[Optional[str]]) -> Optional[str]:
    """Ruling 1.5: the first present in the priority order; None when no cause carries a code."""
    found = {r for r in reasons if r is not None}
    for code in REASON_PRIORITY:
        if code.value in found:
            return code.value
    return None


@dataclass(frozen=True)
class PerformanceAggregation:
    """Rulings 1.4 and 1.5 as clarified by performance/1.1: the single reason code comes ONLY from the causes at the result's OWN state level. An
    INSUFFICIENT_DATA result takes its code from the INSUFFICIENT_DATA parts and causes, a LIMITED result from the LIMITED ones, an AVAILABLE result carries
    STALE_DATA or nothing. If no cause at that level has a code the reason is none, even if a lower-severity cause has one (a suppressed result never
    borrows STALE_DATA from an AVAILABLE input)."""

    rule_id: str = "performance/1.12#1.4-1.5"

    def combine(self, parts: Sequence[Part]) -> Aggregate:
        causes = tuple(c for p in parts for c in p.causes)
        if any(p.state is SufficiencyState.INSUFFICIENT_DATA for p in parts):
            state = SufficiencyState.INSUFFICIENT_DATA
        elif any(p.state is SufficiencyState.LIMITED for p in parts):
            state = SufficiencyState.LIMITED
        else:
            state = SufficiencyState.AVAILABLE
        level = [p.reason for p in parts if p.state is state] + [c.reason for c in causes if c.state == state.value]
        reason = pick_reason(level)
        if state is SufficiencyState.LIMITED and reason is None:
            reason = STALE_DATA  # Ruling 1.4 item 2: LIMITED within valuation is always + STALE_DATA
        if state is SufficiencyState.AVAILABLE and reason != STALE_DATA:
            reason = None  # an AVAILABLE total carries only STALE_DATA (PD-0006)
        return Aggregate(state, reason, sorted_causes(causes))


@dataclass(frozen=True)
class Valued:
    """One valued view of an entry or a total: its state, shown reason, EXACT value (None iff INSUFFICIENT_DATA), causes, freshness vector
    and, for a LIMITED total, the stale weight. Engine-internal: the outward type is `ComputedMetric`."""

    state: SufficiencyState
    reason: Optional[str]
    exact: Optional[Fraction]
    causes: Tuple[Cause, ...]
    freshness: FreshnessVector = EMPTY_FRESHNESS
    stale_weight: Optional[Fraction] = None
    excluded_weight: Optional[Fraction] = None  # Ruling 3.10: the gross weight of what a LIMITED gain aggregate leaves out (proceeds for realized, market value for unrealized)

    def __post_init__(self) -> None:
        if (self.exact is None) != (self.state is SufficiencyState.INSUFFICIENT_DATA):
            raise ValueError("a Valued has an exact value exactly when it is not INSUFFICIENT_DATA")

    def as_part(self, ref: str) -> Part:
        return Part(ref, self.state, self.reason, self.causes)


def build_metric(
    metric_id: str, view: str, subject: Tuple[Tuple[str, str], ...], valued: Valued, currency: Optional[CurrencyCode],
    rounding: RoundingRule, window: WindowUsed, method_id: str, synthetic: bool, conformant: bool,
    lineage: Tuple[Tuple[str, str], ...] = (), *, point: RoundingPoint = RoundingPoint.PRESENT_MONEY,
    unit: str = "CURRENCY_AMOUNT", numeric_basis: str = RATIONAL, breakdown: Tuple[Tuple[str, Decimal, Fraction], ...] = (),
    partial: bool = False, excluded: Tuple[Excluded, ...] = (), details: Tuple[str, ...] = (),
) -> ComputedMetric:
    if metric_id not in METRIC_IDS:
        raise ValueError(f"metric id {metric_id!r} is not in performance.registry.METRIC_IDS: register it, and give it its row in the availability matrix")
    subject = tuple(sorted(subject))
    lineage = tuple(sorted(lineage))
    ccy = None if currency is None else currency.code
    causes = valued.causes
    exact = valued.exact
    rule_used: Optional[str] = None
    stale_presented: Optional[Decimal] = None
    stale = valued.stale_weight
    excluded_w = valued.excluded_weight
    excluded_presented: Optional[Decimal] = None
    shown_breakdown = breakdown
    if valued.state is SufficiencyState.INSUFFICIENT_DATA or exact is None:
        result = MetricResult(None, SufficiencyState.INSUFFICIENT_DATA, reason_enum(valued.reason))
        exact, stale, excluded_w, shown_breakdown = None, None, None, ()
    else:
        p = present(exact, point, currency, rounding, IRRATIONAL_WIDTH if numeric_basis != RATIONAL else Fraction(0))
        if p.status is PresentStatus.OK and p.decimal is not None and p.stated is not None:
            result = MetricResult(p.decimal, valued.state, reason_enum(valued.reason))
            rule_used = None if p.stated == exact else rounding.rule_id
            if p.detail:  # performance/1.12 Ruling 2.2 item 4: a money fact in a currency outside the table is shown unpadded, with this detail; the state is unchanged
                details = tuple(details) + (p.detail,)
            if p.tie:
                details = tuple(details) + (PRESENTATION_TIE,)
            if stale is not None:  # a weight is a share: presented like a return (Ruling 2.2)
                sp = present(stale, RoundingPoint.PRESENT_RETURN, None, rounding)
                stale_presented = sp.decimal if sp.status is PresentStatus.OK else None
            if excluded_w is not None:
                ep = present(excluded_w, RoundingPoint.PRESENT_RETURN, None, rounding)
                excluded_presented = ep.decimal if ep.status is PresentStatus.OK else None
        elif p.status is PresentStatus.NO_RULE:
            result = MetricResult(None, SufficiencyState.INSUFFICIENT_DATA, ReasonCode.UNRESOLVED_CONVENTION)
            causes = sorted_causes(causes + (Cause(
                "presentation", SufficiencyState.INSUFFICIENT_DATA.value, UNRESOLVED_CONVENTION,
                f"{p.detail or 'NO_PRESENTATION'}: no presentation for this value under {rounding.rule_id}",
                p.detail or ""),))
            exact, stale, excluded_w, shown_breakdown = None, None, None, ()
        else:
            result = MetricResult(None, SufficiencyState.INSUFFICIENT_DATA, ReasonCode.CALCULATION_ERROR)
            causes = sorted_causes(causes + (Cause(
                "presentation", SufficiencyState.INSUFFICIENT_DATA.value, CALCULATION_ERROR,
                f"VALUE_NOT_REPRESENTABLE: {p.status.value}", "VALUE_NOT_REPRESENTABLE"),))
            exact, stale, excluded_w, shown_breakdown = None, None, None, ()
    details = tuple(sorted(set(details) | {c.detail for c in causes if c.detail}))
    return ComputedMetric(metric_id, view, subject, result, unit, ccy, exact, rule_used, causes, window, method_id, synthetic,
                          conformant, lineage, freshness=valued.freshness, stale_weight=stale,
                          stale_weight_presented=stale_presented, breakdown=shown_breakdown, partial=partial,
                          excluded=excluded, details=details, numeric_basis=numeric_basis,
                          excluded_weight=excluded_w, excluded_weight_presented=excluded_presented)
