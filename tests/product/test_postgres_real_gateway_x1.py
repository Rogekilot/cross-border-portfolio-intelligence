"""F1 R1, PostgreSQL: the X1 lease (design 3.1, 3.2): admission and lapse, the trusted clock, the capped deadline, renewal and date
correction, and the deadline guard (fact 17).

Covers T07 (the R1 items), FF1-C06 and the two fact-17 showings: the named SET CONSTRAINTS form on the root-link foreign key, and the
deadline guard's COMMIT-time refusal. R1's in-flight work is a READ-phase lease (no fence, seal or create exists yet), so the stall
is "after the last statement, before the COMMIT".

The tests use the real clock and a test install with W = 4 seconds; `valid_until` is a few seconds ahead where the test must cross it.
There is no clock hook. Roots are an E11 CRAFTED fixture (owner-role rows in a disposable database): never product evidence; the
admit, lease, guard and tool under test are the product's. Without a provisioning superuser the tests SKIP with the reason.
"""
from __future__ import annotations

import datetime as dt
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
from psycopg.pq import TransactionStatus  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

import real_gateway_fixtures as fx  # noqa: E402
from persistence import real_workspace_store as store  # noqa: E402
from real_gateway_kit import (PURPOSES, GatewayCase, Worker, begin, commit, rollback, setUpModule, tearDownModule)  # noqa: E402,F401


class X1Case(GatewayCase):
    INSTALL = "x1"
    SCOPE = "SYNTHETIC_TEST"          # the scope of the contexts this class publishes; the classes at the end of the module repeat the
                                      # admission, bound and lapse tests on a TEST_SWITCH context (technical review R1, M-4)

    def live(self, valid_in=120.0, **kw):
        """Publish through the product tool and register a crafted root. Returns (context, valid_until, owner id, root id)."""
        kw.setdefault("scope", self.SCOPE)
        snap, valid, _result = self.publish(valid_in=valid_in, **kw)
        stored = bytes(self.owner.execute(f"SELECT snapshot FROM {self.s}.rw_snapshot WHERE context_id=%s", (snap.context_id,)).fetchone()[0])
        document = json.loads(stored)
        self.assertEqual((document["scope"], document["origin"]["synthetic"], document["origin"]["market_origin"]),
                         (kw["scope"], True, "SYNTHETIC_TEST"))                 # the stored bytes are of the scope under test, invented and synthetic
        self.assertNotIn(b"REAL_SOURCE", stored)
        owner_id, root_id = self.craft_root(snap.context_id)
        return snap.context_id, valid, owner_id, root_id

    def refused_admission(self, code, ctx, generation, purpose, owner_id, root_id, conn=None, **kw):
        conn = conn or self.conn("executor")
        begin(conn)
        try:
            return self.assertRefused(code, lambda: self.admit(conn, ctx, generation, purpose, owner_id, root_id), **kw)
        finally:
            rollback(conn)


class AdmissionAndLapseTests(X1Case):
    def test_admit_before_valid_until_records_the_lease_for_each_purpose(self):
        """T07 R1: admission before valid_until succeeds for each of the four purposes, each its own admission, and the lease records
        the sampled instant, the valid_until used and complete_by = LEAST(admitted_at + W, valid_until)."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        executor = self.conn("executor")
        seen = []
        # E11 crafted for the EXECUTE_CREATE commit only: R3's bundle guard refuses to commit an unsealed create lease, so this R1 test,
        # which is about the recorded row, commits it with the guard off (the guard's own refusal is test_postgres_real_gateway_seal).
        with self.bundle_guard_off():
            for purpose in PURPOSES:
                before = self.db_now()
                begin(executor)
                try:
                    lease = self.admit(executor, ctx, 1, purpose, owner_id, root_id)
                    self.assertEqual((lease.snapshot, lease.context_id, lease.generation, lease.purpose, lease.owner_id, lease.root_id),
                                     (bytes(self.owner.execute(f"SELECT snapshot FROM {self.s}.rw_snapshot WHERE context_id=%s", (ctx,)).fetchone()[0]),
                                      ctx, 1, purpose, owner_id, root_id))
                    commit(executor)
                finally:
                    rollback(executor)
                seen.append((purpose, before, self.db_now(), lease))
        rows = self.leases(ctx)
        self.assertEqual([r["purpose"] for r in rows], list(PURPOSES))
        for (purpose, before, after, lease), row in zip(seen, rows):
            self.assertTrue(before <= row["admitted_at"] <= after, purpose)
            self.assertEqual(row["valid_until"], valid, purpose)
            self.assertEqual(row["complete_by"], min(row["admitted_at"] + fx.seconds(self.inst.w_seconds), valid), purpose)
            self.assertEqual(lease.complete_by, row["complete_by"], purpose)
            self.assertEqual(row["phase"], "OPEN" if purpose == "EXECUTE_CREATE" else "READONLY", purpose)

    def test_lapse_refuses_all_four_purposes_even_though_the_stored_rights_are_true(self):
        """T07 R1 / FF1-C06: at or after valid_until every purpose is refused with the lapse code; a forward jump of the clock has no hook,
        so this test (real time) is the policy's evidence that time passing fails closed."""
        ctx, valid, owner_id, root_id = self.live(2.0)
        executor = self.conn("executor")
        begin(executor)
        try:
            self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id)             # the positive control, before valid_until
        finally:
            rollback(executor)
        self.wait_for_db_time(valid)
        for purpose in PURPOSES:
            self.refused_admission("RW_LAPSED", ctx, 1, purpose, owner_id, root_id, conn=executor)
        self.assertEqual(self.head(ctx)[1], fx.ALL_RIGHTS)                            # stored rights untouched: lapse is computed, never written
        self.assertEqual(len(self.history(ctx)), 1)

    def test_each_purpose_has_its_own_right_and_archive_read_gates_all_of_them(self):
        """FF1-C06 'each purpose has its own terms and evaluation boundary'."""
        for off in ("EXECUTE_CREATE", "ARCHIVE_EXPORT", "EXECUTE_REPRODUCE"):
            ctx, valid, owner_id, root_id = self.live(120.0, rights={**fx.ALL_RIGHTS, off: False})
            for purpose in PURPOSES:
                if purpose == off:
                    self.refused_admission("RW_RIGHT_REFUSED", ctx, 1, purpose, owner_id, root_id)
                else:
                    with self.bundle_guard_off():          # E11 crafted: an unsealed create lease committed for its row only (see above)
                        self.admit_and_commit(self.conn("executor"), ctx, 1, purpose, owner_id, root_id)
        ctx, valid, owner_id, root_id = self.live(120.0, rights={**fx.ALL_RIGHTS, "ARCHIVE_READ": False})
        for purpose in PURPOSES:
            self.refused_admission("RW_RIGHT_REFUSED", ctx, 1, purpose, owner_id, root_id)

    def test_a_completed_withdrawal_has_a_code_of_its_own_distinct_from_a_right_never_granted(self):
        """L-5 (technical review R1; design 2.1, 2.4): after a withdrawal every purpose is refused with `RW_WITHDRAWN`; a right that was
        never granted, and all four rights turned off by a renewal that names no drain mark, are `RW_RIGHT_REFUSED`."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        result = self.tool().withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual((result.status, result.outcome), (0, "WITHDRAWN"), result.text)
        for purpose in PURPOSES:
            self.refused_admission("RW_WITHDRAWN", ctx, 2, purpose, owner_id, root_id)
        ctx, valid, owner_id, root_id = self.live(120.0, rights={**fx.ALL_RIGHTS, "ARCHIVE_EXPORT": False})
        self.refused_admission("RW_RIGHT_REFUSED", ctx, 1, "ARCHIVE_EXPORT", owner_id, root_id)               # never granted
        none = {key: False for key in fx.ALL_RIGHTS}
        ctx, valid, owner_id, root_id = self.live(120.0)
        renewed = self.renew(ctx, 1, valid_until=valid, rights=none)
        self.assertEqual((renewed.status, self.marks(ctx)), (0, []), renewed.text)
        for purpose in PURPOSES:
            self.refused_admission("RW_RIGHT_REFUSED", ctx, 2, purpose, owner_id, root_id)                    # all off, but no withdrawal

    def test_the_refusals_of_admission_by_shape_generation_and_root(self):
        ctx, valid, owner_id, root_id = self.live(120.0)
        self.refused_admission("RW_GENERATION_DIFFERS", ctx, 2, "ARCHIVE_READ", owner_id, root_id)
        self.refused_admission("RW_NOT_FOUND", "0" * 64, 1, "ARCHIVE_READ", owner_id, root_id)
        self.refused_admission("RW_NOT_FOUND", ctx, 1, "ARCHIVE_READ", uuid.uuid4(), root_id)          # another owner's root
        self.refused_admission("RW_NOT_FOUND", ctx, 1, "ARCHIVE_READ", owner_id, uuid.uuid4())         # an unregistered root
        executor = self.conn("executor")
        begin(executor)
        try:
            self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
            self.assertRefused("RW_SINGLE_SCOPE", lambda: self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id))
        finally:
            rollback(executor)
        executor.execute("BEGIN ISOLATION LEVEL REPEATABLE READ")
        try:
            self.assertRefused("RW_ISOLATION", lambda: self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id))
        finally:
            rollback(executor)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 0)

    def test_the_lease_exposes_its_own_scope_to_its_own_transaction_only(self):
        ctx, valid, owner_id, root_id = self.live(120.0)
        executor, other = self.conn("executor"), self.conn("executor")
        op = uuid.uuid4()
        begin(executor)
        try:
            lease = self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id, op=op)
            self.assertEqual((lease.operation_id, lease.owner_id, lease.root_id), (op, owner_id, root_id))
            begin(other)
            try:
                self.assertEqual(other.execute(f"SELECT * FROM {self.s}.rw_scope()").fetchall(), [])
            finally:
                rollback(other)
        finally:
            rollback(executor)
        self.assertEqual(self.count("rw_lease", "operation_id=%s", (op,)), 0)       # a rolled-back admission leaves no lease


class CappedDeadlineTests(X1Case):
    def test_the_deadline_is_the_lesser_of_w_and_valid_until_in_both_orders(self):
        """T07 R1: complete_by = LEAST(admitted_at + W, valid_until). W shorter than the time left: admitted_at + W. W longer: the cap."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        executor = self.conn("executor")
        self.admit_and_commit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
        (row,) = self.leases(ctx)
        self.assertEqual(row["complete_by"], row["admitted_at"] + fx.seconds(self.inst.w_seconds))
        self.assertLess(row["complete_by"], valid)
        ctx, valid, owner_id, root_id = self.live(2.0)
        self.admit_and_commit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
        (row,) = self.leases(ctx)
        self.assertEqual(row["complete_by"], valid)                                         # a lease admitted within W of valid_until is capped
        self.assertLess(row["complete_by"], row["admitted_at"] + fx.seconds(self.inst.w_seconds))
        self.assertEqual(row["valid_until"], valid)

    def test_the_table_check_refuses_a_later_deadline_and_a_non_positive_one(self):
        """E11 CRAFTED INSERTs (the owner role): a lease with a deadline after valid_until, or at/before its admission, cannot be stored."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        now = self.db_now()
        insert = (f"INSERT INTO {self.s}.rw_lease(backend_pid,xid,owner_id,root_id,context_id,generation,operation_id,command_sha256,purpose,phase,"
                  "admitted_at,valid_until,complete_by) VALUES(%s,%s,%s,%s,%s,1,%s,%s,'ARCHIVE_READ','READONLY',%s,%s,%s)")

        def row(label, admitted, until, complete):
            return (1, "crafted-" + label + "-" + uuid.uuid4().hex, owner_id, root_id, ctx, uuid.uuid4(), "1" * 64, admitted, until, complete)
        for label, args in (("later-than-valid-until", (now, valid, valid + fx.seconds(1))), ("equal-to-admission", (now, valid, now)),
                            ("before-admission", (now, valid, now - fx.seconds(1)))):
            with self.assertRaises(psycopg.errors.CheckViolation, msg=label) as caught:
                self.owner.execute(insert, row(label, *args))
            self.assertEqual(caught.exception.diag.constraint_name, "rw_lease_deadline_cap", label)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 0)
        self.owner.execute(insert, row("equal-to-valid-until", now, valid, valid))        # the cap itself is allowed
        self.owner.execute(insert, row("no-valid-until", now, None, now + fx.seconds(self.inst.w_seconds)))
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 2)

    def test_a_read_held_past_its_deadline_is_refused_at_commit_whichever_of_w_and_valid_until_is_earlier(self):
        """T07 R1 (pause before the COMMIT, read-phase lease) with every session timeout at 0: the connection's own timeouts are not
        the bound. The cap decides when valid_until is nearer than W (the stall is shorter than admitted_at + W and is still refused)."""
        for label, valid_in in (("the cap decides", 2.0), ("W decides", 120.0)):
            ctx, valid, owner_id, root_id = self.live(valid_in)
            executor = self.conn("executor", options=self.stall_options())
            for setting in ("statement_timeout", "idle_in_transaction_session_timeout", "lock_timeout", "transaction_timeout"):
                self.assertEqual(executor.execute(f"SHOW {setting}").fetchone()[0], "0", setting)
            op = uuid.uuid4()
            begin(executor)
            try:
                lease = self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id, op=op)
                if valid_in < self.inst.w_seconds:
                    self.assertEqual(lease.complete_by, valid, label)
                else:
                    self.assertLess(lease.complete_by, valid, label)
                self.wait_for_db_time(lease.complete_by)
                with self.assertRaises(psycopg.errors.RaiseException, msg=label) as caught:
                    commit(executor)
                self.assertEqual(caught.exception.diag.message_primary, "RW_DEADLINE", label)
                self.assertEqual(executor.info.transaction_status, TransactionStatus.IDLE, label)
            finally:
                rollback(executor)
            self.assertEqual(self.count("rw_lease", "operation_id=%s", (op,)), 0, label)         # whole rollback: no lease row remains
            if valid_in < self.inst.w_seconds:
                self.refused_admission("RW_LAPSED", ctx, 1, "ARCHIVE_READ", owner_id, root_id, conn=executor)   # and a new admission is refused

    def test_an_operation_that_finishes_before_its_deadline_completes(self):
        """The positive control of the bound: commit at once, the lease row stays."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        self.admit_and_commit(self.conn("executor"), ctx, 1, "ARCHIVE_READ", owner_id, root_id)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 1)


class TrustedClockTests(X1Case):
    def test_overlapping_admissions_are_never_refused_as_a_regression(self):
        """T07 R1 (technical re-review L-2): two connections admit in a tight loop for a few seconds with the real clock. `latest` is read
        BEFORE the sample, so none is refused; sampling first would, from time to time, refuse the later sample of an earlier commit."""
        ctx, valid, _owner, _root = self.live(3600.0)
        roots = [self.craft_root(ctx) for _ in range(2)]
        connections = [self.conn("executor"), self.conn("executor")]
        stop = time.monotonic() + 3.0

        def loop(conn, owner_id, root_id):
            admitted, refusals = 0, []
            while time.monotonic() < stop:
                begin(conn)
                try:
                    self.admit(conn, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
                    commit(conn)
                    admitted += 1
                except store.RealWorkspaceError as error:
                    refusals.append(error.code)
                finally:
                    rollback(conn)
            return admitted, refusals
        workers = [Worker(lambda c=conn, o=owner_id, r=root_id: loop(c, o, r)) for conn, (owner_id, root_id) in zip(connections, roots)]
        results = [w.join(30) for w in workers]
        self.assertEqual([r[1] for r in results], [[], []])
        self.assertGreater(min(r[0] for r in results), 10)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), sum(r[0] for r in results))


class ClockRegressionTests(X1Case):
    INSTALL = "regress"                 # its own install: the test leaves a future instant behind

    def test_admission_is_refused_when_the_clock_is_behind_a_stored_instant(self):
        """T07 R1: 'The test moves a stored instant ahead in a disposable database.' E11 CRAFTED row (owner role): a drain mark for a
        generation that is not current, one hour ahead. Admit reads `latest` (history, marks, leases), samples, and refuses."""
        ctx, valid, owner_id, root_id = self.live(3600.0)
        self.admit_and_commit(self.conn("executor"), ctx, 1, "ARCHIVE_READ", owner_id, root_id)                 # the control: it admits
        self.owner.execute(f"INSERT INTO {self.s}.rw_drain_mark(context_id,generation,issuer_actor,pd_id,git_commit,doc_sha256,marked_at) "
                           "VALUES(%s,99,'crafted','PD-9999',%s,%s,clock_timestamp() + interval '1 hour')", (ctx, "e" * 40, "f" * 64))
        self.assertEqual(self.head(ctx)[0], 1)                       # the mark is for another generation: no pending-withdrawal refusal
        executor = self.conn("executor")
        for purpose in PURPOSES:
            self.refused_admission("RW_CLOCK_REGRESSION", ctx, 1, purpose, owner_id, root_id, conn=executor)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 1)


class DeadlineGuardTests(X1Case):
    """Fact 17. The guard is a constraint trigger of its own with a unique name; the named SET CONSTRAINTS form works on the root-link
    foreign key and leaves the guard pending until COMMIT; naming the guard fires it at once."""

    def test_the_guard_is_one_deferred_constraint_trigger_with_a_unique_name(self):
        """Product path (catalog)."""
        rows = self.admin.execute("SELECT c.conname,c.contype,c.condeferrable,c.condeferred FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace "
                                  "WHERE n.nspname=%s", (self.s,)).fetchall()
        self.assertEqual([r[0] for r in rows].count("rw_lease_deadline_guard"), 1)
        (guard,) = [r for r in rows if r[0] == "rw_lease_deadline_guard"]
        self.assertEqual(guard[1:], ("t", True, True))
        (fk,) = [r for r in rows if r[0] == "rw_root_link_portfolio_fkey"]
        self.assertEqual(fk[1:], ("f", True, True))
        self.assertEqual([r[2:] for r in rows if r[0] == "rw_lease_root_fkey"], [(False, False)])          # not deferrable: not nameable
        trigger = self.admin.execute("SELECT t.tgenabled,t.tgdeferrable,t.tginitdeferred,t.tgtype,p.proname,p.prosecdef FROM pg_trigger t "
                                     "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid "
                                     "WHERE t.tgname='rw_lease_deadline_guard' AND n.nspname=%s AND c.relname='rw_lease'", (self.s,)).fetchall()
        self.assertEqual(trigger, [("O", True, True, 5, "rw_deadline_check", True)])                       # AFTER INSERT, FOR EACH ROW

    def named(self, name):
        return f'SET CONSTRAINTS "{self.s}"."{name}" IMMEDIATE'

    def second_root(self):
        owner_id, root_id = uuid.uuid4(), uuid.uuid4()
        self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
        return owner_id, root_id

    def write_second_root(self, ctx, owner_id, root_id, *, portfolio):
        if portfolio:
            # R3: the write fence fires for the owner too; the crafted insert switches the user triggers of the table off for itself, inside
            # the transaction under test (DDL is transactional, so a rollback restores them). E11 crafted; never product evidence.
            self.owner.execute(f"ALTER TABLE {self.s}.portfolio DISABLE TRIGGER USER")
            self.owner.execute(f"INSERT INTO {self.s}.portfolio(portfolio_id,user_id,reporting_currency) VALUES(%s,%s,'USD')", (root_id, owner_id))
            self.owner.execute(f"ALTER TABLE {self.s}.portfolio ENABLE TRIGGER USER")
        self.owner.execute(f"INSERT INTO {self.s}.rw_root_link(root_id,owner_id,context_id) VALUES(%s,%s,%s)", (root_id, owner_id, ctx))

    def test_the_named_form_fires_the_root_link_key_only_and_leaves_the_guard_pending(self):
        """Fact 17, R1 'must show'. E11 crafted fixture path (design 3.2): in ONE transaction the owner role writes the root-link row (and
        portfolio row) of a second crafted root and calls the read-phase admit on the first."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        # (i) the named form fires THAT key's pending event: a root-link row without a portfolio fails at the SET statement
        second_owner, second_root = self.second_root()
        begin(self.owner)
        try:
            self.admit(self.owner, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
            self.write_second_root(ctx, second_owner, second_root, portfolio=False)
            with self.assertRaises(psycopg.errors.ForeignKeyViolation) as caught:
                self.owner.execute(self.named("rw_root_link_portfolio_fkey"))
            self.assertIn("rw_root_link_portfolio_fkey", str(caught.exception))
        finally:
            rollback(self.owner)
        # (ii) with the portfolio row present the SET passes; the deadline guard is still pending, so a stall past complete_by is refused
        #      at COMMIT with RW_DEADLINE and the WHOLE transaction (second root included) is rolled back
        second_owner, second_root = self.second_root()
        begin(self.owner)
        try:
            lease = self.admit(self.owner, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
            self.write_second_root(ctx, second_owner, second_root, portfolio=True)
            self.owner.execute(self.named("rw_root_link_portfolio_fkey"))
            self.wait_for_db_time(lease.complete_by)
            with self.assertRaises(psycopg.errors.RaiseException) as caught:
                commit(self.owner)
            self.assertEqual(caught.exception.diag.message_primary, "RW_DEADLINE")
        finally:
            rollback(self.owner)
        self.assertEqual(self.count("rw_root_link", "root_id=%s", (second_root,)), 0)
        self.assertEqual(self.count("portfolio", "portfolio_id=%s", (second_root,)), 0)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 0)
        # (iii) the control: the same transaction committed before the deadline succeeds (the refusal in (ii) is the stall's)
        second_owner, second_root = self.second_root()
        begin(self.owner)
        try:
            self.admit(self.owner, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
            self.write_second_root(ctx, second_owner, second_root, portfolio=True)
            self.owner.execute(self.named("rw_root_link_portfolio_fkey"))
            commit(self.owner)
        finally:
            rollback(self.owner)
        self.assertEqual(self.count("rw_root_link", "root_id=%s", (second_root,)), 1)

    def test_naming_the_guard_fires_it_at_once(self):
        """Fact 17, second named showing: naming the deadline guard fires its pending event at the SET statement itself, so a stall past
        complete_by is refused there (RW_DEADLINE) and not at COMMIT. This is also the control for the characterisation test below."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        begin(self.owner)
        try:
            lease = self.admit(self.owner, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
            self.wait_for_db_time(lease.complete_by)
            with self.assertRaises(psycopg.errors.RaiseException) as caught:
                self.owner.execute(self.named("rw_lease_deadline_guard"))
            self.assertEqual(caught.exception.diag.message_primary, "RW_DEADLINE")
        finally:
            rollback(self.owner)

    def test_what_postgres_does_when_set_constraints_names_a_key_that_cannot_be_deferred_or_does_not_exist(self):
        """OBSERVED SERVER BEHAVIOUR (PostgreSQL 17), recorded because the design leans on the manual's sentence that the names given to
        SET CONSTRAINTS "must all be deferrable" (design 3.2) and the first version of this test assumed that the server refuses a
        non-deferrable name in every form. It does not: naming a NOT DEFERRABLE key IMMEDIATE is accepted and does nothing (there is no
        pending event for that key to fire); only DEFERRED is refused (SQLSTATE 42809). A name that does not exist is refused in both
        forms (42704). The design's choice stands: the lease-to-root-link key is not named by any product path, and the guard test names the
        root-link-to-portfolio key, which is deferrable. Nothing in the product depends on the refusal that the first version expected."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        key = "rw_lease_root_fkey"
        begin(self.owner)
        try:
            lease = self.admit(self.owner, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
            self.owner.execute(self.named(key))                              # accepted, a no-op: it fires nothing
            self.wait_for_db_time(lease.complete_by)
            with self.assertRaises(psycopg.errors.RaiseException) as caught:  # and the guard, still pending, still refuses at COMMIT
                commit(self.owner)
            self.assertEqual(caught.exception.diag.message_primary, "RW_DEADLINE")
        finally:
            rollback(self.owner)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 0)
        for form in ("IMMEDIATE", "DEFERRED"):
            begin(self.owner)
            try:
                with self.assertRaises(psycopg.errors.UndefinedObject, msg=form) as caught:
                    self.owner.execute(f'SET CONSTRAINTS "{self.s}"."rw_no_such_constraint" {form}')
                self.assertEqual(caught.exception.sqlstate, "42704", form)
            finally:
                rollback(self.owner)
        begin(self.owner)
        try:
            with self.assertRaises(psycopg.errors.WrongObjectType) as caught:
                self.owner.execute(f'SET CONSTRAINTS "{self.s}"."{key}" DEFERRED')
            self.assertEqual(caught.exception.sqlstate, "42809")
            self.assertIn("is not deferrable", str(caught.exception))
        finally:
            rollback(self.owner)

    def test_characterisation_a_session_that_fires_the_guard_early_commits_unchecked(self):
        """CHARACTERISATION of a disclosed limit (design 3.1 limit (ii), section 9); not a requirement. A session that fires the guard early
        (SET CONSTRAINTS ALL IMMEDIATE, or by name) and then stalls past complete_by is NOT refused at COMMIT by this trigger. The product
        create/read tail (R5) never does this (its own static and recorder tests); the statement-time checks of R2/R3 cannot be bypassed
        this way."""
        for how in ("ALL", "by name"):
            ctx, valid, owner_id, root_id = self.live(120.0)
            executor = self.conn("executor", options=self.stall_options())
            begin(executor)
            try:
                lease = self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
                executor.execute("SET CONSTRAINTS ALL IMMEDIATE" if how == "ALL" else self.named("rw_lease_deadline_guard"))
                self.wait_for_db_time(lease.complete_by)
                commit(executor)                                    # not refused: the trigger already ran, before complete_by
            finally:
                rollback(executor)
            (row,) = self.leases(ctx)
            self.assertLess(row["complete_by"], self.db_now(), how)         # the lease was committed after its own deadline


class RenewalTests(X1Case):
    def test_renewal_needs_a_reference_and_is_a_publisher_act_only(self):
        ctx, valid, owner_id, root_id = self.live(120.0)
        result = self.renew(ctx, 1, valid_until=valid, ref=None)
        self.assertEqual((result.status, result.data["code"]), (2, "RW_DECISION_REF_REQUIRED"))
        publisher = self.conn("publisher")
        call = f"SELECT * FROM {self.s}.rw_renew(%s,1,%s,%s,%s,%s,%s,%s,%s,NULL)"
        for bad in (("", "PD-9002", "c" * 40, "d" * 64), ("a", "PD-2", "c" * 40, "d" * 64), ("a", "PD-9002", "c" * 39, "d" * 64), ("a", "PD-9002", "c" * 40, "D" * 64),
                    (None, "PD-9002", "c" * 40, "d" * 64)):
            self.assertRefused("RW_DECISION_REF_REQUIRED", lambda b=bad: publisher.execute(
                call, (ctx, Jsonb(fx.ALL_RIGHTS), valid, Jsonb([e.as_json() for e in fx.hg4_shape(self.bound())]), b[0], b[1], b[2], b[3])))
        for who in ("executor", "loader"):
            conn = self.conn(who)
            self.assertDenied(lambda c=conn: c.execute(call, (ctx, Jsonb(fx.ALL_RIGHTS), valid, Jsonb([]), "a", "PD-9002", "c" * 40, "d" * 64)))
        self.assertEqual(len(self.history(ctx)), 1)

    def test_a_valid_renewal_restores_admission_and_a_bound_root_still_resolves(self):
        """T07 R1: a lapsed context is renewed by a human act; admission works again at the new generation; the root bound to the original
        context (E11 crafted fixture) still resolves to it."""
        ctx, valid, owner_id, root_id = self.live(2.0)
        self.wait_for_db_time(valid)
        executor = self.conn("executor")
        self.refused_admission("RW_LAPSED", ctx, 1, "ARCHIVE_READ", owner_id, root_id, conn=executor)
        new_valid = self.db_now() + fx.seconds(120)
        result = self.renew(ctx, 1, valid_until=new_valid)
        self.assertEqual((result.status, result.outcome, result.data["generation"]), (0, "RENEWED", 2), result.text)
        self.assertNotIn("moved earlier", result.text)
        first, second = self.history(ctx)
        self.assertEqual((first["valid_until"], second["valid_until"], second["generation"]), (valid, new_valid, 2))
        self.assertEqual((second["issuer_actor"], second["pd_id"], second["git_commit"], second["doc_sha256"]), (fx.ACTOR, "PD-9002", "c" * 40, "d" * 64))
        self.assertEqual(len(second["basis"]), len(fx.SOURCES))
        self.assertEqual(self.head(ctx), (2, fx.ALL_RIGHTS, "LEASE", new_valid))
        self.admit_and_commit(executor, ctx, 2, "ARCHIVE_READ", owner_id, root_id)
        self.refused_admission("RW_GENERATION_DIFFERS", ctx, 1, "ARCHIVE_READ", owner_id, root_id, conn=executor)
        self.assertEqual(store.list_roots(executor, self.s, owner_id), [(root_id, ctx, 2)])

    def test_an_equal_valid_until_restores_the_rights_after_a_withdrawal_without_extending_the_lease(self):
        """E25 / the last step of R8: withdraw (all four rights off), then renew at the equal date."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        withdrawn = self.tool().withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual((withdrawn.status, withdrawn.outcome), (0, "WITHDRAWN"), withdrawn.text)
        self.refused_admission("RW_WITHDRAWN", ctx, 2, "ARCHIVE_READ", owner_id, root_id)
        result = self.renew(ctx, 2, valid_until=valid)
        self.assertEqual((result.status, result.data["generation"], result.data["moved_earlier"]), (0, 3, False), result.text)
        self.assertEqual(result.data["old_valid_until"], result.data["new_valid_until"])
        self.assertEqual(self.head(ctx), (3, fx.ALL_RIGHTS, "LEASE", valid))
        self.admit_and_commit(self.conn("executor"), ctx, 3, "ARCHIVE_READ", owner_id, root_id)

    def test_date_correction_the_pin_scenario(self):
        """E25 amended (conformance R3C-M1; technical TR3-M4), on invented data: publish with valid_until V and bound U (V <= U), then
        correct to V' < V with entries whose bound U' >= V'. The old V no longer admits; both generations stay; the tool says so."""
        bound = self.bound(60)
        snap, V, _ = self.publish(valid_in=30.0, evidence=fx.hg4_shape(bound))
        ctx = snap.context_id
        owner_id, root_id = self.craft_root(ctx)
        corrected = self.db_now() + fx.seconds(3)
        result = self.renew(ctx, 1, valid_until=corrected, evidence=fx.hg4_shape(self.bound(120)))
        self.assertEqual((result.status, result.outcome, result.data["moved_earlier"]), (0, "RENEWED", True), result.text)
        self.assertIn("`valid_until` moved earlier: %s to %s" % (store.iso(V), store.iso(corrected)), result.text)
        first, second = self.history(ctx)
        self.assertEqual((first["valid_until"], second["valid_until"]), (V, corrected))                # both generations stay in the history
        self.assertEqual(self.head(ctx)[3], corrected)
        executor = self.conn("executor")
        lease = self.admit_and_commit(executor, ctx, 2, "ARCHIVE_READ", owner_id, root_id)             # a lease admitted after the correction
        self.assertLessEqual(lease.complete_by, corrected)
        self.wait_for_db_time(corrected)
        self.refused_admission("RW_LAPSED", ctx, 2, "ARCHIVE_READ", owner_id, root_id, conn=executor)    # the old V (30 s) would still admit
        self.assertLess(self.db_now(), V)
        self.assertEqual(store.list_roots(executor, self.s, owner_id), [(root_id, ctx, 2)])           # the bound root still resolves

    def test_a_term_that_already_renewed_is_a_renewal_at_the_equal_date_and_not_a_withdrawal(self):
        """Conformance R3R-L2: the pin shows the old term is over and no notice was given; the owner records a renewal at the equal date
        whose entry carries the Renewal Term's end. Accepted, the context stays live, no drain mark exists."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        result = self.renew(ctx, 1, valid_until=valid, evidence=fx.hg4_shape(self.bound(7200)))
        self.assertEqual((result.status, result.data["generation"], result.data["moved_earlier"]), (0, 2, False), result.text)
        self.assertEqual(self.marks(ctx), [])
        self.admit_and_commit(self.conn("executor"), ctx, 2, "ARCHIVE_READ", owner_id, root_id)

    def test_refused_renewals_append_nothing(self):
        ctx, valid, owner_id, root_id = self.live(120.0)
        bound = self.bound(600)
        cases = [
            ("at the clock or before", dict(valid_until=self.db_now() - fx.seconds(1)), "RW_VALID_UNTIL_PAST", None),
            ("no entries", dict(valid_until=valid, evidence=[]), "RW_EXPIRY_UNSUPPORTED", "BASIS_COUNT"),
            ("later than its own earliest bound", dict(valid_until=bound + fx.seconds(1), evidence=fx.hg4_shape(bound)), "RW_EXPIRY_UNSUPPORTED", "PLAUSIBILITY"),
            ("a source without an entry", dict(valid_until=valid, evidence=fx.hg4_shape(bound)[:2]), "RW_EXPIRY_UNSUPPORTED", "BASIS_COUNT"),
            ("no valid_until with a lease term", dict(valid_until=None, evidence=fx.hg4_shape(bound)), "RW_EXPIRY_UNSUPPORTED", "NO_VALID_UNTIL"),
        ]
        for label, kwargs, code, detail in cases:
            result = self.renew(ctx, 1, **kwargs)
            self.assertEqual((result.status, result.data["code"], result.data["detail"] or None), (2, code, detail), label + ": " + result.text)
        wrong = self.renew(ctx, 7, valid_until=valid)
        self.assertEqual(wrong.data["code"], "RW_GENERATION_DIFFERS")
        missing = self.renew("0" * 64, 1, valid_until=valid)
        self.assertEqual(missing.data["code"], "RW_NOT_FOUND")
        self.assertEqual(len(self.history(ctx)), 1)
        self.assertEqual(self.head(ctx)[0], 1)

    def test_a_correction_waits_for_an_in_flight_read_and_appends_nothing_when_its_lock_timeout_expires(self):
        """T07 R1 / T02: the renewal takes the head EXCLUSIVE, so it waits for a read lease in flight; at its lock_timeout it appends
        nothing and exits with a status of its own, naming the blocking lease. After the read ends, the same command succeeds."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        executor = self.conn("executor")
        pid = executor.execute("SELECT pg_backend_pid()").fetchone()[0]
        begin(executor)
        try:
            lease = self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
            tool = self.tool(lock_timeout_ms=1500)
            started = time.monotonic()
            result = self.renew(ctx, 1, valid_until=self.db_now() + fx.seconds(60), tool=tool)             # an earlier date: a correction
            self.assertGreaterEqual(time.monotonic() - started, 1.3)
            self.assertEqual((result.status, result.outcome), (5, "LOCK_TIMEOUT"), result.text)
            self.assertIn("blocking lease: backend %d, complete_by " % pid, result.text)
            self.assertNotIn("renewed context", result.text)
            self.assertEqual(len(self.history(ctx)), 1)
            self.assertEqual(self.head(ctx)[0], 1)
            blocking = self.conn("publisher").execute(f"SELECT r_pid,r_complete_by FROM {self.s}.rw_in_flight(%s)", (ctx,)).fetchall()
            self.assertEqual([b[0] for b in blocking], [pid])
            self.assertLessEqual(abs(blocking[0][1] - lease.complete_by), fx.seconds(1) / 1000000)  # named by the deadline it carries, to the microsecond
        finally:
            rollback(executor)
        retry = self.renew(ctx, 1, valid_until=self.db_now() + fx.seconds(60))
        self.assertEqual((retry.status, retry.data["moved_earlier"]), (0, True), retry.text)
        self.assertEqual(store.list_roots(executor, self.s, owner_id), [(root_id, ctx, 2)])


class StrictComparisonTests(X1Case):
    """L-10 (technical review R1): the strict comparisons of time are pinned by behaviour at EQUAL instants, which the real clock
    cannot produce. The guard, the lapse, the floor of a publish or renewal and the clock-regression test all call one predicate,
    `rw_reached(now, limit)` = now >= limit (the static tests pin that every one of them does). E11 crafted call: the owner role of the
    disposable database runs the predicate; no runtime role may (the privilege tests)."""

    def reached(self, now, limit):
        return self.owner.execute(f"SELECT {self.s}.rw_reached(%s,%s)", (now, limit)).fetchone()[0]

    def test_the_first_refused_instant_is_the_limit_itself(self):
        micro = dt.timedelta(microseconds=1)
        t = self.db_now()
        self.assertIs(self.reached(t, t), True)              # complete_by itself is refused; valid_until itself is a lapse; a new valid_until equal to the clock is past
        self.assertIs(self.reached(t - micro, t), False)     # one microsecond early is still inside
        self.assertIs(self.reached(t + micro, t), True)
        self.assertIs(self.reached(t, None), False)          # no limit, never reached
        self.assertIs(self.reached(None, t), False)

    def test_no_runtime_role_can_call_the_predicate(self):
        for who in ("executor", "loader", "publisher"):
            conn = self.conn(who)
            self.assertDenied(lambda c=conn: c.execute(f"SELECT {self.s}.rw_reached(clock_timestamp(),clock_timestamp())"))


class PredicateWiringTests(X1Case):
    """L-10 (technical review R1), the other half. The edge at EQUAL instants can be shown only on the predicate itself (above): the real
    clock never produces an instant equal to a stored one, and no hook may supply a time. What stands between a call site and that proof is
    that the site CALLS the predicate, clock first and limit second. This class shows that behaviourally.

    In an install of its own the owner role (E11 crafted, restored after every test) replaces `rw_reached` with one that is true 30 s
    early (or 30 s late). Every site that compares an instant with the clock must then change its answer, and a site that was rewritten
    inline as `>` or `>=` cannot: the lapse of a lease, the floor of a publish, the floor of a renewal, the clock-regression test and the
    COMMIT-time deadline guard. Each test has its control: the same step before the replacement succeeds."""
    INSTALL = "wiring"

    def setUp(self):
        super().setUp()
        self.original = self.owner.execute("SELECT pg_get_functiondef(to_regprocedure(%s))", (f"{self.s}.rw_reached(timestamptz,timestamptz)",)).fetchone()[0]
        self.addCleanup(self.restore)

    def restore(self):
        self.owner.execute("SET lock_timeout = '5s'")
        self.owner.execute(self.original)

    def replace_predicate(self, early_seconds):
        """reached(now, limit) = now >= limit - early_seconds. Later connections see it; open transactions are not touched."""
        self.owner.execute("SET lock_timeout = '5s'")
        self.owner.execute(f"CREATE OR REPLACE FUNCTION {self.s}.rw_reached(p_now timestamptz,p_limit timestamptz) RETURNS boolean "
                           f"LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,{self.s},pg_temp AS $$ "
                           f"SELECT COALESCE(p_now>=p_limit-make_interval(secs=>{int(early_seconds)}),false) $$")

    def test_the_replacement_changes_the_answer_and_the_restore_puts_it_back(self):
        t = self.db_now()
        self.assertIs(self.owner.execute(f"SELECT {self.s}.rw_reached(%s,%s)", (t, t + dt.timedelta(seconds=10))).fetchone()[0], False)
        self.replace_predicate(30)
        self.assertIs(self.owner.execute(f"SELECT {self.s}.rw_reached(%s,%s)", (t, t + dt.timedelta(seconds=10))).fetchone()[0], True)
        self.restore()
        self.assertIs(self.owner.execute(f"SELECT {self.s}.rw_reached(%s,%s)", (t, t + dt.timedelta(seconds=10))).fetchone()[0], False)

    def test_the_lapse_of_a_lease_calls_the_predicate_with_the_clock_first_and_valid_until_second(self):
        ctx, valid, owner_id, root_id = self.live(20.0)
        self.admit_and_commit(self.conn("executor"), ctx, 1, "ARCHIVE_READ", owner_id, root_id)                  # the control: 20 s are left
        self.replace_predicate(30)
        self.refused_admission("RW_LAPSED", ctx, 1, "ARCHIVE_READ", owner_id, root_id, conn=self.conn("executor"))

    def test_the_floor_of_a_publish_calls_the_predicate(self):
        self.publish(valid_in=20.0)                                                                              # the control
        self.replace_predicate(30)
        snap, _valid, refused = self.publish(valid_in=20.0, expect_ok=False)
        self.assertEqual(refused.status, 2, refused.text)
        self.assertEqual(refused.data["code"], "RW_VALID_UNTIL_PAST", refused.text)
        self.assertEqual(self.count("rw_snapshot", "context_id=%s", (snap.context_id,)), 0)

    def test_the_floor_of_a_renewal_calls_the_predicate(self):
        ctx, valid, owner_id, root_id = self.live(20.0)
        renewed = self.renew(ctx, 1, valid_until=self.db_now() + dt.timedelta(seconds=20))                      # the control
        self.assertEqual(renewed.status, 0, renewed.text)
        self.replace_predicate(30)
        refused = self.renew(ctx, 2, valid_until=self.db_now() + dt.timedelta(seconds=25))
        self.assertEqual(refused.status, 2, refused.text)
        self.assertEqual(refused.data["code"], "RW_VALID_UNTIL_PAST", refused.text)
        self.assertEqual(len(self.history(ctx)), 2)

    def test_the_clock_regression_test_calls_the_predicate_with_the_clock_first_and_the_latest_instant_second(self):
        ctx, valid, owner_id, root_id = self.live(120.0)
        self.admit_and_commit(self.conn("executor"), ctx, 1, "ARCHIVE_READ", owner_id, root_id)                  # the control
        self.replace_predicate(-30)                                                                              # "reached" only 30 s after the limit
        self.refused_admission("RW_CLOCK_REGRESSION", ctx, 1, "ARCHIVE_READ", owner_id, root_id, conn=self.conn("executor"))

    def test_the_deadline_guard_at_commit_calls_the_predicate_with_the_clock_first_and_complete_by_second(self):
        ctx, valid, owner_id, root_id = self.live(120.0)
        self.admit_and_commit(self.conn("executor"), ctx, 1, "ARCHIVE_READ", owner_id, root_id)                  # the control: a timely commit passes
        self.replace_predicate(30)
        executor = self.conn("executor")                                                                         # a new backend: no plan under the old definition
        begin(executor)
        try:
            self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
            with self.assertRaises(psycopg.errors.RaiseException) as caught:
                commit(executor)
            self.assertEqual(caught.exception.diag.message_primary, "RW_DEADLINE")
        finally:
            rollback(executor)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 1)                                     # only the control's lease


class MarkerTests(X1Case):
    """L-1 (technical review R1): the advisory-lock markers only NAME leases. Safety never reads them, and a session that interferes with
    them can make a lease unnamed or invent a phantom one, but can neither delay nor deny an admission."""

    def test_a_session_holding_a_marker_key_exclusively_cannot_delay_or_deny_an_admission(self):
        """The reviewer's blocking scenario: the loader (no lease, no table grant) held an EXCLUSIVE lock on the context's marker key and
        the executor's next admit waited for it. The markers are try-locks now: the admission is immediate, and only unnamed."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        loader = self.conn("loader")
        loader.execute("SELECT pg_advisory_lock(hashtext('rw.lease.ctx'),hashtext(%s))", (ctx,))
        executor = self.conn("executor", options="-c timezone=UTC -c lock_timeout=5000")
        publisher = self.conn("publisher")
        started = time.monotonic()
        begin(executor)
        try:
            self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
            self.assertLess(time.monotonic() - started, 2.0)                      # not held up by the loader's exclusive lock
            pid = executor.execute("SELECT pg_backend_pid()").fetchone()[0]
            named = publisher.execute(f"SELECT r_pid FROM {self.s}.rw_in_flight(%s)", (ctx,)).fetchall()
            self.assertNotIn(pid, [row[0] for row in named])                       # the lease exists but is unnamed: the limit of the markers
            commit(executor)
        finally:
            rollback(executor)
            loader.execute("SELECT pg_advisory_unlock_all()")
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 1)

    def test_a_forged_marker_is_listed_as_a_phantom_blocker_which_is_why_the_list_is_advisory(self):
        """CHARACTERISATION of a documented limit, not a requirement: any connected session can take both marker shapes, and
        `rw_in_flight` then lists it with the `complete_by` it chose. Nothing safety-related reads this list."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        loader = self.conn("loader")
        forged_key = 2 ** 62 + 1_000_000 * 1_000_000_000                           # 2^62 + microseconds(2001-09-09T01:46:40Z)
        loader.execute("SELECT pg_advisory_lock_shared(hashtext('rw.lease.ctx'),hashtext(%s))", (ctx,))
        loader.execute("SELECT pg_advisory_lock_shared(%s)", (forged_key,))
        try:
            pid = loader.execute("SELECT pg_backend_pid()").fetchone()[0]
            rows = self.conn("publisher").execute(f"SELECT r_pid,r_complete_by FROM {self.s}.rw_in_flight(%s)", (ctx,)).fetchall()
            self.assertEqual([(p, c.astimezone(dt.timezone.utc)) for p, c in rows],
                             [(pid, dt.datetime(2001, 9, 9, 1, 46, 40, tzinfo=dt.timezone.utc))])
            self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 0)    # and there is no lease behind it
        finally:
            loader.execute("SELECT pg_advisory_unlock_all()")

    def test_an_admission_holds_one_exclusive_lock_below_the_marker_range_and_two_shared_markers(self):
        """The gateway's own exclusive one-bigint lock (the root lock) lies below 2^62, so its high word is under 2^30 and it can never
        be taken for a deadline marker (shared, high word in [2^30, 2^30 + 2^21)). What an admission holds, in pg_locks."""
        ctx, valid, owner_id, root_id = self.live(120.0)
        executor = self.conn("executor")
        begin(executor)
        try:
            lease = self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
            pid = executor.execute("SELECT pg_backend_pid()").fetchone()[0]
            held = self.owner.execute("SELECT mode,objsubid,classid::bigint,objid::bigint FROM pg_locks WHERE locktype='advisory' AND pid=%s AND granted ORDER BY mode,objsubid",
                                      (pid,)).fetchall()
            exclusive = [row for row in held if row[0] == "ExclusiveLock"]
            shared = [row for row in held if row[0] == "ShareLock"]
            # R3 added the operation lock (one more exclusive one-bigint lock, taken by admit so a replay of an operation id is serialised
            # with the first run); both lie below 2^62 and so below the marker range
            self.assertEqual([(row[1], row[2] < 2 ** 30) for row in exclusive], [(1, True), (1, True)])
            self.assertEqual(sorted(row[1] for row in shared), [1, 2])
            one_key = [row for row in shared if row[1] == 1]
            self.assertTrue(2 ** 30 <= one_key[0][2] < 2 ** 30 + 2 ** 21)
            key = one_key[0][2] * 2 ** 32 + one_key[0][3]
            micros = (lease.complete_by - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)) // dt.timedelta(microseconds=1)
            self.assertEqual(key - 2 ** 62, micros)                                                      # the marker's key encodes complete_by
            commit(executor)
        finally:
            rollback(executor)


class TestSwitchAdmissionAndLapseTests(AdmissionAndLapseTests):
    """M-4 (technical review R1; the R1 exit 'a lease minted, bounded and refused on invented data of both test scopes'): every admission
    and lapse test above, repeated on a context of the TEST_SWITCH scope (the real branch on invented, synthetic-labelled data)."""
    SCOPE = "TEST_SWITCH"


class TestSwitchCappedDeadlineTests(CappedDeadlineTests):
    """M-4: the capped deadline, the table check and the COMMIT-time deadline guard, repeated on a TEST_SWITCH context."""
    SCOPE = "TEST_SWITCH"


if __name__ == "__main__":
    import unittest
    unittest.main()
