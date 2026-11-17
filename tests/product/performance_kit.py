"""Synthetic worlds for the CP3b tests (not collected as a test module). EVERYTHING HERE IS SYNTHETIC: invented prices and rates, read by the real market-data port
(`InMemoryMarketData`) and the real conventions (`market11_conventions`); results computed from it say `synthetic`.

The facts are `performance/1.0` Example W (section 5) and its relatives:

  ECB fixings (units per EUR, hypothetical):   2025-04-01: USD 1.0800, HKD 8.4000    -> X(HKD->USD) = 1.0800/8.4000 = 9/70
                                               2025-04-02, 04-03: USD 1.0800, HKD 8.4240 -> X(HKD->USD) = 1.0800/8.4240 = 5/39
  H@XHKG closes:                               2025-04-01 390.00, 04-02 400.00, 04-03 400.00
"""

import datetime
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402

k = x.k
c = x.c

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from domain.replay import SequencedEvent  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.manifest import MarketDataRelease  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.store import InMemoryMarketData  # noqa: E402

D = datetime.date
USD, HKD, CNY, CNH = CurrencyCode("USD"), CurrencyCode("HKD"), CurrencyCode("CNY"), CurrencyCode("CNH")
A1, A2 = uuid.UUID(int=1), uuid.UUID(int=2)
RETRIEVED_LONG_AGO = datetime.datetime(2025, 3, 1, 0, 0, tzinfo=datetime.timezone.utc)

#: hypothetical ECB quotes by fixing date
FIXINGS = {
    D(2025, 3, 25): {"USD": "1.0800", "HKD": "8.4000"}, D(2025, 3, 26): {"USD": "1.0800", "HKD": "8.4000"},
    D(2025, 3, 27): {"USD": "1.0800", "HKD": "8.4000"}, D(2025, 3, 28): {"USD": "1.0800", "HKD": "8.4000"},
    D(2025, 3, 31): {"USD": "1.0800", "HKD": "8.4000"},
    D(2025, 4, 1): {"USD": "1.0800", "HKD": "8.4000"},
    D(2025, 4, 2): {"USD": "1.0800", "HKD": "8.4240"},
    D(2025, 4, 3): {"USD": "1.0800", "HKD": "8.4240"},
}
H_CLOSES = {D(2025, 4, 1): "390.00", D(2025, 4, 2): "400.00", D(2025, 4, 3): "400.00"}
SESSIONS = tuple(D(2025, 3, 24) + datetime.timedelta(days=i) for i in range(0, 12)
                 if (D(2025, 3, 24) + datetime.timedelta(days=i)).weekday() < 5)  # 2025-03-24 .. 2025-04-04, weekdays (invented)


def lineage(source_id: str, group_market: str, retrieved: datetime.datetime = RETRIEVED_LONG_AGO, sha: str = "e" * 64):
    return c.Lineage(source_id, c.AdjustmentStatus.RAW, source_id=source_id, file_sha256=sha, adapter_id="ad", adapter_version="1",
                     source_record_ref="r", retrieved_at=retrieved, usage_scope=c.UsageScope.SYNTHETIC_TEST, market=group_market)


def quote(listing: uuid.UUID, day: D, price: str, ccy: CurrencyCode, market: str, retrieved=RETRIEVED_LONG_AGO, volume="1000", sha: str = "d" * 64):
    source = f"synthetic.{market.lower()}"
    obs = c.QuoteObservation(listing, day, Decimal(price), ccy, c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY),
                             lineage(source, market, retrieved, sha), volume=Decimal(volume), recovered=True,
                             precision_bound=Decimal("0"))
    return c.SourceReading(source, source, sha, obs)


# --- engine entry points with the suppressions STATED (CP3-4) ------------------------------------------------------------------------------------
# The engine's pure entries have no default for `suppressions`. A test that has no corroborated split says so here, once, by name; a test that has one passes it.

def compute(*args, suppressions=(), **kw):
    from performance import engine  # noqa: PLC0415
    return engine.compute(*args, suppressions=suppressions, **kw)


def compute_window(*args, suppressions=(), **kw):
    from performance import engine  # noqa: PLC0415
    return engine.compute_window(*args, suppressions=suppressions, **kw)


def reproduce(*args, suppressions=(), **kw):
    from performance import engine  # noqa: PLC0415
    return engine.reproduce(*args, suppressions=suppressions, **kw)


class InMemoryMarketAt:
    """`M_t` for the in-memory world: the readings of `M` whose retrieval time is at or before `t`, in a new `InMemoryMarketData` (a derived release), with the
    calendars as they are and the hashes of the files left out. A reading of a dropped file never supplies a value (a derived release, not a read-time hide)."""

    def __init__(self, world: "World"):
        self.world = world

    def view(self, instant: datetime.datetime):
        from performance.inputs import MarketView  # noqa: PLC0415

        w = self.world
        keep = [r for r in w.readings if r.observation.lineage.retrieved_at <= instant]
        kept_shas = {r.file_sha256 for r in keep}
        left_out = tuple(sorted({r.file_sha256 for r in w.readings if r.observation.lineage.retrieved_at > instant} - kept_shas))
        release = MarketDataRelease(name=f"{w.store.release.name}@{instant.isoformat()}", files=(), source_precedence=())
        store = InMemoryMarketData(release, keep, exchange_of=w.ident.exchange_mic, contains_synthetic=w.store.contains_synthetic, source_records=k.records_for(keep))
        return MarketView(store, w.calendars, w.market, w.store.release_id(), left_out, instant)


def fixing(day: D, ccy: str, rate: str, retrieved=RETRIEVED_LONG_AGO):
    obs = c.FXObservation(CurrencyCode("EUR"), CurrencyCode(ccy), day, Decimal(rate),
                          c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY), lineage("synthetic.ecb", "FX", retrieved, "c" * 64), "ecb")
    return c.SourceReading("synthetic.ecb", "synthetic.ecb", "c" * 64, obs)


class World:
    """A market-data version, the calendars and an identity registry (the CP2 exit kit's three listings)."""

    def __init__(self, readings: Sequence, fixing_days: Optional[Iterable[D]] = None, calendar_to: Optional[D] = None,
                 hk_close: datetime.time = datetime.time(16, 10)):
        self.ident = x.identity()
        self.h = x.lid(self.ident, "0700", "XHKG")
        self.aapl = x.lid(self.ident, "AAPL", "XNAS")
        days = SESSIONS if calendar_to is None else tuple(d for d in SESSIONS if d <= calendar_to)
        self.calendars = CalendarSet([
            k.exchange_calendar("HKEX_SESSIONS", ("XHKG",), days, tz="Asia/Hong_Kong", default_close=hk_close),
            k.exchange_calendar("NYSE_SESSIONS", ("XNYS", "XNAS"), days, tz="America/New_York"),
            k.ecb_calendar(tuple(fixing_days) if fixing_days is not None else days),
        ])
        release = MarketDataRelease(name="perf-kit", files=(), source_precedence=())
        self.readings = list(readings)
        self.store = InMemoryMarketData(release, self.readings, exchange_of=self.ident.exchange_mic, source_records=k.records_for(self.readings))
        self.market = market11_conventions(self.calendars)
        self.market_at = InMemoryMarketAt(self)


def example_w_readings(h: uuid.UUID, closes: Optional[Dict[D, str]] = None, fixings: Optional[Dict[D, Dict[str, str]]] = None):
    out = []
    for day, price in (closes or H_CLOSES).items():
        out.append(quote(h, day, price, HKD, "HK"))
    for day, rates in (fixings or FIXINGS).items():
        for ccy, rate in rates.items():
            out.append(fixing(day, ccy, rate))
    return out


def world_w(closes: Optional[Dict[D, str]] = None, extra: Sequence = (), **kw) -> World:
    """A world whose readings are Example W's, built in two steps because the listing ids come from the identity registry."""
    probe = x.identity()
    h = x.lid(probe, "0700", "XHKG")
    return World(example_w_readings(h, closes) + list(extra), **kw)


class Ledger:
    """Hand-written ledger events with consecutive `ledger_seq` and deterministic ids."""

    def __init__(self, base: int = 7000):
        self.rows: List[SequencedEvent] = []
        self._base = base

    def add(self, account: uuid.UUID, event_type: EventType, day: D, currency: CurrencyCode, **kw) -> "Ledger":
        n = len(self.rows) + 1
        self.rows.append(SequencedEvent(n, LedgerEvent(event_id=uuid.UUID(int=self._base + n), account_id=account,
                                                       event_type=event_type, event_date=day, currency=currency, **kw)))
        return self

    def money(self, amount: str, currency: CurrencyCode) -> Money:
        return Money(Decimal(amount), currency)

    @property
    def version(self) -> int:
        return len(self.rows)


def example_w_ledger(h: uuid.UUID) -> Ledger:
    """Example W (performance/1.0 section 5): account A1.

    04-01  DEPOSIT 10,000 USD; CURRENCY_CONVERSION 5,000 USD -> 38,800 HKD; BUY H 100 for 38,000 HKD; FEE 10 HKD (listing H)
    04-02  WITHDRAWAL 1,000 USD
    04-03  DIVIDEND H 200 HKD (gross, no ex_date: cash basis); TAX H 20 HKD (withholding)
    """
    L = Ledger()
    d1, d2, d3 = D(2025, 4, 1), D(2025, 4, 2), D(2025, 4, 3)
    L.add(A1, EventType.DEPOSIT, d1, USD, amount=L.money("10000", USD))
    L.add(A1, EventType.CURRENCY_CONVERSION, d1, USD, amount=L.money("5000", USD), bought_amount=L.money("38800", HKD))
    L.add(A1, EventType.BUY, d1, HKD, listing_id=h, quantity=Decimal(100), amount=L.money("38000", HKD))
    L.add(A1, EventType.FEE, d1, HKD, listing_id=h, amount=L.money("10", HKD))
    L.add(A1, EventType.WITHDRAWAL, d2, USD, amount=L.money("1000", USD))
    L.add(A1, EventType.DIVIDEND, d3, HKD, listing_id=h, amount=L.money("200", HKD))
    L.add(A1, EventType.TAX, d3, HKD, listing_id=h, amount=L.money("20", HKD))
    return L
