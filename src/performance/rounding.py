"""The presentation rounding of `performance/1.0` Rulings 2.2 and 2.3 (OI-8 closed), as data and one rule.

Tier P only: a presented value is an OUTPUT. Quanta: a derived money amount in currency `k` is quantized to 10^-minor_unit(k); a
return, a component, a weight or a share to 10^-12; a displayed rate to 10^-6; a recorded ledger fact (or a sum of facts) is
presented exactly. Mode: HALF AWAY FROM ZERO (`numerics.round_half_up`).

The minor-unit table is a versioned DATA table with a status per row (Ruling 2.3): CONFIRMED rows were checked by the owner against the SIX list (PD-0037; performance/1.11),
MEMORY rows (none today) are ISO 4217 from memory and an open item, DECLARED rows (CNH) are a convention with no publisher. A currency missing from the table FAILS CLOSED: its derived
money values are INSUFFICIENT_DATA + UNRESOLVED_CONVENTION, detail CURRENCY_NO_MINOR_UNIT. The engine never defaults to 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Optional, Tuple

from domain.currency import CurrencyCode
from performance.numerics import RoundingPoint, Rounded, is_terminating, round_half_up

MINOR_UNIT_TABLE_VERSION = "minor-units/1.1"  # performance/1.11 Ruling 2.3: the ten ISO rows CONFIRMED (PD-0037); value-equivalent to minor-units/1 (no minor unit changes)
CURRENCY_NO_MINOR_UNIT = "CURRENCY_NO_MINOR_UNIT"
FACT_NOT_TERMINATING = "FACT_NOT_TERMINATING"
RETURN_DECIMALS = 12
RATE_DECIMALS = 6

MEMORY, DECLARED, CONFIRMED = "MEMORY", "DECLARED", "CONFIRMED"
#: (currency, minor unit decimals, status), Ruling 2.3 (1.11), verbatim. CONFIRMED: by the owner, 2026-10-02, against SIX's ISO 4217 List One (published 2026-09-17), field `CcyMnrUnts` (PD-0037).
#: DECLARED: a Quant convention with no publisher to confirm it against (CNH): not an open item. MEMORY: not yet confirmed: an open item.
MINOR_UNIT_ROWS: Tuple[Tuple[str, int, str], ...] = (
    ("USD", 2, CONFIRMED), ("HKD", 2, CONFIRMED), ("CNY", 2, CONFIRMED), ("EUR", 2, CONFIRMED),
    ("CNH", 2, DECLARED),  # not an ISO code; market convention follows CNY
    ("JPY", 0, CONFIRMED),
    ("GBP", 2, CONFIRMED), ("CHF", 2, CONFIRMED), ("SGD", 2, CONFIRMED), ("AUD", 2, CONFIRMED), ("CAD", 2, CONFIRMED),
)


@dataclass(frozen=True)
class MinorUnitTable:
    version: str = MINOR_UNIT_TABLE_VERSION
    rows: Tuple[Tuple[str, int, str], ...] = MINOR_UNIT_ROWS

    def decimals(self, currency: CurrencyCode) -> Optional[int]:
        for code, decimals, _status in self.rows:
            if code == currency.code:
                return decimals
        return None

    def open_items(self) -> Tuple[str, ...]:
        """Only a MEMORY row is an open item (Ruling 2.3, 1.11); a CONFIRMED or DECLARED row is not, so with no MEMORY row the table contributes none."""
        mem = sorted(code for code, _d, status in self.rows if status == MEMORY)
        if not mem:
            return ()
        return (f"minor-unit table {self.version}: rows from memory, owner to confirm against ISO 4217: {','.join(mem)}",)


@dataclass(frozen=True)
class PerformanceRounding:
    rule_id: str = "performance/1.12#2.2-2.4"
    table: MinorUnitTable = MinorUnitTable()

    @property
    def table_version(self) -> str:
        return self.table.version

    def money_decimals(self, currency: CurrencyCode) -> Optional[int]:
        """The minor-unit decimals of `currency` (None: not in the table, so nothing is presented or apportioned for it)."""
        return self.table.decimals(currency)

    def apply(self, point: RoundingPoint, value: Fraction, currency: Optional[CurrencyCode]) -> Rounded:
        if point is RoundingPoint.PRESENT_FACT:
            # a recorded fact or a sum of facts is presented exactly; one that is not a decimal is a defect, not a rounding
            return Rounded(value) if is_terminating(value) else Rounded(None, FACT_NOT_TERMINATING)
        if point is RoundingPoint.PRESENT_RETURN:
            return Rounded(round_half_up(value, RETURN_DECIMALS))
        if point is RoundingPoint.PRESENT_RATE:
            return Rounded(round_half_up(value, RATE_DECIMALS))
        if point is RoundingPoint.PRESENT_MONEY:
            decimals = None if currency is None else self.table.decimals(currency)
            if decimals is None:
                return Rounded(None, CURRENCY_NO_MINOR_UNIT)
            return Rounded(round_half_up(value, decimals))
        raise ValueError(f"unknown rounding point {point!r}")


def decimals_by_currency(table: MinorUnitTable = MinorUnitTable()) -> Dict[str, int]:
    return {code: d for code, d, _s in table.rows}
