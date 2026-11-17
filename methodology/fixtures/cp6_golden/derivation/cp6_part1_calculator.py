"""Independent CP6 predicate checker: stdlib only, no product imports, no writes.

Expected outcomes are the authored specification, not harvested product outputs.
Symbolic upstream_failure rows check the required refusal contract; real tamper
and reproduction coverage belongs to separately reported integration tests.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from fractions import Fraction as F
from hashlib import sha256
import json
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "cp6_golden_part1.json"
POLICY_SELECTORS = {
    "CP4": {"risk_volatility", "risk_max_drawdown"},
    "CP5": {"largest_position_weight", "largest_security_weight", "top5_concentration", "hhi_concentration",
            "country_exposure", "sector_exposure", "currency_exposure", "asset_class_exposure"},
}


def refusal(reason):
    return {"outcome": "REFUSED", "reason": reason}


def surfaced(rule, relation, severity="OBSERVATION", rounding=False):
    klass, basis = {
        "metric_snapshot": ("FACT", None),
        "benchmark_underperformance": ("FACT", "BENCHMARK"),
        "history_change": ("INTERPRETATION", "PORTFOLIO_HISTORY"),
        "user_limit": ("PREFERENCE_DEPENDENT", "USER_POLICY"),
    }[rule]
    row = {"outcome": "SURFACED", "judgment_class": klass, "severity": severity,
           "comparison_basis": basis, "relation": relation}
    if rounding:
        row["rounding_caveat_required"] = True
    return row


def witness(row):
    if row.get("radical_terms"):
        raise ValueError("unsupported sum of radicals")
    if row.get("exact") is not None:
        q = F(row["exact"])
        return (0 if q == 0 else (1 if q > 0 else -1), q*q)
    if row.get("exact_square") is not None:
        q = F(row["exact_square"])
        s = row["sign"]
        if q < 0 or s not in (-1, 1):
            raise ValueError("invalid square-root witness")
        return (0 if q == 0 else s, q)
    raise ValueError("missing exact witness")


def cmp_witness(left, right):
    """A signed magnitude order, without calculating any square root."""
    sl, ql = left
    sr, qr = right
    if sl != sr:
        return (sl > sr) - (sl < sr)
    return sl * ((ql > qr) - (ql < qr))


def rational(q):
    q = F(q)
    return (0 if not q else (1 if q > 0 else -1), q*q)


def normalize(data, case):
    inp = case["input"]
    current = deepcopy(data["defaults"]["current"])
    current.update(inp.get("current", {}))
    baseline = None
    if "baseline" in inp:
        baseline = deepcopy(data["defaults"]["current"])
        baseline.update(data["defaults"]["baseline"])
        baseline.update(inp["baseline"])
    policies = []
    for spec in inp.get("policies", []):
        p = deepcopy(data["defaults"]["policy"])
        p.update(spec)
        policies.append(p)
    return inp, current, baseline, policies


def evaluate(data, case):
    inp, current, baseline, policies = normalize(data, case)
    rule = inp["rule"]
    if inp.get("upstream_failure"):
        return refusal("INPUT_INTEGRITY_FAILURE")
    for evidence in (current, baseline):
        if evidence is None:
            continue
        if evidence["portfolio_state"] != "ACTUAL" or evidence["scenario_id"] is not None:
            return refusal("SCENARIO_UNSUPPORTED")
        if evidence["state"] == "INSUFFICIENT_DATA":
            assert evidence["value"] is None and evidence["exact"] is None
            return refusal("INSUFFICIENT_DATA")
        assert evidence["value"] is not None
        if evidence["state"] == "LIMITED" or evidence["comparability"] != "FULL" or evidence["freshness"] != "FULL":
            assert evidence["limitations"], "a limited claim must retain an actual caveat"
    if rule == "metric_snapshot":
        return surfaced(rule, "MEASURED")
    try:
        current_exact = witness(current)
    except ValueError:
        return refusal("UNSUPPORTED_EXACT_ORDERING")
    if rule == "benchmark_underperformance":
        if (current["source"], current["metric_id"], current["subject"]) != ("CP4", "risk_active_return", []):
            return refusal("UNSUPPORTED_SELECTOR")
        if not current["benchmark"]:
            return refusal("MISSING_BENCHMARK")
        relation = cmp_witness(current_exact, rational(0))
        if relation >= 0:
            return {"outcome": "NOT_TRIGGERED"}
        return surfaced(rule, "BELOW_BENCHMARK", rounding=F(Decimal(current["value"])) >= 0)
    if rule == "history_change":
        assert baseline is not None
        keys = ("source", "metric_id", "subject", "portfolio_id", "account_id", "portfolio_state", "scenario_id",
                "reporting_currency", "semantic_key", "model_kind", "benchmark")
        if any(current[k] != baseline[k] for k in keys):
            return refusal("COMPARISON_MISMATCH")
        statistical = current["model_kind"] != "CAPITAL_SNAPSHOT"
        if statistical:
            if current["requested_rule"] in {"MAX_AVAILABLE", "SINCE_INCEPTION"}:
                return refusal("VARIABLE_SPAN_HISTORY_UNSUPPORTED")
            if any(current[k] != baseline[k] for k in ("frequency", "requested_rule", "requested_months", "observation_count")):
                return refusal("COMPARISON_MISMATCH")
        if date.fromisoformat(baseline["as_of"]) >= date.fromisoformat(current["as_of"]):
            return refusal("BASELINE_NOT_EARLIER")
        try:
            relation = cmp_witness(current_exact, witness(baseline))
        except ValueError:
            return refusal("UNSUPPORTED_EXACT_ORDERING")
        if relation == 0:
            return {"outcome": "NOT_TRIGGERED"}
        shown_relation = (Decimal(current["value"]) > Decimal(baseline["value"])) - (Decimal(current["value"]) < Decimal(baseline["value"]))
        return surfaced(rule, "INCREASED" if relation > 0 else "DECREASED", rounding=shown_relation != relation)
    assert rule == "user_limit"
    if current["metric_id"] not in POLICY_SELECTORS.get(current["source"], set()):
        return refusal("UNSUPPORTED_SELECTOR")
    if not policies:
        return {"outcome": "NOT_TRIGGERED"}
    unique = {json.dumps(p, sort_keys=True): p for p in policies}
    policies = list(unique.values())
    for policy in policies:
        if policy["origin"] != "USER_CONFIRMED" or not policy["decision_evidence"]:
            return refusal("NOT_A_USER_POLICY")
        if policy["portfolio_id"] != current["portfolio_id"]:
            return refusal("POLICY_SCOPE_MISMATCH")
        if current["account_id"] is None:
            if policy["scope"] != "PORTFOLIO" or policy["account_id"] is not None:
                return refusal("POLICY_SCOPE_MISMATCH")
        elif policy["scope"] != "ACCOUNT" or policy["account_id"] != current["account_id"]:
            return refusal("POLICY_SCOPE_MISMATCH")
        if any(current[k] != policy[k] for k in ("source", "metric_id", "subject", "semantic_key")):
            return refusal("POLICY_SELECTOR_MISMATCH")
        asof = date.fromisoformat(current["as_of"])
        if asof < date.fromisoformat(policy["effective_from"]) or (policy["effective_until"] is not None and asof > date.fromisoformat(policy["effective_until"])):
            return refusal("POLICY_NOT_EFFECTIVE")
    if len(policies) > 1:
        return refusal("POLICY_CONFLICT")
    policy = policies[0]
    limit = F(policy["limit"])
    relation = cmp_witness(current_exact, rational(limit))
    max_breach = policy["direction"] == "MAXIMUM" and relation > 0
    min_breach = policy["direction"] == "MINIMUM" and relation < 0
    if not max_breach and not min_breach:
        return {"outcome": "NOT_TRIGGERED"}
    severity = "WARNING" if current["state"] == "AVAILABLE" and current["comparability"] == "FULL" and current["freshness"] == "FULL" else "ATTENTION"
    shown = F(Decimal(current["value"]))
    shown_relation = (shown > limit) - (shown < limit)
    return surfaced(rule, "ABOVE_MAXIMUM" if max_breach else "BELOW_MINIMUM", severity, shown_relation != relation)


def main():
    raw = PATH.read_bytes()
    data = json.loads(raw)
    seen = set()
    assertions = 0
    for case in data["cases"]:
        assert case["id"] not in seen, case["id"]
        seen.add(case["id"])
        actual = evaluate(data, case)
        assert actual == case["expected"], (case["id"], actual, case["expected"])
        assertions += 1
        if actual["outcome"] == "SURFACED":
            assert (actual["severity"] in ("ATTENTION", "WARNING")) == (case["input"]["rule"] == "user_limit")
            assert actual["judgment_class"] == "FACT" or actual["comparison_basis"] in {"BENCHMARK", "USER_POLICY", "PORTFOLIO_HISTORY"}
            assertions += 2
    print(json.dumps({"fixture_id": data["fixture_id"], "cases_checked": len(seen), "assertions": assertions,
                      "differences": 0, "sha256": sha256(raw).hexdigest(),
                      "scope": "independent predicate specification checks; upstream financial/integrity integration not established here"}, sort_keys=True))


if __name__ == "__main__":
    main()
