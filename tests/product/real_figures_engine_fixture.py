"""The ENGINE-MADE document the real-mode key figures are proved on (PD-0080). Not a test module (the name does not match `test*.py`).

The REAL create (`real_service.service._stage_real`) stores `compute_for_portfolio(...).canonical_json()`; the screen reads that document. It is not wired until
R8, so no stored instance exists. This module produces the same document from the REAL performance engine and INVENTED inputs, in memory, with no database row:
`performance.engine.compute` (the pure function `compute_for_portfolio` calls after reading its events), then `ComputationResult.canonical_json()` (the
serialization `_stage_real` stores), parsed back the way the route parses `archive.issued`. The inputs are `performance_kit`'s invented worlds (the same ones
`test_performance_cp3b` uses for the rulings the three states come from); the results say `synthetic`, which is why `compute_for_portfolio`'s gate would refuse
them (CP3-10): `compute_for_portfolio` refuses these particular worlds. It CAN run in memory on the non-synthetic in-memory kit of `test_performance_midpoint`
(`market(None, real_quotes=True)`, usage scope INTERNAL_DEVELOPMENT_ONLY, with `_pin` replaced), and `test_real_figures_engine_fixture` does that to compare it with
`engine.compute` on the same ledgers. That output says `synthetic: false` over an invented reading, so it is used in memory only and never stored or checked in
(the first `synthetic = false` record belongs to the real run). The checked-in fixture is made with `engine.compute` directly.

The fixture keeps the listed figures' rows of BOTH views (`NATIVE` rows come before `REPORTING` rows in an engine document), so the client's view check is tested.

Further cases: RECEIVABLE (an accrued dividend, G-6) and SUBCENT (AAPL close 1.004 USD, quantity 1, USD cash 1.004), is the F-3 case: the total 2.01 has parts 1.01 and 1 in `breakdown`, while the
holding row alone says 1.

THE THREE STATES, each produced by the engine and none edited:
  AVAILABLE   Example W (performance/1.0 section 5), as of 2025-04-02: a total with a number, no stale weight, a breakdown.
  LIMITED     Example V-2(a): a stale holding, 3 sessions missed: total LIMITED + STALE_DATA with `stale_weight_presented` and a breakdown.
  SUPPRESSED  Example V-2(c): a CNH cash deposit with no FX history: total INSUFFICIENT_DATA + MISSING_FX_HISTORY, no number, and the partial figure
              `portfolio_value_priced_holdings` with its excluded counts.
"""
from __future__ import annotations

import datetime
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import performance_kit as pk  # noqa: E402
from domain.currency import CurrencyCode  # noqa: E402
from domain.ledger import EventType, SplitRatio  # noqa: E402
from performance import engine  # noqa: E402

D = datetime.date
USD, HKD, CNH = CurrencyCode("USD"), CurrencyCode("HKD"), CurrencyCode("CNH")
PERF = engine.performance_conventions()
PORTFOLIO = uuid.UUID(int=0x5EED)
FIXTURE = HERE.parents[1] / "web" / "src" / "real-mode-engine-result.fixture.json"

#: The rows of the listed figures, and the partial row: (metric_id, view). The fixture keeps these rows verbatim and, for every other row, only its identity.
LISTED = tuple((metric, view) for metric in ("portfolio_value", "holding_value", "cash_value", "receivable_value") for view in ("NATIVE", "REPORTING")) + (
    ("portfolio_value_priced_holdings", "REPORTING"),)


def _document(result) -> dict:
    """The stored document, exactly as `_stage_real` stores it and the route reads it: `canonical_json()` bytes, parsed."""
    return json.loads(result.canonical_json().encode("utf-8"))


def _compute(ledger, as_of, world):
    return engine.compute(ledger.rows, ledger.version, as_of, USD, world.store, world.ident, world.market, PERF, portfolio_id=PORTFOLIO, suppressions=())


def documents() -> dict:
    """name -> the stored document of the engine's result for that invented case."""
    w = pk.world_w()
    available = _compute(pk.example_w_ledger(w.h), D(2025, 4, 2), w)

    w = pk.world_w(closes={D(2025, 3, 28): "400.00"})
    L = pk.Ledger()
    L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=pk.Money(Decimal(4000), USD))
    L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), HKD, amount=pk.Money(Decimal(790), HKD))
    L.add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), HKD, listing_id=w.h, quantity=Decimal(100))
    limited = _compute(L, D(2025, 4, 2), w)

    w = pk.world_w()
    L = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2025, 4, 2), USD, amount=pk.Money(Decimal(4000), USD))
    L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 2), CNH, amount=pk.Money(Decimal(1000), CNH))
    suppressed = _compute(L, D(2025, 4, 2), w)

    # SUBCENT: an AAPL close of 1.004 USD, quantity 1, USD cash 1.004. The engine itself rounds the total's parts so they add to the total: the breakdown shows
    # 1.01 + 1 = 2.01 while the holding row alone shows 1 (F-3: the parts come from `breakdown`, never from the separate rows).
    aapl = pk.x.lid(pk.x.identity(), "AAPL", "XNAS")
    w = pk.world_w(extra=[pk.quote(aapl, D(2025, 4, 2), "1.004", USD, "US")])
    assert w.aapl == aapl
    L = pk.Ledger()
    L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=pk.Money(Decimal("1.004"), USD))
    L.add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), USD, listing_id=w.aapl, quantity=Decimal(1))
    subcent = _compute(L, D(2025, 4, 2), w)

    # RECEIVABLE: an accrued dividend (Ruling 8.1, ex-date <= as-of < pay date), valued per Ruling 1.3. By hand: holding 100 x 400 x 5/39 = 200,000/39, shown 5128.21;
    # cash 6000; receivable 780 x 5/39 = 100; total 11228.21.
    w = pk.world_w()
    L = pk.Ledger()
    L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=pk.Money(Decimal(6000), USD))
    L.add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), HKD, listing_id=w.h, quantity=Decimal(100))
    L.add(pk.A1, EventType.DIVIDEND, D(2025, 4, 4), HKD, listing_id=w.h, amount=pk.Money(Decimal(780), HKD), ex_date=D(2025, 3, 31))
    receivable = _compute(L, D(2025, 4, 2), w)

    # SPLIT_UNRESOLVED (H-2): 3 shares and a recorded 1-for-2 split: 3 x 1/2 = 1.5 is not integral, so the quantity is unresolved (ledger-replay section 7). Holding,
    # total and partial are INSUFFICIENT_DATA + UNRESOLVED_CONVENTION with no value, and the partial row stores counts of 0 and 0 (`_partial` returns none for an unknown set).
    w = pk.world_w()
    L = pk.Ledger()
    L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=pk.Money(Decimal(4000), USD))
    L.add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), HKD, listing_id=w.h, quantity=Decimal(3))
    L.add(pk.A1, EventType.SPLIT, D(2025, 3, 31), HKD, listing_id=w.h, split_ratio=SplitRatio(Decimal(1), Decimal(2)))
    unresolved = _compute(L, D(2025, 4, 2), w)
    return {"AVAILABLE": _document(available), "LIMITED": _document(limited), "SUPPRESSED": _document(suppressed), "SUBCENT": _document(subcent),
            "RECEIVABLE": _document(receivable), "SPLIT_UNRESOLVED": _document(unresolved)}


def record(document: dict) -> dict:
    """What the fixture keeps of one document: the top-level keys, the identity of every metric row (id, view, subject, state, reason), and the listed rows
    verbatim."""
    metrics = document["metrics"]
    return {
        "top_keys": sorted(document),
        "metric_keys": sorted(metrics[0]) if metrics else [],
        "index": [[m["metric_id"], m["view"], m["subject"], m["state"], m["reason"]] for m in metrics],
        "rows": [m for m in metrics if (m["metric_id"], m["view"]) in LISTED],
    }


def records() -> dict:
    return {name: record(document) for name, document in documents().items()}


if __name__ == "__main__":
    print(json.dumps(records(), sort_keys=True, separators=(",", ":")))
