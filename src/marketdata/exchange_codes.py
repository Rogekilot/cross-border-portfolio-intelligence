"""Appendix A.6 (market-data/1.5): MIC <-> OpenFIGI exchange codes, as versioned DATA (Ruling 7.3).

A transcription of A.6 with its own version, like `profiles.py` for Appendix A.3. Nothing here is a rule the engineer chose:
every entry carries the status the Quant gave it.

- `OBSERVED`: seen in an admitted OpenFIGI file, the record's level established by `figi` against `compositeFIGI`;
- `CONFIRMED`: a human checked it against OpenFIGI's published exchange-code list and recorded the reference;
- `MEMORY`: the Quant's recollection; `TO_CONFIRM`: unknown.

ONLY `OBSERVED` and `CONFIRMED` entries attach a FIGI (Ruling 7.3 items 3 and 6). An entry moves to OBSERVED only from a
real file, by the Quant's or the human's say-so: not by editing this table on a hunch.

`composite_codes` maps a composite-level exchCode to the MICs of the country it spans. It is what lets a composite record
("US") fill `composite_figi` under the uniqueness test (item 4), and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, Mapping, Optional, Tuple

# The id names the version that introduced the table's CONTENT, not the governing set (market-data/1.16 section 11 item 32, rule for the A.6
# table id): it is stamped into identifier provenance, which persists on identity rows across code versions. `#a6/2` counts content changes
# (codes, statuses, references, the composite-code table; comments are not content): `UW` moved MEMORY -> OBSERVED in 1.16 (PD-0066 decision 4).
TABLE_VERSION = "market-data/1.16#a6/2"

OBSERVED = "OBSERVED"
CONFIRMED = "CONFIRMED"
MEMORY = "MEMORY"
TO_CONFIRM = "TO_CONFIRM"
ATTACHING = (OBSERVED, CONFIRMED)


@dataclass(frozen=True)
class ExchangeCode:
    code: str
    status: str
    segment_mic: Optional[str] = None

    @property
    def attaches(self) -> bool:
        return self.status in ATTACHING


@dataclass(frozen=True)
class CompositeCode:
    code: str
    status: str
    mics: Tuple[str, ...] = ()

    @property
    def attaches(self) -> bool:
        return self.status in ATTACHING and bool(self.mics)


@dataclass(frozen=True)
class CodeTable:
    """A versioned MIC <-> exchCode table. `version` is recorded with every FIGI row an assertion attaches."""

    version: str
    exchange: Mapping[str, Tuple[ExchangeCode, ...]]
    composite: Mapping[str, CompositeCode]

    def entry_for(self, mic: str, code: str) -> Optional[ExchangeCode]:
        for entry in self.exchange.get(mic, ()):
            if entry.code == code:
                return entry
        return None

    def knows_mic(self, mic: str) -> bool:
        return mic in self.exchange

    def with_confirmed(self, mapping: Mapping[str, Iterable[str]], version_suffix: str = "+test") -> "CodeTable":
        """A copy whose exchange entries for the given MICs are replaced by CONFIRMED ones. For tests and for a human who
        has confirmed codes before the table file is updated: the status says so (CONFIRMED), the version changes."""
        exchange: Dict[str, Tuple[ExchangeCode, ...]] = dict(self.exchange)
        for mic, codes in mapping.items():
            exchange[mic] = tuple(ExchangeCode(c, CONFIRMED) for c in codes)
        return CodeTable(self.version + version_suffix, exchange, self.composite)


A6 = CodeTable(
    TABLE_VERSION,
    exchange={
        # `UW` (segment XNGS, Nasdaq Global Select) is OBSERVED (1.16; was MEMORY): AAPL_UW.json (request exchCode UW) and AAPL_XNGS.json (request
        # micCode XNGS), retrieved 2026-10-23 by the owner, are byte-identical, payload SHA-256 b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc;
        # manifests 7952829b...a738 (UW, in the indexed store) and cb4d862d...63c8d (XNGS, under data/marketdata/observations/). The record is exchange-level
        # (figi BBG000B9Y5X2 != compositeFIGI BBG000B9XRY4; shareClassFIGI BBG001S5N8V8, Ruling 7.3 item 2). That XNGS is a segment of XNAS is ISO 10383 from
        # the Quant's memory (section 12 item 23). `UQ` and `UR` stay MEMORY.
        "XNAS": (ExchangeCode("UW", OBSERVED, "XNGS"), ExchangeCode("UQ", MEMORY, "XNMS"), ExchangeCode("UR", MEMORY, "XNCM")),
        "XNYS": (ExchangeCode("UN", MEMORY),),
        "ARCX": (ExchangeCode("UP", MEMORY),),
        "BATS": (ExchangeCode("UF", MEMORY),),
        "XASE": (ExchangeCode("UA", MEMORY),),
        "XHKG": (ExchangeCode("HK", OBSERVED),),  # 700_HK.json: figi BBG000BJ35N5 != compositeFIGI BBG000BJ35F4
        "XSHG": (ExchangeCode("CG", MEMORY),),
        "XSHE": (ExchangeCode("CS", MEMORY),),
    },
    composite={
        "US": CompositeCode("US", OBSERVED, ("XNYS", "XNAS", "ARCX", "BATS", "XASE")),  # AAPL_US.json: figi = compositeFIGI
        "CH": CompositeCode("CH", MEMORY, ("XSHG", "XSHE")),
        "HK": CompositeCode("HK", TO_CONFIRM, ()),
    },
)
