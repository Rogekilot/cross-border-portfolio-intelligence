"""Loader and checker for the CP3 golden fixture, part 3 (`methodology/fixtures/cp3_golden/cp3_golden_part3.json`, `cp3_golden/1.2-part3`): FIFO lots, relief records, realized and
unrealized gain, remaining basis, the since-acquisition split, the gain aggregates, a carried split taint ended by FIFO relief, recorded acquisition dates (`acquired_on`).

Like parts 1 and 2 this NEVER edits the fixture and never derives an expected value. M is part 1's synthetic files + part 2's additions + part 3's (two listings, SYNF and SYNT, and a
synthetic corroborated 4:1 split of SYNT), all expanded mechanically into real CP2 layouts under synthetic source ids and ingested through the real adapters. The lot book, relief and
replay-basis items read the ONE lot fold (`domain.replay`); the gain, valuation and window items read the performance engine. `check_*` return `Mismatch` records: a mismatch is a FINDING
for the Quant or the engineer, and neither side is adjusted here.
"""

import copy
import datetime
import json
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp3_golden_kit as g  # noqa: E402
import cp3_golden_part2_kit as p2  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402

from domain.currency import CurrencyCode  # noqa: E402
from domain.replay import reconstruct, reconstruct_fifo  # noqa: E402
from performance.engine import compute_gains  # noqa: E402

PATH = g.FIXTURE_PATH.with_name("cp3_golden_part3.json")
D = datetime.date.fromisoformat
GAIN_KINDS = {"realized_gain", "unrealized_gain", "remaining_basis", "since_acquisition", "realized_gain_total", "unrealized_gain_total"}
REPLAY_KINDS = {"lot_book", "relief", "replay_basis"}

# the loader maps kinds to engine metric ids (a rename is a mapping change, not a fixture change)
g.METRIC_ID.update({k: k for k in GAIN_KINDS})


def load_fixture() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"), parse_float=g._no_float)


FIXTURE = load_fixture()


def content_hash(fixture: dict = FIXTURE) -> str:
    return g.content_hash(fixture)


def items(fixture: dict = FIXTURE) -> Iterable[Tuple[dict, dict, dict]]:
    return g.items(fixture)


def extra_of(fixture: dict = FIXTURE) -> dict:
    """Part 2's additions plus this part's, as ONE release (the fixture's `extends` rule)."""
    two = p2.extra_of()
    add = fixture["market_data_additions"]
    return {"listings": list(two["listings"]) + list(fixture["listings_added"]), "series": list(two["series"]) + list(add["prices"]["series"]),
            "corporate_actions": list(two["corporate_actions"]) + list(add["corporate_actions"]), "release_name": "cp3-golden-part3"}


def source_of(portfolio: dict) -> dict:
    """The portfolio whose events and accounts the fixture means: its own; part 1's P3 (seq 1-7) PLUS `events_added` (seq 8-13); `cp1_golden/1.1` for P1 and P2."""
    if "events" in portfolio:
        return portfolio
    if portfolio.get("events_added"):
        base = p2.part1_portfolio(portfolio["portfolio_id"])
        added = [dict(e, label=e.get("label", f"P3-added-{e['ledger_seq']}")) for e in portfolio["events_added"]]
        return dict(base, events=list(base["events"]) + added)
    return cp1.portfolio_named(portfolio["name"][:2])


def portfolio_events(portfolio: dict, ids):
    return cp1.sequenced(cp1.build_events(source_of(portfolio), ids))


def build_market(ids) -> g.Market:
    return g.Market(ids, extra=extra_of())


class Runner(p2.Runner):
    """Part 2's runner (F8-B dry run supplies the suppressions) with `compute_gains` and the replay reads."""

    def __init__(self, market, ids, events_by_portfolio, verify_identities: bool = False, seq_map=None):
        super().__init__(market, ids, events_by_portfolio, verify_identities, seq_map)
        self.portfolios = {p["name"]: p for p in FIXTURE["portfolios"]}
        self._gains: Dict[Any, Any] = {}

    def gains(self, portfolio: dict, assertion: dict, request: Optional[dict] = None):
        key = (portfolio["name"], assertion["as_of"], assertion["ledger_version"], json.dumps(request, sort_keys=True))
        if key not in self._gains:
            version = self.version(portfolio, assertion)
            spec = None if request is None else g.spec_of(request)
            self._gains[key] = compute_gains(
                self.events[portfolio["name"]], version, D(assertion["as_of"]), CurrencyCode(portfolio["reporting_currency"]), self.market.store, self.market.ident,
                self.market.conventions, self.perf, suppressions=self.suppressions_for(portfolio, version), window=spec, portfolio_id=self.ids(portfolio["portfolio_id"]))
        return self._gains[key]

    def fifo(self, portfolio: dict, assertion: dict):
        return reconstruct_fifo(self.events[portfolio["name"]], D(assertion["as_of"]), self.version(portfolio, assertion))

    def none(self, portfolio: dict, assertion: dict):
        return reconstruct(self.events[portfolio["name"]], D(assertion["as_of"]), self.version(portfolio, assertion))


# --- comparison -----------------------------------------------------------------------------------------------------------------------------------------------------

def _lot_dict(lot, ids) -> Dict[str, Any]:
    return lot.to_dict()


def _expected_lot(item: dict, ids) -> Dict[str, Any]:
    out = {
        "origin_event_id": str(ids(item["origin_event_id"])),
        "carry": [{"from_account_id": str(ids(h["from_account_id"])), "out_event_id": str(ids(h["out_event_id"])), "in_event_id": str(ids(h["in_event_id"])), "date": h["date"]}
                  for h in item["carry"]],
        "acquisition_date": item["acquisition_date"], "date_kind": item["date_kind"], "basis_currency": item["basis_currency"],
        "units": str(Fraction(item["units"])), "unit_cost": None if item["unit_cost"] is None else str(Fraction(item["unit_cost"])),
        "basis": None if item["basis"] is None else str(Fraction(item["basis"])),
    }
    return out


def _norm(d: Dict[str, Any]) -> Dict[str, Any]:
    """The comparable form of an actual lot dict: fraction strings are canonical (`p` or `p/q`); hops keep only the fields the fixture states."""
    out = dict(d)
    out["carry"] = [{k: h[k] for k in ("from_account_id", "out_event_id", "in_event_id", "date")} for h in d["carry"]]
    out.pop("origin_event_type", None)
    return out


def _lot_key(d: Dict[str, Any]) -> Tuple[str, Tuple[str, ...]]:
    return (d["origin_event_id"], tuple(h["out_event_id"] for h in d["carry"]))


def _compare_lots(aid: str, kind: str, label: str, expected: List[dict], actual: List[dict], ids) -> List[g.Mismatch]:
    want = {_lot_key(e): e for e in (_expected_lot(x, ids) for x in expected)}
    have = {_lot_key(a): a for a in (_norm(x) for x in actual)}
    out: List[g.Mismatch] = []
    if set(want) != set(have):
        out.append(g.Mismatch(aid, kind, label, "lots (set of identities)", sorted(want), sorted(have)))
    for key in sorted(set(want) & set(have)):
        for field in sorted(want[key]):
            if want[key][field] != have[key][field]:
                out.append(g.Mismatch(aid, kind, label, f"lot {key[0][-4:]}/{len(key[1])} {field}", want[key][field], have[key][field]))
    return out


def check_lot_book(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[g.Mismatch]:
    ids = runner.ids
    fifo = runner.fifo(portfolio, assertion)
    label = f"{item['account_id'][-4:]}/{item['listing_id'][-4:]}"
    book = fifo.book(ids(item["account_id"]), ids(item["listing_id"]))
    # a closed position has no book in the replay output (as `none` does not emit it): the loader reads it as quantity 0 and no lots (the fixture: "A1's book is empty")
    quantity = Fraction(0) if book is None else book.quantity
    lots = [] if book is None else [lot.to_dict() for lot in book.lots]
    out: List[g.Mismatch] = []
    if quantity is None or quantity != Fraction(item["quantity"]):
        out.append(g.Mismatch(assertion["id"], "lot_book", label, "quantity", item["quantity"], None if quantity is None else str(quantity)))
    out += _compare_lots(assertion["id"], "lot_book", label, item["lots"], lots, ids)
    return out


def check_relief(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[g.Mismatch]:
    ids = runner.ids
    fifo = runner.fifo(portfolio, assertion)
    label = item["event_id"][-6:]
    relief = fifo.relief(ids(item["event_id"]))
    if relief is None:
        return [g.Mismatch(assertion["id"], "relief", label, "relief", "present", None)]
    if relief.withheld:
        return [g.Mismatch(assertion["id"], "relief", label, "relief", "portions", [c.value for c in relief.causes])]
    return _compare_lots(assertion["id"], "relief", label, item["portions"], [p.to_dict() for p in relief.portions], ids)


def check_replay_basis(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[g.Mismatch]:
    ids = runner.ids
    state = runner.none(portfolio, assertion) if item["mode"] == "NONE" else runner.fifo(portfolio, assertion).state
    label = f"{item['mode']} {item['account_id'][-4:]}/{item['listing_id'][-4:]}"
    out: List[g.Mismatch] = []
    aid = assertion["id"]
    account, listing = ids(item["account_id"]), ids(item["listing_id"])
    pos = next((p for a in state.accounts if a.account_id == account for p in a.positions if p.listing_id == listing), None)
    if pos is None:
        return [g.Mismatch(aid, "replay_basis", label, "position", "present", None)]
    entries = pos.cost_basis
    available = all(e.result.value is not None for e in entries)
    if (item["state"] == "AVAILABLE") != available:
        out.append(g.Mismatch(aid, "replay_basis", label, "state", item["state"], "AVAILABLE" if available else "INSUFFICIENT_DATA"))
        return out
    if available:
        got = sorted((e.currency.code, str(e.result.value)) for e in entries)
        want = sorted((m["currency"], str(Decimal(m["amount"]))) for m in item["value"])
        if got != want:
            out.append(g.Mismatch(aid, "replay_basis", label, "value", want, got))
    else:
        reason = entries[0].result.reason_code
        if (None if reason is None else reason.value) != item["reason"]:
            out.append(g.Mismatch(aid, "replay_basis", label, "reason", item["reason"], None if reason is None else reason.value))
        if item.get("detail") is not None and sorted(d.value for d in pos.basis_detail) != sorted(item["detail"]):
            out.append(g.Mismatch(aid, "replay_basis", label, "detail", sorted(item["detail"]), sorted(d.value for d in pos.basis_detail)))
    return out


def _metrics(res, metric_id: str, view: Optional[str] = None, **subject: str) -> List[Any]:
    return [m for m in res.metrics if m.metric_id == metric_id and (view is None or m.view == view)
            and all(dict(m.subject).get(k) == v for k, v in subject.items())]


def _only(res, metric_id: str, view, **subject):
    found = _metrics(res, metric_id, view, **subject)
    return found[0] if len(found) == 1 else found


def _item_subject(item: dict, ids) -> Dict[str, str]:
    s: Dict[str, str] = {}
    if "event_id" in item:
        s["event"] = str(ids(item["event_id"]))
    if "account_id" in item:
        s["account"] = str(ids(item["account_id"]))
    if "listing_id" in item:
        s["listing"] = str(ids(item["listing_id"]))
    return s


def check_gain_item(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[g.Mismatch]:
    ids = runner.ids
    aid, kind = assertion["id"], item["kind"]
    request = item["window"]["request"] if "window" in item else None
    res = runner.gains(portfolio, assertion, request)
    label = g._label(item)
    subject = _item_subject(item, ids)
    view = item.get("view")
    if kind == "remaining_basis" and view == "NATIVE" and isinstance(item["value"], list):
        found = _metrics(res, "remaining_basis", "NATIVE", **subject)
        got = sorted((m.currency, m.result.value, m.exact) for m in found if m.result.value is not None)
        want = sorted((v["currency"], Decimal(v["value"]), Fraction(v["exact"])) for v in item["value"])  # numeric equality: 17500.00 is 17500
        out = []
        if got != want:
            out.append(g.Mismatch(aid, kind, label, "value per currency", want, got))
        bad = [m for m in found if m.result.sufficiency_state.value != item["state"]]
        if bad:
            out.append(g.Mismatch(aid, kind, label, "state", item["state"], sorted({m.result.sufficiency_state.value for m in bad})))
        return out
    if kind == "since_acquisition":
        lot_text = str(ids(item["lot"]["origin_event_id"])) + "".join(f":{ids(x)}" for x in item["lot"]["carry_out_event_ids"])
        m = _only(res, "since_acquisition", "REPORTING", lot=lot_text, **subject)
        if isinstance(m, list):
            return [g.Mismatch(aid, kind, label, "metric", "exactly one", len(m))]
        out = []
        if m.result.sufficiency_state.value != item["state"]:
            out.append(g.Mismatch(aid, kind, label, "state", item["state"], m.result.sufficiency_state.value))
        reason = None if m.result.reason_code is None else m.result.reason_code.value
        if reason != item["reason"]:
            out.append(g.Mismatch(aid, kind, label, "reason", item["reason"], reason))
        if item.get("detail") is not None and sorted(set(m.details)) != sorted(item["detail"]):
            out.append(g.Mismatch(aid, kind, label, "detail", sorted(item["detail"]), sorted(set(m.details))))
        if item["total"] is None:
            if m.result.value is not None:
                out.append(g.Mismatch(aid, kind, label, "total", None, str(m.result.value)))
            return out
        if m.result.value != Decimal(item["total"]["value"]):
            out.append(g.Mismatch(aid, kind, label, "total.value", item["total"]["value"], None if m.result.value is None else str(m.result.value)))
        if m.exact != Fraction(item["total"]["exact"]):
            out.append(g.Mismatch(aid, kind, label, "total.exact", item["total"]["exact"], None if m.exact is None else str(m.exact)))
        have = {name: (exact, shown) for name, shown, exact in m.breakdown}
        for part in item["parts"]:
            got = have.get(part["line"])
            if got is None or got[0] != Fraction(part["exact"]) or got[1] != Decimal(part["apportioned"]):
                out.append(g.Mismatch(aid, kind, label, f"part {part['line']}", (part["exact"], part["apportioned"]), None if got is None else (str(got[0]), str(got[1]))))
        if [name for name, _s, _e in m.breakdown] != [p["line"] for p in item["parts"]]:
            out.append(g.Mismatch(aid, kind, label, "parts order", [p["line"] for p in item["parts"]], [n for n, _s, _e in m.breakdown]))
        return out
    # the single-metric kinds
    if kind == "realized_gain":
        found = _metrics(res, "realized_gain", view, **subject)
        if view == "NATIVE":
            found = [m for m in found if m.currency == item.get("currency")]
    elif kind in ("realized_gain_total", "unrealized_gain_total"):
        found = _metrics(res, kind, view)
    else:
        found = _metrics(res, kind, view, **subject)
        if view == "NATIVE" and item.get("currency") is not None:
            found = [m for m in found if m.currency in (item["currency"], None)]
    if len(found) != 1:
        return [g.Mismatch(aid, kind, label, "metric", "exactly one", len(found))]
    out = g.check_item(SimpleNamespace(metrics=[found[0]]), portfolio, assertion, dict(item, view=view), ids)
    m = found[0]
    if "excluded_weight" in item and item["state"] == "LIMITED":
        want = item["excluded_weight"]
        if m.excluded_weight != Fraction(want["exact"]):
            out.append(g.Mismatch(aid, kind, label, "excluded_weight.exact", want["exact"], None if m.excluded_weight is None else str(m.excluded_weight)))
        if m.excluded_weight_presented != Decimal(want["value"]):
            out.append(g.Mismatch(aid, kind, label, "excluded_weight.value", want["value"], None if m.excluded_weight_presented is None else str(m.excluded_weight_presented)))
    return out


def check_item(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[g.Mismatch]:
    kind = item["kind"]
    if kind == "lot_book":
        return check_lot_book(runner, portfolio, assertion, item)
    if kind == "relief":
        return check_relief(runner, portfolio, assertion, item)
    if kind == "replay_basis":
        return check_replay_basis(runner, portfolio, assertion, item)
    if kind == "split_outcome":
        return p2.check_split_outcome(runner, portfolio, assertion, item)
    if kind in GAIN_KINDS:
        return check_gain_item(runner, portfolio, assertion, item)
    res = runner.window(portfolio, assertion, item["window"]["request"]) if "window" in item else runner.valuation(portfolio, assertion)
    return g.check_item(res, portfolio, assertion, item, runner.ids)


def check_assertion(runner: Runner, portfolio: dict, assertion: dict) -> List[g.Mismatch]:
    out: List[g.Mismatch] = []
    for item in assertion["expect"]:
        out += check_item(runner, portfolio, assertion, item)
    return out


def check_all(runner: Runner) -> Tuple[List[g.Mismatch], int]:
    mismatches: List[g.Mismatch] = []
    checked = 0
    for p in FIXTURE["portfolios"]:
        for a in p["assertions"]:
            mismatches += check_assertion(runner, p, a)
            checked += len(a["expect"])
    return mismatches, checked


def build_runner(ids=None, verify_identities: bool = False) -> Tuple[Runner, g.Market]:
    ids = ids or cp1.Ids(randomize=False)
    market = build_market(ids)
    events = {p["name"]: portfolio_events(p, ids) for p in FIXTURE["portfolios"]}
    runner = Runner(market, ids, events, verify_identities)
    runner.portfolios = {p["name"]: p for p in FIXTURE["portfolios"]}
    return runner, market


if __name__ == "__main__":  # a plain report of every mismatch, for the findings list
    runner, market = build_runner(verify_identities=True)
    print("market-data build issues:", market.issues)
    found, n = check_all(runner)
    print(f"{n} items checked, {len(found)} mismatches")
    for mm in found:
        print(mm)
