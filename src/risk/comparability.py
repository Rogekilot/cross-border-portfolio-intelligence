"""The comparability disclosure of a two-leg metric (`risk/1.4` Ruling 8; tech plan 17.20).

A two-leg metric (beta, R-squared, Jensen's alpha, active return, tracking error, information ratio) compares the portfolio's return with the benchmark's. The two legs are measured at different scheduled instants (a
Hong Kong holding against a New York index) or a different number of sessions behind a grid date (a missed print on one side). Either limits the comparison, and the product says so. This is a DISCLOSURE, never a
state (PD-0014 section 1.3): the value keeps whatever state Ruling 7.3 gives it, and a result that is INSUFFICIENT_DATA carries no disclosure (there is no value to qualify).

THE RULE (Ruling 8.2 (1.1)), over the grid dates the statistic uses (`g_0 ... g_n`; `g_0` and `g_n` only for the active return):
- the portfolio leg at `g` is every freshness entry of the portfolio total at `g` (the calendar of each listing held, and the ECB fixing of each currency other than `R`); the benchmark leg is its calculation calendar
  and, if the index is not in `R`, the ECB fixing;
- a leg's LAG at `g` is the largest missed count among its inputs (0 with none). `LAGGED`: the two lags differ at any date used (one session is enough);
- the INSTANT SETS are the union over the dates used of each leg's calendar ids, the ECB fixing appearing as the ECB calendar's id. `SEAM`: the portfolio's set is non-empty and differs from the benchmark's. A
  portfolio with no market input (cash in `R`) has an empty set and so no seam;
- `max_offset_minutes_at_last_grid_date`: at `g_n` each input's instant is the scheduled close of the session (or calculation day) actually used, or 14:10 Europe/Berlin on the fixing date actually used; the field
  is the largest `|p - b|` in whole minutes.

Pure: it reads the portfolio's freshness at each grid point (on the series), the benchmark's levels, and the calendar set the injected conventions carry; nothing else.
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional, Sequence, Set, Tuple
from zoneinfo import ZoneInfo

from marketdata.calendars import CalendarSet
from marketdata.contracts import CalendarDays
from performance.results import FreshEntry
from performance.series import ReturnSeries
from risk.benchmark import BenchmarkLeg
from risk.results import Comparability, LagPoint, Seam

ECB_KEY = "ECB"  # the key the ECB calendar governs (market-data Ruling 1.1)
EXCHANGE_KINDS = ("EXCHANGE_CALENDAR", "EXCHANGE")


def _calendars_of(conventions_freshness: object) -> Optional[CalendarSet]:
    return getattr(conventions_freshness, "calendars", None)


def _close_instant(calendar: Optional[CalendarDays], day: Optional[datetime.date]) -> Optional[datetime.datetime]:
    """The scheduled close of the session `day` of an exchange calendar, as an aware UTC datetime."""
    if calendar is None or day is None:
        return None
    t = calendar.close_time(day)
    if t is None:
        return None
    return datetime.datetime.combine(day, t, tzinfo=ZoneInfo(calendar.timezone)).astimezone(datetime.timezone.utc)


def _fixing_instant(ecb: Optional[CalendarDays], day: Optional[datetime.date]) -> Optional[datetime.datetime]:
    """14:10 Europe/Berlin (the calendar's fixing time) on the fixing date used."""
    if ecb is None or day is None or ecb.fixing_time is None:
        return None
    return datetime.datetime.combine(day, ecb.fixing_time, tzinfo=ZoneInfo(ecb.timezone)).astimezone(datetime.timezone.utc)


def _portfolio_inputs(entries: Sequence[FreshEntry]) -> Tuple[List[FreshEntry], List[FreshEntry]]:
    return [e for e in entries if e.kind in EXCHANGE_KINDS], [e for e in entries if e.kind == "CURRENCY"]


def comparability(series: ReturnSeries, leg: BenchmarkLeg, dates_used: Sequence[datetime.date], calendars: Optional[CalendarSet]) -> Comparability:
    """The disclosure of Ruling 8.3 over `dates_used` (a subset of the series' grid points)."""
    boundary: Dict[datetime.date, object] = {d: v for d, v in series.boundary_values}
    ecb = None if calendars is None else calendars.governing(ECB_KEY)[0]
    ecb_id = None if ecb is None else ecb.calendar_id
    p_set: Set[str] = set()
    b_set: Set[str] = set()
    points: List[LagPoint] = []
    entry = leg.entry
    for g in dates_used:
        valued = boundary[g]
        entries = valued.freshness.entries  # type: ignore[attr-defined]
        exchange, currency = _portfolio_inputs(entries)
        for e in exchange:
            p_set.add(e.key)
        if currency:
            p_set.add(ecb_id if ecb_id is not None else ECB_KEY)
        p_lag = max([e.missed for e in exchange + currency if e.missed is not None], default=0)
        level = leg.level_at(g)
        b_set.add(entry.calendar_id)
        if level.fx_rate is not None:
            b_set.add(ecb_id if ecb_id is not None else ECB_KEY)
        b_lag = max([x for x in (level.missed, level.fx_missed) if x is not None], default=0)
        if p_lag != b_lag:
            points.append(LagPoint(g, p_lag, b_lag))
    seam: Optional[Seam] = None
    if p_set and p_set != b_set:
        seam = Seam(tuple(sorted(p_set)), tuple(sorted(b_set)), _max_offset(series, leg, dates_used[-1], calendars, ecb))
    klass = "LIMITED" if (seam is not None or points) else "FULL"
    return Comparability(klass, seam, len(points), len(dates_used), tuple(points))


def _max_offset(series: ReturnSeries, leg: BenchmarkLeg, last: datetime.date, calendars: Optional[CalendarSet], ecb: Optional[CalendarDays]) -> Optional[int]:
    """At `g_n`: the largest `|p - b|` between a portfolio instant and a benchmark instant, in whole minutes (None if an instant cannot be placed)."""
    if calendars is None:
        return None
    valued = dict(series.boundary_values)[last]
    exchange, currency = _portfolio_inputs(valued.freshness.entries)  # type: ignore[attr-defined]
    p: List[Optional[datetime.datetime]] = [_close_instant(calendars.by_id(e.key), e.date_used) for e in exchange]
    p += [_fixing_instant(ecb, e.date_used) for e in currency]
    level = leg.level_at(last)
    b: List[Optional[datetime.datetime]] = [_close_instant(calendars.by_id(leg.entry.calendar_id), level.date_used)]
    if level.fx_rate is not None:
        b.append(_fixing_instant(ecb, level.fx_date_used))
    if any(x is None for x in p + b) or not p or not b:
        return None
    seconds = max(abs((x - y).total_seconds()) for x in p for y in b)  # type: ignore[operator]
    return int(seconds // 60)
