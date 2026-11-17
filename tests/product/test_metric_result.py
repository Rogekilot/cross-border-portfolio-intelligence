"""I4 tests for I2 — the metric-state model (`product_contract.metric_state`).

Covers AC-15 **as corrected by `decisions/product/PD-0007-limited-carries-a-value.md`
and its 2026-09-04 amendment**: `value is None` if and only if `sufficiency_state is
INSUFFICIENT_DATA`. `AVAILABLE` and `LIMITED` both *require* a value;
`INSUFFICIENT_DATA` forbids one. This rule moved twice — the original AC-15 forbade
`LIMITED` from ever carrying a value (`test_limited_with_value_fails`, since inverted
into `test_limited_with_value`); PD-0007's first ruling then left `LIMITED` merely
*permitted* to carry one; `design_review` round 3 (finding BF-4) showed that left
`MetricResult(value=None, sufficiency_state=LIMITED)` constructible with no design
rendering for it, so the amendment made the rule a total equivalence, also requiring
`AVAILABLE` to carry a value. Also covers the PD-0006 (second amendment) targeted
reason-code coupling — **unchanged by PD-0007** — the documented escape-hatch
closures from `reviews/TECH_REVIEW.md` (subclassing, `dataclasses.replace`,
`copy.deepcopy`, pickle), and the three vectors that remain deliberately unsealed and
are pinned here as known limitations rather than silently assumed closed.

Run via either:
    python3 -m unittest discover -s tests -p 'test_*.py'      (repository canonical)
    python3 -m unittest discover -s tests/product -v
No `PYTHONPATH` is required for either invocation — see the sys.path setup below
and `tests/product/__init__.py` for why it lives here rather than there.
"""

import copy
import dataclasses
import pickle
import sys
import unittest
from decimal import Decimal
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from product_contract.metric_state import InvalidMetricResultError, MetricResult  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

# The reason codes coupled to sufficiency_state: PD-0006's second amendment (five) plus the
# three PD-0025 §1 added. Every ReasonCode except STALE_DATA.
_COUPLED_REASON_CODES = (
    ReasonCode.UNSUPPORTED_ASSET,
    ReasonCode.MISSING_BENCHMARK,
    ReasonCode.MISSING_COST_BASIS,
    ReasonCode.MISSING_FX_HISTORY,
    ReasonCode.CALCULATION_ERROR,
    ReasonCode.UNRESOLVED_CONVENTION,
    ReasonCode.LEDGER_INCONSISTENT,
    ReasonCode.NOT_RECONSTRUCTABLE,
    ReasonCode.SOURCE_CONFLICT,
    ReasonCode.MISSING_PRICE_HISTORY,
)


class ValidConstructionTests(unittest.TestCase):
    def test_available_with_value(self) -> None:
        m = MetricResult(value=Decimal("1.30"), sufficiency_state=SufficiencyState.AVAILABLE)
        self.assertEqual(m.value, Decimal("1.30"))
        self.assertIsNone(m.reason_code)

    def test_limited_with_value(self) -> None:
        # PD-0007: "LIMITED carries a value; only INSUFFICIENT_DATA suppresses
        # one." This inverts the pre-PD-0007 test_limited_with_value_fails, which
        # pinned AC-15's original, incorrect wording. designs/FEATURE_DESIGN.md
        # §D3.2's LIMITED row renders exactly this: the computed value plus a
        # mandatory, non-dismissible qualifier.
        m = MetricResult(value=Decimal("0.80"), sufficiency_state=SufficiencyState.LIMITED)
        self.assertEqual(m.value, Decimal("0.80"))

    def test_limited_with_zero_value(self) -> None:
        # 0.0 is a real, presentable value under PD-0007 for a state permitted to
        # carry one — unlike the AC15NegativeTests case, this is not the "zero as
        # a fallback" failure mode §32 forbids; it is an actual computed value.
        m = MetricResult(value=Decimal("0"), sufficiency_state=SufficiencyState.LIMITED)
        self.assertEqual(m.value, Decimal("0"))

    def test_limited_with_value_and_each_coupled_reason_code(self) -> None:
        # PD-0006's coupling is unchanged: it forbids AVAILABLE + one of the five,
        # not LIMITED + one of the five. A LIMITED metric may combine a value with
        # any reason code, including one of the five (e.g. the metric is
        # computable on a weak basis precisely because the cost basis is
        # missing).
        for code in _COUPLED_REASON_CODES:
            with self.subTest(reason_code=code):
                m = MetricResult(
                    value=Decimal("0.42"),
                    sufficiency_state=SufficiencyState.LIMITED,
                    reason_code=code,
                )
                self.assertEqual(m.value, Decimal("0.42"))
                self.assertEqual(m.reason_code, code)

    def test_limited_with_no_reason_code(self) -> None:
        # LIMITED requires a value (PD-0007's amendment) but a reason code is
        # still optional even when the state is not AVAILABLE.
        m = MetricResult(value=Decimal("0.55"), sufficiency_state=SufficiencyState.LIMITED)
        self.assertEqual(m.value, Decimal("0.55"))
        self.assertIsNone(m.reason_code)

    def test_insufficient_data_with_no_value_and_no_reason(self) -> None:
        # PD-0006: "a reason code is optional even when the state is not
        # AVAILABLE — 'not enough observations' is a complete answer."
        m = MetricResult(
            value=None, sufficiency_state=SufficiencyState.INSUFFICIENT_DATA
        )
        self.assertIsNone(m.reason_code)

    def test_insufficient_data_with_reason_code(self) -> None:
        m = MetricResult(
            value=None,
            sufficiency_state=SufficiencyState.INSUFFICIENT_DATA,
            reason_code=ReasonCode.MISSING_BENCHMARK,
        )
        self.assertEqual(m.reason_code, ReasonCode.MISSING_BENCHMARK)

    def test_limited_with_each_coupled_reason_code(self) -> None:
        # LIMITED now requires a value (PD-0007's amendment), so this is the same
        # case as test_limited_with_value_and_each_coupled_reason_code above; kept
        # as a separate, minimal test of reason_code alone.
        for code in _COUPLED_REASON_CODES:
            with self.subTest(reason_code=code):
                m = MetricResult(
                    value=Decimal("0.10"),
                    sufficiency_state=SufficiencyState.LIMITED,
                    reason_code=code,
                )
                self.assertEqual(m.reason_code, code)


class AC15NegativeTests(unittest.TestCase):
    """AC-15, as corrected by PD-0007 and its 2026-09-04 amendment: `value is None`
    if and only if `sufficiency_state is INSUFFICIENT_DATA`. This class now covers
    both directions of that equivalence — `INSUFFICIENT_DATA` + a value (the
    original AC-15 rule, unchanged) and `AVAILABLE`/`LIMITED` + no value (the
    amendment, closing `design_review` round-3 finding BF-4). Positive cases live
    in `ValidConstructionTests`."""

    def test_insufficient_data_with_value_fails(self) -> None:
        with self.assertRaises(InvalidMetricResultError):
            MetricResult(value=Decimal("1.30"), sufficiency_state=SufficiencyState.INSUFFICIENT_DATA)

    def test_available_with_no_value_fails(self) -> None:
        # BF-4: AVAILABLE was equally unconstrained and equally incoherent — "a
        # metric that is available and absent is not a state this product should
        # be able to express" (PD-0007 amendment).
        with self.assertRaises(InvalidMetricResultError):
            MetricResult(value=None, sufficiency_state=SufficiencyState.AVAILABLE)

    def test_limited_with_no_value_fails(self) -> None:
        # BF-4, the finding itself: MetricResult(value=None,
        # sufficiency_state=LIMITED) was still legal under PD-0007's first ruling,
        # and designs/FEATURE_DESIGN.md §D3.2's LIMITED row has no branch for a
        # value-less LIMITED — it is written entirely in terms of "the computed
        # value." LIMITED now requires one.
        with self.assertRaises(InvalidMetricResultError):
            MetricResult(value=None, sufficiency_state=SufficiencyState.LIMITED)

    def test_insufficient_data_with_value_and_reason_code_fails(self) -> None:
        with self.assertRaises(InvalidMetricResultError):
            MetricResult(
                value=Decimal("-0.02"),
                sufficiency_state=SufficiencyState.INSUFFICIENT_DATA,
                reason_code=ReasonCode.CALCULATION_ERROR,
            )

    def test_zero_is_still_a_presentable_value_and_is_rejected(self) -> None:
        # §32: "do not render zero ... that can be mistaken for real analytics."
        # 0.0 is not a sentinel for "no value" in this model; None is. A caller
        # passing value=0.0 alongside INSUFFICIENT_DATA must still fail — unlike
        # LIMITED (see test_limited_with_zero_value), INSUFFICIENT_DATA is the one
        # state PD-0007 keeps suppressed regardless of the value's shape.
        with self.assertRaises(InvalidMetricResultError):
            MetricResult(value=Decimal("0"), sufficiency_state=SufficiencyState.INSUFFICIENT_DATA)

    def test_cannot_repair_after_construction_failure(self) -> None:
        # "Enforced by construction" means there is no reference to salvage.
        try:
            MetricResult(value=Decimal("1"), sufficiency_state=SufficiencyState.INSUFFICIENT_DATA)
            self.fail("expected InvalidMetricResultError")
        except InvalidMetricResultError as exc:
            # The exception itself is the only artifact; there is no object.
            self.assertIn("AC-15", str(exc))


class ReasonCodeCouplingNegativeTests(unittest.TestCase):
    """PD-0006, second amendment (closes `reviews/TECH_REVIEW.md` B-1/B-2): each
    of the five reason codes below requires sufficiency_state != AVAILABLE.
    STALE_DATA is the only exempt code — see StaleDataNarrowingTests."""

    def test_available_with_each_coupled_reason_code_and_zero_value_fails(self) -> None:
        # [Corrected 2026-09-05, N-21] This test used to construct
        # AVAILABLE + value=None + a coupled reason code. Once AC-15 became the
        # total equivalence (PD-0007's amendment), value=None on AVAILABLE trips
        # that biconditional clause before __post_init__ ever reaches the
        # reason-code coupling clause, so the old version of this test could not
        # tell the two rules apart — it would still have passed with PD-0006's
        # five-code coupling deleted outright. Using a real (here, zero) value
        # forces the coupling clause to be the one that fires, restoring the
        # discrimination this test exists for. 0.0 is deliberately distinct from
        # the 1.30 used by the sibling test below, so this is not a pure
        # duplicate — it also reconfirms zero is a real value, not a None
        # sentinel, in this construction path.
        for code in _COUPLED_REASON_CODES:
            with self.subTest(reason_code=code):
                with self.assertRaises(InvalidMetricResultError):
                    MetricResult(
                        value=Decimal("0"),
                        sufficiency_state=SufficiencyState.AVAILABLE,
                        reason_code=code,
                    )

    def test_available_with_each_coupled_reason_code_and_a_value_fails(self) -> None:
        # review-01's exact worked example:
        # MetricResult(value=Decimal("1.30"), sufficiency_state=AVAILABLE, reason_code=MISSING_BENCHMARK)
        for code in _COUPLED_REASON_CODES:
            with self.subTest(reason_code=code):
                with self.assertRaises(InvalidMetricResultError):
                    MetricResult(
                        value=Decimal("1.30"),
                        sufficiency_state=SufficiencyState.AVAILABLE,
                        reason_code=code,
                    )


class ImmutabilityTests(unittest.TestCase):
    """A frozen dataclass closes the "mutate into an invalid state after
    construction" loophole for ordinary code, not just the constructor-time one."""

    def test_frozen_rejects_post_construction_mutation(self) -> None:
        # AVAILABLE now requires a value (PD-0007 amendment), so a valid AVAILABLE
        # instance needs one here.
        m = MetricResult(value=Decimal("1.30"), sufficiency_state=SufficiencyState.AVAILABLE)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            m.value = Decimal("5") # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            m.sufficiency_state = SufficiencyState.LIMITED  # type: ignore[misc]

    def test_dataclasses_replace_revalidates_and_blocks_invalid_result(self) -> None:
        # dataclasses.replace() re-invokes __init__ -> __post_init__, so it cannot
        # be used to sidestep either structural rule. Under PD-0007 only
        # INSUFFICIENT_DATA forbids a value, so that is the transition this test
        # must target — AVAILABLE -> LIMITED with the same value is valid now
        # (see test_dataclasses_replace_permits_a_valid_transition_keeping_value).
        m = MetricResult(value=Decimal("1.30"), sufficiency_state=SufficiencyState.AVAILABLE)
        with self.assertRaises(InvalidMetricResultError):
            dataclasses.replace(m, sufficiency_state=SufficiencyState.INSUFFICIENT_DATA)

    def test_dataclasses_replace_permits_a_valid_transition(self) -> None:
        # Under the amended equivalence, dropping to no value is only valid when
        # paired with INSUFFICIENT_DATA — replacing to LIMITED + None (the old
        # version of this test) is now itself the BF-4 violation; see
        # test_dataclasses_replace_to_limited_with_no_value_fails below.
        m = MetricResult(value=Decimal("1.30"), sufficiency_state=SufficiencyState.AVAILABLE)
        replaced = dataclasses.replace(
            m, value=None, sufficiency_state=SufficiencyState.INSUFFICIENT_DATA
        )
        self.assertEqual(replaced.sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)
        self.assertIsNone(replaced.value)

    def test_dataclasses_replace_to_limited_with_no_value_fails(self) -> None:
        # BF-4 via dataclasses.replace(): dropping the value while moving to
        # LIMITED is exactly the gap the amendment closed.
        m = MetricResult(value=Decimal("1.30"), sufficiency_state=SufficiencyState.AVAILABLE)
        with self.assertRaises(InvalidMetricResultError):
            dataclasses.replace(m, value=None, sufficiency_state=SufficiencyState.LIMITED)

    def test_dataclasses_replace_permits_a_valid_transition_keeping_value(self) -> None:
        # PD-0007: AVAILABLE -> LIMITED need not drop the value.
        m = MetricResult(value=Decimal("1.30"), sufficiency_state=SufficiencyState.AVAILABLE)
        replaced = dataclasses.replace(m, sufficiency_state=SufficiencyState.LIMITED)
        self.assertEqual(replaced.sufficiency_state, SufficiencyState.LIMITED)
        self.assertEqual(replaced.value, Decimal("1.30"))


class SubclassSealedTests(unittest.TestCase):
    """`reviews/TECH_REVIEW.md` AC-15 finding: the subclass vector is "the
    important one" — a subclass overriding __post_init__ without calling super()
    would satisfy isinstance() while silently voiding every guarantee above.
    MetricResult forbids subclassing outright via __init_subclass__."""

    def test_subclassing_is_rejected_at_class_definition_time(self) -> None:
        with self.assertRaises(TypeError):

            class Loose(MetricResult):  # type: ignore[misc]
                def __post_init__(self) -> None:  # pragma: no cover - never reached
                    pass


class CopyAndPickleTests(unittest.TestCase):
    """`reviews/TECH_REVIEW.md` AC-15 finding: deepcopy/pickle of a dataclass use
    a default reduction protocol that restores field values without re-running
    __post_init__, which would otherwise propagate a tampered instance's invalid
    state undetected. MetricResult.__reduce__ forces both to go through the real
    constructor."""

    def test_deepcopy_of_a_valid_instance_round_trips(self) -> None:
        # AVAILABLE now requires a value (PD-0007 amendment).
        m = MetricResult(
            value=Decimal("1.30"),
            sufficiency_state=SufficiencyState.AVAILABLE,
            reason_code=ReasonCode.STALE_DATA,
        )
        copied = copy.deepcopy(m)
        self.assertEqual(copied, m)
        self.assertIsNot(copied, m)

    def test_pickle_round_trip_of_a_valid_instance(self) -> None:
        m = MetricResult(value=Decimal("1.30"), sufficiency_state=SufficiencyState.AVAILABLE)
        restored = pickle.loads(pickle.dumps(m))
        self.assertEqual(restored, m)

    def test_deepcopy_of_a_tampered_instance_revalidates_and_raises(self) -> None:
        # Under PD-0007, LIMITED + a value is valid, so the tampering target that
        # demonstrates an invalid state must be INSUFFICIENT_DATA (the one state
        # AC-15 still suppresses).
        m = MetricResult(value=None, sufficiency_state=SufficiencyState.INSUFFICIENT_DATA)
        # Deliberately reach past the frozen dataclass's own __setattr__ — this is
        # the known, unsealed vector documented in metric_state.py's module
        # docstring, exercised here to prove __reduce__ still catches it on copy.
        object.__setattr__(m, "value", Decimal("42"))
        with self.assertRaises(InvalidMetricResultError):
            copy.deepcopy(m)

    def test_pickle_of_a_tampered_instance_revalidates_and_raises_on_load(self) -> None:
        m = MetricResult(value=None, sufficiency_state=SufficiencyState.INSUFFICIENT_DATA)
        object.__setattr__(m, "value", Decimal("42"))
        payload = pickle.dumps(m)  # dumping only records the (now-invalid) fields
        with self.assertRaises(InvalidMetricResultError):
            pickle.loads(payload)  # loading reconstructs via __init__ and re-validates


class KnownUnsealedVectorTests(unittest.TestCase):
    """Documents, rather than silently assumes closed, the three vectors
    `reviews/TECH_REVIEW.md` (round 1 and round 2's N-12) and `metric_state.py`'s
    module docstring agree cannot be sealed in pure Python: object.__setattr__,
    object.__new__, and direct instance __dict__ mutation all bypass every
    guarantee this module builds. Pinned here so a future change in this behavior
    (e.g. an attempted fix) shows in a diff instead of silently regressing this
    documented claim."""

    def test_object_setattr_bypasses_the_frozen_dataclass_by_design_of_python(self) -> None:
        # Target INSUFFICIENT_DATA (the one state PD-0007 still suppresses) so
        # this demonstrates the bypass actually producing a state __post_init__
        # would have rejected, not merely a frozen-attribute workaround into an
        # already-valid combination.
        m = MetricResult(value=None, sufficiency_state=SufficiencyState.INSUFFICIENT_DATA)
        object.__setattr__(m, "value", Decimal("99"))
        # No exception: this is the accepted, documented gap, not a passing check
        # on this module's guarantees. It demonstrates the frozen dataclass's
        # generated __setattr__ was bypassed, not defeated by a flaw in this
        # module specifically.
        self.assertEqual(m.value, Decimal("99"))
        self.assertEqual(m.sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)

    def test_object_new_bypasses_init_and_post_init_entirely(self) -> None:
        m = object.__new__(MetricResult)
        object.__setattr__(m, "value", Decimal("1"))
        object.__setattr__(m, "sufficiency_state", SufficiencyState.INSUFFICIENT_DATA)
        object.__setattr__(m, "reason_code", None)
        # __post_init__ never ran; AC-15 would have rejected this combination had
        # __init__ been used. This is the accepted, documented limitation, not a
        # regression: no code path this module exposes reaches object.__new__ for
        # a caller who does not deliberately import it and call it directly.
        self.assertEqual(m.value, Decimal("1"))
        self.assertEqual(m.sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)

    def test_dict_mutation_bypasses_frozen_and_post_init_entirely(self) -> None:
        # reviews/TECH_REVIEW.md round 2, N-12: a frozen dataclass without
        # __slots__ still keeps its fields in a normal writable instance
        # __dict__; frozen only overrides __setattr__, not __dict__ access. This
        # is a third, distinct vector from the two above (no object.* call at
        # all) and was missing from round 1's docstring claim. Targets
        # INSUFFICIENT_DATA + a value so the bypass demonstrably produces a state
        # __post_init__ would reject, consistent with the other two vectors above.
        m = MetricResult(value=None, sufficiency_state=SufficiencyState.INSUFFICIENT_DATA)
        m.__dict__["value"] = Decimal("42")
        # No exception: this is the accepted, documented gap (widened
        # 2026-09-04), not a passing check on this module's guarantees.
        self.assertEqual(m.value, Decimal("42"))
        self.assertEqual(m.sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)


class TypeValidationTests(unittest.TestCase):
    def test_sufficiency_state_must_be_enum_member(self) -> None:
        with self.assertRaises(TypeError):
            MetricResult(value=None, sufficiency_state="AVAILABLE")  # type: ignore[arg-type]

    def test_reason_code_must_be_enum_member_or_none(self) -> None:
        with self.assertRaises(TypeError):
            MetricResult(
                value=None,
                sufficiency_state=SufficiencyState.LIMITED,
                reason_code="STALE_DATA",  # type: ignore[arg-type]
            )


class DecimalValueTests(unittest.TestCase):
    """PD-0025 §2: the value is an exact, finite Decimal or None; nothing else."""

    def test_float_is_rejected_at_runtime(self) -> None:
        for bad in (1.30, 0.0, float("nan"), float("inf")):
            with self.subTest(value=bad), self.assertRaises(TypeError):
                MetricResult(value=bad, sufficiency_state=SufficiencyState.AVAILABLE)  # type: ignore[arg-type]

    def test_int_str_bool_are_rejected_too(self) -> None:
        for bad in (1, "1.3", True):
            with self.subTest(value=bad), self.assertRaises(TypeError):
                MetricResult(value=bad, sufficiency_state=SufficiencyState.AVAILABLE)  # type: ignore[arg-type]

    def test_non_finite_decimal_is_rejected(self) -> None:
        for bad in ("NaN", "sNaN", "Infinity", "-Infinity"):
            with self.subTest(value=bad), self.assertRaises(InvalidMetricResultError):
                MetricResult(Decimal(bad), SufficiencyState.AVAILABLE)

    def test_exact_decimal_is_kept_unchanged(self) -> None:
        big = Decimal("123456789012345678901234567890.123456789012345678901234567890")
        self.assertEqual(MetricResult(big, SufficiencyState.AVAILABLE).value, big)

    def test_a_float_still_cannot_sneak_in_on_insufficient_data(self) -> None:
        with self.assertRaises(TypeError):
            MetricResult(0.0, SufficiencyState.INSUFFICIENT_DATA)  # type: ignore[arg-type]


class NewReasonCodeCouplingTests(unittest.TestCase):
    """PD-0025 §1: each new code requires sufficiency_state != AVAILABLE."""

    NEW = (ReasonCode.UNRESOLVED_CONVENTION, ReasonCode.LEDGER_INCONSISTENT,
           ReasonCode.NOT_RECONSTRUCTABLE)

    def test_available_is_rejected(self) -> None:
        for code in self.NEW:
            with self.subTest(code=code), self.assertRaises(InvalidMetricResultError):
                MetricResult(Decimal("1"), SufficiencyState.AVAILABLE, code)

    def test_insufficient_and_limited_are_accepted(self) -> None:
        for code in self.NEW:
            with self.subTest(code=code):
                MetricResult(None, SufficiencyState.INSUFFICIENT_DATA, code)
                MetricResult(Decimal("1"), SufficiencyState.LIMITED, code)


class StaleDataNarrowingTests(unittest.TestCase):
    """Pins PD-0006's targeted exemption: STALE_DATA — and only STALE_DATA — is
    exempt from the reason-code/sufficiency-state coupling. `AVAILABLE` +
    `STALE_DATA` is representable pending the freshness axis (CP1+,
    `reviews/gates/CP0_RECONCILIATION.md` §3.1). This test pins that decision so a
    future change to it is visible in a diff, not silent.
    """

    def test_available_with_stale_data_reason_code_is_not_rejected(self) -> None:
        # PD-0007's amendment now requires AVAILABLE to carry a value, so this
        # case (kept, not deleted, per the PM's explicit instruction — it still
        # pins PD-0006's STALE_DATA exemption) needs a real value rather than
        # None: AVAILABLE + STALE_DATA remains representable, and it always was
        # going to need a value anyway, since STALE_DATA describes a metric that
        # *is* computable, just priced off non-current data.
        m = MetricResult(
            value=Decimal("1.30"),
            sufficiency_state=SufficiencyState.AVAILABLE,
            reason_code=ReasonCode.STALE_DATA,
        )
        self.assertIs(m.sufficiency_state, SufficiencyState.AVAILABLE)
        self.assertIs(m.reason_code, ReasonCode.STALE_DATA)
        self.assertEqual(m.value, Decimal("1.30"))

    def test_available_with_value_and_stale_data_reason_code_is_not_rejected(
        self,
    ) -> None:
        # Kept as a separate test from the one above even though both now carry a
        # value (the amendment made this the only shape AVAILABLE can take) —
        # this one pins the PD-0006 coupling angle specifically: AVAILABLE + a
        # value + STALE_DATA is exactly the "computable, fully supported, but
        # priced off non-current data" case PD-0006 says must remain
        # representable, independent of PD-0007's separate value requirement.
        m = MetricResult(
            value=Decimal("1.30"),
            sufficiency_state=SufficiencyState.AVAILABLE,
            reason_code=ReasonCode.STALE_DATA,
        )
        self.assertEqual(m.value, Decimal("1.30"))

    def test_stale_data_is_the_only_exempt_reason_code(self) -> None:
        # Contrast case: every other reason code fails the same construction that
        # STALE_DATA above permits. [Corrected 2026-09-05, N-21] This used to
        # construct value=None, which was no longer "the same construction" once
        # AC-15 became a total equivalence — None on AVAILABLE now fails on that
        # biconditional clause alone, before the reason-code coupling clause is
        # ever reached, so the comment's claim was false and the test could not
        # tell the two rules apart. Using value=Decimal("1.30") — the same value the
        # STALE_DATA positives above use — makes this genuinely the same
        # construction, differing only in reason_code, so a failure here is
        # attributable to the coupling clause specifically.
        for code in _COUPLED_REASON_CODES:
            with self.subTest(reason_code=code):
                with self.assertRaises(InvalidMetricResultError):
                    MetricResult(
                        value=Decimal("1.30"),
                        sufficiency_state=SufficiencyState.AVAILABLE,
                        reason_code=code,
                    )


if __name__ == "__main__":
    unittest.main()
