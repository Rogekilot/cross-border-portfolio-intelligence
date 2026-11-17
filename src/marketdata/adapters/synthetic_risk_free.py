"""`synthetic.riskfree`: a deterministic adapter for SYNTHETIC risk-free rate files (CP4b-2; `risk/1.0` section 4; tech plan 17.4.3, 17.15).

It translates a saved SYNTHETIC file (payload format `synthetic_risk_free_json/1`) into a `RiskFreeSeries` through exactly the interface a real source adapter uses. Deterministic: no clock, no randomness; the bytes
in are the facts out. `make_risk_free_payload` writes such bytes canonically, for tests. It is NOT a real source's parser: the real US Treasury adapter waits for a real file and the owner's attestation (tech plan 17.4.4).

Payload (JSON; numbers are read as exact Decimals, strings are accepted too). Every series states the whole `risk/1.0` Ruling 4.6 checklist; a missing field is an issue and no series is built from it:

    {"series": [{"series_id", "name", "provider", "instrument", "tenor_weeks", "quote_type" (SIMPLE_YIELD|BANK_DISCOUNT),
                 "day_count_basis" (360|365), "unit" (PERCENT|DECIMAL), "decimals_published", "date_semantics", "calendar_id",
                 "revision_policy" (NOT_REVISED|REVISED|UNKNOWN),
                 "points": [{"date", "rate", "term_days" (BANK_DISCOUNT only)}]}]}

The series' currency comes from the manifest (`declared_currency`); an adapter never infers one.
"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal, InvalidOperation
from typing import List, Tuple

from marketdata.adapters.base import (
    AdapterIssue,
    AdapterOutput,
    IssueCode,
    licensing_for,
    lineage_for,
    timing_for,
)
from marketdata.canonical import canonical_bytes
from marketdata.contracts import (
    ObservationRuleError,
    RateUnit,
    RevisionPolicy,
    RiskFreePoint,
    RiskFreeQuoteType,
    RiskFreeSeries,
)
from marketdata.manifest import DataKind, FileManifest

SOURCE_ID = "synthetic.riskfree"
PAYLOAD_FORMAT = "synthetic_risk_free_json/1"
_SERIES_KEYS = {"series_id", "name", "provider", "instrument", "tenor_weeks", "quote_type", "day_count_basis", "unit", "decimals_published", "date_semantics", "calendar_id",
                "revision_policy", "points"}


def make_risk_free_payload(series: Tuple[dict, ...]) -> bytes:
    """Canonical bytes of a synthetic risk-free payload. Values given as Decimal or str."""
    return canonical_bytes({"series": list(series)})


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


def _integer(row: dict, key: str) -> int:
    value = row.get(key)
    if isinstance(value, bool) or value is None:
        raise _RowError(IssueCode.MISSING_FIELD, f"missing {key!r}")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation:
        raise _RowError(IssueCode.UNPARSEABLE_ROW, f"{key!r} is not a number") from None
    if not number.is_finite() or number != number.to_integral_value():
        raise _RowError(IssueCode.UNPARSEABLE_ROW, f"{key!r} must be an integer")
    return int(number)


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


def _date(row: dict, key: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(_text(row, key))
    except ValueError:
        raise _RowError(IssueCode.UNPARSEABLE_ROW, f"{key!r} is not an ISO date") from None


def _enum(enum_type, row: dict, key: str):  # type: ignore[no-untyped-def]
    try:
        return enum_type(_text(row, key))
    except ValueError:
        raise _RowError(IssueCode.UNPARSEABLE_ROW, f"unknown {key!r}") from None


class SyntheticRiskFreeAdapter:
    adapter_version = "1.0.0"
    payload_formats = (PAYLOAD_FORMAT,)
    data_kind = DataKind.RISK_FREE

    def __init__(self, source_id: str = SOURCE_ID):
        self.source_id = source_id
        self.adapter_id = f"{source_id}.risk_free"

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        issues: List[AdapterIssue] = []
        try:
            doc = json.loads(payload.decode("utf-8"), parse_float=Decimal)
            if not isinstance(doc, dict):
                raise ValueError("top level must be an object")
        except (UnicodeDecodeError, ValueError) as exc:
            return AdapterOutput(issues=(AdapterIssue("file", IssueCode.UNKNOWN_FORMAT, str(exc)),))
        rows = doc.get("series", [])
        if not isinstance(rows, list):
            return AdapterOutput(issues=(AdapterIssue("series", IssueCode.UNKNOWN_FORMAT, "section must be a list"),))
        out: List[RiskFreeSeries] = []
        for index, row in enumerate(rows):
            ref = f"series[{index}]"
            try:
                if not isinstance(row, dict):
                    raise _RowError(IssueCode.UNPARSEABLE_ROW, "row must be an object")
                out.append(self._series(manifest, ref, row))
            except _RowError as exc:
                issues.append(AdapterIssue(ref, exc.code, exc.detail))
            except (ObservationRuleError, TypeError, ValueError) as exc:
                issues.append(AdapterIssue(ref, IssueCode.CONTRACT_VIOLATION, str(exc)))
        return AdapterOutput(risk_free=tuple(out), issues=tuple(issues))

    def _series(self, manifest: FileManifest, ref: str, row: dict) -> RiskFreeSeries:
        unknown = sorted(set(row) - _SERIES_KEYS)
        if unknown:
            raise _RowError(IssueCode.UNKNOWN_FORMAT, f"unknown key(s) {unknown}")
        if manifest.declared_currency is None:
            raise _RowError(IssueCode.UNDECLARED_CURRENCY, "manifest declares no currency")
        points = row.get("points")
        if not isinstance(points, list) or not points:
            raise _RowError(IssueCode.MISSING_FIELD, "a risk-free series needs points")
        built: List[RiskFreePoint] = []
        for p in points:
            if not isinstance(p, dict):
                raise _RowError(IssueCode.UNPARSEABLE_ROW, "every point must be an object")
            term = None if p.get("term_days") is None else _integer(p, "term_days")
            built.append(RiskFreePoint(_date(p, "date"), _decimal(p, "rate"), term))
        return RiskFreeSeries(
            series_id=_text(row, "series_id"), name=_text(row, "name"), provider=_text(row, "provider"), currency=manifest.declared_currency,
            instrument=_text(row, "instrument"), tenor_weeks=_integer(row, "tenor_weeks"), quote_type=_enum(RiskFreeQuoteType, row, "quote_type"),
            day_count_basis=_integer(row, "day_count_basis"), unit=_enum(RateUnit, row, "unit"), decimals_published=_integer(row, "decimals_published"),
            date_semantics=_text(row, "date_semantics"), calendar_id=_text(row, "calendar_id"), revision_policy=_enum(RevisionPolicy, row, "revision_policy"),
            points=tuple(built), timing=timing_for(manifest), lineage=lineage_for(manifest, self, ref), licensing=licensing_for(manifest))
