"""CP4c: the risk engine's entry (`risk/engine.py`) and its manifest (`risk/manifest.py`): the request checks, the benchmark selection paths (UAT-03, Ruling 5.6), the risk-free catalog gate (Ruling 4.6), the Risk Manifest
and `reproduce_risk` naming each wrong input.

The market is the Quant's part 2 (synthetic). The unavailable-benchmark forms are the Quant's (`Q1-U2` to `Q1-U5`, `Q4-C0`): the benchmark-relative metrics are the next increment, but the benchmark's own return
is blocked by the same conditions, so its state, reason and detail are asserted against what the Quant asserts for the relative metrics of the same assertion.
"""

import dataclasses
import datetime
import json
import sys
import unittest
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp4_golden_kit as g  # noqa: E402

from domain.currency import CurrencyCode  # noqa: E402
from performance.inputs import SuppressionInput  # noqa: E402
from performance.series import ExplicitBoundaries, Frequency, MaxAvailable  # noqa: E402
from product_contract.vocabulary import SufficiencyState as SS  # noqa: E402
from risk import engine as E  # noqa: E402
from risk import states as S  # noqa: E402
from risk.manifest import RiskReproductionStatus as St  # noqa: E402
from risk.registry import load_registry  # noqa: E402
from risk.risk_free import PeriodRate, refuse_unadmitted  # noqa: E402
from domain.catalogs import RiskFreeCatalog, parse_benchmark_catalog, parse_risk_free_catalog  # noqa: E402

D = datetime.date
BENCHMARK_DETAILS = {"NO_BENCHMARK_SELECTED", "BENCHMARK_SERIES_UNAVAILABLE", "BENCHMARK_NOT_TOTAL_RETURN", "BENCHMARK_NOT_COVERING_WINDOW", "BENCHMARK_STALE"}


def part2():
    r = g.shared_runner(2)
    (q1,) = [p for p in r.data["portfolios"] if p["name"].startswith("Q1 ")]
    return r, q1


def assertion(portfolio, aid):
    return next(a for a in portfolio["assertions"] if a["id"] == aid)


def one_item(a, kind, **match):
    return next(i for i in a["expect"] if i["kind"] == kind and all(i["request"].get(k) == v for k, v in match.items()))


class RequestTests(unittest.TestCase):
    def call(self, **kw):
        r, q1 = part2()
        a = assertion(q1, "Q1-B1")
        item = one_item(a, "benchmark_return")
        args = dict(suppressions=(), risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=r.catalog, selections=g.selections_of(q1, r.ids), selection_version=1,
                    portfolio_id=r.ids(q1["portfolio_id"]), metrics=("benchmark_return",))
        args.update(kw)
        return E.compute_risk(r.events[q1["name"]], r.version(q1, a), g.spec_of(item["request"]), D(2026, 1, 2), Frequency.WEEKLY, CurrencyCode("USD"), r.market.store, r.market.ident,
                              r.market.conventions, r.perf, **args)

    def test_a_metric_that_is_not_built_is_refused_loudly_never_dropped(self):
        for metric in ("risk_not_a_metric", "risk_value_at_risk"):  # the relative metrics are built (CP4d); anything else is refused, never dropped
            with self.assertRaises(ValueError, msg=metric):
                self.call(metrics=(metric,))
        with self.assertRaises(ValueError):
            self.call(metrics=())

    def test_a_rate_metric_needs_the_catalog_and_a_benchmark_metric_needs_the_catalog_and_the_portfolio(self):
        with self.assertRaises(ValueError):
            self.call(metrics=("risk_sharpe",), risk_free_catalog=None)
        with self.assertRaises(ValueError):
            self.call(benchmark_catalog=None)
        with self.assertRaises(ValueError):
            self.call(portfolio_id=None)
        self.call(metrics=("risk_volatility",), risk_free_catalog=None, benchmark_catalog=None, portfolio_id=None)  # a metric that needs neither needs neither

    def test_the_metrics_are_returned_in_metric_id_order_and_the_manifest_lists_what_was_asked(self):
        res = self.call(metrics=("risk_volatility", "benchmark_return", "risk_max_drawdown"))
        self.assertEqual([m.metric_id for m in res.metrics], ["benchmark_return", "risk_max_drawdown", "risk_volatility"])
        self.assertEqual(res.manifest.metrics, ("benchmark_return", "risk_max_drawdown", "risk_volatility"))
        self.assertTrue(all(m.manifest_id == res.manifest.manifest_id for m in res.metrics))

    def test_the_default_is_every_metric_built(self):
        r, q1 = part2()
        a = assertion(q1, "Q1-B1")
        res = E.compute_risk(r.events[q1["name"]], r.version(q1, a), g.spec_of({"rule": "TRAILING_MONTHS", "months": 12}), D(2026, 1, 2), Frequency.WEEKLY, CurrencyCode("USD"), r.market.store, r.market.ident,
                             r.market.conventions, r.perf, suppressions=(), risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=r.catalog, selections=g.selections_of(q1, r.ids), selection_version=1,
                             portfolio_id=r.ids(q1["portfolio_id"]))
        self.assertEqual(tuple(m.metric_id for m in res.metrics), E.COMPUTABLE)

    def test_an_explicit_grid_is_the_callers_and_its_id_is_in_the_manifest(self):
        res = self.call(metrics=("risk_volatility",), boundary_rule=ExplicitBoundaries((D(2025, 1, 10), D(2025, 1, 17), D(2025, 1, 24)), rule_id="test-grid"))
        self.assertEqual((res.manifest.boundary_rule_id, res.metric("risk_volatility").observation_count), ("test-grid", 2))

    def test_verify_identities_off_runs_no_reconciliation_and_says_so(self):
        on, off = self.call(metrics=("risk_max_drawdown",)), self.call(metrics=("risk_max_drawdown",), verify_identities=False)
        self.assertTrue({"I-10", "I-11", "RD-3"} <= {k for k, _v in on.manifest.identities})
        self.assertEqual(off.manifest.identities, (("RD-3", "PASS"),))  # RD-3 is arithmetic on the series itself and always runs; RD-1 (a second TWR) and I-10, I-11 are the opt-out
        self.assertEqual((on.manifest.verify_identities, off.manifest.verify_identities), (True, False))
        self.assertNotEqual(on.manifest.manifest_id, off.manifest.manifest_id)
        self.assertEqual(on.metric("risk_max_drawdown").exact, off.metric("risk_max_drawdown").exact)

    def test_the_engine_id_is_in_the_manifest(self):
        self.assertEqual(self.call().manifest.risk_engine_id, E.RISK_ENGINE_ID)


class SelectionPathTests(unittest.TestCase):
    """UAT-03 and Ruling 5.6: the selection in force at the pinned version, never substituted; each unavailable form is named."""

    def compute(self, aid, item):
        r, q1 = part2()
        a = assertion(q1, aid)
        return r.risk(q1, a, dict(item, request=item["request"]), ("benchmark_return",)).metric("benchmark_return"), a

    def test_every_unavailable_benchmark_form_gives_missing_benchmark_with_the_quants_detail(self):
        for aid, kind in (("Q1-U2", "active_return"), ("Q1-U3", "active_return"), ("Q1-U4", "active_return"), ("Q1-U5", "active_return")):
            r, q1 = part2()
            a = assertion(q1, aid)
            item = next(i for i in a["expect"] if i["kind"] == kind and i["state"] == "INSUFFICIENT_DATA")
            m = r.risk(q1, a, item, ("benchmark_return",)).metric("benchmark_return")
            self.assertEqual((m.state, m.result.reason_code.value, m.value), (SS.INSUFFICIENT_DATA, "MISSING_BENCHMARK", None), aid)
            self.assertEqual(sorted(set(m.details) & BENCHMARK_DETAILS), sorted(set(item["details_include"]) & BENCHMARK_DETAILS), aid)
            expected = a["benchmark_expected"]
            ref = m.benchmark
            self.assertEqual({k: getattr(ref, k) for k in expected if hasattr(ref, k)}, expected, aid)

    def test_no_selection_at_version_zero_and_nothing_is_substituted(self):
        r, _q1 = part2()
        (q4,) = [p for p in r.data["portfolios"] if p["name"].startswith("Q4 ")]
        a = assertion(q4, "Q4-C0")
        item = a["expect"][0]
        m = r.risk(q4, a, item, ("benchmark_return",)).metric("benchmark_return")
        self.assertEqual((m.state, m.details, m.benchmark.benchmark_id, m.benchmark.selection_id, m.benchmark.selection_version), (SS.INSUFFICIENT_DATA, ("NO_BENCHMARK_SELECTED",), None, None, 0))
        self.assertIsNone(m.benchmark.return_basis)  # nothing is invented for a benchmark that was not chosen

    def test_a_cleared_selection_names_the_clearing_record(self):
        r, q1 = part2()
        a = assertion(q1, "Q1-U2")
        res = r.risk(q1, a, one_item(a, "volatility"), ("benchmark_return", "risk_volatility"))
        m = res.metric("benchmark_return")
        self.assertEqual((m.benchmark.benchmark_id, m.benchmark.selection_id, m.benchmark.selection_seq, m.details), (None, "f4201000-0000-4000-8000-000000000002", 2, ("NO_BENCHMARK_SELECTED",)))
        self.assertEqual(res.manifest.benchmark.pin["state"], "CLEARED")
        vol = res.metric("risk_volatility")
        self.assertEqual((vol.state, vol.benchmark), (SS.LIMITED, None))  # a metric that does not use the benchmark is unaffected and names none

    def test_a_window_the_series_covers_is_available_while_the_year_it_does_not_is_not(self):
        r, q1 = part2()
        a = assertion(q1, "Q1-U5")
        late = one_item(a, "active_return", rule="CUSTOM")
        m = r.risk(q1, a, late, ("benchmark_return",)).metric("benchmark_return")
        # the Quant's decomposition view: the benchmark return of (2025-07-11, 2026-01-02] is 0.010101010101 = 1/99
        self.assertEqual((m.state, m.exact, m.value), (SS.AVAILABLE, F(1, 99), Decimal(late["decomposition_view"]["benchmark_return"])))
        self.assertEqual((m.benchmark.benchmark_id, m.benchmark.return_basis), ("SYN4_BM_US_TR_LATE", "TOTAL_RETURN_GROSS"))

    def test_the_result_names_the_series_it_read_not_the_catalogs_claim_cp4m_3(self):
        r, q1 = part2()
        a = assertion(q1, "Q1-B1")
        item = one_item(a, "benchmark_return")
        ok = r.risk(q1, a, item, ("benchmark_return",)).metric("benchmark_return")
        self.assertEqual((ok.state, ok.benchmark.source_id, ok.benchmark.synthetic), (SS.AVAILABLE, "mock.synthetic", True))  # the series' own lineage, which the entry equals
        levels = dict(ok.intermediates)  # CP4M-6: the two translated levels the return is the ratio of
        self.assertEqual(levels["level_gn"] / levels["level_g0"] - 1, ok.exact)
        # the reviewer's demonstration: a catalog claiming a real vendor source and synthetic=false for the same id
        rows = [dict(e.to_obj(), source_id="vendor.real.index", synthetic=False) for e in r.catalog.entries]
        lying = parse_benchmark_catalog(json.dumps({"catalog_id": "lying", "entries": rows}).encode(), allow_synthetic=True)
        res = E.compute_risk(r.events[q1["name"]], r.version(q1, a), g.spec_of(item["request"]), D(2026, 1, 2), Frequency.WEEKLY, CurrencyCode("USD"), r.market.store, r.market.ident, r.market.conventions,
                             r.perf, suppressions=(), benchmark_catalog=lying, selections=g.selections_of(q1, r.ids), selection_version=1, portfolio_id=r.ids(q1["portfolio_id"]), metrics=("benchmark_return",))
        m = res.metric("benchmark_return")
        self.assertEqual((m.state, m.value, m.result.reason_code.value, m.details), (SS.INSUFFICIENT_DATA, None, "MISSING_BENCHMARK", ("BENCHMARK_SERIES_UNAVAILABLE",)))
        ref = m.benchmark
        self.assertEqual((ref.benchmark_id, ref.source_id, ref.synthetic, ref.return_basis, ref.currency, ref.currency_treatment), ("SYN4_BM_US_TR", None, None, None, None, None))  # nothing of the entry is named
        self.assertTrue(res.manifest.benchmark.consumed)  # the file that was read is still cited

    def test_a_translated_benchmark_records_the_untranslated_levels_the_two_rates_and_their_fixing_dates_cp4m_8(self):
        # Q2-T1: an HKD index reported in USD at the ECB fixing; Ruling 9.4 (1.4): L(g_0), L(g_n), L_R(g_0), L_R(g_n), both translation rates and their fixing dates, so the index's own move and the FX move can be told apart
        r = g.shared_runner(2)
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("Q2 ")]
        a = assertion(p, "Q2-T1")
        item = one_item(a, "benchmark_return")
        m = r.risk(p, a, item, ("benchmark_return",)).metric("benchmark_return")
        self.assertEqual((m.state, m.benchmark.currency, m.benchmark.currency_treatment[:10]), (SS.AVAILABLE, "HKD", "TRANSLATED"))
        inter = dict(m.intermediates)
        self.assertEqual(sorted(inter), ["fixing_date_g0", "fixing_date_gn", "index_level_g0", "index_level_gn", "level_g0", "level_gn", "rate_g0", "rate_gn"])
        self.assertEqual(inter["level_g0"], inter["index_level_g0"] * inter["rate_g0"])  # L_R = L x the translation rate, exactly
        self.assertEqual(inter["level_gn"], inter["index_level_gn"] * inter["rate_gn"])
        self.assertEqual(inter["level_gn"] / inter["level_g0"] - 1, m.exact)
        self.assertEqual((inter["fixing_date_g0"], inter["fixing_date_gn"]), (D(2025, 1, 10), D(2026, 1, 2)))  # the ECB fixing days used at the two grid dates
        # the index's own move and the translated move differ exactly by the FX move between the two fixings
        self.assertEqual(inter["level_gn"] / inter["level_g0"], inter["index_level_gn"] / inter["index_level_g0"] * inter["rate_gn"] / inter["rate_g0"])
        # a benchmark already in the reporting currency has no rate and no fixing: none is invented
        (q1,) = [pp for pp in r.data["portfolios"] if pp["name"].startswith("Q1 ")]
        a1 = assertion(q1, "Q1-B1")
        plain = r.risk(q1, a1, one_item(a1, "benchmark_return"), ("benchmark_return",)).metric("benchmark_return")
        self.assertEqual(sorted(dict(plain.intermediates)), ["index_level_g0", "index_level_gn", "level_g0", "level_gn"])
        self.assertEqual(dict(plain.intermediates)["index_level_g0"], dict(plain.intermediates)["level_g0"])

    def test_the_selection_changing_changes_the_pin_and_so_the_question(self):
        r, q1 = part2()
        a1, a2 = assertion(q1, "Q1-B1"), assertion(q1, "Q1-U2")
        first = r.risk(q1, a1, one_item(a1, "benchmark_return"), ("benchmark_return",))
        second = r.risk(q1, a2, one_item(a2, "volatility"), ("benchmark_return",))
        self.assertNotEqual(first.manifest.benchmark.pin, second.manifest.benchmark.pin)
        self.assertNotEqual(first.manifest.manifest_id, second.manifest.manifest_id)

    def test_a_window_refused_for_history_still_names_the_selection_and_reads_nothing(self):
        r, q1 = part2()
        a = assertion(q1, "Q1-B1")
        res = E.compute_risk(r.events[q1["name"]], r.version(q1, a), g.spec_of({"rule": "TRAILING_MONTHS", "months": 60}), D(2026, 1, 2), Frequency.WEEKLY, CurrencyCode("USD"), r.market.store, r.market.ident,
                             r.market.conventions, r.perf, suppressions=(), benchmark_catalog=r.catalog, selections=g.selections_of(q1, r.ids), selection_version=1, portfolio_id=r.ids(q1["portfolio_id"]),
                             metrics=("benchmark_return", "risk_volatility"))
        m = res.metric("benchmark_return")
        self.assertEqual((m.state, m.window, m.benchmark.benchmark_id, res.manifest.benchmark.consumed), (SS.INSUFFICIENT_DATA, None, "SYN4_BM_US_TR", ()))
        self.assertEqual(m.details, ("WINDOW_BEFORE_INCEPTION",))


class SelectionCorrectionTests(unittest.TestCase):
    """CP4M-4 (Ruling 5.6 (1.4)) through the engine: a pin that cuts a correction pair is refused, never answered; a replacement's pin records the position it took."""

    def run_at(self, version, truncate=False):
        r = g.shared_runner(3)
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("R13 ")]
        a = assertion(p, "R13-V8")
        rows = g.selections_of(p, r.ids)
        if truncate:  # exactly what `load_selections(conn, portfolio, version)` returns: nothing above the version
            rows = tuple(s for s in rows if s.selection_seq <= version)
        return E.compute_risk(r.events[p["name"]], r.version(p, a), g.spec_of({"rule": "CUSTOM", "base": "2025-01-08"}), D(2026, 1, 2), Frequency.WEEKLY, CurrencyCode("USD"), r.market.store,
                              r.market.ident, r.market.conventions, r.perf, suppressions=(), benchmark_catalog=r.catalog, selections=rows, selection_version=version,
                              portfolio_id=r.ids(p["portfolio_id"]), metrics=("benchmark_return",))

    def test_a_log_truncated_at_a_version_that_cuts_a_pair_is_refused_not_answered_cp4m_9(self):
        # the reviewer's demonstration: only the rows up to v9 (the REVERSAL of seq 6, its replacement is seq 10) used to answer the ETF proxy, a state that never existed
        from domain.benchmark_selection import SelectionVersionNotPinnableError  # noqa: PLC0415

        for version in (7, 9):
            for truncate in (False, True):
                with self.assertRaises(SelectionVersionNotPinnableError, msg=(version, truncate)):
                    self.run_at(version, truncate)
        for version in (8, 10):  # a boundary gives the same pin with or without the rows above it
            self.assertEqual(self.run_at(version, True).manifest.benchmark.pin, self.run_at(version, False).manifest.benchmark.pin)

    def test_a_version_that_cuts_a_correction_pair_is_refused_by_the_engine(self):
        from domain.benchmark_selection import SelectionVersionNotPinnableError  # noqa: PLC0415

        with self.assertRaises(SelectionVersionNotPinnableError):
            self.run_at(7)
        self.assertEqual(self.run_at(8).manifest.benchmark.pin["selection_seq"], 6)  # the whole pair is in: the user's later choice stays in force

    def test_a_replacement_in_force_records_the_position_it_took_and_an_ordinary_record_does_not(self):
        pin10 = self.run_at(10).manifest.benchmark.pin
        self.assertEqual((pin10["selection_seq"], pin10["position"]), (10, 6))
        self.assertNotIn("position", self.run_at(8).manifest.benchmark.pin)


class RiskFreeCatalogGateTests(unittest.TestCase):
    """Ruling 4.6 and `RISK_FREE.json`: only a catalogued series is a source; a synthetic one is never catalogued and the gate does not apply to it."""

    def rate(self, synthetic, series_id="REAL_SERIES"):
        from performance.states import Valued  # noqa: PLC0415

        return PeriodRate(D(2025, 1, 3), D(2025, 1, 10), D(2025, 1, 3), 0, Valued(SS.AVAILABLE, None, F(7, 10000), ()), (), series_id, (), (), synthetic, series_synthetic=synthetic)

    def catalog(self, *rows):
        return parse_risk_free_catalog(json.dumps({"catalog_id": "rf:test", "entries": list(rows)}).encode())

    ROW = {"currency": "USD", "series_id": "REAL_SERIES", "source_id": "src", "instrument": "SOVEREIGN_BILL", "tenor_days": 91, "quote_type": "SIMPLE_YIELD", "day_count_basis": "365", "unit": "PERCENT",
           "decimals_published": 2, "date_semantics": "d", "calendar_id": "C", "revision_policy": "NOT_REVISED"}

    def test_a_real_series_the_catalog_does_not_admit_is_no_source(self):
        out = refuse_unadmitted((self.rate(False),), self.catalog(), CurrencyCode("USD"))[0]
        self.assertEqual((out.valued.state, out.exact, out.details), (SS.INSUFFICIENT_DATA, None, ("NO_RISK_FREE_SOURCE",)))
        self.assertIsNone(out.valued.reason)

    def test_a_series_whose_own_lineage_is_not_said_is_treated_as_real(self):
        # fail closed: only a series that SAYS it is synthetic is exempt (CP4M-2); None (not said) is not
        from performance.states import Valued  # noqa: PLC0415

        unsaid = PeriodRate(D(2025, 1, 3), D(2025, 1, 10), D(2025, 1, 3), 0, Valued(SS.AVAILABLE, None, F(7, 10000), ()), (), "S", (), (), True)  # release synthetic, series_synthetic default None
        self.assertIsNone(unsaid.series_synthetic)
        self.assertEqual(refuse_unadmitted((unsaid,), self.catalog(), CurrencyCode("USD"))[0].details, ("NO_RISK_FREE_SOURCE",))

    def test_the_admitted_series_passes_and_so_does_a_synthetic_one(self):
        rate = self.rate(False)
        self.assertEqual(refuse_unadmitted((rate,), self.catalog(self.ROW), CurrencyCode("USD")), (rate,))
        synthetic = self.rate(True, "SYN")
        self.assertEqual(refuse_unadmitted((synthetic,), self.catalog(), CurrencyCode("USD")), (synthetic,))

    def test_another_currencys_series_is_never_used(self):
        row = dict(self.ROW, currency="HKD")
        out = refuse_unadmitted((self.rate(False),), self.catalog(row), CurrencyCode("USD"))[0]
        self.assertEqual(out.details, ("NO_RISK_FREE_SOURCE",))

    def test_no_series_in_the_release_is_no_source_through_the_engine_and_volatility_is_unaffected(self):
        r, q1 = part2()
        a = assertion(q1, "Q1-B1")
        item = one_item(a, "beta")
        res = r.risk(q1, a, item, ("risk_volatility", "risk_sharpe", "risk_sortino", "risk_downside_deviation"))
        self.assertEqual(res.metric("risk_volatility").state, SS.LIMITED)
        # part 2's USD portfolio has a risk-free series; make the catalog gate bite by pretending the release is real
        from risk import risk_free as rf  # noqa: PLC0415

        rates = rf.risk_free_rates(r.market.store, CurrencyCode("HKD"), [D(2025, 1, 10), D(2025, 1, 17)], r.market.conventions)  # HKD series exists in part 2 ...
        gated = rf.refuse_unadmitted(tuple(dataclasses.replace(x, synthetic=False, series_synthetic=False) for x in rates), RiskFreeCatalog("none", ()), CurrencyCode("HKD"))
        self.assertTrue(all(x.details == ("NO_RISK_FREE_SOURCE",) for x in gated))  # ... and is not admitted by an empty catalog

    def test_a_real_unadmitted_series_is_no_source_even_in_a_release_that_holds_a_synthetic_file_cp4m_2(self):
        # the reviewer's mixed release: a REAL USD series plus one synthetic file elsewhere (a synthetic HKD series). The release's flag is synthetic (every result is), but the USD series is real and not admitted.
        import test_risk_free_leg as lf  # noqa: PLC0415
        from marketdata import contracts as c  # noqa: PLC0415
        from marketdata.calendars import CalendarSet  # noqa: PLC0415
        from marketdata.manifest import MarketDataRelease  # noqa: PLC0415
        from marketdata.market11 import market11_conventions  # noqa: PLC0415
        from marketdata.store import InMemoryMarketData, RiskFreeEntry  # noqa: PLC0415
        from risk import risk_free as rf  # noqa: PLC0415

        d = lf.fixture()
        (spec,) = d["market_data"]["risk_free"]["series"]
        (cal_spec,) = [x for x in d["market_data"]["calendars"] if x["calendar_id"] == spec["calendar"]]
        real_lineage = dataclasses.replace(lf.lineage(), usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY)
        real = lf.series_for(spec, lineage=real_lineage, licensing=c.LicensingMetadata(c.LicenseStatus.INTERNAL_DEVELOPMENT_ONLY, False))
        other = lf.series_for(spec, series_id="SYN_HKD", currency=CurrencyCode("HKD"))  # synthetic lineage (the helper's default)
        store = InMemoryMarketData(MarketDataRelease(name="mixed", files=(), source_precedence=()),
                                   risk_free=[RiskFreeEntry("real.src", "g1", "ab" * 32, real), RiskFreeEntry("synthetic.riskfree", "g2", "cd" * 32, other)])
        conventions = market11_conventions(CalendarSet([lf.calendar_for(cal_spec)]))
        self.assertTrue(store.contains_synthetic)  # the release flag
        rates = rf.risk_free_rates(store, CurrencyCode("USD"), [D(2025, 1, 3), D(2025, 1, 10), D(2025, 1, 17)], conventions)
        self.assertTrue(all(x.synthetic and x.series_synthetic is False for x in rates))  # release synthetic, series real
        gated = rf.refuse_unadmitted(rates, RiskFreeCatalog("risk_free:1", ()), CurrencyCode("USD"))
        self.assertTrue(all((x.valued.state, x.exact, x.details) == (SS.INSUFFICIENT_DATA, None, ("NO_RISK_FREE_SOURCE",)) for x in gated))
        # the same series, admitted by the catalog, is a source
        admitted = rf.refuse_unadmitted(rates, parse_risk_free_catalog(json.dumps({"catalog_id": "rf:2", "entries": [dict(self.ROW, series_id=spec["series_id"])]}).encode()), CurrencyCode("USD"))
        self.assertTrue(all(x.valued.state is SS.AVAILABLE for x in admitted))


class ManifestAndReproduceTests(unittest.TestCase):
    def setUp(self):
        self.r, self.q1 = part2()
        self.a = assertion(self.q1, "Q1-B1")
        self.item = one_item(self.a, "benchmark_return")
        self.metrics = ("benchmark_return", "risk_sharpe", "risk_volatility")
        self.res = self.r.risk(self.q1, self.a, self.item, self.metrics)
        self.args = (self.r.events[self.q1["name"]], self.r.market.store, self.r.market.ident, self.r.market.conventions, self.r.perf)
        self.kw = dict(suppressions=(), risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=self.r.catalog, selections=g.selections_of(self.q1, self.r.ids))

    def reproduce(self, manifest=None, digest="same", **override):
        kw = dict(self.kw, **override)
        return E.reproduce_risk(manifest or self.res.manifest, self.res.result_digest if digest == "same" else digest, *self.args, **kw)

    def test_it_reproduces(self):
        report = self.reproduce()
        self.assertEqual((report.status, report.detail), (St.REPRODUCED, ""))
        self.assertEqual(report.rerun.result_digest, self.res.result_digest)

    def test_the_manifest_cites_every_input_class(self):
        m = self.res.manifest
        self.assertEqual((m.registry_id, m.frequency, m.request_rule, m.end), ("risk/1.11", "WEEKLY", "CUSTOM", D(2026, 1, 2)))
        self.assertTrue(m.risk_free and m.risk_free.series_id and m.risk_free.consumed)
        self.assertTrue(m.benchmark and m.benchmark.consumed and m.benchmark.entry_digest)
        self.assertEqual(m.consumed_files("ALL"), tuple(sorted(set(m.consumed_files("SERIES")) | set(m.consumed_files("RISK_FREE")) | set(m.consumed_files("BENCHMARK")))))

    def test_each_wrong_input_is_named(self):
        m = self.res.manifest
        sm = m.series
        rep = dataclasses.replace
        cases = {
            St.LEDGER_DIGEST_MISMATCH: dict(manifest=rep(m, series=rep(sm, ledger_digest="0" * 64))),
            St.RELEASE_MISMATCH: dict(manifest=rep(m, series=rep(sm, release_id="1" * 64))),
            St.REGISTRY_MISMATCH: dict(manifest=rep(m, registry_digest="2" * 64)),
            St.SUPPRESSIONS_MISMATCH: dict(suppressions=(SuppressionInput(self.r.ids(self.q1["accounts"][0]["account_id"]), self.r.ids("c4000000-0000-4000-8000-000000000021"), D(2025, 1, 1), None,
                                                                          None, "TEST"),)),
            St.CONVENTION_MISMATCH: dict(manifest=rep(m, series=rep(sm, conventions=sm.conventions[:-1]))),
            St.IDENTITY_MISMATCH: dict(manifest=rep(m, series=rep(sm, identity_digest="3" * 64))),
            St.SOURCE_REGISTRY_MISMATCH: dict(manifest=rep(m, series=rep(sm, source_registry_digest="4" * 64))),
            St.MANIFEST_DIFFERS: dict(manifest=rep(m, numerics=m.numerics + (("x", "y"),))),
            St.RESULT_DIFFERS: dict(digest="5" * 64),
            St.CATALOG_MISMATCH: dict(benchmark_catalog=None),
            St.SELECTION_MISMATCH: dict(selections=g.selections_of(self.q1, self.r.ids)[1:]),
        }
        for status, change in cases.items():
            self.assertEqual(self.reproduce(**change).status, status, status)

    def test_a_different_registry_content_under_the_same_id_is_a_registry_mismatch(self):
        from risk.registry import REGISTRY_FILE  # noqa: PLC0415

        changed = REGISTRY_FILE.read_bytes().replace(b'"insufficient_below": 51', b'"insufficient_below": 52', 1)
        self.assertEqual(self.reproduce(registry=load_registry(changed)).status, St.REGISTRY_MISMATCH)

    def test_a_hidden_input_is_named_per_kind_in_both_directions(self):
        m = self.res.manifest
        rep = dataclasses.replace
        ghost = dataclasses.replace(m.consumed_files("SERIES")[0], file_sha256="9" * 64)
        self.assertEqual(self.reproduce(rep(m, risk_free=rep(m.risk_free, consumed=()))).status, St.RISK_FREE_FILE_NOT_CITED)
        self.assertEqual(self.reproduce(rep(m, risk_free=rep(m.risk_free, consumed=tuple(sorted(m.risk_free.consumed + (ghost,)))))).status, St.RISK_FREE_FILE_NOT_READ)
        self.assertEqual(self.reproduce(rep(m, benchmark=rep(m.benchmark, consumed=()))).status, St.BENCHMARK_FILE_NOT_CITED)
        self.assertEqual(self.reproduce(rep(m, benchmark=rep(m.benchmark, consumed=tuple(sorted(m.benchmark.consumed + (ghost,)))))).status, St.BENCHMARK_FILE_NOT_READ)
        refs = m.series.data_set_refs
        self.assertEqual(self.reproduce(rep(m, series=rep(m.series, data_set_refs=(rep(refs[0], consumed=()),) + refs[1:]))).status, St.FILE_NOT_CITED)
        self.assertEqual(self.reproduce(rep(m, series=rep(m.series, data_set_refs=(rep(refs[0], consumed=tuple(sorted(refs[0].consumed + (ghost,)))),) + refs[1:]))).status, St.FILE_NOT_READ)

    def test_no_expected_digest_is_not_a_reproduction(self):
        self.assertEqual(self.reproduce(digest=None).status, St.RESULT_NOT_COMPARED)

    def test_a_max_available_request_reproduces_too(self):
        res = E.compute_risk(self.args[0], self.r.version(self.q1, self.a), MaxAvailable(), D(2026, 1, 2), Frequency.WEEKLY, CurrencyCode("USD"), self.r.market.store, self.r.market.ident,
                             self.r.market.conventions, self.r.perf, suppressions=(), metrics=("risk_volatility", "risk_max_drawdown"), portfolio_id=self.r.ids(self.q1["portfolio_id"]))
        report = E.reproduce_risk(res.manifest, res.result_digest, *self.args, suppressions=())
        self.assertEqual(report.status, St.REPRODUCED, report.detail)
        self.assertEqual(res.manifest.request_rule, "MAX_AVAILABLE")

    def test_the_catalog_gate_travels_into_the_manifest_as_an_id_and_a_digest(self):
        self.assertEqual((self.res.manifest.benchmark.catalog_id, self.res.manifest.benchmark.catalog_digest), (self.r.catalog.catalog_id, self.r.catalog.digest))
        self.assertEqual(self.res.manifest.risk_free.catalog_digest, g.EMPTY_RISK_FREE_CATALOG.digest)


class AccountScopeTests(unittest.TestCase):
    def test_the_account_scope_is_in_the_manifest_and_reproduces(self):
        r = g.shared_runner(3)
        (p8,) = [p for p in r.data["portfolios"] if p["name"].startswith("R8 ")]
        a = p8["assertions"][0]
        item = next(i for i in a["expect"] if i.get("scope") and i["kind"] == "volatility")
        res = r.risk(p8, a, item, ("risk_volatility",))
        self.assertEqual(res.manifest.series.scope, f"ACCOUNT:{r.ids(item['scope']['account_id'])}")
        args = (r.events[p8["name"]], r.market.store, r.market.ident, r.market.conventions, r.perf)
        report = E.reproduce_risk(res.manifest, res.result_digest, *args, suppressions=r.suppressions_for(p8, r.version(p8, a)), risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG)
        self.assertEqual(report.status, St.REPRODUCED, report.detail)


if __name__ == "__main__":
    unittest.main()
