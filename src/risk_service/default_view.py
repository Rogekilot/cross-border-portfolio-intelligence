"""The default view (`risk/1.4` Ruling 7.7 (1.2), PD-0040 / OD-R1): a SERVICE-LEVEL composition, never a metric (tech plan 17.21).

PD-0040: when the default 3-year request is refused for the portfolio's HISTORY, the default view shows `MAX_AVAILABLE` with its true window, observation count and state, and the refusal stays in the evidence.
This module only COMPOSES two ordinary results; it creates no metric, changes no result and relabels nothing (Ruling 7.2 unchanged):

1. `X` = the metric over the default request (`TRAILING_MONTHS 36`, the registry's `lookback.default`).
2. FALL BACK if and only if `X` is `INSUFFICIENT_DATA` and its details include one of `WINDOW_BEFORE_INCEPTION`, `WINDOW_BEFORE_SNAPSHOT`, `PERIOD_INSUFFICIENT`, `ZERO_CAPITAL_PERIOD` (the portfolio's history is too
   young or has a gap: exactly what `MAX_AVAILABLE` gets past), or (Ruling 7.7 (1.6)) `X` is an active return whose portfolio leg `TWR(g_0, g_n]` is `INSUFFICIENT_DATA` (read from its lineage).
3. If it falls back, `Y` = the same metric over `MAX_AVAILABLE` (same frequency, scope, `E`/`t` and selection). The view shows `Y` with ITS OWN window, count, state and value, WHATEVER that state is (it may itself be
   `INSUFFICIENT_DATA`: R9-Z1, 40 weekly observations; no number is promised, P5). `X` is carried as `refused`.
4. NO fall-back for any other refusal (a missing, price-return, stale or conflicting benchmark; a missing risk-free series; a degenerate case): the view shows `X`. `MAX_AVAILABLE` would be refused for the same cause and
   showing it would only replace a clear reason with a shorter window. A benchmark-side gap does not move `MAX_AVAILABLE`'s base (Ruling 2.3 moves it past the PORTFOLIO's insufficient periods only).

EVIDENCE (the engineer's recommendation in the ruling): `X` and `Y` each have their own manifest and reproduce on their own; the view's record carries both result digests, both manifest ids and the `fallback` flag,
so an auditor sees the refusal and the substitute side by side (P9).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Union

from performance.periods import WindowRule, WindowSpec
from performance.series import MaxAvailable
from risk import states as S
from risk.manifest import RiskResult
from risk.results import RiskMetric
from product_contract.vocabulary import SufficiencyState

#: the default request: PRD section 14's three-year lookback (`risk` registry `common.lookback.default`)
DEFAULT_REQUEST = WindowSpec(WindowRule.TRAILING_MONTHS, 36)
#: the refusals FOR THE PORTFOLIO'S HISTORY (Ruling 7.7 item 2): the only ones that fall back
HISTORY_REFUSALS = frozenset({S.WINDOW_BEFORE_INCEPTION, S.WINDOW_BEFORE_SNAPSHOT, S.PERIOD_INSUFFICIENT, S.ZERO_CAPITAL_PERIOD})

PORTFOLIO_LEG_STATE = "portfolio_leg_state"  # the lineage key `risk.relative` records for the active return (Ruling 6.9 (1.1): the leg is TWR(g_0, g_n])

Request = Union[WindowSpec, MaxAvailable]


def falls_back(x: RiskMetric) -> bool:
    """Ruling 7.7 item 2 and (1.6): `x` is `INSUFFICIENT_DATA` and either carries one of the history details, or is a metric with a portfolio leg (the active return) whose leg `TWR(g_0, g_n]` is itself
    `INSUFFICIENT_DATA`, whatever performance detail it carries (`SPLIT_NOT_APPLIED`, a valuation stale by 5 or more, `NON_POSITIVE_BASE`): a gap in the portfolio's own history. The leg's state is read from the
    metric's lineage (`portfolio_leg_state`). A benchmark-side or risk-free cause is never a trigger: a leg that is not `INSUFFICIENT_DATA` does not trigger it, whatever else refused the metric."""
    if x.state is not SufficiencyState.INSUFFICIENT_DATA:
        return False
    return bool(HISTORY_REFUSALS & set(x.details)) or dict(x.lineage).get(PORTFOLIO_LEG_STATE) == SufficiencyState.INSUFFICIENT_DATA.value


@dataclass(frozen=True)
class DefaultView:
    """What the view shows and its evidence. `shown` is `Y` when `fallback`, else `X`; `refused` is `X` when `fallback`, else None. `x` and `y` are the whole results (each with its own manifest)."""

    metric_id: str
    default_request: WindowSpec
    fallback: bool
    shown: RiskMetric
    refused: Optional[RiskMetric]
    x: RiskResult
    y: Optional[RiskResult]

    def evidence(self) -> dict:
        """The record of the composition (P9): both results' digests and manifest ids and the flag."""
        return {"metric_id": self.metric_id, "default_request": {"rule": self.default_request.rule.value, "months": self.default_request.months}, "fallback": self.fallback,
                "x_result_digest": self.x.result_digest, "x_manifest_id": self.x.manifest.manifest_id,
                "y_result_digest": None if self.y is None else self.y.result_digest, "y_manifest_id": None if self.y is None else self.y.manifest.manifest_id}


def default_view(compute: Callable[[Request], RiskResult], metric_id: str, default_request: WindowSpec = DEFAULT_REQUEST) -> DefaultView:
    """The composition. `compute(request)` returns the ordinary result of `metric_id` over `request` (the caller fixes the frequency, scope, `E` or `t` and selection, and so they are the same for `X` and `Y`)."""
    x = compute(default_request)
    xm = x.metric(metric_id)
    if not falls_back(xm):
        return DefaultView(metric_id, default_request, False, xm, None, x, None)
    y = compute(MaxAvailable())
    return DefaultView(metric_id, default_request, True, y.metric(metric_id), xm, x, y)
