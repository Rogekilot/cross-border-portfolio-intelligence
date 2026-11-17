"""Download tool v0.2 (HUMAN-RUN ONLY; untested against the network).

Saves what a free source returns as an immutable file plus a lineage manifest under
`data/marketdata/` (override: FINWEB_MARKETDATA_DIR). The platform and its agents read those
files; they never run this tool (PD-0027 condition 2).

TERMS GATE (v0.2; PD-0031, PD-0032): before ANY request, `probe` and `fetch` read the committed registry
`SOURCES.json` and refuse every source whose recorded `terms_check` does not permit internal development
use (no check, a negative check, an unknown source and an unreadable registry all refuse). `probe` prints
`REFUSED (terms: PD-0031/PD-0032)` for such a step and makes no request; `fetch` raises a clear error and
exits 2. The terms gate does not apply to `register-file` (hashing a file the human made) or to `verify`
(offline re-hash). `register-file` IS human-only like every command except `verify`: it writes into the
store, so it refuses unless FINWEB_HUMAN_DOWNLOAD=1 and stdin is a terminal (`require_human`). Only the
offline, read-only `verify` has no guard.
New route `fetch --source ecb_eurofxref`: the ECB's own `eurofxref-hist` file (the preferred FX source,
market-data/1.2 Ruling 1.1a); it is refused until the owner adds and attests `ecb.eurofxref`.

SYMBOL FORM (review M-1): a file filed under `alphavantage.us` must name US symbols. `fetch --source alphavantage_us` refuses a
mainland or Hong Kong form (`609999.SHH`, `000001.SHZ`, `0700.HK`, a bare six-digit code) before the key is read and before any
request, and `save_file` refuses the same for any file written under that source, including `register-file`. There is no A-share
fetch route: that source is pending observation (market-data/1.15 Ruling 7A.3) and the ingest gate refuses its real files anyway.

Run from the repository root, in the download environment (PD-0029):

    export FINWEB_HUMAN_DOWNLOAD=1
    PYTHONPATH=src .venv-download/bin/python -m marketdata_tools.download probe
    PYTHONPATH=src .venv-download/bin/python -m marketdata_tools.download fetch \\
        --source akshare_cn --symbol 600519 --start 2025-01-02 --end 2025-01-08 \\
        --adjust raw --currency CNY
    PYTHONPATH=src .venv-download/bin/python -m marketdata_tools.download verify

Guards (a speed bump, not a security control): network commands refuse unless
FINWEB_HUMAN_DOWNLOAD=1 and stdin is a terminal. The sandbox has no network anyway.

Keys come ONLY from the environment (FINWEB_ALPHAVANTAGE_KEY, FINWEB_OPENFIGI_KEY), never from
an argument or a file, are never printed, and never reach a manifest (`request` is an explicit
whitelist). Error reporting: for a call whose URL and arguments carry no key the exception
class, a sanitized message and the HTTP status are reported; for a key-bearing call (Alpha
Vantage; OpenFIGI when a key is set) only the exception class is.

A response that is empty, or that carries a source-side warning or error, is a FAILURE and
nothing is saved. Every OK line states the rows and date range actually returned.

Vendor libraries (akshare, baostock) are imported lazily. Function names and columns come from
akshare 1.19.1's source and from memory of the other APIs: unverified until a human runs them.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import importlib
import importlib.metadata
import io
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Mapping, Optional, Sequence, Tuple

from domain.currency import CurrencyCode
from marketdata.canonical import sha256_hex
from marketdata.contracts import AdjustmentStatus, DataDelayStatus, UsageScope
from marketdata.files import FileHashMismatchError, FileStore
from marketdata.manifest import (
    DataKind,
    FileManifest,
    ManifestError,
    SourceRegistry,
    UnknownSourceError,
)

TOOL_NAME = "marketdata_tools.download"
TOOL_VERSION = "0.2.0"
USER_AGENT = f"finweb-marketdata-tools/{TOOL_VERSION} (internal development; human-run)"
HUMAN_ENV = "FINWEB_HUMAN_DOWNLOAD"
KEY_ENVS = ("FINWEB_ALPHAVANTAGE_KEY", "FINWEB_OPENFIGI_KEY")
GROUP_HINT = (
    "Install the optional download group in its own environment (PD-0029): "
    "UV_PROJECT_ENVIRONMENT=.venv-download uv sync --group marketdata-download"
)
BAOSTOCK_HINT = (
    "BaoStock uses its own TCP service (not HTTP); that server may be unreachable from some "
    "networks, proxies or VPNs. Try another network before assuming a code problem."
)
_TIMEOUT_SECONDS = 60
_DATE_COLUMNS = ("日期", "date", "Date", "timestamp")

# Download-time terms gate (PD-0031, PD-0032). The tool makes NO request for a source whose
# SOURCES.json `terms_check` does not permit internal development use. The gate reads only the
# committed registry; it never decides a verdict, it applies the owner's recorded one.
TERMS_REFUSED = "REFUSED (terms: PD-0031/PD-0032)"
FETCH_SOURCE_IDS = {
    "akshare_cn": "akshare.cn", "akshare_hk": "akshare.hk", "akshare_us": "akshare.us",
    "akshare_sina_cn": "akshare_sina.cn", "akshare_sina_hk": "akshare_sina.hk",
    "akshare_sina_us": "akshare_sina.us", "baostock_cn": "baostock.cn", "alphavantage_us": "alphavantage.us",
    "frankfurter_fx": "frankfurter.ecb", "openfigi": "openfigi", "ecb_eurofxref": "ecb.eurofxref",
}
Gate = Callable[[Optional[str]], Optional[str]]  # source id -> None (permitted) or the reason for refusing

# The symbol forms of the US route of Alpha Vantage. A US ticker is a letter, then up to five letters or digits, then at most one
# class letter after a full stop or a hyphen (`AAPL`, `BRK.B`, `BF-B`). Anything else is another market's form: a six-digit
# mainland code (`609999`), a code with an exchange suffix (`609999.SHH`, `000001.SHZ`, `0700.HK`), a multi-letter suffix.
# The file would be saved under `alphavantage.us`, and a vendor-id row that someone entered for it would then bind a real A-share or
# Hong Kong price to the US source (market-data/1.15 Ruling 7A.3: the A-share route is pending observation and has no fetch route).
_US_SYMBOL = re.compile(r"[A-Z][A-Z0-9]{0,5}(?:[.-][A-Z])?", re.ASCII | re.IGNORECASE)
US_SOURCE_ID = "alphavantage.us"


def us_symbol_refusal(symbols: Sequence[str], market: Optional[str] = "US") -> Optional[str]:
    """None if every symbol is of the US form (and any declared market is US), else the reason the US source refuses it."""
    for symbol in symbols:
        if _US_SYMBOL.fullmatch(symbol) is None:
            return (f"{symbol!r} is not a US symbol form (a mainland or Hong Kong code, or an exchange suffix such as .SHH, .SHZ or "
                    f".HK): {US_SOURCE_ID} supplies US listings only, and the A-share route is pending observation with no fetch route")
    if market not in (None, "US"):
        return f"market {market!r} is not US: {US_SOURCE_ID} supplies US listings only"
    return None


class HumanOnlyError(PermissionError):
    pass


class TermsRefusedError(PermissionError):
    """The source's recorded terms check does not permit internal development use: nothing is fetched."""


def terms_refusal(registry: Optional[SourceRegistry], source_id: Optional[str]) -> Optional[str]:
    """None if the registry records a terms check that PERMITS internal development use for the source;
    otherwise the reason it is refused. Fails closed: an unreadable registry, an unknown source and a
    missing or negative check all refuse."""
    if registry is None:
        return "the source registry could not be read, so every source is refused (fail closed)"
    if source_id is None:
        return "the step names no source, so no terms check can be made"
    try:
        record = registry.get(source_id)
    except UnknownSourceError:
        return f"{source_id} is not in SOURCES.json: the owner must add and attest it first"
    if record.terms_check is None:
        return f"{source_id} has no terms check in SOURCES.json (not attested)"
    if not record.terms_check.permits_internal_development_use:
        return f"{source_id}: the recorded terms check does not permit internal development use"
    return None


def make_gate(root: Path) -> Gate:
    """The registry gate for a data directory. The registry is read once, here."""
    try:
        registry: Optional[SourceRegistry] = FileStore(root).load_registry()
    except (ManifestError, OSError, ValueError):
        registry = None
    return lambda source_id: terms_refusal(registry, source_id)


class ToolDependencyError(RuntimeError):
    pass


class FetchError(RuntimeError):
    pass


class SkipStep(RuntimeError):
    """A probe step that cannot run for a stated, non-failure reason (for example no key set)."""


def require_human(environ: Mapping[str, str], stdin_is_tty: bool) -> None:
    """Refuse unless a human at a terminal opted in. Not a security control."""
    if environ.get(HUMAN_ENV) != "1" or not stdin_is_tty:
        raise HumanOnlyError(
            f"refusing to run: this tool is human-only. Set {HUMAN_ENV}=1 in your own "
            "terminal and run it there; agents never run it (PD-0027)."
        )


def import_vendor(module: str) -> object:
    """Lazy vendor import with a clear message when the optional group is missing."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise ToolDependencyError(
            f"the vendor library {module!r} is not installed. {GROUP_HINT}"
        ) from exc


def data_dir(environ: Mapping[str, str]) -> Path:
    override = environ.get("FINWEB_MARKETDATA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "marketdata"


def sanitize(text: str, secrets: Sequence[str] = (), limit: int = 300) -> str:
    """One line, secrets masked, bounded. Used only on messages of key-free calls."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit] + "..."


def _secrets(environ: Mapping[str, str]) -> List[str]:
    return [environ[k] for k in KEY_ENVS if environ.get(k)]


def describe_exception(exc: BaseException, key_bearing: bool, secrets: Sequence[str] = ()) -> str:
    """Key-free call: class, sanitized message, HTTP status if any. Key-bearing: class only."""
    if key_bearing:
        return f"{type(exc).__name__} (details withheld: the request carries a key)"
    status = getattr(exc, "code", None) if isinstance(exc, urllib.error.HTTPError) else None
    text = f"{type(exc).__name__}: {sanitize(str(exc), secrets)}"
    return f"{text} [HTTP {status}]" if status is not None else text


def _libraries(names: Sequence[str]) -> Tuple[Tuple[str, str], ...]:
    found = []
    for name in names:
        try:
            found.append((name, importlib.metadata.version(name)))
        except importlib.metadata.PackageNotFoundError:
            pass
    return tuple(found)


def _read_key(environ: Mapping[str, str], name: str, required: bool) -> Optional[str]:
    value = environ.get(name)
    if required and not value:
        raise FetchError(f"set {name} in your own terminal environment (never in a file)")
    return value or None


def _safe_label(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "file"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


@dataclass(frozen=True)
class Fetched:
    """What a fetch function returns: the raw bytes plus facts for the manifest. `request`
    is a WHITELIST (no key, no header, no URL carrying one)."""

    payload: bytes
    ext: str
    payload_format: str
    source_id: str
    data_kind: DataKind
    request: Tuple[Tuple[str, str], ...]
    declared_adjustment: AdjustmentStatus
    adjustment_anchor: Optional[str]
    declared_currency: Optional[CurrencyCode]
    market: Optional[str]
    source_identifiers: Tuple[str, ...]
    libraries: Tuple[Tuple[str, str], ...]
    label: str
    declared_delay: DataDelayStatus = DataDelayStatus.END_OF_DAY


# --- response checks: nothing empty or warned about is ever saved ------------------------

def check_fetched(fetched: Fetched) -> Tuple[int, Optional[str], Optional[str]]:
    """Return (rows, first date, last date) actually present, or raise FetchError if the
    response is empty or carries a source-side warning/error."""
    text = fetched.payload.decode("utf-8", "replace")
    if fetched.data_kind is DataKind.IDENTITY:
        try:
            items = json.loads(text)
        except ValueError:
            raise FetchError(f"{fetched.source_id}: response is not JSON") from None
        if not isinstance(items, list) or not items:
            raise FetchError(f"{fetched.source_id}: unexpected or empty response")
        matched = 0
        for item in items:
            if not isinstance(item, dict):
                raise FetchError(f"{fetched.source_id}: unexpected item in response")
            message = item.get("warning") or item.get("error")
            if message:
                raise FetchError(f"{fetched.source_id}: {sanitize(str(message))}")
            if not item.get("data"):
                raise FetchError(f"{fetched.source_id}: an item carries no data")
            matched += len(item["data"])
        return matched, None, None
    if fetched.ext == "json":
        try:
            rates = json.loads(text).get("rates")
        except (ValueError, AttributeError):
            raise FetchError(f"{fetched.source_id}: response is not the expected JSON") from None
        if not rates:
            raise FetchError(f"{fetched.source_id}: no rates returned")
        days = sorted(rates)
        return len(days), days[0], days[-1]
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        raise FetchError(f"{fetched.source_id}: no data rows returned (header only or empty)")
    header, body = rows[0], [r for r in rows[1:] if r]
    index = next((i for i, h in enumerate(header) if h.strip() in _DATE_COLUMNS), None)
    if index is None:
        return len(body), None, None
    days = sorted(r[index] for r in body)
    return len(body), days[0], days[-1]


def save_file(root: Path, fetched: Fetched, retrieval_time: datetime.datetime,
              script_sha256: Optional[str] = None,
              retrieved_by: str = "human",
              usage_scope: UsageScope = UsageScope.INTERNAL_DEVELOPMENT_ONLY) -> Tuple[Path, FileManifest]:
    """Write the payload (exclusive create, then read-only) and its manifest. Never
    overwrites: an existing file of the same name is an error, not a replacement. Every file the tool writes, fetched or
    registered by hand, passes here: a file filed under the US Alpha Vantage source must name US symbols (`us_symbol_refusal`)."""
    if fetched.source_id == US_SOURCE_ID:
        refusal = us_symbol_refusal(fetched.source_identifiers, fetched.market)
        if refusal is not None:
            raise FetchError(f"nothing saved: {refusal}")
    directory = (root / "files" / fetched.source_id / fetched.data_kind.value.lower()
                 / retrieval_time.strftime("%Y-%m-%d"))
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{_safe_label(fetched.label)}.{fetched.ext}"
    payload_path = directory / name
    manifest = FileManifest(
        file_sha256=sha256_hex(fetched.payload),
        size_bytes=len(fetched.payload),
        payload_filename=name,
        payload_format=fetched.payload_format,
        source_id=fetched.source_id,
        data_kind=fetched.data_kind,
        market=fetched.market,
        retrieval_time=retrieval_time,
        retrieved_by=retrieved_by,
        request=fetched.request,
        declared_adjustment=fetched.declared_adjustment,
        adjustment_anchor=fetched.adjustment_anchor,
        declared_currency=fetched.declared_currency,
        declared_delay=fetched.declared_delay,
        source_identifiers=fetched.source_identifiers,
        script_name=TOOL_NAME,
        script_version=TOOL_VERSION,
        script_sha256=script_sha256,
        libraries=fetched.libraries,
        usage_scope=usage_scope,
    )
    with open(payload_path, "xb") as handle:  # exclusive create: refuses to overwrite
        handle.write(fetched.payload)
    os.chmod(payload_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    manifest_path = payload_path.with_name(name + ".manifest.json")
    with open(manifest_path, "x", encoding="utf-8") as handle:
        handle.write(manifest.to_json())
    os.chmod(manifest_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return payload_path, manifest


# --- fetchers (each thin: call the source, keep the raw bytes) ----------------------------

def _ymd(day: str) -> str:
    return day.replace("-", "")


def _http(request: urllib.request.Request, what: str, key_bearing: bool = False,
          secrets: Sequence[str] = ()) -> bytes:
    """One HTTP call with an explicit User-Agent. Key-free: class, message and HTTP status
    (and a short body snippet) are reported. Key-bearing: the class only."""
    if not request.has_header("User-agent"):
        request.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.read()
    except urllib.error.HTTPError as exc:
        if key_bearing:
            raise FetchError(f"{what}: request failed ({type(exc).__name__})") from None
        try:
            body = sanitize(exc.read(300).decode("utf-8", "replace"), secrets, 200)
        except Exception:
            body = ""
        raise FetchError(
            f"{what}: HTTP {exc.code} {sanitize(str(exc.reason), secrets, 100)}"
            + (f"; body: {body}" if body else "")
        ) from None
    except Exception as exc:  # the URL may carry a key for a key-bearing call
        raise FetchError(f"{what}: {describe_exception(exc, key_bearing, secrets)}") from None


def _adjust_fields(adjust: str, raw_label: str) -> Tuple[AdjustmentStatus, Optional[str]]:
    """`raw` is declared RAW. An adjusted pull is UNDECLARED with the call's own label as
    the anchor: what that adjustment covers is for the verification rule to establish."""
    if adjust == "raw":
        return AdjustmentStatus.RAW, None
    return AdjustmentStatus.UNDECLARED, f"{raw_label} adjust={adjust}"


def fetch_akshare(market: str, symbol: str, start: str, end: str, adjust: str,
                  currency: CurrencyCode) -> Fetched:
    """Eastmoney-backed AKShare (stock_zh_a_hist / stock_hk_hist / stock_us_hist), which take
    start_date/end_date as YYYYMMDD."""
    ak = import_vendor("akshare")
    flag = {"raw": "", "qfq": "qfq", "hfq": "hfq"}[adjust]
    func = {"cn": "stock_zh_a_hist", "hk": "stock_hk_hist", "us": "stock_us_hist"}[market]
    frame = getattr(ak, func)(symbol=symbol, period="daily", start_date=_ymd(start),
                              end_date=_ymd(end), adjust=flag)
    status, anchor = _adjust_fields(adjust, f"akshare.{func}")
    return Fetched(
        payload=frame.to_csv(index=False).encode("utf-8"), ext="csv",
        payload_format=f"akshare_csv_{market}_daily/1", source_id=f"akshare.{market}",
        data_kind=DataKind.QUOTE,
        request=(("function", func), ("symbol", symbol), ("start", start), ("end", end),
                 ("adjust", adjust)),
        declared_adjustment=status, adjustment_anchor=anchor, declared_currency=currency,
        market=market.upper(), source_identifiers=(symbol,), libraries=_libraries(["akshare"]),
        label=f"{symbol}_{start}_{end}_{adjust}",
    )


def _filter_csv_by_date(text: str, start: str, end: str) -> str:
    """Keep rows whose `date` column lies in [start, end] (ISO strings). This is the ONLY
    change the tool makes to a payload, and it is declared in the manifest request."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return text
    header = rows[0]
    index = next((i for i, h in enumerate(header) if h.strip() in _DATE_COLUMNS), None)
    if index is None:
        raise FetchError("no date column to filter on")
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    for row in rows[1:]:
        if row and start <= row[index][:10] <= end:
            writer.writerow(row)
    return out.getvalue()


def fetch_akshare_sina(market: str, symbol: str, start: str, end: str, adjust: str,
                       currency: CurrencyCode) -> Fetched:
    """Sina-backed AKShare (stock_hk_daily / stock_us_daily; akshare 1.19.1 source). These take
    no date arguments and return the whole history, so rows are filtered to [start, end] here.
    A DIFFERENT upstream from the Eastmoney functions (independence group `sina`)."""
    ak = import_vendor("akshare")
    func = {"cn": "stock_zh_a_daily", "hk": "stock_hk_daily", "us": "stock_us_daily"}[market]
    flag = {"raw": "", "qfq": "qfq", "hfq": "hfq"}[adjust]
    if market == "cn":
        # akshare 1.19.1 `stock_zh_a_daily(symbol="sh600519", start_date, end_date, adjust)`: Sina
        # upstream; the raw branch rounds prices to 2 decimals and drops duplicate rows itself.
        frame = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust=flag)
    else:
        frame = getattr(ak, func)(symbol=symbol, adjust=flag)
    text = _filter_csv_by_date(frame.to_csv(index=False), start, end)
    status, anchor = _adjust_fields(adjust, f"akshare.{func}")
    return Fetched(
        payload=text.encode("utf-8"), ext="csv",
        payload_format=f"akshare_sina_csv_{market}_daily/1", source_id=f"akshare_sina.{market}",
        data_kind=DataKind.QUOTE,
        request=(("function", func), ("symbol", symbol), ("start", start), ("end", end),
                 ("adjust", adjust), ("row_filter", "date in [start, end] applied by the tool")),
        declared_adjustment=status, adjustment_anchor=anchor, declared_currency=currency,
        market=market.upper(), source_identifiers=(symbol,), libraries=_libraries(["akshare"]),
        label=f"{symbol}_{start}_{end}_{adjust}",
    )


def fetch_baostock(symbol: str, start: str, end: str, adjust: str,
                   currency: CurrencyCode) -> Fetched:
    bs = import_vendor("baostock")
    flag = {"raw": "3", "hfq": "1", "qfq": "2"}[adjust]  # BaoStock: 1 backward, 2 forward, 3 none
    login = bs.login()  # type: ignore[attr-defined]
    if getattr(login, "error_code", "0") != "0":
        raise FetchError(
            f"baostock login failed: error_code={getattr(login, 'error_code', '?')} "
            f"error_msg={sanitize(str(getattr(login, 'error_msg', '?')))}. {BAOSTOCK_HINT}"
        )
    try:
        result = bs.query_history_k_data_plus(  # type: ignore[attr-defined]
            symbol, "date,code,open,high,low,close,volume", start_date=start, end_date=end,
            frequency="d", adjustflag=flag)
        if getattr(result, "error_code", "0") != "0":
            raise FetchError(
                f"baostock query failed: error_code={result.error_code} "
                f"error_msg={sanitize(str(result.error_msg))}. {BAOSTOCK_HINT}"
            )
        frame = result.get_data()
    finally:
        bs.logout()  # type: ignore[attr-defined]
    status, anchor = _adjust_fields(adjust, f"baostock adjustflag={flag}")
    return Fetched(
        payload=frame.to_csv(index=False).encode("utf-8"), ext="csv",
        payload_format="baostock_csv_cn_daily/1", source_id="baostock.cn",
        data_kind=DataKind.QUOTE,
        request=(("function", "query_history_k_data_plus"), ("symbol", symbol),
                 ("start", start), ("end", end), ("adjustflag", flag)),
        declared_adjustment=status, adjustment_anchor=anchor, declared_currency=currency,
        market="CN", source_identifiers=(symbol,), libraries=_libraries(["baostock"]),
        label=f"{symbol}_{start}_{end}_{adjust}",
    )


def fetch_alphavantage(symbol: str, currency: CurrencyCode, environ: Mapping[str, str]) -> Fetched:
    refusal = us_symbol_refusal((symbol,))
    if refusal is not None:  # before the key is read and before any request: no quota is spent on a file that could not be filed here
        raise FetchError(refusal)
    key = _read_key(environ, "FINWEB_ALPHAVANTAGE_KEY", required=True)
    query = urllib.parse.urlencode({"function": "TIME_SERIES_DAILY", "symbol": symbol,
                                    "outputsize": "compact", "datatype": "csv", "apikey": key})
    payload = _http(urllib.request.Request(f"https://www.alphavantage.co/query?{query}"),
                    "alphavantage", key_bearing=True)
    if payload.lstrip().startswith(b"{"):
        raise FetchError("alphavantage returned a JSON message (limit or error); nothing saved")
    return Fetched(
        payload=payload, ext="csv", payload_format="alphavantage_csv_daily/1",
        source_id="alphavantage.us", data_kind=DataKind.QUOTE,
        request=(("function", "TIME_SERIES_DAILY"), ("symbol", symbol), ("outputsize", "compact")),
        declared_adjustment=AdjustmentStatus.UNDECLARED,
        adjustment_anchor="TIME_SERIES_DAILY as returned; label unverified",
        declared_currency=currency, market="US", source_identifiers=(symbol,), libraries=(),
        label=f"{symbol}_compact",
    )


# Candidate Frankfurter bases, tried in order. The first is the host/prefix I believe is current
# (UNVERIFIED); the second is the older host. The base that answered is recorded in `request`.
FRANKFURTER_BASES = ("https://api.frankfurter.dev/v1", "https://api.frankfurter.app")


def fetch_frankfurter(start: str, end: str, symbols: Sequence[str]) -> Fetched:
    """EUR-based quotes only (market-data/1.0 Ruling 1.3: never a re-based quote). Date range
    syntax `/{start}..{end}?base=EUR&symbols=...` (UNVERIFIED for the current API)."""
    query = urllib.parse.urlencode({"base": "EUR", "symbols": ",".join(symbols)})
    failures: List[str] = []
    for base in FRANKFURTER_BASES:
        try:
            payload = _http(urllib.request.Request(f"{base}/{start}..{end}?{query}"), "frankfurter")
        except FetchError as exc:
            failures.append(f"{base}: {exc}")
            continue
        return Fetched(
            payload=payload, ext="json", payload_format="frankfurter_json_timeseries/1",
            source_id="frankfurter.ecb", data_kind=DataKind.FX,
            request=(("base", "EUR"), ("symbols", ",".join(symbols)), ("start", start),
                     ("end", end), ("endpoint", base)),
            declared_adjustment=AdjustmentStatus.RAW, adjustment_anchor=None,
            declared_currency=None, market=None, source_identifiers=tuple(symbols), libraries=(),
            label=f"EUR_{start}_{end}",
        )
    raise FetchError("frankfurter: every endpoint failed: " + " | ".join(failures))


# The ECB's OWN euro reference-rate history (market-data/1.2 Ruling 1.1a: the preferred FX source). The
# file name and location are RECALLED, not verified (UNVERIFIED): the CSV is tried first, then the ZIP
# that holds the same CSV. The endpoint that answered is recorded in `request`.
ECB_EUROFXREF_URLS = (
    "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv",
    "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip",
)


def fetch_ecb_eurofxref(start: str, end: str, symbols: Sequence[str]) -> Fetched:
    """Save the ECB's own `eurofxref-hist` CSV exactly as published (a ZIP container is unpacked: its single
    CSV member is saved byte for byte). The file holds the whole history; `start`, `end` and `symbols` are
    recorded as the READ WINDOW the adapter translates (declared in the manifest request), not as a filter
    on the saved bytes."""
    failures: List[str] = []
    for url in ECB_EUROFXREF_URLS:
        try:
            payload = _http(urllib.request.Request(url), "ecb.eurofxref")
        except FetchError as exc:
            failures.append(f"{url}: {exc}")
            continue
        if payload[:2] == b"PK":  # a ZIP container around the same CSV
            import zipfile  # stdlib; imported lazily so the module import stays minimal
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
                if len(members) != 1:
                    failures.append(f"{url}: expected exactly one CSV member, found {members}")
                    continue
                payload = archive.read(members[0])
        if not payload.lstrip().startswith(b"Date"):
            failures.append(f"{url}: the response does not start with a Date header")
            continue
        return Fetched(
            payload=payload, ext="csv", payload_format="ecb_eurofxref_hist_csv/1",
            source_id="ecb.eurofxref", data_kind=DataKind.FX,
            request=(("file", "eurofxref-hist"), ("endpoint", url), ("read_start", start), ("read_end", end),
                     ("symbols", ",".join(symbols))),
            declared_adjustment=AdjustmentStatus.RAW, adjustment_anchor=None,
            declared_currency=None, market=None, source_identifiers=tuple(symbols), libraries=(),
            label="eurofxref-hist",
        )
    raise FetchError("ecb.eurofxref: every endpoint failed: " + " | ".join(failures))


def fetch_openfigi(ticker: str, environ: Mapping[str, str], exch_code: Optional[str] = None,
                   mic: str = "", sec_des: str = "Equity") -> Fetched:
    """OpenFIGI v3 mapping job. The first probe sent `micCode: XNAS` for AAPL and got
    `No identifier found.` I now send `exchCode` (default "US", the Bloomberg composite code
    that OpenFIGI's own examples use) and `marketSecDes`, and only add `micCode` when asked.
    BASIS: my memory of the OpenFIGI v3 documentation (fields idType, idValue, exchCode,
    micCode, marketSecDes, ...): UNVERIFIED; a warning or error in the answer now fails."""
    key = _read_key(environ, "FINWEB_OPENFIGI_KEY", required=False)
    # PD-0033 §3: a micCode query sends micCode ONLY (no exchCode) unless exchCode is given explicitly.
    # With neither, the default exchCode "US" applies.
    if exch_code is None and not mic:
        exch_code = "US"
    job = {"idType": "TICKER", "idValue": ticker}
    if exch_code:
        job["exchCode"] = exch_code
    job["marketSecDes"] = sec_des
    if mic:
        job["micCode"] = mic
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-OPENFIGI-APIKEY"] = key
    payload = _http(urllib.request.Request(
        "https://api.openfigi.com/v3/mapping", data=json.dumps([job]).encode("utf-8"),
        headers=headers, method="POST"), "openfigi", key_bearing=bool(key), secrets=_secrets(environ))
    request = tuple((k, v) for k, v in job.items())
    return Fetched(
        payload=payload, ext="json", payload_format="openfigi_json_mapping/1",
        source_id="openfigi", data_kind=DataKind.IDENTITY, request=request,
        declared_adjustment=AdjustmentStatus.RAW, adjustment_anchor=None,
        declared_currency=None, market=None, source_identifiers=(ticker,), libraries=(),
        label=f"{ticker}{'_' + exch_code if exch_code else ''}{'_' + mic if mic else ''}", declared_delay=DataDelayStatus.UNKNOWN,
    )


# --- probe plan: tiny first run to learn real response shapes ----------------------------

PROBE_START, PROBE_END = "2025-01-02", "2025-01-08"


@dataclass(frozen=True)
class ProbeTarget:
    """Where a step will save, so an existing file can be detected BEFORE any request."""

    source_id: str
    kind: DataKind
    label: str
    ext: str


@dataclass(frozen=True)
class ProbeStep:
    name: str
    run: Callable[[], Fetched]
    key_bearing: bool = False
    target: Optional[ProbeTarget] = None
    eastmoney: bool = False  # polite handling and the throttling hint
    skip_reason: Optional[str] = None  # known before any request, so no pause is spent on it


PROBE_PAUSE_SECONDS = 3.0  # between steps that made a request: one request per step, no retries
THROTTLE_HINT = (
    "RemoteDisconnected / ConnectionError from an Eastmoney step after an earlier success usually "
    "means the upstream is throttling or blocking this network. Wait (an hour or more) before "
    "trying again; the tool makes ONE request per step and never retries."
)


def expected_path(root: Path, target: ProbeTarget, when: datetime.datetime) -> Path:
    return (root / "files" / target.source_id / target.kind.value.lower()
            / when.strftime("%Y-%m-%d") / f"{_safe_label(target.label)}.{target.ext}")


def _needs_key(environ: Mapping[str, str], name: str, run: Callable[[], Fetched]) -> Callable[[], Fetched]:
    def go() -> Fetched:
        if not environ.get(name):
            raise SkipStep(f"{name} is not set")
        return run()
    return go


def probe_steps(environ: Mapping[str, str]) -> List[ProbeStep]:
    cny, hkd, usd = CurrencyCode("CNY"), CurrencyCode("HKD"), CurrencyCode("USD")
    s, e = PROBE_START, PROBE_END
    has_figi_key = bool(environ.get("FINWEB_OPENFIGI_KEY"))
    Q, F, I = DataKind.QUOTE, DataKind.FX, DataKind.IDENTITY

    def quote(source, symbol, adjust):
        return ProbeTarget(source, Q, f"{symbol}_{s}_{e}_{adjust}", "csv")

    return [
        ProbeStep("akshare.cn raw (eastmoney)", lambda: fetch_akshare("cn", "600519", s, e, "raw", cny),
                  target=quote("akshare.cn", "600519", "raw"), eastmoney=True),
        ProbeStep("akshare.cn qfq (eastmoney)", lambda: fetch_akshare("cn", "600519", s, e, "qfq", cny),
                  target=quote("akshare.cn", "600519", "qfq"), eastmoney=True),
        ProbeStep("akshare.hk raw (eastmoney)", lambda: fetch_akshare("hk", "00700", s, e, "raw", hkd),
                  target=quote("akshare.hk", "00700", "raw"), eastmoney=True),
        ProbeStep("akshare.us raw (eastmoney)", lambda: fetch_akshare("us", "105.AAPL", s, e, "raw", usd),
                  target=quote("akshare.us", "105.AAPL", "raw"), eastmoney=True),
        ProbeStep("akshare_sina.cn raw", lambda: fetch_akshare_sina("cn", "sh600519", s, e, "raw", cny),
                  target=quote("akshare_sina.cn", "sh600519", "raw")),
        ProbeStep("akshare_sina.hk raw", lambda: fetch_akshare_sina("hk", "00700", s, e, "raw", hkd),
                  target=quote("akshare_sina.hk", "00700", "raw")),
        ProbeStep("akshare_sina.us raw", lambda: fetch_akshare_sina("us", "AAPL", s, e, "raw", usd),
                  target=quote("akshare_sina.us", "AAPL", "raw")),
        ProbeStep("baostock.cn raw", lambda: fetch_baostock("sh.600519", s, e, "raw", cny),
                  target=quote("baostock.cn", "sh.600519", "raw")),
        ProbeStep("alphavantage.us", _needs_key(environ, "FINWEB_ALPHAVANTAGE_KEY",
                                                 lambda: fetch_alphavantage("AAPL", usd, environ)), True,
                  target=ProbeTarget("alphavantage.us", Q, "AAPL_compact", "csv"),
                  skip_reason=None if environ.get("FINWEB_ALPHAVANTAGE_KEY")
                  else "FINWEB_ALPHAVANTAGE_KEY is not set"),
        ProbeStep("frankfurter fx", lambda: fetch_frankfurter(s, e, ("USD", "HKD", "CNY")),
                  target=ProbeTarget("frankfurter.ecb", F, f"EUR_{s}_{e}", "json")),
        ProbeStep("openfigi AAPL exchCode=US", lambda: fetch_openfigi("AAPL", environ), has_figi_key,
                  target=ProbeTarget("openfigi", I, "AAPL_US", "json")),
        ProbeStep("openfigi 700 exchCode=HK", lambda: fetch_openfigi("700", environ, "HK"), has_figi_key,
                  target=ProbeTarget("openfigi", I, "700_HK", "json")),
    ]


def _throttle_suffix(step: ProbeStep, message: str) -> str:
    low = message.lower()
    if step.eastmoney and ("remotedisconnected" in low or "connectionerror" in low or "connection aborted" in low):
        return f" HINT: {THROTTLE_HINT}"
    return ""


def run_probe(environ: Mapping[str, str], root: Path,
              sleep: Callable[[float], None] = time.sleep, gate: Optional[Gate] = None) -> int:
    """One request per step, no retries. A step whose output file already exists for today is
    reported EXISTS and makes no request. A pause separates steps that did make a request.

    TERMS GATE (PD-0031/PD-0032): a step whose source's recorded terms check does not permit internal
    development use is reported `REFUSED (terms: PD-0031/PD-0032)` BEFORE anything else (a missing key,
    an existing file): it makes no request and does not count as a failure. `gate` is injectable for
    tests; the default reads SOURCES.json under `root`."""
    failures = 0
    gate = gate or make_gate(root)
    script_hash = sha256_hex(Path(__file__).read_bytes())
    secrets = _secrets(environ)
    requested_before = False
    for step in probe_steps(environ):
        refusal = gate(step.target.source_id if step.target is not None else None)
        if refusal is not None:
            print(f"{TERMS_REFUSED} {step.name}: {refusal}")
            continue
        if step.skip_reason:
            print(f"SKIP  {step.name}: {step.skip_reason}")
            continue
        if step.target is not None:
            existing = expected_path(root, step.target, _now())
            if existing.exists():
                print(f"EXISTS {step.name}: {existing} (not fetched again)")
                continue
        if requested_before:
            sleep(PROBE_PAUSE_SECONDS)
        try:
            fetched = step.run()
            requested_before = True
            rows, first, last = check_fetched(fetched)
            path, manifest = save_file(root, fetched, _now(), script_hash)
            span = f" range={first}..{last}" if first else ""
            print(f"OK    {step.name}: rows={rows}{span} (requested {PROBE_START}..{PROBE_END}) "
                  f"{path} sha256={manifest.file_sha256[:12]}")
        except SkipStep as exc:
            print(f"SKIP  {step.name}: {exc}")
        except (FetchError, ToolDependencyError, FileExistsError, KeyError) as exc:
            requested_before = True
            failures += 1
            message = sanitize(str(exc), secrets, 600)
            print(f"FAIL  {step.name}: {type(exc).__name__}: {message}{_throttle_suffix(step, message)}")
        except Exception as exc:  # a vendor library can raise anything
            requested_before = True
            failures += 1
            message = describe_exception(exc, step.key_bearing, secrets)
            print(f"FAIL  {step.name}: {message}{_throttle_suffix(step, message)}")
    return 1 if failures else 0


def run_verify(root: Path) -> int:
    store = FileStore(root)
    bad = 0
    paths = store.manifest_paths()
    for path in paths:
        try:
            store.read_verified(path)
            print(f"OK    {path}")
        except (FileHashMismatchError, ValueError, LookupError) as exc:
            bad += 1
            print(f"FAIL  {path}: {exc}")
    print(f"{len(paths)} file(s) checked, {bad} failed")
    return 1 if bad else 0


def run_register(args: argparse.Namespace, root: Path) -> int:
    """`register-file`: hash and describe a file the human made, into the store. HUMAN-ONLY (`main` calls `require_human` first); no terms check, because nothing is fetched."""
    payload = Path(args.path).read_bytes()
    identifiers = tuple(s for s in args.identifiers.split(",") if s) if args.identifiers else ()
    fetched = Fetched(
        payload=payload, ext=args.ext, payload_format=args.format, source_id=args.source,
        data_kind=DataKind(args.kind), request=(("origin", "hand-made file"),),
        declared_adjustment=AdjustmentStatus(args.adjustment), adjustment_anchor=None,
        declared_currency=CurrencyCode(args.currency) if args.currency else None,
        market=args.market, source_identifiers=identifiers, libraries=(), label=args.label,
        declared_delay=DataDelayStatus.UNKNOWN,
    )
    path, manifest = save_file(root, fetched, _now(), sha256_hex(Path(__file__).read_bytes()))
    print(f"registered {path} sha256={manifest.file_sha256}")
    return 0


def run_fetch(args: argparse.Namespace, environ: Mapping[str, str], root: Path,
              gate: Optional[Gate] = None) -> int:
    # TERMS GATE first: nothing below runs, and no request is made, for a refused source.
    refusal = (gate or make_gate(root))(FETCH_SOURCE_IDS.get(args.source))
    if args.source in FETCH_SOURCE_IDS and refusal is not None:
        raise TermsRefusedError(f"{TERMS_REFUSED} {args.source}: {refusal}")
    ccy = CurrencyCode(args.currency) if args.currency else None
    price_sources = ("akshare_", "akshare.", "baostock_", "alphavantage_")
    if args.source.startswith(price_sources) and ccy is None:
        raise FetchError("--currency is required for price sources (an adapter never infers it)")
    if args.source in ("akshare_cn", "akshare_hk", "akshare_us"):
        fetched = fetch_akshare(args.source[-2:], args.symbol, args.start, args.end,
                                args.adjust, ccy)  # type: ignore[arg-type]
    elif args.source in ("akshare_sina_cn", "akshare_sina_hk", "akshare_sina_us"):
        fetched = fetch_akshare_sina(args.source[-2:], args.symbol, args.start, args.end,
                                     args.adjust, ccy)  # type: ignore[arg-type]
    elif args.source == "baostock_cn":
        fetched = fetch_baostock(args.symbol, args.start, args.end, args.adjust, ccy)  # type: ignore[arg-type]
    elif args.source == "alphavantage_us":
        fetched = fetch_alphavantage(args.symbol, ccy, environ)  # type: ignore[arg-type]
    elif args.source == "frankfurter_fx":
        fetched = fetch_frankfurter(args.start, args.end, tuple(args.symbols.split(",")))
    elif args.source == "ecb_eurofxref":
        fetched = fetch_ecb_eurofxref(args.start, args.end, tuple(args.symbols.split(",")))
    elif args.source == "openfigi":
        fetched = fetch_openfigi(args.symbol, environ, args.exch_code, args.mic)
    else:
        raise FetchError(f"source {args.source!r} is not implemented in v0.1 (CFETS parity: after "
                         "the terms check, decide the route and add it)")
    rows, first, last = check_fetched(fetched)
    path, manifest = save_file(root, fetched, _now(), sha256_hex(Path(__file__).read_bytes()))
    span = f" range={first}..{last}" if first else ""
    print(f"saved {path} rows={rows}{span} sha256={manifest.file_sha256}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=TOOL_NAME, description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("probe", help="tiny first run: a few symbols/sources, 5 days")
    sub.add_parser("verify", help="re-hash every saved file against its manifest (offline)")
    f = sub.add_parser("fetch", help="fetch one source")
    f.add_argument("--source", required=True, choices=[
        "akshare_cn", "akshare_hk", "akshare_us", "akshare_sina_cn", "akshare_sina_hk", "akshare_sina_us",
        "baostock_cn", "alphavantage_us", "frankfurter_fx", "ecb_eurofxref", "openfigi", "cfets"])
    f.add_argument("--symbol", default="")
    f.add_argument("--symbols", default="USD,HKD,CNY")
    f.add_argument("--exch-code", default=None,
                   help="OpenFIGI exchCode; default US unless --mic is given (then micCode only)")
    f.add_argument("--mic", default="")
    f.add_argument("--start", default=PROBE_START)
    f.add_argument("--end", default=PROBE_END)
    f.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="raw")
    f.add_argument("--currency", default="")
    r = sub.add_parser("register-file", help="hash and describe a hand-made file")
    for name in ("path", "source", "kind", "format", "adjustment", "label"):
        r.add_argument(f"--{name}", required=True)
    r.add_argument("--ext", default="csv")
    r.add_argument("--currency", default="")
    r.add_argument("--market", default=None)
    r.add_argument("--identifiers", default="",
                   help="comma-separated subjects the file covers (a calendar id, symbols); one vintage per subject")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    environ: Mapping[str, str] = os.environ
    root = data_dir(environ)
    try:
        if args.command == "verify":  # offline and read-only: no guard
            return run_verify(root)
        require_human(environ, sys.stdin.isatty())
        if args.command == "probe":
            return run_probe(environ, root)
        if args.command == "register-file":
            return run_register(args, root)
        return run_fetch(args, environ, root)
    except (HumanOnlyError, TermsRefusedError, ToolDependencyError, FetchError, FileExistsError) as exc:
        print(f"error: {sanitize(str(exc), _secrets(environ), 600)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
