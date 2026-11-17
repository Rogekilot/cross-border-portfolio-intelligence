"""PD-0041 policy provenance and its explicit service-to-engine composition.

Only persistence reads are stubbed below: actual synthetic market adapters,
ledger events, F8-B detection and both CP4/CP5 financial engines run unchanged.
The policy authority is the genuine owner decision, not synthetic approval.
"""
import datetime as dt
import json
import sys
import unittest
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import cp4_golden_kit as g
from test_diversification_integration import configuration, compute_case
from diversification.contracts import PRODUCT_ID
from diversification.engine import compute_diversification
from diversification_service.approved_policy import compute_approved_analytics_for_portfolio
from diversification_service.service import compute_analytics_for_portfolio
from domain.currency import CurrencyCode
from performance_service import service as perf
from product_contract.analytics_policy import (ApprovedPolicyError, DECISION_FILE, DECISION_SHA256,
                                               REFERENCE_FILE, REFERENCE_SHA256, load_approved_capital_policy)


class ApprovedPolicyTests(unittest.TestCase):
    def test_immutable_record_binds_exact_owner_evidence_and_global_product_scope(self):
        policy = load_approved_capital_policy()
        self.assertEqual((policy.choice, policy.origin, policy.decision_id), ("FULL_NAV", "USER_CONFIRMED", "PD-0041"))
        self.assertEqual((policy.scope_kind, policy.product_id, policy.portfolio_id, policy.account_id),
                         ("GLOBAL_PRODUCT", PRODUCT_ID, None, None))
        self.assertTrue(policy.applies_to("portfolio-a", None))
        self.assertTrue(policy.applies_to("portfolio-b", "account-b"))
        evidence = json.loads(policy.evidence)
        self.assertEqual(evidence["decision"]["sha256"], DECISION_SHA256)
        self.assertEqual(evidence["reference_sha256"], REFERENCE_SHA256)
        self.assertEqual(evidence["presentation"]["largest_security_weight"], "SEPARATE")
        self.assertEqual(json.loads(REFERENCE_FILE.read_bytes())["personal_preferences"], [])
        with self.assertRaises(FrozenInstanceError):
            policy.choice = "HOLDINGS_ONLY"

    def test_offline_reproduction_is_identical(self):
        original = load_approved_capital_policy()
        reproduced = load_approved_capital_policy(reference_bytes=REFERENCE_FILE.read_bytes(), decision_bytes=DECISION_FILE.read_bytes())
        self.assertEqual(original, reproduced)
        self.assertEqual(original.digest, reproduced.digest)

    def test_reference_choice_scope_and_provenance_tampering_is_rejected(self):
        reference = json.loads(REFERENCE_FILE.read_bytes())
        for key, value in (("choice", "HOLDINGS_ONLY"), ("origin", "SYNTHETIC_CANDIDATE"),
                           ("product_id", "OTHER-PRODUCT"), ("scope_kind", "PORTFOLIO"),
                           ("portfolio_id", "portfolio-a"), ("account_id", "account-a")):
            with self.subTest(key=key):
                changed = dict(reference, **{key: value})
                with self.assertRaisesRegex(ApprovedPolicyError, "analytics policy digest"):
                    load_approved_capital_policy(reference_bytes=json.dumps(changed).encode())
        changed = dict(reference, decision=dict(reference["decision"], owner_statement="I never approved this"))
        with self.assertRaises(ApprovedPolicyError):
            load_approved_capital_policy(reference_bytes=json.dumps(changed).encode())

    def test_owner_decision_tampering_is_rejected(self):
        for decision in (b"", DECISION_FILE.read_bytes() + b"\nchanged after approval"):
            with self.subTest(size=len(decision)):
                with self.assertRaisesRegex(ApprovedPolicyError, "PD-0041 owner decision digest"):
                    load_approved_capital_policy(decision_bytes=decision)

    def test_missing_reference_or_decision_fails_closed(self):
        reference = REFERENCE_FILE.read_bytes()
        with patch.object(Path, "read_bytes", side_effect=FileNotFoundError("not present")):
            with self.assertRaisesRegex(ApprovedPolicyError, "analytics policy is unavailable"):
                load_approved_capital_policy()
            with self.assertRaisesRegex(ApprovedPolicyError, "owner decision is unavailable"):
                load_approved_capital_policy(reference_bytes=reference)

    def test_approved_entry_point_rejects_overrides_before_computation(self):
        with self.assertRaisesRegex(ApprovedPolicyError, "does not accept"):
            compute_approved_analytics_for_portfolio(capital_policy=None)


class ApprovedPolicyServiceTests(unittest.TestCase):
    def call(self, prefix="P3 ", *, approved=True, as_of=dt.date(2026, 1, 2), **overrides):
        runner = g.shared_runner(1)
        portfolio = next(p for p in runner.data["portfolios"] if p["name"].startswith(prefix))
        pid = runner.ids(portfolio["portfolio_id"])
        events = runner.events[portfolio["name"]]
        pin = max(e.ledger_seq for e in events)
        kw = dict(configuration(runner, pid), policy=g.POLICY, allow_synthetic=True)
        kw.pop("capital_policy")
        kw.update(overrides)
        # Boundaries stubbed are only reporting-currency / ledger / selection
        # persistence reads. Real service gating, detection and engines execute.
        with ExitStack() as stack:
            for module in ("diversification_service.service", "risk_service.service"):
                stack.enter_context(patch(module + ".currency_of", return_value=CurrencyCode(portfolio["reporting_currency"])))
                stack.enter_context(patch(module + ".pin_ledger", return_value=(pin, events)))
            stack.enter_context(patch("risk_service.service.pin_selection", return_value=(0, ())))
            service = compute_approved_analytics_for_portfolio if approved else compute_analytics_for_portfolio
            bundle = service(object(), pid, as_of, runner.market.store, runner.market.ident, runner.market.conventions, runner.perf, **kw)
        return bundle, runner, portfolio, pin, kw

    def test_actual_service_consumes_policy_and_matches_the_pinned_engine_result(self):
        bundle, runner, portfolio, pin, kw = self.call()
        policy = load_approved_capital_policy()
        pid = runner.ids(portfolio["portfolio_id"])
        result = bundle.diversification
        manifest = json.loads(result.manifest_json)
        self.assertEqual(manifest["capital_policy"], policy.to_obj())
        self.assertEqual(manifest["capital_policy_digest"], policy.digest)
        self.assertTrue(manifest["capital_policy_confirmed"])
        self.assertTrue(manifest["synthetic"])
        direct = compute_diversification(runner.events[portfolio["name"]], pin, dt.date(2026, 1, 2), CurrencyCode("USD"),
                                         runner.market.store, runner.market.ident, runner.market.conventions, runner.perf,
                                         suppressions=runner.suppressions_for(portfolio, pin), portfolio_id=pid,
                                         detection=perf.DETECTION, detection_policy=perf.policy_reference(g.POLICY),
                                         capital_policy=policy, **{k: v for k, v in kw.items() if k not in ("policy", "allow_synthetic")})
        self.assertEqual(result.canonical_json(), direct.canonical_json())
        self.assertEqual(result.result_digest, direct.result_digest)
        self.assertEqual(result.metric("hhi_concentration").exact, 1)
        self.assertEqual(result.metric("largest_security_weight").exact, 1)
        self.assertEqual(bundle.risk.manifest.series.ledger_version, pin)
        for metric in bundle.diversification_drift.metrics + bundle.risk_drift.metrics:
            self.assertIsNone(metric.result.value)
            self.assertTrue({"NO_BASELINE", "NO_USER_TARGET"} & set(metric.details))

    def test_global_policy_propagates_exact_requested_account_scope(self):
        runner = g.shared_runner(1)
        portfolio = next(p for p in runner.data["portfolios"] if p["name"].startswith("P3 "))
        account = runner.ids(portfolio["accounts"][0]["account_id"])
        bundle, _, _, _, _ = self.call(account_scope=account)
        manifest = json.loads(bundle.diversification.manifest_json)
        self.assertEqual(manifest["account_scope"], str(account))
        self.assertTrue(manifest["capital_policy_confirmed"])
        self.assertIsNotNone(bundle.diversification.metric("hhi_concentration").result.value)

    def test_full_nav_includes_cash_and_keeps_largest_security_separate(self):
        bundle, _, _, _, _ = self.call(prefix="P11 ", as_of=dt.date(2025, 10, 3))
        result = bundle.diversification
        manifest = json.loads(result.manifest_json)
        weights = {key: Fraction(value) for key, value in manifest["weights"]}
        self.assertTrue(any(key.startswith("CASH:") and value > 0 for key, value in weights.items()))
        self.assertEqual(sum(weights.values()), 1)
        security_weights = [value for key, value in weights.items() if key.startswith("SECURITY:")]
        self.assertLess(sum(security_weights), 1)
        self.assertEqual(result.metric("largest_security_weight").exact, max(security_weights))
        self.assertEqual(result.metric("largest_position_weight").exact, max(weights.values()))

    def test_ordinary_service_without_policy_remains_an_explicit_refusal(self):
        bundle, _, _, _, _ = self.call(approved=False)
        result = bundle.diversification
        self.assertFalse(json.loads(result.manifest_json)["capital_policy_confirmed"])
        self.assertIn("CAPITAL_UNIVERSE_UNCONFIRMED", result.metric("hhi_concentration").details)
        self.assertIsNone(result.metric("hhi_concentration").result.value)

    def test_engine_refuses_wrong_scope_or_missing_provenance_in_explicit_input(self):
        policy = load_approved_capital_policy()
        for invalid in (replace(policy, product_id="OTHER"), replace(policy, portfolio_id="OTHER"),
                        replace(policy, scope_kind=None), replace(policy, decision_id=None), replace(policy, evidence="")):
            with self.subTest(policy=invalid.to_obj()):
                result, _, _, _ = compute_case(capital_policy=invalid)
                self.assertIsNone(result.metric("hhi_concentration").result.value)
                self.assertIn("CAPITAL_UNIVERSE_UNCONFIRMED", result.metric("hhi_concentration").details)

    def test_approved_policy_does_not_bypass_synthetic_data_gate(self):
        refused, _, _, _, _ = self.call(allow_synthetic=False)
        self.assertEqual(refused.code, "SYNTHETIC_MARKET_DATA_REFUSED")
