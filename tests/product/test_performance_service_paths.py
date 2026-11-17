"""CP3f: gains and attribution through `performance_service`, behind the same gates as the window entry: the synthetic-M refusal, detection always run (`F8B_DRY_RUN`, read-only), `DETECTION_POLICY_UNMATCHED`
and the `M_t` rule for Current mode. A refusal is an explicit state with no number; `reproduce` re-asks these manifests (Current mode included)."""

import dataclasses
import datetime
import inspect
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import performance_kit as pk  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402
import test_performance_recheck as rc  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.ledger import EventType  # noqa: E402
from performance import engine  # noqa: E402
from performance.manifest import ReproductionStatus  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402
from performance_service import service as svc  # noqa: E402

D, F = datetime.date, Fraction
USD = mp.USD
SINCE = WindowSpec(WindowRule.SINCE_INCEPTION)
CUSTOM = WindowSpec(WindowRule.CUSTOM, None, D(2025, 1, 31))
NOBODY = f8b.ConfirmationPolicy(frozenset({"nobody.feed"}), frozenset({"nobody.filing"}))


def entries(L, port, policy=ca.POLICY):
    """Both new entries over the pinned ledger, as `(name, result)`."""
    with rc.pinned(L):
        yield "gains", svc.compute_gains_for_portfolio(None, ca.PORTFOLIO, D(2025, 2, 3), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=policy)
        yield "attribution", svc.compute_attribution_for_portfolio(None, ca.PORTFOLIO, CUSTOM, D(2025, 2, 3), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=policy)


class GateTests(unittest.TestCase):
    def test_a_synthetic_market_data_version_is_refused_with_an_explicit_state_and_no_number(self):
        L = mp.base_ledger()
        for name, port in (("synthetic evidence", mp.market("synthetic", real_quotes=True)), ("synthetic quotes", mp.market("real")), ("no evidence", mp.market(None))):
            for entry, res in entries(L, port):
                (m,) = res.metrics
                self.assertEqual((m.result.value, m.result.sufficiency_state.value), (None, "INSUFFICIENT_DATA"), (name, entry))
                self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, m.details, (name, entry))
                self.assertTrue(res.manifest.synthetic and m.synthetic)
                self.assertEqual(res.manifest.split_detection, "F8B_DRY_RUN")
            # the engine called directly stays allowed and says synthetic
            direct = engine.compute_gains(L.rows, L.version, D(2025, 2, 3), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=())
            self.assertTrue(direct.manifest.synthetic)

    def test_a_port_that_cannot_say_whether_it_is_synthetic_is_treated_as_synthetic(self):
        L = mp.base_ledger()
        for entry, res in entries(L, rc._Hidden(mp.market(None, real_quotes=True))):
            self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, res.metrics[0].details, entry)

    def test_a_port_that_says_it_is_not_synthetic_but_whose_data_are_is_refused_at_the_finish(self):
        L = mp.base_ledger()
        for entry, res in entries(L, rc._Lying(mp.market(None))):  # the quotes are synthetic; the wrapper lies
            (m,) = res.metrics
            self.assertEqual((m.result.value, m.result.sufficiency_state.value), (None, "INSUFFICIENT_DATA"), entry)
            self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, m.details, entry)

    def test_a_policy_that_names_no_source_of_m_is_refused_and_is_cited(self):
        L = mp.base_ledger()
        for entry, res in entries(L, mp.market("real", real_quotes=True), NOBODY):
            (m,) = res.metrics
            self.assertEqual((m.result.value, m.result.sufficiency_state.value), (None, "INSUFFICIENT_DATA"), entry)
            self.assertIn(svc.DETECTION_POLICY_UNMATCHED, m.details, entry)
            self.assertEqual(dict(res.manifest.detection_policy)["feed"], "nobody.feed")

    def test_detection_always_runs_and_the_suppression_reaches_gains_and_attribution(self):
        L = mp.base_ledger()  # the corroborated 4:1 split is not in the ledger: the position is suppressed from 02-03
        got = dict(entries(L, mp.market("real", real_quotes=True)))
        for entry, res in got.items():
            self.assertEqual(res.manifest.split_detection, "F8B_DRY_RUN", entry)
            self.assertEqual(len(res.manifest.split_suppressions_digest), 64)
        ug = [m for m in got["gains"].metrics if m.metric_id == "unrealized_gain" and m.view == "REPORTING"]
        self.assertEqual([(m.result.value, m.result.sufficiency_state.value, m.result.reason_code.value) for m in ug], [(None, "INSUFFICIENT_DATA", "SOURCE_CONFLICT")])
        self.assertEqual({m.result.reason_code.value for m in got["attribution"].metrics if m.metric_id in ("attribution_money", "attribution_return")}, {"SOURCE_CONFLICT"})
        sa = [m for m in got["gains"].metrics if m.metric_id == "since_acquisition"]
        self.assertEqual([(m.result.value, dict(m.lineage)["identity:I-8"]) for m in sa], [(None, "NOT_COMPUTABLE")])  # a suppressed lot has no parts to relate: not FAIL, not PASS
        self.assertEqual(L.version, 2)  # the dry run appended nothing

    def test_no_new_entry_has_a_suppressions_parameter_and_the_policy_has_no_default(self):
        for entry in (svc.compute_gains_for_portfolio, svc.compute_attribution_for_portfolio, svc.compute_gains_current_for_portfolio, svc.compute_attribution_current_for_portfolio):
            names = inspect.signature(entry).parameters
            self.assertNotIn("suppressions", names)
            self.assertEqual(names["policy"].default, inspect.Parameter.empty)

    def test_a_real_market_is_not_refused_and_the_numbers_equal_the_engines_over_the_same_detection(self):
        L = mp.base_ledger()
        port = mp.market(None, real_quotes=True)
        got = dict(entries(L, port, ca.POLICY))
        self.assertNotIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, {d for m in got["gains"].metrics for d in m.details})
        direct = engine.compute_gains(L.rows, L.version, D(2025, 2, 3), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=(), detection="F8B_DRY_RUN",
                                      detection_policy=svc.policy_reference(ca.POLICY), portfolio_id=ca.PORTFOLIO)
        self.assertEqual(got["gains"].result_digest, direct.result_digest)


class CurrentModeTests(unittest.TestCase):
    UTC = datetime.timezone.utc

    def run_at(self, instant, which):
        L = mp.base_ledger()
        market_at = rc.ProbeMarketAt(rc.CurrentModeDetectionTests().readings())
        with rc.pinned(L):
            if which == "gains":
                return svc.compute_gains_current_for_portfolio(None, ca.PORTFOLIO, instant, USD, mp.Ident(), market_at, mp.PERF, policy=ca.POLICY), L, market_at
            return svc.compute_attribution_current_for_portfolio(None, ca.PORTFOLIO, instant, CUSTOM, USD, mp.Ident(), market_at, mp.PERF, policy=ca.POLICY), L, market_at

    def test_detection_over_m_t_sees_only_the_files_retrieved_by_t_for_both_entries(self):
        early_t, late_t = datetime.datetime(2025, 2, 6, 23, 0, tzinfo=self.UTC), datetime.datetime(2025, 2, 11, 23, 0, tzinfo=self.UTC)
        for which in ("gains", "attribution"):
            early, _L, _m = self.run_at(early_t, which)
            late, _L, _m = self.run_at(late_t, which)
            self.assertEqual((early.manifest.as_of_rule, early.manifest.instant), ("D_c(t)", early_t))
            self.assertEqual(early.manifest.excluded_files, tuple(sorted({ca.FEED_SHA, ca.FILING_SHA})), which)  # t, M and the excluded hashes are cited
            self.assertEqual(late.manifest.excluded_files, (), which)
            self.assertNotEqual(late.manifest.split_suppressions_digest, early.manifest.split_suppressions_digest, which)
        early, _L, _m = self.run_at(early_t, "gains")
        late, _L, _m = self.run_at(late_t, "gains")
        pick = lambda res: [m for m in res.metrics if m.metric_id == "unrealized_gain" and m.view == "REPORTING"]  # noqa: E731
        self.assertEqual(pick(early)[0].result.sufficiency_state.value, "AVAILABLE")  # nothing was known at t
        self.assertEqual(pick(late)[0].result.reason_code.value, "SOURCE_CONFLICT")  # known by t

    def test_a_current_mode_manifest_is_reproduced_for_both_entries(self):
        t = datetime.datetime(2025, 2, 11, 23, 0, tzinfo=self.UTC)
        for which in ("gains", "attribution"):
            res, L, market_at = self.run_at(t, which)
            view = market_at.view(t)
            sup = svc._detect(L.rows, L.version, ca.PORTFOLIO, view.port, mp.Ident(), view.calendars, ca.POLICY)
            again = engine.reproduce(res.manifest, res.result_digest, L.rows, market_at.parent, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=sup, market_at=market_at)
            self.assertEqual(again.status, ReproductionStatus.REPRODUCED, (which, again.detail))
            wrong = engine.reproduce(res.manifest, "0" * 64, L.rows, market_at.parent, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=sup, market_at=market_at)
            self.assertEqual(wrong.status, ReproductionStatus.RESULT_DIFFERS)

    def test_a_synthetic_m_t_is_refused_in_current_mode_too(self):
        L = mp.base_ledger()

        class Synthetic(rc.ProbeMarketAt):
            def view(self, instant):
                v = super().view(instant)
                return dataclasses.replace(v, port=mp.market(None))  # synthetic quotes

        t = datetime.datetime(2025, 2, 11, 23, 0, tzinfo=self.UTC)
        with rc.pinned(L):
            for res in (svc.compute_gains_current_for_portfolio(None, ca.PORTFOLIO, t, USD, mp.Ident(), Synthetic(rc.CurrentModeDetectionTests().readings()), mp.PERF, policy=ca.POLICY),
                        svc.compute_attribution_current_for_portfolio(None, ca.PORTFOLIO, t, CUSTOM, USD, mp.Ident(), Synthetic(rc.CurrentModeDetectionTests().readings()), mp.PERF,
                                                                      policy=ca.POLICY)):
                self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, res.metrics[0].details)


class ReproduceGainsAndAttributionTests(unittest.TestCase):
    def test_every_golden_style_manifest_kind_is_reproduced_and_a_gains_manifest_is_not_mistaken_for_a_window(self):
        L = mp.base_ledger()
        port = mp.market(None, real_quotes=True)
        gains = engine.compute_gains(L.rows, L.version, D(2025, 2, 3), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=())
        attr = engine.compute_attribution(L.rows, L.version, CUSTOM, D(2025, 2, 3), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=())
        for res in (gains, attr):
            again = engine.reproduce(res.manifest, res.result_digest, L.rows, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=())
            self.assertEqual(again.status, ReproductionStatus.REPRODUCED, again.detail)
            self.assertEqual(engine.reproduce(res.manifest, None, L.rows, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=()).status,
                             ReproductionStatus.RESULT_NOT_COMPARED)  # never reported as reproduced


if __name__ == "__main__":
    unittest.main()
