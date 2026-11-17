"""I2 — the metric-state model (source PRD §32, P5; `decisions/product/PD-0006`,
including its second amendment of 2026-09-04; `decisions/product/PD-0007`,
2026-09-04, which corrects AC-15 itself).

`MetricResult` is the envelope every computed number is required to travel in
(`implementation/FEATURE_TECH_PLAN.md` §3.1, §4.2). This module builds two
structural rules:

1. **AC-15, as corrected by PD-0007 and its 2026-09-04 amendment.** `value is None`
   **if and only if** `sufficiency_state is INSUFFICIENT_DATA`. `AVAILABLE` and
   `LIMITED` both **require** a value; `INSUFFICIENT_DATA` forbids one. This is a
   total equivalence, not a one-sided prohibition.

   **This rule has moved twice.** The original AC-15 read "non-`AVAILABLE` cannot
   carry a value," which this module built faithfully — and which was wrong: it made
   `LIMITED` render identically to `INSUFFICIENT_DATA` (both suppressed), collapsing
   a three-state vocabulary to two states' worth of meaning, and it made
   `designs/FEATURE_DESIGN.md` §D3.2's `LIMITED` row — "the computed value plus a
   mandatory, non-dismissible qualifier" — describe an object this module refused to
   construct. `designer-04` (`design_review` round 2, finding BF-3) found the
   contradiction by running this module's own test suite against the design
   document. PD-0007's first ruling corrected that to "`LIMITED` **may** carry a
   value" — permitted, not required — reasoning that inventing a stronger rule
   without evidence would be its own overreach. `designer-04` then found the second
   half of the gap (`design_review` round 3, finding BF-4): `MetricResult(value=None,
   sufficiency_state=LIMITED)` was still legal, and §D3.2's `LIMITED` row has no
   branch for a value-less `LIMITED` — it is written entirely in terms of "the
   computed value." The same defect shape recurred: the contract permitting a state
   the design cannot render. PD-0007's amendment closes the whole gap class rather
   than patching the one instance: `AVAILABLE` was equally unconstrained and equally
   incoherent (a metric that is "available" and absent is not a state this product
   should express), so both `AVAILABLE` and `LIMITED` now *require* a value, and only
   `INSUFFICIENT_DATA` forbids one. See PD-0007's amendment for the full argument,
   including the check for a legitimate value-less `AVAILABLE`-or-`LIMITED` metric
   that turned up none.
   **PD-0025 (2026-09-30):** `value` is `Optional[Decimal]` (finite; a `float` is
   rejected at runtime), and the coupling in rule 2 also covers `UNRESOLVED_CONVENTION`,
   `LEDGER_INCONSISTENT` and `NOT_RECONSTRUCTABLE`. The rest of this docstring predates
   PD-0025 and still speaks of five coupled codes and a float-valued example: read it with
   that amendment. **PD-0030 §1 (2026-10-01):** `SOURCE_CONFLICT` and `MISSING_PRICE_HISTORY`
   join the coupled set (each requires a non-`AVAILABLE` state).
2. **The targeted reason-code coupling (PD-0006, second amendment; closes
   `reviews/TECH_REVIEW.md` B-1/B-2). Unchanged by PD-0007 — do not conflate the
   two.** `reason_code` in
   `{UNSUPPORTED_ASSET, MISSING_BENCHMARK, MISSING_COST_BASIS, MISSING_FX_HISTORY,
   CALCULATION_ERROR}` requires `sufficiency_state != AVAILABLE`. `STALE_DATA` is the
   **only** reason code exempt from this rule — `AVAILABLE` + `STALE_DATA` remains
   constructible, with or without a value. This rule is orthogonal to rule 1 above:
   it still forbids `AVAILABLE` + one of the five, but a `LIMITED` metric may now
   freely combine a value with any reason code, including one of the five (e.g.
   `LIMITED` + a value + `MISSING_COST_BASIS` is valid — the metric is computable on
   a weak basis *because* the cost basis is missing, which is exactly what
   `LIMITED` exists to express).

## Why rule 2 changed from this module's first version, stated plainly

The first version of this module built *no* coupling between `reason_code` and
`sufficiency_state` at all, reasoning that a blanket rule would either forbid
`AVAILABLE` + `STALE_DATA` (wrong — PD-0006 established that combination as real) or
require inventing which reason codes should be exempt from the blanket rule (a call
this module believed was not its authority to make).

`technical_review` (`reviews/TECH_REVIEW.md` B-2, confirmed by the PM's second
amendment to PD-0006) showed the second half of that reasoning was false on the
record: PD-0006's own text already names the exemption, verbatim —
*"`STALE_DATA` is not shaped like the other five reason codes. The other five
describe a condition under which a metric cannot be properly computed."* Nothing
needed inventing. Going blanket instead of targeted left a real hole:
`MetricResult(value=1.30, sufficiency_state=AVAILABLE, reason_code=MISSING_BENCHMARK)`
constructed cleanly and would render, under `designs/FEATURE_DESIGN.md` §D3.2, as an
unqualified `1.30` — a judgment with no reference point (P4) and a number the product
cannot justify (§41.3). This module now builds the rule PD-0006 actually specifies:
targeted at the five, exempting only `STALE_DATA`, with no threshold invented and no
`quant_analyst` input required — the exemption is a fact about which of the six
reason codes describes an inability to compute, not a sufficiency threshold.

## Enforcement: what is actually sealed, and what is not (`reviews/TECH_REVIEW.md`
AC-15 finding, NR-1)

`MetricResult` is a `frozen=True` dataclass whose `__post_init__` validates both
rules above and raises `InvalidMetricResultError` before the constructor call
returns, so ordinary construction cannot produce an invalid instance. Beyond
construction, this module additionally closes two further escape hatches
`technical_review` identified by static analysis:

- **Subclassing.** `__init_subclass__` unconditionally rejects any attempt to
  subclass `MetricResult`. `technical_review` flagged the subclass vector as "the
  important one": a subclass overriding `__post_init__` without calling
  `super().__post_init__()` would satisfy `isinstance(x, MetricResult)` while
  silently voiding both rules above, with no dunder trickery required. Forbidding
  subclassing entirely closes this — CP1 needs a field this type does not have
  (e.g. a freshness field), it composes a new type or extends via a wrapping type,
  it does not extend this one.
- **`copy.deepcopy` / pickle round-trips.** A custom `__reduce__` makes both go
  through the real constructor (`MetricResult(value, sufficiency_state,
  reason_code)`) rather than the default object-reduction protocol, which would
  otherwise reconstruct field-by-field without re-invoking `__post_init__` and
  would silently carry forward a tampered instance's invalid state. `dataclasses`
  gives no such protection by default; this module adds it.

**What remains genuinely unsealed, stated honestly rather than papered over — widened
2026-09-04 per `reviews/TECH_REVIEW.md` round 2, N-12:** `object.__setattr__(instance,
"sufficiency_state", ...)`, `object.__new__(MetricResult)` (allocating an instance
without ever calling `__init__`/`__post_init__`), and — the vector N-12 added, which
the previous wording of this paragraph did not name — direct mutation of the
instance's own `__dict__` (`instance.__dict__["sufficiency_state"] = ...`; a frozen
`dataclass` without `__slots__` still keeps its fields in a normal writable instance
`__dict__`, and frozen only overrides `__setattr__`, not `__dict__` access) all bypass
every guarantee this module builds. None of these three is specific to this class —
each is a fundamental property of the CPython object model, and no pure-Python class
can prevent a caller willing to reach past its own public interface using `object`'s
own methods or the instance's own `__dict__` directly. `technical_review` characterized
the first two as "the usual Python caveats," not defects, and this module agrees, and
extends the same judgment to the third: closing any of them would require a C
extension, `__slots__` combined with further metaclass work, or a similarly
disproportionate measure this increment does not build. Recorded here as a known,
accepted limitation rather than a claim this module does not back: **ordinary code —
construction, assignment, subclassing, `replace`, `copy`, `pickle` — cannot produce an
invalid `MetricResult`. Any code that deliberately reaches past this type's public
interface — via `object.__setattr__`, `object.__new__`, or direct `__dict__`
mutation — can.**
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional, Tuple

from product_contract.vocabulary import ReasonCode, SufficiencyState


class InvalidMetricResultError(ValueError):
    """Raised when an attempted `MetricResult` construction would violate AC-15 as
    corrected by PD-0007 and its amendment (`value is None` iff
    `sufficiency_state is INSUFFICIENT_DATA`) or the targeted reason-code coupling
    (PD-0006's second amendment: a blocking reason code with `AVAILABLE`)."""


# The five reason codes PD-0006's second amendment couples to sufficiency_state.
# STALE_DATA is deliberately excluded — see module docstring and PD-0006.
_REASON_CODES_REQUIRING_NON_AVAILABLE: frozenset = frozenset(
    {
        ReasonCode.UNSUPPORTED_ASSET,
        ReasonCode.MISSING_BENCHMARK,
        ReasonCode.MISSING_COST_BASIS,
        ReasonCode.MISSING_FX_HISTORY,
        ReasonCode.CALCULATION_ERROR,
        # PD-0025 §1
        ReasonCode.UNRESOLVED_CONVENTION,
        ReasonCode.LEDGER_INCONSISTENT,
        ReasonCode.NOT_RECONSTRUCTABLE,
        # PD-0030 §1 (OD-1)
        ReasonCode.SOURCE_CONFLICT,
        ReasonCode.MISSING_PRICE_HISTORY,
    }
)


@dataclass(frozen=True)
class MetricResult:
    """The envelope every computed metric value travels in.

    Fields:
        value: the presentable number; `None` if and only if `sufficiency_state`
            is `INSUFFICIENT_DATA` — `AVAILABLE` and `LIMITED` both require one.
        sufficiency_state: required; exactly one `SufficiencyState` member.
        reason_code: optional; `None`, or exactly one `ReasonCode` member.

    Structural rules (see module docstring for provenance):
        1. AC-15, corrected by PD-0007 and its amendment: `value is None` if and
           only if `sufficiency_state is INSUFFICIENT_DATA`. `AVAILABLE` and
           `LIMITED` both require a value; `INSUFFICIENT_DATA` forbids one.
        2. PD-0006 (second amendment), unchanged by PD-0007: `reason_code` in the
           five non-`STALE_DATA` codes implies `sufficiency_state != AVAILABLE`.
           `STALE_DATA` is exempt.

    Deliberately excluded from this increment: `methodology_ref` and any
    computation-context reference (`implementation/FEATURE_TECH_PLAN.md` §3.1
    mentions both as later fields on the same entity). Both point at concepts
    this increment does not build — a populated methodology registry (I3 ships
    the registry empty, AC-17) and an actual computation — so adding them now
    would be structure with nothing real behind it. This type cannot be
    subclassed to add them later (see module docstring); CP1 extends by
    composition or a new type.
    """

    value: Optional[Decimal]
    sufficiency_state: SufficiencyState
    reason_code: Optional[ReasonCode] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Closes the subclass escape hatch technical_review identified: a subclass
        # overriding __post_init__ without calling super() would satisfy
        # isinstance(x, MetricResult) while silently voiding AC-15 and the
        # reason-code coupling. MetricResult is not designed to be extended.
        raise TypeError(
            "MetricResult may not be subclassed. Extend via composition or a "
            "new type instead of inheritance."
        )

    def __post_init__(self) -> None:
        # PD-0025 §2: the value is an exact, finite Decimal or None. A float (or int,
        # str, bool...) is rejected; there is no coercion.
        if self.value is not None:
            if isinstance(self.value, float) or not isinstance(self.value, Decimal):
                raise TypeError(
                    "value must be None or a decimal.Decimal, never a float or any "
                    f"other type (PD-0025), got {type(self.value)!r}"
                )
            if not self.value.is_finite():
                raise InvalidMetricResultError(
                    f"value must be a finite Decimal (PD-0025), got {self.value!r}"
                )
        if not isinstance(self.sufficiency_state, SufficiencyState):
            raise TypeError(
                "sufficiency_state must be a product_contract.vocabulary."
                f"SufficiencyState member, got {self.sufficiency_state!r}"
            )
        if self.reason_code is not None and not isinstance(self.reason_code, ReasonCode):
            raise TypeError(
                "reason_code must be None or a product_contract.vocabulary."
                f"ReasonCode member, got {self.reason_code!r}"
            )
        is_insufficient = self.sufficiency_state is SufficiencyState.INSUFFICIENT_DATA
        if is_insufficient and self.value is not None:
            raise InvalidMetricResultError(
                "AC-15 violation (PD-0007 amendment): sufficiency_state="
                f"{self.sufficiency_state.value} cannot carry a presentable "
                f"value (got value={self.value!r}). INSUFFICIENT_DATA must be "
                "constructed with value=None."
            )
        if not is_insufficient and self.value is None:
            raise InvalidMetricResultError(
                "AC-15 violation (PD-0007 amendment): sufficiency_state="
                f"{self.sufficiency_state.value} requires a presentable value "
                "(got value=None). Only INSUFFICIENT_DATA may be constructed "
                "with value=None; AVAILABLE and LIMITED both require one."
            )
        if (
            self.reason_code in _REASON_CODES_REQUIRING_NON_AVAILABLE
            and self.sufficiency_state is SufficiencyState.AVAILABLE
        ):
            raise InvalidMetricResultError(
                "PD-0006 violation: reason_code="
                f"{self.reason_code.value} requires sufficiency_state != "
                "AVAILABLE (STALE_DATA is the only reason code exempt from "
                "this rule)."
            )

    def __reduce__(self) -> Tuple[Any, Tuple[Any, ...]]:
        # Forces copy.deepcopy and pickle to reconstruct through __init__ ->
        # __post_init__ rather than the default object-reduction protocol, which
        # would otherwise restore field values directly and could silently
        # propagate an instance tampered with via object.__setattr__ (see module
        # docstring's "what remains genuinely unsealed" section).
        return (self.__class__, (self.value, self.sufficiency_state, self.reason_code))
