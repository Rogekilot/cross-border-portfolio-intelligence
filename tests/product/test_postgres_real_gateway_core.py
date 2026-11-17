"""F1 R1, PostgreSQL: the authority core, its roles and privileges, publish, expiry evidence and the install-kind guard.

Covers (design 7.1 R1 row): T01 (sole authority), T04 (roles), FF1-C03 (sole current authority), FF1-C04 (roles), FF1-C06 (expiry
evidence: X1/NONE/UNKNOWN stay disjoint), reduced FF1-C12 (idempotent re-run of an interrupted publish) and the scope tests of 4.2.

Every test runs against a DISPOSABLE test database provisioned by `real_gateway_kit` (never an existing database). Without a
provisioning superuser (`FINWEB_PG_ADMIN_USER`) they SKIP with the reason; they are never reported as passed. Each test says in its
docstring whether it runs on the PRODUCT path or on an E11 CRAFTED fixture (rows written by the owner role of the disposable
database, which is never product evidence).
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

import real_gateway_fixtures as fx  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from persistence import real_scope, real_workspace_store as store  # noqa: E402
from real_gateway_kit import (KIT, GatewayCase, begin, commit, rollback, setUpModule, tearDownModule)  # noqa: E402,F401

from persistence import real_catalog_audit, real_roles  # noqa: E402

# R3 moved the role plan into persistence.real_roles (one list per role, both install kinds). The `rw_` names only: the `rwp_` registry
# functions are asserted by the R2 modules.
EXECUTOR_FUNCTIONS = {name for name, _args in real_roles.EXECUTOR_FUNCTIONS if name.startswith("rw_")}
PUBLISHER_FUNCTIONS = {name for name, _args in real_roles.PUBLISHER_FUNCTIONS}
CALLS = {
    "rw_publish": "rw_publish(NULL::bytea,NULL::jsonb,NULL::timestamptz,NULL::jsonb,NULL::text,NULL::text,NULL::text,NULL::text)",
    "rw_renew": "rw_renew(NULL::text,NULL::bigint,NULL::jsonb,NULL::timestamptz,NULL::jsonb,NULL::text,NULL::text,NULL::text,NULL::text,NULL::bigint)",
    "rw_withdraw_mark": "rw_withdraw_mark(NULL::text,NULL::bigint,NULL::text,NULL::text,NULL::text,NULL::text)",
    "rw_withdraw_apply": "rw_withdraw_apply(NULL::text,NULL::bigint)",
    "rw_in_flight": "rw_in_flight(NULL::text)",
    "rw_admit": "rw_admit(NULL::uuid,NULL::uuid,NULL::text,NULL::bigint,NULL::text,NULL::uuid,NULL::text,NULL::boolean)",
    "rw_scope": "rw_scope()",
    "rw_list_roots": "rw_list_roots(NULL::uuid)",
    "rw_install_info": "rw_install_info()",
    "rw_latest_instant": "rw_latest_instant()",
    "rw_expiry_derive": "rw_expiry_derive(NULL::text[],NULL::jsonb,NULL::timestamptz)",
    "rw_rights_valid": "rw_rights_valid(NULL::jsonb)",
    "rw_scope_allowed": "rw_scope_allowed(NULL::text,NULL::text)",
    "rw_snapshot_scope": "rw_snapshot_scope(NULL::bytea)",
    "rw_snapshot_sources": "rw_snapshot_sources(NULL::bytea)",
    "rw_reached": "rw_reached(NULL::timestamptz,NULL::timestamptz)",
}
TABLES = ("rw_install", "rw_mode", "rw_snapshot", "rw_drain_mark", "rw_history", "rw_head", "rw_root_link", "rw_lease")
VIEWS = ("rw_pending_marks", "rw_status")


class CatalogAndRoleTests(GatewayCase):
    """T04 / FF1-C04: the four roles, their exact grants, fixed search paths. Product installer; catalog reads by the superuser."""

    def role_set(self, rows):
        return {name for (name,) in rows}

    def test_install_row_holds_kind_and_w_once(self):
        """Product path (installer). The kind and W are written once, are readable by tools only through the definer function."""
        self.assertEqual(self.owner.execute(f"SELECT kind,w_seconds FROM {self.s}.rw_install").fetchall(), [("TEST", 4)])
        executor = self.conn("executor")
        self.assertEqual(executor.execute(f"SELECT * FROM {self.s}.rw_install_info()").fetchone(), ("TEST", 4))
        self.assertEqual(real_scope.read_install_kind(self.factory, self.s), ("TEST", 4))
        self.assertDenied(lambda: executor.execute(f"SELECT * FROM {self.s}.rw_install"))
        self.assertRefused("RW_IMMUTABLE", lambda: self.owner.execute(f"UPDATE {self.s}.rw_install SET w_seconds=5"))
        self.assertRefused("RW_IMMUTABLE", lambda: self.owner.execute(f"DELETE FROM {self.s}.rw_install"))
        self.assertTruncateRefused("rw_install", trigger_expected=True)
        with self.assertRaises(store.RealWorkspaceError) as caught:
            store.install_test_gateway(self.owner, schema=self.s, w_seconds=4, owner_role=self.inst.roles["owner"],
                                       executor_role=self.inst.roles["executor"], loader_role=self.inst.roles["loader"],
                                       publisher_role=self.inst.roles["publisher"])
        self.assertEqual(caught.exception.code, "RW_ALREADY_INSTALLED")

    def test_every_gateway_function_pins_its_search_path_with_pg_temp_last(self):
        """Product path. FF1-C04 'wrong schema/search_path/temp shadowing': the pin is in the catalog for every `rw_` function. R1 had
        twenty-one; R3 adds the fence, the seal, the archive and the thirteen read functions, so the expected set is the set the installed
        SQL files declare (a TEST install: the core plus the TEST-only part)."""
        rows = self.admin.execute(r"SELECT p.proname,p.prosecdef,p.proconfig FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                                  r"WHERE n.nspname=%s AND p.proname LIKE 'rw\_%%' ORDER BY p.proname", (self.s,)).fetchall()
        declared = {n for n in real_catalog_audit._declared_functions("TEST") if n.startswith("rw_")}
        self.assertEqual({r[0] for r in rows}, declared)
        self.assertEqual(len(rows), len(declared))
        self.assertGreater(len(rows), 21)
        for name, secdef, config in rows:
            self.assertTrue(config and len(config) == 1, name)
            path = config[0].split("=", 1)
            self.assertEqual(path[0], "search_path", name)
            self.assertEqual(path[1].replace(" ", "").split(","), ["pg_catalog", self.s, "pg_temp"], name)
            if name in EXECUTOR_FUNCTIONS | PUBLISHER_FUNCTIONS:
                self.assertTrue(secdef, name)

    def test_function_privileges_are_exactly_the_role_plan(self):
        """Product path. EXECUTE on the schema's `rw_` functions: the executor its list (R3), publisher six, loader none, PUBLIC none."""
        query = (r"SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND p.proname LIKE 'rw\_%%' "
                 r"AND has_function_privilege(%s::name,p.oid,'EXECUTE')")
        self.assertEqual(self.role_set(self.admin.execute(query, (self.s, self.inst.roles["executor"])).fetchall()), EXECUTOR_FUNCTIONS)
        self.assertEqual(self.role_set(self.admin.execute(query, (self.s, self.inst.roles["publisher"])).fetchall()), PUBLISHER_FUNCTIONS)
        self.assertEqual(self.admin.execute(query, (self.s, self.inst.roles["loader"])).fetchall(), [])
        public = self.admin.execute(r"SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                                    r"CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a "
                                    r"WHERE n.nspname=%s AND p.proname LIKE 'rw\_%%' AND a.grantee=0", (self.s,)).fetchone()[0]
        self.assertEqual(public, 0)

    def test_table_privileges_are_exactly_the_role_plan(self):
        """Product path. Each role holds exactly the table privileges of its list in `real_roles.role_lists` (R3) over the authority core,
        the status views and the application tables the old R1 plan named; the authority core's tables stay out of every runtime role's
        reach; nobody holds a column-level privilege beyond the list; PUBLIC holds nothing. (R1 asserted 'nothing at all but the
        publisher's two views'; R3 gave the executor its list, and the full per-relation comparison is the catalog audit's, test_postgres_real_gateway_fence.)"""
        relations = list(TABLES) + list(VIEWS) + ["app_user", "portfolio", "account", "ledger_event"]
        lists = real_roles.role_lists("TEST")
        for role in ("executor", "loader", "publisher"):
            granted = lists[role]["tables"]
            for relation in relations:
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                    held = self.admin.execute("SELECT has_table_privilege(%s::name,%s::regclass,%s)",
                                              (self.inst.roles[role], f"{self.s}.{relation}", privilege)).fetchone()[0]
                    self.assertEqual(held, privilege in granted.get(relation, frozenset()), (role, relation, privilege))
                column = self.admin.execute("SELECT has_any_column_privilege(%s::name,%s::regclass,'SELECT,INSERT,UPDATE,REFERENCES')",
                                            (self.inst.roles[role], f"{self.s}.{relation}")).fetchone()[0]
                self.assertEqual(column, bool(granted.get(relation, frozenset()) & {"SELECT", "INSERT", "UPDATE", "REFERENCES"}), (role, relation))
        for role in ("executor", "loader", "publisher"):
            for relation in TABLES:
                self.assertNotIn(relation, lists[role]["tables"], (role, relation))
        public = self.admin.execute(r"SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                                    r"CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a "
                                    r"WHERE n.nspname=%s AND c.relkind IN ('r','v') AND c.relname LIKE 'rw\_%%' AND a.grantee=0", (self.s,)).fetchone()[0]
        self.assertEqual(public, 0)
        for role in ("executor", "loader", "publisher"):
            self.assertTrue(self.admin.execute("SELECT has_schema_privilege(%s::name,%s,'USAGE')", (self.inst.roles[role], self.s)).fetchone()[0])
            self.assertFalse(self.admin.execute("SELECT has_schema_privilege(%s::name,%s,'CREATE')", (self.inst.roles[role], self.s)).fetchone()[0])

    def test_role_attributes_and_memberships(self):
        """Product path. Owner NOLOGIN; the others LOGIN; none superuser, createdb, createrole, replication or BYPASSRLS; no membership."""
        rows = self.admin.execute("SELECT rolname,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit FROM pg_roles "
                                  "WHERE rolname=ANY(%s::text[])", (list(self.inst.roles.values()),)).fetchall()
        by_name = {r[0]: r[1:] for r in rows}
        self.assertEqual(len(by_name), 4)
        self.assertEqual(by_name[self.inst.roles["owner"]][0], False)
        for role in ("executor", "loader", "publisher"):
            self.assertTrue(by_name[self.inst.roles[role]][0], role)
        for name, attrs in by_name.items():
            self.assertEqual(attrs[1:6], (False, False, False, False, False), name)
        members = self.admin.execute("SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid IN (m.roleid,m.member) "
                                     "WHERE r.rolname=ANY(%s::text[])", (list(self.inst.roles.values()),)).fetchone()[0]
        self.assertEqual(members, 0)

    def test_the_executor_reaches_nothing_but_its_functions(self):
        """Product path. Actual executor session: no table read or write, no DDL, no SET ROLE, no publisher function."""
        executor = self.conn("executor")
        for relation in TABLES + VIEWS:
            self.assertDenied(lambda r=relation: executor.execute(f"SELECT * FROM {self.s}.{r}"))
        self.assertDenied(lambda: executor.execute(f"INSERT INTO {self.s}.rw_head(context_id,generation,rights,expiry_kind) VALUES(%s,1,'{{}}','NONE')", ("0" * 64,)))
        self.assertDenied(lambda: executor.execute(f"UPDATE {self.s}.rw_mode SET mode='CLOSED'"))
        self.assertDenied(lambda: executor.execute(f"DELETE FROM {self.s}.rw_lease"))
        # R3: the executor holds INSERT on the portfolio table (its list), so the privilege check no longer refuses; the write FENCE does,
        # with its own code, before any row policy or constraint (the full matrix is in test_postgres_real_gateway_fence).
        self.assertRefused("RW_WRITE_REFUSED", lambda: executor.execute(
            f"INSERT INTO {self.s}.portfolio(portfolio_id,user_id,reporting_currency) VALUES(%s,%s,'USD')", (uuid.uuid4(), uuid.uuid4())))
        rollback(executor)
        self.assertDenied(lambda: executor.execute(f"CREATE TABLE {self.s}.hostile(x int)"))
        self.assertDenied(lambda: executor.execute(f"CREATE FUNCTION {self.s}.hostile() RETURNS int LANGUAGE sql AS 'SELECT 1'"))
        for role in ("owner", "publisher", "loader"):
            self.assertDenied(lambda r=role: executor.execute(f'SET ROLE "{self.inst.roles[r]}"'))
        for name in sorted(CALLS):
            if name not in EXECUTOR_FUNCTIONS:
                self.assertDenied(lambda n=name: executor.execute(f"SELECT * FROM {self.s}.{CALLS[n]}"))

    def test_the_publisher_cannot_create_economic_rows_or_admit(self):
        """Product path. Actual publisher session: reads only the two views, writes nothing, cannot admit or list, cannot SET ROLE."""
        publisher = self.conn("publisher")
        for view in VIEWS:
            publisher.execute(f"SELECT * FROM {self.s}.{view}").fetchall()
        for relation in TABLES:
            self.assertDenied(lambda r=relation: publisher.execute(f"SELECT * FROM {self.s}.{r}"))
            self.assertDenied(lambda r=relation: publisher.execute(f"DELETE FROM {self.s}.{r}"))
        for relation in ("app_user", "portfolio", "account", "ledger_event"):
            self.assertDenied(lambda r=relation: publisher.execute(f"SELECT * FROM {self.s}.{r}"))
        self.assertDenied(lambda: publisher.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (uuid.uuid4(),)))
        self.assertDenied(lambda: publisher.execute(f"INSERT INTO {self.s}.rw_history(context_id,generation) VALUES(%s,1)", ("0" * 64,)))
        for name in sorted(CALLS):
            if name not in PUBLISHER_FUNCTIONS:
                self.assertDenied(lambda n=name: publisher.execute(f"SELECT * FROM {self.s}.{CALLS[n]}"))
        for role in ("owner", "executor", "loader"):
            self.assertDenied(lambda r=role: publisher.execute(f'SET ROLE "{self.inst.roles[r]}"'))
        self.assertDenied(lambda: publisher.execute(f"CREATE TABLE {self.s}.hostile(x int)"))

    def test_the_loader_holds_nothing_in_r1_and_cannot_publish(self):
        """Product path. Actual loader session: USAGE on the schema and nothing else ON THE GATEWAY'S OWN `rw_*` OBJECTS. R2 gave the loader its
        list (INSERT on the thirteen md_* tables, SELECT on two, EXECUTE on the registry's put and get; design 3.3): that list, in the `md_*`
        and `rwp_*` namespaces, is asserted in test_postgres_real_loader.py. This test is about the authority core, where the loader holds
        nothing and cannot publish, and it still holds after R2."""
        loader = self.conn("loader")
        for relation in TABLES + VIEWS:
            self.assertDenied(lambda r=relation: loader.execute(f"SELECT * FROM {self.s}.{r}"))
        for relation in TABLES:
            # DEFAULT VALUES, not INSERT ... SELECT *: several tables have GENERATED ALWAYS identity columns, and PostgreSQL raises that
            # (SQLSTATE 428C9) while it rewrites the statement, before the privilege check at executor start. The first version of this
            # probe died on it, so it showed nothing about privilege. DEFAULT VALUES reaches the privilege check first.
            self.assertDenied(lambda r=relation: loader.execute(f"INSERT INTO {self.s}.{r} DEFAULT VALUES"))
            self.assertDenied(lambda r=relation: loader.execute(f"DELETE FROM {self.s}.{r}"))
            self.assertDenied(lambda r=relation: loader.execute(f"TRUNCATE {self.s}.{r}"))
        for name in sorted(CALLS):
            self.assertDenied(lambda n=name: loader.execute(f"SELECT * FROM {self.s}.{CALLS[n]}"))
        for role in ("owner", "executor", "publisher"):
            self.assertDenied(lambda r=role: loader.execute(f'SET ROLE "{self.inst.roles[r]}"'))

    def test_no_runtime_role_can_write_a_drain_mark(self):
        """Product path (FF1-C04: the issuer's record cannot be forged by a runtime role)."""
        for who in ("executor", "loader", "publisher"):
            conn = self.conn(who)
            self.assertDenied(lambda c=conn: c.execute(f"INSERT INTO {self.s}.rw_drain_mark(context_id,generation,issuer_actor,pd_id,git_commit,doc_sha256,marked_at) "
                                                       "VALUES(%s,1,'x','PD-0001',%s,%s,clock_timestamp())", ("0" * 64, "a" * 40, "b" * 64)))
            self.assertDenied(lambda c=conn: c.execute(f"UPDATE {self.s}.rw_drain_mark SET issuer_actor='y'"))
            self.assertDenied(lambda c=conn: c.execute(f"DELETE FROM {self.s}.rw_drain_mark"))
            self.assertDenied(lambda c=conn: c.execute(f"TRUNCATE {self.s}.rw_drain_mark"))

    def test_hostile_temp_objects_and_search_path_change_nothing(self):
        """Product path. FF1-C04 / T04 'no hostile temp/argument path': TEMPORARY is not granted, and a hostile search_path does not
        move a function off its own schema (it is pinned)."""
        for who in ("executor", "loader", "publisher"):
            conn = self.conn(who)
            self.assertDenied(lambda c=conn: c.execute("CREATE TEMP TABLE rw_mode(singleton boolean, mode text)"))
            self.assertDenied(lambda c=conn: c.execute("CREATE TEMP TABLE rw_head(context_id text)"))
        snap, valid, _result = self.publish()
        owner_id, root_id = self.craft_root(snap.context_id)
        executor = self.conn("executor")
        executor.execute(f"SET search_path = pg_temp, {self.s}")
        begin(executor)
        try:
            lease = self.admit(executor, snap.context_id, 1, "ARCHIVE_READ", owner_id, root_id)
            self.assertEqual(lease.snapshot, snap.data)
        finally:
            rollback(executor)

    def test_hostile_arguments_are_refused_as_malformed(self):
        """Product path. The functions take typed arguments and check their shape; text is never executed."""
        executor = self.conn("executor")
        evil = "x'; DROP SCHEMA %s CASCADE; --" % self.s
        for purpose, context in ((evil, "0" * 64), ("ARCHIVE_READ", evil), ("ARCHIVE_READ", "0" * 63), ("ARCHIVE_READ", "G" * 64), ("", "0" * 64)):
            begin(executor)
            try:
                self.assertRefused("RW_SHAPE", lambda p=purpose, c=context: executor.execute(
                    f"SELECT {self.s}.rw_admit(%s,%s,%s,1,%s,%s,%s,false)", (uuid.uuid4(), uuid.uuid4(), c, p, uuid.uuid4(), "1" * 64)))
            finally:
                rollback(executor)
        self.assertEqual(self.owner.execute("SELECT count(*) FROM pg_namespace WHERE nspname=%s", (self.s,)).fetchone()[0], 1)


class ImmutabilityTests(GatewayCase):
    """T02 'no delete/reinsert head' and the immutability of the authority objects. Product publish and admit, then CRAFTED writes by the
    owner role of the disposable database (E11) that must be refused."""

    def setUp(self):
        super().setUp()
        self.snap, self.valid, _ = self.publish()
        self.ctx = self.snap.context_id
        self.owner_id, self.root_id = self.craft_root(self.ctx)
        self.admit_and_commit(self.conn("executor"), self.ctx, 1, "ARCHIVE_READ", self.owner_id, self.root_id)
        result = self.tool().withdraw(self.ctx, 1, actor=fx.ACTOR, ref=fx.REF)
        self.assertEqual(result.status, 0, result.text)

    def test_snapshot_history_mark_and_root_link_are_immutable(self):
        for table, update in (("rw_snapshot", "SET snapshot=snapshot"), ("rw_history", "SET issuer_actor='x'"), ("rw_drain_mark", "SET issuer_actor='x'"),
                              ("rw_root_link", "SET owner_id=owner_id")):
            self.assertRefused("RW_IMMUTABLE", lambda t=table, u=update: self.owner.execute(f"UPDATE {self.s}.{t} {u}"))
            self.assertRefused("RW_IMMUTABLE", lambda t=table: self.owner.execute(f"DELETE FROM {self.s}.{t}"))
            # every one of these four is referenced by another table, so PostgreSQL's own refusal of TRUNCATE comes first
            self.assertTruncateRefused(table, trigger_expected=False)
        self.assertEqual(len(self.history(self.ctx)), 2)

    def test_the_head_is_never_deleted_or_moved_without_its_history(self):
        self.assertRefused("RW_IMMUTABLE", lambda: self.owner.execute(f"DELETE FROM {self.s}.rw_head WHERE context_id=%s", (self.ctx,)))
        self.assertTruncateRefused("rw_head", trigger_expected=True)
        self.assertRefused("RW_GENERATION_DIFFERS", lambda: self.owner.execute(f"UPDATE {self.s}.rw_head SET rights=rights WHERE context_id=%s", (self.ctx,)))
        self.assertRefused("RW_HEAD_DIFFERS", lambda: self.owner.execute(
            f"UPDATE {self.s}.rw_head SET generation=generation+1 WHERE context_id=%s", (self.ctx,)))
        self.assertRefused("RW_HEAD_DIFFERS", lambda: self.owner.execute(
            f"UPDATE {self.s}.rw_head SET rights=%s WHERE context_id=%s", (Jsonb(fx.ALL_RIGHTS), self.ctx)))
        generation, rights, kind, valid = self.head(self.ctx)
        self.assertEqual((generation, kind, set(rights.values())), (2, "LEASE", {False}))

    def test_history_generations_are_a_chain_and_a_mark_must_precede_the_generation_that_names_it(self):
        base = (f"INSERT INTO {self.s}.rw_history(context_id,generation,rights,expiry_kind,valid_until,basis,issuer_actor,pd_id,git_commit,doc_sha256,recorded_at,drain_mark_id) "
                "VALUES(%s,%s,%s,'LEASE',%s,%s,'x','PD-0001',%s,%s,clock_timestamp(),%s)")
        common = (Jsonb(fx.ALL_RIGHTS), self.valid, Jsonb([]), "a" * 40, "b" * 64)
        self.assertRefused("RW_GENERATION_DIFFERS", lambda: self.owner.execute(base, (self.ctx, 9, *common, None)))
        mark = self.marks(self.ctx)[0]["mark_id"]
        self.assertRefused("RW_MARK_STALE", lambda: self.owner.execute(base, (self.ctx, 3, *common, mark)))
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.owner.execute(base, (self.ctx, 2, *common, None))

    def test_a_lease_row_is_never_deleted_and_its_deadline_never_moves(self):
        self.assertEqual(self.count("rw_lease", "context_id=%s", (self.ctx,)), 1)
        self.assertRefused("RW_IMMUTABLE", lambda: self.owner.execute(f"DELETE FROM {self.s}.rw_lease"))
        self.assertTruncateRefused("rw_lease", trigger_expected=True)
        for column, value in (("complete_by", "complete_by - interval '1 second'"), ("admitted_at", "admitted_at + interval '1 second'"),
                              ("valid_until", "NULL"), ("purpose", "'EXECUTE_CREATE'"), ("operation_id", "gen_random_uuid()"),
                              ("owner_id", "gen_random_uuid()"), ("generation", "generation + 1")):
            self.assertRefused("RW_IMMUTABLE", lambda c=column, v=value: self.owner.execute(f"UPDATE {self.s}.rw_lease SET {c}={v}"))
        # the seal's columns (R3) may change: phase and state digest only
        self.owner.execute(f"UPDATE {self.s}.rw_lease SET phase='SEALED', state_sha256=%s WHERE context_id=%s", ("c" * 64, self.ctx))
        self.assertEqual(self.leases(self.ctx)[0]["phase"], "SEALED")

    def test_the_mode_row_is_never_deleted(self):
        self.assertRefused("RW_IMMUTABLE", lambda: self.owner.execute(f"DELETE FROM {self.s}.rw_mode"))
        self.assertTruncateRefused("rw_mode", trigger_expected=True)


class PublishTests(GatewayCase):
    """T01 / FF1-C03 / reduced FF1-C12. PRODUCT path: the real tool over a real publisher session, snapshots from the factory."""

    def test_publish_in_both_test_scopes_stores_the_verified_bytes_and_opens_the_mode(self):
        for scope in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            snap, valid, result = self.publish(scope=scope)
            ctx = snap.context_id
            self.assertEqual((result.status, result.outcome, result.data["generation"], result.data["created"]), (0, "PUBLISHED", 1, True))
            stored = bytes(self.owner.execute(f"SELECT snapshot FROM {self.s}.rw_snapshot WHERE context_id=%s", (ctx,)).fetchone()[0])
            self.assertEqual(stored, snap.data)
            document = json.loads(stored)
            self.assertEqual((document["scope"], document["origin"]["synthetic"], document["origin"]["market_origin"]), (scope, True, "SYNTHETIC_TEST"))
            self.assertNotIn(b"REAL_SOURCE", stored)                        # I1, I3 on the stored row
            (row,) = self.history(ctx)
            self.assertEqual((row["generation"], row["rights"], row["expiry_kind"], row["valid_until"]), (1, fx.ALL_RIGHTS, "LEASE", valid))
            self.assertEqual((row["issuer_actor"], row["pd_id"], row["git_commit"], row["doc_sha256"]), (fx.ACTOR, "PD-9001", "a" * 40, "b" * 64))
            self.assertEqual([e["source_id"] for e in row["basis"]], sorted(fx.SOURCES))
            self.assertEqual([e["basis"] for e in row["basis"]], ["LEASE_TERM", "NOT_ASSESSED", "NOT_ASSESSED"])
            self.assertLessEqual(row["recorded_at"], self.db_now())
            self.assertEqual(self.head(ctx), (1, fx.ALL_RIGHTS, "LEASE", valid))
            self.assertEqual(self.owner.execute(f"SELECT mode FROM {self.s}.rw_mode").fetchone()[0], "DB_SNAPSHOT_V1")

    def test_t01_editing_a_proposal_cannot_change_a_live_context(self):
        """Mutating the proposal file changes nothing live: a byte edit is refused before the database, a self-consistent edit is a
        DIFFERENT context, and admission returns the stored bytes, never a file."""
        snap, valid, _ = self.publish()
        ctx, data = snap.context_id, self.proposal(snap)
        before = (self.history(ctx), self.head(ctx), bytes(self.owner.execute(f"SELECT snapshot FROM {self.s}.rw_snapshot WHERE context_id=%s", (ctx,)).fetchone()[0]))
        args = dict(rights=fx.ALL_RIGHTS, valid_until=valid, evidence=fx.hg4_shape(self.bound()), actor=fx.ACTOR, ref=fx.REF)
        tool = self.tool()
        refused = tool.publish(data.replace(b'"syn.beta"', b'"syn.betb"', 1), **args)
        self.assertEqual(refused.status, 2)
        self.assertTrue(refused.data["code"].startswith("RW_PROPOSAL_"), refused.text)
        document = json.loads(data)
        document["snapshot"]["members"][0]["payload_sha256"] = fx.sha("edited payload")
        import hashlib
        document["context_id"] = hashlib.sha256(canonical_json(document["snapshot"]).encode()).hexdigest()
        second = tool.publish(canonical_json(document).encode(), **args)
        self.assertEqual((second.status, second.outcome), (0, "PUBLISHED"))
        self.assertNotEqual(second.data["context_id"], ctx)
        after = (self.history(ctx), self.head(ctx), bytes(self.owner.execute(f"SELECT snapshot FROM {self.s}.rw_snapshot WHERE context_id=%s", (ctx,)).fetchone()[0]))
        self.assertEqual(after, before)
        owner_id, root_id = self.craft_root(ctx)
        lease = self.admit_and_commit(self.conn("executor"), ctx, 1, "ARCHIVE_READ", owner_id, root_id)
        self.assertEqual(lease.snapshot, snap.data)
        self.assertEqual(store.digest(lease.snapshot), ctx)

    def test_a_rerun_of_identical_input_returns_the_original_without_a_new_row(self):
        """Reduced FF1-C12: same issuer operation and content reconciles exactly; a conflicting re-run is refused; no new generation."""
        snap, valid, first = self.publish()
        ctx = snap.context_id
        original = self.history(ctx)[0]
        # identical content: reuse the stored entries exactly
        evidence = [store.BasisEntry(e["source_id"], e["basis"], fx.REF, None if "term_end_not_after" not in e else store.parse_utc(e["term_end_not_after"]))
                    for e in original["basis"]]
        again = self.tool().publish(self.proposal(snap), rights=fx.ALL_RIGHTS, valid_until=valid, evidence=evidence, actor=fx.ACTOR, ref=fx.REF)
        self.assertEqual((again.status, again.outcome, again.data["created"], again.data["generation"]), (0, "ALREADY_PUBLISHED", False, 1), again.text)
        self.assertEqual(self.history(ctx), [original])
        for name, override in (("valid_until", dict(valid_until=valid + fx.seconds(1))), ("actor", dict(actor="someone-else")),
                               ("reference", dict(ref=fx.REF_OTHER)), ("rights", dict(rights={**fx.ALL_RIGHTS, "ARCHIVE_EXPORT": False}))):
            args = dict(rights=fx.ALL_RIGHTS, valid_until=valid, evidence=evidence, actor=fx.ACTOR, ref=fx.REF)
            args.update(override)
            conflict = self.tool().publish(self.proposal(snap), **args)
            self.assertEqual((conflict.status, conflict.data["code"]), (2, "RW_PUBLISH_CONFLICT"), name)
        self.assertEqual(self.history(ctx), [original])
        self.assertEqual(self.head(ctx)[0], 1)

    def test_a_lost_acknowledgement_is_unknown_and_the_rerun_reconciles(self):
        """Reduced FF1-C12, product path: the commit succeeded, the acknowledgement was lost. UNKNOWN, no retry; an independent
        connection sees the commit; the identical re-run on a new connection finds it and appends nothing."""
        class LostAcknowledgement(store.RealPublisher):
            def _after_commit(self):
                raise psycopg.OperationalError("the acknowledgement was lost")
        snap = self.snapshot()
        valid = self.db_now() + fx.seconds(120)
        evidence = fx.hg4_shape(self.bound())
        args = dict(rights=fx.ALL_RIGHTS, valid_until=valid, evidence=evidence, actor=fx.ACTOR, ref=fx.REF)
        lost = LostAcknowledgement(self.conn("publisher"), self.s).publish(self.proposal(snap), **args)
        self.assertEqual((lost.status, lost.outcome), (4, "UNKNOWN"))
        self.assertEqual(len(self.history(snap.context_id)), 1)                   # committed: seen from the trusted owner connection
        again = self.tool().publish(self.proposal(snap), **args)
        self.assertEqual((again.status, again.outcome), (0, "ALREADY_PUBLISHED"), again.text)
        self.assertEqual(len(self.history(snap.context_id)), 1)

    def test_a_killed_connection_before_the_commit_is_unknown_and_nothing_remains(self):
        """Reduced FF1-C12, product path: the backend dies before the COMMIT. UNKNOWN (no retry); the trusted connection finds no row;
        the identical re-run then publishes exactly once."""
        admin = self.admin

        class KilledBeforeCommit(store.RealPublisher):
            def _before_commit(self):
                pid = self.conn.execute("SELECT pg_backend_pid()").fetchone()[0]
                admin.execute("SELECT pg_terminate_backend(%s)", (pid,))
                time.sleep(0.3)
        snap = self.snapshot()
        args = dict(rights=fx.ALL_RIGHTS, valid_until=self.db_now() + fx.seconds(120), evidence=fx.hg4_shape(self.bound()), actor=fx.ACTOR, ref=fx.REF)
        killed = KilledBeforeCommit(self.conn("publisher"), self.s).publish(self.proposal(snap), **args)
        self.assertEqual((killed.status, killed.outcome), (4, "UNKNOWN"))
        self.assertEqual(self.history(snap.context_id), [])
        self.assertEqual(self.count("rw_snapshot", "context_id=%s", (snap.context_id,)), 0)
        rerun = self.tool().publish(self.proposal(snap), **args)
        self.assertEqual((rerun.status, rerun.outcome), (0, "PUBLISHED"), rerun.text)
        self.assertEqual(len(self.history(snap.context_id)), 1)

    def test_an_unpublished_context_is_never_admitted(self):
        """FF1-C03 'missing or unpublished head remains HOLD': a context nobody published has no head and no cached fallback, even
        though a snapshot of it exists in memory and the mode is open (another context was published first)."""
        self.publish()
        snap = self.snapshot(label="unpublished")
        executor = self.conn("executor")
        begin(executor)
        try:
            self.assertRefused("RW_NOT_FOUND", lambda: self.admit(executor, snap.context_id, 1, "ARCHIVE_READ", uuid.uuid4(), uuid.uuid4()))
        finally:
            rollback(executor)

    def test_a_missing_decision_reference_is_refused_by_the_database_too(self):
        """Product path, direct call of the function (the tool refuses first): every part of the triple and the actor is required."""
        snap = self.snapshot()
        publisher = self.conn("publisher")
        call = f"SELECT * FROM {self.s}.rw_publish(%s,%s,%s,%s,%s,%s,%s,%s)"
        good = dict(actor="a", pd="PD-9001", commit="a" * 40, doc="b" * 64)
        for name, override in (("no actor", dict(actor=None)), ("empty actor", dict(actor="")), ("no PD", dict(pd=None)), ("bad PD", dict(pd="PD-1")),
                               ("no commit", dict(commit=None)), ("short commit", dict(commit="a" * 39)), ("no hash", dict(doc=None)),
                               ("malformed hash", dict(doc="B" * 64))):
            ref = {**good, **override}
            self.assertRefused("RW_DECISION_REF_REQUIRED", lambda r=ref: publisher.execute(
                call, (snap.data, Jsonb(fx.ALL_RIGHTS), None, Jsonb([]), r["actor"], r["pd"], r["commit"], r["doc"])), detail=None)
        self.assertEqual(self.count("rw_snapshot", "context_id=%s", (snap.context_id,)), 0)

    def test_publish_refuses_malformed_snapshots(self):
        """Product path, direct call: the function re-checks the shape of what it stores."""
        snap = self.snapshot()
        publisher = self.conn("publisher")
        call = f"SELECT * FROM {self.s}.rw_publish(%s,%s,NULL,%s,'a','PD-9001',%s,%s)"
        document = json.loads(snap.data)
        variants = {"not json": b"not json", "wrong schema": canonical_json({**document, "schema": "x"}).encode(),
                    "unknown scope": canonical_json({**document, "scope": "OTHER"}).encode(),
                    "no members": canonical_json({**document, "members": []}).encode(),
                    "member without hash": canonical_json({**document, "members": [{"source_id": "syn.alpha"}]}).encode()}
        for name, data in variants.items():
            self.assertRefused("RW_SHAPE", lambda d=data: publisher.execute(call, (d, Jsonb(fx.ALL_RIGHTS), Jsonb([]), "a" * 40, "b" * 64)))
        self.assertRefused("RW_SHAPE", lambda: publisher.execute(call, (snap.data, Jsonb({"ARCHIVE_READ": True}), Jsonb([]), "a" * 40, "b" * 64)))


class ExpiryEvidenceTests(GatewayCase):
    """FF1-C06 / T07 expiry evidence (E14), PRODUCT path through the tool, on invented fixture references. The kind is derived by the
    database from the stored snapshot's member sources; the tool cannot name a source."""

    def refused(self, valid_until, evidence, reason, label):
        snap = self.snapshot(label=label)
        _snap, _valid, result = self.publish(snap, valid_until=valid_until, evidence=evidence, expect_ok=False)
        self.assertEqual((result.status, result.data.get("code"), result.data.get("detail")), (2, "RW_EXPIRY_UNSUPPORTED", reason), label + ": " + result.text)
        self.assertEqual(self.count("rw_snapshot", "context_id=%s", (snap.context_id,)), 0, label)
        self.assertEqual(self.count("rw_history", "context_id=%s", (snap.context_id,)), 0, label)

    def test_every_unsupported_shape_of_evidence_is_refused_at_publish(self):
        alpha, beta, cal = fx.SOURCES
        ref, bound = fx.REF, self.bound()
        far = self.db_now() + fx.seconds(120)
        no = lambda s: store.BasisEntry(s, "NO_EXPIRY_READING", ref)   # noqa: E731
        na = lambda s: store.BasisEntry(s, "NOT_ASSESSED", ref)        # noqa: E731
        lt = lambda s, b=bound: store.BasisEntry(s, "LEASE_TERM", ref, b)  # noqa: E731
        cases = [
            ("none-without-entries", None, [], "BASIS_COUNT"),
            ("none-with-some-readings-omitting-the-licensed-source", None, [no(beta), no(cal)], "BASIS_COUNT"),
            ("none-with-a-lease-term", None, [lt(alpha), no(beta), no(cal)], "NO_VALID_UNTIL"),
            ("none-with-not-assessed", None, [no(alpha), no(beta), na(cal)], "NOT_EVERY_SOURCE_HAS_A_READING"),
            ("lease-without-a-lease-term", far, [na(alpha), na(beta), na(cal)], "NOT_EVERY_SOURCE_HAS_A_READING"),
            ("lease-term-without-valid-until", None, fx.hg4_shape(bound), "NO_VALID_UNTIL"),
            ("member-without-an-entry", far, [lt(alpha), na(beta)], "BASIS_COUNT"),
            ("entry-for-a-non-member", far, [lt(alpha), na(beta), na("syn.other")], "NON_MEMBER_ENTRY"),
            ("duplicate-entry", far, [lt(alpha), na(beta), na(beta)], "DUPLICATE_ENTRY"),
            ("valid-until-after-the-upper-bound", bound + fx.seconds(1), fx.hg4_shape(bound), "PLAUSIBILITY"),
            ("valid-until-with-none", far, [no(alpha), no(beta), no(cal)], "VALID_UNTIL_WITH_NONE"),
        ]
        for label, valid_until, evidence, reason in cases:
            self.refused(valid_until, evidence, reason, label)

    def test_the_supported_shapes_are_accepted_and_each_gets_exactly_one_kind(self):
        bound = self.bound(600)
        cases = {
            "lease-hg4-shape": (bound - fx.seconds(30), fx.hg4_shape(bound), "LEASE"),
            "lease-equal-to-the-bound": (bound, fx.hg4_shape(bound), "LEASE"),
            "none-with-a-reading-for-every-source": (None, fx.none_shape(), "NONE"),
        }
        for label, (valid_until, evidence, kind) in cases.items():
            snap, valid, result = self.publish(self.snapshot(label=label), valid_until=valid_until, evidence=evidence, expect_ok=False)
            self.assertEqual(result.status, 0, label + ": " + result.text)
            (row,) = self.history(snap.context_id)
            self.assertEqual((row["expiry_kind"], row["valid_until"]), (kind, valid_until), label)
            self.assertEqual(len(row["basis"]), len(fx.SOURCES), label)

    def test_a_none_context_never_lapses_and_its_lease_deadline_is_w(self):
        snap, _none, result = self.publish(valid_until=None, evidence=fx.none_shape())
        self.assertEqual(result.status, 0, result.text)
        ctx = snap.context_id
        owner_id, root_id = self.craft_root(ctx)
        self.admit_and_commit(self.conn("executor"), ctx, 1, "ARCHIVE_READ", owner_id, root_id)
        (lease,) = self.leases(ctx)
        self.assertIsNone(lease["valid_until"])
        self.assertEqual(lease["complete_by"] - lease["admitted_at"], fx.seconds(self.inst.w_seconds))

    def test_the_publish_output_and_the_status_view_print_the_upper_bound_wording(self):
        bound = self.bound(600)
        snap, valid, result = self.publish(valid_until=bound - fx.seconds(5), evidence=fx.hg4_shape(bound))
        self.assertIn(store.PLAUSIBILITY_WORDING, result.text)
        status = self.tool().status(snap.context_id)
        self.assertIn(store.PLAUSIBILITY_WORDING, status.text)
        self.assertIn("recorded upper bound %s" % store.iso(bound), status.text)
        for text in (result.text, status.text):
            self.assertNotIn("within", text.lower())
            self.assertNotIn("margin", text.lower())

    def test_admit_rederives_the_kind_from_the_stored_snapshot_and_entries(self):
        """E11 CRAFTED rows (not product evidence): a stored kind or entry set that the stored snapshot's member sources do not support
        is refused at admit, UNKNOWN is never admitted, and a correct crafted row is admitted (the positive control)."""
        snap = self.snapshot()
        future, bound = self.db_now() + fx.seconds(300), self.bound(900)
        entry = fx.entry_json
        alpha, beta, cal = fx.SOURCES
        crafts = {
            "none-with-readings-for-only-some-sources": dict(kind="NONE", valid_until=None, basis=[entry(beta, "NO_EXPIRY_READING"), entry(cal, "NO_EXPIRY_READING")], reason="BASIS_COUNT"),
            "none-with-no-entries": dict(kind="NONE", valid_until=None, basis=[], reason="BASIS_COUNT"),
            "stored-unknown": dict(kind="UNKNOWN", valid_until=None, basis=[], reason="BASIS_COUNT"),
            "lease-without-a-lease-term": dict(kind="LEASE", valid_until=future, basis=[entry(s, "NOT_ASSESSED") for s in fx.SOURCES],
                                               reason="NOT_EVERY_SOURCE_HAS_A_READING"),
            "lease-with-a-non-member-entry": dict(kind="LEASE", valid_until=future, basis=[entry(alpha, "LEASE_TERM", bound=bound), entry(beta, "NOT_ASSESSED"),
                                                                                         entry("syn.other", "NOT_ASSESSED")], reason="NON_MEMBER_ENTRY"),
        }
        executor = self.conn("executor")
        for label, craft in crafts.items():
            data = canonical_json({**json.loads(snap.data), "release": {**json.loads(snap.data)["release"], "release_id": fx.sha(label)}}).encode()
            ctx = self.craft_context(data, kind=craft["kind"], valid_until=craft["valid_until"], basis=craft["basis"])
            owner_id, root_id = self.craft_root(ctx)
            begin(executor)
            try:
                self.assertRefused("RW_EXPIRY_HOLD", lambda c=ctx, o=owner_id, r=root_id: self.admit(executor, c, 1, "ARCHIVE_READ", o, r), detail=craft["reason"])
            finally:
                rollback(executor)
        good = self.craft_context(canonical_json({**json.loads(snap.data), "release": {**json.loads(snap.data)["release"], "release_id": fx.sha("good")}}).encode(),
                                  kind="LEASE", valid_until=future, basis=[entry(alpha, "LEASE_TERM", bound=bound), entry(beta, "NOT_ASSESSED"), entry(cal, "NOT_ASSESSED")])
        owner_id, root_id = self.craft_root(good)
        self.admit_and_commit(executor, good, 1, "ARCHIVE_READ", owner_id, root_id)


class FreshInstallTests(GatewayCase):
    """A schema nobody has published into: the mode starts CLOSED and the first publish opens it."""

    INSTALL = "fresh"

    def test_closed_mode_refuses_admission_until_the_first_publish(self):
        self.assertEqual(self.owner.execute(f"SELECT mode FROM {self.s}.rw_mode").fetchone()[0], "CLOSED")
        executor = self.conn("executor")
        begin(executor)
        try:
            self.assertRefused("RW_MODE_HOLD", lambda: self.admit(executor, "0" * 64, 1, "ARCHIVE_READ", uuid.uuid4(), uuid.uuid4()))
        finally:
            rollback(executor)
        snap, valid, result = self.publish()
        self.assertEqual(result.status, 0, result.text)
        self.assertEqual(self.owner.execute(f"SELECT mode FROM {self.s}.rw_mode").fetchone()[0], "DB_SNAPSHOT_V1")
        owner_id, root_id = self.craft_root(snap.context_id)
        self.admit_and_commit(executor, snap.context_id, 1, "ARCHIVE_READ", owner_id, root_id)


class MaintenanceHoldTests(GatewayCase):
    """The mode row's third state. Its own install, because the test changes the mode."""

    INSTALL = "hold"

    def test_a_maintenance_hold_refuses_admission_publish_and_renewal(self):
        """E11 crafted: the owner role sets MAINTENANCE_HOLD (no product command does)."""
        snap, valid, _ = self.publish()
        owner_id, root_id = self.craft_root(snap.context_id)
        self.owner.execute(f"UPDATE {self.s}.rw_mode SET mode='MAINTENANCE_HOLD'")
        try:
            executor = self.conn("executor")
            begin(executor)
            try:
                self.assertRefused("RW_MODE_HOLD", lambda: self.admit(executor, snap.context_id, 1, "ARCHIVE_READ", owner_id, root_id))
            finally:
                rollback(executor)
            again = self.publish(self.snapshot(label="held"), expect_ok=False)[2]
            self.assertEqual((again.status, again.data["code"]), (2, "RW_MODE_HOLD"))
            renewed = self.renew(snap.context_id, 1, valid_until=valid + fx.seconds(10))
            self.assertEqual((renewed.status, renewed.data["code"]), (2, "RW_MODE_HOLD"))
        finally:
            self.owner.execute(f"UPDATE {self.s}.rw_mode SET mode='DB_SNAPSHOT_V1'")


class InstallKindGuardTests(GatewayCase):
    """Design 4.2, both directions. A TEST install refuses a REAL-scope snapshot at publish and at admit (this class); a REAL install
    refuses a SYNTHETIC_TEST or TEST_SWITCH snapshot (the class below). R1 asserts the install-kind code only."""

    def real_scope_bytes(self):
        """An in-memory snapshot whose SCOPE FIELD ALONE is REAL: synthetic sources, synthetic origin labels, no REAL_SOURCE string
        anywhere (design 4.2). Built from the factory's snapshot; never stored by the publish path."""
        snap = self.snapshot()
        data = canonical_json({**json.loads(snap.data), "scope": "REAL"}).encode()
        self.assertNotIn(b"REAL_SOURCE", data)
        return data

    def test_publish_into_a_test_install_refuses_a_real_scope_snapshot(self):
        """Product function (called through a test connection, as design 4.2 says) on in-memory bytes; nothing is stored."""
        data = self.real_scope_bytes()
        publisher = self.conn("publisher")
        error = self.assertRefused("RW_PUBLISH_REFUSED", lambda: publisher.execute(
            f"SELECT * FROM {self.s}.rw_publish(%s,%s,NULL,%s,'a','PD-9001',%s,%s)", (data, Jsonb(fx.ALL_RIGHTS), Jsonb([]), "a" * 40, "b" * 64)))
        listed = (error.diag.message_detail or "").split(",")
        self.assertIn("RW_INSTALL_KIND", listed)
        # R2 wired the validators: the R1 placeholder code is gone and the REAL branch lists every failed predicate (design 4.2). These
        # bytes carry synthetic origin labels, so O1 fails; nothing is registered, so O3 fails and the candidate is missing; no source
        # record carries a terms check, so O2 fails.
        self.assertNotIn("RW_REAL_SCOPE_UNWIRED", listed)
        # R3 adds the origin-label code (RW_ORIGIN_MISMATCH): the bytes carry the synthetic labels a real scope may not carry.
        self.assertEqual(listed, ["RW_INSTALL_KIND", "RW_ORIGIN_MISMATCH", "RW_O1_SYNTHETIC_SOURCE", "RW_O2_TERMS_CHECK", "RW_O3_ACQUISITION", "RW_PROV_CANDIDATE_MISSING"])
        import hashlib
        self.assertEqual(self.count("rw_snapshot", "context_id=%s", (hashlib.sha256(data).hexdigest(),)), 0)

    def test_the_tool_refuses_a_relabelled_proposal_before_the_database(self):
        data = self.real_scope_bytes()
        document = {"context_id": store.digest(data), "schema": "finweb.real_proposal/1", "snapshot": json.loads(data)}
        result = self.tool().publish(canonical_json(document).encode(), rights=fx.ALL_RIGHTS, valid_until=None, evidence=[], actor=fx.ACTOR, ref=fx.REF)
        self.assertEqual((result.status, result.data["code"]), (2, "RW_ORIGIN_MISMATCH"))

    def test_admit_in_a_test_install_refuses_a_real_scope_row(self):
        """E11 CRAFTED row (not product evidence), with a control that differs only in the scope field."""
        future, bound = self.db_now() + fx.seconds(300), self.bound(900)
        basis = fx.hg4_shape(bound)
        entries = [e.as_json() for e in basis]
        executor = self.conn("executor")
        crafted = self.craft_context(self.real_scope_bytes(), kind="LEASE", valid_until=future, basis=entries)
        owner_id, root_id = self.craft_root(crafted)
        begin(executor)
        try:
            self.assertRefused("RW_INSTALL_KIND", lambda: self.admit(executor, crafted, 1, "ARCHIVE_READ", owner_id, root_id))
        finally:
            rollback(executor)
        control = self.craft_context(self.snapshot().data, kind="LEASE", valid_until=future, basis=entries)
        owner_id, root_id = self.craft_root(control)
        self.admit_and_commit(executor, control, 1, "ARCHIVE_READ", owner_id, root_id)


class RealInstallRefusesTestScopesTests(GatewayCase):
    """The other direction. The install is a disposable database whose kind row was written REAL by the owner role (E11 crafted
    fixture: the TEST provisioner cannot write REAL). It receives no real content. Snapshots are made in a TEST install and carried
    as bytes."""

    INSTALL = "realkind"
    KIND = "REAL"

    def setUp(self):
        super().setUp()
        self.core = KIT.install("core", w_seconds=4, kind="TEST")
        core_executor = self.core.connect("executor")
        self.addCleanup(core_executor.close)
        self.test_snapshots = {
            "SYNTHETIC_TEST": real_scope.make_snapshot(core_executor, self.core.schema, "SYNTHETIC_TEST", **fx.content(self.tag("a"))),
            "TEST_SWITCH": real_scope.make_snapshot(core_executor, self.core.schema, "TEST_SWITCH", test_switch=True, **fx.content(self.tag("b"))),
        }

    def test_the_install_reports_real_and_the_factory_refuses_test_scopes_there(self):
        self.assertEqual(real_scope.read_install_kind(self.factory, self.s), ("REAL", 4))
        for name in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            with self.assertRaises(real_scope.ScopeError) as caught:
                real_scope.make_snapshot(self.factory, self.s, name, test_switch=(name == "TEST_SWITCH"), **fx.content(self.tag(name)))
            self.assertEqual(caught.exception.code, "RW_INSTALL_KIND", name)

    def test_publish_refuses_carried_bytes_of_both_test_scopes(self):
        publisher = self.conn("publisher")
        for name, snap in self.test_snapshots.items():
            error = self.assertRefused("RW_PUBLISH_REFUSED", lambda d=snap.data: publisher.execute(
                f"SELECT * FROM {self.s}.rw_publish(%s,%s,NULL,%s,'a','PD-9001',%s,%s)", (d, Jsonb(fx.ALL_RIGHTS), Jsonb([]), "a" * 40, "b" * 64)))
            self.assertEqual((error.diag.message_detail or "").split(","), ["RW_INSTALL_KIND"], name)
            self.assertEqual(self.count("rw_snapshot", "context_id=%s", (snap.context_id,)), 0, name)

    def test_admit_refuses_a_crafted_row_of_the_same_bytes(self):
        """E11 CRAFTED row (not product evidence)."""
        future, bound = self.db_now() + fx.seconds(300), self.bound(900)
        entries = [e.as_json() for e in fx.hg4_shape(bound)]
        executor = self.conn("executor")
        for name, snap in self.test_snapshots.items():
            ctx = self.craft_context(snap.data, kind="LEASE", valid_until=future, basis=entries)
            owner_id, root_id = self.craft_root(ctx)
            begin(executor)
            try:
                self.assertRefused("RW_INSTALL_KIND", lambda c=ctx, o=owner_id, r=root_id: self.admit(executor, c, 1, "ARCHIVE_READ", o, r))
            finally:
                rollback(executor)
            self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 0, name)


class ListRootsTests(GatewayCase):
    """The owner-scoped enumeration (design 2.4): identifiers only, no lease needed. Roots are an E11 crafted fixture."""

    def test_the_owner_sees_only_their_own_roots_as_identifiers(self):
        snap, valid, _ = self.publish()
        ctx = snap.context_id
        owner_a, root_a1 = self.craft_root(ctx)
        _same, root_a2 = self.craft_root(ctx, owner_id=owner_a)
        owner_b, root_b = self.craft_root(ctx)
        executor = self.conn("executor")
        rows = store.list_roots(executor, self.s, owner_a)
        self.assertEqual(sorted(rows), sorted([(root_a1, ctx, 1), (root_a2, ctx, 1)]))
        self.assertEqual(store.list_roots(executor, self.s, owner_b), [(root_b, ctx, 1)])
        self.assertEqual(store.list_roots(executor, self.s, uuid.uuid4()), [])
        self.assertEqual({len(r) for r in rows}, {3})
        self.assertRefused("RW_SHAPE", lambda: executor.execute(f"SELECT * FROM {self.s}.rw_list_roots(NULL::uuid)"))
        self.assertDenied(lambda: self.conn("publisher").execute(f"SELECT * FROM {self.s}.rw_list_roots(%s)", (owner_a,)))
        self.assertDenied(lambda: self.conn("loader").execute(f"SELECT * FROM {self.s}.rw_list_roots(%s)", (owner_a,)))
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 0)               # no lease is needed or written


class NewRootTests(GatewayCase):
    """Only rw_admit(new_root) under EXECUTE_CREATE registers a root, and a registered root without a portfolio fails by COMMIT."""

    def test_a_new_root_without_a_portfolio_row_fails_at_commit_through_the_deferred_key(self):
        """Product admit; the owner's app_user row is an E11 crafted fixture (R1 has no create to write it)."""
        snap, valid, _ = self.publish()
        ctx = snap.context_id
        owner_id, root_id = uuid.uuid4(), uuid.uuid4()
        self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
        executor = self.conn("executor")
        begin(executor)
        try:
            self.admit(executor, ctx, 1, "EXECUTE_CREATE", owner_id, root_id, new_root=True)
            with self.assertRaises(psycopg.errors.ForeignKeyViolation) as caught:
                commit(executor)
            self.assertIn("rw_root_link_portfolio_fkey", str(caught.exception))
        finally:
            rollback(executor)
        self.assertEqual(self.count("rw_root_link", "root_id=%s", (root_id,)), 0)
        self.assertEqual(self.count("rw_lease", "root_id=%s", (root_id,)), 0)

    def test_the_new_root_gate_refuses_everything_else(self):
        snap, valid, _ = self.publish()
        ctx = snap.context_id
        owner_id, root_id = self.craft_root(ctx)
        executor = self.conn("executor")
        unknown_owner, unknown_root = uuid.uuid4(), uuid.uuid4()
        cases = {
            "unregistered root without new_root": (unknown_owner, unknown_root, "EXECUTE_CREATE", False),
            "new_root for a read purpose": (owner_id, uuid.uuid4(), "ARCHIVE_READ", True),
            "new_root for an owner with no account": (unknown_owner, unknown_root, "EXECUTE_CREATE", True),
            "new_root on an existing root": (owner_id, root_id, "EXECUTE_CREATE", True),
            "another owner's root": (uuid.uuid4(), root_id, "ARCHIVE_READ", False),
        }
        for label, (o, r, purpose, new_root) in cases.items():
            begin(executor)
            try:
                self.assertRefused("RW_NOT_FOUND", lambda o=o, r=r, p=purpose, n=new_root: self.admit(executor, ctx, 1, p, o, r, new_root=n))
            finally:
                rollback(executor)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 0)


if __name__ == "__main__":
    import unittest
    unittest.main()
