"""Demonstration A: the fully SYNTHETIC cross-border portfolio (tech plan 16.10; PD-0035 section 3).

WHICH GOLDEN PORTFOLIOS COVER US + CN + HK, and what this builds. No single golden portfolio holds US, Mainland China and Hong Kong positions with USD, HKD and CNY cash:
- `P1` (cp1_golden/1.1; USD reporting) holds US (AAPL, MSFT) and HK (0700) positions, USD and HKD cash, a split, an internal transfer, a conversion, fees, financing, a reversal and a correction,
  a missing cost basis and an unresolved basis: the richest history, but no CN holding and no CNY cash;
- `P3` (part 1 and part 3; CNY reporting) holds the CN position (SYNA) and the Southbound HK position (0700 paid in CNY), with USD, HKD and CNH cash, but no US holding.
So the demonstration EXTENDS P1 with one Mainland China account (A4: a CNY deposit and the purchase of SYNA, as P3 does it on 2025-03-03), one HK dividend with an ex-date before its pay date (so the
pack shows a receivable and its FX) and its withholding, and one USD withdrawal (a deposit-versus-gain contrast). Everything else is P1's own events at the golden prices and fixings (the release
is the golden release of parts 1 to 4). NO expected value is derived here: the pack reports what the engine computes; the golden tests are the correctness proof.

The synthetic world is the golden kit's expansion of the fixtures into real CP2 layouts under synthetic source ids (`tests/product/cp3_golden_kit.py`); this tool loads that kit at run time from the
repository's `tests/product` directory (it is a human/CI tool, never imported by product code).
"""

from __future__ import annotations

import copy
import datetime
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from corporate_actions_service import split_confirmation as f8b
from domain.currency import CurrencyCode
from performance.engine import performance_conventions
from performance.periods import WindowRule, WindowSpec
from performance_tools.pack import PackSubject

REPO = Path(__file__).resolve().parents[2]
D = datetime.date.fromisoformat
A4 = "a1000000-0000-4000-8000-000000000004"
SYNA = "c0000000-0000-4000-8000-0000000a0001"
ZERO_PORTFOLIO = uuid.UUID("d0000000-0000-4000-8000-0000000000d1")


class KitNotFoundError(RuntimeError):
    pass


def _kit() -> Tuple[Any, Any, Any]:
    kit_dir = REPO / "tests" / "product"
    if not (kit_dir / "cp3_golden_kit.py").is_file():
        raise KitNotFoundError(f"the golden kit is not at {kit_dir}: the synthetic demonstration is built from it")
    if str(kit_dir) not in sys.path:
        sys.path.insert(0, str(kit_dir))
    import cp3_golden_kit as g  # noqa: PLC0415
    import cp3_golden_part4_kit as p4  # noqa: PLC0415
    import test_cp1_reconstruction as cp1  # noqa: PLC0415

    return g, p4, cp1


def extra_events() -> List[Dict[str, Any]]:
    """The events added to P1 (seq 26 to 30): a CN account's deposit and purchase, an accrued HK dividend with its withholding, and a USD withdrawal."""
    def ev(seq: int, label: str, **kw: Any) -> Dict[str, Any]:
        base = {"event_id": f"e1000000-0000-4000-8000-{seq:012d}", "source_reference": f"DEMO-{label}"}
        base.update(kw)
        return {"ledger_seq": seq, "label": label, "event": base}

    return [
        ev(26, "CN-DEPOSIT", account_id=A4, event_type="DEPOSIT", event_date="2025-03-03", currency="CNY", amount={"amount": "30000", "currency": "CNY"}),
        ev(27, "CN-BUY-SYNA", account_id=A4, event_type="BUY", event_date="2025-03-03", currency="CNY", listing_id=SYNA, quantity="2000", amount={"amount": "20000", "currency": "CNY"}),
        ev(28, "HK-DIVIDEND", account_id="a1000000-0000-4000-8000-000000000002", event_type="DIVIDEND", event_date="2025-04-24", currency="HKD",
           listing_id="c0000000-0000-4000-8000-000000000700", amount={"amount": "1000", "currency": "HKD"}, ex_date="2025-04-10"),
        ev(29, "HK-WITHHOLDING", account_id="a1000000-0000-4000-8000-000000000002", event_type="TAX", event_date="2025-04-24", currency="HKD",
           listing_id="c0000000-0000-4000-8000-000000000700", amount={"amount": "100", "currency": "HKD"}),
        ev(30, "US-WITHDRAWAL", account_id="a1000000-0000-4000-8000-000000000001", event_type="WITHDRAWAL", event_date="2025-04-15", currency="USD", amount={"amount": "500", "currency": "USD"}),
    ]


def build_synthetic_subject() -> Tuple[PackSubject, Any]:
    """The demonstration subject and the market (caller closes it)."""
    g, p4, cp1 = _kit()
    ids = cp1.Ids(randomize=False)
    market = p4.build_market(ids)
    p1 = copy.deepcopy(cp1.portfolio_named("P1"))
    p1["accounts"] = list(p1["accounts"]) + [{"account_id": A4, "name": "A4 (CN, CNY)"}]
    p1["events"] = list(p1["events"]) + extra_events()
    events = tuple(cp1.sequenced(cp1.build_events(p1, ids)))
    names = {ids(a["account_id"]): a["name"] for a in p1["accounts"]}
    policy = f8b.ConfirmationPolicy(frozenset({g.CA_FEED}), frozenset({g.CA_FILING}))
    files = tuple({"source_id": m.source_id, "data_kind": m.data_kind.value, "file_sha256": m.file_sha256, "payload_filename": m.payload_filename, "usage_scope": m.usage_scope.value,
                   "retrieval_time": m.retrieval_time, "admitted": True, "synthetic": m.usage_scope.value == "SYNTHETIC_TEST"} for m in market.manifests)
    as_of = D("2025-04-30")
    subject = PackSubject(
        name="DEMO-A: US + HK + CN synthetic cross-border portfolio", kind="SYNTHETIC_DEMONSTRATION_A",
        description=("Golden P1 (US AAPL and MSFT, HK 0700; USD and HKD cash; a 4:1 split; an internal transfer; a conversion with its correction; fees and financing; a missing and an unresolved cost basis) "
                     "extended with a Mainland China account (CNY cash, SYNA), a HK dividend accrued from its ex-date and a USD withdrawal. Prices, fixings and calendars are the golden SYNTHETIC release "
                     "(parts 1 to 4); the engine is the production engine."),
        portfolio_id=ZERO_PORTFOLIO, events=events, ledger_version=max(e.ledger_seq for e in events), reporting=CurrencyCode("USD"), store=market.store, resolver=market.ident,
        market_conventions=market.conventions, perf=performance_conventions(), policy=policy, as_of=as_of,
        windows=(("SINCE_INCEPTION", WindowSpec(WindowRule.SINCE_INCEPTION)), ("CUSTOM_FROM_2025-03-31", WindowSpec(WindowRule.CUSTOM, None, D("2025-03-31"))),
                 ("TRAILING_1M", WindowSpec(WindowRule.TRAILING_MONTHS, 1)), ("YTD", WindowSpec(WindowRule.YTD))),
        files=files, account_names=names,
        notes=("The as-of date 2025-04-30 is the last session of the synthetic CN series (SYNA); P1's later events (May and June) are in the ledger and not yet in force at that date.",
               "YTD starts before the portfolio's first event, so it is an explicit INSUFFICIENT_DATA (WINDOW_BEFORE_INCEPTION), not a number.",
               "SYNA has stale sessions 2025-03-17 to 03-19 (the golden P3 case): returns that need every day (attribution) are LIMITED + STALE_DATA there."),
        limitations=("Synthetic data throughout: this proves the engine and the pack, not a market fact.",
                     "Gains follow FIFO/1; a broker's lot method may differ."))
    return subject, market
