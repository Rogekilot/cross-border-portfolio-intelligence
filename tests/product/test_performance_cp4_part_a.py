"""CP4 part A (tech plan 16.24): HG2 condition 1 and the items riding with it.

- CP3-15 (TECH_REVIEW sections 31 and 32.1), now ruled: `market-data/1.11` Ruling 6.4d, the confirmation-policy test per (listing, ex-date). A key (listing, ex-date) is UNMATCHED iff some source with a SPLIT
  record for it is named in neither role (`if foreign:`, which includes case (c)); any unmatched key refuses the whole computation (INSUFFICIENT_DATA, reason null, cause DETECTION_POLICY_UNMATCHED) naming every
  key with `listing`, `ex_date`, `unclassified_sources` and `unmatched_roles`. Every row of Example 6-D, pure, through the F8-B append run, and through PostgreSQL as `finweb_app`.
- Money is presented with EXACTLY the currency's minor units (performance Ruling 2.2): 9229.70, not 9229.7 (the real slice's SUMMARY.md showed `9229.7`).
- performance/1.11 (PD-0037): the minor-unit table `minor-units/1.1` has its ten ISO rows CONFIRMED, CNH stays DECLARED, only a MEMORY row is an open item, and the engine is conformant.
"""

import datetime
import json
import sys
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pg_market_kit as pgk  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402
import test_performance_final_review as fr  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402
import test_performance_recheck as rc  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from performance import numerics, rounding  # noqa: E402
from performance.engine import performance_conventions  # noqa: E402
from performance.numerics import RoundingPoint  # noqa: E402
from performance.rounding import PerformanceRounding  # noqa: E402
from performance_service import service as svc  # noqa: E402

D = datetime.date
USD = mp.USD
EX = ca.EX
OLD = D(2023, 6, 1)  # before any holding
D2 = D(2024, 6, 3)  # the ex-date of L2's old record
L2 = fr.Cp3_15PerListingTests.L2
FEED, FILING = ca.FEED, ca.FILING
THIRD = ca.split_reading("third.feed", "f" * 64, (2, 1), day=EX, listing=mp.LISTING)


def feed_and_filing(listing=mp.LISTING):
    return [ca.split_reading(FEED, ca.FEED_SHA, (4, 1), day=EX, listing=listing), ca.split_reading(FILING, ca.FILING_SHA, (4, 1), day=EX, listing=listing)]


def old_filing(listing, day=OLD, ratio=(3, 2)):
    return ca.split_reading("other.filing", "e" * 64, ratio, day=day, listing=listing)


def policy(feed=(FEED,), filing=(FILING, "other.filing")):
    return f8b.ConfirmationPolicy(frozenset(feed), frozenset(filing))


def key(listing, day, unclassified, roles):
    return (str(listing), day.isoformat(), tuple(unclassified), tuple(roles))


def keys_of(unmatched):
    return [key(k.listing, k.ex_date, k.unclassified_sources, k.unmatched_roles) for k in unmatched]


def note_keys(note):
    """The JSON array the refusal's cause carries, parsed back."""
    return json.loads(note.split("unmatched_keys=", 1)[1])


class Example6DPureTests(unittest.TestCase):
    """Example 6-D of Ruling 6.4d: M holds the (4:1) test.feed + test.filing split of L1 at 2025-02-03, an old (3:2) other.filing record of L1 at 2023-06-01 and an old other.filing record of L2 at 2024-06-03;
    the ledger holds L1 across 2025-02-03 with no split, and L2."""

    def world(self, extra=(), with_filing=True):
        L = mp.base_ledger()
        L.add(mp.A1, EventType.BUY, D(2025, 1, 31), USD, listing_id=L2, quantity=Decimal(1), amount=Money(Decimal(100), USD))
        evidence = feed_and_filing() if with_filing else feed_and_filing()[:1]
        readings = mp.closes({D(2025, 1, 31): "100.00", D(2025, 2, 3): "100.00"}, listing=L2, real=True) + evidence + [old_filing(mp.LISTING), old_filing(L2, D2, (2, 1))] + list(extra)
        return L, mp.market(None, real_quotes=True, extra=readings)

    def unmatched(self, pol, **kw):
        L, port = self.world(**kw)
        return svc.policy_unmatched_keys(L.rows, L.version, port, pol)

    def compute(self, pol, **kw):
        L, port = self.world(**kw)
        with rc.pinned(L):
            return svc.compute_for_portfolio(None, ca.PORTFOLIO, EX, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=pol)

    def assert_refused(self, res, expected):
        (m,) = res.metrics
        self.assertIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
        self.assertEqual(m.result.sufficiency_state.value, "INSUFFICIENT_DATA")
        self.assertIsNone(m.result.reason_code)  # Ruling 6.4d item 5: reason null (not SOURCE_CONFLICT, not UNRESOLVED_CONVENTION)
        self.assertIsNone(m.result.value)
        self.assertTrue(m.causes[0].note.startswith(f"{svc.DETECTION_POLICY_UNMATCHED}: "))
        self.assertEqual([(o["listing"], o["ex_date"], tuple(o["unclassified_sources"]), tuple(o["unmatched_roles"])) for o in note_keys(m.causes[0].note)], expected)  # EVERY key, in order
        cited = dict(res.manifest.detection_policy)
        self.assertIn("digest", cited)  # the manifest cites the policy: its digest and the role ids
        self.assertEqual((cited["feed"], cited["filing"]), (",".join(sorted(self.last_policy.feed_sources)), ",".join(sorted(self.last_policy.filing_sources))))

    def check_row(self, pol, expected, **kw):
        self.assertEqual(keys_of(self.unmatched(pol, **kw)), expected)
        self.last_policy = pol
        res = self.compute(pol, **kw)
        if expected:
            self.assert_refused(res, expected)
        return res

    def test_q1_the_correct_policy_is_not_refused_and_the_split_is_corroborated_and_not_recorded(self):
        res = self.check_row(policy(), [])
        (m,) = [m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"]
        self.assertNotIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
        self.assertEqual((m.result.sufficiency_state.value, m.result.reason_code.value), ("INSUFFICIENT_DATA", "SOURCE_CONFLICT"))  # L1 from 2025-02-03; the two old keys are FILING_ONLY (case (e))

    def test_q2_a_filing_role_matched_only_by_an_old_record_of_the_same_listing_is_refused(self):
        self.check_row(policy(filing=("other.filing",)), [key(mp.LISTING, EX, ["test.filing"], ["filing"])])  # a per-listing check passes here: the section 32.1 defeat

    def test_q3_a_typo_matters_through_the_unclassified_source(self):
        self.check_row(policy(filing=("test.filling", "other.filing")), [key(mp.LISTING, EX, ["test.filing"], ["filing"])])

    def test_q4_every_unmatched_key_is_named_ordered_by_listing_id_text_then_ex_date(self):
        self.check_row(policy(filing=("typo.filing",)), [
            key(mp.LISTING, OLD, ["other.filing"], ["feed", "filing"]),
            key(mp.LISTING, EX, ["test.filing"], ["filing"]),
            key(L2, D2, ["other.filing"], ["feed", "filing"])])
        self.assertLess(str(mp.LISTING), str(L2))  # (the order the example assumes)

    def test_case_c_both_roles_matched_and_an_unclassified_source_holds_a_record_is_refused_with_no_unmatched_role(self):
        self.check_row(policy(), [key(mp.LISTING, EX, ["third.feed"], [])], extra=[THIRD])  # empty unmatched_roles: the unclassified source is the whole problem

    def test_case_e_a_key_whose_sources_are_all_classified_is_never_refused_even_feed_only(self):
        res = self.check_row(policy(), [], with_filing=False)  # (L1, 2025-02-03) is FEED_ONLY: SINGLE_SOURCE, no suppression, silence is correct
        (m,) = [m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"]
        self.assertNotIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
        self.assertIsNone(m.result.reason_code)  # nothing suppressed

    def test_case_b_only_unclassified_sources_and_case_d_no_record_at_all(self):
        L = mp.base_ledger()
        lone = mp.market(None, real_quotes=True, extra=[ca.split_reading("stray.feed", "d" * 64, (2, 1), day=OLD, listing=mp.LISTING)])
        self.assertEqual(keys_of(svc.policy_unmatched_keys(L.rows, L.version, lone, policy())), [key(mp.LISTING, OLD, ["stray.feed"], ["feed", "filing"])])  # a lone unclassified source
        self.assertEqual(svc.policy_unmatched_keys(L.rows, L.version, mp.market(None, real_quotes=True), policy()), ())  # no record of the listing: no key

    def test_case_f_a_role_naming_a_source_with_no_record_is_not_a_defect_by_itself(self):
        L = mp.base_ledger()
        port = mp.market("real", real_quotes=True)
        self.assertEqual(svc.policy_unmatched_keys(L.rows, L.version, port, policy(feed=(FEED, "typo.feed"), filing=(FILING, "unused.filing"))), ())

    def test_the_match_is_on_exact_ex_date_equality_no_window(self):
        L = mp.base_ledger()
        # the filing is one day off the feed's ex-date: two keys, each with every source classified, so neither is unmatched (they are not corroborated either: Ruling 4.5 needs equal ex-dates)
        port = mp.market(None, real_quotes=True, extra=[ca.split_reading(FEED, ca.FEED_SHA, (4, 1), day=EX, listing=mp.LISTING), ca.split_reading(FILING, ca.FILING_SHA, (4, 1), day=EX + datetime.timedelta(days=1), listing=mp.LISTING)])
        self.assertEqual(svc.policy_unmatched_keys(L.rows, L.version, port, policy()), ())
        # an unclassified record one day away is its own key, never merged into its neighbour
        port = mp.market("real", real_quotes=True, extra=[ca.split_reading("stray.feed", "d" * 64, (4, 1), day=EX + datetime.timedelta(days=1), listing=mp.LISTING)])
        self.assertEqual(keys_of(svc.policy_unmatched_keys(L.rows, L.version, port, policy(filing=(FILING,)))), [key(mp.LISTING, EX + datetime.timedelta(days=1), ["stray.feed"], ["feed", "filing"])])

    def test_a_reversed_event_still_names_its_listing_and_a_synthetic_world_is_refused_first(self):
        L = mp.base_ledger()
        L.add(mp.A1, EventType.BUY, D(2025, 1, 31), USD, listing_id=L2, quantity=Decimal(1), amount=Money(Decimal(100), USD))
        bought = L.rows[-1].event
        L.add(mp.A1, EventType.REVERSAL, D(2025, 1, 31), USD, reverses_event_id=bought.event_id)
        port = mp.market(None, real_quotes=True, extra=[old_filing(L2, D2, (2, 1))])
        # L2's only event is reversed, but it is still named by an event of the ledger at L: its key is tested (Ruling 6.4d item 2)
        self.assertEqual(keys_of(svc.policy_unmatched_keys(L.rows, L.version, port, policy(filing=("typo.filing",)))), [key(L2, D2, ["other.filing"], ["feed", "filing"])])
        # Ruling 6.4d item 7: the synthetic refusal comes first
        synthetic = mp.market("synthetic", real_quotes=True)
        with rc.pinned(mp.base_ledger()):
            res = svc.compute_for_portfolio(None, ca.PORTFOLIO, EX, USD, synthetic, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=policy(filing=("typo.filing",)))
        self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, res.metrics[0].details)
        self.assertNotIn(svc.DETECTION_POLICY_UNMATCHED, res.metrics[0].details)

    def test_a_policy_with_an_empty_role_or_a_source_in_both_is_refused_when_it_is_configured(self):
        with self.assertRaises(ValueError):
            f8b.ConfirmationPolicy(frozenset(), frozenset({FILING}))
        with self.assertRaises(ValueError):
            f8b.ConfirmationPolicy(frozenset({FEED}), frozenset())
        with self.assertRaises(ValueError):
            f8b.ConfirmationPolicy(frozenset({FEED}), frozenset({FEED, FILING}))


class Example6DAppendRunTests(unittest.TestCase):
    """Ruling 6.4d item 5: under F8-B the append run is refused too, and nothing is appended."""

    def run_f8b(self, pol, readings, dry_run=False):
        ledger = ca.ledger_with_holdings()
        port = ca.port_with(readings)
        report = f8b.confirm_splits(ledger, port, ca.PORTFOLIO, (ca.LISTING,), D(2025, 1, 1), D(2025, 12, 31), pol, {ca.LISTING: USD}, calendars=ca.CALENDARS, exchange_of=ca.exchange_of, dry_run=dry_run)
        return ledger, report

    def evidence(self, listing=ca.LISTING):
        return [ca.split_reading(FEED, ca.FEED_SHA, (4, 1), listing=listing), ca.split_reading(FILING, ca.FILING_SHA, (4, 1), listing=listing)]

    def test_the_correct_policy_still_appends(self):
        ledger, report = self.run_f8b(policy(), self.evidence() + [ca.split_reading("other.filing", "e" * 64, (3, 2), day=OLD)])
        self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.APPENDED])
        self.assertEqual(len(ledger.appended), 1)

    def test_each_refusing_row_appends_nothing_and_names_every_key(self):
        stray = ca.split_reading("other.filing", "e" * 64, (3, 2), day=OLD)
        for pol, extra, expected in (
                (policy(filing=("other.filing",)), [stray], [key(ca.LISTING, EX, ["test.filing"], ["filing"])]),  # Q2
                (policy(filing=("typo.filing",)), [stray], [key(ca.LISTING, OLD, ["other.filing"], ["feed", "filing"]), key(ca.LISTING, EX, ["test.filing"], ["filing"])]),  # Q4
                (policy(), [ca.split_reading("third.feed", "f" * 64, (2, 1))], [key(ca.LISTING, EX, ["third.feed"], [])])):  # case (c)
            ledger = ca.ledger_with_holdings()
            port = ca.port_with(self.evidence() + extra)
            for dry_run in (False, True):
                with self.assertRaises(f8b.DetectionPolicyUnmatchedError) as ctx:
                    f8b.confirm_splits(ledger, port, ca.PORTFOLIO, (ca.LISTING,), D(2025, 1, 1), D(2025, 12, 31), pol, {ca.LISTING: USD}, calendars=ca.CALENDARS, exchange_of=ca.exchange_of, dry_run=dry_run)
                self.assertEqual(keys_of(ctx.exception.keys), expected)
                self.assertEqual(ledger.appended, [])  # nothing appended, in either mode


class MoneyMinorUnitsTests(unittest.TestCase):
    """Ruling 2.2: a presented money amount carries exactly the currency's minor units; the number does not change (equal as a Decimal), only the quantum is kept."""

    RULE = PerformanceRounding()

    def money(self, value, code):
        return numerics.present(value, RoundingPoint.PRESENT_MONEY, CurrencyCode(code), self.RULE)

    def test_a_two_minor_unit_currency_keeps_its_trailing_zero(self):
        p = self.money(Fraction(92297, 10), "EUR")  # the real slice's EUR value
        self.assertEqual(str(p.decimal), "9229.70")
        self.assertEqual(p.decimal.as_tuple().exponent, -2)
        self.assertEqual(p.decimal, Decimal("9229.7"))
        self.assertEqual(str(self.money(Fraction(4375), "USD").decimal), "4375.00")
        self.assertEqual(str(self.money(Fraction(0), "USD").decimal), "0.00")
        self.assertEqual(str(self.money(Fraction(-3, 2), "CNY").decimal), "-1.50")  # exactly -1.5, two places
        self.assertEqual(str(self.money(Fraction(1, 3), "HKD").decimal), "0.33")

    def test_a_zero_minor_unit_currency_has_no_decimals(self):
        p = self.money(Fraction(5000), "JPY")
        self.assertEqual(str(p.decimal), "5000")
        self.assertEqual(p.decimal.as_tuple().exponent, 0)

    def test_returns_and_rates_are_not_padded(self):
        r = numerics.present(Fraction(48033, 1000000), RoundingPoint.PRESENT_RETURN, None, self.RULE)
        self.assertEqual(str(r.decimal), "0.048033")  # 10^-12 is a precision bound, not a fixed number of places (Ruling 2.2)
        self.assertEqual(str(numerics.present(Fraction(5, 4), RoundingPoint.PRESENT_RATE, None, self.RULE).decimal), "1.25")

    def test_a_recorded_fact_is_presented_exactly(self):
        # performance/1.12 Ruling 2.2 items 2 to 4: a money fact is padded to the minor unit and NEVER rounded: max(minor_unit, d(v)) decimals; a quantity (no currency) is unchanged
        def fact(value, code):
            return numerics.present(value, RoundingPoint.PRESENT_FACT, None if code is None else CurrencyCode(code), self.RULE)

        for value, code, text in (
                (Fraction(5, 2), "USD", "2.50"), (Fraction(1, 8), "USD", "0.125"), (Fraction(5000), "JPY", "5000"), (Fraction(25, 2), "JPY", "12.5"),
                (Fraction(0), "USD", "0.00"), (Fraction(2248), "USD", "2248.00"), (Fraction(-7, 2), "USD", "-3.50"), (Fraction(1000), "HKD", "1000.00"), (Fraction(5, 2), None, "2.5")):
            p = fact(value, code)
            self.assertEqual((str(p.decimal), p.decimal == Decimal(value.numerator) / Decimal(value.denominator)), (text, True), (value, code))  # the number is unchanged
            self.assertIsNone(p.detail, (value, code))
        # the recorded scale is not used: 2248, 2248.0 and 2248.0000 are one exact value, one presentation
        self.assertEqual({str(fact(Fraction(Decimal(t)), "USD").decimal) for t in ("2248", "2248.0", "2248.0000")}, {"2248.00"})
        # a currency outside the table: the shortest exact form, unpadded, with the detail, the state unchanged
        odd = fact(Fraction(5, 2), "XXX")
        self.assertEqual((str(odd.decimal), odd.detail, odd.status), ("2.5", "CURRENCY_NO_MINOR_UNIT", numerics.PresentStatus.OK))
        self.assertEqual(str(fact(Fraction(2248), "XXX").decimal), "2248")

    def test_the_money_helper_never_rounds(self):
        self.assertEqual(str(numerics.to_decimal_money(Fraction(5, 2), 2)), "2.50")
        self.assertIsNone(numerics.to_decimal_money(Fraction(1, 3), 2))  # not terminating: no Decimal
        self.assertEqual(str(numerics.to_decimal_money(Fraction(1, 8), 2)), "0.125")  # off the quantum: the exact value, never rounded here

    def test_the_engine_presents_the_valuation_and_its_breakdown_with_two_places(self):
        L = mp.base_ledger()
        port = mp.market(None, real_quotes=True)
        with rc.pinned(L):
            res = svc.compute_for_portfolio(None, ca.PORTFOLIO, D(2025, 1, 31), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=ca.POLICY)
        shown = [m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"]
        self.assertTrue(shown)
        for m in shown:
            self.assertIsNotNone(m.result.value)
            self.assertEqual(m.result.value.as_tuple().exponent, -2, str(m.result.value))
            for _name, part, _exact in m.breakdown:
                self.assertEqual(part.as_tuple().exponent, -2, str(part))


class MinorUnitTable11Tests(unittest.TestCase):
    """performance/1.11 Ruling 2.3 and section 16 item 16 (PD-0037, HG2 condition 2)."""

    def test_the_table_is_minor_units_1_1_with_ten_confirmed_rows_cnh_declared_and_the_same_decimals(self):
        self.assertEqual(rounding.MINOR_UNIT_TABLE_VERSION, "minor-units/1.1")
        rows = {code: (decimals, status) for code, decimals, status in rounding.MINOR_UNIT_ROWS}
        self.assertEqual(rows, {**{c: (2, "CONFIRMED") for c in ("USD", "HKD", "CNY", "EUR", "GBP", "CHF", "SGD", "AUD", "CAD")}, "JPY": (0, "CONFIRMED"), "CNH": (2, "DECLARED")})
        self.assertEqual(rounding.decimals_by_currency(), {c: (0 if c == "JPY" else 2) for c in rows})  # value-equivalent to minor-units/1: no minor unit changed

    def test_only_a_memory_row_is_an_open_item(self):
        self.assertEqual(rounding.MinorUnitTable().open_items(), ())
        later = rounding.MinorUnitTable(rows=rounding.MINOR_UNIT_ROWS + (("XXX", 2, rounding.MEMORY),))  # a currency added later starts as MEMORY
        (item,) = later.open_items()
        self.assertIn("XXX", item)
        self.assertNotIn("USD", item)
        declared_only = rounding.MinorUnitTable(rows=(("CNH", 2, rounding.DECLARED),))
        self.assertEqual(declared_only.open_items(), ())

    def test_the_engine_is_conformant_and_cites_the_1_11_ids(self):
        perf = performance_conventions()
        self.assertTrue(perf.is_conformant)
        self.assertEqual(perf.visible_open_items(), ())
        self.assertEqual(perf.convention_set_id, "performance/1.12")
        self.assertEqual(perf.rounding.rule_id, "performance/1.12#2.2-2.4")
        self.assertEqual(perf.rounding.table_version, "minor-units/1.1")
        for slot in ("aggregation", "annualization", "flow_table", "rounding", "twr", "valuation", "windows"):
            self.assertTrue(perf.ids()[slot].startswith("performance/1.12#"), slot)

    def test_a_placeholder_rule_still_makes_it_non_conformant(self):
        import dataclasses  # noqa: PLC0415

        perf = dataclasses.replace(performance_conventions(), twr_rule_id="placeholder/twr/0")
        self.assertFalse(perf.is_conformant)


@unittest.skipIf(bool(pgk.skip_reason()), pgk.skip_reason())
class Example6DPostgresTests(unittest.TestCase):
    """The rows of Example 6-D through PostgreSQL as `finweb_app`: the ledger is a real, disposable `finweb_it_*` schema; the market-data port is in memory. L1 is the AAPL listing of the shared identity registry;
    L2 is its 0700 listing (an HKD BUY is enough to name it: the refusal never values it)."""

    @classmethod
    def setUpClass(cls):
        rc.PostgresRecheckTests.setUpClass.__func__(cls)
        cls.h = pgk and __import__("marketdata_exit_kit").lid(cls.ident, "0700", "XHKG")

    portfolio = fr.Cp3_14PostgresTests.portfolio

    def two_listing_portfolio(self):
        user, portfolio, account = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        owner = self.db.owner
        owner.execute("INSERT INTO app_user VALUES (%s)", (user,))
        owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (portfolio, user))
        owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (account, portfolio))
        hkd = CurrencyCode("HKD")
        self.ls.append_batch(self.app, [
            LedgerEvent(uuid.uuid4(), account, EventType.DEPOSIT, D(2024, 12, 19), USD, amount=Money(Decimal(10000), USD)),
            LedgerEvent(uuid.uuid4(), account, EventType.BUY, D(2024, 12, 20), USD, listing_id=self.aapl, quantity=Decimal(50), amount=Money(Decimal(7500), USD)),
            LedgerEvent(uuid.uuid4(), account, EventType.DEPOSIT, D(2024, 12, 19), hkd, amount=Money(Decimal(1000), hkd)),
            LedgerEvent(uuid.uuid4(), account, EventType.BUY, D(2024, 12, 20), hkd, listing_id=self.h, quantity=Decimal(1), amount=Money(Decimal(500), hkd))])
        return portfolio

    def market(self, extra=()):
        readings = [r for r in feed_and_filing(self.aapl)] + [old_filing(self.aapl), old_filing(self.h, D2, (2, 1))] + list(extra)
        return mp.market(None, real_quotes=True, listing=self.aapl, mic="XNAS", extra=readings)

    def entries(self, portfolio, market, pol):
        args = (USD, market, self.ident, self.conventions, mp.PERF)
        return (svc.compute_for_portfolio(self.app, portfolio, EX, *args, policy=pol),
                svc.compute_attribution_for_portfolio(self.app, portfolio, fr.CUSTOM, EX, *args, policy=pol),
                svc.compute_gains_for_portfolio(self.app, portfolio, EX, *args, policy=pol, window=fr.CUSTOM))

    def check_refused(self, portfolio, pol, expected, extra=()):
        for res in self.entries(portfolio, self.market(extra), pol):  # all three entries refuse the same way
            (m,) = res.metrics
            self.assertIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
            self.assertIsNone(m.result.value)
            self.assertIsNone(m.result.reason_code)
            self.assertEqual([(o["listing"], o["ex_date"], tuple(o["unclassified_sources"]), tuple(o["unmatched_roles"])) for o in note_keys(m.causes[0].note)], expected)

    def test_q2_and_q3_the_reviewers_probe_is_refused_through_postgresql(self):
        portfolio = self.portfolio(hops=False, sale=False)  # 50 units held, the corroborated 4:1 is NOT in the ledger
        for filing in (("other.filing",), ("test.filling", "other.filing")):
            self.check_refused(portfolio, policy(filing=filing), [key(self.aapl, EX, ["test.filing"], ["filing"])])  # the review's probe gave AVAILABLE for the listing here

    def test_q4_names_all_three_keys_in_order_and_case_c_has_no_unmatched_role(self):
        portfolio = self.two_listing_portfolio()
        expected = [key(self.aapl, OLD, ["other.filing"], ["feed", "filing"]), key(self.aapl, EX, ["test.filing"], ["filing"]), key(self.h, D2, ["other.filing"], ["feed", "filing"])]
        expected.sort(key=lambda k: (k[0], k[1]))  # (listing id as text, then the ex-date)
        self.check_refused(portfolio, policy(filing=("typo.filing",)), expected)
        third = ca.split_reading("third.feed", "f" * 64, (2, 1), day=EX, listing=self.aapl)
        self.check_refused(portfolio, policy(), [key(self.aapl, EX, ["third.feed"], [])], extra=[third])

    def test_the_f8b_append_run_through_postgresql_is_refused_and_appends_nothing_but_the_correct_policy_appends(self):
        portfolio = self.portfolio(hops=False, sale=False)  # 50 units held, the corroborated 4:1 is NOT in the ledger
        access = f8b.PostgresLedgerAccess(self.app)
        port = self.market()
        args = (port, portfolio, [self.aapl], D(2025, 1, 1), D(2025, 12, 31))
        kw = dict(trading_currency={self.aapl: USD}, calendars=self.conventions.freshness.calendars, exchange_of=self.ident.exchange_mic)
        before = self.rs.current_ledger_version(self.app, portfolio)
        with self.assertRaises(f8b.DetectionPolicyUnmatchedError) as ctx:
            f8b.confirm_splits(access, *args, policy(filing=("other.filing",)), **kw)
        self.assertEqual(keys_of(ctx.exception.keys), [key(self.aapl, EX, ["test.filing"], ["filing"])])  # the portfolio names AAPL only: L2's old record is not a key here
        self.assertEqual(self.rs.current_ledger_version(self.app, portfolio), before)  # nothing appended
        report = f8b.confirm_splits(access, *args, policy(), **kw)  # the correct policy classifies every source: the split is appended
        self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.APPENDED])
        self.assertGreater(self.rs.current_ledger_version(self.app, portfolio), before)

    def test_q1_and_case_e_are_not_refused_and_the_check_writes_nothing(self):
        portfolio = self.portfolio(hops=False, sale=False)
        before = self.rs.current_ledger_version(self.app, portfolio)  # CP4-5: compare the state before and after the calls (the old assertion read the version twice with no call between)
        for res in self.entries(portfolio, mp.market(None, real_quotes=True, listing=self.aapl, mic="XNAS", extra=feed_and_filing(self.aapl) + [old_filing(self.aapl)]), policy()):
            self.assertTrue(all(svc.DETECTION_POLICY_UNMATCHED not in m.details for m in res.metrics))
        feed_only = mp.market(None, real_quotes=True, listing=self.aapl, mic="XNAS", extra=feed_and_filing(self.aapl)[:1])
        for res in self.entries(portfolio, feed_only, policy()):  # case (e)
            self.assertTrue(all(svc.DETECTION_POLICY_UNMATCHED not in m.details for m in res.metrics))
        self.assertEqual(self.rs.current_ledger_version(self.app, portfolio), before)  # six computations ran (value, attribution, gains, twice): the ledger is unchanged


if __name__ == "__main__":
    unittest.main()
