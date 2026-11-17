"""CP4c: counting the days of a calendar NAMED by id (`marketdata.calendars.CalendarSet.by_id`, `count_after_calendar`). A benchmark names its index calculation calendar in the catalog (`risk/1.2` Ruling 5.2) instead of
being governed by an `applies_to` key; the counting rules are the same as `count_after`'s (coverage, completeness, the empty-interval rule, the actual-through note), and a test says so.
"""

import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp4_golden_kit as g  # noqa: E402

D = datetime.date


class CalendarByIdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendars = g.shared_runner(2).market.built.calendars  # part 2: SYN4_NYSE (every weekday 2022-12-01 .. 2026-03-31), SYN4_HKEX, SYN4_ECB, two RATE_PUBLICATIONS calendars

    def test_by_id_finds_a_calendar_and_only_that_calendar(self):
        self.assertEqual(self.calendars.by_id("SYN4_NYSE").calendar_id, "SYN4_NYSE")
        self.assertEqual(self.calendars.by_id("SYN4_RF_USD").kind.value, "RATE_PUBLICATIONS")
        self.assertIsNone(self.calendars.by_id("NOPE"))
        self.assertIsNone(self.calendars.by_id(None))

    def test_the_count_is_the_same_as_the_count_through_the_applies_to_key(self):
        for after, upto in ((D(2025, 1, 3), D(2025, 1, 10)), (D(2025, 1, 3), D(2025, 1, 3)), (D(2025, 1, 4), D(2025, 1, 6)), (D(2025, 1, 10), D(2025, 6, 30))):
            by_key = self.calendars.count_after("XNYS", after, upto)
            by_id = self.calendars.count_after_calendar("SYN4_NYSE", after, upto)
            self.assertEqual((by_id.missed, by_id.calendar, by_id.notes), (by_key.missed, by_key.calendar, by_key.notes), (after, upto))

    def test_hand_counts(self):
        self.assertEqual(self.calendars.count_after_calendar("SYN4_NYSE", D(2025, 1, 3), D(2025, 1, 10)).missed, 5)  # Mon .. Fri
        self.assertEqual(self.calendars.count_after_calendar("SYN4_NYSE", D(2025, 1, 3), D(2025, 1, 6)).missed, 1)   # over the weekend: Monday only
        self.assertEqual(self.calendars.count_after_calendar("SYN4_NYSE", D(2025, 1, 10), D(2025, 1, 10)).missed, 0)  # an empty interval on a session

    def test_an_empty_interval_on_a_day_that_is_no_session_cannot_be_counted(self):
        out = self.calendars.count_after_calendar("SYN4_NYSE", D(2025, 1, 4), D(2025, 1, 4))  # a Saturday: the calendar is complete inside its coverage and does not list it
        self.assertIsNone(out.missed)
        self.assertTrue(any("OFF_CALENDAR_DATE" in n for n in out.notes), out.notes)

    def test_outside_the_coverage_is_a_gap_not_a_guess(self):
        out = self.calendars.count_after_calendar("SYN4_NYSE", D(2026, 3, 30), D(2026, 4, 3))
        self.assertIsNone(out.missed)
        self.assertTrue(any("CALENDAR_COVERAGE_GAP" in n for n in out.notes), out.notes)
        before = self.calendars.count_after_calendar("SYN4_NYSE", D(2022, 11, 25), D(2022, 12, 5))
        self.assertIsNone(before.missed)

    def test_an_unknown_id_cannot_be_counted_and_says_so(self):
        out = self.calendars.count_after_calendar("NOPE", D(2025, 1, 3), D(2025, 1, 10))
        self.assertEqual((out.missed, out.calendar), (None, None))
        self.assertTrue(any("CALENDAR_COVERAGE_GAP" in n for n in out.notes))
        self.assertIsNone(self.calendars.count_after_calendar(None, D(2025, 1, 3), D(2025, 1, 10)).missed)


if __name__ == "__main__":
    unittest.main()
