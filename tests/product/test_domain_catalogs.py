"""The benchmark and risk-free catalogs (`domain.catalogs`, `risk_service.catalogs`): the committed files, the rules, and the selection's catalog check.

The committed files are the main session's and have NO entries (PD-0039 D1, PD-0040): every id is refused today. Tests that need an entry build their own catalog from the same classes (a synthetic series is never
catalogued, market-data Ruling 4.8).
"""

import datetime
import json
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from domain.benchmark_selection import BenchmarkSelection, Origin, RecordType  # noqa: E402
from domain.catalogs import (  # noqa: E402
    BenchmarkCatalog,
    BenchmarkNotInCatalogError,
    CatalogError,
    CatalogVersionMismatchError,
    ReturnBasis,
    SeriesForm,
    admit_selection,
    catalog_version_of,
    parse_benchmark_catalog,
    parse_risk_free_catalog,
)
from risk_service import catalogs as files  # noqa: E402

PID = uuid.UUID("d4000000-0000-4000-8000-000000000001")


def entry(**kw):
    row = {"benchmark_id": "TEST_TR", "name": "Test index", "provider": "test", "source_id": "src", "licensing": "none", "currency": "USD", "return_basis": "TOTAL_RETURN_GROSS",
           "dividend_treatment": "reinvested", "calendar_id": "CAL", "series_form": "LEVELS", "proxy_of": None, "synthetic": False}
    row.update(kw)
    return row


def catalog(entries, catalog_id="test:1", **extra):
    return json.dumps(dict({"catalog_id": catalog_id, "entries": entries, "candidates": []}, **extra)).encode("utf-8")


def select(benchmark_id="TEST_TR", **kw):
    return BenchmarkSelection(uuid.uuid4(), PID, RecordType.SELECT, datetime.date(2026, 1, 5), benchmark_id=benchmark_id, origin=Origin.USER_CHOSEN, **kw)


class CommittedFilesTests(unittest.TestCase):
    def test_the_benchmark_catalog_loads_and_has_no_entries(self):
        cat = files.load_benchmark_catalog()
        self.assertEqual((cat.catalog_id, cat.entries), ("benchmarks:1", ()))

    def test_the_risk_free_catalog_loads_and_has_no_entries(self):
        cat = files.load_risk_free_catalog()
        self.assertEqual((cat.catalog_id, cat.entries), ("risk_free:1", ()))
        self.assertIsNone(cat.for_currency("USD"))

    def test_every_id_is_refused_by_the_committed_catalog(self):
        with self.assertRaises(BenchmarkNotInCatalogError):
            admit_selection(select("SPX"), files.load_benchmark_catalog())

    def test_a_missing_file_is_an_error_not_an_empty_catalog(self):
        with self.assertRaises(CatalogError):
            files.load_benchmark_catalog(ROOT / "no_such_directory")


class BenchmarkCatalogTests(unittest.TestCase):
    def test_an_entry_is_parsed_with_every_field(self):
        cat = parse_benchmark_catalog(catalog([entry(proxy_of="Some index")]))
        (e,) = cat.entries
        self.assertEqual((e.benchmark_id, e.return_basis, e.series_form, e.calendar_id, e.currency, e.proxy_of), ("TEST_TR", ReturnBasis.TOTAL_RETURN_GROSS, SeriesForm.LEVELS, "CAL", "USD", "Some index"))
        self.assertTrue(e.return_basis.is_total_return)
        self.assertFalse(ReturnBasis.PRICE_RETURN.is_total_return)

    def test_a_synthetic_entry_is_refused_in_the_committed_form_and_allowed_only_in_a_test_catalog(self):
        raw = catalog([entry(synthetic=True)])
        with self.assertRaises(CatalogError):
            parse_benchmark_catalog(raw)
        self.assertTrue(parse_benchmark_catalog(raw, allow_synthetic=True).synthetic)

    def test_a_malformed_catalog_fails_closed(self):
        for raw in (b"not json", b"[]", catalog("x"), catalog([entry(return_basis="NET")]), catalog([entry(series_form="MONTHLY")]), catalog([entry(currency="usd")]),
                    catalog([entry(benchmark_id="")]), catalog([entry(benchmark_id="bad id")]), catalog([entry(synthetic="no")]), catalog([entry(), entry()]), catalog([entry(calendar_id=" ")]),
                    json.dumps({"entries": []}).encode(), catalog([entry(), "text"])):
            with self.assertRaises(CatalogError, msg=raw):
                parse_benchmark_catalog(raw)

    def test_a_missing_field_is_an_error_nothing_is_defaulted(self):
        for field in ("name", "provider", "source_id", "licensing", "currency", "return_basis", "dividend_treatment", "calendar_id", "series_form", "synthetic"):
            row = entry()
            del row[field]
            with self.assertRaises(CatalogError, msg=field):
                parse_benchmark_catalog(catalog([row]))

    def test_candidates_are_never_read(self):
        poisoned = catalog([entry()], candidates=[{"benchmark_id": "CANDIDATE", "return_basis": "garbage"}, "not even an object"])
        cat = parse_benchmark_catalog(poisoned)
        self.assertEqual([e.benchmark_id for e in cat.entries], ["TEST_TR"])
        self.assertIsNone(cat.get("CANDIDATE"))
        self.assertEqual(cat.digest, parse_benchmark_catalog(catalog([entry()])).digest)  # a change to a candidate, a rule or a date changes no result

    def test_the_digest_follows_the_entries_and_the_id(self):
        base = parse_benchmark_catalog(catalog([entry()]))
        self.assertNotEqual(base.digest, parse_benchmark_catalog(catalog([entry(return_basis="PRICE_RETURN")])).digest)
        self.assertNotEqual(base.digest, parse_benchmark_catalog(catalog([entry()], catalog_id="test:2")).digest)
        self.assertNotEqual(base.digest, parse_benchmark_catalog(catalog([entry(name="Another name")])).digest)  # ANY field of an entry
        self.assertEqual(base.digest, parse_benchmark_catalog(catalog([entry()], updated="2030-01-01", owner="someone else")).digest)

    def test_entries_are_ordered_by_id_whatever_the_file_says(self):
        a, b = parse_benchmark_catalog(catalog([entry(benchmark_id="B"), entry(benchmark_id="A")])), parse_benchmark_catalog(catalog([entry(benchmark_id="A"), entry(benchmark_id="B")]))
        self.assertEqual((a.digest, [e.benchmark_id for e in a.entries]), (b.digest, ["A", "B"]))

    def test_a_catalog_id_must_be_usable_as_a_catalog_version(self):
        with self.assertRaises(CatalogError):
            BenchmarkCatalog("has space", ())


class AdmitSelectionTests(unittest.TestCase):
    def setUp(self):
        self.cat = parse_benchmark_catalog(catalog([entry()]))

    def test_a_select_of_an_entry_is_stamped_with_the_catalog_id(self):
        admitted = admit_selection(select(), self.cat)
        self.assertEqual(admitted.catalog_version, "test:1")  # the catalog's id itself
        self.assertEqual(admit_selection(admitted, self.cat), admitted)  # idempotent

    def test_the_catalog_version_is_the_catalog_id_and_an_id_with_a_slash_is_refused_never_mapped(self):
        for ok in ("benchmarks:1", "risk_free:1", "plain.1", "a-b_c+d:2"):
            self.assertEqual(catalog_version_of(ok), ok)
        for bad in ("benchmarks/1", "risk_free/1", "", " x", "x" * 65, ":1", "a b"):
            with self.assertRaises(CatalogError, msg=bad):
                catalog_version_of(bad)
        with self.assertRaises(CatalogError):  # a catalog file whose id has a slash is refused when read, so it cannot be admitted under
            parse_benchmark_catalog(catalog([entry()], catalog_id="benchmarks/1"))
        with self.assertRaises(CatalogError):
            parse_risk_free_catalog(json.dumps({"catalog_id": "risk_free/1", "entries": []}).encode())
        # two ids can never store the same version: the committed ids are stored as they are
        select(catalog_version=catalog_version_of(files.load_benchmark_catalog().catalog_id))  # constructs: the domain pattern is the stored pattern

    def test_a_select_of_a_non_entry_is_refused_with_the_id(self):
        with self.assertRaises(BenchmarkNotInCatalogError) as caught:
            admit_selection(select("OTHER"), self.cat)
        self.assertEqual((caught.exception.benchmark_id, caught.exception.catalog_id), ("OTHER", "test:1"))

    def test_a_candidate_cannot_be_selected(self):
        cat = parse_benchmark_catalog(catalog([entry()], candidates=[entry(benchmark_id="CAND")]))
        with self.assertRaises(BenchmarkNotInCatalogError):
            admit_selection(select("CAND"), cat)

    def test_another_catalog_version_is_refused_not_restamped(self):
        with self.assertRaises(CatalogVersionMismatchError):
            admit_selection(select(catalog_version="test:0"), self.cat)

    def test_a_clear_and_a_reversal_name_no_benchmark_and_pass_unchanged(self):
        clear = BenchmarkSelection(uuid.uuid4(), PID, RecordType.CLEAR, datetime.date(2026, 1, 5))
        reversal = BenchmarkSelection(uuid.uuid4(), PID, RecordType.REVERSAL, datetime.date(2026, 1, 5), reverses_selection_id=uuid.uuid4())
        self.assertIs(admit_selection(clear, self.cat), clear)
        self.assertIs(admit_selection(reversal, self.cat), reversal)


class RiskFreeCatalogTests(unittest.TestCase):
    ROW = {"currency": "USD", "series_id": "S", "source_id": "src", "instrument": "SOVEREIGN_BILL", "tenor_days": 91, "quote_type": "SIMPLE_YIELD", "day_count_basis": "365", "unit": "PERCENT",
           "decimals_published": 2, "date_semantics": "the date the quote is for", "calendar_id": "RF_CAL", "revision_policy": "NOT_REVISED"}

    def raw(self, *rows):
        return json.dumps({"catalog_id": "rf:1", "entries": list(rows)}).encode("utf-8")

    def test_one_series_per_currency(self):
        cat = parse_risk_free_catalog(self.raw(self.ROW))
        self.assertTrue(cat.admits("USD", "S"))
        self.assertFalse(cat.admits("USD", "OTHER"))
        self.assertFalse(cat.admits("HKD", "S"))  # never another currency's series
        with self.assertRaises(CatalogError):
            parse_risk_free_catalog(self.raw(self.ROW, dict(self.ROW, series_id="T")))

    def test_a_malformed_entry_fails_closed(self):
        for row in (dict(self.ROW, currency="usd"), dict(self.ROW, tenor_days=-1), dict(self.ROW, tenor_days=True), dict(self.ROW, decimals_published="2"), {k: v for k, v in self.ROW.items() if k != "calendar_id"}):
            with self.assertRaises(CatalogError, msg=row):
                parse_risk_free_catalog(self.raw(row))
        with self.assertRaises(CatalogError):
            parse_risk_free_catalog(b"{")

    def test_the_digest_follows_the_entries(self):
        self.assertNotEqual(parse_risk_free_catalog(self.raw(self.ROW)).digest, parse_risk_free_catalog(self.raw(dict(self.ROW, unit="DECIMAL"))).digest)


if __name__ == "__main__":
    unittest.main()
