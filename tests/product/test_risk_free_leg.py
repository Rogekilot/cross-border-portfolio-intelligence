"""CP4b-2: the risk-free leg (`risk/risk_free.py`; `risk/1.0` Rulings 4.1 to 4.5) and the `RISK_FREE` market-data kind it reads, checked against the Quant's hand-derived values.

The expected values are the Quant's (`methodology/fixtures/cp4_golden/cp4_golden_part1.json`): the twelve monthly risk-free returns of P1-S1 (the quote at each period's START, accrued as simple interest over the calendar days),
and the stale cases of P4-C2 (a quote two publications stale: LIMITED + STALE_DATA) and P4-C3 (five missed: INSUFFICIENT_DATA + STALE_DATA). The market data are expanded from the fixture's own compact definition
(`market_data.risk_free` and its `RATE_PUBLICATIONS` calendar) by the few lines below; nothing is taken from the engine.
"""

import dataclasses
import datetime
import json
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_cp2c1_kit as k  # noqa: E402

from domain.currency import CurrencyCode  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.manifest import MarketDataRelease  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.store import InMemoryMarketData, RiskFreeEntry  # noqa: E402
from product_contract.vocabulary import SufficiencyState  # noqa: E402
from risk import risk_free as rf  # noqa: E402

D, F, USD = datetime.date, Fraction, CurrencyCode("USD")
FIXTURE = ROOT / "methodology" / "fixtures" / "cp4_golden" / "cp4_golden_part1.json"
SHA = "ab" * 32


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def weekdays(first, last, gaps=()):
    out, d = [], first
    while d <= last:
        if d.weekday() < 5 and d.isoformat() not in gaps:
            out.append(d)
        d += datetime.timedelta(days=1)
    return out


def lineage():
    return c.Lineage("synthetic.riskfree", c.AdjustmentStatus.RAW, source_id="synthetic.riskfree", file_sha256=SHA, adapter_id="synthetic.riskfree.risk_free", adapter_version="1.0.0",
                     source_record_ref="series[0]", retrieved_at=k.NOW, usage_scope=c.UsageScope.SYNTHETIC_TEST)


def calendar_for(spec, dates=None):
    """The RATE_PUBLICATIONS calendar of the fixture (`SYN4_RF_USD`): every weekday in coverage, evidence synthetic."""
    cov_from, cov_to = D.fromisoformat(spec["coverage"]["from"]), D.fromisoformat(spec["coverage"]["to"])
    return c.CalendarDays(
        calendar_id=spec["calendar_id"], kind=c.CalendarKind.RATE_PUBLICATIONS, applies_to=tuple(spec["applies_to"]), timezone=spec["timezone"], covers_from=cov_from, covers_to=cov_to,
        dates=tuple(dates if dates is not None else weekdays(cov_from, cov_to)),
        actual_through=min(D.fromisoformat(spec["actual_through"]), cov_to), evidence=spec["evidence"], prepared_by="test",
        prepared_on=D(2026, 10, 2), version_label="v1", lineage=c.Lineage("calendar.manual", c.AdjustmentStatus.RAW, source_id="calendar.manual", file_sha256="cd" * 32,
                                                                           adapter_id="calendar.manual.calendar", adapter_version="0.1.0", source_record_ref=spec["calendar_id"],
                                                                           retrieved_at=k.NOW, usage_scope=c.UsageScope.SYNTHETIC_TEST),
        publication_time=datetime.time.fromisoformat(spec["publication"]["time"]))


def series_for(spec, **override):
    first, last = D.fromisoformat(spec["first"]), D.fromisoformat(spec["last"])
    steps = sorted((D.fromisoformat(s["from"]), Decimal(s["rate"])) for s in spec["steps"])
    points = []
    for day in weekdays(first, last, spec["gaps"]):
        rate = [r for f, r in steps if f <= day][-1]
        points.append(c.RiskFreePoint(day, rate))
    fields = dict(series_id=spec["series_id"], name="synthetic 13-week bill", provider="synthetic", currency=CurrencyCode(spec["currency"]), instrument=spec["instrument"],
                  tenor_weeks=13, quote_type=c.RiskFreeQuoteType(spec["quote_type"]), day_count_basis=spec["day_count_basis"], unit=c.RateUnit(spec["unit"]), decimals_published=2,
                  date_semantics="the date the quote is FOR (synthetic)", calendar_id=spec["calendar"], revision_policy=c.RevisionPolicy.NOT_REVISED, points=tuple(points),
                  timing=c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY), lineage=lineage(), licensing=c.LicensingMetadata(c.LicenseStatus.SYNTHETIC_TEST, False))
    fields.update(override)
    if fields["quote_type"] is c.RiskFreeQuoteType.BANK_DISCOUNT:  # a discount quote carries the term of its bill on every point (the contract refuses one without)
        fields["points"] = tuple(c.RiskFreePoint(p.value_date, p.rate, 91) for p in fields["points"])
    return c.RiskFreeSeries(**fields)


def world(spec_series, spec_calendar, calendar_dates=None, series_override=None):
    series = series_for(spec_series, **(series_override or {}))
    cal = calendar_for(spec_calendar, calendar_dates)
    store = InMemoryMarketData(MarketDataRelease(name="rf-test", files=(), source_precedence=()), risk_free=[RiskFreeEntry("synthetic.riskfree", "synthetic", SHA, series)])
    return store, market11_conventions(CalendarSet([cal]))


def fixture_world():
    d = fixture()
    (spec,) = d["market_data"]["risk_free"]["series"]
    (cal_spec,) = [x for x in d["market_data"]["calendars"] if x["calendar_id"] == spec["calendar"]]
    store, conventions = world(spec, cal_spec)
    return d, spec, store, conventions


class MonthlyRatesOfP1S1(unittest.TestCase):
    def test_the_twelve_monthly_returns_are_the_quants_exact_values(self):
        d, spec, store, conventions = fixture_world()
        (p1,) = [p for p in d["portfolios"] if p["name"].startswith("P1 ")]
        (item,) = [e for a in p1["assertions"] if a["id"] == "P1-S1" for e in a["expect"] if e["kind"] == "risk_free_rates"]
        grid = [D.fromisoformat(item["rates"][0]["period_start"])] + [D.fromisoformat(r["period_end"]) for r in item["rates"]]
        got = rf.risk_free_rates(store, USD, grid, conventions)
        self.assertEqual(len(got), 12)
        for expected, actual in zip(item["rates"], got):
            label = expected["period_end"]
            self.assertEqual((actual.start.isoformat(), actual.end.isoformat()), (expected["period_start"], expected["period_end"]), label)
            self.assertEqual(actual.quote_date.isoformat(), expected["quote_date"], label)
            self.assertEqual(actual.missed_publications, expected["missed_publications"], label)
            self.assertEqual(actual.exact, Fraction(expected["exact"]), label)
            self.assertIs(actual.valued.state, SufficiencyState.AVAILABLE, label)
            self.assertIsNone(actual.valued.reason, label)

    def test_the_quote_at_the_period_start_not_the_end(self):
        # July 2025 (06-30, 07-31] earns the 3.65 percent quoted on 06-30 (1/10000 a day, 31 days: 31/10000), NOT the 7.30 percent in force from 07-01 (31/5000)
        d, spec, store, conventions = fixture_world()
        (july,) = rf.risk_free_rates(store, USD, [D(2025, 6, 30), D(2025, 7, 31)], conventions)
        self.assertEqual(july.exact, F(31, 10000))
        self.assertNotEqual(july.exact, F(31, 5000))
        (august,) = rf.risk_free_rates(store, USD, [D(2025, 7, 31), D(2025, 8, 31)], conventions)
        self.assertEqual(august.exact, F(31, 5000))

    def test_interest_accrues_over_calendar_days_not_periods(self):
        # a daily period Friday -> Monday earns three days; a Monday -> Tuesday period earns one: 3.65 percent ACT/365 is exactly 1/10000 a day
        d, spec, store, conventions = fixture_world()
        weekend, midweek = rf.risk_free_rates(store, USD, [D(2025, 3, 7), D(2025, 3, 10), D(2025, 3, 11)], conventions)
        self.assertEqual((weekend.exact, midweek.exact), (F(3, 10000), F(1, 10000)))

    def test_the_rate_is_a_rational_never_a_float(self):
        d, spec, store, conventions = fixture_world()
        (p,) = rf.risk_free_rates(store, USD, [D(2025, 3, 3), D(2025, 3, 10)], conventions)
        self.assertIsInstance(p.exact, Fraction)
        self.assertEqual(p.exact, F(7, 10000))


class StaleCases(unittest.TestCase):
    def weekly(self, store, conventions, first, last):
        grid, day = [], first
        while day <= last:
            grid.append(day)
            day += datetime.timedelta(days=7)
        return rf.risk_free_rates(store, USD, grid, conventions)

    def test_p4_c2_a_quote_two_publications_stale_is_limited_with_stale_data(self):
        # quotes are missing on 2026-02-05 and 02-06: at the period start Friday 02-06 the latest quote is Wednesday 02-04 and the publications 02-05 and 02-06 were missed: m = 2
        d, spec, store, conventions = fixture_world()
        rates = self.weekly(store, conventions, D(2026, 1, 30), D(2026, 2, 27))
        by_start = {r.start: r for r in rates}
        stale = by_start[D(2026, 2, 6)]
        self.assertEqual((stale.quote_date, stale.missed_publications), (D(2026, 2, 4), 2))
        self.assertIs(stale.valued.state, SufficiencyState.LIMITED)
        self.assertEqual(stale.valued.reason, "STALE_DATA")
        self.assertEqual(stale.details, ("RISK_FREE_STALE",))
        self.assertIsNotNone(stale.exact)  # a LIMITED value is still a value (PD-0007): 7 days at 7.30 percent ACT/365 = 14/10000
        self.assertEqual(stale.exact, F(14, 10000))
        others = [r for s, r in by_start.items() if s != D(2026, 2, 6)]
        self.assertTrue(all(r.valued.state is SufficiencyState.AVAILABLE and r.valued.reason is None for r in others))

    def test_p4_c3_five_missed_publications_withhold_the_number(self):
        # quotes are missing 2026-03-02 .. 03-06: at Friday 03-06 the latest quote is 02-27 and five publications were missed: INSUFFICIENT_DATA + STALE_DATA, no value
        d, spec, store, conventions = fixture_world()
        rates = self.weekly(store, conventions, D(2026, 2, 27), D(2026, 3, 27))
        bad = [r for r in rates if r.valued.state is SufficiencyState.INSUFFICIENT_DATA]
        self.assertEqual([r.start for r in bad], [D(2026, 3, 6)])
        (r,) = bad
        self.assertEqual((r.valued.reason, r.details, r.exact, r.missed_publications), ("STALE_DATA", ("RISK_FREE_STALE",), None, 5))
        self.assertTrue(r.valued.causes)

    def test_the_thresholds_are_the_price_and_fx_thresholds_at_every_count(self):
        # m = 0, 1, 2, 3, 4, 5 publications missed: AVAILABLE, AVAILABLE+STALE, LIMITED x3, INSUFFICIENT+STALE (market-data Ruling 5.2, one staleness scale)
        d, spec, _, _ = fixture_world()
        (cal_spec,) = [x for x in d["market_data"]["calendars"] if x["calendar_id"] == spec["calendar"]]
        gaps = [(D(2025, 9, 1) + datetime.timedelta(days=i)).isoformat() for i in range(0, 40) if (D(2025, 9, 1) + datetime.timedelta(days=i)).weekday() < 5]
        spec = dict(spec, gaps=gaps, last="2025-12-31")
        store, conventions = world(spec, cal_spec)
        series = series_for(spec)
        have = {p.value_date for p in series.points}
        last_quote = max(p for p in have if p < D(2025, 9, 1))  # Friday 08-29
        cal_days = weekdays(D(2022, 12, 1), D(2026, 3, 31))
        expected = {0: (SufficiencyState.AVAILABLE, None), 1: (SufficiencyState.AVAILABLE, "STALE_DATA"), 2: (SufficiencyState.LIMITED, "STALE_DATA"), 3: (SufficiencyState.LIMITED, "STALE_DATA"),
                    4: (SufficiencyState.LIMITED, "STALE_DATA"), 5: (SufficiencyState.INSUFFICIENT_DATA, "STALE_DATA")}
        after = [day for day in cal_days if day > last_quote]
        for m, (state, reason) in expected.items():
            start = last_quote if m == 0 else after[m - 1]
            r = rf.period_rate(store.risk_free_on(USD, start, conventions), start, start + datetime.timedelta(days=7))
            self.assertEqual((r.missed_publications, r.valued.state, r.valued.reason), (m, state, reason), m)

    def test_no_series_means_no_risk_free_source_and_nothing_else(self):
        d, spec, store, conventions = fixture_world()
        for ccy in ("CNY", "HKD", "EUR"):
            (r,) = rf.risk_free_rates(store, CurrencyCode(ccy), [D(2025, 3, 3), D(2025, 3, 10)], conventions)
            self.assertIs(r.valued.state, SufficiencyState.INSUFFICIENT_DATA)
            self.assertIsNone(r.valued.reason)
            self.assertIsNone(r.exact)  # never a USD rate, never a constant, never 0
            self.assertEqual(r.details, ("NO_RISK_FREE_SOURCE",))
            self.assertIn(ccy, r.valued.causes[0].note)

    def test_no_quote_before_the_series_starts(self):
        d, spec, store, conventions = fixture_world()
        (r,) = rf.risk_free_rates(store, USD, [D(2022, 11, 25), D(2022, 12, 2)], conventions)
        self.assertEqual((r.valued.state, r.valued.reason, r.details, r.exact), (SufficiencyState.INSUFFICIENT_DATA, None, ("RISK_FREE_UNAVAILABLE",), None))

    def test_a_calendar_that_cannot_count_the_interval_withholds_the_number(self):
        d, spec, _, _ = fixture_world()
        (cal_spec,) = [x for x in d["market_data"]["calendars"] if x["calendar_id"] == spec["calendar"]]
        short = dict(cal_spec, coverage={"from": "2022-12-01", "to": "2025-03-14"})
        store, conventions = world(spec, short, calendar_dates=weekdays(D(2022, 12, 1), D(2025, 3, 14)))
        (r,) = rf.risk_free_rates(store, USD, [D(2025, 3, 21), D(2025, 3, 28)], conventions)  # the period start is past the calendar's coverage
        self.assertEqual((r.valued.state, r.valued.reason, r.details, r.exact), (SufficiencyState.INSUFFICIENT_DATA, None, ("CALENDAR_COVERAGE_GAP",), None))

    def test_a_series_whose_calendar_does_not_govern_it_cannot_be_counted(self):
        d, spec, _, _ = fixture_world()
        (cal_spec,) = [x for x in d["market_data"]["calendars"] if x["calendar_id"] == spec["calendar"]]
        store, conventions = world(spec, cal_spec, series_override={"calendar_id": "SOME_OTHER_CALENDAR"})  # the file says another calendar than the one that governs the series id
        (r,) = rf.risk_free_rates(store, USD, [D(2025, 3, 3), D(2025, 3, 10)], conventions)
        self.assertEqual((r.valued.state, r.details), (SufficiencyState.INSUFFICIENT_DATA, ("CALENDAR_COVERAGE_GAP",)))


class ConversionTests(unittest.TestCase):
    def series(self, quote_type, basis, unit=c.RateUnit.PERCENT, decimals=3):
        d, spec, _, _ = fixture_world()
        return series_for(spec, quote_type=quote_type, day_count_basis=basis, unit=unit, decimals_published=decimals)

    def test_simple_yield_on_act365_and_act360(self):
        s = self.series(c.RiskFreeQuoteType.SIMPLE_YIELD, 365)
        self.assertEqual(rf.daily_rate(s, c.RiskFreePoint(D(2025, 1, 2), Decimal("3.65"))), F(1, 10000))
        s360 = self.series(c.RiskFreeQuoteType.SIMPLE_YIELD, 360)
        self.assertEqual(rf.daily_rate(s360, c.RiskFreePoint(D(2025, 1, 2), Decimal("3.60"))), F(1, 10000))

    def test_a_decimal_unit_is_not_divided_by_100(self):
        s = self.series(c.RiskFreeQuoteType.SIMPLE_YIELD, 365, unit=c.RateUnit.DECIMAL, decimals=4)
        self.assertEqual(rf.daily_rate(s, c.RiskFreePoint(D(2025, 1, 2), Decimal("0.0365"))), F(1, 10000))

    def test_bank_discount_is_the_holding_period_return_per_day_of_the_term(self):
        # a 4.00 percent discount rate on a 91-day bill: price 1 - 0.04 x 91/360 = 1 - 91/9000, holding-period return (91/9000)/(1 - 91/9000) = 91/8909, per day of 91: 1/8909
        s = self.series(c.RiskFreeQuoteType.BANK_DISCOUNT, 360)
        self.assertEqual(rf.daily_rate(s, c.RiskFreePoint(D(2025, 1, 2), Decimal("4.00"), 91)), F(1, 8909))
        self.assertEqual(F(4, 100) / (360 - F(4, 100) * 91), F(1, 8909))
        self.assertEqual(rf.period_return(s, c.RiskFreePoint(D(2025, 1, 2), Decimal("4.00"), 91), D(2025, 1, 2), D(2025, 1, 9)), F(7, 8909))

    def test_a_negative_rate_is_a_rate(self):
        s = self.series(c.RiskFreeQuoteType.SIMPLE_YIELD, 365)
        self.assertEqual(rf.daily_rate(s, c.RiskFreePoint(D(2025, 1, 2), Decimal("-0.365"))), F(-1, 100000))

    def test_a_period_must_end_after_it_starts(self):
        s = self.series(c.RiskFreeQuoteType.SIMPLE_YIELD, 365)
        with self.assertRaises(ValueError):
            rf.period_return(s, c.RiskFreePoint(D(2025, 1, 2), Decimal("3.65")), D(2025, 1, 9), D(2025, 1, 9))


class StoreReadTests(unittest.TestCase):
    def test_the_series_read_trims_to_the_range_and_ambiguity_fails_closed(self):
        d, spec, store, conventions = fixture_world()
        got = store.risk_free_series(USD, D(2025, 3, 3), D(2025, 3, 7))
        self.assertEqual((got.outcome, [p.value_date.day for p in got.series[0].points]), (LookupOutcome.FOUND, [3, 4, 5, 6, 7]))
        self.assertEqual(store.risk_free_series(USD, D(2020, 1, 1), D(2020, 1, 31)).outcome, LookupOutcome.NO_OBSERVATION)
        self.assertEqual(store.risk_free_series(CurrencyCode("HKD"), D(2025, 3, 3), D(2025, 3, 7)).outcome, LookupOutcome.NOT_IN_RELEASE)
        # two series for one currency: the contract is one admitted series per currency, so nothing is picked
        series = series_for(spec)
        other = series_for(spec, series_id="SECOND_SERIES")
        two = InMemoryMarketData(MarketDataRelease(name="two", files=(), source_precedence=()), risk_free=[RiskFreeEntry("synthetic.riskfree", "synthetic", SHA, series),
                                                                                                                RiskFreeEntry("synthetic.riskfree2", "synthetic", "cd" * 32, other)])
        self.assertEqual(two.risk_free_series(USD, D(2025, 3, 3), D(2025, 3, 7)).outcome, LookupOutcome.NO_SELECTION)
        lookup = two.risk_free_on(USD, D(2025, 3, 7), conventions)
        self.assertEqual(lookup.outcome, LookupOutcome.NO_SELECTION)
        (r,) = rf.risk_free_rates(two, USD, [D(2025, 3, 7), D(2025, 3, 14)], conventions)
        self.assertEqual((r.valued.state, r.details, r.exact), (SufficiencyState.INSUFFICIENT_DATA, ("NO_RISK_FREE_SOURCE",), None))

    def segments(self, spec, cuts, **override_last):
        """The one series cut into files by row date (`cp4_golden/1.1-part3`: three file vintages per series). `cuts` are the first dates of the 2nd and later segments."""
        full = series_for(spec)
        bounds = [datetime.date.min] + list(cuts) + [datetime.date.max]
        out = []
        for i, (low, high) in enumerate(zip(bounds, bounds[1:])):
            pts = tuple(p for p in full.points if low <= p.value_date < high)
            lineage = dataclasses.replace(full.lineage, file_sha256=f"{i + 1:02x}" * 32)  # no vintage label anywhere in the key (market-data Ruling 0.1 (1.12))
            out.append(RiskFreeEntry("synthetic.riskfree", "synthetic", f"{i + 1:02x}" * 32, dataclasses.replace(full, points=pts, lineage=lineage)))
        return out

    def test_files_of_one_series_by_row_date_are_one_series_and_every_file_is_cited(self):
        d, spec, store, conventions = fixture_world()
        entries = self.segments(spec, [D(2025, 3, 1), D(2025, 6, 1)])
        three = InMemoryMarketData(MarketDataRelease(name="three", files=(), source_precedence=()), risk_free=entries)
        whole = store.risk_free_series(USD, D(2025, 2, 20), D(2025, 6, 10)).series[0].points
        got = three.risk_free_series(USD, D(2025, 2, 20), D(2025, 6, 10))
        self.assertEqual((got.outcome, got.series[0].points), (LookupOutcome.FOUND, whole))
        self.assertEqual(len(got.consumed), 3)
        for day in (D(2025, 2, 28), D(2025, 3, 3), D(2025, 6, 2)):  # a quote, a first day of a segment, another
            a, b = three.risk_free_on(USD, day, conventions), store.risk_free_on(USD, day, conventions)
            self.assertEqual((a.outcome, a.point, a.date_used, a.missed_count), (b.outcome, b.point, b.date_used, b.missed_count), day)
            self.assertEqual(len({r.file_sha256 for r in a.consumed} - {"cd" * 32}), 3, day)  # the three series files (and the calendar)

    def test_segments_that_overlap_or_disagree_or_differ_in_kind_are_not_one_series(self):
        d, spec, store, conventions = fixture_world()
        a, b, c3 = self.segments(spec, [D(2025, 3, 1), D(2025, 6, 1)])
        overlap = dataclasses.replace(b, series=dataclasses.replace(b.series, points=a.series.points[-1:] + b.series.points))  # one day in two files: two retrievals of that day
        for entries in ([a, overlap], [a, RiskFreeEntry("synthetic.riskfree", "synthetic", b.file_sha256, dataclasses.replace(b.series, unit=c.RateUnit.DECIMAL))],
                        [a, RiskFreeEntry("other.source", "synthetic", b.file_sha256, b.series)],
                        [a, RiskFreeEntry("synthetic.riskfree", "synthetic", b.file_sha256, dataclasses.replace(b.series, lineage=dataclasses.replace(b.series.lineage, usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY)))]):
            two = InMemoryMarketData(MarketDataRelease(name="bad", files=(), source_precedence=()), risk_free=entries)
            self.assertEqual(two.risk_free_series(USD, D(2025, 1, 1), D(2025, 12, 31)).outcome, LookupOutcome.NO_SELECTION)
            self.assertEqual(two.risk_free_on(USD, D(2025, 3, 7), conventions).outcome, LookupOutcome.NO_SELECTION)

    def test_ingest_never_lets_a_vintage_label_make_a_second_series_and_refuses_a_second_retrieval(self):
        # Ruling 0.1 (1.12): the rule lives in the release build (`_require_disjoint_segments`); the read-side join above only assembles what that build admitted. With no calendar and no manifest here a coverage
        # cannot be stated, so several files are refused; a label in the anchor is a difference of IDENTITY (checked first) and never a series of its own.
        from marketdata.calendars import CalendarSet  # noqa: PLC0415
        from marketdata.ingest import _require_disjoint_segments  # noqa: PLC0415
        from marketdata.segments import SegmentCoverageUndeterminedError, SegmentIdentityError  # noqa: PLC0415

        d, spec, store, conventions = fixture_world()
        a, b, c3 = self.segments(spec, [D(2025, 3, 1), D(2025, 6, 1)])
        args = (None, CalendarSet(), {}, None)
        with self.assertRaises(SegmentCoverageUndeterminedError):
            _require_disjoint_segments([], [], *args[:1], [a, b, c3], *args[1:])
        labelled = [RiskFreeEntry(e.source_id, e.independence_group, e.file_sha256, dataclasses.replace(e.series, lineage=dataclasses.replace(e.series.lineage, adjustment_anchor=f"V{i}"))) for i, e in enumerate((a, b))]
        with self.assertRaises(SegmentIdentityError):
            _require_disjoint_segments([], [], None, labelled, CalendarSet(), {}, None)
        real = RiskFreeEntry(b.source_id, b.independence_group, b.file_sha256, dataclasses.replace(b.series, lineage=dataclasses.replace(b.series.lineage, usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY)))
        with self.assertRaises(SegmentIdentityError):  # a real and a synthetic segment are never one series (Ruling 4.8; the identity check is first, whatever the coverage)
            _require_disjoint_segments([], [], None, [a, real], CalendarSet(), {}, None)
        _require_disjoint_segments([], [], None, [a], CalendarSet(), {}, None)  # one file never needs a coverage

    def test_a_lookup_cites_the_series_file_and_the_calendar_file_and_says_synthetic(self):
        d, spec, store, conventions = fixture_world()
        lookup = store.risk_free_on(USD, D(2025, 3, 7), conventions)
        self.assertEqual(lookup.outcome, LookupOutcome.FOUND)
        self.assertEqual({ref.file_sha256 for ref in lookup.consumed}, {SHA, "cd" * 32})
        self.assertTrue(lookup.synthetic)
        self.assertTrue(store.contains_synthetic)
        self.assertEqual((lookup.series.series_id, lookup.series.quote_type, lookup.series.tenor_weeks), ("SYN4_UST13_USD", c.RiskFreeQuoteType.SIMPLE_YIELD, 13))

    def test_a_registry_record_is_required_for_a_risk_free_source(self):
        # the store pins the registry records of EVERY served source, a risk-free source included (a manifest cannot be made over an unpinned source)
        from marketdata.manifest import SourceRegistryNotPinnedError  # noqa: PLC0415

        d, spec, store, conventions = fixture_world()
        with self.assertRaises(SourceRegistryNotPinnedError):
            store.source_registry_records()
        series = series_for(spec)
        from marketdata.manifest import SourceRecord  # noqa: PLC0415

        ok = InMemoryMarketData(MarketDataRelease(name="ok", files=(), source_precedence=()), risk_free=[RiskFreeEntry("synthetic.riskfree", "synthetic", SHA, series)],
                                source_records=[SourceRecord("synthetic.riskfree", "synthetic rf", "synthetic", "synthetic", synthetic=True)])
        self.assertEqual([r.source_id for r in ok.source_registry_records()], ["synthetic.riskfree"])
        liar = InMemoryMarketData(MarketDataRelease(name="liar", files=(), source_precedence=()), risk_free=[RiskFreeEntry("synthetic.riskfree", "synthetic", SHA, series)],
                                  source_records=[SourceRecord("synthetic.riskfree", "real?", "someone", "someone", synthetic=False)])
        with self.assertRaises(SourceRegistryNotPinnedError):
            liar.source_registry_records()  # a series that is synthetic under a record that says real (CP4-10 parity)


if __name__ == "__main__":
    unittest.main()
