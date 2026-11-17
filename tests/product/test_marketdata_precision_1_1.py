"""market-data/1.1: number normalization and precision profiles (Ruling 2.4), the volume-unit check
(2.6), the Sina adapters, Test V2 (3.1), reconciliation (4.1-4.4, 4.6), the input states (4.4) and
the profile admission gate. Every fixture is SYNTHETIC; the Quant's worked values that are quoted
(474.20001 -> 474.2, 469.39999 -> 469.4) are from the convention document, not from any file."""

import ast
import dataclasses
import datetime
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_kit  # noqa: E402
import marketdata_testkit as kit  # noqa: E402

from domain.instrument import SecurityType  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata import precision as p  # noqa: E402
from marketdata import profiles as prof  # noqa: E402
from marketdata.adapters.akshare_sina import AkshareSinaQuoteAdapter  # noqa: E402
from marketdata.adapters.base import AdapterRegistry, IssueCode  # noqa: E402
from marketdata.conventions import ConventionSet, PlaceholderFreshnessPolicy, placeholder_conventions  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, MarketDataRelease, SourceRecord, TermsCheck  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.reconciliation import Market11Reconciler  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402
from marketdata.states import fx_input_state, price_input_state  # noqa: E402
from marketdata.store import InMemoryMarketData  # noqa: E402
from marketdata.verification import CorporateEvent, PriceRow, apply_v2, verify_adjustment_v2  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
F32, F64, TXT = prof.NumberFormat.FLOAT32, prof.NumberFormat.FLOAT64, prof.NumberFormat.TEXT_DECIMAL


class NormalizationTests(unittest.TestCase):
    def test_float32_renderings_normalize_to_the_shortest_round_trip_decimal(self):
        for text, want in (("474.20001", "474.2"), ("469.39999", "469.4"), ("300.20001", "300.2"),
                           ("99.400002", "99.4"), ("212.60001", "212.6")):
            self.assertEqual(p.shortest_float32(text), Decimal(want), text)
            self.assertEqual(p.normalize(text, F32), Decimal(want))

    def test_text_and_float64_are_the_identity_and_nothing_is_rounded(self):
        for fmt in (F64, TXT):
            self.assertEqual(str(p.normalize("12.340", fmt)), "12.340")
            self.assertEqual(p.normalize("1288.0", fmt), Decimal("1288.0"))
        with self.assertRaises(p.NumberError):
            p.normalize("NaN", F64)
        with self.assertRaises(p.NumberError):
            p.normalize("abc", F32)

    def test_the_float32_signature_is_text_equal_to_its_8_digit_rendering_and_longer_than_the_shortest(self):
        for text in ("474.20001", "469.39999", "99.400002"):
            self.assertTrue(p.has_float32_signature(text), text)
        for text in ("233.85", "473.6", "231.8201", "1288.0", "150000004.0", "10.5", "1.1"):
            self.assertFalse(p.has_float32_signature(text), text)

    def test_a_float32_field_must_hold_the_float32_rendering_of_its_own_value(self):
        for text in ("474.20001", "473.6", "300.0", "99.400002"):
            self.assertTrue(p.is_float32_rendering(text), text)
        self.assertFalse(p.is_float32_rendering("414.2000001"))

    def test_the_profile_check_fails_closed_both_ways(self):
        f64 = prof.FieldProfile(F64, prof.OBSERVED)
        f32 = prof.FieldProfile(F32, prof.OBSERVED)
        self.assertIsNone(p.check_field_format(["233.85", "10.5"], f64))
        self.assertIn("float32 signature", p.check_field_format(["233.85", "474.20001"], f64))
        self.assertIsNone(p.check_field_format(["474.20001", "300.2"], f32))
        self.assertIn("not the float32 rendering", p.check_field_format(["414.2000001"], f32))
        self.assertIn("not an integer", p.check_field_format(["10.5"], prof.FieldProfile(F64, prof.OBSERVED, True)))

    def test_integer_volumes_are_tested_by_float32_spacing_not_by_the_8_digit_signature(self):
        vol64 = prof.FieldProfile(F64, prof.OBSERVED, True, 1, "SHARE")
        vol32 = prof.FieldProfile(F32, prof.DECLARED, True, 1, "SHARE")
        # 41000008.0 is 8 digits and a multiple of 4 on [2^25, 2^26): the signature rule would misfire
        self.assertTrue(p.has_float32_signature("41000008.0"))  # the misfire that motivated the exception
        self.assertIsNone(p.check_field_format(["41000008.0", "45000001.0", "150000004.0"], vol64))
        self.assertIsNone(p.check_field_format(["1000", "16777216"], vol32))  # < 2^24 or a multiple of its spacing
        self.assertIn("not a possible float32", p.check_field_format(["45000001.0"], vol32))  # odd in [2^25, 2^26)
        self.assertIn("not an integer", p.check_field_format(["10.5"], vol64))

    def test_float32_ulp_and_the_recoverability_thresholds_of_appendix_a2(self):
        self.assertEqual(p.float32_ulp(Decimal("474.2")), Fraction(1, 2 ** 15))
        self.assertEqual(p.float32_ulp(Decimal("100000")), Fraction(1, 2 ** 7))  # on [65536, 131072)
        self.assertLess(p.float32_ulp(Decimal("131071")), Fraction(1, 100))
        self.assertGreaterEqual(p.float32_ulp(Decimal("131072")), Fraction(1, 100))  # 2^-6 = 0.015625

    def test_close_validation_recovers_or_marks_not_recovered_and_never_rounds(self):
        f32c = prof.FieldProfile(F32, prof.OBSERVED)
        f64c = prof.FieldProfile(F64, prof.OBSERVED)
        hk = p.resolve_close("474.20001", f32c, "HK")
        self.assertEqual((hk.value, hk.recovered, hk.bound), (Decimal("474.2"), True, Decimal(0)))
        too_high = p.resolve_close("200000.5", f32c, "US")  # ulp 2^-6 >= 0.01: the grid is not resolvable
        self.assertEqual((too_high.value, too_high.recovered), (Decimal("200000.5"), False))
        self.assertEqual(too_high.bound, Decimal("0.0078125"))  # half an ulp, exactly
        us = p.resolve_close("187.44", f64c, "US")
        self.assertTrue(us.recovered)
        off = p.resolve_close("187.435", f64c, "US")  # 3 decimals: above the US 2-decimal bound for >= 1.00
        self.assertEqual((off.value, off.recovered), (Decimal("187.435"), False))
        self.assertGreater(off.bound, 0)
        self.assertTrue(p.resolve_close("0.5001", f64c, "US").recovered)  # below 1.00 allows 4 decimals
        with self.assertRaises(p.NumberError):
            p.resolve_close("-1", f64c, "US")

    def test_market_bounds_are_the_memory_status_data_of_appendix_a1(self):
        self.assertEqual((prof.max_dp("US", Decimal("1.00")), prof.max_dp("US", Decimal("0.99"))), (2, 4))
        self.assertEqual(prof.max_dp("HK", Decimal("474.2")), 3)
        self.assertEqual((prof.max_dp("CN", Decimal("10")), prof.max_dp("CN", Decimal("10"), "FUND_ETF_LOF_BOND")), (2, 3))
        self.assertEqual(prof.MARKETS["HK"].tick_table_use, "FLAG_ONLY")  # no tick table is implemented
        with self.assertRaises(prof.ProfileNotAdmittedError):
            prof.max_dp("JP", Decimal("1"))

    def test_no_decimal_is_ever_built_from_a_binary_float(self):
        tree = ast.parse((Path(p.__file__)).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Decimal" and node.args:
                arg = node.args[0]
                self.assertFalse(isinstance(arg, ast.Call) and getattr(arg.func, "id", None) == "float")
        text = Path(p.__file__).read_text(encoding="utf-8")
        self.assertNotIn("round(", text)
        self.assertNotIn("ROUND_HALF", text)  # the 1.0 fixed-decimal rounding is gone

    def test_volume_unit_check_uses_the_median_of_turnover_over_close_times_volume(self):
        rows = [(Decimal("1050000"), Decimal("10.5"), Decimal("1000")),
                (Decimal("2050000"), Decimal("10.25"), Decimal("2000")),
                (Decimal("0"), Decimal("10.3"), Decimal("0"))]  # volume 0: excluded
        ok, median = p.volume_unit_check(rows, 100)
        self.assertEqual((ok, median), (True, Fraction(100)))
        bad, _ = p.volume_unit_check(rows, 1)  # the same data against a wrong declared unit
        self.assertFalse(bad)
        self.assertEqual(p.volume_unit_check([(Decimal(0), Decimal(1), Decimal(0))], 1), (None, None))
        # one extreme row does not move a median of three
        skewed = rows[:2] + [(Decimal("1"), Decimal("10"), Decimal("1000"))]
        self.assertTrue(p.volume_unit_check(skewed, 100)[0])

    def test_row_ordering_check_of_ruling_4_6(self):
        self.assertTrue(p.row_is_consistent(Decimal(10), Decimal(12), Decimal(9), Decimal(11)))
        self.assertFalse(p.row_is_consistent(Decimal(10), Decimal(12), Decimal("10.5"), Decimal(11)))  # open below low
        self.assertFalse(p.row_is_consistent(Decimal(10), Decimal(10), Decimal(9), Decimal(11)))  # close above high


class ProfileDataTests(unittest.TestCase):
    def test_profiles_carry_the_statuses_of_appendix_a_and_a_version(self):
        # 1.5: the id carries the governing set; profiles/3 because A.3 declares delivered_dp (A.4 item 7; profiles/2 was A.1's CN table).
        # 1.15 (PD-0067 decision 6): profiles/4 because A.3 gained the `alphavantage.cn` profile (the content moved; the counter had not)
        # 1.16 (section 11 item 32): profiles/5 because the call_adjustment status is profile data and the MIC and zone tables gained ARCX, BATS, XASE
        self.assertEqual(prof.PROFILE_SET_VERSION, "market-data/1.16#profiles/5")
        hk = prof.SOURCES["akshare_sina.hk"]
        self.assertEqual((hk.fields["close"].format, hk.fields["close"].status), (F32, prof.OBSERVED))
        self.assertEqual((hk.fields["open"].format, hk.fields["open"].status), (F32, prof.DECLARED))
        self.assertEqual((hk.fields["volume"].shares_per_unit, hk.fields["volume"].unit), (1, "SHARE"))
        us = prof.SOURCES["akshare_sina.us"]
        self.assertEqual(us.fields["volume"].status, prof.DECLARED_UNVERIFIED)
        cn = prof.SOURCES["akshare.cn"]
        self.assertEqual((cn.fields["volume"].shares_per_unit, cn.fields["volume"].unit), (100, "LOT_100"))
        self.assertEqual({s.upstream for s in (hk, us, cn)}, {"sina", "eastmoney"})
        self.assertEqual(prof.SOURCES["frankfurter.ecb"].fields["rate"].format, TXT)
        self.assertEqual(hk.profile_id("close"), "market-data/1.16#profiles/5:akshare_sina.hk:close")

    def test_primary_order_by_upstream_is_data_and_lists_only_admitted_upstreams(self):
        # market-data/1.2 A.5 (PD-0031/0032): the 1.1 order (CN eastmoney, sina; HK and US sina, eastmoney,
        # alphavantage) is withdrawn with the admissions it assumed; refused upstreams are removed.
        self.assertEqual(prof.PRIMARY_ORDER["CN"], ())
        self.assertEqual(prof.PRIMARY_ORDER["HK"], ())
        self.assertEqual(prof.PRIMARY_ORDER["US"], ("alphavantage",))
        self.assertEqual(prof.PRIMARY_ORDER["FX"], ("ecb",))

    def test_a_to_observe_or_missing_profile_is_not_admitted(self):
        for source in ("akshare_sina.cn", "akshare.hk", "akshare.us"):  # REFUSED and never profiled (1.2)
            self.assertEqual(prof.SOURCES[source].status, prof.TO_OBSERVE)
            with self.assertRaises(prof.ProfileNotAdmittedError):
                prof.require_admitted(source)
        with self.assertRaises(prof.ProfileNotAdmittedError):
            prof.require_admitted("never.heard.of.it")
        # C2-12 (CP2 review of 39733e9): this test used to end with `require_admitted("akshare.cn").admitted` True. The
        # `refused` flag is now ENFORCED (PD-0031/0032: no file from a refused source is ever a reading), and a MEMORY
        # profile is not admitted for real data (A.4, MD-OI-12: profile it from its first real file first).
        for source in ("akshare.cn", "akshare_sina.hk", "akshare_sina.us"):  # OBSERVED format records, but REFUSED
            self.assertTrue(prof.SOURCES[source].refused and prof.SOURCES[source].status == prof.OBSERVED, source)
            with self.assertRaises(prof.ProfileNotAdmittedError, msg=source):
                prof.require_admitted(source)
            self.assertFalse(prof.SOURCES[source].admitted, source)
        self.assertEqual(prof.SOURCES["ecb.eurofxref"].status, prof.MEMORY)
        with self.assertRaises(prof.ProfileNotAdmittedError):
            prof.require_admitted("ecb.eurofxref")
        for source in ("alphavantage.us", "frankfurter.ecb"):  # OBSERVED and not refused
            self.assertTrue(prof.require_admitted(source).admitted, source)

    def test_ingest_refuses_a_real_source_without_an_admitted_profile_and_exempts_synthetic_ones(self):
        class Stub:
            adapter_id, adapter_version, data_kind = "stub", "1", DataKind.QUOTE
            payload_formats = ("stub/1",)

            def __init__(self, source_id):
                self.source_id = source_id

            def translate(self, manifest, payload):
                raise AssertionError("the profile gate must refuse before translating")

        for source_id in ("akshare.hk", "unknown.vendor"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                rec = SourceRecord(source_id, "x", "up", "g", terms_check=TermsCheck("owner", D(2025, 1, 5), True))
                kit.write_registry(root, extra=[rec])
                m = kit.write_file(root, source_id, DataKind.QUOTE, "stub/1", b"x", "f", "csv", currency=kit.USD,
                                   usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, retrieved_by="human")
                files = FileStore(root)
                with self.assertRaises(prof.ProfileNotAdmittedError):
                    build_in_memory_market_data(MarketDataRelease.from_manifests("r", [m], [source_id]), files,
                                                files.load_registry(), AdapterRegistry([Stub(source_id)]),
                                                kit.make_identity(), catalog_calendars={})


def manifest(source, fmt, symbols, ccy, adjustment=c.AdjustmentStatus.RAW, market="HK"):
    return kit.FileManifest(
        file_sha256="d" * 64, size_bytes=1, payload_filename="x", payload_format=fmt, source_id=source,
        data_kind=DataKind.QUOTE, retrieval_time=kit.RETRIEVED, retrieved_by="synthetic",
        declared_adjustment=adjustment, usage_scope=c.UsageScope.SYNTHETIC_TEST, declared_currency=ccy,
        source_identifiers=symbols, declared_delay=c.DataDelayStatus.END_OF_DAY, market=market)


HK_CSV = ("date,open,high,low,close,volume,amount\n"
          "2025-01-02,300.0,310.0,295.0,300.20001,1000000.0,300200000.0\n"
          "2025-01-03,213.0,215.0,210.0,212.60001,2000000.0,425200000.0\n"
          "2025-01-06,150.0,152.0,149.0,150.39999,0.0,0.0\n")
US_CSV = ("date,open,high,low,close,volume\n"
          "2025-01-02,10.0,12.0,9.0001,10.5,5000000.0\n"
          "2025-01-03,10.0,12.0,9.0,10.2501,6000000.0\n")


class SinaAdapterTests(unittest.TestCase):
    def translate(self, market, text, symbols=("SYM",), adjustment=c.AdjustmentStatus.RAW):
        a = AkshareSinaQuoteAdapter(market)
        ccy = kit.HKD if market == "hk" else kit.USD
        return a.translate(manifest(a.source_id, a.payload_formats[0], symbols, ccy, adjustment, market.upper()),
                           text.encode("utf-8"))

    def test_hk_float32_closes_are_recovered_by_the_shortest_round_trip_not_by_rounding(self):
        out = self.translate("hk", HK_CSV, ("00700",))
        self.assertEqual(out.issues, ())
        self.assertEqual([q.price for q in out.quotes], [Decimal("300.2"), Decimal("212.6"), Decimal("150.4")])
        self.assertTrue(all(q.recovered and q.precision_bound == 0 for q in out.quotes))
        lin = out.quotes[0].lineage
        self.assertEqual(lin.source_value_text, "300.20001")  # verbatim kept
        self.assertEqual(lin.precision_profile_id, "market-data/1.16#profiles/5:akshare_sina.hk:close")
        self.assertFalse(lin.precision_profile_id.startswith("placeholder/"))  # the placeholder is gone
        self.assertEqual(lin.volume_unit_status, "VERIFIED")  # amount / (close x volume) = 1
        self.assertIsNone(lin.consistency_checks_passed)  # Sina has no within-source check
        self.assertEqual((out.quotes[0].identifiers.vendor_id, out.quotes[0].identifiers.mic), ("00700", None))

    def test_hk_volume_is_shares_and_a_wrong_unit_is_refused(self):
        out = self.translate("hk", HK_CSV, ("00700",))
        self.assertEqual([q.volume for q in out.quotes], [Decimal(1000000), Decimal(2000000), Decimal(0)])
        wrong = self.translate("hk", HK_CSV.replace("300200000.0", "3002000.0").replace("425200000.0", "4252000.0"),
                               ("00700",))
        self.assertEqual((wrong.quotes, wrong.issues[0].code), ((), IssueCode.VOLUME_UNIT_CHECK_FAILED))

    def test_an_ohlc_field_that_is_not_a_float32_rendering_fails_the_profile_check(self):
        bad = self.translate("hk", HK_CSV.replace("310.0", "310.123456789"), ("00700",))
        self.assertEqual((bad.quotes, bad.issues[0].code), ((), IssueCode.PROFILE_CHECK_FAILED))

    def test_us_is_float64_a_grid_violation_is_kept_not_recovered_and_the_unit_stays_unverified(self):
        out = self.translate("us", US_CSV, ("AAPL",))
        first, second = out.quotes
        self.assertEqual((first.price, first.recovered), (Decimal("10.5"), True))
        self.assertEqual((second.price, second.recovered), (Decimal("10.2501"), False))  # 4 dp at a price >= 1.00
        self.assertEqual(first.lineage.volume_unit_status, "DECLARED_UNVERIFIED")
        self.assertEqual([i.code for i in out.issues], [IssueCode.PRICE_NOT_RECOVERED])
        bad = self.translate("us", US_CSV.replace("10.5,", "300.20001,"), ("AAPL",))  # float32 signature in FLOAT64
        self.assertEqual((bad.quotes, bad.issues[0].code), ((), IssueCode.PROFILE_CHECK_FAILED))

    def test_the_symbol_must_be_exactly_one_and_an_adjusted_file_is_verification_only(self):
        for symbols in ((), ("A", "B")):
            self.assertEqual(self.translate("us", US_CSV, symbols).issues[0].code, IssueCode.MISSING_FIELD)
        adj = self.translate("us", US_CSV, ("AAPL",), adjustment=c.AdjustmentStatus.UNDECLARED)
        self.assertEqual((adj.quotes, len(adj.adjusted)), ((), 2))
        with self.assertRaises(ValueError):
            AkshareSinaQuoteAdapter("cn")

    def test_end_to_end_a_recovered_hk_close_is_used_and_an_unrecovered_us_close_never_is(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kit.write_registry(root, extra=[SourceRecord("akshare_sina.hk", "Sina HK", "synthetic", "sina", synthetic=True),
                                            SourceRecord("akshare_sina.us", "Sina US", "synthetic", "sina", synthetic=True)])
            ms = [kit.write_file(root, "akshare_sina.hk", DataKind.QUOTE, "akshare_sina_csv_hk_daily/1",
                                 HK_CSV.encode(), "hk", "csv", currency=kit.HKD, source_identifiers=("00700",)),
                  kit.write_file(root, "akshare_sina.us", DataKind.QUOTE, "akshare_sina_csv_us_daily/1",
                                 US_CSV.encode(), "us", "csv", currency=kit.USD, source_identifiers=("AAPL",))]
            identity = InMemoryIdentityRegistry(kit.SequentialIds())
            hk, us = identity.register_instruments([
                InstrumentEntry("HK Co", SecurityType.COMMON_STOCK, "XHKG", "HKEX", "0700", kit.HKD,
                                vendor_ids=(("akshare_sina.hk", "00700"),)),
                InstrumentEntry("US Co", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", kit.USD,
                                vendor_ids=(("akshare_sina.us", "AAPL"),))])
            files = FileStore(root)
            built = build_in_memory_market_data(
                MarketDataRelease.from_manifests("r", ms, ["akshare_sina.hk", "akshare_sina.us"]), files,
                files.load_registry(), AdapterRegistry([AkshareSinaQuoteAdapter("hk"), AkshareSinaQuoteAdapter("us")]),
                identity, catalog_calendars={})
            conv = placeholder_conventions()
            ok = built.store.quote_on(hk.listing_id, D(2025, 1, 2), conv)
            self.assertEqual((ok.outcome, ok.selected.observation.price), (LookupOutcome.FOUND, Decimal("300.2")))
            self.assertEqual(ok.reconciliation.status, c.ReconciliationStatus.SINGLE_SOURCE)
            imprecise = built.store.quote_on(us.listing_id, D(2025, 1, 3), conv)
            self.assertEqual((imprecise.outcome, imprecise.selected), (LookupOutcome.NO_SELECTION, None))
            self.assertEqual(len(imprecise.readings), 1)  # kept, may corroborate, never the value used


# --- Test V2 ---------------------------------------------------------------------------------

HALF_UNIT = lambda v: Fraction(1, 200)  # noqa: E731  (a half cent: the bound Example 3-C uses)


def v2(reference, adjusted, events, vintage, row_bound):
    """market-data/1.2 V2 (a'): the bound is carried by the ROWS (derived from each series' profile), not
    passed to the test. These fixtures stamp the same per-row bound the 1.1 tests passed as `row_bound`
    on both series; the expected values below are unchanged."""
    def stamp(rows_):
        return [dataclasses.replace(r, bound=row_bound(r.close)) for r in rows_]
    return verify_adjustment_v2(stamp(reference), stamp(adjusted), events, vintage)
REF_CLOSES = ("100.00", "98.50", "97.25", "99.00", "98.00")
DAYS5 = [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7), D(2025, 1, 8)]


def rows(closes, transform=lambda price, i: price):
    out = []
    for i, (day, close) in enumerate(zip(DAYS5, closes)):
        base = Decimal(close)
        o, h, l_, cl = (transform(base + off, i) for off in (Decimal(0), Decimal(1), Decimal(-1), Decimal(0)))
        out.append(PriceRow(day, o, h, l_, cl))
    return out


class V2Tests(unittest.TestCase):
    def test_a_subtractive_series_with_no_known_event_is_classified_but_unverifiable(self):
        # the arithmetic structure of Example 3-C on synthetic numbers: adj = raw - 5.25 on every field
        ref = rows(REF_CLOSES)
        adj = rows(REF_CLOSES, lambda v, i: v - Decimal("5.25"))
        r = v2(ref, adj, [], D(2026, 10, 1), HALF_UNIT)
        self.assertEqual((r.method, r.status, r.anchor), (c.AdjustmentMethod.SUBTRACTIVE, c.LabelStatus.UNVERIFIABLE, None))
        (fit,) = r.fits
        self.assertEqual((fit.a, fit.b, fit.kind), (Fraction(1), Fraction(21, 4), "SUBTRACTIVE"))
        label = apply_v2(c.AdjustmentLabel(c.AdjustmentStatus.UNDECLARED, c.AdjustmentMethod.UNKNOWN, None, kit.RETRIEVED), r)
        self.assertEqual((label.adjustment_status, label.method, label.anchor),
                         (c.AdjustmentStatus.DIVIDEND_ADJUSTED, c.AdjustmentMethod.SUBTRACTIVE, None))  # anchor unverified

    def test_a_proportional_series_is_told_apart_from_a_subtractive_one(self):
        ref = rows(REF_CLOSES)
        adj = rows(REF_CLOSES, lambda v, i: v * Decimal("0.99"))
        r = v2(ref, adj, [], D(2026, 10, 1), lambda v: Fraction(1, 2000))
        self.assertEqual((r.method, r.status), (c.AdjustmentMethod.PROPORTIONAL, c.LabelStatus.UNVERIFIABLE))
        self.assertEqual((r.fits[0].a, r.fits[0].b), (Fraction(99, 100), Fraction(0)))

    def test_identity_means_no_adjustment_in_the_window_and_the_method_stays_unknown(self):
        r = v2(rows(REF_CLOSES), rows(REF_CLOSES), [], D(2026, 10, 1), HALF_UNIT)
        self.assertEqual((r.method, r.status), (c.AdjustmentMethod.UNKNOWN, c.LabelStatus.UNVERIFIABLE))
        self.assertIn("IDENTITY", r.reason)

    def test_a_row_that_breaks_the_affine_fit_contradicts_the_label(self):
        ref = rows(REF_CLOSES)
        adj = rows(REF_CLOSES, lambda v, i: v - Decimal("5.25") + (Decimal("0.5") if i == 3 else 0))
        r = v2(ref, adj, [], D(2026, 10, 1), HALF_UNIT)
        self.assertEqual((r.method, r.status), (c.AdjustmentMethod.UNKNOWN, c.LabelStatus.CONTRADICTED))

    def test_proportional_in_one_interval_and_subtractive_in_another_is_contradicted(self):
        ref = rows(REF_CLOSES)
        adj = rows(REF_CLOSES, lambda v, i: v - Decimal("5") if i < 3 else v * Decimal("0.9"))
        r = v2(ref, adj, [CorporateEvent(DAYS5[3])], D(2026, 10, 1), HALF_UNIT)
        self.assertEqual((r.method, r.status), (c.AdjustmentMethod.UNKNOWN, c.LabelStatus.CONTRADICTED))
        self.assertIn("proportional in some", r.reason)

    def test_the_event_check_verifies_a_subtractive_cash_event_inside_the_window(self):
        ref = rows(REF_CLOSES)
        adj = rows(REF_CLOSES, lambda v, i: v - Decimal("1.00") if i < 3 else v)  # ex-date = day 4, cash 1.00
        ok = v2(ref, adj, [CorporateEvent(DAYS5[3], cash=Decimal("1.00"))], D(2026, 10, 1), HALF_UNIT)
        self.assertEqual((ok.method, ok.status, ok.anchor),
                         (c.AdjustmentMethod.SUBTRACTIVE, c.LabelStatus.VERIFIED, c.AnchorKind.LATEST))
        wrong = v2(ref, adj, [CorporateEvent(DAYS5[3], cash=Decimal("2.00"))], D(2026, 10, 1), HALF_UNIT)
        self.assertEqual((wrong.status, wrong.anchor), (c.LabelStatus.CONTRADICTED, None))

    def test_the_event_check_reaches_events_after_the_window_up_to_the_vintage(self):
        ref = rows(REF_CLOSES)
        adj = rows(REF_CLOSES, lambda v, i: v - Decimal("1.50"))  # the window is wholly before two later events
        events = [CorporateEvent(D(2025, 6, 1), cash=Decimal("1.00")), CorporateEvent(D(2025, 9, 1), cash=Decimal("0.50"))]
        tight = lambda v: Fraction(1, 20000)  # noqa: E731  (exact synthetic data, so a tight bound is honest)
        ok = v2(ref, adj, events, D(2026, 1, 1), tight)
        self.assertEqual((ok.method, ok.status), (c.AdjustmentMethod.SUBTRACTIVE, c.LabelStatus.VERIFIED))  # b = 1.00 + 0.50
        late = v2(ref, adj, events, D(2025, 7, 1), tight)  # the second event is after the vintage
        self.assertEqual(late.status, c.LabelStatus.CONTRADICTED)  # b should then be 1.00 only

    def test_the_proportional_event_check_needs_the_previous_close(self):
        ref = rows(REF_CLOSES)
        adj = rows(REF_CLOSES, lambda v, i: v * Decimal("0.99") if i < 3 else v)
        bound = lambda v: Fraction(1, 2000)  # noqa: E731
        no_prev = v2(ref, adj, [CorporateEvent(DAYS5[3], cash=Decimal("0.50"))], D(2026, 1, 1), bound)
        self.assertEqual((no_prev.method, no_prev.status), (c.AdjustmentMethod.PROPORTIONAL, c.LabelStatus.UNVERIFIABLE))
        ok = v2(ref, adj, [CorporateEvent(DAYS5[3], cash=Decimal("0.50"), p_prev=Decimal("50.00"))],
                                  D(2026, 1, 1), bound)
        self.assertEqual((ok.status, ok.anchor), (c.LabelStatus.VERIFIED, c.AnchorKind.LATEST))  # 1 - 0.5/50 = 0.99

    def test_an_interval_with_fewer_than_two_reference_values_is_skipped(self):
        ref = rows(("100.00", "100.00", "100.00", "99.00", "98.00"))
        adj = rows(("100.00", "100.00", "100.00", "99.00", "98.00"), lambda v, i: v - Decimal(2))
        r = v2(ref, adj, [CorporateEvent(DAYS5[3])], D(2026, 1, 1), HALF_UNIT)
        self.assertEqual(len(r.fits), 1)

    def test_v2_yields_no_price_and_the_label_method_has_no_other_setter(self):
        text = (Path(p.__file__).parent / "verification.py").read_text(encoding="utf-8")
        self.assertNotIn("QuoteObservation", text)
        self.assertNotIn("SourceReading", text)


# --- reconciliation ----------------------------------------------------------------------------

NOW = datetime.datetime(2026, 10, 1, 3, 0, tzinfo=datetime.timezone.utc)
SHA = "a" * 64
LID = uuid.UUID(int=7)
_count = [0]


def reading(group, price, recovered=True, bound="0", market="US", library=None, version=None, function=None,
            checks=None, adjustment=c.AdjustmentStatus.RAW, currency=kit.USD):
    _count[0] += 1
    lineage = c.Lineage(group, adjustment, source_id=group, file_sha256=SHA, adapter_id="ad", adapter_version="1",
                        source_record_ref="r", retrieved_at=NOW, market=market, library=library,
                        library_version=version, library_function=function, consistency_checks_passed=checks)
    q = c.QuoteObservation(LID, D(2025, 1, 2), Decimal(price), currency, c.SourceTiming(), lineage,
                           recovered=recovered, precision_bound=Decimal(bound))
    return c.SourceReading(f"{group}.{_count[0]}", group, SHA, q)


def real_store(release, readings):
    """A hand-built store of REAL readings of invented sources on a US venue: market-data/1.16 Ruling 4.7 item 6 refuses a real reading of a
    source with no profile or of a listing with no exchange, so the store is built in `gate_kit`'s world (see there)."""
    with gate_kit.admitted_real_world(readings):
        return InMemoryMarketData(release, readings, exchange_of=lambda _l: "XNAS")


class ReconciliationTests(unittest.TestCase):
    # The primary order is DATA. These mechanics tests keep the market-data/1.1 order (it is what they
    # exercise: the order decides only between AGREEING values); the 1.2 default order (admitted upstreams
    # only, A.5) is pinned in ProfileDataTests and in the CP2c-1 tests.
    rec = Market11Reconciler({"CN": ("eastmoney", "sina"), "HK": ("sina", "eastmoney", "alphavantage"),
                              "US": ("sina", "eastmoney", "alphavantage"), "FX": ("ecb",)})
    S = c.ReconciliationStatus

    def test_two_independent_upstreams_with_equal_recovered_values_corroborate(self):
        r = self.rec.reconcile((reading("eastmoney", "12.34"), reading("sina", "12.3400")))  # Example 4-A (a)
        self.assertIs(r.status, self.S.CORROBORATED)
        self.assertEqual(r.used.independence_group, "sina")  # the US primary order, between AGREEING values

    def test_the_primary_order_is_data_per_market_and_decides_only_between_agreeing_values(self):
        cn = self.rec.reconcile((reading("sina", "10.5", market="CN"), reading("eastmoney", "10.5", market="CN")))
        self.assertEqual(cn.used.independence_group, "eastmoney")  # CN: eastmoney first
        custom = Market11Reconciler({"US": ("eastmoney", "sina")})
        us = custom.reconcile((reading("sina", "10.5"), reading("eastmoney", "10.5")))
        self.assertEqual(us.used.independence_group, "eastmoney")
        # the order never settles a disagreement
        bad = self.rec.reconcile((reading("sina", "187.44"), reading("eastmoney", "187.43")))  # Example 4-A (b)
        self.assertEqual((bad.status, bad.used, bad.selected_source), (self.S.DISAGREEMENT, None, None))

    def test_a_recovered_value_and_an_unrecovered_one_within_half_an_ulp_agree_and_only_the_recovered_is_used(self):
        r = self.rec.reconcile((reading("sina", "187.4351", recovered=False, bound="0.005"),
                                reading("eastmoney", "187.44")))
        self.assertIs(r.status, self.S.CORROBORATED)
        self.assertEqual(r.used.independence_group, "eastmoney")  # the primary (sina) is not recovered: never used
        far = self.rec.reconcile((reading("sina", "187.40", recovered=False, bound="0.005"), reading("eastmoney", "187.44")))
        self.assertIs(far.status, self.S.DISAGREEMENT)

    def test_when_nothing_is_recovered_agreement_gives_no_value_and_no_status(self):
        # market-data/1.3 Ruling 2.4 item 4a (clarification; section 9B #1): two unrecovered readings that agree
        # within their bounds are NOT corroborated. CORROBORATED means a value is used, and none is: no value, no
        # reconciliation status. The agreement is only a lineage flag, UNRECOVERED_READINGS_AGREE.
        # (1.2 expected CORROBORATED with no value here; that was wrong.)
        r = self.rec.reconcile((reading("sina", "187.435", recovered=False, bound="0.001"),
                                reading("eastmoney", "187.4352", recovered=False, bound="0.001")))
        self.assertIsNone(r.status)
        self.assertIsNone(r.used)
        self.assertIsNone(r.selected_source)
        self.assertTrue(any("no recovered value" in f for f in r.flags))
        self.assertIn("UNRECOVERED_READINGS_AGREE", r.flags)
        # unrecovered readings that DISAGREE beyond their bounds stay a DISAGREEMENT (a conflict is not agreement)
        far = self.rec.reconcile((reading("sina", "187.40", recovered=False, bound="0.001"),
                                  reading("eastmoney", "187.4352", recovered=False, bound="0.001")))
        self.assertIs(far.status, self.S.DISAGREEMENT)
        self.assertNotIn("UNRECOVERED_READINGS_AGREE", far.flags)

    def test_a_single_upstream_is_single_source_and_an_unrecovered_single_value_is_not_used(self):
        one = self.rec.reconcile((reading("sina", "10.5"),))
        self.assertEqual((one.status, one.used.independence_group), (self.S.SINGLE_SOURCE, "sina"))
        weak = self.rec.reconcile((reading("sina", "10.5", recovered=False, bound="0.001"),))
        # market-data/1.2 Ruling 2.4 item 4a (section 9A #3, corrected): an unrecovered reading carries NO
        # status of its own: SINGLE_SOURCE means a value is used, and none is.
        self.assertEqual((weak.status, weak.used), (None, None))

    def test_two_functions_reaching_one_upstream_do_not_corroborate_and_a_difference_is_a_disagreement(self):
        agree = self.rec.reconcile((reading("eastmoney", "10.5"), reading("eastmoney", "10.5")))
        self.assertIs(agree.status, self.S.SINGLE_SOURCE)
        differ = self.rec.reconcile((reading("eastmoney", "10.5"), reading("eastmoney", "10.6")))
        self.assertIs(differ.status, self.S.DISAGREEMENT)

    def test_no_majority_no_recency_no_average(self):
        r = self.rec.reconcile((reading("sina", "10.5", market="HK"), reading("eastmoney", "10.5", market="HK"),
                                reading("alphavantage", "10.6", market="HK")))
        self.assertEqual((r.status, r.used), (self.S.DISAGREEMENT, None))
        self.assertTrue(r.differences)  # the spread is kept exactly

    def test_shared_library_safeguards_of_ruling_4_6(self):
        good = self.rec.reconcile((
            reading("eastmoney", "10.5", market="CN", library="akshare", version="1.19.1", function="stock_zh_a_hist", checks=True),
            reading("sina", "10.5", market="CN", library="akshare", version="1.19.1", function="stock_zh_a_daily")))
        self.assertEqual((good.status, good.flags), (self.S.CORROBORATED, ()))
        same_fn = self.rec.reconcile((
            reading("eastmoney", "10.5", market="CN", library="akshare", version="1", function="f"),
            reading("sina", "10.5", market="CN", library="akshare", version="1", function="f")))
        self.assertIs(same_fn.status, self.S.SINGLE_SOURCE)
        self.assertTrue(any(f.startswith("4.6(1)") for f in same_fn.flags))
        failed_check = self.rec.reconcile((
            reading("eastmoney", "10.5", market="CN", library="akshare", version="1", function="a", checks=False),
            reading("sina", "10.5", market="CN", library="akshare", version="1", function="b")))
        self.assertIs(failed_check.status, self.S.SINGLE_SOURCE)
        self.assertTrue(any(f.startswith("4.6(3)") for f in failed_check.flags))
        no_version = self.rec.reconcile((
            reading("eastmoney", "10.5", market="CN", library="akshare", function="a"),
            reading("sina", "10.5", market="CN", library="akshare", version="1", function="b")))
        self.assertTrue(any(f.startswith("4.6(4)") for f in no_version.flags))
        other_library = self.rec.reconcile((
            reading("eastmoney", "10.5", market="CN", library="akshare", version="1", function="a"),
            reading("alphavantage", "10.5", market="CN")))
        self.assertIs(other_library.status, self.S.CORROBORATED)  # a path that does not use the shared library

    def test_readings_that_differ_in_currency_or_are_not_raw_are_not_compared(self):
        r = self.rec.reconcile((reading("sina", "10.5"), reading("eastmoney", "10.5", currency=kit.HKD)))
        self.assertEqual((r.status, r.used), (None, None))
        self.assertTrue(any("NOT_COMPARABLE" in f for f in r.flags))

    def test_fx_one_publisher_two_retrievals_must_be_equal_as_decimals(self):
        def fx(group, rate):
            lineage = c.Lineage(group, c.AdjustmentStatus.RAW, source_id=group, file_sha256=SHA, adapter_id="ad",
                                adapter_version="1", source_record_ref="r", retrieved_at=NOW)
            obs = c.FXObservation(kit.EUR, kit.USD, D(2025, 1, 2), Decimal(rate), c.SourceTiming(), lineage, "ecb")
            _count[0] += 1
            return c.SourceReading(f"{group}.{_count[0]}", "ecb", SHA, obs)

        same = self.rec.reconcile((fx("ecb.file", "1.0321"), fx("frankfurter", "1.03210")))
        self.assertEqual((same.status, same.used.source_id.split(".")[0]), (self.S.SINGLE_SOURCE, "ecb"))
        differ = self.rec.reconcile((fx("ecb.file", "1.0321"), fx("frankfurter", "1.0322")))
        self.assertEqual((differ.status, differ.used), (self.S.DISAGREEMENT, None))

    def test_the_store_applies_the_reconciliation_and_a_disagreement_is_a_source_conflict_state(self):
        release = MarketDataRelease(name="t", files=(), source_precedence=())
        agree = real_store(release, [reading("sina", "10.5"), reading("eastmoney", "10.50")])
        conv = placeholder_conventions()
        lk = agree.quote_on(LID, D(2025, 1, 2), conv)
        self.assertEqual((lk.outcome, lk.selected.observation.price), (LookupOutcome.FOUND, Decimal("10.5")))
        self.assertIs(lk.reconciliation.status, self.S.CORROBORATED)
        self.assertEqual(lk.reconciliation.selected_source, lk.selected.source_id)
        clash = real_store(release, [reading("sina", "10.5"), reading("eastmoney", "10.6")])
        lk2 = clash.quote_on(LID, D(2025, 1, 2), conv)
        self.assertEqual((lk2.outcome, lk2.selected), (LookupOutcome.NO_SELECTION, None))
        state = price_input_state(lk2)
        self.assertEqual((state.state, state.reason), (SufficiencyState.INSUFFICIENT_DATA, ReasonCode.SOURCE_CONFLICT))


class InputStateTests(unittest.TestCase):
    release = MarketDataRelease(name="t", files=(), source_precedence=())

    def test_ruling_4_4_rows(self):
        conv = placeholder_conventions()
        store = real_store(self.release, [reading("sina", "10.5")])
        missing = price_input_state(store.quote_on(uuid.UUID(int=99), D(2025, 1, 2), conv))
        self.assertEqual((missing.state, missing.reason), (SufficiencyState.INSUFFICIENT_DATA, ReasonCode.MISSING_PRICE_HISTORY))
        unknown = price_input_state(store.quote_on(LID, D(2025, 1, 2), conv))  # freshness UNKNOWN: placeholder policy
        self.assertEqual((unknown.state, unknown.reason), (SufficiencyState.INSUFFICIENT_DATA, None))
        self.assertIn("configuration", unknown.note)

        class Current:
            policy_id = "test/current"

            def assess(self, timing, value_date, as_of):
                return c.Freshness(None, c.FreshnessState.CURRENT, timing.delay_status, as_of, self.policy_id)

        current = ConventionSet(Current(), conv.price_of_date, conv.reconciler, conv.fx)
        ok = price_input_state(store.quote_on(LID, D(2025, 1, 2), current))
        self.assertEqual((ok.state, ok.reason), (SufficiencyState.AVAILABLE, None))
        no_obs = price_input_state(store.quote_on(LID, D(2025, 1, 3), current))
        self.assertEqual((no_obs.state, no_obs.reason), (SufficiencyState.INSUFFICIENT_DATA, None))  # no code borrowed

    def test_fx_missing_cnh_and_conflict(self):
        conv = placeholder_conventions()
        eur_usd = c.FXObservation(kit.EUR, kit.USD, D(2025, 1, 2), Decimal("1.03"), c.SourceTiming(),
                                  c.Lineage("e", c.AdjustmentStatus.RAW, source_id="e", file_sha256=SHA, adapter_id="a",
                                            adapter_version="1", source_record_ref="r", retrieved_at=NOW), "ecb")
        store = InMemoryMarketData(self.release, [c.SourceReading("e.1", "ecb", SHA, eur_usd)])
        cnh = fx_input_state(store.fx_on(kit.CurrencyCode("CNH"), kit.USD, D(2025, 1, 2), conv))
        self.assertEqual((cnh.state, cnh.reason), (SufficiencyState.INSUFFICIENT_DATA, ReasonCode.MISSING_FX_HISTORY))
        same = fx_input_state(store.fx_on(kit.USD, kit.USD, D(2025, 1, 2), conv))
        self.assertEqual((same.state, same.reason), (SufficiencyState.AVAILABLE, None))
        cross = fx_input_state(store.fx_on(kit.USD, kit.HKD, D(2025, 1, 2), conv))  # no inversion, no crossing
        self.assertEqual(cross.reason, ReasonCode.MISSING_FX_HISTORY)

    def test_no_borrowed_code_and_the_coupling_is_enforced_by_the_product_contract(self):
        from marketdata.states import InputState
        with self.assertRaises(Exception):
            InputState(SufficiencyState.AVAILABLE, ReasonCode.SOURCE_CONFLICT)
        InputState(SufficiencyState.INSUFFICIENT_DATA, ReasonCode.SOURCE_CONFLICT)  # allowed only off AVAILABLE


if __name__ == "__main__":
    unittest.main()
