"""Demonstration B: the REAL slice (tech plan 16.10; PD-0035 section 3): US prices (Alpha Vantage, the last 100 sessions) and ECB FX, read ONLY from admitted files under `data/marketdata/files/`
through the normal ingest path (`build_in_memory_market_data`, which refuses a source with no terms attestation before it reads the payload), with calendars from REGISTERED calendar files only.

NOTHING is fabricated:
- a source with no permitting terms check (the AKShare sources, BaoStock) is listed as NOT ADMITTED and its files are not read;
- the calendar DRAFTS (`data/marketdata/calendars/drafts/`) are never read: until a calendar file is registered (as source `calendar.manual`, kind CALENDAR) there is no calendar, every freshness is
  UNKNOWN, split detection cannot run, and the engine's states say so;
- the demonstration LEDGER is hypothetical (P8): a deposit and three trades in one US listing whose amounts are the real closes of the dates it names, so a real price is a number the engine
  can value; it is labelled as a demonstration ledger and is not a user's holdings;
- the instrument identity (AAPL on XNAS, USD) is registered by this module's configuration (`REAL_INSTRUMENTS`), as a human identity file would, not discovered from price data.

`requirements()` lists exactly what the real slice still needs from the owner.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from corporate_actions_service import split_confirmation as f8b
from domain.currency import CurrencyCode
from domain.instrument import SecurityType
from domain.currency import Money
from domain.ledger import EventType, LedgerEvent
from domain.replay import SequencedEvent
from marketdata.adapters.alphavantage import AlphaVantageQuoteAdapter
from marketdata.adapters.base import AdapterRegistry
from marketdata.adapters.calendar_file import CalendarFileAdapter
from marketdata.adapters.ecb_eurofxref import EcbEurofxrefFxAdapter
from marketdata.adapters.frankfurter import FrankfurterFxAdapter
from marketdata.contracts import UsageScope
from marketdata.files import FileStore
from marketdata.ingest import build_in_memory_market_data
from marketdata.manifest import DataKind, FileManifest, MarketDataRelease
from marketdata.market11 import market11_conventions
from marketdata.profiles import ProfileNotAdmittedError, require_admitted
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry
from performance.engine import performance_conventions
from performance.periods import WindowRule, WindowSpec
from performance_tools.pack import FRANKFURTER_LABEL, PackSubject

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "marketdata"
REAL_SOURCES = ("alphavantage.us", "frankfurter.ecb", "ecb.eurofxref", "calendar.manual")
REAL_KINDS = (DataKind.QUOTE, DataKind.FX, DataKind.CALENDAR)
REAL_INSTRUMENTS = (
    InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", CurrencyCode("USD"), vendor_ids=(("alphavantage.us", "AAPL"),)),
)
FX_SOURCE_ID = "ecb.eurofxref"  # `fetch --source ecb_eurofxref` writes files of this source id, kind FX, payload format `ecb_eurofxref_hist_csv/1`
FX_PAYLOAD_FORMAT = "ecb_eurofxref_hist_csv/1"
PORTFOLIO_ID = uuid.UUID("d0000000-0000-4000-8000-0000000000d2")
ACCOUNT_ID = uuid.UUID("a1000000-0000-4000-8000-0000000000d2")
CALENDAR_DRAFTS = ("NYSE_SESSIONS", "ECB", "HKEX_SESSIONS", "CN_A_SESSIONS")


def _manifests(root: Path) -> List[Tuple[Path, FileManifest]]:
    store = FileStore(root)
    return [(p, FileManifest.from_json(p.read_text(encoding="utf-8"))) for p in store.manifest_paths()]


def classify_files(root: Path) -> List[Dict[str, Any]]:
    """Every file under `files/`: admitted for the real slice or not, and why."""
    registry = FileStore(root).load_registry()
    rows = []
    for path, m in _manifests(root):
        record = None
        try:
            record = registry.get(m.source_id)
        except Exception:  # noqa: BLE001 (an unknown source is a reason, not a crash)
            pass
        if record is None:
            admitted, why = False, "UNKNOWN_SOURCE: the source is not in SOURCES.json"
        elif not record.terms_attested:
            admitted, why = False, "SOURCE_TERMS_NOT_ATTESTED: no human terms-of-use check permitting internal development use is recorded (the payload is never read)"
        elif m.source_id not in REAL_SOURCES or m.data_kind not in REAL_KINDS:
            admitted, why = False, "not part of the real US/ECB slice (identity files are not read: identity is registered by this tool's configuration)"
        elif m.usage_scope is UsageScope.SYNTHETIC_TEST:
            admitted, why = False, "a synthetic file is never part of the real slice"
        else:
            admitted, why = True, "admitted"
            if m.data_kind is not DataKind.CALENDAR:  # the ingest path refuses a source whose precision profile is not admitted (a recalled, never-observed format): so does the pack, by name
                try:
                    require_admitted(m.source_id)
                except ProfileNotAdmittedError as exc:
                    admitted, why = False, f"PROFILE_NOT_ADMITTED: {exc}"
        rows.append({"path": str(path.relative_to(root)), "source_id": m.source_id, "data_kind": m.data_kind.value, "file_sha256": m.file_sha256, "payload_filename": m.payload_filename,
                     "usage_scope": m.usage_scope.value, "retrieval_time": m.retrieval_time, "request": dict(m.request), "source_identifiers": list(m.source_identifiers),
                     "admitted": admitted, "reason": why, "synthetic": m.usage_scope is UsageScope.SYNTHETIC_TEST})
    return rows


def _fx_coverage(rows: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    out = []
    for r in rows:
        if r["admitted"] and r["data_kind"] == "FX":
            req = r["request"]
            out.append((req.get("start") or req.get("read_start", "?"), req.get("end") or req.get("read_end", "?")))  # Frankfurter names `start`/`end`, the ECB history file `read_start`/`read_end`
    return out


def requirements(root: Path, rows: List[Dict[str, Any]], calendars_registered: bool, price_window: Optional[Tuple[datetime.date, datetime.date]]) -> List[str]:
    """Exactly what the real slice still needs, given what is on disk."""
    need: List[str] = []
    cal_files = [r for r in rows if r["admitted"] and r["data_kind"] == "CALENDAR"]
    if not cal_files:
        drafts = sorted(p.stem for p in (root / "calendars" / "drafts").glob("*.json")) if (root / "calendars" / "drafts").is_dir() else []
        need.append(f"REGISTER THE SESSION CALENDARS (PD-0034): none is registered, so every freshness is UNKNOWN, price and FX lookups are withheld and split detection cannot run. Drafts on disk: {drafts or 'none'}. "
                    "The owner checks each draft against its publisher notice (calendars/drafts/REVIEW.md), sets `version` and `prepared_by`, then registers each file, e.g. "
                    "`PYTHONPATH=src .venv-download/bin/python -m marketdata_tools.download register-file --path data/marketdata/calendars/drafts/NYSE_SESSIONS.json --source calendar.manual --kind CALENDAR "
                    "--format finweb_calendar_json/1 --adjustment RAW --label NYSE_2025_2026 --ext json --identifiers NYSE_SESSIONS` (and the same for ECB). The real US slice needs NYSE_SESSIONS (XNAS, XNYS) and ECB; "
                    "the HKEX and CN drafts are not needed until real HK and CN prices exist.")
    else:
        need.append("calendars: " + ", ".join(sorted({r['payload_filename'] for r in cal_files})) + " registered.")
    if price_window is None:
        need.append("REAL US PRICES: no admitted Alpha Vantage quote file is on disk. Fetch one with the download tool (`fetch --source alphavantage.us --symbol AAPL`, needs the owner's API key and network).")
    else:
        lo, hi = price_window
        covers = [c for c in _fx_coverage(rows) if c[0] <= lo.isoformat() and c[1] >= hi.isoformat()]
        if not covers:
            need.append(f"FX FOR THE PRICE WINDOW (ECB reference rates; the admitted route today republishes them via Frankfurter, provenance UNCONFIRMED, Ruling 1.1a; needed for the EUR and CNY reporting views; the USD view needs none): the admitted FX files cover {_fx_coverage(rows) or 'nothing'}, and the US prices run "
                        f"{lo.isoformat()} to {hi.isoformat()}, so the EUR and CNY views are INSUFFICIENT_DATA until an ADMITTED file covers the window. The route that is admitted today is Frankfurter: "
                        f"`PYTHONPATH=src .venv-download/bin/python -m marketdata_tools.download fetch --source frankfurter_fx --symbols USD,CNY --start {lo.isoformat()} --end {hi.isoformat()}` "
                        "(source id `frankfurter.ecb`, data kind FX, payload format `frankfurter_json_timeseries/1`). The ECB's own history file "
                        f"(`fetch --source ecb_eurofxref`; source id `{FX_SOURCE_ID}`, kind FX, payload format `{FX_PAYLOAD_FORMAT}`) is NOT read yet: its precision profile is MEMORY, and the ingest path refuses a "
                        "source until its first real file has been profiled (market-data Appendix A.4, MD-OI-12); the pack lists such a file as PROFILE_NOT_ADMITTED and does not read it.")
        need.append("The real slice is US-only and a slice, not the cross-border proof: CN and HK price behaviour is shown on SYNTHETIC data only (PD-0035 section 3; STATUS 17).")
    return need


FX_ROUTE_LABEL = FRANKFURTER_LABEL


def conflict_text(c: Dict[str, Any]) -> str:
    files = "; ".join(f"{f['source_id']} {f['data_kind']} retrieved {f['retrieval_time']} sha256 {f['file_sha256']} ({f['payload_filename']})" for f in c["files"])
    d = c.get("disagreement")
    if d is None:
        said = ""
    elif not d["comparable"]:
        said = f" Whether they disagree on a shared date could not be established: {d['reason']}."
    elif d["shared_dates"] == 0:
        said = " The vintages share no (subject, date) point: they do not disagree on any date, they cover different dates of one series."
    elif not d["disagree"]:
        said = f" The vintages agree on all {d['shared_dates']} shared (subject, date) points: no shared date disagrees."
    else:
        shown = "; ".join(f"{x['subject']} {x['date']}: " + " vs ".join(x["values"].values()) for x in d["disagree"][:10])
        said = f" The vintages DISAGREE on {len(d['disagree'])} of {d['shared_dates']} shared dates: {shown}{' ...' if len(d['disagree']) > 10 else ''}."
    return (f"TWO VINTAGES OF ONE SERIES {c['series']}: {files}.{said} M fails closed (market-data Ruling 0.1: it never picks the latest) and NEITHER file is in M, so nothing that depends on the series has a number. "
            "The operator names the file set explicitly: `--exclude-file <sha256>` (repeatable) removes a file from M, or `--use-file <sha256>` (repeatable) names exactly the files of M; the choice is recorded "
            "in 00_inputs.json and SUMMARY.md as the file set chosen by the operator.")


def apply_operator_selection(rows: List[Dict[str, Any]], exclude: Sequence[str], only: Sequence[str]) -> Dict[str, Any]:
    """The operator's explicit file choice, by sha256 (CP3-12): `exclude` removes files from M, `only` keeps exactly those among the admitted files. A human naming the vintage satisfies market-data
    Ruling 0.1 (at most one vintage per series in M); the tool never chooses. Returns the record of the choice (empty when none was made); an unknown sha256 is reported, never ignored."""
    by_sha = {r["file_sha256"]: r for r in rows}
    unknown = sorted(s for s in list(exclude) + list(only) if s not in by_sha)
    record: Dict[str, Any] = {"exclude": sorted(exclude), "only": sorted(only), "unknown_sha256": unknown}
    if not exclude and not only:
        return {}
    for r in rows:
        if r["admitted"] and r["file_sha256"] in exclude:
            r["admitted"], r["reason"] = False, "EXCLUDED_BY_OPERATOR: named in --exclude-file"
        elif r["admitted"] and only and r["file_sha256"] not in only:
            r["admitted"], r["reason"] = False, "NOT_SELECTED_BY_OPERATOR: --use-file names the files of M and this is not one"
    # `files_in_m` is filled by `finish_operator_selection`, AFTER the vintage-conflict check: the record of M is exactly M (CP3-19).
    return record


def finish_operator_selection(record: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """CP3-19: once the conflict check has run, record exactly what M holds (`files_in_m`) and, for every file the operator NAMED (`--use-file`, `--exclude-file`), what became of it: in M, or not in M
    with its reason (unattested, profile not admitted, refused source, left out by a vintage conflict, ...). A named file is never dropped silently."""
    if not record:
        return record
    by_sha = {r["file_sha256"]: r for r in rows}
    record["files_in_m"] = [{"source_id": r["source_id"], "data_kind": r["data_kind"], "retrieval_time": r["retrieval_time"], "file_sha256": r["file_sha256"], "payload_filename": r["payload_filename"]}
                            for r in rows if r["admitted"]]
    named = []
    for how, shas in (("use-file", record["only"]), ("exclude-file", record["exclude"])):
        for sha in shas:
            r = by_sha.get(sha)
            if r is None:
                continue
            named.append({"named_by": how, "file_sha256": sha, "source_id": r["source_id"], "payload_filename": r["payload_filename"], "in_m": bool(r["admitted"]),
                          "reason": "in M" if r["admitted"] else r["reason"]})
    record["named_files"] = named
    return record


def _series_values(root: Path, rows: List[Dict[str, Any]], sha: str) -> Dict[Tuple[str, str], str]:
    """`{(subject, date): value}` of one file, read through its adapter (verified against its manifest); raises on anything unreadable."""
    adapters = AdapterRegistry([AlphaVantageQuoteAdapter(), FrankfurterFxAdapter(), EcbEurofxrefFxAdapter(), CalendarFileAdapter()])
    path = next(root / r["path"] for r in rows if r["file_sha256"] == sha)
    verified = FileStore(root).read_verified(path)
    out = adapters.for_manifest(verified.manifest).translate(verified.manifest, verified.payload)
    values: Dict[Tuple[str, str], str] = {}
    for q in out.quotes:
        values[(str(q.identifiers), q.value_date.isoformat())] = str(q.price)
    for f in out.fx:
        values[(f"{f.base_currency}/{f.quote_currency}", f.value_date.isoformat())] = str(f.rate)
    return values


def decimal_value(text: str) -> Any:
    """The comparison key of a value written as text: its `Decimal` (so `200.00 == 200.0000`); text that is not a number compares as itself (never equal to a number)."""
    try:
        return Decimal(text)
    except InvalidOperation:
        return ("text", text)


def vintage_disagreement(root: Path, rows: List[Dict[str, Any]], shas: List[str]) -> Dict[str, Any]:
    """CP3-19: do the conflicting vintages disagree on any date they share? `{"comparable": True, "shared_dates": n, "disagree": [{subject, date, values: {sha: value}}]}`, or `comparable False`
    with the reason when a file cannot be read. Reporting only: the tool never uses it to pick a vintage."""
    try:
        per = {sha: _series_values(root, rows, sha) for sha in shas}
    except Exception as exc:  # noqa: BLE001 (an unreadable vintage is a stated reason, not a crash)
        return {"comparable": False, "reason": f"{type(exc).__name__}: {exc}"}
    keys = sorted(set.intersection(*[set(v) for v in per.values()])) if per else []
    # market-data Ruling 1.1a item 3 (CP3-21): values are equal as DECIMALS (trailing zeros ignored): 200.00 and 200.0000 agree. The report still shows each file's value as written.
    bad = [{"subject": k[0], "date": k[1], "values": {sha: per[sha][k] for sha in shas}} for k in keys if len({decimal_value(per[sha][k]) for sha in shas}) > 1]
    return {"comparable": True, "shared_dates": len(keys), "disagree": bad}


def find_vintage_conflicts(rows: List[Dict[str, Any]], manifests: List[FileManifest], root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Two admitted files that contribute to one series are two vintages (market-data Ruling 0.1): M fails closed and is NOT built from either. Each conflict names both files by source, retrieval time
    and sha256. Every file of a conflicting series is excluded from M (so nothing that depends on the series gets a number) and marked VINTAGE_CONFLICT."""
    groups: Dict[Tuple[str, ...], List[FileManifest]] = {}
    for m in manifests:
        for key in m.series_keys():
            groups.setdefault(key, []).append(m)
    conflicts = []
    for key, members in sorted(groups.items()):
        if len(members) > 1:
            conflicts.append({"series": list(key), "files": [{"source_id": m.source_id, "data_kind": m.data_kind.value, "retrieval_time": m.retrieval_time, "file_sha256": m.file_sha256,
                                                              "payload_filename": m.payload_filename} for m in sorted(members, key=lambda x: (x.retrieval_time, x.file_sha256))]})
    if root is not None:  # CP3-19: say whether the vintages disagree on a shared date, and which
        for c in conflicts:
            c["disagreement"] = vintage_disagreement(Path(root), rows, [f["file_sha256"] for f in c["files"]])
    in_conflict = {f["file_sha256"] for c in conflicts for f in c["files"]}
    for r in rows:
        if r["file_sha256"] in in_conflict and r["admitted"]:
            r["admitted"], r["reason"] = False, ("VINTAGE_CONFLICT: another admitted file contributes to the same series (market-data Ruling 0.1: a release fails closed and never picks the latest); "
                                                  "the operator names the file set with --exclude-file or --use-file")
    return conflicts


def build_real_subject(root: Path = DEFAULT_ROOT, exclude: Sequence[str] = (), only: Sequence[str] = ()) -> Tuple[Optional[PackSubject], Dict[str, Any]]:
    """The real-slice subject, or `(None, report)` when no real price file can be used. The report always lists every file and what is still needed. Two vintages of one series FAIL CLOSED
    (reported with both files, no number for anything depending on the series) unless the operator names the file set by sha256 (`exclude`, `only`); the choice is recorded."""
    root = Path(root)
    rows = classify_files(root)
    store = FileStore(root)
    registry = store.load_registry()
    selection = apply_operator_selection(rows, exclude, only)
    admitted = [m for p, m in _manifests(root) if any(r["file_sha256"] == m.file_sha256 and r["admitted"] for r in rows)]
    conflicts = find_vintage_conflicts(rows, admitted, root)
    selection = finish_operator_selection(selection, rows)
    admitted = [m for m in admitted if any(r["file_sha256"] == m.file_sha256 and r["admitted"] for r in rows)]
    quotes = [m for m in admitted if m.data_kind is DataKind.QUOTE]
    report: Dict[str, Any] = {"root": str(root), "files": rows, "admitted": len(admitted), "not_admitted": len(rows) - len(admitted), "vintage_conflicts": conflicts,
                              "file_set_chosen_by_operator": selection}
    if selection and selection["unknown_sha256"]:
        report["requirements"] = [f"the operator's selection names sha256 values that are not files of the store: {selection['unknown_sha256']}"]
        report["status"] = "SELECTION_UNKNOWN_FILE"
        return None, report
    if not quotes:
        need = requirements(root, rows, False, None)
        if conflicts:
            report["status"] = "VINTAGE_CONFLICT"
            need = [conflict_text(c) for c in conflicts] + need
        else:
            report["status"] = "NO_REAL_PRICE_FILE"
        report["requirements"] = need
        return None, report
    counter = [0]

    def new_id() -> uuid.UUID:
        counter[0] += 1
        return uuid.uuid5(uuid.UUID("a0000000-0000-4000-8000-000000000001"), f"real-slice-{counter[0]}")

    ident = InMemoryIdentityRegistry(new_id)
    results = ident.register_instruments(REAL_INSTRUMENTS)
    listing_id = results[0].listing_id
    adapters = AdapterRegistry([AlphaVantageQuoteAdapter(), FrankfurterFxAdapter(), EcbEurofxrefFxAdapter(), CalendarFileAdapter()])
    release = MarketDataRelease.from_manifests("real-slice", admitted, [])
    built = build_in_memory_market_data(release, store, registry, adapters, ident, catalog_calendars={})  # the real slice has no benchmark: no catalog applies
    conventions = market11_conventions(built.calendars)
    readings = sorted(built.store.quotes(listing_id, datetime.date.min, datetime.date.max).readings, key=lambda r: r.observation.value_date)
    closes = {r.observation.value_date: r.observation.price for r in readings}
    report["build_issues"] = [str(i) for i in built.issues][:20]
    report["quotes_loaded"] = len(closes)
    if len(closes) < 6:
        report["requirements"] = requirements(root, rows, bool(built.calendars), None)
        report["status"] = "TOO_FEW_REAL_PRICES"
        return None, report
    days = sorted(closes)
    d0, d1, d2 = days[0], days[len(days) // 2], days[-8]
    as_of = days[-1]
    usd = CurrencyCode("USD")

    def event(seq: int, kind: EventType, day: datetime.date, **kw: Any) -> SequencedEvent:
        return SequencedEvent(seq, LedgerEvent(event_id=uuid.uuid5(PORTFOLIO_ID, f"event-{seq}"), account_id=ACCOUNT_ID, event_type=kind, event_date=day, currency=usd,
                                               source_reference=f"REAL-SLICE-DEMO-{seq}", **kw))

    def money(x: Decimal) -> Money:
        return Money(x, usd)

    events = (
        event(1, EventType.DEPOSIT, d0, amount=money(Decimal(10000))),
        event(2, EventType.BUY, d0, listing_id=listing_id, quantity=Decimal(10), amount=money(closes[d0] * 10)),
        event(3, EventType.BUY, d1, listing_id=listing_id, quantity=Decimal(5), amount=money(closes[d1] * 5)),
        event(4, EventType.SELL, d2, listing_id=listing_id, quantity=Decimal(8), amount=money(closes[d2] * 8)),
    )
    need = requirements(root, rows, bool(built.calendars), (d0, as_of))
    report["requirements"] = need
    report["status"] = "BUILT"
    report["calendars_registered"] = [c.calendar_id for c in built.calendars.calendars()]
    files = tuple({"source_id": r["source_id"], "data_kind": r["data_kind"], "file_sha256": r["file_sha256"], "payload_filename": r["payload_filename"], "usage_scope": r["usage_scope"],
                   "retrieval_time": r["retrieval_time"], "admitted": r["admitted"], "reason": r["reason"], "synthetic": r["synthetic"]} for r in rows)
    # no corporate-action source is admitted, so the policy names two sources that do not exist (a policy needs one of each role); M holds no corporate-action record, so there is nothing for it to miss
    policy = f8b.ConfirmationPolicy(frozenset({"none.admitted.feed"}), frozenset({"none.admitted.filing"}))
    subject = PackSubject(
        name="DEMO-B: US-only real slice (Alpha Vantage prices; FX views from ECB reference rates as republished by Frankfurter, provenance unconfirmed)", kind="REAL_SLICE_DEMONSTRATION_B",
        description=("A hypothetical USD ledger in one US listing (AAPL: a deposit, two purchases and a sale at the real closes of the dates named) over the REAL Alpha Vantage prices on disk, with the FX "
                     f"files and the calendars that are admitted and REGISTERED. FX, where a file is present: {FX_ROUTE_LABEL}. Nothing here is a user's holding."),
        operator_selection=selection, vintage_conflicts=tuple(conflicts),
        portfolio_id=PORTFOLIO_ID, events=events, ledger_version=4, reporting=usd, store=built.store, resolver=ident, market_conventions=conventions, perf=performance_conventions(),
        policy=policy, as_of=as_of,
        windows=(("SINCE_INCEPTION", WindowSpec(WindowRule.SINCE_INCEPTION)), ("TRAILING_1M", WindowSpec(WindowRule.TRAILING_MONTHS, 1)), ("CUSTOM_FROM_MIDPOINT", WindowSpec(WindowRule.CUSTOM, None, d1))),
        files=files, account_names={ACCOUNT_ID: "R1 (US, USD)"}, requirements=tuple(need), extra_reporting=(CurrencyCode("EUR"), CurrencyCode("CNY")),
        notes=(f"Real closes are those of the Alpha Vantage file (usage scope INTERNAL_DEVELOPMENT_ONLY): first {d0.isoformat()}, last {as_of.isoformat()}; the as-of date is the last print.",
               f"Ledger dates: deposit and first purchase {d0.isoformat()}, second purchase {d1.isoformat()}, sale {d2.isoformat()}; each amount is quantity x the real close of that date.",
               "Identity is registered by this tool's configuration (AAPL, XNAS, USD), not discovered from price data.",
               "CN and HK price behaviour is shown on synthetic data only (PD-0035 section 3); this slice proves the real data path for US prices and, with an admitted FX file, for FX republished by Frankfurter (not the ECB's own file: provenance unconfirmed, Ruling 1.1a)."),
        limitations=("No corporate-action source is admitted, so split detection has nothing to corroborate with; a split missing from a real ledger would not be found.",
                     "Without registered calendars every freshness is UNKNOWN and the states that follow are shown as computed, never repaired."))
    return subject, report


