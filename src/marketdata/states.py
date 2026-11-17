"""Mapping a market-data lookup outcome to (sufficiency state, reason code) per market-data/1.2
Rulings 1.6, 4.4, 4.7, 5.2 and PD-0030 §1. The ONLY market-data module that names a reason code.

| outcome                                                            | state              | reason                |
|--------------------------------------------------------------------|--------------------|-----------------------|
| price DISAGREEMENT / IMPLAUSIBLE                                   | INSUFFICIENT_DATA  | SOURCE_CONFLICT       |
| FX   DISAGREEMENT / IMPLAUSIBLE                                    | INSUFFICIENT_DATA  | SOURCE_CONFLICT       |
| no admissible print on or before D, or no series at all (price)    | INSUFFICIENT_DATA  | MISSING_PRICE_HISTORY |
| no fixing on or before D, or no series at all (FX; incl. CNH)      | INSUFFICIENT_DATA  | MISSING_FX_HISTORY    |
| freshness UNKNOWN (no calendar coverage)                           | INSUFFICIENT_DATA  | none (configuration)  |
| price, 0 missed sessions                                           | AVAILABLE          | none                  |
| price, 1 missed                                                    | AVAILABLE          | STALE_DATA            |
| price, 2-4 missed                                                  | LIMITED            | STALE_DATA            |
| price, 5 or more missed (the number is withheld)                   | INSUFFICIENT_DATA  | STALE_DATA            |
| FX, 0 missed fixings                                               | AVAILABLE          | none                  |
| FX, 1 missed                                                       | AVAILABLE          | STALE_DATA            |
| FX, 2-4 missed                                                     | LIMITED            | STALE_DATA            |
| FX, 5 or more missed (the rate is withheld)                        | INSUFFICIENT_DATA  | MISSING_FX_HISTORY    |

A price with 5 or more missed sessions stays STALE_DATA, not MISSING_PRICE_HISTORY, because a print
exists (Ruling 4.4); an FX rate with 5 or more missed fixings is MISSING_FX_HISTORY (Ruling 1.6: a week
of absent history). A listing on a market with no admitted source resolves to MISSING_PRICE_HISTORY,
with the cause NO_ADMITTED_SOURCE kept in the lookup's lineage notes (Ruling 4.7).

market-data/1.3 section 9B: the typed outcomes NO_HISTORY, STALE_BEYOND_LIMIT and FRESHNESS_UNKNOWN are internal;
each maps to exactly ONE pair above (NO_HISTORY covers four causes, kept apart in lineage: NO_PRINT_ON_OR_BEFORE_AS_OF,
NO_ADMITTED_SOURCE, SERIES_CONTRADICTED, ONLY_UNRECOVERED_READINGS), a number is withheld only at INSUFFICIENT_DATA
(2-4 missed is LIMITED with the value, 1 missed AVAILABLE + STALE_DATA), and a conflict, an implausible value or CNH is
never folded into NO_HISTORY: its reason code differs. Everything the table
does not decide (a custom policy that gives STALE without a count, a single unrecovered reading) is
INSUFFICIENT_DATA with NO code and a stated note: no existing code is borrowed (CALCULATION_ERROR,
LEDGER_INCONSISTENT, UNSUPPORTED_ASSET and STALE_DATA must not stand in for a conflict or a missing
price). A CNH amount is never translated with the CNY rate (PD-0030 §3).

The thresholds are the named constants of `marketdata.market11` (Ruling 5.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from marketdata.contracts import FreshnessState, ReconciliationStatus
from marketdata.market11 import LIMITED_FROM, NO_VALUE_FROM
from marketdata.port import FXLookup, LookupOutcome, QuoteLookup
from product_contract.metric_state import MetricResult
from product_contract.vocabulary import ReasonCode, SufficiencyState


@dataclass(frozen=True)
class InputState:
    state: SufficiencyState
    reason: Optional[ReasonCode]
    note: str = ""

    def __post_init__(self) -> None:
        if self.state is not SufficiencyState.AVAILABLE:
            # the product's own coupling rules validate the pair (a value is required unless INSUFFICIENT)
            MetricResult(value=None if self.state is SufficiencyState.INSUFFICIENT_DATA else Decimal(0),
                         sufficiency_state=self.state, reason_code=self.reason)
        elif self.reason not in (None, ReasonCode.STALE_DATA):
            raise ValueError("AVAILABLE input carries no reason code here except STALE_DATA")


_CONFLICT = (ReconciliationStatus.DISAGREEMENT, ReconciliationStatus.IMPLAUSIBLE)


def _counted(missed: Optional[int], withheld_code: ReasonCode, what: str) -> Optional[InputState]:
    """Ruling 5.2 table, for a value that IS returned (missed < 5) and was counted."""
    if missed is None:
        return None
    if missed == 0:
        return InputState(SufficiencyState.AVAILABLE, None)
    if missed < LIMITED_FROM:
        return InputState(SufficiencyState.AVAILABLE, ReasonCode.STALE_DATA, f"{missed} {what} missed")
    if missed < NO_VALUE_FROM:
        return InputState(SufficiencyState.LIMITED, ReasonCode.STALE_DATA, f"{missed} {what} missed")
    return InputState(SufficiencyState.INSUFFICIENT_DATA, withheld_code, f"{missed} {what} missed")


def price_input_state(lookup: QuoteLookup) -> InputState:
    rec = lookup.reconciliation
    if rec is not None and rec.status in _CONFLICT:
        return InputState(SufficiencyState.INSUFFICIENT_DATA, ReasonCode.SOURCE_CONFLICT,
                          "two sources disagree beyond the Ruling 4.2 bound")
    if lookup.outcome in (LookupOutcome.NOT_IN_RELEASE, LookupOutcome.NO_HISTORY):
        note = "no admissible print on or before the date" if lookup.outcome is LookupOutcome.NO_HISTORY \
            else "no admitted series for this listing"
        if lookup.lineage_notes:
            note += f" ({'; '.join(lookup.lineage_notes)})"
        return InputState(SufficiencyState.INSUFFICIENT_DATA, ReasonCode.MISSING_PRICE_HISTORY, note)
    if lookup.outcome is LookupOutcome.STALE_BEYOND_LIMIT:
        return InputState(SufficiencyState.INSUFFICIENT_DATA, ReasonCode.STALE_DATA,
                          f"{lookup.missed_count} sessions missed: the price is withheld (Ruling 5.2)")
    if lookup.outcome is LookupOutcome.FRESHNESS_UNKNOWN:
        return InputState(SufficiencyState.INSUFFICIENT_DATA, None,
                          "freshness UNKNOWN: a configuration gap, not a data condition "
                          f"({'; '.join(lookup.lineage_notes)})")
    if lookup.outcome is LookupOutcome.FOUND and lookup.freshness is not None:
        if lookup.freshness.state is FreshnessState.UNKNOWN:
            return InputState(SufficiencyState.INSUFFICIENT_DATA, None,
                              "freshness UNKNOWN: a configuration gap, not a data condition")
        counted = _counted(lookup.missed_count, ReasonCode.STALE_DATA, "session(s)")
        if counted is not None:
            return counted
        if lookup.freshness.state is FreshnessState.CURRENT:
            return InputState(SufficiencyState.AVAILABLE, None)
        return InputState(SufficiencyState.INSUFFICIENT_DATA, None,
                          "stale: the Ruling 5.2 table needs the session count (not supplied by this policy)")
    return InputState(SufficiencyState.INSUFFICIENT_DATA, None,
                      "no usable reading for the date; counting sessions needs the calendar")


def fx_input_state(lookup: FXLookup) -> InputState:
    rec = lookup.reconciliation
    if rec is not None and rec.status in _CONFLICT:
        return InputState(SufficiencyState.INSUFFICIENT_DATA, ReasonCode.SOURCE_CONFLICT,
                          "two retrievals of one quote differ, or a published bound is breached")
    if lookup.outcome is LookupOutcome.SAME_CURRENCY:
        return InputState(SufficiencyState.AVAILABLE, None)
    if lookup.outcome in (LookupOutcome.NOT_IN_RELEASE, LookupOutcome.NO_HISTORY):
        return InputState(SufficiencyState.INSUFFICIENT_DATA, ReasonCode.MISSING_FX_HISTORY,
                          "no fixing on or before the date, or no admitted series for this pair "
                          "(CNH is never translated with the CNY rate)")
    if lookup.outcome is LookupOutcome.STALE_BEYOND_LIMIT:
        return InputState(SufficiencyState.INSUFFICIENT_DATA, ReasonCode.MISSING_FX_HISTORY,
                          f"{lookup.missed_count} fixings missed: the rate is withheld (Ruling 1.6)")
    if lookup.outcome is LookupOutcome.FRESHNESS_UNKNOWN:
        return InputState(SufficiencyState.INSUFFICIENT_DATA, None,
                          "freshness UNKNOWN: a configuration gap, not a data condition "
                          f"({'; '.join(lookup.lineage_notes)})")
    if lookup.outcome is LookupOutcome.FOUND and lookup.leg_freshness:
        if any(f.state is FreshnessState.UNKNOWN for f in lookup.leg_freshness):
            return InputState(SufficiencyState.INSUFFICIENT_DATA, None,
                              "freshness UNKNOWN: a configuration gap, not a data condition")
        counted = _counted(lookup.missed_count, ReasonCode.MISSING_FX_HISTORY, "fixing(s)")
        if counted is not None:
            return counted
        if all(f.state is FreshnessState.CURRENT for f in lookup.leg_freshness):
            return InputState(SufficiencyState.AVAILABLE, None)
        return InputState(SufficiencyState.INSUFFICIENT_DATA, None,
                          "freshness not CURRENT: the Ruling 1.6 table needs the fixing count "
                          "(not supplied by this policy)")
    return InputState(SufficiencyState.INSUFFICIENT_DATA, None,
                      "no usable fixing for the date; counting fixings needs the calendar")
