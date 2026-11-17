"""CP2 normalized market-data contracts (Tech Plan §13.H, §15.1; PRD §11.1-§11.4).

These are the shapes every adapter ends up populating and every analytics consumer
reads. This module contains no adapter, no parsing of any vendor payload, no vendor
name, no conversion and no lookup. Prices and rates are `Decimal`, never `float`.

What CP2a changed relative to the CP1 seam (Tech Plan §15.1), all engineer-proposed:

- observations carry `value_date` (the calendar date the value is for; a daily close is a
  date, not an instant). `observed_at` is optional.
- stored observations carry `SourceTiming` (intrinsic: when the source says it, and its
  delay status). `Freshness` (a state) is assigned at READ time by a policy and records
  the date it was assessed and the policy id. A state assigned at ingest would go stale.
- `Lineage` carries the file hash, adapter id/version, the source's own record reference,
  retrieval time and a `usage_scope` (PD-0028: internal-only data is marked as such on
  every observation; the default is the most restrictive).
- `AdjustmentStatus.UNDECLARED`: an adapter never defaults to RAW.
- `BenchmarkSeries` with `LicensingMetadata` (PRD §11.4).
- `InstrumentResolution` carries a status; ambiguity and conflict are states, not guesses.

Aligned with `market-data/1.0` (methodology/CP2_MARKET_DATA_CONVENTIONS.md, findings MD1-MD6),
which owns every RULE; this module holds data shapes only. No threshold, tolerance, rule
for choosing between sources, FX fixing or crossing, CNY/CNH treatment or freshness rule is
defined here. `value_date` is the source's LOCAL date label (Ruling 2.2): the session date of
a quote, the fixing date of an FX rate; it is never derived from a UTC conversion.
"""

from __future__ import annotations

import datetime
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
from fractions import Fraction
from typing import Optional, Tuple

from domain.currency import CurrencyCode, Money
from domain.field_validation import require_optional_type, require_type
from domain.ledger import SplitRatio


class ObservationRuleError(ValueError):
    """A type-correct observation that violates a content rule."""


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@unique
class FreshnessState(Enum):
    """Label only; no assignment rule is defined here (see module docstring)."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@unique
class DataDelayStatus(Enum):
    """PRD §11.2: delayed / EOD / live 'where known'."""

    LIVE = "LIVE"
    DELAYED = "DELAYED"
    END_OF_DAY = "END_OF_DAY"
    UNKNOWN = "UNKNOWN"


@unique
class AdjustmentStatus(Enum):
    """PRD §11.3: what a series has been adjusted for. `UNDECLARED` = the source did
    not say; it is never silently read as RAW."""

    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    DIVIDEND_ADJUSTED = "DIVIDEND_ADJUSTED"
    TOTAL_RETURN_ADJUSTED = "TOTAL_RETURN_ADJUSTED"
    UNDECLARED = "UNDECLARED"


@unique
class LabelStatus(Enum):
    """market-data/1.0 Ruling 3.1: the result of verifying a series' adjustment label from
    its own data. Assigned by the verification rule (CP2b/CP2c), never by an adapter; a
    `Lineage.label_status` of None means "not yet tested"."""

    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIABLE = "UNVERIFIABLE"


@unique
class PriceKind(Enum):
    """MD4. OFFICIAL_CLOSE is the exchange's own official close (Ruling 2.1), asserted only
    where the source is known to publish it; SOURCE_CLOSE is the source's close with no such
    assertion (the default: fail closed)."""

    OFFICIAL_CLOSE = "OFFICIAL_CLOSE"
    SOURCE_CLOSE = "SOURCE_CLOSE"


@unique
class UsageScope(Enum):
    """What the data may be used for (PD-0027, PD-0028). Free development sources are
    INTERNAL_DEVELOPMENT_ONLY; only a licensed source (OQ-04b) may be LICENSED_DISPLAY."""

    INTERNAL_DEVELOPMENT_ONLY = "INTERNAL_DEVELOPMENT_ONLY"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    LICENSED_DISPLAY = "LICENSED_DISPLAY"


@unique
class CorporateActionType(Enum):
    """market-data/1.0 Ruling 7.1. SYMBOL_CHANGE is an identifier-history record, not a
    position event (Ruling 7.2). UNSUPPORTED stores anything else (rights, spin-offs,
    mergers, tender offers, scrip, special distributions; PRD §12.3) with its dates: it
    changes no position and no price, and is flagged."""

    SPLIT = "SPLIT"
    CASH_DIVIDEND = "CASH_DIVIDEND"
    SYMBOL_CHANGE = "SYMBOL_CHANGE"
    UNSUPPORTED = "UNSUPPORTED"


def _require_aware(entity: object, name: str, value: object) -> None:
    require_type(entity, name, value, datetime.datetime)
    assert isinstance(value, datetime.datetime)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ObservationRuleError(f"{type(entity).__name__}.{name} must be timezone-aware")


def _require_optional_aware(entity: object, name: str, value: object) -> None:
    if value is not None:
        _require_aware(entity, name, value)


def _require_date(entity: object, name: str, value: object) -> None:
    if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
        raise ObservationRuleError(
            f"{type(entity).__name__}.{name} must be a date, not a datetime or other type"
        )


def _require_positive(entity: object, name: str, value: Decimal) -> None:
    require_type(entity, name, value, Decimal)
    if not value.is_finite() or value <= 0:
        raise ObservationRuleError(f"{type(entity).__name__}.{name} must be a finite Decimal > 0")


def _require_optional_nonblank(entity: object, name: str, value: object) -> None:
    require_optional_type(entity, name, value, str)
    if value is not None and not value.strip():  # type: ignore[union-attr]
        raise ObservationRuleError(f"{type(entity).__name__}.{name} must not be blank")


def _require_nonblank(entity: object, name: str, value: object) -> None:
    require_type(entity, name, value, str)
    assert isinstance(value, str)
    if not value.strip():
        raise ObservationRuleError(f"{type(entity).__name__}.{name} must not be blank")


def _require_sha256(entity: object, name: str, value: object) -> None:
    require_type(entity, name, value, str)
    assert isinstance(value, str)
    if not _SHA256_RE.match(value):
        raise ObservationRuleError(
            f"{type(entity).__name__}.{name} must be 64 lowercase hex characters"
        )


@dataclass(frozen=True)
class SourceTiming:
    """The intrinsic, stored half of freshness (PRD §11.2): the instant the source states
    (if any) and the delay status it declares. No state is assigned here."""

    source_time: Optional[datetime.datetime] = None
    delay_status: DataDelayStatus = DataDelayStatus.UNKNOWN

    def __post_init__(self) -> None:
        _require_optional_aware(self, "source_time", self.source_time)
        require_type(self, "delay_status", self.delay_status, DataDelayStatus)


@dataclass(frozen=True)
class Freshness:
    """An ASSESSED freshness (PRD §11.2), produced at read time by a policy. A state other
    than UNKNOWN must say which date it was assessed against and by which policy."""

    source_time: Optional[datetime.datetime]
    state: FreshnessState
    delay_status: DataDelayStatus = DataDelayStatus.UNKNOWN
    assessed_as_of: Optional[datetime.date] = None
    policy_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_optional_aware(self, "source_time", self.source_time)
        require_type(self, "state", self.state, FreshnessState)
        require_type(self, "delay_status", self.delay_status, DataDelayStatus)
        if self.assessed_as_of is not None:
            _require_date(self, "assessed_as_of", self.assessed_as_of)
        _require_optional_nonblank(self, "policy_id", self.policy_id)
        if self.state is not FreshnessState.UNKNOWN and (
            self.assessed_as_of is None or self.policy_id is None
        ):
            raise ObservationRuleError(
                "a Freshness state other than UNKNOWN needs assessed_as_of and policy_id"
            )


@dataclass(frozen=True)
class Lineage:
    """Where an observation came from and what adjustment it carries (PRD §11.3).
    `source` is an opaque, non-blank label. The remaining fields are optional so a
    hand-built observation is constructible, but ingestion requires `is_complete`.
    `usage_scope` defaults to the most restrictive scope (fail closed)."""

    source: str
    adjustment_status: AdjustmentStatus
    source_id: Optional[str] = None
    file_sha256: Optional[str] = None
    adapter_id: Optional[str] = None
    adapter_version: Optional[str] = None
    source_record_ref: Optional[str] = None
    retrieved_at: Optional[datetime.datetime] = None
    usage_scope: UsageScope = UsageScope.INTERNAL_DEVELOPMENT_ONLY
    adjustment_anchor: Optional[str] = None
    # MD3 (market-data/1.0). Set by ingestion from the source registry / verification, not
    # by an adapter: the known upstream and independence group (Ruling 4.1), the stated
    # adjustment method (Ruling 2.3), the label verification result (Ruling 3.1), the
    # declared per-source precision profile (Ruling 4.2) and the source's verbatim number
    # text (Ruling 2.4).
    upstream: Optional[str] = None
    independence_group: Optional[str] = None
    adjustment_method: Optional[str] = None
    label_status: Optional[LabelStatus] = None
    precision_profile_id: Optional[str] = None
    source_value_text: Optional[str] = None
    # market-data/1.1 (Rulings 2.6, 4.6): the listing's market as the manifest states it; the
    # wrapper library, its version and the function used (the shared-library safeguards);
    # the within-source arithmetic check (None = not applicable, False = failed and flagged);
    # and the volume-unit status ("VERIFIED" or "DECLARED_UNVERIFIED").
    market: Optional[str] = None
    library: Optional[str] = None
    library_version: Optional[str] = None
    library_function: Optional[str] = None
    consistency_checks_passed: Optional[bool] = None
    volume_unit_status: Optional[str] = None
    # market-data/1.2 Ruling 1.1a: the upstream a re-server DECLARES is a declaration until an exact
    # comparison with the publisher's own file confirms it: UNCONFIRMED, CONFIRMED or REFUTED (None:
    # not applicable). Set by ingestion, never by an adapter.
    provenance: Optional[str] = None
    # market-data/1.3 section 9B #4 (a): where a RAW label that the MANIFEST does not carry came from. An UNDECLARED
    # manifest of a call whose documentation the profile records (status DECLARED since market-data/1.16, MEMORY before it) is read as
    # that documentation says, and this field says so, so the label is never mistaken for one the file declared. None: the label is the file's.
    adjustment_label_source: Optional[str] = None

    @property
    def is_synthetic(self) -> bool:
        """Ruling 4.8: lineage `synthetic: true`."""
        return self.usage_scope is UsageScope.SYNTHETIC_TEST

    def __post_init__(self) -> None:
        _require_nonblank(self, "source", self.source)
        _require_optional_nonblank(self, "provenance", self.provenance)
        _require_optional_nonblank(self, "adjustment_label_source", self.adjustment_label_source)
        for name in ("market", "library", "library_version", "library_function", "volume_unit_status"):
            _require_optional_nonblank(self, name, getattr(self, name))
        if self.consistency_checks_passed is not None and not isinstance(self.consistency_checks_passed, bool):
            raise ObservationRuleError("consistency_checks_passed must be a bool or None")
        require_type(self, "adjustment_status", self.adjustment_status, AdjustmentStatus)
        for name in ("source_id", "adapter_id", "adapter_version", "source_record_ref",
                     "adjustment_anchor", "upstream", "independence_group",
                     "adjustment_method", "precision_profile_id"):
            _require_optional_nonblank(self, name, getattr(self, name))
        require_optional_type(self, "label_status", self.label_status, LabelStatus)
        require_optional_type(self, "source_value_text", self.source_value_text, str)
        if self.file_sha256 is not None:
            _require_sha256(self, "file_sha256", self.file_sha256)
        _require_optional_aware(self, "retrieved_at", self.retrieved_at)
        require_type(self, "usage_scope", self.usage_scope, UsageScope)

    @property
    def is_complete(self) -> bool:
        return all(
            getattr(self, n) is not None
            for n in ("source_id", "file_sha256", "adapter_id", "adapter_version",
                      "source_record_ref", "retrieved_at")
        )


@dataclass(frozen=True)
class ExternalIdentifiers:
    """What an adapter sees on an incoming row. None of these is a key; `listing_id` is
    (PD-0021 §1). At least one identifier must be present. `source_id` only scopes a
    `vendor_id` (a vendor id is meaningful only inside its source's scheme)."""

    figi: Optional[str] = None
    mic: Optional[str] = None
    ticker: Optional[str] = None
    vendor_id: Optional[str] = None
    source_id: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("figi", "mic", "ticker", "vendor_id", "source_id"):
            value = getattr(self, name)
            require_optional_type(self, name, value, str)
            if value is not None and not value.strip():
                raise ObservationRuleError(f"ExternalIdentifiers.{name} must not be blank")
        if all(getattr(self, n) is None for n in ("figi", "mic", "ticker", "vendor_id")):
            raise ObservationRuleError("ExternalIdentifiers needs at least one identifier")


@unique
class CalendarKind(Enum):
    EXCHANGE_SESSIONS = "EXCHANGE_SESSIONS"
    ECB_FIXINGS = "ECB_FIXINGS"
    RATE_PUBLICATIONS = "RATE_PUBLICATIONS"  # risk/1.0 Ruling 4.5: the publication dates of a risk-free series (`applies_to` = the series ids)


@dataclass(frozen=True)
class CalendarDays:
    """One hand-made calendar (market-data/1.2 Ruling 5.3). It is REFERENCE data: a versioned,
    content-hashed file in the market-data version M, never derived from a price or rate file.

    Inside `[covers_from, covers_to]` the file is COMPLETE: a date is a session (or fixing day) if
    and only if it is listed. Outside it nothing is known. `applies_to` lists the MICs (or `ECB`) the
    calendar governs. `dates` is an explicit list (never "weekdays minus holidays"). `actual_through`
    is the last date checked as actual rather than scheduled. Exchange calendars carry a default
    scheduled close and explicit early-close overrides; the ECB calendar carries the 14:10 fixing
    time and the 16:00 nominal publication time."""

    calendar_id: str
    kind: CalendarKind
    applies_to: Tuple[str, ...]
    timezone: str
    covers_from: datetime.date
    covers_to: datetime.date
    dates: Tuple[datetime.date, ...]
    actual_through: datetime.date
    evidence: str
    prepared_by: str
    prepared_on: datetime.date
    version_label: str
    lineage: Lineage
    default_close: Optional[datetime.time] = None
    early_closes: Tuple[Tuple[datetime.date, datetime.time], ...] = ()
    fixing_time: Optional[datetime.time] = None
    publication_time: Optional[datetime.time] = None

    def __post_init__(self) -> None:
        for name in ("calendar_id", "timezone", "evidence", "prepared_by", "version_label"):
            _require_nonblank(self, name, getattr(self, name))
        require_type(self, "kind", self.kind, CalendarKind)
        require_type(self, "lineage", self.lineage, Lineage)
        require_type(self, "applies_to", self.applies_to, tuple)
        if not self.applies_to or len(set(self.applies_to)) != len(self.applies_to):
            raise ObservationRuleError("applies_to must be a non-empty tuple without repeats")
        for m in self.applies_to:
            _require_nonblank(self, "applies_to[]", m)
        for name in ("covers_from", "covers_to", "actual_through", "prepared_on"):
            _require_date(self, name, getattr(self, name))
        if self.covers_from > self.covers_to:
            raise ObservationRuleError("covers_from is after covers_to")
        if not (self.covers_from <= self.actual_through <= self.covers_to):
            raise ObservationRuleError("actual_through must lie inside the coverage")
        require_type(self, "dates", self.dates, tuple)
        if not self.dates:
            raise ObservationRuleError("a calendar with no date is not a calendar")
        for d in self.dates:
            _require_date(self, "dates[]", d)
        if any(b <= a for a, b in zip(self.dates, self.dates[1:])):
            raise ObservationRuleError("dates must be strictly increasing")
        if self.dates[0] < self.covers_from or self.dates[-1] > self.covers_to:
            raise ObservationRuleError("every date must lie inside the coverage")
        if self.kind is CalendarKind.EXCHANGE_SESSIONS:
            if self.default_close is None or self.fixing_time is not None or self.publication_time is not None:
                raise ObservationRuleError("an exchange calendar needs default_close and no fixing/publication time")
            listed = set(self.dates)
            for d, t in self.early_closes:
                _require_date(self, "early_closes[]", d)
                if d not in listed:
                    raise ObservationRuleError(f"early close {d} is not a listed session")
                if not isinstance(t, datetime.time):
                    raise ObservationRuleError("early close times must be times")
            if len({d for d, _ in self.early_closes}) != len(self.early_closes):
                raise ObservationRuleError("an early close is listed twice")
        elif self.kind is CalendarKind.RATE_PUBLICATIONS:
            # risk/1.0 Ruling 4.5: the dates a risk-free series is published, with a nominal publication time (Current mode: a date counts as published only from that time)
            if self.publication_time is None or self.fixing_time is not None or self.default_close is not None or self.early_closes:
                raise ObservationRuleError("a rate-publication calendar needs a publication time and no fixing or close times")
        else:
            if (self.fixing_time is None or self.publication_time is None or self.default_close is not None
                    or self.early_closes):
                raise ObservationRuleError("an ECB calendar needs fixing and publication times and no close times")
            if self.applies_to != ("ECB",):
                raise ObservationRuleError("an ECB calendar applies to ECB")

    def covers(self, first: datetime.date, last: datetime.date) -> bool:
        """True iff the closed interval [first, last] lies wholly inside the coverage."""
        return self.covers_from <= first and last <= self.covers_to

    def close_time(self, day: datetime.date) -> Optional[datetime.time]:
        """The scheduled close of a listed session (an early-close override wins); None if `day`
        is not a session of an exchange calendar."""
        if self.kind is not CalendarKind.EXCHANGE_SESSIONS or day not in set(self.dates):
            return None
        for d, t in self.early_closes:
            if d == day:
                return t
        return self.default_close


def _check_recovery(entity: object, recovered: object, bound: object) -> None:
    """Ruling 2.4 item 4 / 4.2: a recovered value has bound 0; an unrecovered one a bound > 0
    (and may corroborate only)."""
    if not isinstance(recovered, bool):
        raise ObservationRuleError(f"{type(entity).__name__}.recovered must be a bool")
    require_type(entity, "precision_bound", bound, Decimal)
    assert isinstance(bound, Decimal)
    if not bound.is_finite() or bound < 0:
        raise ObservationRuleError(f"{type(entity).__name__}.precision_bound must be finite and >= 0")
    if recovered and bound != 0:
        raise ObservationRuleError("a recovered value has precision_bound 0")
    if not recovered and bound == 0 and type(entity).__name__ in ("QuoteObservation", "UnresolvedQuote"):
        raise ObservationRuleError("an unrecovered price needs a positive precision_bound")


def _check_field_bounds(entity: object, bounds: object) -> None:
    """The (open, high, low) bounds of a verification row: None, or three finite Decimals >= 0."""
    if bounds is None:
        return
    if not (isinstance(bounds, tuple) and len(bounds) == 3):
        raise ObservationRuleError(f"{type(entity).__name__}.field_bounds must be None or (open, high, low)")
    for b in bounds:
        require_type(entity, "field_bounds[]", b, Decimal)
        if not b.is_finite() or b < 0:
            raise ObservationRuleError(f"{type(entity).__name__}.field_bounds must be finite and >= 0")


def _check_volume(entity: object, volume: object) -> None:
    require_optional_type(entity, "volume", volume, Decimal)
    if volume is not None and (not volume.is_finite() or volume < 0):  # type: ignore[union-attr]
        raise ObservationRuleError(
            f"{type(entity).__name__}.volume must be a finite Decimal >= 0 or None"
        )


@dataclass(frozen=True)
class QuoteObservation:
    """An observed price for a resolved `listing_id` (populates `SecurityPrice`).

    `value_date` is the SESSION date (the source's local date label, Ruling 2.2). `volume`
    is stored because the print rule needs it (Ruling 2.1: a row is a print only if the
    source reports volume > 0); `volume=None` means the source reports none, and such a
    source may corroborate but cannot support valuation. `observed_at`, when known, is the
    session's scheduled close instant (from the session calendar, CP2b/CP2c)."""

    listing_id: uuid.UUID
    value_date: datetime.date
    price: Decimal
    currency: CurrencyCode
    timing: SourceTiming
    lineage: Lineage
    observed_at: Optional[datetime.datetime] = None
    volume: Optional[Decimal] = None
    price_kind: PriceKind = PriceKind.SOURCE_CLOSE
    recovered: bool = True
    precision_bound: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        require_type(self, "listing_id", self.listing_id, uuid.UUID)
        _require_date(self, "value_date", self.value_date)
        _require_positive(self, "price", self.price)
        require_type(self, "currency", self.currency, CurrencyCode)
        require_type(self, "timing", self.timing, SourceTiming)
        require_type(self, "lineage", self.lineage, Lineage)
        _require_optional_aware(self, "observed_at", self.observed_at)
        _check_volume(self, self.volume)
        require_type(self, "price_kind", self.price_kind, PriceKind)
        _check_recovery(self, self.recovered, self.precision_bound)

    @property
    def session_date(self) -> datetime.date:
        return self.value_date

    @property
    def is_print(self) -> bool:
        """Ruling 2.1's print test, as stated: volume reported and > 0."""
        return self.volume is not None and self.volume > 0


@dataclass(frozen=True)
class UnresolvedQuote:
    """What a quote adapter emits: the same facts, but identified by external
    identifiers. Resolution (not the adapter) supplies the `listing_id`."""

    identifiers: ExternalIdentifiers
    value_date: datetime.date
    price: Decimal
    currency: CurrencyCode
    timing: SourceTiming
    lineage: Lineage
    observed_at: Optional[datetime.datetime] = None
    volume: Optional[Decimal] = None
    price_kind: PriceKind = PriceKind.SOURCE_CLOSE
    recovered: bool = True
    precision_bound: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        require_type(self, "identifiers", self.identifiers, ExternalIdentifiers)
        _require_date(self, "value_date", self.value_date)
        _require_positive(self, "price", self.price)
        require_type(self, "currency", self.currency, CurrencyCode)
        require_type(self, "timing", self.timing, SourceTiming)
        require_type(self, "lineage", self.lineage, Lineage)
        _require_optional_aware(self, "observed_at", self.observed_at)
        _check_volume(self, self.volume)
        require_type(self, "price_kind", self.price_kind, PriceKind)
        _check_recovery(self, self.recovered, self.precision_bound)


@unique
class AdjustmentMethod(Enum):
    """market-data/1.1 Ruling 2.3: set ONLY by Test V2, never declared by a source or a manifest."""

    PROPORTIONAL = "PROPORTIONAL"
    SUBTRACTIVE = "SUBTRACTIVE"
    UNKNOWN = "UNKNOWN"


@unique
class AnchorKind(Enum):
    LATEST = "LATEST"      # 前复权 qfq: rows after the last event up to the vintage equal raw
    EARLIEST = "EARLIEST"  # 后复权 hfq: rows before the first event equal raw


@dataclass(frozen=True)
class AdjustmentLabel:
    """(status, method, anchor, vintage), Ruling 2.3. `anchor` None = not verified."""

    adjustment_status: AdjustmentStatus
    method: AdjustmentMethod
    anchor: Optional[AnchorKind]
    vintage: datetime.datetime

    def __post_init__(self) -> None:
        require_type(self, "adjustment_status", self.adjustment_status, AdjustmentStatus)
        require_type(self, "method", self.method, AdjustmentMethod)
        require_optional_type(self, "anchor", self.anchor, AnchorKind)
        _require_aware(self, "vintage", self.vintage)


@dataclass(frozen=True)
class UnresolvedAdjustedQuote:
    """A vendor-ADJUSTED daily row (all four price fields kept, for Test V2). VERIFICATION-ONLY:
    it is not a `QuoteObservation`, no price lookup returns it, and the analytics consumer cannot
    read it as a price (Ruling 2.5: a vendor-adjusted series is never a return input; valuation
    uses RAW only)."""

    identifiers: ExternalIdentifiers
    value_date: datetime.date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    currency: CurrencyCode
    label: AdjustmentLabel
    timing: SourceTiming
    lineage: Lineage
    precision_bound: Decimal = Decimal(0)
    # market-data/1.3 V2 (a'): the bounds of OPEN, HIGH and LOW (`precision_bound` is the close's). Set by the
    # adapter from each field's own profile on RAW reference rows; None = not supplied (V2 then cannot run).
    field_bounds: Optional[Tuple[Decimal, Decimal, Decimal]] = None

    def __post_init__(self) -> None:
        require_type(self, "identifiers", self.identifiers, ExternalIdentifiers)
        _require_date(self, "value_date", self.value_date)
        for name in ("open", "high", "low", "close"):
            require_type(self, name, getattr(self, name), Decimal)
            if not getattr(self, name).is_finite():
                raise ObservationRuleError(f"{name} must be finite")
        require_type(self, "currency", self.currency, CurrencyCode)
        require_type(self, "label", self.label, AdjustmentLabel)
        require_type(self, "timing", self.timing, SourceTiming)
        require_type(self, "lineage", self.lineage, Lineage)
        _check_recovery(self, False, self.precision_bound)
        _check_field_bounds(self, self.field_bounds)


@dataclass(frozen=True)
class AdjustedQuote:
    """The resolved form of `UnresolvedAdjustedQuote` (verification-only; see there)."""

    listing_id: uuid.UUID
    value_date: datetime.date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    currency: CurrencyCode
    label: AdjustmentLabel
    timing: SourceTiming
    lineage: Lineage
    precision_bound: Decimal = Decimal(0)
    field_bounds: Optional[Tuple[Decimal, Decimal, Decimal]] = None  # see UnresolvedAdjustedQuote

    def __post_init__(self) -> None:
        require_type(self, "listing_id", self.listing_id, uuid.UUID)
        _require_date(self, "value_date", self.value_date)
        for name in ("open", "high", "low", "close"):
            require_type(self, name, getattr(self, name), Decimal)
        require_type(self, "currency", self.currency, CurrencyCode)
        require_type(self, "label", self.label, AdjustmentLabel)
        require_type(self, "timing", self.timing, SourceTiming)
        require_type(self, "lineage", self.lineage, Lineage)
        _check_recovery(self, False, self.precision_bound)
        _check_field_bounds(self, self.field_bounds)


@dataclass(frozen=True)
class FXObservation:
    """An observed rate for an ordered currency pair (populates `FXRate`): `rate` is
    units of `quote_currency` per one unit of `base_currency`, EXACTLY as the source
    publishes it (no inversion, no crossing, no CNY/CNH mapping: those are conventions
    owned by the quant-analyst). `rate_basis` is the source's own label for the fixing.
    This is the type through which FX conversion enters (Tech Plan §13.E); it is never
    derived from a ledger `CURRENCY_CONVERSION` (ledger-replay/1.1 §5A.7)."""

    base_currency: CurrencyCode
    quote_currency: CurrencyCode
    value_date: datetime.date
    rate: Decimal
    timing: SourceTiming
    lineage: Lineage
    rate_basis: str
    observed_at: Optional[datetime.datetime] = None

    def __post_init__(self) -> None:
        require_type(self, "base_currency", self.base_currency, CurrencyCode)
        require_type(self, "quote_currency", self.quote_currency, CurrencyCode)
        if self.base_currency == self.quote_currency:
            raise ObservationRuleError("FXObservation needs two different currencies")
        _require_date(self, "value_date", self.value_date)
        _require_positive(self, "rate", self.rate)
        require_type(self, "timing", self.timing, SourceTiming)
        require_type(self, "lineage", self.lineage, Lineage)
        _require_nonblank(self, "rate_basis", self.rate_basis)
        _require_optional_aware(self, "observed_at", self.observed_at)

    @property
    def fixing_date(self) -> datetime.date:
        return self.value_date


@dataclass(frozen=True)
class ExactRatioRate:
    """MD2 / Ruling 1.3: a derived (cross) rate is NEVER a rounded `Decimal`. It is the
    ordered pair of its two published legs, and its value is the exact ratio
    `numerator.rate / denominator.rate` in units of `quote_currency` per one unit of
    `base_currency`. With both legs quoted per one unit of a common currency `c` (for the
    ECB, EUR): numerator = X(c->quote), denominator = X(c->base). Both legs must carry the
    SAME fixing date (legs from two dates are never combined) and the same leg base. Both
    lineage records stay reachable through the legs. Which legs to pair, and through which
    currency, is the FX rule's decision (market-data/1.0), not this type's."""

    numerator: FXObservation
    denominator: FXObservation

    def __post_init__(self) -> None:
        require_type(self, "numerator", self.numerator, FXObservation)
        require_type(self, "denominator", self.denominator, FXObservation)
        if self.numerator.base_currency != self.denominator.base_currency:
            raise ObservationRuleError("both legs must be quoted per one unit of the same currency")
        if self.numerator.value_date != self.denominator.value_date:
            raise ObservationRuleError("both legs must carry the same fixing date")
        if self.numerator.quote_currency == self.denominator.quote_currency:
            raise ObservationRuleError("the legs must have different quote currencies")

    @property
    def base_currency(self) -> CurrencyCode:
        return self.denominator.quote_currency

    @property
    def quote_currency(self) -> CurrencyCode:
        return self.numerator.quote_currency

    @property
    def fixing_date(self) -> datetime.date:
        return self.numerator.value_date

    def as_fraction(self) -> Fraction:
        return Fraction(self.numerator.rate) / Fraction(self.denominator.rate)


_ACTION_FIELDS = (
    "split_ratio", "amount_per_unit", "pay_date", "record_date", "paid_currency",
    "issuer_fx_rate", "old_ticker", "new_ticker", "unsupported_label", "paid_amount",
)
_ACTION_ALLOWED = {
    CorporateActionType.SPLIT: {"split_ratio"},
    CorporateActionType.CASH_DIVIDEND: {
        "amount_per_unit", "pay_date", "record_date", "paid_currency", "issuer_fx_rate", "paid_amount"},
    CorporateActionType.SYMBOL_CHANGE: {"old_ticker", "new_ticker"},
    CorporateActionType.UNSUPPORTED: {"unsupported_label"},
}
_ACTION_REQUIRED = {
    CorporateActionType.SPLIT: {"split_ratio"},
    CorporateActionType.CASH_DIVIDEND: {"amount_per_unit", "pay_date"},
    CorporateActionType.SYMBOL_CHANGE: {"old_ticker", "new_ticker"},
    CorporateActionType.UNSUPPORTED: {"unsupported_label"},
}


def _check_action_shape(entity: object) -> None:
    """market-data/1.0 Ruling 7.1: which fields each action type carries. `effective_date`
    is the EX-DATE for SPLIT and CASH_DIVIDEND (the effective date for SYMBOL_CHANGE)."""
    action_type = getattr(entity, "action_type")
    require_type(entity, "action_type", action_type, CorporateActionType)
    require_optional_type(entity, "split_ratio", entity.split_ratio, SplitRatio)  # type: ignore[attr-defined]
    require_optional_type(entity, "amount_per_unit", entity.amount_per_unit, Money)  # type: ignore[attr-defined]
    for name in ("pay_date", "record_date"):
        value = getattr(entity, name)
        if value is not None:
            _require_date(entity, name, value)
    require_optional_type(entity, "paid_currency", entity.paid_currency, CurrencyCode)  # type: ignore[attr-defined]
    rate = entity.issuer_fx_rate  # type: ignore[attr-defined]
    require_optional_type(entity, "issuer_fx_rate", rate, Decimal)
    if rate is not None and (not rate.is_finite() or rate <= 0):
        raise ObservationRuleError("issuer_fx_rate must be a finite Decimal > 0")
    declared = getattr(entity, "amount_per_unit", None)
    if entity.paid_currency is not None and declared is not None and entity.paid_currency == declared.currency:  # type: ignore[attr-defined]
        raise ObservationRuleError("paid_currency must differ from the declared currency (market-data Ruling 7.1 (1.14)): a payment in the declared currency IS the declared amount")
    paid = entity.paid_amount  # type: ignore[attr-defined]
    require_optional_type(entity, "paid_amount", paid, Decimal)
    if paid is not None and (not paid.is_finite() or paid <= 0 or entity.paid_currency is None):  # type: ignore[attr-defined]
        raise ObservationRuleError("paid_amount must be a finite Decimal > 0 and names its paid_currency")
    for name in ("old_ticker", "new_ticker", "unsupported_label"):
        _require_optional_nonblank(entity, name, getattr(entity, name))
    present = {n for n in _ACTION_FIELDS if getattr(entity, n) is not None}
    missing = _ACTION_REQUIRED[action_type] - present
    extra = present - _ACTION_ALLOWED[action_type]
    if missing:
        raise ObservationRuleError(f"a {action_type.value} needs {sorted(missing)}")
    if extra:
        raise ObservationRuleError(f"a {action_type.value} must not carry {sorted(extra)}")
    amount = entity.amount_per_unit  # type: ignore[attr-defined]
    if amount is not None and amount.amount <= 0:
        raise ObservationRuleError("amount_per_unit must be > 0")
    if action_type is CorporateActionType.SYMBOL_CHANGE and entity.old_ticker == entity.new_ticker:  # type: ignore[attr-defined]
        raise ObservationRuleError("a SYMBOL_CHANGE needs two different tickers")


@dataclass(frozen=True)
class CorporateActionObservation:
    """An observed corporate action for a resolved `listing_id` (populates
    `CorporateAction`), per market-data/1.0 Ruling 7.1:

    - SPLIT: one observation per listing per ex-date, carrying the COMBINED ratio
      (10送3转增2 is (15, 10)); `effective_date` is the ex-date.
    - CASH_DIVIDEND: `amount_per_unit` in the DECLARED currency, per unit held at the record
      date (per pre-distribution share when a share distribution shares the ex-date);
      `pay_date` required; `record_date` where available. If the issuer paid in another
      currency, `paid_currency` and the issuer's own conversion `issuer_fx_rate` are recorded
      as stated, never derived from our FX.
    - SYMBOL_CHANGE: an identifier-history record (old and new ticker), not a position event.
    - UNSUPPORTED: stored with its dates and label, changes nothing, is flagged.

    Under F8-A (the rule in force; PD-0030 §2 adopts F8-B for a later increment) this is
    only DETECTED and flagged: nothing here applies a split to a position."""

    listing_id: uuid.UUID
    action_type: CorporateActionType
    effective_date: datetime.date
    timing: SourceTiming
    lineage: Lineage
    split_ratio: Optional[SplitRatio] = None
    amount_per_unit: Optional[Money] = None
    pay_date: Optional[datetime.date] = None
    record_date: Optional[datetime.date] = None
    paid_currency: Optional[CurrencyCode] = None
    issuer_fx_rate: Optional[Decimal] = None
    old_ticker: Optional[str] = None
    new_ticker: Optional[str] = None
    unsupported_label: Optional[str] = None
    paid_amount: Optional[Decimal] = None  # `risk/1.8` Ruling 5.5 (1.8): what the issuer states it PAID per unit, in `paid_currency`, recorded as stated (never derived from our FX); optional, dividends only

    def __post_init__(self) -> None:
        require_type(self, "listing_id", self.listing_id, uuid.UUID)
        _require_date(self, "effective_date", self.effective_date)
        require_type(self, "timing", self.timing, SourceTiming)
        require_type(self, "lineage", self.lineage, Lineage)
        _check_action_shape(self)

    @property
    def ex_date(self) -> datetime.date:
        return self.effective_date


@dataclass(frozen=True)
class UnresolvedCorporateAction:
    """A corporate action as an adapter emits it (external identifiers, no listing)."""

    identifiers: ExternalIdentifiers
    action_type: CorporateActionType
    effective_date: datetime.date
    timing: SourceTiming
    lineage: Lineage
    split_ratio: Optional[SplitRatio] = None
    amount_per_unit: Optional[Money] = None
    pay_date: Optional[datetime.date] = None
    record_date: Optional[datetime.date] = None
    paid_currency: Optional[CurrencyCode] = None
    issuer_fx_rate: Optional[Decimal] = None
    old_ticker: Optional[str] = None
    new_ticker: Optional[str] = None
    unsupported_label: Optional[str] = None
    paid_amount: Optional[Decimal] = None

    def __post_init__(self) -> None:
        require_type(self, "identifiers", self.identifiers, ExternalIdentifiers)
        _require_date(self, "effective_date", self.effective_date)
        require_type(self, "timing", self.timing, SourceTiming)
        require_type(self, "lineage", self.lineage, Lineage)
        _check_action_shape(self)


@unique
class BenchmarkValueKind(Enum):
    LEVEL = "LEVEL"
    RETURN = "RETURN"


@unique
class LicenseStatus(Enum):
    INTERNAL_DEVELOPMENT_ONLY = "INTERNAL_DEVELOPMENT_ONLY"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    LICENSED = "LICENSED"


@dataclass(frozen=True)
class LicensingMetadata:
    """PRD §11.4: licensing is data on the contract. Display requires a LICENSED status."""

    license_status: LicenseStatus
    display_permitted: bool = False
    terms_ref: Optional[str] = None

    def __post_init__(self) -> None:
        require_type(self, "license_status", self.license_status, LicenseStatus)
        if not isinstance(self.display_permitted, bool):
            raise ObservationRuleError("display_permitted must be a bool")
        _require_optional_nonblank(self, "terms_ref", self.terms_ref)
        if self.display_permitted and self.license_status is not LicenseStatus.LICENSED:
            raise ObservationRuleError("display_permitted requires license_status LICENSED")


@dataclass(frozen=True)
class BenchmarkPoint:
    value_date: datetime.date
    value: Decimal

    def __post_init__(self) -> None:
        _require_date(self, "value_date", self.value_date)
        require_type(self, "value", self.value, Decimal)
        if not self.value.is_finite():
            raise ObservationRuleError("BenchmarkPoint.value must be finite")


@dataclass(frozen=True)
class BenchmarkSeries:
    """PRD §11.1: benchmark id, provider, values/returns, currency, source, licensing
    metadata. Points are strictly increasing by date."""

    benchmark_id: str
    provider: str
    points: Tuple[BenchmarkPoint, ...]
    value_kind: BenchmarkValueKind
    currency: CurrencyCode
    timing: SourceTiming
    lineage: Lineage
    licensing: LicensingMetadata

    def __post_init__(self) -> None:
        _require_nonblank(self, "benchmark_id", self.benchmark_id)
        _require_nonblank(self, "provider", self.provider)
        require_type(self, "points", self.points, tuple)
        for p in self.points:
            require_type(self, "points[]", p, BenchmarkPoint)
        dates = [p.value_date for p in self.points]
        if any(b <= a for a, b in zip(dates, dates[1:])):
            raise ObservationRuleError("BenchmarkSeries points must be strictly increasing by date")
        require_type(self, "value_kind", self.value_kind, BenchmarkValueKind)
        require_type(self, "currency", self.currency, CurrencyCode)
        require_type(self, "timing", self.timing, SourceTiming)
        require_type(self, "lineage", self.lineage, Lineage)
        require_type(self, "licensing", self.licensing, LicensingMetadata)


@unique
class RiskFreeQuoteType(Enum):
    """`risk/1.0` Ruling 4.3: how the quoted rate converts to a per-calendar-day simple rate. `SIMPLE_YIELD`: a money-market or investment (coupon-equivalent) yield, simple interest on an ACT/B basis.
    `BANK_DISCOUNT`: a discount rate on an ACT/360 basis for a bill of a stated term in days."""

    SIMPLE_YIELD = "SIMPLE_YIELD"
    BANK_DISCOUNT = "BANK_DISCOUNT"


@unique
class RateUnit(Enum):
    PERCENT = "PERCENT"  # the published number is a percentage per annum: 3.65 means 0.0365
    DECIMAL = "DECIMAL"  # the published number is a decimal fraction: 0.0365


@unique
class RevisionPolicy(Enum):
    """`risk/1.0` Ruling 4.6 item 7: whether the publisher revises published values. Each retrieval is a vintage (market-data Ruling 0.1: one vintage per series in M)."""

    NOT_REVISED = "NOT_REVISED"
    REVISED = "REVISED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RiskFreePoint:
    """One published quote: the date it is FOR (`value_date`, the source's own date label) and the rate as published (a `Decimal`; the unit is the series'). `term_days` is the term in days of the quoted bill,
    required for a `BANK_DISCOUNT` quote and forbidden for a `SIMPLE_YIELD` one (`risk/1.0` Ruling 4.6 item 2: per quote if it varies)."""

    value_date: datetime.date
    rate: Decimal
    term_days: Optional[int] = None

    def __post_init__(self) -> None:
        _require_date(self, "value_date", self.value_date)
        require_type(self, "rate", self.rate, Decimal)
        if not self.rate.is_finite():
            raise ObservationRuleError("RiskFreePoint.rate must be finite")
        if self.term_days is not None and (isinstance(self.term_days, bool) or not isinstance(self.term_days, int) or self.term_days <= 0):
            raise ObservationRuleError("RiskFreePoint.term_days must be a positive integer or None")


@dataclass(frozen=True)
class RiskFreeSeries:
    """A risk-free rate series in one currency (PD-0039 D2; `risk/1.0` Rulings 4.1 to 4.6). The analytics read nothing else, so the source can change without the method changing. The fields are the
    Ruling 4.6 checklist, item by item, and a series missing any of them is refused at construction (an adapter that cannot say them yields an issue, not a series):

    1. currency and instrument: `currency`, `series_id`, `instrument` (named exactly), `tenor_weeks` (the contract CARRIES the tenor; whether it is acceptable is the method's, and is stated on every result);
    2. quote convention: `quote_type`, `day_count_basis` (360 or 365 for a SIMPLE_YIELD; 360 for a BANK_DISCOUNT) and `term_days` on each BANK_DISCOUNT point;
    3. unit and precision: `unit` and `decimals_published` (a point with more decimals than declared contradicts the profile and is refused);
    4. date semantics: `date_semantics` (which date a value is for, the time of day it represents, its time zone: free text kept as evidence);
    5. publication schedule: `calendar_id`, the `RATE_PUBLICATIONS` calendar that counts publications (hand-made, never derived from this series);
    6. history: the `points`, machine-readable;
    7. revision policy: `revision_policy`;
    8. terms: the source registry's terms check, enforced by the loader (a gate by source, not by kind).

    Points are strictly increasing by date. No rate is plausible-checked here (a rate may be negative); a discount rate must satisfy `y * t < 360` or its conversion has no meaning."""

    series_id: str
    name: str
    provider: str
    currency: CurrencyCode
    instrument: str
    tenor_weeks: int
    quote_type: RiskFreeQuoteType
    day_count_basis: int
    unit: RateUnit
    decimals_published: int
    date_semantics: str
    calendar_id: str
    revision_policy: RevisionPolicy
    points: Tuple[RiskFreePoint, ...]
    timing: SourceTiming
    lineage: Lineage
    licensing: LicensingMetadata

    def __post_init__(self) -> None:
        for name in ("series_id", "name", "provider", "instrument", "date_semantics", "calendar_id"):
            _require_nonblank(self, name, getattr(self, name))
        require_type(self, "currency", self.currency, CurrencyCode)
        for name in ("tenor_weeks", "decimals_published", "day_count_basis"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ObservationRuleError(f"RiskFreeSeries.{name} must be an integer")
        if self.tenor_weeks <= 0:
            raise ObservationRuleError("RiskFreeSeries.tenor_weeks must be positive")
        if not 0 <= self.decimals_published <= 12:
            raise ObservationRuleError("RiskFreeSeries.decimals_published must be between 0 and 12")
        require_type(self, "quote_type", self.quote_type, RiskFreeQuoteType)
        require_type(self, "unit", self.unit, RateUnit)
        require_type(self, "revision_policy", self.revision_policy, RevisionPolicy)
        if self.quote_type is RiskFreeQuoteType.SIMPLE_YIELD and self.day_count_basis not in (360, 365):
            raise ObservationRuleError("a SIMPLE_YIELD series needs day_count_basis 360 or 365")
        if self.quote_type is RiskFreeQuoteType.BANK_DISCOUNT and self.day_count_basis != 360:
            raise ObservationRuleError("a BANK_DISCOUNT series is quoted ACT/360: day_count_basis must be 360")
        require_type(self, "points", self.points, tuple)
        if not self.points:
            raise ObservationRuleError("a risk-free series has at least one point")
        for p in self.points:
            require_type(self, "points[]", p, RiskFreePoint)
        dates = [p.value_date for p in self.points]
        if any(b <= a for a, b in zip(dates, dates[1:])):
            raise ObservationRuleError("RiskFreeSeries points must be strictly increasing by date")
        denominator = 100 if self.unit is RateUnit.PERCENT else 1
        for p in self.points:
            if -p.rate.as_tuple().exponent > self.decimals_published and p.rate != p.rate.quantize(Decimal(1).scaleb(-self.decimals_published)):
                raise ObservationRuleError(f"{p.value_date}: the rate {p.rate} has more decimals than the declared {self.decimals_published}")
            if self.quote_type is RiskFreeQuoteType.BANK_DISCOUNT:
                if p.term_days is None:
                    raise ObservationRuleError(f"{p.value_date}: a BANK_DISCOUNT quote needs its term in days")
                if (p.rate / denominator) * p.term_days >= 360:
                    raise ObservationRuleError(f"{p.value_date}: a discount rate with y * t >= 360 is not a bill price")
            elif p.term_days is not None:
                raise ObservationRuleError(f"{p.value_date}: a SIMPLE_YIELD quote has no term")
        require_type(self, "timing", self.timing, SourceTiming)
        require_type(self, "lineage", self.lineage, Lineage)
        require_type(self, "licensing", self.licensing, LicensingMetadata)


@dataclass(frozen=True)
class IdentityAssertion:
    """What an identifier source says about one listing: its FIGI, composite and
    share-class FIGIs, the source's exchange code and ticker. EVIDENCE, not identity: it never
    creates an Issuer, Instrument or Listing. It can only be matched against existing identity
    (and add identifier rows to a resolved listing); anything unmatched is reported. `exch_code`
    is the source's own code (e.g. "US" for the US composite, "HK"), NOT a MIC: no MIC is
    inferred from it, and `ticker` is kept exactly as published (no zero padding)."""

    figi: str
    ticker: str
    exch_code: str
    timing: SourceTiming
    lineage: Lineage
    composite_figi: Optional[str] = None
    share_class_figi: Optional[str] = None
    name: Optional[str] = None
    security_type: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("figi", "ticker", "exch_code"):
            _require_nonblank(self, name, getattr(self, name))
        for name in ("composite_figi", "share_class_figi", "name", "security_type"):
            _require_optional_nonblank(self, name, getattr(self, name))
        require_type(self, "timing", self.timing, SourceTiming)
        require_type(self, "lineage", self.lineage, Lineage)


@unique
class ResolutionStatus(Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class InstrumentResolution:
    """The outcome of mapping external identifiers to an internal `listing_id`.
    `listing_id` is set if and only if `status` is RESOLVED; any other status means the
    caller must not guess (PD-0021, Tech Plan §15.6)."""

    identifiers: ExternalIdentifiers
    listing_id: Optional[uuid.UUID]
    status: ResolutionStatus
    candidates: Tuple[uuid.UUID, ...] = ()
    matched_on: Tuple[str, ...] = ()
    evidence_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_type(self, "identifiers", self.identifiers, ExternalIdentifiers)
        require_optional_type(self, "listing_id", self.listing_id, uuid.UUID)
        require_type(self, "status", self.status, ResolutionStatus)
        for name in ("candidates", "matched_on", "evidence_refs"):
            require_type(self, name, getattr(self, name), tuple)
        for c in self.candidates:
            require_type(self, "candidates[]", c, uuid.UUID)
        if (self.status is ResolutionStatus.RESOLVED) != (self.listing_id is not None):
            raise ObservationRuleError("listing_id is set if and only if status is RESOLVED")
        if self.status is ResolutionStatus.UNRESOLVED and self.candidates:
            raise ObservationRuleError("UNRESOLVED carries no candidates")
        if self.status is ResolutionStatus.AMBIGUOUS and len(set(self.candidates)) < 2:
            raise ObservationRuleError("AMBIGUOUS needs at least two candidates")
        if self.status is ResolutionStatus.CONFLICT and not self.candidates:
            raise ObservationRuleError("CONFLICT names the listing(s) in conflict")

    @property
    def is_resolved(self) -> bool:
        return self.status is ResolutionStatus.RESOLVED


@unique
class ReconciliationStatus(Enum):
    """market-data/1.0 Ruling 4.3: exactly one per resolved datum. Whether a datum is
    CORROBORATED or in DISAGREEMENT is decided by the Ruling 4.2 precision bound (declared
    per-source precision profiles); IMPLAUSIBLE by the Ruling 1.5 bands; RESOLVED_BY_EVIDENCE
    only by a human-authored resolution record in the market-data version. No source wins a
    disagreement by order, recency, majority or average."""

    CORROBORATED = "CORROBORATED"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    DISAGREEMENT = "DISAGREEMENT"
    IMPLAUSIBLE = "IMPLAUSIBLE"
    RESOLVED_BY_EVIDENCE = "RESOLVED_BY_EVIDENCE"


@dataclass(frozen=True)
class SourceReading:
    """One source's observation, with the identifiers of its provenance. Readings are
    carried, never collapsed, so two sources can be compared (PD-0027 condition 4)."""

    source_id: str
    independence_group: str
    file_sha256: str
    observation: object

    def __post_init__(self) -> None:
        _require_nonblank(self, "source_id", self.source_id)
        _require_nonblank(self, "independence_group", self.independence_group)
        _require_sha256(self, "file_sha256", self.file_sha256)
        if not isinstance(
            self.observation, (QuoteObservation, FXObservation, CorporateActionObservation)
        ):
            raise ObservationRuleError("SourceReading.observation must be a normalized observation")


@dataclass(frozen=True)
class FieldDifference:
    """A value compared across sources, exact. `absolute` is max - min (None if it cannot
    be computed exactly). No tolerance is applied here."""

    field: str
    by_source: Tuple[Tuple[str, Decimal], ...]
    absolute: Optional[Decimal]

    def __post_init__(self) -> None:
        _require_nonblank(self, "field", self.field)
        require_type(self, "by_source", self.by_source, tuple)
        require_optional_type(self, "absolute", self.absolute, Decimal)


@dataclass(frozen=True)
class Reconciliation:
    """Two-source data shape (Tech Plan §15.8; market-data/1.0 §4). Data only. `status` is
    None when the injected rule did not assess the readings (the CP2a placeholder rule does
    this whenever several independent sources report, because assessing needs the declared
    precision profiles); it is never defaulted to an agreement. All readings stay attached,
    so both values stay in lineage. `selected_source` is set only when the injected rule
    chose one, with its basis."""

    status: Optional[ReconciliationStatus]
    readings: Tuple[SourceReading, ...]
    differences: Tuple[FieldDifference, ...]
    rule_id: str
    tolerance_ref: Optional[str] = None
    selected_source: Optional[str] = None
    selection_basis: str = ""
    flags: Tuple[str, ...] = ()  # failed safeguards and notes (Ruling 4.6), never silent
    used: Optional[SourceReading] = None  # the reading whose value is used (Ruling 4.3)

    def __post_init__(self) -> None:
        require_optional_type(self, "status", self.status, ReconciliationStatus)
        require_type(self, "flags", self.flags, tuple)
        require_optional_type(self, "used", self.used, SourceReading)
        if self.used is not None and self.used not in self.readings:
            raise ObservationRuleError("the reading used must be one of the readings")
        require_type(self, "readings", self.readings, tuple)
        if not self.readings:
            raise ObservationRuleError("Reconciliation needs at least one reading")
        for r in self.readings:
            require_type(self, "readings[]", r, SourceReading)
        require_type(self, "differences", self.differences, tuple)
        _require_nonblank(self, "rule_id", self.rule_id)
        _require_optional_nonblank(self, "tolerance_ref", self.tolerance_ref)
        require_optional_type(self, "selected_source", self.selected_source, str)
        require_type(self, "selection_basis", self.selection_basis, str)
        if self.selected_source is not None:
            if self.selected_source not in {r.source_id for r in self.readings}:
                raise ObservationRuleError("selected_source must be one of the readings' sources")
            if not self.selection_basis.strip():
                raise ObservationRuleError("a selected source needs a stated selection_basis")
        if (
            self.status in (ReconciliationStatus.DISAGREEMENT, ReconciliationStatus.IMPLAUSIBLE)
            and (self.selected_source is not None or self.used is not None)
        ):
            raise ObservationRuleError(
                "a DISAGREEMENT or IMPLAUSIBLE datum has no value used (Ruling 4.3)"
            )
