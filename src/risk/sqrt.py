"""The exact square root of a rational and its presentation (`risk/1.1` Ruling 3.4 items 2 and 4; tech plan 17.7.2).

Every square-root metric is `sign * sqrt(Q)` with `Q` an exact non-negative rational (volatility, downside deviation, tracking error, Sharpe, Sortino, information ratio). The presented value is `sqrt(Q)` ROUNDED
EXACTLY to the quantum `10^-12`, with integers only (no float, no `Decimal` power, no `math`):

    N = Q * 10^(2 * digits)             a rational
    k = isqrt(floor(N))                 = floor(sqrt(N)), because floor(sqrt(N)) = floor(sqrt(floor(N)))
    the magnitude is  k + 1 quanta  if  4 N >= (2 k + 1)^2   (that is exactly  sqrt(N) >= k + 1/2),  else  k quanta

The test is decided in integers, so it is exact: no tie rule is needed for an irrational root, and a root that IS a half quantum (`Q` a perfect rational square whose root ends in a 5 at the 13th decimal) rounds up,
half away from zero, as `ROUND_HALF_UP` does. The sign is applied after, to the rounded magnitude. `performance`'s `Decimal`-at-precision-50 route stays conformant; this is the product path.

`isqrt` is Newton's method on integers, written here because `math` is not imported by these packages; a test compares it with `math.isqrt`.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

DIGITS = 12  # the quantum 10^-12 of every risk statistic (Ruling 3.4 item 3)


def isqrt(n: int) -> int:
    """The largest integer `r` with `r * r <= n`, for `n >= 0` (Newton's method; exact)."""
    if n < 0:
        raise ValueError("isqrt of a negative number")
    if n < 2:
        return n
    x = 1 << ((n.bit_length() + 1) // 2)  # >= sqrt(n), so the iteration decreases to floor(sqrt(n))
    while True:
        y = (x + n // x) >> 1
        if y >= x:
            return x
        x = y


@dataclass(frozen=True)
class RootRounded:
    """`quanta` is the rounded magnitude in units of `10^-digits`; `value` the signed rounded value as an exact rational; `exact_square` the radicand `Q`; `exact` is True when `sqrt(Q)` is itself rational and the
    rounded value equals it (so nothing was rounded away)."""

    sign: int
    quanta: int
    digits: int
    value: Fraction
    exact_square: Fraction
    exact: bool


def sqrt_rounded(q: Fraction, sign: int = 1, digits: int = DIGITS) -> RootRounded:
    """`sign * sqrt(q)` rounded half away from zero to `10^-digits`, exactly. `sign` is 1, -1 or 0 (0 for a zero radicand: the Quant's fixtures assert `sign: 0` when `Q = 0`)."""
    if q < 0:
        raise ValueError("the radicand must be non-negative")
    if sign not in (-1, 0, 1):
        raise ValueError("sign must be -1, 0 or 1")
    if q == 0:
        return RootRounded(0, 0, digits, Fraction(0), q, True)
    if sign == 0:
        raise ValueError("a non-zero radicand needs a sign of 1 or -1")
    n = q * 10 ** (2 * digits)
    k = isqrt(n.numerator // n.denominator)
    magnitude = k + 1 if 4 * n >= (2 * k + 1) ** 2 else k
    value = Fraction(sign * magnitude, 10**digits)
    exact = n == k * k and magnitude == k  # sqrt(N) = k exactly: the rounded value is the root itself
    return RootRounded(sign, magnitude, digits, value, q, exact)
