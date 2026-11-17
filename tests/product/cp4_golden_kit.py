"""Loader and checker for the CP4 golden fixture, parts 1 to 3 (`methodology/fixtures/cp4_golden/cp4_golden_part{1,2,3}.json`; `risk/1.2`; tech plan 17.9, 17.16).

This module NEVER edits a fixture and never derives an expected value. It EXPANDS a part's compact synthetic market-data block into real file layouts (calendar files with explicit date lists, an ECB `eurofxref-hist`
CSV with `N/A` cells for the declared gaps, one RAW price file per listing, a synthetic risk-free file per series, a benchmark file per benchmark, corporate-action FEED and FILING files), registers them under
SYNTHETIC source ids and ingests them through the real adapters, resolver, calendars and checks into one release M per part. The expansion is mechanical: every price, rate and level is the decimal string the
fixture gives. It then runs the engine for each assertion and compares every item it can.

THE LOADER IS TOLERANT OF WHAT IT DOES NOT BUILD. A block or an item kind it does not know is RECORDED, not an error and not a silent skip: every item is either CHECKED or DEFERRED with a reason from the closed list
`DEFERRED_REASONS`, and the tests pin how many of each (so a part that grows, or a deferral that stops applying, fails loudly). Deferred today: the benchmark-RELATIVE metrics (the next increment, after the independent review
of this midpoint), the default view (Ruling 7.7: the Quant is confirming its trigger with the owner), Current mode (Ruling 5.8), and a benchmark served by two sources or built as an ETF proxy (Ruling 5.5, 5.7).

`check_*` return `Mismatch` records (assertion id, item, field, expected, actual). A mismatch is a FINDING for the Quant or the engineer: neither side is adjusted here.
"""

import dataclasses
import datetime
import hashlib
import json
import sys
import tempfile
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402

k = x.k
c = x.c

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.benchmark_selection import BenchmarkSelection, Origin, RecordType, SelectionVersionNotPinnableError, SequencedSelection, resolve_selection  # noqa: E402
from domain.catalogs import BenchmarkCatalog, RiskFreeCatalog, parse_benchmark_catalog  # noqa: E402
from domain.currency import CurrencyCode  # noqa: E402
from domain.instrument import SecurityType  # noqa: E402
from domain.replay import SequencedEvent  # noqa: E402
from marketdata.adapters.akshare_cn import AkshareCnQuoteAdapter  # noqa: E402
from marketdata.adapters.akshare_sina import AkshareSinaQuoteAdapter  # noqa: E402
from marketdata.adapters.alphavantage import AlphaVantageQuoteAdapter  # noqa: E402
from marketdata.adapters.base import AdapterRegistry  # noqa: E402
from marketdata.adapters.calendar_file import CalendarFileAdapter  # noqa: E402
from marketdata.adapters.ecb_eurofxref import EcbEurofxrefFxAdapter  # noqa: E402
from marketdata.adapters.mock import MOCK_FORMAT, MockSyntheticAdapter, make_synthetic_payload  # noqa: E402
from marketdata.adapters.synthetic_risk_free import PAYLOAD_FORMAT as RF_FORMAT, SOURCE_ID as RF_SOURCE, SyntheticRiskFreeAdapter, make_risk_free_payload  # noqa: E402
from marketdata.canonical import sha256_hex  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, FileManifest, MarketDataRelease, SourceRecord  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402
from performance.current import choose_current_date  # noqa: E402
from performance.engine import compute_return_series, performance_conventions  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402
from performance.series import Frequency, MaxAvailable, WeekdayFridayMonthEndGrid  # noqa: E402
from performance_service import service as svc  # noqa: E402
from risk import states as S  # noqa: E402
from performance_service.derived_release import DerivedReleaseView  # noqa: E402
from risk_service.default_view import default_view  # noqa: E402
from risk.engine import compute_risk, compute_risk_current  # noqa: E402
from risk.risk_free import risk_free_rates  # noqa: E402
from risk.single import rate_parts, series_parts, window_part  # noqa: E402

D = datetime.date.fromisoformat
FIXTURE_DIR = _ROOT / "methodology" / "fixtures" / "cp4_golden"
PART_FILES = {1: "cp4_golden_part1.json", 2: "cp4_golden_part2.json", 3: "cp4_golden_part3.json", 4: "cp4_golden_part4.json"}  # part 4 (a new file: risk-free at an instant in Current mode, the default-view fallback of a relative metric) loads when it exists
CA_FEED, CA_FILING = "synthetic.ca_feed", "synthetic.ca_filing"
#: parts 1 and 2 declare no retrieval time; their data run to 2026-03-31, and the V0 check (market-data Ruling 2.2) reads a row dated after the latest session closed at retrieval as a contradiction, so a
#: file is retrieved after the last session. (Part 3 at 1.1 declares its file vintages: see `VintagePlan`.)
DEFAULT_RETRIEVED = datetime.datetime(2026, 4, 1, 9, 0, tzinfo=datetime.timezone.utc)
CALENDAR_REGISTERED = datetime.datetime(2022, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)  # a calendar counts by its registration time (performance Ruling 1.7: `M_t`), long before any instant a fixture names
POLICY = f8b.ConfirmationPolicy(frozenset({CA_FEED}), frozenset({CA_FILING}))

KIND_METRIC = {"volatility": "risk_volatility", "downside_deviation": "risk_downside_deviation", "max_drawdown": "risk_max_drawdown", "sharpe": "risk_sharpe", "sortino": "risk_sortino",
               "benchmark_return": "benchmark_return", "beta": "risk_beta", "r_squared": "risk_r_squared", "alpha_jensen": "risk_alpha_jensen", "tracking_error": "risk_tracking_error",
               "information_ratio": "risk_information_ratio", "active_return": "risk_active_return"}
SQRT_KINDS = {"volatility", "downside_deviation", "sharpe", "sortino", "tracking_error", "information_ratio"}
RELATIVE_KINDS = {"beta", "r_squared", "alpha_jensen", "tracking_error", "information_ratio", "active_return"}
RELATIVE_METRIC_IDS = {KIND_METRIC[k] for k in RELATIVE_KINDS}
SERIES_KINDS = {"return_series", "risk_free_rates"}
DEFERRED_REASONS = ("KIND_UNKNOWN_TO_THIS_LOADER",)  # the only reason left: an item kind this loader does not know. Every kind of parts 1 to 3 is checked, so no item is deferred (CP4d)


def _no_float(text):
    raise AssertionError(f"a fixture must hold no float literal, found {text!r}")


def load_part(number: int) -> dict:
    return json.loads((FIXTURE_DIR / PART_FILES[number]).read_text(encoding="utf-8"), parse_float=_no_float)


def content_hash(data: dict) -> str:
    """The pin of a part's asserted content (for `FIXTURE_PINS`): its assertions' ids, as-of dates, versions and expected items."""
    content = [[a["id"], a.get("as_of"), a.get("ledger_version"), a.get("selection_log_version"), a["expect"]] for p in data["portfolios"] for a in p["assertions"]]
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


# --- compact definitions, expanded mechanically ----------------------------------------------------------------------------------------------------

def _weekdays(first: datetime.date, last: datetime.date) -> List[datetime.date]:
    out, day = [], first
    while day <= last:
        if day.weekday() < 5:
            out.append(day)
        day += datetime.timedelta(days=1)
    return out


def calendar_dates(spec: dict) -> List[datetime.date]:
    closed = {D(s) for s in spec["closed_weekdays"]}
    return [d for d in _weekdays(D(spec["coverage"]["from"]), D(spec["coverage"]["to"])) if d not in closed]


def expand_steps(steps: Sequence[dict], cycle: Any, cycle_key: str, step_key: str) -> List[Tuple[datetime.date, str]]:
    """The steps of a series: `steps` plus the expansion of `cycle` (a dict, or a LIST of dicts, each `{from, every_days, until, <cycle_key>: [values]}`): a step at `from + every_days * j` with value
    `values[j mod len(values)]` while the date is `<= until`. Sorted by date; the value in force on a day is the latest step on or before it."""
    out: List[Tuple[datetime.date, str]] = [(D(s["from"]), s[step_key]) for s in steps]
    for cy in ([] if cycle is None else cycle if isinstance(cycle, list) else [cycle]):
        values, day, j = cy[cycle_key], D(cy["from"]), 0
        while day <= D(cy["until"]):
            out.append((day, values[j % len(values)]))
            j += 1
            day = D(cy["from"]) + datetime.timedelta(days=cy["every_days"] * j)
    return sorted(out, key=lambda p: p[0])


def value_on(steps: Sequence[Tuple[datetime.date, str]], day: datetime.date) -> Optional[str]:
    current = None
    for when, value in steps:
        if when <= day:
            current = value
    return current


def _distinct_payload(payload: bytes, seen: set) -> bytes:
    """Two listings with the SAME closes on the SAME dates (SYN31 and SYN32 of part 3) give byte-identical Alpha Vantage files (the layout carries no ticker), and a file is identified by its hash, so the second would
    be refused as a duplicate. The columns are read by NAME, so a repeat is written with its columns rotated: the same facts, different bytes. Every value is unchanged."""
    text = payload.decode("utf-8")
    for turn in range(0, 8):
        candidate = payload
        if turn and text.lstrip().startswith("{"):  # a JSON payload (a benchmark file, two sources publishing the same levels): trailing whitespace is the same facts with different bytes
            candidate = payload + b"\n" * turn
        elif turn:
            rows = [line.split(",") for line in text.splitlines()]
            if len({len(r) for r in rows}) != 1 or len(rows[0]) < 2:
                break
            shift = turn % len(rows[0])
            candidate = ("\n".join(",".join(r[shift:] + r[:shift]) for r in rows) + "\n").encode("utf-8")
        digest = sha256_hex(candidate)
        if digest not in seen:
            seen.add(digest)
            return candidate
    raise AssertionError("could not make a distinct payload")


def eastmoney_exact_csv(rows: List[Tuple[datetime.date, str, int]], symbol: str) -> bytes:
    """The Eastmoney layout with the fixture's closes written EXACTLY (the shared helper rounds to one decimal, which would change a two-decimal close): open = close, high = close + 1, low = close - 1, volume
    in lots of 100 shares, amount = close x shares, change = close_t - close_(t-1) (0 on the first row)."""
    lines = ["日期,股票代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率"]
    prev: Optional[Decimal] = None
    for day, close, shares in rows:
        v = Decimal(close)
        change = Decimal(0) if prev is None else v - prev
        prev = v
        lines.append(",".join([day.isoformat(), symbol, str(v), str(v), str(v + 1), str(v - 1), str(shares // 100), str(v * shares), "0.0", "0.0", str(change), "0.0"]))
    return ("\n".join(lines) + "\n").encode("utf-8")


def calendar_payload(cal: dict, dates: Sequence[datetime.date]) -> bytes:
    doc = {"schema": "finweb.marketdata.calendar/1", "calendar_id": cal["calendar_id"], "kind": cal["kind"], "applies_to": list(cal["applies_to"]), "timezone": cal["timezone"],
           "coverage": {"from": cal["coverage"]["from"], "to": cal["coverage"]["to"]}, "dates": [d.isoformat() for d in dates], "actual_through": cal["actual_through"],
           "evidence": "synthetic: not a real holiday list", "prepared_by": "test", "prepared_on": "2026-10-02", "version": "v1"}
    if cal["kind"] == "EXCHANGE_SESSIONS":
        doc["close"] = {"default": cal["close"]["default"], "overrides": cal["close"]["overrides"]}
    elif cal["kind"] == "ECB_FIXINGS":
        doc["fixing"] = cal["fixing"]
    else:
        doc["publication"] = cal["publication"]
    return json.dumps(doc).encode("utf-8")


def _write_file(root: Path, retrieved: datetime.datetime, source_id: str, kind: DataKind, fmt: str, payload: bytes, label: str, ext: str, *, currency=None, adjustment=c.AdjustmentStatus.RAW,
                identifiers=(), request=(), market=None, anchor=None, usage_scope=c.UsageScope.SYNTHETIC_TEST) -> FileManifest:
    directory = root / "files" / source_id / kind.value.lower() / "cp4"
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{label}.{ext}"
    manifest = FileManifest(
        file_sha256=sha256_hex(payload), size_bytes=len(payload), payload_filename=name, payload_format=fmt, source_id=source_id, data_kind=kind, retrieval_time=retrieved, retrieved_by="synthetic",
        declared_adjustment=adjustment, usage_scope=usage_scope, declared_currency=currency, declared_delay=c.DataDelayStatus.END_OF_DAY, source_identifiers=tuple(identifiers),
        request=tuple(request), market=market, adjustment_anchor=anchor)
    (directory / name).write_bytes(payload)
    (directory / (name + ".manifest.json")).write_text(manifest.to_json(), encoding="utf-8")
    return manifest


MARKET_OF_MIC = {"XNYS": "US", "XHKG": "HK", "XSHG": "CN"}


def _utc(text: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


class VintagePlan:
    """The file vintages a part declares (`market_data.retrieval`, part 3 at 1.1; market-data Ruling 3.1): a series is delivered in up to three files by ROW DATE, each retrieved at or after the availability instant
    of every row it holds. V1 holds the rows to `rows_through`, V2 the rows of one day, each retrieved at its own calendar's close or publication instant (`retrieval_time_by_calendar`), V3 the rest. A vintage with no
    row for a series is not delivered for it. A part that declares none (parts 1 and 2) has ONE file per series, retrieved after the last session of its data."""

    def __init__(self, md: dict):
        spec = md.get("retrieval")
        self.declared = spec is not None
        self.cuts: List[Tuple[str, datetime.date, datetime.date]] = []
        self.times: Dict[str, Any] = {}
        self.files: Dict[str, List[Tuple[str, datetime.date, datetime.date, datetime.datetime]]] = {}
        if spec is not None and spec.get("files") and isinstance(spec["files"][0], dict):  # part 4: EVERY file listed with the series it belongs to, its declared coverage and its retrieval time; a file holds exactly the series' rows inside its coverage
            for f in spec["files"]:
                self.files.setdefault(f["series"], []).append((f["file"], D(f["coverage"][0]), D(f["coverage"][1]), _utc(f["retrieval_time"])))
            self.actions_time = _utc(spec["corporate_actions_retrieval_time"]) if "corporate_actions_retrieval_time" in spec else DEFAULT_RETRIEVED
        elif spec is not None:
            for v in spec["vintages"]:
                low = D(v["rows_from"]) if "rows_from" in v else datetime.date.min
                high = D(v["rows_through"]) if "rows_through" in v else datetime.date.max
                self.cuts.append((v["vintage"], low, high))
                self.times[v["vintage"]] = _utc(v["retrieval_time"]) if "retrieval_time" in v else {cal: _utc(t) for cal, t in v["retrieval_time_by_calendar"].items()}
            self.actions_time = _utc(spec["corporate_actions_retrieval_time"])
        else:
            self.actions_time = DEFAULT_RETRIEVED

    def split(self, rows: Sequence[Any], date_of, calendar_id: str, series: Optional[str] = None) -> List[Tuple[Optional[str], List[Any], datetime.datetime, Optional[Tuple[datetime.date, datetime.date]]]]:
        """`[(vintage name or None, the rows of that vintage, its retrieval time, its declared coverage)]`, only the vintages that hold a row. The coverage is what the part states (1.3-part3 `segments`): V1 from the
        series' first date to `rows_through`, V2 its own day, V3 from `rows_from` to the series' last date. It is written into the file's request (`start`, `end`), where market-data Ruling 0.1 (1.12) reads it; the
        vintage name is NEVER written into the series key (`adjustment_anchor` stays null)."""
        if not self.declared:
            return [(None, list(rows), DEFAULT_RETRIEVED, None)]
        if self.files:  # one file per declared entry of the series, holding exactly the rows inside its coverage (a file with no row is not delivered)
            listed = self.files.get(series or "")
            assert listed is not None, f"part declares its files one by one and lists none for the series {series!r}"
            return [(name, part, when, (low, high)) for name, low, high, when in listed for part in [[r for r in rows if low <= date_of(r) <= high]] if part]
        out = []
        for label, low, high in self.cuts:
            part = [r for r in rows if low <= date_of(r) <= high]
            if part:
                when = self.times[label]
                start = date_of(part[0]) if low == datetime.date.min else low
                end = date_of(part[-1]) if high == datetime.date.max else high
                out.append((label, part, when[calendar_id] if isinstance(when, dict) else when, (start, end)))
        return out


def multi_source_or_proxy_ids(data: dict) -> frozenset:
    """Benchmark ids this loader does NOT load: an id with several entries (the sources of Ruling 5.7) or built as an ETF proxy (Ruling 5.5). Their items are deferred."""
    entries = data["market_data"].get("benchmarks", [])
    counts: Dict[str, int] = {}
    for e in entries:
        counts[e["benchmark_id"]] = counts.get(e["benchmark_id"], 0) + 1
    return frozenset(i for i, n in counts.items() if n > 1) | frozenset(e["benchmark_id"] for e in entries if e.get("construction") == "ETF_PROXY")


def benchmark_catalog_of(data: dict, ids=lambda text: uuid.UUID(text)) -> BenchmarkCatalog:
    """The TEST catalog of a part (a synthetic series is never in the committed catalog, market-data Ruling 4.8): one entry per benchmark id, with the fixture's own return basis and calendar. A benchmark served by
    several sources has one entry naming its PRIMARY source (priority 1); an ETF proxy names its listing (`proxy_listing_id`, mapped through `ids`)."""
    rows = []
    seen = set()
    for b in sorted(data["market_data"].get("benchmarks", []), key=lambda e: (e["benchmark_id"], e.get("source_priority", 1))):
        if b["benchmark_id"] in seen:
            continue
        seen.add(b["benchmark_id"])
        proxy = b.get("construction") == "ETF_PROXY"
        row = {"benchmark_id": b["benchmark_id"], "name": b["name"], "provider": b["provider"], "source_id": b["source_id"] if "source_priority" in b else "mock.synthetic", "licensing": b["licensing"],
               "currency": b["currency"], "return_basis": b["return_basis"], "dividend_treatment": "synthetic", "calendar_id": b["calendar"], "series_form": "LEVELS", "proxy_of": None, "synthetic": True}
        if proxy:
            row["proxy_listing_id"] = str(ids(b["listing_id"]))
        others = [o for o in data["market_data"]["benchmarks"] if o["benchmark_id"] == b["benchmark_id"] and o is not b and "source_priority" in o]
        if "official_decimals" in b:  # risk/1.9 Ruling 5.7 (1.9): the index's published precision and each source's own, DECLARED (never inferred from the levels)
            row["official_decimals"] = b["official_decimals"]
        if "precision_decimals" in b:
            row["precision_decimals"] = b["precision_decimals"]
        if others:  # CP4F-4: every other source of the id is DECLARED in the entry with the basis it publishes
            row["additional_sources"] = [dict({"source_id": o["source_id"], "return_basis": o["return_basis"]}, **({"precision_decimals": o["precision_decimals"]} if "precision_decimals" in o else {})) for o in others]
        rows.append(row)
    return parse_benchmark_catalog(json.dumps({"catalog_id": f"test-{data['fixture_id'].split('/')[-1]}", "entries": rows}).encode("utf-8"), allow_synthetic=True)


EMPTY_RISK_FREE_CATALOG = RiskFreeCatalog("test-risk-free", ())


class Market:
    """The expanded market-data version M, the identity registry and the conventions of one part. `ids` maps the fixture's fixed ids to the ids used."""

    def __init__(self, data: dict, ids, root: Optional[Path] = None):
        self.data, self.ids = data, ids
        self._tmp = None
        if root is None:
            self._tmp = tempfile.TemporaryDirectory()
            root = Path(self._tmp.name)
        self.root = root
        md = data["market_data"]
        self.plan = plan = VintagePlan(md)
        has_actions = bool(md.get("corporate_actions"))
        extra = x.synthetic_registry_records() + [SourceRecord(RF_SOURCE, RF_SOURCE, "synthetic", "synthetic.riskfree", synthetic=True)]
        for b in md.get("benchmarks", []):  # the sources of a benchmark served by several: independent upstreams, and the registry's `source_priority` (Ruling 5.7 (1.2); the test registry, not the committed one)
            if "source_priority" in b:
                known = {r.source_id: r for r in extra}
                if b["source_id"] in known:  # a source serving several benchmarks (part 3 (1.9)) is ONE registry record, and its priority is the same for all of them
                    assert known[b["source_id"]].source_priority == b["source_priority"], b["source_id"]
                    continue
                extra.append(SourceRecord(b["source_id"], b["source_id"], b["upstream"], b["upstream"], synthetic=True, source_priority=b["source_priority"]))
        for s in md["prices"]["series"]:  # a SECOND PRICE SOURCE of a listing (part 3 (1.6), the disputed prints of an ETF proxy): its own upstream, registered once
            second = s.get("second_source")
            if second is not None and second["source_id"] not in {r.source_id for r in extra}:
                extra.append(SourceRecord(second["source_id"], second["source_id"], second["upstream"], second["upstream"], synthetic=True, source_priority=second["source_priority"]))
        if has_actions:
            extra += [SourceRecord(s, s, "synthetic", f"synthetic.{s}", synthetic=True) for s in (CA_FEED, CA_FILING)]
        x.kit.write_registry(root, extra=extra)
        queue: List[uuid.UUID] = []
        entries: List[InstrumentEntry] = []
        self.listings = {lst["listing_id"]: lst for lst in data["listings"]}
        for lst in data["listings"]:
            ticker, mic = lst["ticker"], lst["mic"]
            market = MARKET_OF_MIC[mic]
            vendor = {"US": (x.SRC_US, ticker), "HK": (x.SRC_HK, "00700" if ticker == "0700" else ticker), "CN": (x.SRC_CN, ticker)}[market]
            entries.append(InstrumentEntry(f"Synthetic issuer {ticker}", SecurityType(lst.get("security_type", "COMMON_STOCK")), mic, mic, ticker, CurrencyCode(lst["trading_currency"]), vendor_ids=(vendor,) + tuple((s["second_source"]["source_id"], ticker) for s in md["prices"]["series"] if s["listing_id"] == lst["listing_id"] and s.get("second_source"))))
            queue += [uuid.uuid5(uuid.NAMESPACE_URL, f"cp4-golden:issuer:{ticker}"), uuid.uuid5(uuid.NAMESPACE_URL, f"cp4-golden:instrument:{ticker}"), ids(lst["listing_id"])]
        feed = iter(queue)
        self.ident = InMemoryIdentityRegistry(lambda: next(feed))
        self.ident.register_instruments(entries)
        specs: List[dict] = []
        ticker_listing = {lst["ticker"]: lst["listing_id"] for lst in data["listings"]}  # a price file's series key in a part that declares its files one by one (part 4)

        def emit(base: dict, rows: Sequence[Any], date_of, calendar_id: str, build) -> None:
            """One file per vintage that holds a row (one file when the part declares none): SEGMENTS of one series (market-data Ruling 0.1 (1.12)). The vintage is the file's retrieval time and its declared coverage is its
            request `start` and `end`; nothing about the vintage goes into the series key or `adjustment_anchor`."""
            kind = base["kind"]
            series_key = "ECB" if kind is DataKind.FX else (base["identifiers"][0] if kind in (DataKind.RISK_FREE, DataKind.BENCHMARK) else ticker_listing.get(base["identifiers"][0], base["identifiers"][0]))
            for vintage, part, when, coverage in plan.split(rows, date_of, calendar_id, series_key):
                spec = dict(base, payload=build(part), retrieved=when)
                if vintage is not None:
                    spec["label"] = f"{base['label']}_{vintage}"
                    spec["request"] = tuple(base.get("request", ())) + (("start", coverage[0].isoformat()), ("end", coverage[1].isoformat()))
                specs.append(spec)

        adapters = AdapterRegistry([CalendarFileAdapter(), EcbEurofxrefFxAdapter(x.SRC_ECB), AlphaVantageQuoteAdapter(x.SRC_US), AkshareCnQuoteAdapter(x.SRC_CN), AkshareSinaQuoteAdapter("hk", x.SRC_HK),
                                    SyntheticRiskFreeAdapter(), MockSyntheticAdapter(DataKind.BENCHMARK, "mock.synthetic")])
        calendars: Dict[str, List[datetime.date]] = {}
        for cal in md["calendars"]:
            calendars[cal["calendar_id"]] = calendar_dates(cal)
            specs.append(dict(source_id=x.SRC_CAL, kind=DataKind.CALENDAR, fmt="finweb_calendar_json/1", payload=calendar_payload(cal, calendars[cal["calendar_id"]]), label=cal["calendar_id"], ext="json",
                              identifiers=(cal["calendar_id"],), retrieved=CALENDAR_REGISTERED))  # registered, not retrieved (market-data Ruling 5.3): in every `M_t`
        self.calendar_dates = calendars
        fx = md["fx"]
        ecb = next(cal["calendar_id"] for cal in md["calendars"] if cal["kind"] == "ECB_FIXINGS")
        currencies = list(fx["steps"].keys())
        steps = {ccy: expand_steps(fx["steps"][ccy], fx.get("cycles", {}).get(ccy), "rates", "rate") for ccy in currencies}
        gaps = {ccy: {D(g) for g in fx.get("gaps_by_currency", {}).get(ccy, [])} for ccy in currencies}
        rows = []
        for day in (d for d in calendars[ecb] if D(fx["first"]) <= d <= D(fx["last"])):
            rows.append((day.isoformat(), ["N/A" if day in gaps[ccy] else value_on(steps[ccy], day) for ccy in currencies]))
        emit(dict(source_id=x.SRC_ECB, kind=DataKind.FX, fmt="ecb_eurofxref_hist_csv/1", label="fx", ext="csv", identifiers=tuple(currencies)), rows, lambda r: D(r[0]), ecb,
             lambda part: k.ecb_csv(part, currencies))
        for s in md["prices"]["series"]:
            lst = self.listings[s["listing_id"]]
            gap = {D(g) for g in s["gaps"]}
            closes = expand_steps(s["steps"], s.get("cycle"), "closes", "close")
            sessions = [d for d in calendars[s["calendar"]] if D(s["first"]) <= d <= D(s["last"]) and d not in gap]
            series = [(d, value_on(closes, d), 1000) for d in sessions]
            ccy = CurrencyCode(s["currency"])
            market = MARKET_OF_MIC[lst["mic"]]
            if market == "US":
                emit(dict(source_id=x.SRC_US, kind=DataKind.QUOTE, fmt="alphavantage_csv_daily/1", label=s["ticker"], ext="csv", currency=ccy, adjustment=c.AdjustmentStatus.UNDECLARED,
                          identifiers=(s["ticker"],), request=(("function", "TIME_SERIES_DAILY"), ("outputsize", "compact")), market="US"), series, lambda r: r[0], s["calendar"], x.av_us_csv)
                second = s.get("second_source")
                if second is not None:  # the same sessions from another upstream: every row equals the primary's except the declared overrides, which DISAGREE (market-data Ruling 4.3)
                    overrides = {D(o["date"]): o["close"] for o in second["price_overrides"]}
                    adapters.register(AlphaVantageQuoteAdapter(second["source_id"]))
                    emit(dict(source_id=second["source_id"], kind=DataKind.QUOTE, fmt="alphavantage_csv_daily/1", label=s["ticker"] + "_second", ext="csv", currency=ccy,
                              adjustment=c.AdjustmentStatus.UNDECLARED, identifiers=(s["ticker"],), request=(("function", "TIME_SERIES_DAILY"), ("outputsize", "compact")), market="US"),
                         [(d, overrides.get(d, v), vol) for d, v, vol in series], lambda r: r[0], s["calendar"], x.av_us_csv)
            elif market == "CN":
                emit(dict(source_id=x.SRC_CN, kind=DataKind.QUOTE, fmt="akshare_csv_cn_daily/1", label=s["ticker"], ext="csv", currency=ccy, identifiers=(s["ticker"],),
                          request=(("function", "stock_zh_a_hist"),), market="CN"), series, lambda r: r[0], s["calendar"], lambda part, t=s["ticker"]: eastmoney_exact_csv(part, t))
            else:
                code = "00700" if s["ticker"] == "0700" else s["ticker"]
                emit(dict(source_id=x.SRC_HK, kind=DataKind.QUOTE, fmt="akshare_sina_csv_hk_daily/1", label=code, ext="csv", currency=ccy, identifiers=(code,),
                          request=(("function", "stock_hk_daily"),), market="HK"), series, lambda r: r[0], s["calendar"], x.sina_hk_csv)
        for s in md.get("risk_free", {}).get("series", []):
            cal = calendars[s["calendar"]]
            gap = {D(g) for g in s["gaps"]}
            rates = expand_steps(s["steps"], s.get("cycle"), "rates", "rate")
            points = []
            for day in (d for d in cal if D(s["first"]) <= d <= D(s["last"]) and d not in gap):
                point = {"date": day.isoformat(), "rate": value_on(rates, day)}
                if s["quote_type"] == "BANK_DISCOUNT":
                    point["term_days"] = s["tenor_days"]
                points.append(point)
            def rf_payload(part, s=s):
                return make_risk_free_payload(({"series_id": s["series_id"], "name": s["instrument"], "provider": "synthetic", "instrument": s["instrument"], "tenor_weeks": round(s["tenor_days"] / 7),
                                                "quote_type": s["quote_type"], "day_count_basis": s["day_count_basis"], "unit": s["unit"], "decimals_published": 2,
                                                "date_semantics": "the date the quote is FOR (synthetic)", "calendar_id": s["calendar"], "revision_policy": "NOT_REVISED", "points": part},))

            emit(dict(source_id=RF_SOURCE, kind=DataKind.RISK_FREE, fmt=RF_FORMAT, label=s["series_id"], ext="json", currency=CurrencyCode(s["currency"]), identifiers=(s["series_id"],)),
                 points, lambda r: D(r["date"]), s["calendar"], rf_payload)
        self.benchmarks_loaded: List[str] = []
        registered_benchmark_adapters: set = set()
        for b in md.get("benchmarks", []):
            if b.get("construction") == "ETF_PROXY":
                continue  # no file: the engine builds the series from the listing's prints and actions (Ruling 5.5 (1.2))
            multi = "source_priority" in b
            source = b["source_id"] if multi else "mock.synthetic"
            if multi and source not in registered_benchmark_adapters:  # one adapter per (source, kind), however many benchmarks the source serves
                registered_benchmark_adapters.add(source)
                adapters.register(MockSyntheticAdapter(DataKind.BENCHMARK, source))
            gap = {D(g) for g in b["gaps"]}
            levels = expand_steps(b["steps"], b.get("cycle"), "levels", "level")
            overrides = {D(o["date"]): o["level"] for o in b.get("level_overrides", [])}  # one source publishes another level on a day (the disagreement of R4)
            points = [{"date": d.isoformat(), "value": overrides.get(d, value_on(levels, d))} for d in calendars[b["calendar"]] if D(b["first"]) <= d <= D(b["last"]) and d not in gap and value_on(levels, d) is not None]
            emit(dict(source_id=source, kind=DataKind.BENCHMARK, fmt=MOCK_FORMAT, label=f"{b['benchmark_id']}_{source}" if multi else b["benchmark_id"], ext="json", currency=CurrencyCode(b["currency"]),
                      identifiers=(b["benchmark_id"],),
                      request=(("calendar", b["calendar"]),)),  # a benchmark's index calendar is the catalog's; a series in several files declares it so its coverage can be bounded
                 points, lambda r: D(r["date"]), b["calendar"],
                 lambda part, b=b: make_synthetic_payload(benchmarks=({"benchmark_id": b["benchmark_id"], "provider": b["provider"], "value_kind": "LEVEL", "points": part},)))
            self.benchmarks_loaded.append(b["benchmark_id"])
        if has_actions:
            for source in (CA_FEED, CA_FILING):
                adapters.register(MockSyntheticAdapter(DataKind.CORPORATE_ACTION, source))
            rows_by_file: Dict[Tuple[str, str], List[dict]] = {}  # one file per (source, listing): two files of one source for one series are two vintages (market-data Ruling 0.1)
            for action in md["corporate_actions"]:
                lst = self.listings[action["listing_id"]]
                for rec in action["records"]:
                    source = CA_FEED if rec["side"] == "FEED" else CA_FILING
                    row = {"ticker": lst["ticker"], "mic": lst["mic"], "date": action["ex_date"], "type": action["type"], "note": f"{rec['side']} record of {lst['ticker']} {action['type']} {action['ex_date']}"}
                    if action["type"] == "SPLIT":
                        row.update(new_units=action["ratio"]["new_units"], old_units=action["ratio"]["old_units"])
                    else:
                        row.update(amount=rec["amount"], currency=action["currency"], pay_date=action["pay_date"])
                        if "paid_amount" in rec:  # what the issuer states it paid (risk Ruling 5.5 (1.8) item 2), as the source states it
                            row.update(paid_currency=rec["paid_currency"], paid_amount=rec["paid_amount"])
                    rows_by_file.setdefault((source, lst["ticker"]), []).append(row)
            for (source, ticker), rows in sorted(rows_by_file.items()):
                specs.append(dict(source_id=source, kind=DataKind.CORPORATE_ACTION, fmt=MOCK_FORMAT, payload=make_synthetic_payload(actions=tuple(rows)), label=f"{ticker}_{source.split('.')[-1]}", ext="json",
                                  identifiers=(ticker,), retrieved=plan.actions_time))
        seen: set = set()
        for spec in specs:
            spec["payload"] = _distinct_payload(spec["payload"], seen)
        self.manifests = [_write_file(root, spec.pop("retrieved", DEFAULT_RETRIEVED), **spec) for spec in specs]
        self.release = MarketDataRelease.from_manifests(f"cp4-golden-{data['fixture_id'].split('/')[-1]}", self.manifests, [])
        files = FileStore(root)
        self.built = build_in_memory_market_data(self.release, files, files.load_registry(), adapters, self.ident,
                                                 catalog_calendars={e.benchmark_id: e.calendar_id for e in benchmark_catalog_of(data).entries})  # a segmented benchmark's declared calendar must be the entry's
        self.issues = (self.built.issues, self.built.exceptions)
        self.store = self.built.store
        self.conventions = market11_conventions(self.built.calendars)
        self.has_actions = has_actions
        self.adapters = adapters
        catalog_calendars = {e.benchmark_id: e.calendar_id for e in benchmark_catalog_of(data).entries}
        self.market_at = DerivedReleaseView(self.release, files, files.load_registry(), adapters, self.ident, catalog_calendars=catalog_calendars)  # `M_t` for a Current-mode assertion

    def close(self) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None


# --- the engine runs ------------------------------------------------------------------------------------------------------------------------

def spec_of(request: dict):
    rule = request["rule"]
    if rule == "MAX_AVAILABLE":
        return MaxAvailable()
    return WindowSpec(WindowRule(rule), request.get("months"), D(request["base"]) if "base" in request else None)


def selections_of(portfolio: dict, ids) -> Tuple[SequencedSelection, ...]:
    rows = []
    for rec in portfolio.get("benchmark_selections", []):
        record = RecordType(rec["record_type"]) if "record_type" in rec else RecordType.SELECT if rec["benchmark_id"] is not None else RecordType.CLEAR  # parts 1 and 2 give no record type: a null id clears
        reverses = ids(rec["reverses_selection_id"]) if record is RecordType.REVERSAL else None
        corrects = ids(rec["corrects_selection_id"]) if rec.get("corrects_selection_id") else None
        rows.append(SequencedSelection(rec["seq"], BenchmarkSelection(ids(rec["selection_id"]), ids(rec["portfolio_id"]), record, D(rec["recorded_at"][:10]),
                                                                      benchmark_id=rec["benchmark_id"] if record is RecordType.SELECT else None,
                                                                      origin=Origin.USER_CHOSEN if record is RecordType.SELECT else None, reverses_selection_id=reverses,
                                                                      corrects_selection_id=corrects), atomic_with_seq=rec.get("atomic_with_seq")))  # the part's pair marker is the loader's boundary fact (CP4M-9)
    return tuple(rows)


def resolve_item(runner: "Runner", portfolio: dict, assertion: dict, item: dict) -> List["Mismatch"]:
    """A `selection_resolution` item (Ruling 5.6 (1.4)): the resolution of the log at the pinned version, by the domain's own function (REFUSED is the pin that cannot be taken)."""
    expected = item["selection"]
    out: List[Mismatch] = []
    pid = runner.ids(portfolio["portfolio_id"])
    inverse = {runner.ids(r["selection_id"]): r["selection_id"] for r in portfolio.get("benchmark_selections", [])}
    rows, version = runner.selection_log(portfolio, assertion)  # the fixture's log (pure path), or the log the DATABASE STORES at the pinned version (the PostgreSQL leg: CP4 final review, 41.8)
    try:
        got = resolve_selection(pid, rows, version)
        actual = {"state": got.state.value, "selection_id": None if got.row is None else inverse[got.row.selection.selection_id],
                  "seq": None if got.row is None else runner.fixture_selection_seq(portfolio, got.row.selection_seq), "benchmark_id": None if got.row is None else got.row.selection.benchmark_id}
    except SelectionVersionNotPinnableError:
        actual = {"state": "REFUSED", "selection_id": None, "seq": None, "benchmark_id": None}
    for key, value in expected.items():
        if actual[key] != value:
            out.append(Mismatch(assertion["id"], item["kind"], f"v{assertion['selection_log_version']}", f"selection.{key}", value, actual[key]))
    return out


class Runner:
    """Runs and caches the engine per (portfolio, as-of, request, frequency, scope)."""

    def __init__(self, data: dict, market: Market, ids, verify_identities: bool = True):
        self.data, self.market, self.ids, self.verify = data, market, ids, verify_identities
        self.perf = performance_conventions()
        self.events = {p["name"]: cp1.sequenced(cp1.build_events(p, ids)) for p in data["portfolios"]}
        self.catalog = benchmark_catalog_of(data, ids)
        self._risk: Dict[Any, Any] = {}
        self._series: Dict[Any, Any] = {}
        self._reports: Dict[Any, Any] = {}

    def version(self, portfolio: dict, assertion: dict) -> int:
        return assertion["ledger_version"] if "ledger_version" in assertion else max(e.ledger_seq for e in self.events[portfolio["name"]])

    def selection_log(self, portfolio: dict, assertion: dict):
        """`(the selection rows, the version to pin)` a `selection_resolution` item resolves: the fixture's own log here; the database's stored log in the PostgreSQL runner."""
        return selections_of(portfolio, self.ids), assertion["selection_log_version"]

    def fixture_selection_seq(self, portfolio: dict, seq: int) -> int:
        """The fixture's sequence number of a row of `selection_log` (the same here; the stored number is mapped back in the PostgreSQL runner)."""
        return seq

    def suppressions_for(self, portfolio: dict, version: int, view=None):
        """The F8 suppressions the engine is handed: the dry run over the pinned ledger when the part has corporate actions, else none (stated, not defaulted: CP3-4). In Current mode (`view`) the detection runs
        over `M_t`, the files a computation at `t` could have read (performance Ruling 1.7)."""
        if not self.market.has_actions:
            return ()
        key = (portfolio["name"], version, None if view is None else view.instant)
        if key not in self._reports:
            events = [e for e in self.events[portfolio["name"]] if e.ledger_seq <= version]
            listings = sorted({e.event.listing_id for e in events if e.event.listing_id is not None}, key=str)
            currencies = {lid: c for lid in listings for c in [self.market.ident.trading_currency(lid)] if c is not None}
            port = self.market.store if view is None else view.port
            conventions = self.market.conventions if view is None else view.conventions
            report, _ = svc.detect_split_suppressions(svc.PinnedLedgerAccess(version, events), port, self.ids(portfolio["portfolio_id"]), listings, datetime.date.min, datetime.date.max,
                                                      POLICY, currencies, calendars=conventions.freshness.calendars, exchange_of=self.market.ident.exchange_mic)
            self._reports[key] = report
        return svc.suppressions_from_report(self._reports[key])

    def _args(self, portfolio: dict, assertion: dict, item: dict):
        scope = item.get("scope")
        account = None if scope is None else self.ids(scope["account_id"])
        version = self.version(portfolio, assertion)
        return account, version

    def risk(self, portfolio: dict, assertion: dict, item: dict, metrics: Sequence[str]):
        account, version = self._args(portfolio, assertion, item)
        key = (portfolio["name"], assertion["id"], json.dumps(item["request"], sort_keys=True), item["frequency"], account, tuple(metrics))
        if key not in self._risk:
            common = dict(risk_free_catalog=EMPTY_RISK_FREE_CATALOG, benchmark_catalog=self.catalog, selections=selections_of(portfolio, self.ids), selection_version=assertion.get("selection_log_version", 0),
                          portfolio_id=self.ids(portfolio["portfolio_id"]), metrics=metrics, account_scope=account, verify_identities=self.verify)
            if assertion.get("valuation_mode") == "CURRENT":  # Ruling 5.8: over M_t at the instant, `E = D_c(t)`
                self._risk[key] = compute_risk_current(
                    self.events[portfolio["name"]], version, spec_of(item["request"]), _utc(assertion["instant"]), Frequency(item["frequency"]), CurrencyCode(portfolio["reporting_currency"]),
                    self.market.market_at, self.market.ident, self.perf, suppressions=lambda view, p=portfolio, v=version: self.suppressions_for(p, v, view), **common)
            else:
                self._risk[key] = compute_risk(
                    self.events[portfolio["name"]], version, spec_of(item["request"]), D(assertion["as_of"]), Frequency(item["frequency"]), CurrencyCode(portfolio["reporting_currency"]), self.market.store,
                    self.market.ident, self.market.conventions, self.perf, suppressions=self.suppressions_for(portfolio, version), **common)
        return self._risk[key]

    def series(self, portfolio: dict, assertion: dict, item: dict):
        account, version = self._args(portfolio, assertion, item)
        key = (portfolio["name"], assertion["id"], json.dumps(item["request"], sort_keys=True), item["frequency"], account)
        if key not in self._series:
            view = self.view_of(assertion)
            end = self.current_date(portfolio, assertion) if view is not None else D(assertion["as_of"])
            port, conventions = (self.market.store, self.market.conventions) if view is None else (view.port, view.conventions)
            self._series[key] = compute_return_series(
                self.events[portfolio["name"]], version, spec_of(item["request"]), end, Frequency(item["frequency"]), WeekdayFridayMonthEndGrid(),
                CurrencyCode(portfolio["reporting_currency"]), port, self.market.ident, conventions, self.perf, suppressions=self.suppressions_for(portfolio, version, view),
                portfolio_id=self.ids(portfolio["portfolio_id"]), account_scope=account, verify_identities=self.verify)
        return self._series[key]

    def view_of(self, assertion: dict):
        """`M_t` for a Current-mode assertion (performance Ruling 1.7), None for a historical one."""
        return self.market.market_at.view(_utc(assertion["instant"])) if assertion.get("valuation_mode") == "CURRENT" else None

    def current_date(self, portfolio: dict, assertion: dict) -> datetime.date:
        """`D_c(t)` of a Current-mode assertion, from the portfolio's own inputs (performance Ruling 1.7)."""
        view = self.view_of(assertion)
        _a, version = self._args(portfolio, assertion, {})
        chosen = choose_current_date(_utc(assertion["instant"]), tuple(self.events[portfolio["name"]]), version, view.calendars, self.market.ident.exchange_mic, CurrencyCode(portfolio["reporting_currency"]),
                                     self.market.ident.trading_currency)
        assert chosen.date is not None, chosen.causes
        return chosen.date


# --- what is checked, what is deferred -------------------------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Deferred:
    assertion_id: str
    kind: str
    reason: str


def disposition(data: dict, portfolio: dict, assertion: dict, item: dict) -> Optional[str]:
    """None when the item is CHECKED, else the reason it is DEFERRED (one of `DEFERRED_REASONS`)."""
    kind = item["kind"]
    if kind in ("selection_resolution", "default_view"):
        return None
    if kind in KIND_METRIC or kind in SERIES_KINDS:
        return None
    return "KIND_UNKNOWN_TO_THIS_LOADER"


def _selection_in_force(portfolio: dict, assertion: dict) -> Optional[str]:
    """The benchmark id in force at the assertion's pinned version, by the domain's resolution (None: none in force, cleared, or the pin is refused)."""
    ids = uuid.UUID  # the fixture's ids are literal UUIDs
    try:
        got = resolve_selection(ids(portfolio["portfolio_id"]), selections_of(portfolio, ids), assertion.get("selection_log_version", 0))
    except SelectionVersionNotPinnableError:
        return None
    return None if got.row is None else got.row.selection.benchmark_id


def items(data: dict) -> Iterable[Tuple[dict, dict, dict]]:
    for p in data["portfolios"]:
        for a in p["assertions"]:
            for it in a["expect"]:
                yield p, a, it


def tally(data: dict) -> Tuple[int, List[Deferred]]:
    """(the number of items that are checked, the deferred ones)."""
    checked, deferred = 0, []
    for p, a, it in items(data):
        why = disposition(data, p, a, it)
        if why is None:
            checked += 1
        else:
            deferred.append(Deferred(a["id"], it["kind"], why))
    return checked, deferred


# --- checking -------------------------------------------------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Mismatch:
    assertion_id: str
    kind: str
    item: str
    field: str
    expected: Any
    actual: Any

    def __str__(self) -> str:
        return f"{self.assertion_id} [{self.kind} {self.item}] {self.field}: expected {self.expected!r}, actual {self.actual!r}"


def _label(item: dict) -> str:
    return f"{item['frequency']}/{json.dumps(item['request'], sort_keys=True)}" + ("" if "scope" not in item else f"/{item['scope']['account_id']}")


def _window_obj(w) -> Optional[dict]:
    if w is None:
        return None
    out = {"base_date": w.base_date.isoformat(), "last_period_end": w.last_period_end.isoformat(), "observation_count": w.observation_count, "stub_start_days": w.stub_start_days,
           "stub_end_days": w.stub_end_days}
    if w.max_available_start is not None:
        out["max_available_start"] = w.max_available_start
    return out


def _compare_window(bad, expected: Optional[dict], actual: Optional[dict]) -> None:
    if (expected is None) != (actual is None):
        bad("effective_window", expected, actual)
        return
    if expected is not None:
        for key, value in expected.items():
            if actual.get(key) != value:
                bad(f"effective_window.{key}", value, actual.get(key))


def _risk_names(details: Iterable[str]) -> List[str]:
    return sorted(set(details) & S.RISK_DETAIL_NAMES)


def check_metric_item(result, assertion: dict, item: dict) -> List[Mismatch]:
    aid, kind = assertion["id"], item["kind"]
    out: List[Mismatch] = []

    def bad(field, expected, actual):
        out.append(Mismatch(aid, kind, _label(item), field, expected, actual))

    m = result.metric(KIND_METRIC[kind])
    if m.state.value != item["state"]:
        bad("state", item["state"], m.state.value)
    actual_reason = None if m.result.reason_code is None else m.result.reason_code.value
    if actual_reason != item["reason"]:
        bad("reason", item["reason"], actual_reason)
    expected_value = None if item["value"] is None else Decimal(item["value"])
    if expected_value != m.value:
        bad("value", None if expected_value is None else str(expected_value), None if m.value is None else str(m.value))
    if kind in SQRT_KINDS:
        if item.get("exact_square") is None:
            if m.exact_square is not None:
                bad("exact_square", None, str(m.exact_square))
        else:
            if m.exact_square != Fraction(item["exact_square"]):
                bad("exact_square", item["exact_square"], None if m.exact_square is None else str(m.exact_square))
            if m.sign != item["sign"]:
                bad("sign", item["sign"], m.sign)
    else:
        expected_exact = None if item.get("exact") is None else Fraction(item["exact"])
        if m.exact != expected_exact:
            bad("exact", None if expected_exact is None else str(expected_exact), None if m.exact is None else str(m.exact))
    if "thresholds" in item:
        expected = None if item["thresholds"] is None else (item["thresholds"]["insufficient_below"], item["thresholds"]["available_from"])
        if m.thresholds != expected:
            bad("thresholds", expected, m.thresholds)
    if _risk_names(m.details) != sorted(item["details_include"]):
        bad("details_include", sorted(item["details_include"]), _risk_names(m.details))
    if m.requested_base is None or m.requested_base.isoformat() != item["requested_base"]:
        bad("requested_base", item["requested_base"], None if m.requested_base is None else m.requested_base.isoformat())
    _compare_window(bad, item["effective_window"], _window_obj(m.window))
    if kind == "max_drawdown":
        dd = m.drawdown
        for field in ("peak_date", "trough_date", "recovery_date"):
            actual = None if dd is None or getattr(dd, field) is None else getattr(dd, field).isoformat()
            if actual != item.get(field):
                bad(field, item.get(field), actual)
    if "stale_period_count" in item and m.stale_period_count != item["stale_period_count"]:
        bad("stale_period_count", item["stale_period_count"], m.stale_period_count)
    if "as_of_resolved" in item:  # Current mode: `D_c(t)`, recorded in the manifest's Current block
        current = result.manifest.current
        actual_asof = None if current is None or current.as_of is None else current.as_of.isoformat()
        if actual_asof != item["as_of_resolved"]:
            bad("as_of_resolved", item["as_of_resolved"], actual_asof)
    if "comparability" in item:
        expected_c = item["comparability"]
        actual_c = None if m.comparability is None else m.comparability.to_obj()
        if actual_c is not None:
            actual_c = json.loads(json.dumps(actual_c, default=lambda o: o.isoformat()))  # dates as the fixture writes them
        if actual_c != expected_c:
            bad("comparability", expected_c, actual_c)
    elif m.comparability is not None:
        bad("comparability", None, m.comparability.to_obj())
    if "v_beta" in item:
        actual_v = dict(m.intermediates).get("v_beta")
        if (None if actual_v is None else str(actual_v)) != (None if item["v_beta"] is None else str(Fraction(item["v_beta"]))):
            bad("v_beta", item["v_beta"], None if actual_v is None else str(actual_v))
    if "decomposition_view" in item:
        actual_d = None if m.decomposition is None else {k: format(v, "f") for k, v in m.decomposition}
        if actual_d != item["decomposition_view"]:
            bad("decomposition_view", item["decomposition_view"], actual_d)
    if kind == "benchmark_return" or kind in RELATIVE_KINDS:
        expected_b = assertion.get("benchmark_expected", {})
        ref = m.benchmark
        actual_b = {} if ref is None else {"benchmark_id": ref.benchmark_id, "selection_id": ref.selection_id, "return_basis": ref.return_basis, "currency": ref.currency,
                                           "currency_treatment": ref.currency_treatment}
        for key, value in expected_b.items():
            if actual_b.get(key) != value:
                bad(f"benchmark.{key}", value, actual_b.get(key))
    return out


def check_return_series_item(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[Mismatch]:
    aid, kind = assertion["id"], "return_series"
    out: List[Mismatch] = []

    def bad(field, expected, actual):
        out.append(Mismatch(aid, kind, _label(item), field, expected, actual))

    result = runner.series(portfolio, assertion, item)
    series = result.series
    if series is None:
        agg = S.combine([window_part(result.refusal)])
    else:
        parts, _ = series_parts(series)
        agg = S.combine(parts)
    if agg.state.value != item["state"]:
        bad("state", item["state"], agg.state.value)
    if agg.reason != item["reason"]:
        bad("reason", item["reason"], agg.reason)
    if _risk_names(S.details_of(agg.causes)) != sorted(item["details_include"]):
        bad("details_include", sorted(item["details_include"]), _risk_names(S.details_of(agg.causes)))
    _compare_window(bad, item["effective_window"], None if series is None else _window_obj(series.grid))
    if "returns" in item:
        got = [] if series is None else [(p.end.isoformat(), None if p.exact is None else str(p.exact), p.valued.state.value) for p in series.periods]
        want = [(r["period_end"], r["exact"], r["state"]) for r in item["returns"]]
        if len(got) != len(want):
            bad("returns.count", len(want), len(got))
        for g, w in zip(got, want):
            if g[0] != w[0] or (g[1] is None) != (w[1] is None) or (g[1] is not None and Fraction(g[1]) != Fraction(w[1])) or g[2] != w[2]:
                bad(f"returns[{w[0]}]", w, g)
    return out


def check_rates_item(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[Mismatch]:
    aid, kind = assertion["id"], "risk_free_rates"
    out: List[Mismatch] = []

    def bad(field, expected, actual):
        out.append(Mismatch(aid, kind, _label(item), field, expected, actual))

    result = runner.series(portfolio, assertion, item)
    series = result.series
    if series is None:
        bad("series", "a window", "refused")
        return out
    view = runner.view_of(assertion)  # Current mode: the rates are read over `M_t`, with a publication not yet due neither used nor missed (Ruling 5.8 items 4 and 5)
    rates = risk_free_rates(runner.market.store if view is None else view.port, CurrencyCode(portfolio["reporting_currency"]), series.boundaries,
                            runner.market.conventions if view is None else view.conventions, None if view is None else _utc(assertion["instant"]))
    if "as_of_resolved" in item and runner.current_date(portfolio, assertion).isoformat() != item["as_of_resolved"]:
        out.append(Mismatch(aid, kind, _label(item), "as_of_resolved", item["as_of_resolved"], runner.current_date(portfolio, assertion).isoformat()))
    agg = S.combine(rate_parts(rates))
    if agg.state.value != item["state"]:
        bad("state", item["state"], agg.state.value)
    if agg.reason != item["reason"]:
        bad("reason", item["reason"], agg.reason)
    _compare_window(bad, item["effective_window"], _window_obj(series.grid))
    want = item["rates"]
    if len(rates) != len(want):
        bad("rates.count", len(want), len(rates))
    for r, w in zip(rates, want):
        if (r.start.isoformat(), r.end.isoformat()) != (w["period_start"], w["period_end"]):
            bad("rates.period", (w["period_start"], w["period_end"]), (r.start.isoformat(), r.end.isoformat()))
        if None if r.quote_date is None else r.quote_date.isoformat() != w["quote_date"]:
            bad(f"rates[{w['period_end']}].quote_date", w["quote_date"], r.quote_date)
        if r.missed_publications != w["missed_publications"]:
            bad(f"rates[{w['period_end']}].missed_publications", w["missed_publications"], r.missed_publications)
        if r.exact is None or r.exact != Fraction(w["exact"]):
            bad(f"rates[{w['period_end']}].exact", w["exact"], None if r.exact is None else str(r.exact))
    return out


METRIC_ID_OF = KIND_METRIC


def run_default_view(runner: Runner, portfolio: dict, assertion: dict, item: dict):
    """The composition of Ruling 7.7 over the runner: both underlying results are ordinary ones (the same frequency, scope, instant and selection)."""
    metric_id = KIND_METRIC[item["metric"]]

    def compute(request):
        spec = {"rule": "MAX_AVAILABLE"} if isinstance(request, MaxAvailable) else {"rule": request.rule.value, "months": request.months}
        return runner.risk(portfolio, assertion, dict(item, request=spec), (metric_id,))

    return default_view(compute, metric_id, WindowSpec(WindowRule(item["default_request"]["rule"]), item["default_request"].get("months"))), metric_id


def check_default_view(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[Mismatch]:
    """A `default_view` item (part 3 `format.default_view`): `fallback`, the refused summary (or null) and the shown summary."""
    view, metric_id = run_default_view(runner, portfolio, assertion, item)
    out: List[Mismatch] = []
    aid = assertion["id"]
    if view.fallback != item["fallback"]:
        out.append(Mismatch(aid, "default_view", item["metric"], "fallback", item["fallback"], view.fallback))
    if (item["refused"] is None) != (view.refused is None):
        out.append(Mismatch(aid, "default_view", item["metric"], "refused", item["refused"], None if view.refused is None else view.refused.state.value))
    shown_result = view.y if view.fallback else view.x
    pairs = [("shown", item["shown"], shown_result)]
    if item["refused"] is not None:
        pairs.append(("refused", item["refused"], view.x))
    for label, summary, result in pairs:
        pseudo = dict(summary, kind=item["metric"], frequency=item["frequency"])
        # the view's summary names no comparability object (the format lists the fields it asserts), so that field is not compared; the underlying results assert it as ordinary items
        out += [Mismatch(m.assertion_id, f"default_view.{label}", m.item, m.field, m.expected, m.actual) for m in check_metric_item(result, assertion, pseudo) if m.field != "comparability"]
    ev = view.evidence()  # the evidence record names both digests when it fell back (P9)
    if view.fallback and (ev["y_result_digest"] is None or ev["x_result_digest"] == ev["y_result_digest"]):
        out.append(Mismatch(aid, "default_view", item["metric"], "evidence", "two distinct result digests", ev))
    return out


def check_item(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[Mismatch]:
    kind = item["kind"]
    if kind == "return_series":
        return check_return_series_item(runner, portfolio, assertion, item)
    if kind == "risk_free_rates":
        return check_rates_item(runner, portfolio, assertion, item)
    if kind == "selection_resolution":
        return resolve_item(runner, portfolio, assertion, item)
    if kind == "default_view":
        return check_default_view(runner, portfolio, assertion, item)
    result = runner.risk(portfolio, assertion, item, (KIND_METRIC[kind],))
    return check_metric_item(result, assertion, item)


def check_all(runner: Runner) -> Tuple[List[Mismatch], int, List[Deferred]]:
    mismatches: List[Mismatch] = []
    checked = 0
    deferred: List[Deferred] = []
    for p, a, it in items(runner.data):
        why = disposition(runner.data, p, a, it)
        if why is not None:
            deferred.append(Deferred(a["id"], it["kind"], why))
            continue
        mismatches += check_item(runner, p, a, it)
        checked += 1
    return mismatches, checked, deferred


_SHARED: Dict[int, Runner] = {}


def shared_runner(part: int) -> Runner:
    """One market and one runner per part for the whole test process (the expansion and ingest are the cost). Files are cut and retrieved as the part declares (`VintagePlan`)."""
    if part not in _SHARED:
        data = load_part(part)
        ids = cp1.Ids(randomize=False)
        _SHARED[part] = Runner(data, Market(data, ids), ids)
    return _SHARED[part]


def build_runner(part: int, ids=None, verify_identities: bool = True) -> Tuple[Runner, Market]:
    data = load_part(part)
    ids = ids or cp1.Ids(randomize=False)
    market = Market(data, ids)
    return Runner(data, market, ids, verify_identities), market


if __name__ == "__main__":  # a plain report of every mismatch, for the findings list
    for part in (1, 2, 3):
        runner, market = build_runner(part)
        print(f"part {part}: market-data build issues:", market.issues)
        found, n, deferred = check_all(runner)
        print(f"part {part}: {n} items checked, {len(deferred)} deferred, {len(found)} mismatches")
        for mm in found:
            print("  ", mm)
