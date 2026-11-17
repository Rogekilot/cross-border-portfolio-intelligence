"""E0b remainder — the ledger under a least-privilege application role.

Proves that every append path works, and every forbidden operation is refused,
when the connecting role is NOT the owner: no ownership, no superuser, and only
the grants listed in `APP_GRANTS` below (that list is the production grant spec).

Opt-in (skipped by default). Needs the ledger integration variables PLUS
`FINWEB_PG_APP_USER`, the least-privilege role (e.g. `finweb_app`):

    FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 \\
    FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev \\
    FINWEB_PG_APP_USER=finweb_app \\
        uv run --no-cache --no-sync --frozen --offline python -m unittest \\
        discover -s tests/product -t . -p 'test_postgres_least_privilege.py' -v

Two kinds of connection, same database and socket: the OWNER role
(`FINWEB_PG_USER`) creates one disposable schema `finweb_lp_<random>`, runs the
migrations into it, inserts the fixture rows (users, portfolios, accounts,
listings, which the app role never writes) and grants; the APP role does the
ledger work. The owner drops the schema afterwards and the cleanup fails loudly
if it is still there. No role or database is created or altered; grants and
revokes touch only objects inside the disposable schema.
"""

import datetime
import importlib.util
import os
import sys
import threading
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from persistence import connection, ledger_store, migrator  # noqa: E402

APP_USER_VAR = "FINWEB_PG_APP_USER"

_MISSING = connection.missing_env_vars(os.environ)
if not os.environ.get(APP_USER_VAR):
    _MISSING = list(_MISSING) + [APP_USER_VAR + " (the least-privilege role, e.g. finweb_app)"]
if _MISSING:
    _SKIP = "least-privilege test is opt-in; set: " + "; ".join(_MISSING)
elif importlib.util.find_spec("psycopg") is None:
    _SKIP = "psycopg is not installed (owner runs `uv sync --python 3.12`)"
else:
    _SKIP = ""

#: The production grant spec: exactly this, inside the ledger schema, and nothing else.
#: `{schema}` and `{role}` are filled in. Why each line is needed:
#:  - USAGE on the schema: name resolution.
#:  - SELECT, INSERT on ledger_event: append; INSERT ... RETURNING / ON CONFLICT and the
#:    idempotency and event lookups read it; the BEFORE INSERT and deferred pairing
#:    triggers read it (triggers run with the caller's privileges).
#:  - SELECT on account: the BEFORE INSERT trigger looks up the account's portfolio for
#:    the per-portfolio lock and the same-portfolio check.
#:  - USAGE on the sequence: the trigger draws ledger_seq with nextval as the caller.
#:  - SELECT on portfolio (CP1D-1, CP1-C reads): `ledger_replay_store` starts every read
#:    (`current_ledger_version`, `load_events`, `replay`) by checking the portfolio exists, so
#:    "unknown portfolio" is a typed error and never an empty ledger. The one application
#:    role must be able to read what it serves. Appends do NOT need it.
#: Foreign-key checks run with the table owner's rights, so no grant on listing or app_user
#: is needed (and none on portfolio for appends). No UPDATE, DELETE, TRUNCATE, TRIGGER,
#: REFERENCES.
#:  - SELECT on the eleven md_* tables (CP2c-2, migrations 0009-0011): the application role READS the market-data
#:    projection (`persistence.market_data_store.read_release`), and the F8-B split-confirmation service reads
#:    corporate-action readings through it. It never writes there: loading a release is a privileged step (the
#:    schema owner or a loader role), and the append-only and sealed-release triggers refuse UPDATE, DELETE and
#:    TRUNCATE to every role. No grant on `listing` is needed (the listing's MIC is supplied by the caller).
MD_TABLES = (
    "md_file", "md_release", "md_release_file", "md_quote", "md_fx_rate", "md_corporate_action",
    "md_benchmark", "md_benchmark_point", "md_adjusted_quote", "md_calendar", "md_series_exclusion",
    "md_risk_free", "md_risk_free_point",  # CP4b-2, migration 0016 (risk/1.0 section 4): READ only for the application role, like every md_* table
)
APP_GRANTS = (
    'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"',
    'GRANT SELECT, INSERT ON "{schema}".ledger_event TO "{role}"',
    'GRANT SELECT ON "{schema}".account TO "{role}"',
    'GRANT SELECT ON "{schema}".portfolio TO "{role}"',
    'GRANT USAGE ON SEQUENCE "{schema}".ledger_event_ledger_seq_seq TO "{role}"',
    'GRANT SELECT ON ' + ", ".join('"{schema}".%s' % t for t in MD_TABLES) + ' TO "{role}"',
    #  - SELECT, INSERT on benchmark_selection and USAGE on its sequence (CP4b-3, migration 0015, PD-0039 D5): the user's primary-benchmark
    #    selection is USER DATA appended through the service (the insert trigger draws selection_seq as the caller) and read by the risk
    #    engine's service. Same shape as ledger_event: no UPDATE, DELETE, TRUNCATE, TRIGGER or REFERENCES; the append-only trigger refuses
    #    UPDATE, DELETE and TRUNCATE to every role regardless.
    'GRANT SELECT, INSERT ON "{schema}".benchmark_selection TO "{role}"',
    'GRANT USAGE ON SEQUENCE "{schema}".benchmark_selection_seq_seq TO "{role}"',
)

#: NEVER GRANT CREATE (CP2 final round, review section 26). The application role must never hold CREATE on ANY schema
#: or on the database. `persistence.market_data_store.pinned_schema` resolves the md_* schema from the session's own
#: search_path (skipping pg_temp), so the read path is only as safe as the set of schemas the role can write: with no
#: CREATE it can steer a read to a schema, never plant tables in one. (TEMPORARY, which gives pg_temp, is covered by the
#: schema-qualified reads.) `test_the_application_role_holds_no_create_anywhere` asserts it for every schema and the
#: database, so a deployment grant that breaks the assumption fails the suite.
NEVER_GRANT = ("CREATE ON ANY SCHEMA", "CREATE ON DATABASE")

#: Defence in depth for PRODUCTION, documented and NOT applied by these tests (nor by any
#: migration: it is a database-level grant owned by whoever provisions the database, and
#: this project must not revoke anything at database level on finweb_dev). The ledger
#: triggers are immune to TEMP-object shadowing WITHOUT it (migration 0004 pins every
#: trigger function's search_path, and `test_the_fix_does_not_rely_on_revoking_temporary`
#: proves the attacks fail while the app role still holds TEMPORARY), but the application
#: role has no need to create temporary objects, so remove the default:
PRODUCTION_HARDENING = (
    'REVOKE TEMPORARY ON DATABASE "<database>" FROM PUBLIC',
)

#: SCHEMA RENAME WARNING (R2-3), next to the REVOKE above because it is the same risk.
#: Migration 0004/0006 pin each trigger function's search_path to the ledger schema BY NAME.
#: Renaming that schema (ALTER SCHEMA ... RENAME) or restoring a dump into a different schema
#: name leaves the pins pointing at the old name. In-database guard (migration 0006): the
#: trigger functions compare their pinned schema with the schema of the table that fired
#: them and FAIL CLOSED (`ledger_event_search_path_pin_stale`, 23514) before touching any
#: table, so a rename cannot silently re-open the TEMP-shadow bypass; it makes appends fail
#: until the owner re-pins every function for the new name:
#:     ALTER FUNCTION "<new_schema>".<fn> SET search_path = "<new_schema>", pg_temp
#: for each function in the 0006 pin list. The REVOKE above remains the belt to this brace.
SCHEMA_RENAME_WARNING = "see the comment above: re-pin every ledger function after a rename"

#: The exact table privileges the production role must hold, and nothing else (CP1D-1).
EXPECTED_TABLE_PRIVILEGES = {("ledger_event", "SELECT"), ("ledger_event", "INSERT"),
                             ("account", "SELECT"), ("portfolio", "SELECT"),
                             ("benchmark_selection", "SELECT"), ("benchmark_selection", "INSERT")} | {(t, "SELECT") for t in MD_TABLES}


def table_privileges(conn, schema, role):
    """Every (table, privilege) `role` holds on the tables of `schema`, from the catalog."""
    tables = [r[0] for r in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = %s", (schema,))]
    held = set()
    for table in tables:
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
            if conn.execute("SELECT has_table_privilege(%s, %s, %s)",
                            (role, '"%s"."%s"' % (schema, table), privilege)).fetchone()[0]:
                held.add((table, privilege))
    return held


USD = CurrencyCode("USD")
HKD = CurrencyCode("HKD")
D = datetime.date(2025, 4, 2)

_USER = uuid.UUID("a1111111-1111-1111-1111-111111111111")
_P1 = uuid.uuid4()  # random per process (R3-4): no shared portfolio across concurrent runs
_P2 = uuid.uuid4()
_A1 = uuid.UUID("a3333333-3333-3333-3333-333333333331")
_A2 = uuid.UUID("a3333333-3333-3333-3333-333333333332")
_A3 = uuid.UUID("a3333333-3333-3333-3333-333333333333")
_A4 = uuid.UUID("a3333333-3333-3333-3333-333333333334")
_A5 = uuid.UUID("a3333333-3333-3333-3333-333333333335")
_A6 = uuid.UUID("a3333333-3333-3333-3333-333333333336")
_A7 = uuid.UUID("a3333333-3333-3333-3333-333333333337")
_B1 = uuid.UUID("a3333333-3333-3333-3333-333333333339")
_ISSUER = uuid.UUID("b1111111-1111-1111-1111-111111111111")
_INSTR = uuid.UUID("b2222222-2222-2222-2222-222222222222")
_L1 = uuid.UUID("b3333333-3333-3333-3333-333333333331")


def usd(x):
    return Money(Decimal(x), USD)


@unittest.skipIf(bool(_SKIP), _SKIP)
class LeastPrivilegeTests(unittest.TestCase):
    counter = 0

    @classmethod
    def setUpClass(cls):
        import psycopg  # noqa: PLC0415

        cls.pg = psycopg
        env = os.environ
        cls.app_role = env[APP_USER_VAR]
        cls.schema = "finweb_lp_" + uuid.uuid4().hex[:12]
        cls.owner = connection.connect(connection.conninfo_from_env(env), autocommit=True)
        cls.addClassCleanup(cls._cleanup)
        cls.app_conninfo = connection.build_conninfo(
            dbname=env[connection.DATABASE_VAR], user=cls.app_role,
            socket=env.get(connection.SOCKET_VAR) or None,
            host=env.get(connection.HOST_VAR) or None,
            port=env.get(connection.PORT_VAR) or None,
        )
        # -- as the owner: schema, migrations, fixtures, grants --------------------------
        o = cls.owner
        o.execute('CREATE SCHEMA "%s"' % cls.schema)
        o.execute('SET search_path TO "%s"' % cls.schema)
        migrator.apply_migrations(o)
        o.execute("INSERT INTO app_user VALUES (%s)", (_USER,))
        o.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (_P1, _USER))
        o.execute("INSERT INTO portfolio VALUES (%s, %s, 'HKD')", (_P2, _USER))
        for acc, p in ((_A1, _P1), (_A2, _P1), (_A3, _P1), (_A4, _P1), (_A5, _P1),
                         (_A6, _P1), (_A7, _P1), (_B1, _P2)):
            o.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (acc, p))
        o.execute("INSERT INTO issuer VALUES (%s, 'Issuer', NULL)", (_ISSUER,))
        o.execute("INSERT INTO instrument VALUES (%s, %s, 'COMMON_STOCK')", (_INSTR, _ISSUER))
        o.execute(
            "INSERT INTO listing VALUES (%s, %s, 'XHKG', 'HKEX', 'H', 'HKD', NULL, true)",
            (_L1, _INSTR))
        for statement in APP_GRANTS:
            o.execute(statement.format(schema=cls.schema, role=cls.app_role))
        cls.app = cls.new_app_connection()

    @classmethod
    def new_app_connection(cls, autocommit=True):
        conn = connection.connect(cls.app_conninfo, autocommit=autocommit)
        cls.addClassCleanup(conn.close)
        conn.execute('SET search_path TO "%s"' % cls.schema)
        if not autocommit:
            conn.commit()
        return conn

    @classmethod
    def _cleanup(cls):
        try:
            cls.owner.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % cls.schema)
            left = cls.owner.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = %s", (cls.schema,)).fetchall()
            assert left == [], "disposable schema was not dropped: %r" % (left,)
        finally:
            cls.owner.close()

    # -- helpers ------------------------------------------------------------------------

    def eid(self):
        type(self).counter += 1
        return uuid.UUID(int=(0xE2 << 120) + type(self).counter)

    def event(self, kind, account=_A1, currency=USD, date=D, **kw):
        return LedgerEvent(self.eid(), account, kind, date, currency, **kw)

    def buy(self, account=_A1, **kw):
        base = dict(listing_id=_L1, quantity=Decimal("200"),
                    amount=Money(Decimal("7000"), HKD))
        base.update(kw)
        return self.event(EventType.BUY, account=account, currency=HKD, **base)

    def conv(self, account=_A1, bought="7780", **kw):
        base = dict(amount=usd("1000"), bought_amount=Money(Decimal(bought), HKD))
        base.update(kw)
        return self.event(EventType.CURRENCY_CONVERSION, account=account, **base)

    def reversal(self, target, account=_A1, currency=USD):
        return self.event(EventType.REVERSAL, account=account, currency=currency,
                          reverses_event_id=target, date=datetime.date(2025, 4, 10))

    def expect_denied(self, sql, params=None, conn=None):
        with self.assertRaises(self.pg.Error) as cm:
            (conn or self.app).execute(sql, params)
        self.assertEqual(cm.exception.sqlstate, "42501", str(cm.exception))

    # -- the role really is least-privilege ------------------------------------------------

    def test_the_role_holds_exactly_the_granted_privileges(self):
        role = self.app_role
        attrs = self.owner.execute(
            "SELECT rolsuper, rolcreaterole, rolcreatedb, rolinherit FROM pg_roles "
            "WHERE rolname = %s", (role,)).fetchone()
        self.assertEqual(attrs[:3], (False, False, False))
        has = lambda sql, *a: self.owner.execute(sql, a).fetchone()[0]  # noqa: E731
        self.assertTrue(has("SELECT has_schema_privilege(%s, %s, 'USAGE')", role, self.schema))
        self.assertFalse(has("SELECT has_schema_privilege(%s, %s, 'CREATE')", role, self.schema))
        self.assertFalse(has("SELECT has_database_privilege(%s, current_database(), 'CREATE')",
                             role))
        tables = [r[0] for r in self.owner.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s", (self.schema,))]
        self.assertIn("ledger_event", tables)
        self.assertEqual(table_privileges(self.owner, self.schema, role), EXPECTED_TABLE_PRIVILEGES)
        self.assertTrue(has("SELECT has_sequence_privilege(%s, %s, 'USAGE')", role,
                            '"%s".ledger_event_ledger_seq_seq' % self.schema))
        owner_of_table = self.owner.execute(
            "SELECT tableowner FROM pg_tables WHERE schemaname = %s AND tablename = "
            "'ledger_event'", (self.schema,)).fetchone()[0]
        self.assertNotEqual(owner_of_table, role)
        self.assertEqual(self.app.execute("SELECT current_user").fetchone()[0], role)

    # -- every append path works under the role --------------------------------------------

    def test_the_application_role_holds_no_create_anywhere(self):
        # section 26 / `NEVER_GRANT`: `pinned_schema` relies on it. Every schema of the database, system ones included,
        # and the database itself
        role = self.app_role
        schemas = [r[0] for r in self.owner.execute("SELECT nspname FROM pg_namespace")]
        self.assertIn(self.schema, schemas)
        with_create = [s for s in schemas if self.owner.execute(
            "SELECT has_schema_privilege(%s, %s, 'CREATE')", (role, s)).fetchone()[0]]
        self.assertEqual(with_create, [])
        self.assertFalse(self.owner.execute(
            "SELECT has_database_privilege(%s, current_database(), 'CREATE')", (role,)).fetchone()[0])

    def test_append_event_and_idempotent_resubmission(self):
        first = ledger_store.append_event(self.app, self.buy(source_reference="LP-1"))
        self.assertTrue(first.created)
        again = ledger_store.append_event(self.app, self.buy(source_reference="LP-1"))
        self.assertFalse(again.created)
        self.assertEqual(again.event.event_id, first.event.event_id)
        self.assertEqual(ledger_store.get_event(self.app, first.event.event_id).ledger_seq,
                         first.ledger_seq)

    def test_append_batch(self):
        results = ledger_store.append_batch(self.app, [
            self.event(EventType.DEPOSIT, amount=usd("10000")),
            self.buy(),
        ])
        self.assertTrue(all(r.created for r in results))
        self.assertLess(results[0].ledger_seq, results[1].ledger_seq)

    def test_append_internal_transfer_cash_and_security(self):
        out = self.event(EventType.TRANSFER_OUT, account=_A1, amount=usd("1000"),
                         counterparty_account_id=_A3)
        inn = self.event(EventType.TRANSFER_IN, account=_A3, amount=usd("1000"),
                         counterparty_account_id=_A1)
        r_out, r_in = ledger_store.append_internal_transfer(self.app, out, inn)
        self.assertLess(r_out.ledger_seq, r_in.ledger_seq)
        sec_out = self.event(EventType.TRANSFER_OUT, account=_A1, currency=HKD,
                             listing_id=_L1, quantity=Decimal("50"),
                             counterparty_account_id=_A3)
        sec_in = self.event(EventType.TRANSFER_IN, account=_A3, currency=HKD,
                            listing_id=_L1, quantity=Decimal("50"),
                            counterparty_account_id=_A1)
        ledger_store.append_internal_transfer(self.app, sec_out, sec_in)

    def test_a_lone_transfer_leg_is_still_refused_at_commit(self):
        lone = self.event(EventType.TRANSFER_OUT, account=_A1, amount=usd("5"),
                          counterparty_account_id=_A3)
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_event(self.app, lone)
        self.assertEqual(cm.exception.constraint_name, "ledger_event_transfer_pairing")

    def test_append_correction_of_an_ordinary_event(self):
        target = ledger_store.append_event(self.app, self.buy()).event
        replacement = self.buy(corrects_event_id=target.event_id, quantity=Decimal("210"))
        result = ledger_store.append_correction(
            self.app, self.reversal(target.event_id, currency=HKD), replacement)
        self.assertLess(result.reversal.ledger_seq, result.replacement.ledger_seq)

    def test_currency_conversion_and_its_correction(self):
        original = ledger_store.append_event(self.app, self.conv()).event
        stored = ledger_store.get_event(self.app, original.event_id).event
        self.assertEqual(stored.bought_amount, Money(Decimal("7780"), HKD))
        result = ledger_store.append_correction(
            self.app, self.reversal(original.event_id),
            self.conv(bought="7750", corrects_event_id=original.event_id))
        self.assertLess(result.reversal.ledger_seq, result.replacement.ledger_seq)
        self.assertEqual(result.replacement.event.bought_amount, Money(Decimal("7750"), HKD))

    def test_database_rules_still_apply_to_the_app_role(self):
        # snapshot rule (reads ledger_event) and same-portfolio rule (reads account)
        s = _A4  # a dedicated account: an opening event here must not affect other tests
        ledger_store.append_event(self.app, self.event(
            EventType.OPENING_CASH, account=s, amount=usd("100")))
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_event(self.app, self.event(
                EventType.DEPOSIT, account=s, amount=usd("1")))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_after_snapshot_date")
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_event(self.app, self.event(
                EventType.TRANSFER_OUT, account=_A1, amount=usd("1"),
                counterparty_account_id=_B1))
        self.assertEqual(cm.exception.constraint_name,
                         "ledger_event_counterparty_same_portfolio")

    # -- forbidden operations are refused ---------------------------------------------------

    def test_update_delete_truncate_are_refused(self):
        ledger_store.append_event(self.app, self.buy())
        self.expect_denied("UPDATE ledger_event SET quantity = quantity")
        self.expect_denied("DELETE FROM ledger_event")
        self.expect_denied("TRUNCATE ledger_event")

    def test_the_role_cannot_defeat_the_triggers_or_alter_the_schema(self):
        self.expect_denied("ALTER TABLE ledger_event DISABLE TRIGGER ALL")
        self.expect_denied("ALTER TABLE ledger_event DISABLE TRIGGER ledger_event_before_insert")
        self.expect_denied("DROP TRIGGER ledger_event_before_insert ON ledger_event")
        self.expect_denied("ALTER TABLE ledger_event ADD COLUMN extra integer")
        self.expect_denied("ALTER TABLE ledger_event DROP CONSTRAINT ledger_event_amount_positive")
        self.expect_denied("DROP TABLE ledger_event")
        self.expect_denied("CREATE OR REPLACE FUNCTION ledger_event_before_insert() "
                           "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$")
        self.expect_denied("CREATE TABLE sneaky (x integer)")
        # A GRANT without grant option is not an error in PostgreSQL (it warns "no
        # privileges were granted"), so assert it had no effect rather than that it raised.
        self.app.execute("GRANT UPDATE ON ledger_event TO PUBLIC")
        self.assertFalse(self.owner.execute(
            "SELECT has_table_privilege(%s, %s, 'UPDATE')",
            (self.app_role, '"%s".ledger_event' % self.schema)).fetchone()[0])
        self.expect_denied("UPDATE ledger_event SET quantity = quantity")
        # session_replication_role = replica would skip ordinary triggers: superuser only
        self.expect_denied("SET session_replication_role = replica")

    def test_the_role_cannot_touch_schema_migrations_or_run_the_migrator(self):
        self.expect_denied(
            "INSERT INTO schema_migrations (version, name, checksum) VALUES (99, 'x', %s)",
            ("0" * 64,))
        self.expect_denied("SELECT * FROM schema_migrations")
        with self.assertRaises(self.pg.Error) as cm:
            migrator.apply_migrations(self.app)
        self.assertEqual(cm.exception.sqlstate, "42501", str(cm.exception))
        self.assertEqual(self.owner.execute("SELECT count(*) FROM schema_migrations"
                                            ).fetchone()[0], 19)  # 0019: immutable CSV reports/source keys; prior migrations frozen

    def test_the_grants_are_each_load_bearing(self):
        """Negative controls: without the sequence or account grant the append fails
        (so neither is superfluous); they are restored afterwards."""
        seq = '"%s".ledger_event_ledger_seq_seq' % self.schema
        acct = '"%s".account' % self.schema
        role = '"%s"' % self.app_role
        for revoke, grant in (
            ("REVOKE USAGE ON SEQUENCE %s FROM %s" % (seq, role),
             "GRANT USAGE ON SEQUENCE %s TO %s" % (seq, role)),
            ("REVOKE SELECT ON %s FROM %s" % (acct, role),
             "GRANT SELECT ON %s TO %s" % (acct, role)),
        ):
            self.owner.execute(revoke)
            try:
                with self.assertRaises(self.pg.Error) as cm:
                    ledger_store.append_event(self.app, self.buy())
                self.assertEqual(cm.exception.sqlstate, "42501", revoke)
            finally:
                self.owner.execute(grant)
        self.assertTrue(ledger_store.append_event(self.app, self.buy()).created)

    def test_the_portfolio_grant_is_load_bearing_for_reads_only(self):
        """CP1D-1 negative control: without SELECT on portfolio the replay reads are refused
        (42501) while appends still work; the grant is restored afterwards."""
        from persistence import ledger_replay_store  # noqa: PLC0415

        tbl, role = '"%s".portfolio' % self.schema, '"%s"' % self.app_role
        # CP1D-3: restore EXACTLY the prior privilege state. Never grant unconditionally: that
        # would mask a missing portfolio line in APP_GRANTS for the tests that run after this one.
        before = table_privileges(self.owner, self.schema, self.app_role)
        held = ("portfolio", "SELECT") in before
        if held:
            self.owner.execute("REVOKE SELECT ON %s FROM %s" % (tbl, role))
        try:
            with self.assertRaises(self.pg.Error) as cm:
                ledger_replay_store.current_ledger_version(self.app, _P1)
            self.assertEqual(cm.exception.sqlstate, "42501")
            self.assertTrue(ledger_store.append_event(self.app, self.buy()).created)
        finally:
            if held:
                self.owner.execute("GRANT SELECT ON %s TO %s" % (tbl, role))
        self.assertEqual(table_privileges(self.owner, self.schema, self.app_role), before)
        if held:
            self.assertGreaterEqual(ledger_replay_store.current_ledger_version(self.app, _P1), 1)

    def test_cp1d3_the_exact_privilege_check_detects_a_missing_portfolio_grant(self):
        """Proof for CP1D-3, in its own disposable schema and with a LOCAL copy of the grant
        list (the real constant is untouched): without the portfolio line the role's exact
        privilege set differs from the expected one, so the exact-privilege assertion fails."""
        schema = "finweb_lpp_" + uuid.uuid4().hex[:12]
        control = connection.connect(connection.conninfo_from_env(os.environ), autocommit=True)
        self.addCleanup(control.close)
        self.addCleanup(lambda: control.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % schema))
        control.execute('CREATE SCHEMA "%s"' % schema)
        control.execute('SET search_path TO "%s"' % schema)
        migrator.apply_migrations(control)
        local = tuple(g for g in APP_GRANTS if ".portfolio" not in g)  # portfolio line removed
        self.assertEqual(len(local), len(APP_GRANTS) - 1)
        for statement in local:
            control.execute(statement.format(schema=schema, role=self.app_role))
        actual = table_privileges(control, schema, self.app_role)
        self.assertNotIn(("portfolio", "SELECT"), actual)
        with self.assertRaises(AssertionError):
            self.assertEqual(actual, EXPECTED_TABLE_PRIVILEGES)  # what the exact test asserts
        # and with the real grants the same computation matches
        for statement in APP_GRANTS:
            control.execute(statement.format(schema=schema, role=self.app_role))
        self.assertEqual(table_privileges(control, schema, self.app_role), EXPECTED_TABLE_PRIVILEGES)

    # -- the per-portfolio advisory lock works for the app role -------------------------------

    def test_per_portfolio_lock_serializes_one_portfolio_and_not_another(self):
        conn_same = self.new_app_connection()
        conn_other = self.new_app_connection()
        results = {}

        def append_on(name, conn, event):
            results[name] = ledger_store.append_event(conn, event)

        with self.app.transaction():
            held = ledger_store.append_event(self.app, self.buy(account=_A1))
            same = threading.Thread(target=append_on, args=(
                "same", conn_same, self.buy(account=_A2)))
            other = threading.Thread(target=append_on, args=(
                "other", conn_other, self.event(
                    EventType.DEPOSIT, account=_B1, currency=HKD,
                    amount=Money(Decimal("1"), HKD))))
            other.start()
            other.join(timeout=10)
            self.assertFalse(other.is_alive(), "another portfolio must not be blocked")
            same.start()
            same.join(timeout=1.0)
            self.assertTrue(same.is_alive(), "the same portfolio must wait for the lock")
        same.join(timeout=10)
        self.assertFalse(same.is_alive())
        self.assertGreater(results["same"].ledger_seq, held.ledger_seq)

    # -- CP1B-1: TEMP-object shadowing attacks (the reviewer's probes), as the app role ------

    def attacker(self, schema=None):
        """A session that shadows every unqualified name the triggers use with TEMP
        objects. The role holds TEMPORARY through the PUBLIC default (asserted below)."""
        schema = schema or self.schema
        conn = connection.connect(self.app_conninfo, autocommit=True)
        self.addCleanup(conn.close)
        conn.execute('SET search_path TO "%s"' % schema)
        conn.execute("CREATE TEMP TABLE account (account_id uuid, portfolio_id uuid, name text)")
        conn.execute('CREATE TEMP TABLE ledger_event (LIKE "%s".ledger_event)' % schema)
        conn.execute("CREATE TEMP SEQUENCE ledger_event_ledger_seq_seq START 1000000000")
        # the shadow is real: the unqualified names now resolve to the empty TEMP objects
        self.assertEqual(conn.execute("SELECT count(*) FROM account").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT count(*) FROM ledger_event").fetchone()[0], 0)
        return conn

    def attack_insert(self, conn, event, schema=None, ledger_seq=None):
        row = dict(zip(ledger_store.EVENT_COLUMNS, ledger_store.event_to_row(event)))
        if row.get("acquired_on") is None:
            row.pop("acquired_on", None)  # PD-0036: the shadow/old schemas under attack predate 0014; the store omits the NULL column the same way
        if ledger_seq is not None:
            row["ledger_seq"] = ledger_seq
        cols = list(row)
        conn.execute(
            'INSERT INTO "%s".ledger_event (%s) VALUES (%s)'
            % (schema or self.schema, ", ".join(cols), ", ".join(["%s"] * len(cols))),
            [row[c] for c in cols])

    def assert_refused(self, action, constraint):
        with self.assertRaises(self.pg.errors.CheckViolation) as cm:
            action()
        self.assertEqual(cm.exception.diag.constraint_name, constraint, str(cm.exception))

    def test_the_fix_does_not_rely_on_revoking_temporary(self):
        self.assertTrue(self.owner.execute(
            "SELECT has_database_privilege(%s, current_database(), 'TEMP')",
            (self.app_role,)).fetchone()[0])
        self.attacker()  # creating the TEMP shadows works: the privilege is still held

    def test_shadowed_tables_cannot_produce_a_reversal_of_a_reversal(self):
        deposit = ledger_store.append_event(self.app, self.event(
            EventType.DEPOSIT, account=_A5, amount=usd("10"))).event
        reversal = ledger_store.append_event(
            self.app, self.reversal(deposit.event_id, account=_A5)).event
        conn = self.attacker()
        second = self.reversal(reversal.event_id, account=_A5)
        self.assert_refused(lambda: self.attack_insert(conn, second),
                            "ledger_event_reversal_of_reversal")

    def test_shadowed_tables_cannot_put_a_buy_before_the_snapshot(self):
        ledger_store.append_event(self.app, self.event(
            EventType.OPENING_CASH, account=_A6, currency=HKD, date=datetime.date(2025, 6, 30),
            amount=Money(Decimal("100"), HKD)))
        conn = self.attacker()
        early = self.buy(account=_A6, date=datetime.date(2025, 6, 15))
        self.assert_refused(lambda: self.attack_insert(conn, early),
                            "ledger_event_after_snapshot_date")

    def test_shadowed_tables_cannot_commit_a_lone_internal_transfer_leg(self):
        conn = self.attacker()
        lone = self.event(EventType.TRANSFER_OUT, account=_A5, amount=usd("7"),
                          counterparty_account_id=_A7)

        def run():
            with conn.transaction():
                self.attack_insert(conn, lone)  # the deferred pairing check fires at commit

        self.assert_refused(run, "ledger_event_transfer_pairing")
        self.assertEqual(self.owner.execute(
            "SELECT count(*) FROM ledger_event WHERE event_id = %s", (lone.event_id,)
        ).fetchone()[0], 0)

    def test_shadowed_account_table_cannot_hide_a_cross_portfolio_transfer(self):
        conn = self.attacker()
        cross = self.event(EventType.TRANSFER_OUT, account=_A5, amount=usd("7"),
                           counterparty_account_id=_B1)
        self.assert_refused(lambda: self.attack_insert(conn, cross),
                            "ledger_event_counterparty_same_portfolio")

    def test_a_shadow_sequence_and_a_chosen_ledger_seq_are_ignored(self):
        before = self.owner.execute("SELECT max(ledger_seq) FROM ledger_event").fetchone()[0] or 0
        conn = self.attacker()
        event = self.event(EventType.DEPOSIT, account=_A7, amount=usd("3"))
        self.attack_insert(conn, event, ledger_seq=5)  # a caller-chosen value is overwritten
        seq = self.owner.execute("SELECT ledger_seq FROM ledger_event WHERE event_id = %s",
                                 (event.event_id,)).fetchone()[0]
        self.assertGreater(seq, before)  # drawn from the REAL sequence, after every commit
        self.assertLess(seq, 1_000_000_000)  # not from the attacker's TEMP sequence
        self.assertNotEqual(seq, 5)

    def test_the_portfolio_lock_is_still_taken_under_a_shadowed_account_table(self):
        conn = self.attacker()
        event = self.event(EventType.DEPOSIT, account=_A7, amount=usd("4"))
        with conn.transaction():
            self.attack_insert(conn, event)
            held = self.owner.execute(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND granted "
                "AND pid = %s", (conn.info.backend_pid,)).fetchone()[0]
            self.assertGreaterEqual(held, 1, "no per-portfolio advisory lock was taken")

    def test_control_the_same_attack_succeeds_against_the_unfixed_0003_schema(self):
        """Proves the attack is real and the tests above would fail without 0004: the same
        reversal-of-a-reversal is ACCEPTED in a schema migrated only through 0003."""
        old = "finweb_lpc_" + uuid.uuid4().hex[:12]
        control = connection.connect(connection.conninfo_from_env(os.environ), autocommit=True)

        def drop():
            try:
                control.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % old)
                left = control.execute(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = %s", (old,)).fetchall()
                self.assertEqual(left, [])
            finally:
                control.close()

        self.addCleanup(drop)
        control.execute('CREATE SCHEMA "%s"' % old)
        control.execute('SET search_path TO "%s"' % old)
        migrator.apply_migrations(control, migrator.load_migrations()[:3])
        control.execute("INSERT INTO app_user VALUES (%s)", (_USER,))
        control.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (_P1, _USER))
        control.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (_A5, _P1))
        for statement in APP_GRANTS:
            if ".md_" in statement or "benchmark_selection" in statement:
                continue  # this schema is migrated only through 0003: the md_* tables (0009+) do not exist in it
            control.execute(statement.format(schema=old, role=self.app_role))
        setup = connection.connect(self.app_conninfo, autocommit=True)
        self.addCleanup(setup.close)
        setup.execute('SET search_path TO "%s"' % old)
        deposit = ledger_store.append_event(setup, self.event(
            EventType.DEPOSIT, account=_A5, amount=usd("10"))).event
        reversal = ledger_store.append_event(
            setup, self.reversal(deposit.event_id, account=_A5)).event
        conn = self.attacker(schema=old)
        self.attack_insert(conn, self.reversal(reversal.event_id, account=_A5), schema=old)
        self.assertEqual(control.execute(
            "SELECT count(*) FROM ledger_event WHERE event_type = 'REVERSAL'").fetchone()[0], 2)

    def test_a_schema_rename_fails_closed_instead_of_reopening_the_bypass(self):
        """R2-3: the pin names the schema. After ALTER SCHEMA ... RENAME the functions fail
        closed (ledger_event_search_path_pin_stale) before touching any table, so the TEMP
        shadow attacks are refused, and so are honest appends until the owner re-pins."""
        old = "finweb_lpr_" + uuid.uuid4().hex[:12]
        new = old + "_renamed"
        control = connection.connect(connection.conninfo_from_env(os.environ), autocommit=True)

        def drop():
            try:
                for name in (old, new):
                    control.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % name)
                left = control.execute(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name IN (%s, %s)", (old, new)).fetchall()
                self.assertEqual(left, [])
            finally:
                control.close()

        self.addCleanup(drop)
        control.execute('CREATE SCHEMA "%s"' % old)
        control.execute('SET search_path TO "%s"' % old)
        migrator.apply_migrations(control)
        control.execute("INSERT INTO app_user VALUES (%s)", (_USER,))
        control.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (_P1, _USER))
        control.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (_A5, _P1))
        for statement in APP_GRANTS:
            control.execute(statement.format(schema=old, role=self.app_role))
        honest = connection.connect(self.app_conninfo, autocommit=True)
        self.addCleanup(honest.close)
        honest.execute('SET search_path TO "%s"' % old)
        deposit = ledger_store.append_event(honest, self.event(
            EventType.DEPOSIT, account=_A5, amount=usd("10"))).event
        reversal = ledger_store.append_event(
            honest, self.reversal(deposit.event_id, account=_A5)).event

        control.execute('ALTER SCHEMA "%s" RENAME TO "%s"' % (old, new))

        conn = self.attacker(schema=new)
        self.assert_refused(
            lambda: self.attack_insert(
                conn, self.reversal(reversal.event_id, account=_A5), schema=new),
            "ledger_event_search_path_pin_stale")
        honest_after = connection.connect(self.app_conninfo, autocommit=True)
        self.addCleanup(honest_after.close)
        honest_after.execute('SET search_path TO "%s"' % new)
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_event(honest_after, self.event(
                EventType.DEPOSIT, account=_A5, amount=usd("1")))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_search_path_pin_stale")

    def test_non_read_committed_is_still_refused_for_the_app_role(self):
        conn = connection.connect(self.app_conninfo)
        self.addCleanup(conn.close)
        conn.isolation_level = self.pg.IsolationLevel.REPEATABLE_READ
        conn.execute('SET search_path TO "%s"' % self.schema)
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_event(conn, self.buy())
        self.assertEqual(cm.exception.constraint_name, "ledger_event_requires_read_committed")


if __name__ == "__main__":
    unittest.main()
