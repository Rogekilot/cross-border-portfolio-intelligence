"""Tie the additive CP3 appendix to the Quant's text and existing 24 ids."""
import hashlib
import json
import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from product_contract import performance_methodology_registry as registry
from performance.registry import METRIC_IDS
from product_contract.methodology_registry import REQUIRED_FIELDS


class PerformanceMethodologyRegistryTests(unittest.TestCase):
    def test_byte_identity_ids_and_fifteen_required_fields(self):
        # performance-registry/1.2 (label re-issue of the 1.0 appendix for market-data/1.16, section 11 item 35): the 1.0 and 1.1 files stay as records
        self.assertEqual(registry.REGISTRY_BYTES, (ROOT / "methodology/registry/PERFORMANCE_1.12_REGISTRY_APPENDIX_1.2.json").read_bytes())
        self.assertEqual(registry.REGISTRY.metric_ids, METRIC_IDS)
        self.assertEqual(len(registry.METHODOLOGY_REGISTRY), 24)
        self.assertEqual(len(REQUIRED_FIELDS), 15)
        for row in registry.REGISTRY.entries():
            self.assertFalse(set(REQUIRED_FIELDS) - set(row))
            self.assertTrue(row["defined_in"])
            self.assertTrue(registry.REGISTRY.resolved(row["metric_id"])["formula"])

    def test_nested_pointers_resolve_and_returned_values_cannot_mutate_registry(self):
        row = registry.REGISTRY.resolved("portfolio_value")
        self.assertNotEqual(row["states"][0], "common.states.valuation")
        before = registry.REGISTRY.digest
        row["formula"] = "changed copy"
        registry.REGISTRY.to_obj()["entries"].clear()
        self.assertEqual(registry.REGISTRY.digest, before)
        self.assertEqual(len(registry.REGISTRY.entries()), 24)
        with self.assertRaises(FrozenInstanceError):
            registry.REGISTRY._json = "{}"

    def test_missing_field_duplicate_unknown_id_and_dangling_pointer_refuse(self):
        for field in REQUIRED_FIELDS:
            data = registry.REGISTRY.to_obj()
            del data["entries"][0][field]
            with self.assertRaises(ValueError, msg=field):
                registry.load_registry(json.dumps(data))
        for mutation in (lambda d: d["entries"].append(d["entries"][0]),
                         lambda d: d["entries"][0].update(metric_id="unknown"),
                         lambda d: d["entries"][0].update(formula="common.states.missing"),
                         lambda d: d.update(registry_id="performance/1.13")):
            data = registry.REGISTRY.to_obj()
            mutation(data)
            with self.assertRaises(ValueError):
                registry.load_registry(json.dumps(data))
        with self.assertRaises(KeyError):
            registry.REGISTRY.entry("unknown")

    def test_the_appendix_in_force_is_1_2_and_the_earlier_texts_are_records_this_loader_refuses(self):
        self.assertEqual(registry.REGISTRY.appendix_id, "performance-registry/1.2")
        previous = (ROOT / "methodology/registry/PERFORMANCE_1.12_REGISTRY_APPENDIX_1.1.json").read_bytes()
        self.assertEqual(json.loads(previous)["appendix_id"], "performance-registry/1.1")
        with self.assertRaisesRegex(registry.RegistryError, "unsupported performance methodology appendix"):
            registry.load_registry(previous)
        old = (ROOT / "methodology/registry/PERFORMANCE_1.12_REGISTRY.json").read_bytes()
        self.assertEqual(json.loads(old)["appendix_id"], "performance-registry/1.0")
        self.assertEqual(json.loads(old)["registry_id"], registry.REGISTRY_ID)  # the same registry_id: the appendix id and the digest tell the two texts apart
        with self.assertRaisesRegex(registry.RegistryError, "unsupported performance methodology appendix"):
            registry.load_registry(old)
        self.assertNotEqual(registry.load_registry().digest, hashlib.sha256(json.dumps(json.loads(old), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest())

    def test_registry_is_additive_to_existing_metric_id_keys(self):
        self.assertEqual(registry.REGISTRY_ID, "performance/1.12")
        self.assertEqual(registry.REGISTRY.entry_key("return_twr"), "performance/1.12#return_twr")
        self.assertEqual(registry.load_registry().digest, registry.REGISTRY_DIGEST)


if __name__ == "__main__":
    unittest.main()
