"""Small input types of the performance engine (tech plan 16.2)."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Dict, Optional, Protocol, Sequence, Tuple

from marketdata.calendars import CalendarSet
from marketdata.canonical import canonical_json, sha256_hex
from marketdata.conventions import ConventionSet
from marketdata.port import MarketDataPort


@unique
class ValuationMode(Enum):
    """PD-0015 / PM ruling 4 of CP3a: only HISTORICAL_AS_OF is built. `CURRENT_LIVE` is refused with an explicit
    availability state (`UNSUPPORTED_VALUATION_MODE`): no live source is admitted and Current mode is unbuilt in CP2.
    "Current value" means the valuation at the latest date with admissible data, labelled with that date and its freshness:
    the caller names that date as the as-of date; the engine never reads a clock."""

    HISTORICAL_AS_OF = "HISTORICAL_AS_OF"
    CURRENT_LIVE = "CURRENT_LIVE"  # live or delayed inputs: refused, no live source is admitted
    CURRENT_AT_INSTANT = "CURRENT_AT_INSTANT"  # PD-0015 Part 1's Current / Latest mode on end-of-day data: the engine chooses `D_c(t)` from the instant `t` and runs over `M_t` (Ruling 1.7 (1.12) item 5)


@dataclass(frozen=True)
class MarketView:
    """The market data a computation runs over (performance/1.2 Ruling 1.7). In historical mode it is the release `M`; in Current mode at `t` it is `M_t`, the files
    of `M` retrieved at or before `t` (calendar files by registration time), with EVERY CP2 step re-run over it. `parent_release_id` is `M`; `excluded_files` are the
    hashes of the files of `M` that `M_t` leaves out; both go into the manifest with `t`."""

    port: MarketDataPort
    calendars: CalendarSet
    conventions: ConventionSet
    parent_release_id: str
    excluded_files: Tuple[str, ...]
    instant: datetime.datetime


class MarketAtInstant(Protocol):
    """Builds `M_t` for an instant: a deterministic function of `(M, t)`."""

    def view(self, instant: datetime.datetime) -> MarketView: ...


@dataclass(frozen=True)
class SuppressionInput:
    """A valuation suppression for `(account, listing)` over `[first_date, end_exclusive)` (None: open-ended), produced
    OUTSIDE the engine (the F8-B service, in detect-only mode) and handed in. The engine never computes or applies a
    split, and never writes the ledger. `reason` is the reason-code TEXT (or None for a configuration gap)."""

    account_id: uuid.UUID
    listing_id: uuid.UUID
    first_date: datetime.date
    end_exclusive: Optional[datetime.date]
    reason: Optional[str]
    flag: str
    # market-data 1.9 Ruling 6.4c: what a carried taint needs to know about the SOURCE suppression: the corroborated split's ex-date `X` (the key `K`) and the
    # F8-B decision that produced it (`CONFLICT_DATE`, `NOT_RECORDED...`, ...). Optional: a caller that supplies neither gets the open-ended rule.
    ex_date: Optional[datetime.date] = None
    decision: Optional[str] = None

    def covers(self, day: datetime.date) -> bool:
        return self.first_date <= day and (self.end_exclusive is None or day < self.end_exclusive)

    def to_obj(self) -> Dict[str, Any]:
        return {"account_id": str(self.account_id), "listing_id": str(self.listing_id), "first_date": self.first_date,
                "end_exclusive": self.end_exclusive, "reason": self.reason, "flag": self.flag, "ex_date": self.ex_date,
                "decision": self.decision}


def suppressions_digest(items: Sequence[SuppressionInput]) -> str:
    """sha256 of the canonical JSON of the suppressions in a fixed order (recorded in the manifest)."""
    ordered = sorted(items, key=lambda s: (str(s.account_id), str(s.listing_id), s.first_date,
                                           s.end_exclusive or datetime.date.max, s.flag))
    return sha256_hex(canonical_json([s.to_obj() for s in ordered]).encode("utf-8"))
