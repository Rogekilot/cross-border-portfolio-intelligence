"""I3 — methodology registry schema and validator (source PRD §33; AC-16, AC-17).

§33 requires a centralized methodology registry, versioned per metric, carrying
fifteen fields (reproduced verbatim from the source PRD, in its own order):
metric name; human definition; formula; annualization convention; data inputs;
minimum observations; frequency; lookback; benchmark dependency; risk-free rate
dependency; missing-data handling; FX treatment; corporate-action treatment;
known limitations; implementation version.

This module builds the schema (the required-field list) and a validator
(`validate_entry`). It does not decide, and never invents, a metric definition:
every metric definition is a methodology decision owned by `quant_analyst`
(§33, §44.4; `decisions/product/PD-0004-increment-1-scope-and-hg1-ordering.md`).
Under INC-001 the shipped registry was `EMPTY_METHODOLOGY_REGISTRY` (zero entries, AC-17).
That scope ended with INC-001 (main-session ruling 2026-10-02): from CP4 the shipped registry
is populated from the Quant's registry file (`risk.registry.METHODOLOGY_REGISTRY`), each entry
validated here, and `EMPTY_METHODOLOGY_REGISTRY` remains only as the INC-001 artifact.
Test fixtures with sample entries belong in `tests/product/`, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

# The fifteen §33 fields, in source-PRD order. This tuple is the schema: presence
# of every key is required on any entry that claims to satisfy §33. This module
# does not additionally require a field's *value* to be non-empty/non-null —
# whether e.g. "benchmark dependency: none" is a valid value for a given metric is
# a methodology judgment (quant_analyst's), not a schema question this module
# answers.
REQUIRED_FIELDS: Tuple[str, ...] = (
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
)


class MethodologyRegistryValidationError(ValueError):
    """Raised when a methodology registry entry does not satisfy the §33 schema."""


def validate_entry(entry: Mapping[str, Any]) -> None:
    """Raise `MethodologyRegistryValidationError` if `entry` is missing any of the
    fifteen §33 required fields. Presence is checked per field so a caller gets
    the full list of what is missing, not just the first miss (AC-16: "one
    negative case per required field, or a single parameterized case covering all
    fifteen" — this makes either style of test possible against one function).
    """
    if not isinstance(entry, Mapping):
        raise MethodologyRegistryValidationError(
            f"a methodology registry entry must be a mapping, got {type(entry)!r}"
        )
    missing = [f for f in REQUIRED_FIELDS if f not in entry]
    if missing:
        raise MethodologyRegistryValidationError(
            "methodology registry entry missing required §33 field(s): "
            f"{missing}"
        )


@dataclass(frozen=True)
class MethodologyRegistry:
    """A versioned collection of methodology entries. Every entry, if any, is
    validated against the §33 schema at construction time — an entry that fails
    `validate_entry` prevents the registry from being constructed at all, the
    same "invalid by construction" style as `metric_state.MetricResult`.
    """

    entries: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for entry in self.entries:
            validate_entry(entry)

    def __len__(self) -> int:
        return len(self.entries)


# The registry INC-001 shipped (AC-17): zero metric entries. Superseded for CP4 onward
# (main-session ruling 2026-10-02): the shipped registry is `risk.registry.METHODOLOGY_REGISTRY`.
# This constant stays as the INC-001 artifact (an empty registry is still constructible).
EMPTY_METHODOLOGY_REGISTRY: MethodologyRegistry = MethodologyRegistry(entries=())
