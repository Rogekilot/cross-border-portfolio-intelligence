"""F8-B: append a CONFIRMED split to the user's ledger (PD-0030 section 2; market-data/1.4 section 6, Rulings 6.4, 6.4a,
6.4b, 4.1, 4.8).

Positions take splits ONLY from ledger SPLIT events; the corporate-action feed never applies a split. This service is the
one place a split reaches the ledger without the user typing it, and only when the evidence is corroborated:

- CORROBORATION (Rulings 4.5, 4.1, 4.8): a corporate-action FEED record and an issuer FILING record (a file a human
  registered) for the same listing agree on the ex-date and, as an EXACT rational, on the ratio, AND come from DIFFERENT
  upstreams (C2-7: two renditions of one upstream are SAME_UPSTREAM, never corroboration). market-data 1.9 Ruling 4.8 item 4:
  corroboration happens WITHIN ONE WORLD: real feed + real filing (with the upstream test), or synthetic feed + synthetic filing
  (no upstream test); a mixed pair never corroborates. SYNTHETIC evidence NEVER causes an append (a ledger event is a canonical
  fact; C2-2), dry run or not: the outcome is NOT_RECORDED_APPEND_BARRED, and it DRIVES DETECTION AND SUPPRESSION exactly as real
  evidence does (suppression creates no fact, it only withholds a number). The append bar depends on the EVIDENCE, not on whether
  M holds other synthetic files. A record in only one role, or two that differ, is NOT corroborated:
  nothing is appended and the case is reported (F8-A detection). Which sources are feeds and which are filings is
  configuration the caller supplies (`ConfirmationPolicy`); nothing is inferred from a source's name.
- LINKING (Ruling 6.4a, C2-3): for a corroborated split K = (n, o) of listing l with ex-date X, the LINKING WINDOW W(K)
  runs from the 20th session before X to the 20th session after X, counted in the calendar governing the listing's MIC.
  For each account holding units at the START of X (replay at the previous day, at the current ledger version) the
  candidates are the account's live ledger SPLITs of l dated inside W(K). The outcome depends only on the ledger and the
  release, never on the date range the caller asked about (the corroborated splits of the WHOLE release are used to
  place the windows; the caller's range only chooses which splits are acted on):

      no candidate                                  NOT_RECORDED   -> append SPLIT (n, o) dated X (unless 6.4b)
      one, dated X, equal ratio                     MATCHED        -> nothing (the decision is ALREADY_RECORDED)
      one, equal ratio, dated Y != X                CONFLICT_DATE  -> nothing; suppressed over [min(X,Y), max(X,Y))
      a different ratio, or two or more             CONFLICT_RATIO -> nothing; suppressed from min(X, earliest)
      two corroborated splits whose windows         CONFLICT_RATIO (BOTH splits), whatever the ledger holds ->
        overlap (C2-15; 6.4a items 5 and 6)         nothing appended; suppressed from the earlier ex-date
      window not covered by the calendar            CALENDAR_COVERAGE_GAP -> nothing appended; INSUFFICIENT_DATA
                                                    from X with NO reason code (Ruling 5.3)

  A ledger split inside NO window is only flagged in lineage (`UNCORROBORATED_LEDGER_SPLIT`) and changes no state,
  whatever its ratio (Ruling 6.4 item 4). A CONFLICT is not repaired and not appended over: valuation of the position
  is suppressed and flagged (`ValuationSuppression`, reason SOURCE_CONFLICT); the quantity itself stays the ledger fact.
  An appended event goes through `persistence.ledger_store.append_system_event`, so it is idempotent on
  (account, source_reference), refused as a second live split on one day (migration 0007), reversible by the user with
  REVERSAL, never an update.
- USER REVERSAL IS FINAL FOR ITS WINDOW (Ruling 6.4b, C2-10): when the user reverses a split THIS SERVICE appended, the
  service never appends for the same (account, listing) with a date inside the reversed event's window, under any later
  ledger version or release. The outcome is NOT_RECORDED, valuation is suppressed from X, and the lineage cause is
  SYSTEM_SPLIT_REVERSED_BY_USER, until the user records the split themselves. A corroborated split whose window does not
  contain the reversed event's date is a different event and follows the normal rule.
- PROVENANCE (PD-0030 section 2: attributable and distinguishable from a user-entered event). The event's
  `source_reference` is a fixed, ASCII, bounded string that names the evidence and the market-data version:

      finweb.f8b/1;md=<convention set id>;rel=<release id>;feed=<file sha256>[+...];filing=<file sha256>[+...];
      ex=<YYYY-MM-DD>;ratio=<new>/<old>

  (one line, no spaces). `finweb.f8b/1` marks a system-appended event. C2-8: it cannot be forged by a user entry: the
  ledger's ordinary append paths REFUSE any reference in the reserved `finweb.` namespace (`ledger_store`), and a
  service that recognises its own events (`is_system_event`) additionally requires the strict reference grammar
  (no duplicate or extra key, bounded length) and the DETERMINISTIC event id of (account, reference).
  The string is parsed back by `parse_source_reference`. It is checked against the ledger's constraints (non-blank, not
  whitespace-only, no NUL, and far below the unique index's entry limit) and is REFUSED, never truncated, if it would
  exceed `MAX_SOURCE_REFERENCE_CHARS`. The `event_id` is a UUIDv5 of (account, source_reference), so the same evidence
  in the same release is the same event: an identical re-run changes nothing.

Deterministic: no clock, no randomness; the same ledger, release, calendars and policy give the same report and events.
The run is not one transaction: each append is atomic and independent, and every one is idempotent, so a run that stops
half way is finished by running it again.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime
import re
import uuid
from dataclasses import dataclass
from enum import Enum, unique
from fractions import Fraction
from typing import Any, Callable, Dict, FrozenSet, Iterable, Iterator, List, Mapping, Optional, Protocol, Sequence, Tuple

from domain.currency import CurrencyCode
from domain.ledger import EventType, LedgerEvent, SplitRatio
from domain.replay import AccountStatus, SequencedEvent, reconstruct
from marketdata.calendars import CalendarSet, SessionWindow
from marketdata.canonical import canonical_decimal
from marketdata.contracts import CorporateActionObservation, CorporateActionType, SourceReading
from marketdata.manifest import MarketDataRelease
from persistence import ledger_replay_store, ledger_store
from persistence.ledger_store import AppendResult, SameDaySplitError
from product_contract.vocabulary import ReasonCode

PREFIX = "finweb.f8b/1"
#: The namespace of the deterministic event ids (a UUIDv5 of a fixed name: no randomness, no clock).
EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "urn:finweb:f8b:1")
#: A system-written reference this long is refused, not truncated. The ledger's unique index on
#: (account_id, source_reference) has an entry limit of about 2.7 KB; this bound is well below it and above any
#: reference this service writes for a handful of evidence files.
MAX_SOURCE_REFERENCE_CHARS = 1024
#: Ruling 6.4a item 1: the linking window is 20 sessions on each side of the ex-date (a written convention, like the
#: freshness thresholds; the Quant's number, not this module's).
WINDOW_SESSIONS = 20
_ALPHABET = re.compile(r"^[A-Za-z0-9._/;=:+\-]+$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_KEYS = ("md", "rel", "feed", "filing", "ex", "ratio")

UNCORROBORATED_LEDGER_SPLIT = "UNCORROBORATED_LEDGER_SPLIT"
CALENDAR_COVERAGE_GAP = "CALENDAR_COVERAGE_GAP"
SYSTEM_SPLIT_REVERSED_BY_USER = "SYSTEM_SPLIT_REVERSED_BY_USER"
SPLIT_NOT_APPLIED = "SPLIT_NOT_APPLIED"  # CP3a dry-run: a corroborated split the ledger does not hold yet
SYNTHETIC_EVIDENCE_APPEND_BARRED = "SYNTHETIC_EVIDENCE_APPEND_BARRED"  # market-data 1.9 Ruling 4.8 item 4(b)


class SourceReferenceError(ValueError):
    """The provenance string would break a ledger constraint (blank, a character outside the fixed alphabet, or too
    long) and is refused rather than altered."""


class ReleaseMismatchError(ValueError):
    """The market-data port is not bound to the release it claims."""


# --- configuration and results ----------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfirmationPolicy:
    """Which registered sources are corporate-action FEEDS and which are issuer FILINGS (a human registered those
    files). Both are required for corroboration; the sets must not overlap."""

    feed_sources: FrozenSet[str]
    filing_sources: FrozenSet[str]

    def __post_init__(self) -> None:
        if not self.feed_sources or not self.filing_sources:
            raise ValueError("a confirmation policy needs at least one feed source and one filing source")
        if self.feed_sources & self.filing_sources:
            raise ValueError("a source cannot be both a feed and a filing")


@unique
class Corroboration(Enum):
    CORROBORATED = "CORROBORATED"
    FEED_ONLY = "FEED_ONLY"
    FILING_ONLY = "FILING_ONLY"
    DISAGREEMENT = "DISAGREEMENT"  # the feed and the filing differ, or readings within one role differ
    SYNTHETIC_MIXED = "SYNTHETIC_MIXED"  # Ruling 4.8: synthetic data never meets real data (a mixed pair never corroborates)
    SAME_UPSTREAM = "SAME_UPSTREAM"  # C2-7, Ruling 4.1: feed and filing share an upstream: not corroboration


@dataclass(frozen=True)
class SplitFinding:
    """What the evidence says about one split of one listing. `ratio` is the filing's own form of the ratio when
    CORROBORATED, else None."""

    listing_id: uuid.UUID
    ex_date: datetime.date
    status: Corroboration
    ratio: Optional[SplitRatio]
    feed_files: Tuple[str, ...]
    filing_files: Tuple[str, ...]
    detail: str
    synthetic: bool = False  # market-data 1.9 Ruling 4.8 item 4: both records are SYNTHETIC (corroboration happens within one world)


@unique
class SplitDecision(Enum):
    APPENDED = "APPENDED"
    ALREADY_RECORDED = "ALREADY_RECORDED"  # Ruling 6.4a MATCHED (also: this very evidence was recorded by an earlier run)
    CONFLICT_RATIO = "CONFLICT_RATIO"
    CONFLICT_DATE = "CONFLICT_DATE"
    REVERSED_BY_USER = "REVERSED_BY_USER"  # Ruling 6.4b: NOT_RECORDED, cause SYSTEM_SPLIT_REVERSED_BY_USER
    CALENDAR_COVERAGE_GAP = "CALENDAR_COVERAGE_GAP"  # Ruling 6.4a item 1: the window cannot be evaluated
    POSITION_UNKNOWN = "POSITION_UNKNOWN"
    NOT_HELD = "NOT_HELD"
    WOULD_APPEND = "WOULD_APPEND"  # dry-run only (CP3a): the split would be appended; nothing was written
    # market-data 1.9 Ruling 4.8 item 4(b): the split is corroborated by SYNTHETIC evidence. NOT_RECORDED, append barred: synthetic evidence never causes an append
    # (to any ledger, dry run or not). It drives detection and suppression exactly as real evidence does.
    NOT_RECORDED_APPEND_BARRED = "NOT_RECORDED_APPEND_BARRED"


@dataclass(frozen=True)
class AccountOutcome:
    """`linking` is Ruling 6.4a's own word for the outcome: MATCHED, CONFLICT_DATE, CONFLICT_RATIO, NOT_RECORDED or
    CALENDAR_COVERAGE_GAP (None where linking did not run: not held, position unknown). `cause` is a lineage cause."""

    account_id: uuid.UUID
    listing_id: uuid.UUID
    ex_date: datetime.date
    decision: SplitDecision
    event_id: Optional[uuid.UUID]  # the event appended, or the existing one the decision refers to
    source_reference: Optional[str]
    ledger_date: Optional[datetime.date]  # CONFLICT_DATE: the date the user's split carries
    detail: str
    linking: Optional[str] = None
    cause: Optional[str] = None
    suppress_from: Optional[datetime.date] = None  # C2-15: the earlier ex-date of an overlapping pair


@dataclass(frozen=True)
class ValuationSuppression:
    """Ruling 6.4 item 2 / 6.4a: the valuation of (quantity x RAW price) for this position is INSUFFICIENT_DATA for every
    date D with `first_date <= D < end_exclusive` (None: open-ended), because quantity and price are in different
    units there. The replayed quantity itself is still reported. `reason_code` is SOURCE_CONFLICT, except for a
    calendar coverage gap, which is a configuration defect and carries NO reason code (Ruling 5.3)."""

    account_id: uuid.UUID
    listing_id: uuid.UUID
    first_date: datetime.date
    end_exclusive: Optional[datetime.date]
    reason_code: Optional[ReasonCode]
    flag: str
    # market-data 1.9 Ruling 6.4c: the corroborated split `K` this suppression belongs to (its ex-date) and the decision that produced it, so a consumer can
    # carry the suppression with units moved by an internal transfer (CONFLICT_DATE with Y < X ends at X; everything else is open-ended).
    ex_date: Optional[datetime.date] = None
    decision: Optional[str] = None

    def covers(self, day: datetime.date) -> bool:
        return self.first_date <= day and (self.end_exclusive is None or day < self.end_exclusive)


@dataclass(frozen=True)
class LineageFlag:
    """A flag for lineage that changes no state (Ruling 6.4 item 4 / 6.4a item 4)."""

    account_id: uuid.UUID
    listing_id: uuid.UUID
    event_id: uuid.UUID
    event_date: datetime.date
    flag: str
    detail: str


@dataclass(frozen=True)
class SplitReport:
    release_id: str
    convention_set_id: str
    ledger_version_before: int
    ledger_version_after: int
    findings: Tuple[SplitFinding, ...]
    outcomes: Tuple[AccountOutcome, ...]
    suppressions: Tuple[ValuationSuppression, ...]
    lineage_flags: Tuple[LineageFlag, ...] = ()

    def suppressed_on(self, account_id: uuid.UUID, listing_id: uuid.UUID,
                      day: datetime.date) -> Optional[ValuationSuppression]:
        for s in self.suppressions:
            if s.account_id == account_id and s.listing_id == listing_id and s.covers(day):
                return s
        return None


# --- the ledger, as the service needs it -----------------------------------------------------------------------

class LedgerAccess(Protocol):
    def load(self, portfolio_id: uuid.UUID) -> Tuple[int, Tuple[SequencedEvent, ...]]:
        """(the portfolio's current committed ledger version L, its events with ledger_seq <= L)."""

    def append(self, event: LedgerEvent) -> AppendResult:
        """Append a SYSTEM event through the ledger's own path (idempotent, guarded)."""

    def atomic(self, portfolio_id: uuid.UUID) -> Any:
        """A context manager: everything the run loads and appends inside it is ONE unit, under the portfolio's ledger lock where the store has one. An exception leaves the ledger exactly as it was
        before the run (CP4-6: an F8-B run is all or nothing, Ruling 6.4d item 5). A read-only access returns a no-op manager."""


class PostgresLedgerAccess:
    """The real ledger: `persistence.ledger_replay_store` for reads and `persistence.ledger_store.append_system_event`
    for writes (the one append path that accepts the reserved `finweb.f8b/1` reference, C2-8), over a psycopg
    connection. The application role needs only the grants of tech plan 14.3 (SELECT and INSERT on ledger_event,
    SELECT on account and portfolio, USAGE on the sequence)."""

    def __init__(self, conn: Any):
        self._conn = conn

    def load(self, portfolio_id: uuid.UUID) -> Tuple[int, Tuple[SequencedEvent, ...]]:
        version = ledger_replay_store.current_ledger_version(self._conn, portfolio_id)
        return version, ledger_replay_store.load_events(self._conn, portfolio_id, version)

    def append(self, event: LedgerEvent) -> AppendResult:
        return ledger_store.append_system_event(self._conn, event, namespace=PREFIX)

    def ledger_schema(self) -> str:
        """The schema of the table the append trigger fires on, found FROM THE TRIGGER ITSELF (`ledger_event_before_insert` on `ledger_event`, among the non-temporary schemas of the search path), the
        value the trigger's own lock key uses (`TG_TABLE_SCHEMA`, migration 0008), so the lock here and the lock there can never name different schemas (a TEMP shadow is excluded by its schema name,
        `pg_temp*`, not because it could not carry a trigger; two candidate schemas fail closed rather than guess, since the insert goes to the first and the lock must name the same one)."""
        rows = self._conn.execute(
            "SELECT DISTINCT n.nspname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE t.tgname = 'ledger_event_before_insert' AND c.relname = 'ledger_event' AND n.nspname = ANY (current_schemas(false)) "
            "AND n.nspname NOT LIKE 'pg\\_temp%' AND n.nspname NOT LIKE 'pg\\_toast\\_temp%'").fetchall()
        if len(rows) != 1:
            raise RuntimeError(f"cannot say which schema holds the ledger's append trigger ({len(rows)} candidate(s)): nothing is locked or appended")
        return str(rows[0][0])

    @contextlib.contextmanager
    def atomic(self, portfolio_id: uuid.UUID) -> Iterator[None]:
        """ONE transaction for the whole run (a savepoint if the caller holds one), with the portfolio's ledger advisory lock taken FIRST (the same key the append trigger takes, migration 0008), so
        the loads the run reads and the events it appends are one consistent unit: no concurrent writer can name a new listing mid-run, and any exception rolls back every append of the run."""
        with self._conn.transaction():
            schema = self.ledger_schema()
            self._conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"finweb.ledger.portfolio:{schema}:{portfolio_id}",))
            yield


class ReleasePort(Protocol):
    """What the service reads from a market-data store: the corporate-action readings, and the release it is bound
    to (both `InMemoryMarketData` and `PostgresMarketData` have these)."""

    release: MarketDataRelease

    @property
    def contains_synthetic(self) -> bool: ...

    def release_id(self) -> str: ...

    def corporate_actions(self, listing_id: uuid.UUID, start: datetime.date, end: datetime.date) -> Any: ...


# --- provenance ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SplitProvenance:
    convention_set_id: str
    release_id: str
    feed_files: Tuple[str, ...]
    filing_files: Tuple[str, ...]
    ex_date: datetime.date
    ratio: Tuple[str, str]  # (new, old) as canonical decimal text


def _ratio_text(ratio: SplitRatio) -> Tuple[str, str]:
    return canonical_decimal(ratio.new_units), canonical_decimal(ratio.old_units)


def build_source_reference(
    convention_set_id: str, release_id: str, feed_files: Sequence[str], filing_files: Sequence[str],
    ex_date: datetime.date, ratio: SplitRatio,
) -> str:
    """The provenance string of a system-appended split (see the module docstring). Refused, never altered, when it
    would break a ledger constraint."""
    for sha in tuple(feed_files) + tuple(filing_files) + (release_id,):
        if not _SHA.match(sha):
            raise SourceReferenceError(f"{sha!r} is not a SHA-256 hex digest")
    if not feed_files or not filing_files:
        raise SourceReferenceError("evidence needs at least one feed file and one filing file")
    new, old = _ratio_text(ratio)
    text = (f"{PREFIX};md={convention_set_id};rel={release_id};feed={'+'.join(sorted(set(feed_files)))};"
            f"filing={'+'.join(sorted(set(filing_files)))};ex={ex_date.isoformat()};ratio={new}/{old}")
    check_source_reference(text)
    return text


def check_source_reference(text: str) -> None:
    """The ledger's constraints on `source_reference`, restated for a SYSTEM-written one: non-blank (and not
    whitespace-only, which the database also refuses), no NUL, a fixed ASCII alphabet (so no character can be
    mis-stored or mis-compared), and no longer than `MAX_SOURCE_REFERENCE_CHARS` (far below the btree entry limit of
    the unique index on (account_id, source_reference): a longer one would fail as an untyped index error)."""
    if not text or not text.strip():
        raise SourceReferenceError("source_reference must not be blank")
    if len(text) > MAX_SOURCE_REFERENCE_CHARS:
        raise SourceReferenceError(
            f"source_reference is {len(text)} characters, over the {MAX_SOURCE_REFERENCE_CHARS} limit: too much "
            "evidence for one event; it is refused rather than truncated")
    if not _ALPHABET.match(text):
        raise SourceReferenceError("source_reference may contain only letters, digits and . _ / ; = : + -")


def parse_source_reference(text: Optional[str]) -> Optional[SplitProvenance]:
    """The provenance of a system-appended split, or None for any other reference (a user-entered event).

    C2-8: the grammar is STRICT. Exactly the keys `md, rel, feed, filing, ex, ratio`, once each and in that order
    (a duplicate key is not 'last wins': it is not a system reference), the whole string within the length bound and
    the fixed alphabet, every hash a SHA-256 hex digest, the date an ISO date, the ratio two positive decimals."""
    if text is None or not text.startswith(PREFIX + ";") or len(text) > MAX_SOURCE_REFERENCE_CHARS:
        return None
    try:
        check_source_reference(text)
        pairs = [p.split("=", 1) for p in text.split(";")[1:]]
        if [p[0] for p in pairs] != list(_KEYS) or any(len(p) != 2 for p in pairs):
            return None
        parts = {k: v for k, v in pairs}
        new, old = parts["ratio"].split("/")
        feed, filing = tuple(parts["feed"].split("+")), tuple(parts["filing"].split("+"))
        if not all(_SHA.match(s) for s in feed + filing + (parts["rel"],)) or not parts["md"]:
            return None
        if Fraction(new) <= 0 or Fraction(old) <= 0:
            return None
        return SplitProvenance(parts["md"], parts["rel"], feed, filing,
                               datetime.date.fromisoformat(parts["ex"]), (new, old))
    except (KeyError, ValueError, SourceReferenceError, ZeroDivisionError):
        return None


def event_id_for(account_id: uuid.UUID, source_reference: str) -> uuid.UUID:
    """Deterministic: the same evidence for the same account is the same event."""
    return uuid.uuid5(EVENT_NAMESPACE, f"{account_id}|{source_reference}")


def is_system_event(event: LedgerEvent) -> bool:
    """True only for a split this service wrote (C2-8): the strict reference grammar, AND the deterministic event id
    of (account, reference), AND a date and ratio that agree with the reference. A user entry that merely imitates
    the marker is not one: the ledger refuses the marker on every ordinary path, and this test does not take the
    string at its word either."""
    prov = parse_source_reference(event.source_reference)
    if (prov is None or event.event_type is not EventType.SPLIT or event.split_ratio is None
            or event.source_reference is None):
        return False
    return (event.event_id == event_id_for(event.account_id, event.source_reference)
            and event.event_date == prov.ex_date
            and _ratio_text(event.split_ratio) == prov.ratio)


# --- corroboration ---------------------------------------------------------------------------------------------

def _ratio_of(obs: CorporateActionObservation) -> Fraction:
    assert obs.split_ratio is not None
    return Fraction(obs.split_ratio.new_units) / Fraction(obs.split_ratio.old_units)


def corroborate(
    listing_id: uuid.UUID, readings: Iterable[SourceReading], policy: ConfirmationPolicy,
) -> Tuple[SplitFinding, ...]:
    """One finding per ex-date of `listing_id`'s SPLIT readings (Ruling 4.5): a feed record and a filing record that
    agree on the ex-date and, as an exact rational, on the ratio, from different upstreams (Ruling 4.1), and not
    synthetic (Ruling 4.8). Pure."""
    by_date: Dict[datetime.date, List[SourceReading]] = {}
    for r in readings:
        obs = r.observation
        if (isinstance(obs, CorporateActionObservation) and obs.action_type is CorporateActionType.SPLIT
                and obs.listing_id == listing_id and r.source_id in (policy.feed_sources | policy.filing_sources)):
            by_date.setdefault(obs.effective_date, []).append(r)
    findings: List[SplitFinding] = []
    for day in sorted(by_date):
        group = sorted(by_date[day], key=lambda r: (r.source_id, r.file_sha256))
        feed = [r for r in group if r.source_id in policy.feed_sources]
        filing = [r for r in group if r.source_id in policy.filing_sources]
        feed_files = tuple(sorted({r.file_sha256 for r in feed}))
        filing_files = tuple(sorted({r.file_sha256 for r in filing}))

        def finding(status: Corroboration, detail: str, ratio: Optional[SplitRatio] = None,
                    synthetic: bool = False) -> SplitFinding:
            return SplitFinding(listing_id, day, status, ratio, feed_files, filing_files, detail, synthetic)

        if not feed or not filing:
            only = Corroboration.FEED_ONLY if feed else Corroboration.FILING_ONLY
            findings.append(finding(only, "a record in one of the two sources only: SINGLE_SOURCE, never appended"))
            continue
        synthetic_flags = {r.observation.lineage.is_synthetic for r in group}  # type: ignore[attr-defined]
        if len(synthetic_flags) > 1:
            findings.append(finding(Corroboration.SYNTHETIC_MIXED,
                                    "synthetic and real records never meet (Ruling 4.8): not corroborated"))
            continue
        is_synthetic = synthetic_flags == {True}
        # Ruling 4.8 item 4(a): two SYNTHETIC records corroborate within their own world; the independence test of Ruling 4.1 does not apply to them (both are
        # upstream `synthetic`; the fixture author declares them the feed and the filing). Real records still need different upstreams.
        if not is_synthetic and {r.independence_group for r in feed} & {r.independence_group for r in filing}:
            findings.append(finding(Corroboration.SAME_UPSTREAM,
                                    "the feed and the filing share an upstream: two renditions of one upstream are "
                                    "not corroboration (Ruling 4.1); never appended"))
            continue
        ratios = {_ratio_of(r.observation) for r in group}  # type: ignore[arg-type]
        if len(ratios) != 1:
            findings.append(finding(Corroboration.DISAGREEMENT,
                                    "the records differ in ratio (as exact rationals): a disputed split is never "
                                    "appended"))
            continue
        chosen = filing[0].observation  # the issuer's own form of the ratio (first by source, then file hash)
        assert isinstance(chosen, CorporateActionObservation) and chosen.split_ratio is not None
        findings.append(finding(Corroboration.CORROBORATED,
                                ("a synthetic feed record and a synthetic filing agree on the ex-date and the exact ratio "
                                 "(Ruling 4.8 item 4): they drive detection and suppression, never an append")
                                if is_synthetic else
                                "a feed record and an issuer filing from different upstreams agree on the ex-date and the "
                                "exact ratio", chosen.split_ratio, is_synthetic))
    return tuple(findings)


# --- the confirmation-policy test (market-data/1.11 Ruling 6.4d) --------------------------------------------------

@dataclass(frozen=True)
class UnmatchedKey:
    """One (listing, ex-date) key the policy does not classify (Ruling 6.4d item 6)."""

    listing: uuid.UUID
    ex_date: datetime.date
    unclassified_sources: Tuple[str, ...]  # sorted: the sources with a SPLIT record for the key that are named in neither role
    unmatched_roles: Tuple[str, ...]  # a subset of ("feed", "filing"), in that order: the roles with no source among the key's records (empty in case (c))

    def as_object(self) -> Dict[str, Any]:
        return {"listing": str(self.listing), "ex_date": self.ex_date.isoformat(), "unclassified_sources": list(self.unclassified_sources),
                "unmatched_roles": list(self.unmatched_roles)}


class DetectionPolicyUnmatchedError(ValueError):
    """The F8-B append run is refused (Ruling 6.4d item 5): a key is unmatched, so NOTHING is appended: the run is atomic (`LedgerAccess.atomic`), so any append an earlier finding made
    in this run is rolled back with it (CP4-6). `keys` names every one."""

    def __init__(self, keys: Sequence[UnmatchedKey]):
        self.keys = tuple(keys)
        super().__init__("DETECTION_POLICY_UNMATCHED: " + "; ".join(
            f"listing {k.listing} ex-date {k.ex_date.isoformat()} unclassified {list(k.unclassified_sources)} unmatched roles {list(k.unmatched_roles)}" for k in self.keys))


def unmatched_policy_keys(listing_ids: Iterable[uuid.UUID], readings_of: Callable[[uuid.UUID], Iterable[SourceReading]],
                          policy: ConfirmationPolicy) -> Tuple[UnmatchedKey, ...]:
    """Ruling 6.4d. For each listing and each ex-date `X` on which the readings hold a `SPLIT` record of the listing (EXACT date equality, real or synthetic, no window), let `S` be the sources with a
    record for the key and `U` those named in neither role: the key is UNMATCHED iff `U` is not empty (the reviewer's role-less case, the only-unclassified case, and case (c), where both roles are
    matched and an unclassified source holds a record too). A key whose sources are all classified is never unmatched, even `FEED_ONLY` or `FILING_ONLY` (SINGLE_SOURCE: silence is correct). Every
    unmatched key is returned, ordered by (listing id as text, ex-date). Pure. (A policy with an empty role or a source in both is refused when it is built: `ConfirmationPolicy.__post_init__`.)"""
    named = set(policy.feed_sources) | set(policy.filing_sources)
    out: List[UnmatchedKey] = []
    for listing in sorted(set(listing_ids), key=str):
        by_date: Dict[datetime.date, set] = {}
        for r in readings_of(listing):
            obs = r.observation
            if isinstance(obs, CorporateActionObservation) and obs.action_type is CorporateActionType.SPLIT and obs.listing_id == listing:
                by_date.setdefault(obs.effective_date, set()).add(r.source_id)
        for day in sorted(by_date):
            present = by_date[day]
            unclassified = present - named
            if unclassified:
                roles = tuple(role for role, sources in (("feed", policy.feed_sources), ("filing", policy.filing_sources)) if not (present & set(sources)))
                out.append(UnmatchedKey(listing, day, tuple(sorted(unclassified)), roles))
    return tuple(out)


# --- the service -----------------------------------------------------------------------------------------------

def _live_splits(events: Sequence[SequencedEvent], account_id: uuid.UUID,
                 listing_id: uuid.UUID) -> Tuple[List[LedgerEvent], List[LedgerEvent]]:
    """(live SPLIT events, REVERSED SPLIT events) of one position, from the events at the ledger version."""
    reversed_ids = {se.event.reverses_event_id for se in events if se.event.event_type is EventType.REVERSAL}
    live: List[LedgerEvent] = []
    gone: List[LedgerEvent] = []
    for se in events:
        e = se.event
        if e.event_type is EventType.SPLIT and e.account_id == account_id and e.listing_id == listing_id:
            (gone if e.event_id in reversed_ids else live).append(e)
    return live, gone


def _fraction(r: SplitRatio) -> Fraction:
    return Fraction(r.new_units) / Fraction(r.old_units)


def _eq(a: SplitRatio, b: SplitRatio) -> bool:
    return _fraction(a) == _fraction(b)


def confirm_splits(
    access: LedgerAccess,
    port: ReleasePort,
    portfolio_id: uuid.UUID,
    listing_ids: Iterable[uuid.UUID],
    start: datetime.date,
    end: datetime.date,
    policy: ConfirmationPolicy,
    trading_currency: Mapping[uuid.UUID, CurrencyCode],
    *,
    calendars: CalendarSet,
    exchange_of: Callable[[uuid.UUID], Optional[str]],
    dry_run: bool = False,
) -> SplitReport:
    """ALL OR NOTHING (CP4-6; Ruling 6.4d item 5): the run executes inside `access.atomic(portfolio_id)`, one unit under the portfolio's ledger lock. A refusal, or any other exception, leaves the
    ledger exactly as it was before the run. An access that cannot run atomically is refused (no other design is chosen). See `_confirm_splits` for the rules."""
    atomic = getattr(access, "atomic", None)
    if atomic is None:
        raise TypeError("the ledger access has no `atomic(portfolio_id)`: an F8-B run is all or nothing, and nothing is appended through an access that cannot say so")
    with atomic(portfolio_id):
        return _confirm_splits(access, port, portfolio_id, listing_ids, start, end, policy, trading_currency, calendars=calendars, exchange_of=exchange_of, dry_run=dry_run)


def _confirm_splits(
    access: LedgerAccess,
    port: ReleasePort,
    portfolio_id: uuid.UUID,
    listing_ids: Iterable[uuid.UUID],
    start: datetime.date,
    end: datetime.date,
    policy: ConfirmationPolicy,
    trading_currency: Mapping[uuid.UUID, CurrencyCode],
    *,
    calendars: CalendarSet,
    exchange_of: Callable[[uuid.UUID], Optional[str]],
    dry_run: bool = False,
) -> SplitReport:
    """DETECT-AND-REPORT MODE (CP3a; PM ruling: a performance computation never writes the ledger): with
    `dry_run=True` the whole decision runs unchanged but `access.append` is NEVER called. Where the normal run would
    append, the outcome is `WOULD_APPEND` and valuation of that position is suppressed from the ex-date (quantity and
    price would be in different units), so the report can be handed to a read. The default (`dry_run=False`) is the
    unchanged append path.

    Append the corroborated splits of `listing_ids` with ex-dates in `[start, end]` that a portfolio's accounts
    are missing (see the module docstring). `trading_currency` gives each listing's currency (a ledger event
    carries one, also a SPLIT). `calendars` and `exchange_of` (the listing's MIC) place the Ruling 6.4a linking
    windows; they are required, because without them no window can be evaluated and nothing may be appended.
    Returns what was found, decided, appended, suppressed and flagged."""
    release = port.release
    if release.release_id != port.release_id():
        raise ReleaseMismatchError("the port is not bound to the release it reports")
    listings = sorted(set(listing_ids), key=str)

    # Ruling 6.4d: the policy must classify every SPLIT record of every listing the ledger names (live or reversed), per (listing, ex-date). Any unmatched key refuses the whole run: NOTHING is
    # appended (the run is atomic: `confirm_splits` wraps this body in `access.atomic`, so an earlier append of this run is rolled back too).
    # CP4-1: the test and the decisions must read the SAME ledger, so the test is applied to EVERY load a decision reads (below), over the listings that load names and no earlier test covered
    # (M is fixed for the run, so a listing already tested stays tested). Under the portfolio lock a writer cannot add a listing mid-run; an access without a lock still gets the per-load test.
    tested: set = set()

    def require_policy_matched(version: int, loaded: Sequence[SequencedEvent]) -> None:
        named = {s.event.listing_id for s in loaded if s.event.listing_id is not None and s.ledger_seq <= version}
        keys = unmatched_policy_keys(named - tested, lambda l: port.corporate_actions(l, datetime.date.min, datetime.date.max).readings, policy)
        if keys:
            raise DetectionPolicyUnmatchedError(keys)
        tested.update(named)

    ledger_version, ledger_events = access.load(portfolio_id)
    require_policy_matched(ledger_version, ledger_events)

    # every corroborated split of each listing in the WHOLE release places the windows (C2-3: the caller's range
    # must not change the outcome); the range only chooses which splits are acted on
    all_findings: Dict[uuid.UUID, List[SplitFinding]] = {}
    for listing_id in listings:
        actions = port.corporate_actions(listing_id, datetime.date.min, datetime.date.max)
        # market-data 1.9 Ruling 4.8 item 4(d): the append bar depends on the EVIDENCE (a finding's `synthetic` flag), NOT on whether M holds some other synthetic
        # file: the old rewrite of every finding to SYNTHETIC_EVIDENCE because M held any synthetic file is gone.
        all_findings[listing_id] = list(corroborate(listing_id, actions.readings, policy))

    windows: Dict[Tuple[uuid.UUID, datetime.date], SessionWindow] = {}
    for listing_id, found in all_findings.items():
        for f in found:
            if f.status is Corroboration.CORROBORATED:
                windows[(listing_id, f.ex_date)] = calendars.session_window(
                    exchange_of(listing_id), f.ex_date, WINDOW_SESSIONS)

    findings = sorted((f for fs in all_findings.values() for f in fs if start <= f.ex_date <= end),
                      key=lambda f: (f.ex_date, str(f.listing_id)))
    version_before, _ = access.load(portfolio_id)
    outcomes: List[AccountOutcome] = []
    suppressions: List[ValuationSuppression] = []
    for f in findings:
        if f.status is not Corroboration.CORROBORATED or f.ratio is None:
            continue
        version, events = access.load(portfolio_id)  # fresh: an earlier append is part of the ledger now
        require_policy_matched(version, events)  # CP4-1: this load is the one the decision below acts on, so it is the one tested (nothing is appended for this finding if a new listing is unmatched)
        state = reconstruct(events, f.ex_date - datetime.timedelta(days=1), version)
        partners = _pair_partners(f, all_findings, windows, calendars, exchange_of)
        pair_accounts = _pair_accounts(events, version, f, partners) if partners else frozenset()
        for account in state.accounts:
            if account.account_id in pair_accounts:
                outcome = _pair_outcome(account.account_id, f, partners)
                outcomes.append(outcome)
                suppression = _suppression_for(outcome, f)
                if suppression is not None:
                    suppressions.append(suppression)
                continue
            held = _held_state(account, f.listing_id)
            if held == "NOT_HELD":
                outcomes.append(AccountOutcome(account.account_id, f.listing_id, f.ex_date, SplitDecision.NOT_HELD, None,
                                               None, None, "no units held at the start of the ex-date"))
                continue
            if held == "UNKNOWN":
                outcomes.append(AccountOutcome(
                    account.account_id, f.listing_id, f.ex_date, SplitDecision.POSITION_UNKNOWN, None, None, None,
                    "the position at the start of the ex-date is flagged (not a reliable quantity): nothing appended"))
                continue
            outcome = _decide_and_append(access, portfolio_id, account.account_id, f, release, port,
                                         windows[(f.listing_id, f.ex_date)], trading_currency, dry_run)
            outcomes.append(outcome)
            suppression = _suppression_for(outcome, f)
            if suppression is not None:
                suppressions.append(suppression)
    version_after, events_after = access.load(portfolio_id)
    flags = _uncorroborated_flags(events_after, listings, windows)
    return SplitReport(port.release_id(), release.convention_set_id, version_before, version_after, tuple(findings),
                       tuple(outcomes), tuple(suppressions), flags)


def _held_state(account: Any, listing_id: uuid.UUID) -> str:
    if account.status is AccountStatus.NOT_RECONSTRUCTABLE:
        return "NOT_HELD"  # before the account's snapshot: the snapshot already holds the post-split units
    for p in account.positions:
        if p.listing_id == listing_id:
            if p.quantity.value is None:
                return "UNKNOWN"
            return "HELD" if p.quantity.value != 0 else "NOT_HELD"
    return "NOT_HELD"


def _overlap(a: SessionWindow, b: SessionWindow) -> Optional[Tuple[datetime.date, datetime.date]]:
    assert a.start is not None and a.end is not None and b.start is not None and b.end is not None
    low, high = max(a.start, b.start), min(a.end, b.end)
    return (low, high) if low <= high else None


OVERLAPPING_SPLIT_WINDOWS = "OVERLAPPING_SPLIT_WINDOWS"


def _pair_partners(
    f: SplitFinding, all_findings: Mapping[uuid.UUID, Sequence[SplitFinding]],
    windows: Mapping[Tuple[uuid.UUID, datetime.date], SessionWindow], calendars: CalendarSet,
    exchange_of: Callable[[uuid.UUID], Optional[str]],
) -> List[Tuple[datetime.date, str]]:
    """Ruling 6.4a item 5 (1.6), decided from the WHOLE release's corroborated splits of the listing: the other splits
    that make a pair with `f`, as (ex-date, kind). OVERLAP: the two windows overlap (both evaluable and intersecting, or
    the calendar shows at most 40 sessions between the ex-dates). GAP: the calendar cannot cover both windows and cannot
    show them disjoint (more than 40 sessions apart), so the overlap cannot be decided. Disjoint pairs are not partners."""
    out: List[Tuple[datetime.date, str]] = []
    wf = windows[(f.listing_id, f.ex_date)]
    for g in all_findings[f.listing_id]:
        if g.status is not Corroboration.CORROBORATED or g.ex_date == f.ex_date:
            continue
        wg = windows[(f.listing_id, g.ex_date)]
        if wf.evaluable and wg.evaluable:
            if _overlap(wf, wg) is not None:
                out.append((g.ex_date, "OVERLAP"))
            continue
        low, high = sorted((f.ex_date, g.ex_date))
        between = calendars.count_after(exchange_of(f.listing_id), low, high).missed
        if between is None:
            out.append((g.ex_date, "GAP"))
        elif between <= 2 * WINDOW_SESSIONS:
            out.append((g.ex_date, "OVERLAP"))
    return out


def _pair_accounts(events: Sequence[SequencedEvent], version: int, f: SplitFinding,
                   partners: Sequence[Tuple[datetime.date, str]]) -> FrozenSet[uuid.UUID]:
    """Accounts with units in the listing at the start of the ex-date of `f` or of any partner (Ruling 6.4a item 5)."""
    held: List[uuid.UUID] = []
    for day in sorted({f.ex_date} | {ex for ex, _ in partners}):
        state = reconstruct(events, day - datetime.timedelta(days=1), version)
        held += [a.account_id for a in state.accounts if _held_state(a, f.listing_id) == "HELD"]
    return frozenset(held)


def _pair_outcome(account_id: uuid.UUID, f: SplitFinding, partners: Sequence[Tuple[datetime.date, str]]) -> AccountOutcome:
    overlap = [ex for ex, kind in partners if kind == "OVERLAP"]
    chosen = overlap if overlap else [ex for ex, _ in partners]
    earliest = min([f.ex_date] + chosen)
    if overlap:
        return AccountOutcome(
            account_id, f.listing_id, f.ex_date, SplitDecision.CONFLICT_RATIO, None, None, None,
            "this corroborated split's linking window overlaps that of another corroborated split of the listing (ex-dates "
            f"{', '.join(d.isoformat() for d in sorted(set(overlap + [f.ex_date])))}): neither is appended; valuation is "
            "suppressed from the earlier ex-date; a human decides", "CONFLICT_RATIO", OVERLAPPING_SPLIT_WINDOWS, earliest)
    return AccountOutcome(
        account_id, f.listing_id, f.ex_date, SplitDecision.CALENDAR_COVERAGE_GAP, None, None, None,
        "the calendar cannot cover both linking windows of two nearby corroborated splits, so their overlap cannot be "
        "decided: nothing is appended; valuation is INSUFFICIENT_DATA from the earlier ex-date with no reason code",
        CALENDAR_COVERAGE_GAP, CALENDAR_COVERAGE_GAP, earliest)


def _decide_and_append(
    access: LedgerAccess, portfolio_id: uuid.UUID, account_id: uuid.UUID, finding: SplitFinding,
    release: MarketDataRelease, port: ReleasePort, window: SessionWindow,
    trading_currency: Mapping[uuid.UUID, CurrencyCode], dry_run: bool = False,
) -> AccountOutcome:
    ratio = finding.ratio
    assert ratio is not None
    ref = build_source_reference(release.convention_set_id, port.release_id(), finding.feed_files,
                                 finding.filing_files, finding.ex_date, ratio)
    event_id = event_id_for(account_id, ref)
    base = dict(account_id=account_id, listing_id=finding.listing_id, ex_date=finding.ex_date)

    def outcome(decision: SplitDecision, event: Optional[uuid.UUID], detail: str,
                ledger_date: Optional[datetime.date] = None, source_reference: Optional[str] = ref,
                linking: Optional[str] = None, cause: Optional[str] = None,
                suppress_from: Optional[datetime.date] = None) -> AccountOutcome:
        return AccountOutcome(base["account_id"], base["listing_id"], base["ex_date"], decision, event,  # type: ignore[arg-type]
                              source_reference, ledger_date, detail, linking, cause, suppress_from)

    if not window.evaluable:
        # Ruling 6.4a item 1: linking cannot be evaluated; nothing is appended, nothing is guessed
        return outcome(SplitDecision.CALENDAR_COVERAGE_GAP, None,
                       "the calendar does not cover the linking window (" + "; ".join(window.notes) + "): nothing "
                       "appended; valuation is INSUFFICIENT_DATA from the ex-date with no reason code",
                       source_reference=None, linking=CALENDAR_COVERAGE_GAP, cause=CALENDAR_COVERAGE_GAP)

    # (Overlapping windows, Ruling 6.4a item 5, are decided BEFORE this function, per pair, in `_pair_partners`.)
    for _attempt in range(2):
        _, events = access.load(portfolio_id)
        live, gone = _live_splits(events, account_id, finding.listing_id)
        cands = sorted((s for s in live if window.contains(s.event_date)), key=lambda s: (s.event_date, str(s.event_id)))
        if len(cands) >= 2 or (len(cands) == 1 and cands[0].split_ratio is not None
                               and not _eq(cands[0].split_ratio, ratio)):
            return outcome(SplitDecision.CONFLICT_RATIO, cands[0].event_id,
                           "the ledger records a split with another ratio (or several) inside the linking window: "
                           "nothing appended; valuation is suppressed until the user corrects it",
                           cands[0].event_date, cands[0].source_reference, linking="CONFLICT_RATIO")
        if len(cands) == 1:
            s = cands[0]
            if s.event_date == finding.ex_date:
                return outcome(SplitDecision.ALREADY_RECORDED, s.event_id,
                               "an equal live split is already in the ledger: nothing appended",
                               source_reference=s.source_reference, linking="MATCHED")
            return outcome(SplitDecision.CONFLICT_DATE, s.event_id,
                           "the ledger records the same ratio on another date inside the linking window (a record or "
                           "pay date?): nothing appended; valuation is suppressed until the user corrects it",
                           s.event_date, s.source_reference, linking="CONFLICT_DATE")
        # no candidate: NOT_RECORDED. Ruling 6.4b: a split this service appended and the user reversed, dated inside
        # this window, is never appended again
        reversed_by_user = [s for s in gone if window.contains(s.event_date) and is_system_event(s)]
        if reversed_by_user:
            r = sorted(reversed_by_user, key=lambda s: (s.event_date, str(s.event_id)))[0]
            return outcome(SplitDecision.REVERSED_BY_USER, r.event_id,
                           "a split this service appended was reversed by the user: it is not appended again for "
                           "this window; the position is flagged 'corporate action not recorded' until the user "
                           "records the split", source_reference=r.source_reference, linking="NOT_RECORDED",
                           cause=SYSTEM_SPLIT_REVERSED_BY_USER)
        currency = trading_currency.get(finding.listing_id)
        if currency is None:
            raise ValueError(f"no trading currency for listing {finding.listing_id}: a ledger event carries one")
        event = LedgerEvent(
            event_id=event_id, account_id=account_id, event_type=EventType.SPLIT, event_date=finding.ex_date,
            currency=currency, listing_id=finding.listing_id, split_ratio=ratio, source_reference=ref)
        if finding.synthetic:  # Ruling 4.8 item 4(b): synthetic evidence NEVER causes an append, dry run or not; it still suppresses (item 4(c))
            return outcome(SplitDecision.NOT_RECORDED_APPEND_BARRED, event_id,
                           "the evidence is synthetic: NOT_RECORDED, append barred (Ruling 4.8 item 4); valuation is "
                           "suppressed from the ex-date exactly as for real evidence",
                           linking="NOT_RECORDED", cause=SYNTHETIC_EVIDENCE_APPEND_BARRED)
        if dry_run:  # detect-and-report: the append is NOT made (the caller's ledger is untouched)
            return outcome(SplitDecision.WOULD_APPEND, event_id,
                           "detect-only mode: a feed record and an issuer filing agree and the ledger lacks the split; "
                           "nothing was appended and valuation is suppressed from the ex-date until it is applied",
                           linking="NOT_RECORDED", cause=SPLIT_NOT_APPLIED)
        try:
            result = access.append(event)
        except SameDaySplitError:
            continue  # another writer recorded a split on that day between our read and our append: decide again
        if result.created:
            return outcome(SplitDecision.APPENDED, result.event.event_id,
                           "appended: a feed record and an issuer filing agree and the ledger lacked the split",
                           linking="NOT_RECORDED")
        # the key already existed (the same evidence, an earlier run): that event is the answer
        return outcome(SplitDecision.ALREADY_RECORDED, result.event.event_id,
                       "this evidence was already recorded: nothing appended", source_reference=ref, linking="MATCHED")
    raise ledger_store.LedgerStoreError("could not settle a split decision: the ledger kept changing")


def _suppression_for(outcome: AccountOutcome, finding: SplitFinding) -> Optional[ValuationSuppression]:
    """`_suppression_core` plus the split's ex-date and the decision (market-data 1.9 Ruling 6.4c)."""
    core = _suppression_core(outcome, finding)
    if core is None:
        return None
    return dataclasses.replace(core, ex_date=finding.ex_date, decision=outcome.decision.value)


def _suppression_core(outcome: AccountOutcome, finding: SplitFinding) -> Optional[ValuationSuppression]:
    """Ruling 6.4 item 2 / 6.4a, from the decision. The two CONFLICT decisions, a user reversal and a coverage gap
    suppress; MATCHED and an append do not."""
    x = finding.ex_date
    if outcome.decision is SplitDecision.CONFLICT_DATE and outcome.ledger_date is not None:
        y = outcome.ledger_date
        return ValuationSuppression(outcome.account_id, outcome.listing_id, min(x, y), max(x, y),
                                    ReasonCode.SOURCE_CONFLICT, "split dated off its ex-date")
    if outcome.decision is SplitDecision.CONFLICT_RATIO:
        first = x if outcome.ledger_date is None else min(x, outcome.ledger_date)  # Ruling 6.4a item 3
        if outcome.suppress_from is not None:  # C2-15: an overlapping pair is suppressed from the earlier ex-date
            first = min(first, outcome.suppress_from)
        flag = ("split recorded with a different ratio than the corroborated corporate action"
                if outcome.cause != OVERLAPPING_SPLIT_WINDOWS else
                f"{OVERLAPPING_SPLIT_WINDOWS}: two corroborated splits of the listing have overlapping linking windows")
        return ValuationSuppression(outcome.account_id, outcome.listing_id, first, None, ReasonCode.SOURCE_CONFLICT, flag)
    if outcome.decision is SplitDecision.REVERSED_BY_USER:
        return ValuationSuppression(outcome.account_id, outcome.listing_id, x, None, ReasonCode.SOURCE_CONFLICT,
                                    f"corporate action not recorded ({SYSTEM_SPLIT_REVERSED_BY_USER})")
    if outcome.decision is SplitDecision.WOULD_APPEND:  # dry-run only: the split is not in the ledger the read sees
        return ValuationSuppression(outcome.account_id, outcome.listing_id, x, None, ReasonCode.SOURCE_CONFLICT,
                                    f"corporate action not recorded ({SPLIT_NOT_APPLIED})")
    if outcome.decision is SplitDecision.NOT_RECORDED_APPEND_BARRED:  # synthetic evidence: no append, the same suppression (Ruling 4.8 item 4(c))
        return ValuationSuppression(outcome.account_id, outcome.listing_id, x, None, ReasonCode.SOURCE_CONFLICT,
                                    f"corporate action not recorded ({SPLIT_NOT_APPLIED}; {SYNTHETIC_EVIDENCE_APPEND_BARRED})")
    if outcome.decision is SplitDecision.CALENDAR_COVERAGE_GAP:
        first = x if outcome.suppress_from is None else min(x, outcome.suppress_from)
        return ValuationSuppression(outcome.account_id, outcome.listing_id, first, None, None,
                                    CALENDAR_COVERAGE_GAP + ": the linking window is not covered by a calendar")
    return None


def _uncorroborated_flags(
    events: Sequence[SequencedEvent], listings: Sequence[uuid.UUID],
    windows: Mapping[Tuple[uuid.UUID, datetime.date], SessionWindow],
) -> Tuple[LineageFlag, ...]:
    """Ruling 6.4 item 4 / 6.4a item 4: a live ledger SPLIT inside NO linking window is flagged
    UNCORROBORATED_LEDGER_SPLIT in lineage, whatever its ratio, and changes no state. When any corroborated split of
    the listing has a window that could not be evaluated, a split outside the evaluable windows might lie inside that
    one, so nothing is flagged for the listing."""
    reversed_ids = {se.event.reverses_event_id for se in events if se.event.event_type is EventType.REVERSAL}
    wanted = set(listings)
    flags: List[LineageFlag] = []
    for se in events:
        e = se.event
        if (e.event_type is not EventType.SPLIT or e.listing_id not in wanted or e.event_id in reversed_ids
                or e.listing_id is None):
            continue
        mine = [w for (lid, _), w in windows.items() if lid == e.listing_id]
        if any(not w.evaluable for w in mine) or any(w.contains(e.event_date) for w in mine):
            continue
        flags.append(LineageFlag(e.account_id, e.listing_id, e.event_id, e.event_date, UNCORROBORATED_LEDGER_SPLIT,
                                 "a live ledger split inside no corroborated split's linking window (the free feed "
                                 "may not know it); no state effect"))
    return tuple(sorted(flags, key=lambda f: (f.event_date, str(f.account_id), str(f.event_id))))
