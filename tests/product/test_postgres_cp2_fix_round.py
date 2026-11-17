"""CP2 fix round, the findings that need a real server (opt-in; variables as in `test_postgres_market_data_store.py`):

    C2-5   the read path cannot be shadowed with TEMP tables by `finweb_app`
    C2-6   `read_release` refuses a stored release whose content is not the release its key names (and migration 0012)

The OWNER role migrates and projects a release in a disposable `finweb_it_md_*` schema; the APP role reads under exactly
the production grants. Every schema is dropped at the end. All data is synthetic; expected values are hand-written.
"""

import dataclasses
import datetime
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402
import pg_market_kit as pk  # noqa: E402

k = x.k
c = x.c

from marketdata import contracts  # noqa: E402,F401
from persistence import market_data_store as mds  # noqa: E402

D = datetime.date
_SKIP = pk.skip_reason()

#: every md_* table `read_release` reads: the shadowing probe makes a TEMP copy of each
READ_TABLES = ("md_release", "md_release_file", "md_quote", "md_fx_rate", "md_corporate_action", "md_benchmark",
               "md_benchmark_point", "md_adjusted_quote", "md_calendar", "md_series_exclusion")


@unittest.skipIf(bool(_SKIP), _SKIP)
class ReadPathHardeningDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg  # noqa: PLC0415

        cls.pg = psycopg
        cls.db = pk.PgSchema().open()
        cls.addClassCleanup(cls.db.close)
        cls.owner = cls.db.owner
        cls.world = x.build_world("mock")
        cls.addClassCleanup(cls.world.close)
        pk.insert_identity(cls.owner, cls.world.ident)
        cls.release = cls.world.release
        cls.result = mds.write_release(cls.owner, cls.release, cls.world.built.manifests, cls.world.store.export(),
                                       cls.world.built.calendars)
        cls.aapl = x.lid(cls.world.ident, "AAPL", "XNAS")

    def app(self):
        conn = self.db.app_connection()
        self.addCleanup(conn.close)
        return conn

    def registry(self):
        return x.k.registry_for(self.world.store)  # `read_release` requires the registry in force (performance/1.12 Ruling 1.7 item 4)

    def aapl_price(self, port):
        """The AAPL close of 2025-01-03 as the port serves it (hand: the facts say 151.10)."""
        (reading,) = [r for r in port.quotes(self.aapl, D(2025, 1, 3), D(2025, 1, 3)).readings]
        return reading.observation.price

    # -- C2-5 ----------------------------------------------------------------------------------------------------------

    def shadow_everything(self, app, factor=10):
        """The reviewer's probe P3b, as the application role in its own session: copy every md_* table into pg_temp,
        multiply AAPL's price, and store in pg_temp.md_release the digest recomputed from the altered rows."""
        schema = f'"{self.db.schema}"'
        for table in READ_TABLES:
            app.execute(f"CREATE TEMP TABLE {table} AS SELECT * FROM {schema}.{table}")
        app.execute("UPDATE pg_temp.md_quote SET price = price * %s WHERE listing_id = %s", (factor, self.aapl))
        # the recomputed digest of the altered rows: read them through the TEMP shadows (an UNQUALIFIED reader would too)
        altered = self.world.store.export()
        readings = tuple(
            dataclasses.replace(r, observation=dataclasses.replace(r.observation, price=r.observation.price * factor))
            if isinstance(r.observation, c.QuoteObservation) and r.observation.listing_id == self.aapl else r
            for r in altered.readings)
        digest = mds.projection_digest(self.release, dataclasses.replace(altered, readings=readings), self.world.built.calendars)
        app.execute("UPDATE pg_temp.md_release SET projection_digest = %s WHERE release_id = %s", (digest, self.release.release_id))
        return digest

    def test_a_temp_table_shadow_in_the_application_session_cannot_alter_what_read_release_returns(self):
        app = self.app()
        honest = self.aapl_price(mds.read_release(app, self.release.release_id, exchange_of=self.world.ident.exchange_mic, registry=self.registry()))
        self.assertEqual(honest, Decimal("151.10"))  # hand: AAPL closed 151.10 on 2025-01-03 in the facts
        forged_digest = self.shadow_everything(app)
        self.assertNotEqual(forged_digest, self.result.projection_digest)
        # CONTROL: the shadow IS effective in this session. An unqualified reader sees the altered row, which is exactly
        # what `read_release` returned (AAPL 1511.0000) before the reads were schema-qualified
        seen = app.execute("SELECT price FROM md_quote WHERE listing_id = %s AND value_date = %s", (self.aapl, D(2025, 1, 3))).fetchone()[0]
        self.assertEqual(seen, Decimal("1511.00"))
        shadowed_digest = app.execute("SELECT projection_digest FROM md_release WHERE release_id = %s", (self.release.release_id,)).fetchone()[0]
        self.assertEqual(shadowed_digest, forged_digest)
        # THE FIX: the same session, the same release, and the read returns the honest rows and the honest digest
        port = mds.read_release(app, self.release.release_id, exchange_of=self.world.ident.exchange_mic, registry=self.registry())
        self.assertEqual(self.aapl_price(port), Decimal("151.10"))
        self.assertEqual(port.projection_digest(), self.result.projection_digest)
        self.assertEqual(port.release_id(), self.release.release_id)

    def test_putting_pg_temp_first_in_the_search_path_does_not_help_either(self):
        app = self.app()
        self.shadow_everything(app)
        app.execute('SET search_path TO pg_temp, "%s"' % self.db.schema)  # an explicit pg_temp FIRST
        self.assertEqual(mds.pinned_schema(app), self.db.schema)
        port = mds.read_release(app, self.release.release_id, exchange_of=self.world.ident.exchange_mic, registry=self.registry())
        self.assertEqual(self.aapl_price(port), Decimal("151.10"))

    def test_a_search_path_with_no_non_temporary_schema_fails_closed(self):
        app = self.app()
        app.execute("SET search_path TO pg_temp")
        with self.assertRaises(mds.MarketDataStoreError):
            mds.pinned_schema(app)
        with self.assertRaises(mds.MarketDataStoreError):
            mds.read_release(app, self.release.release_id, registry=self.registry())

    # -- C2-6 ----------------------------------------------------------------------------------------------------------

    def insert_release_row(self, key, release, digest=None):
        self.owner.execute(
            "INSERT INTO md_release (release_id, name, convention_set_id, release_content, contains_synthetic, projection_digest) "
            "VALUES (%s, %s, %s, %s::jsonb, true, %s)",
            (key, release.name, release.convention_set_id, json.dumps(json.loads(release.to_json())),
             digest or self.result.projection_digest))

    def test_migration_0012_refuses_a_new_row_whose_content_is_another_release_and_is_not_valid_for_old_rows(self):
        convalidated, definition = self.owner.execute(
            "SELECT convalidated, pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'md_release_key_matches_content' "
            "AND conrelid = 'md_release'::regclass").fetchone()
        self.assertFalse(convalidated)  # NOT VALID: an upgrade over a pre-0012 release can never fail on this file
        self.assertIn("release_content", definition)
        with self.assertRaises(self.pg.Error) as cm:
            self.insert_release_row("9" * 64, self.release)  # the reviewer's probe: key 999...9 holding the mock release
        self.assertEqual(cm.exception.diag.constraint_name, "md_release_key_matches_content")
        self.assertIsInstance(mds.translate_error(cm.exception), mds.ReleaseKeyMismatchError)
        self.assertEqual(self.owner.execute("SELECT count(*) FROM md_release WHERE release_id = %s", ("9" * 64,)).fetchone()[0], 0)

    def test_read_release_refuses_content_that_is_not_the_release_its_key_names_even_without_the_check(self):
        scratch = pk.PgSchema().open()
        self.addCleanup(scratch.close)
        pk.insert_identity(scratch.owner, self.world.ident)
        mds.write_release(scratch.owner, self.release, self.world.built.manifests, self.world.store.export(), self.world.built.calendars)
        # a row written before 0012 (or by an owner who dropped the CHECK) is read-side checked: drop it in THIS scratch schema
        scratch.owner.execute("ALTER TABLE md_release DROP CONSTRAINT md_release_key_matches_content")
        scratch.owner.execute(
            "INSERT INTO md_release (release_id, name, convention_set_id, release_content, contains_synthetic, projection_digest) "
            "SELECT %s, name, convention_set_id, release_content, contains_synthetic, projection_digest FROM md_release WHERE release_id = %s",
            ("9" * 64, self.release.release_id))
        app = scratch.app_connection()
        self.addCleanup(app.close)
        with self.assertRaises(mds.ReleaseKeyMismatchError) as cm:
            mds.read_release(app, "9" * 64, exchange_of=self.world.ident.exchange_mic, registry=self.registry())
        self.assertIn(self.release.release_id, str(cm.exception))  # it says whose content it found
        # (the genuine row still reads, so the refusal is specific to the mismatch)
        self.assertEqual(mds.read_release(app, self.release.release_id, registry=self.registry()).release_id(), self.release.release_id)

    def test_read_release_refuses_a_release_whose_file_rows_are_not_the_files_it_names(self):
        scratch = pk.PgSchema().open()
        self.addCleanup(scratch.close)
        other = dataclasses.replace(self.release, name="no-file-rows")  # a different release id, a consistent key and content
        scratch.owner.execute(
            "INSERT INTO md_release (release_id, name, convention_set_id, release_content, contains_synthetic, projection_digest) "
            "VALUES (%s, %s, %s, %s::jsonb, true, %s)",
            (other.release_id, other.name, other.convention_set_id, json.dumps(json.loads(other.to_json())),
             self.result.projection_digest))  # ... but NO md_release_file rows: the release names files it does not hold
        app = scratch.app_connection()
        self.addCleanup(app.close)
        with self.assertRaises(mds.ReleaseKeyMismatchError):
            mds.read_release(app, other.release_id, registry=self.registry())


@unittest.skipIf(bool(_SKIP), _SKIP)
class FxSeriesExclusionDbTests(unittest.TestCase):
    """Migration 0013 (market-data/1.7 Test V0-FX): an FX series exclusion has no listing, only a currency. It projects, reads
    back as the app role with the same digest, and the lookup carries the same lineage as the in-memory store."""

    def test_an_excluded_fx_series_round_trips_through_postgres_with_the_same_digest_and_lineage(self):
        import test_cp2_closing_round as cr  # noqa: PLC0415
        from marketdata.market11 import market11_conventions  # noqa: PLC0415

        built, ident, release, manifests, tmp = cr.build_variant(ecb_rows=cr.shifted_rows(), ecb_dates=cr.ECB_DATES)
        self.addCleanup(tmp.cleanup)
        db = pk.PgSchema().open()
        self.addCleanup(db.close)
        pk.insert_identity(db.owner, ident)
        result = mds.write_release(db.owner, release, built.manifests, built.store.export(), built.calendars)
        stored = db.owner.execute("SELECT currency, listing_id, test FROM md_series_exclusion ORDER BY exclusion_ordinal").fetchall()
        self.assertEqual(sorted(r[0] for r in stored if r[1] is None), ["CNY", "HKD", "USD"])
        self.assertEqual({r[2] for r in stored if r[1] is None}, {"V0_FX_OFF_CALENDAR"})
        with self.assertRaises(self.pg_error()):  # exactly one of listing and currency: the CHECK of 0013
            db.owner.execute("INSERT INTO md_series_exclusion (release_id, exclusion_ordinal, listing_id, file_sha256, test, reason, "
                             "currency) SELECT release_id, 99, NULL, file_sha256, 't', 'r', NULL FROM md_series_exclusion LIMIT 1")
        app = db.app_connection()
        self.addCleanup(app.close)
        port = mds.read_release(app, release.release_id, exchange_of=ident.exchange_mic, registry=x.k.registry_for(built.store))
        self.assertEqual(port.projection_digest(), result.projection_digest)
        conv = market11_conventions(port.calendars())
        a = port.fx_on(k.EUR, k.USD, D(2025, 1, 6), conv)
        b = built.store.fx_on(k.EUR, k.USD, D(2025, 1, 6), market11_conventions(built.calendars))
        self.assertEqual((a.outcome, a.rate, a.lineage_notes), (b.outcome, b.rate, b.lineage_notes))
        self.assertTrue(any(n.startswith("V0_FX_OFF_CALENDAR") for n in a.lineage_notes))

    @staticmethod
    def pg_error():
        import psycopg  # noqa: PLC0415

        return psycopg.Error


if __name__ == "__main__":
    unittest.main()
