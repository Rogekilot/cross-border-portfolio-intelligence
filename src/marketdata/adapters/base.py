"""The source-adapter interface and shared helpers (Tech Plan §15.1).

Allowed imports for any adapter module: stdlib (no network, process, clock or randomness
modules), `domain.currency`, `domain.ledger`, `domain.field_validation`, `marketdata.contracts`,
`marketdata.manifest`, `marketdata.adapters.base`. A boundary test enforces this.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum, unique
from typing import Dict, Iterable, Optional, Protocol, Tuple

from marketdata.contracts import (
    AdjustmentStatus,
    BenchmarkSeries,
    CalendarDays,
    ExternalIdentifiers,
    FXObservation,
    IdentityAssertion,
    LicenseStatus,
    LicensingMetadata,
    Lineage,
    RiskFreeSeries,
    SourceTiming,
    UnresolvedAdjustedQuote,
    UnresolvedCorporateAction,
    UnresolvedQuote,
    UsageScope,
)
from marketdata.manifest import DataKind, FileManifest


@unique
class IssueCode(Enum):
    UNPARSEABLE_ROW = "UNPARSEABLE_ROW"
    MISSING_FIELD = "MISSING_FIELD"
    NON_POSITIVE_VALUE = "NON_POSITIVE_VALUE"
    UNMAPPED_ACTION = "UNMAPPED_ACTION"
    UNDECLARED_CURRENCY = "UNDECLARED_CURRENCY"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    UNKNOWN_FORMAT = "UNKNOWN_FORMAT"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
    PRICE_OFF_GRID = "PRICE_OFF_GRID"  # kept for 1.0 compatibility; 1.1 marks values imprecise instead
    PROFILE_CHECK_FAILED = "PROFILE_CHECK_FAILED"  # Ruling 2.4 item 5: the profile is wrong; file not admitted
    VOLUME_UNIT_CHECK_FAILED = "VOLUME_UNIT_CHECK_FAILED"  # Ruling 2.6: file not admitted
    ROW_INCONSISTENT = "ROW_INCONSISTENT"  # Ruling 4.6 item 2: row not admitted
    CONSISTENCY_CHECK_FAILED = "CONSISTENCY_CHECK_FAILED"  # Ruling 4.6 item 3: flagged, rows kept
    PRICE_NOT_RECOVERED = "PRICE_NOT_RECOVERED"  # informational: kept, corroborates only
    CALENDAR_INVALID = "CALENDAR_INVALID"  # Ruling 5.3: a calendar file that breaks its format; refused
    MISSING_VALUE = "MISSING_VALUE"  # a published N/A: not an observation (Ruling 1.6); informational
    # 1.15 Ruling 7A.3 (c) 3, in every market from 1.16 (Test V0): two statements of one close for one parsed date. The SERIES (listing, file) is contradicted
    # (ingestion judges it AFTER identity resolution, from `AdapterOutput.dated_statements`): it supplies no reading, and the file stays in M. For an FX
    # file a fixing stated twice (a date, or a currency, stated twice) excludes every currency series (Test V0-FX, `AdapterOutput.contradicted`).
    DUPLICATE_SESSION_DATE = "DUPLICATE_SESSION_DATE"
    VENDOR_ID_UNRECOGNIZED = "VENDOR_ID_UNRECOGNIZED"  # 1.15 Ruling 7A.1 items 1 and 3: not a vendor id of the route; unresolved, flagged
    VENDOR_CODE_RANGE_UNEXPECTED = "VENDOR_CODE_RANGE_UNEXPECTED"  # 1.15 Ruling 7A.1 item 5: FLAG_ONLY, never refuses or resolves
    # raised by ingestion, not by adapters:
    UNRESOLVED_IDENTITY = "UNRESOLVED_IDENTITY"
    TRADING_CURRENCY_MISMATCH = "TRADING_CURRENCY_MISMATCH"
    SECURITY_CLASS_UNRESOLVED = "SECURITY_CLASS_UNRESOLVED"  # Appendix A.1 (1.4): informational; strict 2 dp applied


@dataclass(frozen=True)
class AdapterIssue:
    """A row that was not translated. Nothing is dropped silently."""

    row_ref: str
    code: IssueCode
    detail: str


@dataclass(frozen=True)
class DatedStatement:
    """One statement of a close for a session date, made by one row of a PRICE file: the identifiers the row would carry and the date it parses to. An
    adapter lists one for EVERY row whose date parses and which names a symbol, whether or not the row later passes its own checks (a row whose date parses
    but whose other field is bad still states that session: Addendum A.2 (iv)). A row whose date cannot be read states nothing and is not listed. Ingestion
    resolves the identifiers and counts (listing, file, date): two statements make the series CONTRADICTED (Test V0 (1.16), whatever the layout, the symbol
    or the alias). `ref` is the row reference the adapter would give the row (`symbol@date`)."""

    identifiers: ExternalIdentifiers
    value_date: datetime.date
    ref: str


@dataclass(frozen=True)
class ContradictedSeries:
    """An FX series the adapter refuses to translate because the FILE states a fixing twice (market-data/1.16 Test V0-FX: a date stated twice, or one
    currency stated twice for one date, in any layout). The adapter outputs no rate of the file; ingestion turns this into a `SeriesExclusion` per currency,
    so that the file stays in M and the failure stays in lineage. The series is named by its quote `currency`. `test` is the lineage test name
    (`V0_FX_DUPLICATE_DATE`), `cause` the reason label, `dates` the dates concerned and `names` the currencies stated twice, when it is a currency that was.
    (Price series are judged by ingestion from `AdapterOutput.dated_statements`, after identity resolution.)"""

    test: str
    cause: str
    dates: Tuple[datetime.date, ...]
    currency: str
    names: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.dates:
            raise ValueError("a contradicted series names the dates that contradict it")
        if not self.currency:
            raise ValueError("a contradicted series is named by its currency")


@dataclass(frozen=True)
class AdapterOutput:
    """What `translate` returns. Which tuple an adapter may fill is fixed by its kind."""

    quotes: Tuple[UnresolvedQuote, ...] = ()
    fx: Tuple[FXObservation, ...] = ()
    actions: Tuple[UnresolvedCorporateAction, ...] = ()
    benchmarks: Tuple[BenchmarkSeries, ...] = ()
    issues: Tuple[AdapterIssue, ...] = ()
    identities: Tuple[IdentityAssertion, ...] = ()
    adjusted: Tuple[UnresolvedAdjustedQuote, ...] = ()  # verification-only (Ruling 2.5)
    # verification-only RAW reference rows (all four price fields), supplied so Test V2 can fit an
    # adjusted series of the same upstream against them (market-data/1.2 section 9A #6). They are
    # never prices and never readings.
    reference: Tuple[UnresolvedAdjustedQuote, ...] = ()
    calendars: Tuple[CalendarDays, ...] = ()  # CALENDAR files only (Ruling 5.3)
    risk_free: Tuple[RiskFreeSeries, ...] = ()  # RISK_FREE files only (risk/1.0 section 4)
    contradicted: Tuple[ContradictedSeries, ...] = ()  # FX files only (market-data/1.16 Test V0-FX: a fixing stated twice)
    # QUOTE files only (market-data/1.16 Test V0): one entry per row whose date parses, refused rows included. None: ingestion derives them from the quotes
    # and adjusted rows, so a route that lists nothing is still judged on what it emits. Ingestion owns the duplicate test (after identity resolution).
    dated_statements: Optional[Tuple[DatedStatement, ...]] = None


class SourceAdapter(Protocol):
    adapter_id: str
    adapter_version: str
    source_id: str
    data_kind: DataKind
    payload_formats: Tuple[str, ...]

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput: ...


class NoAdapterError(LookupError):
    pass


class AdapterRegistry:
    """Finds the adapter for a file by (source_id, data_kind, payload_format), never by
    sniffing the content."""

    def __init__(self, adapters: Iterable[SourceAdapter] = ()):
        self._by_key: Dict[Tuple[str, DataKind, str], SourceAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: SourceAdapter) -> None:
        for fmt in adapter.payload_formats:
            key = (adapter.source_id, adapter.data_kind, fmt)
            if key in self._by_key:
                raise ValueError(f"two adapters claim {key}")
            self._by_key[key] = adapter

    def for_manifest(self, manifest: FileManifest) -> SourceAdapter:
        key = (manifest.source_id, manifest.data_kind, manifest.payload_format)
        try:
            return self._by_key[key]
        except KeyError:
            raise NoAdapterError(f"no adapter registered for {key}") from None


def lineage_for(
    manifest: FileManifest,
    adapter: SourceAdapter,
    source_record_ref: str,
    source_value_text: Optional[str] = None,
    precision_profile_id: Optional[str] = None,
    consistency_checks_passed: Optional[bool] = None,
    volume_unit_status: Optional[str] = None,
    adjustment_status: Optional[AdjustmentStatus] = None,
    adjustment_label_source: Optional[str] = None,
) -> Lineage:
    """Lineage built only from the manifest and the adapter; nothing is defaulted. The
    adjustment label is the manifest's declaration (possibly UNDECLARED). Upstream,
    independence group and label status are NOT set here: ingestion sets the first two from
    the source registry and verification sets the third (Ruling 3.1)."""
    request = dict(manifest.request)
    libraries = manifest.libraries
    return Lineage(
        source_value_text=source_value_text,
        precision_profile_id=precision_profile_id,
        consistency_checks_passed=consistency_checks_passed,
        volume_unit_status=volume_unit_status,
        market=manifest.market,
        library=libraries[0][0] if libraries else None,
        library_version=libraries[0][1] if libraries else None,
        library_function=request.get("function"),
        source=manifest.source_id,
        adjustment_status=adjustment_status or manifest.declared_adjustment,
        source_id=manifest.source_id,
        file_sha256=manifest.file_sha256,
        adapter_id=adapter.adapter_id,
        adapter_version=adapter.adapter_version,
        source_record_ref=source_record_ref,
        retrieved_at=manifest.retrieval_time,
        usage_scope=manifest.usage_scope,
        adjustment_anchor=manifest.adjustment_anchor,
        adjustment_label_source=adjustment_label_source,
    )


def timing_for(manifest: FileManifest) -> SourceTiming:
    """The source states no instant for a daily file; the delay status is the manifest's."""
    return SourceTiming(source_time=None, delay_status=manifest.declared_delay)


def licensing_for(manifest: FileManifest) -> LicensingMetadata:
    """Licensing follows the manifest's usage scope; display is never permitted for
    internal or synthetic data (PD-0028)."""
    if manifest.usage_scope is UsageScope.SYNTHETIC_TEST:
        return LicensingMetadata(LicenseStatus.SYNTHETIC_TEST, False)
    if manifest.usage_scope is UsageScope.LICENSED_DISPLAY:
        return LicensingMetadata(LicenseStatus.LICENSED, True)
    return LicensingMetadata(LicenseStatus.INTERNAL_DEVELOPMENT_ONLY, False)
