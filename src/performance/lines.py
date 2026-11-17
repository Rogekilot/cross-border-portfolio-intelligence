"""Income, fee, tax, financing and conversion-result AMOUNTS over a window (`performance/1.4` Rulings 8.1 to 8.6; tech plan 16.17).

Each amount is a money fact in the reporting currency `R` over `(B, E]`, the sum of its lines, each recognized on ONE date at that date's fixing `X(c to R, d)` (never the
user's own conversion rate):

| line                  | events                                      | recognized on                                                   | sign     |
|-----------------------|---------------------------------------------|-----------------------------------------------------------------|----------|
| income                | `DIVIDEND`, `INTEREST`                      | a dividend with `ex_date < event_date`: the EX-DATE (accrual, 8.1); otherwise the event date (cash basis, lineage `INCOME_CASH_BASIS`); interest: its booking date (8.3) | positive |
| fees                  | `FEE`                                       | the event date                                                  | negative |
| known taxes           | `TAX`                                       | the event date (withholding, stamp duty, levies)                | negative |
| financing costs       | `INTEREST_CHARGED`                          | the event date; never netted against `INTEREST` income          | negative |
| conversion result     | `CURRENCY_CONVERSION`                       | the event date: `- amount x X(sold to R, d) + bought_amount x X(bought to R, d)` (8.5) | either |

A window with no such event has amount 0 and state AVAILABLE: a fact, not missing data (1.4 clarification of 8.6). An event whose amount cannot be translated (a CNH
amount, a missing rate) makes the amount of ITS OWN line INSUFFICIENT_DATA with that reason; the other lines are unaffected. The pay-date credit of an accrued dividend is not
income again (8.1). A net-only dividend's withholding is unknown, not zero (8.2): the taxes line is "known taxes" and is not marked LIMITED.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, List, Optional, Sequence, Tuple

from domain.currency import CurrencyCode
from domain.ledger import EventType
from domain.replay import SequencedEvent
from marketdata.conventions import ConventionSet
from marketdata.port import MarketDataPort
from performance.conventions import PerformanceConventionSet
from performance.flows import DataUse, _rate
from performance.numerics import within_bounds
from performance.results import EMPTY_FRESHNESS, Cause, Part
from performance.states import CALCULATION_ERROR, Valued, insufficient_part
from product_contract.vocabulary import SufficiencyState

INSUFFICIENT = SufficiencyState.INSUFFICIENT_DATA
INCOME_CASH_BASIS = "INCOME_CASH_BASIS"

INCOME, FEES, TAXES, FINANCING, CONVERSION = "income", "fees", "taxes", "financing", "conversion_result"
LINES = (INCOME, FEES, TAXES, FINANCING, CONVERSION)
METRIC_ID = {INCOME: "income_amount", FEES: "fees_amount", TAXES: "taxes_amount", FINANCING: "financing_amount", CONVERSION: "conversion_result_amount"}


@dataclass(frozen=True)
class LineItem:
    """One recognized line: its event, the date it is recognized on, the native pieces `(currency, signed amount)` it is made of, and any lineage detail."""

    event_id: uuid.UUID
    day: datetime.date
    pieces: Tuple[Tuple[CurrencyCode, Fraction], ...]
    detail: str = ""


def line_items(live: Sequence[SequencedEvent], line: str, base: datetime.date, end: datetime.date,
               account_scope: Optional[uuid.UUID] = None) -> Tuple[LineItem, ...]:
    """The items of `line` recognized in `(base, end]` among the live events (reversed events are already gone), in `(day, event id)` order."""
    out: List[LineItem] = []
    for item in live:
        e = item.event
        if account_scope is not None and e.account_id != account_scope:
            continue
        ty = e.event_type
        if line == INCOME and ty in (EventType.DIVIDEND, EventType.INTEREST) and e.amount is not None:
            if ty is EventType.DIVIDEND and e.ex_date is not None and e.ex_date < e.event_date:
                day, detail = e.ex_date, ""  # Ruling 8.1: accrued from the ex-date
            else:
                day, detail = e.event_date, INCOME_CASH_BASIS if ty is EventType.DIVIDEND else ""  # cash basis (lineage, no state change)
            pieces = ((e.currency, Fraction(e.amount.amount)),)
        elif line == FEES and ty is EventType.FEE and e.amount is not None:
            day, detail, pieces = e.event_date, "", ((e.currency, -Fraction(e.amount.amount)),)
        elif line == TAXES and ty is EventType.TAX and e.amount is not None:
            day, detail, pieces = e.event_date, "", ((e.currency, -Fraction(e.amount.amount)),)
        elif line == FINANCING and ty is EventType.INTEREST_CHARGED and e.amount is not None:
            day, detail, pieces = e.event_date, "", ((e.currency, -Fraction(e.amount.amount)),)
        elif line == CONVERSION and ty is EventType.CURRENCY_CONVERSION and e.amount is not None and e.bought_amount is not None:
            day, detail = e.event_date, ""
            pieces = ((e.amount.currency, -Fraction(e.amount.amount)), (e.bought_amount.currency, Fraction(e.bought_amount.amount)))
        else:
            continue
        if base < day <= end:
            out.append(LineItem(e.event_id, day, pieces, detail))
    return tuple(sorted(out, key=lambda i: (i.day, str(i.event_id))))


def line_amount(
    live: Sequence[SequencedEvent], line: str, base: datetime.date, end: datetime.date, reporting: CurrencyCode, port: MarketDataPort, market: ConventionSet,
    conventions: PerformanceConventionSet, use: DataUse, account_scope: Optional[uuid.UUID] = None,
    retrieved_not_after: Optional[datetime.datetime] = None,
) -> Tuple[Valued, Tuple[str, ...]]:
    """The amount of one line over `(B, E]` as a `Valued` (exact, in `R`) and its lineage details. Each piece is translated at its own date's fixing; the states of
    the translations are combined by the injected aggregation (Ruling 1.4), so one untranslatable piece makes THIS line INSUFFICIENT_DATA with its reason."""
    items = line_items(live, line, base, end, account_scope)
    if not items:
        return Valued(SufficiencyState.AVAILABLE, None, Fraction(0), ()), ()
    total = Fraction(0)
    parts: List[Part] = []
    fresh = EMPTY_FRESHNESS
    for it in items:
        for currency, amount in it.pieces:
            rate, part, f = _rate(it.day, currency, reporting, port, market, use, retrieved_not_after)
            fresh = fresh.union(f)
            if part is not None:
                parts.append(Part(f"{line}:{it.event_id}:{part.ref}", part.state, part.reason, part.causes, ))
            if rate is not None:
                total += amount * rate
    details = tuple(sorted({it.detail for it in items if it.detail}))
    agg = conventions.aggregation.combine(parts)
    if agg.state is INSUFFICIENT:
        return Valued(INSUFFICIENT, agg.reason, None, agg.causes, fresh), details
    if not within_bounds(total):
        cause = Cause(line, INSUFFICIENT.value, CALCULATION_ERROR, "VALUE_NOT_REPRESENTABLE: size guard", "VALUE_NOT_REPRESENTABLE")
        return Valued(INSUFFICIENT, CALCULATION_ERROR, None, tuple(sorted(set(agg.causes + (cause,)))), fresh), details
    return Valued(agg.state, agg.reason, total, agg.causes, fresh), details
