"""Calendars as reference data in the market-data version M (market-data/1.2 Ruling 5.3).

A `CalendarSet` holds the hand-made calendar files of M and answers ONE question: how many
sessions (or fixing days) fall in the interval `(after, upto]`, and from which file. Rules, all
from Ruling 5.3 and none chosen here:

- every listing's MIC must be governed by EXACTLY ONE calendar in M; zero or several make the count
  impossible (freshness UNKNOWN);
- one version per `calendar_id` in M (Ruling 0.1): a second file with the same id is refused;
- inside its coverage a calendar is complete (a date is a session iff listed); an interval that is
  not wholly inside the coverage cannot be counted: there is NO fallback to weekdays and nothing is
  inferred, and the result carries the cause `CALENDAR_COVERAGE_GAP` with the calendar and the
  uncovered dates;
- the count over an interval that goes past `actual_through` is still made (no state effect) and the
  note `COUNTED_PAST_ACTUAL_THROUGH` says so, so a scheduled-not-actual count is visible in lineage.

Pure: no clock, no file access, no network.
"""

from __future__ import annotations

import datetime
from bisect import bisect_right
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from marketdata.contracts import CalendarDays
from marketdata.manifest import FileRef, TwoVintagesError

COVERAGE_GAP = "CALENDAR_COVERAGE_GAP"
OFF_CALENDAR = "OFF_CALENDAR_DATE"  # a print/fixing dated the as-of date, which the covering calendar does not list
PAST_ACTUAL = "COUNTED_PAST_ACTUAL_THROUGH"


@dataclass(frozen=True)
class CalendarCount:
    """The answer for one interval. `missed` is None when it cannot be counted (then `note` carries
    the cause). `calendar` is the file consulted, if any; `notes` go to lineage."""

    missed: Optional[int]
    calendar: Optional[CalendarDays]
    notes: Tuple[str, ...] = ()

    @property
    def calendar_ref(self) -> Optional[FileRef]:
        return None if self.calendar is None else calendar_ref(self.calendar)


@dataclass(frozen=True)
class SessionWindow:
    """`session_window`'s answer: `[start, end]`, or None/None when it cannot be evaluated (then `notes` say why)."""

    start: Optional[datetime.date]
    end: Optional[datetime.date]
    calendar: Optional[CalendarDays]
    notes: Tuple[str, ...] = ()

    @property
    def evaluable(self) -> bool:
        return self.start is not None and self.end is not None

    def contains(self, day: datetime.date) -> bool:
        return self.start is not None and self.end is not None and self.start <= day <= self.end

    @property
    def calendar_ref(self) -> Optional[FileRef]:
        return None if self.calendar is None else calendar_ref(self.calendar)


def _past_actual_notes(calendar: CalendarDays, upto: datetime.date) -> Tuple[str, ...]:
    if upto > calendar.actual_through:
        return (f"{PAST_ACTUAL}: calendar {calendar.calendar_id} is checked as actual only through "
                f"{calendar.actual_through.isoformat()}",)
    return ()


def calendar_ref(calendar: CalendarDays) -> FileRef:
    lineage = calendar.lineage
    if lineage.file_sha256 is None or lineage.adapter_id is None or lineage.adapter_version is None:
        raise ValueError("a calendar must carry complete lineage")
    return FileRef(lineage.file_sha256, lineage.adapter_id, lineage.adapter_version)


class CalendarSet:
    def __init__(self, calendars: Iterable[CalendarDays] = ()):
        self._by_id: Dict[str, CalendarDays] = {}
        self._by_key: Dict[str, List[CalendarDays]] = {}
        for cal in calendars:
            if cal.calendar_id in self._by_id:
                raise TwoVintagesError(f"two vintages of calendar {cal.calendar_id!r} in one market-data version")
            self._by_id[cal.calendar_id] = cal
            for key in cal.applies_to:
                self._by_key.setdefault(key, []).append(cal)

    def __bool__(self) -> bool:
        return bool(self._by_id)

    def calendars(self) -> Tuple[CalendarDays, ...]:
        return tuple(self._by_id[k] for k in sorted(self._by_id))

    def governing(self, key: Optional[str]) -> Tuple[Optional[CalendarDays], Optional[str]]:
        """(calendar, None) when exactly one calendar governs `key` (a MIC, or `ECB`); otherwise
        (None, the problem)."""
        if key is None:
            return None, "the listing's exchange is not known"
        found = self._by_key.get(key, [])
        if not found:
            return None, f"no calendar in the market-data version governs {key}"
        if len(found) > 1:
            return None, f"{len(found)} calendars govern {key} ({', '.join(sorted(c.calendar_id for c in found))})"
        return found[0], None

    def count_after(self, key: Optional[str], after: datetime.date, upto: datetime.date) -> CalendarCount:
        """Sessions (or fixing days) `d` of the calendar governing `key` with `after < d <= upto`.

        C2-1 (review of 39733e9; Rulings 5.3, 1.6, 5.2): an EMPTY interval (the last print or fixing is dated `upto`)
        is NOT exempt from the calendar. The count is 0 only when ONE calendar governs `key`, its coverage contains
        `upto`, and it lists `upto` as a session (fixing day); otherwise it cannot be made (freshness UNKNOWN, cause
        CALENDAR_COVERAGE_GAP, or OFF_CALENDAR_DATE when the covering calendar does not list the date). Before this fix
        a print dated the as-of date was CURRENT with no calendar at all, so a UTC-shifted series (every row on a
        Sunday) or any series with no calendar passed as current."""
        calendar, problem = self.governing(key)
        if calendar is None:
            return CalendarCount(None, None, (f"{COVERAGE_GAP}: {problem}",))
        return self._count(calendar, after, upto)

    def by_id(self, calendar_id: Optional[str]) -> Optional[CalendarDays]:
        """The calendar of `calendar_id` (a file of M), or None. For a reference series that NAMES its calendar (a benchmark's index calculation calendar, `risk/1.1` Ruling 5.2) instead of being governed by an
        `applies_to` key."""
        return None if calendar_id is None else self._by_id.get(calendar_id)

    def count_after_calendar(self, calendar_id: Optional[str], after: datetime.date, upto: datetime.date) -> CalendarCount:
        """`count_after` for the calendar NAMED by `calendar_id`: the same rules (coverage, completeness, the empty-interval rule, the actual-through note), with no `applies_to` lookup. An unknown id cannot be counted."""
        calendar = self.by_id(calendar_id)
        if calendar is None:
            return CalendarCount(None, None, (f"{COVERAGE_GAP}: no calendar {calendar_id!r} in the market-data version",))
        return self._count(calendar, after, upto)

    def _count(self, calendar: CalendarDays, after: datetime.date, upto: datetime.date) -> CalendarCount:
        if upto <= after:
            if not calendar.covers(upto, upto):
                return CalendarCount(None, calendar, (
                    f"{COVERAGE_GAP}: calendar {calendar.calendar_id} covers "
                    f"{calendar.covers_from.isoformat()}..{calendar.covers_to.isoformat()}; "
                    f"uncovered {upto.isoformat()}..{upto.isoformat()} (the as-of date itself)",))
            index = bisect_right(calendar.dates, upto) - 1
            if not (index >= 0 and calendar.dates[index] == upto):  # the calendar lists `upto` as a session
                # inside its coverage a calendar is COMPLETE (Ruling 5.3 item 4): a date it does not list is no session
                # (fixing day), so a print or fixing dated that day has no session date in the calendar (Ruling 5.2
                # table, last row) and its freshness cannot be vouched for. A series of such dates (every row on a
                # Sunday: the signature of a UTC shift) is also what Test V0 catches for prices; FX has no V0.
                return CalendarCount(None, calendar, (
                    f"{OFF_CALENDAR}: {upto.isoformat()} is not a session (fixing day) of calendar "
                    f"{calendar.calendar_id}, which is complete inside its coverage "
                    f"{calendar.covers_from.isoformat()}..{calendar.covers_to.isoformat()}",))
            return CalendarCount(0, calendar, _past_actual_notes(calendar, upto))
        first = after + datetime.timedelta(days=1)
        if not calendar.covers(first, upto):
            gaps: List[str] = []
            if first < calendar.covers_from:
                last_gap = min(upto, calendar.covers_from - datetime.timedelta(days=1))
                gaps.append(f"{first.isoformat()}..{last_gap.isoformat()}")
            if upto > calendar.covers_to:
                first_gap = max(first, calendar.covers_to + datetime.timedelta(days=1))
                gaps.append(f"{first_gap.isoformat()}..{upto.isoformat()}")
            return CalendarCount(None, calendar, (
                f"{COVERAGE_GAP}: calendar {calendar.calendar_id} covers "
                f"{calendar.covers_from.isoformat()}..{calendar.covers_to.isoformat()}; "
                f"uncovered {', '.join(gaps)}",))
        missed = bisect_right(calendar.dates, upto) - bisect_right(calendar.dates, after)
        return CalendarCount(missed, calendar, _past_actual_notes(calendar, upto))

    def session_window(self, key: Optional[str], day: datetime.date, n: int) -> "SessionWindow":
        """The closed interval from the `n`-th session before `day` to the `n`-th session after it, counted in the
        calendar governing `key` (market-data/1.4 Ruling 6.4a item 1, n = 20). `day` itself need not be a session.
        Nothing is inferred: when ONE calendar does not govern `key`, or its coverage does not contain `day` and `n`
        sessions on each side, the window cannot be evaluated (`start`/`end` None, the cause CALENDAR_COVERAGE_GAP in
        `notes`)."""
        calendar, problem = self.governing(key)
        if calendar is None:
            return SessionWindow(None, None, None, (f"{COVERAGE_GAP}: {problem}",))
        if not calendar.covers(day, day):
            return SessionWindow(None, None, calendar, (
                f"{COVERAGE_GAP}: calendar {calendar.calendar_id} covers {calendar.covers_from.isoformat()}.."
                f"{calendar.covers_to.isoformat()}; the date {day.isoformat()} is uncovered",))
        before = bisect_right(calendar.dates, day - datetime.timedelta(days=1))  # sessions strictly before `day`
        upto = bisect_right(calendar.dates, day)  # sessions up to and including `day`
        after = len(calendar.dates) - upto  # sessions strictly after `day`
        if before < n or after < n:
            return SessionWindow(None, None, calendar, (
                f"{COVERAGE_GAP}: calendar {calendar.calendar_id} lists {before} session(s) before and {after} after "
                f"{day.isoformat()} inside its coverage {calendar.covers_from.isoformat()}.."
                f"{calendar.covers_to.isoformat()}; {n} are needed on each side",))
        return SessionWindow(calendar.dates[before - n], calendar.dates[upto + n - 1], calendar,
                             _past_actual_notes(calendar, calendar.dates[upto + n - 1]))

    def is_session(self, key: Optional[str], day: datetime.date) -> Optional[bool]:
        """True/False inside the coverage of the governing calendar; None if it cannot be said."""
        calendar, _ = self.governing(key)
        if calendar is None or not calendar.covers(day, day):
            return None
        index = bisect_right(calendar.dates, day) - 1
        return index >= 0 and calendar.dates[index] == day
