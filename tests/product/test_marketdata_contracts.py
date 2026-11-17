"""CP2 normalized contracts (Tech Plan §15.1; market-data/1.0 findings MD1-MD6): shapes and
construction rules only. No rule of the Quant's is tested as a rule here."""

import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.field_validation import DomainFieldTypeError  # noqa: E402
from domain.ledger import SplitRatio  # noqa: E402
from marketdata import contracts as c  # noqa: E402

USD, HKD, EUR = CurrencyCode("USD"), CurrencyCode("HKD"), CurrencyCode("EUR")
NOW = datetime.datetime(2025, 1, 2, 15, 0, tzinfo=datetime.timezone.utc)
DAY = datetime.date(2025, 1, 2)
TIMING = c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY)
LINE = c.Lineage("vendor-neutral-label", c.AdjustmentStatus.RAW)
LID = uuid.UUID(int=7)
SHA = "a" * 64


class QuoteTests(unittest.TestCase):
    def test_quote_is_dated_by_session_and_never_float(self):
        q = c.QuoteObservation(LID, DAY, Decimal("150.25"), USD, TIMING, LINE)
        self.assertEqual(q.session_date, DAY)
        self.assertEqual(q.price_kind, c.PriceKind.SOURCE_CLOSE)  # official-ness is never assumed
        with self.assertRaises(DomainFieldTypeError):
            c.QuoteObservation(LID, DAY, 150.25, USD, TIMING, LINE)
        with self.assertRaises(c.ObservationRuleError):
            c.QuoteObservation(LID, DAY, Decimal(0), USD, TIMING, LINE)
        with self.assertRaises(c.ObservationRuleError):  # a datetime is not a session date
            c.QuoteObservation(LID, NOW, Decimal(1), USD, TIMING, LINE)
        with self.assertRaises(c.ObservationRuleError):
            c.QuoteObservation(LID, DAY, Decimal(1), USD, TIMING, LINE,
                               observed_at=datetime.datetime(2025, 1, 2, 15, 0))  # naive

    def test_volume_and_print_rule_inputs(self):
        base = dict(listing_id=LID, value_date=DAY, price=Decimal(1), currency=USD,
                    timing=TIMING, lineage=LINE)
        self.assertFalse(c.QuoteObservation(**base).is_print)  # no volume reported
        self.assertFalse(c.QuoteObservation(**base, volume=Decimal(0)).is_print)
        self.assertTrue(c.QuoteObservation(**base, volume=Decimal(1)).is_print)
        with self.assertRaises(c.ObservationRuleError):
            c.QuoteObservation(**base, volume=Decimal(-1))
        with self.assertRaises(DomainFieldTypeError):
            c.QuoteObservation(**base, volume=10)

    def test_unresolved_quote_carries_identifiers_not_a_listing(self):
        ids = c.ExternalIdentifiers(ticker="AAPL", mic="XNAS")
        u = c.UnresolvedQuote(ids, DAY, Decimal(1), USD, TIMING, LINE)
        self.assertFalse(hasattr(u, "listing_id"))


class TimingAndFreshnessTests(unittest.TestCase):
    def test_timing_is_intrinsic_and_carries_no_state(self):
        t = c.SourceTiming()
        self.assertIsNone(t.source_time)
        self.assertFalse(hasattr(t, "state"))
        with self.assertRaises(c.ObservationRuleError):
            c.SourceTiming(datetime.datetime(2025, 1, 2, 15, 0))

    def test_observations_store_no_freshness_state(self):
        q = c.QuoteObservation(LID, DAY, Decimal(1), USD, TIMING, LINE)
        self.assertFalse(hasattr(q, "freshness"))  # MD1: a state is assessed at read time

    def test_assessed_state_names_its_date_and_policy(self):
        c.Freshness(None, c.FreshnessState.UNKNOWN)
        c.Freshness(None, c.FreshnessState.CURRENT, assessed_as_of=DAY, policy_id="p/1")
        with self.assertRaises(c.ObservationRuleError):
            c.Freshness(None, c.FreshnessState.STALE)
        self.assertEqual({s.value for s in c.FreshnessState}, {"CURRENT", "STALE", "UNKNOWN"})


class LineageTests(unittest.TestCase):
    def test_default_scope_is_the_most_restrictive_and_adjustment_can_be_undeclared(self):
        self.assertIs(LINE.usage_scope, c.UsageScope.INTERNAL_DEVELOPMENT_ONLY)
        self.assertIn(c.AdjustmentStatus.UNDECLARED, list(c.AdjustmentStatus))
        self.assertFalse(LINE.is_complete)

    def test_complete_lineage_and_md3_fields(self):
        full = c.Lineage(
            "s", c.AdjustmentStatus.SPLIT_ADJUSTED, source_id="s", file_sha256=SHA,
            adapter_id="a", adapter_version="1", source_record_ref="row1", retrieved_at=NOW,
            adjustment_anchor="latest raw", upstream="eastmoney", independence_group="g1",
            adjustment_method="proportional", label_status=c.LabelStatus.UNVERIFIABLE,
            precision_profile_id="cn/3dp", source_value_text="12.340000001")
        self.assertTrue(full.is_complete)
        self.assertEqual({s.value for s in c.LabelStatus}, {"VERIFIED", "CONTRADICTED", "UNVERIFIABLE"})
        with self.assertRaises(c.ObservationRuleError):
            c.Lineage("s", c.AdjustmentStatus.RAW, file_sha256="xyz")
        with self.assertRaises(DomainFieldTypeError):
            c.Lineage("s", c.AdjustmentStatus.RAW, label_status="VERIFIED")


class FXTests(unittest.TestCase):
    def test_fx_pair_rate_basis_and_rate(self):
        fx = c.FXObservation(EUR, USD, DAY, Decimal("1.0823"), TIMING, LINE, "published fixing")
        self.assertEqual(fx.fixing_date, DAY)
        with self.assertRaises(c.ObservationRuleError):
            c.FXObservation(USD, USD, DAY, Decimal("1"), TIMING, LINE, "x")
        with self.assertRaises(c.ObservationRuleError):
            c.FXObservation(EUR, USD, DAY, Decimal("-1"), TIMING, LINE, "x")
        with self.assertRaises(c.ObservationRuleError):
            c.FXObservation(EUR, USD, DAY, Decimal("1"), TIMING, LINE, " ")

    def test_cnh_is_a_distinct_code_never_aliased_to_cny(self):
        self.assertNotEqual(CurrencyCode("CNH"), CurrencyCode("CNY"))

    def test_a_cross_is_the_exact_ratio_of_two_published_legs(self):
        # Ruling 1.3 Example 1-A (hypothetical): x_USD 1.0823, x_HKD 8.4512 per EUR on one date.
        usd = c.FXObservation(EUR, USD, DAY, Decimal("1.0823"), TIMING, LINE, "published")
        hkd = c.FXObservation(EUR, HKD, DAY, Decimal("8.4512"), TIMING, LINE, "published")
        cross = c.ExactRatioRate(numerator=hkd, denominator=usd)  # HKD per USD
        self.assertEqual((cross.base_currency, cross.quote_currency), (USD, HKD))
        self.assertEqual(cross.as_fraction(), Fraction(84512, 10823))  # not terminating
        self.assertEqual(cross.fixing_date, DAY)
        self.assertFalse(hasattr(cross, "rate"))  # never materialized as a rounded Decimal

    def test_cross_legs_must_share_date_and_leg_base(self):
        usd = c.FXObservation(EUR, USD, DAY, Decimal("1.0823"), TIMING, LINE, "p")
        hkd_other_day = c.FXObservation(EUR, HKD, DAY + datetime.timedelta(days=1),
                                        Decimal("8.4512"), TIMING, LINE, "p")
        with self.assertRaises(c.ObservationRuleError):
            c.ExactRatioRate(hkd_other_day, usd)
        hkd_other_base = c.FXObservation(USD, HKD, DAY, Decimal("7.8"), TIMING, LINE, "p")
        with self.assertRaises(c.ObservationRuleError):
            c.ExactRatioRate(hkd_other_base, usd)


class CorporateActionTests(unittest.TestCase):
    def action(self, kind, **kw):
        return c.CorporateActionObservation(LID, kind, DAY, TIMING, LINE, **kw)

    def test_types_are_those_of_ruling_7_1(self):
        self.assertEqual({t.value for t in c.CorporateActionType},
                         {"SPLIT", "CASH_DIVIDEND", "SYMBOL_CHANGE", "UNSUPPORTED"})

    def test_split_carries_only_a_combined_ratio_and_effective_date_is_the_ex_date(self):
        a = self.action(c.CorporateActionType.SPLIT, split_ratio=SplitRatio(Decimal(15), Decimal(10)))
        self.assertEqual(a.ex_date, DAY)
        with self.assertRaises(c.ObservationRuleError):
            self.action(c.CorporateActionType.SPLIT)
        with self.assertRaises(c.ObservationRuleError):
            self.action(c.CorporateActionType.SPLIT, split_ratio=SplitRatio(Decimal(2), Decimal(1)),
                        pay_date=DAY)

    def test_dividend_needs_amount_and_pay_date(self):
        pay = DAY + datetime.timedelta(days=20)
        a = self.action(c.CorporateActionType.CASH_DIVIDEND, amount_per_unit=Money(Decimal("0.25"), USD),
                        pay_date=pay, record_date=DAY, paid_currency=HKD, issuer_fx_rate=Decimal("7.8"))
        self.assertEqual(a.pay_date, pay)
        with self.assertRaises(c.ObservationRuleError):  # no pay date
            self.action(c.CorporateActionType.CASH_DIVIDEND, amount_per_unit=Money(Decimal("0.25"), USD))
        with self.assertRaises(c.ObservationRuleError):  # amount must be positive
            self.action(c.CorporateActionType.CASH_DIVIDEND, amount_per_unit=Money(Decimal("0"), USD),
                        pay_date=pay)
        with self.assertRaises(c.ObservationRuleError):  # a dividend carries no split ratio
            self.action(c.CorporateActionType.CASH_DIVIDEND, amount_per_unit=Money(Decimal(1), USD),
                        pay_date=pay, split_ratio=SplitRatio(Decimal(2), Decimal(1)))

    def test_a_stated_payment_is_a_positive_amount_that_names_its_currency_and_belongs_to_a_dividend(self):
        """`risk/1.8` Ruling 5.5 (1.8) item 2: what the issuer says it PAID, in `paid_currency`, recorded as stated."""
        pay = DAY + datetime.timedelta(days=20)
        ok = self.action(c.CorporateActionType.CASH_DIVIDEND, amount_per_unit=Money(Decimal("3.30"), HKD), pay_date=pay, paid_currency=USD, paid_amount=Decimal("0.46"))
        self.assertEqual((ok.paid_currency, ok.paid_amount), (USD, Decimal("0.46")))
        for bad in (dict(paid_amount=Decimal("0.46")), dict(paid_currency=USD, paid_amount=Decimal(0)), dict(paid_currency=USD, paid_amount=Decimal("-1"))):
            with self.assertRaises(c.ObservationRuleError, msg=str(bad)):
                self.action(c.CorporateActionType.CASH_DIVIDEND, amount_per_unit=Money(Decimal("3.30"), HKD), pay_date=pay, **bad)
        with self.assertRaises(c.ObservationRuleError):  # market-data Ruling 7.1 (1.14): the paid currency DIFFERS from the declared one (a payment in the declared currency is the declared amount)
            self.action(c.CorporateActionType.CASH_DIVIDEND, amount_per_unit=Money(Decimal("3.30"), USD), pay_date=pay, paid_currency=USD, paid_amount=Decimal("0.46"))
        with self.assertRaises(c.ObservationRuleError):
            self.action(c.CorporateActionType.CASH_DIVIDEND, amount_per_unit=Money(Decimal("3.30"), USD), pay_date=pay, paid_currency=USD)
        with self.assertRaises(c.ObservationRuleError):  # a split states no payment
            self.action(c.CorporateActionType.SPLIT, split_ratio=SplitRatio(Decimal(2), Decimal(1)), paid_currency=USD, paid_amount=Decimal("1"))

    def test_symbol_change_and_unsupported(self):
        self.action(c.CorporateActionType.SYMBOL_CHANGE, old_ticker="OLD", new_ticker="NEW")
        with self.assertRaises(c.ObservationRuleError):
            self.action(c.CorporateActionType.SYMBOL_CHANGE, old_ticker="X", new_ticker="X")
        with self.assertRaises(c.ObservationRuleError):
            self.action(c.CorporateActionType.SYMBOL_CHANGE, old_ticker="X")
        u = self.action(c.CorporateActionType.UNSUPPORTED, unsupported_label="rights issue")
        self.assertEqual(u.unsupported_label, "rights issue")
        with self.assertRaises(c.ObservationRuleError):
            self.action(c.CorporateActionType.UNSUPPORTED)


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_series_and_licensing(self):
        lic = c.LicensingMetadata(c.LicenseStatus.INTERNAL_DEVELOPMENT_ONLY)
        self.assertFalse(lic.display_permitted)
        pts = (c.BenchmarkPoint(DAY, Decimal("100")),
               c.BenchmarkPoint(DAY + datetime.timedelta(days=1), Decimal("101")))
        s = c.BenchmarkSeries("IDX", "provider", pts, c.BenchmarkValueKind.LEVEL, USD, TIMING, LINE, lic)
        self.assertEqual(len(s.points), 2)
        with self.assertRaises(c.ObservationRuleError):  # display needs a licence (PD-0028)
            c.LicensingMetadata(c.LicenseStatus.INTERNAL_DEVELOPMENT_ONLY, display_permitted=True)
        with self.assertRaises(c.ObservationRuleError):
            c.BenchmarkSeries("IDX", "p", pts[::-1], c.BenchmarkValueKind.LEVEL, USD, TIMING, LINE, lic)


class IdentityTests(unittest.TestCase):
    def test_external_identifiers_need_one_identifier(self):
        c.ExternalIdentifiers(ticker="0700", mic="XHKG")
        with self.assertRaises(c.ObservationRuleError):
            c.ExternalIdentifiers()
        with self.assertRaises(c.ObservationRuleError):
            c.ExternalIdentifiers(source_id="only-a-scope")

    def test_resolution_statuses_never_guess(self):
        ids = c.ExternalIdentifiers(ticker="0700", mic="XHKG")
        R = c.ResolutionStatus
        ok = c.InstrumentResolution(ids, LID, R.RESOLVED)
        self.assertTrue(ok.is_resolved)
        other = uuid.UUID(int=8)
        c.InstrumentResolution(ids, None, R.UNRESOLVED)
        amb = c.InstrumentResolution(ids, None, R.AMBIGUOUS, candidates=(LID, other))
        self.assertFalse(amb.is_resolved)
        c.InstrumentResolution(ids, None, R.CONFLICT, candidates=(LID,))
        with self.assertRaises(c.ObservationRuleError):  # RESOLVED needs the listing
            c.InstrumentResolution(ids, None, R.RESOLVED)
        with self.assertRaises(c.ObservationRuleError):  # no listing with another status
            c.InstrumentResolution(ids, LID, R.AMBIGUOUS, candidates=(LID, other))
        with self.assertRaises(c.ObservationRuleError):
            c.InstrumentResolution(ids, None, R.AMBIGUOUS, candidates=(LID,))


class ReconciliationShapeTests(unittest.TestCase):
    def reading(self, source, group, price="1"):
        q = c.QuoteObservation(LID, DAY, Decimal(price), USD, TIMING,
                               c.Lineage("s", c.AdjustmentStatus.RAW, file_sha256=SHA))
        return c.SourceReading(source, group, SHA, q)

    def test_status_names_are_those_of_ruling_4_3(self):
        self.assertEqual({s.value for s in c.ReconciliationStatus},
                         {"CORROBORATED", "SINGLE_SOURCE", "DISAGREEMENT", "IMPLAUSIBLE",
                          "RESOLVED_BY_EVIDENCE"})

    def test_no_value_is_used_under_disagreement_or_implausibility(self):
        r = self.reading("a", "g")
        c.Reconciliation(c.ReconciliationStatus.SINGLE_SOURCE, (r,), (), "rule", selected_source="a",
                         selection_basis="only source")
        c.Reconciliation(None, (r,), (), "rule")  # not assessed: allowed, never an agreement
        for status in (c.ReconciliationStatus.DISAGREEMENT, c.ReconciliationStatus.IMPLAUSIBLE):
            with self.assertRaises(c.ObservationRuleError):
                c.Reconciliation(status, (r,), (), "rule", selected_source="a", selection_basis="x")
            c.Reconciliation(status, (r,), (), "rule")
        with self.assertRaises(c.ObservationRuleError):  # a selection needs its basis
            c.Reconciliation(None, (r,), (), "rule", selected_source="a")
        with self.assertRaises(c.ObservationRuleError):
            c.Reconciliation(None, (), (), "rule")


class ModuleShapeTests(unittest.TestCase):
    def test_no_adapter_conversion_or_new_reason_code_lives_in_contracts(self):
        for name in (n for n in dir(c) if not n.startswith("_")):
            self.assertNotIn("convert", name.lower())
            self.assertNotIn("adapter", name.lower())

    def test_domain_does_not_import_marketdata(self):
        for path in (_SRC / "domain").glob("*.py"):
            self.assertNotIn("marketdata", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
