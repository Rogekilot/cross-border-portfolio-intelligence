"""The result type of the risk engine (`risk/1.1` Rulings 3.4, 7.1, 9.4; tech plan 17.7, 17.16).

`RiskMetric` wraps the product's `MetricResult` (PD-0025: a `Decimal` or no value, never subclassed) with what an audit needs: the exact rational (a rational output), or the exact radicand `Q` and the sign (a
square-root output), EVERY cause that shaped the state, the detail names, the declared window (Ruling 2.3), the observation count and the thresholds in the same unit (Ruling 7.1), the stale-period count (Ruling 2.5),
the drawdown's dates and peak rule (Ruling 1.1), the benchmark lineage (Ruling 5.6), and the registry entry it was computed under. It never carries a number for an INSUFFICIENT_DATA result: `exact`, `exact_square` and
`sign` are None exactly when the `MetricResult` has no value, so an exact value cannot leak a suppressed number.

It is separate from `performance.results.ComputedMetric`, which belongs to the CP3 id list and carries a freshness vector, a stale weight and a breakdown that do not apply here; the CP3 types are untouched.
This module names no reason code (`risk.states` is the only one that does).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any, Dict, Optional, Tuple, Union

from marketdata.canonical import canonical_json, sha256_hex
from performance.grid import SeriesWindow
from performance.results import Cause
from product_contract.metric_state import MetricResult
from product_contract.vocabulary import SufficiencyState

PORTFOLIO_STATE_ACTUAL = "ACTUAL"  # P8: only the portfolio as actually held goes through this engine
METRIC_SCHEMA = "finweb.risk_metric/1"


@dataclass(frozen=True)
class DrawdownFacts:
    """Ruling 1.1: the three dates and the peak rule, carried with the value."""

    peak_date: Optional[datetime.date]
    trough_date: Optional[datetime.date]
    recovery_date: Optional[datetime.date]
    peak_rule: str

    def to_obj(self) -> Dict[str, Any]:
        return {"peak_date": self.peak_date, "trough_date": self.trough_date, "recovery_date": self.recovery_date, "peak_rule": self.peak_rule}


@dataclass(frozen=True)
class LagPoint:
    """A grid date where the two legs are measured a different number of sessions behind it (Ruling 8.2 item 1)."""

    date: datetime.date
    portfolio_lag: int
    benchmark_lag: int


@dataclass(frozen=True)
class Seam:
    """Ruling 8.2 item 2 and 8.3 (1.1): the two legs' inputs are at different scheduled instants. `portfolio_calendars` and `benchmark_calendars` are the two instant sets as SORTED calendar ids (the ECB fixing appears
    as the ECB calendar's id); `max_offset_minutes_at_last_grid_date` is the largest `|p - b|` over a portfolio instant and a benchmark instant at `g_n`, in whole minutes."""

    portfolio_calendars: Tuple[str, ...]
    benchmark_calendars: Tuple[str, ...]
    max_offset_minutes_at_last_grid_date: Optional[int]

    def to_obj(self) -> Dict[str, Any]:
        return {"portfolio_calendars": list(self.portfolio_calendars), "benchmark_calendars": list(self.benchmark_calendars), "max_offset_minutes_at_last_grid_date": self.max_offset_minutes_at_last_grid_date}


@dataclass(frozen=True)
class Comparability:
    """The disclosure object of Ruling 8.3: a DISCLOSURE, never a state (PD-0014 section 1.3). `klass` is `LIMITED` when `seam` is not None or `lagged_count > 0`, else `FULL`. A two-leg result that is INSUFFICIENT_DATA
    carries none."""

    klass: str
    seam: Optional[Seam]
    lagged_count: int
    lagged_of: int
    points: Tuple[LagPoint, ...]

    def __post_init__(self) -> None:
        if self.klass not in ("FULL", "LIMITED"):
            raise ValueError("class is FULL or LIMITED")
        if (self.klass == "LIMITED") != (self.seam is not None or self.lagged_count > 0):
            raise ValueError("class is LIMITED exactly when there is a seam or a lag")
        if self.lagged_count != len(self.points):
            raise ValueError("the lag count is the number of points listed")

    def to_obj(self) -> Dict[str, Any]:
        return {"class": self.klass, "seam": None if self.seam is None else self.seam.to_obj(),
                "lagged": {"count": self.lagged_count, "of": self.lagged_of, "points": [{"date": p.date, "portfolio_lag": p.portfolio_lag, "benchmark_lag": p.benchmark_lag} for p in self.points]}}


@dataclass(frozen=True)
class BenchmarkRef:
    """Ruling 5.6: what every benchmark-dependent result names. `benchmark_id` and `selection_id` are None when no selection is in force (and `selection_id` is then the id of the record that CLEARED it, if any);
    `return_basis`, `currency`, `currency_treatment`, `name`, `provider` and `source_id` are known once the series is in the catalog."""

    benchmark_id: Optional[str]
    selection_id: Optional[str]
    selection_seq: Optional[int]
    selection_version: int
    catalog_id: Optional[str]
    return_basis: Optional[str] = None
    currency: Optional[str] = None
    currency_treatment: Optional[str] = None
    name: Optional[str] = None
    provider: Optional[str] = None
    source_id: Optional[str] = None
    synthetic: Optional[bool] = None

    def to_obj(self) -> Dict[str, Any]:
        return {"benchmark_id": self.benchmark_id, "selection_id": self.selection_id, "selection_seq": self.selection_seq, "selection_version": self.selection_version, "catalog_id": self.catalog_id,
                "return_basis": self.return_basis, "currency": self.currency, "currency_treatment": self.currency_treatment, "name": self.name, "provider": self.provider, "source_id": self.source_id,
                "synthetic": self.synthetic}


@dataclass(frozen=True)
class RiskMetric:
    metric_id: str
    method_key: str                                  # `risk/1.1#risk_volatility`: the registry entry it was computed under (Ruling 9.2)
    result: MetricResult
    exact: Optional[Fraction]                        # a rational output (maximum drawdown, benchmark return): the value before presentation
    exact_square: Optional[Fraction]                 # a square-root output: the radicand `Q`, with `value = sign * sqrt(Q)` rounded (Ruling 3.4)
    sign: Optional[int]
    frequency: str
    requested_rule: Optional[str]
    requested_months: Optional[int]
    requested_base: Optional[datetime.date]          # `B`, asserted for refusals too
    window: Optional[SeriesWindow]                   # the effective window (Ruling 2.3); None when the request is refused
    observation_count: Optional[int]
    thresholds: Optional[Tuple[int, int]]            # (insufficient_below, available_from) in observations; None for a window fact
    causes: Tuple[Cause, ...]
    details: Tuple[str, ...]
    intermediates: Tuple[Tuple[str, Union[Fraction, datetime.date]], ...] = ()  # Ruling 9.4: the exact sums and means the value came from (mean_return, mean_excess, mean_risk_free, variance, shortfall_sum, level_g0, level_gn), sorted by name
    stale_period_count: Optional[int] = None         # Ruling 2.5: present when some period returns are LIMITED
    drawdown: Optional[DrawdownFacts] = None
    benchmark: Optional[BenchmarkRef] = None
    lineage: Tuple[Tuple[str, str], ...] = ()
    synthetic: bool = True
    manifest_id: Optional[str] = None
    portfolio_state: str = PORTFOLIO_STATE_ACTUAL
    comparability: Optional[Comparability] = None    # Ruling 8.3: a two-leg metric with a value (never for INSUFFICIENT_DATA)
    decomposition: Optional[Tuple[Tuple[str, Any], ...]] = None  # Ruling 6.9 (1.1): the view `(portfolio_twr, benchmark_return, active_return)` apportioned so the shown difference is the difference of the shown legs

    def __post_init__(self) -> None:
        suppressed = self.result.value is None
        if suppressed and (self.comparability is not None or self.decomposition is not None):
            raise ValueError("a suppressed metric carries no comparability object and no decomposition (there is no value to qualify)")
        for name in ("exact", "exact_square", "sign"):
            if suppressed and getattr(self, name) is not None:
                raise ValueError(f"a suppressed metric carries no {name} (no number for INSUFFICIENT_DATA)")
        if self.exact is not None and not isinstance(self.exact, Fraction):
            raise TypeError("exact must be a Fraction")
        if self.exact_square is not None and (not isinstance(self.exact_square, Fraction) or self.exact_square < 0):
            raise TypeError("exact_square must be a non-negative Fraction")
        if self.exact is not None and self.exact_square is not None:
            raise ValueError("a metric is a rational output or a square-root output, not both")
        if self.portfolio_state != PORTFOLIO_STATE_ACTUAL:
            raise ValueError("this engine computes ACTUAL portfolios only (P8)")
        if list(self.causes) != sorted(set(self.causes)) or list(self.details) != sorted(set(self.details)) or list(self.lineage) != sorted(self.lineage):
            raise ValueError("causes, details and lineage must be sorted and unique")
        if self.result.sufficiency_state is SufficiencyState.INSUFFICIENT_DATA and not self.causes:
            raise ValueError("an INSUFFICIENT_DATA metric must name its causes")
        if suppressed and (self.drawdown is not None):
            raise ValueError("a suppressed metric carries no drawdown dates")
        if list(self.intermediates) != sorted(self.intermediates) or (suppressed and self.intermediates):
            raise ValueError("intermediates are sorted, and a suppressed metric carries none (no number for INSUFFICIENT_DATA)")
        if any(not isinstance(v, (Fraction, datetime.date)) or isinstance(v, datetime.datetime) for _n, v in self.intermediates):
            raise TypeError("an intermediate is an exact Fraction (or the date of a fixing)")

    @property
    def value(self):
        return self.result.value

    @property
    def state(self) -> SufficiencyState:
        return self.result.sufficiency_state

    def with_manifest(self, manifest_id: str) -> "RiskMetric":
        return replace(self, manifest_id=manifest_id)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema": METRIC_SCHEMA, "metric_id": self.metric_id, "method_key": self.method_key, "value": self.result.value, "state": self.result.sufficiency_state.value,
            "reason": None if self.result.reason_code is None else self.result.reason_code.value, "exact": self.exact, "exact_square": self.exact_square, "sign": self.sign,
            "frequency": self.frequency, "requested_rule": self.requested_rule, "requested_months": self.requested_months, "requested_base": self.requested_base,
            "window": None if self.window is None else self.window.to_obj(), "observation_count": self.observation_count,
            "thresholds": None if self.thresholds is None else list(self.thresholds), "causes": [c.to_obj() for c in self.causes], "details": list(self.details),
            "intermediates": [[n, v] for n, v in self.intermediates], "stale_period_count": self.stale_period_count, "drawdown": None if self.drawdown is None else self.drawdown.to_obj(),
            "benchmark": None if self.benchmark is None else self.benchmark.to_obj(), "lineage": [list(p) for p in self.lineage], "synthetic": self.synthetic,
            "manifest_id": self.manifest_id, "portfolio_state": self.portfolio_state,
            "comparability": None if self.comparability is None else self.comparability.to_obj(),
            "decomposition": None if self.decomposition is None else [[n, v] for n, v in self.decomposition],
        }


def risk_digest(metrics: Tuple[RiskMetric, ...]) -> str:
    """The result digest: sha256 of the canonical JSON of every metric, in the order given (the engine sorts by metric id)."""
    return sha256_hex(canonical_json([m.to_canonical_dict() for m in metrics]).encode("utf-8"))
