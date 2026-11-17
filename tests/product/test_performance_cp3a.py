"""CP3a: the performance engine's spine and valuation (tech plan 16, 16.14).

Every expected value is derived by hand from the synthetic CP2 exit-kit facts, with the arithmetic shown:

  account holds (2025-01-03): AAPL 10, 0700 100, 600519 2
  cash: deposits of 100,000 in each of USD, HKD and CNY, minus the purchases
        USD 100,000 - 1,500 = 98,500;  HKD 100,000 - 33,000 = 67,000;  CNY 100,000 - 3,000 = 97,000
  closes of 2025-01-03: AAPL 151.10, 0700 332.6, 600519 1502.00
  ECB fixings of 2025-01-03 (units per EUR): USD 1.0810, HKD 8.4100, CNY 7.8100
  HKD->USD = 1.0810 / 8.4100 = 1081/8410;  CNY->USD = 1.0810 / 7.8100 = 1081/7810   (reporting currency USD)

Nothing is asserted from engine output: each legs' exact rational is written below from these facts.
"""

import dataclasses
import datetime
import os
import subprocess
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402
import pg_market_kit as pk  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from domain.replay import SequencedEvent, live_events, reconstruct  # noqa: E402
from marketdata.consumption import assemble_valuation_inputs  # noqa: E402
from marketdata.manifest import SourceRegistry  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from performance import numerics  # noqa: E402
from performance.conventions import FlowClass, FlowRow, FlowTable, performance_flow_table  # noqa: E402
from performance.engine import performance_conventions  # noqa: E402
import performance_kit as _kit  # noqa: E402
compute, reproduce = _kit.compute, _kit.reproduce  # the engine's pure entries with `suppressions` STATED (none), see performance_kit
from performance.rounding import PerformanceRounding  # noqa: E402
from performance.inputs import SuppressionInput, ValuationMode  # noqa: E402
from performance.ledger_view import classify_events, ledger_digest  # noqa: E402
from performance.manifest import ReproductionStatus  # noqa: E402
from performance.results import Cause, ComputedMetric, WindowUsed  # noqa: E402
from performance.valuation import value_portfolio  # noqa: E402
from performance_service.service import ReadOnlyLedgerAccess, WriteRefusedError, suppressions_from_report  # noqa: E402
from product_contract.metric_state import MetricResult  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
USD, HKD, CNY = CurrencyCode("USD"), CurrencyCode("HKD"), CurrencyCode("CNY")
ACCOUNT = uuid.UUID(int=1)
AS_OF, LATER = x.AS_OF, x.LATER  # 2025-01-03 and 2025-01-06
AVAILABLE, LIMITED, INSUFFICIENT = (SufficiencyState.AVAILABLE, SufficiencyState.LIMITED,
                                    SufficiencyState.INSUFFICIENT_DATA)

# the exact rationals, by hand (see the module docstring)
AAPL_NATIVE = Fraction(1511)                       # 10 x 151.10
HK_NATIVE = Fraction(33260)                        # 100 x 332.6
CN_NATIVE = Fraction(3004)                         # 2 x 1502.00
HK_REPORTING = Fraction(3595406, 841)              # 33,260 x 1081/8410 = 3,326 x 1081 / 841 ; 3,326 x 1,081 = 3,595,406
CN_REPORTING = Fraction(1623662, 3905)             # 3,004 x 1081/7810 = 1,502 x 1,081 / 3,905 ; 1,502 x 1,081 = 1,623,662
HK_CASH_REPORTING = Fraction(7242700, 841)         # 67,000 x 1081/8410 = 6,700 x 1,081 / 841 ; 6,700 x 1,081 = 7,242,700
CN_CASH_REPORTING = Fraction(10485700, 781)        # 97,000 x 1081/7810 = 9,700 x 1,081 / 781 ; 9,700 x 1,081 = 10,485,700
NATIVE_TOTALS = {"USD": Fraction(100011), "HKD": Fraction(100260), "CNY": Fraction(100004)}  # 1,511 + 98,500 ; 33,260 + 67,000 ; 3,004 + 97,000
# reporting total = 1,511 + 98,500 + (3,595,406 + 7,242,700)/841 + (1,623,662 x 5 + 10,485,700 x 5)/3,905
#                 = 100,011 + 10,838,106/841 + 54,052,162/3,905   (1,623,662 + 52,428,500 = 54,052,162)
REPORTING_TOTAL = Fraction(100011) + Fraction(10838106, 841) + Fraction(54052162, 3905)


ROUNDING_ID = "performance/1.12#2.2-2.4"


def ledger_events(ident, account=ACCOUNT, base=500) -> List[SequencedEvent]:
    out, n = [], 0

    def add(**kw):
        nonlocal n
        n += 1
        out.append(SequencedEvent(n, LedgerEvent(event_id=uuid.UUID(int=base + n), account_id=account,
                                                 event_date=D(2024, 12, 20), **kw)))

    for ccy in (USD, HKD, CNY):
        add(event_type=EventType.DEPOSIT, currency=ccy, amount=Money(Decimal(100000), ccy))
    for ticker, mic, ccy, qty, cost in (("AAPL", "XNAS", USD, 10, 1500), ("0700", "XHKG", HKD, 100, 33000),
                                         ("600519", "XSHG", CNY, 2, 3000)):
        add(event_type=EventType.BUY, currency=ccy, listing_id=x.lid(ident, ticker, mic), quantity=Decimal(qty),
            amount=Money(Decimal(cost), ccy))
    return out


def run_world(world, events=None, as_of=AS_OF, perf=None, **kw):
    events = events if events is not None else ledger_events(world.ident)
    market = market11_conventions(world.built.calendars)
    return compute(events, max(e.ledger_seq for e in events) if events else 0, as_of, USD, world.store, world.ident,
                   market, perf or performance_conventions(), portfolio_id=uuid.UUID(int=900), **kw)


def valuation_of(world, events, as_of=AS_OF, suppressions=()):
    market = market11_conventions(world.built.calendars)
    version = max(e.ledger_seq for e in events)
    state = reconstruct(events, as_of, version)
    inputs = assemble_valuation_inputs(world.store, world.ident, state, as_of, USD, market)
    return value_portfolio(state, inputs, suppressions, performance_conventions())


def find(result, metric_id, view, **subject) -> ComputedMetric:
    want = tuple(sorted(subject.items()))
    hits = [m for m in result.metrics if m.metric_id == metric_id and m.view == view
            and all(p in m.subject for p in want)]
    assert len(hits) == 1, (metric_id, view, subject, len(hits))
    return hits[0]


class _Worlds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worlds = {fl: x.build_world(fl) for fl in x.FLAVOURS + (x.NO_CN_HK,)}
        for w in cls.worlds.values():
            cls.addClassCleanup(w.close)
        cls.w = cls.worlds["formats"]
        cls.ids = {t: x.lid(cls.w.ident, t, m) for t, m in (("AAPL", "XNAS"), ("0700", "XHKG"), ("600519", "XSHG"))}


class ExactValuationTests(_Worlds):
    def test_every_leg_and_total_equals_the_hand_derived_rational(self):
        val = valuation_of(self.w, ledger_events(self.w.ident))
        by_listing = {h.listing_id: h for h in val.holdings}
        aapl, hk, cn = (by_listing[self.ids[t]] for t in ("AAPL", "0700", "600519"))
        self.assertEqual((aapl.quantity, aapl.price, aapl.native.exact, aapl.reporting.exact),
                         (Fraction(10), Fraction("151.1"), AAPL_NATIVE, AAPL_NATIVE))  # USD: no FX
        self.assertEqual((hk.native.exact, hk.fx_rate, hk.reporting.exact), (HK_NATIVE, Fraction(1081, 8410), HK_REPORTING))
        self.assertEqual((cn.native.exact, cn.fx_rate, cn.reporting.exact), (CN_NATIVE, Fraction(1081, 7810), CN_REPORTING))
        cash = {c.currency.code: c for c in val.cash}
        self.assertEqual({k: (c.native.exact, c.reporting.exact) for k, c in cash.items()},
                         {"USD": (Fraction(98500), Fraction(98500)), "HKD": (Fraction(67000), HK_CASH_REPORTING),
                          "CNY": (Fraction(97000), CN_CASH_REPORTING)})
        self.assertEqual({c.code: v.exact for c, v in val.native_totals}, NATIVE_TOTALS)
        self.assertEqual(val.reporting_total.exact, REPORTING_TOTAL)
        # the by-hand sum of the legs agrees with the by-hand closed form
        self.assertEqual(AAPL_NATIVE + Fraction(98500) + HK_REPORTING + HK_CASH_REPORTING + CN_REPORTING + CN_CASH_REPORTING,
                         REPORTING_TOTAL)
        self.assertEqual(val.reporting_total.state, AVAILABLE)

    def test_the_price_is_the_as_traded_close_of_the_date_and_the_quantity_is_the_replayed_quantity(self):
        # 2025-01-02 closes: AAPL 150.25, 0700 330.4 ; fixings USD 1.0800, HKD 8.4000
        val = valuation_of(self.w, ledger_events(self.w.ident), as_of=D(2025, 1, 2))
        h = {h.listing_id: h for h in val.holdings}
        self.assertEqual(h[self.ids["AAPL"]].native.exact, Fraction(10) * Fraction("150.25"))  # 1,502.5
        self.assertEqual(h[self.ids["0700"]].reporting.exact, Fraction(100) * Fraction("330.4") * Fraction(1080, 8400))


class PresentationTests(_Worlds):
    def test_native_facts_and_exact_amounts_present_exactly_and_the_hkd_cny_reporting_values_now_present(self):
        res = run_world(self.w)
        aapl = find(res, "holding_value", "REPORTING", listing=str(self.ids["AAPL"]))
        self.assertEqual((aapl.result.value, aapl.result.sufficiency_state, aapl.exact), (Decimal("1511"), AVAILABLE, AAPL_NATIVE))
        self.assertIsNone(aapl.rounding_rule_id)  # 1,511 needs no rounding: stated equals exact
        hk_native = find(res, "holding_value", "NATIVE", listing=str(self.ids["0700"]))
        self.assertEqual((hk_native.result.value, hk_native.currency), (Decimal("33260"), "HKD"))
        # a native cash balance is a sum of recorded facts: presented exactly (Ruling 2.2, last row); its reporting value is derived money
        self.assertEqual(find(res, "cash_value", "NATIVE", currency="HKD").result.value, Decimal("67000"))
        self.assertIsNone(find(res, "cash_value", "NATIVE", currency="HKD").rounding_rule_id)
        # 3,595,406 / 841 does not terminate; CP3b presents it (Ruling 2.2, half away from zero at the minor unit of USD)
        hk = find(res, "holding_value", "REPORTING", listing=str(self.ids["0700"]))
        self.assertEqual((hk.result.value, hk.result.sufficiency_state, hk.exact), (Decimal("4275.16"), AVAILABLE, HK_REPORTING))
        self.assertEqual(hk.rounding_rule_id, ROUNDING_ID)

    def test_the_value_is_rounded_once_at_the_edge_and_the_exact_rational_is_kept(self):
        res = run_world(self.w, perf=performance_conventions())
        # 3,595,406 / 841 = 4,275.1558... (841 x 4,275 = 3,595,275 ; remainder 131 ; 131/841 = 0.1558) -> 4,275.16
        hk = find(res, "holding_value", "REPORTING", listing=str(self.ids["0700"]))
        self.assertEqual((hk.result.value, hk.exact, hk.rounding_rule_id), (Decimal("4275.16"), HK_REPORTING, ROUNDING_ID))
        # 7,242,700 / 841 = 8,612.0095 (841 x 8,612 = 7,242,692 ; remainder 8 ; 8/841 = 0.0095) -> 8,612.01
        cash = find(res, "cash_value", "REPORTING", currency="HKD")
        self.assertEqual(cash.result.value, Decimal("8612.01"))
        # total = 100,011 + 12,887.1653 (10,838,106/841 ; 841 x 12,887 = 10,837,967 ; remainder 139) + 13,841.7828
        # (54,052,162/3,905 ; 3,905 x 13,841 = 54,049,105 ; remainder 3,057) = 126,739.9481 -> 126,739.95
        total = find(res, "portfolio_value", "REPORTING")
        self.assertEqual((total.result.value, total.exact, total.result.sufficiency_state),
                         (Decimal("126739.95"), REPORTING_TOTAL, AVAILABLE))
        self.assertTrue(total.conformant)  # performance/1.12: nothing unbuilt, no MEMORY row (a placeholder rule would still make it False)
        self.assertFalse([m for m in res.metrics if m.partial])  # the total exists, so there is no partial figure

    def test_the_displayed_breakdown_sums_exactly_to_the_displayed_total_by_largest_remainder(self):
        # exact lines (USD) and their floors at 2 decimals; remainders in the last column (hand arithmetic):
        #   AAPL      1,511             1,511.00     0
        #   0700      3,595,406/841     4,275.15     0.005767   (131/841 = 0.155767)
        #   600519    1,623,662/3,905   415.79       0.000525   (3,087/3,905 = 0.790525)
        #   cash CNY  10,485,700/781    13,425.99    0.002317   (775/781 = 0.992317)
        #   cash HKD  7,242,700/841     8,612.00     0.009512   (8/841 = 0.009512)
        #   cash USD  98,500            98,500.00    0
        # floors sum to 126,739.93; the displayed total is 126,739.95 (126,739.9481): shortfall 2 quanta, given to the two largest
        # remainders (cash HKD, then 0700): 8,612.01 and 4,275.16. Displayed lines: 1,511.00 + 4,275.16 + 415.79 + 13,425.99 +
        # 8,612.01 + 98,500.00 = 126,739.95.
        res = run_world(self.w)
        total = find(res, "portfolio_value", "REPORTING")
        shown = {ref: dec for ref, dec, _exact in total.breakdown}
        a = str(ACCOUNT)
        self.assertEqual(shown, {
            f"holding:{a}/{self.ids['AAPL']}": Decimal("1511.00"), f"holding:{a}/{self.ids['0700']}": Decimal("4275.16"),
            f"holding:{a}/{self.ids['600519']}": Decimal("415.79"), f"cash:{a}/CNY": Decimal("13425.99"),
            f"cash:{a}/HKD": Decimal("8612.01"), f"cash:{a}/USD": Decimal("98500.00")})
        self.assertEqual(sum(shown.values()), total.result.value)
        self.assertEqual(sum(exact for _r, _d, exact in total.breakdown), REPORTING_TOTAL)  # tier E: exact

    def test_a_suppressed_total_gets_a_separately_labelled_partial_figure_with_the_excluded_count(self):
        # no admitted source for 0700 and 600519: the total is INSUFFICIENT_DATA; the partial figure is
        # 1,511 + 98,500 + 7,242,700/841 + 10,485,700/781 = 100,011 + 8,612.0095 + 13,425.9923 = 122,049.0018 -> 122,049.00
        res = run_world(self.worlds[x.NO_CN_HK])
        total = find(res, "portfolio_value", "REPORTING")
        self.assertEqual((total.result.value, total.partial), (None, False))
        (part,) = [m for m in res.metrics if m.metric_id == "portfolio_value_priced_holdings"]
        self.assertTrue(part.partial)
        self.assertEqual((part.result.value, part.result.sufficiency_state), (Decimal("122049.00"), AVAILABLE))
        self.assertEqual(part.exact, Fraction(100011) + Fraction(7242700, 841) + Fraction(10485700, 781))
        self.assertIn(("excluded_holdings", "2"), part.lineage)
        self.assertEqual(sorted(e.kind for e in part.excluded), ["POSITION", "POSITION"])
        self.assertEqual(sorted(e.native for e in part.excluded), ["100", "2"])  # the unpriced native quantities
        self.assertTrue(all(c.reason == "MISSING_PRICE_HISTORY" for e in part.excluded for c in e.causes))

    def test_the_value_part_is_byte_identical_across_the_four_worlds_while_the_manifest_cites_different_files(self):
        digests, files = {}, {}
        for fl in x.FLAVOURS:
            w = self.worlds[fl]
            res = run_world(w, perf=performance_conventions())
            parts = [(m.metric_id, m.view, m.subject, m.result.value, m.result.sufficiency_state, m.exact) for m in res.metrics]
            digests[fl] = repr(parts)
            files[fl] = res.manifest.consumed_files()
        self.assertEqual(len(set(digests.values())), 1)
        self.assertEqual(len({tuple(f) for f in files.values()}), len(x.FLAVOURS))  # different files, same facts


class StatePropagationTests(_Worlds):
    def test_a_listing_with_no_admitted_source_blocks_its_own_view_and_the_totals_it_belongs_to_and_nothing_else(self):
        w = self.worlds[x.NO_CN_HK]
        res = run_world(w, perf=performance_conventions())
        hk = find(res, "holding_value", "NATIVE", listing=str(self.ids["0700"]))
        self.assertEqual((hk.result.value, hk.result.sufficiency_state, hk.result.reason_code, hk.exact),
                         (None, INSUFFICIENT, ReasonCode.MISSING_PRICE_HISTORY, None))
        self.assertTrue(hk.causes)
        # the native facts that need no price stay available (cash: 67,000 HKD)
        self.assertEqual(find(res, "cash_value", "NATIVE", currency="HKD").result.value, Decimal("67000"))
        self.assertEqual(find(res, "portfolio_value", "NATIVE", currency="USD").result.value, Decimal("100011"))
        hk_total = find(res, "portfolio_value", "NATIVE", currency="HKD")
        self.assertEqual((hk_total.result.value, hk_total.result.reason_code), (None, ReasonCode.MISSING_PRICE_HISTORY))
        total = find(res, "portfolio_value", "REPORTING")
        self.assertEqual((total.result.value, total.result.sufficiency_state, total.result.reason_code),
                         (None, INSUFFICIENT, ReasonCode.MISSING_PRICE_HISTORY))
        self.assertTrue(any(c.reason == "MISSING_PRICE_HISTORY" for c in total.causes))
        # the cash conversion itself is fine (ECB rates exist): 67,000 x 1081/8410 = 8,612.01
        self.assertEqual(find(res, "cash_value", "REPORTING", currency="HKD").result.value, Decimal("8612.01"))

    def test_one_session_stale_is_available_with_stale_data_and_the_value_is_unchanged(self):
        # as of Mon 2025-01-06 the last print and the last fixing are the 3rd: 1 session / 1 fixing missed (market-data table)
        res = run_world(self.w, as_of=LATER, perf=performance_conventions())
        aapl = find(res, "holding_value", "NATIVE", listing=str(self.ids["AAPL"]))
        self.assertEqual((aapl.result.value, aapl.result.sufficiency_state, aapl.result.reason_code),
                         (Decimal("1511"), AVAILABLE, ReasonCode.STALE_DATA))
        self.assertIn(("price_missed_sessions", "1"), aapl.lineage)
        self.assertIn(("price_date_used", "2025-01-03"), aapl.lineage)
        total = find(res, "portfolio_value", "REPORTING")
        self.assertEqual((total.result.value, total.result.sufficiency_state, total.result.reason_code),
                         (Decimal("126739.95"), AVAILABLE, ReasonCode.STALE_DATA))  # same facts, same rates carried forward

    def test_a_valuation_suppression_makes_the_position_and_its_totals_insufficient_with_the_stated_reason(self):
        sup = SuppressionInput(ACCOUNT, self.ids["AAPL"], D(2025, 1, 2), None, "SOURCE_CONFLICT", "split dated off its ex-date")
        res = run_world(self.w, suppressions=(sup,), perf=performance_conventions())
        aapl = find(res, "holding_value", "NATIVE", listing=str(self.ids["AAPL"]))
        self.assertEqual((aapl.result.value, aapl.result.reason_code), (None, ReasonCode.SOURCE_CONFLICT))
        self.assertEqual(find(res, "portfolio_value", "REPORTING").result.reason_code, ReasonCode.SOURCE_CONFLICT)
        # the quantity fact is untouched and another listing is unaffected
        self.assertEqual(find(res, "holding_value", "NATIVE", listing=str(self.ids["0700"])).result.value, Decimal("33260"))
        self.assertNotEqual(res.manifest.split_suppressions_digest, run_world(self.w).manifest.split_suppressions_digest)
        # a suppression that ends before the as-of date does not apply
        old = dataclasses.replace(sup, end_exclusive=D(2025, 1, 3))
        self.assertEqual(find(run_world(self.w, suppressions=(old,)), "holding_value", "NATIVE",
                              listing=str(self.ids["AAPL"])).result.value, Decimal("1511"))

    def test_an_account_before_its_snapshot_blocks_every_total_and_a_ledger_with_no_events_is_not_zero(self):
        a2 = uuid.UUID(int=2)
        events = ledger_events(self.w.ident) + [SequencedEvent(7, LedgerEvent(
            event_id=uuid.UUID(int=999), account_id=a2, event_type=EventType.OPENING_CASH, event_date=D(2025, 1, 10),
            currency=USD, amount=Money(Decimal(5), USD)))]
        res = run_world(self.w, events=events, perf=performance_conventions())
        total = find(res, "portfolio_value", "REPORTING")
        self.assertEqual((total.result.value, total.result.reason_code), (None, ReasonCode.NOT_RECONSTRUCTABLE))
        self.assertEqual(find(res, "portfolio_value", "NATIVE", currency="USD").result.reason_code, ReasonCode.NOT_RECONSTRUCTABLE)
        empty = run_world(self.w, events=[])
        (only,) = empty.metrics
        self.assertEqual((only.result.value, only.result.sufficiency_state), (None, INSUFFICIENT))
        self.assertTrue(any("NO_LIVE_LEDGER_EVENTS" in c.note for c in only.causes))

    def test_a_current_live_request_is_refused_with_an_explicit_state_and_no_number(self):
        res = run_world(self.w, mode=ValuationMode.CURRENT_LIVE)
        (m,) = res.metrics
        self.assertEqual((m.result.value, m.result.sufficiency_state, m.result.reason_code), (None, INSUFFICIENT, None))
        self.assertTrue(any("UNSUPPORTED_VALUATION_MODE" in c.note for c in m.causes))
        self.assertEqual((res.manifest.valuation_mode, res.manifest.release_id), ("CURRENT_LIVE", None))

    def test_the_synthetic_flag_is_carried_to_every_metric_and_the_manifest(self):
        res = run_world(self.w)
        self.assertTrue(res.manifest.synthetic)
        self.assertTrue(all(m.synthetic and m.portfolio_state == "ACTUAL" for m in res.metrics))


class ManifestTests(_Worlds):
    def test_the_manifest_pins_the_ledger_the_release_the_conventions_and_the_calendars(self):
        events = ledger_events(self.w.ident)
        res = run_world(self.w, events=events)
        m = res.manifest
        self.assertEqual((m.ledger_version, m.release_id, m.as_of, m.reporting_currency, m.state_kind),
                         (6, self.w.release.release_id, AS_OF, "USD", "ACTUAL"))
        self.assertEqual(m.ledger_digest, ledger_digest(events, 6))
        conv = dict(m.conventions)
        self.assertEqual(conv["ledger_replay"], "ledger-replay/1.5")  # the FIFO/1 mode of the one lot fold (also decides the carried taint); CP1 outputs still cite 1.3
        self.assertEqual(conv["market_data.convention_set"], "market-data/1.16")
        self.assertEqual(conv["performance.convention_set"], "performance/1.12")
        self.assertEqual(conv["performance.minor_unit_table"], "minor-units/1.1")
        self.assertEqual(conv["performance.lot_method"], "FIFO/1")
        self.assertEqual(conv["performance.rounding"], "performance/1.12#2.2-2.4")
        # performance/1.12 (PD-0037, HG2 condition 2): the ten ISO rows are CONFIRMED and the HG2 entry is gone, so the convention names nothing unbuilt: the engine is conformant
        self.assertTrue(m.conformant)
        self.assertEqual([i for i in m.open_items if not i.startswith("market_data:")], [])  # (market-data's own open items are listed with the prefix)
        self.assertTrue(m.calendar_file_refs)
        self.assertTrue(all(f.adapter_id.endswith(".calendar") for f in m.calendar_file_refs))
        self.assertTrue(set(m.calendar_file_refs) <= set(m.consumed_files()))
        self.assertTrue(all(metric.manifest_id == m.manifest_id for metric in res.metrics))
        self.assertEqual(len(m.manifest_id), 64)

    def test_the_same_inputs_give_the_same_bytes_and_a_changed_input_changes_the_id(self):
        a, b = run_world(self.w), run_world(self.w)
        self.assertEqual(a.canonical_json(), b.canonical_json())
        self.assertNotEqual(run_world(self.w, as_of=D(2025, 1, 2)).manifest.manifest_id, a.manifest.manifest_id)
        self.assertNotEqual(run_world(self.worlds["mock"]).manifest.manifest_id, a.manifest.manifest_id)

    def test_reproduce_returns_each_typed_status(self):
        events = ledger_events(self.w.ident)
        res = run_world(self.w, events=events)
        market = market11_conventions(self.w.built.calendars)
        perf = performance_conventions()

        def go(manifest=None, digest="same", ev=events, port=None, conv=perf, **kw):
            return reproduce(manifest or res.manifest, res.result_digest if digest == "same" else digest, ev,
                             port or self.w.store, self.w.ident, market, conv, **kw)

        self.assertEqual(go().status, ReproductionStatus.REPRODUCED)
        altered = events[:-1] + [SequencedEvent(6, dataclasses.replace(events[-1].event, quantity=Decimal(3)))]
        self.assertEqual(go(ev=altered).status, ReproductionStatus.LEDGER_DIGEST_MISMATCH)
        self.assertEqual(go(port=self.worlds["mock"].store).status, ReproductionStatus.RELEASE_MISMATCH)
        self.assertEqual(go(conv=dataclasses.replace(performance_conventions(), twr_rule_id="performance/9.9")).status,
                         ReproductionStatus.CONVENTION_MISMATCH)
        sup = SuppressionInput(ACCOUNT, self.ids["AAPL"], D(2025, 1, 2), None, "SOURCE_CONFLICT", "x")
        self.assertEqual(go(suppressions=(sup,)).status, ReproductionStatus.SUPPRESSIONS_MISMATCH)
        self.assertEqual(go(digest="0" * 64).status, ReproductionStatus.RESULT_DIFFERS)
        hidden = dataclasses.replace(res.manifest, data_set_refs=())  # the re-run reads files the manifest does not cite
        self.assertEqual(go(manifest=hidden).status, ReproductionStatus.FILE_NOT_CITED)
        extra = dataclasses.replace(res.manifest, data_set_refs=res.manifest.data_set_refs[:1])
        self.assertIn(go(manifest=extra).status, (ReproductionStatus.FILE_NOT_CITED, ReproductionStatus.FILE_NOT_READ))
        # a manifest that cites a file the re-run does not read
        fx_only = res.manifest.data_set_refs[0]
        ghost = dataclasses.replace(fx_only, consumed=fx_only.consumed + (type(fx_only.consumed[0])("f" * 64, "a", "1"),))
        self.assertEqual(go(manifest=dataclasses.replace(res.manifest, data_set_refs=(ghost,) + res.manifest.data_set_refs[1:])
                            ).status, ReproductionStatus.FILE_NOT_READ)


class LedgerViewTests(_Worlds):
    def test_live_events_applies_reversals_and_versions_like_replay(self):
        events = ledger_events(self.w.ident)
        target = events[3].event  # the AAPL buy
        events.append(SequencedEvent(7, LedgerEvent(event_id=uuid.UUID(int=700), account_id=ACCOUNT,
                                                    event_type=EventType.REVERSAL, event_date=D(2025, 1, 1),
                                                    currency=USD, reverses_event_id=target.event_id)))
        self.assertEqual([i.ledger_seq for i in live_events(events, 7)], [1, 2, 3, 5, 6])  # no reversal, no target
        self.assertEqual([i.ledger_seq for i in live_events(events, 6)], [1, 2, 3, 4, 5, 6])  # the reversal is not yet known
        self.assertEqual([i.ledger_seq for i in live_events(events, 2)], [1, 2])
        # replaying the live events alone gives the same state as replaying everything (same code path)
        for version in (2, 6, 7):
            live = live_events(events, version)
            self.assertEqual(reconstruct(live, AS_OF, version).canonical_json(), reconstruct(events, AS_OF, version).canonical_json())
        self.assertNotEqual(ledger_digest(events, 6), ledger_digest(events, 7))
        self.assertEqual(ledger_digest(events, 7), ledger_digest(list(reversed(events)), 7))  # input order is irrelevant

    def test_the_flow_table_is_ruling_41_data(self):
        events = ledger_events(self.w.ident)
        table = performance_flow_table()
        rows = classify_events(events, 6, table)
        self.assertEqual([(r.event_type, r.flow_class) for r in rows],
                         [("DEPOSIT", FlowClass.EXTERNAL_INFLOW_CASH)] * 3 + [("BUY", FlowClass.EXCHANGE)] * 3)
        self.assertEqual({r.timing.value for r in rows[:3]}, {"START"})  # a cash inflow is at the START of the day (Ruling 4.2)
        self.assertTrue(table.table_id.startswith("performance/1.12#"))
        with self.assertRaises(ValueError):
            FlowTable("t", (FlowRow(EventType.BUY, FlowClass.EXCHANGE), FlowRow(EventType.BUY, FlowClass.FEE)))
        self.assertTrue(performance_conventions().is_conformant)  # performance/1.12: no rule is unbuilt and no minor-unit row is from memory


class NumericsAndEnvelopeTests(unittest.TestCase):
    def test_exact_decimals_only_and_the_size_guard(self):
        self.assertTrue(numerics.is_terminating(Fraction(1, 8)))
        self.assertFalse(numerics.is_terminating(Fraction(1, 3)))
        self.assertEqual(numerics.to_decimal_exact(Fraction(1, 8)), Decimal("0.125"))  # 125 / 1000
        self.assertEqual(numerics.to_decimal_exact(Fraction(-7, 2)), Decimal("-3.5"))
        self.assertIsNone(numerics.to_decimal_exact(Fraction(1, 3)))
        rule = PerformanceRounding()
        P = numerics.RoundingPoint.PRESENT_MONEY
        self.assertEqual(numerics.present(Fraction(5), P, USD, rule).decimal, Decimal(5))
        self.assertEqual(numerics.present(Fraction(1, 3), P, USD, rule).decimal, Decimal("0.33"))  # 1/3 -> 0.33 (half away from zero)
        huge = Fraction(1, 2 ** (numerics.MAX_BITS + 1))
        self.assertEqual(numerics.present(huge, P, USD, rule).status, numerics.PresentStatus.TOO_LARGE)

    def test_a_computed_metric_cannot_carry_a_number_for_insufficient_data_or_hide_its_causes(self):
        win = WindowUsed(AS_OF, AS_OF)
        ok = dict(metric_id="m", view="NATIVE", subject=(), unit="CURRENCY_AMOUNT", currency="USD", rounding_rule_id=None,
                  window=win, method_id="t", synthetic=False, conformant=False)
        with self.assertRaises(ValueError):  # an exact rational without a value would leak a suppressed number
            ComputedMetric(result=MetricResult(None, INSUFFICIENT), exact=Fraction(1), causes=(Cause("a", "X", None),), **ok)
        with self.assertRaises(ValueError):  # INSUFFICIENT_DATA must name its causes
            ComputedMetric(result=MetricResult(None, INSUFFICIENT), exact=None, causes=(), **ok)
        with self.assertRaises(ValueError):  # a value without its exact rational
            ComputedMetric(result=MetricResult(Decimal(1), AVAILABLE), exact=None, causes=(), **ok)
        fine = ComputedMetric(result=MetricResult(Decimal(1), AVAILABLE), exact=Fraction(1), causes=(), **ok)
        self.assertEqual(fine.to_canonical_dict()["exact"], Fraction(1))


class DetectOnlySplitTests(unittest.TestCase):
    """F8-B detect-and-report mode (PM ruling 3): the decision runs, `append` is never called, valuation is suppressed."""

    def test_dry_run_reports_would_append_writes_nothing_and_yields_a_suppression_from_the_ex_date(self):
        ledger = ca.ledger_with_holdings()

        def boom(event):
            raise AssertionError("dry-run must never append")

        ledger.append = boom
        before = (ledger.seq, list(ledger.rows))
        report = f8b.confirm_splits(ledger, ca.corroborated(), ca.PORTFOLIO, (ca.LISTING,), D(2025, 1, 1), D(2025, 12, 31),
                                    ca.POLICY, {ca.LISTING: ca.USD}, calendars=ca.CALENDARS, exchange_of=ca.exchange_of,
                                    dry_run=True)
        (o,) = report.outcomes
        self.assertEqual((o.decision, o.cause, o.account_id, o.ex_date), (f8b.SplitDecision.WOULD_APPEND, f8b.SPLIT_NOT_APPLIED,
                                                                          ca.A1, ca.EX))
        self.assertEqual((ledger.seq, list(ledger.rows)), before)
        self.assertEqual((report.ledger_version_before, report.ledger_version_after), (2, 2))
        (s,) = report.suppressions
        self.assertEqual((s.first_date, s.end_exclusive, s.reason_code), (ca.EX, None, ReasonCode.SOURCE_CONFLICT))
        (conv,) = suppressions_from_report(report)
        self.assertEqual((conv.account_id, conv.listing_id, conv.first_date, conv.reason), (ca.A1, ca.LISTING, ca.EX, "SOURCE_CONFLICT"))
        self.assertTrue(conv.covers(D(2025, 2, 10)) and not conv.covers(D(2025, 2, 2)))

    def test_the_normal_path_is_unchanged_and_a_dry_run_changes_nothing_for_it(self):
        ledger = ca.ledger_with_holdings()
        ca.run(ledger, ca.corroborated(), start=D(2025, 1, 1), end=D(2025, 12, 31))  # normal: appends
        (event,) = ledger.appended
        self.assertEqual(event.event_type, EventType.SPLIT)
        again = f8b.confirm_splits(ledger, ca.corroborated(), ca.PORTFOLIO, (ca.LISTING,), D(2025, 1, 1), D(2025, 12, 31),
                                   ca.POLICY, {ca.LISTING: ca.USD}, calendars=ca.CALENDARS, exchange_of=ca.exchange_of,
                                   dry_run=True)
        self.assertEqual([o.decision for o in again.outcomes], [f8b.SplitDecision.ALREADY_RECORDED])
        self.assertEqual(again.suppressions, ())

    def test_the_read_only_access_refuses_any_append(self):
        access = ReadOnlyLedgerAccess(conn=None)
        with self.assertRaises(WriteRefusedError):
            access.append(object())


class DeterminismAcrossProcessesTests(unittest.TestCase):
    def test_the_result_digest_is_the_same_in_processes_with_different_hash_seeds(self):
        digests = set()
        for seed in ("1", "2", "random"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            out = subprocess.run([sys.executable, str(Path(__file__)), "digest"], capture_output=True, text=True, env=env,
                                 timeout=120)
            self.assertEqual(out.returncode, 0, out.stderr)
            digests.add(out.stdout.strip())
        self.assertEqual(len(digests), 1)
        (digest,) = digests
        self.assertEqual(len(digest), 64)


# ---- opt-in: the PostgreSQL market-data store and the real ledger, read as the least-privilege role ------------------------
_SKIP = pk.skip_reason()


class _Silent:
    """CP3-10 probe: a wrapping port that forwards the `MarketDataPort` methods and `release` only, and HIDES `contains_synthetic`."""

    def __init__(self, inner):
        self._inner = inner
        self.release = inner.release

    def __getattr__(self, name):
        if name == "contains_synthetic":
            raise AttributeError(name)
        return getattr(self._inner, name)


class _AsIfReal:
    """CP3-10 probe: a wrapping port that LIES, reporting `contains_synthetic = False`. The service still refuses: the computed result is marked synthetic by
    what it read."""

    contains_synthetic = False

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)


@unittest.skipIf(bool(_SKIP), _SKIP)
class PostgresValuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from persistence import ledger_replay_store, ledger_store, market_data_store as mds  # noqa: PLC0415

        cls.rs, cls.ls, cls.mds = ledger_replay_store, ledger_store, mds
        cls.db = pk.PgSchema().open()
        cls.addClassCleanup(cls.db.close)
        cls.world = x.build_world("formats")
        cls.addClassCleanup(cls.world.close)
        pk.insert_identity(cls.db.owner, cls.world.ident)
        mds.write_release(cls.db.owner, cls.world.release, cls.world.built.manifests, cls.world.store.export(),
                          cls.world.built.calendars)
        cls.user, cls.portfolio, cls.account = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        cls.db.owner.execute("INSERT INTO app_user VALUES (%s)", (cls.user,))
        cls.db.owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (cls.portfolio, cls.user))
        cls.db.owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (cls.account, cls.portfolio))
        cls.app = cls.db.app_connection()
        cls.addClassCleanup(cls.app.close)
        events = [s.event for s in ledger_events(cls.world.ident, account=cls.account, base=int(uuid.uuid4().int % 10**9) * 10)]
        ledger_store.append_batch(cls.app, events[:3])  # the deposits: a committed boundary a test can pin
        ledger_store.append_batch(cls.app, events[3:])
        # the registry in force now (here: the records the in-memory build read) is handed to the projection's reader, so both ports pin the same `source_registry_digest` (Ruling 1.7 (1.12) item 4)
        cls.pg = mds.read_release(cls.app, cls.world.release.release_id, exchange_of=cls.world.ident.exchange_mic,
                                  registry=SourceRegistry(cls.world.store.source_registry_records()))

    def test_valuation_through_the_postgresql_store_as_the_application_role_equals_the_in_memory_result(self):
        from performance_service.service import compute_for_portfolio  # noqa: PLC0415

        self.assertEqual(self.app.execute("SELECT current_user").fetchone()[0], self.db.app_role)
        market = market11_conventions(self.pg.calendars())
        # PM ruling (Ruling 4.8 item 4): the world is synthetic, so the SERVICE refuses it for a user portfolio, with an explicit state and no number
        refused = compute_for_portfolio(self.app, self.portfolio, AS_OF, USD, self.pg, self.world.ident, market,
                                        performance_conventions(), policy=ca.POLICY)
        self.assertTrue(self.pg.contains_synthetic)
        (rm,) = refused.metrics
        self.assertEqual((rm.result.value, rm.result.sufficiency_state), (None, INSUFFICIENT))
        self.assertIn("SYNTHETIC_MARKET_DATA_REFUSED", rm.details)
        # CP3-10: a port that HIDES the attribute is refused too (and so is one that lies: the computed result is itself marked synthetic)
        for hidden in (_AsIfReal(self.pg), _Silent(self.pg)):
            again = compute_for_portfolio(self.app, self.portfolio, AS_OF, USD, hidden, self.world.ident, market, performance_conventions(), policy=ca.POLICY)
            self.assertIn("SYNTHETIC_MARKET_DATA_REFUSED", again.metrics[0].details)
        # the engine called directly (tests and fixtures) stays allowed; the service's happy path over real data is in test_performance_midpoint (PG ledger)
        version = self.rs.current_ledger_version(self.app, self.portfolio)
        events = self.rs.load_events(self.app, self.portfolio, version)
        memory = compute(events, version, AS_OF, USD, self.world.store, self.world.ident,
                         market11_conventions(self.world.built.calendars), performance_conventions(), portfolio_id=self.portfolio,
                         suppressions=(), detection="F8B_DRY_RUN")  # the world has no corroborated split: detection finds none
        direct_pg = compute(events, version, AS_OF, USD, self.pg, self.world.ident, market, performance_conventions(), portfolio_id=self.portfolio,
                            suppressions=(), detection="F8B_DRY_RUN")  # the engine, called directly, over the PostgreSQL store: allowed, and synthetic
        self.assertTrue(direct_pg.manifest.synthetic)
        self.assertEqual(direct_pg.result_digest, memory.result_digest)
        self.assertEqual(direct_pg.canonical_json(), memory.canonical_json())
        # Ruling 1.7 (1.12) item 4: the projection reports the registry records of the sources with a file in the release, read through the registry handed to `read_release`; without one it reports none
        self.assertTrue(memory.manifest.source_registry_digest)
        self.assertEqual(direct_pg.manifest.source_registry_digest, memory.manifest.source_registry_digest)
        self.assertEqual(self.pg.source_registry_records(), self.world.store.source_registry_records())
        with self.assertRaises(TypeError):  # the registry is REQUIRED: omitting it fails closed
            self.mds.read_release(self.app, self.world.release.release_id, exchange_of=self.world.ident.exchange_mic)
        with self.assertRaises(LookupError):  # a source the registry does not know: fail closed
            self.mds.read_release(self.app, self.world.release.release_id, exchange_of=self.world.ident.exchange_mic, registry=SourceRegistry([]))
        total = find(direct_pg, "portfolio_value", "REPORTING")
        self.assertEqual((total.result.value, total.exact), (Decimal("126739.95"), REPORTING_TOTAL))
        self.assertEqual(find(direct_pg, "portfolio_value", "NATIVE", currency="HKD").exact, NATIVE_TOTALS["HKD"])
        report = reproduce(direct_pg.manifest, direct_pg.result_digest, events, self.pg, self.world.ident, market, performance_conventions(),
                           suppressions=())
        self.assertEqual(report.status, ReproductionStatus.REPRODUCED)

    def test_a_pinned_earlier_ledger_version_sees_only_the_events_up_to_it_and_nothing_is_written(self):
        from performance_service.service import compute_for_portfolio  # noqa: PLC0415

        market = market11_conventions(self.pg.calendars())
        before = self.rs.current_ledger_version(self.app, self.portfolio)
        cutoff = self.rs.load_events(self.app, self.portfolio, before)[2].ledger_seq  # after the three deposits
        res = compute_for_portfolio(self.app, self.portfolio, AS_OF, USD, self.pg, self.world.ident, market,
                                    performance_conventions(), policy=ca.POLICY, ledger_version=cutoff)
        self.assertEqual(res.manifest.ledger_version, cutoff)  # the pin is honoured (the synthetic refusal carries it)
        direct = compute(self.rs.load_events(self.app, self.portfolio, cutoff), cutoff, AS_OF, USD, self.pg, self.world.ident, market,
                         performance_conventions(), suppressions=())
        # deposits only: 100,000 USD, no holdings
        self.assertEqual(find(direct, "portfolio_value", "NATIVE", currency="USD").result.value, Decimal("100000"))
        self.assertFalse([m for m in direct.metrics if m.metric_id == "holding_value"])
        self.assertEqual(self.rs.current_ledger_version(self.app, self.portfolio), before)  # a read wrote nothing


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "digest":
        _w = x.build_world("formats")
        print(run_world(_w, perf=performance_conventions()).result_digest)
        _w.close()
    else:
        unittest.main()
