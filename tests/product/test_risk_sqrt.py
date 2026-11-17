"""CP4b-2: the exact integer square root and its presentation (`risk/sqrt.py`; `risk/1.1` Ruling 3.4). The oracle is independent: `math.isqrt` for the integer root, and for the rounding an exact rational inequality
(the rounded magnitude `m` is the one with `((2m - 1)/2)^2 <= N < ((2m + 1)/2)^2`, or the tie), never the implementation's own comparison.
"""

import math
import random
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from risk.sqrt import DIGITS, isqrt, sqrt_rounded  # noqa: E402

F = Fraction


class IsqrtTests(unittest.TestCase):
    def test_against_math_isqrt_small_and_around_every_square(self):
        for n in range(0, 5000):
            self.assertEqual(isqrt(n), math.isqrt(n), n)
        for r in (1, 2, 3, 10, 12345, 10**6, 10**9 + 7, 2**31 - 1, 2**32, 10**15):
            for d in (-1, 0, 1):
                self.assertEqual(isqrt(r * r + d), math.isqrt(r * r + d), (r, d))

    def test_against_math_isqrt_on_huge_and_random_integers(self):
        rng = random.Random(20261002)
        for bits in (64, 65, 127, 128, 200, 1000, 4000):
            for _ in range(20):
                n = rng.getrandbits(bits)
                self.assertEqual(isqrt(n), math.isqrt(n), bits)
        big = 10**400 + 12345
        self.assertEqual(isqrt(big), math.isqrt(big))
        self.assertEqual(isqrt(big * big - 1), big - 1)
        self.assertEqual(isqrt(big * big), big)

    def test_a_negative_is_refused(self):
        with self.assertRaises(ValueError):
            isqrt(-1)


def oracle_magnitude(q, digits=DIGITS):
    """The correctly rounded magnitude of sqrt(q) in quanta, half up, by exact rational search around a float-free estimate."""
    n = q * 10 ** (2 * digits)
    m = math.isqrt(n.numerator // n.denominator)
    for cand in (m - 1, m, m + 1, m + 2):
        if cand < 0:
            continue
        low, high = F((2 * cand - 1), 2) ** 2, F((2 * cand + 1), 2) ** 2  # the interval of radicands that round to `cand`: [low, high), half up
        if low <= n < high:
            return cand
    raise AssertionError("the oracle found no magnitude")


class RoundingTests(unittest.TestCase):
    def test_hand_values(self):
        # sqrt(2009/50000000) = 0.006338769597...: the Quant's P4-C1 downside deviation (part 1), exact_square 2009/50000000
        r = sqrt_rounded(F(2009, 50000000), 1)
        self.assertEqual((r.quanta, r.value, r.exact), (6338769597, F(6338769597, 10**12), False))
        # a perfect square: sqrt(1/4) = 1/2 exactly
        half = sqrt_rounded(F(1, 4), 1)
        self.assertEqual((half.quanta, half.value, half.exact), (500000000000, F(1, 2), True))
        # a negative ratio keeps its sign after rounding
        self.assertEqual(sqrt_rounded(F(1, 4), -1).value, F(-1, 2))
        # the radicand is carried exactly
        self.assertEqual(sqrt_rounded(F(2107, 50000000), 1).exact_square, F(2107, 50000000))

    def test_zero(self):
        z = sqrt_rounded(F(0), 0)
        self.assertEqual((z.sign, z.quanta, z.value, z.exact), (0, 0, F(0), True))
        self.assertEqual(sqrt_rounded(F(0), 1).value, 0)  # a zero radicand is zero whatever sign was passed
        with self.assertRaises(ValueError):
            sqrt_rounded(F(1, 4), 0)
        with self.assertRaises(ValueError):
            sqrt_rounded(F(-1, 4), 1)
        with self.assertRaises(ValueError):
            sqrt_rounded(F(1, 4), 2)

    def test_an_exact_half_quantum_rounds_up_half_away_from_zero(self):
        # sqrt(q) = 0.5e-12 exactly: q = 0.25e-24 = 1/(4 x 10^24): the magnitude is 1 quantum, not 0
        q = F(1, 4 * 10**24)
        r = sqrt_rounded(q, 1)
        self.assertEqual(r.quanta, 1)
        self.assertEqual(sqrt_rounded(q, -1).value, F(-1, 10**12))
        # 1.5 quanta: sqrt(q) = 1.5e-12 -> 2
        self.assertEqual(sqrt_rounded(F(9, 4 * 10**24), 1).quanta, 2)
        # just below a half quantum rounds down, just above rounds up
        below = F(1, 4 * 10**24) - F(1, 10**60)
        above = F(1, 4 * 10**24) + F(1, 10**60)
        self.assertEqual((sqrt_rounded(below, 1).quanta, sqrt_rounded(above, 1).quanta), (0, 1))

    def test_every_rounding_agrees_with_the_independent_exact_oracle(self):
        rng = random.Random(7)
        cases = [F(rng.randrange(0, 10**9), rng.randrange(1, 10**9)) for _ in range(400)]
        cases += [F(rng.randrange(1, 10**6), 10**rng.randrange(0, 30)) for _ in range(400)]
        cases += [F(a * a, b * b) for a, b in ((1, 3), (2, 7), (22, 7), (10**6, 3), (1, 10**6), (355, 113))]  # rational squares: exact or half-quantum ties
        for q in cases:
            r = sqrt_rounded(q, 1)
            self.assertEqual(r.quanta, oracle_magnitude(q), q)
            # |rounded - sqrt| <= half a quantum, checked exactly with squares: ((2m-1)/2)^2 <= N <= ((2m+1)/2)^2 (in quanta^2)
            n = q * 10 ** (2 * DIGITS)
            self.assertLessEqual(F(2 * r.quanta - 1, 2) ** 2 if r.quanta else F(0), n)
            self.assertLessEqual(n, F(2 * r.quanta + 1, 2) ** 2)

    def test_the_result_is_a_rational_never_a_float_and_is_deterministic(self):
        r = sqrt_rounded(F(2, 3), 1)
        self.assertIsInstance(r.value, Fraction)
        self.assertEqual(r, sqrt_rounded(F(2, 3), 1))
        self.assertEqual(r.value.denominator, 10**12 // math.gcd(r.quanta, 10**12))

    def test_huge_and_tiny_radicands(self):
        self.assertEqual(sqrt_rounded(F(10**80), 1).quanta, 10**40 * 10**12)
        tiny = sqrt_rounded(F(1, 10**100), 1)  # sqrt = 1e-50: far below the quantum
        self.assertEqual(tiny.quanta, 0)
        self.assertFalse(tiny.exact)
        self.assertEqual(sqrt_rounded(F(10**30 + 1, 10**18), 1).quanta, oracle_magnitude(F(10**30 + 1, 10**18)))

    def test_digits_other_than_twelve_follow_the_same_rule(self):
        self.assertEqual(sqrt_rounded(F(2), 1, digits=3).quanta, 1414)    # 1.41421356...
        self.assertEqual(sqrt_rounded(F(2), 1, digits=0).quanta, 1)
        self.assertEqual(sqrt_rounded(F(6, 4), 1, digits=0).quanta, 1)    # 1.2247
        self.assertEqual(sqrt_rounded(F(9, 4), 1, digits=0).quanta, 2)    # exactly 1.5 -> half up -> 2


class QuantFixturePart1Values(unittest.TestCase):
    """The presented values of the Quant's part-1 square-root items, from their `exact_square`, with tolerance 0."""

    def test_every_sqrt_item_of_part_1_is_reproduced_exactly(self):
        import json  # noqa: PLC0415

        d = json.loads((ROOT / "methodology" / "fixtures" / "cp4_golden" / "cp4_golden_part1.json").read_text(encoding="utf-8"))
        checked = 0
        for p in d["portfolios"]:
            for a in p["assertions"]:
                for e in a["expect"]:
                    if e.get("exact_square") is None or e.get("value") is None:
                        continue
                    r = sqrt_rounded(F(e["exact_square"]), int(e["sign"]))
                    self.assertEqual(r.value * 10**12, int(F(e["value"]) * 10**12), (a["id"], e["kind"]))
                    self.assertEqual(r.exact_square, F(e["exact_square"]))
                    checked += 1
        self.assertGreaterEqual(checked, 20)


if __name__ == "__main__":
    unittest.main()
