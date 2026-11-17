"""CP4b-2: the RISK_FREE kind in PostgreSQL (migration 0016; `persistence.market_data_store`). Opt-in, like every PostgreSQL test (the integration variables plus `FINWEB_PG_APP_USER`).

What is proved: a release holding a risk-free series and its RATE_PUBLICATIONS calendar projects, reads back as the least-privilege role and answers the port exactly as the in-memory store does; the rows are append-only
and sealed with their release like every md_* table; the database refuses what the contract refuses; and the projection digest of a release written BEFORE the migration is the same after it.
"""

import datetime
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402
import marketdata_testkit as kit  # noqa: E402
import pg_market_kit as pk  # noqa: E402
import test_marketdata_risk_free as rfk  # noqa: E402

from domain.currency import CurrencyCode  # noqa: E402
from marketdata.adapters.base import AdapterRegistry  # noqa: E402
from marketdata.adapters.calendar_file import CalendarFileAdapter  # noqa: E402
from marketdata.adapters.synthetic_risk_free import SyntheticRiskFreeAdapter, make_risk_free_payload  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, MarketDataRelease, SourceRecord  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from persistence import connection, migrator  # noqa: E402
from persistence import market_data_store as mds  # noqa: E402

D, USD = datetime.date, CurrencyCode("USD")
_SKIP = pk.skip_reason()


def build_rf_world(root):
    kit.write_registry(root, [SourceRecord(rfk.SOURCE_ID, "synthetic rf", "synthetic", "synthetic.rf", synthetic=True), SourceRecord(rfk.CAL_SOURCE, "calendar", "synthetic", "synthetic.cal", synthetic=True)])
    manifests = [
        kit.write_file(root, rfk.SOURCE_ID, DataKind.RISK_FREE, rfk.PAYLOAD_FORMAT, make_risk_free_payload((rfk.rf_row(),)), "rf", "json", currency=USD, source_identifiers=(rfk.SERIES,)),
        kit.write_file(root, rfk.CAL_SOURCE, DataKind.CALENDAR, rfk.CAL_FORMAT, rfk.calendar_payload(rfk.JAN_DATES), "cal", "json", source_identifiers=(rfk.CAL_ID,)),
    ]
    release = MarketDataRelease.from_manifests("rf-db", manifests, [rfk.SOURCE_ID])
    files = kit.FileStore(root)
    built = build_in_memory_market_data(release, files, files.load_registry(), AdapterRegistry([SyntheticRiskFreeAdapter(), CalendarFileAdapter()]), kit.make_identity(), catalog_calendars={})
    return files, release, built


@unittest.skipIf(bool(_SKIP), _SKIP)
class RiskFreeProjectionDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg  # noqa: PLC0415

        cls.pg = psycopg
        cls.db = pk.PgSchema(prefix="finweb_it_rf_").open()
        cls.addClassCleanup(cls.db.close)
        cls.owner = cls.db.owner
        cls.app = cls.db.app_connection()
        cls.addClassCleanup(cls.app.close)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.files, cls.release, cls.built = build_rf_world(Path(cls.tmp.name))
        cls.registry = cls.files.load_registry()
        cls.result = mds.write_release(cls.owner, cls.release, cls.built.manifests, cls.built.store.export(), cls.built.calendars)

    def read(self, conn=None):
        return mds.read_release(conn or self.app, self.release.release_id, registry=self.registry)

    def test_the_release_projects_one_series_with_its_points_and_a_publication_calendar(self):
        counts = dict(self.result.row_counts)
        self.assertEqual((counts["md_risk_free"], counts["md_risk_free_point"], counts["md_calendar"], counts["md_release_file"]), (1, 3, 1, 2))
        self.assertTrue(self.result.created)
        row = self.owner.execute("SELECT series_id, currency, quote_type, day_count_basis, unit, decimals_published, calendar_id, revision_policy, tenor_weeks FROM md_risk_free").fetchone()
        self.assertEqual(row, (rfk.SERIES, "USD", "SIMPLE_YIELD", 365, "PERCENT", 2, rfk.CAL_ID, "NOT_REVISED", 13))
        self.assertEqual(sorted(r[0] for r in self.owner.execute("SELECT data_kind FROM md_file")), ["CALENDAR", "RISK_FREE"])
        self.assertEqual(self.owner.execute("SELECT kind FROM md_calendar").fetchone()[0], "RATE_PUBLICATIONS")

    def test_the_least_privilege_role_reads_it_back_and_the_port_answers_as_the_in_memory_store_does(self):
        pg = self.read()
        conventions_mem = market11_conventions(self.built.calendars)
        conventions_pg = market11_conventions(pg.calendars())
        self.assertEqual(pg.projection_digest(), self.result.projection_digest)
        self.assertEqual(pg.export().risk_free, self.built.store.export().risk_free)
        for day in (D(2025, 1, 2), D(2025, 1, 6), D(2025, 1, 7), D(2025, 1, 8), D(2024, 12, 31)):
            self.assertEqual(pg.risk_free_on(USD, day, conventions_pg), self.built.store.risk_free_on(USD, day, conventions_mem), day)
        self.assertEqual(pg.risk_free_series(USD, D(2025, 1, 1), D(2025, 1, 31)), self.built.store.risk_free_series(USD, D(2025, 1, 1), D(2025, 1, 31)))
        self.assertEqual(pg.risk_free_on(CurrencyCode("HKD"), D(2025, 1, 6), conventions_pg).outcome.value, "NOT_IN_RELEASE")
        self.assertEqual([r.source_id for r in pg.source_registry_records()], [rfk.CAL_SOURCE, rfk.SOURCE_ID])  # the risk-free source is pinned like any served source

    def test_an_idempotent_reprojection_is_a_no_op_and_the_app_role_cannot_write(self):
        again = mds.write_release(self.owner, self.release, self.built.manifests, self.built.store.export(), self.built.calendars)
        self.assertFalse(again.created)
        self.assertEqual(again.projection_digest, self.result.projection_digest)
        for sql in ("INSERT INTO md_risk_free_point (release_id, risk_free_ordinal, point_ordinal, value_date, rate) VALUES ('%s', 0, 99, '2025-02-01', 1)" % self.release.release_id,
                    "UPDATE md_risk_free SET provider = provider", "DELETE FROM md_risk_free_point", "TRUNCATE md_risk_free"):
            with self.assertRaises(self.pg.Error, msg=sql) as cm:
                self.app.execute(sql)
            self.assertEqual(cm.exception.sqlstate, "42501", sql)

    def test_the_rows_are_append_only_and_sealed_with_their_release(self):
        for sql in ("UPDATE md_risk_free_point SET rate = rate", "DELETE FROM md_risk_free", "TRUNCATE md_risk_free_point"):
            with self.assertRaises(self.pg.Error, msg=sql) as cm:
                self.owner.execute(sql)
            self.assertEqual(cm.exception.diag.constraint_name, "md_append_only", sql)
        with self.assertRaises(self.pg.Error) as cm:  # the release is committed: nothing can be added to it, by anyone
            self.owner.execute("INSERT INTO md_risk_free_point (release_id, risk_free_ordinal, point_ordinal, value_date, rate) VALUES (%s, 0, 99, '2025-02-01', 1)", (self.release.release_id,))
        self.assertEqual(cm.exception.diag.constraint_name, "md_release_sealed")

    def in_open_release(self, body):
        """Run `body(release_id)` inside a transaction that creates a release (so its child rows are accepted) and roll it back."""
        rid = uuid.uuid4().hex + uuid.uuid4().hex
        sha = uuid.uuid4().hex + uuid.uuid4().hex
        with self.assertRaises(_Rollback):
            with self.owner.transaction():
                self.owner.execute(
                    "INSERT INTO md_file (file_sha256, source_id, data_kind, usage_scope, retrieval_time, declared_adjustment, market, manifest) "
                    "VALUES (%s, 'synthetic.riskfree', 'RISK_FREE', 'SYNTHETIC_TEST', now(), 'RAW', NULL, '{}'::jsonb)", (sha,))
                self.owner.execute(
                    "INSERT INTO md_release (release_id, name, convention_set_id, release_content, contains_synthetic, projection_digest) "
                    "VALUES (%s, 'n', 'c', %s::jsonb, true, %s)", (rid, '{"release_id": "%s", "convention_set_id": "c"}' % rid, "0" * 64))
                self.owner.execute("INSERT INTO md_release_file (release_id, file_sha256, ordinal, has_fx_window) VALUES (%s, %s, 0, false)", (rid, sha))
                body(rid, sha)
                raise _Rollback()

    def series_sql(self, rid, sha, **kw):
        row = dict(release_id=rid, risk_free_ordinal=0, file_sha256=sha, source_id="synthetic.riskfree", independence_group="g", series_id="S", name="n", provider="p", currency="USD",
                   instrument="i", tenor_weeks=13, quote_type="SIMPLE_YIELD", day_count_basis=365, unit="PERCENT", decimals_published=2, date_semantics="d", calendar_id="C",
                   revision_policy="NOT_REVISED", license_status="SYNTHETIC_TEST", display_permitted=False, delay_status="END_OF_DAY", lineage="{}")
        row.update(kw)
        cols = list(row)
        self.owner.execute("INSERT INTO md_risk_free (%s) VALUES (%s)" % (", ".join(cols), ", ".join("%s" if c != "lineage" else "%s::jsonb" for c in cols)), [row[c] for c in cols])

    def test_the_database_refuses_what_the_contract_refuses(self):
        def expect(constraint, **kw):
            def body(rid, sha):
                with self.assertRaises(self.pg.errors.CheckViolation, msg=str(kw)) as cm:
                    with self.owner.transaction():
                        self.series_sql(rid, sha, **kw)
                self.assertEqual(cm.exception.diag.constraint_name, constraint, str(kw))
            self.in_open_release(body)

        expect("md_risk_free_quote_type_check", quote_type="CONTINUOUS")
        expect("md_risk_free_unit_check", unit="BASIS_POINTS")
        expect("md_risk_free_revision_policy_check", revision_policy="SOMETIMES")
        expect("md_risk_free_day_count_basis_check", day_count_basis=364)
        expect("md_risk_free_tenor_weeks_check", tenor_weeks=0)
        expect("md_risk_free_decimals_published_check", decimals_published=13)
        expect("md_risk_free_currency_check", currency="usd")
        expect("md_risk_free_series_id_check", series_id=" ")
        expect("md_risk_free_discount_is_act360", quote_type="BANK_DISCOUNT", day_count_basis=365)
        expect("md_risk_free_display_needs_license", display_permitted=True)

        def points(rid, sha):
            self.series_sql(rid, sha)
            for kw, constraint in (({"rate": "1E30"}, "md_risk_free_point_value_bounds"), ({"rate": "0.1234567890123456789012345"}, "md_risk_free_point_value_bounds"),
                                   ({"value_date": "infinity"}, "md_risk_free_point_date_bounds"), ({"term_days": 0}, "md_risk_free_point_term_days_check")):
                row = dict(release_id=rid, risk_free_ordinal=0, point_ordinal=0, value_date="2025-01-02", rate="1", term_days=None)
                row.update(kw)
                with self.assertRaises(self.pg.errors.CheckViolation, msg=str(kw)) as cm:
                    with self.owner.transaction():
                        self.owner.execute("INSERT INTO md_risk_free_point (release_id, risk_free_ordinal, point_ordinal, value_date, rate, term_days) VALUES (%s, %s, %s, %s, %s, %s)",
                                           [row[k] for k in ("release_id", "risk_free_ordinal", "point_ordinal", "value_date", "rate", "term_days")])
                self.assertEqual(cm.exception.diag.constraint_name, constraint, str(kw))
                self.assertIsInstance(mds.translate_error(cm.exception), mds.MarketDataValueOutOfRangeError if constraint.endswith("_bounds") else mds.MarketDataRuleRejectedError)
            # a good point in the same release is accepted (the checks above are not refusing everything)
            self.owner.execute("INSERT INTO md_risk_free_point (release_id, risk_free_ordinal, point_ordinal, value_date, rate) VALUES (%s, 0, 0, '2025-01-02', -0.5)", (rid,))

        self.in_open_release(points)

    def test_a_series_needs_its_file_in_the_release_and_a_point_needs_its_series(self):
        def body(rid, sha):
            with self.assertRaises(self.pg.errors.ForeignKeyViolation):
                with self.owner.transaction():
                    self.series_sql(rid, "f" * 64)  # a file the release does not hold
            with self.assertRaises(self.pg.errors.ForeignKeyViolation):
                with self.owner.transaction():
                    self.owner.execute("INSERT INTO md_risk_free_point (release_id, risk_free_ordinal, point_ordinal, value_date, rate) VALUES (%s, 7, 0, '2025-01-02', 1)", (rid,))

        self.in_open_release(body)

    def test_a_release_written_before_the_migration_has_the_same_digest_after_it(self):
        """Migrate through 0015, project the synthetic world, apply 0016-0019, read it back: the stored digest is still reproduced, byte for byte."""
        schema = "finweb_it_rfc_" + uuid.uuid4().hex[:10]
        owner = connection.connect(connection.conninfo_from_env(__import__("os").environ), autocommit=True)
        self.addCleanup(owner.close)
        try:
            owner.execute('CREATE SCHEMA "%s"' % schema)
            owner.execute('SET search_path TO "%s"' % schema)
            migrator.apply_migrations(owner, migrator.load_migrations()[:15])
            w = x.build_world("mock")
            self.addCleanup(w.close)
            pk.insert_identity(owner, w.ident)
            from unittest import mock  # noqa: PLC0415

            before_tables = tuple(t for t in mds.MD_TABLES if "risk_free" not in t)  # the tables that existed when this release was written (the 0015 schema has no risk-free table)
            with mock.patch.object(mds, "MD_TABLES", before_tables):
                before = mds.write_release(owner, w.release, w.built.manifests, w.store.export(), w.built.calendars)
            self.assertEqual(migrator.apply_migrations(owner), ["0016_risk_free_kind.sql", "0017_web_accounts_and_saved_sandboxes.sql", "0018_web_portfolio_revisions.sql", "0019_web_csv_import.sql"])
            after = mds.read_release(owner, w.release.release_id, exchange_of=w.ident.exchange_mic, registry=x.k.registry_for(w.store))
            self.assertEqual(after.projection_digest(), before.projection_digest)
            self.assertEqual(after.export().risk_free, ())
            counts = dict(mds.row_counts(owner, w.release.release_id))
            self.assertEqual((counts["md_risk_free"], counts["md_risk_free_point"]), (0, 0))
        finally:
            owner.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % schema)
            left = owner.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s", (schema,)).fetchall()
            self.assertEqual(left, [])


class _Rollback(Exception):
    pass


if __name__ == "__main__":
    unittest.main()
