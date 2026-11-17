"""Shared helpers for the CP2c-1 tests (not collected as a test module). SYNTHETIC data only:
hand-written numbers in the structure of the real files; no vendor data is read or copied.

Every expected value in the tests that use these helpers is derived by hand from the inputs shown, or
is a figure of the Quant's worked examples in methodology/CP2_MARKET_DATA_CONVENTIONS.md (cited)."""

import datetime
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_testkit as kit  # noqa: E402

from domain.currency import CurrencyCode  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata.adapters.base import AdapterRegistry  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.manifest import MarketDataRelease  # noqa: E402
from marketdata.store import InMemoryMarketData  # noqa: E402

D = datetime.date
SHA = "e" * 64
SHA2 = "f" * 64
NOW = datetime.datetime(2026, 10, 1, 3, 0, tzinfo=datetime.timezone.utc)
EUR, USD, HKD, CNY, CNH = (CurrencyCode(x) for x in ("EUR", "USD", "HKD", "CNY", "CNH"))
LID = uuid.UUID(int=77)
OTHER_LID = uuid.UUID(int=78)
RELEASE = MarketDataRelease(name="t", files=(), source_precedence=())


def lineage(source_id="alphavantage.us", sha=SHA, adjustment=c.AdjustmentStatus.RAW, usage=c.UsageScope.SYNTHETIC_TEST,
            provenance=None, group_market="US"):
    return c.Lineage(source_id, adjustment, source_id=source_id, file_sha256=sha, adapter_id="ad",
                     adapter_version="1", source_record_ref="r", retrieved_at=NOW, usage_scope=usage,
                     market=group_market, provenance=provenance)


def quote_reading(day, price="100.00", volume="1000", source="alphavantage.us", group="alphavantage", sha=SHA,
                  listing=LID, recovered=True, bound="0", usage=c.UsageScope.SYNTHETIC_TEST,
                  adjustment=c.AdjustmentStatus.RAW, ccy=USD):
    q = c.QuoteObservation(listing, day, Decimal(price), ccy, c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY),
                           lineage(source, sha, adjustment, usage), volume=None if volume is None else Decimal(volume),
                           recovered=recovered, precision_bound=Decimal(bound))
    return c.SourceReading(source, group, sha, q)


def fx_reading(day, ccy, rate, source="ecb.eurofxref", group="ecb", sha=SHA, provenance=None, base=EUR,
               usage=c.UsageScope.SYNTHETIC_TEST):
    obs = c.FXObservation(base, ccy if isinstance(ccy, CurrencyCode) else CurrencyCode(ccy), day, Decimal(rate),
                          c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY),
                          lineage(source, sha, usage=usage, provenance=provenance), "ecb")
    return c.SourceReading(source, group, sha, obs)


def calendar(calendar_id, kind, applies_to, dates, covers=None, actual_through=None, tz=None, sha=SHA2,
             default_close=datetime.time(16, 0), early=(), version="v1"):
    dates = tuple(dates)
    covers = covers or (dates[0], dates[-1])
    zone = tz or ("Europe/Berlin" if kind is c.CalendarKind.ECB_FIXINGS else "America/New_York")
    line = c.Lineage("calendar.manual", c.AdjustmentStatus.RAW, source_id="calendar.manual", file_sha256=sha,
                     adapter_id="calendar.manual.calendar", adapter_version="0.1.0", source_record_ref=calendar_id,
                     retrieved_at=NOW, usage_scope=c.UsageScope.SYNTHETIC_TEST)
    ecb = kind is c.CalendarKind.ECB_FIXINGS
    return c.CalendarDays(
        calendar_id=calendar_id, kind=kind, applies_to=tuple(applies_to), timezone=zone, covers_from=covers[0],
        covers_to=covers[1], dates=dates, actual_through=actual_through or covers[1],
        evidence="synthetic test calendar", prepared_by="test", prepared_on=D(2026, 10, 2), version_label=version,
        lineage=line, default_close=None if ecb else default_close, early_closes=() if ecb else tuple(early),
        fixing_time=datetime.time(14, 10) if ecb else None, publication_time=datetime.time(16, 0) if ecb else None)


def exchange_calendar(calendar_id, mics, dates, **kw):
    return calendar(calendar_id, c.CalendarKind.EXCHANGE_SESSIONS, mics, dates, **kw)


def ecb_calendar(dates, **kw):
    return calendar("ECB_FIXINGS", c.CalendarKind.ECB_FIXINGS, ("ECB",), dates, **kw)


def records_for(readings: Iterable[c.SourceReading]):
    """The registry records a TEST DOUBLE must supply for the sources whose observations it serves (performance/1.12 Ruling 1.7 item 4: a port that serves file observations pins their sources'
    records; a double that reads no file gets the empty-list hash). One synthetic-style record per distinct source, from what its readings carry."""
    from marketdata.manifest import SourceRecord  # noqa: PLC0415

    out = {}
    for r in readings:
        lineage = r.observation.lineage
        out.setdefault(r.source_id, SourceRecord(source_id=r.source_id, name=r.source_id, upstream_provider=lineage.upstream or r.source_id,
                                                 independence_group=r.independence_group or r.source_id, synthetic=bool(lineage.is_synthetic)))
    return list(out.values())


def registry_for(store):
    """The registry `persistence.market_data_store.read_release` REQUIRES, for a test world: the records the in-memory build of that world read (performance/1.12 Ruling 1.7 item 4)."""
    from marketdata.manifest import SourceRegistry  # noqa: PLC0415

    return SourceRegistry(store.source_registry_records())


def store(readings: Iterable[c.SourceReading], mic: Optional[str] = "XNYS", precedence=(), fx_windows=None,
          exclusions=()):
    """`fx_windows` (file hash -> FXFileWindow) is the Ruling 1.1a item 5 coverage window the build path derives
    from a manifest; with none given the date-set check cannot run (UNVERIFIABLE), never guessed from held dates."""
    release = MarketDataRelease(name="t", files=(), source_precedence=tuple(precedence))
    readings = list(readings)
    return InMemoryMarketData(release, readings, exchange_of=(lambda lid: mic), fx_windows=fx_windows,
                              exclusions=exclusions, source_records=records_for(readings))


# --- file payload builders (synthetic copies of the real structures) ----------------------------

def av_csv(rows: Sequence[Tuple[str, str, str, str, str, str]], newest_first=True) -> bytes:
    """timestamp,open,high,low,close,volume, rows given oldest first."""
    ordered = list(reversed(rows)) if newest_first else list(rows)
    lines = ["timestamp,open,high,low,close,volume"] + [",".join(r) for r in ordered]
    return ("\n".join(lines) + "\n").encode("utf-8")


def ecb_csv(rows: Sequence[Tuple[str, Sequence[str]]], currencies: Sequence[str], newest_first=True,
            trailing_comma=True) -> bytes:
    """Date,<ccy...>, rows given oldest first as (date, values)."""
    tail = "," if trailing_comma else ""
    ordered = list(reversed(rows)) if newest_first else list(rows)
    lines = ["Date," + ",".join(currencies) + tail] + [d + "," + ",".join(v) + tail for d, v in ordered]
    return ("\n".join(lines) + "\n").encode("utf-8")


def calendar_json(calendar_id="NYSE_SESSIONS", kind="EXCHANGE_SESSIONS", applies_to=("XNYS", "XNAS"),
                  timezone="America/New_York", coverage=("2025-01-01", "2025-01-31"),
                  dates=("2025-01-02", "2025-01-03"), actual_through=None, **overrides) -> bytes:
    doc = {
        "schema": "finweb.marketdata.calendar/1", "calendar_id": calendar_id, "kind": kind,
        "applies_to": list(applies_to), "timezone": timezone, "coverage": {"from": coverage[0], "to": coverage[1]},
        "dates": list(dates), "actual_through": actual_through or coverage[1],
        "evidence": "synthetic: not a real holiday list", "prepared_by": "test", "prepared_on": "2026-10-02",
        "version": "v1",
    }
    if kind == "EXCHANGE_SESSIONS":
        doc["close"] = {"default": "16:00", "overrides": []}
    else:
        doc["fixing"] = {"time": "14:10", "publication": "16:00"}
    doc.update(overrides)
    return json.dumps(doc).encode("utf-8")
