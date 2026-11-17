"""The code's method label is `market-data/1.16`, everywhere it is built, and nowhere else (PD-0067 decision 6 moved it to 1.15; the F1 R4a
label increment, CP2 section 11 item 35, moved it to 1.16 on 2026-10-25, re-recorded here).

The label is part of the method (P12, NFR-001): it is in every manifest, every release id and every lineage `precision_profile_id`,
so a release id names the method the code runs. A bump that moves some constants and not others would mint ids that name two
sets at once. These tests pin the one-set rule; they decide no convention (the label's value is the owner's, PD-0067 decision 6).

The label moved before the 1.15 engine behaviours were built (market-data/1.15 section 11 items 17 to 20, 29 and 30; 1.16 builds items 21 to 28 and 32 to 35 and leaves those). A manifest that cites
1.16 must therefore say which of them it does not run (P9, section 21; CP2 section 11 "When a manifest may cite 1.16", point 2), and the tests below hold that to be true in both
directions: every unbuilt behaviour is listed, and a listed behaviour that appears in src/ must have its line taken out.

The label is also stated in the three shipped PRD section 33 registries (`common.implementation_version` names what the code runs, not a
minimum: risk Ruling 9.2 (1.10)). They are byte copies of Quant files and are re-issued under a new id whenever the label moves, so
`RegistryVersionTests` checks the market-data entry alone, and checks that the check can fail (review M-2 and M-3, 2026-10-24).
"""

import ast
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from diversification import registry as diversification_registry  # noqa: E402
from marketdata import manifest, market11, profiles, reconciliation  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.market11 import UNBUILT, UNBUILT_1_16, market11_conventions  # noqa: E402
from product_contract import performance_methodology_registry as performance_registry  # noqa: E402
from risk import registry as risk_registry  # noqa: E402

GOVERNING_SET = "market-data/1.16"
PREVIOUS_SET = "market-data/1.15"

# The three shipped PRD section 33 registries, by family. Each is a byte copy of a Quant-owned methodology file (tested equal elsewhere).
# The family is the key, not the registry id: a registry is re-issued under a NEW id whenever a dependency label moves (risk Ruling 9.2 (1.10),
# market-data 1.16 section 11 item 35), so a guard keyed by the id would stop looking at the file the moment the id moved (review M-3, 2026-10-24).
REGISTRY_FILES = {
    "risk": SRC / "risk" / "risk_registry.json",
    "performance": SRC / "product_contract" / "performance_methodology_registry.json",
    "diversification": SRC / "diversification" / "diversification_registry.json",
}

# The issue in force for the 1.16 label, the issue it replaced (the 1.15 label's issue), and the ONLY places the two differ (JSON pointers). Every other byte of the text,
# every entry and every number included, is the earlier issue's. Re-recorded 2026-10-25 with the reason "re-issue for market-data/1.16 (CP2 section 11 item 35, Quant note
# CP2_MD_1_16_LABEL_GATE_NOTE_2026-10-25)": risk/1.10 -> 1.11, performance-registry/1.1 -> 1.2 (registry_id performance/1.12 unchanged), diversification/1.1 -> 1.2. The pointers were
# computed from the two files and read against each file's change_note, which names the same fields; the SHA-256 of each file and the loader digests equal the values the Quant's
# note states (risk 9760901707bd..., 5c630fdf...; performance ef68208a2f6c..., f2aefda7...; diversification 0cd4fbe7d544..., 4f27f1e9...).
REGISTRY_REISSUES = {
    "risk": {
        "previous": ROOT / "methodology" / "registry" / "RISK_1.10_REGISTRY.json",
        "current": ROOT / "methodology" / "registry" / "RISK_1.11_REGISTRY.json",
        "differs_at": {"/registry_id", "/issued", "/change_note", "/status", "/common/implementation_version/0", "/common/implementation_version/3"},
        "file_sha256": "9760901707bd925fbd5f4693aa7b763f81cc2fa50ea1cccdccbfc7e90e899de3",
        "digest": "5c630fdf9ff4eb6cf0569cda655794b1c0e1ec1f64c1e2ea7daf3df9348058ce",
    },
    "performance": {
        "previous": ROOT / "methodology" / "registry" / "PERFORMANCE_1.12_REGISTRY_APPENDIX_1.1.json",
        "current": ROOT / "methodology" / "registry" / "PERFORMANCE_1.12_REGISTRY_APPENDIX_1.2.json",
        "differs_at": {"/appendix_id", "/issued", "/change_note", "/common/implementation_version/2", "/common/historical_version_note"},
        "file_sha256": "ef68208a2f6ca06cd5f6cade006a69dfa072fd661112b95874e05bc6e4df5840",
        "digest": "f2aefda7232da0a46be1d1592bb50856becf1d10a237e30cf64d060437891a71",
    },
    "diversification": {
        "previous": ROOT / "methodology" / "registry" / "DIVERSIFICATION_1.1_REGISTRY.json",
        "current": ROOT / "methodology" / "registry" / "DIVERSIFICATION_1.2_REGISTRY.json",
        "differs_at": {"/registry_id", "/issued", "/change_note", "/common/implementation_version/0", "/common/implementation_version/2",
                       "/common/implementation_version/3"},
        "file_sha256": "0cd4fbe7d544d865448e734ccf61133fb406a0abda9bbb4876a1cda2513bedaa",
        "digest": "4f27f1e957e36a6c0c749228153d5fb266e0a9ffd0b4f212fc95e8899e852297",
    },
}


def shipped_registries():
    return {family: json.loads(path.read_text(encoding="utf-8")) for family, path in REGISTRY_FILES.items()}


def market_data_items(registry_doc):
    return [v for v in registry_doc["common"]["implementation_version"] if v.startswith("market-data/")]


def stale_registries(docs):
    """The families whose `common.implementation_version` does not name exactly the governing market-data set. It reads that one entry and nothing
    else of the registry: not its id, not its digest, not the other dependencies."""
    return {family: market_data_items(doc) for family, doc in docs.items() if market_data_items(doc) != [GOVERNING_SET]}


def differences(a, b, pointer=""):
    """Every JSON pointer at which `a` and `b` differ (a key present in one only, a list of another length, or unequal leaves)."""
    if isinstance(a, dict) and isinstance(b, dict):
        found = set()
        for key in set(a) | set(b):
            found |= differences(a[key], b[key], f"{pointer}/{key}") if key in a and key in b else {f"{pointer}/{key}"}
        return found
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        found = set()
        for i, (x, y) in enumerate(zip(a, b)):
            found |= differences(x, y, f"{pointer}/{i}")
        return found
    return set() if a == b and type(a) is type(b) else {pointer or "/"}

# Ruling 3.2 items 4 and 5, Rulings 7.4 and 7.5: a code token that only the built behaviour would introduce, with the index (in
# UNBUILT_1_16) of the line that says the behaviour is not built. Test V4 and the Ruling 4.5 decimal comparison introduce no token
# of their own that this test could rely on; they are covered by the listing tests only.
TRIPWIRES = (
    ("SPLIT_LABEL_EXPOSED", 0),
    ("DIVIDEND_LABEL_EXPOSED", 1),
    ("UNMAPPED_ACTION_RECORD", 4),
    ("EMPTY_RESPONSE", 4),
)


def label_constants():
    return {
        "manifest.CONVENTION_SET_ID": manifest.CONVENTION_SET_ID,
        "profiles.CONVENTION_SET": profiles.CONVENTION_SET,
        "profiles.PROFILE_SET_VERSION": profiles.PROFILE_SET_VERSION,
        "reconciliation.RULE_ID": reconciliation.RULE_ID,
        "reconciliation.TOLERANCE_REF": reconciliation.TOLERANCE_REF,
        "market11.FRESHNESS_ID": market11.FRESHNESS_ID,
        "market11.PRICE_OF_DATE_ID": market11.PRICE_OF_DATE_ID,
        "market11.FX_ID": market11.FX_ID,
    }


def python_text_outside_the_unbuilt_lines(path: Path) -> str:
    """The source of `path`, with the `UNBUILT_1_16` assignment of market11 cut out (it names the tokens on purpose)."""
    text = path.read_text(encoding="utf-8")
    if path != SRC / "marketdata" / "market11.py":
        return text
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "UNBUILT_1_16" for t in node.targets):
            return text.replace(ast.get_source_segment(text, node), "")
    raise AssertionError("market11.UNBUILT_1_16 is not an assignment at module level")


class VersionLabelTests(unittest.TestCase):
    def test_every_label_constant_names_the_one_governing_set(self):
        self.assertEqual(len(label_constants()), 8)  # the eight label constants, in four modules
        for name, value in label_constants().items():
            self.assertEqual(value.split("#")[0], GOVERNING_SET, name)

    def test_the_profile_set_id_carries_the_set_and_its_own_counter(self):
        # profiles/5: the profile content moved with the 1.16 label increment (the Quant's answer (b): the DECLARED `call_adjustment` entries of the two Alpha Vantage
        # `TIME_SERIES_DAILY` calls, the US MICs ARCX/BATS/XASE with their zones, and the Ruling 4.7 item 6 gate); profiles/4 (1.15) held the MEMORY entries
        self.assertEqual(profiles.PROFILE_SET_VERSION, f"{GOVERNING_SET}#profiles/5")
        self.assertEqual(profiles.SOURCES["alphavantage.us"].profile_id("close"), f"{GOVERNING_SET}#profiles/5:alphavantage.us:close")

    def test_a_profile_id_of_the_previous_set_is_not_read(self):
        # an id written under 1.15 (profiles/4) names another profile set: recomputed at ingest, as for every earlier bump
        old = f"{PREVIOUS_SET}#profiles/4:alphavantage.us:close"
        self.assertIsNone(profiles.field_profile_of(old))
        new = profiles.SOURCES["alphavantage.us"].profile_id("close")
        self.assertIs(profiles.field_profile_of(new), profiles.SOURCES["alphavantage.us"].fields["close"])

    def test_no_label_constant_names_the_previous_set(self):
        # the ids a result prints are built from these constants; none may name the previous set
        for name, value in label_constants().items():
            self.assertNotIn(PREVIOUS_SET, value, name)

    def test_no_python_module_under_src_builds_an_id_of_the_previous_set(self):
        # A string constant that IS a label (the set itself, or the set followed by `#`) and names 1.15. Comments and docstrings that
        # narrate history are not labels (they start with other text) and are not matched. The three JSON registries under src/ are
        # not Python and are not the running label: they are byte copies of the Quant's registry files. What their
        # `implementation_version` field must say is held by `RegistryVersionTests`.
        offenders = []
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value == PREVIOUS_SET or node.value.startswith(PREVIOUS_SET + "#"):
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: {node.value!r}")
        self.assertEqual(offenders, [])


class RegistryVersionTests(unittest.TestCase):
    """Reviews M-2 and M-3 (2026-10-24). `analytics_composer` prints a registry's id and digest next to `conventions` that name market-data/1.16, and
    PRD section 33 `implementation_version` names what the code runs (risk Ruling 9.2 (1.10)), so a registry that names another market-data
    version puts two versions in one audit chain. The Quant re-issued the three registries for 1.16 under new ids (2026-10-25); the copies in src/ are those files.

    The guard (`stale_registries`) reads the market-data entry of `common.implementation_version` and nothing else. It is keyed by family, not by id:
    review M-3 showed that a guard keyed by today's ids stops looking at the file the moment the Quant re-issues it under a new id, and so could
    never fail again. Each test below can fail, and `test_the_guard_flips_on_the_market_data_entry_alone` shows that it does."""

    def test_the_shipped_registries_state_the_version_the_code_runs(self):
        self.assertEqual(stale_registries(shipped_registries()), {})

    def test_the_guard_reads_the_files_the_engines_load(self):
        self.assertEqual(risk_registry.REGISTRY_FILE.resolve(), REGISTRY_FILES["risk"].resolve())
        self.assertEqual(performance_registry.REGISTRY_FILE.resolve(), REGISTRY_FILES["performance"].resolve())
        self.assertEqual(performance_registry.REGISTRY_BYTES, REGISTRY_FILES["performance"].read_bytes())
        self.assertEqual(diversification_registry.REGISTRY_BYTES, REGISTRY_FILES["diversification"].read_bytes())
        self.assertEqual(risk_registry.REGISTRY_FILE.read_bytes(), REGISTRY_FILES["risk"].read_bytes())

    def test_the_guard_flips_on_the_market_data_entry_alone(self):
        docs = shipped_registries()
        for family in docs:
            items = docs[family]["common"]["implementation_version"]
            at = [i for i, v in enumerate(items) if v.startswith("market-data/")]
            self.assertEqual(len(at), 1, family)
            with self.subTest(family=family):
                # the entry alone moves back: stale, though the id, the digest and every other entry are as shipped
                entry_only = copy.deepcopy(docs)
                entry_only[family]["common"]["implementation_version"][at[0]] = PREVIOUS_SET
                self.assertEqual(stale_registries(entry_only), {family: [PREVIOUS_SET]})
                # the id (and the issue date) move, the entry does not: not stale
                id_only = copy.deepcopy(docs)
                for key in ("registry_id", "appendix_id"):
                    if key in id_only[family]:
                        id_only[family][key] = "re-issued/9.99"
                id_only[family]["issued"] = "2099-01-01"
                self.assertEqual(stale_registries(id_only), {})
                # both move: stale (the id changing does not hide the entry, which is the M-3 gap)
                both = copy.deepcopy(id_only)
                both[family]["common"]["implementation_version"][at[0]] = PREVIOUS_SET
                self.assertEqual(stale_registries(both), {family: [PREVIOUS_SET]})
                # the entry missing, or named twice, is not "the version the code runs" either
                missing = copy.deepcopy(docs)
                del missing[family]["common"]["implementation_version"][at[0]]
                self.assertEqual(stale_registries(missing), {family: []})
                twice = copy.deepcopy(docs)
                twice[family]["common"]["implementation_version"].append(PREVIOUS_SET)
                self.assertEqual(stale_registries(twice), {family: [GOVERNING_SET, PREVIOUS_SET]})
                # the other families are judged on their own entries
                others = {f: d for f, d in entry_only.items() if f != family}
                self.assertEqual(stale_registries(others), {})

    def test_the_issues_before_the_re_issue_are_stale_for_this_label(self):
        # the real unsynced state, not a synthetic one: each earlier issue (kept in methodology/registry as the record) names market-data/1.15
        for family, spec in REGISTRY_REISSUES.items():
            previous = json.loads(spec["previous"].read_text(encoding="utf-8"))
            self.assertEqual(stale_registries({family: previous}), {family: [PREVIOUS_SET]}, family)

    def test_each_registry_names_its_own_id_and_its_dependencies_at_the_labels_the_code_runs(self):
        docs = shipped_registries()
        risk, performance, diversification = (docs[f]["common"]["implementation_version"] for f in ("risk", "performance", "diversification"))
        self.assertEqual(risk[0], risk_registry.REGISTRY_ID)
        self.assertIn(performance_registry.REGISTRY_ID, risk)
        self.assertEqual(performance[0], performance_registry.REGISTRY_ID)
        self.assertEqual(diversification[0], diversification_registry.REGISTRY_ID)
        self.assertIn(risk_registry.REGISTRY_ID, diversification)
        self.assertIn(performance_registry.REGISTRY_ID, diversification)
        self.assertEqual((risk_registry.REGISTRY_ID, performance_registry.REGISTRY_ID, diversification_registry.REGISTRY_ID),
                         ("risk/1.11", "performance/1.12", "diversification/1.2"))
        self.assertEqual(performance_registry.REGISTRY.appendix_id, "performance-registry/1.2")  # registry_id stays performance/1.12 through the appendices 1.0, 1.1 and 1.2; the appendix id and the digest tell them apart

    def test_the_re_issues_differ_from_the_issue_they_replace_only_where_the_change_note_says(self):
        # nothing numeric, no entry and no ruling moved: the only differences are the labels and their notes
        shipped = shipped_registries()
        for family, spec in REGISTRY_REISSUES.items():
            with self.subTest(family=family):
                previous = json.loads(spec["previous"].read_text(encoding="utf-8"))
                self.assertEqual(differences(previous, shipped[family]), spec["differs_at"])
                self.assertEqual(previous["entries"], shipped[family]["entries"])

    def test_the_copies_are_the_quants_re_issues_by_file_hash_and_by_digest(self):
        digests = {"risk": risk_registry.REGISTRY.digest, "performance": performance_registry.REGISTRY.digest,
                   "diversification": diversification_registry.REGISTRY_DIGEST}
        for family, spec in REGISTRY_REISSUES.items():
            with self.subTest(family=family):
                self.assertEqual(REGISTRY_FILES[family].read_bytes(), spec["current"].read_bytes())
                self.assertEqual(hashlib.sha256(REGISTRY_FILES[family].read_bytes()).hexdigest(), spec["file_sha256"])
                self.assertEqual(digests[family], spec["digest"])

    def test_the_differences_function_can_fail(self):
        self.assertEqual(differences({"a": [1, 2], "b": {"c": 1}}, {"a": [1, 3], "b": {"c": 1}, "d": 0}), {"/a/1", "/d"})
        self.assertEqual(differences({"a": [1]}, {"a": [1, 2]}), {"/a"})
        self.assertEqual(differences({"a": 1}, {"a": True}), {"/a"})  # 1 == True in Python; a registry value changing type is a difference
        self.assertEqual(differences({"a": 1}, {"a": 1}), set())


class UnbuiltBehavioursAreDisclosedTests(unittest.TestCase):
    """Review M-1 (2026-10-24), re-recorded for 1.16 (2026-10-25, CP2 section 11 "When a manifest may cite 1.16", point 2): a manifest that cites
    market-data/1.16 lists the behaviours of items 17 to 20, 29 and 30 it does not run. Items 21 and 22 are built (the A-share route and its not-admitted gate;
    Ruling 6.5 item 4, `test_marketdata_r4a_inputs.ConfirmationPolicyWithNoCorporateActionFileTests.test_7`), so they have no line."""

    def test_every_unbuilt_1_16_behaviour_is_a_line_of_the_open_items_every_result_carries(self):
        items = market11_conventions(CalendarSet()).visible_open_items()
        self.assertEqual(len(UNBUILT_1_16), 6)
        for line in UNBUILT_1_16:
            self.assertIn(line, items)
            self.assertTrue(line.startswith(f"not built: {GOVERNING_SET} "), line)
        # the older four stay as they were (CP4 counts them) and stay listed
        self.assertTrue(set(UNBUILT) <= set(items))
        self.assertEqual(len(UNBUILT), 4)

    def test_the_lines_cover_the_unbuilt_behaviours_one_each(self):
        for part in ("Ruling 3.2 item 4", "Ruling 3.2 item 5", "Ruling 3.3, Test V4", "Ruling 4.5 (1.15)", "Rulings 7.4 and 7.5", "Ruling 7.3 item 3 and Ruling 7A.1 as worded"):
            self.assertEqual(sum(part in line for line in UNBUILT_1_16), 1, part)

    def test_the_exposure_line_says_the_interim_check_is_by_hand_and_not_recorded(self):
        # Ruling 3.2 item 6: until item 4 and V1 are built, a refusal made before the run; the manifest cannot show it was made
        line = UNBUILT_1_16[0]
        self.assertIn("SPLIT_LABEL_EXPOSED", line)
        self.assertIn("Ruling 3.2 item 6", line)
        self.assertIn("by hand", line)
        self.assertIn("does not record", line)

    def test_the_lineage_line_names_the_three_things_item_5_requires(self):
        line = UNBUILT_1_16[1]
        for part in ("label status", "label source", "E(d_p, R)", "found in E; none in E; none in M"):
            self.assertIn(part, line)

    def test_the_security_type_line_is_the_open_item_of_answer_d_and_changes_no_code(self):
        # The Quant's answer (d) of 2026-10-25: Ruling 7.3 item 3 and Ruling 7A.1 name `securityType2`, the rule means `securityType`; the text
        # defect goes to the next version and ETF values need a human's confirmation. The line says so; the code reads `securityType`.
        line = UNBUILT_1_16[5]
        for part in ("securityType2", "securityType", "next market-data version", "ETF", "human's confirmation"):
            self.assertIn(part, line)

    def test_no_listed_behaviour_has_appeared_in_src_while_its_line_is_still_listed(self):
        found = []
        for path in sorted(SRC.rglob("*.py")):
            text = python_text_outside_the_unbuilt_lines(path)
            for token, index in TRIPWIRES:
                if token in text:
                    found.append(f"{token} in {path.relative_to(ROOT)} (line {index} of market11.UNBUILT_1_16 says it is not built)")
        self.assertEqual(found, [], "a behaviour that its open-items line calls unbuilt now exists: take the line out (or reword it) in the "
                                    "same change, and re-record the byte-identity baseline and the market11 pin")

    def test_the_cut_removes_the_listed_lines_from_market11_and_nothing_else(self):
        # without the cut, market11 itself would trip the scan (the lines name the tokens); and the cut leaves the rest of the file whole
        path = SRC / "marketdata" / "market11.py"
        raw, cut = path.read_text(encoding="utf-8"), python_text_outside_the_unbuilt_lines(path)
        for token, _ in TRIPWIRES:
            self.assertIn(token, raw)
            self.assertNotIn(token, cut)
        self.assertIn("class Market11Freshness", cut)
        self.assertIn("UNBUILT = (", cut)


if __name__ == "__main__":
    unittest.main()
