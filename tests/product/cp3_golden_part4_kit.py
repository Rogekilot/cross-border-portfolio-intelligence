"""Loader and checker for the CP3 golden fixture, part 4 (`methodology/fixtures/cp3_golden/cp3_golden_part4.json`, `cp3_golden/1.1-part4`): attribution (performance Rulings 9.1 to 9.6).

Like parts 1 to 3 this NEVER edits the fixture and never derives an expected value. M is part 1's synthetic files + the additions of parts 2 and 3 + part 4's (one listing, SYNG, with an
interior five-session gap), all expanded mechanically into real CP2 layouts under synthetic source ids and ingested through the real adapters. The attribution items read
`compute_attribution`; the `twr`, `gain_absolute` and `holding_value` items read the existing window and valuation entries, as in the earlier parts. `check_*` return `Mismatch` records: a
mismatch is a FINDING for the Quant or the engineer, and neither side is adjusted here.

Loader mappings (a rename is a mapping change, not a fixture change): the line `id` is the engine's fixed identifier and is matched BY `id`; the fixture's `line` (the registry position) must
agree with the position of that line in the engine's breakdown; `attribution_money` reads metric `attribution_money` (`value` = G, `breakdown` = the apportioned lines), `attribution_return` reads
`attribution_return` (`value` = the TWR, `breakdown` = the linked components), `attribution_breakdown` reads `attribution_breakdown` with subject `(group_by, line)`; a breakdown part is named
`listing:<id>` or, by component, `position:<listing id>`, `cash:<currency>`, `receivable:<event id>`.
"""

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
import cp3_golden_part3_kit as p3  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402

from domain.currency import CurrencyCode  # noqa: E402
from performance.engine import compute_attribution  # noqa: E402

PATH = g.FIXTURE_PATH.with_name("cp3_golden_part4.json")
D = datetime.date.fromisoformat
ATTRIBUTION_KINDS = {"attribution_money", "attribution_return", "attribution_breakdown"}


def load_fixture() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"), parse_float=g._no_float)


FIXTURE = load_fixture()


def content_hash(fixture: dict = FIXTURE) -> str:
    return g.content_hash(fixture)


def items(fixture: dict = FIXTURE) -> Iterable[Tuple[dict, dict, dict]]:
    return g.items(fixture)


def extra_of(fixture: dict = FIXTURE) -> dict:
    """Parts 2 and 3's additions plus this part's, as ONE release (the fixture's `extends` rule)."""
    three = p3.extra_of()
    add = fixture["market_data_additions"]
    return {"listings": list(three["listings"]) + list(fixture["listings_added"]), "series": list(three["series"]) + list(add["prices"]["series"]),
            "corporate_actions": list(three["corporate_actions"]) + list(add["corporate_actions"]), "release_name": "cp3-golden-part4"}


def source_of(portfolio: dict) -> dict:
    """The portfolio whose events and accounts the fixture means: its own; else the one with the same id in part 3, part 2 or part 1 that carries `events` (part 1's P3 for the seven events of
    ledger version 7); else `cp1_golden/1.1` by name (P1)."""
    if "events" in portfolio:
        return portfolio
    for fixture in (p3.FIXTURE, p2.FIXTURE, g.FIXTURE):
        for other in fixture["portfolios"]:
            if other["portfolio_id"] == portfolio["portfolio_id"] and "events" in other:
                return other
    return cp1.portfolio_named(portfolio["name"].split()[0])


def portfolio_events(portfolio: dict, ids):
    return cp1.sequenced(cp1.build_events(source_of(portfolio), ids))


def build_market(ids) -> g.Market:
    return g.Market(ids, extra=extra_of())


class Runner(p3.Runner):
    """Part 3's runner (gains, replay, F8-B suppressions) with `compute_attribution`."""

    def __init__(self, market, ids, events_by_portfolio, verify_identities: bool = False, seq_map=None):
        super().__init__(market, ids, events_by_portfolio, verify_identities, seq_map)
        self.portfolios = {p["name"]: p for p in FIXTURE["portfolios"]}
        self._attribution: Dict[Any, Any] = {}

    def attribution(self, portfolio: dict, assertion: dict, request: dict, events: Optional[list] = None):
        key = (portfolio["name"], assertion["as_of"], assertion["ledger_version"], json.dumps(request, sort_keys=True), None if events is None else id(events))
        if key not in self._attribution:
            version = self.version(portfolio, assertion)
            self._attribution[key] = compute_attribution(
                self.events[portfolio["name"]] if events is None else events, version, g.spec_of(request), D(assertion["as_of"]), CurrencyCode(portfolio["reporting_currency"]),
                self.market.store, self.market.ident, self.market.conventions, self.perf, suppressions=self.suppressions_for(portfolio, version),
                portfolio_id=self.ids(portfolio["portfolio_id"]))
        return self._attribution[key]


# --- comparison -------------------------------------------------------------------------------------------------------------------------

def _only(res, metric_id: str, **subject: str):
    found = [m for m in res.metrics if m.metric_id == metric_id and all(dict(m.subject).get(k) == v for k, v in subject.items())]
    return found[0] if len(found) == 1 else found


def _common(aid: str, kind: str, label: str, m, item: dict) -> List[g.Mismatch]:
    out: List[g.Mismatch] = []
    if m.result.sufficiency_state.value != item["state"]:
        out.append(g.Mismatch(aid, kind, label, "state", item["state"], m.result.sufficiency_state.value))
    reason = None if m.result.reason_code is None else m.result.reason_code.value
    if reason != item["reason"]:
        out.append(g.Mismatch(aid, kind, label, "reason", item["reason"], reason))
    if item.get("detail") is not None and sorted(set(m.details)) != sorted(item["detail"]):
        out.append(g.Mismatch(aid, kind, label, "detail", sorted(item["detail"]), sorted(set(m.details))))
    w, wm = item["window"], m.window
    for field, expected, actual in (("window.base", D(w["base"]), wm.start), ("window.end", D(w["end"]), wm.end), ("window.days", w["days"], wm.days)):
        if expected != actual:
            out.append(g.Mismatch(aid, kind, label, field, str(expected), str(actual)))
    return out


def _lines(aid: str, kind: str, label: str, m, item: dict, field_exact: str, field_shown: str, tolerance_default: Optional[Decimal] = None) -> List[g.Mismatch]:
    """Compare the eight lines by `id`; `line` must agree with the engine's position."""
    out: List[g.Mismatch] = []
    have = {name: (shown, exact, position + 1) for position, (name, shown, exact) in enumerate(m.breakdown)}
    if [name for name, _s, _e in m.breakdown] != [ln["id"] for ln in item["lines"]]:
        out.append(g.Mismatch(aid, kind, label, "line ids and order", [ln["id"] for ln in item["lines"]], [name for name, _s, _e in m.breakdown]))
    for ln in item["lines"]:
        got = have.get(ln["id"])
        if got is None:
            out.append(g.Mismatch(aid, kind, label, f"line {ln['id']}", "present", None))
            continue
        shown, exact, position = got
        if position != ln["line"]:
            out.append(g.Mismatch(aid, kind, label, f"line {ln['id']} position", ln["line"], position))
        if field_exact in ln and exact != Fraction(ln[field_exact]):
            out.append(g.Mismatch(aid, kind, label, f"line {ln['id']} exact", ln[field_exact], str(exact)))
        want = Decimal(ln[field_shown])
        tol = Decimal(ln["tolerance"]) if ln.get("tolerance") not in (None, "0") else None
        if (tol is None and shown != want) or (tol is not None and abs(shown - want) > tol):
            out.append(g.Mismatch(aid, kind, label, f"line {ln['id']} {field_shown}" + ("" if tol is None else f" (tolerance {tol})"), ln[field_shown], str(shown)))
    return out


def check_money(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[g.Mismatch]:
    aid, kind, label = assertion["id"], "attribution_money", "money"
    res = runner.attribution(portfolio, assertion, item["window"]["request"])
    m = _only(res, "attribution_money")
    if isinstance(m, list):
        return [g.Mismatch(aid, kind, label, "metric", "exactly one", len(m))]
    out = _common(aid, kind, label, m, item)
    if item["total"] is None:
        if m.result.value is not None or m.breakdown or item["lines"] is not None:
            if m.result.value is not None:
                out.append(g.Mismatch(aid, kind, label, "total", None, str(m.result.value)))
            if m.breakdown:
                out.append(g.Mismatch(aid, kind, label, "lines", None, [n for n, _s, _e in m.breakdown]))
        return out
    if m.result.value != Decimal(item["total"]["value"]):
        out.append(g.Mismatch(aid, kind, label, "total.value", item["total"]["value"], None if m.result.value is None else str(m.result.value)))
    if m.exact != Fraction(item["total"]["exact"]):
        out.append(g.Mismatch(aid, kind, label, "total.exact", item["total"]["exact"], None if m.exact is None else str(m.exact)))
    return out + _lines(aid, kind, label, m, item, "exact", "apportioned")


def check_return(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[g.Mismatch]:
    aid, kind, label = assertion["id"], "attribution_return", "return"
    res = runner.attribution(portfolio, assertion, item["window"]["request"])
    m = _only(res, "attribution_return")
    if isinstance(m, list):
        return [g.Mismatch(aid, kind, label, "metric", "exactly one", len(m))]
    out = _common(aid, kind, label, m, item)
    if item["twr"] is None:
        if m.result.value is not None:
            out.append(g.Mismatch(aid, kind, label, "twr", None, str(m.result.value)))
        if m.breakdown:
            out.append(g.Mismatch(aid, kind, label, "lines", None, [n for n, _s, _e in m.breakdown]))
        return out
    if m.result.value != Decimal(item["twr"]["value"]):
        out.append(g.Mismatch(aid, kind, label, "twr.value", item["twr"]["value"], None if m.result.value is None else str(m.result.value)))
    if m.exact != Fraction(item["twr"]["exact"]):
        out.append(g.Mismatch(aid, kind, label, "twr.exact", item["twr"]["exact"], None if m.exact is None else str(m.exact)))
    return out + _lines(aid, kind, label, m, item, "exact", "value")


def _part_name(part: dict, group_by: str, ids) -> str:
    if group_by == "listing":
        return f"listing:{ids(part['listing_id'])}"
    if part["component"] == "position":
        return f"position:{ids(part['listing_id'])}"
    if part["component"] == "cash":
        return f"cash:{part['currency']}"
    return f"receivable:{ids(part['event_id'])}"


def part_order_key(part: dict, group_by: str, ids) -> tuple:
    """The Ruling 9.6 order of a fixture part UNDER THE IDS THE RUN USES (the database path generates random listing and event ids, and the order is by id as a UUID integer): components run
    positions, cash by currency code, receivables, events; listings by id; `none` is not a fixture part. The fixture lists its parts in this order for its own (identity) ids only."""
    if group_by == "listing":
        return (ids(part["listing_id"]).int,)
    if part["component"] == "position":
        return (0, ids(part["listing_id"]).int)
    if part["component"] == "cash":
        return (1, part["currency"])
    if part["component"] == "receivable":
        return (2, ids(part["event_id"]).int)
    return (3, ids(part["event_id"]).int)


def expected_parts(item: dict, ids) -> list:
    return sorted(item["parts"], key=lambda p: part_order_key(p, item["group_by"], ids))


def check_breakdown(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[g.Mismatch]:
    aid, kind, label = assertion["id"], "attribution_breakdown", f"{item['line_id']}/{item['group_by']}"
    res = runner.attribution(portfolio, assertion, item["window"]["request"])
    m = _only(res, "attribution_breakdown", group_by=item["group_by"], line=item["line_id"])
    if isinstance(m, list):
        return [g.Mismatch(aid, kind, label, "metric", "exactly one", len(m))]
    out = _common(aid, kind, label, m, item)
    want = {_part_name(p, item["group_by"], runner.ids): (Fraction(p["exact"]), Decimal(p["apportioned"])) for p in item["parts"]}  # a decomposition object (Ruling 9.6 (1.9))
    have = {name: (exact, shown) for name, shown, exact in m.breakdown}
    in_order = [_part_name(p, item["group_by"], runner.ids) for p in expected_parts(item, runner.ids)]  # the fixture's parts, ordered by Ruling 9.6 under the ids of THIS run
    if in_order != [name for name, _s, _e in m.breakdown]:
        out.append(g.Mismatch(aid, kind, label, "parts and order", in_order, [name for name, _s, _e in m.breakdown]))
    if set(want) != set(have):
        out.append(g.Mismatch(aid, kind, label, "parts", sorted(want), sorted(have)))
    for name in sorted(set(want) & set(have)):
        if want[name][0] != have[name][0]:
            out.append(g.Mismatch(aid, kind, label, f"{name} exact", str(want[name][0]), str(have[name][0])))
        if want[name][1] != have[name][1]:
            out.append(g.Mismatch(aid, kind, label, f"{name} value", str(want[name][1]), str(have[name][1])))
    return out


def check_item(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[g.Mismatch]:
    kind = item["kind"]
    if kind == "attribution_money":
        return check_money(runner, portfolio, assertion, item)
    if kind == "attribution_return":
        return check_return(runner, portfolio, assertion, item)
    if kind == "attribution_breakdown":
        return check_breakdown(runner, portfolio, assertion, item)
    return p3.check_item(runner, portfolio, assertion, item)


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
    return Runner(market, ids, events, verify_identities), market


if __name__ == "__main__":  # a plain report of every mismatch, for the findings list
    runner, market = build_runner(verify_identities=True)
    print("market-data build issues:", market.issues)
    found, n = check_all(runner)
    print(f"{n} items checked, {len(found)} mismatches")
    for mm in found:
        print(mm)
