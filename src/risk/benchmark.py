"""The benchmark leg: levels at the grid dates, translated into the reporting currency, and the period returns (`risk/1.1` Rulings 5.1 to 5.4, 6.9; tech plan 17.4, 17.16).

For a grid date `g` the leg reads, from the market-data version M and the catalog entry of the selected benchmark:

    L(g)   = the level of the latest calculation day <= g on the index's own calendar       (Ruling 5.2)
    m_b(g) = the calculation days in (that day, g], counted in the calendar the catalog names  the missed count; the price thresholds:
             0 AVAILABLE | 1 AVAILABLE + STALE_DATA | 2 to 4 LIMITED + STALE_DATA | >= 5 INSUFFICIENT_DATA + STALE_DATA, detail BENCHMARK_STALE;
             no level on or before g: INSUFFICIENT_DATA + MISSING_BENCHMARK, detail BENCHMARK_NOT_COVERING_WINDOW; a calendar that cannot count it: INSUFFICIENT_DATA, no reason, CALENDAR_COVERAGE_GAP
    L_R(g) = L(g) x X(c_b -> R, g)   at the ECB fixing u(g) of the date, the SAME fixing the portfolio uses (Ruling 5.3); no translation when c_b is R
    b_k    = L_R(g_k) / L_R(g_{k-1}) - 1     exact

The level's state and the translation's combine (the worse wins; Ruling 5.3); the fixing's own staleness counts toward the leg. Everything is exact (`Fraction`): the level is the series' decimal, the fixing is the
port's exact rate. A series that cannot be used as a REFERENCE is refused as a whole, with its detail and `MISSING_BENCHMARK` (Ruling 5.4: a price-return series is not a usable reference point, more data of the same
kind does not fix it): not in the catalog or not in M (`BENCHMARK_SERIES_UNAVAILABLE`), not a total-return series (`BENCHMARK_NOT_TOTAL_RETURN`).

THE CATALOG says what the series cannot say about itself: its return basis, its calendar, the currency and the form of its levels. The series in M must agree with the entry (currency, levels): a disagreement is
`BENCHMARK_SERIES_UNAVAILABLE`, never a guess. NOT BUILT (and said so, not defaulted): a series published as RETURNS (Ruling 5.1 compounding; the contract carries no base level), and two admitted sources for one
benchmark (Ruling 5.7 reconciliation): the first is refused as unavailable with its note, the second raises `BenchmarkSourcesNotReconciled`.

Pure: no clock, no randomness, no float, no I/O. The reads go through the market-data port.
"""

from __future__ import annotations

import bisect
import dataclasses
import datetime
import uuid
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Optional, Sequence, Tuple, Union
from zoneinfo import ZoneInfo

from domain.catalogs import BenchmarkEntry, SeriesForm
from domain.currency import CurrencyCode
from marketdata.contracts import BenchmarkSeries, BenchmarkValueKind, CalendarDays, CalendarKind
from marketdata.conventions import ConventionSet
from marketdata.manifest import FileRef
from marketdata.port import LookupOutcome, MarketDataPort
from marketdata.states import LIMITED_FROM, NO_VALUE_FROM, fx_input_state
from performance.results import Cause, FreshEntry, FreshnessVector, Part
from performance.states import Valued
from product_contract.vocabulary import SufficiencyState
from risk import states as S
from risk.levels import LevelBook, PrecisionUndeclared, SourcePriorityError, book_of_series, build_proxy, reconcile_sources

AVAILABLE, LIMITED, INSUFFICIENT = SufficiencyState.AVAILABLE, SufficiencyState.LIMITED, SufficiencyState.INSUFFICIENT_DATA
ONE = Fraction(1)
NO_TRANSLATION = "NONE (benchmark already in R)"
TRANSLATED = "TRANSLATED_UNHEDGED (ECB fixing u(g))"
BENCHMARK_FRESH_KIND = "BENCHMARK"
CURRENCY_FRESH_KIND = "CURRENCY"


ECB_KEY = "ECB"  # the key the ECB calendar governs (market-data Ruling 1.1)


class BenchmarkSourcesNotReconciled(RuntimeError):
    """More than one admitted source serves the benchmark (Ruling 5.7): the precision-bound reconciliation is not built yet, so nothing is chosen."""


@dataclass(frozen=True)
class BenchmarkRefusal:
    """The whole series cannot be a reference: `reason` is the reason-code text (`MISSING_BENCHMARK`), `detail` one of Ruling 7.4's names, `consumed` the files read before the refusal."""

    reason: Optional[str]
    detail: str
    note: str
    consumed: Tuple[FileRef, ...] = ()
    entry_bound: bool = True  # False when the catalog entry does not describe the series that was read (CP4M-3): then no result may name the entry's values

    def part(self, ref: str) -> Part:
        cause = Cause(ref, INSUFFICIENT.value, self.reason, self.note, self.detail)
        return Part(ref, INSUFFICIENT, self.reason, (cause,))


@dataclass(frozen=True)
class BenchmarkLevel:
    """`L_R(g)` and everything behind it. `translated` is None exactly when the level is INSUFFICIENT_DATA."""

    grid_date: datetime.date
    date_used: Optional[datetime.date]
    missed: Optional[int]
    level: Optional[Fraction]
    fx_rate: Optional[Fraction]
    fx_date_used: Optional[datetime.date]
    fx_missed: Optional[int]
    translated: Optional[Fraction]
    valued: Valued
    segment: int = 0  # the chain of the level used (an ETF proxy broken at a disputed corporate action: Ruling 5.5 (1.6) item 4b); a published series is one segment

    @property
    def details(self) -> Tuple[str, ...]:
        return S.details_of(self.valued.causes)


@dataclass(frozen=True)
class BenchmarkPeriod:
    """`b_k` over `(start, end]` with its state: the worse of the two levels' states."""

    start: datetime.date
    end: datetime.date
    valued: Valued

    @property
    def exact(self) -> Optional[Fraction]:
        return self.valued.exact


def _level_part(ref: str, state: SufficiencyState, reason: Optional[str], note: str, detail: str) -> Part:
    if state is AVAILABLE and reason is None:
        return Part(ref, state, None, ())
    return Part(ref, state, reason, (Cause(ref, state.value, reason, note, detail),))


class BenchmarkLeg:
    """The levels of ONE benchmark in M, read lazily and cached by grid date. Build with `open_benchmark`."""

    def __init__(self, entry: BenchmarkEntry, book: LevelBook, source_id: Optional[str], series_synthetic: bool, series_files: Tuple[FileRef, ...], port: MarketDataPort, reporting: CurrencyCode,
                 conventions: ConventionSet, instant: Optional[datetime.datetime] = None):
        """`book` is the calculation days with the level used on each (one published series, two reconciled sources or an ETF proxy: `risk.levels`). `source_id` and `series_synthetic` are the SERIES' own (CP4M-3).
        `instant` is Current mode's `t` (Ruling 5.8): a calculation day or a fixing that is not yet due at `t` does not exist, and is not counted as missed."""
        self.entry = entry
        self.book = book
        self.source_id = source_id
        self.series_synthetic = series_synthetic
        self.reporting = reporting
        self.instant = instant
        self._port, self._conventions = port, conventions
        self._files = set(series_files)
        self._levels: Dict[datetime.date, BenchmarkLevel] = {}
        self.synthetic = bool(getattr(port, "contains_synthetic", True))
        self._calendars = getattr(conventions.freshness, "calendars", None)

    # -- Current mode: what exists at t (Ruling 5.8 items 2, 3 and 5) ----------------------------------------------------------------------
    def _close_at(self, calendar_id: Optional[str], day: datetime.date) -> Optional[datetime.datetime]:
        cal = None if self._calendars is None else self._calendars.by_id(calendar_id)
        if cal is None:
            return None
        t = cal.close_time(day) if cal.kind is CalendarKind.EXCHANGE_SESSIONS else cal.publication_time
        return None if t is None else datetime.datetime.combine(day, t, tzinfo=ZoneInfo(cal.timezone))

    def _exists(self, day: datetime.date) -> bool:
        """A calculation day exists at `t` only if its scheduled close is at or before `t`; with no instant (historical mode) every day exists."""
        if self.instant is None:
            return True
        at = self._close_at(self.entry.calendar_id, day)
        return at is None or at <= self.instant

    def _not_yet_due(self, calendar: Optional[CalendarDays], after: datetime.date, upto: datetime.date) -> int:
        """The calendar days in `(after, upto]` whose scheduled close (publication) is AFTER `t`: neither used nor missed (Ruling 5.8 item 5)."""
        if self.instant is None or calendar is None:
            return 0
        zone = ZoneInfo(calendar.timezone)
        n = 0
        for day in calendar.dates[bisect.bisect_right(calendar.dates, after):bisect.bisect_right(calendar.dates, upto)]:
            t = calendar.close_time(day) if calendar.kind is CalendarKind.EXCHANGE_SESSIONS else calendar.publication_time
            if t is not None and datetime.datetime.combine(day, t, tzinfo=zone) > self.instant:
                n += 1
        return n

    def _latest_due_fixing(self, g: datetime.date) -> datetime.date:
        """`g` itself in historical mode; in Current mode the latest ECB fixing day on or before `g` whose publication is at or before `t` (`g` if the calendar is unknown or none is due)."""
        if self.instant is None or self._calendars is None:
            return g
        ecb = self._calendars.governing(ECB_KEY)[0]
        if ecb is None:
            return g
        zone = ZoneInfo(ecb.timezone)
        i = bisect.bisect_right(ecb.dates, g)
        while i > 0:
            day = ecb.dates[i - 1]
            t = ecb.publication_time if ecb.kind is not CalendarKind.EXCHANGE_SESSIONS else ecb.close_time(day)
            if t is None or datetime.datetime.combine(day, t, tzinfo=zone) <= self.instant:
                return day
            i -= 1
        return g

    @property
    def currency_treatment(self) -> str:
        return NO_TRANSLATION if self.entry.currency == self.reporting.code else TRANSLATED

    @property
    def consumed(self) -> Tuple[FileRef, ...]:
        """Every file the leg has read so far: the benchmark file, the calendars that counted it, the FX files that translated it."""
        return tuple(sorted(self._files))

    def level_at(self, g: datetime.date) -> BenchmarkLevel:
        cached = self._levels.get(g)
        if cached is None:
            cached = self._levels[g] = self._read(g)
        return cached

    # -- one date ----------------------------------------------------------------------------------------------------------------------
    def _read(self, g: datetime.date) -> BenchmarkLevel:
        ref = f"benchmark:{self.entry.benchmark_id}@{g.isoformat()}"
        day = self.book.latest(g, self._exists if self.instant is not None else None)
        if day is None:
            part = _level_part(ref, INSUFFICIENT, S.MISSING_BENCHMARK, f"{S.BENCHMARK_NOT_COVERING_WINDOW}: no level of {self.entry.benchmark_id} on or before {g.isoformat()}", S.BENCHMARK_NOT_COVERING_WINDOW)
            return self._insufficient(g, None, None, None, part)
        if day.value is None:  # Ruling 5.7 (1.2) / 5.5 (1.2): a withheld day is not skipped; the grid date that needs it has no level until a resolution record exists
            part = _level_part(ref, INSUFFICIENT, S.SOURCE_CONFLICT, f"{S.BENCHMARK_SOURCE_CONFLICT}: the level of {day.day.isoformat()} is withheld ({day.note})", S.BENCHMARK_SOURCE_CONFLICT)
            return self._insufficient(g, day.day, None, None, part)
        used, level = day.day, day.value
        if level <= 0:  # a level is a positive number: a ratio over a non-positive level is not a return
            part = _level_part(ref, INSUFFICIENT, S.MISSING_BENCHMARK, f"{S.BENCHMARK_SERIES_UNAVAILABLE}: the level of {used.isoformat()} is not positive", S.BENCHMARK_SERIES_UNAVAILABLE)
            return self._insufficient(g, used, None, level, part)
        calendars = getattr(self._conventions.freshness, "calendars", None)
        counted = None if calendars is None else calendars.count_after_calendar(self.entry.calendar_id, used, g)
        if counted is not None and counted.calendar_ref is not None:
            self._files.add(counted.calendar_ref)
        if counted is None or counted.missed is None:
            notes = ("the conventions carry no calendar set",) if counted is None else counted.notes
            part = _level_part(ref, INSUFFICIENT, None, f"{S.CALENDAR_COVERAGE_GAP}: the calendar {self.entry.calendar_id!r} cannot count the interval to {g.isoformat()} ({'; '.join(notes)})",
                               S.CALENDAR_COVERAGE_GAP)
            return self._insufficient(g, used, None, level, part)
        m = counted.missed - self._not_yet_due(counted.calendar, used, g)  # Ruling 5.8 item 5: not yet due is not missed
        stale = f"{S.BENCHMARK_STALE}: {m} calculation day(s) of {self.entry.calendar_id} missed since the level of {used.isoformat()}"
        if m == 0:
            level_part = _level_part(ref, AVAILABLE, None, "", "")
        elif m < LIMITED_FROM:
            level_part = _level_part(ref, AVAILABLE, S.STALE_DATA, stale, S.BENCHMARK_STALE)
        elif m < NO_VALUE_FROM:
            level_part = _level_part(ref, LIMITED, S.STALE_DATA, stale, S.BENCHMARK_STALE)
        else:
            level_part = _level_part(ref, INSUFFICIENT, S.STALE_DATA, stale + ": the level is withheld", S.BENCHMARK_STALE)
        fresh = FreshEntry(BENCHMARK_FRESH_KIND, self.entry.benchmark_id, used, m, "CURRENT" if m == 0 else "STALE")
        if level_part.state is INSUFFICIENT:
            return self._insufficient(g, used, m, level, level_part, FreshnessVector((fresh,), ()))
        rate: Optional[Fraction] = None
        fx_used: Optional[datetime.date] = None
        fx_missed: Optional[int] = None
        parts = [level_part]
        entries = [fresh]
        if self.entry.currency != self.reporting.code:
            # Ruling 5.8 items 3 and 5 (CP4F-6): an ECB fixing exists at `t` only once PUBLISHED, and one not yet due is not missed. The rate is therefore looked up AT THE LATEST FIXING DUE AT `t` on or before `g`, so
            # the port counts only the fixings that are due (a fixing due but not in M_t IS missed: the port counts it). Subtracting the not-yet-due ones from the port's count after the lookup was wrong at the
            # 5-missed boundary: the port withholds the rate at 5 before any adjustment could apply.
            lookup = self._port.fx_on(CurrencyCode(self.entry.currency), self.reporting, self._latest_due_fixing(g), self._conventions)
            self._files.update(lookup.consumed)
            fx = fx_input_state(lookup)
            fx_ref = f"benchmark_fx:{self.entry.currency}->{self.reporting.code}@{g.isoformat()}"
            fx_used, fx_missed = lookup.date_used, lookup.missed_count
            fx_reason = None if fx.reason is None else fx.reason.value
            parts.append(_level_part(fx_ref, fx.state, fx_reason, fx.note, ""))
            entries.append(FreshEntry(CURRENCY_FRESH_KIND, f"{self.entry.currency}->{self.reporting.code}", fx_used, fx_missed, "CURRENT" if not fx_missed else "STALE"))
            if fx.state is not INSUFFICIENT:
                assert lookup.rate is not None and lookup.rate > 0
                rate = lookup.rate
        agg = S.combine(parts)
        fresh_vector = FreshnessVector(tuple(sorted(entries)), ())
        if agg.state is INSUFFICIENT:
            return BenchmarkLevel(g, used, m, level, rate, fx_used, fx_missed, None, Valued(INSUFFICIENT, agg.reason, None, agg.causes, fresh_vector), day.segment)
        translated = level * (rate if rate is not None else ONE)
        return BenchmarkLevel(g, used, m, level, rate, fx_used, fx_missed, translated, Valued(agg.state, agg.reason, translated, agg.causes, fresh_vector), day.segment)

    @staticmethod
    def _insufficient(g: datetime.date, used: Optional[datetime.date], m: Optional[int], level: Optional[Fraction], part: Part,
                      fresh: FreshnessVector = FreshnessVector()) -> BenchmarkLevel:
        agg = S.combine([part])
        return BenchmarkLevel(g, used, m, level, None, None, None, None, Valued(INSUFFICIENT, agg.reason, None, agg.causes, fresh))

    # -- returns ---------------------------------------------------------------------------------------------------------------------------
    def span_parts(self, dates: Sequence[datetime.date]) -> List[Part]:
        return [p for a, b in zip(dates, dates[1:]) for p in self.parts_between(a, b)]

    def parts_between(self, start: datetime.date, end: datetime.date) -> List[Part]:
        """What attaches to a ratio of levels of an ETF proxy that SPANS a corporate action (`a < ex <= b`, the dates of the two prints used): Ruling 5.5 (1.6) item 4b, a disputed action (no factor across it:
        INSUFFICIENT_DATA + SOURCE_CONFLICT); Ruling 5.5 (1.8) item 4, the freshness of the fixing that converts a foreign-currency dividend (AVAILABLE or LIMITED + STALE_DATA, or INSUFFICIENT_DATA +
        MISSING_FX_HISTORY with no rate used). Nothing for a ratio that does not span one, or when either level has no value (its own part says why)."""
        a, b = self.level_at(start), self.level_at(end)
        if a.translated is None or b.translated is None or a.date_used is None or b.date_used is None:
            return []
        parts = []
        for span in self.book.spans:
            if a.date_used < span.ex <= b.date_used:
                ref = f"benchmark_chain:{span.ex.isoformat()}"
                parts.append(_level_part(ref, span.state, span.reason, f"{span.detail or 'translation'}: {span.note}", span.detail))
        if a.segment != b.segment and not any(p.state is INSUFFICIENT for p in parts):  # a chain broken without a recorded span (a book built by hand)
            parts.append(_level_part(f"benchmark_chain:{start.isoformat()}..{end.isoformat()}", INSUFFICIENT, S.SOURCE_CONFLICT,
                                     f"{S.BENCHMARK_SOURCE_CONFLICT}: a corporate action of {self.entry.benchmark_id} between the levels of {a.date_used} and {b.date_used} is in dispute: there is no factor across it",
                                     S.BENCHMARK_SOURCE_CONFLICT))
        return parts

    def period(self, start: datetime.date, end: datetime.date) -> BenchmarkPeriod:
        """`b = L_R(end) / L_R(start) - 1` with the worse of the two levels' states (Ruling 6.9 reads the benchmark at `g_0` and `g_n` ONLY for a window return; an interior level is not an input)."""
        a, b = self.level_at(start), self.level_at(end)
        parts = [a.valued.as_part(f"level@{start.isoformat()}"), b.valued.as_part(f"level@{end.isoformat()}")]
        parts += self.parts_between(start, end)
        agg = S.combine(parts)
        fresh = a.valued.freshness.union(b.valued.freshness)
        if agg.state is INSUFFICIENT or a.translated is None or b.translated is None:
            return BenchmarkPeriod(start, end, Valued(INSUFFICIENT, agg.reason, None, agg.causes, fresh))
        return BenchmarkPeriod(start, end, Valued(agg.state, agg.reason, b.translated / a.translated - ONE, agg.causes, fresh))

    def period_returns(self, grid: Sequence[datetime.date]) -> Tuple[BenchmarkPeriod, ...]:
        """`b_1 ... b_n` on the grid points `g_0 ... g_n`: one period per consecutive pair, each from the two levels' translated values."""
        return tuple(self.period(a, b) for a, b in zip(grid, grid[1:]))


def _one_series(series: Sequence[BenchmarkSeries]) -> Optional[BenchmarkSeries]:
    """The ONE series the files of a benchmark make, or None. The RULE for several files of one series is market-data Ruling 0.1 (1.12) and lives in the release build (`ingest._require_disjoint_segments`: disjoint
    declared coverage, one identity, vintage-stable); a release that holds a benchmark in several files has already passed it, and this only ASSEMBLES the admitted segments (the port returns one series per file) and
    asserts what the build guarantees: one source, points disjoint and ascending, equal declared fields. Anything else (files of different sources: the reconciliation of Ruling 5.7, which is not built; or a store
    built by hand with overlap) is None, and nothing is picked."""
    if len(series) == 1:
        return series[0]
    if len({s.lineage.source_id for s in series}) != 1:
        return None
    ordered = sorted((s for s in series if s.points), key=lambda s: s.points[0].value_date)  # a file with no row up to the read's end holds nothing for it (its file is still cited)
    if not ordered:
        return series[0]
    first = ordered[0]
    if any((s.provider, s.currency, s.value_kind, s.licensing, s.lineage.is_synthetic) != (first.provider, first.currency, first.value_kind, first.licensing, first.lineage.is_synthetic)
           for s in ordered[1:]):
        return None
    points = tuple(p for s in ordered for p in s.points)
    if any(b.value_date <= a.value_date for a, b in zip(points, points[1:])):
        return None
    return dataclasses.replace(first, points=points)


def _by_source(series: Sequence[BenchmarkSeries]) -> Optional[Dict[str, BenchmarkSeries]]:
    """The files of a benchmark grouped by SOURCE, each source's files assembled into its one series (`_one_series`); None if one source's own files overlap or disagree."""
    groups: Dict[str, List[BenchmarkSeries]] = {}
    for s in series:
        groups.setdefault(s.lineage.source_id or "", []).append(s)
    out: Dict[str, BenchmarkSeries] = {}
    for source, group in sorted(groups.items()):
        one = _one_series(group)
        if one is None:
            return None
        out[source] = one
    return out


def open_benchmark(
    entry: Optional[BenchmarkEntry], benchmark_id: str, port: MarketDataPort, reporting: CurrencyCode, conventions: ConventionSet, end: datetime.date,
    instant: Optional[datetime.datetime] = None,
) -> Union[BenchmarkLeg, BenchmarkRefusal]:
    """The leg for the catalog `entry` of `benchmark_id`, or why the series cannot be a reference. `end` bounds the read (`g_n`); `instant` is Current mode's `t` (Ruling 5.8). The levels are one published series,
    two or more sources reconciled day by day (Ruling 5.7 (1.2), `risk.levels.reconcile_sources`) or, for a catalog entry that names an ETF listing, the proxy the engine builds (Ruling 5.5 (1.2))."""
    if entry is None:
        return BenchmarkRefusal(S.MISSING_BENCHMARK, S.BENCHMARK_SERIES_UNAVAILABLE, f"{S.BENCHMARK_SERIES_UNAVAILABLE}: {benchmark_id!r} is not an entry of the benchmark catalog")
    if entry.proxy_listing_id is not None:
        return _open_proxy(entry, port, reporting, conventions, end, instant)
    found = port.benchmark(benchmark_id, datetime.date.min, end)
    if found.outcome is LookupOutcome.NOT_IN_RELEASE or not found.series:
        return BenchmarkRefusal(S.MISSING_BENCHMARK, S.BENCHMARK_SERIES_UNAVAILABLE, f"{S.BENCHMARK_SERIES_UNAVAILABLE}: the market-data release holds no series for {benchmark_id!r}")
    by_source = _by_source(found.series)
    if by_source is None:
        raise BenchmarkSourcesNotReconciled(f"the files of a source of {benchmark_id!r} overlap or disagree in their declared fields: nothing is picked")
    files = found.consumed

    def refuse(detail: str, note: str, bound: bool = True) -> BenchmarkRefusal:
        return BenchmarkRefusal(S.MISSING_BENCHMARK, detail, f"{detail}: {note}", files, bound)

    sources = sorted(by_source)
    firsts = [by_source[s] for s in sources]
    # CP4M-3: the catalog entry describes ONE series. Bind it to what was read: the source, the synthetic flag and the currency must be the series' own, or the entry says nothing about this series (its basis,
    # its calendar, its currency would be a guess), and a result must not name catalog values that differ from what was read. For several sources the entry names the source whose level is carried.
    if entry.source_id not in by_source:
        return refuse(S.BENCHMARK_SERIES_UNAVAILABLE, f"the series read comes from source(s) {sources}, the catalog entry describes source {entry.source_id!r}", bound=False)
    if any(bool(s.lineage.is_synthetic) != entry.synthetic for s in firsts):
        return refuse(S.BENCHMARK_SERIES_UNAVAILABLE, f"a series read is synthetic={[bool(s.lineage.is_synthetic) for s in firsts]}, the catalog entry says synthetic={entry.synthetic} (a synthetic and a real series never meet, market-data Ruling 4.8)", bound=False)
    if any(s.currency.code != entry.currency for s in firsts):
        return refuse(S.BENCHMARK_SERIES_UNAVAILABLE, f"a series is in {[s.currency.code for s in firsts]}, the catalog says {entry.currency}", bound=False)
    if any(s.value_kind is not BenchmarkValueKind.LEVEL for s in firsts) or entry.series_form is not SeriesForm.LEVELS:
        return refuse(S.BENCHMARK_SERIES_UNAVAILABLE, "only a series of LEVELS is read: a series published as RETURNS is refused until one is put up for admission (Ruling 5.1 (1.3): its compounded base is 1 and cancels, "
                                                       "so no base level is needed, but none is built)")
    if not entry.return_basis.is_total_return:
        return refuse(S.BENCHMARK_NOT_TOTAL_RETURN, f"the catalog says {entry.return_basis.value}: a benchmark-relative metric needs a total-return series (Ruling 5.4)")
    declared = dict(entry.additional_sources)
    undeclared = [s for s in sources if s != entry.source_id and declared.get(s) != entry.return_basis.value]
    if undeclared:  # CP4F-4: the series contract carries no return basis, so a second source serving the id is bound by the CATALOG (Ruling 5.7: different bases are different benchmarks, never reconciled)
        return refuse(S.BENCHMARK_SERIES_UNAVAILABLE, f"source(s) {undeclared} serve {benchmark_id!r} but the catalog entry does not declare them with return_basis {entry.return_basis.value}: a copy of another basis is a different "
                                                     "benchmark and never fills or corroborates a day (Ruling 5.7)", bound=False)
    if len(by_source) == 1:
        book = book_of_series(firsts[0])
        carried = sources[0]
    else:
        records = getattr(port, "source_registry_records", None)
        priority = {} if records is None else {r.source_id: r.source_priority for r in records()}
        try:
            book = reconcile_sources(by_source, priority, entry.official_decimals, dict(entry.source_precisions))
        except (SourcePriorityError, PrecisionUndeclared) as error:  # undeclared precision, or a declaration the file contradicts, is no usable series (Ruling 5.7 (1.9) items 3 and 4)
            return refuse(S.BENCHMARK_SERIES_UNAVAILABLE, str(error))
        carried = min(sources, key=lambda s: priority[s])  # type: ignore[arg-type, return-value]
    return BenchmarkLeg(entry, book, carried, bool(by_source[carried].lineage.is_synthetic), files, port, reporting, conventions, instant)


def _open_proxy(entry: BenchmarkEntry, port: MarketDataPort, reporting: CurrencyCode, conventions: ConventionSet, end: datetime.date, instant: Optional[datetime.datetime]) -> Union[BenchmarkLeg, BenchmarkRefusal]:
    """An ETF proxy (Ruling 5.5 (1.2)): the series built from the listing's RAW prints and its corporate actions. The entry's `return_basis` must be a total return (the proxy IS gross total return)."""
    assert entry.proxy_listing_id is not None
    built = build_proxy(uuid.UUID(entry.proxy_listing_id), port, conventions, end, entry.calendar_id)
    if built is None:
        return BenchmarkRefusal(S.MISSING_BENCHMARK, S.BENCHMARK_SERIES_UNAVAILABLE, f"{S.BENCHMARK_SERIES_UNAVAILABLE}: the market-data release holds no print of the ETF {entry.proxy_listing_id} behind proxy {entry.benchmark_id!r}")

    def refuse(detail: str, note: str, bound: bool = True) -> BenchmarkRefusal:
        return BenchmarkRefusal(S.MISSING_BENCHMARK, detail, f"{detail}: {note}", built.consumed, bound)

    if built.synthetic != entry.synthetic:
        return refuse(S.BENCHMARK_SERIES_UNAVAILABLE, f"the ETF's prints are synthetic={built.synthetic}, the catalog entry says synthetic={entry.synthetic}", bound=False)
    if built.currency != entry.currency:
        return refuse(S.BENCHMARK_SERIES_UNAVAILABLE, f"the ETF trades in {built.currency}, the catalog says {entry.currency}", bound=False)
    if not entry.return_basis.is_total_return:
        return refuse(S.BENCHMARK_NOT_TOTAL_RETURN, f"the catalog says {entry.return_basis.value}: an ETF proxy is built as a total return and must be catalogued as one")
    return BenchmarkLeg(entry, built.book, built.source_id, built.synthetic, built.consumed, port, reporting, conventions, instant)
