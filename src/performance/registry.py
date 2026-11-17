"""The registry of metric ids the performance engine can emit (tech plan 16.8 item 4: the availability matrix).

`build_metric` refuses an id that is not here, so a new metric cannot ship without being registered; the availability-matrix test (`tests/product/test_performance_availability_matrix.py`) fails
for a registered id that has no row, so a registered metric cannot ship without its unsupported cases. The ids are names only: no reason code and no number lives here.
"""

from __future__ import annotations

from typing import FrozenSet

#: valuation (Ruling 1), window (5, 6, 7), amounts (8), gains (3) and attribution (9)
METRIC_IDS: FrozenSet[str] = frozenset({
    "holding_value", "cash_value", "receivable_value", "portfolio_value", "portfolio_value_priced_holdings",
    "gain_absolute", "return_twr", "return_annualized", "return_mwr", "return_mwr_annualized",
    "income_amount", "fees_amount", "taxes_amount", "financing_amount", "conversion_result_amount",
    "realized_gain", "realized_gain_total", "unrealized_gain", "unrealized_gain_total", "remaining_basis", "since_acquisition",
    "attribution_money", "attribution_return", "attribution_breakdown",
})
