"""CP5 §7: accepted exact comparisons and refusal of incompatible evidence.

The numerical expectations are the Quant's C5-D1--D9 and simple closed forms;
these tests do not acquire market data or connect to a database.
"""
import datetime
import json
import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from diversification.contracts import AVAILABLE, LIMITED, INSUFFICIENT, Metric, digest, metric, seal
from diversification.core import EXPOSURE_IDS
from diversification.drift import Baseline, Qualifier, Snapshot, Target, compute_drift, compute_drift_result, qualifiers, reproduce_drift, snapshot
from marketdata.canonical import canonical_json
from performance.grid import Frequency, effective_window, grid_dates
from performance.manifest import ComputationManifest
from performance.results import Cause, WindowUsed
from product_contract.metric_state import MetricResult
from product_contract.vocabulary import ReasonCode
from risk.manifest import BenchmarkBlock, RiskManifest, seal as seal_risk
from risk.results import BenchmarkRef, DrawdownFacts, RiskMetric

D = datetime.date
OLD, NOW = D(2025, 11, 28), D(2025, 12, 26)


def capital(rows=None, as_of=NOW, **changes):
    metadata = {"taxonomy": "SYN5-sector/1", "version": "1", "source": "SYNTHETIC", "as_of": "2020-01-01", "rows": []}
    valuation = {"portfolio_id": "portfolio", "reporting_currency": "USD", "state_kind": "ACTUAL", "conventions": [["valuation", "performance/1.12"]],
                 "release_id": "release-1", "ledger_version": 1, "scope": "PORTFOLIO"}
    policy = {"choice": "FULL_NAV", "origin": "SYNTHETIC_CANDIDATE", "evidence": "CP5-SYNTHETIC-FIXTURE",
              "decision_id": "SYNTHETIC-CP5-PORTFOLIO-SCOPE", "scope_kind": "PORTFOLIO", "product_id": None, "portfolio_id": "portfolio", "account_id": None}
    manifest = {"schema": "finweb.diversification_manifest/1", "engine_id": "test", "registry_id": "diversification/1.2", "registry_digest": "registry-digest",
                "portfolio_id": "portfolio", "account_scope": None, "reporting_currency": "USD", "state_kind": "ACTUAL", "as_of": as_of,
                "metadata": metadata, "metadata_digest": digest(metadata), "valuation_manifest": valuation,
                "capital_policy": policy, "capital_policy_confirmed": True, "synthetic": True,
                "complete_exposure_maps": list(EXPOSURE_IDS), "frequency": "WEEKLY", "request": {"rule": "TRAILING_MONTHS", "months": 36}}
    manifest.update(changes)
    return seal(manifest, (metric("largest_position_weight", exact=F(2, 5)),) if rows is None else rows)


def risk(mid="risk_beta", exact=F(6, 5), square=None, sign=1, as_of=NOW, state=AVAILABLE, reason=None,
         frequency="WEEKLY", rule="TRAILING_MONTHS", months=12, base=None, benchmark="BM", grid_rule="risk/1.0#2.2", **changes):
    base = as_of - datetime.timedelta(days=365) if base is None else base
    grid = grid_dates(Frequency(frequency), base, as_of)
    window = effective_window(rule, months, Frequency(frequency), base, as_of, grid, grid_rule)
    series = ComputationManifest("portfolio", "USD", 1, "ledger", as_of, WindowUsed(base, as_of, frequency, rule, months), "HISTORICAL",
                                 (("valuation", "performance/1.12"),), True, (), "release-1", (), (), "suppression", (), (), True)
    bm = BenchmarkBlock({}, benchmark, "catalog", "catalog-digest", "entry-" + benchmark, (), "UNHEDGED", True)
    ref = BenchmarkRef(benchmark, "selection", 1, 1, "catalog", return_basis="TOTAL_RETURN_GROSS", currency="USD", currency_treatment="UNHEDGED")
    base_metric = metric(mid, exact=exact if square is None else None, square=square, sign=sign, state=state, reason=reason,
                         details=("MISSING_BENCHMARK",) if state is INSUFFICIENT else ())
    rm = RiskMetric(mid, "risk/1.11#" + mid, base_metric.result, base_metric.exact, base_metric.exact_square, base_metric.sign,
                    frequency, rule, months, base, window, len(grid) - 1, (51, 155),
                    (Cause("source", state.value, reason, "", "MISSING_BENCHMARK"),) if state is INSUFFICIENT else (), base_metric.details,
                    benchmark=ref if mid in ("risk_beta", "risk_active_return", "risk_tracking_error") else None,
                    drawdown=DrawdownFacts(base, as_of, None, "WITHIN_WINDOW_FROM_BASE") if mid == "risk_max_drawdown" and state is not INSUFFICIENT else None)
    manifest = RiskManifest("risk-engine", "risk/1.11", "risk-registry-digest", (mid,), frequency, rule, months, base if rule == "CUSTOM" else None,
                            as_of, grid_rule, series, "series-digest", None, bm if rm.benchmark else None, (), True, (), True)
    manifest = replace(manifest, **changes)
    return seal_risk(manifest, (rm,))


def baseline(source=None, **changes):
    obj = Baseline("SYN5-BASELINE", snapshot(capital(as_of=OLD) if source is None else source), True, "SYNTHETIC-HUMAN-REFERENCE")
    return replace(obj, **changes)


def target(source, exact=F(3, 10), target_id="SYN5-USER-TARGET", **changes):
    obj = Target(target_id, qualifiers(source)[0], exact, D(2025, 11, 1), "EXPLICIT_USER", "SYNTHETIC-USER-REFERENCE")
    return replace(obj, **changes)


def pick(rows, mid="drift_absolute", source="largest_position_weight", subject=()):
    return next(m for m in rows if m.metric_id == mid and m.subject == (source,) + subject)


class ExactDriftTests(unittest.TestCase):
    def test_quant_c5_d1_current_minus_accepted_history(self):
        old = capital((metric("largest_position_weight", exact=F(1, 4)),), OLD)
        result = pick(compute_drift(capital(), baseline(old)))
        self.assertEqual(result.exact, F(3, 20))
        self.assertEqual(result.result.value, Decimal("0.15"))
        self.assertIs(result.state, AVAILABLE)

    def test_quant_c5_d8_never_subtract_displayed_values(self):
        old = capital((metric("largest_position_weight", exact=F(1000000000004, 10000000000000)),), OLD)
        new = capital((metric("largest_position_weight", exact=F(1000000000006, 10000000000000)),))
        result = pick(compute_drift(new, baseline(old)))
        self.assertEqual(result.exact, F(1, 5000000000000))
        self.assertEqual(result.result.value, Decimal("0"))
        self.assertEqual(new.metrics[0].result.value - old.metrics[0].result.value, Decimal("0.000000000001"))

    def test_root_difference_uses_unrounded_signed_values(self):
        old, new = risk("risk_volatility", square=F(8), as_of=OLD), risk("risk_volatility", square=F(2))
        result = pick(compute_drift(new, baseline(old)), source="risk_volatility")
        self.assertEqual(result.result.value, Decimal("-1.414213562373"))
        self.assertTrue(result.radical_terms)
        self.assertIsNone(result.exact)

    def test_equal_roots_cancel_exactly(self):
        old, new = risk("risk_volatility", square=F(2), as_of=OLD), risk("risk_volatility", square=F(2))
        result = pick(compute_drift(new, baseline(old)), source="risk_volatility")
        self.assertEqual(result.exact, F(0))
        self.assertFalse(result.radical_terms)

    def test_signed_root_and_rational_target(self):
        new = risk("risk_volatility", square=F(1, 4))
        t = target(new, exact=F(1, 5))
        result = pick(compute_drift(new, targets=(t,)), "drift_target_gap", "risk_volatility", (t.target_id,))
        self.assertEqual(result.exact, F(3, 10))

    def test_presentation_tie_keeps_numeric_value_state_and_radical_witness(self):
        root2_lower = F("1.4142135623730950488016887242096980785696718753769480731766797379907324784621070")
        new = risk("risk_volatility", square=F(2), state=LIMITED)
        for offset, shown in ((-F(1, 2 * 10**12), Decimal("0.000000000001")), (F(1, 2 * 10**12), Decimal("-0.000000000001"))):
            with self.subTest(shown=shown):
                t = target(new, exact=root2_lower + offset)
                result = pick(compute_drift(new, targets=(t,)), "drift_target_gap", "risk_volatility", (t.target_id,))
                self.assertIs(result.state, LIMITED)
                self.assertEqual(result.result.value, shown)
                self.assertIsNone(result.exact)
                self.assertTrue(result.radical_terms)
                self.assertTrue(any("PRESENTATION_TIE" in value for _, value in result.lineage))
                line = dict(result.lineage)
                self.assertLess(F(line["presentation_tie_width"]), F(1, 10**40))
                self.assertLessEqual(F(line["presentation_tie_low"]), F(line["presentation_tie_boundary"]))
                self.assertGreaterEqual(F(line["presentation_tie_high"]), F(line["presentation_tie_boundary"]))

    def test_exact_rational_half_tie_retains_its_equality_proof(self):
        for delta in (F(1, 2 * 10**12), -F(1, 2 * 10**12)):
            old = capital((metric("largest_position_weight", exact=F(1, 10)),), OLD)
            new = capital((metric("largest_position_weight", exact=F(1, 10) + delta),))
            result = pick(compute_drift(new, baseline(old)))
            self.assertEqual(result.exact, delta)
            self.assertEqual(result.result.value, Decimal("0.000000000001") if delta > 0 else Decimal("-0.000000000001"))
            self.assertEqual(dict(result.lineage)["presentation_tie_proof"], "EXACT_EQUALITY")
            self.assertEqual(dict(result.lineage)["presentation_tie_width"], "0")

    def test_all_cp4_requested_metrics_and_drawdown_sign(self):
        cases = (("risk_beta", F(6, 5), F(1)), ("risk_active_return", F(1, 20), F(-1, 20)),
                 ("risk_tracking_error", F(3, 20), F(1, 20)), ("risk_max_drawdown", F(-2, 5), F(-1, 4)))
        for mid, current, previous in cases:
            with self.subTest(mid=mid):
                result = pick(compute_drift(risk(mid, current), baseline(risk(mid, previous, as_of=OLD))), source=mid)
                self.assertEqual(result.exact, current - previous)
        self.assertIn("within-window", dict(result.lineage)["drawdown_definition"])


class BaselineRefusalTests(unittest.TestCase):
    def assert_refused(self, result, detail):
        self.assertIs(result.state, INSUFFICIENT)
        self.assertIsNone(result.result.value)
        self.assertIsNone(result.exact)
        self.assertIsNone(result.exact_square)
        self.assertFalse(result.radical_terms)
        self.assertIn(detail, result.details)

    def test_no_baseline_unaccepted_and_acceptance_without_evidence(self):
        for b, detail in ((None, "NO_BASELINE"), (baseline(accepted=False), "BASELINE_NOT_ACCEPTED"),
                          (baseline(acceptance_reference=""), "BASELINE_NOT_ACCEPTED"), (baseline(accepted=1), "BASELINE_NOT_ACCEPTED")):
            with self.subTest(b=b):
                self.assert_refused(pick(compute_drift(capital(), b)), detail)

    def test_same_date_and_future_are_not_historical(self):
        for date in (NOW, NOW + datetime.timedelta(days=1)):
            self.assert_refused(pick(compute_drift(capital(), baseline(capital(as_of=date)))), "INCOMPATIBLE_BASELINE")

    def test_missing_signature_and_portfolio_currency_scope_semantic_changes(self):
        for changes in ({"portfolio_id": None}, {"portfolio_id": "other"}, {"reporting_currency": "HKD"}, {"account_scope": "account"},
                        {"registry_id": "diversification/0.9"}, {"registry_digest": "different"}, {"state_kind": "HYPOTHETICAL"}):
            with self.subTest(changes=changes):
                self.assert_refused(pick(compute_drift(capital(), baseline(capital(as_of=OLD, **changes)))), "INCOMPATIBLE_BASELINE")

    def test_missing_and_changed_capital_policy_are_incompatible(self):
        for changes in ({"capital_policy": None}, {"capital_policy_confirmed": False}, {"synthetic": False},
                        {"capital_policy": {"choice": "FULL_NAV", "origin": "USER_CONFIRMED", "evidence": "different-policy"}}):
            self.assert_refused(pick(compute_drift(capital(), baseline(capital(as_of=OLD, **changes)))), "INCOMPATIBLE_BASELINE")

    def test_policy_confirmation_requires_structured_matching_scope(self):
        base_policy = json.loads(capital().manifest_json)["capital_policy"]
        invalid = ({"decision_id": None}, {"scope_kind": None}, {"portfolio_id": "OTHER-PORTFOLIO"},
                   {"scope_kind": "ACCOUNT", "account_id": "OTHER-ACCOUNT"},
                   {"scope_kind": "GLOBAL_PRODUCT", "product_id": "OTHER-PRODUCT", "portfolio_id": None},
                   {"scope_kind": "GLOBAL_PRODUCT", "product_id": None, "portfolio_id": None})
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                policy = dict(base_policy, **overrides)
                current = capital(capital_policy=policy, capital_policy_confirmed=True)
                old = capital(as_of=OLD, capital_policy=policy, capital_policy_confirmed=True)
                result = pick(compute_drift(current, baseline(old)))
                self.assert_refused(result, "INCOMPATIBLE_BASELINE")
        inherited = dict(base_policy)
        current = capital(account_scope="account", capital_policy=inherited)
        old = capital(as_of=OLD, account_scope="account", capital_policy=inherited)
        self.assert_refused(pick(compute_drift(current, baseline(old))), "INCOMPATIBLE_BASELINE")

    def test_scoped_synthetic_records_and_global_identity_compare_explicitly(self):
        base_policy = json.loads(capital().manifest_json)["capital_policy"]
        for policy, account in ((dict(base_policy, scope_kind="GLOBAL_PRODUCT", product_id="cross-border-portfolio-intelligence", portfolio_id=None), None),
                                (dict(base_policy, scope_kind="ACCOUNT", account_id="account"), "account")):
            result = pick(compute_drift(capital(account_scope=account, capital_policy=policy), baseline(capital(as_of=OLD, account_scope=account, capital_policy=policy))))
            self.assertIs(result.state, AVAILABLE)
            self.assertEqual(result.exact, 0)

    def test_cp4_frequency_window_grid_benchmark_changes(self):
        for changes in ({"frequency": "MONTHLY"}, {"months": 36}, {"grid_rule": "different-grid"}, {"benchmark": "OTHER"},
                        {"rule": "CUSTOM", "months": None}, {"registry_digest": "different"}):
            with self.subTest(changes=changes):
                self.assert_refused(pick(compute_drift(risk(), baseline(risk(as_of=OLD, **changes))), source="risk_beta"), "INCOMPATIBLE_BASELINE")

    def test_nonrolling_windows_require_equal_requested_duration(self):
        old = risk(as_of=OLD, rule="CUSTOM", months=None, base=OLD - datetime.timedelta(days=364))
        new = risk(rule="CUSTOM", months=None, base=NOW - datetime.timedelta(days=365))
        self.assert_refused(pick(compute_drift(new, baseline(old)), source="risk_beta"), "INCOMPATIBLE_BASELINE")
        equal = risk(as_of=OLD, rule="CUSTOM", months=None, base=OLD - datetime.timedelta(days=365))
        self.assertEqual(pick(compute_drift(new, baseline(equal)), source="risk_beta").exact, 0)

    def test_quant_c5_d9_insufficient_side_retains_existing_reason(self):
        old = risk(as_of=OLD, state=INSUFFICIENT, reason="MISSING_BENCHMARK")
        result = pick(compute_drift(risk(), baseline(old)), source="risk_beta")
        self.assert_refused(result, "MISSING_BENCHMARK")
        self.assertIs(result.result.reason_code, ReasonCode.MISSING_BENCHMARK)
        current = risk(state=INSUFFICIENT, reason="MISSING_BENCHMARK")
        result = pick(compute_drift(current, baseline(risk(as_of=OLD))), source="risk_beta")
        self.assert_refused(result, "MISSING_BENCHMARK")
        self.assertIs(result.result.reason_code, ReasonCode.MISSING_BENCHMARK)

    def test_limited_source_state_and_reason_propagate(self):
        old = capital((metric("largest_position_weight", exact=F(1, 4), state=LIMITED, reason="STALE_DATA", details=("STALE",)),), OLD)
        result = pick(compute_drift(capital(), baseline(old)))
        self.assertIs(result.state, LIMITED)
        self.assertIs(result.result.reason_code, ReasonCode.STALE_DATA)
        self.assertEqual(result.exact, F(3, 20))

    def test_market_vintage_and_ledger_changes_are_disclosed_not_refused(self):
        old = capital(as_of=OLD)
        m = json.loads(old.manifest_json)
        m["valuation_manifest"].update(release_id="older-release", ledger_version=0)
        result = pick(compute_drift(capital(), baseline(seal(m, old.metrics))))
        self.assertIs(result.state, AVAILABLE)
        self.assertIn("restatement", dict(result.lineage)["vintage_disclosure"])

    def test_snapshot_and_risk_result_tampering_are_refused(self):
        frozen = snapshot(capital(as_of=OLD))
        bad = replace(frozen, content_json=frozen.content_json.replace("portfolio", "tampered"))
        self.assert_refused(pick(compute_drift(capital(), baseline(bad))), "SNAPSHOT_DIGEST_MISMATCH")
        old = risk(as_of=OLD)
        altered = replace(old.metrics[0], exact=F(9), result=MetricResult(Decimal("9"), AVAILABLE))
        self.assert_refused(pick(compute_drift(risk(), baseline(replace(old, metrics=(altered,)))), source="risk_beta"), "SNAPSHOT_DIGEST_MISMATCH")

    def test_source_numeric_display_contradiction_is_refused(self):
        current = capital()
        invalid = replace(current.metrics[0], exact=F(9))
        result = pick(compute_drift(seal(json.loads(current.manifest_json), (invalid,)), baseline()))
        self.assert_refused(result, "INVALID_EXACT_SOURCE")

    def test_same_metric_twice_and_missing_manifest_stamp_are_refused(self):
        current = capital()
        duplicate = seal(json.loads(current.manifest_json), current.metrics * 2)
        self.assert_refused(pick(compute_drift(duplicate, baseline())), "DUPLICATE_SOURCE_METRIC")
        unstamped = replace(current, metrics=(replace(current.metrics[0], manifest_id=None),))
        self.assert_refused(pick(compute_drift(unstamped, baseline())), "SNAPSHOT_DIGEST_MISMATCH")


class ExposureAndTargetTests(unittest.TestCase):
    def maps(self):
        old = capital(tuple(metric("country_exposure", (k,), exact=v) for k, v in (("US", F(1, 2)), ("KY", F(1, 2)))), OLD)
        new = capital(tuple(metric("country_exposure", (k,), exact=v) for k, v in (("US", F(2, 5)), ("IE", F(3, 5)))))
        return old, new

    def test_quant_c5_d2_complete_union_has_zero_total_change(self):
        old, new = self.maps()
        rows = [m for m in compute_drift(new, baseline(old)) if m.metric_id == "drift_absolute"]
        self.assertEqual({m.subject[1]: m.exact for m in rows}, {"US": F(-1, 10), "KY": F(-1, 2), "IE": F(3, 5)})
        self.assertEqual(sum(m.exact for m in rows), 0)

    def test_apportioned_exposure_is_bound_but_drift_uses_exact_scalars(self):
        old = capital(tuple(metric("country_exposure", (k,), exact=F(1, 2)) for k in ("A", "B")), OLD)
        new = capital(tuple(metric("country_exposure", (k,), exact=F(1, 3)) for k in ("A", "B", "C")))
        partition, = new.exposure_decompositions
        self.assertEqual(partition.displayed_total, Decimal(1))
        self.assertEqual(sum(part.apportioned for part in partition.parts), 1)
        self.assertEqual(partition.parts[0].scalar, Decimal("0.333333333333"))
        self.assertEqual(partition.parts[0].apportioned, Decimal("0.333333333334"))
        result = pick(compute_drift(new, baseline(old)), source="country_exposure", subject=("A",))
        self.assertEqual(result.exact, -F(1, 6))
        self.assertEqual(result.result.value, Decimal("-0.166666666667"))
        self.assertNotEqual(result.result.value, partition.parts[0].apportioned - old.metric("country_exposure", ("A",)).result.value)
        changed = replace(partition, parts=(replace(partition.parts[0], apportioned=Decimal("0.333333333335")),) + partition.parts[1:])
        self.assertNotEqual(new.result_digest, replace(new, exposure_decompositions=(changed,)).result_digest)
        frozen = snapshot(new)
        tampered = replace(frozen, content_json=frozen.content_json.replace('"apportioned":"0.333333333334"', '"apportioned":"0.333333333335"'))
        refused = pick(compute_drift(tampered, baseline(old)), source="country_exposure", subject=("A",))
        self.assertIsNone(refused.result.value)
        self.assertIn("SNAPSHOT_DIGEST_MISMATCH", refused.details)

    def test_incomplete_map_never_supplies_implicit_zero(self):
        old, new = self.maps()
        incomplete = seal(json.loads(old.manifest_json), (old.metrics[0],))
        result = pick(compute_drift(new, baseline(incomplete)), source="country_exposure", subject=("IE",))
        self.assertIsNone(result.result.value)
        self.assertIn("INCOMPLETE_EXPOSURE_MAP", result.details)
        m = json.loads(old.manifest_json)
        del m["complete_exposure_maps"]
        result = pick(compute_drift(new, baseline(seal(m, old.metrics))), source="country_exposure", subject=("IE",))
        self.assertIsNone(result.result.value)

    def test_changed_metadata_or_taxonomy_refuses_reclassification_drift(self):
        old, new = self.maps()
        for field in ("taxonomy", "version"):
            m = json.loads(old.manifest_json)
            m["metadata"][field] = "changed"
            m["metadata_digest"] = digest(m["metadata"])
            result = pick(compute_drift(new, baseline(seal(m, old.metrics))), source="country_exposure", subject=("US",))
            self.assertIn("INCOMPATIBLE_BASELINE", result.details)
            self.assertIsNone(result.result.value)

    def test_metadata_difference_does_not_invalidate_concentration(self):
        m = json.loads(capital(as_of=OLD).manifest_json)
        m["metadata"] = None
        m["metadata_digest"] = None
        self.assertIs(pick(compute_drift(capital(), baseline(seal(m, capital().metrics)))).state, AVAILABLE)

    def test_explicit_target_gap_no_target_and_generated_target(self):
        new = capital((metric("largest_security_weight", exact=F(2, 5)),))
        t = target(new)
        result = pick(compute_drift(new, targets=(t,)), "drift_target_gap", "largest_security_weight", (t.target_id,))
        self.assertEqual(result.exact, F(1, 10))
        missing = pick(compute_drift(new), "drift_target_gap", "largest_security_weight")
        self.assertIn("NO_USER_TARGET", missing.details)
        generated = replace(t, provenance="MODEL_RECOMMENDATION")
        result = pick(compute_drift(new, targets=(generated,)), "drift_target_gap", "largest_security_weight", (t.target_id,))
        self.assertIn("TARGET_NOT_USER_DEFINED", result.details)
        self.assertIsNone(result.result.value)

    def test_future_ambiguous_nonexact_and_incompatible_targets(self):
        new = capital()
        t = target(new)
        cases = (replace(t, effective_date=NOW + datetime.timedelta(days=1)), replace(t, exact=Decimal("0.3")),
                 replace(t, qualifier=replace(t.qualifier, unit="RATIO")), replace(t, qualifier=replace(t.qualifier, reporting_currency="HKD")),
                 replace(t, qualifier=replace(t.qualifier, signature_json="{}")))
        for invalid in cases:
            result = pick(compute_drift(new, targets=(invalid,)), "drift_target_gap", subject=(t.target_id,))
            self.assertIn("INCOMPATIBLE_TARGET", result.details)
            self.assertIsNone(result.result.value)
        for changes in ({"evidence": ""}, {"provenance": "USER"}):
            result = pick(compute_drift(new, targets=(replace(t, **changes),)), "drift_target_gap", subject=(t.target_id,))
            self.assertIn("TARGET_NOT_USER_DEFINED", result.details)

    def test_independent_targets_and_missing_target_category_not_zero(self):
        old, new = self.maps()
        us = next(q for q in qualifiers(new) if q.subject == ("US",))
        t = Target("US-only", us, F(1, 2), OLD, "EXPLICIT_USER", "user-evidence")
        out = compute_drift(new, targets=(t,))
        self.assertEqual(pick(out, "drift_target_gap", "country_exposure", ("US", "US-only")).exact, F(-1, 10))
        self.assertIn("NO_USER_TARGET", pick(out, "drift_target_gap", "country_exposure", ("IE",)).details)
        absent = replace(t, target_id="KY-only", qualifier=replace(us, subject=("KY",)))
        self.assertEqual(pick(compute_drift(new, targets=(absent,)), "drift_target_gap", "country_exposure", ("KY", "KY-only")).exact, F(-1, 2))
        other = replace(t, target_id="another", exact=F(3, 5))
        results = compute_drift(new, targets=(t, other))
        self.assertEqual(pick(results, "drift_target_gap", "country_exposure", ("US", "another")).exact, F(-1, 5))

    def test_content_identity_immutability_and_determinism(self):
        source = capital()
        t1, t2 = target(source), target(source, target_id="other", exact=F(1, 5))
        b = baseline()
        first = compute_drift_result(source, b, (t1, t2))
        second = compute_drift_result(snapshot(source), b, (t2, t1))
        self.assertEqual(first.canonical_json(), second.canonical_json())
        self.assertEqual(snapshot(source).digest, snapshot(source).digest)
        self.assertNotEqual(t1.digest, replace(t1, evidence="different-evidence").digest)
        self.assertNotEqual(b.digest, replace(b, acceptance_reference="other-evidence").digest)
        with self.assertRaises(FrozenInstanceError):
            t1.exact = F(1)
        obj = b.to_obj()
        obj["snapshot"]["content"]["manifest"]["portfolio_id"] = "mutated-copy"
        self.assertEqual(b.digest, baseline().digest)
        with self.assertRaises(ValueError):
            compute_drift(source, targets=(t1, t1))

    def test_saved_comparison_reproduces_without_source_recomputation(self):
        source = capital()
        result = compute_drift_result(source, baseline(), (target(source),))
        self.assertEqual(reproduce_drift(result, result.result_digest).status, "REPRODUCED")
        self.assertEqual(reproduce_drift(result.manifest_json).status, "RESULT_NOT_COMPARED")
        self.assertEqual(reproduce_drift(result, "wrong-digest").status, "RESULT_DIFFERS")
        manifest = json.loads(result.manifest_json)
        manifest["engine_id"] = "different"
        self.assertEqual(reproduce_drift(canonical_json(manifest), result.result_digest).status, "MANIFEST_DIFFERS")

    def test_existing_cp4_engine_result_adapts_all_five_source_metrics(self):
        from tests.product.test_risk_engine import RequestTests
        mids = ("risk_beta", "risk_volatility", "risk_active_return", "risk_tracking_error", "risk_max_drawdown")
        result = RequestTests().call(metrics=mids)
        self.assertEqual({q.metric_id for q in qualifiers(result)}, set(mids))
        supplied = tuple(Target(mid, q, F(0), D(2025, 1, 1), "EXPLICIT_USER", "SYNTHETIC-USER-REFERENCE")
                         for mid in mids for q in qualifiers(result) if q.metric_id == mid)
        comparison = compute_drift_result(result, targets=supplied)
        for m in comparison.metrics:
            if m.metric_id == "drift_target_gap":
                self.assertEqual(m.result.value, result.metric(m.subject[0]).value)
                self.assertIs(m.state, result.metric(m.subject[0]).state)
        self.assertEqual(reproduce_drift(comparison, comparison.result_digest).status, "REPRODUCED")

    def test_integrated_cp5_sources_compare_and_policy_refusal_propagates(self):
        from tests.product.test_diversification_integration import compute_case
        old, *_ = compute_case(as_of=D(2025, 12, 26))
        new, *_ = compute_case()
        comparison = compute_drift_result(new, baseline(old))
        actual = [m for m in comparison.metrics if m.metric_id == "drift_absolute"]
        self.assertEqual(len(actual), 9)
        self.assertTrue(all(m.state is AVAILABLE and m.exact == 0 for m in actual))
        self.assertEqual(reproduce_drift(comparison, comparison.result_digest).status, "REPRODUCED")
        unconfirmed, *_ = compute_case(capital_policy=None)
        result = pick(compute_drift(unconfirmed, baseline(old)))
        self.assertIsNone(result.result.value)
        self.assertIn("CAPITAL_UNIVERSE_UNCONFIRMED", result.details)


if __name__ == "__main__":
    unittest.main()
