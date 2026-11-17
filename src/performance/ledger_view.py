"""The ledger as the performance engine reads it (tech plan 16.1, 16.2, 16.4; `performance/1.0` Ruling 4).

- `ledger_digest(events, L)`: sha256 of the canonical encoding of the live events at ledger version L (in `ledger_seq` order). The manifest records
  it beside the version pin, so a restored or altered ledger is detected, not trusted.
- `paired_transfer_legs`: the transfer legs that are INTERNAL to the portfolio (reciprocal counterparties, same date and currency, same listing and
  quantity or same cash amount): each such leg is neutral at portfolio level (Ruling 4.1) and a flow of its account at account scope (Ruling 4.5).
- `classify_events`: each live event's flow class and timing from the injected `FlowTable`, at PORTFOLIO or ACCOUNT scope.
- `inception_of`: the inception base date `I0` (Ruling 4.4).
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from domain.ledger import EventType, LedgerEvent
from domain.replay import SequencedEvent, live_events
from marketdata.canonical import canonical_json, sha256_hex
from performance.conventions import FlowClass, FlowTable, FlowTiming, timing_of


def _money(m: Any) -> Optional[Dict[str, Any]]:
    return None if m is None else {"amount": m.amount, "currency": m.currency.code}


def event_obj(item: SequencedEvent) -> Dict[str, Any]:
    e: LedgerEvent = item.event
    out = _event_obj_base(item)
    if e.acquired_on is not None:  # PD-0036: part of the digest only where present, so every ledger without it keeps its digest
        out["acquired_on"] = e.acquired_on
    return out


def _event_obj_base(item: SequencedEvent) -> Dict[str, Any]:
    e: LedgerEvent = item.event
    ratio = None if e.split_ratio is None else {"new_units": e.split_ratio.new_units, "old_units": e.split_ratio.old_units}
    return {
        "ledger_seq": item.ledger_seq, "event_id": str(e.event_id), "account_id": str(e.account_id),
        "event_type": e.event_type.value, "event_date": e.event_date, "currency": e.currency.code,
        "listing_id": None if e.listing_id is None else str(e.listing_id), "quantity": e.quantity,
        "amount": _money(e.amount), "cost_basis": _money(e.cost_basis), "bought_amount": _money(e.bought_amount),
        "split_ratio": ratio,
        "counterparty_account_id": None if e.counterparty_account_id is None else str(e.counterparty_account_id),
        "settlement_date": e.settlement_date, "ex_date": e.ex_date,
        "reverses_event_id": None if e.reverses_event_id is None else str(e.reverses_event_id),
        "corrects_event_id": None if e.corrects_event_id is None else str(e.corrects_event_id),
        "source_reference": e.source_reference,
    }


def ledger_digest(events: Iterable[SequencedEvent], ledger_version: int) -> str:
    live = live_events(events, ledger_version)
    return sha256_hex(canonical_json([event_obj(i) for i in live]).encode("utf-8"))


def transfer_pairs(live: Sequence[SequencedEvent]) -> Tuple[Tuple[SequencedEvent, SequencedEvent], ...]:
    """The internal transfers among `live` as `(out leg, in leg)` pairs (greedy, in `(event_date, ledger_seq)` order, each leg used once; cash or security
    form). A leg with no counterparty account is external by definition; a leg that names one but finds no partner is NOT paired (the ledger refuses such a state
    at commit, so it cannot arise from a committed ledger)."""
    outs = sorted((i for i in live if i.event.event_type is EventType.TRANSFER_OUT and i.event.counterparty_account_id is not None),
                  key=lambda i: (i.event.event_date, i.ledger_seq))
    ins = sorted((i for i in live if i.event.event_type is EventType.TRANSFER_IN and i.event.counterparty_account_id is not None),
                 key=lambda i: (i.event.event_date, i.ledger_seq))
    used: set = set()
    pairs: List[Tuple[SequencedEvent, SequencedEvent]] = []
    for out in outs:
        o = out.event
        for leg in ins:
            e = leg.event
            if e.event_id in used:
                continue
            if (e.account_id == o.counterparty_account_id and e.counterparty_account_id == o.account_id
                    and e.event_date == o.event_date and e.currency == o.currency and e.listing_id == o.listing_id
                    and e.quantity == o.quantity and e.amount == o.amount):
                used.add(e.event_id)
                pairs.append((out, leg))
                break
    return tuple(pairs)


def paired_transfer_legs(live: Sequence[SequencedEvent]) -> FrozenSet[uuid.UUID]:
    """The event ids of the transfer legs that have their partner leg among `live` (see `transfer_pairs`)."""
    return frozenset(e.event.event_id for pair in transfer_pairs(live) for e in pair)


@dataclass(frozen=True)
class ClassifiedEvent:
    ledger_seq: int
    event_id: uuid.UUID
    account_id: uuid.UUID
    event_date: datetime.date
    event_type: str
    flow_class: FlowClass
    timing: FlowTiming
    currency: str
    native_amount: Optional[Decimal]  # a cash amount (None for a security-form transfer or a SPLIT)
    listing_id: Optional[uuid.UUID]
    quantity: Optional[Decimal]
    internal: bool  # a transfer paired inside the portfolio
    detail: str = ""


def classify_events(events: Iterable[SequencedEvent], ledger_version: int, table: FlowTable,
                    account_scope: Optional[uuid.UUID] = None) -> Tuple[ClassifiedEvent, ...]:
    """The live events at L, ordered `(event_date, ledger_seq)`, each with its flow class from `table`. At PORTFOLIO scope (`account_scope`
    None) every event is considered. At ACCOUNT scope only that account's events are, and an internal transfer is a flow of the account (Ruling 4.5)."""
    live = live_events(events, ledger_version)
    paired = paired_transfer_legs(live)
    out: List[ClassifiedEvent] = []
    for item in live:
        e = item.event
        if account_scope is not None and e.account_id != account_scope:
            continue
        internal = e.event_id in paired
        cls = table.classify(e, internal=internal, account_scope=account_scope is not None)
        detail = ""
        if e.event_type in (EventType.TRANSFER_IN, EventType.TRANSFER_OUT) and e.counterparty_account_id is not None and not internal:
            detail = "UNPAIRED_TRANSFER_LEG"
        amount = None if e.amount is None else e.amount.amount
        out.append(ClassifiedEvent(item.ledger_seq, e.event_id, e.account_id, e.event_date, e.event_type.value, cls, timing_of(cls),
                                   e.currency.code, amount, e.listing_id, e.quantity, internal, detail))
    return tuple(sorted(out, key=lambda c: (c.event_date, c.ledger_seq)))


@dataclass(frozen=True)
class Inception:
    """Ruling 4.4. `date` is `I0`: the LATEST snapshot date among the accounts if any account has one, else the day before the earliest live event;
    None when there is no live event. `since_snapshot` marks a snapshot portfolio (the window is then "since S")."""

    date: Optional[datetime.date]
    since_snapshot: bool


def inception_of(events: Iterable[SequencedEvent], ledger_version: int,
                 account_scope: Optional[uuid.UUID] = None) -> Inception:
    live = [i for i in live_events(events, ledger_version) if account_scope is None or i.event.account_id == account_scope]
    snapshots = [i.event.event_date for i in live if i.event.event_type in (EventType.OPENING_POSITION, EventType.OPENING_CASH)]
    if snapshots:
        return Inception(max(snapshots), True)
    if not live:
        return Inception(None, False)
    return Inception(min(i.event.event_date for i in live) - datetime.timedelta(days=1), False)
