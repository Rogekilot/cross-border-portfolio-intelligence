"""The risk service: read the portfolio's ledger and benchmark selection from the database, run the split detection read-only, and call the engine (tech plan 17.21; the HG3 composition).

`compute_risk_for_portfolio` is the only door a USER's risk numbers leave through. It PINS two things in the database and nothing else (the engine is pure):
- the LEDGER at a version (`ledger_replay_store`: the default is the current committed one; a version inside an atomic append is refused), and
- the BENCHMARK SELECTION LOG at a version (`benchmark_selection_store`: the engine is handed exactly what `load_selections` returns, truncated at the pinned version with the loader's boundary facts; a version that cuts
  a correction pair is refused by the engine's one check). The selection is the PORTFOLIO's, at every scope (Ruling 5.6 (1.2)).

It also owns the gates that belong to a product and not to an engine, exactly as `performance_service` does (the same PM ruling, market-data Ruling 4.8 item 4): a USER portfolio is never computed from a market-data
version that holds a synthetic file; the F8-B detection (confirmation policy included) runs here, read-only, over the pinned ledger and the same `M` (or `M_t` in Current mode) and its suppressions go to the engine
with `detection="F8B_DRY_RUN"`. Fixtures and tests reach the engine directly, or pass `allow_synthetic=True` here: a LABELLED opt-in (the manifest and every result keep `synthetic=True`), never a product default.

`currency_of(conn, portfolio_id)` is the portfolio's reporting currency `R` (the risk-free rate's currency, Ruling 4.1; the benchmark's translation target), read from the `portfolio` row: it is data of the portfolio and
never a default.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Sequence, Tuple, Union

from corporate_actions_service import split_confirmation as f8b
from domain.benchmark_selection import SequencedSelection
from domain.catalogs import BenchmarkCatalog, RiskFreeCatalog
from domain.currency import CurrencyCode
from domain.replay import SequencedEvent
from marketdata.conventions import ConventionSet
from marketdata.port import InstrumentResolverPort, MarketDataPort
from performance.conventions import PerformanceConventionSet
from performance.inputs import MarketAtInstant, MarketView, SuppressionInput
from performance.periods import WindowSpec
from performance.series import BoundaryRule, Frequency, MaxAvailable
from performance_service import service as perf
from persistence import benchmark_selection_store as selection_store
from persistence import ledger_replay_store
from risk.engine import compute_risk, compute_risk_current
from risk.manifest import RiskResult

SYNTHETIC_MARKET_DATA_REFUSED = perf.SYNTHETIC_MARKET_DATA_REFUSED
DETECTION_POLICY_UNMATCHED = perf.DETECTION_POLICY_UNMATCHED
DETECTION = perf.DETECTION
PORTFOLIO_CURRENCY_SQL = "SELECT reporting_currency FROM portfolio WHERE portfolio_id = %s"


@dataclass(frozen=True)
class RiskRefusal:
    """A computation the SERVICE refuses before any number: INSUFFICIENT_DATA with an explicit code and the reason in words (never a manifest with a number). `code` is one of this module's two constants."""

    code: str
    note: str
    ledger_version: int

    state = "INSUFFICIENT_DATA"


ServiceResult = Union[RiskResult, RiskRefusal]


def currency_of(conn: Any, portfolio_id: uuid.UUID) -> CurrencyCode:
    """The portfolio's reporting currency (`R`), from its row. An unknown portfolio is `PortfolioNotFoundError`."""
    row = conn.execute(PORTFOLIO_CURRENCY_SQL, (portfolio_id,)).fetchone()
    if row is None:
        raise ledger_replay_store.PortfolioNotFoundError(f"portfolio {portfolio_id} does not exist")
    return CurrencyCode(row[0])


def pin_ledger(conn: Any, portfolio_id: uuid.UUID, ledger_version: Optional[int] = None) -> Tuple[int, Tuple[SequencedEvent, ...]]:
    """The ledger events at a pinned version: the current committed one by default; above it is `LedgerVersionNotCommittedError`; inside an atomic append `LedgerVersionNotABoundaryError`."""
    return perf.pin_ledger_events(conn, portfolio_id, ledger_version)


def pin_selection(conn: Any, portfolio_id: uuid.UUID, selection_version: Optional[int] = None) -> Tuple[int, Tuple[SequencedSelection, ...]]:
    """The benchmark selection log at a pinned version: `(version, the rows at or below it)`. The default is the current committed version. A version above it is `SelectionVersionNotCommittedError`. The rows carry the
    loader's boundary facts, so a version that cuts a correction pair is refused by the engine (`SelectionVersionNotPinnableError`) however few rows it is given."""
    current = selection_store.current_selection_version(conn, portfolio_id)
    version = current if selection_version is None else selection_version
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise ValueError(f"selection_version must be an int >= 0, got {version!r}")
    if version > current:
        raise selection_store.SelectionVersionNotCommittedError(f"selection version {version} is above the portfolio's greatest committed {current}")
    return version, selection_store.load_selections(conn, portfolio_id, version)


def _gate(events: Sequence[SequencedEvent], pin: int, port: Any, policy: f8b.ConfirmationPolicy, allow_synthetic: bool) -> Optional[RiskRefusal]:
    """The checks before any number: a port that cannot say whether it holds synthetic files is treated as synthetic; the policy must recognise every source of M's corporate-action records (CP3-11)."""
    if getattr(port, "contains_synthetic", True) and not allow_synthetic:
        return RiskRefusal(SYNTHETIC_MARKET_DATA_REFUSED, "a user portfolio is never computed from a market-data version that holds a synthetic file (market-data Ruling 4.8 item 4)", pin)
    why = perf.policy_matches_nothing(events, pin, port, policy)
    if why is not None:
        return RiskRefusal(DETECTION_POLICY_UNMATCHED, why, pin)
    return None


def _suppressions(events: Sequence[SequencedEvent], pin: int, portfolio_id: uuid.UUID, port: Any, resolver: InstrumentResolverPort, market_conventions: ConventionSet,
                  policy: f8b.ConfirmationPolicy) -> Tuple[SuppressionInput, ...]:
    return perf.detect_suppressions(events, pin, portfolio_id, port, resolver, perf.calendars_of_conventions(market_conventions), policy)


def compute_risk_for_portfolio(
    conn: Any, portfolio_id: uuid.UUID, request: Union[WindowSpec, MaxAvailable], end: datetime.date, frequency: Frequency, port: MarketDataPort, resolver: InstrumentResolverPort,
    market_conventions: ConventionSet, conventions: PerformanceConventionSet, *, policy: f8b.ConfirmationPolicy, risk_free_catalog: Optional[RiskFreeCatalog] = None,
    benchmark_catalog: Optional[BenchmarkCatalog] = None, ledger_version: Optional[int] = None, selection_version: Optional[int] = None, metrics: Optional[Iterable[str]] = None,
    account_scope: Optional[uuid.UUID] = None, boundary_rule: Optional[BoundaryRule] = None, verify_identities: bool = True, allow_synthetic: bool = False,
) -> ServiceResult:
    """The risk metrics of a portfolio at a pinned ledger version and a pinned selection version, over `M`: the pins are read here, the detection runs read-only, and the PURE engine computes. The reporting currency is
    the portfolio's own (`currency_of`)."""
    reporting = currency_of(conn, portfolio_id)
    pin, events = pin_ledger(conn, portfolio_id, ledger_version)
    refusal = _gate(events, pin, port, policy, allow_synthetic)
    if refusal is not None:
        return refusal
    sel_version, rows = pin_selection(conn, portfolio_id, selection_version)
    suppressions = _suppressions(events, pin, portfolio_id, port, resolver, market_conventions, policy)
    return compute_risk(events, pin, request, end, frequency, reporting, port, resolver, market_conventions, conventions, suppressions=suppressions, risk_free_catalog=risk_free_catalog,
                        benchmark_catalog=benchmark_catalog, selections=rows, selection_version=sel_version, portfolio_id=portfolio_id, metrics=metrics, account_scope=account_scope,
                        boundary_rule=boundary_rule, verify_identities=verify_identities, detection=DETECTION, detection_policy=perf.policy_reference(policy))


def compute_risk_current_for_portfolio(
    conn: Any, portfolio_id: uuid.UUID, request: Union[WindowSpec, MaxAvailable], instant: datetime.datetime, frequency: Frequency, resolver: InstrumentResolverPort,
    market_at: MarketAtInstant, conventions: PerformanceConventionSet, *, policy: f8b.ConfirmationPolicy, risk_free_catalog: Optional[RiskFreeCatalog] = None,
    benchmark_catalog: Optional[BenchmarkCatalog] = None, ledger_version: Optional[int] = None, selection_version: Optional[int] = None, metrics: Optional[Iterable[str]] = None,
    account_scope: Optional[uuid.UUID] = None, boundary_rule: Optional[BoundaryRule] = None, verify_identities: bool = True, allow_synthetic: bool = False,
) -> ServiceResult:
    """The same over the Current-mode view at `instant` (Ruling 5.8): `E = D_c(t)`, every input from `M_t`, and the detection over `M_t` too."""
    reporting = currency_of(conn, portfolio_id)
    pin, events = pin_ledger(conn, portfolio_id, ledger_version)
    view = market_at.view(instant)
    refusal = _gate(events, pin, view.port, policy, allow_synthetic)
    if refusal is not None:
        return refusal
    sel_version, rows = pin_selection(conn, portfolio_id, selection_version)

    def suppressions(v: MarketView) -> Sequence[SuppressionInput]:
        return perf.detect_suppressions(events, pin, portfolio_id, v.port, resolver, v.calendars, policy)

    return compute_risk_current(events, pin, request, instant, frequency, reporting, market_at, resolver, conventions, suppressions=suppressions, risk_free_catalog=risk_free_catalog,
                                benchmark_catalog=benchmark_catalog, selections=rows, selection_version=sel_version, portfolio_id=portfolio_id, metrics=metrics, account_scope=account_scope,
                                boundary_rule=boundary_rule, verify_identities=verify_identities, detection=DETECTION, detection_policy=perf.policy_reference(policy))
