"""Import-boundary and hygiene checks for CP2 (Tech Plan §15.1, §15.4, §15.9).

Static, over the source text: analytics must not depend on adapters, vendors or the
human-run download tool; adapters are pure translators; nothing in product code reads a
clock, uses randomness, touches the network or borrows a reason code; the market-data layer
never imports persistence (F8-A: detect and flag only; PD-0030 §2 lands F8-B later).
"""

import ast
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

# C2-11 (CP2 review of 39733e9): the list missed the UPSTREAM names `sina` and `eastmoney` and the ECB file's own name.
# (`ecb` alone is not here: the conventions DEFINE the fixing as the ECB reference rate, so convention modules must name the
# publisher; the exit test checks the word `ecb` only in the consumer-facing modules, which have no business with it.)
VENDOR_WORDS = ("akshare", "baostock", "tushare", "yfinance", "alphavantage", "alpha vantage",
                "frankfurter", "cfets", "openfigi", "pandas", "sina", "eastmoney", "eurofxref")
FORBIDDEN_EVERYWHERE_IN_PRODUCT = {"random", "secrets", "time", "socket", "ssl", "http", "urllib",
                                   "requests", "subprocess", "multiprocessing", "asyncio", "sqlite3"}
CLOCK_CALLS = {"now", "utcnow", "today", "uuid4", "uuid1", "time", "monotonic", "perf_counter"}


def imports_of(path: Path):
    """Every module name a file imports, including `from pkg import module` forms."""
    names = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def py_files(sub: str):
    return sorted((SRC / sub).rglob("*.py"))


def top(name: str) -> str:
    return name.split(".")[0]


def under(names, prefix: str):
    return {n for n in names if n == prefix or n.startswith(prefix + ".")}


class AdapterPurityTests(unittest.TestCase):
    ALLOWED_PROJECT = {"domain.currency", "domain.ledger", "domain.field_validation",
                       "marketdata.contracts", "marketdata.manifest", "marketdata.canonical",
                       "marketdata.adapters.base", "marketdata.adapters.daily_csv", "marketdata.precision",
                       "marketdata.profiles"}

    def test_adapters_import_only_stdlib_and_the_contract_modules(self):
        files = [p for p in py_files("marketdata/adapters") if p.name != "__init__.py"]
        self.assertTrue(files)
        stdlib = set(sys.stdlib_module_names)
        for path in files:
            for name in imports_of(path):
                root = top(name)
                if root in ("domain", "marketdata"):
                    # `from marketdata.contracts import X` also yields marketdata.contracts.X
                    ok = any(name == a or name.startswith(a + ".") for a in self.ALLOWED_PROJECT) or name in (
                        "marketdata", "marketdata.adapters", "domain")
                    self.assertTrue(ok, f"{path.name} imports {name}")
                else:
                    self.assertIn(root, stdlib - FORBIDDEN_EVERYWHERE_IN_PRODUCT - {"os", "pathlib", "shutil",
                                                                                   "tempfile", "glob"},
                                  f"{path.name} imports {name}")

    def test_adapters_do_not_open_files_or_evaluate_code(self):
        for path in py_files("marketdata/adapters"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"open", "eval", "exec", "compile", "__import__", "input"},
                                     f"{path.name} calls {node.func.id}")

    def test_no_adapter_imports_another_adapter_or_a_vendor_library(self):
        for path in py_files("marketdata/adapters"):
            names = imports_of(path)
            for other in under(names, "marketdata.adapters"):
                self.assertTrue(other == "marketdata.adapters" or other.startswith(
                    ("marketdata.adapters.base", "marketdata.adapters.daily_csv")), f"{path.name} imports {other}")
            for word in VENDOR_WORDS:
                self.assertFalse(any(word in n.lower() for n in names), f"{path.name} imports {word}")


class AnalyticsIndependenceTests(unittest.TestCase):
    # the modules an analytics consumer reaches; none may know any adapter, vendor, file or tool
    ANALYTICS = ("consumption", "port", "conventions", "store", "contracts", "canonical", "manifest",
                 "resolver", "market11", "calendars", "states")

    def test_analytics_modules_import_no_adapter_ingestion_file_or_tool(self):
        for name in self.ANALYTICS:
            names = imports_of(SRC / "marketdata" / f"{name}.py")
            for banned in ("marketdata.adapters", "marketdata.ingest", "marketdata.files", "marketdata_tools"):
                self.assertFalse(under(names, banned), f"{name}.py imports {banned}")

    def test_analytics_modules_name_no_vendor(self):
        for name in ("consumption", "port", "conventions", "store", "resolver", "contracts", "market11",
                     "calendars", "states"):
            text = (SRC / "marketdata" / f"{name}.py").read_text(encoding="utf-8").lower()
            for word in VENDOR_WORDS:
                self.assertNotIn(word, text, f"{name}.py mentions {word}")

    def test_domain_persistence_and_product_contract_know_no_adapter_vendor_or_tool(self):
        for sub in ("domain", "persistence", "product_contract"):
            for path in py_files(sub):
                names = imports_of(path)
                for banned in ("marketdata.adapters", "marketdata.ingest", "marketdata_tools"):
                    self.assertFalse(under(names, banned), f"{sub}/{path.name} imports {banned}")
                for word in VENDOR_WORDS:
                    self.assertFalse(any(word in n.lower() for n in names), f"{sub}/{path.name}: {word}")

    def test_a_vendor_adjusted_series_is_verification_only_and_unreachable_from_analytics(self):
        """Ruling 2.5: the consumer, the port and the price lookups cannot read an adjusted series."""
        for name in ("consumption", "port", "conventions", "states"):
            text = (SRC / "marketdata" / f"{name}.py").read_text(encoding="utf-8")
            for banned in ("AdjustedQuote", "UnresolvedAdjustedQuote", "adjusted_series", "marketdata.verification"):
                self.assertNotIn(banned, text, f"{name}.py mentions {banned}")
        import marketdata.contracts as contracts
        self.assertFalse(issubclass(contracts.AdjustedQuote, contracts.QuoteObservation))
        self.assertFalse(issubclass(contracts.UnresolvedAdjustedQuote, contracts.UnresolvedQuote))
        port = (SRC / "marketdata" / "port.py").read_text(encoding="utf-8")
        self.assertNotIn("adjusted", port.lower())

    def test_the_consumer_depends_only_on_the_port_the_contracts_and_replay_results(self):
        names = imports_of(SRC / "marketdata" / "consumption.py")
        allowed = {"domain.currency", "domain.replay", "marketdata.conventions", "marketdata.contracts",
                   "marketdata.manifest", "marketdata.port", "product_contract.metric_state"}
        for n in names:
            if top(n) in ("domain", "marketdata", "product_contract"):
                self.assertTrue(any(n == a or n.startswith(a + ".") for a in allowed), n)


class ToolBoundaryTests(unittest.TestCase):
    def test_nothing_imports_the_download_tool(self):
        for path in sorted(SRC.rglob("*.py")):
            if "marketdata_tools" in path.parts:
                continue
            self.assertFalse(under(imports_of(path), "marketdata_tools"), str(path))

    def test_the_tool_imports_only_stdlib_and_a_few_marketdata_modules_and_no_vendor_at_module_level(self):
        stdlib = set(sys.stdlib_module_names)
        allowed = {"domain.currency", "marketdata.canonical", "marketdata.contracts", "marketdata.files",
                   "marketdata.manifest"}
        for path in py_files("marketdata_tools"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:  # module level only: vendor imports must be lazy
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    mods = [node.module]
                for m in mods:
                    if top(m) in ("domain", "marketdata"):
                        self.assertIn(m, allowed, f"{path.name}: {m}")
                    else:
                        self.assertIn(top(m), stdlib, f"{path.name} imports {m} at module level")


class ProductHygieneTests(unittest.TestCase):
    def test_no_clock_randomness_or_network_in_the_market_data_layer(self):
        for path in py_files("marketdata"):
            names = imports_of(path)
            for n in names:
                self.assertNotIn(top(n), FORBIDDEN_EVERYWHERE_IN_PRODUCT, f"{path.name} imports {n}")
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, CLOCK_CALLS, f"{path.name}: .{node.func.attr}()")

    def test_the_market_data_layer_never_touches_persistence_or_appends_to_the_ledger(self):
        for path in py_files("marketdata"):
            names = imports_of(path)
            self.assertFalse(under(names, "persistence"), f"{path.name} imports persistence")
            for n in names:
                self.assertNotIn("append", n.lower(), f"{path.name} imports {n}")

    def test_only_the_states_module_names_a_reason_code(self):
        """Ruling 4.4 / PD-0030: SOURCE_CONFLICT and MISSING_PRICE_HISTORY are used in one place,
        exactly as the table says; no other market-data module names or borrows a code."""
        for path in py_files("marketdata"):
            if path.name == "states.py":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("ReasonCode", text, path.name)
            self.assertNotIn("reason_code", text, path.name)

    def test_no_float_annotations_in_market_data_contracts(self):
        tree = ast.parse((SRC / "marketdata" / "contracts.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                self.assertNotEqual(node.id, "float")


if __name__ == "__main__":
    unittest.main()
