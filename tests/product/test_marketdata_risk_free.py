"""CP4b-2: the RISK_FREE market-data kind (contract, synthetic adapter, RATE_PUBLICATIONS calendar, ingest, the Current-mode derived release, the source gates). `risk/1.0` Ruling 4.6 is the checklist the contract encodes.

The statistics and the conversion to a period return are tested in `test_risk_free_leg.py`; the PostgreSQL projection (migration 0016) in `test_postgres_risk_free.py`.
"""

import dataclasses
import datetime
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_testkit as kit  # noqa: E402

from domain.currency import CurrencyCode  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata.adapters.base import AdapterRegistry, IssueCode  # noqa: E402
from marketdata.adapters.calendar_file import PAYLOAD_FORMAT as CAL_FORMAT, CalendarFileAdapter  # noqa: E402
from marketdata.adapters.synthetic_risk_free import PAYLOAD_FORMAT, SOURCE_ID, SyntheticRiskFreeAdapter, make_risk_free_payload  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from marketdata.ingest import IngestError, build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, FileManifest, MarketDataRelease, SourceRecord, SourceTermsNotAttestedError, TwoVintagesError, TermsCheck  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.profiles import ProfileNotAdmittedError  # noqa: E402

D, USD = datetime.date, CurrencyCode("USD")
CAL_SOURCE = "calendar.manual"
SERIES = "SYN_UST13_USD"
CAL_ID = "SYN_RF_USD"


def rf_row(**kw):
    base = {"series_id": SERIES, "name": "synthetic 13-week bill", "provider": "synthetic provider", "instrument": "synthetic 13-WEEK SOVEREIGN BILL", "tenor_weeks": 13,
            "quote_type": "SIMPLE_YIELD", "day_count_basis": 365, "unit": "PERCENT", "decimals_published": 2, "date_semantics": "the date the quote is FOR; close, New York",
            "calendar_id": CAL_ID, "revision_policy": "NOT_REVISED",
            "points": [{"date": "2025-01-02", "rate": "3.65"}, {"date": "2025-01-03", "rate": "3.65"}, {"date": "2025-01-06", "rate": "3.66"}]}
    base.update(kw)
    return base


def rf_manifest(sha="e" * 64, currency=USD, scope=c.UsageScope.SYNTHETIC_TEST, source=SOURCE_ID, retrieved=kit.RETRIEVED):
    return FileManifest(file_sha256=sha, size_bytes=1, payload_filename="rf.json", payload_format=PAYLOAD_FORMAT, source_id=source, data_kind=DataKind.RISK_FREE, retrieval_time=retrieved,
                        retrieved_by="synthetic", declared_adjustment=c.AdjustmentStatus.RAW, usage_scope=scope, declared_currency=currency, declared_delay=c.DataDelayStatus.END_OF_DAY)


def translate(rows, **kw):
    return SyntheticRiskFreeAdapter().translate(rf_manifest(**kw), make_risk_free_payload(tuple(rows)))


def calendar_payload(dates, coverage=("2025-01-01", "2025-01-31"), series=(SERIES,), publication="18:00", **kw):
    doc = {"schema": "finweb.marketdata.calendar/1", "calendar_id": CAL_ID, "kind": "RATE_PUBLICATIONS", "applies_to": list(series), "timezone": "America/New_York",
           "coverage": {"from": coverage[0], "to": coverage[1]}, "dates": [d.isoformat() for d in dates], "actual_through": coverage[1], "publication": {"time": publication},
           "evidence": "synthetic publication schedule", "prepared_by": "test", "prepared_on": "2026-10-02", "version": "v1"}
    doc.update(kw)
    return json.dumps(doc).encode("utf-8")


JAN_DATES = [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7), D(2025, 1, 8)]


class ContractTests(unittest.TestCase):
    def series(self, **override):
        out = translate([rf_row(**override)])
        self.assertEqual(out.issues, (), out.issues)
        return out.risk_free[0]

    def refused(self, **override):
        out = translate([rf_row(**override)])
        self.assertEqual(out.risk_free, ())
        (issue,) = out.issues
        return issue

    def test_a_series_carries_the_whole_checklist(self):
        s = self.series()
        self.assertEqual((s.series_id, s.currency, s.instrument, s.tenor_weeks, s.quote_type, s.day_count_basis, s.unit, s.decimals_published, s.calendar_id, s.revision_policy),
                         (SERIES, USD, "synthetic 13-WEEK SOVEREIGN BILL", 13, c.RiskFreeQuoteType.SIMPLE_YIELD, 365, c.RateUnit.PERCENT, 2, CAL_ID, c.RevisionPolicy.NOT_REVISED))
        self.assertEqual([(p.value_date.isoformat(), str(p.rate)) for p in s.points], [("2025-01-02", "3.65"), ("2025-01-03", "3.65"), ("2025-01-06", "3.66")])
        self.assertTrue(s.lineage.is_complete and s.lineage.is_synthetic)
        self.assertEqual(s.licensing.license_status, c.LicenseStatus.SYNTHETIC_TEST)
        self.assertFalse(s.licensing.display_permitted)

    def test_every_checklist_field_is_required(self):
        for field in ("series_id", "name", "provider", "instrument", "tenor_weeks", "quote_type", "day_count_basis", "unit", "decimals_published", "date_semantics", "calendar_id",
                      "revision_policy", "points"):
            row = rf_row()
            del row[field]
            out = translate([row])
            self.assertEqual(out.risk_free, (), field)
            self.assertEqual(out.issues[0].code, IssueCode.MISSING_FIELD, field)

    def test_the_currency_comes_from_the_manifest_and_is_never_inferred(self):
        out = SyntheticRiskFreeAdapter().translate(dataclasses.replace(rf_manifest(), declared_currency=None), make_risk_free_payload((rf_row(),)))
        self.assertEqual((out.risk_free, out.issues[0].code), ((), IssueCode.UNDECLARED_CURRENCY))
        self.assertEqual(self.series().currency, USD)
        out = translate([rf_row()], currency=CurrencyCode("HKD"))
        self.assertEqual(out.risk_free[0].currency.code, "HKD")

    def test_a_bank_discount_quote_needs_its_term_and_is_act360(self):
        discount = rf_row(quote_type="BANK_DISCOUNT", day_count_basis=360, points=[{"date": "2025-01-02", "rate": "4.00", "term_days": 91}])
        s = translate([discount]).risk_free[0]
        self.assertEqual((s.quote_type, s.points[0].term_days), (c.RiskFreeQuoteType.BANK_DISCOUNT, 91))
        self.assertEqual(translate([dict(discount, points=[{"date": "2025-01-02", "rate": "4.00"}])]).issues[0].code, IssueCode.CONTRACT_VIOLATION)  # no term
        self.assertIn("needs its term", translate([dict(discount, points=[{"date": "2025-01-02", "rate": "4.00"}])]).issues[0].detail)  # refused for the right reason, not by a crash
        self.assertEqual(translate([dict(discount, day_count_basis=365)]).issues[0].code, IssueCode.CONTRACT_VIOLATION)  # a discount rate is ACT/360
        self.assertEqual(translate([dict(discount, points=[{"date": "2025-01-02", "rate": "400", "term_days": 91}])]).issues[0].code, IssueCode.CONTRACT_VIOLATION)  # y t >= 360
        self.assertEqual(translate([rf_row(points=[{"date": "2025-01-02", "rate": "3.65", "term_days": 91}])]).issues[0].code, IssueCode.CONTRACT_VIOLATION)  # a yield has no term

    def test_a_simple_yield_needs_a_declared_day_count(self):
        self.assertEqual(self.refused(day_count_basis=364).code, IssueCode.CONTRACT_VIOLATION)
        self.assertEqual(self.series(day_count_basis=360).day_count_basis, 360)

    def test_precision_is_declared_and_enforced(self):
        self.assertEqual(self.refused(decimals_published=1).code, IssueCode.CONTRACT_VIOLATION)   # 3.65 has two decimals
        self.assertEqual(self.series(decimals_published=4).decimals_published, 4)                  # fewer used than declared is fine
        self.assertEqual(self.refused(decimals_published=13).code, IssueCode.CONTRACT_VIOLATION)
        trailing = rf_row(decimals_published=1, points=[{"date": "2025-01-02", "rate": "3.60"}])    # 3.60 == 3.6: trailing zeros are not extra precision
        self.assertEqual(translate([trailing]).issues, ())

    def test_points_must_increase_and_a_rate_may_be_negative_but_not_nonfinite(self):
        self.assertEqual(self.refused(points=[{"date": "2025-01-03", "rate": "1"}, {"date": "2025-01-02", "rate": "1"}]).code, IssueCode.CONTRACT_VIOLATION)
        self.assertEqual(self.refused(points=[{"date": "2025-01-03", "rate": "1"}, {"date": "2025-01-03", "rate": "1"}]).code, IssueCode.CONTRACT_VIOLATION)
        self.assertEqual(self.series(points=[{"date": "2025-01-02", "rate": "-0.50"}]).points[0].rate, Decimal("-0.50"))
        self.assertEqual(self.refused(points=[{"date": "2025-01-02", "rate": "NaN"}]).code, IssueCode.UNPARSEABLE_ROW)
        self.assertEqual(self.refused(points=[]).code, IssueCode.MISSING_FIELD)

    def test_enumerations_and_unknown_keys_are_refused(self):
        self.assertEqual(self.refused(quote_type="CONTINUOUS").code, IssueCode.UNPARSEABLE_ROW)
        self.assertEqual(self.refused(unit="BASIS_POINTS").code, IssueCode.UNPARSEABLE_ROW)
        self.assertEqual(self.refused(revision_policy="SOMETIMES").code, IssueCode.UNPARSEABLE_ROW)
        self.assertEqual(self.refused(surprise="x").code, IssueCode.UNKNOWN_FORMAT)
        self.assertEqual(self.refused(tenor_weeks=0).code, IssueCode.CONTRACT_VIOLATION)

    def test_a_number_is_an_exact_decimal_never_a_float(self):
        # a bare JSON number with twelve decimals, which a float cannot hold exactly: it is read as the exact Decimal
        payload = b'{"series": [' + json.dumps(rf_row(decimals_published=12, points=[{"date": "2025-01-02", "rate": "X"}])).replace('"X"', "3.650000000001").encode() + b"]}"
        out = SyntheticRiskFreeAdapter().translate(rf_manifest(), payload)
        self.assertEqual(out.issues, ())
        self.assertEqual(out.risk_free[0].points[0].rate, Decimal("3.650000000001"))
        self.assertIsInstance(out.risk_free[0].points[0].rate, Decimal)

    def test_translation_is_deterministic_and_its_digest_covers_every_checklist_field(self):
        from marketdata.canonical import observation_obj  # noqa: PLC0415

        a = translate([rf_row()]).risk_free[0]
        b = translate([rf_row()]).risk_free[0]
        self.assertEqual(canonical_json(observation_obj(a)), canonical_json(observation_obj(b)))
        base = canonical_json(observation_obj(a))
        for change in ({"tenor_weeks": 26}, {"quote_type": "BANK_DISCOUNT", "day_count_basis": 360, "points": [{"date": "2025-01-02", "rate": "3.65", "term_days": 91}]},
                       {"unit": "DECIMAL", "points": [{"date": "2025-01-02", "rate": "0.0365"}], "decimals_published": 4}, {"revision_policy": "REVISED"}, {"calendar_id": "OTHER"},
                       {"date_semantics": "another meaning"}, {"instrument": "another instrument"}):
            other = translate([rf_row(**change)]).risk_free[0]
            self.assertNotEqual(canonical_json(observation_obj(other)), base, change)

    def test_a_series_with_an_unknown_adjustment_is_still_a_rate_series_and_not_a_benchmark(self):
        self.assertFalse(hasattr(self.series(), "value_kind"))  # a rate is not a benchmark and cannot be selected as one: a distinct type
        self.assertIsNot(c.RiskFreeSeries, c.BenchmarkSeries)


class RatePublicationCalendarTests(unittest.TestCase):
    def manifest(self):
        return FileManifest(file_sha256="c" * 64, size_bytes=1, payload_filename="cal.json", payload_format=CAL_FORMAT, source_id=CAL_SOURCE, data_kind=DataKind.CALENDAR,
                            retrieval_time=kit.RETRIEVED, retrieved_by="human", declared_adjustment=c.AdjustmentStatus.RAW, usage_scope=c.UsageScope.SYNTHETIC_TEST)

    def parse(self, payload):
        return CalendarFileAdapter().translate(self.manifest(), payload)

    def test_a_publication_calendar_names_series_and_a_publication_time(self):
        out = self.parse(calendar_payload(JAN_DATES))
        self.assertEqual(out.issues, ())
        (cal,) = out.calendars
        self.assertEqual((cal.kind, cal.applies_to, cal.timezone, cal.publication_time, cal.fixing_time, cal.default_close, cal.early_closes),
                         (c.CalendarKind.RATE_PUBLICATIONS, (SERIES,), "America/New_York", datetime.time(18, 0), None, None, ()))
        self.assertEqual(cal.dates, tuple(JAN_DATES))

    def test_it_is_an_invalid_file_when_it_breaks_its_format(self):
        bad = {
            "unknown zone": calendar_payload(JAN_DATES, timezone="Nowhere/Land"),
            "an exchange close on a rate calendar": calendar_payload(JAN_DATES, close={"default": "16:00"}),
            "no publication": json.dumps({k: v for k, v in json.loads(calendar_payload(JAN_DATES)).items() if k != "publication"}).encode(),
            "extra keys inside publication": json.dumps(dict(json.loads(calendar_payload(JAN_DATES)), publication={"time": "18:00", "other": "x"})).encode(),
            "a fixing block": calendar_payload(JAN_DATES, fixing={"time": "14:10", "publication": "16:00"}),
            "not a time": calendar_payload(JAN_DATES, publication="soon"),
            "unsorted dates": calendar_payload(list(reversed(JAN_DATES))),
        }
        for label, payload in bad.items():
            out = self.parse(payload)
            self.assertEqual(out.calendars, (), label)
            self.assertEqual([i.code for i in out.issues], [IssueCode.CALENDAR_INVALID], label)

    def test_a_publication_calendar_is_not_an_exchange_calendar(self):
        # the exchange-zone check is not applied to series ids (they are not MICs), and an exchange calendar still checks its MICs
        self.assertEqual(self.parse(calendar_payload(JAN_DATES, series=("ANY_SERIES_ID",))).issues, ())
        exchange = json.loads(calendar_payload(JAN_DATES))
        exchange.update(kind="EXCHANGE_SESSIONS", applies_to=["NOT_A_MIC"], close={"default": "16:00"})
        del exchange["publication"]
        self.assertEqual([i.code for i in self.parse(json.dumps(exchange).encode()).issues], [IssueCode.CALENDAR_INVALID])

    def test_the_contract_rules_for_each_kind(self):
        base = dict(calendar_id="X", applies_to=("S",), timezone="America/New_York", covers_from=D(2025, 1, 1), covers_to=D(2025, 1, 31), dates=(D(2025, 1, 2),), actual_through=D(2025, 1, 31),
                    evidence="e", prepared_by="p", prepared_on=D(2026, 10, 2), version_label="v", lineage=c.Lineage("s", c.AdjustmentStatus.RAW))
        c.CalendarDays(kind=c.CalendarKind.RATE_PUBLICATIONS, publication_time=datetime.time(18, 0), **base)
        for extra in ({}, {"publication_time": datetime.time(18, 0), "fixing_time": datetime.time(14, 10)}, {"publication_time": datetime.time(18, 0), "default_close": datetime.time(16, 0)}):
            with self.assertRaises(c.ObservationRuleError, msg=str(extra)):
                c.CalendarDays(kind=c.CalendarKind.RATE_PUBLICATIONS, **dict(base, **extra))
        with self.assertRaises(c.ObservationRuleError):  # an ECB calendar is still the ECB's
            c.CalendarDays(kind=c.CalendarKind.ECB_FIXINGS, fixing_time=datetime.time(14, 10), publication_time=datetime.time(16, 0), **base)


class PipelineTests(unittest.TestCase):
    """The files go through the real loader: registered files, the adapter registry, the source gates, the one-vintage rule and the derived release."""

    def build(self, extra_records=(), rf_sha=None, retrieved=None, files=None, release_sources=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        records = [SourceRecord(SOURCE_ID, "synthetic rf", "synthetic", "synthetic.rf", synthetic=True), SourceRecord(CAL_SOURCE, "calendar", "synthetic", "synthetic.cal", synthetic=True)] + list(extra_records)
        kit.write_registry(root, records)
        manifests = []
        for payload_format, kind, payload, label, source in (files or (
                (PAYLOAD_FORMAT, DataKind.RISK_FREE, make_risk_free_payload((rf_row(),)), "rf", SOURCE_ID),
                (CAL_FORMAT, DataKind.CALENDAR, calendar_payload(JAN_DATES), "cal", CAL_SOURCE))):
            manifests.append(kit.write_file(root, source, kind, payload_format, payload, label, "json", currency=USD if kind is DataKind.RISK_FREE else None,
                                            source_identifiers=(SERIES,) if kind is DataKind.RISK_FREE else (CAL_ID,)))
        adapters = AdapterRegistry([SyntheticRiskFreeAdapter(), CalendarFileAdapter()])
        release = MarketDataRelease.from_manifests("rf-world", manifests, release_sources or [SOURCE_ID])
        files_store = kit.FileStore(root)
        built = build_in_memory_market_data(release, files_store, files_store.load_registry(), adapters, kit.make_identity(), catalog_calendars={})
        return root, files_store, release, adapters, built, manifests

    def test_a_risk_free_file_and_its_calendar_load_and_serve_the_port(self):
        root, files, release, adapters, built, manifests = self.build()
        self.assertEqual([s.observation_count for s in built.summaries], [1, 1])
        self.assertEqual(built.issues, ())
        store = built.store
        conventions = market11_conventions(built.calendars)
        self.assertTrue(store.contains_synthetic)
        lookup = store.risk_free_on(USD, D(2025, 1, 6), conventions)
        self.assertEqual((lookup.outcome, lookup.date_used, lookup.missed_count, str(lookup.point.rate)), (LookupOutcome.FOUND, D(2025, 1, 6), 0, "3.66"))
        lookup = store.risk_free_on(USD, D(2025, 1, 8), conventions)  # the series' last quote is 01-06; the calendar lists 01-07 and 01-08: two publications missed
        self.assertEqual((lookup.date_used, lookup.missed_count), (D(2025, 1, 6), 2))
        lineage = lookup.series.lineage
        self.assertEqual((lineage.upstream, lineage.independence_group), ("synthetic", "synthetic.rf"))  # set from the source registry at ingest, never by the adapter
        self.assertEqual({r.adapter_id for r in lookup.consumed}, {"synthetic.riskfree.risk_free", "calendar.manual.calendar"})

    def test_the_whole_load_is_deterministic(self):
        a = self.build()[4]
        b = self.build()[4]
        self.assertEqual([s.normalized_digest for s in a.summaries], [s.normalized_digest for s in b.summaries])
        self.assertEqual(a.store.export().risk_free, b.store.export().risk_free)

    def test_a_real_risk_free_source_without_a_terms_attestation_is_refused_before_its_payload_is_read(self):
        real = SourceRecord("real.rf", "a real rate source", "Treasury", "treasury")  # no terms_check, not synthetic
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, [real, SourceRecord(CAL_SOURCE, "calendar", "synthetic", "synthetic.cal", synthetic=True)])
        m = kit.write_file(root, "real.rf", DataKind.RISK_FREE, PAYLOAD_FORMAT, b"NOT EVEN JSON", "rf", "json", usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, currency=USD,
                           source_identifiers=(SERIES,), retrieved_by="human")
        release = MarketDataRelease.from_manifests("real", [m], ["real.rf"])
        files = kit.FileStore(root)
        with self.assertRaises(SourceTermsNotAttestedError):
            build_in_memory_market_data(release, files, files.load_registry(), AdapterRegistry([SyntheticRiskFreeAdapter(source_id="real.rf")]), kit.make_identity(), catalog_calendars={})

    def test_an_attested_real_risk_free_source_still_needs_a_precision_profile(self):
        # PD-0031 attests the terms; Ruling 4.6 item 3 (precision) needs a profile too, and none exists until the first real file is profiled: fail closed
        real = SourceRecord("real.rf", "a real rate source", "Treasury", "treasury", terms_check=TermsCheck("owner", datetime.date(2026, 10, 2), True, "permitted (test)"))
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, [real])
        m = kit.write_file(root, "real.rf", DataKind.RISK_FREE, PAYLOAD_FORMAT, make_risk_free_payload((rf_row(),)), "rf", "json", usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY,
                           currency=USD, source_identifiers=(SERIES,), retrieved_by="human")
        release = MarketDataRelease.from_manifests("real", [m], ["real.rf"])
        files = kit.FileStore(root)
        with self.assertRaises(ProfileNotAdmittedError):
            build_in_memory_market_data(release, files, files.load_registry(), AdapterRegistry([SyntheticRiskFreeAdapter(source_id="real.rf")]), kit.make_identity(), catalog_calendars={})

    def test_a_synthetic_file_from_a_source_not_flagged_synthetic_is_refused(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, [SourceRecord(SOURCE_ID, "x", "synthetic", "synthetic.rf", terms_check=TermsCheck("o", datetime.date(2026, 10, 2), True, "n"))])  # attested, but NOT synthetic
        m = kit.write_file(root, SOURCE_ID, DataKind.RISK_FREE, PAYLOAD_FORMAT, make_risk_free_payload((rf_row(),)), "rf", "json", currency=USD, source_identifiers=(SERIES,))
        release = MarketDataRelease.from_manifests("x", [m], [SOURCE_ID])
        files = kit.FileStore(root)
        with self.assertRaises(IngestError):
            build_in_memory_market_data(release, files, files.load_registry(), AdapterRegistry([SyntheticRiskFreeAdapter()]), kit.make_identity(), catalog_calendars={})

    def test_two_vintages_of_one_series_fail_closed(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, [SourceRecord(SOURCE_ID, "x", "synthetic", "synthetic.rf", synthetic=True)])
        m1 = kit.write_file(root, SOURCE_ID, DataKind.RISK_FREE, PAYLOAD_FORMAT, make_risk_free_payload((rf_row(),)), "rf1", "json", currency=USD, source_identifiers=(SERIES,))
        m2 = kit.write_file(root, SOURCE_ID, DataKind.RISK_FREE, PAYLOAD_FORMAT, make_risk_free_payload((rf_row(points=[{"date": "2025-01-02", "rate": "3.70"}]),)), "rf2", "json",
                            currency=USD, source_identifiers=(SERIES,))
        with self.assertRaises(TwoVintagesError):
            MarketDataRelease.from_manifests("two", [m1, m2], [SOURCE_ID])  # caught at the release; the load repeats the check on the loaded data (below)
        release = MarketDataRelease(name="two", files=tuple(sorted({m1.file_sha256, m2.file_sha256})), source_precedence=(SOURCE_ID,))
        files = kit.FileStore(root)
        with self.assertRaises(TwoVintagesError):
            build_in_memory_market_data(release, files, files.load_registry(), AdapterRegistry([SyntheticRiskFreeAdapter()]), kit.make_identity(), catalog_calendars={})

    def test_a_file_the_adapter_cannot_translate_yields_issues_and_no_series(self):
        files = ((PAYLOAD_FORMAT, DataKind.RISK_FREE, make_risk_free_payload((rf_row(quote_type="NOPE"),)), "rf", SOURCE_ID), (CAL_FORMAT, DataKind.CALENDAR, calendar_payload(JAN_DATES), "cal", CAL_SOURCE))
        _root, _files, _release, _adapters, built, _m = self.build(files=files)
        self.assertEqual([i.code for _sha, i in built.issues], [IssueCode.UNPARSEABLE_ROW])
        self.assertEqual(built.store.export().risk_free, ())
        self.assertEqual(built.store.risk_free_on(USD, D(2025, 1, 6), market11_conventions(built.calendars)).outcome, LookupOutcome.NOT_IN_RELEASE)

    def test_the_derived_release_for_current_mode_leaves_out_a_series_retrieved_after_the_instant(self):
        from performance_service.derived_release import DerivedReleaseView  # noqa: PLC0415

        root, files, release, adapters, built, manifests = self.build()
        view = DerivedReleaseView(release, files, files.load_registry(), adapters, kit.make_identity(), catalog_calendars={})
        before = kit.RETRIEVED - datetime.timedelta(days=1)
        early = view.view(before)  # t is before the files were retrieved: nothing of M_t (no rate, no calendar)
        self.assertEqual(early.port.risk_free_on(USD, D(2025, 1, 6), early.conventions).outcome, LookupOutcome.NOT_IN_RELEASE)
        self.assertEqual(set(early.excluded_files), {m.file_sha256 for m in manifests})
        late = view.view(kit.RETRIEVED + datetime.timedelta(days=1))
        self.assertEqual(late.port.risk_free_on(USD, D(2025, 1, 6), late.conventions).outcome, LookupOutcome.FOUND)
        self.assertEqual(late.excluded_files, ())
        self.assertNotEqual(early.port.release_id(), late.port.release_id())  # a different M_t is a different release id
        self.assertEqual(late.parent_release_id, release.release_id)

    def test_a_projection_without_a_risk_free_series_has_the_document_it_always_had(self):
        from persistence.market_data_store import projection_obj  # noqa: PLC0415

        root, files, release, adapters, built, manifests = self.build()
        contents = built.store.export()
        with_rf = projection_obj(release, contents, built.calendars)
        self.assertIn("risk_free", with_rf)
        without = projection_obj(release, dataclasses.replace(contents, risk_free=()), built.calendars)
        self.assertEqual(set(without), {"release_id", "convention_set_id", "contains_synthetic", "readings", "benchmarks", "adjusted", "fx_windows", "exclusions", "calendars"})
        self.assertNotIn("risk_free", without)


if __name__ == "__main__":
    unittest.main()
