"""Independent §47 counterexamples, recorded red before CP5 repairs."""
import datetime as dt
import json
import unittest
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction as F

from tests.product.test_diversification_integration import compute_case
from diversification import core
from diversification.contracts import AVAILABLE, LIMITED, INSUFFICIENT, PRODUCT_ID, Bucket, CapitalUniverseChoice, Classification, History, MetadataSnapshot, Observation, seal
from diversification.engine import compute_diversification, reproduce_diversification
from domain.currency import CurrencyCode


def histories(vectors):
    n = len(next(iter(vectors.values())))
    dates = tuple(dt.date(2023, 1, 6) + dt.timedelta(days=7 * i) for i in range(n + 1))
    return dates, [History(key, tuple(Observation(a, b, value) for a, b, value in zip(dates, dates[1:], values))) for key, values in vectors.items()]


class ReviewCounterexampleTests(unittest.TestCase):
    def test_i1_unscoped_owner_evidence_does_not_apply_to_this_portfolio(self):
        policy = CapitalUniverseChoice("FULL_NAV", "USER_CONFIRMED", "Owner approval applies only to DIFFERENT-PORTFOLIO")
        result, _, _, _ = compute_case(capital_policy=policy)
        self.assertIn("CAPITAL_UNIVERSE_UNCONFIRMED", result.metric("hhi_concentration").details)
        self.assertFalse(json.loads(result.manifest_json)["capital_policy_confirmed"])

    def test_i2_recent_acquisition_does_not_erase_existing_security_history(self):
        original, r, p, kw = compute_case()
        events = tuple(replace(e, event=replace(e.event, event_date=dt.date(2025, 12, 1))) for e in r.events[p["name"]])
        result = compute_diversification(events, max(e.ledger_seq for e in events), dt.date(2026, 1, 2), CurrencyCode("USD"),
                                         r.market.store, r.market.ident, r.market.conventions, r.perf, **kw)
        self.assertEqual(result.metric("modeled_volatility").exact_square, F(7803, 96875))
        self.assertEqual(result.metric("modeled_volatility").observation_count, 156)
        self.assertEqual(result.metric("modeled_volatility").state, original.metric("modeled_volatility").state)

    def test_i3_thirds_have_separate_apportioned_display_and_unchanged_exact_scalars(self):
        buckets = tuple(Bucket("SECURITY:" + key, "SECURITY", "USD", F(1)) for key in "ABC")
        meta = MetadataSnapshot("1", "explicit synthetic fixture", "1", dt.date(2023, 1, 1), tuple(Classification(k, k, "TECH") for k in "ABC"))
        metrics, _ = core.capital(buckets, F(3), AVAILABLE, None, (), meta, {k: "COMMON_STOCK" for k in "ABC"})
        result = seal({"complete_exposure_maps": list(core.EXPOSURE_IDS)}, metrics)
        partition = next(p for p in result.exposure_decompositions if p.metric_id == "country_exposure")
        self.assertEqual([p.exact for p in partition.parts], [F(1, 3)] * 3)
        self.assertEqual([p.scalar for p in partition.parts], [Decimal("0.333333333333")] * 3)
        self.assertEqual([p.apportioned for p in partition.parts], [Decimal("0.333333333334"), Decimal("0.333333333333"), Decimal("0.333333333333")])
        self.assertEqual(sum((p.apportioned for p in partition.parts), Decimal()), partition.displayed_total)

    def test_i4_cancelling_radicals_at_exact_positive_half_quantum_retain_value(self):
        a = [F(1, 10), F(-1, 10), F(1, 10), F(-1, 10)] * 13
        z = [F(1, 10), F(1, 10), F(-1, 10), F(-1, 10)] * 13
        c = [(3 * x + 4 * y) / 5 for x, y in zip(a, z)]
        b = [x - y for x, y in zip(a, c)]
        weights = {"SECURITY:A": F(2, 1200000000003), "SECURITY:B": F(1199999999999, 1200000000003), "SECURITY:C": F(2, 1200000000003)}
        dates, rows = histories(dict(zip(weights, (a, b, c))))
        buckets = tuple(Bucket(k, "SECURITY", "USD", w) for k, w in weights.items())
        metrics, _ = core.statistics(buckets, weights, rows, dates, (51, 155), 52, F(3, 5))
        m = next(m for m in metrics if m.metric_id == "average_correlation")
        self.assertEqual(m.state, LIMITED)
        self.assertEqual(m.result.value, Decimal("0.000000000001"))
        self.assertIn("PRESENTATION_TIE", str(m.lineage))

    def test_i5_cluster_missing_price_reason_wins_over_available_stale_pair(self):
        a = [F(-1, 10), F(1, 10)] * 77 + [F()]
        dates, rows = histories({"SECURITY:A": a, "SECURITY:B": [2 * x for x in a], "SECURITY:C": [-x for x in a]})
        rows[0] = replace(rows[0], observations=tuple(replace(o, reason="STALE_DATA") for o in rows[0].observations))
        rows[2] = replace(rows[2], observations=tuple(replace(o, value=None, state=INSUFFICIENT, reason="MISSING_PRICE_HISTORY") if i == 7 else o for i, o in enumerate(rows[2].observations)))
        weights = {h.key: F(1, 3) for h in rows}
        buckets = tuple(Bucket(k, "SECURITY", "USD", w) for k, w in weights.items())
        metrics, _ = core.statistics(buckets, weights, rows, dates, (51, 155), 52, F(3, 5))
        m = next(m for m in metrics if m.metric_id == "correlation_cluster_count")
        self.assertEqual(m.state, INSUFFICIENT)
        self.assertEqual(m.result.reason_code.value, "MISSING_PRICE_HISTORY")
        renamed = {"SECURITY:A": "SECURITY:Z", "SECURITY:B": "SECURITY:Y", "SECURITY:C": "SECURITY:X"}
        alternate, _ = core.statistics(tuple(replace(b, key=renamed[b.key]) for b in reversed(buckets)),
                                        {renamed[k]: v for k, v in weights.items()}, tuple(replace(h, key=renamed[h.key]) for h in reversed(rows)),
                                        dates, (51, 155), 52, F(3, 5))
        self.assertEqual(next(m for m in alternate if m.metric_id == "correlation_cluster_count").result.reason_code.value, "MISSING_PRICE_HISTORY")

    def test_i6_missing_and_added_null_manifest_keys_are_input_mismatches(self):
        result, r, p, kw = compute_case()
        old = json.loads(result.manifest_json)
        del old["instant"]
        old["unexpected_null_field"] = None
        report = reproduce_diversification(json.dumps(old), result.result_digest, r.events[p["name"]], r.market.store, r.market.ident, r.market.conventions, r.perf,
                                           **{k: kw[k] for k in ("suppressions", "metadata", "coverage")})
        self.assertEqual(report.status, "INPUT_MISMATCH")
        self.assertIn("instant", report.detail)
        self.assertIn("unexpected_null_field", report.detail)

    def test_i1_every_owner_scope_is_explicit_and_matches_the_actual_request(self):
        _, r, p, kw = compute_case()
        pid = str(r.ids(p["portfolio_id"]))
        account = r.ids(p["accounts"][0]["account_id"])
        portfolio_policy = CapitalUniverseChoice("FULL_NAV", "USER_CONFIRMED", "synthetic owner-scope test evidence", "synthetic-decision/1", "PORTFOLIO", portfolio_id=pid)
        account_policy = replace(portfolio_policy, scope_kind="ACCOUNT", account_id=str(account))
        global_policy = replace(portfolio_policy, scope_kind="GLOBAL_PRODUCT", product_id=PRODUCT_ID, portfolio_id=None)
        for policy, scope in ((portfolio_policy, None), (account_policy, account), (global_policy, None), (global_policy, account)):
            with self.subTest(policy=policy.scope_kind, scope=scope):
                result, _, _, _ = compute_case(capital_policy=policy, account_scope=scope)
                self.assertTrue(json.loads(result.manifest_json)["capital_policy_confirmed"])
                self.assertIsNotNone(result.metric("hhi_concentration").result.value)
        invalid = ((portfolio_policy, account), (account_policy, None), (replace(portfolio_policy, portfolio_id="other"), None),
                   (replace(account_policy, account_id="other"), account), (replace(global_policy, product_id="other"), None),
                   (replace(global_policy, product_id=None), None), (replace(portfolio_policy, decision_id=None), None),
                   (replace(portfolio_policy, scope_kind=None), None), (replace(portfolio_policy, evidence=""), None))
        for policy, scope in invalid:
            with self.subTest(policy=policy.to_obj(), scope=scope):
                result, _, _, _ = compute_case(capital_policy=policy, account_scope=scope)
                self.assertIn("CAPITAL_UNIVERSE_UNCONFIRMED", result.metric("hhi_concentration").details)

    def test_i2_custom_window_predates_acquisition_but_inception_requests_keep_their_floor(self):
        from performance.periods import WindowSpec, WindowRule
        from performance.series import MaxAvailable
        _, r, p, kw = compute_case()
        events = tuple(replace(e, event=replace(e.event, event_date=dt.date(2025, 12, 1))) for e in r.events[p["name"]])
        args = (events, max(e.ledger_seq for e in events), dt.date(2026, 1, 2), CurrencyCode("USD"), r.market.store, r.market.ident, r.market.conventions, r.perf)
        custom = compute_diversification(*args, **dict(kw, request=WindowSpec(WindowRule.CUSTOM, custom_base=dt.date(2023, 1, 2))))
        self.assertEqual(custom.metric("modeled_volatility").exact_square, F(7803, 96875))
        self.assertEqual(json.loads(custom.manifest_json)["history_floor"]["rule"], "NONE_FIXED_REQUEST")
        for request in (WindowSpec(WindowRule.SINCE_INCEPTION), MaxAvailable()):
            result = compute_diversification(*args, **dict(kw, request=request))
            self.assertEqual(json.loads(result.manifest_json)["history_floor"]["date"], "2025-11-30")
            self.assertLess(result.metric("modeled_volatility").observation_count, 51)
            self.assertIsNone(result.metric("modeled_volatility").result.value)
        shortened, _, _, _ = compute_case(prefix="P11 ", request=MaxAvailable())
        floor = json.loads(shortened.manifest_json)["history_floor"]
        self.assertEqual(floor["rule"], "PORTFOLIO_INCEPTION")
        self.assertIsNotNone(floor["suffix_after"])
        self.assertIn("MISSING_PRICE_HISTORY", floor["suffix_cause"])

    def test_i3_apportioned_partition_is_in_result_digest_and_missing_values_have_none(self):
        result, _, _, _ = compute_case()
        partition = result.exposure_decompositions[0]
        changed_part = replace(partition.parts[0], apportioned=Decimal("0.9"))
        changed = replace(result, exposure_decompositions=(replace(partition, parts=(changed_part,) + partition.parts[1:]),) + result.exposure_decompositions[1:])
        self.assertNotEqual(result.result_digest, changed.result_digest)
        self.assertEqual(result.manifest_id, changed.manifest_id)
        denied, _, _, _ = compute_case(capital_policy=None)
        self.assertEqual(denied.exposure_decompositions, ())

    def test_i4_equivalent_radicals_cancel_before_positive_and_negative_tie_rounding(self):
        from diversification.numerics import radical_sum, PresentationTie
        for sign in (-1, 1):
            tie = F(sign, 2 * 10**12)
            with self.assertRaises(PresentationTie) as found:
                radical_sum(((F(2), F(1, 2)), (F(-1), F(2)), (tie, F(1))))
            result = found.exception
            self.assertEqual(result.value, Decimal(sign) * Decimal("0.000000000001"))
            self.assertEqual((result.exact, result.low, result.high), (tie, tie, tie))

    def test_i6_typed_null_integer_boolean_and_invalid_structure_tampering_are_rejected(self):
        result, r, p, kw = compute_case()
        genuine = json.loads(result.manifest_json)
        mutations = []
        changed = dict(genuine, synthetic=1)
        mutations.append(changed)
        changed = dict(genuine, cluster_threshold=0.6)
        mutations.append(changed)
        changed = dict(genuine)
        del changed["request"]
        mutations.extend((changed, [], None))
        for old in mutations:
            with self.subTest(manifest=type(old).__name__):
                report = reproduce_diversification(json.dumps(old), result.result_digest, r.events[p["name"]], r.market.store, r.market.ident, r.market.conventions, r.perf,
                                                   **{k: kw[k] for k in ("suppressions", "metadata", "coverage")})
                self.assertEqual(report.status, "INPUT_MISMATCH", report)
