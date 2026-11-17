"""Source authenticity tests; these are actual existing engine replays."""
import json
import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from insight_service.sources import verify_source
from insights.contracts import SourceEvidence, InsightRefusal
from product_contract.metric_state import MetricResult
from tests.product.insight_testkit import cp4_source, cp5_source, cp5_current_source


class SourceVerificationTests(unittest.TestCase):
    def test_cp4_actual_replay_keeps_exact_value_benchmark_and_lineage(self):
        source, _, _, _, item = cp4_source()
        evidence = verify_source(source, allow_synthetic=True)
        self.assertIsInstance(evidence, SourceEvidence)
        metric = evidence.payload()["metrics"][0]
        self.assertEqual(metric["exact"], item["exact"])
        self.assertEqual(Decimal(metric["value"]), Decimal(item["value"]))
        self.assertTrue(metric["benchmark"]["selection_id"])
        self.assertEqual(metric["state"], item["state"])
        self.assertTrue(evidence.payload()["manifest"]["series_manifest"]["data_set_refs"])

    def test_cp5_replay_preserves_capital_decision_and_window(self):
        source, _, _, _ = cp5_source()
        evidence = verify_source(source, allow_synthetic=True)
        self.assertIsInstance(evidence, SourceEvidence)
        context, payload = evidence.context(), evidence.payload()
        self.assertEqual(context["capital_universe"], "FULL_NAV")
        self.assertEqual(payload["manifest"]["capital_policy"]["decision_id"], "PD-0041")
        self.assertEqual(payload["manifest"]["window"]["observation_count"], 156)
        self.assertEqual(context["portfolio_state"], "ACTUAL")
        self.assertIsNone(context["scenario_id"])

    def test_synthetic_requires_explicit_opt_in_and_payload_dict_is_not_source(self):
        source, _, _, _ = cp5_source()
        self.assertEqual(verify_source(source).code, "SYNTHETIC_DATA_REFUSED")
        self.assertEqual(verify_source(source.result.canonical_json()).code, "UNSUPPORTED_SOURCE")

    def test_correct_advertised_risk_digest_does_not_authenticate_changed_payload(self):
        source, *_ = cp4_source()
        m = source.result.metrics[0]
        wrong = replace(m, result=MetricResult(Decimal("0.9"), m.state, m.result.reason_code))
        tampered = replace(source.result, metrics=(wrong,))
        self.assertEqual(tampered.result_digest, source.result.result_digest)
        self.assertEqual(verify_source(replace(source, result=tampered), allow_synthetic=True).code, "SOURCE_PAYLOAD_MISMATCH")

    def test_risk_bad_digest_is_a_refusal(self):
        source, *_ = cp4_source()
        wrong = replace(source, result=replace(source.result, result_digest="0" * 64))
        self.assertEqual(verify_source(wrong, allow_synthetic=True).code, "SOURCE_NOT_REPRODUCED")

    def test_cp5_extra_null_manifest_key_or_changed_answer_is_refused(self):
        source, _, _, _ = cp5_source()
        payload = json.loads(source.result.manifest_json)
        payload["unexpected_null"] = None
        changed = replace(source.result, manifest_json=json.dumps(payload))
        self.assertEqual(verify_source(replace(source, result=changed), allow_synthetic=True).code, "SOURCE_NOT_REPRODUCED")
        wrong_metric = replace(source.result.metrics[0], details=("fabricated caveat",))
        changed = replace(source.result, metrics=(wrong_metric,) + source.result.metrics[1:])
        self.assertEqual(verify_source(replace(source, result=changed), allow_synthetic=True).code, "SOURCE_NOT_REPRODUCED")

    def test_changed_ledger_is_not_verified(self):
        source, *_ = cp4_source()
        self.assertEqual(verify_source(replace(source, events=()), allow_synthetic=True).code, "SOURCE_NOT_REPRODUCED")

    def test_invalid_upstream_object_fields_are_typed_refusals(self):
        risk, *_ = cp4_source()
        div, *_ = cp5_source()
        for source, result in ((risk, replace(risk.result, manifest=None)), (risk, replace(risk.result, result_digest=None)),
                               (div, replace(div.result, manifest_json=None)), (div, replace(div.result, metrics=None))):
            with self.subTest(kind=type(result).__name__):
                report = verify_source(replace(source, result=result), allow_synthetic=True)
                self.assertIsInstance(report, InsightRefusal)

    def test_auxiliary_is_exactly_bound_and_its_full_payload_is_authenticated(self):
        source, _, _, _ = cp5_source(with_freshness=True)
        auxiliary = source.freshness_result
        wrong_date = replace(auxiliary, manifest=replace(auxiliary.manifest, as_of=auxiliary.manifest.as_of.replace(day=1)))
        wrong_scope = replace(auxiliary, manifest=replace(auxiliary.manifest, scope="ACCOUNT:other"))
        wrong_release = replace(auxiliary, manifest=replace(auxiliary.manifest, release_id="other-release"))
        wrong_pin = replace(auxiliary, manifest=replace(auxiliary.manifest, ledger_version=0))
        metric = auxiliary.metrics[0]
        forged_payload = replace(auxiliary, metrics=(replace(metric, details=("fabricated freshness caveat",)),) + auxiliary.metrics[1:])
        for wrong in (wrong_date, wrong_scope, wrong_release, wrong_pin, forged_payload, {}):
            with self.subTest(wrong=type(wrong).__name__):
                report = verify_source(replace(source, freshness_result=wrong), allow_synthetic=True)
                self.assertIsInstance(report, InsightRefusal)
                self.assertIn("FRESHNESS_AUXILIARY", report.detail)

    def test_auxiliary_malformed_freshness_object_cannot_escape_guard(self):
        source, _, _, _ = cp5_source(with_freshness=True)
        wrong = replace(source.freshness_result, manifest=None)
        self.assertIsInstance(verify_source(replace(source, freshness_result=wrong), allow_synthetic=True), InsightRefusal)

    def test_current_source_and_freshness_auxiliary_bind_exact_m_t_instant(self):
        source, _, _ = cp5_current_source(with_freshness=True)
        evidence = verify_source(source, allow_synthetic=True)
        self.assertIsInstance(evidence, SourceEvidence)
        self.assertTrue(evidence.payload()["manifest"]["valuation_manifest"]["excluded_files"])
        self.assertEqual(evidence.context()["instant"], "2026-01-09T09:00:00.000000Z")
        self.assertEqual(evidence.context()["freshness_auxiliary"]["manifest"]["instant"], evidence.context()["instant"])
        auxiliary = source.freshness_result
        wrong = replace(auxiliary, manifest=replace(auxiliary.manifest, instant=auxiliary.manifest.instant.replace(second=1)))
        self.assertIsInstance(verify_source(replace(source, freshness_result=wrong), allow_synthetic=True), InsightRefusal)
        self.assertIsInstance(verify_source(replace(source, market_at=None), allow_synthetic=True), InsightRefusal)


if __name__ == "__main__":
    unittest.main()
