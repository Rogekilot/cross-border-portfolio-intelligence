"""CP6 rule families against real CP4/CP5 engine outputs, not metric dictionaries."""
import datetime as dt
import json
import sys
import unittest
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from insight_service.service import compute_insights, reproduce_insights
from insight_service.sources import verify_source
from insights.contracts import HistoryComparison, InsightResult, MetricRef, ProofPacket, UserLimit
from insights.evidence import semantic_key
from marketdata.canonical import canonical_json
from tests.product.insight_testkit import cp4_source, cp5_source
from diversification.engine import compute_diversification
from domain.currency import CurrencyCode
from domain.ledger import EventType
from performance.periods import WindowRule, WindowSpec


def policy_for(source, metric_id="largest_security_weight", subject=(), **changes):
    evidence = verify_source(source, allow_synthetic=True)
    metric = next(m for m in evidence.payload()["metrics"] if m["metric_id"] == metric_id and tuple(m.get("subject", ())) == subject)
    c = evidence.context()
    options = dict(policy_id="synthetic-personal-limit/1", version="1", evidence="SYNTHETIC explicit user limit for CP6 tests only",
                   portfolio_id=c["portfolio_id"], scope_kind="PORTFOLIO" if c["account_id"] is None else "ACCOUNT", account_id=c["account_id"],
                   source_kind=evidence.source_kind, metric_id=metric_id, subject=subject, semantic_key=semantic_key(evidence, metric),
                   direction="MAXIMUM", limit=Fraction(1, 2), effective_from=dt.date(2022, 1, 1))
    options.update(changes)
    return UserLimit(**options)


def packets(result, family):
    return [p.to_obj() for p in result.packets if p.to_obj()["insight_type"] == family]


class IntegratedRuleTests(unittest.TestCase):
    def test_cp4_negative_active_return_is_fact_observation_never_warning(self):
        source, _, _, _, item = cp4_source()
        result = compute_insights((source,), allow_synthetic=True)
        self.assertIsInstance(result, InsightResult)
        (packet,) = packets(result, "benchmark_underperformance")
        self.assertEqual((packet["judgment_class"], packet["severity"], packet["comparison_basis"]["kind"]), ("FACT", "OBSERVATION", "BENCHMARK"))
        self.assertEqual(packet["metrics_used"][0]["metric"]["exact"], item["exact"])
        self.assertIn("SYNTHETIC", packet["claim"]["text"])
        self.assertTrue(packet["benchmark"]["selection_id"])

    def test_cp5_snapshot_and_explicit_limit_keep_actual_policy_and_scope(self):
        source, _, _, _ = cp5_source()
        policy = policy_for(source)
        result = compute_insights((source,), policies=(policy,), allow_synthetic=True)
        (packet,) = packets(result, "user_limit")
        self.assertEqual(packet["judgment_class"], "PREFERENCE_DEPENDENT")
        self.assertEqual(packet["metrics_used"][0]["metric"]["exact"], "1/1")
        self.assertEqual(packet["comparison_basis"]["policy_digest"], policy.policy_digest)
        self.assertEqual(packet["source_evidence"][0]["payload"]["manifest"]["capital_policy"]["decision_id"], "PD-0041")
        self.assertTrue(packets(result, "metric_snapshot"))
        self.assertEqual(packet["portfolio_state"], "ACTUAL")
        self.assertIsNone(packet["scenario_id"])
        self.assertEqual(packet["severity"], "ATTENTION")
        self.assertIn("SOURCE_FRESHNESS_UNKNOWN", packet["limitations"])

    def test_cp3_exact_verified_valuation_freshness_supports_cap_warning(self):
        source, _, _, _ = cp5_source(with_freshness=True)
        policy = policy_for(source)
        result = compute_insights((source,), policies=(policy,), allow_synthetic=True)
        (packet,) = packets(result, "user_limit")
        self.assertEqual(packet["severity"], "WARNING")
        freshness = packet["data_freshness"][0]
        self.assertEqual(freshness["freshness_status"], "FULL")
        self.assertEqual(freshness["freshness_vector"]["summary"], "CURRENT")
        self.assertTrue(freshness["freshness_evidence"]["result_digest"])
        self.assertEqual(freshness["freshness_scope"], "CAPITAL_SNAPSHOT_VALUATION")
        model = next(p for p in packets(result, "metric_snapshot") if p["metrics_used"][0]["metric"]["metric_id"] == "modeled_volatility")
        self.assertEqual(model["data_freshness"][0]["freshness_status"], "UNKNOWN")
        self.assertIn("POINT_IN_TIME_VALUATION_DOES_NOT_ATTEST_HISTORICAL_MODEL_INPUTS", model["limitations"])
        self.assertEqual(reproduce_insights(result, result.result_digest, (source,), policies=(policy,), allow_synthetic=True).status, "REPRODUCED")

    def test_no_personal_limit_means_no_preference_judgment(self):
        source, _, _, _ = cp5_source()
        result = compute_insights((source,), allow_synthetic=True)
        self.assertFalse(packets(result, "user_limit"))
        self.assertTrue(all(p.to_obj()["severity"] == "OBSERVATION" for p in result.packets))

    def test_missing_data_surfaces_diagnostic_without_numeric_claim(self):
        source, _, _, _ = cp5_source(prefix="P7 ", as_of=dt.date(2025, 6, 13))
        result = compute_insights((source,), allow_synthetic=True)
        self.assertFalse(any(p["metrics_used"][0]["metric"]["metric_id"] == "hhi_concentration" for p in packets(result, "metric_snapshot")))
        self.assertIn("INSUFFICIENT_DATA", result.diagnostics_json)
        for packet in result.packets:
            self.assertTrue(all(m["metric"]["value"] is not None for m in packet.to_obj()["metrics_used"]))

    def test_unknown_country_remains_unknown_with_its_caveat(self):
        source, _, _, _ = cp5_source(metadata=None)
        result = compute_insights((source,), allow_synthetic=True)
        packet = next(p for p in packets(result, "metric_snapshot") if p["metrics_used"][0]["metric"]["metric_id"] == "country_exposure")
        self.assertEqual(packet["metrics_used"][0]["metric"]["subject"], ["UNKNOWN"])
        self.assertIn("UNKNOWN_CLASSIFICATION", packet["limitations"])

    def test_equal_limit_never_breaches_and_conflicting_limits_do_not_choose_one(self):
        source, _, _, _ = cp5_source()
        equal = policy_for(source, limit=Fraction(1))
        result = compute_insights((source,), policies=(equal,), allow_synthetic=True)
        self.assertFalse(packets(result, "user_limit"))
        a = policy_for(source)
        result = compute_insights((source,), policies=(a, replace(a, policy_id="another-user-limit", limit=Fraction(3, 4))), allow_synthetic=True)
        self.assertFalse(packets(result, "user_limit"))
        self.assertIn("POLICY_CONFLICT", result.diagnostics_json)

    def test_policy_does_not_inherit_into_account_or_other_portfolio(self):
        source, _, _, _ = cp5_source()
        policy = policy_for(source)
        for wrong in (replace(policy, portfolio_id="OTHER"), replace(policy, scope_kind="ACCOUNT", account_id="OTHER-ACCOUNT")):
            result = compute_insights((source,), policies=(wrong,), allow_synthetic=True)
            self.assertFalse(packets(result, "user_limit"))
            self.assertIn("POLICY_SCOPE_MISMATCH", result.diagnostics_json)

    def test_history_uses_two_actual_pinned_snapshots_and_only_direction(self):
        # P11's explicit ledger buys a recent listing during October. Independent
        # before/after concentration direction follows the fixture ledger: before,
        # one security plus cash; afterwards, two securities plus residual cash.
        baseline, _, _, _ = cp5_source(prefix="P11 ", as_of=dt.date(2025, 9, 26))
        current, _, _, _ = cp5_source(prefix="P11 ", as_of=dt.date(2026, 1, 2))
        ce, be = (verify_source(s, allow_synthetic=True) for s in (current, baseline))
        comparison = HistoryComparison(MetricRef(ce.source_id, "hhi_concentration"), MetricRef(be.source_id, "hhi_concentration"))
        result = compute_insights((current, baseline), history=(comparison,), allow_synthetic=True)
        (packet,) = packets(result, "history_change")
        self.assertEqual((packet["judgment_class"], packet["severity"]), ("INTERPRETATION", "OBSERVATION"))
        self.assertEqual(packet["claim"]["parameters"]["direction"], "DECREASED")
        self.assertNotIn("delta", packet["claim"]["parameters"])
        self.assertEqual(len(packet["metrics_used"]), 2)
        self.assertEqual(packet["comparison_basis"]["kind"], "PORTFOLIO_HISTORY")

    def test_changed_classification_taxonomy_cannot_reuse_history_or_personal_limit(self):
        baseline, _, _, _ = cp5_source(prefix="P11 ", as_of=dt.date(2025, 9, 26))
        _, _, _, kw = cp5_source(prefix="P11 ")
        current, _, _, _ = cp5_source(prefix="P11 ", metadata=replace(kw["metadata"], taxonomy="OTHER-CLASSIFICATION-SYSTEM"))
        ce, be = (verify_source(s, allow_synthetic=True) for s in (current, baseline))
        subject = ("EXPLICIT_SYNTHETIC_SECTOR",)
        comparison = HistoryComparison(MetricRef(ce.source_id, "sector_exposure", subject), MetricRef(be.source_id, "sector_exposure", subject))
        policy = policy_for(baseline, "sector_exposure", subject)
        result = compute_insights((current, baseline), history=(comparison,), policies=(policy,), allow_synthetic=True)
        self.assertEqual(len(packets(result, "history_change")), 0)
        self.assertFalse(any(p["metrics_used"][0]["reference"]["source_id"] == ce.source_id for p in packets(result, "user_limit")))
        self.assertIn("SEMANTIC_MISMATCH", result.diagnostics_json)

    def test_changed_cluster_threshold_is_not_a_historical_change_in_clustering(self):
        source, r, p, kw = cp5_source(prefix="P11 ", request=WindowSpec(WindowRule.TRAILING_MONTHS, 12))
        original = source.events
        first_listing = next(e.event.listing_id for e in original if e.event.event_type is EventType.BUY)
        replacement = r.ids("c4000000-0000-4000-8000-000000000001")
        events = tuple(replace(e, event=replace(e.event, listing_id=replacement)) if e.event.event_type is EventType.BUY and e.event.listing_id != first_listing else e for e in original)
        def make(as_of, threshold):
            result = compute_diversification(events, max(e.ledger_seq for e in events), as_of, CurrencyCode("USD"), r.market.store, r.market.ident,
                                             r.market.conventions, r.perf, **dict(kw, cluster_threshold=threshold))
            return replace(source, result=result, events=events)
        baseline = make(dt.date(2026, 1, 2), Fraction(1))
        current = make(dt.date(2026, 1, 9), Fraction(1, 10))
        ce, be = (verify_source(s, allow_synthetic=True) for s in (current, baseline))
        comparison = HistoryComparison(MetricRef(ce.source_id, "correlation_cluster_count"), MetricRef(be.source_id, "correlation_cluster_count"))
        result = compute_insights((current, baseline), history=(comparison,), allow_synthetic=True)
        self.assertEqual(len(packets(result, "history_change")), 0)
        self.assertIn("SEMANTIC_MISMATCH", result.diagnostics_json)


class ProofReproductionTests(unittest.TestCase):
    def setUp(self):
        self.source, _, _, _ = cp5_source()
        self.policy = policy_for(self.source)
        self.result = compute_insights((self.source,), policies=(self.policy,), allow_synthetic=True)

    def test_actual_replay_requires_expected_result_and_all_inputs(self):
        args = (self.result, self.result.result_digest, (self.source,))
        self.assertEqual(reproduce_insights(*args, policies=(self.policy,), allow_synthetic=True).status, "REPRODUCED")
        self.assertEqual(reproduce_insights(self.result, None, (self.source,), policies=(self.policy,), allow_synthetic=True).status, "RESULT_NOT_COMPARED")
        self.assertEqual(reproduce_insights(self.result, "0" * 64, (self.source,), policies=(self.policy,), allow_synthetic=True).status, "RESULT_DIFFERS")
        self.assertEqual(reproduce_insights(*args, allow_synthetic=True).status, "INPUT_MISMATCH")
        self.assertEqual(reproduce_insights(self.result, self.result.result_digest, (), policies=(self.policy,), allow_synthetic=True).status, "SOURCE_REFUSED")

    def test_quant_i3_changed_baseline_result_prevents_any_rule_output(self):
        baseline, _, _, _ = cp5_source(prefix="P11 ", as_of=dt.date(2025, 9, 26))
        current, _, _, _ = cp5_source(prefix="P11 ")
        ce, be = (verify_source(s, allow_synthetic=True) for s in (current, baseline))
        history = (HistoryComparison(MetricRef(ce.source_id, "hhi_concentration"), MetricRef(be.source_id, "hhi_concentration")),)
        row = baseline.result.metrics[0]
        wrong = replace(baseline, result=replace(baseline.result, metrics=(replace(row, details=("changed baseline answer",)),) + baseline.result.metrics[1:]))
        refused = compute_insights((current, wrong), history=history, allow_synthetic=True)
        self.assertEqual(refused.code, "SOURCE_NOT_REPRODUCED")
        self.assertFalse(hasattr(refused, "packets"))

    def test_quant_i4_changed_policy_content_cannot_reproduce_original_policy_digest(self):
        changed = replace(self.policy, limit=Fraction(3, 4))
        self.assertNotEqual(changed.policy_digest, self.policy.policy_digest)
        report = reproduce_insights(self.result, self.result.result_digest, (self.source,), policies=(changed,), allow_synthetic=True)
        self.assertEqual(report.status, "INPUT_MISMATCH")

    def test_packet_value_severity_limit_caveat_counts_timestamp_and_refs_are_bound(self):
        original = next(p for p in self.result.packets if p.to_obj()["insight_type"] == "user_limit")
        mutations = (
            lambda p: p.update(severity="OBSERVATION"),
            lambda p: p["metrics_used"][0]["metric"].update(value="0"),
            lambda p: p["thresholds_limits"]["policy"].update(limit="1/100"),
            lambda p: p.update(limitations=[]),
            lambda p: p.update(observations=[999]),
            lambda p: p["source_data_timestamps"][0].update(retrieved_at="2026-10-19"),
            lambda p: p["comparison_basis"].update(policy_digest="0" * 64),
            lambda p: p["metrics_used"][0]["reference"].update(metric_id="hhi_concentration"),
        )
        for mutate in mutations:
            payload = original.to_obj()
            mutate(payload)
            changed = ProofPacket(canonical_json(payload))
            stored = replace(self.result, packets=tuple(changed if p == original else p for p in self.result.packets))
            self.assertEqual(reproduce_insights(stored, stored.result_digest, (self.source,), policies=(self.policy,), allow_synthetic=True).status, "RESULT_DIFFERS")

    def test_complete_manifest_compares_missing_added_null_and_boolean(self):
        for kind in ("missing", "added", "boolean"):
            old = json.loads(self.result.manifest_json)
            if kind == "missing":
                del old["scenario_id"]
            elif kind == "added":
                old["unexpected_null"] = None
            else:
                old["allow_synthetic"] = 1
            changed = replace(self.result, manifest_json=canonical_json(old))
            self.assertEqual(reproduce_insights(changed, self.result.result_digest, (self.source,), policies=(self.policy,), allow_synthetic=True).status, "INPUT_MISMATCH")

    def test_source_policy_order_and_identical_duplicates_do_not_change_identity(self):
        a = compute_insights((self.source, self.source), policies=(self.policy, self.policy), allow_synthetic=True)
        self.assertEqual(a.canonical_json(), self.result.canonical_json())
        changed = replace(self.policy, limit=Fraction(3, 4), policy_id="second")
        left = compute_insights((self.source,), policies=(self.policy, changed), allow_synthetic=True)
        right = compute_insights((self.source,), policies=(changed, self.policy), allow_synthetic=True)
        self.assertEqual(left.canonical_json(), right.canonical_json())

    def test_malformed_nested_request_and_saved_packet_are_typed_refusals(self):
        for history in (HistoryComparison(None, None), HistoryComparison("a", "b")):
            result = compute_insights((self.source,), history=(history,), allow_synthetic=True)
            self.assertEqual(result.code, "INVALID_REQUEST")
        for sources, policies, history in ((None, (), ()), ((self.source,), None, ()), ((self.source,), (), None)):
            self.assertEqual(compute_insights(sources, policies=policies, history=history, allow_synthetic=True).code, "INVALID_REQUEST")
        wrong = replace(self.result, packets=(None,))
        report = reproduce_insights(wrong, self.result.result_digest, (self.source,), policies=(self.policy,), allow_synthetic=True)
        self.assertEqual(report.status, "INPUT_MISMATCH")


if __name__ == "__main__":
    unittest.main()
