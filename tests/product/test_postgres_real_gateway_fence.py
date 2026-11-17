"""F1 R3, PostgreSQL: the WRITE FENCE, the ROW POLICY and the JOURNAL of design 2.6 (the whole database is the namespace), the read bound of the
rooted tables, and the T03 all-writer matrix on the executor role's own connection.

Design 2.6 item 5 lists the tests; this module is that list. Where a test needs a database state no product path can reach, it says so in its
docstring: the owner role of the DISPOSABLE database writes a root or disables a barrier (E11 crafted). Those are not product evidence. The
product evidence is the executor's own refusals: a session that holds exactly the executor's grants and does what the writers of the matrix do.
Each barrier is shown ALONE (the owner disables the other two), so that none is claimed to work only because another does.
"""
from __future__ import annotations

import contextlib
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402

import real_gateway_fixtures as fx  # noqa: E402
from real_gateway_kit import GatewayCase, begin, commit, rollback, setUpModule, tearDownModule  # noqa: E402,F401

FENCED = ("portfolio", "account", "ledger_event", "benchmark_selection", "rw_root", "rw_revision")
BODY = {"mode": "LOCAL_SYNTHETIC_ACCOUNT", "name": "Saved fictional holdings", "reporting_currency": "USD",
        "positions": [{"symbol": "SYN-A", "quantity": "10"}, {"symbol": "SYN-B", "quantity": "10"}], "cash": "500", "synthetic_acknowledged": True}


class World:
    """A crafted root (E11): app_user, portfolio, account, and optionally a root-link row and the S2 root row."""

    def __init__(self, owner_id, root_id, account_id, ctx):
        self.owner_id, self.root_id, self.account_id, self.ctx = owner_id, root_id, account_id, ctx


class FenceCase(GatewayCase):
    INSTALL = "fence"
    W = 30

    def setUp(self):
        super().setUp()
        self.executor = self.conn("executor")
        self.executor.execute(f'SET search_path TO "{self.s}", pg_temp')       # the benchmark trigger pins the search path to its schema
        self.snap, self.valid, _ = self.publish(valid_in=300.0)
        self.ctx = self.snap.context_id

    # ---- crafted worlds (E11) ---------------------------------------------------------------------------------------------------
    def world(self, *, registered, ctx=None, with_root_row=False, with_event=False):
        owner_id, root_id, account_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        ctx = ctx or self.ctx
        # The fixture switches off only the fence and the journal of the tables it writes, by name, so that the migrations' own triggers
        # (which fill ledger_event's append columns, for one) still run.
        triggers = [(t, n) for t in ("portfolio", "account", "rw_root", "ledger_event") for n in ("zz_rw_write", "zz_rw_journal")]
        with self.owner.transaction():
            for table, trigger in triggers:
                self.owner.execute(f"ALTER TABLE {self.s}.{table} DISABLE TRIGGER {trigger}")
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
            self.owner.execute(f"INSERT INTO {self.s}.portfolio(portfolio_id,user_id,reporting_currency) VALUES(%s,%s,'USD')", (root_id, owner_id))
            self.owner.execute(f"INSERT INTO {self.s}.account(account_id,portfolio_id,name) VALUES(%s,%s,'crafted')", (account_id, root_id))
            if with_event:
                self.owner.execute(f"INSERT INTO {self.s}.ledger_event(event_id,account_id,event_type,event_date,currency,amount) "
                                   "VALUES(%s,%s,'OPENING_CASH',DATE '2001-01-02','USD',7)", (uuid.uuid4(), account_id))
            if registered:
                self.owner.execute(f"INSERT INTO {self.s}.rw_root_link(root_id,owner_id,context_id) VALUES(%s,%s,%s)", (root_id, owner_id, ctx))
                if with_root_row:
                    self.owner.execute(self.root_sql(), self.root_params(root_id, ctx))
            self.owner.execute("SET CONSTRAINTS ALL IMMEDIATE")        # no event may be pending when the triggers are switched on again
            for table, trigger in triggers:
                self.owner.execute(f"ALTER TABLE {self.s}.{table} ENABLE TRIGGER {trigger}")
        return World(owner_id, root_id, account_id, ctx)

    def root_sql(self):
        return (f"INSERT INTO {self.s}.rw_root(portfolio_id,context_id,market_origin,ledger_origin,personal_holdings,synthetic,name,account_label,"
                "opening_label,request_json,snapshot_json,snapshot_sha256,ledger_version,created_at) "
                "VALUES(%s,%s,'SYNTHETIC_TEST','INVENTED_TEST_LEDGER',false,true,'n','a','o','{}','{}',%s,1,now())")

    def root_params(self, root_id, ctx):
        return (root_id, ctx, fx.sha("{}"))

    def attempt(self, table, world):
        """(sql, params) of one INSERT into `table` for the root of `world`, valid in every other respect."""
        if table == "portfolio":
            return (f"INSERT INTO {self.s}.portfolio(portfolio_id,user_id,reporting_currency) VALUES(%s,%s,'USD')", (uuid.uuid4(), world.owner_id))
        if table == "account":
            return (f"INSERT INTO {self.s}.account(account_id,portfolio_id,name) VALUES(%s,%s,'attempt')", (uuid.uuid4(), world.root_id))
        if table == "ledger_event":
            return (f"INSERT INTO {self.s}.ledger_event(event_id,account_id,event_type,event_date,currency,amount) "
                    "VALUES(%s,%s,'OPENING_CASH',DATE '2001-01-02','USD',1)", (uuid.uuid4(), world.account_id))
        if table == "benchmark_selection":
            return (f"INSERT INTO {self.s}.benchmark_selection(selection_id,portfolio_id,record_type,benchmark_id,origin,selected_on) "
                    "VALUES(%s,%s,'SELECT','SPY','USER_CHOSEN',DATE '2001-01-02')", (uuid.uuid4(), world.root_id))
        if table == "rw_root":
            return (self.root_sql(), self.root_params(world.root_id, world.ctx))
        if table == "rw_revision":
            revision = uuid.uuid4()
            return (f"INSERT INTO {self.s}.rw_revision(revision_id,portfolio_id,parent_revision_id,operation_id,operation,command_sha256,as_of,"
                    "ledger_version,selection_version,policies_json,policies_state,snapshot_json,snapshot_sha256,created_at) "
                    "VALUES(%s,%s,%s,%s,'CREATE',%s,DATE '2001-01-02',1,0,'{}','NOT_STATED','{}',%s,now())",
                    (revision, world.root_id, revision, uuid.uuid4(), "1" * 64, fx.sha("{}")))
        raise AssertionError(table)

    def counts(self):
        return {t: self.count(t) for t in FENCED}

    @contextlib.contextmanager
    def barriers(self, table, active):
        """E11 CRAFTED (never product evidence): the owner role of the disposable database leaves ONLY the barriers named in `active`
        ('fence', 'policy', 'journal') switched on for `table`, and switches all three on again afterwards, whatever happens.
        The ledger table's own insert trigger (a migration trigger that is not SECURITY DEFINER) reads the `account` row of the event with the
        executor's privileges, so the row policy of `account` would hide it (the trigger would then leave `portfolio_id` NULL and the table's
        CHECK would refuse the row first). While a barrier of another table is under test, `account`'s row policy is therefore off too."""
        def apply(on, also):
            with self.owner.transaction():
                self.owner.execute(f"ALTER TABLE {self.s}.{table} {'ENABLE' if 'fence' in on else 'DISABLE'} TRIGGER zz_rw_write")
                self.owner.execute(f"ALTER TABLE {self.s}.{table} {'ENABLE' if 'journal' in on else 'DISABLE'} TRIGGER zz_rw_journal")
                self.owner.execute(f"ALTER TABLE {self.s}.{table} {'ENABLE' if 'policy' in on else 'DISABLE'} ROW LEVEL SECURITY")
                if table == "ledger_event":
                    self.owner.execute(f"ALTER TABLE {self.s}.account {'ENABLE' if also else 'DISABLE'} ROW LEVEL SECURITY")
        apply(set(active), True)
        if table == "ledger_event":
            apply(set(active), False)
        try:
            yield
        finally:
            apply({"fence", "policy", "journal"}, True)

    def refused(self, sql, params, *codes, conn=None):
        """Run one statement on the executor connection; it must raise one of `codes`: a gateway code, 'RLS' (the row policy's 42501), 'PRIVILEGE'
        (any other 42501) or 'FK'. Returns the code seen."""
        conn = conn or self.executor
        try:
            conn.execute(sql, params)
        except psycopg.errors.RaiseException as error:
            code = (error.diag.message_primary or str(error)).splitlines()[0]
        except psycopg.errors.InsufficientPrivilege as error:
            code = "RLS" if "row-level security" in str(error) else "PRIVILEGE"
        except psycopg.errors.ForeignKeyViolation:
            code = "FK"
        else:
            self.fail("the statement was not refused: " + sql[:70])
        self.assertIn(code, codes, sql[:80])
        return code

    def lease_for(self, purpose, world, *, op=None, new_root=False):
        begin(self.executor)
        return self.admit(self.executor, world.ctx, 1, purpose, world.owner_id, world.root_id, op=op, new_root=new_root)


class AllWriterMatrixTests(FenceCase):
    def test_a_lease_less_insert_into_a_registered_nowhere_root_is_refused_on_every_fenced_table(self):
        """The executor's own session (product path) against CRAFTED rows the owner wrote to have something to point at (E11): no admit, no
        lease, a root registered nowhere. Every fenced table refuses with the fence's code and writes nothing."""
        world = self.world(registered=False)
        other = self.world(registered=False)
        before = self.counts()
        for table in FENCED:
            with self.subTest(table):
                self.refused(*self.attempt(table, world), "RW_WRITE_REFUSED")
        # a ledger event on an account of ANOTHER root, and one on an account that does not exist, are refused too
        self.refused(*self.attempt("ledger_event", other), "RW_WRITE_REFUSED")
        sql, _params = self.attempt("ledger_event", other)
        self.refused(sql, (uuid.uuid4(), uuid.uuid4()), "RW_ROOT_UNKNOWN", "RW_WRITE_REFUSED")
        self.assertEqual(self.counts(), before)

    def test_each_barrier_alone_refuses_the_lease_less_insert(self):
        """E11 crafted (the owner switches two of the three barriers off on the table under test and all three on again): the fence alone, the row
        policy alone and the journal alone each refuse the executor's lease-less insert. Fence and journal raise the gateway's code; the policy
        raises PostgreSQL's row-level-security error. The journal runs AFTER the table's constraints, so its probe uses a REGISTERED root (the
        foreign keys of `rw_root` need one); the other two use a root registered nowhere."""
        unregistered = self.world(registered=False)
        registered = self.world(registered=True)                                  # a root link and a portfolio, no S2 root row yet
        registered_with_root = self.world(registered=True, with_root_row=True)    # for rw_revision, whose foreign key needs the S2 root row
        before = self.counts()
        for table in FENCED:
            journal_world = registered_with_root if table == "rw_revision" else registered
            for barrier, world, code in (("fence", unregistered, "RW_WRITE_REFUSED"), ("policy", unregistered, "RLS"),
                                         ("journal", journal_world, "RW_WRITE_REFUSED")):
                with self.subTest(table=table, barrier=barrier), self.barriers(table, {barrier}):
                    self.refused(*self.attempt(table, world), code)
        self.assertEqual(self.counts(), before)

    def test_each_barrier_alone_refuses_a_write_under_the_wrong_lease(self):
        """Mutation M4 of R3's own run (the journal without its root, purpose, phase and deadline tests) was caught by one test only. E11 crafted
        (the owner switches two of the three barriers off on `account`): under a read-only lease on the root, and under the open create lease of
        ANOTHER root, the fence alone, the policy alone and the journal alone each refuse an `account` insert for a registered root."""
        registered = self.world(registered=True, with_root_row=True)
        owner_id, root_a = uuid.uuid4(), uuid.uuid4()
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
        mine = World(owner_id, root_a, uuid.uuid4(), self.ctx)
        before = self.counts()
        scenarios = (("read-only lease on the root", "ARCHIVE_READ", registered, False, {"fence": "RW_WRITE_REFUSED", "journal": "RW_WRITE_REFUSED", "policy": "RLS"}),
                     ("create lease of another root", "EXECUTE_CREATE", mine, True, {"fence": "RW_ROOT_DIFFERS", "journal": "RW_WRITE_REFUSED", "policy": "RLS"}))
        for label, purpose, leased, new_root, codes in scenarios:
            for barrier, code in codes.items():
                with self.subTest(scenario=label, barrier=barrier), self.barriers("account", {barrier}):
                    try:
                        self.lease_for(purpose, leased, new_root=new_root)
                        self.refused(*self.attempt("account", registered), code)
                    finally:
                        rollback(self.executor)
        self.assertEqual(self.counts(), before)

    def test_the_control_with_all_three_barriers_off_the_same_insert_goes_through(self):
        """E11 crafted control: the owner switches ALL THREE barriers off on the table and the same executor insert succeeds. Without this a refusal
        above could be a malformed row. The rows stay in the disposable database, which is dropped at the end of the run."""
        for table in FENCED:
            world = self.world(registered=table in ("rw_root", "rw_revision"), with_root_row=table == "rw_revision")
            with self.subTest(table), self.barriers(table, set()):
                before = self.count(table)
                self.executor.execute(*self.attempt(table, world))
                self.assertEqual(self.count(table), before + 1)

    def test_a_read_only_lease_does_not_allow_an_economic_write(self):
        """Product path on a crafted root (E11 root): with a lease of any read-phase purpose for the root, every fenced insert for that root is
        refused. This is the PD-0060 pattern: ledger and CSV writes under a legitimate read-only lease are actually refused."""
        world = self.world(registered=True, with_root_row=True)
        before = self.counts()
        for purpose in ("ARCHIVE_READ", "ARCHIVE_EXPORT", "EXECUTE_REPRODUCE"):
            for table in FENCED:
                with self.subTest(purpose=purpose, table=table):
                    try:
                        self.lease_for(purpose, world)
                        self.refused(*self.attempt(table, world), "RW_WRITE_REFUSED")
                    finally:
                        rollback(self.executor)
        self.assertEqual(self.counts(), before)

    def test_a_lease_less_executor_write_to_the_identity_tables_is_refused_and_so_is_every_read(self):
        """Technical review M-1 and L-6 (R3 fix round). `issuer`, `instrument` and `listing` carry no root, so no fence or journal could cover a write
        to them: the executor holds no privilege on them (or on `app_user`), with or without a lease, and a write is refused by privilege BEFORE any
        constraint. The probe the reviewer ran (an insert after a completed withdrawal) is the lease-less case. Product path: the executor's own
        session; no crafted row is needed because the statement is refused before it reads one."""
        owner_id = uuid.uuid4()
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
        mine = World(owner_id, uuid.uuid4(), uuid.uuid4(), self.ctx)
        before = {t: self.count(t) for t in ("issuer", "instrument", "listing")}
        statements = [f"INSERT INTO {self.s}.{t} DEFAULT VALUES" for t in ("issuer", "instrument", "listing")] + \
                     [f"SELECT 1 FROM {self.s}.{t} LIMIT 1" for t in ("issuer", "instrument", "listing", "app_user")] + \
                     [f"INSERT INTO {self.s}.app_user DEFAULT VALUES", f"UPDATE {self.s}.listing SET listing_id=listing_id"]
        for label, open_lease in (("no lease", False), ("an open create lease", True)):
            for statement in statements:
                with self.subTest(lease=label, statement=statement[:48]):
                    try:
                        if open_lease:
                            self.lease_for("EXECUTE_CREATE", mine, new_root=True)
                        self.refused(statement, (), "PRIVILEGE")
                    finally:
                        rollback(self.executor)
        self.assertEqual({t: self.count(t) for t in before}, before)
        for table in ("issuer", "instrument", "listing", "app_user"):                  # and the catalog agrees, whatever the statements did
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                self.assertFalse(self.owner.execute("SELECT has_table_privilege(%s::name,%s::regclass,%s)",
                                                    (self.inst.roles["executor"], f'"{self.s}"."{table}"', privilege)).fetchone()[0], (table, privilege))

    def test_the_csv_and_sandbox_tables_are_out_of_reach_even_under_a_valid_lease(self):
        """PD-0060 pattern, CSV half. Product path: the executor holds no privilege on the legacy web tables, so under a legitimate read lease
        and under an open create lease alike the write is a privilege refusal, before any trigger."""
        world = self.world(registered=True, with_root_row=True)
        owner_id = uuid.uuid4()
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
        fresh = World(owner_id, uuid.uuid4(), None, self.ctx)
        statements = (f"INSERT INTO {self.s}.web_csv_report SELECT * FROM {self.s}.web_csv_report LIMIT 0",
                      f"INSERT INTO {self.s}.web_csv_source_key SELECT * FROM {self.s}.web_csv_source_key LIMIT 0",
                      f"INSERT INTO {self.s}.web_saved_sandbox SELECT * FROM {self.s}.web_saved_sandbox LIMIT 0",
                      f"INSERT INTO {self.s}.web_portfolio_revision SELECT * FROM {self.s}.web_portfolio_revision LIMIT 0",
                      f"SELECT * FROM {self.s}.web_csv_report", f"SELECT * FROM {self.s}.web_saved_sandbox")
        for purpose, target, new_root in (("ARCHIVE_READ", world, False), ("EXECUTE_CREATE", fresh, True)):
            for statement in statements:
                with self.subTest(purpose=purpose, statement=statement[:60]):
                    try:
                        self.lease_for(purpose, target, new_root=new_root)
                        self.refused(statement, (), "PRIVILEGE")
                    finally:
                        rollback(self.executor)

    def test_an_open_create_lease_for_one_root_refuses_the_inserts_of_every_other_root(self):
        """Product path on crafted rows: with the open create lease of root A, an insert for an unregistered root B and one for a registered root
        C are refused with RW_ROOT_DIFFERS. The control is the insert for A itself, which the lease allows."""
        owner_id, root_a = uuid.uuid4(), uuid.uuid4()
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
        unregistered_b = self.world(registered=False)
        registered_c = self.world(registered=True, with_root_row=True)
        mine = World(owner_id, root_a, uuid.uuid4(), self.ctx)
        for table in ("portfolio", "account", "ledger_event", "benchmark_selection"):
            with self.subTest(table=table, root="A (control)"):
                try:
                    self.lease_for("EXECUTE_CREATE", mine, new_root=True)
                    self.executor.execute(f"INSERT INTO {self.s}.portfolio(portfolio_id,user_id,reporting_currency) VALUES(%s,%s,'USD')", (root_a, owner_id))
                    self.executor.execute(f"INSERT INTO {self.s}.account(account_id,portfolio_id,name) VALUES(%s,%s,'a')", (mine.account_id, root_a))
                    if table in ("ledger_event", "benchmark_selection"):
                        self.executor.execute(*self.attempt(table, mine))
                finally:
                    rollback(self.executor)
        for label, world in (("B unregistered", unregistered_b), ("C registered", registered_c)):
            for table in FENCED:
                with self.subTest(table=table, root=label):
                    try:
                        self.lease_for("EXECUTE_CREATE", mine, new_root=True)
                        sql, params = self.attempt(table, world)
                        self.refused(sql, params, "RW_ROOT_DIFFERS")
                    finally:
                        rollback(self.executor)

    def test_insert_first_register_later_is_refused_at_both_ends(self):
        """The executor's insert for an unregistered root is refused (above); with the portfolio row written by the owner of the disposable
        database (E11), `rw_admit(new_root = true)` for that root is refused because the root exists."""
        world = self.world(registered=False)
        owner_id = world.owner_id
        try:
            begin(self.executor)
            self.assertRefused("RW_NOT_FOUND", lambda: self.admit(self.executor, self.ctx, 1, "EXECUTE_CREATE", owner_id, world.root_id, new_root=True))
        finally:
            rollback(self.executor)
        self.assertEqual(self.count("rw_root_link", "root_id=%s", (world.root_id,)), 0)

    def test_the_executor_cannot_write_the_registry_the_lease_or_the_bundle_tables(self):
        """Product path: no INSERT, UPDATE, DELETE or TRUNCATE on the root-link, lease, journal, artifact, operation, snapshot, head, history
        and mode tables (the privilege check comes first)."""
        column = {"rw_mode": "singleton", "rw_journal": "table_name"}
        for table in ("rw_root_link", "rw_lease", "rw_journal", "rw_artifact", "rw_operation", "rw_snapshot", "rw_head", "rw_history", "rw_mode"):
            set_column = column.get(table, "context_id")
            # DEFAULT VALUES, not INSERT ... SELECT *: a GENERATED ALWAYS column makes PostgreSQL refuse the rewrite before the privilege check
            for statement in (f"INSERT INTO {self.s}.{table} DEFAULT VALUES", f"DELETE FROM {self.s}.{table}",
                              f"UPDATE {self.s}.{table} SET {set_column}={set_column}", f"TRUNCATE {self.s}.{table}"):
                with self.subTest(statement=statement[:70]):
                    self.refused(statement, (), "PRIVILEGE")

    def test_the_executor_cannot_disable_a_barrier(self):
        """Product path: DISABLE TRIGGER, DISABLE ROW LEVEL SECURITY, DROP POLICY, session_replication_role and SET ROLE all fail for the
        executor, and afterwards every barrier is still on."""
        owner_role = self.inst.roles["owner"]
        for table in FENCED:
            for statement in (f"ALTER TABLE {self.s}.{table} DISABLE TRIGGER zz_rw_write", f"ALTER TABLE {self.s}.{table} DISABLE TRIGGER zz_rw_journal",
                              f"ALTER TABLE {self.s}.{table} DISABLE TRIGGER ALL", f"ALTER TABLE {self.s}.{table} DISABLE ROW LEVEL SECURITY",
                              f"DROP POLICY rw_row_guard ON {self.s}.{table}", f"DROP TRIGGER zz_rw_write ON {self.s}.{table}",
                              f"ALTER TABLE {self.s}.{table} OWNER TO CURRENT_USER"):
                with self.subTest(statement=statement[:80]):
                    self.refused(statement, (), "PRIVILEGE")
        self.refused("SET session_replication_role = replica", (), "PRIVILEGE")
        self.refused(f'SET ROLE "{owner_role}"', (), "PRIVILEGE")
        self.refused(f'SET SESSION AUTHORIZATION "{owner_role}"', (), "PRIVILEGE")
        for table in FENCED:
            enabled = {r[0]: r[1] for r in self.admin.execute(
                "SELECT t.tgname,t.tgenabled FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname=%s AND c.relname=%s AND t.tgname LIKE 'zz\\_rw\\_%%'", (self.s, table)).fetchall()}
            self.assertEqual(enabled, {"zz_rw_write": "O", "zz_rw_journal": "O", "zz_rw_truncate": "O"}, table)
            self.assertTrue(self.admin.execute("SELECT relrowsecurity FROM pg_class WHERE oid=%s::regclass", (f"{self.s}.{table}",)).fetchone()[0], table)

    def test_a_registered_root_without_a_portfolio_row_fails_at_commit(self):
        """Product path on the registry: `rw_admit(new_root=true)` registers the root before the portfolio row exists; COMMIT without the row
        fails on the deferred foreign key and nothing is left (the fuller create is in test_postgres_real_gateway_seal)."""
        owner_id, root_id = uuid.uuid4(), uuid.uuid4()
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
        try:
            begin(self.executor)
            self.admit(self.executor, self.ctx, 1, "EXECUTE_CREATE", owner_id, root_id, new_root=True)
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                commit(self.executor)
        finally:
            rollback(self.executor)
        self.assertEqual(self.count("rw_root_link", "root_id=%s", (root_id,)), 0)

    def test_truncate_is_refused_for_the_executor_and_for_the_owner(self):
        """The executor holds no TRUNCATE privilege; the owner's TRUNCATE is refused by the fence's statement trigger or, where another table
        references the table, by PostgreSQL's own foreign-key rule first. Either way the rows stay."""
        world = self.world(registered=True, with_root_row=True)
        before = self.counts()
        for table in FENCED:
            self.refused(f"TRUNCATE {self.s}.{table}", (), "PRIVILEGE")
            try:
                self.owner.execute(f"TRUNCATE {self.s}.{table}")
            except (psycopg.errors.RaiseException, psycopg.errors.FeatureNotSupported, psycopg.errors.RestrictViolation):
                pass                      # the fence's statement trigger, PostgreSQL's foreign-key rule, or the migration's own append-only trigger
            else:
                self.fail("TRUNCATE succeeded on " + table)
        self.assertEqual(self.counts(), before)
        self.assertIsNotNone(world)

    def test_web_account_store_create_portfolio_on_the_executor_connection_is_refused_by_each_barrier_on_its_own(self):
        """W07 / FF1-C02, T03: the legacy create route called on the executor's connection. Barrier 1: the executor has no privilege on
        `web_saved_sandbox`, which the route reads first. Barrier 2 (E11 crafted: the owner of the disposable database grants the executor SELECT
        and INSERT on that one table, and revokes them in `finally`): the route goes on to insert the portfolio, and the write fence refuses it.
        No portfolio, account, ledger row or saved sandbox row remains."""
        from persistence.web_account_store import WebAccountStore
        from web_api.synthetic import SyntheticWorld
        store = WebAccountStore("unused-conninfo", self.s)
        owner_id = uuid.uuid4()
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
        before = (self.counts(), self.count("web_saved_sandbox"), self.count("issuer"))
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            store.create_portfolio(str(owner_id), BODY, SyntheticWorld(), connection=self.executor)
        role = self.inst.roles["executor"]
        # barrier 1b (the R3 fix round, M-1): the route books issuer, instrument and listing rows first, and the executor holds nothing on them
        self.owner.execute(f'GRANT SELECT, INSERT ON {self.s}.web_saved_sandbox TO "{role}"')
        try:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                store.create_portfolio(str(owner_id), BODY, SyntheticWorld(), connection=self.executor)
        finally:
            self.owner.execute(f'REVOKE SELECT, INSERT ON {self.s}.web_saved_sandbox FROM "{role}"')
        # barrier 2 (E11 crafted): the identity tables are granted as well, so only the fence is left between the route and the portfolio row
        identity = ("web_saved_sandbox", "issuer", "instrument", "listing", "app_user")
        for table in identity:
            self.owner.execute(f'GRANT SELECT, INSERT ON {self.s}.{table} TO "{role}"')
        try:
            with self.assertRaises(psycopg.errors.RaiseException) as caught:
                store.create_portfolio(str(owner_id), BODY, SyntheticWorld(), connection=self.executor)
            self.assertEqual(caught.exception.diag.message_primary, "RW_WRITE_REFUSED")
        finally:
            for table in identity:
                self.owner.execute(f'REVOKE SELECT, INSERT ON {self.s}.{table} FROM "{role}"')
        self.assertEqual((self.counts(), self.count("web_saved_sandbox"), self.count("issuer")), before)


class RowPolicyReadTests(FenceCase):
    def test_a_read_without_a_lease_returns_no_row_and_a_lease_on_another_root_returns_none_of_this_root(self):
        """Product path on crafted rows (E11 rows): a restrictive policy filters silently. No lease: no row of any fenced table. A lease on root
        B: none of root A's rows. A lease on root A: its rows (the control)."""
        a = self.world(registered=True, with_root_row=True, with_event=True)
        b = self.world(registered=True, with_root_row=True, with_event=True)
        queries = {"portfolio": ("portfolio_id", a.root_id), "account": ("portfolio_id", a.root_id), "rw_root": ("portfolio_id", a.root_id),
                   "ledger_event": ("account_id", a.account_id)}
        def rows(table):
            column, value = queries[table]
            return self.executor.execute(f"SELECT count(*) FROM {self.s}.{table} WHERE {column}=%s", (value,)).fetchone()[0]
        for table in queries:
            self.assertEqual(rows(table), 0, table)
        try:
            self.lease_for("ARCHIVE_READ", b)
            for table in queries:
                self.assertEqual(rows(table), 0, table)
        finally:
            rollback(self.executor)
        try:
            self.lease_for("ARCHIVE_READ", a)
            for table in queries:
                self.assertEqual(rows(table), 1, table)
        finally:
            rollback(self.executor)


class DeadlineFenceCase(FenceCase):
    INSTALL = "fencedl"
    W = 3


class ReadBoundTests(DeadlineFenceCase):
    """Design 3.2 R3 'the read bound' (E11 root, product-path session): a read lease whose transaction is kept open past complete_by (every session
    timeout 0) reads no row of a rooted table and the archive refuses. The same statements before complete_by return the rows (the control)."""

    ORDERS = (("W decides", 120.0), ("the cap decides", 2.0))

    def stalled_world(self, valid_in):
        snap, valid, _ = self.publish(valid_in=valid_in)
        world = self.world(registered=True, ctx=snap.context_id, with_root_row=True, with_event=True)
        stalled = self.conn("executor", options=self.stall_options())
        stalled.execute(f'SET search_path TO "{self.s}", pg_temp')
        return snap, valid, world, stalled

    def test_rooted_reads_stop_at_complete_by_in_both_orders_of_least(self):
        """A restrictive policy filters silently: the rows before complete_by (the control), no row and no error after."""
        for label, valid_in in self.ORDERS:
            with self.subTest(label):
                snap, valid, world, stalled = self.stalled_world(valid_in)

                def counts():
                    return [stalled.execute(f"SELECT count(*) FROM {self.s}.{t} WHERE {c}=%s", (v,)).fetchone()[0] for t, c, v in (
                        ("portfolio", "portfolio_id", world.root_id), ("account", "portfolio_id", world.root_id),
                        ("ledger_event", "account_id", world.account_id), ("rw_root", "portfolio_id", world.root_id))]
                begin(stalled)
                try:
                    lease = self.admit(stalled, snap.context_id, 1, "ARCHIVE_READ", world.owner_id, world.root_id)
                    self.assertEqual(lease.complete_by < valid, valid_in > self.inst.w_seconds)
                    self.assertEqual(counts(), [1, 1, 1, 1])
                    self.wait_for_db_time(lease.complete_by)
                    self.assertEqual(counts(), [0, 0, 0, 0])
                finally:
                    rollback(stalled)

    def test_the_archive_read_refuses_at_complete_by_in_both_orders_of_least(self):
        """The archive read answers its lookup before complete_by (an unknown operation is NOT_FOUND: the control) and refuses with the deadline
        code at or after it, before it looks anything up."""
        for label, valid_in in self.ORDERS:
            with self.subTest(label):
                snap, valid, world, stalled = self.stalled_world(valid_in)

                def archive():
                    return stalled.execute(f"SELECT * FROM {self.s}.rw_archive(%s,%s)", (world.owner_id, uuid.uuid4()))
                begin(stalled)
                try:
                    self.admit(stalled, snap.context_id, 1, "ARCHIVE_READ", world.owner_id, world.root_id)
                    self.assertRefused("RW_NOT_FOUND", archive)
                finally:
                    rollback(stalled)
                begin(stalled)
                try:
                    lease = self.admit(stalled, snap.context_id, 1, "ARCHIVE_READ", world.owner_id, world.root_id)
                    self.wait_for_db_time(lease.complete_by)
                    self.assertRefused("RW_DEADLINE", archive)
                finally:
                    rollback(stalled)


if __name__ == "__main__":
    import unittest
    unittest.main()
