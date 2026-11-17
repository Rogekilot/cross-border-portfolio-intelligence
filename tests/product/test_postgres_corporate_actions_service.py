"""F8-B against a real server, as the least-privilege application role (opt-in; see `test_postgres_market_data_store.py`
for the variables). The corporate-action feed and the issuer filing are two test-double sources written as files, read by
the mock adapter, projected into the PostgreSQL market-data store and read back by `finweb_app`; the ledger is the real
one under the production grants (migrations 0001-0012, `APP_GRANTS`). Appends go through the system append path.

C2-2 (CP2 review of 39733e9): F8-B never appends from SYNTHETIC evidence, so these files carry the REAL usage scope
(`INTERNAL_DEVELOPMENT_ONLY`, the sources attested in a test registry) and the mock adapter reads them; they used to be
SYNTHETIC_TEST files. The calendar for the linking window (Ruling 6.4a) is a synthetic weekday calendar for XNAS.

The expected values are derived by hand: the account deposits 10,000 USD and buys 50 units for 7,500 USD on 2024-12-20; a
corroborated SPLIT (4, 1) has ex-date 2025-02-03, so the replayed quantity is 50 before it and 50 x 4 = 200 from it.
"""

import datetime
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_kit  # noqa: E402
import marketdata_exit_kit as x  # noqa: E402
import pg_market_kit as pk  # noqa: E402

k = x.k
c = x.c
kit = x.kit

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent, SplitRatio  # noqa: E402
from marketdata.adapters.base import AdapterRegistry  # noqa: E402
from marketdata.adapters.mock import MOCK_FORMAT, MockSyntheticAdapter, make_synthetic_payload  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.manifest import DataKind, MarketDataRelease, SourceRecord, TermsCheck  # noqa: E402
from persistence import ledger_replay_store, ledger_store, market_data_store as mds  # noqa: E402

D = datetime.date
EX = D(2025, 2, 3)
FEED, FILING = "mock.feed", "mock.filing"
POLICY = f8b.ConfirmationPolicy(frozenset({FEED}), frozenset({FILING}))
_SKIP = pk.skip_reason()
REAL = c.UsageScope.INTERNAL_DEVELOPMENT_ONLY


def weekday_calendar(mic="XNAS"):
    """Every weekday of 2024-06-03..2026-06-30, no holidays (invented): the +-20 session window of Ruling 6.4a is counted in it."""
    days, day = [], D(2024, 6, 3)
    while day <= D(2026, 6, 30):
        if day.weekday() < 5:
            days.append(day)
        day += datetime.timedelta(days=1)
    return CalendarSet([k.exchange_calendar("TEST_SESSIONS", (mic,), days)])


def action_files(root, ratio=("4", "1"), filing_ratio=None, extra_name="", day=EX):
    """The feed file and the filing file of ONE split of AAPL, in the mock format, written in the real layout, with the
    REAL usage scope (the sources are attested in the test registry): F8-B refuses synthetic evidence (C2-2)."""
    manifests = []
    for source, r in ((FEED, ratio), (FILING, filing_ratio or ratio)):
        # a feed export and an issuer-filing transcription are different files: the note makes the bytes (so the hash) differ
        payload = make_synthetic_payload(actions=({"ticker": "AAPL", "mic": "XNAS", "date": day.isoformat(), "type": "SPLIT",
                                                   "new_units": r[0], "old_units": r[1], "note": f"test double {source}"},))
        manifests.append(kit.write_file(root, source, DataKind.CORPORATE_ACTION, MOCK_FORMAT, payload, f"split{extra_name}", "json",
                                        usage_scope=REAL, retrieved_by="human", source_identifiers=("AAPL",)))
    return manifests


def attested_sources():
    terms = TermsCheck("owner", D(2026, 10, 1), True)
    return [SourceRecord(FEED, FEED, "test-feed-upstream", "test.feed", terms_check=terms),
            SourceRecord(FILING, FILING, "test-filing-upstream", "test.filing", terms_check=terms)]


@unittest.skipIf(bool(_SKIP), _SKIP)
class SplitConfirmationDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg  # noqa: PLC0415

        cls.pg = psycopg
        cls.db = pk.PgSchema().open()
        cls.addClassCleanup(cls.db.close)
        cls.owner = cls.db.owner
        cls.ident = x.identity()
        pk.insert_identity(cls.owner, cls.ident)
        cls.aapl = x.lid(cls.ident, "AAPL", "XNAS")
        cls.user, cls.portfolio = uuid.uuid4(), uuid.uuid4()
        cls.accounts = {n: uuid.uuid4() for n in ("held", "conflict", "reversed", "after")}
        cls.owner.execute("INSERT INTO app_user VALUES (%s)", (cls.user,))
        cls.owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (cls.portfolio, cls.user))
        for account in cls.accounts.values():
            cls.owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (account, cls.portfolio))
        cls.app = cls.db.app_connection()
        cls.addClassCleanup(cls.app.close)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        kit.write_registry(root, extra=attested_sources())
        manifests = action_files(root)
        cls.manifests = manifests
        adapters = AdapterRegistry([MockSyntheticAdapter(DataKind.CORPORATE_ACTION, FEED),
                                    MockSyntheticAdapter(DataKind.CORPORATE_ACTION, FILING)])
        release = MarketDataRelease.from_manifests("f8b-db", manifests, [])
        files = FileStore(root)
        # 1.16 Ruling 4.7 item 6: REAL records of sources with no profile are refused at ingest, at write and at read; this test is about F8-B over a
        # stored release, so the invented feed and filing sources are admitted for the build, the write and the read only (see gate_kit)
        with gate_kit.admitted_sources((FEED, FILING)):
            built = build_in_memory_market_data(release, files, files.load_registry(), adapters, cls.ident, catalog_calendars={})
            assert built.issues == () and built.exceptions == ()
            mds.write_release(cls.owner, release, built.manifests, built.store.export(), built.calendars)
            cls.store = mds.read_release(cls.app, release.release_id, exchange_of=cls.ident.exchange_mic, registry=files.load_registry())
        cls.access = f8b.PostgresLedgerAccess(cls.app)
        # every account: deposit 10,000 USD, buy 50 units for 7,500 USD on 2024-12-20 (the "after" account buys on the ex-date)
        for name, account in cls.accounts.items():
            day = EX if name == "after" else D(2024, 12, 20)
            ledger_store.append_batch(cls.app, [
                LedgerEvent(uuid.uuid4(), account, EventType.DEPOSIT, D(2024, 12, 19), k.USD, amount=Money(Decimal(10000), k.USD)),
                LedgerEvent(uuid.uuid4(), account, EventType.BUY, day, k.USD, listing_id=cls.aapl, quantity=Decimal(50),
                            amount=Money(Decimal(7500), k.USD))])
        # the "conflict" account already holds a wrongly typed split on the ex-date (ratio 2:1)
        ledger_store.append_event(cls.app, LedgerEvent(
            uuid.uuid4(), cls.accounts["conflict"], EventType.SPLIT, EX, k.USD, listing_id=cls.aapl,
            split_ratio=SplitRatio(Decimal(2), Decimal(1)), source_reference="user-typed"))
        cls.calendars = weekday_calendar()
        cls.report = f8b.confirm_splits(cls.access, cls.store, cls.portfolio, [cls.aapl], D(2025, 1, 1), D(2025, 12, 31),
                                        POLICY, {cls.aapl: k.USD}, calendars=cls.calendars, exchange_of=cls.ident.exchange_mic)

    def decisions(self, report=None):
        return {n: o.decision for o in (report or self.report).outcomes for n, a in self.accounts.items() if a == o.account_id}

    def stored_splits(self, account):
        return self.owner.execute(
            "SELECT event_type, event_date, split_new, split_old, source_reference FROM ledger_event "
            "WHERE account_id = %s AND event_type = 'SPLIT' ORDER BY ledger_seq", (account,)).fetchall()

    def test_the_service_ran_as_the_least_privilege_role_and_read_the_database_store(self):
        self.assertEqual(self.app.execute("SELECT current_user").fetchone()[0], self.db.app_role)
        self.assertIsInstance(self.store, mds.PostgresMarketData)

    def test_each_account_got_the_decision_its_ledger_calls_for(self):
        self.assertEqual(self.decisions(), {"held": f8b.SplitDecision.APPENDED, "conflict": f8b.SplitDecision.CONFLICT_RATIO,
                                           "reversed": f8b.SplitDecision.APPENDED, "after": f8b.SplitDecision.NOT_HELD})
        self.assertEqual([f.status for f in self.report.findings], [f8b.Corroboration.CORROBORATED])

    def test_the_appended_event_is_an_ordinary_split_with_provenance_and_the_replayed_quantity_follows(self):
        ((etype, day, new, old, ref),) = self.stored_splits(self.accounts["held"])
        self.assertEqual((etype, day, new, old), ("SPLIT", EX, Decimal(4), Decimal(1)))
        prov = f8b.parse_source_reference(ref)
        self.assertEqual((prov.convention_set_id, prov.release_id, prov.ex_date), ("market-data/1.16", self.store.release_id(), EX))
        self.assertEqual((prov.feed_files, prov.filing_files), ((self.manifests[0].file_sha256,), (self.manifests[1].file_sha256,)))
        state = ledger_replay_store.replay(self.app, self.portfolio, EX)
        before = ledger_replay_store.replay(self.app, self.portfolio, D(2025, 2, 2))
        self.assertEqual((before.account(self.accounts["held"]).positions[0].quantity.value,
                          state.account(self.accounts["held"]).positions[0].quantity.value), (Decimal(50), Decimal(200)))

    def test_the_conflicting_account_got_no_split_appended_and_is_flagged_for_suppression(self):
        splits = self.stored_splits(self.accounts["conflict"])
        self.assertEqual([(s[2], s[3], s[4]) for s in splits], [(Decimal(2), Decimal(1), "user-typed")])  # the user's own, untouched
        (s,) = [s for s in self.report.suppressions if s.account_id == self.accounts["conflict"]]
        self.assertEqual((s.first_date, s.end_exclusive, s.reason_code.value), (EX, None, "SOURCE_CONFLICT"))

    def test_a_rerun_is_a_no_op_for_every_account(self):
        before = self.owner.execute("SELECT count(*), max(ledger_seq) FROM ledger_event").fetchone()
        again = f8b.confirm_splits(self.access, self.store, self.portfolio, [self.aapl], D(2025, 1, 1), D(2025, 12, 31), POLICY,
                                   {self.aapl: k.USD}, calendars=self.calendars, exchange_of=self.ident.exchange_mic)
        self.assertEqual(self.decisions(again)["held"], f8b.SplitDecision.ALREADY_RECORDED)
        self.assertEqual(self.owner.execute("SELECT count(*), max(ledger_seq) FROM ledger_event").fetchone(), before)

    def test_the_ledgers_own_guards_hold_under_the_service_one_live_split_per_day_and_idempotent_resubmission(self):
        ((_, _, _, _, ref),) = self.stored_splits(self.accounts["held"])
        # the identical event again: the existing event is returned, nothing is written
        same = LedgerEvent(f8b.event_id_for(self.accounts["held"], ref), self.accounts["held"], EventType.SPLIT, EX, k.USD,
                           listing_id=self.aapl, split_ratio=SplitRatio(Decimal(4), Decimal(1)), source_reference=ref)
        # (C2-8: the reserved marker is accepted only by the system path; an ordinary append of it is refused, below)
        self.assertFalse(ledger_store.append_system_event(self.app, same, namespace=f8b.PREFIX).created)
        with self.assertRaises(ledger_store.ReservedSourceReferenceError):
            ledger_store.append_event(self.app, same)
        # a SECOND live split on the same day (migration 0007) is refused with its typed error
        with self.assertRaises(ledger_store.SameDaySplitError):
            ledger_store.append_event(self.app, LedgerEvent(
                uuid.uuid4(), self.accounts["held"], EventType.SPLIT, EX, k.USD, listing_id=self.aapl,
                split_ratio=SplitRatio(Decimal(4), Decimal(1)), source_reference="a-second-split"))

    def test_a_split_the_user_reverses_stays_reversed_on_every_later_run(self):
        account = self.accounts["reversed"]
        ((_, _, _, _, ref),) = self.stored_splits(account)
        event_id = f8b.event_id_for(account, ref)
        ledger_store.append_event(self.app, LedgerEvent(uuid.uuid4(), account, EventType.REVERSAL, D(2025, 2, 10), k.USD,
                                                        reverses_event_id=event_id))
        before = self.owner.execute("SELECT count(*) FROM ledger_event WHERE account_id = %s", (account,)).fetchone()[0]
        again = f8b.confirm_splits(self.access, self.store, self.portfolio, [self.aapl], D(2025, 1, 1), D(2025, 12, 31), POLICY,
                                   {self.aapl: k.USD}, calendars=self.calendars, exchange_of=self.ident.exchange_mic)
        self.assertEqual(self.decisions(again)["reversed"], f8b.SplitDecision.REVERSED_BY_USER)
        self.assertEqual(self.owner.execute("SELECT count(*) FROM ledger_event WHERE account_id = %s", (account,)).fetchone()[0], before)
        self.assertEqual(again.suppressions and any(s.account_id == account for s in again.suppressions), True)

    def test_the_provenance_length_bound_keeps_every_system_reference_far_inside_the_unique_index_limit(self):
        account = self.accounts["after"]
        longest = "finweb.f8b/1;" + "a" * (f8b.MAX_SOURCE_REFERENCE_CHARS - len("finweb.f8b/1;"))
        self.assertEqual(len(longest), f8b.MAX_SOURCE_REFERENCE_CHARS)
        event = LedgerEvent(uuid.uuid4(), account, EventType.DEPOSIT, D(2025, 3, 1), k.USD, amount=Money(Decimal(1), k.USD),
                            source_reference=longest)
        # the database accepts the longest we would write (through the system path: the marker is reserved, C2-8)
        self.assertTrue(ledger_store.append_system_event(self.app, event, namespace=f8b.PREFIX).created)
        # the database's own limit is an INDEX limit (about 2.7 KB), reported by the driver rather than as a typed ledger
        # error: which is why the service bounds its reference itself and refuses, instead of relying on the database
        # (the limit is on the index entry AFTER compression, so a repetitive string is not a fair probe: 8,000 characters
        # of hash digests do not compress below it)
        import hashlib  # noqa: PLC0415

        incompressible = "".join(hashlib.sha256(str(i).encode()).hexdigest() for i in range(125))  # 8,000 hex characters
        huge = LedgerEvent(uuid.uuid4(), account, EventType.DEPOSIT, D(2025, 3, 2), k.USD, amount=Money(Decimal(1), k.USD),
                           source_reference=incompressible)
        with self.assertRaises(self.pg.Error):
            ledger_store.append_event(self.app, huge)


if __name__ == "__main__":
    unittest.main()
