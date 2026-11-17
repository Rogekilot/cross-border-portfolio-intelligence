"""The risk engine's entry: `compute_risk` and `reproduce_risk` (`risk/1.2`; tech plan 17.7.6, 17.16).

A PURE function of the live ledger events at a pinned version L, a `MarketDataPort` bound to one release M, the injected conventions, the two reference catalogs and, for a benchmark metric, the selection log at a
pinned version S. It never writes anything, never reads a clock and chooses no convention: every grid, window, threshold, annualization and state is the text of `risk/1.2`, in the modules below.

THE FLOW. (1) the portfolio leg: `performance.engine.compute_return_series` on the grid (a refused window is a refusal, never a clipped one); (2) the risk-free leg, if a metric uses the rate; (3) the benchmark leg,
if a metric uses the benchmark (the selection in force at S, the catalog, the series in M); (4) each metric from exact values (`risk.single`), its state from the parts of Ruling 7.3; (5) the identities that must
hold exactly (RD-1 against the TWR engine, RD-3, RQ-1; the series' I-10 and I-11); (6) the Risk Manifest and the result digest.

BUILT: volatility, downside deviation, maximum drawdown, Sharpe, Sortino, the benchmark return and (CP4d, `risk.relative`) beta, R-squared, Jensen's alpha, active return, tracking error and the information ratio, each
two-leg metric with its comparability disclosure (Ruling 8, `risk.comparability`). NOT BUILT HERE: the default view (Ruling 7.7, a service-level composition) and Current mode; asking for a metric that is not built is
a `ValueError`, never a silent omission.

This is the ONLY risk module that imports `performance.engine`: the orchestration needs the portfolio leg and the TWR engine for RD-1, nothing else does.
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from domain.benchmark_selection import SelectionInForce, SelectionPin, SelectionState, SequencedSelection, pin_of, resolve_selection
from domain.catalogs import BenchmarkCatalog, RiskFreeCatalog
from domain.currency import CurrencyCode
from domain.replay import SequencedEvent
from marketdata.canonical import canonical_json, sha256_hex
from marketdata.conventions import ConventionSet
from marketdata.manifest import FileRef
from marketdata.port import InstrumentResolverPort, MarketDataPort
from performance.conventions import PerformanceConventionSet
from performance.current import choose_current_date
from performance.engine import compute_return_series, compute_twr_between, series_digest_of
from performance.inputs import MarketAtInstant, MarketView, SuppressionInput, suppressions_digest
from performance.ledger_view import ledger_digest
from performance.periods import WindowRule, WindowSpec
from performance.results import Cause, Part
from performance.series import BoundaryRule, Frequency, MaxAvailable, SeriesRefusal, SeriesResult, WeekdayFridayMonthEndGrid
from risk import states as S
from risk.benchmark import BenchmarkLeg, BenchmarkRefusal, open_benchmark
from risk.manifest import (
    BenchmarkBlock,
    CurrentBlock,
    RiskFreeBlock,
    RiskManifest,
    RiskReproductionReport,
    RiskReproductionStatus,
    RiskResult,
    seal,
)
from risk.registry import REGISTRY, RiskRegistry
from risk.relative import RATE_DEPENDENT_RELATIVE, RELATIVE_METRICS, relative_metrics
from risk.results import BenchmarkRef, RiskMetric
from risk.risk_free import PeriodRate, refuse_unadmitted, risk_free_rates, source_probe
from risk.single import (
    BENCHMARK_RETURN,
    PERIODS_PER_YEAR,
    RATE_DEPENDENT,
    SINGLE_SERIES_METRICS,
    Declared,
    MetricBuilder,
    SingleInputs,
    Value,
    count_parts,
    single_series_metrics,
    window_part,
)

RISK_ENGINE_ID = "risk/cp4i-0.3"  # bumped on ANY change to a computation (cp4i-0.2: the registry it loads moved to risk/1.10, a label re-issue of risk/1.9 with no computation change; cp4i-0.3: it moved to risk/1.11, the same for market-data/1.16, with no computation change); `RISK_ENGINE_PINS` in test_risk_boundaries pins the source hashes so a change cannot be silent
COMPUTABLE: Tuple[str, ...] = tuple(sorted(SINGLE_SERIES_METRICS + (BENCHMARK_RETURN,) + RELATIVE_METRICS))
BENCHMARK_DEPENDENT = frozenset({BENCHMARK_RETURN}) | frozenset(RELATIVE_METRICS)


def _request_of(request: Union[WindowSpec, MaxAvailable]) -> Tuple[str, Optional[int], Optional[datetime.date]]:
    if isinstance(request, MaxAvailable):
        return "MAX_AVAILABLE", None, None
    return request.rule.value, request.months, request.custom_base


def _periods_digest(rates: Sequence[PeriodRate]) -> str:
    rows = [[r.start, r.end, r.quote_date, r.missed_publications, r.valued.state.value, r.valued.reason, r.exact, r.series_id] for r in rates]
    return sha256_hex(canonical_json(rows).encode("utf-8"))


def _identity_rows(series: SeriesResult, metrics: Sequence[RiskMetric]) -> Tuple[Tuple[str, str], ...]:
    rows = set(series.identities)
    for m in metrics:
        for key, value in m.lineage:
            if key.startswith("identity:"):
                rows.add((key.split(":", 1)[1], value))
    return tuple(sorted(rows))


def _benchmark_context(
    benchmark_catalog: BenchmarkCatalog, in_force: SelectionInForce, port: MarketDataPort, reporting: CurrencyCode, market_conventions: ConventionSet, end: Optional[datetime.date],
    instant: Optional[datetime.datetime] = None, refused_window_as_of: Optional[datetime.date] = None,
) -> Tuple[BenchmarkRef, Optional[BenchmarkLeg], Optional[BenchmarkRefusal], SelectionPin]:
    """Ruling 5.6: the selection in force, the catalog entry, and the leg (or why there is none). Precedence: no selection or a cleared one; an id the catalog does not list or M does not hold; a price-return series.
    `end` is `g_n`; None when the window was refused. Then `refused_window_as_of` (the request's `E`) asks the window-independent causes only (Ruling 7.3 (1.5)): a series not in M, a binding the entry fails, a
    price-return series; whatever would need a grid date (coverage, staleness, a withheld day) is not asked, and a usable series gives no leg."""
    pin = pin_of(in_force)
    entry = None if in_force.state is not SelectionState.IN_FORCE else benchmark_catalog.get(pin.benchmark_id)

    def make_ref(entry_values: bool, source_id: Optional[str] = None, synthetic: Optional[bool] = None) -> BenchmarkRef:
        """`source_id` and `synthetic` are the SERIES' OWN (CP4M-3: never the catalog's); the other fields are the catalog's, and only while the entry describes the series that was read."""
        e = entry if entry_values else None
        return BenchmarkRef(
            benchmark_id=pin.benchmark_id, selection_id=pin.selection_id, selection_seq=pin.selection_seq, selection_version=pin.version, catalog_id=benchmark_catalog.catalog_id,
            return_basis=None if e is None else e.return_basis.value, currency=None if e is None else e.currency,
            currency_treatment=None if e is None else ("NONE (benchmark already in R)" if e.currency == reporting.code else "TRANSLATED_UNHEDGED (ECB fixing u(g))"),
            name=None if e is None else e.name, provider=None if e is None else e.provider, source_id=source_id, synthetic=synthetic)

    if in_force.state is not SelectionState.IN_FORCE:
        why = "no benchmark has been selected" if in_force.state is SelectionState.NONE else "the selection was cleared"
        return make_ref(True), None, BenchmarkRefusal(S.MISSING_BENCHMARK, S.NO_BENCHMARK_SELECTED, f"{S.NO_BENCHMARK_SELECTED}: {why} (selection log version {pin.version}); no benchmark is ever substituted"), pin
    assert pin.benchmark_id is not None
    if end is None:  # the window was refused: no grid date to read a level at
        if refused_window_as_of is not None:
            probed = open_benchmark(entry, pin.benchmark_id, port, reporting, market_conventions, refused_window_as_of, instant)
            if isinstance(probed, BenchmarkRefusal):
                return make_ref(probed.entry_bound), None, probed, pin
        return make_ref(True), None, None, pin
    opened = open_benchmark(entry, pin.benchmark_id, port, reporting, market_conventions, end, instant)
    if isinstance(opened, BenchmarkRefusal):
        return make_ref(opened.entry_bound), None, opened, pin
    return make_ref(True, opened.source_id, opened.series_synthetic), opened, None, pin


def compute_risk(
    events: Sequence[SequencedEvent], ledger_version: int, request: Union[WindowSpec, MaxAvailable], end: datetime.date, frequency: Frequency, reporting_currency: CurrencyCode,
    port: MarketDataPort, resolver: InstrumentResolverPort, market_conventions: ConventionSet, conventions: PerformanceConventionSet, *, suppressions: Sequence[SuppressionInput],
    risk_free_catalog: Optional[RiskFreeCatalog] = None, benchmark_catalog: Optional[BenchmarkCatalog] = None, selections: Sequence[SequencedSelection] = (), selection_version: int = 0,
    portfolio_id: Optional[uuid.UUID] = None, metrics: Optional[Iterable[str]] = None, account_scope: Optional[uuid.UUID] = None, boundary_rule: Optional[BoundaryRule] = None,
    verify_identities: bool = True, registry: RiskRegistry = REGISTRY, detection: str = "CALLER_SUPPLIED", detection_policy: Tuple[Tuple[str, str], ...] = (),
    current: Optional["CurrentContext"] = None,
) -> RiskResult:
    """The requested metrics (default: every metric built so far) over the request ending at `end`, at `frequency`. `risk_free_catalog` is required if a metric uses the rate; `benchmark_catalog`, `portfolio_id`
    and the selection log (`selections` at `selection_version`) if one uses the benchmark. `verify_identities` (default True) runs RD-1 against the TWR engine and the series' I-10 and I-11: a failed series
    identity RAISES (an engine fault is never a metric); a failed RD-1, RD-3 or RQ-1 is INSUFFICIENT_DATA + CALCULATION_ERROR on that metric (Ruling 1.4)."""
    wanted = tuple(sorted(set(COMPUTABLE if metrics is None else metrics)))
    unknown = [m for m in wanted if m not in COMPUTABLE]
    if unknown:
        raise ValueError(f"not built in this increment (or not a risk metric): {unknown}; built: {list(COMPUTABLE)}")
    if not wanted:
        raise ValueError("no metric was asked for")
    needs_rate = any(m in RATE_DEPENDENT or m in RATE_DEPENDENT_RELATIVE for m in wanted)
    needs_benchmark = any(m in BENCHMARK_DEPENDENT for m in wanted)
    if needs_rate and risk_free_catalog is None:
        raise ValueError("a risk-free metric needs the risk-free catalog (Ruling 4.6: no catalog, no admitted series)")
    if needs_benchmark and (benchmark_catalog is None or portfolio_id is None):
        raise ValueError("a benchmark metric needs the benchmark catalog and the portfolio id (the selection is the portfolio's, Ruling 5.6)")
    rule = boundary_rule or WeekdayFridayMonthEndGrid()
    series_result = compute_return_series(events, ledger_version, request, end, frequency, rule, reporting_currency, port, resolver, market_conventions, conventions, suppressions=suppressions,
                                          portfolio_id=portfolio_id, account_scope=account_scope, verify_identities=verify_identities, detection=detection, detection_policy=detection_policy)
    if current is not None and current.gap is not None:  # `D_c(t)` could not be chosen (a governing calendar does not cover a candidate date): no series, whatever the metric (performance Ruling 1.7)
        refused = SeriesRefusal(None, current.gap)
        series_result = dataclasses.replace(series_result, series=None, refusal=refused, series_digest=series_digest_of(series_result.manifest.window, None, current.gap), identities=())
    series, refusal = series_result.series, series_result.refusal
    sm = series_result.manifest
    if series is not None:
        g = series.grid
        declared = Declared(frequency.value, g.rule, g.months, g.requested_base, g, sm.synthetic)
    else:
        w = sm.window
        declared = Declared(frequency.value, w.rule, w.months, w.start, None, sm.synthetic)

    # Ruling 7.3 (1.5): a refused WINDOW (before inception, before the snapshot) still evaluates the window-independent causes: no selection, a series not in M, a price-return series, no risk-free source
    window_refused = series is None and refusal is not None and refusal.cause.detail in (S.WINDOW_BEFORE_INCEPTION, S.WINDOW_BEFORE_SNAPSHOT)

    # the risk-free leg
    rates: Optional[Tuple[PeriodRate, ...]] = None
    rate_series_id: Optional[str] = None
    rate_probe: Optional[PeriodRate] = None
    if needs_rate and series is not None:
        assert risk_free_catalog is not None
        rates = refuse_unadmitted(risk_free_rates(port, reporting_currency, series.boundaries, market_conventions, None if current is None else current.instant), risk_free_catalog, reporting_currency)
        rate_series_id = next((r.series_id for r in rates if r.series_id is not None), None)
    elif needs_rate and window_refused:
        assert risk_free_catalog is not None
        rate_probe = source_probe(port, reporting_currency, end, market_conventions, risk_free_catalog)

    # the benchmark leg
    ref: Optional[BenchmarkRef] = None
    leg: Optional[BenchmarkLeg] = None
    leg_refusal: Optional[BenchmarkRefusal] = None
    pin = None
    if needs_benchmark:
        assert benchmark_catalog is not None and portfolio_id is not None
        in_force = resolve_selection(portfolio_id, selections, selection_version)
        ref, leg, leg_refusal, pin = _benchmark_context(benchmark_catalog, in_force, port, reporting_currency, market_conventions, None if series is None else series.boundaries[-1],
                                                        None if current is None else current.instant, end if window_refused else None)

    def reconcile(start: datetime.date, stop: datetime.date):
        return compute_twr_between(events, ledger_version, start, stop, reporting_currency, port, resolver, market_conventions, conventions, suppressions=suppressions, account_scope=account_scope,
                                   detection=detection, detection_policy=detection_policy).exact

    def window_twr(start: datetime.date, stop: datetime.date):
        return compute_twr_between(events, ledger_version, start, stop, reporting_currency, port, resolver, market_conventions, conventions, suppressions=suppressions, account_scope=account_scope,
                                   detection=detection, detection_policy=detection_policy)

    single = [m for m in wanted if m in SINGLE_SERIES_METRICS]
    out: List[RiskMetric] = []
    if single:
        out += single_series_metrics(SingleInputs(series, refusal, rates, rate_series_id, rate_probe), declared, single, registry=registry, reconcile=reconcile if verify_identities else None)
    if BENCHMARK_RETURN in wanted:
        out.append(_benchmark_return(declared, registry, series, refusal, ref, leg, leg_refusal))
    relative = [m for m in wanted if m in RELATIVE_METRICS]
    if relative:
        out += relative_metrics(series, refusal, rates, rate_series_id, leg, leg_refusal, declared, relative, registry=registry, benchmark=ref, reconcile=reconcile if verify_identities else None,
                                calendars=getattr(market_conventions.freshness, "calendars", None), window_twr=window_twr, rate_probe=rate_probe)

    # the manifest
    rf_block: Optional[RiskFreeBlock] = None
    if rates is not None:
        assert risk_free_catalog is not None
        files = tuple(sorted({f for r in rates for f in r.consumed}))
        rf_block = RiskFreeBlock(reporting_currency.code, rate_series_id, files, risk_free_catalog.catalog_id, risk_free_catalog.digest, _periods_digest(rates), sm.synthetic)
    bm_block: Optional[BenchmarkBlock] = None
    if needs_benchmark:
        assert benchmark_catalog is not None and pin is not None and ref is not None
        entry = benchmark_catalog.get(ref.benchmark_id)
        consumed = tuple(sorted(set(leg.consumed) if leg is not None else set(leg_refusal.consumed) if leg_refusal is not None else set()))
        level_gn = fixing_gn = None
        if current is not None and leg is not None and series is not None:  # Ruling 5.8 item 6: for `g_n`, the benchmark day and the fixing date actually used
            at_gn = leg.level_at(series.boundaries[-1])
            level_gn, fixing_gn = at_gn.date_used, at_gn.fx_date_used
        bm_block = BenchmarkBlock(pin.to_obj(), ref.benchmark_id, benchmark_catalog.catalog_id, benchmark_catalog.digest, None if entry is None else entry.digest, consumed, ref.currency_treatment, sm.synthetic,
                                  level_gn, fixing_gn)
    code, months, custom_base = _request_of(request)
    numerics = (("periods_per_year", ",".join(f"{k}={v}" for k, v in sorted(PERIODS_PER_YEAR.items()))), ("rounding", "risk/1.2#3.4: 1e-12 half away from zero"), ("sqrt", "exact integer root, 12 digits"))
    manifest = RiskManifest(
        risk_engine_id=RISK_ENGINE_ID, registry_id=registry.registry_id, registry_digest=registry.digest, metrics=wanted, frequency=frequency.value, request_rule=code, request_months=months,
        request_base=custom_base, end=end, boundary_rule_id=rule.rule_id, series=sm, series_digest=series_result.series_digest, risk_free=rf_block, benchmark=bm_block,
        identities=_identity_rows(series_result, out), verify_identities=verify_identities, numerics=numerics, synthetic=sm.synthetic,
        current=None if current is None else CurrentBlock("CURRENT_AT_INSTANT", current.instant, "D_c(t)", None if current.gap is not None else end, current.causes, current.parent_release_id, current.excluded_files))
    return seal(manifest, tuple(out))


@dataclass(frozen=True)
class CurrentContext:
    """Current mode (`performance` Ruling 1.7 (1.12), `risk` Ruling 5.8): the instant `t`, `M` (the release the caller named), the hashes `M_t` leaves out, the causes of the date choice and, when `D_c(t)` could not be chosen,
    the cause that refuses every metric (no series; `CALENDAR_COVERAGE_GAP`, no reason code)."""

    instant: datetime.datetime
    parent_release_id: str
    excluded_files: Tuple[str, ...]
    causes: Tuple[str, ...] = ()
    gap: Optional[Cause] = None


def compute_risk_current(
    events: Sequence[SequencedEvent], ledger_version: int, request: Union[WindowSpec, MaxAvailable], instant: datetime.datetime, frequency: Frequency, reporting_currency: CurrencyCode,
    market_at: MarketAtInstant, resolver: InstrumentResolverPort, conventions: PerformanceConventionSet, *, suppressions: Union[Sequence[SuppressionInput], Callable[[MarketView], Sequence[SuppressionInput]]],
    **kw,
) -> RiskResult:
    """The metrics over the Current-mode view at `instant` (Ruling 5.8): `E = D_c(t)` resolved from the PORTFOLIO's inputs only (performance Ruling 1.7: the benchmark never moves `E`), every input read from `M_t`
    (the files of `M` retrieved at or before `t`; a calculation day or fixing not yet due at `t` is neither used nor missed). `suppressions` may be a function of the view (the F8-B detection runs over `M_t` too).
    All other arguments are `compute_risk`'s."""
    view = market_at.view(instant)
    chosen = choose_current_date(instant, tuple(events), ledger_version, view.calendars, resolver.exchange_mic, reporting_currency, resolver.trading_currency)
    sup = suppressions(view) if callable(suppressions) else suppressions
    gap = None if chosen.date is not None else (chosen.causes[0] if chosen.causes else None)
    ctx = CurrentContext(instant, view.parent_release_id, view.excluded_files, tuple(c.note for c in chosen.causes), gap)
    end = chosen.date if chosen.date is not None else instant.astimezone(datetime.timezone.utc).date()
    return compute_risk(events, ledger_version, request, end, frequency, reporting_currency, view.port, resolver, view.conventions, conventions, suppressions=sup, current=ctx, **kw)


def _benchmark_return(declared: Declared, registry: RiskRegistry, series, refusal, ref: Optional[BenchmarkRef], leg: Optional[BenchmarkLeg], leg_refusal: Optional[BenchmarkRefusal]) -> RiskMetric:
    """`benchmark_return` (Ruling 6.9): `L_R(g_n) / L_R(g_0) - 1`, the benchmark's total return over the EFFECTIVE window, read at `g_0` and `g_n` only. Single-leg: only the window and the benchmark's own states
    count (not the portfolio's periods)."""
    builder = MetricBuilder(declared, registry, ref)
    parts: List[Part] = []
    if series is None:
        assert refusal is not None
        parts.append(window_part(refusal))
        if leg_refusal is not None:
            parts.append(leg_refusal.part("benchmark"))
        return builder.build(BENCHMARK_RETURN, parts, None)
    if leg_refusal is not None:
        parts.append(leg_refusal.part("benchmark"))
        return builder.build(BENCHMARK_RETURN, parts, None)
    assert leg is not None and declared.n is not None
    g0, gn = series.boundaries[0], series.boundaries[-1]
    window = leg.period(g0, gn)
    parts.append(window.valued.as_part(f"benchmark:{g0.isoformat()}..{gn.isoformat()}"))
    parts += count_parts(registry, BENCHMARK_RETURN, declared.frequency, declared.n)
    lineage = [("benchmark_files", str(len(leg.consumed)))]
    value = None
    if window.exact is not None:
        first, last = leg.level_at(g0), leg.level_at(gn)
        a, b = first.translated, last.translated
        assert a is not None and b is not None and first.level is not None and last.level is not None
        # Ruling 9.4 (1.4), benchmark return: L(g_0), L(g_n) (the index's own levels), L_R(g_0), L_R(g_n) (translated: `level_g0`, `level_gn`), and, when the index is translated, the two translation rates and their
        # fixing dates. A benchmark already in the reporting currency has no rate and no fixing: none is recorded (CP4M-8)
        inter: List[Tuple[str, Union[Fraction, datetime.date]]] = [("index_level_g0", first.level), ("index_level_gn", last.level), ("level_g0", a), ("level_gn", b)]
        if first.fx_rate is not None and last.fx_rate is not None and first.fx_date_used is not None and last.fx_date_used is not None:
            inter += [("rate_g0", first.fx_rate), ("rate_gn", last.fx_rate), ("fixing_date_g0", first.fx_date_used), ("fixing_date_gn", last.fx_date_used)]
        value = Value(rational=window.exact, intermediates=tuple(inter))
    return builder.build(BENCHMARK_RETURN, parts, value, lineage=lineage)


def reproduce_risk(
    manifest: RiskManifest, expected_result_digest: Optional[str], events: Sequence[SequencedEvent], port: MarketDataPort, resolver: InstrumentResolverPort, market_conventions: ConventionSet,
    conventions: PerformanceConventionSet, *, suppressions: Sequence[SuppressionInput], risk_free_catalog: Optional[RiskFreeCatalog] = None, benchmark_catalog: Optional[BenchmarkCatalog] = None,
    selections: Sequence[SequencedSelection] = (), registry: RiskRegistry = REGISTRY, boundary_rule: Optional[BoundaryRule] = None, market_at: Optional[MarketAtInstant] = None,
) -> RiskReproductionReport:
    """Re-ask a manifest's question against the supplied inputs. Cheap checks first, so a wrong input is named before anything is recomputed; `suppressions` has no default (CP3-4). The files the re-run reads are
    compared with the manifest's in both directions, per kind. No expected digest is `RESULT_NOT_COMPARED`, never `REPRODUCED`."""
    St = RiskReproductionStatus
    sm = manifest.series
    if ledger_digest(events, sm.ledger_version) != sm.ledger_digest:
        return RiskReproductionReport(St.LEDGER_DIGEST_MISMATCH, "the live events at the pinned version differ from the manifest")
    expected_release = manifest.current.parent_release_id if manifest.current is not None else sm.release_id  # Current mode: the port is `M`, the parent of `M_t`
    if manifest.current is not None and market_at is None:
        raise ValueError("reproducing a Current-mode risk manifest needs `market_at` (M_t) and the recorded instant")
    if expected_release is not None and port.release_id() != expected_release:
        return RiskReproductionReport(St.RELEASE_MISMATCH, f"the port is bound to {port.release_id()}")
    if (registry.registry_id, registry.digest) != (manifest.registry_id, manifest.registry_digest):
        return RiskReproductionReport(St.REGISTRY_MISMATCH, f"the registry is {registry.registry_id} {registry.digest[:12]}, the manifest says {manifest.registry_id} {manifest.registry_digest[:12]}")
    if suppressions_digest(suppressions) != sm.split_suppressions_digest:
        return RiskReproductionReport(St.SUPPRESSIONS_MISMATCH, "the suppressions differ from the manifest's")
    if manifest.risk_free is not None:
        if risk_free_catalog is None or (risk_free_catalog.catalog_id, risk_free_catalog.digest) != (manifest.risk_free.catalog_id, manifest.risk_free.catalog_digest):
            return RiskReproductionReport(St.CATALOG_MISMATCH, "the risk-free catalog differs from the manifest's")
    selection_version = 0
    portfolio_id = None if sm.portfolio_id is None else uuid.UUID(sm.portfolio_id)
    if manifest.benchmark is not None:
        if benchmark_catalog is None or (benchmark_catalog.catalog_id, benchmark_catalog.digest) != (manifest.benchmark.catalog_id, manifest.benchmark.catalog_digest):
            return RiskReproductionReport(St.CATALOG_MISMATCH, "the benchmark catalog differs from the manifest's")
        selection_version = int(manifest.benchmark.pin["version"])
        if portfolio_id is None or pin_of(resolve_selection(portfolio_id, selections, selection_version)).to_obj() != manifest.benchmark.pin:
            return RiskReproductionReport(St.SELECTION_MISMATCH, "the selection log at the manifest's version gives another pin")
    spec: Union[WindowSpec, MaxAvailable]
    if manifest.request_rule == "MAX_AVAILABLE":
        spec = MaxAvailable()
    else:
        rule = WindowRule(manifest.request_rule)
        spec = WindowSpec(rule, manifest.request_months if rule is WindowRule.TRAILING_MONTHS else None, manifest.request_base if rule is WindowRule.CUSTOM else None)
    account = None if sm.scope == "PORTFOLIO" else uuid.UUID(sm.scope.split(":", 1)[1])
    common = dict(suppressions=suppressions, risk_free_catalog=risk_free_catalog, benchmark_catalog=benchmark_catalog, selections=selections, selection_version=selection_version, portfolio_id=portfolio_id,
                  metrics=manifest.metrics, account_scope=account, boundary_rule=boundary_rule, verify_identities=manifest.verify_identities, registry=registry, detection=sm.split_detection,
                  detection_policy=sm.detection_policy)
    if manifest.current is not None:  # Current mode: over `M_t` at the recorded instant (the port is `M`, which the manifest names as its parent)
        rerun = compute_risk_current(events, sm.ledger_version, spec, manifest.current.instant, Frequency(manifest.frequency), CurrencyCode(sm.reporting_currency), market_at, resolver, conventions, **common)
    else:
        rerun = compute_risk(events, sm.ledger_version, spec, manifest.end, Frequency(manifest.frequency), CurrencyCode(sm.reporting_currency), port, resolver, market_conventions, conventions, **common)
    rm = rerun.manifest
    if rm.series.conventions != sm.conventions:
        return RiskReproductionReport(St.CONVENTION_MISMATCH, "the injected convention ids differ from the manifest's", rerun)
    if rm.series.identity_digest != sm.identity_digest:
        return RiskReproductionReport(St.IDENTITY_MISMATCH, "the identity registry facts the re-run used differ from the manifest's", rerun)
    if rm.series.source_registry_digest != sm.source_registry_digest:
        return RiskReproductionReport(St.SOURCE_REGISTRY_MISMATCH, "the source registry records the re-run used differ from the manifest's", rerun)
    for kind, not_cited, not_read in (("SERIES", St.FILE_NOT_CITED, St.FILE_NOT_READ), ("RISK_FREE", St.RISK_FREE_FILE_NOT_CITED, St.RISK_FREE_FILE_NOT_READ),
                                      ("BENCHMARK", St.BENCHMARK_FILE_NOT_CITED, St.BENCHMARK_FILE_NOT_READ)):
        cited, read = set(manifest.consumed_files(kind)), set(rm.consumed_files(kind))
        if read - cited:
            return RiskReproductionReport(not_cited, f"the re-run read {len(read - cited)} {kind.lower()} file(s) the manifest does not cite", rerun)
        if cited - read:
            return RiskReproductionReport(not_read, f"the manifest cites {len(cited - read)} {kind.lower()} file(s) the re-run did not read", rerun)
    if rm.manifest_id != manifest.manifest_id:
        return RiskReproductionReport(St.MANIFEST_DIFFERS, "the re-run's manifest differs", rerun)
    if expected_result_digest is None:
        return RiskReproductionReport(St.RESULT_NOT_COMPARED, "no expected result digest was given: the inputs agree but the answer was not compared", rerun)
    if rerun.result_digest != expected_result_digest:
        return RiskReproductionReport(St.RESULT_DIFFERS, "the result digest differs", rerun)
    return RiskReproductionReport(St.REPRODUCED, "", rerun)
