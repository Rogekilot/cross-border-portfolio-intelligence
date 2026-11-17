"""I4 tests for I3 — methodology registry schema and validator
(`product_contract.methodology_registry`). Covers AC-16 (one negative case per
required field) and AC-17 as superseded for CP4 onward (the shipped registry is the Quant's, validated; see `ShippedRegistryTests`).

Run via either:
    python3 -m unittest discover -s tests -p 'test_*.py'      (repository canonical)
    python3 -m unittest discover -s tests/product -v
No `PYTHONPATH` is required for either invocation — see the sys.path setup below
and `tests/product/__init__.py` for why it lives here rather than there.

Fixture note: the sample entry below exists only in this test file. Under INC-001
(`decisions/product/PD-0004-increment-1-scope-and-hg1-ordering.md`) no metric entry, not even
an example, could live under `src/`. That scope ended with INC-001 (main-session ruling
2026-10-02): from CP4 the shipped entries are the Quant's, from `methodology/registry/`.
"""

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from product_contract.methodology_registry import (  # noqa: E402
    EMPTY_METHODOLOGY_REGISTRY,
    REQUIRED_FIELDS,
    MethodologyRegistry,
    MethodologyRegistryValidationError,
    validate_entry,
)


def _complete_fixture_entry() -> dict:
    """A test-only fixture satisfying all fifteen §33 fields. Never imported by
    src/ code and never added to `EMPTY_METHODOLOGY_REGISTRY`."""
    return {field: f"fixture-{field}" for field in REQUIRED_FIELDS}


class SchemaShapeTests(unittest.TestCase):
    def test_exactly_fifteen_required_fields(self) -> None:
        self.assertEqual(len(REQUIRED_FIELDS), 15)

    def test_required_fields_match_section_33_verbatim(self) -> None:
        self.assertEqual(
            REQUIRED_FIELDS,
            (
                "metric_name",
                "human_definition",
                "formula",
                "annualization_convention",
                "data_inputs",
                "minimum_observations",
                "frequency",
                "lookback",
                "benchmark_dependency",
                "risk_free_rate_dependency",
                "missing_data_handling",
                "fx_treatment",
                "corporate_action_treatment",
                "known_limitations",
                "implementation_version",
            ),
        )

    def test_no_duplicate_fields(self) -> None:
        self.assertEqual(len(REQUIRED_FIELDS), len(set(REQUIRED_FIELDS)))


class ValidateEntryPositiveTests(unittest.TestCase):
    def test_complete_entry_passes(self) -> None:
        validate_entry(_complete_fixture_entry())  # must not raise

    def test_entry_with_extra_field_still_passes(self) -> None:
        # The schema requires presence of the fifteen; it does not forbid an
        # entry from carrying additional metadata quant_analyst chooses to add.
        entry = _complete_fixture_entry()
        entry["extra_internal_note"] = "not a §33 field"
        validate_entry(entry)  # must not raise


class ValidateEntryNegativeTests(unittest.TestCase):
    """AC-16: one negative case per required field — a registry entry missing
    any single required field must fail validation."""

    def test_missing_field_fails_for_every_required_field(self) -> None:
        for missing_field in REQUIRED_FIELDS:
            with self.subTest(missing_field=missing_field):
                entry = _complete_fixture_entry()
                del entry[missing_field]
                with self.assertRaises(MethodologyRegistryValidationError):
                    validate_entry(entry)

    def test_empty_entry_fails(self) -> None:
        with self.assertRaises(MethodologyRegistryValidationError):
            validate_entry({})

    def test_non_mapping_entry_fails(self) -> None:
        with self.assertRaises(MethodologyRegistryValidationError):
            validate_entry(["metric_name", "human_definition"])  # type: ignore[arg-type]


class RegistryConstructionTests(unittest.TestCase):
    def test_registry_with_valid_entries_constructs(self) -> None:
        registry = MethodologyRegistry(entries=(_complete_fixture_entry(),))
        self.assertEqual(len(registry), 1)

    def test_registry_with_invalid_entry_fails_to_construct(self) -> None:
        incomplete = _complete_fixture_entry()
        del incomplete["formula"]
        with self.assertRaises(MethodologyRegistryValidationError):
            MethodologyRegistry(entries=(incomplete,))


class ShippedRegistryTests(unittest.TestCase):
    """AC-17 as superseded for CP4 onward (main-session ruling 2026-10-02): AC-17's "zero entries" applied to INC-001 (CP0) only. From CP4 the shipped registry is populated, and the test is: every
    entry VALIDATES against the schema (all fifteen PRD section 33 fields), and the entries are EXACTLY the Quant's registry file of the risk convention set (the engine's bundled copy is also tested
    byte-equal to it in `test_risk_registry_matches_methodology`). Nothing asserts emptiness."""

    @staticmethod
    def quants_file() -> dict:
        import json  # noqa: PLC0415

        from risk.registry import REGISTRY_ID  # noqa: PLC0415

        for path in sorted((Path(__file__).resolve().parents[2] / "methodology" / "registry").glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("registry_id") == REGISTRY_ID:  # the id is read from the file's content, never its name
                return doc
        raise AssertionError(f"no registry file in methodology/registry carries registry_id {REGISTRY_ID!r}")

    def test_every_shipped_entry_validates_against_the_schema(self) -> None:
        from risk.registry import METHODOLOGY_REGISTRY  # noqa: PLC0415

        self.assertGreater(len(METHODOLOGY_REGISTRY), 0)
        for entry in METHODOLOGY_REGISTRY.entries:
            validate_entry(entry)  # raises on any missing section 33 field
            for field in REQUIRED_FIELDS:
                self.assertIn(field, entry)

    def test_the_shipped_entries_are_exactly_the_quants_appendix(self) -> None:
        from risk.registry import METHODOLOGY_REGISTRY  # noqa: PLC0415

        doc = self.quants_file()
        self.assertEqual([dict(e) for e in METHODOLOGY_REGISTRY.entries], sorted(doc["entries"], key=lambda e: e["metric_id"]))
        self.assertEqual(len(METHODOLOGY_REGISTRY), 12)

    def test_the_increment_1_empty_constant_still_constructs_and_is_not_the_shipped_registry(self) -> None:
        from risk.registry import METHODOLOGY_REGISTRY  # noqa: PLC0415

        self.assertEqual(EMPTY_METHODOLOGY_REGISTRY.entries, ())  # the INC-001 artifact: a registry with no entries is still constructible
        self.assertIsNot(EMPTY_METHODOLOGY_REGISTRY, METHODOLOGY_REGISTRY)


if __name__ == "__main__":
    unittest.main()
