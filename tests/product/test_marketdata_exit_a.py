"""CP2 exit criterion, first half (Tech Plan §15.9): one analytics-facing consumer, run
UNCHANGED over several adapters and a mock.

    "same internal analytics contract can consume test data from more than one adapter/mock
     without business-logic change" (PRD §38.3)

CP2a covers: the mock adapter, two hand-made source formats (test-local adapters), one mixed
release (quotes from one source, FX from another), and a further novel adapter added with no
production edit. The expected values below were written by hand from the synthetic facts in
`marketdata_testkit`; the Quant authors the CP2c fixture expectations (market-data/1.0 MD-OI-7).
The consumer is exercised with the PLACEHOLDER conventions only (exact-date, no assessed
freshness), so the result states `conformant: False` and carries the placeholder ids.
"""

import datetime
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_testkit as kit  # noqa: E402

from marketdata import contracts as c  # noqa: E402
from marketdata.adapters.base import AdapterOutput, AdapterRegistry  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from marketdata.conventions import PLACEHOLDER_IDS, placeholder_conventions  # noqa: E402
from marketdata.consumption import ValuationInputsError, assemble_valuation_inputs  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, MarketDataRelease  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CONSUMER = REPO / "src" / "marketdata" / "consumption.py"
AS_OF = kit.DAY1
REPORTING = kit.USD


def consumer_body(port, identity):
    """THE test body: written once, it calls only `assemble_valuation_inputs`."""
    state = kit.replayed_state(identity, AS_OF)
    return assemble_valuation_inputs(port, identity, state, AS_OF, REPORTING, placeholder_conventions())


def port_for(root: Path, flavour: str):
    """Build a port through the full real path: files, hash verification, adapters, resolution,
    store, release. `flavour` is a source (mock, csv, jsonl) or 'mixed'."""
    identity = kit.make_identity()
    if flavour == "mixed":
        files, release, adapters = _mixed_world(root)
    elif flavour == "tsv":
        files, release, adapters = _tsv_world(root)
    else:
        files, release, adapters = kit.build_world(root, flavour)
    built = build_in_memory_market_data(release, files, files.load_registry(), adapters, identity, catalog_calendars={})
    assert built.issues == () and built.exceptions == (), (built.issues, built.exceptions)
    return built.store, identity, release


def _mixed_world(root: Path):
    """Quotes from the jsonl source, FX from the csv source, one release."""
    kit.write_registry(root)
    manifests = []
    by_ccy = {}
    for q in kit.QUOTES:
        by_ccy.setdefault(q[5], []).append(q)
    for ccy, rows in by_ccy.items():
        manifests.append(kit.write_file(
            root, kit.JSONL_SOURCE, DataKind.QUOTE, kit.JSONL_FORMAT, kit.jsonl_quotes_payload(tuple(rows)),
            f"quotes_{ccy.code}", "jsonl", currency=ccy, source_identifiers=tuple(sorted({r[0] for r in rows}))))
    manifests.append(kit.write_file(root, kit.CSV_SOURCE, DataKind.FX, kit.CSV_FORMAT, kit.csv_fx_payload(),
                                    "fx", "csv", source_identifiers=("HKD", "CNY")))
    adapters = AdapterRegistry([kit.JsonlQuoteAdapter(), kit.CsvFXAdapter()])
    release = MarketDataRelease.from_manifests("mixed", manifests, [kit.JSONL_SOURCE, kit.CSV_SOURCE])
    return FileStore(root), release, adapters


class TsvQuoteAdapter:
    """A NOVEL adapter, written only for this test, for a format no production code knows."""

    adapter_id = "testvendor.tsv.quotes"
    adapter_version = "0.0.1"
    source_id = "testvendor.tsv"
    data_kind = DataKind.QUOTE
    payload_formats = ("testvendor_tsv/1",)

    def translate(self, manifest, payload):
        rows = []
        for i, line in enumerate(payload.decode("utf-8").splitlines()):
            ticker, mic, day, close, volume = line.split("\t")
            rows.append(c.UnresolvedQuote(
                c.ExternalIdentifiers(ticker=ticker, mic=mic), datetime.date.fromisoformat(day),
                Decimal(close), manifest.declared_currency, kit.timing_for(manifest),
                kit.lineage_for(manifest, self, f"line{i}", source_value_text=close), volume=Decimal(volume)))
        return AdapterOutput(quotes=tuple(rows))


def _tsv_world(root: Path):
    """Quotes through the novel TSV adapter, FX through the csv adapter."""
    kit.write_registry(root, extra=[kit.SourceRecord("testvendor.tsv", "TSV", "synthetic", "synthetic.tsv",
                                                     synthetic=True)])
    manifests = []
    by_ccy = {}
    for q in kit.QUOTES:
        by_ccy.setdefault(q[5], []).append(q)
    for ccy, rows in by_ccy.items():
        text = "".join(f"{t}\t{m}\t{d.isoformat()}\t{close}\t{v}\n" for t, m, d, close, v, _ in rows)
        manifests.append(kit.write_file(
            root, "testvendor.tsv", DataKind.QUOTE, "testvendor_tsv/1", text.encode("utf-8"),
            f"quotes_{ccy.code}", "tsv", currency=ccy, source_identifiers=tuple(sorted({r[0] for r in rows}))))
    manifests.append(kit.write_file(root, kit.CSV_SOURCE, DataKind.FX, kit.CSV_FORMAT, kit.csv_fx_payload(),
                                    "fx", "csv", source_identifiers=("HKD", "CNY")))
    adapters = AdapterRegistry([TsvQuoteAdapter(), kit.CsvFXAdapter()])
    release = MarketDataRelease.from_manifests("tsv", manifests, ["testvendor.tsv", kit.CSV_SOURCE])
    return FileStore(root), release, adapters


def expected_value_obj(identity):
    lid = lambda t, m: str(kit.listing_id(identity, t, m))  # noqa: E731
    quote = lambda t, m, ccy, price: {  # noqa: E731
        "listing_id": lid(t, m), "native_currency": ccy, "outcome": "FOUND", "value_date": "2025-01-02",
        "price": price, "currency": ccy, "reconciliation": "SINGLE_SOURCE", "freshness": "UNKNOWN"}
    quotes = sorted([quote("AAPL", "XNAS", "USD", "150.25"), quote("0700", "XHKG", "HKD", "330.4"),
                     quote("600519", "XSHG", "CNY", "1500")], key=lambda q: q["listing_id"])
    pos = lambda t, m, qty: {  # noqa: E731
        "account_id": str(kit.uuid.UUID(int=1)), "listing_id": lid(t, m), "quantity": qty, "state": "AVAILABLE"}
    positions = [pos("AAPL", "XNAS", "10"), pos("0700", "XHKG", "100"), pos("600519", "XSHG", "2")]
    return {
        "as_of": "2025-01-02", "reporting_currency": "USD",
        "positions": sorted(positions, key=lambda p: p["listing_id"]),
        "quotes": quotes,
        "fx": [
            {"currency": "CNY", "outcome": "FOUND", "rate": "137/1000", "reconciliation": "SINGLE_SOURCE",
             "freshness": ["UNKNOWN"]},
            {"currency": "HKD", "outcome": "FOUND", "rate": "161/1250", "reconciliation": "SINGLE_SOURCE",
             "freshness": ["UNKNOWN"]},
        ],
    }


def normalize(obj):
    """Round-trip through canonical JSON so Decimals/Fractions/dates compare as their bytes."""
    import json
    return json.loads(canonical_json(obj))


class ExitCriterionFirstHalf(unittest.TestCase):
    FLAVOURS = ("mock", "csv", "jsonl", "mixed", "tsv")

    def run_all(self):
        results = {}
        for flavour in self.FLAVOURS:
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            port, identity, release = port_for(Path(tmp.name), flavour)
            results[flavour] = (consumer_body(port, identity), identity, release)
        return results

    def test_same_consumer_same_values_over_every_adapter_and_the_mock(self):
        before = hashlib.sha256(CONSUMER.read_bytes()).hexdigest()
        results = self.run_all()
        values = {f: canonical_json(r[0].value_obj()) for f, r in results.items()}
        self.assertEqual(len(set(values.values())), 1, values)  # byte-identical value part
        identity = results["mock"][1]
        self.assertEqual(normalize(results["mock"][0].value_obj()), normalize(expected_value_obj(identity)))
        self.assertEqual(before, hashlib.sha256(CONSUMER.read_bytes()).hexdigest())  # no business-logic edit

    def test_lineage_differs_and_names_the_exact_files_and_adapters(self):
        results = self.run_all()
        seen_files = set()
        for flavour, (inputs, _, release) in results.items():
            consumed = {r for ref in inputs.data_set_refs for r in ref.consumed}
            self.assertTrue(consumed, flavour)
            self.assertTrue({r.file_sha256 for r in consumed} <= set(release.files), flavour)
            seen_files |= {r.file_sha256 for r in consumed}
            self.assertEqual({ref.release_id for ref in inputs.data_set_refs}, {release.release_id})
            self.assertEqual({ref.kind for ref in inputs.data_set_refs}, {DataKind.QUOTE, DataKind.FX})
            for ref in inputs.data_set_refs:
                self.assertEqual(ref.convention_set_id, "market-data/1.16")  # section 11 item 13 (1.7)
        lineages = {f: canonical_json(r[0].lineage_obj()) for f, r in results.items()}
        self.assertEqual(len(set(lineages.values())), len(self.FLAVOURS))  # provenance differs per adapter
        adapters = {f: {a.adapter_id for ref in r[0].data_set_refs for a in ref.consumed}
                    for f, r in results.items()}
        self.assertEqual(adapters["mock"], {"mock.synthetic.quote", "mock.synthetic.fx"})
        self.assertEqual(adapters["tsv"], {"testvendor.tsv.quotes", "testvendor.csv.fx"})
        self.assertEqual(adapters["mixed"], {"testvendor.jsonl.quotes", "testvendor.csv.fx"})

    def test_the_result_does_not_claim_conformance_while_placeholders_are_injected(self):
        (inputs, _, _) = self.run_all()["mock"]
        self.assertFalse(inputs.conformant)
        ids = dict(inputs.convention_ids)
        self.assertEqual(ids["convention_set"], "market-data/1.16")  # 1.7
        self.assertEqual(set(inputs_placeholders(ids)), set(PLACEHOLDER_IDS))  # freshness, price of date, FX
        self.assertTrue(ids["reconciliation"].startswith("market-data/1.16#"))  # reconciliation is implemented

    def test_the_consumer_applies_no_arithmetic_and_chooses_no_value_itself(self):
        (inputs, _, _) = self.run_all()["mock"]
        for q in inputs.quotes:
            self.assertIs(q.lookup.outcome, LookupOutcome.FOUND)
        # positions pass through replay's own MetricResult untouched
        self.assertEqual(sorted(p.quantity.value for p in inputs.positions),
                         [Decimal(2), Decimal(10), Decimal(100)])

    def test_missing_data_is_stated_not_filled(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        port, identity, _ = port_for(Path(tmp.name), "csv")
        later = datetime.date(2025, 1, 6)  # a date the files do not cover
        state = kit.replayed_state(identity, later)
        inputs = assemble_valuation_inputs(port, identity, state, later, REPORTING, placeholder_conventions())
        self.assertEqual({q.lookup.outcome for q in inputs.quotes}, {LookupOutcome.NO_OBSERVATION})
        self.assertEqual({f.lookup.outcome for f in inputs.fx}, {LookupOutcome.NO_OBSERVATION})
        self.assertTrue(all(q.lookup.selected is None for q in inputs.quotes))
        self.assertTrue(all(f.lookup.rate is None for f in inputs.fx))

    def test_a_cnh_balance_is_not_translated_with_the_cny_rate(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        port, identity, _ = port_for(Path(tmp.name), "csv")
        cnh = kit.CurrencyCode("CNH")
        lk = port.fx_on(cnh, REPORTING, AS_OF, placeholder_conventions())
        self.assertIsNone(lk.rate)  # OD-3 / PD-0030: strict; CNY data exists and is not substituted
        self.assertIs(lk.outcome, LookupOutcome.NOT_IN_RELEASE)

    def test_the_consumer_refuses_a_mismatched_as_of(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        port, identity, _ = port_for(Path(tmp.name), "mock")
        state = kit.replayed_state(identity, AS_OF)
        with self.assertRaises(ValuationInputsError):
            assemble_valuation_inputs(port, identity, state, kit.DAY2, REPORTING, placeholder_conventions())

    def test_output_is_byte_identical_across_processes_and_hash_seeds(self):
        digests = set()
        for seed in ("1", "2", "random"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            out = subprocess.run([sys.executable, str(Path(__file__)), "digest"], env=env, cwd=str(REPO),
                                 capture_output=True, text=True, timeout=120)
            self.assertEqual(out.returncode, 0, out.stderr)
            digests.add(out.stdout.strip())
        self.assertEqual(len(digests), 1, digests)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        port, identity, _ = port_for(Path(tmp.name), "mock")
        self.assertEqual(digests.pop(), digest_of(consumer_body(port, identity)))


def inputs_placeholders(ids):
    return [v for v in ids.values() if v.startswith("placeholder/")]


def digest_of(inputs) -> str:
    return hashlib.sha256(
        (canonical_json(inputs.value_obj()) + "|" + canonical_json(inputs.lineage_obj())).encode("utf-8")
    ).hexdigest()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "digest":
        with tempfile.TemporaryDirectory() as tmp:
            port, identity, _ = port_for(Path(tmp), "mock")
            print(digest_of(consumer_body(port, identity)))
    else:
        unittest.main()
