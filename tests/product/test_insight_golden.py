"""Quant's normalized CP6 predicates, consumed without changing expected values.

These sources are deliberately internal synthetic premises, not replay-verified
financial results. Public source/replay/tamper proof belongs to the separately
mapped adapter tests; a symbolic upstream_failure never counts as that proof.
"""
import ast
import copy
import datetime as dt
import json
import sys
import unittest
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from insights.contracts import HistoryComparison, MetricRef, SourceEvidence, UserLimit
from insights.engine import _generate
from insights.evidence import semantic_key
from marketdata.canonical import canonical_json

FIXTURE = Path(__file__).resolve().parents[2] / "methodology/fixtures/cp6_golden/cp6_golden_part1.json"
DATA = json.loads(FIXTURE.read_bytes())
INTEGRITY_CASES = {
    "C6-I1": "MANIFEST_MISMATCH",
    "C6-I2": "STORED_RESULT_CHANGED",
    "C6-I3": "BASELINE_RESULT_CHANGED",
    "C6-I4": "POLICY_DIGEST_MISMATCH",
    "C6-I5": "AUXILIARY_VALUATION_MANIFEST_MISMATCH",
    "C6-I6": "AUXILIARY_VALUATION_RESULT_MISMATCH",
    "C6-I7": "AUXILIARY_SCOPE_MISMATCH",
    "C6-I8": "AUXILIARY_CURRENT_INSTANT_MISMATCH",
}
INTEGRITY_TESTS = {
    "C6-I1": ("test_insight_sources", "SourceVerificationTests", "test_cp5_extra_null_manifest_key_or_changed_answer_is_refused"),
    "C6-I2": ("test_insight_sources", "SourceVerificationTests", "test_correct_advertised_risk_digest_does_not_authenticate_changed_payload"),
    "C6-I3": ("test_insight_integration", "ProofReproductionTests", "test_quant_i3_changed_baseline_result_prevents_any_rule_output"),
    "C6-I4": ("test_insight_integration", "ProofReproductionTests", "test_quant_i4_changed_policy_content_cannot_reproduce_original_policy_digest"),
    "C6-I5": ("test_insight_sources", "SourceVerificationTests", "test_auxiliary_is_exactly_bound_and_its_full_payload_is_authenticated"),
    "C6-I6": ("test_insight_sources", "SourceVerificationTests", "test_auxiliary_is_exactly_bound_and_its_full_payload_is_authenticated"),
    "C6-I7": ("test_insight_sources", "SourceVerificationTests", "test_auxiliary_is_exactly_bound_and_its_full_payload_is_authenticated"),
    "C6-I8": ("test_insight_sources", "SourceVerificationTests", "test_current_source_and_freshness_auxiliary_bind_exact_m_t_instant"),
}


def normalized(case):
    inp = case["input"]
    current = copy.deepcopy(DATA["defaults"]["current"])
    current.update(inp.get("current", {}))
    baseline = None
    if "baseline" in inp:
        baseline = copy.deepcopy(DATA["defaults"]["current"])
        baseline.update(DATA["defaults"]["baseline"])
        baseline.update(inp["baseline"])
    policies = [dict(copy.deepcopy(DATA["defaults"]["policy"]), **p) for p in inp.get("policies", ())]
    return current, baseline, policies


def source(row, source_id, *, capital_choice="FULL_NAV"):
    """Translate symbolic conventions into actual structured dependency fields.

    H8's different capital semantics become a changed capital_universe field.
    H15's different model premise becomes a changed financial-convention field.
    Neither symbolic semantic_key nor source_ref is accepted as a proof digest.
    """
    benchmark = None if row["benchmark"] is None else {
        "benchmark_id": "SYNTHETIC-BENCHMARK", "selection_id": row["benchmark"], "selection_seq": 1,
        "return_basis": "TOTAL_RETURN_GROSS", "currency": "USD", "currency_treatment": "REPORTING",
        "catalog_id": "NORMALIZED-SYNTHETIC-CATALOG", "source_id": "NORMALIZED-SYNTHETIC-SOURCE"}
    metric = {key: copy.deepcopy(row.get(key)) for key in ("metric_id", "subject", "value", "exact", "exact_square", "sign", "state", "reason", "observation_count")}
    metric.update(details=copy.deepcopy(row["limitations"]), causes=[], benchmark=benchmark,
                  method_key="NORMALIZED-SYNTHETIC-METHOD#" + row["metric_id"],
                  comparability={"class": row["comparability"]}, radical_terms=copy.deepcopy(row.get("radical_terms", [])),
                  window={"rule": row["requested_rule"], "months": row["requested_months"]})
    conventions = {"fixture": "NORMALIZED-SYNTHETIC-CONVENTIONS", "model_kind": row["model_kind"]}
    manifest = {"valuation_manifest": {"conventions": conventions}, "series_manifest": {"conventions": conventions},
                "metadata": {"taxonomy": "NORMALIZED-SYNTHETIC-TAXONOMY"}, "window": {"grid_rule": "NORMALIZED-SYNTHETIC-GRID"},
                "boundary_rule_id": "NORMALIZED-SYNTHETIC-BOUNDARY", "coverage": [], "cluster_threshold": "3/5",
                "benchmark": None if benchmark is None else {"entry_digest": "NORMALIZED-SYNTHETIC-BENCHMARK-ENTRY"}}
    context = {key: copy.deepcopy(row[key]) for key in ("portfolio_id", "as_of", "portfolio_state", "scenario_id", "reporting_currency", "frequency")}
    context.update(account_id=row["account_id"], portfolio_snapshot_id="NORMALIZED-SYNTHETIC-SNAPSHOT:" + source_id,
                   instant=None, synthetic=True, limitations=copy.deepcopy(row["limitations"]),
                   capital_universe={"choice": capital_choice}, valuation_mode="HISTORICAL",
                   request={"rule": row["requested_rule"], "months": row["requested_months"]},
                   engine_id="NORMALIZED-SYNTHETIC-ENGINE:" + row["source"], registry_id="NORMALIZED-SYNTHETIC-REGISTRY:" + row["source"],
                   registry_digest="NORMALIZED-SYNTHETIC-REGISTRY-DIGEST:" + row["source"],
                   freshness={"status": row["freshness"], "vector": None, "evidence": None}, freshness_auxiliary=None)
    payload = {"manifest": manifest, "manifest_id": "NORMALIZED-SYNTHETIC-MANIFEST:" + source_id,
               "result_digest": "NORMALIZED-SYNTHETIC-RESULT:" + source_id, "metrics": [metric]}
    return SourceEvidence(source_id, row["source"], canonical_json(payload), canonical_json(context))


def user_limit(policy, current, evidence):
    # Derive the real semantic fingerprint from structured source fields. The
    # fixture's mismatched symbolic key means a different denominator premise.
    if policy["semantic_key"] == current["semantic_key"]:
        key = semantic_key(evidence, evidence.payload()["metrics"][0])
    else:
        different = source(current, "policy-semantics", capital_choice="HOLDINGS_ONLY")
        key = semantic_key(different, different.payload()["metrics"][0])
    return UserLimit(policy_id=policy["policy_id"], version=policy["version"], evidence=policy["decision_evidence"],
                     portfolio_id=policy["portfolio_id"], scope_kind=policy["scope"], source_kind=policy["source"],
                     metric_id=policy["metric_id"], subject=tuple(policy["subject"]), semantic_key=key,
                     direction=policy["direction"], limit=Fraction(policy["limit"]), origin=policy["origin"],
                     effective_from=dt.date.fromisoformat(policy["effective_from"]), account_id=policy["account_id"],
                     effective_until=None if policy["effective_until"] is None else dt.date.fromisoformat(policy["effective_until"]))


def project(case):
    """Project observable packet/diagnostic vocabulary into the issued fixture.

    U8 has no requested-rule API: eligibility plus absent family output is the
    selector refusal. This projection does not invent an engine diagnostic.
    """
    rule = case["input"]["rule"]
    current, baseline, policy_rows = normalized(case)
    current_source = source(current, "current")
    sources = [current_source]
    if baseline is not None:
        capital_choice = "FULL_NAV" if baseline["semantic_key"] == DATA["defaults"]["current"]["semantic_key"] else "HOLDINGS_ONLY"
        baseline_source = source(baseline, "baseline", capital_choice=capital_choice)
        sources.append(baseline_source)
    try:
        policies = tuple(user_limit(p, current, current_source) for p in policy_rows)
    except ValueError:
        if any(p["origin"] != "USER_CONFIRMED" or not p["decision_evidence"] for p in policy_rows):
            return {"outcome": "REFUSED", "reason": "NOT_A_USER_POLICY"}, None
        raise
    history = () if baseline is None else (HistoryComparison(MetricRef("current", current["metric_id"], tuple(current["subject"])),
                                                             MetricRef("baseline", baseline["metric_id"], tuple(baseline["subject"]))),)
    result = _generate(tuple(sources), policies, history, allow_synthetic=True)
    packets = [p.to_obj() for p in result.packets if p.to_obj()["insight_type"] == rule]
    if packets:
        if len(packets) != 1:
            raise AssertionError("one normalized predicate emitted several claims")
        packet = packets[0]
        relation = {"metric_snapshot": "MEASURED", "benchmark_underperformance": "BELOW_BENCHMARK",
                    "history_change": packet["claim"]["parameters"].get("direction"),
                    "user_limit": "ABOVE_MAXIMUM" if not policies or policies[0].direction == "MAXIMUM" else "BELOW_MINIMUM"}[rule]
        outcome = {"outcome": "SURFACED", "judgment_class": packet["judgment_class"], "severity": packet["severity"],
                   "comparison_basis": None if packet["comparison_basis"] is None else packet["comparison_basis"]["kind"], "relation": relation}
        if "DISPLAY_ROUNDING_HIDES_EXACT_DIFFERENCE" in packet["limitations"]:
            outcome["rounding_caveat_required"] = True
        return outcome, packet
    codes = {d["code"] for d in json.loads(result.diagnostics_json) if d["rule"] == rule}
    aliases = {"PRIMARY_BENCHMARK_UNBOUND": "MISSING_BENCHMARK", "UNSUPPORTED_POLICY_SELECTOR": "UNSUPPORTED_SELECTOR",
               "POLICY_SEMANTIC_MISMATCH": "POLICY_SELECTOR_MISMATCH", "POLICY_METRIC_NOT_PRESENT": "POLICY_SELECTOR_MISMATCH",
               "METRIC_SELECTOR_MISMATCH": "COMPARISON_MISMATCH", "SCOPE_MISMATCH": "COMPARISON_MISMATCH", "SEMANTIC_MISMATCH": "COMPARISON_MISMATCH",
               "STATISTICAL_HISTORY_NOT_COMPARABLE": "VARIABLE_SPAN_HISTORY_UNSUPPORTED" if current["requested_rule"] in ("MAX_AVAILABLE", "SINCE_INCEPTION") else "COMPARISON_MISMATCH"}
    reasons = {aliases.get(code, code) for code in codes}
    if len(reasons) > 1:
        raise AssertionError("several distinct predicate refusals: " + str(reasons))
    if reasons:
        return {"outcome": "REFUSED", "reason": reasons.pop()}, None
    if rule == "benchmark_underperformance" and (current["source"], current["metric_id"], current["subject"]) != ("CP4", "risk_active_return", []):
        return {"outcome": "REFUSED", "reason": "UNSUPPORTED_SELECTOR"}, None
    return {"outcome": "NOT_TRIGGERED"}, None


class GoldenPredicateTests(unittest.TestCase):
    def test_fixture_inventory_distinguishes_predicates_from_integrity_requirements(self):
        cases = DATA["cases"]
        self.assertEqual(len(cases), 67)
        self.assertEqual(len({c["id"] for c in cases}), 67)
        integrity = {c["id"]: c["input"]["upstream_failure"] for c in cases if "upstream_failure" in c["input"]}
        self.assertEqual(integrity, INTEGRITY_CASES)
        self.assertEqual(sum("upstream_failure" not in c["input"] for c in cases), 59)
        self.assertEqual(set(INTEGRITY_TESTS), set(INTEGRITY_CASES))
        for module, klass, method in INTEGRITY_TESTS.values():
            parsed = ast.parse(Path(__file__).with_name(module + ".py").read_text())
            owner = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == klass)
            self.assertIn(method, {node.name for node in owner.body if isinstance(node, ast.FunctionDef)})
        # This is an inventory assertion, not eight simulated integrity passes.
        # test_insight_sources/integration must exercise real upstream tampering.


def predicate_test(case):
    def test(self):
        actual, packet = project(case)
        self.assertEqual(actual, case["expected"], case["id"])
        if packet is not None:
            current, baseline, _policies = normalized(case)
            limitations = set(current["limitations"])
            if baseline is not None:
                limitations.update(baseline["limitations"])
            self.assertTrue(limitations.issubset(packet["limitations"]))
            self.assertTrue(packet["synthetic"])
            self.assertTrue(packet["claim"]["text"].startswith("SYNTHETIC"))
    return test


for _case in DATA["cases"]:
    if "upstream_failure" not in _case["input"]:
        setattr(GoldenPredicateTests, "test_" + _case["id"].replace("-", "_"), predicate_test(_case))
