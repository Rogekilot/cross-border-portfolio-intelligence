"""Deterministic rules of insights/1.0, on internally verified source evidence.

Applications enter through insight_service.service.compute_insights. This module
has no price, ledger, policy-default, financial calculation, clock or LLM authority.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from insights import registry
from insights.contracts import InsightResult, MetricRef, ProofPacket, digest
from insights.evidence import (CAPITAL_SNAPSHOTS, compare_witness, history_problem, metric_rows, numeric_problem,
                               rational_witness, reference, semantic_fields, semantic_key, temporal_limited, temporal_status, metric_freshness)
from marketdata.canonical import canonical_json, sha256_hex

ENGINE_ID = "insights/cp6-0.1"


def implementation_digest():
    root = Path(__file__).resolve().parents[1]
    paths = ("insights/contracts.py", "insights/evidence.py", "insights/engine.py", "insights/registry.py",
             "insight_service/sources.py", "insight_service/service.py")
    return digest([[p, sha256_hex((root / p).read_bytes())] for p in paths])


def _metric_payload(source, row):
    c = source.context()
    window = row.get("window") if source.source_kind == "CP4" else source.payload()["manifest"].get("window")
    if source.source_kind == "CP5" and row["metric_id"] in CAPITAL_SNAPSHOTS:
        window, frequency = {"as_of": c["as_of"], "kind": "SNAPSHOT"}, None
    else:
        frequency = c["frequency"]
    return {"reference": reference(source, row).to_obj(), "metric": row, "semantic_key": semantic_key(source, row),
            "semantic_fields": semantic_fields(source, row), "source_manifest_id": source.payload()["manifest_id"],
            "source_result_digest": source.payload()["result_digest"], "portfolio_snapshot_id": c["portfolio_snapshot_id"],
            "portfolio_id": c["portfolio_id"], "account_id": c["account_id"], "as_of": c["as_of"], "instant": c["instant"],
            "period": window, "frequency": frequency, "observations": row.get("observation_count"),
            "portfolio_state": c["portfolio_state"], "scenario_id": c["scenario_id"], "synthetic": c["synthetic"]}


def _packet(rule, entries, *, basis=None, severity="OBSERVATION", parameters=None, extra_limitations=(), policy=None):
    first_source, first = entries[0]
    contexts = [s.context() for s, _m in entries]
    evidence = [_metric_payload(s, m) for s, m in entries]
    limitations = set(extra_limitations)
    for source, row in entries:
        limitations.update(source.context()["limitations"])
        limitations.update(row.get("details", ()))
        for cause in row.get("causes", ()):
            limitations.add(cause.get("detail") or cause.get("reason") or canonical_json(cause))
        if temporal_limited(row):
            limitations.add("LIMITED_TEMPORAL_COMPARABILITY")
        freshness = metric_freshness(source, row)
        if freshness["status"] != "FULL":
            limitations.add("SOURCE_FRESHNESS_" + freshness["status"])
        if source.source_kind == "CP5" and row["metric_id"] not in CAPITAL_SNAPSHOTS:
            limitations.add("POINT_IN_TIME_VALUATION_DOES_NOT_ATTEST_HISTORICAL_MODEL_INPUTS")
        if temporal_status(source, row) == "UNKNOWN":
            limitations.add("TEMPORAL_COMPARABILITY_UNKNOWN")
    limitations.add("Source observation/retrieval timestamps are UNKNOWN unless supplied by the upstream manifest; as-of is not a retrieval timestamp")
    synthetic = any(c["synthetic"] for c in contexts)
    state = "LIMITED" if any(m["state"] == "LIMITED" for _s, m in entries) else "AVAILABLE"
    params = {} if parameters is None else parameters
    subjects = "/".join(first.get("subject", ()))
    name = first["metric_id"] + (" [" + subjects + "]" if subjects else "")
    if rule == "metric_snapshot":
        text = f"{name} is {first['value']} as of {contexts[0]['as_of']}."
    elif rule == "benchmark_underperformance":
        text = f"Historical active return is {first['value']} versus the explicitly selected benchmark over the declared period."
    elif rule == "history_change":
        text = f"{name} {params['direction'].lower()} from {entries[1][1]['value']} to {first['value']} between the two recorded snapshots."
    else:
        relation = "exceeds" if policy.direction == "MAXIMUM" else "is below"
        text = f"Computed {name} ({first['value']}) {relation} your stated {policy.direction.lower()} limit ({policy.limit})."
    if state == "LIMITED" or any(temporal_status(s, m) != "FULL" or metric_freshness(s, m)["status"] != "FULL" for s, m in entries):
        text += " Evidence is limited; the stated limitations apply."
    if "DISPLAY_ROUNDING_HIDES_EXACT_DIFFERENCE" in limitations:
        text += " Rounded values can appear equal; the comparison uses the exact upstream witnesses."
    if synthetic:
        text = "SYNTHETIC — " + text
    if first_source.source_kind == "CP5" and first["metric_id"] not in CAPITAL_SNAPSHOTS:
        text += " This is a fixed-current-weight historical model, not realized portfolio history or a forecast."
    body = {"schema": "finweb.proof_packet/1", "insight_type": rule, "severity": severity,
            "judgment_class": registry.RULES[rule]["judgment_class"], "claim": {"text": text, "parameters": params, "caveats": sorted(limitations)},
            "metrics_used": evidence, "portfolio_snapshot_id": contexts[0]["portfolio_snapshot_id"],
            "portfolio_id": contexts[0]["portfolio_id"], "account_id": contexts[0]["account_id"],
            "portfolio_state": "ACTUAL", "scenario_id": None, "synthetic": synthetic, "comparison_basis": basis,
            "benchmark": first.get("benchmark"), "period": [e["period"] for e in evidence],
            "frequency": [e["frequency"] for e in evidence], "observations": [e["observations"] for e in evidence],
            "thresholds_limits": None if policy is None else {"policy": policy.to_obj(), "policy_digest": policy.policy_digest,
                                                            "decision_basis": "EXACT_UPSTREAM_WITNESS", "equality_is_breach": False},
            "source_data_timestamps": [{"source_id": s.source_id, "as_of": s.context()["as_of"], "calculation_instant": s.context()["instant"],
                                        "observed_at": "UNKNOWN", "retrieved_at": "UNKNOWN"} for s, _m in entries],
            "methodology_versions": {"insight": registry.METHOD_ID, "rule": registry.METHOD_ID + "#" + rule,
                                     "registry_digest": registry.REGISTRY_DIGEST, "conventions_digest": registry.METHOD_DIGEST,
                                     "upstream": [{"source_id": s.source_id, "engine_id": s.context()["engine_id"], "registry_id": s.context()["registry_id"],
                                                   "registry_digest": s.context()["registry_digest"], "method_key": m.get("method_key")} for s, m in entries]},
            "data_freshness": [{"reference": reference(s, m).to_obj(), "state": m["state"], "reason": m.get("reason"),
                                "causes": m.get("causes", []), "details": m.get("details", []), "stale_period_count": m.get("stale_period_count"),
                                "comparability": m.get("comparability"), "temporal_comparability_status": temporal_status(s, m),
                                "freshness_vector": m.get("freshness") or metric_freshness(s, m)["vector"] or "UNKNOWN",
                                "freshness_status": metric_freshness(s, m)["status"], "freshness_evidence": metric_freshness(s, m)["evidence"],
                                "freshness_scope": metric_freshness(s, m)["scope"]} for s, m in entries],
            "confidence_availability_state": state, "limitations": sorted(limitations),
            "permitted_suggested_explorations": ["INSPECT_SOURCE_EVIDENCE", "COMPARE_DECLARED_HISTORICAL_WINDOW"] + (["REVIEW_RECORDED_LIMIT"] if policy is not None else []),
            "source_evidence": [s.to_obj() for s in dict((s.source_id, s) for s, _m in entries).values()]}
    return ProofPacket(canonical_json(dict(body, insight_id=digest(body))))


def _generate(sources, policies=(), history=(), *, allow_synthetic=False):
    """Internal pure rule entry; service must verify every source before calling."""
    sources = tuple(sorted(sources, key=lambda s: s.source_id))
    policies = tuple(sorted({p.policy_digest: p for p in policies}.values(), key=lambda p: p.policy_digest))
    history = tuple(sorted({canonical_json(h.to_obj()): h for h in history}.values(), key=lambda h: canonical_json(h.to_obj())))
    index, packets, diagnostics = {}, [], []

    def diagnostic(rule, code, refs=(), **extra):
        diagnostics.append(dict(rule=rule, code=code, references=[r.to_obj() for r in refs], **extra))

    for source in sources:
        context = source.context()
        if context["portfolio_state"] != "ACTUAL" or context["scenario_id"] is not None:
            diagnostic("metric_snapshot", "SCENARIO_UNSUPPORTED")
            continue
        for row in metric_rows(source):
            ref = reference(source, row)
            if ref in index:
                raise ValueError("DUPLICATE_METRIC_REFERENCE")
            index[ref] = (source, row)
            problem = numeric_problem(row)
            if problem:
                diagnostic("metric_snapshot", problem, (ref,))
                continue
            packets.append(_packet("metric_snapshot", ((source, row),)))
            if source.source_kind == "CP4" and row["metric_id"] == "risk_active_return":
                bm = row.get("benchmark")
                if not bm or not bm.get("benchmark_id") or not bm.get("selection_id") or not bm.get("selection_seq"):
                    diagnostic("benchmark_underperformance", "PRIMARY_BENCHMARK_UNBOUND", (ref,))
                else:
                    try:
                        if compare_witness(row, rational_witness(Fraction())) < 0:
                            extra = ("DISPLAY_ROUNDING_HIDES_EXACT_DIFFERENCE",) if Decimal(row["value"]) == 0 else ()
                            packets.append(_packet("benchmark_underperformance", ((source, row),), basis={"kind": "BENCHMARK", "benchmark": bm}, extra_limitations=extra))
                    except (ValueError, TypeError, ZeroDivisionError) as error:
                        diagnostic("benchmark_underperformance", str(error), (ref,))

    for comparison in history:
        refs = (comparison.current, comparison.baseline)
        if any(r not in index for r in refs):
            diagnostic("history_change", "MISSING_METRIC_REFERENCE", refs)
            continue
        (cs, cm), (bs, bm) = (index[r] for r in refs)
        problem = numeric_problem(cm) or numeric_problem(bm) or history_problem(cs, cm, bs, bm)
        if problem:
            diagnostic("history_change", problem, refs)
            continue
        try:
            relation = compare_witness(cm, bm)
        except (ValueError, TypeError, ZeroDivisionError) as error:
            diagnostic("history_change", str(error), refs)
            continue
        if relation:
            extra = ("DISPLAY_ROUNDING_HIDES_EXACT_DIFFERENCE",) if Decimal(cm["value"]) == Decimal(bm["value"]) else ()
            packets.append(_packet("history_change", ((cs, cm), (bs, bm)), basis={"kind": "PORTFOLIO_HISTORY", "baseline": comparison.baseline.to_obj(),
                                                                                             "current": comparison.current.to_obj()},
                                   parameters={"direction": "INCREASED" if relation > 0 else "DECREASED"}, extra_limitations=extra))

    for ref, (source, row) in sorted(index.items()):
        candidates = [p for p in policies if (p.source_kind, p.metric_id, p.subject) == (source.source_kind, row["metric_id"], ref.subject)]
        if not candidates:
            continue
        if row["metric_id"] not in registry.POLICY_SELECTORS[source.source_kind]:
            diagnostic("user_limit", "UNSUPPORTED_POLICY_SELECTOR", (ref,))
            continue
        problem = numeric_problem(row)
        if problem:
            diagnostic("user_limit", problem, (ref,))
            continue
        c = source.context()
        active = []
        for policy in candidates:
            scope = "PORTFOLIO" if c["account_id"] is None else "ACCOUNT"
            day = dt.date.fromisoformat(c["as_of"])
            code = None
            if (policy.portfolio_id, policy.account_id, policy.scope_kind) != (c["portfolio_id"], c["account_id"], scope):
                code = "POLICY_SCOPE_MISMATCH"
            elif day < policy.effective_from or policy.effective_until is not None and day > policy.effective_until:
                code = "POLICY_NOT_EFFECTIVE"
            elif policy.semantic_key != semantic_key(source, row):
                code = "POLICY_SEMANTIC_MISMATCH"
            if code:
                diagnostic("user_limit", code, (ref,), policy_id=policy.policy_id, policy_digest=policy.policy_digest)
            else:
                active.append(policy)
        if len(active) > 1:
            diagnostic("user_limit", "POLICY_CONFLICT", (ref,), policy_digests=sorted(p.policy_digest for p in active))
            continue
        if not active:
            continue
        policy = active[0]
        try:
            relation = compare_witness(row, rational_witness(policy.limit))
        except (ValueError, TypeError, ZeroDivisionError) as error:
            diagnostic("user_limit", str(error), (ref,))
            continue
        breached = relation > 0 if policy.direction == "MAXIMUM" else relation < 0
        if breached:
            severity = "WARNING" if row["state"] == "AVAILABLE" and temporal_status(source, row) == "FULL" and metric_freshness(source, row)["status"] == "FULL" else "ATTENTION"
            extra = ("DISPLAY_ROUNDING_HIDES_EXACT_DIFFERENCE",) if Fraction(Decimal(row["value"])) == policy.limit else ()
            packets.append(_packet("user_limit", ((source, row),), basis={"kind": "USER_POLICY", "policy_id": policy.policy_id,
                                                                         "version": policy.version, "policy_digest": policy.policy_digest},
                                   severity=severity, extra_limitations=extra, policy=policy))

    # A policy is never silently accepted as relevant if no source row names it.
    for policy in policies:
        if not any((s.source_kind, row["metric_id"], ref.subject) == (policy.source_kind, policy.metric_id, policy.subject) for ref, (s, row) in index.items()):
            diagnostic("user_limit", "POLICY_METRIC_NOT_PRESENT", policy_id=policy.policy_id, policy_digest=policy.policy_digest)
    packets = tuple(sorted({p.insight_id: p for p in packets}.values(), key=lambda p: p.insight_id))
    diagnostics = sorted(diagnostics, key=canonical_json)
    manifest = {"schema": "finweb.insight_manifest/1", "engine_id": ENGINE_ID, "implementation_digest": implementation_digest(),
                "method_id": registry.METHOD_ID, "registry_digest": registry.REGISTRY_DIGEST, "conventions_digest": registry.METHOD_DIGEST,
                "state_kind": "ACTUAL", "scenario_id": None, "allow_synthetic": allow_synthetic,
                "sources": [s.to_obj() for s in sources], "policies": [p.to_obj() for p in policies], "history": [h.to_obj() for h in history],
                "rules": sorted(registry.RULES), "limitations": ["Only four issued deterministic families; no generic warning thresholds or forecasts", "HG3 66 supporting gaps remain disclosed; this is scoped new rule evidence"]}
    return InsightResult(canonical_json(manifest), packets, canonical_json(diagnostics))
