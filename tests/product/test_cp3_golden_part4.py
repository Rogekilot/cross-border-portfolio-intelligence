"""CP3 golden fixture, part 4 (`methodology/fixtures/cp3_golden/cp3_golden_part4.json`, `cp3_golden/1.2-part4`; `performance/1.9` and later, `ledger-replay/1.5`, `market-data/1.10`): attribution
(Rulings 9.1 to 9.6). 28 items.

The fixture is never edited here and no expected value is derived here: a mismatch is reported (assertion id, expected, actual) and neither side is changed.

Layers: 1. SHAPE and PINS; 2. the expansion of part 4's additions adds no number; 3. PURE: every item compared; 4. STRUCTURAL assertions S4-1 to S4-8; 5. DATABASE (opt-in): the same ledgers
through the real store as `finweb_app` and the market data through the PostgreSQL market-data store.

KNOWN FINDINGS. A finding the engineer reports to the Quant is listed in `KNOWN_FINDINGS` as (assertion id, field), so the suite stays an honest record: the golden test fails if the list is
missing a mismatch, AND if a listed finding no longer occurs (so the entry is removed when the finding is resolved).
"""

import copy
import datetime
import hashlib
import json
import os
import random
import subprocess
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp3_golden_kit as g  # noqa: E402
import cp3_golden_part2_kit as p2  # noqa: E402
import cp3_golden_part3_kit as p3  # noqa: E402
import cp3_golden_part4_kit as p4  # noqa: E402
import pg_market_kit as pk  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402

from marketdata.market11 import market11_conventions  # noqa: E402

FIXTURE = p4.FIXTURE
D = datetime.date.fromisoformat

# A tripwire against a silently trimmed or edited fixture (as parts 1 to 3). It changes only with a new `fixture_id`. Counts come from the fixture FILE; the hash is over the assertions.
FIXTURE_PINS = {
    "cp3_golden/1.2-part4": {
        "expect_counts": {"P12-A1": 2, "P12-A2": 2, "P1-A1": 2, "P6-A1": 3, "P3-A1": 3, "P3-A2": 2, "P21-A1": 5, "P22-V1": 1, "P22-A1": 4, "P14-A1": 2, "P13-A1": 2},
        "expect_total": 28,
        "assertions": 11,
        "content_sha256": "a2c816d803c4a5884890d33ad6c5ed9fdc5ac178830d0d264944b993640b0514",
    },
}
#: Findings reported to the Quant and not adjusted: (assertion id, field). EMPTY: the one finding of CP3e (P22-V1 `price_date_used`) was ruled by the Quant in performance/1.9 Ruling 1.1b (the engine
#: was right; the fixture is re-issued as 1.2-part4 and the engine adds the lineage field `last_print_date`).
KNOWN_FINDINGS = set()
LINE_IDS = ["attr.price", "attr.fx", "attr.price_fx_interaction", "attr.income", "attr.fees", "attr.taxes", "attr.financing", "attr.conversion"]  # Ruling 9.2 (1.7), typed here independently
NEW_KINDS = {"attribution_money", "attribution_return", "attribution_breakdown"}


def describe(found):
    return "\n".join(str(m) for m in found)


def attribution_items():
    return [(p, a, i) for p, a, i in p4.items() if i["kind"] in ("attribution_money", "attribution_return")]


class _Shared(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = cp1.Ids(randomize=False)
        cls.runner, cls.market = p4.build_runner(cls.ids, verify_identities=True)
        cls.addClassCleanup(cls.market.close)

    def portfolio(self, prefix):
        return next(p for p in FIXTURE["portfolios"] if p["name"].split()[0] == prefix)

    def assertion(self, portfolio, assertion_id):
        return next(a for a in portfolio["assertions"] if a["id"] == assertion_id)


class FixtureShapeTests(unittest.TestCase):
    def test_the_fixture_is_the_ratified_one_and_pinned(self):
        pins = FIXTURE_PINS[FIXTURE["fixture_id"]]
        counts = {a["id"]: len(a["expect"]) for p in FIXTURE["portfolios"] for a in p["assertions"]}
        self.assertEqual(counts, pins["expect_counts"])
        self.assertEqual((sum(counts.values()), len(counts)), (pins["expect_total"], pins["assertions"]))
        self.assertEqual({k: v for k, v in FIXTURE["item_counts"].items() if k not in ("note", "total")}, counts)
        self.assertEqual(FIXTURE["item_counts"]["total"], pins["expect_total"])
        self.assertEqual(p4.content_hash(), pins["content_sha256"])
        self.assertEqual(FIXTURE["part"], 4)
        self.assertEqual(FIXTURE["extends"]["fixture_ids"], ["cp3_golden/1.4-part1", "cp3_golden/1.2-part2", "cp3_golden/1.2-part3"])
        sets = FIXTURE["convention_sets"]  # minimum versions (PM ruling OI-P11)
        self.assertEqual((sets["performance"], sets["market_data"]), ("performance/1.9", "market-data/1.10"))
        self.assertTrue(sets["ledger_replay"].startswith("ledger-replay/1.5 (FIFO/1 mode)"))

    def test_every_money_and_return_item_lists_the_eight_lines_in_registry_order_and_line_agrees_with_id(self):
        for _p, a, i in attribution_items():
            if i["kind"] == "attribution_money" and i["lines"] is None or i["kind"] == "attribution_return" and i["lines"] is None:
                continue
            self.assertEqual([ln["id"] for ln in i["lines"]], LINE_IDS, a["id"])
            self.assertEqual([ln["line"] for ln in i["lines"]], list(range(1, 9)), a["id"])
        for _p, a, i in p4.items():
            if i["kind"] == "attribution_breakdown":
                self.assertEqual(LINE_IDS[i["line"] - 1], i["line_id"], a["id"])

    def test_the_fixture_exercises_every_new_kind_and_cannot_pass_vacuously(self):
        kinds = {i["kind"] for _p, _a, i in p4.items()}
        self.assertTrue(NEW_KINDS <= kinds, NEW_KINDS - kinds)
        states = {i["state"] for _p, _a, i in p4.items() if "state" in i}
        self.assertEqual(states, {"AVAILABLE", "LIMITED", "INSUFFICIENT_DATA"})
        self.assertEqual({i["reason"] for _p, _a, i in p4.items() if i["kind"] in NEW_KINDS and i["state"] != "AVAILABLE"}, {"STALE_DATA", "SOURCE_CONFLICT"})
        self.assertEqual({i["group_by"] for _p, _a, i in p4.items() if i["kind"] == "attribution_breakdown"}, {"listing", "component"})

    def test_no_value_in_the_fixture_is_a_float(self):
        def walk(node):
            if isinstance(node, float):
                self.fail(f"a float literal: {node!r}")
            if isinstance(node, dict):
                for v in node.values():
                    walk(v)
            if isinstance(node, list):
                for v in node:
                    walk(v)

        walk(json.loads(p4.PATH.read_text(encoding="utf-8")))


class ForcedIds(cp1.Ids):
    """Ids with some fixture ids forced to chosen UUIDs (the others are the fixture's own), so the id ORDER the database path gets at random can be tested deterministically."""

    def __init__(self, forced):
        super().__init__(randomize=False)
        self.map.update({k: uuid.UUID(int=v) for k, v in forced.items()})


L700, LA1 = "c0000000-0000-4000-8000-000000000700", "c0000000-0000-4000-8000-0000000a0001"


class PartOrderUnderRandomIdsTests(unittest.TestCase):
    """Ruling 9.6 orders breakdown parts BY ID as a UUID integer, so under the database path's random ids the expected order is the fixture's parts re-sorted under the mapped ids, never the
    fixture's own order. These tests force two mappings with OPPOSITE id order and fail deterministically for a checker that assumes the fixture's order."""

    def breakdown_check(self, ids):
        runner, market = p4.build_runner(ids, verify_identities=True)
        self.addCleanup(market.close)
        p = next(x for x in FIXTURE["portfolios"] if x["name"].split()[0] == "P3")
        a = next(x for x in p["assertions"] if x["id"] == "P3-A1")
        item = next(i for i in a["expect"] if i["kind"] == "attribution_breakdown")
        found = p4.check_assertion(runner, p, a)
        res = runner.attribution(p, a, item["window"]["request"])
        m = next(x for x in res.metrics if x.metric_id == "attribution_breakdown" and dict(x.subject) == {"group_by": "listing", "line": "attr.price"})
        return found, [n for n, _s, _e in m.breakdown], item, runner.ids

    def test_the_fixtures_own_order_is_the_9_6_order_under_its_own_ids(self):
        ids = cp1.Ids(randomize=False)
        for _p, _a, i in p4.items():
            if i["kind"] == "attribution_breakdown":
                self.assertEqual(i["parts"], p4.expected_parts(i, ids), i["line_id"])

    def test_the_actual_order_follows_the_mapped_ids_and_the_checker_accepts_both_orders(self):
        ascending = self.breakdown_check(ForcedIds({L700: 1, LA1: 2}))
        descending = self.breakdown_check(ForcedIds({L700: 2, LA1: 1}))
        for found, names, item, ids in (ascending, descending):
            self.assertEqual(found, [], describe(found))
        self.assertEqual(ascending[1][0], f"listing:{ascending[3](L700)}")  # 0700 has the lower id: first
        self.assertEqual(descending[1][0], f"listing:{descending[3](LA1)}")  # SYNA has the lower id: first, so the listings swapped places
        for names in (ascending[1], descending[1]):
            self.assertEqual([n.split(":")[1] for n in names], [str(uuid.UUID(int=1)), str(uuid.UUID(int=2))])  # always ascending by id

    def test_a_checker_that_assumed_the_fixtures_order_would_fail_under_the_reversed_mapping(self):
        _found, names, item, ids = self.breakdown_check(ForcedIds({L700: 2, LA1: 1}))
        naive = [f"listing:{ids(p['listing_id'])}" for p in item["parts"]]  # the fixture's order: 0700 first
        self.assertNotEqual(naive, names)
        self.assertEqual([f"listing:{ids(p['listing_id'])}" for p in p4.expected_parts(item, ids)], names)


class MarketExpansionTests(_Shared):
    def test_the_expansion_ingests_through_the_real_adapters_with_no_issue(self):
        self.assertEqual(self.market.issues, ((), ()))
        md, two, three = g.FIXTURE["market_data"], p2.FIXTURE["market_data_additions"], p3.FIXTURE["market_data_additions"]
        four = FIXTURE["market_data_additions"]
        expected = (len(md["calendars"]) + 1 + len(md["prices"]["series"]) + len(two["prices"]["series"]) + len(three["prices"]["series"]) + len(four["prices"]["series"])
                    + 2 + 2)  # two corporate-action pairs (part 2's and part 3's); part 4 adds none
        self.assertEqual(len(self.market.manifests), expected)
        self.assertTrue(self.market.store.contains_synthetic)
        self.assertTrue(all(m.usage_scope.value == "SYNTHETIC_TEST" for m in self.market.manifests))

    def test_the_new_series_is_exactly_the_fixtures_steps_with_its_five_session_gap_and_nothing_else(self):
        (s,) = FIXTURE["market_data_additions"]["prices"]["series"]
        readings = self.market.store.quotes(self.ids(s["listing_id"]), D(s["first"]), D(s["last"])).readings
        days = {r.observation.value_date for r in readings}
        for gap in s["gaps"]:
            self.assertNotIn(D(gap), days, gap)
        self.assertTrue(days)
        for r in readings:
            day = r.observation.value_date
            step = [x for x in s["steps"] if D(x["from"]) <= day][-1]
            self.assertEqual(r.observation.price, Decimal(step["close"]), day)
        self.assertEqual(FIXTURE["market_data_additions"]["corporate_actions"], [])

    def test_p14_p13_and_p3_use_the_events_of_the_parts_they_come_from(self):
        events = self.runner.events
        self.assertEqual([e.ledger_seq for e in events[self.portfolio("P3")["name"]]], list(range(1, 8)))  # part 1's seven events: no part 3 additions
        self.assertEqual(max(e.ledger_seq for e in events[self.portfolio("P14")["name"]]), 6)
        self.assertEqual(len(events[self.portfolio("P1")["name"]]), 25)
        for p in ("P21", "P22"):
            self.assertEqual(len(events[self.portfolio(p)["name"]]), len(self.portfolio(p)["events"]))


class PureGoldenTests(_Shared):
    def test_every_item_of_every_assertion_matches_the_fixture_except_the_reported_findings(self):
        checked, found_all = 0, []
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                found = p4.check_assertion(self.runner, p, a)
                checked += len(a["expect"])
                found_all += found
        self.assertEqual(checked, 28)
        unexpected = [m for m in found_all if (m.assertion_id, m.field) not in KNOWN_FINDINGS]
        self.assertEqual(unexpected, [], "\n" + describe(unexpected))
        self.assertEqual({(m.assertion_id, m.field) for m in found_all} & KNOWN_FINDINGS, KNOWN_FINDINGS, "a listed finding no longer occurs: remove it from KNOWN_FINDINGS")

    def test_the_checker_really_fails_on_a_wrong_expectation(self):
        def broken(prefix, assertion_id, kind, mutate, pick=lambda i: True):
            p = self.portfolio(prefix)
            a = copy.deepcopy(self.assertion(p, assertion_id))
            item = next(i for i in a["expect"] if i["kind"] == kind and pick(i))
            mutate(item)
            found = p4.check_assertion(self.runner, p, a)
            self.assertTrue([m for m in found if m.kind == kind], (assertion_id, kind))

        broken("P12", "P12-A1", "attribution_money", lambda i: i["total"].update(exact="6105/25"))
        broken("P12", "P12-A1", "attribution_money", lambda i: i["lines"][7].update(apportioned="-25.65"))  # the largest-remainder tie-break and rounding are checked
        broken("P12", "P12-A1", "attribution_money", lambda i: i["lines"][1].update(exact="-7957/975"))
        broken("P12", "P12-A1", "attribution_money", lambda i: i["lines"].reverse())
        broken("P12", "P12-A1", "attribution_money", lambda i: i["lines"][0].update(line=2))
        broken("P12", "P12-A1", "attribution_money", lambda i: i.update(state="LIMITED"))
        broken("P12", "P12-A1", "attribution_return", lambda i: i["lines"][0].update(value="0.025684949598"))  # 1e-10 tolerance: 1.01e-10 away is reported
        broken("P12", "P12-A1", "attribution_return", lambda i: i["twr"].update(exact="2776451/112562501"))
        broken("P12", "P12-A1", "attribution_return", lambda i: i["lines"][6].update(value="0.000000000001"))  # an exactly-zero line is compared exactly
        broken("P6", "P6-A1", "attribution_breakdown", lambda i: i["parts"][0].update(exact="46/8"))
        broken("P6", "P6-A1", "attribution_breakdown", lambda i: i["parts"].pop())
        broken("P3", "P3-A1", "attribution_breakdown", lambda i: i["parts"][1].update(apportioned="1000.01"))
        broken("P6", "P6-A1", "attribution_breakdown", lambda i: i["parts"][2].update(apportioned="6.88"))  # the independently presented 6.88 would sum to 6.76: apportioned is 6.87
        broken("P22", "P22-V1", "holding_value", lambda i: i.update(last_print_date="2025-03-08"))
        broken("P22", "P22-V1", "holding_value", lambda i: i.update(price_date_used="2025-03-07"))  # a withheld holding has no close that values it
        broken("P22", "P22-A1", "attribution_money", lambda i: i.update(state="AVAILABLE", reason=None))
        broken("P13", "P13-A1", "attribution_return", lambda i: i.update(reason="STALE_DATA"))
        broken("P3", "P3-A2", "attribution_money", lambda i: i.update(reason=None))

    def test_a_missing_item_is_reported_not_skipped(self):
        p = self.portfolio("P12")
        a = copy.deepcopy(self.assertion(p, "P12-A1"))
        a["expect"][0]["window"]["request"] = {"rule": "CUSTOM", "base": "2025-03-31"}
        self.assertTrue(p4.check_assertion(self.runner, p, a))  # a different window gives a different result, reported


class StructuralAssertionTests(_Shared):
    def results(self):
        return [(p, a, i, self.runner.attribution(p, a, i["window"]["request"])) for p, a, i in attribution_items()]

    def test_s4_1_every_result_is_synthetic_and_every_manifest_cites_the_fixtures_ids_or_later(self):
        rs = self.results()
        self.assertEqual(len(rs), 20)
        for _p, a, _i, res in rs:
            self.assertTrue(res.manifest.synthetic)
            self.assertEqual(g.convention_problems(dict(res.manifest.conventions), FIXTURE["convention_sets"]), [], a["id"])
            for m in res.metrics:
                self.assertTrue(m.synthetic)
        self.assertEqual({m.metric_id for _p, _a, _i, res in rs for m in res.metrics}, {"attribution_money", "attribution_return", "attribution_breakdown"} | set())

    def test_s4_2_identity_i4_the_lines_sum_to_g_every_day_and_to_g_over_the_window(self):
        """Every calendar day of every available window: the one-day attribution of `(D-1, D]` has lines that sum to that day's `g_D` (read from the window entry's gain over the same one day), the
        daily lines add up to the window lines per line, and the window lines sum to the `gain_absolute` asserted by the window entry."""
        seen_days = 0
        for p, a, i, res in self.results():
            if i["kind"] != "attribution_money" or i["state"] == "INSUFFICIENT_DATA":
                continue
            money = next(m for m in res.metrics if m.metric_id == "attribution_money")
            self.assertEqual(dict(money.lineage)["identity:I-4"], "PASS", a["id"])
            gain = self.runner.window(p, a, i["window"]["request"])
            g_window = next(m for m in gain.metrics if m.metric_id == "gain_absolute").exact
            self.assertEqual(sum((e for _n, _s, e in money.breakdown), Fraction(0)), g_window, a["id"])
            self.assertEqual(money.exact, g_window, a["id"])
            base, end = D(i["window"]["base"]), D(i["window"]["end"])
            per_line = [Fraction(0)] * 8
            day = base + datetime.timedelta(days=1)
            while day <= end:
                fake = {"id": a["id"], "as_of": day.isoformat(), "ledger_version": a["ledger_version"]}
                request = {"rule": "CUSTOM", "base": (day - datetime.timedelta(days=1)).isoformat()}
                one = next(m for m in self.runner.attribution(p, fake, request).metrics if m.metric_id == "attribution_money")
                day_gain = next(m for m in self.runner.window(p, fake, request).metrics if m.metric_id == "gain_absolute").exact
                lines = [e for _n, _s, e in one.breakdown]
                self.assertEqual(sum(lines, Fraction(0)), day_gain, (a["id"], day))
                per_line = [x + y for x, y in zip(per_line, lines)]
                seen_days += 1
                day += datetime.timedelta(days=1)
            self.assertEqual(per_line, [e for _n, _s, e in money.breakdown], a["id"])  # a line's window sum is the sum of its days (Ruling 9.3)
        self.assertGreater(seen_days, 300)

    def test_s4_3_identities_i2_and_i3_run_in_every_call_and_the_daily_product_is_the_segment_twr(self):
        for p, a, i, res in self.results():
            self.assertEqual(res.manifest.identities_run, ("I-2", "I-3", "I-4", "I-9"), a["id"])
            if i["state"] == "INSUFFICIENT_DATA":
                continue
            ret = next(m for m in res.metrics if m.metric_id == "attribution_return")
            lin = dict(ret.lineage)
            self.assertEqual((lin["identity:I-2"], lin["identity:I-3"], lin["identity:I-4"], lin["identity:I-9"]), ("PASS",) * 4, a["id"])
            twr = next(m for m in self.runner.window(p, a, i["window"]["request"]).metrics if m.metric_id == "return_twr")
            self.assertEqual(ret.exact, twr.exact, a["id"])  # the daily product, exactly
        # the TWRs the earlier parts and this one assert for the same windows, read from the fixtures' own text
        expected = {("P12-A1", "attribution_return"): Fraction("2776451/112562500"), ("P14-A1", "attribution_return"): Fraction(1, 40), ("P21-A1", "attribution_return"): Fraction(1067, 15625),
                    ("P6-A1", "attribution_return"): Fraction(47, 61828), ("P3-A2", "attribution_return"): Fraction(35242, 2205125)}
        for p, a, i, res in self.results():
            want = expected.get((a["id"], i["kind"]))
            if want is not None:
                self.assertEqual(next(m for m in res.metrics if m.metric_id == "attribution_return").exact, want, a["id"])

    def test_s4_4_the_apportioned_lines_sum_exactly_to_the_total_and_each_is_within_one_cent(self):
        for _p, a, i, res in self.results():
            if i["kind"] != "attribution_money" or i["state"] == "INSUFFICIENT_DATA":
                continue
            m = next(x for x in res.metrics if x.metric_id == "attribution_money")
            self.assertEqual(sum((s for _n, s, _e in m.breakdown), Decimal(0)), m.result.value, a["id"])
            for name, shown, exact in m.breakdown:
                self.assertLess(abs(Fraction(shown) - exact), Fraction(1, 100), (a["id"], name))

    def test_s4_5_the_linked_components_reconcile_to_the_twr(self):
        for _p, a, i, res in self.results():
            if i["kind"] != "attribution_return" or i["state"] == "INSUFFICIENT_DATA":
                continue
            m = next(x for x in res.metrics if x.metric_id == "attribution_return")
            self.assertLessEqual(abs(sum((e for _n, _s, e in m.breakdown), Fraction(0)) - m.exact), Fraction(1, 10 ** 40), a["id"])  # the internal sum, Ruling 11.2
            self.assertLessEqual(abs(sum((s for _n, s, _e in m.breakdown), Decimal(0)) - m.result.value), Decimal("4.5e-12"), a["id"])  # the presented ones, (8 + 1)/2 quanta
            self.assertEqual(dict(m.lineage)["components_basis"], "DECIMAL_PREC50_HALF_EVEN")
            self.assertLessEqual(abs(Decimal(dict(m.lineage)["carino_residual"])), Decimal("1e-40"))

    def test_s4_6_every_breakdown_sums_exactly_to_its_line_in_every_grouping(self):
        seen = 0
        for _p, a, i, res in self.results():
            if i["kind"] != "attribution_money" or i["state"] == "INSUFFICIENT_DATA":
                continue
            money = next(x for x in res.metrics if x.metric_id == "attribution_money")
            lines = {name: exact for name, _s, exact in money.breakdown}
            groups = [m for m in res.metrics if m.metric_id == "attribution_breakdown"]
            self.assertEqual(len(groups), 8 * 5, a["id"])  # every line in every grouping (listing, component, currency, account, market)
            shown_lines = {name: shown for name, shown, _e in money.breakdown}
            for m in groups:
                sub = dict(m.subject)
                self.assertEqual(sum((e for _n, _s, e in m.breakdown), Fraction(0)), lines[sub["line"]], (a["id"], sub))  # the exact parts sum to the line
                self.assertEqual(m.exact, lines[sub["line"]])
                # Ruling 9.6 (1.9): the APPORTIONED parts sum exactly to the line's apportioned display value in the money attribution, each within one cent of its exact value
                self.assertEqual(sum((s for _n, s, _e in m.breakdown), Decimal(0)), shown_lines[sub["line"]], (a["id"], sub))
                self.assertEqual(dict(m.lineage)["displayed_total"], str(shown_lines[sub["line"]]))
                for _n, shown, exact in m.breakdown:
                    self.assertLess(abs(Fraction(shown) - exact), Fraction(1, 100))
                    self.assertNotEqual(exact, 0)  # a part that is exactly 0 is omitted (item 4)
                seen += 1
        self.assertGreater(seen, 200)

    def test_s4_7_metamorphic_all_in_the_reporting_currency_and_an_interior_valuation_gap(self):
        p14 = self.portfolio("P14")
        a = self.assertion(p14, "P14-A1")
        res = self.runner.attribution(p14, a, {"rule": "SINCE_INCEPTION"})
        money = next(m for m in res.metrics if m.metric_id == "attribution_money")
        ret = next(m for m in res.metrics if m.metric_id == "attribution_return")
        for index in (1, 2, 7):  # fx, price_fx_interaction, conversion
            self.assertEqual(money.breakdown[index][2], 0, money.breakdown[index][0])
            self.assertEqual(ret.breakdown[index][2], 0, ret.breakdown[index][0])
        self.assertEqual(money.breakdown[0][2], money.exact)  # everything is price here
        # P22: the TWR and G stay AVAILABLE, the attribution does not (11.3 #6)
        p22 = self.portfolio("P22")
        a22 = self.assertion(p22, "P22-A1")
        req = {"rule": "SINCE_INCEPTION"}
        window = self.runner.window(p22, a22, req)
        self.assertEqual({m.result.sufficiency_state.value for m in window.metrics if m.metric_id in ("return_twr", "gain_absolute")}, {"AVAILABLE"})
        attr = self.runner.attribution(p22, a22, req)
        self.assertEqual({(m.result.sufficiency_state.value, m.result.reason_code.value) for m in attr.metrics}, {("INSUFFICIENT_DATA", "STALE_DATA")})
        for m in attr.metrics:
            self.assertIsNone(m.result.value)
            self.assertEqual((m.breakdown, m.exact), ((), None))
            self.assertTrue(m.causes)

    def test_s4_8_determinism_in_process_across_processes_hash_seeds_and_with_events_shuffled_within_a_day(self):
        def digest(runner, shuffled=False):
            out = []
            for p in FIXTURE["portfolios"]:
                for a in p["assertions"]:
                    for item in a["expect"]:
                        if item["kind"] in ("attribution_money", "attribution_return"):
                            events = None
                            if shuffled:
                                events = list(runner.events[p["name"]])
                                random.Random(7).shuffle(events)
                            out.append(runner.attribution(p, a, item["window"]["request"], events).canonical_json())
            return hashlib.sha256("\n".join(sorted(set(out))).encode("utf-8")).hexdigest()

        first = digest(self.runner)
        runner2, market2 = p4.build_runner(cp1.Ids(randomize=False), verify_identities=True)
        self.addCleanup(market2.close)
        self.assertEqual(digest(runner2), first)
        self.assertEqual(digest(runner2, shuffled=True), first)  # ledger_seq unchanged, list order shuffled
        digests = set()
        for seed in ("1", "2", "random"):
            proc = subprocess.run([sys.executable, str(Path(__file__)), "digest"], capture_output=True, text=True, timeout=900, env=dict(os.environ, PYTHONHASHSEED=seed))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            digests.add(proc.stdout.strip())
        self.assertEqual(digests, {first})

    def test_window_results_are_unchanged_by_the_new_entry(self):
        """The attribution entry shares nothing mutable with the window entry: the window result of a portfolio is byte-identical before and after an attribution call."""
        p = self.portfolio("P12")
        a = self.assertion(p, "P12-A1")
        before = self.runner.window(p, a, {"rule": "SINCE_INCEPTION"}).canonical_json()
        runner2, market2 = p4.build_runner(cp1.Ids(randomize=False), verify_identities=True)
        self.addCleanup(market2.close)
        runner2.attribution(p, a, {"rule": "SINCE_INCEPTION"})
        self.assertEqual(runner2.window(p, a, {"rule": "SINCE_INCEPTION"}).canonical_json(), before)


# ---- opt-in database layer ------------------------------------------------------------------------------------------------------

_SKIP = pk.skip_reason()


@unittest.skipIf(bool(_SKIP), _SKIP)
class DatabaseGoldenTests(unittest.TestCase):
    """The same ledgers through the real store as `finweb_app` and the market data through the PostgreSQL market-data store; every item is compared through the DATABASE path."""

    @classmethod
    def setUpClass(cls):
        from persistence import ledger_replay_store, ledger_store, market_data_store as mds  # noqa: PLC0415
        import test_cp3_golden_part1 as t1  # noqa: PLC0415

        cls.rs, cls.mds = ledger_replay_store, mds
        cls.db = pk.PgSchema().open()
        cls.addClassCleanup(cls.db.close)
        cls.ids = cp1.Ids(randomize=True)
        cls.market = p4.build_market(cls.ids)
        cls.addClassCleanup(cls.market.close)
        assert cls.market.issues == ((), ())
        pk.insert_identity(cls.db.owner, cls.market.ident)
        mds.write_release(cls.db.owner, cls.market.release, cls.market.manifests, cls.market.store.export(), cls.market.built.calendars)
        user = uuid.uuid4()
        cls.db.owner.execute("INSERT INTO app_user VALUES (%s)", (user,))
        cls.app = cls.db.app_connection()
        cls.addClassCleanup(cls.app.close)
        cls.seq_map, cls.stored = {}, {}
        for p in FIXTURE["portfolios"]:
            source = p4.source_of(p)
            pid = cls.ids(p["portfolio_id"])
            cls.db.owner.execute("INSERT INTO portfolio VALUES (%s, %s, %s)", (pid, user, p["reporting_currency"]))
            for account in source["accounts"]:
                cls.db.owner.execute("INSERT INTO account VALUES (%s, %s, %s)", (cls.ids(account["account_id"]), pid, account["name"]))
            built = cp1.build_events(source, cls.ids)
            cls.seq_map[p["name"]] = t1._append_portfolio(cls.app, ledger_store, built)
            version = ledger_replay_store.current_ledger_version(cls.app, pid)
            cls.stored[p["name"]] = list(ledger_replay_store.load_events(cls.app, pid, version))
        import marketdata_cp2c1_kit as kit_  # noqa: PLC0415

        cls.pg = mds.read_release(cls.app, cls.market.release.release_id, exchange_of=cls.market.ident.exchange_mic, registry=kit_.registry_for(cls.market.store))
        shim = SimpleNamespace(store=cls.pg, ident=cls.market.ident, conventions=market11_conventions(cls.pg.calendars()))
        cls.runner = p4.Runner(shim, cls.ids, cls.stored, verify_identities=True, seq_map=cls.seq_map)

    def test_every_item_of_every_assertion_matches_the_fixture_through_the_database_as_finweb_app(self):
        self.assertEqual(self.app.execute("SELECT current_user").fetchone()[0], self.db.app_role)
        checked, found_all = 0, []
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                found_all += p4.check_assertion(self.runner, p, a)
                checked += len(a["expect"])
        self.assertEqual(checked, 28)
        self.assertEqual([m for m in found_all if (m.assertion_id, m.field) not in KNOWN_FINDINGS], [], "\n" + describe(found_all))
        self.assertEqual({(m.assertion_id, m.field) for m in found_all} & KNOWN_FINDINGS, KNOWN_FINDINGS)

    def test_the_ledger_is_unchanged_by_an_attribution(self):
        p = next(x for x in FIXTURE["portfolios"] if x["name"].split()[0] == "P12")
        pid = self.ids(p["portfolio_id"])
        before = self.rs.current_ledger_version(self.app, pid)
        for a in p["assertions"]:
            p4.check_assertion(self.runner, p, a)
        self.assertEqual(self.rs.current_ledger_version(self.app, pid), before)

    def test_the_database_and_the_pure_paths_give_the_same_attribution(self):
        pure, market = p4.build_runner(cp1.Ids(randomize=False), verify_identities=False)
        self.addCleanup(market.close)
        p = next(x for x in FIXTURE["portfolios"] if x["name"].split()[0] == "P21")
        a = p["assertions"][0]
        # the database run uses randomized ids, so a breakdown part's NAME (which carries an id) is compared by its numbers, in name order of the same sorted ids' images: values only
        key = lambda res: sorted((m.metric_id, m.view, m.subject, m.result.value, m.exact, m.result.sufficiency_state.value,  # noqa: E731
                                  tuple(sorted((s, e) for _n, s, e in m.breakdown)) if m.metric_id == "attribution_breakdown" else m.breakdown) for m in res.metrics)
        self.assertEqual(key(pure.attribution(p, a, {"rule": "SINCE_INCEPTION"})), key(self.runner.attribution(p, a, {"rule": "SINCE_INCEPTION"})))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "digest":
        runner, market = p4.build_runner(cp1.Ids(randomize=False), verify_identities=True)
        out = []
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                for item in a["expect"]:
                    if item["kind"] in ("attribution_money", "attribution_return"):
                        out.append(runner.attribution(p, a, item["window"]["request"]).canonical_json())
        print(hashlib.sha256("\n".join(sorted(set(out))).encode("utf-8")).hexdigest())
        market.close()
    else:
        unittest.main()
