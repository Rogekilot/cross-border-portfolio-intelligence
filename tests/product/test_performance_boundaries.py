"""Import-boundary and hygiene checks for the performance engine (tech plan 16.1), in the style of the CP2 tests.

Static, over the source text: `performance` is a pure deterministic engine module. It depends only on stdlib (no clock,
randomness, network, float, `math`), `domain`, `product_contract` and the analytics-facing `marketdata` modules; nothing
below it imports it; it names no vendor and no reason code outside `states.py`; it never rounds with a literal; it never
reaches advisory, scenario, AI or execution capability (PRD 31, P1, P8).
"""

import ast
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_marketdata_boundaries import CLOCK_CALLS, FORBIDDEN_EVERYWHERE_IN_PRODUCT, VENDOR_WORDS, imports_of, under  # noqa: E402

PERF = sorted((SRC / "performance").rglob("*.py"))
PUBLIC = {"engine", "results", "manifest", "conventions", "inputs", "periods", "series"}
MARKETDATA_OK = {"contracts", "manifest", "canonical", "port", "conventions", "calendars", "states", "consumption"}
FORBIDDEN_PERF_STDLIB = FORBIDDEN_EVERYWHERE_IN_PRODUCT | {"math", "statistics", "cmath", "numbers"}
CAPABILITY_WORDS = ("ai", "advisory", "scenario", "execution", "order", "broker", "llm")


# CP3-6 (review of 0059d64): tech plan 16.2 says the engine's source is pinned, like the CP2 analytics modules (`ANALYTICS_PINS` in test_marketdata_cp2c2_exit). This is
# that pin: the SHA-256 of every module of the `performance` package as it stood when this test was last reviewed (recorded 2026-10-01, CP3 midpoint fix round,
# `ENGINE_ID` below). A change to any engine module changes a hash here and fails the test, which names the module; the change is then made in the SAME commit as the
# new pin and a bump of `ENGINE_ID` in `performance/manifest.py`, where review sees both as changed lines. Adding a module without a pin fails as well.
#
# THE COUPLING (re-check note, review section 29.2): updating the hashes WITHOUT bumping `ENGINE_ID` must fail. `ENGINE_PIN_HISTORY` is the ordered record of
# `ENGINE_ID -> digest of the pin set recorded under that id`. The tests require: the current `ENGINE_ID` is the LAST entry; the digest of `ENGINE_PINS` is that entry's;
# no two ids share a digest (an id bump with unchanged pins, or pins changed back, is refused). So a new set of hashes needs a new id in `manifest.py` AND a new entry
# here; editing the last entry's digest to hide a change is a visible edit of history, which review sees.
ENGINE_PINNED_ID = "performance/cp4-0.16"
ENGINE_PINS = {
    "__init__": "df71ff0c1a71ae2c43cf000a6d2e9160d5366c692ac02667bc94f99695311260",
    "attribution": "9f547bfe8f5763c88c9e5656939f92ac4475e7af57c16049fe55007c6e415d15",
    "conventions": "61d92ef8096c32774f02bb6158da5811f9898feb1a5acffb2b67f899ebc26004",
    "current": "342842530548ab494a1bbe8cfddb368d7e630063f50c59988258b3dddf9d5825",
    "engine": "8b258b1cae0c90184f492aab4213a1adab7918874d3db316457ed207c23c602e",
    "flows": "4b2095210d06da58145bd65be22bc7f922e73053bb5a7eebd8340634fc32eb92",
    "gains": "3d12160f12a3acaaca7268166e4a421817c17bb99dc00fe707ff767cff6a5057",
    "grid": "cb4e173671a03a633fa6c9c8751913c07e8ce509a4ab74030f879a60cf2acd4d",
    "identity": "7a36476e4f2da7718bba6b883e562a7b7cb05f24b3a0f51507827a1c5034cf59",
    "inputs": "759d873b72e9f994b61de5cd178d252a0283066543a941bef052fd4594323cfa",
    "ledger_view": "cfae832c3435384374546ed4a780dc3d39ce0199ac7ae959ae5ec11292d0dec8",
    "lines": "9b1dd4b52b132abc4f00ee2568793c535263fa66839f406acdc87c4a5b45b526",
    "manifest": "2713625c04b1c0d7419cf41ffe87ec5ea10ee96346e86f5a2b929bef1eb2b044",
    "numerics": "625010ae1e2353ffaca119957598b5c4f0ff3e87e2510daca27b2d3572afa48a",
    "periods": "537403114eedfa48b3e8f9ecba4ca3eb9d0e28d5603d777f891d88daf7e930bc",
    "registry": "10e8e51c20e64e3b8ea58288fbd377e741b586e23707683b690c956c8dad7fec",
    "results": "9500054d4e662a1795427673c8032ce0b078546b8aafeeea0fdecfc4ba68e6e3",
    "returns": "e890ceff1afb05faa608dd6812925ea96eec509102cfc3ea66612118427ecb59",
    "rounding": "d2a332f95d27df52c59af72602a20e9f0860b9e98ad9b6531028284999dc4144",
    "series": "40559db23d8385ea8b887199adf7713c98042caf5f22d63e22d7d9b07ea71bd3",
    "states": "b287f2a8834dbfda475e1ee92512a68e95b0f033839d8ed8db04cdde59359428",
    "taint": "17edc241da18d6efa371904db4cc7e9c435784d879bde562f782e3816bcbc6ca",
    "valuation": "9450e6977a82a0e44861e92871ef85ece9dfec6466d6b325544a143553507d71",
}
ENGINE_PIN_HISTORY = {
    "performance/cp3-0.3": "f36fd38526d8624b6e96bb365c01503a24e85fd4a17d96f832875c61be34019f",   # the CP3 midpoint fix round (reviewed in section 29)
    "performance/cp3c-0.4": "d3a9e953d16c6c010650e17744a9b04d09b7001c1a49edfd71a25a5ced069e3c",  # the re-check fixes and CP3c
    "performance/cp3d-0.5": "23f9cd086e9178707d532459143f38d7d23c8d0724ea6cdb9d2915656d6e42c6",  # CP3d: FIFO lots, gains, taint by lot book (performance/1.8, ledger-replay/1.5)
    "performance/cp3e-0.6": "f262c1a2d2a879e09eb03bb0789acf12f4adffb3e3cff167cc4793bd80f44109",  # CP3e: attribution, identities I-2/I-3/I-4/I-9, metric-id registry (performance/1.8)
    "performance/cp3f-0.7": "df2bbf63060a46fa400f570e223fc8fbbc45783701970e5c3f9fc7bd4c8f5f3c",  # CP3f: performance/1.9 (last_print_date, apportioned breakdowns), reproduce for gains and attribution, Current-mode manifests
    "performance/cp3f-0.8": "747beb9901918cf7d3848ce3c1fb45adec4b4520cba7fcdfaf877737860e6708",  # CP3f fix round: performance/1.10 (one grouping key per contribution)
    "performance/cp3f-0.9": "3e83391737fcc839a5fa3ca2af8f2b241483f34866137786c8f705b7dcbdd836",  # final-review fixes: attribution guards (CP3-14), stable Carino kappa (CP3-16), FX lineage notes (CP3-13)
    "performance/cp3f-0.10": "44c5465bded1a86ee4054c9669ddf65fb31f6711e6350effa0473b9845c2b9ef",  # section 31 fixes: the receiving leg of a tainted transfer carries the taint (CP3-18); kappa docstring
    "performance/cp4-0.11": "37c42ae11b21f97d3f0458272fe490c566c78b0f9563d846611547021cbc8726",  # CP4 part A (tech plan 16.24), one id for the whole round: presented money carries exactly its minor units (Ruling 2.2; to_decimal_money); performance/1.11 (minor-units/1.1, ten rows CONFIRMED, conformant); market-data/1.11 slot ids
    "performance/cp4-0.12": "1bd12ea3e3630a9a7461bccd460d37d5a69f1a6bb97f4b5a52bf6ed35b3ca129",  # CP4 part A round 2 (tech plan 16.25): performance/1.12 (D_c(t) tests events dated D; money FACTS padded to the minor unit; source_registry_digest; Current-mode refusals record t, M, M_t)
    "performance/cp4-0.13": "2a10244d0d69978ac91d62b235e0ece6c86bdab99f26bb040d3bffb922972b03",  # CP4 part A round 3 (tech plan 16.26): valuation_mode CURRENT_AT_INSTANT with the manifest invariants; registry digest never empty (fails closed); D_c(t) tests every money field; refusals carry both digests
    "performance/cp4-0.14": "b8986f714e0410b8859fc3ba9a4cc0185a27cb8c77d293a1ddab417a9f1dcfbb",  # CP4b-1 (tech plan 17.13): the periodic return series (series.py, compute_return_series), additive WindowUsed.requested_*; no CP3 computation changed (test_performance_cp3_byte_identity)
    "performance/cp4-0.15": "6a1602d4477963b23626c577fe5d8f861004b0308f4087e3de2d485975ab4e5c",  # CP4b-2 (tech plan 17.15): series conformed to risk/1.1 section 2 (grid window with declared stubs, no clipping, MAX_AVAILABLE, zero-capital PERIOD, no merging), the new grid module
    "performance/cp4-0.16": "2b24787124ccdfd3954fa9ad6809cf022b0c96950757808eaf11b24ea74577c3",  # CP4c (tech plan 17.16): `compute_twr_between` (the TWR of two dates from the TWR engine directly, for RD-1); a MAX_AVAILABLE refusal declares the request's base `B` (cp4_golden part 3 R8-K1, R11-X1)
}


def pins_digest(pins):
    import hashlib  # noqa: PLC0415
    import json  # noqa: PLC0415

    return hashlib.sha256(json.dumps(pins, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def engine_hashes():
    import hashlib  # noqa: PLC0415

    return {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in PERF}


def pin_history_problems(history, engine_id, pins):
    """Why the ENGINE_ID / pin coupling is broken (empty when sound): the current id must be the last entry, its digest must be the pins', and no digest may repeat."""
    problems = []
    ids = list(history)
    if not ids or ids[-1] != engine_id:
        problems.append(f"ENGINE_ID {engine_id!r} is not the last entry of ENGINE_PIN_HISTORY")
    elif history[engine_id] != pins_digest(pins):
        problems.append("ENGINE_PINS changed without a new ENGINE_ID: bump ENGINE_ID in performance/manifest.py and add its entry to ENGINE_PIN_HISTORY")
    if len(set(history.values())) != len(history):
        problems.append("two ENGINE_IDs record the same pin set: an id bump with no change, or a change reverted")
    return problems


def unpinned_engine_changes(hashes):
    """The engine modules whose hash is not the committed pin, plus any module with no pin, plus any pin with no module (empty when nothing moved)."""
    return sorted(n for n in set(hashes) | set(ENGINE_PINS) if hashes.get(n) != ENGINE_PINS.get(n))


class EnginePinTests(unittest.TestCase):
    def test_every_engine_module_matches_its_committed_pin_and_the_pinned_engine_id_is_the_manifests(self):
        sys.path.insert(0, str(SRC))
        from performance.manifest import ENGINE_ID  # noqa: PLC0415

        self.assertEqual(unpinned_engine_changes(engine_hashes()), [],
                         "an engine module changed: that is a computation change; bump ENGINE_ID in performance/manifest.py and update ENGINE_PINS in the same commit")
        self.assertEqual(ENGINE_ID, ENGINE_PINNED_ID)
        self.assertEqual(pin_history_problems(ENGINE_PIN_HISTORY, ENGINE_ID, ENGINE_PINS), [])

    def test_updating_the_pins_without_bumping_the_engine_id_fails_and_so_does_an_empty_bump(self):
        # the review's probe: new hashes under the SAME id
        edited = dict(ENGINE_PINS, returns="0" * 64)
        self.assertIn("ENGINE_PINS changed without a new ENGINE_ID", " ".join(pin_history_problems(ENGINE_PIN_HISTORY, ENGINE_PINNED_ID, edited)))
        # a new id with the new hashes but no history entry
        self.assertTrue(pin_history_problems(ENGINE_PIN_HISTORY, "performance/cp3c-0.5", edited))
        # the sound update: a new id, the new pins and a new entry
        history = dict(ENGINE_PIN_HISTORY)
        history["performance/cp3c-0.5"] = pins_digest(edited)
        self.assertEqual(pin_history_problems(history, "performance/cp3c-0.5", edited), [])
        # an id bump with unchanged pins repeats a digest
        same = dict(ENGINE_PIN_HISTORY)
        same["performance/cp3c-0.5"] = pins_digest(ENGINE_PINS)
        self.assertIn("same pin set", " ".join(pin_history_problems(same, "performance/cp3c-0.5", ENGINE_PINS)))

    def test_the_pin_check_can_fail_a_changed_module_is_named_a_missing_pin_and_a_missing_module_are_changes(self):
        real = engine_hashes()
        self.assertEqual(unpinned_engine_changes(dict(real, returns="0" * 64)), ["returns"])
        self.assertEqual(unpinned_engine_changes(dict(real, engine="1" * 64, taint="2" * 64)), ["engine", "taint"])
        self.assertEqual(unpinned_engine_changes(dict(real, brand_new="1" * 64)), ["brand_new"])  # a new module with no pin
        self.assertEqual(unpinned_engine_changes({k: v for k, v in real.items() if k != "numerics"}), ["numerics"])  # a pinned module that vanished
        self.assertEqual(set(ENGINE_PINS), set(real))


class PerformanceBoundaryTests(unittest.TestCase):
    def test_the_package_exists_and_has_the_planned_modules(self):
        names = {p.stem for p in PERF}
        self.assertTrue({"engine", "results", "manifest", "conventions", "numerics", "states", "valuation", "ledger_view",
                         "inputs"} <= names)

    def test_imports_are_stdlib_domain_product_contract_and_analytics_facing_marketdata_only(self):
        stdlib = set(sys.stdlib_module_names)
        for path in PERF:
            for name in imports_of(path):
                root = name.split(".")[0]
                if root == "performance":
                    continue
                if root == "domain" or root == "product_contract":
                    continue
                if root == "marketdata":
                    parts = name.split(".")
                    self.assertTrue(len(parts) == 1 or parts[1] in MARKETDATA_OK, f"{path.name} imports {name}")
                    continue
                self.assertIn(root, stdlib - FORBIDDEN_PERF_STDLIB, f"{path.name} imports {name}")

    def test_no_persistence_service_adapter_vendor_or_capability_import(self):
        for path in PERF:
            names = imports_of(path)
            for banned in ("persistence", "corporate_actions_service", "performance_service", "performance_tools",
                           "marketdata.adapters", "marketdata.ingest", "marketdata.files", "marketdata.store",
                           "marketdata.verification", "marketdata.profiles", "marketdata_tools"):
                self.assertFalse(under(names, banned), f"{path.name} imports {banned}")
            for n in names:
                self.assertFalse(any(part in CAPABILITY_WORDS for part in n.lower().split(".")), f"{path.name} imports {n}")
            for word in VENDOR_WORDS:
                self.assertFalse(any(word in n.lower() for n in names), f"{path.name}: {word}")
            text = path.read_text(encoding="utf-8").lower()
            for word in VENDOR_WORDS:
                self.assertNotIn(word, text, f"{path.name} mentions {word}")

    def test_nothing_below_the_engine_imports_it_and_other_packages_use_only_the_public_modules(self):
        for sub in ("domain", "marketdata", "persistence", "product_contract", "corporate_actions_service", "marketdata_tools"):
            for path in sorted((SRC / sub).rglob("*.py")):
                self.assertFalse(under(imports_of(path), "performance"), f"{sub}/{path.name} imports performance")
        for path in sorted((SRC / "performance_service").rglob("*.py")):
            for n in under(imports_of(path), "performance"):
                parts = n.split(".")
                self.assertTrue(len(parts) == 1 or parts[1] in PUBLIC, f"{path.name} imports {n}")

    def test_only_states_names_a_reason_code(self):
        for path in PERF:
            if path.name == "states.py":
                continue
            self.assertNotIn("ReasonCode", path.read_text(encoding="utf-8"), path.name)

    def test_no_float_no_rounding_call_no_clock_no_decimal_context(self):
        for path in PERF:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant):
                    self.assertNotIsInstance(node.value, float, f"{path.name}: a float literal")
                if isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "float", f"{path.name} names float")
                if isinstance(node, ast.Call):
                    f = node.func
                    name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                    self.assertNotIn(name, {"round", "quantize", "getcontext", "setcontext", "localcontext", "float",
                                            "eval", "exec", "open"} | CLOCK_CALLS, f"{path.name} calls {name}")
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, {"ROUND_HALF_UP", "ROUND_DOWN", "ROUND_UP", "ROUND_FLOOR", "ROUND_CEILING"},
                                     f"{path.name}: a rounding mode literal outside the private exact context")

    def test_two_private_decimal_contexts_only_the_exact_one_traps_inexactness_and_the_precision_is_50(self):
        text = (SRC / "performance" / "numerics.py").read_text(encoding="utf-8")
        self.assertEqual(text.count("decimal.Context("), 2)  # tier E (exact, traps Inexact) and the transcendental one (Ruling 2.1)
        self.assertIn("decimal.Inexact", text)
        self.assertIn("TRANSCENDENTAL_PRECISION = 50", text)

    def test_ln_and_exp_are_used_only_in_numerics(self):
        for path in PERF:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in {"ln", "exp", "log10", "power", "sqrt"}:
                    self.assertEqual(path.name, "numerics.py", f"{path.name} calls {node.attr}")

    def test_a_vendor_adjusted_series_is_unreachable(self):
        for path in PERF:
            text = path.read_text(encoding="utf-8")
            for banned in ("AdjustedQuote", "UnresolvedAdjustedQuote", "adjusted_series", "marketdata.verification"):
                self.assertNotIn(banned, text, f"{path.name} mentions {banned}")

    def test_the_engine_module_never_reads_the_ledger_store_or_writes_anything(self):
        for path in PERF:
            names = imports_of(path)
            self.assertFalse(under(names, "persistence"))
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, {"append_event", "append_batch", "append_system_event", "append_correction",
                                                 "append_internal_transfer", "execute"}, f"{path.name}.{node.attr}")

    def test_the_service_never_calls_an_append_path(self):
        text = (SRC / "performance_service" / "service.py").read_text(encoding="utf-8")
        for banned in ("append_event", "append_batch", "append_system_event", "append_correction", "ledger_store"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
