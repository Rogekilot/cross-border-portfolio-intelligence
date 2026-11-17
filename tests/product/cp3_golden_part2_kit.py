"""Loader and checker for the CP3 golden fixture, part 2 (`methodology/fixtures/cp3_golden/cp3_golden_part2.json`, `cp3_golden/1.1-part2`): the MWR and annualized MWR, the income,
fee, tax, financing and conversion-result amounts, the dividend receivables, and one synthetic split-suppression case.

Like part 1 (`cp3_golden_kit`), this NEVER edits the fixture and never derives an expected value. It builds ONE market-data version M = part 1's synthetic files PLUS part 2's additions
(five new listings and their price files, and the corporate-action pair expanded MECHANICALLY into a real-layout FEED file and FILING file under synthetic source ids, with the fixture's own
ex-date and ratio and no other number), ingests them through the real adapters, and runs the engine. The split-suppression case needs the F8-B detection: the runner runs the dry run over
the pinned ledger and hands the engine the suppressions it implies. `check_*` return `Mismatch` records; a mismatch is a FINDING, never adjusted here.
"""

import datetime
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp3_golden_kit as g  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import CurrencyCode  # noqa: E402
from performance_service import service as svc  # noqa: E402

PATH = g.FIXTURE_PATH.with_name("cp3_golden_part2.json")
D = datetime.date.fromisoformat
POLICY = f8b.ConfirmationPolicy(frozenset({g.CA_FEED}), frozenset({g.CA_FILING}))  # which registered sources are the feed and the filing (the fixture's declaration)


def load_fixture() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"), parse_float=g._no_float)


FIXTURE = load_fixture()


def content_hash(fixture: dict = FIXTURE) -> str:
    return g.content_hash(fixture)


def extra_of(fixture: dict = FIXTURE) -> dict:
    additions = fixture["market_data_additions"]
    return {"listings": fixture["listings_added"], "series": additions["prices"]["series"], "corporate_actions": additions["corporate_actions"],
            "release_name": "cp3-golden-part2"}


def items(fixture: dict = FIXTURE) -> Iterable[Tuple[dict, dict, dict]]:
    return g.items(fixture)


def part1_portfolio(portfolio_id: str) -> dict:
    return next(p for p in g.FIXTURE["portfolios"] if p["portfolio_id"] == portfolio_id)


def source_of(portfolio: dict) -> dict:
    """The portfolio the fixture's events come from: its own `events`, else part 1's (P4, P5, by portfolio id), else `cp1_golden/1.1` (P1, P2, by name)."""
    if "events" in portfolio:
        return portfolio
    if portfolio["events_from"].startswith("cp3_golden part 1"):
        return part1_portfolio(portfolio["portfolio_id"])
    return cp1.portfolio_named(portfolio["name"][:2])


def portfolio_events(portfolio: dict, ids):
    return cp1.sequenced(cp1.build_events(source_of(portfolio), ids))


def build_market(ids) -> g.Market:
    return g.Market(ids, extra=extra_of())


class Runner(g.Runner):
    """`g.Runner` with the F8-B detection: for each (portfolio, ledger version) the dry run over the pinned ledger gives the suppressions the engine is handed."""

    def __init__(self, market, ids, events_by_portfolio, verify_identities: bool = False, seq_map=None):
        super().__init__(market, ids, events_by_portfolio, verify_identities, seq_map)
        self._reports: Dict[Tuple[str, int], f8b.SplitReport] = {}
        self.portfolios = {p["name"]: p for p in FIXTURE["portfolios"]}

    def report(self, portfolio: dict, version: int) -> f8b.SplitReport:
        key = (portfolio["name"], version)
        if key not in self._reports:
            events = [e for e in self.events[portfolio["name"]] if e.ledger_seq <= version]
            listings = sorted({e.event.listing_id for e in events if e.event.listing_id is not None}, key=str)
            currencies = {lid: c for lid in listings for c in [self.market.ident.trading_currency(lid)] if c is not None}
            calendars = self.market.conventions.freshness.calendars
            report, _ = svc.detect_split_suppressions(
                svc.PinnedLedgerAccess(version, events), self.market.store, self.ids(portfolio["portfolio_id"]), listings, datetime.date.min, datetime.date.max,
                POLICY, currencies, calendars=calendars, exchange_of=self.market.ident.exchange_mic)
            self._reports[key] = report
        return self._reports[key]

    def suppressions_for(self, portfolio: dict, version: int):
        return svc.suppressions_from_report(self.report(portfolio, version))


def check_split_outcome(runner: Runner, portfolio: dict, assertion: dict, item: dict) -> List[g.Mismatch]:
    """`split_outcome` (market-data Ruling 6.4a / 4.8 item 4): the F8 outcome for (account, listing, ex_date) and whether an append is allowed. `BARRED_SYNTHETIC_EVIDENCE`
    means the dry run reports NOT_RECORDED with the append barred (never WOULD_APPEND)."""
    out: List[g.Mismatch] = []
    aid = assertion["id"]
    version = runner.version(portfolio, assertion)
    report = runner.report(portfolio, version)
    account, listing, ex = runner.ids(item["account_id"]), runner.ids(item["listing_id"]), D(item["ex_date"])
    mine = [o for o in report.outcomes if (o.account_id, o.listing_id, o.ex_date) == (account, listing, ex)]
    label = f"{item['listing_id']}@{item['ex_date']}"
    if len(mine) != 1:
        return [g.Mismatch(aid, "split_outcome", label, "outcomes", "exactly one", len(mine))]
    o = mine[0]
    if o.linking != item["outcome"]:
        out.append(g.Mismatch(aid, "split_outcome", label, "outcome", item["outcome"], o.linking))
    append = {f8b.SplitDecision.NOT_RECORDED_APPEND_BARRED: "BARRED_SYNTHETIC_EVIDENCE", f8b.SplitDecision.WOULD_APPEND: "WOULD_APPEND"}.get(o.decision, o.decision.value)
    if append != item["append"]:
        out.append(g.Mismatch(aid, "split_outcome", label, "append", item["append"], append))
    # the fixture's ledger_version is the fixture's numbering; a database ledger numbers its own rows (`seq_map`, as for every assertion's `ledger_version`)
    expected_after = item["ledger_version_after"] if runner.seq_map is None else runner.seq_map[portfolio["name"]][item["ledger_version_after"]]
    if report.ledger_version_after != expected_after or report.ledger_version_after != report.ledger_version_before:
        out.append(g.Mismatch(aid, "split_outcome", label, "ledger_version_after", item["ledger_version_after"], report.ledger_version_after))
    return out


def check_assertion(runner: Runner, portfolio: dict, assertion: dict) -> List[g.Mismatch]:
    out: List[g.Mismatch] = []
    for item in assertion["expect"]:
        if item["kind"] == "split_outcome":
            out += check_split_outcome(runner, portfolio, assertion, item)
            continue
        res = runner.window(portfolio, assertion, item["window"]["request"]) if "window" in item else runner.valuation(portfolio, assertion)
        out += g.check_item(res, portfolio, assertion, item, runner.ids)
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
