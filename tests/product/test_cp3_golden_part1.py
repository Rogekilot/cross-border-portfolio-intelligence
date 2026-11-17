"""CP3 golden fixture, part 1 (`methodology/fixtures/cp3_golden/cp3_golden_part1.json`, `cp3_golden/1.2-part1`, convention sets `performance/1.3`, `ledger-replay/1.3`,
`market-data/1.9`): valuation, absolute gain, TWR and annualized TWR over six portfolios.

This file NEVER edits the fixture and never derives an expected value. If the engine disagrees with the fixture the test fails and names the assertion, the expected
value and the actual value; neither side is adjusted here (the Quant and the engineer decide, separately).

Layers:
1. SHAPE and PINS (always): the fixture is what it was ratified as (item counts, content hash), holds no float, and cannot pass vacuously.
2. PURE (always): the compact market-data block is EXPANDED into real CP2 file layouts and ingested through the real adapters; the engine runs at every assertion's
   (D, L) or window and every `expect` item is compared (state, reason, details, presented value, exact rational, window, lineage, stale share, partial list). Window
   assertions run with the runtime identities I-2 and I-3 on.
3. STRUCTURAL assertions S-1 to S-6 of the fixture.
4. DATABASE (opt-in, `FINWEB_PG_*` like the other database tests): the same ledger through the real store as `finweb_app` and the same market data through the
   PostgreSQL market-data store.
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
import pg_market_kit as pk  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from domain.replay import SequencedEvent  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from performance.engine import compute_window  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = g.FIXTURE

# A tripwire against a silently trimmed or edited fixture (as FIXTURE_PINS in the CP1 test). It changes only with a new `fixture_id` (the Quant bumps it). The counts and the hash are
# taken from the fixture FILE, never from engine output.
FIXTURE_PINS = {
    "cp3_golden/1.4-part1": {
        "expect_counts": {
            "P1-V1": 1, "P1-V2": 4, "P1-V3": 3, "P1-V4": 2, "P1-V5": 3, "P1-V6": 2, "P1-V7": 4, "P1-V8": 2, "P1-V9": 1, "P1-V10": 1,
            "P1-R1": 2, "P1-R2": 3, "P1-R3": 2, "P1-R4": 3, "P1-R5": 3, "P2-V1": 1, "P2-V2": 2, "P2-V3": 1, "P2-R1": 4, "P2-R2": 2,
            "P3-V1": 3, "P3-V2": 2, "P3-V3": 3, "P3-V4": 5, "P3-V5": 4, "P3-V6": 5, "P3-R1": 2, "P3-R2": 1, "P3-R3": 2, "P3-R4": 1,
            "P4-V1": 1, "P4-V2": 2, "P4-R1": 2, "P4-R2": 1, "P5-V1": 1, "P5-R1": 2, "P6-V1": 4, "P6-V2": 4, "P6-R1": 2,
        },
        "expect_total": 93,
        "assertions": 39,
        "content_sha256": "14b5d7b7e904f1b0af50bbd587f8ad9d161c6a4febaa328c1d344f6916ade0de",  # the hash of the ASSERTIONS (id, as_of, ledger_version, expect): identical to 1.0 and 1.1, because 1.2-part1 changed no expected value
    },
}
WINDOW_ASSERTIONS_WITH_I2 = ("P1-R1", "P1-R2", "P2-R1", "P3-R1", "P4-R2", "P6-R1")  # structural assertion S-2 names these


def describe(found):
    return "\n".join(str(m) for m in found)


class _Shared(unittest.TestCase):
    """The expanded market data and a runner with the runtime identities on, built once per class."""

    @classmethod
    def setUpClass(cls):
        cls.ids = cp1.Ids(randomize=False)
        cls.runner, cls.market = g.build_runner(cls.ids, verify_identities=True)
        cls.addClassCleanup(cls.market.close)


class FixtureShapeTests(unittest.TestCase):
    def test_the_fixture_is_the_ratified_one_and_pinned(self):
        pins = FIXTURE_PINS[FIXTURE["fixture_id"]]
        counts = {a["id"]: len(a["expect"]) for p in FIXTURE["portfolios"] for a in p["assertions"]}
        self.assertEqual(counts, pins["expect_counts"])
        self.assertEqual((sum(counts.values()), len(counts)), (pins["expect_total"], pins["assertions"]))
        self.assertEqual({k: v for k, v in FIXTURE["item_counts"].items() if k not in ("note", "total")}, counts)  # the fixture's own list agrees
        self.assertEqual(FIXTURE["item_counts"]["total"], pins["expect_total"])
        self.assertEqual(g.content_hash(), pins["content_sha256"])
        # the fixture's convention sets are MINIMUM versions (PM ruling OI-P11): this is the file as relabelled in 1.4-part1; a manifest may cite the same family later
        self.assertEqual(FIXTURE["convention_sets"]["performance"], "performance/1.6")
        self.assertEqual(FIXTURE["convention_sets"]["market_data"], "market-data/1.10")
        self.assertEqual(FIXTURE["convention_sets"]["ledger_replay"].split(" ")[0], "ledger-replay/1.5")

    def test_the_minimum_version_comparison_is_by_dotted_integers_in_the_same_family(self):
        self.assertTrue(g.cites_at_least("market-data/1.10", "market-data/1.9"))  # 1.10 is later than 1.9: not a string comparison
        self.assertFalse(g.cites_at_least("market-data/1.9", "market-data/1.10"))
        self.assertTrue(g.cites_at_least("performance/1.8", "performance/1.6"))
        self.assertTrue(g.cites_at_least("performance/1.6", "performance/1.6"))
        self.assertFalse(g.cites_at_least("performance/1.5", "performance/1.6"))
        self.assertFalse(g.cites_at_least("ledger-replay/1.5", "performance/1.5"))  # another family never satisfies
        self.assertTrue(g.cites_at_least("ledger-replay/1.5", "ledger-replay/1.5 (FIFO/1 mode)"))
        self.assertEqual(g.convention_problems({"performance.convention_set": "performance/1.5", "ledger_replay": "ledger-replay/1.5", "market_data.convention_set": "market-data/1.10"},
                                               FIXTURE["convention_sets"]), ["performance.convention_set: cites 'performance/1.5', the fixture needs 'performance/1.6' or later"])

    def test_no_value_in_the_fixture_is_a_float_and_every_item_names_its_fields(self):
        def walk(node):
            if isinstance(node, float):
                self.fail("a float in the fixture")
            elif isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(FIXTURE)
        for _p, a, item in g.items():
            if item["kind"] == "priced_holdings_value" and item.get("emitted") is False:
                continue
            for key in ("state", "value", "exact", "reason", "detail"):
                self.assertIn(key, item, (a["id"], item["kind"]))
            self.assertEqual(item["value"] is None, item["state"] == "INSUFFICIENT_DATA", (a["id"], item["kind"]))  # `value` is null iff INSUFFICIENT_DATA

    def test_every_kind_the_fixture_uses_is_one_the_checker_knows(self):
        kinds = {item["kind"] for _p, _a, item in g.items()}
        self.assertEqual(kinds, {"portfolio_value", "twr", "holding_value", "cash_value", "gain_absolute", "priced_holdings_value", "annualized_twr"})
        self.assertEqual(sum(1 for _ in g.items()), 93)


class MarketExpansionTests(_Shared):
    def test_the_expansion_ingests_through_the_real_adapters_with_no_issue_and_covers_every_series(self):
        self.assertEqual(self.market.issues, ((), ()))  # no row refused, nothing quarantined, no exception
        md = FIXTURE["market_data"]
        # four calendars + one ECB file + one price file per series
        self.assertEqual(len(self.market.manifests), len(md["calendars"]) + 1 + len(md["prices"]["series"]))
        self.assertEqual(len(md["calendars"]), 4)
        listing_ids = {s["listing_id"] for s in md["prices"]["series"]}
        self.assertEqual(len(listing_ids), 5)
        # every priced listing has readings in M; the listing without a series has none (the P3 unpriced case)
        for lst in FIXTURE["listings"]:
            series = self.market.store.quotes(self.ids(lst["listing_id"]), datetime.date(2025, 1, 1), datetime.date(2026, 2, 1))
            has = lst["listing_id"] in listing_ids
            self.assertEqual(bool(series.readings), has, lst["ticker"])
        self.assertTrue(self.market.store.contains_synthetic)

    def test_the_synthetic_market_data_is_never_a_real_source(self):
        sources = {m.source_id for m in self.market.manifests}
        self.assertTrue(all(s.startswith("synthetic.") or s == "calendar.manual" for s in sources), sources)
        self.assertTrue(all(m.usage_scope.value == "SYNTHETIC_TEST" for m in self.market.manifests))


class PureGoldenTests(_Shared):
    def test_every_item_of_every_assertion_matches_the_fixture(self):
        checked = 0
        failures = []
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                with self.subTest(assertion=a["id"]):
                    found = g.check_assertion(self.runner, p, a)
                    checked += len(a["expect"])
                    self.assertEqual(found, [], "\n" + describe(found))
                    failures += found
        self.assertEqual(checked, 93)  # nothing skipped: the loop is not vacuous

    def test_the_checker_really_fails_on_a_wrong_expectation(self):
        """Each kind of perturbation of a real item must be reported; otherwise the checker could pass vacuously."""
        p = FIXTURE["portfolios"][0]
        base = next(a for a in p["assertions"] if a["id"] == "P1-V2")
        result = self.runner.valuation(p, base)
        item = next(i for i in base["expect"] if i["kind"] == "portfolio_value")
        self.assertEqual(g.check_item(result, p, base, item, self.ids), [])
        for field, wrong in (("value", "12564.11"), ("exact", "490001/39"), ("state", "LIMITED"), ("reason", "STALE_DATA"), ("detail", ["X"])):
            bad = copy.deepcopy(item)
            bad[field] = wrong
            found = g.check_item(result, p, base, bad, self.ids)
            self.assertTrue(found, field)
            self.assertIn(field, {m.field for m in found}, field)
        # a missing metric is reported, not skipped
        ghost = dict(item, view="NATIVE", currency="XXX")
        self.assertEqual([m.field for m in g.check_item(result, p, base, ghost, self.ids)], ["metric"])
        # window, lineage and partial-list fields
        r1 = next(a for a in p["assertions"] if a["id"] == "P1-R4")
        wres = self.runner.window(p, r1, r1["expect"][0]["window"]["request"])
        witem = copy.deepcopy(r1["expect"][0])
        witem["window"]["days"] = 366
        self.assertIn("window.days", {m.field for m in g.check_item(wres, p, r1, witem, self.ids)})
        p3 = FIXTURE["portfolios"][2]
        v5 = next(a for a in p3["assertions"] if a["id"] == "P3-V5")
        vres = self.runner.valuation(p3, v5)
        ph = copy.deepcopy(next(i for i in v5["expect"] if i["kind"] == "priced_holdings_value"))
        self.assertEqual(g.check_item(vres, p3, v5, ph, self.ids), [])
        ph["excluded_count"] = 2
        ph["excluded"][0]["native"] = "3001"
        self.assertTrue({"excluded_count", "excluded"} <= {m.field for m in g.check_item(vres, p3, v5, ph, self.ids)})
        # an `emitted: false` item fails when the metric IS emitted
        ph2 = {"kind": "priced_holdings_value", "emitted": False}
        self.assertEqual([m.field for m in g.check_item(vres, p3, v5, ph2, self.ids)], ["emitted"])
        # a stale share that is wrong
        p3v3 = next(a for a in p3["assertions"] if a["id"] == "P3-V3")
        res3 = self.runner.valuation(p3, p3v3)
        stale = copy.deepcopy(next(i for i in p3v3["expect"] if "stale_share" in i))
        stale["stale_share"]["exact"] = "1/2"
        self.assertIn("stale_share.exact", {m.field for m in g.check_item(res3, p3, p3v3, stale, self.ids)})

    def test_null_detail_is_not_asserted_and_an_explicit_list_is_asserted_exactly(self):
        p = FIXTURE["portfolios"][3]  # P4
        r1 = next(a for a in p["assertions"] if a["id"] == "P4-R1")
        res = self.runner.window(p, r1, r1["expect"][0]["window"]["request"])
        item = copy.deepcopy(r1["expect"][0])
        self.assertEqual(item["detail"], ["NON_POSITIVE_BASE"])
        self.assertEqual(g.check_item(res, p, r1, item, self.ids), [])
        item["detail"] = []  # asserted empty: must FAIL (an explicit [] is not "not asserted")
        self.assertIn("detail", {m.field for m in g.check_item(res, p, r1, item, self.ids)})
        item["detail"] = None  # not asserted: passes whatever the engine carries
        self.assertEqual(g.check_item(res, p, r1, item, self.ids), [])

    def test_the_tolerance_is_used_only_where_the_fixture_gives_one(self):
        with_tol = [(a["id"], i["kind"]) for _p, a, i in g.items() if i.get("tolerance") not in (None, "0")]
        self.assertEqual(with_tol, [("P1-R5", "annualized_twr")])  # the one transcendental output
        p = FIXTURE["portfolios"][0]
        a = next(x for x in p["assertions"] if x["id"] == "P1-R5")
        item = copy.deepcopy(next(i for i in a["expect"] if i["kind"] == "annualized_twr"))
        res = self.runner.window(p, a, item["window"]["request"])
        self.assertEqual(g.check_item(res, p, a, item, self.ids), [])
        item["value"] = str(Decimal(item["value"]) + Decimal("1e-9"))  # beyond the 1e-10 tolerance
        self.assertIn("value (tolerance 1E-10)", {m.field for m in g.check_item(res, p, a, item, self.ids)})
        item["tolerance"] = None  # without a tolerance an exact comparison of the presented value would apply
        item["value"] = str(Decimal(item["value"]) + Decimal("1e-12"))
        self.assertTrue(g.check_item(res, p, a, item, self.ids))


class StructuralAssertionTests(_Shared):
    def all_results(self):
        out = []
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                for item in a["expect"]:
                    out.append(self.runner.window(p, a, item["window"]["request"]) if "window" in item else self.runner.valuation(p, a))
        return out

    def test_s1_every_result_is_synthetic_and_every_manifest_cites_the_three_convention_sets(self):
        results = self.all_results()
        self.assertGreater(len(results), 50)
        for res in results:
            self.assertTrue(res.manifest.synthetic)
            conv = dict(res.manifest.conventions)
            self.assertEqual(g.convention_problems(conv, FIXTURE["convention_sets"]), [])  # S-1: the same family at the fixture's version OR LATER (PM ruling OI-P11)
            self.assertEqual(conv["performance.lot_method"], "FIFO/1")
            self.assertEqual(conv["performance.minor_unit_table"], "minor-units/1.1")  # performance/1.11 Ruling 2.3: the table with its rows CONFIRMED (value-equivalent to minor-units/1)
            for m in res.metrics:
                self.assertTrue(m.synthetic or res.manifest.release_id is None or not res.manifest.synthetic, m.metric_id)
                self.assertTrue(m.synthetic == res.manifest.synthetic, m.metric_id)

    def test_s2_s3_the_daily_product_and_the_daily_gain_equal_the_segment_results_exactly(self):
        # the runner computes every window with verify_identities=True: a difference would make the metric INSUFFICIENT_DATA + CALCULATION_ERROR (IDENTITY_FAILED).
        seen = set()
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                for item in a["expect"]:
                    if "window" not in item:
                        continue
                    res = self.runner.window(p, a, item["window"]["request"])
                    for m in res.metrics:
                        self.assertNotIn("IDENTITY_FAILED", m.details, (a["id"], m.metric_id))
                        self.assertNotEqual(m.result.reason_code and m.result.reason_code.value, "CALCULATION_ERROR", (a["id"], m.metric_id))
                    if a["id"] in WINDOW_ASSERTIONS_WITH_I2 and item["kind"] == "twr":
                        seen.add(a["id"])
        self.assertEqual(seen, set(WINDOW_ASSERTIONS_WITH_I2))
        # and the identity checks can fail: a tampered segment result is reported
        from performance.engine import _identity_failure  # noqa: PLC0415
        from performance.states import Valued  # noqa: PLC0415
        from product_contract.vocabulary import SufficiencyState  # noqa: PLC0415

        tampered = _identity_failure("I-2 test", Valued(SufficiencyState.AVAILABLE, None, Fraction(1), ()))
        self.assertEqual((tampered.state, tampered.exact), (SufficiencyState.INSUFFICIENT_DATA, None))

    def test_s4_the_value_of_priced_holdings_feeds_nothing(self):
        for name in ("returns", "flows", "periods", "ledger_view"):
            text = (_ROOT / "src" / "performance" / f"{name}.py").read_text(encoding="utf-8").lower()
            self.assertNotIn("partial", text, name)  # no return, gain or flow code reads the partial figure
        # every window result carries no partial metric, and removing the partial metric from a valuation result changes no other metric
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                for item in a["expect"]:
                    if "window" in item:
                        self.assertFalse([m for m in self.runner.window(p, a, item["window"]["request"]).metrics if m.partial])
        p3 = FIXTURE["portfolios"][2]
        v6 = next(a for a in p3["assertions"] if a["id"] == "P3-V6")
        res = self.runner.valuation(p3, v6)
        others = [m for m in res.metrics if not m.partial]
        self.assertEqual(len(others) + 1, len(res.metrics))
        total = next(m for m in others if m.metric_id == "portfolio_value" and m.view == "REPORTING")
        self.assertIsNone(total.result.value)  # the total stays suppressed: the partial figure never stands in for it
        self.assertTrue(all(m.stale_weight is None or not m.partial for m in res.metrics))

    def test_s4_named_mutation_target_a_suppressed_end_value_is_never_replaced_by_the_priced_holdings_figure(self):
        """The test that the S-4 scratch-copy mutation must fail (fixture 1.2-part1, S-4): replace a suppressed end value by the value of priced holdings and P3's
        window results would show a number. Here: where the fixture says the end value (or a flow) is suppressed, the window metrics have NO value, whatever the
        partial figure of the same valuation is."""
        p3 = FIXTURE["portfolios"][2]
        checked = 0
        for assertion_id in ("P3-R3", "P3-R4"):
            a = next(x for x in p3["assertions"] if x["id"] == assertion_id)
            for item in a["expect"]:
                self.assertEqual(item["state"], "INSUFFICIENT_DATA")  # the fixture's own statement
                res = self.runner.window(p3, a, item["window"]["request"])
                wanted = "twr" if item["kind"] == "twr" else item["kind"]
                result = next(m for m in res.metrics if {"twr": "return_twr", "gain_absolute": "gain_absolute"}.get(wanted) == m.metric_id)
                self.assertEqual((result.result.value, result.exact), (None, None), (assertion_id, result.metric_id))
                self.assertEqual(result.result.sufficiency_state.value, "INSUFFICIENT_DATA", (assertion_id, result.metric_id))
                # and for the fixture's REASON: the partial figure's own state would carry a different reason (observed under the S-4 mutation: P3-R4 says
                # MISSING_FX_HISTORY instead of the fixture's MISSING_PRICE_HISTORY)
                self.assertEqual(result.result.reason_code.value, item["reason"], (assertion_id, result.metric_id))
                checked += 1
        self.assertEqual(checked, 3)
        # the suppressed totals of the valuation at the same date have a partial figure beside them: a number that exists and must not be used
        v6 = next(a for a in p3["assertions"] if a["id"] == "P3-V6")
        valuation = self.runner.valuation(p3, v6)
        partial = [m for m in valuation.metrics if m.partial]
        self.assertTrue(partial and partial[0].exact is not None)
        self.assertIsNone(next(m for m in valuation.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING" and not m.partial).exact)

    def test_s5_an_internal_cash_transfer_pair_inserted_into_p1_changes_no_assertion(self):
        p1 = FIXTURE["portfolios"][0]
        events = list(self.runner.events["P1"])
        a1 = self.ids("a1000000-0000-4000-8000-000000000001")
        a3 = self.ids("a1000000-0000-4000-8000-000000000003")
        usd = CurrencyCode("USD")
        out = LedgerEvent(uuid.UUID(int=0x5001), a1, EventType.TRANSFER_OUT, datetime.date(2025, 5, 20), usd, amount=Money(Decimal(100), usd),
                          counterparty_account_id=a3, source_reference="S-5 out")
        inn = LedgerEvent(uuid.UUID(int=0x5002), a3, EventType.TRANSFER_IN, datetime.date(2025, 5, 20), usd, amount=Money(Decimal(100), usd),
                          counterparty_account_id=a1, source_reference="S-5 in")
        events += [SequencedEvent(26, out), SequencedEvent(27, inn)]
        runner = g.Runner(self.market, self.ids, {**self.runner.events, "P1": events}, verify_identities=False)
        mismatches, compared = [], 0
        for a in p1["assertions"]:
            # S-5 is a PORTFOLIO-level statement: an account-level cash or holding value (A3's USD cash) legitimately moves by the 100 USD that was transferred in
            portfolio_level = [i for i in a["expect"] if i["kind"] in ("twr", "gain_absolute", "annualized_twr", "priced_holdings_value")
                               or (i["kind"] == "portfolio_value")]
            shifted = dict(a, ledger_version=27, expect=portfolio_level)  # the pin moves past the inserted pair; every other input is unchanged
            compared += len(portfolio_level)
            mismatches += g.check_assertion(runner, p1, shifted)
        self.assertEqual(mismatches, [], "\n" + describe(mismatches))
        self.assertGreaterEqual(compared, 20)  # not vacuous: 25 portfolio-level items of P1 are compared
        # and the account-level change is real: A3's USD cash moved by exactly the transferred 100
        v8 = next(a for a in p1["assertions"] if a["id"] == "P1-V8")
        moved = g.check_assertion(runner, p1, dict(v8, ledger_version=27))
        self.assertTrue(any(m.field == "value" and m.actual == "96.50" for m in moved))  # -3.50 + 100.00, presented with USD's two minor units (performance/1.x Ruling 2.2)

    def test_s6_determinism_across_runs_shuffles_and_processes(self):
        def digest(runner):
            out = []
            for p in FIXTURE["portfolios"]:
                for a in p["assertions"]:
                    for item in a["expect"]:
                        res = runner.window(p, a, item["window"]["request"]) if "window" in item else runner.valuation(p, a)
                        out.append(res.canonical_json())
            return hashlib.sha256("\n".join(sorted(set(out))).encode("utf-8")).hexdigest()

        first = digest(self.runner)
        runner2, market2 = g.build_runner(cp1.Ids(randomize=False), verify_identities=True)
        self.addCleanup(market2.close)
        self.assertEqual(digest(runner2), first)  # a second build of the world and a second run
        # events shuffled WITHIN their order (ledger_seq unchanged): the same bytes
        import random as _random  # noqa: PLC0415  (a test, not product code)

        shuffled = {name: list(evs) for name, evs in self.runner.events.items()}
        rng = _random.Random(7)
        for evs in shuffled.values():
            rng.shuffle(evs)
        runner3 = g.Runner(self.market, self.ids, shuffled, verify_identities=True)
        self.assertEqual(digest(runner3), first)
        # separate processes with different hash seeds
        digests = set()
        for seed in ("1", "2", "random"):
            proc = subprocess.run([sys.executable, str(Path(__file__)), "digest"], capture_output=True, text=True, timeout=600,
                                  env=dict(os.environ, PYTHONHASHSEED=seed))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            digests.add(proc.stdout.strip())
        self.assertEqual(digests, {first})


# ---- opt-in database layer ------------------------------------------------------------------------------------------------------

_SKIP = pk.skip_reason()


def _append_portfolio(conn, ledger_store, built):
    """Append `[(seq, label, group, event)]` honouring the atomic groups (as the CP1 database test does); return {fixture seq: stored ledger_seq}."""
    mapping = {}
    i = 0
    while i < len(built):
        seq, _label, group, event = built[i]
        members = [built[i]]
        if group is not None:
            while i + len(members) < len(built) and built[i + len(members)][2] == group:
                members.append(built[i + len(members)])
        evs = [m[3] for m in members]
        if group is None:
            results = [ledger_store.append_event(conn, evs[0])]
        elif evs[0].event_type is EventType.REVERSAL:
            pair = ledger_store.append_correction(conn, evs[0], evs[1])
            results = [pair.reversal, pair.replacement]
        elif evs[0].event_type is EventType.TRANSFER_OUT:
            results = list(ledger_store.append_internal_transfer(conn, evs[0], evs[1]))
        else:
            results = ledger_store.append_batch(conn, evs)
        for member, result in zip(members, results):
            mapping[member[0]] = result.ledger_seq
        i += len(members)
    return mapping


@unittest.skipIf(bool(_SKIP), _SKIP)
class DatabaseGoldenTests(unittest.TestCase):
    """The same ledger through the real store as `finweb_app` (random ids per run, so concurrent runs share no lock key) and the same market data through the
    PostgreSQL market-data store; every assertion of the fixture is then compared through the DATABASE path."""

    @classmethod
    def setUpClass(cls):
        from persistence import ledger_replay_store, ledger_store, market_data_store as mds  # noqa: PLC0415

        cls.rs, cls.mds = ledger_replay_store, mds
        cls.db = pk.PgSchema().open()
        cls.addClassCleanup(cls.db.close)
        cls.ids = cp1.Ids(randomize=True)
        cls.market = g.Market(cls.ids)
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
            source = p if "events" in p else cp1.portfolio_named(p["name"][:2])
            pid = cls.ids(p["portfolio_id"])
            cls.db.owner.execute("INSERT INTO portfolio VALUES (%s, %s, %s)", (pid, user, p["reporting_currency"]))
            for account in source["accounts"]:
                cls.db.owner.execute("INSERT INTO account VALUES (%s, %s, %s)", (cls.ids(account["account_id"]), pid, account["name"]))
            built = cp1.build_events(source, cls.ids)
            cls.seq_map[p["name"]] = _append_portfolio(cls.app, ledger_store, built)
            version = ledger_replay_store.current_ledger_version(cls.app, pid)
            cls.stored[p["name"]] = list(ledger_replay_store.load_events(cls.app, pid, version))
        import marketdata_cp2c1_kit as kit_  # noqa: PLC0415

        cls.pg = mds.read_release(cls.app, cls.market.release.release_id, exchange_of=cls.market.ident.exchange_mic, registry=kit_.registry_for(cls.market.store))
        shim = SimpleNamespace(store=cls.pg, ident=cls.market.ident, conventions=market11_conventions(cls.pg.calendars()))
        cls.runner = g.Runner(shim, cls.ids, cls.stored, verify_identities=True, seq_map=cls.seq_map)

    def test_every_item_of_every_assertion_matches_the_fixture_through_the_database_as_finweb_app(self):
        self.assertEqual(self.app.execute("SELECT current_user").fetchone()[0], self.db.app_role)
        checked = 0
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                with self.subTest(assertion=a["id"]):
                    found = g.check_assertion(self.runner, p, a)
                    checked += len(a["expect"])
                    self.assertEqual(found, [], "\n" + describe(found))
        self.assertEqual(checked, 93)

    def test_the_database_and_the_pure_paths_give_the_same_results_except_for_ids_and_ledger_numbers(self):
        pure_runner, market = g.build_runner(cp1.Ids(randomize=False), verify_identities=False)
        self.addCleanup(market.close)
        p = FIXTURE["portfolios"][0]
        a = next(x for x in p["assertions"] if x["id"] == "P1-V7")
        pure = pure_runner.valuation(p, a)
        db = self.runner.valuation(p, a)
        key = lambda res: sorted((m.metric_id, m.view, m.result.value, m.exact, m.result.sufficiency_state.value) for m in res.metrics)  # noqa: E731
        self.assertEqual(key(pure), key(db))

    def test_a_computation_wrote_nothing_to_the_ledger(self):
        p = FIXTURE["portfolios"][0]
        pid = self.ids(p["portfolio_id"])
        before = self.rs.current_ledger_version(self.app, pid)
        for a in p["assertions"][:3]:
            g.check_assertion(self.runner, p, a)
        self.assertEqual(self.rs.current_ledger_version(self.app, pid), before)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "digest":
        _ids = cp1.Ids(randomize=False)
        _runner, _market = g.build_runner(_ids, verify_identities=True)
        _out = []
        for _p in FIXTURE["portfolios"]:
            for _a in _p["assertions"]:
                for _item in _a["expect"]:
                    _res = _runner.window(_p, _a, _item["window"]["request"]) if "window" in _item else _runner.valuation(_p, _a)
                    _out.append(_res.canonical_json())
        print(hashlib.sha256("\n".join(sorted(set(_out))).encode("utf-8")).hexdigest())
        _market.close()
    else:
        unittest.main()
