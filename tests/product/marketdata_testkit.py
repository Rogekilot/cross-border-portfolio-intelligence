"""Shared helpers for the CP2 market-data tests (not collected as a test module).

Everything here is SYNTHETIC: hand-written numbers and invented source formats that imitate
nothing a vendor ships. Two test-local adapters read two different hand-made formats of the
same facts, standing in for real source adapters until the human `probe` run (CP2b).
"""

import csv
import datetime
import io
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.instrument import SecurityType  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from domain.replay import SequencedEvent, reconstruct  # noqa: E402
from marketdata.adapters.base import (  # noqa: E402
    AdapterIssue,
    AdapterOutput,
    AdapterRegistry,
    IssueCode,
    lineage_for,
    timing_for,
)
from marketdata.adapters.mock import MOCK_FORMAT, MOCK_SOURCE_ID, MockSyntheticAdapter, make_synthetic_payload  # noqa: E402
from marketdata.canonical import sha256_hex  # noqa: E402
from marketdata.contracts import (  # noqa: E402
    AdjustmentStatus,
    DataDelayStatus,
    ExternalIdentifiers,
    FXObservation,
    UnresolvedQuote,
    UsageScope,
)
from marketdata.files import FileStore  # noqa: E402
from marketdata.manifest import (  # noqa: E402
    DataKind,
    FileManifest,
    MarketDataRelease,
    SourceRecord,
    SourceRegistry,
)
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402

USD, HKD, CNY, EUR = (CurrencyCode(c) for c in ("USD", "HKD", "CNY", "EUR"))
DAY1 = datetime.date(2025, 1, 2)
DAY2 = datetime.date(2025, 1, 3)
RETRIEVED = datetime.datetime(2025, 1, 10, 9, 0, tzinfo=datetime.timezone.utc)

# The same facts, written three ways by the three sources below.
QUOTES = (
    # ticker, mic, date, close text, volume text, currency
    ("AAPL", "XNAS", DAY1, "150.25", "1000", USD),
    ("AAPL", "XNAS", DAY2, "151.10", "1200", USD),
    ("0700", "XHKG", DAY1, "330.400", "5000", HKD),
    ("600519", "XSHG", DAY1, "1500.00", "800", CNY),
)
FX = (
    # base, quote, date, rate text  (published directly in this synthetic world)
    ("HKD", "USD", DAY1, "0.1288"),
    ("CNY", "USD", DAY1, "0.1370"),
)


class SequentialIds:
    """Deterministic id factory (product code has no randomness)."""

    def __init__(self, start: int = 1000):
        self._n = start

    def __call__(self) -> uuid.UUID:
        self._n += 1
        return uuid.UUID(int=self._n)


def make_identity() -> InMemoryIdentityRegistry:
    registry = InMemoryIdentityRegistry(SequentialIds())
    registry.register_instruments([
        InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", USD),
        InstrumentEntry("Tencent Holdings", SecurityType.COMMON_STOCK, "XHKG", "HKEX", "0700", HKD),
        InstrumentEntry("Kweichow Moutai", SecurityType.COMMON_STOCK, "XSHG", "SSE", "600519", CNY),
    ])
    return registry


def listing_id(registry: InMemoryIdentityRegistry, ticker: str, mic: str) -> uuid.UUID:
    res = registry.resolve(ExternalIdentifiers(ticker=ticker, mic=mic), None)
    assert res.listing_id is not None, res
    return res.listing_id


# --- two hand-made formats, each with its own adapter -------------------------------------

CSV_SOURCE = "testvendor.csv"
JSONL_SOURCE = "testvendor.jsonl"
CSV_FORMAT = "testvendor_csv/1"
JSONL_FORMAT = "testvendor_jsonl/1"


def csv_quotes_payload(rows=QUOTES) -> bytes:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["symbol", "mic", "trade_date", "last_close", "vol"])
    for t, m, d, c, v, _ in rows:
        w.writerow([t, m, d.strftime("%Y%m%d"), c, v])
    return out.getvalue().encode("utf-8")


def csv_fx_payload() -> bytes:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["pair", "fixing", "rate"])
    for b, q, d, r in FX:
        w.writerow([b + q, d.strftime("%Y%m%d"), r])
    return out.getvalue().encode("utf-8")


def jsonl_quotes_payload(rows=QUOTES) -> bytes:
    lines = []
    for t, m, d, c, v, _ in rows:
        # trailing zeros differ from the CSV rendering on purpose: same fact, other text
        lines.append(json.dumps({"t": t, "x": m, "d": d.isoformat(), "c": c + "0", "v": v}))
    return ("\n".join(lines) + "\n").encode("utf-8")


def jsonl_fx_payload() -> bytes:
    lines = [json.dumps({"from": b, "to": q, "d": d.isoformat(), "r": r + "00"}) for b, q, d, r in FX]
    return ("\n".join(lines) + "\n").encode("utf-8")


class _TestAdapterBase:
    adapter_version = "0.1.0"

    def _issue(self, ref: str, detail: str) -> AdapterIssue:
        return AdapterIssue(ref, IssueCode.UNPARSEABLE_ROW, detail)


class CsvQuoteAdapter(_TestAdapterBase):
    adapter_id = "testvendor.csv.quotes"
    source_id = CSV_SOURCE
    data_kind = DataKind.QUOTE
    payload_formats = (CSV_FORMAT,)

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        rows, issues = [], []
        for i, row in enumerate(csv.DictReader(io.StringIO(payload.decode("utf-8")))):
            ref = f"row{i}"
            try:
                rows.append(UnresolvedQuote(
                    identifiers=ExternalIdentifiers(ticker=row["symbol"], mic=row["mic"]),
                    value_date=datetime.datetime.strptime(row["trade_date"], "%Y%m%d").date(),
                    price=Decimal(row["last_close"]),
                    currency=manifest.declared_currency,
                    timing=timing_for(manifest),
                    lineage=lineage_for(manifest, self, ref, source_value_text=row["last_close"]),
                    volume=Decimal(row["vol"]),
                ))
            except Exception as exc:  # a test adapter: report, never drop silently
                issues.append(self._issue(ref, str(exc)))
        return AdapterOutput(quotes=tuple(rows), issues=tuple(issues))


class CsvFXAdapter(_TestAdapterBase):
    adapter_id = "testvendor.csv.fx"
    source_id = CSV_SOURCE
    data_kind = DataKind.FX
    payload_formats = (CSV_FORMAT,)

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        rows = []
        for i, row in enumerate(csv.DictReader(io.StringIO(payload.decode("utf-8")))):
            rows.append(FXObservation(
                CurrencyCode(row["pair"][:3]), CurrencyCode(row["pair"][3:]),
                datetime.datetime.strptime(row["fixing"], "%Y%m%d").date(),
                Decimal(row["rate"]), timing_for(manifest),
                lineage_for(manifest, self, f"row{i}", source_value_text=row["rate"]),
                rate_basis="testvendor daily",
            ))
        return AdapterOutput(fx=tuple(rows))


class JsonlQuoteAdapter(_TestAdapterBase):
    adapter_id = "testvendor.jsonl.quotes"
    source_id = JSONL_SOURCE
    data_kind = DataKind.QUOTE
    payload_formats = (JSONL_FORMAT,)

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        rows = []
        for i, line in enumerate(payload.decode("utf-8").splitlines()):
            obj = json.loads(line)
            rows.append(UnresolvedQuote(
                ExternalIdentifiers(ticker=obj["t"], mic=obj["x"]),
                datetime.date.fromisoformat(obj["d"]), Decimal(obj["c"]),
                manifest.declared_currency, timing_for(manifest),
                lineage_for(manifest, self, f"line{i}", source_value_text=obj["c"]),
                volume=Decimal(obj["v"]),
            ))
        return AdapterOutput(quotes=tuple(rows))


class JsonlFXAdapter(_TestAdapterBase):
    adapter_id = "testvendor.jsonl.fx"
    source_id = JSONL_SOURCE
    data_kind = DataKind.FX
    payload_formats = (JSONL_FORMAT,)

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        rows = []
        for i, line in enumerate(payload.decode("utf-8").splitlines()):
            obj = json.loads(line)
            rows.append(FXObservation(
                CurrencyCode(obj["from"]), CurrencyCode(obj["to"]),
                datetime.date.fromisoformat(obj["d"]), Decimal(obj["r"]), timing_for(manifest),
                lineage_for(manifest, self, f"line{i}", source_value_text=obj["r"]),
                rate_basis="testvendor daily",
            ))
        return AdapterOutput(fx=tuple(rows))


# --- writing files in the real layout ----------------------------------------------------

def write_file(
    root: Path,
    source_id: str,
    kind: DataKind,
    payload_format: str,
    payload: bytes,
    label: str,
    ext: str,
    usage_scope: UsageScope = UsageScope.SYNTHETIC_TEST,
    currency: Optional[CurrencyCode] = None,
    adjustment: AdjustmentStatus = AdjustmentStatus.RAW,
    source_identifiers: Tuple[str, ...] = (),
    retrieved_by: str = "synthetic",
    anchor: Optional[str] = None,
    request: Tuple[Tuple[str, str], ...] = (),
    market: Optional[str] = None,
) -> FileManifest:
    directory = root / "files" / source_id / kind.value.lower() / "2025-01-10"
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{label}.{ext}"
    manifest = FileManifest(
        file_sha256=sha256_hex(payload), size_bytes=len(payload), payload_filename=name,
        payload_format=payload_format, source_id=source_id, data_kind=kind,
        retrieval_time=RETRIEVED, retrieved_by=retrieved_by, declared_adjustment=adjustment,
        usage_scope=usage_scope, declared_currency=currency, declared_delay=DataDelayStatus.END_OF_DAY,
        source_identifiers=source_identifiers, adjustment_anchor=anchor, request=request, market=market,
    )
    (directory / name).write_bytes(payload)
    (directory / (name + ".manifest.json")).write_text(manifest.to_json(), encoding="utf-8")
    return manifest


def write_registry(root: Path, extra: Iterable[SourceRecord] = ()) -> None:
    records = [
        SourceRecord(MOCK_SOURCE_ID, "Mock synthetic", "synthetic", "synthetic.mock", synthetic=True),
        SourceRecord(CSV_SOURCE, "Test CSV vendor", "synthetic", "synthetic.csv", synthetic=True),
        SourceRecord(JSONL_SOURCE, "Test JSONL vendor", "synthetic", "synthetic.jsonl", synthetic=True),
    ] + list(extra)
    def entry(r):
        item = {"source_id": r.source_id, "name": r.name, "upstream_provider": r.upstream_provider,
                "independence_group": r.independence_group, "synthetic": r.synthetic}
        if r.source_priority is not None:
            item["source_priority"] = r.source_priority
        if r.terms_check is not None:
            item["terms_check"] = {
                "checked_by": r.terms_check.checked_by, "checked_on": r.terms_check.checked_on.isoformat(),
                "permits_internal_development_use": r.terms_check.permits_internal_development_use}
        return item

    obj = {"sources": [entry(r) for r in records]}
    root.mkdir(parents=True, exist_ok=True)
    (root / "SOURCES.json").write_text(json.dumps(obj), encoding="utf-8")


def mock_quotes_payload() -> bytes:
    return make_synthetic_payload(quotes=tuple(
        {"ticker": t, "mic": m, "date": d.isoformat(), "close": Decimal(c), "volume": Decimal(v)}
        for t, m, d, c, v, _ in QUOTES))


def mock_fx_payload() -> bytes:
    return make_synthetic_payload(fx=tuple(
        {"base": b, "quote": q, "date": d.isoformat(), "rate": Decimal(r), "rate_basis": "synthetic"}
        for b, q, d, r in FX))


def build_world(root: Path, flavour: str) -> Tuple[FileStore, MarketDataRelease, AdapterRegistry]:
    """Write the synthetic facts in one flavour's format and cut a release over them.
    The currency of a quote file is declared per file, so quotes go in one file per currency."""
    write_registry(root)
    manifests: List[FileManifest] = []
    adapters = AdapterRegistry()
    by_ccy: Dict[CurrencyCode, List[tuple]] = {}
    for q in QUOTES:
        by_ccy.setdefault(q[5], []).append(q)
    if flavour == "mock":
        source = MOCK_SOURCE_ID
        adapters.register(MockSyntheticAdapter(DataKind.QUOTE))
        adapters.register(MockSyntheticAdapter(DataKind.FX))
        for ccy, rows in by_ccy.items():
            payload = make_synthetic_payload(quotes=tuple(
                {"ticker": t, "mic": m, "date": d.isoformat(), "close": Decimal(c), "volume": Decimal(v)}
                for t, m, d, c, v, _ in rows))
            manifests.append(write_file(root, source, DataKind.QUOTE, MOCK_FORMAT, payload,
                                        f"quotes_{ccy.code}", "json", currency=ccy,
                                        source_identifiers=tuple(sorted({r[0] for r in rows}))))
        manifests.append(write_file(root, source, DataKind.FX, MOCK_FORMAT, mock_fx_payload(),
                                    "fx", "json", source_identifiers=("HKD", "CNY")))
    else:
        if flavour == "csv":
            source, fmt, ext = CSV_SOURCE, CSV_FORMAT, "csv"
            adapters.register(CsvQuoteAdapter())
            adapters.register(CsvFXAdapter())
            quote_payload, fx_payload = csv_quotes_payload, csv_fx_payload
        else:
            source, fmt, ext = JSONL_SOURCE, JSONL_FORMAT, "jsonl"
            adapters.register(JsonlQuoteAdapter())
            adapters.register(JsonlFXAdapter())
            quote_payload, fx_payload = jsonl_quotes_payload, jsonl_fx_payload
        for ccy, rows in by_ccy.items():
            # one file per currency: the format has no currency column, the manifest declares it
            payload = quote_payload(tuple(rows))
            manifests.append(write_file(root, source, DataKind.QUOTE, fmt, payload,
                                        f"quotes_{ccy.code}", ext, currency=ccy,
                                        source_identifiers=tuple(sorted({r[0] for r in rows}))))
        manifests.append(write_file(root, source, DataKind.FX, fmt, fx_payload(), "fx", ext,
                                    source_identifiers=("HKD", "CNY")))
    release = MarketDataRelease.from_manifests(f"synthetic-{flavour}", manifests, [source])
    return FileStore(root), release, adapters


def replayed_state(registry: InMemoryIdentityRegistry, as_of: datetime.date):
    """A CP1 replay of one account holding the three listings, with cash in each currency."""
    account = uuid.UUID(int=1)
    events = []
    seq = 0
    n = 0

    def add(**kwargs):
        nonlocal seq, n
        seq += 1
        n += 1
        events.append(SequencedEvent(seq, LedgerEvent(
            event_id=uuid.UUID(int=500 + n), account_id=account, event_date=datetime.date(2024, 12, 20),
            **kwargs)))

    for ccy in (USD, HKD, CNY):
        add(event_type=EventType.DEPOSIT, currency=ccy, amount=Money(Decimal(100000), ccy))
    for ticker, mic, ccy, qty, cost in (("AAPL", "XNAS", USD, 10, 1500), ("0700", "XHKG", HKD, 100, 33000),
                                         ("600519", "XSHG", CNY, 2, 3000)):
        add(event_type=EventType.BUY, currency=ccy, listing_id=listing_id(registry, ticker, mic),
            quantity=Decimal(qty), amount=Money(Decimal(cost), ccy))
    return reconstruct(events, as_of, seq)
