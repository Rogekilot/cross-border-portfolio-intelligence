"""A split suppression follows the units (market-data/1.11 Ruling 6.4c; performance/1.5 Ruling 1.1a; review CP3-2, CP3-9).

Ruling 6.4 item 2 suppresses the positions that hold units at the start of a corroborated split's ex-date `X`. Units moved out of such a position by an INTERNAL transfer, dated `T`
inside the suppressed interval, arrive in an account that did not hold the listing at `X`: they are the same pre-split units, valued at the post-split RAW price. The
suppression follows the units by LOT IDENTITY, decided by the FIFO/1 lot book (`ledger-replay/1.4` Ruling 0.5.14), which REPLACES the earlier conservative "until the first day the
receiver ends at 0" stand-in:

- A lot is TAINTED when its carry history has a hop out of a position suppressed on the hop's date `T` (by an F8 suppression, or by a carried one: the hops are followed through
  every position). A `CONFLICT_DATE` source whose ledger split came early (`Y < X`) taints only until `X` (6.4c item 3(b)).
- A receiving position's valuation on `D` is suppressed iff its END-OF-DAY lot book on `D` holds a tainted lot: `INSUFFICIENT_DATA` + `SOURCE_CONFLICT`, lineage cause
  `SPLIT_SUPPRESSION_CARRIED`. So it ends on the day the last tainted unit is relieved (the position then holds no tainted unit and is valued).
- The events of that day stay suppressed: every `SELL` or `TRANSFER_OUT` whose relief record holds a tainted portion (`event_taints`): its realized gain (3.8) and its in-kind
  flow (4.3). A position that only passes the units on the day it receives them ends the day with no tainted lot and carries no suppression: it holds nothing to value.
- Never more suppression than the conservative rule: the day a receiver ends at 0 its book is empty.
- Taint is evaluated PER LEDGER VERSION: the suppressions handed in are those of the ledger at `L`, so where the source split has been appended nothing is carried. The fold is a
  function of the live events and is independent of entry order within a day (Ruling 11.3 (1)), so the result is too. Carried suppressions are taken to a FIXED POINT (a carried
  suppression is a source for the next hop; it only grows, so it ends).
- `TRANSFER_AFTER_UNRECORDED_SPLIT` is a lineage note, with no state effect: a split dated `X` is in the source account's ledger, but an internal transfer out of the source dated on
  or after `X` was recorded BEFORE the split was (`ledger_seq`), so its recorded quantity is read in post-split units.
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from domain.ledger import EventType
from domain.replay import DayBook, FifoState, Hop, Lot, SequencedEvent, reconstruct_fifo
from performance.inputs import SuppressionInput
from performance.ledger_view import transfer_pairs

SPLIT_SUPPRESSION_CARRIED = "SPLIT_SUPPRESSION_CARRIED"
TRANSFER_AFTER_UNRECORDED_SPLIT = "TRANSFER_AFTER_UNRECORDED_SPLIT"
CONFLICT_DATE = "CONFLICT_DATE"
ONE_DAY = datetime.timedelta(days=1)
MAX_DATE = datetime.date.max


@dataclass(frozen=True)
class CarriedTaint:
    """What the lot-book rule derives: the suppressions carried to positions, and, per depleting event (by `event_id`), the suppression its relief record's tainted portion implies."""

    suppressions: Tuple[SuppressionInput, ...] = ()
    event_taints: Dict[uuid.UUID, SuppressionInput] = field(default_factory=dict)


def _expiry(s: SuppressionInput, hop: Hop) -> Optional[datetime.date]:
    """6.4c item 3(b): a `CONFLICT_DATE` source with the ledger split early (`Y < X`) taints only until the market catches up at `X` (`None`: it does not end)."""
    if s.decision == CONFLICT_DATE and s.ex_date is not None and s.first_date < s.ex_date and s.ex_date > hop.date:
        return s.ex_date
    return None


def lot_taint(lot: Lot, known: Sequence[SuppressionInput], on: Optional[datetime.date] = None) -> Optional[Tuple[SuppressionInput, Hop, Optional[datetime.date]]]:
    """`(source suppression, hop, expiry)` if `lot` is tainted (on `on`, when given), else None: its first hop (in carry order) out of a position suppressed on the hop's date."""
    for hop in lot.hops:
        for s in sorted(known, key=lambda s: (s.first_date, s.flag)):
            if s.account_id == hop.source_account_id and s.listing_id == hop.listing_id and s.covers(hop.date):
                expiry = _expiry(s, hop)
                if on is not None and expiry is not None and on >= expiry:
                    continue
                return s, hop, expiry
    return None


def _flag(s: SuppressionInput, hop: Hop) -> str:
    return (f"{SPLIT_SUPPRESSION_CARRIED}: units carried from account {hop.source_account_id} on {hop.date.isoformat()} (split K ex-date "
            f"{'?' if s.ex_date is None else s.ex_date.isoformat()}; the source's own cause: {s.flag})")


def _carried_from_books(fifo: FifoState, known: Sequence[SuppressionInput]) -> List[SuppressionInput]:
    """Each position's tainted stretches, from its end-of-day books by day: a book recorded on day `d_i` holds until the next recorded day `d_{i+1}`."""
    out: List[SuppressionInput] = []
    for (account, listing), entries in sorted(fifo.history.items(), key=lambda kv: (kv[0][0].int, kv[0][1].int)):
        stretches: List[Tuple[datetime.date, Optional[datetime.date], SuppressionInput, Hop]] = []
        for i, book in enumerate(entries):
            if book.causes:
                continue  # no lot book is presented (flagged or opaque): replay's own state governs, not the taint
            nxt = entries[i + 1].date if i + 1 < len(entries) else None
            best: Optional[Tuple[datetime.date, SuppressionInput, Hop]] = None  # the stretch's end (MAX_DATE: open) and its source
            for lot in sorted(book.lots, key=lambda x: x.sort_key):
                found = lot_taint(lot, known)
                if found is None:
                    continue
                s, hop, expiry = found
                end = MAX_DATE if expiry is None else expiry
                if nxt is not None:
                    end = min(end, nxt)
                if best is None or end > best[0]:
                    best = (end, s, hop)
            if best is None:
                continue
            end, s, hop = best
            if end <= book.date:
                continue
            stretches.append((book.date, None if end == MAX_DATE else end, s, hop))
        merged: List[List] = []
        for start, end, s, hop in stretches:
            if merged and merged[-1][1] is not None and merged[-1][1] == start:
                merged[-1][1] = end  # continuous with the previous stretch
            else:
                merged.append([start, end, s, hop])
        for start, end, s, hop in merged:
            out.append(SuppressionInput(account, listing, start, end, s.reason, _flag(s, hop), s.ex_date, s.decision))
    return out


def carried_taint(live: Sequence[SequencedEvent], suppressions: Sequence[SuppressionInput]) -> CarriedTaint:
    """The carried suppressions and the per-event taints, derived deterministically from the live events at the ledger version and the F8 suppressions at that version.
    No internal security transfer, no carry: nothing is computed."""
    live = tuple(live)
    suppressions = tuple(suppressions)
    if not transfer_pairs(live) or not suppressions:
        return CarriedTaint()
    version = max(item.ledger_seq for item in live)
    fifo = reconstruct_fifo(live, MAX_DATE, version)
    carried: List[SuppressionInput] = []
    for _ in range(len(fifo.history) * 8 + 8):  # a fixed point: the carried set only grows and is bounded by the positions' stretches
        fresh = _carried_from_books(fifo, list(suppressions) + carried)
        if sorted(fresh, key=_sort_key) == sorted(carried, key=_sort_key):
            break
        carried = fresh
    known = list(suppressions) + carried
    events: Dict[uuid.UUID, SuppressionInput] = {}
    for relief in fifo.reliefs.values():
        if relief.withheld:
            continue
        for portion in sorted(relief.portions, key=lambda x: x.sort_key):
            found = lot_taint(portion, known, relief.event_date)
            if found is not None:
                s, hop, _expiry_date = found
                events[relief.event_id] = SuppressionInput(relief.account_id, relief.listing_id, relief.event_date, relief.event_date + ONE_DAY, s.reason, _flag(s, hop),
                                                           s.ex_date, s.decision)
                break
    # CP3-18 (market-data Ruling 6.4c rule 6): the RECEIVING leg of an internal pair carries the taint of the units it delivers. At account scope that leg is an in-kind inflow valued at
    # q x P x X; where the receiver ends the day without the tainted lot (it sold it the same day) no carried suppression covers it, so the in-leg itself is tainted when the lot it delivers
    # (the out-leg's relieved portions with this hop appended) has a hop out of a position suppressed on the hop's date.
    for out, leg in transfer_pairs(live):
        relief = fifo.relief(out.event.event_id)
        if relief is None or relief.withheld:
            continue
        o, i = out.event, leg.event
        for portion in sorted(relief.portions, key=lambda x: x.sort_key):
            delivered = dataclasses.replace(portion, hops=tuple(portion.hops) + (Hop(o.account_id, o.listing_id, o.event_id, i.event_id, o.event_date),))
            found = lot_taint(delivered, known, i.event_date)
            if found is not None:
                s, hop, _expiry_date = found
                events[i.event_id] = SuppressionInput(i.account_id, i.listing_id, i.event_date, i.event_date + ONE_DAY, s.reason, _flag(s, hop), s.ex_date, s.decision)
                break
    return CarriedTaint(tuple(sorted(carried, key=_sort_key)), events)


def _sort_key(c: SuppressionInput) -> Tuple[str, str, datetime.date, str]:
    return (str(c.account_id), str(c.listing_id), c.first_date, c.flag)


def carried_suppressions(live: Sequence[SequencedEvent], suppressions: Sequence[SuppressionInput]) -> Tuple[SuppressionInput, ...]:
    """The suppressions carried to receiving positions (see the module docstring). Sorted."""
    return carried_taint(live, suppressions).suppressions


@dataclass(frozen=True)
class UnrecordedSplitNote:
    """A lineage note (no state effect): the receiving position, the source account and the split's ex-date."""

    receiver: Tuple[uuid.UUID, uuid.UUID]
    source_account: uuid.UUID
    ex_date: datetime.date


def transfers_after_unrecorded_split(live: Sequence[SequencedEvent]) -> Tuple[UnrecordedSplitNote, ...]:
    """Ruling 6.4c item 7: a live SPLIT dated `X` in a source account `a` for listing `l`, and an internal security transfer out of `(a, l)` dated `T >= X` that was
    recorded BEFORE the split (a lower `ledger_seq`): the transfer's quantity is read in post-split units, which may not be what the user meant. Flagged for review."""
    live = tuple(live)
    splits = [i for i in live if i.event.event_type is EventType.SPLIT and i.event.listing_id is not None]
    notes: List[UnrecordedSplitNote] = []
    for out, leg in transfer_pairs(live):
        listing = out.event.listing_id
        if listing is None:
            continue
        for sp in splits:
            e = sp.event
            if (e.account_id == out.event.account_id and e.listing_id == listing and out.event.event_date >= e.event_date
                    and out.ledger_seq < sp.ledger_seq):
                notes.append(UnrecordedSplitNote((leg.event.account_id, listing), out.event.account_id, e.event_date))
    return tuple(sorted(set(notes), key=lambda n: (str(n.receiver[0]), str(n.receiver[1]), n.ex_date)))
