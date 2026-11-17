"""The performance engine's public entry (tech plan 16.0, 16.2, 16.3, 16.5; `performance/1.0`): `compute`, `compute_window`, `compute_current` and `reproduce`.

All are PURE functions of the live ledger events at a pinned version L, a `MarketDataPort` bound to one release M and the injected conventions. They never write
anything and never read a clock (the Current-mode instant `t` is an argument).

- `compute(...)`: the valuation at an as-of date D: `holding_value`, `cash_value`, `receivable_value`, `portfolio_value` (native and reporting views), the stale weight of
  a LIMITED total, the freshness vector, the apportioned breakdown of the total, and, only when the total is suppressed, the separately labelled partial figure
  `portfolio_value_priced_holdings` (PD-0035 section 2: never the total, never a denominator).
- `compute_window(...)`: over a window `(B, E]`: the absolute gain `G`, the TWR in segment form and the annualized TWR (Rulings 5.x, 7.x), portfolio or account scope.
- `compute_current(...)`: "current value" as the valuation at `D_c(t)`, the latest date whose every close and fixing has happened (Ruling 1.7), still historical as-of with
  no live feed. A `CURRENT_LIVE` request is refused with an explicit availability state (PM ruling 4).
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from domain.currency import CurrencyCode
from domain.replay import CONVENTION_SET_ID as LEDGER_REPLAY_ID
from domain.replay import FIFO_CONVENTION_SET_ID as FIFO_REPLAY_ID
from domain.replay import AccountStatus, SequencedEvent, live_events, reconstruct, reconstruct_fifo
from domain.ledger import EventType
from marketdata.calendars import CalendarSet
from marketdata.canonical import canonical_json, sha256_hex
from marketdata.conventions import ConventionSet
from marketdata.consumption import ValuationInputs, assemble_valuation_inputs
from marketdata.manifest import DataKind, DataSetRef, SourceRegistryNotPinnedError, source_registry_digest
from marketdata.port import InstrumentResolverPort, MarketDataPort
from performance.conventions import (
    CONVENTION_SET_ID,
    UNBUILT_IN_CP3B,
    DateLabelValuation,
    PerformanceConventionSet,
    performance_flow_table,
)
from performance.current import CurrentDate, choose_current_date
from performance.flows import DataUse, ValuedFlow, external_flows, value_flow
from performance.identity import RecordingResolver
from performance.inputs import MarketAtInstant, MarketView, SuppressionInput, ValuationMode, suppressions_digest
from performance.ledger_view import classify_events, inception_of, ledger_digest
from performance.taint import TRANSFER_AFTER_UNRECORDED_SPLIT, carried_taint, transfers_after_unrecorded_split
from performance.manifest import (
    ComputationManifest,
    ComputationResult,
    ReproductionReport,
    ReproductionStatus,
    calendar_files,
    seal,
)
from performance.numerics import CARINO_RESIDUAL_BOUND, IRRATIONAL_WIDTH, PresentStatus, RoundingPoint, apportion, apportion_displayed, carino_link, present, to_decimal_money
from performance.periods import WindowRule, WindowSpec, resolve_window, year_fraction
from performance.results import RATIONAL, DECIMAL_PREC50, Cause, ComputedMetric, Excluded, Part, WindowUsed, sorted_causes
from performance import attribution, gains, lines
from performance.returns import absolute_gain, annualize, daily_gain_sum, daily_twr_factor, mwr_period, twr_segments
from performance.series import (
    FAIL,
    MAX_AVAILABLE,
    NO_FULL_PERIOD,
    SERIES_SCHEMA,
    BoundaryRule,
    Frequency,
    MaxAvailable,
    SeriesIdentityError,
    SeriesRefusal,
    SeriesResult,
    apply_max_available,
    boundaries_digest,
    build_series,
    coverage_identity,
    effective_window,
    link_identity,
    validate_boundaries,
)
from performance.rounding import PerformanceRounding
from performance.states import (
    CALCULATION_ERROR,
    NOT_RECONSTRUCTABLE,
    PerformanceAggregation,
    Valued,
    build_metric,
    insufficient_part,
)
from performance.valuation import (
    PortfolioValuation,
    accrued_receivables,
    extend_fx,
    value_portfolio,
)
from product_contract.vocabulary import SufficiencyState

METHOD_ID = "performance.valuation/cp3b"
WINDOW_METHOD_ID = "performance.returns/cp3b"
GAINS_METHOD_ID = "performance.gains/cp3d"
ATTRIBUTION_METHOD_ID = "performance.attribution/cp3e"
UNSUPPORTED_VALUATION_MODE = "UNSUPPORTED_VALUATION_MODE"
INSUFFICIENT = SufficiencyState.INSUFFICIENT_DATA


def performance_conventions() -> PerformanceConventionSet:
    """The performance convention set as built: every ruling carries its id; a ruling not yet built would be listed as an open item (none is, since performance/1.11), so
    `is_conformant` is True unless a placeholder is injected or a minor-unit row is from memory."""
    rounding = PerformanceRounding()
    return PerformanceConventionSet(
        convention_set_id=CONVENTION_SET_ID, valuation=DateLabelValuation(), aggregation=PerformanceAggregation(),
        rounding=rounding, flows=performance_flow_table(),
        open_items=UNBUILT_IN_CP3B + rounding.table.open_items(),
    )


def calendar_id_resolver(market: ConventionSet):
    """MIC -> the id of the ONE calendar of M that governs it (performance/1.2 Ruling 1.6 keys the freshness vector by calendar), or None (no calendars, none or
    several govern it)."""
    calendars = getattr(market.freshness, "calendars", None)

    def calendar_id_of(mic: Optional[str]) -> Optional[str]:
        if calendars is None or mic is None:
            return None
        calendar, _problem = calendars.governing(mic)
        return None if calendar is None else calendar.calendar_id

    return calendar_id_of


def _convention_pairs(market: ConventionSet, perf: PerformanceConventionSet) -> Tuple[Tuple[str, str], ...]:
    # A manifest cites ledger-replay/1.5 (the FIFO/1 mode of the one lot fold), which also decides the carried taint (performance/1.5 Ruling 1.1a); the replay of quantities, cash
    # and flags is identical in the `none` mode (ledger-replay/1.3, which CP1 outputs still cite).
    pairs = [("ledger_replay", FIFO_REPLAY_ID)]
    pairs += [(f"market_data.{k}", v) for k, v in market.ids().items()]
    pairs += [(f"performance.{k}", v) for k, v in perf.ids().items()]
    return tuple(sorted(pairs))


def _open_items(market: ConventionSet, perf: PerformanceConventionSet) -> Tuple[str, ...]:
    return tuple(sorted(set(perf.visible_open_items()) | {f"market_data: {i}" for i in market.visible_open_items()}))


class _Run:
    """One computation's working state: the live events at L, a cache of daily valuations and the data read (for the manifest)."""

    def __init__(self, events: Sequence[SequencedEvent], ledger_version: int, reporting: CurrencyCode, port: MarketDataPort,
                 resolver: InstrumentResolverPort, market: ConventionSet, perf: PerformanceConventionSet,
                 suppressions: Sequence[SuppressionInput], account_scope: Optional[uuid.UUID],
                 retrieved_not_after: Optional[datetime.datetime], view: Optional[MarketView] = None,
                 detection: str = "CALLER_SUPPLIED", detection_policy: Tuple[Tuple[str, str], ...] = ()):
        self.detection_policy = tuple(detection_policy)
        self.events = tuple(events)
        self.L = ledger_version
        self.reporting = reporting
        self.port, self.market, self.perf = port, market, perf
        # CP3-6: every identity fact the computation asks for is recorded and its digest goes into the manifest
        self.resolver = RecordingResolver.wrap(resolver)
        self.view = view
        self.detection = detection
        self.input_suppressions = tuple(suppressions)
        self.account_scope = account_scope
        self.retrieved_not_after = retrieved_not_after
        self.live = live_events(self.events, ledger_version)
        # market-data 1.9 Ruling 6.4c: a suppression follows the units carried by an internal transfer (derived from the live events and the suppressions at L)
        # (performance/1.5 Ruling 1.1a: decided by the end-of-day FIFO lot book; `event_taints` are the sales and transfers out whose relief record holds a tainted portion)
        self.carried = carried_taint(self.live, self.input_suppressions)
        self.suppressions = self.input_suppressions + self.carried.suppressions
        self.event_taints = self.carried.event_taints
        self.unrecorded_split_notes = transfers_after_unrecorded_split(self.live)
        self.calendar_id_of = calendar_id_resolver(market)
        # market-data Ruling 4.8: EVERY result computed from a version M that holds any synthetic file is synthetic, whether or not a lookup was needed
        # (CP3-10: a port that does not say is treated as synthetic: fail closed. `contains_synthetic` is a required member of the port.)
        self.use = DataUse(synthetic=bool(getattr(port, "contains_synthetic", True)))
        self._cache: Dict[datetime.date, PortfolioValuation] = {}
        self._totals: Dict[datetime.date, Valued] = {}

    def valuation(self, day: datetime.date) -> PortfolioValuation:
        cached = self._cache.get(day)
        if cached is not None:
            return cached
        state = reconstruct(self.events, day, self.L)
        if self.account_scope is not None:
            state = dataclasses.replace(state, accounts=tuple(a for a in state.accounts if a.account_id == self.account_scope))
        live = [i for i in self.live if self.account_scope is None or i.event.account_id == self.account_scope]
        receivables = accrued_receivables(live, day)
        inputs: ValuationInputs = assemble_valuation_inputs(self.port, self.resolver, state, day, self.reporting, self.market)
        inputs = extend_fx(inputs, [r.currency for r in receivables], self.port, self.market)
        self.use.add(DataKind.QUOTE, [f for q in inputs.quotes for f in q.lookup.consumed], day, any(q.lookup.synthetic for q in inputs.quotes))
        self.use.add(DataKind.FX, [f for x in inputs.fx for f in x.lookup.consumed], day, any(x.lookup.synthetic for x in inputs.fx))
        for x in inputs.fx:
            self.use.fx_notes.update(x.lookup.lineage_notes)
        self.release_id = inputs.release_id
        val = value_portfolio(state, inputs, self.suppressions, self.perf, self.resolver, receivables, self.retrieved_not_after,
                              self.calendar_id_of)
        self._cache[day] = val
        return val

    def total(self, day: datetime.date) -> Valued:
        return self.valuation(day).reporting_total

    def data_set_refs(self) -> Tuple[DataSetRef, ...]:
        ids = dict(self.market.ids())
        refs = []
        for kind in (DataKind.QUOTE, DataKind.FX):
            if kind in self.use.consumed:
                refs.append(DataSetRef.build(kind, self.port.release_id(), self.use.consumed[kind], ids, self.use.first[kind],
                                             self.use.last[kind], self.market.convention_set_id))
        return tuple(refs)


class ManifestInvariantError(ValueError):
    """An ENGINE FAULT: a manifest whose `valuation_mode`, `as_of_rule`, instant and parent release do not agree (performance/1.12 Ruling 1.7 item 5)."""


def _checked_mode(mode: ValuationMode, as_of_rule: str, instant: Optional[datetime.datetime], view: Optional[MarketView]) -> ValuationMode:
    """The manifest invariants (performance/1.12 build note, Ruling 1.7 item 5):

    | valuation_mode      | as_of_rule | instant | parent_release_id |
    | HISTORICAL_AS_OF    | CALLER     | null    | null              |
    | CURRENT_AT_INSTANT  | D_c(t)     | t       | M                 |

    (`CURRENT_LIVE` is a refused request: CALLER, no instant.) A call site that does not name the Current value but carries the Current-mode fields is read as Current (the gains and attribution
    entries share one manifest builder); every other combination is an engine fault, raised before a manifest exists."""
    current_fields = (as_of_rule == "D_c(t)", instant is not None, view is not None)
    if mode is ValuationMode.CURRENT_LIVE:
        if any(current_fields):
            raise ManifestInvariantError("a CURRENT_LIVE request is refused as a caller-dated one: no as-of rule, instant or M_t")
        return mode
    if all(current_fields):
        return ValuationMode.CURRENT_AT_INSTANT
    if not any(current_fields):
        if mode is ValuationMode.CURRENT_AT_INSTANT:
            raise ManifestInvariantError("CURRENT_AT_INSTANT needs as_of_rule D_c(t), the instant t and the parent release M")
        return ValuationMode.HISTORICAL_AS_OF
    raise ManifestInvariantError(f"valuation_mode, as_of_rule, instant and parent release disagree: as_of_rule D_c(t) {current_fields[0]}, instant {current_fields[1]}, M_t view {current_fields[2]}")


def registry_digest_of(port: Optional[MarketDataPort]) -> str:
    """`source_registry_digest` (performance/1.12 Ruling 1.7 item 4): the digest of the full registry records of the sources with a file in the `M` the port serves (`M_t` in Current mode).
    It is NEVER "": no market-data file read (no port) is the digest of the empty list, and a port that serves file observations must report its sources' records (`source_registry_records()`,
    which fails closed when a source it serves has no record); a port that cannot report them is refused: no manifest, no value."""
    if port is None:
        return source_registry_digest(())
    report = getattr(port, "source_registry_records", None)
    if report is None:
        raise SourceRegistryNotPinnedError("the market-data port cannot report its source registry records: nothing is computed over a registry that is not pinned")
    return source_registry_digest(tuple(report()))


def _manifest(run: Optional[_Run], events: Sequence[SequencedEvent], ledger_version: int, as_of: datetime.date, window: WindowUsed,
              reporting: CurrencyCode, market: ConventionSet, perf: PerformanceConventionSet, mode: ValuationMode,
              portfolio_id: Optional[uuid.UUID], suppressions: Sequence[SuppressionInput], account_scope: Optional[uuid.UUID],
              as_of_rule: str = "CALLER", instant: Optional[datetime.datetime] = None,
              as_of_causes: Tuple[str, ...] = (), synthetic_port: Optional[MarketDataPort] = None,
              detection: str = "CALLER_SUPPLIED", view: Optional[MarketView] = None,
              identity_digest: str = "", detection_policy: Tuple[Tuple[str, str], ...] = (), release_id: Optional[str] = None,
              registry_port: Optional[MarketDataPort] = None, source_registry_digest: Optional[str] = None) -> ComputationManifest:
    if run is not None:
        detection, view, identity_digest = run.detection, run.view, run.resolver.digest()
        detection_policy = run.detection_policy
    mode = _checked_mode(mode, as_of_rule, instant, view)
    refs = () if run is None else run.data_set_refs()
    consumed = tuple(sorted({f for r in refs for f in r.consumed}))
    return ComputationManifest(
        portfolio_id=None if portfolio_id is None else str(portfolio_id), reporting_currency=reporting.code,
        ledger_version=ledger_version, ledger_digest=ledger_digest(events, ledger_version), as_of=as_of, window=window,
        valuation_mode=mode.value, conventions=_convention_pairs(market, perf), conformant=perf.is_conformant,
        open_items=_open_items(market, perf), release_id=release_id if run is None else run.port.release_id(),
        data_set_refs=refs, calendar_file_refs=calendar_files(consumed), split_suppressions_digest=suppressions_digest(suppressions),
        methodology=(), numerics=(("rounding", perf.rounding.rule_id),),
        synthetic=(synthetic_port is not None and bool(getattr(synthetic_port, "contains_synthetic", True))) if run is None else run.use.synthetic,
        scope="PORTFOLIO" if account_scope is None else f"ACCOUNT:{account_scope}", as_of_rule=as_of_rule, instant=instant,
        as_of_causes=as_of_causes, identity_digest=identity_digest, split_detection=detection,
        parent_release_id=None if view is None else view.parent_release_id,
        excluded_files=() if view is None else tuple(sorted(view.excluded_files)), detection_policy=tuple(detection_policy),
        source_registry_digest=(source_registry_digest if source_registry_digest is not None
                                else registry_digest_of(run.port if run is not None else (registry_port or synthetic_port))))


# --- valuation metrics -------------------------------------------------------------------------------------------------------------

def _i1_status(val: PortfolioValuation) -> str:
    """Identity I-1 (Ruling 11.1; run in every call that produces the values it relates, performance/1.2 Q5): the total equals the exact sum of its components."""
    total = val.reporting_total
    if total.exact is None:
        return "NOT_COMPUTABLE"
    components = val.components()
    if any(v.exact is None for _r, v in components):
        return "NOT_COMPUTABLE"
    return "PASS" if sum((v.exact for _r, v in components), Fraction(0)) == total.exact else "FAIL"


def _valuation_metrics(val: PortfolioValuation, perf: PerformanceConventionSet, window: WindowUsed,
                       synthetic: bool, notes: Sequence = ()) -> Tuple[ComputedMetric, ...]:
    conformant = perf.is_conformant
    rounding = perf.rounding
    out: List[ComputedMetric] = []

    def add(metric_id: str, view: str, subject, valued: Valued, currency: Optional[CurrencyCode], lineage=(), *,
            point: RoundingPoint = RoundingPoint.PRESENT_MONEY, **extra) -> None:
        out.append(build_metric(metric_id, view, tuple(subject), valued, currency, rounding, window, METHOD_ID, synthetic, conformant,
                                tuple(lineage), point=point, **extra))

    for h in val.holdings:
        subject = (("account", str(h.account_id)), ("listing", str(h.listing_id)))
        lineage = []
        if h.last_print_date is not None:  # Ruling 1.1b: reported whenever a print exists, valued or withheld; never a value
            lineage.append(("last_print_date", h.last_print_date.isoformat()))
        if h.price_missed_count is not None:
            lineage.append(("price_missed_sessions", str(h.price_missed_count)))
        if h.fx_date_used is not None:
            lineage.append(("fx_date_used", h.fx_date_used.isoformat()))
        mine = [n for n in notes if n.receiver == (h.account_id, h.listing_id)]
        details = (TRANSFER_AFTER_UNRECORDED_SPLIT,) if mine else ()  # Ruling 6.4c item 7: a lineage note with no state effect
        lineage += [(f"{TRANSFER_AFTER_UNRECORDED_SPLIT}:{n.source_account}", n.ex_date.isoformat()) for n in mine]
        # Ruling 1.1b (performance/1.9): `price_date_used` is the session of the close that VALUES the holding in this view, so it is absent where the view has no value (withheld)
        used = [("price_date_used", h.price_date_used.isoformat())] if h.price_date_used is not None else []
        add("holding_value", "NATIVE", subject, h.native, h.native_currency, lineage + (used if h.native.exact is not None else []), details=details)
        add("holding_value", "REPORTING", subject, h.reporting, val.reporting_currency, lineage + (used if h.reporting.exact is not None else []), details=details)
    for c in val.cash:
        subject = (("account", str(c.account_id)), ("currency", c.currency.code))
        lineage = [] if c.fx_date_used is None else [("fx_date_used", c.fx_date_used.isoformat())]
        # a native cash balance is a SUM OF RECORDED FACTS: presented exactly (Ruling 2.2, last row); its reporting value is derived money
        add("cash_value", "NATIVE", subject, c.native, c.currency, lineage, point=RoundingPoint.PRESENT_FACT)
        add("cash_value", "REPORTING", subject, c.reporting, val.reporting_currency, lineage)
    for r in val.receivables:
        subject = (("account", str(r.receivable.account_id)), ("event", str(r.receivable.event_id)))
        lineage = [("ex_date", r.receivable.ex_date.isoformat()), ("pay_date", r.receivable.pay_date.isoformat())]
        if r.fx_date_used is not None:
            lineage.append(("fx_date_used", r.fx_date_used.isoformat()))
        add("receivable_value", "NATIVE", subject, r.native, r.receivable.currency, lineage, point=RoundingPoint.PRESENT_FACT)
        add("receivable_value", "REPORTING", subject, r.reporting, val.reporting_currency, lineage)
    for ccy, valued in val.native_totals:
        add("portfolio_value", "NATIVE", (("currency", ccy.code),), valued, ccy)
    i1 = _i1_status(val)
    breakdown = _breakdown(val, rounding) if i1 != "FAIL" else ()  # a total that differs from its parts has no apportionment: the identity failure is reported, never raised
    total_valued = val.reporting_total if i1 != "FAIL" else _identity_failure("I-1: the total differs from the sum of its components", val.reporting_total)
    add("portfolio_value", "REPORTING", (("currency", val.reporting_currency.code),), total_valued, val.reporting_currency,
        [("identity:I-1", i1)], breakdown=breakdown)
    if val.partial is not None:
        p = val.partial
        lineage = [("excluded_components", str(len(p.excluded))), ("excluded_holdings", str(p.excluded_holdings)),
                   ("included_components", str(p.included))]
        add("portfolio_value_priced_holdings", "REPORTING", (("currency", val.reporting_currency.code),), p.valued,
            val.reporting_currency, lineage, partial=True, excluded=p.excluded)
    return tuple(sorted(out, key=lambda m: (m.metric_id, m.view, m.subject)))


def _breakdown(val: PortfolioValuation, rounding) -> Tuple[Tuple[str, Decimal, Fraction], ...]:
    """Ruling 2.4: the displayed parts of the total, largest-remainder, summing EXACTLY to the displayed total."""
    total = val.reporting_total
    decimals_of = getattr(rounding, "money_decimals", None)
    if total.exact is None or decimals_of is None:
        return ()
    decimals = decimals_of(val.reporting_currency)
    comps = val.components()
    if decimals is None or not comps:
        return ()
    exacts = []
    for _ref, v in comps:
        if v.exact is None:
            return ()
        exacts.append(v.exact)
    shown = apportion(total.exact, exacts, decimals)
    lines = []
    for (ref, _v), exact, stated in zip(comps, exacts, shown):
        dec = to_decimal_money(stated, decimals)
        if dec is None:
            return ()
        lines.append((ref, dec, exact))
    return tuple(lines)


# --- entries -------------------------------------------------------------------------------------------------------------------

def refuse(events, ledger_version, as_of, reporting, market, conventions, mode, portfolio_id, suppressions, account_scope, detection,
           code: str, note: str, synthetic: bool = False, detection_policy: Tuple[Tuple[str, str], ...] = (),
           as_of_rule: str = "CALLER", instant: Optional[datetime.datetime] = None, as_of_causes: Tuple[str, ...] = (),
           view: Optional[MarketView] = None, release_id: Optional[str] = None, registry_port: Optional[MarketDataPort] = None,
           identity_digest: str = "", source_registry_digest: Optional[str] = None) -> ComputationResult:
    """An explicit refusal: one INSUFFICIENT_DATA `portfolio_value` that names `code`, and no number. Used for an unsupported valuation mode and (by the service)
    for a user portfolio whose market-data version holds synthetic files (PM ruling on market-data/1.9 Ruling 4.8), and for an unmatched confirmation policy.
    A Current-mode refusal passes `instant`, `view`, `as_of_rule` and `release_id`, so its manifest records what a computed Current-mode manifest records (performance Ruling 1.7 (1.2), P9):
    `t`, `D_c(t)` (as `as_of`), `M` (`parent_release_id`), `M_t` (`release_id`) and the hashes `M_t` leaves out. EVERY refusal, Current or historical, also records the identity facts it asked
    for (`identity_digest`) and the source registry of the view it read (`source_registry_digest`: given, or computed from `registry_port`; never ""), as the computed manifest does (CP4-7)."""
    window = WindowUsed(as_of, as_of)
    manifest = _manifest(None, events, ledger_version, as_of, window, reporting, market, conventions, mode, portfolio_id, suppressions,
                         account_scope, as_of_rule=as_of_rule, instant=instant, as_of_causes=as_of_causes, detection=detection, view=view,
                         detection_policy=detection_policy, release_id=release_id, registry_port=registry_port, identity_digest=identity_digest,
                         source_registry_digest=source_registry_digest)
    if synthetic:
        manifest = dataclasses.replace(manifest, synthetic=True)
    cause = Cause("refusal", INSUFFICIENT.value, None, f"{code}: {note}", code)
    refused = build_metric("portfolio_value", "REPORTING", (("currency", reporting.code),), Valued(INSUFFICIENT, None, None, (cause,)),
                           reporting, conventions.rounding, window, METHOD_ID, synthetic, conventions.is_conformant)
    return seal(manifest, (refused,))


def _refuse_mode(events, ledger_version, as_of, reporting, market, conventions, mode, portfolio_id, suppressions, account_scope, detection):
    return refuse(events, ledger_version, as_of, reporting, market, conventions, mode, portfolio_id, suppressions, account_scope, detection,
                  UNSUPPORTED_VALUATION_MODE,
                  f"{mode.value} is not built (no live source is admitted); only HISTORICAL_AS_OF is available")


def compute(
    events: Sequence[SequencedEvent], ledger_version: int, as_of: datetime.date, reporting_currency: CurrencyCode,
    port: Optional[MarketDataPort], resolver: Optional[InstrumentResolverPort], market_conventions: ConventionSet,
    conventions: PerformanceConventionSet, *, suppressions: Sequence[SuppressionInput],
    portfolio_id: Optional[uuid.UUID] = None, mode: ValuationMode = ValuationMode.HISTORICAL_AS_OF,
    account_scope: Optional[uuid.UUID] = None, retrieved_not_after: Optional[datetime.datetime] = None,
    as_of_rule: str = "CALLER", instant: Optional[datetime.datetime] = None, detection: str = "CALLER_SUPPLIED",
    view: Optional[MarketView] = None, detection_policy: Tuple[Tuple[str, str], ...] = (),
) -> ComputationResult:
    """`suppressions` has NO DEFAULT (CP3-4): the caller states the F8 valuation suppressions of the ledger at `ledger_version` explicitly (an empty tuple is an
    explicit statement that detection found none) and says in `detection` where they came from (`F8B_DRY_RUN` when the service ran detection, `CALLER_SUPPLIED`
    otherwise); both go into the manifest. No entry point silently defaults to "no suppressions"."""
    events = tuple(events)
    if mode is ValuationMode.CURRENT_LIVE:
        return _refuse_mode(events, ledger_version, as_of, reporting_currency, market_conventions, conventions, mode, portfolio_id,
                            suppressions, account_scope, detection)
    if port is None or resolver is None:
        raise ValueError("a historical valuation needs a market-data port and a resolver")
    window = WindowUsed(as_of, as_of)
    run = _Run(events, ledger_version, reporting_currency, port, resolver, market_conventions, conventions, suppressions, account_scope,
               retrieved_not_after, view, detection, detection_policy)
    val = run.valuation(as_of)
    metrics = _valuation_metrics(val, conventions, window, run.use.synthetic, run.unrecorded_split_notes)
    manifest = dataclasses.replace(
        _manifest(run, events, ledger_version, as_of, window, reporting_currency, market_conventions, conventions, mode,
                  portfolio_id, suppressions, account_scope, as_of_rule, instant), identities_run=("I-1",))
    return seal(manifest, _with_fx_lineage(metrics, run.use.fx_notes))


def compute_current(
    events: Sequence[SequencedEvent], ledger_version: int, instant: datetime.datetime, reporting_currency: CurrencyCode,
    resolver: InstrumentResolverPort, market_at: MarketAtInstant, conventions: PerformanceConventionSet, *,
    suppressions: Sequence[SuppressionInput], portfolio_id: Optional[uuid.UUID] = None, account_scope: Optional[uuid.UUID] = None,
    detection: str = "CALLER_SUPPLIED", detection_policy: Tuple[Tuple[str, str], ...] = (),
) -> ComputationResult:
    """"Current value" (Ruling 1.7): the valuation at `D_c(instant)` over `M_t` (performance/1.2 Ruling 1.7): the files of `M` retrieved at or before `instant`
    (calendar files by registration time), with EVERY CP2 step re-run over them (`market_at.view(instant)` builds the derived release). The manifest records `t`, `M`
    (`parent_release_id`) and the hashes of the files `M_t` leaves out. If the choice of date cannot be made (a governing calendar does not cover a candidate
    date) every metric is INSUFFICIENT_DATA with no reason code and the cause CALENDAR_COVERAGE_GAP."""
    events = tuple(events)
    view = market_at.view(instant)
    resolver = RecordingResolver.wrap(resolver)  # one record for the date choice AND the valuation
    chosen: CurrentDate = choose_current_date(instant, events, ledger_version, view.calendars, resolver.exchange_mic, reporting_currency,
                                                resolver.trading_currency)
    if chosen.date is None:
        as_of = instant.astimezone(datetime.timezone.utc).date()
        window = WindowUsed(as_of, as_of)
        manifest = _manifest(None, events, ledger_version, as_of, window, reporting_currency, view.conventions, conventions,
                             ValuationMode.HISTORICAL_AS_OF, portfolio_id, suppressions, account_scope, "D_c(t)", instant,
                             tuple(c.note for c in chosen.causes), synthetic_port=view.port, detection=detection, view=view,
                             identity_digest=resolver.digest(), detection_policy=detection_policy, release_id=view.port.release_id())
        metric = build_metric("portfolio_value", "REPORTING", (("currency", reporting_currency.code),),
                              Valued(INSUFFICIENT, None, None, sorted_causes(chosen.causes)), reporting_currency,
                              conventions.rounding, window, METHOD_ID, manifest.synthetic, conventions.is_conformant)
        return seal(manifest, (metric,))
    return compute(events, ledger_version, chosen.date, reporting_currency, view.port, resolver, view.conventions, conventions,
                   portfolio_id=portfolio_id, suppressions=suppressions, account_scope=account_scope,
                   as_of_rule="D_c(t)", instant=instant, detection=detection, view=view, detection_policy=detection_policy)


FX_NOTE_PREFIXES = (("provenance: UNCONFIRMED", "fx_note:provenance"), ("PARITY_CHECK_NOT_RUN", "fx_note:parity"))


def _fx_lineage(notes: Iterable[str]) -> Tuple[Tuple[str, str], ...]:
    """market-data Rulings 1.1a item 2 and 1.5a: a value computed from rates whose provenance is UNCONFIRMED (a republished rate) says so in its lineage, and a CNY cross says the parity band check did not
    run. LINEAGE NOTES, not reason codes: they change no state (PD-0036), and they stand on every metric computed from those rates, valued or not."""
    out = []
    for prefix, key in FX_NOTE_PREFIXES:
        found = sorted(n for n in notes if n.startswith(prefix))
        if found:
            out.append((key, " | ".join(found)))
    return tuple(out)


def _with_fx_lineage(metrics: Sequence[ComputedMetric], notes: Iterable[str]) -> Tuple[ComputedMetric, ...]:
    extra = _fx_lineage(notes)
    if not extra:
        return tuple(metrics)
    return tuple(dataclasses.replace(m, lineage=tuple(sorted(set(m.lineage) | set(extra)))) for m in metrics)


def _period_metric(metric_id: str, valued: Valued, rounding, window: WindowUsed, synthetic: bool, conformant: bool,
                   currency: Optional[CurrencyCode], point: RoundingPoint, unit: str, lineage=(), details=(),
                   numeric_basis: str = RATIONAL) -> ComputedMetric:
    return build_metric(metric_id, "PERIOD", (), valued, currency, rounding, window, WINDOW_METHOD_ID, synthetic, conformant, tuple(lineage),
                        point=point, unit=unit, numeric_basis=numeric_basis, details=tuple(details))


def _window_flows(run: _Run, events: Sequence[SequencedEvent], ledger_version: int, base: datetime.date, end: datetime.date, reporting_currency: CurrencyCode,
                  port: MarketDataPort, market_conventions: ConventionSet, conventions: PerformanceConventionSet,
                  account_scope: Optional[uuid.UUID]) -> List[ValuedFlow]:
    """The external flows of `(base, end]`, each valued at its own date (Ruling 4.3)."""
    classified = classify_events(events, ledger_version, conventions.flows, account_scope)
    return [
        value_flow(c, reporting_currency, port, run.resolver, market_conventions, conventions, run.use,
                   # CP3-1: in-kind flows respect the suppressions (and carried taint); performance/1.5 Ruling 1.1a item 3: so does a transfer out whose relief record
                   # holds a tainted portion (its event-level taint is a one-day suppression of its own position)
                   suppressions=run.suppressions + ((run.event_taints[c.event_id],) if c.event_id in run.event_taints else ()),
                   calendar_id_of=run.calendar_id_of)
        for c in external_flows(classified, base, end)]


def compute_window(
    events: Sequence[SequencedEvent], ledger_version: int, spec: WindowSpec, end: datetime.date, reporting_currency: CurrencyCode,
    port: MarketDataPort, resolver: InstrumentResolverPort, market_conventions: ConventionSet,
    conventions: PerformanceConventionSet, *, suppressions: Sequence[SuppressionInput],
    portfolio_id: Optional[uuid.UUID] = None, account_scope: Optional[uuid.UUID] = None,
    verify_identities: bool = False, detection: str = "CALLER_SUPPLIED", detection_policy: Tuple[Tuple[str, str], ...] = (),
) -> ComputationResult:
    """The absolute gain `G`, the TWR and the annualized TWR over the window declared by `spec` ending at `end` (`performance/1.0` Rulings 5, 7).

    `verify_identities=True` also computes the DAILY product and the daily gain sum and requires them to equal the segment results EXACTLY (identities I-2 and I-3,
    Ruling 11.1); a failed identity is an engine fault: the metric is INSUFFICIENT_DATA + CALCULATION_ERROR. It values every day of the window, so it is off by default."""
    events = tuple(events)
    rounding, conformant = conventions.rounding, conventions.is_conformant
    run = _Run(events, ledger_version, reporting_currency, port, resolver, market_conventions, conventions, suppressions,
               account_scope, None, None, detection, detection_policy)
    inception = inception_of(events, ledger_version, account_scope)
    resolved = resolve_window(spec, end, inception, NOT_RECONSTRUCTABLE)
    if resolved.window is None:
        window = resolved.declared or WindowUsed(end, end, None, spec.rule.value, spec.months)  # the declared window travels even when refused
        manifest = _manifest(None, events, ledger_version, end, window, reporting_currency, market_conventions, conventions,
                             ValuationMode.HISTORICAL_AS_OF, portfolio_id, suppressions, account_scope, synthetic_port=port,
                             detection=detection, identity_digest=run.resolver.digest(), detection_policy=detection_policy)
        assert resolved.cause is not None
        valued = Valued(INSUFFICIENT, resolved.reason, None, (resolved.cause,))
        syn = manifest.synthetic
        metrics = tuple(sorted((
            _period_metric("gain_absolute", valued, rounding, window, syn, conformant, reporting_currency, RoundingPoint.PRESENT_MONEY,
                           "CURRENCY_AMOUNT"),
            _period_metric("return_twr", valued, rounding, window, syn, conformant, None, RoundingPoint.PRESENT_RETURN, "RATIO"),
            _period_metric("return_annualized", valued, rounding, window, syn, conformant, None, RoundingPoint.PRESENT_RETURN,
                           "RATE_PER_YEAR"),
            _period_metric("return_mwr", valued, rounding, window, syn, conformant, None, RoundingPoint.PRESENT_RETURN, "RATIO"),
            _period_metric("return_mwr_annualized", valued, rounding, window, syn, conformant, None, RoundingPoint.PRESENT_RETURN, "RATE_PER_YEAR"),
        ) + tuple(_period_metric(lines.METRIC_ID[ln], valued, rounding, window, syn, conformant, reporting_currency, RoundingPoint.PRESENT_MONEY,
                                 "CURRENCY_AMOUNT") for ln in lines.LINES), key=lambda m: m.metric_id))
        return seal(manifest, metrics)

    window = resolved.window
    base = window.start
    flows = _window_flows(run, events, ledger_version, base, end, reporting_currency, port, market_conventions, conventions, account_scope)
    twr = twr_segments(base, end, flows, run.total, conventions)
    gain = absolute_gain(base, end, flows, run.total, conventions)
    years = year_fraction(base, end)
    annual = annualize(twr.valued, years, conventions)
    twr_valued, gain_valued, twr_details = twr.valued, gain, list(twr.details)
    mwr = mwr_period(base, end, flows, run.total, conventions)  # Ruling 6: inputs are V_B, V_E and the flows
    mwr_valued = mwr.valued

    # performance/1.2 Q5: lineage records which identities ran and what each said ("NOT_RUN": not required in a TWR/G-only call; "NOT_COMPUTABLE": an interior
    # day has no value, so the check cannot run, which is not a pass)
    i2 = i3 = "NOT_RUN"
    if verify_identities:
        i2 = i3 = "NOT_COMPUTABLE"
        if twr_valued.exact is not None:
            daily = daily_twr_factor(base, end, flows, run.total)
            if daily is not None:
                i2 = "PASS" if daily - 1 == twr_valued.exact else "FAIL"
                if i2 == "FAIL":
                    twr_valued = _identity_failure("I-2: the daily product differs from the segment product", twr_valued)
                    annual = annualize(twr_valued, years, conventions)
        if gain_valued.exact is not None:
            total = daily_gain_sum(base, end, flows, run.total)
            if total is not None:
                i3 = "PASS" if total == gain_valued.exact else "FAIL"
                if i3 == "FAIL":
                    gain_valued = _identity_failure("I-3: the sum of the daily gains differs from G", gain_valued)

    # Identity I-6 (Ruling 11.1; run whenever an MWR and a TWR are computed over the same window): `f(1) = G` always; and with no flow strictly inside the window
    # the period MWR equals the TWR EXACTLY. "NOT_APPLICABLE": an interior flow; "NOT_COMPUTABLE": an input is missing (a check that cannot run is not a pass).
    i6 = "NOT_COMPUTABLE"
    if mwr_valued.exact is not None and gain_valued.exact is not None and twr_valued.exact is not None:
        f_of_one = sum((cf for _tau, cf in mwr.flows), Fraction(0))
        if f_of_one != gain_valued.exact:
            i6 = "FAIL"
        elif mwr.interior:
            i6 = "NOT_APPLICABLE"
        else:
            i6 = "PASS" if mwr_valued.exact == twr_valued.exact else "FAIL"
        if i6 == "FAIL":
            mwr_valued = _identity_failure("I-6: the MWR differs from the TWR with no interior flow, or f(1) differs from G", mwr_valued)
    elif mwr_valued.exact is not None and gain_valued.exact is not None:
        i6 = "PASS" if sum((cf for _tau, cf in mwr.flows), Fraction(0)) == gain_valued.exact else "FAIL"
        if i6 == "FAIL":
            mwr_valued = _identity_failure("I-6: f(1) differs from G", mwr_valued)
    annual_mwr = annualize(mwr_valued, years, conventions)

    # Rulings 8.1 to 8.6: the amounts of the five lines over (B, E], each in its own state
    line_values = {ln: lines.line_amount(run.live, ln, base, end, reporting_currency, port, market_conventions, conventions, run.use, account_scope)
                   for ln in lines.LINES}

    synthetic = run.use.synthetic
    lineage = [("flow_days", str(len({f.event.event_date for f in flows}))), ("external_flows", str(len(flows))), ("identity:I-2", i2)]
    lineage += [(f"factor:{label}", f"{factor.numerator}/{factor.denominator}") for label, factor in twr.factors]
    manifest = dataclasses.replace(
        _manifest(run, events, ledger_version, end, window, reporting_currency, market_conventions, conventions,
                  ValuationMode.HISTORICAL_AS_OF, portfolio_id, suppressions, account_scope),
        identities_run=(("I-2", "I-3") if verify_identities else ()) + ("I-6",))
    mwr_basis = RATIONAL if mwr.rational else DECIMAL_PREC50
    annual_mwr_basis = mwr_basis if annual_mwr.rational else DECIMAL_PREC50  # Y = 1: the annualized figure IS the period figure, of the same basis
    amount_metrics = tuple(
        _period_metric(lines.METRIC_ID[ln], valued, rounding, window, synthetic, conformant, reporting_currency, RoundingPoint.PRESENT_MONEY,
                       "CURRENCY_AMOUNT", (), details)
        for ln, (valued, details) in line_values.items())
    metrics = (
        _period_metric("gain_absolute", gain_valued, rounding, window, synthetic, conformant, reporting_currency,
                       RoundingPoint.PRESENT_MONEY, "CURRENCY_AMOUNT", [("external_flows", str(len(flows))), ("identity:I-3", i3)]),
        _period_metric("return_twr", twr_valued, rounding, window, synthetic, conformant, None, RoundingPoint.PRESENT_RETURN, "RATIO",
                       lineage, twr_details),
        _period_metric("return_annualized", annual.valued, rounding, window, synthetic, conformant, None, RoundingPoint.PRESENT_RETURN,
                       "RATE_PER_YEAR", [("year_fraction", f"{years.numerator}/{years.denominator}")], annual.details,
                       RATIONAL if annual.rational else DECIMAL_PREC50),
        _period_metric("return_mwr", mwr_valued, rounding, window, synthetic, conformant, None, RoundingPoint.PRESENT_RETURN, "RATIO",
                       [("identity:I-6", i6), ("investor_flows", str(len(mwr.flows)))], mwr.details, mwr_basis),
        _period_metric("return_mwr_annualized", annual_mwr.valued, rounding, window, synthetic, conformant, None, RoundingPoint.PRESENT_RETURN,
                       "RATE_PER_YEAR", [("year_fraction", f"{years.numerator}/{years.denominator}")], annual_mwr.details, annual_mwr_basis),
    ) + amount_metrics
    return seal(manifest, _with_fx_lineage(tuple(sorted(metrics, key=lambda m: m.metric_id)), run.use.fx_notes))


def compute_return_series(
    events: Sequence[SequencedEvent], ledger_version: int, request: Union[WindowSpec, MaxAvailable], end: datetime.date, frequency: Frequency, boundary_rule: BoundaryRule,
    reporting_currency: CurrencyCode, port: MarketDataPort, resolver: InstrumentResolverPort, market_conventions: ConventionSet,
    conventions: PerformanceConventionSet, *, suppressions: Sequence[SuppressionInput], portfolio_id: Optional[uuid.UUID] = None,
    account_scope: Optional[uuid.UUID] = None, verify_identities: bool = True, detection: str = "CALLER_SUPPLIED", detection_policy: Tuple[Tuple[str, str], ...] = (),
) -> SeriesResult:
    """The periodic return series for the request (`WindowSpec`, or `MaxAvailable`) ending at `end`, at `frequency`, on the grid points `boundary_rule` gives (`risk/1.0` Rulings 2.1 to 2.5; tech plan 17.15).

    The spine of the risk engine and nothing else: it returns period TWRs (each a `twr_segments` over its own period, so the CP3 states, freshness and flow handling apply unchanged), with no statistic computed.
    A request that cannot be served is REFUSED with its detail, never shortened (`WINDOW_BEFORE_INCEPTION`, `WINDOW_BEFORE_SNAPSHOT`, `NO_FULL_PERIOD`): `MaxAvailable` is the separate, labelled request for the
    longest computable window. No period is merged, dropped or filled. The manifest is the CP3 `ComputationManifest` of the window question with `series.*` pairs in `numerics` (the request, the frequency, the grid
    rule id, the grid points' digest, the MAX_AVAILABLE start), so all of them are part of `manifest_id`.

    `verify_identities` (default True: `risk/1.0` Ruling 2.1 says RS-1 runs in every product call) runs I-10 (linking) and I-11 (coverage) and RAISES `SeriesIdentityError` on a failure: an engine fault is never a metric."""
    events = tuple(events)
    run = _Run(events, ledger_version, reporting_currency, port, resolver, market_conventions, conventions, suppressions, account_scope, None, None, detection, detection_policy)
    inception = inception_of(events, ledger_version, account_scope)
    max_available = isinstance(request, MaxAvailable)
    spec = WindowSpec(WindowRule.SINCE_INCEPTION) if max_available else request
    rule_name = MAX_AVAILABLE if max_available else spec.rule.value
    resolved = resolve_window(spec, end, inception, NOT_RECONSTRUCTABLE)
    pairs = [("series.frequency", frequency.value), ("series.boundary_rule", boundary_rule.rule_id), ("series.request", rule_name)]

    def refused(window: WindowUsed, cause: Cause, reason: Optional[str], extra: Tuple[Tuple[str, str], ...] = ()) -> SeriesResult:
        window = replace(window, frequency=frequency.value, rule=rule_name)
        manifest = _manifest(None, events, ledger_version, end, window, reporting_currency, market_conventions, conventions, ValuationMode.HISTORICAL_AS_OF, portfolio_id, suppressions,
                             account_scope, synthetic_port=port, detection=detection, identity_digest=run.resolver.digest(), detection_policy=detection_policy)
        manifest = replace(manifest, numerics=tuple(sorted(manifest.numerics + tuple(pairs) + extra)))
        return SeriesResult(manifest, None, SeriesRefusal(reason, cause), series_digest_of(window, reason, cause), ())

    if resolved.window is None:
        assert resolved.cause is not None
        return refused(resolved.declared or WindowUsed(end, end, None, rule_name, spec.months), resolved.cause, resolved.reason)
    requested = resolved.window
    dates = validate_boundaries(requested, boundary_rule.boundaries(frequency, requested))
    declared = effective_window(spec.rule.value, spec.months, frequency, requested.start, end, dates, boundary_rule.rule_id)
    if declared is None:
        cause = Cause("window", INSUFFICIENT.value, None, f"{NO_FULL_PERIOD}: the window ({requested.start.isoformat()}, {end.isoformat()}] holds no full {frequency.value} period", NO_FULL_PERIOD)
        return refused(requested, cause, None)
    flows = _window_flows(run, events, ledger_version, dates[0], dates[-1], reporting_currency, port, market_conventions, conventions, account_scope)
    series = build_series(declared, requested, dates, boundary_rule.rule_id, flows, run.total, conventions)
    identities: Tuple[Tuple[str, str], ...] = ()
    if verify_identities:
        link = link_identity(series, flows, run.total, conventions)
        identities = (("I-10", link.status), ("I-11", coverage_identity(series)))
        if FAIL in {s for _i, s in identities}:
            raise SeriesIdentityError(f"a series identity failed: {identities}")
    if max_available:
        truncated, cause = apply_max_available(series)
        if truncated is None:
            assert cause is not None
            return refused(requested, cause, None)  # the refusal declares the REQUEST's window (its base `B`: the since-inception base), as every other refusal does (cp4_golden part 3 R8-K1, R11-X1)
        series = truncated
    manifest = _manifest(run, events, ledger_version, end, series.window, reporting_currency, market_conventions, conventions, ValuationMode.HISTORICAL_AS_OF, portfolio_id,
                         suppressions, account_scope)
    g = series.grid
    pairs += [("series.boundaries_digest", boundaries_digest(series.boundaries)), ("series.requested_base", g.requested_base.isoformat()), ("series.requested_end", g.requested_end.isoformat())]
    if g.max_available_start is not None:
        pairs.append(("series.max_available_start", g.max_available_start + ("" if g.max_available_after is None else "@" + g.max_available_after.isoformat())))
    manifest = replace(manifest, identities_run=("I-10", "I-11") if verify_identities else (), numerics=tuple(sorted(manifest.numerics + tuple(pairs))))
    return SeriesResult(manifest, series, None, series.digest, identities)


def series_digest_of(window: WindowUsed, reason: Optional[str], cause: Cause) -> str:
    """The identity of a refused series: the digest of the refusal itself (the window it declared and the cause), so a refusal is as reproducible as a series."""
    return sha256_hex(canonical_json({"schema": SERIES_SCHEMA, "refused": True, "window": dict(window.to_obj(), frequency=None), "reason": reason, "cause": cause.to_obj()}).encode("utf-8"))


def compute_twr_between(
    events: Sequence[SequencedEvent], ledger_version: int, start: datetime.date, end: datetime.date, reporting_currency: CurrencyCode, port: MarketDataPort, resolver: InstrumentResolverPort,
    market_conventions: ConventionSet, conventions: PerformanceConventionSet, *, suppressions: Sequence[SuppressionInput], account_scope: Optional[uuid.UUID] = None,
    detection: str = "CALLER_SUPPLIED", detection_policy: Tuple[Tuple[str, str], ...] = (),
) -> Valued:
    """The TWR of `(start, end]` in segment form, from the TWR engine directly: one `twr_segments` over the window's own flows and the portfolio valuations it asks for (`risk/1.1` Ruling 1.4: RD-1 reconciles a
    drawdown against THIS, a window the series was not asked for). No clamping to inception and no window rule: the caller names two dates with `start < end`. Returns the `Valued` (state, exact value, causes)."""
    if not start < end:
        raise ValueError("a TWR window needs start < end")
    events = tuple(events)
    run = _Run(events, ledger_version, reporting_currency, port, resolver, market_conventions, conventions, suppressions, account_scope, None, None, detection, detection_policy)
    flows = _window_flows(run, events, ledger_version, start, end, reporting_currency, port, market_conventions, conventions, account_scope)
    return twr_segments(start, end, flows, run.total, conventions).valued


def compute_gains(
    events: Sequence[SequencedEvent], ledger_version: int, as_of: datetime.date, reporting_currency: CurrencyCode, port: MarketDataPort,
    resolver: InstrumentResolverPort, market_conventions: ConventionSet, conventions: PerformanceConventionSet, *,
    suppressions: Sequence[SuppressionInput], window: Optional[WindowSpec] = None, portfolio_id: Optional[uuid.UUID] = None,
    account_scope: Optional[uuid.UUID] = None, detection: str = "CALLER_SUPPLIED", detection_policy: Tuple[Tuple[str, str], ...] = (),
    as_of_rule: str = "CALLER", instant: Optional[datetime.datetime] = None, view: Optional[MarketView] = None,
) -> ComputationResult:
    """Realized and unrealized gain, remaining basis, the since-acquisition split and the gain aggregates (CP3d; performance Rulings 3.3a to 3.10 and 9.7) at `as_of`, for the sales of
    `window` (default: since inception). The lots and the relief records are those of the ONE lot fold's FIFO/1 mode (`ledger-replay/1.5`); this function relieves nothing itself.
    Realized figures are per SELL in `(B, E]` (REPORTING and NATIVE views) plus the window total; unrealized figures are per position at `as_of`, plus the total, and `remaining_basis`
    and `since_acquisition` (per remaining lot). Identities: I-5 (lot conservation, checked at every relief by the fold) and I-8 (the since-acquisition parts sum to the lot's gain)."""
    events = tuple(events)
    run = _Run(events, ledger_version, reporting_currency, port, resolver, market_conventions, conventions, suppressions, account_scope, None, view, detection, detection_policy)
    val = run.valuation(as_of)
    fifo = reconstruct_fifo(events, as_of, ledger_version)
    spec = window or WindowSpec(WindowRule.SINCE_INCEPTION)
    inception = inception_of(events, ledger_version, account_scope)
    resolved = resolve_window(spec, as_of, inception, NOT_RECONSTRUCTABLE)
    as_of_window = WindowUsed(as_of, as_of)
    env = gains.GainsEnv(reporting_currency, port, market_conventions, conventions, run.use, run.suppressions)
    fault = bool(fifo.conservation_failures)
    synthetic = run.use.synthetic

    def factory(w: WindowUsed) -> gains.MetricFactory:
        return gains.MetricFactory(env, conventions.rounding, w, GAINS_METHOD_ID, synthetic, conventions.is_conformant, fault)

    metrics: List[ComputedMetric] = []
    holdings = {(h.account_id, h.listing_id): h for h in val.holdings}
    books = {k: b for k, b in fifo.books.items() if account_scope is None or k[0] == account_scope}
    i5 = ("identity:I-5", "FAIL" if fault else "PASS")

    # realized: each SELL dated in (B, E], then the window total
    win = resolved.window
    sale_gains: List[gains.SaleGain] = []
    if win is not None:
        sales = [i.event for i in run.live if i.event.event_type is EventType.SELL and i.event.amount is not None and win.start < i.event.event_date <= win.end
                 and (account_scope is None or i.event.account_id == account_scope)]
        for e in sorted(sales, key=lambda e: (e.event_date, str(e.event_id))):
            relief = fifo.relief(e.event_id)
            if relief is None:
                continue
            sale_gains.append(gains.realized_gain(env, e, relief))
        f = factory(win)
        for sg in sale_gains:
            e = sg.event
            subject = (("event", str(e.event_id)),)
            labels = gains._labels(sg.lots) + (("account", str(e.account_id)), ("listing", str(e.listing_id)), i5)
            metrics.append(f.make("realized_gain", "REPORTING", subject, sg.reporting, reporting_currency, labels, details=sg.details))
            metrics.append(f.make("realized_gain", "NATIVE", subject, sg.native, e.currency, labels, details=sg.details))
        metrics.append(f.make("realized_gain_total", "REPORTING", (), gains.realized_total(env, sale_gains), reporting_currency,
                              (("caveat.lot_method", gains.BROKER_DIFFERENCE_LABEL), i5)))
    else:
        refused = Valued(INSUFFICIENT, resolved.reason, None, (resolved.cause,) if resolved.cause is not None else ())
        metrics.append(factory(resolved.declared or as_of_window).make("realized_gain_total", "REPORTING", (), refused, reporting_currency))

    # unrealized, remaining basis, since acquisition: per position at as_of
    f0 = factory(as_of_window)
    position_gains: List[gains.PositionGains] = []
    for key in sorted(books, key=lambda k: (k[0].int, k[1].int)):
        book = books[key]
        pg = gains.position_gains(env, book, holdings.get(key), as_of)
        position_gains.append(pg)
        subject = (("account", str(key[0])), ("listing", str(key[1])))
        labels = gains._labels(book.lots) + (i5,)
        h = pg.holding
        metrics.append(f0.make("remaining_basis", "REPORTING", subject, pg.remaining_reporting, reporting_currency, labels, details=pg.details["remaining.reporting"]))
        rn = pg.remaining_native_state
        if rn.exact is not None and pg.remaining_native:
            for ccy in sorted(pg.remaining_native, key=lambda c: c.code):
                metrics.append(f0.make("remaining_basis", "NATIVE", subject + (("currency", ccy.code),),
                                       Valued(rn.state, rn.reason, pg.remaining_native[ccy], rn.causes), ccy, labels))
        else:
            metrics.append(f0.make("remaining_basis", "NATIVE", subject, rn, None, labels, details=pg.details["remaining.native"]))
        metrics.append(f0.make("unrealized_gain", "REPORTING", subject, pg.ug_reporting, reporting_currency, labels, details=pg.details["ug.reporting"]))
        metrics.append(f0.make("unrealized_gain", "NATIVE", subject, pg.ug_native, None if h is None else h.native_currency, labels, details=pg.details["ug.native"]))
        for lot in book.lots:
            sa = gains.since_acquisition(env, book, lot, h, as_of)
            breakdown: Tuple = ()
            if sa.valued.exact is not None and sa.parts:
                decimals = conventions.rounding.money_decimals(reporting_currency)  # type: ignore[attr-defined]
                if decimals is not None:
                    shown = apportion(sa.valued.exact, list(sa.parts), decimals)
                    breakdown = tuple((name, to_decimal_money(s, decimals), x) for name, s, x in zip(gains.SINCE_ACQUISITION_LINES, shown, sa.parts))
            metrics.append(f0.make("since_acquisition", "REPORTING", subject + (("lot", gains.lot_id_text(lot)),), sa.valued, reporting_currency,
                                   gains._labels([lot]) + (("identity:I-8", _i8_status(sa)),), breakdown=breakdown))
    metrics.append(f0.make("unrealized_gain_total", "REPORTING", (), gains.unrealized_total(env, position_gains), reporting_currency,
                           (("caveat.lot_method", gains.BROKER_DIFFERENCE_LABEL), i5)))

    manifest = _manifest(run, events, ledger_version, as_of, win or resolved.declared or as_of_window, reporting_currency, market_conventions, conventions, ValuationMode.HISTORICAL_AS_OF, portfolio_id,
                         suppressions, account_scope, as_of_rule, instant)
    pairs = tuple(sorted((k, FIFO_REPLAY_ID if k == "ledger_replay" else v) for k, v in manifest.conventions))
    manifest = dataclasses.replace(manifest, conventions=pairs, identities_run=("I-5", "I-8"), synthetic=run.use.synthetic)
    return seal(manifest, _with_fx_lineage(tuple(sorted(metrics, key=lambda m: (m.metric_id, m.view, m.subject))), run.use.fx_notes))


def compute_attribution(
    events: Sequence[SequencedEvent], ledger_version: int, spec: WindowSpec, end: datetime.date, reporting_currency: CurrencyCode,
    port: MarketDataPort, resolver: InstrumentResolverPort, market_conventions: ConventionSet, conventions: PerformanceConventionSet, *,
    suppressions: Sequence[SuppressionInput], portfolio_id: Optional[uuid.UUID] = None, account_scope: Optional[uuid.UUID] = None,
    detection: str = "CALLER_SUPPLIED", detection_policy: Tuple[Tuple[str, str], ...] = (),
    as_of_rule: str = "CALLER", instant: Optional[datetime.datetime] = None, view: Optional[MarketView] = None,
) -> ComputationResult:
    """Attribution over the window declared by `spec` ending at `end` (`performance/1.8` Rulings 9.1 to 9.6; CP3e): the eight exact daily money lines summed over the window
    (`attribution_money`, with the apportioned display values of Ruling 2.4), the Carino-linked percentage components (`attribution_return`) and the breakdowns of every line by listing,
    component, currency, account and market (`attribution_breakdown`). Identities I-2, I-3, I-4 and I-9 run in EVERY call; a failed one is an engine fault. The window results
    (`compute_window`) are unchanged by this entry."""
    events = tuple(events)
    rounding, conformant = conventions.rounding, conventions.is_conformant
    run = _Run(events, ledger_version, reporting_currency, port, resolver, market_conventions, conventions, suppressions, account_scope, None, view, detection, detection_policy)
    inception = inception_of(events, ledger_version, account_scope)
    resolved = resolve_window(spec, end, inception, NOT_RECONSTRUCTABLE)
    identities = ("I-2", "I-3", "I-4", "I-9")

    def refused_result(window: WindowUsed, valued: Valued, details: Tuple[str, ...] = (), run_used: Optional[_Run] = None) -> ComputationResult:
        manifest = dataclasses.replace(
            _manifest(run_used, events, ledger_version, end, window, reporting_currency, market_conventions, conventions, ValuationMode.HISTORICAL_AS_OF, portfolio_id, suppressions,
                      account_scope, as_of_rule, instant, synthetic_port=port, detection=detection, view=view, identity_digest=run.resolver.digest(),
                      detection_policy=detection_policy),
            identities_run=identities)
        syn = manifest.synthetic
        return seal(manifest, (
            build_metric("attribution_money", "REPORTING", (), valued, reporting_currency, rounding, window, ATTRIBUTION_METHOD_ID, syn, conformant, details=details),
            build_metric("attribution_return", "PERIOD", (), valued, None, rounding, window, ATTRIBUTION_METHOD_ID, syn, conformant, point=RoundingPoint.PRESENT_RETURN,
                         unit="RATIO", details=details)))

    if resolved.window is None:
        assert resolved.cause is not None
        return refused_result(resolved.declared or WindowUsed(end, end, None, spec.rule.value, spec.months), Valued(INSUFFICIENT, resolved.reason, None, (resolved.cause,)))
    window = resolved.window
    base = window.start
    flows = _window_flows(run, events, ledger_version, base, end, reporting_currency, port, market_conventions, conventions, account_scope)
    all_days = [base + datetime.timedelta(days=i) for i in range((end - base).days + 1)]
    totals = {d: run.total(d) for d in all_days}
    parts: List[Part] = [totals[d].as_part(f"valuation@{d.isoformat()}") for d in all_days]
    parts += [f.valued.as_part(f"flow:{f.event.event_id}") for f in flows if base < f.event.event_date <= end]
    agg = conventions.aggregation.combine(parts)
    if agg.state is INSUFFICIENT:  # Ruling 9.5: every day's valuation and every flow is an input
        return refused_result(window, Valued(INSUFFICIENT, agg.reason, None, agg.causes), run_used=run)

    lookups = attribution.Lookups(reporting_currency, port, market_conventions, run.resolver, run.use, None, run.calendar_id_of, run.suppressions, run.event_taints)
    data = attribution.daily_lines(run.live, base, end, run.valuation, flows, lookups, conventions, account_scope)
    fresh = data.freshness
    for d in all_days:
        fresh = fresh.union(totals[d].freshness)
    for f in flows:
        fresh = fresh.union(f.valued.freshness)
    agg = conventions.aggregation.combine(parts + list(data.parts))
    if agg.state is INSUFFICIENT:
        return refused_result(window, Valued(INSUFFICIENT, agg.reason, None, agg.causes, fresh), run_used=run)

    m_k = attribution.window_lines(data)
    g_window = sum(m_k, Fraction(0))
    dr = attribution.daily_returns(data)
    twr = twr_segments(base, end, flows, run.total, conventions)
    i9 = "PASS"
    for day_val in (run.valuation(base), run.valuation(end)):
        status = attribution.cash_identity(run.live, day_val, account_scope)
        if status == "FAIL":
            i9 = "FAIL"
        elif status == "NOT_COMPUTABLE" and i9 == "PASS":
            i9 = "NOT_COMPUTABLE"
    i2 = "NOT_COMPUTABLE"
    if dr.product is not None and twr.valued.exact is not None:
        i2 = "PASS" if dr.product - 1 == twr.valued.exact else "FAIL"
    elif dr.product is not None and twr.valued.exact is None:
        i2 = "NOT_COMPUTABLE"
    faults: List[str] = []
    if data.i4 == "FAIL":
        faults.append(data.i4_failure)
    if data.i3 == "FAIL":
        faults.append("I-3: the sum of the daily gains differs from G")
    if i9 == "FAIL":
        faults.append("I-9: the replayed cash differs from the sum of the cash effects")
    if i2 == "FAIL":
        faults.append("I-2: the daily product differs from the segment product")
    status_lineage = (("identity:I-2", i2), ("identity:I-3", data.i3), ("identity:I-4", data.i4), ("identity:I-9", i9))
    synthetic = run.use.synthetic
    decimals = rounding.money_decimals(reporting_currency)  # type: ignore[attr-defined]
    metrics: List[ComputedMetric] = []

    # money (Ruling 9.3): the exact window lines and their apportioned display values (Ruling 2.4 item 3)
    money = Valued(agg.state, agg.reason, g_window, agg.causes, fresh)
    breakdown: Tuple = ()
    if faults:
        money = _identity_failure("; ".join(faults), money)
    elif decimals is not None:
        shown = apportion(g_window, list(m_k), decimals)
        breakdown = tuple((line, to_decimal_money(s, decimals), exact) for line, s, exact in zip(attribution.LINE_IDS, shown, m_k))
    metrics.append(build_metric("attribution_money", "REPORTING", (), money, reporting_currency, rounding, window, ATTRIBUTION_METHOD_ID, synthetic, conformant,
                                status_lineage + (("days", str(len(data.days))),), breakdown=breakdown))

    # percentage (Ruling 9.4): Carino-linked components that reconcile to the TWR
    components: Optional[Tuple[Fraction, ...]] = None
    ret_details: Tuple[str, ...] = ()
    ret_lineage = status_lineage + (("days", str(len(data.days))), ("zero_capital_days", str(dr.zero_capital_days)), ("components_basis", DECIMAL_PREC50))
    ret = Valued(agg.state, agg.reason, None if dr.product is None else dr.product - 1, agg.causes, fresh) if dr.product is not None else None
    if faults:
        ret = _identity_failure("; ".join(faults), Valued(agg.state, agg.reason, Fraction(0), agg.causes, fresh))
    elif dr.product is None:
        bad = insufficient_part(f"attribution@{(dr.failure_day or end).isoformat()}", None,
                                f"{dr.failure}: the day's capital base is not positive" if dr.failure == attribution.NON_POSITIVE_BASE
                                else f"{dr.failure}: the value fell below zero", dr.failure)
        agg_bad = conventions.aggregation.combine(parts + list(data.parts) + [bad])
        ret, ret_details = Valued(INSUFFICIENT, agg_bad.reason, None, agg_bad.causes, fresh), (dr.failure,)
    else:
        link = carino_link(dr.factors, dr.product - 1)
        if link is None:
            bad = insufficient_part("attribution:carino", None, f"{attribution.TOTAL_LOSS}: a day's return or the TWR is -1, so there is no logarithm", attribution.TOTAL_LOSS)
            agg_bad = conventions.aggregation.combine(parts + list(data.parts) + [bad])
            ret, ret_details = Valued(INSUFFICIENT, agg_bad.reason, None, agg_bad.causes, fresh), (attribution.TOTAL_LOSS,)
        elif abs(link.residual) > CARINO_RESIDUAL_BOUND:
            ret = _identity_failure("Carino: the linked components differ from the TWR by more than 1E-40", Valued(agg.state, agg.reason, Fraction(0), agg.causes, fresh))
        else:
            components = tuple(Fraction(c) for c in link.components)
            ret_lineage += (("carino_residual", str(link.residual)),)
    ret_breakdown: Tuple = ()
    if components is not None and ret is not None and ret.exact is not None:
        shown_c = []
        for line, c in zip(attribution.LINE_IDS, components):
            p = present(c, RoundingPoint.PRESENT_RETURN, None, rounding, IRRATIONAL_WIDTH)
            if p.status is not PresentStatus.OK or p.decimal is None:
                ret = Valued(INSUFFICIENT, CALCULATION_ERROR, None, sorted_causes(ret.causes + (Cause("presentation", INSUFFICIENT.value, CALCULATION_ERROR, "VALUE_NOT_REPRESENTABLE", "VALUE_NOT_REPRESENTABLE"),)), fresh)
                shown_c = []
                break
            shown_c.append((line, p.decimal, c))
        ret_breakdown = tuple(shown_c)
    metrics.append(build_metric("attribution_return", "PERIOD", (), ret, None, rounding, window, ATTRIBUTION_METHOD_ID, synthetic, conformant, ret_lineage,
                                point=RoundingPoint.PRESENT_RETURN, unit="RATIO", breakdown=ret_breakdown, details=ret_details))

    # breakdowns (Ruling 9.6): every line by every grouping; the parts sum to the line exactly; each part is presented on its own (Ruling 2.4 item 2)
    mics: Dict[str, str] = {}

    def market_of(listing: str) -> str:
        if listing not in mics:
            mic = run.resolver.exchange_mic(uuid.UUID(listing))
            mics[listing] = mic or "?"
        return mics[listing]

    # performance/1.9 Ruling 9.6: a breakdown is a decomposition object: its total is the line's apportioned DISPLAY value in the money attribution above, its parts are apportioned to it
    # (Ruling 2.4 item 3) in the fixed order of the ruling, and the exact parts stay in the breakdown's exact column
    displayed = {line: Fraction(shown) for line, shown, _exact in breakdown}
    if not faults and decimals is not None and displayed:
        for line, line_total in zip(attribution.LINE_IDS, m_k):
            for group in attribution.GROUPS:
                parts_g = attribution.breakdown_parts(data, line, group, market_of)
                if sum((e for _n, e in parts_g), Fraction(0)) != line_total:
                    raise ValueError(f"the parts of {line} by {group} do not sum to the line")  # an engine defect, never a presented number
                shown_parts_g = apportion_displayed(displayed[line], [e for _n, e in parts_g], decimals)
                shown_parts = tuple((name, to_decimal_money(s, decimals), exact) for (name, exact), s in zip(parts_g, shown_parts_g))
                metrics.append(build_metric("attribution_breakdown", "REPORTING", (("group_by", group), ("line", line)), Valued(agg.state, agg.reason, line_total, agg.causes, fresh),
                                            reporting_currency, rounding, window, ATTRIBUTION_METHOD_ID, synthetic, conformant,
                                            (("displayed_total", str(to_decimal_money(displayed[line], decimals))), ("part_order", "performance/1.9#9.6")), breakdown=shown_parts))  # type: ignore[arg-type]
    manifest = dataclasses.replace(
        _manifest(run, events, ledger_version, end, window, reporting_currency, market_conventions, conventions, ValuationMode.HISTORICAL_AS_OF, portfolio_id, suppressions, account_scope,
                  as_of_rule, instant),
        identities_run=identities)
    return seal(manifest, _with_fx_lineage(tuple(sorted(metrics, key=lambda m: (m.metric_id, m.view, m.subject))), run.use.fx_notes))


def _i8_status(sa: "gains.SinceAcquisition") -> str:
    """Identity I-8 (the since-acquisition parts sum to the lot's gain, exactly): `PASS` when a value exists and its parts sum to it; `FAIL` when the check failed (the metric is then
    INSUFFICIENT_DATA + CALCULATION_ERROR); `NOT_COMPUTABLE` when no value exists for another reason (a suppressed, unknown or unpriced lot has no parts to relate)."""
    if sa.valued.exact is not None:
        return "PASS" if not sa.parts or sum(sa.parts, Fraction(0)) == sa.valued.exact else "FAIL"
    return "FAIL" if sa.valued.reason == CALCULATION_ERROR else "NOT_COMPUTABLE"


def _identity_failure(note: str, valued: Valued) -> Valued:
    cause = Cause("identity", INSUFFICIENT.value, CALCULATION_ERROR, f"IDENTITY_FAILED: {note}", "IDENTITY_FAILED")
    return Valued(INSUFFICIENT, CALCULATION_ERROR, None, sorted_causes(valued.causes + (cause,)), valued.freshness)


def reproduce(
    manifest: ComputationManifest, expected_result_digest: Optional[str], events: Sequence[SequencedEvent],
    port: MarketDataPort, resolver: InstrumentResolverPort, market_conventions: ConventionSet,
    conventions: PerformanceConventionSet, *, suppressions: Sequence[SuppressionInput],
    market_at: Optional[MarketAtInstant] = None,
) -> ReproductionReport:
    """Re-run a manifest (tech plan 16.2). Cheap checks first, so a wrong input is named before anything is recomputed. `suppressions` has no default (CP3-4).
    The re-run uses the manifest's own `identities_run`, `split_detection` and (Current mode) instant, so the same question is asked again; the identity registry
    facts (CP3-6) are compared with the manifest's."""
    S = ReproductionStatus
    if ledger_digest(events, manifest.ledger_version) != manifest.ledger_digest:
        return ReproductionReport(S.LEDGER_DIGEST_MISMATCH, "the live events at the pinned version differ from the manifest")
    expected_release = manifest.parent_release_id if manifest.parent_release_id is not None else manifest.release_id  # Current mode: `M` (the port), not `M_t`
    if expected_release is not None and port.release_id() != expected_release:
        return ReproductionReport(S.RELEASE_MISMATCH, f"the port is bound to {port.release_id()}")
    if _convention_pairs(market_conventions, conventions) != manifest.conventions:
        return ReproductionReport(S.CONVENTION_MISMATCH, "the injected convention ids differ from the manifest's")
    if suppressions_digest(suppressions) != manifest.split_suppressions_digest:
        return ReproductionReport(S.SUPPRESSIONS_MISMATCH, "the suppressions differ from the manifest's")
    if (manifest.valuation_mode == ValuationMode.CURRENT_AT_INSTANT.value) != (manifest.as_of_rule == "D_c(t)"):
        return ReproductionReport(S.MANIFEST_DIFFERS, "the manifest's valuation_mode and as_of_rule disagree (a mode difference is a manifest difference)")
    if not manifest.source_registry_digest:  # a check that cannot run is not a pass (Ruling 11.1 (1.2)); "" is never a match, not even against ""
        return ReproductionReport(S.SOURCE_REGISTRY_MISMATCH, "registry not pinned: the manifest carries no source_registry_digest")
    portfolio = None if manifest.portfolio_id is None else uuid.UUID(manifest.portfolio_id)
    account = None if manifest.scope == "PORTFOLIO" else uuid.UUID(manifest.scope.split(":", 1)[1])
    reporting = CurrencyCode(manifest.reporting_currency)
    w = manifest.window
    detection, policy = manifest.split_detection, manifest.detection_policy
    is_gains, is_attribution = "I-8" in manifest.identities_run, "I-4" in manifest.identities_run  # CP3d / CP3e manifests re-ask their own question
    if is_gains or is_attribution:
        spec = None if w.rule == "AS_OF" else WindowSpec(WindowRule(w.rule), w.months if w.rule == WindowRule.TRAILING_MONTHS.value else None,
                                                         w.start if w.rule == WindowRule.CUSTOM.value else None)
        port_used, conv_used, extra = port, market_conventions, {}
        if manifest.as_of_rule == "D_c(t)":  # Current mode: over M_t, as the service computed it
            if market_at is None or manifest.instant is None:
                raise ValueError("reproducing a Current-mode manifest needs `market_at` (M_t) and the recorded instant")
            view = market_at.view(manifest.instant)
            port_used, conv_used = view.port, view.conventions
            extra = {"as_of_rule": "D_c(t)", "instant": manifest.instant, "view": view}
            resolver = RecordingResolver.wrap(resolver)
            # the date choice asked the identity registry too (the service records those facts): ask again, and the chosen date must be the manifest's
            chosen = choose_current_date(manifest.instant, events, manifest.ledger_version, view.calendars, resolver.exchange_mic, reporting, resolver.trading_currency)
            if chosen.date != manifest.as_of:
                return ReproductionReport(S.MANIFEST_DIFFERS, f"D_c(t) is {chosen.date} over this M_t, the manifest says {manifest.as_of}")
        if is_gains:
            rerun = compute_gains(events, manifest.ledger_version, manifest.as_of, reporting, port_used, resolver, conv_used, conventions, suppressions=suppressions, window=spec,
                                  portfolio_id=portfolio, account_scope=account, detection=detection, detection_policy=policy, **extra)
        else:
            assert spec is not None
            rerun = compute_attribution(events, manifest.ledger_version, spec, manifest.as_of, reporting, port_used, resolver, conv_used, conventions, portfolio_id=portfolio,
                                        suppressions=suppressions, account_scope=account, detection=detection, detection_policy=policy, **extra)
    elif manifest.as_of_rule == "D_c(t)":
        if market_at is None or manifest.instant is None:
            raise ValueError("reproducing a Current-mode manifest needs `market_at` (M_t) and the recorded instant")
        rerun = compute_current(events, manifest.ledger_version, manifest.instant, reporting, resolver, market_at, conventions,
                                suppressions=suppressions, portfolio_id=portfolio, account_scope=account, detection=detection, detection_policy=policy)
    elif w.rule == "AS_OF":
        rerun = compute(events, manifest.ledger_version, manifest.as_of, reporting, port, resolver, market_conventions, conventions,
                        portfolio_id=portfolio, suppressions=suppressions, mode=ValuationMode(manifest.valuation_mode),
                        account_scope=account, detection=detection, detection_policy=policy)
    else:
        rule = WindowRule(w.rule)
        spec = WindowSpec(rule, w.months if rule is WindowRule.TRAILING_MONTHS else None,
                          w.start if rule is WindowRule.CUSTOM else None)
        rerun = compute_window(events, manifest.ledger_version, spec, manifest.as_of, reporting, port, resolver, market_conventions,
                               conventions, portfolio_id=portfolio, suppressions=suppressions, account_scope=account,
                               verify_identities="I-2" in manifest.identities_run, detection=detection, detection_policy=policy)
    if rerun.manifest.identity_digest != manifest.identity_digest:
        return ReproductionReport(S.IDENTITY_MISMATCH, "the identity registry facts the re-run used differ from the manifest's", rerun)
    if rerun.manifest.valuation_mode != manifest.valuation_mode:
        return ReproductionReport(S.MANIFEST_DIFFERS, f"the re-run's valuation_mode is {rerun.manifest.valuation_mode}, the manifest's {manifest.valuation_mode}", rerun)
    if not rerun.manifest.source_registry_digest:
        return ReproductionReport(S.SOURCE_REGISTRY_MISMATCH, "registry not pinned: the re-run carries no source_registry_digest", rerun)
    if rerun.manifest.source_registry_digest != manifest.source_registry_digest:
        return ReproductionReport(S.SOURCE_REGISTRY_MISMATCH, "the source registry records the re-run used differ from the manifest's (performance/1.12 Ruling 1.7 item 4)", rerun)
    cited, read = set(manifest.consumed_files()), set(rerun.manifest.consumed_files())
    if read - cited:
        return ReproductionReport(S.FILE_NOT_CITED, f"the re-run read {len(read - cited)} file(s) the manifest does not cite", rerun)
    if cited - read:
        return ReproductionReport(S.FILE_NOT_READ, f"the manifest cites {len(cited - read)} file(s) the re-run did not read", rerun)
    if rerun.manifest.manifest_id != manifest.manifest_id:
        return ReproductionReport(S.MANIFEST_DIFFERS, "the re-run's manifest differs", rerun)
    if expected_result_digest is None:
        return ReproductionReport(S.RESULT_NOT_COMPARED, "no expected result digest was given: the inputs agree but the answer was not compared", rerun)
    if rerun.result_digest != expected_result_digest:
        return ReproductionReport(S.RESULT_DIFFERS, "the result digest differs", rerun)
    return ReproductionReport(S.REPRODUCED, "", rerun)
