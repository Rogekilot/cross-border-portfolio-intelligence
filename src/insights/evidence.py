"""Extract dependency semantics and compare existing exact upstream witnesses."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from insights.contracts import MetricRef, digest

CAPITAL_SNAPSHOTS = frozenset({"largest_position_weight", "largest_security_weight", "top5_concentration", "hhi_concentration", "effective_positions",
                               "country_exposure", "sector_exposure", "currency_exposure", "asset_class_exposure"})


def compare_witness(left, right):
    """Order rational or signed-root witnesses exactly; no displayed-value fallback."""
    def parts(row):
        if row.get("radical_terms"):
            raise ValueError("UNSUPPORTED_EXACT_ORDERING")
        exact, square = row.get("exact"), row.get("exact_square")
        if exact is not None and square is not None:
            raise ValueError("INCONSISTENT_WITNESS")
        if exact is not None:
            value = Fraction(exact)
            return (value > 0) - (value < 0), value * value
        if square is not None:
            q, sign = Fraction(square), row.get("sign")
            if q < 0 or type(sign) is not int or sign not in (-1, 0, 1) or (q > 0 and sign == 0):
                raise ValueError("INCONSISTENT_WITNESS")
            return 0 if q == 0 else sign, q
        raise ValueError("MISSING_EXACT_WITNESS")
    ls, lq = parts(left)
    rs, rq = parts(right)
    if ls != rs:
        return (ls > rs) - (ls < rs)
    return ls * ((lq > rq) - (lq < rq))


def rational_witness(value):
    return {"exact": str(value), "exact_square": None, "sign": None}


def metric_rows(source):
    """All upstream rows remain intact, including freshness/lineage extensions."""
    return source.payload()["metrics"]


def reference(source, metric):
    return MetricRef(source.source_id, metric["metric_id"], tuple(metric.get("subject", ())))


def numeric_problem(metric):
    state, value = metric.get("state"), metric.get("value")
    if state not in ("AVAILABLE", "LIMITED", "INSUFFICIENT_DATA"):
        return "INVALID_METRIC_STATE"
    if state == "INSUFFICIENT_DATA":
        return "INSUFFICIENT_DATA" if value is None and metric.get("exact") is None and metric.get("exact_square") is None and not metric.get("radical_terms") else "STATE_VALUE_CONTRADICTION"
    if value is None:
        return "STATE_VALUE_CONTRADICTION"
    try:
        shown = Decimal(value)
        if not shown.is_finite():
            return "INVALID_VALUE"
        if metric.get("exact") is not None or metric.get("exact_square") is not None:
            half_quantum = Fraction(1, 2 * 10**12)
            display = Fraction(shown)
            if compare_witness(metric, rational_witness(display - half_quantum)) < 0 or compare_witness(metric, rational_witness(display + half_quantum)) > 0:
                return "INCONSISTENT_WITNESS"
    except (ValueError, TypeError, InvalidOperation, ZeroDivisionError):
        return "INCONSISTENT_WITNESS"
    return None


def semantic_fields(source, metric):
    c = source.context()
    manifest = source.payload()["manifest"]
    base = manifest["series_manifest"] if source.source_kind == "CP4" else manifest["valuation_manifest"]
    is_snapshot = source.source_kind == "CP5" and metric["metric_id"] in CAPITAL_SNAPSHOTS
    benchmark = metric.get("benchmark")
    # Dates and selection-record identity are retained in the source. Binding
    # semantics include the benchmark identity/basis, not the mutable record id.
    bm = None if benchmark is None else {k: benchmark.get(k) for k in ("benchmark_id", "return_basis", "currency", "currency_treatment", "catalog_id", "source_id")}
    out = {"source_kind": source.source_kind, "metric_id": metric["metric_id"], "subject": list(metric.get("subject", ())),
           "reporting_currency": c["reporting_currency"], "portfolio_state": c["portfolio_state"], "scenario_id": c["scenario_id"],
           "model_semantics": "CAPITAL_SNAPSHOT" if is_snapshot else "CURRENT_FIXED_WEIGHT_HISTORICAL_MODEL" if source.source_kind == "CP5" else "ACTUAL_PORTFOLIO_HISTORY",
           "capital_universe": c["capital_universe"], "method_key": metric.get("method_key"), "registry_id": c["registry_id"],
           "registry_digest": c["registry_digest"], "engine_id": c["engine_id"], "valuation_mode": c["valuation_mode"], "benchmark": bm,
           "financial_conventions": base["conventions"]}
    if source.source_kind == "CP4" and benchmark is not None:
        out["benchmark_entry_digest"] = None if manifest.get("benchmark") is None else manifest["benchmark"]["entry_digest"]
    if source.source_kind == "CP4":
        # The risk-free dependency exists only for the relevant selected family;
        # bind the series/catalog semantics rather than its changing period values.
        if metric["metric_id"] in ("risk_sharpe", "risk_sortino", "risk_downside_deviation", "risk_alpha_jensen"):
            rf = manifest.get("risk_free")
            out["risk_free_binding"] = None if rf is None else {k: rf[k] for k in ("currency", "series_id", "catalog_id", "catalog_digest")}
        if metric["metric_id"] == "risk_max_drawdown":
            out["drawdown_peak_rule"] = None if metric.get("drawdown") is None else metric["drawdown"]["peak_rule"]
    if source.source_kind == "CP5" and metric["metric_id"] in ("sector_exposure", "country_exposure", "asset_class_exposure"):
        out["classification_taxonomy"] = None if manifest["metadata"] is None else manifest["metadata"]["taxonomy"]
    if source.source_kind == "CP5" and metric["metric_id"] == "correlation_cluster_count":
        out["cluster_threshold"] = manifest["cluster_threshold"]
    if not is_snapshot:
        out["frequency"], out["request"] = c["frequency"], c["request"]
        out["grid_rule"] = manifest.get("boundary_rule_id") if source.source_kind == "CP4" else None if manifest.get("window") is None else manifest["window"]["grid_rule"]
        out["coverage_semantics"] = None if source.source_kind == "CP4" else [{k: row[k] for k in ("listing_id", "source", "version", "confirmed", "return_basis")} for row in manifest["coverage"]]
    return out


def semantic_key(source, metric):
    return digest(semantic_fields(source, metric))


def temporal_limited(metric):
    return metric.get("comparability") is not None and metric["comparability"].get("class") == "LIMITED"


def temporal_status(source, metric):
    comparability = metric.get("comparability")
    if comparability is not None:
        return comparability.get("class", "UNKNOWN")
    # A single capital snapshot has no asynchronous pair of return legs.
    # This explicit non-applicability is separate from source freshness.
    return "FULL" if source.source_kind == "CP5" and metric["metric_id"] in CAPITAL_SNAPSHOTS else "UNKNOWN"


def metric_freshness(source, metric):
    if source.source_kind == "CP5" and metric["metric_id"] not in CAPITAL_SNAPSHOTS:
        return {"status": "UNKNOWN", "vector": None, "evidence": None,
                "scope": "POINT_IN_TIME_VALUATION_DOES_NOT_ATTEST_HISTORICAL_MODEL_INPUTS"}
    return dict(source.context()["freshness"], scope="CAPITAL_SNAPSHOT_VALUATION" if source.source_kind == "CP5" else "UPSTREAM_METRIC")


def history_problem(current_source, current, baseline_source, baseline):
    c, b = current_source.context(), baseline_source.context()
    if current["metric_id"] != baseline["metric_id"] or current.get("subject", []) != baseline.get("subject", []):
        return "METRIC_SELECTOR_MISMATCH"
    if (c["portfolio_id"], c["account_id"], c["portfolio_state"], c["scenario_id"]) != (b["portfolio_id"], b["account_id"], b["portfolio_state"], b["scenario_id"]):
        return "SCOPE_MISMATCH"
    if semantic_fields(current_source, current) != semantic_fields(baseline_source, baseline):
        return "SEMANTIC_MISMATCH"
    if dt.date.fromisoformat(b["as_of"]) >= dt.date.fromisoformat(c["as_of"]):
        return "BASELINE_NOT_EARLIER"
    if not (current_source.source_kind == "CP5" and current["metric_id"] in CAPITAL_SNAPSHOTS):
        if c["request"]["rule"] != "TRAILING_MONTHS" or current.get("observation_count") != baseline.get("observation_count"):
            return "STATISTICAL_HISTORY_NOT_COMPARABLE"
    return None
