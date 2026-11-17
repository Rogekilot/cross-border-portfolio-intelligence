"""CP4c: the engine against the Quant's `cp4_golden` parts 1 to 3 (`risk/1.2`), on the pure path (no database): the series spine, the risk-free leg, the single-series metrics and the benchmark return.

Every expected value is the Quant's (hand derived, re-derived by independent calculators that import nothing from `src/`); nothing is computed from the engine. A mismatch is a FINDING: neither side is adjusted.
What is CHECKED and what is DEFERRED is pinned item by item (`cp4_golden_kit.DEFERRED_REASONS`): the benchmark-relative metrics belong to the next increment (after the independent review of this midpoint), the default
view (Ruling 7.7) and Current mode (Ruling 5.8) are not built, and a benchmark of two sources or an ETF proxy waits for Rulings 5.5 and 5.7.
"""

import datetime
import json
import sys
import unittest
from collections import Counter
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp4_golden_kit as g  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402

from marketdata.canonical import canonical_json  # noqa: E402
from risk import states as S  # noqa: E402
from risk import stats  # noqa: E402
from risk.engine import compute_risk, reproduce_risk  # noqa: E402
from risk.manifest import RiskReproductionStatus as St  # noqa: E402

D = datetime.date

#: item counts and a content hash per part (the pin of what the Quant asserts: a reissued part changes them and this fails loudly)
FIXTURE_PINS = {
    1: ("cp4_golden/1.0-part1", 78, "0a5a21823016375c9e99cd801a8227e4ebdeee8cbb9a239a7e31b128374cd4c9"),
    2: ("cp4_golden/1.0-part2", 61, "635711f6f7499bb7f6e9d583d1bdc46e8f4f9973d8c66c390a67ca87d1fffd6c"),
    # 1.4-part3 (market-data/1.13, risk/1.4): the 1.2 items unchanged (no item value moved), plus `release_cases` RB-1 to RB-9 (checked in `test_market_data_segments`), which are not items.
    # 1.5-part3 (risk/1.5): R9-Z3 (3 items) and R6-W0 (2 items) added, mutations M-C30 and M-C31; 88 items. 1.6-part3 (risk/1.6): R5-E4, R5-E5, R5-E6 and R11-V1 added (7 items), mutations M-C32 to M-C35; no earlier item
    # changes; 95 items.
    # 1.7-part3 (risk/1.7): R5-E7 and R5-E8 added (SYN34, the identity of one dividend across the feed and the filing), mutations M-C36 and M-C37; no earlier item changes; 98 items.
    # 1.8-part3 (risk/1.8): R5-E9 added (SYN35: a USD ETF that declares in CNY; mutations M-C38 to M-C42); no earlier item changes; 101 items.
    # 1.9-part3 (risk/1.9, market-data/1.14): declared precision on every multi-source series, SYN4_BM_US_TR5 and SYN4_BM_US_TR4, R4-S4, R4-S6, R5-E10 to R5-E12, mutations M-C43 to M-C46; no earlier value, state, reason or
    # detail changes; 107 items.
    3: ("cp4_golden/1.9-part3", 107, "1001b96b3382eb5b768c22db83b865c714b44e4569587d645be562a5e4690649"),
    # part 4 (a new file, minimums risk/1.9, performance/1.12, market-data/1.14): the risk-free quote at instant t in Current mode (R41-C1 to C3) and the default view of a benchmark-relative metric (R41-V1, R42-V0); 11 items
    4: ("cp4_golden/1.0-part4", 11, "a598389dca44f269d7e65400a3eb5bf92f0ba007bfa3db9e3b21a74e096d06bd"),
}
#: how many items each part has checked, and why the rest are deferred
EXPECTED_DISPOSITION = {
    1: (78, {}),
    2: (61, {}),
    4: (11, {}),
    3: (107, {}),  # CP4d: nothing is deferred. Increment 1 built the relative metrics and the comparability; increment 2 the two sources, the ETF proxies, Current mode and the default view
}
#: which parts the engine's registry id meets the MINIMUM `risk` version of. Part 3 on disk asks for risk/1.4 (not issued); its R13 items are deferred as PENDING_QUANT_RULING and nothing else in it needs 1.4. When
#: the engine implements 1.4 this flips, and the test says so.
MINIMUM_MET = {1: True, 2: True, 3: True, 4: True}


def runner_for(part: int) -> g.Runner:
    """Files are cut and retrieved as the part declares (`VintagePlan`)."""
    return g.shared_runner(part)


class FixtureTests(unittest.TestCase):
    def test_every_part_is_the_one_the_tests_pin(self):
        for number, (fixture_id, count, digest) in FIXTURE_PINS.items():
            data = g.load_part(number)
            self.assertEqual(data["fixture_id"], fixture_id)
            self.assertEqual(sum(len(a["expect"]) for p in data["portfolios"] for a in p["assertions"]), count)
            self.assertEqual(sum(v for k, v in data["item_counts"].items() if k != "note"), count, "the part's own item counts")
            self.assertEqual(g.content_hash(data), digest, f"part {number} was reissued: review it, then update FIXTURE_PINS")

    def test_the_minimum_convention_sets_are_met_by_the_engine(self):
        from risk.registry import REGISTRY_ID  # noqa: PLC0415

        for number in (1, 2, 3, 4):
            cited = g.load_part(number)["convention_sets"]["risk"]
            family, version = cited.split("/")
            self.assertEqual(family, "risk")
            met = tuple(int(x) for x in REGISTRY_ID.split("/")[1].split(".")) >= tuple(int(x) for x in version.split("."))
            self.assertEqual(met, MINIMUM_MET[number], (number, cited, REGISTRY_ID))

    def test_no_fixture_holds_a_float_literal(self):
        for number in (1, 2, 3, 4):
            g.load_part(number)  # parse_float refuses

    def test_every_detail_name_a_fixture_asserts_is_a_name_of_ruling_7_4(self):
        for number in (1, 2, 3, 4):
            for _p, _a, item in g.items(g.load_part(number)):
                for name in item.get("details_include", []):
                    self.assertIn(name, S.RISK_DETAIL_NAMES, (number, item["kind"], name))

    def test_what_is_checked_and_what_is_deferred_is_pinned_per_part(self):
        for number, (checked, deferred) in EXPECTED_DISPOSITION.items():
            n, rows = g.tally(g.load_part(number))
            self.assertEqual((n, dict(Counter(d.reason for d in rows))), (checked, deferred), number)
            self.assertTrue(all(d.reason in g.DEFERRED_REASONS for d in rows))

    def test_the_loader_tolerates_a_part_that_grows_new_blocks_and_new_kinds(self):
        import copy  # noqa: PLC0415

        data = copy.deepcopy(g.load_part(1))
        data["market_data"]["a_future_block"] = {"anything": [1, 2, 3]}
        data["format"]["a_future_note"] = "ignored"
        data["portfolios"][0]["assertions"][0]["expect"].append({"kind": "a_future_metric", "frequency": "WEEKLY", "request": {"rule": "SINCE_INCEPTION"}, "state": "AVAILABLE"})
        data["portfolios"][0]["assertions"][0]["valuation_mode"] = "HISTORICAL"
        checked, deferred = g.tally(data)
        self.assertEqual(checked, 78)
        self.assertEqual([(d.kind, d.reason) for d in deferred], [("a_future_metric", "KIND_UNKNOWN_TO_THIS_LOADER")])  # recorded, not an error and not a silent skip
        market = g.Market(data, cp1.Ids(randomize=False))  # the unknown block is not an input
        self.addCleanup(market.close)
        self.assertEqual(market.built.exceptions, ())

    def test_nothing_deferred_is_a_single_series_metric_or_a_series_item(self):
        for number in (1, 2, 3):
            _n, rows = g.tally(g.load_part(number))
            for d in rows:
                self.assertNotIn(d.kind, ("volatility", "downside_deviation", "max_drawdown", "sharpe", "sortino", "return_series", "risk_free_rates"), (number, d))


class PartOneTests(unittest.TestCase):
    """The series spine, the risk-free conversion, the five single-series metrics, the thresholds and every HG3 edge case but the benchmark."""

    def test_every_item_of_part_1_matches_exactly(self):
        found, checked, deferred = g.check_all(runner_for(1))
        self.assertEqual((checked, len(deferred)), (78, 0))
        self.assertEqual([str(m) for m in found], [])

    def test_the_market_data_built_without_a_refusal(self):
        market = runner_for(1).market
        self.assertEqual(market.built.exceptions, ())
        # the only issues are the declared N/A cells of the ECB file (Ruling 1.6: not an observation) and the SSE file's change column across the closed week
        self.assertTrue(all(issue.code.value in ("MISSING_VALUE", "CONSISTENCY_CHECK_FAILED") for _sha, issue in market.built.issues))


class PartTwoTests(unittest.TestCase):
    def test_every_checked_item_of_part_2_matches_exactly(self):
        found, checked, deferred = g.check_all(runner_for(2))
        self.assertEqual((checked, len(deferred)), (61, 0))
        self.assertEqual([str(m) for m in found], [])

    def test_the_market_data_built_without_an_issue(self):
        self.assertEqual(runner_for(2).market.issues, ((), ()))


class PartFourTests(unittest.TestCase):
    def test_every_checked_item_of_part_4_matches_exactly(self):
        found, checked, deferred = g.check_all(runner_for(4))
        self.assertEqual((checked, len(deferred)), (11, 0))
        self.assertEqual([str(m) for m in found], [])

    def test_the_market_data_built_without_an_issue_and_the_files_are_the_ones_the_part_lists(self):
        runner = runner_for(4)
        self.assertEqual(runner.market.issues, ((), ()))
        listed = {f["file"] for f in g.load_part(4)["market_data"]["retrieval"]["files"]}
        self.assertEqual(len(runner.market.manifests), len(listed) + len(g.load_part(4)["market_data"]["calendars"]))  # every listed file, and the calendars (registered, not retrieved)

    def test_the_risk_free_quote_at_t_is_used_missed_or_not_yet_due_as_the_part_states(self):
        """R41-C3, R41-C2, R41-C1: the 11-26 quote is published at 01:00Z on 11-27 and its file retrieved at 01:15Z. At 00:30 it is not yet due (0 missed, the 11-25 rate), at 01:10 it is published but not in M_t (1 missed,
        RISK_FREE_STALE in the lineage, the Sharpe ratio LIMITED by count with no reason), at 01:30 it is used. (A synthetic 20:00 New York publication makes the first case testable: on no real calendar can it arise.)"""
        r = runner_for(4)
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("P41 ")]
        seen = {}
        for aid in ("R41-C3", "R41-C2", "R41-C1"):
            a = next(x for x in p["assertions"] if x["id"] == aid)
            item = next(i for i in a["expect"] if i["kind"] == "sharpe")
            sharpe = r.risk(p, a, item, ("risk_sharpe",)).metric("risk_sharpe")
            seen[aid] = (sharpe.state.value, sharpe.result.reason_code, g._risk_names(sharpe.details))
        self.assertEqual(seen["R41-C3"], ("LIMITED", None, ["OBSERVATIONS_BELOW_STANDARD"]))
        self.assertEqual(seen["R41-C2"], ("LIMITED", None, ["OBSERVATIONS_BELOW_STANDARD", "RISK_FREE_STALE"]))  # the stale input is a lower-level coded cause: no reason (Ruling 7.3 (1.3))
        self.assertEqual(seen["R41-C1"], ("LIMITED", None, ["OBSERVATIONS_BELOW_STANDARD"]))

    def test_the_default_view_falls_back_for_a_young_portfolio_and_not_for_a_benchmark_side_refusal(self):
        r = runner_for(4)
        views = {}
        for pname, aid in (("P41 ", "R41-V1"), ("P42 ", "R42-V0")):
            (p,) = [p for p in r.data["portfolios"] if p["name"].startswith(pname)]
            a = next(x for x in p["assertions"] if x["id"] == aid)
            item = next(i for i in a["expect"] if i["kind"] == "default_view")
            view, _metric = g.run_default_view(r, p, a, item)
            views[aid] = view
        self.assertTrue(views["R41-V1"].fallback)
        self.assertEqual((views["R41-V1"].shown.state.value, views["R41-V1"].shown.observation_count), ("LIMITED", 56))  # MAX_AVAILABLE, with its own window
        self.assertFalse(views["R42-V0"].fallback)  # BENCHMARK_NOT_COVERING_WINDOW is the benchmark's, never a trigger
        self.assertEqual(g._risk_names(views["R42-V0"].shown.details), ["BENCHMARK_NOT_COVERING_WINDOW"])


class PartThreeTests(unittest.TestCase):
    def assert_complete_market_build(self, market):
        """CP4F-16: fixture evidence includes every source file, not just queried dates."""
        self.assertEqual(market.built.exceptions, ())
        manifests = {m.file_sha256: m for m in market.manifests}
        expected_counts = {
            "synthetic.alphavantage_us": 24, "synthetic_b": 12,
            "mock.synthetic": 9, "synthetic_a": 9, "calendar.manual": 6,
            "synthetic.riskfree": 6, "synthetic.ca_feed": 5,
            "synthetic.ca_filing": 5, "synthetic.ecb_direct": 3,
            "synthetic.sina_hk": 3,
        }
        self.assertEqual(Counter(m.source_id for m in market.manifests), expected_counts)
        self.assertEqual(Counter(s.file_sha256 for s in market.built.summaries), Counter(manifests.keys()))
        self.assertEqual(Counter(m.file_sha256 for m in market.built.manifests), Counter(manifests.keys()))
        self.assertEqual(Counter(manifests[s.file_sha256].source_id for s in market.built.summaries), expected_counts)
        declared = g.load_part(3)["market_data"]["fx"]["gaps_by_currency"]
        expected_issues = Counter(("synthetic.ecb_direct", "MISSING_VALUE", f"{day}/{currency}")
                                  for currency, days in declared.items() for day in days)
        actual_issues = Counter((manifests[sha].source_id, issue.code.value, issue.row_ref)
                                for sha, issue in market.built.issues)
        self.assertEqual(actual_issues, expected_issues)
        self.assertTrue(all(s.observation_count > 0 for s in market.built.summaries), "a refused or empty source file")

    def test_the_market_data_build_is_complete_for_every_source(self):
        self.assert_complete_market_build(runner_for(3).market)

    def test_the_build_guard_catches_the_previous_json_rotation_refusal(self):
        def legacy_csv_rotation(payload, seen):
            # The previous loader applied CSV column rotation to duplicate JSON.
            text = payload.decode("utf-8")
            for turn in range(8):
                candidate = payload
                if turn:
                    rows = [line.split(",") for line in text.splitlines()]
                    shift = turn % len(rows[0])
                    candidate = ("\n".join(",".join(row[shift:] + row[:shift]) for row in rows) + "\n").encode()
                digest = g.sha256_hex(candidate)
                if digest not in seen:
                    seen.add(digest)
                    return candidate
            raise AssertionError("could not make a distinct payload")

        with patch.object(g, "_distinct_payload", legacy_csv_rotation):
            market = g.Market(g.load_part(3), cp1.Ids(randomize=False))
        self.addCleanup(market.close)
        self.assertTrue(any(issue.code.value == "UNKNOWN_FORMAT" for _, issue in market.built.issues))
        with self.assertRaises(AssertionError):
            self.assert_complete_market_build(market)

    def test_every_checked_item_of_part_3_matches_exactly(self):
        found, checked, deferred = g.check_all(runner_for(3))
        self.assertEqual((checked, len(deferred)), (107, 0))
        self.assertEqual([str(m) for m in found], [])

    def test_the_part_has_corporate_actions_and_the_dry_run_gives_the_split_suppression(self):
        r = runner_for(3)
        self.assertTrue(r.market.has_actions)
        (p11,) = [p for p in r.data["portfolios"] if p["name"].startswith("R11 ")]
        self.assertTrue(r.suppressions_for(p11, r.version(p11, p11["assertions"][0])))  # R11's split is corroborated and NOT in the ledger
        (p12,) = [p for p in r.data["portfolios"] if p["name"].startswith("R12 ")]
        self.assertEqual(r.suppressions_for(p12, r.version(p12, p12["assertions"][0])), ())  # R12 recorded it


class PartThreeVintageTests(unittest.TestCase):
    """Part 3 (1.1) declares THREE FILE VINTAGES per series (`market_data.retrieval`): V1 the rows to 2026-01-08, V2 the rows of 2026-01-09 each retrieved at its own calendar's close or publication instant, V3 the
    rest. The kit cuts the files exactly so (the 1.0 declaration of one retrieval time for every file is withdrawn), and M_t, the files retrieved at or before t, then holds exactly the rows due at t."""

    @classmethod
    def setUpClass(cls):
        cls.r = runner_for(3)
        cls.spec = cls.r.data["market_data"]["retrieval"]

    def files_of(self, kind, label_prefix):
        return sorted((m for m in self.r.market.manifests if m.data_kind.value == kind and m.payload_filename.startswith(label_prefix)), key=lambda m: m.retrieval_time)

    def test_a_series_is_delivered_in_the_declared_vintages_with_the_declared_retrieval_times(self):
        v1, v2, v3 = (v["retrieval_time"] if "retrieval_time" in v else None for v in self.spec["vintages"])
        files = self.files_of("QUOTE", "SYN21_")
        self.assertEqual([m.adjustment_anchor for m in files], [None, None, None])  # no vintage label in the series key: the vintage is the retrieval time (Ruling 0.1 (1.12))
        self.assertEqual([dict(m.request)["start"] for m in files][1:], ["2026-01-09", "2026-01-10"])  # the declared coverage of V2 and V3 (V1 starts at the series' first date)
        self.assertEqual([dict(m.request)["end"] for m in files][:2], ["2026-01-08", "2026-01-09"])
        stamp = lambda m: m.retrieval_time.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
        nyse = self.spec["vintages"][1]["retrieval_time_by_calendar"]["SYN4_NYSE"]
        self.assertEqual([stamp(m) for m in files], [v1, nyse, v3])
        # a series on another calendar takes THAT calendar's V2 instant (SYN22 is on the HK exchange)
        hk = self.files_of("QUOTE", "SYN22_")
        self.assertEqual(stamp(hk[1]), self.spec["vintages"][1]["retrieval_time_by_calendar"]["SYN4_HKEX"])
        # the risk-free series and the benchmark follow their own calendars; the ECB file per vintage holds every currency
        rf = self.files_of("RISK_FREE", "SYN4_UST13_USD_")
        self.assertEqual((len(rf), stamp(rf[1])), (3, self.spec["vintages"][1]["retrieval_time_by_calendar"]["SYN4_RF_USD"]))
        fx = self.files_of("FX", "fx_")
        self.assertEqual((len(fx), stamp(fx[1])), (3, self.spec["vintages"][1]["retrieval_time_by_calendar"]["SYN4_ECB"]))
        self.assertTrue(self.files_of("BENCHMARK", "SYN4_BM_US_TR_"))

    def test_every_file_is_retrieved_at_or_after_the_rows_it_holds_so_no_series_is_contradicted(self):
        # market-data Ruling 3.1's after-retrieval test (V0): a price lookup over the whole data finds no SERIES_CONTRADICTED note, at any date of any listing
        market, ids = self.r.market, self.r.ids
        for listing_id in market.listings:
            for day in (D(2023, 6, 2), D(2025, 6, 2), D(2026, 1, 8), D(2026, 1, 9), D(2026, 1, 12), D(2026, 3, 31)):
                lookup = market.store.quote_on(ids(listing_id), day, market.conventions)
                self.assertFalse(any("SERIES_CONTRADICTED" in n for n in lookup.lineage_notes), (listing_id, day, lookup.lineage_notes))
                disputed = {D.fromisoformat(o["date"]) for s in g.load_part(3)["market_data"]["prices"]["series"] if s["listing_id"] == listing_id and s.get("second_source")
                            for o in s["second_source"]["price_overrides"]}  # the days two price sources DISAGREE on (part 3 (1.6)): no price is used, by design (market-data Ruling 4.3)
                self.assertEqual(lookup.outcome.value, "NO_SELECTION" if day in disputed else "FOUND", (listing_id, day))

    def test_the_vintages_of_a_series_are_one_series_with_every_row_and_every_file_cited(self):
        market, ids = self.r.market, self.r.ids
        series = market.store.quotes(ids("c4000000-0000-4000-8000-000000000021"), D(2026, 1, 5), D(2026, 1, 14))
        self.assertEqual([r.observation.value_date.isoformat() for r in series.readings], ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14"])
        self.assertEqual(len(series.consumed), 3)  # V1, V2 and V3 are three files of the one series
        rates = market.store.risk_free_series(g.CurrencyCode("USD"), D(2026, 1, 7), D(2026, 1, 13))
        self.assertEqual(rates.outcome.value, "FOUND")
        self.assertEqual([p.value_date.isoformat() for p in rates.series[0].points], ["2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13"])
        self.assertEqual(len(rates.consumed), 3)
        self.assertEqual(market.store.risk_free_on(g.CurrencyCode("USD"), D(2026, 1, 12), market.conventions).outcome.value, "FOUND")

    def test_the_vintage_rows_are_cut_by_date_and_each_row_is_in_exactly_one_file(self):
        plan = g.VintagePlan(self.r.data["market_data"])
        rows = [D(2025, 12, 31) + datetime.timedelta(days=i) for i in range(12)]
        parts = plan.split(rows, lambda d: d, "SYN4_NYSE")
        self.assertEqual([(label, len(part)) for label, part, _t, _c in parts], [("V1", 9), ("V2", 1), ("V3", 2)])  # 12-31 .. 01-08, 01-09, 01-10 .. 01-11
        self.assertEqual(sorted(d for _l, part, _t, _c in parts for d in part), rows)
        # a part that declares none (parts 1 and 2) has ONE file per series
        single = g.VintagePlan({}).split(rows, lambda d: d, "X")
        self.assertEqual([(label, len(part)) for label, part, _t, _c in single], [(None, 12)])


class IdentityTests(unittest.TestCase):
    """The structural assertions of part 1 (S-2, S-3): RS-1, RD-1, RD-2, RD-3, and the subsequence property RD-4, over every drawdown the parts assert."""

    def test_rs1_and_the_series_identities_run_and_pass_in_every_checked_call(self):
        r = runner_for(1)
        (p1,) = [p for p in r.data["portfolios"] if p["name"].startswith("P1 ")]
        a = p1["assertions"][0]
        res = r.risk(p1, a, a["expect"][2], ("risk_volatility", "risk_max_drawdown"))
        rows = dict(res.manifest.identities)
        self.assertEqual({k: rows[k] for k in ("I-10", "I-11", "RD-1", "RD-3")}, {"I-10": "PASS", "I-11": "PASS", "RD-1": "PASS", "RD-3": "PASS"})
        self.assertEqual(res.manifest.series.identities_run, ("I-10", "I-11"))

    def test_rd1_to_rd3_hold_for_every_asserted_drawdown(self):
        for number in (1, 3):
            r = runner_for(number)
            for p, a, item in g.items(r.data):
                if item["kind"] != "max_drawdown" or item["value"] is None or g.disposition(r.data, p, a, item):
                    continue
                result = r.series(p, a, item)
                returns = [pr.exact for pr in result.series.periods]
                dd = stats.max_drawdown(returns)
                self.assertEqual(dd.value, Fraction(item["exact"]), (a["id"], item["frequency"]))
                wealth = dd.wealth
                # RD-2: no pair of grid points has a TWR below the value (brute force)
                self.assertTrue(all(wealth[k] / wealth[j] - 1 >= dd.value for j in range(len(wealth)) for k in range(j + 1, len(wealth))), a["id"])
                # RD-3
                self.assertLessEqual(dd.value, min([Fraction(0)] + returns))
                # RD-1 (a path independent of the series: the TWR engine over (peak, trough])
                if dd.trough is not None:
                    from performance.engine import compute_twr_between  # noqa: PLC0415

                    twr = compute_twr_between(r.events[p["name"]], r.version(p, a), result.series.boundaries[dd.peak], result.series.boundaries[dd.trough], g.CurrencyCode(p["reporting_currency"]),
                                              r.market.store, r.market.ident, r.market.conventions, r.perf, suppressions=r.suppressions_for(p, r.version(p, a)))
                    self.assertEqual(1 + dd.value, 1 + twr.exact, a["id"])

    def test_the_twr_between_two_dates_is_the_window_twr_of_the_same_engine(self):
        from performance.engine import compute_twr_between, compute_window  # noqa: PLC0415
        from performance.periods import WindowRule, WindowSpec  # noqa: PLC0415

        r = runner_for(1)
        (p1,) = [p for p in r.data["portfolios"] if p["name"].startswith("P1 ")]
        events, version, reporting = r.events[p1["name"]], r.version(p1, p1["assertions"][0]), g.CurrencyCode(p1["reporting_currency"])
        for base, end in ((D(2024, 12, 31), D(2025, 12, 31)), (D(2025, 3, 31), D(2025, 6, 30)), (D(2025, 6, 30), D(2025, 7, 31))):
            via_window = compute_window(events, version, WindowSpec(WindowRule.CUSTOM, None, base), end, reporting, r.market.store, r.market.ident, r.market.conventions, r.perf,
                                        suppressions=()).metrics
            expected = next(m for m in via_window if m.metric_id == "return_twr").exact
            self.assertEqual(compute_twr_between(events, version, base, end, reporting, r.market.store, r.market.ident, r.market.conventions, r.perf, suppressions=()).exact, expected, (base, end))
        with self.assertRaises(ValueError):
            compute_twr_between(events, version, D(2025, 6, 30), D(2025, 6, 30), reporting, r.market.store, r.market.ident, r.market.conventions, r.perf, suppressions=())

    def test_rd4_a_coarser_grid_never_shows_a_deeper_drawdown_on_p2(self):
        r = runner_for(1)
        (p2,) = [p for p in r.data["portfolios"] if p["name"].startswith("P2 ")]
        a = next(a for a in p2["assertions"] if a["id"] == "P2-D1")
        by_frequency = {i["frequency"]: Fraction(i["exact"]) for i in a["expect"] if i["kind"] == "max_drawdown"}
        self.assertEqual(set(by_frequency), {"WEEKLY", "DAILY"})
        self.assertLessEqual(by_frequency["DAILY"], by_frequency["WEEKLY"])
        self.assertEqual(by_frequency["DAILY"], by_frequency["WEEKLY"])  # P2 moves only on Fridays: equal, -1/10


class DeterminismAndReproductionTests(unittest.TestCase):
    def pick(self, number, aid, kind):
        r = runner_for(number)
        for p, a, item in g.items(r.data):
            if a["id"] == aid and item["kind"] == kind:
                return r, p, a, item
        raise AssertionError((aid, kind))

    def test_the_same_question_gives_the_same_bytes(self):
        r, p, a, item = self.pick(1, "P1-S1", "volatility")
        metrics = ("risk_downside_deviation", "risk_max_drawdown", "risk_sharpe", "risk_sortino", "risk_volatility")
        first, second = r.risk(p, a, item, metrics), compute_risk(
            r.events[p["name"]], r.version(p, a), g.spec_of(item["request"]), D.fromisoformat(a["as_of"]), g.Frequency(item["frequency"]), g.CurrencyCode(p["reporting_currency"]), r.market.store, r.market.ident,
            r.market.conventions, r.perf, suppressions=(), risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=r.catalog, portfolio_id=r.ids(p["portfolio_id"]), metrics=metrics)
        self.assertEqual(first.canonical_json(), second.canonical_json())
        self.assertEqual(first.result_digest, second.result_digest)
        self.assertEqual(first.manifest.manifest_id, second.manifest.manifest_id)

    def test_a_result_reproduces_and_each_wrong_input_is_named(self):
        r, p, a, item = self.pick(1, "P1-S1", "sharpe")
        res = r.risk(p, a, item, ("risk_sharpe", "risk_volatility"))
        common = dict(suppressions=(), risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG)
        args = (r.events[p["name"]], r.market.store, r.market.ident, r.market.conventions, r.perf)
        report = reproduce_risk(res.manifest, res.result_digest, *args, **common)
        self.assertEqual((report.status, report.detail), (St.REPRODUCED, ""))
        self.assertEqual(reproduce_risk(res.manifest, None, *args, **common).status, St.RESULT_NOT_COMPARED)  # no digest: nothing was compared, so it is not "reproduced"
        self.assertEqual(reproduce_risk(res.manifest, "0" * 64, *args, **common).status, St.RESULT_DIFFERS)
        shorter = (r.events[p["name"]][:-1],) + args[1:]
        self.assertEqual(reproduce_risk(res.manifest, res.result_digest, *shorter, **common).status, St.LEDGER_DIGEST_MISMATCH)
        other_catalog = g.RiskFreeCatalog("another-catalog", ())
        self.assertEqual(reproduce_risk(res.manifest, res.result_digest, *args, suppressions=(), risk_free_catalog=other_catalog).status, St.CATALOG_MISMATCH)
        self.assertEqual(reproduce_risk(res.manifest, res.result_digest, *args, suppressions=(), risk_free_catalog=None).status, St.CATALOG_MISMATCH)

    def test_every_file_the_question_read_is_cited_and_a_synthetic_result_says_so(self):
        r, p, a, item = self.pick(1, "P1-S1", "sharpe")
        res = r.risk(p, a, item, ("risk_sharpe",))
        self.assertTrue(res.manifest.synthetic)
        self.assertTrue(all(m.synthetic for m in res.metrics))
        self.assertTrue(res.manifest.consumed_files("RISK_FREE"))  # the risk-free file
        self.assertTrue(res.manifest.consumed_files("SERIES"))
        self.assertEqual(res.manifest.consumed_files("BENCHMARK"), ())
        self.assertEqual(res.manifest.registry_id, "risk/1.11")
        self.assertEqual(len(res.manifest.registry_digest), 64)

    def test_the_benchmark_block_pins_the_selection_and_the_catalog(self):
        r, p, a, item = self.pick(2, "Q1-B1", "benchmark_return")
        res = r.risk(p, a, item, ("benchmark_return",))
        block = res.manifest.benchmark
        self.assertEqual((block.pin["version"], block.pin["state"], block.pin["benchmark_id"]), (1, "IN_FORCE", "SYN4_BM_US_TR"))
        self.assertEqual((block.catalog_id, block.catalog_digest), (r.catalog.catalog_id, r.catalog.digest))
        self.assertTrue(block.consumed)
        args = (r.events[p["name"]], r.market.store, r.market.ident, r.market.conventions, r.perf)
        rows = g.selections_of(p, r.ids)
        ok = reproduce_risk(res.manifest, res.result_digest, *args, suppressions=(), benchmark_catalog=r.catalog, selections=rows)
        self.assertEqual(ok.status, St.REPRODUCED, ok.detail)
        # UAT-03: a log whose latest record at the pinned version differs is another question
        changed = tuple(rows[:0]) + (rows[1],) + tuple(rows[1:])
        self.assertEqual(reproduce_risk(res.manifest, res.result_digest, *args, suppressions=(), benchmark_catalog=r.catalog, selections=rows[1:]).status, St.SELECTION_MISMATCH)
        self.assertEqual(reproduce_risk(res.manifest, res.result_digest, *args, suppressions=(), benchmark_catalog=None, selections=rows).status, St.CATALOG_MISMATCH)
        del changed

    def test_the_result_digest_is_the_same_under_every_hash_seed(self):
        # a set or a dict iterated into a result would show here: three interpreters with three hash seeds
        import os  # noqa: PLC0415
        import subprocess  # noqa: PLC0415

        code = (
            "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
            "import cp4_golden_kit as g\n"
            "r = g.shared_runner(1)\n"
            "p = [p for p in r.data['portfolios'] if p['name'].startswith('P1 ')][0]\n"
            "a = p['assertions'][0]\n"
            "item = [i for i in a['expect'] if i['kind'] == 'volatility'][0]\n"
            "res = r.risk(p, a, item, ('risk_downside_deviation', 'risk_max_drawdown', 'risk_sharpe', 'risk_sortino', 'risk_volatility'))\n"
            "print(res.result_digest, res.manifest.manifest_id)\n" % (str(Path(__file__).resolve().parents[2] / "src"), str(Path(__file__).resolve().parent)))
        seen = set()
        for seed in ("0", "1", "4242"):
            out = subprocess.run([sys.executable, "-c", code], env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True, timeout=300)
            self.assertEqual(out.returncode, 0, out.stderr[-800:])
            seen.add(out.stdout.strip())
        self.assertEqual(len(seen), 1, seen)
        r, p, a, item = self.pick(1, "P1-S1", "volatility")
        here = r.risk(p, a, item, ("risk_downside_deviation", "risk_max_drawdown", "risk_sharpe", "risk_sortino", "risk_volatility"))
        self.assertEqual(seen, {f"{here.result_digest} {here.manifest.manifest_id}"})

    def test_json_of_a_result_has_no_float(self):
        r, p, a, item = self.pick(1, "P1-S1", "volatility")
        text = r.risk(p, a, item, ("risk_volatility",)).canonical_json()
        def refuse(token):
            raise AssertionError(f"a float token {token!r} in a canonical result")

        self.assertIsInstance(json.loads(text, parse_float=refuse), dict)  # every number is a string or an integer


if __name__ == "__main__":
    unittest.main()
