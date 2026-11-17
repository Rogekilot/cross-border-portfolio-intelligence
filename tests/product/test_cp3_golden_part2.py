"""CP3 golden fixture, part 2 (`methodology/fixtures/cp3_golden/cp3_golden_part2.json`, `cp3_golden/1.1-part2`, `performance/1.4`, `ledger-replay/1.3`, `market-data/1.10`): the MWR and
annualized MWR, the income, fee, tax, financing and conversion-result amounts, the dividend receivables and the synthetic split-suppression case. 78 items.

The fixture is never edited here and no expected value is derived here: a mismatch is reported (assertion id, expected, actual) and neither side is changed.

Layers: 1. SHAPE and PINS; 2. the expansion of part 2's additions into real CP2 layouts adds no number; 3. PURE: every item compared (the F8-B dry run supplies the suppressions);
4. STRUCTURAL assertions S2-1 to S2-5; 5. DATABASE (opt-in): the same ledger through the real store as `finweb_app` and the market data through the PostgreSQL market-data store.
"""

import copy
import datetime
import hashlib
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
import pg_market_kit as pk  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.ledger import EventType  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402

FIXTURE = p2.FIXTURE

# A tripwire against a silently trimmed or edited fixture (like FIXTURE_PINS of part 1). It changes only with a new `fixture_id`. The counts come from the fixture FILE, never from engine
# output; the hash is over the assertions (id, as_of, ledger_version, expect) and is unchanged by the wording-only 1.1-part2.
FIXTURE_PINS = {
    "cp3_golden/1.2-part2": {
        "expect_counts": {
            "P1-M1": 7, "P1-M2": 2, "P2-M1": 1, "P4-M1": 2, "P5-M1": 3, "P7-V1": 3, "P7-V2": 4, "P7-V3": 2, "P7-V4": 2, "P7-R1": 7, "P7-R2": 2, "P7-R3": 2, "P7-R4": 6,
            "P8-M1": 4, "P9-M1": 3, "P10-M1": 3, "P11-M1": 3, "P11-M2": 3, "P12-V1": 1, "P12-V2": 1, "P12-R1": 8, "P13-S1": 1, "P13-V1": 1, "P13-V2": 4, "P13-R1": 3,
        },
        "expect_total": 78,
        "assertions": 25,
        "content_sha256": "c62a5c49493211ec240bae52f13390b5d987fbe664e7d55522f193d874c8611d",
    },
}
MWR_WITH_NO_INTERIOR_FLOW = ("P2-M1", "P7-R1", "P8-M1")  # structural assertion S2-2 names these
NEW_KINDS = {"mwr", "annualized_mwr", "income_amount", "fees_amount", "taxes_amount", "financing_amount", "conversion_result_amount", "receivable_value", "split_outcome"}


def describe(found):
    return "\n".join(str(m) for m in found)


class _Shared(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = cp1.Ids(randomize=False)
        cls.runner, cls.market = p2.build_runner(cls.ids, verify_identities=True)
        cls.addClassCleanup(cls.market.close)


class FixtureShapeTests(unittest.TestCase):
    def test_the_fixture_is_the_ratified_one_and_pinned(self):
        pins = FIXTURE_PINS[FIXTURE["fixture_id"]]
        counts = {a["id"]: len(a["expect"]) for p in FIXTURE["portfolios"] for a in p["assertions"]}
        self.assertEqual(counts, pins["expect_counts"])
        self.assertEqual((sum(counts.values()), len(counts)), (pins["expect_total"], pins["assertions"]))
        self.assertEqual({k: v for k, v in FIXTURE["item_counts"].items() if k not in ("note", "total")}, counts)
        self.assertEqual(FIXTURE["item_counts"]["total"], pins["expect_total"])
        self.assertEqual(p2.content_hash(), pins["content_sha256"])
        # minimum versions (PM ruling OI-P11); this is the file as relabelled in 1.2-part2
        self.assertEqual(FIXTURE["convention_sets"], {"performance": "performance/1.6", "ledger_replay": "ledger-replay/1.5 (FIFO/1 mode)", "market_data": "market-data/1.10",
                                                      "lot_relief": FIXTURE["convention_sets"]["lot_relief"]})
        self.assertEqual(FIXTURE["extends"]["fixture_id"], g.FIXTURE["fixture_id"])  # part 2 extends the part-1 fixture the loader reads
        self.assertEqual(FIXTURE["part"], 2)

    def test_the_fixture_exercises_every_new_kind_and_cannot_pass_vacuously(self):
        kinds = {i["kind"] for _p, _a, i in p2.items()}
        self.assertTrue(NEW_KINDS <= kinds, NEW_KINDS - kinds)
        self.assertEqual(sum(1 for _p, _a, i in p2.items() if i.get("emitted") is False), 2)  # P7-V1 and P7-V4: no receivable
        states = {i["state"] for _p, _a, i in p2.items() if "state" in i}
        self.assertEqual(states, {"AVAILABLE", "INSUFFICIENT_DATA"})
        self.assertTrue(all(isinstance(a["ledger_version"], int) for _p, a, _i in p2.items()))


class MarketExpansionTests(_Shared):
    def test_the_expansion_ingests_through_the_real_adapters_with_no_issue(self):
        self.assertEqual(self.market.issues, ((), ()))
        add = FIXTURE["market_data_additions"]
        md = g.FIXTURE["market_data"]
        # part 1's files + the new price files + the corporate-action pair (one FEED file and one FILING file)
        expected = len(md["calendars"]) + 1 + len(md["prices"]["series"]) + len(add["prices"]["series"]) + 2
        self.assertEqual(len(self.market.manifests), expected)
        self.assertTrue(self.market.store.contains_synthetic)
        self.assertTrue(all(m.usage_scope.value == "SYNTHETIC_TEST" for m in self.market.manifests))
        self.assertTrue(all(m.source_id.startswith("synthetic.") or m.source_id == "calendar.manual" for m in self.market.manifests))

    def test_the_new_series_are_exactly_the_fixtures_steps_and_no_part_1_series_changed(self):
        D = datetime.date.fromisoformat
        for s in FIXTURE["market_data_additions"]["prices"]["series"]:
            readings = self.market.store.quotes(self.ids(s["listing_id"]), D(s["first"]), D(s["last"])).readings
            self.assertTrue(readings, s["ticker"])
            for r in readings:
                day = r.observation.value_date
                step = [x for x in s["steps"] if D(x["from"]) <= day][-1]
                self.assertEqual(r.observation.price, Decimal(step["close"]), (s["ticker"], day))
        part1 = {p["listing_id"] for p in g.FIXTURE["market_data"]["prices"]["series"]}
        self.assertEqual(len(part1), 5)  # untouched

    def test_the_corporate_action_pair_carries_exactly_the_fixtures_ex_date_and_ratio_in_a_feed_and_a_filing(self):
        (action,) = FIXTURE["market_data_additions"]["corporate_actions"]
        actions = self.market.store.corporate_actions(self.ids(action["listing_id"]), datetime.date.min, datetime.date.max)
        readings = list(actions.readings)
        self.assertEqual(sorted(r.source_id for r in readings), [g.CA_FEED, g.CA_FILING])
        for r in readings:
            o = r.observation
            self.assertEqual((o.effective_date.isoformat(), o.split_ratio.new_units, o.split_ratio.old_units, o.lineage.is_synthetic),
                             (action["ex_date"], Decimal(action["ratio"]["new_units"]), Decimal(action["ratio"]["old_units"]), True))
        self.assertEqual(len({r.file_sha256 for r in readings}), 2)  # two different files, a feed and a filing


class PureGoldenTests(_Shared):
    def test_every_item_of_every_assertion_matches_the_fixture(self):
        checked = 0
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                with self.subTest(assertion=a["id"]):
                    found = p2.check_assertion(self.runner, p, a)
                    checked += len(a["expect"])
                    self.assertEqual(found, [], "\n" + describe(found))
        self.assertEqual(checked, 78)

    def test_the_checker_really_fails_on_a_wrong_expectation(self):
        p = next(x for x in FIXTURE["portfolios"] if x["name"].startswith("P1 "[:2]) and x["name"] == "P1")
        a = next(x for x in p["assertions"] if x["id"] == "P1-M1")
        for kind, field, wrong in (("mwr", "state", "INSUFFICIENT_DATA"), ("fees_amount", "value", "-2.01"), ("conversion_result_amount", "exact", "-9"),
                                   ("income_amount", "reason", "STALE_DATA"), ("annualized_mwr", "year_fraction", "2173/4381")):
            wrong_a = copy.deepcopy(a)
            for item in wrong_a["expect"]:
                if item["kind"] == kind:
                    item[field] = wrong
            found = p2.check_assertion(self.runner, p, wrong_a)
            self.assertTrue([m for m in found if m.kind == kind], (kind, field))
        # a tolerance is used only where the fixture gives one: widening the MWR beyond 1e-10 is reported
        mwr = copy.deepcopy(a)
        item = next(i for i in mwr["expect"] if i["kind"] == "mwr")
        item["value"] = str(Decimal(item["value"]) + Decimal("1e-9"))
        self.assertIn("value (tolerance 1E-10)", {m.field for m in p2.check_assertion(self.runner, p, mwr)})
        # a split_outcome and an `emitted: false` item can fail too
        p13 = next(x for x in FIXTURE["portfolios"] if x["name"].startswith("P13"))
        s1 = copy.deepcopy(next(x for x in p13["assertions"] if x["id"] == "P13-S1"))
        s1["expect"][0]["append"] = "WOULD_APPEND"
        self.assertEqual([m.field for m in p2.check_assertion(self.runner, p13, s1)], ["append"])
        p7 = next(x for x in FIXTURE["portfolios"] if x["name"].startswith("P7"))
        v2 = copy.deepcopy(next(x for x in p7["assertions"] if x["id"] == "P7-V2"))  # on 05-06 a receivable DOES exist
        v2["expect"] = [{"kind": "receivable_value", "event_id": "e7000000-0000-4000-8000-000000000005", "emitted": False}]
        self.assertEqual([m.field for m in p2.check_assertion(self.runner, p7, v2)], ["emitted"])


class StructuralAssertionTests(_Shared):
    def results(self):
        out = []
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                for item in a["expect"]:
                    if item["kind"] == "split_outcome":
                        continue
                    out.append((p, a, item, self.runner.window(p, a, item["window"]["request"]) if "window" in item else self.runner.valuation(p, a)))
        return out

    def test_s2_1_every_result_is_synthetic_and_every_manifest_cites_the_fixtures_convention_ids(self):
        rs = self.results()
        self.assertGreater(len(rs), 60)
        sets = FIXTURE["convention_sets"]
        for _p, _a, _i, res in rs:
            self.assertTrue(res.manifest.synthetic)
            conv = dict(res.manifest.conventions)
            self.assertEqual(g.convention_problems(conv, sets), [])  # S2-1: the same family at the fixture's version or later (PM ruling OI-P11)
            for m in res.metrics:
                self.assertTrue(m.synthetic)

    def test_s2_2_identity_i6_the_mwr_equals_the_twr_with_no_interior_flow_and_f_of_1_is_g(self):
        seen = set()
        for p, a, item, res in self.results():
            if item["kind"] != "mwr" or item["state"] != "AVAILABLE":
                continue
            mwr = next(m for m in res.metrics if m.metric_id == "return_mwr")
            self.assertIn(dict(mwr.lineage)["identity:I-6"], ("PASS", "NOT_APPLICABLE"), a["id"])  # f(1) = G held (and the MWR = TWR where applicable)
            gain = next(m for m in res.metrics if m.metric_id == "gain_absolute")
            if gain.exact is not None:
                self.assertEqual((mwr.exact > 0) - (mwr.exact < 0), (gain.exact > 0) - (gain.exact < 0), a["id"])  # the sign of the MWR is the sign of G
            if a["id"] in MWR_WITH_NO_INTERIOR_FLOW:
                twr = next(m for m in res.metrics if m.metric_id == "return_twr")
                self.assertEqual((dict(mwr.lineage)["identity:I-6"], mwr.exact), ("PASS", twr.exact), a["id"])  # EXACTLY equal
                seen.add(a["id"])
        self.assertEqual(seen, set(MWR_WITH_NO_INTERIOR_FLOW))

    def test_s2_3_the_solver_is_deterministic_in_process_and_across_processes(self):
        def digest(runner):
            out = []
            for p in FIXTURE["portfolios"]:
                for a in p["assertions"]:
                    for item in a["expect"]:
                        if item["kind"] in ("mwr", "annualized_mwr"):
                            out.append(runner.window(p, a, item["window"]["request"]).canonical_json())
            return hashlib.sha256("\n".join(sorted(set(out))).encode("utf-8")).hexdigest()

        first = digest(self.runner)
        runner2, market2 = p2.build_runner(cp1.Ids(randomize=False), verify_identities=True)
        self.addCleanup(market2.close)
        self.assertEqual(digest(runner2), first)  # a second build and a second run
        digests = set()
        for seed in ("1", "2", "random"):
            proc = subprocess.run([sys.executable, str(Path(__file__)), "digest"], capture_output=True, text=True, timeout=600, env=dict(os.environ, PYTHONHASHSEED=seed))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            digests.add(proc.stdout.strip())
        self.assertEqual(digests, {first})

    def test_s2_4_synthetic_evidence_never_appends_dry_run_or_not(self):
        p13 = next(x for x in FIXTURE["portfolios"] if x["name"].startswith("P13"))
        events = self.runner.events[p13["name"]]
        self.assertEqual(max(e.ledger_seq for e in events), 2)
        for dry in (True, False):
            ledger = ca.FakeLedger()
            for row in events:
                ledger.add(row.event)
            listing = self.ids("c0000000-0000-4000-8000-0000001e0001")
            report = f8b.confirm_splits(ledger, self.market.store, self.ids(p13["portfolio_id"]), (listing,), datetime.date.min, datetime.date.max, p2.POLICY,
                                        {listing: self.market.ident.trading_currency(listing)}, calendars=self.market.conventions.freshness.calendars,
                                        exchange_of=self.market.ident.exchange_mic, dry_run=dry)
            self.assertEqual(ledger.appended, [], dry)
            self.assertEqual((report.ledger_version_before, report.ledger_version_after), (2, 2), dry)
            self.assertFalse([r for r in ledger.rows if r.event.event_type is EventType.SPLIT], dry)
            self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.NOT_RECORDED_APPEND_BARRED], dry)

    def test_s2_5_the_amount_lines_add_up_with_the_price_effect_to_the_absolute_gain(self):
        """Ruling 8.6 / 9.3: for P7 over (03-31, 06-26] G = price effect + income + fees + taxes + financing + conversion result (here the conversion line is 0). The only number
        taken from outside the engine is the price effect, from the derivation (section 4 cross-check): 1,000 shares x (51.00 - 50.00) HKD x 16/125."""
        p7 = next(x for x in FIXTURE["portfolios"] if x["name"].startswith("P7"))
        a = next(x for x in p7["assertions"] if x["id"] == "P7-R1")
        res = self.runner.window(p7, a, {"rule": "SINCE_INCEPTION"})
        by = {m.metric_id: m for m in res.metrics}
        lines = sum((by[k].exact for k in ("income_amount", "fees_amount", "taxes_amount", "financing_amount", "conversion_result_amount")), Fraction(0))
        price_effect = Fraction(1000) * (51 - 50) * Fraction(16, 125)
        self.assertEqual(by["gain_absolute"].exact, price_effect + lines)
        self.assertEqual(by["conversion_result_amount"].exact, 0)


# ---- opt-in database layer ------------------------------------------------------------------------------------------------------

_SKIP = pk.skip_reason()


@unittest.skipIf(bool(_SKIP), _SKIP)
class DatabaseGoldenTests(unittest.TestCase):
    """The same ledger through the real store as `finweb_app` and the same market data through the PostgreSQL market-data store; every item is compared through the DATABASE path."""

    @classmethod
    def setUpClass(cls):
        from persistence import ledger_replay_store, ledger_store, market_data_store as mds  # noqa: PLC0415
        import test_cp3_golden_part1 as t1  # noqa: PLC0415

        cls.rs, cls.mds = ledger_replay_store, mds
        cls.db = pk.PgSchema().open()
        cls.addClassCleanup(cls.db.close)
        cls.ids = cp1.Ids(randomize=True)
        cls.market = p2.build_market(cls.ids)
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
            source = p2.source_of(p)
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
        cls.runner = p2.Runner(shim, cls.ids, cls.stored, verify_identities=True, seq_map=cls.seq_map)

    def test_every_item_of_every_assertion_matches_the_fixture_through_the_database_as_finweb_app(self):
        self.assertEqual(self.app.execute("SELECT current_user").fetchone()[0], self.db.app_role)
        checked = 0
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                with self.subTest(assertion=a["id"]):
                    found = p2.check_assertion(self.runner, p, a)
                    checked += len(a["expect"])
                    self.assertEqual(found, [], "\n" + describe(found))
        self.assertEqual(checked, 78)

    def test_s2_4_on_the_database_the_ledger_of_p13_is_unchanged_and_holds_no_split(self):
        p13 = next(x for x in FIXTURE["portfolios"] if x["name"].startswith("P13"))
        pid = self.ids(p13["portfolio_id"])
        before = self.rs.current_ledger_version(self.app, pid)
        for a in p13["assertions"]:
            p2.check_assertion(self.runner, p13, a)
        self.assertEqual(self.rs.current_ledger_version(self.app, pid), before)
        self.assertEqual(before, self.seq_map[p13["name"]][2])
        self.assertFalse([e for e in self.stored[p13["name"]] if e.event.event_type is EventType.SPLIT])

    def test_the_database_and_the_pure_paths_give_the_same_mwr_and_amounts(self):
        pure, market = p2.build_runner(cp1.Ids(randomize=False), verify_identities=False)
        self.addCleanup(market.close)
        p = next(x for x in FIXTURE["portfolios"] if x["name"].startswith("P7"))
        a = next(x for x in p["assertions"] if x["id"] == "P7-R1")
        key = lambda res: sorted((m.metric_id, m.result.value, m.exact, m.result.sufficiency_state.value) for m in res.metrics)  # noqa: E731
        self.assertEqual(key(pure.window(p, a, {"rule": "SINCE_INCEPTION"})), key(self.runner.window(p, a, {"rule": "SINCE_INCEPTION"})))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "digest":
        runner, market = p2.build_runner(cp1.Ids(randomize=False), verify_identities=True)
        out = []
        for p in FIXTURE["portfolios"]:
            for a in p["assertions"]:
                for item in a["expect"]:
                    if item["kind"] in ("mwr", "annualized_mwr"):
                        out.append(runner.window(p, a, item["window"]["request"]).canonical_json())
        print(hashlib.sha256("\n".join(sorted(set(out))).encode("utf-8")).hexdigest())
        market.close()
    else:
        unittest.main()
