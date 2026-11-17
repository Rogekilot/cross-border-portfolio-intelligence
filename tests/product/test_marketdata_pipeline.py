"""Mock adapter, identity resolution, ingestion, in-memory port and the placeholder
conventions (Tech Plan §15; market-data/1.0 where it states a shape). The placeholder rules
are tested only as what they are: conservative stand-ins that decide nothing."""

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
import marketdata_testkit as kit  # noqa: E402

from domain.instrument import SecurityType  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata.adapters.base import AdapterOutput, AdapterRegistry, IssueCode, NoAdapterError  # noqa: E402
from marketdata.adapters.mock import MOCK_FORMAT, MOCK_SOURCE_ID, MockSyntheticAdapter, make_synthetic_payload  # noqa: E402
from marketdata.conventions import (  # noqa: E402
    PLACEHOLDER_IDS,
    ConventionSet,
    PlaceholderFreshnessPolicy,
    placeholder_conventions,
)
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import (  # noqa: E402
    IngestError,
    ReleaseFileMissingError,
    build_in_memory_market_data,
)
from marketdata.manifest import (  # noqa: E402
    DataKind,
    MarketDataRelease,
    SourceRecord,
    SourceTermsNotAttestedError,
    TermsCheck,
    TwoVintagesError,
)
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402

D = kit.DAY1


def mock_manifest(kind=DataKind.QUOTE, currency=kit.USD):
    return kit.FileManifest(
        file_sha256="d" * 64, size_bytes=1, payload_filename="x.json", payload_format=MOCK_FORMAT,
        source_id=MOCK_SOURCE_ID, data_kind=kind, retrieval_time=kit.RETRIEVED, retrieved_by="synthetic",
        declared_adjustment=c.AdjustmentStatus.RAW, usage_scope=c.UsageScope.SYNTHETIC_TEST,
        declared_currency=currency)


class MockAdapterTests(unittest.TestCase):
    def quotes(self, rows, currency=kit.USD):
        payload = make_synthetic_payload(quotes=tuple(rows))
        return MockSyntheticAdapter(DataKind.QUOTE).translate(mock_manifest(currency=currency), payload)

    def row(self, **kw):
        base = {"ticker": "AAPL", "mic": "XNAS", "date": "2025-01-02", "close": "150.25"}
        base.update(kw)
        return base

    def test_quote_row_becomes_an_unresolved_quote_with_complete_lineage(self):
        out = self.quotes([self.row(volume="10")])
        (q,) = out.quotes
        self.assertEqual(out.issues, ())
        self.assertEqual((q.identifiers.ticker, q.identifiers.mic), ("AAPL", "XNAS"))
        self.assertEqual(q.price, Decimal("150.25"))
        self.assertEqual(q.volume, Decimal(10))
        self.assertEqual(q.currency, kit.USD)
        self.assertTrue(q.lineage.is_complete)
        self.assertEqual(q.lineage.source_value_text, "150.25")
        self.assertEqual(q.lineage.adapter_id, "mock.synthetic.quote")
        self.assertIs(q.lineage.usage_scope, c.UsageScope.SYNTHETIC_TEST)
        self.assertIsNone(q.lineage.independence_group)  # set by ingestion, not the adapter

    def test_bad_rows_are_reported_never_dropped_silently(self):
        # Re-recorded 2026-10-25 (review HIGH-1, market-data/1.16 Test V0): the rows used to share ONE date, which since 1.16 makes the series contradicted
        # (two rows for one date, whether or not they pass their own checks). The bad rows now have dates of their own, so this test is still about
        # bad rows and nothing else; the duplicate-date rule is tested in `test_marketdata_r4a_inputs.MockRouteDuplicateDatesTests`.
        out = self.quotes([self.row(date="2025-01-03", close="0"), self.row(date="not-a-date"), self.row(date="2025-01-06", ticker=""),
                           self.row(date="2025-01-07", close="abc"), self.row()])
        self.assertEqual(len(out.quotes), 1)
        self.assertEqual([i.code for i in out.issues],
                         [IssueCode.NON_POSITIVE_VALUE, IssueCode.UNPARSEABLE_ROW,
                          IssueCode.MISSING_FIELD, IssueCode.UNPARSEABLE_ROW])
        self.assertEqual([i.row_ref for i in out.issues], ["quotes[0]", "quotes[1]", "quotes[2]", "quotes[3]"])

    def test_a_number_is_read_as_an_exact_decimal_never_a_float(self):
        payload = b'{"quotes":[{"ticker":"A","mic":"M","date":"2025-01-02","close":150.2500000000000000001}]}'
        out = MockSyntheticAdapter(DataKind.QUOTE).translate(mock_manifest(), payload)
        self.assertEqual(out.quotes[0].price, Decimal("150.2500000000000000001"))

    def test_currency_is_never_inferred(self):
        out = MockSyntheticAdapter(DataKind.QUOTE).translate(
            dataclasses.replace(mock_manifest(), declared_currency=None),
            make_synthetic_payload(quotes=(self.row(),)))
        self.assertEqual(out.quotes, ())
        self.assertEqual(out.issues[0].code, IssueCode.UNDECLARED_CURRENCY)

    def test_unknown_format_is_an_issue(self):
        out = MockSyntheticAdapter(DataKind.QUOTE).translate(mock_manifest(), b"\xff not json")
        self.assertEqual(out.issues[0].code, IssueCode.UNKNOWN_FORMAT)

    def test_translation_is_deterministic(self):
        payload = make_synthetic_payload(quotes=(self.row(), self.row(date="2025-01-03")))
        a = MockSyntheticAdapter(DataKind.QUOTE)
        self.assertEqual(a.translate(mock_manifest(), payload), a.translate(mock_manifest(), payload))

    def test_corporate_action_types(self):
        actions = (
            {"ticker": "AAPL", "mic": "XNAS", "date": "2025-02-03", "type": "SPLIT", "new_units": "15", "old_units": "10"},
            {"ticker": "AAPL", "mic": "XNAS", "date": "2025-02-03", "type": "CASH_DIVIDEND", "amount": "0.25",
             "currency": "USD", "pay_date": "2025-02-20", "record_date": "2025-02-04"},
            {"ticker": "AAPL", "mic": "XNAS", "date": "2025-03-01", "type": "SYMBOL_CHANGE",
             "old_ticker": "AAPL", "new_ticker": "APPL"},
            {"ticker": "AAPL", "mic": "XNAS", "date": "2025-04-01", "type": "RIGHTS_ISSUE"},
            {"ticker": "AAPL", "mic": "XNAS", "date": "2025-02-03", "type": "CASH_DIVIDEND", "amount": "0.25",
             "currency": "USD"},  # no pay date: refused
        )
        out = MockSyntheticAdapter(DataKind.CORPORATE_ACTION).translate(
            mock_manifest(DataKind.CORPORATE_ACTION), make_synthetic_payload(actions=actions))
        kinds = [a.action_type for a in out.actions]
        self.assertEqual(kinds, [c.CorporateActionType.SPLIT, c.CorporateActionType.CASH_DIVIDEND,
                                 c.CorporateActionType.SYMBOL_CHANGE, c.CorporateActionType.UNSUPPORTED])
        self.assertEqual(out.actions[0].split_ratio.new_units, Decimal(15))  # combined ratio as given
        self.assertEqual(out.actions[3].unsupported_label, "RIGHTS_ISSUE")
        self.assertEqual(len(out.issues), 1)

    def test_benchmark_licensing_follows_the_manifest_and_never_permits_display(self):
        payload = make_synthetic_payload(benchmarks=({
            "benchmark_id": "SYN500", "provider": "synthetic", "value_kind": "LEVEL",
            "points": [{"date": "2025-01-02", "value": "100"}, {"date": "2025-01-03", "value": "101.5"}]},))
        out = MockSyntheticAdapter(DataKind.BENCHMARK).translate(mock_manifest(DataKind.BENCHMARK), payload)
        (b,) = out.benchmarks
        self.assertFalse(b.licensing.display_permitted)
        self.assertIs(b.licensing.license_status, c.LicenseStatus.SYNTHETIC_TEST)

    def test_adapter_registry_selects_by_source_kind_and_format_only(self):
        reg = AdapterRegistry([MockSyntheticAdapter(DataKind.QUOTE)])
        self.assertEqual(reg.for_manifest(mock_manifest()).adapter_id, "mock.synthetic.quote")
        with self.assertRaises(NoAdapterError):
            reg.for_manifest(mock_manifest(DataKind.FX))
        with self.assertRaises(ValueError):
            AdapterRegistry([MockSyntheticAdapter(DataKind.QUOTE), MockSyntheticAdapter(DataKind.QUOTE)])


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.reg = InMemoryIdentityRegistry(kit.SequentialIds())

    def entry(self, ticker="AAPL", mic="XNAS", **kw):
        base = dict(issuer_name="Issuer", security_type=SecurityType.COMMON_STOCK, mic=mic, exchange="X",
                    ticker=ticker, trading_currency=kit.USD)
        base.update(kw)
        return InstrumentEntry(**base)

    def ids(self, **kw):
        return c.ExternalIdentifiers(**kw)

    def test_identity_is_created_only_when_resolution_fails(self):
        (first,) = self.reg.register_instruments([self.entry(figi="BBG000B9XRY4")])
        self.assertTrue(first.created)
        self.assertEqual(first.resolution.status, c.ResolutionStatus.UNRESOLVED)
        (again,) = self.reg.register_instruments([self.entry(figi="BBG000B9XRY4")])
        self.assertFalse(again.created)
        self.assertEqual(again.listing_id, first.listing_id)
        self.assertEqual(len({r.listing_id for r in self.reg.identifier_rows()}), 1)

    def test_resolution_by_each_step(self):
        (r,) = self.reg.register_instruments([self.entry(figi="BBG000B9XRY4", vendor_ids=(("srcA", "sh600519"),))])
        for ids in (self.ids(figi="BBG000B9XRY4"), self.ids(ticker="AAPL", mic="XNAS"),
                    self.ids(vendor_id="sh600519", source_id="srcA")):
            res = self.reg.resolve(ids, D)
            self.assertEqual((res.status, res.listing_id), (c.ResolutionStatus.RESOLVED, r.listing_id), ids)
        # a vendor id is meaningful only inside its own source's scheme
        self.assertEqual(self.reg.resolve(self.ids(vendor_id="sh600519", source_id="srcB"), D).status,
                         c.ResolutionStatus.UNRESOLVED)
        self.assertEqual(self.reg.resolve(self.ids(vendor_id="sh600519"), D).status,
                         c.ResolutionStatus.UNRESOLVED)

    def test_a_ticker_shared_across_venues_is_ambiguous_not_guessed(self):
        a, b = self.reg.register_instruments([self.entry(mic="XNAS"), self.entry(mic="XNYS")])
        res = self.reg.resolve(self.ids(ticker="AAPL"), D)  # no MIC: cannot tell
        self.assertEqual(res.status, c.ResolutionStatus.AMBIGUOUS)
        self.assertEqual(set(res.candidates), {a.listing_id, b.listing_id})
        self.assertIsNone(res.listing_id)

    def test_conflicting_identifiers_never_pick_a_side(self):
        a, b = self.reg.register_instruments([self.entry("AAA", figi="BBG000000001"),
                                              self.entry("BBB", figi="BBG000000002")])
        res = self.reg.resolve(self.ids(figi="BBG000000001", ticker="BBB", mic="XNAS"), D)
        self.assertEqual(res.status, c.ResolutionStatus.CONFLICT)
        self.assertEqual(set(res.candidates), {a.listing_id, b.listing_id})
        # a file asserting a different FIGI than the stored one is a conflict, nothing overwritten
        res = self.reg.resolve(self.ids(figi="BBG0000000ZZ", ticker="AAA", mic="XNAS"), D)
        self.assertEqual(res.status, c.ResolutionStatus.CONFLICT)
        self.assertEqual([r.value for r in self.reg.identifier_rows(a.listing_id) if r.scheme == "FIGI"],
                         ["BBG000000001"])
        # a conflicting registration entry creates nothing
        before = len(self.reg.identifier_rows())
        (reg_result,) = self.reg.register_instruments([self.entry("AAA", figi="BBG0000000ZZ")])
        self.assertFalse(reg_result.created)
        self.assertEqual(len(self.reg.identifier_rows()), before)

    def test_a_symbol_change_is_an_attribute_update_with_dated_resolution(self):
        (r,) = self.reg.register_instruments([self.entry("OLD")])
        effective = datetime.date(2025, 3, 3)
        self.reg.change_ticker(r.listing_id, "NEW", effective)
        old = self.ids(ticker="OLD", mic="XNAS")
        new = self.ids(ticker="NEW", mic="XNAS")
        before, on = effective - datetime.timedelta(days=1), effective
        self.assertEqual(self.reg.resolve(old, before).listing_id, r.listing_id)
        self.assertEqual(self.reg.resolve(new, on).listing_id, r.listing_id)  # same listing_id
        self.assertEqual(self.reg.resolve(new, before).status, c.ResolutionStatus.UNRESOLVED)  # not guessed
        self.assertEqual(self.reg.resolve(old, on).status, c.ResolutionStatus.UNRESOLVED)
        self.assertEqual(self.reg.listing(r.listing_id).ticker, "NEW")  # attribute updated
        self.assertEqual(self.reg.listing(r.listing_id).listing_id, r.listing_id)

    def test_new_ids_come_from_the_injected_factory(self):
        (r,) = self.reg.register_instruments([self.entry()])
        self.assertEqual(r.listing_id, uuid.UUID(int=1003))  # issuer 1001, instrument 1002, listing 1003


class BuiltWorldTestCase(unittest.TestCase):
    def build(self, flavour, extra=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        files, release, adapters = kit.build_world(root, flavour)
        identity = kit.make_identity()
        result = build_in_memory_market_data(release, files, files.load_registry(), adapters, identity, catalog_calendars={})
        return root, files, release, adapters, identity, result


class IngestTests(BuiltWorldTestCase):
    def test_every_flavour_loads_all_facts_with_complete_lineage_and_registry_fields(self):
        for flavour in ("mock", "csv", "jsonl"):
            with self.subTest(flavour):
                *_, identity, result = self.build(flavour)
                self.assertEqual(result.issues, ())
                self.assertEqual(result.exceptions, ())
                self.assertEqual(sum(s.observation_count for s in result.summaries), len(kit.QUOTES) + len(kit.FX))
                aapl = kit.listing_id(identity, "AAPL", "XNAS")
                series = result.store.quotes(aapl, kit.DAY1, kit.DAY2)
                self.assertEqual(len(series.readings), 2)
                lin = series.readings[0].observation.lineage
                self.assertTrue(lin.is_complete)
                self.assertTrue(lin.upstream and lin.independence_group)
                self.assertIs(lin.usage_scope, c.UsageScope.SYNTHETIC_TEST)

    def test_load_is_deterministic(self):
        *_, r1 = self.build("csv")
        *_, r2 = self.build("csv")
        self.assertEqual([s.normalized_digest for s in r1.summaries], [s.normalized_digest for s in r2.summaries])

    def test_an_unresolved_identity_is_quarantined_not_loaded_and_never_creates_identity(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root)
        payload = make_synthetic_payload(quotes=(
            {"ticker": "ZZZZ", "mic": "XNAS", "date": "2025-01-02", "close": "5"},
            {"ticker": "ZZZZ", "mic": "XNAS", "date": "2025-01-03", "close": "6"},
            {"ticker": "AAPL", "mic": "XNAS", "date": "2025-01-02", "close": "150.25"}))
        m = kit.write_file(root, MOCK_SOURCE_ID, DataKind.QUOTE, MOCK_FORMAT, payload, "q", "json",
                           currency=kit.USD)
        identity = kit.make_identity()
        rows_before = len(identity.identifier_rows())
        files = FileStore(root)
        release = MarketDataRelease.from_manifests("r", [m], [MOCK_SOURCE_ID])
        result = build_in_memory_market_data(release, files, files.load_registry(),
                                             AdapterRegistry([MockSyntheticAdapter(DataKind.QUOTE)]), identity, catalog_calendars={})
        self.assertEqual(len(identity.identifier_rows()), rows_before)  # nothing created
        ((sha, exc),) = result.exceptions
        self.assertEqual((exc.status, exc.row_count), (c.ResolutionStatus.UNRESOLVED, 2))
        self.assertEqual(result.summaries[0].exception_count, 1)
        self.assertEqual(result.summaries[0].observation_count, 1)
        self.assertEqual([i.code for _, i in result.issues], [IssueCode.UNRESOLVED_IDENTITY])

    def test_a_declared_currency_that_differs_from_the_listing_is_reported_not_loaded(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root)
        payload = make_synthetic_payload(quotes=(
            {"ticker": "AAPL", "mic": "XNAS", "date": "2025-01-02", "close": "150.25"},))
        m = kit.write_file(root, MOCK_SOURCE_ID, DataKind.QUOTE, MOCK_FORMAT, payload, "q", "json",
                           currency=kit.HKD)  # AAPL trades in USD
        files = FileStore(root)
        release = MarketDataRelease.from_manifests("r", [m], [MOCK_SOURCE_ID])
        result = build_in_memory_market_data(release, files, files.load_registry(),
                                             AdapterRegistry([MockSyntheticAdapter(DataKind.QUOTE)]),
                                             kit.make_identity(), catalog_calendars={})
        self.assertEqual([i.code for _, i in result.issues], [IssueCode.TRADING_CURRENCY_MISMATCH])
        self.assertEqual(result.summaries[0].observation_count, 0)

    def _single_file_world(self, source_id, scope, records, adapter_cls=MockSyntheticAdapter,
                           payload_format=MOCK_FORMAT, adapter=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=records)
        payload = make_synthetic_payload(quotes=(
            {"ticker": "AAPL", "mic": "XNAS", "date": "2025-01-02", "close": "150.25"},))
        m = kit.write_file(root, source_id, DataKind.QUOTE, payload_format, payload, "q", "json",
                           currency=kit.USD, usage_scope=scope, retrieved_by="human")
        files = FileStore(root)
        release = MarketDataRelease.from_manifests("r", [m], [source_id])
        return files, release, adapter or AdapterRegistry([MockSyntheticAdapter(DataKind.QUOTE)])

    def test_a_source_without_a_recorded_terms_check_is_refused(self):
        rec = SourceRecord("vendor.x", "X", "up", "g")
        files, release, adapters = self._single_file_world(
            "vendor.x", c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, [rec])
        with self.assertRaises(SourceTermsNotAttestedError):
            build_in_memory_market_data(release, files, files.load_registry(), adapters, kit.make_identity(), catalog_calendars={})

    def test_synthetic_scope_and_synthetic_source_must_go_together(self):
        rec = SourceRecord(MOCK_SOURCE_ID + ".2", "X", "up", "g",
                           terms_check=TermsCheck("owner", datetime.date(2025, 1, 5), True))
        files, release, adapters = self._single_file_world(
            rec.source_id, c.UsageScope.SYNTHETIC_TEST, [rec])
        adapter = MockSyntheticAdapter(DataKind.QUOTE)
        adapter.source_id = rec.source_id
        with self.assertRaises(IngestError):
            build_in_memory_market_data(release, files, files.load_registry(), AdapterRegistry([adapter]),
                                        kit.make_identity(), catalog_calendars={})

    def test_an_adapter_that_breaks_the_rules_is_a_bug_not_data(self):
        class NoLineage(MockSyntheticAdapter):
            def translate(self, manifest, payload):
                out = super().translate(manifest, payload)
                q = out.quotes[0]
                bare = dataclasses.replace(q, lineage=c.Lineage("s", c.AdjustmentStatus.RAW))
                return AdapterOutput(quotes=(bare,))

        class WrongTuple(MockSyntheticAdapter):
            def translate(self, manifest, payload):
                out = super().translate(manifest, payload)
                return AdapterOutput(quotes=out.quotes, benchmarks=(object(),))  # type: ignore[arg-type]

        class WrongFile(MockSyntheticAdapter):
            def translate(self, manifest, payload):
                out = super().translate(manifest, payload)
                q = out.quotes[0]
                other = dataclasses.replace(q.lineage, file_sha256="e" * 64)
                return AdapterOutput(quotes=(dataclasses.replace(q, lineage=other),))

        for cls in (NoLineage, WrongTuple, WrongFile):
            with self.subTest(cls.__name__):
                tmp = tempfile.TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                root = Path(tmp.name)
                kit.write_registry(root)
                payload = make_synthetic_payload(quotes=(
                    {"ticker": "AAPL", "mic": "XNAS", "date": "2025-01-02", "close": "150.25"},))
                m = kit.write_file(root, MOCK_SOURCE_ID, DataKind.QUOTE, MOCK_FORMAT, payload, "q", "json",
                                   currency=kit.USD)
                files = FileStore(root)
                release = MarketDataRelease.from_manifests("r", [m], [MOCK_SOURCE_ID])
                with self.assertRaises(IngestError):
                    build_in_memory_market_data(release, files, files.load_registry(),
                                                AdapterRegistry([cls(DataKind.QUOTE)]), kit.make_identity(), catalog_calendars={})

    def test_a_release_naming_a_missing_file_fails(self):
        root, files, release, adapters, identity, _ = self.build("mock")
        ghost = MarketDataRelease(name="g", files=tuple(sorted(release.files + ("0" * 64,))),
                                  source_precedence=release.source_precedence)
        with self.assertRaises(ReleaseFileMissingError):
            build_in_memory_market_data(ghost, files, files.load_registry(), adapters, identity, catalog_calendars={})

    def test_two_vintages_in_loaded_data_fail_closed_even_if_the_release_was_built_by_hand(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root)
        manifests = []
        for label, price in (("v1", "150.25"), ("v2", "150.30")):  # same series, two retrievals
            payload = make_synthetic_payload(quotes=(
                {"ticker": "AAPL", "mic": "XNAS", "date": "2025-01-02", "close": price},))
            manifests.append(kit.write_file(root, MOCK_SOURCE_ID, DataKind.QUOTE, MOCK_FORMAT, payload, label,
                                            "json", currency=kit.USD))  # no source_identifiers: series '*'
        with self.assertRaises(TwoVintagesError):  # the supported builder refuses
            MarketDataRelease.from_manifests("r", manifests, [MOCK_SOURCE_ID])
        hand = MarketDataRelease(name="hand", files=tuple(sorted(m.file_sha256 for m in manifests)),
                                 source_precedence=(MOCK_SOURCE_ID,))
        files = FileStore(root)
        with self.assertRaises(TwoVintagesError):  # and so does loading
            build_in_memory_market_data(hand, files, files.load_registry(),
                                        AdapterRegistry([MockSyntheticAdapter(DataKind.QUOTE)]),
                                        kit.make_identity(), catalog_calendars={})


class PortAndPlaceholderTests(BuiltWorldTestCase):
    def setUp(self):
        self.root, self.files, self.release, self.adapters, self.identity, self.result = self.build("mock")
        self.port = self.result.store
        self.conv = placeholder_conventions()
        self.aapl = kit.listing_id(self.identity, "AAPL", "XNAS")

    def test_quote_on_an_exact_date(self):
        lk = self.port.quote_on(self.aapl, kit.DAY1, self.conv)
        self.assertEqual(lk.outcome, LookupOutcome.FOUND)
        self.assertEqual(lk.selected.observation.price, Decimal("150.25"))
        self.assertEqual(lk.date_used, kit.DAY1)
        self.assertEqual(lk.reconciliation.status, c.ReconciliationStatus.SINGLE_SOURCE)
        self.assertEqual(lk.reconciliation.selected_source, MOCK_SOURCE_ID)
        self.assertEqual(len(lk.consumed), 1)

    def test_no_look_back_no_fill(self):
        lk = self.port.quote_on(self.aapl, datetime.date(2025, 1, 4), self.conv)
        self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_OBSERVATION, None))
        unknown = self.port.quote_on(uuid.UUID(int=99), kit.DAY1, self.conv)
        self.assertEqual(unknown.outcome, LookupOutcome.NOT_IN_RELEASE)

    def test_freshness_is_assessed_at_read_time_and_the_placeholder_assigns_nothing(self):
        lk = self.port.quote_on(self.aapl, kit.DAY1, self.conv)
        self.assertIs(lk.freshness.state, c.FreshnessState.UNKNOWN)
        self.assertEqual(lk.freshness.assessed_as_of, kit.DAY1)
        self.assertEqual(lk.freshness.policy_id, PlaceholderFreshnessPolicy.policy_id)
        self.assertIs(lk.freshness.delay_status, c.DataDelayStatus.END_OF_DAY)

    def test_placeholders_are_named_and_the_set_is_not_conformant(self):
        self.assertTrue(all(i.startswith("placeholder/") for i in PLACEHOLDER_IDS))
        self.assertFalse(self.conv.is_conformant)
        self.assertEqual(set(self.conv.placeholder_ids()), set(PLACEHOLDER_IDS))
        self.assertEqual(self.conv.ids()["convention_set"], "market-data/1.16")  # 1.7
        self.assertTrue(self.conv.ids()["reconciliation"].startswith("market-data/1.16#"))  # implemented, not a placeholder

    def test_fx_published_pair_is_an_exact_rational_and_same_currency_is_one(self):
        lk = self.port.fx_on(kit.HKD, kit.USD, kit.DAY1, self.conv)
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.FOUND, Fraction(1288, 10000)))
        self.assertEqual(len(lk.legs), 1)
        self.assertEqual(lk.date_used, kit.DAY1)
        self.assertEqual(len(lk.leg_freshness), 1)
        same = self.port.fx_on(kit.USD, kit.USD, kit.DAY1, self.conv)
        self.assertEqual((same.outcome, same.rate, same.legs), (LookupOutcome.SAME_CURRENCY, Fraction(1), ()))

    def test_no_inversion_no_crossing_and_cnh_is_never_cny(self):
        # only HKD->USD and CNY->USD are published; none of these may be derived or substituted
        inverse = self.port.fx_on(kit.USD, kit.HKD, kit.DAY1, self.conv)
        self.assertEqual((inverse.outcome, inverse.rate), (LookupOutcome.NOT_IN_RELEASE, None))
        cross = self.port.fx_on(kit.HKD, kit.CNY, kit.DAY1, self.conv)
        self.assertEqual((cross.outcome, cross.rate), (LookupOutcome.NOT_IN_RELEASE, None))
        cnh = self.port.fx_on(kit.CurrencyCode("CNH"), kit.USD, kit.DAY1, self.conv)  # OD-3: strict
        self.assertEqual((cnh.outcome, cnh.rate), (LookupOutcome.NOT_IN_RELEASE, None))
        other_day = self.port.fx_on(kit.HKD, kit.USD, kit.DAY2, self.conv)
        self.assertEqual((other_day.outcome, other_day.rate), (LookupOutcome.NO_OBSERVATION, None))

    def test_no_adjustment_or_source_mixing_label_is_defaulted(self):
        lk = self.port.quote_on(self.aapl, kit.DAY1, self.conv)
        self.assertIs(lk.selected.observation.lineage.adjustment_status, c.AdjustmentStatus.RAW)

    def test_two_independent_sources_are_all_kept_and_nothing_is_chosen_or_resolved(self):
        # csv world (AAPL 150.25) plus a jsonl file reporting AAPL 150.30 for the same date
        write = kit.write_file
        tmp2 = tempfile.TemporaryDirectory()
        self.addCleanup(tmp2.cleanup)
        root2 = Path(tmp2.name)
        files, release, adapters = kit.build_world(root2, "csv")
        payload = kit.jsonl_quotes_payload((("AAPL", "XNAS", kit.DAY1, "150.30", "900", kit.USD),))
        m = write(root2, kit.JSONL_SOURCE, DataKind.QUOTE, kit.JSONL_FORMAT, payload, "other", "jsonl",
                  currency=kit.USD, source_identifiers=("AAPL",))
        adapters.register(kit.JsonlQuoteAdapter())
        store = FileStore(root2)
        manifests = [store.read_verified(p).manifest for p in store.manifest_paths()]
        rel = MarketDataRelease.from_manifests("two", manifests, [kit.CSV_SOURCE, kit.JSONL_SOURCE])
        built = build_in_memory_market_data(rel, store, store.load_registry(), adapters, self.identity, catalog_calendars={})
        lk = built.store.quote_on(self.aapl, kit.DAY1, self.conv)
        # two independent upstreams, two recovered values that differ: DISAGREEMENT, no value used,
        # never settled by order (Ruling 4.3)
        self.assertEqual(lk.outcome, LookupOutcome.NO_SELECTION)
        self.assertIsNone(lk.selected)
        self.assertEqual(len(lk.readings), 2)
        self.assertIs(lk.reconciliation.status, c.ReconciliationStatus.DISAGREEMENT)
        self.assertIsNone(lk.reconciliation.selected_source)
        self.assertIsNone(lk.reconciliation.used)
        (price_diff,) = lk.reconciliation.differences
        self.assertEqual((price_diff.field, price_diff.absolute), ("price", Decimal("0.05")))
        self.assertEqual({r.source_id for r in lk.readings}, {kit.CSV_SOURCE, kit.JSONL_SOURCE})
        self.assertIsNone(lk.freshness)
        from marketdata.states import price_input_state
        from product_contract.vocabulary import ReasonCode, SufficiencyState
        state = price_input_state(lk)  # Ruling 4.4: INSUFFICIENT_DATA + SOURCE_CONFLICT
        self.assertEqual((state.state, state.reason), (SufficiencyState.INSUFFICIENT_DATA, ReasonCode.SOURCE_CONFLICT))

    def test_sources_sharing_an_upstream_count_as_one(self):
        from marketdata.reconciliation import Market11Reconciler
        q = self.port.quote_on(self.aapl, kit.DAY1, self.conv).selected
        shared = [dataclasses.replace(q, source_id="a"), dataclasses.replace(q, source_id="b")]
        r = Market11Reconciler().reconcile(tuple(shared))
        self.assertIs(r.status, c.ReconciliationStatus.SINGLE_SOURCE)

    def test_actions_and_benchmarks_come_back_with_their_flags(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root)
        actions = make_synthetic_payload(actions=(
            {"ticker": "AAPL", "mic": "XNAS", "date": "2025-02-03", "type": "SPLIT", "new_units": "4", "old_units": "1"},
            {"ticker": "AAPL", "mic": "XNAS", "date": "2025-04-01", "type": "SPIN_OFF"}))
        bench = make_synthetic_payload(benchmarks=({
            "benchmark_id": "SYN500", "provider": "synthetic", "value_kind": "LEVEL",
            "points": [{"date": "2025-01-02", "value": "100"}, {"date": "2025-01-03", "value": "101"}]},))
        ms = [kit.write_file(root, MOCK_SOURCE_ID, DataKind.CORPORATE_ACTION, MOCK_FORMAT, actions, "a", "json",
                             source_identifiers=("AAPL",)),
              kit.write_file(root, MOCK_SOURCE_ID, DataKind.BENCHMARK, MOCK_FORMAT, bench, "b", "json",
                             currency=kit.USD, source_identifiers=("SYN500",))]
        files = FileStore(root)
        adapters = AdapterRegistry([MockSyntheticAdapter(DataKind.CORPORATE_ACTION),
                                    MockSyntheticAdapter(DataKind.BENCHMARK)])
        rel = MarketDataRelease.from_manifests("r", ms, [MOCK_SOURCE_ID])
        built = build_in_memory_market_data(rel, files, files.load_registry(), adapters, self.identity, catalog_calendars={})
        got = built.store.corporate_actions(self.aapl, datetime.date(2025, 1, 1), datetime.date(2025, 12, 31))
        self.assertEqual([r.observation.action_type for r in got.readings],
                         [c.CorporateActionType.SPLIT, c.CorporateActionType.UNSUPPORTED])
        self.assertEqual(built.store.corporate_actions(self.aapl, datetime.date(2026, 1, 1),
                                                       datetime.date(2026, 2, 1)).outcome,
                         LookupOutcome.NO_OBSERVATION)
        b = built.store.benchmark("SYN500", kit.DAY2, kit.DAY2)
        self.assertEqual(len(b.series[0].points), 1)
        self.assertFalse(b.series[0].licensing.display_permitted)
        self.assertEqual(built.store.benchmark("NOPE", kit.DAY1, kit.DAY2).outcome, LookupOutcome.NOT_IN_RELEASE)

    def test_conventions_are_injected_not_hard_wired(self):
        class FixedFreshness:
            policy_id = "test/fixed-current"

            def assess(self, timing, value_date, as_of):
                return c.Freshness(None, c.FreshnessState.CURRENT, timing.delay_status, as_of, self.policy_id)

        conv = dataclasses.replace(self.conv, freshness=FixedFreshness())
        lk = self.port.quote_on(self.aapl, kit.DAY1, conv)
        self.assertIs(lk.freshness.state, c.FreshnessState.CURRENT)
        self.assertEqual(set(conv.placeholder_ids()), set(PLACEHOLDER_IDS) - {PlaceholderFreshnessPolicy.policy_id})
        self.assertIsInstance(conv, ConventionSet)


if __name__ == "__main__":
    unittest.main()
