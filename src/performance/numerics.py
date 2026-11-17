"""Exact numerics for the performance engine (`performance/1.0` Rulings 2.1 to 2.5; tech plan 16.6).

TWO TIERS (Ruling 2.1).
- Tier E (engine): every money amount, quantity, rate and return is an exact `Fraction`. There is NO intermediate rounding,
  never a binary float, and the global `decimal` context is never read. The one conversion to `Decimal` of a rational uses a
  private, exact, wide context that traps inexactness (the discipline of `domain.replay`).
- Transcendental steps ONLY (annualization roots; later the IRR solver and Cariño logarithms): `Decimal` at precision 50,
  ROUND_HALF_EVEN, `ln` and `exp` (correctly rounded under the General Decimal Arithmetic specification), with a power computed
  as `exp(y ln x)`. Inputs enter as exact rationals converted at that precision. This is the ONLY use of `ln`/`exp` and it has its
  own private context.
- Tier P (presented): quantized once, at the edge, by a `RoundingRule` (`performance.rounding`): half away from zero.
  Nothing computes from a tier-P value.

This module holds no rounding LITERAL for money or returns: the quanta (Ruling 2.2) and the minor-unit table (Ruling 2.3) live
in `performance.rounding`. It holds the mechanisms: `round_half_up`, `floor_to` and the largest-remainder `apportion` (Ruling 2.4).
"""

from __future__ import annotations

import decimal
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
from fractions import Fraction
from typing import Optional, Protocol, Sequence, Tuple

from domain.currency import CurrencyCode

#: Size guard (CP3-5): a numerator or denominator wider than this many bits is refused as a state, never computed on. It exists ONLY to stop a runaway input
#: (a corrupt or hostile ledger) from hanging the engine; it must not be reachable by ANY valid input within the conventions' windows (OI-P5), so the bound is
#: derived, not chosen:
#:   - a window is at most 100 years (36,600 days), and a daily-flow TWR is a product of at most one factor per day;
#:   - a factor is a ratio of two valuations, each a sum of products of a quantity, a price (each below 1E30 with at most 24 decimals: PD-0026) and at most two
#:     ECB quotes (4 decimals); its numerator and denominator each fit in 2,000 bits even for 20 currencies (the observed width of a realistic daily factor
#:     is about 20 bits per day, 40,000 bits over five years);
#:   - 36,600 factors x 2,000 bits = 73.2 million bits < 2**27 = 134 million bits.
#: So no valid input is refused; only a runaway one is.
MAX_BITS = 1 << 27

_CTX = decimal.Context(
    prec=200, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999, Emax=999999, capitals=1, clamp=0, flags=[],
    traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow, decimal.Inexact],
)

#: Ruling 2.1: the transcendental context. Inexact is NOT trapped (ln and exp are inexact by nature).
TRANSCENDENTAL_PRECISION = 50
_CTX50 = decimal.Context(
    prec=TRANSCENDENTAL_PRECISION, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999, Emax=999999, capitals=1, clamp=0,
    flags=[], traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow],
)


@unique
class RoundingPoint(Enum):
    """What is being presented (Ruling 2.2). The quantum and mode of each belong to the rounding rule."""

    PRESENT_MONEY = "PRESENT_MONEY"    # a DERIVED money amount in a currency (a price, a rate, a division, an allocation)
    PRESENT_RETURN = "PRESENT_RETURN"  # a return, a return component, a weight, a share
    PRESENT_RATE = "PRESENT_RATE"      # a displayed rate
    PRESENT_FACT = "PRESENT_FACT"      # a recorded ledger fact or a sum of facts: presented exactly, never rounded


@dataclass(frozen=True)
class Rounded:
    """What a rule states for a value: the rounded rational, or no value and the DETAIL why (for example
    `CURRENCY_NO_MINOR_UNIT`: a currency missing from the table fails closed)."""

    stated: Optional[Fraction]
    detail: Optional[str] = None


class RoundingRule(Protocol):
    rule_id: str

    def apply(self, point: RoundingPoint, value: Fraction, currency: Optional[CurrencyCode]) -> Rounded: ...


def within_bounds(value: Fraction) -> bool:
    return value.numerator.bit_length() <= MAX_BITS and value.denominator.bit_length() <= MAX_BITS


def is_terminating(value: Fraction) -> bool:
    """True when `value` has a finite decimal expansion (its denominator has no prime factor other than 2 and 5)."""
    rest = value.denominator
    for p in (2, 5):
        while rest % p == 0:
            rest //= p
    return rest == 1


def to_decimal_exact(value: Fraction) -> Optional[Decimal]:
    """The exact `Decimal` of a terminating `value`, else None (never rounds, never raises). No int-to-str conversion
    anywhere (CPython caps that at 4,300 digits): `Decimal(int)` and `scaleb` are exact."""
    if not is_terminating(value) or not within_bounds(value):
        return None
    rest, twos, fives = value.denominator, 0, 0
    while rest % 2 == 0:
        rest //= 2
        twos += 1
    while rest % 5 == 0:
        rest //= 5
        fives += 1
    k = max(twos, fives)
    scaled = value.numerator * (10 ** k // value.denominator)
    try:
        return Decimal(scaled).scaleb(-k, _CTX) if scaled != 0 else Decimal(0)
    except (ValueError, ArithmeticError):
        return None


def shortest_decimals(value: Fraction) -> int:
    """`d(v)`: the least `n >= 0` with `value * 10**n` an integer, for a TERMINATING `value` (performance/1.12 Ruling 2.2 item 2). Integer arithmetic only."""
    rest, twos, fives = value.denominator, 0, 0
    while rest % 2 == 0:
        rest //= 2
        twos += 1
    while rest % 5 == 0:
        rest //= 5
        fives += 1
    if rest != 1:
        raise ValueError("a non-terminating value has no finite number of decimals")
    return max(twos, fives)


def to_decimal_money(value: Fraction, decimals: int) -> Optional[Decimal]:
    """`to_decimal_exact` of a money amount already quantized to `decimals` places (Ruling 2.2), carried with EXACTLY that many places (9229.70, not 9229.7; 0.00; JPY 5000):
    the presented money value is a `Decimal` whose exponent is the currency's minor unit. The number is unchanged; only the trailing zeros of the quantum are kept. None as `to_decimal_exact`."""
    dec = to_decimal_exact(value)
    if dec is None:
        return None
    scaled = value * (10 ** decimals)
    if scaled.denominator != 1:
        return dec  # off the quantum: the exact value, never rounded here
    try:
        return Decimal(scaled.numerator).scaleb(-decimals, _CTX)  # integer scaled by the minor unit: the exponent is exactly -decimals (zero is 0.00)
    except (ValueError, ArithmeticError):
        return dec  # beyond the 200-digit context by the padding zeros alone: the exact value, as before


# --- quantization mechanisms (Ruling 2.2, 2.4) ---------------------------------------------------------------------------

def round_half_up(value: Fraction, decimals: int) -> Fraction:
    """`value` rounded to `decimals` places, HALF AWAY FROM ZERO (Ruling 2.2). Integer arithmetic only. Ties occur only for
    terminating values; a non-terminating rational cannot sit exactly on a half."""
    if decimals < 0:
        raise ValueError("decimals must be >= 0")
    scale = 10 ** decimals
    n, d = value.numerator * scale, value.denominator
    q = (2 * abs(n) + d) // (2 * d)  # floor(|x| + 1/2)
    return Fraction(q if n >= 0 else -q, scale)


def floor_to(value: Fraction, decimals: int) -> Fraction:
    """`value` rounded DOWN (toward minus infinity) to `decimals` places."""
    scale = 10 ** decimals
    return Fraction((value.numerator * scale) // value.denominator, scale)


def apportion(total: Fraction, parts: Sequence[Fraction], decimals: int) -> Tuple[Fraction, ...]:
    """Ruling 2.4 item 3, the largest-remainder method. `total_hat` is the total quantized by Ruling 2.2; each part is first
    rounded DOWN to the quantum; the shortfall (an integer number of quanta, between 0 and `len(parts)`) is given one quantum at
    a time to the parts with the largest remainders `p - floor(p)`; ties go in the FIXED LINE ORDER of `parts`. The displayed
    parts then sum to the displayed total EXACTLY and each is within one quantum of its exact value. Deterministic.

    The parts must sum to `total` exactly (tier E); anything else is a defect and raises."""
    if sum(parts, Fraction(0)) != total:
        raise ValueError("the parts of a decomposition must sum to its total exactly (tier E)")
    quantum = Fraction(1, 10 ** decimals)
    total_hat = round_half_up(total, decimals)
    floors = [floor_to(p, decimals) for p in parts]
    shortfall = (total_hat - sum(floors, Fraction(0))) / quantum
    if shortfall.denominator != 1 or not 0 <= shortfall <= len(parts):
        raise ValueError("apportionment shortfall outside 0..k: the parts do not reconcile to the quantized total")
    order = sorted(range(len(parts)), key=lambda i: (-(parts[i] - floors[i]), i))
    out = list(floors)
    for i in order[: int(shortfall)]:
        out[i] += quantum
    return tuple(out)


def apportion_displayed(displayed_total: Fraction, parts: Sequence[Fraction], decimals: int) -> Tuple[Fraction, ...]:
    """Ruling 2.4 item 3 with a total that is ALREADY a display value (performance/1.9 Ruling 9.6: a breakdown's total is the line's apportioned display value, which is not the
    rounding of the line's exact value). Each part is rounded DOWN to the quantum; the shortfall to `displayed_total` goes one quantum at a time to the largest remainders, ties in the
    FIXED order of `parts`. The displayed parts then sum to `displayed_total` exactly and each is within one quantum of its exact value. The shortfall is an integer between 0 and
    `len(parts)` whenever `displayed_total` is the line's own apportioned value (the floors sum to at most the line, and the display is above the line's floor); anything else raises."""
    quantum = Fraction(1, 10 ** decimals)
    floors = [floor_to(p, decimals) for p in parts]
    shortfall = (displayed_total - sum(floors, Fraction(0))) / quantum
    if shortfall.denominator != 1 or not 0 <= shortfall <= len(parts):
        raise ValueError("apportionment shortfall outside 0..k: the parts do not reconcile to the displayed total")
    order = sorted(range(len(parts)), key=lambda i: (-(parts[i] - floors[i]), i))
    out = list(floors)
    for i in order[: int(shortfall)]:
        out[i] += quantum
    return tuple(out)


# --- presentation: the single path from an exact rational to the Decimal of a MetricResult (PD-0025) -------------------

@unique
class PresentStatus(Enum):
    OK = "OK"
    NO_RULE = "NO_RULE"  # the convention gives no presentation for this value (the detail says why)
    NOT_REPRESENTABLE = "NOT_REPRESENTABLE"  # too wide to write exactly
    TOO_LARGE = "TOO_LARGE"  # the size guard


@dataclass(frozen=True)
class Presented:
    status: PresentStatus
    decimal: Optional[Decimal] = None
    stated: Optional[Fraction] = None  # the value as the convention states it (equal to the input if nothing rounded)
    detail: Optional[str] = None
    tie: bool = False  # an undecidable tie (performance/1.1 Ruling 2.1): lineage `PRESENTATION_TIE`


#: performance/1.1 Ruling 2.1: an irrational result is known to within this width; a rounding boundary inside the bracket is an UNDECIDABLE TIE.
IRRATIONAL_WIDTH = Fraction(1, 10 ** 40)
PRESENTATION_TIE = "PRESENTATION_TIE"


def present(value: Fraction, point: RoundingPoint, currency: Optional[CurrencyCode], rule: RoundingRule,
            width: Fraction = Fraction(0)) -> Presented:
    """The single path from a rational to the `Decimal` of a `MetricResult` (PD-0025). `width` > 0 says the value is only known to within `+-width`
    (an irrational result computed at precision 50, Ruling 2.1): if the bracket `[value - width, value + width]` contains a rounding boundary, the exact result
    cannot be rounded decisively, and the presented value is that boundary rounded half-up (AWAY from zero), with `tie` set. Otherwise the rounding is the
    same for every value in the bracket, hence for the exact mathematical result."""
    if not within_bounds(value):
        return Presented(PresentStatus.TOO_LARGE)
    rounded = rule.apply(point, value, currency)
    stated = rounded.stated
    if stated is None:
        return Presented(PresentStatus.NO_RULE, detail=rounded.detail)
    tie = False
    if width != 0:
        lo = rule.apply(point, value - width, currency).stated
        hi = rule.apply(point, value + width, currency).stated
        if lo is not None and hi is not None and lo != hi:
            tie = True
            stated = hi if value >= 0 else lo  # the boundary rounds half-up, away from zero
    if not within_bounds(stated):
        return Presented(PresentStatus.TOO_LARGE)
    minor = rule.money_decimals(currency) if currency is not None and hasattr(rule, "money_decimals") else None
    detail: Optional[str] = None
    if point is RoundingPoint.PRESENT_MONEY:
        money_decimals = minor  # Ruling 2.2 item 1: derived money carries exactly its minor units
    elif point is RoundingPoint.PRESENT_FACT and currency is not None and hasattr(rule, "money_decimals"):
        # performance/1.12 Ruling 2.2 items 2 to 4: a money FACT is padded to the minor unit and never rounded: `max(minor_unit, d(v))` decimals, `d(v)` the fewest that write the exact value
        # (so 2248 -> 2248.00 and 0.125 USD stays 0.125; the recorded scale is not used). A currency outside the table: the shortest exact form, with the detail, the state unchanged.
        if minor is None:
            money_decimals, detail = None, "CURRENCY_NO_MINOR_UNIT"
        else:
            money_decimals = max(minor, shortest_decimals(stated))
    else:
        money_decimals = None
    dec = to_decimal_exact(stated) if money_decimals is None else to_decimal_money(stated, money_decimals)
    if dec is None:
        return Presented(PresentStatus.NOT_REPRESENTABLE)
    return Presented(PresentStatus.OK, dec, stated, detail=detail, tie=tie)


# --- transcendental steps (Ruling 2.1): Decimal prec 50, ln and exp only --------------------------------------------------

def _dec50(value: Fraction) -> Decimal:
    """An exact rational at 50 digits (a correctly rounded division of two integers)."""
    return _CTX50.divide(Decimal(value.numerator), Decimal(value.denominator))


def growth_root(growth: Fraction, years: Fraction) -> Optional[Fraction]:
    """`growth ** (1 / years)` for `growth > 0`, `years > 0`, computed as `exp(ln(growth) / years)` at precision 50 (Ruling 7.2).
    Returned as the exact `Fraction` of that 50-digit `Decimal` (never a float). None when growth <= 0 or years <= 0."""
    if growth <= 0 or years <= 0:
        return None
    ln_g = _CTX50.ln(_dec50(growth))
    scaled = _CTX50.divide(_CTX50.multiply(ln_g, Decimal(years.denominator)), Decimal(years.numerator))
    return Fraction(_CTX50.exp(scaled))


# --- Carino linking (Ruling 9.4) ---------------------------------------------------------------------------------------------------

CARINO_RESIDUAL_BOUND = Decimal(10) ** -40  # Ruling 11.2: the internal sum of the linked components against the TWR
CARINO_SERIES_BELOW = Fraction(1, 10 ** 4)  # |r| below this: kappa by its series (see `_carino_kappa`); above it the direct form keeps 46 correct digits


def _carino_kappa(r: Fraction) -> Optional[Decimal]:
    """`ln(1 + r) / r` at precision 50 (1 when `r` is 0); None when `r <= -1` (no logarithm: `TOTAL_LOSS` or a negative factor)."""
    if r == 0:
        return Decimal(1)
    if r <= -1:
        return None
    if abs(r) < CARINO_SERIES_BELOW:
        # ln(1 + r) / r = sum_{k>=0} (-r)^k / (k + 1). For a tiny r the direct form rounds `1 + r` at precision 50 (to exactly 1 below 1E-50, so kappa would be 0 and the
        # division by it a DivisionByZero; and with 20 digits left at 1E-30), so the defined formula is evaluated by its series. Error: the truncation after 14 terms is below |r|^14 / 15 < 7E-58 (|r| < 1E-4); the rounding at precision 50 (14 additions, 14
        # divisions, 13 power multiplications; each term at most about 1) dominates and totals at most about 5E-50. The series value is within about 5E-50 of kappa, not 1E-55.
        x = _dec50(-r)
        total, power = Decimal(0), Decimal(1)
        for k in range(14):
            total = _CTX50.add(total, _CTX50.divide(power, Decimal(k + 1)))
            power = _CTX50.multiply(power, x)
        return total
    return _CTX50.divide(_CTX50.ln(_dec50(1 + r)), _dec50(r))


@dataclass(frozen=True)
class CarinoResult:
    components: Tuple[Decimal, ...]  # C_k, one per line, in the order of the input
    residual: Decimal                # (sum of C_k) - TWR, at precision 50


def carino_link(daily: Sequence[Tuple[Fraction, Sequence[Fraction]]], twr: Fraction) -> Optional[CarinoResult]:
    """Ruling 9.4: `C_k = (1 / kappa) sum_D kappa_D c_{k,D}`, with `kappa_D = ln(1 + r_D) / r_D` and `kappa = ln(1 + TWR) / TWR` (each 1 at 0). `daily` holds, for each day, `r_D`
    and the exact `c_{k,D} = m_{k,D} / beta_D` for every line `k` (a day with no capital and no gain has `r_D = 0` and every `c` 0). The sums are Decimal at precision 50, ROUND_HALF_EVEN;
    a line that is 0 every day stays exactly 0. None when a day's `r_D` or the TWR is at or below -1 (`TOTAL_LOSS`)."""
    width = len(daily[0][1]) if daily else 0
    kappa = _carino_kappa(twr)
    if kappa is None:
        return None
    sums = [Decimal(0)] * width
    for r, cs in daily:
        k_d = _carino_kappa(r)
        if k_d is None:
            return None
        for i, c in enumerate(cs):
            if c != 0:
                sums[i] = _CTX50.add(sums[i], _CTX50.multiply(k_d, _dec50(c)))
    components = tuple(_CTX50.divide(s, kappa) if s != 0 else Decimal(0) for s in sums)
    total = Decimal(0)
    for c in components:
        total = _CTX50.add(total, c)
    return CarinoResult(components, _CTX50.subtract(total, _dec50(twr)))


# --- the IRR solver (Ruling 6.2) and the uniqueness test (Ruling 6.3) ---------------------------------------------------------

IRR_OUT_OF_RANGE = "IRR_OUT_OF_RANGE"
IRR_BRACKET_EXPONENT = 64            # Ruling 6.2 step 3: give up beyond 2**64 or below 2**-64
IRR_MAX_ITERATIONS = 400             # Ruling 6.2 step 4
IRR_STOP = Decimal(10) ** -30        # Ruling 6.2 step 4: stop when g_hi - g_lo <= 1E-30 * g_hi

#: One investor cash flow: (tau as an exact fraction of the window, amount from the investor's side). Sorted by tau, amounts at the same tau already summed.
IrrFlow = Tuple[Fraction, Fraction]


@dataclass(frozen=True)
class IrrRoot:
    """`g` is `1 + rho` as an exact rational (the 50-digit Decimal of the bisection, converted exactly) or None; `rational` says `g` is exact (not a Decimal
    approximation); `detail` is `IRR_OUT_OF_RANGE` when no bracket was found."""

    g: Optional[Fraction]
    rational: bool = False
    detail: Optional[str] = None


def _f(flows: Sequence[Tuple[Decimal, Decimal]], ln_g: Decimal) -> Decimal:
    """Ruling 6.2 step 1: `f(g) = sum CF_i * exp(-tau_i * ln g)` in Decimal prec 50, ROUND_HALF_EVEN, summed in increasing tau (the input order)."""
    total = Decimal(0)
    for tau, cf in flows:
        total = _CTX50.add(total, _CTX50.multiply(cf, _CTX50.exp(_CTX50.minus(_CTX50.multiply(tau, ln_g)))))
    return total


def solve_irr(flows: Sequence[IrrFlow]) -> IrrRoot:
    """The deterministic root of `f(g) = sum CF_i g^(-tau_i)` for `g > 0` (Ruling 6.2): `G = f(1) = sum CF_i` exactly; `G = 0` gives `g = 1`; otherwise a BRACKET
    from `g = 1` (`G > 0`: `g_hi = 2, 4, 8, ...` until `f(g_hi) < 0`; `G < 0`: `g_lo = 1/2, 1/4, ...` until `f(g_lo) > 0`; the other end is 1; none within `2**+-64` is
    `IRR_OUT_OF_RANGE`), then BISECTION (`f(mid) > 0` moves `g_lo`, else `g_hi`) until `g_hi - g_lo <= 1E-30 * g_hi` or 400 iterations; `g* = (g_lo + g_hi)/2`.
    The preconditions of Ruling 6.4 are the caller's. When every flow is at tau 0 or tau 1 the root is `g = (sum of positive) / (sum of negative)` EXACTLY (the equation
    is `CF_0 + CF_1 / g = 0`), and that exact rational is returned (identity I-6: the MWR then IS the TWR)."""
    flows = tuple(flows)
    g_total = sum((cf for _tau, cf in flows), Fraction(0))
    if g_total == 0:
        return IrrRoot(Fraction(1), True)
    if all(tau in (0, 1) for tau, _cf in flows):
        early = sum((cf for tau, cf in flows if tau == 0), Fraction(0))
        late = sum((cf for tau, cf in flows if tau == 1), Fraction(0))
        if early < 0 < late:
            return IrrRoot(late / -early, True)
    dec = [(_dec50(tau), _dec50(cf)) for tau, cf in flows]

    def at(g: Decimal) -> Decimal:
        return _f(dec, _CTX50.ln(g))

    one = Decimal(1)
    if g_total > 0:
        lo, hi = one, None  # the other end is 1 (f(1) = G > 0), exactly as Ruling 6.2 step 3 says
        for i in range(1, IRR_BRACKET_EXPONENT + 1):
            candidate = Decimal(2) ** i
            if at(candidate) < 0:
                hi = candidate
                break
        if hi is None:
            return IrrRoot(None, False, IRR_OUT_OF_RANGE)
    else:
        hi, lo = one, None  # the other end is 1 (f(1) = G < 0)
        for i in range(1, IRR_BRACKET_EXPONENT + 1):
            candidate = _CTX50.divide(one, Decimal(2) ** i)
            if at(candidate) > 0:
                lo = candidate
                break
        if lo is None:
            return IrrRoot(None, False, IRR_OUT_OF_RANGE)
    for _ in range(IRR_MAX_ITERATIONS):
        if hi - lo <= IRR_STOP * hi:
            break
        mid = _CTX50.divide(_CTX50.add(lo, hi), Decimal(2))
        if at(mid) > 0:
            lo = mid
        else:
            hi = mid
    return IrrRoot(Fraction(_CTX50.divide(_CTX50.add(lo, hi), Decimal(2))), False)


def irr_is_unique(flows: Sequence[IrrFlow], g: Fraction) -> bool:
    """Ruling 6.3: the investor's running balance compounded at `g*`: `K_0 = -CF_0`, `K_j = K_{j-1} g*^(tau_j - tau_{j-1}) - CF_j` for every flow but the last.
    If every `K_j >= 0` the root is the only one. At `g = 1` the powers are exactly 1 and the test is exact; otherwise it is evaluated in Decimal prec 50."""
    flows = tuple(flows)
    if len(flows) < 2:
        return True
    if g == 1:
        k = -flows[0][1]
        if k < 0:
            return False
        for j in range(1, len(flows) - 1):
            k = k - flows[j][1]
            if k < 0:
                return False
        return True
    ln_g = _CTX50.ln(_dec50(g))
    k = _dec50(-flows[0][1])
    if k < 0:
        return False
    for j in range(1, len(flows) - 1):
        step = _CTX50.exp(_CTX50.multiply(_dec50(flows[j][0] - flows[j - 1][0]), ln_g))
        k = _CTX50.subtract(_CTX50.multiply(k, step), _dec50(flows[j][1]))
        if k < 0:
            return False
    return True
