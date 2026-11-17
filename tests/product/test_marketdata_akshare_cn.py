"""`akshare.cn.quotes` adapter under market-data/1.1. The fixtures are SYNTHETIC: invented numbers
in the exact column structure of the first real file. No real vendor file is read or committed."""

import dataclasses
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_kit  # noqa: E402
import marketdata_testkit as kit  # noqa: E402

from domain.instrument import SecurityType  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata.adapters.akshare_cn import COLUMNS, PAYLOAD_FORMAT, SOURCE_ID, AkshareCnQuoteAdapter  # noqa: E402
from marketdata.adapters.base import AdapterRegistry, IssueCode  # noqa: E402
from marketdata.conventions import placeholder_conventions  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, MarketDataRelease, SourceRecord  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.profiles import PROFILE_SET_VERSION  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402

HEADER = "日期,股票代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率\n"
DAYS = ("2025-01-02", "2025-01-03", "2025-01-06")


def csv_text(closes, lots=(1000, 2000, 0), symbol="600001", amount_factor=100, change=None, low_offset="0.5",
             derived="1.0,1.0,0.1"):
    """Rows with a consistent shape: open = close, high = close + 0.5, low = close - offset,
    amount = close x lots x 100 (shares), change = close_t - close_(t-1)."""
    rows = []
    prev = None
    for i, (day, close, lot) in enumerate(zip(DAYS, closes, lots)):
        c_ = Decimal(close)
        high, low = c_ + Decimal("0.5"), c_ - Decimal(low_offset)
        amount = c_ * Decimal(str(lot)) * amount_factor
        delta = "0.0" if prev is None else str(c_ - prev)
        if change is not None:
            delta = change[i]
        rows.append(f"{day},{symbol},{close},{close},{high},{low},{lot},{amount},{derived.split(',')[0]},"
                    f"{derived.split(',')[1]},{delta},{derived.split(',')[2]}\n")
        prev = c_
    return HEADER + "".join(rows)


RAW = csv_text(("10.5", "10.25", "10.3"))
QFQ = csv_text(("9.5", "9.25", "9.3"))


def manifest(adjustment=c.AdjustmentStatus.RAW, anchor=None, request=(("function", "stock_zh_a_hist"),),
             libraries=(("akshare", "1.19.1"),)):
    return kit.FileManifest(
        file_sha256="d" * 64, size_bytes=1, payload_filename="x.csv", payload_format=PAYLOAD_FORMAT,
        source_id=SOURCE_ID, data_kind=DataKind.QUOTE, retrieval_time=kit.RETRIEVED, retrieved_by="synthetic",
        declared_adjustment=adjustment, usage_scope=c.UsageScope.SYNTHETIC_TEST, declared_currency=kit.CNY,
        declared_delay=c.DataDelayStatus.END_OF_DAY, adjustment_anchor=anchor, market="CN",
        request=request, libraries=libraries, source_identifiers=("600001",))


def translate(text, **kw):
    return AkshareCnQuoteAdapter().translate(manifest(**kw), text.encode("utf-8"))


class RawTranslationTests(unittest.TestCase):
    def test_rows_become_unresolved_quotes_by_vendor_id_with_full_1_1_lineage(self):
        out = translate(RAW)
        self.assertEqual((out.issues, out.adjusted), ((), ()))
        self.assertEqual(len(out.quotes), 3)
        q = out.quotes[0]
        self.assertEqual((q.identifiers.vendor_id, q.identifiers.source_id, q.identifiers.mic), ("600001", SOURCE_ID, None))
        self.assertEqual((q.value_date.isoformat(), q.price, q.currency), ("2025-01-02", Decimal("10.5"), kit.CNY))
        self.assertTrue(q.recovered and q.precision_bound == 0)
        lin = q.lineage
        self.assertTrue(lin.is_complete)
        self.assertEqual(lin.source_value_text, "10.5")
        self.assertEqual(lin.precision_profile_id, f"{PROFILE_SET_VERSION}:akshare.cn:close")
        self.assertEqual((lin.market, lin.library, lin.library_version, lin.library_function),
                         ("CN", "akshare", "1.19.1", "stock_zh_a_hist"))
        self.assertIs(lin.consistency_checks_passed, True)  # the 涨跌额 check ran and passed
        self.assertEqual(lin.volume_unit_status, "VERIFIED")  # 成交额 / (close x volume) is about 100
        self.assertIs(q.price_kind, c.PriceKind.SOURCE_CLOSE)

    def test_volume_is_lots_converted_to_shares_and_a_zero_volume_row_is_no_print(self):
        out = translate(RAW)
        self.assertEqual([q.volume for q in out.quotes], [Decimal(100000), Decimal(200000), Decimal(0)])
        self.assertEqual([q.volume > 0 for q in out.quotes], [True, True, False])

    def test_vendor_computed_columns_are_never_read(self):
        out = translate(csv_text(("10.5", "10.25", "10.3"), derived="abc,not-a-number,###"))
        self.assertEqual((len(out.quotes), out.issues), (3, ()))  # 振幅, 涨跌幅, 换手率 are garbage and ignored

    def test_nothing_is_rounded_a_grid_violation_is_kept_but_not_recovered(self):
        # RE-RECORDED for market-data/1.16 item 26: the recorded Eastmoney profile (delivered_dp 2) now refuses a 3-decimal text at the PROFILE
        # check (see the next test for that); this test is about the grid step after it, so it runs against a hypothetical wider profile
        with gate_kit.delivered_dp("akshare.cn", 8):
            out = translate(csv_text(("10.5", "10.255", "10.3")))  # 3 decimals, A-share maximum is 2
        q = out.quotes[1]
        self.assertEqual(q.price, Decimal("10.255"))  # not rounded to 10.26 or 10.25
        self.assertFalse(q.recovered)
        self.assertGreater(q.precision_bound, 0)  # half an ulp of float64: tiny but positive
        self.assertEqual([i.code for i in out.issues], [IssueCode.PRICE_NOT_RECOVERED])
        self.assertEqual(q.lineage.source_value_text, "10.255")

    def test_a_float32_signature_in_a_float64_field_fails_the_profile_and_the_file_is_not_admitted(self):
        # RE-RECORDED for market-data/1.16 item 26: 474.20001 shows 5 decimals against the recorded delivered_dp 2, so the profile check now
        # fails it first, on the decimals (also not admitted). The float32-signature step is reached only under a wider hypothetical profile.
        out = translate(csv_text(("474.20001", "10.25", "10.3")))
        self.assertEqual(out.quotes, ())
        self.assertEqual(out.issues[0].code, IssueCode.PROFILE_CHECK_FAILED)
        self.assertIn("shows 5 decimals but the profile delivers 2", out.issues[0].detail)
        with gate_kit.delivered_dp("akshare.cn", 8):
            out = translate(csv_text(("474.20001", "10.25", "10.3")))
        self.assertEqual((out.quotes, out.issues[0].code), ((), IssueCode.PROFILE_CHECK_FAILED))
        self.assertIn("float32 signature", out.issues[0].detail)

    def test_a_row_that_breaks_the_ohlc_ordering_is_not_admitted(self):
        out = translate(csv_text(("10.5", "10.25", "10.3"), low_offset="-0.2"))  # low above close
        self.assertEqual(out.quotes, ())
        self.assertEqual({i.code for i in out.issues}, {IssueCode.ROW_INCONSISTENT})

    def test_a_failing_change_check_is_flagged_on_every_row_and_rows_are_kept(self):
        out = translate(csv_text(("10.5", "10.25", "10.3"), change=("0.0", "-0.99", "0.05")))
        self.assertEqual(len(out.quotes), 3)
        self.assertTrue(all(q.lineage.consistency_checks_passed is False for q in out.quotes))
        self.assertIn(IssueCode.CONSISTENCY_CHECK_FAILED, [i.code for i in out.issues])

    def test_a_wrong_volume_unit_fails_the_ruling_2_6_check_and_the_file_is_not_admitted(self):
        out = translate(csv_text(("10.5", "10.25", "10.3"), amount_factor=1))  # turnover 100x too small
        self.assertEqual(out.quotes, ())
        self.assertEqual(out.issues[0].code, IssueCode.VOLUME_UNIT_CHECK_FAILED)

    def test_a_non_integral_volume_fails_the_profile_check_in_lots_too(self):
        out = translate(csv_text(("10.5", "10.25", "10.3"), lots=("1000.5", 2000, 0)))
        self.assertEqual(out.quotes, ())

    def test_bad_rows_wrong_structure_header_only_and_missing_currency(self):
        out = translate(HEADER + "2025-01-0x,600001,1,10.5,11,10,5,525,1,1,0,1\n2025-01-03,,1,10.5,11,10,5,525,1,1,0,1\n")
        self.assertEqual((out.quotes, [i.code for i in out.issues]), ((), [IssueCode.UNPARSEABLE_ROW] * 2))
        self.assertEqual(translate("a,b\n1,2\n").issues[0].code, IssueCode.UNKNOWN_FORMAT)
        empty = translate(HEADER)
        self.assertEqual((empty.quotes, empty.issues), ((), ()))
        no_ccy = AkshareCnQuoteAdapter().translate(dataclasses.replace(manifest(), declared_currency=None), RAW.encode())
        self.assertEqual(no_ccy.issues[0].code, IssueCode.UNDECLARED_CURRENCY)

    def test_translation_is_deterministic_and_a_byte_order_mark_is_tolerated(self):
        a = AkshareCnQuoteAdapter()
        self.assertEqual(a.translate(manifest(), b"\xef\xbb\xbf" + RAW.encode()), a.translate(manifest(), RAW.encode()))

    def test_the_columns_used_are_exactly_the_documented_ones(self):
        used = {COLUMNS.date, COLUMNS.open, COLUMNS.high, COLUMNS.low, COLUMNS.close, COLUMNS.volume,
                COLUMNS.turnover, COLUMNS.change, COLUMNS.symbol}
        self.assertFalse(used & {"振幅", "涨跌幅", "换手率"})


class AdjustedTranslationTests(unittest.TestCase):
    def test_an_adjusted_file_yields_verification_only_rows_with_method_unknown(self):
        out = translate(QFQ, adjustment=c.AdjustmentStatus.UNDECLARED, anchor="akshare.stock_zh_a_hist adjust=qfq")
        self.assertEqual((out.quotes, out.issues), ((), ()))
        self.assertEqual(len(out.adjusted), 3)
        a = out.adjusted[0]
        self.assertNotIsInstance(a, c.UnresolvedQuote)
        self.assertEqual((a.open, a.high, a.low, a.close), (Decimal("9.5"), Decimal("10.0"), Decimal("9.0"), Decimal("9.5")))
        self.assertIs(a.label.method, c.AdjustmentMethod.UNKNOWN)  # set only by Test V2, never declared
        self.assertIsNone(a.label.anchor)
        self.assertEqual(a.label.vintage, kit.RETRIEVED)
        self.assertIs(a.label.adjustment_status, c.AdjustmentStatus.UNDECLARED)
        self.assertGreater(a.precision_bound, 0)
        self.assertIsNone(a.lineage.label_status)  # not yet tested

    def test_adjusted_values_are_never_rounded_or_grid_validated(self):
        # RE-RECORDED for market-data/1.16 item 26: the recorded Eastmoney profile (delivered_dp 2) would refuse these texts at the profile check
        # (A.3 gives Eastmoney's qfq values a delivered_dp too); this test is about the adjusted path never rounding, so it runs against a wider profile
        with gate_kit.delivered_dp("akshare.cn", 8):
            out = translate(csv_text(("9.49999999", "9.2512345", "9.3")), adjustment=c.AdjustmentStatus.UNDECLARED, anchor="x")
        self.assertEqual([a.close for a in out.adjusted], [Decimal("9.49999999"), Decimal("9.2512345"), Decimal("9.3")])
        self.assertEqual(out.issues, ())


class EndToEndTests(unittest.TestCase):
    def build(self, with_adjusted=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=[SourceRecord(SOURCE_ID, "AKShare CN (synthetic copy)", "synthetic",
                                                     "eastmoney", synthetic=True)])
        ms = [kit.write_file(root, SOURCE_ID, DataKind.QUOTE, PAYLOAD_FORMAT, RAW.encode("utf-8"), "raw", "csv",
                             currency=kit.CNY, source_identifiers=("600001",))]
        if with_adjusted:
            ms.append(kit.write_file(root, SOURCE_ID, DataKind.QUOTE, PAYLOAD_FORMAT, QFQ.encode("utf-8"), "qfq",
                                     "csv", currency=kit.CNY, source_identifiers=("600001",),
                                     adjustment=c.AdjustmentStatus.UNDECLARED,
                                     anchor="akshare.stock_zh_a_hist adjust=qfq"))
        identity = InMemoryIdentityRegistry(kit.SequentialIds())
        (reg,) = identity.register_instruments([InstrumentEntry(
            "Synthetic Co", SecurityType.COMMON_STOCK, "XSHG", "SSE", "600001", kit.CNY,
            vendor_ids=((SOURCE_ID, "600001"),))])
        files = FileStore(root)
        release = MarketDataRelease.from_manifests("ak", ms, [SOURCE_ID])
        built = build_in_memory_market_data(release, files, files.load_registry(),
                                            AdapterRegistry([AkshareCnQuoteAdapter()]), identity, catalog_calendars={})
        return built, reg.listing_id

    def test_adjusted_rows_are_reachable_only_through_the_verification_port_and_never_as_a_price(self):
        built, lid = self.build()
        self.assertEqual((built.issues, built.exceptions), ((), ()))
        series = built.store.quotes(lid, kit.DAY1, kit.datetime.date(2025, 1, 6))
        self.assertEqual(len(series.readings), 3)  # RAW only
        self.assertTrue(all(r.observation.lineage.adjustment_status is c.AdjustmentStatus.RAW for r in series.readings))
        adjusted = built.store.adjusted_series(lid)
        self.assertEqual(len(adjusted), 3)
        self.assertTrue(all(isinstance(a, c.AdjustedQuote) for a in adjusted))
        lk = built.store.quote_on(lid, kit.DAY1, placeholder_conventions())
        self.assertEqual((lk.outcome, lk.selected.observation.price), (LookupOutcome.FOUND, Decimal("10.5")))
        self.assertEqual(lk.selected.observation.lineage.independence_group, "eastmoney")  # the upstream

    def test_an_unregistered_symbol_is_quarantined_not_guessed(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=[SourceRecord(SOURCE_ID, "x", "synthetic", "g", synthetic=True)])
        m = kit.write_file(root, SOURCE_ID, DataKind.QUOTE, PAYLOAD_FORMAT, RAW.encode("utf-8"), "raw", "csv",
                           currency=kit.CNY, source_identifiers=("600001",))
        files = FileStore(root)
        built = build_in_memory_market_data(
            MarketDataRelease.from_manifests("r", [m], [SOURCE_ID]), files, files.load_registry(),
            AdapterRegistry([AkshareCnQuoteAdapter()]), InMemoryIdentityRegistry(kit.SequentialIds()), catalog_calendars={})
        ((_, exc),) = built.exceptions
        self.assertEqual(exc.row_count, 3)
        self.assertEqual(built.summaries[0].observation_count, 0)


if __name__ == "__main__":
    unittest.main()
