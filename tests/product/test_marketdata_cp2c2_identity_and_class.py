"""CP2c-2 identity work: (3) the FIGI-equality test for a symbol change (market-data/1.3 Ruling 7.2 item 3) and (4) the
mainland security class read from `Instrument.security_type` (market-data/1.2 section 9A item 2, confirmed in 1.3).

Every value is hand-derived from the inputs shown. All data is synthetic.
"""

import datetime
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_kit  # noqa: E402
import marketdata_cp2c1_kit as k  # noqa: E402

kit = k.kit
c = k.c

from domain.instrument import SecurityType  # noqa: E402
from marketdata.adapters.akshare_cn import AkshareCnQuoteAdapter  # noqa: E402
from marketdata.adapters.base import AdapterRegistry, IssueCode  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, MarketDataRelease, SourceRecord  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.profiles import CN_CLASS_TABLE, field_profile_of, security_class_for, SOURCES  # noqa: E402
from marketdata.resolver import (  # noqa: E402
    InMemoryIdentityRegistry,
    InstrumentEntry,
    SymbolChangeStatus,
)
from marketdata.states import price_input_state  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
FIGI_A, FIGI_B = "BBG000AAAAA1", "BBG000BBBBB2"


def assertion(figi, ticker, exch="US"):
    return c.IdentityAssertion(figi, ticker, exch, c.SourceTiming(), k.lineage("synthetic.figi", k.SHA))


# C2-4 (CP2 review): the registry compares an assertion's exchange code with the listing's MIC through DATA it is given
# (empty by default, so nothing is CONFIRMED without it). These synthetic test codes are the source's "US" and "HK".
TEST_EXCHANGE_CODES = {"XNYS": ("US",), "XNAS": ("US",), "XHKG": ("HK",)}


def us_registry(figi=FIGI_A):
    reg = InMemoryIdentityRegistry(kit.SequentialIds(), exchange_codes=TEST_EXCHANGE_CODES)
    reg.register_instruments([InstrumentEntry("Old Name Inc.", SecurityType.COMMON_STOCK, "XNYS", "NYSE", "OLD", k.USD,
                                              figi=figi, valid_from=D(2020, 1, 1))])
    return reg, kit.listing_id(reg, "OLD", "XNYS")


class FigiEqualityTests(unittest.TestCase):
    """Ruling 7.2 item 3: the old and the new ticker must resolve to the SAME FIGI on the same exchange."""

    EFFECTIVE = D(2025, 3, 3)

    def test_the_same_figi_confirms_and_applies_the_change_as_an_attribute_update(self):
        reg, lid = us_registry()
        decision = reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE, [assertion(FIGI_A, "OLD"), assertion(FIGI_A, "NEW")])
        self.assertEqual((decision.status, decision.applied, decision.old_figi, decision.new_figi),
                         (SymbolChangeStatus.CONFIRMED, True, FIGI_A, FIGI_A))
        ids = lambda t, day: reg.resolve(c.ExternalIdentifiers(ticker=t, mic="XNYS"), day)  # noqa: E731
        # Example 7-A: OLD before the effective date and NEW from it resolve to the one listing; NEW before it does not
        self.assertEqual(ids("OLD", self.EFFECTIVE - datetime.timedelta(days=1)).listing_id, lid)
        self.assertEqual(ids("NEW", self.EFFECTIVE).listing_id, lid)
        self.assertEqual(ids("NEW", self.EFFECTIVE - datetime.timedelta(days=1)).status, c.ResolutionStatus.UNRESOLVED)
        self.assertEqual(reg.listing(lid).ticker, "NEW")  # the listing keeps its id; only an attribute moved
        self.assertEqual(reg.quarantine(), ())

    def test_different_figis_are_never_a_symbol_change_and_go_to_a_human(self):
        reg, lid = us_registry()
        decision = reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE, [assertion(FIGI_A, "OLD"), assertion(FIGI_B, "NEW")])
        self.assertEqual((decision.status, decision.applied), (SymbolChangeStatus.QUARANTINED, False))
        self.assertIn("different FIGIs", decision.reason)
        self.assertEqual(reg.quarantine(), (decision,))  # kept for a human, not merged, not a new listing
        self.assertEqual(reg.listing(lid).ticker, "OLD")  # nothing changed
        self.assertEqual(reg.resolve(c.ExternalIdentifiers(ticker="NEW", mic="XNYS"), self.EFFECTIVE).status,
                         c.ResolutionStatus.UNRESOLVED)  # observations under the new ticker stay unresolved, never guessed
        self.assertEqual(len(reg.identifier_rows(lid)), 2)  # the FIGI row and the original ticker row: no new row

    def test_the_same_figi_under_two_exchange_codes_is_a_venue_change_not_a_symbol_change(self):
        reg, lid = us_registry()
        decision = reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE,
                                             [assertion(FIGI_A, "OLD", "US"), assertion(FIGI_A, "NEW", "UN")])
        self.assertEqual((decision.status, decision.applied), (SymbolChangeStatus.QUARANTINED, False))
        self.assertIn("exchange", decision.reason)

    def test_a_figi_that_contradicts_the_stored_one_is_quarantined_and_nothing_is_overwritten(self):
        reg, lid = us_registry(figi=FIGI_B)  # the listing's stored FIGI is B
        decision = reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE, [assertion(FIGI_A, "OLD"), assertion(FIGI_A, "NEW")])
        self.assertEqual((decision.status, decision.applied), (SymbolChangeStatus.QUARANTINED, False))
        self.assertEqual({r.value for r in reg.identifier_rows(lid) if r.scheme == "FIGI"}, {FIGI_B})

    def test_a_ticker_with_no_assertion_is_unconfirmed_and_nothing_is_applied_or_quarantined(self):
        reg, lid = us_registry()
        decision = reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE, [assertion(FIGI_A, "NEW")])  # the old ticker no longer resolves
        self.assertEqual((decision.status, decision.applied), (SymbolChangeStatus.UNCONFIRMED, False))
        self.assertIn("'OLD'", decision.reason)
        self.assertEqual((reg.listing(lid).ticker, reg.quarantine()), ("OLD", ()))
        none = reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE, [])
        self.assertEqual(none.status, SymbolChangeStatus.UNCONFIRMED)

    def test_a_ticker_matches_exactly_as_published_with_no_zero_padding(self):
        reg = InMemoryIdentityRegistry(kit.SequentialIds(), exchange_codes=TEST_EXCHANGE_CODES)
        reg.register_instruments([InstrumentEntry("Tencent", SecurityType.COMMON_STOCK, "XHKG", "HKEX", "0700", k.HKD, figi=FIGI_A)])
        lid = kit.listing_id(reg, "0700", "XHKG")
        decision = reg.propose_symbol_change(lid, "0701", self.EFFECTIVE,
                                             [assertion(FIGI_A, "700", "HK"), assertion(FIGI_A, "0701", "HK")])
        self.assertEqual(decision.status, SymbolChangeStatus.UNCONFIRMED)  # "700" is not "0700": a human identity file decides

    def test_the_decision_is_deterministic(self):
        outs = []
        for _ in range(2):
            reg, lid = us_registry()
            outs.append(reg.propose_symbol_change(lid, "NEW", self.EFFECTIVE, [assertion(FIGI_A, "OLD"), assertion(FIGI_B, "NEW")]))
        self.assertEqual(outs[0], outs[1])


SRC_CN = "synthetic.eastmoney_cn"


def eastmoney(symbol, close, shares=10000, day="2025-01-03"):
    """One synthetic row in the Eastmoney layout. open = close, high = close + 1, low = close - 1; volume in lots of
    100 shares; 成交额 = close x shares (so the unit check reads 100 shares per lot exactly)."""
    v = Decimal(close)
    head = "日期,股票代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率"
    row = ",".join([day, symbol, str(v), str(v), str(v + 1), str(v - 1), str(shares // 100), f"{v * shares:.1f}", "0.0", "0.0", "0.0", "0.0"])
    return (head + "\n" + row + "\n").encode("utf-8")


class NoTypeRegistry(InMemoryIdentityRegistry):
    """An identity record that does not know its security type (the class is then unknown)."""

    def security_type(self, listing_id):
        return None


class CnSecurityClassTests(unittest.TestCase):
    """market-data/1.2 section 9A #2: the class comes from `Instrument.security_type`, never from the file or the request.
    CN max decimals by class (Appendix A.1): A_SHARE 2, FUND_ETF_LOF_BOND 3. A close with MORE decimals than its class allows
    is kept but NOT recovered (Ruling 2.4 item 4: it may corroborate, never be the value used)."""

    def build(self, rows, registry_type=InMemoryIdentityRegistry):
        # RE-RECORDED for market-data/1.16 item 26: A.4 item 7 now refuses a 3-decimal close on the Eastmoney profile (delivered_dp 2) before
        # the class grid sees it, so these tests, which are about the class grid, run against a hypothetical wider profile (finding for the Quant)
        self.enterContext(gate_kit.delivered_dp("akshare.cn", 8))
        reg = registry_type(kit.SequentialIds())
        reg.register_instruments([
            InstrumentEntry("Kweichow Moutai", SecurityType.COMMON_STOCK, "XSHG", "SSE", "600519", k.CNY, vendor_ids=((SRC_CN, "600519"),)),
            InstrumentEntry("CSI 300 ETF", SecurityType.ETF, "XSHG", "SSE", "510300", k.CNY, vendor_ids=((SRC_CN, "510300"),))])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=[SourceRecord(SRC_CN, SRC_CN, "synthetic", "synthetic.cn", synthetic=True)])
        manifests = [kit.write_file(root, SRC_CN, DataKind.QUOTE, "akshare_csv_cn_daily/1", eastmoney(symbol, close), symbol, "csv",
                                    currency=k.CNY, adjustment=c.AdjustmentStatus.RAW, source_identifiers=(symbol,),
                                    request=(("function", "stock_zh_a_hist"),), market="CN") for symbol, close in rows]
        files = FileStore(root)
        built = build_in_memory_market_data(MarketDataRelease.from_manifests("cn", manifests, []), files, files.load_registry(),
                                            AdapterRegistry([AkshareCnQuoteAdapter(SRC_CN)]), reg, catalog_calendars={})
        return built, reg

    def lookup(self, built, reg, ticker):
        lid = kit.listing_id(reg, ticker, "XSHG")
        # C2-1: the lookup is ON the print date, so a governing calendar covering it is part of the setup (invented dates)
        sse = k.exchange_calendar("SSE", ("XSHG", "XSHE"), [D(2025, 1, 2), D(2025, 1, 3)], covers=(D(2025, 1, 1), D(2025, 1, 31)))
        return built.store.quote_on(lid, D(2025, 1, 3), market11_conventions(CalendarSet([sse])))

    def test_the_mapping_is_data_from_the_instrument_type_and_only_for_the_mainland(self):
        # C2-10 (market-data/1.4 Appendix A.1): the class comes from (MIC, SecurityType, trading currency); this test used
        # to assert the 1.3 SecurityType-only mapping. B-shares are told by their currency; anything else is unresolved.
        self.assertEqual(CN_CLASS_TABLE, {
            ("XSHG", "COMMON_STOCK", "CNY"): "A_SHARE", ("XSHE", "COMMON_STOCK", "CNY"): "A_SHARE",
            ("XSHG", "ETF", "CNY"): "FUND_ETF_LOF_BOND", ("XSHE", "ETF", "CNY"): "FUND_ETF_LOF_BOND",
            ("XSHG", "COMMON_STOCK", "USD"): "B_SHARE_SSE", ("XSHE", "COMMON_STOCK", "HKD"): "B_SHARE_SZSE"})
        self.assertEqual((security_class_for("XSHG", "COMMON_STOCK", "CNY"), security_class_for("XSHE", "ETF", "CNY"),
                          security_class_for("XSHG", "COMMON_STOCK", "USD"), security_class_for("XSHE", "COMMON_STOCK", "HKD"),
                          security_class_for("XSHG", None, "CNY"), security_class_for("XHKG", "ETF", "HKD"),
                          security_class_for("XNYS", "COMMON_STOCK", "USD"), security_class_for("XSHG", "ETF", "USD"),
                          security_class_for("XSHE", "COMMON_STOCK", "USD"), security_class_for("XSHG", "COMMON_STOCK", None)),
                         ("A_SHARE", "FUND_ETF_LOF_BOND", "B_SHARE_SSE", "B_SHARE_SZSE", None, None, None, None, None, None))
        self.assertIs(field_profile_of("market-data/1.16#profiles/5:akshare.cn:close"), SOURCES["akshare.cn"].fields["close"])
        self.assertIsNone(field_profile_of("market-data/1.2#profiles/1:akshare.cn:close"))  # another profile set: not read
        # PD-0067 decision 6: an id written under the previous governing set (1.14, profiles/3) names another profile set and is not read,
        # as for every earlier bump (a lineage `precision_profile_id` is recomputed at ingest)
        self.assertIsNone(field_profile_of("market-data/1.14#profiles/3:akshare.cn:close"))
        self.assertIsNone(field_profile_of("market-data/1.15#profiles/4:akshare.cn:close"))  # market-data/1.16 (item 32): an id of the previous set is not read
        self.assertIsNone(field_profile_of("market-data/1.16#profiles/4:akshare.cn:close"))  # the counter is part of the id
        self.assertIsNone(field_profile_of(None))

    def test_an_etf_close_with_three_decimals_is_recovered_by_its_class(self):
        # 4.123 has 3 decimals: off the A-share grid (2), on the fund grid (3). The adapter, which does not know the
        # listing, judged it strictly; the identity record (ETF -> FUND_ETF_LOF_BOND) now recovers it.
        built, reg = self.build([("510300", "4.123")])
        lk = self.lookup(built, reg, "510300")
        self.assertEqual((lk.outcome, lk.selected.observation.price, lk.selected.observation.recovered,
                          lk.selected.observation.precision_bound), (LookupOutcome.FOUND, Decimal("4.123"), True, Decimal(0)))
        self.assertEqual([i for _, i in built.issues if i.code is IssueCode.PRICE_NOT_RECOVERED], [])  # the stale note is gone
        st = price_input_state(lk)
        self.assertEqual((st.state, st.reason), (SufficiencyState.AVAILABLE, None))

    def test_a_common_stock_close_with_three_decimals_stays_unrecovered_and_says_which_class_refused_it(self):
        built, reg = self.build([("600519", "12.345")])  # COMMON_STOCK -> A_SHARE, 2 decimals
        lk = self.lookup(built, reg, "600519")
        self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_HISTORY, None))
        self.assertTrue(any(n.startswith("ONLY_UNRECOVERED_READINGS") for n in lk.lineage_notes), lk.lineage_notes)
        self.assertEqual(price_input_state(lk).reason, ReasonCode.MISSING_PRICE_HISTORY)
        (issue,) = [i for _, i in built.issues if i.code is IssueCode.PRICE_NOT_RECOVERED]
        self.assertIn("security class A_SHARE", issue.detail)
        self.assertNotIn("SECURITY_CLASS_UNRESOLVED", issue.detail)

    def test_an_etf_close_with_four_decimals_is_still_off_its_grid(self):
        built, reg = self.build([("510300", "4.1234")])  # 4 decimals > 3
        self.assertEqual(self.lookup(built, reg, "510300").outcome, LookupOutcome.NO_HISTORY)

    def test_an_unknown_security_class_keeps_the_strict_grid_and_is_flagged_not_silently_dropped(self):
        built, reg = self.build([("510300", "4.123")], registry_type=NoTypeRegistry)
        lk = self.lookup(built, reg, "510300")
        self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_HISTORY, None))  # fail closed: strict 2 decimals
        (issue,) = [i for _, i in built.issues if i.code is IssueCode.PRICE_NOT_RECOVERED]
        self.assertIn("SECURITY_CLASS_UNRESOLVED", issue.detail)  # 1.4 A.1: flagged under that name (was "security class unknown")
        # and once per listing as its own issue (nothing is dropped silently)
        self.assertEqual(len([i for _, i in built.issues if i.code is IssueCode.SECURITY_CLASS_UNRESOLVED]), 1)

    def test_a_close_on_the_grid_is_unaffected_by_the_class(self):
        built, reg = self.build([("600519", "1500.00"), ("510300", "4.12")])
        for ticker, price in (("600519", "1500"), ("510300", "4.12")):
            lk = self.lookup(built, reg, ticker)
            self.assertEqual((lk.outcome, lk.selected.observation.price), (LookupOutcome.FOUND, Decimal(price)), ticker)

    def test_the_class_never_comes_from_the_request_or_the_file(self):
        # the real manifest of such a file carries no class, and a request parameter named like one changes nothing
        built, reg = self.build([("510300", "4.123")])
        self.assertNotIn("security_class", " ".join(f"{a}={b}" for m in built.manifests for a, b in m.request))
        src = (Path(__file__).resolve().parents[2] / "src" / "marketdata" / "adapters" / "daily_csv.py").read_text(encoding="utf-8")
        self.assertIn("security_class: Optional[str] = None", src)  # the adapter still passes no class: unknown there


class MultiSymbolFileV0Tests(unittest.TestCase):
    """market-data/1.16 section 11 item 25, the Quant's finding F-1: Test V0's unit is the SERIES (symbol, file), not the file. A file of two symbols in
    which one repeats a date excludes that symbol only; the other is read as before, and its lookup does not read NO_ADMITTED_SOURCE (a cause that would be
    untrue). The Eastmoney layout is the only multi-symbol route (a refused source, synthetic here)."""

    def rows(self, *specs):
        """specs: (symbol, day); close 10.50 everywhere so the change column (always 0.0) agrees on every pair."""
        body = [eastmoney(symbol, "10.50", day=day).decode("utf-8").splitlines()[1] for symbol, day in specs]
        head = eastmoney("x", "1").decode("utf-8").splitlines()[0]
        return ("\n".join([head] + body) + "\n").encode("utf-8")

    def build(self, payload, first_aliases=("600519",)):
        reg = InMemoryIdentityRegistry(kit.SequentialIds())
        reg.register_instruments([
            InstrumentEntry("Kweichow Moutai", SecurityType.COMMON_STOCK, "XSHG", "SSE", "600519", k.CNY, vendor_ids=tuple((SRC_CN, a) for a in first_aliases)),
            InstrumentEntry("A second share", SecurityType.COMMON_STOCK, "XSHG", "SSE", "600520", k.CNY, vendor_ids=((SRC_CN, "600520"),))])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=[SourceRecord(SRC_CN, SRC_CN, "synthetic", "synthetic.cn", synthetic=True)])
        manifests = [kit.write_file(root, SRC_CN, DataKind.QUOTE, "akshare_csv_cn_daily/1", payload, "two", "csv", currency=k.CNY,
                                    adjustment=c.AdjustmentStatus.RAW, source_identifiers=("600519",), request=(("function", "stock_zh_a_hist"),), market="CN")]
        files = FileStore(root)
        built = build_in_memory_market_data(MarketDataRelease.from_manifests("cn2", manifests, []), files, files.load_registry(),
                                            AdapterRegistry([AkshareCnQuoteAdapter(SRC_CN)]), reg, catalog_calendars={})
        sse = k.exchange_calendar("SSE", ("XSHG", "XSHE"), [D(2025, 1, 2), D(2025, 1, 3)], covers=(D(2025, 1, 1), D(2025, 1, 31)))
        conv = market11_conventions(CalendarSet([sse]))
        return built, reg, lambda ticker: built.store.quote_on(kit.listing_id(reg, ticker, "XSHG"), D(2025, 1, 3), conv)

    def test_1_control_without_the_repeated_row_both_symbols_are_served(self):
        built, reg, look = self.build(self.rows(("600519", "2025-01-02"), ("600519", "2025-01-03"), ("600520", "2025-01-02"), ("600520", "2025-01-03")))
        self.assertEqual([look(t).outcome for t in ("600519", "600520")], [LookupOutcome.FOUND, LookupOutcome.FOUND])
        self.assertEqual(built.store.export().exclusions, ())

    def test_2_only_the_symbol_that_repeats_a_date_is_excluded_and_the_other_is_served(self):
        built, reg, look = self.build(self.rows(("600519", "2025-01-02"), ("600519", "2025-01-03"), ("600520", "2025-01-02"), ("600520", "2025-01-03"),
                                                ("600520", "2025-01-03")))
        clean, bad = look("600519"), look("600520")
        # the clean symbol: its readings are there, its lookup is a price, and nothing says it has no admitted source
        self.assertEqual((clean.outcome, clean.selected.observation.price), (LookupOutcome.FOUND, Decimal("10.5")))
        self.assertEqual(price_input_state(clean).state, SufficiencyState.AVAILABLE)
        self.assertFalse(any(n.startswith("NO_ADMITTED_SOURCE") for n in clean.lineage_notes), clean.lineage_notes)
        self.assertEqual(len(built.store.quotes(kit.listing_id(reg, "600519", "XSHG"), D(2025, 1, 1), D(2025, 1, 31)).readings), 2)
        # the repeated symbol: no reading, its own cause in lineage, V0 and the date, and no NO_ADMITTED_SOURCE beside it (item 28)
        self.assertEqual((bad.outcome, bad.selected), (LookupOutcome.NO_HISTORY, None))
        (note,) = bad.lineage_notes
        self.assertTrue(note.startswith("SERIES_CONTRADICTED: V0 on file "), note)
        self.assertIn("DUPLICATE_SESSION_DATE", note)
        self.assertIn("2025-01-03", note)
        (exclusion,) = built.store.export().exclusions
        self.assertEqual(exclusion.listing_id, kit.listing_id(reg, "600520", "XSHG"))
        self.assertEqual([i.row_ref for _sha, i in built.issues if i.code is IssueCode.DUPLICATE_SESSION_DATE], ["600520@2025-01-03"])

    # --- LOW-5 (Addendum A.4): the key is the LISTING after identity resolution, not the vendor symbol --------------------------------------------

    def test_3_two_aliases_of_one_listing_on_one_date_contradict_the_series(self):
        """One XSHG listing carries two vendor ids, `600519` and `600519X`; a two-symbol file states 2025-01-03 once under each. That is the listing's session
        stated twice. Hand outcome (the Quant's): the series (listing, file) is CONTRADICTED, no reading on any date; INSUFFICIENT_DATA + MISSING_PRICE_HISTORY
        with SERIES_CONTRADICTED (V0, 2025-01-03); not `FOUND 10.50`."""
        built, reg, look = self.build(self.rows(("600519", "2025-01-02"), ("600519", "2025-01-03"), ("600519X", "2025-01-03"), ("600520", "2025-01-02"),
                                                ("600520", "2025-01-03")), first_aliases=("600519", "600519X"))
        moutai, other = look("600519"), look("600520")
        st = price_input_state(moutai)
        self.assertEqual((moutai.outcome, moutai.selected, st.state, st.reason),
                         (LookupOutcome.NO_HISTORY, None, SufficiencyState.INSUFFICIENT_DATA, ReasonCode.MISSING_PRICE_HISTORY))
        (note,) = moutai.lineage_notes
        self.assertTrue(note.startswith("SERIES_CONTRADICTED: V0 on file "), note)
        self.assertIn("2025-01-03", note)
        self.assertEqual(built.store.quotes(kit.listing_id(reg, "600519", "XSHG"), D(2025, 1, 1), D(2025, 1, 31)).readings, ())
        (exclusion,) = built.store.export().exclusions
        self.assertEqual(exclusion.listing_id, kit.listing_id(reg, "600519", "XSHG"))
        # the other listing of the file is a different series and is served
        self.assertEqual((other.outcome, other.selected.observation.price), (LookupOutcome.FOUND, Decimal("10.5")))

    def test_4_two_aliases_of_one_listing_on_different_dates_are_one_series_stated_once_per_date(self):
        built, reg, look = self.build(self.rows(("600519", "2025-01-02"), ("600519X", "2025-01-03")), first_aliases=("600519", "600519X"))
        self.assertEqual(look("600519").outcome, LookupOutcome.FOUND)
        self.assertEqual(built.store.export().exclusions, ())

    # --- the header names a column twice (Addendum A.3, observation) --------------------------------------------------------------------------

    def test_5_a_header_that_names_a_read_column_twice_contradicts_every_series_of_the_file(self):
        """`csv.DictReader` keeps the LAST of two same-named columns, which would serve one of two statements of every close by position. Every row states
        its close twice, so every series (listing, file) is two statements of one close: CONTRADICTED, the file stays in M, no reading."""
        lines = self.rows(("600519", "2025-01-02"), ("600519", "2025-01-03"), ("600520", "2025-01-02"), ("600520", "2025-01-03")).decode("utf-8").splitlines()
        payload = "\n".join([lines[0] + ",收盘"] + [row + ",99.00" for row in lines[1:]]) + "\n"
        built, reg, look = self.build(payload.encode("utf-8"))
        for ticker in ("600519", "600520"):
            lk = look(ticker)
            self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_HISTORY, None), ticker)
            (note,) = lk.lineage_notes
            self.assertTrue(note.startswith("SERIES_CONTRADICTED: V0 on file "), (ticker, note))
        self.assertEqual(sorted(e.listing_id for e in built.store.export().exclusions),
                         sorted(kit.listing_id(reg, t, "XSHG") for t in ("600519", "600520")))
        (sha,) = {e.file_sha256 for e in built.store.export().exclusions}
        self.assertIn(sha, {s.file_sha256 for s in built.summaries})  # the file stays in M
        self.assertIn(("header/收盘", IssueCode.DUPLICATE_SESSION_DATE), [(i.row_ref, i.code) for _s, i in built.issues])

    def test_6_a_repeated_column_the_adapter_does_not_read_changes_nothing(self):
        lines = self.rows(("600519", "2025-01-02"), ("600519", "2025-01-03")).decode("utf-8").splitlines()
        payload = "\n".join([lines[0] + ",未使用,未使用"] + [row + ",1,2" for row in lines[1:]]) + "\n"
        built, reg, look = self.build(payload.encode("utf-8"))
        self.assertEqual(look("600519").outcome, LookupOutcome.FOUND)
        self.assertEqual(built.store.export().exclusions, ())


if __name__ == "__main__":
    unittest.main()
