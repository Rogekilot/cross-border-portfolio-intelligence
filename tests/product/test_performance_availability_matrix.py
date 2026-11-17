"""The availability matrix (tech plan 16.8 item 4; PRD 38.3 "unsupported cases return availability states"): METRIC x CONDITION -> the allowed (state, reason) pairs.

Every metric id of `performance.registry.METRIC_IDS` has a ROW; every row has a cell for EVERY condition (an empty cell, `NONE`, means "no metric of this id is emitted under this condition" and is
asserted too). The cells are derived from the rulings of `performance/1.8` and, where the condition is a fixture portfolio, from the fixture's own asserted states (written by the Quant), never from
the engine's output. A mismatch is a FINDING: neither side is adjusted here.

Invariants asserted for every metric of every condition: no exception; a value exists exactly when the state is AVAILABLE or LIMITED; an INSUFFICIENT_DATA metric names its causes; an AVAILABLE or
LIMITED metric states nothing but its own reason (none or STALE_DATA for AVAILABLE/LIMITED, per Ruling 1.5). Adding a metric id without a row, or a row without a metric id, fails.
"""

import datetime
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp3_golden_kit as g  # noqa: E402
import cp3_golden_part3_kit as p3  # noqa: E402
import cp3_golden_part4_kit as p4  # noqa: E402
import performance_kit as pk  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402

from domain.currency import Money  # noqa: E402
from domain.ledger import EventType  # noqa: E402
from performance import engine  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402
from performance.registry import METRIC_IDS  # noqa: E402

D = datetime.date
NONE = None  # no metric of this id is emitted under the condition
A = ("AVAILABLE", None)
L_STALE = ("LIMITED", "STALE_DATA")
I_NONE = ("INSUFFICIENT_DATA", None)  # no reason code: the detail names the cause (Rulings 5.3, 5.4, 6.4, 7.2)
I_SC = ("INSUFFICIENT_DATA", "SOURCE_CONFLICT")
I_STALE = ("INSUFFICIENT_DATA", "STALE_DATA")
I_FX = ("INSUFFICIENT_DATA", "MISSING_FX_HISTORY")
I_COST = ("INSUFFICIENT_DATA", "MISSING_COST_BASIS")

CONDITIONS = ("BASELINE", "SOURCE_CONFLICT", "INTERIOR_GAP", "STALE_INTERIOR", "CNH_FLOW", "WINDOW_BEFORE_INCEPTION", "NON_POSITIVE_BASE", "UNKNOWN_BASIS")

AMOUNTS = ("income_amount", "fees_amount", "taxes_amount", "financing_amount", "conversion_result_amount")


def row(*cells):
    return dict(zip(CONDITIONS, cells))


def cell(*pairs):
    return frozenset(pairs)


# Each cell is a frozenset of allowed (state, reason) pairs, or NONE. The order of the cells is CONDITIONS.
MATRIX = {
    # valuation (Rulings 1.1 to 1.4a)
    "holding_value":        row(cell(A), cell(I_SC), cell(A), cell(A), NONE, cell(A), cell(A), cell(A)),
    "cash_value":           row(cell(A), cell(A), NONE, cell(A), cell(A, I_FX), cell(A), cell(A), cell(A)),  # P22 spends its whole deposit: a zero balance is not emitted (Ruling 1.3)
    "receivable_value":     row(NONE, NONE, NONE, NONE, NONE, NONE, NONE, NONE),
    "portfolio_value":      row(cell(A), cell(I_SC), cell(A), cell(A), cell(A, I_FX), cell(A), cell(A), cell(A)),
    "portfolio_value_priced_holdings": row(NONE, cell(A), NONE, NONE, cell(A), NONE, NONE, NONE),  # only when the total is suppressed (PD-0035 section 2): here the USD deposit without the CNH one
    # window (Rulings 5 to 7)
    "gain_absolute":        row(cell(A), cell(I_SC), cell(A), cell(A), cell(I_FX), cell(I_NONE), cell(A), cell(A)),
    "return_twr":           row(cell(A), cell(I_SC), cell(A), cell(A), cell(I_FX), cell(I_NONE), cell(I_NONE), cell(A)),
    "return_annualized":    row(cell(I_NONE), cell(I_SC), cell(I_NONE), cell(I_NONE), cell(I_FX), cell(I_NONE), cell(I_NONE), cell(I_NONE)),  # every window here is shorter than a year (Ruling 7.2)
    "return_mwr":           row(cell(A), cell(I_SC), cell(A), cell(A), cell(I_FX), cell(I_NONE), cell(I_NONE), cell(A)),  # NON_POSITIVE_BASE: no capital was invested (NO_CAPITAL)
    "return_mwr_annualized": row(cell(I_NONE), cell(I_SC), cell(I_NONE), cell(I_NONE), cell(I_FX), cell(I_NONE), cell(I_NONE), cell(I_NONE)),
    # amounts (Ruling 8): a window with no such event is 0, AVAILABLE; a refused window refuses them
    **{amount: row(cell(A), cell(A), cell(A), cell(A), cell(A), cell(I_NONE), cell(A), cell(A)) for amount in AMOUNTS},
    # gains (Ruling 3)
    "realized_gain":        row(cell(A), NONE, NONE, NONE, NONE, NONE, NONE, cell(I_COST)),
    "realized_gain_total":  row(cell(A), cell(A), cell(A), NONE, cell(A), cell(I_NONE), cell(A), cell(I_COST)),
    "unrealized_gain":      row(cell(A), cell(I_SC), cell(A), NONE, NONE, cell(A), cell(A), cell(I_COST)),
    "unrealized_gain_total": row(cell(A), cell(I_SC), cell(A), NONE, cell(A), cell(A), cell(A), cell(I_COST)),
    "remaining_basis":      row(cell(A), cell(I_SC), cell(A), NONE, NONE, cell(A), cell(A), cell(I_COST)),
    "since_acquisition":    row(cell(A), cell(I_SC), cell(A), NONE, NONE, cell(A), cell(A), cell(I_COST)),
    # attribution (Ruling 9)
    "attribution_money":    row(cell(A), cell(I_SC), cell(I_STALE), cell(L_STALE), cell(I_FX), cell(I_NONE), cell(A), NONE),
    "attribution_return":   row(cell(A), cell(I_SC), cell(I_STALE), cell(L_STALE), cell(I_FX), cell(I_NONE), cell(I_NONE), NONE),
    "attribution_breakdown": row(cell(A), NONE, NONE, cell(L_STALE), NONE, NONE, cell(A), NONE),  # a refused attribution has no breakdown
}


def pairs_of(results):
    out = {}
    for res in results:
        for m in res.metrics:
            out.setdefault(m.metric_id, []).append(m)
    return out


class _World(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = cp1.Ids(randomize=False)
        market = p4.build_market(cls.ids)
        cls.addClassCleanup(market.close)
        events = {p["name"]: p4.portfolio_events(p, cls.ids) for p in p4.FIXTURE["portfolios"]}
        p2_fixture = next(p for p in p3.FIXTURE["portfolios"] if p["name"].startswith("P2 ("))
        events[p2_fixture["name"]] = p3.portfolio_events(p2_fixture, cls.ids)
        cls.runner = p4.Runner(market, cls.ids, events, verify_identities=True)
        cls.p2 = p2_fixture

    def fx(self, prefix):
        return next(p for p in p4.FIXTURE["portfolios"] if p["name"].split()[0] == prefix)

    def run_fixture(self, portfolio, as_of, version, request, attribution=True, gains=True):
        a = {"id": "matrix", "as_of": as_of, "ledger_version": version}
        out = [self.runner.valuation(portfolio, a), self.runner.window(portfolio, a, request)]
        if gains:
            out.append(self.runner.gains(portfolio, a, request))
        if attribution:
            out.append(self.runner.attribution(portfolio, a, request))
        return out

    def scenarios(self):
        since = {"rule": "SINCE_INCEPTION"}
        out = {
            "BASELINE": self.run_fixture(self.fx("P14"), "2025-03-31", 6, since),
            "SOURCE_CONFLICT": self.run_fixture(self.fx("P13"), "2025-03-04", 2, {"rule": "CUSTOM", "base": "2025-02-28"}),
            "INTERIOR_GAP": self.run_fixture(self.fx("P22"), "2025-03-31", 2, since),
            "STALE_INTERIOR": self.run_fixture(self.fx("P3"), "2025-03-20", 7, since, gains=False),
            "WINDOW_BEFORE_INCEPTION": self.run_fixture(self.fx("P14"), "2025-03-31", 6, {"rule": "CUSTOM", "base": "2024-01-01"}),
            "UNKNOWN_BASIS": self.run_fixture(self.p2, "2025-07-31", 3, since, attribution=False),
        }
        out["CNH_FLOW"] = self.cnh()
        out["NON_POSITIVE_BASE"] = self.non_positive_base()
        return out

    def cnh(self):
        """A CNH deposit has no ECB fixing (Ruling 1.2): its value is INSUFFICIENT_DATA + MISSING_FX_HISTORY; the USD deposit is fine."""
        w = pk.world_w()
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), pk.USD, amount=Money(Decimal(1000), pk.USD))
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 2), pk.CNH, amount=Money(Decimal(100), pk.CNH))
        spec = WindowSpec(WindowRule.CUSTOM, None, D(2025, 4, 1))
        args = (w.store, w.ident, w.market, engine.performance_conventions())
        return [
            engine.compute(L.rows, L.version, D(2025, 4, 2), pk.USD, w.store, w.ident, w.market, args[3], suppressions=()),
            engine.compute_window(L.rows, L.version, spec, D(2025, 4, 2), pk.USD, *args, suppressions=()),
            engine.compute_gains(L.rows, L.version, D(2025, 4, 2), pk.USD, *args, suppressions=(), window=spec),
            engine.compute_attribution(L.rows, L.version, spec, D(2025, 4, 2), pk.USD, *args, suppressions=()),
        ]

    def non_positive_base(self):
        """A purchase recorded with no funding deposit: the first day's base is 0 and its gain is not (Ruling 5.3)."""
        L = pk.Ledger()
        L.add(mp.A1, EventType.BUY, D(2025, 2, 3), mp.USD, listing_id=mp.LISTING, quantity=Decimal(50), amount=Money(Decimal(7500), mp.USD))
        port = mp.market(evidence=None, prices={D(2025, 2, 3): "37.50", D(2025, 2, 4): "40.00"})
        spec = WindowSpec(WindowRule.SINCE_INCEPTION)
        args = (port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF)
        return [
            engine.compute(L.rows, L.version, D(2025, 2, 4), mp.USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=()),
            engine.compute_window(L.rows, L.version, spec, D(2025, 2, 4), mp.USD, *args, suppressions=()),
            engine.compute_gains(L.rows, L.version, D(2025, 2, 4), mp.USD, *args, suppressions=(), window=spec),
            engine.compute_attribution(L.rows, L.version, spec, D(2025, 2, 4), mp.USD, *args, suppressions=()),
        ]


class AvailabilityMatrixTests(_World):
    def test_every_registered_metric_has_a_row_and_every_row_a_registered_metric_and_a_cell_per_condition(self):
        self.assertEqual(set(MATRIX), set(METRIC_IDS))
        for metric_id, cells in MATRIX.items():
            self.assertEqual(set(cells), set(CONDITIONS), metric_id)
            for condition, c in cells.items():
                self.assertTrue(c is None or (isinstance(c, frozenset) and c), (metric_id, condition))

    def test_a_metric_id_that_is_not_registered_cannot_be_built(self):
        from decimal import Decimal as Dec  # noqa: PLC0415
        from performance.results import WindowUsed  # noqa: PLC0415
        from performance.states import Valued, build_metric  # noqa: PLC0415
        from product_contract.vocabulary import SufficiencyState  # noqa: PLC0415

        valued = Valued(SufficiencyState.AVAILABLE, None, __import__("fractions").Fraction(1), ())
        with self.assertRaises(ValueError):
            build_metric("brand_new_metric", "PERIOD", (), valued, None, engine.performance_conventions().rounding, WindowUsed(D(2025, 1, 1), D(2025, 1, 2)), "t", False, False)
        self.assertEqual(Dec(1), Dec(1))

    def test_every_cell_of_the_matrix_holds_and_every_metric_keeps_the_invariants(self):
        findings = []
        scenarios = self.scenarios()
        self.assertEqual(set(scenarios), set(CONDITIONS))
        for condition, results in scenarios.items():
            by_id = pairs_of(results)
            for metric_id, metrics in by_id.items():
                self.assertIn(metric_id, METRIC_IDS, condition)
                for m in metrics:
                    state, reason = m.result.sufficiency_state.value, None if m.result.reason_code is None else m.result.reason_code.value
                    # invariants (no exception got here; the engine returns states, never raises)
                    self.assertEqual(state in ("AVAILABLE", "LIMITED"), m.result.value is not None, (condition, metric_id, m.subject))
                    if state == "INSUFFICIENT_DATA":
                        self.assertTrue(m.causes, (condition, metric_id, m.subject))
                        self.assertIsNone(m.exact)
                        self.assertEqual(m.breakdown, ())
                    if state == "AVAILABLE":
                        self.assertIn(reason, (None, "STALE_DATA"), (condition, metric_id))
                    if state == "LIMITED":
                        self.assertIsNotNone(reason, (condition, metric_id))
            for metric_id, cells in MATRIX.items():
                expected = cells[condition]
                got = by_id.get(metric_id, [])
                if expected is None:
                    if got:
                        findings.append(f"{condition} {metric_id}: expected no metric, got {sorted({(m.result.sufficiency_state.value, None if m.result.reason_code is None else m.result.reason_code.value) for m in got})}")
                    continue
                if not got:
                    findings.append(f"{condition} {metric_id}: expected {sorted(expected, key=str)}, no metric emitted")
                    continue
                seen = {(m.result.sufficiency_state.value, None if m.result.reason_code is None else m.result.reason_code.value) for m in got}
                if not seen <= {(s, r) for s, r in expected}:
                    findings.append(f"{condition} {metric_id}: expected within {sorted(expected, key=str)}, got {sorted(seen, key=str)}")
        self.assertEqual(findings, [], "\n" + "\n".join(findings))


if __name__ == "__main__":
    unittest.main()
