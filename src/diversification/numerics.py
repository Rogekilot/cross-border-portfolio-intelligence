"""Exact signed radical sums with certified final rounding (CP5 §1)."""
from fractions import Fraction

from performance.numerics import round_half_up, to_decimal_exact
from risk.sqrt import isqrt


class PresentationTie(ValueError):
    """A disclosed HALF_UP boundary result, not missing statistical data."""
    def __init__(self, boundary, low, high, exact=None):
        super().__init__("PRESENTATION_TIE")
        self.boundary, self.low, self.high, self.exact = boundary, low, high, exact
        self.value = to_decimal_exact(round_half_up(boundary, 12))


def _rational_root(q):
    n, d = isqrt(q.numerator), isqrt(q.denominator)
    return Fraction(n, d) if n * n == q.numerator and d * d == q.denominator else None


def _combine_terms(terms):
    rational, grouped = Fraction(), {}
    for coefficient, q in terms:
        if not coefficient or not q:
            continue
        root = _rational_root(q)
        if root is not None:
            rational += coefficient * root
            continue
        for representative in sorted(grouped):
            factor = _rational_root(q / representative)
            if factor is not None:
                grouped[representative] += coefficient * factor
                break
        else:
            grouped[q] = grouped.get(q, Fraction()) + coefficient
    return rational, tuple((coefficient, q) for q, coefficient in sorted(grouped.items()) if coefficient)


def radical_sum(terms):
    """Return Decimal sum(c*sqrt(q)), never averaging rounded correlations."""
    terms = tuple((Fraction(c), Fraction(q)) for c, q in terms if c and q)
    if any(q < 0 for _, q in terms):
        raise ValueError("negative radicand")
    rational, terms = _combine_terms(terms)
    if not terms:
        scaled = abs(rational) * 10**12
        if scaled - scaled.numerator // scaled.denominator == Fraction(1, 2):
            raise PresentationTie(rational, rational, rational, exact=rational)
        return to_decimal_exact(round_half_up(rational, 12))
    digits = 16
    while True:
        scale = 10 ** digits
        low, high = rational, rational
        for coefficient, q in terms:
            n, d = isqrt(q.numerator), isqrt(q.denominator)
            if n * n == q.numerator and d * d == q.denominator:
                a = b = Fraction(n, d)
            else:
                z = q * scale * scale
                floor = isqrt(z.numerator // z.denominator)
                a, b = Fraction(floor, scale), Fraction(floor + 1, scale)
            if coefficient < 0:
                a, b = b, a
            low += coefficient * a
            high += coefficient * b
        rounded_low, rounded_high = round_half_up(low, 12), round_half_up(high, 12)
        if rounded_low == rounded_high:
            return to_decimal_exact(rounded_low)
        if high - low < Fraction(1, 10**40):
            boundary = (rounded_low + rounded_high) / 2
            raise PresentationTie(boundary, low, high)
        digits *= 2
