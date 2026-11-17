"""F1 R1, PostgreSQL: publication races (T02) and withdrawal with cancellation (design 3.2, "Withdrawal and cancellation").

R1's in-flight work is a READ-phase lease on a registered root (E11 crafted root fixture; the lease, the admit, the locks, the drain mark
and the publisher commands are the product's). The create-phase counterparts need an economic write and are R3 (crafted bundles) and
R5 (the shared create tail); nothing here claims them.

T02 'blocking-pid causality': a test that expects a session to WAIT proves it by asking the server which backend blocks it
(pg_blocking_pids), not by a sleep. Without a provisioning superuser the tests SKIP with the reason.
"""
from __future__ import annotations

import sys
import threading
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
from persistence import real_workspace_store as store  # noqa: E402
from real_gateway_kit import (GatewayCase, Worker, begin, commit, rollback, setUpModule, tearDownModule, wait_until)  # noqa: E402,F401

PENDING = "RW_WITHDRAWAL_PENDING"


class WithdrawalCase(GatewayCase):
    INSTALL = "wd"

    def live(self, valid_in=300.0):
        snap, valid, _result = self.publish(valid_in=valid_in)
        owner_id, root_id = self.craft_root(snap.context_id)
        return snap.context_id, valid, owner_id, root_id

    def pid(self, conn):
        return conn.execute("SELECT pg_backend_pid()").fetchone()[0]

    def blockers(self, pid):
        return self.admin.execute("SELECT pg_blocking_pids(%s)", (pid,)).fetchone()[0]

    def hold_read(self, ctx, owner_id, root_id, **conn_kw):
        """An executor session with a READ-phase lease in flight (transaction open, head and mode share-locked)."""
        executor = self.conn("executor", **conn_kw)
        begin(executor)
        lease = self.admit(executor, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
        return executor, lease

    def refused_admission(self, code, ctx, generation, owner_id, root_id, purpose="ARCHIVE_READ"):
        conn = self.conn("executor")
        begin(conn)
        try:
            return self.assertRefused(code, lambda: self.admit(conn, ctx, generation, purpose, owner_id, root_id))
        finally:
            rollback(conn)


class PublicationRaceTests(WithdrawalCase):
    """T02: separate connections, shared/exclusive stable-head lock ordering through outer commit and whole rollback."""

    def renewal(self, ctx, expected_generation, valid):
        """The renewal function called directly, so that a test can leave its transaction open (head EXCLUSIVE, uncommitted)."""
        return (f"SELECT * FROM {self.s}.rw_renew(%s,{int(expected_generation)},%s,%s,%s,'invented-owner','PD-9002',%s,%s,NULL)",
                (ctx, Jsonb(fx.ALL_RIGHTS), valid, Jsonb([e.as_json() for e in fx.hg4_shape(self.bound())]), "c" * 40, "d" * 64))

    def test_a_renewal_waits_for_a_reader_and_the_server_names_the_reader_as_the_blocker(self):
        ctx, valid, owner_id, root_id = self.live()
        executor, lease = self.hold_read(ctx, owner_id, root_id)
        reader_pid = self.pid(executor)
        publisher = self.conn("publisher")
        publisher_pid = self.pid(publisher)
        worker = Worker(lambda: store.RealPublisher(publisher, self.s, lock_timeout_ms=20000).renew(
            ctx, 1, rights=fx.ALL_RIGHTS, valid_until=valid + fx.seconds(10), evidence=fx.hg4_shape(self.bound()), actor=fx.ACTOR, ref=fx.REF_OTHER))
        try:
            wait_until(lambda: self.blockers(publisher_pid) == [reader_pid], timeout=3.0, what="the renewal to wait on the reader")
            self.assertFalse(worker.done)
            self.assertEqual(len(self.history(ctx)), 1)
            commit(executor)                                                    # the read ends before its deadline
        finally:
            rollback(executor)
        result = worker.join(30)
        self.assertEqual((result.status, result.data["generation"]), (0, 2), result.text)

    def test_an_admission_waits_for_a_renewal_in_progress_then_sees_the_new_generation_or_the_old_one_after_a_rollback(self):
        ctx, valid, owner_id, root_id = self.live()
        publisher = self.conn("publisher")
        publisher_pid = self.pid(publisher)
        for outcome, generation in (("commit", 1), ("rollback", 2)):
            call, params = self.renewal(ctx, generation, valid + fx.seconds(20))
            begin(publisher)
            try:
                publisher.execute(call, params)                                      # head EXCLUSIVE, uncommitted
                executor = self.conn("executor")
                executor_pid = self.pid(executor)

                def attempt(conn=executor, expected=generation):
                    begin(conn)
                    try:
                        self.admit(conn, ctx, expected, "ARCHIVE_READ", owner_id, root_id)
                        commit(conn)
                        return "ADMITTED"
                    except store.RealWorkspaceError as error:
                        return error.code
                    finally:
                        rollback(conn)
                worker = Worker(attempt)
                wait_until(lambda: self.blockers(executor_pid) == [publisher_pid], timeout=3.0, what="the admission to wait on the renewal")
                self.assertFalse(worker.done)
                if outcome == "commit":
                    commit(publisher)
                else:
                    rollback(publisher)
            finally:
                rollback(publisher)
            self.assertEqual(worker.join(30), "RW_GENERATION_DIFFERS" if outcome == "commit" else "ADMITTED", outcome)
        self.assertEqual(self.head(ctx)[0], 2)                      # the committed renewal only; the rolled-back one left nothing
        self.assertEqual(len(self.history(ctx)), 2)

    def test_two_publishers_of_different_contexts_and_a_reader_do_not_deadlock(self):
        """Lock order everywhere is mode shared, then head: publishing a second context while a reader holds the first neither blocks nor
        deadlocks, and the publish still opens nothing it should not."""
        ctx, valid, owner_id, root_id = self.live()
        executor, lease = self.hold_read(ctx, owner_id, root_id)
        try:
            other, _valid, result = self.publish(valid_in=300.0)
            self.assertEqual(result.status, 0, result.text)
            commit(executor)
        finally:
            rollback(executor)
        self.assertEqual(self.count("rw_head"), self.count("rw_snapshot"))


class WithdrawalTests(WithdrawalCase):
    def test_withdrawal_during_an_in_flight_read_marks_first_waits_then_applies(self):
        """R1: the drain mark commits first with issuer, the reference triple and the server time; a new admission is refused at once
        with the pending code; the withdrawal then waits for the reader (the server names it) and applies once the read ends, and its
        generation row names the mark."""
        ctx, valid, owner_id, root_id = self.live()
        executor, lease = self.hold_read(ctx, owner_id, root_id)
        reader_pid = self.pid(executor)
        publisher = self.conn("publisher")
        publisher_pid = self.pid(publisher)
        worker = Worker(lambda: store.RealPublisher(publisher, self.s, lock_timeout_ms=20000).withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER))
        try:
            marks = wait_until(lambda: self.marks(ctx), timeout=5.0, what="the drain mark to commit")
            (mark,) = marks
            self.assertEqual((mark["generation"], mark["issuer_actor"], mark["pd_id"], mark["git_commit"], mark["doc_sha256"]),
                             (1, fx.ACTOR, "PD-9002", "c" * 40, "d" * 64))
            self.assertLessEqual(mark["marked_at"], self.db_now())
            self.refused_admission(PENDING, ctx, 1, owner_id, root_id)               # new admissions stop, although the reader still holds a share lock
            wait_until(lambda: self.blockers(publisher_pid) == [reader_pid], timeout=3.0, what="the withdrawal to wait on the reader")
            self.assertFalse(worker.done)
            self.assertEqual(len(self.history(ctx)), 1)                             # nothing appended while the read is in flight
            commit(executor)
        finally:
            rollback(executor)
        result = worker.join(30)
        self.assertEqual((result.status, result.outcome), (0, "WITHDRAWN"), result.text)
        first, second = self.history(ctx)
        self.assertEqual((second["generation"], second["drain_mark_id"], set(second["rights"].values())), (2, mark["mark_id"], {False}))
        self.assertEqual((second["issuer_actor"], second["pd_id"], second["git_commit"], second["doc_sha256"]), (fx.ACTOR, "PD-9002", "c" * 40, "d" * 64))
        self.assertEqual((second["expiry_kind"], second["valid_until"], second["basis"]), (first["expiry_kind"], first["valid_until"], first["basis"]))
        self.assertEqual(self.head(ctx)[:3], (2, second["rights"], "LEASE"))
        self.refused_admission("RW_WITHDRAWN", ctx, 2, owner_id, root_id)

    def test_a_timed_out_withdrawal_leaves_a_recorded_pending_mark_and_never_says_done(self):
        """R1 (conformance re-review DC-M1; technical re-review M-4), read back from the database."""
        ctx, valid, owner_id, root_id = self.live()
        executor, lease = self.hold_read(ctx, owner_id, root_id)
        reader_pid = self.pid(executor)
        tool = self.tool(lock_timeout_ms=1000)
        try:
            result = tool.withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
            (mark,) = self.marks(ctx)
            self.assertEqual((result.status, result.outcome), (3, "NOT_YET_EFFECTIVE"), result.text)
            self.assertIn("not yet effective for in-flight work; new admissions refused since %s" % store.iso(mark["marked_at"]), result.text)
            self.assertIn("blocking lease: backend %d, complete_by " % reader_pid, result.text)
            self.assertNotIn("done", result.text.lower())
            self.assertEqual((mark["issuer_actor"], mark["pd_id"], mark["git_commit"], mark["doc_sha256"]), (fx.ACTOR, "PD-9002", "c" * 40, "d" * 64))
            self.assertEqual(len(self.history(ctx)), 1)                              # no new generation
            self.assertEqual(self.head(ctx)[0], 1)
            status = self.tool().status(ctx)
            self.assertIn("pending drain mark %d on context %s generation 1 by %s under PD-9002" % (mark["mark_id"], ctx, fx.ACTOR), status.text)
            self.refused_admission(PENDING, ctx, 1, owner_id, root_id)
            age = self.conn("publisher").execute(f"SELECT age FROM {self.s}.rw_pending_marks WHERE mark_id=%s", (mark["mark_id"],)).fetchone()[0]
            self.assertGreaterEqual(age, fx.seconds(0))
        finally:
            rollback(executor)
        again = tool.withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)             # re-running finds the mark and continues from the wait
        self.assertEqual((again.status, again.outcome), (0, "WITHDRAWN"), again.text)
        self.assertIn("drain mark %d already recorded" % mark["mark_id"], again.text)
        self.assertEqual(self.marks(ctx), [mark])                                    # the same mark, not a second one
        first, second = self.history(ctx)
        self.assertEqual((second["generation"], second["drain_mark_id"]), (2, mark["mark_id"]))
        finished = tool.withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual(finished.status, 0)
        self.assertIn("done (already effective)", finished.text)
        self.assertEqual(len(self.history(ctx)), 2)

    def test_a_statement_timeout_during_the_wait_leaves_the_mark_pending_and_the_tool_says_so(self):
        """M-3 (technical review R1), the reviewer's run: the publisher's connection has statement_timeout 1 s and the tool's lock_timeout is
        4 s, so step 2 ends by the STATEMENT timeout (QueryCanceled), not by the lock timeout. The drain mark is already committed. The tool
        must say so (pending mark, exit 3), never "nothing was recorded", and the mark and the refusal of new admissions are in the database."""
        ctx, valid, owner_id, root_id = self.live()
        executor, lease = self.hold_read(ctx, owner_id, root_id)
        reader_pid = self.pid(executor)
        publisher = self.conn("publisher", options="-c timezone=UTC -c statement_timeout=1000")
        tool = store.RealPublisher(publisher, self.s, lock_timeout_ms=4000)
        try:
            started = time.monotonic()
            result = tool.withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
            elapsed = time.monotonic() - started
            (mark,) = self.marks(ctx)                                                       # the mark is committed, as the database shows
            self.assertLess(elapsed, 3.5)                                                   # the statement timeout ended the wait, not the lock timeout
            self.assertEqual((result.status, result.outcome), (3, "NOT_YET_EFFECTIVE"), result.text)
            self.assertNotIn("nothing was recorded", result.text)
            self.assertNotIn("done", result.text.lower())
            self.assertIn("drain mark %d recorded at %s" % (mark["mark_id"], store.iso(mark["marked_at"])), result.text)
            self.assertIn("new admissions are refused with RW_WITHDRAWAL_PENDING", result.text)
            self.assertIn("the wait ended before the lock was granted (QueryCanceled): no generation was appended", result.text)
            self.assertIn("not yet effective for in-flight work; new admissions refused since %s" % store.iso(mark["marked_at"]), result.text)
            self.assertIn("blocking lease: backend %d, complete_by " % reader_pid, result.text)
            self.assertEqual(result.data["mark_id"], mark["mark_id"])
            self.assertEqual((len(self.history(ctx)), self.head(ctx)[0]), (1, 1))             # no generation
            self.refused_admission(PENDING, ctx, 1, owner_id, root_id)                        # and the mark does refuse new admissions
            self.assertIn("pending drain mark %d on context %s generation 1" % (mark["mark_id"], ctx), self.tool().status(ctx).text)
        finally:
            rollback(executor)
        again = self.tool().withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)               # the rerun continues from the same mark
        self.assertEqual((again.status, again.outcome), (0, "WITHDRAWN"), again.text)
        self.assertIn("drain mark %d already recorded" % mark["mark_id"], again.text)
        self.assertEqual(self.marks(ctx), [mark])

    def test_a_cancel_during_the_wait_is_also_not_yet_effective_and_a_lost_connection_is_unknown_with_the_mark_named(self):
        """M-3, the other ways step 2 can end after the mark committed: a cancel (pg_cancel_backend by the operator) is the not-yet-effective
        state; the backend being ended (pg_terminate_backend) is UNKNOWN for the generation, and says that the mark IS recorded."""
        for how in ("cancel", "terminate"):
            ctx, valid, owner_id, root_id = self.live()
            executor, lease = self.hold_read(ctx, owner_id, root_id)
            reader_pid = self.pid(executor)
            publisher = self.conn("publisher")
            publisher_pid = self.pid(publisher)
            worker = Worker(lambda p=publisher: store.RealPublisher(p, self.s, lock_timeout_ms=20000).withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER))
            try:
                wait_until(lambda: self.marks(ctx) and self.blockers(publisher_pid) == [reader_pid], timeout=5.0, what="step 2 to wait on the reader (%s)" % how)
                function = "pg_cancel_backend" if how == "cancel" else "pg_terminate_backend"
                self.assertTrue(self.admin.execute(f"SELECT {function}(%s)", (publisher_pid,)).fetchone()[0])
                result = worker.join(30)
            finally:
                rollback(executor)
            (mark,) = self.marks(ctx)
            self.assertNotIn("nothing was recorded", result.text, how)
            self.assertIn("drain mark %d" % mark["mark_id"], result.text, how)
            self.assertEqual(len(self.history(ctx)), 1, how)
            if how == "cancel":
                self.assertEqual((result.status, result.outcome), (3, "NOT_YET_EFFECTIVE"), result.text)
                self.assertIn("(QueryCanceled)", result.text)
            else:
                self.assertEqual((result.status, result.outcome), (4, "UNKNOWN"), result.text)
                self.assertIn("the drain mark %d is recorded; whether the generation was appended is not known" % mark["mark_id"], result.text)
            self.refused_admission(PENDING, ctx, 1, owner_id, root_id)

    def test_an_admission_queued_on_the_root_lock_is_refused_by_a_mark_committed_while_it_waited(self):
        """L-2 (technical review R1; design 2.1 'no admission begins after the mark commits'): B passes the pending-mark check, queues on the
        root lock behind A's lease, the drain mark commits while B waits, and A ends. B holds the lock then and checks the mark AGAIN: it is
        refused with the pending code and no lease row is written. Without the second check B would be admitted after the mark."""
        ctx, valid, owner_id, root_id = self.live()
        a, _lease = self.hold_read(ctx, owner_id, root_id)                         # A holds the root lock (and a head share lock)
        a_pid = self.pid(a)
        b = self.conn("executor", options="-c timezone=UTC -c lock_timeout=20000")  # a backstop: B can never wait for ever
        b_pid = self.pid(b)

        def attempt():
            begin(b)
            try:
                self.admit(b, ctx, 1, "ARCHIVE_READ", owner_id, root_id)
                commit(b)
                return "ADMITTED"
            except store.RealWorkspaceError as error:
                return error.code
            finally:
                rollback(b)
        worker = Worker(attempt)
        try:
            wait_until(lambda: self.blockers(b_pid) == [a_pid], timeout=5.0, what="B to queue on A's root lock")
            marked = self.conn("publisher").execute(f"SELECT * FROM {self.s}.rw_withdraw_mark(%s,1,%s,'PD-9002',%s,%s)",
                                                    (ctx, fx.ACTOR, "c" * 40, "d" * 64)).fetchall()
            self.assertEqual(len(marked), 1)
            self.assertFalse(worker.done)                                              # still queued: the mark did not move it
        finally:
            rollback(a)                                                             # A ends; B takes the root lock
        self.assertEqual(worker.join(30), PENDING)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 0)         # neither lease row survives (A rolled back, B refused)

    def test_two_concurrent_withdrawals_record_one_mark_and_the_second_says_whose_it_is(self):
        """L-4 (technical review R1): the second withdrawal of a generation waits for the first mark's transaction, creates nothing, and its
        output does not claim to have recorded its own: it says 'already recorded' and names the other issuer and reference. The
        generation it then appends carries the FIRST mark's issuer and reference."""
        ctx, valid, owner_id, root_id = self.live()
        first = self.conn("publisher")
        first_pid = self.pid(first)
        second = self.conn("publisher")
        second_pid = self.pid(second)
        begin(first)
        try:
            (mark_row,) = first.execute(f"SELECT * FROM {self.s}.rw_withdraw_mark(%s,1,'first-issuer','PD-9001',%s,%s)", (ctx, "a" * 40, "b" * 64)).fetchall()
            worker = Worker(lambda: store.RealPublisher(second, self.s, lock_timeout_ms=20000).withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER))
            wait_until(lambda: self.blockers(second_pid) == [first_pid], timeout=5.0, what="the second mark to wait on the first")
            self.assertFalse(worker.done)
            commit(first)
        finally:
            rollback(first)
        result = worker.join(30)
        (mark,) = self.marks(ctx)
        self.assertEqual((mark["mark_id"], mark["issuer_actor"], mark["pd_id"]), (mark_row[0], "first-issuer", "PD-9001"))
        self.assertEqual((result.status, result.outcome), (0, "WITHDRAWN"), result.text)
        self.assertIn("drain mark %d already recorded" % mark["mark_id"], result.text)
        self.assertNotIn("drain mark %d recorded at" % mark["mark_id"], result.text)
        self.assertIn("that mark was recorded by first-issuer under PD-9001; this command's actor and reference were not recorded", result.text)
        first_generation, second_generation = self.history(ctx)
        self.assertEqual((second_generation["drain_mark_id"], second_generation["issuer_actor"], second_generation["pd_id"]),
                         (mark["mark_id"], "first-issuer", "PD-9001"))

    def test_the_mark_record_cannot_be_made_without_its_issuer_reference_or_time(self):
        """R1: a mark without an issuer, without any one part of the triple, or with a malformed hash is refused (function and table)."""
        ctx, valid, owner_id, root_id = self.live()
        publisher = self.conn("publisher")
        good = ("invented-owner", "PD-9002", "c" * 40, "d" * 64)
        bad = {"no issuer": (None,) + good[1:], "empty issuer": ("",) + good[1:], "no PD": (good[0], None) + good[2:], "bad PD": (good[0], "PD-2") + good[2:],
               "no commit": good[:2] + (None, good[3]), "short commit": good[:2] + ("c" * 39, good[3]), "no hash": good[:3] + (None,),
               "upper-case hash": good[:3] + ("D" * 64,), "short hash": good[:3] + ("d" * 63,)}
        for label, values in bad.items():
            self.assertRefused("RW_DECISION_REF_REQUIRED", lambda v=values: publisher.execute(
                f"SELECT * FROM {self.s}.rw_withdraw_mark(%s,1,%s,%s,%s,%s)", (ctx, *v)))
            with self.assertRaises(psycopg.errors.IntegrityError, msg=label):                                  # E11 crafted INSERT by the owner role
                self.owner.execute(f"INSERT INTO {self.s}.rw_drain_mark(context_id,generation,issuer_actor,pd_id,git_commit,doc_sha256,marked_at) "
                                   "VALUES(%s,1,%s,%s,%s,%s,clock_timestamp())", (ctx, *values))
        with self.assertRaises(psycopg.errors.NotNullViolation):
            self.owner.execute(f"INSERT INTO {self.s}.rw_drain_mark(context_id,generation,issuer_actor,pd_id,git_commit,doc_sha256,marked_at) "
                               "VALUES(%s,1,%s,%s,%s,%s,NULL)", (ctx, *good))
        self.assertEqual(self.marks(ctx), [])

    def test_a_renewal_while_a_mark_is_pending_must_name_it_and_naming_it_supersedes_it(self):
        ctx, valid, owner_id, root_id = self.live()
        executor, lease = self.hold_read(ctx, owner_id, root_id)
        try:
            timed_out = self.tool(lock_timeout_ms=1000).withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
            self.assertEqual(timed_out.status, 3, timed_out.text)
        finally:
            rollback(executor)
        (mark,) = self.marks(ctx)
        plain = self.renew(ctx, 1, valid_until=valid)
        self.assertEqual((plain.status, plain.data["code"], plain.data["detail"]), (2, PENDING, "RENEWAL_MUST_NAME_MARK"))
        wrong = self.renew(ctx, 1, valid_until=valid, names_mark=mark["mark_id"] + 1000)
        self.assertEqual((wrong.status, wrong.data["code"]), (2, PENDING))
        self.assertEqual(len(self.history(ctx)), 1)
        named = self.renew(ctx, 1, valid_until=valid, names_mark=mark["mark_id"])
        self.assertEqual((named.status, named.data["superseded_mark"]), (0, mark["mark_id"]), named.text)
        self.assertIn("drain mark %d is superseded by this renewal and stays readable" % mark["mark_id"], named.text)
        first, second = self.history(ctx)
        self.assertEqual((second["generation"], second["drain_mark_id"], second["rights"]), (2, mark["mark_id"], fx.ALL_RIGHTS))
        self.assertEqual(self.marks(ctx), [mark])                                       # superseded, and still readable
        self.assertNotIn("pending drain mark", self.tool().status(ctx).text)
        self.admit_and_commit(self.conn("executor"), ctx, 2, "ARCHIVE_READ", owner_id, root_id)
        stale = self.tool().withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)      # re-running the old withdrawal finds the superseded mark
        self.assertEqual((stale.status, stale.data["code"]), (2, "RW_MARK_STALE"), stale.text)
        self.assertNotIn("done", stale.text.lower())
        other, _v, _r = self.publish(valid_in=300.0)
        nothing_pending = self.renew(other.context_id, 1, valid_until=valid, names_mark=1)
        self.assertEqual((nothing_pending.status, nothing_pending.data["code"]), (2, "RW_MARK_STALE"))

    def test_overlapping_admissions_stop_while_a_withdrawal_runs(self):
        """R1: two connections admit read operations in an overlapping loop while a withdrawal runs. New admissions stop (the pending code,
        then the generation moves on), and the withdrawal completes or reports 'not yet effective'. This is the check on the starvation
        reading (section 9: a new share locker may overtake a waiting exclusive locker).

        What it does and does not show. Observed on PostgreSQL 17.11 in five runs: the withdrawal ended WITHDRAWN every time, about 1,000
        admissions per loop passed in the second, and a loop saw the pending code in each run. It is a soak check: it also passes with the
        pending-mark refusal removed from the admit function (checked by hand: the generation change alone stops the loops), so it does
        NOT show that the mark stops admissions. The first test of this class does (a reader holds a share lock and the mark alone
        refuses a new admission), and the characterisation test below shows that the overtaking the mark guards against is real."""
        ctx, valid, owner_id, root_id = self.live()
        roots = [self.craft_root(ctx) for _ in range(2)]
        stop = threading.Event()

        def loop(conn, owner_id, root_id):
            admitted, refusals = 0, []
            while not stop.is_set():
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
        workers = [Worker(lambda c=self.conn("executor"), o=o, r=r: loop(c, o, r)) for o, r in roots]
        try:
            time.sleep(0.5)                                                           # admissions are flowing
            result = self.tool(lock_timeout_ms=10000).withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
            time.sleep(0.5)
        finally:
            stop.set()
        results = [w.join(30) for w in workers]
        self.assertIn(result.outcome, ("WITHDRAWN", "NOT_YET_EFFECTIVE"), result.text)
        self.assertIn(result.status, (0, 3))
        for admitted, refusals in results:
            self.assertGreater(admitted, 0)
            self.assertGreater(len(refusals), 0)                                      # admissions stopped
            self.assertLessEqual(set(refusals), {PENDING, "RW_GENERATION_DIFFERS"})
        (mark,) = self.marks(ctx)
        if result.outcome == "WITHDRAWN":
            self.assertEqual([h["drain_mark_id"] for h in self.history(ctx)], [None, mark["mark_id"]])
        else:
            self.assertEqual(len(self.history(ctx)), 1)

    def test_characterisation_a_new_share_locker_overtakes_a_waiting_for_update_locker_on_the_same_row(self):
        """CHARACTERISATION of the server (design section 9, "not run" until now): E11 crafted probe on the head row as the owner role, raw
        SQL, not product evidence. A holds FOR SHARE; B asks FOR UPDATE and waits (the server names A as its blocker); C then asks FOR SHARE.
        The recorded behaviour is that C is granted at once although B is queued, which is the starvation reading of section 9: overlapping
        readers could hold a withdrawal off for as long as they overlap. The design does not depend on it, because the drain mark stops
        new admissions first. THAT is shown by `test_withdrawal_during_an_in_flight_read_marks_first_waits_then_applies` (a reader holds a
        share lock and the mark alone refuses a new admission), NOT by the overlap soak above, which also passes without the mark (L-7,
        technical review R1); this test only fixes the reading of the server."""
        ctx, valid, owner_id, root_id = self.live()
        a, b, c = self.conn("owner"), self.conn("owner"), self.conn("owner")
        pid_a, pid_b, pid_c = self.pid(a), self.pid(b), self.pid(c)
        row = f"SELECT 1 FROM {self.s}.rw_head WHERE context_id=%s"
        begin(a)
        a.execute(row + " FOR SHARE", (ctx,))
        begin(b)
        b.execute("SET LOCAL lock_timeout = '30s'")                     # a backstop: B can never wait for ever, whatever fails below
        waiter = Worker(lambda: b.execute(row + " FOR UPDATE", (ctx,)).fetchall())
        try:
            wait_until(lambda: self.blockers(pid_b) == [pid_a], timeout=3.0, what="B's FOR UPDATE to wait on A")
            begin(c)
            c.execute("SET LOCAL lock_timeout = '2s'")                  # if C queued behind B this would raise LockNotAvailable
            self.assertEqual(c.execute(row + " FOR SHARE", (ctx,)).fetchall(), [(1,)])
            self.assertFalse(waiter.done)                              # B is still waiting, now behind both share lockers
            rollback(a)
            time.sleep(0.3)
            self.assertFalse(waiter.done)                              # C alone keeps B out, although the first holder is gone
            self.assertEqual(self.blockers(pid_b), [pid_c])
            rollback(c)
            self.assertEqual(waiter.join(10), [(1,)])                  # and B is granted once the last share locker ends
            commit(b)
        finally:
            # Release the lock holders first (the main thread owns A and C), then make sure B's waiting thread is over before B's own
            # connection is touched: a connection is locked by the statement that is running on it, so rollback(b) would wait for ever.
            rollback(a)
            rollback(c)
            if not waiter.done:
                b.cancel()
                waiter.thread.join(10)
            rollback(b)

    def test_a_stalled_worker_past_its_deadline_is_named_and_only_the_trusted_operator_can_end_it(self):
        """R1 (read lease): the withdrawal names the blocking lease and its complete_by; the publisher role cannot terminate the backend;
        after the operator (the superuser here) ends it, the withdrawal proceeds and no lease row leaks."""
        ctx, valid, owner_id, root_id = self.live()
        executor, lease = self.hold_read(ctx, owner_id, root_id, options=self.stall_options())
        stalled_pid = self.pid(executor)
        self.wait_for_db_time(lease.complete_by)                       # stalled past its deadline: it can no longer commit
        result = self.tool(lock_timeout_ms=1000).withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual((result.status, result.outcome), (3, "NOT_YET_EFFECTIVE"), result.text)
        self.assertIn("blocking lease: backend %d, complete_by " % stalled_pid, result.text)
        publisher = self.conn("publisher")
        self.assertDenied(lambda: publisher.execute("SELECT pg_terminate_backend(%s)", (stalled_pid,)))
        self.assertDenied(lambda: publisher.execute("SELECT pg_cancel_backend(%s)", (stalled_pid,)))
        self.assertTrue(self.admin.execute("SELECT pg_terminate_backend(%s)", (stalled_pid,)).fetchone()[0])
        wait_until(lambda: self.admin.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s", (stalled_pid,)).fetchone()[0] == 0,
                   timeout=5.0, what="the stalled backend to end")
        finished = self.tool(lock_timeout_ms=5000).withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual((finished.status, finished.outcome), (0, "WITHDRAWN"), finished.text)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (ctx,)), 0)             # no leaked lease row

    def test_an_operation_over_its_statement_timeout_or_cancelled_rolls_back_wholly_and_then_withdrawal_proceeds(self):
        """R1: statement timeout and cancellation (read lease). The transaction rolls back wholly, its locks are released, no lease row
        remains, and the withdrawal is not held up."""
        ctx, valid, owner_id, root_id = self.live()
        op = uuid.uuid4()
        timed = self.conn("executor", options="-c timezone=UTC -c statement_timeout=500 -c lock_timeout=8000")
        begin(timed)
        try:
            self.admit(timed, ctx, 1, "ARCHIVE_READ", owner_id, root_id, op=op)
            with self.assertRaises(psycopg.errors.QueryCanceled):
                timed.execute("SELECT pg_sleep(5)")
        finally:
            rollback(timed)
        self.assertEqual(self.count("rw_lease", "operation_id=%s", (op,)), 0)
        cancelled_op = uuid.uuid4()
        victim = self.conn("executor", options=self.stall_options())
        victim_pid = self.pid(victim)
        begin(victim)
        self.admit(victim, ctx, 1, "ARCHIVE_READ", owner_id, root_id, op=cancelled_op)

        def sleeper():
            try:
                victim.execute("SELECT pg_sleep(30)")
            except psycopg.errors.QueryCanceled as error:
                return type(error).__name__
        worker = Worker(sleeper)
        wait_until(lambda: self.admin.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s AND state='active' AND query LIKE '%%pg_sleep%%'",
                                              (victim_pid,)).fetchone()[0] == 1, timeout=5.0, what="the victim to be sleeping")
        self.assertTrue(self.admin.execute("SELECT pg_cancel_backend(%s)", (victim_pid,)).fetchone()[0])
        self.assertEqual(worker.join(10), "QueryCanceled")
        rollback(victim)
        self.assertEqual(self.count("rw_lease", "operation_id=%s", (cancelled_op,)), 0)
        started = time.monotonic()
        result = self.tool(lock_timeout_ms=5000).withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual((result.status, result.outcome), (0, "WITHDRAWN"), result.text)
        self.assertLess(time.monotonic() - started, 4.0)                                  # nothing held it up

    def test_a_lost_acknowledgement_of_the_generation_is_unknown_and_the_rerun_reconciles(self):
        """Reduced FF1-C12 for the withdrawal: the generation commits, the acknowledgement is lost. UNKNOWN and no retry; the rerun finds the
        committed generation and reports it as already effective."""
        class LoseTheSecondAcknowledgement(store.RealPublisher):
            commits = 0

            def _after_commit(self):
                type(self).commits += 1
                if type(self).commits == 2:
                    raise psycopg.OperationalError("the acknowledgement was lost")
        ctx, valid, owner_id, root_id = self.live()
        lost = LoseTheSecondAcknowledgement(self.conn("publisher"), self.s).withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual((lost.status, lost.outcome), (4, "UNKNOWN"), lost.text)
        self.assertNotIn("done:", lost.text)
        self.assertEqual(len(self.history(ctx)), 2)                                      # committed
        rerun = self.tool().withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual(rerun.status, 0, rerun.text)
        self.assertIn("done (already effective)", rerun.text)
        self.assertEqual(len(self.history(ctx)), 2)
        self.assertEqual(len(self.marks(ctx)), 1)

    def test_the_withdrawal_needs_a_reference_and_the_executor_cannot_withdraw(self):
        ctx, valid, owner_id, root_id = self.live()
        refused = self.tool().withdraw(ctx, 1, actor=fx.ACTOR, ref=None)
        self.assertEqual((refused.status, refused.data["code"]), (2, "RW_DECISION_REF_REQUIRED"))
        for who in ("executor", "loader"):
            conn = self.conn(who)
            self.assertDenied(lambda c=conn: c.execute(f"SELECT * FROM {self.s}.rw_withdraw_mark(%s,1,'a','PD-9002',%s,%s)", (ctx, "c" * 40, "d" * 64)))
            self.assertDenied(lambda c=conn: c.execute(f"SELECT * FROM {self.s}.rw_withdraw_apply(%s,1)", (ctx,)))
        self.assertEqual((self.marks(ctx), len(self.history(ctx))), ([], 1))


if __name__ == "__main__":
    import unittest
    unittest.main()
