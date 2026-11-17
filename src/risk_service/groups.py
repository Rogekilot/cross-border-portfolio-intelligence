"""UAT-03 (tech plan 17.21, 17.23; PRD FR-018): changing the benchmark recomputes ONLY the benchmark-dependent group, and no stale result stays labelled current.

The metrics split into two GROUPS by what they read (Ruling 8.1 and the registry):
- the INDEPENDENT group (volatility, downside deviation, maximum drawdown, Sharpe, Sortino): a function of the ledger at its pinned version, `M`, the request and the risk-free series. The user's benchmark selection is not
  an input, so choosing, changing or clearing a benchmark cannot change a digit of it;
- the BENCHMARK group (the benchmark return, beta, R-squared, alpha, active return, tracking error, the information ratio): a function of those AND the selection log at its pinned version.

A `RiskView` holds one result per group with the PINS each was computed at: the ledger version, the selection version, the market-data RELEASE, the AS-OF date (or Current-mode instant) and the portfolio's REPORTING
CURRENCY (CP4F-7: all five are inputs of every metric, so a view is CURRENT only if none has moved). The caller states the release and the as-of it asks about (the service cannot know which release the caller would
compute against now); the ledger and selection versions and the reporting currency are read from the database as it is NOW.

`refresh` recomputes the benchmark group when, and only when, the selection version alone has moved, and hands back the independent group's result UNCHANGED (the same object, the same digests: the proof that nothing
it depends on moved); a moved ledger, release, as-of or reporting currency recomputes both. `status` labels a view: `CURRENT` only when every pin is what it is now; otherwise the label names what moved
(`STALE_SELECTION`, `STALE_LEDGER`, `STALE_LEDGER_AND_SELECTION`, `STALE_RELEASE`, `STALE_AS_OF`, `STALE_REPORTING_CURRENCY`, or `STALE_MULTIPLE`): a result is never left labelled current after its inputs moved.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple, Union

from persistence import benchmark_selection_store as selection_store
from persistence import ledger_replay_store
from risk.engine import BENCHMARK_DEPENDENT, COMPUTABLE
from risk.manifest import RiskResult
from risk_service.service import RiskRefusal, ServiceResult, currency_of

CURRENT = "CURRENT"
STALE_SELECTION = "STALE_SELECTION"
STALE_LEDGER = "STALE_LEDGER"
STALE_BOTH = "STALE_LEDGER_AND_SELECTION"
STALE_RELEASE = "STALE_RELEASE"
STALE_AS_OF = "STALE_AS_OF"
STALE_CURRENCY = "STALE_REPORTING_CURRENCY"
STALE_MULTIPLE = "STALE_MULTIPLE"

#: the two groups of metric ids (the benchmark group is the engine's own set; the independent group is the rest)
BENCHMARK_GROUP: Tuple[str, ...] = tuple(sorted(BENCHMARK_DEPENDENT))
INDEPENDENT_GROUP: Tuple[str, ...] = tuple(sorted(set(COMPUTABLE) - set(BENCHMARK_DEPENDENT)))

#: `compute(metrics, ledger_version, selection_version) -> ServiceResult`: the caller binds the request, the frequency, the port and the rest (and so the release and the as-of)
Compute = Callable[[Tuple[str, ...], Optional[int], Optional[int]], ServiceResult]
AsOf = Union[datetime.date, datetime.datetime]


@dataclass(frozen=True)
class RiskView:
    ledger_version: int
    selection_version: int
    independent: ServiceResult
    benchmark: ServiceResult
    release_id: str
    as_of: AsOf
    reporting_currency: str


def _pins(conn: Any, portfolio_id: uuid.UUID) -> Tuple[int, int, str]:
    return (ledger_replay_store.current_ledger_version(conn, portfolio_id), selection_store.current_selection_version(conn, portfolio_id), currency_of(conn, portfolio_id).code)


def _checked(result: ServiceResult, release_id: str, as_of: AsOf, currency: str) -> ServiceResult:
    """A result must be for the release, the as-of and the currency the view says (a refusal names none, and is left as it is)."""
    if isinstance(result, RiskRefusal):
        return result
    series = result.manifest.series
    current = result.manifest.current
    if series.reporting_currency != currency:
        raise ValueError(f"the computed result is in {series.reporting_currency}, the portfolio's reporting currency is {currency}")
    if current is None:  # historical: the release `M` and the date `E`
        if series.release_id not in (None, release_id):
            raise ValueError(f"the computed result is over release {series.release_id}, the view says {release_id}")
        if isinstance(as_of, datetime.datetime) or result.manifest.end != as_of:
            raise ValueError(f"the computed result ends {result.manifest.end}, the view says {as_of}")
    else:  # Current mode (CP4F-14): the parent release `M` and the instant `t`
        if current.parent_release_id != release_id:
            raise ValueError(f"the computed result is over release {current.parent_release_id}, the view says {release_id}")
        if current.instant != as_of:
            raise ValueError(f"the computed result is at {current.instant}, the view says {as_of}")
    return result


def _both(ledger: int, selection: int, currency: str, release_id: str, as_of: AsOf, compute: Compute) -> RiskView:
    independent = _checked(compute(INDEPENDENT_GROUP, ledger, selection), release_id, as_of, currency)
    benchmark = _checked(compute(BENCHMARK_GROUP, ledger, selection), release_id, as_of, currency)
    return RiskView(ledger, selection, independent, benchmark, release_id, as_of, currency)


def compute_view(conn: Any, portfolio_id: uuid.UUID, compute: Compute, *, release_id: str, as_of: AsOf) -> RiskView:
    """Both groups at the CURRENT pins (read once, so both groups are of one state of the world), for the release and the as-of the caller states."""
    ledger, selection, currency = _pins(conn, portfolio_id)
    return _both(ledger, selection, currency, release_id, as_of, compute)


def moved(conn: Any, portfolio_id: uuid.UUID, view: RiskView, *, release_id: str, as_of: AsOf) -> Tuple[str, ...]:
    """Which inputs of `view` are not what they are now, in a fixed order: LEDGER, SELECTION, RELEASE, AS_OF, REPORTING_CURRENCY."""
    ledger, selection, currency = _pins(conn, portfolio_id)
    out = []
    if ledger != view.ledger_version:
        out.append("LEDGER")
    if selection != view.selection_version:
        out.append("SELECTION")
    if release_id != view.release_id:
        out.append("RELEASE")
    if as_of != view.as_of:
        out.append("AS_OF")
    if currency != view.reporting_currency:
        out.append("REPORTING_CURRENCY")
    return tuple(out)


def refresh(conn: Any, portfolio_id: uuid.UUID, previous: RiskView, compute: Compute, *, release_id: str, as_of: AsOf) -> RiskView:
    """The view at the pins as they are now. The selection version alone moved: the benchmark group is recomputed and the independent group is returned UNCHANGED. Anything else moved (the ledger, the release, the
    as-of, the reporting currency): both are recomputed, for every one of them is an input of both. Nothing moved: `previous`."""
    ledger, selection, currency = _pins(conn, portfolio_id)
    changed = moved(conn, portfolio_id, previous, release_id=release_id, as_of=as_of)
    if not changed:
        return previous
    if changed == ("SELECTION",):
        return RiskView(ledger, selection, previous.independent, _checked(compute(BENCHMARK_GROUP, ledger, selection), release_id, as_of, currency), release_id, as_of, currency)
    return _both(ledger, selection, currency, release_id, as_of, compute)


def status(conn: Any, portfolio_id: uuid.UUID, view: RiskView, *, release_id: str, as_of: AsOf) -> str:
    """The label a surface may put on `view` NOW: `CURRENT` only if the ledger version, the selection version, the release, the as-of and the reporting currency are all what they are now."""
    changed = moved(conn, portfolio_id, view, release_id=release_id, as_of=as_of)
    if not changed:
        return CURRENT
    if changed == ("LEDGER", "SELECTION"):
        return STALE_BOTH
    if len(changed) > 1:
        return STALE_MULTIPLE
    return {"LEDGER": STALE_LEDGER, "SELECTION": STALE_SELECTION, "RELEASE": STALE_RELEASE, "AS_OF": STALE_AS_OF, "REPORTING_CURRENCY": STALE_CURRENCY}[changed[0]]


def digests(view: RiskView) -> Tuple[Optional[str], Optional[str]]:
    """The two result digests (None for a refusal): what a test compares to prove which group moved."""
    return tuple(None if isinstance(r, RiskRefusal) else r.result_digest for r in (view.independent, view.benchmark))  # type: ignore[return-value]
