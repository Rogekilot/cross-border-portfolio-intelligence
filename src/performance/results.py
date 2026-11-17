"""Result types of the performance engine (tech plan 16.0 item 4, 16.3).

`ComputedMetric` wraps the product's `MetricResult` (PD-0025: a `Decimal` or no value, never subclassed) with everything an
audit needs: the exact rational (or the 50-digit decimal of a transcendental step) the value came from, EVERY cause that shaped its
state, the window actually used (PRD 14), the unit and currency, the freshness vector (performance Ruling 1.6), the stale weight where
a total is LIMITED (Ruling 1.4), the apportioned breakdown of a total (Ruling 2.4), the method id and the Computation Manifest id. It
never carries a number for an INSUFFICIENT_DATA result: `exact` is None exactly when the `MetricResult` has no value, so an exact rational
cannot leak a suppressed number.

This module names no reason code: a cause carries the code's TEXT (`performance.states` is the only module that maps it to and from the
product vocabulary).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, replace
from decimal import Decimal
from fractions import Fraction
from typing import Any, Dict, Optional, Tuple

from marketdata.canonical import canonical_json, sha256_hex
from product_contract.metric_state import MetricResult
from product_contract.vocabulary import SufficiencyState

PORTFOLIO_STATE_ACTUAL = "ACTUAL"  # P8: a hypothetical portfolio never goes through this engine
RATIONAL = "RATIONAL"  # tier E: an exact rational
DECIMAL_PREC50 = "DECIMAL_PREC50_HALF_EVEN"  # a transcendental step (Ruling 2.1): the exact value of a 50-digit decimal


@dataclass(frozen=True, order=True)
class Cause:
    """One input or condition that shaped a state: what (`ref`), its sufficiency state text, its reason-code text (or None), a
    short note and, where the convention names one, the lineage DETAIL (for example `NON_POSITIVE_BASE`). Sorted and
    de-duplicated wherever it appears."""

    ref: str
    state: str
    reason: Optional[str]
    note: str = ""
    detail: str = ""

    def to_obj(self) -> Dict[str, Any]:
        return {"ref": self.ref, "state": self.state, "reason": self.reason, "note": self.note, "detail": self.detail}


@dataclass(frozen=True)
class Part:
    """An input to an aggregation: its state, reason text and the causes it brings."""

    ref: str
    state: SufficiencyState
    reason: Optional[str] = None
    causes: Tuple[Cause, ...] = ()


@dataclass(frozen=True)
class Aggregate:
    state: SufficiencyState
    reason: Optional[str]
    causes: Tuple[Cause, ...]


# --- freshness vector (Ruling 1.6) -----------------------------------------------------------------------------------------

_RANK = {"CURRENT": 0, "STALE": 1, "UNKNOWN": 2}


@dataclass(frozen=True, order=True)
class FreshEntry:
    """For an exchange CALENDAR (its calendar id, with the MICs it governs, performance/1.2 Ruling 1.6) the OLDEST session used and the LARGEST missed-session count; for a currency the fixing date
    used and the missed-fixing count; the worst freshness state text among them."""

    kind: str  # "EXCHANGE" or "CURRENCY"
    key: str
    date_used: Optional[datetime.date]
    missed: Optional[int]
    state: str
    mics: Tuple[str, ...] = ()  # performance/1.2 Ruling 1.6: an EXCHANGE_CALENDAR entry lists the MICs the calendar governs among the holdings

    def to_obj(self) -> Dict[str, Any]:
        return {"kind": self.kind, "key": self.key, "date_used": self.date_used, "missed": self.missed, "state": self.state,
                "mics": list(self.mics)}


@dataclass(frozen=True)
class FreshnessVector:
    entries: Tuple[FreshEntry, ...] = ()
    delays: Tuple[str, ...] = ()  # DataDelayStatus texts (END_OF_DAY for every PD-0027 datum)

    @property
    def summary(self) -> str:
        """`UNKNOWN` if any component is UNKNOWN; `STALE` if any is STALE; otherwise `CURRENT` (Ruling 1.6)."""
        worst = max((_RANK.get(e.state, 2) for e in self.entries), default=0)
        return {0: "CURRENT", 1: "STALE", 2: "UNKNOWN"}[worst]

    def union(self, other: "FreshnessVector") -> "FreshnessVector":
        merged: Dict[Tuple[str, str], FreshEntry] = {}
        for e in self.entries + other.entries:
            key = (e.kind, e.key)
            old = merged.get(key)
            if old is None:
                merged[key] = e
                continue
            dates = [d for d in (old.date_used, e.date_used) if d is not None]
            misses = [m for m in (old.missed, e.missed) if m is not None]
            state = old.state if _RANK.get(old.state, 2) >= _RANK.get(e.state, 2) else e.state
            merged[key] = FreshEntry(e.kind, e.key, min(dates) if dates else None, max(misses) if misses else None, state,
                                     tuple(sorted(set(old.mics) | set(e.mics))))
        return FreshnessVector(tuple(sorted(merged.values())), tuple(sorted(set(self.delays) | set(other.delays))))

    def to_obj(self) -> Dict[str, Any]:
        return {"summary": self.summary, "entries": [e.to_obj() for e in self.entries], "delays": list(self.delays)}


EMPTY_FRESHNESS = FreshnessVector()


@dataclass(frozen=True)
class WindowUsed:
    """The window actually used (PRD 14, Ruling 5.4). Windows are HALF-OPEN `(start, end]`: `start` is the base date `B` (the base
    valuation is at the END of `B`), `end` is `E`, and the window contains the days `B+1 .. E`. For an as-of valuation `start == end`
    and the rule is `AS_OF`. `days` is `E - B`. `rule` is `AS_OF`, `TRAILING_MONTHS`, `YTD`, `SINCE_INCEPTION` or `CUSTOM`."""

    start: datetime.date
    end: datetime.date
    frequency: Optional[str] = None
    rule: str = "AS_OF"
    months: Optional[int] = None
    since_snapshot: bool = False  # "since S" for a snapshot portfolio, never "since you started investing" (PRD 9.3)
    # CP4b (tech plan 17.3.2 item 1; PRD 14 "state the actual window it used"): when a series window was CLIPPED to inception, the window that was ASKED for. Both None for every CP3 window.
    requested_months: Optional[int] = None
    requested_start: Optional[datetime.date] = None

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def to_obj(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"start": self.start, "end": self.end, "frequency": self.frequency, "rule": self.rule, "months": self.months,
                               "days": self.days, "since_snapshot": self.since_snapshot}
        # additive-when-present (tech plan 17.0 item 5): a window that was not clipped serialises exactly as in CP3, so no CP3 canonical dict, manifest id or digest changes
        if self.requested_months is not None:
            out["requested_months"] = self.requested_months
        if self.requested_start is not None:
            out["requested_start"] = self.requested_start
        return out


@dataclass(frozen=True)
class Excluded:
    """A component an INSUFFICIENT_DATA total could not value: what it is, its native quantity or amount, and why."""

    ref: str
    kind: str  # "POSITION", "CASH" or "RECEIVABLE"
    currency: Optional[str]
    native: str  # the native quantity (positions) or amount, as text
    causes: Tuple[Cause, ...]

    def to_obj(self) -> Dict[str, Any]:
        return {"ref": self.ref, "kind": self.kind, "currency": self.currency, "native": self.native,
                "causes": [c.to_obj() for c in self.causes]}


def sorted_causes(causes: Tuple[Cause, ...]) -> Tuple[Cause, ...]:
    return tuple(sorted(set(causes)))


@dataclass(frozen=True)
class ComputedMetric:
    metric_id: str
    view: str  # "NATIVE", "REPORTING" or "PERIOD"
    subject: Tuple[Tuple[str, str], ...]  # e.g. (("account", ...), ("listing", ...)), sorted
    result: MetricResult
    unit: str  # "CURRENCY_AMOUNT", "RATIO", "RATE_PER_YEAR"
    currency: Optional[str]
    exact: Optional[Fraction]  # the exact value BEFORE any presentation rule; None iff `result.value` is None
    rounding_rule_id: Optional[str]  # None when the presented value equals `exact`
    causes: Tuple[Cause, ...]
    window: WindowUsed
    method_id: str
    synthetic: bool
    conformant: bool
    lineage: Tuple[Tuple[str, str], ...] = ()  # e.g. ("price_date_used", "2025-01-03"); sorted
    manifest_id: Optional[str] = None
    portfolio_state: str = PORTFOLIO_STATE_ACTUAL
    freshness: Optional[FreshnessVector] = None
    stale_weight: Optional[Fraction] = None  # Ruling 1.4 item 2: stated beside a LIMITED total (gross weights)
    stale_weight_presented: Optional[Decimal] = None
    breakdown: Tuple[Tuple[str, Decimal, Fraction], ...] = ()  # apportioned display values (Ruling 2.4): (line, shown, exact)
    partial: bool = False  # PD-0035 section 2: a partial figure, never the total
    excluded: Tuple[Excluded, ...] = ()
    details: Tuple[str, ...] = ()  # lineage detail names (NON_POSITIVE_BASE, ZERO_CAPITAL_RUN, ...), sorted
    numeric_basis: str = RATIONAL
    excluded_weight: Optional[Fraction] = None  # Ruling 3.10: stated beside a LIMITED gain aggregate (gross weight of the excluded sales or positions)
    excluded_weight_presented: Optional[Decimal] = None

    def __post_init__(self) -> None:
        if (self.exact is None) != (self.result.value is None):
            raise ValueError("`exact` is present exactly when the MetricResult has a value (no number for INSUFFICIENT_DATA)")
        if self.exact is not None and not isinstance(self.exact, Fraction):
            raise TypeError("exact must be a Fraction")
        if self.portfolio_state != PORTFOLIO_STATE_ACTUAL:
            raise ValueError("this engine computes ACTUAL portfolios only (P8)")
        if list(self.subject) != sorted(self.subject) or list(self.lineage) != sorted(self.lineage):
            raise ValueError("subject and lineage must be sorted")
        if list(self.causes) != sorted(set(self.causes)):
            raise ValueError("causes must be sorted and unique")
        if list(self.details) != sorted(set(self.details)):
            raise ValueError("details must be sorted and unique")
        if self.result.sufficiency_state is SufficiencyState.INSUFFICIENT_DATA and not self.causes:
            raise ValueError("an INSUFFICIENT_DATA metric must name its causes")
        if self.result.value is None and (self.stale_weight is not None or self.breakdown or self.excluded_weight is not None):
            raise ValueError("a suppressed metric carries no stale weight, no excluded weight and no breakdown")

    def with_manifest(self, manifest_id: str) -> "ComputedMetric":
        return replace(self, manifest_id=manifest_id)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id, "view": self.view, "subject": [list(p) for p in self.subject],
            "value": self.result.value, "state": self.result.sufficiency_state.value,
            "reason": None if self.result.reason_code is None else self.result.reason_code.value,
            "unit": self.unit, "currency": self.currency, "exact": self.exact,
            "rounding_rule_id": self.rounding_rule_id, "causes": [c.to_obj() for c in self.causes],
            "window": self.window.to_obj(), "method_id": self.method_id, "synthetic": self.synthetic,
            "conformant": self.conformant, "lineage": [list(p) for p in self.lineage],
            "manifest_id": self.manifest_id, "portfolio_state": self.portfolio_state,
            "freshness": None if self.freshness is None else self.freshness.to_obj(),
            "stale_weight": self.stale_weight, "stale_weight_presented": self.stale_weight_presented,
            "breakdown": [[ref, shown, exact] for ref, shown, exact in self.breakdown], "partial": self.partial,
            "excluded": [e.to_obj() for e in self.excluded], "details": list(self.details),
            "numeric_basis": self.numeric_basis,
            "excluded_weight": self.excluded_weight, "excluded_weight_presented": self.excluded_weight_presented,
        }


def metrics_digest(metrics: Tuple[ComputedMetric, ...]) -> str:
    """The result digest: sha256 of the canonical JSON of every metric (section 16.2)."""
    return sha256_hex(canonical_json([m.to_canonical_dict() for m in metrics]).encode("utf-8"))
