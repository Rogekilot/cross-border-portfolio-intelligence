"""F1 R3, PostgreSQL: the thirteen lease-checked `md_*` READ FUNCTIONS (design 2.6 item 6; PD-0069; PD-0070 decision 2).

The rows are an invented release written by the loader role's own `write_release` (R2; E11 only in that the identity rows it points at were
written by the owner role of the disposable database). EVERY test here is "E11 crafted probe, not product evidence" (technical review L-3): the
executor session calls the SQL functions directly, there is no `read_release` before R5, and the root and the lease are crafted. What the tests
show is the SQL of the functions and their grants. Every refusal asserts the function's code, its DETAIL reason and that no row was returned.
R5 adds the test of `read_release` through these functions (T-m); R3 shows the functions.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402

import marketdata_exit_kit as x  # noqa: E402
import pg_market_kit as pk  # noqa: E402
import real_gateway_fixtures as fx  # noqa: E402
from persistence import market_data_store as mds, real_roles, real_scope  # noqa: E402
from real_gateway_kit import GatewayCase, begin, commit, rollback, setUpModule, tearDownModule  # noqa: E402,F401
from test_postgres_market_data_store import rich_release  # noqa: E402

# Written by hand from design 2.6 item 6 (not read from real_roles).
MD_TABLES = ("md_file", "md_release", "md_release_file", "md_quote", "md_fx_rate", "md_corporate_action", "md_benchmark", "md_benchmark_point",
             "md_adjusted_quote", "md_calendar", "md_series_exclusion", "md_risk_free", "md_risk_free_point")
# Rows of the release `rich_release` writes, per table (the same hand count as test_postgres_real_loader.RICH_ROWS).
RICH_ROWS = {"md_file": 7, "md_release": 1, "md_release_file": 7, "md_quote": 1, "md_fx_rate": 1, "md_corporate_action": 5, "md_benchmark": 1,
             "md_benchmark_point": 2, "md_adjusted_quote": 1, "md_calendar": 1, "md_series_exclusion": 1, "md_risk_free": 1, "md_risk_free_point": 2}
FUNCTIONS = {t: "rw_md_" + t[len("md_"):] for t in MD_TABLES}
CODE = "RW_MD_READ_REFUSED"


class MdCase(GatewayCase):
    INSTALL = "mdread"
    W = 30

    def setUp(self):
        super().setUp()
        if self.count("issuer") == 0:
            pk.insert_identity(self.owner, x.identity())              # E11: the listings the observation tables point at
        loader = self.conn("loader")
        loader.execute(f'SET search_path TO "{self.s}", pg_temp')
        self.release, manifests, contents, calendars = rich_release(x.identity())
        mds.write_release(loader, self.release, manifests, contents, calendars, count_rows=False)    # idempotent across the tests of an install
        self.rid = self.release.release_id
        # L-4 (technical review of R3): a STRAY md_file row that no release lists. `rw_md_file` must return the files `md_release_file` lists for the
        # release and not the whole table; without the stray row the release filter was not observable (a mutant without it passed).
        self.stray = fx.sha("a stray md_file row no release lists")
        self.owner.execute(
            f"INSERT INTO {self.s}.md_file(file_sha256,source_id,data_kind,usage_scope,retrieval_time,declared_adjustment,market,manifest) "
            "SELECT %s,source_id,data_kind,usage_scope,retrieval_time,declared_adjustment,market,manifest FROM "
            f"{self.s}.md_file WHERE file_sha256<>%s ORDER BY file_sha256 LIMIT 1 ON CONFLICT DO NOTHING", (self.stray, self.stray))
        self.executor = self.conn("executor")

    # ---- a published context whose snapshot names the release, and a crafted root for it ------------------------------------------
    def context(self, *, valid_in=300.0, scope="SYNTHETIC_TEST"):
        content = {**fx.content(self.tag("md")), "release_id": self.rid}
        snap = real_scope.make_snapshot(self.factory, self.s, scope, test_switch=(scope == "TEST_SWITCH"), **content)
        _snap, valid, _result = self.publish(snap, valid_in=valid_in)
        owner_id, root_id = self.craft_root(snap.context_id)
        return snap.context_id, valid, owner_id, root_id

    def call(self, conn, table, release=None):
        release = self.rid if release is None else release
        return conn.execute(f"SELECT * FROM {self.s}.{FUNCTIONS[table]}(%s)", (release,)).fetchall()

    def counts(self, conn, release=None):
        return {t: len(self.call(conn, t, release)) for t in MD_TABLES}

    def refused(self, conn, table, reason, release=None):
        """The call raises the function's refusal with `reason` in DETAIL and SQLSTATE P0001. Inside a transaction the call runs under a
        savepoint (a refused statement aborts its transaction otherwise), so one lease can be asked thirteen times."""
        in_transaction = conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE
        if in_transaction:
            conn.execute("SAVEPOINT md_call")
        with self.assertRaises(psycopg.errors.RaiseException, msg=table) as caught:
            self.call(conn, table, release)
        if in_transaction:
            conn.execute("ROLLBACK TO SAVEPOINT md_call")
        error = caught.exception
        self.assertEqual((error.diag.message_primary, (error.diag.message_detail or "").strip(), error.sqlstate), (CODE, reason, "P0001"), table)

    def refused_everywhere(self, conn, reason, release=None):
        for table in MD_TABLES:
            self.refused(conn, table, reason, release)

    def leased(self, purpose, ctx, owner_id, root_id, conn=None):
        conn = conn or self.executor
        begin(conn)
        return self.admit(conn, ctx, 1, purpose, owner_id, root_id)


class FunctionsAndGrantsTests(MdCase):
    def test_the_thirteen_functions_match_the_md_tables_and_only_the_executor_may_execute_them(self):
        """E11 crafted probe, not product evidence (catalog). A table a later migration adds without a function is a finding: the set of md_* tables of the schema is
        exactly the thirteen, each has its function, each function returns that table's row type, and EXECUTE is the executor's alone."""
        tables = {r[0] for r in self.admin.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind IN ('r','p') AND c.relname LIKE 'md\\_%%'",
            (self.s,)).fetchall()}
        self.assertEqual(tables, set(MD_TABLES))
        rows = self.admin.execute(
            "SELECT p.proname,p.prosecdef,p.proretset,t.typrelid::regclass::text,p.proconfig,p.proowner::regrole::text,p.provolatile "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_type t ON t.oid=p.prorettype WHERE n.nspname=%s AND p.proname LIKE 'rw\\_md\\_%%' "
            "AND p.proname<>'rw_md_guard'", (self.s,)).fetchall()
        self.assertEqual({r[0] for r in rows}, set(FUNCTIONS.values()))
        for name, secdef, setof, row_type, config, owner, volatility in rows:
            table = [t for t, f in FUNCTIONS.items() if f == name][0]
            self.assertEqual((secdef, setof, row_type, owner, volatility), (True, True, f'"{self.s}".{table}' if '"' in row_type else f"{self.s}.{table}",
                                                                           self.inst.roles["owner"], "v"), name)
            self.assertEqual([c.replace(" ", "") for c in config], [f"search_path=pg_catalog,{self.s},pg_temp"], name)
        who = {role: self.inst.roles[role] for role in ("executor", "loader", "publisher")}
        for name in FUNCTIONS.values():
            for role, rolname in who.items():
                held = self.admin.execute("SELECT has_function_privilege(%s::name,p.oid,'EXECUTE') FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                                          "WHERE n.nspname=%s AND p.proname=%s", (rolname, self.s, name)).fetchone()[0]
                self.assertEqual(held, role == "executor", (name, role))
            public = self.admin.execute("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a "
                                        "WHERE n.nspname=%s AND p.proname=%s AND a.grantee=0", (self.s, name)).fetchone()[0]
            self.assertEqual(public, 0, name)
        # the guard they call is nobody's: no runtime role may execute it directly
        for role, rolname in who.items():
            self.assertFalse(self.admin.execute("SELECT has_function_privilege(%s::name,p.oid,'EXECUTE') FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                                                "WHERE n.nspname=%s AND p.proname='rw_md_guard'", (rolname, self.s)).fetchone()[0], role)

    def test_the_shared_list_names_exactly_these_functions(self):
        self.assertEqual({n for n, _a in real_roles.MD_READ_FUNCTIONS}, set(FUNCTIONS.values()))
        self.assertEqual({a for _n, a in real_roles.MD_READ_FUNCTIONS}, {"text"})
        for kind in ("TEST", "REAL"):
            self.assertTrue(set(real_roles.MD_READ_FUNCTIONS) <= real_roles.role_lists(kind)["executor"]["functions"])
            for role in ("loader", "publisher", "public"):
                self.assertFalse(set(real_roles.MD_READ_FUNCTIONS) & real_roles.role_lists(kind)[role]["functions"])

    def test_the_executor_has_no_direct_select_on_any_md_table_with_or_without_a_lease(self):
        """E11 crafted probe, not product evidence: 42501 for each of the thirteen tables, with no lease and under a lease of each of the four purposes (a lease changes
        nothing about a table privilege), and the catalog finds no table, column or default privilege of the executor or of public on them."""
        ctx, _valid, owner_id, root_id = self.context()
        for table in MD_TABLES:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege, msg=table) as caught:
                self.executor.execute(f"SELECT count(*) FROM {self.s}.{table}")
            self.assertEqual(caught.exception.sqlstate, "42501")
        for purpose in ("EXECUTE_CREATE", "EXECUTE_REPRODUCE", "ARCHIVE_READ", "ARCHIVE_EXPORT"):
            for table in MD_TABLES:
                with self.subTest(purpose=purpose, table=table):
                    try:
                        self.leased(purpose, ctx, owner_id, root_id)
                        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                            self.executor.execute(f"SELECT * FROM {self.s}.{table}")
                    finally:
                        rollback(self.executor)
        role = self.inst.roles["executor"]
        for table in MD_TABLES:
            for who in (role, "public"):
                self.assertFalse(self.admin.execute("SELECT has_any_column_privilege(%s::name,%s::regclass,'SELECT,INSERT,UPDATE,REFERENCES')",
                                                    (who, f'"{self.s}"."{table}"')).fetchone()[0], (who, table))
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                    self.assertFalse(self.admin.execute("SELECT has_table_privilege(%s::name,%s::regclass,%s)", (who, f'"{self.s}"."{table}"', privilege)).fetchone()[0],
                                     (who, table, privilege))

    def test_without_a_lease_every_function_refuses_and_returns_no_row(self):
        """E11 crafted probe, not product evidence: the executor's connection with no admission, in autocommit and inside a transaction that never admitted."""
        self.refused_everywhere(self.executor, "NO_LEASE")
        begin(self.executor)
        try:
            self.refused(self.executor, "md_quote", "NO_LEASE")
        finally:
            rollback(self.executor)


class PositiveControlTests(MdCase):
    def test_an_open_create_lease_and_a_reproduce_lease_read_the_rows_of_the_snapshots_release(self):
        """E11 crafted probe, not product evidence (the executor session, the release rows and the crafted root are E11 fixtures): each function returns exactly that
        release's rows, md_file the files md_release_file lists for it. E11 crafted probe, not product evidence for the real branch's read."""
        ctx, _valid, owner_id, root_id = self.context()
        for purpose in ("EXECUTE_CREATE", "EXECUTE_REPRODUCE"):
            with self.subTest(purpose=purpose):
                try:
                    self.leased(purpose, ctx, owner_id, root_id)
                    self.assertEqual(self.counts(self.executor), RICH_ROWS)
                    files = {bytes(r[0]) if isinstance(r[0], (bytes, memoryview)) else r[0] for r in self.executor.execute(
                        f"SELECT file_sha256 FROM {self.s}.rw_md_file(%s)", (self.rid,)).fetchall()}
                    listed = {r[0] for r in self.owner.execute(f"SELECT file_sha256 FROM {self.s}.md_release_file WHERE release_id=%s", (self.rid,)).fetchall()}
                    self.assertEqual(files, listed)
                    self.assertNotIn(self.stray, files)                                # the stored file no release lists is not returned
                    self.assertEqual(self.count("md_file", "file_sha256=%s", (self.stray,)), 1)             # and it is stored (the control)
                    self.assertGreater(self.count("md_file"), len(files))
                    # the rows are the stored rows, column for column
                    for table in ("md_quote", "md_release", "md_calendar"):
                        stored = self.owner.execute(f"SELECT to_jsonb(t) FROM {self.s}.{table} t {'WHERE release_id=%s' if table != 'md_release' else 'WHERE release_id=%s'}", (self.rid,)).fetchall()
                        seen = self.executor.execute(f"SELECT to_jsonb(t) FROM {self.s}.{FUNCTIONS[table]}(%s) t", (self.rid,)).fetchall()
                        self.assertEqual(sorted(map(str, stored)), sorted(map(str, seen)), table)
                finally:
                    rollback(self.executor)


class PurposeAndReleaseRefusalTests(MdCase):
    def test_read_and_export_leases_get_none_of_it(self):
        ctx, _valid, owner_id, root_id = self.context()
        for purpose in ("ARCHIVE_READ", "ARCHIVE_EXPORT"):
            with self.subTest(purpose=purpose):
                try:
                    self.leased(purpose, ctx, owner_id, root_id)
                    self.refused_everywhere(self.executor, "PURPOSE")
                finally:
                    rollback(self.executor)

    def test_a_release_that_is_not_the_snapshots_is_refused(self):
        """E11 crafted probe, not product evidence. Another release, an unreferenced candidate (a release id nothing names), a NULL and the empty string: all RELEASE, with a lease that
        reads the right one in the same transaction beforehand (the control)."""
        ctx, _valid, owner_id, root_id = self.context()
        for label, other in (("another release", fx.sha("another release")), ("not a digest", "not-a-release"), ("empty", ""), ("null", None)):
            for table in MD_TABLES:
                with self.subTest(label=label, table=table):
                    try:
                        self.leased("EXECUTE_CREATE", ctx, owner_id, root_id)
                        self.assertEqual(len(self.call(self.executor, "md_release")), 1)                       # the control
                        with self.assertRaises(psycopg.errors.RaiseException) as caught:
                            self.executor.execute(f"SELECT * FROM {self.s}.{FUNCTIONS[table]}(%s)", (other,))
                        self.assertEqual((caught.exception.diag.message_primary, (caught.exception.diag.message_detail or "").strip()), (CODE, "RELEASE"))
                    finally:
                        rollback(self.executor)

    def test_an_unreferenced_candidate_release_is_not_readable_even_though_it_is_stored(self):
        """E11 crafted probe, not product evidence. A release the loader wrote that no published snapshot names: the lease's context names another release, so it is refused."""
        from marketdata.manifest import MarketDataRelease
        loader = self.conn("loader")
        loader.execute(f'SET search_path TO "{self.s}", pg_temp')
        release, manifests, contents, calendars = rich_release(x.identity())
        candidate = MarketDataRelease(name="rich-candidate", files=release.files, source_precedence=release.source_precedence, created_for="test")
        self.assertNotEqual(candidate.release_id, release.release_id)
        mds.write_release(loader, candidate, manifests, contents, calendars, count_rows=False)
        self.assertEqual(self.count("md_release", "release_id=%s", (candidate.release_id,)), 1)       # stored, and named by no snapshot
        ctx, _valid, owner_id, root_id = self.context()
        try:
            self.leased("EXECUTE_CREATE", ctx, owner_id, root_id)
            self.assertEqual(len(self.call(self.executor, "md_release")), 1)                          # the control: the snapshot's release reads
            for table in MD_TABLES:
                self.refused(self.executor, table, "RELEASE", release=candidate.release_id)
        finally:
            rollback(self.executor)


class TempShadowTests(MdCase):
    def test_a_temporary_table_named_like_an_md_table_changes_nothing_a_function_returns(self):
        """E11 crafted (the administrative role of the disposable database grants the executor TEMPORARY on the database for this test and revokes
        it in `finally`; a product executor has none): the executor creates `pg_temp.md_quote` and `pg_temp.md_release` with forged rows and puts
        pg_temp first on its search path. The control is that the shadow is real in the executor's own session. The functions still return the
        stored rows (their search_path is pinned with pg_temp last)."""
        ctx, _valid, owner_id, root_id = self.context()
        role = self.inst.roles["executor"]
        database = self.admin.execute("SELECT current_database()").fetchone()[0]
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.executor.execute("CREATE TEMP TABLE md_quote (release_id text, price numeric)")                    # a product executor cannot
        self.admin.execute(f'GRANT TEMPORARY ON DATABASE "{database}" TO "{role}"')
        try:
            shadow = self.conn("executor")
            shadow.execute("CREATE TEMP TABLE md_quote (release_id text)")
            shadow.execute("INSERT INTO md_quote VALUES (%s), (%s), (%s)", (self.rid, self.rid, self.rid))
            shadow.execute(f'SET search_path TO pg_temp, "{self.s}"')
            self.assertEqual(shadow.execute("SELECT count(*) FROM md_quote").fetchone()[0], 3)              # the shadow is in effect for an unqualified reader
            begin(shadow)
            try:
                self.admit(shadow, ctx, 1, "EXECUTE_CREATE", owner_id, root_id)
                self.assertEqual(len(self.call(shadow, "md_quote")), RICH_ROWS["md_quote"])                   # ... and not for the function
                self.assertEqual(self.counts(shadow), RICH_ROWS)
            finally:
                rollback(shadow)
        finally:
            self.admin.execute(f'REVOKE TEMPORARY ON DATABASE "{database}" FROM "{role}"')


class DeadlineCase(MdCase):
    INSTALL = "mdreaddl"
    W = 3

    def stalled(self):
        return self.conn("executor", options=self.stall_options())


class DeadlineTests(DeadlineCase):
    ORDERS = (("W decides", 120.0), ("the cap decides", 2.0))

    def test_every_function_is_refused_at_or_after_complete_by_in_both_orders_of_least(self):
        """E11 crafted probe, not product evidence (the executor session) with every session timeout at 0 (so no timeout is the bound). Before complete_by the call
        reads the release (the control); at the first instant of complete_by it is refused, for each of the thirteen functions."""
        for label, valid_in in self.ORDERS:
            with self.subTest(label):
                ctx, valid, owner_id, root_id = self.context(valid_in=valid_in)
                stalled = self.stalled()
                try:
                    lease = self.leased("EXECUTE_CREATE", ctx, owner_id, root_id, conn=stalled)
                    self.assertEqual(lease.complete_by < valid, valid_in > self.inst.w_seconds)
                    self.assertEqual(self.counts(stalled), RICH_ROWS)
                    self.wait_for_db_time(lease.complete_by)
                    self.refused_everywhere(stalled, "DEADLINE")
                finally:
                    rollback(stalled)

    def test_a_read_lease_is_bounded_the_same_way(self):
        """E11 crafted probe, not product evidence. An EXECUTE_REPRODUCE lease (a read-phase purpose) is refused at its complete_by exactly like a create lease."""
        ctx, _valid, owner_id, root_id = self.context(valid_in=120.0)
        stalled = self.stalled()
        try:
            lease = self.leased("EXECUTE_REPRODUCE", ctx, owner_id, root_id, conn=stalled)
            self.assertEqual(self.counts(stalled), RICH_ROWS)
            self.wait_for_db_time(lease.complete_by)
            self.refused_everywhere(stalled, "DEADLINE")
        finally:
            rollback(stalled)

    def test_after_a_lapse_there_is_no_lease_to_call_from_and_a_lease_just_before_it_ends_at_valid_until(self):
        """E11 crafted probe, not product evidence. A new admission at or after valid_until is refused (so a call from that connection has no lease: NO_LEASE); a lease admitted just
        before valid_until has complete_by = valid_until and is refused at it."""
        ctx, valid, owner_id, root_id = self.context(valid_in=2.0)
        stalled = self.stalled()
        lease = self.leased("EXECUTE_CREATE", ctx, owner_id, root_id, conn=stalled)
        try:
            self.assertEqual(lease.complete_by, valid)                       # the cap decides: W is 3 s, 2 s are left
            self.assertEqual(len(self.call(stalled, "md_release")), 1)
            self.wait_for_db_time(valid)
            self.refused(stalled, "md_release", "DEADLINE")
        finally:
            rollback(stalled)
        late = self.stalled()
        begin(late)
        try:
            self.assertRefused("RW_LAPSED", lambda: self.admit(late, ctx, 1, "EXECUTE_CREATE", owner_id, root_id))
        finally:
            rollback(late)
        self.refused_everywhere(late, "NO_LEASE")

    def test_a_pending_drain_mark_refuses_a_new_admission_but_a_lease_admitted_before_it_reads_until_its_own_complete_by(self):
        """E11 crafted probe, not product evidence. 3.1 'withdrawal does not cancel admitted work', and the owner's PD-0069 'all rights off': the mark commits (the publisher function,
        called directly, so nothing waits), a new admission is refused with the pending code and a connection that never admitted is refused by
        the function; the lease admitted before the mark still reads, and is refused after its own complete_by."""
        ctx, _valid, owner_id, root_id = self.context(valid_in=120.0)
        holder = self.stalled()
        lease = self.leased("EXECUTE_CREATE", ctx, owner_id, root_id, conn=holder)
        try:
            marked = self.conn("publisher").execute(f"SELECT * FROM {self.s}.rw_withdraw_mark(%s,1,%s,'PD-9002',%s,%s)", (ctx, fx.ACTOR, "c" * 40, "d" * 64)).fetchall()
            self.assertEqual(len(marked), 1)
            late = self.stalled()
            begin(late)
            try:
                self.assertRefused("RW_WITHDRAWAL_PENDING", lambda: self.admit(late, ctx, 1, "EXECUTE_CREATE", owner_id, root_id))
            finally:
                rollback(late)
            self.refused_everywhere(late, "NO_LEASE")
            self.assertEqual(self.counts(holder), RICH_ROWS)                  # the earlier lease still reads
            self.wait_for_db_time(lease.complete_by)
            self.refused(holder, "md_quote", "DEADLINE")                      # ... until its own complete_by
        finally:
            rollback(holder)

    def test_after_a_completed_withdrawal_there_is_no_read_and_a_renewal_restores_it_for_a_new_lease(self):
        ctx, valid, owner_id, root_id = self.context(valid_in=120.0)
        result = self.tool().withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual((result.status, result.outcome), (0, "WITHDRAWN"), result.text)
        executor = self.conn("executor")
        begin(executor)
        try:
            self.assertRefused("RW_WITHDRAWN", lambda: self.admit(executor, ctx, 2, "EXECUTE_CREATE", owner_id, root_id))
        finally:
            rollback(executor)
        self.refused_everywhere(executor, "NO_LEASE")
        renewed = self.renew(ctx, 2, valid_until=valid)
        self.assertEqual(renewed.status, 0, renewed.text)
        begin(executor)
        try:
            self.admit(executor, ctx, 3, "EXECUTE_CREATE", owner_id, root_id)
            self.assertEqual(self.counts(executor), RICH_ROWS)                # the restored right reads again
        finally:
            rollback(executor)


if __name__ == "__main__":
    import unittest
    unittest.main()
