"""Replay upstream questions and adapt only the reproduced immutable answers.

The stored result itself is also compared: a correct advertised digest cannot vouch
for a tampered metric payload. No caller-supplied metric dictionary enters this seam.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, Tuple

from diversification.contracts import Result as DiversificationResult
from diversification.engine import reproduce_diversification
from insights.contracts import InsightRefusal, SourceEvidence, digest
from marketdata.canonical import canonical_json
from performance.engine import reproduce as reproduce_valuation
from performance.manifest import ComputationResult
from risk.engine import reproduce_risk
from risk.manifest import RiskResult


@dataclass(frozen=True)
class RiskSource:
    result: RiskResult
    events: tuple
    port: object
    resolver: object
    market_conventions: object
    conventions: object
    suppressions: tuple
    risk_free_catalog: object = None
    benchmark_catalog: object = None
    selections: tuple = ()
    boundary_rule: object = None
    market_at: object = None


@dataclass(frozen=True)
class DiversificationSource:
    result: DiversificationResult
    events: tuple
    port: object
    resolver: object
    market_conventions: object
    conventions: object
    suppressions: tuple
    metadata: object
    coverage: tuple = ()
    market_at: object = None
    freshness_result: object = None


def source_id(result, kind):
    mid = result.manifest.manifest_id if kind == "CP4" else result.manifest_id
    return kind + ":" + mid + ":" + result.result_digest


def _context(kind, result):
    if kind == "CP4":
        m = result.manifest.to_obj()
        base = m["series_manifest"]
        scope = base["scope"]
        account = None if scope == "PORTFOLIO" else scope.split(":", 1)[1]
        context = {"portfolio_id": base["portfolio_id"], "account_id": account, "portfolio_state": m["state_kind"], "scenario_id": None,
                   "reporting_currency": base["reporting_currency"], "as_of": m["end"], "instant": None if m.get("current") is None else m["current"]["instant"],
                   "valuation_mode": base["valuation_mode"], "ledger_version": base["ledger_version"], "ledger_digest": base["ledger_digest"],
                   "release_id": base["release_id"], "frequency": m["frequency"], "request": {"rule": m["request_rule"], "months": m["request_months"], "custom_base": m["request_base"]},
                   "registry_id": m["registry_id"], "registry_digest": m["registry_digest"], "engine_id": m["risk_engine_id"], "synthetic": m["synthetic"],
                   "capital_universe": "ACTUAL_PORTFOLIO_TWR", "complete_exposure_maps": [], "limitations": list(base["open_items"])}
    else:
        m = json.loads(result.manifest_json)
        base = m["valuation_manifest"]
        context = {"portfolio_id": m["portfolio_id"], "account_id": m["account_scope"], "portfolio_state": m["state_kind"], "scenario_id": None,
                   "reporting_currency": m["reporting_currency"], "as_of": m["as_of"], "instant": m["instant"], "valuation_mode": base["valuation_mode"],
                   "ledger_version": base["ledger_version"], "ledger_digest": base["ledger_digest"], "release_id": base["release_id"],
                   "frequency": m["frequency"], "request": m["request"], "registry_id": m["registry_id"], "registry_digest": m["registry_digest"],
                   "engine_id": m["engine_id"], "synthetic": m["synthetic"], "capital_universe": None if not m["capital_policy_confirmed"] else m["capital_policy"]["choice"],
                   "complete_exposure_maps": m["complete_exposure_maps"], "limitations": m["limitations"]}
    context["portfolio_snapshot_id"] = digest({k: context[k] for k in ("portfolio_id", "account_id", "portfolio_state", "as_of", "instant", "ledger_version", "ledger_digest", "release_id")})
    context["freshness"] = {"status": "UNKNOWN", "vector": None, "evidence": None}
    context["freshness_auxiliary"] = None
    return context


def _freshness_context(source, result, context):
    """Narrow CP3 auxiliary: authenticate CP5's *exact* valuation question/answer."""
    auxiliary = source.freshness_result
    if auxiliary is None:
        return context
    if not isinstance(auxiliary, ComputationResult):
        raise ValueError("FRESHNESS_AUXILIARY_INVALID: expected the CP3 ComputationResult")
    manifest = json.loads(result.manifest_json)
    if (canonical_json(auxiliary.manifest.to_obj()) != canonical_json(manifest["valuation_manifest"])
            or auxiliary.result_digest != manifest["valuation_result_digest"]):
        raise ValueError("FRESHNESS_AUXILIARY_MISMATCH: valuation manifest/scope/instant/answer is not CP5's exact dependency")
    report = reproduce_valuation(auxiliary.manifest, auxiliary.result_digest, source.events, source.port, source.resolver, source.market_conventions,
                                 source.conventions, suppressions=source.suppressions, market_at=source.market_at)
    if not report.reproduced or report.rerun is None or report.rerun.canonical_json() != auxiliary.canonical_json():
        raise ValueError("FRESHNESS_AUXILIARY_NOT_REPRODUCED: " + report.status.value)
    total = [m for m in report.rerun.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING" and not m.partial]
    if len(total) != 1:
        raise ValueError("FRESHNESS_AUXILIARY_INVALID: one full reporting total is required")
    vector = total[0].freshness
    status = "UNKNOWN" if vector is None else "FULL" if vector.summary == "CURRENT" else "LIMITED" if vector.summary == "STALE" else "UNKNOWN"
    context["freshness"] = {"status": status, "vector": None if vector is None else vector.to_obj(),
                            "evidence": {"manifest_id": auxiliary.manifest.manifest_id, "result_digest": auxiliary.result_digest, "metric_id": "portfolio_value", "view": "REPORTING"}}
    context["freshness_auxiliary"] = json.loads(auxiliary.canonical_json())
    return context


def verify_source(source, *, allow_synthetic=False):
    """A typed refusal on any replay/payload failure; a fresh adapter on success."""
    kind = "CP4" if isinstance(source, RiskSource) else "CP5" if isinstance(source, DiversificationSource) else None
    if kind is None:
        return InsightRefusal("UNSUPPORTED_SOURCE", "expected a RiskSource or DiversificationSource")
    expected_type = RiskResult if kind == "CP4" else DiversificationResult
    if not isinstance(source.result, expected_type):
        return InsightRefusal("UNSUPPORTED_SOURCE", "upstream result type does not match its source")
    sid = None
    try:
        sid = source_id(source.result, kind)
        if kind == "CP4":
            report = reproduce_risk(source.result.manifest, source.result.result_digest, source.events, source.port, source.resolver, source.market_conventions, source.conventions,
                                    suppressions=source.suppressions, risk_free_catalog=source.risk_free_catalog, benchmark_catalog=source.benchmark_catalog,
                                    selections=source.selections, boundary_rule=source.boundary_rule, market_at=source.market_at)
            status, rerun = report.status.value, report.rerun
        else:
            report = reproduce_diversification(source.result, source.result.result_digest, source.events, source.port, source.resolver, source.market_conventions, source.conventions,
                                               suppressions=source.suppressions, metadata=source.metadata, coverage=source.coverage, market_at=source.market_at)
            status, rerun = report.status, report.result
        if status != "REPRODUCED" or rerun is None:
            return InsightRefusal("SOURCE_NOT_REPRODUCED", status + ": " + report.detail, sid)
        if source.result.canonical_json() != rerun.canonical_json():
            return InsightRefusal("SOURCE_PAYLOAD_MISMATCH", "stored answer differs from the reproduced canonical answer", sid)
        context = _context(kind, rerun)
        if kind == "CP5":
            context = _freshness_context(source, rerun, context)
        if context["portfolio_state"] != "ACTUAL":
            return InsightRefusal("UNSUPPORTED_STATE", "CP6 currently accepts ACTUAL state only", sid)
        if not context["portfolio_id"]:
            return InsightRefusal("SCOPE_UNBOUND", "the upstream source must identify its portfolio", sid)
        if context["synthetic"] and allow_synthetic is not True:
            return InsightRefusal("SYNTHETIC_DATA_REFUSED", "synthetic evidence requires explicit labelled opt-in", sid)
        return SourceEvidence(sid, kind, rerun.canonical_json(), canonical_json(context))
    except (TypeError, ValueError, KeyError, AttributeError, OSError) as error:
        return InsightRefusal("SOURCE_INPUT_INVALID", str(error), sid)
