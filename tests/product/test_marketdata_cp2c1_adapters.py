"""CP2c-1 adapters on SYNTHETIC copies of the real structures: Alpha Vantage `alphavantage.us.quotes`
(profile OBSERVED in market-data/1.2, Example A-1), the ECB's own `ecb.eurofxref.fx`, and the calendar
file of Ruling 5.3. Nothing here reads or copies a downloaded vendor file; expected values are derived by
hand from the inputs shown."""

import datetime
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_cp2c1_kit as k  # noqa: E402

from marketdata import contracts as c  # noqa: E402
from marketdata.adapters.alphavantage import AlphaVantageQuoteAdapter  # noqa: E402
from marketdata.adapters.base import IssueCode  # noqa: E402
from marketdata.adapters.calendar_file import CalendarFileAdapter  # noqa: E402
from marketdata.adapters.ecb_eurofxref import EcbEurofxrefFxAdapter  # noqa: E402
from marketdata.manifest import DataKind, FileManifest  # noqa: E402
from marketdata.profiles import SOURCES, PROFILE_SET_VERSION, require_admitted  # noqa: E402

D = datetime.date
UTC = datetime.timezone.utc
AV_ROWS = [  # oldest first; the file lists them newest first
    ("2025-01-02", "100.0000", "101.5000", "99.2500", "100.5000", "1000"),
    ("2025-01-03", "100.5000", "102.0000", "100.0000", "101.2500", "1100"),
    ("2025-01-06", "101.2500", "101.7500", "100.1234", "100.7500", "900"),
]


def manifest(source, kind, fmt, symbols=(), currency=None, adjustment=c.AdjustmentStatus.UNDECLARED, request=()):
    return FileManifest(
        file_sha256="d" * 64, size_bytes=1, payload_filename="x", payload_format=fmt, source_id=source,
        data_kind=kind, retrieval_time=k.kit.RETRIEVED, retrieved_by="synthetic", declared_adjustment=adjustment,
        usage_scope=c.UsageScope.SYNTHETIC_TEST, declared_currency=currency, source_identifiers=symbols,
        declared_delay=c.DataDelayStatus.END_OF_DAY, request=request)


def av(rows=AV_ROWS, symbols=("AAPL",), adjustment=c.AdjustmentStatus.UNDECLARED,
       request=(("function", "TIME_SERIES_DAILY"), ("outputsize", "compact")), currency=k.USD, payload=None):
    m = manifest("alphavantage.us", DataKind.QUOTE, "alphavantage_csv_daily/1", symbols, currency, adjustment, request)
    return AlphaVantageQuoteAdapter().translate(m, payload if payload is not None else k.av_csv(rows))


class AlphaVantageTests(unittest.TestCase):
    def test_rows_arrive_newest_first_and_come_out_sorted_by_date(self):
        out = av()
        self.assertEqual(out.issues, ())
        self.assertEqual([q.value_date for q in out.quotes], [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)])
        self.assertEqual([q.price for q in out.quotes], [Decimal("100.5"), Decimal("101.25"), Decimal("100.75")])
        # the same facts delivered oldest first give the same output: no input order is assumed
        self.assertEqual(av(payload=k.av_csv(AV_ROWS, newest_first=False)), out)

    def test_the_session_date_is_the_timestamp_label_and_the_source_text_is_kept_verbatim(self):
        q = av().quotes[0]
        self.assertEqual(q.value_date, D(2025, 1, 2))
        self.assertEqual(q.lineage.source_value_text, "100.5000")  # 4 delivered decimals, trailing zeros kept
        self.assertEqual((q.identifiers.vendor_id, q.identifiers.source_id, q.identifiers.mic), ("AAPL", "alphavantage.us", None))
        self.assertEqual(q.currency, k.USD)

    def test_the_profile_is_observed_text_decimal_and_admitted(self):
        p = SOURCES["alphavantage.us"]
        self.assertEqual((p.status, p.upstream, p.function), ("OBSERVED", "alphavantage", "TIME_SERIES_DAILY"))
        self.assertEqual({f: p.fields[f].format.value for f in ("open", "high", "low", "close")},
                         {f: "TEXT_DECIMAL" for f in ("open", "high", "low", "close")})
        self.assertEqual(p.fields["close"].delivered_dp, 4)
        self.assertEqual((p.fields["volume"].status, p.fields["volume"].shares_per_unit, p.fields["volume"].integral),
                         ("DECLARED_UNVERIFIED", 1, True))
        self.assertTrue(require_admitted("alphavantage.us").admitted)
        self.assertEqual(av().quotes[0].lineage.precision_profile_id, f"{PROFILE_SET_VERSION}:alphavantage.us:close")
        self.assertFalse(av().quotes[0].lineage.precision_profile_id.startswith("placeholder/"))  # the placeholder is gone

    def test_a_close_on_the_cent_grid_is_recovered_and_off_the_grid_is_kept_but_not_recovered(self):
        rows = [("2025-01-02", "100.0000", "101.0000", "99.0000", "100.0250", "10"),   # 3 decimals at >= $1.00
                ("2025-01-03", "100.0000", "101.0000", "99.0000", "100.0200", "10")]
        a, b = av(rows).quotes
        self.assertEqual((a.price, a.recovered), (Decimal("100.0250"), False))
        self.assertEqual(a.precision_bound, Decimal("0.00005"))  # half a unit of the 4 delivered decimals (4.2)
        self.assertEqual((b.price, b.recovered, b.precision_bound), (Decimal("100.0200"), True, Decimal(0)))
        self.assertIn(IssueCode.PRICE_NOT_RECOVERED, [i.code for i in av(rows).issues])

    def test_sub_penny_open_high_low_are_not_grid_checked_only_the_row_check_applies(self):
        rows = [("2025-01-02", "100.0000", "101.0001", "99.9999", "100.5000", "10")]  # 47/300 such values were observed
        out = av(rows)
        self.assertEqual((len(out.quotes), out.issues), (1, ()))
        broken = [("2025-01-02", "100.0000", "101.0000", "100.2000", "100.5000", "10")]  # low above open
        bad = av(broken)
        self.assertEqual((bad.quotes, [i.code for i in bad.issues]), ((), [IssueCode.ROW_INCONSISTENT]))

    def test_volume_is_integral_shares_and_its_unit_stays_declared_unverified(self):
        out = av()
        self.assertEqual([q.volume for q in out.quotes], [Decimal(1000), Decimal(1100), Decimal(900)])
        self.assertEqual({q.lineage.volume_unit_status for q in out.quotes}, {"DECLARED_UNVERIFIED"})
        frac = av([("2025-01-02", "100.0000", "101.0000", "99.0000", "100.5000", "10.5")])
        self.assertEqual((frac.quotes, frac.issues[0].code), ((), IssueCode.PROFILE_CHECK_FAILED))  # not an integer

    def test_a_float32_signature_in_a_text_field_fails_the_profile_check(self):
        bad = av([("2025-01-02", "100.0000", "101.0000", "99.0000", "474.20001", "10")])
        self.assertEqual((bad.quotes, bad.issues[0].code), ((), IssueCode.PROFILE_CHECK_FAILED))

    def test_an_undeclared_manifest_of_time_series_daily_is_read_as_raw_with_no_library_in_lineage(self):
        q = av().quotes[0]
        self.assertIs(q.lineage.adjustment_status, c.AdjustmentStatus.RAW)
        self.assertEqual((q.lineage.library, q.lineage.library_function), (None, "TIME_SERIES_DAILY"))
        self.assertEqual(len(av().reference), 3)  # all four fields kept for Test V2 (verification-only)

    def test_an_undeclared_manifest_of_another_function_is_never_read_as_raw(self):
        out = av(request=(("function", "TIME_SERIES_DAILY_ADJUSTED"),))
        self.assertEqual((out.quotes, len(out.adjusted)), ((), 3))  # verification-only rows, label unknown
        self.assertIs(out.adjusted[0].label.adjustment_status, c.AdjustmentStatus.UNDECLARED)
        none = av(request=())
        self.assertEqual(none.quotes, ())

    def test_one_symbol_a_currency_and_the_columns_are_required(self):
        for symbols in ((), ("A", "B")):
            self.assertEqual(av(symbols=symbols).issues[0].code, IssueCode.MISSING_FIELD)
        self.assertEqual(av(currency=None).issues[0].code, IssueCode.UNDECLARED_CURRENCY)
        bad = AlphaVantageQuoteAdapter().translate(
            manifest("alphavantage.us", DataKind.QUOTE, "alphavantage_csv_daily/1", ("AAPL",), k.USD),
            b"date,close\n2025-01-02,1\n")
        self.assertEqual(bad.issues[0].code, IssueCode.UNKNOWN_FORMAT)

    def test_a_rate_limit_message_is_not_data(self):
        out = AlphaVantageQuoteAdapter().translate(
            manifest("alphavantage.us", DataKind.QUOTE, "alphavantage_csv_daily/1", ("AAPL",), k.USD),
            b'{"Information": "limit reached"}')
        self.assertEqual((out.quotes, out.issues[0].code), ((), IssueCode.UNKNOWN_FORMAT))


ECB_ROWS = [("2025-01-02", ["1.0800", "8.4000", "N/A"]), ("2025-01-03", ["1.0810", "8.4100", "7.8100"]),
            ("2025-01-06", ["1.0820", "8.4200", "7.8200"])]


def ecb(rows=ECB_ROWS, currencies=("USD", "HKD", "CNY"), symbols=(), request=(), payload=None, **kw):
    m = manifest("ecb.eurofxref", DataKind.FX, "ecb_eurofxref_hist_csv/1", symbols, None, c.AdjustmentStatus.RAW, request)
    return EcbEurofxrefFxAdapter().translate(m, payload if payload is not None else k.ecb_csv(rows, currencies, **kw))


class EcbEurofxrefTests(unittest.TestCase):
    def test_quotes_are_eur_based_exact_text_sorted_and_the_trailing_comma_is_ignored(self):
        out = ecb()
        usd = [o for o in out.fx if o.quote_currency == k.USD]
        self.assertEqual([(o.value_date, o.rate) for o in usd],
                         [(D(2025, 1, 2), Decimal("1.0800")), (D(2025, 1, 3), Decimal("1.0810")), (D(2025, 1, 6), Decimal("1.0820"))])
        self.assertTrue(all(o.base_currency == k.EUR for o in out.fx))
        self.assertEqual(usd[0].lineage.source_value_text, "1.0800")  # no re-rounding, trailing zeros kept
        self.assertEqual(out.fx, tuple(sorted(out.fx, key=lambda o: (o.value_date, o.quote_currency.code))))
        self.assertEqual(ecb(newest_first=False, trailing_comma=False), out)  # order and the trailing comma are irrelevant

    def test_the_fixing_instant_is_1410_europe_berlin_in_winter_and_summer(self):
        # market-data/1.8: 14:10 local = 13:10 UTC in winter (CET, UTC+1) and 12:10 UTC in summer (CEST, UTC+2)
        out = ecb([("2025-01-02", ["1.08"]), ("2025-07-01", ["1.10"])], ("USD",))
        winter, summer = out.fx
        self.assertEqual(winter.observed_at.astimezone(UTC), datetime.datetime(2025, 1, 2, 13, 10, tzinfo=UTC))
        self.assertEqual(summer.observed_at.astimezone(UTC), datetime.datetime(2025, 7, 1, 12, 10, tzinfo=UTC))
        self.assertEqual(winter.timing.source_time, winter.observed_at)
        self.assertIs(winter.timing.delay_status, c.DataDelayStatus.END_OF_DAY)

    def test_n_a_is_not_an_observation_and_is_never_filled(self):
        out = ecb(symbols=("USD", "CNY", "HKD"))
        cny = [o.value_date for o in out.fx if o.quote_currency == k.CNY]
        self.assertEqual(cny, [D(2025, 1, 3), D(2025, 1, 6)])  # the 2nd of January is N/A: no observation
        self.assertEqual([(i.row_ref, i.code) for i in out.issues], [("2025-01-02/CNY", IssueCode.MISSING_VALUE)])
        quiet = ecb()  # no named symbols: a single summary line, still not silent
        self.assertEqual([(i.row_ref, i.code) for i in quiet.issues], [("file", IssueCode.MISSING_VALUE)])

    def test_the_manifest_names_the_columns_and_the_read_window_and_nothing_else_is_translated(self):
        out = ecb(symbols=("USD",), request=(("read_start", "2025-01-03"), ("read_end", "2025-01-03")))
        self.assertEqual([(o.value_date, o.quote_currency.code) for o in out.fx], [(D(2025, 1, 3), "USD")])
        missing = ecb(symbols=("USD", "JPY"))
        self.assertEqual([i.row_ref for i in missing.issues], ["header/JPY"])
        self.assertEqual(ecb(request=(("read_start", "yesterday"),)).issues[0].code, IssueCode.UNKNOWN_FORMAT)

    def test_nothing_is_inverted_crossed_or_rebased_and_bad_cells_are_reported(self):
        out = ecb([("2025-01-02", ["1.08", "abc", "-1"])], ("USD", "HKD", "CNY"))
        self.assertEqual([(o.quote_currency.code, o.base_currency.code) for o in out.fx], [("USD", "EUR")])
        self.assertEqual(sorted(i.row_ref for i in out.issues), ["2025-01-02/CNY", "2025-01-02/HKD"])
        self.assertTrue(all(i.code is IssueCode.UNPARSEABLE_ROW for i in out.issues))

    def test_a_fixing_date_stated_twice_excludes_every_currency_series_of_the_file(self):
        """RE-RECORDED 2026-10-25 (F1 R4a, market-data/1.16 item 34, Test V0-FX). This was `..._reported_and_the_first_row_wins_nothing_is_averaged`: the
        first row (1.08) won over the second (9.99). Keeping either row chose which of two statements of one fixing is true, which only a resolution
        record may do. Now no rate of the file is output, the repeated date is reported, and each currency series is named as contradicted."""
        out = ecb([("2025-01-02", ["1.08"]), ("2025-01-02", ["9.99"])], ("USD",), newest_first=False)
        self.assertEqual(out.fx, ())
        self.assertEqual((out.issues[0].row_ref, out.issues[0].code), ("2025-01-02", IssueCode.DUPLICATE_SESSION_DATE))
        self.assertEqual([(c.test, c.currency, c.dates) for c in out.contradicted], [("V0_FX_DUPLICATE_DATE", "USD", (D(2025, 1, 2),))])

    def test_a_file_that_is_not_the_published_shape_is_refused(self):
        for payload in (b"", b"day,USD\n2025-01-02,1.08\n", b"\xff\xfe"):
            out = ecb(payload=payload)
            self.assertEqual((out.fx, out.issues[0].code), ((), IssueCode.UNKNOWN_FORMAT), payload)

    def test_the_profile_is_memory_status_prefers_ecb_and_has_no_placeholder_in_lineage(self):
        p = SOURCES["ecb.eurofxref"]
        self.assertEqual((p.status, p.upstream, p.role), ("MEMORY", "ecb", "PREFERRED_FX"))
        # C2-12 (CP2 review): this used to assert `p.admitted` ("MEMORY is admitted by the profile gate"). A MEMORY profile is
        # a recalled, never observed format: it must not read REAL data until the first real file has been profiled
        # (Appendix A.4, MD-OI-12), even if the owner attests the terms. Synthetic data is unaffected (it is exempt).
        self.assertFalse(p.admitted)
        self.assertIn("MEMORY", p.not_admitted_reason)


def calendar_manifest(**kw):
    return manifest("calendar.manual", DataKind.CALENDAR, "finweb_calendar_json/1", ("NYSE_SESSIONS",), None,
                    c.AdjustmentStatus.RAW)


def cal(payload):
    return CalendarFileAdapter().translate(calendar_manifest(), payload)


class CalendarFileTests(unittest.TestCase):
    def test_an_exchange_calendar_is_read_with_its_content_of_ruling_5_3(self):
        out = cal(k.calendar_json(dates=("2025-01-02", "2025-01-03", "2025-01-06"), actual_through="2025-01-03",
                                  close={"default": "16:00", "overrides": [{"date": "2025-01-03", "time": "13:00"}]}))
        self.assertEqual(out.issues, ())
        (calendar,) = out.calendars
        self.assertEqual((calendar.calendar_id, calendar.kind, calendar.applies_to, calendar.timezone),
                         ("NYSE_SESSIONS", c.CalendarKind.EXCHANGE_SESSIONS, ("XNYS", "XNAS"), "America/New_York"))
        self.assertEqual((calendar.covers_from, calendar.covers_to, calendar.actual_through),
                         (D(2025, 1, 1), D(2025, 1, 31), D(2025, 1, 3)))
        self.assertEqual(calendar.dates, (D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)))
        self.assertEqual((calendar.close_time(D(2025, 1, 2)), calendar.close_time(D(2025, 1, 3))),
                         (datetime.time(16, 0), datetime.time(13, 0)))  # the early-close override wins
        self.assertIsNone(calendar.close_time(D(2025, 1, 4)))  # not a session
        self.assertEqual((calendar.evidence, calendar.prepared_by, calendar.version_label),
                         ("synthetic: not a real holiday list", "test", "v1"))
        self.assertTrue(calendar.lineage.is_complete)

    def test_the_ecb_calendar_carries_the_fixing_and_publication_times(self):
        out = cal(k.calendar_json("ECB_FIXINGS", "ECB_FIXINGS", ("ECB",), "Europe/Berlin", dates=("2025-01-02",)))
        (calendar,) = out.calendars
        self.assertEqual((calendar.fixing_time, calendar.publication_time), (datetime.time(14, 10), datetime.time(16, 0)))
        wrong = cal(k.calendar_json("ECB_FIXINGS", "ECB_FIXINGS", ("ECB",), "Europe/Berlin", dates=("2025-01-02",),
                                    fixing={"time": "15:00", "publication": "16:00"}))
        self.assertEqual((wrong.calendars, wrong.issues[0].code), ((), IssueCode.CALENDAR_INVALID))
        self.assertIn("new convention version", wrong.issues[0].detail)

    def test_a_file_that_breaks_the_format_is_refused_whole_with_the_reason(self):
        good = json.loads(k.calendar_json())
        cases = {
            "unknown key": {**good, "holidays": []},
            "missing key": {key: v for key, v in good.items() if key != "evidence"},
            "wrong schema": {**good, "schema": "other/1"},
            "wrong zone": {**good, "timezone": "Europe/London"},
            "a MIC with no zone": {**good, "applies_to": ["XXXX"]},
            "dates not sorted": {**good, "dates": ["2025-01-03", "2025-01-02"]},
            "date outside coverage": {**good, "dates": ["2025-02-03"]},
            "no dates": {**good, "dates": []},
            "weekday rule instead of a list": {**good, "dates": "weekdays"},
            "two coverage intervals": {**good, "coverage": {"from": "2025-01-01", "to": "2025-01-31", "also": "x"}},
            "actual_through outside coverage": {**good, "actual_through": "2026-01-01"},
            "blank evidence": {**good, "evidence": " "},
            "early close on a non-session": {**good, "close": {"default": "16:00", "overrides": [{"date": "2025-01-20", "time": "13:00"}]}},
            "ecb key on an exchange calendar": {**good, "fixing": {"time": "14:10", "publication": "16:00"}},
        }
        for name, doc in cases.items():
            out = cal(json.dumps(doc).encode("utf-8"))
            self.assertEqual((out.calendars, [i.code for i in out.issues]), ((), [IssueCode.CALENDAR_INVALID]), name)
        self.assertEqual(cal(b"not json").issues[0].code, IssueCode.CALENDAR_INVALID)

    def test_a_calendar_must_not_be_derived_from_prices_so_the_format_has_no_price_input(self):
        text = (Path(__file__).resolve().parents[2] / "src" / "marketdata" / "adapters" / "calendar_file.py").read_text(encoding="utf-8")
        self.assertNotIn("QuoteObservation", text)
        self.assertNotIn("weekday", text.split('"""')[2])  # no rule in the code: only the docstring says "never"


if __name__ == "__main__":
    unittest.main()
