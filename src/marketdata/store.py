"""In-memory implementation of `MarketDataPort` (Tech Plan §15.5: CP2a/CP2b storage).

Holds already-resolved observations for exactly one `MarketDataRelease`. It reads no file,
no clock and no environment; `marketdata.ingest.build_in_memory_market_data` fills it from
verified files. The PostgreSQL projection (CP2c) will implement the same port.

market-data/1.2 behaviour added here (the RULES live in the injected `ConventionSet`; the store only
applies their answers and records the lineage that belongs to a (datum, as-of)):

- a calendar-aware freshness policy counts missed sessions / fixings; a count that cannot be made, or
  that reaches 5, WITHHOLDS the number (outcome FRESHNESS_UNKNOWN / STALE_BEYOND_LIMIT) and says why;
- a listing with nothing in the version on a market that has no admitted source carries the cause
  NO_ADMITTED_SOURCE and freshness UNKNOWN (Ruling 4.7);
- every result says whether the version holds synthetic data (Ruling 4.8) and carries the notes the
  calendars and the FX rule produced (CALENDAR_COVERAGE_GAP, COUNTED_PAST_ACTUAL_THROUGH, provenance).
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, Iterable, List, Mapping, Optional, Set, Tuple

from domain.currency import CurrencyCode
from marketdata.conventions import (
    CalendarFreshnessPolicy,
    ConventionSet,
    FXOutcome,
    FXSelection,
    Withhold,
)
from marketdata.reconciliation import UNRECOVERED_AGREE
from marketdata.contracts import (
    AdjustedQuote,
    AdjustmentStatus,
    BenchmarkSeries,
    CorporateActionObservation,
    DataDelayStatus,
    Freshness,
    FreshnessState,
    FXObservation,
    QuoteObservation,
    Reconciliation,
    ReconciliationStatus,
    RiskFreeSeries,
    SourceReading,
)
from marketdata.manifest import FileRef, MarketDataRelease, SourceRecord, SourceRegistryNotPinnedError
from marketdata.market11 import NO_VALUE_FROM
from marketdata.port import (
    ActionSet,
    BenchmarkSet,
    FXLookup,
    FXSeries,
    LookupOutcome,
    QuoteLookup,
    QuoteSeries,
    RiskFreeLookup,
    RiskFreeSet,
    file_refs,
)
from marketdata.profiles import (
    ECB_CALENDAR_ID,
    SOURCES,
    ProfileNotAdmittedError,
    market_has_admitted_source,
    market_of_mic,
    require_listing_market,
)
from fractions import Fraction

_CONFLICT = (ReconciliationStatus.DISAGREEMENT, ReconciliationStatus.IMPLAUSIBLE)


@dataclass(frozen=True)
class BenchmarkEntry:
    source_id: str
    independence_group: str
    file_sha256: str
    series: BenchmarkSeries


@dataclass(frozen=True)
class RiskFreeEntry:
    source_id: str
    independence_group: str
    file_sha256: str
    series: RiskFreeSeries


@dataclass(frozen=True)
class FXFileWindow:
    """Ruling 1.1a item 5 (1.3): the window of one FX file that fixes its COVERAGE `[start, end]`, as computed
    at ingest from the manifest's request and its retrieval time (never from the dates the file holds).
    `start`: the requested start; None for a full-history file, whose coverage of a currency starts at the
    first date it holds for that currency. `end`: the earlier of the requested end and D_ret, the last
    fixing publishable (16:00 Europe/Berlin) by the retrieval time; None when it could not be determined
    (no ECB calendar covers it), and the date-set check is then UNVERIFIABLE for that file."""

    start: Optional[datetime.date]
    end: Optional[datetime.date]


@dataclass(frozen=True)
class SeriesExclusion:
    """A series that is NOT admitted (Ruling 3.1 consequences, 1.3): it supplies no readings, and its failure
    stays in lineage. The unit is the series: (listing, file) for a price series; (file, currency) for an FX series
    (market-data/1.7 Test V0-FX: `listing_id` is None and `currency` names the quote currency)."""

    listing_id: Optional[uuid.UUID]
    file_sha256: str
    test: str  # "V0" | "V0_FX_OFF_CALENDAR" | "V0_FX_AFTER_RETRIEVAL" | "V0_FX_DUPLICATE_DATE" (1.16)
    reason: str
    currency: Optional[str] = None


@dataclass(frozen=True)
class FileCoverage:
    """One file's coverage of one FX pair: `[first, last]` is the COVERAGE of Ruling 1.1a item 5 (1.3) and
    `dates` the dates the file holds, so the FX rule can tell "absent from this file inside its coverage" from
    "outside its coverage". `covered` False: the coverage could not be determined, and the date-set check
    does not run for the file (UNVERIFIABLE); `first` and `last` are then only the dates held."""

    file_sha256: str
    source_id: str
    independence_group: str
    first: datetime.date
    last: datetime.date
    dates: FrozenSet[datetime.date]
    covered: bool = False


@dataclass(frozen=True)
class StoreContents:
    """What an `InMemoryMarketData` holds, for a projection of the release to persist and rebuild from."""

    readings: Tuple[SourceReading, ...]
    benchmarks: Tuple[BenchmarkEntry, ...]
    adjusted: Tuple[AdjustedQuote, ...]
    fx_windows: Tuple[Tuple[str, FXFileWindow], ...]
    exclusions: Tuple[SeriesExclusion, ...]
    contains_synthetic: bool
    risk_free: Tuple[RiskFreeEntry, ...] = ()  # CP4b-2: appended last and defaulted, so every earlier construction and projection is unchanged


def _date_of(obs: object) -> datetime.date:
    if isinstance(obs, CorporateActionObservation):
        return obs.effective_date
    return obs.value_date  # type: ignore[attr-defined]


class _FXView:
    """What an FX rule sees: readings of a published pair on a date, the dates a pair has, and the
    per-file coverage. Callable like the old `PairLookup`."""

    def __init__(self, store: "InMemoryMarketData"):
        self._s = store

    def __call__(self, base: CurrencyCode, quote: CurrencyCode, day: datetime.date) -> Tuple[SourceReading, ...]:
        return tuple(self._s._fx.get((base, quote), {}).get(day, ()))

    def has_series(self, base: CurrencyCode, quote: CurrencyCode) -> bool:
        return (base, quote) in self._s._fx

    def dates(self, base: CurrencyCode, quote: CurrencyCode, upto: datetime.date) -> Tuple[datetime.date, ...]:
        # Ruling 1.1a item 6 (1.3): a REFUTED re-server file supplies NO rate on any date, so a date only
        # such a file holds is not a date with a rate
        return tuple(d for d, items in sorted(self._s._fx.get((base, quote), {}).items())
                     if d <= upto and any(r.observation.lineage.provenance != "REFUTED" for r in items))  # type: ignore[attr-defined]

    def refuted_only_dates(
        self, base: CurrencyCode, quote: CurrencyCode, after: datetime.date, upto: datetime.date,
    ) -> Tuple[datetime.date, ...]:
        """Dates `d` with `after < d <= upto` that ONLY a REFUTED re-server file holds (C2-9, market-data/1.4 Ruling
        1.1a item 6). Such a date has no rate, but it is a date a refuted file claims the publisher's file lacks: the
        FX rule must test it against the date-set check instead of carrying the rate forward over it."""
        return tuple(d for d, items in sorted(self._s._fx.get((base, quote), {}).items())
                     if after < d <= upto
                     and all(r.observation.lineage.provenance == "REFUTED" for r in items))  # type: ignore[attr-defined]

    def file_coverage(self, base: CurrencyCode, quote: CurrencyCode) -> Tuple[FileCoverage, ...]:
        return self._s._fx_files.get((base, quote), ())


class InMemoryMarketData:
    def __init__(
        self,
        release: MarketDataRelease,
        readings: Iterable[SourceReading] = (),
        benchmarks: Iterable[BenchmarkEntry] = (),
        adjusted: Iterable[AdjustedQuote] = (),
        exchange_of: Optional[Callable[[uuid.UUID], Optional[str]]] = None,
        contains_synthetic: bool = False,
        fx_windows: Optional[Mapping[str, FXFileWindow]] = None,
        exclusions: Iterable[SeriesExclusion] = (),
        source_records: Iterable[SourceRecord] = (),
        risk_free: Iterable[RiskFreeEntry] = (),
    ):
        self._release = release
        self._risk_free_in: Tuple[RiskFreeEntry, ...] = tuple(risk_free)
        self._source_records: Tuple[SourceRecord, ...] = tuple(sorted(source_records, key=lambda r: r.source_id))  # the registry records of the sources with a file in this M (None given: unknown)
        self._exchange_of = exchange_of
        self._fx_windows: Dict[str, FXFileWindow] = dict(fx_windows or {})
        self._exclusions: Dict[uuid.UUID, List[SeriesExclusion]] = {}
        self._fx_exclusions: List[SeriesExclusion] = []  # Test V0-FX (1.7): (file, currency) series
        for e in exclusions:
            if e.listing_id is None:
                self._fx_exclusions.append(e)
            else:
                self._exclusions.setdefault(e.listing_id, []).append(e)
        for items_ in self._exclusions.values():
            items_.sort(key=lambda e: (e.file_sha256, e.test, e.reason))
        self._fx_exclusions.sort(key=lambda e: (e.currency or "", e.file_sha256, e.test, e.reason))
        self._readings_in: Tuple[SourceReading, ...] = tuple(readings)
        self._benchmarks_in: Tuple[BenchmarkEntry, ...] = tuple(benchmarks)
        self._adjusted_in: Tuple[AdjustedQuote, ...] = tuple(adjusted)
        self._require_readings_admitted()  # before any index exists: no lookup of any kind can serve what this refuses
        readings = self._readings_in
        benchmarks = self._benchmarks_in
        adjusted = self._adjusted_in
        self._adjusted: Dict[uuid.UUID, List[AdjustedQuote]] = {}
        for a in adjusted:
            self._adjusted.setdefault(a.listing_id, []).append(a)
        for items in self._adjusted.values():
            items.sort(key=lambda a: (a.value_date, a.label.adjustment_status.value, a.lineage.file_sha256 or ""))
        order = {s: i for i, s in enumerate(release.source_precedence)}
        self._rank = lambda r: (order.get(r.source_id, len(order)), r.source_id, r.file_sha256)
        self._quotes: Dict[uuid.UUID, Dict[datetime.date, List[SourceReading]]] = {}
        self._fx: Dict[Tuple[CurrencyCode, CurrencyCode], Dict[datetime.date, List[SourceReading]]] = {}
        self._actions: Dict[uuid.UUID, List[SourceReading]] = {}
        synthetic = contains_synthetic
        for reading in readings:
            obs = reading.observation
            synthetic = synthetic or obs.lineage.is_synthetic  # type: ignore[attr-defined]
            if isinstance(obs, QuoteObservation):
                self._quotes.setdefault(obs.listing_id, {}).setdefault(obs.value_date, []).append(reading)
            elif isinstance(obs, FXObservation):
                key = (obs.base_currency, obs.quote_currency)
                self._fx.setdefault(key, {}).setdefault(obs.value_date, []).append(reading)
            else:
                assert isinstance(obs, CorporateActionObservation)
                self._actions.setdefault(obs.listing_id, []).append(reading)
        self._synthetic = synthetic
        for by_date in self._quotes.values():
            for items in by_date.values():
                items.sort(key=self._rank)
        for by_date in self._fx.values():
            for items in by_date.values():
                items.sort(key=self._rank)
        for items in self._actions.values():
            items.sort(key=lambda r: (_date_of(r.observation),) + self._rank(r))
        self._fx_files: Dict[Tuple[CurrencyCode, CurrencyCode], Tuple[FileCoverage, ...]] = {}
        for key, by_date in self._fx.items():
            per_file: Dict[str, Dict[str, object]] = {}
            for day, items in by_date.items():
                for r in items:
                    entry = per_file.setdefault(r.file_sha256, {"source": r.source_id,
                                                                "group": r.independence_group, "dates": set()})
                    entry["dates"].add(day)  # type: ignore[attr-defined]
            coverage: List[FileCoverage] = []
            for sha, e in sorted(per_file.items()):
                held = e["dates"]
                window = self._fx_windows.get(sha)
                if window is None or window.end is None:
                    # the coverage cannot be determined: the date-set check does not run (UNVERIFIABLE)
                    coverage.append(FileCoverage(sha, str(e["source"]), str(e["group"]), min(held), max(held),  # type: ignore[type-var,arg-type]
                                                 frozenset(held), covered=False))  # type: ignore[arg-type]
                else:
                    start = window.start if window.start is not None else min(held)  # type: ignore[type-var,arg-type]
                    coverage.append(FileCoverage(sha, str(e["source"]), str(e["group"]), start, window.end,
                                                 frozenset(held), covered=True))  # type: ignore[arg-type]
            self._fx_files[key] = tuple(coverage)
        self._benchmarks: Dict[str, List[BenchmarkEntry]] = {}
        for entry in benchmarks:
            self._benchmarks.setdefault(entry.series.benchmark_id, []).append(entry)
        for items in self._benchmarks.values():
            items.sort(key=lambda e: (self._rank(e),))  # type: ignore[arg-type]
        self._risk_free: Dict[CurrencyCode, List[RiskFreeEntry]] = {}
        for rf in self._risk_free_in:
            self._risk_free.setdefault(rf.series.currency, []).append(rf)
            self._synthetic = self._synthetic or rf.series.lineage.is_synthetic
        for items in self._risk_free.values():
            items.sort(key=lambda e: (self._rank(e),))  # type: ignore[arg-type]

    def _require_readings_admitted(self) -> None:
        """market-data/1.15 Ruling 7A.3 item 1 and Appendix A.5, applied where a REAL reading is served from. A terms attestation
        alone admits nothing, and the gate is per MARKET: a reading bound to a listing is usable only if the profile of its source
        covers the listing's market, is admitted, and lists the upstream in the market's primary order (`require_listing_market`).
        The ingest path refuses such a file already; this holds for a store built by hand and for one rebuilt from stored rows
        (`PostgresMarketData`), so that none of `quote_on`, `quotes`, `corporate_actions` or `adjusted_series` can serve it. An
        FX reading is bound to no listing, so only the source-level gate applies. Synthetic readings are exempt (Ruling 4.8)."""
        for r in self._readings_in:
            obs = r.observation
            if obs.lineage.is_synthetic:  # type: ignore[attr-defined]
                continue
            if isinstance(obs, (QuoteObservation, CorporateActionObservation)):
                require_listing_market(r.source_id, obs.listing_id, self._mic(obs.listing_id))
                continue
            profile = SOURCES.get(r.source_id)
            if profile is not None and profile.gate_refusal is not None:
                code, why = profile.gate_refusal
                raise ProfileNotAdmittedError(f"{code}: source {r.source_id!r} is not admitted: {why}", code)
        for a in self._adjusted_in:
            if not a.lineage.is_synthetic:
                require_listing_market(a.lineage.source_id or "", a.listing_id, self._mic(a.listing_id))

    @property
    def contains_synthetic(self) -> bool:
        """Ruling 4.8: True if the market-data version holds any synthetic data."""
        return self._synthetic

    @property
    def release(self) -> MarketDataRelease:
        return self._release

    def export(self) -> "StoreContents":
        """Everything the store was built from, in the order it was given: what a projection of the
        release (the PostgreSQL store) persists. Not part of the port."""
        return StoreContents(
            self._readings_in, self._benchmarks_in, self._adjusted_in,
            tuple(sorted(self._fx_windows.items())),
            tuple(e for lid in sorted(self._exclusions, key=str) for e in self._exclusions[lid])
            + tuple(self._fx_exclusions),
            self._synthetic, self._risk_free_in)

    # -- verification port (NOT part of MarketDataPort; analytics never reads it) ------------
    def adjusted_series(self, listing_id: uuid.UUID) -> Tuple[AdjustedQuote, ...]:
        """Vendor-adjusted rows for Test V2 and event checks. Never a price (Ruling 2.5)."""
        return tuple(self._adjusted.get(listing_id, ()))

    # -- port ---------------------------------------------------------------------------
    def release_id(self) -> str:
        return self._release.release_id

    def source_registry_records(self) -> Tuple[SourceRecord, ...]:
        """The full registry records (`SOURCES.json` entries) of every source with a file in this version, sorted by `source_id`; empty where the store was built without them
        (performance/1.12 Ruling 1.7 item 4: the manifest pins them by digest). FAILS CLOSED: a source that serves an observation of this version but has no record here cannot be pinned
        (and, for the build path, cannot have passed the terms check at use), so `SourceRegistryNotPinnedError` is raised before any value. A version that serves no observation has none."""
        have = {r.source_id for r in self._source_records}
        # CP4b-2: a risk-free series is served data too, so its source is pinned like a price source (the same fail-closed rule, the same synthetic parity)
        served = {r.source_id for r in self._readings_in} | {e.source_id for e in self._risk_free_in}
        if served - have:
            raise SourceRegistryNotPinnedError(f"the market-data version serves observations of source(s) {sorted(served - have)} with no source registry record")
        by_id = {r.source_id: r for r in self._source_records}
        for r in self._readings_in:  # CP4-10 parity with `ingest_file`: a reading is synthetic if and only if its source's record says so (the build path checks per file; a directly built store is checked here)
            if bool(r.observation.lineage.is_synthetic) != by_id[r.source_id].synthetic:
                raise SourceRegistryNotPinnedError(f"source {r.source_id!r}: a reading is synthetic={bool(r.observation.lineage.is_synthetic)} but its registry record says synthetic={by_id[r.source_id].synthetic}")
        for e in self._risk_free_in:
            if bool(e.series.lineage.is_synthetic) != by_id[e.source_id].synthetic:
                raise SourceRegistryNotPinnedError(f"source {e.source_id!r}: a risk-free series is synthetic={bool(e.series.lineage.is_synthetic)} but its registry record says synthetic={by_id[e.source_id].synthetic}")
        return self._source_records

    def quotes(self, listing_id: uuid.UUID, start: datetime.date, end: datetime.date) -> QuoteSeries:
        by_date = self._quotes.get(listing_id, {})
        chosen = tuple(r for d in sorted(by_date) if start <= d <= end for r in by_date[d])
        return QuoteSeries(listing_id, start, end, chosen, file_refs(chosen))

    def _mic(self, listing_id: uuid.UUID) -> Optional[str]:
        return None if self._exchange_of is None else self._exchange_of(listing_id)

    def quote_on(
        self, listing_id: uuid.UUID, as_of: datetime.date, conventions: ConventionSet
    ) -> QuoteLookup:
        by_date = self._quotes.get(listing_id)
        rule = conventions.price_of_date
        if not by_date:
            freshness = None
            cause_notes: List[str] = []
            market = market_of_mic(self._mic(listing_id))
            if market is not None and not market_has_admitted_source(market):
                # Ruling 4.7: INSUFFICIENT_DATA + MISSING_PRICE_HISTORY (mapped in states.py), cause recorded; freshness UNKNOWN.
                # market-data/1.16 Ruling 4.7 item 1: the CAUSE NO_ADMITTED_SOURCE is added only when M holds NO series of the listing at
                # all. An excluded series is a series, and its own failure (SERIES_CONTRADICTED, below) is then the cause: the lineage
                # names causes, not every true statement about the market.
                if not self._exclusions.get(listing_id):
                    cause_notes.append(f"NO_ADMITTED_SOURCE: market {market} has no admitted price source (Ruling 4.7)")
                freshness = Freshness(None, FreshnessState.UNKNOWN, DataDelayStatus.UNKNOWN, as_of,
                                      conventions.freshness.policy_id)
            for e in self._exclusions.get(listing_id, ()):
                # section 9B #3: every series CONTRADICTED is its own cause of NO_HISTORY; the failure is kept
                cause_notes.append(f"SERIES_CONTRADICTED: {e.test} on file {e.file_sha256[:12]}: {e.reason}")
            # section 9B: these causes share the NO_HISTORY outcome (one (state, reason) pair) and stay apart in
            # lineage; a listing the version holds nothing for, with no cause above, is NOT_IN_RELEASE
            outcome = LookupOutcome.NO_HISTORY if cause_notes else LookupOutcome.NOT_IN_RELEASE
            return QuoteLookup(outcome, listing_id, as_of, None, (), None,
                               freshness, "the release holds no admitted quote for this listing", rule.rule_id, (),
                               lineage_notes=tuple(cause_notes), synthetic=self._synthetic)
        history = {d: tuple(items) for d, items in by_date.items() if d <= as_of}
        selection = rule.select(history, as_of)
        considered = tuple(selection.considered)
        reconciliation = conventions.reconciler.reconcile(considered) if considered else None
        freshness = None
        outcome = LookupOutcome.NO_OBSERVATION
        selected = selection.selected
        basis = selection.basis
        if selected is None and reconciliation is not None and reconciliation.used is not None:
            selected, basis = reconciliation.used, reconciliation.selection_basis  # Ruling 4.3
        if reconciliation is not None and reconciliation.status in _CONFLICT:
            selected = None  # no value is used under a disagreement
        missed: Optional[int] = None
        notes_list: List[str] = []
        extra_refs: Set[FileRef] = set()
        if selected is not None:
            outcome = LookupOutcome.FOUND
            obs = selected.observation
            assert isinstance(obs, QuoteObservation) and obs.recovered
            policy = conventions.freshness
            if isinstance(policy, CalendarFreshnessPolicy):
                assessed = policy.assess_in(obs.timing, obs.value_date, as_of, self._mic(listing_id))
                freshness, missed = assessed.freshness, assessed.missed
                notes_list += assessed.notes
                if assessed.calendar_ref is not None:
                    extra_refs.add(assessed.calendar_ref)
                if assessed.withhold is Withhold.UNCOUNTABLE:
                    outcome, selected = LookupOutcome.FRESHNESS_UNKNOWN, None  # the number is suppressed
                elif assessed.withhold is Withhold.STALE_BEYOND_LIMIT:
                    outcome, selected = LookupOutcome.STALE_BEYOND_LIMIT, None
            else:
                freshness = policy.assess(obs.timing, obs.value_date, as_of)
        elif considered:
            outcome = LookupOutcome.NO_SELECTION
        elif selection.no_history:
            outcome = LookupOutcome.NO_HISTORY
            notes_list += self._no_history_causes(by_date, history, as_of, conventions)
        used_date = None if selected is None else selected.observation.value_date  # type: ignore[attr-defined]
        consumed = tuple(sorted(set(file_refs(considered)) | extra_refs))
        return QuoteLookup(outcome, listing_id, as_of, selected, considered,
                           reconciliation, freshness, basis, rule.rule_id,
                           consumed, date_used=used_date, missed_count=missed,
                           lineage_notes=tuple(notes_list), synthetic=self._synthetic)

    @staticmethod
    def _no_history_causes(
        by_date: Mapping[datetime.date, List[SourceReading]],
        history: Mapping[datetime.date, Tuple[SourceReading, ...]],
        as_of: datetime.date, conventions: ConventionSet,
    ) -> List[str]:
        """The cause(s) of a NO_HISTORY price, each kept apart in lineage (section 9B #3). They share one
        outcome and one (state, reason) pair; they differ in what a human is told."""
        notes: List[str] = []
        flat = [r for d in sorted(history) for r in history[d]]
        if not flat:
            notes.append(f"NO_PRINT_ON_OR_BEFORE_AS_OF: the earliest reading of the listing is dated "
                         f"{min(by_date).isoformat()}, after {as_of.isoformat()}")
            return notes
        raw = [r for r in flat if r.observation.lineage.adjustment_status is AdjustmentStatus.RAW]  # type: ignore[attr-defined]
        if not raw:
            notes.append("NO_RAW_READING: the readings on or before the date are all non-RAW (Ruling 2.3)")
        no_volume = [r for r in raw if not r.observation.is_print]  # type: ignore[attr-defined]
        if no_volume:
            notes.append(f"NO_PRINT: {len(no_volume)} RAW reading(s) without volume > 0 (Ruling 2.1)")
        unrecovered = [r for r in raw if r.observation.is_print and not r.observation.recovered]  # type: ignore[attr-defined]
        if unrecovered:
            notes.append(f"ONLY_UNRECOVERED_READINGS: {len(unrecovered)} reading(s) not recovered on the grid, "
                         "so none is an admissible print (Ruling 2.4 item 4a)")
            by_session: Dict[datetime.date, List[SourceReading]] = {}
            for r in unrecovered:
                by_session.setdefault(r.observation.value_date, []).append(r)  # type: ignore[attr-defined]
            for day in sorted(by_session):
                if len(by_session[day]) >= 2:
                    rec = conventions.reconciler.reconcile(tuple(by_session[day]))
                    if UNRECOVERED_AGREE in rec.flags and rec.status is None:
                        # lineage only: agreement does not make a value, a status or a state effect
                        notes.append(f"{UNRECOVERED_AGREE}: {len(by_session[day])} unrecovered readings of "
                                     f"{day.isoformat()} agree within their bounds; no value, no status")
        return notes

    def fx_series(
        self, base: CurrencyCode, quote: CurrencyCode, start: datetime.date, end: datetime.date
    ) -> FXSeries:
        by_date = self._fx.get((base, quote), {})
        chosen = tuple(r for d in sorted(by_date) if start <= d <= end for r in by_date[d])
        return FXSeries(base, quote, start, end, chosen, file_refs(chosen))

    def fx_on(
        self, base: CurrencyCode, quote: CurrencyCode, as_of: datetime.date,
        conventions: ConventionSet,
    ) -> FXLookup:
        rule = conventions.fx
        selection = rule.resolve(base, quote, as_of, _FXView(self), conventions.reconciler.reconcile)
        outcome = LookupOutcome(selection.outcome.value)
        if selection.outcome is FXOutcome.NO_OBSERVATION and base != quote and (
            (base, quote) not in self._fx
        ):
            outcome = LookupOutcome.NOT_IN_RELEASE
        considered = tuple(selection.considered)
        leg_recs: Tuple[Reconciliation, ...] = tuple(selection.reconciliations)
        if leg_recs:  # a rule that reconciled each leg itself (a cross has legs of two currencies)
            reconciliation: Optional[Reconciliation] = next(
                (r for r in leg_recs if r.status in _CONFLICT), leg_recs[0])
        else:
            reconciliation = conventions.reconciler.reconcile(considered) if considered else None
        if (
            selection.outcome is FXOutcome.NO_SELECTION and reconciliation is not None and not leg_recs
            and reconciliation.used is not None
            and reconciliation.status not in _CONFLICT
        ):  # several readings that agree: the reconciliation's primary order picks the value used
            fx_used = reconciliation.used.observation
            assert isinstance(fx_used, FXObservation)
            selection = FXSelection(FXOutcome.FOUND, Fraction(fx_used.rate), (reconciliation.used,),
                                    considered, reconciliation.selection_basis)
            outcome = LookupOutcome.FOUND
        rate = selection.rate
        legs = tuple(selection.legs)
        policy = conventions.freshness
        leg_freshness: Tuple[Freshness, ...] = ()
        missed: Optional[int] = None
        notes_list: List[str] = list(selection.lineage_notes)
        for ex in self._fx_exclusions:  # Test V0-FX (1.7): an excluded series supplies no rates, and the lineage says so
            if ex.currency in (base.code, quote.code):
                notes_list.append(f"{ex.test}: the {ex.currency} series of file {ex.file_sha256[:12]} is excluded whole: "
                                  f"{ex.reason}")
        extra_refs: Set[FileRef] = set()
        withhold: Optional[Withhold] = None
        for index, leg in enumerate(legs):
            obs = leg.observation
            assert isinstance(obs, FXObservation)
            if isinstance(policy, CalendarFreshnessPolicy):
                assessed = policy.assess_in(obs.timing, obs.value_date, as_of, ECB_CALENDAR_ID)
                leg_freshness += (assessed.freshness,)
                if index == 0:  # both legs carry one date, so one count
                    missed, withhold = assessed.missed, assessed.withhold
                    notes_list += assessed.notes
                    if assessed.calendar_ref is not None:
                        extra_refs.add(assessed.calendar_ref)
            else:
                leg_freshness += (policy.assess(obs.timing, obs.value_date, as_of),)
        used = None
        if legs:
            used = legs[0].observation.value_date  # type: ignore[attr-defined]
        if outcome is LookupOutcome.FOUND and withhold is Withhold.UNCOUNTABLE:
            outcome, rate, legs, used = LookupOutcome.FRESHNESS_UNKNOWN, None, (), None
        elif outcome is LookupOutcome.FOUND and withhold is Withhold.STALE_BEYOND_LIMIT:
            outcome, rate, legs, used = LookupOutcome.STALE_BEYOND_LIMIT, None, (), None
        consumed = tuple(sorted(set(file_refs(tuple(considered) + tuple(selection.legs))) | extra_refs))
        return FXLookup(outcome, base, quote, as_of, rate, legs,
                        considered, reconciliation, leg_freshness, selection.basis,
                        rule.rule_id, consumed, date_used=used, missed_count=missed,
                        lineage_notes=tuple(notes_list), synthetic=self._synthetic,
                        cross=selection.cross if outcome is LookupOutcome.FOUND else None,
                        leg_reconciliations=leg_recs, checks=tuple(selection.checks))

    def corporate_actions(
        self, listing_id: uuid.UUID, start: datetime.date, end: datetime.date
    ) -> ActionSet:
        items = self._actions.get(listing_id)
        if not items:
            return ActionSet(listing_id, start, end, LookupOutcome.NOT_IN_RELEASE, (), ())
        chosen = tuple(r for r in items if start <= _date_of(r.observation) <= end)
        outcome = LookupOutcome.FOUND if chosen else LookupOutcome.NO_OBSERVATION
        return ActionSet(listing_id, start, end, outcome, chosen, file_refs(chosen))

    def benchmark(self, benchmark_id: str, start: datetime.date, end: datetime.date) -> BenchmarkSet:
        entries = self._benchmarks.get(benchmark_id)
        if not entries:
            return BenchmarkSet(benchmark_id, LookupOutcome.NOT_IN_RELEASE, (), ())
        trimmed = []
        refs = set()
        for e in entries:
            points = tuple(p for p in e.series.points if start <= p.value_date <= end)
            trimmed.append(dataclasses.replace(e.series, points=points))
            lineage = e.series.lineage
            assert lineage.adapter_id is not None and lineage.adapter_version is not None
            refs.add(FileRef(e.file_sha256, lineage.adapter_id, lineage.adapter_version))
        outcome = LookupOutcome.FOUND if any(s.points for s in trimmed) else LookupOutcome.NO_OBSERVATION
        return BenchmarkSet(benchmark_id, outcome, tuple(trimmed), tuple(sorted(refs)))

    # -- risk-free rates (risk/1.0 section 4; CP4b-2) ----------------------------------------------------------------------------------------
    @staticmethod
    def _rf_ref(entry: RiskFreeEntry) -> FileRef:
        lineage = entry.series.lineage
        assert lineage.adapter_id is not None and lineage.adapter_version is not None
        return FileRef(entry.file_sha256, lineage.adapter_id, lineage.adapter_version)

    @staticmethod
    def _rf_one_series(entries: List[RiskFreeEntry]) -> Optional[RiskFreeSeries]:
        """The ONE series the entries of a currency make, or None. One entry is that series. Several entries of the SAME (source, series id) are the SEGMENTS of it that the release build admitted (market-data Ruling 0.1
        (1.12): `ingest._require_disjoint_segments` judges identity, vintage-stability and disjoint COVERAGE once, for every kind; this read-side join only assembles them and is NOT the rule). It stays a fail-closed
        assertion for a store built by hand: points that overlap or are not ascending, or a declared field that differs, are not one series (`NO_SELECTION`), and nothing is picked. Two series are not one either:
        the rule is one admitted series per currency (`risk/1.0` Ruling 4.1)."""
        if len({(e.source_id, e.series.series_id) for e in entries}) != 1:
            return None
        if len(entries) == 1:
            return entries[0].series
        ordered = sorted((e.series for e in entries), key=lambda s: s.points[0].value_date)
        first = ordered[0]
        static = lambda s: tuple(getattr(s, f.name) for f in dataclasses.fields(s) if f.name not in ("points", "lineage", "timing"))  # noqa: E731
        if any(static(s) != static(first) or bool(s.lineage.is_synthetic) != bool(first.lineage.is_synthetic) for s in ordered[1:]):  # a real and a synthetic segment are never one series (Ruling 4.8)
            return None
        points = tuple(p for s in ordered for p in s.points)
        if any(b.value_date <= a.value_date for a, b in zip(points, points[1:])):
            return None
        return dataclasses.replace(first, points=points)

    def risk_free_series(self, currency: CurrencyCode, start: datetime.date, end: datetime.date) -> RiskFreeSet:
        """The risk-free series of `currency` with its points in `[start, end]` (`risk/1.0` Ruling 4.1: ONE admitted series per currency; more than one is `NO_SELECTION`, and nothing is picked)."""
        entries = self._risk_free.get(currency, [])
        if not entries:
            return RiskFreeSet(currency, start, end, LookupOutcome.NOT_IN_RELEASE, (), ())
        refs = tuple(sorted({self._rf_ref(e) for e in entries}))
        series = self._rf_one_series(entries)
        if series is None:
            return RiskFreeSet(currency, start, end, LookupOutcome.NO_SELECTION, (), refs)
        points = tuple(p for p in series.points if start <= p.value_date <= end)
        if not points:  # a series has at least one point (the contract), so an empty range yields no series object
            return RiskFreeSet(currency, start, end, LookupOutcome.NO_OBSERVATION, (), refs)
        return RiskFreeSet(currency, start, end, LookupOutcome.FOUND, (dataclasses.replace(series, points=points),), refs)

    def risk_free_on(self, currency: CurrencyCode, as_of: datetime.date, conventions: ConventionSet) -> RiskFreeLookup:
        """The quote in force on `as_of`: the latest publication on or before it (`risk/1.0` Ruling 4.3: the quote known on that date, never a later one), and `m`, the publication dates in `(f, as_of]` counted in the
        series' own `RATE_PUBLICATIONS` calendar (Ruling 4.4). `m >= 5` withholds the number (`STALE_BEYOND_LIMIT`); a count that cannot be made withholds it too (`FRESHNESS_UNKNOWN`, with the cause
        `CALENDAR_COVERAGE_GAP` in the notes). The thresholds of `m` are the price and FX thresholds (one staleness scale); the STATE of a missed count 1 to 4 is mapped by the caller."""
        entries = self._risk_free.get(currency, [])
        if not entries:
            return RiskFreeLookup(LookupOutcome.NOT_IN_RELEASE, currency, as_of, None, None, None, None, (), (f"NO_RISK_FREE_SERIES: the release holds no risk-free series in {currency.code}",), self._synthetic)
        refs = tuple(sorted({self._rf_ref(e) for e in entries}))
        series = self._rf_one_series(entries)
        if series is None:
            return RiskFreeLookup(LookupOutcome.NO_SELECTION, currency, as_of, None, None, None, None, refs,
                                  (f"AMBIGUOUS_RISK_FREE_SERIES: {len(entries)} files serve {currency.code} ({', '.join(sorted(e.series.series_id for e in entries))}); the rule is one admitted series per currency",), self._synthetic)
        known = [p for p in series.points if p.value_date <= as_of]
        if not known:
            first = series.points[0].value_date
            return RiskFreeLookup(LookupOutcome.NO_HISTORY, currency, as_of, series, None, None, None, refs,
                                  (f"NO_QUOTE_ON_OR_BEFORE_AS_OF: the series {series.series_id} starts {first.isoformat()}, after {as_of.isoformat()}",), self._synthetic)
        point = known[-1]
        trimmed = dataclasses.replace(series, points=(point,))
        calendars = getattr(conventions.freshness, "calendars", None)
        if calendars is None:
            return RiskFreeLookup(LookupOutcome.FRESHNESS_UNKNOWN, currency, as_of, trimmed, point, point.value_date, None, refs,
                                  ("CALENDAR_COVERAGE_GAP: the conventions carry no calendar set, so publications cannot be counted",), self._synthetic)
        counted = calendars.count_after(series.series_id, point.value_date, as_of)
        notes = list(counted.notes)
        consumed = set(refs)
        if counted.calendar_ref is not None:
            consumed.add(counted.calendar_ref)
        if counted.calendar is not None and counted.calendar.calendar_id != series.calendar_id:
            return RiskFreeLookup(LookupOutcome.FRESHNESS_UNKNOWN, currency, as_of, trimmed, point, point.value_date, None, tuple(sorted(consumed)),
                                  tuple(notes) + (f"CALENDAR_COVERAGE_GAP: the series declares calendar {series.calendar_id!r} but {counted.calendar.calendar_id!r} governs it",), self._synthetic)
        if counted.missed is None:
            return RiskFreeLookup(LookupOutcome.FRESHNESS_UNKNOWN, currency, as_of, trimmed, point, point.value_date, None, tuple(sorted(consumed)), tuple(notes), self._synthetic)
        outcome = LookupOutcome.STALE_BEYOND_LIMIT if counted.missed >= NO_VALUE_FROM else LookupOutcome.FOUND
        return RiskFreeLookup(outcome, currency, as_of, trimmed, point, point.value_date, counted.missed, tuple(sorted(consumed)), tuple(notes), self._synthetic)
