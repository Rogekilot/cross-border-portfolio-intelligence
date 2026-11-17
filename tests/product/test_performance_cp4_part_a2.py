"""CP4 part A, round 2 (tech plan 16.25): review section 33 (CP4-1, CP4-2, CP4-4, CP4-5) and `performance/1.12`.

- CP4-1: the F8-B append run tests the confirmation policy on EVERY ledger load a decision reads, so a listing that enters the ledger mid-run cannot skip Ruling 6.4d.
- CP4-2 and Ruling 1.7 (1.12) item 5: a Current-mode refusal records what a computed Current-mode result records (`t`, `D_c(t)`, the as-of rule, `M`, the hashes `M_t` leaves out, `M_t`'s release id).
- CP4-3 and Ruling 2.2 (1.12): a recorded money FACT is padded to the minor unit and never rounded, in the NATIVE view (the REPORTING view is derived).
- CP4-4: the summary of a pack lists the market-data open items the manifests carry, and no stale "is_conformant is False" limitation.
- CP4-5: behaviour tests for the since-acquisition and attribution breakdown parts, the F8-B key set from the ledger (not the caller's list), and the transfer-only listing.
- Ruling 1.7 (1.12) item 2 (Example 1.7-C): `D_c(t)` also tests every live ledger event dated `D`; item 1: the calendar check; item 4: `source_registry_digest`.
"""

import dataclasses
import datetime
import json
import sys
import tempfile
import unittest
import uuid
import zoneinfo
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_kit  # noqa: E402
import marketdata_cp2c1_kit as k  # noqa: E402
import performance_kit as pk  # noqa: E402
import pg_market_kit as pgk  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402
import test_performance_attribution as ta  # noqa: E402
import test_performance_cp4_part_a as a1  # noqa: E402
import test_performance_final_review as fr  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402
import test_performance_real_fx as rfx  # noqa: E402
import test_performance_recheck as rc  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
import unittest.mock  # noqa: E402
from marketdata.manifest import MarketDataRelease, SourceRecord, SourceRegistryNotPinnedError, TermsCheck, source_registry_digest  # noqa: E402
from marketdata.market11 import UNBUILT, market11_conventions  # noqa: E402
from marketdata.store import InMemoryMarketData  # noqa: E402
from performance import current, engine  # noqa: E402
from performance.inputs import MarketView  # noqa: E402
from performance.manifest import ReproductionStatus  # noqa: E402
from performance.periods import WindowRule, WindowSpec  # noqa: E402
from performance_service import service as svc  # noqa: E402
from performance_tools import pack, real_slice  # noqa: E402

D, F = datetime.date, Fraction
UTC = datetime.timezone.utc
USD, HKD = mp.USD, CurrencyCode("HKD")
EX = ca.EX
T = datetime.time


# ===== CP4-1 ===================================================================================================================================

class RacingLedger(ca.FakeLedger):
    """A ledger whose Nth `load` first sees a concurrent writer's event (the run is not one transaction)."""

    def __init__(self, race_on_load, event):
        super().__init__()
        self.loads, self.race_on_load, self.event = 0, race_on_load, event

    def load(self, portfolio_id):
        self.loads += 1
        if self.loads == self.race_on_load:
            self.add(self.event)
        return super().load(portfolio_id)


class Cp4_1Tests(unittest.TestCase):
    B = ca.OTHER_LISTING

    def readings(self):
        # B has the classified feed and filing at 4:1 and an UNCLASSIFIED third.feed at 2:1 on one ex-date: case (c), `DISAGREEMENT` if it were classified
        return [ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1), listing=self.B), ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1), listing=self.B),
                ca.split_reading("third.feed", "f" * 64, (2, 1), listing=self.B)]

    def bought(self):
        return LedgerEvent(ca.eid(), ca.A1, EventType.BUY, D(2024, 12, 23), USD, listing_id=self.B, quantity=Decimal(50), amount=Money(Decimal(7500), USD))

    def run_f8b(self, ledger):
        return f8b.confirm_splits(ledger, ca.port_with(self.readings()), ca.PORTFOLIO, (ca.LISTING, self.B), D(2025, 1, 1), D(2025, 12, 31), ca.POLICY,
                                  {ca.LISTING: USD, self.B: USD}, calendars=ca.CALENDARS, exchange_of=ca.exchange_of)

    def test_a_listing_that_enters_the_ledger_after_the_first_load_is_still_tested_and_nothing_is_appended(self):
        # the reviewer's interleaving: B is not on the ledger when the first load is tested; a concurrent writer appends a BUY of B before the decisions load it again
        for race_on in (2, 3):  # between the test and the version read, and between the version read and the decision's load
            ledger = RacingLedger(race_on, self.bought())
            ledger.add(LedgerEvent(ca.eid(), ca.A1, EventType.DEPOSIT, D(2024, 12, 20), USD, amount=Money(Decimal(10000), USD)))
            with self.assertRaises(f8b.DetectionPolicyUnmatchedError) as ctx:
                self.run_f8b(ledger)
            self.assertEqual(a1.keys_of(ctx.exception.keys), [a1.key(self.B, EX, ["third.feed"], [])], race_on)
            self.assertEqual(ledger.appended, [], race_on)  # was: a 4:1 split appended to B that the full evidence disputes

    def test_without_the_race_the_same_world_is_refused_at_the_first_load(self):
        ledger = ca.ledger_with_holdings()
        ledger.add(self.bought())
        with self.assertRaises(f8b.DetectionPolicyUnmatchedError):
            self.run_f8b(ledger)
        self.assertEqual(ledger.appended, [])

    def test_a_listing_already_tested_is_not_tested_again_so_the_run_still_appends_for_a_classified_world(self):
        ledger = ca.ledger_with_holdings()
        clean = [ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1)), ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1))]
        report = f8b.confirm_splits(ledger, ca.port_with(clean), ca.PORTFOLIO, (ca.LISTING,), D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {ca.LISTING: USD},
                                    calendars=ca.CALENDARS, exchange_of=ca.exchange_of)
        self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.APPENDED])


# ===== CP4-5: m9 (the key set comes from the ledger, not the caller's list) and m12 (a listing named only by a TRANSFER_IN) ======================

class KeySetTests(unittest.TestCase):
    def transfer_in_ledger(self):
        L = mp.base_ledger()
        L.add(mp.A1, EventType.TRANSFER_IN, D(2025, 1, 15), USD, listing_id=a1.L2, quantity=Decimal(10))  # L2 is named by this event ALONE
        return L

    def test_m12_a_listing_named_only_by_a_transfer_in_is_a_key(self):
        L = self.transfer_in_ledger()
        port = mp.market("real", real_quotes=True, extra=[a1.old_filing(a1.L2, a1.D2, (2, 1))])
        self.assertEqual(a1.keys_of(svc.policy_unmatched_keys(L.rows, L.version, port, a1.policy(filing=("typo.filing",)))),
                         [a1.key(mp.LISTING, a1.EX, ["test.filing"], ["filing"]), a1.key(a1.L2, a1.D2, ["other.filing"], ["feed", "filing"])])
        # and the whole computation is refused for it (a1.policy classifies other.filing, test.filing and test.feed: the transfer-only listing's record is classified, so only a bad policy refuses)
        with rc.pinned(L):
            res = svc.compute_for_portfolio(None, ca.PORTFOLIO, a1.EX, USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=a1.policy(feed=(a1.FEED,), filing=("typo.filing",)))
        self.assertIn(svc.DETECTION_POLICY_UNMATCHED, res.metrics[0].details)
        self.assertIn(str(a1.L2), res.metrics[0].causes[0].note)

    def test_m9_the_f8b_run_takes_its_keys_from_the_ledger_not_from_the_callers_list(self):
        ledger = ca.ledger_with_holdings()
        ledger.add(LedgerEvent(ca.eid(), ca.A1, EventType.TRANSFER_IN, D(2025, 1, 15), USD, listing_id=ca.OTHER_LISTING, quantity=Decimal(10)))  # the ledger names B; the caller does not
        readings = [ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1)), ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1)), ca.split_reading("stray.filing", "9" * 64, (2, 1), day=D(2024, 6, 3), listing=ca.OTHER_LISTING)]
        with self.assertRaises(f8b.DetectionPolicyUnmatchedError) as ctx:
            f8b.confirm_splits(ledger, ca.port_with(readings), ca.PORTFOLIO, (ca.LISTING,), D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {ca.LISTING: USD},
                               calendars=ca.CALENDARS, exchange_of=ca.exchange_of)
        self.assertEqual(a1.keys_of(ctx.exception.keys), [a1.key(ca.OTHER_LISTING, D(2024, 6, 3), ["stray.filing"], ["feed", "filing"])])
        self.assertEqual(ledger.appended, [])  # the corroborated split of the caller's listing was not appended either: the whole run is refused


@unittest.skipIf(bool(pgk.skip_reason()), pgk.skip_reason())
class KeySetPostgresTests(unittest.TestCase):
    """m9 and m12 through PostgreSQL as `finweb_app`: a listing named only by a TRANSFER_IN (the AAPL position has a corroborated 4:1 the ledger lacks)."""

    @classmethod
    def setUpClass(cls):
        rc.PostgresRecheckTests.setUpClass.__func__(cls)
        cls.h = __import__("marketdata_exit_kit").lid(cls.ident, "0700", "XHKG")

    def portfolio(self):
        user, portfolio, account = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        owner = self.db.owner
        owner.execute("INSERT INTO app_user VALUES (%s)", (user,))
        owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (portfolio, user))
        owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (account, portfolio))
        self.ls.append_batch(self.app, [
            LedgerEvent(uuid.uuid4(), account, EventType.DEPOSIT, D(2024, 12, 19), USD, amount=Money(Decimal(10000), USD)),
            LedgerEvent(uuid.uuid4(), account, EventType.BUY, D(2024, 12, 20), USD, listing_id=self.aapl, quantity=Decimal(50), amount=Money(Decimal(7500), USD)),
            LedgerEvent(uuid.uuid4(), account, EventType.TRANSFER_IN, D(2025, 1, 15), HKD, listing_id=self.h, quantity=Decimal(10))])
        return portfolio

    def market(self):
        extra = a1.feed_and_filing(self.aapl) + [ca.split_reading("stray.filing", "9" * 64, (2, 1), day=D(2024, 6, 3), listing=self.h)]
        return mp.market(None, real_quotes=True, listing=self.aapl, mic="XNAS", extra=extra)

    def test_the_service_names_the_transfer_only_listing_in_all_three_entries(self):
        portfolio = self.portfolio()
        args = (USD, self.market(), self.ident, self.conventions, mp.PERF)
        for res in (svc.compute_for_portfolio(self.app, portfolio, a1.EX, *args, policy=ca.POLICY),
                    svc.compute_attribution_for_portfolio(self.app, portfolio, fr.CUSTOM, a1.EX, *args, policy=ca.POLICY),
                    svc.compute_gains_for_portfolio(self.app, portfolio, a1.EX, *args, policy=ca.POLICY, window=fr.CUSTOM)):
            (m,) = res.metrics
            self.assertIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
            self.assertEqual([(o["listing"], o["ex_date"], tuple(o["unclassified_sources"]), tuple(o["unmatched_roles"])) for o in a1.note_keys(m.causes[0].note)],
                             [a1.key(self.h, D(2024, 6, 3), ["stray.filing"], ["feed", "filing"])])

    def test_the_f8b_run_over_postgresql_refuses_for_the_transfer_only_listing_the_caller_did_not_name(self):
        portfolio = self.portfolio()
        access = f8b.PostgresLedgerAccess(self.app)
        before = self.rs.current_ledger_version(self.app, portfolio)
        with self.assertRaises(f8b.DetectionPolicyUnmatchedError) as ctx:
            f8b.confirm_splits(access, self.market(), portfolio, [self.aapl], D(2025, 1, 1), D(2025, 12, 31), ca.POLICY, {self.aapl: USD},
                               calendars=self.conventions.freshness.calendars, exchange_of=self.ident.exchange_mic)
        self.assertEqual(a1.keys_of(ctx.exception.keys), [a1.key(self.h, D(2024, 6, 3), ["stray.filing"], ["feed", "filing"])])
        self.assertEqual(self.rs.current_ledger_version(self.app, portfolio), before)  # AAPL's corroborated split was NOT appended: the whole run is refused


# ===== CP4-2 and Ruling 1.7 (1.12) item 5: a Current-mode refusal is a Current-mode result ======================================================

def utc_dt(*a):
    return datetime.datetime(*a, tzinfo=UTC)


class RecordedMarketAt:
    """`M_t` over readings with retrieval times, as a derived release (the probe of the recheck module, with the calendars and exchange this test needs)."""

    def __init__(self, readings, calendars, conventions, exchange_of):
        self.readings, self.calendars, self.conventions, self.exchange_of = list(readings), calendars, conventions, exchange_of
        with gate_kit.admitted_real_world(self.readings, *[exchange_of(r.observation.listing_id) for r in self.readings if hasattr(r.observation, "listing_id")]):  # 1.16 Ruling 4.7 item 6: see gate_kit
            self.parent = InMemoryMarketData(MarketDataRelease(name="m-parent", files=(), source_precedence=()), self.readings, exchange_of=exchange_of, source_records=k.records_for(self.readings))

    def view(self, instant):
        keep = [r for r in self.readings if r.observation.lineage.retrieved_at <= instant]
        kept = {r.file_sha256 for r in keep}
        left = tuple(sorted({r.file_sha256 for r in self.readings if r.observation.lineage.retrieved_at > instant} - kept))
        release = MarketDataRelease(name=f"m-t@{instant.isoformat()}", files=(), source_precedence=())
        with gate_kit.admitted_real_world(keep, *[self.exchange_of(r.observation.listing_id) for r in keep if hasattr(r.observation, "listing_id")]):
            store = InMemoryMarketData(release, keep, exchange_of=self.exchange_of, contains_synthetic=any(r.observation.lineage.is_synthetic for r in keep), source_records=k.records_for(keep))
        return MarketView(store, self.calendars, self.conventions, self.parent.release_id(), left, instant)


def stamp(reading, when):
    lin = dataclasses.replace(reading.observation.lineage, retrieved_at=when)
    return dataclasses.replace(reading, observation=dataclasses.replace(reading.observation, lineage=lin))


def real_quote(listing, day, price, retrieved):
    r = pk.quote(listing, day, price, USD, "US", retrieved=retrieved, sha="e" * 64)
    return dataclasses.replace(r, observation=dataclasses.replace(r.observation, lineage=dataclasses.replace(r.observation.lineage, usage_scope=ca.REAL)))


def assert_current_record(testcase, res, instant, market_at, expected_as_of, *, expect_excluded=None):
    m = res.manifest
    view = market_at.view(instant)
    testcase.assertEqual((m.as_of_rule, m.instant), ("D_c(t)", instant))  # a Current-mode refusal says it is one
    testcase.assertEqual(m.parent_release_id, market_at.parent.release_id())  # M
    testcase.assertEqual(m.release_id, view.port.release_id())  # M_t
    testcase.assertEqual(m.excluded_files, tuple(sorted(view.excluded_files)))  # the hashes M_t leaves out
    if expect_excluded is not None:
        testcase.assertEqual(m.excluded_files, tuple(sorted(expect_excluded)))
    testcase.assertEqual(m.as_of, expected_as_of)  # D_c(t) if one was chosen
    testcase.assertEqual(m.valuation_mode, "CURRENT_AT_INSTANT")  # the Current value (performance/1.12 build note), refused or computed
    testcase.assertTrue(m.identity_digest and m.source_registry_digest)  # CP4-7: both digests, over the view the refusal read


class Cp4_2Tests(unittest.TestCase):
    """The probe world of the recheck module: AAPL-like listing `mp.LISTING` (USD, MIC XTST), the XTST calendar of `ca.CALENDARS`: a Tuesday close is 16:00 New York = 21:00 UTC."""

    T_LATE = utc_dt(2025, 2, 11, 23, 0)  # after the 02-11 close: D_c(t) = 2025-02-11
    T_EARLY = utc_dt(2025, 2, 6, 23, 0)

    def market_at(self, *, synthetic=False, third=False):
        quotes = [real_quote(mp.LISTING, d, p, utc_dt(2025, 2, 4, 0, 0)) for d, p in mp.PRICES.items()]
        usage = ca.SYN if synthetic else ca.REAL
        evidence = [stamp(ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1), usage=usage), utc_dt(2025, 2, 10, 12, 0)),
                    stamp(ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1), usage=usage), utc_dt(2025, 2, 10, 12, 0))]
        if third:
            evidence.append(stamp(ca.split_reading("third.feed", "f" * 64, (2, 1)), utc_dt(2025, 2, 10, 12, 0)))
        return RecordedMarketAt(quotes + evidence, ca.CALENDARS, mp.MARKET_CONVENTIONS, lambda _l: mp.MIC)

    def run_at(self, instant, market_at, policy=ca.POLICY):
        with rc.pinned(mp.base_ledger()):
            return svc.compute_current_for_portfolio(None, ca.PORTFOLIO, instant, USD, mp.Ident(), market_at, mp.PERF, policy=policy)

    def test_a_policy_refusal_over_m_t_records_t_m_m_t_the_excluded_files_and_d_c_t(self):
        market_at = self.market_at(third=True)
        res = self.run_at(self.T_LATE, market_at)  # M_t holds the unclassified third.feed record (retrieved 02-10): case (c)
        (m,) = res.metrics
        self.assertIn(svc.DETECTION_POLICY_UNMATCHED, m.details)
        assert_current_record(self, res, self.T_LATE, market_at, D(2025, 2, 11))
        self.assertEqual(res.manifest.excluded_files, ())
        # before the evidence was retrieved M_t does not hold it: no refusal, and the computed result records the same fields
        early = self.run_at(self.T_EARLY, market_at)
        self.assertNotIn(svc.DETECTION_POLICY_UNMATCHED, early.metrics[0].details)
        self.assertEqual((early.manifest.as_of_rule, early.manifest.instant, early.manifest.parent_release_id), ("D_c(t)", self.T_EARLY, market_at.parent.release_id()))
        self.assertEqual(early.manifest.excluded_files, tuple(sorted({ca.FEED_SHA, ca.FILING_SHA, "f" * 64})))

    def test_a_refusal_at_an_instant_that_excludes_files_names_them(self):
        # a policy that classifies nothing the evidence uses refuses over M_t = the evidence retrieved by t only; at T_EARLY M_t holds no corporate-action record, so use the late instant with a later file
        market_at = self.market_at(third=True)
        later = stamp(ca.split_reading("later.feed", "1" * 64, (3, 1)), utc_dt(2025, 3, 1, 0, 0))
        market_at.readings.append(later)
        res = self.run_at(self.T_LATE, market_at)
        assert_current_record(self, res, self.T_LATE, market_at, D(2025, 2, 11), expect_excluded=["1" * 64])

    def test_the_synthetic_refusal_in_current_mode_records_the_same(self):
        market_at = self.market_at(synthetic=True)
        res = self.run_at(self.T_LATE, market_at)
        self.assertIn(svc.SYNTHETIC_MARKET_DATA_REFUSED, res.metrics[0].details)
        assert_current_record(self, res, self.T_LATE, market_at, D(2025, 2, 11))

    def test_a_historical_refusal_is_unchanged(self):
        with rc.pinned(mp.base_ledger()):
            res = svc.compute_for_portfolio(None, ca.PORTFOLIO, a1.EX, USD, mp.market("synthetic", real_quotes=True), mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=ca.POLICY)
        self.assertEqual((res.manifest.as_of_rule, res.manifest.instant, res.manifest.parent_release_id), ("CALLER", None, None))

    def test_a_coverage_gap_and_an_unchosen_date_record_t_m_and_m_t(self):
        w = pk.World(pk.example_w_readings(pk.x.lid(pk.x.identity(), "0700", "XHKG")))
        L = pk.Ledger().add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), HKD, listing_id=w.h, quantity=Decimal(100))
        sat = utc_dt(2025, 4, 5, 12, 0)  # past the calendars' coverage: D_c(t) cannot be chosen
        res = engine.compute_current(L.rows, L.version, sat, USD, w.ident, w.market_at, mp.PERF, suppressions=())
        view = w.market_at.view(sat)
        (m,) = res.metrics
        self.assertIsNone(m.result.value)
        self.assertEqual((res.manifest.as_of_rule, res.manifest.instant), ("D_c(t)", sat))
        self.assertEqual((res.manifest.parent_release_id, res.manifest.release_id), (view.parent_release_id, view.port.release_id()))  # M and M_t
        self.assertTrue(res.manifest.as_of_causes)  # why no D_c(t) could be chosen


# ===== CP4-2 through PostgreSQL as finweb_app =======================================================================================================

@unittest.skipIf(bool(pgk.skip_reason()), pgk.skip_reason())
class Cp4_2PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rc.PostgresRecheckTests.setUpClass.__func__(cls)

    portfolio = fr.Cp3_14PostgresTests.portfolio

    def market_at(self, *, third=False, synthetic=False):
        calendars = self.conventions.freshness.calendars
        usage = ca.SYN if synthetic else ca.REAL
        quotes = [real_quote(self.aapl, d, p, utc_dt(2025, 2, 4, 0, 0)) for d, p in mp.PRICES.items()]
        evidence = [stamp(ca.split_reading(ca.FEED, ca.FEED_SHA, (4, 1), listing=self.aapl, usage=usage), utc_dt(2025, 2, 10, 12, 0)),
                    stamp(ca.split_reading(ca.FILING, ca.FILING_SHA, (4, 1), listing=self.aapl, usage=usage), utc_dt(2025, 2, 10, 12, 0))]
        if third:
            evidence.append(stamp(ca.split_reading("third.feed", "f" * 64, (2, 1), listing=self.aapl), utc_dt(2025, 2, 10, 12, 0)))
        later = stamp(ca.split_reading("later.feed", "1" * 64, (3, 1), listing=self.aapl), utc_dt(2025, 3, 1, 0, 0))
        return RecordedMarketAt(quotes + evidence + [later], calendars, self.conventions, self.ident.exchange_mic)

    def test_the_refusals_of_every_current_entry_record_t_m_m_t_and_d_c_t(self):
        portfolio = self.portfolio(hops=False, sale=False)
        t = utc_dt(2025, 2, 11, 23, 0)
        for third, synthetic, code in ((True, False, svc.DETECTION_POLICY_UNMATCHED), (False, True, svc.SYNTHETIC_MARKET_DATA_REFUSED)):
            market_at = self.market_at(third=third, synthetic=synthetic)
            results = (svc.compute_current_for_portfolio(self.app, portfolio, t, USD, self.ident, market_at, mp.PERF, policy=ca.POLICY),
                       svc.compute_gains_current_for_portfolio(self.app, portfolio, t, USD, self.ident, market_at, mp.PERF, policy=ca.POLICY, window=fr.CUSTOM),
                       svc.compute_attribution_current_for_portfolio(self.app, portfolio, t, fr.CUSTOM, USD, self.ident, market_at, mp.PERF, policy=ca.POLICY))
            for res in results:
                self.assertIn(code, res.metrics[0].details)
                assert_current_record(self, res, t, market_at, D(2025, 2, 11), expect_excluded=["1" * 64])
        before = self.rs.current_ledger_version(self.app, portfolio)
        self.assertEqual(before, self.rs.current_ledger_version(self.app, portfolio))


# ===== Ruling 1.7 (1.12) item 2: D_c(t) tests every live event dated D (Example 1.7-C) ===============================================================

def weekdays(first, last):
    out, day = [], first
    while day <= last:
        if day.weekday() < 5:
            out.append(day)
        day += datetime.timedelta(days=1)
    return out


class Example17CTests(unittest.TestCase):
    """Example 1.7-C: 2026-10-01 (Thursday) and 2026-10-02 (Friday) are fixing days; the ECB publishes 16:00 Berlin = 14:00 UTC (CEST); an XNYS close is 16:00 New York = 20:00 UTC (EDT); t = 2026-10-02 12:00 UTC."""

    T12 = utc_dt(2026, 10, 2, 12, 0)

    def setUp(self):
        days = weekdays(D(2026, 9, 28), D(2026, 10, 9))
        self.ident = pk.x.identity()
        self.h, self.aapl = pk.x.lid(self.ident, "0700", "XHKG"), pk.x.lid(self.ident, "AAPL", "XNAS")
        self.calendars = CalendarSet([k.exchange_calendar("HKEX_SESSIONS", ("XHKG",), days, tz="Asia/Hong_Kong", default_close=T(16, 10)),
                                      k.exchange_calendar("NYSE_SESSIONS", ("XNYS", "XNAS"), days, tz="America/New_York"), k.ecb_calendar(days)])

    def choose(self, ledger, t=None, currency_of=None):
        return current.choose_current_date(t or self.T12, ledger.rows, ledger.version, self.calendars, self.ident.exchange_mic, USD, currency_of or self.ident.trading_currency)

    def withdrawal_ledger(self, withdrawal_day=D(2026, 10, 2)):
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2026, 9, 30), USD, amount=Money(Decimal(1000), USD))
        L.add(pk.A1, EventType.DEPOSIT, D(2026, 9, 30), HKD, amount=Money(Decimal(7800), HKD))
        L.add(pk.A1, EventType.WITHDRAWAL, withdrawal_day, HKD, amount=Money(Decimal(7800), HKD))  # all of it: nothing foreign is held at the end of the day
        return L

    def in_kind_ledger(self):
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2026, 9, 30), USD, amount=Money(Decimal(1000), USD))
        L.add(pk.A1, EventType.TRANSFER_IN, D(2026, 9, 30), USD, listing_id=self.aapl, quantity=Decimal(100))
        L.add(pk.A1, EventType.TRANSFER_OUT, D(2026, 10, 2), USD, listing_id=self.aapl, quantity=Decimal(100))  # the last 100 units leave; only USD cash remains
        return L

    def test_row_1_a_full_hkd_withdrawal_dated_d_makes_the_unpublished_fixing_of_d_matter(self):
        L = self.withdrawal_ledger()
        self.assertEqual(self.choose(L).date, D(2026, 10, 1))  # was 2026-10-02 (end-of-D test only): the withdrawal translated at the 10-01 fixing, STALE
        self.assertEqual(self.choose(L, utc_dt(2026, 10, 2, 14, 30)).date, D(2026, 10, 2))  # after the 14:00 UTC publication the date is eligible again
        self.assertEqual(self.choose(self.withdrawal_ledger(D(2026, 10, 1))).date, D(2026, 10, 2))  # a withdrawal dated 10-01 is no event dated 10-02, and nothing foreign is held then: unchanged

    def test_row_2_an_in_kind_transfer_of_the_last_us_units_makes_the_close_of_d_matter(self):
        L = self.in_kind_ledger()
        self.assertEqual(self.choose(L).date, D(2026, 10, 1))  # the XNYS close of 10-02 is 20:00 UTC > t; was 2026-10-02 (nothing held afterwards)
        self.assertEqual(self.choose(L, utc_dt(2026, 10, 2, 20, 30)).date, D(2026, 10, 2))

    def test_q8_nothing_held_still_gives_the_utc_date_but_only_without_a_live_event_dated_d(self):
        quiet = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2026, 10, 2), USD, amount=Money(Decimal(1000), USD))  # a USD deposit dated D: no exchange, no foreign amount
        self.assertEqual(self.choose(quiet).date, D(2026, 10, 2))
        empty = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2026, 9, 1), USD, amount=Money(Decimal(1000), USD))
        self.assertEqual(self.choose(empty).date, D(2026, 10, 2))

    def test_a_reversed_event_is_not_live_and_does_not_count(self):
        L = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2026, 9, 30), USD, amount=Money(Decimal(1000), USD))
        L.add(pk.A1, EventType.DEPOSIT, D(2026, 10, 2), HKD, amount=Money(Decimal(7800), HKD))
        self.assertEqual(self.choose(L).date, D(2026, 10, 1))  # live: HKD is held, and the 10-02 fixing (14:00 UTC) is after t
        L.add(pk.A1, EventType.REVERSAL, D(2026, 10, 2), HKD, reverses_event_id=L.rows[1].event.event_id)
        self.assertEqual(self.choose(L).date, D(2026, 10, 2))  # reversed: the deposit never happened, nothing foreign is dated D, so D_c is the UTC date of t

    def test_a_same_day_sell_of_the_last_unit_names_its_exchange(self):
        sold = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2026, 9, 30), USD, amount=Money(Decimal(1000), USD)).add(
            pk.A1, EventType.BUY, D(2026, 9, 30), USD, listing_id=self.aapl, quantity=Decimal(1), amount=Money(Decimal(100), USD)).add(
            pk.A1, EventType.SELL, D(2026, 10, 2), USD, listing_id=self.aapl, quantity=Decimal(1), amount=Money(Decimal(100), USD))
        self.assertEqual(self.choose(sold).date, D(2026, 10, 1))  # nothing held afterwards, but the event names XNAS and its 10-02 close (20:00 UTC) is after t
        self.assertEqual(self.choose(sold, utc_dt(2026, 10, 2, 21, 0)).date, D(2026, 10, 2))

    def test_a_listing_currency_decides_foreign_and_an_unknown_currency_is_foreign(self):
        # an HKEX listing leaves on 10-02: its close (08:10 UTC) is <= t = 12:00 UTC, so ONLY the currency decides whether the ECB (14:00 UTC) matters
        L = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2026, 9, 30), USD, amount=Money(Decimal(1000), USD))
        L.add(pk.A1, EventType.TRANSFER_IN, D(2026, 9, 30), HKD, listing_id=self.h, quantity=Decimal(1))
        L.add(pk.A1, EventType.TRANSFER_OUT, D(2026, 10, 2), HKD, listing_id=self.h, quantity=Decimal(1))
        self.assertEqual(self.choose(L).date, D(2026, 10, 1))  # HKD listing: the ECB fixing of 10-02 is needed
        self.assertEqual(self.choose(L, currency_of=lambda _l: USD).date, D(2026, 10, 2))  # a USD listing would need no fixing (control: the exchange alone is eligible)
        self.assertEqual(self.choose(L, currency_of=lambda _l: None).date, D(2026, 10, 1))  # an unknown currency counts as foreign

    def test_d_c_t_does_not_depend_on_the_metric_only_on_t_l_and_m_t(self):
        L = self.withdrawal_ledger()
        for _ in range(2):
            self.assertEqual(self.choose(L).date, D(2026, 10, 1))


# ===== Ruling 1.7 (1.12) item 1: every scheduled close or publication falls on the same UTC date as its local session date ==============================

def utc_date_problems(zone, items):
    """`items`: `(local date, local time)`. The pairs whose UTC date is not the local date."""
    tz = zoneinfo.ZoneInfo(zone)
    out = []
    for day, time in items:
        instant = datetime.datetime.combine(day, time, tzinfo=tz).astimezone(UTC)
        if instant.date() != day:
            out.append((day.isoformat(), time.isoformat(), instant.isoformat()))
    return out


def document_items(doc):
    """The (date, time) pairs a calendar document schedules: a session's close (default and early closes), an ECB fixing and its publication."""
    dates = [datetime.date.fromisoformat(d) for d in doc["dates"]]
    if doc["kind"] == "EXCHANGE_SESSIONS":
        close = {datetime.date.fromisoformat(o["date"]): T.fromisoformat(o["time"]) for o in doc["close"].get("overrides", [])}
        default = T.fromisoformat(doc["close"]["default"])
        return [(d, close.get(d, default)) for d in dates]
    return [(d, T.fromisoformat(doc["fixing"][key])) for d in dates for key in ("time", "publication")]


def calendar_objects_items(calendar):
    if calendar.default_close is not None:
        early = dict(calendar.early_closes)
        return [(d, early.get(d, calendar.default_close)) for d in calendar.dates]
    return [(d, t) for d in calendar.dates for t in (calendar.fixing_time, calendar.publication_time)]


class CalendarCheckTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[2] / "data" / "marketdata"

    def documents(self):
        found = []
        for path in sorted(self.ROOT.rglob("*.json")):
            if path.name.endswith(".manifest.json") or path.name in ("SOURCES.json", "SOURCES.example.json"):
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(doc, dict) and doc.get("schema") == "finweb.marketdata.calendar/1":
                found.append((path, doc))
        return found

    def test_every_registered_and_drafted_calendar_file_has_its_close_and_publication_on_the_local_utc_date(self):
        documents = self.documents()
        self.assertGreaterEqual(len(documents), 4)  # the four drafts at least (NYSE, ECB, HKEX, CN-A) and the registered NYSE and ECB files
        names = {p.name for p, _d in documents}
        self.assertTrue({"NYSE_SESSIONS.json", "ECB.json", "HKEX_SESSIONS.json", "CN_A_SESSIONS.json"} <= names, names)
        for path, doc in documents:
            self.assertEqual(utc_date_problems(doc["timezone"], document_items(doc)), [], str(path))

    def test_every_calendar_object_the_tests_and_tools_build_has_the_property(self):
        days = weekdays(D(2025, 1, 1), D(2026, 12, 31))
        built = [pk.World([]).calendars, ca.CALENDARS,
                 CalendarSet([k.exchange_calendar("HKEX_SESSIONS", ("XHKG",), days, tz="Asia/Hong_Kong", default_close=T(16, 10)),
                              k.exchange_calendar("CN_A_SESSIONS", ("XSHG", "XSHE"), days, tz="Asia/Shanghai", default_close=T(15, 0)),
                              k.exchange_calendar("NYSE_SESSIONS", ("XNYS", "XNAS"), days, tz="America/New_York"), k.ecb_calendar(days)])]
        count = 0
        for calendars in built:
            for calendar in calendars.calendars():
                count += 1
                self.assertEqual(utc_date_problems(calendar.timezone, calendar_objects_items(calendar)), [], calendar.calendar_id)
        self.assertGreaterEqual(count, 8)
        # and the real-slice test double's calendar documents
        for zone, doc in ((z, json.loads(rfx.calendar_json(cid, kind, [mic], z, days)))
                          for cid, kind, mic, z in (("NYSE_SESSIONS", "EXCHANGE_SESSIONS", "XNYS", "America/New_York"), ("ECB", "ECB_FIXINGS", "ECB", "Europe/Berlin"))):
            self.assertEqual(utc_date_problems(zone, document_items(doc)), [], doc["calendar_id"])

    def test_the_check_can_fail_a_close_before_midnight_utc_of_the_previous_day_is_found(self):
        # a Tokyo 07:00 JST open is 22:00 UTC of the PREVIOUS day: the same-UTC-date argument would not cover such a calendar
        self.assertEqual(utc_date_problems("Asia/Tokyo", [(D(2026, 10, 1), T(7, 0))]), [("2026-10-01", "07:00:00", "2026-09-30T22:00:00+00:00")])
        self.assertEqual(utc_date_problems("Pacific/Auckland", [(D(2026, 7, 1), T(9, 0))])[0][0], "2026-07-01")  # 09:00 NZST is 21:00 UTC the day before
        self.assertEqual(utc_date_problems("America/New_York", [(D(2026, 10, 1), T(16, 0))]), [])  # 20:00 UTC, the same date
        self.assertEqual(len(utc_date_problems("America/Los_Angeles", [(D(2026, 10, 1), T(17, 30))])), 1)  # 00:30 UTC the NEXT day: also not covered


# ===== market11.UNBUILT: the Current-mode item is closed =============================================================================================

class UnbuiltTests(unittest.TestCase):
    def test_the_current_mode_item_is_removed_and_the_others_stay(self):
        self.assertFalse([i for i in UNBUILT if "Current mode" in i])
        self.assertEqual(len(UNBUILT), 4)
        items = market11_conventions(CalendarSet()).visible_open_items()
        self.assertFalse([i for i in items if "Current mode" in i])


# ===== CP4-3 / Ruling 2.2 (1.12) through the engine ==================================================================================================

class RecordedFactsThroughTheEngineTests(unittest.TestCase):
    def test_native_cash_is_a_fact_padded_to_the_minor_unit_and_the_reporting_view_is_derived(self):
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 4, 1), USD, amount=Money(Decimal("2248.0000"), USD))  # the recorded scale is not used
        L.add(pk.A2, EventType.DEPOSIT, D(2025, 4, 1), USD, amount=Money(Decimal("0.125"), USD))  # a recorded 0.125 USD stays 0.125 as a fact, 0.13 as a derived value
        w = pk.world_w()
        res = pk.compute(L.rows, L.version, D(2025, 4, 2), USD, w.store, w.ident, w.market, mp.PERF)
        cash = {(dict(m.subject)["account"], m.view): m for m in res.metrics if m.metric_id == "cash_value"}
        a1_, a2_ = str(pk.A1), str(pk.A2)
        self.assertEqual((str(cash[(a1_, "NATIVE")].result.value), str(cash[(a1_, "REPORTING")].result.value)), ("2248.00", "2248.00"))
        self.assertEqual((str(cash[(a2_, "NATIVE")].result.value), str(cash[(a2_, "REPORTING")].result.value)), ("0.125", "0.13"))
        self.assertEqual(cash[(a2_, "NATIVE")].exact, F(1, 8))  # the exact value is unchanged
        self.assertEqual(cash[(a2_, "NATIVE")].details, ())  # USD is in the table: no detail

    def test_a_native_receivable_is_a_fact_too(self):
        w = pk.world_w()
        L = pk.Ledger()
        L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=Money(Decimal(6000), USD))
        L.add(pk.A1, EventType.DIVIDEND, D(2025, 4, 4), HKD, listing_id=w.h, amount=Money(Decimal("780.5"), HKD), ex_date=D(2025, 3, 31))
        res = pk.compute(L.rows, L.version, D(2025, 4, 2), USD, w.store, w.ident, w.market, mp.PERF)
        native = mp.metric(res, "receivable_value", "NATIVE")
        self.assertEqual(str(native.result.value), "780.50")  # was "780.5"
        self.assertEqual(native.exact, F(1561, 2))


# ===== CP4-5: m1 and m3, the breakdown sites ==========================================================================================================

class BreakdownExponentTests(unittest.TestCase):
    def test_m3_the_attribution_breakdown_parts_carry_the_minor_unit_in_every_grouping(self):
        res = ta.attribute(ta.post_split_ledger(), D(2025, 2, 5), base=D(2025, 2, 3))  # price line 500 on a split-neutral position
        breakdowns = [m for m in res.metrics if m.metric_id == "attribution_breakdown"]
        self.assertTrue(breakdowns)
        checked = 0
        for m in breakdowns:
            for name, shown, _exact in m.breakdown:
                self.assertEqual(shown.as_tuple().exponent, -2, (m.subject, name, str(shown)))
                checked += 1
            self.assertRegex(dict(m.lineage)["displayed_total"], r"^-?\d+\.\d{2}$")  # the displayed total of the line, as lineage text, also has two places
        self.assertGreaterEqual(checked, 3)
        self.assertEqual(str(next(shown for m in breakdowns if dict(m.subject) == {"group_by": "listing", "line": "attr.price"} for _n, shown, _e in m.breakdown)), "500.00")

    def test_m1_the_since_acquisition_lines_carry_the_minor_unit(self):
        L = mp.base_ledger()
        port = mp.market(evidence=None, prices={D(2025, 2, 3): "37.50", D(2025, 2, 4): "40.00"})
        spec = WindowSpec(WindowRule.SINCE_INCEPTION)
        res = engine.compute_gains(L.rows, L.version, D(2025, 2, 4), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, suppressions=(), window=spec)
        lines = [m for m in res.metrics if m.metric_id == "since_acquisition"]
        self.assertTrue(lines)
        checked = [(name, shown) for m in lines for name, shown, _e in m.breakdown]
        self.assertTrue(checked)
        for name, shown in checked:
            self.assertEqual(shown.as_tuple().exponent, -2, (name, str(shown)))


# ===== Ruling 1.7 (1.12) item 4: source_registry_digest ==============================================================================================

def record(**kw):
    base = dict(source_id="test.src", name="Test source", upstream_provider="Upstream Inc", independence_group="upstream-a", terms_url="https://example.invalid/terms",
                terms_check=TermsCheck("owner", D(2026, 10, 1), True, "checked"), synthetic=False)
    base.update(kw)
    return SourceRecord(**base)


class SourceRegistryDigestTests(unittest.TestCase):
    def test_the_digest_covers_every_field_and_is_independent_of_the_order(self):
        a, b = record(), record(source_id="other.src", name="Other")
        base = source_registry_digest([a, b])
        self.assertEqual(source_registry_digest([b, a]), base)  # sorted by source_id
        self.assertEqual(len(base), 64)
        for change in (dict(independence_group="upstream-b"), dict(synthetic=True), dict(upstream_provider="Else"), dict(name="Renamed"), dict(terms_url=None),
                       dict(terms_check=None), dict(terms_check=TermsCheck("owner", D(2026, 10, 1), False, "checked")), dict(terms_check=TermsCheck("owner", D(2026, 10, 2), True, "checked")),
                       dict(terms_check=TermsCheck("other", D(2026, 10, 1), True, "checked")), dict(terms_check=TermsCheck("owner", D(2026, 10, 1), True, "notes changed"))):
            self.assertNotEqual(source_registry_digest([record(**change), b]), base, change)
        self.assertNotEqual(source_registry_digest([a]), base)  # the set of sources is part of it
        self.assertEqual(source_registry_digest([record()]), source_registry_digest([record()]))  # deterministic

    def world(self, overrides=(), drop=()):
        """The probe market `mp.market("real")` with the records its readings imply (`k.records_for`), some replaced by `overrides` (by source id) or dropped."""
        base = mp.market("real", real_quotes=True)
        readings = list(base._readings_in)
        records = {r.source_id: r for r in k.records_for(readings)}
        records.update({r.source_id: r for r in overrides})
        for source_id in drop:
            records.pop(source_id)
        with gate_kit.admitted_real_world(readings, mp.MIC):  # 1.16 Ruling 4.7 item 6: see gate_kit
            return InMemoryMarketData(base._release, readings, exchange_of=lambda _l: mp.MIC, source_records=list(records.values()))

    def compute(self, port, ledger=None):
        L = ledger or mp.base_ledger()
        return pk.compute(L.rows, L.version, D(2025, 1, 31), USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF)

    def test_every_manifest_carries_the_digest_of_the_ports_records_never_empty(self):
        port = self.world([record(source_id="test.feed", independence_group="feed-up")])
        res = self.compute(port)
        self.assertEqual(res.manifest.source_registry_digest, source_registry_digest(port.source_registry_records()))
        self.assertRegex(res.manifest.source_registry_digest, r"^[0-9a-f]{64}$")
        other = self.compute(self.world([record(source_id="test.feed", independence_group="feed-other")]))
        self.assertNotEqual(res.manifest.manifest_id, other.manifest.manifest_id)  # it is part of the manifest id

    def test_a_version_that_serves_no_file_observation_has_the_empty_list_digest_not_empty_text(self):
        empty = InMemoryMarketData(MarketDataRelease(name="none", files=(), source_precedence=()), [], exchange_of=lambda _l: mp.MIC)
        L = pk.Ledger().add(pk.A1, EventType.DEPOSIT, D(2025, 1, 2), USD, amount=Money(Decimal(100), USD))
        res = self.compute(empty, L)
        self.assertEqual(res.manifest.source_registry_digest, source_registry_digest(()))
        self.assertNotEqual(res.manifest.source_registry_digest, "")
        self.assertEqual(engine.registry_digest_of(None), source_registry_digest(()))  # no port at all: the same

    def test_a_source_with_observations_in_m_and_no_record_fails_closed_before_any_value(self):
        L = mp.base_ledger()
        none_has = mp.market("real", real_quotes=True)
        with gate_kit.admitted_real_world(none_has._readings_in, mp.MIC):  # 1.16 Ruling 4.7 item 6: see gate_kit
            no_records = InMemoryMarketData(none_has._release, list(none_has._readings_in), exchange_of=lambda _l: mp.MIC)
        for port in (self.world(drop=["test.feed"]),  # one source of the served observations has no record
                     no_records):  # none has
            with self.assertRaises(SourceRegistryNotPinnedError):
                self.compute(port, L)

        class NoRegistry:  # a port that cannot report its records at all
            def __init__(self, inner):
                self._inner = inner

            def __getattr__(self, name):
                if name == "source_registry_records":
                    raise AttributeError(name)
                return getattr(self._inner, name)

        with self.assertRaises(SourceRegistryNotPinnedError):
            self.compute(NoRegistry(self.world()), L)

    def test_a_changed_independence_group_or_synthetic_flag_changes_the_digest_and_reproduce_reports_the_mismatch(self):
        L = mp.base_ledger()
        recs = [record(source_id="test.feed"), record(source_id="test.filing", independence_group="filing-up")]
        res = self.compute(self.world(recs))
        ok = pk.reproduce(res.manifest, res.result_digest, L.rows, self.world(recs), mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF)
        self.assertEqual(ok.status, ReproductionStatus.REPRODUCED)
        with self.assertRaises(SourceRegistryNotPinnedError):  # CP4-10: a synthetic flag that disagrees with the readings' usage scope is refused, not pinned
            self.compute(self.world([record(source_id="test.feed", synthetic=True), recs[1]]))
        for changed in ([record(source_id="test.feed", independence_group="other-up"), recs[1]],):
            report = pk.reproduce(res.manifest, res.result_digest, L.rows, self.world(changed), mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF)
            self.assertEqual(report.status, ReproductionStatus.SOURCE_REGISTRY_MISMATCH, changed)
            self.assertNotEqual(report.rerun.manifest.source_registry_digest, res.manifest.source_registry_digest)

    def test_reproduce_with_an_unpinned_registry_is_never_reproduced_and_empty_against_empty_is_not_a_match(self):
        L = mp.base_ledger()
        port = self.world()
        res = self.compute(port)
        for digest in ("", None):
            unpinned = dataclasses.replace(res.manifest, source_registry_digest=digest if digest is not None else "")
            report = pk.reproduce(unpinned, res.result_digest, L.rows, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF)
            self.assertEqual(report.status, ReproductionStatus.SOURCE_REGISTRY_MISMATCH)
            self.assertIn("registry not pinned", report.detail)
            self.assertNotIn(report.status, (ReproductionStatus.REPRODUCED, ReproductionStatus.RESULT_NOT_COMPARED))
        # a rerun side that is "" fails the same way (the engine never produces one; a port stub that forced it would not pass either)
        with unittest.mock.patch.object(engine, "registry_digest_of", return_value=""):
            report = pk.reproduce(res.manifest, res.result_digest, L.rows, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF)
        self.assertEqual(report.status, ReproductionStatus.SOURCE_REGISTRY_MISMATCH)
        self.assertIn("registry not pinned", report.detail)

    def test_the_build_path_hands_the_registry_records_of_the_sources_with_a_file_in_m_to_the_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rfx.build_store(root, calendars=True)
            subject, report = real_slice.build_real_subject(root)
            self.assertIsNotNone(subject, report)
            records = subject.store.source_registry_records()
            self.assertEqual([r.source_id for r in records], sorted({"alphavantage.us", "frankfurter.ecb", "calendar.manual"}))  # exactly the sources that have a file in M, sorted
            computed = pack.run_all(subject)
            self.assertEqual({c.result.manifest.source_registry_digest for c in computed.results}, {source_registry_digest(records)})  # every manifest of the pack carries it
            # change one source's independence group in SOURCES.json: the store's records and the digest change
            sources = json.loads((root / "SOURCES.json").read_text(encoding="utf-8"))
            for item in sources["sources"]:
                if item["source_id"] == "alphavantage.us":
                    item["independence_group"] = "changed-group"
            (root / "SOURCES.json").write_text(json.dumps(sources), encoding="utf-8")
            subject2, _ = real_slice.build_real_subject(root)
            self.assertNotEqual(source_registry_digest(subject2.store.source_registry_records()), source_registry_digest(records))


# ===== Current mode (M_t): the digest is the registry of the sources with a file in M_t ========================================================================

class DerivedReleaseRegistryTests(unittest.TestCase):
    def test_a_source_whose_files_are_all_retrieved_after_t_is_not_in_the_registry_digest_at_t(self):
        # the engine reads `view.port.source_registry_records()`: M_t's, so a source that only has later files is absent at t
        early = record(source_id="early.src")
        late = record(source_id="late.src", independence_group="late-up")
        port_t = InMemoryMarketData(MarketDataRelease(name="t", files=(), source_precedence=()), [], source_records=[early])
        port_later = InMemoryMarketData(MarketDataRelease(name="t2", files=(), source_precedence=()), [], source_records=[early, late])
        self.assertNotEqual(engine.registry_digest_of(port_t), engine.registry_digest_of(port_later))
        self.assertEqual(engine.registry_digest_of(port_t), source_registry_digest([early]))
        self.assertEqual(engine.registry_digest_of(None), source_registry_digest(()))


if __name__ == "__main__":
    unittest.main()
