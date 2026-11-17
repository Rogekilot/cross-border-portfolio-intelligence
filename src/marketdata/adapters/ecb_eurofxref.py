"""`ecb.eurofxref.fx`: the ECB's OWN published euro reference-rate history file (`eurofxref-hist`,
CSV), payload format `ecb_eurofxref_hist_csv/1`. The PREFERRED FX source (market-data/1.2 Ruling
1.1a): the publisher's own record of the quantity Ruling 1.1 defines. A pure translator (Tech Plan
§15.2).

Structure (RECALLED, profile status MEMORY: no real file has been seen, so this is untested against
the ECB's actual bytes; only synthetic files of this structure are tested; the first real file must
be profiled by Appendix A.4 before the source is admitted):

    Date,USD,JPY,BGN,...,
    2025-01-08,1.0305,162.79,1.9558,...,
    2025-01-07,1.0393,162.65,1.9558,...,

- newest first (the parser sorts and never assumes an order); a trailing comma gives an empty last
  column that is ignored; an unavailable value is the token `N/A`, which is NOT an observation
  (Ruling 1.6) and is never filled;
- quotes are units of currency per 1 EUR, stored EXACTLY as the published decimal text, base EUR
  (Ruling 1.1): never inverted, crossed, rebased or rounded here;
- the date is the row's own date (Ruling 2.2: the source's local date label), and the instant is that
  date at 14:10 Europe/Berlin (market-data/1.8; 14:15 through 1.7) (IANA zone, never a fixed offset).

READ WINDOW. The file holds the whole history. The manifest's `source_identifiers` name the currency
columns to read (empty: all), and its `request` pairs `read_start` / `read_end` (ISO dates, both
optional) name the rows to read. This is a declared selection of what to translate; the saved bytes
are exactly the ECB's. Nothing outside the window becomes an observation, and no row is silently
changed.
"""

from __future__ import annotations

import csv
import datetime
import io
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set

from domain.currency import CurrencyCode, InvalidCurrencyCodeError
from marketdata.adapters.base import AdapterIssue, AdapterOutput, ContradictedSeries, IssueCode, lineage_for
from marketdata.contracts import DataDelayStatus, FXObservation, ObservationRuleError, SourceTiming
from marketdata.manifest import DataKind, FileManifest
from marketdata.profiles import ecb_fixing_instant

SOURCE_ID = "ecb.eurofxref"
PAYLOAD_FORMAT = "ecb_eurofxref_hist_csv/1"
BASE = CurrencyCode("EUR")
MISSING_TOKEN = "N/A"
RATE_BASIS = "ECB euro reference rate (EUR-based, as published)"


def _window(manifest: FileManifest) -> Optional[tuple]:
    request = dict(manifest.request)
    try:
        start = datetime.date.fromisoformat(request["read_start"]) if request.get("read_start") else None
        end = datetime.date.fromisoformat(request["read_end"]) if request.get("read_end") else None
    except ValueError:
        return None
    return start, end


class EcbEurofxrefFxAdapter:
    """`source_id` defaults to the real source; a synthetic fixture passes its own synthetic id (the format stays
    this one's)."""

    adapter_version = "0.1.0"
    data_kind = DataKind.FX
    payload_formats = (PAYLOAD_FORMAT,)

    def __init__(self, source_id: str = SOURCE_ID):
        self.source_id = source_id
        self.adapter_id = f"{source_id}.fx"

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        def refuse(code: IssueCode, detail: str) -> AdapterOutput:
            return AdapterOutput(issues=(AdapterIssue("file", code, detail),))

        window = _window(manifest)
        if window is None:
            return refuse(IssueCode.UNKNOWN_FORMAT, "read_start/read_end in the manifest are not ISO dates")
        start, end = window
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            return refuse(IssueCode.UNKNOWN_FORMAT, str(exc))
        rows = [r for r in csv.reader(io.StringIO(text)) if any(cell.strip() for cell in r)]
        if not rows or rows[0][0].strip() != "Date":
            return refuse(IssueCode.UNKNOWN_FORMAT, "the first column must be 'Date'")
        header = [h.strip() for h in rows[0]]
        columns: Dict[int, CurrencyCode] = {}
        issues: List[AdapterIssue] = []
        wanted: Set[str] = set(manifest.source_identifiers)
        for index, name in enumerate(header[1:], start=1):
            if not name:
                continue  # the trailing comma
            try:
                code = CurrencyCode(name)
            except InvalidCurrencyCodeError:
                issues.append(AdapterIssue(f"header/{name}", IssueCode.UNPARSEABLE_ROW, "not a currency code"))
                continue
            if wanted and name not in wanted:
                continue
            columns[index] = code
        for symbol in sorted(wanted - set(header)):
            issues.append(AdapterIssue(f"header/{symbol}", IssueCode.MISSING_FIELD,
                                       "a requested currency is not a column of the file"))
        # Test V0-FX (market-data/1.16 section 11 item 34): a fixing date stated twice fails EVERY currency series read from the file, whole,
        # whatever the values (equal rows count; a row where a currency is N/A counts), inside the read window or outside it, because it is
        # not a calendar question but a defect of the file's dating. The key is the parsed date. Keeping the first row (the rule before 1.16)
        # chose which of two statements of one fixing wins, which only a resolution record may do. The adapter outputs no rate and names the
        # series; ingestion keeps the file in M and the lineage says why.
        counts: Dict[datetime.date, int] = {}
        for row in rows[1:]:
            try:
                counted = datetime.date.fromisoformat(row[0].strip())
            except ValueError:
                continue
            counts[counted] = counts.get(counted, 0) + 1
        repeated = tuple(sorted(d for d, n in counts.items() if n > 1))
        # A fixing is a (date, currency), whatever the layout (Addendum A.1, A.3): a header that names a currency column we read TWICE states that currency
        # twice on EVERY date of the file, and which of the two columns wins is not a thing the file can tell (before this, both were read and the date
        # resolved to `NO_SELECTION`). It is the same rule: every currency series of the file is excluded, and the lineage names every date of the file and
        # the currency stated twice.
        read_codes = [code.code for code in columns.values()]
        stated_twice = tuple(sorted({c for c in read_codes if read_codes.count(c) > 1}))
        if stated_twice:
            repeated = tuple(sorted(set(repeated) | set(counts)))
            issues += [AdapterIssue(f"header/{c}", IssueCode.DUPLICATE_SESSION_DATE,
                                    f"the header names currency {c} more than once: it is stated twice on every date of the file") for c in stated_twice]
        if repeated:
            issues += [AdapterIssue(d.isoformat(), IssueCode.DUPLICATE_SESSION_DATE,
                                    "a fixing stated twice: every currency series of the file is excluded (Test V0-FX)")
                       for d in repeated]
            return AdapterOutput(issues=tuple(issues), contradicted=tuple(
                ContradictedSeries("V0_FX_DUPLICATE_DATE", "V0_FX_DUPLICATE_DATE", repeated, currency=code, names=stated_twice)
                for code in sorted(set(read_codes))))
        observations: List[FXObservation] = []
        unreported_missing = 0
        for line, row in enumerate(rows[1:], start=2):
            day_text = row[0].strip()
            try:
                day = datetime.date.fromisoformat(day_text)
            except ValueError:
                issues.append(AdapterIssue(f"line{line}", IssueCode.UNPARSEABLE_ROW, "bad date"))
                continue
            if (start is not None and day < start) or (end is not None and day > end):
                continue
            instant = ecb_fixing_instant(day)
            timing = SourceTiming(source_time=instant, delay_status=DataDelayStatus.END_OF_DAY)
            for index, code in columns.items():
                ref = f"{day_text}/{code.code}"
                cell = row[index].strip() if index < len(row) else ""
                if cell == MISSING_TOKEN or not cell:
                    if wanted:
                        issues.append(AdapterIssue(ref, IssueCode.MISSING_VALUE,
                                                   "published as N/A: not an observation (Ruling 1.6)"))
                    else:
                        unreported_missing += 1
                    continue
                try:
                    rate = Decimal(cell)
                    observations.append(FXObservation(
                        base_currency=BASE, quote_currency=code, value_date=day, rate=rate, timing=timing,
                        lineage=lineage_for(manifest, self, ref, source_value_text=cell),
                        rate_basis=RATE_BASIS, observed_at=instant))
                except (InvalidOperation, ObservationRuleError):
                    issues.append(AdapterIssue(ref, IssueCode.UNPARSEABLE_ROW, "not a positive decimal rate"))
        if unreported_missing:
            issues.append(AdapterIssue("file", IssueCode.MISSING_VALUE,
                                       f"{unreported_missing} N/A cell(s) read as not observed (Ruling 1.6)"))
        observations.sort(key=lambda o: (o.value_date, o.quote_currency.code))
        return AdapterOutput(fx=tuple(observations), issues=tuple(issues))
