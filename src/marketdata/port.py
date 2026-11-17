"""`MarketDataPort` and `InstrumentResolverPort`: what analytics depends on (Tech Plan §5.2,
§15.1). Expressed purely in the normalized contracts. Read-only; bound to one
`MarketDataRelease`; same release and arguments give the same result. A missing value is
a typed outcome, never `None` or an exception, and the port never fills a gap.

This module imports no adapter, no vendor and no persistence implementation.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from fractions import Fraction
from enum import Enum, unique
from typing import Optional, Protocol, Tuple

from domain.currency import CurrencyCode
from marketdata.conventions import ConventionSet
from marketdata.contracts import (
    BenchmarkSeries,
    CorporateActionObservation,
    ExactRatioRate,
    ExternalIdentifiers,
    Freshness,
    InstrumentResolution,
    Reconciliation,
    RiskFreePoint,
    RiskFreeSeries,
    SourceReading,
)
from marketdata.manifest import FileRef


@unique
class LookupOutcome(Enum):
    FOUND = "FOUND"                    # a reading was selected by the injected rule
    NO_OBSERVATION = "NO_OBSERVATION"  # the subject is in the release; nothing for that date
    NO_SELECTION = "NO_SELECTION"      # readings exist; the rule chose none
    NOT_IN_RELEASE = "NOT_IN_RELEASE"  # the release holds nothing at all for the subject
    SAME_CURRENCY = "SAME_CURRENCY"    # FX only: from == to
    # market-data/1.2 (conventions Rulings 1.6, 2.4 item 4a, 5.2): no value is returned, and why.
    NO_HISTORY = "NO_HISTORY"                    # nothing admissible on or before the date (no print / no fixing)
    STALE_BEYOND_LIMIT = "STALE_BEYOND_LIMIT"    # 5 or more sessions / fixings missed: the number is suppressed
    FRESHNESS_UNKNOWN = "FRESHNESS_UNKNOWN"      # the interval cannot be counted (calendar gap): suppressed


def file_refs(readings: Tuple[SourceReading, ...]) -> Tuple[FileRef, ...]:
    """The (file hash, adapter id, adapter version) behind each reading, sorted, unique."""
    refs = set()
    for r in readings:
        lineage = r.observation.lineage  # type: ignore[attr-defined]
        if lineage.adapter_id is None or lineage.adapter_version is None:
            raise ValueError("an ingested observation must carry complete lineage")
        refs.add(FileRef(r.file_sha256, lineage.adapter_id, lineage.adapter_version))
    return tuple(sorted(refs))


@dataclass(frozen=True)
class QuoteSeries:
    """Every candidate reading per date in the range (all sources); no value chosen."""

    listing_id: uuid.UUID
    start: datetime.date
    end: datetime.date
    readings: Tuple[SourceReading, ...]  # sorted by (value_date, source precedence)
    consumed: Tuple[FileRef, ...]


@dataclass(frozen=True)
class QuoteLookup:
    outcome: LookupOutcome
    listing_id: uuid.UUID
    as_of: datetime.date
    selected: Optional[SourceReading]
    readings: Tuple[SourceReading, ...]
    reconciliation: Optional[Reconciliation]
    freshness: Optional[Freshness]
    selection_basis: str
    price_rule_id: str
    consumed: Tuple[FileRef, ...]
    # MD3: the session date actually used and the number of sessions missed since it
    # (Ruling 5.2); None until the session-calendar rule counts them (CP2b/CP2c).
    date_used: Optional[datetime.date] = None
    missed_count: Optional[int] = None
    # market-data/1.2 lineage that belongs to this (datum, as-of): causes such as NO_ADMITTED_SOURCE
    # (Ruling 4.7) and CALENDAR_COVERAGE_GAP (Ruling 5.3), the actual_through note, and whether the result
    # comes from synthetic data (Ruling 4.8; True if the market-data version holds any synthetic file).
    lineage_notes: Tuple[str, ...] = ()
    synthetic: bool = False


@dataclass(frozen=True)
class FXSeries:
    """Published-pair readings only, as published (nothing derived)."""

    base: CurrencyCode
    quote: CurrencyCode
    start: datetime.date
    end: datetime.date
    readings: Tuple[SourceReading, ...]
    consumed: Tuple[FileRef, ...]


@dataclass(frozen=True)
class FXLookup:
    outcome: LookupOutcome
    base: CurrencyCode
    quote: CurrencyCode
    as_of: datetime.date
    rate: Optional[Fraction]  # exact; never a rounded Decimal (Ruling 1.3)
    legs: Tuple[SourceReading, ...]
    readings: Tuple[SourceReading, ...]
    reconciliation: Optional[Reconciliation]
    leg_freshness: Tuple[Freshness, ...]  # one per leg, in leg order (a derived rate has several)
    selection_basis: str
    fx_rule_id: str
    consumed: Tuple[FileRef, ...]
    # MD3: the fixing date actually used and the missed-fixing count (Ruling 1.6); None
    # until the fixing-calendar rule counts them (CP2b/CP2c).
    date_used: Optional[datetime.date] = None
    missed_count: Optional[int] = None
    lineage_notes: Tuple[str, ...] = ()
    synthetic: bool = False
    # Ruling 1.3: a cross is the two linked same-date legs (`cross.as_fraction()` is `rate`); the
    # per-leg reconciliations; and the plausibility checks that ran (check id, PASS/FAIL/UNVERIFIABLE).
    cross: Optional[ExactRatioRate] = None
    leg_reconciliations: Tuple[Reconciliation, ...] = ()
    checks: Tuple[Tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ActionSet:
    listing_id: uuid.UUID
    start: datetime.date
    end: datetime.date
    outcome: LookupOutcome
    readings: Tuple[SourceReading, ...]  # sorted by (effective_date, source precedence)
    consumed: Tuple[FileRef, ...]


@dataclass(frozen=True)
class BenchmarkSet:
    benchmark_id: str
    outcome: LookupOutcome
    series: Tuple[BenchmarkSeries, ...]  # one per source, points trimmed to the range
    consumed: Tuple[FileRef, ...]


@dataclass(frozen=True)
class RiskFreeSet:
    """The risk-free series of one currency in the release, points trimmed to the range (`risk/1.0` Ruling 4.1: one admitted series per currency). `NOT_IN_RELEASE`: none; `NO_SELECTION`: more than one
    series serves the currency (the contract is one: fail closed, nothing is picked); `NO_OBSERVATION`: the series holds no point in the range."""

    currency: CurrencyCode
    start: datetime.date
    end: datetime.date
    outcome: LookupOutcome
    series: Tuple[RiskFreeSeries, ...]
    consumed: Tuple[FileRef, ...]


@dataclass(frozen=True)
class RiskFreeLookup:
    """The quote in force on a date (`risk/1.0` Ruling 4.3: the latest publication date `f` at or before `as_of`) and how stale it is (Ruling 4.4: `missed_count` is `m`, the publication dates in `(f, as_of]` counted
    in the series' own `RATE_PUBLICATIONS` calendar). `STALE_BEYOND_LIMIT`: `m >= 5`, the number is withheld; `FRESHNESS_UNKNOWN`: the calendar cannot count the interval (a gap: `CALENDAR_COVERAGE_GAP` in the notes).
    `series` is the series with only the quote used as its point (its unit, quote type, day count, tenor and the rest of the checklist travel with it)."""

    outcome: LookupOutcome
    currency: CurrencyCode
    as_of: datetime.date
    series: Optional[RiskFreeSeries]
    point: Optional[RiskFreePoint]
    date_used: Optional[datetime.date]
    missed_count: Optional[int]
    consumed: Tuple[FileRef, ...]
    lineage_notes: Tuple[str, ...] = ()
    synthetic: bool = False


class MarketDataPort(Protocol):
    """Pure reads over one release. The conventions are injected; none is hard-wired."""

    @property
    def contains_synthetic(self) -> bool:
        """REQUIRED (CP3-10): whether the release holds any synthetic file (market-data Ruling 4.8). A port that cannot say is not a `MarketDataPort`: the product
        service refuses a user portfolio against synthetic data, and that gate must not depend on an optional attribute."""
        ...

    def release_id(self) -> str: ...

    def quotes(
        self, listing_id: uuid.UUID, start: datetime.date, end: datetime.date
    ) -> QuoteSeries: ...

    def quote_on(
        self, listing_id: uuid.UUID, as_of: datetime.date, conventions: ConventionSet
    ) -> QuoteLookup: ...

    def fx_series(
        self, base: CurrencyCode, quote: CurrencyCode, start: datetime.date, end: datetime.date
    ) -> FXSeries: ...

    def fx_on(
        self, base: CurrencyCode, quote: CurrencyCode, as_of: datetime.date,
        conventions: ConventionSet,
    ) -> FXLookup: ...

    def corporate_actions(
        self, listing_id: uuid.UUID, start: datetime.date, end: datetime.date
    ) -> ActionSet: ...

    def benchmark(
        self, benchmark_id: str, start: datetime.date, end: datetime.date
    ) -> BenchmarkSet: ...

    def risk_free_on(
        self, currency: CurrencyCode, as_of: datetime.date, conventions: ConventionSet
    ) -> RiskFreeLookup: ...

    def risk_free_series(
        self, currency: CurrencyCode, start: datetime.date, end: datetime.date
    ) -> RiskFreeSet: ...


class InstrumentResolverPort(Protocol):
    """Identity reads. `as_of` is the date the identifiers are valid on (None: any date).
    Creating or correcting identity is a separate write interface, never part of this."""

    def resolve(
        self, identifiers: ExternalIdentifiers, as_of: Optional[datetime.date]
    ) -> InstrumentResolution: ...

    def trading_currency(self, listing_id: uuid.UUID) -> Optional[CurrencyCode]: ...

    def exchange_mic(self, listing_id: uuid.UUID) -> Optional[str]: ...

    def security_type(self, listing_id: uuid.UUID) -> Optional[str]: ...

