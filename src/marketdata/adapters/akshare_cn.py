"""`akshare.cn.quotes`: A-share daily history saved from AKShare's `stock_zh_a_hist` (upstream
Eastmoney), payload format `akshare_csv_cn_daily/1`. A pure translator (Tech Plan §15.2) over the
shared `daily_csv` rules (market-data/1.1 Rulings 2.4, 2.5, 2.6, 4.6).

Structure, from the first real files (2026-10-01; never committed, only synthetic files with this
structure are):

    日期,股票代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率

Read: 日期, 股票代码 (the source's own symbol, a vendor id scoped to this source: no MIC is
inferred), 开盘/收盘/最高/最低, 成交量, 成交额 (only for the volume-unit check) and 涨跌额 (only for
the within-source check of Ruling 4.6). NEVER read: 振幅, 涨跌幅, 换手率 (vendor arithmetic, Ruling
2.5). Profile: `marketdata.profiles` entry `akshare.cn` (FLOAT64 prices; volume in LOTS of 100
shares, converted to SHARES; checked against 成交额 at ingest, Ruling 2.6).

REFUSED SOURCE (PD-0031/0032): this parser is a format record, tested on synthetic files only; no
file from Eastmoney is ever a reading (market-data/1.2 Ruling 4.7).

A RAW file yields `UnresolvedQuote`s (the close validated against the strict A-share maximum of 2
decimals, MEMORY-status: the security class comes from the listing's identity record, not from the
request, and is unknown here; a refused value is flagged SECURITY_CLASS_UNRESOLVED). A non-RAW file (qfq/hfq)
yields verification-only `UnresolvedAdjustedQuote`s with method UNKNOWN: the method is set only by
Test V2, never declared.
"""

from __future__ import annotations

from marketdata.adapters.base import AdapterOutput
from marketdata.adapters.daily_csv import Columns, translate_daily_csv
from marketdata.manifest import DataKind, FileManifest
from marketdata.profiles import source_profile

SOURCE_ID = "akshare.cn"
PAYLOAD_FORMAT = "akshare_csv_cn_daily/1"
COLUMNS = Columns(date="日期", open="开盘", high="最高", low="最低", close="收盘", volume="成交量",
                  turnover="成交额", change="涨跌额", symbol="股票代码")


class AkshareCnQuoteAdapter:
    """`source_id` is the registered source whose files this instance reads. It defaults to the real
    (REFUSED) source. A test or a synthetic fixture passes its OWN synthetic source id: the file FORMAT, and so the
    parser and its profile, stay this adapter's, while the data is then recorded as that synthetic source's
    (market-data/1.3 Ruling 4.8) and is never attested as the real one."""

    adapter_version = "0.2.0"
    data_kind = DataKind.QUOTE
    payload_formats = (PAYLOAD_FORMAT,)

    def __init__(self, source_id: str = SOURCE_ID):
        self.source_id = source_id
        self.adapter_id = f"{source_id}.quotes"

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        return translate_daily_csv(self, manifest, payload, COLUMNS, source_profile(SOURCE_ID), "CN")
