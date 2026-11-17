"""Flow-date FX and valuation of the external flows (`performance/1.0` Rulings 4.1 to 4.3; tech plan 16.4).

An external flow is translated at its OWN date: a cash flow of `a` in currency `c` dated `d` is `a x X(c to R, d)`, at the fixing `u(d)` (never the
user's own conversion rate, never another date's rate: PRD 8.3); an in-kind flow is `q x P(listing, d) x X(c(listing) to R, d)` (Ruling 4.3). A flow
that cannot be translated (CNH, a missing rate) or valued (no price) is INSUFFICIENT_DATA with its reason, and so is every return over a window that
contains it; a LIMITED rate gives LIMITED. Exact rationals throughout.

Timing (Ruling 4.2): cash inflows `I^C` are available from the START of the day; cash outflows `O` and every in-kind flow (`I^K`, `O`) happen at the END,
valued at that day's close and fixing.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional, Sequence, Set, Tuple

from domain.currency import CurrencyCode
from marketdata.conventions import ConventionSet
from marketdata.contracts import QuoteObservation
from marketdata.manifest import DataKind, FileRef
from marketdata.port import InstrumentResolverPort, MarketDataPort
from marketdata.states import fx_input_state, price_input_state
from performance.conventions import EXTERNAL_CLASSES, FlowClass, FlowTiming, PerformanceConventionSet
from performance.inputs import SuppressionInput
from performance.ledger_view import ClassifiedEvent
from performance.numerics import within_bounds
from performance.results import EMPTY_FRESHNESS, Cause, FreshnessVector, Part, sorted_causes
from performance.states import Valued, insufficient_part, part_from_input
from performance.valuation import SUPPRESSION_DETAILS, CalendarIdOf, fx_freshness, price_freshness, retrieved_after
from product_contract.vocabulary import SufficiencyState

INSUFFICIENT = SufficiencyState.INSUFFICIENT_DATA


@dataclass
class DataUse:
    """What the flow valuations read, for the manifest: consumed files by kind, the date range looked up, and whether any input is synthetic."""

    consumed: Dict[DataKind, Set[FileRef]] = field(default_factory=dict)
    first: Dict[DataKind, datetime.date] = field(default_factory=dict)
    last: Dict[DataKind, datetime.date] = field(default_factory=dict)
    synthetic: bool = False
    fx_notes: Set[str] = field(default_factory=set)  # the lineage notes of every FX lookup read (provenance, parity check): they reach the lineage of every metric computed from those rates

    def add(self, kind: DataKind, refs: Sequence[FileRef], day: datetime.date, synthetic: bool) -> None:
        self.consumed.setdefault(kind, set()).update(refs)
        self.first[kind] = min(day, self.first.get(kind, day))
        self.last[kind] = max(day, self.last.get(kind, day))
        self.synthetic = self.synthetic or synthetic


@dataclass(frozen=True)
class ValuedFlow:
    event: ClassifiedEvent
    flow_class: FlowClass
    timing: FlowTiming
    valued: Valued  # the value in R (exact), or INSUFFICIENT_DATA with its causes


def external_flows(classified: Sequence[ClassifiedEvent], base: datetime.date, end: datetime.date) -> Tuple[ClassifiedEvent, ...]:
    """The external flows dated in `(base, end]` (Ruling 5.1: the window contains the days `B+1 .. E`)."""
    return tuple(c for c in classified if c.flow_class in EXTERNAL_CLASSES and base < c.event_date <= end)


ECB_CALENDAR = "ECB"  # the id of the calendar of the ECB fixings (as in `current.py`)


def _ecb_calendar_gap(market: ConventionSet, day: datetime.date) -> bool:
    """True when the ECB calendar of M governs but does not cover `day` (performance/1.6 Ruling 3.7a item 3: a rate that is missing because the calendar does not reach the date)."""
    calendars = getattr(getattr(market, "freshness", None), "calendars", None)
    if calendars is None:
        return False
    calendar, _problem = calendars.governing(ECB_CALENDAR)
    return calendar is not None and not calendar.covers(day, day)


def _rate(day: datetime.date, currency: CurrencyCode, reporting: CurrencyCode, port: MarketDataPort, market: ConventionSet,
          use: DataUse, retrieved_not_after: Optional[datetime.datetime]) -> Tuple[Optional[Fraction], Optional[Part], FreshnessVector]:
    if currency == reporting:
        return Fraction(1), None, EMPTY_FRESHNESS
    lookup = port.fx_on(currency, reporting, day, market)
    use.add(DataKind.FX, lookup.consumed, day, lookup.synthetic)
    use.fx_notes.update(lookup.lineage_notes)
    ref = f"fx:{currency.code}->{reporting.code}@{day.isoformat()}"
    fresh = fx_freshness(currency, lookup)
    st = fx_input_state(lookup)
    part = part_from_input(ref, st)
    if st.state is INSUFFICIENT and (any("CALENDAR_COVERAGE_GAP" in note for note in lookup.lineage_notes) or _ecb_calendar_gap(market, day)):
        # performance/1.6 Ruling 3.7a item 3: when the calendar does not cover the date either, lineage carries CALENDAR_COVERAGE_GAP as well (the reason stays
        # MISSING_FX_HISTORY: Ruling 1.5 takes the first cause at that level that has a code)
        gap = Cause(ref + ":calendar", INSUFFICIENT.value, None, "CALENDAR_COVERAGE_GAP: the ECB calendar does not cover the date", "CALENDAR_COVERAGE_GAP")
        part = Part(part.ref, part.state, part.reason, sorted_causes(part.causes + (gap,)))
    if st.state is not INSUFFICIENT and retrieved_after(lookup.legs, retrieved_not_after):
        return None, insufficient_part(ref, None, "RETRIEVED_AFTER_CURRENT_INSTANT: a leg was retrieved after the Current-mode instant",
                                       "RETRIEVED_AFTER_CURRENT_INSTANT"), fresh
    if st.state is INSUFFICIENT or lookup.rate is None:
        if st.state is not INSUFFICIENT:
            return None, insufficient_part(ref, None, "the lookup carries no rate"), fresh
        return None, part, fresh
    return lookup.rate, part, fresh


def value_flow(event: ClassifiedEvent, reporting: CurrencyCode, port: MarketDataPort, resolver: InstrumentResolverPort,
               market: ConventionSet, conventions: PerformanceConventionSet, use: DataUse,
               retrieved_not_after: Optional[datetime.datetime] = None, *, suppressions: Sequence[SuppressionInput],
               calendar_id_of: Optional[CalendarIdOf] = None) -> ValuedFlow:
    """`suppressions` has NO default (CP3-4): an in-kind flow of a suppressed `(account, listing)` is valued at a RAW close of another unit than its quantity
    (market-data Ruling 6.4 item 2), so it is INSUFFICIENT_DATA like the valuations of the same position (CP3-1)."""
    day = event.event_date
    ref = f"flow:{event.event_id}"
    if event.flow_class in (FlowClass.EXTERNAL_INFLOW_KIND, FlowClass.EXTERNAL_OUTFLOW_KIND):
        return _value_in_kind(event, reporting, port, resolver, market, conventions, use, retrieved_not_after, suppressions, calendar_id_of)
    if event.native_amount is None:
        return ValuedFlow(event, event.flow_class, event.timing, Valued(INSUFFICIENT, None, None, (Cause(
            ref, INSUFFICIENT.value, None, "a cash flow without an amount"),)))
    currency = CurrencyCode(event.currency)
    rate, part, fresh = _rate(day, currency, reporting, port, market, use, retrieved_not_after)
    amount = Fraction(event.native_amount)
    parts = [] if part is None else [part]
    agg = conventions.aggregation.combine(parts)
    value = None if rate is None else amount * rate
    if agg.state is INSUFFICIENT or value is None or not within_bounds(value):
        causes = agg.causes if agg.state is INSUFFICIENT else agg.causes + (Cause(
            ref, INSUFFICIENT.value, None, "the flow cannot be valued", ""),)
        return ValuedFlow(event, event.flow_class, event.timing, Valued(INSUFFICIENT, agg.reason, None, tuple(sorted(set(causes))), fresh))
    return ValuedFlow(event, event.flow_class, event.timing, Valued(agg.state, agg.reason, value, agg.causes, fresh))


def _value_in_kind(event: ClassifiedEvent, reporting: CurrencyCode, port: MarketDataPort, resolver: InstrumentResolverPort,
                   market: ConventionSet, conventions: PerformanceConventionSet, use: DataUse,
                   retrieved_not_after: Optional[datetime.datetime], suppressions: Sequence[SuppressionInput],
                   calendar_id_of: Optional[CalendarIdOf]) -> ValuedFlow:
    day = event.event_date
    ref = f"flow:{event.event_id}"
    lid = event.listing_id
    if lid is None or event.quantity is None:
        return ValuedFlow(event, event.flow_class, event.timing, Valued(INSUFFICIENT, None, None, (Cause(
            ref, INSUFFICIENT.value, None, "an in-kind flow without a listing and a quantity"),)))
    suppression_parts: List[Part] = []
    for s in sorted(suppressions, key=lambda s: (s.first_date, s.flag)):
        if s.account_id == event.account_id and s.listing_id == lid and s.covers(day):
            detail = next((d for d in SUPPRESSION_DETAILS if d in s.flag), "")
            suppression_parts.append(insufficient_part(f"suppression:{ref}", s.reason, s.flag, detail))
            break
    lookup = port.quote_on(lid, day, market)
    use.add(DataKind.QUOTE, lookup.consumed, day, lookup.synthetic)
    st = price_input_state(lookup)
    price_part = part_from_input(f"price:{lid}@{day.isoformat()}", st)
    price: Optional[Fraction] = None
    currency: Optional[CurrencyCode] = None
    sel = lookup.selected
    if sel is not None and isinstance(sel.observation, QuoteObservation):
        currency = sel.observation.currency
    else:
        currency = resolver.trading_currency(lid)
    if st.state is not INSUFFICIENT:
        if sel is None or not isinstance(sel.observation, QuoteObservation):
            price_part = insufficient_part(f"price:{lid}@{day.isoformat()}", None, "the lookup selected no reading")
        elif retrieved_after((sel,), retrieved_not_after):
            price_part = insufficient_part(f"price:{lid}@{day.isoformat()}", None,
                                           "RETRIEVED_AFTER_CURRENT_INSTANT: the close was retrieved after the Current-mode instant",
                                           "RETRIEVED_AFTER_CURRENT_INSTANT")
        else:
            price = Fraction(sel.observation.price)
    parts: List[Part] = [price_part] + suppression_parts
    rate: Optional[Fraction] = None
    fresh = price_freshness(lookup, resolver.exchange_mic(lid), calendar_id_of)
    if currency is None:
        parts.append(insufficient_part("fx:?", None, "no native currency is known for the in-kind listing"))
    else:
        rate, fx_part, fx_fresh = _rate(day, currency, reporting, port, market, use, retrieved_not_after)
        if fx_part is not None:
            parts.append(fx_part)
        fresh = fresh.union(fx_fresh)
    agg = conventions.aggregation.combine(parts)
    value = None
    if price is not None and rate is not None and not suppression_parts:
        value = Fraction(event.quantity) * price * rate
    if agg.state is INSUFFICIENT or value is None or not within_bounds(value):
        causes = agg.causes if agg.state is INSUFFICIENT else agg.causes + (Cause(ref, INSUFFICIENT.value, None, "the flow cannot be valued"),)
        return ValuedFlow(event, event.flow_class, event.timing, Valued(INSUFFICIENT, agg.reason, None, tuple(sorted(set(causes))), fresh))
    return ValuedFlow(event, event.flow_class, event.timing, Valued(agg.state, agg.reason, value, agg.causes, fresh))
