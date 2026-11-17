"""I1 — canonical product vocabulary.

These are the terms the source PRD (`Cross_Border_Portfolio_Intelligence_PRD_v1_1.md`)
uses with precision. Downstream code (CP1 and later) must import these names rather
than redefining an equivalent enum locally — a second, slightly different
`SufficiencyState` in an analytics module would silently fork the vocabulary this
product's claims depend on.

Provenance:
- `SufficiencyState`, `ReasonCode` — source PRD §32 ("Data Sufficiency and
  Availability States"), layered per
  `decisions/product/PD-0006-metric-state-vocabulary-is-layered.md`. §32 itself calls
  its nine items "suggested conceptual states"; PD-0006 is the product-contract
  decision that fixes their shape as two layers rather than a flat nine-value enum.
- `ReferencePoint` — P4 ("every judgment needs a reference point"), source PRD §3.
  P4 names exactly three kinds of reference point: a benchmark, the user's own
  stated policy, or the portfolio's own history. This enum exists so that any code
  which cites a comparison basis (an Insight, a claim, a rendered judgment) can name
  *which* of the three it is using rather than leaving the reference implicit —
  implicit reference points are exactly what P4 exists to forbid.

Out of scope here (CP1+, gated by HG1): any threshold that decides when a metric
crosses from one `SufficiencyState` to another (minimum observations, lookback,
frequency) — those are `quant_analyst`'s methodology authority (§33, §44.4), not a
vocabulary question, and none is set or implied by this module.
"""

from __future__ import annotations

from enum import Enum, unique


@unique
class SufficiencyState(Enum):
    """Whether a metric is supported by enough data to present a value.

    Required on every metric (PD-0006). Exactly one of these three — never a
    fourth, and never absent.
    """

    AVAILABLE = "AVAILABLE"
    """Supported by sufficient data; may present a value."""

    LIMITED = "LIMITED"
    """Computable, but on a basis weak enough that the caveat changes the
    conclusion. May not present an unqualified value (see `metric_state.py`)."""

    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    """Not computable to a standard the product will stand behind. No value is
    presented (source PRD §32, P5)."""


@unique
class ReasonCode(Enum):
    """Explains a non-`AVAILABLE` sufficiency state. Nullable, zero-or-one per
    metric — a reason code is optional even when the state is not `AVAILABLE`;
    "not enough observations" is a complete answer on its own (PD-0006).

    **Coupling to `SufficiencyState` (PD-0006, second amendment; enforced in
    `metric_state.MetricResult`, not by this enum itself):** `UNSUPPORTED_ASSET`,
    `MISSING_BENCHMARK`, `MISSING_COST_BASIS`, `MISSING_FX_HISTORY`, and
    `CALCULATION_ERROR` each describe a condition under which a metric *cannot* be
    properly computed, and each requires `sufficiency_state != AVAILABLE`.
    `STALE_DATA` is the **only** exception: a metric can be fully computable and
    `AVAILABLE` while priced off non-current data (source PRD P10, NFR-008 — cross-
    market prices are never simultaneously real-time), so `STALE_DATA` carries no
    such implication and remains valid alongside `AVAILABLE`. Ordinary, expected
    staleness is additionally carried by a separate freshness axis
    (`designs/FEATURE_DESIGN.md` §D5) that this increment does not build; where the
    threshold sits for staleness severe enough to independently justify demoting a
    metric off `AVAILABLE` is `quant_analyst`'s and is not set here. This enum
    records the terms; `metric_state.MetricResult` enforces the coupling.
    """

    STALE_DATA = "STALE_DATA"
    UNSUPPORTED_ASSET = "UNSUPPORTED_ASSET"
    MISSING_BENCHMARK = "MISSING_BENCHMARK"
    MISSING_COST_BASIS = "MISSING_COST_BASIS"
    MISSING_FX_HISTORY = "MISSING_FX_HISTORY"
    CALCULATION_ERROR = "CALCULATION_ERROR"
    UNRESOLVED_CONVENTION = "UNRESOLVED_CONVENTION"
    """PD-0025 §1: the result is blocked by a methodology convention no one has
    ruled on yet (e.g. lot depletion, fractional split). Requires a non-
    `AVAILABLE` state."""
    LEDGER_INCONSISTENT = "LEDGER_INCONSISTENT"
    """PD-0025 §1: the recorded ledger contradicts itself (e.g. a negative share
    quantity). Requires a non-`AVAILABLE` state."""
    NOT_RECONSTRUCTABLE = "NOT_RECONSTRUCTABLE"
    """PD-0025 §1: the requested date is before the account's recorded history
    begins (a snapshot account). Requires a non-`AVAILABLE` state."""
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    """PD-0030 §1 (OD-1): two inputs that must agree do not and the conflict is
    unresolved (two price sources, a value outside a published bound, a ledger split
    against a corroborated corporate action). Requires a non-`AVAILABLE` state."""
    MISSING_PRICE_HISTORY = "MISSING_PRICE_HISTORY"
    """PD-0030 §1 (OD-1): the listing has no usable price history for the requested
    date; the counterpart of `MISSING_FX_HISTORY`. Requires a non-`AVAILABLE` state."""


@unique
class ReferencePoint(Enum):
    """The kind of comparison basis a judgment cites (P4). Every judgment needs
    exactly one of these three — a judgment with none is the false-precision
    failure mode P4 exists to prevent (source PRD §3, §41.3).
    """

    BENCHMARK = "BENCHMARK"
    """A selected benchmark series (source PRD §13.1)."""

    USER_POLICY = "USER_POLICY"
    """The user's own stated constraint or objective (source PRD §25, P7) — never
    invented on the user's behalf."""

    PORTFOLIO_HISTORY = "PORTFOLIO_HISTORY"
    """The portfolio's own prior state or track record."""
