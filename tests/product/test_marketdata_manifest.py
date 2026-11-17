"""Canonical encodings, file manifest, release, data-set reference, file verification,
source terms gate and the one-vintage rule (Tech Plan §15.3; market-data/1.0 Ruling 0.1)."""

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

from marketdata.adapters.mock import MOCK_FORMAT, MOCK_SOURCE_ID, make_synthetic_payload  # noqa: E402
from marketdata.canonical import (  # noqa: E402
    CanonicalEncodingError,
    canonical_decimal,
    canonical_json,
    sha256_hex,
)
from marketdata.contracts import AdjustmentStatus, UsageScope  # noqa: E402
from marketdata.files import FileHashMismatchError, FileNotInStoreError, FileStore  # noqa: E402
from marketdata.manifest import (  # noqa: E402
    CONVENTION_SET_ID,
    DataKind,
    DataSetRef,
    FileManifest,
    FileRef,
    ManifestError,
    MarketDataRelease,
    SourceRecord,
    SourceRegistry,
    SourceTermsNotAttestedError,
    TermsCheck,
    TwoVintagesError,
)

SHA_A, SHA_B = "a" * 64, "b" * 64


class CanonicalTests(unittest.TestCase):
    def test_decimal_text_is_exact_without_exponent_or_trailing_zeros(self):
        cases = {"150.20": "150.2", "150.2": "150.2", "0.0": "0", "1E+3": "1000", "-0.00120": "-0.0012",
                 "100": "100", "1.5E-7": "0.00000015"}
        for given, want in cases.items():
            self.assertEqual(canonical_decimal(Decimal(given)), want, given)

    def test_floats_and_non_finite_are_refused(self):
        with self.assertRaises(CanonicalEncodingError):
            canonical_json({"x": 1.5})
        with self.assertRaises(CanonicalEncodingError):
            canonical_decimal(Decimal("NaN"))

    def test_fraction_is_written_in_lowest_terms(self):
        self.assertEqual(canonical_json({"r": Fraction(84512, 10823)}), '{"r":"84512/10823"}')
        self.assertEqual(canonical_json({"r": Fraction(2, 4)}), '{"r":"1/2"}')

    def test_key_order_does_not_matter(self):
        self.assertEqual(canonical_json({"b": 1, "a": 2}), canonical_json({"a": 2, "b": 1}))


class ManifestTests(unittest.TestCase):
    def manifest(self, **kw):
        base = dict(
            file_sha256=SHA_A, size_bytes=3, payload_filename="f.json", payload_format="x/1",
            source_id="src", data_kind=DataKind.QUOTE, retrieval_time=kit.RETRIEVED,
            retrieved_by="human", declared_adjustment=AdjustmentStatus.UNDECLARED,
            usage_scope=UsageScope.INTERNAL_DEVELOPMENT_ONLY)
        base.update(kw)
        return FileManifest(**base)

    def test_round_trip_is_exact(self):
        m = self.manifest(declared_currency=kit.USD, request=(("symbol", "AAPL"),),
                          source_identifiers=("AAPL",), libraries=(("akshare", "1.2.3"),),
                          script_name="t", script_version="0.1", script_sha256=SHA_B,
                          adjustment_anchor="qfq", market="US")
        self.assertEqual(FileManifest.from_json(m.to_json()), m)
        self.assertEqual(m.to_json(), FileManifest.from_json(m.to_json()).to_json())

    def test_malformed_manifests_are_refused(self):
        with self.assertRaises(ManifestError):
            self.manifest(file_sha256="nothex")
        with self.assertRaises(ManifestError):
            self.manifest(retrieval_time=datetime.datetime(2025, 1, 1))  # naive
        with self.assertRaises(ManifestError):
            self.manifest(retrieved_by="agent")
        with self.assertRaises(ManifestError):
            FileManifest.from_json("{not json")

    def test_series_keys_identify_symbol_adjustment_and_anchor(self):
        m = self.manifest(source_identifiers=("B", "A"), adjustment_anchor="qfq")
        self.assertEqual([k[2] for k in m.series_keys()], ["A", "B"])
        self.assertEqual(self.manifest().series_keys()[0][2], "*")


class ReleaseTests(unittest.TestCase):
    def manifest(self, sha, symbols=("AAPL",), adjustment=AdjustmentStatus.RAW, anchor=None, source="src"):
        return FileManifest(
            file_sha256=sha, size_bytes=1, payload_filename="f", payload_format="x/1", source_id=source,
            data_kind=DataKind.QUOTE, retrieval_time=kit.RETRIEVED, retrieved_by="human",
            declared_adjustment=adjustment, usage_scope=UsageScope.INTERNAL_DEVELOPMENT_ONLY,
            source_identifiers=symbols, adjustment_anchor=anchor)

    def test_release_id_is_the_hash_of_its_content_and_records_the_convention_set(self):
        r = MarketDataRelease.from_manifests("r", [self.manifest(SHA_B), self.manifest(SHA_A, ("MSFT",))],
                                             ["src"])
        self.assertEqual(r.files, (SHA_A, SHA_B))  # sorted
        self.assertEqual(r.convention_set_id, "market-data/1.16")  # section 11 item 13 (1.7)
        self.assertEqual(CONVENTION_SET_ID, "market-data/1.16")
        self.assertEqual(len(r.release_id), 64)
        self.assertEqual(MarketDataRelease.from_json(r.to_json()), r)
        same = MarketDataRelease.from_manifests("r", [self.manifest(SHA_A, ("MSFT",)), self.manifest(SHA_B)],
                                                ["src"])
        self.assertEqual(same.release_id, r.release_id)  # input order is irrelevant
        other = MarketDataRelease.from_manifests("r2", [self.manifest(SHA_B), self.manifest(SHA_A, ("MSFT",))],
                                                 ["src"])
        self.assertNotEqual(other.release_id, r.release_id)

    def test_tampered_release_is_refused(self):
        r = MarketDataRelease.from_manifests("r", [self.manifest(SHA_A)], ["src"])
        obj = json.loads(r.to_json())
        obj["files"] = [SHA_B]
        with self.assertRaises(ManifestError):
            MarketDataRelease.from_json(json.dumps(obj))

    def test_two_vintages_of_one_series_fail_closed_never_the_latest(self):
        with self.assertRaises(TwoVintagesError):
            MarketDataRelease.from_manifests(
                "r", [self.manifest(SHA_A, ("AAPL", "MSFT")), self.manifest(SHA_B, ("MSFT",))], ["src"])

    def test_different_adjustment_or_anchor_or_source_is_a_different_series(self):
        MarketDataRelease.from_manifests("r", [
            self.manifest(SHA_A), self.manifest(SHA_B, adjustment=AdjustmentStatus.UNDECLARED, anchor="qfq"),
            self.manifest("c" * 64, source="other")], ["src", "other"])

    def test_precedence_must_not_repeat(self):
        with self.assertRaises(ManifestError):
            MarketDataRelease.from_manifests("r", [self.manifest(SHA_A)], ["src", "src"])


class DataSetRefTests(unittest.TestCase):
    def test_ref_is_canonical_sorted_and_carries_the_convention_set(self):
        a, b = FileRef(SHA_A, "ad", "1"), FileRef(SHA_B, "ad", "1")
        r1 = DataSetRef.build(DataKind.QUOTE, SHA_A, [b, a, a], {"x": "1"})
        r2 = DataSetRef.build(DataKind.QUOTE, SHA_A, [a, b], {"x": "1"})
        self.assertEqual(r1, r2)
        self.assertEqual(r1.ref_id, r2.ref_id)
        self.assertEqual(r1.consumed, (a, b))
        self.assertEqual(r1.convention_set_id, "market-data/1.16")
        self.assertNotEqual(r1.ref_id, DataSetRef.build(DataKind.FX, SHA_A, [a, b], {"x": "1"}).ref_id)
        with self.assertRaises(ManifestError):
            DataSetRef(DataKind.QUOTE, SHA_A, (b, a))  # unsorted


class RegistryTests(unittest.TestCase):
    def test_terms_gate(self):
        ok = SourceRecord("a", "A", "up", "g", terms_check=TermsCheck("owner", datetime.date(2025, 1, 5), True))
        no = SourceRecord("b", "B", "up", "g", terms_check=TermsCheck("owner", datetime.date(2025, 1, 5), False))
        none = SourceRecord("c", "C", "up", "g")
        synth = SourceRecord("d", "D", "synthetic", "g2", synthetic=True)
        reg = SourceRegistry([ok, no, none, synth])
        reg.require_attested("a")
        reg.require_attested("d")
        for sid in ("b", "c"):
            with self.assertRaises(SourceTermsNotAttestedError):
                reg.require_attested(sid)
        with self.assertRaises(ManifestError):
            SourceRegistry([ok, ok])

    def test_registry_json(self):
        text = json.dumps({"sources": [{
            "source_id": "a", "name": "A", "upstream_provider": "u", "independence_group": "g",
            "terms_check": {"checked_by": "owner", "checked_on": "2025-01-05",
                            "permits_internal_development_use": True}}]})
        self.assertTrue(SourceRegistry.from_json(text).get("a").terms_attested)
        with self.assertRaises(ManifestError):
            SourceRegistry.from_json("{}")


class FileStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        kit.write_registry(self.root)
        self.payload = make_synthetic_payload(quotes=({"ticker": "AAPL", "mic": "XNAS",
                                                       "date": "2025-01-02", "close": "1"},))
        self.manifest = kit.write_file(self.root, MOCK_SOURCE_ID, DataKind.QUOTE, MOCK_FORMAT,
                                       self.payload, "q", "json", currency=kit.USD)
        self.store = FileStore(self.root)

    def test_verified_read_returns_the_exact_bytes(self):
        v = self.store.read_by_hash(self.manifest.file_sha256)
        self.assertEqual(v.payload, self.payload)
        self.assertEqual(v.manifest, self.manifest)
        self.assertEqual(sha256_hex(v.payload), self.manifest.file_sha256)

    def test_an_edited_payload_is_refused(self):
        path = next((self.root / "files").rglob("q.json"))
        path.write_bytes(self.payload.replace(b'"1"', b'"2"'))
        with self.assertRaises(FileHashMismatchError):
            self.store.read_by_hash(self.manifest.file_sha256)

    def test_a_truncated_or_missing_payload_is_refused(self):
        path = next((self.root / "files").rglob("q.json"))
        path.write_bytes(self.payload[:-1])
        with self.assertRaises(FileHashMismatchError):
            self.store.read_by_hash(self.manifest.file_sha256)
        path.unlink()
        with self.assertRaises(FileNotInStoreError):
            self.store.read_by_hash(self.manifest.file_sha256)

    def test_unknown_hash_and_registry_load(self):
        with self.assertRaises(FileNotInStoreError):
            self.store.read_by_hash("f" * 64)
        self.assertTrue(self.store.load_registry().get(MOCK_SOURCE_ID).synthetic)

    def test_release_files_round_trip_through_the_store(self):
        release = MarketDataRelease.from_manifests("r", [self.manifest], [MOCK_SOURCE_ID])
        (self.root / "releases").mkdir()
        (self.root / "releases" / f"{release.release_id}.json").write_text(release.to_json(), encoding="utf-8")
        self.assertEqual(self.store.load_release(release.release_id), release)


if __name__ == "__main__":
    unittest.main()
