"""The absolute gain, the time-weighted return in segment form, the daily-product check and annualization
(`performance/1.0` Rulings 5.1 to 5.6 and 7.1 to 7.2; tech plan 16.5). Pure functions over valuations and flows; exact rationals (tier E); no float.

DEFINITIONS (all values in the reporting currency `R`, tier E; Ruling 5.1). For each calendar day `D` in `(B, E]`:

    V_D = TV_R(D)                                       (the total of Ruling 1.4)
    beta_D = V_{D-1} + I^C_D                            the day's capital base (cash inflows at the START of the day, Ruling 4.2)
    g_D = V_D + O_D - I^K_D - beta_D                    the day's investment gain;   r_D = g_D / beta_D
    TWR(B, E] = product of (1 + r_D) - 1;    G(B, E] = sum g_D = V_E - V_B - (sum I^C + sum I^K - sum O)

SEGMENT FORM (Ruling 5.2): a flow-free run collapses to the ratio of its end values, so the TWR needs exactly `V_B`, `V_E` and, for each flow day `D_j`,
both `V_{D_j - 1}` and `V_{D_j}`, plus the flows. A valuation on any other day is NOT an input (its being INSUFFICIENT does not touch the TWR). The daily
product must equal the segment product exactly (identity I-2); `daily_twr_factor` computes it for the runtime check.

A BASE THAT IS ZERO OR NEGATIVE (Ruling 5.3): `0/0` is 1 (lineage `ZERO_CAPITAL_RUN`); any other denominator <= 0 makes the TWR INSUFFICIENT_DATA with
NO reason and the detail `NON_POSITIVE_BASE`. States (Ruling 5.5): the worst of every required valuation and every flow, the reason chosen by Ruling 1.5.
No fallback to Modified Dietz or any approximation, ever.

ANNUALIZATION (Ruling 7): only when `Y >= 1`; `(1 + R)^(1/Y) - 1` computed as `exp(ln(1+R)/Y)` at precision 50 from the tier-E `R`; `Y < 1` is
INSUFFICIENT_DATA (no reason, detail `PERIOD_SHORTER_THAN_ONE_YEAR`); `R = -1` is `TOTAL_LOSS`. Never applied to a gain, an attribution line or a component.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from performance.conventions import FlowClass, PerformanceConventionSet
from performance.flows import ValuedFlow
from performance.numerics import growth_root, irr_is_unique, solve_irr, within_bounds
from performance.results import EMPTY_FRESHNESS, Cause, FreshnessVector, Part, sorted_causes
from performance.states import CALCULATION_ERROR, Valued, insufficient_part
from product_contract.vocabulary import SufficiencyState

INSUFFICIENT = SufficiencyState.INSUFFICIENT_DATA
NON_POSITIVE_BASE = "NON_POSITIVE_BASE"
NEGATIVE_VALUE = "NEGATIVE_VALUE"
ZERO_CAPITAL_RUN = "ZERO_CAPITAL_RUN"
PERIOD_SHORTER_THAN_ONE_YEAR = "PERIOD_SHORTER_THAN_ONE_YEAR"
TOTAL_LOSS = "TOTAL_LOSS"
NEGATIVE_GROWTH_FACTOR = "NEGATIVE_GROWTH_FACTOR"
ONE = Fraction(1)


@dataclass(frozen=True)
class DayFlows:
    day: datetime.date
    inflow_cash: Fraction  # I^C_D
    inflow_kind: Fraction  # I^K_D
    outflow: Fraction      # O_D (cash and in kind)


def group_flows(flows: Sequence[ValuedFlow]) -> Dict[datetime.date, DayFlows]:
    """The value-bearing external flows by day (Ruling 5.1). A flow that could not be valued contributes nothing HERE: it is carried as a part of the
    state, and the metric is INSUFFICIENT_DATA before any number is formed."""
    cash_in: Dict[datetime.date, Fraction] = {}
    kind_in: Dict[datetime.date, Fraction] = {}
    out: Dict[datetime.date, Fraction] = {}
    days = set()
    for f in flows:
        d = f.event.event_date
        days.add(d)
        if f.valued.exact is None:
            continue
        if f.flow_class is FlowClass.EXTERNAL_INFLOW_CASH:
            cash_in[d] = cash_in.get(d, Fraction(0)) + f.valued.exact
        elif f.flow_class is FlowClass.EXTERNAL_INFLOW_KIND:
            kind_in[d] = kind_in.get(d, Fraction(0)) + f.valued.exact
        elif f.flow_class in (FlowClass.EXTERNAL_OUTFLOW_CASH, FlowClass.EXTERNAL_OUTFLOW_KIND):
            out[d] = out.get(d, Fraction(0)) + f.valued.exact
    zero = Fraction(0)
    return {d: DayFlows(d, cash_in.get(d, zero), kind_in.get(d, zero), out.get(d, zero)) for d in sorted(days)}


def ratio(numerator: Fraction, denominator: Fraction) -> Tuple[Optional[Fraction], str]:
    """Ruling 5.3 (performance/1.1): a positive denominator with a non-negative numerator gives the ratio (a factor of exactly 0 is a real total loss,
    TWR = -1); a positive denominator with a NEGATIVE numerator means the value fell below zero and gives no value (`NEGATIVE_VALUE`); `0/0` is 1
    (`ZERO_CAPITAL_RUN`); any other denominator <= 0 gives no value (`NON_POSITIVE_BASE`). A negative factor is never presented."""
    if denominator > 0:
        if numerator < 0:
            return None, NEGATIVE_VALUE
        return numerator / denominator, ""
    if denominator == 0 and numerator == 0:
        return ONE, ZERO_CAPITAL_RUN
    return None, NON_POSITIVE_BASE


def _one_day(day: datetime.date) -> datetime.timedelta:
    return datetime.timedelta(days=1)


def _worst(conventions: PerformanceConventionSet, parts: Sequence[Part], extra: Sequence[Part] = ()):
    return conventions.aggregation.combine(list(parts) + list(extra))


@dataclass(frozen=True)
class ReturnOutcome:
    valued: Valued
    details: Tuple[str, ...] = ()
    factors: Tuple[Tuple[str, Fraction], ...] = ()  # the labelled factors of the segment product (lineage)


def twr_segments(
    base: datetime.date, end: datetime.date, flows: Sequence[ValuedFlow], valuation: Callable[[datetime.date], Valued],
    conventions: PerformanceConventionSet,
) -> ReturnOutcome:
    """The TWR over `(base, end]` in segment form (Rulings 5.1, 5.2, 5.3, 5.5). `valuation(day)` returns the total `TV_R` of that day as a `Valued`."""
    by_day = group_flows(flows)
    flow_days = sorted(d for d in by_day if base < d <= end)
    required = sorted({base, end} | {d - datetime.timedelta(days=1) for d in flow_days} | set(flow_days))
    vals = {d: valuation(d) for d in required}
    parts = [vals[d].as_part(f"valuation@{d.isoformat()}") for d in required]
    parts += [f.valued.as_part(f"flow:{f.event.event_id}") for f in flows if base < f.event.event_date <= end]
    fresh = EMPTY_FRESHNESS
    for v in list(vals.values()) + [f.valued for f in flows]:
        fresh = fresh.union(v.freshness)
    agg = _worst(conventions, parts)
    if agg.state is INSUFFICIENT:
        return ReturnOutcome(Valued(INSUFFICIENT, agg.reason, None, agg.causes, fresh))

    details: List[str] = []
    factors: List[Tuple[str, Fraction]] = []
    product = ONE
    bad: Optional[Part] = None
    bad_detail = ""
    prev_day = base
    one = datetime.timedelta(days=1)

    def step(label: str, num: Fraction, den: Fraction, when: datetime.date) -> bool:
        nonlocal product, bad, bad_detail
        factor, detail = ratio(num, den)
        if factor is None:
            bad_detail = detail
            note = (f"{NON_POSITIVE_BASE}: the capital base on {when.isoformat()} is {den.numerator}/{den.denominator}, not positive"
                    if detail == NON_POSITIVE_BASE else
                    f"{NEGATIVE_VALUE}: the value on {when.isoformat()} fell below zero (numerator {num.numerator}/{num.denominator} "
                    f"over a positive base)")
            bad = insufficient_part(f"twr@{when.isoformat()}", None, note, detail)
            return False
        if detail:
            details.append(detail)
        factors.append((label, factor))
        product *= factor
        return True

    def v(day: datetime.date) -> Fraction:
        exact = vals[day].exact
        assert exact is not None
        return exact

    for d in flow_days:
        before = d - one
        # a run of no days (the flow day directly follows the previous boundary) has no factor: nothing is divided, nothing is flagged
        if before > prev_day and not step(f"run:{prev_day.isoformat()}..{before.isoformat()}", v(before), v(prev_day), prev_day):
            break
        f = by_day[d]
        if not step(f"flow:{d.isoformat()}", v(d) + f.outflow - f.inflow_kind, v(before) + f.inflow_cash, d):
            break
        prev_day = d
    else:
        if end > prev_day:
            step(f"run:{prev_day.isoformat()}..{end.isoformat()}", v(end), v(prev_day), prev_day)
    if bad is not None:
        agg2 = _worst(conventions, parts, [bad])
        return ReturnOutcome(Valued(INSUFFICIENT, agg2.reason, None, agg2.causes, fresh), (bad_detail,), tuple(factors))
    twr = product - ONE
    if not within_bounds(twr):
        cause = Cause("twr", INSUFFICIENT.value, CALCULATION_ERROR, "VALUE_NOT_REPRESENTABLE: size guard", "VALUE_NOT_REPRESENTABLE")
        return ReturnOutcome(Valued(INSUFFICIENT, CALCULATION_ERROR, None, sorted_causes(agg.causes + (cause,)), fresh))
    return ReturnOutcome(Valued(agg.state, agg.reason, twr, agg.causes, fresh), tuple(sorted(set(details))), tuple(factors))


def daily_twr_factor(
    base: datetime.date, end: datetime.date, flows: Sequence[ValuedFlow], valuation: Callable[[datetime.date], Valued],
) -> Optional[Fraction]:
    """The DAILY product `prod (1 + r_D)` over every day of `(base, end]` (Ruling 5.1), or None when some daily value does not exist or some
    day's base is not positive. Identity I-2: whenever it exists it equals the segment product EXACTLY."""
    by_day = group_flows(flows)
    one = datetime.timedelta(days=1)
    product = ONE
    prev = valuation(base).exact
    if prev is None:
        return None
    day = base + one
    while day <= end:
        cur = valuation(day).exact
        if cur is None:
            return None
        f = by_day.get(day)
        inflow_cash = Fraction(0) if f is None else f.inflow_cash
        numerator = cur + (Fraction(0) if f is None else f.outflow - f.inflow_kind)
        factor, _ = ratio(numerator, prev + inflow_cash)
        if factor is None:
            return None
        product *= factor
        prev = cur
        day += one
    return product


def daily_gain_sum(
    base: datetime.date, end: datetime.date, flows: Sequence[ValuedFlow], valuation: Callable[[datetime.date], Valued],
) -> Optional[Fraction]:
    """`sum g_D` over every day of `(base, end]` (identity I-3), or None when some daily value does not exist."""
    by_day = group_flows(flows)
    one = datetime.timedelta(days=1)
    total = Fraction(0)
    prev = valuation(base).exact
    if prev is None:
        return None
    day = base + one
    while day <= end:
        cur = valuation(day).exact
        if cur is None:
            return None
        f = by_day.get(day)
        i_c = Fraction(0) if f is None else f.inflow_cash
        total += cur + (Fraction(0) if f is None else f.outflow - f.inflow_kind) - (prev + i_c)
        prev = cur
        day += one
    return total


def absolute_gain(
    base: datetime.date, end: datetime.date, flows: Sequence[ValuedFlow], valuation: Callable[[datetime.date], Valued],
    conventions: PerformanceConventionSet,
) -> Valued:
    """`G(B, E] = V_E - V_B - (sum I^C + sum I^K - sum O)` (Ruling 5.1): the only money gain over a window, exact, independent of the lot method
    and never derived from a TWR. Its inputs are `V_B`, `V_E` and every flow."""
    v_b, v_e = valuation(base), valuation(end)
    window_flows = [f for f in flows if base < f.event.event_date <= end]
    parts = [v_b.as_part(f"valuation@{base.isoformat()}"), v_e.as_part(f"valuation@{end.isoformat()}")]
    parts += [f.valued.as_part(f"flow:{f.event.event_id}") for f in window_flows]
    fresh = v_b.freshness.union(v_e.freshness)
    for f in window_flows:
        fresh = fresh.union(f.valued.freshness)
    agg = conventions.aggregation.combine(parts)
    if agg.state is INSUFFICIENT:
        return Valued(INSUFFICIENT, agg.reason, None, agg.causes, fresh)
    assert v_b.exact is not None and v_e.exact is not None
    by_day = group_flows(window_flows)
    net = Fraction(0)
    for f in by_day.values():
        net += f.inflow_cash + f.inflow_kind - f.outflow
    gain = v_e.exact - v_b.exact - net
    if not within_bounds(gain):
        cause = Cause("gain", INSUFFICIENT.value, CALCULATION_ERROR, "VALUE_NOT_REPRESENTABLE: size guard", "VALUE_NOT_REPRESENTABLE")
        return Valued(INSUFFICIENT, CALCULATION_ERROR, None, sorted_causes(agg.causes + (cause,)), fresh)
    return Valued(agg.state, agg.reason, gain, agg.causes, fresh)


NO_CAPITAL = "NO_CAPITAL"
IRR_NOT_DEFINED = "IRR_NOT_DEFINED"
IRR_UNIQUENESS_NOT_ESTABLISHED = "IRR_UNIQUENESS_NOT_ESTABLISHED"


@dataclass(frozen=True)
class MwrOutcome:
    valued: Valued
    details: Tuple[str, ...] = ()
    rational: bool = False  # the period MWR is an exact rational (the two-time and `G = 0` cases), not a 50-digit approximation
    flows: Tuple[Tuple[Fraction, Fraction], ...] = ()  # the investor cash flows (tau, amount) the root was solved on: lineage and the identities
    interior: bool = False  # some flow lies strictly inside the window (tau not 0 or 1), so identity I-6 does not apply


def mwr_flows(
    base: datetime.date, end: datetime.date, flows: Sequence[ValuedFlow], v_b: Fraction, v_e: Fraction,
) -> Tuple[Tuple[Tuple[Fraction, Fraction], ...], bool]:
    """Ruling 6.1: the investor's cash flows over `(B, E]`, `n = E - B` days, as `(tau, amount)` sorted by tau with the amounts at one tau summed exactly:
    `-V_B` at 0; a cash inflow dated `D` is `-I^C_D` at `(D - 1 - B)/n` (the start of `D`); an in-kind inflow is `-I^K_D` and an outflow `+O_D`, both at `(D - B)/n`
    (the end of `D`); `+V_E` at 1. Zero amounts are dropped. The second value is whether any inflow exists (Ruling 6.4's `NO_CAPITAL`)."""
    n = (end - base).days
    by_k: Dict[int, Fraction] = {}

    def put(k: int, amount: Fraction) -> None:
        by_k[k] = by_k.get(k, Fraction(0)) + amount

    put(0, -v_b)
    any_inflow = False
    for day, f in group_flows([f for f in flows if base < f.event.event_date <= end]).items():
        if f.inflow_cash != 0 or f.inflow_kind != 0:
            any_inflow = True
        put((day - base).days - 1, -f.inflow_cash)
        put((day - base).days, f.outflow - f.inflow_kind)
    put(n, v_e)
    return tuple((Fraction(k, n), amount) for k, amount in sorted(by_k.items()) if amount != 0), any_inflow


def mwr_period(
    base: datetime.date, end: datetime.date, flows: Sequence[ValuedFlow], valuation: Callable[[datetime.date], Valued],
    conventions: PerformanceConventionSet,
) -> MwrOutcome:
    """The period MWR `rho = g* - 1` over `(B, E]` (Rulings 6.1 to 6.4) on the same values, flows and timing as the TWR. Its inputs are `V_B`, `V_E` and every flow
    (NOT the interior valuations: a day with a negative base is just a flow pattern). States (6.4): any required input INSUFFICIENT: that input's reason; no capital:
    `NO_CAPITAL`; the first non-zero flow positive or no positive flow: `IRR_NOT_DEFINED`; no bracket: `IRR_OUT_OF_RANGE`; the pure-investment test fails:
    `IRR_UNIQUENESS_NOT_ESTABLISHED` (each of these INSUFFICIENT_DATA with NO reason code); a LIMITED input makes the MWR LIMITED, as for the TWR."""
    v_b, v_e = valuation(base), valuation(end)
    window_flows = [f for f in flows if base < f.event.event_date <= end]
    parts = [v_b.as_part(f"valuation@{base.isoformat()}"), v_e.as_part(f"valuation@{end.isoformat()}")]
    parts += [f.valued.as_part(f"flow:{f.event.event_id}") for f in window_flows]
    fresh = v_b.freshness.union(v_e.freshness)
    for f in window_flows:
        fresh = fresh.union(f.valued.freshness)
    agg = _worst(conventions, parts)
    if agg.state is INSUFFICIENT:
        return MwrOutcome(Valued(INSUFFICIENT, agg.reason, None, agg.causes, fresh))
    assert v_b.exact is not None and v_e.exact is not None
    cfs, any_inflow = mwr_flows(base, end, window_flows, v_b.exact, v_e.exact)

    def refuse(detail: str, note: str) -> MwrOutcome:
        bad = insufficient_part(f"mwr@{end.isoformat()}", None, f"{detail}: {note}", detail)
        agg2 = _worst(conventions, parts, [bad])
        return MwrOutcome(Valued(INSUFFICIENT, agg2.reason, None, agg2.causes, fresh), (detail,), flows=cfs)

    if not cfs or (v_b.exact == 0 and not any_inflow):
        return refuse(NO_CAPITAL, "no capital was invested in the window")
    first_nonzero = cfs[0][1]
    if first_nonzero > 0 or not any(amount > 0 for _tau, amount in cfs):
        return refuse(IRR_NOT_DEFINED, "the first non-zero investor flow is positive, or no flow is positive")
    root = solve_irr(cfs)
    if root.g is None:
        return refuse(root.detail or IRR_OUT_OF_RANGE, "no bracket for the root within 2^-64 .. 2^64")
    if not irr_is_unique(cfs, root.g):
        return refuse(IRR_UNIQUENESS_NOT_ESTABLISHED, "the investor becomes a net borrower at the solved rate: another root may exist")
    rho = root.g - ONE
    if not within_bounds(rho):
        cause = Cause("mwr", INSUFFICIENT.value, CALCULATION_ERROR, "VALUE_NOT_REPRESENTABLE: size guard", "VALUE_NOT_REPRESENTABLE")
        return MwrOutcome(Valued(INSUFFICIENT, CALCULATION_ERROR, None, sorted_causes(agg.causes + (cause,)), fresh), flows=cfs)
    interior = any(tau not in (0, 1) for tau, _a in cfs)
    return MwrOutcome(Valued(agg.state, agg.reason, rho, agg.causes, fresh), (), root.rational, cfs, interior)


@dataclass(frozen=True)
class AnnualizedOutcome:
    valued: Valued
    year_fraction: Fraction
    details: Tuple[str, ...] = ()
    rational: bool = False  # True when the figure is an exact rational (Y = 1: the annualized figure IS the period figure, Ruling 7.1)


def annualize(twr: Valued, years: Fraction, conventions: PerformanceConventionSet) -> AnnualizedOutcome:
    """Ruling 7.2 for a TWR `Valued` (its state, causes and freshness are inherited): only when `years >= 1`; `exp(ln(1 + R)/Y) - 1` at precision 50;
    `Y < 1` is INSUFFICIENT_DATA with no reason and the detail `PERIOD_SHORTER_THAN_ONE_YEAR`; `R = -1` is `TOTAL_LOSS`."""
    if twr.exact is None:
        return AnnualizedOutcome(Valued(INSUFFICIENT, twr.reason, None, twr.causes, twr.freshness), years)

    def refuse(detail: str, note: str, reason: Optional[str] = None) -> AnnualizedOutcome:
        part = insufficient_part("annualized", reason, note, detail)
        agg = conventions.aggregation.combine([twr.as_part("twr"), part])
        return AnnualizedOutcome(Valued(INSUFFICIENT, agg.reason, None, agg.causes, twr.freshness), years, (detail,))

    if years < 1:
        return refuse(PERIOD_SHORTER_THAN_ONE_YEAR,
                      f"{PERIOD_SHORTER_THAN_ONE_YEAR}: the window is {years.numerator}/{years.denominator} years; the period return is the figure")
    growth = ONE + twr.exact
    if growth == 0:
        return refuse(TOTAL_LOSS, f"{TOTAL_LOSS}: the return is -1, an annualized rate is undefined")
    if growth < 0:
        # performance/1.2 Ruling 7.2: reaching this is an ENGINE FAULT (Ruling 5.3 makes a negative factor unreachable): CALCULATION_ERROR, loud and alertable
        return refuse(NEGATIVE_GROWTH_FACTOR, f"{NEGATIVE_GROWTH_FACTOR}: 1 + R is negative, no real root exists (an engine fault)", CALCULATION_ERROR)
    if years == 1:  # (1 + R)^(1/1) - 1 = R: exact, no transcendental step (Ruling 7.1: a one-year window annualizes to itself)
        return AnnualizedOutcome(Valued(twr.state, twr.reason, twr.exact, twr.causes, twr.freshness), years, rational=True)
    root = growth_root(growth, years)
    if root is None or not within_bounds(root):
        cause = Cause("annualized", INSUFFICIENT.value, CALCULATION_ERROR, "VALUE_NOT_REPRESENTABLE", "VALUE_NOT_REPRESENTABLE")
        return AnnualizedOutcome(Valued(INSUFFICIENT, CALCULATION_ERROR, None, sorted_causes(twr.causes + (cause,)), twr.freshness), years)
    return AnnualizedOutcome(Valued(twr.state, twr.reason, root - ONE, twr.causes, twr.freshness), years)
