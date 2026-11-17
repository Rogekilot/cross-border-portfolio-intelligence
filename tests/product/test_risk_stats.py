"""CP4c: the exact statistics (`risk/stats.py`) and the maximum drawdown rule (`risk/1.2` Rulings 1.1, 1.5, 3.3, 6.2 to 6.6).

The oracles are independent of the code under test: centred sums computed the long way, a brute-force drawdown over every pair of grid points, and the Quant's P2 numbers (`cp4_golden` part 1) worked by hand below.
The COUNTER-CONVENTIONS of Ruling 1.5 (the rejected rules) are written here as plain functions; the tests show that they give the other numbers on P2, so the fixtures bite them.
"""

import random
import sys
import unittest
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from risk import stats  # noqa: E402


def centred_ssd(values):
    n = len(values)
    mean = sum(values, F(0)) / n
    return sum(((v - mean) ** 2 for v in values), F(0))


def centred_cross(xs, ys):
    n = len(xs)
    mx, my = sum(xs, F(0)) / n, sum(ys, F(0)) / n
    return sum(((x - mx) * (y - my) for x, y in zip(xs, ys)), F(0))


def brute_force_mdd(returns):
    """MDD = min over every pair j <= k of W_k / W_j - 1 (the largest fall from any earlier point to a later one), the base W_0 = 1 included."""
    wealth = [F(1)]
    for r in returns:
        wealth.append(wealth[-1] * (1 + r))
    return min([F(0)] + [wealth[k] / wealth[j] - 1 for j in range(len(wealth)) for k in range(j + 1, len(wealth))])


def all_history_mdd(returns, history_returns):
    """The REJECTED rule (M-DD1): the running peak over ALL history, then the drawdown at each point of the window."""
    wealth = [F(1)]
    for r in list(history_returns) + list(returns):
        wealth.append(wealth[-1] * (1 + r))
    peak, worst = wealth[0], F(0)
    for index, w in enumerate(wealth):
        peak = max(peak, w)
        if index >= len(history_returns):
            worst = min(worst, w / peak - 1)
    return worst


def peak_from_first_observation_mdd(returns):
    """The REJECTED rule (M-DD2): the peak search starts at g_1, so the base is not a candidate peak."""
    wealth = [F(1)]
    for r in returns:
        wealth.append(wealth[-1] * (1 + r))
    peak, worst = wealth[1], F(0)
    for w in wealth[1:]:
        peak = max(peak, w)
        worst = min(worst, w / peak - 1)
    return worst


class SumsTests(unittest.TestCase):
    def test_the_raw_sum_forms_equal_the_centred_sums_exactly(self):
        rng = random.Random(20261002)
        for _ in range(60):
            n = rng.randint(2, 40)
            xs = [F(rng.randint(-900, 900), rng.randint(1, 997)) for _ in range(n)]
            ys = [F(rng.randint(-900, 900), rng.randint(1, 997)) for _ in range(n)]
            self.assertEqual(stats.sum_squared_deviations(xs), centred_ssd(xs))
            self.assertEqual(stats.sum_cross_deviations(xs, ys), centred_cross(xs, ys))
            self.assertEqual(stats.sample_variance(xs), centred_ssd(xs) / (n - 1))  # n - 1 around a sample mean (Ruling 3.3)
            self.assertEqual(stats.sum_cross_deviations(xs, xs), stats.sum_squared_deviations(xs))

    def test_a_constant_series_has_zero_dispersion_exactly(self):
        self.assertEqual(stats.sample_variance([F(1, 7)] * 12), 0)
        self.assertEqual(stats.volatility_radicand([F(1, 7)] * 12, 52), 0)

    def test_inputs_that_cannot_give_a_statistic_are_refused(self):
        for call in (lambda: stats.mean([]), lambda: stats.sum_squared_deviations([]), lambda: stats.sample_variance([F(1)]), lambda: stats.sum_cross_deviations([F(1)], [F(1), F(2)])):
            with self.assertRaises(ValueError):
                call()

    def test_the_downside_sum_counts_only_the_periods_below_the_target_and_divides_by_the_full_n(self):
        d = [F(-1, 10), F(2, 10), F(0), F(-3, 10)]
        self.assertEqual(stats.shortfall_square_sum(d), F(1, 100) + F(9, 100))
        # Ruling 3.3: the full n (4), not the number of shortfalls (2): the rejected form would be twice as large
        self.assertEqual(stats.downside_radicand(d, 52), F(52) * F(10, 100) / 4)

    def test_radicands_are_the_rulings_formulas(self):
        r = [F(1, 10), F(-1, 20), F(3, 100), F(0)]
        d = [F(1, 10) - F(1, 1000), F(-1, 20) - F(1, 1000), F(3, 100) - F(1, 1000), F(-1, 1000)]
        s2 = centred_ssd(r) / 3
        dbar = sum(d, F(0)) / 4
        self.assertEqual(stats.volatility_radicand(r, 52), 52 * s2)
        self.assertEqual(stats.sharpe_radicand(dbar, s2, 52), 52 * dbar * dbar / s2)
        shortfall = sum((x * x for x in d if x < 0), F(0))
        self.assertEqual(stats.sortino_radicand(dbar, shortfall, 4, 52), 52 * dbar * dbar * 4 / shortfall)

    def test_sign_of(self):
        self.assertEqual([stats.sign_of(F(-1, 3)), stats.sign_of(F(0)), stats.sign_of(F(5))], [-1, 0, 1])


class DrawdownTests(unittest.TestCase):
    # P2 of part 1 (weekly closes 100 -> 120 -> 100 -> 110 -> 99 -> 105 from Fri 2025-12-05), worked by hand:
    # the window of P2-D1 has base 12-12 (level 100): r = 110/100 - 1, 99/110 - 1, 105/99 - 1
    D1 = [F(1, 10), F(-1, 10), F(2, 33)]
    # the window of P2-D2 has base 12-05 (level 120): r = 100/120 - 1, 110/100 - 1, 99/110 - 1, 105/99 - 1
    D2 = [F(-1, 6), F(1, 10), F(-1, 10), F(2, 33)]

    def test_p2_d1_peak_to_trough_within_the_window_from_the_base(self):
        dd = stats.max_drawdown(self.D1)
        self.assertEqual((dd.value, dd.peak, dd.trough, dd.recovery), (F(-1, 10), 1, 2, None))  # peak 12-19 (index 1), trough 12-26 (index 2), no recovery of 110
        self.assertEqual(dd.wealth, (F(1), F(11, 10), F(99, 100), F(99, 100) * F(35, 33)))

    def test_p2_d2_the_base_is_a_peak_candidate(self):
        dd = stats.max_drawdown(self.D2)
        self.assertEqual((dd.value, dd.peak, dd.trough), (F(-175, 1000), 0, 3))  # 99/120 - 1 = -0.175: the peak IS the base (index 0), the all-time high

    def test_the_rejected_conventions_give_the_other_numbers_on_p2(self):
        # M-DD1: all history. With the history of D1 (the move 100 -> 120 before the base) the window's figure would be -0.175, not -0.1
        history = [F(1, 5), F(-1, 6)]  # the first level 100, the high 120 on 12-05, back to 100 on 12-12 (the base of D1)
        self.assertEqual(all_history_mdd(self.D1, history), F(-175, 1000))
        self.assertNotEqual(all_history_mdd(self.D1, history), stats.max_drawdown(self.D1).value)
        # M-DD2: the peak search starting at g_1 misses the base as a peak: D2 would give -0.1, not -0.175
        self.assertEqual(peak_from_first_observation_mdd(self.D2), F(-1, 10))
        self.assertNotEqual(peak_from_first_observation_mdd(self.D2), stats.max_drawdown(self.D2).value)
        # the canonical rule is neither
        self.assertEqual(stats.max_drawdown(self.D1).value, F(-1, 10))
        self.assertEqual(stats.max_drawdown(self.D2).value, F(-175, 1000))

    def test_the_trough_is_the_earliest_and_the_peak_the_latest_at_the_high_water_mark(self):
        # M-DD4: the level is flat at 110 for three grid points before the decline: the peak is the LAST of them
        r = [F(1, 10), F(0), F(0), F(-1, 10)]
        dd = stats.max_drawdown(r)
        self.assertEqual((dd.peak, dd.trough), (3, 4))  # not index 1, the earliest valuation at 110
        # two equal troughs: the earliest keeps its place
        r2 = [F(-1, 10), F(1, 9), F(-1, 10)]
        dd2 = stats.max_drawdown(r2)
        self.assertEqual((dd2.value, dd2.peak, dd2.trough, dd2.recovery), (F(-1, 10), 0, 1, 2))

    def test_recovery_is_the_earliest_point_at_or_above_the_peak_after_the_trough(self):
        r = [F(1, 10), F(-1, 10), F(1, 99), F(1, 10)]  # W: 1, 1.1, 0.99, 1.0, 1.1: back to the peak at index 4 (equal counts as regained)
        dd = stats.max_drawdown(r)
        self.assertEqual((dd.peak, dd.trough, dd.recovery), (1, 2, 4))

    def test_no_fall_is_a_zero_with_no_dates(self):
        dd = stats.max_drawdown([F(1, 100), F(0), F(2, 100)])
        self.assertEqual((dd.value, dd.peak, dd.trough, dd.recovery), (0, None, None, None))
        self.assertEqual(stats.max_drawdown([F(0)] * 5).value, 0)  # a cash-only portfolio: a value, not a missing number

    def test_a_fall_in_the_first_period_is_a_drawdown_from_the_base(self):
        dd = stats.max_drawdown([F(-1, 4), F(1, 10)])
        self.assertEqual((dd.value, dd.peak, dd.trough), (F(-1, 4), 0, 1))

    def test_the_value_equals_the_brute_force_minimum_over_every_pair_and_obeys_rd3(self):
        rng = random.Random(19)
        for _ in range(120):
            n = rng.randint(1, 30)
            r = [F(rng.randint(-40, 45), rng.randint(41, 100)) for _ in range(n)]  # every return above -1: the wealth stays positive
            dd = stats.max_drawdown(r)
            self.assertEqual(dd.value, brute_force_mdd(r))
            self.assertLessEqual(dd.value, min([F(0)] + r))  # RD-3
            if dd.trough is not None:
                self.assertEqual(dd.wealth[dd.trough] / dd.wealth[dd.peak] - 1, dd.value)  # the dates reconcile with the value
                self.assertTrue(all(w < dd.wealth[dd.peak] or i == dd.peak or i > dd.trough or w == dd.wealth[dd.peak] for i, w in enumerate(dd.wealth)))

    def test_the_wealth_path_is_the_window_twr_so_rs1_holds(self):
        r = [F(3, 50), F(-1, 50), F(-3, 53)]
        path = stats.wealth_path(r)
        self.assertEqual(path[0], 1)
        self.assertEqual(path[-1], (1 + r[0]) * (1 + r[1]) * (1 + r[2]))

    def test_a_coarser_grid_never_shows_a_deeper_drawdown(self):
        # RD-4 as a property: the weekly path is a subsequence of the daily one
        rng = random.Random(4)
        for _ in range(50):
            daily = [F(rng.randint(-30, 30), 400) for _ in range(5 * rng.randint(2, 12))]
            weekly = []
            for i in range(0, len(daily), 5):
                factor = F(1)
                for x in daily[i:i + 5]:
                    factor *= 1 + x
                weekly.append(factor - 1)
            self.assertLessEqual(stats.max_drawdown(daily).value, stats.max_drawdown(weekly).value)


if __name__ == "__main__":
    unittest.main()
