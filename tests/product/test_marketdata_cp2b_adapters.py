"""CP2b adapters for the shapes saved by the human probe runs: Sina HK/US quotes, Frankfurter
(ECB) FX, OpenFIGI identity, and the precision-profile data. Every fixture is SYNTHETIC: invented
numbers in the exact structure of the real files, which are never committed or read here."""

import datetime
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_testkit as kit  # noqa: E402

from domain.instrument import SecurityType  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata.adapters.base import AdapterRegistry, IssueCode  # noqa: E402
from marketdata.adapters.frankfurter import PAYLOAD_FORMAT as FX_FORMAT, SOURCE_ID as FX_SOURCE, FrankfurterFxAdapter  # noqa: E402
from marketdata.adapters.openfigi import PAYLOAD_FORMAT as FIGI_FORMAT, SOURCE_ID as FIGI_SOURCE, OpenFigiIdentityAdapter  # noqa: E402
from marketdata.conventions import placeholder_conventions  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, MarketDataRelease, SourceRecord  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402


def manifest(source, kind, fmt, symbols=(), currency=None, adjustment=c.AdjustmentStatus.RAW):
    return kit.FileManifest(
        file_sha256="d" * 64, size_bytes=1, payload_filename="x", payload_format=fmt, source_id=source,
        data_kind=kind, retrieval_time=kit.RETRIEVED, retrieved_by="synthetic", declared_adjustment=adjustment,
        usage_scope=c.UsageScope.SYNTHETIC_TEST, declared_currency=currency, source_identifiers=symbols,
        declared_delay=c.DataDelayStatus.END_OF_DAY)


FX_JSON = ('{"amount":1.0,"base":"EUR","start_date":"2025-01-02","end_date":"2025-07-01","rates":'
           '{"2025-01-02":{"CNY":7.5,"HKD":8.0,"USD":1.0321},"2025-07-01":{"CNY":8.25,"HKD":9.1,"USD":1.1}}}')


class FrankfurterTests(unittest.TestCase):
    def translate(self, text):
        return FrankfurterFxAdapter().translate(manifest(FX_SOURCE, DataKind.FX, FX_FORMAT), text.encode())

    def test_quotes_are_eur_based_exact_and_dated_by_the_payload(self):
        out = self.translate(FX_JSON)
        self.assertEqual(out.issues, ())
        self.assertEqual(len(out.fx), 6)
        self.assertTrue(all(o.base_currency == kit.EUR for o in out.fx))
        usd = next(o for o in out.fx if o.quote_currency == kit.USD and o.value_date == datetime.date(2025, 1, 2))
        self.assertEqual(usd.rate, Decimal("1.0321"))
        self.assertEqual(usd.lineage.source_value_text, "1.0321")
        self.assertEqual(usd.rate_basis, "ECB euro reference rate (EUR-based, as published)")
        self.assertTrue(usd.lineage.is_complete)

    def test_the_fixing_instant_is_1410_europe_berlin_not_a_fixed_offset(self):
        # market-data/1.8: 14:10 (14:15 through 1.7). CET is UTC+1 in January (13:10 UTC), CEST UTC+2 in July (12:10 UTC).
        out = self.translate(FX_JSON)
        winter = next(o for o in out.fx if o.value_date == datetime.date(2025, 1, 2))
        summer = next(o for o in out.fx if o.value_date == datetime.date(2025, 7, 1))
        utc = datetime.timezone.utc
        self.assertEqual(winter.observed_at.astimezone(utc), datetime.datetime(2025, 1, 2, 13, 10, tzinfo=utc))
        self.assertEqual(summer.observed_at.astimezone(utc), datetime.datetime(2025, 7, 1, 12, 10, tzinfo=utc))
        self.assertEqual(winter.timing.source_time, winter.observed_at)
        self.assertIs(winter.timing.delay_status, c.DataDelayStatus.END_OF_DAY)

    def test_a_rebased_or_scaled_payload_is_refused(self):
        for bad in (FX_JSON.replace('"base":"EUR"', '"base":"USD"'), FX_JSON.replace('"amount":1.0', '"amount":2.0')):
            out = self.translate(bad)
            self.assertEqual((out.fx, out.issues[0].code), ((), IssueCode.UNKNOWN_FORMAT))

    def test_bad_entries_are_reported_and_unreadable_payloads_refused(self):
        text = '{"amount":1.0,"base":"EUR","rates":{"2025-01-02":{"USD":1.1,"XX":2.0,"EUR1":3.0,"JPY":"x"},"bad":{"USD":1.0}}}'
        out = self.translate(text)
        self.assertEqual(len(out.fx), 1)
        self.assertEqual(sorted(i.row_ref for i in out.issues), ["2025-01-02/EUR1", "2025-01-02/JPY",
                                                                  "2025-01-02/XX", "bad"])
        self.assertEqual(self.translate("not json").issues[0].code, IssueCode.UNKNOWN_FORMAT)

    def test_nothing_is_inverted_crossed_or_rounded_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kit.write_registry(root, extra=[SourceRecord(FX_SOURCE, "Frankfurter (synthetic)", "synthetic",
                                                         "synthetic.ecb", synthetic=True)])
            m = kit.write_file(root, FX_SOURCE, DataKind.FX, FX_FORMAT, FX_JSON.encode(), "fx", "json",
                               source_identifiers=("CNY", "HKD", "USD"))
            files = FileStore(root)
            built = build_in_memory_market_data(
                MarketDataRelease.from_manifests("r", [m], [FX_SOURCE]), files, files.load_registry(),
                AdapterRegistry([FrankfurterFxAdapter()]), InMemoryIdentityRegistry(kit.SequentialIds()), catalog_calendars={})
            conv, day = placeholder_conventions(), datetime.date(2025, 1, 2)
            direct = built.store.fx_on(kit.EUR, kit.USD, day, conv)
            self.assertEqual((direct.outcome, direct.rate), (LookupOutcome.FOUND, Fraction(10321, 10000)))
            self.assertEqual(built.store.fx_on(kit.USD, kit.EUR, day, conv).outcome, LookupOutcome.NOT_IN_RELEASE)
            self.assertEqual(built.store.fx_on(kit.USD, kit.HKD, day, conv).outcome, LookupOutcome.NOT_IN_RELEASE)


FIGI_JSON = json.dumps([
    {"data": [{"figi": "BBG0SYNTH001", "name": "SYNTHETIC INC", "ticker": "SYN", "exchCode": "US",
               "compositeFIGI": "BBG0SYNTH001", "securityType": "Common Stock", "marketSector": "Equity",
               "shareClassFIGI": "BBG0SYNTHSC1", "securityType2": "Common Stock", "securityDescription": "SYN"}]},
    {"data": [{"figi": "BBG0SYNTH002", "name": "SYNTHETIC HK", "ticker": "700", "exchCode": "HK",
               "compositeFIGI": "BBG0SYNTH003", "shareClassFIGI": "BBG0SYNTHSC2"}]},
    {"warning": "No identifier found."},
])


class OpenFigiTests(unittest.TestCase):
    def translate(self, text=FIGI_JSON):
        return OpenFigiIdentityAdapter().translate(manifest(FIGI_SOURCE, DataKind.IDENTITY, FIGI_FORMAT),
                                                   text.encode())

    def test_data_items_become_assertions_exactly_as_published(self):
        out = self.translate()
        self.assertEqual(len(out.identities), 2)
        us, hk = out.identities
        self.assertEqual((us.figi, us.composite_figi, us.share_class_figi, us.exch_code, us.ticker),
                         ("BBG0SYNTH001", "BBG0SYNTH001", "BBG0SYNTHSC1", "US", "SYN"))
        self.assertEqual((hk.ticker, hk.exch_code), ("700", "HK"))  # no zero padding, no MIC invented
        self.assertFalse(hasattr(hk, "mic"))
        self.assertEqual([(i.row_ref, i.code) for i in out.issues], [("job2", IssueCode.MISSING_FIELD)])
        self.assertIn("No identifier found.", out.issues[0].detail)

    def test_malformed_input_is_reported(self):
        self.assertEqual(self.translate("{}").issues[0].code, IssueCode.UNKNOWN_FORMAT)
        out = self.translate('[{"data":[{"figi":"X"}]}]')
        self.assertEqual((out.identities, out.issues[0].code), ((), IssueCode.MISSING_FIELD))

    def build(self, identity, root):
        kit.write_registry(root, extra=[SourceRecord(FIGI_SOURCE, "OpenFIGI (synthetic)", "synthetic",
                                                     "synthetic.figi", synthetic=True)])
        m = kit.write_file(root, FIGI_SOURCE, DataKind.IDENTITY, FIGI_FORMAT, FIGI_JSON.encode(), "m", "json",
                           source_identifiers=("SYN", "700"))
        files = FileStore(root)
        return build_in_memory_market_data(
            MarketDataRelease.from_manifests("r", [m], [FIGI_SOURCE]), files, files.load_registry(),
            AdapterRegistry([OpenFigiIdentityAdapter()]), identity, catalog_calendars={})

    def identity(self, figi=None):
        # C2-4 (CP2 review of 39733e9): evidence is attached only when the assertion's exchange code is one of the codes
        # of the listing's MIC, given to the registry as DATA (synthetic codes here: the source's "US" and "HK")
        reg = InMemoryIdentityRegistry(kit.SequentialIds(), exchange_codes={"XNAS": ("US",), "XHKG": ("HK",)})
        reg.register_instruments([
            InstrumentEntry("Synthetic Inc", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "SYN", kit.USD, figi=figi),
            InstrumentEntry("Synthetic HK", SecurityType.COMMON_STOCK, "XHKG", "HKEX", "0700", kit.HKD)])
        return reg

    def test_evidence_matches_existing_identity_and_never_creates_any(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = self.identity()
            listings_before = {r.listing_id for r in reg.identifier_rows()}
            built = self.build(reg, Path(tmp))
            self.assertEqual(built.summaries[0].observation_count, 2)
            statuses = [e.resolution.status for _, e in built.identity_evidence]
            # "SYN" matches the one listing; HK "700" does not match the registered "0700"
            self.assertEqual(statuses, [c.ResolutionStatus.RESOLVED, c.ResolutionStatus.UNRESOLVED])
            self.assertEqual({r.listing_id for r in reg.identifier_rows()}, listings_before)  # nothing created

    def test_applying_evidence_adds_figis_to_a_resolved_listing_and_leaves_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = self.identity()
            built = self.build(reg, Path(tmp))
            applied = reg.apply_identity_assertions(e.assertion for _, e in built.identity_evidence)
            # market-data/1.5 Ruling 7.3: this record is COMPOSITE-level (figi == compositeFIGI, exchCode "US"), so it never
            # fills the exchange-level FIGI (this test used to expect FIGI + COMPOSITE + SHARE_CLASS). It fills
            # `composite_figi` because exactly one active listing of the US carries the ticker SYN (item 4)
            self.assertEqual(applied[0][2], ("COMPOSITE_FIGI",))
            self.assertEqual(applied[1][2], ())
            listing = reg.listing(kit.listing_id(reg, "SYN", "XNAS"))
            self.assertEqual((listing.figi, listing.composite_figi), (None, "BBG0SYNTH001"))
            self.assertEqual(reg.resolve(c.ExternalIdentifiers(figi="BBG0SYNTH001"), None).status, c.ResolutionStatus.UNRESOLVED)
            self.assertEqual([r for r in reg.identifier_rows() if r.scheme == "FIGI"], [])  # levels are never mixed

    def test_a_figi_that_contradicts_the_stored_one_is_a_conflict_and_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = self.identity(figi="BBG0OTHER000")
            built = self.build(reg, Path(tmp))
            first = built.identity_evidence[0][1].resolution
            self.assertEqual(first.status, c.ResolutionStatus.CONFLICT)
            reg.apply_identity_assertions(e.assertion for _, e in built.identity_evidence)
            # the stored EXCHANGE-level FIGI is untouched; 1.5 Ruling 7.3 item 4 lets the composite-level record fill the
            # separate `composite_figi` (this test used to expect no row at all)
            self.assertEqual([r.value for r in reg.identifier_rows() if r.scheme == "FIGI"], ["BBG0OTHER000"])
            listing = reg.listing(kit.listing_id(reg, "SYN", "XNAS"))
            self.assertEqual((listing.figi, listing.composite_figi), ("BBG0OTHER000", "BBG0SYNTH001"))


if __name__ == "__main__":
    unittest.main()
