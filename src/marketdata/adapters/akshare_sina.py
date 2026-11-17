"""`akshare_sina.{hk,us}.quotes`: daily history saved from AKShare's Sina-backed functions
`stock_hk_daily` / `stock_us_daily` (upstream Sina Finance; a different upstream from the
Eastmoney functions). A pure translator over the shared `daily_csv` rules (market-data/1.1).

Structure, from the first real files (2026-10-01; never committed, only synthetic files with this
structure are):

    HK:  date,open,high,low,close,volume,amount
    US:  date,open,high,low,close,volume

No symbol column: the symbol is the one in the manifest's `source_identifiers`, exactly one. Identity
is a vendor id scoped to the source; no MIC is inferred.

Profiles (`marketdata.profiles`, Appendix A.3): HK close is FLOAT32 (OBSERVED: `474.20001` ->
`474.2` by the shortest binary32 round trip, never by rounding to a fixed number of decimals),
HK open/high/low FLOAT32 (DECLARED), HK volume FLOAT64 shares checked against `amount` (Ruling 2.6);
US prices FLOAT64, US volume shares DECLARED_UNVERIFIED (no turnover column, so the unit check
cannot run and no rule may use volume magnitude). A float32 value is recovered only while
ulp(v) < 10^-max_dp; otherwise it is kept, marked not recovered, and corroborates only.
"""

from __future__ import annotations

from typing import Optional

from marketdata.adapters.base import AdapterOutput
from marketdata.adapters.daily_csv import Columns, translate_daily_csv
from marketdata.manifest import DataKind, FileManifest
from marketdata.profiles import source_profile

HK_COLUMNS = Columns(date="date", open="open", high="high", low="low", close="close", volume="volume",
                     turnover="amount")
US_COLUMNS = Columns(date="date", open="open", high="high", low="low", close="close", volume="volume")


class AkshareSinaQuoteAdapter:
    adapter_version = "0.2.0"
    data_kind = DataKind.QUOTE

    def __init__(self, market: str, source_id: Optional[str] = None):
        """`source_id` defaults to the real (REFUSED) source of the format; a synthetic fixture passes its own
        synthetic id (the parser and its profile stay this format's: market-data/1.3 Ruling 4.8)."""
        if market not in ("hk", "us"):
            raise ValueError("market must be 'hk' or 'us'")
        self.market = market
        self.format_source_id = f"akshare_sina.{market}"
        self.source_id = source_id or self.format_source_id
        self.adapter_id = f"{self.source_id}.quotes"
        self.payload_formats = (f"akshare_sina_csv_{market}_daily/1",)

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        columns = HK_COLUMNS if self.market == "hk" else US_COLUMNS
        return translate_daily_csv(self, manifest, payload, columns, source_profile(self.format_source_id),
                                   self.market.upper())
