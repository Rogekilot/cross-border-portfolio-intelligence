"""CP4 part A, round 4: review section 35 (CP4-10, CP4-11) and the lock-schema residual.

- CP4-10: a file is SYNTHETIC_TEST if and only if its source is synthetic (market-data Ruling 4.7, as `ingest_file` enforces), on the PostgreSQL read path and for a directly built in-memory store.
- CP4-11: the F8-B advisory lock is real: while one connection is inside `atomic` for a portfolio, an append on a second connection waits and fails with `lock_timeout` (55P03).
- The lock's schema is found from the ledger's append trigger, the value the trigger's own key uses.
"""

import dataclasses
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_kit  # noqa: E402
import marketdata_cp2c1_kit as k  # noqa: E402
import pg_market_kit as pgk  # noqa: E402
import test_corporate_actions_service as ca  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402
import test_performance_recheck as rc  # noqa: E402

from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from domain.currency import Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from marketdata.manifest import MarketDataRelease, SourceRegistry, SourceRegistryNotPinnedError  # noqa: E402
from marketdata.store import InMemoryMarketData  # noqa: E402
from persistence import market_data_store as mds  # noqa: E402

D = __import__("datetime").date
USD = mp.USD


class Cp4_10InMemoryTests(unittest.TestCase):
    def store(self, flip):
        base = mp.market("real", real_quotes=True)
        readings = list(base._readings_in)
        records = k.records_for(readings)
        if flip:
            records = [dataclasses.replace(r, synthetic=not r.synthetic) if r.source_id == records[0].source_id else r for r in records]
        with gate_kit.admitted_real_world(readings, mp.MIC):  # 1.16 Ruling 4.7 item 6: see gate_kit (the probe market's exchange is XTST)
            return InMemoryMarketData(base._release, readings, exchange_of=lambda _l: mp.MIC, source_records=records)

    def test_a_record_that_disagrees_with_the_readings_usage_scope_is_refused_both_ways(self):
        self.assertTrue(self.store(False).source_registry_records())  # consistent: accepted
        with self.assertRaises(SourceRegistryNotPinnedError):
            self.store(True).source_registry_records()  # real readings under a record that says synthetic (the terms-gate bypass) and the reverse are both a disagreement
        base = mp.market("synthetic", real_quotes=True)
        readings = list(base._readings_in)
        recs = [dataclasses.replace(r, synthetic=False) for r in k.records_for(readings)]  # synthetic readings under records that say real
        with gate_kit.admitted_real_world(readings, mp.MIC):  # 1.16 Ruling 4.7 item 6: see gate_kit (`real_quotes=True`: the quotes are real even where the evidence is synthetic)
            store = InMemoryMarketData(base._release, readings, exchange_of=lambda _l: mp.MIC, source_records=recs)
        with self.assertRaises(SourceRegistryNotPinnedError):
            store.source_registry_records()


@unittest.skipIf(bool(pgk.skip_reason()), pgk.skip_reason())
class Cp4_10PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_performance_cp3a as cp3a  # noqa: PLC0415

        cp3a.PostgresValuationTests.setUpClass.__func__(cls)  # a synthetic "formats" world projected into PostgreSQL: every file SYNTHETIC_TEST

    def read(self, records):
        return mds.read_release(self.app, self.world.release.release_id, exchange_of=self.world.ident.exchange_mic, registry=SourceRegistry(records))

    def records(self):
        return list(self.world.store.source_registry_records())

    def test_the_consistent_registry_reads(self):
        self.assertTrue(self.read(self.records()).source_registry_records())

    def test_a_registry_that_calls_synthetic_sources_real_is_refused_like_the_in_memory_build(self):
        # the reviewer's reproduction: every source real (with a passing terms check), over rows that are all SYNTHETIC_TEST
        from marketdata.manifest import TermsCheck  # noqa: PLC0415

        real = [dataclasses.replace(r, synthetic=False, terms_check=TermsCheck("owner", D(2026, 10, 1), True, "checked")) for r in self.records()]
        with self.assertRaises(mds.RegistryDisagreesWithStoredRowsError):
            self.read(real)

    def test_a_real_source_edited_to_synthetic_is_refused_the_terms_gate_cannot_be_bypassed(self):
        # the harmful mirror: a source whose stored files are REAL, its record edited to synthetic with the terms check removed (`terms_attested` would pass it). A world with real files is
        # projected for this test: only the FILE records (`md_file.usage_scope`) are stored as real; the readings inside are still synthetic. The check under test compares the file records.
        from marketdata.contracts import UsageScope  # noqa: PLC0415

        scratch = pgk.PgSchema().open()
        self.addCleanup(scratch.close)
        pgk.insert_identity(scratch.owner, self.world.ident)
        w = self.world
        manifests = [dataclasses.replace(m, usage_scope=UsageScope.INTERNAL_DEVELOPMENT_ONLY) for m in w.built.manifests]  # the SAME release content with every file stored as real
        release = MarketDataRelease.from_manifests("real-copy", manifests, [])
        mds.write_release(scratch.owner, release, manifests, w.store.export(), w.built.calendars)
        app = scratch.app_connection()
        self.addCleanup(app.close)
        synthetic_records = [dataclasses.replace(r, synthetic=True, terms_check=None) for r in self.records()]
        with self.assertRaises(mds.RegistryDisagreesWithStoredRowsError):
            mds.read_release(app, release.release_id, exchange_of=w.ident.exchange_mic, registry=SourceRegistry(synthetic_records))
        # and an honestly real registry over those real rows is accepted only with a passing terms check (require_attested)
        no_terms = [dataclasses.replace(r, synthetic=False, terms_check=None) for r in self.records()]
        with self.assertRaises(PermissionError):
            mds.read_release(app, release.release_id, exchange_of=w.ident.exchange_mic, registry=SourceRegistry(no_terms))


@unittest.skipIf(bool(pgk.skip_reason()), pgk.skip_reason())
class Cp4_11LockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rc.PostgresRecheckTests.setUpClass.__func__(cls)

    def portfolio(self):
        user, portfolio, account = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        owner = self.db.owner
        owner.execute("INSERT INTO app_user VALUES (%s)", (user,))
        owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (portfolio, user))
        owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (account, portfolio))
        return portfolio, account

    def deposit(self, account):
        return LedgerEvent(uuid.uuid4(), account, EventType.DEPOSIT, D(2025, 1, 2), USD, amount=Money(Decimal(1), USD))

    def second_connection(self):
        conn = self.db.app_connection()
        self.addCleanup(conn.close)
        conn.execute("SET lock_timeout = '300ms'")  # the wait is bounded by the server: no sleep is used to synchronise
        return conn

    @staticmethod
    def sqlstate(exc):
        while exc is not None:
            state = getattr(exc, "sqlstate", None)
            if state:
                return state
            exc = exc.__cause__ or exc.__context__
        return None

    def test_while_one_connection_is_inside_atomic_an_append_on_a_second_connection_waits_and_fails_with_55p03(self):
        portfolio, account = self.portfolio()
        other_portfolio, other_account = self.portfolio()
        second = self.second_connection()
        access = f8b.PostgresLedgerAccess(self.app)
        with access.atomic(portfolio):
            with self.assertRaises(Exception) as ctx:
                self.ls.append_batch(second, [self.deposit(account)])  # the same portfolio: blocked on the advisory lock
            self.assertEqual(self.sqlstate(ctx.exception), "55P03")
            self.ls.append_batch(second, [self.deposit(other_account)])  # another portfolio is not blocked: the lock is per portfolio
        # released with the transaction: the append now goes through
        self.ls.append_batch(second, [self.deposit(account)])
        self.assertEqual(self.rs.current_ledger_version(second, portfolio) > 0, True)

    def test_the_lock_is_released_when_the_run_raises(self):
        portfolio, account = self.portfolio()
        second = self.second_connection()
        access = f8b.PostgresLedgerAccess(self.app)
        with self.assertRaises(RuntimeError):
            with access.atomic(portfolio):
                raise RuntimeError("the run fails")
        self.ls.append_batch(second, [self.deposit(account)])  # the lock did not outlive the rolled-back transaction

    def test_the_lock_schema_is_the_schema_of_the_tables_append_trigger_even_with_a_temp_shadow(self):
        access = f8b.PostgresLedgerAccess(self.app)
        self.assertEqual(access.ledger_schema(), self.db.schema)

        def restore():
            self.app.execute("DROP TABLE IF EXISTS pg_temp.ledger_event")
            self.app.execute('SET search_path TO "%s"' % self.db.schema)

        self.addCleanup(restore)  # runs even if an assertion below fails
        self.app.execute("CREATE TEMP TABLE ledger_event (LIKE ledger_event INCLUDING DEFAULTS)")  # a shadow in pg_temp: excluded by its schema name
        self.app.execute('SET search_path TO pg_temp, "%s"' % self.db.schema)
        self.assertEqual(access.ledger_schema(), self.db.schema)

    def test_a_search_path_without_the_ledger_schema_fails_closed(self):
        access = f8b.PostgresLedgerAccess(self.app)
        self.addCleanup(lambda: self.app.execute('SET search_path TO "%s"' % self.db.schema))
        self.app.execute("SET search_path TO pg_temp")
        with self.assertRaises(RuntimeError):
            access.ledger_schema()

    def test_two_schemas_holding_a_ledger_on_one_search_path_fail_closed_in_both_orders_cp4_12(self):
        # the insert goes to the FIRST schema's table, so a lock named for another would not block a concurrent append: with two candidates nothing is locked or appended
        other = pgk.PgSchema().open()
        self.addCleanup(other.close)
        a, b = self.db.schema, other.schema
        self.addCleanup(lambda: self.app.execute('SET search_path TO "%s"' % a))
        access = f8b.PostgresLedgerAccess(self.app)
        portfolio, _ = self.portfolio()
        for path in ((a, b), (b, a)):
            self.app.execute('SET search_path TO "%s", "%s"' % path)
            with self.assertRaises(RuntimeError):
                access.ledger_schema()
            with self.assertRaises(RuntimeError):
                with access.atomic(portfolio):
                    self.fail("atomic must not enter")
        self.app.execute('SET search_path TO "%s"' % a)
        self.assertEqual(access.ledger_schema(), a)  # one schema again: fine


if __name__ == "__main__":
    unittest.main()
