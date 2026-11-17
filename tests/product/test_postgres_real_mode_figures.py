"""F1 R7 / PD-0079, PostgreSQL: the shape of the issued result that a TEST create STORES and the real-mode API returns, pinned (the key-figures finding).

The key-figures list (`web/src/real-mode.ts`, `keyFigures`) was written against the performance engine's `ComputedMetric` dictionary
(`metrics[].metric_id` + `view`, `portfolio_value`/`REPORTING` as the NAV). The result a TEST (fictional-scope) create stores is NOT that document: the
fictional branch issues the CP5 DIVERSIFICATION result (`service._stage_fictional`, selector `CP5_DIVERSIFICATION`). These tests pin what it really holds, so
that a change in the stored document's shape fails here, and so that the vitest fixture recorded from it (`web/src/real-mode-stored-result.json`, when one is
made) can be compared with it. They record a FACT about the stored result; they decide nothing about the list.
"""
from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import test_postgres_real_mode as m  # noqa: E402
from real_gateway_kit import setUpModule, tearDownModule  # noqa: E402,F401

TOP_KEYS = ["clusters", "exposure_decompositions", "manifest", "manifest_id", "metrics", "result_digest"]
METRIC_KEYS = ["details", "exact", "exact_square", "lineage", "manifest_id", "method_key", "metric_id", "observation_count", "radical_terms", "reason", "sign",
               "state", "subject", "thresholds", "value"]
BUCKET_KEYS = ["currency", "details", "key", "kind", "reason", "state", "value"]


class StoredResultShapeTests(m.R7Case):
    def created(self):
        client = self.client()
        client.sign_up("shape_" + uuid.uuid4().hex[:10])
        status, body, _ = client.post("/api/real/v1/roots", self.intent(self.live))
        self.assertEqual(status, 201, body)
        return client, body

    def test_a_test_create_stores_the_diversification_result_and_it_holds_no_nav_metric(self):
        _client, body = self.created()
        result = body["result"]
        self.assertEqual(sorted(result), TOP_KEYS)
        self.assertEqual(result["manifest"]["registry_id"], "diversification/1.2")
        self.assertEqual(result["manifest"]["engine_id"], "diversification/cp5-0.2")
        for metric in result["metrics"]:
            self.assertEqual(sorted(metric), METRIC_KEYS)
            self.assertTrue(metric["method_key"].startswith("diversification/1.2#"))
            self.assertNotIn("view", metric)                         # no `view`, no `currency`, no `unit`: the performance engine's fields are not here
            self.assertNotIn("currency", metric)
            self.assertIsInstance(metric["subject"], list)
            self.assertTrue(all(isinstance(part, str) for part in metric["subject"]))      # strings, not [key, value] pairs
        ids = {metric["metric_id"] for metric in result["metrics"]}
        self.assertTrue({"top5_concentration", "hhi_concentration", "effective_positions", "currency_exposure"} <= ids)
        self.assertFalse(ids & {"portfolio_value", "holding_value", "cash_value", "receivable_value", "portfolio_value_priced_holdings"})
        self.assertNotIn('"portfolio_value"', json.dumps(result))     # NAV is not in the stored result, in the performance engine's form or any other

    def test_the_only_money_figures_are_the_buckets_of_the_manifest_and_they_are_components_not_a_total(self):
        _client, body = self.created()
        buckets = body["result"]["manifest"]["buckets"]
        self.assertTrue(buckets)
        for bucket in buckets:
            self.assertEqual(sorted(bucket), BUCKET_KEYS)
            self.assertIn("/", bucket["value"])                      # an exact rational "n/d", per CASH:<ccy> and SECURITY:<id>; their sum would be a NAV
        self.assertEqual({bucket["kind"] for bucket in buckets}, {"CASH", "SECURITY"})
        self.assertEqual(sorted(body["result"]["manifest"]["valuation_manifest"])[:3], ["as_of", "as_of_causes", "as_of_rule"])   # the valuation's manifest, no metrics


FIXTURE = HERE.parents[1] / "web" / "src" / "real-mode-stored-result.fixture.json"


class RecordedFixtureTests(StoredResultShapeTests):
    """The vitest fixture (`web/src/real-mode-stored-result.fixture.json`) is a RECORD of the document a TEST create stores: its `metrics` (without the per-run
    `manifest_id`), the manifest's `buckets`, `clusters`, the top-level keys and the valuation manifest's keys. It was made from a create on a TEST install by a
    throwaway print of exactly those parts (invented data: the project's fictional world). This test fails when the live document's shape or values move, so the
    fixture cannot drift from what the product stores; the vitest tests read the same file."""

    def test_the_recorded_fixture_equals_the_live_stored_document(self):
        _client, body = self.created()
        result = body["result"]
        live = {"metrics": [{k: v for k, v in metric.items() if k != "manifest_id"} for metric in result["metrics"]], "buckets": result["manifest"]["buckets"],
                "top_keys": sorted(result), "clusters": result["clusters"], "valuation_manifest_keys": sorted(result["manifest"]["valuation_manifest"])}
        self.assertEqual(json.loads(FIXTURE.read_text("utf8")), live)


del StoredResultShapeTests      # the base class is reused above; run its tests once, through the subclass


if __name__ == "__main__":
    unittest.main()
