"""I4 tests for I1 — canonical vocabulary (`product_contract.vocabulary`).

Run via either:
    python3 -m unittest discover -s tests -p 'test_*.py'      (repository canonical)
    python3 -m unittest discover -s tests/product -v
No `PYTHONPATH` is required for either invocation — see the sys.path setup below
and `tests/product/__init__.py` for why it lives here rather than there.
"""

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from product_contract.vocabulary import ReasonCode, ReferencePoint, SufficiencyState  # noqa: E402


class SufficiencyStateTests(unittest.TestCase):
    def test_exactly_three_members(self) -> None:
        self.assertEqual(
            {m.value for m in SufficiencyState},
            {"AVAILABLE", "LIMITED", "INSUFFICIENT_DATA"},
        )
        self.assertEqual(len(SufficiencyState), 3)


class ReasonCodeTests(unittest.TestCase):
    def test_exactly_eleven_members(self) -> None:
        # Six from PD-0006, three added by PD-0025 §1, two added by PD-0030 §1.
        self.assertEqual(
            {m.value for m in ReasonCode},
            {
                "STALE_DATA",
                "UNSUPPORTED_ASSET",
                "MISSING_BENCHMARK",
                "MISSING_COST_BASIS",
                "MISSING_FX_HISTORY",
                "CALCULATION_ERROR",
                "UNRESOLVED_CONVENTION",
                "LEDGER_INCONSISTENT",
                "NOT_RECONSTRUCTABLE",
                "SOURCE_CONFLICT",
                "MISSING_PRICE_HISTORY",
            },
        )
        self.assertEqual(len(ReasonCode), 11)

    def test_no_overlap_with_sufficiency_state(self) -> None:
        # The layered model (PD-0006) is only meaningful if the two vocabularies
        # are disjoint; overlap would make "which layer is this value in" ambiguous.
        reason_values = {m.value for m in ReasonCode}
        sufficiency_values = {m.value for m in SufficiencyState}
        self.assertEqual(reason_values & sufficiency_values, set())


class ReferencePointTests(unittest.TestCase):
    def test_exactly_three_members_matching_p4(self) -> None:
        # P4: "benchmark, the user's own policy, or the portfolio's history"
        self.assertEqual(
            {m.value for m in ReferencePoint},
            {"BENCHMARK", "USER_POLICY", "PORTFOLIO_HISTORY"},
        )
        self.assertEqual(len(ReferencePoint), 3)


if __name__ == "__main__":
    unittest.main()
