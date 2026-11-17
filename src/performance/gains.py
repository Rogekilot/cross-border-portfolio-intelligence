"""Realized and unrealized gain, remaining basis, the since-acquisition split and the gain aggregates (`performance/1.8` Rulings 3.3a, 3.7, 3.7a, 3.8, 3.9, 3.9a, 3.10, 9.7; tech plan 16.18).

The FIFO/1 lot book and relief records come from the ONE lot fold in `domain.replay` (`reconstruct_fifo`); this module reads them and never relieves a lot itself. Everything is exact
(tier E). A figure is a money fact in a currency; its state follows Rulings 1.4 and 1.5 through the injected aggregation.

- A lot's reporting-currency unit cost (3.7, 3.7a): `TRADE` and `RECORDED` lots at the fixing of `a` (`k = R`: no rate); an `ENTRY` lot only when `k = R`, else `MISSING_COST_BASIS`, detail
  `ACQUISITION_DATE_UNKNOWN`; an unknown lot `MISSING_COST_BASIS`, detail `UNKNOWN_BASIS`. The rate's state is the lot's state for ever.
- `RG_native = A - sum(basis)` only when every known portion's basis currency is the sale's; mixed currency is `UNSUPPORTED_ASSET` + `MIXED_CURRENCY_BASIS` (native only). `RG_R = A X(c to R, d) -
  sum(units c_R)`. A relief record that holds suppressed or TAINTED units gives `SOURCE_CONFLICT` (3.8 (1.5) item 1); a withheld record gives its own reason (item 2).
- Remaining basis (3.9a) and unrealized gain (3.9) per position; the aggregates (3.10) sum what is available or limited and state the excluded gross weight.
- Every figure carries the broker-difference label (PD-0035 section 1); a figure built on a `RECORDED` lot also says "as recorded by you" (3.7a item 7).
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from typing import Dict, List, Optional, Sequence, Tuple

from domain.currency import CurrencyCode
from domain.ledger import LedgerEvent
from domain.replay import DATE_ENTRY, DATE_RECORDED, FifoState, Lot, LotBook, Relief, ReplayDetail
from marketdata.conventions import ConventionSet
from marketdata.port import MarketDataPort
from performance.conventions import PerformanceConventionSet
from performance.flows import DataUse, _rate
from performance.inputs import SuppressionInput
from performance.numerics import RoundingPoint, apportion, to_decimal_exact, within_bounds
from performance.results import EMPTY_FRESHNESS, RATIONAL, Cause, ComputedMetric, FreshnessVector, Part, WindowUsed, sorted_causes
from performance.states import (
    CALCULATION_ERROR,
    MISSING_COST_BASIS,
    SOURCE_CONFLICT,
    UNRESOLVED_CONVENTION,
    UNSUPPORTED_ASSET,
    Valued,
    build_metric,
    insufficient_part,
    pick_reason,
    replay_reason,
)
from performance.taint import SPLIT_SUPPRESSION_CARRIED, lot_taint
from performance.valuation import HoldingValuation
from product_contract.vocabulary import SufficiencyState

INSUFFICIENT, LIMITED, AVAILABLE = SufficiencyState.INSUFFICIENT_DATA, SufficiencyState.LIMITED, SufficiencyState.AVAILABLE

UNKNOWN_BASIS = "UNKNOWN_BASIS"
ACQUISITION_DATE_UNKNOWN = "ACQUISITION_DATE_UNKNOWN"
MIXED_CURRENCY_BASIS = "MIXED_CURRENCY_BASIS"
LOCAL_AT_ACQUISITION_FX, FX_ON_COST, INTERACTION = "LOCAL_AT_ACQUISITION_FX", "FX_ON_COST", "INTERACTION"  # Ruling 9.7 (1.5): the registry order
SINCE_ACQUISITION_LINES = (LOCAL_AT_ACQUISITION_FX, FX_ON_COST, INTERACTION)

#: PD-0035 section 1 (the words are the design's): on every realized or unrealized figure.
BROKER_DIFFERENCE_LABEL = "lots are relieved first in, first out; this may differ from your broker's own lot records"
#: performance/1.6 Ruling 3.7a item 7: on a figure built on a RECORDED lot.
RECORDED_BY_YOU_LABEL = "cost and acquisition date as recorded by you"

#: Ruling 3.10 (1.5): the reasons that make a gain aggregate LIMITED with a stated weight; any other reason of an excluded item makes it INSUFFICIENT_DATA.
LIMITING_REASONS = frozenset({MISSING_COST_BASIS, UNRESOLVED_CONVENTION, UNSUPPORTED_ASSET, SOURCE_CONFLICT, "MISSING_FX_HISTORY"})


@dataclass
class GainsEnv:
    """What a gains computation reads: the reporting currency and market data, the injected rules, the DataUse the manifest cites, and the suppressions (F8 plus carried)."""

    reporting: CurrencyCode
    port: MarketDataPort
    market: ConventionSet
    conventions: PerformanceConventionSet
    use: DataUse
    suppressions: Sequence[SuppressionInput]
    retrieved_not_after: Optional[datetime.datetime] = None
    _rates: Dict[Tuple[datetime.date, str], Tuple[Optional[Fraction], Optional[Part], FreshnessVector]] = field(default_factory=dict)

    def rate(self, day: datetime.date, currency: CurrencyCode) -> Tuple[Optional[Fraction], Optional[Part], FreshnessVector]:
        key = (day, currency.code)
        if key not in self._rates:
            self._rates[key] = _rate(day, currency, self.reporting, self.port, self.market, self.use, self.retrieved_not_after)
        return self._rates[key]


def _valued(env: GainsEnv, parts: Sequence[Part], value: Optional[Fraction], fresh: FreshnessVector, ref: str) -> Valued:
    agg = env.conventions.aggregation.combine(list(parts))
    if agg.state is INSUFFICIENT:
        return Valued(INSUFFICIENT, agg.reason, None, agg.causes, fresh)
    if value is None:
        cause = Cause(ref, INSUFFICIENT.value, None, "the figure cannot be computed")
        return Valued(INSUFFICIENT, None, None, sorted_causes(agg.causes + (cause,)), fresh)
    if not within_bounds(value):
        cause = Cause(ref, INSUFFICIENT.value, CALCULATION_ERROR, "VALUE_NOT_REPRESENTABLE: size guard", "VALUE_NOT_REPRESENTABLE")
        return Valued(INSUFFICIENT, CALCULATION_ERROR, None, sorted_causes(agg.causes + (cause,)), fresh)
    return Valued(agg.state, agg.reason, value, agg.causes, fresh)


def _suppressed(env: GainsEnv, account: uuid.UUID, listing: uuid.UUID, day: datetime.date) -> Optional[SuppressionInput]:
    for s in sorted(env.suppressions, key=lambda s: (s.first_date, s.flag)):
        if s.account_id == account and s.listing_id == listing and s.covers(day):
            return s
    return None


def lot_ref(lot: Lot) -> str:
    return lot_id_text(lot)


def lot_id_text(lot: Lot) -> str:
    """The lot's identity as text: the origin event id and the out-leg ids of its hops, in order."""
    return str(lot.origin_event_id) + "".join(f":{h.out_event_id}" for h in lot.hops)


@dataclass(frozen=True)
class LotCost:
    """A lot's unit costs and the states of each: `native_part` is None unless the native basis is unknown; `reporting_part` is the state of `c_R` (None: a clean known value)."""

    unit_native: Optional[Fraction]
    unit_reporting: Optional[Fraction]
    native_part: Optional[Part]
    reporting_part: Optional[Part]
    fresh: FreshnessVector


def lot_cost(env: GainsEnv, lot: Lot) -> LotCost:
    ref = f"lot:{lot_id_text(lot)}"
    if lot.unit_cost is None or lot.basis_currency is None:  # unknown basis: MISSING_COST_BASIS (3.7, ledger-replay 6.4)
        part = insufficient_part(ref, MISSING_COST_BASIS, f"{UNKNOWN_BASIS}: the lot has no recorded basis", UNKNOWN_BASIS)
        return LotCost(None, None, part, part, EMPTY_FRESHNESS)
    if lot.basis_currency == env.reporting:
        return LotCost(lot.unit_cost, lot.unit_cost, None, None, EMPTY_FRESHNESS)  # k = R: no rate is needed, whatever the date (3.7a item 4)
    if lot.date_kind == DATE_ENTRY:  # the date it entered the portfolio is not the date it was bought: never translated (3.7)
        part = insufficient_part(ref, MISSING_COST_BASIS, f"{ACQUISITION_DATE_UNKNOWN}: an ENTRY lot in another currency has no recorded acquisition date",
                                 ACQUISITION_DATE_UNKNOWN)
        return LotCost(lot.unit_cost, None, None, part, EMPTY_FRESHNESS)
    rate, part, fresh = env.rate(lot.acquisition_date, lot.basis_currency)  # TRADE and RECORDED: the fixing of a_lambda (3.7, 3.7a)
    rep = None if rate is None else lot.unit_cost * rate
    return LotCost(lot.unit_cost, rep, None, part if part is not None else None, fresh)


def _labels(lots: Sequence[Lot]) -> Tuple[Tuple[str, str], ...]:
    out = [("caveat.lot_method", BROKER_DIFFERENCE_LABEL)]
    if any(lot.date_kind == DATE_RECORDED for lot in lots):
        out.append(("caveat.recorded", RECORDED_BY_YOU_LABEL))
    return tuple(out)


# --- realized gain (3.8) -----------------------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SaleGain:
    event: LedgerEvent
    relief: Relief
    native: Valued
    reporting: Valued
    proceeds_reporting: Optional[Fraction]
    proceeds_parts: Tuple[Part, ...]
    lots: Tuple[Lot, ...]
    details: Tuple[str, ...]


def _withheld_parts(ref: str, relief: Relief) -> List[Part]:
    return [insufficient_part(f"{ref}:relief", replay_reason(d), f"{d.value}: replay withholds the relief record", d.value) for d in relief.causes]


def realized_gain(env: GainsEnv, event: LedgerEvent, relief: Relief) -> SaleGain:
    assert event.amount is not None
    ref = f"sale:{event.event_id}"
    day = event.event_date
    proceeds = Fraction(event.amount.amount)
    sale_ccy = event.currency
    rate, rate_part, rate_fresh = env.rate(day, sale_ccy)
    proceeds_R = None if rate is None else proceeds * rate
    proceeds_parts = () if rate_part is None else (rate_part,)
    lots = tuple(relief.portions)
    details: List[str] = []
    if relief.withheld:  # item 2: a flagged position, an opaque lot or a same-day cycle: the reason of the record
        parts = _withheld_parts(ref, relief)
        details += [d.value for d in relief.causes]
        v = _valued(env, parts, None, EMPTY_FRESHNESS, ref)
        return SaleGain(event, relief, v, v, proceeds_R, proceeds_parts, lots, tuple(sorted(set(details))))
    own = _suppressed(env, relief.account_id, relief.listing_id, day)
    tainted = next((lot_taint(p, env.suppressions, day) for p in sorted(lots, key=lambda x: x.sort_key) if lot_taint(p, env.suppressions, day) is not None), None)
    if own is not None or tainted is not None:  # item 1: the ledger's quantity and the market's units disagree: the relieved basis may be in the wrong unit system
        source = own if own is not None else tainted[0]  # type: ignore[index]
        detail = SPLIT_SUPPRESSION_CARRIED if tainted is not None or SPLIT_SUPPRESSION_CARRIED in (own.flag if own else "") else ""
        part = insufficient_part(f"{ref}:suppression", source.reason, source.flag, detail)
        v = _valued(env, [part], None, EMPTY_FRESHNESS, ref)
        return SaleGain(event, relief, v, v, proceeds_R, proceeds_parts, lots, (detail,) if detail else ())
    known = [p for p in lots if p.unit_cost is not None]
    unknown = [p for p in lots if p.unit_cost is None]
    # native view
    n_parts: List[Part] = []
    for p in unknown:
        n_parts.append(insufficient_part(f"{ref}:lot:{lot_id_text(p)}", MISSING_COST_BASIS, f"{UNKNOWN_BASIS}: a relieved portion has no basis", UNKNOWN_BASIS))
    ccys = {p.basis_currency for p in known}
    if known and (len(ccys) > 1 or ccys != {sale_ccy}):  # the mixed-currency test is over KNOWN portions only (item 3)
        n_parts.append(insufficient_part(ref, UNSUPPORTED_ASSET, f"{MIXED_CURRENCY_BASIS}: the relieved lots' basis currency is not the sale's", MIXED_CURRENCY_BASIS))
    n_value = None if n_parts else proceeds - sum((p.basis for p in known if p.basis is not None), Fraction(0))
    native = _valued(env, n_parts, n_value, EMPTY_FRESHNESS, ref)
    # reporting view
    r_parts: List[Part] = list(proceeds_parts)
    fresh = rate_fresh
    unit_sum = Fraction(0)
    ok = proceeds_R is not None
    for p in lots:
        cost = lot_cost(env, p)
        fresh = fresh.union(cost.fresh)
        if cost.reporting_part is not None:
            r_parts.append(cost.reporting_part)
        if cost.unit_reporting is None:
            ok = False
        else:
            unit_sum += cost.unit_reporting * p.units
    r_value = None if not ok else proceeds_R - unit_sum  # type: ignore[operator]
    reporting = _valued(env, r_parts, r_value, fresh, ref)
    for part in n_parts + r_parts:
        details += [c.detail for c in part.causes if c.detail]
    return SaleGain(event, relief, native, reporting, proceeds_R, proceeds_parts, lots, tuple(sorted(set(details))))


# --- positions: remaining basis (3.9a), unrealized gain (3.9), since acquisition (9.7) ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class PositionGains:
    account_id: uuid.UUID
    listing_id: uuid.UUID
    book: LotBook
    holding: Optional[HoldingValuation]
    remaining_native: Dict[CurrencyCode, Fraction]  # known basis per basis currency (empty when withheld or unknown)
    remaining_native_state: Valued  # the native view's state (an exact total is never presented across currencies)
    remaining_reporting: Valued
    ug_native: Valued
    ug_reporting: Valued
    mv_reporting: Optional[Fraction]
    mv_valued: Optional[Valued]
    details: Dict[str, Tuple[str, ...]]  # lineage detail names per view: remaining.native, remaining.reporting, ug.native, ug.reporting


def position_gains(env: GainsEnv, book: LotBook, holding: Optional[HoldingValuation], day: datetime.date) -> PositionGains:
    ref = f"position:{book.account_id}/{book.listing_id}"
    details: List[str] = []
    suppression = _suppressed(env, book.account_id, book.listing_id, day)
    withheld = [insufficient_part(f"{ref}:book", replay_reason(d), f"{d.value}: replay withholds the lot book", d.value) for d in book.causes]
    n_parts: List[Part] = list(withheld)
    r_parts: List[Part] = list(withheld)
    if suppression is not None:  # 3.9a: a suppressed position's basis is withheld too (its units are in doubt)
        sp = insufficient_part(f"{ref}:suppression", SOURCE_CONFLICT, suppression.flag, SPLIT_SUPPRESSION_CARRIED if SPLIT_SUPPRESSION_CARRIED in suppression.flag else "")
        n_parts.append(sp)
        r_parts.append(sp)
    native: Dict[CurrencyCode, Fraction] = {}
    unit_sum = Fraction(0)
    r_ok = True
    fresh = EMPTY_FRESHNESS
    if not book.causes:
        for lot in book.lots:
            cost = lot_cost(env, lot)
            fresh = fresh.union(cost.fresh)
            if cost.native_part is not None:
                n_parts.append(cost.native_part)
            elif lot.basis is not None and lot.basis_currency is not None:
                native[lot.basis_currency] = native.get(lot.basis_currency, Fraction(0)) + lot.basis
            if cost.reporting_part is not None:
                r_parts.append(cost.reporting_part)
            if cost.unit_reporting is None:
                r_ok = False
            else:
                unit_sum += cost.unit_reporting * lot.units
    clean_native = not any(p.state is INSUFFICIENT for p in n_parts)
    clean_reporting = not any(p.state is INSUFFICIENT for p in r_parts)
    rem_native = _valued(env, n_parts, Fraction(sum(native.values(), Fraction(0))) if clean_native else None, EMPTY_FRESHNESS, ref + ":remaining.native")
    rem_reporting = _valued(env, r_parts, unit_sum if (r_ok and clean_reporting and not book.causes) else None, fresh, ref + ":remaining.reporting")
    # unrealized gain
    ug_n_parts = list(n_parts)
    ug_r_parts = list(r_parts)
    mv_valued: Optional[Valued] = None
    mv_R: Optional[Fraction] = None
    mv_native: Optional[Fraction] = None
    if holding is None:
        miss = insufficient_part(f"{ref}:valuation", replay_reason(book.causes[0]) if book.causes else None, "the position has no valuation", "")
        ug_n_parts.append(miss)
        ug_r_parts.append(miss)
    else:
        ug_n_parts.append(holding.native.as_part(f"{ref}:mv.native"))
        ug_r_parts.append(holding.reporting.as_part(f"{ref}:mv.reporting"))
        mv_valued = holding.reporting
        mv_R = holding.reporting.exact
        mv_native = holding.native.exact
        if holding.native_currency is not None and native and set(native) != {holding.native_currency}:  # 3.9: a native gain needs every basis in the listing's currency
            ug_n_parts.append(insufficient_part(ref, UNSUPPORTED_ASSET, f"{MIXED_CURRENCY_BASIS}: a basis currency differs from the listing's", MIXED_CURRENCY_BASIS))
    ug_n_value = None
    if holding is not None and mv_native is not None and not any(p.state is INSUFFICIENT for p in ug_n_parts):
        ug_n_value = mv_native - sum(native.values(), Fraction(0))
    ug_r_value = None
    if holding is not None and mv_R is not None and r_ok and not any(p.state is INSUFFICIENT for p in ug_r_parts) and not book.causes:
        ug_r_value = mv_R - unit_sum
    ug_native = _valued(env, ug_n_parts, ug_n_value, EMPTY_FRESHNESS, ref + ":ug.native")
    ug_reporting = _valued(env, ug_r_parts, ug_r_value, fresh.union(holding.reporting.freshness) if holding is not None else fresh, ref + ":ug.reporting")
    def names(parts: Sequence[Part]) -> Tuple[str, ...]:
        return tuple(sorted({c.detail for part in parts for c in part.causes if c.detail}))

    return PositionGains(book.account_id, book.listing_id, book, holding, native, rem_native, rem_reporting, ug_native, ug_reporting, mv_R, mv_valued,
                         {"remaining.native": names(n_parts), "remaining.reporting": names(r_parts), "ug.native": names(ug_n_parts), "ug.reporting": names(ug_r_parts)})


@dataclass(frozen=True)
class SinceAcquisition:
    lot: Lot
    valued: Valued
    parts: Tuple[Fraction, ...]  # LOCAL_AT_ACQUISITION_FX, FX_ON_COST, INTERACTION (empty when INSUFFICIENT)


def since_acquisition(env: GainsEnv, book: LotBook, lot: Lot, holding: Optional[HoldingValuation], day: datetime.date) -> SinceAcquisition:
    """Ruling 9.7 (1.5, 1.6): `UG_R(lot) = V X_D - K X_a` split into the local gain at acquisition FX, the FX on cost and their interaction (exact; sums to the total)."""
    ref = f"lot:{lot_id_text(lot)}:since"
    parts: List[Part] = []
    suppression = _suppressed(env, book.account_id, book.listing_id, day)
    if suppression is not None:
        parts.append(insufficient_part(f"{ref}:suppression", SOURCE_CONFLICT, suppression.flag, SPLIT_SUPPRESSION_CARRIED if SPLIT_SUPPRESSION_CARRIED in suppression.flag else ""))
    if lot.unit_cost is None or lot.basis_currency is None:
        parts.append(insufficient_part(ref, MISSING_COST_BASIS, f"{UNKNOWN_BASIS}: the lot has no recorded basis", UNKNOWN_BASIS))
        return SinceAcquisition(lot, _valued(env, parts, None, EMPTY_FRESHNESS, ref), ())
    if holding is None or holding.price is None:
        parts.append(insufficient_part(ref, "MISSING_PRICE_HISTORY", "the position has no price", ""))
        return SinceAcquisition(lot, _valued(env, parts, None, EMPTY_FRESHNESS, ref), ())
    parts.append(holding.reporting.as_part(f"{ref}:mv"))
    k = lot.basis_currency
    if holding.native_currency is not None and k != holding.native_currency:
        parts.append(insufficient_part(ref, UNSUPPORTED_ASSET, f"{MIXED_CURRENCY_BASIS}: the basis currency is not the listing's", MIXED_CURRENCY_BASIS))
        return SinceAcquisition(lot, _valued(env, parts, None, EMPTY_FRESHNESS, ref), ())
    fresh = holding.reporting.freshness
    if k == env.reporting:
        x_a = x_d = Fraction(1)  # k = R: all local, whatever the dates (an ENTRY lot with k = R included)
    else:
        if lot.date_kind == DATE_ENTRY:
            parts.append(insufficient_part(ref, MISSING_COST_BASIS, f"{ACQUISITION_DATE_UNKNOWN}: no recorded acquisition date", ACQUISITION_DATE_UNKNOWN))
            return SinceAcquisition(lot, _valued(env, parts, None, EMPTY_FRESHNESS, ref), ())
        rate_a, part_a, fresh_a = env.rate(lot.acquisition_date, k)
        fresh = fresh.union(fresh_a)
        if part_a is not None:
            parts.append(part_a)
        x_a = rate_a  # type: ignore[assignment]
        x_d = holding.fx_rate  # type: ignore[assignment]
        if x_a is None or x_d is None:
            return SinceAcquisition(lot, _valued(env, parts, None, fresh, ref), ())
    value = lot.units * holding.price
    cost = lot.units * lot.unit_cost
    local = (value - cost) * x_a
    fx = cost * (x_d - x_a)
    inter = (value - cost) * (x_d - x_a)
    total = value * x_d - cost * x_a
    if local + fx + inter != total:  # identity I-8 (exact): an engine fault
        parts.append(insufficient_part(ref, CALCULATION_ERROR, "IDENTITY_FAILED: I-8: the parts differ from the total", "IDENTITY_FAILED"))
        return SinceAcquisition(lot, _valued(env, parts, None, fresh, ref), ())
    return SinceAcquisition(lot, _valued(env, parts, total, fresh, ref), (local, fx, inter))


# --- aggregates (3.10) -------------------------------------------------------------------------------------------------------------------------------------------------

def _aggregate(env: GainsEnv, items: Sequence[Tuple[str, Valued, Optional[Fraction], Optional[Valued]]], ref: str) -> Valued:
    """Ruling 3.10 (1.5): `items` are `(name, gain in R, weight base |.|, the base's own Valued or None)`. Positions: weight base is |MV_R|, and an item with no weight base is UNVALUED (the
    aggregate is INSUFFICIENT with its reason). Sales: the weight base is |proceeds_R|. Nothing to sum is 0, AVAILABLE (a fact)."""
    if not items:
        return Valued(AVAILABLE, None, Fraction(0), ())
    unvalued = [(n, g, w, b) for n, g, w, b in items if w is None]
    if unvalued:
        parts = [(b if b is not None else g).as_part(f"{ref}:{n}") for n, g, w, b in unvalued]
        agg = env.conventions.aggregation.combine(parts)
        return Valued(INSUFFICIENT, agg.reason, None, agg.causes)
    included = [(n, g, w) for n, g, w, _b in items if g.state is not INSUFFICIENT]
    excluded = [(n, g, w) for n, g, w, _b in items if g.state is INSUFFICIENT]
    if excluded and any(g.reason not in LIMITING_REASONS for _n, g, _w in excluded):
        parts = [g.as_part(f"{ref}:{n}") for n, g, _w in excluded if g.reason not in LIMITING_REASONS]
        return Valued(INSUFFICIENT, pick_reason([g.reason for _n, g, _w in excluded if g.reason not in LIMITING_REASONS]), None,
                      sorted_causes(tuple(c for p in parts for c in p.causes)))
    if not included:
        parts = [g.as_part(f"{ref}:{n}") for n, g, _w in excluded]
        agg = env.conventions.aggregation.combine(parts)
        return Valued(INSUFFICIENT, agg.reason, None, agg.causes)
    total = sum((g.exact for _n, g, _w in included if g.exact is not None), Fraction(0))
    agg = env.conventions.aggregation.combine([g.as_part(f"{ref}:{n}") for n, g, _w in included])
    fresh = EMPTY_FRESHNESS
    for _n, g, _w in included:
        fresh = fresh.union(g.freshness)
    if not excluded:
        return Valued(agg.state, agg.reason, total, agg.causes, fresh)
    weight = sum((abs(w) for _n, _g, w in excluded if w is not None), Fraction(0)) / sum((abs(w) for _n, _g, w, _b in items if w is not None), Fraction(0))
    causes = sorted_causes(agg.causes + tuple(c for _n, g, _w in excluded for c in g.causes))
    reason = pick_reason([g.reason for _n, g, _w in excluded] + [agg.reason])
    return Valued(LIMITED, reason, total, causes, fresh, excluded_weight=weight)


def realized_total(env: GainsEnv, sales: Sequence[SaleGain]) -> Valued:
    items: List[Tuple[str, Valued, Optional[Fraction], Optional[Valued]]] = []
    for s in sales:
        base = None if s.proceeds_reporting is None else s.proceeds_reporting
        base_valued = None
        if base is None:  # the proceeds cannot be translated (a CNH amount, a missing rate): the weight cannot be stated
            parts = list(s.proceeds_parts)
            agg = env.conventions.aggregation.combine(parts) if parts else None
            base_valued = Valued(INSUFFICIENT, None if agg is None else agg.reason, None, () if agg is None else agg.causes)
        items.append((str(s.event.event_id), s.reporting, base, base_valued))
    return _aggregate(env, items, "realized")


def unrealized_total(env: GainsEnv, positions: Sequence[PositionGains]) -> Valued:
    items = []
    for pg in positions:
        base_valued = pg.mv_valued if pg.mv_reporting is None else None
        items.append((f"{pg.account_id}/{pg.listing_id}", pg.ug_reporting, pg.mv_reporting, base_valued))
    return _aggregate(env, items, "unrealized")


# --- metrics -----------------------------------------------------------------------------------------------------------------------------------------------------------

@dataclass
class MetricFactory:
    env: GainsEnv
    rounding: object
    window: WindowUsed
    method_id: str
    synthetic: bool
    conformant: bool
    fault: bool = False  # identity I-5 failed in the fold: an engine fault, so every figure is INSUFFICIENT_DATA + CALCULATION_ERROR

    def make(self, metric_id: str, view: str, subject: Sequence[Tuple[str, str]], valued: Valued, currency: Optional[CurrencyCode], lineage: Sequence[Tuple[str, str]] = (),
             breakdown: Tuple[Tuple[str, Decimal, Fraction], ...] = (), details: Sequence[str] = ()) -> ComputedMetric:
        if self.fault:
            cause = Cause("identity", INSUFFICIENT.value, CALCULATION_ERROR, "IDENTITY_FAILED: I-5: lot conservation failed in the fold", "IDENTITY_FAILED")
            valued = Valued(INSUFFICIENT, CALCULATION_ERROR, None, sorted_causes(valued.causes + (cause,)), valued.freshness)
            breakdown = ()
        return build_metric(metric_id, view, tuple(subject), valued, currency, self.rounding, self.window, self.method_id, self.synthetic, self.conformant,  # type: ignore[arg-type]
                            tuple(lineage), point=RoundingPoint.PRESENT_MONEY, unit="CURRENCY_AMOUNT", numeric_basis=RATIONAL, breakdown=breakdown, details=tuple(details))
