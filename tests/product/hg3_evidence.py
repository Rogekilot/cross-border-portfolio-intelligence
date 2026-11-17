"""Export observed HG3 synthetic evidence, never an approval or an expected result
masquerading as an actual value. Run with ``python -m tests.product.hg3_evidence
--output /tmp/new-directory`` from the project root under its Python 3.12 runtime.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
import sys
from dataclasses import asdict, replace
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests/product"))

from diversification import registry as diversification_registry
from diversification.contracts import INSUFFICIENT, metric
from diversification.core import CAPITAL_IDS, EXPOSURE_IDS
from diversification.drift import Baseline, Target, compute_drift_result, qualifiers, snapshot as freeze_snapshot
from marketdata.canonical import canonical_json
from product_contract.performance_methodology_registry import REGISTRY as PERFORMANCE_REGISTRY
from risk.registry import REGISTRY as RISK_REGISTRY
from tests.product import cp4_golden_kit as cp4
from tests.product import test_diversification_golden as cp5
from tests.product import test_diversification_drift as drift_inputs
from tests.product.test_diversification_integration import compute_case, compute_fx_case, configuration

LABEL = "SYNTHETIC CANDIDATE EVIDENCE: no HG3, source, capital-policy, production or user-target approval"
EDGE_ASSERTIONS = {
    "short_history": ("P3-A1", "P8-L1", "C5-H3"),
    "missing_fx": ("P7-F1", "C5-S3"),
    "missing_cost_basis": ("P6-B1",),
    "cash_only": ("P4-C1", "C5-H7"),
    "single_security": ("P3-A1", "C5-H13"),
    "multi_currency": ("P5-M1", "C5-S1"),
    "recent_listing": ("P8-L1", "P11-R1"),
    "missing_benchmark": ("Q1-U2", "Q4-C0", "C5-D9"),
}


def _plain(value):
    return json.loads(canonical_json(value))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _definition(family, metric_id):
    if family == "CP4":
        return RISK_REGISTRY.resolved(metric_id), RISK_REGISTRY.registry_id, RISK_REGISTRY.digest
    data = diversification_registry.REGISTRY
    row = next(row for row in data["entries"] if row["metric_id"] == metric_id)
    def expand(value):
        if isinstance(value, str) and value.startswith("common.") and " " not in value:
            item = data
            for key in value.split("."):
                item = item[key]
            return expand(item)
        if isinstance(value, dict):
            return {key: expand(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expand(item) for item in value]
        return value
    return expand(row), diversification_registry.REGISTRY_ID, diversification_registry.REGISTRY_DIGEST


def _witness(metric):
    return _plain(metric.to_obj() if hasattr(metric, "to_obj") else metric.to_canonical_dict())


def _expected_decimal(expected):
    """Independent Decimal evaluation of a fixture expression, only for evidence
    comparison; it never computes the exported actual value or a product result.
    """
    with localcontext() as ctx:
        ctx.prec = 100
        if expected.get("exact") is not None:
            q = Fraction(expected["exact"])
            value = Decimal(q.numerator) / Decimal(q.denominator)
        elif expected.get("exact_square") is not None:
            q = Fraction(expected["exact_square"])
            value = (Decimal(q.numerator) / Decimal(q.denominator)).sqrt() * expected.get("sign", 1)
        else:
            return None
        return value.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP)


def compare_metric(actual, expected):
    """Compare only fields independently specified. State-only is explicit."""
    mismatches, fields = [], []
    if expected is None:
        return {"status": "NO_INDEPENDENT_EXPECTATION", "checked_fields": [], "mismatches": []}
    def check(name, observed, wanted):
        fields.append(name)
        if observed != wanted:
            mismatches.append({"field": name, "expected": _plain(wanted), "actual": _plain(observed)})
    for field in ("state", "reason", "sign"):
        if field in expected:
            check(field, actual.get(field), expected[field])
    if expected.get("detail"):
        check("details_include:" + expected["detail"], expected["detail"] in actual.get("details", ()), True)
    if "exact" in expected:
        if expected["exact"] is None:
            for field in ("value", "exact", "exact_square"):
                check(field, actual.get(field), None)
            check("radical_terms", actual.get("radical_terms", []), [])
        elif actual.get("exact") is not None:
            check("exact", Fraction(actual["exact"]), Fraction(expected["exact"]))
        elif actual.get("exact_square") is not None:
            q = Fraction(expected["exact"])
            check("exact_square", Fraction(actual["exact_square"]), q * q)
            check("sign", actual.get("sign"), (q > 0) - (q < 0))
    if expected.get("exact_square") is not None:
        if actual.get("exact_square") is not None:
            check("exact_square", Fraction(actual["exact_square"]), Fraction(expected["exact_square"]))
    if expected.get("exact") is not None or expected.get("exact_square") is not None:
        check("presented_value", None if actual.get("value") is None else Decimal(actual["value"]), _expected_decimal(expected))
    if "value" in expected:
        check("value", None if actual.get("value") is None else Decimal(actual["value"]), None if expected["value"] is None else Decimal(expected["value"]))
    numeric = any(name in fields for name in ("exact", "exact_square", "presented_value", "value"))
    return {"status": "MISMATCH" if mismatches else "MATCH" if numeric else "STATE_ONLY_MATCH",
            "checked_fields": fields, "mismatches": mismatches}


def _record(result, artifacts):
    text = result.canonical_json()
    manifest_id = result.manifest_id if hasattr(result, "manifest_id") else result.manifest.manifest_id
    key = "computations/" + manifest_id + "-" + result.result_digest + ".json"
    artifacts[key] = text + "\n"
    return key


def _row(family, case_id, m, expected, source, *, path, result=None, artifacts=None, context=None, comparison=None):
    definition, version, registry_digest = _definition(family, m.metric_id)
    actual = _witness(m)
    ctx = {} if context is None else context
    manifest = None
    if result is not None:
        manifest = json.loads(result.manifest_json) if hasattr(result, "manifest_json") else _plain(result.manifest.to_obj())
    window = actual.get("window", ctx.get("window", None if manifest is None else manifest.get("window")))
    currency = ctx.get("reporting_currency")
    if currency is None and manifest is not None:
        currency = manifest.get("reporting_currency", manifest.get("series_manifest", {}).get("reporting_currency"))
    frequency = actual.get("frequency", ctx.get("frequency", "AS_OF"))
    benchmark = actual.get("benchmark", ctx.get("benchmark", "NOT_APPLICABLE"))
    observation_count = actual.get("observation_count")
    source_method = None
    if family == "CP5" and m.metric_id in CAPITAL_IDS + EXPOSURE_IDS:
        frequency = "AS_OF"
        window = {"as_of": (manifest or {}).get("as_of", (ctx.get("window") or {}).get("as_of"))}
    if manifest is not None and manifest.get("schema") == "finweb.drift_manifest/1":
        source_content = manifest["current"]["content"]
        source_manifest = source_content["manifest"]
        source_row = next((r for r in source_content["metrics"] if r["metric_id"] == m.subject[0] and tuple(r.get("subject", ())) == m.subject[1:]), None)
        # A target id is appended to drift_target_gap's subject.
        if source_row is None and m.metric_id == "drift_target_gap":
            source_row = next((r for r in source_content["metrics"] if r["metric_id"] == m.subject[0] and tuple(r.get("subject", ())) == m.subject[1:-1]), None)
        currency = source_manifest.get("reporting_currency", source_manifest.get("series_manifest", {}).get("reporting_currency"))
        if source_row is not None:
            source_method = source_row.get("method_key")
            frequency = source_row.get("frequency", "AS_OF")
            window = source_row.get("window", {"as_of": source_manifest.get("as_of")})
            benchmark = source_row.get("benchmark", "NOT_APPLICABLE")
            observation_count = source_row.get("observation_count")
    row = {"family": family, "case_id": case_id, "metric_id": m.metric_id, "subject": actual.get("subject", []), "evidence_path": path,
           "actual": actual, "expected": expected, "comparison": compare_metric(actual, expected) if comparison is None else comparison,
           "input": source, "formula": definition["formula"], "method_version": version, "registry_digest": registry_digest,
           "benchmark": benchmark, "window": window, "source_method_key": source_method,
           "frequency": frequency, "reporting_currency": currency,
           "observation_count": observation_count, "minimum_data_rule": definition["minimum_observations"],
           "thresholds": actual.get("thresholds"), "tolerance": {"exact_witness": "0", "state": "exact", "presentation_quantum": "0.000000000001"},
           "limitations": definition["known_limitations"], "label": LABEL,
           "computation_ref": None if result is None else _record(result, artifacts)}
    row["exposure_decomposition"] = next((part.to_obj() for part in getattr(result, "exposure_decompositions", ()) if part.metric_id == m.metric_id), None)
    return row


def cp4_rows(parts, artifacts, missing, cases):
    rows = []
    for part in parts:
        runner = cp4.shared_runner(part)
        for index, (portfolio, assertion, item) in enumerate(cp4.items(runner.data)):
            case_id = assertion["id"]
            input_ref = {"fixture": str(cp4.FIXTURE_DIR.relative_to(ROOT) / cp4.PART_FILES[part]), "portfolio": portfolio["name"],
                         "assertion_id": case_id, "item_index": index, "kind": item["kind"], "request": item.get("request"),
                         "as_of": assertion.get("as_of"), "instant": assertion.get("instant")}
            if item["kind"] not in cp4.KIND_METRIC:
                # Run existing checks, but do not invent an output serialization
                # for selection/rate/series/default-view objects.
                bad = cp4.check_item(runner, portfolio, assertion, item)
                cases.append({"family": "CP4", "case_id": case_id, "kind": item["kind"], "status": "MISMATCH" if bad else "CHECK_ONLY",
                              "input": input_ref, "expected": item, "actual": None, "mismatches": [asdict(b) for b in bad]})
                missing.append({"case_id": case_id, "kind": item["kind"], "reason": "Supporting check executed, actual structured output not materialized; no scalar result invented"})
                continue
            mid = cp4.KIND_METRIC[item["kind"]]
            result = runner.risk(portfolio, assertion, item, (mid,))
            m = result.metric(mid)
            bad = cp4.check_metric_item(result, assertion, item)
            comparison = {"status": "MISMATCH" if bad else "MATCH", "checked_fields": "Existing independent CP4 golden checker: value, exact witness, state, window, causes and applicable lineage",
                          "mismatches": [asdict(b) for b in bad]}
            rows.append(_row("CP4", case_id, m, item, input_ref, path="INTEGRATED_LEDGER_MARKET_ENGINE", result=result, artifacts=artifacts, comparison=comparison))
            cases.append({"family": "CP4", "case_id": case_id, "kind": item["kind"], "status": comparison["status"], "input": input_ref})
    return rows


def _case_expect(case):
    expected = copy.deepcopy(case["expected"])
    ref = expected.get("same_metrics_as") or expected.get("other_metrics_same_as")
    if ref:
        inherited = _case_expect(cp5.CASES[ref])
        if "other_metrics_same_as" in expected:
            for key in ("clusters", "cluster_count", "correlation_cluster_count"):
                inherited.pop(key, None)
        inherited.update(expected)
        expected = inherited
    return expected


def _cp5_expected(case, m):
    e, mid = _case_expect(case), m.metric_id
    if "all_concentration_and_exposure" in e:
        return e["all_concentration_and_exposure"]
    if "metrics" in e:
        if mid in e["metrics"]:
            return e["metrics"][mid]
        dimension = mid.removesuffix("_exposure")
        spec = e.get("exposures", {}).get(dimension)
        if spec is not None and m.subject and m.subject[0] in spec["categories"]:
            return {k: v for k, v in spec.items() if k != "categories"} | {"exact": spec["categories"][m.subject[0]]}
        return None
    if "statistical_metrics" in e:
        return e["statistical_metrics"]
    result = {k: e[k] for k in ("state", "detail") if k in e}
    specific = e.get(mid)
    if mid == "pairwise_correlation":
        pair = "|".join(m.subject)
        specific = e.get("pairwise", {}).get(pair, e.get("unaffected_pair", {}).get(pair))
        short = {("SECURITY:A", "SECURITY:B"): "pair_A_B", ("SECURITY:A", "SECURITY:C"): "pair_A_C", ("SECURITY:B", "SECURITY:C"): "pair_B_C"}.get(m.subject)
        specific = e.get(short, specific)
    elif mid == "correlation_cluster_count" and specific is None and "clusters" in e:
        specific = {"exact": e.get("cluster_count", str(len(e["clusters"])))}
    elif mid == "risk_contribution_share" and m.subject:
        specific = e.get("risk_shares", {}).get(m.subject[0], specific)
    elif mid == "modeled_volatility" and specific is None and "annual_variance" in e:
        specific = {"exact_square": e["annual_variance"], "sign": 0 if Fraction(e["annual_variance"]) == 0 else 1}
    elif mid == "risk_contribution_component" and "annual_variance" in e and m.subject and m.subject[0] in e.get("risk_shares", {}):
        share = Fraction(e["risk_shares"][m.subject[0]])
        specific = {"exact_square": str(share * share * Fraction(e["annual_variance"])), "sign": (share > 0) - (share < 0),
                    "derived_from_independent_fixture": "risk_share * sqrt(annual_variance)"}
    elif mid == "risk_contribution_component" and e.get("risk_contribution_share", {}).get("detail") == "ZERO_MODEL_VARIANCE":
        specific = dict(e["risk_contribution_share"], derived_from_independent_fixture="CP5 section 6: shares and components both undefined at fixture Q=0")
    if isinstance(specific, str):
        specific = {"exact": specific}
    if isinstance(specific, dict):
        specific = dict(specific)
        if "signed_sqrt" in specific:
            specific["exact_square"] = specific.pop("signed_sqrt")
        if "squared" in specific:
            specific["exact_square"] = specific.pop("squared")
        if "coefficient" in specific:
            c = Fraction(specific["coefficient"])
            specific.update(exact_square=str(c * c * Fraction(specific["radicand"])), sign=(c > 0) - (c < 0))
        result.update(specific)
    if mid == "average_correlation" and "average_correlation_presented" in e:
        result["value"] = e["average_correlation_presented"]
    return result or None


def _drift_case(case):
    """Expand the Quant's D1--D9 input numbers into explicit synthetic envelopes."""
    spec, cid = case["input"], case["id"]
    old_date = datetime.date.fromisoformat(spec.get("baseline_as_of", "2025-11-28"))
    new_date = datetime.date.fromisoformat(spec.get("current_as_of", spec.get("as_of", "2025-12-26")))
    mid = spec.get("metric", "largest_position_weight")
    if cid == "C5-D2":
        old = drift_inputs.capital(tuple(metric(mid, (k,), exact=Fraction(v)) for k, v in spec["baseline_complete_map"].items()), old_date)
        new = drift_inputs.capital(tuple(metric(mid, (k,), exact=Fraction(v)) for k, v in spec["current_complete_map"].items()), new_date)
    elif cid == "C5-D9":
        old = drift_inputs.risk(mid, as_of=old_date, state=INSUFFICIENT, reason=spec["baseline_reason"])
        new = drift_inputs.risk(mid, exact=Fraction(spec["current_exact"]), as_of=new_date)
    else:
        old = drift_inputs.capital((metric(mid, exact=Fraction(spec.get("baseline_exact", "1/4"))),), old_date)
        new = drift_inputs.capital((metric(mid, exact=Fraction(spec["current_exact"])),), new_date)
    if cid == "C5-D7":
        old = drift_inputs.capital(old.metrics, old_date, reporting_currency="HKD")
    before = Baseline("SYNTHETIC-" + cid, freeze_snapshot(old), spec.get("accepted", True), spec.get("acceptance_reference", "SYNTHETIC-ACCEPTANCE-FIXTURE"))
    targets = ()
    if cid in ("C5-D3", "C5-D5"):
        q = qualifiers(new)[0]
        targets = (Target(spec.get("target_id", "SYNTHETIC-" + cid), q, Fraction(spec["target_exact"]),
                          datetime.date.fromisoformat(spec.get("effective_date", "2025-11-01")), spec["origin"], "SYNTHETIC-USER-FIXTURE"),)
    result = compute_drift_result(new, None if case["kind"] == "target" else before, targets)
    wanted = "drift_target_gap" if case["kind"] == "target" else "drift_absolute"
    return result, tuple(m for m in result.metrics if m.metric_id == wanted)


def cp5_rows(case_ids, artifacts, missing, cases):
    rows = []
    for case_id in case_ids:
        case = cp5.CASES[case_id]
        spec, kind = cp5.inputs(case), case["kind"]
        source = {"fixture": "methodology/fixtures/cp5_golden/cp5_golden_part1.json", "case_id": case_id, "expanded_input": spec}
        context = {"reporting_currency": spec.get("reporting_currency", "USD"), "frequency": spec.get("frequency", "AS_OF"),
                   "window": {"as_of": spec.get("as_of", cp5.FIXTURE["as_of"]), "grid_start": spec.get("grid_start"), "n": spec.get("n")}}
        result, clusters = None, None
        if kind in ("snapshot", "snapshot_identity", "snapshot_refusal"):
            metrics, _ = cp5.snapshot(case)
            expected = lambda m: _cp5_expected(case, m)
            path = "PURE_CAPITAL_KERNEL_EXPLICIT_SYNTHETIC_INPUTS"
        elif kind in ("history", "history_radical", "history_refusal", "single_security_history", "zero_model_history"):
            metrics, clusters = cp5.history(case)
            expected = lambda m: _cp5_expected(case, m)
            path = "PURE_STATISTICS_KERNEL_EXPLICIT_SYNTHETIC_RETURN_VECTORS"
        elif kind in ("drift", "target"):
            result, metrics = _drift_case(case)
            def expected(m):
                e = case["expected"]
                if "category_deltas" in e:
                    return {"exact": e["category_deltas"][m.subject[1]]}
                return e[m.metric_id]
            path = "DRIFT_ENGINE_EXPLICIT_PINNED_SYNTHETIC_SNAPSHOTS"
        elif kind == "universe_refusal":
            overrides = {"capital_policy": None} if case_id == "C5-P1" else {"metadata": replace(configuration(cp4.shared_runner(1))["metadata"], synthetic=False)}
            result, *_ = compute_case(**overrides)
            metrics = tuple(m for m in result.metrics if m.metric_id not in ("pairwise_correlation", "correlation_cluster_count"))
            expected = lambda m: case["expected"]["capital_dependent_metrics"]
            path = "INTEGRATED_LEDGER_MARKET_ENGINE_POLICY_REFUSAL"
        elif kind == "return_translation":
            history, files = compute_fx_case()
            actual_return = history.observations[0].value
            expected_return = Fraction(case["expected"]["reporting_return"])
            actual = {"history": history.to_obj(), "files": [[f.file_sha256, f.adapter_id, f.adapter_version] for f in files]}
            cases.append({"family": "CP5", "case_id": case_id, "status": "MATERIALIZED" if actual_return == expected_return else "MISMATCH",
                          "evidence_path": "NATIVE_PRICE_AND_FX_PORT_TO_REPORTING_SECURITY_HISTORY", "input": source,
                          "actual": actual, "expected": case["expected"], "checked_fields": ["reporting_return"],
                          "comparison_limit": "Cross-term identity and sign remain separately checked by the integration test; only the reporting return is compared here"})
            continue
        else:
            missing.append({"case_id": case_id, "kind": kind, "reason": "Reusable output-producing builder not exported for this fixture kind; no actual copied from expected"})
            cases.append({"family": "CP5", "case_id": case_id, "status": "NOT_MATERIALIZED", "input": source, "expected": case["expected"], "actual": None})
            continue
        case_rows = [_row("CP5", case_id, m, expected(m), source, path=path, result=result, artifacts=artifacts, context=context) for m in metrics]
        rows.extend(case_rows)
        e = _case_expect(case)
        case_record = {"family": "CP5", "case_id": case_id, "status": "MISMATCH" if any(r["comparison"]["status"] == "MISMATCH" for r in case_rows) else "MATERIALIZED",
                       "input": source, "metric_rows": len(case_rows)}
        if clusters is not None:
            case_record["actual_clusters"] = clusters
            if "clusters" in e:
                case_record["expected_clusters"] = e["clusters"]
                if _plain(clusters) != e["clusters"]:
                    case_record.update(status="MISMATCH", cluster_mismatch=True)
        cases.append(case_record)
        for row in case_rows:
            if row["comparison"]["status"] in ("NO_INDEPENDENT_EXPECTATION", "STATE_ONLY_MATCH"):
                missing.append({"case_id": case_id, "metric_id": row["metric_id"], "subject": row["subject"],
                                "reason": "Actual materialized; independent numerical expectation absent for this row"})
    return rows


def integration_rows(artifacts, cases):
    """One auditable ledger-to-market CP5 example alongside kernel fixtures.
    Its model volatility expected value comes from the independent CP4 fixture.
    Other rows remain observations, without manufactured expectations.
    """
    result, runner, portfolio, _ = compute_case()
    wanted = next(it for it in portfolio["assertions"][0]["expect"] if it["kind"] == "volatility")
    context = {"reporting_currency": portfolio["reporting_currency"], "frequency": "WEEKLY"}
    source = {"fixture": "methodology/fixtures/cp4_golden/cp4_golden_part1.json", "portfolio": portfolio["name"], "assertion_id": portfolio["assertions"][0]["id"],
              "adapter": "tests.product.test_diversification_integration.compute_case", "capital_policy": "EXPLICIT_SYNTHETIC_CANDIDATE"}
    rows = []
    for m in result.metrics:
        expected = {k: wanted[k] for k in ("state", "value", "exact_square", "sign")} if m.metric_id == "modeled_volatility" else None
        rows.append(_row("CP5", "CP5-INTEGRATED-P3", m, expected, source, path="INTEGRATED_LEDGER_MARKET_ENGINE", result=result, artifacts=artifacts, context=context))
    cases.append({"family": "CP5", "case_id": "CP5-INTEGRATED-P3", "status": "MATERIALIZED", "metric_rows": len(rows),
                  "scope": "Independent numerical comparison only for modeled volatility; other metrics are observed outputs with their manifests"})
    return rows


def build_evidence(*, cp4_parts=(1, 2, 3, 4), cp5_case_ids=None, include_integration=True):
    """Execute current engine paths. No output file is written by this function."""
    cp4_parts = tuple(cp4_parts)
    cp5_case_ids = tuple(sorted(cp5.CASES if cp5_case_ids is None else cp5_case_ids))
    artifacts, missing, cases = {}, [], []
    rows = cp4_rows(cp4_parts, artifacts, missing, cases)
    rows += cp5_rows(cp5_case_ids, artifacts, missing, cases)
    if include_integration:
        integrated = integration_rows(artifacts, cases)
        rows += integrated
        missing.extend({"case_id": row["case_id"], "metric_id": row["metric_id"], "subject": row["subject"],
                        "reason": "Integrated actual output materialized; no independent numerical expectation attached to this extra observation"}
                       for row in integrated if row["expected"] is None)
    missing.append({"kind": "CP5_COUNT_BOUNDARIES", "count": len(cp5.FIXTURE["threshold_boundary_assertions"]),
                    "reason": "Covered by GoldenTests.test_all_twelve_count_boundaries; individual boundary outputs not materialized by this exporter"})
    for family, ids in (("CP4", set(RISK_REGISTRY.metric_ids)), ("CP5", set(diversification_registry.METRIC_IDS))):
        observed = {row["metric_id"] for row in rows if row["family"] == family}
        for mid in sorted(ids - observed):
            missing.append({"family": family, "metric_id": mid, "reason": "No actual scalar row materialized in selected evidence scope"})
    present = {row["case_id"] for row in rows}
    edges = []
    for edge, refs in EDGE_ASSERTIONS.items():
        eligible = present
        if edge == "missing_fx":
            # A pointer alone cannot turn empty NAV or another refusal into FX
            # evidence: both the observed result and independent expectation agree.
            eligible = {row["case_id"] for row in rows
                        if row["actual"].get("state") == "INSUFFICIENT_DATA" and row["actual"].get("reason") == "MISSING_FX_HISTORY"
                        and (row["expected"] or {}).get("state") == "INSUFFICIENT_DATA" and (row["expected"] or {}).get("reason") == "MISSING_FX_HISTORY"}
        matched = sorted(set(refs) & eligible)
        edges.append({"edge_case": edge, "assertion_pointers": list(refs), "materialized_assertions": matched,
                      "status": "MATERIALIZED" if matched else "POINTER_ONLY"})
    files = [f"methodology/fixtures/cp4_golden/{cp4.PART_FILES[p]}" for p in cp4_parts]
    # the registry texts the engines run (market-data/1.16 label re-issue, section 11 item 35): performance-registry/1.2, risk/1.11, diversification/1.2
    files += ["methodology/fixtures/cp5_golden/cp5_golden_part1.json", "methodology/registry/PERFORMANCE_1.12_REGISTRY_APPENDIX_1.2.json",
              "methodology/registry/RISK_1.11_REGISTRY.json", "methodology/registry/DIVERSIFICATION_1.2_REGISTRY.json"]
    sources = []
    for path in files:
        raw = (ROOT / path).read_bytes()
        artifact = "inputs/" + Path(path).name
        artifacts[artifact] = raw.decode("utf-8")
        sources.append({"path": path, "sha256": _sha(raw), "artifact": artifact})
    implementation = {path: _sha((ROOT / path).read_bytes()) for path in (
        "src/diversification/core.py", "src/diversification/engine.py", "src/diversification/drift.py", "src/diversification/contracts.py",
        "src/diversification/numerics.py", "src/risk/engine.py",
        "src/risk/single.py", "src/risk/relative.py", "src/product_contract/performance_methodology_registry.py",
        "src/product_contract/performance_methodology_registry.json", "tests/product/hg3_evidence.py", "tests/product/cp4_golden_kit.py",
        "tests/product/test_diversification_golden.py", "tests/product/test_diversification_drift.py", "tests/product/test_diversification_integration.py")}
    numeric_mismatches = sum(row["comparison"]["status"] == "MISMATCH" for row in rows)
    case_mismatches = sum(case["status"] == "MISMATCH" for case in cases)
    summary = {"actual_metric_rows": len(rows), "cp4_actual_rows": sum(r["family"] == "CP4" for r in rows), "cp5_actual_rows": sum(r["family"] == "CP5" for r in rows),
               "cp4_checked_items": sum(c["family"] == "CP4" for c in cases), "cp4_check_only_items": sum(c["family"] == "CP4" and c["status"] == "CHECK_ONLY" for c in cases),
               "cp5_materialized_fixture_cases": sum(c["family"] == "CP5" and c["case_id"] in cp5_case_ids and c["status"] == "MATERIALIZED" for c in cases),
               "cp5_unmaterialized_fixture_cases": sum(c["family"] == "CP5" and c["case_id"] in cp5_case_ids and c["status"] == "NOT_MATERIALIZED" for c in cases),
               "major_metric_ids": {family: sorted({r["metric_id"] for r in rows if r["family"] == family}) for family in ("CP4", "CP5")},
               "numeric_or_state_mismatch_rows": numeric_mismatches, "case_mismatches": case_mismatches, "missing_items": len(missing),
               "independent_comparison_rows": sum(r["comparison"]["status"] == "MATCH" for r in rows),
               "state_only_rows": sum(r["comparison"]["status"] == "STATE_ONLY_MATCH" for r in rows),
               "observation_only_rows": sum(r["comparison"]["status"] == "NO_INDEPENDENT_EXPECTATION" for r in rows),
               "materialized_edge_cases": sum(e["status"] == "MATERIALIZED" for e in edges),
               "cp4_selected_parts": list(cp4_parts), "cp5_selected_cases": list(cp5_case_ids)}
    return {"schema": "finweb.hg3_evidence/1", "label": LABEL, "summary": summary, "sources": sources, "implementation_sha256": implementation,
            "rows": rows, "cases": cases, "edge_cases": edges, "missing": missing,
            "registry_inventory": {"performance": {"registry_id": PERFORMANCE_REGISTRY.registry_id, "appendix_id": PERFORMANCE_REGISTRY.appendix_id, "digest": PERFORMANCE_REGISTRY.digest,
                                                   "metric_ids": sorted(PERFORMANCE_REGISTRY.metric_ids)},
                                   "risk": {"registry_id": RISK_REGISTRY.registry_id, "digest": RISK_REGISTRY.digest},
                                   "diversification": {"registry_id": diversification_registry.REGISTRY_ID, "digest": diversification_registry.REGISTRY_DIGEST}},
            "limitations": ["All inputs are synthetic; real-data/source authorization is unproved by this output.",
                            "Kernel fixture rows do not prove ledger, identity or vendor-adapter integration; evidence_path distinguishes them.",
                            "CP5 capital universe remains an explicit synthetic candidate pending OD-CP5-01.",
                            "Missing and observation-only rows are not independent correctness proof.",
                            "This exporter materializes CP4/CP5 scalar evidence and FX1 history; supporting CP4 structured checks remain check-only.",
                            "Historical statistics and gaps do not establish causality, forecast, severity or an investment recommendation."],
            "artifacts": artifacts}


def markdown_report(evidence):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    summary = evidence["summary"]
    lines = ["# HG3 synthetic observed evidence", "", LABEL, "", "Actual rows: " + str(summary["actual_metric_rows"]) +
             "; independent comparisons: " + str(summary["independent_comparison_rows"]) + "; mismatched rows: " + str(summary["numeric_or_state_mismatch_rows"]) +
             "; explicit missing items: " + str(summary["missing_items"]) + ".", "",
             "Full values, exact witnesses, definitions, inputs, thresholds and limitations are in [evidence.json](evidence.json).", "",
             "| Family / case | Metric / subject | Actual value | State | Independent comparison | Path |", "|---|---|---|---|---|---|"]
    for row in evidence["rows"]:
        values = (row["family"] + " / " + row["case_id"], row["metric_id"] + " " + ",".join(row["subject"]),
                  row["actual"]["value"], row["actual"]["state"], row["comparison"]["status"], row["evidence_path"])
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
    lines += ["", "## Edge coverage", "", "| Edge | Status | Actual assertion ids |", "|---|---|---|"]
    for edge in evidence["edge_cases"]:
        lines.append("| " + " | ".join((edge["edge_case"], edge["status"], ", ".join(edge["materialized_assertions"]))) + " |")
    lines += ["", "## Missing or incomplete materialization", ""]
    lines += ["- " + cell(row) for row in evidence["missing"]] or ["None."]
    lines += ["", "## Limits", ""] + ["- " + text for text in evidence["limitations"]]
    return "\n".join(lines) + "\n"


def write_evidence(evidence, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    artifacts = dict(evidence["artifacts"])
    body = {key: value for key, value in evidence.items() if key != "artifacts"}
    artifacts["evidence.json"] = json.dumps(_plain(body), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    artifacts["README.md"] = markdown_report(evidence)
    manifest = {}
    for name, text in sorted(artifacts.items()):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        manifest[name] = _sha(text.encode("utf-8"))
    (output / "FILES_SHA256.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory; existing directories are never overwritten")
    parser.add_argument("--cp4-parts", default="1,2,3,4", help="comma-separated fixture parts; empty means none")
    parser.add_argument("--cp5-cases", default=None, help="comma-separated fixture ids; default all")
    parser.add_argument("--no-integration", action="store_true", help="omit the additional ledger-to-market CP5 example")
    args = parser.parse_args(argv)
    evidence = build_evidence(cp4_parts=tuple(int(p) for p in args.cp4_parts.split(",") if p),
                              cp5_case_ids=None if args.cp5_cases is None else tuple(c for c in args.cp5_cases.split(",") if c), include_integration=not args.no_integration)
    write_evidence(evidence, args.output)
    print(json.dumps(evidence["summary"], sort_keys=True))
    return int(bool(evidence["summary"]["numeric_or_state_mismatch_rows"] or evidence["summary"]["case_mismatches"]))


if __name__ == "__main__":
    raise SystemExit(main())
