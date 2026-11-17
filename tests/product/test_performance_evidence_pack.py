"""The HG2 evidence pack and its tools (`src/performance_tools`; PRD 38.4; tech plan 16.10; PD-0035 section 3).

The pack REPORTS what the engine computes; the golden tests prove correctness. These tests prove the PACK: it has every evidence item, labels every synthetic result, shows state, reason, detail, manifest id
and expected digest, never presents RESULT_NOT_COMPARED as reproduced, is byte-deterministic, never fabricates a missing real input, reads only admitted terms-attested files, and is imported by no product code.
"""

import ast
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(SRC))

from performance_tools import pack, real_slice, synthetic  # noqa: E402
from vendor_files import needs_vendor_files  # noqa: E402  (the vendor-payload gate; see vendor_files.py; the gated set is pinned in test_vendor_files_flag)

REAL_ROOT = real_slice.DEFAULT_ROOT
SECTIONS = [name for name, _t in pack.SECTION_FILES]
_BUILT = {}


def setUpModule():
    _BUILT["tmp"] = tempfile.TemporaryDirectory()
    root = Path(_BUILT["tmp"].name)
    for label in ("a", "b"):  # two builds: the second proves byte-determinism
        subject, market = synthetic.build_synthetic_subject()
        try:
            _BUILT[label] = pack.build_pack(subject, root / label)
        finally:
            market.close()
    _BUILT["root"] = root


def tearDownModule():
    _BUILT["tmp"].cleanup()


def load(label, name):
    return json.loads((_BUILT["root"] / label / name).read_text(encoding="utf-8"))


class BoundaryTests(unittest.TestCase):
    def test_no_product_module_imports_the_tools(self):
        for path in sorted(SRC.rglob("*.py")):
            if "performance_tools" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                for n in names:
                    self.assertFalse(n == "performance_tools" or n.startswith("performance_tools."), f"{path.relative_to(SRC)} imports {n}")

    def test_the_tools_use_no_network_clock_or_environment(self):
        for path in sorted((SRC / "performance_tools").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for banned in (r"import socket", r"\burllib", r"\brequests\b", r"http\.client", r"\.now\(", r"\.today\(", r"\btime\.time\(", r"os\.environ", r"getenv"):
                self.assertIsNone(re.search(banned, text), f"{path.name} uses {banned}")


class SyntheticPackTests(unittest.TestCase):
    def test_every_prd_evidence_item_has_a_file_and_the_pack_has_one_markdown_summary(self):
        files = {p.name for p in (_BUILT["root"] / "a").iterdir()}
        for name in SECTIONS:
            self.assertIn(f"{name}.json", files)
        self.assertEqual(len(SECTIONS), 16)
        self.assertTrue({"00_inputs.json", "00_manifests.json", "00_open_items.json", "SUMMARY.md"} <= files)
        self.assertEqual([f for f in files if f.endswith(".md")], ["SUMMARY.md"])
        for name in files:
            if name.endswith(".json"):
                json.loads((_BUILT["root"] / "a" / name).read_text(encoding="utf-8"))  # every JSON file parses

    def test_the_demonstration_covers_us_hk_and_cn_holdings_and_usd_hkd_cny_cash(self):
        positions = load("a", "01_positions.json")["data"]["states"][-1]  # the as-of date (the last of the dates, sorted)
        listings = {p["listing"] for a in positions["accounts"] for p in a["positions"]}
        cash = {c["currency"] for a in positions["accounts"] for c in a["cash"]}
        mics = {l.split("@")[1] for l in listings}
        self.assertTrue({"XNYS", "XHKG", "XSHG"} <= mics, mics)  # US, Hong Kong and Mainland China
        self.assertTrue({"USD", "HKD", "CNY"} <= cash, cash)

    def test_every_file_labels_the_results_synthetic_and_carries_the_pd_0035_caveat(self):
        for name in SECTIONS:
            doc = load("a", f"{name}.json")
            self.assertTrue(doc["labels"]["all_results_synthetic"], name)
            self.assertIn("SYNTHETIC", doc["labels"]["label"], name)
            self.assertIn("SYNTHETIC data only", doc["labels"]["pd_0035_caveat"], name)
        summary = (_BUILT["root"] / "a" / "SUMMARY.md").read_text(encoding="utf-8")
        self.assertIn("SYNTHETIC: every result below", summary)
        self.assertIn("PD-0035 section 3", summary)
        self.assertIn("DEMONSTRATION LEDGER", summary)

    def test_every_number_comes_with_state_reason_detail_manifest_id_and_the_digest_it_was_computed_to(self):
        doc = load("a", "02_current_value.json")["data"]
        self.assertTrue(doc["metrics"])
        for m in doc["metrics"]:
            for key in ("state", "reason", "details", "manifest_id", "synthetic", "causes"):
                self.assertIn(key, m)
            self.assertTrue(m["manifest_id"] and m["synthetic"] is True)
        rows = load("a", "00_manifests.json")["computations"]
        self.assertGreater(len(rows), 10)
        for r in rows:
            self.assertEqual(len(r["manifest_id"]), 64)
            self.assertEqual(len(r["expected_result_digest"]), 64)
            self.assertTrue(r["synthetic"])

    def test_every_manifest_is_reproduced_with_its_digest_and_a_missing_digest_is_never_reproduced(self):
        rows = load("a", "00_manifests.json")["computations"]
        self.assertTrue(all(r["reproduction"] == "REPRODUCED" and r["reproduced"] for r in rows), [r for r in rows if r["reproduction"] != "REPRODUCED"])
        # the builder's own rule: a re-run without an expected digest is RESULT_NOT_COMPARED and not counted as reproduced
        computed = _BUILT["a"]["computed"]
        first = computed.results[0].result
        from performance import engine  # noqa: PLC0415

        s = computed.subject
        report = engine.reproduce(first.manifest, None, s.events, s.store, s.resolver, s.market_conventions, s.perf, suppressions=computed.suppressions)
        self.assertEqual(report.status.value, "RESULT_NOT_COMPARED")
        self.assertNotEqual(report.status.value, "REPRODUCED")
        summary = (_BUILT["root"] / "a" / "SUMMARY.md").read_text(encoding="utf-8")
        self.assertIn(f"Reproduced with a matching digest: **{len(rows)} of {len(rows)}**", summary)

    def test_a_result_whose_digest_does_not_match_is_not_reproduced_in_the_pack(self):
        import dataclasses  # noqa: PLC0415

        computed = _BUILT["a"]["computed"]
        forged = dataclasses.replace(computed, results=[dataclasses.replace(c, result=dataclasses.replace(c.result, result_digest="0" * 64)) for c in computed.results])
        rows = pack.reproduction(forged)
        self.assertEqual({r["reproduction"] for r in rows}, {"RESULT_DIFFERS"})
        self.assertEqual({r["reproduced"] for r in rows}, {False})  # a mismatch (or an uncompared result) is never counted as reproduced
        summary = pack._summary(forged, pack.build_sections(forged, rows), rows, {})
        self.assertIn(f"Reproduced with a matching digest: **0 of {len(rows)}**", summary)

    def test_the_identities_ran_and_none_failed_and_i7_is_stated_not_assumed(self):
        doc = load("a", "15_reconciliation_proof.json")["data"]
        counts = doc["identity_status_counts_over_every_metric_carrying_one"]
        for ident in ("I-1", "I-2", "I-3", "I-4", "I-5", "I-8", "I-9"):
            self.assertIn("PASS", counts[ident], ident)
        self.assertEqual(doc["failed"], [])
        self.assertIn("I-7", counts)
        for row in doc["identity_I-7_method_independence"]:
            self.assertIn(row["status"], ("PASS", "NOT_APPLICABLE", "NOT_COMPUTABLE"))
            if row["status"] == "NOT_APPLICABLE":
                self.assertTrue(row["why"])  # never counted as a pass: it says why it does not apply

    def test_unsupported_cases_show_their_states_not_numbers(self):
        docs = load("a", "11_twr.json")["data"]["rows"]
        ytd = next(r for r in docs if r["window"] == "YTD")
        self.assertEqual((ytd["twr"]["value"], ytd["twr"]["state"]), (None, "INSUFFICIENT_DATA"))
        self.assertIn("WINDOW_BEFORE_INCEPTION", ytd["twr"]["details"])
        miss = load("a", "10_missing_cost_basis.json")["data"]
        self.assertTrue(miss["metrics_returning_MISSING_COST_BASIS"])  # P1's MSFT holding has no recorded basis: withheld, never 0

    def test_internal_transfers_have_no_portfolio_level_effect_and_splits_and_dividends_are_shown(self):
        transfers = load("a", "07_internal_transfers.json")["data"]
        self.assertTrue(transfers["internal_legs"] and transfers["checks"])
        self.assertTrue(all(c["no_portfolio_level_effect"] for c in transfers["checks"]))
        splits = load("a", "09_splits.json")["data"]
        self.assertEqual(splits["detection"], "F8B_DRY_RUN")  # detection always runs where calendars exist
        self.assertTrue(splits["ledger_splits"] and splits["ledger_splits"][0]["quantity_before"] != splits["ledger_splits"][0]["quantity_after"])
        divs = load("a", "08_dividends.json")["data"]
        self.assertTrue(any(e["type"] == "DIVIDEND" for e in divs["dividend_and_cost_events"]))
        self.assertTrue(divs["receivable_on_the_day_before_each_pay_date"])  # accrued from the ex-date: a receivable until the pay date, valued by FX meanwhile
        self.assertEqual(divs["receivables_at_as_of"], [])  # settled by 04-30: it is cash then, not income again

    def test_fx_attribution_reconciles_and_the_tolerances_are_stated_with_the_open_items(self):
        rows = load("a", "14_fx_attribution.json")["data"]["rows"]
        since = next(r for r in rows if r["window"] == "SINCE_INCEPTION")
        self.assertEqual(since["money"]["state"], "LIMITED")  # SYNA's stale sessions: stated, not hidden
        self.assertTrue(all(v == "PASS" for v in since["identities"].values()))
        tol = load("a", "16_tolerances.json")["data"]
        self.assertTrue(tol["table"])
        self.assertEqual(tol["open_items_still_injected"], [])  # performance/1.12: nothing unbuilt, no MEMORY minor-unit row
        self.assertIs(tol["is_conformant"], True)
        self.assertIn("performance/1.12", tol["source"])
        summary = (_BUILT["root"] / "a" / "SUMMARY.md").read_text(encoding="utf-8")
        self.assertIn("Open items the convention set still lists:\n- none", summary)  # the summary prints "none", not an empty list
        # CP4-4: one statement of conformance (no stale contrary limitation), and the market-data open items every manifest carries are listed beside it
        self.assertNotIn("is_conformant` is False while", summary)
        self.assertIn("Open items of the market-data convention set that every manifest in this pack lists", summary)
        self.assertIn("market_data: not built: a real corporate-action FEED adapter", summary)
        self.assertNotIn("Current mode (instant t)", summary)  # closed: Ruling 1.7 (1.12) items 2 and 5 are built
        listed = tol["market_data_open_items_in_manifests"]
        self.assertTrue(listed and all(i.startswith("market_data:") for i in listed))
        manifests = load("a", "00_manifests.json")
        self.assertTrue(manifests)

    def test_the_pack_is_byte_deterministic(self):
        self.assertEqual(_BUILT["a"]["files"], _BUILT["b"]["files"])
        for name in _BUILT["a"]["files"]:
            self.assertEqual((_BUILT["root"] / "a" / name).read_bytes(), (_BUILT["root"] / "b" / name).read_bytes(), name)

    def test_the_pack_reports_the_engines_own_numbers(self):
        computed = _BUILT["a"]["computed"]
        s = computed.subject
        from performance import engine  # noqa: PLC0415

        base = dict(suppressions=computed.suppressions, portfolio_id=s.portfolio_id, detection=computed.detection, detection_policy=pack.svc.policy_reference(s.policy))
        direct = engine.compute(s.events, s.ledger_version, s.as_of, s.reporting, s.store, s.resolver, s.market_conventions, s.perf, **base)
        doc = load("a", "02_current_value.json")["data"]
        self.assertEqual(doc["manifest_id"], direct.manifest.manifest_id)
        total = next(m for m in doc["total_reporting"])
        self.assertEqual(total["value"], format(next(m.result.value for m in direct.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"), "f"))


class IdentitySevenTests(unittest.TestCase):
    """I-7 in the pack where its domain holds: golden P14 (all USD, buys and a sale, no transfer, every basis known): RG + UG = proceeds + MV - costs, exactly (the golden I-7 total is 250)."""

    @classmethod
    def setUpClass(cls):
        import cp3_golden_part3_kit as p3  # noqa: PLC0415
        import cp3_golden_part4_kit as p4  # noqa: PLC0415
        import test_cp1_reconstruction as cp1  # noqa: PLC0415
        from corporate_actions_service import split_confirmation as f8b  # noqa: PLC0415
        from domain.currency import CurrencyCode  # noqa: PLC0415
        from performance.engine import performance_conventions  # noqa: PLC0415
        from performance.periods import WindowRule, WindowSpec  # noqa: PLC0415

        ids = cp1.Ids(randomize=False)
        market = p4.build_market(ids)
        cls.addClassCleanup(market.close)
        p14 = next(p for p in p3.FIXTURE["portfolios"] if p["name"].startswith("P14 "))
        events = tuple(p3.portfolio_events(p14, ids))
        cls.subject = pack.PackSubject(
            name="P14", kind="SYNTHETIC_DEMONSTRATION_A", description="golden P14", portfolio_id=ids(p14["portfolio_id"]), events=events, ledger_version=6, reporting=CurrencyCode("USD"),
            store=market.store, resolver=market.ident, market_conventions=market.conventions, perf=performance_conventions(),
            policy=f8b.ConfirmationPolicy(frozenset({"x.feed"}), frozenset({"x.filing"})), as_of=pack.datetime.date(2025, 3, 31), windows=(("SINCE_INCEPTION", WindowSpec(WindowRule.SINCE_INCEPTION)),))
        cls.computed = pack.run_all(cls.subject)

    def test_the_identity_passes_where_it_applies(self):
        (row,) = pack._i7(self.computed)
        self.assertEqual(row["status"], "PASS", row)
        self.assertEqual(row["realized_plus_unrealized"], pack.Fraction(250))  # 118 + 132, the golden P14 I-7 total
        self.assertEqual(row["realized_plus_unrealized"], row["proceeds_plus_market_value_minus_costs"])

    def test_a_forged_gain_is_a_fail_never_a_pass(self):
        import dataclasses  # noqa: PLC0415

        forged = []
        for c in self.computed.results:
            if c.kind == "gains":
                metrics = tuple(dataclasses.replace(m, exact=m.exact + 1) if m.metric_id == "realized_gain_total" else m for m in c.result.metrics)
                c = dataclasses.replace(c, result=dataclasses.replace(c.result, metrics=metrics))
            forged.append(c)
        (row,) = pack._i7(dataclasses.replace(self.computed, results=forged))
        self.assertEqual(row["status"], "FAIL")


class RealSliceTests(unittest.TestCase):
    @needs_vendor_files
    def test_only_terms_attested_files_are_admitted_and_the_drafts_are_never_read(self):
        rows = real_slice.classify_files(REAL_ROOT)
        self.assertTrue(rows)
        registry = real_slice.FileStore(REAL_ROOT).load_registry()
        for r in rows:
            if r["admitted"]:
                self.assertTrue(registry.get(r["source_id"]).terms_attested, r["source_id"])
                self.assertIn(r["source_id"], real_slice.REAL_SOURCES)
                self.assertFalse(r["synthetic"])
            if r["source_id"].startswith("akshare"):
                self.assertFalse(r["admitted"])
                self.assertIn("SOURCE_TERMS_NOT_ATTESTED", r["reason"])
        self.assertFalse([r for r in rows if "drafts" in r["path"]])  # the calendar drafts are not files of the store

    @needs_vendor_files
    def test_the_real_slice_builds_from_the_admitted_files_and_is_labelled_real_and_states_what_is_missing(self):
        subject, report = real_slice.build_real_subject(REAL_ROOT)
        self.assertIsNotNone(subject, report["status"])
        self.assertEqual(report["status"], "BUILT")
        with tempfile.TemporaryDirectory() as tmp:
            result = pack.build_pack(subject, Path(tmp))
            labels = pack._labels(result["computed"])
            self.assertFalse(labels["any_result_synthetic"])
            self.assertIn("REAL INPUTS", labels["label"])
            summary = (Path(tmp) / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertNotIn("SYNTHETIC: every result below", summary)
            self.assertIn("PD-0035 section 3", summary)  # the caveat is on the real pack too
            self.assertTrue(all(r["reproduced"] for r in result["reproduced"]))
        if not report["calendars_registered"]:  # no registered calendar: UNKNOWN freshness, detection not run, no number, and the pack says exactly what is needed
            self.assertEqual(result["computed"].detection, "NOT_RUN_NO_CALENDARS")
            val = result["computed"].get(f"valuation@{subject.as_of.isoformat()}")
            total = next(m for m in val.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING")
            self.assertEqual((total.result.value, total.result.sufficiency_state.value), (None, "INSUFFICIENT_DATA"))
            self.assertTrue(any("CALENDAR_COVERAGE_GAP" in c.note for c in total.causes))
            self.assertTrue(any("REGISTER THE SESSION CALENDARS" in r for r in report["requirements"]))

    def test_with_no_real_price_file_the_slice_is_not_built_and_the_needs_are_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(REAL_ROOT / "SOURCES.json", Path(tmp) / "SOURCES.json")
            subject, report = real_slice.build_real_subject(Path(tmp))
            self.assertIsNone(subject)
            self.assertEqual(report["status"], "NO_REAL_PRICE_FILE")
            self.assertTrue(any("REAL US PRICES" in r for r in report["requirements"]))
            self.assertTrue(any("REGISTER THE SESSION CALENDARS" in r for r in report["requirements"]))

    @needs_vendor_files
    def test_an_unattested_source_is_refused_before_its_payload_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REAL_ROOT / "files" / "alphavantage.us", root / "files" / "alphavantage.us")
            registry = json.loads((REAL_ROOT / "SOURCES.json").read_text(encoding="utf-8"))
            for source in registry["sources"]:
                if source["source_id"] == "alphavantage.us":
                    source["terms_check"]["permits_internal_development_use"] = False
            (root / "SOURCES.json").write_text(json.dumps(registry), encoding="utf-8")
            rows = real_slice.classify_files(root)
            self.assertTrue(rows and not any(r["admitted"] for r in rows))
            subject, report = real_slice.build_real_subject(root)
            self.assertIsNone(subject)
            self.assertEqual(report["status"], "NO_REAL_PRICE_FILE")

    def test_the_command_line_writes_a_not_built_summary_without_numbers_when_there_is_no_real_file(self):
        from performance_tools import evidence_pack  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            data, out = Path(tmp) / "data", Path(tmp) / "out"
            data.mkdir()
            shutil.copy(REAL_ROOT / "SOURCES.json", data / "SOURCES.json")
            self.assertEqual(evidence_pack.run_real(out, data), 0)
            text = (out / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("Real slice: not built", text)
            self.assertIn("No number is shown", text)
            self.assertTrue((out / "REAL_SLICE_REPORT.json").is_file())


if __name__ == "__main__":
    unittest.main()
