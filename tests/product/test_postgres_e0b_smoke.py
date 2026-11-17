"""E0b — PostgreSQL protocol / driver smoke test (PD-0021 §3.5; Tech Plan §13.G).

Separate from E0 (`test_postgres_connectivity_preflight.py`, transport only,
unchanged). E0b verifies, through the real driver (psycopg 3):

  1. a driver-level connection (authentication and the wire protocol work);
  2. the actual server and its version (major 16 or 17; the string is recorded);
  3. application-role access: what the connecting role is and can do;
  4. rollback: an insert that is rolled back is not visible afterwards;
  5. the exact Decimal <-> NUMERIC round trip (scale and digits preserved).

**Least privilege is NOT proven here.** As of this test the connecting role
(`finweb_dev`) owns the database, so it can create schemas and objects. That is
a development role; the production application role (SELECT/INSERT on the
ledger only, plus USAGE on its sequence) has not been provisioned. The access
test records the role's actual attributes so the gap is visible, and asserts
only what this test itself needs.

Opt-in and isolation: same variables as the ledger integration tests
(`FINWEB_PG_INTEGRATION=1`, `FINWEB_PG_SOCKET` or `FINWEB_PG_HOST`+
`FINWEB_PG_PORT`, `FINWEB_PG_DATABASE`, `FINWEB_PG_USER`; password via libpq).
Skipped by default and when `psycopg` is missing. The test creates one
disposable schema `finweb_e0b_<random>` and drops it; it touches no other
object and no other database, and creates or alters no role.

    FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 \\
    FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev \\
        uv run --no-cache --no-sync --frozen --offline python -m unittest \\
        discover -s tests/product -t . -p 'test_postgres_e0b_smoke.py' -v
"""

import importlib.util
import os
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from persistence import connection  # noqa: E402

_MISSING = connection.missing_env_vars(os.environ)
if _MISSING:
    _SKIP = "E0b is opt-in; set: " + "; ".join(_MISSING)
elif importlib.util.find_spec("psycopg") is None:
    _SKIP = "psycopg is not installed (owner runs `uv sync --python 3.12`)"
else:
    _SKIP = ""


def _record(line: str) -> None:
    """Evidence line on stderr, visible with -v or on failure."""
    sys.stderr.write("E0B " + line + "\n")


@unittest.skipIf(bool(_SKIP), _SKIP)
class E0bSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg  # noqa: PLC0415

        cls.pg = psycopg
        cls.conn = connection.connect(
            connection.conninfo_from_env(os.environ), autocommit=True
        )
        cls.schema = "finweb_e0b_" + uuid.uuid4().hex[:12]
        cls.addClassCleanup(cls._cleanup)
        cls.conn.execute('CREATE SCHEMA "%s"' % cls.schema)
        cls.conn.execute('SET search_path TO "%s"' % cls.schema)
        cls.conn.execute("CREATE TABLE e0b_numbers (k integer PRIMARY KEY, x numeric)")

    @classmethod
    def _cleanup(cls):
        try:
            cls.conn.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % cls.schema)
        finally:
            cls.conn.close()

    # 1 + 2 -----------------------------------------------------------------------

    def test_driver_connection_and_server_identity(self):
        self.assertEqual(self.conn.execute("SELECT 1").fetchone()[0], 1)
        number = self.conn.info.server_version  # e.g. 170011
        version_string = self.conn.execute("SHOW server_version").fetchone()[0]
        banner = self.conn.execute("SELECT version()").fetchone()[0]
        _record("server_version=%s (%d) banner=%s driver=psycopg %s" % (
            version_string, number, banner, self.pg.__version__))
        self.assertIn(number // 10000, (16, 17), banner)
        self.assertTrue(banner.startswith("PostgreSQL"), banner)
        self.assertEqual(self.conn.execute("SELECT current_database()").fetchone()[0],
                         os.environ[connection.DATABASE_VAR])

    # 3 -----------------------------------------------------------------------------

    def test_application_role_access(self):
        who = self.conn.execute("SELECT current_user").fetchone()[0]
        self.assertEqual(who, os.environ[connection.USER_VAR])
        superuser, createrole, createdb = self.conn.execute(
            "SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles "
            "WHERE rolname = current_user").fetchone()
        owner = self.conn.execute(
            "SELECT pg_get_userbyid(datdba) FROM pg_database "
            "WHERE datname = current_database()").fetchone()[0]
        can_connect, can_create, can_temp = self.conn.execute(
            "SELECT has_database_privilege(current_database(), 'CONNECT'),"
            " has_database_privilege(current_database(), 'CREATE'),"
            " has_database_privilege(current_database(), 'TEMPORARY')").fetchone()
        _record("role=%s superuser=%s createrole=%s createdb=%s database_owner=%s "
                "connect=%s create=%s temp=%s" % (
                    who, superuser, createrole, createdb, owner, can_connect, can_create,
                    can_temp))
        _record("NOTE: this is the development owner role, NOT the production "
                "least-privilege application role (not yet provisioned)")
        # What the ledger tests need and this role must be able to do:
        self.assertTrue(can_connect)
        self.assertTrue(can_create)  # create the disposable schema
        # Working in the disposable schema: DDL, insert, select, and a sequence draw.
        self.conn.execute("CREATE TABLE e0b_access (id integer)")
        self.conn.execute("INSERT INTO e0b_access VALUES (1)")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM e0b_access").fetchone()[0], 1)
        self.conn.execute("CREATE SEQUENCE e0b_seq")
        self.assertEqual(self.conn.execute("SELECT nextval('e0b_seq')").fetchone()[0], 1)
        # The role must not be a superuser for the production claim to mean anything;
        # recorded above rather than asserted, because this dev role may legitimately be.
        # Privilege enforcement itself works: revoking the owner's own SELECT is honoured.
        self.conn.execute("REVOKE SELECT ON e0b_access FROM CURRENT_USER")
        if not superuser:
            with self.assertRaises(self.pg.errors.InsufficientPrivilege):
                self.conn.execute("SELECT * FROM e0b_access")
        self.conn.execute("GRANT SELECT ON e0b_access TO CURRENT_USER")

    # 4 -----------------------------------------------------------------------------

    def test_rolled_back_insert_is_not_visible(self):
        # (a) an exception inside a transaction block rolls the insert back
        with self.assertRaises(RuntimeError):
            with self.conn.transaction():
                self.conn.execute("INSERT INTO e0b_numbers VALUES (1, 1.5)")
                self.assertEqual(
                    self.conn.execute("SELECT count(*) FROM e0b_numbers WHERE k = 1"
                                      ).fetchone()[0], 1)  # visible inside the transaction
                raise RuntimeError("force rollback")
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM e0b_numbers WHERE k = 1").fetchone()[0], 0)

        # (b) explicit rollback on a non-autocommit connection, seen from a second session
        other = connection.connect(connection.conninfo_from_env(os.environ))
        self.addCleanup(other.close)
        other.execute('SET search_path TO "%s"' % self.schema)
        other.commit()  # SET is transactional: commit it, or the rollback below undoes it too
        other.execute("INSERT INTO e0b_numbers VALUES (2, 2.5)")
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM e0b_numbers WHERE k = 2").fetchone()[0], 0,
            "uncommitted rows must not be visible to another session")
        other.rollback()
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM e0b_numbers WHERE k = 2").fetchone()[0], 0)

        # control: a committed insert IS visible
        other.execute("INSERT INTO e0b_numbers VALUES (3, 3.5)")
        other.commit()
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM e0b_numbers WHERE k = 3").fetchone()[0], 1)

    # 5 -----------------------------------------------------------------------------

    _PLAIN = (
        "0", "0.00", "1", "1.10", "1.100000", "0.5000", "-0.0100", "100", "100.00",
        "0.000000000000000000000000001",
        "123456789012345678901234567890.123456789012345678901234567890",  # 60 digits
        "-123456789012345678901234567890.123456789012345678901234567890",
        "999999999999999999999999999999999999999999999999999999999999",     # 60 digits
        "0." + "0" * 58 + "1",                                              # 59 decimals
    )
    _EXPONENT = ("1E+3", "1.5E+2", "1E-10", "1.25E-7", "1E+30", "-2.5E+1", "0E+2")

    def _round_trip(self, key, value):
        self.conn.execute("INSERT INTO e0b_numbers VALUES (%s, %s)", (key, value))
        back, as_text = self.conn.execute(
            "SELECT x, x::text FROM e0b_numbers WHERE k = %s", (key,)).fetchone()
        self.assertIsInstance(back, Decimal)
        return back, as_text

    def test_decimal_numeric_round_trip_preserves_value_digits_and_scale(self):
        for index, text in enumerate(self._PLAIN, start=1000):
            value = Decimal(text)
            back, as_text = self._round_trip(index, value)
            self.assertEqual(back, value, text)
            self.assertEqual(str(back), str(value), text)  # digits and trailing zeros
            self.assertEqual(as_text, format(value, "f"), text)  # server's own rendering

    def test_decimal_numeric_round_trip_of_exponent_forms_is_numerically_exact(self):
        for index, text in enumerate(self._EXPONENT, start=2000):
            value = Decimal(text)
            back, as_text = self._round_trip(index, value)
            self.assertEqual(back, value, text)
            self.assertEqual(as_text, format(value, "f"), text)

    def test_numeric_is_never_a_float(self):
        value = Decimal("0.1")
        back, _ = self._round_trip(3000, value)
        self.assertEqual(back, value)
        self.assertNotEqual(back, Decimal(0.1))  # the float artefact is not what came back
        row = self.conn.execute("SELECT 0.1::numeric + 0.2::numeric").fetchone()[0]
        self.assertEqual(row, Decimal("0.3"))

    def test_numeric_holds_and_returns_non_finite_values_faithfully(self):
        # The ledger forbids these by CHECK; this only documents the wire behaviour that
        # makes those CHECKs necessary.
        for index, text in enumerate(("NaN", "Infinity", "-Infinity"), start=4000):
            back, _ = self._round_trip(index, Decimal(text))
            self.assertFalse(back.is_finite(), text)


if __name__ == "__main__":
    unittest.main()
