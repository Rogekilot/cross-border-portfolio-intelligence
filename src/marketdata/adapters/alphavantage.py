"""`alphavantage.us.quotes`: US daily history saved from Alpha Vantage's `TIME_SERIES_DAILY` with
`datatype=csv`, payload format `alphavantage_csv_daily/1`. A pure translator (Tech Plan §15.2) over the
shared `daily_csv` rules (market-data/1.2 Appendix A.3, Example A-1; Rulings 2.4, 4.6, 2.5).

Structure, from the first real file (2026-10-01; never committed, only synthetic files with this
structure are):

    timestamp,open,high,low,close,volume
    2026-09-30,<open>,<high>,<low>,<close>,<volume>

- `timestamp` is the SESSION DATE as a local date label (Ruling 2.2), never an instant.
- Prices are TEXT_DECIMAL with 4 delivered decimals; the close is grid-checked against the US
  `price_max_dp`, open/high/low are NOT (sub-penny values are normal) and are used only in the
  Ruling 4.6 row check. Volume is integral shares, DECLARED_UNVERIFIED (no turnover column, so the
  Ruling 2.6 unit check cannot run and no rule may use its magnitude).
- Rows arrive newest first. The parser sorts by date and never assumes an order.
- A direct API: no wrapper library, the upstream and independence group are `alphavantage`.
- The symbol is the manifest's single `source_identifiers` entry (no symbol column): a vendor id
  scoped to this source, with no MIC inferred.
- ADJUSTMENT. The manifest of the first real file declares `UNDECLARED`. The profile documents
  `TIME_SERIES_DAILY` as as-traded (label source DECLARED: the owner's reading of the live documentation, PD-0066 decision 3;
  a vendor declaration, not a verification), so an UNDECLARED manifest of that call is read as RAW;
  an UNDECLARED manifest of any other function is not (verification-only rows). The series' label
  status is then set by ingestion and stays UNVERIFIABLE until a decisive split lies in its window.

A-SHARE ROUTE (market-data/1.15 section 7A; PENDING OBSERVATION, NOT ADMITTED). The same adapter serves `alphavantage.cn`
when it is constructed for that route: the vendor id is `dddddd.SHH` or `dddddd.SHZ`, the suffix gives the MIC (the only thing
inferred from it) and the six digits are the local code, so a listing is found by (MIC, code), never by the code alone and never
through a vendor-id row (`cn_identifiers`: the resolver is handed the MIC and the code only). The route's profile is TO_OBSERVE
with PROVISIONAL_UNOBSERVED fields: they let the parser run on SYNTHETIC files, and the admission gate (`profiles.gate_refusal`
and `profiles.listing_market_refusal`, applied by `ingest_file`, the store and the PostgreSQL projection) refuses every REAL
file of the source whatever its terms check says, and every REAL reading of a CN listing whatever source id its file carries.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Optional

from domain.currency import CurrencyCode
from marketdata.adapters.base import AdapterIssue, AdapterOutput, IssueCode
from marketdata.adapters.daily_csv import Columns, translate_daily_csv
from marketdata.contracts import AdjustmentStatus, ExternalIdentifiers
from marketdata.manifest import DataKind, FileManifest
from marketdata.profiles import source_profile

SOURCE_ID = "alphavantage.us"
CN_SOURCE_ID = "alphavantage.cn"
PAYLOAD_FORMAT = "alphavantage_csv_daily/1"
COLUMNS = Columns(date="timestamp", open="open", high="high", low="low", close="close", volume="volume")

# Ruling 7A.1 item 2 (DECLARED from the vendor's documentation as read for PD-0063): the suffix gives the MIC and nothing else
SUFFIX_TO_MIC = {"SHH": "XSHG", "SHZ": "XSHE"}
# Ruling 7A.1 item 5 (MEMORY, FLAG_ONLY): expected first digits of the code per suffix. A mismatch is flagged, never refused or resolved.
EXPECTED_FIRST_DIGITS = {"SHH": "569", "SHZ": "0123"}
_GRAMMAR = re.compile(r"[0-9]{6}\.(SHH|SHZ)", re.ASCII)  # six ASCII digits, a full stop, the suffix in upper case


@dataclass(frozen=True)
class CnVendorId:
    vendor_id: str
    code: str
    suffix: str
    mic: str

    @property
    def range_unexpected(self) -> bool:
        return self.code[0] not in EXPECTED_FIRST_DIGITS[self.suffix]


def parse_cn_vendor_id(text: str) -> Optional[CnVendorId]:
    """Ruling 7A.1 items 1 to 3: exactly six ASCII digits, '.', then SHH or SHZ in upper case; anything else is None
    (unresolved, never guessed). Whole-string match: no surrounding whitespace, no trailing newline."""
    if not isinstance(text, str) or _GRAMMAR.fullmatch(text) is None:
        return None
    code, suffix = text.split(".")
    return CnVendorId(text, code, suffix, SUFFIX_TO_MIC[suffix])


def cn_identifiers(parsed: CnVendorId) -> ExternalIdentifiers:
    """Ruling 7A.1 item 4: a CN listing is found by (MIC, six-digit local code) and by nothing else. These are the ONLY identifiers
    the route hands the resolver, so no stored vendor-id row (not even one scoped to this source, and not one that points at
    the other exchange's listing) can stand in for the (MIC, code) lookup: with no vendor id offered, the resolver has no
    vendor step to run. Zero or several listings leave the row unresolved. The vendor id itself is kept in the row's reference
    (`<vendor id>@<date>`, in the lineage and in every issue), scoped to this file's source; it is a label, never a key."""
    return ExternalIdentifiers(mic=parsed.mic, ticker=parsed.code)


class AlphaVantageQuoteAdapter:
    """`source_id` defaults to the real source. A synthetic fixture passes its own synthetic id; the format and its
    profile stay Alpha Vantage's (market-data/1.3 Ruling 4.8: synthetic data is its own upstream). `route` is the profile
    (and so the market) the adapter reads with: `alphavantage.us` (default) or `alphavantage.cn`; when omitted it is
    `alphavantage.cn` for a source id that is, or ends in `.`, `alphavantage.cn`, and `alphavantage.us` otherwise."""

    adapter_version = "0.1.0"
    data_kind = DataKind.QUOTE
    payload_formats = (PAYLOAD_FORMAT,)

    def __init__(self, source_id: str = SOURCE_ID, route: Optional[str] = None):
        if route is None:
            route = CN_SOURCE_ID if source_id == CN_SOURCE_ID or source_id.endswith("." + CN_SOURCE_ID) else SOURCE_ID
        if route not in (SOURCE_ID, CN_SOURCE_ID):
            raise ValueError(f"unknown Alpha Vantage route {route!r}")
        self.source_id = source_id
        self.route = route
        self.adapter_id = f"{source_id}.quotes"

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        profile = source_profile(self.route)
        override = None
        if manifest.declared_adjustment is AdjustmentStatus.UNDECLARED:
            documented = profile.call_adjustment.get(dict(manifest.request).get("function", ""))
            if documented is not None:
                override = AdjustmentStatus(documented.adjustment)
        if self.route == SOURCE_ID:
            return translate_daily_csv(self, manifest, payload, COLUMNS, profile, "US", adjustment_override=override)
        return self._translate_cn(manifest, payload, profile, override)

    def _translate_cn(self, manifest: FileManifest, payload: bytes, profile, override) -> AdapterOutput:
        symbols = manifest.source_identifiers
        parsed = None
        if len(set(symbols)) == 1:
            parsed = parse_cn_vendor_id(symbols[0])
            if parsed is None:  # Ruling 7A.1 item 3: not a vendor id of this route: nothing is read, nothing is guessed
                return AdapterOutput(issues=(AdapterIssue(symbols[0], IssueCode.VENDOR_ID_UNRECOGNIZED,
                                                          "not six digits, '.', and SHH or SHZ in upper case: unresolved"),))
        # Ruling 7A.1 items 7 and 8: the acquirer declares CNY; a manifest of this route may not declare USD or HKD
        if manifest.declared_currency is not None and manifest.declared_currency != CurrencyCode("CNY"):
            return AdapterOutput(issues=(AdapterIssue("manifest", IssueCode.CURRENCY_MISMATCH,
                                                      "a manifest of the alphavantage.cn route declares CNY only"),))

        def identifiers_for(symbol: str) -> ExternalIdentifiers:
            p = parse_cn_vendor_id(symbol)
            assert p is not None  # one symbol, parsed above
            return cn_identifiers(p)  # the MIC is the only thing inferred from the vendor id; resolution is by (MIC, code) alone

        out = translate_daily_csv(self, manifest, payload, COLUMNS, profile, "CN", adjustment_override=override,
                                  identifiers_for=identifiers_for)
        if parsed is not None and parsed.range_unexpected and (out.quotes or out.adjusted):
            out = dataclasses.replace(out, issues=out.issues + (AdapterIssue(
                parsed.vendor_id, IssueCode.VENDOR_CODE_RANGE_UNEXPECTED,
                f"a .{parsed.suffix} code starts with {parsed.code[0]}: flag only, resolution is by (MIC, code)"),))
        return out
