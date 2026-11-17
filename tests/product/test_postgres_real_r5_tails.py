"""F1 R5, PostgreSQL: the SHARED CREATE TAIL and the SHARED READ TAIL, on the `SYNTHETIC_TEST` create (design 3.2, 4.4, E23; tests T-a to T-g).

LABELS. Every test says what it is, in its docstring:
  "product path, shared tail on SYNTHETIC_TEST"  the product's create, read, reproduce or list code (`real_workspace_service` over
                                                   `real_tails`) on an accepted commit of the fictional branch. It shows the TAIL; it does not
                                                   show the real branch's own commit, which cannot happen before R8 (the service refuses invented
                                                   data, fact 12).
  "E11 crafted probe, not product evidence"       a state the owner role wrote in the test's own disposable database.
  "first run at R8"                                not run here.
There is NO acknowledgement-loss re-proof for the real branch (PD-0068 answer 2): T-c and T-d are the SHARED TAIL's, on the `SYNTHETIC_TEST`
create, and nothing in this module claims otherwise.

The invented data is labelled synthetic throughout; nothing is marked `synthetic = false`.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
import time
import unittest.mock as mock
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg.pq import TransactionStatus  # noqa: E402

from persistence import real_labels, real_tails  # noqa: E402
from persistence.real_workspace_context import require_in_transaction  # noqa: E402
from real_gateway_kit import setUpModule, tearDownModule  # noqa: E402,F401
import real_gateway_fixtures as fx  # noqa: E402
from real_r5_case import AS_OF, CRAFTED, PRODUCT, R5Case, RecordingConnection  # noqa: E402
from web_api import real_scoped_contract as contract  # noqa: E402


class AcceptedCreateTests(R5Case):
    INSTALL = "r5a"

    def test_the_create_commits_one_atomic_bundle_and_stores_the_origin_it_took_from_the_scope(self):
        """product path, shared tail on SYNTHETIC_TEST: the existing fictional integration runs UNCHANGED over the S2 tables; root, revision, portfolio, account, two ledger events,
        artifact and operation become visible together, and the four origin fields are the scope's (never a caller's)."""
        live, owner = self.fictional_live(), self.new_owner()
        result, body = self.create(live, owner)
        self.assertEqual(type(result).__name__, "Created", result)
        counts = self.tables_for(result.root_id)
        self.assertEqual({k: v for k, v in counts.items() if k != "rw_journal"},
                         {"portfolio": 1, "rw_root": 1, "rw_revision": 1, "account": 1, "rw_root_link": 1, "rw_lease": 1, "rw_artifact": 1,
                          "rw_operation": 1, "ledger_event": 2})
        row = self.owner.execute(f"SELECT market_origin,ledger_origin,personal_holdings,synthetic FROM {self.s}.rw_root WHERE portfolio_id=%s",
                                 (result.root_id,)).fetchone()
        self.assertEqual(row, ("SYNTHETIC_TEST", "INVENTED_TEST_LEDGER", False, True))
        self.assertEqual(result.archive.origin, {"market_origin": row[0], "ledger_origin": row[1], "personal_holdings": row[2], "synthetic": row[3]})
        self.assertEqual(result.archive.labels["origin_kind"], real_labels.root_labels(result.archive.origin)["origin_kind"])
        self.assertNotIn(b"REAL_SOURCE", result.archive.response + result.archive.issued + result.archive.envelope)
        self.assertFalse(result.replayed)
        # the connection is back at IDLE and the lease is SEALED in the committed record
        self.assertEqual(self.executor.info.transaction_status, TransactionStatus.IDLE)
        self.assertEqual(self.owner.execute(f"SELECT phase FROM {self.s}.rw_lease WHERE root_id=%s", (result.root_id,)).fetchone()[0], "SEALED")

    def test_an_exact_retry_replays_the_committed_operation_and_calls_no_service_and_writes_nothing(self):
        """product path, shared tail on SYNTHETIC_TEST: the second call of the IDENTICAL command is a REPLAY (a read-only lease), from a new service object and a new connection,
        and the fictional issuer is not called."""
        import financial_service_integration as integration
        live, owner = self.fictional_live(), self.new_owner()
        first, body = self.create(live, owner)
        before = self.tables_for(first.root_id)
        fresh = self.conn("executor")
        with mock.patch.object(integration, "issue_local_service", side_effect=AssertionError("a replay must not call the service")):
            again, _ = self.create(live, owner, body, conn=fresh)
        self.assertEqual(type(again).__name__, "Created", again)
        self.assertTrue(again.replayed)
        self.assertEqual((again.archive.issued_sha256, again.archive.response_sha256), (first.archive.issued_sha256, first.archive.response_sha256))
        after = self.tables_for(first.root_id)
        self.assertEqual({k: v for k, v in after.items() if k != "rw_lease"}, {k: v for k, v in before.items() if k != "rw_lease"})

    def test_the_same_operation_with_another_command_is_an_idempotency_conflict_and_changes_nothing(self):
        """product path, shared tail on SYNTHETIC_TEST (T08): the operation id was used with a different body."""
        live, owner = self.fictional_live(), self.new_owner()
        first, body = self.create(live, owner)
        before = self.tables_for(first.root_id)
        other = dict(body, name="a different name")
        again, _ = self.create(live, owner, other)
        self.assertEqual(type(again).__name__, "Refused", again)
        self.assertEqual(again.code, "RW_IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.tables_for(first.root_id), before)

    def test_an_invalid_intent_is_refused_before_any_statement(self):
        """product path, shared tail on SYNTHETIC_TEST: the intent is validated before a transaction is opened."""
        live, owner = self.fictional_live(), self.new_owner()
        recorder = RecordingConnection(self.executor)
        bad = dict(self.intent(live), constructed_ledger_acknowledged=False)
        result = self.service.create(recorder, owner=owner, body=bad, generation=1, link=self.link(live))
        self.assertEqual((type(result).__name__, result.code), ("Refused", "REAL_REQUEST_INVALID"))
        self.assertEqual(recorder.statements, [])

    def test_a_release_the_context_does_not_name_is_refused_and_nothing_is_left(self):
        """product path, shared tail on SYNTHETIC_TEST: `expected_release_id` is a binding check against the locked snapshot."""
        live, owner = self.fictional_live(), self.new_owner()
        body = dict(self.intent(live), expected_release_id="f" * 64)
        result, _ = self.create(live, owner, body)
        self.assertEqual((type(result).__name__, result.code), ("Refused", "RW_CONTEXT_BINDING_DIFFERS"))
        self.assertNothingLeft(self.root_of(owner, body))

    def test_a_context_that_is_not_published_is_not_found_and_nothing_is_left(self):
        """product path, shared tail on SYNTHETIC_TEST: admission refuses an unknown context."""
        live, owner = self.fictional_live(), self.new_owner()
        body = dict(self.intent(live), source_context_id="e" * 64)
        result, _ = self.create(live, owner, body)
        self.assertEqual((type(result).__name__, result.code), ("Refused", "RW_NOT_FOUND"))
        self.assertNothingLeft(self.root_of(owner, body))


class FictionalIntegrationRunsUnchangedTests(R5Case):
    INSTALL = "r5b"

    def test_the_create_reads_no_md_table_and_calls_the_integration_issuer_once(self):
        """product path, shared tail on SYNTHETIC_TEST (R5's first task, 4.2 build table): the integration is called UNCHANGED; the fictional branch reads no stored market data."""
        import financial_service_integration as integration
        live, owner = self.fictional_live(), self.new_owner()
        recorder = RecordingConnection(self.executor)
        with mock.patch.object(integration, "issue_local_service", wraps=integration.issue_local_service) as issuer:
            result = self.service.create(recorder, owner=owner, body=self.intent(live), generation=1, link=self.link(live))
        self.assertEqual(type(result).__name__, "Created", result)
        self.assertEqual(issuer.call_count, 1)
        from real_r5_case import md_table_reads
        self.assertEqual(md_table_reads(recorder.statements), [])


class ReadPathsTests(R5Case):
    INSTALL = "r5c"

    def committed(self):
        live, owner = self.fictional_live(), self.new_owner()
        created, body = self.create(live, owner)
        self.assertEqual(type(created).__name__, "Created", created)
        return live, owner, created, body

    def test_archive_read_returns_the_stored_bytes_and_the_stored_origin(self):
        """product path, shared tail on SYNTHETIC_TEST: ARCHIVE_READ delivers the committed bundle after the COMMIT; origin and labels are read from the STORED response."""
        live, owner, created, body = self.committed()
        read = self.service.archive_read(self.conn("executor"), owner=owner, root=created.root_id, operation_id=created.operation_id,
                                         context_id=live.ctx, generation=1)
        self.assertIsInstance(read, real_tails.Done)
        self.assertEqual((read.value.issued_sha256, read.value.response_sha256), (created.archive.issued_sha256, created.archive.response_sha256))
        self.assertEqual(read.value.origin, {"market_origin": "SYNTHETIC_TEST", "ledger_origin": "INVENTED_TEST_LEDGER", "personal_holdings": False, "synthetic": True})
        self.assertEqual(read.value.labels["origin_kind"], "INVENTED_TEST_DATA")

    def test_reproduce_runs_the_same_service_again_and_finds_the_same_bytes(self):
        """product path, shared tail on SYNTHETIC_TEST (T08): EXECUTE_REPRODUCE under the current generation's own lease, with the original generation's binding."""
        live, owner, created, body = self.committed()
        again = self.service.reproduce(self.conn("executor"), owner=owner, root=created.root_id, operation_id=created.operation_id,
                                       context_id=live.ctx, generation=1)
        self.assertIsInstance(again, real_tails.Done)
        self.assertEqual((again.value.status, again.value.detail), ("REPRODUCED", ""))
        self.assertEqual(again.value.issued_sha256, created.archive.issued_sha256)

    def test_a_foreign_owner_cannot_read_the_operation(self):
        """product path, shared tail on SYNTHETIC_TEST: the archive is addressed by (owner, operation) and the lease by the root's own owner."""
        live, owner, created, body = self.committed()
        stranger = self.new_owner()
        read = self.service.archive_read(self.conn("executor"), owner=stranger, root=created.root_id, operation_id=created.operation_id,
                                         context_id=live.ctx, generation=1)
        self.assertIsInstance(read, real_tails.Refused)
        self.assertEqual(read.code, "RW_NOT_FOUND")

    def test_list_returns_the_owners_roots_with_the_stored_origin_and_no_number(self):
        """product path, shared tail on SYNTHETIC_TEST: the owner-scoped list (design 2.4): identifiers, the stored origin fields, the generation and the creation time."""
        live, owner, created, body = self.committed()
        other = self.new_owner()
        listed = self.service.list_roots(self.conn("executor"), owner=owner)
        self.assertIsInstance(listed, real_tails.Done)
        self.assertEqual(len(listed.value), 1)
        entry = listed.value[0]
        self.assertEqual(set(entry), {"root_id", "operation_id", "context_id", "generation", "created_at", "origin"})
        self.assertEqual((entry["root_id"], entry["context_id"], entry["generation"]), (str(created.root_id), live.ctx, 1))
        self.assertEqual(entry["operation_id"], str(created.operation_id))          # DR-R8-1: the stored create operation, so the list can reopen the root
        self.assertEqual(entry["origin"], created.archive.origin)
        self.assertEqual(self.service.list_roots(self.conn("executor"), owner=other).value, [])        # empty only when the owner has no root
        payload = contract.list_payload(listed.value)
        self.assertEqual(payload["roots"], listed.value)

    def test_a_withdrawn_context_is_listed_with_its_refusal_code_not_as_an_empty_list(self):
        """product path, shared tail on SYNTHETIC_TEST: each entry is its own ARCHIVE_READ admission; a completed withdrawal returns the code (design 2.4)."""
        live, owner, created, body = self.committed()
        result = self.tool().withdraw(live.ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual(result.status, 0, result.text)
        listed = self.service.list_roots(self.conn("executor"), owner=owner)
        self.assertEqual(listed.value, [{"root_id": str(created.root_id), "context_id": live.ctx, "status": "RW_WITHDRAWN"}])

    def test_each_purpose_is_refused_independently(self):
        """product path, shared tail on SYNTHETIC_TEST (T08): a context that grants ARCHIVE_READ but not EXECUTE_REPRODUCE reads and does not reproduce."""
        live, owner, created, body = self.committed()
        rights = dict(fx.ALL_RIGHTS, EXECUTE_REPRODUCE=False)
        renewed = self.renew(live.ctx, 1, valid_until=self.db_now() + dt.timedelta(seconds=120), rights=rights, evidence=self.evidence())
        self.assertEqual(renewed.status, 0, renewed.text)
        read = self.service.archive_read(self.conn("executor"), owner=owner, root=created.root_id, operation_id=created.operation_id,
                                         context_id=live.ctx, generation=2)
        self.assertIsInstance(read, real_tails.Done)
        again = self.service.reproduce(self.conn("executor"), owner=owner, root=created.root_id, operation_id=created.operation_id,
                                       context_id=live.ctx, generation=2)
        self.assertEqual((type(again).__name__, again.code), ("Refused", "RW_RIGHT_REFUSED"))


class StatementRecorderTests(R5Case):
    INSTALL = "r5d"

    def test_T_a_the_create_names_each_constraint_and_never_all_and_never_the_deadline_guard(self):
        """product path, shared tail on SYNTHETIC_TEST (T-a): a non-vacuous recorder. It sees the create's own admit, at least one NAMED `SET CONSTRAINTS`, never `ALL`, never the
        deadline guard's name; every name is on the inventory."""
        from persistence import real_catalog_audit
        live, owner = self.fictional_live(), self.new_owner()
        recorder = RecordingConnection(self.executor)
        result = self.service.create(recorder, owner=owner, body=self.intent(live), generation=1, link=self.link(live))
        self.assertEqual(type(result).__name__, "Created", result)
        self.assertGreaterEqual(len(recorder.admits()), 1, "the recorder saw no admit: it is not wired to the path under test")
        statements = recorder.set_constraints()
        self.assertGreaterEqual(len(statements), 1, "the recorder saw no SET CONSTRAINTS: a recorder that sees none passes vacuously")
        names = []
        for statement in statements:
            self.assertIsNone(re.match(r"SET\s+CONSTRAINTS\s+ALL\b", statement, re.I), statement)
            self.assertNotIn(real_tails.DEADLINE_GUARD, statement)
            names.append(statement.split(".")[1].split(" ")[0].strip('"'))
        inventory = {n for n, _t, _k in real_catalog_audit.EXPECTED_DEFERRABLE}
        self.assertEqual(set(names), inventory - {real_tails.DEADLINE_GUARD})
        self.assertEqual(len(names), len(set(names)))

    def test_T_a_the_firing_comes_after_the_seal_and_before_the_commit(self):
        """product path, shared tail on SYNTHETIC_TEST (T-a): the order of the create's own statements: admit, writes, the service, the seal, then the firing."""
        live, owner = self.fictional_live(), self.new_owner()
        recorder = RecordingConnection(self.executor)
        self.assertEqual(type(self.service.create(recorder, owner=owner, body=self.intent(live), generation=1, link=self.link(live))).__name__, "Created")
        first = lambda needle: next(i for i, s in enumerate(recorder.statements) if needle in s)          # noqa: E731
        self.assertLess(first("rw_admit"), first("INSERT INTO"))
        self.assertLess(first("rw_seal"), first("SET CONSTRAINTS"))
        self.assertGreater(first("SET CONSTRAINTS"), first("rw_seal"))
        self.assertEqual(recorder.statements[-1].split(".")[0], "SET CONSTRAINTS \"%s\"" % self.s)      # the last statement of the transaction is a firing

    def test_T_f_the_read_paths_record_their_own_statements_and_no_set_constraints_of_any_form(self):
        """product path, shared tail on SYNTHETIC_TEST (T-f): read, reproduce and each list entry. The recorder must see the path's own admit and read statements (a recorder wired
        to the wrong connection sees none and fails) and ZERO `SET CONSTRAINTS` of any form."""
        live, owner = self.fictional_live(), self.new_owner()
        created, _ = self.create(live, owner)
        paths = {
            "read": lambda c: self.service.archive_read(c, owner=owner, root=created.root_id, operation_id=created.operation_id, context_id=live.ctx, generation=1),
            "reproduce": lambda c: self.service.reproduce(c, owner=owner, root=created.root_id, operation_id=created.operation_id, context_id=live.ctx, generation=1),
            "list": lambda c: self.service.list_roots(c, owner=owner),
        }
        for name, run in paths.items():
            recorder = RecordingConnection(self.conn("executor"))
            outcome = run(recorder)
            self.assertIn(type(outcome).__name__, ("Done",), (name, outcome))
            self.assertGreaterEqual(len(recorder.admits()) + len(recorder.matching("rw_list_roots")), 1, name)
            self.assertGreaterEqual(len(recorder.matching("rw_archive")) + len(recorder.matching("rw_root")) + len(recorder.matching("rw_list_roots")), 1, name)
            self.assertEqual(recorder.set_constraints(), [], name)
            self.assertEqual([s for s in recorder.statements if "CONSTRAINTS" in s.upper()], [], name)


class InventoryTests(R5Case):
    INSTALL = "r5e"

    def test_T_a_the_inventory_check_refuses_a_deferrable_constraint_it_does_not_know(self):
        """E11 crafted probe, not product evidence (T-a): the owner adds a deferrable constraint to a table the create writes; the create is refused before the COMMIT and
        nothing is left. Then the constraint is dropped and the same create commits (the control)."""
        live, owner = self.fictional_live(), self.new_owner()
        with self.owner.transaction():
            self.owner.execute(f"ALTER TABLE {self.s}.account ADD CONSTRAINT r5_unknown_deferrable CHECK (name <> '') ")
            self.owner.execute(f"ALTER TABLE {self.s}.account ADD CONSTRAINT r5_unknown_fk FOREIGN KEY (portfolio_id) REFERENCES {self.s}.portfolio(portfolio_id) "
                               "DEFERRABLE INITIALLY DEFERRED")
        recorder = RecordingConnection(self.executor)
        body = self.intent(live)
        result = self.service.create(recorder, owner=owner, body=body, generation=1, link=self.link(live))
        self.assertEqual((type(result).__name__, result.code), ("Refused", "RW_UNKNOWN_DEFERRABLE"))
        self.assertIn("r5_unknown_fk", result.detail)
        self.assertEqual(recorder.set_constraints(), [])                                  # refused BEFORE any firing
        self.assertNothingLeft(self.root_of(owner, body))
        self.assertEqual(self.executor.info.transaction_status, TransactionStatus.IDLE)
        with self.owner.transaction():
            self.owner.execute(f"ALTER TABLE {self.s}.account DROP CONSTRAINT r5_unknown_fk")
            self.owner.execute(f"ALTER TABLE {self.s}.account DROP CONSTRAINT r5_unknown_deferrable")
        control, _ = self.create(live, owner, body)
        self.assertEqual(type(control).__name__, "Created", control)


class CommitTimeTests(R5Case):
    INSTALL = "r5f"
    W = 3

    def stalled(self, who="executor"):
        return self.conn(who, options=self.stall_options())

    def test_T_b_a_create_stalled_past_complete_by_is_refused_at_commit_by_the_deadline_guard(self):
        """product path, shared tail on SYNTHETIC_TEST (T-b): stalled between the seal and the COMMIT (the session's timeouts are 0, so they are not the bound). The deadline guard,
        still pending because the tail never fired it, refuses the COMMIT: a DEFINITE refusal, the connection IDLE, no row left."""
        live, owner = self.fictional_live(), self.new_owner()
        executor = self.stalled()
        for setting in ("statement_timeout", "idle_in_transaction_session_timeout", "lock_timeout"):
            self.assertEqual(executor.execute(f"SHOW {setting}").fetchone()[0], "0")

        def stall(tail):
            require_in_transaction(tail.conn)
            time.sleep(self.W + 1.0)
        body = self.intent(live)
        with mock.patch.object(real_tails.CreateTail, "_before_commit", stall):
            result = self.service.create(executor, owner=owner, body=body, generation=1, link=self.link(live))
        self.assertEqual((type(result).__name__, result.code), ("Refused", "RW_DEADLINE"))
        self.assertEqual(executor.info.transaction_status, TransactionStatus.IDLE)
        self.assertNothingLeft(self.root_of(owner, body))
        self.assertFalse(result.persisted)

    def test_T_b_control_the_same_create_without_the_stall_commits(self):
        """product path, shared tail on SYNTHETIC_TEST (T-b control): the stall is the only difference."""
        live, owner = self.fictional_live(), self.new_owner()
        result, _ = self.create(live, owner, conn=self.stalled())
        self.assertEqual(type(result).__name__, "Created", result)

    def test_T_c_acknowledgement_loss_after_an_accepted_commit_is_unknown_with_no_retry_and_reconciliation_finds_it_committed(self):
        """product path, shared tail on SYNTHETIC_TEST (T-c): the commit is real and the loss is injected AFTER it (F2's test_c20 pattern: `_after_commit` raises OperationalError).
        UNKNOWN; one operation row (nothing retried); reconciliation on a new connection reports COMMITTED; an absent operation stays UNKNOWN.
        Shared tail on SYNTHETIC_TEST: NOT a re-proof of the real branch's ordering (PD-0068 answer 2)."""
        live, owner = self.fictional_live(), self.new_owner()
        body = self.intent(live)

        def lost(tail):
            raise psycopg.OperationalError("injected acknowledgement loss")
        with mock.patch.object(real_tails.CreateTail, "_after_commit", lost):
            result, _ = self.create(live, owner, body)
        self.assertEqual(type(result).__name__, "Unknown", result)
        self.assertEqual(result.disposition, "UNKNOWN")
        root = self.root_of(owner, body)
        self.assertEqual(self.count("rw_operation", "root_id=%s", (root,)), 1)                       # committed, and not created twice
        self.assertEqual(self.count("rw_lease", "root_id=%s", (root,)), 1)
        reconciled = self.service.reconcile(owner=owner, body=body, generation=1)
        self.assertEqual(reconciled.status, "COMMITTED", reconciled)
        self.assertEqual(self.count("rw_operation", "root_id=%s", (root,)), 1)                       # reconciliation wrote nothing that counts
        absent = self.service.reconcile(owner=owner, body=self.intent(live), generation=1)
        self.assertEqual((absent.status, absent.reason), ("UNKNOWN", "ABSENT"))                     # never "rolled back" from absence

    def test_T_d_a_connection_killed_at_the_pre_commit_seam_is_unknown_and_absence_is_not_a_rollback(self):
        """product path, shared tail on SYNTHETIC_TEST (T-d): another connection terminates the backend at the seam. UNKNOWN; reconciliation finds the state absent and does NOT
        report a rollback from absence alone."""
        live, owner = self.fictional_live(), self.new_owner()
        body = self.intent(live)
        victim = self.conn("executor")
        pid = victim.info.backend_pid

        def kill(tail):
            require_in_transaction(tail.conn)
            self.admin.execute("SELECT pg_terminate_backend(%s)", (pid,))
            for _ in range(100):                                                    # wait until the backend is gone
                if not self.admin.execute("SELECT 1 FROM pg_stat_activity WHERE pid=%s", (pid,)).fetchone():
                    break
                time.sleep(0.05)
        with mock.patch.object(real_tails.CreateTail, "_before_commit", kill):
            result, _ = self.create(live, owner, body, conn=victim)
        self.assertEqual(type(result).__name__, "Unknown", result)
        reconciled = self.service.reconcile(owner=owner, body=body, generation=1)
        self.assertEqual((reconciled.status, reconciled.reason), ("UNKNOWN", "ABSENT"))
        self.assertNothingLeft(self.root_of(owner, body))

    def test_T_c_an_error_with_no_gateway_code_in_the_post_commit_check_is_unknown_even_on_an_idle_connection(self):
        """product path, shared tail on SYNTHETIC_TEST (3.1 E4), POST-COMMIT path only: the COMMIT SUCCEEDED and the tail's own post-commit check
        (`_after_commit`, patched here to raise) fails with an error that has no gateway code. The result is UNKNOWN, not a refusal, and the
        connection is IDLE. This does NOT show an error raised BY the COMMIT; that is the next test. The bundle IS durable here (the create
        committed), which is why a refusal would have been a wrong answer."""
        live, owner = self.fictional_live(), self.new_owner()
        body = self.intent(live)

        def after(tail):
            raise psycopg.errors.CheckViolation("a constraint error with no gateway code")
        with mock.patch.object(real_tails.CreateTail, "_after_commit", after):
            result, _ = self.create(live, owner, body)
        self.assertEqual(type(result).__name__, "Unknown", result)
        self.assertEqual(self.executor.info.transaction_status, TransactionStatus.IDLE)
        self.assertEqual(self.tables_for(self.root_of(owner, body))["rw_operation"], 1)          # durable: the COMMIT had succeeded

    def test_T_c_an_error_with_no_gateway_code_raised_by_the_commit_itself_is_unknown_even_on_an_idle_connection(self):
        """E11 crafted probe, not product evidence (the product path to the COMMIT is real; only the guard's body is crafted). The owner role
        replaces the body of the deferred deadline guard's trigger function, in this test's disposable database and restored in `finally`, with
        one that raises a CHECK violation whose message carries NO `RW_` code. The guard is the constraint the tail leaves pending, so PostgreSQL
        raises the error WHILE PROCESSING THE COMMIT. The tail reports UNKNOWN (3.1 E4: at or after the commit point only a gateway `RW_` code
        on an IDLE connection is a refusal), the connection is back at IDLE, and no retry happened (one admission). The transaction was in
        fact rolled back by the server, so nothing is addressable, and reconciliation reports UNKNOWN (ABSENT is not proof of rollback)."""
        live, owner = self.fictional_live(), self.new_owner()
        body = self.intent(live)
        function = f"{self.s}.rw_deadline_check()"
        original = self.owner.execute("SELECT pg_get_functiondef(%s::regprocedure)", (function,)).fetchone()[0]
        crafted = original.replace("RAISE EXCEPTION 'RW_DEADLINE'", "RAISE EXCEPTION 'a constraint failed' USING ERRCODE = '23514'").replace(
            "IF rw_reached(clock_timestamp(),NEW.complete_by) THEN", "IF true THEN")
        self.assertNotEqual(crafted, original)
        with self.owner.transaction():
            self.owner.execute(crafted)
        try:
            recorder = RecordingConnection(self.executor)
            result = self.service.create(recorder, owner=owner, body=body, generation=1, link=self.link(live))
            self.assertEqual(type(result).__name__, "Unknown", result)
            self.assertEqual(self.executor.info.transaction_status, TransactionStatus.IDLE)
            self.assertEqual(len(recorder.admits()), 1)                                           # no retry
            self.assertTrue(recorder.set_constraints())                                           # the tail did reach its firing step before the COMMIT
        finally:
            with self.owner.transaction():
                self.owner.execute(original)
        self.assertEqual(self.owner.execute("SELECT pg_get_functiondef(%s::regprocedure)", (function,)).fetchone()[0], original)
        self.assertNothingLeft(self.root_of(owner, body))
        reconciled = self.service.reconcile(owner=owner, body=body, generation=1)
        self.assertEqual((reconciled.status, reconciled.reason), ("UNKNOWN", "ABSENT"))


class ReconciliationTests(R5Case):
    INSTALL = "r5g"

    def committed(self):
        live, owner = self.fictional_live(), self.new_owner()
        created, body = self.create(live, owner)
        self.assertEqual(type(created).__name__, "Created", created)
        return live, owner, created, body

    def test_T_e_partial_or_conflicting_state_is_unknown(self):
        """E11 crafted probe, not product evidence (T-e): the owner role, with the table triggers disabled for this crafted edit, makes the operation row name another revision
        than the artifact's. Reconciliation reports UNKNOWN. A conflicting command digest is UNKNOWN too (product path)."""
        live, owner, created, body = self.committed()
        # conflicting command: the identical operation id with another command digest
        other = real_tails.reconcile(lambda: self.inst.connect("executor"), self.s, owner=owner, root=created.root_id, operation_id=created.operation_id,
                                     command_sha256="2" * 64, context_id=live.ctx, generation=1)
        self.assertEqual((other.status, other.reason), ("UNKNOWN", "RW_IDEMPOTENCY_CONFLICT"))
        with self.owner.transaction():
            self.owner.execute(f"ALTER TABLE {self.s}.rw_operation DISABLE TRIGGER USER")
            try:
                self.owner.execute(f"UPDATE {self.s}.rw_operation SET revision_id=gen_random_uuid() WHERE operation_id=%s", (created.operation_id,))
            finally:
                self.owner.execute(f"ALTER TABLE {self.s}.rw_operation ENABLE TRIGGER USER")
        reconciled = self.service.reconcile(owner=owner, body=body, generation=1)
        self.assertEqual((reconciled.status, reconciled.reason), ("UNKNOWN", "RW_OPERATION_DIFFERS"))

    def test_T_e_a_refused_reconciliation_is_unknown_not_the_refusal_and_after_a_renewal_it_is_committed(self):
        """product path, shared tail on SYNTHETIC_TEST (T-e, 3.1): the reconciliation's own ARCHIVE_READ admission is refused (a completed withdrawal), the result is UNKNOWN and
        not the refusal; after a renewal the same reconciliation, at the new generation, reports COMMITTED."""
        live, owner, created, body = self.committed()
        self.assertEqual(self.tool().withdraw(live.ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER).status, 0)
        refused = self.service.reconcile(owner=owner, body=body, generation=2)
        self.assertEqual((refused.status, refused.reason), ("UNKNOWN", "RW_WITHDRAWN"))
        self.assertEqual(self.renew(live.ctx, 2, valid_until=self.db_now() + dt.timedelta(seconds=120), evidence=self.evidence()).status, 0)
        back = self.service.reconcile(owner=owner, body=body, generation=3)
        self.assertEqual(back.status, "COMMITTED", back)

    def test_reconciliation_reports_committed_with_matching_digests_and_unknown_with_other_digests(self):
        """product path, shared tail on SYNTHETIC_TEST (T-e): bytes match gives committed; a caller that expects other bytes gets UNKNOWN."""
        live, owner, created, body = self.committed()
        match = self.service.reconcile(owner=owner, body=body, generation=1, expected=created.archive)
        self.assertEqual(match.status, "COMMITTED")
        self.assertEqual(match.archive[3], created.archive.issued_sha256)

        class Other:
            issued_sha256, response_sha256 = "3" * 64, created.archive.response_sha256
        differs = self.service.reconcile(owner=owner, body=body, generation=1, expected=Other)
        self.assertEqual((differs.status, differs.reason), ("UNKNOWN", "ARCHIVE_DIFFERS"))


class StalledReadsTests(R5Case):
    INSTALL = "r5h"
    W = 3

    def test_T_g_a_read_a_reproduce_and_a_list_entry_stalled_past_complete_by_are_refused_at_commit_and_deliver_no_value(self):
        """product path, shared tail on SYNTHETIC_TEST (T-g): paused after the last statement and past `complete_by` (timeouts 0), each is refused at COMMIT with RW_DEADLINE and no
        value is delivered. Controls: the same calls without the stall deliver."""
        live, owner = self.fictional_live(), self.new_owner()
        created, _ = self.create(live, owner)
        self.assertEqual(type(created).__name__, "Created", created)

        def stall(tail):
            require_in_transaction(tail.conn)
            time.sleep(self.W + 1.0)
        calls = {
            "read": lambda c: self.service.archive_read(c, owner=owner, root=created.root_id, operation_id=created.operation_id, context_id=live.ctx, generation=1),
            "reproduce": lambda c: self.service.reproduce(c, owner=owner, root=created.root_id, operation_id=created.operation_id, context_id=live.ctx, generation=1),
        }
        for name, run in calls.items():
            self.assertIsInstance(run(self.conn("executor", options=self.stall_options())), real_tails.Done, name)       # control
            with mock.patch.object(real_tails.ReadTail, "_before_commit", stall):
                outcome = run(self.conn("executor", options=self.stall_options()))
            self.assertEqual((type(outcome).__name__, outcome.code), ("Refused", "RW_DEADLINE"), name)
            self.assertFalse(hasattr(outcome, "value"), name)
        with mock.patch.object(real_tails.ReadTail, "_before_commit", stall):                      # the list: the entry's transaction stalls
            listed = self.service.list_roots(self.conn("executor", options=self.stall_options()), owner=owner)
        self.assertIsInstance(listed, real_tails.Done)
        self.assertEqual(listed.value[0]["status"], "RW_DEADLINE")                                # the entry is listed with the code and no stored field
        self.assertEqual(set(listed.value[0]), {"root_id", "context_id", "status"})

    def test_a_read_killed_at_the_seam_is_unknown_and_delivers_nothing(self):
        """product path, shared tail on SYNTHETIC_TEST (T09): a killed connection during a read is UNKNOWN, with no value and no retry."""
        live, owner = self.fictional_live(), self.new_owner()
        created, _ = self.create(live, owner)
        victim = self.conn("executor")
        pid = victim.info.backend_pid

        def kill(tail):
            self.admin.execute("SELECT pg_terminate_backend(%s)", (pid,))
            for _ in range(100):
                if not self.admin.execute("SELECT 1 FROM pg_stat_activity WHERE pid=%s", (pid,)).fetchone():
                    break
                time.sleep(0.05)
        with mock.patch.object(real_tails.ReadTail, "_before_commit", kill):
            outcome = self.service.archive_read(victim, owner=owner, root=created.root_id, operation_id=created.operation_id, context_id=live.ctx, generation=1)
        self.assertEqual(type(outcome).__name__, "Unknown", outcome)
        self.assertFalse(hasattr(outcome, "value"))


class ConcurrencyAndRestartTests(R5Case):
    INSTALL = "r5i"

    def test_two_identical_creates_on_two_connections_commit_once_and_the_other_replays(self):
        """product path, shared tail on SYNTHETIC_TEST (N3-derived): two connections issue the identical command at once. The operation lock serialises them: exactly one operation
        row, one root; the second is the exact replay of the first; no duplicate economic row."""
        from real_gateway_kit import Worker
        live, owner = self.fictional_live(), self.new_owner()
        body = self.intent(live)
        results = []
        workers = [Worker(lambda c=self.conn("executor"): results.append(self.create(live, owner, body, conn=c)[0])) for _ in range(2)]
        for worker in workers:
            worker.join(60)
        self.assertEqual(sorted(type(r).__name__ for r in results), ["Created", "Created"], results)
        self.assertEqual(sorted(r.replayed for r in results), [False, True])
        self.assertEqual(len({r.archive.issued_sha256 for r in results}), 1)
        counts = self.tables_for(self.root_of(owner, body))
        self.assertEqual((counts["rw_operation"], counts["rw_root"], counts["portfolio"], counts["ledger_event"]), (1, 1, 1, 2))

    def test_after_a_restart_the_identical_command_is_the_same_committed_operation(self):
        """product path, shared tail on SYNTHETIC_TEST (N3-derived): a new service object, a new connection and a new process-like state (no memory of the first call)."""
        from real_service.service import RealWorkspaceService
        live, owner = self.fictional_live(), self.new_owner()
        first, body = self.create(live, owner)
        restarted = RealWorkspaceService(self.s, executor_role=self.inst.roles["executor"], connect=lambda: self.inst.connect("executor"))
        again, _ = self.create(live, owner, body, conn=self.conn("executor"), service=restarted)
        self.assertTrue(again.replayed)
        self.assertEqual(again.archive.response_sha256, first.archive.response_sha256)

    def test_a_process_killed_before_the_commit_leaves_nothing_and_the_identical_command_then_commits(self):
        """product path, shared tail on SYNTHETIC_TEST (T09): the backend dies before the COMMIT: UNKNOWN to the caller, nothing durable; the identical command later commits
        once (the caller's decision, not an automatic retry)."""
        live, owner = self.fictional_live(), self.new_owner()
        body = self.intent(live)
        victim = self.conn("executor")
        pid = victim.info.backend_pid

        def kill(tail):
            self.admin.execute("SELECT pg_terminate_backend(%s)", (pid,))
            for _ in range(100):
                if not self.admin.execute("SELECT 1 FROM pg_stat_activity WHERE pid=%s", (pid,)).fetchone():
                    break
                time.sleep(0.05)
        with mock.patch.object(real_tails.CreateTail, "_before_commit", kill):
            first, _ = self.create(live, owner, body, conn=victim)
        self.assertEqual(type(first).__name__, "Unknown")
        self.assertNothingLeft(self.root_of(owner, body))
        second, _ = self.create(live, owner, body, conn=self.conn("executor"))
        self.assertEqual(type(second).__name__, "Created", second)
        self.assertFalse(second.replayed)

    def test_a_service_refusal_inside_the_transaction_rolls_back_everything(self):
        """product path, shared tail on SYNTHETIC_TEST (T09): the fictional service refuses (here: the issuer raises its provisional refusal). Savepoint-level work is not what
        survives: the WHOLE transaction rolls back and nothing is addressable."""
        import financial_service_integration as integration
        live, owner = self.fictional_live(), self.new_owner()
        body = self.intent(live)
        refusal = integration.LocalServiceRefusal("LOCAL_SERVICE_RESULT_REFUSED", None, b"{}")
        with mock.patch.object(integration, "issue_local_service", side_effect=refusal):
            result, _ = self.create(live, owner, body)
        self.assertEqual((type(result).__name__, result.code), ("Refused", "LOCAL_SERVICE_RESULT_REFUSED"))
        self.assertEqual(result.issued_bytes, b"{}")
        self.assertNothingLeft(self.root_of(owner, body))
        self.assertEqual(self.count("rw_root_link", "root_id=%s", (self.root_of(owner, body),)), 0)


class WorldBindingTests(R5Case):
    INSTALL = "r5j"

    def test_FF1_C05_a_changed_digest_of_the_snapshot_fails_before_any_economic_write(self):
        """product path, shared tail on SYNTHETIC_TEST (FF1-C05): for each digest the snapshot holds, a snapshot that differs from the world the product builds is refused with
        RW_WORLD_DIFFERS naming the field, BEFORE any economic statement (no INSERT is issued) and with nothing left."""
        from persistence import real_scope
        from persistence.real_proposal import Member
        from real_service import worlds as real_worlds
        stub = Member("0" * 64, "0" * 64, real_worlds.FICTIONAL_SOURCE, None, "r5.adapter", "1")
        fields = real_worlds.fictional_snapshot_fields([stub], None)
        content = {k: v for k, v in fields.items() if k != "members"}
        for field in ("identity_digest", "calendar_digest", "convention_digest", "profile_digest", "f8b_policy_digest", "projection_digest",
                      "release_digest"):
            with self.subTest(field=field):
                altered = dict(content, **{field: "a" * 64 if content[field] != "a" * 64 else "b" * 64})
                live = self.live("SYNTHETIC_TEST", source_id=real_worlds.FICTIONAL_SOURCE, content=altered, label=field)
                owner = self.new_owner()
                recorder = RecordingConnection(self.conn("executor"))
                body = self.intent(live)
                result = self.service.create(recorder, owner=owner, body=body, generation=1, link=self.link(live))
                self.assertEqual((type(result).__name__, result.code), ("Refused", "RW_WORLD_DIFFERS"), result)
                self.assertEqual(result.detail, field)
                self.assertEqual([s for s in recorder.statements if s.startswith("INSERT")], [])
                self.assertNothingLeft(self.root_of(owner, body))

    def test_FF1_C05_a_changed_source_registry_fails_before_any_economic_write(self):
        """product path, shared tail on SYNTHETIC_TEST (FF1-C05): full-versus-used registry digest."""
        from persistence.real_proposal import Member, SourceRecord
        from real_service import worlds as real_worlds
        stub = Member("0" * 64, "0" * 64, real_worlds.FICTIONAL_SOURCE, None, "r5.adapter", "1")
        fields = real_worlds.fictional_snapshot_fields([stub], None)
        content = {k: v for k, v in fields.items() if k != "members"}
        content["source_records"] = [SourceRecord(real_worlds.FICTIONAL_SOURCE, "another name", "fictional unit", real_worlds.FICTIONAL_SOURCE, None, None)]
        live = self.live("SYNTHETIC_TEST", source_id=real_worlds.FICTIONAL_SOURCE, content=content, label="registry")
        owner = self.new_owner()
        recorder = RecordingConnection(self.conn("executor"))
        result = self.service.create(recorder, owner=owner, body=self.intent(live), generation=1, link=self.link(live))
        self.assertEqual((type(result).__name__, result.code), ("Refused", "RW_WORLD_DIFFERS"), result)
        self.assertEqual(result.detail, "registry.port")
        self.assertEqual([s for s in recorder.statements if s.startswith("INSERT")], [])

    def test_a_listing_the_world_does_not_know_is_refused_and_nothing_is_left(self):
        """product path, shared tail on SYNTHETIC_TEST: the opening position names a listing the invented world has no identity for."""
        live, owner = self.fictional_live(), self.new_owner()
        body = self.intent(live, listing=uuid.uuid4())
        result, _ = self.create(live, owner, body)
        self.assertEqual((type(result).__name__, result.code, result.detail), ("Refused", "RW_WORLD_DIFFERS", "listing"))
        self.assertNothingLeft(self.root_of(owner, body))

    def test_a_date_the_invented_world_does_not_have_is_refused(self):
        """product path, shared tail on SYNTHETIC_TEST: the fictional integration is a one-date profile."""
        live, owner = self.fictional_live(), self.new_owner()
        body = self.intent(live, as_of="2026-01-06")
        result, _ = self.create(live, owner, body)
        self.assertEqual((type(result).__name__, result.code, result.detail), ("Refused", "RW_WORLD_DIFFERS", "as_of"))
        self.assertNothingLeft(self.root_of(owner, body))


class MigrationTriggerTests(R5Case):
    INSTALL = "r5k"

    def test_the_executor_fired_migration_triggers_fire_in_a_create_with_the_installers_revoke_in_place(self):
        """product path, shared tail on SYNTHETIC_TEST (1.2 rule 5.3 (e), technical TR6-L2): the install is made by the product installer, which revokes PUBLIC's EXECUTE on every
        function of the schema. The create writes portfolio, account, ledger_event, rw_root and rw_revision; the migration triggers on those tables
        (those whose function is not a gateway `rw_*` function) are listed from the catalog, PUBLIC holds EXECUTE on none of their functions, and
        the create commits. `benchmark_selection_before_insert` is on a table this create does not write."""
        live, owner = self.fictional_live(), self.new_owner()
        written = ("portfolio", "account", "ledger_event", "rw_root", "rw_revision")
        rows = self.owner.execute(
            "SELECT c.relname,t.tgname,p.proname,t.tgtype,(t.tgconstraint<>0) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname=%s AND NOT t.tgisinternal ORDER BY 1,2",
            (self.s,)).fetchall()
        migration = [(table, name, function, tgtype, deferred) for table, name, function, tgtype, deferred in rows
                     if table in written + ("benchmark_selection",) and not function.startswith("rw_")]
        insert = [m for m in migration if m[3] & 4]                                     # tgtype bit 4: INSERT
        fired = sorted((table, name) for table, name, _f, _t, _d in insert if table in written)
        self.assertEqual(fired, [("ledger_event", "ledger_event_before_insert"), ("ledger_event", "ledger_event_transfer_pairing")])
        self.assertEqual([(t, n) for t, n, *_ in insert if t == "benchmark_selection"], [("benchmark_selection", "benchmark_selection_before_insert")])
        for _table, _name, function, _tgtype, _deferred in insert:
            public = self.owner.execute(
                "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a "
                "WHERE n.nspname=%s AND p.proname=%s AND a.grantee=0 AND a.privilege_type='EXECUTE'", (self.s, function)).fetchone()[0]
            self.assertEqual(public, 0, function)                                        # PUBLIC holds no EXECUTE on the trigger function
        result, _ = self.create(live, owner)
        self.assertEqual(type(result).__name__, "Created", result)                      # the INSERTs fired the BEFORE trigger; the tail fired the deferred one
        seqs = [r[0] for r in self.owner.execute(
            f"SELECT e.ledger_seq FROM {self.s}.ledger_event e JOIN {self.s}.account a USING(account_id) WHERE a.portfolio_id=%s ORDER BY 1", (result.root_id,)).fetchall()]
        self.assertEqual(len(seqs), 2)
        self.assertGreater(seqs[1], seqs[0])
