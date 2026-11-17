"""Normalize only the shipped fictional raw inputs; no test or expected-output imports.

This deliberately bounded demo adapter does not admit or download any real source.
The fixture hashes, adapter version, synthetic lineage and raw source rows remain
in the existing deterministic engines' manifests. No financial metric is derived
here. Historical coverage and classification are intentionally absent.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from diversification.engine import compute_diversification
from domain.currency import CurrencyCode, Money
from domain.instrument import SecurityType
from domain.ledger import EventType, LedgerEvent
from domain.replay import SequencedEvent
from insight_service.service import compute_insights
from insight_service.sources import DiversificationSource
from insights.contracts import InsightRefusal
from marketdata.calendars import CalendarSet
from marketdata.canonical import canonical_json, sha256_hex
from marketdata.contracts import (AdjustmentStatus, CalendarDays, CalendarKind,
    DataDelayStatus, Lineage, QuoteObservation, SourceReading, SourceTiming, UsageScope)
from marketdata.manifest import MarketDataRelease, SourceRecord
from marketdata.market11 import market11_conventions
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry
from marketdata.store import InMemoryMarketData
from performance.engine import compute, performance_conventions
from product_contract.analytics_policy import load_approved_capital_policy
from risk_service.catalogs import load_benchmark_catalog

FIXTURES = Path(__file__).with_name("fixtures")
SOURCE = "finweb.cp7.synthetic"
ADAPTER = "finweb.cp7.raw-demo"
ADAPTER_VERSION = "1.0"
MODE = "LOCAL_SYNTHETIC_GUEST"
LIMITATIONS = (
    "SYNTHETIC_ONLY: fictional securities, prices and one-date calendar; no real market claim.",
    "EPHEMERAL_GUEST: state expires after one hour or process restart; not saved to an account.",
    "USD_ONLY: other reporting currencies have no admitted FX path in this increment.",
    "SNAPSHOT_ONLY: no historical total-return coverage, benchmark selection or personal risk limits.",
    "CLASSIFICATION_UNKNOWN: issuer country and sector are not inferred from a trading venue.",
    "HISTORICAL_AS_OF: freshness is assessed at the labelled synthetic date, not current/live.",
)


def _load(name):
    raw = (FIXTURES / name).read_bytes()
    return json.loads(raw), sha256_hex(raw)


def _instant(text):
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


class SyntheticWorld:
    def __init__(self, *, benchmark_catalog_provider=None):
        # File I/O belongs to this edge; persistence receives only the callable.
        self.benchmark_catalog_provider = load_benchmark_catalog if benchmark_catalog_provider is None else benchmark_catalog_provider
        if not callable(self.benchmark_catalog_provider):
            raise TypeError("A callable benchmark catalog provider is required")
        self.raw, self.input_sha256 = _load("quotes-v1.json")
        calendar, self.calendar_sha256 = _load("calendar-v1.json")
        self.as_of = dt.date.fromisoformat(self.raw["as_of"])
        self.currency = CurrencyCode(self.raw["currency"])
        self.resolver = InMemoryIdentityRegistry(self._id)
        self._next_id = 100
        registered = self.resolver.register_instruments(tuple(InstrumentEntry(
            row["issuer"], SecurityType.COMMON_STOCK, self.raw["mic"], "NYSE",
            row["symbol"], self.currency) for row in self.raw["quotes"]))
        self.listings = {entry.entry.ticker: entry.listing_id for entry in registered}
        self.symbols = {str(value): key for key, value in self.listings.items()}
        retrieved = _instant(self.raw["retrieved_at"])
        cal_lineage = self._lineage(self.calendar_sha256, "calendar", _instant(calendar["registered_at"]))
        cal = CalendarDays(calendar["calendar_id"], CalendarKind.EXCHANGE_SESSIONS,
            (calendar["mic"],), calendar["timezone"], dt.date.fromisoformat(calendar["covers_from"]),
            dt.date.fromisoformat(calendar["covers_to"]), tuple(dt.date.fromisoformat(s) for s in calendar["dates"]),
            dt.date.fromisoformat(calendar["actual_through"]), calendar["label"], "CP7 raw synthetic fixture",
            dt.date.fromisoformat(calendar["prepared_on"]), "v1", cal_lineage,
            default_close=dt.time.fromisoformat(calendar["default_close"]))
        self.conventions = market11_conventions(CalendarSet((cal,)))
        release = MarketDataRelease("CP7 fictional snapshot v1", tuple(sorted((self.input_sha256, self.calendar_sha256))),
                                    (SOURCE,), created_for="PD-0042 local synthetic guest only")
        readings = tuple(SourceReading(SOURCE, SOURCE, self.input_sha256, QuoteObservation(
            self.listings[row["symbol"]], self.as_of, Decimal(row["price"]), self.currency,
            SourceTiming(delay_status=DataDelayStatus.END_OF_DAY),
            self._lineage(self.input_sha256, "quotes:" + row["symbol"], retrieved, row["price"]),
            volume=Decimal(row["volume"]))) for row in self.raw["quotes"])
        record = SourceRecord(SOURCE, self.raw["label"], "fictional raw fixture", SOURCE, synthetic=True)
        self.port = InMemoryMarketData(release, readings, exchange_of=self.resolver.exchange_mic,
                                      contains_synthetic=True, source_records=(record,))
        self.perf = performance_conventions()

    def _id(self):
        self._next_id += 1
        return uuid.UUID(int=self._next_id)

    @staticmethod
    def _lineage(digest, ref, retrieved, value=None):
        return Lineage("CP7 fictional raw fixture", AdjustmentStatus.RAW,
            source_id=SOURCE, file_sha256=digest, adapter_id=ADAPTER, adapter_version=ADAPTER_VERSION,
            source_record_ref=ref, retrieved_at=retrieved, usage_scope=UsageScope.SYNTHETIC_TEST,
            upstream="fictional raw fixture", independence_group=SOURCE, source_value_text=value, market="US")

    def capabilities(self):
        return {"mode": MODE, "synthetic": True, "as_of": self.as_of.isoformat(),
            "reporting_currencies": [{"code": "USD", "available": True, "reason": None},
                                      {"code": "CNY", "available": False, "reason": "FX_PATH_UNAVAILABLE"}],
            "listings": [{"symbol": row["symbol"], "listing_id": str(self.listings[row["symbol"]]),
                          "name": row["issuer"], "currency": "USD"} for row in self.raw["quotes"]],
            "defaults": {"name": "Synthetic demonstration", "reporting_currency": "USD",
                         "positions": [{"symbol": "SYN-A", "quantity": "10"}, {"symbol": "SYN-B", "quantity": "10"}],
                         "cash": "500", "synthetic_acknowledged": True},
            "limitations": list(LIMITATIONS)}

    def opening_events(self, portfolio_id, request):
        account_id = uuid.uuid5(portfolio_id, "guest-account")
        events = []
        for position in sorted(request["positions"], key=lambda item: item["symbol"]):
            events.append(SequencedEvent(len(events) + 1, LedgerEvent(
                event_id=uuid.uuid5(portfolio_id, position["symbol"]), account_id=account_id,
                event_type=EventType.OPENING_POSITION, event_date=self.as_of, currency=self.currency,
                listing_id=self.listings[position["symbol"]], quantity=Decimal(position["quantity"]),
                source_reference="CP7 manual synthetic opening snapshot")))
        if Decimal(request["cash"]) > 0:
            events.append(SequencedEvent(len(events) + 1, LedgerEvent(
                event_id=uuid.uuid5(portfolio_id, "cash"), account_id=account_id,
                event_type=EventType.OPENING_CASH, event_date=self.as_of, currency=self.currency,
                amount=Money(Decimal(request["cash"]), self.currency),
                source_reference="CP7 manual synthetic opening snapshot")))
        return tuple(events)

    def create(self, portfolio_id, request, *, ledger_events=None, as_of=None, policies=(), workspace=False, benchmark_pin=None):
        events = self.opening_events(portfolio_id, request) if ledger_events is None else tuple(ledger_events)
        pin = max((item.ledger_seq for item in events), default=0)
        day = self.as_of if as_of is None else as_of
        valuation = compute(events, pin, day, self.currency, self.port, self.resolver,
                            self.conventions, self.perf, suppressions=(), portfolio_id=portfolio_id)
        exposure = compute_diversification(events, pin, day, self.currency, self.port, self.resolver,
            self.conventions, self.perf, suppressions=(), metadata=None,
            capital_policy=load_approved_capital_policy(), portfolio_id=portfolio_id)
        source = DiversificationSource(exposure, events, self.port, self.resolver, self.conventions,
                                       self.perf, (), None, freshness_result=valuation)
        insights = compute_insights((source,), policies=policies, allow_synthetic=True)
        if isinstance(insights, InsightRefusal):
            raise ValueError(insights.code + ": " + insights.detail)
        snapshot = {"schema_version": "finweb.cp7/1", "portfolio_id": str(portfolio_id), "name": request["name"],
            "mode": MODE, "synthetic": True, "persisted": False, "reporting_currency": "USD",
            "as_of": day, "limitations": list(LIMITATIONS),
            "inputs": {"positions": request["positions"], "cash": request["cash"]},
            "valuation": {"manifest_id": valuation.manifest.manifest_id, "result_digest": valuation.result_digest,
                          "metrics": [m.to_canonical_dict() for m in valuation.metrics]},
            "diversification": {"manifest_id": exposure.manifest_id, "result_digest": exposure.result_digest,
                                "metrics": [m.to_obj() for m in exposure.metrics]},
            "insights": {"manifest_id": insights.manifest_id, "result_digest": insights.result_digest,
                         "packets": [packet.to_obj() for packet in insights.packets],
                         "diagnostics": json.loads(insights.diagnostics_json)},
            "provenance": {"source_id": SOURCE, "input_sha256": self.input_sha256,
                           "calendar_sha256": self.calendar_sha256, "release_id": self.port.release.release_id,
                           "synthetic": True}}
        if workspace:
            snapshot["limitations"] = [note for note in snapshot["limitations"] if not note.startswith("SNAPSHOT_ONLY:")]
            snapshot["limitations"].append("ONE_DATE_MARKET_SOURCE: fictional quotes/calendar only cover 2026-01-02; later ledger facts do not create later market data.")
            snapshot["provenance"]["fixture_as_of"] = self.as_of.isoformat()
            snapshot["preferences"] = {"benchmark_pin": benchmark_pin}
        # Store bytes, not shared mutable response dictionaries.
        return GuestPortfolio(canonical_json(snapshot), source, insights, tuple(policies))


@dataclass(frozen=True)
class GuestPortfolio:
    snapshot_json: str
    source: DiversificationSource
    insights: object
    policies: tuple = ()

    def snapshot(self):
        return json.loads(self.snapshot_json)
