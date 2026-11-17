"""In-memory instrument resolution and identity registration (Tech Plan §15.6).

`listing_id` is the key (PD-0021 §1); FIGI, MIC, ticker and vendor id are resolution
attributes held in a TEMPORAL, append-only identifier table. Resolution returns a status,
never a guess:

  RESOLVED    exactly one listing; the steps that matched agree
  UNRESOLVED  no candidate
  AMBIGUOUS   a step matched more than one listing
  CONFLICT    steps point at different listings, or the identifiers assert a FIGI that
              differs from the one stored for the matched listing (nothing is overwritten)

Steps: (1) FIGI; (2) ticker with MIC when given, valid on the date; (3) vendor id scoped to
its source. A symbol change is an attribute update (a new identifier row and the listing's
current ticker), never a change of `listing_id`.

Identity is created only by `register_instruments`, and only for an entry whose
resolution is UNRESOLVED. Price/FX/action ingestion never creates identity. New ids come
from an injected factory: this module has no randomness and no clock.
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from dataclasses import dataclass
from enum import Enum, unique
from typing import Callable, Dict, FrozenSet, Iterable, List, Mapping, Optional, Set, Tuple

from domain.currency import CurrencyCode
from domain.instrument import Instrument, Issuer, Listing, SecurityType
from marketdata.exchange_codes import A6, CodeTable
from marketdata.contracts import (
    ExternalIdentifiers,
    IdentityAssertion,
    InstrumentResolution,
    ResolutionStatus,
)

SCHEME_FIGI = "FIGI"
SCHEME_TICKER = "TICKER"
SCHEME_VENDOR = "VENDOR"
SCHEME_COMPOSITE_FIGI = "COMPOSITE_FIGI"
SCHEME_SHARE_CLASS_FIGI = "SHARE_CLASS_FIGI"


class IdentityError(ValueError):
    pass


@dataclass(frozen=True)
class IdentifierRow:
    """One external identifier a listing has had. `qualifier` is the MIC for a TICKER and
    the source id for a VENDOR id. Validity is inclusive; None means unbounded."""

    listing_id: uuid.UUID
    scheme: str
    value: str
    qualifier: Optional[str] = None
    valid_from: Optional[datetime.date] = None
    valid_to: Optional[datetime.date] = None
    asserted_by: str = ""

    def valid_on(self, day: Optional[datetime.date]) -> bool:
        if day is None:
            return True
        return (self.valid_from is None or self.valid_from <= day) and (
            self.valid_to is None or day <= self.valid_to
        )

    def ref(self) -> str:
        return f"{self.scheme}:{self.qualifier or '-'}:{self.value}"


@dataclass(frozen=True)
class InstrumentEntry:
    """What a human identity file supplies to create an instrument: price files do not
    carry issuer name, security type or currency."""

    issuer_name: str
    security_type: SecurityType
    mic: str
    exchange: str
    ticker: str
    trading_currency: CurrencyCode
    figi: Optional[str] = None
    issuer_domicile: Optional[str] = None
    vendor_ids: Tuple[Tuple[str, str], ...] = ()  # (source_id, vendor_id)
    valid_from: Optional[datetime.date] = None


@dataclass(frozen=True)
class RegistrationResult:
    entry: InstrumentEntry
    resolution: InstrumentResolution
    created: bool
    listing_id: Optional[uuid.UUID]


@unique
class SymbolChangeStatus(Enum):
    """market-data/1.3 Ruling 7.2 item 3, the deterministic test that a change of ticker is a SYMBOL CHANGE."""

    CONFIRMED = "CONFIRMED"  # the old and the new ticker resolve to the SAME FIGI on the same exchange: applied
    QUARANTINED = "QUARANTINED"  # different FIGIs (or an exchange or stored-FIGI mismatch): a human decides
    UNCONFIRMED = "UNCONFIRMED"  # an identifier source has no assertion for one of the tickers: nothing is applied


@dataclass(frozen=True)
class SymbolChangeDecision:
    """The outcome of `propose_symbol_change`. `applied` is True only for CONFIRMED. A QUARANTINED decision is
    kept by the registry (`quarantine()`) for a human; it is never auto-merged and never a new listing."""

    status: SymbolChangeStatus
    listing_id: uuid.UUID
    old_ticker: str
    new_ticker: str
    effective: datetime.date
    old_figi: Optional[str]
    new_figi: Optional[str]
    reason: str
    applied: bool


@dataclass(frozen=True)
class QuarantinedAssertion:
    """An identifier-source assertion that matched an existing listing by FIGI or ticker but was NOT accepted as
    evidence for it (C2-4, Ruling 7.2 item 3, PD-0021 section 1: identity is by FIGI on the same MIC). Kept for a
    human; nothing was attached to the listing."""

    assertion: IdentityAssertion
    listing_id: uuid.UUID
    verdict: str  # "EXCHANGE_MISMATCH" | "EXCHANGE_UNVERIFIABLE"
    reason: str


_EX_OK, _EX_MISMATCH, _EX_UNMAPPED = "OK", "EXCHANGE_MISMATCH", "EXCHANGE_UNVERIFIABLE"


class InMemoryIdentityRegistry:
    """The code table is DATA (market-data/1.5 Appendix A.6, `marketdata.exchange_codes`, versioned): the registry uses
    `code_table` (default: the Quant's A.6). Only entries with status OBSERVED or CONFIRMED attach a FIGI (Ruling 7.3
    items 3 and 6); a MEMORY or TO_CONFIRM entry, an unknown MIC, never does, and a symbol change on such a listing is
    never CONFIRMED (C2-4). `exchange_codes` (MIC -> codes) replaces those MICs' entries with CONFIRMED ones: for tests,
    and for a human who has confirmed codes before the table is updated."""

    def __init__(self, new_id: Callable[[], uuid.UUID], *,
                 exchange_codes: Optional[Mapping[str, Iterable[str]]] = None,
                 code_table: Optional[CodeTable] = None):
        self._new_id = new_id
        table = code_table or A6
        self._codes: CodeTable = table.with_confirmed(exchange_codes) if exchange_codes else table
        self._assertion_quarantine: List[QuarantinedAssertion] = []
        self._quarantine: List[SymbolChangeDecision] = []
        self._issuers: Dict[uuid.UUID, Issuer] = {}
        self._instruments: Dict[uuid.UUID, Instrument] = {}
        self._listings: Dict[uuid.UUID, Listing] = {}
        self._rows: List[IdentifierRow] = []

    # -- reads (InstrumentResolverPort) ---------------------------------------------------
    def listing(self, listing_id: uuid.UUID) -> Listing:
        return self._listings[listing_id]

    def trading_currency(self, listing_id: uuid.UUID) -> Optional[CurrencyCode]:
        listing = self._listings.get(listing_id)
        return None if listing is None else listing.trading_currency

    def exchange_mic(self, listing_id: uuid.UUID) -> Optional[str]:
        """The MIC of the listing's exchange (None if the listing is unknown): which calendar
        governs it (Ruling 5.3) and which market it is in (Ruling 4.7)."""
        listing = self._listings.get(listing_id)
        return None if listing is None else listing.mic

    def snapshot(self) -> Tuple[Tuple[Issuer, ...], Tuple[Instrument, ...], Tuple[Listing, ...]]:
        """The identity entities, ordered by id: what a persistent identity writer (a later increment; none exists
        in CP1) would store. Read-only."""
        return (tuple(self._issuers[k] for k in sorted(self._issuers, key=str)),
                tuple(self._instruments[k] for k in sorted(self._instruments, key=str)),
                tuple(self._listings[k] for k in sorted(self._listings, key=str)))

    def security_type(self, listing_id: uuid.UUID) -> Optional[str]:
        """The `Instrument.security_type` value of the listing's instrument (None if unknown): the identity
        record that decides the CN security class (market-data/1.2 section 9A #2)."""
        listing = self._listings.get(listing_id)
        if listing is None:
            return None
        instrument = self._instruments.get(listing.instrument_id)
        return None if instrument is None else instrument.security_type.value

    def identifier_rows(self, listing_id: Optional[uuid.UUID] = None) -> Tuple[IdentifierRow, ...]:
        return tuple(r for r in self._rows if listing_id is None or r.listing_id == listing_id)

    def resolve(
        self, identifiers: ExternalIdentifiers, as_of: Optional[datetime.date]
    ) -> InstrumentResolution:
        steps: Dict[str, Set[uuid.UUID]] = {}
        evidence: List[str] = []
        if identifiers.figi is not None:
            hits = [r for r in self._rows if r.scheme == SCHEME_FIGI
                    and r.value == identifiers.figi and r.valid_on(as_of)]
            steps["FIGI"] = {r.listing_id for r in hits}
            evidence += [r.ref() for r in hits]
        if identifiers.ticker is not None:
            hits = [r for r in self._rows if r.scheme == SCHEME_TICKER
                    and r.value == identifiers.ticker and r.valid_on(as_of)
                    and (identifiers.mic is None or r.qualifier == identifiers.mic)]
            steps["TICKER"] = {r.listing_id for r in hits}
            evidence += [r.ref() for r in hits]
        if identifiers.vendor_id is not None and identifiers.source_id is not None:
            hits = [r for r in self._rows if r.scheme == SCHEME_VENDOR
                    and r.value == identifiers.vendor_id and r.qualifier == identifiers.source_id
                    and r.valid_on(as_of)]
            steps["VENDOR"] = {r.listing_id for r in hits}
            evidence += [r.ref() for r in hits]

        def result(status: ResolutionStatus, listing: Optional[uuid.UUID],
                   candidates: Set[uuid.UUID], matched: Iterable[str]) -> InstrumentResolution:
            return InstrumentResolution(
                identifiers, listing, status,
                candidates=tuple(sorted(candidates, key=str)),
                matched_on=tuple(sorted(matched)),
                evidence_refs=tuple(sorted(set(evidence))),
            )

        matched = {name: ids for name, ids in steps.items() if ids}
        if not matched:
            return result(ResolutionStatus.UNRESOLVED, None, set(), ())
        union: Set[uuid.UUID] = set().union(*matched.values())
        if any(len(ids) > 1 for ids in matched.values()):
            return result(ResolutionStatus.AMBIGUOUS, None, union, matched)
        if len(union) > 1:
            return result(ResolutionStatus.CONFLICT, None, union, matched)
        (only,) = union
        if identifiers.figi is not None and "FIGI" not in matched:
            stored = [r.value for r in self._rows if r.listing_id == only
                      and r.scheme == SCHEME_FIGI and r.valid_on(as_of)]
            if stored:  # the file asserts a FIGI that differs from the stored one
                return result(ResolutionStatus.CONFLICT, None, {only}, matched)
        return result(ResolutionStatus.RESOLVED, only, {only}, matched)

    def _exchange_verdict(self, listing_id: uuid.UUID, exch_code: str) -> Tuple[str, str]:
        """(verdict, reason): does the source's EXCHANGE-LEVEL exchange code denote the listing's MIC, with an entry whose
        status attaches (OBSERVED or CONFIRMED; Ruling 7.3 items 3 and 6)?"""
        mic = self._listings[listing_id].mic
        if not self._codes.knows_mic(mic):
            return _EX_UNMAPPED, (f"no MIC-to-exchange-code mapping for MIC {mic} in {self._codes.version}: the "
                                  f"exchange code {exch_code!r} cannot be compared with the listing's MIC")
        entry = self._codes.entry_for(mic, exch_code)
        if entry is None:
            codes = sorted(e.code for e in self._codes.exchange[mic])
            return _EX_MISMATCH, (f"exchange code {exch_code!r} is not one of the codes for MIC {mic} "
                                  f"({', '.join(codes)}): evidence from another venue")
        if not entry.attaches:
            return _EX_UNMAPPED, (f"the code {exch_code!r} for MIC {mic} has status {entry.status} in "
                                  f"{self._codes.version}: only OBSERVED or CONFIRMED entries attach a FIGI")
        return _EX_OK, ""

    @staticmethod
    def _is_composite(a: IdentityAssertion) -> bool:
        """Ruling 7.3 item 2: the level is decided from the RECORD: figi == compositeFIGI means composite-level."""
        return a.composite_figi is not None and a.composite_figi == a.figi

    _TYPE_OF = {"common stock": "COMMON_STOCK", "etp": "ETF"}

    def _type_consistent(self, listing_id: uuid.UUID, security_type: Optional[str]) -> bool:
        """Ruling 7.3 item 3: the record's security type is consistent with the instrument's SecurityType. C2-17 (CP2
        final check): a record with NO security type is not consistent with anything, so it does not attach."""
        if security_type is None:
            return False
        instrument = self._instruments.get(self._listings[listing_id].instrument_id)
        return instrument is not None and self._TYPE_OF.get(security_type.strip().casefold()) == instrument.security_type.value

    @staticmethod
    def _assertion_day(a: IdentityAssertion) -> Optional[datetime.date]:
        """The date an assertion is made on: the source's own time if it gave one, else the retrieval time (its date);
        None only when the record carries neither (then any date is accepted, as before)."""
        stamp = a.timing.source_time or a.lineage.retrieved_at
        return None if stamp is None else stamp.date()

    def _ticker_on(self, listing_id: uuid.UUID, ticker: str, day: Optional[datetime.date]) -> bool:
        """Was `ticker` the listing's ticker ON `day` (Ruling 7.2 item 2; Ruling 7.3 items 3 and 4)?"""
        mic = self._listings[listing_id].mic
        return any(r.listing_id == listing_id and r.scheme == SCHEME_TICKER and r.qualifier == mic and r.value == ticker
                   and r.valid_on(day) for r in self._rows)

    def assertion_quarantine(self) -> Tuple[QuarantinedAssertion, ...]:
        """Assertions that matched a listing but were not accepted (C2-4), in the order they were seen."""
        return tuple(self._assertion_quarantine)

    # -- writes (identity registry; used by ingestion setup, never by analytics) ----------
    def _add_row(self, row: IdentifierRow) -> None:
        if row.listing_id not in self._listings:
            raise IdentityError("unknown listing_id")
        self._rows.append(row)

    def add_vendor_id(self, listing_id: uuid.UUID, source_id: str, vendor_id: str,
                      valid_from: Optional[datetime.date] = None, asserted_by: str = "") -> None:
        self._add_row(IdentifierRow(listing_id, SCHEME_VENDOR, vendor_id, source_id,
                                    valid_from, None, asserted_by))

    def change_ticker(self, listing_id: uuid.UUID, new_ticker: str,
                      effective: datetime.date, asserted_by: str = "") -> None:
        """A symbol change: an attribute update. The old identifier row is closed the day
        before `effective`; the listing keeps its `listing_id`."""
        listing = self._listings[listing_id]
        open_rows = [i for i, r in enumerate(self._rows)
                     if r.listing_id == listing_id and r.scheme == SCHEME_TICKER
                     and r.qualifier == listing.mic and r.valid_to is None]
        for i in open_rows:
            old = self._rows[i]
            if old.valid_from is not None and old.valid_from >= effective:
                raise IdentityError("symbol change must be after the identifier's valid_from")
            self._rows[i] = dataclasses.replace(
                old, valid_to=effective - datetime.timedelta(days=1)
            )
        self._add_row(IdentifierRow(listing_id, SCHEME_TICKER, new_ticker, listing.mic,
                                    effective, None, asserted_by))
        self._listings[listing_id] = dataclasses.replace(listing, ticker=new_ticker)

    def propose_symbol_change(
        self, listing_id: uuid.UUID, new_ticker: str, effective: datetime.date,
        assertions: Iterable[IdentityAssertion], asserted_by: str = "",
    ) -> SymbolChangeDecision:
        """Ruling 7.2 item 3 (the FIGI-equality test). A human proposes that `listing_id`'s ticker changed to
        `new_ticker` on `effective`; the identifier source's assertions (saved files of the FIGI identity source) decide whether
        it IS a symbol change, deterministically:

        - the OLD ticker (the listing's current one) and the NEW ticker must each have an assertion, and both
          assertions must give the SAME FIGI on the SAME exchange code, which must be an exchange code of the
          LISTING'S MIC (C2-4: the registry's `exchange_codes` data; the exchange code is the source's own, never
          inferred to be a MIC) and, where the listing stores a FIGI, that one. Then the change is CONFIRMED and
          applied as an attribute update (`change_ticker`): the listing keeps its `listing_id`.
        - an exchange code that is not the listing's MIC's is QUARANTINED; a MIC with no mapping cannot be
          compared, so it is UNCONFIRMED, never CONFIRMED (C2-4).
        - DIFFERENT FIGIs (or a different exchange code, or a FIGI that contradicts the stored one) mean a
          different instrument or listing (a merger, a new share class, a venue transfer): QUARANTINED. Nothing
          is applied or merged; the decision is kept for a human (`quarantine()`).
        - no assertion for either ticker (the old one often no longer resolves): UNCONFIRMED. Nothing is applied;
          observations under the new ticker stay UNRESOLVED (never guessed). An issuer filing or an exchange
          notice, registered by a human, is the only other evidence the Ruling accepts, and is not built here.

        An assertion matches a ticker exactly as published (no zero padding, no case folding)."""
        listing = self._listings[listing_id]
        old = listing.ticker
        by_ticker: Dict[str, List[IdentityAssertion]] = {}
        for a in assertions:
            by_ticker.setdefault(a.ticker, []).append(a)

        def figis(ticker: str) -> Set[Tuple[str, str]]:
            # Ruling 7.3 item 5: only EXCHANGE-level FIGIs decide a symbol change; a composite record is not one
            return {(a.figi, a.exch_code) for a in by_ticker.get(ticker, []) if not self._is_composite(a)}

        def composites(ticker: str) -> Set[str]:
            return {a.figi for a in by_ticker.get(ticker, []) if self._is_composite(a)}

        old_ids, new_ids = figis(old), figis(new_ticker)
        stored = sorted(r.value for r in self._rows if r.listing_id == listing_id
                        and r.scheme == SCHEME_FIGI and r.valid_on(effective - datetime.timedelta(days=1)))

        def decide(status: SymbolChangeStatus, reason: str, applied: bool = False) -> SymbolChangeDecision:
            decision = SymbolChangeDecision(
                status, listing_id, old, new_ticker, effective,
                next(iter(sorted(f for f, _ in old_ids)), None), next(iter(sorted(f for f, _ in new_ids)), None),
                reason, applied)
            if status is SymbolChangeStatus.QUARANTINED:
                self._quarantine.append(decision)
            return decision

        if (not old_ids or not new_ids) and composites(old) & composites(new_ticker):
            return decide(SymbolChangeStatus.UNCONFIRMED,
                          "equal COMPOSITE FIGIs alone are not sufficient (Ruling 7.3 item 5): a move to another venue "
                          "keeps the composite and changes the exchange-level FIGI; a human decides")
        if not old_ids or not new_ids:
            missing = [t for t, ids in ((old, old_ids), (new_ticker, new_ids)) if not ids]
            return decide(SymbolChangeStatus.UNCONFIRMED,
                          f"no identifier-source assertion for {', '.join(repr(t) for t in missing)}: "
                          "nothing is applied and observations under the new ticker stay unresolved")
        if len(old_ids) > 1 or len(new_ids) > 1:
            return decide(SymbolChangeStatus.QUARANTINED, "an identifier source gave several FIGIs for one ticker")
        (old_figi, old_exch), (new_figi, new_exch) = next(iter(old_ids)), next(iter(new_ids))
        if old_figi != new_figi:
            return decide(SymbolChangeStatus.QUARANTINED,
                          f"different FIGIs ({old_figi} for {old!r}, {new_figi} for {new_ticker!r}): a different "
                          "instrument or listing, not a symbol change; a human decides")
        if old_exch != new_exch:
            return decide(SymbolChangeStatus.QUARANTINED,
                          f"the same FIGI under two exchange codes ({old_exch}, {new_exch}): a venue change is not a "
                          "symbol change; a human decides")
        verdict, why = self._exchange_verdict(listing_id, old_exch)
        if verdict == _EX_MISMATCH:  # C2-4: the same FIGI on ANOTHER venue's exchange code is not this listing
            return decide(SymbolChangeStatus.QUARANTINED, why + "; a human decides")
        if verdict == _EX_UNMAPPED:  # C2-4: no way to say the exchange is the listing's MIC: never CONFIRMED
            return decide(SymbolChangeStatus.UNCONFIRMED, why + ": nothing is applied")
        if stored and old_figi not in stored:
            return decide(SymbolChangeStatus.QUARANTINED,
                          f"the assertions' FIGI {old_figi} contradicts the FIGI stored for the listing "
                          f"({', '.join(stored)}): nothing is overwritten")
        self.change_ticker(listing_id, new_ticker, effective, asserted_by or f"identity-assertion:{old_figi}")
        return decide(SymbolChangeStatus.CONFIRMED, f"both tickers resolve to FIGI {old_figi} on {old_exch}", True)

    def quarantine(self) -> Tuple[SymbolChangeDecision, ...]:
        """Symbol-change proposals sent to a human, in the order they were made."""
        return tuple(self._quarantine)

    def apply_identity_assertions(
        self, assertions: Iterable[IdentityAssertion]
    ) -> Tuple[Tuple[IdentityAssertion, InstrumentResolution, Tuple[str, ...]], ...]:
        """Use identifier-source assertions as EVIDENCE for EXISTING listings. Creates no
        Issuer, Instrument or Listing. An assertion that resolves (by FIGI, or by ticker with
        a consistent FIGI) AND whose exchange code is an exchange code of the listing's MIC (C2-4: FIGI identity is
        on the same MIC, PD-0021 section 1) adds FIGI, composite-FIGI and share-class-FIGI rows the listing
        lacks (an attribute update); one that does not resolve, is ambiguous, conflicts
        with a stored FIGI, or comes from another exchange (or one whose MIC has no code mapping) changes nothing and
        is returned for a human: the last two as a CONFLICT resolution and an entry of `assertion_quarantine()`.
        Returns (assertion, resolution, schemes added)."""
        out = []
        for a in assertions:
            if self._is_composite(a):
                out.append(self._apply_composite(a))
                continue
            # the ticker must be the listing's ticker VALID ON THE ASSERTION'S DATE (final check, note), not on any date
            res = self.resolve(ExternalIdentifiers(figi=a.figi, ticker=a.ticker), self._assertion_day(a))
            added: List[str] = []
            if res.status is ResolutionStatus.RESOLVED and res.listing_id is not None:
                lid = res.listing_id
                verdict, why = self._exchange_verdict(lid, a.exch_code)
                if verdict == _EX_OK and not self._type_consistent(lid, a.security_type):
                    verdict, why = "SECURITY_TYPE_MISMATCH", (
                        f"the record's security type {a.security_type!r} is not consistent with the instrument's "
                        f"SecurityType (Ruling 7.3 item 3; a record with no security type does not attach)")
                stored_composite = self._listings[lid].composite_figi
                if (verdict == _EX_OK and a.composite_figi is not None and stored_composite is not None
                        and stored_composite != a.composite_figi):
                    # C2-18: the same exchange-level FIGI with a DIFFERENT composite: quarantined like the composite path
                    # does (COMPOSITE_CONFLICT); nothing from this record is attached, no second composite row is added
                    verdict, why = "COMPOSITE_CONFLICT", (
                        f"the listing already holds composite FIGI {stored_composite}, the record says "
                        f"{a.composite_figi}: nothing is overwritten and nothing is added")
                stored_share_class = self._instruments[self._listings[lid].instrument_id].share_class_figi
                if (verdict == _EX_OK and a.share_class_figi is not None and stored_share_class is not None
                        and stored_share_class != a.share_class_figi):
                    # market-data/1.16 Ruling 7.3 item 10 (fail closed; section 11 item 24, review C-9): the same exchange-level FIGI with a
                    # DIFFERENT share class is two securities. Nothing from this record is attached: no Listing.figi, no composite_figi, no
                    # identifier row of any level, and no second SHARE_CLASS_FIGI row beside the instrument's old value. The record is kept
                    # as unmatched evidence for a human, like the composite mismatch above.
                    verdict, why = "SHARE_CLASS_CONFLICT", (
                        f"the instrument already holds share-class FIGI {stored_share_class}, the record says "
                        f"{a.share_class_figi}: nothing is overwritten and nothing is added (Ruling 7.3 item 10)")
                if verdict != _EX_OK:
                    self._assertion_quarantine.append(QuarantinedAssertion(a, lid, verdict, why))
                    res = InstrumentResolution(res.identifiers, None, ResolutionStatus.CONFLICT,
                                               candidates=(lid,), matched_on=res.matched_on,
                                               evidence_refs=res.evidence_refs)
                    out.append((a, res, ()))
                    continue
                # Ruling 7.3 items 1, 3 and 7: an EXCHANGE-level record fills Listing.figi; its compositeFIGI fills
                # Listing.composite_figi and its shareClassFIGI the instrument's share-class attribute
                who = f"identity-assertion:{a.lineage.source_id};{self._codes.version}"
                listing = self._listings[lid]
                have = {(r.scheme, r.value) for r in self._rows if r.listing_id == lid}
                for scheme, value in ((SCHEME_FIGI, a.figi), (SCHEME_COMPOSITE_FIGI, a.composite_figi),
                                      (SCHEME_SHARE_CLASS_FIGI, a.share_class_figi)):
                    if value is not None and (scheme, value) not in have:
                        self._rows.append(IdentifierRow(lid, scheme, value, None, None, None, who))
                        added.append(scheme)
                if listing.figi is None:
                    listing = dataclasses.replace(listing, figi=a.figi)
                if a.composite_figi is not None and listing.composite_figi is None:
                    listing = dataclasses.replace(listing, composite_figi=a.composite_figi)
                self._listings[lid] = listing
                if a.share_class_figi is not None:
                    instrument = self._instruments[listing.instrument_id]
                    if instrument.share_class_figi is None:
                        self._instruments[listing.instrument_id] = dataclasses.replace(
                            instrument, share_class_figi=a.share_class_figi)
            out.append((a, res, tuple(added)))
        return tuple(out)

    def _apply_composite(
        self, a: IdentityAssertion,
    ) -> Tuple[IdentityAssertion, InstrumentResolution, Tuple[str, ...]]:
        """Ruling 7.3 item 4: a COMPOSITE-level record (figi == compositeFIGI) never fills `Listing.figi`. It may fill
        `Listing.composite_figi` on exactly one listing, and only when its composite code is a known country code with
        an attaching status (A.6 `composite_codes`) and EXACTLY ONE active listing of that country (a MIC the code
        spans) carries the record's ticker. Zero or several attach nothing: the link is a fact about OUR listing table,
        not a venue read out of the record."""
        ids = ExternalIdentifiers(figi=a.figi, ticker=a.ticker)
        entry = self._codes.composite.get(a.exch_code)
        if entry is None or not entry.attaches:
            status = "unknown" if entry is None else entry.status
            res = InstrumentResolution(ids, None, ResolutionStatus.UNRESOLVED)
            matched = [lid for lid, li in self._listings.items() if li.ticker == a.ticker]
            if matched:  # something of ours carries the ticker: keep the evidence for a human
                self._assertion_quarantine.append(QuarantinedAssertion(
                    a, sorted(matched, key=str)[0], _EX_UNMAPPED,
                    f"composite code {a.exch_code!r} is {status} in {self._codes.version}: nothing attached"))
            return a, res, ()
        day = self._assertion_day(a)
        candidates = sorted((lid for lid, li in self._listings.items()
                             if li.is_active and li.mic in entry.mics and self._ticker_on(lid, a.ticker, day)), key=str)
        if not candidates:
            return a, InstrumentResolution(ids, None, ResolutionStatus.UNRESOLVED), ()
        if len(candidates) > 1:
            self._assertion_quarantine.append(QuarantinedAssertion(
                a, candidates[0], "COMPOSITE_NOT_UNIQUE",
                f"{len(candidates)} active listings in the country of composite code {a.exch_code!r} carry ticker "
                f"{a.ticker!r}: nothing attached (Ruling 7.3 item 4)"))
            return a, InstrumentResolution(ids, None, ResolutionStatus.AMBIGUOUS, candidates=tuple(candidates)), ()
        lid = candidates[0]
        listing = self._listings[lid]
        res = InstrumentResolution(ids, lid, ResolutionStatus.RESOLVED, candidates=(lid,),
                                   matched_on=("COMPOSITE_UNIQUE_TICKER",))
        if listing.composite_figi is not None and listing.composite_figi != a.figi:
            self._assertion_quarantine.append(QuarantinedAssertion(
                a, lid, "COMPOSITE_CONFLICT",
                f"the listing already holds composite FIGI {listing.composite_figi}: nothing is overwritten"))
            return a, InstrumentResolution(ids, None, ResolutionStatus.CONFLICT, candidates=(lid,)), ()
        if listing.composite_figi == a.figi:
            return a, res, ()
        self._listings[lid] = dataclasses.replace(listing, composite_figi=a.figi)
        self._rows.append(IdentifierRow(lid, SCHEME_COMPOSITE_FIGI, a.figi, None, None, None,
                                        f"identity-assertion:{a.lineage.source_id};{self._codes.version}"))
        return a, res, (SCHEME_COMPOSITE_FIGI,)

    def register_instruments(
        self, entries: Iterable[InstrumentEntry]
    ) -> Tuple[RegistrationResult, ...]:
        """Create Issuer/Instrument/Listing ONLY for an entry whose resolution is
        UNRESOLVED. A resolved entry is returned as is; an AMBIGUOUS or CONFLICT entry is
        reported and nothing is created or overwritten."""
        results = []
        for entry in entries:
            ids = ExternalIdentifiers(figi=entry.figi, mic=entry.mic, ticker=entry.ticker)
            resolution = self.resolve(ids, entry.valid_from)
            if resolution.status is ResolutionStatus.UNRESOLVED:
                issuer = Issuer(self._new_id(), entry.issuer_name, entry.issuer_domicile)
                instrument = Instrument(self._new_id(), issuer.issuer_id, entry.security_type)
                listing = Listing(
                    listing_id=self._new_id(), instrument_id=instrument.instrument_id,
                    mic=entry.mic, exchange=entry.exchange, ticker=entry.ticker,
                    trading_currency=entry.trading_currency, figi=entry.figi,
                )
                self._issuers[issuer.issuer_id] = issuer
                self._instruments[instrument.instrument_id] = instrument
                self._listings[listing.listing_id] = listing
                self._rows.append(IdentifierRow(listing.listing_id, SCHEME_TICKER, entry.ticker,
                                                entry.mic, entry.valid_from, None, "register"))
                if entry.figi is not None:
                    self._rows.append(IdentifierRow(listing.listing_id, SCHEME_FIGI, entry.figi,
                                                    None, entry.valid_from, None, "register"))
                for source_id, vendor_id in entry.vendor_ids:
                    self._rows.append(IdentifierRow(listing.listing_id, SCHEME_VENDOR, vendor_id,
                                                    source_id, entry.valid_from, None, "register"))
                results.append(RegistrationResult(entry, resolution, True, listing.listing_id))
            else:
                results.append(RegistrationResult(entry, resolution, False, resolution.listing_id))
        return tuple(results)
