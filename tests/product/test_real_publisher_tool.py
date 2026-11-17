"""F1 R1: the publisher tool's exit statuses, wording and refusals (design 3.2, 2.5), on a scripted connection.

Pure tests: no database. They show what the TOOL does with each answer the database can give; what the database answers is shown by
`test_postgres_real_gateway_*.py`, which run the same commands against a disposable TEST install.
"""
from __future__ import annotations

import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

import psycopg
from psycopg.pq import TransactionStatus

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

import real_gateway_fixtures as fx  # noqa: E402
from persistence import real_proposal as rp  # noqa: E402
from persistence import real_workspace_store as store  # noqa: E402
from persistence.real_scope import resolve_scope  # noqa: E402
from persistence.real_workspace_context import RealWorkspaceError  # noqa: E402
from persistence.real_workspace_store import (BasisEntry, DecisionRef, RealPublisher, EXIT_DONE, EXIT_LOCK_TIMEOUT,  # noqa: E402
                                              EXIT_NOT_YET_EFFECTIVE, EXIT_REFUSED, EXIT_UNKNOWN)

CTX = "c" * 64
NOW = dt.datetime(2026, 10, 25, 12, 0, 0, 250000, tzinfo=dt.timezone.utc)
LATER = NOW + dt.timedelta(seconds=90)


class _Diag:
    def __init__(self, primary, detail):
        self.message_primary, self.message_detail = primary, detail


class GatewayRefusal(psycopg.errors.RaiseException):
    """A RAISE EXCEPTION from a gateway function, with the DETAIL line the server would send."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self._d = _Diag(code, detail)

    @property
    def diag(self):
        return self._d


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class _Transaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.transactions += 1
        self.conn.status = TransactionStatus.INTRANS
        return self

    def __exit__(self, exc_type, exc, tb):
        self.conn.status = TransactionStatus.IDLE
        if exc_type is None:
            error = self.conn.commit_errors.get(self.conn.transactions, self.conn.commit_error)
            if error is not None:
                self.conn.status = self.conn.status_after_commit_error
                raise error
        return False


class FakeConnection:
    """A scripted psycopg connection: answers `SELECT * FROM "schema"."fn"(...)` by function name, records every statement with the
    number of the transaction it ran in, and can fail the COMMIT."""

    def __init__(self, **answers):
        self.answers, self.log, self.transactions = dict(answers), [], 0
        self.status, self.commit_error, self.closed = TransactionStatus.IDLE, None, False
        self.commit_errors = {}                                  # transaction number -> the error its COMMIT raises
        self.status_after_commit_error = TransactionStatus.IDLE   # where the connection is when the COMMIT's error arrives

    @property
    def info(self):
        return types.SimpleNamespace(transaction_status=self.status)

    def transaction(self):
        return _Transaction(self)

    def close(self):
        self.closed = True

    def calls(self, name):
        return [entry for entry in self.log if '"%s"' % name in entry[1]]

    def execute(self, query, params=()):
        text = query.as_string()
        self.log.append((self.transactions, text, params))
        if text.startswith("SET LOCAL"):
            return _Cursor([])
        for name, answer in self.answers.items():
            if '"%s"' % name in text or ("." + name) in text:
                if isinstance(answer, BaseException):
                    raise answer
                if callable(answer):
                    return _Cursor(answer(text, params))
                return _Cursor(answer)
        raise AssertionError("unscripted statement: " + text)


def _tool(conn, **kw):
    return RealPublisher(conn, "rw_t", **kw)


def _proposal(tag="tool"):
    return rp.write_proposal(resolve_scope("SYNTHETIC_TEST"), **fx.content(tag))


class PublishTests(unittest.TestCase):
    def publish(self, conn, **overrides):
        args = dict(rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=fx.hg4_shape(fx.FAR), actor=fx.ACTOR, ref=fx.REF)
        args.update(overrides)
        return _tool(conn).publish(_proposal(), **args)

    def test_published_prints_the_upper_bound_wording_and_never_within(self):
        conn = FakeConnection(rw_publish=[(CTX, 1, True)])
        result = self.publish(conn)
        self.assertEqual((result.status, result.outcome), (EXIT_DONE, "PUBLISHED"))
        self.assertIn(store.PLAUSIBILITY_WORDING, result.text)
        self.assertIn("upper bound", result.text)
        self.assertNotIn("within", result.text.lower())
        self.assertNotIn("margin", result.text.lower())
        self.assertEqual(result.data, {"context_id": CTX, "generation": 1, "created": True})
        (_tx, text, params), = conn.calls("rw_publish")
        self.assertEqual(len(params), 8)
        self.assertEqual(params[4:], (fx.ACTOR, "PD-9001", "a" * 40, "b" * 64))
        self.assertEqual(params[0], rp.verify_proposal(_proposal()).snapshot.data)    # the verified bytes, not any file

    def test_a_rerun_of_identical_input_reports_the_original_and_exits_zero(self):
        result = self.publish(FakeConnection(rw_publish=[(CTX, 1, False)]))
        self.assertEqual((result.status, result.outcome), (EXIT_DONE, "ALREADY_PUBLISHED"))
        self.assertIn("already published", result.text)

    def test_the_statements_run_in_one_transaction_with_the_tools_lock_timeout(self):
        conn = FakeConnection(rw_publish=[(CTX, 1, True)])
        self.publish(conn)
        self.assertEqual({tx for tx, _t, _p in conn.log}, {1})
        self.assertEqual([t for _tx, t, _p in conn.log][0], "SET LOCAL lock_timeout = '10000ms'")

    def test_no_decision_reference_or_actor_reaches_the_database(self):
        for name, override in (("no reference", dict(ref=None)), ("reference as a tuple", dict(ref=("PD-1", "a" * 40, "b" * 64))),
                               ("empty actor", dict(actor="")), ("no actor", dict(actor=None))):
            conn = FakeConnection()
            result = self.publish(conn, **override)
            self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, "RW_DECISION_REF_REQUIRED"), name)
            self.assertEqual(conn.log, [], name)
            self.assertIn("nothing was recorded", result.text)

    def test_every_part_of_the_reference_is_required_and_checked_in_form(self):
        good = ("PD-9001", "a" * 40, "b" * 64)
        DecisionRef(*good)
        for bad in (("", good[1], good[2]), ("PD-1", good[1], good[2]), ("pd-9001", good[1], good[2]), (good[0], "a" * 39, good[2]),
                    (good[0], "A" * 40, good[2]), (good[0], good[1], "b" * 63), (good[0], good[1], "B" * 64), (None, good[1], good[2]),
                    (good[0], None, good[2]), (good[0], good[1], None)):
            with self.assertRaises(RealWorkspaceError, msg=repr(bad)) as caught:
                DecisionRef(*bad)
            self.assertEqual(caught.exception.code, "RW_DECISION_REF_REQUIRED")

    def test_an_edited_or_junk_proposal_is_refused_before_any_statement(self):
        for name, data in (("bytes edited", _proposal().replace(b"syn.alpha", b"syn.alphA")), ("junk", b"not json"), ("text", "x")):
            conn = FakeConnection()
            result = _tool(conn).publish(data, rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=fx.hg4_shape(fx.FAR), actor=fx.ACTOR, ref=fx.REF)
            self.assertEqual(result.status, EXIT_REFUSED, name)
            self.assertTrue(result.data["code"].startswith("RW_PROPOSAL_"), name)
            self.assertEqual(conn.log, [], name)

    def test_malformed_rights_evidence_and_time_are_refused_in_the_tool(self):
        for name, override in (("rights missing a key", dict(rights={"ARCHIVE_READ": True})), ("rights not bool", dict(rights={**fx.ALL_RIGHTS, "ARCHIVE_READ": 1})),
                               ("naive valid_until", dict(valid_until=dt.datetime(2030, 1, 1))), ("string valid_until", dict(valid_until="2030-01-01")),
                               ("evidence not entries", dict(evidence=[{"source_id": "syn.alpha"}])),
                               ("bound with microseconds", dict(evidence=fx.hg4_shape(dt.datetime(2099, 1, 1, 0, 0, 0, 5, tzinfo=dt.timezone.utc))))):
            conn = FakeConnection()
            result = self.publish(conn, **override)
            self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, "RW_SHAPE"), name)
            self.assertEqual(conn.log, [], name)

    def test_a_gateway_refusal_reports_its_code_and_reasons_and_exits_two(self):
        refusal = GatewayRefusal("RW_PUBLISH_REFUSED", "RW_INSTALL_KIND,RW_O1_SYNTHETIC_SOURCE")
        result = self.publish(FakeConnection(rw_publish=refusal))
        self.assertEqual(result.status, EXIT_REFUSED)
        self.assertEqual(result.data["code"], "RW_PUBLISH_REFUSED")
        self.assertEqual(result.data["codes"], ("RW_PUBLISH_REFUSED", "RW_INSTALL_KIND", "RW_O1_SYNTHETIC_SOURCE"))
        self.assertIn("nothing was recorded", result.text)
        result = self.publish(FakeConnection(rw_publish=GatewayRefusal("RW_EXPIRY_UNSUPPORTED", "NON_MEMBER_ENTRY")))
        self.assertEqual((result.data["code"], result.data["detail"]), ("RW_EXPIRY_UNSUPPORTED", "NON_MEMBER_ENTRY"))

    def test_a_database_error_that_is_not_a_gateway_code_is_reported_by_its_class_and_never_raised(self):
        # Before the commit point, on a usable IDLE connection, the transaction was rolled back: a definite refusal with the
        # exception's class name as its reason (technical review R1, L-3: no traceback, one of the tool's own statuses).
        for error in (psycopg.errors.InsufficientPrivilege("permission denied"), psycopg.errors.ForeignKeyViolation("fk"),
                      psycopg.errors.DatabaseError("generic")):
            result = self.publish(FakeConnection(rw_publish=error))
            self.assertEqual((result.status, result.data["code"], result.data["detail"]), (EXIT_REFUSED, "RW_STATEMENT_FAILED", type(error).__name__))
            self.assertIn("nothing was recorded", result.text)

    def test_publish_times_out_on_a_lock_without_recording(self):
        result = self.publish(FakeConnection(rw_publish=psycopg.errors.LockNotAvailable("lock")))
        self.assertEqual((result.status, result.outcome), (EXIT_LOCK_TIMEOUT, "LOCK_TIMEOUT"))


class CommitOutcomeTests(unittest.TestCase):
    """A lost connection is UNKNOWN (F2's rule): the identical command reconciles, nothing is retried."""

    def call(self, conn, tool=None):
        return (tool or _tool(conn)).publish(_proposal(), rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=fx.hg4_shape(fx.FAR),
                                             actor=fx.ACTOR, ref=fx.REF)

    def test_a_failed_commit_is_unknown_and_exits_four(self):
        for error in (psycopg.OperationalError("server closed the connection"), psycopg.InterfaceError("connection is closed")):
            conn = FakeConnection(rw_publish=[(CTX, 1, True)])
            conn.commit_error = error
            result = self.call(conn)
            self.assertEqual((result.status, result.outcome), (EXIT_UNKNOWN, "UNKNOWN"), repr(error))
            self.assertIn("not known", result.text)
            self.assertIn("re-run the identical command", result.text)
            self.assertNotIn("published context", result.text)
            self.assertEqual(len(conn.calls("rw_publish")), 1)     # no retry

    def test_acknowledgement_loss_after_the_commit_is_unknown(self):
        class LostAck(RealPublisher):
            def _after_commit(self):
                raise psycopg.OperationalError("the acknowledgement was lost")
        conn = FakeConnection(rw_publish=[(CTX, 1, True)])
        result = self.call(conn, LostAck(conn, "rw_t"))
        self.assertEqual(result.status, EXIT_UNKNOWN)
        self.assertEqual(len(conn.calls("rw_publish")), 1)

    def test_a_connection_that_breaks_inside_the_statement_is_unknown(self):
        conn = FakeConnection(rw_publish=psycopg.OperationalError("terminating connection"))
        conn.closed = True
        self.assertEqual(self.call(conn).status, EXIT_UNKNOWN)

    def test_a_deadlock_before_the_commit_on_a_usable_connection_is_a_definite_rollback(self):
        conn = FakeConnection(rw_publish=psycopg.errors.DeadlockDetected("deadlock"))
        result = self.call(conn)
        self.assertEqual((result.status, result.data["code"], result.data["detail"]), (EXIT_REFUSED, "RW_STATEMENT_FAILED", "DeadlockDetected"))
        self.assertIn("nothing was recorded", result.text)

    def test_a_post_commit_check_failure_is_never_reported_as_nothing_recorded(self):
        class Dirty(RealPublisher):
            def _after_commit(self):
                raise RealWorkspaceError("RW_OUTER_TRANSACTION_REQUIRED")
        conn = FakeConnection(rw_publish=[(CTX, 1, True)])
        self.assertEqual(self.call(conn, Dirty(conn, "rw_t")).status, EXIT_UNKNOWN)

    # ---- the E4 rule the PM chose (technical review R1, item 3, L-3): at or after the commit point ONLY a gateway code on a
    # ---- connection back at IDLE is a definite refusal; every other error is UNKNOWN, tells the owner to look, and is not retried.
    def assertUnknownAndNeverNothingRecorded(self, result, conn, label):
        self.assertEqual((result.status, result.outcome), (EXIT_UNKNOWN, "UNKNOWN"), label)
        self.assertNotIn("nothing was recorded", result.text, label)
        self.assertNotIn("recorded nothing", result.text, label)
        self.assertIn("not known", result.text, label)
        self.assertIn("status view", result.text, label)
        self.assertIn("re-run the identical command", result.text, label)
        self.assertEqual(len(conn.calls("rw_publish")), 1, label)                       # no retry

    def test_every_error_at_the_commit_that_is_not_a_gateway_code_is_unknown(self):
        errors = {"lock timeout": psycopg.errors.LockNotAvailable("lock"), "deadlock": psycopg.errors.DeadlockDetected("deadlock"),
                  "cancel": psycopg.errors.QueryCanceled("cancelled"), "foreign key": psycopg.errors.ForeignKeyViolation("fk"),
                  "check": psycopg.errors.CheckViolation("check"), "generic database error": psycopg.errors.DatabaseError("generic"),
                  "a raise that is not a gateway code": psycopg.errors.RaiseException("something else")}
        for label, error in errors.items():
            conn = FakeConnection(rw_publish=[(CTX, 1, True)])
            conn.commit_error = error
            self.assertUnknownAndNeverNothingRecorded(self.call(conn), conn, label)

    def test_a_gateway_code_at_the_commit_on_an_idle_connection_is_the_one_definite_refusal(self):
        # The deadline guard's RW_DEADLINE comes back as an error reply to COMMIT; the transaction is gone (design 3.1, T-b).
        conn = FakeConnection(rw_publish=[(CTX, 1, True)])
        conn.commit_error = GatewayRefusal("RW_DEADLINE")
        result = self.call(conn)
        self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, "RW_DEADLINE"))
        self.assertIn("nothing was recorded", result.text)
        # The same code on a connection that is not back at IDLE is not a definite answer.
        for status in (TransactionStatus.INTRANS, TransactionStatus.INERROR, TransactionStatus.UNKNOWN):
            conn = FakeConnection(rw_publish=[(CTX, 1, True)])
            conn.commit_error = GatewayRefusal("RW_DEADLINE")
            conn.status_after_commit_error = status
            self.assertUnknownAndNeverNothingRecorded(self.call(conn), conn, repr(status))
        conn = FakeConnection(rw_publish=[(CTX, 1, True)])
        conn.commit_error = GatewayRefusal("RW_DEADLINE")
        conn.closed = True
        self.assertUnknownAndNeverNothingRecorded(self.call(conn), conn, "closed")

    def test_before_the_commit_point_the_same_errors_are_definite_rollbacks_on_a_usable_connection(self):
        result = self.call(FakeConnection(rw_publish=psycopg.errors.LockNotAvailable("lock")))
        self.assertEqual((result.status, result.outcome), (EXIT_LOCK_TIMEOUT, "LOCK_TIMEOUT"))
        self.assertIn("recorded nothing", result.text)
        for label, error in (("deadlock", psycopg.errors.DeadlockDetected("d")), ("cancel", psycopg.errors.QueryCanceled("c")),
                             ("integrity", psycopg.errors.IntegrityError("i"))):
            result = self.call(FakeConnection(rw_publish=error))
            self.assertEqual((result.status, result.data["code"], result.data["detail"]), (EXIT_REFUSED, "RW_STATEMENT_FAILED", type(error).__name__), label)
            self.assertIn("nothing was recorded", result.text, label)

        # On a connection that is not usable (not back at IDLE after the error) the rollback is not known: UNKNOWN.
        class StuckTransaction(_Transaction):
            def __exit__(self, exc_type, exc, tb):
                self.conn.status = TransactionStatus.INERROR
                return False
        conn = FakeConnection(rw_publish=psycopg.errors.QueryCanceled("c"))
        conn.transaction = lambda: StuckTransaction(conn)
        self.assertUnknownAndNeverNothingRecorded(self.call(conn), conn, "not back at IDLE")


class RenewTests(unittest.TestCase):
    def renew(self, conn, **overrides):
        args = dict(rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=fx.hg4_shape(fx.FAR), actor=fx.ACTOR, ref=fx.REF_OTHER)
        args.update(overrides)
        return _tool(conn).renew(CTX, 1, **args)

    def test_a_renewal_that_moves_the_date_earlier_says_so(self):
        old, new = LATER + dt.timedelta(days=10), LATER
        result = self.renew(FakeConnection(rw_renew=[(2, old, new, True, None)]))
        self.assertEqual((result.status, result.outcome), (EXIT_DONE, "RENEWED"))
        self.assertIn("`valid_until` moved earlier: %s to %s" % (store.iso(old), store.iso(new)), result.text)
        self.assertTrue(result.data["moved_earlier"])

    def test_a_later_or_equal_date_is_not_called_a_correction(self):
        for old, new in ((LATER, LATER + dt.timedelta(days=1)), (LATER, LATER)):
            result = self.renew(FakeConnection(rw_renew=[(2, old, new, False, None)]))
            self.assertNotIn("moved earlier", result.text)
            self.assertIn("valid_until %s (was %s)" % (store.iso(new), store.iso(old)), result.text)

    def test_no_renew_output_ever_says_within_or_margin(self):
        # L-6 (technical review R1): the plausibility rule's wording is an UPPER bound everywhere. Every renew output is covered: with
        # and without a recorded bound, a later, equal and earlier date, a superseded mark, and the lock timeout and refusal texts.
        bound = fx.hg4_shape(fx.FAR)
        cases = [FakeConnection(rw_renew=[(2, LATER, LATER + dt.timedelta(days=1), False, None)]),
                 FakeConnection(rw_renew=[(2, LATER, LATER, False, None)]),
                 FakeConnection(rw_renew=[(2, LATER + dt.timedelta(days=10), LATER, True, None)]),
                 FakeConnection(rw_renew=[(3, LATER, LATER, False, 7)]),
                 FakeConnection(rw_renew=psycopg.errors.LockNotAvailable("timeout"), rw_in_flight=[(4321, LATER)]),
                 FakeConnection(rw_renew=GatewayRefusal("RW_EXPIRY_UNSUPPORTED", "PLAUSIBILITY"))]
        for conn in cases:
            for evidence in (bound, []):
                result = self.renew(conn, evidence=evidence)
                text = result.text.lower()
                self.assertNotIn("within", text, result.text)
                self.assertNotIn("margin", text, result.text)
        done = self.renew(FakeConnection(rw_renew=[(2, LATER, LATER, False, None)]), evidence=bound)
        self.assertIn(store.PLAUSIBILITY_WORDING, done.text)                    # the one allowed wording is present, and it is the upper bound
        self.assertIn("upper bound", done.text)

    def test_naming_a_mark_reports_the_supersession(self):
        result = self.renew(FakeConnection(rw_renew=[(3, LATER, LATER, False, 7)]), names_mark=7)
        self.assertIn("drain mark 7 is superseded by this renewal and stays readable", result.text)

    def test_the_call_carries_the_reference_the_entries_and_the_expected_generation(self):
        conn = FakeConnection(rw_renew=[(2, LATER, LATER, False, None)])
        self.renew(conn)
        (_tx, _text, params), = conn.calls("rw_renew")
        self.assertEqual((params[0], params[1], params[5], params[6:9], params[9]), (CTX, 1, fx.ACTOR, ("PD-9002", "c" * 40, "d" * 64), None))
        self.assertEqual(params[4].obj, sorted(params[4].obj, key=lambda e: e["source_id"]))

    def test_refusals_without_a_statement(self):
        for name, override, code in (("no reference", dict(ref=None), "RW_DECISION_REF_REQUIRED"), ("no actor", dict(actor=""), "RW_DECISION_REF_REQUIRED"),
                                     ("bad mark", dict(names_mark=0), "RW_SHAPE"), ("bad rights", dict(rights={}), "RW_SHAPE")):
            conn = FakeConnection()
            result = self.renew(conn, **override)
            self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, code), name)
            self.assertEqual(conn.log, [], name)
        conn = FakeConnection()
        self.assertEqual(_tool(conn).renew("xyz", 1, rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=[], actor="a", ref=fx.REF).status, EXIT_REFUSED)
        self.assertEqual(_tool(conn).renew(CTX, 0, rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=[], actor="a", ref=fx.REF).status, EXIT_REFUSED)
        self.assertEqual(conn.log, [])

    def test_gateway_refusals_are_reported_with_their_codes(self):
        for code, detail in (("RW_VALID_UNTIL_PAST", None), ("RW_WITHDRAWAL_PENDING", "RENEWAL_MUST_NAME_MARK"), ("RW_EXPIRY_UNSUPPORTED", "PLAUSIBILITY"),
                             ("RW_GENERATION_DIFFERS", None), ("RW_MARK_STALE", None)):
            result = self.renew(FakeConnection(rw_renew=GatewayRefusal(code, detail)))
            self.assertEqual((result.status, result.data["code"], result.data["detail"]), (EXIT_REFUSED, code, detail or ""), code)

    def test_a_renewal_that_times_out_on_in_flight_work_appends_nothing_and_names_the_lease(self):
        conn = FakeConnection(rw_renew=psycopg.errors.LockNotAvailable("timeout"), rw_in_flight=[(4321, LATER)])
        result = self.renew(conn)
        self.assertEqual((result.status, result.outcome), (EXIT_LOCK_TIMEOUT, "LOCK_TIMEOUT"))
        self.assertIn("recorded nothing", result.text)
        self.assertIn("blocking lease: backend 4321, complete_by %s" % store.iso(LATER), result.text)
        self.assertNotIn("renewed context", result.text)


class WithdrawTests(unittest.TestCase):
    MARK = (7, 1, NOW, True, False, fx.ACTOR, "PD-9001")           # id, generation, time, created, named, issuer, reference

    def withdraw(self, conn, **kw):
        return _tool(conn).withdraw(CTX, 1, actor=fx.ACTOR, ref=fx.REF, **kw)

    def test_a_completed_withdrawal_says_done_and_names_the_mark(self):
        conn = FakeConnection(rw_withdraw_mark=[self.MARK], rw_withdraw_apply=[(2, LATER, True, True)])
        result = self.withdraw(conn)
        self.assertEqual((result.status, result.outcome), (EXIT_DONE, "WITHDRAWN"))
        self.assertIn("done: generation 2 names drain mark 7", result.text)
        self.assertIn("drain mark 7 recorded at %s" % store.iso(NOW), result.text)

    def test_the_drain_mark_commits_in_a_transaction_of_its_own_before_the_wait(self):
        conn = FakeConnection(rw_withdraw_mark=[self.MARK], rw_withdraw_apply=[(2, LATER, True, True)])
        self.withdraw(conn, lock_timeout_ms=1500)
        (mark_tx, *_), = conn.calls("rw_withdraw_mark")
        (apply_tx, *_), = conn.calls("rw_withdraw_apply")
        self.assertLess(mark_tx, apply_tx)
        self.assertEqual([t for _tx, t, _p in conn.log if t.startswith("SET LOCAL")],
                         ["SET LOCAL lock_timeout = '10000ms'", "SET LOCAL lock_timeout = '1500ms'"])
        self.assertEqual(conn.calls("rw_withdraw_mark")[0][2][2:], (fx.ACTOR, "PD-9001", "a" * 40, "b" * 64))

    def test_a_timed_out_withdrawal_is_explicit_and_never_done(self):
        conn = FakeConnection(rw_withdraw_mark=[self.MARK], rw_withdraw_apply=psycopg.errors.LockNotAvailable("timeout"),
                              rw_in_flight=[(4321, LATER), (4322, LATER + dt.timedelta(seconds=1))])
        result = self.withdraw(conn, lock_timeout_ms=1500)
        self.assertEqual((result.status, result.outcome), (EXIT_NOT_YET_EFFECTIVE, "NOT_YET_EFFECTIVE"))
        self.assertNotEqual(result.status, 0)
        self.assertIn("not yet effective for in-flight work; new admissions refused since %s" % store.iso(NOW), result.text)
        self.assertIn("blocking lease: backend 4321, complete_by %s" % store.iso(LATER), result.text)
        self.assertIn("blocking lease: backend 4322", result.text)
        self.assertNotIn("done", result.text.lower())
        self.assertNotIn("withdrawn", result.text.lower())
        self.assertEqual(result.data["mark_id"], 7)

    def test_a_rerun_finds_the_mark_and_continues(self):
        conn = FakeConnection(rw_withdraw_mark=[(7, 1, NOW, False, False, fx.ACTOR, "PD-9001")], rw_withdraw_apply=[(2, LATER, True, True)])
        result = self.withdraw(conn)
        self.assertEqual(result.status, EXIT_DONE)
        self.assertIn("drain mark 7 already recorded at", result.text)

    def test_a_rerun_after_completion_reports_already_effective(self):
        conn = FakeConnection(rw_withdraw_mark=[(7, 1, NOW, False, True, fx.ACTOR, "PD-9001")], rw_withdraw_apply=[(2, LATER, False, True)])
        result = self.withdraw(conn)
        self.assertEqual(result.status, EXIT_DONE)
        self.assertIn("done (already effective): generation 2 names drain mark 7", result.text)

    def test_a_mark_that_a_renewal_superseded_is_not_reported_as_a_withdrawal(self):
        conn = FakeConnection(rw_withdraw_mark=[(7, 1, NOW, False, True, fx.ACTOR, "PD-9001")], rw_withdraw_apply=[(2, LATER, False, False)])
        result = self.withdraw(conn)
        self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, "RW_MARK_STALE"))
        self.assertNotIn("done", result.text.lower())

    def test_a_refused_mark_stops_before_the_wait(self):
        conn = FakeConnection(rw_withdraw_mark=GatewayRefusal("RW_GENERATION_DIFFERS"))
        result = self.withdraw(conn)
        self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, "RW_GENERATION_DIFFERS"))
        self.assertEqual(conn.calls("rw_withdraw_apply"), [])

    def test_a_lost_connection_in_either_step_is_unknown_and_keeps_the_mark_visible(self):
        first = FakeConnection(rw_withdraw_mark=[self.MARK])
        first.commit_error = psycopg.OperationalError("lost")
        self.assertEqual(self.withdraw(first).status, EXIT_UNKNOWN)
        self.assertEqual(first.calls("rw_withdraw_apply"), [])

        class SecondStepLost(RealPublisher):
            calls_to_commit = 0

            def _after_commit(self):
                type(self).calls_to_commit += 1
                if type(self).calls_to_commit == 2:
                    raise psycopg.OperationalError("lost")
        conn = FakeConnection(rw_withdraw_mark=[self.MARK], rw_withdraw_apply=[(2, LATER, True, True)])
        result = SecondStepLost(conn, "rw_t").withdraw(CTX, 1, actor=fx.ACTOR, ref=fx.REF)
        self.assertEqual(result.status, EXIT_UNKNOWN)
        self.assertIn("drain mark 7 recorded", result.text)
        self.assertNotIn("done:", result.text)

    def test_no_reference_means_no_statement(self):
        conn = FakeConnection()
        result = _tool(conn).withdraw(CTX, 1, actor=fx.ACTOR, ref=None)
        self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, "RW_DECISION_REF_REQUIRED"))
        self.assertEqual(conn.log, [])

    # ---- M-3 (technical review R1): once the drain mark is committed, no later failure of the withdrawal may say that nothing was
    # ---- recorded. A wait that ends by anything but the lock timeout is the same pending state, with the same status.
    def assertMarkStaysRecorded(self, result, label):
        self.assertIn("drain mark 7 recorded at %s" % store.iso(NOW), result.text, label)
        self.assertNotIn("nothing was recorded", result.text, label)
        self.assertNotIn("recorded nothing", result.text, label)
        self.assertNotIn("done", result.text.lower(), label)

    def test_a_wait_that_ends_by_a_statement_timeout_a_cancel_or_a_deadlock_is_the_pending_state(self):
        for label, error in (("statement timeout or cancel", psycopg.errors.QueryCanceled("canceling statement due to statement timeout")),
                             ("deadlock", psycopg.errors.DeadlockDetected("deadlock detected")),
                             ("serialization failure", psycopg.errors.SerializationFailure("could not serialize")),
                             ("an error with no gateway code", psycopg.errors.IntegrityError("integrity"))):
            conn = FakeConnection(rw_withdraw_mark=[self.MARK], rw_withdraw_apply=error, rw_in_flight=[(4321, LATER)])
            result = self.withdraw(conn)
            self.assertEqual((result.status, result.outcome), (EXIT_NOT_YET_EFFECTIVE, "NOT_YET_EFFECTIVE"), label)
            self.assertMarkStaysRecorded(result, label)
            self.assertIn("new admissions are refused with RW_WITHDRAWAL_PENDING", result.text, label)
            self.assertIn("not yet effective for in-flight work; new admissions refused since %s" % store.iso(NOW), result.text, label)
            self.assertIn("(%s)" % type(error).__name__, result.text, label)
            self.assertIn("no generation was appended", result.text, label)
            self.assertIn("blocking lease: backend 4321", result.text, label)
            self.assertEqual(result.data["mark_id"], 7, label)
            self.assertEqual(len(conn.calls("rw_withdraw_apply")), 1, label)                    # no retry

    def test_a_gateway_refusal_of_the_second_step_says_the_mark_stays_recorded(self):
        for code in ("RW_NOT_FOUND", "RW_MARK_NOT_FOUND", "RW_MARK_STALE", "RW_SHAPE"):
            conn = FakeConnection(rw_withdraw_mark=[self.MARK], rw_withdraw_apply=GatewayRefusal(code))
            result = self.withdraw(conn)
            self.assertEqual((result.status, result.data["code"], result.data["mark_id"]), (EXIT_REFUSED, code, 7), code)
            self.assertMarkStaysRecorded(result, code)
            self.assertIn("the drain mark 7 stays recorded", result.text, code)

    def test_an_error_at_the_commit_of_the_second_step_is_unknown_and_names_the_recorded_mark(self):
        for label, error in (("lock timeout at the commit", psycopg.errors.LockNotAvailable("lock")),
                             ("deadlock at the commit", psycopg.errors.DeadlockDetected("d")),
                             ("no gateway code at the commit", psycopg.errors.CheckViolation("c")),
                             ("lost connection", psycopg.OperationalError("lost"))):
            conn = FakeConnection(rw_withdraw_mark=[self.MARK], rw_withdraw_apply=[(2, LATER, True, True)])
            conn.commit_errors = {2: error}                                    # the second transaction's COMMIT
            result = self.withdraw(conn)
            self.assertEqual((result.status, result.outcome), (EXIT_UNKNOWN, "UNKNOWN"), label)
            self.assertMarkStaysRecorded(result, label)
            self.assertIn("the drain mark 7 is recorded; whether the generation was appended is not known", result.text, label)
            self.assertIn("status view", result.text, label)
            self.assertEqual(len(conn.calls("rw_withdraw_apply")), 1, label)

    def test_the_first_step_never_claims_a_record_it_did_not_make(self):
        # Before the mark commits, a refusal or a lock timeout really recorded nothing.
        conn = FakeConnection(rw_withdraw_mark=psycopg.errors.QueryCanceled("c"))
        result = self.withdraw(conn)
        self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, "RW_STATEMENT_FAILED"))
        self.assertIn("nothing was recorded", result.text)
        self.assertEqual(conn.calls("rw_withdraw_apply"), [])
        result = self.withdraw(FakeConnection(rw_withdraw_mark=psycopg.errors.LockNotAvailable("lock")))
        self.assertEqual((result.status, result.outcome), (EXIT_LOCK_TIMEOUT, "LOCK_TIMEOUT"))
        self.assertIn("recorded nothing", result.text)

    def test_a_concurrent_mark_is_reported_as_already_recorded_with_its_own_issuer(self):
        # L-4: two operators withdraw the same generation at once. The loser created nothing; its output must not claim a record
        # under ITS actor and reference, and it names whose record exists.
        other = (7, 1, NOW, False, False, "other-owner", "PD-9003")
        result = self.withdraw(FakeConnection(rw_withdraw_mark=[other], rw_withdraw_apply=[(2, LATER, True, True)]))
        self.assertEqual(result.status, EXIT_DONE)
        self.assertIn("drain mark 7 already recorded at %s" % store.iso(NOW), result.text)
        self.assertNotIn("drain mark 7 recorded at", result.text)
        self.assertIn("that mark was recorded by other-owner under PD-9003; this command's actor and reference were not recorded", result.text)
        same = (7, 1, NOW, False, False, fx.ACTOR, "PD-9001")                   # the same operator re-running: no such line
        result = self.withdraw(FakeConnection(rw_withdraw_mark=[same], rw_withdraw_apply=[(2, LATER, True, True)]))
        self.assertNotIn("that mark was recorded by", result.text)


class StatusTests(unittest.TestCase):
    def test_status_prints_the_rule_as_an_upper_bound_and_lists_pending_marks(self):
        status_rows = [(CTX, 2, fx.ALL_RIGHTS, "LEASE", LATER, LATER + dt.timedelta(days=30), 1)]
        marks = [(7, CTX, 2, "invented-owner", "PD-9001", NOW, dt.timedelta(seconds=125))]
        conn = FakeConnection(rw_status=status_rows, rw_pending_marks=marks)
        result = _tool(conn).status()
        self.assertIn(store.PLAUSIBILITY_WORDING, result.text)
        self.assertNotIn("within", result.text.lower())
        self.assertIn("pending drain mark 7 on context %s generation 2 by invented-owner under PD-9001 since %s (age 0:02:05)" %
                      (CTX, store.iso(NOW)), result.text)
        self.assertEqual((result.status, result.data), (EXIT_DONE, {"contexts": 1, "pending": 1}))

    def test_status_of_nothing_says_so(self):
        self.assertEqual(_tool(FakeConnection(rw_status=[], rw_pending_marks=[])).status().text, "no context is published")


class InstallerInputTests(unittest.TestCase):
    def test_w_is_a_whole_number_of_seconds_from_one_to_a_day(self):
        names = dict(schema="rw_s", owner_role="rw_o", executor_role="rw_e", loader_role="rw_l", publisher_role="rw_p")
        for bad in (0, -1, 86401, 1.5, "4", True, None):
            with self.assertRaises(RealWorkspaceError, msg=repr(bad)) as caught:
                store._check_install_inputs(w_seconds=bad, **names)
            self.assertEqual(caught.exception.code, "RW_SHAPE")
        for good in (1, 4, 600, 86400):
            self.assertEqual(store._check_install_inputs(w_seconds=good, **names)[0], "rw_s")

    def test_roles_must_be_four_distinct_exact_identifiers(self):
        with self.assertRaises(RealWorkspaceError) as caught:
            store._check_install_inputs("rw_s", "rw_o", "rw_e", "rw_e", "rw_p", 4)
        self.assertEqual(caught.exception.code, "RW_ROLE_DIFFERS")
        for bad in ("RW_O", "rw o", "rw-o", "", "1rw", "rw;drop", "x" * 64):
            with self.assertRaises(RealWorkspaceError, msg=bad) as caught:
                store._check_install_inputs("rw_s", bad, "rw_e", "rw_l", "rw_p", 4)
            self.assertEqual(caught.exception.code, "RW_SHAPE")

    def test_the_test_installer_refuses_the_reserved_real_namespace_before_writing(self):
        conn = FakeConnection(**{"current_database": lambda text, params: [("finweb_real_main",)]})
        conn.execute = self._wrap(conn)
        with self.assertRaises(RealWorkspaceError) as caught:
            store.install_test_gateway(conn, schema="rw_s", owner_role="rw_o", executor_role="rw_e", loader_role="rw_l",
                                       publisher_role="rw_p", w_seconds=4)
        self.assertEqual(caught.exception.code, "RW_INSTALL_KIND_REFUSED")
        self.assertEqual([t for _tx, t, _p in conn.log], ["SELECT current_database()"])

    @staticmethod
    def _wrap(conn):
        def execute(query, params=()):
            text = query if isinstance(query, str) else query.as_string()
            conn.log.append((conn.transactions, text, params))
            if text == "SELECT current_database()":
                return _Cursor([("finweb_real_main",)])
            raise AssertionError("unscripted: " + text)
        return execute


class ExecutorWrapperTests(unittest.TestCase):
    def test_admit_checks_the_snapshot_against_the_context_id(self):
        snapshot = rp.verify_proposal(_proposal("admit")).snapshot
        row = ("owner", "root", snapshot.context_id, 1, "op", "ARCHIVE_READ", LATER)
        conn = FakeConnection(rw_admit=[(snapshot.data,)], rw_scope=[row])
        conn.status = TransactionStatus.INTRANS
        lease = store.admit(conn, "rw_t", owner="owner", root="root", context_id=snapshot.context_id, generation=1, purpose="ARCHIVE_READ",
                            operation_id="op", command_sha256="1" * 64)
        self.assertEqual((lease.snapshot, lease.context_id, lease.complete_by), (snapshot.data, snapshot.context_id, LATER))
        conn = FakeConnection(rw_admit=[(snapshot.data + b" ",)], rw_scope=[row])
        conn.status = TransactionStatus.INTRANS
        with self.assertRaises(RealWorkspaceError) as caught:
            store.admit(conn, "rw_t", owner="owner", root="root", context_id=snapshot.context_id, generation=1, purpose="ARCHIVE_READ",
                        operation_id="op", command_sha256="1" * 64)
        self.assertEqual(caught.exception.code, "RW_CONTEXT_DIFFERS")

    def test_admit_maps_a_gateway_refusal_and_requires_an_open_transaction(self):
        conn = FakeConnection(rw_admit=GatewayRefusal("RW_LAPSED"))
        with self.assertRaises(RealWorkspaceError) as caught:
            store.admit(conn, "rw_t", owner="o", root="r", context_id=CTX, generation=1, purpose="ARCHIVE_READ", operation_id="x",
                        command_sha256="1" * 64)
        self.assertEqual(caught.exception.code, "RW_ACTIVE_TRANSACTION_REQUIRED")
        conn.status = TransactionStatus.INTRANS
        with self.assertRaises(RealWorkspaceError) as caught:
            store.admit(conn, "rw_t", owner="o", root="r", context_id=CTX, generation=1, purpose="ARCHIVE_READ", operation_id="x",
                        command_sha256="1" * 64)
        self.assertEqual(caught.exception.code, "RW_LAPSED")


class CommandLineTests(unittest.TestCase):
    ARGS = ["--socket", "/tmp/.s.PGSQL.5432", "--database", "d", "--user", "u", "--schema", "rw_t"]

    def run_cli(self, extra, conn):
        out = io.StringIO()
        status = store.main(self.ARGS + extra, connect=lambda args: conn, out=out)
        return status, out.getvalue()

    def test_status_command(self):
        conn = FakeConnection(rw_status=[], rw_pending_marks=[])
        status, text = self.run_cli(["status"], conn)
        self.assertEqual((status, text.strip(), conn.closed), (0, "no context is published", True))

    def test_withdraw_command_without_a_valid_reference_exits_two_and_touches_nothing(self):
        conn = FakeConnection()
        status, text = self.run_cli(["withdraw", "--context", CTX, "--generation", "1", "--actor", "a", "--pd", "PD-1", "--commit", "x", "--sha", "y"], conn)
        self.assertEqual(status, EXIT_REFUSED)
        self.assertIn("RW_DECISION_REF_REQUIRED", text)
        self.assertEqual(conn.log, [])

    def test_publish_command_reads_the_proposal_and_the_evidence_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            proposal, evidence = Path(tmp, "p.json"), Path(tmp, "e.json")
            proposal.write_bytes(_proposal("cli"))
            evidence.write_text(json.dumps([store.BasisEntry("syn.alpha", "LEASE_TERM", fx.REF, fx.FAR).as_json(),
                                            BasisEntry("syn.beta", "NOT_ASSESSED", fx.REF).as_json(),
                                            BasisEntry("syn.cal", "NOT_ASSESSED", fx.REF).as_json()]))
            conn = FakeConnection(rw_install_info=[("TEST", 4)], rw_publish=[(CTX, 1, True)])      # R6: the tool reads the install kind first (5.2)
            status, text = self.run_cli(["publish", "--proposal", str(proposal), "--evidence-file", str(evidence), "--valid-until",
                                         "2030-01-01T00:00:00Z", "--actor", fx.ACTOR, "--pd", "PD-9001", "--commit", "a" * 40, "--sha", "b" * 64], conn)
            self.assertEqual(status, 0)
            self.assertIn("published context " + CTX, text)
            self.assertIn(store.PLAUSIBILITY_WORDING, text)
            evidence.write_text(json.dumps([{"source_id": "syn.alpha", "basis": "NOT_ASSESSED", "pd_id": "PD-9001", "git_commit": "a" * 40,
                                             "doc_sha256": "b" * 64, "free_text": "x"}]))
            status, text = self.run_cli(["publish", "--proposal", str(proposal), "--evidence-file", str(evidence), "--actor", "a", "--pd", "PD-9001",
                                         "--commit", "a" * 40, "--sha", "b" * 64], FakeConnection())
            self.assertEqual(status, EXIT_REFUSED)
            self.assertIn("RW_SHAPE", text)

    def test_malformed_input_is_a_typed_refusal_with_an_exit_status_never_a_traceback(self):
        # L-8 (technical review R1): bad JSON, a missing or unreadable file, a non-UTF-8 file and a connection that cannot be made
        # each end as a refusal with exit status 2, and nothing is sent to the database.
        publish = ["publish", "--actor", "a", "--pd", "PD-9001", "--commit", "a" * 40, "--sha", "b" * 64]
        with tempfile.TemporaryDirectory() as tmp:
            proposal, evidence, binary = Path(tmp, "p.json"), Path(tmp, "e.json"), Path(tmp, "b.json")
            proposal.write_bytes(_proposal("cli-bad"))
            evidence.write_text("[]")
            binary.write_bytes(b"\xff\xfe\x00")
            missing = str(Path(tmp, "missing.json"))
            cases = {
                "rights not json": (publish + ["--proposal", str(proposal), "--evidence-file", str(evidence), "--rights-json", "{bad"], "RW_SHAPE"),
                "missing proposal": (publish + ["--proposal", missing, "--evidence-file", str(evidence)], "RW_INPUT_UNREADABLE"),
                "missing evidence": (publish + ["--proposal", str(proposal), "--evidence-file", missing], "RW_INPUT_UNREADABLE"),
                "evidence not utf-8": (publish + ["--proposal", str(proposal), "--evidence-file", str(binary)], "RW_INPUT_UNREADABLE"),
                "directory as a file": (publish + ["--proposal", tmp, "--evidence-file", str(evidence)], "RW_INPUT_UNREADABLE"),
            }
            for label, (extra, code) in cases.items():
                conn = FakeConnection()
                status, text = self.run_cli(extra, conn)
                self.assertEqual(status, EXIT_REFUSED, label)
                self.assertIn(code, text, label)
                self.assertIn("nothing was recorded", text, label)
                self.assertEqual(conn.log, [], label)
                self.assertTrue(conn.closed, label)
            evidence.write_text("{bad")
            conn = FakeConnection()
            status, text = self.run_cli(publish + ["--proposal", str(proposal), "--evidence-file", str(evidence)], conn)
            self.assertEqual(status, EXIT_REFUSED)
            self.assertIn("RW_SHAPE", text)
            self.assertEqual(conn.log, [])
        conn = FakeConnection()
        out = io.StringIO()
        status = store.main(["--socket", "/tmp/.s.PGSQL.5432", "--database", "d", "--user", "u", "--schema", "rw_t", "--lock-timeout-ms", "0", "status"],
                            connect=lambda args: conn, out=out)
        self.assertEqual((status, conn.log), (EXIT_REFUSED, []))
        self.assertIn("RW_SHAPE", out.getvalue())

        def cannot_connect(args):
            raise psycopg.OperationalError("connection refused")
        out = io.StringIO()
        status = store.main(self.ARGS + ["status"], connect=cannot_connect, out=out)
        self.assertEqual(status, EXIT_REFUSED)
        self.assertIn("RW_CONNECT_FAILED", out.getvalue())
        self.assertIn("OperationalError", out.getvalue())

    def test_times_are_utc_seconds_only(self):
        self.assertEqual(store.parse_utc("2027-08-31T16:00:00Z"), dt.datetime(2027, 8, 31, 16, tzinfo=dt.timezone.utc))
        for bad in ("2027-08-31", "2027-08-31T16:00:00", "2027-08-31T16:00:00+08:00", "2027-13-31T16:00:00Z", "2027-08-31 16:00:00Z", None, 5):
            with self.assertRaises(RealWorkspaceError, msg=repr(bad)):
                store.parse_utc(bad)


if __name__ == "__main__":
    unittest.main()
