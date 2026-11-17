"""File lineage manifest, source registry, market-data release and data-set reference
(Tech Plan §15.3).

Files are the evidence of record. Each payload file has a sibling manifest recording
where it came from; the SHA-256 of the exact payload bytes is the file's identity. A
`MarketDataRelease` is the market-data pin (an immutable, hashed list of file hashes plus
source precedence and convention-set ids). A `DataSetRef` is what a Computation Manifest
cites: the release and the files actually consumed. Nothing here reads a clock or the
network; `retrieval_time` is data written by the human-run tool.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from enum import Enum, unique
from typing import Dict, Iterable, Mapping, Optional, Tuple

from domain.currency import CurrencyCode
from domain.field_validation import require_optional_type, require_type
from marketdata.canonical import canonical_json, sha256_hex
from marketdata.contracts import AdjustmentStatus, DataDelayStatus, UsageScope

CONVENTION_SET_ID = "market-data/1.16" # methodology/CP2_MARKET_DATA_CONVENTIONS.md (section 11 item 13; 1.14 defines `paid_amount` and its comparison, Rulings 7.1 and 4.5; 1.15 label: PD-0067 decision 6, a label only; 1.16 label: the F1 R4a label increment, section 11 items 23 to 28 and 32 to 35 built. The engine behaviours of section 11 items 17 to 20, 29 and 30 NOT built are listed in every manifest as open items, `market11.UNBUILT_1_16`: Ruling 3.2 item 4 with Test V1, Ruling 3.2 item 5, Test V4 (Ruling 3.3), Ruling 4.5 (1.15), Rulings 7.4 and 7.5, and the `securityType` / `securityType2` reading of Ruling 7.3 item 3)
#: the statuses of a series a vendor re-bases at each retrieval (Ruling 2.3); the only ones whose key carries the anchor and that Ruling 0.1 (1.12) never segments
VENDOR_ADJUSTED = (AdjustmentStatus.SPLIT_ADJUSTED, AdjustmentStatus.DIVIDEND_ADJUSTED, AdjustmentStatus.TOTAL_RETURN_ADJUSTED)
MANIFEST_SCHEMA = "finweb.marketdata.file_manifest/1"
RELEASE_SCHEMA = "finweb.marketdata.release/1"
_HEX = set("0123456789abcdef")


class ManifestError(ValueError):
    """A manifest, registry or release that is malformed or inconsistent."""


class UnknownSourceError(LookupError):
    pass


class SourceRegistryNotPinnedError(ValueError):
    """A computation cannot pin the source registry (performance/1.12 Ruling 1.7 item 4): a source with a file in the market-data version has no registry record, or the port cannot report its
    records. It fails closed: no manifest and no value, never a manifest with `source_registry_digest` ""."""


class SourceTermsNotAttestedError(PermissionError):
    """SOURCE_TERMS_NOT_ATTESTED: no human terms-of-use check is recorded for the source."""


class TwoVintagesError(ManifestError):
    """Ruling 0.1: a market-data version holds at most one vintage per series; building one
    with two fails closed (it never takes "the latest")."""


@unique
class DataKind(Enum):
    QUOTE = "QUOTE"
    FX = "FX"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    BENCHMARK = "BENCHMARK"
    RISK_FREE = "RISK_FREE"  # CP4 (risk/1.0 section 4, migration 0016): a risk-free rate series in one currency
    IDENTITY = "IDENTITY"
    # Reference files that are part of the market-data version M (market-data/1.0 §0):
    CALENDAR = "CALENDAR"                    # exchange session calendars, the ECB fixing calendar
    RESOLUTION_RECORD = "RESOLUTION_RECORD"  # human-authored disagreement resolutions (§4.3)


def _is_sha256(text: object) -> bool:
    return isinstance(text, str) and len(text) == 64 and set(text) <= _HEX


def _pairs(name: str, value: object) -> Tuple[Tuple[str, str], ...]:
    if not isinstance(value, tuple):
        raise ManifestError(f"{name} must be a tuple of (str, str) pairs")
    for item in value:
        if not (isinstance(item, tuple) and len(item) == 2 and all(isinstance(x, str) for x in item)):
            raise ManifestError(f"{name} must contain only (str, str) pairs")
    return value


@dataclass(frozen=True)
class FileManifest:
    """Lineage of one payload file (PD-0027 condition 3, STATUS 16b).

    `request` is a WHITELIST of the call parameters (never a key, header or URL carrying a
    token). `declared_adjustment` is what the call implies; nothing trusts it, and a
    separate verification record (Quant rule, later) judges it."""

    file_sha256: str
    size_bytes: int
    payload_filename: str
    payload_format: str
    source_id: str
    data_kind: DataKind
    retrieval_time: datetime.datetime
    retrieved_by: str
    declared_adjustment: AdjustmentStatus
    usage_scope: UsageScope
    market: Optional[str] = None
    request: Tuple[Tuple[str, str], ...] = ()
    adjustment_anchor: Optional[str] = None
    declared_currency: Optional[CurrencyCode] = None
    declared_delay: DataDelayStatus = DataDelayStatus.UNKNOWN
    source_identifiers: Tuple[str, ...] = ()
    script_name: Optional[str] = None
    script_version: Optional[str] = None
    script_sha256: Optional[str] = None
    libraries: Tuple[Tuple[str, str], ...] = ()
    coverage: Tuple[Tuple[str, str], ...] = ()
    schema: str = MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != MANIFEST_SCHEMA:
            raise ManifestError(f"unsupported manifest schema {self.schema!r}")
        if not _is_sha256(self.file_sha256):
            raise ManifestError("file_sha256 must be 64 lowercase hex characters")
        if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool) or self.size_bytes < 0:
            raise ManifestError("size_bytes must be a non-negative int")
        for name in ("payload_filename", "payload_format", "source_id", "retrieved_by"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ManifestError(f"{name} must be a non-blank string")
        if self.retrieved_by not in ("human", "synthetic"):
            raise ManifestError("retrieved_by must be 'human' or 'synthetic'")
        require_type(self, "data_kind", self.data_kind, DataKind)
        if (
            not isinstance(self.retrieval_time, datetime.datetime)
            or self.retrieval_time.utcoffset() is None
        ):
            raise ManifestError("retrieval_time must be a timezone-aware datetime")
        require_type(self, "declared_adjustment", self.declared_adjustment, AdjustmentStatus)
        require_type(self, "usage_scope", self.usage_scope, UsageScope)
        require_type(self, "declared_delay", self.declared_delay, DataDelayStatus)
        require_optional_type(self, "declared_currency", self.declared_currency, CurrencyCode)
        for name in ("market", "adjustment_anchor", "script_name", "script_version"):
            require_optional_type(self, name, getattr(self, name), str)
        if self.script_sha256 is not None and not _is_sha256(self.script_sha256):
            raise ManifestError("script_sha256 must be 64 lowercase hex characters")
        _pairs("request", self.request)
        _pairs("libraries", self.libraries)
        _pairs("coverage", self.coverage)
        if not isinstance(self.source_identifiers, tuple) or not all(
            isinstance(s, str) for s in self.source_identifiers
        ):
            raise ManifestError("source_identifiers must be a tuple of str")

    def series_keys(self) -> Tuple[Tuple[str, str, str, str, str], ...]:
        """The series this file contributes to (Ruling 0.1): (source, kind, subject,
        adjustment status, anchor), one per symbol the file covers. A file that lists no
        symbols covers the whole combination ('*'), so a second such file is a second
        vintage. (1.12) The anchor is part of the key ONLY for a vendor-adjusted series (Ruling 2.3: it
        is null for a raw series). A declared anchor on any other series is a difference of IDENTITY the
        build refuses, never a way to make a second file a different series: no vintage label may sit in a
        key field."""
        subjects = sorted(set(self.source_identifiers)) or ["*"]
        anchor = (self.adjustment_anchor or "") if self.declared_adjustment in VENDOR_ADJUSTED else ""
        return tuple(
            (self.source_id, self.data_kind.value, s, self.declared_adjustment.value, anchor)
            for s in subjects
        )

    def to_obj(self) -> Dict[str, object]:
        return {
            "schema": self.schema,
            "file_sha256": self.file_sha256,
            "size_bytes": self.size_bytes,
            "payload_filename": self.payload_filename,
            "payload_format": self.payload_format,
            "source_id": self.source_id,
            "data_kind": self.data_kind.value,
            "market": self.market,
            "retrieval_time": self.retrieval_time.astimezone(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "retrieved_by": self.retrieved_by,
            "request": [list(p) for p in self.request],
            "declared_adjustment": self.declared_adjustment.value,
            "adjustment_anchor": self.adjustment_anchor,
            "declared_currency": None if self.declared_currency is None else self.declared_currency.code,
            "declared_delay": self.declared_delay.value,
            "source_identifiers": list(self.source_identifiers),
            "script": {"name": self.script_name, "version": self.script_version,
                       "script_sha256": self.script_sha256},
            "libraries": [list(p) for p in self.libraries],
            "usage_scope": self.usage_scope.value,
            "coverage": [list(p) for p in self.coverage],
        }

    def to_json(self) -> str:
        """Human-readable, deterministic (sorted keys, 2-space indent, trailing newline)."""
        return json.dumps(self.to_obj(), sort_keys=True, indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "FileManifest":
        try:
            obj = json.loads(text)
            script = obj.get("script") or {}
            time = datetime.datetime.strptime(obj["retrieval_time"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=datetime.timezone.utc
            )
            ccy = obj.get("declared_currency")
            return cls(
                schema=obj["schema"],
                file_sha256=obj["file_sha256"],
                size_bytes=obj["size_bytes"],
                payload_filename=obj["payload_filename"],
                payload_format=obj["payload_format"],
                source_id=obj["source_id"],
                data_kind=DataKind(obj["data_kind"]),
                market=obj.get("market"),
                retrieval_time=time,
                retrieved_by=obj["retrieved_by"],
                request=tuple((a, b) for a, b in obj.get("request", [])),
                declared_adjustment=AdjustmentStatus(obj["declared_adjustment"]),
                adjustment_anchor=obj.get("adjustment_anchor"),
                declared_currency=None if ccy is None else CurrencyCode(ccy),
                declared_delay=DataDelayStatus(obj.get("declared_delay", "UNKNOWN")),
                source_identifiers=tuple(obj.get("source_identifiers", [])),
                script_name=script.get("name"),
                script_version=script.get("version"),
                script_sha256=script.get("script_sha256"),
                libraries=tuple((a, b) for a, b in obj.get("libraries", [])),
                usage_scope=UsageScope(obj["usage_scope"]),
                coverage=tuple((a, b) for a, b in obj.get("coverage", [])),
            )
        except ManifestError:
            raise
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ManifestError(f"malformed manifest: {exc}") from exc


@dataclass(frozen=True)
class TermsCheck:
    """A HUMAN's terms-of-use check for internal development use (STATUS 16e). Agents
    have no network and cannot make this attestation."""

    checked_by: str
    checked_on: datetime.date
    permits_internal_development_use: bool
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.checked_by, str) or not self.checked_by.strip():
            raise ManifestError("terms_check.checked_by must be non-blank")
        if isinstance(self.checked_on, datetime.datetime) or not isinstance(
            self.checked_on, datetime.date
        ):
            raise ManifestError("terms_check.checked_on must be a date")
        if not isinstance(self.permits_internal_development_use, bool):
            raise ManifestError("permits_internal_development_use must be a bool")


@dataclass(frozen=True)
class SourceRecord:
    """One entry of `SOURCES.json`. `independence_group` names the true upstream, so two
    libraries wrapping the same website count as one source for reconciliation."""

    source_id: str
    name: str
    upstream_provider: str
    independence_group: str
    terms_url: Optional[str] = None
    terms_check: Optional[TermsCheck] = None
    synthetic: bool = False
    #: `risk/1.4` Ruling 5.7 (1.2) (OI-R10): which of several sources serving ONE benchmark id is carried when they agree; a positive integer, 1 = primary, unique among the sources of a benchmark. None: the
    #: source has no priority, which is allowed only while no benchmark it serves has another source (the engine refuses a multi-source benchmark with a missing or repeated priority).
    source_priority: Optional[int] = None

    def __post_init__(self) -> None:
        for name in ("source_id", "name", "upstream_provider", "independence_group"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ManifestError(f"SourceRecord.{name} must be non-blank")
        if self.source_priority is not None and (isinstance(self.source_priority, bool) or not isinstance(self.source_priority, int) or self.source_priority < 1):
            raise ManifestError("SourceRecord.source_priority must be a positive integer (1 = primary) or None")
        if not isinstance(self.synthetic, bool):
            raise ManifestError("SourceRecord.synthetic must be a bool")
        require_optional_type(self, "terms_check", self.terms_check, TermsCheck)

    @property
    def terms_attested(self) -> bool:
        return self.synthetic or (
            self.terms_check is not None and self.terms_check.permits_internal_development_use
        )

    def to_obj(self) -> Dict[str, object]:
        """EVERY field (performance/1.12 Ruling 1.7 item 4: `terms_check` included), for the registry digest."""
        tc = self.terms_check
        out: Dict[str, object] = {
            "source_id": self.source_id, "name": self.name, "upstream_provider": self.upstream_provider,
            "independence_group": self.independence_group, "terms_url": self.terms_url, "synthetic": self.synthetic,
            "terms_check": None if tc is None else {
                "checked_by": tc.checked_by, "checked_on": tc.checked_on.isoformat(),
                "permits_internal_development_use": tc.permits_internal_development_use, "notes": tc.notes},
        }
        if self.source_priority is not None:  # present only when set, so every registry digest recorded before the field existed is unchanged
            out["source_priority"] = self.source_priority
        return out


def source_registry_digest(records: Iterable[SourceRecord]) -> str:
    """The SHA-256 of the canonical JSON of the full source records, sorted by `source_id` (performance/1.12 Ruling 1.7 item 4). The caller passes the records of the sources that have at least
    one file in the `M` it read (`M_t` in Current mode). A pure function of the records."""
    ordered = sorted(records, key=lambda r: r.source_id)
    return sha256_hex(canonical_json([r.to_obj() for r in ordered]).encode("utf-8"))


class SourceRegistry:
    """The registry of sources (`SOURCES.json`)."""

    def __init__(self, records: Iterable[SourceRecord]):
        self._records: Dict[str, SourceRecord] = {}
        for r in records:
            if r.source_id in self._records:
                raise ManifestError(f"duplicate source_id {r.source_id!r}")
            self._records[r.source_id] = r

    def get(self, source_id: str) -> SourceRecord:
        try:
            return self._records[source_id]
        except KeyError:
            raise UnknownSourceError(f"source {source_id!r} is not in the registry") from None

    def require_attested(self, source_id: str) -> SourceRecord:
        record = self.get(source_id)
        if not record.terms_attested:
            raise SourceTermsNotAttestedError(
                f"SOURCE_TERMS_NOT_ATTESTED: no human terms-of-use check permitting internal "
                f"development use is recorded for source {source_id!r}"
            )
        return record

    @classmethod
    def from_json(cls, text: str) -> "SourceRegistry":
        try:
            obj = json.loads(text)
            records = []
            for item in obj["sources"]:
                tc = item.get("terms_check")
                records.append(
                    SourceRecord(
                        source_id=item["source_id"],
                        name=item["name"],
                        upstream_provider=item["upstream_provider"],
                        independence_group=item["independence_group"],
                        terms_url=item.get("terms_url"),
                        terms_check=None if tc is None else TermsCheck(
                            checked_by=tc["checked_by"],
                            checked_on=datetime.date.fromisoformat(tc["checked_on"]),
                            permits_internal_development_use=tc["permits_internal_development_use"],
                            notes=tc.get("notes", ""),
                        ),
                        synthetic=item.get("synthetic", False),
                        source_priority=item.get("source_priority"),
                    )
                )
            return cls(records)
        except ManifestError:
            raise
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ManifestError(f"malformed source registry: {exc}") from exc


@dataclass(frozen=True, order=True)
class FileRef:
    """A file as cited by a computation: its hash and the adapter version that read it."""

    file_sha256: str
    adapter_id: str
    adapter_version: str

    def __post_init__(self) -> None:
        if not _is_sha256(self.file_sha256):
            raise ManifestError("FileRef.file_sha256 must be 64 lowercase hex characters")


@dataclass(frozen=True)
class MarketDataRelease:
    """The market-data pin (Tech Plan §15.3): which files count, in which source
    precedence, under which convention-set ids. Immutable; `release_id` is the SHA-256 of
    the canonical content. Precedence is a data choice; whether it decides a value when
    sources differ is the reconciliation rule's business, not the release's."""

    name: str
    files: Tuple[str, ...]
    source_precedence: Tuple[str, ...]
    conventions: Tuple[Tuple[str, str], ...] = ()
    created_for: str = ""
    convention_set_id: str = CONVENTION_SET_ID
    schema: str = RELEASE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != RELEASE_SCHEMA:
            raise ManifestError(f"unsupported release schema {self.schema!r}")
        if not isinstance(self.convention_set_id, str) or not self.convention_set_id.strip():
            raise ManifestError("convention_set_id must be non-blank")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ManifestError("release name must be non-blank")
        if not isinstance(self.files, tuple) or not all(_is_sha256(f) for f in self.files):
            raise ManifestError("release files must be a tuple of sha256 hex strings")
        if list(self.files) != sorted(set(self.files)):
            raise ManifestError("release files must be sorted and unique")
        if not isinstance(self.source_precedence, tuple) or not all(
            isinstance(s, str) and s.strip() for s in self.source_precedence
        ):
            raise ManifestError("source_precedence must be a tuple of non-blank source ids")
        if len(set(self.source_precedence)) != len(self.source_precedence):
            raise ManifestError("source_precedence must not repeat a source")
        _pairs("conventions", self.conventions)
        if list(self.conventions) != sorted(self.conventions):
            raise ManifestError("conventions must be sorted")
        if not isinstance(self.created_for, str):
            raise ManifestError("created_for must be a string")

    @classmethod
    def from_manifests(
        cls,
        name: str,
        manifests: Iterable[FileManifest],
        source_precedence: Iterable[str],
        conventions: Optional[Mapping[str, str]] = None,
        created_for: str = "",
    ) -> "MarketDataRelease":
        """The supported way to cut a release. FAILS CLOSED (`TwoVintagesError`) if two different files
        contribute to one series (Ruling 0.1) UNLESS they are segments (Ruling 0.1 (1.12)): the series is of a
        segmentable kind and every file declares its request `start` and `end`, the declared intervals disjoint
        (`marketdata.segments.manifest_level_check`). It never takes the latest. The manifests alone cannot see
        rows or calendars, so the exact check (coverage from the rows and calendars, identity, vintage-stability)
        is repeated on the loaded data by `build_in_memory_market_data`, for every release however cut."""
        from marketdata.segments import manifest_level_check  # noqa: PLC0415

        manifests = tuple(manifests)
        groups: Dict[Tuple[str, str, str, str, str], Dict[str, FileManifest]] = {}
        for manifest in manifests:
            for key in manifest.series_keys():
                groups.setdefault(key, {})[manifest.file_sha256] = manifest
        for key, members in sorted(groups.items()):
            manifest_level_check(key, tuple(members.values()))
        return cls(
            name=name,
            files=tuple(sorted({m.file_sha256 for m in manifests})),
            source_precedence=tuple(source_precedence),
            conventions=tuple(sorted((conventions or {}).items())),
            created_for=created_for,
        )

    def content_obj(self) -> Dict[str, object]:
        return {
            "schema": self.schema,
            "name": self.name,
            "files": list(self.files),
            "source_precedence": list(self.source_precedence),
            "conventions": [list(p) for p in self.conventions],
            "created_for": self.created_for,
            "convention_set_id": self.convention_set_id,
        }

    @property
    def release_id(self) -> str:
        return sha256_hex(canonical_json(self.content_obj()).encode("utf-8"))

    def to_json(self) -> str:
        obj = self.content_obj()
        obj["release_id"] = self.release_id
        return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "MarketDataRelease":
        try:
            obj = json.loads(text)
            release = cls(
                schema=obj["schema"],
                name=obj["name"],
                files=tuple(obj["files"]),
                source_precedence=tuple(obj["source_precedence"]),
                conventions=tuple((a, b) for a, b in obj["conventions"]),
                created_for=obj.get("created_for", ""),
                convention_set_id=obj["convention_set_id"],
            )
        except ManifestError:
            raise
        except (KeyError, ValueError, TypeError) as exc:
            raise ManifestError(f"malformed release: {exc}") from exc
        if obj.get("release_id") != release.release_id:
            raise ManifestError("release_id does not match the release content")
        return release


@dataclass(frozen=True)
class DataSetRef:
    """What a Computation Manifest cites for one kind of market data (Tech Plan §6.2,
    §15.3): the release, the files actually consumed (sorted, unique) with the adapter
    versions that read them, the convention ids, and the requested date range."""

    kind: DataKind
    release_id: str
    consumed: Tuple[FileRef, ...]
    convention_ids: Tuple[Tuple[str, str], ...] = ()
    range_start: Optional[datetime.date] = None
    range_end: Optional[datetime.date] = None
    convention_set_id: str = CONVENTION_SET_ID

    def __post_init__(self) -> None:
        require_type(self, "kind", self.kind, DataKind)
        if not isinstance(self.convention_set_id, str) or not self.convention_set_id.strip():
            raise ManifestError("convention_set_id must be non-blank")
        if not _is_sha256(self.release_id):
            raise ManifestError("release_id must be 64 lowercase hex characters")
        if list(self.consumed) != sorted(set(self.consumed)):
            raise ManifestError("consumed files must be sorted and unique")
        _pairs("convention_ids", self.convention_ids)

    @classmethod
    def build(
        cls,
        kind: DataKind,
        release_id: str,
        consumed: Iterable[FileRef],
        convention_ids: Optional[Mapping[str, str]] = None,
        range_start: Optional[datetime.date] = None,
        range_end: Optional[datetime.date] = None,
        convention_set_id: str = CONVENTION_SET_ID,
    ) -> "DataSetRef":
        return cls(
            kind=kind,
            release_id=release_id,
            consumed=tuple(sorted(set(consumed))),
            convention_ids=tuple(sorted((convention_ids or {}).items())),
            range_start=range_start,
            range_end=range_end,
            convention_set_id=convention_set_id,
        )

    def to_obj(self) -> Dict[str, object]:
        return {
            "kind": self.kind.value,
            "release_id": self.release_id,
            "consumed": [[f.file_sha256, f.adapter_id, f.adapter_version] for f in self.consumed],
            "convention_ids": [list(p) for p in self.convention_ids],
            "range_start": self.range_start,
            "range_end": self.range_end,
            "convention_set_id": self.convention_set_id,
        }

    @property
    def ref_id(self) -> str:
        return sha256_hex(canonical_json(self.to_obj()).encode("utf-8"))
