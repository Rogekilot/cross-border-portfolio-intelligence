"""CP2c-1 through the REAL path: files -> hash verification -> adapters -> resolver -> calendars ->
file-level checks (V0, V2, provenance) -> store -> market-data/1.2 conventions -> the analytics consumer.
Every file is SYNTHETIC (invented numbers in the structure of the real files); expected values are derived
by hand from the inputs shown."""

import dataclasses
import datetime
import json
import os
import sys
import tempfile
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_cp2c1_kit as k  # noqa: E402

kit = k.kit

from domain.instrument import SecurityType  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata.adapters.akshare_cn import AkshareCnQuoteAdapter  # noqa: E402
from marketdata.adapters.alphavantage import AlphaVantageQuoteAdapter  # noqa: E402
from marketdata.adapters.base import AdapterRegistry, IssueCode  # noqa: E402
from marketdata.adapters.calendar_file import CalendarFileAdapter  # noqa: E402
from marketdata.adapters.ecb_eurofxref import EcbEurofxrefFxAdapter  # noqa: E402
from marketdata.adapters.frankfurter import FrankfurterFxAdapter  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from marketdata.consumption import assemble_valuation_inputs  # noqa: E402
from marketdata.files import FileHashMismatchError, FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import (  # noqa: E402
    DataKind,
    MarketDataRelease,
    SourceRecord,
    SourceTermsNotAttestedError,
    TermsCheck,
    TwoVintagesError,
)
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata import profiles as prof  # noqa: E402
from marketdata.profiles import ProfileNotAdmittedError  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402
from marketdata.states import fx_input_state, price_input_state  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
UTC = datetime.timezone.utc
S, R = SufficiencyState, ReasonCode

AV_ROWS = [
    ("2025-01-02", "100.0000", "101.5000", "99.2500", "100.5000", "1000"),
    ("2025-01-03", "100.5000", "102.0000", "100.0000", "101.2500", "1100"),
    ("2025-01-06", "101.2500", "101.7500", "100.1234", "100.7500", "900"),
    ("2025-01-07", "100.7500", "103.0000", "100.5000", "102.5000", "1200"),
    ("2025-01-08", "102.5000", "103.2500", "101.0000", "102.0000", "1300"),
]
SESSIONS = ("2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09", "2025-01-10")
# synthetic ECB rows, oldest first: USD, HKD, CNY per EUR. HKD/USD stays inside the 7.75..7.85 peg band on each day.
ECB_ROWS = [("2025-01-02", ["1.0800", "8.4000", "7.8000"]), ("2025-01-03", ["1.0810", "8.4100", "7.8100"]),
            ("2025-01-06", ["1.0820", "8.4200", "7.8200"]), ("2025-01-07", ["1.0830", "8.4300", "7.8300"]),
            ("2025-01-08", ["1.0823", "8.4512", "7.8243"])]  # the last row is the Quant's Example 1-A fixing

synth = lambda sid, up, grp: SourceRecord(sid, sid, up, grp, synthetic=True)  # noqa: E731
SRC_AV = synth("alphavantage.us", "alphavantage", "alphavantage")
SRC_ECB = synth("ecb.eurofxref", "ecb", "ecb")
SRC_FRANK = synth("frankfurter.ecb", "ecb", "ecb")
SRC_CAL = synth("calendar.manual", "calendar", "calendar")
SRC_AKCN = synth("akshare.cn", "eastmoney", "eastmoney")


def identity():
    reg = InMemoryIdentityRegistry(kit.SequentialIds())
    reg.register_instruments([
        InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", k.USD,
                        vendor_ids=(("alphavantage.us", "AAPL"),)),
        InstrumentEntry("Tencent Holdings", SecurityType.COMMON_STOCK, "XHKG", "HKEX", "0700", k.HKD),
        InstrumentEntry("Kweichow Moutai", SecurityType.COMMON_STOCK, "XSHG", "SSE", "600519", k.CNY,
                        vendor_ids=(("akshare.cn", "600519"),)),
    ])
    return reg


def av_spec(rows=AV_ROWS, label="AAPL", currency=k.USD, **kw):
    spec = dict(source_id="alphavantage.us", kind=DataKind.QUOTE, payload_format="alphavantage_csv_daily/1",
                payload=k.av_csv(rows), label=label, ext="csv", currency=currency,
                adjustment=c.AdjustmentStatus.UNDECLARED, source_identifiers=("AAPL",),
                request=(("function", "TIME_SERIES_DAILY"), ("outputsize", "compact")), market="US")
    spec.update(kw)
    return spec


def ecb_spec(rows=ECB_ROWS, currencies=("USD", "HKD", "CNY"), label="ecb", **kw):
    spec = dict(source_id="ecb.eurofxref", kind=DataKind.FX, payload_format="ecb_eurofxref_hist_csv/1",
                payload=k.ecb_csv(rows, currencies), label=label, ext="csv", source_identifiers=tuple(currencies))
    spec.update(kw)
    return spec


def frank_spec(rows_by_day, label="frank", start=None, end=None):
    """rows_by_day: {"2025-01-02": {"USD": "1.0800"}} as Frankfurter's JSON (numbers as JSON number lexemes).
    `start` / `end`: the REQUESTED window the manifest records (Ruling 1.1a item 5 fixes the file's coverage from it)."""
    body = ",".join(f'"{d}":{{' + ",".join(f'"{c_}":{v}' for c_, v in q.items()) + "}" for d, q in sorted(rows_by_day.items()))
    text = '{"amount":1.0,"base":"EUR","rates":{' + body + "}}"
    ccys = sorted({c_ for q in rows_by_day.values() for c_ in q})
    request = tuple((key, value) for key, value in (("start", start), ("end", end)) if value is not None)
    return dict(source_id="frankfurter.ecb", kind=DataKind.FX, payload_format="frankfurter_json_timeseries/1",
                payload=text.encode("utf-8"), label=label, ext="json", source_identifiers=tuple(ccys), request=request)


def cal_spec(calendar_id, kind, applies_to, tz, dates, label=None, **kw):
    payload = k.calendar_json(calendar_id, kind, applies_to, tz, coverage=("2025-01-01", "2025-01-31"), dates=dates, **kw)
    return dict(source_id="calendar.manual", kind=DataKind.CALENDAR, payload_format="finweb_calendar_json/1",
                payload=payload, label=label or calendar_id, ext="json", source_identifiers=(calendar_id,))


def nyse_cal(**kw):
    return cal_spec("NYSE_SESSIONS", "EXCHANGE_SESSIONS", ("XNYS", "XNAS"), "America/New_York", SESSIONS,
                    close={"default": "16:00", "overrides": [{"date": "2025-01-03", "time": "13:00"}]}, **kw)


def ecb_cal(**kw):
    return cal_spec("ECB_FIXINGS", "ECB_FIXINGS", ("ECB",), "Europe/Berlin", SESSIONS, **kw)


ADAPTERS = (AlphaVantageQuoteAdapter(), EcbEurofxrefFxAdapter(), FrankfurterFxAdapter(), CalendarFileAdapter(),
            AkshareCnQuoteAdapter())


class WorldCase(unittest.TestCase):
    def world(self, specs, sources=(SRC_AV, SRC_ECB, SRC_FRANK, SRC_CAL, SRC_AKCN), ident=None, adapters=ADAPTERS,
              mutate=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=list(sources))
        manifests = [kit.write_file(root, **spec) for spec in specs]
        if mutate:
            mutate(root)
        files = FileStore(root)
        release = MarketDataRelease(name="r", files=tuple(sorted(m.file_sha256 for m in manifests)), source_precedence=())
        ident = ident or identity()
        built = build_in_memory_market_data(release, files, files.load_registry(), AdapterRegistry(list(adapters)), ident, catalog_calendars={})
        return built, ident

    def listing(self, ident, ticker, mic):
        return kit.listing_id(ident, ticker, mic)


class UsPriceThroughRealPathTests(WorldCase):
    def setUp(self):
        self.built, self.ident = self.world([av_spec(), nyse_cal(), ecb_cal()])
        self.aapl = self.listing(self.ident, "AAPL", "XNAS")
        self.conv = market11_conventions(self.built.calendars)

    def test_the_print_is_current_on_its_date_and_aged_by_the_sessions_missed_since(self):
        store = self.built.store
        for day, missed, want in ((D(2025, 1, 8), 0, (S.AVAILABLE, None)), (D(2025, 1, 9), 1, (S.AVAILABLE, R.STALE_DATA)),
                                  (D(2025, 1, 10), 2, (S.LIMITED, R.STALE_DATA))):
            lk = store.quote_on(self.aapl, day, self.conv)
            st = price_input_state(lk)
            self.assertEqual((lk.outcome, lk.missed_count, lk.date_used, (st.state, st.reason)),
                             (LookupOutcome.FOUND, missed, D(2025, 1, 8), want), day)
            self.assertEqual(lk.selected.observation.price, Decimal("102"))

    def test_an_as_of_date_inside_the_series_uses_that_dates_close_and_nothing_later(self):
        lk = self.built.store.quote_on(self.aapl, D(2025, 1, 6), self.conv)
        self.assertEqual((lk.date_used, lk.selected.observation.price), (D(2025, 1, 6), Decimal("100.75")))

    def test_every_alpha_vantage_quote_is_raw_with_an_unverifiable_label_and_its_own_upstream(self):
        lk = self.built.store.quote_on(self.aapl, D(2025, 1, 8), self.conv)
        lin = lk.selected.observation.lineage
        self.assertEqual((lin.adjustment_status, lin.label_status, lin.upstream, lin.independence_group),
                         (c.AdjustmentStatus.RAW, c.LabelStatus.UNVERIFIABLE, "alphavantage", "alphavantage"))
        self.assertEqual((lin.library, lin.precision_profile_id.split(":")[-2:]), (None, ["alphavantage.us", "close"]))
        self.assertIs(lk.reconciliation.status, c.ReconciliationStatus.SINGLE_SOURCE)  # the only US upstream

    def test_observed_at_is_the_scheduled_close_from_the_calendar_with_the_early_close_override(self):
        store = self.built.store
        regular = store.quote_on(self.aapl, D(2025, 1, 2), self.conv).selected.observation.observed_at
        early = store.quote_on(self.aapl, D(2025, 1, 3), self.conv).selected.observation.observed_at
        self.assertEqual(regular.astimezone(UTC), datetime.datetime(2025, 1, 2, 21, 0, tzinfo=UTC))  # 16:00 EST
        self.assertEqual(early.astimezone(UTC), datetime.datetime(2025, 1, 3, 18, 0, tzinfo=UTC))  # 13:00 EST override

    def test_the_calendars_are_part_of_the_result_and_of_the_consumed_files(self):
        lk = self.built.store.quote_on(self.aapl, D(2025, 1, 9), self.conv)
        sessions = next(cal for cal in self.built.calendars.calendars() if cal.calendar_id == "NYSE_SESSIONS")
        self.assertIn(sessions.lineage.file_sha256, {r.file_sha256 for r in lk.consumed})

    def test_v0_verifies_a_series_whose_dates_are_all_sessions_and_records_it(self):
        v0 = [r for r in self.built.label_results if r.test == "V0"]
        self.assertEqual([(r.status, r.admitted) for r in v0], [(c.LabelStatus.VERIFIED, True)])


class V0AtIngestTests(WorldCase):
    def test_a_series_dated_on_a_non_session_is_contradicted_and_not_admitted(self):
        rows = AV_ROWS[:2] + [("2025-01-04", "100.0000", "101.0000", "99.0000", "100.0000", "10")]  # a Saturday
        built, ident = self.world([av_spec(rows), nyse_cal()])
        (v0,) = [r for r in built.label_results if r.test == "V0"]
        self.assertEqual((v0.status, v0.admitted), (c.LabelStatus.CONTRADICTED, False))
        aapl = self.listing(ident, "AAPL", "XNAS")
        lk = built.store.quote_on(aapl, D(2025, 1, 3), market11_conventions(built.calendars))
        # market-data/1.3 section 9B #3 and Ruling 3.1 consequences: "every series CONTRADICTED" is a cause of
        # NO_HISTORY (was NOT_IN_RELEASE in 1.2): no reading is supplied, the file stays in M, and the failure is
        # kept in lineage
        self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_HISTORY, None))
        self.assertTrue(any(n.startswith("SERIES_CONTRADICTED: V0 on file") for n in lk.lineage_notes), lk.lineage_notes)
        self.assertEqual(price_input_state(lk).reason, R.MISSING_PRICE_HISTORY)
        self.assertEqual([(e.test, e.listing_id == aapl) for e in built.store.export().exclusions], [("V0", True)])

    def test_dates_outside_the_coverage_are_unverifiable_but_admitted(self):
        rows = AV_ROWS[:1] + [("2025-02-03", "100.0000", "101.0000", "99.0000", "100.0000", "10")]
        built, ident = self.world([av_spec(rows), nyse_cal()])
        (v0,) = [r for r in built.label_results if r.test == "V0"]
        self.assertEqual((v0.status, v0.admitted), (c.LabelStatus.UNVERIFIABLE, True))
        self.assertEqual(built.store.quotes(self.listing(ident, "AAPL", "XNAS"), D(2025, 1, 1), D(2025, 3, 1)).readings.__len__(), 2)

    def test_with_no_calendar_nothing_is_verified_and_nothing_is_dropped(self):
        built, ident = self.world([av_spec()])
        (v0,) = [r for r in built.label_results if r.test == "V0"]
        self.assertEqual((v0.status, v0.admitted), (c.LabelStatus.UNVERIFIABLE, True))
        self.assertIn("CALENDAR_COVERAGE_GAP", v0.reason)
        lk = built.store.quote_on(self.listing(ident, "AAPL", "XNAS"), D(2025, 1, 9), market11_conventions(built.calendars))
        self.assertEqual(lk.outcome, LookupOutcome.FRESHNESS_UNKNOWN)  # the count needs a calendar: no weekday guess
        self.assertEqual(price_input_state(lk).reason, None)


class CalendarFilesTests(WorldCase):
    def test_a_calendar_file_is_hashed_like_any_file_and_a_changed_byte_is_refused(self):
        def tamper(root):
            for path in root.rglob("NYSE_SESSIONS.json"):
                os.chmod(path, 0o644)
                path.write_bytes(path.read_bytes().replace(b"2025-01-02", b"2025-01-04", 1))

        with self.assertRaises(FileHashMismatchError):
            self.world([nyse_cal()], mutate=tamper)

    def test_two_calendar_files_with_one_calendar_id_are_two_vintages_and_refused(self):
        a = cal_spec("NYSE_SESSIONS", "EXCHANGE_SESSIONS", ("XNYS",), "America/New_York", SESSIONS, label="a")
        b = cal_spec("NYSE_SESSIONS", "EXCHANGE_SESSIONS", ("XNYS",), "America/New_York", SESSIONS[:-1], label="b")
        b["source_identifiers"] = ("OTHER_NAME",)  # the file name is not the key: the calendar_id is
        with self.assertRaises(TwoVintagesError):
            self.world([a, b])

    def test_a_mic_governed_by_two_calendars_makes_freshness_unknown_not_an_error(self):
        a = cal_spec("NYSE_A", "EXCHANGE_SESSIONS", ("XNAS",), "America/New_York", SESSIONS)
        b = cal_spec("NYSE_B", "EXCHANGE_SESSIONS", ("XNAS", "XNYS"), "America/New_York", SESSIONS)
        built, ident = self.world([av_spec(), a, b])
        lk = built.store.quote_on(self.listing(ident, "AAPL", "XNAS"), D(2025, 1, 9), market11_conventions(built.calendars))
        self.assertEqual(lk.outcome, LookupOutcome.FRESHNESS_UNKNOWN)
        self.assertIn("2 calendars govern XNAS", lk.lineage_notes[0])

    def test_an_invalid_calendar_is_reported_not_loaded_and_the_set_stays_empty(self):
        bad = cal_spec("NYSE_SESSIONS", "EXCHANGE_SESSIONS", ("XNYS",), "Europe/London", SESSIONS)  # wrong zone
        built, _ = self.world([bad])
        self.assertEqual(built.calendars.calendars(), ())
        self.assertEqual([i.code for _, i in built.issues], [IssueCode.CALENDAR_INVALID])


class SourceGateAndProfileTests(WorldCase):
    def test_a_refused_source_is_refused_before_its_payload_is_read_or_parsed(self):
        reads, translated = [], []

        class SpyStore(FileStore):
            def read_verified(self, manifest_path):
                reads.append(manifest_path)
                return super().read_verified(manifest_path)

        class SpyAdapter(AkshareCnQuoteAdapter):
            def translate(self, manifest, payload):
                translated.append(1)
                return super().translate(manifest, payload)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            refused = SourceRecord("akshare.cn", "x", "eastmoney", "eastmoney",
                                   terms_check=TermsCheck("owner", D(2026, 10, 1), False))
            kit.write_registry(root, extra=[refused])
            m = kit.write_file(root, "akshare.cn", DataKind.QUOTE, "akshare_csv_cn_daily/1", b"anything", "f", "csv",
                               usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, currency=k.CNY,
                               source_identifiers=("600519",), retrieved_by="human")
            files = SpyStore(root)
            release = MarketDataRelease.from_manifests("r", [m], [])
            with self.assertRaises(SourceTermsNotAttestedError):
                build_in_memory_market_data(release, files, files.load_registry(), AdapterRegistry([SpyAdapter()]), identity(), catalog_calendars={})
        self.assertEqual((reads, translated), ([], []))  # the payload was never opened and no adapter ran

    def test_an_attested_alpha_vantage_file_is_admitted_through_the_real_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = SourceRecord("alphavantage.us", "AV", "alphavantage", "alphavantage",
                                terms_check=TermsCheck("owner", D(2026, 10, 1), True))
            kit.write_registry(root, extra=[real])
            spec = av_spec(usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, retrieved_by="human")
            m = kit.write_file(root, **spec)
            files = FileStore(root)
            ident = identity()
            built = build_in_memory_market_data(MarketDataRelease.from_manifests("r", [m], []), files, files.load_registry(),
                                                AdapterRegistry([AlphaVantageQuoteAdapter()]), ident, catalog_calendars={})
            self.assertEqual(built.summaries[0].observation_count, 5)  # the profile is OBSERVED: admitted
            self.assertFalse(built.store.contains_synthetic)  # real data is not marked synthetic
            # C2-1: the lookup is ON the last print date, so a governing calendar covering it is part of the setup
            ny = k.exchange_calendar("NY", ("XNAS", "XNYS"), [D(2025, 1, d) for d in (2, 3, 6, 7, 8)],
                                     covers=(D(2025, 1, 1), D(2025, 1, 31)))
            lk = built.store.quote_on(kit.listing_id(ident, "AAPL", "XNAS"), D(2025, 1, 8),
                                      market11_conventions(CalendarSet([ny])))
            self.assertEqual((lk.outcome, lk.synthetic), (LookupOutcome.FOUND, False))

    def test_an_attested_source_with_no_profile_is_still_refused_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = SourceRecord(kit.CSV_SOURCE, "x", "x", "x", terms_check=TermsCheck("owner", D(2026, 10, 1), True))
            kit.write_registry(root, extra=[])
            # replace the synthetic registry entry of the test vendor by an attested non-synthetic one
            doc = json.loads((root / "SOURCES.json").read_text())
            doc["sources"] = [s for s in doc["sources"] if s["source_id"] != kit.CSV_SOURCE] + [{
                "source_id": real.source_id, "name": "x", "upstream_provider": "x", "independence_group": "x",
                "terms_check": {"checked_by": "owner", "checked_on": "2026-10-01", "permits_internal_development_use": True}}]
            (root / "SOURCES.json").write_text(json.dumps(doc))
            m = kit.write_file(root, kit.CSV_SOURCE, DataKind.QUOTE, kit.CSV_FORMAT, kit.csv_quotes_payload(), "q", "csv",
                               usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, currency=k.USD, retrieved_by="human")
            files = FileStore(root)
            with self.assertRaises(ProfileNotAdmittedError):
                build_in_memory_market_data(MarketDataRelease.from_manifests("r", [m], []), files, files.load_registry(),
                                            AdapterRegistry([kit.CsvQuoteAdapter()]), identity(), catalog_calendars={})

    def test_a_reading_in_a_currency_other_than_the_listings_is_refused_at_ingest(self):
        built, ident = self.world([av_spec(currency=k.HKD)])  # AAPL trades in USD
        self.assertEqual(built.summaries[0].observation_count, 0)
        self.assertEqual({i.code for _, i in built.issues}, {IssueCode.TRADING_CURRENCY_MISMATCH})
        lk = built.store.quote_on(self.listing(ident, "AAPL", "XNAS"), D(2025, 1, 8), market11_conventions(CalendarSet()))
        self.assertEqual(lk.outcome, LookupOutcome.NOT_IN_RELEASE)  # a data error, not a comparison outcome


def akshare_csv(closes, shift=None, factor=None, lots=1000, break_row=None):
    """akshare.cn-shaped daily rows (the format record of a REFUSED source: parsed here from a SYNTHETIC copy
    only). open = close, high = close + 1, low = close - 1; amount = close x lots x 100 (so 100 shares per lot)."""
    head = "日期,股票代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率"
    lines = [head]
    prev = None
    for day, close in zip(("2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08"), closes):
        v = Decimal(close)
        def adj(x):
            if shift is not None:
                return x - Decimal(shift)
            if factor is not None:
                return x * Decimal(factor)
            return x
        o, h, l_, cl = adj(v), adj(v + 1), adj(v - 1), adj(v)
        if break_row == day:
            cl += Decimal("0.5")
            h = max(h, cl)
        change = "0.0" if prev is None else str(cl - prev)
        prev = cl
        amount = v * lots * 100
        lines.append(",".join([day, "600519", f"{o:.2f}", f"{cl:.2f}", f"{h:.2f}", f"{l_:.2f}", str(lots), f"{amount:.1f}",
                               "0", "0", change, "0"]))
    return ("\n".join(lines) + "\n").encode("utf-8")


CLOSES = ("100.00", "90.00", "80.00", "110.00", "120.00")  # lo = 80, hi = 120


def ak_spec(payload, label, adjustment, anchor=None):
    return dict(source_id="akshare.cn", kind=DataKind.QUOTE, payload_format="akshare_csv_cn_daily/1", payload=payload,
                label=label, ext="csv", currency=k.CNY, adjustment=adjustment, source_identifiers=("600519",),
                anchor=anchor, request=(("function", "stock_zh_a_hist"),), market="CN")


REAL_EASTMONEY = prof.SOURCES["akshare.cn"]  # captured at import, before any test patches the registry


def eastmoney_profile_without_ohl_decimals():
    """The Eastmoney profile as it was in 1.4: open/high/low with NO `delivered_dp`. Appendix A.3 (1.5, A.4 item 7)
    now declares 2 for them, so the real profile runs V2 and Example 3-C reproduces from it (the V2 tests below use the
    REAL profile). This stand-in keeps the 1.4 rule testable: without a declared `delivered_dp`, V2 stops with
    PROFILE_INCOMPLETE and half an ulp of binary64 is no substitute (C2-10)."""
    real = prof.SOURCES["akshare.cn"]
    fields = dict(real.fields)
    for name in ("open", "high", "low"):
        fields[name] = dataclasses.replace(fields[name], delivered_dp=None)
    return dataclasses.replace(real, fields=fields)


class V2AtIngestTests(WorldCase):
    def label(self, shift=None, factor=None, break_row=None):
        raw = ak_spec(akshare_csv(CLOSES), "raw", c.AdjustmentStatus.RAW)
        adj = ak_spec(akshare_csv(CLOSES, shift=shift, factor=factor, break_row=break_row), "qfq",
                      c.AdjustmentStatus.UNDECLARED, anchor="akshare.stock_zh_a_hist adjust=qfq")
        built, ident = self.world([raw, adj])
        (v2,) = [r for r in built.label_results if r.test == "V2"]
        rows = built.store.adjusted_series(self.listing(ident, "600519", "XSHG"))
        return built, v2, rows

    def test_a_subtractive_series_gets_its_method_and_an_unverifiable_label_from_the_affine_fit(self):
        # adj = raw - 7.50 on every field: a = (112.5 - 72.5) / (120 - 80) = 1, b = 120 - 112.5 = 7.5; the profile's
        # adjusted_dp 2 gives delta_j = 1/200, so u_b = 1/200 + 80/4000 = 0.025 and 7.5 is far above it
        built, v2, rows = self.label(shift="7.50")
        self.assertEqual((v2.status, v2.method), (c.LabelStatus.UNVERIFIABLE, "SUBTRACTIVE"))  # no confirmed event: no check (c)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r.label.method is c.AdjustmentMethod.SUBTRACTIVE for r in rows))
        self.assertTrue(all(r.label.adjustment_status is c.AdjustmentStatus.DIVIDEND_ADJUSTED for r in rows))
        self.assertTrue(all((r.lineage.label_status, r.lineage.adjustment_method) == (c.LabelStatus.UNVERIFIABLE, "SUBTRACTIVE")
                            for r in rows))
        self.assertTrue(all(r.label.anchor is None for r in rows))  # the anchor is verified only with events

    def test_a_proportional_series_is_told_apart(self):
        _, v2, rows = self.label(factor="0.99")
        self.assertEqual((v2.status, v2.method), (c.LabelStatus.UNVERIFIABLE, "PROPORTIONAL"))

    def test_a_row_that_breaks_the_fit_contradicts_the_label_and_the_method_stays_unknown(self):
        _, v2, rows = self.label(shift="7.50", break_row="2025-01-06")  # that close is 0.5 off the fit
        self.assertEqual((v2.status, v2.method), (c.LabelStatus.CONTRADICTED, "UNKNOWN"))
        self.assertTrue(all(r.lineage.label_status is c.LabelStatus.CONTRADICTED for r in rows))

    def test_the_raw_rows_are_supplied_to_verification_and_never_become_adjusted_rows_or_prices_of_the_wrong_kind(self):
        built, _, rows = self.label(shift="7.50")
        self.assertTrue(all(isinstance(r, c.AdjustedQuote) for r in rows))
        aggregate = sum(s.reference_count for s in built.summaries)
        self.assertEqual(aggregate, 5)  # the raw file's 5 rows, kept apart from the observation count
        raw_summary = next(s for s in built.summaries if s.reference_count)
        self.assertEqual(raw_summary.observation_count, 5)  # observations are the 5 quotes only

    def test_the_real_eastmoney_profile_declares_delivered_dp_so_example_3c_reproduces_from_it(self):
        # 1.5 A.3 / A.4 item 7: delivered_dp 2 for open/high/low/close (the maximum observed). The V2 tests above use the real
        # profile and give the same results as before (the 3-C structure, adj = raw - 7.50: SUBTRACTIVE).
        real = prof.SOURCES["akshare.cn"]
        self.assertEqual({n: real.fields[n].delivered_dp for n in ("open", "high", "low", "close")},
                         {"open": 2, "high": 2, "low": 2, "close": 2})
        self.assertEqual(real.adjusted_dp, 2)
        self.assertEqual(prof.SOURCES["akshare_sina.us"].fields["open"].delivered_dp, 4)

    def test_without_a_declared_delivered_dp_v2_stops_with_profile_incomplete(self):
        # C2-10 (market-data/1.4 V2 (a'), section 9C item 4), kept under 1.5 for a profile that declares none: half an ulp
        # of binary64 is no longer a bound, so V2 does not run. Method UNKNOWN, label UNVERIFIABLE, cause PROFILE_INCOMPLETE,
        # whatever the data (even a series that breaks the fit).
        for kwargs in (dict(shift="7.50"), dict(shift="7.50", break_row="2025-01-06")):
            with mock.patch.dict(prof.SOURCES, {"akshare.cn": eastmoney_profile_without_ohl_decimals()}):
                _, v2, rows = self.label(**kwargs)
            self.assertEqual((v2.status, v2.method), (c.LabelStatus.UNVERIFIABLE, "UNKNOWN"), kwargs)
            self.assertIn("PROFILE_INCOMPLETE", v2.reason)
            self.assertTrue(all((r.label.method, r.lineage.label_status) == (c.AdjustmentMethod.UNKNOWN, c.LabelStatus.UNVERIFIABLE)
                                for r in rows), kwargs)

    def test_an_adjusted_series_with_no_raw_reference_is_unverifiable_with_the_reason(self):
        adj = ak_spec(akshare_csv(CLOSES, shift="7.50"), "qfq", c.AdjustmentStatus.UNDECLARED)
        built, _ = self.world([adj])
        (v2,) = [r for r in built.label_results if r.test == "V2"]
        self.assertEqual((v2.status, v2.method), (c.LabelStatus.UNVERIFIABLE, "UNKNOWN"))
        self.assertIn("no RAW reference", v2.reason)


class ProvenanceAtIngestTests(WorldCase):
    def provenance(self, built, base_ccy="USD"):
        series = built.store.fx_series(k.EUR, k.CurrencyCode(base_ccy), D(2025, 1, 1), D(2025, 1, 31))
        return {(r.observation.value_date, r.source_id): r.observation.lineage.provenance for r in series.readings}

    def frank_rows(self, **overrides):
        rows = {"2025-01-02": {"USD": "1.0800"}, "2025-01-03": {"USD": "1.0810"}, "2025-01-06": {"USD": "1.0820"}}
        rows.update(overrides)
        return rows

    def test_a_reserver_alone_is_unconfirmed(self):
        built, _ = self.world([frank_spec(self.frank_rows())])
        self.assertEqual(set(self.provenance(built).values()), {"UNCONFIRMED"})

    # market-data/1.3 Ruling 1.1a item 5: the date-set part runs over the COVERAGES the manifests fix. The ECB
    # calendar (fixing days 2, 3, 6, 7, 8, 9, 10 January 2025; retrieval 2025-01-10 09:00 UTC, so D_ret is the 9th:
    # 16:00 Berlin on the 9th is 15:00 UTC on the 9th, before the retrieval; on the 10th it is 15:00 UTC, after it)
    # and `read_end` (the ECB file was read through 8 January) give the windows below.
    ECB_READ = (("read_end", "2025-01-08"),)

    def world_with(self, frank, **kw):
        return self.world([frank, ecb_spec(request=self.ECB_READ), ecb_cal()], **kw)

    def test_equal_values_and_the_same_dates_with_the_ecb_file_confirm_the_overlap(self):
        # frank: requested 2..6 Jan, holds 2, 3, 6. ECB file: window (first held for USD = 2 Jan, min(read_end 8, D_ret 9) = 8).
        # overlap [2, 6]: frank {2, 3, 6}; ECB fixings in [2, 6] {2, 3, 6} (4 and 5 January are a weekend): equal.
        built, _ = self.world_with(frank_spec(self.frank_rows(), start="2025-01-02", end="2025-01-06"))
        prov = self.provenance(built)
        for day in (D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)):
            self.assertEqual(prov[(day, "frankfurter.ecb")], "CONFIRMED")
        self.assertIsNone(prov[(D(2025, 1, 7), "ecb.eurofxref")])  # the publisher's own file carries no provenance flag

    def test_dates_beyond_the_ecb_files_window_stay_unconfirmed_while_the_overlap_is_confirmed(self):
        # frank requested 2..9 Jan: window (2, min(9, D_ret 9) = 9). The ECB file's window ends on its read_end, the 8th.
        # overlap [2, 8]: both {2, 3, 6, 7, 8}. The re-server's 9th lies beyond the overlap: unconfirmed, not refuted.
        rows = self.frank_rows(**{"2025-01-07": {"USD": "1.0830"}, "2025-01-08": {"USD": "1.0823"},
                                  "2025-01-09": {"USD": "1.0900"}})
        built, _ = self.world_with(frank_spec(rows, start="2025-01-02", end="2025-01-09"))
        prov = self.provenance(built)
        self.assertEqual((prov[(D(2025, 1, 6), "frankfurter.ecb")], prov[(D(2025, 1, 9), "frankfurter.ecb")]),
                         ("CONFIRMED", "UNCONFIRMED"))

    def test_a_value_difference_refutes_the_whole_reserver_file(self):
        rows = self.frank_rows(**{"2025-01-03": {"USD": "1.0811"}})
        built, _ = self.world_with(frank_spec(rows, start="2025-01-02", end="2025-01-06"))
        self.assertEqual({v for (d, s), v in self.provenance(built).items() if s == "frankfurter.ecb"}, {"REFUTED"})
        (res,) = [r for r in built.label_results if r.test == "PROVENANCE"]
        self.assertIn("2025-01-03/USD", res.reason)  # the differing (date, currency) list is kept (item 6)

    def test_a_missing_date_inside_the_overlap_refutes_it(self):
        rows = {"2025-01-02": {"USD": "1.0800"}, "2025-01-06": {"USD": "1.0820"}}  # no 3 January
        built, _ = self.world_with(frank_spec(rows, start="2025-01-02", end="2025-01-06"))
        self.assertEqual({v for (d, s), v in self.provenance(built).items() if s == "frankfurter.ecb"}, {"REFUTED"})

    def test_the_quants_worked_example_a_missing_edge_date_is_seen_through_the_requested_window(self):
        # Ruling 1.1a item 5, worked example: a Frankfurter file requested for 2025-01-01..2025-01-08 lacks the 8th
        # while the ECB file has it. Coverage [2025-01-01, 8] (1 January, a TARGET closing day, is no gap): the missing
        # 8th is a difference. Under the held-dates reading (coverage 2..7) the gap would be invisible and the file
        # CONFIRMED.
        rows = {"2025-01-02": {"USD": "1.0800"}, "2025-01-03": {"USD": "1.0810"}, "2025-01-06": {"USD": "1.0820"},
                "2025-01-07": {"USD": "1.0830"}}
        built, _ = self.world_with(frank_spec(rows, start="2025-01-01", end="2025-01-08"))
        self.assertEqual({v for (d, s), v in self.provenance(built).items() if s == "frankfurter.ecb"}, {"REFUTED"})
        # control: the same file holding the 8th (the ECB's own fixing of Example 1-A) is confirmed
        rows["2025-01-08"] = {"USD": "1.0823"}
        built, _ = self.world_with(frank_spec(rows, start="2025-01-01", end="2025-01-08"))
        self.assertEqual({v for (d, s), v in self.provenance(built).items() if s == "frankfurter.ecb"}, {"CONFIRMED"})

    def test_no_ecb_calendar_means_the_date_set_part_cannot_run_and_nothing_is_confirmed(self):
        # without the fixing calendar D_ret cannot be determined: coverage UNVERIFIABLE, so no CONFIRMED and no invented
        # REFUTED; the value part still ran and found no difference
        built, _ = self.world([frank_spec(self.frank_rows(), start="2025-01-02", end="2025-01-06"),
                               ecb_spec(request=self.ECB_READ)])
        self.assertEqual({v for (d, s), v in self.provenance(built).items() if s == "frankfurter.ecb"}, {"UNCONFIRMED"})

    def test_a_refuted_file_stays_in_the_version_supplies_no_rate_and_the_ecb_value_stands_or_is_in_conflict(self):
        # Ruling 1.1a item 6: refuted by the 3 January value (1.0811 against 1.0810). It stays in M (its file is
        # consumed), supplies no rate, the ECB value is a DISAGREEMENT where they differ (3 Jan) and the ECB value is
        # used as SINGLE_SOURCE where they agree (2 Jan).
        rows = self.frank_rows(**{"2025-01-03": {"USD": "1.0811"}})
        built, _ = self.world_with(frank_spec(rows, start="2025-01-02", end="2025-01-06"))
        conv = market11_conventions(built.calendars)
        agree = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 2), conv)
        self.assertEqual((agree.outcome, agree.rate), (LookupOutcome.FOUND, Fraction(1080, 1000)))
        self.assertEqual((agree.legs[0].source_id, agree.reconciliation.status), ("ecb.eurofxref", c.ReconciliationStatus.SINGLE_SOURCE))
        differ = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 3), conv)
        self.assertEqual((differ.outcome, differ.rate), (LookupOutcome.NO_SELECTION, None))
        self.assertIs(differ.reconciliation.status, c.ReconciliationStatus.DISAGREEMENT)
        self.assertEqual(fx_input_state(differ).reason, R.SOURCE_CONFLICT)
        self.assertEqual(len(built.store.fx_series(k.EUR, k.USD, D(2025, 1, 1), D(2025, 1, 31)).readings), 8)  # M is whole


class ConsumerEndToEndTests(WorldCase):
    """The analytics consumer over the real path: a US price from Alpha Vantage, FX from the ECB's own file
    crossed through EUR, and CN / HK holdings with NO admitted source."""

    AS_OF = D(2025, 1, 8)

    def run_once(self):
        built, ident = self.world([av_spec(), ecb_spec(), nyse_cal(), ecb_cal()])
        state = kit.replayed_state(ident, self.AS_OF)
        inputs = assemble_valuation_inputs(built.store, ident, state, self.AS_OF, k.USD, market11_conventions(built.calendars))
        return built, ident, inputs

    def test_the_us_holding_is_available_and_the_cn_and_hk_holdings_are_missing_price_history_with_the_cause(self):
        _, ident, inputs = self.run_once()
        by_listing = {q.listing_id: q for q in inputs.quotes}
        aapl = by_listing[self.listing(ident, "AAPL", "XNAS")]
        st = price_input_state(aapl.lookup)
        self.assertEqual((aapl.lookup.outcome, aapl.lookup.selected.observation.price, st.state, st.reason),
                         (LookupOutcome.FOUND, Decimal("102"), S.AVAILABLE, None))
        for ticker, mic, market in (("0700", "XHKG", "HK"), ("600519", "XSHG", "CN")):
            lk = by_listing[self.listing(ident, ticker, mic)].lookup
            st = price_input_state(lk)
            # section 9B #3: NO_ADMITTED_SOURCE is a cause of NO_HISTORY (1.2 reported NOT_IN_RELEASE)
            self.assertEqual((lk.outcome, lk.selected, st.state, st.reason),
                             (LookupOutcome.NO_HISTORY, None, S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY), ticker)
            self.assertIn(f"NO_ADMITTED_SOURCE: market {market}", lk.lineage_notes[0])
            self.assertIs(lk.freshness.state, c.FreshnessState.UNKNOWN)

    def test_hkd_and_cny_translate_through_exact_same_date_crosses_with_the_quants_example_1a_fixing(self):
        _, _, inputs = self.run_once()
        fx = {f.currency.code: f.lookup for f in inputs.fx}
        self.assertEqual(sorted(fx), ["CNY", "HKD"])  # USD is the reporting currency
        self.assertEqual(fx["HKD"].rate, Fraction(10823, 84512))  # x_USD / x_HKD = 1.0823 / 8.4512
        self.assertEqual(fx["CNY"].rate, Fraction(10823, 78243))
        for lk in fx.values():
            st = fx_input_state(lk)
            self.assertEqual((lk.outcome, lk.date_used, lk.missed_count, st.state, st.reason),
                             (LookupOutcome.FOUND, self.AS_OF, 0, S.AVAILABLE, None))
            self.assertEqual(lk.cross.fixing_date, self.AS_OF)
            self.assertEqual(lk.leg_reconciliations[0].status, c.ReconciliationStatus.SINGLE_SOURCE)
        self.assertEqual(fx["HKD"].checks, (("HKD_PEG_BAND", "PASS"),))
        self.assertEqual(fx["CNY"].checks, (("CNY_PARITY_BAND", "UNVERIFIABLE"),))  # no central-parity series: never fabricated

    def test_the_result_is_conformant_marks_synthetic_data_and_lists_what_is_open(self):
        _, _, inputs = self.run_once()
        self.assertTrue(inputs.conformant)
        self.assertTrue(inputs.synthetic)  # Ruling 4.8: this version holds synthetic files
        self.assertTrue(any("TO_OBSERVE" in i for i in inputs.open_items))
        self.assertTrue(any(i.startswith("not built:") for i in inputs.open_items))
        self.assertIn("open_items", inputs.lineage_obj())
        self.assertNotIn("open_items", inputs.value_obj())  # facts only
        res = inputs.resolution_obj()
        self.assertEqual({q["notes"] != [] for q in res["quotes"]}, {True, False})

    def test_the_consumed_files_name_exactly_the_files_that_were_consulted(self):
        built, ident, inputs = self.run_once()
        hashes = {r.file_sha256 for ref in inputs.data_set_refs for r in ref.consumed}
        calendar_hashes = {cal.lineage.file_sha256 for cal in built.calendars.calendars()}
        # on the as-of date itself the prints and the fixing are dated D. C2-1 (CP2 review): the interval is empty but
        # a print dated D is CURRENT only under a governing calendar that covers D, so the calendars ARE consulted and
        # cited (the one governing the listing's MIC and the ECB's), beside the AV file and the ECB file (it used to be
        # 2 files and no calendar)
        self.assertEqual((len(hashes), len(hashes & calendar_hashes), len(hashes - calendar_hashes)), (4, 2, 2))
        # one day later the interval (D, D+1] must be counted, and the exact calendar files are cited
        conv = market11_conventions(built.calendars)
        later = D(2025, 1, 9)
        q = built.store.quote_on(self.listing(ident, "AAPL", "XNAS"), later, conv)
        f = built.store.fx_on(k.HKD, k.USD, later, conv)
        cited = {r.file_sha256 for r in q.consumed} | {r.file_sha256 for r in f.consumed}
        self.assertTrue(calendar_hashes <= cited)

    def test_the_whole_result_is_deterministic_across_independent_builds(self):
        first = self.run_once()[2]
        second = self.run_once()[2]
        for part in ("value_obj", "lineage_obj", "resolution_obj"):
            self.assertEqual(canonical_json(getattr(first, part)()), canonical_json(getattr(second, part)()), part)


if __name__ == "__main__":
    unittest.main()
