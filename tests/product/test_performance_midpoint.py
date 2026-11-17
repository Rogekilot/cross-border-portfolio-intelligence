"""The CP3 midpoint fix round (review `reviews/TECH_REVIEW.md` section 28 of 0059d64; conventions market-data/1.9 and performance/1.3).

One file, one set-up: the review's own probe. A1 holds 50 units of one listing (bought 2024-12-20 for 7,500 USD, 10,000 USD deposited); a corroborated 4:1 split has
ex-date 2025-02-03 and is NOT in the ledger; RAW closes are 150.00 (2025-01-31) and 37.50 from 2025-02-03. Every expected value is derived by hand in the test.

Layers: CP3-1 (in-kind flows), CP3-2 (the suppression follows units, Ruling 6.4c), CP3-3 (synthetic evidence, Ruling 4.8 item 4), CP3-4 (detection composed with
computation), CP3-5 (the size guard), CP3-6 (identity registry and engine pins), CP3-7 (a receivable needs the fixing), CP3-8 (the four surviving mutants), the
performance/1.2 and 1.3 items (Q1 to Q7, M_t), and the S-4 named test.
"""

import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_kit  # noqa: E402
import marketdata_cp2c1_kit as k  # noqa: E402
import performance_kit as pk  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.manifest import MarketDataRelease  # noqa: E402
from marketdata.store import InMemoryMarketData  # noqa: E402
from performance.engine import compute_current, performance_conventions  # noqa: E402
from performance.inputs import SuppressionInput  # noqa: E402
from performance.manifest import ReproductionStatus  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402
from performance_service import service as svc  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
F = Fraction
USD = CurrencyCode("USD")
A1, A2, A3 = pk.A1, pk.A2, uuid.UUID(int=3)
LISTING, MIC = ca.LISTING, ca.MIC
AVAILABLE, LIMITED, INSUFFICIENT = SufficiencyState.AVAILABLE, SufficiencyState.LIMITED, SufficiencyState.INSUFFICIENT_DATA
PERF = performance_conventions()
EX = ca.EX  # 2025-02-03


class Ident:
    """A one-listing identity registry: LISTING trades in USD on XTST."""

    def __init__(self, mic=MIC):
        self.mic = mic

    def resolve(self, identifiers, as_of):
        raise NotImplementedError

    def trading_currency(self, listing_id):
        return USD

    def exchange_mic(self, listing_id):
        return self.mic

    def security_type(self, listing_id):
        return "EQUITY"


def closes(prices, listing=LISTING, real=False):
    """RAW closes. `real=True` marks the file as NOT synthetic (usage scope INTERNAL_DEVELOPMENT_ONLY), so a market that also has REAL corporate-action evidence
    holds no synthetic file at all (the service's happy path, as opposed to its synthetic refusal)."""
    out = []
    for day, price in prices.items():
        reading = pk.quote(listing, day, price, USD, "US")
        if real:
            import dataclasses  # noqa: PLC0415

            obs = reading.observation
            obs = dataclasses.replace(obs, lineage=dataclasses.replace(obs.lineage, usage_scope=ca.REAL))
            reading = dataclasses.replace(reading, observation=obs)
        out.append(reading)
    return out


PRICES = {D(2025, 1, 30): "150.00", D(2025, 1, 31): "150.00", D(2025, 2, 3): "37.50", D(2025, 2, 4): "37.50", D(2025, 2, 5): "37.50",
          D(2025, 2, 6): "37.50", D(2025, 2, 7): "37.50"}


def market(evidence="real", prices=None, name="probe", extra=(), real_quotes=False, listing=LISTING, mic=MIC):
    """`evidence`: "real" (a REAL feed and filing agree on 4:1 at 2025-02-03), "synthetic" (the same, both SYNTHETIC) or None (no corporate-action file)."""
    readings = closes(prices or PRICES, listing=listing, real=real_quotes) + list(extra)
    if evidence == "real":
        readings += [ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1), listing=listing), ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1), listing=listing)]
    elif evidence == "synthetic":
        readings += [ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1), listing=listing, usage=ca.SYN),
                     ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1), listing=listing, usage=ca.SYN)]
    release = MarketDataRelease(name=name, files=tuple(sorted({r.file_sha256 for r in readings})), source_precedence=())
    with gate_kit.admitted_real_world(readings, mic):  # 1.16 Ruling 4.7 item 6: a REAL reading of an invented source on XTST passes the per-reading gate only in this world
        return InMemoryMarketData(release, readings, exchange_of=lambda _l: mic, source_records=ca.k.records_for(readings))


MARKET_CONVENTIONS = market11_conventions(ca.CALENDARS)


def base_ledger() -> pk.Ledger:
    L = pk.Ledger()
    L.add(A1, EventType.DEPOSIT, D(2024, 12, 20), USD, amount=Money(Decimal(10000), USD))
    L.add(A1, EventType.BUY, D(2024, 12, 20), USD, listing_id=LISTING, quantity=Decimal(50), amount=Money(Decimal(7500), USD))
    return L


def transfer_out(L, day, account=A1, quantity=50):
    return L.add(account, EventType.TRANSFER_OUT, day, USD, listing_id=LISTING, quantity=Decimal(quantity))


def internal_transfer(L, day, source=A1, receiver=A2, quantity=50):
    L.add(source, EventType.TRANSFER_OUT, day, USD, listing_id=LISTING, quantity=Decimal(quantity), counterparty_account_id=receiver)
    L.add(receiver, EventType.TRANSFER_IN, day, USD, listing_id=LISTING, quantity=Decimal(quantity), counterparty_account_id=source)
    return L


def detect(L, port, ident=None, version=None):
    """Read-only F8-B detection over the ledger (the service's own helper), as the suppressions the engine is handed."""
    return svc._detect(L.rows, version or L.version, ca.PORTFOLIO, port, ident or Ident(), ca.CALENDARS, ca.POLICY)


def value(L, day, port, suppressions, account_scope=None, ident=None):
    return pk.compute(L.rows, L.version, day, USD, port, ident or Ident(), MARKET_CONVENTIONS, PERF, suppressions=suppressions, account_scope=account_scope)


def window(L, end, port, suppressions, start=D(2025, 1, 31), account_scope=None, ident=None, verify=False):
    return pk.compute_window(L.rows, L.version, WindowSpec(WindowRule.CUSTOM, None, start), end, USD, port, ident or Ident(), MARKET_CONVENTIONS, PERF,
                             suppressions=suppressions, account_scope=account_scope, verify_identities=verify)


def metric(res, metric_id, view=None, **subject):
    found = [m for m in res.metrics if m.metric_id == metric_id and (view is None or m.view == view)
             and all(dict(m.subject).get(key) == str(v) for key, v in subject.items())]
    assert len(found) == 1, (metric_id, view, subject, [(m.metric_id, m.view, m.subject) for m in res.metrics])
    return found[0]


def state_of(m):
    return m.result.sufficiency_state, m.result.reason_code


class SetUpIsTheReviewsProbe(unittest.TestCase):
    """Guards the harness: the dry run gives WOULD_APPEND and the suppression [2025-02-03, inf) with SOURCE_CONFLICT; the unsuppressed valuation of the holding
    on 2025-02-03 is the mixed-unit 1,875 (so a later test that sees INSUFFICIENT_DATA is seeing the fix, not a broken harness)."""

    def test_detection_gives_the_review_suppression(self):
        L = base_ledger()
        port = market()
        (s,) = detect(L, port)
        self.assertEqual((s.account_id, s.first_date, s.end_exclusive, s.reason, s.ex_date, s.decision),
                         (A1, EX, None, "SOURCE_CONFLICT", EX, "WOULD_APPEND"))
        self.assertEqual(metric(value(L, D(2025, 2, 3), port, ()), "holding_value", "NATIVE").exact, F(1875))  # the mixed-unit number the suppression exists to stop
        self.assertEqual(metric(value(L, D(2025, 2, 3), port, (s,)), "holding_value", "NATIVE").result.sufficiency_state, INSUFFICIENT)


def insufficient_conflict(test, m, note=""):
    test.assertEqual((m.result.value, m.result.sufficiency_state, m.result.reason_code), (None, INSUFFICIENT, ReasonCode.SOURCE_CONFLICT), note)


# ===== CP3-1: in-kind flows respect the split suppressions =====================================================================================

class InKindFlowsAndSuppressionsTests(unittest.TestCase):
    def test_a_whole_position_in_kind_outflow_on_the_ex_date_is_not_valued_in_mixed_units(self):
        L = transfer_out(base_ledger(), D(2025, 2, 3))
        port = market()
        sup = detect(L, port)
        # without the suppression the mixed-unit probe number appears: G = V_E - V_B + outflow = 2,500 - 10,000 + 50 x 37.50 = -5,625 (the reviewer's -5625)
        wrong = window(L, D(2025, 2, 3), port, ())
        self.assertEqual((metric(wrong, "gain_absolute").exact, metric(wrong, "gain_absolute").result.sufficiency_state), (F(-5625), AVAILABLE))
        res = window(L, D(2025, 2, 3), port, sup)
        for metric_id in ("gain_absolute", "return_twr", "return_annualized"):
            insufficient_conflict(self, metric(res, metric_id), metric_id)  # the flow cannot be valued (Ruling 4.3): every return over the window

    def test_the_same_transfer_two_days_after_the_ex_date_gives_no_gain_either(self):
        L = transfer_out(base_ledger(), D(2025, 2, 5))
        port = market()
        sup = detect(L, port)
        res = window(L, D(2025, 2, 6), port, sup)
        insufficient_conflict(self, metric(res, "return_twr"))  # V(02-04) holds the suppressed position
        insufficient_conflict(self, metric(res, "gain_absolute"), "G needs only V_B, V_E and the flows; the flow is unvaluable")
        self.assertEqual(metric(window(L, D(2025, 2, 6), port, ()), "gain_absolute").exact, F(-5625))  # the probe number, were the suppression ignored

    def test_a_flow_before_the_suppression_starts_is_valued_normally(self):
        L = transfer_out(base_ledger(), D(2025, 1, 31))
        port = market()
        res = window(L, D(2025, 1, 31), port, detect(L, port), start=D(2025, 1, 30))
        # 01-30: 10,000. The outflow on 01-31 is 50 x 150.00 = 7,500; V_E = 2,500: G = 2,500 - 10,000 + 7,500 = 0
        self.assertEqual((metric(res, "gain_absolute").exact, metric(res, "gain_absolute").result.sufficiency_state), (F(0), AVAILABLE))

    def test_account_scope_flow_of_an_internal_transfer_out_of_the_suppressed_account(self):
        L = internal_transfer(base_ledger(), D(2025, 2, 5))
        port = market()
        res = window(L, D(2025, 2, 6), port, detect(L, port), account_scope=A1)
        insufficient_conflict(self, metric(res, "gain_absolute"))  # the A1 side of an internal security transfer is an in-kind flow of A1


# ===== CP3-2 / market-data Ruling 6.4c: the suppression follows the units =======================================================================

class SuppressionFollowsUnitsTests(unittest.TestCase):
    def probe(self, extra_events=None):
        L = internal_transfer(base_ledger(), D(2025, 2, 5))
        if extra_events:
            extra_events(L)
        return L

    def test_the_review_probe_the_02_06_total_is_insufficient_and_source_conflict(self):
        L = self.probe()
        port = market()
        sup = detect(L, port)
        self.assertEqual([s.account_id for s in sup], [A1])  # F8-B is unchanged: A1 WOULD_APPEND, A2 NOT_HELD, one suppression
        before = value(L, D(2025, 2, 6), port, sup)
        insufficient_conflict(self, metric(before, "portfolio_value", "REPORTING"))
        # (the review's number, with the suppression applied to A1 only, was AVAILABLE 4,375 = 2,500 cash + 50 x 37.50; the mutation evidence shows this test fails then)
        holding = metric(before, "holding_value", "NATIVE", account=A2)
        insufficient_conflict(self, holding)
        self.assertIn("SPLIT_SUPPRESSION_CARRIED", holding.details)  # the lineage cause of the carried suppression

    def test_it_applies_at_account_scope_and_in_every_portfolio_total(self):
        L = self.probe()
        port = market()
        sup = detect(L, port)
        a2 = value(L, D(2025, 2, 6), port, sup, account_scope=A2)
        insufficient_conflict(self, metric(a2, "portfolio_value", "REPORTING"))
        insufficient_conflict(self, metric(a2, "portfolio_value", "NATIVE", currency="USD"))
        total = value(L, D(2025, 2, 6), port, sup)
        insufficient_conflict(self, metric(total, "portfolio_value", "NATIVE", currency="USD"))
        # the partial figure is separately labelled and excludes the carried position, never silently including it
        partial = metric(total, "portfolio_value_priced_holdings", "REPORTING")
        self.assertEqual(partial.exact, F(2500))

    def test_once_the_source_split_is_appended_the_carried_units_are_valued_normally_10000(self):
        from domain.ledger import SplitRatio  # noqa: PLC0415

        L = self.probe(lambda ledger: ledger.add(A1, EventType.SPLIT, EX, USD, listing_id=LISTING, split_ratio=SplitRatio(Decimal(4), Decimal(1))))
        port = market()
        sup = detect(L, port)
        self.assertEqual(sup, ())  # the split is recorded (ALREADY_RECORDED/MATCHED): nothing to suppress, nothing to carry
        res = value(L, D(2025, 2, 6), port, sup)
        total = metric(res, "portfolio_value", "REPORTING")
        # A1: 200 split units - 50 transferred = 150 x 37.50 = 5,625; A2: 50 x 37.50 = 1,875; cash 2,500: 10,000
        self.assertEqual((total.exact, total.result.sufficiency_state), (F(10000), AVAILABLE))
        # lineage only (Ruling 6.4c item 7): the transfer was recorded BEFORE the split, so its quantity is read in post-split units; no state effect
        self.assertIn("TRANSFER_AFTER_UNRECORDED_SPLIT", metric(res, "holding_value", "NATIVE", account=A2).details)

    def test_the_receiver_stays_suppressed_until_the_day_the_last_tainted_unit_is_relieved(self):
        """performance/1.5 Ruling 1.1a (CP3d): the lot-book rule REPLACES the conservative "through the first zero-end day": the sale of 02-07 relieves the tainted lot, so the
        receiver's end-of-day book on 02-07 is empty and the suppression of its valuation ends THERE ([02-05, 02-07)); the sale's own relief (02-07) is event-tainted."""
        from performance.taint import carried_suppressions  # noqa: PLC0415

        def sell_all(ledger):
            ledger.add(A2, EventType.SELL, D(2025, 2, 7), USD, listing_id=LISTING, quantity=Decimal(50), amount=Money(Decimal(1875), USD))

        L = self.probe(sell_all)
        port = market()
        sup = detect(L, port)
        from domain.replay import live_events  # noqa: PLC0415
        (carried,) = carried_suppressions(live_events(L.rows, L.version), sup)
        self.assertEqual((carried.account_id, carried.first_date, carried.end_exclusive), (A2, D(2025, 2, 5), D(2025, 2, 7)))  # through 02-06: 02-07 ends at 0 tainted units
        self.assertTrue(carried.covers(D(2025, 2, 6)) and not carried.covers(D(2025, 2, 7)))
        from performance.taint import carried_taint  # noqa: PLC0415

        taint = carried_taint(live_events(L.rows, L.version), sup)
        sale = [i.event.event_id for i in L.rows if i.event.event_type is EventType.SELL and i.event.account_id == A2]
        legs = [i.event.event_id for i in L.rows if i.event.event_type is EventType.TRANSFER_IN and i.event.account_id == A2]
        self.assertEqual(set(taint.event_taints), set(sale) | set(legs))  # the events of that day stay suppressed (Ruling 1.1a item 3), and the receiving leg carries the taint (CP3-18, Ruling 6.4c rule 6)

    def test_it_is_carried_through_every_hop(self):
        from performance.taint import carried_suppressions  # noqa: PLC0415
        from domain.replay import live_events  # noqa: PLC0415

        L = base_ledger()
        internal_transfer(L, D(2025, 2, 5), A1, A2)
        internal_transfer(L, D(2025, 2, 6), A2, A3)
        sup = detect(L, market())
        carried = carried_suppressions(live_events(L.rows, L.version), sup)
        self.assertEqual([c.account_id for c in carried], [A2, A3])
        # A2 holds the tainted lot at the end of 02-05 and has moved it on by the end of 02-06, so its suppression is [02-05, 02-06); A3 holds them and is open-ended
        self.assertEqual({c.account_id: (c.first_date, c.end_exclusive) for c in carried}, {A2: (D(2025, 2, 5), D(2025, 2, 6)), A3: (D(2025, 2, 6), None)})

    def test_a_conflict_date_source_with_the_ledger_split_early_ends_where_the_market_catches_up(self):
        from performance.taint import carried_suppressions  # noqa: PLC0415
        from domain.replay import live_events  # noqa: PLC0415

        L = internal_transfer(base_ledger(), D(2025, 2, 5))
        # F8-B CONFLICT_DATE with Y = 2025-02-03 (the ledger's split date) < X = 2025-02-10 (the ex-date): the suppression is [Y, X)
        s = SuppressionInput(A1, LISTING, D(2025, 2, 3), D(2025, 2, 10), "SOURCE_CONFLICT", "split dated off its ex-date", D(2025, 2, 10), "CONFLICT_DATE")
        (carried,) = carried_suppressions(live_events(L.rows, L.version), (s,))
        self.assertEqual((carried.account_id, carried.first_date, carried.end_exclusive), (A2, D(2025, 2, 5), D(2025, 2, 10)))

    def test_a_transfer_before_the_suppression_starts_carries_nothing(self):
        from performance.taint import carried_suppressions  # noqa: PLC0415
        from domain.replay import live_events  # noqa: PLC0415

        L = internal_transfer(base_ledger(), D(2025, 1, 31))
        sup = detect(L, market())
        self.assertEqual(carried_suppressions(live_events(L.rows, L.version), sup), ())

    def test_in_kind_flows_of_tainted_units_are_insufficient_and_source_conflict(self):
        L = self.probe(lambda ledger: transfer_out(ledger, D(2025, 2, 6), account=A2))
        port = market()
        sup = detect(L, port)
        res = window(L, D(2025, 2, 6), port, sup, account_scope=A2, start=D(2025, 2, 4))
        insufficient_conflict(self, metric(res, "gain_absolute"))  # A2's outflow of the carried units is an in-kind flow of tainted units


# ===== CP3-3 / Ruling 4.8 item 4: synthetic evidence drives suppression and never appends ======================================================

class SyntheticEvidenceTests(unittest.TestCase):
    def test_the_review_probe_a_synthetic_corroborated_split_suppresses_instead_of_valuing_1875(self):
        L = base_ledger()
        port = market("synthetic")
        report = f8b.confirm_splits(_fake_ledger(L), port, ca.PORTFOLIO, (LISTING,), D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {LISTING: USD},
                                    calendars=ca.CALENDARS, exchange_of=ca.exchange_of, dry_run=True)
        (outcome,) = report.outcomes
        self.assertEqual(outcome.decision, f8b.SplitDecision.NOT_RECORDED_APPEND_BARRED)
        (finding,) = report.findings
        self.assertTrue(finding.synthetic)
        sup = detect(L, port)
        self.assertEqual(len(sup), 1)
        # the reviewer's number: AVAILABLE 1,875 (holding) and AVAILABLE -0.5625 (TWR). Now INSUFFICIENT_DATA + SOURCE_CONFLICT.
        holding = metric(value(L, D(2025, 2, 3), port, sup), "holding_value", "NATIVE")
        insufficient_conflict(self, holding)
        insufficient_conflict(self, metric(window(L, D(2025, 2, 3), port, sup), "return_twr"))
        self.assertEqual(metric(value(L, D(2025, 2, 3), port, ()), "holding_value", "NATIVE").exact, F(1875))  # the probe number, were detection off

    def test_synthetic_evidence_never_appends_dry_run_or_not(self):
        port = market("synthetic")
        for dry in (True, False):
            ledger = ca.ledger_with_holdings()
            report = f8b.confirm_splits(ledger, port, ca.PORTFOLIO, (LISTING,), D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {LISTING: USD},
                                        calendars=ca.CALENDARS, exchange_of=ca.exchange_of, dry_run=dry)
            self.assertEqual(ledger.appended, [], dry)
            self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.NOT_RECORDED_APPEND_BARRED], dry)
            self.assertEqual(len(report.suppressions), 1, dry)

    def test_the_append_bar_depends_on_the_evidence_not_on_other_synthetic_files_in_m(self):
        # M holds synthetic QUOTE files (every probe market does) but the corporate-action evidence is REAL: the split is appended by a normal run
        port = market("real")
        self.assertTrue(port.contains_synthetic)
        ledger = ca.ledger_with_holdings()
        report = f8b.confirm_splits(ledger, port, ca.PORTFOLIO, (LISTING,), D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {LISTING: USD},
                                    calendars=ca.CALENDARS, exchange_of=ca.exchange_of)
        self.assertEqual(len(ledger.appended), 1)
        self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.APPENDED])

    def test_corroboration_happens_within_one_world(self):
        readings = [ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1), usage=ca.SYN), ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1), usage=ca.REAL)]
        report = f8b.confirm_splits(ca.ledger_with_holdings(), ca.port_with(readings), ca.PORTFOLIO, (LISTING,), D(2025, 1, 1), D(2025, 12, 31), ca.POLICY,
                                    {LISTING: USD}, calendars=ca.CALENDARS, exchange_of=ca.exchange_of, dry_run=True)
        self.assertEqual([f.status for f in report.findings], [f8b.Corroboration.SYNTHETIC_MIXED])
        self.assertEqual((report.outcomes, report.suppressions), ((), ()))


# ===== CP3-4: detection is composed with computation; nothing defaults to "no suppressions" ====================================================

class DetectionIsComposedTests(unittest.TestCase):
    """The service entries read the ledger at a pin (here stubbed: the database path is covered by the opt-in tests), run F8-B read-only and compute.

    CHOICE (CP3-4): the pure engine entries REQUIRE `suppressions` (a missing argument is a TypeError, an empty tuple is an explicit statement), and the SERVICE
    entries have no `suppressions` parameter at all: they run detection themselves, so a caller cannot forget it. The manifest says which (`split_detection`)."""

    def run_service(self, L, port, entry="value", **kw):
        from unittest import mock  # noqa: PLC0415

        with mock.patch.object(svc, "_pin", return_value=(L.version, tuple(L.rows))):
            if entry == "value":
                return svc.compute_for_portfolio(None, ca.PORTFOLIO, kw.pop("day", D(2025, 2, 3)), USD, port, Ident(), MARKET_CONVENTIONS, PERF,
                                                 policy=ca.POLICY, **kw)
            return svc.compute_window_for_portfolio(None, ca.PORTFOLIO, WindowSpec(WindowRule.CUSTOM, None, D(2025, 1, 31)), kw.pop("end", D(2025, 2, 3)), USD,
                                                    port, Ident(), MARKET_CONVENTIONS, PERF, policy=ca.POLICY, **kw)

    def test_the_review_probe_through_the_service_is_no_longer_available_1875(self):
        L = base_ledger()
        port = market("real", real_quotes=True)
        self.assertFalse(port.contains_synthetic)
        res = self.run_service(L, port)
        insufficient_conflict(self, metric(res, "holding_value", "NATIVE"))
        self.assertEqual(res.manifest.split_detection, "F8B_DRY_RUN")
        self.assertNotEqual(res.manifest.split_suppressions_digest, pk.compute(L.rows, L.version, D(2025, 2, 3), USD, port, Ident(), MARKET_CONVENTIONS, PERF,
                                                                               suppressions=()).manifest.split_suppressions_digest)
        self.assertEqual(L.version, 2)  # the dry run appended nothing

    def test_the_windows_entry_runs_the_same_detection(self):
        L = transfer_out(base_ledger(), D(2025, 2, 3))
        res = self.run_service(L, market("real", real_quotes=True), entry="window")
        for metric_id in ("gain_absolute", "return_twr"):
            insufficient_conflict(self, metric(res, metric_id))
        self.assertEqual(res.manifest.split_detection, "F8B_DRY_RUN")

    def test_a_pure_entry_without_suppressions_is_a_type_error_and_the_service_has_no_such_parameter(self):
        import inspect  # noqa: PLC0415
        from performance import engine  # noqa: PLC0415

        L = base_ledger()
        port = market()
        with self.assertRaises(TypeError):
            engine.compute(L.rows, L.version, D(2025, 2, 3), USD, port, Ident(), MARKET_CONVENTIONS, PERF)
        with self.assertRaises(TypeError):
            engine.compute_window(L.rows, L.version, WindowSpec(WindowRule.CUSTOM, None, D(2025, 1, 31)), D(2025, 2, 3), USD, port, Ident(), MARKET_CONVENTIONS, PERF)
        res = pk.compute(L.rows, L.version, D(2025, 2, 3), USD, port, Ident(), MARKET_CONVENTIONS, PERF, suppressions=())
        with self.assertRaises(TypeError):
            engine.reproduce(res.manifest, res.result_digest, L.rows, port, Ident(), MARKET_CONVENTIONS, PERF)
        for entry in (svc.compute_for_portfolio, svc.compute_window_for_portfolio, svc.compute_current_for_portfolio):
            names = inspect.signature(entry).parameters
            self.assertNotIn("suppressions", names)
            self.assertIn("policy", names)
            self.assertEqual(names["policy"].default, inspect.Parameter.empty)  # the confirmation policy is a human's registration: no default either
        self.assertEqual(res.manifest.split_detection, "CALLER_SUPPLIED")  # a direct call says so in its manifest

    def test_the_read_only_access_cannot_append_even_where_a_normal_run_would(self):
        L = base_ledger()
        before = list(L.rows)
        self.run_service(L, market("real", real_quotes=True))
        self.assertEqual(L.rows, before)
        with self.assertRaises(svc.WriteRefusedError):
            svc.PinnedLedgerAccess(L.version, L.rows).append(object())

    def test_a_synthetic_market_data_version_is_refused_for_a_user_portfolio_with_an_explicit_state(self):
        L = base_ledger()
        for name, port in (("synthetic evidence", market("synthetic", real_quotes=True)), ("synthetic quotes, real evidence", market("real")),
                           ("synthetic quotes, no evidence", market(None))):
            self.assertTrue(port.contains_synthetic, name)
            for entry in ("value", "window"):
                res = self.run_service(L, port, entry=entry)
                (m,) = res.metrics
                self.assertEqual((m.result.value, m.result.sufficiency_state), (None, INSUFFICIENT), name)
                self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, m.details, name)
                self.assertTrue(res.manifest.synthetic and m.synthetic, name)
            # the engine called directly (tests, fixtures) stays allowed and says synthetic
            direct = pk.compute(L.rows, L.version, D(2025, 2, 3), USD, port, Ident(), MARKET_CONVENTIONS, PERF, suppressions=())
            self.assertTrue(direct.manifest.synthetic)
            self.assertIsNotNone(metric(direct, "holding_value", "NATIVE").exact)


# ===== CP3-5: the size guard ===================================================================================================================

class SizeGuardTests(unittest.TestCase):
    def test_the_reviewers_probe_five_years_with_a_flow_every_day_is_available(self):
        import test_performance_cp3b as t3b  # noqa: PLC0415
        from performance import numerics  # noqa: PLC0415
        from performance.conventions import FlowClass  # noqa: PLC0415
        from performance.returns import twr_segments  # noqa: PLC0415

        start = D(2020, 1, 1)
        days = [start + datetime.timedelta(days=i) for i in range(1827)]  # five years, a flow on EVERY day
        table = {}
        for i, d in enumerate(days):
            usd, hkd = 10800 + (i * 104729) % 300, 84000 + (i * 7919) % 900  # ECB-like quotes with 4 decimals: a cross is a ratio of two 5-digit integers
            table[d] = F(1_000_000 + 13 * i + (i * i) % 977) * F(usd, hkd)
        flows = tuple(t3b.vf(d, FlowClass.EXTERNAL_INFLOW_CASH, 100) for d in days[1:])
        out = twr_segments(days[0], days[-1], flows, t3b.valuations(table), PERF)
        self.assertEqual(out.valued.state, AVAILABLE)  # was INSUFFICIENT_DATA + CALCULATION_ERROR (VALUE_NOT_REPRESENTABLE) at the old 2**15-bit limit
        self.assertIsNone(out.valued.reason)
        exact = out.valued.exact
        widest = max(exact.numerator.bit_length(), exact.denominator.bit_length())
        self.assertGreater(widest, 1 << 15)  # the probe really exceeds the old limit
        self.assertLess(widest, numerics.MAX_BITS)
        self.assertTrue(numerics.within_bounds(exact))

    def test_the_bound_is_derived_not_chosen_and_still_stops_a_runaway(self):
        from performance import numerics  # noqa: PLC0415

        self.assertEqual(numerics.MAX_BITS, 1 << 27)
        self.assertTrue(numerics.within_bounds(F(1, (1 << (numerics.MAX_BITS - 1)))))
        self.assertFalse(numerics.within_bounds(F(1, 1 << numerics.MAX_BITS)))  # a denominator of MAX_BITS + 1 bits is refused


# ===== CP3-6: the identity registry is a cited input; the engine's source is pinned ============================================================

class IdentityRegistryTests(unittest.TestCase):
    def test_a_resolver_that_maps_the_listing_to_another_exchange_is_named_not_reported_as_reproduced(self):
        L = base_ledger()
        port = market(None)
        res = value(L, D(2025, 1, 31), port, ())
        self.assertNotEqual(res.manifest.identity_digest, "")
        args = (res.manifest, res.result_digest, L.rows, port)
        ok = pk.reproduce(*args, Ident(), MARKET_CONVENTIONS, PERF)
        self.assertEqual(ok.status, ReproductionStatus.REPRODUCED)
        other = pk.reproduce(*args, Ident("XNAS"), MARKET_CONVENTIONS, PERF)  # the review's probe: H mapped to XNAS instead of its exchange
        self.assertEqual(other.status, ReproductionStatus.IDENTITY_MISMATCH)
        # with NO expected digest the old code said REPRODUCED even when the answer differed; the status now says nothing was compared
        none = pk.reproduce(res.manifest, None, L.rows, port, Ident(), MARKET_CONVENTIONS, PERF)
        self.assertEqual(none.status, ReproductionStatus.RESULT_NOT_COMPARED)
        self.assertFalse(none.reproduced)
        self.assertEqual(pk.reproduce(res.manifest, None, L.rows, port, Ident("XNAS"), MARKET_CONVENTIONS, PERF).status, ReproductionStatus.IDENTITY_MISMATCH)

    def test_the_digest_covers_the_facts_asked_for_and_is_in_the_manifest_id(self):
        L = base_ledger()
        port = market(None)
        a = value(L, D(2025, 1, 31), port, ())
        b = value(L, D(2025, 1, 31), port, (), ident=Ident("XNAS"))  # a different exchange is a different input
        # a fact is recorded only where the computation asked for it: an UNPRICED holding asks for the listing's trading currency (its native currency)
        unpriced = market(None, prices={D(2020, 1, 1): "1.00"})

        class Euro(Ident):
            def trading_currency(self, listing_id):
                return CurrencyCode("EUR")

        v1 = value(L, D(2025, 1, 31), unpriced, ())
        v2 = value(L, D(2025, 1, 31), unpriced, (), ident=Euro())
        self.assertNotEqual(v1.manifest.identity_digest, v2.manifest.identity_digest)
        self.assertNotEqual(a.manifest.identity_digest, b.manifest.identity_digest)
        self.assertNotEqual(a.manifest.manifest_id, b.manifest.manifest_id)


# (the engine source-hash pins, ENGINE_PINS, and their negative control are in test_performance_boundaries, next to the CP2 ANALYTICS_PINS they follow)


# ===== CP3-7: a foreign dividend receivable needs that day's fixing =============================================================================

class ReceivableCurrentModeTests(unittest.TestCase):
    T = datetime.datetime(2025, 4, 2, 13, 0, tzinfo=datetime.timezone.utc)  # 15:00 Berlin: before the 16:00 ECB publication

    def world(self):
        return pk.world_w()

    def ledger(self, w, receivable_currency=pk.HKD, amount="780"):
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), pk.USD, amount=Money(Decimal(6000), pk.USD))
        # a dividend declared with an ex-date of 03-31 and paid on 04-04 is a receivable on 04-01..04-03 (Ruling 8.1)
        L.add(pk.A1, EventType.DIVIDEND, D(2025, 4, 4), receivable_currency, listing_id=w.h, amount=Money(Decimal(amount), receivable_currency), ex_date=D(2025, 3, 31))
        return L

    def test_the_review_probe_a_hkd_receivable_pushes_d_c_back_to_the_last_published_fixing(self):
        from performance import current  # noqa: PLC0415

        w = self.world()
        L = self.ledger(w)
        chosen = current.choose_current_date(self.T, L.rows, L.version, w.calendars, w.ident.exchange_mic, pk.USD, w.ident.trading_currency)
        self.assertEqual(chosen.date, D(2025, 4, 1))  # was 2025-04-02: translated at a fixing that had not been published
        res = compute_current(L.rows, L.version, self.T, pk.USD, w.ident, w.market_at, PERF, suppressions=())
        self.assertEqual(res.manifest.as_of, D(2025, 4, 1))
        # 04-01 fixing: HKD->USD = 1.0800/8.4000 = 9/70; 780 x 9/70 = 702/7. (The 04-02 value would have been 780 x 5/39 = 100.)
        self.assertEqual(metric(res, "receivable_value", "REPORTING").exact, F(702, 7))
        self.assertEqual(metric(res, "portfolio_value", "REPORTING").exact, F(6000) + F(702, 7))  # kills M8 (receivables dropped from the total)

    def test_a_reporting_currency_receivable_needs_no_fixing(self):
        from performance import current  # noqa: PLC0415

        w = self.world()
        L = self.ledger(w, receivable_currency=pk.USD, amount="100")
        chosen = current.choose_current_date(self.T, L.rows, L.version, w.calendars, w.ident.exchange_mic, pk.USD, w.ident.trading_currency)
        self.assertEqual(chosen.date, D(2025, 4, 2))  # the listing H is not held, only USD amounts: nothing waits for the ECB

    def test_the_receivable_is_part_of_the_total_in_historical_mode_too_m8(self):
        w = self.world()
        L = self.ledger(w)
        res = pk.compute(L.rows, L.version, D(2025, 4, 2), pk.USD, w.store, w.ident, w.market, PERF)
        # 04-02: 780 x 5/39 = 100; the total is 6,000 + 100, the breakdown has the receivable as a line, and the lineage has its dates
        r = metric(res, "receivable_value", "REPORTING")
        self.assertEqual(r.exact, F(100))
        total = metric(res, "portfolio_value", "REPORTING")
        self.assertEqual((total.exact, total.result.value), (F(6100), Decimal("6100.00")))
        self.assertIn(("ex_date", "2025-03-31"), r.lineage)
        self.assertIn("receivable", " ".join(line for line, _shown, _exact in total.breakdown).lower())
        # on the pay date the receivable is gone (ex_date <= day < pay date): the cash arrives with the DIVIDEND event itself
        paid = pk.compute(L.rows, L.version, D(2025, 4, 4), pk.USD, w.store, w.ident, w.market, PERF)
        self.assertEqual([m for m in paid.metrics if m.metric_id == "receivable_value"], [])


# ===== CP3-8: the four surviving mutants ========================================================================================================

class SurvivingMutantTests(unittest.TestCase):
    def test_m1_an_in_kind_inflow_is_end_of_day_not_start_of_day_cash(self):
        """A1 holds 10 units (bought for 1,000 with 2,000 deposited). Close 100.00 on 01-31 and 110.00 on 02-03. On 02-03 another 10 units arrive in kind
        (valued 10 x 110 = 1,100). V(01-31) = 1,000 + 1,000 = 2,000; V(02-03) = 1,000 + 20 x 110 = 3,200.
        END timing (Ruling 4.2): factor = (V - I^K) / V(d-1) = (3,200 - 1,100) / 2,000 = 21/20, TWR = 1/20. Start-of-day cash would give 3,200 / 3,100 (TWR 1/31)."""
        L = pk.Ledger()
        L.add(A1, EventType.DEPOSIT, D(2025, 1, 29), USD, amount=Money(Decimal(2000), USD))
        L.add(A1, EventType.BUY, D(2025, 1, 29), USD, listing_id=LISTING, quantity=Decimal(10), amount=Money(Decimal(1000), USD))
        L.add(A1, EventType.TRANSFER_IN, D(2025, 2, 3), USD, listing_id=LISTING, quantity=Decimal(10))
        port = market(None, prices={D(2025, 1, 30): "100.00", D(2025, 1, 31): "100.00", D(2025, 2, 3): "110.00"})
        res = window(L, D(2025, 2, 3), port, ())
        self.assertEqual(metric(res, "return_twr").exact, F(1, 20))
        self.assertEqual(metric(res, "gain_absolute").exact, F(100))  # 3,200 - 2,000 - 1,100
        self.assertNotEqual(metric(res, "return_twr").exact, F(1, 31))

    def test_m2_the_stale_weight_uses_gross_values_when_a_component_is_negative(self):
        """500 USD deposited and 10 units bought for 1,000: cash -500. The close of 100.00 is on 01-31 and the value date is 02-05: three missed sessions, LIMITED.
        Stale component 1,000; gross = 1,000 + |-500| = 1,500; weight = 1,000/1,500 = 2/3 (a signed total of 500 would give 2, a weight above 100%)."""
        L = pk.Ledger()
        L.add(A1, EventType.DEPOSIT, D(2025, 1, 29), USD, amount=Money(Decimal(500), USD))
        L.add(A1, EventType.BUY, D(2025, 1, 29), USD, listing_id=LISTING, quantity=Decimal(10), amount=Money(Decimal(1000), USD))
        port = market(None, prices={D(2025, 1, 30): "100.00", D(2025, 1, 31): "100.00"})
        total = metric(value(L, D(2025, 2, 5), port, ()), "portfolio_value", "REPORTING")
        self.assertEqual((total.exact, total.result.sufficiency_state, total.result.reason_code), (F(500), LIMITED, ReasonCode.STALE_DATA))
        self.assertEqual(total.stale_weight, F(2, 3))

    def test_m9_the_state_of_the_value_the_day_before_a_flow_day_is_part_of_the_twr_state(self):
        import test_performance_cp3b as t3b  # noqa: PLC0415
        from performance.conventions import FlowClass  # noqa: PLC0415
        from performance.returns import twr_segments  # noqa: PLC0415
        from performance.states import Valued  # noqa: PLC0415
        from performance.results import Cause  # noqa: PLC0415

        table = {D(2025, 3, 31): F(100), D(2025, 4, 1): F(101), D(2025, 4, 2): F(112), D(2025, 4, 3): F(113)}
        flows = (t3b.vf(D(2025, 4, 2), FlowClass.EXTERNAL_INFLOW_CASH, 10),)

        def valuation(day):
            if day == D(2025, 4, 1):  # V(D_j - 1) alone is LIMITED (stale)
                return Valued(LIMITED, "STALE_DATA", table[day], (Cause("v@04-01", "LIMITED", "STALE_DATA", "3 sessions"),))
            return Valued(AVAILABLE, None, table[day], ())

        out = twr_segments(D(2025, 3, 31), D(2025, 4, 3), flows, valuation, PERF)
        self.assertEqual((out.valued.state, out.valued.reason), (LIMITED, "STALE_DATA"))  # Ruling 5.2: V(D_j - 1) is an input of the TWR, so its state is
        # (112 / (101 + 10)) x (101/100 ... the exact value is unchanged by the state: 1 + TWR = (101/100) x (112/111) x (113/112)
        self.assertEqual(out.valued.exact, F(101, 100) * F(112, 111) * F(113, 112) - 1)


# ===== performance/1.2 and 1.3: Q3, Q5, Q7 ======================================================================================================

class RulingQuestionsTests(unittest.TestCase):
    def test_q3_a_limited_total_with_zero_gross_value_states_no_stale_share(self):
        from performance.results import Cause  # noqa: PLC0415
        from performance.states import Valued  # noqa: PLC0415
        from performance.valuation import total_of  # noqa: PLC0415

        zero = Valued(LIMITED, "STALE_DATA", F(0), (Cause("c", "LIMITED", "STALE_DATA", "3 sessions"),))
        total = total_of([zero, Valued(AVAILABLE, None, F(0), ())], PERF, "t")
        self.assertEqual((total.state, total.reason, total.exact, total.stale_weight), (LIMITED, "STALE_DATA", F(0), None))
        self.assertTrue(any("STALE_SHARE_UNDEFINED" in c.detail for c in total.causes))  # the lineage cause (Ruling 1.4 item 2)
        # a non-zero gross value still states the weight
        self.assertEqual(total_of([Valued(LIMITED, "STALE_DATA", F(3), (Cause("c", "LIMITED", "STALE_DATA", "x"),)), Valued(AVAILABLE, None, F(1), ())],
                                  PERF, "t").stale_weight, F(3, 4))

    def test_q5_identity_lineage_says_which_ran_and_what_each_said(self):
        L = base_ledger()
        port = market(None)
        v = value(L, D(2025, 1, 31), port, ())
        self.assertEqual(v.manifest.identities_run, ("I-1",))
        self.assertIn(("identity:I-1", "PASS"), metric(v, "portfolio_value", "REPORTING").lineage)
        off = window(L, D(2025, 1, 31), port, (), start=D(2025, 1, 30))
        self.assertEqual(off.manifest.identities_run, ("I-6",))  # CP3c: I-6 runs whenever an MWR and a TWR are computed over the same window
        self.assertIn(("identity:I-2", "NOT_RUN"), metric(off, "return_twr").lineage)
        self.assertIn(("identity:I-3", "NOT_RUN"), metric(off, "gain_absolute").lineage)
        on = window(L, D(2025, 1, 31), port, (), start=D(2025, 1, 30), verify=True)
        self.assertEqual(on.manifest.identities_run, ("I-2", "I-3", "I-6"))
        self.assertIn(("identity:I-2", "PASS"), metric(on, "return_twr").lineage)
        self.assertIn(("identity:I-3", "PASS"), metric(on, "gain_absolute").lineage)
        self.assertNotEqual(on.manifest.manifest_id, off.manifest.manifest_id)  # the question differs: which identities were asked for is part of it

    def test_q5_an_identity_that_cannot_run_because_an_interior_day_has_no_value_is_not_computable_not_a_pass(self):
        L = base_ledger()
        port = market(None, prices={D(2025, 1, 31): "150.00", D(2025, 2, 10): "150.00"})
        # 02-03 .. 02-07 are missed sessions: the 5th is withheld (STALE_BEYOND_LIMIT), so there are interior days with no value; B and E are priced
        res = window(L, D(2025, 2, 10), port, (), start=D(2025, 1, 31), verify=True)
        twr = metric(res, "return_twr")
        self.assertIsNotNone(twr.exact)
        self.assertIn(("identity:I-2", "NOT_COMPUTABLE"), twr.lineage)

    def test_q7_a_negative_growth_factor_is_an_engine_fault_calculation_error(self):
        from performance.returns import annualize  # noqa: PLC0415
        from performance.states import Valued  # noqa: PLC0415

        out = annualize(Valued(AVAILABLE, None, F(-3, 2), ()), F(2), PERF)  # 1 + R = -1/2: unreachable through Ruling 5.3, so reaching it is a fault
        self.assertEqual((out.valued.state, out.valued.reason, out.valued.exact), (INSUFFICIENT, "CALCULATION_ERROR", None))
        self.assertIn("NEGATIVE_GROWTH_FACTOR", out.details)
        total_loss = annualize(Valued(AVAILABLE, None, F(-1), ()), F(2), PERF)
        self.assertIn("TOTAL_LOSS", total_loss.details)
        self.assertNotEqual(total_loss.valued.reason, "CALCULATION_ERROR")  # a total loss is a real outcome, not a fault


# ===== performance/1.2 Ruling 1.7: M_t through the real CP2 build path ========================================================================

class DerivedReleaseTests(unittest.TestCase):
    def test_m_t_is_the_files_retrieved_by_t_rebuilt_through_the_cp2_build_path(self):
        import dataclasses  # noqa: PLC0415
        import json  # noqa: PLC0415
        import marketdata_exit_kit as x  # noqa: PLC0415
        from marketdata.files import FileStore  # noqa: PLC0415
        from marketdata.manifest import FileManifest  # noqa: PLC0415
        from performance_service.derived_release import DerivedReleaseView  # noqa: PLC0415

        world = x.build_world("formats")
        self.addCleanup(world.close)
        files = FileStore(world.root)
        # make ONE file (the HK quotes) retrieved a day after the others
        hk = next(m for m in world.manifests if m.source_identifiers == ("00700",))
        later = hk.retrieval_time + datetime.timedelta(days=1)
        manifest_path = files.index()[hk.file_sha256]
        manifest_path.write_text(dataclasses.replace(hk, retrieval_time=later).to_json(), encoding="utf-8")
        release = dataclasses.replace(world.release)
        view = DerivedReleaseView(release, files, files.load_registry(), world.adapters, world.ident, catalog_calendars={})
        t = hk.retrieval_time + datetime.timedelta(hours=1)
        mt = view.view(t)
        self.assertEqual((mt.parent_release_id, mt.excluded_files, mt.instant), (release.release_id, (hk.file_sha256,), t))
        self.assertNotEqual(mt.port.release_id(), release.release_id)  # `M_t` has its own id
        hk_id = x.lid(world.ident, "0700", "XHKG")
        self.assertEqual(world.store.release_id(), release.release_id)  # the parent is the world's own release
        self.assertEqual(mt.port.quotes(hk_id, D(2025, 1, 1), D(2025, 1, 31)).readings, ())  # the excluded file supplies nothing to M_t ...
        self.assertEqual(len(view.view(later + datetime.timedelta(hours=1)).port.quotes(hk_id, D(2025, 1, 1), D(2025, 1, 31)).readings), 2)  # ... and does to a later one
        # a later instant includes it; the derived view is a deterministic function of (M, t)
        full = view.view(later + datetime.timedelta(hours=1))
        self.assertEqual(full.excluded_files, ())
        self.assertEqual(view.view(t).port.release_id(), mt.port.release_id())
        # and the engine runs over it: every CP2 step has been re-run over exactly these files
        ledger = pk.Ledger().add(A1, EventType.TRANSFER_IN, D(2024, 12, 20), CurrencyCode("HKD"), listing_id=hk_id, quantity=Decimal(100))
        res = compute_current(ledger.rows, ledger.version, t, USD, world.ident, view, PERF, suppressions=())
        self.assertEqual(res.manifest.excluded_files, (hk.file_sha256,))
        self.assertEqual(res.manifest.parent_release_id, release.release_id)


def _fake_ledger(L):
    ledger = ca.FakeLedger()
    for row in L.rows:
        ledger.add(row.event)
    return ledger


if __name__ == "__main__":
    unittest.main()
