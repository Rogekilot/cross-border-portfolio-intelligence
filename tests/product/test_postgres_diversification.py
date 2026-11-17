"""CP5 service and release projection parity through the least-privilege DB role."""
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp4_golden_kit as g
import pg_market_kit as pk
from test_postgres_cp4_golden import PgWorld
from test_diversification_integration import configuration, D
from diversification.engine import compute_diversification
from diversification_service.service import compute_diversification_for_portfolio
from domain.currency import CurrencyCode
from performance.grid import Frequency
from performance.periods import WindowRule, WindowSpec
from performance_service import service as perf
from persistence import ledger_replay_store
from risk_service.service import pin_ledger, SYNTHETIC_MARKET_DATA_REFUSED


@unittest.skipIf(bool(pk.skip_reason()), pk.skip_reason())
class PostgresDiversificationTests(PgWorld, unittest.TestCase):
    PART = 1

    def call(self, prefix="P3 ", **overrides):
        r = self.runner
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith(prefix)]
        pid = r.portfolio_ids[p["name"]]
        kw = dict(configuration(r, pid, overrides.get("account_scope")), request=WindowSpec(WindowRule.TRAILING_MONTHS, 36), frequency=Frequency.WEEKLY, policy=g.POLICY, allow_synthetic=True)
        kw.update(overrides)
        result = compute_diversification_for_portfolio(self.app, pid, D(2026, 1, 2), r.market.store, r.market.ident, r.market.conventions, r.perf, **kw)
        return result, p, pid, kw

    def test_service_is_exactly_the_engine_over_pinned_database_inputs(self):
        served, p, pid, kw = self.call()
        r = self.runner
        pin, events = pin_ledger(self.app, pid)
        direct = compute_diversification(events, pin, D(2026, 1, 2), CurrencyCode("USD"), r.market.store, r.market.ident, r.market.conventions, r.perf,
                                         suppressions=r.suppressions_for(p, pin), portfolio_id=pid, detection=perf.DETECTION, detection_policy=perf.policy_reference(g.POLICY),
                                         **{k: v for k, v in kw.items() if k not in ("policy", "allow_synthetic")})
        self.assertEqual(served.canonical_json(), direct.canonical_json())
        from fractions import Fraction
        self.assertEqual(served.metric("modeled_volatility").exact_square, Fraction(7803, 96875))
        self.assertTrue(json.loads(served.manifest_json)["synthetic"])

    def test_default_service_refuses_synthetic_and_uncommitted_ledger_pin(self):
        refused, _, pid, _ = self.call(allow_synthetic=False)
        self.assertEqual(refused.code, SYNTHETIC_MARKET_DATA_REFUSED)
        current, _ = pin_ledger(self.app, pid)
        with self.assertRaises(ledger_replay_store.LedgerVersionNotCommittedError):
            self.call(ledger_version=current + 10000)

    def test_missing_capital_policy_is_not_an_owner_decision(self):
        result, _, _, _ = self.call(capital_policy=None)
        self.assertIn("CAPITAL_UNIVERSE_UNCONFIRMED", result.metric("hhi_concentration").details)
        self.assertIsNone(json.loads(result.manifest_json)["weights"])

    def test_owner_decision_scope_is_enforced_against_database_portfolio_and_account(self):
        _, p, pid, kw = self.call()
        policy = replace(kw["capital_policy"], origin="USER_CONFIRMED", decision_id="synthetic-owner-scope-test/1", evidence="Synthetic test record only")
        scoped, _, _, _ = self.call(capital_policy=policy)
        self.assertIsNotNone(scoped.metric("hhi_concentration").result.value)
        wrong, _, _, _ = self.call(capital_policy=replace(policy, portfolio_id="different-portfolio"))
        self.assertIn("CAPITAL_UNIVERSE_UNCONFIRMED", wrong.metric("hhi_concentration").details)
        account = self.runner.ids(p["accounts"][0]["account_id"])
        inherited, _, _, _ = self.call(capital_policy=policy, account_scope=account)
        self.assertIn("CAPITAL_UNIVERSE_UNCONFIRMED", inherited.metric("hhi_concentration").details)
        specific, _, _, _ = self.call(capital_policy=replace(policy, scope_kind="ACCOUNT", account_id=str(account)), account_scope=account)
        self.assertIsNotNone(specific.metric("hhi_concentration").result.value)

    def test_no_cost_basis_and_foreign_cash_work_through_service(self):
        result, _, _, _ = self.call("P6 ")
        self.assertEqual(result.metric("hhi_concentration").exact, 1)
        foreign, _, _, _ = self.call("P5 ", request=WindowSpec(WindowRule.TRAILING_MONTHS, 12))
        self.assertGreater(foreign.metric("modeled_volatility").result.value, 0)
        self.assertEqual(foreign.metric("risk_contribution_share", ("CASH:HKD",)).exact, 1)

    def test_complete_analytics_composes_snapshot_and_all_required_risk_drift_sources(self):
        from diversification_service.service import compute_analytics_for_portfolio, AnalyticsBundle
        r = self.runner
        p = next(p for p in r.data["portfolios"] if p["name"].startswith("P3 "))
        bundle = compute_analytics_for_portfolio(self.app, r.portfolio_ids[p["name"]], D(2026, 1, 2), r.market.store, r.market.ident, r.market.conventions, r.perf,
                                                 policy=g.POLICY, allow_synthetic=True, **configuration(r, r.portfolio_ids[p["name"]]))
        self.assertIsInstance(bundle, AnalyticsBundle)
        self.assertEqual(bundle.risk.manifest.series.ledger_version, json.loads(bundle.diversification.manifest_json)["valuation_manifest"]["ledger_version"])
        self.assertEqual({m.metric_id for m in bundle.risk.metrics}, {"risk_beta", "risk_volatility", "risk_active_return", "risk_tracking_error", "risk_max_drawdown"})
        self.assertEqual(bundle.risk.metric("risk_beta").result.reason_code.value, "MISSING_BENCHMARK")
        self.assertIsNone(bundle.risk.metric("risk_beta").result.value)
        self.assertIsNotNone(bundle.risk.metric("risk_volatility").result.value)
        self.assertTrue(bundle.diversification_drift.metrics)
        self.assertTrue(bundle.risk_drift.metrics)
        for m in bundle.diversification_drift.metrics + bundle.risk_drift.metrics:
            self.assertIsNone(m.result.value)
            self.assertTrue({"NO_BASELINE", "NO_USER_TARGET"} & set(m.details))
