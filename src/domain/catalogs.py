"""The reference catalogs of the risk engine: benchmarks and risk-free series (`risk/1.1` Rulings 4.6, 5.1, 5.4; PD-0039 D1, D2, D5; PD-0040; tech plan 17.4, 17.16).

Two committed data files, owned by the main session, say WHICH reference series the product may use and what each one is:
- the committed `BENCHMARKS.json` (under `data/`; `catalog_id` `benchmarks:1`): the benchmarks a user may select (migration 0015). An entry carries what a series cannot say about itself: the return basis (`TOTAL_RETURN_NET`,
  `TOTAL_RETURN_GROSS`, `PRICE_RETURN`), the calendar of the index, the currency of the levels, the form of the series (levels or returns), the licence and the source.
- the committed `RISK_FREE.json` (under `data/`; `catalog_id` `risk_free:1`): at most ONE admitted series per currency (Ruling 4.1).

THE RULES, enforced here and nowhere else:
- Only `entries` are read. `candidates` are never parsed into anything (a test puts a poisoned candidate in a file and shows nothing changes), so a candidate cannot become selectable by being listed.
- An id that is not an entry is refused (`BenchmarkNotInCatalogError`). A synthetic series is NEVER catalogued (market-data Ruling 4.8: synthetic data stays in fixtures and tests): an entry with `synthetic` other than
  false is refused when the file is read. Tests and fixtures build their own catalog object from the same classes, with their own `catalog_id`.
- A change to any field of an entry is a NEW `catalog_id`, so a manifest (and a selection, as `catalog_version`) that cites the id cites the content. `digest` is the SHA-256 of the canonical JSON of the id and the
  entries only: an edit to a candidate, a rule or a date does not change a result, an edit to an entry does.
- Fail closed: a missing field, an unknown enumeration value, a duplicate id, two risk-free entries for one currency, or a malformed file is `CatalogError`; nothing is defaulted.

Pure: parses bytes. Reading the files is the edge's job (`risk_service.catalogs`).
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, replace
from enum import Enum, unique
from typing import Any, Dict, Mapping, Optional, Tuple

from domain.benchmark_selection import (
    BenchmarkSelection,
    BenchmarkSelectionError,
    CATALOG_VERSION_PATTERN,
    RecordType,
    is_benchmark_id,
)

_CURRENCY = re.compile(r"[A-Z]{3}")


class CatalogError(ValueError):
    """The catalog file is malformed or breaks a rule of the catalog."""


class BenchmarkNotInCatalogError(BenchmarkSelectionError):
    """A SELECT names a benchmark id that is not an entry of the catalog."""

    def __init__(self, benchmark_id: str, catalog_id: str) -> None:
        super().__init__(f"benchmark {benchmark_id!r} is not an entry of catalog {catalog_id!r}: a selection must name an admitted benchmark")
        self.benchmark_id = benchmark_id
        self.catalog_id = catalog_id


class CatalogVersionMismatchError(BenchmarkSelectionError):
    """A selection that already names a catalog version is checked against another catalog."""


@unique
class ReturnBasis(Enum):
    TOTAL_RETURN_NET = "TOTAL_RETURN_NET"
    TOTAL_RETURN_GROSS = "TOTAL_RETURN_GROSS"
    PRICE_RETURN = "PRICE_RETURN"

    @property
    def is_total_return(self) -> bool:
        return self is not ReturnBasis.PRICE_RETURN


@unique
class SeriesForm(Enum):
    LEVELS = "LEVELS"
    RETURNS = "RETURNS"


def catalog_version_of(catalog_id: str) -> str:
    """The `catalog_version` a selection row stores for a catalog (`benchmark_selection.catalog_version`, migration 0015): the catalog id ITSELF. The committed ids are `benchmarks:1` and `risk_free:1` (the
    stored pattern `[A-Za-z0-9][A-Za-z0-9._:+-]{0,63}` does not allow a `/`). An id that does not fit the pattern, a `/` included, is REFUSED (`CatalogError`) when a catalog is built, never mapped: two ids can
    therefore never store the same version."""
    if CATALOG_VERSION_PATTERN.fullmatch(catalog_id) is None:
        raise CatalogError(f"catalog_id {catalog_id!r} cannot be a catalog_version (letters, digits and . _ : + - only, at most 64 characters, starting with a letter or digit; a '/' is refused)")
    return catalog_id


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _text(row: Mapping[str, Any], key: str, where: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{where}: missing or blank {key!r}")
    return value


def _enum(enum_type: Any, row: Mapping[str, Any], key: str, where: str) -> Any:
    text = _text(row, key, where)
    try:
        return enum_type(text)
    except ValueError:
        raise CatalogError(f"{where}: {key!r} is {text!r}, not one of {[m.value for m in enum_type]}") from None


# --- benchmarks -----------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class BenchmarkEntry:
    """What the catalog says about one benchmark (the fields of `BENCHMARKS.json` `entry_fields`)."""

    benchmark_id: str
    name: str
    provider: str
    source_id: str
    licensing: str
    currency: str
    return_basis: ReturnBasis
    dividend_treatment: str
    calendar_id: str
    series_form: SeriesForm
    proxy_of: Optional[str]
    synthetic: bool
    #: `risk/1.4` Ruling 5.5 (1.2): the LISTING of the ETF a proxy is built from (a `listing_id`). Set exactly for an ETF proxy, whose series the engine builds from that listing's RAW closes and cash
    #: dividends; None for a published index. (The committed `BENCHMARKS.json` documents this field; it has no entries yet.)
    proxy_listing_id: Optional[str] = None
    #: `risk/1.5` Ruling 5.7 (CP4F-4): the OTHER sources that serve this benchmark id, each with the `return_basis` it publishes (the entry's own `source_id` and `return_basis` are the primary's). A source that
    #: serves the id but is not declared here with the entry's basis is refused as a whole (a price-return copy must never fill a day the primary lacks). Empty for a single-source benchmark. Pairs of
    #: `(source_id, return_basis value)`, sorted; in `to_obj` only when set (every catalog digest recorded before the field existed is unchanged).
    additional_sources: Tuple[Tuple[str, str], ...] = ()
    #: `risk/1.9` Ruling 5.7 (1.9): the precision of a multi-source benchmark is DECLARED, never inferred from the levels. `official_decimals` is the index's own published precision `D`; `source_precisions` pairs each
    #: serving source (the entry's own and each additional one) with the decimals it writes, `d`. Both absent for a single-source benchmark; absent from `to_obj` when unset (no digest moves).
    official_decimals: Optional[int] = None
    source_precisions: Tuple[Tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        serving = {self.source_id} | {s for s, _b in self.additional_sources}
        if list(self.source_precisions) != sorted(set(self.source_precisions)) or len({s for s, _d in self.source_precisions}) != len(self.source_precisions) or any(s not in serving for s, _d in self.source_precisions):
            raise CatalogError(f"{self.benchmark_id}: source precisions must be sorted, one per serving source")
        for value in [self.official_decimals] + [d for _s, d in self.source_precisions]:
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise CatalogError(f"{self.benchmark_id}: a declared precision is a non-negative number of decimals")
        listed = [s for s, _b in self.additional_sources]
        if list(self.additional_sources) != sorted(set(self.additional_sources)) or any(s == self.source_id for s in listed) or len(set(listed)) != len(listed):  # a source is listed once, with one basis
            raise CatalogError(f"{self.benchmark_id}: additional_sources must be sorted, unique and not the primary source")
        if not is_benchmark_id(self.benchmark_id):
            raise CatalogError(f"benchmark_id {self.benchmark_id!r} is not a valid id")
        if self.proxy_listing_id is not None:
            try:
                uuid.UUID(self.proxy_listing_id)
            except (ValueError, AttributeError, TypeError):
                raise CatalogError(f"{self.benchmark_id}: proxy_listing_id must be a listing id (a UUID)") from None
        if not _CURRENCY.fullmatch(self.currency):
            raise CatalogError(f"{self.benchmark_id}: currency {self.currency!r} is not an ISO 4217 code")

    def to_obj(self) -> Dict[str, Any]:
        out = {"benchmark_id": self.benchmark_id, "name": self.name, "provider": self.provider, "source_id": self.source_id, "licensing": self.licensing, "currency": self.currency,
               "return_basis": self.return_basis.value, "dividend_treatment": self.dividend_treatment, "calendar_id": self.calendar_id, "series_form": self.series_form.value,
               "proxy_of": self.proxy_of, "synthetic": self.synthetic}
        if self.proxy_listing_id is not None:  # present only when set: every catalog digest recorded before the field existed is unchanged
            out["proxy_listing_id"] = self.proxy_listing_id
        precision = dict(self.source_precisions)
        if self.additional_sources:
            out["additional_sources"] = [dict({"source_id": s, "return_basis": b}, **({"precision_decimals": precision[s]} if s in precision else {})) for s, b in self.additional_sources]
        if self.official_decimals is not None:
            out["official_decimals"] = self.official_decimals
        if self.source_id in precision:
            out["precision_decimals"] = precision[self.source_id]
        return out

    @property
    def digest(self) -> str:
        return _digest(self.to_obj())


def _benchmark_entry(row: Mapping[str, Any], allow_synthetic: bool) -> BenchmarkEntry:
    where = f"benchmark entry {row.get('benchmark_id')!r}"
    synthetic = row.get("synthetic")
    if not isinstance(synthetic, bool):
        raise CatalogError(f"{where}: 'synthetic' must be true or false")
    if synthetic and not allow_synthetic:
        raise CatalogError(f"{where}: a synthetic series is never catalogued (market-data Ruling 4.8)")
    proxy = row.get("proxy_of")
    if proxy is not None and (not isinstance(proxy, str) or not proxy.strip()):
        raise CatalogError(f"{where}: 'proxy_of' must be null or a name")
    extra = row.get("additional_sources", [])
    if not isinstance(extra, list) or any(not isinstance(x, dict) or not {"source_id", "return_basis"} <= set(x) <= {"source_id", "return_basis", "precision_decimals"}
                                           or not isinstance(x["source_id"], str) or not x["source_id"].strip() for x in extra):
        raise CatalogError(f"{where}: 'additional_sources' must be a list of {{source_id, return_basis[, precision_decimals]}}")
    precisions = {x["source_id"]: x["precision_decimals"] for x in extra if "precision_decimals" in x}
    if row.get("precision_decimals") is not None:
        precisions[_text(row, "source_id", where)] = row["precision_decimals"]
    try:
        additional = tuple(sorted({(x["source_id"], ReturnBasis(x["return_basis"]).value) for x in extra}))
    except ValueError:
        raise CatalogError(f"{where}: an additional source has an unknown return_basis") from None
    if len({s for s, _b in additional}) != len(additional):
        raise CatalogError(f"{where}: an additional source is listed twice (with different return bases)")
    return BenchmarkEntry(_text(row, "benchmark_id", where), _text(row, "name", where), _text(row, "provider", where), _text(row, "source_id", where), _text(row, "licensing", where),
                          _text(row, "currency", where), _enum(ReturnBasis, row, "return_basis", where), _text(row, "dividend_treatment", where), _text(row, "calendar_id", where),
                          _enum(SeriesForm, row, "series_form", where), proxy, synthetic, row.get("proxy_listing_id"), additional, row.get("official_decimals"),
                          tuple(sorted(precisions.items())))


@dataclass(frozen=True)
class BenchmarkCatalog:
    """The admitted benchmarks. `catalog_id` names the catalog; a selection pins it as its `catalog_version` (`catalog_version_of`); `digest` is what a manifest records."""

    catalog_id: str
    entries: Tuple[BenchmarkEntry, ...]
    synthetic: bool = False  # True only for a test catalog built with `allow_synthetic` (never the committed file)

    def __post_init__(self) -> None:
        catalog_version_of(self.catalog_id)  # refuses an id that cannot be stored as a catalog_version
        ids = [e.benchmark_id for e in self.entries]
        if len(set(ids)) != len(ids):
            raise CatalogError("two entries share a benchmark_id")
        if list(ids) != sorted(ids):
            object.__setattr__(self, "entries", tuple(sorted(self.entries, key=lambda e: e.benchmark_id)))

    def get(self, benchmark_id: Optional[str]) -> Optional[BenchmarkEntry]:
        for e in self.entries:
            if e.benchmark_id == benchmark_id:
                return e
        return None

    @property
    def digest(self) -> str:
        return _digest({"catalog_id": self.catalog_id, "entries": [e.to_obj() for e in self.entries]})


def parse_benchmark_catalog(raw: bytes, *, allow_synthetic: bool = False) -> BenchmarkCatalog:
    """Parse `BENCHMARKS.json`. `allow_synthetic` is for a TEST catalog built from a fixture's own definitions; the committed file never passes it."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise CatalogError(f"the benchmark catalog is not JSON: {error}") from None
    if not isinstance(data, dict):
        raise CatalogError("the benchmark catalog must be a JSON object")
    catalog_id = _text(data, "catalog_id", "benchmark catalog")
    entries = data.get("entries")
    if not isinstance(entries, list) or not all(isinstance(r, dict) for r in entries):
        raise CatalogError("the benchmark catalog needs an 'entries' list of objects")
    return BenchmarkCatalog(catalog_id, tuple(_benchmark_entry(row, allow_synthetic) for row in entries), allow_synthetic)


def admit_selection(selection: BenchmarkSelection, catalog: BenchmarkCatalog) -> BenchmarkSelection:
    """The catalog check of a selection (PD-0039 D5; the main session's ruling 2026-10-02): a SELECT must name an entry of `catalog`, and the row records the catalog it was admitted under
    (`catalog_version` = the catalog's id in its stored form, `catalog_version_of`). A CLEAR and a REVERSAL name no benchmark and pass unchanged. A SELECT that already names another catalog version is
    refused, never silently re-stamped."""
    if selection.record_type is not RecordType.SELECT:
        return selection
    if catalog.get(selection.benchmark_id) is None:
        raise BenchmarkNotInCatalogError(str(selection.benchmark_id), catalog.catalog_id)
    version = catalog_version_of(catalog.catalog_id)
    if selection.catalog_version is not None and selection.catalog_version != version:
        raise CatalogVersionMismatchError(f"the selection names catalog {selection.catalog_version!r}; it is being admitted under {version!r}")
    return replace(selection, catalog_version=version)


# --- risk-free series -----------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskFreeEntry:
    """One admitted risk-free series (`RISK_FREE.json` `entry_fields`): exactly one per currency."""

    currency: str
    series_id: str
    source_id: str
    instrument: str
    tenor_days: int
    quote_type: str
    day_count_basis: str
    unit: str
    decimals_published: int
    date_semantics: str
    calendar_id: str
    revision_policy: str

    def to_obj(self) -> Dict[str, Any]:
        return {"currency": self.currency, "series_id": self.series_id, "source_id": self.source_id, "instrument": self.instrument, "tenor_days": self.tenor_days,
                "quote_type": self.quote_type, "day_count_basis": self.day_count_basis, "unit": self.unit, "decimals_published": self.decimals_published,
                "date_semantics": self.date_semantics, "calendar_id": self.calendar_id, "revision_policy": self.revision_policy}


def _risk_free_entry(row: Mapping[str, Any]) -> RiskFreeEntry:
    where = f"risk-free entry {row.get('series_id')!r}"
    currency = _text(row, "currency", where)
    if not _CURRENCY.fullmatch(currency):
        raise CatalogError(f"{where}: currency {currency!r} is not an ISO 4217 code")
    for key in ("tenor_days", "decimals_published"):
        if isinstance(row.get(key), bool) or not isinstance(row.get(key), int) or row[key] < 0:
            raise CatalogError(f"{where}: {key!r} must be a non-negative integer")
    return RiskFreeEntry(currency, _text(row, "series_id", where), _text(row, "source_id", where), _text(row, "instrument", where), row["tenor_days"], _text(row, "quote_type", where),
                         _text(row, "day_count_basis", where), _text(row, "unit", where), row["decimals_published"], _text(row, "date_semantics", where), _text(row, "calendar_id", where),
                         _text(row, "revision_policy", where))


@dataclass(frozen=True)
class RiskFreeCatalog:
    catalog_id: str
    entries: Tuple[RiskFreeEntry, ...]

    def __post_init__(self) -> None:
        catalog_version_of(self.catalog_id)  # the id is cited in manifests and must be a well-formed identifier like the benchmark catalog's
        currencies = [e.currency for e in self.entries]
        if len(set(currencies)) != len(currencies):
            raise CatalogError("two admitted risk-free series for one currency (AMBIGUOUS_RISK_FREE_SERIES): the rule is one per currency (Ruling 4.1)")
        object.__setattr__(self, "entries", tuple(sorted(self.entries, key=lambda e: e.currency)))

    def for_currency(self, currency: str) -> Optional[RiskFreeEntry]:
        for e in self.entries:
            if e.currency == currency:
                return e
        return None

    def admits(self, currency: str, series_id: str) -> bool:
        entry = self.for_currency(currency)
        return entry is not None and entry.series_id == series_id

    @property
    def digest(self) -> str:
        return _digest({"catalog_id": self.catalog_id, "entries": [e.to_obj() for e in self.entries]})


def parse_risk_free_catalog(raw: bytes) -> RiskFreeCatalog:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise CatalogError(f"the risk-free catalog is not JSON: {error}") from None
    if not isinstance(data, dict):
        raise CatalogError("the risk-free catalog must be a JSON object")
    catalog_id = _text(data, "catalog_id", "risk-free catalog")
    entries = data.get("entries")
    if not isinstance(entries, list) or not all(isinstance(r, dict) for r in entries):
        raise CatalogError("the risk-free catalog needs an 'entries' list of objects")
    return RiskFreeCatalog(catalog_id, tuple(_risk_free_entry(r) for r in entries))
