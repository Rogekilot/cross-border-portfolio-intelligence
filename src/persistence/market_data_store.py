"""PostgreSQL market-data store: an append-only, rebuildable PROJECTION of a market-data release
(tech plan 15.5 and 15.17; migrations 0009-0011).

What it is. The files are the record. The tables hold what the adapters and the file-level checks made of the files
of ONE release (`write_release`); `read_release` returns a `PostgresMarketData`, which implements the same read-only
`MarketDataPort` as `marketdata.store.InMemoryMarketData` and gives the same answers, because it IS that store,
rebuilt from the stored rows: every lookup rule (price of date, FX crosses, reconciliation, freshness, V0
exclusions, the no-admitted-source cause) lives in one place and is not re-written in SQL. The read is eager (one
query per table for the pinned release; a release is small and immutable), so no lookup ever reads "latest", and a
projection that does not reproduce its recorded digest is refused (`ProjectionDigestMismatchError`).

Rules this module relies on, all enforced by the database (migration 0011) and tested:
- every md_* table refuses UPDATE, DELETE and TRUNCATE for every role;
- a release is sealed: child rows are accepted only from the transaction that created the release row;
- no observation table has a ticker or FIGI column; `listing_id` is the key;
- every number is bounded (below 1E30, at most 24 decimals; precision bounds at most 100) by CHECK.

Roles. Writing (`write_release`) is a privileged step (the schema owner or a loader role). The application role is
granted SELECT on the md_* tables only (tech plan 15.17), which is all `read_release` needs. The listing's MIC for
the freshness and no-admitted-source rules is supplied by the caller (`exchange_of`), exactly as for the in-memory
store, so no grant on `listing` is needed.

`conn` is a psycopg 3 connection; this module does not import the driver. Statements run in `conn.transaction()`.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import uuid
from dataclasses import dataclass
from decimal import ROUND_CEILING, Context, Decimal
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from domain.currency import CurrencyCode, Money
from domain.ledger import SplitRatio
from marketdata import contracts as c
from marketdata.calendars import CalendarSet
from marketdata.canonical import (
    canonical_decimal,
    canonical_json,
    lineage_from_json_obj,
    lineage_json_obj,
    observation_obj,
    sha256_hex,
)
from marketdata.manifest import FileManifest, MarketDataRelease, SourceRecord, SourceRegistry
from marketdata.profiles import SOURCE_NOT_ADMITTED, SOURCES as SOURCE_PROFILES, ProfileNotAdmittedError, require_listing_market
from marketdata.segments import file_dates_of, require_rows_inside_request
from marketdata.port import (
    ActionSet,
    BenchmarkSet,
    FXLookup,
    FXSeries,
    QuoteLookup,
    QuoteSeries,
    RiskFreeLookup,
    RiskFreeSet,
)
from marketdata.store import (
    BenchmarkEntry,
    FXFileWindow,
    InMemoryMarketData,
    RiskFreeEntry,
    SeriesExclusion,
    StoreContents,
)

#: The tables of the projection, in dependency order (a table after the ones it references). The least-privilege
#: grant spec gives the application role SELECT on exactly these.
MD_TABLES: Tuple[str, ...] = (
    "md_file", "md_release", "md_release_file", "md_quote", "md_fx_rate", "md_corporate_action",
    "md_benchmark", "md_benchmark_point", "md_adjusted_quote", "md_calendar", "md_series_exclusion",
    "md_risk_free", "md_risk_free_point",  # CP4b-2, migration 0016
)

_APPEND_ONLY = "md_append_only"
_SEALED = "md_release_sealed"
_PIN_STALE = "md_search_path_pin_stale"


class MarketDataStoreError(Exception):
    """Base class for market-data store failures."""


class RegistryDisagreesWithStoredRowsError(MarketDataStoreError):
    """The source registry in force now disagrees with what the stored rows carry (upstream, independence group): the digest would pin facts the computation does not use (CP4-8)."""


class ReleaseSealedError(MarketDataStoreError):
    """A row was offered for a release that is sealed (its creating transaction has committed) or unknown."""


class MarketDataImmutableError(MarketDataStoreError):
    """UPDATE, DELETE or TRUNCATE of a market-data table: the projection is append-only."""


class MarketDataValueOutOfRangeError(MarketDataStoreError):
    """A number is outside the bounds of the projection (below 1E30, at most 24 decimals)."""


class MarketDataRuleRejectedError(MarketDataStoreError):
    """Another database rule (a CHECK, a foreign key, a pin guard) rejected the write."""

    def __init__(self, constraint_name: Optional[str], message: str) -> None:
        super().__init__(f"{constraint_name or 'database rule'}: {message}")
        self.constraint_name = constraint_name


class ReleaseConflictError(MarketDataStoreError):
    """The release id is already projected, but the rows offered now differ from the stored ones (a different
    adapter version, say). A release is never overwritten: cut a new release."""


class FileRegistrationConflictError(MarketDataStoreError):
    """A file with this SHA-256 is already registered with a different manifest."""


class ReleaseNotFoundError(LookupError):
    pass


class ProjectionDigestMismatchError(MarketDataStoreError):
    """The rows read back do not reproduce the digest recorded when the release was projected."""


class ReleaseKeyMismatchError(MarketDataStoreError):
    """C2-6: a release row's stored content (or file list) is not the release its key names."""


def translate_error(exc: BaseException) -> Optional[MarketDataStoreError]:
    """Map a driver error to a typed store error, or None if it is not one of ours."""
    sqlstate = getattr(exc, "sqlstate", None)
    if not isinstance(sqlstate, str):
        return None
    diag = getattr(exc, "diag", None)
    name = getattr(diag, "constraint_name", None)
    if sqlstate == "23001" and name == _APPEND_ONLY:
        return MarketDataImmutableError(str(exc))
    if sqlstate == "23514" and name == _SEALED:
        return ReleaseSealedError(str(exc))
    if sqlstate == "23514" and name == "md_release_key_matches_content":  # migration 0012 (C2-6)
        return ReleaseKeyMismatchError(str(exc))
    if sqlstate == "22003" or (sqlstate.startswith("23") and isinstance(name, str) and name.endswith("_bounds")):
        return MarketDataValueOutOfRangeError(str(exc))
    if sqlstate.startswith("23"):
        return MarketDataRuleRejectedError(name, str(exc))
    return None


# --- the projection digest ------------------------------------------------------------------------------

def _in_projection_order(readings: Iterable[c.SourceReading]) -> List[c.SourceReading]:
    """Quotes, then rates, then actions, each kind in its original order (a stable grouping). The kinds never
    interact in a lookup, so only the order WITHIN a kind matters; the tables hold one kind each, so this is the
    order a read returns and the order the digest is taken in."""
    def rank(r: c.SourceReading) -> int:
        return 0 if isinstance(r.observation, c.QuoteObservation) else (
            1 if isinstance(r.observation, c.FXObservation) else 2)

    return sorted(readings, key=rank)


def projection_obj(release: MarketDataRelease, contents: StoreContents, calendars: CalendarSet) -> Dict[str, Any]:
    """The canonical document a projection is judged by: every reading in reading order, the benchmarks, the
    verification rows, the file windows, the exclusions and the calendars. It is computed from objects, so the same
    document comes out of a store built from files and of a store read back from the tables."""
    doc = {
        "release_id": release.release_id,
        "convention_set_id": release.convention_set_id,
        "contains_synthetic": contents.contains_synthetic,
        "readings": [
            {"source_id": r.source_id, "independence_group": r.independence_group, "file_sha256": r.file_sha256,
             "observation": observation_obj(r.observation)} for r in _in_projection_order(contents.readings)],
        "benchmarks": [
            {"source_id": b.source_id, "independence_group": b.independence_group, "file_sha256": b.file_sha256,
             "series": observation_obj(b.series)} for b in contents.benchmarks],
        "adjusted": [observation_obj(a) for a in contents.adjusted],
        "fx_windows": [[sha, w.start, w.end] for sha, w in sorted(contents.fx_windows)],
        # a price series is keyed by listing; an FX series (1.7 V0-FX) by currency, appended only when set so a price-only
        # projection keeps its digest
        "exclusions": [[str(e.listing_id), e.file_sha256, e.test, e.reason] + ([e.currency] if e.currency else [])
                       for e in contents.exclusions],
        "calendars": [observation_obj(cal) for cal in calendars.calendars()],
    }
    if contents.risk_free:  # CP4b-2 (migration 0016): only when a release holds a risk-free series, so every earlier release keeps its digest byte for byte
        doc["risk_free"] = [{"source_id": e.source_id, "independence_group": e.independence_group, "file_sha256": e.file_sha256, "series": observation_obj(e.series)} for e in contents.risk_free]
    return doc


def projection_digest(release: MarketDataRelease, contents: StoreContents, calendars: CalendarSet) -> str:
    return sha256_hex(canonical_json(projection_obj(release, contents, calendars)).encode("utf-8"))


# --- precision bounds at storage (market-data/1.4 section 9C item 6) -------------------------------------------

#: The most decimal places a stored precision bound may have (migration 0010). `precision_bound` is METADATA about a
#: reading's precision: never a money amount, quantity or ledger value, and it only ever enters a comparison. PD-0026
#: (title and text: ledger values; enforced on `ledger_event` by 0008) does not reach it (main-session ruling,
#: 2026-10-01); the Quant's condition is that a bound is stored EXACTLY or rounded toward +infinity, never lower.
BOUND_MAX_SCALE = 100
_BOUND_CONTEXT = Context(prec=400)
_BOUND_QUANTUM = Decimal(1).scaleb(-BOUND_MAX_SCALE)


def bound_for_storage(bound: Decimal) -> Decimal:
    """`bound` exactly when it has at most 100 decimals; otherwise `bound` rounded toward +infinity to 100 decimals (a
    larger bound is the conservative direction: it can only make two readings agree more easily, never less).
    Exact decimal expansions of 2^-k have k decimals, so every binary bound down to 2^-100 is stored exactly."""
    exponent = bound.as_tuple().exponent
    if not isinstance(exponent, int) or exponent >= -BOUND_MAX_SCALE:
        return bound
    return bound.quantize(_BOUND_QUANTUM, rounding=ROUND_CEILING, context=_BOUND_CONTEXT)


def stored_contents(contents: StoreContents) -> StoreContents:
    """`contents` with every precision bound passed through `bound_for_storage`. It is applied BEFORE the projection
    digest is taken, so the digest, the rows and a read-back all describe the same values. Unchanged (the same
    object) when no bound needed rounding, which is every real source's case."""
    changed = False
    readings: List[c.SourceReading] = []
    for r in contents.readings:
        obs = r.observation
        if isinstance(obs, c.QuoteObservation):
            fixed = bound_for_storage(obs.precision_bound)
            if fixed != obs.precision_bound or fixed.as_tuple() != obs.precision_bound.as_tuple():
                r = dataclasses.replace(r, observation=dataclasses.replace(obs, precision_bound=fixed))
                changed = True
        readings.append(r)
    adjusted: List[c.AdjustedQuote] = []
    for a in contents.adjusted:
        fixed_bound = bound_for_storage(a.precision_bound)
        fixed_fields = None if a.field_bounds is None else tuple(bound_for_storage(b) for b in a.field_bounds)
        if fixed_bound.as_tuple() != a.precision_bound.as_tuple() or fixed_fields != a.field_bounds:
            a = dataclasses.replace(a, precision_bound=fixed_bound, field_bounds=fixed_fields)  # type: ignore[arg-type]
            changed = True
        adjusted.append(a)
    if not changed:
        return contents
    return dataclasses.replace(contents, readings=tuple(readings), adjusted=tuple(adjusted))


# --- writing ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ProjectionResult:
    release_id: str
    created: bool  # False: this exact projection already existed (an idempotent no-op)
    projection_digest: str
    row_counts: Tuple[Tuple[str, int], ...]


def _jsonb(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def _bounds(b: Optional[Tuple[Decimal, ...]]) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    return (None, None, None) if b is None else (b[0], b[1], b[2])


def _action_detail(obs: c.CorporateActionObservation) -> Dict[str, Any]:
    out = {
        "paid_currency": None if obs.paid_currency is None else obs.paid_currency.code,
        "issuer_fx_rate": None if obs.issuer_fx_rate is None else canonical_decimal(obs.issuer_fx_rate),
        "old_ticker": obs.old_ticker, "new_ticker": obs.new_ticker, "unsupported_label": obs.unsupported_label,
    }
    if obs.paid_amount is not None:  # present only when stated: every stored detail recorded before the field existed is unchanged
        out["paid_amount"] = canonical_decimal(obs.paid_amount)
    return out


def _insert_files(conn: Any, manifests: Sequence[FileManifest]) -> None:
    for m in manifests:
        text = _jsonb(m.to_obj())
        row = conn.execute(
            "INSERT INTO md_file (file_sha256, source_id, data_kind, usage_scope, retrieval_time, "
            "declared_adjustment, market, manifest) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
            "ON CONFLICT (file_sha256) DO NOTHING RETURNING file_sha256",
            (m.file_sha256, m.source_id, m.data_kind.value, m.usage_scope.value, m.retrieval_time,
             m.declared_adjustment.value, m.market, text)).fetchone()
        if row is None:
            stored = conn.execute("SELECT manifest FROM md_file WHERE file_sha256 = %s", (m.file_sha256,)).fetchone()
            if stored is None or json.loads(_jsonb(stored[0])) != json.loads(text):
                raise FileRegistrationConflictError(
                    f"file {m.file_sha256} is already registered with a different manifest")


def _insert_release_rows(
    conn: Any, release: MarketDataRelease, manifests: Sequence[FileManifest], contents: StoreContents,
    calendars: CalendarSet, digest: str,
) -> None:
    rid = release.release_id
    conn.execute(
        "INSERT INTO md_release (release_id, name, convention_set_id, release_content, contains_synthetic, "
        "projection_digest) VALUES (%s, %s, %s, %s::jsonb, %s, %s)",
        (rid, release.name, release.convention_set_id, _jsonb(json.loads(release.to_json())),
         contents.contains_synthetic, digest))
    windows = dict(contents.fx_windows)
    for ordinal, sha in enumerate(release.files):
        w = windows.get(sha)
        conn.execute(
            "INSERT INTO md_release_file (release_id, file_sha256, ordinal, has_fx_window, fx_window_start, "
            "fx_window_end) VALUES (%s, %s, %s, %s, %s, %s)",
            (rid, sha, ordinal, w is not None, None if w is None else w.start, None if w is None else w.end))
    counters = {"quote": 0, "fx": 0, "action": 0}
    for r in _in_projection_order(contents.readings):
        obs = r.observation
        timing = (obs.timing.source_time, obs.timing.delay_status.value)  # type: ignore[attr-defined]
        lineage = _jsonb(lineage_json_obj(obs.lineage))  # type: ignore[attr-defined]
        if isinstance(obs, c.QuoteObservation):
            conn.execute(
                "INSERT INTO md_quote (release_id, row_ordinal, file_sha256, source_id, independence_group, "
                "listing_id, value_date, price, currency, volume, price_kind, recovered, precision_bound, "
                "observed_at, source_time, delay_status, lineage) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                (rid, counters["quote"], r.file_sha256, r.source_id, r.independence_group, obs.listing_id,
                 obs.value_date, obs.price, obs.currency.code, obs.volume, obs.price_kind.value, obs.recovered,
                 obs.precision_bound, obs.observed_at, timing[0], timing[1], lineage))
            counters["quote"] += 1
        elif isinstance(obs, c.FXObservation):
            conn.execute(
                "INSERT INTO md_fx_rate (release_id, row_ordinal, file_sha256, source_id, independence_group, "
                "base_currency, quote_currency, value_date, rate, rate_basis, observed_at, source_time, "
                "delay_status, lineage) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                (rid, counters["fx"], r.file_sha256, r.source_id, r.independence_group, obs.base_currency.code,
                 obs.quote_currency.code, obs.value_date, obs.rate, obs.rate_basis, obs.observed_at,
                 timing[0], timing[1], lineage))
            counters["fx"] += 1
        else:
            assert isinstance(obs, c.CorporateActionObservation)
            ratio, amount = obs.split_ratio, obs.amount_per_unit
            conn.execute(
                "INSERT INTO md_corporate_action (release_id, row_ordinal, file_sha256, source_id, "
                "independence_group, listing_id, action_type, effective_date, split_new, split_old, "
                "amount_per_unit, amount_currency, pay_date, record_date, detail, source_time, delay_status, "
                "lineage) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, "
                "%s::jsonb)",
                (rid, counters["action"], r.file_sha256, r.source_id, r.independence_group, obs.listing_id,
                 obs.action_type.value, obs.effective_date,
                 None if ratio is None else ratio.new_units, None if ratio is None else ratio.old_units,
                 None if amount is None else amount.amount, None if amount is None else amount.currency.code,
                 obs.pay_date, obs.record_date, _jsonb(_action_detail(obs)), timing[0], timing[1], lineage))
            counters["action"] += 1
    for ordinal, b in enumerate(contents.benchmarks):
        s = b.series
        conn.execute(
            "INSERT INTO md_benchmark (release_id, benchmark_ordinal, file_sha256, source_id, independence_group, "
            "benchmark_id, provider, value_kind, currency, license_status, display_permitted, terms_ref, "
            "source_time, delay_status, lineage) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (rid, ordinal, b.file_sha256, b.source_id, b.independence_group, s.benchmark_id, s.provider,
             s.value_kind.value, s.currency.code, s.licensing.license_status.value, s.licensing.display_permitted,
             s.licensing.terms_ref, s.timing.source_time, s.timing.delay_status.value,
             _jsonb(lineage_json_obj(s.lineage))))
        for p_ordinal, p in enumerate(s.points):
            conn.execute(
                "INSERT INTO md_benchmark_point (release_id, benchmark_ordinal, point_ordinal, value_date, value) "
                "VALUES (%s, %s, %s, %s, %s)", (rid, ordinal, p_ordinal, p.value_date, p.value))
    for ordinal, e in enumerate(contents.risk_free):
        s = e.series
        conn.execute(
            "INSERT INTO md_risk_free (release_id, risk_free_ordinal, file_sha256, source_id, independence_group, series_id, name, provider, currency, "
            "instrument, tenor_weeks, quote_type, day_count_basis, unit, decimals_published, date_semantics, calendar_id, revision_policy, license_status, "
            "display_permitted, terms_ref, source_time, delay_status, lineage) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (rid, ordinal, e.file_sha256, e.source_id, e.independence_group, s.series_id, s.name, s.provider, s.currency.code, s.instrument, s.tenor_weeks,
             s.quote_type.value, s.day_count_basis, s.unit.value, s.decimals_published, s.date_semantics, s.calendar_id, s.revision_policy.value,
             s.licensing.license_status.value, s.licensing.display_permitted, s.licensing.terms_ref, s.timing.source_time, s.timing.delay_status.value,
             _jsonb(lineage_json_obj(s.lineage))))
        for p_ordinal, p in enumerate(s.points):
            conn.execute(
                "INSERT INTO md_risk_free_point (release_id, risk_free_ordinal, point_ordinal, value_date, rate, term_days) VALUES (%s, %s, %s, %s, %s, %s)",
                (rid, ordinal, p_ordinal, p.value_date, p.rate, p.term_days))
    for ordinal, a in enumerate(contents.adjusted):
        o_b, h_b, l_b = _bounds(a.field_bounds)
        conn.execute(
            "INSERT INTO md_adjusted_quote (release_id, row_ordinal, file_sha256, listing_id, value_date, open, "
            "high, low, close, currency, adjustment_status, adjustment_method, anchor, vintage, precision_bound, "
            "open_bound, high_bound, low_bound, source_time, delay_status, lineage) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (rid, ordinal, a.lineage.file_sha256, a.listing_id, a.value_date, a.open, a.high, a.low, a.close,
             a.currency.code, a.label.adjustment_status.value, a.label.method.value,
             None if a.label.anchor is None else a.label.anchor.value, a.label.vintage, a.precision_bound,
             o_b, h_b, l_b, a.timing.source_time, a.timing.delay_status.value, _jsonb(lineage_json_obj(a.lineage))))
    for cal in calendars.calendars():
        conn.execute(
            "INSERT INTO md_calendar (release_id, file_sha256, calendar_id, kind, applies_to, timezone, "
            "covers_from, covers_to, dates, actual_through, evidence, prepared_by, prepared_on, version_label, "
            "default_close, early_closes, fixing_time, publication_time, lineage) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)",
            (rid, cal.lineage.file_sha256, cal.calendar_id, cal.kind.value, list(cal.applies_to), cal.timezone,
             cal.covers_from, cal.covers_to, list(cal.dates), cal.actual_through, cal.evidence, cal.prepared_by,
             cal.prepared_on, cal.version_label, cal.default_close,
             _jsonb([[d.isoformat(), t.isoformat()] for d, t in cal.early_closes]), cal.fixing_time,
             cal.publication_time, _jsonb(lineage_json_obj(cal.lineage))))
    for ordinal, e in enumerate(contents.exclusions):
        conn.execute(
            "INSERT INTO md_series_exclusion (release_id, exclusion_ordinal, listing_id, file_sha256, test, "
            "reason, currency) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (rid, ordinal, e.listing_id, e.file_sha256, e.test, e.reason, e.currency))


def row_counts(conn: Any, release_id: str) -> Tuple[Tuple[str, int], ...]:
    out = []
    for table in MD_TABLES:
        if table in ("md_file",):
            continue
        if table == "md_benchmark_point":
            n = conn.execute("SELECT count(*) FROM md_benchmark_point WHERE release_id = %s", (release_id,)).fetchone()[0]
        elif table == "md_release":
            n = conn.execute("SELECT count(*) FROM md_release WHERE release_id = %s", (release_id,)).fetchone()[0]
        else:
            n = conn.execute(f"SELECT count(*) FROM {table} WHERE release_id = %s", (release_id,)).fetchone()[0]
        out.append((table, int(n)))
    return tuple(out)


def _require_admitted_to_store(
    release: MarketDataRelease, manifests: Sequence[FileManifest], contents: StoreContents,
    exchange_of: Optional[Callable[[uuid.UUID], Optional[str]]],
) -> None:
    """The tables are append-only (migration 0011), so a row that `read_release` would refuse could never be removed again: the
    same admission gate (market-data/1.15 Ruling 7A.3: a terms attestation is necessary, never sufficient) is applied BEFORE
    anything is written. Source level: a REAL file of a source that is pending observation, or that Appendix A.5 does not list for
    its markets. Listing level, when the caller supplies `exchange_of` (the identity's `exchange_mic`; `write_release` holds no
    identity of its own): a REAL reading bound to a listing whose market the source's profile does not cover or admit
    (`require_listing_market`). Without `exchange_of` the listing level cannot run here, and `read_release` still refuses the rows."""
    for m in manifests:
        gated = SOURCE_PROFILES.get(m.source_id)
        if m.usage_scope is not c.UsageScope.SYNTHETIC_TEST and gated is not None and gated.gate_refusal is not None:
            code, why = gated.gate_refusal
            raise ProfileNotAdmittedError(
                f"{code}: release {release.release_id}: source {m.source_id!r} is not admitted: {why} (nothing is written)", code)
    # market-data/1.16 Ruling 4.7 item 6 (section 11 item 27): a source with NO profile never supplies a real price reading or corporate-action
    # record. That needs no identity, so it is judged here whether or not `exchange_of` is supplied (SOURCE_NOT_ADMITTED).
    for r in contents.readings:
        obs = r.observation
        if isinstance(obs, (c.QuoteObservation, c.CorporateActionObservation)) and not obs.lineage.is_synthetic and r.source_id not in SOURCE_PROFILES:
            raise ProfileNotAdmittedError(
                f"{SOURCE_NOT_ADMITTED}: release {release.release_id}: source {r.source_id!r} has no profile: a source with no profile supplies "
                "no real reading (Ruling 4.7 item 6; nothing is written)", SOURCE_NOT_ADMITTED)
    for a in contents.adjusted:
        if not a.lineage.is_synthetic and (a.lineage.source_id or "") not in SOURCE_PROFILES:
            raise ProfileNotAdmittedError(
                f"{SOURCE_NOT_ADMITTED}: release {release.release_id}: source {a.lineage.source_id!r} has no profile: a source with no profile supplies "
                "no real reading (Ruling 4.7 item 6; nothing is written)", SOURCE_NOT_ADMITTED)
    if exchange_of is None:
        return
    # the listing level: the MIC maps to a V1 market (an unmapped MIC is LISTING_EXCHANGE_UNKNOWN), the profile covers it, is admitted, lists the upstream
    for r in contents.readings:
        obs = r.observation
        if isinstance(obs, (c.QuoteObservation, c.CorporateActionObservation)) and not obs.lineage.is_synthetic:
            require_listing_market(r.source_id, obs.listing_id, exchange_of(obs.listing_id))
    for a in contents.adjusted:
        if not a.lineage.is_synthetic:
            require_listing_market(a.lineage.source_id or "", a.listing_id, exchange_of(a.listing_id))


def write_release(
    conn: Any, release: MarketDataRelease, manifests: Sequence[FileManifest], contents: StoreContents,
    calendars: CalendarSet, *, exchange_of: Optional[Callable[[uuid.UUID], Optional[str]]] = None, count_rows: bool = True,
) -> ProjectionResult:
    """Project a release into the tables, in ONE transaction. Idempotent: the same release projected to the same
    rows is a no-op (`created` False); the same release id with different rows is `ReleaseConflictError`.
    Every number is bounded by the database (typed `MarketDataValueOutOfRangeError`). A REAL file or reading that the admission
    gate refuses is refused here, before any write (`ProfileNotAdmittedError`); see `_require_admitted_to_store`.

    `count_rows` (F1 R2, design 3.3, PD-0070 decision 1): the default `True` is the behaviour of every caller before R2 and returns
    the per-table counts in `ProjectionResult.row_counts`. `False` skips that read-back: the result's `row_counts` is the empty tuple
    and no table other than `md_file` and `md_release` is read. The real loader role holds `INSERT` on the thirteen tables but
    `SELECT` on those two only, so it calls this with `count_rows=False`. The written rows, the projection digest and the idempotence
    check are the same either way. The parameter is keyword-only and a plain `bool`."""
    if type(count_rows) is not bool:
        raise TypeError("count_rows must be a bool")
    if {m.file_sha256 for m in manifests} != set(release.files):
        raise ValueError("the manifests must be exactly the files the release names")
    _require_admitted_to_store(release, manifests, contents, exchange_of)
    require_rows_inside_request(file_dates_of(contents.readings, contents.benchmarks, contents.adjusted, contents.risk_free), {m.file_sha256: m for m in manifests})  # CP4M-10: the projection never holds a file that says one thing and holds another
    contents = stored_contents(contents)  # a bound beyond 100 decimals is rounded UP, before the digest (1.4 item 6)
    digest = projection_digest(release, contents, calendars)
    existing = conn.execute("SELECT projection_digest FROM md_release WHERE release_id = %s",
                            (release.release_id,)).fetchone()
    if existing is not None:
        return _already_projected(conn, release, existing[0], digest, count_rows)
    try:
        with conn.transaction():
            _insert_files(conn, manifests)
            _insert_release_rows(conn, release, manifests, contents, calendars, digest)
    except MarketDataStoreError:
        raise
    except Exception as exc:
        if getattr(exc, "sqlstate", None) == "23505":  # a concurrent writer projected the same release first
            existing = conn.execute("SELECT projection_digest FROM md_release WHERE release_id = %s",
                                    (release.release_id,)).fetchone()
            if existing is not None:
                return _already_projected(conn, release, existing[0], digest, count_rows)
        typed = translate_error(exc)
        if typed is not None:
            raise typed from exc
        raise
    return ProjectionResult(release.release_id, True, digest, row_counts(conn, release.release_id) if count_rows else ())


def _already_projected(conn: Any, release: MarketDataRelease, stored: str, offered: str, count_rows: bool = True) -> ProjectionResult:
    if stored != offered:
        raise ReleaseConflictError(
            f"release {release.release_id} is already projected with a different projection digest "
            f"({stored} stored, {offered} offered): a release is never overwritten; cut a new release")
    return ProjectionResult(release.release_id, False, stored, row_counts(conn, release.release_id) if count_rows else ())


# --- reading ---------------------------------------------------------------------------------------------------

def _timing(source_time: Optional[datetime.datetime], delay: str) -> c.SourceTiming:
    return c.SourceTiming(source_time, c.DataDelayStatus(delay))


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def pinned_schema(conn: Any) -> str:
    """The schema that holds the md_* tables, resolved ONCE per read: the first NON-TEMPORARY schema of the
    connection's search_path (the contract every migration and `persistence.migrator` already states: objects live in
    the first search_path schema). C2-5 (review of 39733e9): PostgreSQL searches the session's `pg_temp` schema FIRST
    for relations unless it is named in the path, and a role that can create TEMP tables (finweb_app can) could shadow
    `md_quote` and `md_release` with copies it altered, recompute the digest from them, and pass the digest check in
    that session. Every read is therefore SCHEMA-QUALIFIED with the name this returns, so a temporary relation is
    never reached. No temporary schema is ever returned; none found fails closed."""
    row = conn.execute(
        "SELECT s FROM unnest(current_schemas(false)) WITH ORDINALITY AS t(s, n) "
        "WHERE s NOT LIKE 'pg\\_temp%' AND s NOT LIKE 'pg\\_toast\\_temp%' ORDER BY n LIMIT 1").fetchone()
    if row is None:
        raise MarketDataStoreError("the connection's search_path names no non-temporary schema: nothing is read")
    return str(row[0])


def _lease_function(qs: str, table: str) -> str:
    """The table's lease-checked read function, `rw_<table>(release_id)` (F1 R3): the ONE place the derivation of the name is written."""
    return f"{qs}.rw_{table}(%s)"


def _select(conn: Any, qs: str, release_id: str, lease_checked: bool, columns: str, table: str, order: str,
            and_where: str = "", params: Tuple[Any, ...] = ()) -> List[Any]:
    """One read of one `md_*` table for one release. `lease_checked=False` is the table itself (the loader, the owner and every pre-F1 caller);
    `lease_checked=True` is the table's lease-checked read function (F1 R3, PD-0069), which the executor holds EXECUTE on instead of any
    privilege on the table: the function refuses without an open EXECUTE_CREATE or EXECUTE_REPRODUCE lease for the snapshot's release, and at or
    after the lease's `complete_by`. The WHERE and ORDER BY are the same in both forms, so a result is the same rows in the same order."""
    source = f"{_lease_function(qs, table)} AS {table}" if lease_checked else f"{qs}.{table}"
    args = ((release_id,) if lease_checked else ()) + (release_id,) + tuple(params)
    return conn.execute(f"SELECT {columns} FROM {source} WHERE release_id = %s{and_where} ORDER BY {order}", args).fetchall()


def _read_contents(conn: Any, release_id: str, schema: str, lease_checked: bool = False) -> Tuple[StoreContents, CalendarSet]:
    qs = _quoted(schema)

    def select(columns: str, table: str, order: str, and_where: str = "", params: Tuple[Any, ...] = ()) -> List[Any]:
        return _select(conn, qs, release_id, lease_checked, columns, table, order, and_where, params)

    readings: List[c.SourceReading] = []
    for row in select(
            "source_id, independence_group, file_sha256, listing_id, value_date, price, currency, volume, "
            "price_kind, recovered, precision_bound, observed_at, source_time, delay_status, lineage",
            "md_quote", "row_ordinal"):
        (source, group, sha, listing, day, price, ccy, volume, kind, recovered, bound, observed, stime, delay,
         lineage) = row
        readings.append(c.SourceReading(source, group, sha, c.QuoteObservation(
            listing, day, price, CurrencyCode(ccy), _timing(stime, delay), lineage_from_json_obj(lineage),
            observed, volume, c.PriceKind(kind), recovered, bound)))
    for row in select(
            "source_id, independence_group, file_sha256, base_currency, quote_currency, value_date, rate, "
            "rate_basis, observed_at, source_time, delay_status, lineage", "md_fx_rate", "row_ordinal"):
        source, group, sha, base, quote, day, rate, basis, observed, stime, delay, lineage = row
        readings.append(c.SourceReading(source, group, sha, c.FXObservation(
            CurrencyCode(base), CurrencyCode(quote), day, rate, _timing(stime, delay),
            lineage_from_json_obj(lineage), basis, observed)))
    for row in select(
            "source_id, independence_group, file_sha256, listing_id, action_type, effective_date, "
            "split_new, split_old, amount_per_unit, amount_currency, pay_date, record_date, detail, source_time, "
            "delay_status, lineage", "md_corporate_action", "row_ordinal"):
        (source, group, sha, listing, kind, day, s_new, s_old, amount, amount_ccy, pay, record, detail, stime,
         delay, lineage) = row
        readings.append(c.SourceReading(source, group, sha, c.CorporateActionObservation(
            listing, c.CorporateActionType(kind), day, _timing(stime, delay), lineage_from_json_obj(lineage),
            None if s_new is None else SplitRatio(s_new, s_old),
            None if amount is None else Money(amount, CurrencyCode(amount_ccy)),
            pay, record,
            None if detail["paid_currency"] is None else CurrencyCode(detail["paid_currency"]),
            None if detail["issuer_fx_rate"] is None else Decimal(detail["issuer_fx_rate"]),
            detail["old_ticker"], detail["new_ticker"], detail["unsupported_label"],
            None if detail.get("paid_amount") is None else Decimal(detail["paid_amount"]))))
    benchmarks: List[BenchmarkEntry] = []
    for row in select(
            "benchmark_ordinal, file_sha256, source_id, independence_group, benchmark_id, provider, "
            "value_kind, currency, license_status, display_permitted, terms_ref, source_time, delay_status, "
            "lineage", "md_benchmark", "benchmark_ordinal"):
        (ordinal, sha, source, group, bid, provider, kind, ccy, license_status, display, terms, stime, delay,
         lineage) = row
        points = tuple(c.BenchmarkPoint(d, v) for d, v in select(
            "value_date, value", "md_benchmark_point", "point_ordinal", " AND benchmark_ordinal = %s", (ordinal,)))
        benchmarks.append(BenchmarkEntry(source, group, sha, c.BenchmarkSeries(
            bid, provider, points, c.BenchmarkValueKind(kind), CurrencyCode(ccy), _timing(stime, delay),
            lineage_from_json_obj(lineage),
            c.LicensingMetadata(c.LicenseStatus(license_status), display, terms))))
    risk_free: List[RiskFreeEntry] = []
    for row in select(
            "risk_free_ordinal, file_sha256, source_id, independence_group, series_id, name, provider, currency, instrument, tenor_weeks, quote_type, day_count_basis, "
            "unit, decimals_published, date_semantics, calendar_id, revision_policy, license_status, display_permitted, terms_ref, source_time, delay_status, lineage",
            "md_risk_free", "risk_free_ordinal"):
        (ordinal, sha, source, group, series_id, name, provider, ccy, instrument, tenor, quote_type, basis, unit, decimals, semantics, calendar_id, revision,
         license_status, display, terms, stime, delay, lineage) = row
        points = tuple(c.RiskFreePoint(d, r, t) for d, r, t in select(
            "value_date, rate, term_days", "md_risk_free_point", "point_ordinal", " AND risk_free_ordinal = %s", (ordinal,)))
        risk_free.append(RiskFreeEntry(source, group, sha, c.RiskFreeSeries(
            series_id, name, provider, CurrencyCode(ccy), instrument, tenor, c.RiskFreeQuoteType(quote_type), basis, c.RateUnit(unit), decimals, semantics, calendar_id,
            c.RevisionPolicy(revision), points, _timing(stime, delay), lineage_from_json_obj(lineage), c.LicensingMetadata(c.LicenseStatus(license_status), display, terms))))
    adjusted: List[c.AdjustedQuote] = []
    for row in select(
            "listing_id, value_date, open, high, low, close, currency, adjustment_status, "
            "adjustment_method, anchor, vintage, precision_bound, open_bound, high_bound, low_bound, source_time, "
            "delay_status, lineage", "md_adjusted_quote", "row_ordinal"):
        (listing, day, o, h, low, close, ccy, status, method, anchor, vintage, bound, o_b, h_b, l_b, stime, delay,
         lineage) = row
        adjusted.append(c.AdjustedQuote(
            listing, day, o, h, low, close, CurrencyCode(ccy),
            c.AdjustmentLabel(c.AdjustmentStatus(status), c.AdjustmentMethod(method),
                              None if anchor is None else c.AnchorKind(anchor), vintage),
            _timing(stime, delay), lineage_from_json_obj(lineage), bound,
            None if o_b is None else (o_b, h_b, l_b)))
    windows = tuple(
        (sha, FXFileWindow(start, end)) for sha, start, end in select(
            "file_sha256, fx_window_start, fx_window_end", "md_release_file", "file_sha256", " AND has_fx_window"))
    exclusions = tuple(
        SeriesExclusion(listing, sha, test, reason, currency) for listing, sha, test, reason, currency in select(
            "listing_id, file_sha256, test, reason, currency", "md_series_exclusion", "exclusion_ordinal"))
    calendars: List[c.CalendarDays] = []
    for row in select(
            "file_sha256, calendar_id, kind, applies_to, timezone, covers_from, covers_to, dates, "
            "actual_through, evidence, prepared_by, prepared_on, version_label, default_close, early_closes, "
            "fixing_time, publication_time, lineage", "md_calendar", "calendar_id"):
        (_sha, cid, kind, applies, tz, c_from, c_to, dates, actual, evidence, by, on, version, close, early, fixing,
         publication, lineage) = row
        calendars.append(c.CalendarDays(
            calendar_id=cid, kind=c.CalendarKind(kind), applies_to=tuple(applies), timezone=tz, covers_from=c_from,
            covers_to=c_to, dates=tuple(dates), actual_through=actual, evidence=evidence, prepared_by=by,
            prepared_on=on, version_label=version, lineage=lineage_from_json_obj(lineage), default_close=close,
            early_closes=tuple((datetime.date.fromisoformat(d), datetime.time.fromisoformat(t)) for d, t in early),
            fixing_time=fixing, publication_time=publication))
    synthetic = _select(conn, qs, release_id, lease_checked, "contains_synthetic", "md_release", "release_id")[0][0]
    return (StoreContents(tuple(readings), tuple(benchmarks), tuple(adjusted), windows, exclusions, bool(synthetic), tuple(risk_free)),
            CalendarSet(calendars))


class PostgresMarketData:
    """The `MarketDataPort` (and the verification-only `adjusted_series`) over the projection of one release.
    Bound to exactly one release: nothing here reads "latest". See the module docstring."""

    def __init__(self, release: MarketDataRelease, contents: StoreContents, calendars: CalendarSet,
                 exchange_of: Optional[Callable[[uuid.UUID], Optional[str]]] = None,
                 source_records: Iterable[SourceRecord] = ()):
        self._release = release
        self._contents = contents
        self._calendars = calendars
        self._mem = InMemoryMarketData(
            release, contents.readings, contents.benchmarks, contents.adjusted, exchange_of=exchange_of,
            contains_synthetic=contents.contains_synthetic, fx_windows=dict(contents.fx_windows),
            exclusions=contents.exclusions, source_records=source_records, risk_free=contents.risk_free)

    def source_registry_records(self) -> Tuple[SourceRecord, ...]:
        """The registry records of the sources with a file in this release, as the caller's registry held them when the release was read (performance/1.12 Ruling 1.7 item 4: reference data
        is read at computation time and pinned by digest). The projection does not store the registry, so `read_release` REQUIRES one; fails closed like `InMemoryMarketData`."""
        return self._mem.source_registry_records()

    # -- what the projection holds, beyond the port ----------------------------------------------------------
    @property
    def release(self) -> MarketDataRelease:
        return self._release

    @property
    def contains_synthetic(self) -> bool:
        return self._contents.contains_synthetic

    def calendars(self) -> CalendarSet:
        """The calendar files of the market-data version M (Ruling 5.3), as projected."""
        return self._calendars

    def export(self) -> StoreContents:
        return self._contents

    def projection_digest(self) -> str:
        return projection_digest(self._release, self._contents, self._calendars)

    # -- MarketDataPort ---------------------------------------------------------------------------------------
    def release_id(self) -> str:
        return self._mem.release_id()

    def quotes(self, listing_id: uuid.UUID, start: datetime.date, end: datetime.date) -> QuoteSeries:
        return self._mem.quotes(listing_id, start, end)

    def quote_on(self, listing_id: uuid.UUID, as_of: datetime.date, conventions: Any) -> QuoteLookup:
        return self._mem.quote_on(listing_id, as_of, conventions)

    def fx_series(self, base: CurrencyCode, quote: CurrencyCode, start: datetime.date,
                  end: datetime.date) -> FXSeries:
        return self._mem.fx_series(base, quote, start, end)

    def fx_on(self, base: CurrencyCode, quote: CurrencyCode, as_of: datetime.date, conventions: Any) -> FXLookup:
        return self._mem.fx_on(base, quote, as_of, conventions)

    def corporate_actions(self, listing_id: uuid.UUID, start: datetime.date, end: datetime.date) -> ActionSet:
        return self._mem.corporate_actions(listing_id, start, end)

    def benchmark(self, benchmark_id: str, start: datetime.date, end: datetime.date) -> BenchmarkSet:
        return self._mem.benchmark(benchmark_id, start, end)

    def risk_free_on(self, currency: CurrencyCode, as_of: datetime.date, conventions: Any) -> RiskFreeLookup:
        return self._mem.risk_free_on(currency, as_of, conventions)

    def risk_free_series(self, currency: CurrencyCode, start: datetime.date, end: datetime.date) -> RiskFreeSet:
        return self._mem.risk_free_series(currency, start, end)

    # -- verification port (NOT part of MarketDataPort; analytics never reads it) -------------------------------
    def adjusted_series(self, listing_id: uuid.UUID) -> Tuple[c.AdjustedQuote, ...]:
        return self._mem.adjusted_series(listing_id)


def read_release(
    conn: Any, release_id: str, exchange_of: Optional[Callable[[uuid.UUID], Optional[str]]] = None,
    *, registry: SourceRegistry, lease_checked: bool = False,
) -> PostgresMarketData:
    """Load the projection of ONE release and verify it reproduces its recorded digest. The `registry` (the `SOURCES.json` in force now) is REQUIRED: the port reports the full registry records
    of the sources that have a file in the release, so every manifest of a computation over it carries `source_registry_digest` (performance/1.12 Ruling 1.7 item 4). Omitting it is a `TypeError`;
    a source the registry does not know is `UnknownSourceError`, one whose attestation is withdrawn is `SourceTermsNotAttestedError`, and a stored row that disagrees with the registry's record
    is `RegistryDisagreesWithStoredRowsError`: in each case nothing is read. Needs SELECT on the md_*
    tables only. A release the database does not hold is `ReleaseNotFoundError`; a projection whose rows no longer
    reproduce the digest (it cannot happen while the append-only triggers are in place) is
    `ProjectionDigestMismatchError`: fail closed.

    `lease_checked` (F1 R5, PD-0069; keyword-only, default False and then byte-for-byte the read above): every read goes through the table's
    lease-checked function (F1 R3) instead of the table. This is the executor's form: the executor holds EXECUTE on those
    functions and no privilege on any `md_*` table. A call outside an open `EXECUTE_CREATE`/`EXECUTE_REPRODUCE` lease for this release, or at or after
    its `complete_by`, is refused by the function with its own gateway code (a `psycopg.errors.RaiseException`, SQLSTATE P0001) and is NOT translated
    here into a store error, so the caller's tail classifies it as the gateway's typed refusal with whole rollback. Everything else is unchanged: the
    file-list check against the release content, the projection-digest recompute and the registry checks all still run (FF1 FR-L1 (a))."""
    try:
        with conn.transaction():
            schema = pinned_schema(conn)  # C2-5: every read below is schema-qualified; pg_temp is never reached
            qs = _quoted(schema)
            heads = _select(conn, qs, release_id, lease_checked, "release_content, projection_digest, convention_set_id", "md_release", "release_id")
            head = heads[0] if heads else None
            if head is None:
                raise ReleaseNotFoundError(f"market-data release {release_id} is not projected in this database")
            release = MarketDataRelease.from_json(_jsonb(head[0]))
            # C2-6: the stored content must BE the release the row's key names, with the convention set the row says,
            # and the release's file list must be exactly the files the release rows hold: otherwise a manifest would
            # cite a release other than the rows it read (P9)
            listed = tuple(r[0] for r in _select(conn, qs, release_id, lease_checked, "file_sha256", "md_release_file", "ordinal"))
            if release.release_id != release_id or release.convention_set_id != head[2] or listed != release.files:
                raise ReleaseKeyMismatchError(
                    f"the stored content of market-data release {release_id} is not that release (content id "
                    f"{release.release_id}, convention set {release.convention_set_id!r} against {head[2]!r}, "
                    f"{len(listed)} file row(s) against {len(release.files)} named): nothing is read")
            contents, calendars = _read_contents(conn, release_id, schema, lease_checked)
            if lease_checked:
                scope_rows = conn.execute(
                    f"SELECT DISTINCT f.source_id, f.usage_scope FROM {_lease_function(qs, 'md_release_file')} AS rf "
                    f"JOIN {_lease_function(qs, 'md_file')} AS f "
                    "ON f.file_sha256 = rf.file_sha256 WHERE rf.release_id = %s ORDER BY f.source_id, f.usage_scope",
                    (release_id, release_id, release_id)).fetchall()
            else:
                scope_rows = conn.execute(
                    f"SELECT DISTINCT f.source_id, f.usage_scope FROM {qs}.md_release_file rf JOIN {qs}.md_file f ON f.file_sha256 = rf.file_sha256 "
                    "WHERE rf.release_id = %s ORDER BY f.source_id, f.usage_scope", (release_id,)).fetchall()
            source_scopes = tuple((r[0], r[1]) for r in scope_rows)
            source_ids = tuple(sorted({s for s, _scope in source_scopes}))
    except (MarketDataStoreError, LookupError):
        raise
    except Exception as exc:
        typed = translate_error(exc)
        if typed is not None:
            raise typed from exc
        raise
    # performance/1.12 Ruling 1.7 item 4 (CP4-8): the registry is read NOW and pinned by digest, and ONE registry is used consistently. A source with no record is UnknownSourceError; a source whose
    # attestation is withdrawn fails closed (`require_attested`, market-data Ruling 4.7); and every stored row must carry the upstream and independence group of the pinned record, because
    # reconciliation reads the STORED values: a registry that changed since ingest is refused, never silently pinned beside rows that describe the old one.
    records = tuple(registry.require_attested(source_id) for source_id in source_ids)
    by_id = {r.source_id: r for r in records}
    # market-data/1.15 Ruling 7A.3: a terms attestation is necessary, never sufficient. A REAL file of a source whose profile is pending observation (or that Appendix A.5 does not list for its market) is
    # refused here as `ingest_file` refuses it, whatever the registry's terms check says (SOURCE_PENDING_OBSERVATION / SOURCE_NOT_IN_PRIMARY_ORDER).
    # The per-LISTING form (a real reading whose listing is in a market the source does not cover) is applied when the store is rebuilt below, from `exchange_of`:
    # without it the market of a real reading cannot be established, and the rebuild refuses it (LISTING_EXCHANGE_UNKNOWN).
    for source_id, scope in source_scopes:
        gated = SOURCE_PROFILES.get(source_id)
        if scope != "SYNTHETIC_TEST" and gated is not None and gated.gate_refusal is not None:
            code, why = gated.gate_refusal
            raise ProfileNotAdmittedError(f"{code}: release {release_id}: source {source_id!r} is not admitted: {why}", code)
    # CP4-10 (market-data Ruling 4.7, as `ingest_file` does): a file is SYNTHETIC_TEST if and only if its source is synthetic. A registry that calls a source real over synthetic rows, or (the harmful
    # mirror) calls a source synthetic, which `terms_attested` would pass without a terms check, over rows stored as real, is refused. Every file of the release is checked (calendars and benchmarks too).
    for source_id, scope in source_scopes:
        if by_id[source_id].synthetic != (scope == "SYNTHETIC_TEST"):
            raise RegistryDisagreesWithStoredRowsError(
                f"release {release_id}: source {source_id!r} has a stored file with usage scope {scope} but the registry says synthetic={by_id[source_id].synthetic}: "
                "a file is SYNTHETIC_TEST if and only if its source is synthetic (nothing is read)")
    for reading in contents.readings:
        record = by_id.get(reading.source_id)
        lineage = reading.observation.lineage
        # (ingest always sets the lineage's upstream and group from the record, so a stored value that is set must equal it; the reading's own group is what reconciliation reads and must always equal it)
        if (record is None or reading.independence_group != record.independence_group
                or (lineage.independence_group is not None and lineage.independence_group != record.independence_group)
                or (lineage.upstream is not None and lineage.upstream != record.upstream_provider)):
            raise RegistryDisagreesWithStoredRowsError(
                f"release {release_id}: a stored row of source {reading.source_id!r} carries group {reading.independence_group!r}/{lineage.independence_group!r} and upstream {lineage.upstream!r}, "
                f"the registry now says {None if record is None else (record.independence_group, record.upstream_provider)!r}: the rows were ingested under another registry; re-ingest the release")
    store = PostgresMarketData(release, contents, calendars, exchange_of, records)
    if store.projection_digest() != head[1]:
        raise ProjectionDigestMismatchError(
            f"the rows of release {release_id} do not reproduce the recorded projection digest")
    return store


def read_release_files(conn: Any, release_id: str, *, lease_checked: bool = False) -> Tuple[Tuple[str, str, str, Any], ...]:
    """The files of ONE release, one `(file_sha256, source_id, data_kind, manifest)` per file, in `file_sha256` order (O-7: the claim record copies each member's kind and
    the valuing file's manifest, `claim_record.build_claim_record`). `manifest` is the parsed file manifest as the download tool wrote it. `lease_checked` is as in
    `read_release`: the executor's form reads through the two lease-checked functions of `_lease_function`, which refuse without an open `EXECUTE_CREATE`/`EXECUTE_REPRODUCE` lease for
    the snapshot's release; a refusal is the function's own `RaiseException` and is NOT translated here. A release the database does not hold has no file row and
    gives an empty tuple (the caller's own release read has refused it before)."""
    qs = _quoted(pinned_schema(conn))
    if lease_checked:
        rows = conn.execute(
            f"SELECT f.file_sha256, f.source_id, f.data_kind, f.manifest FROM {_lease_function(qs, 'md_release_file')} AS rf "
            f"JOIN {_lease_function(qs, 'md_file')} AS f ON f.file_sha256 = rf.file_sha256 WHERE rf.release_id = %s ORDER BY f.file_sha256",
            (release_id, release_id, release_id)).fetchall()
    else:
        rows = conn.execute(
            f"SELECT f.file_sha256, f.source_id, f.data_kind, f.manifest FROM {qs}.md_release_file rf JOIN {qs}.md_file f ON f.file_sha256 = rf.file_sha256 "
            "WHERE rf.release_id = %s ORDER BY f.file_sha256", (release_id,)).fetchall()
    return tuple((r[0], r[1], r[2], r[3]) for r in rows)
