"""Windows, the end-of-month rule and the year fraction (`performance/1.0` Rulings 5.4 and 7.1; tech plan 16.4).

Windows are HALF-OPEN `(B, E]`: the base valuation is at the END of `B`, the last at the end of `E`, the window contains the days `B+1 .. E`
(HG1 M1 RULING 1(a)). Pure date arithmetic: no clock, no float.

- `add_months` / `sub_months` use the end-of-month rule: if the date is the last day of its month the result is the last day of the target month;
  otherwise the same day of the month, clamped to the target month's last day.
- `Y(B, E) = m/12 + r/365` with `m` the largest integer such that `add_months(B, m) <= E` and `r = E - add_months(B, m)` in days (exact rational).
- Validity (Ruling 5.4): `B >= I0` and `B < E`. `B < I0` because of a snapshot is INSUFFICIENT_DATA + NOT_RECONSTRUCTABLE; `B < I0` for a portfolio with no
  snapshot is INSUFFICIENT_DATA with no reason and the detail `WINDOW_BEFORE_INCEPTION`. A "1Y" figure for a young portfolio would assert a year of
  history that did not exist (P5): the since-inception window is the honest figure.
"""

from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from enum import Enum, unique
from fractions import Fraction
from typing import Optional

from performance.ledger_view import Inception
from performance.results import Cause, WindowUsed


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def add_months(x: datetime.date, months: int) -> datetime.date:
    index = x.year * 12 + (x.month - 1) + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    last = _last_day(year, month)
    if x.day == _last_day(x.year, x.month):
        return datetime.date(year, month, last)
    return datetime.date(year, month, min(x.day, last))


def sub_months(x: datetime.date, months: int) -> datetime.date:
    return add_months(x, -months)


def year_fraction(base: datetime.date, end: datetime.date) -> Fraction:
    """Ruling 7.1: `m/12 + r/365`, exact."""
    if end < base:
        raise ValueError("the window end precedes its base")
    m = (end.year - base.year) * 12 + (end.month - base.month)
    while add_months(base, m) > end:
        m -= 1
    r = (end - add_months(base, m)).days
    return Fraction(m, 12) + Fraction(r, 365)


@unique
class WindowRule(Enum):
    TRAILING_MONTHS = "TRAILING_MONTHS"
    YTD = "YTD"
    SINCE_INCEPTION = "SINCE_INCEPTION"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class WindowSpec:
    rule: WindowRule
    months: Optional[int] = None            # TRAILING_MONTHS: 1, 3, 6, 12 (1Y), 36 (3Y), 60 (5Y)
    custom_base: Optional[datetime.date] = None  # CUSTOM: any B < E

    def __post_init__(self) -> None:
        if self.rule is WindowRule.TRAILING_MONTHS and (self.months is None or self.months <= 0):
            raise ValueError("TRAILING_MONTHS needs a positive number of months")
        if self.rule is WindowRule.CUSTOM and self.custom_base is None:
            raise ValueError("CUSTOM needs a base date")


@dataclass(frozen=True)
class ResolvedWindow:
    """A valid window, or the cause that makes every window metric INSUFFICIENT_DATA. `reason` is the reason-code text (or None)."""

    window: Optional[WindowUsed]
    cause: Optional[Cause] = None
    reason: Optional[str] = None
    declared: Optional[WindowUsed] = None  # the window as declared (base, end, days), even where it is refused: it travels with every value

    @property
    def valid(self) -> bool:
        return self.window is not None


def resolve_window(spec: WindowSpec, end: datetime.date, inception: Inception, not_reconstructable_reason: str) -> ResolvedWindow:
    """Declare `(B, E]` (Ruling 5.4) and judge its validity. `not_reconstructable_reason` is the reason-code text of NOT_RECONSTRUCTABLE (the only
    module that names reason codes passes it in)."""
    insufficient = "INSUFFICIENT_DATA"
    if inception.date is None:
        return ResolvedWindow(None, Cause("window", insufficient, None, "NO_LIVE_LEDGER_EVENTS: the ledger has no live event", "NO_LIVE_LEDGER_EVENTS"))
    if spec.rule is WindowRule.TRAILING_MONTHS:
        assert spec.months is not None
        base = sub_months(end, spec.months)
    elif spec.rule is WindowRule.YTD:
        base = datetime.date(end.year - 1, 12, 31)
    elif spec.rule is WindowRule.SINCE_INCEPTION:
        base = inception.date
    else:
        assert spec.custom_base is not None
        base = spec.custom_base
    window = WindowUsed(base, end, None, spec.rule.value, spec.months, inception.since_snapshot and spec.rule is WindowRule.SINCE_INCEPTION)
    if not base < end:
        return ResolvedWindow(None, Cause("window", insufficient, None,
                                          f"WINDOW_NOT_POSITIVE: the base {base.isoformat()} is not before the end {end.isoformat()}",
                                          "WINDOW_NOT_POSITIVE"), declared=window)
    if base < inception.date:
        if inception.since_snapshot:
            return ResolvedWindow(None, Cause("window", insufficient, not_reconstructable_reason,
                                              f"the base {base.isoformat()} is before the snapshot date {inception.date.isoformat()}",
                                              "WINDOW_BEFORE_SNAPSHOT"), not_reconstructable_reason, window)
        return ResolvedWindow(None, Cause("window", insufficient, None,
                                          f"WINDOW_BEFORE_INCEPTION: the base {base.isoformat()} is before inception {inception.date.isoformat()}",
                                          "WINDOW_BEFORE_INCEPTION"), declared=window)
    return ResolvedWindow(window, declared=window)
