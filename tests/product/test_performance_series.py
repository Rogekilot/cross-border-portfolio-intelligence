"""CP4b-1: the periodic return series (tech plan 17.3; `performance/series.py`, `engine.compute_return_series`).

Every expected value is derived BY HAND from the inputs shown (a one-listing USD portfolio; no FX), never from the engine's output. The boundary rule is the caller's (`ExplicitBoundaries`): nothing here
asserts what a week is (that is `risk/1.0` P-1). The series is the CP3 segment TWR per period, so the checks are against numbers worked out from prices and flows.

The world. AAPL (XNAS, USD) closes, invented:  03-24 100, 03-25 102, 03-26 101, 03-27 103, 03-28 104, 03-31 105, 04-01 107, 04-02 106, 04-03 108, 04-04 110.
Account A1 on 03-24: DEPOSIT 1000 USD and BUY 10 AAPL for 1000 USD, so cash 0 and V(D) = 10 x close(D).
"""

import dataclasses
import datetime
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402
import performance_kit as pk  # noqa: E402

from domain.ledger import EventType  # noqa: E402
from performance import engine, series as S  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402
from performance.results import WindowUsed  # noqa: E402
from product_contract.vocabulary import SufficiencyState  # noqa: E402

D, F, USD = datetime.date, Fraction, pk.USD
PERF = engine.performance_conventions()
CLOSES = {D(2025, 3, 24): "100", D(2025, 3, 25): "102", D(2025, 3, 26): "101", D(2025, 3, 27): "103", D(2025, 3, 28): "104",
          D(2025, 3, 31): "105", D(2025, 4, 1): "107", D(2025, 4, 2): "106", D(2025, 4, 3): "108", D(2025, 4, 4): "110"}
SINCE = WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 24))


def world(closes=None, **kw):
    probe = x.identity()
    aapl = x.lid(probe, "AAPL", "XNAS")
    readings = [pk.quote(aapl, d, p, USD, "US") for d, p in (CLOSES if closes is None else closes).items()]
    w = pk.World(readings, **kw)
    return w, aapl


def ledger(aapl, extra=()):
    L = pk.Ledger()
    L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 24), USD, amount=L.money("1000", USD))
    L.add(pk.A1, EventType.BUY, D(2025, 3, 24), USD, listing_id=aapl, quantity=Decimal(10), amount=L.money("1000", USD))
    for fn in extra:
        fn(L)
    return L


def run(w, L, boundaries, end=None, spec=SINCE, freq=S.Frequency.WEEKLY, verify=True, **kw):
    """A series on grid points the CALLER chose (`ExplicitBoundaries`: they must lie in the requested window `[B, E]`)."""
    return engine.compute_return_series(
        L.rows, L.version, spec, end or boundaries[-1], freq, S.ExplicitBoundaries(tuple(boundaries)), USD, w.store, w.ident, w.market, PERF,
        suppressions=(), verify_identities=verify, **kw)


def run_grid(w, L, request, end, freq, verify=True, **kw):
    """A series on the real grid of `risk/1.0` Ruling 2.2 (weekdays, Fridays, month-ends)."""
    return engine.compute_return_series(L.rows, L.version, request, end, freq, S.WeekdayFridayMonthEndGrid(), USD, w.store, w.ident, w.market, PERF, suppressions=(),
                                        verify_identities=verify, **kw)


class SpineTests(unittest.TestCase):
    def test_a_flow_free_series_is_the_ratio_of_end_values_per_period(self):
        # periods (03-24, 03-28] and (03-28, 04-04]: 1040/1000 = 26/25 and 1100/1040 = 55/52; product 11/10 = TWR of the whole window (1100/1000)
        w, aapl = world()
        res = run(w, ledger(aapl), [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)])
        s = res.series
        self.assertEqual([p.exact for p in s.periods], [F(1, 25), F(3, 52)])
        self.assertEqual(s.boundary_values[0][1].exact, F(1000))
        self.assertEqual([v.exact for _d, v in s.boundary_values], [F(1000), F(1040), F(1100)])
        self.assertEqual((F(26, 25) * F(55, 52)) - 1, F(1, 10))
        self.assertEqual(dict(res.identities), {"I-10": S.PASS, "I-11": S.PASS})
        self.assertEqual(s.window.frequency, "WEEKLY")
        self.assertEqual(s.assessment.periods, 2)
        self.assertEqual((s.assessment.available, s.assessment.insufficient, s.assessment.zero_capital), (2, 0, 0))
        self.assertTrue(all(p.valued.state is SufficiencyState.AVAILABLE and p.valued.reason is None for p in s.periods))

    def test_the_series_is_the_segment_twr_per_period_and_the_window_twr_links(self):
        # a daily series over (03-24, 03-28]: r_D = close(D)/close(D-1) - 1, and the product is the window TWR 104/100
        w, aapl = world()
        days = [D(2025, 3, 24), D(2025, 3, 25), D(2025, 3, 26), D(2025, 3, 27), D(2025, 3, 28)]
        res = run(w, ledger(aapl), days, freq=S.Frequency.DAILY)
        self.assertEqual([p.exact for p in res.series.periods], [F(102, 100) - 1, F(101, 102) - 1, F(103, 101) - 1, F(104, 103) - 1])
        product = F(1)
        for p in res.series.periods:
            product *= 1 + p.exact
        self.assertEqual(product, F(104, 100))
        self.assertEqual(dict(res.identities)["I-10"], S.PASS)

    def test_a_deposit_inside_a_period_is_neutralised_and_the_linked_product_equals_the_window(self):
        # +500 USD on 04-01 (cash, start of the day). Period 2 (03-28, 04-04]: run (03-28..03-31): 1050/1040; flow day 04-01: V(04-01) / (V(03-31) + 500) = 1570/1550;
        # run (04-01..04-04): 1600/1570. Product 1050 x 1600 / (1040 x 1550) = 420/403, so r2 = 17/403. Whole window: 1050 x 1600 / (1000 x 1550) = 168/155.
        w, aapl = world()
        L = ledger(aapl, [lambda L: L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), USD, amount=L.money("500", USD))])
        res = run(w, L, [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)])
        self.assertEqual([p.exact for p in res.series.periods], [F(1, 25), F(17, 403)])
        self.assertEqual(res.series.periods[1].flow_days, 1)
        self.assertEqual(F(26, 25) * F(420, 403) - 1, F(13, 155))
        self.assertEqual(F(168, 155) - 1, F(13, 155))
        self.assertEqual(dict(res.identities)["I-10"], S.PASS)
        # the same window as ONE period gives the same linked figure: 168/155
        one = run(w, L, [D(2025, 3, 24), D(2025, 4, 4)])
        self.assertEqual(one.series.periods[0].exact, F(13, 155))

    def test_a_boundary_on_the_day_of_a_flow_puts_the_flow_in_the_period_that_ends_there(self):
        # the deposit of 04-01 with a boundary ON 04-01: period (03-28, 04-01] holds it, period (04-01, 04-04] does not
        # (03-28, 04-01]: run (03-28..03-31): 1050/1040; flow: 1570/1550 -> 1050 x 1570 / (1040 x 1550) ; (04-01, 04-04]: 1600/1570. Linked: 1050 x 1600 / (1040 x 1550) = 420/403
        w, aapl = world()
        L = ledger(aapl, [lambda L: L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), USD, amount=L.money("500", USD))])
        res = run(w, L, [D(2025, 3, 28), D(2025, 4, 1), D(2025, 4, 4)], spec=WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 28)))
        p1, p2 = res.series.periods
        self.assertEqual((p1.flow_days, p2.flow_days), (1, 0))
        self.assertEqual(p1.exact, F(1050 * 1570, 1040 * 1550) - 1)
        self.assertEqual(p2.exact, F(1600, 1570) - 1)
        self.assertEqual((1 + p1.exact) * (1 + p2.exact) - 1, F(420, 403) - 1)
        self.assertEqual(dict(res.identities), {"I-10": S.PASS, "I-11": S.PASS})

    def test_each_period_counts_only_the_flow_days_dated_inside_it(self):
        # deposits on 03-27 (period 1) and 04-01 (period 2): one flow day each, not two each, and the dates read are the boundaries plus D-1 and D of each flow day
        w, aapl = world()
        L = ledger(aapl, [lambda L: L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 27), USD, amount=L.money("200", USD)),
                          lambda L: L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), USD, amount=L.money("500", USD))])
        res = run(w, L, [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)])
        self.assertEqual([p.flow_days for p in res.series.periods], [1, 1])
        self.assertEqual(res.series.valuation_dates_read, tuple(sorted({D(2025, 3, 24), D(2025, 3, 26), D(2025, 3, 27), D(2025, 3, 28), D(2025, 3, 31), D(2025, 4, 1), D(2025, 4, 4)})))
        self.assertEqual(dict(res.identities), {"I-10": S.PASS, "I-11": S.PASS})

    def test_the_manifest_lists_the_identities_that_were_run(self):
        w, aapl = world()
        L = ledger(aapl)
        on = run(w, L, [D(2025, 3, 24), D(2025, 4, 4)], verify=True)
        off = run(w, L, [D(2025, 3, 24), D(2025, 4, 4)], verify=False)
        self.assertEqual(on.manifest.identities_run, ("I-10", "I-11"))
        self.assertEqual((off.manifest.identities_run, off.identities), ((), ()))
        default = engine.compute_return_series(L.rows, L.version, SINCE, D(2025, 4, 4), S.Frequency.WEEKLY, S.ExplicitBoundaries((D(2025, 3, 24), D(2025, 4, 4))), USD, w.store, w.ident, w.market, PERF, suppressions=())
        self.assertEqual(default.manifest.identities_run, ("I-10", "I-11"))  # RS-1 runs in every product call unless the caller opts out

    def test_a_missed_session_is_available_with_stale_data_and_the_period_carries_it(self):
        # no close on 03-31: the boundary value of 03-31 uses 03-28 (one missed session): AVAILABLE + STALE_DATA (performance/1.1 Ruling 1.4). V(03-31) = 1040
        closes = {d: p for d, p in CLOSES.items() if d != D(2025, 3, 31)}
        w, aapl = world(closes)
        res = run(w, ledger(aapl), [D(2025, 3, 24), D(2025, 3, 31), D(2025, 4, 4)])
        p1, p2 = res.series.periods
        self.assertEqual((p1.exact, p2.exact), (F(1040, 1000) - 1, F(1100, 1040) - 1))
        self.assertIs(p1.valued.state, SufficiencyState.AVAILABLE)
        self.assertEqual((p1.valued.reason, p2.valued.reason), ("STALE_DATA", "STALE_DATA"))
        self.assertEqual((res.series.assessment.available, res.series.assessment.available_stale), (0, 2))
        self.assertEqual(res.series.assessment.freshness.summary, "STALE")
        self.assertEqual(dict(res.identities)["I-10"], S.PASS)

    def test_an_insufficient_period_has_no_number_and_the_others_are_unaffected(self):
        # closes stop after 03-28: the boundary 04-04 has five missed sessions, so the value is withheld (Ruling 1.4/P22) and period 2 is INSUFFICIENT_DATA with no value
        closes = {d: p for d, p in CLOSES.items() if d <= D(2025, 3, 28)}
        w, aapl = world(closes)
        res = run(w, ledger(aapl), [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)])
        p1, p2 = res.series.periods
        self.assertEqual(p1.exact, F(1, 25))
        self.assertIsNone(p2.exact)
        self.assertIs(p2.valued.state, SufficiencyState.INSUFFICIENT_DATA)
        self.assertTrue(p2.valued.causes)
        a = res.series.assessment
        self.assertEqual((a.available, a.insufficient, a.first_insufficient_end, a.last_insufficient_end), (1, 1, D(2025, 4, 4), D(2025, 4, 4)))
        # I-10 checks the run of exact periods (period 1 only) and passes; the failed period is not hidden by it
        self.assertEqual(dict(res.identities)["I-10"], S.PASS)
        self.assertEqual(res.series.boundary_values[-1][1].state, SufficiencyState.INSUFFICIENT_DATA)

    def zero_capital_world(self):
        # 03-24 deposit 1000 and 03-25 withdraw all 1000 (cash only, no buy); 03-27 deposit 500. Grid points 03-24, 03-25, 03-26, 03-28.
        # (03-24, 03-25]: withdrawal at the end of 03-25: (V(03-25) + 1000) / (V(03-24) + 0) = (0 + 1000) / 1000 = 1: capital for the whole period: r = 0, an observation.
        # (03-25, 03-26]: no flow, V(03-25) = V(03-26) = 0: the single run is 0/0 (ZERO_CAPITAL_RUN): NO capital on any day of it: not an observation.
        # (03-26, 03-28]: starts at value 0 but receives 500 at the start of 03-27: V(03-27) / (V(03-26) + 500) = 500/500 = 1, then 500/500 = 1: r = 0, an observation (Ruling 2.4).
        w, aapl = world()
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 24), USD, amount=L.money("1000", USD))
        L.add(pk.A1, EventType.WITHDRAWAL, D(2025, 3, 25), USD, amount=L.money("1000", USD))
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 27), USD, amount=L.money("500", USD))
        return w, L

    def test_a_period_with_no_capital_on_any_day_is_insufficient_not_a_zero_return(self):
        w, L = self.zero_capital_world()
        res = run(w, L, [D(2025, 3, 24), D(2025, 3, 25), D(2025, 3, 26), D(2025, 3, 28)])
        p1, p2, p3 = res.series.periods
        self.assertEqual((p1.exact, p3.exact), (F(0), F(0)))
        self.assertIsNone(p2.exact)
        self.assertIs(p2.valued.state, SufficiencyState.INSUFFICIENT_DATA)
        self.assertIsNone(p2.valued.reason)                                  # no reason code: a detail only (Ruling 2.4)
        self.assertEqual([p.zero_capital for p in res.series.periods], [False, True, False])
        self.assertIn("ZERO_CAPITAL_PERIOD", p2.details)
        self.assertIn("ZERO_CAPITAL_PERIOD", {c.detail for c in p2.valued.causes})
        self.assertEqual((res.series.assessment.zero_capital, res.series.assessment.insufficient, res.series.assessment.available), (1, 1, 2))
        self.assertEqual(dict(res.identities)["I-10"], S.PASS)               # the two exact periods link on their own runs

    def test_a_period_funded_only_part_of_its_days_is_an_ordinary_observation(self):
        # the same world, one period (03-25, 03-28]: empty on 03-26, funded from the start of 03-27: flow day 03-27 inside, so it is NOT a zero-capital period.
        # run (03-25..03-26): 0/0 = 1 (ZERO_CAPITAL_RUN); flow: V(03-27)/(V(03-26) + 500) = 1; run (03-27..03-28): 500/500 = 1: r = 0
        w, L = self.zero_capital_world()
        res = run(w, L, [D(2025, 3, 25), D(2025, 3, 28)], spec=WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 25)))
        (p,) = res.series.periods
        self.assertEqual(p.exact, F(0))
        self.assertFalse(p.zero_capital)
        self.assertIn("ZERO_CAPITAL_RUN", p.details)                         # a run of it, yes; the whole period, no
        self.assertNotIn("ZERO_CAPITAL_PERIOD", p.details)


class WindowTests(unittest.TestCase):
    def test_a_window_before_inception_is_refused_as_in_cp3_under_refuse(self):
        w, aapl = world()
        L = ledger(aapl)  # earliest event 03-24: inception I0 = 03-23
        spec = WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 20))
        res = run(w, L, [D(2025, 3, 20), D(2025, 4, 4)], spec=spec)
        self.assertIsNone(res.series)
        self.assertEqual(res.refusal.cause.detail, "WINDOW_BEFORE_INCEPTION")
        self.assertIsNone(res.refusal.reason)
        self.assertEqual(res.manifest.window.start, D(2025, 3, 20))  # the declared window travels with the refusal
        self.assertEqual(res.manifest.window.frequency, "WEEKLY")
        # the refusal is as reproducible as a series: its digest is the hash of exactly its window, reason and cause
        from marketdata.canonical import canonical_json, sha256_hex  # noqa: PLC0415

        expected = {"schema": S.SERIES_SCHEMA, "refused": True, "window": dict(res.manifest.window.to_obj(), frequency=None), "reason": None, "cause": res.refusal.cause.to_obj()}
        self.assertEqual(res.series_digest, sha256_hex(canonical_json(expected).encode("utf-8")))

    def test_a_trailing_request_before_inception_is_refused_and_never_shortened(self):
        # a 3Y request on a portfolio whose history starts 2025-03-23 (Ruling 7.2): refused with WINDOW_BEFORE_INCEPTION, on the real grid, in every frequency
        w, aapl = world()
        L = ledger(aapl)
        for freq in S.Frequency:
            res = run_grid(w, L, WindowSpec(WindowRule.TRAILING_MONTHS, 36), D(2025, 4, 4), freq)
            self.assertIsNone(res.series, freq)
            self.assertEqual(res.refusal.cause.detail, "WINDOW_BEFORE_INCEPTION")
            self.assertEqual(res.manifest.window.start, D(2022, 4, 4))   # the requested base travels with the refusal

    def test_the_grid_window_declares_its_stubs_and_the_series_starts_at_the_first_grid_date(self):
        # CUSTOM base Mon 2025-03-24, E Fri 2025-04-04, weekly: grid points Fri 03-28 and Fri 04-04: g_0 = 03-28, one period; stubs 4 and 0 days
        w, aapl = world()
        res = run_grid(w, ledger(aapl), WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 24)), D(2025, 4, 4), S.Frequency.WEEKLY)
        s = res.series
        g = s.grid
        self.assertEqual((g.requested_base, g.requested_end, g.base_date, g.last_period_end, g.observation_count, g.stub_start_days, g.stub_end_days),
                         (D(2025, 3, 24), D(2025, 4, 4), D(2025, 3, 28), D(2025, 4, 4), 1, 4, 0))
        self.assertEqual((s.window.start, s.window.end, s.window.requested_start, s.window.rule, s.window.frequency), (D(2025, 3, 28), D(2025, 4, 4), D(2025, 3, 24), "CUSTOM", "WEEKLY"))
        self.assertEqual([p.exact for p in s.periods], [F(1100, 1040) - 1])
        self.assertEqual(s.rule_id, S.GRID_RULE_ID)
        pairs = dict(res.manifest.numerics)
        self.assertEqual((pairs["series.requested_base"], pairs["series.requested_end"], pairs["series.request"]), ("2025-03-24", "2025-04-04", "CUSTOM"))

    def test_the_end_stub_is_declared_and_excluded(self):
        # E = Wed 2025-04-09 (no closes after 04-04): the last grid point is Fri 04-04, the 5 days after it are the end stub and no observation
        w, aapl = world()
        res = run_grid(w, ledger(aapl), WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 24)), D(2025, 4, 9), S.Frequency.WEEKLY)
        g = res.series.grid
        self.assertEqual((g.last_period_end, g.stub_end_days, g.observation_count), (D(2025, 4, 4), 5, 1))
        self.assertEqual(res.series.valuation_dates_read, (D(2025, 3, 28), D(2025, 4, 4)))  # nothing after the last grid point was valued

    def test_a_window_with_no_full_period_is_refused_with_no_full_period(self):
        # E = Thu 04-03: the only Friday in (03-24, 04-03] is 03-28: one grid point, no period
        w, aapl = world()
        res = run_grid(w, ledger(aapl), WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 24)), D(2025, 4, 3), S.Frequency.WEEKLY)
        self.assertIsNone(res.series)
        self.assertEqual((res.refusal.cause.detail, res.refusal.reason), ("NO_FULL_PERIOD", None))
        self.assertEqual(res.refusal.cause.state, "INSUFFICIENT_DATA")
        none = run(w, ledger(aapl), [], end=D(2025, 4, 3), spec=SINCE)  # a rule that returns no grid point at all is the same refusal, not an error
        self.assertEqual(none.refusal.cause.detail, "NO_FULL_PERIOD")

    DAILY_GAP = {D(2025, 3, 24): "100", D(2025, 3, 25): "102", D(2025, 4, 2): "106", D(2025, 4, 3): "108", D(2025, 4, 4): "110"}

    def test_max_available_starts_after_the_last_insufficient_period_and_says_so(self):
        # closes only on 03-24, 03-25 and 04-02..04-04; daily grid from inception (B = I0 = Sun 03-23, so g_0 = Mon 03-24). The value at 04-01 has 5 missed sessions: withheld, so the periods ending 04-01 and
        # 04-02 are INSUFFICIENT_DATA; the base becomes g_j = 04-02 and the observations are (04-02, 04-03] = 108/106 - 1 = 1/53 and (04-03, 04-04] = 110/108 - 1 = 1/54.
        w, aapl = world(self.DAILY_GAP)
        L = ledger(aapl)
        res = run_grid(w, L, S.MaxAvailable(), D(2025, 4, 4), S.Frequency.DAILY)
        s = res.series
        g = s.grid
        self.assertEqual([p.exact for p in s.periods], [F(1, 53), F(1, 54)])
        self.assertEqual((g.rule, g.max_available_start, g.max_available_after, g.base_date, g.last_period_end, g.observation_count), ("MAX_AVAILABLE", "AFTER_INSUFFICIENT_PERIOD", D(2025, 4, 2), D(2025, 4, 2), D(2025, 4, 4), 2))
        self.assertEqual((g.requested_base, g.stub_start_days, g.stub_end_days), (D(2025, 3, 23), 10, 0))  # g_0 - B = 04-02 - 03-23: the requested base is kept
        self.assertEqual((s.window.rule, s.window.start), ("MAX_AVAILABLE", D(2025, 4, 2)))
        self.assertEqual(dict(res.manifest.numerics)["series.max_available_start"], "AFTER_INSUFFICIENT_PERIOD@2025-04-02")
        self.assertEqual(dict(res.identities), {"I-10": S.PASS, "I-11": S.PASS})
        # the SAME window asked as a CUSTOM request is not shortened: every period is kept, the insufficient ones with no value
        full = run_grid(w, L, WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 24)), D(2025, 4, 4), S.Frequency.DAILY)
        self.assertEqual(len(full.series.periods), 9)
        self.assertEqual([p.valued.state.value for p in full.series.periods][-4:], ["INSUFFICIENT_DATA", "INSUFFICIENT_DATA", "AVAILABLE", "AVAILABLE"])
        self.assertEqual(full.series.assessment.insufficient, 2)

    def test_max_available_from_inception_says_inception(self):
        w, aapl = world()
        res = run_grid(w, ledger(aapl), S.MaxAvailable(), D(2025, 4, 4), S.Frequency.WEEKLY)
        g = res.series.grid
        # B = I0 = Sun 03-23; the first Friday on or after it is 03-28 (stub 5 days); nothing insufficient
        self.assertEqual((g.max_available_start, g.max_available_after, g.base_date, g.stub_start_days, g.observation_count), ("INCEPTION", None, D(2025, 3, 28), 5, 1))
        self.assertEqual(res.series.window.rule, "MAX_AVAILABLE")

    def test_max_available_with_no_full_period_after_the_last_insufficient_one_is_refused(self):
        # closes stop after 03-28: from 04-04 the value is withheld, so the LAST period is insufficient and no full period follows it
        closes = {d: p for d, p in CLOSES.items() if d <= D(2025, 3, 28)}
        w, aapl = world(closes)
        res = run_grid(w, ledger(aapl), S.MaxAvailable(), D(2025, 4, 4), S.Frequency.DAILY)
        self.assertIsNone(res.series)
        self.assertEqual(res.refusal.cause.detail, "NO_FULL_PERIOD")
        self.assertEqual(dict(res.manifest.numerics)["series.request"], "MAX_AVAILABLE")
        # the refusal declares the REQUEST's window like every other refusal: its base is the since-inception base B = I0 (Sun 03-23), not the first grid date (cp4_golden part 3 R8-K1, R11-X1)
        self.assertEqual((res.manifest.window.start, res.manifest.window.end, res.manifest.window.rule), (D(2025, 3, 23), D(2025, 4, 4), "MAX_AVAILABLE"))

    def test_no_period_is_merged_dropped_or_filled(self):
        # the insufficient periods stay in the series, in place, with no value and their causes; the neighbours keep their own horizon (Ruling 2.5)
        w, aapl = world(self.DAILY_GAP)
        full = run_grid(w, ledger(aapl), WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 24)), D(2025, 4, 4), S.Frequency.DAILY)
        ends = [p.end for p in full.series.periods]
        self.assertEqual(ends, [D(2025, 3, 25), D(2025, 3, 26), D(2025, 3, 27), D(2025, 3, 28), D(2025, 3, 31), D(2025, 4, 1), D(2025, 4, 2), D(2025, 4, 3), D(2025, 4, 4)])
        self.assertTrue(all(b - a == datetime.timedelta(days=1) or (a.weekday() == 4 and b - a == datetime.timedelta(days=3)) for a, b in zip(full.series.boundaries, full.series.boundaries[1:])))
        dead = [p for p in full.series.periods if p.exact is None]
        self.assertEqual([p.end for p in dead], [D(2025, 4, 1), D(2025, 4, 2)])
        self.assertTrue(all(p.valued.causes for p in dead))

    def test_an_unclipped_window_serialises_exactly_as_cp3_did(self):
        w = WindowUsed(D(2025, 1, 1), D(2025, 2, 1), None, "CUSTOM", None)
        self.assertEqual(set(w.to_obj()), {"start", "end", "frequency", "rule", "months", "days", "since_snapshot"})
        self.assertIn("requested_start", dataclasses.replace(w, requested_start=D(2024, 1, 1)).to_obj())


class BoundaryRuleContractTests(unittest.TestCase):
    def test_the_rule_must_be_strictly_increasing_and_inside_the_requested_window(self):
        w, aapl = world()
        L = ledger(aapl)
        for bad in ([D(2025, 3, 24), D(2025, 3, 24), D(2025, 4, 4)], [D(2025, 3, 28), D(2025, 3, 24), D(2025, 4, 4)],
                    [D(2025, 3, 23), D(2025, 4, 4)],          # before B (03-24)
                    [D(2025, 3, 24), D(2025, 4, 5)]):         # after E (04-04)
            with self.assertRaises(S.BoundaryRuleError, msg=bad):
                run(w, L, bad, end=D(2025, 4, 4))
        # inside the window but not starting at B or ending at E is FINE now: the stubs are declared
        ok = run(w, L, [D(2025, 3, 25), D(2025, 4, 3)], end=D(2025, 4, 4))
        self.assertEqual((ok.series.grid.stub_start_days, ok.series.grid.stub_end_days), (1, 1))

    def test_the_rule_receives_the_frequency_and_the_window_used_and_its_id_is_in_the_manifest(self):
        seen = []

        class Rule:
            rule_id = "test-rule/1"

            def boundaries(self, frequency, window):
                seen.append((frequency, window.start, window.end))
                return (window.start, window.end)

        w, aapl = world()
        L = ledger(aapl)
        res = engine.compute_return_series(L.rows, L.version, SINCE, D(2025, 4, 4), S.Frequency.MONTHLY, Rule(), USD, w.store, w.ident, w.market, PERF, suppressions=())
        self.assertEqual(seen, [(S.Frequency.MONTHLY, D(2025, 3, 24), D(2025, 4, 4))])
        pairs = dict(res.manifest.numerics)
        self.assertEqual((pairs["series.boundary_rule"], pairs["series.frequency"], pairs["series.request"]), ("test-rule/1", "MONTHLY", "CUSTOM"))
        self.assertNotIn("series.short_window_policy", pairs)  # there is no such policy: a requested window is refused or served, never shortened

    def test_the_boundaries_the_frequency_the_rule_and_the_request_are_part_of_the_question(self):
        w, aapl = world()
        L = ledger(aapl)
        dates = [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)]
        base = run(w, L, dates)
        other_dates = run(w, L, [D(2025, 3, 24), D(2025, 3, 27), D(2025, 4, 4)])
        other_freq = run(w, L, dates, freq=S.Frequency.MONTHLY)
        other_request = run(w, L, dates, spec=WindowSpec(WindowRule.CUSTOM, None, D(2025, 3, 23)))  # a different requested base: a different stub, a different question
        ids = {r.manifest.manifest_id for r in (base, other_dates, other_freq, other_request)}
        self.assertEqual(len(ids), 4)


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.w, self.aapl = world()
        self.L = ledger(self.aapl)
        self.res = run(self.w, self.L, [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)])

    def test_i10_fails_when_a_period_return_is_altered(self):
        s = self.res.series
        forged = dataclasses.replace(s, periods=(dataclasses.replace(s.periods[0], valued=dataclasses.replace(s.periods[0].valued, exact=F(1, 20))),) + s.periods[1:])
        bv = dict(s.boundary_values)
        report = S.link_identity(forged, [], lambda d: bv[d] if d in bv else self.fail("a date outside the boundaries was read"), PERF)
        self.assertEqual(report.status, S.FAIL)
        self.assertEqual([r.status for r in report.runs], [S.FAIL])

    def test_i10_is_not_computable_when_no_period_has_a_value(self):
        s = self.res.series
        dead = dataclasses.replace(s.periods[0].valued, state=SufficiencyState.INSUFFICIENT_DATA, exact=None)
        forged = dataclasses.replace(s, periods=tuple(dataclasses.replace(p, valued=dead) for p in s.periods))
        self.assertEqual(S.link_identity(forged, [], lambda d: dead, PERF).status, S.NOT_COMPUTABLE)

    def test_i11_fails_on_a_hidden_read_and_on_a_missing_read(self):
        s = self.res.series
        self.assertEqual(S.coverage_identity(s), S.PASS)
        self.assertEqual(S.coverage_identity(dataclasses.replace(s, valuation_dates_read=s.valuation_dates_read + (D(2025, 4, 3),))), S.FAIL)
        self.assertEqual(S.coverage_identity(dataclasses.replace(s, valuation_dates_read=s.valuation_dates_read[1:])), S.FAIL)

    def test_only_the_required_dates_are_valued(self):
        # weekly boundaries and no flow after the buy: the dates read are exactly the three boundaries, not the seven days between
        self.assertEqual(self.res.series.valuation_dates_read, (D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)))
        L = ledger(self.aapl, [lambda L: L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), USD, amount=L.money("500", USD))])
        res = run(self.w, L, [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)])
        self.assertEqual(res.series.valuation_dates_read, (D(2025, 3, 24), D(2025, 3, 28), D(2025, 3, 31), D(2025, 4, 1), D(2025, 4, 4)))

    def test_a_failed_identity_raises_in_the_engine_it_is_never_a_number(self):
        from unittest import mock  # noqa: PLC0415

        with mock.patch.object(engine, "link_identity", return_value=S.LinkReport(S.FAIL, ())):
            with self.assertRaises(S.SeriesIdentityError):
                run(self.w, self.L, [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)])


class DeterminismTests(unittest.TestCase):
    def test_same_inputs_same_bytes_and_the_digest_names_the_answer(self):
        w, aapl = world()
        L = ledger(aapl)
        a = run(w, L, [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)])
        b = run(w, L, [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)])
        self.assertEqual(a.canonical_json(), b.canonical_json())
        self.assertEqual(a.series_digest, b.series.digest)
        c = run(w, L, [D(2025, 3, 24), D(2025, 3, 31), D(2025, 4, 4)])
        self.assertNotEqual(a.series_digest, c.series_digest)

    def test_the_series_is_synthetic_when_the_release_is(self):
        w, aapl = world()
        res = run(w, ledger(aapl), [D(2025, 3, 24), D(2025, 4, 4)])
        self.assertTrue(res.manifest.synthetic)

    def test_the_manifest_cites_the_files_the_series_read_in_both_directions(self):
        w, aapl = world()
        res = run(w, ledger(aapl), [D(2025, 3, 24), D(2025, 3, 28), D(2025, 4, 4)])
        self.assertTrue(res.manifest.consumed_files())
        # the same window through compute_window cites the same file set (one close file in this world): the series adds no hidden input
        L = ledger(aapl)
        win = pk.compute_window(L.rows, L.version, SINCE, D(2025, 4, 4), USD, w.store, w.ident, w.market, PERF)
        self.assertEqual(set(res.manifest.consumed_files()), set(win.manifest.consumed_files()))


class ToolBoundaryTests(unittest.TestCase):
    def test_no_product_module_imports_the_risk_tools(self):
        import ast  # noqa: PLC0415

        src = Path(__file__).resolve().parents[2] / "src"
        for path in sorted(src.rglob("*.py")):
            if "risk_tools" in path.parts:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                for n in names:
                    self.assertFalse(n == "risk_tools" or n.startswith("risk_tools."), f"{path.relative_to(src)} imports {n}")

    def test_the_cost_tool_runs_on_a_small_world_and_its_mitigation_is_output_neutral(self):
        from risk_tools import cost  # noqa: PLC0415

        case = cost.Case(4, 80, 6, D(2025, 6, 30), 7)
        out = cost.measure(case, "weekly", True)
        self.assertGreater(out["periods"], 100)
        self.assertEqual(out["states"]["insufficient"], 0)
        self.assertTrue(out["pairwise_equals_naive"])
        self.assertEqual(out["exact_periods"], out["periods"])
        vals = [F(i * i + 1, 7 + i) for i in range(37)]
        self.assertEqual(cost.pairwise_sum(vals), sum(vals, F(0)))

    def test_the_cost_tool_boundaries_satisfy_the_rule_contract(self):
        from risk_tools import cost  # noqa: PLC0415

        w = WindowUsed(D(2022, 6, 30), D(2025, 6, 30), None, "TRAILING_MONTHS", 36)
        weekly = S.validate_boundaries(w, cost.grid_for("weekly", w.start, w.end))
        self.assertEqual((weekly[0], weekly[-1]), (D(2022, 7, 1), D(2025, 6, 27)))  # g_0 = the first Friday on or after B, g_n = the last on or before E
        self.assertEqual(S.validate_boundaries(w, cost.grid_for("daily", w.start, w.end))[-1], w.end)


if __name__ == "__main__":
    unittest.main()
