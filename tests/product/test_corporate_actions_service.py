"""F8-B (PD-0030 section 2; market-data/1.4 section 6): the split-confirmation service. Unit tests over an in-memory
ledger that behaves like the real append path where the service relies on it (idempotent on (account,
source_reference), one live SPLIT per position per day, REVERSAL); the same flows against PostgreSQL, as `finweb_app`,
are in `test_postgres_corporate_actions_service.py`.

Every expected value is derived by hand from the inputs shown. The worked example is the Quant's Example 6-A
(`methodology/CP2_MARKET_DATA_CONVENTIONS.md`): an account holds 50 units, a corroborated SPLIT (4, 1) has ex-date
2025-02-03, raw closes are 150.00 (2025-01-31) and 38.00 (2025-02-03).
"""

import ast
import contextlib
import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_kit  # noqa: E402
import marketdata_cp2c1_kit as k  # noqa: E402

c = k.c
kit = k.kit

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent, SplitRatio  # noqa: E402
from domain.replay import SequencedEvent, reconstruct  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.manifest import MarketDataRelease  # noqa: E402
from marketdata.store import InMemoryMarketData  # noqa: E402
from persistence.ledger_store import AppendResult, IdempotencyConflictError, SameDaySplitError  # noqa: E402
from product_contract.vocabulary import ReasonCode  # noqa: E402

D = datetime.date
SRC = Path(__file__).resolve().parents[2] / "src"
PORTFOLIO = uuid.UUID(int=900)
A1, A2 = uuid.UUID(int=1), uuid.UUID(int=2)
LISTING = uuid.UUID(int=77)
OTHER_LISTING = uuid.UUID(int=78)
EX = D(2025, 2, 3)
# C2-2 (CP2 review of 39733e9): F8-B never appends from SYNTHETIC evidence. The unit tests of an append therefore need
# evidence that is NOT synthetic: these are test doubles whose files carry the REAL usage scope (`REAL`), so the service
# sees real evidence. `SYN` is the synthetic usage scope, used by the tests that prove it is refused.
FEED, FILING = "test.feed", "test.filing"
FEED_SHA, FILING_SHA = "c" * 64, "d" * 64
POLICY = f8b.ConfirmationPolicy(frozenset({FEED}), frozenset({FILING}))
USD = CurrencyCode("USD")
REAL, SYN = c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, c.UsageScope.SYNTHETIC_TEST
MIC = "XTST"


def weekdays(first, last):
    out, day = [], first
    while day <= last:
        if day.weekday() < 5:
            out.append(day)
        day += datetime.timedelta(days=1)
    return out


# A synthetic calendar for the listing's MIC: every weekday of 2024-06-03..2026-06-30, no holidays (invented). Ruling 6.4a
# counts the +-20 sessions of the linking window in it. By hand, for EX = Mon 2025-02-03: the 20th session before is Mon
# 2025-01-06 (Jan 31, 30, 29, 28, 27 = 5; Jan 24..20 = 10; Jan 17..13 = 15; Jan 10, 9, 8, 7, 6 = 20) and the 20th after is
# Mon 2025-03-03 (Feb 4..7 = 4; Feb 10..14 = 9; Feb 17..21 = 14; Feb 24..28 = 19; Mar 3 = 20): W = [2025-01-06, 2025-03-03].
CALENDARS = CalendarSet([k.exchange_calendar("TEST_SESSIONS", (MIC,), weekdays(D(2024, 6, 3), D(2026, 6, 30)))])
exchange_of = lambda listing_id: MIC  # noqa: E731


class FakeLedger:
    """The pieces of the real append path the service depends on, and nothing else."""

    def __init__(self):
        self.rows: List[SequencedEvent] = []
        self.seq = 0
        self.appended: List[LedgerEvent] = []

    def add(self, event: LedgerEvent) -> SequencedEvent:
        self.seq += 1
        row = SequencedEvent(self.seq, event)
        self.rows.append(row)
        return row

    def load(self, portfolio_id):
        return self.seq, tuple(self.rows)

    @contextlib.contextmanager
    def atomic(self, portfolio_id):
        """The in-memory twin of `PostgresLedgerAccess.atomic`: an exception removes every event THIS run appended (a concurrent writer's events stay, as they would after a rollback) and the
        committed version falls back to the highest remaining `ledger_seq`."""
        mark = len(self.appended)
        try:
            yield
        except BaseException:
            mine = {e.event_id for e in self.appended[mark:]}
            self.rows = [r for r in self.rows if r.event.event_id not in mine]
            del self.appended[mark:]
            self.seq = max((r.ledger_seq for r in self.rows), default=0)
            raise

    def append(self, event: LedgerEvent) -> AppendResult:
        live_reversed = {r.event.reverses_event_id for r in self.rows if r.event.event_type is EventType.REVERSAL}
        if event.source_reference is not None:
            for r in self.rows:
                if r.event.account_id == event.account_id and r.event.source_reference == event.source_reference:
                    if r.event.has_same_content(event):
                        return AppendResult(r.event, r.ledger_seq, False)
                    raise IdempotencyConflictError(r.event.event_id, event.account_id, event.source_reference)
        if event.event_type is EventType.SPLIT:
            for r in self.rows:
                e = r.event
                if (e.event_type is EventType.SPLIT and e.account_id == event.account_id and e.listing_id == event.listing_id
                        and e.event_date == event.event_date and e.event_id not in live_reversed):
                    raise SameDaySplitError("ledger_event_split_once_per_day", "a live split already exists")
        row = self.add(event)
        self.appended.append(event)
        return AppendResult(event, row.ledger_seq, True)


_ids = iter(range(10_000, 10_000_000))


def eid() -> uuid.UUID:
    return uuid.UUID(int=next(_ids))


def ledger_with_holdings(accounts=(A1,), quantity="50", bought=D(2024, 12, 20)) -> FakeLedger:
    """Each account deposits 10,000 USD and buys `quantity` units of LISTING for 7,500 USD on `bought` (hand-made)."""
    ledger = FakeLedger()
    for account in accounts:
        ledger.add(LedgerEvent(eid(), account, EventType.DEPOSIT, bought, USD, amount=Money(Decimal(10000), USD)))
        ledger.add(LedgerEvent(eid(), account, EventType.BUY, bought, USD, listing_id=LISTING,
                               quantity=Decimal(quantity), amount=Money(Decimal(7500), USD)))
    return ledger


def split_reading(source, sha, ratio, day=EX, listing=LISTING, usage=REAL):
    obs = c.CorporateActionObservation(
        listing, c.CorporateActionType.SPLIT, day, c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY),
        k.lineage(source, sha, usage=usage), split_ratio=SplitRatio(Decimal(ratio[0]), Decimal(ratio[1])))
    return c.SourceReading(source, source, sha, obs)


def port_with(readings, name="release-a") -> InMemoryMarketData:
    release = MarketDataRelease(name=name, files=tuple(sorted({r.file_sha256 for r in readings})), source_precedence=())
    with gate_kit.admitted_real_world(readings, MIC):  # 1.16 Ruling 4.7 item 6: REAL records of invented sources pass the per-reading gate only in this world
        return InMemoryMarketData(release, readings, exchange_of=lambda _l: MIC, source_records=k.records_for(readings))


def corroborated(ratio=(4, 1), name="release-a", filing_ratio=None) -> InMemoryMarketData:
    return port_with([split_reading(FEED, FEED_SHA, ratio), split_reading(FILING, FILING_SHA, filing_ratio or ratio)], name)


def run(ledger, port, accounts_listing=(LISTING,), start=D(2025, 1, 1), end=D(2025, 12, 31)):
    return f8b.confirm_splits(ledger, port, PORTFOLIO, accounts_listing, start, end, POLICY, {LISTING: USD, OTHER_LISTING: USD},
                              calendars=CALENDARS, exchange_of=exchange_of)


class AppendTests(unittest.TestCase):
    def test_a_corroborated_split_is_appended_with_provenance_and_changes_the_replayed_quantity(self):
        ledger = ledger_with_holdings()
        port = corroborated()
        report = run(ledger, port)
        (outcome,) = report.outcomes
        self.assertEqual((outcome.decision, outcome.account_id, outcome.listing_id, outcome.ex_date),
                         (f8b.SplitDecision.APPENDED, A1, LISTING, EX))
        (event,) = ledger.appended
        self.assertEqual((event.event_type, event.event_date, event.listing_id, event.currency),
                         (EventType.SPLIT, EX, LISTING, USD))
        self.assertEqual((event.split_ratio.new_units, event.split_ratio.old_units), (Decimal(4), Decimal(1)))
        # provenance: evidence file hashes, the release and its convention set, the ex-date and the ratio
        prov = f8b.parse_source_reference(event.source_reference)
        self.assertEqual((prov.convention_set_id, prov.release_id, prov.feed_files, prov.filing_files, prov.ex_date, prov.ratio),
                         ("market-data/1.16", port.release_id(), (FEED_SHA,), (FILING_SHA,), EX, ("4", "1")))
        self.assertEqual(event.event_id, f8b.event_id_for(A1, event.source_reference))  # deterministic id
        # Example 6-A: 50 units before the ex-date, 50 x 4 = 200 from it; 200 x 38.00 = 7,600.00
        before = reconstruct(ledger.load(PORTFOLIO)[1], D(2025, 2, 2), ledger.seq).account(A1).positions[0].quantity.value
        after = reconstruct(ledger.load(PORTFOLIO)[1], EX, ledger.seq).account(A1).positions[0].quantity.value
        self.assertEqual((before, after), (Decimal(50), Decimal(200)))
        self.assertEqual(after * Decimal("38.00"), Decimal("7600.00"))
        self.assertEqual((report.ledger_version_before, report.ledger_version_after), (2, 3))

    def test_the_provenance_string_is_ascii_bounded_marks_the_system_and_is_not_on_a_user_event(self):
        ref = f8b.build_source_reference("market-data/1.3", "a" * 64, [FEED_SHA], [FILING_SHA], EX, SplitRatio(Decimal(4), Decimal(1)))
        # by hand: finweb.f8b/1 (12) ;md= (4) market-data/1.3 (15) ;rel= (5) 64 ;feed= (6) 64 ;filing= (8) 64 ;ex= (4) 10
        # ;ratio= (7) 4/1 (3) = 12 + 4 + 15 + 5 + 64 + 6 + 64 + 8 + 64 + 4 + 10 + 7 + 3
        self.assertEqual(len(ref), 266)
        self.assertTrue(ref.isascii() and " " not in ref and ref.strip() == ref)
        self.assertLess(len(ref), f8b.MAX_SOURCE_REFERENCE_CHARS)
        self.assertLess(f8b.MAX_SOURCE_REFERENCE_CHARS, 2704)  # the btree entry limit of the ledger's unique index, in bytes
        self.assertTrue(ref.startswith("finweb.f8b/1;"))
        self.assertIsNone(f8b.parse_source_reference("broker-statement-2025-02-03"))  # a user-entered reference
        self.assertIsNone(f8b.parse_source_reference(None))
        self.assertEqual(f8b.parse_source_reference(ref).ratio, ("4", "1"))

    def test_a_reference_that_would_break_a_ledger_constraint_is_refused_not_altered(self):
        ratio = SplitRatio(Decimal(4), Decimal(1))
        many = ["%064x" % i for i in range(20)]  # 20 feed files x 65 characters: far over the bound
        with self.assertRaises(f8b.SourceReferenceError):
            f8b.build_source_reference("market-data/1.3", "a" * 64, many, [FILING_SHA], EX, ratio)
        for bad in ("", "   ", "finweb.f8b/1;a b", "café", "x\x00y", "tab\tx"):
            with self.assertRaises(f8b.SourceReferenceError, msg=repr(bad)):
                f8b.check_source_reference(bad)
        with self.assertRaises(f8b.SourceReferenceError):
            f8b.build_source_reference("market-data/1.3", "not-a-hash", [FEED_SHA], [FILING_SHA], EX, ratio)
        with self.assertRaises(f8b.SourceReferenceError):
            f8b.build_source_reference("market-data/1.3", "a" * 64, [], [FILING_SHA], EX, ratio)
        # a convention-set id with a space cannot be smuggled in
        with self.assertRaises(f8b.SourceReferenceError):
            f8b.build_source_reference("market data", "a" * 64, [FEED_SHA], [FILING_SHA], EX, ratio)

    def test_an_identical_resubmission_is_a_no_op_and_so_is_new_evidence_for_the_same_split(self):
        ledger = ledger_with_holdings()
        run(ledger, corroborated())
        version = ledger.seq
        again = run(ledger, corroborated())  # the very same evidence and release
        self.assertEqual([o.decision for o in again.outcomes], [f8b.SplitDecision.ALREADY_RECORDED])
        later = run(ledger, corroborated(name="release-b"))  # a NEW release: another reference, the same split
        self.assertEqual([o.decision for o in later.outcomes], [f8b.SplitDecision.ALREADY_RECORDED])
        self.assertEqual((ledger.seq, len(ledger.appended)), (version, 1))  # nothing was written twice, no second split

    def test_the_ratio_is_compared_as_an_exact_rational_and_the_filings_form_is_recorded(self):
        ledger = ledger_with_holdings(quantity="10")
        report = run(ledger, corroborated(ratio=(15, 10), filing_ratio=(3, 2)))  # 15/10 = 3/2
        self.assertEqual(report.findings[0].status, f8b.Corroboration.CORROBORATED)
        (event,) = ledger.appended
        self.assertEqual((event.split_ratio.new_units, event.split_ratio.old_units), (Decimal(3), Decimal(2)))  # the filing's form
        after = reconstruct(ledger.load(PORTFOLIO)[1], EX, ledger.seq).account(A1).positions[0].quantity.value
        self.assertEqual(after, Decimal(15))  # 10 x 3/2

    def test_only_accounts_holding_units_at_the_start_of_the_ex_date_get_the_split(self):
        ledger = ledger_with_holdings(accounts=(A1,))
        # A2 buys ON the ex-date: its position at the start of the ex-date is zero
        ledger.add(LedgerEvent(eid(), A2, EventType.DEPOSIT, D(2025, 1, 2), USD, amount=Money(Decimal(10000), USD)))
        ledger.add(LedgerEvent(eid(), A2, EventType.BUY, EX, USD, listing_id=LISTING, quantity=Decimal(5),
                               amount=Money(Decimal(190), USD)))
        report = run(ledger, corroborated())
        decisions = {o.account_id: o.decision for o in report.outcomes}
        self.assertEqual(decisions, {A1: f8b.SplitDecision.APPENDED, A2: f8b.SplitDecision.NOT_HELD})
        self.assertEqual(len(ledger.appended), 1)

    def test_an_existing_equal_split_a_users_own_is_left_alone(self):
        ledger = ledger_with_holdings()
        ledger.add(LedgerEvent(eid(), A1, EventType.SPLIT, EX, USD, listing_id=LISTING,
                               split_ratio=SplitRatio(Decimal(4), Decimal(1)), source_reference="broker-statement"))
        report = run(ledger, corroborated())
        (o,) = report.outcomes
        self.assertEqual((o.decision, o.source_reference), (f8b.SplitDecision.ALREADY_RECORDED, "broker-statement"))
        self.assertEqual(ledger.appended, [])


class ConflictTests(unittest.TestCase):
    def test_a_split_recorded_with_another_ratio_on_the_ex_date_is_not_appended_over_and_valuation_is_suppressed(self):
        ledger = ledger_with_holdings()
        ledger.add(LedgerEvent(eid(), A1, EventType.SPLIT, EX, USD, listing_id=LISTING,
                               split_ratio=SplitRatio(Decimal(2), Decimal(1)), source_reference="typo"))
        report = run(ledger, corroborated())
        (o,) = report.outcomes
        self.assertEqual((o.decision, o.ledger_date), (f8b.SplitDecision.CONFLICT_RATIO, EX))
        self.assertEqual(ledger.appended, [])
        (s,) = report.suppressions
        # Ruling 6.4 item 2: a different ratio: INSUFFICIENT_DATA + SOURCE_CONFLICT from min(X, Y) = the ex-date, open-ended
        self.assertEqual((s.first_date, s.end_exclusive, s.reason_code), (EX, None, ReasonCode.SOURCE_CONFLICT))
        self.assertIsNone(report.suppressed_on(A1, LISTING, D(2025, 2, 2)))
        self.assertIsNotNone(report.suppressed_on(A1, LISTING, EX))
        self.assertIsNotNone(report.suppressed_on(A1, LISTING, D(2026, 1, 1)))

    def test_the_example_6a_record_date_split_is_suppressed_for_the_dates_where_units_and_price_disagree(self):
        # the ledger holds SPLIT (4, 1) dated 2025-01-29 (a record date); the corroborated ex-date is 2025-02-03.
        # Same ratio, other date Y: INSUFFICIENT_DATA for D in [min(X, Y), max(X, Y)) = 29, 30, 31 January and 1, 2 February
        # (the ex-date itself is right again). Nothing is appended: the ledger would otherwise apply the ratio twice
        # (50 x 4 x 4 = 800, the Quant's failure row).
        ledger = ledger_with_holdings()
        user = LedgerEvent(eid(), A1, EventType.SPLIT, D(2025, 1, 29), USD, listing_id=LISTING,
                           split_ratio=SplitRatio(Decimal(4), Decimal(1)), source_reference="broker-record-date")
        ledger.add(user)
        report = run(ledger, corroborated())
        (o,) = report.outcomes
        self.assertEqual((o.decision, o.ledger_date, o.event_id), (f8b.SplitDecision.CONFLICT_DATE, D(2025, 1, 29), user.event_id))
        self.assertEqual(ledger.appended, [])
        for day, suppressed in ((D(2025, 1, 28), False), (D(2025, 1, 29), True), (D(2025, 1, 30), True), (D(2025, 1, 31), True),
                                (D(2025, 2, 2), True), (EX, False), (D(2025, 2, 4), False)):
            self.assertEqual(report.suppressed_on(A1, LISTING, day) is not None, suppressed, day)
        self.assertEqual(reconstruct(ledger.load(PORTFOLIO)[1], EX, ledger.seq).account(A1).positions[0].quantity.value,
                         Decimal(200))  # the replayed quantity is still reported as the ledger fact it is
        # (200 x 150.00 = 30,000 on 2025-01-31 would be wrong: units already split, price not yet)

    def test_an_unrelated_older_split_with_another_ratio_does_not_block_a_new_corroborated_one(self):
        ledger = ledger_with_holdings()
        ledger.add(LedgerEvent(eid(), A1, EventType.SPLIT, D(2024, 12, 25), USD, listing_id=LISTING,
                               split_ratio=SplitRatio(Decimal(2), Decimal(1)), source_reference="older"))
        report = run(ledger, corroborated())
        self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.APPENDED])

    def test_a_split_that_a_corroborated_record_explains_is_not_mistaken_for_an_off_date_entry(self):
        # two real 4-for-1 splits on two ex-dates, the first already in the ledger: the second must still be appended.
        # C2-15 (CP2 final round): the two linking windows must NOT overlap, or both fail closed. The first ex-date moved from
        # 2024-12-27 (26 sessions before: windows overlap) to Mon 2024-11-04; its window ends Mon 2024-12-02 (hand: Nov 5..8 = 4,
        # 11..15 = 9, 18..22 = 14, 25..29 = 19, Dec 2 = 20), before the second opens on 2025-01-06
        first = D(2024, 11, 4)
        ledger = ledger_with_holdings(bought=D(2024, 10, 1))
        ledger.add(LedgerEvent(eid(), A1, EventType.SPLIT, first, USD, listing_id=LISTING,
                               split_ratio=SplitRatio(Decimal(4), Decimal(1)), source_reference="first"))
        port = port_with([split_reading(FEED, FEED_SHA, (4, 1), day=first), split_reading(FILING, FILING_SHA, (4, 1), day=first),
                          split_reading(FEED, FEED_SHA, (4, 1)), split_reading(FILING, FILING_SHA, (4, 1))])
        report = run(ledger, port, start=D(2024, 1, 1))
        decisions = {(o.ex_date): o.decision for o in report.outcomes}
        self.assertEqual(decisions, {first: f8b.SplitDecision.ALREADY_RECORDED, EX: f8b.SplitDecision.APPENDED})

    def test_a_split_the_user_reversed_is_never_appended_again_not_even_by_a_later_release(self):
        ledger = ledger_with_holdings()
        run(ledger, corroborated())
        system = ledger.appended[0]
        ledger.add(LedgerEvent(eid(), A1, EventType.REVERSAL, D(2025, 2, 10), USD, reverses_event_id=system.event_id))
        version = ledger.seq
        for name in ("release-a", "release-b"):
            report = run(ledger, corroborated(name=name))
            (o,) = report.outcomes
            self.assertEqual(o.decision, f8b.SplitDecision.REVERSED_BY_USER, name)
            self.assertEqual(report.suppressions[0].first_date, EX)  # 'corporate action not recorded' until the user acts
        self.assertEqual((ledger.seq, len(ledger.appended)), (version, 1))
        # once the user records the split themselves (here: the correct one), the position is consistent again
        ledger.add(LedgerEvent(eid(), A1, EventType.SPLIT, EX, USD, listing_id=LISTING,
                               split_ratio=SplitRatio(Decimal(4), Decimal(1)), source_reference="user-correction"))
        self.assertEqual([o.decision for o in run(ledger, corroborated(name="release-c")).outcomes],
                         [f8b.SplitDecision.ALREADY_RECORDED])

    def test_a_flagged_position_is_not_appended_to(self):
        ledger = ledger_with_holdings()
        # a sale of more than is held makes the quantity inconsistent: replay flags it, the service does not touch it
        ledger.add(LedgerEvent(eid(), A1, EventType.SELL, D(2025, 1, 5), USD, listing_id=LISTING, quantity=Decimal(80),
                               amount=Money(Decimal(100), USD)))
        report = run(ledger, corroborated())
        self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.POSITION_UNKNOWN])
        self.assertEqual(ledger.appended, [])


class CorroborationTests(unittest.TestCase):
    def one(self, readings):
        ledger = ledger_with_holdings()
        report = run(ledger, port_with(readings))
        return report, ledger

    def test_a_feed_only_record_is_never_appended(self):
        report, ledger = self.one([split_reading(FEED, FEED_SHA, (4, 1))])
        self.assertEqual([f.status for f in report.findings], [f8b.Corroboration.FEED_ONLY])
        self.assertEqual((report.outcomes, ledger.appended), ((), []))

    def test_a_filing_only_record_is_never_appended(self):
        report, ledger = self.one([split_reading(FILING, FILING_SHA, (4, 1))])
        self.assertEqual([f.status for f in report.findings], [f8b.Corroboration.FILING_ONLY])
        self.assertEqual(ledger.appended, [])

    def test_a_feed_and_a_filing_that_disagree_are_never_appended(self):
        report, ledger = self.one([split_reading(FEED, FEED_SHA, (4, 1)), split_reading(FILING, FILING_SHA, (5, 1))])
        self.assertEqual([f.status for f in report.findings], [f8b.Corroboration.DISAGREEMENT])
        self.assertEqual(ledger.appended, [])

    def test_a_different_ex_date_is_not_corroboration(self):
        report, ledger = self.one([split_reading(FEED, FEED_SHA, (4, 1), day=EX),
                                   split_reading(FILING, FILING_SHA, (4, 1), day=EX + datetime.timedelta(days=1))])
        self.assertEqual(sorted(f.status.value for f in report.findings), ["FEED_ONLY", "FILING_ONLY"])
        self.assertEqual(ledger.appended, [])

    def test_synthetic_and_real_records_never_meet(self):
        report, ledger = self.one([split_reading(FEED, FEED_SHA, (4, 1)), split_reading(FILING, FILING_SHA, (4, 1), usage=SYN)])
        self.assertEqual([f.status for f in report.findings], [f8b.Corroboration.SYNTHETIC_MIXED])
        self.assertEqual(ledger.appended, [])

    def test_a_source_that_is_neither_feed_nor_filing_is_not_read_by_corroboration_and_refuses_the_append_run(self):
        readings = [split_reading("synthetic.other", "e" * 64, (4, 1)), split_reading(FILING, FILING_SHA, (4, 1))]
        # `corroborate` itself reads classified sources only: the unclassified record is not part of the finding ...
        self.assertEqual([f.status for f in f8b.corroborate(LISTING, readings, POLICY)], [f8b.Corroboration.FILING_ONLY])
        # ... but market-data/1.11 Ruling 6.4d: the run is REFUSED for the (listing, ex-date) key and nothing is appended (before 1.11 the record was silently ignored)
        ledger = ledger_with_holdings()
        with self.assertRaises(f8b.DetectionPolicyUnmatchedError) as ctx:
            run(ledger, port_with(readings))
        (key,) = ctx.exception.keys
        self.assertEqual((key.listing, key.ex_date, key.unclassified_sources, key.unmatched_roles), (LISTING, EX, ("synthetic.other",), ("feed",)))
        self.assertEqual(ledger.appended, [])

    def test_the_policy_needs_both_roles_and_no_source_may_be_both(self):
        with self.assertRaises(ValueError):
            f8b.ConfirmationPolicy(frozenset(), frozenset({FILING}))
        with self.assertRaises(ValueError):
            f8b.ConfirmationPolicy(frozenset({FEED}), frozenset({FEED}))

    def test_another_listings_split_is_not_applied_to_this_listing(self):
        ledger = ledger_with_holdings()
        port = port_with([split_reading(FEED, FEED_SHA, (4, 1), listing=OTHER_LISTING),
                          split_reading(FILING, FILING_SHA, (4, 1), listing=OTHER_LISTING)])
        report = run(ledger, port, accounts_listing=(LISTING,))
        self.assertEqual((report.findings, ledger.appended), ((), []))

    def test_the_same_inputs_give_the_same_report_and_the_same_events(self):
        reports, ledgers = [], []
        for _ in range(2):
            ledger = ledger_with_holdings(accounts=(A1, A2))
            reports.append(run(ledger, corroborated()))
            ledgers.append([(e.event_id, e.account_id, e.source_reference) for e in ledger.appended])
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(ledgers[0], ledgers[1])


REF_41 = f8b.build_source_reference("market-data/1.4", "a" * 64, [FEED_SHA], [FILING_SHA], EX, SplitRatio(Decimal(4), Decimal(1)))


def quantity_on(ledger, day, account=A1):
    return reconstruct(ledger.load(PORTFOLIO)[1], day, ledger.seq).account(account).positions[0].quantity.value


def user_split(ledger, day, ratio=(4, 1), account=A1, ref="user-entered"):
    event = LedgerEvent(eid(), account, EventType.SPLIT, day, USD, listing_id=LISTING,
                        split_ratio=SplitRatio(Decimal(ratio[0]), Decimal(ratio[1])), source_reference=ref)
    ledger.add(event)
    return event


class C2_3_LinkingWindowTests(unittest.TestCase):
    """Ruling 6.4a (C2-3). The reviewer's probe P2c: two corroborated 2:1 splits, ex-dates 2025-02-03 and 2025-08-04; the user
    recorded only the August one; 50 units from December 2024. Before the fix a run over January to March found the August
    split "unexplained", called the February split CONFLICT_DATE, appended nothing and left the position at 100 on
    2025-09-01 (true: 50 x 2 x 2 = 200) with no suppression: the outcome depended on the caller's date range."""

    AUG = D(2025, 8, 4)

    def two_splits(self):
        return port_with([split_reading(FEED, FEED_SHA, (2, 1), day=EX), split_reading(FILING, FILING_SHA, (2, 1), day=EX),
                          split_reading(FEED, FEED_SHA, (2, 1), day=self.AUG), split_reading(FILING, FILING_SHA, (2, 1), day=self.AUG)])

    def ledger_with_only_august(self):
        ledger = ledger_with_holdings()
        user_split(ledger, self.AUG, ratio=(2, 1), ref="user-august")
        return ledger

    def test_the_outcome_for_one_ledger_and_one_release_does_not_depend_on_the_callers_date_range(self):
        results = {}
        for name, (start, end) in {"full year": (D(2025, 1, 1), D(2025, 12, 31)), "january to march": (D(2025, 1, 1), D(2025, 3, 31))}.items():
            ledger = self.ledger_with_only_august()
            report = run(ledger, self.two_splits(), start=start, end=end)
            february = [o for o in report.outcomes if o.ex_date == EX]
            self.assertEqual([(o.decision, o.linking) for o in february], [(f8b.SplitDecision.APPENDED, "NOT_RECORDED")], name)
            self.assertEqual(len(ledger.appended), 1, name)
            (event,) = ledger.appended
            self.assertEqual((event.event_date, event.split_ratio.new_units, event.split_ratio.old_units), (EX, Decimal(2), Decimal(1)), name)
            # 50 x 2 (February, appended) x 2 (August, the user's) = 200 on 2025-09-01; 100 was the unflagged wrong value
            self.assertEqual(quantity_on(ledger, D(2025, 9, 1)), Decimal(200), name)
            self.assertIsNone(report.suppressed_on(A1, LISTING, D(2025, 9, 1)), name)
            results[name] = (event.event_id, event.source_reference)
        self.assertEqual(results["full year"], results["january to march"])  # the very same event, whichever the window
        # and the August split, when the caller asks about it, is MATCHED against the user's own entry
        ledger = self.ledger_with_only_august()
        report = run(ledger, self.two_splits())
        august = [o for o in report.outcomes if o.ex_date == self.AUG]
        self.assertEqual([(o.decision, o.linking) for o in august], [(f8b.SplitDecision.ALREADY_RECORDED, "MATCHED")])

    def test_a_ledger_split_inside_no_window_is_only_flagged_in_lineage_whatever_its_ratio(self):
        # only February is corroborated; the user's August split (an equal ratio, 2:1) lies in no window: not CONFLICT_DATE
        port = port_with([split_reading(FEED, FEED_SHA, (2, 1)), split_reading(FILING, FILING_SHA, (2, 1))])
        for ratio in ((2, 1), (3, 1)):
            ledger = ledger_with_holdings()
            user = user_split(ledger, self.AUG, ratio=ratio, ref="user-august")
            report = run(ledger, port)
            self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.APPENDED], ratio)
            (flag,) = report.lineage_flags
            self.assertEqual((flag.flag, flag.event_id, flag.event_date), ("UNCORROBORATED_LEDGER_SPLIT", user.event_id, self.AUG), ratio)
            self.assertEqual(report.suppressions, (), ratio)  # no state effect

    def test_the_window_is_a_closed_interval_of_20_sessions_on_the_listings_calendar(self):
        # W(EX) = [2025-01-06, 2025-03-03] (hand derivation at CALENDARS). An equal split ON either end is a candidate
        # (CONFLICT_DATE); one session further out is no candidate and the corroborated split is appended
        port = corroborated()
        for day, decision in ((D(2025, 1, 6), f8b.SplitDecision.CONFLICT_DATE), (D(2025, 3, 3), f8b.SplitDecision.CONFLICT_DATE),
                              (D(2025, 1, 3), f8b.SplitDecision.APPENDED), (D(2025, 3, 4), f8b.SplitDecision.APPENDED)):
            ledger = ledger_with_holdings()
            user_split(ledger, day)
            self.assertEqual([o.decision for o in run(ledger, port).outcomes], [decision], day)

    def test_a_different_ratio_inside_the_window_is_conflict_ratio_from_the_earlier_date_and_outside_it_only_uncorroborated(self):
        ledger = ledger_with_holdings()
        user_split(ledger, D(2025, 1, 20), ratio=(2, 1))
        (o,) = run(ledger, corroborated()).outcomes
        self.assertEqual((o.decision, o.linking, o.ledger_date), (f8b.SplitDecision.CONFLICT_RATIO, "CONFLICT_RATIO", D(2025, 1, 20)))
        report = run(ledger_with_holdings(), corroborated())  # (control: nothing recorded: appended)
        self.assertEqual([x.decision for x in report.outcomes], [f8b.SplitDecision.APPENDED])
        # suppression runs from min(X, earliest candidate) = 2025-01-20, open-ended
        ledger = ledger_with_holdings()
        user_split(ledger, D(2025, 1, 20), ratio=(2, 1))
        (s,) = run(ledger, corroborated()).suppressions
        self.assertEqual((s.first_date, s.end_exclusive, s.reason_code), (D(2025, 1, 20), None, ReasonCode.SOURCE_CONFLICT))

    def test_two_ledger_splits_inside_one_window_are_conflict_ratio(self):
        ledger = ledger_with_holdings()
        user_split(ledger, D(2025, 1, 20), ratio=(4, 1), ref="one")
        user_split(ledger, D(2025, 1, 27), ratio=(4, 1), ref="two")
        (o,) = run(ledger, corroborated()).outcomes
        self.assertEqual((o.decision, ledger.appended), (f8b.SplitDecision.CONFLICT_RATIO, []))

    def test_overlapping_windows_make_both_outcomes_conflict_ratio_with_nothing_appended(self):
        # corroborated 4:1 on Mon 2025-02-03 and Mon 2025-02-24; W = [Jan 6, Mar 3] and [Jan 27, Mar 24] (hand: before 24 Feb:
        # Feb 21..17 = 5, 14..10 = 10, 7..3 = 15, Jan 31..27 = 20; after: Feb 25..28 = 4, Mar 3..7 = 9, 10..14 = 14, 17..21 = 19,
        # 24 = 20). The overlap is [Jan 27, Mar 3]; a user split on Feb 10 lies inside it and links to just one of them: neither
        feb24 = D(2025, 2, 24)
        port = port_with([split_reading(FEED, FEED_SHA, (4, 1), day=EX), split_reading(FILING, FILING_SHA, (4, 1), day=EX),
                          split_reading(FEED, FEED_SHA, (4, 1), day=feb24), split_reading(FILING, FILING_SHA, (4, 1), day=feb24)])
        ledger = ledger_with_holdings()
        user_split(ledger, D(2025, 2, 10), ratio=(4, 1), ref="between")
        report = run(ledger, port)
        self.assertEqual(sorted((o.ex_date, o.decision, o.linking) for o in report.outcomes),
                         [(EX, f8b.SplitDecision.CONFLICT_RATIO, "CONFLICT_RATIO"), (feb24, f8b.SplitDecision.CONFLICT_RATIO, "CONFLICT_RATIO")])
        self.assertEqual(ledger.appended, [])
        # C2-15: BOTH are suppressed from the EARLIER ex-date (the second used to start at the user's split, 2025-02-10)
        self.assertEqual(sorted((s.first_date, s.end_exclusive) for s in report.suppressions), [(EX, None), (EX, None)])
        # C2-15: the overlap alone is enough, wherever the ledger split lies (Jan 20 is inside W(EX) only; it used to be a
        # normal CONFLICT_DATE for the first split) and with NO ledger split at all (see C2_15_*)
        ledger = ledger_with_holdings()
        user_split(ledger, D(2025, 1, 20), ratio=(4, 1), ref="early")
        by = {o.ex_date: o for o in run(ledger, port).outcomes}
        self.assertEqual({d: o.decision for d, o in by.items()},
                         {EX: f8b.SplitDecision.CONFLICT_RATIO, feb24: f8b.SplitDecision.CONFLICT_RATIO})
        self.assertEqual(ledger.appended, [])

    def test_a_window_the_calendar_does_not_cover_gives_a_coverage_gap_nothing_appended_and_no_reason_code(self):
        short = CalendarSet([k.exchange_calendar("TEST_SESSIONS", (MIC,), weekdays(D(2025, 1, 20), D(2025, 2, 14)))])
        for name, calendars in (("a calendar too short for the window", short), ("no calendar at all", CalendarSet())):
            ledger = ledger_with_holdings()
            report = f8b.confirm_splits(ledger, corroborated(), PORTFOLIO, (LISTING,), D(2025, 1, 1), D(2025, 12, 31), POLICY,
                                        {LISTING: USD}, calendars=calendars, exchange_of=exchange_of)
            (o,) = report.outcomes
            self.assertEqual((o.decision, o.linking, o.cause), (f8b.SplitDecision.CALENDAR_COVERAGE_GAP, "CALENDAR_COVERAGE_GAP",
                                                                 "CALENDAR_COVERAGE_GAP"), name)
            self.assertEqual(ledger.appended, [], name)
            (s,) = report.suppressions
            # INSUFFICIENT_DATA from the ex-date with NO reason code (Ruling 5.3: a configuration gap, not a data condition)
            self.assertEqual((s.first_date, s.end_exclusive, s.reason_code), (EX, None, None), name)
            self.assertIn("CALENDAR_COVERAGE_GAP", s.flag)
            self.assertIsNotNone(report.suppressed_on(A1, LISTING, D(2025, 6, 1)), name)

    def test_the_calendar_and_the_mic_are_required_so_a_caller_cannot_skip_the_window(self):
        with self.assertRaises(TypeError):
            f8b.confirm_splits(ledger_with_holdings(), corroborated(), PORTFOLIO, (LISTING,), D(2025, 1, 1), D(2025, 12, 31), POLICY,
                               {LISTING: USD})


class C2_10_UserReversalIsFinalWithinItsWindowTests(unittest.TestCase):
    """Ruling 6.4b (C2-10): the system never appends again for the same (account, listing) with a date inside the reversed
    event's window; a corroborated split whose window does not contain the reversed date follows the normal rule. Before the
    fix only the SAME ex-date and ratio were recognised, so a corrected ex-date inside the window was appended again."""

    def reversed_system_split(self):
        ledger = ledger_with_holdings()
        run(ledger, corroborated())
        (system,) = ledger.appended
        ledger.add(LedgerEvent(eid(), A1, EventType.REVERSAL, D(2025, 2, 10), USD, reverses_event_id=system.event_id))
        return ledger

    def test_a_corrected_ex_date_inside_the_window_is_not_appended_and_names_its_cause(self):
        ledger = self.reversed_system_split()
        version = ledger.seq
        corrected = D(2025, 2, 5)  # W = [Jan 8, Mar 5] (hand: before 5 Feb: Feb 4, 3 = 2, Jan 31..27 = 7, 24..20 = 12, 17..13 = 17,
        #                            Jan 10, 9, 8 = 20), and it contains the reversed event's date, 3 February
        port = port_with([split_reading(FEED, FEED_SHA, (4, 1), day=corrected), split_reading(FILING, FILING_SHA, (4, 1), day=corrected)], "corrected")
        report = run(ledger, port)
        (o,) = report.outcomes
        self.assertEqual((o.decision, o.linking, o.cause), (f8b.SplitDecision.REVERSED_BY_USER, "NOT_RECORDED", "SYSTEM_SPLIT_REVERSED_BY_USER"))
        self.assertEqual((ledger.seq, len(ledger.appended)), (version, 1))  # nothing was appended
        (s,) = report.suppressions
        self.assertEqual((s.first_date, s.end_exclusive, s.reason_code), (corrected, None, ReasonCode.SOURCE_CONFLICT))
        self.assertIn("SYSTEM_SPLIT_REVERSED_BY_USER", s.flag)

    def test_a_corroborated_split_whose_window_does_not_contain_the_reversed_date_follows_the_normal_rule(self):
        # Mon 2 June 2025: W = [2025-05-05, 2025-06-30] (hand: before: May 30..26 = 5, 23..19 = 10, 16..12 = 15, 9..5 = 20; after:
        # Jun 3..6 = 4, 9..13 = 9, 16..20 = 14, 23..27 = 19, Jun 30 = 20) does not contain 3 February: a different event
        ledger = self.reversed_system_split()
        june = D(2025, 6, 2)
        port = port_with([split_reading(FEED, FEED_SHA, (4, 1), day=june), split_reading(FILING, FILING_SHA, (4, 1), day=june)], "june")
        (o,) = run(ledger, port).outcomes
        self.assertEqual((o.decision, o.linking), (f8b.SplitDecision.APPENDED, "NOT_RECORDED"))
        self.assertEqual(len(ledger.appended), 2)

    def test_the_user_clears_it_by_recording_the_split_themselves(self):
        ledger = self.reversed_system_split()
        user_split(ledger, EX, ref="user-correction")
        (o,) = run(ledger, corroborated(name="release-later")).outcomes
        self.assertEqual((o.decision, o.linking), (f8b.SplitDecision.ALREADY_RECORDED, "MATCHED"))


class C2_2_SyntheticEvidenceIsNeverAppendedTests(unittest.TestCase):
    """Ruling 4.8 items 1-2 (C2-2). The reviewer's probe P2a: a synthetic feed and a synthetic filing were CORROBORATED and
    appended on a ledger of 50 units, the replayed quantity on the ex-date became 200, and the event carried an ordinary
    `finweb.f8b/1;...` reference. A ledger event is a canonical fact: synthetic evidence is reported and never appended."""

    def test_a_synthetic_feed_and_a_synthetic_filing_are_reported_and_nothing_is_appended(self):
        ledger = ledger_with_holdings()
        port = port_with([split_reading(FEED, FEED_SHA, (4, 1), usage=SYN), split_reading(FILING, FILING_SHA, (4, 1), usage=SYN)])
        self.assertTrue(port.contains_synthetic)
        report = run(ledger, port)
        # market-data 1.9 Ruling 4.8 item 4: two synthetic records corroborate within their own world (no upstream test) ...
        self.assertEqual([(f.status, f.synthetic) for f in report.findings], [(f8b.Corroboration.CORROBORATED, True)])
        # ... the outcome is NOT_RECORDED, append barred (never WOULD_APPEND, never APPENDED), and nothing is written
        (o,) = report.outcomes
        self.assertEqual((o.decision, o.cause, o.linking), (f8b.SplitDecision.NOT_RECORDED_APPEND_BARRED,
                                                            f8b.SYNTHETIC_EVIDENCE_APPEND_BARRED, "NOT_RECORDED"))
        self.assertEqual(ledger.appended, [])
        self.assertEqual(quantity_on(ledger, EX), Decimal(50))  # it was 200
        # ... and it DRIVES SUPPRESSION exactly as real evidence does (item 4(c)): valuation withheld from the ex-date, SOURCE_CONFLICT
        (s,) = report.suppressions
        self.assertEqual((s.account_id, s.listing_id, s.first_date, s.end_exclusive, s.reason_code), (A1, LISTING, EX, None, ReasonCode.SOURCE_CONFLICT))
        # a dry run reports the same barred outcome in place of WOULD_APPEND
        dry = f8b.confirm_splits(ledger, port, PORTFOLIO, (LISTING,), D(2025, 1, 1), D(2025, 12, 31), POLICY, {LISTING: USD}, calendars=CALENDARS,
                                 exchange_of=exchange_of, dry_run=True)
        self.assertEqual([o.decision for o in dry.outcomes], [f8b.SplitDecision.NOT_RECORDED_APPEND_BARRED])

    def test_synthetic_feed_and_filing_need_no_upstream_test_but_a_mixed_pair_never_corroborates(self):
        # item 4(a): both synthetic with the SAME independence group still corroborate (the test of Ruling 4.1 does not apply to them) ...
        ledger = ledger_with_holdings()
        import dataclasses  # noqa: PLC0415

        same = [dataclasses.replace(split_reading(FEED, FEED_SHA, (4, 1), usage=SYN), independence_group="synthetic"),
                dataclasses.replace(split_reading(FILING, FILING_SHA, (4, 1), usage=SYN), independence_group="synthetic")]
        self.assertEqual({r.independence_group for r in same}, {"synthetic"})
        report = run(ledger, port_with(same))
        self.assertEqual([f.status for f in report.findings], [f8b.Corroboration.CORROBORATED])
        # ... a real record and a synthetic record never corroborate, in either direction
        for pair in ([split_reading(FEED, FEED_SHA, (4, 1)), split_reading(FILING, FILING_SHA, (4, 1), usage=SYN)],
                     [split_reading(FEED, FEED_SHA, (4, 1), usage=SYN), split_reading(FILING, FILING_SHA, (4, 1))]):
            rep = run(ledger_with_holdings(), port_with(pair))
            self.assertEqual([f.status for f in rep.findings], [f8b.Corroboration.SYNTHETIC_MIXED])
            self.assertEqual(rep.suppressions, ())

    def test_real_evidence_in_a_version_that_holds_other_synthetic_files_may_be_appended(self):
        # item 4(d): the append bar depends on the EVIDENCE, not on M. The old rewrite of every finding because M held any synthetic file is corrected.
        ledger = ledger_with_holdings()
        other = k.quote_reading(D(2025, 1, 31), "10.00", listing=OTHER_LISTING)  # a synthetic quote of another listing
        port = port_with([split_reading(FEED, FEED_SHA, (4, 1)), split_reading(FILING, FILING_SHA, (4, 1)), other])
        self.assertTrue(port.contains_synthetic)
        report = run(ledger, port)
        self.assertEqual([(f.status, f.synthetic) for f in report.findings], [(f8b.Corroboration.CORROBORATED, False)])
        self.assertEqual([o.decision for o in report.outcomes], [f8b.SplitDecision.APPENDED])
        self.assertEqual(len(ledger.appended), 1)

    def test_real_evidence_in_a_real_version_is_still_appended(self):
        ledger = ledger_with_holdings()
        port = corroborated()
        self.assertFalse(port.contains_synthetic)
        self.assertEqual([o.decision for o in run(ledger, port).outcomes], [f8b.SplitDecision.APPENDED])


class C2_7_FeedAndFilingNeedDifferentUpstreamsTests(unittest.TestCase):
    """Ruling 4.1 (C2-7). Probe P2b: readings whose `independence_group` was the same (`vendorX`) were CORROBORATED and appended."""

    def with_groups(self, feed_group, filing_group):
        def reading(source, sha, group):
            r = split_reading(source, sha, (4, 1))
            return c.SourceReading(r.source_id, group, r.file_sha256, r.observation)

        return port_with([reading(FEED, FEED_SHA, feed_group), reading(FILING, FILING_SHA, filing_group)])

    def test_one_upstream_for_both_roles_is_not_corroboration_and_nothing_is_appended(self):
        ledger = ledger_with_holdings()
        report = run(ledger, self.with_groups("vendorX", "vendorX"))
        self.assertEqual([f.status for f in report.findings], [f8b.Corroboration.SAME_UPSTREAM])
        self.assertEqual((report.outcomes, ledger.appended), ((), []))

    def test_two_upstreams_corroborate(self):
        ledger = ledger_with_holdings()
        report = run(ledger, self.with_groups("vendorX", "issuer-filing"))
        self.assertEqual([f.status for f in report.findings], [f8b.Corroboration.CORROBORATED])
        self.assertEqual(len(ledger.appended), 1)


class C2_8_TheSystemMarkerCannotBeForgedTests(unittest.TestCase):
    """PD-0030 section 2 (C2-8). Probe P2d: a user recorded a 4:1 split with an f8b-shaped `source_reference` and reversed it;
    the service reported REVERSED_BY_USER and appended nothing, treating the user's own entry as a system split. CHOICE: the
    marker is made unforgeable at the append path (the `finweb.` namespace is reserved: only `append_system_event` may write
    it) AND the service recognises only a split whose reference parses strictly and whose event id is the deterministic id of
    (account, reference). A marker check at one layer alone would leave the other open."""

    FORGED = REF_41

    def user_event(self, ref, day=EX):
        return LedgerEvent(eid(), A1, EventType.SPLIT, day, USD, listing_id=LISTING, split_ratio=SplitRatio(Decimal(4), Decimal(1)),
                           source_reference=ref)

    def test_every_ordinary_append_path_refuses_a_reference_in_the_reserved_namespace(self):
        from persistence import ledger_store  # noqa: PLC0415

        for spelling in (self.FORGED, "  " + self.FORGED, self.FORGED.upper(), "ﬁ" + self.FORGED[2:], "finweb.anything",
                         "FinWeb.f8b/2;x"):
            event = self.user_event(spelling)
            self.assertTrue(ledger_store.is_reserved_source_reference(spelling), spelling)
            with self.assertRaises(ledger_store.ReservedSourceReferenceError, msg=spelling):
                ledger_store.append_event(None, event)  # refused before the connection is touched
            with self.assertRaises(ledger_store.ReservedSourceReferenceError, msg=spelling):
                ledger_store.append_batch(None, [self.user_event("fine-reference"), event])  # and no partial batch
        for fine in ("broker-statement-2025-02-03", "my finweb.f8b/1 note", "f8b/1", None):
            self.assertFalse(ledger_store.is_reserved_source_reference(fine), fine)

    def test_only_the_system_path_accepts_the_marker_and_only_with_the_matching_namespace(self):
        from persistence import ledger_store  # noqa: PLC0415

        with self.assertRaises(ledger_store.ReservedSourceReferenceError):
            ledger_store.append_system_event(None, self.user_event("plain-reference"), namespace=f8b.PREFIX)  # not in the namespace
        with self.assertRaises(ledger_store.ReservedSourceReferenceError):
            ledger_store.append_system_event(None, self.user_event(self.FORGED), namespace="finweb.other/1")  # another namespace
        with self.assertRaises(ledger_store.ReservedSourceReferenceError):
            ledger_store.append_system_event(None, self.user_event(self.FORGED), namespace="plain")  # not a reserved namespace

    def test_an_entry_that_imitates_the_marker_is_not_a_system_event_so_its_reversal_is_not_final(self):
        # the user's own entry (a random event id, an f8b-shaped reference) reaches the ledger by some other route and is reversed
        ledger = ledger_with_holdings()
        forged = self.user_event(self.FORGED)
        ledger.add(forged)
        ledger.add(LedgerEvent(eid(), A1, EventType.REVERSAL, D(2025, 2, 10), USD, reverses_event_id=forged.event_id))
        self.assertIsNotNone(f8b.parse_source_reference(forged.source_reference))  # it parses ...
        self.assertFalse(f8b.is_system_event(forged))                              # ... but it is not one of ours
        (o,) = run(ledger, corroborated()).outcomes
        self.assertEqual(o.decision, f8b.SplitDecision.APPENDED)  # it was REVERSED_BY_USER with nothing appended

    def test_a_split_the_service_appended_is_recognised_and_its_reversal_is_final(self):
        ledger = ledger_with_holdings()
        run(ledger, corroborated())
        (system,) = ledger.appended
        self.assertTrue(f8b.is_system_event(system))

    def test_the_reference_grammar_is_strict_no_duplicate_key_no_extra_key_no_overlength_no_bad_hash(self):
        good = f8b.parse_source_reference(self.FORGED)
        self.assertEqual(good.ratio, ("4", "1"))
        for bad, why in ((self.FORGED + ";ratio=9/1", "a duplicate key (last-wins before the fix)"),
                         (self.FORGED + ";extra=1", "an extra key"),
                         (self.FORGED.replace("ex=", "xe="), "a renamed key"),
                         (self.FORGED.replace(";md=market-data/1.4", ""), "a missing key"),
                         (self.FORGED.replace("rel=" + "a" * 64, "rel=not-a-hash"), "a bad release hash"),
                         (self.FORGED.replace("ratio=4/1", "ratio=4/0"), "a zero ratio term"),
                         (self.FORGED.replace("ex=2025-02-03", "ex=2025-13-45"), "a bad date"),
                         (self.FORGED + "x" * f8b.MAX_SOURCE_REFERENCE_CHARS, "over the length bound"),
                         (self.FORGED + " ", "a trailing blank")):
            self.assertIsNone(f8b.parse_source_reference(bad), why)


class BoundaryTests(unittest.TestCase):
    """The service lives outside the market-data layer, and the market-data layer never learns of it."""

    def imports(self, path):
        names = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module)
        return names

    def test_the_service_imports_no_adapter_ingestion_vendor_or_tool(self):
        for path in sorted((SRC / "corporate_actions_service").glob("*.py")):
            names = self.imports(path)
            for banned in ("marketdata.adapters", "marketdata.ingest", "marketdata.files", "marketdata_tools"):
                self.assertFalse({n for n in names if n == banned or n.startswith(banned + ".")}, f"{path.name}: {banned}")
            text = path.read_text(encoding="utf-8").lower()
            for word in ("akshare", "baostock", "alphavantage", "frankfurter", "openfigi", "pandas"):
                self.assertNotIn(word, text, path.name)

    def test_no_module_of_the_market_data_layer_imports_the_service_or_appends_to_the_ledger(self):
        for path in sorted((SRC / "marketdata").rglob("*.py")):
            names = self.imports(path)
            self.assertFalse({n for n in names if n.startswith("corporate_actions_service")}, path.name)
            self.assertFalse({n for n in names if n.startswith("persistence")}, path.name)

    def test_the_service_does_not_import_the_domain_replay_internals_or_write_anywhere_but_the_append_path(self):
        names = self.imports(SRC / "corporate_actions_service" / "split_confirmation.py")
        self.assertIn("persistence.ledger_store", names)
        self.assertFalse({n for n in names if n.startswith("psycopg")})  # the driver is reached only through persistence


if __name__ == "__main__":
    unittest.main()
