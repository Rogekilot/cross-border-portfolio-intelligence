"""The exact statistics of the risk engine (`risk/1.1` Rulings 1.1, 3.2 to 3.4, 6.2 to 6.6; tech plan 17.7.2, 17.16).

Everything is an exact rational (`Fraction`). The only irrational step of a metric is ONE final square root, rounded exactly by `risk.sqrt`; this module forms the radicand `Q` and nothing else. No float, no logarithm,
no exponential, no `math`. A statistic is computed from the exact periodic values, never from a presented value (Ruling 3.4 item 6).

THE MAXIMUM DRAWDOWN (Ruling 1.1) is ONE function, `max_drawdown`, and the only one: a chart, an insight or the AI layer calls it, never re-derives it (Ruling 1.3):

    W_0 = 1,   W_k = W_{k-1} (1 + r_k)          the window's own wealth path, from the base `g_0`
    M_k = max_{0 <= j <= k} W_j                 the running peak over the WINDOW, INCLUDING the base (it never looks before `g_0`)
    DD_k = W_k / M_k - 1,   MDD = min_k DD_k
    trough = the EARLIEST k with DD_k = MDD;  peak = the LATEST j <= trough with W_j = M_trough;  recovery = the earliest k > trough with W_k >= M_trough, or none.

`MDD = 0` (no negative drawdown) has no dates. Indices are positions in the grid points `g_0 ... g_n`.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Optional, Sequence, Tuple

ZERO = Fraction(0)
ONE = Fraction(1)
PEAK_RULE = "WITHIN_WINDOW_FROM_BASE"


def total(values: Sequence[Fraction]) -> Fraction:
    """The exact sum (the order of an exact sum is immaterial)."""
    out = ZERO
    for v in values:
        out += v
    return out


def mean(values: Sequence[Fraction]) -> Fraction:
    if not values:
        raise ValueError("the mean of no values")
    return total(values) / len(values)


def sum_squared_deviations(values: Sequence[Fraction]) -> Fraction:
    """`S_zz = sum (z_k - mean)^2`, exactly, in the raw-sum form `sum z^2 - (sum z)^2 / n` (no centring error: every value is exact)."""
    n = len(values)
    if n == 0:
        raise ValueError("no values")
    s = total(values)
    return total([v * v for v in values]) - s * s / n


def sum_cross_deviations(xs: Sequence[Fraction], ys: Sequence[Fraction]) -> Fraction:
    """`S_zw = sum (z_k - mean z)(w_k - mean w)`, exactly."""
    n = len(xs)
    if n == 0 or n != len(ys):
        raise ValueError("two series of the same positive length are needed")
    return total([x * y for x, y in zip(xs, ys)]) - total(xs) * total(ys) / n


def sample_variance(values: Sequence[Fraction]) -> Fraction:
    """`s^2 = S_zz / (n - 1)`: around a sample mean, `n - 1` (Ruling 3.3)."""
    n = len(values)
    if n < 2:
        raise ValueError("a sample variance needs at least two values")
    return sum_squared_deviations(values) / (n - 1)


def shortfall_square_sum(excess: Sequence[Fraction]) -> Fraction:
    """`sum min(0, d_k)^2`: periods at or above the target contribute 0 (Ruling 6.3)."""
    return total([d * d for d in excess if d < 0])


def sign_of(value: Fraction) -> int:
    return (value > 0) - (value < 0)


# --- single-series radicands (Ruling 3.4 item 2): each metric is `sign * sqrt(Q)` with `Q` exact ------------------------------------------------

def volatility_radicand(returns: Sequence[Fraction], periods_per_year: int) -> Fraction:
    """`A s^2(r)` (Ruling 6.2)."""
    return periods_per_year * sample_variance(returns)


def downside_radicand(excess: Sequence[Fraction], periods_per_year: int) -> Fraction:
    """`A (1/n) sum min(0, d_k)^2` (Ruling 6.3: the full `n`, a fixed target)."""
    return periods_per_year * shortfall_square_sum(excess) / len(excess)


def sharpe_radicand(mean_excess: Fraction, variance: Fraction, periods_per_year: int) -> Fraction:
    """`A dbar^2 / s^2(r)` (Ruling 6.5); the caller guarantees `variance > 0`."""
    return periods_per_year * mean_excess * mean_excess / variance


def sortino_radicand(mean_excess: Fraction, shortfall_squares: Fraction, n: int, periods_per_year: int) -> Fraction:
    """`A dbar^2 n / sum min(0, d_k)^2` (Ruling 6.6); the caller guarantees the shortfall sum is positive."""
    return periods_per_year * mean_excess * mean_excess * n / shortfall_squares


# --- maximum drawdown --------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Drawdown:
    """`value` is `MDD` in [-1, 0]; the three indices are positions in `g_0 ... g_n` (None when `MDD = 0`, and `recovery` None while the peak is not regained); `wealth` is `W_0 ... W_n`."""

    value: Fraction
    peak: Optional[int]
    trough: Optional[int]
    recovery: Optional[int]
    wealth: Tuple[Fraction, ...]


def wealth_path(returns: Sequence[Fraction]) -> Tuple[Fraction, ...]:
    """`W_0 = 1`, `W_k = W_{k-1} (1 + r_k)`: `1 + TWR(g_0, g_k]` exactly (RS-1)."""
    path = [ONE]
    for r in returns:
        path.append(path[-1] * (ONE + r))
    return tuple(path)


def max_drawdown(returns: Sequence[Fraction]) -> Drawdown:
    """Ruling 1.1 over the window's own periodic returns `r_1 ... r_n` (so the base is `W_0 = 1`, inside the peak search)."""
    wealth = wealth_path(returns)
    running_peak = wealth[0]
    worst = ZERO
    trough: Optional[int] = None
    peaks = []
    for k, w in enumerate(wealth):
        if w > running_peak:
            running_peak = w
        peaks.append(running_peak)
        dd = w / running_peak - ONE
        if dd < worst:  # strict: the EARLIEST trough keeps its place on a tie
            worst, trough = dd, k
    if trough is None:
        return Drawdown(ZERO, None, None, None, wealth)
    high = peaks[trough]
    peak = max(j for j in range(trough + 1) if wealth[j] == high)  # the LATEST valuation at the high-water mark before the decline
    recovery = next((k for k in range(trough + 1, len(wealth)) if wealth[k] >= high), None)
    return Drawdown(worst, peak, trough, recovery, wealth)
