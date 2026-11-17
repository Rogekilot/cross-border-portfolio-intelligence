"""The grids of the periodic return series and the window function (`risk/1.0` Rulings 2.2 and 2.3; tech plan 17.3, 17.15).

PURE: no market data, no clock, no float. It decides WHEN a series is sampled and WHICH periods are observations; it never values anything.

THE GRID `G_f` (Ruling 2.2): the calendar dates on which a period of frequency `f` ENDS.
- `DAILY`   every Monday to Friday (calendar weekdays, whatever any exchange does);
- `WEEKLY`  every Friday;
- `MONTHLY` the last calendar day of every month.
It depends on nothing a portfolio holds, so a portfolio and its benchmark are sampled on the same dates by construction. A grid date is a VALUATION date, not a session: no weekday is inferred to be a
session (the valuation reads each market's own calendar). A holiday is not special-cased and a zero-return period is never dropped.

THE WINDOW (Ruling 2.3). The request gives `(B, E]` through `performance.periods.resolve_window` (validity: `B >= I0`, `B < E`). The grid points used are `g_0 < ... < g_n`, all in `[B, E]`:
`g_0` the first grid date `>= B` (the base, not an observation), `g_n` the last grid date `<= E`, `n` the number of periods `(g_{k-1}, g_k]`. The stubs `(B, g_0]` and `(g_n, E]` are NOT observations: `stub_start_days = g_0 - B`,
`stub_end_days = E - g_n`. `n < 1` is INSUFFICIENT_DATA, no reason, detail `NO_FULL_PERIOD`.
"""

from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Dict, Optional, Tuple

GRID_RULE_ID = "risk/1.0#2.2"
ONE_DAY = datetime.timedelta(days=1)
NO_FULL_PERIOD = "NO_FULL_PERIOD"


@unique
class Frequency(Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


def on_grid(frequency: Frequency, day: datetime.date) -> bool:
    if frequency is Frequency.DAILY:
        return day.weekday() < 5
    if frequency is Frequency.WEEKLY:
        return day.weekday() == 4
    return day.day == calendar.monthrange(day.year, day.month)[1]


def next_on_or_after(frequency: Frequency, day: datetime.date) -> datetime.date:
    """The first grid date on or after `day`."""
    if frequency is Frequency.DAILY:
        return day + datetime.timedelta(days=max(0, 7 - day.weekday())) if day.weekday() > 4 else day
    if frequency is Frequency.WEEKLY:
        return day + datetime.timedelta(days=(4 - day.weekday()) % 7)
    return datetime.date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def next_after(frequency: Frequency, day: datetime.date) -> datetime.date:
    """The first grid date strictly after `day`."""
    return next_on_or_after(frequency, day + ONE_DAY)


def grid_dates(frequency: Frequency, low: datetime.date, high: datetime.date) -> Tuple[datetime.date, ...]:
    """Every grid date in `[low, high]`, increasing."""
    out = []
    d = next_on_or_after(frequency, low)
    while d <= high:
        out.append(d)
        d = next_after(frequency, d)
    return tuple(out)


@dataclass(frozen=True)
class WeekdayFridayMonthEndGrid:
    """The `BoundaryRule` of `risk/1.0` Ruling 2.2: every grid date in `[window.start, window.end]` (the REQUESTED window `(B, E]`; `g_0` may equal `B`)."""

    rule_id: str = GRID_RULE_ID

    def boundaries(self, frequency: Frequency, window: Any) -> Tuple[datetime.date, ...]:
        return grid_dates(frequency, window.start, window.end)


@dataclass(frozen=True)
class SeriesWindow:
    """What a series declares about its window (Ruling 2.3: 'every result declares'): the request, the effective window, the observation count, the stubs, and for MAX_AVAILABLE why it starts where it does."""

    rule: str                                  # TRAILING_MONTHS, YTD, SINCE_INCEPTION, CUSTOM or MAX_AVAILABLE
    months: Optional[int]
    frequency: str
    grid_rule: str
    requested_base: datetime.date              # B
    requested_end: datetime.date               # E
    base_date: datetime.date                   # g_0
    last_period_end: datetime.date             # g_n
    observation_count: int                     # n
    stub_start_days: int                       # g_0 - B
    stub_end_days: int                         # E - g_n
    max_available_start: Optional[str] = None  # INCEPTION or AFTER_INSUFFICIENT_PERIOD (MAX_AVAILABLE only)
    max_available_after: Optional[datetime.date] = None  # the end of the last insufficient period, when the start is AFTER_INSUFFICIENT_PERIOD
    max_available_cause: Optional[str] = None

    def to_obj(self) -> Dict[str, Any]:
        return {"rule": self.rule, "months": self.months, "frequency": self.frequency, "grid_rule": self.grid_rule, "requested_base": self.requested_base, "requested_end": self.requested_end,
                "base_date": self.base_date, "last_period_end": self.last_period_end, "observation_count": self.observation_count, "stub_start_days": self.stub_start_days,
                "stub_end_days": self.stub_end_days, "max_available_start": self.max_available_start, "max_available_after": self.max_available_after,
                "max_available_cause": self.max_available_cause}


def effective_window(rule: str, months: Optional[int], frequency: Frequency, requested_base: datetime.date, requested_end: datetime.date,
                     dates: Tuple[datetime.date, ...], grid_rule: str = GRID_RULE_ID) -> Optional[SeriesWindow]:
    """The declared window for the grid points `dates` (`g_0 ... g_n`), or None when there is no full period (`n < 1`)."""
    if len(dates) < 2:
        return None
    return SeriesWindow(rule, months, frequency.value, grid_rule, requested_base, requested_end, dates[0], dates[-1], len(dates) - 1, (dates[0] - requested_base).days,
                        (requested_end - dates[-1]).days)
