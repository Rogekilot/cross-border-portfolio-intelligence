"""Shared worlds for the CP2 exit test and the PostgreSQL store tests (not collected as a test module).

EVERYTHING HERE IS SYNTHETIC. The numbers are invented; the file FORMATS are the real ones (the Eastmoney and Sina
CSV layouts, the Alpha Vantage CSV, the ECB `eurofxref-hist` CSV, the Frankfurter JSON), read by the real parsers.
Every source id is a SYNTHETIC id registered with `synthetic: true`, so no file here is, or is attested as, a real
source (market-data/1.4 Ruling 4.8; PD-0031/0032), and every result computed from them says `synthetic`.

One set of facts is written out as several complete market-data versions ("worlds"). The facts, and every expected
value derived from them, are in `FACTS` and `expected_value_obj`, with the arithmetic shown.
"""

import datetime
import json
import sys
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import marketdata_cp2c1_kit as k  # noqa: E402

kit = k.kit

from domain.instrument import SecurityType  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata.adapters.akshare_cn import AkshareCnQuoteAdapter  # noqa: E402
from marketdata.adapters.akshare_sina import AkshareSinaQuoteAdapter  # noqa: E402
from marketdata.adapters.alphavantage import AlphaVantageQuoteAdapter  # noqa: E402
from marketdata.adapters.base import AdapterOutput, AdapterRegistry  # noqa: E402
from marketdata.adapters.calendar_file import CalendarFileAdapter  # noqa: E402
from marketdata.adapters.ecb_eurofxref import EcbEurofxrefFxAdapter  # noqa: E402
from marketdata.adapters.frankfurter import FrankfurterFxAdapter  # noqa: E402
from marketdata.adapters.mock import MOCK_FORMAT, MockSyntheticAdapter, make_synthetic_payload  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import BuildResult, build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, FileManifest, MarketDataRelease, SourceRecord  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402

D = datetime.date
USD, HKD, CNY, EUR = k.USD, k.HKD, k.CNY, k.EUR
AS_OF = D(2025, 1, 3)
LATER = D(2025, 1, 6)  # one session after the last datum
SESSIONS = ("2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07")

# The synthetic sources (never the real ids): who is registered, and which format their files are in.
SRC_MOCK = "mock.synthetic"
SRC_CN = "synthetic.eastmoney_cn"      # the Eastmoney CSV layout, read by the real parser
SRC_HK = "synthetic.sina_hk"           # the Sina HK CSV layout
SRC_US = "synthetic.alphavantage_us"   # the Alpha Vantage CSV layout
SRC_ECB = "synthetic.ecb_direct"       # the ECB eurofxref-hist CSV layout
SRC_FRANK = "synthetic.frankfurter_fx"  # the Frankfurter JSON layout
SRC_TSV = "synthetic.tsv_us"           # an invented layout with a test-local adapter (the fourth adapter)
SRC_CAL = "calendar.manual"
ALL_SOURCES = (SRC_MOCK, SRC_CN, SRC_HK, SRC_US, SRC_ECB, SRC_FRANK, SRC_TSV, SRC_CAL)

# FACTS. (ticker, mic) -> {date: (close text, volume in shares)}
FACTS_QUOTES = {
    ("AAPL", "XNAS"): {D(2025, 1, 2): ("150.25", 1000), D(2025, 1, 3): ("151.10", 1200)},
    ("0700", "XHKG"): {D(2025, 1, 2): ("330.4", 5000), D(2025, 1, 3): ("332.6", 5200)},
    ("600519", "XSHG"): {D(2025, 1, 2): ("1500.00", 800), D(2025, 1, 3): ("1502.00", 820)},
}
# FACTS. ECB-style quotes, units of currency per 1 EUR, by fixing date.
FACTS_FX = {
    D(2025, 1, 2): {"USD": "1.0800", "HKD": "8.4000", "CNY": "7.8000"},
    D(2025, 1, 3): {"USD": "1.0810", "HKD": "8.4100", "CNY": "7.8100"},
}
CURRENCY_OF = {("AAPL", "XNAS"): USD, ("0700", "XHKG"): HKD, ("600519", "XSHG"): CNY}
VENDOR_ID = {SRC_US: {"AAPL": "AAPL"}, SRC_HK: {"0700": "00700"}, SRC_CN: {"600519": "600519"}, SRC_TSV: {"AAPL": "AAPL"}}


def identity() -> InMemoryIdentityRegistry:
    """Three listings with the vendor ids of the synthetic formats that carry no MIC (the symbol column of the
    Eastmoney layout, the manifest symbol of the Sina and Alpha Vantage layouts)."""
    reg = InMemoryIdentityRegistry(kit.SequentialIds())
    reg.register_instruments([
        InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", USD,
                        vendor_ids=((SRC_US, "AAPL"), (SRC_TSV, "AAPL"))),
        InstrumentEntry("Tencent Holdings", SecurityType.COMMON_STOCK, "XHKG", "HKEX", "0700", HKD,
                        vendor_ids=((SRC_HK, "00700"),)),
        InstrumentEntry("Kweichow Moutai", SecurityType.COMMON_STOCK, "XSHG", "SSE", "600519", CNY,
                        vendor_ids=((SRC_CN, "600519"),)),
    ])
    return reg


def synthetic_registry_records() -> List[SourceRecord]:
    """Every synthetic source except the mock, which `kit.write_registry` always registers."""
    return [SourceRecord(s, s, "synthetic", f"synthetic.{s}", synthetic=True) for s in ALL_SOURCES if s != SRC_MOCK]


# --- payloads in the real formats ------------------------------------------------------------------------------

def eastmoney_csv(rows: List[Tuple[D, str, int]], symbol: str = "600519") -> bytes:
    """The Eastmoney layout, oldest first. open = close, high = close + 1, low = close - 1; volume in LOTS of 100
    shares (`shares // 100`), 成交额 = close x shares exactly; 涨跌额 = close_t - close_(t-1) (0.0 on the first row)."""
    head = "日期,股票代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率"
    lines = [head]
    prev: Optional[Decimal] = None
    for day, close, shares in rows:
        v = Decimal(close)
        change = Decimal(0) if prev is None else v - prev
        prev = v
        lots = shares // 100
        amount = v * shares
        lines.append(",".join([day.isoformat(), symbol, f"{v:.1f}", f"{v:.1f}", f"{v + 1:.1f}", f"{v - 1:.1f}", str(lots),
                               f"{amount:.1f}", "0.0", "0.0", f"{change:.1f}", "0.0"]))
    return ("\n".join(lines) + "\n").encode("utf-8")


def sina_hk_csv(rows: List[Tuple[D, str, int]]) -> bytes:
    """The Sina HK layout, oldest first: date,open,high,low,close,volume,amount (volume in shares, amount = close x
    shares). Prices are float32 renderings (330.4 is its own shortest binary32 form)."""
    lines = ["date,open,high,low,close,volume,amount"]
    for day, close, shares in rows:
        v = Decimal(close)
        lines.append(",".join([day.isoformat(), str(v), str(v + 1), str(v - 1), str(v), str(shares), f"{v * shares:.1f}"]))
    return ("\n".join(lines) + "\n").encode("utf-8")


def av_us_csv(rows: List[Tuple[D, str, int]]) -> bytes:
    """The Alpha Vantage layout (newest first, four decimals)."""
    out = []
    for day, close, shares in rows:
        v = Decimal(close)
        out.append((day.isoformat(), f"{v:.4f}", f"{v + 1:.4f}", f"{v - 1:.4f}", f"{v:.4f}", str(shares)))
    return k.av_csv(out)


def ecb_direct_csv() -> bytes:
    rows = [(d.isoformat(), [FACTS_FX[d]["USD"], FACTS_FX[d]["HKD"], FACTS_FX[d]["CNY"]]) for d in sorted(FACTS_FX)]
    return k.ecb_csv(rows, ["USD", "HKD", "CNY"])


def frankfurter_json() -> bytes:
    body = ",".join(f'"{d.isoformat()}":{{' + ",".join(f'"{ccy}":{FACTS_FX[d][ccy]}' for ccy in ("CNY", "HKD", "USD")) + "}"
                    for d in sorted(FACTS_FX))
    return ('{"amount":1.0,"base":"EUR","rates":{' + body + "}}").encode("utf-8")


def calendar_files() -> List[dict]:
    """Four hand-made calendars (synthetic, invented dates): the three exchanges and the ECB fixings."""
    specs = (("NYSE_SESSIONS", "EXCHANGE_SESSIONS", ("XNYS", "XNAS"), "America/New_York"),
             ("SSE_SESSIONS", "EXCHANGE_SESSIONS", ("XSHG", "XSHE"), "Asia/Shanghai"),
             ("HKEX_SESSIONS", "EXCHANGE_SESSIONS", ("XHKG",), "Asia/Hong_Kong"),
             ("ECB_FIXINGS", "ECB_FIXINGS", ("ECB",), "Europe/Berlin"))
    out = []
    for cid, kind, applies, tz in specs:
        payload = k.calendar_json(cid, kind, applies, tz, coverage=("2025-01-01", "2025-01-31"), dates=SESSIONS)
        out.append(dict(source_id=SRC_CAL, kind=DataKind.CALENDAR, payload_format="finweb_calendar_json/1",
                        payload=payload, label=cid, ext="json", source_identifiers=(cid,)))
    return out


# --- the novel fourth adapter (a layout no production code knows) ------------------------------------------------

class TsvQuoteAdapter:
    """TEST-LOCAL: `symbol<TAB>date<TAB>close<TAB>volume`, one symbol per line, identifiers = the source's vendor id."""

    adapter_id = "synthetic.tsv_us.quotes"
    adapter_version = "0.0.1"
    source_id = SRC_TSV
    data_kind = DataKind.QUOTE
    payload_formats = ("synthetic_tsv/1",)

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        rows = []
        for i, line in enumerate(payload.decode("utf-8").splitlines()):
            symbol, day, close, volume = line.split("\t")
            rows.append(c.UnresolvedQuote(
                c.ExternalIdentifiers(vendor_id=symbol, source_id=manifest.source_id), D.fromisoformat(day), Decimal(close),
                manifest.declared_currency, kit.timing_for(manifest),
                kit.lineage_for(manifest, self, f"line{i}", source_value_text=close), volume=Decimal(volume)))
        return AdapterOutput(quotes=tuple(rows))


# --- the worlds ------------------------------------------------------------------------------------------------

FLAVOURS = ("mock", "formats", "formats_frankfurter", "novel")
#: A version with NO file for the mainland and Hong Kong listings: what Ruling 4.7 describes (no admitted source).
NO_CN_HK = "us_only"


def _rows(ticker: str, mic: str) -> List[Tuple[D, str, int]]:
    return [(d, close, vol) for d, (close, vol) in sorted(FACTS_QUOTES[(ticker, mic)].items())]


def world_specs(flavour: str) -> Tuple[List[dict], AdapterRegistry]:
    """The file specs (for `kit.write_file`) and the adapters of one flavour. Calendars are the same in every world."""
    specs: List[dict] = []
    adapters = AdapterRegistry([CalendarFileAdapter()])
    specs += calendar_files()
    if flavour == "mock":
        for kind in (DataKind.QUOTE, DataKind.FX):
            adapters.register(MockSyntheticAdapter(kind))
        for (ticker, mic), ccy in CURRENCY_OF.items():
            payload = make_synthetic_payload(quotes=tuple(
                {"ticker": ticker, "mic": mic, "date": d.isoformat(), "close": Decimal(close), "volume": Decimal(vol)}
                for d, close, vol in _rows(ticker, mic)))
            specs.append(dict(source_id=SRC_MOCK, kind=DataKind.QUOTE, payload_format=MOCK_FORMAT, payload=payload,
                              label=f"quotes_{ticker}", ext="json", currency=ccy, source_identifiers=(ticker,)))
        fx_rows = tuple({"base": "EUR", "quote": ccy, "date": d.isoformat(), "rate": Decimal(rate), "rate_basis": "synthetic ECB"}
                        for d in sorted(FACTS_FX) for ccy, rate in FACTS_FX[d].items())
        specs.append(dict(source_id=SRC_MOCK, kind=DataKind.FX, payload_format=MOCK_FORMAT,
                          payload=make_synthetic_payload(fx=fx_rows), label="fx", ext="json",
                          source_identifiers=("USD", "HKD", "CNY")))
        return specs, adapters

    if flavour != NO_CN_HK:
        adapters.register(AkshareCnQuoteAdapter(SRC_CN))
        adapters.register(AkshareSinaQuoteAdapter("hk", SRC_HK))
        specs.append(dict(source_id=SRC_CN, kind=DataKind.QUOTE, payload_format="akshare_csv_cn_daily/1",
                          payload=eastmoney_csv(_rows("600519", "XSHG")), label="600519", ext="csv", currency=CNY,
                          adjustment=c.AdjustmentStatus.RAW, source_identifiers=("600519",),
                          request=(("function", "stock_zh_a_hist"),), market="CN"))
        specs.append(dict(source_id=SRC_HK, kind=DataKind.QUOTE, payload_format="akshare_sina_csv_hk_daily/1",
                          payload=sina_hk_csv(_rows("0700", "XHKG")), label="00700", ext="csv", currency=HKD,
                          adjustment=c.AdjustmentStatus.RAW, source_identifiers=("00700",),
                          request=(("function", "stock_hk_daily"),), market="HK"))
    if flavour == "novel":
        adapters.register(TsvQuoteAdapter())
        text = "".join(f"AAPL\t{d.isoformat()}\t{close}\t{vol}\n" for d, close, vol in _rows("AAPL", "XNAS"))
        specs.append(dict(source_id=SRC_TSV, kind=DataKind.QUOTE, payload_format="synthetic_tsv/1",
                          payload=text.encode("utf-8"), label="AAPL", ext="tsv", currency=USD,
                          source_identifiers=("AAPL",)))
    else:
        adapters.register(AlphaVantageQuoteAdapter(SRC_US))
        specs.append(dict(source_id=SRC_US, kind=DataKind.QUOTE, payload_format="alphavantage_csv_daily/1",
                          payload=av_us_csv(_rows("AAPL", "XNAS")), label="AAPL", ext="csv", currency=USD,
                          adjustment=c.AdjustmentStatus.UNDECLARED, source_identifiers=("AAPL",),
                          request=(("function", "TIME_SERIES_DAILY"), ("outputsize", "compact")), market="US"))
    if flavour == "formats_frankfurter":
        adapters.register(FrankfurterFxAdapter(SRC_FRANK))
        specs.append(dict(source_id=SRC_FRANK, kind=DataKind.FX, payload_format="frankfurter_json_timeseries/1",
                          payload=frankfurter_json(), label="fx", ext="json", source_identifiers=("CNY", "HKD", "USD"),
                          request=(("start", "2025-01-02"), ("end", "2025-01-03"))))
    else:
        adapters.register(EcbEurofxrefFxAdapter(SRC_ECB))
        specs.append(dict(source_id=SRC_ECB, kind=DataKind.FX, payload_format="ecb_eurofxref_hist_csv/1",
                          payload=ecb_direct_csv(), label="fx", ext="csv", source_identifiers=("USD", "HKD", "CNY")))
    return specs, adapters


class World:
    """A built market-data version: its files on disk (kept alive by `tmp`), the release, the in-memory build, the
    identity registry and the adapters."""

    def __init__(self, flavour: str, root: Path, tmp, release: MarketDataRelease, built: BuildResult,
                 ident: InMemoryIdentityRegistry, adapters: AdapterRegistry, manifests: List[FileManifest]):
        self.flavour, self.root, self._tmp = flavour, root, tmp
        self.release, self.built, self.ident, self.adapters, self.manifests = release, built, ident, adapters, manifests

    @property
    def store(self):
        return self.built.store

    def close(self) -> None:
        """Remove the temporary directory this world's files live in (a no-op for a world built on a given root)."""
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None


def write_registry(root: Path) -> None:
    kit.write_registry(root, extra=synthetic_registry_records())


def build_world(flavour: str, root: Optional[Path] = None, ident: Optional[InMemoryIdentityRegistry] = None) -> World:
    """Write the flavour's files in their real layout, cut a release over them (failing closed on two vintages) and
    build the in-memory store through the real path: hash verification, adapter, resolver, calendars, checks."""
    tmp = None
    if root is None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
    write_registry(root)
    specs, adapters = world_specs(flavour)
    manifests = [kit.write_file(root, **spec) for spec in specs]
    release = MarketDataRelease.from_manifests(f"exit-{flavour}", manifests, [])
    files = FileStore(root)
    ident = ident or identity()
    built = build_in_memory_market_data(release, files, files.load_registry(), adapters, ident, catalog_calendars={})
    assert built.issues == () and built.exceptions == (), (built.issues, built.exceptions)
    return World(flavour, root, tmp, release, built, ident, adapters, manifests)


def replayed_state(ident: InMemoryIdentityRegistry, as_of: D):
    """A CP1 replay of one account holding AAPL x10, 0700 x100 and 600519 x2 with cash in each currency."""
    return kit.replayed_state(ident, as_of)


def lid(ident: InMemoryIdentityRegistry, ticker: str, mic: str) -> uuid.UUID:
    return kit.listing_id(ident, ticker, mic)


# --- expected values, derived by hand --------------------------------------------------------------------------

def expected_value_obj(ident: InMemoryIdentityRegistry) -> dict:
    """`ValuationInputs.value_obj()` for AS_OF = 2025-01-03, written from the facts above and nothing else.

    Prices (the close dated 2025-01-03 of each listing, every one CURRENT because the print is dated the as-of
    date, so no session is missed): AAPL 151.10 -> canonical 151.1, 0700 332.6, 600519 1502.00 -> 1502.
    One upstream per series, so every reconciliation is SINGLE_SOURCE.

    FX to USD (the reporting currency), crosses through EUR of the two SAME-DATE legs (Ruling 1.3), exact:
      HKD -> USD = x_USD / x_HKD = 1.0810 / 8.4100 = 10810/84100 = 1081/8410   (gcd(1081 = 23 x 47, 8410 = 2 x 5 x 29^2) = 1)
      CNY -> USD = x_USD / x_CNY = 1.0810 / 7.8100 = 10810/78100 = 1081/7810   (gcd(1081, 7810 = 2 x 5 x 11 x 71) = 1)
    Two legs, both dated 2025-01-03 = the as-of date: freshness [CURRENT, CURRENT].
    Positions are the replayed quantities 10, 100 and 2."""
    def quote(ticker, mic, ccy, price):
        return {"listing_id": str(lid(ident, ticker, mic)), "native_currency": ccy, "outcome": "FOUND",
                "value_date": "2025-01-03", "price": price, "currency": ccy, "reconciliation": "SINGLE_SOURCE",
                "freshness": "CURRENT"}

    def position(ticker, mic, qty):
        return {"account_id": str(uuid.UUID(int=1)), "listing_id": str(lid(ident, ticker, mic)), "quantity": qty,
                "state": "AVAILABLE"}

    quotes = [quote("AAPL", "XNAS", "USD", "151.1"), quote("0700", "XHKG", "HKD", "332.6"),
              quote("600519", "XSHG", "CNY", "1502")]
    positions = [position("AAPL", "XNAS", "10"), position("0700", "XHKG", "100"), position("600519", "XSHG", "2")]
    return {
        "as_of": "2025-01-03", "reporting_currency": "USD",
        "positions": sorted(positions, key=lambda p: p["listing_id"]),
        "quotes": sorted(quotes, key=lambda q: q["listing_id"]),
        "fx": [
            {"currency": "CNY", "outcome": "FOUND", "rate": "1081/7810", "reconciliation": "SINGLE_SOURCE",
             "freshness": ["CURRENT", "CURRENT"]},
            {"currency": "HKD", "outcome": "FOUND", "rate": "1081/8410", "reconciliation": "SINGLE_SOURCE",
             "freshness": ["CURRENT", "CURRENT"]},
        ],
    }


def normalize(obj) -> object:
    from marketdata.canonical import canonical_json
    return json.loads(canonical_json(obj))
