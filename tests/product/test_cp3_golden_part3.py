"""CP3 golden fixture, part 3 (`methodology/fixtures/cp3_golden/cp3_golden_part3.json`, `cp3_golden/1.2-part3`; `performance/1.6` and later, `ledger-replay/1.5` FIFO/1, `market-data/1.10`):
FIFO lots and relief records, realized and unrealized gain, remaining basis, the since-acquisition split, the gain aggregates, a carried split taint ended by FIFO relief, and recorded
acquisition dates (`acquired_on`). 167 items.

The fixture is never edited here and no expected value is derived here: a mismatch is reported (assertion id, expected, actual) and neither side is changed.

Layers: 1. SHAPE and PINS; 2. the expansion of the additions into real CP2 layouts adds no number; 3. PURE: every item compared; 4. STRUCTURAL assertions S3-1 to S3-7; 5. DATABASE
(opt-in): the same ledgers through the real store as `finweb_app` and the market data through the PostgreSQL market-data store.
"""

import copy
import datetime
import hashlib
import json
import os
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
import pg_market_kit as pk  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402

from domain.replay import SequencedEvent, reconstruct, reconstruct_fifo  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402

FIXTURE = p3.FIXTURE
D = datetime.date.fromisoformat

# A tripwire against a silently trimmed or edited fixture (as parts 1 and 2). It changes only with a new `fixture_id`. Counts come from the fixture FILE; the hash is over the
# assertions (id, as_of, ledger_version, expect).
FIXTURE_PINS = {
    "cp3_golden/1.2-part3": {
        "expect_counts": {
            "P1-L1": 6, "P1-L2": 5, "P1-L3": 3, "P1-G1": 13, "P1-G2": 3, "P1-S1": 2, "P1-N1": 2, "P2-L1": 7, "P3-L1": 3, "P3-L2": 3, "P3-L3": 3, "P3-L4": 3, "P3-G1": 6,
            "P14-L1": 5, "P14-L2": 2, "P14-G1": 4, "P15-L1": 5, "P15-L2": 2, "P15-G1": 4, "P16-L1": 5, "P16-L2": 2, "P16-L3": 5, "P16-L4": 2, "P16-G1": 7, "P17-S1": 1,
            "P17-V1": 4, "P17-L1": 4, "P17-V2": 5, "P18-L1": 2, "P18-L2": 3, "P18-G1": 8, "P19-L1": 1, "P19-L2": 1, "P19-L3": 5, "P19-L4": 5, "P20-V1": 1, "P20-L1": 2,
            "P20-L2": 2, "P20-L3": 3, "P20-L4": 3, "P20-L5": 3, "P20-G1": 12,
        },
        "expect_total": 167,
        "assertions": 42,
        "content_sha256": "3140a1bf7239729ab1f3cf3447239594f89e31c5d083364b2a87ba91e051d6ed",
    },
}
NEW_KINDS = {"lot_book", "relief", "replay_basis", "realized_gain", "unrealized_gain", "remaining_basis", "since_acquisition", "realized_gain_total", "unrealized_gain_total",
             "split_outcome"}


def describe(found):
    return "\n".join(str(m) for m in found)


class _Shared(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = cp1.Ids(randomize=False)
        cls.runner, cls.market = p3.build_runner(cls.ids, verify_identities=True)
        cls.addClassCleanup(cls.market.close)

    def portfolio(self, prefix):
        return next(p for p in FIXTURE["portfolios"] if p["name"].split()[0] == prefix.strip())

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
        self.assertEqual(p3.content_hash(), pins["content_sha256"])
        self.assertEqual(FIXTURE["part"], 3)
        self.assertEqual(FIXTURE["extends"]["fixture_ids"], [g.FIXTURE["fixture_id"], p2.FIXTURE["fixture_id"]])  # the relabelled parts 1 and 2 the loader reads
        sets = FIXTURE["convention_sets"]  # minimum versions (PM ruling OI-P11)
        self.assertEqual((sets["performance"], sets["market_data"], sets["lot_relief"]), ("performance/1.6", "market-data/1.10", "FIFO/1"))
        self.assertTrue(sets["ledger_replay"].startswith("ledger-replay/1.5 (FIFO/1 mode)"))

    def test_the_fixture_exercises_every_new_kind_and_cannot_pass_vacuously(self):
        kinds = {i["kind"] for _p, _a, i in p3.items()}
        self.assertTrue(NEW_KINDS <= kinds, NEW_KINDS - kinds)
        states = {i["state"] for _p, _a, i in p3.items() if "state" in i}
        self.assertEqual(states, {"AVAILABLE", "LIMITED", "INSUFFICIENT_DATA"})
        self.assertTrue(any(i.get("excluded_weight") for _p, _a, i in p3.items()))
        carried = [i for _p, _a, i in p3.items() if i["kind"] == "lot_book" and any(lot["carry"] for lot in i["lots"])]
        self.assertTrue(carried)
        self.assertTrue(any(lot["date_kind"] == "RECORDED" for _p, _a, i in p3.items() if i["kind"] == "lot_book" for lot in i["lots"]))
        events = [e["event"] for p in FIXTURE["portfolios"] for e in p.get("events", [])]
        self.assertEqual(len([e for e in events if e.get("acquired_on")]), 4)  # P20: the only events that carry the PD-0036 field

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

        walk(json.loads(p3.PATH.read_text(encoding="utf-8")))


class MarketExpansionTests(_Shared):
    def test_the_expansion_ingests_through_the_real_adapters_with_no_issue(self):
        self.assertEqual(self.market.issues, ((), ()))
        md, two, three = g.FIXTURE["market_data"], p2.FIXTURE["market_data_additions"], FIXTURE["market_data_additions"]
        expected = len(md["calendars"]) + 1 + len(md["prices"]["series"]) + len(two["prices"]["series"]) + len(three["prices"]["series"]) + 2 + 2  # two corporate-action pairs
        self.assertEqual(len(self.market.manifests), expected)
        self.assertTrue(self.market.store.contains_synthetic)
        self.assertTrue(all(m.usage_scope.value == "SYNTHETIC_TEST" for m in self.market.manifests))

    def test_the_new_series_and_the_new_split_are_exactly_the_fixtures_numbers(self):
        for s in FIXTURE["market_data_additions"]["prices"]["series"]:
            readings = self.market.store.quotes(self.ids(s["listing_id"]), D(s["first"]), D(s["last"])).readings
            self.assertTrue(readings, s["ticker"])
            for r in readings:
                day = r.observation.value_date
                step = [x for x in s["steps"] if D(x["from"]) <= day][-1]
                self.assertEqual(r.observation.price, Decimal(step["close"]), (s["ticker"], day))
        (action,) = FIXTURE["market_data_additions"]["corporate_actions"]
        actions = self.market.store.corporate_actions(self.ids(action["listing_id"]), datetime.date.min, datetime.date.max)
        readings = list(actions.readings)
        self.assertEqual(sorted(r.source_id for r in readings), [g.CA_FEED, g.CA_FILING])
        for r in readings:
            o = r.observation
            self.assertEqual((o.effective_date.isoformat(), o.split_ratio.new_units, o.split_ratio.old_units, o.lineage.is_synthetic),
                             (action["ex_date"], Decimal(action["ratio"]["new_units"]), Decimal(action["ratio"]["old_units"]), True))

    def test_p3_is_part_1s_events_plus_the_added_ones_and_p20_carries_acquired_on(self):
        events = self.runner.events[self.portfolio("P3")["name"]]
        self.assertEqual([e.ledger_seq for e in events], list(range(1, 14)))
        p20 = self.runner.events[self.portfolio("P20")["name"]]
        self.assertEqual(sorted(str(e.event.acquired_on) for e in p20 if e.event.acquired_on is not None),
                         ["2024-11-01", "2024-12-16", "2025-01-04", "2025-01-08"])


class PureGoldenTests(_Shared):
    def test_every_item_of_every_assertion_matches_the_fixture(self):
        checked = 0
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                with self.subTest(assertion=a["id"]):
                    found = p3.check_assertion(self.runner, p, a)
                    checked += len(a["expect"])
                    self.assertEqual(found, [], "\n" + describe(found))
        self.assertEqual(checked, 167)

    def test_the_checker_really_fails_on_a_wrong_expectation(self):
        def broken(portfolio_prefix, assertion_id, kind, mutate, expected_field=None):
            p = self.portfolio(portfolio_prefix)
            a = copy.deepcopy(self.assertion(p, assertion_id))
            item = next(i for i in a["expect"] if i["kind"] == kind and (expected_field is None or expected_field(i)))
            mutate(item)
            found = p3.check_assertion(self.runner, p, a)
            self.assertTrue([m for m in found if m.kind == kind], (assertion_id, kind))

        broken("P1 ", "P1-L1", "lot_book", lambda i: i["lots"][0].update(units="149"))
        broken("P1 ", "P1-L1", "relief", lambda i: i["portions"][0].update(basis="1876"))
        broken("P1 ", "P1-L1", "relief", lambda i: i["portions"][0].update(date_kind="ENTRY"))
        broken("P1 ", "P1-L2", "lot_book", lambda i: i["lots"][0]["carry"][0].update(out_event_id="e0000000-0000-4000-8000-000000000999"), lambda i: i["lots"])
        broken("P1 ", "P1-L1", "realized_gain", lambda i: i.update(value="375.01"), lambda i: i["view"] == "REPORTING")
        broken("P1 ", "P1-L1", "remaining_basis", lambda i: i.update(exact="5624"))
        broken("P1 ", "P1-G1", "remaining_basis", lambda i: i["value"][0].update(currency="USD"), lambda i: isinstance(i["value"], list))
        broken("P1 ", "P1-G2", "unrealized_gain_total", lambda i: i["excluded_weight"].update(exact="1/2"))
        broken("P1 ", "P1-S1", "since_acquisition", lambda i: i["parts"][0].update(apportioned="128.20"))
        broken("P1 ", "P1-S1", "since_acquisition", lambda i: i.update(state="INSUFFICIENT_DATA"))
        broken("P1 ", "P1-N1", "replay_basis", lambda i: i.update(state="AVAILABLE"), lambda i: i["mode"] == "NONE")
        broken("P17", "P17-S1", "split_outcome", lambda i: i.update(append="WOULD_APPEND"))

    def test_a_missing_item_is_reported_not_skipped(self):
        p = self.portfolio("P1 ")
        a = copy.deepcopy(self.assertion(p, "P1-L1"))
        a["expect"] = [dict(a["expect"][0], listing_id="c0000000-0000-4000-8000-0000000000ff")]
        self.assertTrue(p3.check_assertion(self.runner, p, a))


class StructuralAssertionTests(_Shared):
    def all_results(self):
        out = []
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                for item in a["expect"]:
                    if item["kind"] in p3.GAIN_KINDS:
                        out.append((p, a, item, self.runner.gains(p, a, item["window"]["request"] if "window" in item else None)))
                    elif item["kind"] in ("holding_value", "portfolio_value"):
                        out.append((p, a, item, self.runner.valuation(p, a)))
        return out

    def test_s3_1_every_result_is_synthetic_and_every_manifest_cites_the_fixtures_ids_or_later(self):
        rs = self.all_results()
        self.assertGreater(len(rs), 100)
        for p, a, _i, res in rs:
            self.assertTrue(res.manifest.synthetic)
            conv = dict(res.manifest.conventions)
            self.assertEqual(g.convention_problems(conv, FIXTURE["convention_sets"]), [], a["id"])  # the same family at the fixture's version or LATER (PM ruling OI-P11)
            self.assertEqual(conv["performance.lot_method"], "FIFO/1")
            for m in res.metrics:
                self.assertTrue(m.synthetic)
        # the FIFO-mode state cites ledger-replay/1.5 and FIFO/1; the replay_basis NONE items are ledger-replay/1.3 outputs
        p1 = self.portfolio("P1 ")
        a = self.assertion(p1, "P1-N1")
        self.assertEqual((self.runner.fifo(p1, a).state.convention_set, self.runner.fifo(p1, a).lot_method, self.runner.none(p1, a).convention_set),
                         ("ledger-replay/1.5", "FIFO/1", "ledger-replay/1.3"))

    def test_s3_2_identity_i5_lot_conservation_and_internal_pairs_deliver_exactly_the_relief(self):
        checked_pairs = 0
        for p in FIXTURE["portfolios"]:
            last = max(p["assertions"], key=lambda a: (a["as_of"], a["ledger_version"]))
            events = self.runner.events[p["name"]]
            fifo = reconstruct_fifo(events, D("2026-12-31"), max(e.ledger_seq for e in events))
            self.assertEqual(fifo.conservation_failures, (), p["name"])  # relieved + remaining = the candidate set at every relief
            by_id = {e.event.event_id: e.event for e in events}
            for relief in fifo.reliefs.values():
                if not relief.internal or relief.withheld:
                    continue
                out = by_id[relief.event_id]
                receiver = out.counterparty_account_id
                same_day_reliefs = [r for r in fifo.reliefs.values() if r.account_id == receiver and r.listing_id == relief.listing_id and r.event_date == relief.event_date]
                if same_day_reliefs:
                    continue  # the receiver depletes the same day: its end-of-day book no longer shows the delivered lot whole
                book = fifo.book_on(receiver, relief.listing_id, relief.event_date)
                self.assertIsNotNone(book, p["name"])
                have = {lot.identity: lot for lot in book.lots}
                for portion in relief.portions:
                    delivered = have[(portion.origin_event_id, tuple(h.out_event_id for h in portion.hops) + (relief.event_id,))]
                    self.assertEqual((delivered.units, delivered.unit_cost, delivered.basis_currency, delivered.acquisition_date, delivered.date_kind),
                                     (portion.units, portion.unit_cost, portion.basis_currency, portion.acquisition_date, portion.date_kind))
                    self.assertEqual(len(delivered.hops), len(portion.hops) + 1)  # exactly one hop appended
                checked_pairs += 1
        self.assertGreaterEqual(checked_pairs, 3)

    def test_s3_3_identity_i7_method_independence_rg_plus_ug_equals_proceeds_plus_mv_minus_costs(self):
        def totals(prefix, assertion_id, request=None, version=None):
            p = self.portfolio(prefix)
            a = copy.deepcopy(self.assertion(p, assertion_id))
            res = self.runner.gains(p, a, request)
            by = {m.metric_id: m for m in res.metrics if m.metric_id in ("realized_gain_total", "unrealized_gain_total")}
            return by["realized_gain_total"].exact, by["unrealized_gain_total"].exact

        # P14 and P15 at 03-31: 118 + 132 = 1,360 + 780 - 1,890 = 250 (the fixture's own S3-3 numbers)
        for prefix, aid in (("P14", "P14-G1"), ("P15", "P15-G1")):
            rg, ug = totals(prefix, aid)
            self.assertEqual((rg, ug, rg + ug), (Fraction(118), Fraction(132), Fraction(1360 + 780 - 1890)))
        # P16 at portfolio level: 1,544/3 + 436/3 = 660 = (1,440 + 520 + 780) + 80 x 13 - 3,120
        rg, ug = totals("P16", "P16-G1")
        self.assertEqual((rg, ug, rg + ug), (Fraction(1544, 3), Fraction(436, 3), Fraction(1440 + 520 + 780 + 80 * 13 - 3120)))
        # P19 under both ledger versions: 300 + 200 = 1,200 + 1,300 - 2,000 and 100 + 180 = 1,200 + 1,300 - 2,220
        for aid, want in (("P19-L3", (300, 200, 1200 + 1300 - 2000)), ("P19-L4", (100, 180, 1200 + 1300 - 2220))):
            rg, ug = totals("P19", aid)
            self.assertEqual((rg, ug, rg + ug), (Fraction(want[0]), Fraction(want[1]), Fraction(want[2])), aid)
        # P1 A3 MSFT at 06-30: realized 120 (X11) + unrealized 80 = 1,720 + 2,580 - 4,100
        p1 = self.portfolio("P1 ")
        res = self.runner.gains(p1, self.assertion(p1, "P1-G1"), None)
        msft = "c0000000-0000-4000-8000-00000000f001"
        a3 = "a1000000-0000-4000-8000-000000000003"
        ug = [m for m in res.metrics if m.metric_id == "unrealized_gain" and m.view == "REPORTING" and dict(m.subject).get("account") == str(self.ids(a3))
              and dict(m.subject).get("listing") == str(self.ids(msft))]
        sale = [m for m in res.metrics if m.metric_id == "realized_gain" and m.view == "REPORTING" and dict(m.lineage).get("account") == str(self.ids(a3))
                and dict(m.lineage).get("listing") == str(self.ids(msft))]
        self.assertEqual((sale[0].exact, ug[0].exact, sale[0].exact + ug[0].exact), (Fraction(120), Fraction(80), Fraction(1720 + 2580 - 4100)))

    def test_s3_4_identity_i8_the_since_acquisition_parts_sum_to_the_total_exactly_and_the_apportioned_ones_to_its_presented_value(self):
        seen = 0
        for p, a, item, res in self.all_results():
            if item["kind"] != "since_acquisition" or item["state"] != "AVAILABLE":
                continue
            lot_text = str(self.ids(item["lot"]["origin_event_id"])) + "".join(f":{self.ids(x)}" for x in item["lot"]["carry_out_event_ids"])
            m = next(x for x in res.metrics if x.metric_id == "since_acquisition" and dict(x.subject).get("lot") == lot_text)
            self.assertEqual(sum((exact for _n, _s, exact in m.breakdown), Fraction(0)), m.exact, a["id"])
            self.assertEqual(sum((shown for _n, shown, _e in m.breakdown), Decimal(0)), m.result.value, a["id"])
            self.assertEqual(dict(m.lineage)["identity:I-8"], "PASS")
            seen += 1
        self.assertGreaterEqual(seen, 5)

    def test_s3_5_entry_order_independence_p14_against_p15_and_ledger_seq_permuted_within_every_day(self):
        p14, p15 = self.portfolio("P14"), self.portfolio("P15")
        for a14, a15 in zip(p14["assertions"], p15["assertions"]):
            for i14, i15 in zip(a14["expect"], a15["expect"]):
                keep = lambda i: {k: v for k, v in i.items() if k not in ("event_id", "account_id", "listing_id", "origin_event_id", "portions", "lots")}  # noqa: E731
                self.assertEqual(keep(i14), keep(i15), (a14["id"], i14["kind"]))  # every expected value is identical; only event ids differ
            r14, r15 = self.runner.gains(p14, a14), self.runner.gains(p15, a15)
            key = lambda res: sorted((m.metric_id, m.view, m.exact, m.result.sufficiency_state.value) for m in res.metrics)  # noqa: E731
            self.assertEqual(key(r14), key(r15), a14["id"])
        # permuting ledger_seq within any day of any part-3 portfolio changes no output byte, carry histories included
        for p in FIXTURE["portfolios"]:
            events = self.runner.events[p["name"]]
            if any(e.event.event_type.value == "REVERSAL" for e in events):
                continue  # a reversal's position in ledger_seq is its meaning (P1, P19: tested at their own L above)
            by_day = {}
            for e in events:
                by_day.setdefault(e.event.event_date, []).append(e)
            permuted = []
            for day, group in by_day.items():
                seqs = sorted(e.ledger_seq for e in group)
                permuted += [SequencedEvent(s, e.event) for s, e in zip(seqs, reversed(sorted(group, key=lambda x: x.ledger_seq)))]
            version = max(e.ledger_seq for e in events)
            base = reconstruct_fifo(events, D("2026-12-31"), version).canonical_json()
            self.assertEqual(reconstruct_fifo(permuted, D("2026-12-31"), version).canonical_json(), base, p["name"])

    def test_s3_6_mode_consistency_quantities_cash_and_flags_are_identical_and_determinate_none_values_agree(self):
        agreed = 0
        for p in FIXTURE["portfolios"]:
            events = self.runner.events[p["name"]]
            version = max(e.ledger_seq for e in events)
            for day in sorted({D(a["as_of"]) for a in p["assertions"]} | {D("2025-12-31")}):
                none = reconstruct(events, day, version)
                fifo = reconstruct_fifo(events, day, version).state
                for an, af in zip(none.accounts, fifo.accounts):
                    self.assertEqual((an.account_id, an.status, an.cash), (af.account_id, af.status, af.cash), (p["name"], day))
                    self.assertEqual([(x.listing_id, x.quantity, x.quantity_detail) for x in an.positions], [(x.listing_id, x.quantity, x.quantity_detail) for x in af.positions])
                    for xn, xf in zip(an.positions, af.positions):
                        if all(b.result.value is not None for b in xn.cost_basis):  # wherever `none` emits a determinate basis, FIFO emits the same value
                            self.assertEqual(xn.cost_basis, xf.cost_basis, (p["name"], day))
                            agreed += 1
        self.assertGreater(agreed, 10)

    def test_s3_7_determinism_in_process_and_across_processes_and_hash_seeds(self):
        def digest(runner):
            out = []
            for p in FIXTURE["portfolios"]:
                for a in p["assertions"]:
                    out.append(runner.fifo(p, a).canonical_json())
                    for item in a["expect"]:
                        if item["kind"] in p3.GAIN_KINDS:
                            out.append(runner.gains(p, a, item["window"]["request"] if "window" in item else None).canonical_json())
            return hashlib.sha256("\n".join(sorted(set(out))).encode("utf-8")).hexdigest()

        first = digest(self.runner)
        runner2, market2 = p3.build_runner(cp1.Ids(randomize=False), verify_identities=True)
        self.addCleanup(market2.close)
        self.assertEqual(digest(runner2), first)
        digests = set()
        for seed in ("1", "2", "random"):
            proc = subprocess.run([sys.executable, str(Path(__file__)), "digest"], capture_output=True, text=True, timeout=900, env=dict(os.environ, PYTHONHASHSEED=seed))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            digests.add(proc.stdout.strip())
        self.assertEqual(digests, {first})

    def test_the_broker_difference_label_and_the_as_recorded_label_are_on_the_figures(self):
        p20 = self.portfolio("P20")
        res = self.runner.gains(p20, self.assertion(p20, "P20-G1"), None)
        gains = [m for m in res.metrics if m.metric_id in ("realized_gain", "unrealized_gain", "remaining_basis", "since_acquisition")]
        self.assertTrue(gains)
        for m in gains:
            self.assertIn("caveat.lot_method", dict(m.lineage), (m.metric_id, m.view))
        recorded = [m for m in gains if "caveat.recorded" in dict(m.lineage)]
        self.assertTrue(recorded)  # a figure built on a RECORDED lot says "as recorded by you"
        self.assertEqual({dict(m.lineage)["caveat.recorded"] for m in recorded}, {"cost and acquisition date as recorded by you"})
        p1 = self.portfolio("P1 ")
        plain = self.runner.gains(p1, self.assertion(p1, "P1-L1"), None)
        self.assertFalse([m for m in plain.metrics if "caveat.recorded" in dict(m.lineage)])  # no RECORDED lot, no such label


# ---- opt-in database layer ------------------------------------------------------------------------------------------------------

_SKIP = pk.skip_reason()


@unittest.skipIf(bool(_SKIP), _SKIP)
class DatabaseGoldenTests(unittest.TestCase):
    """The same ledgers through the real store as `finweb_app` (P20 carries `acquired_on` through migration 0014) and the market data through the PostgreSQL market-data store; every
    item is compared through the DATABASE path."""

    @classmethod
    def setUpClass(cls):
        from persistence import ledger_replay_store, ledger_store, market_data_store as mds  # noqa: PLC0415
        import test_cp3_golden_part1 as t1  # noqa: PLC0415

        cls.rs, cls.mds = ledger_replay_store, mds
        cls.db = pk.PgSchema().open()
        cls.addClassCleanup(cls.db.close)
        cls.ids = cp1.Ids(randomize=True)
        cls.market = p3.build_market(cls.ids)
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
            source = p3.source_of(p)
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
        cls.runner = p3.Runner(shim, cls.ids, cls.stored, verify_identities=True, seq_map=cls.seq_map)

    def test_every_item_of_every_assertion_matches_the_fixture_through_the_database_as_finweb_app(self):
        self.assertEqual(self.app.execute("SELECT current_user").fetchone()[0], self.db.app_role)
        checked = 0
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                with self.subTest(assertion=a["id"]):
                    found = p3.check_assertion(self.runner, p, a)
                    checked += len(a["expect"])
                    self.assertEqual(found, [], "\n" + describe(found))
        self.assertEqual(checked, 167)

    def test_acquired_on_round_trips_through_the_store_and_the_ledger_is_unchanged_by_a_computation(self):
        p20 = next(p for p in FIXTURE["portfolios"] if p["name"].startswith("P20"))
        stored = self.stored[p20["name"]]
        self.assertEqual(sorted(str(e.event.acquired_on) for e in stored if e.event.acquired_on is not None), ["2024-11-01", "2024-12-16", "2025-01-04", "2025-01-08"])
        pid = self.ids(p20["portfolio_id"])
        before = self.rs.current_ledger_version(self.app, pid)
        for a in p20["assertions"]:
            p3.check_assertion(self.runner, p20, a)
        self.assertEqual(self.rs.current_ledger_version(self.app, pid), before)

    def test_the_database_and_the_pure_paths_give_the_same_gains(self):
        pure, market = p3.build_runner(cp1.Ids(randomize=False), verify_identities=False)
        self.addCleanup(market.close)
        p = next(x for x in FIXTURE["portfolios"] if x["name"].startswith("P16"))
        a = next(x for x in p["assertions"] if x["id"] == "P16-G1")
        key = lambda res: sorted((m.metric_id, m.view, m.result.value, m.exact, m.result.sufficiency_state.value) for m in res.metrics)  # noqa: E731
        self.assertEqual(key(pure.gains(p, a)), key(self.runner.gains(p, a)))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "digest":
        runner, market = p3.build_runner(cp1.Ids(randomize=False), verify_identities=True)
        out = []
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                out.append(runner.fifo(p, a).canonical_json())
                for item in a["expect"]:
                    if item["kind"] in p3.GAIN_KINDS:
                        out.append(runner.gains(p, a, item["window"]["request"] if "window" in item else None).canonical_json())
        print(hashlib.sha256("\n".join(sorted(set(out))).encode("utf-8")).hexdigest())
        market.close()
    else:
        unittest.main()
