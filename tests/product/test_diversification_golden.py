"""CP5 independent Quant fixtures, exact rational witnesses and safe refusals."""
import copy
import datetime as dt
import json
import sys
import unittest
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from diversification import core, registry
from diversification.contracts import AVAILABLE, INSUFFICIENT, Bucket, Classification, History, MetadataSnapshot, Observation
from performance.numerics import round_half_up, to_decimal_exact
from risk.sqrt import sqrt_rounded

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / "methodology/fixtures/cp5_golden/cp5_golden_part1.json").read_text())
CASES = {c["id"]: c for c in FIXTURE["cases"]}
SNAPSHOT_CASE_IDS = frozenset(f"C5-S{i}" for i in range(1, 7))
HISTORY_CASE_IDS = frozenset(f"C5-H{i}" for i in range(1, 17))
DRIFT_CASE_IDS = frozenset(f"C5-D{i}" for i in range(1, 10))
POLICY_CASE_IDS = frozenset(("C5-P1", "C5-P2"))
FX_CASE_IDS = frozenset(("C5-FX1",))


def inputs(case):
    row = copy.deepcopy(case["input"])
    if "base_case" in row:
        base = inputs(CASES[row.pop("base_case")])
        base.update(row)
        row = base
    return row


def snapshot(case):
    spec = inputs(case)
    grouped, classifications, types = {}, {}, {}
    overrides = {o["key"]: o for o in spec.get("overrides", [])}
    for row in spec["components"]:
        key = row["key"]
        value = F(row["value"]) if "value" in row else F(row["native_value"]) * F(row["fx"])
        state, reason = AVAILABLE, None
        if key in overrides:
            value, state, reason = None, INSUFFICIENT, overrides[key]["reason"]
        old = grouped.get(key)
        value = value if old is None else None if old.value is None or value is None else old.value + value
        grouped[key] = Bucket(key, key.split(":")[0], row.get("native_currency", "USD"), value, state, reason)
        if key.startswith("SECURITY:"):
            listing = key.split(":")[1]
            classifications[listing] = Classification(listing, row.get("country"), row.get("sector"))
            types[listing] = "ETF" if row.get("asset_class") == "ETF" else "COMMON_STOCK"
    buckets = tuple(grouped[k] for k in sorted(grouped))
    total = None if any(b.value is None for b in buckets) else sum((b.value for b in buckets), F())
    metadata = MetadataSnapshot("synthetic/1", "quant fixture", "synthetic/1", dt.date(2025, 12, 26), tuple(classifications.values()))
    metrics, weights = core.capital(buckets, total, INSUFFICIENT if total is None else AVAILABLE, "MISSING_FX_HISTORY" if total is None else None, (), metadata, types)
    return metrics, weights


def history(case):
    spec = inputs(case)
    vectors = {}
    def expand(key):
        if key in vectors:
            return vectors[key]
        row = spec["vectors"][key]
        if "multiple_of" in row:
            values = [v * F(row["multiplier"]) for v in expand(row["multiple_of"])]
        elif "linear_combination" in row:
            terms = [(F(c), expand(k)) for k, c in row["linear_combination"].items()]
            values = [sum((c * vector[i] for c, vector in terms), F()) for i in range(spec["n"])]
        elif "constant" in row:
            values = [F(row["constant"])] * spec["n"]
        else:
            values = [F(v) for v in row["pattern"]] * row["repeat"] + [F(v) for v in row.get("tail", [])]
        vectors[key] = values[:spec["n"]]
        return vectors[key]
    for key in spec["vectors"]:
        expand(key)
    if "constant_security" in spec:
        vectors[spec["constant_security"]] = [F()] * spec["n"]
    dates = tuple(dt.date.fromisoformat(spec["grid_start"]) + dt.timedelta(days=7 * i) for i in range(spec["n"] + 1))
    histories = []
    for key, values in sorted(vectors.items()):
        rows = tuple(Observation(a, b, v) for a, b, v in zip(dates, dates[1:], values))
        missing = spec.get("missing_period", {})
        if missing.get("key") == key:
            rows = tuple(replace(o, value=None, state=INSUFFICIENT, details=("PERIOD_INSUFFICIENT",)) if i == missing["index"] else o for i, o in enumerate(rows))
        coverage = spec["total_return_coverage"]
        if coverage != "COMPLETE_SYNTHETIC":
            detail = "NOT_TOTAL_RETURN" if coverage == "PRICE_ONLY" else "TOTAL_RETURN_COVERAGE_UNCONFIRMED"
            rows = tuple(replace(o, value=None, state=INSUFFICIENT, details=(detail,)) for o in rows)
        histories.append(History(key, rows))
    weights = {k: F(v) for k, v in spec["weights"].items()}
    buckets = tuple(Bucket(k, k.split(":")[0], "USD", v) for k, v in weights.items())
    tau = None if spec["tau"] is None else F(spec["tau"])
    return core.statistics(buckets, weights, histories, dates, registry.thresholds(spec["frequency"]), registry.annualization(spec["frequency"]), tau)


class GoldenTests(unittest.TestCase):
    def assert_expected(self, m, expected):
        if "state" in expected:
            self.assertEqual(m.state.value, expected["state"])
        if "reason" in expected:
            self.assertEqual(None if m.result.reason_code is None else m.result.reason_code.value, expected["reason"])
        if "exact" in expected:
            wanted = expected["exact"]
            if wanted is None:
                self.assertIsNone(m.result.value)
                self.assertIsNone(m.exact)
                self.assertIsNone(m.exact_square)
                self.assertFalse(m.radical_terms)
            elif m.exact is not None:
                self.assertEqual(m.exact, F(wanted))
            else:
                self.assertEqual(F(m.result.value), round_half_up(F(wanted), 12))
        if expected.get("detail"):
            self.assertIn(expected["detail"], m.details)

    def test_registry_is_the_quants_byte_identical_17_entry_registry(self):
        # diversification/1.2 (label re-issue of 1.0 for market-data/1.16, section 11 item 35): the 1.0 and 1.1 files stay as records and are no longer the engine's
        self.assertEqual(registry.REGISTRY_BYTES, (ROOT / "methodology/registry/DIVERSIFICATION_1.2_REGISTRY.json").read_bytes())
        self.assertNotEqual(registry.REGISTRY_BYTES, (ROOT / "methodology/registry/DIVERSIFICATION_1.0_REGISTRY.json").read_bytes())
        self.assertNotEqual(registry.REGISTRY_BYTES, (ROOT / "methodology/registry/DIVERSIFICATION_1.1_REGISTRY.json").read_bytes())
        self.assertEqual(registry.REGISTRY_ID, "diversification/1.2")
        self.assertEqual(len(registry.METRIC_IDS), 17)

    def test_a_result_cites_the_registry_it_was_computed_under(self):
        # `method_key` is `<registry_id>#<metric_id>`; drift refuses any other form, so a prefix that lags the registry would refuse every CP5 result
        from diversification.contracts import METHOD_KEY_PREFIX, metric  # noqa: PLC0415

        self.assertEqual(METHOD_KEY_PREFIX, registry.REGISTRY_ID + "#")
        row = metric("hhi_concentration", exact=F(1, 2)).to_obj()
        self.assertEqual(row["method_key"], registry.REGISTRY_ID + "#hhi_concentration")

    def test_every_case_has_an_explicit_checker_and_no_case_is_silently_skipped(self):
        self.assertEqual(len(CASES), len(FIXTURE["cases"]))
        self.assertEqual(set(CASES), SNAPSHOT_CASE_IDS | HISTORY_CASE_IDS | DRIFT_CASE_IDS | POLICY_CASE_IDS | FX_CASE_IDS)
        self.assertEqual(FIXTURE["fixture_id"], "cp5_golden/1.1-part1")
        self.assertEqual(len(FIXTURE["threshold_boundary_assertions"]), 12)

    def test_six_snapshot_cases(self):
        for case_id in sorted(SNAPSHOT_CASE_IDS):
            with self.subTest(case=case_id):
                case = CASES[case_id]
                metrics, weights = snapshot(case)
                expect = case["expected"]
                if "same_metrics_as" in expect:
                    self.assertEqual((metrics, weights), snapshot(CASES[expect["same_metrics_as"]]))
                elif "all_concentration_and_exposure" in expect:
                    self.assertIsNone(weights)
                    for m in metrics:
                        self.assert_expected(m, expect["all_concentration_and_exposure"])
                else:
                    self.assertEqual(weights, {k: F(v) for k, v in expect["weights"].items()})
                    for m in metrics:
                        if m.metric_id in expect["metrics"]:
                            self.assert_expected(m, expect["metrics"][m.metric_id])
                    for dimension, e in expect.get("exposures", {}).items():
                        actual = {m.subject[0]: m for m in metrics if m.metric_id == dimension + "_exposure"}
                        self.assertEqual(set(actual), set(e["categories"]))
                        for category, value in e["categories"].items():
                            self.assert_expected(actual[category], dict(e, exact=value))

    def test_all_sixteen_historical_cases(self):
        allowed = {"state", "detail", "pairwise", "average_correlation", "security_coverage", "cluster_count", "clusters", "periodic_variance", "annual_variance", "modeled_volatility",
                   "risk_shares", "statistical_metrics", "unaffected_pair", "correlation_cluster_count", "risk_contribution_share", "risk_contribution_component", "pair_A_B", "pair_A_C", "pair_B_C",
                   "modeled_periodic_variance", "other_metrics_same_as", "average_correlation_presented", "rounded_pairs_mutant"}
        for case_id in sorted(HISTORY_CASE_IDS):
            with self.subTest(case=case_id):
                case = CASES[case_id]
                metrics, clusters = history(case)
                by = {(m.metric_id, m.subject): m for m in metrics}
                expect = case["expected"]
                self.assertFalse(set(expect) - allowed, "unchecked expected fields")
                for m in metrics:
                    if m.state is not INSUFFICIENT and "state" in expect:
                        self.assert_expected(m, {"state": expect["state"], "detail": expect.get("detail")})
                for key, value in expect.get("pairwise", {}).items():
                    m = by["pairwise_correlation", tuple(key.split("|"))]
                    if isinstance(value, dict):
                        self.assertEqual((m.sign, m.exact_square), (value["sign"], F(value["squared"])))
                    else:
                        self.assert_expected(m, {"exact": value, "state": expect["state"]})
                if "clusters" in expect:
                    self.assertEqual(clusters, tuple(tuple(c) for c in expect["clusters"]))
                    self.assert_expected(by["correlation_cluster_count", ()], {"exact": expect.get("cluster_count", str(len(expect["clusters"])))})
                if "risk_shares" in expect:
                    for key, value in expect["risk_shares"].items():
                        self.assert_expected(by["risk_contribution_share", (key,)], {"exact": value})
                    self.assertEqual(sum((m.exact for m in metrics if m.metric_id == "risk_contribution_share"), F()), 1)
                if "annual_variance" in expect:
                    self.assertEqual(by["modeled_volatility", ()].exact_square, F(expect["annual_variance"]))
                for key in ("periodic_variance", "modeled_periodic_variance"):
                    if key in expect:
                        self.assertEqual(F(dict(by["modeled_volatility", ()].lineage)["periodic_variance"]), F(expect[key]))
                if "security_coverage" in expect:
                    self.assertEqual(F(dict(by["average_correlation", ()].lineage)["security_capital_coverage"]), F(expect["security_coverage"]))
                for key in ("average_correlation", "correlation_cluster_count", "modeled_volatility", "risk_contribution_share", "risk_contribution_component"):
                    e = expect.get(key)
                    if isinstance(e, str):
                        self.assert_expected(by[key, ()], {"exact": e})
                    elif isinstance(e, dict) and "coefficient" in e:
                        value = sqrt_rounded(F(e["coefficient"]) ** 2 * F(e["radicand"])).value
                        self.assertEqual(F(by[key, ()].result.value), value)
                    elif isinstance(e, dict) and "signed_sqrt" in e:
                        self.assertEqual((by[key, ()].exact_square, by[key, ()].sign), (F(e["signed_sqrt"]), e["sign"]))
                    elif isinstance(e, dict):
                        for m in metrics:
                            if m.metric_id == key:
                                self.assert_expected(m, e)
                if "statistical_metrics" in expect:
                    for m in metrics:
                        self.assert_expected(m, expect["statistical_metrics"])
                for pair, e in expect.get("unaffected_pair", {}).items():
                    self.assert_expected(by["pairwise_correlation", tuple(pair.split("|"))], e)
                for short, pair in (("pair_A_B", ("SECURITY:A", "SECURITY:B")), ("pair_A_C", ("SECURITY:A", "SECURITY:C")), ("pair_B_C", ("SECURITY:B", "SECURITY:C"))):
                    if short in expect:
                        self.assert_expected(by["pairwise_correlation", pair], expect[short])
                if "other_metrics_same_as" in expect:
                    reference, _ = history(CASES[expect["other_metrics_same_as"]])
                    self.assertEqual([m for m in metrics if m.metric_id != "correlation_cluster_count"], [m for m in reference if m.metric_id != "correlation_cluster_count"])
                if "average_correlation_presented" in expect:
                    self.assertEqual(str(by["average_correlation", ()].result.value), expect["average_correlation_presented"])
                    self.assertNotEqual(str(by["average_correlation", ()].result.value), expect["rounded_pairs_mutant"]["weighted_average_presented"])

    def test_h16_kills_averaging_the_already_rounded_pair_correlations(self):
        expected = CASES["C5-H16"]["expected"]
        def premature_rounding(terms):
            value = sum((coefficient * sqrt_rounded(square).value for coefficient, square in terms), F())
            return to_decimal_exact(round_half_up(value, 12))
        with patch.object(core, "radical_sum", premature_rounding):
            metrics, _ = history(CASES["C5-H16"])
        mutant = next(m for m in metrics if m.metric_id == "average_correlation")
        self.assertEqual(F(mutant.result.value), F(expected["rounded_pairs_mutant"]["weighted_average_presented"]))
        self.assertNotEqual(F(mutant.result.value), F(expected["average_correlation_presented"]))

    def test_all_twelve_count_boundaries(self):
        for boundary in FIXTURE["threshold_boundary_assertions"]:
            case = copy.deepcopy(CASES["C5-H1"])
            n = boundary["n"]
            case["input"].update(n=n, frequency=boundary["frequency"])
            case["input"]["vectors"]["SECURITY:A"].update(repeat=n // 2, tail=["0"] if n % 2 else [])
            metrics, _ = history(case)
            for m in metrics:
                self.assertEqual(m.state.value, boundary["state"], (boundary, m.metric_id))


if __name__ == "__main__":
    unittest.main()
