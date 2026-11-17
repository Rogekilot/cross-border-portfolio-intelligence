"""The benchmark's calculation-day levels when the series is not one published file: two sources for one benchmark (`risk/1.4` Ruling 5.7 (1.2)) and an ETF proxy built inside the engine (Ruling 5.5 (1.2)); tech plan 17.21.

A `LevelBook` is the list of a benchmark's calculation days with the level used on each, or the reason no level may be used. The leg (`risk.benchmark`) reads it exactly as it read one series: `L(g)` is the latest
calculation day `<= g` that has a level from any source (Ruling 5.2), and a day whose level is WITHHELD is not skipped: the grid date that needs it is `INSUFFICIENT_DATA` + `SOURCE_CONFLICT` with the detail
`BENCHMARK_SOURCE_CONFLICT` (a disagreement on a day no grid date uses changes nothing).

TWO SOURCES, per calculation day `d`:
- two or more sources with a level, all agreeing within the precision bound: `CORROBORATED` when their DECLARED upstreams are independent, else `SINGLE_SOURCE` (`market-data` Ruling 4.3; a source that declares no upstream is
  independent of nothing); the level of the HIGHEST-PRIORITY source (`SourceRecord.source_priority`, 1 = primary) is used. The bound of a published decimal level is half a unit of its last digit (`market-data` Ruling 4.2: `4321.12` is
  0.005), and two levels agree iff they differ by no more than the sum of their two bounds (CP4F-4). A second source is bound to the catalog entry: it must be declared there with the entry's return basis (`BenchmarkEntry.additional_sources`);
- one source only: `SINGLE_SOURCE`, used, not degraded;
- two or more differing: `DISAGREEMENT`, no level, until a resolution record exists (none is built, so none is applied).
A source's priority is DATA in the source registry; a multi-source benchmark with a missing or a repeated priority is refused as a whole (`BENCHMARK_SERIES_UNAVAILABLE`), never ordered by file order.

ETF PROXY: `TR` at the ETF's first print is its close; at each later print `t` (the previous print `t-`) `TR_t = TR_{t-} * f_t * (P_t + d_t) / P_{t-}`, with `d_t` the cash dividend per share and `f_t` the split ratio whose
ex-dates lie in `(t-, t]` (an ex-date that is not a print date applies at the next print). The actions used are those whose status (`market-data` Rulings 4.3, 4.5) is `CORROBORATED` or `SINGLE_SOURCE` (a single-source
dividend is NOT dropped: dropping it would make the proxy a partial price return, the bias Ruling 5.4 exists to prevent). Actions are identified by the STATEMENT, not the ex-date (`_identify_actions`, CP4F-3).
Ruling 5.5 (1.6): a DISAGREEMENT on a corporate action BREAKS THE CHAIN at its ex-date (levels from the first print on or after it are a new chain, `DayLevel.segment`; a ratio across the break is unavailable and every
other ratio is what it would be without the dispute); a price DISAGREEMENT withholds THAT print only and the chain links around it; a print with no usable reading is missing (normal staleness), not a conflict.
Everything is exact (`Fraction`).

Pure: no clock, no float, no I/O; the reads are the market-data port's.
"""

from __future__ import annotations

import bisect
import dataclasses
import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from itertools import combinations
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from marketdata.conventions import ConventionSet
from marketdata.contracts import BenchmarkSeries, CorporateActionObservation, CorporateActionType, QuoteObservation, ReconciliationStatus, SourceReading
from domain.currency import CurrencyCode
from marketdata.manifest import FileRef
from marketdata.port import MarketDataPort
from marketdata.states import fx_input_state
from product_contract.vocabulary import SufficiencyState

SINGLE_SOURCE = ReconciliationStatus.SINGLE_SOURCE.value
CORROBORATED = ReconciliationStatus.CORROBORATED.value
DISAGREEMENT = ReconciliationStatus.DISAGREEMENT.value
PROXY = "PROXY"


@dataclass(frozen=True)
class DayLevel:
    """One calculation day: the level used (None: withheld, with `note` saying why), the reconciliation status and the lineage of the levels it came from."""

    day: datetime.date
    value: Optional[Fraction]
    status: str
    note: str = ""
    #: the chain the level belongs to (Ruling 5.5 (1.6) item 4b): a ratio of two levels is available only inside one segment; a published series is one segment (0)
    segment: int = 0

    @property
    def withheld(self) -> bool:
        return self.value is None


@dataclass(frozen=True)
class Span:
    """A condition that attaches to EVERY ratio of levels spanning `ex` (`a < ex <= b`, the dates of the two prints used): a disputed corporate action (SOURCE_CONFLICT), a dividend whose conversion fixing is stale
    (AVAILABLE or LIMITED + STALE_DATA) or missing (INSUFFICIENT_DATA + MISSING_FX_HISTORY, the chain breaking there). Ratios that do not span `ex` are untouched. `detail` is the risk detail name, or "" for translation
    staleness, which adds none (Ruling 5.5 (1.8) item 4)."""

    ex: datetime.date
    state: SufficiencyState
    reason: Optional[str]
    detail: str
    note: str


class LevelBook:
    def __init__(self, days: Sequence[DayLevel], spans: Sequence[Span] = ()):
        ordered = sorted(days, key=lambda d: d.day)
        if any(b.day <= a.day for a, b in zip(ordered, ordered[1:])):
            raise ValueError("a level book has one entry per calculation day, ascending")
        self.days: Tuple[DayLevel, ...] = tuple(ordered)
        self.spans: Tuple[Span, ...] = tuple(sorted(spans, key=lambda s: s.ex))
        self._dates = [d.day for d in ordered]

    def __len__(self) -> int:
        return len(self.days)

    def latest(self, g: datetime.date, exists=None) -> Optional[DayLevel]:
        """The latest calculation day `<= g` (that `exists(day)` says exists, when a predicate is given: Current mode), or None."""
        i = bisect.bisect_right(self._dates, g) - 1
        while i >= 0:
            if exists is None or exists(self._dates[i]):
                return self.days[i]
            i -= 1
        return None


def book_of_series(series: BenchmarkSeries) -> LevelBook:
    return LevelBook([DayLevel(p.value_date, Fraction(p.value), SINGLE_SOURCE, f"{series.lineage.source_id}") for p in series.points])


# --- two sources (Ruling 5.7 (1.2)) -------------------------------------------------------------------------------------------------------------

class SourcePriorityError(ValueError):
    """A benchmark served by several sources has no usable order: a source has no `source_priority`, or two share one."""


class PrecisionUndeclared(ValueError):
    """A benchmark served by several sources cannot be reconciled without the index's `official_decimals` and every source's `precision_decimals` (Ruling 5.7 (1.9) item 4: precision is declared, never inferred)."""


def shown_decimals(series: BenchmarkSeries) -> int:
    """The most decimals any level of `series` SHOWS in its text. Used ONLY to check the declaration (Ruling 5.7 (1.9) item 3), never to set a bound."""
    return max((max(0, -int(p.value.as_tuple().exponent)) for p in series.points), default=0)  # type: ignore[arg-type]


def _bound(declared: int, official: int) -> Fraction:
    """The bound of a source (Ruling 5.7 (1.9) item 2, market-data Ruling 4.2): 0 when it publishes at least the official decimals (it renders the official level exactly), else half a unit of its declared last digit."""
    return Fraction(0) if declared >= official else Fraction(1, 2) * Fraction(1, 10 ** declared)


def _agree(a: Decimal, da: int, b: Decimal, db: int, official: int) -> bool:
    """Two levels agree iff they differ by no more than the sum of their sources' DECLARED bounds, exactly."""
    return abs(Fraction(a) - Fraction(b)) <= _bound(da, official) + _bound(db, official)


def reconcile_sources(by_source: Mapping[str, BenchmarkSeries], priority: Mapping[str, Optional[int]], official_decimals: Optional[int], source_decimals: Mapping[str, int]) -> LevelBook:
    """The book of a benchmark served by several sources. `priority` maps each source id to its registry `source_priority`; `official_decimals` is the index's declared precision and `source_decimals` each source's
    (Ruling 5.7 (1.9)): undeclared is `PrecisionUndeclared`, a level showing more decimals than its source declares is a contradiction of the declaration (the content check, item 3)."""
    ids = sorted(by_source)
    missing = [s for s in ids if priority.get(s) is None]
    if missing:
        raise SourcePriorityError(f"source(s) {missing} serve a benchmark that another source also serves and carry no source_priority in the source registry")
    ranks = [priority[s] for s in ids]
    if len(set(ranks)) != len(ranks):
        raise SourcePriorityError(f"two sources of one benchmark share a source_priority ({dict(zip(ids, ranks))}): the order is data and must be unique")
    if official_decimals is None or any(s not in source_decimals for s in by_source):
        raise PrecisionUndeclared(f"the benchmark is served by {sorted(by_source)} and its official decimals or a source's precision is not declared in the catalog entry")
    for s, series in sorted(by_source.items()):
        if shown_decimals(series) > source_decimals[s]:
            raise PrecisionUndeclared(f"source {s!r} declares {source_decimals[s]} decimals but a level shows {shown_decimals(series)}: the declaration is contradicted by the file")
    ordered = sorted(ids, key=lambda s: priority[s])  # type: ignore[arg-type, return-value]
    values: Dict[str, Dict[datetime.date, Decimal]] = {s: {p.value_date: p.value for p in by_source[s].points} for s in ordered}
    groups = {s: by_source[s].lineage.independence_group for s in ordered}  # None: no declared upstream
    precision = dict(source_decimals)
    days = sorted({d for s in ordered for d in values[s]})
    out: List[DayLevel] = []
    for d in days:
        have = [(s, values[s][d]) for s in ordered if d in values[s]]
        lineage = "; ".join(f"{s}={v}" for s, v in have)
        if any(not _agree(a, precision[sa], b, precision[sb], official_decimals) for (sa, a), (sb, b) in combinations(have, 2)):  # differing beyond the precision bound of the two published levels: no level, never settled by order, recency, majority or average
            out.append(DayLevel(d, None, DISAGREEMENT, f"BENCHMARK_SOURCE_CONFLICT: {lineage}"))
            continue
        # independence is by declared UPSTREAM (market-data Ruling 4.1): a source that declares none is not independent of anything, so agreement with it is SINGLE_SOURCE, never CORROBORATED (fail closed)
        independent = len(have) > 1 and all(groups[s] is not None for s, _v in have) and len({groups[s] for s, _v in have}) > 1
        status = CORROBORATED if independent else SINGLE_SOURCE
        out.append(DayLevel(d, Fraction(have[0][1]), status, lineage))  # the highest-priority source's level (`have` is in priority order)
    return LevelBook(out)


# --- the ETF proxy (Ruling 5.5 (1.2)) -----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ProxyBuild:
    book: LevelBook
    consumed: Tuple[FileRef, ...]
    source_id: Optional[str]
    synthetic: bool
    currency: Optional[str]


def _amount(reading: SourceReading) -> Fraction:
    obs = reading.observation
    assert isinstance(obs, CorporateActionObservation) and obs.amount_per_unit is not None
    return Fraction(obs.amount_per_unit.amount)


def _ratio(reading: SourceReading) -> Fraction:
    obs = reading.observation
    assert isinstance(obs, CorporateActionObservation) and obs.split_ratio is not None
    return Fraction(obs.split_ratio.new_units) / Fraction(obs.split_ratio.old_units)


def _shown(kind: str, reading: SourceReading) -> str:
    """The value as the source published it (a decimal), for the lineage."""
    obs = reading.observation
    assert isinstance(obs, CorporateActionObservation)
    if kind == "CASH_DIVIDEND":
        assert obs.amount_per_unit is not None
        return str(obs.amount_per_unit.amount)
    assert obs.split_ratio is not None
    return f"{obs.split_ratio.new_units}:{obs.split_ratio.old_units}"


@dataclass(frozen=True)
class _Item:
    """One corporate action as one source states it: what `market-data` Ruling 4.5 says must be EQUAL for two records to be the same corroborated action (a split: ex-date and ratio; a cash dividend: ex-date,
    per-unit amount, currency and pay date)."""

    kind: str
    ex: datetime.date
    pay: Optional[datetime.date]
    value: Fraction            # the per-unit amount, or the split ratio
    currency: Optional[str]
    record: Optional[datetime.date] = None  # the issuer's record date, when the source states one
    paid_currency: Optional[str] = None     # what the issuer states it paid (Ruling 5.5 (1.8) item 2), as stated
    paid_amount: Optional[Fraction] = None

    def key(self) -> Tuple:
        return (self.kind, self.ex, self.pay, self.value, self.currency, self.record)

    def base(self) -> Tuple:
        """What two statements must share to be equal, the record date being compared only when BOTH state one (Ruling 5.5 (1.7) item 1)."""
        return (self.kind, self.ex, self.pay, self.value, self.currency)

    def shown(self, source_value: str) -> str:
        return f"{self.kind} ex {self.ex.isoformat()}" + (f" pay {self.pay.isoformat()}" if self.pay else "") + f" {source_value}"


def _item_of(reading: SourceReading) -> Optional[Tuple[_Item, str]]:
    obs = reading.observation
    if not isinstance(obs, CorporateActionObservation):
        return None
    if obs.action_type is CorporateActionType.CASH_DIVIDEND:
        assert obs.amount_per_unit is not None
        return _Item("CASH_DIVIDEND", obs.effective_date, obs.pay_date, Fraction(obs.amount_per_unit.amount), obs.amount_per_unit.currency.code, obs.record_date,
                     None if obs.paid_currency is None else obs.paid_currency.code, None if obs.paid_amount is None else Fraction(obs.paid_amount)), _shown("CASH_DIVIDEND", reading)
    if obs.action_type is CorporateActionType.SPLIT:
        assert obs.split_ratio is not None
        return _Item("SPLIT", obs.effective_date, None, _ratio(reading), None, obs.record_date), _shown("SPLIT", reading)
    return None


#: `market-data` Ruling 6.4a's linking window (sessions): statements of the two sides whose ex-dates are this close and that are not equal are ONE disputed action (Ruling 5.5 (1.7) item 3)
LINKING_WINDOW_SESSIONS = 20
Apart = Callable[[datetime.date, datetime.date], int]


def sessions_apart_of(conventions: ConventionSet, calendar_id: Optional[str]) -> Apart:
    """The number of sessions of `calendar_id` in `(earlier, later]`; the number of weekdays when the calendar is unknown or cannot count the interval."""
    calendars = getattr(getattr(conventions, "freshness", None), "calendars", None)

    def apart(a: datetime.date, b: datetime.date) -> int:
        lo, hi = (a, b) if a <= b else (b, a)
        if calendars is not None and calendar_id is not None:
            counted = calendars.count_after_calendar(calendar_id, lo, hi)
            if counted.missed is not None:
                return int(counted.missed)
        return sum(1 for n in range((hi - lo).days) if (lo + datetime.timedelta(days=n + 1)).weekday() < 5)

    return apart


def _same_action(a: _Item, b: _Item, apart: Apart) -> bool:
    """Two UNEQUAL statements of the two sides that are about one action, so the pair is one DISAGREEMENT and never two actions applied (Ruling 5.5 (1.7) items 2 and 3): they share the record date (both stated),
    the ex-date, or (a dividend) the pay date; or their ex-dates are at most 20 sessions apart (which also covers a split's equal ratio on another date: outside the window it is a different split)."""
    if a.kind != b.kind:
        return False
    if a.record is not None and a.record == b.record:
        return True
    if a.ex == b.ex:
        return True
    if a.kind == "CASH_DIVIDEND" and a.pay is not None and a.pay == b.pay:
        return True
    return apart(a.ex, b.ex) <= LINKING_WINDOW_SESSIONS


def _identify_actions(readings: Sequence[SourceReading], apart: Apart) -> Tuple[List[_Item], Dict[datetime.date, Fraction], Dict[datetime.date, str]]:
    """`(the dividend statements that apply, split ratios f_t multiplied per ex-date, the ex-dates a DISAGREEMENT names with their notes)`. A dividend is returned as its statement: its currency and any stated payment
    are converted to the price currency by the caller (Ruling 5.5 (1.8)).

    Ruling 5.5 (1.7), per statement and never per ex-date: (1) one side's own statements are deduplicated and are never matched with each other (a regular and a special dividend on one ex-date from one side are two
    actions, both applied); statements of the two sides that are equal (the record date compared only when both state it) pair one-to-one into one corroborated action; (2, 3) two unequal statements of DIFFERENT
    sides that share an identity date, or whose ex-dates are at most 20 sessions apart, are one action in DISAGREEMENT: neither is applied; (4) every other statement is a single-source action, applied (Ruling 5.5 (1.2)
    item 3)."""
    clusters: List[List] = []  # [item, set of sources, shown list]
    paid: Dict[int, Dict[str, Tuple[Optional[str], Fraction]]] = {}  # per cluster: the payment each side states
    for r in readings:
        got = _item_of(r)
        if got is None:
            continue
        item, shown = got
        for c in clusters:
            same_record = c[0].record is None or item.record is None or c[0].record == item.record
            if c[0].base() == item.base() and same_record:
                if c[0].record is None and item.record is not None:
                    c[0] = item
                break
        else:
            c = [item, set(), []]
            clusters.append(c)
        if r.source_id not in c[1]:
            c[1].add(r.source_id)
            c[2].append(f"{r.source_id}={shown}")
        if item.paid_amount is not None:  # which side states the paid fields is decided by market-data Ruling 4.5 (1.14), never by the order of the statements (CP4F-15)
            paid.setdefault(id(c), {})[r.source_id] = (item.paid_currency, item.paid_amount)
    ordered = sorted(clusters, key=lambda c: (c[0].ex, c[0].kind, str(c[0].pay), c[0].value))
    conflicted: set = set()
    notes: Dict[datetime.date, str] = {}  # every ex-date a disagreement names, with both statements
    for i, c in enumerate(ordered):
        stated = paid.get(id(c), {})
        if len(set(stated.values())) > 1:  # both sides state a payment and they differ: the dividend is in DISAGREEMENT (neither is used)
            conflicted.add(i)
            notes.setdefault(c[0].ex, f"{c[0].kind} of {c[0].ex.isoformat()}: the issuer's stated payments differ: " + "; ".join(f"{s}={cur} {_decimal_text(amt)}" for s, (cur, amt) in sorted(stated.items())))
        c[0] = dataclasses.replace(c[0], paid_currency=None, paid_amount=None) if not stated else dataclasses.replace(c[0], paid_currency=next(iter(stated.values()))[0], paid_amount=next(iter(stated.values()))[1])
    for i, (a, sources_a, shown_a) in enumerate(ordered):
        for j in range(i + 1, len(ordered)):
            b, sources_b, shown_b = ordered[j]
            if sources_a & sources_b or not _same_action(a, b, apart):
                continue  # one side states both (two real actions), or they are about different actions
            conflicted.update({i, j})
            for ex in (a.ex, b.ex):  # the chain breaks at EVERY date the two statements name (a ratio spanning either is unavailable)
                notes.setdefault(ex, f"{a.kind} around {min(a.ex, b.ex).isoformat()}: " + "; ".join(shown_a + shown_b))  # every source's statement stays in the lineage
    dividends: List[_Item] = []
    splits: Dict[datetime.date, Fraction] = {}
    for i, (item, _sources, _shown_list) in enumerate(ordered):
        if i in conflicted:
            continue
        if item.kind == "CASH_DIVIDEND":
            dividends.append(item)
        else:
            splits[item.ex] = splits.get(item.ex, Fraction(1)) * item.value
    return dividends, splits, notes


def _decimal_text(value: Fraction) -> str:
    """An exact amount as text for lineage: a decimal to 10 significant digits (a note, never an input)."""
    return str((Decimal(value.numerator) / Decimal(value.denominator)).normalize())


def _convert_dividends(items: Sequence[_Item], price_currency: Optional[str], port: MarketDataPort, conventions: ConventionSet
                       ) -> Tuple[Dict[datetime.date, Fraction], Dict[datetime.date, str], List[Span], Dict[datetime.date, str], List[FileRef]]:
    """Ruling 5.5 (1.8): each dividend in the ETF's PRICE currency `p`: (1) declared in `p`: as declared; (2) the issuer states a payment in `p`: that amount, as stated; (3) else the declared amount times the ECB cross
    `X(c -> p)` at the fixing of the ex-date (or the latest earlier one; market-data Rulings 1.3 and 1.6). Returns `(d per ex-date, notes per ex-date, the spans the fixing's freshness attaches to, the ex-dates at which
    the chain breaks for want of a rate with the reason note, the files the lookups read)`. A fixing missed 5 or more times gives no rate: the dividend is NOT applied, the chain breaks at its ex-date and every ratio
    spanning it is INSUFFICIENT_DATA + MISSING_FX_HISTORY."""
    d: Dict[datetime.date, Fraction] = {}
    notes: Dict[datetime.date, str] = {}
    spans: List[Span] = []
    breaks: Dict[datetime.date, str] = {}
    files: List[FileRef] = []
    for item in items:
        declared = f"{item.currency} {_decimal_text(item.value)}"
        if price_currency is None or item.currency == price_currency:
            amount = item.value
        elif item.paid_currency == price_currency and item.paid_amount is not None:
            amount = item.paid_amount
            notes[item.ex] = f"{notes.get(item.ex, '')}dividend declared {declared}, the issuer states it paid {price_currency} {_decimal_text(amount)}: used as stated; "
        else:
            lookup = port.fx_on(CurrencyCode(item.currency), CurrencyCode(price_currency), item.ex, conventions)
            files += list(lookup.consumed)
            state = fx_input_state(lookup)
            if state.state is SufficiencyState.INSUFFICIENT_DATA or lookup.rate is None:
                breaks[item.ex] = f"a dividend of {item.ex.isoformat()} declared {declared} has no ECB fixing to convert it ({state.note}); the chain breaks at its ex-date"
                continue
            amount = item.value * Fraction(lookup.rate)
            notes[item.ex] = (f"{notes.get(item.ex, '')}dividend converted from {declared} at the ECB fixing of {lookup.date_used.isoformat()} "
                              f"(rate {lookup.rate}, {lookup.missed_count} fixing(s) missed) to {price_currency} {_decimal_text(amount)}; ")
            if state.state is not SufficiencyState.AVAILABLE or state.reason is not None:
                spans.append(Span(item.ex, state.state, None if state.reason is None else state.reason.value, "",
                                  f"the fixing of {lookup.date_used.isoformat()} that converts the dividend of {item.ex.isoformat()} is {lookup.missed_count} fixing(s) stale"))
        d[item.ex] = d.get(item.ex, Fraction(0)) + amount
    return d, notes, spans, breaks, files


def build_proxy(listing_id: uuid.UUID, port: MarketDataPort, conventions: ConventionSet, end: datetime.date, calendar_id: Optional[str] = None) -> Optional[ProxyBuild]:
    """The proxy's book from the listing's RAW prints and corporate actions in `port`, up to `end`; None when the listing has no print. `calendar_id` is the ETF's calendar (the catalog entry's), which counts the sessions
    of Ruling 5.5 (1.7)'s linking window."""
    quotes = port.quotes(listing_id, datetime.date.min, end)
    by_day: Dict[datetime.date, List[SourceReading]] = {}
    for r in quotes.readings:
        obs = r.observation
        if isinstance(obs, QuoteObservation) and obs.is_print:
            by_day.setdefault(obs.value_date, []).append(r)
    if not by_day:
        return None
    actions = port.corporate_actions(listing_id, datetime.date.min, end)
    price_currencies = {r.observation.currency.code for r in quotes.readings if isinstance(r.observation, QuoteObservation)}  # type: ignore[attr-defined]
    dividend_items, splits, disputes = _identify_actions(actions.readings, sessions_apart_of(conventions, calendar_id))
    price_currency = next(iter(price_currencies)) if len(price_currencies) == 1 else None
    dividends, conversions, conversion_spans, no_rate, fx_files = _convert_dividends(dividend_items, price_currency, port, conventions)
    breaks: Dict[datetime.date, str] = dict(disputes)  # every ex-date at which the chain breaks, with the note
    spans: List[Span] = [Span(ex, SufficiencyState.INSUFFICIENT_DATA, "SOURCE_CONFLICT", "BENCHMARK_SOURCE_CONFLICT", f"a corporate action is in dispute ({note})") for ex, note in disputes.items()]
    for ex, note in no_rate.items():  # Ruling 5.5 (1.8) item 4: no rate, no conversion, no factor across the ex-date
        breaks.setdefault(ex, note)
        spans.append(Span(ex, SufficiencyState.INSUFFICIENT_DATA, "MISSING_FX_HISTORY", "", note))
    spans += conversion_spans
    days = sorted(by_day)
    out: List[DayLevel] = []
    tr: Optional[Fraction] = None
    prev_price: Optional[Fraction] = None
    prev_day: Optional[datetime.date] = None
    segment = 0
    for t in days:
        readings = by_day[t]
        rec = conventions.reconciler.reconcile(tuple(readings)) if len(readings) > 1 else None
        if rec is not None and rec.status is ReconciliationStatus.DISAGREEMENT:
            # Ruling 5.5 (1.6) item 4a: a disputed print is withheld for THAT DAY ONLY. The chain links around it (`prev_price`/`prev_day` stay at the last usable print, so a dividend or split dated on or
            # after it lands on the next usable print), and a grid date whose latest print it is has no level (SOURCE_CONFLICT). Never "every later print".
            out.append(DayLevel(t, None, DISAGREEMENT, f"BENCHMARK_SOURCE_CONFLICT: price of {t.isoformat()}: " + "; ".join(f"{r.source_id}={r.observation.price}" for r in readings), segment))  # type: ignore[attr-defined]
            continue
        used = readings[0] if rec is None else rec.used
        if used is not None and not getattr(used.observation, "recovered", True):  # an unrecovered value is not an admissible print (market-data Ruling 2.4 item 4): a lone one is as unusable as one the reconciler skips
            used = None
        if used is None:  # no usable reading (every reading unrecovered): the print is MISSING (normal staleness), not a conflict
            continue
        price = Fraction(used.observation.price)  # type: ignore[attr-defined]
        restart = ""
        if tr is None:
            tr = price
        else:
            assert prev_price is not None and prev_day is not None
            crossed = [x for x in sorted(breaks) if prev_day < x <= t]
            if crossed:
                restart = f"; chain restarted at this print: {breaks[crossed[0]]}"
                # item 4b: a disputed dividend or split breaks the chain at its ex-date. No factor exists for the link across it, so the levels from here on are a NEW chain (the restart of Ruling 5.1 (1.3),
                # based at this print); a ratio of levels in different segments is unavailable, and ratios inside one segment are what they would be if the dispute did not exist.
                segment += 1
                tr = price
            else:
                f = Fraction(1)
                d = Fraction(0)
                for ex in sorted(set(splits) | set(dividends)):
                    if prev_day < ex <= t:
                        f *= splits.get(ex, Fraction(1))
                        d += dividends.get(ex, Fraction(0))
                tr = tr * f * (price + d) / prev_price
                restart = "".join(f"; {conversions[ex].rstrip('; ')}" for ex in sorted(conversions) if prev_day < ex <= t)  # Ruling 5.5 (1.8) item 5: what each converted dividend came from, in the lineage
        out.append(DayLevel(t, tr, PROXY, f"TR from {len(dividends)} dividend(s), {len(splits)} split(s){restart}", segment))
        prev_price, prev_day = price, t
    first = quotes.readings[0].observation
    currencies = {r.observation.currency.code for r in quotes.readings if isinstance(r.observation, QuoteObservation)}
    lineage = first.lineage  # type: ignore[attr-defined]
    files = tuple(sorted(set(quotes.consumed) | set(actions.consumed) | set(fx_files)))
    return ProxyBuild(LevelBook(out, spans), files, quotes.readings[0].source_id, bool(lineage.is_synthetic), next(iter(currencies)) if len(currencies) == 1 else None)
