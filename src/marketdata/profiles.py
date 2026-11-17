"""Precision, unit and upstream profiles, as versioned DATA (market-data/1.1 Appendix A).

A transcription of Appendix A, with its own version. Nothing here is a rule the engineer chose:
every entry carries the status the Quant gave it (OBSERVED, DECLARED, DECLARED_UNVERIFIED,
OBSERVED_ONE_WINDOW, MEMORY or TO_OBSERVE). MEMORY entries are validation bounds and flag-only
tick tables the human must confirm (§12); they are used for nothing beyond what Ruling 2.4 says
(a `max_dp` validation; the tick tables are NOT implemented). A source whose profile is
TO_OBSERVE, MEMORY (C2-12) or REFUSED (C2-12), or absent, is not admitted for real data (Ruling 11, "a missing
profile fails closed").

Lineage records `PROFILE_SET_VERSION` through `precision_profile_id`.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from datetime import time as TimeOfDay
from decimal import Decimal
from enum import Enum, unique
from typing import Dict, List, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

CONVENTION_SET = "market-data/1.16"  # raised from 1.15 by the F1 R4a label increment (section 11 item 35 and its gate are met): a release id names the method the code runs (P12, NFR-001)
# profiles/2: Appendix A.1 gained the CN security-class table of 1.4 (MIC, SecurityType, currency).
# profiles/3 (1.5): A.3 declares delivered_dp for the Eastmoney (2) and Sina-US (4) open/high/low/close (A.4 item 7)
# profiles/4 (1.15): A.3 gained the `alphavantage.cn` profile (TO_OBSERVE; added to SOURCES by f42efa0, which left the counter at 3). The
# methodology fixes no rule for this counter; moving it with the content is the conservative reading, listed for the Quant to confirm.
# profiles/5 (1.16, section 11 item 32; the Quant's note of 2026-10-25, answer (b)): the content of profiles/4 plus exactly three changes: the `TIME_SERIES_DAILY`
# `call_adjustment` entry of `alphavantage.us` and `alphavantage.cn` carries its status DECLARED and the reference "PD-0066 decision 3" as data (item 23); the
# Ruling 4.7 item 6 MIC -> market table gains ARCX, BATS, XASE (US); the Ruling 2.2 item 1 zone table gains the same three (America/New_York).
PROFILE_SET_VERSION = "market-data/1.16#profiles/5"  # the id carries the governing set and a counter that moves when the profile content does

OBSERVED = "OBSERVED"
OBSERVED_ONE_WINDOW = "OBSERVED_ONE_WINDOW"
DECLARED = "DECLARED"
DECLARED_UNVERIFIED = "DECLARED_UNVERIFIED"
MEMORY = "MEMORY"
TO_OBSERVE = "TO_OBSERVE"
# market-data/1.15 Ruling 7A.3 item 2: fields that exist only so a parser can be tested on SYNTHETIC files. They admit nothing.
PROVISIONAL_UNOBSERVED = "PROVISIONAL_UNOBSERVED"

# Reason codes of the admission gate (market-data/1.15 Ruling 7A.3 item 1; engineer item 21). A terms attestation is necessary
# for admission, never sufficient: the profile status and Appendix A.5 gate a REAL file as well.
SOURCE_NOT_ADMITTED = "SOURCE_NOT_ADMITTED"
SOURCE_PENDING_OBSERVATION = "SOURCE_PENDING_OBSERVATION"
SOURCE_NOT_IN_PRIMARY_ORDER = "SOURCE_NOT_IN_PRIMARY_ORDER"
# the per-listing form of the same gate (Ruling 7A.3 item 1; Appendix A.5 is per market): a REAL reading is bound to a listing, and the
# listing's market, not the file's source id, decides whether the source may supply it
SOURCE_MARKET_NOT_COVERED = "SOURCE_MARKET_NOT_COVERED"
LISTING_EXCHANGE_UNKNOWN = "LISTING_EXCHANGE_UNKNOWN"


@unique
class NumberFormat(Enum):
    """The type in which the upstream or the wrapper last held the number before printing it."""

    TEXT_DECIMAL = "TEXT_DECIMAL"
    FLOAT64 = "FLOAT64"
    FLOAT32 = "FLOAT32"


class ProfileNotAdmittedError(PermissionError):
    """The source's profile is TO_OBSERVE or missing: the file is not admitted (fail closed). `gate_code` says
    which gate refused: SOURCE_NOT_ADMITTED, SOURCE_PENDING_OBSERVATION or SOURCE_NOT_IN_PRIMARY_ORDER for a source, and for a
    reading bound to a listing also SOURCE_MARKET_NOT_COVERED (the profile does not cover the listing's market) and
    LISTING_EXCHANGE_UNKNOWN (the market of a profiled source's real reading cannot be established). It is a refusal
    label of the admission gate, not a metric reason code (those live in `states` only)."""

    def __init__(self, message: str, gate_code: str = SOURCE_NOT_ADMITTED):
        super().__init__(message)
        self.gate_code = gate_code


@dataclass(frozen=True)
class FieldProfile:
    format: NumberFormat
    status: str
    integral: bool = False
    shares_per_unit: Optional[int] = None  # volume fields only
    unit: Optional[str] = None
    delivered_dp: Optional[int] = None  # TEXT_DECIMAL: the decimals the source delivers (Ruling 4.2 bound)


#: The decision that records the owner's reading of the vendor documentation (market-data/1.16 section 11 item 23).
PD_0066_DECISION_3 = "PD-0066 decision 3"

#: The statuses a `CallAdjustment` may carry (market-data/1.16 Appendix A.3 `call_adjustment`; section 11 item 23). `DECLARED`: a human read the
#: vendor's live documentation of the call and recorded the reference. `MEMORY`: the Quant's recollection of it. Neither is a verification.
CALL_ADJUSTMENT_STATUSES = (DECLARED, MEMORY)


@dataclass(frozen=True)
class CallAdjustment:
    """What a source's documentation says one request function returns, and how well that is established.

    `adjustment` is the adjustment status the function documents (`RAW` for an as-traded call). `status` is the label source's status,
    `DECLARED` or `MEMORY`, and it is DATA of the profile, not a constant of the adapter (market-data/1.16 section 11 item 23): the
    lineage's label source reads `PROFILE_CALL_ADJUSTMENT:<source>:<function>:<status>`. `reference` names the decision that records the
    reading (required for `DECLARED`). A declaration by the vendor is not a verification: the series' label status stays UNVERIFIABLE
    (section 9B item 4 (d); Tests V1 and V4 are the only things that change it)."""

    adjustment: str
    status: str
    reference: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in CALL_ADJUSTMENT_STATUSES:
            raise ValueError(f"a call adjustment's status is one of {CALL_ADJUSTMENT_STATUSES}, not {self.status!r}")
        if not isinstance(self.adjustment, str) or not self.adjustment.strip():
            raise ValueError("a call adjustment names the adjustment status the call documents")
        if self.status == DECLARED and not (isinstance(self.reference, str) and self.reference.strip()):
            raise ValueError("a DECLARED call adjustment records the decision that declared it")


@dataclass(frozen=True)
class SourceProfile:
    """One source's profile (Appendix A.3). `adjusted_dp` is the decimals the source delivers for
    ADJUSTED values (Ruling 3.1 V2 (a')); None means it delivers none we may verify. `call_adjustment`
    maps a request function to a `CallAdjustment`: the adjustment status that function documents and the status of that reading
    (`DECLARED` or `MEMORY`). An `UNDECLARED` manifest of such a call is read through it and the series' label is then verified
    (never trusted). `refused` marks a source whose terms are refused (PD-0031/0032): its parser is
    kept as a format record, and no file from it is ever a reading (Ruling 4.7)."""

    source_id: str
    upstream: str
    status: str  # TO_OBSERVE => not admitted
    function: Optional[str] = None
    markets: Tuple[str, ...] = ()
    payload_format: Optional[str] = None
    fields: Mapping[str, FieldProfile] = field(default_factory=dict)
    role: Optional[str] = None
    adjusted_dp: Optional[int] = None
    call_adjustment: Mapping[str, CallAdjustment] = field(default_factory=dict)
    refused: bool = False

    @property
    def admitted(self) -> bool:
        """C2-12 (review of 39733e9; Appendix A.4, MD-OI-12): a profile admits REAL data only when it is neither
        TO_OBSERVE nor MEMORY (a MEMORY format is recalled, not observed: the source's first real file must be
        profiled before the profile may read real data) and the source is not `refused` (PD-0031/0032)."""
        return self.not_admitted_reason is None

    @property
    def gate_refusal(self) -> Optional[Tuple[str, str]]:
        """(reason code, reason) when a REAL file of this source is refused because the source is pending observation or
        is not in Appendix A.5's primary order for its markets, whatever its terms check says (Ruling 7A.3 item 1: terms
        attestation is necessary, not sufficient). None when neither gate applies. Independent of MEMORY and `refused`."""
        if self.status == TO_OBSERVE:
            return (SOURCE_PENDING_OBSERVATION,
                    "the profile is TO_OBSERVE (pending observation): a terms attestation alone admits nothing (Ruling 7A.3)")
        for market in self.markets:
            if self.upstream not in PRIMARY_ORDER.get(market, ()):
                return (SOURCE_NOT_IN_PRIMARY_ORDER,
                        f"upstream {self.upstream!r} is not in Appendix A.5's primary order for market {market}: only an "
                        "owner decision admits it (Ruling 7A.3 item 3 (e))")
        return None

    @property
    def not_admitted_code(self) -> str:
        """The gate code that goes with `not_admitted_reason`, in the same order of checks."""
        if self.refused or self.status == MEMORY:
            return SOURCE_NOT_ADMITTED
        gate = self.gate_refusal
        return SOURCE_NOT_ADMITTED if gate is None else gate[0]

    @property
    def not_admitted_reason(self) -> Optional[str]:
        if self.refused:
            return "the source is REFUSED (PD-0031/0032): no file from it is ever a reading (Ruling 4.7)"
        if self.status == TO_OBSERVE:
            return "the profile is TO_OBSERVE: not admitted until it is filled (Appendix A.4)"
        if self.status == MEMORY:
            return ("the profile is MEMORY (a recalled, never observed format): real data is not admitted until the "
                    "source's first real file has been profiled (Appendix A.4, MD-OI-12)")
        gate = self.gate_refusal  # Ruling 7A.3: an OBSERVED profile of a source A.5 does not list is still not admitted
        return None if gate is None else gate[1]

    def profile_id(self, role: str) -> str:
        return f"{PROFILE_SET_VERSION}:{self.source_id}:{role}"


@dataclass(frozen=True)
class MarketProfile:
    """`max_dp_by_class` for CN is keyed by security class; HK is one value; US is two bands."""

    market: str
    max_dp: Mapping[str, int] = field(default_factory=dict)
    default_class: Optional[str] = None
    bands: Tuple[Tuple[Optional[Decimal], Optional[Decimal], int], ...] = ()  # (at_least, below, dp)
    status: str = MEMORY
    tick_table_status: str = MEMORY  # FLAG_ONLY; never used to normalize
    tick_table_use: str = "FLAG_ONLY"


MARKETS: Dict[str, MarketProfile] = {
    "CN": MarketProfile(
        "CN",
        max_dp={"A_SHARE": 2, "FUND_ETF_LOF_BOND": 3, "B_SHARE_SSE": 3, "B_SHARE_SZSE": 2},
        default_class="A_SHARE",
    ),
    "HK": MarketProfile("HK", max_dp={"ALL": 3}, default_class="ALL"),
    "US": MarketProfile(
        "US", bands=((Decimal("1.00"), None, 2), (None, Decimal("1.00"), 4)),
    ),
}


def max_dp(market: str, price: Decimal, security_class: Optional[str] = None) -> int:
    """The validation bound of Ruling 2.4 item 4 for a close. MEMORY-status data."""
    try:
        profile = MARKETS[market]
    except KeyError:
        raise ProfileNotAdmittedError(f"no market profile for {market!r}") from None
    if profile.bands:
        for at_least, below, dp in profile.bands:
            if (at_least is None or price >= at_least) and (below is None or price < below):
                return dp
        raise ProfileNotAdmittedError(f"no price band for {price} in {market}")
    cls = security_class or profile.default_class
    if cls not in profile.max_dp:
        raise ProfileNotAdmittedError(f"no max_dp for class {cls!r} in {market}")
    return profile.max_dp[cls]


# market-data/1.4 Appendix A.1 "CN security class" (C2-10, section 9C item 5): the class is derived from the listing's
# IDENTITY record, never from a request or a file: (MIC, `Instrument.security_type`, `trading_currency`). It decides the
# close's maximum decimals (Ruling 2.4 item 4; MARKETS["CN"]). B-shares are identified by their currency (USD on XSHG,
# HKD on XSHE). ANY OTHER combination (an unknown MIC, type or currency, or a type of None) has NO class: the strict
# 2-decimal grid applies and the refusal is flagged SECURITY_CLASS_UNRESOLVED. The table is DATA of the profile set.
SECURITY_CLASS_UNRESOLVED = "SECURITY_CLASS_UNRESOLVED"
CN_CLASS_TABLE: Mapping[Tuple[str, str, str], str] = {
    ("XSHG", "COMMON_STOCK", "CNY"): "A_SHARE",
    ("XSHE", "COMMON_STOCK", "CNY"): "A_SHARE",
    ("XSHG", "ETF", "CNY"): "FUND_ETF_LOF_BOND",
    ("XSHE", "ETF", "CNY"): "FUND_ETF_LOF_BOND",
    ("XSHG", "COMMON_STOCK", "USD"): "B_SHARE_SSE",
    ("XSHE", "COMMON_STOCK", "HKD"): "B_SHARE_SZSE",
}


def security_class_for(mic: Optional[str], security_type: Optional[str], currency: Optional[str]) -> Optional[str]:
    """The Ruling 2.4 security class of a mainland listing from A.1's table, or None when the combination is not in it
    (then `SECURITY_CLASS_UNRESOLVED`: strict 2 decimals). `currency` is the listing's trading currency code."""
    if mic is None or security_type is None or currency is None:
        return None
    return CN_CLASS_TABLE.get((mic, security_type, currency))


def field_profile_of(profile_id: Optional[str]) -> Optional[FieldProfile]:
    """The field profile a lineage's `precision_profile_id` names (`<profile set>:<source>:<role>`), or None."""
    if not profile_id or not profile_id.startswith(PROFILE_SET_VERSION + ":"):
        return None
    source_id, _, role = profile_id[len(PROFILE_SET_VERSION) + 1:].rpartition(":")
    profile = SOURCES.get(source_id)
    return None if profile is None else profile.fields.get(role)


def _ohlc(fmt: NumberFormat, status: str, close_status: Optional[str] = None,
          delivered_dp: Optional[int] = None) -> Dict[str, FieldProfile]:
    return {
        "open": FieldProfile(fmt, status, delivered_dp=delivered_dp),
        "high": FieldProfile(fmt, status, delivered_dp=delivered_dp),
        "low": FieldProfile(fmt, status, delivered_dp=delivered_dp),
        "close": FieldProfile(fmt, close_status or status, delivered_dp=delivered_dp),
    }


SOURCES: Dict[str, SourceProfile] = {
    # REFUSED (PD-0031/0032): the AKShare/Eastmoney and Sina entries below are format records for the
    # parsers, tested on synthetic files only. No file from them is ever a reading (Ruling 4.7).
    "akshare.cn": SourceProfile(
        "akshare.cn", "eastmoney", OBSERVED, "stock_zh_a_hist", ("CN",), "akshare_csv_cn_daily/1",
        # 1.5 A.3 / A.4 item 7: delivered_dp 2 = the maximum number of decimals observed ("1324.49"), conservative
        {**_ohlc(NumberFormat.FLOAT64, OBSERVED, delivered_dp=2),
         "volume": FieldProfile(NumberFormat.FLOAT64, OBSERVED, True, 100, "LOT_100"),
         "turnover": FieldProfile(NumberFormat.FLOAT64, OBSERVED)},
        adjusted_dp=2, refused=True),  # Example 3-C: the qfq file delivers 2 decimals (delta_j = 0.005)
    "akshare_sina.hk": SourceProfile(
        "akshare_sina.hk", "sina", OBSERVED, "stock_hk_daily", ("HK",), "akshare_sina_csv_hk_daily/1",
        {**_ohlc(NumberFormat.FLOAT32, DECLARED, OBSERVED),
         "volume": FieldProfile(NumberFormat.FLOAT64, OBSERVED, True, 1, "SHARE"),
         "turnover": FieldProfile(NumberFormat.FLOAT64, OBSERVED)}, refused=True),
    "akshare_sina.us": SourceProfile(
        "akshare_sina.us", "sina", OBSERVED, "stock_us_daily", ("US",), "akshare_sina_csv_us_daily/1",
        # 1.5 A.3 / A.4 item 7: delivered_dp 4 = the maximum observed ("231.8201")
        {**_ohlc(NumberFormat.FLOAT64, OBSERVED, delivered_dp=4),
         "volume": FieldProfile(NumberFormat.FLOAT64, DECLARED_UNVERIFIED, True, 1, "SHARE")},
        refused=True),
    # ADMITTED (PD-0032); profile OBSERVED in market-data/1.2 (Example A-1). A direct API: no wrapper
    # library. Close: 4 delivered decimals, grid-checked against the US price_max_dp. Open, high and low:
    # 4 decimals, NOT grid-checked (47/300 sub-penny values), used only in the row check. Volume:
    # integral shares, DECLARED_UNVERIFIED (no turnover column). Rows arrive newest first.
    # `TIME_SERIES_DAILY` is documented as as-traded, and the label source is DECLARED (PD-0066 decision 3: the owner read the vendor's live
    # documentation on 2026-10-24; market-data/1.16 Appendix A.3 and section 9B item 4 (d)). A declaration by the vendor, not a verification:
    # an UNDECLARED manifest of that call is read as RAW, and the series' label status stays UNVERIFIABLE until a decisive split is in the window.
    "alphavantage.us": SourceProfile(
        "alphavantage.us", "alphavantage", OBSERVED, "TIME_SERIES_DAILY", ("US",), "alphavantage_csv_daily/1",
        {"open": FieldProfile(NumberFormat.TEXT_DECIMAL, OBSERVED, delivered_dp=4),
         "high": FieldProfile(NumberFormat.TEXT_DECIMAL, OBSERVED, delivered_dp=4),
         "low": FieldProfile(NumberFormat.TEXT_DECIMAL, OBSERVED, delivered_dp=4),
         "close": FieldProfile(NumberFormat.TEXT_DECIMAL, OBSERVED, delivered_dp=4),
         "volume": FieldProfile(NumberFormat.TEXT_DECIMAL, DECLARED_UNVERIFIED, True, 1, "SHARE")},
        call_adjustment={"TIME_SERIES_DAILY": CallAdjustment("RAW", DECLARED, PD_0066_DECISION_3)}),
    # PENDING OBSERVATION, NOT ADMITTED (market-data/1.15 Ruling 7A.3; PD-0063/PD-0065). The terms reading is owner-accepted;
    # the profile is not. The fields mirror alphavantage.us and are PROVISIONAL_UNOBSERVED: they exist only so the parser can be
    # tested on SYNTHETIC files (Examples 7A-G1 to G3). `PRIMARY_ORDER["CN"]` stays empty, and `status` TO_OBSERVE keeps
    # `admitted` False, so no real file of this source is ever a reading. A.4 observation replaces these fields.
    "alphavantage.cn": SourceProfile(
        "alphavantage.cn", "alphavantage", TO_OBSERVE, "TIME_SERIES_DAILY", ("CN",), "alphavantage_csv_daily/1",
        {"open": FieldProfile(NumberFormat.TEXT_DECIMAL, PROVISIONAL_UNOBSERVED, delivered_dp=4),
         "high": FieldProfile(NumberFormat.TEXT_DECIMAL, PROVISIONAL_UNOBSERVED, delivered_dp=4),
         "low": FieldProfile(NumberFormat.TEXT_DECIMAL, PROVISIONAL_UNOBSERVED, delivered_dp=4),
         "close": FieldProfile(NumberFormat.TEXT_DECIMAL, PROVISIONAL_UNOBSERVED, delivered_dp=4),
         "volume": FieldProfile(NumberFormat.TEXT_DECIMAL, PROVISIONAL_UNOBSERVED, True, 1, "SHARE")},
        # DECLARED on the same reading: the documentation shows `.SHH`/`.SHZ` as supported on the same call (1.16 section 11 item 23). It
        # relaxes nothing for admission (this profile stays TO_OBSERVE; Ruling 7A.3 (c) 5 needs V4 for both components).
        call_adjustment={"TIME_SERIES_DAILY": CallAdjustment("RAW", DECLARED, PD_0066_DECISION_3)}),
    "frankfurter.ecb": SourceProfile(
        "frankfurter.ecb", "ecb", OBSERVED, None, (), "frankfurter_json_timeseries/1",
        {"rate": FieldProfile(NumberFormat.TEXT_DECIMAL, OBSERVED)}, role="TRANSPORT_CHECK_FOR_ECB"),
    # the preferred FX source (Ruling 1.1a): the ECB's own history file. MEMORY status (the format is
    # recalled, not yet observed: A.3); it needs a SOURCES.json entry and the owner's attestation.
    "ecb.eurofxref": SourceProfile(
        "ecb.eurofxref", "ecb", MEMORY, None, (), "ecb_eurofxref_hist_csv/1",
        {"rate": FieldProfile(NumberFormat.TEXT_DECIMAL, MEMORY)}, role="PREFERRED_FX"),
    # REFUSED and never profiled: not admitted (TO_OBSERVE).
    "akshare_sina.cn": SourceProfile("akshare_sina.cn", "sina", TO_OBSERVE, refused=True),
    "akshare.hk": SourceProfile("akshare.hk", "eastmoney", TO_OBSERVE, refused=True),
    "akshare.us": SourceProfile("akshare.us", "eastmoney", TO_OBSERVE, refused=True),
}

# A.5 (market-data/1.2), Ruling 4.3: the ADMITTED upstreams per market; it decides only between AGREEING
# values. A market whose list is empty has no admitted source (Ruling 4.7): its listings resolve to
# MISSING_PRICE_HISTORY with cause NO_ADMITTED_SOURCE. Admitting a source changes this data and nothing else.
PRIMARY_ORDER: Dict[str, Tuple[str, ...]] = {
    "CN": (),
    "HK": (),
    "US": ("alphavantage",),
    "FX": ("ecb",),
}

# Ruling 2.2: the IANA zone of each exchange and of the ECB fixing, and each MIC's market.
EXCHANGE_ZONES: Dict[str, str] = {
    "XNYS": "America/New_York", "XNAS": "America/New_York", "XHKG": "Asia/Hong_Kong",
    "XSHG": "Asia/Shanghai", "XSHE": "Asia/Shanghai", "ECB": "Europe/Berlin",
    # market-data/1.16 Ruling 2.2 item 1: the other US venues. No registered calendar names them, so a listing on them stays FRESHNESS_UNKNOWN.
    "ARCX": "America/New_York", "BATS": "America/New_York", "XASE": "America/New_York",
}
# Ruling 4.7 item 6 (1.16): a MIC that is not listed here has NO V1 market, and a real reading bound to such a listing is refused
# (`listing_market_refusal`, LISTING_EXCHANGE_UNKNOWN). BJSE is such a MIC.
MIC_MARKET: Dict[str, str] = {"XNYS": "US", "XNAS": "US", "ARCX": "US", "BATS": "US", "XASE": "US",
                              "XHKG": "HK", "XSHG": "CN", "XSHE": "CN"}

# Ruling 1.1 (market-data/1.8): the nominal fixing instant is 14:10 Europe/Berlin (IANA zone, never a fixed offset; the ECB
# says "around 14:10 CET"; 1.0 to 1.7 used 14:15); Ruling 1.6 (Current mode): nominal publication 16:00. Constants of the
# convention, not clock reads.
ECB_ZONE_NAME = "Europe/Berlin"
ECB_FIXING_TIME = TimeOfDay(14, 10)
ECB_PUBLICATION_TIME = TimeOfDay(16, 0)
ECB_CALENDAR_ID = "ECB"


def ecb_fixing_instant(day: datetime.date) -> datetime.datetime:
    return datetime.datetime.combine(day, ECB_FIXING_TIME, tzinfo=ZoneInfo(ECB_ZONE_NAME))


def market_of_mic(mic: Optional[str]) -> Optional[str]:
    return None if mic is None else MIC_MARKET.get(mic)


def market_has_admitted_source(market: str) -> bool:
    return bool(PRIMARY_ORDER.get(market, ()))


def profile_open_items() -> Tuple[str, ...]:
    """Every profile still TO_OBSERVE, listed so a result cannot hide it (A.3, A.4)."""
    items: List[str] = []
    for source_id, profile in sorted(SOURCES.items()):
        if profile.status == TO_OBSERVE:
            provisional = any(f.status == PROVISIONAL_UNOBSERVED for f in profile.fields.values())
            tag = ("REFUSED (PD-0031/0032), never profiled" if profile.refused
                   else "pending observation, not admitted; provisional fields serve synthetic tests only (Ruling 7A.3)"
                   if provisional else "no profile yet (A.4)")
            items.append(f"profile TO_OBSERVE: {source_id} ({tag})")
        elif profile.status == MEMORY:  # C2-12: a recalled format is not admitted for real data
            items.append(f"profile MEMORY: {source_id} (real data not admitted until its first real file is "
                         "profiled, A.4)")
    return tuple(items)


def source_profile(source_id: str) -> SourceProfile:
    try:
        return SOURCES[source_id]
    except KeyError:
        raise ProfileNotAdmittedError(
            f"no precision profile for source {source_id!r}: not admitted until one exists") from None


def require_admitted(source_id: str) -> SourceProfile:
    profile = source_profile(source_id)
    reason = profile.not_admitted_reason
    if reason is not None:
        raise ProfileNotAdmittedError(f"{profile.not_admitted_code}: source {source_id!r} is not admitted: {reason}",
                                      profile.not_admitted_code)
    return profile


def listing_market_refusal(source_id: str, mic: Optional[str]) -> Optional[Tuple[str, str]]:
    """(reason code, reason) when a REAL reading of `source_id` may not be bound to a listing on exchange `mic`, else None.

    market-data/1.15 Ruling 7A.3 item 1 and Appendix A.5 are per MARKET, so the gate cannot key on the file's source id alone: a
    file labelled with one source can carry a symbol that the identity table maps to a listing of another market. A real
    reading of a listing whose market is X is usable only if (1) the source's profile covers X, (2) the profile is admitted (not
    TO_OBSERVE, MEMORY or refused), and (3) the profile's upstream is in `PRIMARY_ORDER[X]` (part of `not_admitted_reason`). With the
    CN order empty, every real reading of a CN listing is refused, whatever the file's source id says.

    Ruling 4.7 item 6 (market-data/1.16), in its order: (1) the listing's MIC maps to a V1 market in `MIC_MARKET`, else
    LISTING_EXCHANGE_UNKNOWN (the detail names the MIC; `mic` None, a listing unknown to the identity table, is the same
    refusal, so a reading is never assumed to be in a market the profile covers; BJSE is unmapped); (2) the source has a profile,
    else SOURCE_NOT_ADMITTED (OpenFIGI and the calendar files are not price sources; this holds for a corporate-action record
    as well); (3) the profile covers the market, else SOURCE_MARKET_NOT_COVERED; (4) the profile is admitted and its upstream is in
    A.5 for the market (`not_admitted_code`). The five labels are admission refusals, never reason codes. SYNTHETIC readings never
    reach this function: the callers exempt them, as they exempt synthetic sources from every other gate."""
    market = market_of_mic(mic)
    if market is None:
        return (LISTING_EXCHANGE_UNKNOWN,
                f"the listing's exchange is {mic!r}, which maps to no V1 market (Ruling 4.7 item 6): the market of a real reading of "
                f"source {source_id!r} cannot be established" if mic is not None else
                f"the listing's exchange is unknown, so the market of a real reading of source {source_id!r} cannot be established")
    profile = SOURCES.get(source_id)
    if profile is None:
        return (SOURCE_NOT_ADMITTED,
                f"source {source_id!r} has no profile: a source with no profile supplies no real reading (Ruling 4.7 item 6)")
    if market not in profile.markets:
        return (SOURCE_MARKET_NOT_COVERED,
                f"the profile of source {source_id!r} covers market(s) {', '.join(profile.markets) or 'none'}, not {market} "
                f"(exchange {mic}): a symbol of another market filed under this source supplies no reading")
    reason = profile.not_admitted_reason
    if reason is not None:
        return (profile.not_admitted_code, reason)
    return None


def require_listing_market(source_id: str, listing_id: object, mic: Optional[str]) -> None:
    """Raise `ProfileNotAdmittedError` (with the gate code) when `listing_market_refusal` refuses this real reading."""
    refusal = listing_market_refusal(source_id, mic)
    if refusal is not None:
        code, why = refusal
        raise ProfileNotAdmittedError(
            f"{code}: source {source_id!r} may not supply a reading for listing {listing_id} on exchange {mic or 'unknown'}: {why}", code)
