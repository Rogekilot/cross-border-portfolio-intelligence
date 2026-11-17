"""CP4b-2: the methodology registry is the Quant's text, and the engine's registry is tied to it (tech plan 17.6.3, 17.15; `risk/1.1` Ruling 9).

The engine ships a BYTE-IDENTICAL copy of `methodology/registry/<file>.json` (`src/risk/risk_registry.json`); the file is found by the `registry_id` in its CONTENT, never by its name. Everything here fails, it does not
skip, when the text and the copy disagree, when the id is not the document's, when a pointer dangles, when a number disagrees with the grid it was derived from, or when a change is made under an unchanged id.
"""

import datetime
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from marketdata.canonical import canonical_json, sha256_hex  # noqa: E402
from performance.grid import Frequency, grid_dates  # noqa: E402
from performance.periods import sub_months  # noqa: E402
from product_contract.methodology_registry import REQUIRED_FIELDS  # noqa: E402
from risk import registry as R  # noqa: E402

DOC = ROOT / "methodology" / "CP4_RISK_CONVENTIONS.md"
REGISTRY_DIR = ROOT / "methodology" / "registry"
EXPECTED_IDS = {"risk_volatility", "risk_downside_deviation", "risk_max_drawdown", "risk_sharpe", "risk_sortino", "risk_beta", "risk_r_squared", "risk_alpha_jensen", "risk_active_return",
                "risk_tracking_error", "risk_information_ratio", "benchmark_return"}
STATISTICAL = EXPECTED_IDS - {"risk_max_drawdown", "risk_active_return", "benchmark_return"}


def quants_file():
    matches = []
    for path in sorted(REGISTRY_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("registry_id") == R.REGISTRY_ID:
            matches.append(path)
    return matches


class CopyEqualsTextTests(unittest.TestCase):
    def test_exactly_one_file_of_the_text_carries_the_engines_registry_id(self):
        self.assertEqual(len(quants_file()), 1, quants_file())

    def test_the_engines_copy_is_byte_identical_to_the_quants_file(self):
        (path,) = quants_file()
        self.assertEqual(R.REGISTRY_FILE.read_bytes(), path.read_bytes())
        self.assertEqual(R.REGISTRY.digest, sha256_hex(canonical_json(json.loads(path.read_text(encoding="utf-8"))).encode("utf-8")))

    def test_the_registry_id_is_the_documents_convention_set_id(self):
        # The document is the CURRENT text and the engine implements it (risk/1.4). If the Quant issues a later id this fails, and the engine moves with a new registry copy, never silently.
        text = DOC.read_text(encoding="utf-8")
        (current,) = re.findall(r"\*\*Convention set ID:\*\* `([^`]+)`", text)
        self.assertEqual((current, R.REGISTRY_ID), ("risk/1.11", "risk/1.11"), "the document and the engine moved: update the engine")
        self.assertIn(R.REGISTRY_ID, R.REGISTRY.common["implementation_version"])  # every entry's implementation_version cites the id first
        self.assertEqual(R.REGISTRY.common["implementation_version"][0], R.REGISTRY_ID)

    def test_the_entries_are_the_twelve_of_ruling_9_3_and_each_is_named_in_the_document(self):
        self.assertEqual(R.RISK_METRIC_IDS, EXPECTED_IDS)
        text = DOC.read_text(encoding="utf-8")
        for metric_id in EXPECTED_IDS:
            self.assertIn(f"`{metric_id}`", text, metric_id)

    def test_every_ruling_an_entry_cites_is_a_ruling_of_the_document(self):
        text = DOC.read_text(encoding="utf-8")
        headings = set(re.findall(r"^### RULING (\d+\.\d+)", text, re.M))
        for entry in R.REGISTRY.entries():
            for ref in entry["defined_in"]:
                match = re.fullmatch(r"Ruling (\d+\.\d+)", ref)
                self.assertIsNotNone(match, (entry["metric_id"], ref))
                self.assertIn(match.group(1), headings, (entry["metric_id"], ref))

    def test_a_change_under_an_unchanged_id_changes_the_digest(self):
        raw = R.REGISTRY_FILE.read_bytes()
        edited = raw.replace(b"WEEKLY\": {\"insufficient_below\": 51", b"WEEKLY\": {\"insufficient_below\": 52", 1)
        self.assertNotEqual(edited, raw)
        other = R.load_registry(edited)
        self.assertEqual(other.registry_id, R.REGISTRY_ID)
        self.assertNotEqual(other.digest, R.REGISTRY.digest)
        self.assertEqual(R.load_registry(raw).digest, R.REGISTRY.digest)  # and the digest is deterministic

    def test_the_digest_depends_on_content_not_on_whitespace_or_key_order(self):
        doc = json.loads(R.REGISTRY_FILE.read_text(encoding="utf-8"))
        reordered = json.dumps(dict(reversed(list(doc.items()))), indent=4).encode("utf-8")
        self.assertEqual(R.load_registry(reordered).digest, R.REGISTRY.digest)


class OneFilePerVersionTests(unittest.TestCase):
    """Ruling 9.2 (1.2): each version's registry is its own file, named after its id; the engine reads the id from the CONTENT and refuses a file whose id it does not implement."""

    def test_the_engine_implements_risk_1_11_and_its_copy_is_the_1_11_file(self):
        self.assertEqual((R.IMPLEMENTED_REGISTRY_ID, R.REGISTRY_ID), ("risk/1.11", "risk/1.11"))
        self.assertEqual(R.REGISTRY_FILE.read_bytes(), (REGISTRY_DIR / "RISK_1.11_REGISTRY.json").read_bytes())
        previous = (REGISTRY_DIR / "RISK_1.10_REGISTRY.json").read_bytes()  # the record of the 1.15 label: a record, not what this engine implements
        with self.assertRaises(R.RegistryError):
            R.load_registry(previous)

    def test_every_version_file_carries_its_own_id_and_the_old_ones_are_refused_by_this_engine(self):
        for name, registry_id in (("RISK_1.0_REGISTRY.json", "risk/1.0"), ("RISK_1.1_REGISTRY.json", "risk/1.1"), ("RISK_1.2_REGISTRY.json", "risk/1.2"), ("RISK_1.3_REGISTRY.json", "risk/1.3"), ("RISK_1.4_REGISTRY.json", "risk/1.4"), ("RISK_1.5_REGISTRY.json", "risk/1.5"), ("RISK_1.6_REGISTRY.json", "risk/1.6"), ("RISK_1.7_REGISTRY.json", "risk/1.7"), ("RISK_1.8_REGISTRY.json", "risk/1.8"), ("RISK_1.9_REGISTRY.json", "risk/1.9")):
            raw = (REGISTRY_DIR / name).read_bytes()
            self.assertEqual(json.loads(raw.decode("utf-8"))["registry_id"], registry_id, name)
            with self.assertRaises(R.RegistryError, msg=name):
                R.load_registry(raw)  # a record, not what this engine implements
            self.assertEqual(R.load_registry(raw, implements=registry_id).registry_id, registry_id)  # readable as a record by the id it states

    def test_the_engine_implements_the_latest_issued_registry_by_numeric_order_never_string_order(self):
        # risk/1.10 follows risk/1.9: the components are numbers. As strings "risk/1.9" would sort after "risk/1.10", which is the trap
        ids = [json.loads(path.read_text(encoding="utf-8"))["registry_id"] for path in sorted(REGISTRY_DIR.glob("RISK_*_REGISTRY.json"))]
        self.assertIn("risk/1.9", ids)
        self.assertIn("risk/1.10", ids)
        self.assertIn("risk/1.11", ids)

        def numeric(registry_id):
            return tuple(int(part) for part in registry_id.split("/")[1].split("."))

        self.assertEqual(max(ids, key=numeric), R.IMPLEMENTED_REGISTRY_ID)
        self.assertEqual(max(ids), "risk/1.9")  # the string order, shown to be wrong
        self.assertGreater(numeric("risk/1.10"), numeric("risk/1.9"))

    def test_the_id_is_read_from_the_content_not_the_name(self):
        raw = (REGISTRY_DIR / "RISK_1.1_REGISTRY.json").read_bytes()
        renamed = raw.replace(b'"registry_id": "risk/1.1"', b'"registry_id": "risk/1.11"', 1)
        self.assertNotEqual(raw, renamed)
        self.assertEqual(R.load_registry(renamed).registry_id, "risk/1.11")  # whatever file it came from, its content says 1.11
        self.assertNotEqual(R.load_registry(renamed).digest, R.REGISTRY.digest)  # but its content is not the 1.11 text: the digest tells

    def test_the_manifest_cites_both_the_id_and_the_digest_of_the_file_it_used(self):
        self.assertEqual(len(R.REGISTRY.digest), 64)
        self.assertEqual(R.REGISTRY.digest, sha256_hex(canonical_json(json.loads((REGISTRY_DIR / "RISK_1.11_REGISTRY.json").read_text(encoding="utf-8"))).encode("utf-8")))


class SchemaTests(unittest.TestCase):
    def test_every_entry_carries_the_fifteen_prd_fields_and_the_seven_structured_ones(self):
        for entry in R.REGISTRY.entries():
            for field in tuple(REQUIRED_FIELDS) + ("metric_id", "judgment_class", "reference_point", "comparability_class", "presentation", "states", "wording", "defined_in"):
                self.assertIn(field, entry, (entry["metric_id"], field))

    def test_the_product_contract_validates_the_shipped_entries(self):
        self.assertEqual(len(R.METHODOLOGY_REGISTRY), 12)  # the constructor validates every entry against the section 33 schema

    def test_no_pointer_dangles_and_whole_value_pointers_resolve(self):
        resolved = R.REGISTRY.resolved("risk_volatility")
        self.assertEqual(resolved["frequency"]["default"], "WEEKLY")
        self.assertEqual(resolved["lookback"]["default"], "TRAILING_MONTHS 36")
        self.assertEqual(resolved["implementation_version"][0], R.REGISTRY_ID)
        self.assertIsInstance(resolved["states"], list)
        self.assertEqual(resolved["states"][0][0]["detail"], "WINDOW_BEFORE_INCEPTION")  # a list of whole-value pointers resolves item by item
        # prose that mentions a pointer is left as written
        self.assertIn("common.states_window_and_series", R.REGISTRY.entry("risk_volatility")["missing_data_handling"])
        bad = json.loads(R.REGISTRY_FILE.read_text(encoding="utf-8"))
        bad["entries"][0]["frequency"] = "common.does_not_exist"
        with self.assertRaises(R.RegistryError):
            R.load_registry(json.dumps(bad).encode("utf-8"))

    def test_a_malformed_registry_fails_closed(self):
        doc = json.loads(R.REGISTRY_FILE.read_text(encoding="utf-8"))
        missing = json.loads(json.dumps(doc))
        del missing["entries"][3]["formula"]
        duplicate = json.loads(json.dumps(doc))
        duplicate["entries"].append(duplicate["entries"][0])
        for broken in (missing, duplicate):
            with self.assertRaises(R.RegistryError):
                R.load_registry(json.dumps(broken).encode("utf-8"))

    def test_a_result_cites_the_id_and_the_metric(self):
        self.assertEqual(R.REGISTRY.entry_key("risk_volatility"), "risk/1.11#risk_volatility")
        with self.assertRaises(KeyError):
            R.REGISTRY.entry_key("risk_unknown")
        with self.assertRaises(KeyError):
            R.REGISTRY.entry("holding_value")  # a CP3 metric has no entry here: that debt is carried (the allow-list is the CP3 ids, shrinking)


class ThresholdsAreTheGridsTests(unittest.TestCase):
    """Ruling 7.1: the minimum observations are the counts a full 1-year and a full 3-year window ALWAYS yield on the grid of Ruling 2.2. They are recomputed here by brute force over every third end date from 2001 to
    2029 (the Quant counted every one), so the registry's numbers cannot drift from the grid."""

    @classmethod
    def setUpClass(cls):
        cls.low, cls.high = {}, {}
        for frequency in Frequency:
            for months in (12, 36):
                counts = []
                end = datetime.date(2001, 1, 1)
                while end <= datetime.date(2029, 12, 31):
                    counts.append(len(grid_dates(frequency, sub_months(end, months), end)) - 1)
                    end += datetime.timedelta(days=3)
                cls.low[(frequency.value, months)] = min(counts)

    def test_insufficient_below_is_the_one_year_floor_and_available_from_the_three_year_floor(self):
        for metric_id in STATISTICAL:
            for frequency in Frequency:
                m = R.REGISTRY.minimum_observations(metric_id, frequency.value)
                self.assertEqual((m.insufficient_below, m.available_from), (self.low[(frequency.value, 12)], self.low[(frequency.value, 36)]), (metric_id, frequency))

    def test_window_facts_have_no_statistical_minimum(self):
        for metric_id in EXPECTED_IDS - STATISTICAL:
            for frequency in Frequency:
                m = R.REGISTRY.minimum_observations(metric_id, frequency.value)
                self.assertEqual((m.insufficient_below, m.available_from), (1, 1), (metric_id, frequency))

    def test_the_state_of_a_count_follows_the_entry(self):
        m = R.REGISTRY.minimum_observations("risk_beta", "WEEKLY")
        self.assertEqual((m.insufficient_below, m.available_from), (51, 155))
        with self.assertRaises(ValueError):
            R.REGISTRY.minimum_observations("risk_beta", "HOURLY")

    def test_the_frequency_invariance_property_on_full_windows(self):
        # a full window has the same STATE at every frequency: 3Y gives >= available_from at all three, 1Y gives a count in [insufficient_below, available_from)
        for frequency in Frequency:
            m = R.REGISTRY.minimum_observations("risk_volatility", frequency.value)
            self.assertGreaterEqual(self.low[(frequency.value, 36)], m.available_from)
            self.assertGreaterEqual(self.low[(frequency.value, 12)], m.insufficient_below)
            self.assertLess(self.low[(frequency.value, 12)] + 1, m.available_from)  # even the largest 1Y count (min + 1) stays below the standard

    def test_no_risk_module_holds_a_threshold_literal(self):
        import ast  # noqa: PLC0415

        thresholds = {259, 781, 51, 155, 11, 35, 1304}  # every floor and standard of Ruling 7.1 (CP4M-5: 11, the monthly floor, was missing)
        for path in sorted((ROOT / "src" / "risk").glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
                    self.assertNotIn(node.value, thresholds, f"{path.name}: the literal {node.value} is a registry threshold: read it from the entry")


class WordingTests(unittest.TestCase):
    """P6: historical statistics are not forecasts. The registry's own prose must obey the words it forbids (the forbidden list itself, and the `wording` blocks, are excluded)."""

    def test_no_definition_formula_or_limitation_uses_a_forbidden_word(self):
        forbidden = R.REGISTRY.common["wording_forbidden"]
        patterns = [re.compile(r"\b%s\b" % re.escape(w), re.I) for w in forbidden]
        for entry in R.REGISTRY.entries():
            prose = [entry["human_definition"], entry["formula"], entry["annualization_convention"], entry["missing_data_handling"]] + [x for x in entry["known_limitations"] if isinstance(x, str)]
            for text in prose:
                for pattern in patterns:
                    self.assertIsNone(pattern.search(text), (entry["metric_id"], pattern.pattern, text))
        for key in ("limitation_actual_history", "limitation_daily", "comparability_two_leg"):
            for pattern in patterns:
                self.assertIsNone(pattern.search(R.REGISTRY.common[key]), (key, pattern.pattern))


if __name__ == "__main__":
    unittest.main()
