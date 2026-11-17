"""Loader and checker for the CP3 golden fixture, part 1 (`methodology/fixtures/cp3_golden/cp3_golden_part1.json`, `cp3_golden/1.2-part1`).

This module NEVER edits the fixture and never derives an expected value. It EXPANDS the fixture's compact synthetic market-data block into real CP2 file layouts (calendar
files with explicit date lists; an ECB `eurofxref-hist` CSV; one RAW price file per listing in the Alpha Vantage, Hong Kong (Sina) and Mainland (Eastmoney) layouts),
registers them under SYNTHETIC source ids, and ingests them through the real adapters, resolver, calendars and checks into one release M. The expansion is mechanical: every
price and rate is the decimal string the fixture gives. It then runs the engine at each assertion's (D, L) or window and compares every `expect` item.

`check_*` functions return `Mismatch` records (assertion id, item, field, expected, actual). A mismatch is a FINDING for the Quant or the engineer: neither side is adjusted here.
"""

import dataclasses
import datetime
import json
import sys
import tempfile
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402

k = x.k
c = x.c

from domain.currency import CurrencyCode  # noqa: E402
from domain.instrument import SecurityType  # noqa: E402
from domain.replay import SequencedEvent  # noqa: E402
from marketdata.adapters.alphavantage import AlphaVantageQuoteAdapter  # noqa: E402
from marketdata.adapters.akshare_cn import AkshareCnQuoteAdapter  # noqa: E402
from marketdata.adapters.akshare_sina import AkshareSinaQuoteAdapter  # noqa: E402
from marketdata.adapters.base import AdapterRegistry  # noqa: E402
from marketdata.adapters.calendar_file import CalendarFileAdapter  # noqa: E402
from marketdata.adapters.ecb_eurofxref import EcbEurofxrefFxAdapter  # noqa: E402
from marketdata.canonical import sha256_hex  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, FileManifest, MarketDataRelease  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402
from performance.engine import compute, compute_window, performance_conventions  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402

FIXTURE_PATH = _ROOT / "methodology" / "fixtures" / "cp3_golden" / "cp3_golden_part1.json"
RETRIEVED = datetime.datetime(2026, 2, 2, 9, 0, tzinfo=datetime.timezone.utc)  # after every date in the fixture's market data
CA_FEED, CA_FILING = "synthetic.ca_feed", "synthetic.ca_filing"  # part 2: the synthetic corporate-action FEED and issuer FILING sources (market-data Ruling 4.8 item 4)
D = datetime.date.fromisoformat


def _family_and_version(text: str) -> Tuple[str, Tuple[int, ...]]:
    """`performance/1.10 (note)` -> ("performance", (1, 10)): the family and the dotted version as INTEGERS (1.10 is later than 1.9), never as a string."""
    token = text.strip().split(" ", 1)[0]
    family, _, version = token.partition("/")
    return family, tuple(int(part) for part in version.split("."))


def cites_at_least(cited: str, minimum: str) -> bool:
    """PM ruling OI-P11: a fixture's `convention_sets` are MINIMUM versions. A manifest satisfies one when it cites the SAME family at that version or LATER (dotted integers)."""
    cf, cv = _family_and_version(cited)
    mf, mv = _family_and_version(minimum)
    return cf == mf and cv >= mv


def convention_problems(conventions: Dict[str, str], fixture_sets: Dict[str, str]) -> List[str]:
    """Why a manifest's `conventions` do not satisfy a fixture's `convention_sets` (empty when they do). Exact-match pins on fixture ids and content hashes are elsewhere."""
    wanted = {"performance.convention_set": fixture_sets["performance"], "ledger_replay": fixture_sets["ledger_replay"], "market_data.convention_set": fixture_sets["market_data"]}
    return [f"{key}: cites {conventions.get(key)!r}, the fixture needs {minimum!r} or later" for key, minimum in wanted.items()
            if key not in conventions or not cites_at_least(conventions[key], minimum)]


def _no_float(text):
    raise AssertionError(f"the fixture must hold no float literal, found {text!r}")


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"), parse_float=_no_float)


FIXTURE = load_fixture()


def content_hash(fixture: dict = FIXTURE) -> str:
    import hashlib  # noqa: PLC0415

    content = [[a["id"], a["as_of"], a["ledger_version"], a["expect"]] for p in fixture["portfolios"] for a in p["assertions"]]
    text = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def items(fixture: dict = FIXTURE) -> Iterable[Tuple[dict, dict, dict]]:
    for p in fixture["portfolios"]:
        for a in p["assertions"]:
            for it in a["expect"]:
                yield p, a, it


# --- the synthetic market data, expanded mechanically ------------------------------------------------------------------------------------

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


def _step_value(steps: List[dict], key: str, day: datetime.date) -> Optional[str]:
    current = None
    for s in steps:
        if D(s["from"]) <= day:
            current = s[key]
    return current


def _write_file(root: Path, source_id: str, kind: DataKind, fmt: str, payload: bytes, label: str, ext: str, *, currency=None,
                adjustment=c.AdjustmentStatus.RAW, identifiers=(), request=(), market=None) -> FileManifest:
    directory = root / "files" / source_id / kind.value.lower() / "2026-02-02"
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{label}.{ext}"
    manifest = FileManifest(
        file_sha256=sha256_hex(payload), size_bytes=len(payload), payload_filename=name, payload_format=fmt, source_id=source_id, data_kind=kind,
        retrieval_time=RETRIEVED, retrieved_by="synthetic", declared_adjustment=adjustment, usage_scope=c.UsageScope.SYNTHETIC_TEST,
        declared_currency=currency, declared_delay=c.DataDelayStatus.END_OF_DAY, source_identifiers=tuple(identifiers), request=tuple(request),
        market=market)
    (directory / name).write_bytes(payload)
    (directory / (name + ".manifest.json")).write_text(manifest.to_json(), encoding="utf-8")
    return manifest


class Market:
    """The expanded market-data version M, the identity registry and the conventions. `ids` maps the fixture's fixed ids to the ids used."""

    def __init__(self, ids, root: Optional[Path] = None, extra: Optional[dict] = None):
        """`extra` (part 2: `market_data_additions`): `{"listings": [...], "series": [...], "corporate_actions": [...]}` added to part 1's market data to make ONE release M.
        A corporate-action record becomes a file in the mock layout under a synthetic FEED or FILING source id, with the fixture's own numbers and no other."""
        self.ids = ids
        self._tmp = None
        extra = extra or {}
        if root is None:
            self._tmp = tempfile.TemporaryDirectory()
            root = Path(self._tmp.name)
        self.root = root
        md = FIXTURE["market_data"]
        from marketdata.manifest import SourceRecord  # noqa: PLC0415

        ca_sources = [SourceRecord(s, s, "synthetic", f"synthetic.{s}", synthetic=True) for s in (CA_FEED, CA_FILING)] if extra.get("corporate_actions") else []
        x.kit.write_registry(root, extra=x.synthetic_registry_records() + ca_sources)
        # identity: the fixture's listings, created by the registry with the fixture's own listing ids (3 ids per entry: issuer, instrument, listing)
        queue: List[uuid.UUID] = []
        self.entries: List[Tuple[dict, InstrumentEntry]] = []
        for lst in FIXTURE["listings"] + list(extra.get("listings", [])):
            ticker, mic = lst["ticker"], lst["mic"]
            market = {"XNYS": "US", "XHKG": "HK", "XSHG": "CN"}[mic]
            vendor = {"US": (x.SRC_US, ticker), "HK": (x.SRC_HK, "00700" if ticker == "0700" else ticker),
                      "CN": (x.SRC_CN, ticker)}[market]
            stype = SecurityType(lst.get("security_type", "COMMON_STOCK"))
            self.entries.append((lst, InstrumentEntry(f"Synthetic issuer {ticker}", stype, mic, mic, ticker, CurrencyCode(lst["trading_currency"]),
                                                       vendor_ids=(vendor,))))
            queue += [uuid.uuid5(uuid.NAMESPACE_URL, f"cp3-golden:issuer:{ticker}"), uuid.uuid5(uuid.NAMESPACE_URL, f"cp3-golden:instrument:{ticker}"),
                      ids(lst["listing_id"])]
        feed = iter(queue)
        self.ident = InMemoryIdentityRegistry(lambda: next(feed))
        self.ident.register_instruments([e for _l, e in self.entries])
        for lst, _e in self.entries:
            assert self.ident.trading_currency(ids(lst["listing_id"])) == CurrencyCode(lst["trading_currency"]), lst

        specs: List[dict] = []
        adapters = AdapterRegistry([CalendarFileAdapter(), EcbEurofxrefFxAdapter(x.SRC_ECB), AlphaVantageQuoteAdapter(x.SRC_US),
                                    AkshareCnQuoteAdapter(x.SRC_CN), AkshareSinaQuoteAdapter("hk", x.SRC_HK)])
        calendars = {}
        for cal in md["calendars"]:
            dates = calendar_dates(cal)
            calendars[cal["calendar_id"]] = dates
            overrides = {}
            if cal["kind"] == "EXCHANGE_SESSIONS":
                overrides["close"] = {"default": cal["close"]["default"], "overrides": cal["close"]["overrides"]}
            else:
                overrides["fixing"] = cal["fixing"]
            payload = k.calendar_json(cal["calendar_id"], cal["kind"], tuple(cal["applies_to"]), cal["timezone"],
                                      (cal["coverage"]["from"], cal["coverage"]["to"]), [d.isoformat() for d in dates],
                                      cal["actual_through"], **overrides)
            specs.append(dict(source_id=x.SRC_CAL, kind=DataKind.CALENDAR, fmt="finweb_calendar_json/1", payload=payload,
                              label=cal["calendar_id"], ext="json", identifiers=(cal["calendar_id"],)))
        fx = md["fx"]
        ecb_dates = calendars["SYN_ECB"]
        first, last = D(fx["first"]), D(fx["last"])
        rows = []
        for day in (d for d in ecb_dates if first <= d <= last):
            rows.append((day.isoformat(), [_step_value(fx["steps"][ccy], "rate", day) for ccy in ("USD", "HKD", "CNY")]))
        specs.append(dict(source_id=x.SRC_ECB, kind=DataKind.FX, fmt="ecb_eurofxref_hist_csv/1", payload=k.ecb_csv(rows, ["USD", "HKD", "CNY"]),
                          label="fx", ext="csv", identifiers=("USD", "HKD", "CNY")))
        from marketdata.adapters.mock import MOCK_FORMAT, MockSyntheticAdapter, make_synthetic_payload  # noqa: PLC0415

        if extra.get("corporate_actions"):
            for source in (CA_FEED, CA_FILING):
                adapters.register(MockSyntheticAdapter(DataKind.CORPORATE_ACTION, source))

        for s in list(md["prices"]["series"]) + list(extra.get("series", [])):
            gaps = {D(g) for g in s["gaps"]}
            sessions = [d for d in calendars[s["calendar"]] if D(s["first"]) <= d <= D(s["last"]) and d not in gaps]
            series = [(d, _step_value(s["steps"], "close", d), 1000) for d in sessions]
            ccy = CurrencyCode(s["currency"])
            if s["calendar"] == "SYN_NYSE":
                specs.append(dict(source_id=x.SRC_US, kind=DataKind.QUOTE, fmt="alphavantage_csv_daily/1", payload=x.av_us_csv(series), label=s["ticker"],
                                  ext="csv", currency=ccy, adjustment=c.AdjustmentStatus.UNDECLARED, identifiers=(s["ticker"],),
                                  request=(("function", "TIME_SERIES_DAILY"), ("outputsize", "compact")), market="US"))
            elif s["calendar"] == "SYN_CN_A":
                specs.append(dict(source_id=x.SRC_CN, kind=DataKind.QUOTE, fmt="akshare_csv_cn_daily/1", payload=x.eastmoney_csv(series, s["ticker"]),
                                  label=s["ticker"], ext="csv", currency=ccy, identifiers=(s["ticker"],),
                                  request=(("function", "stock_zh_a_hist"),), market="CN"))
            else:
                code = "00700" if s["ticker"] == "0700" else s["ticker"]
                specs.append(dict(source_id=x.SRC_HK, kind=DataKind.QUOTE, fmt="akshare_sina_csv_hk_daily/1", payload=x.sina_hk_csv(series),
                                  label=code, ext="csv", currency=ccy, identifiers=(code,),
                                  request=(("function", "stock_hk_daily"),), market="HK"))
        listing_by_id = {lst["listing_id"]: lst for lst in FIXTURE["listings"] + list(extra.get("listings", []))}
        for action in extra.get("corporate_actions", []):
            lst = listing_by_id[action["listing_id"]]
            for rec in action["records"]:
                source = CA_FEED if rec["side"] == "FEED" else CA_FILING
                row = {"ticker": lst["ticker"], "mic": lst["mic"], "date": action["ex_date"], "type": action["type"],
                       "new_units": action["ratio"]["new_units"], "old_units": action["ratio"]["old_units"],
                       "note": f"{rec['side']} record of {lst['ticker']} {action['type']} {action['ex_date']}"}  # the note makes the two files' bytes (so hashes) differ
                specs.append(dict(source_id=source, kind=DataKind.CORPORATE_ACTION, fmt=MOCK_FORMAT, payload=make_synthetic_payload(actions=(row,)),
                                  label=f"{lst['ticker']}_{rec['side'].lower()}", ext="json", identifiers=(lst["ticker"],)))
        self.manifests = [_write_file(root, **s) for s in specs]
        self.release = MarketDataRelease.from_manifests(extra.get("release_name", "cp3-golden-part1"), self.manifests, [])
        files = FileStore(root)
        self.built = build_in_memory_market_data(self.release, files, files.load_registry(), adapters, self.ident, catalog_calendars={})
        self.issues = (self.built.issues, self.built.exceptions)
        self.store = self.built.store
        self.calendars = self.built.calendars
        self.conventions = market11_conventions(self.calendars)

    def close(self) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None


# --- portfolios -----------------------------------------------------------------------------------------------------------------------

def portfolio_events(portfolio: dict, ids) -> List[SequencedEvent]:
    """P1 and P2 take their events from `cp1_golden/1.1` (same ids, accounts, ledger_seq); P3 to P6 carry their own."""
    if "events" not in portfolio:
        source = cp1.portfolio_named(portfolio["name"][:2])
        return cp1.sequenced(cp1.build_events(source, ids))
    return cp1.sequenced(cp1.build_events(portfolio, ids))


# --- running the engine ------------------------------------------------------------------------------------------------------------

def spec_of(request: dict) -> WindowSpec:
    rule = WindowRule(request["rule"])
    return WindowSpec(rule, request.get("months"), D(request["base"]) if "base" in request else None)


class Runner:
    """Runs and caches the engine per (portfolio, as_of, L[, window request])."""

    def __init__(self, market: Market, ids, events_by_portfolio: Dict[str, List[SequencedEvent]], verify_identities: bool = False,
                 seq_map: Optional[Dict[str, Dict[int, int]]] = None):
        """`seq_map` maps the fixture's ledger_seq to the stored one (a database ledger numbers its own rows)."""
        self.market, self.ids, self.events = market, ids, events_by_portfolio
        self.verify = verify_identities
        self.seq_map = seq_map
        self.perf = performance_conventions()
        self._valuation: Dict[Any, Any] = {}
        self._window: Dict[Any, Any] = {}

    def version(self, portfolio: dict, assertion: dict) -> int:
        fixture_l = assertion["ledger_version"]
        return fixture_l if self.seq_map is None else self.seq_map[portfolio["name"]][fixture_l]

    def suppressions_for(self, portfolio: dict, version: int):
        """The F8 suppressions handed to the engine. Part 1 has no corroborated split (stated, not defaulted: CP3-4); part 2's runner runs the F8-B dry run."""
        return ()

    def valuation(self, portfolio: dict, assertion: dict):
        key = (portfolio["name"], assertion["as_of"], assertion["ledger_version"])
        if key not in self._valuation:
            self._valuation[key] = compute(
                self.events[portfolio["name"]], self.version(portfolio, assertion), D(assertion["as_of"]), CurrencyCode(portfolio["reporting_currency"]),
                self.market.store, self.market.ident, self.market.conventions, self.perf, portfolio_id=self.ids(portfolio["portfolio_id"]),
                suppressions=self.suppressions_for(portfolio, self.version(portfolio, assertion)))
        return self._valuation[key]

    def window(self, portfolio: dict, assertion: dict, request: dict):
        key = (portfolio["name"], assertion["as_of"], assertion["ledger_version"], json.dumps(request, sort_keys=True))
        if key not in self._window:
            self._window[key] = compute_window(
                self.events[portfolio["name"]], self.version(portfolio, assertion), spec_of(request), D(assertion["as_of"]),
                CurrencyCode(portfolio["reporting_currency"]), self.market.store, self.market.ident, self.market.conventions, self.perf,
                portfolio_id=self.ids(portfolio["portfolio_id"]), verify_identities=self.verify,
                suppressions=self.suppressions_for(portfolio, self.version(portfolio, assertion)))
        return self._window[key]


# --- checking ------------------------------------------------------------------------------------------------------------------

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


METRIC_ID = {"gain_absolute": "gain_absolute", "twr": "return_twr", "annualized_twr": "return_annualized",
             "priced_holdings_value": "portfolio_value_priced_holdings",
             # part 2 kinds (the loader maps kinds to engine metric ids; a rename is a mapping change, not a fixture change)
             "mwr": "return_mwr", "annualized_mwr": "return_mwr_annualized", "income_amount": "income_amount", "fees_amount": "fees_amount",
             "taxes_amount": "taxes_amount", "financing_amount": "financing_amount", "conversion_result_amount": "conversion_result_amount"}


def _label(item: dict) -> str:
    return "/".join(str(item[k]) for k in ("view", "currency", "account_id", "listing_id") if k in item) or "-"


def select(result, item: dict, ids) -> List[Any]:
    kind = item["kind"]
    metrics = list(result.metrics)
    if kind in METRIC_ID:
        return [m for m in metrics if m.metric_id == METRIC_ID[kind]]
    subject: Dict[str, str] = {}
    if "account_id" in item:
        subject["account"] = str(ids(item["account_id"]))
    if "listing_id" in item:
        subject["listing"] = str(ids(item["listing_id"]))
    if kind == "receivable_value":
        subject["event"] = str(ids(item["event_id"]))
    if kind == "cash_value":
        subject["currency"] = item["currency"]
    if kind == "portfolio_value" and item["view"] == "NATIVE":
        subject["currency"] = item["currency"]
    return [m for m in metrics if m.metric_id == kind and (item.get("view") is None or m.view == item["view"])
            and all(p in dict(m.subject).items() for p in subject.items())
            and (kind != "portfolio_value" or len(m.subject) == 1)]


def _lineage(m) -> Dict[str, str]:
    return dict(m.lineage)


def check_item(result, portfolio: dict, assertion: dict, item: dict, ids) -> List[Mismatch]:
    aid, kind, lab = assertion["id"], item["kind"], _label(item)
    out: List[Mismatch] = []

    def bad(field, expected, actual):
        out.append(Mismatch(aid, kind, lab, field, expected, actual))

    found = select(result, item, ids)
    if kind == "priced_holdings_value" and item.get("emitted") is False:
        partial = [m for m in found if m.partial]
        if partial:
            bad("emitted", False, True)
        return out
    if kind != "priced_holdings_value" and item.get("emitted") is False:  # part 2: no receivable exists on that date
        if found:
            bad("emitted", False, True)
        return out
    if len(found) != 1:
        bad("metric", "exactly one", len(found))
        return out
    m = found[0]
    tol = Decimal(item["tolerance"]) if item.get("tolerance") not in (None, "0") else None
    if m.result.sufficiency_state.value != item["state"]:
        bad("state", item["state"], m.result.sufficiency_state.value)
    actual_reason = None if m.result.reason_code is None else m.result.reason_code.value
    if actual_reason != item["reason"]:
        bad("reason", item["reason"], actual_reason)
    expected_value = None if item["value"] is None else Decimal(item["value"])
    if expected_value is None or m.result.value is None:
        if expected_value != m.result.value:
            bad("value", None if expected_value is None else str(expected_value), None if m.result.value is None else str(m.result.value))
    elif tol is None:
        if m.result.value != expected_value:
            bad("value", str(expected_value), str(m.result.value))
    elif abs(m.result.value - expected_value) > tol:
        bad(f"value (tolerance {tol})", str(expected_value), str(m.result.value))
    if item["exact"] is not None:
        expected_exact = Fraction(item["exact"])
        if m.exact != expected_exact:
            bad("exact", str(expected_exact), None if m.exact is None else str(m.exact))
    elif item["value"] is None and m.exact is not None:
        bad("exact", None, str(m.exact))
    if item["detail"] is not None and sorted(set(m.details)) != sorted(item["detail"]):
        bad("detail", sorted(item["detail"]), sorted(set(m.details)))
    if "window" in item:
        w, wm = item["window"], m.window
        for field, expected, actual in (("window.base", D(w["base"]), wm.start), ("window.end", D(w["end"]), wm.end), ("window.days", w["days"], wm.days)):
            if expected != actual:
                bad(field, str(expected), str(actual))
    lin = _lineage(m)
    for field, key in (("price_date_used", "price_date_used"), ("last_print_date", "last_print_date"), ("fx_fixing_date", "fx_date_used")):  # null asserts the lineage field is absent
        if field in item and lin.get(key) != item[field]:
            bad(field, item[field], lin.get(key))
    if "missed_sessions" in item and lin.get("price_missed_sessions") != str(item["missed_sessions"]):
        bad("missed_sessions", str(item["missed_sessions"]), lin.get("price_missed_sessions"))
    if "year_fraction" in item:
        yf = lin.get("year_fraction")
        if yf is None or Fraction(yf) != Fraction(item["year_fraction"]):
            bad("year_fraction", item["year_fraction"], yf)
    if "stale_share" in item:
        s = item["stale_share"]
        if m.stale_weight != Fraction(s["exact"]):
            bad("stale_share.exact", s["exact"], None if m.stale_weight is None else str(m.stale_weight))
        if m.stale_weight_presented != Decimal(s["value"]):
            bad("stale_share.value", s["value"], None if m.stale_weight_presented is None else str(m.stale_weight_presented))
    if "lineage_includes" in item:
        missing = sorted(set(item["lineage_includes"]) - set(m.details))
        if missing:
            bad("lineage_includes", sorted(item["lineage_includes"]), sorted(set(m.details)))
    if kind == "priced_holdings_value":
        if not m.partial:
            bad("partial", True, False)
        if "excluded_count" in item and item["excluded_count"] != len(m.excluded):
            bad("excluded_count", item["excluded_count"], len(m.excluded))
        if "excluded" in item:
            from performance.states import pick_reason  # noqa: PLC0415

            def key_of(component, account, ident, native, reason):
                return (component, account, ident, native, reason)

            want = {key_of(e["component"], str(ids(e["account_id"])), str(ids(e["listing_id"])) if "listing_id" in e else e["currency"], e["native"], e["reason"])
                    for e in item["excluded"]}
            have = set()
            for e in m.excluded:
                account, _, ident = e.ref.split(":", 1)[1].partition("/")
                have.add(key_of(e.kind.lower(), account, ident, e.native,
                                pick_reason([cz.reason for cz in e.causes if cz.state == "INSUFFICIENT_DATA"])))
            if want != have:
                bad("excluded", sorted(want), sorted(have))
    return out


def check_assertion(runner: Runner, portfolio: dict, assertion: dict) -> List[Mismatch]:
    out: List[Mismatch] = []
    for item in assertion["expect"]:
        if "window" in item:
            res = runner.window(portfolio, assertion, item["window"]["request"])
        else:
            res = runner.valuation(portfolio, assertion)
        out += check_item(res, portfolio, assertion, item, runner.ids)
    return out


def check_all(runner: Runner) -> Tuple[List[Mismatch], int]:
    mismatches: List[Mismatch] = []
    checked = 0
    for p in FIXTURE["portfolios"]:
        for a in p["assertions"]:
            mismatches += check_assertion(runner, p, a)
            checked += len(a["expect"])
    return mismatches, checked


def build_runner(ids=None, verify_identities: bool = False) -> Tuple[Runner, Market]:
    ids = ids or cp1.Ids(randomize=False)
    market = Market(ids)
    events = {p["name"]: portfolio_events(p, ids) for p in FIXTURE["portfolios"]}
    return Runner(market, ids, events, verify_identities), market


if __name__ == "__main__":  # a plain report of every mismatch, for the findings list
    runner, market = build_runner(verify_identities=True)
    print("market-data build issues:", market.issues)
    found, n = check_all(runner)
    print(f"{n} items checked, {len(found)} mismatches")
    for mm in found:
        print(mm)
