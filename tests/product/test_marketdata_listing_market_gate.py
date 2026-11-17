"""The admission gate is per MARKET, not per file label (technical review of the Alpha Vantage A-share route, findings M-1 and L-4).

market-data/1.15 Ruling 7A.3 item 1 and Appendix A.5: with the CN order empty, a real file supplies no reading for a CN listing.
The first build of the gate keyed on the file's `source_id`, so a real file saved under `alphavantage.us` whose symbol the identity
table maps to an XSHG listing still produced an AVAILABLE number. The rule now holds where a real observation is bound to a
listing: `profiles.listing_market_refusal` / `require_listing_market`, applied by `ingest_file`, by the store from its construction
(so the `PostgresMarketData` rebuild too), and by the PostgreSQL projection before any write and on every read.

Every file here is SYNTHETIC in content (invented numbers and codes) even where its manifest carries a REAL scope and source id to
reach the gate. The expected values are the methodology's hand-derived ones (7A-G1: 10.55 on 2026-10-08, XSHG 609999) or are
written out below from the inputs; none comes from this code's output. The PostgreSQL tests are opt-in (see
`test_postgres_market_data_store.py`) and live only inside disposable `finweb_it_md_*` schemas.
"""

import contextlib
import dataclasses
import datetime
import io
import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_cp2c1_kit as k  # noqa: E402
import pg_market_kit as pk  # noqa: E402

kit = k.kit

from domain.instrument import SecurityType  # noqa: E402
from domain.ledger import SplitRatio  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata import profiles as prof  # noqa: E402
from marketdata.adapters.alphavantage import AlphaVantageQuoteAdapter  # noqa: E402
from marketdata.adapters.base import AdapterRegistry  # noqa: E402
from marketdata.adapters.calendar_file import CalendarFileAdapter  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.canonical import sha256_hex  # noqa: E402
from marketdata.files import FileStore, VerifiedFile  # noqa: E402
from marketdata.ingest import build_in_memory_market_data, ingest_file  # noqa: E402
from marketdata.manifest import (  # noqa: E402
    DataKind,
    FileManifest,
    MarketDataRelease,
    SourceRecord,
    SourceRegistry,
    TermsCheck,
)
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.profiles import ProfileNotAdmittedError  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402
from marketdata.states import price_input_state  # noqa: E402
from marketdata.store import InMemoryMarketData, StoreContents  # noqa: E402
from marketdata_tools import download as dl  # noqa: E402
from persistence import market_data_store as mds  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
UTC = datetime.timezone.utc
FORMAT = "alphavantage_csv_daily/1"
FUNCTION = (("function", "TIME_SERIES_DAILY"), ("outputsize", "compact"))
RETRIEVED = datetime.datetime(2026, 10, 8, 8, 0, tzinfo=UTC)  # 16:00 in Shanghai, after the 2026-10-08 close
REAL = c.UsageScope.INTERNAL_DEVELOPMENT_ONLY
PERMITTING = TermsCheck("owner", D(2026, 10, 23), True, "synthetic test record of a PERMITTING terms check")
REAL_US = SourceRecord("alphavantage.us", "Alpha Vantage US", "alphavantage", "alphavantage", terms_check=PERMITTING)
REAL_CN = SourceRecord("alphavantage.cn", "Alpha Vantage CN", "alphavantage", "alphavantage", terms_check=PERMITTING)
CAL_REC = SourceRecord("calendar.manual", "calendar.manual", "calendar", "calendar", synthetic=True)

# 7A-G1's last row (hand-derived there): the 2026-10-08 close of XSHG 609999 is 10.55
CN_ROWS = [("2026-10-08", "10.3500", "10.6000", "10.2800", "10.5500", "2034500")]
# the US fixture rows of the existing US pin (test_marketdata_alphavantage_cn.UsAdapterIsUnchanged)
US_ROWS = [("2025-01-02", "100.0000", "101.5000", "99.2500", "100.5000", "1000"),
           ("2025-01-03", "100.5000", "102.0000", "100.0000", "101.2500", "1100"),
           ("2025-01-06", "101.2500", "101.7500", "100.1234", "100.7500", "900")]


def identity(cn_vendor_source="alphavantage.us"):
    """AAPL on XNAS (USD) and an invented A-share, XSHG 609999 (CNY), plus the row the reviewer's scenario needs: a vendor-id row,
    `(cn_vendor_source, 609999.SHH)`, entered by a human who registered the A-share 'for Alpha Vantage'."""
    reg = InMemoryIdentityRegistry(kit.SequentialIds())
    reg.register_instruments([
        InstrumentEntry("Apple", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", k.USD,
                        vendor_ids=(("alphavantage.us", "AAPL"),)),
        InstrumentEntry("A-share", SecurityType.COMMON_STOCK, "XSHG", "SSE", "609999", k.CNY,
                        vendor_ids=((cn_vendor_source, "609999.SHH"),)),
        InstrumentEntry("B-share-HK", SecurityType.COMMON_STOCK, "XHKG", "HKEX", "0700", k.HKD,
                        vendor_ids=(("alphavantage.us", "0700.HK"),)),
        InstrumentEntry("A-share-SZ", SecurityType.COMMON_STOCK, "XSHE", "SZSE", "009999", k.CNY,
                        vendor_ids=(("alphavantage.us", "009999.SHZ"),)),
    ])
    return reg


def manifest(source_id, symbol, currency, rows, scope=REAL, kind=DataKind.QUOTE, retrieved=RETRIEVED, tag=""):
    """`tag` makes the payload (so the file hash) unique per test; a tagged payload is for the database tests, which never parse it."""
    payload = k.av_csv(rows) + tag.encode("utf-8")
    return FileManifest(
        file_sha256=sha256_hex(payload), size_bytes=len(payload), payload_filename="q.csv", payload_format=FORMAT,
        source_id=source_id, data_kind=kind, retrieval_time=retrieved, retrieved_by="human",
        declared_adjustment=c.AdjustmentStatus.UNDECLARED, usage_scope=scope, declared_currency=currency,
        source_identifiers=(symbol,), declared_delay=c.DataDelayStatus.END_OF_DAY, request=FUNCTION), payload


def ingest(source_record, symbol, currency, rows, ident, adapter=None):
    m, payload = manifest(source_record.source_id, symbol, currency, rows)
    return ingest_file(VerifiedFile(m, payload, Path("x")), adapter or AlphaVantageQuoteAdapter(source_record.source_id),
                       ident, source_record)


class ListingMarketRule(unittest.TestCase):
    """`profiles.listing_market_refusal`: a table written from the rule (profile covers X, is admitted, upstream in PRIMARY_ORDER[X])."""

    def code(self, source, mic):
        refusal = prof.listing_market_refusal(source, mic)
        return None if refusal is None else refusal[0]

    def test_a_us_listing_of_the_us_source_is_unchanged(self):
        for mic in ("XNAS", "XNYS"):
            self.assertIsNone(prof.listing_market_refusal("alphavantage.us", mic), mic)

    def test_with_the_cn_order_empty_every_real_cn_listing_is_refused_under_any_source_id(self):
        self.assertEqual(prof.PRIMARY_ORDER["CN"], ())
        for mic in ("XSHG", "XSHE"):
            self.assertEqual(self.code("alphavantage.us", mic), prof.SOURCE_MARKET_NOT_COVERED, mic)  # the reviewer's scenario
            self.assertEqual(self.code("alphavantage.cn", mic), prof.SOURCE_PENDING_OBSERVATION, mic)  # the pending route itself
            self.assertEqual(self.code("frankfurter.ecb", mic), prof.SOURCE_MARKET_NOT_COVERED, mic)  # a source with no market at all
            self.assertEqual(self.code("akshare.cn", mic), prof.SOURCE_NOT_ADMITTED, mic)  # covers CN, but REFUSED (PD-0031/0032)
            self.assertEqual(self.code("akshare_sina.cn", mic), prof.SOURCE_MARKET_NOT_COVERED, mic)  # never profiled: it declares no market

    def test_hong_kong_is_refused_for_the_us_source_too_and_the_cn_source_does_not_cover_the_us(self):
        self.assertEqual(self.code("alphavantage.us", "XHKG"), prof.SOURCE_MARKET_NOT_COVERED)
        self.assertEqual(self.code("alphavantage.cn", "XNAS"), prof.SOURCE_MARKET_NOT_COVERED)

    def test_the_primary_order_decides_even_for_an_observed_profile_that_covers_the_market(self):
        observed = dataclasses.replace(prof.SOURCES["alphavantage.cn"], status=prof.OBSERVED)  # a hypothetical profile flip
        with mock.patch.dict(prof.SOURCES, {"alphavantage.cn": observed}):
            self.assertEqual(self.code("alphavantage.cn", "XSHG"), prof.SOURCE_NOT_IN_PRIMARY_ORDER)
            with mock.patch.dict(prof.PRIMARY_ORDER, {"CN": ("alphavantage",)}):  # only the data change an owner decision makes
                self.assertIsNone(prof.listing_market_refusal("alphavantage.cn", "XSHG"))
                self.assertEqual(self.code("alphavantage.cn", "XSHE"), None)
        with mock.patch.dict(prof.PRIMARY_ORDER, {"US": ()}):  # and the US source loses the US the same way
            self.assertEqual(self.code("alphavantage.us", "XNAS"), prof.SOURCE_NOT_IN_PRIMARY_ORDER)
        self.assertEqual(prof.PRIMARY_ORDER["CN"], ())

    def test_what_the_rule_judges_under_1_16_is_stated(self):
        # RE-RECORDED for market-data/1.16 Ruling 4.7 item 6. Before 1.16 this test pinned three gaps as "not judged here": an exchange outside the
        # MIC table (XLON), a source with no profile (no.such.source), and an unknown exchange with a profile-less source. 1.16 closes all
        # three: the rule has an order, (1) the MIC maps to a V1 market, (2) the source has a profile, (3) it covers the market, (4) it is admitted.
        refusal = prof.listing_market_refusal("alphavantage.us", "XLON")
        self.assertEqual(None if refusal is None else refusal[0], prof.LISTING_EXCHANGE_UNKNOWN)  # a MIC outside the table has no V1 market
        self.assertIn("XLON", refusal[1])  # the detail names the MIC
        self.assertIsNone(prof.listing_market_refusal("alphavantage.us", "ARCX"))  # the US venues of 1.16 map to US
        self.assertEqual(self.code("no.such.source", "XSHG"), prof.SOURCE_NOT_ADMITTED)  # a source with no profile never supplies a real reading
        self.assertEqual(self.code("no.such.source", "XNAS"), prof.SOURCE_NOT_ADMITTED)
        self.assertEqual(self.code("alphavantage.us", None), prof.LISTING_EXCHANGE_UNKNOWN)  # the market of a real reading is never assumed
        self.assertEqual(self.code("no.such.source", None), prof.LISTING_EXCHANGE_UNKNOWN)  # condition 1 comes first

    def test_require_listing_market_raises_with_the_code_and_names_source_listing_and_exchange(self):
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            prof.require_listing_market("alphavantage.us", "L-1", "XSHG")
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED)
        text = str(cm.exception)
        self.assertTrue(text.startswith("SOURCE_MARKET_NOT_COVERED: "), text)
        for part in ("alphavantage.us", "L-1", "XSHG", "covers market(s) US, not CN"):
            self.assertIn(part, text)
        prof.require_listing_market("alphavantage.us", "L-2", "XNAS")  # no exception

    def test_not_admitted_code_follows_the_order_of_not_admitted_reason(self):
        memory = dataclasses.replace(prof.SOURCES["alphavantage.us"], status=prof.MEMORY)  # MEMORY, whatever A.5 says
        self.assertEqual((memory.not_admitted_code, "MEMORY" in memory.not_admitted_reason), (prof.SOURCE_NOT_ADMITTED, True))
        pending = prof.SOURCES["alphavantage.cn"]
        self.assertEqual(pending.not_admitted_code, prof.SOURCE_PENDING_OBSERVATION)
        self.assertEqual(prof.SOURCES["akshare.cn"].not_admitted_code, prof.SOURCE_NOT_ADMITTED)


class ReviewersScenario(unittest.TestCase):
    """M-1, the reviewer's exact case: `fetch --source alphavantage_us --symbol 609999.SHH --currency CNY` saves a real file labelled
    `alphavantage.us`, and the identity table holds a vendor row (`alphavantage.us`, `609999.SHH`) pointing at an XSHG listing."""

    def test_ingest_refuses_the_file_and_names_the_market_gate(self):
        ident = identity()
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            ingest(REAL_US, "609999.SHH", k.CNY, CN_ROWS, ident)
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED)
        self.assertIn("XSHG", str(cm.exception))

    def test_the_refusal_comes_before_the_currency_check_and_holds_for_every_other_exchange(self):
        for symbol, ccy in (("609999.SHH", k.USD),  # a wrong currency declaration does not turn the refusal into a row issue
                            ("009999.SHZ", k.CNY),  # the other mainland exchange
                            ("0700.HK", k.HKD)):  # Hong Kong: no admitted source either
            with self.assertRaises(ProfileNotAdmittedError) as cm:
                ingest(REAL_US, symbol, ccy, CN_ROWS, identity())
            self.assertEqual(cm.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED, symbol)

    def test_a_real_file_that_repeats_a_date_is_refused_by_the_market_gate_just_the_same(self):
        """Review LOW-6 (mutation M6). A contradicted series is still a series of the source, and its listing's market is judged as for a reading: a real
        `alphavantage.us` file whose symbol maps to an XSHG listing (or an unmapped MIC) and that states a date twice is refused WHOLE, not quietly
        excluded and kept. Without the gate on the contradicted path the file would pass and the CN series would sit in the release as an exclusion."""
        twice = CN_ROWS + CN_ROWS
        for symbol, ccy, code in (("609999.SHH", k.CNY, prof.SOURCE_MARKET_NOT_COVERED), ("009999.SHZ", k.CNY, prof.SOURCE_MARKET_NOT_COVERED),
                                  ("0700.HK", k.HKD, prof.SOURCE_MARKET_NOT_COVERED)):
            with self.assertRaises(ProfileNotAdmittedError, msg=symbol) as cm:
                ingest(REAL_US, symbol, ccy, twice, identity())
            self.assertEqual(cm.exception.gate_code, code, symbol)
        # the control: a US listing that repeats a date is excluded, and the file is not refused
        result = ingest(REAL_US, "AAPL", k.USD, US_ROWS + US_ROWS[:1], identity())
        self.assertEqual([(e.test, e.currency) for e in result.exclusions], [("V0", None)])
        self.assertEqual(result.readings, ())

    def test_without_the_vendor_row_the_file_resolves_to_nothing_and_is_no_reading(self):
        ident = InMemoryIdentityRegistry(kit.SequentialIds())  # no listing at all
        result = ingest(REAL_US, "609999.SHH", k.CNY, CN_ROWS, ident)
        self.assertEqual(result.readings, ())
        self.assertEqual([e.status for e in result.exceptions], [c.ResolutionStatus.UNRESOLVED])

    def test_us_aapl_is_unchanged(self):
        result = ingest(REAL_US, "AAPL", k.USD, US_ROWS, identity())
        self.assertEqual([(r.observation.value_date, r.observation.price, r.observation.recovered) for r in result.readings],
                         [(D(2025, 1, 2), Decimal("100.5"), True), (D(2025, 1, 3), Decimal("101.25"), True),
                          (D(2025, 1, 6), Decimal("100.75"), True)])  # the closes of the rows above
        self.assertEqual({r.observation.listing_id for r in result.readings}, {kit.listing_id(identity(), "AAPL", "XNAS")})
        self.assertEqual((result.exceptions, [i.code for i in result.issues]), ((), []))

    def test_the_real_pending_route_is_still_refused_before_the_payload_is_read(self):
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            ingest(REAL_CN, "609999.SHH", k.CNY, CN_ROWS, identity("alphavantage.cn"))
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_PENDING_OBSERVATION)

    def test_a_synthetic_source_is_exempt_whatever_the_market(self):
        syn = SourceRecord("synthetic.alphavantage.cn", "syn", "synthetic", "synthetic", synthetic=True)
        ident = identity("synthetic.alphavantage.cn")
        m, payload = manifest("synthetic.alphavantage.cn", "609999.SHH", k.CNY, CN_ROWS, scope=c.UsageScope.SYNTHETIC_TEST)
        result = ingest_file(VerifiedFile(m, payload, Path("x")), AlphaVantageQuoteAdapter("synthetic.alphavantage.cn"), ident, syn)
        self.assertEqual([r.observation.price for r in result.readings], [Decimal("10.55")])

    def test_the_build_path_refuses_it_and_without_the_file_the_listing_has_no_admitted_source(self):
        """The whole path, with files on disk and a registry that attests the terms of `alphavantage.us`. The refused file is not in
        the version, and the CN listing then resolves as Ruling 4.7 and 7A.3 require: INSUFFICIENT_DATA + MISSING_PRICE_HISTORY,
        cause NO_ADMITTED_SOURCE (hand-derived: A.5 CN is empty, so no source is admitted for the market)."""
        for with_quote_file in (True, False):
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            root = Path(tmp.name)
            kit.write_registry(root, extra=[REAL_US, CAL_REC])
            shas = []
            if with_quote_file:
                m, payload = manifest("alphavantage.us", "609999.SHH", k.CNY, CN_ROWS)
                directory = root / "files" / "alphavantage.us" / "quote" / "2026-10-08"
                directory.mkdir(parents=True)
                (directory / "q.csv").write_bytes(payload)
                (directory / "q.csv.manifest.json").write_text(m.to_json(), encoding="utf-8")
                shas.append(m.file_sha256)
            cal = k.calendar_json("SYN_CN", "EXCHANGE_SESSIONS", ("XSHG", "XSHE"), "Asia/Shanghai",
                                  coverage=("2026-09-01", "2026-10-31"), dates=["2026-10-08", "2026-10-09"],
                                  close={"default": "15:00", "overrides": []})
            cdir = root / "files" / "calendar.manual" / "calendar" / "2026-10-08"
            cdir.mkdir(parents=True)
            cm_ = FileManifest(file_sha256=sha256_hex(cal), size_bytes=len(cal), payload_filename="cal.json",
                               payload_format="finweb_calendar_json/1", source_id="calendar.manual", data_kind=DataKind.CALENDAR,
                               retrieval_time=RETRIEVED, retrieved_by="synthetic", declared_adjustment=c.AdjustmentStatus.RAW,
                               usage_scope=c.UsageScope.SYNTHETIC_TEST, source_identifiers=("SYN_CN",),
                               declared_delay=c.DataDelayStatus.END_OF_DAY)
            (cdir / "cal.json").write_bytes(cal)
            (cdir / "cal.json.manifest.json").write_text(cm_.to_json(), encoding="utf-8")
            shas.append(cm_.file_sha256)
            files = FileStore(root)
            registry = files.load_registry()
            self.assertTrue(registry.require_attested("alphavantage.us").terms_attested)  # the terms barrier alone lets the file through
            release = MarketDataRelease(name="r", files=tuple(sorted(shas)), source_precedence=())
            ident = identity()
            adapters = AdapterRegistry([AlphaVantageQuoteAdapter("alphavantage.us"), CalendarFileAdapter()])
            if with_quote_file:
                with self.assertRaises(ProfileNotAdmittedError) as cm:
                    build_in_memory_market_data(release, files, registry, adapters, ident, catalog_calendars={})
                self.assertEqual(cm.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED)
                continue
            built = build_in_memory_market_data(release, files, registry, adapters, ident, catalog_calendars={})
            lookup = built.store.quote_on(kit.listing_id(ident, "609999", "XSHG"), D(2026, 10, 8), market11_conventions(built.calendars))
            state = price_input_state(lookup)
            self.assertEqual((lookup.outcome, lookup.selected, state.state, state.reason),
                             (LookupOutcome.NO_HISTORY, None, SufficiencyState.INSUFFICIENT_DATA, ReasonCode.MISSING_PRICE_HISTORY))
            self.assertIn("NO_ADMITTED_SOURCE: market CN", lookup.lineage_notes[0])


def real_quote(listing, source="alphavantage.us", group="alphavantage", sha=None, ccy=k.CNY, price="10.55", day=D(2026, 10, 8)):
    return k.quote_reading(day, price, source=source, group=group, sha=sha or k.SHA, listing=listing, usage=REAL, ccy=ccy)


class StoreGate(unittest.TestCase):
    """The store holds the gate from its construction, so `quote_on`, `quotes`, `corporate_actions` and `adjusted_series` cannot
    serve what it refuses, however the store was built (by hand, or rebuilt from stored rows)."""

    def setUp(self):
        self.ident = identity()
        self.cn = kit.listing_id(self.ident, "609999", "XSHG")
        self.aapl = kit.listing_id(self.ident, "AAPL", "XNAS")

    def test_the_reviewers_store_probe_is_refused_at_construction(self):
        # the reviewer built exactly this in memory and got `quote_on` = FOUND, 10.55, AVAILABLE
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            InMemoryMarketData(k.RELEASE, [real_quote(self.cn)], exchange_of=self.ident.exchange_mic, source_records=[REAL_US])
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED)

    def test_a_us_listing_of_the_us_source_builds_and_serves(self):
        store = InMemoryMarketData(k.RELEASE, [real_quote(self.aapl, ccy=k.USD, price="100.50", day=D(2025, 1, 2))],
                                   exchange_of=self.ident.exchange_mic, source_records=[REAL_US])
        self.assertEqual([r.source_id for r in store.source_registry_records()], ["alphavantage.us"])
        self.assertEqual([r.observation.price for r in store.quotes(self.aapl, D(2025, 1, 1), D(2025, 1, 31)).readings], [Decimal("100.50")])

    def test_a_corporate_action_and_an_adjusted_row_are_gated_like_a_quote(self):
        timing = c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY)
        lineage = k.lineage("alphavantage.us", k.SHA, usage=REAL)
        split = c.SourceReading("alphavantage.us", "alphavantage", k.SHA, c.CorporateActionObservation(
            self.cn, c.CorporateActionType.SPLIT, D(2026, 10, 8), timing, lineage, split_ratio=SplitRatio(Decimal(2), Decimal(1))))
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            InMemoryMarketData(k.RELEASE, [split], exchange_of=self.ident.exchange_mic, source_records=[REAL_US])
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED)
        adjusted = c.AdjustedQuote(
            self.cn, D(2026, 10, 8), Decimal("10.3"), Decimal("10.6"), Decimal("10.2"), Decimal("10.5"), k.CNY,
            c.AdjustmentLabel(c.AdjustmentStatus.DIVIDEND_ADJUSTED, c.AdjustmentMethod.SUBTRACTIVE, c.AnchorKind.LATEST, k.NOW),
            timing, k.lineage("alphavantage.us", k.SHA, adjustment=c.AdjustmentStatus.DIVIDEND_ADJUSTED, usage=REAL),
            Decimal("0.005"), (Decimal("0.00005"),) * 3)
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            InMemoryMarketData(k.RELEASE, [], adjusted=[adjusted], exchange_of=self.ident.exchange_mic, source_records=[REAL_US])
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED)

    def test_without_an_identity_the_market_of_a_real_reading_of_a_profiled_source_is_not_assumed(self):
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            InMemoryMarketData(k.RELEASE, [real_quote(self.cn)], source_records=[REAL_US])  # no exchange_of
        self.assertEqual(cm.exception.gate_code, prof.LISTING_EXCHANGE_UNKNOWN)
        # market-data/1.16 Ruling 4.7 item 6 (re-recorded: before 1.16 a made-up source id "made no coverage claim" and such hand-built stores
        # were unchanged): a real reading of a source with no profile is refused, SOURCE_NOT_ADMITTED, once its listing's exchange is known
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            InMemoryMarketData(k.RELEASE, [real_quote(self.aapl, ccy=k.USD, price="100.50", day=D(2025, 1, 2), source="test.feed", group="test.feed")],
                               exchange_of=self.ident.exchange_mic,
                               source_records=k.records_for([real_quote(self.aapl, ccy=k.USD, price="100.50", day=D(2025, 1, 2), source="test.feed", group="test.feed")]))
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_NOT_ADMITTED)

    def test_a_synthetic_reading_is_exempt_whatever_its_market(self):
        syn = k.quote_reading(D(2026, 10, 8), "10.55", source="synthetic.alphavantage.cn", group="synthetic", listing=self.cn, ccy=k.CNY)
        store = InMemoryMarketData(k.RELEASE, [syn], exchange_of=self.ident.exchange_mic, source_records=k.records_for([syn]))
        self.assertTrue(store.contains_synthetic)

    def test_the_pending_source_is_refused_on_its_own_market_with_its_own_code(self):
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            InMemoryMarketData(k.RELEASE, [real_quote(self.cn, source="alphavantage.cn")], exchange_of=self.ident.exchange_mic,
                               source_records=[REAL_CN])
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_PENDING_OBSERVATION)


class Item27PerReadingGateTests(unittest.TestCase):
    """market-data/1.16 section 11 item 27 (the part outside `src/persistence/`): Ruling 4.7 item 6, the per-reading form of A.5, at ingest and in the
    store's constructor. Expected values are written out from the Ruling's table and its order of conditions (1: the MIC maps to a V1 market; 2: the
    source has a profile; 3: it covers the market; 4: it is admitted and its upstream is in A.5), not from this code's output. The gate labels are
    admission refusals: they never reach a ReasonCode."""

    def setUp(self):
        self.reg = InMemoryIdentityRegistry(kit.SequentialIds())
        self.reg.register_instruments([
            InstrumentEntry("Apple", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", k.USD, vendor_ids=(("alphavantage.us", "AAPL"),)),
            InstrumentEntry("An Arca ETF", SecurityType.ETF, "ARCX", "NYSE Arca", "SPYX", k.USD, vendor_ids=(("alphavantage.us", "SPYX"),)),
            InstrumentEntry("A Beijing share", SecurityType.COMMON_STOCK, "BJSE", "BSE", "430047", k.CNY, vendor_ids=(("alphavantage.us", "430047.BJ"),)),
            InstrumentEntry("A Stock Connect share", SecurityType.COMMON_STOCK, "XSSC", "SSE Connect", "600999", k.CNY, vendor_ids=(("alphavantage.us", "600999.SC"),)),
            InstrumentEntry("An A-share", SecurityType.COMMON_STOCK, "XSHG", "SSE", "609999", k.CNY, vendor_ids=(("alphavantage.cn", "609999.SHH"),)),
        ])
        self.listing = {t: kit.listing_id(self.reg, t, m) for t, m in
                        (("AAPL", "XNAS"), ("SPYX", "ARCX"), ("430047", "BJSE"), ("600999", "XSSC"), ("609999", "XSHG"))}

    # --- the table -----------------------------------------------------------------------------------------------------------------

    def test_the_mic_table_and_the_zones_are_the_rulings(self):
        for mic in ("XNYS", "XNAS", "ARCX", "BATS", "XASE"):
            self.assertEqual(prof.market_of_mic(mic), "US", mic)
        self.assertEqual([prof.market_of_mic(m) for m in ("XHKG", "XSHG", "XSHE")], ["HK", "CN", "CN"])
        for mic in ("BJSE", "XSSC", "XLON", "xnas", "", None):
            self.assertIsNone(prof.market_of_mic(mic), mic)  # any other MIC has no V1 market
        for mic in ("ARCX", "BATS", "XASE"):
            self.assertEqual(prof.EXCHANGE_ZONES[mic], "America/New_York", mic)  # Ruling 2.2 item 1 (1.16)
        for mic in ("BJSE", "XSSC"):
            self.assertNotIn(mic, prof.EXCHANGE_ZONES, mic)  # no other MIC has a zone

    def test_the_rule_applies_its_conditions_in_the_rulings_order_and_the_labels_are_not_reason_codes(self):
        code = lambda source, mic: (prof.listing_market_refusal(source, mic) or (None,))[0]  # noqa: E731
        self.assertEqual(code("alphavantage.us", "BJSE"), prof.LISTING_EXCHANGE_UNKNOWN)  # 1: an unmapped MIC
        self.assertEqual(code("alphavantage.cn", "BJSE"), prof.LISTING_EXCHANGE_UNKNOWN)  # ... before the source's own pending state
        self.assertEqual(code("no.such.source", "BJSE"), prof.LISTING_EXCHANGE_UNKNOWN)  # ... and before the missing profile
        self.assertEqual(code("no.such.source", "XNAS"), prof.SOURCE_NOT_ADMITTED)  # 2: a source with no profile
        self.assertEqual(code("no.such.source", "XSHG"), prof.SOURCE_NOT_ADMITTED)
        self.assertEqual(code("alphavantage.us", "XSHG"), prof.SOURCE_MARKET_NOT_COVERED)  # 3
        self.assertEqual(code("alphavantage.cn", "XSHG"), prof.SOURCE_PENDING_OBSERVATION)  # 4
        for mic in ("XNYS", "XNAS", "ARCX", "BATS", "XASE"):
            self.assertIsNone(prof.listing_market_refusal("alphavantage.us", mic), mic)
        refusal = prof.listing_market_refusal("alphavantage.us", "BJSE")
        self.assertIn("BJSE", refusal[1])  # the detail names the MIC
        labels = {prof.SOURCE_NOT_ADMITTED, prof.SOURCE_PENDING_OBSERVATION, prof.SOURCE_NOT_IN_PRIMARY_ORDER, prof.SOURCE_MARKET_NOT_COVERED,
                  prof.LISTING_EXCHANGE_UNKNOWN}
        self.assertEqual(len(labels), 5)
        self.assertEqual(labels & {r.value for r in ReasonCode}, set())

    # --- ingest ----------------------------------------------------------------------------------------------------------------------

    def test_ingest_refuses_a_real_file_whose_symbol_resolves_to_a_listing_on_an_unmapped_mic(self):
        for symbol, mic in (("430047.BJ", "BJSE"), ("600999.SC", "XSSC")):
            with self.assertRaises(ProfileNotAdmittedError, msg=mic) as cm:
                ingest(REAL_US, symbol, k.CNY, CN_ROWS, self.reg)
            self.assertEqual(cm.exception.gate_code, prof.LISTING_EXCHANGE_UNKNOWN, mic)
            self.assertIn(mic, str(cm.exception))

    def test_an_arca_listing_passes_the_gate_for_the_us_source_and_stays_freshness_unknown_under_the_registered_nyse_calendar(self):
        arca = ingest(REAL_US, "SPYX", k.USD, US_ROWS, self.reg)
        aapl = ingest(REAL_US, "AAPL", k.USD, US_ROWS, self.reg)
        self.assertEqual((len(arca.readings), len(aapl.readings)), (3, 3))  # not refused
        nyse = k.exchange_calendar("NYSE_SESSIONS", ("XNYS", "XNAS"), [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)], covers=(D(2025, 1, 1), D(2025, 1, 31)))
        conv = market11_conventions(CalendarSet([nyse]))
        store = InMemoryMarketData(k.RELEASE, list(arca.readings) + list(aapl.readings), exchange_of=self.reg.exchange_mic, source_records=[REAL_US])
        on_nasdaq = store.quote_on(self.listing["AAPL"], D(2025, 1, 6), conv)
        on_arca = store.quote_on(self.listing["SPYX"], D(2025, 1, 6), conv)
        self.assertEqual(on_nasdaq.freshness.state, c.FreshnessState.CURRENT)  # the calendar governs XNAS
        self.assertEqual(on_arca.freshness.state, c.FreshnessState.UNKNOWN)  # and does not name ARCX (Ruling 2.2 item 1)
        self.assertEqual(price_input_state(on_nasdaq).state, SufficiencyState.AVAILABLE)
        self.assertNotEqual(price_input_state(on_arca).state, SufficiencyState.AVAILABLE)

    # --- the store's constructor ----------------------------------------------------------------------------------------------------

    def split(self, source, listing, usage=REAL):
        lineage = k.lineage(source, k.SHA, usage=usage)
        return c.SourceReading(source, source, k.SHA, c.CorporateActionObservation(
            listing, c.CorporateActionType.SPLIT, D(2026, 10, 8), c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY), lineage,
            split_ratio=SplitRatio(Decimal(2), Decimal(1))))

    def adjusted(self, source, listing, usage=REAL):
        return c.AdjustedQuote(
            listing, D(2026, 10, 8), Decimal("10.3"), Decimal("10.6"), Decimal("10.2"), Decimal("10.5"), k.USD,
            c.AdjustmentLabel(c.AdjustmentStatus.DIVIDEND_ADJUSTED, c.AdjustmentMethod.SUBTRACTIVE, c.AnchorKind.LATEST, k.NOW),
            c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY),
            k.lineage(source, k.SHA, adjustment=c.AdjustmentStatus.DIVIDEND_ADJUSTED, usage=usage), Decimal("0.005"), (Decimal("0.00005"),) * 3)

    def build(self, readings=(), adjusted=()):
        records = k.records_for(list(readings)) + [
            SourceRecord(a.lineage.source_id, a.lineage.source_id, "x", a.lineage.source_id, synthetic=bool(a.lineage.is_synthetic)) for a in adjusted]
        return InMemoryMarketData(k.RELEASE, list(readings), adjusted=list(adjusted), exchange_of=self.reg.exchange_mic, source_records=records)

    def refused(self, **kw):
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            self.build(**kw)
        return cm.exception.gate_code

    def test_the_constructor_refuses_a_real_record_of_a_pending_source_on_its_own_market_and_of_a_refused_source(self):
        self.assertEqual(self.refused(readings=[self.split("alphavantage.cn", self.listing["609999"])]), prof.SOURCE_PENDING_OBSERVATION)
        self.assertEqual(self.refused(readings=[self.split("akshare.cn", self.listing["609999"])]), prof.SOURCE_NOT_ADMITTED)  # REFUSED (PD-0031/0032)

    def test_the_constructor_refuses_a_real_reading_of_a_source_with_no_profile_whatever_its_kind(self):
        aapl = self.listing["AAPL"]
        self.assertEqual(self.refused(readings=[real_quote(aapl, source="openfigi", group="openfigi", ccy=k.USD, price="100.50", day=D(2025, 1, 2))]),
                         prof.SOURCE_NOT_ADMITTED)  # OpenFIGI is an identity source, not a price source (review R-2)
        self.assertEqual(self.refused(readings=[self.split("test.filing", aapl)]), prof.SOURCE_NOT_ADMITTED)  # a filing source with no filing profile
        self.assertEqual(self.refused(adjusted=[self.adjusted("test.feed", aapl)]), prof.SOURCE_NOT_ADMITTED)  # the TS-1 arm: adjusted rows

    def test_the_constructor_refuses_a_real_reading_bound_to_an_unmapped_mic_even_for_an_admitted_source(self):
        bjse = self.listing["430047"]
        self.assertEqual(self.refused(readings=[real_quote(bjse, ccy=k.CNY)]), prof.LISTING_EXCHANGE_UNKNOWN)
        self.assertEqual(self.refused(readings=[self.split("alphavantage.us", self.listing["600999"])]), prof.LISTING_EXCHANGE_UNKNOWN)
        self.assertEqual(self.refused(adjusted=[self.adjusted("alphavantage.us", bjse)]), prof.LISTING_EXCHANGE_UNKNOWN)

    def test_a_synthetic_reading_is_exempt_from_the_profile_and_the_mic_conditions(self):
        syn = [k.quote_reading(D(2025, 1, 2), "10.55", source="test.feed", group="test.feed", listing=self.listing["430047"], ccy=k.CNY),
               self.split("test.filing", self.listing["600999"], usage=c.UsageScope.SYNTHETIC_TEST)]
        self.assertTrue(self.build(readings=syn, adjusted=[self.adjusted("test.feed", self.listing["430047"], usage=c.UsageScope.SYNTHETIC_TEST)]).contains_synthetic)


class _NoDatabase:
    """A connection that fails the test if anything touches it: a refusal must come before the first statement."""

    def __getattr__(self, name):
        raise AssertionError(f"the database was touched ({name}): the gate must refuse before any write")


class WriteGate(unittest.TestCase):
    """L-4: `write_release` refuses a REAL file or reading the read gate would refuse, before anything is written (the tables are
    append-only, so a stored row could never be removed again)."""

    def release_of(self, source, symbol, ccy, readings, scope=REAL):
        m, _payload = manifest(source, symbol, ccy, CN_ROWS, scope=scope)
        release = MarketDataRelease(name="w", files=(m.file_sha256,), source_precedence=())
        contents = StoreContents(tuple(readings), (), (), (), (), False, ())
        return release, [m], contents

    def test_a_real_file_of_the_pending_source_is_refused_before_the_first_statement(self):
        release, manifests, contents = self.release_of("alphavantage.cn", "609999.SHH", k.CNY, [])
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            mds.write_release(_NoDatabase(), release, manifests, contents, CalendarSet())
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_PENDING_OBSERVATION)
        self.assertIn("nothing is written", str(cm.exception))

    def test_a_real_reading_of_a_cn_listing_under_the_us_source_is_refused_when_the_identity_is_supplied(self):
        ident = identity()
        cn = kit.listing_id(ident, "609999", "XSHG")
        sha = manifest("alphavantage.us", "609999.SHH", k.CNY, CN_ROWS)[0].file_sha256
        release, manifests, contents = self.release_of("alphavantage.us", "609999.SHH", k.CNY, [real_quote(cn, sha=sha)])
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            mds.write_release(_NoDatabase(), release, manifests, contents, CalendarSet(), exchange_of=ident.exchange_mic)
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED)

    def test_1_16_a_real_reading_of_a_source_with_no_profile_is_refused_with_or_without_an_identity(self):
        # market-data/1.16 item 27 (persistence half): the profile condition needs no identity, so it is judged even when `exchange_of` is not supplied
        ident = identity()
        aapl = kit.listing_id(ident, "AAPL", "XNAS")
        sha = manifest("alphavantage.us", "AAPL", k.USD, US_ROWS)[0].file_sha256
        for exchange_of in (None, ident.exchange_mic):
            for reading in (real_quote(aapl, source="test.feed", group="test.feed", sha=sha, ccy=k.USD, price="100.50", day=D(2025, 1, 2)),
                            c.SourceReading("test.filing", "test.filing", sha, c.CorporateActionObservation(
                                aapl, c.CorporateActionType.SPLIT, D(2026, 10, 8), c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY),
                                k.lineage("test.filing", sha, usage=REAL), split_ratio=SplitRatio(Decimal(2), Decimal(1))))):
                release, manifests, contents = self.release_of("alphavantage.us", "AAPL", k.USD, [reading])
                with self.assertRaises(ProfileNotAdmittedError, msg=(exchange_of, reading.source_id)) as cm:
                    mds.write_release(_NoDatabase(), release, manifests, contents, CalendarSet(), exchange_of=exchange_of)
                self.assertEqual(cm.exception.gate_code, prof.SOURCE_NOT_ADMITTED)
                self.assertIn("nothing is written", str(cm.exception))

    def test_1_16_a_real_adjusted_row_of_a_source_with_no_profile_is_refused_with_or_without_an_identity(self):
        """Review LOW-6 (mutation M4): the profile-less check on ADJUSTED rows had no test, and `write_release(..., exchange_of=None)` (how the real loader calls
        it) would have stored a real adjusted row of a made-up source in the append-only tables. Item 27 names the adjusted rows (a verification-only row is a
        reading of the source too). The control is a profiled source's adjusted row, which passes the source-level gate and reaches the (absent) database."""
        ident = identity()
        aapl = kit.listing_id(ident, "AAPL", "XNAS")
        sha = manifest("alphavantage.us", "AAPL", k.USD, US_ROWS)[0].file_sha256

        def adjusted(source):
            return c.AdjustedQuote(
                aapl, D(2025, 1, 2), Decimal("10.3"), Decimal("10.6"), Decimal("10.2"), Decimal("10.5"), k.USD,
                c.AdjustmentLabel(c.AdjustmentStatus.DIVIDEND_ADJUSTED, c.AdjustmentMethod.SUBTRACTIVE, c.AnchorKind.LATEST, k.NOW),
                c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY),
                k.lineage(source, sha, adjustment=c.AdjustmentStatus.DIVIDEND_ADJUSTED, usage=REAL), Decimal("0.005"), (Decimal("0.00005"),) * 3)

        m, _payload = manifest("alphavantage.us", "AAPL", k.USD, US_ROWS)
        release = MarketDataRelease(name="w", files=(m.file_sha256,), source_precedence=())
        for exchange_of in (None, ident.exchange_mic):
            contents = StoreContents((), (), (adjusted("test.feed"),), (), (), False, ())
            with self.assertRaises(ProfileNotAdmittedError, msg=exchange_of) as cm:
                mds.write_release(_NoDatabase(), release, [m], contents, CalendarSet(), exchange_of=exchange_of)
            self.assertEqual(cm.exception.gate_code, prof.SOURCE_NOT_ADMITTED)
            self.assertIn("nothing is written", str(cm.exception))
        control = StoreContents((), (), (adjusted("alphavantage.us"),), (), (), False, ())
        with self.assertRaises(AssertionError) as cm:  # a profiled source passes the gate and reaches the (absent) database
            mds.write_release(_NoDatabase(), release, [m], control, CalendarSet())
        self.assertIn("the database was touched", str(cm.exception))

    def test_1_16_an_unmapped_mic_is_refused_before_the_first_statement(self):
        ident = InMemoryIdentityRegistry(kit.SequentialIds())
        ident.register_instruments([InstrumentEntry("A Beijing share", SecurityType.COMMON_STOCK, "BJSE", "BSE", "430047", k.CNY)])
        bjse = kit.listing_id(ident, "430047", "BJSE")
        sha = manifest("alphavantage.us", "430047.BJ", k.CNY, CN_ROWS)[0].file_sha256
        release, manifests, contents = self.release_of("alphavantage.us", "430047.BJ", k.CNY, [real_quote(bjse, sha=sha)])
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            mds.write_release(_NoDatabase(), release, manifests, contents, CalendarSet(), exchange_of=ident.exchange_mic)
        self.assertEqual(cm.exception.gate_code, prof.LISTING_EXCHANGE_UNKNOWN)
        self.assertIn("BJSE", str(cm.exception))

    def test_a_synthetic_file_of_the_same_label_is_not_gated(self):
        release, manifests, contents = self.release_of("alphavantage.cn", "609999.SHH", k.CNY, [], scope=c.UsageScope.SYNTHETIC_TEST)
        with self.assertRaises(AssertionError) as cm:  # it passes the gate and reaches the (absent) database
            mds.write_release(_NoDatabase(), release, manifests, contents, CalendarSet())
        self.assertIn("the database was touched", str(cm.exception))


_SKIP = pk.skip_reason()


@unittest.skipIf(bool(_SKIP), _SKIP)
class ReadGatePostgreSQL(unittest.TestCase):
    """L-4 on a real server, in a disposable schema: `read_release` as the application role refuses what the gate refuses, whatever
    the registry's terms check says. Rows enter by `write_release` (the owner role), the only way into the tables."""

    @classmethod
    def setUpClass(cls):
        cls.db = pk.PgSchema().open()  # migrated, granted to the app role
        cls.addClassCleanup(cls.db.close)
        cls.ident = identity()
        pk.insert_identity(cls.db.owner, cls.ident)
        cls.cn = kit.listing_id(cls.ident, "609999", "XSHG")
        cls.aapl = kit.listing_id(cls.ident, "AAPL", "XNAS")
        cls.registry = SourceRegistry([REAL_US, REAL_CN])
        cls.app = cls.db.app_connection()  # the application role, under the production grants
        cls.addClassCleanup(cls.app.close)

    def project(self, source, symbol, ccy, readings, name, exchange_of=None):
        m, _payload = manifest(source, symbol, ccy, CN_ROWS, tag=name)
        release = MarketDataRelease(name=name, files=(m.file_sha256,), source_precedence=())
        contents = StoreContents(tuple(readings), (), (), (), (), False, ())
        mds.write_release(self.db.owner, release, [m], contents, CalendarSet(), exchange_of=exchange_of)
        return release, m

    def rows_of(self, release_id):
        return self.db.owner.execute("SELECT count(*) FROM md_release WHERE release_id = %s", (release_id,)).fetchone()[0]

    def test_a_us_labelled_cn_reading_is_refused_on_read_and_never_written_when_the_identity_is_supplied(self):
        m, _payload = manifest("alphavantage.us", "609999.SHH", k.CNY, CN_ROWS, tag="m1")
        reading = real_quote(self.cn, sha=m.file_sha256)
        release = MarketDataRelease(name="m1", files=(m.file_sha256,), source_precedence=())
        contents = StoreContents((reading,), (), (), (), (), False, ())
        with self.assertRaises(ProfileNotAdmittedError) as cm:  # (1) with the identity, nothing reaches the tables
            mds.write_release(self.db.owner, release, [m], contents, CalendarSet(), exchange_of=self.ident.exchange_mic)
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED)
        self.assertEqual(self.rows_of(release.release_id), 0)
        # (2) `write_release` without an identity cannot see the market; this is how such rows could be stored at all ...
        mds.write_release(self.db.owner, release, [m], contents, CalendarSet())
        self.assertEqual(self.rows_of(release.release_id), 1)
        # ... and `read_release` is the last gate: with the identity the market is known and the rows are refused
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            mds.read_release(self.app, release.release_id, self.ident.exchange_mic, registry=self.registry)
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED)
        # without it the market of a real reading is not assumed either
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            mds.read_release(self.app, release.release_id, registry=self.registry)
        self.assertEqual(cm.exception.gate_code, prof.LISTING_EXCHANGE_UNKNOWN)

    def test_a_real_us_listing_of_the_us_source_is_written_and_read_as_before(self):
        m, _payload = manifest("alphavantage.us", "AAPL", k.USD, US_ROWS, tag="us-control")
        reading = real_quote(self.aapl, sha=m.file_sha256, ccy=k.USD, price="100.50", day=D(2025, 1, 2))
        release = MarketDataRelease(name="us-control", files=(m.file_sha256,), source_precedence=())
        contents = StoreContents((reading,), (), (), (), (), False, ())
        mds.write_release(self.db.owner, release, [m], contents, CalendarSet(), exchange_of=self.ident.exchange_mic)
        store = mds.read_release(self.app, release.release_id, self.ident.exchange_mic, registry=self.registry)
        self.assertEqual([r.observation.price for r in store.quotes(self.aapl, D(2025, 1, 1), D(2025, 1, 31)).readings], [Decimal("100.50")])
        self.assertEqual([r.source_id for r in store.source_registry_records()], ["alphavantage.us"])

    def test_the_source_level_read_gate_alone_refuses_a_stored_real_file_of_the_pending_source(self):
        """The release holds ONE real `alphavantage.cn` file and no reading, so the store rebuild has nothing to gate: only the
        source-level gate of `read_release` can refuse it (a dropped block or a wrong scope string would leave it readable).
        The rows are written while an owner admission is SIMULATED (profile OBSERVED and A.5 CN opened, both patched), the only
        way a pending source's file can be stored; the patches end, and the pending profile is back when the release is read."""
        observed = dataclasses.replace(prof.SOURCES["alphavantage.cn"], status=prof.OBSERVED)
        with mock.patch.dict(prof.SOURCES, {"alphavantage.cn": observed}), mock.patch.dict(prof.PRIMARY_ORDER, {"CN": ("alphavantage",)}):
            release, _m = self.project("alphavantage.cn", "609999.SHH", k.CNY, [], "l4", exchange_of=self.ident.exchange_mic)
        self.assertEqual(self.rows_of(release.release_id), 1)
        self.assertEqual(prof.SOURCES["alphavantage.cn"].status, prof.TO_OBSERVE)
        self.assertTrue(self.registry.require_attested("alphavantage.cn").terms_attested)  # the terms barrier passes
        for exchange_of in (self.ident.exchange_mic, None):
            with self.assertRaises(ProfileNotAdmittedError) as cm:
                mds.read_release(self.app, release.release_id, exchange_of, registry=self.registry)
            self.assertEqual(cm.exception.gate_code, prof.SOURCE_PENDING_OBSERVATION)
            self.assertIn(release.release_id, str(cm.exception))

    def test_a_synthetic_scope_file_of_a_real_looking_label_is_not_gated_on_read(self):
        syn = SourceRecord("alphavantage.cn", "synthetic stand-in", "synthetic", "synthetic", synthetic=True)
        m, _payload = manifest("alphavantage.cn", "609999.SHH", k.CNY, CN_ROWS, scope=c.UsageScope.SYNTHETIC_TEST, tag="syn")
        release = MarketDataRelease(name="syn", files=(m.file_sha256,), source_precedence=())
        mds.write_release(self.db.owner, release, [m], StoreContents((), (), (), (), (), True, ()), CalendarSet())
        store = mds.read_release(self.app, release.release_id, self.ident.exchange_mic, registry=SourceRegistry([syn]))
        self.assertTrue(store.contains_synthetic)


class DownloadToolUsSymbolForm(unittest.TestCase):
    """M-1, download tool: the US Alpha Vantage source takes US symbols only. Nothing reaches the network in these tests."""

    US = ("AAPL", "aapl", "MSFT", "BRK.B", "BF-B", "GOOGL", "A", "T")
    NOT_US = ("609999.SHH", "000001.SHZ", "0700.HK", "609999", "600519", "AAPL.HK", "BRK.AB", "AAPL.LON", "", " AAPL", "AAPL ", "AAPL\n",
              "６09999", "A" * 8, "-AAPL", "AAPL.", ".HK")

    def test_the_symbol_forms(self):
        for symbol in self.US:
            self.assertIsNone(dl.us_symbol_refusal((symbol,)), symbol)
        for symbol in self.NOT_US:
            reason = dl.us_symbol_refusal((symbol,))
            self.assertIsNotNone(reason, repr(symbol))
            self.assertIn("not a US symbol form", reason)
        self.assertIsNotNone(dl.us_symbol_refusal(("AAPL", "609999.SHH")))  # one bad symbol among good ones
        self.assertIsNotNone(dl.us_symbol_refusal(("AAPL",), market="CN"))
        self.assertIsNone(dl.us_symbol_refusal(("AAPL",), market=None))

    def test_fetch_refuses_a_non_us_symbol_before_the_key_is_read_and_before_any_request(self):
        for symbol in ("609999.SHH", "000001.SHZ", "0700.HK"):
            with mock.patch.object(dl, "_http", side_effect=AssertionError("network!")), \
                    mock.patch.object(dl.urllib.request, "urlopen", side_effect=AssertionError("network!")):
                with self.assertRaises(dl.FetchError) as cm:  # the environment holds no key: the symbol check comes first
                    dl.fetch_alphavantage(symbol, k.CNY, {})
            self.assertIn("not a US symbol form", str(cm.exception), symbol)
            self.assertNotIn("FINWEB_ALPHAVANTAGE_KEY", str(cm.exception), symbol)

    def test_fetch_of_a_us_symbol_still_works(self):
        body = b"timestamp,open,high,low,close,volume\n2025-01-02,100.0000,101.0000,99.0000,100.5000,10\n"
        with mock.patch.object(dl, "_http", return_value=body):
            fetched = dl.fetch_alphavantage("AAPL", k.USD, {"FINWEB_ALPHAVANTAGE_KEY": "x" * 8})
        self.assertEqual((fetched.source_id, fetched.market, fetched.source_identifiers), ("alphavantage.us", "US", ("AAPL",)))

    def test_run_fetch_exits_2_through_main_and_saves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SOURCES.json").write_text(
                '{"sources":[{"source_id":"alphavantage.us","name":"x","upstream_provider":"x","independence_group":"x",'
                '"terms_check":{"checked_by":"owner","checked_on":"2026-10-01","permits_internal_development_use":true}}]}',
                encoding="utf-8")
            env = {dl.HUMAN_ENV: "1", "FINWEB_MARKETDATA_DIR": tmp, "FINWEB_ALPHAVANTAGE_KEY": "x" * 8}
            err = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys.stdin, "isatty", return_value=True), \
                    contextlib.redirect_stderr(err), \
                    mock.patch.object(dl.urllib.request, "urlopen", side_effect=AssertionError("network!")):
                code = dl.main(["fetch", "--source", "alphavantage_us", "--symbol", "609999.SHH", "--currency", "CNY"])
            self.assertEqual(code, 2)
            self.assertIn("not a US symbol form", err.getvalue())
            self.assertEqual(FileStore(root).manifest_paths(), [])

    def test_register_file_refuses_a_non_us_label_under_the_us_source_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "hand.csv"
            source.write_bytes(k.av_csv(CN_ROWS))
            env = {dl.HUMAN_ENV: "1", "FINWEB_MARKETDATA_DIR": tmp}
            base = ["register-file", "--path", str(source), "--source", "alphavantage.us", "--kind", "QUOTE", "--format", FORMAT,
                    "--adjustment", "UNDECLARED", "--currency", "CNY"]
            for extra in (["--label", "a", "--identifiers", "609999.SHH"],
                          ["--label", "b", "--identifiers", "AAPL", "--market", "CN"]):
                err = io.StringIO()
                with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys.stdin, "isatty", return_value=True), \
                        contextlib.redirect_stderr(err):
                    code = dl.main(base + extra)
                self.assertEqual(code, 2, extra)
                self.assertIn("nothing saved", err.getvalue(), extra)
                self.assertEqual(FileStore(root).manifest_paths(), [], extra)
            # a US file registered by hand still works, and so does a hand-made file of any other source
            out = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys.stdin, "isatty", return_value=True), \
                    contextlib.redirect_stdout(out):
                self.assertEqual(dl.main(base + ["--label", "c", "--identifiers", "AAPL", "--market", "US"]), 0)
                self.assertEqual(dl.main(["register-file", "--path", str(source), "--source", "alphavantage.cn", "--kind", "QUOTE",
                                          "--format", FORMAT, "--adjustment", "UNDECLARED", "--currency", "CNY", "--label", "d",
                                          "--identifiers", "609999.SHH"]), 0)
            self.assertEqual(len(FileStore(root).manifest_paths()), 2)


if __name__ == "__main__":
    unittest.main()
