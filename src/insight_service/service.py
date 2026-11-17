"""Public CP6 service: verify each upstream source, then apply the issued rules."""
from __future__ import annotations

import json

from insights.contracts import HistoryComparison, InsightRefusal, InsightResult, MetricRef, Reproduction, UserLimit
from insights.engine import _generate
from insight_service.sources import verify_source
from marketdata.canonical import canonical_json


def compute_insights(sources, *, policies=(), history=(), allow_synthetic=False):
    """Read-only composition; source or schema refusal exposes no financial number."""
    if type(allow_synthetic) is not bool:
        return InsightRefusal("INVALID_REQUEST", "allow_synthetic must be an explicit Boolean")
    try:
        sources, policies, history = tuple(sources), tuple(policies), tuple(history)
    except TypeError:
        return InsightRefusal("INVALID_REQUEST", "sources, policies and history must be iterable")
    if not sources:
        return InsightRefusal("NO_SOURCES", "at least one pinned upstream computation is required")
    if not all(isinstance(p, UserLimit) for p in policies) or not all(isinstance(h, HistoryComparison) for h in history):
        return InsightRefusal("INVALID_REQUEST", "policies and historical comparisons must use the immutable contract types")
    if not all(isinstance(h.current, MetricRef) and isinstance(h.baseline, MetricRef) for h in history):
        return InsightRefusal("INVALID_REQUEST", "each historical comparison requires two immutable metric references")
    verified = {}
    for source in sources:
        evidence = verify_source(source, allow_synthetic=allow_synthetic)
        if isinstance(evidence, InsightRefusal):
            return evidence
        if evidence.source_id in verified and evidence != verified[evidence.source_id]:
            return InsightRefusal("DUPLICATE_SOURCE_CONFLICT", "the same source identity has different evidence", evidence.source_id)
        verified[evidence.source_id] = evidence
    try:
        return _generate(tuple(verified.values()), policies, history, allow_synthetic=allow_synthetic)
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        return InsightRefusal("INVALID_REQUEST", str(error))


def reproduce_insights(saved, expected_result_digest, sources, *, policies=(), history=(), allow_synthetic=False):
    """Complete question and answer comparison, including added/missing null keys."""
    if not isinstance(saved, InsightResult):
        return Reproduction("INPUT_MISMATCH", "saved result must be the immutable InsightResult")
    rerun = compute_insights(sources, policies=policies, history=history, allow_synthetic=allow_synthetic)
    if isinstance(rerun, InsightRefusal):
        return Reproduction("SOURCE_REFUSED", rerun.code + ": " + rerun.detail)
    try:
        old, new = json.loads(saved.manifest_json), json.loads(rerun.manifest_json)
        if canonical_json(old) != canonical_json(new):
            return Reproduction("INPUT_MISMATCH", "complete source, policy, rule or method manifest differs", rerun)
        if saved.result_digest != rerun.result_digest:
            return Reproduction("RESULT_DIFFERS", "stored packets, claims, diagnostics or caveats differ", rerun)
        if expected_result_digest is None:
            return Reproduction("RESULT_NOT_COMPARED", "no expected result digest was supplied", rerun)
        if expected_result_digest != rerun.result_digest:
            return Reproduction("RESULT_DIFFERS", "expected answer digest differs", rerun)
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        return Reproduction("INPUT_MISMATCH", "invalid saved canonical structure: " + str(error))
    return Reproduction("REPRODUCED", "", rerun)
