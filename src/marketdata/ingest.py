"""Ingestion: verified file -> adapter -> resolution -> normalized readings (Tech Plan §15.3,
§15.6). A pure pipeline over bytes the file store already verified.

Rules enforced here, each tested:
- the adapter's source and data kind must match the manifest; an adapter may fill only the
  tuple of its own kind; every observation must carry COMPLETE lineage that names this
  file and this adapter (an adapter that cannot is a bug and raises);
- nothing is dropped silently: adapter issues, unresolved identities and currency
  mismatches are all reported;
- identity is never created here; a row whose identity is not RESOLVED is not loaded and
  is reported as a `ResolutionException`;
- a quote's declared currency must equal the listing's trading currency, or the row is
  reported and not loaded (market-data/1.2 Ruling 4.1a);
- a file from a source with no recorded human terms-of-use check is refused BEFORE its payload is
  read or parsed (Ruling 4.7: refused files are never readings; synthetic sources are exempt);
- a REAL observation bound to a listing needs a source whose profile covers, admits and lists (Appendix A.5) the
  LISTING'S market, whatever source id the file carries (market-data/1.15 Ruling 7A.3, `profiles.require_listing_market`):
  the file is refused, not the row, as for a source that is not admitted.

market-data/1.2 file-level checks over the whole market-data version, run after every file is
loaded so they are deterministic whatever order the release lists the files in:
- calendars (Ruling 5.3): one version per `calendar_id`; the `CalendarSet` goes into the result;
- Test V0 (calendar alignment): a quote series whose dates fall on non-sessions of the governing
  calendar is CONTRADICTED and NOT admitted (treated as absent); an uncovered part is UNVERIFIABLE;
- Test V2 (affine fit) over each adjusted series and the RAW reference rows of the same listing and
  upstream; the bound comes from the profiles (V2 (a')); the result sets the label's method and the
  lineage's label status. No corroborated corporate action is in M, so the event check is UNVERIFIABLE;
- every RAW quote series' label status is UNVERIFIABLE (Test V1 needs a decisive corroborated split);
- `observed_at` of a quote on a listed session is its scheduled close instant (Ruling 2.2 item 3);
- Ruling 1.1a: a re-server's declared upstream carries provenance UNCONFIRMED until an exact comparison
  with the publisher's own file confirms it (CONFIRMED) or refutes it (REFUTED).
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from marketdata.adapters.base import (
    AdapterIssue,
    AdapterOutput,
    AdapterRegistry,
    ContradictedSeries,
    DatedStatement,
    IssueCode,
    SourceAdapter,
)
from marketdata.calendars import CalendarSet
from marketdata.canonical import canonical_json, observation_obj, sha256_hex
from marketdata.precision import PriceValue, resolve_close
from marketdata.profiles import (
    ECB_CALENDAR_ID,
    ProfileNotAdmittedError,
    SOURCES as PROFILES,
    field_profile_of,
    market_of_mic,
    require_admitted,
    require_listing_market,
    security_class_for,
)
from marketdata.contracts import (
    AdjustedQuote,
    AdjustmentMethod,
    AdjustmentStatus,
    CalendarDays,
    CorporateActionObservation,
    ExternalIdentifiers,
    FXObservation,
    IdentityAssertion,
    InstrumentResolution,
    LabelStatus,
    Lineage,
    QuoteObservation,
    ResolutionStatus,
    RevisionPolicy,
    SourceReading,
    UnresolvedQuote,
    UsageScope,
)
from marketdata.files import FileStore, VerifiedFile
from marketdata.manifest import (
    DataKind,
    FileManifest,
    MarketDataRelease,
    SourceRecord,
    SourceRegistry,
    SourceTermsNotAttestedError,
    VENDOR_ADJUSTED,
)
from marketdata.segments import (
    FileSegment,
    SegmentCalendarMismatchError,
    admit_segments,
    declared_coverage,
)
from marketdata.port import InstrumentResolverPort
from marketdata.store import BenchmarkEntry, FXFileWindow, InMemoryMarketData, RiskFreeEntry, SeriesExclusion
from marketdata.verification import (
    PriceRow,
    V2Result,
    apply_v2,
    check_provenance,
    verify_adjustment_v2,
    verify_v0,
)

REFERENCE_DECLARED = "TRANSPORT_CHECK_FOR_ECB"  # profile role of a re-server whose upstream is declared
REFERENCE_DIRECT = "PREFERRED_FX"  # profile role of the publisher's own file


class IngestError(ValueError):
    """An adapter or file broke a rule the pipeline relies on (not a data problem)."""


@dataclass(frozen=True)
class ResolutionException:
    identifiers: ExternalIdentifiers
    status: ResolutionStatus
    candidates: Tuple[str, ...]
    row_count: int
    first_row_ref: str


@dataclass(frozen=True)
class FileSummary:
    file_sha256: str
    adapter_id: str
    adapter_version: str
    observation_count: int
    issue_count: int
    exception_count: int
    normalized_digest: str
    reference_count: int = 0  # verification-only RAW reference rows (not counted in observation_count)


@dataclass(frozen=True)
class IdentityEvidence:
    """An identifier source's assertion, matched against EXISTING identity only. Nothing is
    created from it; `resolution` says what it matched (RESOLVED, UNRESOLVED, AMBIGUOUS or
    CONFLICT), and a human decides the rest."""

    assertion: IdentityAssertion
    resolution: InstrumentResolution


@dataclass(frozen=True)
class FileIngest:
    readings: Tuple[SourceReading, ...]
    benchmarks: Tuple[BenchmarkEntry, ...]
    issues: Tuple[AdapterIssue, ...]
    exceptions: Tuple[ResolutionException, ...]
    summary: FileSummary
    identity_evidence: Tuple[IdentityEvidence, ...] = ()
    adjusted: Tuple[AdjustedQuote, ...] = ()
    reference: Tuple[AdjustedQuote, ...] = ()
    calendars: Tuple[CalendarDays, ...] = ()
    risk_free: Tuple[RiskFreeEntry, ...] = ()
    #: series the FILE contradicts by stating a date twice (market-data/1.16 Tests V0 and V0-FX): no reading, the file stays in M
    exclusions: Tuple[SeriesExclusion, ...] = ()


@dataclass(frozen=True)
class LabelResult:
    """The outcome of a file-level verification test on one series (market-data/1.2 section 9A #6):
    stored as series lineage, re-runnable and deterministic."""

    test: str  # "V0" | "V2"
    listing_id: Optional[uuid.UUID]
    file_sha256: str
    status: LabelStatus
    method: Optional[str]
    reason: str
    admitted: bool = True  # False: a CONTRADICTED series is not admitted (Ruling 3.1, Consequences)


def _check_kind(adapter: SourceAdapter, out: AdapterOutput) -> None:
    fields = {
        DataKind.QUOTE: "quotes", DataKind.FX: "fx",
        DataKind.CORPORATE_ACTION: "actions", DataKind.BENCHMARK: "benchmarks",
        DataKind.IDENTITY: "identities", DataKind.CALENDAR: "calendars", DataKind.RISK_FREE: "risk_free",
    }
    own = fields.get(adapter.data_kind)
    if own is None:
        raise IngestError(f"adapter kind {adapter.data_kind} is not ingestible")
    allowed = {own, "adjusted", "reference"} if adapter.data_kind is DataKind.QUOTE else {own}
    if adapter.data_kind is DataKind.FX:
        allowed = allowed | {"contradicted"}  # Test V0-FX (market-data/1.16): an FX file may name the currency series it contradicts
    for name in list(fields.values()) + ["adjusted", "reference", "contradicted"]:
        if name not in allowed and getattr(out, name):
            raise IngestError(f"adapter {adapter.adapter_id} filled {name!r}, not its kind {own!r}")
    if out.dated_statements is not None and adapter.data_kind is not DataKind.QUOTE:
        raise IngestError(f"adapter {adapter.adapter_id} listed dated statements, which only a price file has")


def _check_lineage(adapter: SourceAdapter, verified: VerifiedFile, obs: object) -> None:
    lineage = getattr(obs, "lineage")
    if not lineage.is_complete:
        raise IngestError(f"{adapter.adapter_id} emitted an observation with incomplete lineage")
    if (
        lineage.file_sha256 != verified.manifest.file_sha256
        or lineage.adapter_id != adapter.adapter_id
        or lineage.adapter_version != adapter.adapter_version
        or lineage.source_id != verified.manifest.source_id
    ):
        raise IngestError(f"{adapter.adapter_id} emitted lineage that does not name this file/adapter")
    if lineage.usage_scope is not verified.manifest.usage_scope:
        raise IngestError(f"{adapter.adapter_id} changed the usage scope")


def _enrich(obs, source: SourceRecord):  # type: ignore[no-untyped-def]
    """Set what only the source registry (and the profiles) know: the upstream and independence group;
    for a re-server whose upstream is only DECLARED, `provenance: UNCONFIRMED` (Ruling 1.1a); and, for a
    RAW quote, the label status UNVERIFIABLE (Test V1 needs a decisive corroborated split, none in M)."""
    changes: Dict[str, object] = {"upstream": source.upstream_provider,
                                  "independence_group": source.independence_group}
    profile = PROFILES.get(source.source_id)
    if profile is not None and profile.role == REFERENCE_DECLARED:
        changes["provenance"] = "UNCONFIRMED"
    if (isinstance(obs, UnresolvedQuote) and obs.lineage.adjustment_status is AdjustmentStatus.RAW
            and obs.lineage.label_status is None):
        changes["label_status"] = LabelStatus.UNVERIFIABLE
    return dataclasses.replace(obs, lineage=dataclasses.replace(obs.lineage, **changes))


def _cn_class(resolver: InstrumentResolverPort, listing_id: uuid.UUID) -> Tuple[bool, Optional[str]]:
    """(is a mainland listing, its security class or None). market-data/1.4 Appendix A.1 (C2-10): the class comes from
    (MIC, `Instrument.security_type`, `trading_currency`) of the identity record; None = SECURITY_CLASS_UNRESOLVED."""
    mic = resolver.exchange_mic(listing_id)
    if market_of_mic(mic) != "CN":
        return False, None
    currency = resolver.trading_currency(listing_id)
    return True, security_class_for(mic, resolver.security_type(listing_id), None if currency is None else currency.code)


def _classify_close(
    lineage: Lineage, value: Decimal, resolver: InstrumentResolverPort, listing_id: uuid.UUID,
) -> Optional[Tuple[str, PriceValue]]:
    """market-data/1.2 section 9A #2, 1.4 A.1: for a RAW close of a MAINLAND listing whose security class is KNOWN from
    the identity record, re-apply the Ruling 2.4 grid with that class to the close's own verbatim text and profile.
    Returns (class, result), or None when nothing changes: another market, an unresolved class (the adapter's strict
    result stands and says SECURITY_CLASS_UNRESOLVED), or a close with no text or profile. The class never comes
    from the file or from a request parameter."""
    if lineage.adjustment_status is not AdjustmentStatus.RAW or lineage.source_value_text is None:
        return None
    mainland, cls = _cn_class(resolver, listing_id)
    if not mainland:
        return None
    field = field_profile_of(lineage.precision_profile_id)
    if cls is None or field is None:
        return None
    result = resolve_close(lineage.source_value_text, field, "CN", cls)
    if result.value != value:
        raise IngestError("the re-read close differs from the adapter's: the profile and the text disagree")
    return cls, result


def ingest_file(
    verified: VerifiedFile,
    adapter: SourceAdapter,
    resolver: InstrumentResolverPort,
    source: SourceRecord,
) -> FileIngest:
    manifest = verified.manifest
    if adapter.source_id != manifest.source_id or adapter.data_kind is not manifest.data_kind:
        raise IngestError("adapter does not match the file's source and data kind")
    if source.source_id != manifest.source_id:
        raise IngestError("source record does not match the file's source")
    if source.synthetic != (manifest.usage_scope is UsageScope.SYNTHETIC_TEST):
        raise IngestError("a file is SYNTHETIC_TEST if and only if its source is synthetic")
    # C2-13 (defence in depth): the terms gate is enforced HERE too, before the payload is parsed, not only by the
    # build path. A source with no recorded human terms-of-use check (or a negative one) is refused with the same typed
    # error, whoever hands ingest_file its `SourceRecord`. Synthetic sources are exempt (`terms_attested`).
    if not source.terms_attested:
        raise SourceTermsNotAttestedError(
            f"SOURCE_TERMS_NOT_ATTESTED: no human terms-of-use check permitting internal development use is "
            f"recorded for source {source.source_id!r}: its file is refused before its payload is parsed")

    if not source.synthetic and manifest.data_kind in (DataKind.QUOTE, DataKind.FX, DataKind.RISK_FREE):
        # TO_OBSERVE, MEMORY, refused or missing profile: fail closed. CP4b-2: a REAL risk-free source needs a precision profile too (risk/1.0 Ruling 4.6 item 3), so none is
        # admitted until the Quant has profiled its first real file (as for the ECB fixings, MD-OI-12); a synthetic source needs none.
        require_admitted(manifest.source_id)
    elif not source.synthetic:
        # CP2 final round: a REFUSED profile blocks EVERY kind of file (its own text says "no file from it is ever a
        # reading"): a corporate-action, identity, benchmark or calendar file from a refused source is refused too.
        # (Such kinds have no precision profile of their own, so only `refused` is tested, never MEMORY or absence.)
        profile = PROFILES.get(manifest.source_id)
        if profile is not None and profile.refused:
            raise ProfileNotAdmittedError(f"source {manifest.source_id!r} is not admitted: {profile.not_admitted_reason}")
        # market-data/1.15 Ruling 7A.3: a source pending observation supplies no file of ANY kind as a real one, whatever its
        # terms check says (terms attestation is necessary, not sufficient).
        if profile is not None and profile.gate_refusal is not None:
            code, why = profile.gate_refusal
            raise ProfileNotAdmittedError(f"{code}: source {manifest.source_id!r} is not admitted: {why}", code)
    out = adapter.translate(manifest, verified.payload)
    _check_kind(adapter, out)
    issues: List[AdapterIssue] = list(out.issues)
    readings: List[SourceReading] = []
    benchmarks: List[BenchmarkEntry] = []
    adjusted: List[AdjustedQuote] = []
    reference: List[AdjustedQuote] = []
    calendars: List[CalendarDays] = []
    risk_free: List[RiskFreeEntry] = []
    pending: Dict[Tuple[ExternalIdentifiers, ResolutionStatus, Tuple[str, ...]], List[str]] = {}
    class_flagged: Set[uuid.UUID] = set()

    def reading(obs: object) -> SourceReading:
        return SourceReading(manifest.source_id, source.independence_group,
                             manifest.file_sha256, obs)

    market_cleared: Set[uuid.UUID] = set()

    def bind(listing_id: uuid.UUID) -> None:
        """market-data/1.15 Ruling 7A.3 item 1 and Appendix A.5 are per MARKET: the gate above keys on the file's source id, but a
        real file can carry a symbol that the identity table maps to a listing of ANOTHER market (a vendor-id row entered for
        it). Where a real observation is bound to a listing, the LISTING's market must be one the source's profile covers,
        admits and lists in its primary order. With the CN order empty, no real file supplies a reading for a CN listing, under
        any source id. The whole file is refused, as for a source that is not admitted. Synthetic sources are exempt."""
        if source.synthetic or listing_id in market_cleared:
            return
        require_listing_market(manifest.source_id, listing_id, resolver.exchange_mic(listing_id))
        market_cleared.add(listing_id)

    exclusions: List[SeriesExclusion] = []
    # Test V0 (market-data/1.16, section 11 item 25), judged HERE and nowhere else, so that every route is covered by construction: a price file states a close per
    # (listing, session date), whatever its layout, its symbols or its aliases (Addendum A.1, A.4). The statements are resolved first, then counted per
    # (listing, file, parsed date); two make the series (listing, file) CONTRADICTED. It supplies no reading (the listing's quotes, adjusted rows and reference
    # rows of THIS file are dropped below), the file stays in M, and the failure is a `SeriesExclusion`. A statement that does not resolve belongs to no
    # series. An adapter that lists no statements is judged on the quotes and adjusted rows it emitted.
    duplicated: Set[uuid.UUID] = set()
    if adapter.data_kind is DataKind.QUOTE:
        statements = out.dated_statements
        if statements is None:
            statements = tuple(DatedStatement(r.identifiers, r.value_date, r.lineage.source_record_ref or "?") for r in tuple(out.quotes) + tuple(out.adjusted))
        stated: Dict[Tuple[uuid.UUID, datetime.date], List[str]] = {}
        for st in statements:
            res = resolver.resolve(st.identifiers, st.value_date)
            if res.is_resolved:
                assert res.listing_id is not None
                stated.setdefault((res.listing_id, st.value_date), []).append(st.ref)
        twice: Dict[uuid.UUID, List[Tuple[datetime.date, List[str]]]] = {}
        for (lid, day), refs in sorted(stated.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
            if len(refs) > 1:
                twice.setdefault(lid, []).append((day, refs))
        for lid, found in twice.items():
            bind(lid)  # a contradicted series is still a series of the source: the listing's market is judged as for a reading
            duplicated.add(lid)
            dates = ", ".join(day.isoformat() for day, _ in found)
            for day, refs in found:
                issues.append(AdapterIssue(refs[0], IssueCode.DUPLICATE_SESSION_DATE,
                                           f"two rows for one date ({', '.join(refs)}): the series is contradicted (Test V0), it supplies no reading and the file stays in M"))
            exclusions.append(SeriesExclusion(lid, manifest.file_sha256, "V0",
                                              f"{IssueCode.DUPLICATE_SESSION_DATE.value}: two rows for one session date: {dates}"))

    for q in out.quotes:
        _check_lineage(adapter, verified, q)
        q = _enrich(q, source)
        res = resolver.resolve(q.identifiers, q.value_date)
        if not res.is_resolved:
            key = (q.identifiers, res.status, tuple(str(c) for c in res.candidates))
            pending.setdefault(key, []).append(q.lineage.source_record_ref or "?")
            continue
        assert res.listing_id is not None
        if res.listing_id in duplicated:
            continue  # the series is CONTRADICTED: no reading of it
        bind(res.listing_id)
        native = resolver.trading_currency(res.listing_id)
        if native is not None and native != q.currency:
            # Ruling 4.1a item 1: a currency other than the listing's trading currency is refused at
            # ingest, as a data error (never a comparison outcome)
            issues.append(AdapterIssue(
                q.lineage.source_record_ref or "?", IssueCode.TRADING_CURRENCY_MISMATCH,
                f"declared {q.currency.code}, listing trades in {native.code}"))
            continue
        recovered, bound = q.recovered, q.precision_bound
        mainland, known_class = _cn_class(resolver, res.listing_id)
        if mainland and known_class is None and res.listing_id not in class_flagged:
            class_flagged.add(res.listing_id)  # once per listing and file: the strict grid applies (Appendix A.1, 1.4)
            issues.append(AdapterIssue(
                q.lineage.source_record_ref or "?", IssueCode.SECURITY_CLASS_UNRESOLVED,
                "no security class for this (MIC, SecurityType, trading currency): strict 2-decimal grid applied "
                "(Appendix A.1)"))
        classed = _classify_close(q.lineage, q.price, resolver, res.listing_id)
        if classed is not None:
            cls, pv = classed
            recovered, bound = pv.recovered, pv.bound
            ref = q.lineage.source_record_ref or "?"
            # the adapter judged this close with the strict class-unknown grid and may have said so: the listing's
            # identity record has now decided the class, so the adapter's note is replaced by the true one
            issues = [i for i in issues if not (i.row_ref == ref and i.code is IssueCode.PRICE_NOT_RECOVERED)]
            if not pv.recovered:
                issues.append(AdapterIssue(ref, IssueCode.PRICE_NOT_RECOVERED,
                                           f"kept, corroborates only: {pv.note} [security class {cls}]"))
        readings.append(reading(QuoteObservation(
            res.listing_id, q.value_date, q.price, q.currency, q.timing, q.lineage, q.observed_at,
            q.volume, q.price_kind, recovered, bound)))
    # Test V0-FX (market-data/1.16, item 34): the adapter output no rate of the file and names every currency series it excludes; a stated fixing is a
    # (date, currency), whatever the layout. An adapter that names nothing is judged on the observations it emitted: a (pair, date) emitted twice excludes
    # every currency series of the file, whole, and none of its rates is kept.
    fx_observations = tuple(out.fx)
    contradicted = tuple(out.contradicted)
    if adapter.data_kind is DataKind.FX and not contradicted:
        seen_fx: Dict[Tuple[str, str, datetime.date], int] = {}
        for fx_obs in fx_observations:
            key_fx = (fx_obs.base_currency.code, fx_obs.quote_currency.code, fx_obs.value_date)
            seen_fx[key_fx] = seen_fx.get(key_fx, 0) + 1
        repeated_fx = tuple(sorted({d for (_, _, d), n in seen_fx.items() if n > 1}))
        if repeated_fx:
            issues += [AdapterIssue(d.isoformat(), IssueCode.DUPLICATE_SESSION_DATE,
                                    "a fixing stated twice: every currency series of the file is excluded (Test V0-FX)") for d in repeated_fx]
            contradicted = tuple(ContradictedSeries("V0_FX_DUPLICATE_DATE", "V0_FX_DUPLICATE_DATE", repeated_fx, currency=code)
                                 for code in sorted({fx_obs.quote_currency.code for fx_obs in fx_observations}))
            fx_observations = ()
    for cs in contradicted:
        dates = ", ".join(d.isoformat() for d in cs.dates)
        named = f" (stated twice: {', '.join(cs.names)})" if cs.names else ""
        exclusions.append(SeriesExclusion(None, manifest.file_sha256, cs.test,
                                          f"{cs.cause}: a fixing stated twice in the file: {dates}{named}", cs.currency))
    for target, rows in ((adjusted, out.adjusted), (reference, out.reference)):
        for aq in rows:  # verification-only: never a reading, never a price
            _check_lineage(adapter, verified, aq)
            aq = _enrich(aq, source)
            res = resolver.resolve(aq.identifiers, aq.value_date)
            # reference rows repeat rows the file's quotes already report: an unresolved identity or a
            # wrong currency is reported once, for the quote, never twice
            report = target is adjusted
            if not res.is_resolved:
                if report:
                    key = (aq.identifiers, res.status, tuple(str(c) for c in res.candidates))
                    pending.setdefault(key, []).append(aq.lineage.source_record_ref or "?")
                continue
            assert res.listing_id is not None
            if res.listing_id in duplicated:
                continue  # the series is CONTRADICTED (Test V0): its verification rows are dropped with it
            bind(res.listing_id)  # verification-only rows are a reading of the source too ("not even as corroboration", Ruling 7A.3)
            native = resolver.trading_currency(res.listing_id)
            if native is not None and native != aq.currency:
                if report:
                    issues.append(AdapterIssue(aq.lineage.source_record_ref or "?",
                                               IssueCode.TRADING_CURRENCY_MISMATCH,
                                               f"declared {aq.currency.code}, listing trades in {native.code}"))
                continue
            bound = aq.precision_bound
            if target is reference:  # a RAW reference close follows the same class decision as its quote
                classed = _classify_close(aq.lineage, aq.close, resolver, res.listing_id)
                if classed is not None:
                    bound = classed[1].bound
            target.append(AdjustedQuote(res.listing_id, aq.value_date, aq.open, aq.high, aq.low, aq.close,
                                        aq.currency, aq.label, aq.timing, aq.lineage, bound,
                                        aq.field_bounds))
    for a in out.actions:
        _check_lineage(adapter, verified, a)
        a = _enrich(a, source)
        res = resolver.resolve(a.identifiers, a.effective_date)
        if not res.is_resolved:
            key = (a.identifiers, res.status, tuple(str(c) for c in res.candidates))
            pending.setdefault(key, []).append(a.lineage.source_record_ref or "?")
            continue
        assert res.listing_id is not None
        bind(res.listing_id)
        readings.append(reading(CorporateActionObservation(
            res.listing_id, a.action_type, a.effective_date, a.timing, a.lineage,
            a.split_ratio, a.amount_per_unit, a.pay_date, a.record_date, a.paid_currency,
            a.issuer_fx_rate, a.old_ticker, a.new_ticker, a.unsupported_label, a.paid_amount)))
    for f in fx_observations:
        _check_lineage(adapter, verified, f)
        readings.append(reading(_enrich(f, source)))
    for b in out.benchmarks:
        _check_lineage(adapter, verified, b)
        b = _enrich(b, source)
        benchmarks.append(BenchmarkEntry(manifest.source_id, source.independence_group,
                                         manifest.file_sha256, b))
    for rf in out.risk_free:
        _check_lineage(adapter, verified, rf)
        rf = _enrich(rf, source)
        risk_free.append(RiskFreeEntry(manifest.source_id, source.independence_group, manifest.file_sha256, rf))
    for cal in out.calendars:
        _check_lineage(adapter, verified, cal)
        calendars.append(dataclasses.replace(cal, lineage=dataclasses.replace(
            cal.lineage, upstream=source.upstream_provider, independence_group=source.independence_group)))

    evidence: List[IdentityEvidence] = []
    for ident in out.identities:
        _check_lineage(adapter, verified, ident)
        ident = _enrich(ident, source)
        evidence.append(IdentityEvidence(ident, resolver.resolve(
            ExternalIdentifiers(figi=ident.figi, ticker=ident.ticker), None)))

    exceptions = tuple(
        ResolutionException(ids, status, cands, len(rows), rows[0])
        for (ids, status, cands), rows in sorted(
            pending.items(), key=lambda kv: (kv[0][1].value, repr(kv[0][0]), kv[0][2]))
    )
    for e in exceptions:
        issues.append(AdapterIssue(e.first_row_ref, IssueCode.UNRESOLVED_IDENTITY,
                                   f"{e.status.value} ({e.row_count} row(s))"))
    digest = sha256_hex(canonical_json(
        [observation_obj(r.observation) for r in readings]
        + [observation_obj(b.series) for b in benchmarks]
        + [observation_obj(e.assertion) for e in evidence]
        + [observation_obj(a) for a in adjusted]
        + [observation_obj(c) for c in calendars]
        + [observation_obj(r.series) for r in risk_free]
    ).encode("utf-8"))
    summary = FileSummary(manifest.file_sha256, adapter.adapter_id, adapter.adapter_version,
                          len(readings) + len(benchmarks) + len(evidence) + len(adjusted) + len(calendars) + len(risk_free),
                          len(issues), len(exceptions), digest, reference_count=len(reference))
    return FileIngest(tuple(readings), tuple(benchmarks), tuple(issues), exceptions, summary,
                      tuple(evidence), tuple(adjusted), tuple(reference), tuple(calendars), tuple(risk_free), tuple(exclusions))


@dataclass(frozen=True)
class BuildResult:
    store: InMemoryMarketData
    summaries: Tuple[FileSummary, ...]
    issues: Tuple[Tuple[str, AdapterIssue], ...]  # (file_sha256, issue)
    exceptions: Tuple[Tuple[str, ResolutionException], ...]
    identity_evidence: Tuple[Tuple[str, IdentityEvidence], ...] = ()
    calendars: CalendarSet = CalendarSet()
    label_results: Tuple[LabelResult, ...] = ()
    manifests: Tuple[FileManifest, ...] = ()  # the files of M, in the release's order (for a projection)


class ReleaseFileMissingError(LookupError):
    pass


def _series_key(reading: SourceReading) -> Tuple[str, ...]:
    obs = reading.observation
    lineage = obs.lineage  # type: ignore[attr-defined]
    if isinstance(obs, CorporateActionObservation):
        subject = f"{obs.listing_id}/{obs.action_type.value}"
    elif isinstance(obs, QuoteObservation):
        subject = str(obs.listing_id)
    else:
        subject = f"{obs.base_currency.code}/{obs.quote_currency.code}"  # type: ignore[attr-defined]
    return (reading.source_id, type(obs).__name__, subject, lineage.adjustment_status.value, _key_anchor(lineage))


def _key_anchor(lineage: Lineage) -> str:
    """The anchor as a KEY field: only a vendor-adjusted series carries one (Ruling 2.3). On any other series a declared anchor is a difference of identity that `admit_segments` refuses; it is never a
    second series (Ruling 0.1 (1.12): no vintage label in a key)."""
    return (lineage.adjustment_anchor or "") if lineage.adjustment_status in VENDOR_ADJUSTED else ""


def _identity(pairs: Dict[str, object], lineage: Lineage) -> Tuple[Tuple[str, object], ...]:
    """The declared identity of a file's contribution to a series: the kind's static fields, the series key's status and anchor, and the synthetic flag (Ruling 0.1 (1.12) item 2)."""
    out = dict(pairs)
    out.update(adjustment_status=lineage.adjustment_status.value, anchor=lineage.adjustment_anchor or "", synthetic=bool(lineage.is_synthetic))
    return tuple(sorted(out.items()))


def _static(series: object) -> Dict[str, object]:
    """The declared static fields of a benchmark or risk-free series: every field except the points, the lineage and the timing."""
    return {f.name: getattr(series, f.name) for f in dataclasses.fields(series) if f.name not in ("points", "lineage", "timing")}  # type: ignore[arg-type]


def _require_disjoint_segments(readings: List[SourceReading], benchmarks: List[BenchmarkEntry], adjusted: Optional[List[AdjustedQuote]], risk_free: Optional[List[RiskFreeEntry]],
                               calendars: CalendarSet, manifests: Dict[str, FileManifest], resolver: InstrumentResolverPort,
                               catalog_calendars: Optional[Mapping[str, str]] = None) -> Dict[Tuple[str, ...], Tuple[FileSegment, ...]]:
    """Ruling 0.1 (1.12) on the loaded data, ONCE for every kind (prices, FX, benchmarks, risk-free rates; corporate actions and adjusted quotes are never segmented): per series key, the files are admitted as
    segments only when their declared COVERAGE intervals are disjoint, they share one identity, and the series is vintage-stable. Fails closed with a `SegmentError` (a `TwoVintagesError`); never picks a vintage,
    and refuses an overlap even when the values agree. Returns the admitted segments per series key (the files of every series, one for most)."""
    held: Dict[Tuple[Tuple[str, ...], str], List[datetime.date]] = {}
    meta: Dict[Tuple[Tuple[str, ...], str], Tuple[Optional[CalendarDays], Tuple[Tuple[str, object], ...], bool]] = {}

    def add(key: Tuple[str, ...], sha: str, days: Iterable[datetime.date], calendar: Optional[CalendarDays], identity: Tuple[Tuple[str, object], ...], segmentable: bool) -> None:
        held.setdefault((key, sha), []).extend(days)
        meta.setdefault((key, sha), (calendar, identity, segmentable))

    for r in readings:
        obs, lineage = r.observation, r.observation.lineage  # type: ignore[attr-defined]
        key = _series_key(r)
        if (key, r.file_sha256) in meta:  # the file's facts were taken from its first reading of the series; only the date is new
            day = getattr(obs, "value_date", None)
            if day is not None:
                held[(key, r.file_sha256)].append(day)
            continue
        if isinstance(obs, QuoteObservation):
            calendar, _ = calendars.governing(resolver.exchange_mic(obs.listing_id))
            identity = _identity(dict(currency=obs.currency.code, market=lineage.market, adjustment_method=lineage.adjustment_method, upstream=lineage.upstream, independence_group=r.independence_group,
                                      price_kind=obs.price_kind.value, precision_profile_id=lineage.precision_profile_id), lineage)
            add(key, r.file_sha256, [obs.value_date], calendar, identity, lineage.adjustment_status is AdjustmentStatus.RAW)
        elif isinstance(obs, FXObservation):
            calendar, _ = calendars.governing(ECB_CALENDAR_ID)
            identity = _identity(dict(rate_basis=obs.rate_basis, upstream=lineage.upstream, independence_group=r.independence_group), lineage)
            add(key, r.file_sha256, [obs.value_date], calendar, identity, lineage.adjustment_status not in VENDOR_ADJUSTED)
        else:  # corporate actions: not in the list of vintage-stable series, so several files of one key are refused
            add(key, r.file_sha256, [obs.value_date] if hasattr(obs, "value_date") else [], None, _identity({}, lineage), False)
    for rf in risk_free or []:
        lineage = rf.series.lineage
        key = (rf.source_id, "RiskFreeSeries", rf.series.series_id, lineage.adjustment_status.value, _key_anchor(lineage))
        stable = lineage.adjustment_status not in VENDOR_ADJUSTED and rf.series.revision_policy is RevisionPolicy.NOT_REVISED  # a publisher that revises (or does not say) makes each retrieval a vintage
        add(key, rf.file_sha256, [p.value_date for p in rf.series.points], calendars.by_id(rf.series.calendar_id), _identity(_static(rf.series), lineage), stable)
    for b in benchmarks:
        lineage = b.series.lineage
        key = (b.source_id, "BenchmarkSeries", b.series.benchmark_id, lineage.adjustment_status.value, _key_anchor(lineage))
        manifest = manifests.get(b.file_sha256)
        calendar_id = None if manifest is None else dict(manifest.request).get("calendar")  # a benchmark's calendar is the catalog's; a file that has several segments DECLARES it in its request
        add(key, b.file_sha256, [p.value_date for p in b.series.points], calendars.by_id(calendar_id), _identity(_static(b.series), lineage), lineage.adjustment_status not in VENDOR_ADJUSTED)
    for a in adjusted or []:
        key = (a.lineage.source_id or "", "AdjustedQuote", str(a.listing_id), a.label.adjustment_status.value, a.lineage.adjustment_anchor or "")
        add(key, a.lineage.file_sha256 or "", [a.value_date], None, _identity({"currency": a.currency.code}, a.lineage), False)  # a vendor-adjusted series is never segmented
    by_key: Dict[Tuple[str, ...], List[FileSegment]] = {}
    files_of_key: Dict[Tuple[str, ...], int] = {}
    for key, _sha in held:
        files_of_key[key] = files_of_key.get(key, 0) + 1
    for (key, sha), days in sorted(held.items()):
        calendar, identity, segmentable = meta[(key, sha)]
        manifest = manifests.get(sha)
        if manifest is None:  # no manifest to state a retrieval time or coverage from (a hand-built reading): one file is admitted as before, several cannot be shown disjoint
            by_key.setdefault(key, []).append(FileSegment(sha, datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), None, identity, segmentable))
            continue
        coverage = declared_coverage(manifest, calendar, days)
        if files_of_key[key] > 1 and key[1] == "BenchmarkSeries" and catalog_calendars and key[2] in catalog_calendars:
            declared = dict(manifest.request).get("calendar")  # CP4M-10 point 3: the calendar a segmented benchmark file DECLARES is the catalog entry's, or the coverage it bounds is not the index's
            if declared != catalog_calendars[key[2]]:
                raise SegmentCalendarMismatchError(key, f"file {sha[:12]} declares calendar {declared!r}, the catalog entry of {key[2]!r} names {catalog_calendars[key[2]]!r}")
        outside = () if coverage is None else tuple(sorted(d for d in days if not coverage[0] <= d <= coverage[1]))  # CP4M-10 (Ruling 0.1 (1.13) 1(c)): judged by `admit_segments`, after the coverage is known
        by_key.setdefault(key, []).append(FileSegment(sha, manifest.retrieval_time, coverage, identity, segmentable, outside))
    return {key: admit_segments(key, files) for key, files in sorted(by_key.items())}


# --- file-level verification over the whole version (after every file is loaded) ----------------

def _price_row(q: AdjustedQuote, bound: Fraction) -> PriceRow:
    return PriceRow(q.value_date, q.open, q.high, q.low, q.close, bound)


def _reference_row(q: AdjustedQuote) -> PriceRow:
    """A RAW reference row with the PER-FIELD bounds V2 (a', 1.3) needs. The adapter supplies them from each
    field's own profile; `precision_bound` is the close's."""
    assert q.field_bounds is not None
    return PriceRow(q.value_date, q.open, q.high, q.low, q.close, Fraction(q.precision_bound),
                    tuple(Fraction(b) for b in q.field_bounds))  # type: ignore[arg-type]


def _run_v2(
    adjusted: List[AdjustedQuote], reference: List[AdjustedQuote],
) -> Tuple[List[AdjustedQuote], List[LabelResult]]:
    """Test V2 per (listing, upstream, currency): the affine fit of each adjusted series against the RAW
    reference rows of the same upstream. The result sets the label's method (and the verified anchor) and
    the lineage's label status; nothing is trusted from the manifest."""
    groups: Dict[Tuple[str, str, str], List[AdjustedQuote]] = {}
    for a in adjusted:
        groups.setdefault((str(a.listing_id), a.lineage.independence_group or "", a.currency.code), []).append(a)
    refs: Dict[Tuple[str, str, str], List[AdjustedQuote]] = {}
    for r in reference:
        refs.setdefault((str(r.listing_id), r.lineage.independence_group or "", r.currency.code), []).append(r)
    out: List[AdjustedQuote] = []
    results: List[LabelResult] = []
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda r: r.value_date)
        sha = rows[0].lineage.file_sha256 or ""
        profile = PROFILES.get(rows[0].lineage.source_id or "")
        result: V2Result
        if profile is None or profile.adjusted_dp is None:
            reason = "the source profile gives no adjusted_dp, so the V2 bound cannot be derived (V2 (a'))"
            result = V2Result(AdjustmentMethod.UNKNOWN, LabelStatus.UNVERIFIABLE, None, (), reason)
        elif key not in refs:
            result = V2Result(AdjustmentMethod.UNKNOWN, LabelStatus.UNVERIFIABLE, None, (),
                              "no RAW reference rows from the same upstream and listing")
        elif any(r.field_bounds is None for r in refs[key]):
            # 1.3: delta_r is per field; a reference row without its open/high/low bounds would be bounded
            # by the close's 0, which understates it. 1.4 (C2-10): a text or float64 field with no declared
            # `delivered_dp` has no bound, and half an ulp of binary64 is NOT a substitute. Fail closed: V2 does not
            # run on this series: method UNKNOWN, label UNVERIFIABLE, cause PROFILE_INCOMPLETE.
            result = V2Result(AdjustmentMethod.UNKNOWN, LabelStatus.UNVERIFIABLE, None, (),
                              "PROFILE_INCOMPLETE: a field V2 reads has no declared delivered_dp, so its reference "
                              "bound cannot be derived (V2 (a'), 1.4)")
        else:
            delta_j = Fraction(1, 2 * 10 ** profile.adjusted_dp)
            adj_rows = [_price_row(r, delta_j) for r in rows]
            ref_rows = [_reference_row(r) for r in sorted(refs[key], key=lambda r: r.value_date)]
            vintage = rows[0].label.vintage.date()
            result = verify_adjustment_v2(ref_rows, adj_rows, [], vintage)
        for r in rows:
            label = apply_v2(r.label, result)
            lineage: Lineage = dataclasses.replace(
                r.lineage, label_status=result.status, adjustment_method=result.method.value)
            out.append(dataclasses.replace(r, label=label, lineage=lineage))
        results.append(LabelResult("V2", rows[0].listing_id, sha, result.status, result.method.value, result.reason))
    return out, results


def _confirm_provenance(
    readings: List[SourceReading], windows: Optional[Dict[str, FXFileWindow]] = None,
) -> Tuple[List[SourceReading], List[LabelResult]]:
    """Ruling 1.1a item 3 over the files of M: each re-server file whose upstream is only declared is
    compared with each publisher-direct file, over the COVERAGES of item 5 (`windows`, from the manifests).
    Any REFUTED verdict refutes the declared file (it stays in M, flagged, and supplies no rate: item 6; the
    differing list is returned as a `LabelResult`); otherwise the dates the check confirmed are CONFIRMED;
    everything else stays UNCONFIRMED."""
    windows = windows or {}
    declared_files: Dict[str, Dict[Tuple[datetime.date, str], Decimal]] = {}
    direct_files: Dict[str, Dict[Tuple[datetime.date, str], Decimal]] = {}
    for r in readings:
        obs = r.observation
        if not isinstance(obs, FXObservation):
            continue
        profile = PROFILES.get(r.source_id)
        role = None if profile is None else profile.role
        target = declared_files if role == REFERENCE_DECLARED else direct_files if role == REFERENCE_DIRECT else None
        if target is not None:
            target.setdefault(r.file_sha256, {})[(obs.value_date, obs.quote_currency.code)] = obs.rate
    if not declared_files or not direct_files:
        return readings, []
    verdict: Dict[str, Tuple[str, Set[datetime.date]]] = {}
    results: List[LabelResult] = []

    def window_of(sha: str) -> Optional[Tuple[Optional[datetime.date], Optional[datetime.date]]]:
        w = windows.get(sha)
        return None if w is None else (w.start, w.end)

    for sha, declared in sorted(declared_files.items()):
        refuted, confirmed = False, set()
        reasons: List[str] = []
        for dsha, direct in sorted(direct_files.items()):
            res = check_provenance(declared, direct, window_of(sha), window_of(dsha))
            if res.status == "REFUTED":
                refuted = True
                reasons.append(f"against {dsha[:12]}: {res.reason}")
            elif res.status == "CONFIRMED":
                confirmed |= set(res.confirmed_dates)
        verdict[sha] = ("REFUTED", set()) if refuted else ("CONFIRMED", confirmed) if confirmed else ("UNCONFIRMED", set())
        results.append(LabelResult("PROVENANCE", None, sha, LabelStatus.CONTRADICTED if refuted else
                                   LabelStatus.VERIFIED if confirmed else LabelStatus.UNVERIFIABLE, None,
                                   verdict[sha][0] + (": " + "; ".join(reasons) if reasons else "")))
    out: List[SourceReading] = []
    for r in readings:
        v = verdict.get(r.file_sha256)
        obs = r.observation
        if v is not None and isinstance(obs, FXObservation):
            status = v[0] if (v[0] == "REFUTED" or obs.value_date in v[1]) else "UNCONFIRMED"
            obs = dataclasses.replace(obs, lineage=dataclasses.replace(obs.lineage, provenance=status))
            r = dataclasses.replace(r, observation=obs)
        out.append(r)
    return out, results


def fx_file_window(manifest: FileManifest, calendars: CalendarSet) -> FXFileWindow:
    """Ruling 1.1a item 5 (1.3): the coverage window of an FX file.

    start: the manifest's requested start (`start`, or `read_start` for a full-history file the human read a
    window of); with none the file is a full-history file and the start is None here (the store takes the first
    date held for each currency). end: the earlier of the requested end (`end` / `read_end`; a full-history file
    has none) and D_ret, the latest fixing date f of the ECB fixing calendar with f at its nominal publication
    time (16:00 Europe/Berlin) at or before the file's retrieval time: a fixing that could not yet have been
    published when the file was fetched is never counted as missing from it. When no ECB calendar governs, or
    none of its fixings is publishable by then, D_ret cannot be determined and `end` is None (UNVERIFIABLE);
    a retrieval after the calendar's coverage leaves the dates beyond the coverage unchecked (end is capped at
    the coverage)."""
    request = dict(manifest.request)

    def iso(key: str) -> Optional[datetime.date]:
        text = request.get(key)
        return None if not text else datetime.date.fromisoformat(text)

    try:
        start = iso("start") or iso("read_start")
        requested_end = iso("end") or iso("read_end")
    except ValueError:
        return FXFileWindow(None, None)
    d_ret = fx_d_ret(manifest, calendars)
    if d_ret is None:
        return FXFileWindow(start, None)
    end = d_ret if requested_end is None else min(requested_end, d_ret)
    return FXFileWindow(start, end)


def fx_d_ret(manifest: FileManifest, calendars: CalendarSet) -> Optional[datetime.date]:
    """`D_ret` (Ruling 1.1a item 5): the latest fixing of the governing ECB calendar whose nominal publication (16:00
    Europe/Berlin) is at or before the file's retrieval time; None when no calendar governs or none was publishable."""
    calendar, _ = calendars.governing(ECB_CALENDAR_ID)
    if calendar is None or calendar.publication_time is None:
        return None
    zone = ZoneInfo(calendar.timezone)
    publishable = [f for f in calendar.dates
                   if datetime.datetime.combine(f, calendar.publication_time, tzinfo=zone) <= manifest.retrieval_time]
    return max(publishable) if publishable else None


def _admit_fx_series(
    readings: List[SourceReading], calendars: CalendarSet, manifests: Dict[str, FileManifest],
) -> Tuple[List[SourceReading], List[LabelResult], List[SeriesExclusion]]:
    """Test V0-FX (market-data/1.7, review finding C2-16), per (file, currency) series, inside the governing ECB calendar's
    coverage (rows outside it are UNVERIFIABLE and not judged):
    - ANY row dated on a day that is not a fixing day excludes the WHOLE series (`V0_FX_OFF_CALENDAR`): excluding only the
      off-calendar rows would leave a series labelled one day early serving the next fixing as CURRENT (look-ahead
      against Ruling 1.1);
    - ANY row dated after `D_ret`, the last fixing publishable by the file's retrieval time, contradicts the whole series
      (`V0_FX_AFTER_RETRIEVAL`): a file cannot contain a fixing not yet published when it was fetched; this catches a
      shift that lands only on valid days.
    An excluded series supplies no rates, its file stays in M, and its dates are simply missing (missed fixings, Ruling
    1.6). Known limit (1.7): a constant shift by whole weeks, or a file too short to touch a non-fixing day, can pass."""
    series: Dict[Tuple[str, str], List[datetime.date]] = {}
    for r in readings:
        obs = r.observation
        if isinstance(obs, FXObservation):
            series.setdefault((r.file_sha256, obs.quote_currency.code), []).append(obs.value_date)
    calendar, _ = calendars.governing(ECB_CALENDAR_ID)
    results: List[LabelResult] = []
    exclusions: List[SeriesExclusion] = []
    dropped: Set[Tuple[str, str]] = set()
    if calendar is not None:
        for key in sorted(series):
            sha, ccy = key
            days = sorted({d for d in series[key] if calendar.covers(d, d)})  # only rows INSIDE the coverage are judged
            off = [d for d in days if calendars.is_session(ECB_CALENDAR_ID, d) is False]
            manifest = manifests.get(sha)
            d_ret = None if manifest is None else fx_d_ret(manifest, calendars)
            late = [d for d in days if d_ret is not None and d > d_ret]
            cause, reason = None, ""
            if off:
                cause = "V0_FX_OFF_CALENDAR"
                reason = f"{len(off)} row(s) dated on a non-fixing day of {calendar.calendar_id}: {', '.join(d.isoformat() for d in off)}"
            elif late:
                cause = "V0_FX_AFTER_RETRIEVAL"
                reason = (f"{len(late)} row(s) dated after D_ret {d_ret.isoformat()} (the last fixing publishable when the "  # type: ignore[union-attr]
                          f"file was retrieved): {', '.join(d.isoformat() for d in late)}")
            if cause is not None:
                dropped.add(key)
                exclusions.append(SeriesExclusion(None, sha, cause, reason, ccy))
                results.append(LabelResult(cause, None, sha, LabelStatus.CONTRADICTED, None, reason, False))
    if not dropped:
        return readings, results, exclusions
    kept = [r for r in readings
            if not (isinstance(r.observation, FXObservation) and (r.file_sha256, r.observation.quote_currency.code) in dropped)]
    return kept, results, exclusions


def _latest_closed_session(calendar: CalendarDays, retrieved: datetime.datetime) -> Optional[datetime.date]:
    """The latest session of an exchange calendar whose SCHEDULED close is at or before `retrieved` (market-data/1.7: what
    a price file retrieved then could at most contain); None when no session had closed."""
    zone = ZoneInfo(calendar.timezone)
    closed = [d for d in calendar.dates
              if (t := calendar.close_time(d)) is not None
              and datetime.datetime.combine(d, t, tzinfo=zone) <= retrieved]
    return max(closed) if closed else None


def _admit_by_calendar(
    readings: List[SourceReading], calendars: CalendarSet, resolver: InstrumentResolverPort,
    manifests: Optional[Dict[str, FileManifest]] = None,
) -> Tuple[List[SourceReading], List[LabelResult], List[SeriesExclusion]]:
    """Test V0 per (listing, file) quote series, and `observed_at` from the calendar's close time. A
    CONTRADICTED series supplies no readings, and its failure is kept (`SeriesExclusion`): the file stays in M
    (section 3 consequences, 1.3). market-data/1.7 adds, for prices, the after-retrieval check: a row dated after the
    latest session whose scheduled close is at or before the file's retrieval time (inside the calendar's coverage)
    could not be in that file, and contradicts the whole series; it catches a shift that lands only on valid days."""
    series: Dict[Tuple[str, str], List[datetime.date]] = {}
    listing_of: Dict[Tuple[str, str], uuid.UUID] = {}
    for r in readings:
        if isinstance(r.observation, QuoteObservation):
            key = (str(r.observation.listing_id), r.file_sha256)
            series.setdefault(key, []).append(r.observation.value_date)
            listing_of[key] = r.observation.listing_id
    results: List[LabelResult] = []
    exclusions: List[SeriesExclusion] = []
    dropped: Set[Tuple[str, str]] = set()
    for key in sorted(series):
        listing_id = listing_of[key]
        mic = resolver.exchange_mic(listing_id)
        v0 = verify_v0(series[key], calendars, mic)
        status, reason = v0.status, v0.reason
        calendar, _ = calendars.governing(mic)
        manifest = (manifests or {}).get(key[1])
        if status is not LabelStatus.CONTRADICTED and calendar is not None and manifest is not None:
            last = _latest_closed_session(calendar, manifest.retrieval_time)
            late = sorted({d for d in series[key] if calendar.covers(d, d) and (last is None or d > last)})
            if late:
                status = LabelStatus.CONTRADICTED
                reason = (f"V0 after retrieval: {len(late)} row(s) dated after the latest session closed at the file's "
                          f"retrieval time ({'none' if last is None else last.isoformat()}): "
                          f"{', '.join(d.isoformat() for d in late)}")
        admitted = status is not LabelStatus.CONTRADICTED
        if not admitted:
            dropped.add(key)
            exclusions.append(SeriesExclusion(listing_id, key[1], "V0", reason))
        results.append(LabelResult("V0", listing_id, key[1], status, None, reason, admitted))
    out: List[SourceReading] = []
    for r in readings:
        obs = r.observation
        if isinstance(obs, QuoteObservation):
            if (str(obs.listing_id), r.file_sha256) in dropped:
                continue  # CONTRADICTED: not admitted, treated as absent
            calendar, _ = calendars.governing(resolver.exchange_mic(obs.listing_id))
            close = None if calendar is None else calendar.close_time(obs.value_date)
            if close is not None and obs.observed_at is None and calendar is not None:
                instant = datetime.datetime.combine(obs.value_date, close, tzinfo=ZoneInfo(calendar.timezone))
                r = dataclasses.replace(r, observation=dataclasses.replace(obs, observed_at=instant))
        out.append(r)
    return out, results, exclusions


def build_in_memory_market_data(
    release: MarketDataRelease,
    files: FileStore,
    registry: SourceRegistry,
    adapters: AdapterRegistry,
    resolver: InstrumentResolverPort,
    *,
    catalog_calendars: Mapping[str, str],
) -> BuildResult:
    """Load every file the release names (verifying hashes), in the release's sorted
    order. A file the release names but the store lacks is an error, never skipped. A file whose
    source is not attested is refused from its MANIFEST alone: its payload is never read or parsed.
    `catalog_calendars` (benchmark id -> the calendar its catalog entry names) is REQUIRED (CP4F-8): it is checked against the calendar a SEGMENTED benchmark file declares (CP4M-10 point 3), and a builder that forgot
    it would skip the check silently. Pass the benchmark catalog's calendars, or an explicit empty mapping where no benchmark catalog applies (a release with no benchmark, a test of another kind)."""
    index = files.index()
    readings: List[SourceReading] = []
    benchmarks: List[BenchmarkEntry] = []
    summaries: List[FileSummary] = []
    issues: List[Tuple[str, AdapterIssue]] = []
    exceptions: List[Tuple[str, ResolutionException]] = []
    evidence: List[Tuple[str, IdentityEvidence]] = []
    adjusted_all: List[AdjustedQuote] = []
    reference_all: List[AdjustedQuote] = []
    calendars_all: List[CalendarDays] = []
    risk_free_all: List[RiskFreeEntry] = []
    manifests_all: List[FileManifest] = []
    file_exclusions: List[SeriesExclusion] = []  # series a file contradicts by a repeated date (market-data/1.16 Tests V0, V0-FX)
    synthetic = False
    source_records: Dict[str, SourceRecord] = {}  # the sources with at least one file in this release (performance/1.12 Ruling 1.7 item 4)
    for sha in release.files:
        path = index.get(sha)
        if path is None:
            raise ReleaseFileMissingError(f"release names file {sha} which the store lacks")
        manifest = FileManifest.from_json(path.read_text(encoding="utf-8"))
        source = registry.require_attested(manifest.source_id)  # before the payload is read (Ruling 4.7)
        source_records[source.source_id] = source
        verified = files.read_verified(path)
        adapter = adapters.for_manifest(verified.manifest)
        result = ingest_file(verified, adapter, resolver, source)
        synthetic = synthetic or manifest.usage_scope is UsageScope.SYNTHETIC_TEST
        manifests_all.append(verified.manifest)
        readings += result.readings
        benchmarks += result.benchmarks
        summaries.append(result.summary)
        issues += [(sha, i) for i in result.issues]
        exceptions += [(sha, e) for e in result.exceptions]
        evidence += [(sha, e) for e in result.identity_evidence]
        adjusted_all += list(result.adjusted)
        reference_all += list(result.reference)
        calendars_all += list(result.calendars)
        risk_free_all += list(result.risk_free)
        file_exclusions += list(result.exclusions)
    calendars = CalendarSet(calendars_all)  # one version per calendar_id (Ruling 0.1)
    by_sha = {m.file_sha256: m for m in manifests_all}
    _require_disjoint_segments(readings, benchmarks, adjusted_all, risk_free_all, calendars, by_sha, resolver, catalog_calendars)  # Ruling 0.1 (1.12): disjoint coverage per series, for every kind
    label_results: List[LabelResult] = []
    readings, v0_results, exclusions = _admit_by_calendar(readings, calendars, resolver, by_sha)
    label_results += v0_results
    readings, fx_v0_results, fx_exclusions = _admit_fx_series(readings, calendars, by_sha)  # Test V0-FX (1.7)
    label_results += fx_v0_results
    exclusions = list(exclusions) + fx_exclusions
    for fe in file_exclusions:  # the file's own contradiction: the same CONTRADICTED outcome, in lineage and in the store's exclusions
        exclusions.append(fe)
        label_results.append(LabelResult(fe.test, fe.listing_id, fe.file_sha256, LabelStatus.CONTRADICTED, None, fe.reason, False))
    adjusted_all, v2_results = _run_v2(adjusted_all, reference_all)
    label_results += v2_results
    fx_windows = {m.file_sha256: fx_file_window(m, calendars) for m in manifests_all if m.data_kind is DataKind.FX}
    readings, provenance_results = _confirm_provenance(readings, fx_windows)
    label_results += provenance_results
    store = InMemoryMarketData(release, readings, benchmarks, adjusted_all,
                               exchange_of=resolver.exchange_mic, contains_synthetic=synthetic,
                               fx_windows=fx_windows, exclusions=exclusions, source_records=source_records.values(), risk_free=risk_free_all)
    return BuildResult(store, tuple(summaries), tuple(issues), tuple(exceptions), tuple(evidence),
                       calendars, tuple(label_results), tuple(manifests_all))
