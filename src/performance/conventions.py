"""The performance convention set `performance/1.0` (`methodology/CP3_PERFORMANCE_CONVENTIONS.md`), as injected rules.

Every rule the Quant owns is an id-bearing slot. A slot the convention fixes carries its ruling's id (`performance/1.0#<ruling>`); a
slot still awaiting a ruling or an implementation would carry `placeholder/<name>/0`. `is_conformant` is False while any placeholder
(or any `test/...` stand-in) is injected OR any rule of the convention is not yet built (`open_items`), every Computation Manifest records
it, and every result says so (tech plan 15.13, 16.9).

The flow table (`FlowTable`) is DATA (Ruling 4.1): the class and the timing (Ruling 4.2) of each ledger event type. The engineer decides none
of it: it is transcribed from the Quant's table, and every row not stated there would be a placeholder.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from enum import Enum, unique
from typing import Dict, Mapping, Optional, Protocol, Sequence, Tuple

from domain.ledger import EventType, LedgerEvent
from performance.numerics import RoundingRule
from performance.results import Aggregate, Part

CONVENTION_SET_ID = "performance/1.12"
PLACEHOLDER_PREFIXES = ("placeholder/", "test/")

#: Rules of the convention that are NOT yet built (each is listed in every manifest as an open item). performance/1.11 names none (CP3 section 16 item 16, 1.11): the HG2 evidence-pack entry is gone
#: (the pack is built, the gate is decided: PD-0038; I-7 runs in the test suite, the fixtures and the pack, where Ruling 11.1 (1.2) puts it). The name is kept: the engine imports it.
UNBUILT_IN_CP3B: Tuple[str, ...] = ()


@unique
class FlowClass(Enum):
    """Ruling 4.1 at portfolio level (and Ruling 4.5 at account scope)."""

    EXTERNAL_INFLOW_CASH = "EXTERNAL_INFLOW_CASH"    # I^C
    EXTERNAL_OUTFLOW_CASH = "EXTERNAL_OUTFLOW_CASH"  # O
    EXTERNAL_INFLOW_KIND = "EXTERNAL_INFLOW_KIND"    # I^K
    EXTERNAL_OUTFLOW_KIND = "EXTERNAL_OUTFLOW_KIND"  # O (in kind)
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"          # neutral at portfolio level
    EXCHANGE = "EXCHANGE"                            # BUY, SELL: internal exchange (a price effect)
    CONVERSION = "CONVERSION"                        # CURRENCY_CONVERSION: internal exchange
    INCOME = "INCOME"                                # DIVIDEND, INTEREST
    FEE = "FEE"
    TAX = "TAX"
    FINANCING = "FINANCING"                          # INTEREST_CHARGED
    NONE = "NONE"                                    # SPLIT (value is continuous); REVERSAL (removed by live selection)
    OPENING = "OPENING"                              # the snapshot origin: not a flow


@unique
class FlowTiming(Enum):
    """Ruling 4.2: cash inflows are available from the START of the day; cash outflows and every in-kind flow happen at the END, valued at the
    day's close and fixing."""

    START = "START"
    END = "END"
    NONE = "NONE"


EXTERNAL_CLASSES = frozenset({FlowClass.EXTERNAL_INFLOW_CASH, FlowClass.EXTERNAL_OUTFLOW_CASH,
                              FlowClass.EXTERNAL_INFLOW_KIND, FlowClass.EXTERNAL_OUTFLOW_KIND})

_TIMING: Mapping[FlowClass, FlowTiming] = {
    FlowClass.EXTERNAL_INFLOW_CASH: FlowTiming.START,
    FlowClass.EXTERNAL_OUTFLOW_CASH: FlowTiming.END,
    FlowClass.EXTERNAL_INFLOW_KIND: FlowTiming.END,
    FlowClass.EXTERNAL_OUTFLOW_KIND: FlowTiming.END,
}


def timing_of(flow_class: FlowClass) -> FlowTiming:
    return _TIMING.get(flow_class, FlowTiming.NONE)


@dataclass(frozen=True)
class FlowRow:
    event_type: EventType
    flow_class: Optional[FlowClass]  # None: decided by `FlowTable.classify` (a transfer: internal or external, cash or kind)
    note: str = ""


@dataclass(frozen=True)
class FlowTable:
    table_id: str
    rows: Tuple[FlowRow, ...]

    def __post_init__(self) -> None:
        seen = [r.event_type for r in self.rows]
        if len(seen) != len(set(seen)):
            raise ValueError("a flow table has one row per event type")

    def row(self, event_type: EventType) -> FlowRow:
        for r in self.rows:
            if r.event_type is event_type:
                return r
        raise KeyError(f"no row for {event_type.value}: the table must cover every event type")

    def classify(self, event: LedgerEvent, *, internal: bool, account_scope: bool) -> FlowClass:
        """The class of one event. `internal` says a transfer is paired with its other leg inside the portfolio. At ACCOUNT scope an
        internal transfer is a flow of the account (Ruling 4.5), like an external one."""
        row = self.row(event.event_type)
        if row.flow_class is not None:
            return row.flow_class
        if event.event_type not in (EventType.TRANSFER_IN, EventType.TRANSFER_OUT):
            raise ValueError(f"{event.event_type.value} needs a class in the table")
        if internal and not account_scope:
            return FlowClass.INTERNAL_TRANSFER
        inbound = event.event_type is EventType.TRANSFER_IN
        security_form = event.listing_id is not None
        if security_form:
            return FlowClass.EXTERNAL_INFLOW_KIND if inbound else FlowClass.EXTERNAL_OUTFLOW_KIND
        return FlowClass.EXTERNAL_INFLOW_CASH if inbound else FlowClass.EXTERNAL_OUTFLOW_CASH


def performance_flow_table() -> FlowTable:
    """Ruling 4.1, row by row."""
    return FlowTable("performance/1.12#4.1-4.2", (
        FlowRow(EventType.DEPOSIT, FlowClass.EXTERNAL_INFLOW_CASH, "Ruling 4.1"),
        FlowRow(EventType.WITHDRAWAL, FlowClass.EXTERNAL_OUTFLOW_CASH, "Ruling 4.1"),
        FlowRow(EventType.TRANSFER_IN, None, "external cash I^C, external security I^K, internal: neutral (Rulings 4.1, 4.5)"),
        FlowRow(EventType.TRANSFER_OUT, None, "external cash O, external security O in kind, internal: neutral"),
        FlowRow(EventType.BUY, FlowClass.EXCHANGE), FlowRow(EventType.SELL, FlowClass.EXCHANGE),
        FlowRow(EventType.CURRENCY_CONVERSION, FlowClass.CONVERSION),
        FlowRow(EventType.DIVIDEND, FlowClass.INCOME), FlowRow(EventType.INTEREST, FlowClass.INCOME),
        FlowRow(EventType.FEE, FlowClass.FEE), FlowRow(EventType.TAX, FlowClass.TAX),
        FlowRow(EventType.INTEREST_CHARGED, FlowClass.FINANCING),
        FlowRow(EventType.SPLIT, FlowClass.NONE, "value is continuous"),
        FlowRow(EventType.REVERSAL, FlowClass.NONE, "removes its target at every D (ledger-replay 2.1)"),
        FlowRow(EventType.OPENING_POSITION, FlowClass.OPENING, "not a flow: the base value V_S (Ruling 4.4)"),
        FlowRow(EventType.OPENING_CASH, FlowClass.OPENING, "not a flow: the base value V_S (Ruling 4.4)"),
    ))


class ValuationRule(Protocol):
    rule_id: str


class AggregationRule(Protocol):
    """How the states of parts combine into the state of a total (Rulings 1.4, 1.5)."""

    rule_id: str

    def combine(self, parts: Sequence[Part]) -> Aggregate: ...


@dataclass(frozen=True)
class DateLabelValuation:
    """Rulings 1.1 to 1.3 and 1.7: value at the as-of DATE; the date-label bundle; no instant cutoff."""

    rule_id: str = "performance/1.12#1.1-1.3,1.7"


@dataclass(frozen=True)
class PerformanceConventionSet:
    convention_set_id: str
    valuation: ValuationRule
    aggregation: AggregationRule
    rounding: RoundingRule
    flows: FlowTable
    window_rule_id: str = "performance/1.12#5.4"
    twr_rule_id: str = "performance/1.12#5.1-5.6"
    annualization_rule_id: str = "performance/1.12#7.1-7.2"
    lot_method: str = "FIFO/1"  # performance/1.1 Ruling 3.3, PD-0035 section 1 (lands with the lot engine, CP3d)
    open_items: Tuple[str, ...] = UNBUILT_IN_CP3B

    def ids(self) -> Dict[str, str]:
        ids = {
            "aggregation": self.aggregation.rule_id, "annualization": self.annualization_rule_id,
            "convention_set": self.convention_set_id, "flow_table": self.flows.table_id, "lot_method": self.lot_method,
            "rounding": self.rounding.rule_id, "twr": self.twr_rule_id, "valuation": self.valuation.rule_id,
            "windows": self.window_rule_id,
        }
        table_version = getattr(self.rounding, "table_version", None)
        if table_version is not None:
            ids["minor_unit_table"] = table_version
        return ids

    def placeholder_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(v for v in self.ids().values() if v.startswith(PLACEHOLDER_PREFIXES)))

    @property
    def is_conformant(self) -> bool:
        """True only when no placeholder or test stand-in is injected AND nothing in the convention is left unbuilt."""
        return not self.placeholder_ids() and not self.open_items

    def visible_open_items(self) -> Tuple[str, ...]:
        return tuple(f"placeholder rule injected: {p}" for p in self.placeholder_ids()) + tuple(self.open_items)
