"""The valuation layer (`performance/1.0` Rulings 1.1 to 1.8; tech plan 16.3): positions x price-of-date x FX, dividend receivables and cash, in
two views, with state propagation, a freshness vector, the stale weight and a labelled partial figure.

Pure function of a CP1 `ReplayedState` and the CP2 `ValuationInputs` (what `assemble_valuation_inputs` gathered at the as-of date) plus the
injected conventions and the valuation suppressions. No I/O, no clock, no float, no rounding (tier E: exact rationals).

- NATIVE view: `quantity x RAW close`, needing no FX (Ruling 1.1). A missing rate degrades only the REPORTING view.
- REPORTING view: `native value x exact FX rate` (Ruling 1.2); a CNH amount is INSUFFICIENT_DATA + MISSING_FX_HISTORY (the CP2 lookup says so).
- Cash (Ruling 1.3): `balance x rate`, signed; a zero balance is not emitted by replay and needs no rate.
- Dividend receivables (Ruling 1.3, 8.1): a DIVIDEND recorded with `ex_date < event_date` is a receivable of its amount on every day
  `ex_date <= D < pay date`, valued at that day's rate. (Income RECOGNITION is CP3c; the receivable's contribution to the value is here.)
- Totals (Ruling 1.4): `TV_R` is the exact sum of its components. Any INSUFFICIENT_DATA component makes it INSUFFICIENT_DATA with no value; the
  lineage lists EVERY unvalued component. Otherwise any LIMITED component makes it LIMITED + STALE_DATA with the STALE WEIGHT stated
  (gross weights `sum |v|` over LIMITED components against all). Otherwise AVAILABLE (+ STALE_DATA if any component carries it).
- The freshness vector (Ruling 1.6) travels with every total.
- `partial` (PD-0035 section 2): when the total is suppressed, a SEPARATE labelled figure of the components that CAN be valued, with the count and
  list of the excluded ones. It is never the total and never a denominator.
- The price is the as-traded close of the as-of date and the quantity is the replayed quantity at that date (no adjusted series is read:
  market-data Ruling 2.5). Where F8-B says they are NOT in the same unit (a suppression), the entry is INSUFFICIENT_DATA.
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from domain.currency import CurrencyCode
from domain.ledger import EventType
from domain.replay import AccountStatus, ReplayedState, SequencedEvent
from marketdata.consumption import FXInput, QuoteInput, ValuationInputs
from marketdata.contracts import QuoteObservation
from marketdata.conventions import ConventionSet
from marketdata.manifest import DataKind, DataSetRef
from marketdata.port import FXLookup, InstrumentResolverPort, MarketDataPort, QuoteLookup
from marketdata.states import fx_input_state, price_input_state
from performance.conventions import PerformanceConventionSet
from performance.inputs import SuppressionInput
from performance.numerics import within_bounds
from performance.results import (
    EMPTY_FRESHNESS,
    Cause,
    Excluded,
    FreshEntry,
    FreshnessVector,
    Part,
    sorted_causes,
)
from performance.states import (
    CALCULATION_ERROR,
    NOT_RECONSTRUCTABLE,
    Valued,
    insufficient_part,
    part_from_input,
    part_from_metric,
)
from product_contract.vocabulary import SufficiencyState

INSUFFICIENT = SufficiencyState.INSUFFICIENT_DATA
LIMITED = SufficiencyState.LIMITED
RETRIEVED_AFTER_INSTANT = "RETRIEVED_AFTER_CURRENT_INSTANT"
#: lineage details a corporate-action suppression can name (performance/1.1 Example V-2a: an unapplied corroborated split is `SPLIT_NOT_APPLIED`)
SUPPRESSION_DETAILS = ("SPLIT_SUPPRESSION_CARRIED", "SPLIT_NOT_APPLIED", "SYSTEM_SPLIT_REVERSED_BY_USER", "OVERLAPPING_SPLIT_WINDOWS",
                       "CALENDAR_COVERAGE_GAP", "SYNTHETIC_EVIDENCE_APPEND_BARRED")


@dataclass(frozen=True)
class Receivable:
    """A dividend declared with an ex-date before its pay date (Ruling 8.1), in the event currency."""

    account_id: uuid.UUID
    event_id: uuid.UUID
    listing_id: Optional[uuid.UUID]
    currency: CurrencyCode
    amount: Fraction
    ex_date: datetime.date
    pay_date: datetime.date


def accrued_receivables(live: Iterable[SequencedEvent], day: datetime.date) -> Tuple[Receivable, ...]:
    """The receivables outstanding at the END of `day` among the live events: `ex_date <= day < pay date` (Ruling 8.1)."""
    out = []
    for item in live:
        e = item.event
        if (e.event_type is EventType.DIVIDEND and e.ex_date is not None and e.amount is not None
                and e.ex_date < e.event_date and e.ex_date <= day < e.event_date):
            out.append(Receivable(e.account_id, e.event_id, e.listing_id, e.currency, Fraction(e.amount.amount),
                                  e.ex_date, e.event_date))
    return tuple(sorted(out, key=lambda r: (str(r.account_id), str(r.event_id))))


@dataclass(frozen=True)
class HoldingValuation:
    account_id: uuid.UUID
    listing_id: uuid.UUID
    native_currency: Optional[CurrencyCode]
    quantity: Optional[Fraction]
    price: Optional[Fraction]
    price_date_used: Optional[datetime.date]
    price_missed_count: Optional[int]
    fx_rate: Optional[Fraction]
    fx_date_used: Optional[datetime.date]
    native: Valued
    reporting: Valued
    # performance/1.9 Ruling 1.1b: the session of the last admissible print at or before D (the print the missed-session count is counted from). Lineage only, reported also when the
    # value is withheld (5 or more missed sessions, a split suppression, an unresolved quantity); equal to `price_date_used` when a close values the holding; None when no print exists.
    last_print_date: Optional[datetime.date] = None


@dataclass(frozen=True)
class CashValuation:
    account_id: uuid.UUID
    currency: CurrencyCode
    amount: Optional[Fraction]
    fx_rate: Optional[Fraction]
    fx_date_used: Optional[datetime.date]
    native: Valued
    reporting: Valued


@dataclass(frozen=True)
class ReceivableValuation:
    receivable: Receivable
    fx_rate: Optional[Fraction]
    fx_date_used: Optional[datetime.date]
    native: Valued
    reporting: Valued


@dataclass(frozen=True)
class BlockedAccount:
    """An account that cannot be reconstructed at the as-of date (before its snapshot): it blocks every total."""

    account_id: uuid.UUID
    cause: Cause


@dataclass(frozen=True)
class PartialValuation:
    """PD-0035 section 2: the value of the components that CAN be valued, with the ones it leaves out. Never the total."""

    valued: Valued
    included: int
    excluded: Tuple[Excluded, ...]

    @property
    def excluded_holdings(self) -> int:
        return sum(1 for e in self.excluded if e.kind == "POSITION")


@dataclass(frozen=True)
class PortfolioValuation:
    as_of: datetime.date
    ledger_version: int
    reporting_currency: CurrencyCode
    holdings: Tuple[HoldingValuation, ...]
    cash: Tuple[CashValuation, ...]
    receivables: Tuple[ReceivableValuation, ...]
    blocked: Tuple[BlockedAccount, ...]
    native_totals: Tuple[Tuple[CurrencyCode, Valued], ...]
    reporting_total: Valued
    partial: Optional[PartialValuation]
    synthetic: bool

    def components(self) -> Tuple[Tuple[str, Valued], ...]:
        """The reporting-view components in the FIXED line order of the decomposition: positions, cash, receivables."""
        out: List[Tuple[str, Valued]] = []
        for h in self.holdings:
            out.append((f"holding:{h.account_id}/{h.listing_id}", h.reporting))
        for c in self.cash:
            out.append((f"cash:{c.account_id}/{c.currency.code}", c.reporting))
        for r in self.receivables:
            out.append((f"receivable:{r.receivable.account_id}/{r.receivable.event_id}", r.reporting))
        return tuple(out)


def _combine(parts: Sequence[Part], conventions: PerformanceConventionSet, exact: Optional[Fraction],
             freshness: FreshnessVector) -> Valued:
    agg = conventions.aggregation.combine(parts)
    if agg.state is INSUFFICIENT or exact is None:
        if agg.state is not INSUFFICIENT:  # a value-bearing state but no value: the size guard or a missing leg
            cause = Cause("value", INSUFFICIENT.value, CALCULATION_ERROR, "VALUE_NOT_REPRESENTABLE: no exact value",
                          "VALUE_NOT_REPRESENTABLE")
            return Valued(INSUFFICIENT, CALCULATION_ERROR, None, sorted_causes(agg.causes + (cause,)), freshness)
        return Valued(agg.state, agg.reason, None, agg.causes, freshness)
    return Valued(agg.state, agg.reason, exact, agg.causes, freshness)


def _product(left: Optional[Fraction], right: Optional[Fraction]) -> Optional[Fraction]:
    if left is None or right is None:
        return None
    value = left * right
    return value if within_bounds(value) else None


def total_of(values: Sequence[Valued], conventions: PerformanceConventionSet, ref: str, extra: Sequence[Part] = ()) -> Valued:
    """Ruling 1.4: combine states through the injected rule and sum the exact values when the result is not INSUFFICIENT_DATA; state the stale
    weight for a LIMITED total (gross weights)."""
    parts = [v.as_part(f"{ref}[{i}]") for i, v in enumerate(values)] + list(extra)
    fresh = EMPTY_FRESHNESS
    for v in values:
        fresh = fresh.union(v.freshness)
    agg = conventions.aggregation.combine(parts)
    if agg.state is INSUFFICIENT:
        return Valued(agg.state, agg.reason, None, agg.causes, fresh)
    total = Fraction(0)
    gross = Fraction(0)
    stale = Fraction(0)
    for v in values:
        assert v.exact is not None  # the rule must not return a value-bearing state over an INSUFFICIENT part
        total += v.exact
        gross += abs(v.exact)
        if v.state is LIMITED:
            stale += abs(v.exact)
    if not within_bounds(total):
        cause = Cause(ref, INSUFFICIENT.value, CALCULATION_ERROR, "VALUE_NOT_REPRESENTABLE: size guard",
                      "VALUE_NOT_REPRESENTABLE")
        return Valued(INSUFFICIENT, CALCULATION_ERROR, None, sorted_causes(agg.causes + (cause,)), fresh)
    weight = None
    causes = agg.causes
    if agg.state is LIMITED and gross != 0:
        weight = stale / gross
    elif agg.state is LIMITED:
        # performance/1.2 Ruling 1.4 item 2: every component is worth exactly 0, so the share is 0/0 and is NOT stated; the total stays LIMITED + STALE_DATA
        causes = sorted_causes(causes + (Cause(ref, LIMITED.value, None, "STALE_SHARE_UNDEFINED: the gross value is 0, so no stale share is stated",
                                               "STALE_SHARE_UNDEFINED"),))
    return Valued(agg.state, agg.reason, total, causes, fresh, weight)


# --- extra FX lookups (a receivable's currency need not be held as cash or a position) ---------------------------------------------

def extend_fx(inputs: ValuationInputs, currencies: Iterable[CurrencyCode], port: MarketDataPort,
              market: ConventionSet) -> ValuationInputs:
    """`inputs` plus the FX lookup (to the reporting currency, at the same as-of date) of every currency not yet looked up."""
    have = {f.currency for f in inputs.fx}
    extra = sorted({c for c in currencies if c != inputs.reporting_currency and c not in have}, key=lambda c: c.code)
    if not extra:
        return inputs
    added = tuple(FXInput(c, port.fx_on(c, inputs.reporting_currency, inputs.as_of, market)) for c in extra)
    fx = tuple(sorted(inputs.fx + added, key=lambda f: f.currency.code))
    refs = [r for r in inputs.data_set_refs if r.kind is not DataKind.FX]
    consumed = [f for item in fx for f in item.lookup.consumed]
    ids = dict(inputs.convention_ids)
    refs.append(DataSetRef.build(DataKind.FX, inputs.release_id, consumed, ids, inputs.as_of, inputs.as_of,
                                 market.convention_set_id))
    synthetic = inputs.synthetic or any(f.lookup.synthetic for f in added)
    return dataclasses.replace(inputs, fx=fx, data_set_refs=tuple(sorted(refs, key=lambda r: r.kind.value)),
                               synthetic=synthetic)


# --- freshness entries ------------------------------------------------------------------------------------------------------------

CalendarIdOf = Callable[[Optional[str]], Optional[str]]


def price_freshness(lookup: Optional[QuoteLookup], mic: Optional[str], calendar_id_of: Optional[CalendarIdOf] = None) -> FreshnessVector:
    """Ruling 1.6 (performance/1.2): ONE entry per exchange CALENDAR (keyed by `calendar_id`, listing the MICs it governs among the holdings): the oldest
    session used, the largest missed-session count and the freshness state of the price lookup (UNKNOWN if none). Where the calendar of a MIC cannot be
    named (no calendars, none or several govern it) the entry is keyed by the MIC itself (kind `EXCHANGE`)."""
    calendar_id = None if calendar_id_of is None else calendar_id_of(mic)
    kind, key = ("EXCHANGE_CALENDAR", calendar_id) if calendar_id is not None else ("EXCHANGE", mic or "?")
    mics = () if mic is None else (mic,)
    if lookup is None or lookup.freshness is None:
        return FreshnessVector((FreshEntry(kind, key, None if lookup is None else lookup.date_used,
                                           None if lookup is None else lookup.missed_count, "UNKNOWN", mics),), ("UNKNOWN",))
    f = lookup.freshness
    return FreshnessVector((FreshEntry(kind, key, lookup.date_used, lookup.missed_count, f.state.value, mics),),
                           (f.delay_status.value,))


def fx_freshness(currency: CurrencyCode, lookup: Optional[FXLookup]) -> FreshnessVector:
    """Ruling 1.6, one currency: the fixing date used, the missed-fixing count and the worst leg freshness (UNKNOWN if none)."""
    if lookup is None or not lookup.leg_freshness:
        return FreshnessVector((FreshEntry("CURRENCY", currency.code, None if lookup is None else lookup.date_used,
                                           None if lookup is None else lookup.missed_count, "UNKNOWN"),), ("UNKNOWN",))
    rank = {"CURRENT": 0, "STALE": 1, "UNKNOWN": 2}
    worst = max((f.state.value for f in lookup.leg_freshness), key=lambda s: rank.get(s, 2))
    delays = tuple(sorted({f.delay_status.value for f in lookup.leg_freshness}))
    return FreshnessVector((FreshEntry("CURRENCY", currency.code, lookup.date_used, lookup.missed_count, worst),), delays)


def retrieved_after(lineage_sources: Iterable[object], bound: Optional[datetime.datetime]) -> bool:
    """True if any reading was retrieved after `bound` (Current mode reads only files retrieved at or before the instant, Ruling 1.7)."""
    if bound is None:
        return False
    for reading in lineage_sources:
        retrieved = getattr(getattr(getattr(reading, "observation", None), "lineage", None), "retrieved_at", None)
        if retrieved is not None and retrieved > bound:
            return True
    return False


def value_portfolio(
    state: ReplayedState, inputs: ValuationInputs, suppressions: Sequence[SuppressionInput],
    conventions: PerformanceConventionSet, resolver: Optional[InstrumentResolverPort] = None,
    receivables: Sequence[Receivable] = (), retrieved_not_after: Optional[datetime.datetime] = None,
    calendar_id_of: Optional[CalendarIdOf] = None,
) -> PortfolioValuation:
    """`retrieved_not_after` is a DEFENCE IN DEPTH only: Current mode runs over `M_t` (performance/1.2 Ruling 1.7), where no file retrieved after `t` exists; a
    selected reading that nevertheless carries a later retrieval time is refused."""
    reporting = inputs.reporting_currency
    D = inputs.as_of
    quotes: Dict[uuid.UUID, QuoteInput] = {q.listing_id: q for q in inputs.quotes}
    fx: Dict[CurrencyCode, FXInput] = {f.currency: f for f in inputs.fx}

    def fx_leg(currency: Optional[CurrencyCode]) -> Tuple[Optional[Fraction], Optional[datetime.date], Optional[Part], FreshnessVector]:
        """(rate, date used, part, freshness). The reporting currency needs no rate and no freshness (X(R to R) is 1)."""
        if currency is None:
            return None, None, insufficient_part("fx:?", None, "no native currency is known, so no FX lookup was made"), EMPTY_FRESHNESS
        if currency == reporting:
            return Fraction(1), None, None, EMPTY_FRESHNESS
        item = fx.get(currency)
        ref = f"fx:{currency.code}->{reporting.code}"
        fresh = fx_freshness(currency, None if item is None else item.lookup)
        if item is None:
            return None, None, insufficient_part(ref, None, "no FX lookup was made for this currency"), fresh
        st = fx_input_state(item.lookup)
        part = part_from_input(ref, st)
        rate = item.lookup.rate
        if st.state is not INSUFFICIENT and retrieved_after(item.lookup.legs, retrieved_not_after):
            return None, item.lookup.date_used, insufficient_part(
                ref, None, f"{RETRIEVED_AFTER_INSTANT}: a leg was retrieved after the Current-mode instant",
                RETRIEVED_AFTER_INSTANT), fresh
        if st.state is INSUFFICIENT or rate is None:
            if st.state is not INSUFFICIENT:
                return None, item.lookup.date_used, insufficient_part(ref, None, "the lookup carries no rate"), fresh
            return None, item.lookup.date_used, part, fresh
        return rate, item.lookup.date_used, part, fresh

    def active_suppression(account_id: uuid.UUID, listing_id: uuid.UUID) -> Optional[SuppressionInput]:
        for s in sorted(suppressions, key=lambda s: (s.first_date, s.flag)):
            if s.account_id == account_id and s.listing_id == listing_id and s.covers(D):
                return s
        return None

    holdings: List[HoldingValuation] = []
    cash: List[CashValuation] = []
    recv: List[ReceivableValuation] = []
    blocked: List[BlockedAccount] = []

    for account in state.accounts:
        if account.status is AccountStatus.NOT_RECONSTRUCTABLE:
            blocked.append(BlockedAccount(account.account_id, Cause(
                f"account:{account.account_id}", INSUFFICIENT.value, NOT_RECONSTRUCTABLE,
                f"before the snapshot date {account.snapshot_date}")))
            continue
        for p in account.positions:
            lid = p.listing_id
            ref = f"holding:{account.account_id}/{lid}"
            qty_part = part_from_metric(f"quantity:{ref}", p.quantity, [d.value for d in p.quantity_detail])
            quantity = None if p.quantity.value is None else Fraction(p.quantity.value)
            q = quotes.get(lid)
            price: Optional[Fraction] = None
            currency: Optional[CurrencyCode] = None
            price_date: Optional[datetime.date] = None
            missed: Optional[int] = None
            mic = None if resolver is None else resolver.exchange_mic(lid)
            if q is None:
                price_part = insufficient_part(f"price:{lid}", None, "no quote lookup was made for this listing")
            else:
                st = price_input_state(q.lookup)
                price_part = part_from_input(f"price:{lid}", st)
                currency = q.native_currency
                price_date, missed = q.lookup.date_used, q.lookup.missed_count
                sel = q.lookup.selected
                if st.state is not INSUFFICIENT:
                    if sel is None or not isinstance(sel.observation, QuoteObservation):
                        price_part = insufficient_part(f"price:{lid}", None, "the lookup selected no reading")
                    elif retrieved_after((sel,), retrieved_not_after):
                        price_part = insufficient_part(
                            f"price:{lid}", None, f"{RETRIEVED_AFTER_INSTANT}: the close was retrieved after the Current-mode instant",
                            RETRIEVED_AFTER_INSTANT)
                    else:
                        price = Fraction(sel.observation.price)
            native_parts: List[Part] = [qty_part, price_part]
            sup = active_suppression(account.account_id, lid)
            if sup is not None:
                detail = next((d for d in SUPPRESSION_DETAILS if d in sup.flag), "")
                native_parts.append(insufficient_part(f"suppression:{ref}", sup.reason, sup.flag, detail))
            native_exact = _product(quantity, price) if all(x.state is not INSUFFICIENT for x in native_parts) else None
            price_fresh = price_freshness(None if q is None else q.lookup, mic, calendar_id_of)
            native = _combine(native_parts, conventions, native_exact, price_fresh)
            rate, fx_date, fx_part, fx_fresh = fx_leg(currency)
            rep_parts = native_parts + ([fx_part] if fx_part is not None else [])
            rep_exact = _product(native.exact, rate) if all(x.state is not INSUFFICIENT for x in rep_parts) else None
            reporting_v = _combine(rep_parts, conventions, rep_exact, price_fresh.union(fx_fresh))
            last_print = price_date
            if last_print is None and q is not None:  # withheld: the readings the lookup considered still say when the listing was last printed
                dates = [r.observation.value_date for r in q.lookup.readings if isinstance(r.observation, QuoteObservation)]
                last_print = max(dates) if dates else None
            holdings.append(HoldingValuation(account.account_id, lid, currency, quantity, price, price_date, missed,
                                             rate, fx_date, native, reporting_v, last_print))
        currencies = sorted({c.balance.currency for c in account.cash} | set(account.unrepresentable_cash),
                            key=lambda c: c.code)
        for ccy in currencies:
            ref = f"cash:{account.account_id}/{ccy.code}"
            balance = state.cash_balance(account.account_id, ccy)
            part = part_from_metric(ref, balance)
            amount = None if balance.value is None else Fraction(balance.value)
            native = _combine([part], conventions, amount if part.state is not INSUFFICIENT else None, EMPTY_FRESHNESS)
            rate, fx_date, fx_part, fx_fresh = fx_leg(ccy)
            rep_parts = [part] + ([fx_part] if fx_part is not None else [])
            rep_exact = _product(native.exact, rate) if all(x.state is not INSUFFICIENT for x in rep_parts) else None
            cash.append(CashValuation(account.account_id, ccy, amount, rate, fx_date, native,
                                      _combine(rep_parts, conventions, rep_exact, fx_fresh)))

    reconstructable = {a.account_id for a in state.accounts if a.status is not AccountStatus.NOT_RECONSTRUCTABLE}
    for r in receivables:
        if r.account_id not in reconstructable:
            continue
        native = Valued(SufficiencyState.AVAILABLE, None, r.amount, (), EMPTY_FRESHNESS)
        rate, fx_date, fx_part, fx_fresh = fx_leg(r.currency)
        rep_parts = [native.as_part("receivable")] + ([fx_part] if fx_part is not None else [])
        rep_exact = _product(native.exact, rate) if all(x.state is not INSUFFICIENT for x in rep_parts) else None
        recv.append(ReceivableValuation(r, rate, fx_date, native, _combine(rep_parts, conventions, rep_exact, fx_fresh)))

    blocked_parts = [Part(b.cause.ref, INSUFFICIENT, NOT_RECONSTRUCTABLE, (b.cause,)) for b in blocked]
    if not state.accounts:
        blocked_parts.append(insufficient_part("ledger", None, "NO_LIVE_LEDGER_EVENTS: no account has a live event at this version",
                                               "NO_LIVE_LEDGER_EVENTS"))
    # entries that cannot be assigned to a native currency block every native total (conservative, stated)
    unassigned = [h.native.as_part(f"holding:{h.account_id}/{h.listing_id}") for h in holdings
                  if h.native_currency is None and h.native.state is INSUFFICIENT]
    ccys = sorted({h.native_currency for h in holdings if h.native_currency is not None}
                  | {c.currency for c in cash} | {r.receivable.currency for r in recv}, key=lambda c: c.code)
    native_totals: List[Tuple[CurrencyCode, Valued]] = []
    for ccy in ccys:
        items = ([h.native for h in holdings if h.native_currency == ccy] + [c.native for c in cash if c.currency == ccy]
                 + [r.native for r in recv if r.receivable.currency == ccy])
        native_totals.append((ccy, total_of(items, conventions, f"total:{ccy.code}", blocked_parts + unassigned)))
    entries = [h.reporting for h in holdings] + [c.reporting for c in cash] + [r.reporting for r in recv]
    reporting_total = total_of(entries, conventions, "total", blocked_parts)

    partial: Optional[PartialValuation] = None
    if reporting_total.state is INSUFFICIENT and not blocked_parts:
        partial = _partial(holdings, cash, recv, conventions)
    return PortfolioValuation(inputs.as_of, state.ledger_version, reporting, tuple(holdings), tuple(cash), tuple(recv),
                              tuple(blocked), tuple(native_totals), reporting_total, partial, inputs.synthetic)


def _partial(holdings: Sequence[HoldingValuation], cash: Sequence[CashValuation], recv: Sequence[ReceivableValuation],
             conventions: PerformanceConventionSet) -> PartialValuation:
    # Ruling 1.4a: if the SET of holdings itself is unknown (a quantity that is inconsistent or split-unresolved), a partial sum over an unknown set cannot
    # state what it leaves out: INSUFFICIENT_DATA with that reason and no value.
    unknown = [h for h in holdings if h.quantity is None]
    if unknown:
        parts = [Part(f"holding:{h.account_id}/{h.listing_id}", INSUFFICIENT, None,
                      tuple(c for c in h.native.causes if c.ref.startswith("quantity:")) or h.native.causes) for h in unknown]
        agg = conventions.aggregation.combine(parts)
        return PartialValuation(Valued(INSUFFICIENT, agg.reason, None, agg.causes), 0, ())
    included: List[Valued] = []
    excluded: List[Excluded] = []
    for h in holdings:
        if h.reporting.state is INSUFFICIENT:
            excluded.append(Excluded(f"holding:{h.account_id}/{h.listing_id}", "POSITION",
                                     None if h.native_currency is None else h.native_currency.code,
                                     "unknown quantity" if h.quantity is None else _text(h.quantity), h.reporting.causes))
        else:
            included.append(h.reporting)
    for c in cash:
        if c.reporting.state is INSUFFICIENT:
            excluded.append(Excluded(f"cash:{c.account_id}/{c.currency.code}", "CASH", c.currency.code,
                                     "unknown amount" if c.amount is None else _text(c.amount), c.reporting.causes))
        else:
            included.append(c.reporting)
    for r in recv:
        if r.reporting.state is INSUFFICIENT:
            excluded.append(Excluded(f"receivable:{r.receivable.account_id}/{r.receivable.event_id}", "RECEIVABLE",
                                     r.receivable.currency.code, _text(r.receivable.amount), r.reporting.causes))
        else:
            included.append(r.reporting)
    if not included:
        cause = Cause("partial", INSUFFICIENT.value, None, "NO_VALUED_COMPONENT: nothing can be valued", "NO_VALUED_COMPONENT")
        valued = Valued(INSUFFICIENT, None, None, (cause,))
    else:
        valued = total_of(included, conventions, "partial")
    return PartialValuation(valued, len(included), tuple(excluded))


def _text(value: Fraction) -> str:
    """A native quantity or amount as exact text: an integer, or the fraction `n/d` (a recorded fact is terminating, so it is
    normally a decimal; the text is for lineage only)."""
    from performance.numerics import to_decimal_exact  # noqa: PLC0415 (local: keeps the module header short)

    dec = to_decimal_exact(value)
    return format(dec, "f") if dec is not None else f"{value.numerator}/{value.denominator}"
