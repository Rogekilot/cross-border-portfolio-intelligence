"""The as-of date of a "current value" (`performance/1.0` Ruling 1.7, Current mode; closes OI-2 and MD-OI-1).

CP3 valuation is HISTORICAL AS-OF only (PM ruling 4). "Current value" is that valuation at the date the Current-mode rule chooses, still with no live
mode and no live feed:

    D_c(t) = the latest date D <= UTC-date(t) such that
        for every exchange m governing a listing with non-zero quantity in S(D, L):   D is not a session of m   or   scheduled_close_m(D) <= t
        and, if any amount in a currency other than R is held:                        D is not an ECB fixing day or 16:00 Europe/Berlin on D <= t

(performance/1.12 Ruling 1.7 item 2: "non-zero quantity in S(D, L)" also covers a listing NAMED by a live ledger event dated D, and "held" also covers a live event dated D that carries an amount, or
names a listing, whose currency is not R.)

`t` is an INPUT (the engine never reads a clock); `D_c(t)` and `t` are both recorded in the manifest. If a governing calendar does not cover a candidate
date the choice cannot be made: it FAILS CLOSED (no date, cause `CALENDAR_COVERAGE_GAP`, no reason code) and is never resolved by guessing a weekday.
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from domain.currency import CurrencyCode, Money
from domain.replay import AccountStatus, SequencedEvent, live_events, reconstruct
from marketdata.calendars import CalendarSet
from performance.results import Cause
from performance.valuation import accrued_receivables

#: The key of the calendar that governs the fixing days (market-data/1.8 Ruling 1.1); a test pins it to `marketdata.market11.FX_CALENDAR_KEY`.
ECB_CALENDAR_ID = "ECB"
CALENDAR_COVERAGE_GAP = "CALENDAR_COVERAGE_GAP"
MAX_LOOKBACK_DAYS = 400  # a bound on the search; a portfolio's open positions cannot be unpriceable for longer than the calendars cover


@dataclass(frozen=True)
class CurrentDate:
    date: Optional[datetime.date]
    causes: Tuple[Cause, ...] = ()
    examined: int = 0


def _gap(note: str) -> CurrentDate:
    return CurrentDate(None, (Cause("current_date", "INSUFFICIENT_DATA", None, f"{CALENDAR_COVERAGE_GAP}: {note}", CALENDAR_COVERAGE_GAP),))


def choose_current_date(
    instant: datetime.datetime, events: Iterable[SequencedEvent], ledger_version: int, calendars: CalendarSet,
    mic_of: Callable[[uuid.UUID], Optional[str]], reporting: CurrencyCode,
    currency_of: Callable[[uuid.UUID], Optional[CurrencyCode]],
) -> CurrentDate:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("the Current-mode instant must be timezone-aware")
    events = tuple(events)
    live = live_events(events, ledger_version)
    t = instant.astimezone(datetime.timezone.utc)
    day = t.date()
    for examined in range(1, MAX_LOOKBACK_DAYS + 1):
        state = reconstruct(events, day, ledger_version)
        mics: Set[Optional[str]] = set()
        foreign = False
        for account in state.accounts:
            if account.status is AccountStatus.NOT_RECONSTRUCTABLE:
                continue
            for p in account.positions:  # a flagged position is emitted too: it is treated as held (nothing is assumed away)
                mics.add(mic_of(p.listing_id))
                # Ruling 1.7: a position whose LISTING currency differs from R needs that day's fixing too (an unknown currency is treated as foreign)
                listing_currency = currency_of(p.listing_id)
                foreign = foreign or listing_currency is None or listing_currency != reporting
            for c in account.cash:
                foreign = foreign or c.balance.currency != reporting
            foreign = foreign or any(c != reporting for c in account.unrepresentable_cash)
        # CP3-7 (Ruling 1.7): a dividend receivable is a valued amount in a currency, so a foreign one needs that day's fixing too
        foreign = foreign or any(r.currency != reporting for r in accrued_receivables(live, day))
        # performance/1.12 Ruling 1.7 item 2: every LIVE ledger event dated `day` is also tested, because some need `day`'s close or fixing while nothing they touch remains held at the end of the day
        # (an in-kind transfer of a listing's last units; a foreign-currency withdrawal, income, cost or conversion). The exchange of a listing it names counts, and so does an amount or a listing
        # whose currency is not R (an unknown currency is foreign). `D_c(t)` stays a function of (t, L, M_t) only, never of the metric asked for.
        for item in live:
            e = item.event
            if e.event_date != day:
                continue
            # EVERY money field the event carries (CP4-9): `amount`, `bought_amount` (the bought side of a conversion), `cost_basis` (a lot's basis, needing the fixing of its acquisition date), and any
            # currency-bearing field added later; a currency that is not R is foreign
            for field in dataclasses.fields(e):
                value = getattr(e, field.name)
                if isinstance(value, Money) and value.currency != reporting:
                    foreign = True
            if e.listing_id is not None:
                mics.add(mic_of(e.listing_id))
                listing_currency = currency_of(e.listing_id)
                foreign = foreign or listing_currency is None or listing_currency != reporting
        eligible = True
        for mic in sorted(mics, key=lambda m: m or ""):
            calendar, problem = calendars.governing(mic)
            if calendar is None:
                return _gap(f"no single calendar governs {mic}: {problem}")
            if not calendar.covers(day, day):
                return _gap(f"calendar {calendar.calendar_id} does not cover {day.isoformat()}")
            if calendars.is_session(mic, day):
                close = calendar.close_time(day)
                if close is None:
                    return _gap(f"calendar {calendar.calendar_id} has no close time for {day.isoformat()}")
                instant_close = datetime.datetime.combine(day, close, tzinfo=ZoneInfo(calendar.timezone))
                if instant_close > t:
                    eligible = False
        if foreign:
            ecb, problem = calendars.governing(ECB_CALENDAR_ID)
            if ecb is None:
                return _gap(f"no single calendar governs the ECB fixings: {problem}")
            if not ecb.covers(day, day):
                return _gap(f"calendar {ecb.calendar_id} does not cover {day.isoformat()}")
            if calendars.is_session(ECB_CALENDAR_ID, day):
                if ecb.publication_time is None:
                    return _gap(f"calendar {ecb.calendar_id} has no publication time")
                published = datetime.datetime.combine(day, ecb.publication_time, tzinfo=ZoneInfo(ecb.timezone))
                if published > t:
                    eligible = False
        if eligible:
            return CurrentDate(day, (), examined)
        day -= datetime.timedelta(days=1)
    return CurrentDate(None, (Cause("current_date", "INSUFFICIENT_DATA", None,
                                    f"NO_ELIGIBLE_DATE: none of the {MAX_LOOKBACK_DAYS} days before the instant is eligible",
                                    "NO_ELIGIBLE_DATE"),), MAX_LOOKBACK_DAYS)
