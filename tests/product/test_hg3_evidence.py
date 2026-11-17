"""Evidence comes from executed engines; fixture expectations cannot fill it in."""
import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.product import hg3_evidence as evidence


class EvidenceTests(unittest.TestCase):
    def small(self, **kw):
        args = dict(cp4_parts=(), cp5_case_ids=("C5-S1", "C5-H1", "C5-D1", "C5-H16"), include_integration=False)
        args.update(kw)
        return evidence.build_evidence(**args)

    def test_actual_kernels_and_drift_engine_are_invoked(self):
        with mock.patch.object(evidence.cp5, "snapshot", wraps=evidence.cp5.snapshot) as capital, \
             mock.patch.object(evidence.cp5, "history", wraps=evidence.cp5.history) as history, \
             mock.patch.object(evidence, "compute_drift_result", wraps=evidence.compute_drift_result) as drift:
            result = self.small()
        self.assertEqual(capital.call_count, 1)
        self.assertEqual(history.call_count, 2)
        self.assertEqual(drift.call_count, 1)
        self.assertEqual(result["summary"]["numeric_or_state_mismatch_rows"], 0)
        self.assertTrue(result["rows"])
        for row in result["rows"]:
            self.assertEqual(row["label"], evidence.LABEL)
            self.assertIn("actual", row)
            self.assertTrue(row["formula"])
            self.assertTrue(row["method_version"])
            self.assertIn("minimum_data_rule", row)
            self.assertIn("limitations", row)
        h16 = next(row for row in result["rows"] if row["case_id"] == "C5-H16" and row["metric_id"] == "average_correlation")
        self.assertEqual(h16["actual"]["value"], "0.565685424949")
        self.assertEqual(h16["expected"]["value"], "0.565685424949")

    def test_changed_actual_value_is_exported_and_detected(self):
        original = evidence.cp5.snapshot
        def mutant(case):
            metrics, weights = original(case)
            return [replace(m, exact=m.exact + Fraction(1, 100)) if m.metric_id == "hhi_concentration" else m for m in metrics], weights
        with mock.patch.object(evidence.cp5, "snapshot", side_effect=mutant):
            result = self.small(cp5_case_ids=("C5-S1",))
        row = next(r for r in result["rows"] if r["metric_id"] == "hhi_concentration")
        self.assertEqual(row["comparison"]["status"], "MISMATCH")
        self.assertNotEqual(Fraction(row["actual"]["exact"]), Fraction(row["expected"]["exact"]))
        self.assertEqual(result["summary"]["numeric_or_state_mismatch_rows"], 1)

    def test_cp4_export_uses_existing_engine_and_independent_checker(self):
        runner = evidence.cp4.shared_runner(1)
        portfolio, assertion, item = next((p, a, it) for p, a, it in evidence.cp4.items(runner.data) if it["kind"] == "volatility")
        selected = copy.deepcopy(portfolio)
        selected["assertions"] = [dict(assertion, expect=[item])]
        risk_call = mock.Mock(wraps=runner.risk)
        proxy = SimpleNamespace(data={"portfolios": [selected]}, risk=risk_call)
        with mock.patch.object(evidence.cp4, "shared_runner", return_value=proxy):
            artifacts, missing, cases = {}, [], []
            rows = evidence.cp4_rows((1,), artifacts, missing, cases)
        self.assertEqual(risk_call.call_count, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["comparison"]["status"], "MATCH")
        self.assertEqual(rows[0]["actual"]["metric_id"], "risk_volatility")
        self.assertTrue(rows[0]["computation_ref"] in artifacts)
        self.assertFalse(missing)

    def test_missing_builder_is_explicit_without_expected_as_actual(self):
        case = {"id": "NEW-UNKNOWN", "kind": "new_kind", "input": {}, "expected": {"invented_value": "123"}}
        with mock.patch.dict(evidence.cp5.CASES, {case["id"]: case}):
            result = self.small(cp5_case_ids=(case["id"],))
        self.assertFalse(result["rows"])
        self.assertIsNone(result["cases"][0]["actual"])
        self.assertEqual(result["cases"][0]["status"], "NOT_MATERIALIZED")
        self.assertTrue(any(r.get("case_id") == case["id"] for r in result["missing"]))

    def test_partial_scope_and_eight_edges_are_reported_honestly(self):
        result = self.small(cp5_case_ids=("C5-S1",))
        self.assertEqual(len(result["edge_cases"]), 8)
        self.assertTrue(any(e["status"] == "POINTER_ONLY" for e in result["edge_cases"]))
        self.assertEqual(result["summary"]["major_metric_ids"]["CP4"], [])
        self.assertTrue(any(m.get("family") == "CP4" for m in result["missing"]))
        self.assertIn("no HG3", result["label"])

    def test_missing_fx_subset_excludes_empty_nav_and_includes_actual_missing_fx(self):
        for case_id, status, assertions in (("C5-S5", "POINTER_ONLY", []), ("C5-S3", "MATERIALIZED", ["C5-S3"])):
            with self.subTest(case_id=case_id):
                result = self.small(cp5_case_ids=(case_id,))
                edge = next(row for row in result["edge_cases"] if row["edge_case"] == "missing_fx")
                self.assertEqual(edge["status"], status)
                self.assertEqual(edge["materialized_assertions"], assertions)
                reasons = {row["actual"]["reason"] for row in result["rows"]}
                self.assertEqual("MISSING_FX_HISTORY" in reasons, case_id == "C5-S3")

    def test_missing_fx_mapping_requires_observed_and_expected_fx_reason(self):
        with mock.patch.dict(evidence.EDGE_ASSERTIONS, {"missing_fx": ("C5-S5",)}):
            empty_nav = self.small(cp5_case_ids=("C5-S5",))
        edge = next(row for row in empty_nav["edge_cases"] if row["edge_case"] == "missing_fx")
        self.assertEqual(edge["status"], "POINTER_ONLY")
        self.assertEqual(edge["materialized_assertions"], [])
        original = evidence.cp5.snapshot
        def changed_actual(case):
            metrics, weights = original(case)
            return [evidence.metric(m.metric_id, m.subject, state=evidence.INSUFFICIENT, reason="MISSING_PRICE_HISTORY", details=m.details) for m in metrics], weights
        with mock.patch.object(evidence.cp5, "snapshot", side_effect=changed_actual):
            actual_mismatch = self.small(cp5_case_ids=("C5-S3",))
        changed_case = copy.deepcopy(evidence.cp5.CASES["C5-S3"])
        changed_case["expected"]["all_concentration_and_exposure"]["reason"] = "MISSING_PRICE_HISTORY"
        with mock.patch.dict(evidence.cp5.CASES, {"C5-S3": changed_case}):
            expected_mismatch = self.small(cp5_case_ids=("C5-S3",))
        for result in (actual_mismatch, expected_mismatch):
            edge = next(row for row in result["edge_cases"] if row["edge_case"] == "missing_fx")
            self.assertEqual(edge["status"], "POINTER_ONLY")
            self.assertEqual(edge["materialized_assertions"], [])

    def test_artifact_checksums_references_and_no_overwrite(self):
        result = self.small(cp5_case_ids=("C5-D1",))
        with tempfile.TemporaryDirectory(prefix="finweb-hg3-evidence-test-") as tmp:
            out = Path(tmp) / "evidence"
            evidence.write_evidence(result, out)
            inventory = json.loads((out / "FILES_SHA256.json").read_text())
            for relative, digest in inventory.items():
                self.assertEqual(hashlib.sha256((out / relative).read_bytes()).hexdigest(), digest)
            saved = json.loads((out / "evidence.json").read_text())
            for row in saved["rows"]:
                if row["computation_ref"]:
                    self.assertTrue((out / row["computation_ref"]).is_file())
            self.assertEqual(saved["registry_inventory"]["performance"]["metric_ids"], sorted(evidence.PERFORMANCE_REGISTRY.metric_ids))
            self.assertIn("actual", (out / "README.md").read_text().lower())
            with self.assertRaises(FileExistsError):
                evidence.write_evidence(result, out)

    def test_reruns_are_deterministic_and_cli_runs_a_bounded_scope(self):
        first = self.small(cp5_case_ids=("C5-D1",))
        second = self.small(cp5_case_ids=("C5-D1",))
        self.assertEqual(evidence._plain(first), evidence._plain(second))
        with tempfile.TemporaryDirectory(prefix="finweb-hg3-cli-test-") as tmp, contextlib.redirect_stdout(io.StringIO()) as stream:
            code = evidence.main(["--output", str(Path(tmp) / "out"), "--cp4-parts", "", "--cp5-cases", "C5-D1", "--no-integration"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stream.getvalue())["actual_metric_rows"], 1)

    def test_comparator_has_no_silent_state_only_numeric_pass(self):
        actual = {"value": "0.5", "exact": "1/2", "exact_square": None, "state": "LIMITED", "reason": None, "details": []}
        self.assertEqual(evidence.compare_metric(actual, {"state": "LIMITED"})["status"], "STATE_ONLY_MATCH")
        self.assertEqual(evidence.compare_metric(actual, None)["status"], "NO_INDEPENDENT_EXPECTATION")
        self.assertEqual(evidence.compare_metric(actual, {"exact": "1/3"})["status"], "MISMATCH")
        self.assertEqual(evidence.compare_metric(actual, {"exact": None})["status"], "MISMATCH")

    def test_repaired_policy_and_exposure_partition_are_materialized_separately(self):
        result = self.small(cp5_case_ids=(), include_integration=True)
        row = next(r for r in result["rows"] if r["metric_id"] == "country_exposure")
        partition = row["exposure_decomposition"]
        self.assertIsNotNone(partition)
        self.assertEqual(partition["exact_total"], 1)
        self.assertEqual(partition["displayed_total"], 1)
        self.assertEqual(partition["parts"][0]["exact"], Fraction(row["actual"]["exact"]))
        source = json.loads(result["artifacts"][row["computation_ref"]])
        self.assertIn("exposure_decompositions", source)
        policy = source["manifest"]["capital_policy"]
        self.assertEqual(policy["origin"], "SYNTHETIC_CANDIDATE")
        self.assertEqual(policy["scope_kind"], "PORTFOLIO")
        self.assertEqual(policy["portfolio_id"], source["manifest"]["portfolio_id"])
        self.assertTrue(policy["decision_id"])
        self.assertIn("src/diversification/contracts.py", result["implementation_sha256"])
        self.assertIn("src/diversification/numerics.py", result["implementation_sha256"])


if __name__ == "__main__":
    unittest.main()
