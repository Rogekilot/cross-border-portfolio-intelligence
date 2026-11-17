"""CP4b-1: nothing the CP3 engine computes changed (tech plan 17.0 item 5, 17.3). The series spine adds `performance/series.py`, `compute_return_series`, an additive `WindowUsed` field pair and an
`ENGINE_ID` bump. `ENGINE_ID` is part of every manifest, so manifest ids and result digests change with it BY DESIGN; this test shows that is the ONLY thing that changed:

1. The canonical results of the committed HG2 synthetic demonstration (17 computations: every metric, state, reason, exact value, cause, freshness, lineage and the whole manifest) are hashed with the
   `engine_id` and the manifest ids removed, and the hash equals the one recorded BEFORE the CP4b-1 change (`BASELINE_SHA256`, taken from the unchanged code at 40cef82 plus the uncommitted tree).
   If a later increment changes a CP3 result on purpose, it re-records the hash in the same commit, which review sees.
2. Every `exact` value of the committed gate record (`reviews/gates/HG2_EVIDENCE/synthetic/*.json`, 228 values) equals the regenerated pack's.
3. The key sets of the manifest, the canonical metric and an unclipped window are the CP3 ones (additive-when-present is kept).
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from marketdata.canonical import canonical_json  # noqa: E402
from performance_tools import pack, synthetic  # noqa: E402

BASELINE_COMPUTATIONS = 17
# Re-recorded 2026-10-02 (CP4c round 2, market-data/1.12): the convention-set id `market-data/1.11` -> `1.12` is in every manifest and in the release id (a hash of the release content, which holds it). Shown to be the ONLY
# change: the canonical text of the 17 computations before and after, with `market-data/1.11` read as `1.12` and every 64-hex id masked, is byte-identical (570394 characters each).
# Re-recorded again 2026-10-03 (CP4c round 3, market-data/1.13): the same and only change, `market-data/1.12` -> `1.13` and the release ids derived from it (the canonical text before and after, with 1.12 read as 1.13
# and every 64-hex id masked, is byte-identical, 570394 characters each).
# Re-recorded again 2026-10-03 (CP4 conformance round, market-data/1.14, tech plan 17.25): the same and only change, `market-data/1.13` -> `1.14` and the release ids derived from it (the canonical text before and after, with
# 1.14 read as 1.13 and every 64-hex id masked, is byte-identical, 570394 characters each; sha256 4b161a71...).
# Re-recorded again 2026-10-23 (night run B2, market-data/1.15 Ruling 7A.3 / MD-OI-14): the `alphavantage.cn` profile is TO_OBSERVE, and `profile_open_items()` lists every TO_OBSERVE profile so that a result cannot hide it. So every one
# of the 17 manifests gained exactly ONE open-items line: "market_data: profile TO_OBSERVE: alphavantage.cn (pending observation, not admitted; ...)". Shown to be the ONLY change: with that one line removed from the
# 17 manifests the masked canonical hash is again 6f3088a1... (the previous baseline). No number, state, reason, lineage or freshness changed.
# Re-recorded again 2026-10-24 (PD-0067 decision 6, L-2/N-1, market-data/1.14 -> 1.15, and its review M-1). TWO things moved, and nothing else:
# (a) the code's method label: `convention_set_id` and the conventions entry `market_data.convention_set` read `market-data/1.15` in every manifest, and the release ids derived from the label changed;
# (b) every one of the 17 manifests gained exactly FIVE open-items lines, "market_data: not built: market-data/1.15 ..." (`market11.UNBUILT_1_15`): a manifest that cites 1.15 must say which 1.15 behaviours the code does not run.
# Shown by reverting, in scratch copies of the new tree, and re-running this very hash: (1) with `UNBUILT_1_15` emptied it is e0d38c11... (the baseline of the label move alone); (2) with `UNBUILT_1_15` emptied AND all EIGHT label
# constants reverted (manifest.CONVENTION_SET_ID; profiles.CONVENTION_SET and PROFILE_SET_VERSION; reconciliation.RULE_ID and TOLERANCE_REF; market11.FRESHNESS_ID, PRICE_OF_DATE_ID and FX_ID: eight constants in four modules) it is
# again 4e3a9a0d... (the previous baseline, taken before the label moved). Reverting only seven of the eight (FX_ID left at 1.15) gives 0e186490..., not 4e3a9a0d..., so a reviewer must revert all eight.
# For (1) the earlier round compared the unmasked canonical text of the 17 computations before and after the label move, with 1.15 read as 1.14 and every 64-hex id masked: byte-identical, and the 64-hex ids map one to one.
# No number, state, reason code, lineage entry, freshness or window changed.
# NOT moved by the 2026-10-24 registry re-issue (review M-2 of the label move: risk/1.10, performance-registry/1.1, diversification/1.1): a CP3 manifest carries none of the three section 33 registries' ids or
# digests, and the performance registry's `registry_id` stays performance/1.12. The baseline below is the one recorded above.
# Re-recorded again 2026-10-25 (F1 R4a label increment, market-data/1.15 -> 1.16, CP2 section 11 item 35, Quant note CP2_MD_1_16_LABEL_GATE_NOTE_2026-10-25). TWO things moved, and nothing else (the same two as 2026-10-24):
# (a) the code's method label: `convention_set_id` and the conventions entry `market_data.convention_set` read `market-data/1.16` in every manifest, and the release ids derived from the label changed; the profile-set id
# is `market-data/1.16#profiles/5` (it is not part of a CP3 manifest);
# (b) the "not built" open-items lines of every one of the 17 manifests are the six lines of `market11.UNBUILT_1_16` (they were the five of `UNBUILT_1_15`; one line is new, the securityType / securityType2 text defect of
# the Quant's answer (d), and the other five are re-worded for 1.16).
# Shown by reverting, in scratch copies of the new tree, and re-running this very hash: (1) the new tree is 952f7905... (the value below); (2) with `UNBUILT_1_16` emptied it is 34773977... (the label move alone);
# (3) with `UNBUILT_1_16` emptied AND all EIGHT label constants reverted to 1.15 (manifest.CONVENTION_SET_ID; profiles.CONVENTION_SET and PROFILE_SET_VERSION [1.15#profiles/4]; reconciliation.RULE_ID and TOLERANCE_REF;
# market11.FRESHNESS_ID, PRICE_OF_DATE_ID and FX_ID) it is e0d38c11... (the 1.15 label with no lines, the value recorded on 2026-10-24); (4) with the eight constants reverted AND market11.py as at HEAD 11c804a (which is the
# 1.15 constants and the five `UNBUILT_1_15` lines, and differs from the new file in nothing else: `git diff HEAD` of it shows the three ids, the tuple and its comment, and the `open_items=` argument) it is again
# 971cd925... (the baseline of 2026-10-24). Reverting only seven of the eight (FX_ID left at 1.16, no lines) gives c4bb1282..., so a reviewer must revert all eight. Profile content (profiles/5) and the three registries are
# not in a CP3 manifest, so they do not move this hash. No number, state, reason code, lineage entry, freshness or window changed.
BASELINE_SHA256 = "952f790512f5d70bdb0896fbfac0aa22ec59472ae8e7b7084c5fe603d9df39b4"
COMMITTED_PACK = ROOT / "reviews" / "gates" / "HG2_EVIDENCE" / "synthetic"
MANIFEST_KEYS = ['as_of', 'as_of_causes', 'as_of_rule', 'calendar_files', 'conformant', 'conventions', 'data_set_refs', 'detection_policy', 'engine_id', 'excluded_files', 'identities_run',
                 'identity_digest', 'instant', 'ledger_digest', 'ledger_version', 'methodology', 'numerics', 'open_items', 'parent_release_id', 'portfolio_id', 'release_id',
                 'reporting_currency', 'schema', 'scope', 'source_registry_digest', 'split_detection', 'split_suppressions_digest', 'state_kind', 'synthetic', 'valuation_mode', 'window']
METRIC_KEYS = ['breakdown', 'causes', 'conformant', 'currency', 'details', 'exact', 'excluded', 'excluded_weight', 'excluded_weight_presented', 'freshness', 'lineage', 'manifest_id',
               'method_id', 'metric_id', 'numeric_basis', 'partial', 'portfolio_state', 'reason', 'rounding_rule_id', 'stale_weight', 'stale_weight_presented', 'state', 'subject',
               'synthetic', 'unit', 'value', 'view', 'window']
WINDOW_KEYS = ['days', 'end', 'frequency', 'months', 'rule', 'since_snapshot', 'start']
_BUILT = {}


def setUpModule():
    subject, market = synthetic.build_synthetic_subject()
    try:
        _BUILT["computed"] = pack.run_all(subject)
        _BUILT["tmp"] = tempfile.TemporaryDirectory()
        pack.build_pack(subject, Path(_BUILT["tmp"].name) / "new")
    finally:
        market.close()


def tearDownModule():
    _BUILT["tmp"].cleanup()


def masked_hash(computed):
    items = []
    for c in computed.results:
        d = c.result.to_canonical_dict()
        d.pop("manifest_id")
        d.pop("result_digest")
        d["manifest"].pop("engine_id", None)
        for m in d["metrics"]:
            m.pop("manifest_id", None)
        items.append([c.key, d])
    return len(items), hashlib.sha256(canonical_json(items).encode("utf-8")).hexdigest()


def exacts(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "exact":
                yield path + "/exact", json.dumps(v)
            else:
                yield from exacts(v, path + "/" + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from exacts(v, f"{path}[{i}]")


class Cp3ByteIdentityTests(unittest.TestCase):
    def test_the_canonical_cp3_results_equal_the_recorded_baseline_apart_from_the_engine_id(self):
        n, digest = masked_hash(_BUILT["computed"])
        self.assertEqual((n, digest), (BASELINE_COMPUTATIONS, BASELINE_SHA256))

    def test_every_exact_value_of_the_committed_gate_record_is_reproduced(self):
        total = 0
        for old in sorted(COMMITTED_PACK.glob("*.json")):
            new = Path(_BUILT["tmp"].name) / "new" / old.name
            a = list(exacts(json.loads(old.read_text(encoding="utf-8"))))
            b = list(exacts(json.loads(new.read_text(encoding="utf-8"))))
            self.assertEqual(a, b, old.name)
            total += len(a)
        self.assertEqual(total, 228)

    def test_the_manifest_the_metric_and_the_window_keep_their_cp3_key_sets(self):
        result = _BUILT["computed"].results[0].result
        self.assertEqual(sorted(result.manifest.to_obj()), MANIFEST_KEYS)
        self.assertEqual(sorted(result.to_canonical_dict()["metrics"][0]), METRIC_KEYS)
        self.assertEqual(sorted(result.manifest.to_obj()["window"]), WINDOW_KEYS)

    def test_the_baseline_check_can_fail(self):
        n, digest = masked_hash(_BUILT["computed"])
        forged = _BUILT["computed"]
        forged_results = list(forged.results)
        first = forged_results[0]
        import dataclasses  # noqa: PLC0415

        metrics = list(first.result.metrics)
        m0 = dataclasses.replace(metrics[0], details=metrics[0].details + ("FORGED",))
        forged_results[0] = dataclasses.replace(first, result=dataclasses.replace(first.result, metrics=(m0,) + tuple(metrics[1:])))
        _n, other = masked_hash(dataclasses.replace(forged, results=forged_results))
        self.assertNotEqual(other, digest)


if __name__ == "__main__":
    unittest.main()
