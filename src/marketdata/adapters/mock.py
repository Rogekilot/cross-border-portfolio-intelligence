"""`mock.synthetic`: a deterministic mock adapter (Tech Plan §15.2).

It translates a saved SYNTHETIC file (payload format `mock_synthetic_json/1`) into
unresolved observations through exactly the same interface a real source adapter uses. It
is deterministic: no clock, no randomness, no generation from a seed; the bytes in are the
facts out. `make_synthetic_payload` writes such bytes canonically, for tests.

Payload shape (JSON; numbers are read as exact Decimals, strings are accepted too):

    {"quotes":   [{"ticker", "mic", "date", "close"}],
     "fx":       [{"base", "quote", "date", "rate", "rate_basis"}],
     "actions":  [{"ticker", "mic", "date" (the ex-date), "type", then per type:
                   SPLIT "new_units", "old_units" | CASH_DIVIDEND "amount", "currency",
                   "pay_date", optional "record_date", "paid_currency", "issuer_fx_rate" |
                   SYMBOL_CHANGE "old_ticker", "new_ticker" | UNSUPPORTED "label"}],
     "benchmarks": [{"benchmark_id", "provider", "value_kind", "currency",
                     "points": [{"date", "value"}]}]}

Quote and benchmark currency comes from the manifest (`declared_currency`); an adapter
never infers a currency.
"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

from domain.currency import CurrencyCode, InvalidCurrencyCodeError, Money
from domain.ledger import LedgerEventRuleError, SplitRatio
from marketdata.adapters.base import (
    AdapterIssue,
    AdapterOutput,
    ContradictedSeries,
    DatedStatement,
    IssueCode,
    licensing_for,
    lineage_for,
    timing_for,
)
from marketdata.canonical import canonical_bytes
from marketdata.contracts import (
    BenchmarkPoint,
    BenchmarkSeries,
    BenchmarkValueKind,
    CorporateActionType,
    ExternalIdentifiers,
    FXObservation,
    ObservationRuleError,
    UnresolvedCorporateAction,
    UnresolvedQuote,
)
from marketdata.manifest import DataKind, FileManifest

MOCK_FORMAT = "mock_synthetic_json/1"
MOCK_SOURCE_ID = "mock.synthetic"


def make_synthetic_payload(
    quotes: Tuple[dict, ...] = (),
    fx: Tuple[dict, ...] = (),
    actions: Tuple[dict, ...] = (),
    benchmarks: Tuple[dict, ...] = (),
) -> bytes:
    """Canonical bytes of a synthetic payload. Values given as Decimal or str."""
    return canonical_bytes(
        {"quotes": list(quotes), "fx": list(fx), "actions": list(actions),
         "benchmarks": list(benchmarks)}
    )


class _RowError(Exception):
    def __init__(self, code: IssueCode, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _text(row: dict, key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _RowError(IssueCode.MISSING_FIELD, f"missing or blank {key!r}")
    return value


def _decimal(row: dict, key: str) -> Decimal:
    value = row.get(key)
    if isinstance(value, bool) or value is None:
        raise _RowError(IssueCode.MISSING_FIELD, f"missing {key!r}")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation:
        raise _RowError(IssueCode.UNPARSEABLE_ROW, f"{key!r} is not a number") from None
    if not number.is_finite():
        raise _RowError(IssueCode.UNPARSEABLE_ROW, f"{key!r} is not finite")
    return number


def _positive(row: dict, key: str) -> Decimal:
    number = _decimal(row, key)
    if number <= 0:
        raise _RowError(IssueCode.NON_POSITIVE_VALUE, f"{key!r} must be > 0")
    return number


def _date(row: dict, key: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(_text(row, key))
    except ValueError:
        raise _RowError(IssueCode.UNPARSEABLE_ROW, f"{key!r} is not an ISO date") from None


def _currency(text: str) -> CurrencyCode:
    try:
        return CurrencyCode(text)
    except InvalidCurrencyCodeError:
        raise _RowError(IssueCode.UNPARSEABLE_ROW, f"bad currency code {text!r}") from None


class MockSyntheticAdapter:
    """One adapter instance serves every data kind of the synthetic source, by manifest."""

    adapter_version = "1.0.0"
    payload_formats = (MOCK_FORMAT,)

    def __init__(self, data_kind: DataKind, source_id: str = MOCK_SOURCE_ID):
        """`source_id`: the registered (synthetic) source whose files this instance reads. A second mock source
        lets a test hold, say, a corporate-action FEED and an issuer FILING as two different sources."""
        if data_kind not in (
            DataKind.QUOTE, DataKind.FX, DataKind.CORPORATE_ACTION, DataKind.BENCHMARK
        ):
            raise ValueError(f"mock adapter does not serve {data_kind}")
        self.data_kind = data_kind
        self.source_id = source_id
        self.adapter_id = f"{source_id}.{data_kind.value.lower()}"

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        issues: List[AdapterIssue] = []
        try:
            doc = json.loads(payload.decode("utf-8"), parse_float=Decimal)
            if not isinstance(doc, dict):
                raise ValueError("top level must be an object")
        except (UnicodeDecodeError, ValueError) as exc:
            return AdapterOutput(issues=(AdapterIssue("file", IssueCode.UNKNOWN_FORMAT, str(exc)),))
        section = {
            DataKind.QUOTE: "quotes", DataKind.FX: "fx",
            DataKind.CORPORATE_ACTION: "actions", DataKind.BENCHMARK: "benchmarks",
        }[self.data_kind]
        rows = doc.get(section, [])
        if not isinstance(rows, list):
            return AdapterOutput(issues=(AdapterIssue(section, IssueCode.UNKNOWN_FORMAT,
                                                      "section must be a list"),))
        # Tests V0 and V0-FX (market-data/1.16 section 11 items 25 and 34) run on the synthetic route too (review HIGH-1, 2026-10-25): the rest of V0 runs on
        # every mock file, and a method label that says "in every market" must not have a route where the duplicate-date half does not run.
        # Prices: the adapter LISTS what each row states and ingestion judges it per listing, after identity resolution (Addendum A.4); the aliases (mic, ticker)
        # of one listing are the same series. FX: judged here, per (pair, date).
        statements: Optional[Tuple[DatedStatement, ...]] = None
        if self.data_kind is DataKind.QUOTE:
            statements = self._dated_statements(rows)
        elif self.data_kind is DataKind.FX:
            contradicted, duplicate_issues = self._duplicated_fixings(rows)
            issues.extend(duplicate_issues)
            if contradicted:
                return AdapterOutput(issues=tuple(issues), contradicted=contradicted)
        out: List[object] = []
        for index, row in enumerate(rows):
            ref = f"{section}[{index}]"
            try:
                if not isinstance(row, dict):
                    raise _RowError(IssueCode.UNPARSEABLE_ROW, "row must be an object")
                out.append(self._row(manifest, ref, row))
            except _RowError as exc:
                issues.append(AdapterIssue(ref, exc.code, exc.detail))
            except (ObservationRuleError, LedgerEventRuleError, TypeError, ValueError) as exc:
                issues.append(AdapterIssue(ref, IssueCode.CONTRACT_VIOLATION, str(exc)))
        issues_t = tuple(issues)
        if self.data_kind is DataKind.QUOTE:
            return AdapterOutput(quotes=tuple(out), issues=issues_t, dated_statements=statements)  # type: ignore[arg-type]
        if self.data_kind is DataKind.FX:
            return AdapterOutput(fx=tuple(out), issues=issues_t)  # type: ignore[arg-type]
        if self.data_kind is DataKind.CORPORATE_ACTION:
            return AdapterOutput(actions=tuple(out), issues=issues_t)  # type: ignore[arg-type]
        return AdapterOutput(benchmarks=tuple(out), issues=issues_t)  # type: ignore[arg-type]

    # -- Tests V0 and V0-FX: a date stated twice ---------------------------------------
    @staticmethod
    def _parsed_date(row: object) -> Optional[datetime.date]:
        """The row's date as a date, in any form `date.fromisoformat` reads (`2025-01-07`, `20250107`), else None. The DATE decides, not its spelling."""
        if not isinstance(row, dict):
            return None
        value = row.get("date")
        if not isinstance(value, str):
            return None
        try:
            return datetime.date.fromisoformat(value.strip())
        except ValueError:
            return None

    def _dated_statements(self, rows: list) -> Tuple[DatedStatement, ...]:
        """Test V0 (1.16): one `DatedStatement` for every row whose date parses and which names a (mic, ticker), whatever its other fields and its values (a row
        whose date parses but whose close is bad still states that session). A row with no readable date states nothing: its row reader refuses it alone.
        Ingestion counts them per listing, after resolution, so two aliases of one listing on one date are one series stated twice."""
        found: List[DatedStatement] = []
        for row in rows:
            day = self._parsed_date(row)
            mic, ticker = (row.get("mic"), row.get("ticker")) if isinstance(row, dict) else (None, None)
            if day is None or not isinstance(mic, str) or not mic.strip() or not isinstance(ticker, str) or not ticker.strip():
                continue
            found.append(DatedStatement(ExternalIdentifiers(mic=mic, ticker=ticker), day, f"{ticker}@{day.isoformat()}"))
        return tuple(sorted(found, key=lambda s: s.ref))

    def _duplicated_fixings(self, rows: list) -> Tuple[Tuple[ContradictedSeries, ...], List[AdapterIssue]]:
        """Test V0-FX (1.16): a fixing date stated twice excludes EVERY currency series read from the file, whole. A mock FX file is one row per (base, quote,
        date), not one row per date (an ECB row holds all currencies), so the key here is the pair's parsed date: one pair on one date twice. Equal rows count.
        Which statement stands is not decided by order or value (section 11 'Must not decide'); the adapter then outputs no rate at all."""
        seen: Dict[Tuple[str, str, datetime.date], int] = {}
        quote_currencies: set = set()
        for row in rows:
            day = self._parsed_date(row)
            if day is None or not isinstance(row, dict):
                continue
            try:
                base, quote = _currency(_text(row, "base")), _currency(_text(row, "quote"))
            except _RowError:
                continue
            quote_currencies.add(quote.code)
            seen[(base.code, quote.code, day)] = seen.get((base.code, quote.code, day), 0) + 1
        repeated = tuple(sorted({d for (_, _, d), n in seen.items() if n > 1}))
        if not repeated:
            return (), []
        named = tuple(sorted({f"{base}/{quote}" for (base, quote, _), n in seen.items() if n > 1}))
        issues = [AdapterIssue(d.isoformat(), IssueCode.DUPLICATE_SESSION_DATE,
                               f"a fixing stated twice ({', '.join(named)}): every currency series of the file is excluded (Test V0-FX)") for d in repeated]
        return tuple(ContradictedSeries("V0_FX_DUPLICATE_DATE", "V0_FX_DUPLICATE_DATE", repeated, currency=code, names=named)
                     for code in sorted(quote_currencies)), issues

    # -- rows -------------------------------------------------------------------------
    def _declared_currency(self, manifest: FileManifest) -> CurrencyCode:
        if manifest.declared_currency is None:
            raise _RowError(IssueCode.UNDECLARED_CURRENCY, "manifest declares no currency")
        return manifest.declared_currency

    def _row(self, manifest: FileManifest, ref: str, row: dict) -> object:
        lineage = lineage_for(manifest, self, ref)
        timing = timing_for(manifest)
        if self.data_kind is DataKind.QUOTE:
            volume = None if row.get("volume") is None else _decimal(row, "volume")
            return UnresolvedQuote(
                identifiers=ExternalIdentifiers(mic=_text(row, "mic"), ticker=_text(row, "ticker")),
                value_date=_date(row, "date"),
                price=_positive(row, "close"),
                currency=self._declared_currency(manifest),
                timing=timing,
                lineage=lineage_for(manifest, self, ref, source_value_text=str(row["close"])),
                volume=volume,
            )
        if self.data_kind is DataKind.FX:
            return FXObservation(
                base_currency=_currency(_text(row, "base")),
                quote_currency=_currency(_text(row, "quote")),
                value_date=_date(row, "date"),
                rate=_positive(row, "rate"),
                timing=timing,
                lineage=lineage_for(manifest, self, ref, source_value_text=str(row["rate"])),
                rate_basis=_text(row, "rate_basis"),
            )
        if self.data_kind is DataKind.CORPORATE_ACTION:
            return self._action(manifest, row, lineage, timing)
        points: Optional[object] = row.get("points")
        if not isinstance(points, list) or not points:
            raise _RowError(IssueCode.MISSING_FIELD, "benchmark needs points")
        built = tuple(
            BenchmarkPoint(_date(p, "date"), _decimal(p, "value")) for p in points
            if isinstance(p, dict)
        )
        if len(built) != len(points):
            raise _RowError(IssueCode.UNPARSEABLE_ROW, "every point must be an object")
        try:
            kind = BenchmarkValueKind(_text(row, "value_kind"))
        except ValueError:
            raise _RowError(IssueCode.UNPARSEABLE_ROW, "unknown value_kind") from None
        return BenchmarkSeries(
            benchmark_id=_text(row, "benchmark_id"),
            provider=_text(row, "provider"),
            points=built,
            value_kind=kind,
            currency=self._declared_currency(manifest),
            timing=timing,
            lineage=lineage,
            licensing=licensing_for(manifest),
        )

    def _action(self, manifest, row, lineage, timing) -> UnresolvedCorporateAction:  # type: ignore[no-untyped-def]
        kind = _text(row, "type")
        ids = ExternalIdentifiers(mic=_text(row, "mic"), ticker=_text(row, "ticker"))
        when = _date(row, "date")  # the ex-date for a SPLIT or CASH_DIVIDEND
        try:
            action = CorporateActionType(kind)
        except ValueError:
            # Ruling 7.1: anything else is STORED as unsupported, with its label, and flagged.
            return UnresolvedCorporateAction(ids, CorporateActionType.UNSUPPORTED, when, timing,
                                             lineage, unsupported_label=kind)
        if action is CorporateActionType.SPLIT:
            ratio = SplitRatio(_positive(row, "new_units"), _positive(row, "old_units"))
            return UnresolvedCorporateAction(ids, action, when, timing, lineage, split_ratio=ratio)
        if action is CorporateActionType.SYMBOL_CHANGE:
            return UnresolvedCorporateAction(ids, action, when, timing, lineage,
                                             old_ticker=_text(row, "old_ticker"),
                                             new_ticker=_text(row, "new_ticker"))
        if action is CorporateActionType.UNSUPPORTED:
            return UnresolvedCorporateAction(ids, action, when, timing, lineage,
                                             unsupported_label=_text(row, "label"))
        money = Money(_positive(row, "amount"), _currency(_text(row, "currency")))
        record = None if row.get("record_date") is None else _date(row, "record_date")
        paid = None if row.get("paid_currency") is None else _currency(_text(row, "paid_currency"))
        issuer_rate = None if row.get("issuer_fx_rate") is None else _positive(row, "issuer_fx_rate")
        paid_amount = None if row.get("paid_amount") is None else _positive(row, "paid_amount")
        return UnresolvedCorporateAction(
            ids, action, when, timing, lineage, amount_per_unit=money,
            pay_date=_date(row, "pay_date"), record_date=record, paid_currency=paid,
            issuer_fx_rate=issuer_rate, paid_amount=paid_amount)
