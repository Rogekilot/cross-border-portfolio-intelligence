"""`frankfurter.ecb.fx`: ECB euro reference rates as served by the Frankfurter API, payload
format `frankfurter_json_timeseries/1`. A pure translator (Tech Plan §15.2).

Structure, from the first real file (2026-10-01; never committed, only synthetic files with
this structure are):

    {"amount":1.0,"base":"EUR","start_date":"2025-01-02","end_date":"2025-01-08",
     "rates":{"2025-01-02":{"CNY":7.5338,"HKD":8.0261,"USD":1.0321}, ...}}

market-data/1.0 §1: quotes are stored EXACTLY as published, EUR-based (units of currency per
1 EUR), as `FXObservation(base=EUR, quote=ccy)`. Nothing is inverted, crossed, rebased or
rounded here; a payload whose base is not EUR or whose amount is not 1 (a re-based quote that
Frankfurter computed and rounded itself, Ruling 1.3) is REFUSED. Numbers are read from the JSON
text as exact `Decimal`s (never a float). The date is the payload's own date (Frankfurter
returns the previous fixing under that fixing's own date for a non-fixing day: Ruling 1.6,
§12 item 6); the requested date is never used.

`observed_at` and `source_time` are the fixing date at 14:10 Europe/Berlin (1.8; 14:15 through 1.7) (market-data/1.0
§11 item 1; the minute is an external fact the human confirms, §12). The zone is the IANA
`Europe/Berlin`, never a fixed offset. This needs the system tz database (stdlib `zoneinfo`).

The ECB's own history file is the primary FX source; Frankfurter is a re-server, so a match with
it is a transport check, not independent corroboration (Ruling 4.1). Its upstream is the ECB.
"""

from __future__ import annotations

import datetime
import json
from datetime import time as TimeOfDay
from decimal import Decimal
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

from domain.currency import CurrencyCode, InvalidCurrencyCodeError
from marketdata.adapters.base import (
    AdapterIssue,
    AdapterOutput,
    ContradictedSeries,
    IssueCode,
    lineage_for,
)
from marketdata.contracts import DataDelayStatus, FXObservation, ObservationRuleError, SourceTiming
from marketdata.manifest import DataKind, FileManifest

SOURCE_ID = "frankfurter.ecb"
PAYLOAD_FORMAT = "frankfurter_json_timeseries/1"
BASE = CurrencyCode("EUR")
FIXING_ZONE = ZoneInfo("Europe/Berlin")
FIXING_TIME = TimeOfDay(14, 10)  # concertation time, market-data/1.8 (a constant, not a clock read); confirm per §12
RATE_BASIS = "ECB euro reference rate (EUR-based, as published)"


class FrankfurterFxAdapter:
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

        # Test V0-FX (market-data/1.16 section 11 item 34, the Quant's finding F-2): the rule is not limited to the ECB's own format. `json.loads` keeps the LAST
        # value of a repeated object name, which would serve one of two statements of a fixing by the parser's order, so every object's pairs are kept here.
        pairs_of: Dict[int, List[Tuple[str, object]]] = {}

        def keep_pairs(pairs: List[Tuple[str, object]]) -> Dict[str, object]:
            obj = dict(pairs)
            pairs_of[id(obj)] = list(pairs)
            return obj

        try:
            doc = json.loads(payload.decode("utf-8"), parse_float=Decimal, object_pairs_hook=keep_pairs)
            rates = doc["rates"]
            base, amount = doc["base"], doc["amount"]
        except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
            return refuse(IssueCode.UNKNOWN_FORMAT, f"unreadable payload: {type(exc).__name__}")
        if base != "EUR" or Decimal(str(amount)) != 1 or not isinstance(rates, dict):
            return refuse(IssueCode.UNKNOWN_FORMAT,
                          "only EUR-based quotes with amount 1 are accepted; never a re-based quote")
        observations: List[FXObservation] = []
        issues: List[AdapterIssue] = []
        # Every object level the adapter reads is read with its repeated names kept (review MEDIUM-3, 2026-10-25). The top level first: `json.loads`
        # keeps the LAST of a repeated `rates` member, which would silently drop or override the dates of the earlier one. The dates of EVERY `rates`
        # member are counted together, so a date stated in two members is a date stated twice (Test V0-FX, item 34).
        top = pairs_of.get(id(doc), [])
        rates_members = [value for name, value in top if name == "rates"]
        # a date stated twice: the same name twice, or two names that parse to one date (`2025-01-02` and `20250102`)
        counts: Dict[datetime.date, int] = {}
        currencies: set = set()
        stated_twice: set = set()  # a currency stated twice for one date (`{"USD":1.08,"USD":9.99}`, or `usd` and `USD`): LOW-4, Addendum A.3
        twice_on: set = set()
        for member in rates_members:
            for name, value in pairs_of.get(id(member), []):
                try:
                    day = datetime.date.fromisoformat(name)
                except ValueError:
                    continue  # a name that is no date states nothing: it is refused below as `bad date key`
                counts[day] = counts.get(day, 0) + 1
                if id(value) in pairs_of:
                    codes: List[str] = []
                    for code, _ in pairs_of[id(value)]:
                        try:
                            codes.append(CurrencyCode(code).code)
                        except InvalidCurrencyCodeError:
                            pass  # not a currency: refused below, alone
                    currencies.update(codes)
                    for code in set(codes):
                        if codes.count(code) > 1:
                            stated_twice.add(code)
                            twice_on.add(day)
        repeated = tuple(sorted({d for d, n in counts.items() if n > 1} | twice_on))
        if repeated:
            named = tuple(sorted(stated_twice))
            return AdapterOutput(
                issues=tuple(AdapterIssue(d.isoformat(), IssueCode.DUPLICATE_SESSION_DATE,
                                          "a fixing stated twice" + (f" (currency {', '.join(named)})" if d in twice_on else "")
                                          + ": every currency series of the file is excluded (Test V0-FX)") for d in repeated),
                contradicted=tuple(ContradictedSeries("V0_FX_DUPLICATE_DATE", "V0_FX_DUPLICATE_DATE", repeated, currency=code, names=named)
                                   for code in sorted(currencies)))
        # A repeated top-level name that the adapter reads and that states no date twice (a second `rates` member with other dates, or a second `base` or
        # `amount`): the method text does not say which statement stands, and the parser's order must not decide. The file is REFUSED, fail closed. This is a
        # choice the contract does not cover (reported to the Quant); the repeated-date case above is the text's own rule.
        top_names = [name for name, _ in top]
        for name in ("rates", "base", "amount"):
            if top_names.count(name) > 1:
                return refuse(IssueCode.UNKNOWN_FORMAT,
                              f"the top-level member {name!r} is stated more than once: the file is refused, no statement is chosen by order")
        for day_text in sorted(rates):
            quotes = rates[day_text]
            try:
                day = datetime.date.fromisoformat(day_text)
            except ValueError:
                issues.append(AdapterIssue(day_text, IssueCode.UNPARSEABLE_ROW, "bad date key"))
                continue
            instant = datetime.datetime.combine(day, FIXING_TIME, tzinfo=FIXING_ZONE)
            timing = SourceTiming(source_time=instant, delay_status=DataDelayStatus.END_OF_DAY)
            for code in sorted(quotes):
                ref = f"{day_text}/{code}"
                try:
                    rate = quotes[code]
                    if not isinstance(rate, Decimal):
                        raise ValueError("rate is not a JSON number")
                    observations.append(FXObservation(
                        base_currency=BASE, quote_currency=CurrencyCode(code), value_date=day,
                        rate=rate, timing=timing,
                        lineage=lineage_for(manifest, self, ref, source_value_text=str(rate)),
                        rate_basis=RATE_BASIS, observed_at=instant))
                except (ValueError, InvalidCurrencyCodeError, ObservationRuleError) as exc:
                    issues.append(AdapterIssue(ref, IssueCode.UNPARSEABLE_ROW, type(exc).__name__))
        return AdapterOutput(fx=tuple(observations), issues=tuple(issues))
