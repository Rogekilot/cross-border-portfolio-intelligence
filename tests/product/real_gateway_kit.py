"""Provisioning kit and base test case for the real-gateway PostgreSQL tests (F1 R1). Not a test module.

What it does, and what it refuses
  * It follows the existing provisioning pattern (`guarded_pg_provision.Provisioner`): ONE run prefix `finweb_it_rw_<hex8>`, every
    object it creates is named from that prefix, every drop goes through `owned_name`, a role or database is recorded for cleanup
    only after its CREATE succeeded, and everything is dropped in `release()`.
  * It creates a DISPOSABLE database (template0, `TEMPORARY`/`CREATE` revoked from PUBLIC) and, per install, one schema and four new
    roles (owner NOLOGIN; executor, loader, publisher LOGIN with a random password). It never touches an existing database, schema
    or role, and the database name can never use the reserved `finweb_real` prefix.
  * The admin role must be a SUPERUSER that can CREATE ROLE and CREATE DATABASE, as for the existing runner (the owner session is a
    `SET ROLE` from it, and the stall tests terminate backends). It is taken from `FINWEB_PG_ADMIN_USER`, else `FINWEB_PG_USER`. A
    role that cannot provision makes the tests SKIP with the exact reason; they are never reported as passed. A password, if the
    cluster needs one, is read by the Provisioner from `FINWEB_IT_ADMIN_PASSWORD`. Nothing here chooses another role.
  * Installs are made by the PRODUCT installer (`install_test_gateway`, kind TEST). The one exception is `kind="REAL"`: the
    kit builds the install with the product's own checks and body and then writes the kind row `REAL` as the owner role, an E11
    crafted fixture for the install-kind guard test (design 4.2). It is a disposable database, so it never receives real content.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import os
import secrets
import sys
import threading
import time
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402
from psycopg.pq import TransactionStatus  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

import real_gateway_fixtures as fx  # noqa: E402
from guarded_pg_provision import Provisioner  # noqa: E402
from persistence import real_scope, real_workspace_store as store  # noqa: E402

PREFIX = "finweb_it_rw_"
ROLE_KINDS = (("owner", "NOLOGIN"), ("executor", "PASSWORD"), ("loader", "PASSWORD"), ("publisher", "PASSWORD"))
PURPOSES = ("EXECUTE_CREATE", "ARCHIVE_READ", "ARCHIVE_EXPORT", "EXECUTE_REPRODUCE")
NO_TIMEOUTS = "-c timezone=UTC"
AUTO = object()          # "choose a valid_until for me" (None is a real value: no valid_until)


class Install:
    """One schema of the disposable database with its four roles."""

    def __init__(self, kit, tag, schema, roles, passwords, w_seconds, kind):
        self.kit, self.tag, self.schema, self.roles, self.passwords, self.w_seconds, self.kind = kit, tag, schema, roles, passwords, w_seconds, kind

    def set_login(self, who, enabled):
        """E11 crafted fixture: the owner's procedure of PD-0070 decision 1 (ALTER ROLE ... LOGIN / NOLOGIN), run by the administrative
        role of this DISPOSABLE database. Enabling gives the role a new random password; connections already open are not ended."""
        import secrets as _secrets
        prov = self.kit.prov
        role = sql.Identifier(self.roles[who])
        with prov.admin(prov.database) as conn:
            if enabled:
                password = _secrets.token_hex(16)
                conn.execute(sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(role, sql.Literal(password)))
                self.passwords[who] = password
            else:
                conn.execute(sql.SQL("ALTER ROLE {} NOLOGIN").format(role))

    def set_membership(self, member, role, enabled):
        """E11 crafted fixture (R2 review L-4): `GRANT <role> TO <member>` / `REVOKE <role> FROM <member>` between two of this install's
        roles, run by the administrative role of this DISPOSABLE database. A product path never grants a role to another."""
        prov = self.kit.prov
        statement = "GRANT {} TO {}" if enabled else "REVOKE {} FROM {}"
        with prov.admin(prov.database) as conn:
            conn.execute(sql.SQL(statement).format(sql.Identifier(self.roles[role]), sql.Identifier(self.roles[member])))

    def connect(self, who, *, autocommit=True, options=None):
        """A new connection as `who`: owner (admin session after SET ROLE owner), admin (the superuser, no SET ROLE), executor, loader or
        publisher (each logs in as itself)."""
        prov = self.kit.prov
        if who in ("owner", "admin"):
            conn = psycopg.connect(prov.dsn(prov.db, prov.admin_user, prov.password, options=options or NO_TIMEOUTS), autocommit=True)
        else:
            extra = {} if options is None else {"options": options}
            conn = psycopg.connect(prov.dsn(prov.db, self.roles[who], self.passwords[who], **extra), autocommit=True)
        prov.connections.append(conn)
        try:
            if who == "owner":
                conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(self.roles["owner"])))
                conn.execute(sql.SQL("SET search_path TO {}, pg_temp").format(sql.Identifier(self.schema)))
            if not autocommit:
                conn.autocommit = False
        except BaseException:
            conn.close()
            raise
        return conn


class GatewayKit:
    """Reference-counted: the first `acquire()` provisions the database, the last `release()` drops it."""

    def __init__(self):
        self.users, self.prov, self.skip_reason, self.installs = 0, None, None, {}
        self.server_version = None
        self.lock = threading.Lock()

    @property
    def ready(self):
        return self.prov is not None and self.skip_reason is None

    # ---- lifecycle -------------------------------------------------------------------------------------------------------
    def acquire(self):
        with self.lock:
            self.users += 1
            if self.users == 1:
                self._provision()

    def release(self):
        with self.lock:
            self.users -= 1
            if self.users == 0:
                self._cleanup()

    def _provision(self):
        self.prov, self.skip_reason, self.installs = None, None, {}
        env = os.environ
        if env.get("FINWEB_PG_INTEGRATION") != "1":
            self.skip_reason = "FINWEB_PG_INTEGRATION=1 is not set"
            return
        socket, database = env.get("FINWEB_PG_SOCKET"), env.get("FINWEB_PG_DATABASE")
        admin = env.get("FINWEB_PG_ADMIN_USER") or env.get("FINWEB_PG_USER")
        if not (socket and database and admin):
            self.skip_reason = "FINWEB_PG_SOCKET, FINWEB_PG_DATABASE and FINWEB_PG_ADMIN_USER (or FINWEB_PG_USER) are required"
            return
        if database.startswith(store.RESERVED_REAL_PREFIX):
            self.skip_reason = "the reserved real-install namespace is never used by the test tooling"
            return
        prov = Provisioner(socket, database, admin, PREFIX + secrets.token_hex(4))
        try:
            prov.preflight()
            prov.refuse_if_prefix_exists()
            prov.create_database()
        except (RuntimeError, psycopg.Error) as error:
            reason = str(error).splitlines()[0] if str(error) else type(error).__name__
            if prov.db_created or prov.created_roles:
                self._drop(prov)            # something was created before the failure: remove exactly that
            else:
                prov.close_connections()
            self.skip_reason = ("cannot provision a disposable database as %r: %s. Set FINWEB_PG_ADMIN_USER to a superuser role of the "
                                "development cluster (the supplied FINWEB_PG_USER is used when it is not set)" % (admin, reason))
            return
        self.prov = prov
        with contextlib.suppress(psycopg.Error):          # one log line, so that a run says what server it ran against
            with prov.admin(prov.db) as conn:
                self.server_version = conn.execute("SHOW server_version").fetchone()[0]
            sys.stderr.write("real-gateway kit: PostgreSQL %s, disposable database %s\n" % (self.server_version, prov.db))

    def _drop(self, prov):
        prov.close_connections()
        prov.drop_objects(db_created=prov.db_created, roles=prov.created_roles)
        if prov.errors:
            raise RuntimeError("cleanup of %s failed: %s" % (prov.own, "; ".join(prov.errors)))

    def _cleanup(self):
        prov, self.prov, self.installs = self.prov, None, {}
        if prov is not None:
            self._drop(prov)

    # ---- installs --------------------------------------------------------------------------------------------------------
    def install(self, tag, *, w_seconds=4, kind="TEST", loader_login=True, account=False):
        """The cached install `tag`, created on first use. Raises (a test ERROR) if the installer or the gateway SQL fails: a failure
        of the code under test is never turned into a skip. `loader_login=False` creates the loader NOLOGIN (R2: the installer accepts
        a loader with or without LOGIN; PD-0070 decision 1 has the owner set it NOLOGIN while no load runs)."""
        key = (tag, w_seconds, kind, loader_login, account)
        with self.lock:
            if key not in self.installs:
                self.installs[key] = self._create_install(tag, w_seconds, kind, loader_login, account)
            return self.installs[key]

    def _create_install(self, tag, w_seconds, kind, loader_login=True, account=False):
        """`account=True` (PD-0078) creates the fifth role, `account`, LOGIN with a password, and passes it to the PRODUCT installer, which grants it
        exactly `real_roles.ACCOUNT_TABLES` and audits it. The earlier installs stay four-role."""
        prov = self.prov
        schema = prov.owned_name("%s_%s" % (prov.own, tag))
        kinds = ROLE_KINDS + ((("account", "PASSWORD"),) if account else ())
        roles = {name: prov.owned_name("%s_%s_%s" % (prov.own, tag, name)) for name, _mode in kinds}
        passwords = {}
        with prov.admin(prov.database) as conn:
            for name, mode in kinds:
                if name == "loader" and not loader_login:
                    mode = "NOLOGIN"
                password = prov.create_role(conn, roles[name], mode)
                if password is not None:
                    passwords[name] = password
        prov.create_schema(schema, roles["owner"])
        names = dict(schema=schema, owner_role=roles["owner"], executor_role=roles["executor"], loader_role=roles["loader"],
                     publisher_role=roles["publisher"])
        if account:
            names["account_role"] = roles["account"]
        with prov.admin(prov.db) as conn:
            prov.apply_migrations_as_owner(conn, schema, roles["owner"])
            if kind == "TEST":
                store.install_test_gateway(conn, w_seconds=w_seconds, **names)
            else:
                # E11 CRAFTED FIXTURE (design 4.2): the product installer writes TEST only. For the install-kind guard test in the
                # other direction, the owner role of this DISPOSABLE database writes the kind row REAL after the product's own
                # checks and gateway SQL ran. The database holds no real content and its name is outside the reserved namespace.
                assert kind == "REAL" and prov.db.startswith(PREFIX) and not prov.db.startswith(store.RESERVED_REAL_PREFIX)
                # R3: the crafted REAL install runs the REAL file list (the core alone, without the TEST-only part) and the REAL role
                # lists, and the audit as REAL, so the file split is exercised on a database that holds no fictional-branch function.
                checked = store._check_install_inputs(w_seconds=w_seconds, **names)
                with conn.transaction():
                    store._install_gateway_body(conn, checked, roles["owner"], roles["executor"], roles["loader"], roles["publisher"], kind="REAL",
                                                account_role=names.get("account_role"))
                    conn.execute(sql.SQL("INSERT INTO {}.rw_install(singleton,kind,w_seconds) VALUES(true,'REAL',%s)").format(
                        sql.Identifier(schema)), (w_seconds,))
        return Install(self, tag, schema, roles, passwords, w_seconds, kind)


KIT = GatewayKit()


def setUpModule():
    KIT.acquire()


def tearDownModule():
    KIT.release()


# =====================================================================================================================
# Helpers for tests
# =====================================================================================================================
def begin(conn):
    conn.execute("BEGIN")


def commit(conn):
    conn.execute("COMMIT")


def rollback(conn):
    if conn.info.transaction_status != TransactionStatus.IDLE:
        conn.execute("ROLLBACK")


class Worker:
    """Runs `fn()` on a thread; `join()` returns its value or re-raises its exception."""

    def __init__(self, fn):
        self.result, self.error = None, None
        self.thread = threading.Thread(target=self._run, args=(fn,), daemon=True)
        self.thread.start()

    def _run(self, fn):
        try:
            self.result = fn()
        except BaseException as error:  # noqa: BLE001
            self.error = error

    def join(self, timeout=30):
        self.thread.join(timeout)
        if self.thread.is_alive():
            raise AssertionError("worker did not finish in %ss" % timeout)
        if self.error is not None:
            raise self.error
        return self.result

    @property
    def done(self):
        return not self.thread.is_alive()


def wait_until(predicate, timeout=10.0, interval=0.05, what="condition"):
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting for " + what)
        time.sleep(interval)


class GatewayCase(unittest.TestCase):
    """Base class: one cached TEST install per `INSTALL` tag; unique content per test; connections closed after each test."""

    INSTALL = "core"
    W = 4
    KIND = "TEST"
    LOADER_LOGIN = True
    ACCOUNT = False             # PD-0078: True gives the install the fifth, account role (made by the product installer's grants)

    def setUp(self):
        if not KIT.ready:
            self.skipTest(KIT.skip_reason or "the real-gateway PostgreSQL tests were not provisioned")
        self.inst = KIT.install(self.INSTALL, w_seconds=self.W, kind=self.KIND, loader_login=self.LOADER_LOGIN, account=self.ACCOUNT)
        self.s = self.inst.schema
        self._counter = 0
        self.owner = self.conn("owner")
        self.admin = self.conn("admin")
        self.factory = self.conn("executor")        # autocommit; used only by the product factory (rw_install_info)

    # ---- connections -----------------------------------------------------------------------------------------------------
    def conn(self, who, **kw):
        connection = self.inst.connect(who, **kw)
        self.addCleanup(self._close, connection)
        return connection

    @staticmethod
    def _close(connection):
        with contextlib.suppress(Exception):
            if not connection.closed and connection.info.transaction_status != TransactionStatus.IDLE:
                connection.rollback()
        with contextlib.suppress(Exception):
            connection.close()

    def tool(self, **kw):
        return store.RealPublisher(self.conn("publisher"), self.s, **kw)

    # ---- time ------------------------------------------------------------------------------------------------------------
    def db_now(self):
        return self.owner.execute("SELECT clock_timestamp()").fetchone()[0]

    def wait_for_db_time(self, instant, slack=0.05):
        wait_until(lambda: self.db_now() >= instant + dt.timedelta(seconds=slack), timeout=60, interval=0.05, what="the database clock to pass %s" % instant)

    # ---- content ---------------------------------------------------------------------------------------------------------
    def tag(self, label=""):
        self._counter += 1
        return "%s/%s/%d" % (self.id(), label, self._counter)

    def snapshot(self, scope="SYNTHETIC_TEST", *, sources=fx.SOURCES, label=""):
        """A snapshot from the PRODUCT factory (never a test helper): scope, switch and install kind are checked there."""
        return real_scope.make_snapshot(self.factory, self.s, scope, test_switch=(scope == "TEST_SWITCH"),
                                        **fx.content(self.tag(label), sources=sources))

    def proposal(self, snapshot):
        from persistence import real_proposal
        return real_proposal.proposal_bytes(snapshot)

    def bound(self, seconds=86400):
        return (self.db_now() + dt.timedelta(seconds=seconds)).astimezone(dt.timezone.utc).replace(microsecond=0)

    def publish(self, snapshot=None, *, valid_in=120.0, valid_until=AUTO, rights=None, evidence=None, actor=fx.ACTOR, ref=fx.REF,
                scope="SYNTHETIC_TEST", tool=None, expect_ok=True):
        """Publish through the PRODUCT tool; returns (snapshot, valid_until, result). `valid_until=None` publishes without one."""
        snapshot = snapshot or self.snapshot(scope)
        valid = self.db_now() + dt.timedelta(seconds=valid_in) if valid_until is AUTO else valid_until
        result = (tool or self.tool()).publish(self.proposal(snapshot), rights=rights or fx.ALL_RIGHTS, valid_until=valid,
                                               evidence=evidence if evidence is not None else fx.hg4_shape(self.bound()), actor=actor, ref=ref)
        if expect_ok:
            self.assertEqual(result.status, 0, result.text)
        return snapshot, valid, result

    def renew(self, ctx, generation, *, valid_until, rights=None, evidence=None, ref=fx.REF_OTHER, actor=fx.ACTOR, tool=None, **kw):
        return (tool or self.tool()).renew(ctx, generation, rights=rights or fx.ALL_RIGHTS, valid_until=valid_until,
                                           evidence=evidence if evidence is not None else fx.hg4_shape(self.bound()), actor=actor, ref=ref, **kw)

    # ---- crafted fixtures (E11: written by the owner role of a disposable database; never product evidence) ---------------
    def craft_root(self, ctx, *, owner_id=None, root_id=None):
        """One app_user, one portfolio row and one root-link row in a single transaction (design 3.2, R1's root fixture)."""
        owner_id, root_id = owner_id or uuid.uuid4(), root_id or uuid.uuid4()
        with self.owner.transaction():
            # R3 (design 3.2): the write fence fires for the owner too, so the fixture disables the user triggers of the one table it
            # writes for its own insert and enables them again in the same transaction. E11 crafted; never product evidence.
            self.owner.execute(f"ALTER TABLE {self.s}.portfolio DISABLE TRIGGER USER")
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s) ON CONFLICT DO NOTHING", (owner_id,))
            self.owner.execute(f"INSERT INTO {self.s}.portfolio(portfolio_id,user_id,reporting_currency) VALUES(%s,%s,'USD')", (root_id, owner_id))
            self.owner.execute(f"ALTER TABLE {self.s}.portfolio ENABLE TRIGGER USER")
            self.owner.execute(f"INSERT INTO {self.s}.rw_root_link(root_id,owner_id,context_id) VALUES(%s,%s,%s)", (root_id, owner_id, ctx))
        return owner_id, root_id

    @contextlib.contextmanager
    def bundle_guard_off(self):
        """E11 CRAFTED (never product evidence). R3's bundle guard refuses to COMMIT an EXECUTE_CREATE lease that was not sealed with a
        complete bundle (design 2.6 item 4), which is the product behaviour; an R1 or R2 test that needs only the lease ROW to exist
        (a recorded purpose, a load under a committed lease) switches the guard off for its own duration and on again at the end. The
        guard is a trigger of the disposable database's lease table; the owner role of that database disables it."""
        with self.owner.transaction():
            self.owner.execute(f"ALTER TABLE {self.s}.rw_lease DISABLE TRIGGER rw_bundle_complete")
        try:
            yield
        finally:
            with self.owner.transaction():
                self.owner.execute(f"ALTER TABLE {self.s}.rw_lease ENABLE TRIGGER rw_bundle_complete")

    def craft_context(self, snapshot_bytes, *, kind, valid_until, basis, rights=None, generation=1):
        """A snapshot, a history row and a head written directly (E11 crafted), and the mode opened."""
        import hashlib
        ctx = hashlib.sha256(snapshot_bytes).hexdigest()
        rights = rights or fx.ALL_RIGHTS
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.rw_snapshot(context_id,snapshot) VALUES(%s,%s) ON CONFLICT DO NOTHING", (ctx, snapshot_bytes))
            self.owner.execute(
                f"INSERT INTO {self.s}.rw_history(context_id,generation,rights,expiry_kind,valid_until,basis,issuer_actor,pd_id,git_commit,doc_sha256,recorded_at)"
                " VALUES(%s,%s,%s,%s,%s,%s,'crafted','PD-9999',%s,%s,clock_timestamp())",
                (ctx, generation, Jsonb(rights), kind, valid_until, Jsonb(basis), "e" * 40, "f" * 64))
            self.owner.execute(f"INSERT INTO {self.s}.rw_head(context_id,generation,rights,expiry_kind,valid_until) VALUES(%s,%s,%s,%s,%s)",
                               (ctx, generation, Jsonb(rights), kind, valid_until))
            self.owner.execute(f"UPDATE {self.s}.rw_mode SET mode='DB_SNAPSHOT_V1' WHERE singleton")
        return ctx

    # ---- reads (owner) -----------------------------------------------------------------------------------------------------
    def history(self, ctx):
        rows = self.owner.execute(f"SELECT generation,rights,expiry_kind,valid_until,basis,issuer_actor,pd_id,git_commit,doc_sha256,recorded_at,drain_mark_id "
                                  f"FROM {self.s}.rw_history WHERE context_id=%s ORDER BY generation", (ctx,)).fetchall()
        names = ("generation", "rights", "expiry_kind", "valid_until", "basis", "issuer_actor", "pd_id", "git_commit", "doc_sha256", "recorded_at", "drain_mark_id")
        return [dict(zip(names, row)) for row in rows]

    def head(self, ctx):
        return self.owner.execute(f"SELECT generation,rights,expiry_kind,valid_until FROM {self.s}.rw_head WHERE context_id=%s", (ctx,)).fetchone()

    def marks(self, ctx):
        rows = self.owner.execute(f"SELECT mark_id,generation,issuer_actor,pd_id,git_commit,doc_sha256,marked_at FROM {self.s}.rw_drain_mark "
                                  f"WHERE context_id=%s ORDER BY mark_id", (ctx,)).fetchall()
        return [dict(zip(("mark_id", "generation", "issuer_actor", "pd_id", "git_commit", "doc_sha256", "marked_at"), r)) for r in rows]

    def leases(self, ctx):
        rows = self.owner.execute(f"SELECT admitted_at,valid_until,complete_by,purpose,phase,operation_id,backend_pid FROM {self.s}.rw_lease "
                                  f"WHERE context_id=%s ORDER BY admitted_at", (ctx,)).fetchall()
        return [dict(zip(("admitted_at", "valid_until", "complete_by", "purpose", "phase", "operation_id", "backend_pid"), r)) for r in rows]

    def count(self, table, where="true", params=()):
        return self.owner.execute(f"SELECT count(*) FROM {self.s}.{table} WHERE {where}", params).fetchone()[0]

    # ---- the executor ------------------------------------------------------------------------------------------------------
    def admit(self, conn, ctx, generation, purpose, owner_id, root_id, *, op=None, new_root=False):
        """Admit inside the CALLER's open transaction on `conn` (autocommit connection, BEGIN issued by the caller)."""
        return store.admit(conn, self.s, owner=owner_id, root=root_id, context_id=ctx, generation=generation, purpose=purpose,
                           operation_id=op or uuid.uuid4(), command_sha256="1" * 64, new_root=new_root)

    def admit_and_commit(self, conn, ctx, generation, purpose, owner_id, root_id, **kw):
        begin(conn)
        try:
            lease = self.admit(conn, ctx, generation, purpose, owner_id, root_id, **kw)
            commit(conn)
            return lease
        finally:
            rollback(conn)

    def stall_options(self):
        """Connection options that leave every timeout at 0: the connection's own timeouts are then not the bound (design 3.2)."""
        return "-c timezone=UTC -c statement_timeout=0 -c idle_in_transaction_session_timeout=0 -c lock_timeout=0 -c transaction_timeout=0"

    # ---- assertions --------------------------------------------------------------------------------------------------------
    def assertRefused(self, code, fn, *, detail=None):
        """`fn()` raises the gateway refusal `code` (a RealWorkspaceError, or a raw RaiseException whose primary message is `code`)."""
        try:
            fn()
        except store.RealWorkspaceError as error:
            self.assertEqual(error.code, code, str(error))
            if detail is not None:
                self.assertIn(detail, error.codes + (error.detail,), str(error))
            return error
        except psycopg.errors.RaiseException as error:
            primary = error.diag.message_primary or str(error)
            self.assertEqual(primary.splitlines()[0], code)
            if detail is not None:
                self.assertIn(detail, error.diag.message_detail or "")
            return error
        self.fail("expected the refusal " + code)

    def assertTruncateRefused(self, table, *, trigger_expected):
        """TRUNCATE of `table` as the owner is refused and removes nothing. For a table that another table references, PostgreSQL's own
        foreign-key refusal comes first and the immutability trigger is not reached; for an unreferenced table the trigger must be."""
        before = self.count(table)
        try:
            self.owner.execute(f"TRUNCATE {self.s}.{table}")
        except psycopg.errors.RaiseException as error:
            self.assertEqual((error.diag.message_primary or str(error)).splitlines()[0], "RW_IMMUTABLE", table)
        except psycopg.errors.FeatureNotSupported:
            self.assertFalse(trigger_expected, table + ": expected the immutability trigger, got PostgreSQL's foreign-key refusal")
        else:
            self.fail("TRUNCATE succeeded on " + table)
        self.assertEqual(self.count(table), before, table)

    def assertDenied(self, fn):
        """`fn()` raises insufficient_privilege (42501)."""
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            fn()
