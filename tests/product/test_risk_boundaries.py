"""Import-boundary and hygiene checks for the risk package (tech plan 17.7.1), in the style of `test_performance_boundaries`.

Static, over the source text: `risk` is a pure deterministic package. It depends on stdlib (no clock, randomness, network, float, `math`), `domain`, `product_contract`, `performance` (its public spine) and the
analytics-facing `marketdata` modules; nothing below it imports it (`performance` never imports `risk`); it names no vendor and no reason code outside a future `states.py`; it reads no file except its own bundled
registry; it never reaches advisory, scenario, AI or execution capability (PRD 31, P1, P8).
"""

import ast
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_marketdata_boundaries import CLOCK_CALLS, FORBIDDEN_EVERYWHERE_IN_PRODUCT, VENDOR_WORDS, imports_of, under  # noqa: E402

RISK = sorted((SRC / "risk").glob("*.py"))
MARKETDATA_OK = {"contracts", "manifest", "canonical", "port", "conventions", "calendars", "states"}
PERFORMANCE_OK = {"results", "numerics", "series", "grid", "manifest", "states", "periods"}
ENGINE_ONLY = {"engine", "conventions", "inputs", "ledger_view", "current"}  # the orchestration (`risk/engine.py`) alone may reach the portfolio leg, its convention set, the suppressions, the ledger digest and (Current mode) the as-of date rule
FORBIDDEN_RISK_STDLIB = FORBIDDEN_EVERYWHERE_IN_PRODUCT | {"math", "statistics", "cmath", "numbers", "os", "sys", "subprocess", "glob", "shutil", "tempfile", "pickle"}
CAPABILITY_WORDS = ("ai", "advisory", "scenario", "execution", "order", "broker", "llm")


class RiskBoundaryTests(unittest.TestCase):
    def test_the_package_exists_with_the_cp4b_2_and_cp4c_modules(self):
        self.assertTrue({"risk_free", "sqrt", "registry", "states", "stats", "results", "single", "benchmark", "manifest", "engine"} <= {p.stem for p in RISK})

    def test_imports_are_stdlib_domain_product_contract_the_public_performance_spine_and_analytics_marketdata_only(self):
        stdlib = set(sys.stdlib_module_names)
        for path in RISK:
            for name in imports_of(path):
                root = name.split(".")[0]
                if root == "risk" or root in ("domain", "product_contract"):
                    continue
                if root == "performance":
                    parts = name.split(".")
                    allowed = PERFORMANCE_OK | (ENGINE_ONLY if path.name == "engine.py" else set())
                    self.assertTrue(len(parts) == 1 or parts[1] in allowed, f"{path.name} imports {name}")
                    continue
                if root == "marketdata":
                    parts = name.split(".")
                    self.assertTrue(len(parts) == 1 or parts[1] in MARKETDATA_OK, f"{path.name} imports {name}")
                    continue
                self.assertIn(root, stdlib - FORBIDDEN_RISK_STDLIB, f"{path.name} imports {name}")

    def test_no_persistence_service_adapter_vendor_tool_or_capability_import(self):
        for path in RISK:
            names = imports_of(path)
            for banned in ("persistence", "corporate_actions_service", "performance_service", "performance_tools", "risk_service", "risk_tools", "marketdata.adapters", "marketdata.ingest",
                           "marketdata.files", "marketdata.store", "marketdata.verification", "marketdata.profiles", "marketdata.market11", "marketdata_tools"):
                self.assertFalse(under(names, banned), f"{path.name} imports {banned}")
            for n in names:
                self.assertFalse(any(part in CAPABILITY_WORDS for part in n.lower().split(".")), f"{path.name} imports {n}")
            text = path.read_text(encoding="utf-8").lower()
            for word in VENDOR_WORDS:
                self.assertNotIn(word, text, f"{path.name} mentions {word}")

    def test_nothing_below_risk_imports_it_and_performance_never_does(self):
        for sub in ("domain", "marketdata", "persistence", "product_contract", "corporate_actions_service", "marketdata_tools", "performance", "performance_service"):
            for path in sorted((SRC / sub).rglob("*.py")):
                self.assertFalse(under(imports_of(path), "risk"), f"{sub}/{path.name} imports risk")

    def test_no_reason_code_enum_is_named_here_yet(self):
        # when `risk/states.py` exists it is the only module that may name `ReasonCode`; until then none does (reason codes arrive as TEXT through `performance.states` constants)
        for path in RISK:
            if path.name == "states.py":
                continue
            self.assertNotIn("ReasonCode", path.read_text(encoding="utf-8"), path.name)

    def test_no_float_no_python_rounding_no_clock_no_decimal_context_no_open(self):
        for path in RISK:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant):
                    self.assertNotIsInstance(node.value, float, f"{path.name}: a float literal")
                if isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "float", f"{path.name} names float")
                if isinstance(node, ast.Call):
                    f = node.func
                    name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                    self.assertNotIn(name, {"round", "quantize", "getcontext", "setcontext", "localcontext", "float", "eval", "exec", "open"} | CLOCK_CALLS, f"{path.name} calls {name}")
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, {"ROUND_HALF_UP", "ROUND_DOWN", "ROUND_UP", "ROUND_FLOOR", "ROUND_CEILING", "ln", "exp", "log10", "power", "sqrt"}, f"{path.name}.{node.attr}")

    def test_only_the_registry_reads_a_file_and_only_its_own_bundled_one(self):
        for path in RISK:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            reads = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in {"read_bytes", "read_text", "write_bytes", "write_text", "mkdir", "unlink"}]
            if path.name == "registry.py":
                self.assertEqual([n.attr for n in reads], ["read_bytes"])  # one read, nothing written
            else:
                self.assertEqual(reads, [], path.name)
        text = (SRC / "risk" / "registry.py").read_text(encoding="utf-8")
        self.assertIn('Path(__file__).with_name("risk_registry.json")', text)

    def test_a_vendor_adjusted_series_is_unreachable(self):
        for path in RISK:
            text = path.read_text(encoding="utf-8")
            for banned in ("AdjustedQuote", "UnresolvedAdjustedQuote", "adjusted_series", "marketdata.verification"):
                self.assertNotIn(banned, text, f"{path.name} mentions {banned}")

    def test_the_hypothetical_portfolio_never_goes_through_here(self):
        # P8: nothing in risk names a scenario or hypothetical state; the engine computes ACTUAL portfolios only
        for path in RISK:
            self.assertNotIn("HYPOTHETICAL", path.read_text(encoding="utf-8").upper().replace("HYPOTHETICAL AND ACTUAL", ""), path.name)

    def test_only_the_orchestration_reaches_the_portfolio_leg_and_nothing_else_imports_the_engine(self):
        for path in RISK:
            text = path.read_text(encoding="utf-8")
            if path.name != "engine.py":
                self.assertNotIn("performance.engine", text, path.name)
                self.assertNotIn("from performance import engine", text, path.name)
            for banned in ("compute_window", "compute(", "compute_gains", "compute_attribution", "reproduce("):
                self.assertNotIn(banned, text, f"{path.name} mentions {banned}")  # the one entry it needs is the series and the TWR between two dates

    def test_a_metric_is_made_in_one_place_and_the_drawdown_rule_in_one_function(self):
        # Ruling 1.3: one function owns the peak rule; a second implementation (a chart, an insight) calls it
        defs = [p.name for p in RISK if "def max_drawdown" in p.read_text(encoding="utf-8")]
        self.assertEqual(defs, ["stats.py"])
        builders = [p.name for p in RISK if "RiskMetric(" in p.read_text(encoding="utf-8").replace("class RiskMetric", "")]
        self.assertEqual(builders, ["single.py"])  # `MetricBuilder.build` is the one place a RiskMetric is made

    def test_no_risk_module_reads_a_wall_clock_or_a_random_source_or_the_environment(self):
        for path in RISK:
            names = imports_of(path)
            for banned in ("time", "datetime.datetime.now", "random", "secrets", "os", "uuid.uuid4"):
                self.assertNotIn(banned, names, f"{path.name} imports {banned}")
            text = path.read_text(encoding="utf-8")
            for needle in (".now(", ".today(", "uuid4", "environ", "PYTHONHASHSEED"):
                self.assertNotIn(needle, text, f"{path.name} uses {needle}")


def risk_hashes():
    import hashlib  # noqa: PLC0415

    return {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in RISK}


#: the source of the risk engine, pinned like `performance`'s `ENGINE_PINS`: a computation change cannot be silent. Any change to a `risk/*.py` file needs a new `RISK_ENGINE_ID` in `risk/engine.py`, and these re-recorded.
RISK_ENGINE_PINNED_ID = "risk/cp4i-0.3"  # cp4i-0.3 (2026-10-25, F1 R4a label increment, market-data/1.16 section 11 item 35): the registry the engine loads is risk/1.11, a label re-issue (the 1.15 re-issue's twin: no entry, no number); the ONLY source changes are `registry.IMPLEMENTED_REGISTRY_ID` and this id with their comments, re-recorded below as `registry` (e14e8b02... to 8844f2c4...) and `engine` (2ef3c75a... to 8766b2e4...). cp4i-0.2 was: (2026-10-24, review M-2 of the market-data/1.15 label move): the registry the engine loads is risk/1.10, a label re-issue of risk/1.9 (Ruling 9.2 (1.10)) that changes no entry and no number; the ONLY source changes are `registry.IMPLEMENTED_REGISTRY_ID` (and its comment) and this id, re-recorded below as `registry` and `engine` (`registry.py` says that a newer registry is a new engine version). cp4i-0.1 was: CP4I (risk/1.9, market-data/1.14, tech plan 17.25): declared precision, which side's stated payment applies. CP4H (risk/1.8, tech plan 17.24): a foreign-currency dividend converted at the ECB fixing of its ex-date. CP4G (risk/1.7): the identity of a corporate action across sources, a foreign-currency dividend refused, the per-source precision bound. (Before: CP4F (final review fix round, risk/1.6; tech plan 17.23): refused-window causes, zero-capital active return, proxy identity and chain breaks, source binding, Current-mode fixing boundary. (CP4e: `relative.py` (the active return over a window with a zero-capital period no longer asserts; RA-1 NOT_COMPUTABLE there)
RISK_ENGINE_PINS = {
    "__init__": "7f3ede6ea517ba0ba35f0dc33ca0d89d3541d6f219f6f1d63bbd3a199cf41fa1",
    "benchmark": "507ebdecefabf754d06dd293ad9bc4ba9a822585d22b92d67dfee9494c2ee415",
    "comparability": "c42bf7baef64300a129cc543e7ed21e9aa62ede487954f2865fb429d16aca2ff",
    "engine": "8766b2e48c371578c55d54fcff44e59e9e24ed10f10304d625684b1da13d6ad4",
    "levels": "e6982874f131639b9801fb3f54ea27ffcad98ab75e63699adafbb586067acb64",
    "relative": "afa5d1406195d7094052af18fad85b094e225b3fdb93d9000a5ace8a0f6fa505",
    "manifest": "556c3a890160fc211d00edf1b75a168cf4e64c465249129729f82e629a3c0411",
    "registry": "8844f2c48f8ccff465b5c1d3b9218858274319bd8b316b654b02f9657c7252ac",
    "results": "3f2b4ef9aa04acadbd6244201d5d5a23f54081a3f7e6994b1fb1b60afe6dfafd",
    "risk_free": "cc19c4abd8f0c337b3f8a8b65fa7de5964547d773bd2299098ccd5c2c61276fb",
    "single": "95d823ea2d072f0f30b812efb34975a7e0a48f6fcefd9515f5a6f497bfede33e",
    "sqrt": "13d8c30dc12bc327cc1d822a749728e8a2329984eb88e11cfd0e4f562e6cc576",
    "states": "dea31cc4a8b4ee00816f564c86b1bbb42da91d2c9c7dba8e6e75e54ceb6f37b0",
    "stats": "5e53e343334c493734e3838d64f27538fd7c72d8aae84386111e4bb8b5c8ecf6",
}


class RiskEnginePinTests(unittest.TestCase):
    def test_every_risk_module_matches_its_committed_pin_and_the_pinned_engine_id_is_the_engines(self):
        sys.path.insert(0, str(SRC))
        from risk.engine import RISK_ENGINE_ID  # noqa: PLC0415

        self.assertEqual(RISK_ENGINE_ID, RISK_ENGINE_PINNED_ID)
        real = risk_hashes()
        moved = sorted(n for n in set(real) | set(RISK_ENGINE_PINS) if real.get(n) != RISK_ENGINE_PINS.get(n))
        self.assertEqual(moved, [], "a risk module changed: that is a computation change; bump RISK_ENGINE_ID in risk/engine.py and update RISK_ENGINE_PINS in the same commit")

    def test_the_check_can_fail(self):
        real = risk_hashes()
        self.assertTrue(real)
        changed = dict(real, stats="0" * 64)
        self.assertEqual(sorted(n for n in set(changed) | set(real) if changed.get(n) != real.get(n)), ["stats"])


class RiskServiceBoundaryTests(unittest.TestCase):
    SERVICE = sorted((SRC / "risk_service").glob("*.py"))

    #: what the I/O edge may import (CP4d: it reads the ledger and the selection log through their stores and composes the engine): never a driver, never a clock, never a file write
    EDGE_ROOTS = {"domain", "risk", "pathlib", "typing", "__future__", "performance", "performance_service", "persistence", "corporate_actions_service", "marketdata", "product_contract", "risk_service"}

    def test_the_edge_package_has_the_service_the_groups_the_default_view_and_the_catalog_reader(self):
        self.assertTrue({"__init__", "catalogs", "service", "groups", "default_view"} <= {p.stem for p in self.SERVICE})
        for path in self.SERVICE:
            text = path.read_text(encoding="utf-8")
            for needle in (".now(", ".today(", "psycopg", "uuid4", "random"):
                self.assertNotIn(needle, text, f"{path.name} uses {needle}")

    def test_the_edge_package_exists_and_reads_only_the_catalogs(self):
        self.assertTrue({"__init__", "catalogs"} <= {p.stem for p in self.SERVICE})
        text = (SRC / "risk_service" / "catalogs.py").read_text(encoding="utf-8")
        self.assertIn('"BENCHMARKS.json"', text)
        self.assertIn('"RISK_FREE.json"', text)
        for path in self.SERVICE:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
            self.assertFalse(attrs & {"write_bytes", "write_text", "mkdir", "unlink", "rename", "touch"}, path.name)  # the files are the main session's: never written
            for name in imports_of(path):
                root = name.split(".")[0]
                self.assertTrue(root in self.EDGE_ROOTS or root in sys.stdlib_module_names, f"{path.name} imports {name}")

    def test_the_pure_packages_never_import_the_edge(self):
        for sub in ("domain", "marketdata", "persistence", "product_contract", "performance", "risk"):
            for path in sorted((SRC / sub).rglob("*.py")):
                self.assertFalse(under(imports_of(path), "risk_service"), f"{sub}/{path.name} imports risk_service")

    def test_the_catalog_rules_live_in_the_domain_and_the_domain_has_no_clock(self):
        text = (SRC / "domain" / "catalogs.py").read_text(encoding="utf-8")
        for needle in (".now(", ".today(", "open(", "read_text", "read_bytes", "random", "uuid4"):
            self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
