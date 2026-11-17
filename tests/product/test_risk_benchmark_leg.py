"""CP4c: the benchmark leg (`risk/benchmark.py`; `risk/1.2` Rulings 5.1 to 5.4, 6.9): levels at the grid dates, the freshness counts, the translation into R at the ECB fixing, the period returns, and the ways a
series is refused as a reference.

The market is the Quant's part 2 (synthetic: a US gross total-return index on a 4-week level cycle 1000/1030/1010/990 with a two-day and a five-day gap, the same levels as a price return, a series first published
2025-07-04, and an HK net total-return index in HKD against an HKD/EUR rate that alternates weekly). The expected numbers are worked by hand in the comments from those definitions.
"""

import datetime
import json
import sys
import unittest
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp4_golden_kit as g  # noqa: E402

from domain.catalogs import parse_benchmark_catalog  # noqa: E402
from domain.currency import CurrencyCode  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.manifest import MarketDataRelease  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.store import BenchmarkEntry, InMemoryMarketData  # noqa: E402
from performance.grid import Frequency, grid_dates  # noqa: E402
from product_contract.vocabulary import SufficiencyState as SS  # noqa: E402
from risk import benchmark as B  # noqa: E402

D = datetime.date
USD, HKD = CurrencyCode("USD"), CurrencyCode("HKD")


class World:
    def __init__(self):
        self.runner = g.shared_runner(2)
        self.market = self.runner.market
        self.catalog = self.runner.catalog

    def leg(self, benchmark_id, reporting=USD, end=D(2026, 3, 31), catalog=None):
        cat = catalog or self.catalog
        return B.open_benchmark(cat.get(benchmark_id), benchmark_id, self.market.store, reporting, self.market.conventions, end)

    def catalog_with(self, benchmark_id, **changes):
        rows = [dict(e.to_obj(), **(changes if e.benchmark_id == benchmark_id else {})) for e in self.catalog.entries]
        return parse_benchmark_catalog(json.dumps({"catalog_id": "variant", "entries": rows}).encode(), allow_synthetic=True)


WORLD = None


def world() -> World:
    global WORLD
    if WORLD is None:
        WORLD = World()
    return WORLD


class LevelTests(unittest.TestCase):
    def test_a_level_on_a_calculation_day_is_current_and_exact(self):
        # Fri 2025-01-03 is 104 weeks after the cycle's start 2023-01-06: index 104 mod 4 = 0, level 1000.00
        lv = world().leg("SYN4_BM_US_TR").level_at(D(2025, 1, 3))
        self.assertEqual((lv.date_used, lv.missed, lv.level, lv.translated, lv.valued.state, lv.valued.reason, lv.details), (D(2025, 1, 3), 0, F(1000), F(1000), SS.AVAILABLE, None, ()))

    def test_between_two_days_the_latest_one_on_or_before_is_used(self):
        # the index calculates on every weekday and the level steps on Fridays: Wednesday 01-08 carries Friday 01-03's... no: the step in force on a day is the latest step on or before it
        lv = world().leg("SYN4_BM_US_TR").level_at(D(2025, 1, 8))
        self.assertEqual((lv.date_used, lv.missed, lv.level), (D(2025, 1, 8), 0, F(1000)))  # a point exists for every weekday; the step 1030 begins Friday 01-10

    def test_one_missed_calculation_day_is_available_with_stale_data(self):
        # the series has no 2026-01-15 and 2026-01-16: at 01-15 the latest level is 01-14's, one day missed
        lv = world().leg("SYN4_BM_US_TR").level_at(D(2026, 1, 15))
        self.assertEqual((lv.date_used, lv.missed, lv.valued.state, lv.valued.reason, lv.details), (D(2026, 1, 14), 1, SS.AVAILABLE, "STALE_DATA", ("BENCHMARK_STALE",)))
        self.assertIsNotNone(lv.translated)

    def test_two_to_four_missed_are_limited_and_five_withhold_the_level(self):
        leg = world().leg("SYN4_BM_US_TR")
        two = leg.level_at(D(2026, 1, 16))
        self.assertEqual((two.date_used, two.missed, two.valued.state, two.valued.reason), (D(2026, 1, 14), 2, SS.LIMITED, "STALE_DATA"))
        self.assertIsNotNone(two.translated)  # the value is kept at LIMITED
        # the gap 2026-02-23 .. 02-27 (a whole week): the latest day is Fri 02-20
        for day, missed, state in ((D(2026, 2, 23), 1, SS.AVAILABLE), (D(2026, 2, 24), 2, SS.LIMITED), (D(2026, 2, 26), 4, SS.LIMITED), (D(2026, 2, 27), 5, SS.INSUFFICIENT_DATA)):
            lv = leg.level_at(day)
            self.assertEqual((lv.date_used, lv.missed, lv.valued.state), (D(2026, 2, 20), missed, state), day)
        five = leg.level_at(D(2026, 2, 27))
        self.assertEqual((five.valued.reason, five.translated, five.valued.exact, five.details), ("STALE_DATA", None, None, ("BENCHMARK_STALE",)))  # no number

    def test_no_level_on_or_before_the_date_is_missing_benchmark_not_covering_the_window(self):
        lv = world().leg("SYN4_BM_US_TR_LATE").level_at(D(2025, 7, 3))  # first published 2025-07-04
        self.assertEqual((lv.valued.state, lv.valued.reason, lv.details, lv.date_used, lv.translated), (SS.INSUFFICIENT_DATA, "MISSING_BENCHMARK", ("BENCHMARK_NOT_COVERING_WINDOW",), None, None))
        self.assertEqual(world().leg("SYN4_BM_US_TR_LATE").level_at(D(2025, 7, 4)).valued.state, SS.AVAILABLE)

    def test_a_calendar_that_cannot_count_the_interval_gives_no_number_and_no_reason(self):
        w = world()
        leg = w.leg("SYN4_BM_US_TR")
        # past the calendar's coverage (to 2026-03-31) the missed count cannot be made
        lv = leg.level_at(D(2026, 4, 3))
        self.assertEqual((lv.valued.state, lv.valued.reason, lv.details), (SS.INSUFFICIENT_DATA, None, ("CALENDAR_COVERAGE_GAP",)))
        # a catalog that names a calendar M does not hold
        odd = w.leg("SYN4_BM_US_TR", catalog=w.catalog_with("SYN4_BM_US_TR", calendar_id="NO_SUCH_CALENDAR"))
        lv2 = odd.level_at(D(2025, 1, 3))
        self.assertEqual((lv2.valued.state, lv2.valued.reason, lv2.details), (SS.INSUFFICIENT_DATA, None, ("CALENDAR_COVERAGE_GAP",)))

    def test_levels_are_cached_and_the_files_read_are_cited(self):
        leg = world().leg("SYN4_BM_US_TR")
        self.assertIs(leg.level_at(D(2025, 1, 3)), leg.level_at(D(2025, 1, 3)))
        files = leg.consumed
        self.assertTrue(files and list(files) == sorted(set(files)))
        self.assertTrue(any(f.adapter_id.endswith(".calendar") for f in files))  # the calendar that counted the days
        self.assertTrue(any("benchmark" in f.adapter_id for f in files))


class TranslationTests(unittest.TestCase):
    def test_a_benchmark_in_r_needs_no_translation(self):
        leg = world().leg("SYN4_BM_US_TR")
        lv = leg.level_at(D(2025, 1, 10))
        self.assertEqual((lv.fx_rate, lv.fx_date_used, lv.translated, leg.currency_treatment), (None, None, F(1030), "NONE (benchmark already in R)"))

    def test_an_hkd_index_is_translated_into_usd_at_the_ecb_fixing_of_the_grid_date(self):
        # HKD per EUR alternates 8.4000 (even weeks) / 8.4420 (odd) from Fri 2023-01-06; USD per EUR is 1.0800. X(HKD->USD) = 1.08 / 8.4 = 9/70 (even), 1.08 / 8.442 = 60/469 (odd).
        # 2025-01-03 is week 104 (even): level 20000 x 9/70 = 18000/7.  2025-01-10 is week 105 (odd): level 21000 x 60/469 = 180000/67.
        leg = world().leg("SYN4_BM_HK_TR")
        a, b = leg.level_at(D(2025, 1, 3)), leg.level_at(D(2025, 1, 10))
        self.assertEqual((a.level, a.fx_rate, a.translated), (F(20000), F(9, 70), F(18000, 7)))
        self.assertEqual((b.level, b.fx_rate, b.translated), (F(21000), F(60, 469), F(180000, 67)))
        self.assertEqual(leg.currency_treatment, "TRANSLATED_UNHEDGED (ECB fixing u(g))")
        self.assertEqual((a.fx_date_used, a.fx_missed), (D(2025, 1, 3), 0))

    def test_the_period_return_is_the_ratio_of_the_translated_levels_so_the_fx_move_is_in_it(self):
        leg = world().leg("SYN4_BM_HK_TR")
        p = leg.period(D(2025, 1, 3), D(2025, 1, 10))
        # (180000/67) / (18000/7) - 1 = 70/67 - 1 = 3/67: in HKD the index rose 5 percent, the dollar-HKD move took part of it
        self.assertEqual(p.exact, F(3, 67))
        self.assertEqual(p.valued.state, SS.AVAILABLE)
        self.assertNotEqual(p.exact, F(21000, 20000) - 1)  # not the native return

    def test_the_two_legs_of_the_quant_are_the_same_in_usd_over_the_asserted_window(self):
        # Q2-T1: (g_0, g_n] = (2025-01-10, 2026-01-02]: HK index in USD, exactly -3/70
        leg = world().leg("SYN4_BM_HK_TR")
        self.assertEqual(leg.period(D(2025, 1, 10), D(2026, 1, 2)).exact, F(-3, 70))
        # and Q5-H1 (HKD reporting, no translation): the levels' own ratio, -1/21
        hk = world().leg("SYN4_BM_HK_TR", reporting=HKD)
        self.assertEqual(hk.currency_treatment, "NONE (benchmark already in R)")
        self.assertEqual(hk.period(D(2025, 1, 10), D(2026, 1, 2)).exact, F(-1, 21))

    def test_a_translation_that_cannot_be_made_makes_the_level_insufficient_with_the_fx_reason(self):
        leg = world().leg("SYN4_BM_HK_TR", reporting=CurrencyCode("CNY"))  # part 2 has no CNY fixing at all
        lv = leg.level_at(D(2025, 1, 10))
        self.assertEqual((lv.valued.state, lv.valued.reason, lv.translated), (SS.INSUFFICIENT_DATA, "MISSING_FX_HISTORY", None))


class PartThreeLegTests(unittest.TestCase):
    """The CN index of part 3 (CNY levels on the SSE calendar) against the ECB fixing: the translation is at the GRID date's fixing, whatever the level's own date is, and a stale fixing counts toward the leg."""

    @classmethod
    def setUpClass(cls):
        cls.runner = g.shared_runner(3)
        cls.leg = B.open_benchmark(cls.runner.catalog.get("SYN4_BM_CN_TR"), "SYN4_BM_CN_TR", cls.runner.market.store, USD, cls.runner.market.conventions, D(2026, 3, 31))

    def test_a_cny_level_is_translated_at_the_ecb_fixing_of_the_grid_date(self):
        # 2025-10-03 is week 143 of the 4-cycle (levels 5000/5100/5050/4950: index 3 = 4950); CNY per EUR alternates 7.8000 (even weeks) / 7.8390 (odd), so week 143 is 7.8390
        # and X(CNY -> USD) = 1.08 / 7.839 = 120/871; L_R = 4950 x 120/871 = 594000/871
        lv = self.leg.level_at(D(2025, 10, 3))
        self.assertEqual((lv.date_used, lv.missed, lv.level, lv.fx_date_used, lv.fx_missed), (D(2025, 10, 3), 0, F(4950), D(2025, 10, 3), 0))
        self.assertEqual((lv.fx_rate, lv.translated, lv.valued.state), (F(120, 871), F(594000, 871), SS.AVAILABLE))

    def test_the_fixing_is_the_grid_dates_even_when_the_level_is_older(self):
        # the US index has no level on 2026-01-15 and 01-16: at Fri 01-16 the latest is Wed 01-14's (in force since Fri 01-09: 1030), two missed. Reported in HKD, the translation is at the fixing OF 01-16
        # (week 158, even: 8.4000 HKD per EUR, so 8.4 / 1.08 = 70/9 HKD per USD), never at the level's own date 01-14 (week 157, odd: 8.4420)
        runner = g.shared_runner(2)
        leg = B.open_benchmark(runner.catalog.get("SYN4_BM_US_TR"), "SYN4_BM_US_TR", runner.market.store, HKD, runner.market.conventions, D(2026, 3, 31))
        lv = leg.level_at(D(2026, 1, 16))
        self.assertEqual((lv.date_used, lv.missed, lv.level, lv.fx_date_used, lv.fx_rate), (D(2026, 1, 14), 2, F(1030), D(2026, 1, 16), F(70, 9)))
        self.assertEqual((lv.translated, lv.valued.state, lv.valued.reason), (F(1030) * F(70, 9), SS.LIMITED, "STALE_DATA"))
        self.assertNotEqual(lv.fx_rate, F(469, 60))  # 8.4420 / 1.08: the rate of the level's own date is not what is used

    def test_a_stale_fixing_on_the_benchmark_leg_alone_is_limited_with_stale_data_and_counts(self):
        # the ECB file has no CNY quote on 2025-03-13 and 03-14: at Fri 03-14 the latest fixing is 03-12, two missed (LIMITED). The index level itself is current.
        lv = self.leg.level_at(D(2025, 3, 14))
        self.assertEqual((lv.date_used, lv.missed, lv.fx_date_used, lv.fx_missed), (D(2025, 3, 14), 0, D(2025, 3, 12), 2))
        self.assertEqual((lv.valued.state, lv.valued.reason, lv.translated is not None), (SS.LIMITED, "STALE_DATA", True))
        kinds = {e.kind: (e.missed, e.state) for e in lv.valued.freshness.entries}
        self.assertEqual(kinds, {"BENCHMARK": (0, "CURRENT"), "CURRENCY": (2, "STALE")})  # both legs' freshness stays visible (the lag of Ruling 8.2 needs it)

    def test_a_window_return_between_two_current_dates_is_not_touched_by_an_interior_stale_fixing(self):
        p = self.leg.period(D(2025, 1, 10), D(2026, 1, 2))
        self.assertEqual((p.valued.state, p.valued.reason), (SS.AVAILABLE, None))  # Ruling 6.9: g_0 and g_n only


class PeriodReturnTests(unittest.TestCase):
    def test_the_weekly_returns_of_the_cycle(self):
        leg = world().leg("SYN4_BM_US_TR")
        grid = grid_dates(Frequency.WEEKLY, D(2025, 1, 3), D(2025, 1, 31))
        got = [p.exact for p in leg.period_returns(grid)]
        self.assertEqual(got, [F(3, 100), F(-2, 103), F(-2, 101), F(1, 99)])  # 1030/1000, 1010/1030, 990/1010, 1000/990 - 1
        self.assertEqual([p.valued.state for p in leg.period_returns(grid)], [SS.AVAILABLE] * 4)

    def test_rs2_the_product_of_the_periods_is_the_ratio_of_the_end_levels_exactly(self):
        for name, reporting in (("SYN4_BM_US_TR", USD), ("SYN4_BM_HK_TR", USD), ("SYN4_BM_HK_TR", HKD)):
            leg = world().leg(name, reporting=reporting)
            grid = grid_dates(Frequency.WEEKLY, D(2025, 1, 10), D(2025, 12, 26))
            product = F(1)
            for p in leg.period_returns(grid):
                product *= 1 + p.exact
            self.assertEqual(product, leg.level_at(grid[-1]).translated / leg.level_at(grid[0]).translated, name)

    def test_a_period_takes_the_worse_state_of_its_two_levels(self):
        leg = world().leg("SYN4_BM_US_TR")
        p = leg.period(D(2026, 1, 2), D(2026, 1, 16))  # the end level is two days stale
        # 2026-01-02 is week 156 (level 1000); the end level is Wed 01-14's, in force since Fri 01-09 (week 157: 1030): 1030/1000 - 1 (the Quant's Q1-B3: 3/100, LIMITED + STALE_DATA)
        self.assertEqual((p.valued.state, p.valued.reason, p.exact), (SS.LIMITED, "STALE_DATA", F(3, 100)))
        dead = leg.period(D(2026, 2, 20), D(2026, 2, 27))  # the end level is withheld (five missed)
        self.assertEqual((dead.valued.state, dead.exact), (SS.INSUFFICIENT_DATA, None))

    def test_an_interior_level_is_not_an_input_of_a_window_return(self):
        leg = world().leg("SYN4_BM_US_TR")
        leg.period(D(2025, 1, 10), D(2025, 12, 26))
        self.assertEqual(sorted(leg._levels), [D(2025, 1, 10), D(2025, 12, 26)])  # Ruling 6.9: g_0 and g_n only


class RefusalTests(unittest.TestCase):
    def test_a_price_return_series_is_not_a_usable_reference_and_its_file_is_still_cited(self):
        w = world()
        out = w.leg("SYN4_BM_US_PR")
        self.assertIsInstance(out, B.BenchmarkRefusal)
        self.assertEqual((out.reason, out.detail), ("MISSING_BENCHMARK", "BENCHMARK_NOT_TOTAL_RETURN"))
        self.assertTrue(out.consumed)  # the file was read to learn what it is: a re-run reads it too

    def test_the_basis_is_the_catalogs_not_the_series_a_total_return_entry_is_usable(self):
        self.assertIsInstance(world().leg("SYN4_BM_US_TR"), B.BenchmarkLeg)
        out = world().leg("SYN4_BM_US_TR", catalog=world().catalog_with("SYN4_BM_US_TR", return_basis="PRICE_RETURN"))
        self.assertEqual(out.detail, "BENCHMARK_NOT_TOTAL_RETURN")

    def test_an_id_the_catalog_does_not_list_or_m_does_not_hold_is_unavailable(self):
        w = world()
        absent = B.open_benchmark(None, "SYN4_BM_ABSENT", w.market.store, USD, w.market.conventions, D(2026, 1, 2))
        self.assertEqual((absent.reason, absent.detail), ("MISSING_BENCHMARK", "BENCHMARK_SERIES_UNAVAILABLE"))
        rows = [dict(e.to_obj(), benchmark_id="SYN4_BM_ABSENT") for e in w.catalog.entries if e.benchmark_id == "SYN4_BM_US_TR"]
        cat = parse_benchmark_catalog(json.dumps({"catalog_id": "x", "entries": rows}).encode(), allow_synthetic=True)
        listed_not_held = B.open_benchmark(cat.get("SYN4_BM_ABSENT"), "SYN4_BM_ABSENT", w.market.store, USD, w.market.conventions, D(2026, 1, 2))
        self.assertEqual(listed_not_held.detail, "BENCHMARK_SERIES_UNAVAILABLE")
        self.assertEqual(listed_not_held.consumed, ())

    def test_a_series_that_disagrees_with_its_catalog_entry_is_unavailable_never_a_guess(self):
        w = world()
        wrong_currency = w.leg("SYN4_BM_US_TR", catalog=w.catalog_with("SYN4_BM_US_TR", currency="HKD"))
        self.assertEqual(wrong_currency.detail, "BENCHMARK_SERIES_UNAVAILABLE")
        self.assertIn("USD", wrong_currency.note)
        returns_form = w.leg("SYN4_BM_US_TR", catalog=w.catalog_with("SYN4_BM_US_TR", series_form="RETURNS"))
        self.assertEqual(returns_form.detail, "BENCHMARK_SERIES_UNAVAILABLE")

    def test_the_refusal_makes_a_part_with_the_reason_and_the_detail(self):
        out = world().leg("SYN4_BM_US_PR")
        part = out.part("benchmark")
        self.assertEqual((part.state, part.reason, [c.detail for c in part.causes]), (SS.INSUFFICIENT_DATA, "MISSING_BENCHMARK", ["BENCHMARK_NOT_TOTAL_RETURN"]))


class DirectWorldTests(unittest.TestCase):
    """A tiny world built from contract objects: the cases the part-2 data cannot make."""

    def series(self, values, benchmark_id="B", currency=USD, sha="ab" * 32, source="t", synthetic=True, anchor=None, kind=c.BenchmarkValueKind.LEVEL):
        lineage = c.Lineage("t", c.AdjustmentStatus.RAW, source_id=source, file_sha256=sha, adapter_id="t.benchmark", adapter_version="1", source_record_ref="r", retrieved_at=g.DEFAULT_RETRIEVED,
                            usage_scope=c.UsageScope.SYNTHETIC_TEST if synthetic else c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, adjustment_anchor=anchor)
        return c.BenchmarkSeries(benchmark_id, "p", tuple(c.BenchmarkPoint(d, v) for d, v in values), kind, currency, c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY), lineage,
                                 c.LicensingMetadata(c.LicenseStatus.SYNTHETIC_TEST if synthetic else c.LicenseStatus.INTERNAL_DEVELOPMENT_ONLY, False))

    def store(self, *entries):
        release = MarketDataRelease(name="direct", files=(), source_precedence=())
        return InMemoryMarketData(release, benchmarks=list(entries)), market11_conventions(CalendarSet([]))

    def entry(self, **kw):
        row = {"benchmark_id": "B", "name": "n", "provider": "p", "source_id": "t", "licensing": "l", "currency": "USD", "return_basis": "TOTAL_RETURN_GROSS", "dividend_treatment": "d",
               "calendar_id": "C", "series_form": "LEVELS", "proxy_of": None, "synthetic": True}
        row.update(kw)
        return parse_benchmark_catalog(json.dumps({"catalog_id": "d", "entries": [row]}).encode(), allow_synthetic=True).get("B")

    def test_two_sources_for_one_benchmark_are_not_reconciled_and_nothing_is_chosen(self):
        from decimal import Decimal  # noqa: PLC0415

        # two sources are Ruling 5.7 (1.2): reconciled by source_priority, which is DATA in the source registry. A store that carries no priority for them is REFUSED as a whole (never ordered by file order);
        # two files of one source on overlapping days are two retrievals of the same dates: not one series, and still raise
        a = BenchmarkEntry("s1", "g1", "aa" * 32, self.series([(D(2025, 1, 3), Decimal(100))], sha="aa" * 32, source="s1"))
        b = BenchmarkEntry("s2", "g2", "bb" * 32, self.series([(D(2025, 1, 10), Decimal(101))], sha="bb" * 32, source="s2"))
        store, conventions = self.store(a, b)
        refused = B.open_benchmark(self.entry(source_id="s1", additional_sources=[{"source_id": "s2", "return_basis": "TOTAL_RETURN_GROSS"}]), "B", store, USD, conventions, D(2025, 1, 10))
        self.assertIsInstance(refused, B.BenchmarkRefusal)
        self.assertEqual((refused.reason, refused.detail), ("MISSING_BENCHMARK", "BENCHMARK_SERIES_UNAVAILABLE"))
        self.assertIn("source_priority", refused.note)
        c1 = BenchmarkEntry("t", "g", "cc" * 32, self.series([(D(2025, 1, 3), Decimal(100))], sha="cc" * 32, anchor="V1"))
        c2 = BenchmarkEntry("t", "g", "dd" * 32, self.series([(D(2025, 1, 3), Decimal(101))], sha="dd" * 32, anchor="V2"))
        store2, conventions2 = self.store(c1, c2)
        with self.assertRaises(B.BenchmarkSourcesNotReconciled):
            B.open_benchmark(self.entry(), "B", store2, USD, conventions2, D(2025, 1, 10))

    def test_files_of_one_source_by_row_date_are_segments_of_one_series_and_every_file_is_cited(self):
        from decimal import Decimal  # noqa: PLC0415

        v1 = BenchmarkEntry("t", "g", "c1" * 32, self.series([(D(2025, 1, 3), Decimal(100)), (D(2025, 1, 6), Decimal(101))], sha="c1" * 32, anchor="V1"))
        v2 = BenchmarkEntry("t", "g", "c2" * 32, self.series([(D(2025, 1, 7), Decimal(102))], sha="c2" * 32, anchor="V2"))
        v3 = BenchmarkEntry("t", "g", "c3" * 32, self.series([(D(2025, 2, 3), Decimal(150))], sha="c3" * 32, anchor="V3"))  # nothing up to the read's end: holds nothing for it, still cited
        store, conventions = self.store(v1, v2, v3)
        leg = B.open_benchmark(self.entry(), "B", store, USD, conventions, D(2025, 1, 10))
        self.assertIsInstance(leg, B.BenchmarkLeg)
        self.assertEqual([d.day for d in leg.book.days], [D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7)])
        self.assertEqual({f.file_sha256 for f in leg.consumed}, {"c1" * 32, "c2" * 32, "c3" * 32})

    def test_a_real_and_a_synthetic_segment_are_never_one_series(self):
        from decimal import Decimal  # noqa: PLC0415

        a = BenchmarkEntry("t", "g", "e1" * 32, self.series([(D(2025, 1, 3), Decimal(100))], sha="e1" * 32, anchor="V1"))
        b = BenchmarkEntry("t", "g", "e2" * 32, self.series([(D(2025, 1, 6), Decimal(101))], sha="e2" * 32, anchor="V2", synthetic=False))
        store, conventions = self.store(a, b)
        with self.assertRaises(B.BenchmarkSourcesNotReconciled):
            B.open_benchmark(self.entry(), "B", store, USD, conventions, D(2025, 1, 10))

    def test_the_entry_is_bound_to_the_series_it_describes_cp4m_3(self):
        # the reviewer's demonstration: an entry that claims another source and synthetic=false must not be attached to a synthetic series of source `t`
        from decimal import Decimal  # noqa: PLC0415

        store, conventions = self.store(BenchmarkEntry("t", "g", "ab" * 32, self.series([(D(2025, 1, 3), Decimal(100))])))
        wrong_source = B.open_benchmark(self.entry(source_id="vendor.real.index"), "B", store, USD, conventions, D(2025, 1, 10))
        self.assertEqual((wrong_source.reason, wrong_source.detail, wrong_source.entry_bound), ("MISSING_BENCHMARK", "BENCHMARK_SERIES_UNAVAILABLE", False))
        self.assertIn("vendor.real.index", wrong_source.note)
        wrong_flag = B.open_benchmark(self.entry(synthetic=False), "B", store, USD, conventions, D(2025, 1, 10))
        self.assertEqual((wrong_flag.detail, wrong_flag.entry_bound), ("BENCHMARK_SERIES_UNAVAILABLE", False))
        self.assertIsInstance(B.open_benchmark(self.entry(), "B", store, USD, conventions, D(2025, 1, 10)), B.BenchmarkLeg)  # the bound entry passes

    def test_a_price_return_file_of_another_source_cannot_pass_as_total_return(self):
        # Ruling 5.4: the basis comes from the catalog, so the entry must describe THIS file. A real PRICE_RETURN file under the id, against an entry for the (total-return) synthetic source, is refused as unavailable
        from decimal import Decimal  # noqa: PLC0415

        store, conventions = self.store(BenchmarkEntry("vendor.price", "g", "f1" * 32, self.series([(D(2025, 1, 3), Decimal(100))], sha="f1" * 32, source="vendor.price", synthetic=False)))
        out = B.open_benchmark(self.entry(return_basis="TOTAL_RETURN_GROSS"), "B", store, USD, conventions, D(2025, 1, 10))
        self.assertEqual((out.detail, out.entry_bound), ("BENCHMARK_SERIES_UNAVAILABLE", False))

    def test_a_level_that_is_not_positive_is_not_a_reference(self):
        from decimal import Decimal  # noqa: PLC0415

        s = self.series([(D(2025, 1, 3), Decimal("0"))])
        store, conventions = self.store(BenchmarkEntry("s1", "g1", "ab" * 32, s))
        leg = B.open_benchmark(self.entry(), "B", store, USD, conventions, D(2025, 1, 10))
        lv = leg.level_at(D(2025, 1, 3))
        self.assertEqual((lv.valued.state, lv.valued.reason, lv.details), (SS.INSUFFICIENT_DATA, "MISSING_BENCHMARK", ("BENCHMARK_SERIES_UNAVAILABLE",)))

    def test_a_conventions_object_with_no_calendars_cannot_count(self):
        from decimal import Decimal  # noqa: PLC0415

        s = self.series([(D(2025, 1, 3), Decimal("100"))])
        store, conventions = self.store(BenchmarkEntry("s1", "g1", "ab" * 32, s))
        leg = B.open_benchmark(self.entry(), "B", store, USD, conventions, D(2025, 1, 10))
        lv = leg.level_at(D(2025, 1, 3))
        self.assertEqual((lv.valued.state, lv.details), (SS.INSUFFICIENT_DATA, ("CALENDAR_COVERAGE_GAP",)))


if __name__ == "__main__":
    unittest.main()
