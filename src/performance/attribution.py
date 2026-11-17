"""Attribution: the exact daily money decomposition, the window sums, the Carino-linked percentage components and the per-holding, per-currency, per-market and per-account
breakdowns (`performance/1.8` Rulings 9.1 to 9.6, 8.5, 2.4 and 11.1; tech plan 16.19).

THE DAILY LINES (Ruling 9.1). For each calendar day `D` in `(B, E]` and each position `(a, l)` held at the end of `D-1`:
    sigma = n/o if a SPLIT dated D applies, else 1;  q0 = q(D-1) sigma;  P0 = P(l, D-1) / sigma;  P1 = P(l, D);  X0 = X(c(l) to R, D-1);  X1 = X(c(l) to R, D)
    price        q0 (P1 - P0) X0                       (holdings) and each trade's result against the close: BUY q_e P1 X1 - A_e X(c_e, D); SELL A_e X(c_e, D) - q_e P1 X1
    FX           q0 P0 (X1 - X0) per position;  m0 (X1_k - X0_k) per start cash balance;  r0 (X1 - X0) per start dividend receivable
    interaction  q0 (P1 - P0)(X1 - X0)
    income, fees, known taxes, financing costs and the conversion result: the lines of `lines.py` (Rulings 8.1 to 8.5), each at its own date's fixing
Flows, in-kind offsets, internal transfers and the settlement of a receivable contribute 0. The eight lines are in the registry order of Ruling 9.2 with the FIXED identifiers
`attr.price`, `attr.fx`, `attr.price_fx_interaction`, `attr.income`, `attr.fees`, `attr.taxes`, `attr.financing`, `attr.conversion`.

EVERY contribution is kept per component (a position, a cash balance, a receivable, an income or cost event), so any grouping sums EXACTLY to the line (Ruling 9.6).

IDENTITIES (Ruling 11.1 (1.2)), in every attribution call; a failure is an engine fault (INSUFFICIENT_DATA + CALCULATION_ERROR, never a number with a caveat):
    I-4  the eight lines sum to `g_D` on EVERY day, and the window lines sum to `G`;
    I-3  the sum of `g_D` equals `G = V_E - V_B - (sum I^C + sum I^K - sum O)`;
    I-2  the daily product `prod (1 + r_D)` equals the segment TWR exactly;
    I-9  cash: the replayed balance equals the sum of the events' cash effects (restated here from the event table, not read back from the replay).

STATES (Ruling 9.5). Every day's valuation and every flow is an input: any INSUFFICIENT input makes the attribution INSUFFICIENT_DATA with that reason (the TWR may stay AVAILABLE,
Ruling 5.2), a LIMITED input makes it LIMITED + STALE_DATA. The percentage components need `beta_D > 0` (or `beta_D = 0 = g_D`) every day: otherwise INSUFFICIENT_DATA with no reason and
the detail `NON_POSITIVE_BASE` (or `NEGATIVE_VALUE`); `TOTAL_LOSS` when a day's return or the TWR is -1. The money lines need no base, so they stay available in those cases.
Never annualized.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from domain.currency import CurrencyCode
from domain.ledger import EventType
from domain.replay import SequencedEvent
from marketdata.contracts import QuoteObservation
from marketdata.conventions import ConventionSet
from marketdata.manifest import DataKind
from marketdata.port import InstrumentResolverPort, MarketDataPort
from marketdata.states import price_input_state
from performance import lines as income_lines
from performance.conventions import PerformanceConventionSet
from performance.flows import DataUse, ValuedFlow, _rate
from performance.inputs import SuppressionInput
from performance.results import EMPTY_FRESHNESS, FreshnessVector, Part
from performance.returns import DayFlows, ratio, group_flows
from performance.states import insufficient_part, part_from_input
from performance.valuation import SUPPRESSION_DETAILS, CalendarIdOf, PortfolioValuation, price_freshness, retrieved_after
from product_contract.vocabulary import SufficiencyState

INSUFFICIENT = SufficiencyState.INSUFFICIENT_DATA
ONE_DAY = datetime.timedelta(days=1)

PRICE, FX, INTERACTION, INCOME, FEES, TAXES, FINANCING, CONVERSION = (
    "attr.price", "attr.fx", "attr.price_fx_interaction", "attr.income", "attr.fees", "attr.taxes", "attr.financing", "attr.conversion")
LINE_IDS: Tuple[str, ...] = (PRICE, FX, INTERACTION, INCOME, FEES, TAXES, FINANCING, CONVERSION)  # Ruling 9.2 (1.7): the registry order
LINE_NAMES = {PRICE: "local price effect", FX: "FX effect", INTERACTION: "price-FX interaction", INCOME: "income", FEES: "fees", TAXES: "known taxes",
              FINANCING: "financing costs", CONVERSION: "currency conversion result"}
_FROM_AMOUNT_LINE = {income_lines.INCOME: INCOME, income_lines.FEES: FEES, income_lines.TAXES: TAXES, income_lines.FINANCING: FINANCING, income_lines.CONVERSION: CONVERSION}

NON_POSITIVE_BASE = "NON_POSITIVE_BASE"
NEGATIVE_VALUE = "NEGATIVE_VALUE"
TOTAL_LOSS = "TOTAL_LOSS"

#: groupings of Ruling 9.6
GROUPS = ("listing", "component", "currency", "account", "market")


@dataclass(frozen=True, order=True)
class Component:
    """What a contribution belongs to: `kind` is `position`, `cash`, `receivable` or `event`; the rest is text (empty when not applicable) so the key sorts and hashes simply."""

    kind: str
    account: str = ""
    listing: str = ""
    currency: str = ""
    event: str = ""

    def part(self, group: str, market_of: Callable[[str], str]) -> Tuple[str, Tuple]:
        """`(name, sort key)` of the part this component falls into under `group` (performance/1.10 Ruling 9.6 table: exactly ONE key per contribution per grouping). What the ledger does not record
        falls into the part `none`, which sorts LAST, so every grouping sums to the whole line. The sort key is the fixed order (UUID integers for ids, text for currency codes and MICs;
        components run positions, cash, receivables, events). A receivable carries its dividend's listing; an income, fee, tax or financing event its own listing (else none) and currency;
        a conversion result has no listing and no currency (the caller leaves both empty)."""
        if group == "listing":
            return (f"listing:{self.listing}", (0, uuid.UUID(self.listing).int)) if self.listing else ("listing:none", (1,))
        if group == "component":
            if self.kind == "position":
                return f"position:{self.listing}", (0, 0, uuid.UUID(self.listing).int)
            if self.kind == "cash":
                return f"cash:{self.currency}", (0, 1, self.currency)
            if self.kind == "receivable":
                return f"receivable:{self.event}", (0, 2, uuid.UUID(self.event).int)
            return f"event:{self.event}", (0, 3, uuid.UUID(self.event).int)
        if group == "currency":
            return (f"currency:{self.currency}", (0, self.currency)) if self.currency else ("currency:none", (1,))
        if group == "account":
            return (f"account:{self.account}", (0, uuid.UUID(self.account).int)) if self.account else ("account:none", (1,))
        if group == "market":
            mic = market_of(self.listing) if self.listing else ""
            return (f"market:{mic}", (0, mic)) if mic and mic != "?" else ("market:none", (1,))
        raise ValueError(group)


@dataclass
class DayLines:
    """One calendar day: the contributions of each line per component, the base, the gain and the day's identity facts."""

    day: datetime.date
    base: Fraction                 # beta_D
    gain: Fraction                 # g_D
    contributions: Dict[str, Dict[Component, Fraction]] = field(default_factory=lambda: {line: {} for line in LINE_IDS})

    def add(self, line: str, component: Component, amount: Fraction) -> None:
        if amount != 0:
            bucket = self.contributions[line]
            bucket[component] = bucket.get(component, Fraction(0)) + amount

    def line(self, line_id: str) -> Fraction:
        return sum(self.contributions[line_id].values(), Fraction(0))

    def lines(self) -> Tuple[Fraction, ...]:
        return tuple(self.line(i) for i in LINE_IDS)


@dataclass(frozen=True)
class AttributionData:
    """Everything the daily decomposition produced; the entry turns it into metrics."""

    days: Tuple[DayLines, ...]
    parts: Tuple[Part, ...]
    freshness: FreshnessVector
    i3: str  # PASS / FAIL
    i4: str  # PASS / FAIL
    i4_failure: str = ""


class Lookups:
    """The rates and closes the decomposition needs beyond the valuations (trade-day closes, a position's close on the day it was closed, flow-day fixings), each recorded as a Part so
    a LIMITED or INSUFFICIENT lookup reaches the state of the attribution, and each read recorded in `use` for the manifest."""

    def __init__(self, reporting: CurrencyCode, port: MarketDataPort, market: ConventionSet, resolver: InstrumentResolverPort, use: DataUse,
                 retrieved_not_after: Optional[datetime.datetime], calendar_id_of: Optional[CalendarIdOf],
                 suppressions: Sequence[SuppressionInput] = (), event_taints: Optional[Dict[uuid.UUID, SuppressionInput]] = None):
        self.reporting, self.port, self.market, self.resolver, self.use = reporting, port, market, resolver, use
        self.retrieved_not_after, self.calendar_id_of = retrieved_not_after, calendar_id_of
        self.suppressions, self.event_taints = tuple(suppressions), dict(event_taints or {})
        self._guarded: set = set()
        self.parts: List[Part] = []
        self.fresh = EMPTY_FRESHNESS
        self._rates: Dict[Tuple[datetime.date, str], Optional[Fraction]] = {}
        self._closes: Dict[Tuple[datetime.date, uuid.UUID], Tuple[Optional[Fraction], Optional[CurrencyCode]]] = {}

    def rate(self, day: datetime.date, currency: CurrencyCode) -> Optional[Fraction]:
        key = (day, currency.code)
        if key not in self._rates:
            rate, part, fresh = _rate(day, currency, self.reporting, self.port, self.market, self.use, self.retrieved_not_after)
            if part is not None:
                self.parts.append(Part(f"attr:{part.ref}", part.state, part.reason, part.causes))
            self.fresh = self.fresh.union(fresh)
            self._rates[key] = rate
        return self._rates[key]

    def guard(self, account: uuid.UUID, listing: uuid.UUID, day: datetime.date, event_id: Optional[uuid.UUID] = None) -> None:
        """A close that is used for `(account, listing)` on `day` (a position closed out that day, or a trade's result) is in doubt where the position is suppressed on `day` (market-data Ruling 6.4
        item 2: the ledger's quantity and the raw close are in different units) or where the trade's relief holds a tainted portion (performance/1.10 Ruling 1.1a item 3): an INSUFFICIENT part with
        SOURCE_CONFLICT joins the attribution's state, exactly as the realized gain and the valuations of that day take it (Ruling 9.5)."""
        key = (account, listing, day, event_id)
        if key in self._guarded:
            return
        self._guarded.add(key)
        for s in sorted(self.suppressions, key=lambda s: (s.first_date, s.flag)):
            if s.account_id == account and s.listing_id == listing and s.covers(day):
                detail = next((d for d in SUPPRESSION_DETAILS if d in s.flag), "")
                self.parts.append(insufficient_part(f"attr:suppression:{account}/{listing}@{day.isoformat()}", s.reason, s.flag, detail))
                break
        taint = None if event_id is None else self.event_taints.get(event_id)
        if taint is not None:
            detail = next((d for d in SUPPRESSION_DETAILS if d in taint.flag), "")
            self.parts.append(insufficient_part(f"attr:taint:{event_id}", taint.reason, taint.flag, detail))

    def close(self, listing: uuid.UUID, day: datetime.date) -> Tuple[Optional[Fraction], Optional[CurrencyCode]]:
        key = (day, listing)
        if key not in self._closes:
            lookup = self.port.quote_on(listing, day, self.market)
            self.use.add(DataKind.QUOTE, lookup.consumed, day, lookup.synthetic)
            st = price_input_state(lookup)
            ref = f"attr:price:{listing}@{day.isoformat()}"
            part = part_from_input(ref, st)
            sel = lookup.selected
            currency = sel.observation.currency if sel is not None and isinstance(sel.observation, QuoteObservation) else self.resolver.trading_currency(listing)
            price: Optional[Fraction] = None
            if st.state is not INSUFFICIENT:
                if sel is None or not isinstance(sel.observation, QuoteObservation):
                    part = insufficient_part(ref, None, "the lookup selected no reading")
                elif retrieved_after((sel,), self.retrieved_not_after):
                    part = insufficient_part(ref, None, "RETRIEVED_AFTER_CURRENT_INSTANT: the close was retrieved after the Current-mode instant", "RETRIEVED_AFTER_CURRENT_INSTANT")
                else:
                    price = Fraction(sel.observation.price)
            self.parts.append(part)
            self.fresh = self.fresh.union(price_freshness(lookup, self.resolver.exchange_mic(listing), self.calendar_id_of))
            self._closes[key] = (price, currency)
        return self._closes[key]


def _sigma(live: Sequence[SequencedEvent], day: datetime.date, account_scope: Optional[uuid.UUID]) -> Dict[Tuple[uuid.UUID, uuid.UUID], Fraction]:
    out: Dict[Tuple[uuid.UUID, uuid.UUID], Fraction] = {}
    for item in live:
        e = item.event
        if e.event_type is EventType.SPLIT and e.event_date == day and e.listing_id is not None and e.split_ratio is not None:
            if account_scope is not None and e.account_id != account_scope:
                continue
            key = (e.account_id, e.listing_id)
            out[key] = out.get(key, Fraction(1)) * Fraction(e.split_ratio.new_units) / Fraction(e.split_ratio.old_units)
    return out


def daily_lines(
    live: Sequence[SequencedEvent], base: datetime.date, end: datetime.date, valuation: Callable[[datetime.date], PortfolioValuation],
    flows: Sequence[ValuedFlow], lookups: Lookups, conventions: PerformanceConventionSet, account_scope: Optional[uuid.UUID],
) -> AttributionData:
    """The eight lines for every calendar day of `(base, end]` (Ruling 9.1). Preconditions: every daily valuation and every flow value exists (the caller refuses first), so a
    missing rate or close here can only be one the valuations did not need (a position's close on the day it was closed) and is recorded as an INSUFFICIENT part."""
    by_day: Dict[datetime.date, DayFlows] = group_flows([f for f in flows if base < f.event.event_date <= end])
    scoped = [i for i in live if account_scope is None or i.event.account_id == account_scope]
    by_event = {i.event.event_id: i.event for i in scoped}
    # the amount lines (Rulings 8.1 to 8.5): each item translated at its own date's fixing, kept per event
    amount_items: Dict[datetime.date, List[Tuple[str, uuid.UUID, Fraction]]] = {}
    for ln in income_lines.LINES:
        for item in income_lines.line_items(live, ln, base, end, account_scope):
            total = Fraction(0)
            for currency, amount in item.pieces:
                rate = lookups.rate(item.day, currency)
                if rate is not None:
                    total += amount * rate
            amount_items.setdefault(item.day, []).append((_FROM_AMOUNT_LINE[ln], item.event_id, total))
    trades: Dict[datetime.date, List] = {}
    for item in scoped:
        e = item.event
        if e.event_type in (EventType.BUY, EventType.SELL) and e.listing_id is not None and e.quantity is not None and e.amount is not None and base < e.event_date <= end:
            trades.setdefault(e.event_date, []).append(e)

    days: List[DayLines] = []
    gain_sum = Fraction(0)
    i4, i4_failure = "PASS", ""
    day = base + ONE_DAY
    while day <= end:
        v0, v1 = valuation(day - ONE_DAY), valuation(day)
        f = by_day.get(day)
        i_c = Fraction(0) if f is None else f.inflow_cash
        beta = (v0.reporting_total.exact or Fraction(0)) + i_c
        g = (v1.reporting_total.exact or Fraction(0)) + (Fraction(0) if f is None else f.outflow - f.inflow_kind) - beta
        d = DayLines(day, beta, g)
        sigma = _sigma(live, day, account_scope)
        held1 = {(h.account_id, h.listing_id): h for h in v1.holdings}
        cash1 = {(c.account_id, c.currency): c for c in v1.cash}
        recv1 = {r.receivable.event_id: r for r in v1.receivables}
        for h0 in sorted(v0.holdings, key=lambda h: (h.account_id.int, h.listing_id.int)):
            key = (h0.account_id, h0.listing_id)
            if h0.quantity is None or h0.price is None or h0.fx_rate is None or h0.native_currency is None:
                lookups.parts.append(insufficient_part(f"attr:holding:{h0.account_id}/{h0.listing_id}@{(day - ONE_DAY).isoformat()}", None, "the start-of-day holding has no quantity, price or rate"))
                continue
            sg = sigma.get(key, Fraction(1))
            q0, p0, x0 = h0.quantity * sg, h0.price / sg, h0.fx_rate
            h1 = held1.get(key)
            if h1 is not None and h1.price is not None and h1.fx_rate is not None:
                p1, x1 = h1.price, h1.fx_rate
            else:
                lookups.guard(h0.account_id, h0.listing_id, day)
                p1, _ccy = lookups.close(h0.listing_id, day)
                x1 = lookups.rate(day, h0.native_currency)
                if p1 is None or x1 is None:
                    continue
            comp = Component("position", str(h0.account_id), str(h0.listing_id), h0.native_currency.code)
            d.add(PRICE, comp, q0 * (p1 - p0) * x0)
            d.add(FX, comp, q0 * p0 * (x1 - x0))
            d.add(INTERACTION, comp, q0 * (p1 - p0) * (x1 - x0))
        for c0 in sorted(v0.cash, key=lambda c: (c.account_id.int, c.currency.code)):
            if c0.amount is None or c0.fx_rate is None:
                lookups.parts.append(insufficient_part(f"attr:cash:{c0.account_id}/{c0.currency.code}@{(day - ONE_DAY).isoformat()}", None, "the start-of-day cash balance has no amount or rate"))
                continue
            c1 = cash1.get((c0.account_id, c0.currency))
            x1 = c1.fx_rate if c1 is not None and c1.fx_rate is not None else lookups.rate(day, c0.currency)
            if x1 is None:
                continue
            d.add(FX, Component("cash", str(c0.account_id), "", c0.currency.code), c0.amount * (x1 - c0.fx_rate))
        for r0 in sorted(v0.receivables, key=lambda r: (r.receivable.account_id.int, r.receivable.event_id.int)):
            rc = r0.receivable
            if r0.fx_rate is None:
                lookups.parts.append(insufficient_part(f"attr:receivable:{rc.event_id}@{(day - ONE_DAY).isoformat()}", None, "the start-of-day receivable has no rate"))
                continue
            r1 = recv1.get(rc.event_id)
            x1 = r1.fx_rate if r1 is not None and r1.fx_rate is not None else lookups.rate(day, rc.currency)
            if x1 is None:
                continue
            # performance/1.10 Ruling 9.6: a receivable's FX is its dividend's listing's (accrued income is part of the security's return until it is paid)
            d.add(FX, Component("receivable", str(rc.account_id), "" if rc.listing_id is None else str(rc.listing_id), rc.currency.code, str(rc.event_id)), rc.amount * (x1 - r0.fx_rate))
        for e in sorted(trades.get(day, ()), key=lambda e: str(e.event_id)):
            lookups.guard(e.account_id, e.listing_id, day, e.event_id)
            p1, ccy = lookups.close(e.listing_id, day)
            x1 = None if ccy is None else lookups.rate(day, ccy)
            x_e = lookups.rate(day, e.amount.currency)
            if p1 is None or x1 is None or x_e is None:
                continue
            at_close = Fraction(e.quantity) * p1 * x1
            paid = Fraction(e.amount.amount) * x_e
            d.add(PRICE, Component("position", str(e.account_id), str(e.listing_id), "" if ccy is None else ccy.code),
                  at_close - paid if e.event_type is EventType.BUY else paid - at_close)
        for line, event_id, amount in sorted(amount_items.get(day, ()), key=lambda t: (LINE_IDS.index(t[0]), str(t[1]))):
            ev = by_event.get(event_id)
            # performance/1.10 Ruling 9.6: an income, fee, tax or financing event is keyed by what it records (its listing if any, its currency, its own event id); a conversion result has no
            # single currency and no listing (`none`), and is an `event` by component
            keyed = line != CONVERSION and ev is not None
            d.add(line, Component("event", "" if ev is None else str(ev.account_id), "" if not keyed or ev.listing_id is None else str(ev.listing_id), ev.currency.code if keyed else "", str(event_id)), amount)
        if sum(d.lines(), Fraction(0)) != g:
            i4, i4_failure = "FAIL", f"I-4: the lines sum to {sum(d.lines(), Fraction(0))} on {day.isoformat()}, g_D is {g}"
        gain_sum += g
        days.append(d)
        day += ONE_DAY
    g_total = valuation(end).reporting_total.exact
    v_b = valuation(base).reporting_total.exact
    net = Fraction(0)
    for fl in by_day.values():
        net += fl.inflow_cash + fl.inflow_kind - fl.outflow
    i3 = "PASS" if g_total is not None and v_b is not None and gain_sum == g_total - v_b - net else "FAIL"
    return AttributionData(tuple(days), tuple(lookups.parts), lookups.fresh, i3, i4, i4_failure)


# --- identity I-9: cash --------------------------------------------------------------------------------------------------------------

_CASH_UP = (EventType.SELL, EventType.DIVIDEND, EventType.INTEREST, EventType.DEPOSIT, EventType.OPENING_CASH)
_CASH_DOWN = (EventType.BUY, EventType.FEE, EventType.TAX, EventType.WITHDRAWAL, EventType.INTEREST_CHARGED)


def cash_effects(live: Iterable[SequencedEvent], day: datetime.date, accounts: Optional[Iterable[uuid.UUID]] = None) -> Dict[Tuple[uuid.UUID, str], Fraction]:
    """The sum of the cash effects of the live events dated on or before `day`, per (account, currency): a deposit, a sale, a dividend, interest and an opening balance add; a purchase, a fee,
    a tax, a withdrawal and a financing cost subtract; a cash transfer adds (in) or subtracts (out); a conversion subtracts the sold amount and adds the bought one. Zero balances are dropped."""
    wanted = None if accounts is None else set(accounts)
    out: Dict[Tuple[uuid.UUID, str], Fraction] = {}

    def move(account: uuid.UUID, currency: str, delta: Fraction) -> None:
        out[(account, currency)] = out.get((account, currency), Fraction(0)) + delta

    for item in live:
        e = item.event
        if e.event_date > day or (wanted is not None and e.account_id not in wanted):
            continue
        t = e.event_type
        amount = None if e.amount is None else Fraction(e.amount.amount)
        if t in _CASH_UP and amount is not None:
            move(e.account_id, e.currency.code, amount)
        elif t in _CASH_DOWN and amount is not None:
            move(e.account_id, e.currency.code, -amount)
        elif t is EventType.TRANSFER_IN and amount is not None:
            move(e.account_id, e.currency.code, amount)
        elif t is EventType.TRANSFER_OUT and amount is not None:
            move(e.account_id, e.currency.code, -amount)
        elif t is EventType.CURRENCY_CONVERSION and amount is not None and e.bought_amount is not None:
            move(e.account_id, e.currency.code, -amount)
            move(e.account_id, e.bought_amount.currency.code, Fraction(e.bought_amount.amount))
    return {k: v for k, v in out.items() if v != 0}


def cash_identity(live: Sequence[SequencedEvent], val: PortfolioValuation, account_scope: Optional[uuid.UUID]) -> str:
    """I-9 at `val.as_of`: `PASS`, `FAIL` or `NOT_COMPUTABLE` (a blocked account or an unrepresentable balance means the replay states no balance to compare)."""
    if val.blocked or any(c.amount is None for c in val.cash):
        return "NOT_COMPUTABLE"
    live_scoped = [i for i in live if account_scope is None or i.event.account_id == account_scope]
    replayed = {(c.account_id, c.currency.code): c.amount for c in val.cash if c.amount is not None and c.amount != 0}
    return "PASS" if cash_effects(live_scoped, val.as_of) == replayed else "FAIL"


# --- window sums, daily returns and breakdowns ---------------------------------------------------------------------------------------

def window_lines(data: AttributionData) -> Tuple[Fraction, ...]:
    """`M_k(B, E] = sum_D m_{k,D}` (Ruling 9.3), in the registry order."""
    return tuple(sum((d.line(line) for d in data.days), Fraction(0)) for line in LINE_IDS)


@dataclass(frozen=True)
class DailyReturns:
    """The daily returns `r_D`, the exact components `c_{k,D} = m_{k,D} / beta_D`, the daily product, or why there is none."""

    factors: Tuple[Tuple[Fraction, Tuple[Fraction, ...]], ...] = ()
    product: Optional[Fraction] = None  # prod (1 + r_D)
    failure: str = ""                    # NON_POSITIVE_BASE or NEGATIVE_VALUE
    failure_day: Optional[datetime.date] = None
    zero_capital_days: int = 0


def daily_returns(data: AttributionData) -> DailyReturns:
    out: List[Tuple[Fraction, Tuple[Fraction, ...]]] = []
    product = Fraction(1)
    zero = 0
    for d in data.days:
        factor, detail = ratio(d.base + d.gain, d.base)
        if factor is None:
            return DailyReturns(failure=detail, failure_day=d.day)
        if detail:
            zero += 1
            out.append((Fraction(0), tuple(Fraction(0) for _ in LINE_IDS)))  # beta = 0 and g = 0: the day contributes nothing
        else:
            out.append((d.gain / d.base, tuple(m / d.base for m in d.lines())))
        product *= factor
    return DailyReturns(tuple(out), product, zero_capital_days=zero)


def breakdown_parts(data: AttributionData, line_id: str, group: str, market_of: Callable[[str], str]) -> Tuple[Tuple[str, Fraction], ...]:
    """Ruling 9.6 (1.9): one line split by `group`, as `(part name, exact)` in the fixed order of item 3 (which also breaks the apportionment ties of Ruling 2.4), parts that are exactly 0
    omitted (item 4; their components stay in `data`). The exact parts sum to the line exactly; the entry apportions them to the line's display value."""
    per_component: Dict[Component, Fraction] = {}
    for d in data.days:
        for comp, amount in d.contributions[line_id].items():
            per_component[comp] = per_component.get(comp, Fraction(0)) + amount
    sums: Dict[str, Fraction] = {}
    keys: Dict[str, Tuple] = {}
    for comp, amount in per_component.items():
        name, key = comp.part(group, market_of)
        sums[name] = sums.get(name, Fraction(0)) + amount
        keys[name] = key
    return tuple((n, sums[n]) for n in sorted(sums, key=lambda n: keys[n]) if sums[n] != 0)
