"""CP4b-2: the grids and the window function (`performance/grid.py`; `risk/1.0` Rulings 2.2, 2.3, 7.1). Pure; no market data.

The expected windows are the Quant's (`methodology/fixtures/cp4_golden/cp4_golden_part1.json`, derived by hand): every assertion whose window does not depend on a computed period state is checked here, on its own,
as `risk/1.0` section 12 asks ("test it alone against every effective_window in part 1"). The engine composes the same three functions (`resolve_window`, the grid, `effective_window`).
"""

import datetime
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from performance.grid import (  # noqa: E402
    GRID_RULE_ID,
    Frequency,
    WeekdayFridayMonthEndGrid,
    effective_window,
    grid_dates,
    next_after,
    next_on_or_after,
    on_grid,
)
from performance.ledger_view import Inception  # noqa: E402
from performance.periods import WindowRule, WindowSpec, resolve_window, sub_months  # noqa: E402

D = datetime.date
FIXTURE = ROOT / "methodology" / "fixtures" / "cp4_golden" / "cp4_golden_part1.json"


class GridTests(unittest.TestCase):
    def test_daily_is_every_weekday_weekly_every_friday_monthly_the_last_day_of_the_month(self):
        week = [D(2026, 1, 5) + datetime.timedelta(days=i) for i in range(14)]  # Mon 2026-01-05 .. Sun 2026-01-18
        self.assertEqual([d.day for d in week if on_grid(Frequency.DAILY, d)], [5, 6, 7, 8, 9, 12, 13, 14, 15, 16])
        self.assertEqual([d.day for d in week if on_grid(Frequency.WEEKLY, d)], [9, 16])
        self.assertEqual([d for d in (D(2024, 2, 28), D(2024, 2, 29), D(2025, 2, 28), D(2025, 4, 29), D(2025, 4, 30), D(2025, 12, 31)) if on_grid(Frequency.MONTHLY, d)],
                         [D(2024, 2, 29), D(2025, 2, 28), D(2025, 4, 30), D(2025, 12, 31)])

    def test_next_on_or_after_for_every_weekday_and_the_three_frequencies(self):
        mon = D(2026, 1, 5)
        daily = [next_on_or_after(Frequency.DAILY, mon + datetime.timedelta(days=i)) for i in range(7)]
        self.assertEqual(daily, [D(2026, 1, 5), D(2026, 1, 6), D(2026, 1, 7), D(2026, 1, 8), D(2026, 1, 9), D(2026, 1, 12), D(2026, 1, 12)])
        weekly = [next_on_or_after(Frequency.WEEKLY, mon + datetime.timedelta(days=i)) for i in range(7)]
        self.assertEqual(weekly, [D(2026, 1, 9)] * 5 + [D(2026, 1, 16)] * 2)
        self.assertEqual(next_on_or_after(Frequency.MONTHLY, D(2026, 2, 1)), D(2026, 2, 28))
        self.assertEqual(next_on_or_after(Frequency.MONTHLY, D(2028, 2, 1)), D(2028, 2, 29))
        self.assertEqual(next_after(Frequency.WEEKLY, D(2026, 1, 9)), D(2026, 1, 16))
        self.assertEqual(next_after(Frequency.MONTHLY, D(2025, 12, 31)), D(2026, 1, 31))
        self.assertEqual(next_after(Frequency.DAILY, D(2026, 1, 9)), D(2026, 1, 12))

    def test_grid_dates_are_exactly_the_grid_in_range_and_agree_with_on_grid(self):
        for f in Frequency:
            got = grid_dates(f, D(2025, 11, 1), D(2026, 3, 31))
            brute = tuple(D(2025, 11, 1) + datetime.timedelta(days=i) for i in range((D(2026, 3, 31) - D(2025, 11, 1)).days + 1) if on_grid(f, D(2025, 11, 1) + datetime.timedelta(days=i)))
            self.assertEqual(got, brute, f)
        self.assertEqual(grid_dates(Frequency.WEEKLY, D(2026, 1, 10), D(2026, 1, 15)), ())  # a window with no Friday has no grid point

    def test_the_weekly_grid_is_inside_the_daily_grid_which_is_what_the_nesting_relies_on(self):
        daily = set(grid_dates(Frequency.DAILY, D(2023, 1, 1), D(2026, 1, 2)))
        self.assertTrue(set(grid_dates(Frequency.WEEKLY, D(2023, 1, 1), D(2026, 1, 2))) <= daily)

    def test_the_rule_gives_the_grid_in_the_requested_window_and_has_a_stable_id(self):
        class W:
            start, end = D(2026, 1, 2), D(2026, 1, 16)

        rule = WeekdayFridayMonthEndGrid()
        self.assertEqual(rule.rule_id, GRID_RULE_ID)
        self.assertEqual(rule.boundaries(Frequency.WEEKLY, W), (D(2026, 1, 2), D(2026, 1, 9), D(2026, 1, 16)))
        self.assertEqual(len(rule.boundaries(Frequency.DAILY, W)), 11)

    def test_full_windows_yield_the_counts_the_thresholds_are_derived_from(self):
        """Ruling 7.1: a full 1-, 3- or 5-year window always holds these observation counts, whatever its end date (checked here over every third end date from 2001 to 2029; the Quant counted every one)."""
        expected = {  # frequency -> {months: (min n, max n)}
            Frequency.DAILY: {12: (259, 262), 36: (781, 784), 60: (1304, 1305)},
            Frequency.WEEKLY: {12: (51, 52), 36: (155, 156), 60: (260, 261)},
            Frequency.MONTHLY: {12: (11, 12), 36: (35, 36), 60: (59, 60)},
        }
        seen = {(f, m): [10**9, 0] for f in Frequency for m in (12, 36, 60)}
        end = D(2001, 1, 1)
        while end <= D(2029, 12, 31):
            for f in Frequency:
                for months in (12, 36, 60):
                    base = sub_months(end, months)
                    n = len(grid_dates(f, base, end)) - 1
                    lo_hi = seen[(f, months)]
                    lo_hi[0], lo_hi[1] = min(lo_hi[0], n), max(lo_hi[1], n)
            end += datetime.timedelta(days=3 if True else 1)
        for f, by in expected.items():
            for months, (lo, hi) in by.items():
                self.assertEqual(tuple(seen[(f, months)]), (lo, hi), (f, months))


def window_for(request, as_of, frequency, i0):
    """The composition the engine performs, without market data."""
    if request["rule"] == "MAX_AVAILABLE":
        spec, rule_name, months = WindowSpec(WindowRule.SINCE_INCEPTION), "MAX_AVAILABLE", None
    elif request["rule"] == "TRAILING_MONTHS":
        spec, rule_name, months = WindowSpec(WindowRule.TRAILING_MONTHS, request["months"]), "TRAILING_MONTHS", request["months"]
    else:
        spec, rule_name, months = WindowSpec(WindowRule.CUSTOM, None, D.fromisoformat(request["base"])), "CUSTOM", None
    end = D.fromisoformat(as_of)
    resolved = resolve_window(spec, end, Inception(D.fromisoformat(i0), False), "NOT_RECONSTRUCTABLE")
    if resolved.window is None:
        return resolved.declared.start, None, resolved.cause.detail
    dates = grid_dates(Frequency(frequency), resolved.window.start, resolved.window.end)
    return resolved.window.start, effective_window(rule_name, months, Frequency(frequency), resolved.window.start, end, dates), None


class FixtureWindowTests(unittest.TestCase):
    def items(self):
        d = json.loads(FIXTURE.read_text(encoding="utf-8"))
        seen = set()
        for p in d["portfolios"]:
            for a in p["assertions"]:
                for e in a["expect"]:
                    if "request" not in e:
                        continue
                    ew = e.get("effective_window")
                    if ew is not None and ew.get("max_available_start") == "AFTER_INSUFFICIENT_PERIOD":
                        continue  # its start depends on a computed period state: the series tests cover it
                    key = (p["inception_base"], a["as_of"], e["frequency"], json.dumps(e["request"], sort_keys=True), e.get("requested_base"), json.dumps(ew, sort_keys=True))
                    if key not in seen:
                        seen.add(key)
                        yield a["id"], p["inception_base"], a["as_of"], e["frequency"], e["request"], e.get("requested_base"), ew, e

    def test_every_effective_window_of_part_1_that_needs_no_period_state_is_reproduced(self):
        checked = refused = 0
        for aid, i0, as_of, frequency, request, requested_base, ew, expect in self.items():
            base, window, detail = window_for(request, as_of, frequency, i0)
            self.assertEqual(base.isoformat(), requested_base, aid)  # requested_base is asserted for refusals too
            if ew is None:
                self.assertIsNone(window, aid)
                self.assertIn(detail, expect["details_include"], aid)
                refused += 1
                continue
            self.assertIsNone(detail, aid)
            got = {"base_date": window.base_date.isoformat(), "last_period_end": window.last_period_end.isoformat(), "observation_count": window.observation_count,
                   "stub_start_days": window.stub_start_days, "stub_end_days": window.stub_end_days}
            self.assertEqual(got, {k: v for k, v in ew.items() if k in got}, aid)
            checked += 1
        self.assertEqual(checked, 22)  # the distinct windows of part 1, less the two refusals and P7-F2 (its start depends on a period state)
        self.assertEqual(refused, 2)  # P3-A5 and P8-L1: a trailing request before inception is refused, never shortened

    def test_the_named_examples_of_ruling_2_3(self):
        # P3-A1 3Y weekly to Friday 2026-01-02: B = Mon 2023-01-02, g_0 = Fri 2023-01-06, n = 156, stubs 4 and 0
        base, w, _ = window_for({"rule": "TRAILING_MONTHS", "months": 36}, "2026-01-02", "WEEKLY", "2022-12-29")
        self.assertEqual((base, w.base_date, w.observation_count, w.stub_start_days, w.stub_end_days), (D(2023, 1, 2), D(2023, 1, 6), 156, 4, 0))
        # P3-A7 1Y weekly to Wednesday 2025-12-31: g_0 = 2025-01-03, g_n = 2025-12-26, n = 51, stubs 3 and 5
        _, w, _ = window_for({"rule": "TRAILING_MONTHS", "months": 12}, "2025-12-31", "WEEKLY", "2022-12-29")
        self.assertEqual((w.base_date, w.last_period_end, w.observation_count, w.stub_start_days, w.stub_end_days), (D(2025, 1, 3), D(2025, 12, 26), 51, 3, 5))
        # P1-S1 monthly 1Y to a month-end: g_0 = B, n = 12; P1-S2 the same request at 2025-12-30: n = 11, stubs 1 and 30
        _, w, _ = window_for({"rule": "TRAILING_MONTHS", "months": 12}, "2025-12-31", "MONTHLY", "2024-12-30")
        self.assertEqual((w.observation_count, w.stub_start_days, w.stub_end_days), (12, 0, 0))
        _, w, _ = window_for({"rule": "TRAILING_MONTHS", "months": 12}, "2025-12-30", "MONTHLY", "2024-12-30")
        self.assertEqual((w.observation_count, w.stub_start_days, w.stub_end_days), (11, 1, 30))

    def test_a_window_with_no_full_period_has_no_effective_window(self):
        # Sat 2026-01-03 .. Thu 2026-01-08: no Friday on or after B inside, so no weekly period
        dates = grid_dates(Frequency.WEEKLY, D(2026, 1, 3), D(2026, 1, 8))
        self.assertIsNone(effective_window("CUSTOM", None, Frequency.WEEKLY, D(2026, 1, 3), D(2026, 1, 8), dates))
        # exactly one grid point is not a period either
        dates = grid_dates(Frequency.WEEKLY, D(2026, 1, 3), D(2026, 1, 11))
        self.assertEqual(len(dates), 1)
        self.assertIsNone(effective_window("CUSTOM", None, Frequency.WEEKLY, D(2026, 1, 3), D(2026, 1, 11), dates))


if __name__ == "__main__":
    unittest.main()
