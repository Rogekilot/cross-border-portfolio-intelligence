"""The risk-free leg: the per-period risk-free return and its states (`risk/1.0` Rulings 4.1 to 4.4; tech plan 17.4.2, 17.15).

For grid points `g_0 < ... < g_n` the period `(g_{k-1}, g_k]` earns, exactly:

    f_k   = the latest publication date <= g_{k-1}            (the quote KNOWN when the period starts; never the end-of-period quote)
    rho_k = the simple rate per calendar day of that quote
    rf_k  = rho_k * (g_k - g_{k-1})                           (simple interest over the period's calendar days; exact rational)

`rho` by quote type (`y` = the quoted rate as a decimal fraction, from the series' declared unit):
- `SIMPLE_YIELD` on an ACT/`B` basis: `y / B`, `B` the series' declared `day_count_basis` (360 or 365);
- `BANK_DISCOUNT` (ACT/360) with the quote's term `t` days: `y / (360 - y t)`, the bill's holding-period return `1 / (1 - y t / 360) - 1` divided by its `t` days.

The state of each `rf_k` follows Ruling 4.4 with `m_k` = the publication dates in `(f_k, g_{k-1}]` of the series' own `RATE_PUBLICATIONS` calendar (the thresholds are the price and FX thresholds, one staleness scale):

| condition | state | reason | detail |
|---|---|---|---|
| `m = 0` | AVAILABLE | none | |
| `m = 1` | AVAILABLE | STALE_DATA | RISK_FREE_STALE |
| `m = 2` to `4` | LIMITED | STALE_DATA | RISK_FREE_STALE |
| `m >= 5` | INSUFFICIENT_DATA | STALE_DATA | RISK_FREE_STALE |
| no quote on or before `g_{k-1}` | INSUFFICIENT_DATA | none | RISK_FREE_UNAVAILABLE |
| no admitted series for `R` (or more than one) | INSUFFICIENT_DATA | none | NO_RISK_FREE_SOURCE |
| the publication calendar cannot count the interval | INSUFFICIENT_DATA | none | CALENDAR_COVERAGE_GAP |

A currency with no admitted series is `NO_RISK_FREE_SOURCE` and nothing else: never another currency's rate, never a constant, never 0 (Ruling 4.1). No interpolation, no look-ahead. This module computes no statistic and decides no threshold:
the unit, quote type, day count and term are the SERIES' declared data (`RiskFreeSeries`), and the staleness counts are the market-data convention's.
"""

from __future__ import annotations

import bisect
import datetime
from dataclasses import dataclass
from fractions import Fraction
from typing import List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from domain.catalogs import RiskFreeCatalog
from domain.currency import CurrencyCode
from marketdata.conventions import ConventionSet
from marketdata.contracts import RateUnit, RiskFreePoint, RiskFreeQuoteType, RiskFreeSeries
from marketdata.manifest import FileRef
from marketdata.port import LookupOutcome, MarketDataPort, RiskFreeLookup
from marketdata.states import LIMITED_FROM, NO_VALUE_FROM
from performance.results import Cause, FreshEntry, FreshnessVector
from performance.states import STALE_DATA, Valued
from product_contract.vocabulary import SufficiencyState

RISK_FREE_STALE = "RISK_FREE_STALE"
RISK_FREE_UNAVAILABLE = "RISK_FREE_UNAVAILABLE"
NO_RISK_FREE_SOURCE = "NO_RISK_FREE_SOURCE"
CALENDAR_COVERAGE_GAP = "CALENDAR_COVERAGE_GAP"
RISK_FREE_KIND = "RISK_FREE"  # the `FreshEntry.kind` of a risk-free series in a freshness vector
DAYS_ACT_360 = 360


def rate_fraction(point: RiskFreePoint, unit: RateUnit) -> Fraction:
    """The quoted rate as an exact decimal fraction `y` (3.65 percent is 73/2000)."""
    value = Fraction(point.rate)
    return value / 100 if unit is RateUnit.PERCENT else value


def daily_rate(series: RiskFreeSeries, point: RiskFreePoint) -> Fraction:
    """`rho`: the simple rate per calendar day of the quote (Ruling 4.3). Exact."""
    y = rate_fraction(point, series.unit)
    if series.quote_type is RiskFreeQuoteType.SIMPLE_YIELD:
        return y / series.day_count_basis
    assert point.term_days is not None  # the contract refuses a BANK_DISCOUNT point without its term
    denominator = DAYS_ACT_360 - y * point.term_days
    if denominator <= 0:  # the contract refuses y * t >= 360; a defensive stop, never a number
        raise ValueError("a discount rate with y * t >= 360 has no conversion")
    return y / denominator


def period_return(series: RiskFreeSeries, point: RiskFreePoint, start: datetime.date, end: datetime.date) -> Fraction:
    """`rf_k = rho_k * (g_k - g_{k-1})` in calendar days."""
    if end <= start:
        raise ValueError("a period ends after it starts")
    return daily_rate(series, point) * (end - start).days


@dataclass(frozen=True)
class PeriodRate:
    """The risk-free return of one period, with its state and the facts that make it reproducible (Ruling 9.4: for each period `f_k` and `m_k`)."""

    start: datetime.date
    end: datetime.date
    quote_date: Optional[datetime.date]        # f_k
    missed_publications: Optional[int]         # m_k
    valued: Valued                             # state, reason, exact rf_k (None when INSUFFICIENT), causes
    details: Tuple[str, ...]
    series_id: Optional[str]
    consumed: Tuple[FileRef, ...]
    notes: Tuple[str, ...]
    synthetic: bool                            # the RELEASE holds a synthetic file: every result computed from it is synthetic (Ruling 4.8). NOT a property of this series.
    series_synthetic: Optional[bool] = None    # the SERIES' OWN lineage (CP4M-2): the catalog gate reads this, never the release's flag; None (no series, or not said) is treated as real

    @property
    def exact(self) -> Optional[Fraction]:
        return self.valued.exact


def _cause(start: datetime.date, end: datetime.date, state: SufficiencyState, reason: Optional[str], note: str, detail: str) -> Cause:
    return Cause(f"risk_free:{start.isoformat()}..{end.isoformat()}", state.value, reason, note, detail)


def _refused(lookup: RiskFreeLookup, start: datetime.date, end: datetime.date, reason: Optional[str], detail: str, note: str) -> PeriodRate:
    cause = _cause(start, end, SufficiencyState.INSUFFICIENT_DATA, reason, note, detail)
    notes = lookup.lineage_notes
    return PeriodRate(start, end, lookup.date_used, lookup.missed_count, Valued(SufficiencyState.INSUFFICIENT_DATA, reason, None, (cause,)), (detail,),
                      None if lookup.series is None else lookup.series.series_id, lookup.consumed, notes, lookup.synthetic,
                      None if lookup.series is None else bool(lookup.series.lineage.is_synthetic))


def period_rate(lookup: RiskFreeLookup, start: datetime.date, end: datetime.date) -> PeriodRate:
    """Ruling 4.3 and 4.4 for one period, from the lookup made AT THE PERIOD'S START `g_{k-1}`."""
    currency = lookup.currency.code
    if lookup.outcome in (LookupOutcome.NOT_IN_RELEASE, LookupOutcome.NO_SELECTION):
        why = "no admitted risk-free series" if lookup.outcome is LookupOutcome.NOT_IN_RELEASE else "more than one risk-free series serves the currency (the rule is one)"
        return _refused(lookup, start, end, None, NO_RISK_FREE_SOURCE, f"{NO_RISK_FREE_SOURCE}: {why} for {currency}; no other currency's rate and no constant is used")
    if lookup.outcome is LookupOutcome.NO_HISTORY:
        return _refused(lookup, start, end, None, RISK_FREE_UNAVAILABLE, f"{RISK_FREE_UNAVAILABLE}: no quote on or before {start.isoformat()}")
    if lookup.outcome is LookupOutcome.FRESHNESS_UNKNOWN:
        return _refused(lookup, start, end, None, CALENDAR_COVERAGE_GAP, f"{CALENDAR_COVERAGE_GAP}: the publication calendar cannot count the interval to {start.isoformat()}")
    if lookup.outcome is LookupOutcome.STALE_BEYOND_LIMIT:
        return _refused(lookup, start, end, STALE_DATA, RISK_FREE_STALE, f"{RISK_FREE_STALE}: {lookup.missed_count} publication(s) missed")
    if lookup.outcome is not LookupOutcome.FOUND or lookup.series is None or lookup.point is None or lookup.missed_count is None or lookup.date_used is None:
        return _refused(lookup, start, end, None, RISK_FREE_UNAVAILABLE, f"{RISK_FREE_UNAVAILABLE}: no usable quote ({lookup.outcome.value})")
    m = lookup.missed_count
    exact = period_return(lookup.series, lookup.point, start, end)
    fresh = FreshnessVector((FreshEntry(RISK_FREE_KIND, lookup.series.series_id, lookup.date_used, m, "CURRENT" if m == 0 else "STALE"),), ())
    if m == 0:
        valued = Valued(SufficiencyState.AVAILABLE, None, exact, (), fresh)
        details: Tuple[str, ...] = ()
    else:
        state = SufficiencyState.AVAILABLE if m < LIMITED_FROM else SufficiencyState.LIMITED
        cause = _cause(start, end, state, STALE_DATA, f"{RISK_FREE_STALE}: {m} publication(s) missed since the quote of {lookup.date_used.isoformat()}", RISK_FREE_STALE)
        valued = Valued(state, STALE_DATA, exact, (cause,), fresh)
        details = (RISK_FREE_STALE,)
    assert m < NO_VALUE_FROM  # `m >= 5` is STALE_BEYOND_LIMIT, handled above
    return PeriodRate(start, end, lookup.date_used, m, valued, details, lookup.series.series_id, lookup.consumed, lookup.lineage_notes, lookup.synthetic, bool(lookup.series.lineage.is_synthetic))


def refuse_unadmitted(rates: Sequence[PeriodRate], catalog: RiskFreeCatalog, currency: CurrencyCode) -> Tuple[PeriodRate, ...]:
    """Ruling 4.6 and `RISK_FREE.json`: only a catalogued series is a source. A REAL series that the catalog does not admit for `currency` is no source at all: `NO_RISK_FREE_SOURCE`, never used, never another
    currency's rate. A synthetic series is never catalogued (market-data Ruling 4.8: fixtures and tests carry their own series), so the gate does not apply to it. WHICH series is synthetic is the SERIES' OWN
    lineage (CP4M-2), never the release's flag: a real, unadmitted series in a release that also holds one synthetic file elsewhere is still no source."""
    out: List[PeriodRate] = []
    for r in rates:
        if r.series_id is None or r.series_synthetic is True or catalog.admits(currency.code, r.series_id):
            out.append(r)
            continue
        note = f"{NO_RISK_FREE_SOURCE}: the series {r.series_id!r} is not the admitted {currency.code} series of catalog {catalog.catalog_id!r}"
        cause = _cause(r.start, r.end, SufficiencyState.INSUFFICIENT_DATA, None, note, NO_RISK_FREE_SOURCE)
        out.append(PeriodRate(r.start, r.end, r.quote_date, r.missed_publications, Valued(SufficiencyState.INSUFFICIENT_DATA, None, None, (cause,)), (NO_RISK_FREE_SOURCE,), r.series_id,
                              r.consumed, r.notes, r.synthetic, r.series_synthetic))
    return tuple(out)


def source_probe(port: MarketDataPort, currency: CurrencyCode, as_of: datetime.date, conventions: ConventionSet, catalog: RiskFreeCatalog) -> Optional[PeriodRate]:
    """The window-independent half of Ruling 4.4 (and Ruling 7.3 (1.5)): is there an admitted risk-free series for `currency` at all? Asked when the window is refused and there are no grid dates to take
    rates at. Returns the `NO_RISK_FREE_SOURCE` refusal (a zero-length probe at `as_of`, never a period of the window), or None: a freshness, history or coverage problem is window-dependent and is not asked."""
    lookup = port.risk_free_on(currency, as_of, conventions)
    if lookup.outcome in (LookupOutcome.NOT_IN_RELEASE, LookupOutcome.NO_SELECTION):
        return period_rate(lookup, as_of, as_of)
    series = lookup.series
    if series is not None and not bool(series.lineage.is_synthetic) and not catalog.admits(currency.code, series.series_id):
        return _refused(lookup, as_of, as_of, None, NO_RISK_FREE_SOURCE, f"{NO_RISK_FREE_SOURCE}: the series {series.series_id!r} is not the admitted {currency.code} series of catalog {catalog.catalog_id!r}")
    return None


def _latest_due_publication(lookup: RiskFreeLookup, start: datetime.date, instant: datetime.datetime, conventions: ConventionSet) -> datetime.date:
    """Current mode (`risk` Ruling 5.8 items 4 and 5): the latest PUBLICATION date of the series' calendar on or before `start` whose publication instant is at or before `t`; `start` itself when the calendar is
    unknown or none is due. A publication not yet due at `t` is neither used nor counted as missed."""
    calendars = getattr(conventions.freshness, "calendars", None)
    series = lookup.series
    calendar = None if calendars is None or series is None else calendars.by_id(series.calendar_id)
    if calendar is None or calendar.publication_time is None:
        return start
    zone = ZoneInfo(calendar.timezone)
    i = bisect.bisect_right(calendar.dates, start)
    while i > 0:
        day = calendar.dates[i - 1]
        if datetime.datetime.combine(day, calendar.publication_time, tzinfo=zone) <= instant:
            return day
        i -= 1
    return start


def risk_free_rates(
    port: MarketDataPort, currency: CurrencyCode, grid: Sequence[datetime.date], conventions: ConventionSet, instant: Optional[datetime.datetime] = None,
) -> Tuple[PeriodRate, ...]:
    """The per-period risk-free returns for the grid points `grid` (`g_0 ... g_n`), each from the quote known at the period's start. One lookup per period start. In Current mode (`instant` = `t`) the lookup is made
    at the latest publication DUE at `t` (Ruling 5.8 items 4 and 5): a quote published but not yet in `M_t` is MISSED (the port counts it), one not yet published is not."""
    out: List[PeriodRate] = []
    for start, end in zip(grid, grid[1:]):
        lookup = port.risk_free_on(currency, start, conventions)
        if instant is not None:
            due = _latest_due_publication(lookup, start, instant, conventions)
            if due != start:
                lookup = port.risk_free_on(currency, due, conventions)
        out.append(period_rate(lookup, start, end))
    return tuple(out)
