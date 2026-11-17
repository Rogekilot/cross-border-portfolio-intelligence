"""Load the ledger, detect split suppressions without writing, and call the engine (tech plan 16.1, 16.2, 16.16).

CP3-4: NO entry here defaults to "no suppressions". Each `*_for_portfolio` entry runs the F8-B detection itself, read-only (`dry_run=True`, a `ReadOnlyLedgerAccess`
that refuses to append), over every listing the ledger touches and the whole release, and hands the result to the engine with `detection="F8B_DRY_RUN"`, which goes
into the manifest. The caller supplies the confirmation policy (which registered sources are feeds and which are filings): that is a human's registration, not a
default.

PM ruling (market-data/1.9 Ruling 4.8 item 4, performance/1.3): a USER portfolio is never computed from a market-data version that holds a synthetic file. These
entries REFUSE, with the explicit state `SYNTHETIC_MARKET_DATA_REFUSED` (INSUFFICIENT_DATA, no number). Tests and fixtures call the engine directly, and stay allowed.
"""

from __future__ import annotations

import contextlib
import datetime
import json
import uuid
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from corporate_actions_service import split_confirmation as f8b
from domain.currency import CurrencyCode
from domain.replay import SequencedEvent
from marketdata.calendars import CalendarSet
from marketdata.canonical import canonical_json, sha256_hex
from marketdata.conventions import ConventionSet
from marketdata.port import InstrumentResolverPort, MarketDataPort
from performance.engine import (
    RecordingResolver,
    choose_current_date,
    compute,
    compute_attribution,
    compute_current,
    compute_gains,
    compute_window,
    refuse,
)
from performance.inputs import MarketAtInstant, SuppressionInput, ValuationMode
from performance.manifest import ComputationResult
from performance.periods import WindowSpec
from persistence import ledger_replay_store

SYNTHETIC_MARKET_DATA_REFUSED = "SYNTHETIC_MARKET_DATA_REFUSED"
DETECTION_POLICY_UNMATCHED = "DETECTION_POLICY_UNMATCHED"  # CP3-11: an explicit state, no number
DETECTION = "F8B_DRY_RUN"


class WriteRefusedError(RuntimeError):
    """The read-only ledger access was asked to append. A performance computation never writes the ledger."""


class ReadOnlyLedgerAccess:
    """A `LedgerAccess` (F8-B) whose `append` always refuses: detect-only mode cannot write even by mistake."""

    def __init__(self, conn: Any):
        self._conn = conn

    def load(self, portfolio_id: uuid.UUID) -> Tuple[int, Tuple[SequencedEvent, ...]]:
        version = ledger_replay_store.current_ledger_version(self._conn, portfolio_id)
        return version, ledger_replay_store.load_events(self._conn, portfolio_id, version)

    def append(self, event: Any) -> Any:
        raise WriteRefusedError("performance computation never writes the ledger")

    def atomic(self, portfolio_id: uuid.UUID) -> Any:
        return contextlib.nullcontext()  # a read-only access has nothing to roll back


class PinnedLedgerAccess:
    """A read-only `LedgerAccess` over events already loaded at a pinned version (so detection sees the SAME ledger the engine computes over)."""

    def __init__(self, version: int, events: Sequence[SequencedEvent]):
        self._version, self._events = version, tuple(events)

    def load(self, portfolio_id: uuid.UUID) -> Tuple[int, Tuple[SequencedEvent, ...]]:
        return self._version, self._events

    def append(self, event: Any) -> Any:
        raise WriteRefusedError("performance computation never writes the ledger")

    def atomic(self, portfolio_id: uuid.UUID) -> Any:
        return contextlib.nullcontext()


def suppressions_from_report(report: f8b.SplitReport) -> Tuple[SuppressionInput, ...]:
    return tuple(SuppressionInput(
        s.account_id, s.listing_id, s.first_date, s.end_exclusive, None if s.reason_code is None else s.reason_code.value,
        s.flag, s.ex_date, s.decision) for s in report.suppressions)


def detect_split_suppressions(
    access: Any, port: Any, portfolio_id: uuid.UUID, listing_ids: Iterable[uuid.UUID], start: datetime.date,
    end: datetime.date, policy: f8b.ConfirmationPolicy, trading_currency: Mapping[uuid.UUID, CurrencyCode], *,
    calendars: CalendarSet, exchange_of: Callable[[uuid.UUID], Optional[str]],
) -> Tuple[f8b.SplitReport, Tuple[SuppressionInput, ...]]:
    """Run F8-B in detect-only mode (`dry_run=True`): the report and the suppressions it implies, nothing appended."""
    report = f8b.confirm_splits(access, port, portfolio_id, listing_ids, start, end, policy, trading_currency,
                                calendars=calendars, exchange_of=exchange_of, dry_run=True)
    return report, suppressions_from_report(report)


def _detect(events: Sequence[SequencedEvent], pin: int, portfolio_id: uuid.UUID, port: Any, resolver: InstrumentResolverPort,
            calendars: CalendarSet, policy: f8b.ConfirmationPolicy) -> Tuple[SuppressionInput, ...]:
    listings = sorted({i.event.listing_id for i in events if i.event.listing_id is not None and i.ledger_seq <= pin}, key=str)
    currencies = {lid: c for lid in listings for c in [resolver.trading_currency(lid)] if c is not None}
    _report, suppressions = detect_split_suppressions(
        PinnedLedgerAccess(pin, [i for i in events if i.ledger_seq <= pin]), port, portfolio_id, listings, datetime.date.min, datetime.date.max, policy,
        currencies, calendars=calendars, exchange_of=resolver.exchange_mic)
    return suppressions


def _pin(conn: Any, portfolio_id: uuid.UUID, ledger_version: Optional[int]) -> Tuple[int, Tuple[SequencedEvent, ...]]:
    current = ledger_replay_store.current_ledger_version(conn, portfolio_id)
    pin = current if ledger_version is None else ledger_version
    if pin > current:
        raise ledger_replay_store.LedgerVersionNotCommittedError(f"ledger_version {pin} is above the committed {current}")
    if pin != current:
        ledger_replay_store.require_committed_boundary(conn, portfolio_id, pin)
    return pin, ledger_replay_store.load_events(conn, portfolio_id, pin)


def _calendars_of(market_conventions: ConventionSet) -> CalendarSet:
    calendars = getattr(market_conventions.freshness, "calendars", None)
    if calendars is None:
        raise ValueError("split detection needs the calendars of the market-data conventions (no calendar-aware freshness policy)")
    return calendars


# The three helpers a sibling service (`risk_service`) shares with this one, PUBLIC so that it never reaches into a private name (CP4 final review): one pin rule and one detection rule for CP3 and CP4. They call the
# private functions through the module, so a test that patches `_pin` patches both.
def pin_ledger_events(conn: Any, portfolio_id: uuid.UUID, ledger_version: Optional[int] = None) -> Tuple[int, Tuple[SequencedEvent, ...]]:
    """The ledger events at a pinned version (the current committed one by default); an uncommitted or mid-append version is refused."""
    return _pin(conn, portfolio_id, ledger_version)


def detect_suppressions(events: Sequence[SequencedEvent], pin: int, portfolio_id: uuid.UUID, port: Any, resolver: InstrumentResolverPort, calendars: CalendarSet,
                        policy: f8b.ConfirmationPolicy) -> Tuple[SuppressionInput, ...]:
    """The F8-B dry-run split suppressions over the pinned ledger and `port`, read-only."""
    return _detect(events, pin, portfolio_id, port, resolver, calendars, policy)


def calendars_of_conventions(market_conventions: ConventionSet) -> CalendarSet:
    """The calendar set of the market-data conventions (a refusal if the freshness policy is not calendar-aware)."""
    return _calendars_of(market_conventions)


def _refusal_record(events, pin, as_of, reporting, current, resolver, port, computed) -> Tuple[Dict[str, Any], datetime.date]:
    """What EVERY refusal records, Current or historical (CP4-2, CP4-7; performance Ruling 1.7 (1.12) items 4 and 5), the same as the computed manifest over the same view:
    - the identity facts it asked for (`identity_digest`: the exchange and currency of every listing the ledger names, and whatever `D_c(t)` asked) and the source registry of the view it read
      (`source_registry_digest`, from `port`; or, when a COMPUTED result is being refused after the fact, the digests that result carries);
    - in Current mode (`current` = `(instant, view, resolver)`): the instant `t`, the as-of rule `D_c(t)` and the date it chose (the UTC date of `t`, with the cause, if none), `M`
      (`parent_release_id`), the hashes `M_t` leaves out and `M_t`'s release id.
    Returns `(refuse kwargs, the as-of date)`."""
    extra: Dict[str, Any] = {}
    recording = RecordingResolver.wrap(resolver if resolver is not None else current[2]) if (resolver is not None or current is not None) else None
    if computed is None and recording is not None:
        for listing in sorted({i.event.listing_id for i in events if i.event.listing_id is not None and i.ledger_seq <= pin}, key=str):
            recording.trading_currency(listing)
            recording.exchange_mic(listing)
    if current is not None:
        instant, view, _resolver = current
        chosen = choose_current_date(instant, events, pin, view.calendars, recording.exchange_mic, reporting, recording.trading_currency)
        extra.update({"as_of_rule": "D_c(t)", "instant": instant, "as_of_causes": tuple(c.note for c in chosen.causes), "view": view, "release_id": view.port.release_id()})
        if chosen.date is not None:
            as_of = chosen.date
    if computed is not None:
        extra.update(identity_digest=computed.manifest.identity_digest, source_registry_digest=computed.manifest.source_registry_digest)
    else:
        extra.update(identity_digest="" if recording is None else recording.digest(), registry_port=port)
    return extra, as_of


def _refuse_synthetic(events, pin, as_of, reporting, market_conventions, conventions, portfolio_id, account_scope, current=None, resolver=None, port=None, computed=None) -> ComputationResult:
    extra, as_of = _refusal_record(events, pin, as_of, reporting, current, resolver, port, computed)
    return refuse(events, pin, as_of, reporting, market_conventions, conventions, ValuationMode.HISTORICAL_AS_OF, portfolio_id, (), account_scope,
                  DETECTION, SYNTHETIC_MARKET_DATA_REFUSED,
                  "the market-data version holds synthetic files, and a user portfolio is never computed from synthetic data (no number)", synthetic=True, **extra)


def policy_reference(policy: f8b.ConfirmationPolicy) -> Tuple[Tuple[str, str], ...]:
    """The confirmation policy as the manifest cites it (CP3-11): its digest and its source ids."""
    feed, filing = ",".join(sorted(policy.feed_sources)), ",".join(sorted(policy.filing_sources))
    return (("digest", sha256_hex(canonical_json({"feed": sorted(policy.feed_sources), "filing": sorted(policy.filing_sources)}).encode("utf-8"))),
            ("feed", feed), ("filing", filing))


def policy_matches_nothing(events: Sequence[SequencedEvent], pin: int, port: Any, policy: f8b.ConfirmationPolicy) -> Optional[str]:
    """market-data/1.11 Ruling 6.4d (CP3-11, CP3-15). The confirmation policy must classify (name in a role) every source that holds a SPLIT record of a ledger listing, PER (LISTING, EX-DATE) with
    exact ex-date equality: otherwise a split missing from the ledger could be valued in mixed units, or an unclassified record could hide a `DISAGREEMENT` (case (c)). Returns the reason text, which
    names EVERY unmatched key as a JSON array (`listing`, `ex_date`, `unclassified_sources`, `unmatched_roles`), else None. The keys come from `f8b.unmatched_policy_keys` (the F8-B append run
    applies the same test)."""
    keys = policy_unmatched_keys(events, pin, port, policy)
    if not keys:
        return None
    return (f"the confirmation policy leaves {len(keys)} (listing, ex-date) key{'s' if len(keys) > 1 else ''} unclassified, so detection could never be sure of what M holds for "
            f"{'them' if len(keys) > 1 else 'it'} and a split missing from the ledger could be valued in mixed units; unmatched_keys=" + json.dumps([k.as_object() for k in keys], sort_keys=True, separators=(",", ":")))


def policy_unmatched_keys(events: Sequence[SequencedEvent], pin: int, port: Any, policy: f8b.ConfirmationPolicy) -> Tuple[f8b.UnmatchedKey, ...]:
    """Ruling 6.4d: every listing named by an event of the ledger at the pin (live or reversed) against every ex-date of its SPLIT records in `port` (M, or M_t in Current mode)."""
    listings = {i.event.listing_id for i in events if i.event.listing_id is not None and i.ledger_seq <= pin}
    return f8b.unmatched_policy_keys(listings, lambda l: port.corporate_actions(l, datetime.date.min, datetime.date.max).readings, policy)


def _refuse_policy(events, pin, as_of, reporting, market_conventions, conventions, portfolio_id, account_scope, policy, why, current=None, resolver=None, port=None) -> ComputationResult:
    extra, as_of = _refusal_record(events, pin, as_of, reporting, current, resolver, port, None)
    return refuse(events, pin, as_of, reporting, market_conventions, conventions, ValuationMode.HISTORICAL_AS_OF, portfolio_id, (), account_scope,
                  DETECTION, DETECTION_POLICY_UNMATCHED, why, detection_policy=policy_reference(policy), **extra)


def _gate(events, pin, as_of, reporting, market_conventions, conventions, portfolio_id, account_scope, port, calendars, resolver, policy, current=None):
    """The checks before any number: (1) the port must say whether it holds synthetic files, and a port that cannot is treated as synthetic (CP3-10); (2) the
    policy must recognise a source of M's corporate-action records (CP3-11). Returns `(refusal, None)` or `(None, suppressions)`."""
    if getattr(port, "contains_synthetic", True):
        return _refuse_synthetic(events, pin, as_of, reporting, market_conventions, conventions, portfolio_id, account_scope, current, resolver, port), None
    why = policy_matches_nothing(events, pin, port, policy)
    if why is not None:
        return _refuse_policy(events, pin, as_of, reporting, market_conventions, conventions, portfolio_id, account_scope, policy, why, current, resolver, port), None
    return None, _detect(events, pin, portfolio_id, port, resolver, calendars, policy)


def _finish(result: ComputationResult, events, pin, as_of, reporting, market_conventions, conventions, portfolio_id, account_scope, current=None) -> ComputationResult:
    """CP3-10, belt and braces: whatever the port said, a computed result that is marked synthetic (the data it read says so) is never handed out for a user portfolio."""
    if result.manifest.synthetic:
        return _refuse_synthetic(events, pin, as_of, reporting, market_conventions, conventions, portfolio_id, account_scope, current, computed=result)
    return result


def compute_for_portfolio(
    conn: Any, portfolio_id: uuid.UUID, as_of: datetime.date, reporting_currency: CurrencyCode, port: MarketDataPort,
    resolver: InstrumentResolverPort, market_conventions: ConventionSet, conventions: Any, *,
    policy: f8b.ConfirmationPolicy, ledger_version: Optional[int] = None,
    mode: ValuationMode = ValuationMode.HISTORICAL_AS_OF, account_scope: Optional[uuid.UUID] = None,
) -> ComputationResult:
    """Read the portfolio's events at a pinned ledger version (default: the current committed one), detect the split suppressions (read-only) and compute."""
    pin, events = _pin(conn, portfolio_id, ledger_version)
    refusal, suppressions = _gate(events, pin, as_of, reporting_currency, market_conventions, conventions, portfolio_id, account_scope, port,
                                  _calendars_of(market_conventions), resolver, policy)
    if refusal is not None:
        return refusal
    result = compute(events, pin, as_of, reporting_currency, port, resolver, market_conventions, conventions, portfolio_id=portfolio_id,
                     suppressions=suppressions, mode=mode, account_scope=account_scope, detection=DETECTION, detection_policy=policy_reference(policy))
    return _finish(result, events, pin, as_of, reporting_currency, market_conventions, conventions, portfolio_id, account_scope)


def compute_window_for_portfolio(
    conn: Any, portfolio_id: uuid.UUID, spec: WindowSpec, end: datetime.date, reporting_currency: CurrencyCode, port: MarketDataPort,
    resolver: InstrumentResolverPort, market_conventions: ConventionSet, conventions: Any, *,
    policy: f8b.ConfirmationPolicy, ledger_version: Optional[int] = None, account_scope: Optional[uuid.UUID] = None,
    verify_identities: bool = False,
) -> ComputationResult:
    """The window metrics (G, TWR, annualized TWR) of a portfolio, with the same detection and the same synthetic refusal."""
    pin, events = _pin(conn, portfolio_id, ledger_version)
    refusal, suppressions = _gate(events, pin, end, reporting_currency, market_conventions, conventions, portfolio_id, account_scope, port,
                                  _calendars_of(market_conventions), resolver, policy)
    if refusal is not None:
        return refusal
    result = compute_window(events, pin, spec, end, reporting_currency, port, resolver, market_conventions, conventions, portfolio_id=portfolio_id,
                            suppressions=suppressions, account_scope=account_scope, verify_identities=verify_identities, detection=DETECTION,
                            detection_policy=policy_reference(policy))
    return _finish(result, events, pin, end, reporting_currency, market_conventions, conventions, portfolio_id, account_scope)


def compute_current_for_portfolio(
    conn: Any, portfolio_id: uuid.UUID, instant: datetime.datetime, reporting_currency: CurrencyCode, resolver: InstrumentResolverPort,
    market_at: MarketAtInstant, conventions: Any, *, policy: f8b.ConfirmationPolicy, ledger_version: Optional[int] = None,
    account_scope: Optional[uuid.UUID] = None,
) -> ComputationResult:
    """"Current value" over `M_t` (performance/1.2 Ruling 1.7). Detection runs over `M_t` too (the corporate-action files a computation at `t` could have read)."""
    pin, events = _pin(conn, portfolio_id, ledger_version)
    view = market_at.view(instant)
    day = instant.astimezone(datetime.timezone.utc).date()
    refusal, suppressions = _gate(events, pin, day, reporting_currency, view.conventions, conventions, portfolio_id, account_scope, view.port,
                                  view.calendars, resolver, policy, (instant, view, resolver))  # performance/1.4 Ruling 1.7: detection runs over M_t, the files a computation at t could have read
    if refusal is not None:
        return refusal
    result = compute_current(events, pin, instant, reporting_currency, resolver, market_at, conventions, suppressions=suppressions,
                             portfolio_id=portfolio_id, account_scope=account_scope, detection=DETECTION, detection_policy=policy_reference(policy))
    return _finish(result, events, pin, day, reporting_currency, view.conventions, conventions, portfolio_id, account_scope, (instant, view, resolver))


# --- gains and attribution (CP3f): the same gates as the window entry ----------------------------------------------------------------------------------------------------

def compute_gains_for_portfolio(
    conn: Any, portfolio_id: uuid.UUID, as_of: datetime.date, reporting_currency: CurrencyCode, port: MarketDataPort,
    resolver: InstrumentResolverPort, market_conventions: ConventionSet, conventions: Any, *,
    policy: f8b.ConfirmationPolicy, ledger_version: Optional[int] = None, window: Optional[WindowSpec] = None, account_scope: Optional[uuid.UUID] = None,
) -> ComputationResult:
    """Realized and unrealized gain, remaining basis and the since-acquisition split of a portfolio (`compute_gains`), behind the gates of every entry here: the synthetic refusal,
    detection always run (read-only, `F8B_DRY_RUN`) and `DETECTION_POLICY_UNMATCHED`. A refusal carries no number."""
    pin, events = _pin(conn, portfolio_id, ledger_version)
    refusal, suppressions = _gate(events, pin, as_of, reporting_currency, market_conventions, conventions, portfolio_id, account_scope, port,
                                  _calendars_of(market_conventions), resolver, policy)
    if refusal is not None:
        return refusal
    result = compute_gains(events, pin, as_of, reporting_currency, port, resolver, market_conventions, conventions, suppressions=suppressions, window=window,
                           portfolio_id=portfolio_id, account_scope=account_scope, detection=DETECTION, detection_policy=policy_reference(policy))
    return _finish(result, events, pin, as_of, reporting_currency, market_conventions, conventions, portfolio_id, account_scope)


def compute_attribution_for_portfolio(
    conn: Any, portfolio_id: uuid.UUID, spec: WindowSpec, end: datetime.date, reporting_currency: CurrencyCode, port: MarketDataPort,
    resolver: InstrumentResolverPort, market_conventions: ConventionSet, conventions: Any, *,
    policy: f8b.ConfirmationPolicy, ledger_version: Optional[int] = None, account_scope: Optional[uuid.UUID] = None,
) -> ComputationResult:
    """The attribution of a portfolio over a window (`compute_attribution`), behind the same gates as `compute_window_for_portfolio`."""
    pin, events = _pin(conn, portfolio_id, ledger_version)
    refusal, suppressions = _gate(events, pin, end, reporting_currency, market_conventions, conventions, portfolio_id, account_scope, port,
                                  _calendars_of(market_conventions), resolver, policy)
    if refusal is not None:
        return refusal
    result = compute_attribution(events, pin, spec, end, reporting_currency, port, resolver, market_conventions, conventions, portfolio_id=portfolio_id,
                                 suppressions=suppressions, account_scope=account_scope, detection=DETECTION, detection_policy=policy_reference(policy))
    return _finish(result, events, pin, end, reporting_currency, market_conventions, conventions, portfolio_id, account_scope)


def _current_view(conn: Any, portfolio_id: uuid.UUID, instant: datetime.datetime, reporting_currency: CurrencyCode, resolver: InstrumentResolverPort,
                  market_at: MarketAtInstant, conventions: Any, policy: f8b.ConfirmationPolicy, ledger_version: Optional[int], account_scope: Optional[uuid.UUID]):
    """Current mode for gains and attribution (performance/1.2 Ruling 1.7, as for `compute_current_for_portfolio`): the gate and the detection run over `M_t`; the date is
    `D_c(t)` chosen from `M_t`'s calendars. Returns `(result, None)` for a refusal (the explicit state, no number) or `(None, ready)`."""
    pin, events = _pin(conn, portfolio_id, ledger_version)
    view = market_at.view(instant)
    day = instant.astimezone(datetime.timezone.utc).date()
    refusal, suppressions = _gate(events, pin, day, reporting_currency, view.conventions, conventions, portfolio_id, account_scope, view.port, view.calendars, resolver, policy,
                                  (instant, view, resolver))
    if refusal is not None:
        return refusal, None
    recording = RecordingResolver.wrap(resolver)
    chosen = choose_current_date(instant, events, pin, view.calendars, recording.exchange_mic, reporting_currency, recording.trading_currency)
    if chosen.date is None:
        return compute_current(events, pin, instant, reporting_currency, resolver, market_at, conventions, suppressions=suppressions, portfolio_id=portfolio_id,
                               account_scope=account_scope, detection=DETECTION, detection_policy=policy_reference(policy)), None
    return None, (events, pin, view, recording, chosen.date, suppressions)


def compute_gains_current_for_portfolio(
    conn: Any, portfolio_id: uuid.UUID, instant: datetime.datetime, reporting_currency: CurrencyCode, resolver: InstrumentResolverPort,
    market_at: MarketAtInstant, conventions: Any, *, policy: f8b.ConfirmationPolicy, ledger_version: Optional[int] = None,
    window: Optional[WindowSpec] = None, account_scope: Optional[uuid.UUID] = None,
) -> ComputationResult:
    """Gains at `D_c(t)` over `M_t` (the files retrieved at or before `t`); detection runs over `M_t` too."""
    refusal, ready = _current_view(conn, portfolio_id, instant, reporting_currency, resolver, market_at, conventions, policy, ledger_version, account_scope)
    if ready is None:
        return refusal
    events, pin, view, recording, date, suppressions = ready
    result = compute_gains(events, pin, date, reporting_currency, view.port, recording, view.conventions, conventions, suppressions=suppressions, window=window,
                           portfolio_id=portfolio_id, account_scope=account_scope, detection=DETECTION, detection_policy=policy_reference(policy),
                           as_of_rule="D_c(t)", instant=instant, view=view)
    return _finish(result, events, pin, date, reporting_currency, view.conventions, conventions, portfolio_id, account_scope, (instant, view, recording))


def compute_attribution_current_for_portfolio(
    conn: Any, portfolio_id: uuid.UUID, instant: datetime.datetime, spec: WindowSpec, reporting_currency: CurrencyCode, resolver: InstrumentResolverPort,
    market_at: MarketAtInstant, conventions: Any, *, policy: f8b.ConfirmationPolicy, ledger_version: Optional[int] = None, account_scope: Optional[uuid.UUID] = None,
) -> ComputationResult:
    """The attribution of the window `spec` ending at `D_c(t)`, over `M_t`."""
    refusal, ready = _current_view(conn, portfolio_id, instant, reporting_currency, resolver, market_at, conventions, policy, ledger_version, account_scope)
    if ready is None:
        return refusal
    events, pin, view, recording, date, suppressions = ready
    result = compute_attribution(events, pin, spec, date, reporting_currency, view.port, recording, view.conventions, conventions, portfolio_id=portfolio_id,
                                 suppressions=suppressions, account_scope=account_scope, detection=DETECTION, detection_policy=policy_reference(policy),
                                 as_of_rule="D_c(t)", instant=instant, view=view)
    return _finish(result, events, pin, date, reporting_currency, view.conventions, conventions, portfolio_id, account_scope, (instant, view, recording))
