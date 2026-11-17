"""`calendar.manual.calendar`: the hand-made calendar file of market-data/1.2 Ruling 5.3 (session
days per exchange; ECB fixing days). Payload format `finweb_calendar_json/1`. A pure translator.

The file is made BY A HUMAN from the publisher's notices (an exchange circular, the ECB's TARGET
closing days). It is never derived from a price or rate file (that would be circular: Test V0 and the
freshness count would then always say "nothing missed"). It is registered like any file:

    python -m marketdata_tools.download register-file --path cal.json --source calendar.manual \\
        --kind CALENDAR --format finweb_calendar_json/1 --adjustment RAW --label NYSE_2026 \\
        --ext json --identifiers NYSE_SESSIONS

which hashes it and writes its lineage manifest; the loader verifies the hash on every read.

Format (one calendar per file; every key is required except where stated; an unknown key refuses
the file):

    {
      "schema": "finweb.marketdata.calendar/1",
      "calendar_id": "NYSE_SESSIONS",
      "kind": "EXCHANGE_SESSIONS",                 // or "ECB_FIXINGS"
      "applies_to": ["XNYS", "XNAS"],              // MICs the calendar governs; ["ECB"] for the ECB
      "timezone": "America/New_York",              // IANA; must be the Ruling 2.2 zone of every MIC
      "coverage": {"from": "2026-01-01", "to": "2026-12-31"},   // ONE contiguous closed interval
      "dates": ["2026-01-02", "2026-01-05", ...],  // EXPLICIT sorted list of actual session / fixing dates
      "actual_through": "2026-09-30",              // last date checked as actual, not scheduled
      "close": {"default": "16:00",                // EXCHANGE_SESSIONS only
                "overrides": [{"date": "2026-11-27", "time": "13:00"}]},
      "fixing": {"time": "14:10", "publication": "16:00"},      // ECB_FIXINGS only
      "publication": {"time": "15:30"},            // RATE_PUBLICATIONS only (risk/1.0 Ruling 4.5): `kind` "RATE_PUBLICATIONS", `applies_to` the risk-free SERIES ids,
                                                   // `timezone` the publisher's own IANA zone, `dates` the publication dates
      "evidence": "publisher reference for the holiday / closure list",
      "prepared_by": "name",
      "prepared_on": "2026-10-02",
      "version": "label of this version"
    }

Inside the coverage the list is complete (a date is a session iff it is listed). Outside it nothing
is known: a count over an uncovered interval is impossible and the result is freshness UNKNOWN with
the cause CALENDAR_COVERAGE_GAP. Weekdays are never inferred. The content hash is computed by the
loader. A MIC may be governed by exactly one calendar in the market-data version.
"""

from __future__ import annotations

import datetime
import json
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from marketdata.adapters.base import AdapterIssue, AdapterOutput, IssueCode, lineage_for
from marketdata.contracts import CalendarDays, CalendarKind, ObservationRuleError
from marketdata.manifest import DataKind, FileManifest
from marketdata.profiles import ECB_FIXING_TIME, ECB_PUBLICATION_TIME, EXCHANGE_ZONES

SOURCE_ID = "calendar.manual"
PAYLOAD_FORMAT = "finweb_calendar_json/1"
SCHEMA = "finweb.marketdata.calendar/1"
_COMMON_KEYS = {"schema", "calendar_id", "kind", "applies_to", "timezone", "coverage", "dates",
                "actual_through", "evidence", "prepared_by", "prepared_on", "version"}
_EXCHANGE_KEYS = _COMMON_KEYS | {"close"}
_ECB_KEYS = _COMMON_KEYS | {"fixing"}
_RATE_KEYS = _COMMON_KEYS | {"publication"}  # RATE_PUBLICATIONS (risk/1.0 Ruling 4.5): `applies_to` names the risk-free SERIES ids, and `publication.time` is the nominal publication time


class CalendarFormatError(ValueError):
    pass


def _date(value: Any, what: str) -> datetime.date:
    if not isinstance(value, str):
        raise CalendarFormatError(f"{what} must be an ISO date string")
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise CalendarFormatError(f"{what} is not an ISO date: {value!r}") from None


def _time(value: Any, what: str) -> datetime.time:
    if not isinstance(value, str):
        raise CalendarFormatError(f"{what} must be a time string")
    try:
        return datetime.time.fromisoformat(value)
    except ValueError:
        raise CalendarFormatError(f"{what} is not a time: {value!r}") from None


def _strings(value: Any, what: str) -> Tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise CalendarFormatError(f"{what} must be a list of strings")
    return tuple(value)


class CalendarFileAdapter:
    adapter_id = "calendar.manual.calendar"
    adapter_version = "0.1.0"
    source_id = SOURCE_ID
    data_kind = DataKind.CALENDAR
    payload_formats = (PAYLOAD_FORMAT,)

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        try:
            calendar = self._parse(manifest, payload)
        except (CalendarFormatError, ObservationRuleError) as exc:
            return AdapterOutput(issues=(AdapterIssue("file", IssueCode.CALENDAR_INVALID, str(exc)),))
        return AdapterOutput(calendars=(calendar,))

    def _parse(self, manifest: FileManifest, payload: bytes) -> CalendarDays:
        try:
            doc: Dict[str, Any] = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise CalendarFormatError("the file is not UTF-8 JSON") from None
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            raise CalendarFormatError(f"schema must be {SCHEMA!r}")
        try:
            kind = CalendarKind(doc.get("kind"))
        except ValueError:
            raise CalendarFormatError("kind must be EXCHANGE_SESSIONS, ECB_FIXINGS or RATE_PUBLICATIONS") from None
        allowed = {CalendarKind.EXCHANGE_SESSIONS: _EXCHANGE_KEYS, CalendarKind.ECB_FIXINGS: _ECB_KEYS, CalendarKind.RATE_PUBLICATIONS: _RATE_KEYS}[kind]
        unknown = sorted(set(doc) - allowed)
        missing = sorted(allowed - set(doc))
        if unknown:
            raise CalendarFormatError(f"unknown key(s) {unknown}")
        if missing:
            raise CalendarFormatError(f"missing key(s) {missing}")
        calendar_id = doc["calendar_id"]
        applies_to = _strings(doc["applies_to"], "applies_to")
        timezone = doc["timezone"]
        if not isinstance(calendar_id, str) or not isinstance(timezone, str):
            raise CalendarFormatError("calendar_id and timezone must be strings")
        if kind is CalendarKind.RATE_PUBLICATIONS:
            try:
                ZoneInfo(timezone)  # a publication calendar names the publisher's own IANA zone; there is no MIC to read it from
            except (ZoneInfoNotFoundError, ValueError):
                raise CalendarFormatError(f"{timezone!r} is not an IANA time zone") from None
        else:
            for mic in applies_to:  # Ruling 2.2: each MIC has one IANA zone; the file must agree
                expected = EXCHANGE_ZONES.get(mic)
                if expected is None:
                    raise CalendarFormatError(f"{mic!r} has no zone in the convention (Ruling 2.2)")
                if expected != timezone:
                    raise CalendarFormatError(f"{mic} is in zone {expected}, the file says {timezone}")
        coverage = doc["coverage"]
        if not isinstance(coverage, dict) or set(coverage) != {"from", "to"}:
            raise CalendarFormatError("coverage must be exactly {from, to}: one contiguous interval")
        if not isinstance(doc["dates"], list):
            raise CalendarFormatError("dates must be an explicit list")
        dates = tuple(_date(d, "dates[]") for d in doc["dates"])
        default_close = None
        early: List[Tuple[datetime.date, datetime.time]] = []
        fixing = publication = None
        if kind is CalendarKind.EXCHANGE_SESSIONS:
            close = doc["close"]
            if not isinstance(close, dict) or not set(close) <= {"default", "overrides"} or "default" not in close:
                raise CalendarFormatError("close must be {default, overrides?}")
            default_close = _time(close["default"], "close.default")
            overrides = close.get("overrides", [])
            if not isinstance(overrides, list):
                raise CalendarFormatError("close.overrides must be a list")
            for item in overrides:
                if not isinstance(item, dict) or set(item) != {"date", "time"}:
                    raise CalendarFormatError("each override must be {date, time}")
                early.append((_date(item["date"], "override date"), _time(item["time"], "override time")))
        elif kind is CalendarKind.RATE_PUBLICATIONS:
            pub = doc["publication"]
            if not isinstance(pub, dict) or set(pub) != {"time"}:
                raise CalendarFormatError("publication must be {time}")
            publication = _time(pub["time"], "publication.time")
        else:
            fx = doc["fixing"]
            if not isinstance(fx, dict) or set(fx) != {"time", "publication"}:
                raise CalendarFormatError("fixing must be {time, publication}")
            fixing, publication = _time(fx["time"], "fixing.time"), _time(fx["publication"], "fixing.publication")
            if fixing != ECB_FIXING_TIME or publication != ECB_PUBLICATION_TIME:
                raise CalendarFormatError(
                    "the ECB fixing/publication times differ from the convention (14:10/16:00): "
                    "a different time is a new convention version, not a calendar edit")
        for name in ("evidence", "prepared_by", "version"):
            if not isinstance(doc[name], str) or not doc[name].strip():
                raise CalendarFormatError(f"{name} must be non-blank text (the provenance of the file)")
        return CalendarDays(
            calendar_id=calendar_id, kind=kind, applies_to=applies_to, timezone=timezone,
            covers_from=_date(coverage["from"], "coverage.from"), covers_to=_date(coverage["to"], "coverage.to"),
            dates=dates, actual_through=_date(doc["actual_through"], "actual_through"),
            evidence=doc["evidence"], prepared_by=doc["prepared_by"],
            prepared_on=_date(doc["prepared_on"], "prepared_on"), version_label=doc["version"],
            lineage=lineage_for(manifest, self, calendar_id), default_close=default_close,
            early_closes=tuple(early), fixing_time=fixing, publication_time=publication)
