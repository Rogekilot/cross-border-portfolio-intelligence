"""Shared translation of a daily OHLCV CSV through a precision profile (market-data/1.1).

Used by the AKShare-saved-file adapters. A pure function of its arguments. What it enforces:

- Ruling 2.4: every field is read as TEXT, checked against the profile's declared binary format
  for the whole file (the float32-signature check; FAIL CLOSED: a wrong profile means the file is
  not admitted), then normalized to the shortest round-trip decimal in that format. A RAW close
  is validated against the market's maximum decimals and the format's resolving power; a value
  that fails is KEPT but marked not recovered (bound = half an ulp), so it can corroborate and is
  never the value used. Nothing is rounded to a fixed number of decimals.
- Ruling 4.6 item 2: every row must satisfy low <= min(open, close) <= max(open, close) <= high;
  a failing row is not admitted.
- Ruling 4.6 item 3: where the upstream supplies a change column (Eastmoney 涨跌额) it must equal
  close_t - close_(t-1) exactly on consecutive rows of the file. Used ONLY as a check; failure is
  flagged on every row of the file (lineage) and reported, and the pair then cannot be
  CORROBORATED through a shared library.
- Ruling 2.5: vendor-computed columns (change %, amplitude, turnover rate) are never read.
- Ruling 2.6: where a turnover column exists, the median of turnover / (close x volume) must lie
  within [0.9, 1.1] x the declared shares per unit, or the file is not admitted. Without a
  turnover column the volume unit stays DECLARED_UNVERIFIED. Volume is converted to SHARES.
- An ADJUSTED file yields `UnresolvedAdjustedQuote`s (verification-only), never quotes.
"""

from __future__ import annotations

import csv
import datetime
import io
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Tuple

from marketdata.adapters.base import (
    AdapterIssue,
    AdapterOutput,
    DatedStatement,
    IssueCode,
    lineage_for,
    timing_for,
)
from marketdata.contracts import (
    AdjustmentLabel,
    AdjustmentMethod,
    AdjustmentStatus,
    ExternalIdentifiers,
    ObservationRuleError,
    UnresolvedAdjustedQuote,
    UnresolvedQuote,
)
from marketdata.manifest import FileManifest
from marketdata.precision import (
    NumberError,
    check_field_format,
    field_bound,
    normalize,
    normalize_adjusted,
    normalize_volume,
    resolve_close,
    row_is_consistent,
    volume_unit_check,
)
from marketdata.profiles import DECLARED_UNVERIFIED, MEMORY, PROVISIONAL_UNOBSERVED, SourceProfile


@dataclass(frozen=True)
class Columns:
    date: str
    open: str
    high: str
    low: str
    close: str
    volume: str
    turnover: Optional[str] = None  # amount traded, used only for the Ruling 2.6 unit check
    change: Optional[str] = None  # the upstream's own close change, used only for Ruling 4.6 item 3
    symbol: Optional[str] = None  # None: the symbol comes from the manifest


def _field_bounds(profile: SourceProfile, parsed: Dict[str, object]) -> Optional[Tuple[Decimal, Decimal, Decimal]]:
    bounds = [field_bound(profile.fields[n], parsed[n]) for n in ("open", "high", "low")]  # type: ignore[arg-type]
    if any(b is None for b in bounds):
        return None
    return (bounds[0], bounds[1], bounds[2])  # type: ignore[return-value]


def translate_daily_csv(
    adapter: object, manifest: FileManifest, payload: bytes, columns: Columns,
    profile: SourceProfile, market: str,
    adjustment_override: Optional[AdjustmentStatus] = None,
    identifiers_for: Optional[Callable[[str], ExternalIdentifiers]] = None,
) -> AdapterOutput:
    """`adjustment_override` is how an adapter whose profile documents the call's adjustment (for
    example a function documented as as-traded) reads an UNDECLARED manifest of that call. Rows are
    sorted by date and no input order is assumed (an API may deliver newest first). `identifiers_for` builds the row's
    `ExternalIdentifiers` from its symbol (default: the symbol as a vendor id scoped to the source, no MIC).

    Two rules hold on EVERY route since market-data/1.16 (they were opt-in for the A-share route in 1.15, and no route has an opt-out):
    a session date written twice for one listing makes that SERIES contradicted. This adapter lists what each row states (`AdapterOutput.dated_statements`)
    and INGESTION judges it after identity resolution, so the unit is the listing and the other series of the file are read as before (Test V0, section 11
    item 25; Example 3-E; Addendum A.4), and a text field showing more decimals than its profile's `delivered_dp` fails the profile check (A.4
    item 7, section 11 item 26; Example 7A-G3 (d)), for `TEXT_DECIMAL` and `FLOAT64` fields (a `FLOAT32` rendering is exempt)."""
    def refuse(code: IssueCode, detail: str, ref: str = "file") -> AdapterOutput:
        return AdapterOutput(issues=(AdapterIssue(ref, code, detail),))

    if manifest.declared_currency is None:
        return refuse(IssueCode.UNDECLARED_CURRENCY, "manifest declares no currency")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return refuse(IssueCode.UNKNOWN_FORMAT, str(exc))
    reader = csv.DictReader(io.StringIO(text))
    wanted = [columns.date, columns.open, columns.high, columns.low, columns.close, columns.volume]
    if columns.symbol:
        wanted.append(columns.symbol)
    missing = [c for c in wanted if c not in (reader.fieldnames or [])]
    if missing:
        return refuse(IssueCode.UNKNOWN_FORMAT, f"missing columns {missing}", "header")
    if columns.symbol is None and len(set(manifest.source_identifiers)) != 1:
        return refuse(IssueCode.MISSING_FIELD, "manifest must name exactly one symbol")
    rows = [r for r in reader if any((v or "").strip() for v in r.values())]

    # --- profile check against the data (fail closed) -----------------------------------
    roles: List[Tuple[str, str]] = [("open", columns.open), ("high", columns.high), ("low", columns.low),
                                    ("close", columns.close), ("volume", columns.volume)]
    has_turnover = bool(columns.turnover and columns.turnover in (reader.fieldnames or []))
    if has_turnover:
        roles.append(("turnover", columns.turnover or ""))
    for role, column in roles:
        fp = profile.fields.get(role)
        if fp is None:
            return refuse(IssueCode.PROFILE_CHECK_FAILED, f"profile has no {role} field", "header")
        problem = check_field_format((r.get(column) or "" for r in rows), fp)
        if problem:
            return refuse(IssueCode.PROFILE_CHECK_FAILED, f"{role}: {problem}", "profile")

    # Test V0 (market-data/1.16, every market, section 11 item 25): a price file states a close per (listing, session date), and two statements of one make the
    # series CONTRADICTED. The adapter does not judge it, because the unit is the LISTING and only ingestion has resolved the identity (a vendor id and its alias are
    # two symbols of one listing; Addendum A.4). It LISTS what each row states: one `DatedStatement` for every row whose date parses and which names a symbol,
    # whether or not the row later passes its own checks (a row whose date parses but whose other field is bad states that session: Addendum A.2 (iv)), identical
    # rows included. The DATE decides, not its spelling: the row parser below reads any `date.fromisoformat` form (`2026-09-29`, `20260929`, `2026-W40-2`).
    # A row whose date is blank or cannot be read states NOTHING: it is refused below as unparseable, alone, and takes no part in the count (Addendum A.2 (i)
    # to (iii); never a silent removal of the series).
    # A header that repeats a column this adapter reads states every field of every row twice (`csv.DictReader` would silently keep the LAST of them): each
    # row is then listed twice, so that every series of the file is two statements of one close, and contradicted (Addendum A, observation of A.3).
    read_columns = [c for c in (columns.date, columns.open, columns.high, columns.low, columns.close, columns.volume, columns.turnover, columns.change,
                                columns.symbol) if c]
    header = list(reader.fieldnames or [])
    repeated_columns = sorted({c for c in read_columns if header.count(c) > 1})
    statements: List[DatedStatement] = []
    for row in rows:
        stated_symbol = ((row.get(columns.symbol) or "").strip() if columns.symbol else manifest.source_identifiers[0])
        try:
            stated_day = datetime.date.fromisoformat((row.get(columns.date) or "").strip())
        except ValueError:
            continue
        if not stated_symbol:
            continue
        ids = (ExternalIdentifiers(vendor_id=stated_symbol, source_id=manifest.source_id)
               if identifiers_for is None else identifiers_for(stated_symbol))
        for _ in range(2 if repeated_columns else 1):
            statements.append(DatedStatement(ids, stated_day, f"{stated_symbol}@{stated_day.isoformat()}"))
    statements.sort(key=lambda s: s.ref)  # no input order is assumed (an API may deliver newest first)
    duplicate_issues = [AdapterIssue(f"header/{c}", IssueCode.DUPLICATE_SESSION_DATE,
                                     f"the header names column {c!r} more than once: every row states its fields twice, so every series of the file is "
                                     "contradicted (Test V0); no value is chosen by position") for c in repeated_columns]

    effective = adjustment_override or manifest.declared_adjustment
    raw = effective is AdjustmentStatus.RAW
    # market-data/1.3 section 9B #4 (a): a label the MANIFEST did not carry is recorded as coming from the profile's
    # documentation of the call, never presented as the file's own declaration. The status of that reading is PROFILE DATA
    # (market-data/1.16 section 11 item 23): DECLARED when a human read the vendor's documentation (PD-0066 decision 3), MEMORY when
    # the profile has no such record for the call. Either way a vendor's declaration is not a verification: the label status
    # stays UNVERIFIABLE, set by ingestion.
    function = dict(manifest.request).get("function", "?")
    documented = profile.call_adjustment.get(function)
    label_source = (None if adjustment_override is None else
                    f"PROFILE_CALL_ADJUSTMENT:{profile.source_id}:{function}:{documented.status if documented is not None else MEMORY}")
    # market-data/1.2 section 9A #2: the security class comes from the listing's identity record, never
    # from a request parameter. The adapter does not know the listing, so the class is unknown here and
    # the strict value applies (CN: 2 decimals); a refused value is flagged SECURITY_CLASS_UNRESOLVED.
    security_class: Optional[str] = None
    volume_profile = profile.fields["volume"]
    shares_per_unit = Decimal(volume_profile.shares_per_unit or 1)
    parsed: List[Dict[str, object]] = []
    issues: List[AdapterIssue] = list(duplicate_issues)
    for line, row in enumerate(rows, start=2):
        day_text = (row.get(columns.date) or "").strip()
        symbol = ((row.get(columns.symbol) or "").strip() if columns.symbol else manifest.source_identifiers[0])
        ref = f"{symbol or '?'}@{day_text or '?'}"
        try:
            if not symbol:
                raise NumberError("empty symbol")
            day = datetime.date.fromisoformat(day_text)
            o = normalize((row.get(columns.open) or ""), profile.fields["open"].format)
            h = normalize((row.get(columns.high) or ""), profile.fields["high"].format)
            low = normalize((row.get(columns.low) or ""), profile.fields["low"].format)
            close_text = (row.get(columns.close) or "").strip()
            if raw:
                price = resolve_close(close_text, profile.fields["close"], market, security_class)
            else:
                price = normalize_adjusted(close_text, profile.fields["close"])
            units = normalize_volume((row.get(columns.volume) or ""), volume_profile)
            turnover = (normalize((row.get(columns.turnover) or ""), profile.fields["turnover"].format)
                        if has_turnover else None)
            change = (normalize((row.get(columns.change) or ""), profile.fields["close"].format)
                      if columns.change and columns.change in (reader.fieldnames or []) else None)
        except (NumberError, ValueError) as exc:
            issues.append(AdapterIssue(ref, IssueCode.UNPARSEABLE_ROW, f"line {line}: {type(exc).__name__}: {exc}"))
            continue
        if not row_is_consistent(o, h, low, price.value if raw else price.value):
            issues.append(AdapterIssue(ref, IssueCode.ROW_INCONSISTENT, "low <= min(open, close) <= max(open, close) <= high fails"))
            continue
        if raw and not price.value > 0:
            issues.append(AdapterIssue(ref, IssueCode.NON_POSITIVE_VALUE, "close must be > 0"))
            continue
        parsed.append({"ref": ref, "symbol": symbol, "day": day, "open": o, "high": h, "low": low,
                       "price": price, "units": units, "turnover": turnover, "change": change,
                       "close_text": close_text})

    parsed.sort(key=lambda p: p["day"])  # stable: no input order is assumed

    # --- Ruling 4.6 item 3: within-source arithmetic (check only) ------------------------
    checks_passed: Optional[bool] = None
    if columns.change and any(p["change"] is not None for p in parsed):
        checks_passed = True
        for prev, cur in zip(parsed, parsed[1:]):
            if cur["change"] is not None and cur["price"].value - prev["price"].value != cur["change"]:  # type: ignore[attr-defined]
                checks_passed = False
                issues.append(AdapterIssue(str(cur["ref"]), IssueCode.CONSISTENCY_CHECK_FAILED,
                                           "the change column does not equal close_t - close_(t-1)"))
                break

    # --- Ruling 2.6: volume unit ---------------------------------------------------------
    unit_status: Optional[str] = None
    if raw:
        if has_turnover:
            ok, median = volume_unit_check(
                [(p["turnover"], p["price"].value, p["units"]) for p in parsed if p["turnover"] is not None],  # type: ignore[attr-defined,misc]
                int(shares_per_unit))
            if ok is False:
                return refuse(IssueCode.VOLUME_UNIT_CHECK_FAILED,
                              f"median turnover/(close x volume) = {median} is outside "
                              f"[0.9, 1.1] x {shares_per_unit} shares per unit", "profile")
            unit_status = "VERIFIED" if ok else "DECLARED_UNVERIFIED"
        elif volume_profile.status in (DECLARED_UNVERIFIED, PROVISIONAL_UNOBSERVED):  # a provisional unit is not a verified one
            unit_status = "DECLARED_UNVERIFIED"

    quotes: List[UnresolvedQuote] = []
    adjusted: List[UnresolvedAdjustedQuote] = []
    reference: List[UnresolvedAdjustedQuote] = []
    timing = timing_for(manifest)
    for p in parsed:
        price = p["price"]
        profile_id = profile.profile_id("close")
        lineage = lineage_for(manifest, adapter, str(p["ref"]), source_value_text=str(p["close_text"]),  # type: ignore[arg-type]
                              precision_profile_id=profile_id, consistency_checks_passed=checks_passed,
                              volume_unit_status=unit_status, adjustment_status=effective,
                              adjustment_label_source=label_source)
        ids = (ExternalIdentifiers(vendor_id=str(p["symbol"]), source_id=manifest.source_id)
               if identifiers_for is None else identifiers_for(str(p["symbol"])))
        try:
            if raw:
                if not price.recovered:  # type: ignore[attr-defined]
                    issues.append(AdapterIssue(str(p["ref"]), IssueCode.PRICE_NOT_RECOVERED,
                                               f"kept, corroborates only: {price.note}"))  # type: ignore[attr-defined]
                quotes.append(UnresolvedQuote(
                    identifiers=ids, value_date=p["day"], price=price.value,  # type: ignore[arg-type,attr-defined]
                    currency=manifest.declared_currency, timing=timing, lineage=lineage,
                    volume=p["units"] * shares_per_unit,  # type: ignore[operator]
                    recovered=price.recovered, precision_bound=price.bound))  # type: ignore[attr-defined]
                # the same row, all four fields, for Test V2 (verification-only; never a price)
                reference.append(UnresolvedAdjustedQuote(
                    identifiers=ids, value_date=p["day"], open=p["open"], high=p["high"], low=p["low"],  # type: ignore[arg-type]
                    close=price.value, currency=manifest.declared_currency,  # type: ignore[attr-defined]
                    label=AdjustmentLabel(AdjustmentStatus.RAW, AdjustmentMethod.UNKNOWN, None,
                                          manifest.retrieval_time),
                    timing=timing, lineage=lineage, precision_bound=price.bound,  # type: ignore[attr-defined]
                    # market-data/1.4 V2 (a'): delta_r per field, from each field's own profile. A field whose profile
                    # declares no `delivered_dp` (text or float64) has NO bound (C2-10): the row then carries no
                    # field_bounds at all and V2 stops on the series with cause PROFILE_INCOMPLETE (never a
                    # half-ulp-of-binary64 substitute)
                    field_bounds=_field_bounds(profile, p)))  # type: ignore[arg-type]
            else:
                label = AdjustmentLabel(effective, AdjustmentMethod.UNKNOWN, None,
                                        manifest.retrieval_time)
                adjusted.append(UnresolvedAdjustedQuote(
                    identifiers=ids, value_date=p["day"], open=p["open"], high=p["high"], low=p["low"],  # type: ignore[arg-type]
                    close=price.value, currency=manifest.declared_currency, label=label,  # type: ignore[attr-defined]
                    timing=timing, lineage=lineage, precision_bound=price.bound))  # type: ignore[attr-defined]
        except ObservationRuleError as exc:
            issues.append(AdapterIssue(str(p["ref"]), IssueCode.CONTRACT_VIOLATION, str(exc)))
    return AdapterOutput(quotes=tuple(quotes), adjusted=tuple(adjusted), reference=tuple(reference),
                         issues=tuple(issues), dated_statements=tuple(statements))
