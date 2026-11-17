"""CP5 through ledger replay, real file adapters, FX, action rules and manifests."""
import copy
import datetime as dt
import json
import os
import subprocess
import sys
import unittest
from dataclasses import replace
from decimal import localcontext
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import cp4_golden_kit as g
from diversification.contracts import CapitalUniverseChoice, Classification, MetadataSnapshot, TotalReturnCoverage
from diversification.engine import compute_diversification, compute_diversification_current, reproduce_diversification
from domain.currency import CurrencyCode
from performance.grid import Frequency
from performance.periods import WindowRule, WindowSpec

D = dt.date


def configuration(r, portfolio_id=None, account_scope=None):
    rows = tuple(Classification(str(r.ids(s["listing_id"])), "EXPLICIT_SYNTHETIC_COUNTRY", "EXPLICIT_SYNTHETIC_SECTOR") for s in r.data["listings"])
    metadata = MetadataSnapshot("synthetic-classification/1", "independent synthetic fixture", "synthetic-sector/1", D(2022, 1, 1), rows, synthetic=True)
    coverage = tuple(TotalReturnCoverage(str(r.ids(s["listing_id"])), "synthetic fixture action definitions", "cp4-source-fixture/1", r.data["fixture_id"],
                                        D(2022, 1, 1), D(2026, 12, 31), D(2022, 1, 1), True, synthetic=True) for s in r.data["listings"])
    return dict(metadata=metadata, coverage=coverage, cluster_threshold=F(3, 5), capital_policy=CapitalUniverseChoice(
        "FULL_NAV", "SYNTHETIC_CANDIDATE", "cp5 synthetic proof only", decision_id="synthetic-candidate/1",
        scope_kind="PORTFOLIO" if account_scope is None else "ACCOUNT", portfolio_id=None if portfolio_id is None else str(portfolio_id),
        account_id=None if account_scope is None else str(account_scope)))


def compute_case(part=1, prefix="P3 ", *, as_of=D(2026, 1, 2), **overrides):
    r = g.shared_runner(part)
    (p,) = [p for p in r.data["portfolios"] if p["name"].startswith(prefix)]
    version = max(e.ledger_seq for e in r.events[p["name"]])
    kw = dict(suppressions=r.suppressions_for(p, version), request=WindowSpec(WindowRule.TRAILING_MONTHS, 36), frequency=Frequency.WEEKLY,
              portfolio_id=r.ids(p["portfolio_id"]), **configuration(r, r.ids(p["portfolio_id"]), overrides.get("account_scope")))
    kw.update(overrides)
    result = compute_diversification(r.events[p["name"]], version, as_of, CurrencyCode(p["reporting_currency"]), r.market.store, r.market.ident, r.market.conventions, r.perf, **kw)
    return result, r, p, kw


def compute_fx_case():
    """C5-FX1 through deterministic source files, for both regression and HG3 evidence."""
    import test_cp1_reconstruction as cp1
    from diversification.contracts import Bucket
    from diversification.inputs import history_for
    data = copy.deepcopy(g.load_part(3))
    listing = "c4000000-0000-4000-8000-000000000021"
    price = next(s for s in data["market_data"]["prices"]["series"] if s["listing_id"] == listing)
    price.update(steps=[{"from": price["first"], "close": "100"}, {"from": "2025-12-26", "close": "110"}], cycle=None, gaps=[])
    fx = data["market_data"]["fx"]
    # USD/EUR is unpegged. EUR per USD falls from 1 to 4/5; using HKD/USD
    # for a 20% move would correctly trip the existing HKD peg guard.
    fx["steps"]["USD"] = [{"from": "2022-12-01", "rate": "1"}, {"from": "2025-12-26", "rate": "1.25"}]
    market = g.Market(data, cp1.Ids(randomize=False))
    try:
        coverage = TotalReturnCoverage(listing, "synthetic fixture", "fx1/1", "C5-FX1", D(2022, 1, 1), D(2026, 12, 31), D(2022, 1, 1), True, synthetic=True)
        return history_for(Bucket("SECURITY:" + listing, "SECURITY", "USD", F(1)), (D(2025, 1, 3), D(2025, 12, 26)), CurrencyCode("EUR"),
                           market.store, market.ident, market.conventions, coverage=coverage, as_of=D(2025, 12, 26))
    finally:
        market.close()


class IntegrationTests(unittest.TestCase):
    def test_single_listing_covariance_matches_the_independent_cp4_golden_volatility(self):
        result, r, p, kw = compute_case()
        expected = next(i for i in p["assertions"][0]["expect"] if i["kind"] == "volatility")
        m = result.metric("modeled_volatility")
        self.assertEqual(m.exact_square, F(expected["exact_square"]))
        self.assertEqual(m.state.value, expected["state"])
        self.assertEqual(str(m.result.value), expected["value"])
        self.assertEqual(result.metric("hhi_concentration").exact, 1)
        share = next(m for m in result.metrics if m.metric_id == "risk_contribution_share")
        self.assertEqual(share.exact, 1)
        self.assertIn("TOO_FEW_SECURITIES", result.metric("average_correlation").details)
        manifest = json.loads(result.manifest_json)
        self.assertTrue(manifest["history_files"])
        self.assertTrue(manifest["synthetic"])
        self.assertTrue(manifest["coverage_digest"])
        self.assertEqual(len(manifest["histories"][0]["observations"]), 156)

    def test_cash_only_is_not_fake_security_or_risk_allocation(self):
        result, _, _, _ = compute_case(prefix="P4 ", as_of=D(2026, 1, 30))
        self.assertEqual(result.metric("largest_position_weight").exact, 1)
        self.assertEqual(result.metric("modeled_volatility").result.value, 0)
        self.assertIn("NO_SECURITY_POSITIONS", result.metric("largest_security_weight").details)
        self.assertIn("ZERO_MODEL_VARIANCE", result.metric("risk_contribution_share", ("CASH:USD",)).details)

    def test_foreign_cash_risk_uses_fx_history(self):
        result, _, p, _ = compute_case(prefix="P5 ", request=WindowSpec(WindowRule.TRAILING_MONTHS, 12))
        expected = next(i for i in p["assertions"][0]["expect"] if i["kind"] == "volatility")
        self.assertEqual(result.metric("modeled_volatility").exact_square, F(expected["exact_square"]))
        self.assertGreater(result.metric("modeled_volatility").result.value, 0)
        self.assertEqual(result.metric("currency_exposure", ("HKD",)).exact, 1)
        self.assertEqual(result.metric("risk_contribution_share", ("CASH:HKD",)).exact, 1)

    def test_missing_cost_basis_does_not_change_concentration_or_security_risk(self):
        result, _, _, _ = compute_case(prefix="P6 ")
        baseline, _, _, _ = compute_case()
        for mid in ("hhi_concentration", "largest_position_weight", "modeled_volatility"):
            a, b = result.metric(mid), baseline.metric(mid)
            self.assertEqual((a.exact, a.exact_square, a.state), (b.exact, b.exact_square, b.state))

    def test_incomplete_fx_never_uses_partial_nav_and_recovery_is_explicit(self):
        result, _, _, _ = compute_case(prefix="P7 ", as_of=D(2025, 6, 13))
        for mid in ("hhi_concentration", "currency_exposure", "modeled_volatility"):
            m = result.metric(mid)
            self.assertIsNone(m.result.value)
            self.assertIsNone(m.exact)
        self.assertIsNone(json.loads(result.manifest_json)["weights"])

    def test_recent_listing_does_not_shorten_requested_history(self):
        result, _, _, _ = compute_case(prefix="P11 ")
        self.assertIsNotNone(result.metric("hhi_concentration").result.value)
        self.assertIsNone(result.metric("modeled_volatility").result.value)
        self.assertIsNone(result.metric("average_correlation").result.value)
        self.assertEqual(result.metric("modeled_volatility").observation_count, 156)

    def test_classification_unknown_is_a_limited_partition_not_a_guessed_country(self):
        result, _, _, _ = compute_case(metadata=None)
        for dimension in ("country", "sector"):
            m = result.metric(dimension + "_exposure", ("UNKNOWN",))
            self.assertEqual(m.exact, 1)
            self.assertEqual(m.state.value, "LIMITED")
            self.assertIn("UNKNOWN_CLASSIFICATION", m.details)
        self.assertEqual(result.metric("currency_exposure", ("USD",)).state.value, "AVAILABLE")
        self.assertEqual(result.metric("asset_class_exposure", ("EQUITY",)).exact, 1)

    def test_future_metadata_is_rejected_before_numbers(self):
        r = g.shared_runner(1)
        meta = replace(configuration(r)["metadata"], as_of=D(2026, 1, 3))
        with self.assertRaisesRegex(ValueError, "look ahead"):
            compute_case(metadata=meta)

    def test_missing_or_price_only_action_coverage_suppresses_history_only(self):
        for coverage in ((), tuple(replace(c, return_basis="PRICE_RETURN") for c in configuration(g.shared_runner(1))["coverage"])):
            result, _, _, _ = compute_case(coverage=coverage)
            self.assertIsNone(result.metric("modeled_volatility").result.value)
            self.assertIsNotNone(result.metric("hhi_concentration").result.value)
            wanted = "NOT_TOTAL_RETURN" if coverage else "TOTAL_RETURN_COVERAGE_UNCONFIRMED"
            self.assertIn(wanted, result.metric("modeled_volatility").details)

    def test_reproduction_and_every_auditable_input_are_checked(self):
        result, r, p, kw = compute_case()
        args = (result, result.result_digest, r.events[p["name"]], r.market.store, r.market.ident, r.market.conventions, r.perf)
        reproduce_kw = {k: kw[k] for k in ("suppressions", "metadata", "coverage")}
        self.assertEqual(reproduce_diversification(*args, **reproduce_kw).status, "REPRODUCED")
        self.assertEqual(reproduce_diversification(result, None, *args[2:], **reproduce_kw).status, "RESULT_NOT_COMPARED")
        self.assertEqual(reproduce_diversification(result, "0" * 64, *args[2:], **reproduce_kw).status, "RESULT_DIFFERS")
        changed = dict(reproduce_kw, metadata=replace(kw["metadata"], source="changed provenance"))
        report = reproduce_diversification(*args, **changed)
        self.assertEqual(report.status, "INPUT_MISMATCH")
        self.assertIn("metadata", report.detail)
        old = json.loads(result.manifest_json)
        old["history_files"].pop()
        report = reproduce_diversification(json.dumps(old), result.result_digest, *args[2:], **reproduce_kw)
        self.assertEqual(report.status, "INPUT_MISMATCH")
        self.assertIn("history_files", report.detail)

    def test_order_hash_seed_and_decimal_context_do_not_change_results(self):
        result, r, p, kw = compute_case()
        with localcontext() as context:
            context.prec = 6
            other, _, _, _ = compute_case(coverage=tuple(reversed(kw["coverage"])), metadata=replace(kw["metadata"], rows=tuple(reversed(kw["metadata"].rows))))
        self.assertEqual(result.canonical_json(), other.canonical_json())
        code = "from tests.product.test_diversification_integration import compute_case; r=compute_case()[0]; print(r.manifest_id, r.result_digest)"
        for seed in ("1", "4242"):
            out = subprocess.run([sys.executable, "-c", code], env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True, timeout=30)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout.strip(), result.manifest_id + " " + result.result_digest)

    def test_current_mode_reads_only_m_t_and_reproduces(self):
        r = g.shared_runner(3)
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("R7 ")]
        events = r.events[p["name"]]
        pin = max(e.ledger_seq for e in events)
        instant = g._utc("2026-01-09T09:00:00Z")
        kw = dict(configuration(r, r.ids(p["portfolio_id"])), suppressions=(), request=WindowSpec(WindowRule.TRAILING_MONTHS, 12), portfolio_id=r.ids(p["portfolio_id"]))
        result = compute_diversification_current(events, pin, instant, CurrencyCode(p["reporting_currency"]), r.market.market_at, r.market.ident, r.perf, **kw)
        manifest = json.loads(result.manifest_json)
        self.assertEqual(manifest["as_of"], "2026-01-09")
        self.assertTrue(manifest["valuation_manifest"]["excluded_files"])
        report = reproduce_diversification(result, result.result_digest, events, r.market.store, r.market.ident, r.market.conventions, r.perf,
                                           suppressions=(), metadata=kw["metadata"], coverage=kw["coverage"], market_at=r.market.market_at)
        self.assertEqual(report.status, "REPRODUCED", report.detail)

    def test_quant_policy_cases_p1_p2_refuse_without_an_actual_owner_choice(self):
        from test_diversification_golden import CASES
        for case_id, over in (("C5-P1", {"capital_policy": None}),
                              ("C5-P2", {"metadata": replace(configuration(g.shared_runner(1))["metadata"], synthetic=False)})):
            result, _, _, _ = compute_case(**over)
            wanted = CASES[case_id]["expected"]["capital_dependent_metrics"]
            for m in result.metrics:
                if m.metric_id not in ("pairwise_correlation", "correlation_cluster_count"):
                    self.assertEqual(m.state.value, wanted["state"])
                    self.assertIn(wanted["detail"], m.details)
                    self.assertIsNone(m.result.value)
                    self.assertEqual(m.lineage, ())
            self.assertFalse(json.loads(result.manifest_json)["capital_policy_confirmed"])

    def test_owner_policy_refusal_leaves_the_independent_two_security_pairs_and_clusters_unchanged(self):
        import uuid
        from domain.replay import SequencedEvent
        r = g.shared_runner(1)
        portfolios = [p for p in r.data["portfolios"] if p["name"].startswith(("P1 ", "P3 "))]
        events = [e.event for p in portfolios for e in r.events[p["name"]]]
        events = tuple(SequencedEvent(i + 1, e) for i, e in enumerate(events))
        pid = uuid.UUID("dd550000-0000-4000-8000-000000000001")
        kw = dict(configuration(r, pid), suppressions=(), request=WindowSpec(WindowRule.TRAILING_MONTHS, 12), portfolio_id=pid)
        args = (events, len(events), D(2025, 12, 31), CurrencyCode("USD"), r.market.store, r.market.ident, r.market.conventions, r.perf)
        candidate = compute_diversification(*args, **kw)
        unconfirmed = compute_diversification(*args, **dict(kw, capital_policy=None))
        independent = {"pairwise_correlation", "correlation_cluster_count"}
        for a, b in zip(candidate.metrics, unconfirmed.metrics):
            if a.metric_id in independent:
                self.assertIsNotNone(a.result.value)
                self.assertEqual((a.result, a.exact_square, a.sign), (b.result, b.exact_square, b.sign))
        self.assertEqual(candidate.clusters, unconfirmed.clusters)

    def test_quant_fx1_is_computed_from_native_prices_and_actual_fx_port(self):
        from test_diversification_golden import CASES
        h, files = compute_fx_case()
        expected = CASES["C5-FX1"]["expected"]
        self.assertEqual(h.observations[0].value, F(expected["reporting_return"]), h.observations[0])
        native, fx_return = F("1/10"), F("-1/5")
        self.assertEqual(h.observations[0].value - native - fx_return, F(expected["cross_term"]))
        self.assertLess(h.observations[0].value, 0)
        self.assertTrue(files)

    def test_unpaid_income_is_a_receivable_bucket_not_counted_again_as_cash(self):
        import uuid
        from decimal import Decimal
        from domain.currency import Money
        from domain.ledger import EventType, LedgerEvent
        from domain.replay import SequencedEvent
        base, r, p, kw = compute_case()
        events = r.events[p["name"]]
        pin = max(e.ledger_seq for e in events) + 1
        dividend = LedgerEvent(uuid.UUID("ee550000-0000-4000-8000-000000000001"), r.ids(p["accounts"][0]["account_id"]), EventType.DIVIDEND,
                               D(2026, 1, 9), CurrencyCode("USD"), listing_id=r.ids("c4000000-0000-4000-8000-000000000003"),
                               amount=Money(Decimal("100"), CurrencyCode("USD")), ex_date=D(2026, 1, 2), source_reference="CP5 synthetic accrued income")
        result = compute_diversification(tuple(events) + (SequencedEvent(pin, dividend),), pin, D(2026, 1, 2), CurrencyCode("USD"), r.market.store, r.market.ident, r.market.conventions, r.perf, **kw)
        buckets = json.loads(result.manifest_json)["buckets"]
        receivable = [b for b in buckets if b["kind"] == "RECEIVABLE"]
        self.assertEqual(len(receivable), 1)
        self.assertEqual(F(receivable[0]["value"]), 100)
        self.assertFalse([b for b in buckets if b["kind"] == "CASH" and F(b["value"]) != 0])
        self.assertGreater(result.metric("country_exposure", ("RECEIVABLE",)).exact, 0)
        self.assertEqual(result.metric("risk_contribution_share", ("RECEIVABLE:USD",)).exact, 0)


if __name__ == "__main__":
    unittest.main()
