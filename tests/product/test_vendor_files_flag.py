"""Pins the set of tests gated by FINWEB_NO_VENDOR_FILES (tests/product/vendor_files.py).

A cloud run has no human-downloaded vendor payloads (`data/marketdata/files/` is gitignored; PD-0027/PD-0028). Setting the flag skips exactly the tests below. The set is pinned
here so the gate cannot grow silently: adding a test to it is a reviewed change to EXPECTED_GATED. Four independent checks hold the pin:

1. `gated_ids`: a static scan of the decorator on the methods of every test class, compared with EXPECTED_GATED.
2. `flag_problems` (static, every test file but the helper and this file): the flag's name, or any import of the helper other than the plain
   `from vendor_files import needs_vendor_files` used only as a plain decorator on a `test*` method of a top-level class, fails. So the flag cannot be read, aliased, rebound,
   applied by assignment, wrapped in an inline `skipIf`, or raised as a `SkipTest` from `setUpModule`, `setUpClass` or a test body, in any other file.
3. `payload_skip_problems` (static): a `skip*`/`SkipTest` in the same top-level scope as a reference to the real data root fails: a missing payload is an error, never a skip.
4. A load-time comparison: in a subprocess the whole suite is LOADED (never run) with the flag set and with it unset, and the test ids carrying `__unittest_skip__`
   (method or class) must differ by exactly EXPECTED_GATED.

What remains uncaught: a skip that is neither a load-time mark nor a spelling of the flag, which is to say a runtime `SkipTest` that learns the flag by a means that avoids the
string `NO_VENDOR_FILES` and the helper (for example a name assembled from pieces at run time, or an environment scan). Check 2 stops the natural spellings and review stops the rest.
Checks 1 and 2 are static and give the same answer with the flag set or unset.
"""

import ast
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import vendor_files as vf  # noqa: E402

DECORATOR = "needs_vendor_files"
HELPER_MODULE = "vendor_files"
THIS_FILE = Path(__file__).resolve().name
EXEMPT = frozenset({"vendor_files.py", THIS_FILE})

R4A = "test_marketdata_r4a_inputs"
PACK = "test_performance_evidence_pack"
QUAL = "test_real_qualification"
EXPECTED_GATED = frozenset({
    f"{R4A}.A6AndRuling73Tests.test_2_the_files_are_the_ones_the_owner_confirmed",
    f"{R4A}.A6AndRuling73Tests.test_3_the_owners_record_attaches_all_three_levels_to_aapl_on_xnas_and_to_nothing_else",
    f"{R4A}.A6AndRuling73Tests.test_4_the_composite_record_observed_earlier_agrees_with_it",
    f"{R4A}.A6AndRuling73Tests.test_5_a_stored_composite_that_differs_attaches_nothing",
    f"{R4A}.A6AndRuling73Tests.test_6_a_share_class_that_differs_attaches_nothing_and_adds_no_second_row",
    f"{R4A}.A6AndRuling73Tests.test_7_a_share_class_with_nothing_stored_to_compare_still_attaches",
    f"{R4A}.A6AndRuling73Tests.test_8_the_memory_codes_attach_nothing_for_their_own_mic",
    f"{R4A}.A6AndRuling73Tests.test_9_the_uw_record_does_not_attach_to_a_listing_of_another_mic",
    f"{R4A}.A6AndRuling73Tests.test_10_the_data_root_builds_and_maps_the_payload_to_the_uw_manifest_only",
    f"{R4A}.A6AndRuling73Tests.test_11_two_manifests_of_one_payload_are_still_refused_before_any_file_is_read",
    f"{R4A}.DeliveredDecimalsTests.test_5_the_stored_aapl_file_passes_every_price_text_shows_exactly_four_decimals",
    f"{R4A}.FixingDateStatedTwiceTests.test_7e_the_two_stored_frankfurter_files_state_no_date_twice_so_nothing_on_disk_is_excluded",
    f"{PACK}.RealSliceTests.test_only_terms_attested_files_are_admitted_and_the_drafts_are_never_read",
    f"{PACK}.RealSliceTests.test_the_real_slice_builds_from_the_admitted_files_and_is_labelled_real_and_states_what_is_missing",
    f"{PACK}.RealSliceTests.test_an_unattested_source_is_refused_before_its_payload_is_used",
    f"{QUAL}.ConfirmationTableTests.test_the_table_equals_the_real_files",
})


def test_files() -> List[Path]:
    return sorted(p for p in HERE.rglob("*.py") if "__pycache__" not in p.parts)


# --- 1. the decorator on the methods ----------------------------------------------------------------------------------------------------------

def _is_gate(node: ast.expr) -> bool:
    return (isinstance(node, ast.Name) and node.id == DECORATOR) or (isinstance(node, ast.Attribute) and node.attr == DECORATOR)


def gated_ids():
    """Every `module.Class.test` carrying the decorator, in every test file; a decorated class or module-level function is reported by its own name so it can never match the pin."""
    found = set()
    for path in test_files():
        if path.name == "vendor_files.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if any(_is_gate(d) for d in node.decorator_list):
                    found.add(f"{path.stem}.{node.name}")
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(_is_gate(d) for d in item.decorator_list):
                        found.add(f"{path.stem}.{node.name}.{item.name}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(_is_gate(d) for d in node.decorator_list):
                found.add(f"{path.stem}.{node.name}")
    return found


# --- 2. no other reference to the flag or to the helper ---------------------------------------------------------------------------------------

def flag_problems(source: str, name: str = "<source>") -> List[str]:
    """Problems with how one test file refers to the flag or to the helper; empty when the file uses nothing or only the plain decorator on a `test*` method of a top-level class."""
    problems: List[str] = []
    if re.search(r"NO_VENDOR_FILES", source, re.IGNORECASE):
        problems.append(f"{name}: names the flag (FINWEB_NO_VENDOR_FILES); only vendor_files.py may")
    tree = ast.parse(source, filename=name)
    legitimate = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test"):
                    legitimate.update(id(d) for d in item.decorator_list if isinstance(d, ast.Name) and d.id == DECORATOR)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[-1] == HELPER_MODULE for a in node.names):
                problems.append(f"{name}:{node.lineno}: imports the helper module itself")
        elif isinstance(node, ast.ImportFrom):
            from_helper = bool(node.module) and node.module.split(".")[-1] == HELPER_MODULE
            names_helper = any(a.name == HELPER_MODULE for a in node.names)
            if names_helper:
                problems.append(f"{name}:{node.lineno}: imports the helper module itself")
            elif from_helper and not (node.level == 0 and node.module == HELPER_MODULE and [(a.name, a.asname) for a in node.names] == [(DECORATOR, None)]):
                problems.append(f"{name}:{node.lineno}: imports from the helper anything but the plain `{DECORATOR}`")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.split(".")[-1] == HELPER_MODULE:
            problems.append(f"{name}:{node.lineno}: names the helper module as a string (a dynamic import)")
        elif (isinstance(node, ast.Name) and node.id == DECORATOR) or (isinstance(node, ast.Attribute) and node.attr == DECORATOR):
            if id(node) not in legitimate:
                problems.append(f"{name}:{node.lineno}: `{DECORATOR}` used other than as a plain decorator on a test method of a top-level class")
    return problems


# --- 3. a missing payload is an error, never a skip -------------------------------------------------------------------------------------------

SKIP_NAMES = frozenset({"skipTest", "SkipTest", "skipIf", "skipUnless", "skip"})
ROOT_NAMES = frozenset({"DEFAULT_ROOT", "REAL_ROOT"})


def _identifiers(node: ast.AST) -> set:
    names = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
    return names


def _points_at_real_root(node: ast.AST, payload_names: set) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and (n.value == "marketdata" or "data/marketdata" in n.value):
            return True
    return bool(_identifiers(node) & (ROOT_NAMES | payload_names))


def payload_skip_problems(source: str, name: str = "<source>") -> List[str]:
    """A skip call (or decorator) in the same top-level class or function as a reference to the real data root, or to a module name built from it, is an existence check in disguise."""
    tree = ast.parse(source, filename=name)
    payload_names = set()  # module-level names whose value is built from the real data root (DATA, UW_PATH, ...)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None and _points_at_real_root(node.value, set()):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            payload_names.update(t.id for t in targets if isinstance(t, ast.Name))
    problems = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            skips = sorted(_identifiers(node) & SKIP_NAMES)
            if skips and _points_at_real_root(node, payload_names):
                problems.append(f"{name}:{node.lineno}: {node.name} uses {skips} and refers to the real data root")
        elif _identifiers(node) & SKIP_NAMES and _points_at_real_root(node, payload_names):
            problems.append(f"{name}:{node.lineno}: a module-level skip refers to the real data root")
    return problems


# --- 4. the load-time comparison --------------------------------------------------------------------------------------------------------------

_LOAD = r'''
import json, sys, unittest
root, start = sys.argv[1], sys.argv[2]
suite = unittest.defaultTestLoader.discover(start, top_level_dir=root)
def walk(s):
    for t in s:
        if isinstance(t, unittest.TestSuite):
            yield from walk(t)
        else:
            yield t
total, skipped, failed = 0, [], []
for t in walk(suite):
    total += 1
    if isinstance(t, unittest.loader._FailedTest):
        failed.append(t.id())
        continue
    method = getattr(t, t._testMethodName, None)
    if getattr(type(t), "__unittest_skip__", False) or getattr(method, "__unittest_skip__", False):
        skipped.append(t.id())
print("SKIPMARKS:" + json.dumps({"total": total, "skipped": sorted(skipped), "failed": sorted(failed)}))
'''


def load_skip_marks(flag_set: bool) -> dict:
    """Load (never run) the whole suite in a fresh interpreter; every FINWEB_* variable is removed, so the one flag is the only difference and no database is reached."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("FINWEB_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if flag_set:
        env[vf.FLAG] = "1"
    done = subprocess.run([sys.executable, "-c", _LOAD, str(ROOT), str(HERE)], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300)
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("SKIPMARKS:")]
    if done.returncode != 0 or len(lines) != 1:
        raise AssertionError(f"loading the suite failed (flag_set={flag_set}, exit {done.returncode}): {done.stderr[-2000:]}")
    return json.loads(lines[0][len("SKIPMARKS:"):])


def short(test_id: str) -> str:
    return test_id[len("tests.product."):] if test_id.startswith("tests.product.") else test_id


# --- tests ------------------------------------------------------------------------------------------------------------------------------------

class GatedSetIsPinnedTests(unittest.TestCase):
    def test_exactly_the_pinned_tests_are_gated(self):
        found = gated_ids()
        self.assertEqual(sorted(found - EXPECTED_GATED), [], "gated but not pinned: add it to EXPECTED_GATED as a reviewed change")
        self.assertEqual(sorted(EXPECTED_GATED - found), [], "pinned but no longer gated")

    def test_every_pinned_test_exists(self):
        for gid in sorted(EXPECTED_GATED):
            module, cls, name = gid.split(".")
            tree = ast.parse((HERE / f"{module}.py").read_text(encoding="utf-8"))
            (klass,) = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls]
            self.assertIn(name, [i.name for i in klass.body if isinstance(i, ast.FunctionDef)], gid)
            self.assertTrue(name.startswith("test"), gid)

    def test_no_test_file_refers_to_the_flag_or_the_helper_except_by_the_plain_decorator(self):
        problems = []
        for path in test_files():
            if path.name not in EXEMPT:
                problems += flag_problems(path.read_text(encoding="utf-8"), path.name)
        self.assertEqual(problems, [])

    def test_the_load_time_skip_marks_differ_by_exactly_the_pinned_set(self):
        unset, flagged = load_skip_marks(False), load_skip_marks(True)
        self.assertEqual((unset["failed"], flagged["failed"]), ([], []), "a test module failed to load")
        self.assertEqual(unset["total"], flagged["total"])
        self.assertGreater(unset["total"], 1000)  # the whole suite was loaded, not a corner of it
        before, after = {short(i) for i in unset["skipped"]}, {short(i) for i in flagged["skipped"]}
        self.assertEqual(sorted(before - after), [], "the flag UNskips a test")
        self.assertEqual(sorted(after - before - EXPECTED_GATED), [], "skipped under the flag but not pinned")
        self.assertEqual(sorted(EXPECTED_GATED - (after - before)), [], "pinned but not skipped under the flag")


class NoSkipOnMissingPayloadTests(unittest.TestCase):
    def test_no_test_file_skips_where_it_refers_to_the_real_data_root(self):
        problems = []
        for path in test_files():
            if path.name not in EXEMPT:
                problems += payload_skip_problems(path.read_text(encoding="utf-8"), path.name)
        self.assertEqual(problems, [])


class FlagSemanticsTests(unittest.TestCase):
    def test_only_the_exact_value_one_sets_the_flag(self):
        self.assertEqual(vf.FLAG, "FINWEB_NO_VENDOR_FILES")
        self.assertTrue(vf.vendor_files_absent({"FINWEB_NO_VENDOR_FILES": "1"}))
        for value in ("0", "", "true", "yes", " 1", "11"):
            self.assertFalse(vf.vendor_files_absent({"FINWEB_NO_VENDOR_FILES": value}), repr(value))
        self.assertFalse(vf.vendor_files_absent({}))

    def test_the_reason_names_the_flag_and_both_decisions(self):
        for text in ("FINWEB_NO_VENDOR_FILES=1", "PD-0027", "PD-0028"):
            self.assertIn(text, vf.REASON)

    def test_the_helper_never_looks_at_the_file_system(self):
        tree = ast.parse((HERE / "vendor_files.py").read_text(encoding="utf-8"))
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        self.assertFalse(attrs & {"exists", "is_file", "is_dir", "glob", "rglob", "iterdir", "stat", "read_bytes", "read_text"}, "no skip-if-missing logic")
        imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertFalse(imports & {"pathlib", "glob", "shutil"})


# The reviewer's bypass spellings (TVF-M1, TVF-L2), kept as source text. Each must be refused by the static checks; the load-time comparison is the second net for those that skip at
# load time.
_FLAG = "FINWEB_NO_VENDOR_FILES"
BYPASSES = {
    "alias": "from vendor_files import needs_vendor_files as nvf\nclass T:\n    @nvf\n    def test_a(self): pass\n",
    "rebinding": "from vendor_files import needs_vendor_files\ngate = needs_vendor_files\nclass T:\n    @gate\n    def test_a(self): pass\n",
    "inline skipIf on the env var": f"import os, unittest\nclass T:\n    @unittest.skipIf(os.environ.get('{_FLAG}') == '1', 'x')\n    def test_a(self): pass\n",
    "inline skipIf on the helper": "import unittest, vendor_files\nclass T:\n    @unittest.skipIf(vendor_files.vendor_files_absent(), vendor_files.REASON)\n    def test_a(self): pass\n",
    "helper through from-import of other names": "from vendor_files import vendor_files_absent, REASON\n",
    "helper through the package": "from tests.product import vendor_files\n",
    "helper through a string": "import importlib\nm = importlib.import_module('vendor_files')\n",
    "SkipTest in setUpModule": f"import os, unittest\ndef setUpModule():\n    if os.environ.get('{_FLAG}'):\n        raise unittest.SkipTest('x')\n",
    "SkipTest in setUpClass": "import unittest\nfrom vendor_files import vendor_files_absent\nclass T(unittest.TestCase):\n    @classmethod\n    def setUpClass(cls):\n        if vendor_files_absent():\n            raise unittest.SkipTest('x')\n",
    "skipTest in the body": "import unittest\nfrom vendor_files import vendor_files_absent\nclass T(unittest.TestCase):\n    def test_a(self):\n        if vendor_files_absent():\n            self.skipTest('x')\n",
    "assignment-applied on a method": "from vendor_files import needs_vendor_files\nclass T:\n    def test_a(self): pass\n    test_a = needs_vendor_files(test_a)\n",
    "assignment-applied on a class": "from vendor_files import needs_vendor_files\nclass C:\n    def test_a(self): pass\nC = needs_vendor_files(C)\n",
    "decorated class": "from vendor_files import needs_vendor_files\n@needs_vendor_files\nclass T:\n    def test_a(self): pass\n",
    "class nested in an if": "from vendor_files import needs_vendor_files\nif True:\n    class T:\n        @needs_vendor_files\n        def test_a(self): pass\n",
    "decorator on a module-level function": "from vendor_files import needs_vendor_files\n@needs_vendor_files\ndef test_a(): pass\n",
    "decorator on a non-test helper method": "from vendor_files import needs_vendor_files\nclass T:\n    @needs_vendor_files\n    def helper(self): pass\n",
    "decorator called": "from vendor_files import needs_vendor_files\nclass T:\n    @needs_vendor_files()\n    def test_a(self): pass\n",
}
SKIP_ON_PAYLOAD = {
    "is_file then skipTest": "import unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n    def test_a(self):\n        if not Path('data/marketdata/files/x').is_file():\n            self.skipTest('absent')\n",
    "skip through the data constant": "import unittest\nfrom pathlib import Path\nDATA = Path('x') / 'data' / 'marketdata'\nclass T(unittest.TestCase):\n    def test_a(self):\n        if not (DATA / 'files').exists():\n            raise unittest.SkipTest('absent')\n",
    "skip through the real slice root": "import unittest\nfrom performance_tools import real_slice\nclass T(unittest.TestCase):\n    @unittest.skipUnless(real_slice.DEFAULT_ROOT.exists(), 'x')\n    def test_a(self): pass\n",
    "module-level skip": "import unittest\nfrom pathlib import Path\nif not Path('data/marketdata/files').is_dir():\n    raise unittest.SkipTest('x')\n",
}
CLEAN = {
    "the plain decorator": "from vendor_files import needs_vendor_files\nclass T:\n    @needs_vendor_files\n    def test_a(self): pass\n",
    "a database skip": "import unittest\n@unittest.skipIf(True, 'no database')\nclass T(unittest.TestCase):\n    def test_a(self): pass\n",
    "no skip at all, reads the root": "from pathlib import Path\nDATA = Path('data') / 'marketdata'\nclass T:\n    def test_a(self): DATA.exists()\n",
}


class CheckersRefuseTheBypassesTests(unittest.TestCase):
    def test_every_bypass_spelling_is_refused_by_the_static_check(self):
        for label, source in BYPASSES.items():
            self.assertTrue(flag_problems(source, label), label)

    def test_every_skip_on_a_payload_spelling_is_refused(self):
        for label, source in SKIP_ON_PAYLOAD.items():
            self.assertTrue(payload_skip_problems(source, label), label)

    def test_the_plain_forms_are_not_refused(self):
        for label, source in CLEAN.items():
            self.assertEqual((flag_problems(source, label) if label == "the plain decorator" else []), [], label)
            self.assertEqual(payload_skip_problems(source, label), [], label)


if __name__ == "__main__":
    unittest.main()
