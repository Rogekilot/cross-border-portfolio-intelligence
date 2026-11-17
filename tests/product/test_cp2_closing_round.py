"""CP2 closing round (final check section 27 of `reviews/TECH_REVIEW.md`; conventions `market-data/1.7`): one regression test per item.

    C2-16  Test V0-FX: an FX series with any off-calendar row is excluded whole; a row after the file could have held it
           contradicts the series (FX: after D_ret; prices: after the latest session closed at retrieval)
    C2-17  an exchange-level record with no security type does not attach       C2-18  a contradicting composite is quarantined
    note   the ticker of an exchange-level or composite attach is the one valid ON the assertion date
    1.6    overlapping windows: every account holding at X1 or X2, cause OVERLAPPING_SPLIT_WINDOWS, the coverage-gap pair;
           a composite-only observation stays unresolved

Every expected value is derived by hand from the inputs shown. All data is synthetic.
"""

import datetime
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402
import test_corporate_actions_service as f8t  # noqa: E402
import test_cp2_fix_round_marketdata as fr  # noqa: E402

k = x.k
c = x.c
kit = x.kit

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.instrument import SecurityType  # noqa: E402
from marketdata.adapters.ecb_eurofxref import EcbEurofxrefFxAdapter  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, MarketDataRelease  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
S, R = SufficiencyState, ReasonCode
state_of = fr.state_of


# --- C2-16 -------------------------------------------------------------------------------------------------------------

def build_variant(us_rows=None, ecb_rows=None, ecb_dates=None, nyse_dates=None, with_frankfurter=False):
    """The exit kit's "formats" world with its US file, its ECB file and its calendars replaced. Retrieval is the kit's
    2025-01-10 09:00 UTC: the ECB fixing of 10 January (16:00 Berlin = 15:00 UTC) is NOT yet published, so D_ret = 2025-01-09;
    the NYSE session of 9 January closed at 21:00 UTC on the 9th, the one of the 10th had not (it opens at 14:30 UTC)."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    x.write_registry(root)
    specs, adapters = x.world_specs("formats_frankfurter" if with_frankfurter else "formats")
    out = []
    for spec in specs:
        if spec["source_id"] == x.SRC_CAL and spec["label"] == "ECB_FIXINGS" and ecb_dates == "none":
            continue  # no ECB calendar in M
        if spec["source_id"] == x.SRC_CAL and spec["label"] == "ECB_FIXINGS" and ecb_dates is not None:
            spec = dict(spec, payload=k.calendar_json("ECB_FIXINGS", "ECB_FIXINGS", ("ECB",), "Europe/Berlin",
                                                      coverage=("2025-01-01", "2025-01-31"), dates=ecb_dates))
        if spec["source_id"] == x.SRC_CAL and spec["label"] == "NYSE_SESSIONS" and nyse_dates is not None:
            spec = dict(spec, payload=k.calendar_json("NYSE_SESSIONS", "EXCHANGE_SESSIONS", ("XNYS", "XNAS"), "America/New_York",
                                                      coverage=("2025-01-01", "2025-01-31"), dates=nyse_dates))
        if spec["source_id"] == x.SRC_US and us_rows is not None:
            spec = dict(spec, payload=x.av_us_csv(us_rows))
        if spec["source_id"] == x.SRC_ECB and ecb_rows is not None:
            spec = dict(spec, payload=k.ecb_csv(ecb_rows, ["USD", "HKD", "CNY"]))
        out.append(spec)
    if with_frankfurter and ecb_rows is not None:  # an ECB-direct file next to the Frankfurter one
        adapters.register(EcbEurofxrefFxAdapter(x.SRC_ECB))
        out.append(dict(source_id=x.SRC_ECB, kind=DataKind.FX, payload_format="ecb_eurofxref_hist_csv/1",
                        payload=k.ecb_csv(ecb_rows, ["USD", "HKD", "CNY"]), label="fx_ecb", ext="csv",
                        source_identifiers=("USD", "HKD", "CNY")))
    manifests = [kit.write_file(root, **spec) for spec in out]
    release = MarketDataRelease.from_manifests("c2-16", manifests, [])
    files = FileStore(root)
    ident = x.identity()
    built = build_in_memory_market_data(release, files, files.load_registry(), adapters, ident, catalog_calendars={})
    return built, ident, release, manifests, tmp


FIX_6_10 = (D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7), D(2025, 1, 8), D(2025, 1, 9), D(2025, 1, 10))
ECB_DATES = [d.isoformat() for d in FIX_6_10]


def shifted_rows():
    """P13: the true fixings Mon 6 to Fri 10 January, USD 1.01 to 1.05, every row labelled ONE DAY EARLY (Sun 5 to Thu 9)."""
    true = [("2025-01-05", "1.01"), ("2025-01-06", "1.02"), ("2025-01-07", "1.03"), ("2025-01-08", "1.04"), ("2025-01-09", "1.05")]
    return [(day, [rate, "8.4000", "7.8000"]) for day, rate in true]


class C2_16_TestV0FxExcludesTheWholeSeries(unittest.TestCase):
    def test_p13_a_series_labelled_one_day_early_is_excluded_whole_not_just_its_sunday_row(self):
        built, _, _, _, tmp = build_variant(ecb_rows=shifted_rows(), ecb_dates=ECB_DATES)
        self.addCleanup(tmp.cleanup)
        # the Sunday 5 January is not a fixing day: V0-FX excludes the whole (file, currency) series, for each currency
        self.assertEqual({(r.test, r.status, r.admitted) for r in built.label_results if r.test.startswith("V0_FX")},
                         {("V0_FX_OFF_CALENDAR", c.LabelStatus.CONTRADICTED, False)})
        self.assertEqual(sorted(e.currency for e in built.store.export().exclusions if e.listing_id is None), ["CNY", "HKD", "USD"])
        conv = market11_conventions(built.calendars)
        # as of Monday 6 January it used to serve Tuesday's 1.02 (51/50) as CURRENT/AVAILABLE; now there is no rate at all
        lk = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 6), conv)
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.NOT_IN_RELEASE, None))
        self.assertEqual(state_of(lk, fx=True), (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY))
        self.assertTrue(any(n.startswith("V0_FX_OFF_CALENDAR") for n in lk.lineage_notes), lk.lineage_notes)
        # the file stays in M, and a Thursday row (a valid fixing day) of the shifted series is not used either
        self.assertEqual(built.store.fx_on(k.EUR, k.USD, D(2025, 1, 10), conv).rate, None)

    def test_with_another_valid_series_the_lookup_falls_back_to_it_counted_by_missed_fixings(self):
        # the Frankfurter file (true fixings 2 and 3 January: USD 1.0800 and 1.0810) is the only admitted series; as of Mon 6 January
        # the last valid fixing is the 3rd, and the 6th has been missed: 1 missed fixing, AVAILABLE + STALE_DATA
        built, _, _, _, tmp = build_variant(ecb_rows=shifted_rows(), ecb_dates=ECB_DATES, with_frankfurter=True)
        self.addCleanup(tmp.cleanup)
        lk = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 6), market11_conventions(built.calendars))
        self.assertEqual((lk.outcome, lk.rate, lk.date_used, lk.missed_count), (LookupOutcome.FOUND, Fraction(10810, 10000), D(2025, 1, 3), 1))
        self.assertEqual(state_of(lk, fx=True), (S.AVAILABLE, R.STALE_DATA))
        self.assertTrue(any("V0_FX_OFF_CALENDAR" in n for n in lk.lineage_notes))

    def test_five_missed_fixings_after_the_last_valid_one_is_missing_fx_history(self):
        built, _, _, _, tmp = build_variant(ecb_rows=shifted_rows(), ecb_dates=ECB_DATES, with_frankfurter=True)
        self.addCleanup(tmp.cleanup)
        # fixings after the 3rd up to the 10th: 6, 7, 8, 9, 10 = 5 missed: the rate is withheld (Ruling 1.6)
        lk = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 10), market11_conventions(built.calendars))
        self.assertEqual((lk.outcome, lk.rate, lk.missed_count), (LookupOutcome.STALE_BEYOND_LIMIT, None, 5))
        self.assertEqual(state_of(lk, fx=True), (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY))

    def test_rows_outside_the_calendars_coverage_are_not_judged(self):
        # 30 December 2024 lies before the calendar's coverage (1-31 January): UNVERIFIABLE, not off-calendar; the series stays
        rows = [("2024-12-30", ["1.0700", "8.4000", "7.8000"]), ("2025-01-03", ["1.0810", "8.4100", "7.8100"])]
        built, _, _, _, tmp = build_variant(ecb_rows=rows, ecb_dates=ECB_DATES)
        self.addCleanup(tmp.cleanup)
        self.assertEqual([r for r in built.label_results if r.test.startswith("V0_FX")], [])
        lk = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 3), market11_conventions(built.calendars))
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.FOUND, Fraction(10810, 10000)))

    def test_with_no_ecb_calendar_nothing_is_judged(self):
        built, _, _, _, tmp = build_variant(ecb_rows=shifted_rows(), ecb_dates="none")
        self.addCleanup(tmp.cleanup)
        self.assertEqual([r for r in built.label_results if r.test.startswith("V0_FX")], [])  # nothing is judged without a calendar
        lk = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 6), market11_conventions(built.calendars))
        self.assertEqual((lk.outcome, state_of(lk, fx=True)), (LookupOutcome.FRESHNESS_UNKNOWN, (S.INSUFFICIENT_DATA, None)))

    # -- the after-retrieval rule, for FX ------------------------------------------------------------------------------

    def test_a_correctly_dated_row_after_d_ret_contradicts_the_series_a_shift_landing_only_on_valid_days(self):
        # retrieved 2025-01-10 09:00 UTC: D_ret = 9 January (the 10th is published at 15:00 UTC). A series through 10 January,
        # every date a real fixing day, holds a row the file could not contain
        rows = [(d, ["1.0900", "8.4000", "7.8000"]) for d in ("2025-01-08", "2025-01-09", "2025-01-10")]
        late, _, _, _, tmp = build_variant(ecb_rows=rows, ecb_dates=ECB_DATES)
        self.addCleanup(tmp.cleanup)
        self.assertEqual({r.test for r in late.label_results if r.test.startswith("V0_FX")}, {"V0_FX_AFTER_RETRIEVAL"})
        self.assertIn("2025-01-10", [r.reason for r in late.label_results if r.test == "V0_FX_AFTER_RETRIEVAL"][0])
        lk = late.store.fx_on(k.EUR, k.USD, D(2025, 1, 9), market11_conventions(late.calendars))
        self.assertEqual(lk.outcome, LookupOutcome.NOT_IN_RELEASE)
        # control: the same series through the 9th is admitted
        ok, _, _, _, tmp2 = build_variant(ecb_rows=rows[:2], ecb_dates=ECB_DATES)
        self.addCleanup(tmp2.cleanup)
        self.assertEqual([r for r in ok.label_results if r.test.startswith("V0_FX")], [])
        self.assertEqual(ok.store.fx_on(k.EUR, k.USD, D(2025, 1, 9), market11_conventions(ok.calendars)).rate, Fraction(10900, 10000))

    # -- the after-retrieval rule, for prices --------------------------------------------------------------------------

    NYSE = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09", "2025-01-10"]

    def test_a_price_row_dated_after_the_latest_closed_session_contradicts_the_series_and_valid_days_do_not_save_it(self):
        # the NYSE session of 10 January closes at 21:00 UTC on the 10th; the file was retrieved at 09:00 UTC: the latest closed
        # session is the 9th. Every row is a listed session: Test V0 passes, the after-retrieval rule does not
        rows = [(D(2025, 1, 8), "150.00", 1000), (D(2025, 1, 9), "151.00", 1000), (D(2025, 1, 10), "152.00", 1000)]
        built, ident, _, _, tmp = build_variant(us_rows=rows, nyse_dates=self.NYSE)
        self.addCleanup(tmp.cleanup)
        aapl = x.lid(ident, "AAPL", "XNAS")
        v0 = [r for r in built.label_results if r.test == "V0" and r.listing_id == aapl]
        self.assertEqual([(r.status, r.admitted) for r in v0], [(c.LabelStatus.CONTRADICTED, False)])
        self.assertIn("after retrieval", v0[0].reason)
        lk = built.store.quote_on(aapl, D(2025, 1, 9), market11_conventions(built.calendars))
        self.assertEqual((lk.outcome, state_of(lk)), (LookupOutcome.NO_HISTORY, (S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY)))
        # control: through the 9th is admitted and current
        ok, ident2, _, _, tmp2 = build_variant(us_rows=rows[:2], nyse_dates=self.NYSE)
        self.addCleanup(tmp2.cleanup)
        good = ok.store.quote_on(x.lid(ident2, "AAPL", "XNAS"), D(2025, 1, 9), market11_conventions(ok.calendars))
        self.assertEqual((good.outcome, good.selected.observation.price, good.missed_count), (LookupOutcome.FOUND, Decimal("151.00"), 0))


# --- C2-17, C2-18, ticker date, composite-only -------------------------------------------------------------------------

def assertion(figi, ticker, exch, composite=None, share=None, security_type=None, day=None):
    import datetime as dt  # noqa: PLC0415

    timing = c.SourceTiming(None if day is None else dt.datetime(day.year, day.month, day.day, 12, tzinfo=dt.timezone.utc))
    return c.IdentityAssertion(figi, ticker, exch, timing, k.lineage("synthetic.figi", k.SHA), composite_figi=composite,
                               share_class_figi=share, security_type=security_type)


class Figi16Tests(unittest.TestCase):
    FIGI, COMP, SHARE = "BBG000BJ35N5", "BBG000BJ35F4", "BBG001S8C4T6"  # 700 on HK, as observed

    def hk(self):
        reg = InMemoryIdentityRegistry(kit.SequentialIds())
        reg.register_instruments([InstrumentEntry("Tencent", SecurityType.COMMON_STOCK, "XHKG", "HKEX", "700", k.HKD,
                                                  valid_from=D(2020, 1, 1))])
        return reg, kit.listing_id(reg, "700", "XHKG")

    def test_c2_17_an_exchange_level_record_with_no_security_type_does_not_attach_and_is_quarantined(self):
        reg, lid = self.hk()
        ((_, res, added),) = reg.apply_identity_assertions([assertion(self.FIGI, "700", "HK", self.COMP, self.SHARE, None)])
        self.assertEqual((added, res.status), ((), c.ResolutionStatus.CONFLICT))  # it used to attach FIGI + composite + share class
        (q,) = reg.assertion_quarantine()
        self.assertEqual((q.verdict, q.listing_id), ("SECURITY_TYPE_MISMATCH", lid))
        self.assertEqual((reg.listing(lid).figi, reg.listing(lid).composite_figi), (None, None))
        # control: the same record WITH its type attaches
        ((_, ok, added2),) = reg.apply_identity_assertions([assertion(self.FIGI, "700", "HK", self.COMP, self.SHARE, "Common Stock")])
        self.assertEqual((ok.status, added2), (c.ResolutionStatus.RESOLVED, ("FIGI", "COMPOSITE_FIGI", "SHARE_CLASS_FIGI")))

    def test_c2_18_a_second_record_with_the_same_figi_and_another_composite_is_quarantined_with_no_second_composite_row(self):
        reg, lid = self.hk()
        reg.apply_identity_assertions([assertion(self.FIGI, "700", "HK", self.COMP, self.SHARE, "Common Stock")])
        ((_, res, added),) = reg.apply_identity_assertions([assertion(self.FIGI, "700", "HK", "BBGOTHERCOMP", self.SHARE, "Common Stock")])
        self.assertEqual((res.status, added), (c.ResolutionStatus.CONFLICT, ()))  # it was RESOLVED with a second COMPOSITE row
        (q,) = reg.assertion_quarantine()
        self.assertEqual(q.verdict, "COMPOSITE_CONFLICT")
        self.assertEqual([r.value for r in reg.identifier_rows(lid) if r.scheme == "COMPOSITE_FIGI"], [self.COMP])
        self.assertEqual(reg.listing(lid).composite_figi, self.COMP)

    def test_the_ticker_of_an_exchange_level_attach_is_the_one_valid_on_the_assertion_date(self):
        reg, lid = self.hk()
        reg.change_ticker(lid, "701", D(2025, 3, 3))  # 700 until 2025-03-02, 701 from 2025-03-03
        before = assertion(self.FIGI, "700", "HK", self.COMP, self.SHARE, "Common Stock", D(2025, 2, 1))
        after = assertion(self.FIGI, "700", "HK", self.COMP, self.SHARE, "Common Stock", D(2025, 4, 1))
        ((_, res_after, added_after),) = reg.apply_identity_assertions([after])  # "700" was no longer the ticker on 1 April
        self.assertEqual((res_after.status, added_after), (c.ResolutionStatus.UNRESOLVED, ()))
        self.assertIsNone(reg.listing(lid).figi)
        ((_, res_before, added_before),) = reg.apply_identity_assertions([before])  # but it was on 1 February
        self.assertEqual((res_before.status, added_before), (c.ResolutionStatus.RESOLVED, ("FIGI", "COMPOSITE_FIGI", "SHARE_CLASS_FIGI")))

    def test_the_ticker_of_a_composite_attach_is_also_valid_on_the_assertion_date(self):
        reg = InMemoryIdentityRegistry(kit.SequentialIds())
        reg.register_instruments([InstrumentEntry("Apple", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", k.USD,
                                                  valid_from=D(2020, 1, 1))])
        lid = kit.listing_id(reg, "AAPL", "XNAS")
        reg.change_ticker(lid, "AAPX", D(2025, 3, 3))
        later = assertion("BBG000B9XRY4", "AAPL", "US", "BBG000B9XRY4", None, "Common Stock", D(2025, 4, 1))
        ((_, res, added),) = reg.apply_identity_assertions([later])
        self.assertEqual((res.status, added), (c.ResolutionStatus.UNRESOLVED, ()))
        earlier = assertion("BBG000B9XRY4", "AAPL", "US", "BBG000B9XRY4", None, "Common Stock", D(2025, 2, 1))
        ((_, res2, added2),) = reg.apply_identity_assertions([earlier])
        self.assertEqual((res2.status, added2), (c.ResolutionStatus.RESOLVED, ("COMPOSITE_FIGI",)))

    def test_a_composite_only_observation_stays_unresolved_even_after_the_composite_is_attached(self):
        # Ruling 7.3 item 4 (1.6): no admitted source produces composite-only observations, so such an observation is unresolved
        reg = InMemoryIdentityRegistry(kit.SequentialIds())
        reg.register_instruments([InstrumentEntry("Apple", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", k.USD)])
        reg.apply_identity_assertions([assertion("BBG000B9XRY4", "AAPL", "US", "BBG000B9XRY4", None, "Common Stock")])
        self.assertEqual(reg.listing(kit.listing_id(reg, "AAPL", "XNAS")).composite_figi, "BBG000B9XRY4")
        for as_of in (None, D(2025, 1, 3)):
            res = reg.resolve(c.ExternalIdentifiers(figi="BBG000B9XRY4"), as_of)
            self.assertEqual((res.status, res.listing_id), (c.ResolutionStatus.UNRESOLVED, None), as_of)


# --- 1.6: overlapping windows, every account, and the coverage-gap pair ------------------------------------------------

class C2_15_Item5_1_6Tests(unittest.TestCase):
    FEB17 = D(2025, 2, 17)

    def port(self, second=None):
        second = second or self.FEB17
        return f8t.port_with([f8t.split_reading(f8t.FEED, f8t.FEED_SHA, (2, 1)), f8t.split_reading(f8t.FILING, f8t.FILING_SHA, (2, 1)),
                              f8t.split_reading(f8t.FEED, f8t.FEED_SHA, (3, 1), day=second),
                              f8t.split_reading(f8t.FILING, f8t.FILING_SHA, (3, 1), day=second)])

    def ledger(self):
        # A1 holds from 20 December and sells ALL on 10 February (so it holds at the start of 3 February but NOT of 17 February);
        # A2 buys on 10 February (it holds at the start of 17 February but NOT of 3 February)
        ledger = f8t.ledger_with_holdings(accounts=(f8t.A1,))
        ledger.add(f8t.LedgerEvent(f8t.eid(), f8t.A1, f8t.EventType.SELL, D(2025, 2, 10), f8t.USD, listing_id=f8t.LISTING,
                                   quantity=Decimal(50), amount=f8t.Money(Decimal(7500), f8t.USD)))
        ledger.add(f8t.LedgerEvent(f8t.eid(), f8t.A2, f8t.EventType.DEPOSIT, D(2025, 1, 2), f8t.USD, amount=f8t.Money(Decimal(10000), f8t.USD)))
        ledger.add(f8t.LedgerEvent(f8t.eid(), f8t.A2, f8t.EventType.BUY, D(2025, 2, 10), f8t.USD, listing_id=f8t.LISTING,
                                   quantity=Decimal(10), amount=f8t.Money(Decimal(1000), f8t.USD)))
        return ledger

    def test_every_account_holding_at_x1_or_x2_gets_conflict_ratio_for_both_splits_with_the_cause_and_one_suppression_date(self):
        ledger = self.ledger()
        report = f8t.run(ledger, self.port())
        got = sorted((str(o.account_id), o.ex_date, o.decision, o.cause) for o in report.outcomes if o.decision is not f8b.SplitDecision.NOT_HELD)
        want = sorted((str(a), d, f8b.SplitDecision.CONFLICT_RATIO, "OVERLAPPING_SPLIT_WINDOWS")
                      for a in (f8t.A1, f8t.A2) for d in (f8t.EX, self.FEB17))
        self.assertEqual(got, want)  # four outcomes: A1 and A2, each for BOTH splits, though each holds at only one ex-date
        self.assertEqual(ledger.appended, [])
        self.assertEqual({(s.account_id, s.first_date, s.end_exclusive, s.reason_code) for s in report.suppressions},
                         {(a, f8t.EX, None, ReasonCode.SOURCE_CONFLICT) for a in (f8t.A1, f8t.A2)})  # from X1 = 2025-02-03
        self.assertTrue(all("OVERLAPPING_SPLIT_WINDOWS" in s.flag for s in report.suppressions))

    def test_the_same_with_a_range_that_holds_only_the_second_split(self):
        ledger = self.ledger()
        report = f8t.run(ledger, self.port(), start=D(2025, 2, 10), end=D(2025, 2, 28))
        self.assertEqual({(o.account_id, o.ex_date, o.decision) for o in report.outcomes if o.decision is not f8b.SplitDecision.NOT_HELD},
                         {(a, self.FEB17, f8b.SplitDecision.CONFLICT_RATIO) for a in (f8t.A1, f8t.A2)})
        self.assertEqual({s.first_date for s in report.suppressions}, {f8t.EX})  # still from the earlier ex-date
        self.assertEqual(ledger.appended, [])

    def test_when_the_calendar_cannot_cover_both_windows_both_splits_take_the_gap_outcome_from_x1_and_nothing_is_appended(self):
        # the calendar ends 2025-03-07: W(3 Feb) = [6 Jan, 3 Mar] is covered; the second split, 2 June, is not covered at all, so
        # whether the windows overlap cannot be decided (no session count between the ex-dates exists either)
        june = D(2025, 6, 2)
        short = f8t.CalendarSet([f8t.k.exchange_calendar("TEST_SESSIONS", (f8t.MIC,), f8t.weekdays(D(2024, 6, 3), D(2025, 3, 7)))])
        ledger = f8t.ledger_with_holdings()
        report = f8b.confirm_splits(ledger, self.port(june), f8t.PORTFOLIO, (f8t.LISTING,), D(2025, 1, 1), D(2025, 12, 31), f8t.POLICY,
                                    {f8t.LISTING: f8t.USD}, calendars=short, exchange_of=f8t.exchange_of)
        self.assertEqual(sorted((o.ex_date, o.decision) for o in report.outcomes),
                         [(f8t.EX, f8b.SplitDecision.CALENDAR_COVERAGE_GAP), (june, f8b.SplitDecision.CALENDAR_COVERAGE_GAP)])
        self.assertEqual(ledger.appended, [])
        # INSUFFICIENT_DATA with no reason code from X1 for both
        self.assertEqual({(s.first_date, s.end_exclusive, s.reason_code) for s in report.suppressions}, {(f8t.EX, None, None)})

    def test_pairs_the_calendar_shows_to_be_disjoint_are_still_appended_when_one_window_is_uncovered(self):
        # Feb 3 and a split beyond the calendar's end by MORE than 40 sessions cannot be shown disjoint (uncovered): gap. But a
        # calendar covering the whole interval between the ex-dates shows 41+ sessions apart: decided disjoint
        far = D(2025, 4, 7)  # 46 sessions after 3 Feb
        cal = f8t.CalendarSet([f8t.k.exchange_calendar("TEST_SESSIONS", (f8t.MIC,), f8t.weekdays(D(2024, 6, 3), D(2025, 4, 8)))])
        ledger = f8t.ledger_with_holdings()
        report = f8b.confirm_splits(ledger, self.port(far), f8t.PORTFOLIO, (f8t.LISTING,), D(2025, 1, 1), D(2025, 12, 31), f8t.POLICY,
                                    {f8t.LISTING: f8t.USD}, calendars=cal, exchange_of=f8t.exchange_of)
        # the second split's own window (to 5 May) is uncovered, so IT is a gap by item 1; the first is decided disjoint and appended
        self.assertEqual(sorted((o.ex_date, o.decision) for o in report.outcomes),
                         [(f8t.EX, f8b.SplitDecision.APPENDED), (far, f8b.SplitDecision.CALENDAR_COVERAGE_GAP)])


if __name__ == "__main__":
    unittest.main()
