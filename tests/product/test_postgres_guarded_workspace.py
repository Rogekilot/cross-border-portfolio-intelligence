"""Actual product writer-chain tests on an explicitly supplied fresh fictional DB.

CONFIG is set only by the separately frozen bounded runner; no ambient .env,
database, socket or historic fixture harness fallback is consulted here.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import datetime as dt
from decimal import Decimal
import json
import threading
import time
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from corporate_actions_service.split_confirmation import ConfirmationPolicy
from diversification.contracts import CapitalUniverseChoice
from domain.benchmark_selection import BenchmarkSelection, RecordType
from domain.catalogs import BenchmarkCatalog
from domain.currency import CurrencyCode, Money
from domain.ledger import EventType, LedgerEvent
from financial_service_integration import LocalServiceKind
from persistence import ledger_store, benchmark_selection_store, ledger_replay_store
from persistence.guarded_workspace_context import GuardedWorkspaceError, validate_domain_constraints
from persistence.guarded_workspace_store import (GuardedWorkspaceStore, CommittedWorkspaceResult,
    RefusedWorkspaceResult, UnknownWorkspaceResult, digest, root_id_for)
from persistence.web_account_store import WebAccountStore, AccountStoreError
from web_api.synthetic import SyntheticWorld


CONFIG = None
CASE_EVENTS = []
_OPEN_CONNECTIONS = []
NS = uuid.UUID("f2000000-0000-4000-8000-000000000001")
ALL_RIGHTS = {k: True for k in ("EXECUTE_CREATE", "ARCHIVE_READ", "ARCHIVE_EXPORT", "EXECUTE_REPRODUCE")}


def cleanup():
    """No process/PG control. Runner owns the registered native-session budget."""
    for conn in _OPEN_CONNECTIONS:
        conn.close()
    _OPEN_CONNECTIONS.clear()


class PostgresGuardedWorkspaceTests(unittest.TestCase):
    def conn(self, role):
        conn = CONFIG["connect"](role)
        _OPEN_CONNECTIONS.append(conn)
        self.addCleanup(conn.close)
        return conn

    def setUp(self):
        if CONFIG is None:
            self.skipTest("explicit fresh F2 runtime CONFIG required")
        self.schema = CONFIG["schema"]
        self.app, self.observer, self.issuer = self.conn("executor"), self.conn("owner"), self.conn("issuer")
        self.owner = uuid.uuid5(NS, self.id())
        self.create_op = uuid.uuid5(self.owner, "create")
        self.root = root_id_for(self.owner, self.create_op)
        self.app.execute("INSERT INTO app_user VALUES(%s)", (self.owner,))
        self.world = SyntheticWorld(benchmark_catalog_provider=lambda: BenchmarkCatalog("f2-empty:1", ()))
        policy = ConfirmationPolicy(frozenset(("f2.synthetic.feed",)), frozenset(("f2.synthetic.filing",)))
        capital = CapitalUniverseChoice("FULL_NAV", "SYNTHETIC_CANDIDATE", "F2 actual-world fictional integration only",
            decision_id="f2-integration:1", scope_kind="PORTFOLIO", portfolio_id=str(self.root))
        self.store = WebAccountStore(CONFIG["executor_conninfo"], self.schema,
            clock=lambda: dt.datetime(2026, 1, 3, tzinfo=dt.timezone.utc))
        args = dict(generation=1, policy=policy, capital_policy=capital, preview_key=b"F2_TEST_ONLY_PREVIEW_KEY_32_BYTES!!")
        self.core = GuardedWorkspaceStore(self.store, self.world, context_id="0" * 64, **args)
        snapshot = self.core.source_snapshot()
        self.ctx = digest(snapshot)
        self.core = GuardedWorkspaceStore(self.store, self.world, context_id=self.ctx, **args)
        self.q(self.issuer, "gw_publish", (snapshot,))
        self.rights(ALL_RIGHTS)
        self.body = dict(name="F2 invented actual-world test", reporting_currency="USD",
            positions=[dict(symbol="SYN-A", quantity="2")], cash="20", synthetic_acknowledged=True,
            opening_date="2026-01-01")

    def q(self, conn, fn, params=()):
        return conn.execute(sql.SQL("SELECT * FROM {}.{}(" + ",".join(["%s"] * len(params)) + ")").format(
            sql.Identifier(self.schema), sql.Identifier(fn)), params).fetchone()

    def rights(self, values, generation=1, expiry="NONE"):
        self.q(self.issuer, "gw_set_rights", (self.ctx, generation, Jsonb(values), expiry))
        self.core.generation = generation

    def create(self, **kwargs):
        result = self.core.create(self.owner, self.create_op, self.body, connection=self.app, **kwargs)
        self.assertIsInstance(result, CommittedWorkspaceResult)
        return result

    def count(self, table, where="portfolio_id=%s", params=None):
        return self.observer.execute(sql.SQL("SELECT count(*) FROM {}.{} WHERE " + where).format(
            sql.Identifier(self.schema), sql.Identifier(table)), (self.root,) if params is None else params).fetchone()[0]

    def absent(self):
        for table in ("portfolio", "account", "web_saved_sandbox", "web_portfolio_revision", "web_csv_report", "web_csv_source_key"):
            self.assertEqual(self.count(table), 0, table)
        for table in ("gw_artifact", "gw_operation", "gw_root"):
            self.assertEqual(self.count(table, "root_id=%s"), 0, table)
        self.assertEqual(self.count("ledger_event", "account_id=%s", (uuid.uuid5(self.root, "guest-account"),)), 0)

    def command(self, *, operation="APPEND", expected=None, op=None, amount="5"):
        event = dict(event_type="DEPOSIT", account_id=str(uuid.uuid5(self.root, "guest-account")),
            event_date="2026-01-02", currency="USD", amount=amount, listing_id=None, quantity=None,
            cost_basis=None, bought_amount=None, split_ratio=None, counterparty_account_id=None,
            settlement_date=None, ex_date=None, acquired_on=None)
        return dict(operation_id=str(op or uuid.uuid5(self.owner, "ledger")), expected_revision_id=str(expected or self.root),
            as_of="2026-01-02", operation=operation, events=[event] if operation == "APPEND" else [],
            target_event_ids=[], account_name=None)

    def proposal(self, amount="7"):
        raw = ("key,date,type,currency,amount\nrow-a,2026-01-02,DEPOSIT,USD," + amount + "\n").encode()
        return dict(operation_id=str(uuid.uuid5(self.owner, "csv")), expected_revision_id=str(self.root),
            as_of="2026-01-02", file_base64=base64.b64encode(raw).decode(), filename="invented.csv", kind="TRANSACTIONS",
            source_namespace="f2:" + str(self.root), source_account_key=None, snapshot_key=None, new_account_name=None,
            mapping=dict(source_row_key=0, event_date=1, event_type=2, currency=3, amount=4),
            constants=dict(account_id=str(uuid.uuid5(self.root, "guest-account"))), corrections=[], classifications=[],
            format=dict(delimiter=",", date_format="ISO", decimal_separator=".", thousands_separator=None), synthetic_acknowledged=True)

    def lease(self, op=None, purpose="EXECUTE_CREATE"):
        return self.core._admit(self.app, self.owner, self.root, op or uuid.uuid5(self.owner, "manual"), "1" * 64, purpose)

    def assert_db_refused(self, callable_, text=None):
        with self.assertRaises((psycopg.Error, AccountStoreError, GuardedWorkspaceError,
                                ledger_store.LedgerStoreError, benchmark_selection_store.SelectionStoreError,
                                ledger_replay_store.PortfolioNotFoundError)) as caught:
            callable_()
        if text:
            self.assertIn(text, getattr(caught.exception, "code", str(caught.exception)))

    def test_c01_early_root_create_actual_chain(self):
        source_before = self.core.source_snapshot()
        for invalid in (None, True, 20260101, dt.date(2026, 1, 1), "", "2026-1-01", "2026-01-1",
                        "20260101", "2026-W01-4", "2026-02-30", "2026-01-03", "2026-01-01 "):
            with self.subTest(opening_date=repr(invalid)), self.assertRaises(AccountStoreError) as caught:
                self.store.create_portfolio(str(self.owner), {**self.body, "opening_date": invalid},
                    self.world, connection=self.app, portfolio_id=self.root)
            self.assertEqual((caught.exception.status, caught.exception.code), (422, "INVALID_OPENING_DATE"))
            self.assertEqual(self.app.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)
            self.absent()
        with self.app.transaction():
            provisional = self.core._stage(self.app, owner=self.owner, root=self.root, op=self.create_op,
                kind="CREATE", body=self.body, selector=LocalServiceKind.CP5_DIVERSIFICATION)
            self.assertFalse(hasattr(provisional, "issued_bytes"))
            self.absent()
        self.assertEqual(self.count("portfolio"), 1)
        self.assertEqual(self.count("web_saved_sandbox"), 1)
        self.assertEqual(self.count("gw_operation", "root_id=%s"), 1)
        dates = self.observer.execute("SELECT e.event_date FROM ledger_event e JOIN account a USING(account_id) "
            "WHERE a.portfolio_id=%s ORDER BY e.ledger_seq", (self.root,)).fetchall()
        self.assertEqual(dates, [(dt.date(2026, 1, 1),)] * 2)
        request, snapshot = self.observer.execute("SELECT request_json,snapshot_json FROM web_saved_sandbox WHERE portfolio_id=%s", (self.root,)).fetchone()
        self.assertEqual(json.loads(request)["opening_date"], "2026-01-01")
        self.assertEqual(json.loads(request)["as_of"], "2026-01-02")
        self.assertEqual(json.loads(snapshot)["as_of"], "2026-01-02")
        archive = self.core.archive_read(self.owner, self.root, self.create_op, connection=self.app)
        envelope = json.loads(archive[2])
        self.assertEqual(json.loads(bytes.fromhex(envelope["question_hex"]))["as_of"], "2026-01-02")
        self.assertEqual(self.core.source_snapshot(), source_before)
        self.assertEqual(digest(source_before), self.ctx)

    def test_c02_actual_append_correct_reverse_transfer(self):
        self.create()
        body = self.command()
        duplicate = ledger_store.get_event(self.observer, uuid.uuid5(self.root, "SYN-A")).event
        actual_append = self.core.workspace._append
        def with_duplicate(conn, ident, command, old_events):
            self.assertFalse(ledger_store.append_event(conn, duplicate).created)
            return actual_append(conn, ident, command, old_events)
        with patch.object(self.core.workspace, "_append", side_effect=with_duplicate):
            result = self.core.ledger_command(self.owner, self.root, body, connection=self.app)
        self.assertIsInstance(result, CommittedWorkspaceResult)
        payload = json.loads(result.response_bytes)
        self.assertEqual(payload["workspace"]["ledger"]["current_state"]["accounts"][0]["cash"][0]["amount"], "25")
        event_id = str(uuid.uuid5(uuid.UUID(body["operation_id"]), "event:0"))
        correct = self.command(op=uuid.uuid5(self.owner, "correct"), expected=payload["workspace"]["revision_id"], amount="8")
        correct.update(operation="CORRECT", target_event_ids=[event_id])
        corrected = self.core.ledger_command(self.owner, self.root, correct, connection=self.app)
        self.assertIsInstance(corrected, CommittedWorkspaceResult)
        reverse = self.command(operation="REVERSE", op=uuid.uuid5(self.owner, "reverse"), expected=json.loads(corrected.response_bytes)["workspace"]["revision_id"])
        reverse["target_event_ids"] = [str(uuid.uuid5(uuid.UUID(correct["operation_id"]), "event:0"))]
        reversed_result = self.core.ledger_command(self.owner, self.root, reverse, connection=self.app)
        self.assertIsInstance(reversed_result, CommittedWorkspaceResult)
        add = self.command(operation="ADD_ACCOUNT", op=uuid.uuid5(self.owner, "add-account"), expected=json.loads(reversed_result.response_bytes)["workspace"]["revision_id"])
        add["account_name"] = "Second invented account"
        added = self.core.ledger_command(self.owner, self.root, add, connection=self.app)
        second = str(uuid.uuid5(uuid.UUID(add["operation_id"]), "account"))
        transfer = self.command(op=uuid.uuid5(self.owner, "transfer"), expected=json.loads(added.response_bytes)["workspace"]["revision_id"], amount="3")
        outgoing = {**transfer["events"][0], "event_type": "TRANSFER_OUT", "counterparty_account_id": second}
        incoming = {**outgoing, "event_type": "TRANSFER_IN", "account_id": second, "counterparty_account_id": outgoing["account_id"]}
        transfer["events"] = [outgoing, incoming]
        self.assertIsInstance(self.core.ledger_command(self.owner, self.root, transfer, connection=self.app), CommittedWorkspaceResult)
        current_revision = uuid.uuid5(uuid.UUID(transfer["operation_id"]), "revision")
        preference = dict(operation_id=str(uuid.uuid5(self.owner, "clear-benchmark")), expected_revision_id=str(current_revision),
            as_of="2026-01-02", policies=[], policies_confirmed=True,
            benchmark=dict(action="CLEAR", benchmark_id=None, selected_on="2026-01-02"))
        self.assertIsInstance(self.core.ledger_command(self.owner, self.root, preference, preferences=True, connection=self.app), CommittedWorkspaceResult)
        self.assertEqual(self.count("benchmark_selection"), 1)
        journaled = self.count("gw_journal", "root_id=%s AND table_name='ledger_event'")
        actual = self.observer.execute("SELECT count(*) FROM ledger_event e JOIN account a USING(account_id) WHERE a.portfolio_id=%s", (self.root,)).fetchone()[0]
        self.assertEqual(journaled, actual)  # ON CONFLICT no-op produces no phantom journal.

    def test_c03_actual_csv_preview_commit(self):
        self.create()
        proposal = self.proposal()
        preview = self.core.csv_preview(self.owner, self.root, proposal, connection=self.app)
        self.assertEqual(self.count("web_csv_report"), 0)
        self.assertEqual(self.count("web_portfolio_revision"), 0)
        result = self.core.csv_commit(self.owner, self.root, proposal, preview["preview_receipt"], connection=self.app)
        self.assertIsInstance(result, CommittedWorkspaceResult)
        self.assertEqual(self.count("web_csv_report"), 1)
        self.assertEqual(self.count("web_csv_source_key"), 1)
        self.assertEqual(json.loads(result.response_bytes)["report"]["status"], "COMMITTED")

    def test_c04_csv_and_operation_replay_no_new_connection(self):
        self.create()
        proposal = self.proposal()
        preview = self.core.csv_preview(self.owner, self.root, proposal, connection=self.app)
        first = self.core.csv_commit(self.owner, self.root, proposal, preview["preview_receipt"], connection=self.app)
        with patch.object(self.store, "connect", side_effect=AssertionError("new connection")), patch("persistence.guarded_workspace_store.issue_local_service", side_effect=AssertionError("recomputed")), patch.object(self.core.csv, "commit", side_effect=AssertionError("reparsed")):
            second = self.core.csv_commit(self.owner, self.root, proposal, "0" * 64, connection=self.app)
        self.assertEqual(second, first)
        self.assertEqual(self.count("web_csv_report"), 1)

    def test_c05_changed_command_precedence(self):
        self.create()
        with self.issuer.transaction():
            self.q(self.issuer, "gw_set_rights", (self.ctx, 2, Jsonb(ALL_RIGHTS), "NONE"))
            started = time.monotonic()
            self.assert_db_refused(lambda: self.core.create(self.owner, self.create_op, {**self.body, "name": "different"}, connection=self.app), "F2_IDEMPOTENCY_CONFLICT")
            self.assert_db_refused(lambda: self.core.create(self.owner, self.create_op, {**self.body, "opening_date": "2026-01-02"}, connection=self.app), "F2_IDEMPOTENCY_CONFLICT")
            self.assertLess(time.monotonic() - started, 2)

    def test_c06_actual_typed_performance_refusal(self):
        refused = self.core.create(self.owner, self.create_op, self.body, connection=self.app,
            selector=LocalServiceKind.PERFORMANCE_SYNTHETIC_REFUSAL)
        self.assertIsInstance(refused, RefusedWorkspaceResult)
        self.assertIn(b"SYNTHETIC_MARKET_DATA_REFUSED", refused.issued_bytes)
        self.assertEqual(refused.economic_writes, 0)
        self.absent()

    def test_c07_actual_positive_cp5_service(self):
        result = self.create()
        issued = json.loads(result.issued_bytes)
        self.assertEqual(digest(result.issued_bytes), result.issued_sha256)
        self.assertIn("F8B_DRY_RUN", result.issued_bytes.decode())
        self.assertIn('"synthetic":true', result.issued_bytes.decode())
        snapshot = json.loads(result.response_bytes)
        values = [m for m in snapshot["valuation"]["metrics"] if m["metric_id"] == "portfolio_value" and m["view"] == "REPORTING"]
        self.assertEqual(values[0]["value"], "220")  # SAME shipped SYN-A100, qty2, cash20.
        self.assertTrue(issued)

    def test_c08_archive_failure_rolls_actual_chain_back(self):
        real_query = self.core._query
        def fail(conn, name, params=(), **kwargs):
            if name == "gw_seal":
                raise GuardedWorkspaceError("INJECTED_ARCHIVE_FAILURE")
            return real_query(conn, name, params, **kwargs)
        with patch.object(self.core, "_query", side_effect=fail), self.assertRaises(GuardedWorkspaceError):
            self.create()
        self.absent()
        def corrupt(mode):
            def send(conn, name, params=(), **kwargs):
                if name == "gw_seal":
                    kind, revision, report, issued_b, response_b, envelope_b = params
                    env = json.loads(envelope_b)
                    if mode == "empty-issued":
                        issued_b = b"{}"
                        env["issued_sha256"] = digest(issued_b)
                    elif mode == "omit-owner":
                        del env["owner_id"]
                    elif mode == "wrong-owner":
                        env["owner_id"] = str(uuid.uuid5(self.owner, "wrong"))
                    elif mode == "wrong-revision":
                        revision = uuid.uuid5(self.root, "wrong-revision")
                    elif mode == "wrong-generation":
                        env["generation"] += 1
                    elif mode == "unknown-envelope-field":
                        env["extra"] = True
                    elif mode == "alter-question":
                        question = json.loads(bytes.fromhex(env["question_hex"]))
                        question["ledger_pin"] = "1"
                        from persistence.guarded_workspace_store import encoded
                        qb = encoded(question)
                        env["question_hex"], env["question_sha256"] = qb.hex(), digest(qb)
                    elif mode == "alter-response":
                        from persistence.guarded_workspace_store import encoded
                        response = json.loads(response_b)
                        response["inputs"]["cash"] = "999"
                        response_b = encoded(response)
                        env["response_sha256"] = digest(response_b)
                    from persistence.guarded_workspace_store import encoded
                    params = (kind, revision, report, issued_b, response_b, encoded(env))
                return real_query(conn, name, params, **kwargs)
            return send
        for mode in ("empty-issued", "omit-owner", "wrong-owner", "wrong-revision", "wrong-generation", "unknown-envelope-field", "alter-question", "alter-response"):
            with self.subTest(mode=mode), patch.object(self.core, "_query", side_effect=corrupt(mode)):
                self.assert_db_refused(lambda: self.core.create(self.owner, self.create_op, self.body, connection=self.app))
                self.absent()

    def test_c09_caller_savepoint_is_not_outer_commit(self):
        with self.app.transaction():
            with self.assertRaises(GuardedWorkspaceError):
                self.core.create(self.owner, self.create_op, self.body, connection=self.app)
            self.core._stage(self.app, owner=self.owner, root=self.root, op=self.create_op,
                kind="CREATE", body=self.body, selector=LocalServiceKind.CP5_DIVERSIFICATION)
            self.absent()
            raise psycopg.Rollback()
        self.absent()

    def test_c10_executor_first_revoker_waits(self):
        self.create()
        revoker = self.conn("issuer")
        ready = threading.Event()
        done = threading.Event()
        errors = []
        def revoke():
            try:
                ready.set()
                self.q(revoker, "gw_set_rights", (self.ctx, 2, Jsonb({**ALL_RIGHTS, "EXECUTE_CREATE": False}), "NONE"))
            except BaseException as error:
                errors.append(error)
            finally:
                done.set()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.app.transaction():
                scope = self.lease(purpose="ARCHIVE_READ")
                future = pool.submit(revoke)
                self.assertTrue(ready.wait(1))
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    blocking = self.observer.execute("SELECT pg_blocking_pids(%s)", (revoker.info.backend_pid,)).fetchone()[0]
                    if scope.backend_pid in blocking:
                        break
                else:
                    self.fail("owned revoker blocker not observed")
                self.assertFalse(done.is_set())
                CASE_EVENTS.append(dict(case="C10", executor=scope.backend_pid, revoker=revoker.info.backend_pid, observed_blockers=blocking))
            future.result(timeout=4)
        self.assertFalse(errors)
        self.assertTrue(done.is_set())

    def test_c11_revoker_first_no_economic_io(self):
        self.rights({**ALL_RIGHTS, "EXECUTE_CREATE": False}, 2)
        with patch.object(self.world, "create", side_effect=AssertionError("financial io")):
            self.assert_db_refused(lambda: self.core.create(self.owner, self.create_op, self.body, connection=self.app), "F2_RIGHT_REFUSED")
        self.absent()

    def test_c12_legacy_and_direct_writer_fence(self):
        self.create()
        legacy = self.conn("legacy")
        event = LedgerEvent(uuid.uuid5(self.owner, "bypass"), uuid.uuid5(self.root, "guest-account"), EventType.DEPOSIT,
            self.world.as_of, CurrencyCode("USD"), amount=Money(Decimal("9"), CurrencyCode("USD")))
        self.assert_db_refused(lambda: ledger_store.append_event(legacy, event))
        self.assert_db_refused(lambda: ledger_store.append_batch(legacy, [event]))
        system = replace(event, source_reference="finweb.f8b/1:f2-invented-proof")
        self.assert_db_refused(lambda: ledger_store.append_system_event(legacy, system, namespace="finweb.f8b/1"))
        target = ledger_store.get_event(self.observer, uuid.uuid5(self.root, "cash")).event
        reversal = LedgerEvent(event_id=uuid.uuid5(self.owner, "bypass-reversal"), account_id=target.account_id,
            event_type=EventType.REVERSAL, event_date=self.world.as_of, currency=target.currency, reverses_event_id=target.event_id)
        replacement = replace(target, event_id=uuid.uuid5(self.owner, "bypass-replacement"), corrects_event_id=target.event_id,
            amount=Money(Decimal("30"), target.currency), source_reference=None)
        self.assert_db_refused(lambda: ledger_store.append_correction(legacy, reversal, replacement))
        selection = BenchmarkSelection(selection_id=uuid.uuid5(self.owner, "bypass-selection"), portfolio_id=self.root,
            record_type=RecordType.CLEAR, selected_on=self.world.as_of)
        self.assert_db_refused(lambda: benchmark_selection_store.append_selection(legacy, selection, catalog=BenchmarkCatalog("f2-empty:1", ())))
        self.assert_db_refused(lambda: legacy.execute("INSERT INTO account VALUES(%s,%s,%s)", (uuid.uuid5(self.owner, "bad-account"), self.root, "bad")))
        self.assert_db_refused(lambda: self.core.workspace.workspace(str(self.owner), str(self.root), connection=legacy))
        self.assert_db_refused(lambda: self.core.workspace.command(str(self.owner), str(self.root), self.command(), connection=legacy))
        self.assert_db_refused(lambda: self.core.csv.commit(str(self.owner), str(self.root), self.proposal(), "0" * 64, connection=legacy))
        self.assertEqual(self.count("web_portfolio_revision"), 0)

    def test_c13_partial_and_unsealed_commit(self):
        self.create()
        before = self.count("account")
        def partial():
            with self.app.transaction():
                self.lease()
                self.app.execute("INSERT INTO account VALUES(%s,%s,%s)", (uuid.uuid5(self.owner, "partial"), self.root, "partial"))
        self.assert_db_refused(partial, "F2_UNSEALED")
        self.assertEqual(self.count("account"), before)

    def test_c14_manual_constraints_cannot_bypass(self):
        self.create()
        with self.app.transaction():
            scope = self.lease()
            validate_domain_constraints(self.app, scope)
            with self.assertRaises(psycopg.Error):
                with self.app.transaction():
                    self.app.execute("SET CONSTRAINTS ALL IMMEDIATE")
            raise psycopg.Rollback()
        body = self.command()
        with self.app.transaction():
            self.core._stage(self.app, owner=self.owner, root=self.root, op=uuid.UUID(body["operation_id"]), kind="LEDGER", body=body, selector=LocalServiceKind.CP5_DIVERSIFICATION)
            self.app.execute("SET CONSTRAINTS ALL DEFERRED")
            with self.assertRaises(psycopg.Error):
                with self.app.transaction():
                    self.app.execute("INSERT INTO account VALUES(%s,%s,%s)", (uuid.uuid5(self.owner, "afterseal"), self.root, "post-seal"))
        self.assertEqual(self.count("account"), 1)

    def test_c15_archive_current_rights(self):
        result = self.create()
        self.assertEqual(self.core.archive_read(self.owner, self.root, self.create_op, connection=self.app)[0], result.issued_bytes)
        self.rights({**ALL_RIGHTS, "ARCHIVE_READ": False}, 2)
        self.assert_db_refused(lambda: self.core.archive_read(self.owner, self.root, self.create_op, connection=self.app), "F2_RIGHT_REFUSED")
        self.assertEqual(self.app.execute("SELECT count(*) FROM ledger_event WHERE account_id=%s", (uuid.uuid5(self.root, "guest-account"),)).fetchone()[0], 0)

    def test_c16_owner_idor_and_hidden_account(self):
        self.create()
        foreign = uuid.uuid5(self.owner, "foreign")
        self.assert_db_refused(lambda: self.core.archive_read(foreign, self.root, self.create_op, connection=self.app), "F2_NOT_FOUND")
        self.assertEqual(self.app.execute("SELECT account_id FROM account WHERE portfolio_id=%s", (self.root,)).fetchall(), [])
        self.assert_db_refused(lambda: self.app.execute("INSERT INTO ledger_event(event_id,account_id,event_type,event_date,currency,amount,source_reference) VALUES(%s,%s,'DEPOSIT','2026-01-02','USD',1,'hidden-bypass')", (uuid.uuid5(self.owner, "hidden"), uuid.uuid5(self.root, "guest-account"))))

    def test_c17_role_definer_temp_ddl(self):
        self.create()
        flags = self.app.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
        self.assertEqual(flags, (False, False))
        for statement in ("UPDATE gw_head SET generation=generation+1", "DELETE FROM gw_journal", "INSERT INTO gw_lease(backend_pid) VALUES(1)", "TRUNCATE ledger_event", "ALTER TABLE ledger_event DISABLE TRIGGER ALL", "CREATE TEMP TABLE gw_head(x int)"):
            self.assert_db_refused(lambda s=statement: self.app.execute(s))
        for role in (CONFIG["owner_role"], CONFIG["issuer_role"]):
            self.assert_db_refused(lambda r=role: self.app.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(r))))

    def test_c18_distinct_retry_read_export_reproduce(self):
        saved = self.create()
        self.rights({**ALL_RIGHTS, "EXECUTE_CREATE": False}, 2)
        self.assert_db_refused(lambda: self.core.create(self.owner, self.create_op, self.body, connection=self.app), "F2_RIGHT_REFUSED")
        self.assertEqual(self.core.archive_read(self.owner, self.root, self.create_op, connection=self.app)[0], saved.issued_bytes)
        self.assertEqual(self.core.archive_export(self.owner, self.root, self.create_op, connection=self.app)[0], saved.issued_bytes)
        reproduction = self.core.reproduce(self.owner, self.root, self.create_op, connection=self.app)
        self.assertEqual(reproduction.status, "REPRODUCED")
        self.assertEqual(reproduction.issued_sha256, saved.issued_sha256)
        self.rights({**ALL_RIGHTS, "ARCHIVE_READ": False}, 3)
        for call in (self.core.archive_export, self.core.reproduce):
            self.assert_db_refused(lambda c=call: c(self.owner, self.root, self.create_op, connection=self.app), "F2_RIGHT_REFUSED")

    def test_c19_actual_service_context_mismatch(self):
        self.create()
        with self.app.transaction():
            scope = self.lease(purpose="ARCHIVE_READ")
            scope.assert_current(self.app)
            with self.assertRaises(GuardedWorkspaceError):
                scope.assert_current(self.observer)
            with self.assertRaises(psycopg.Error):
                with self.app.transaction():
                    self.core._admit(self.app, self.owner, uuid.uuid5(self.root, "other"), uuid.uuid5(self.owner, "other-op"), "2" * 64, "ARCHIVE_READ")
        with self.app.transaction(), self.assertRaises(GuardedWorkspaceError):
            scope.assert_current(self.app)

    def test_c20_honest_unknown_commit_and_disconnect(self):
        with patch.object(self.core, "_after_commit_ack", side_effect=psycopg.OperationalError("injected after actual commit ACK loss")):
            lost = self.core.create(self.owner, self.create_op, self.body, connection=self.app)
        self.assertIsInstance(lost, UnknownWorkspaceResult)
        self.assertEqual(self.count("gw_operation", "root_id=%s"), 1)
        unknown = self.core.reconcile(self.owner, self.root, uuid.uuid5(self.owner, "absent"), connection=self.app)
        self.assertIsInstance(unknown, UnknownWorkspaceResult)
        actual = self.core.reconcile(self.owner, self.root, self.create_op, connection=self.app)
        self.assertTrue(actual[0])
        connection = self.conn("executor")
        connection.execute("BEGIN")
        self.core._admit(connection, self.owner, self.root, uuid.uuid5(self.owner, "disconnect"), "3" * 64, "EXECUTE_CREATE")
        connection.execute("INSERT INTO account VALUES(%s,%s,'disconnect')", (uuid.uuid5(self.owner, "disconnected-account"), self.root))
        connection.close()
        self.assertEqual(self.count("account"), 1)
        # Absence alone is not promoted to confirmed rollback by the public API.
        self.assertIsInstance(self.core.reconcile(self.owner, self.root, uuid.uuid5(self.owner, "disconnect"), connection=self.app), UnknownWorkspaceResult)

    def test_c21_selected_old_revision_and_report_integrity(self):
        original = self.create()
        result = self.core.ledger_command(self.owner, self.root, self.command(), connection=self.app)
        self.assertIsInstance(result, CommittedWorkspaceResult)
        self.assertEqual(self.core.archive_read(self.owner, self.root, self.create_op, connection=self.app)[0], original.issued_bytes)
        self.assertEqual(self.count("web_portfolio_revision"), 1)

    def test_c22_closed_real_and_unprotected_compatibility(self):
        self.create()
        default_body = {key: value for key, value in self.body.items() if key != "opening_date"}
        control = self.store.create_portfolio(str(self.owner), default_body, self.world, connection=self.app,
            portfolio_id=uuid.uuid5(self.owner, "default-opening-control"))
        control_root = uuid.UUID(control.snapshot()["portfolio_id"])
        self.assertNotEqual(control_root, self.root)
        self.assertTrue(self.core.workspace.workspace(str(self.owner), str(control_root), connection=self.app))
        self.assertFalse(self.core.workspace.store is None)
        dates = self.observer.execute("SELECT e.event_date FROM ledger_event e JOIN account a USING(account_id) "
            "WHERE a.portfolio_id=%s ORDER BY e.ledger_seq", (control_root,)).fetchall()
        self.assertEqual(dates, [(dt.date(2026, 1, 2),)] * 2)
        request = self.observer.execute("SELECT request_json FROM web_saved_sandbox WHERE portfolio_id=%s", (control_root,)).fetchone()[0]
        self.assertNotIn("opening_date", json.loads(request))
        command = self.command(expected=control_root, op=uuid.uuid5(control_root, "same-day-refused"))
        command["events"][0]["account_id"] = str(uuid.uuid5(control_root, "guest-account"))
        with self.assertRaises(AccountStoreError) as caught:
            self.core.workspace.command(str(self.owner), str(control_root), command, connection=self.app)
        self.assertEqual((caught.exception.status, caught.exception.code), (422, "WORKSPACE_COMMAND_REFUSED"))
        self.assertIn("ledger_event_after_snapshot_date", caught.exception.detail)
        after_dates = self.observer.execute("SELECT e.event_date FROM ledger_event e JOIN account a USING(account_id) "
            "WHERE a.portfolio_id=%s ORDER BY e.ledger_seq", (control_root,)).fetchall()
        self.assertEqual(after_dates, dates)
        self.assertEqual(self.count("web_portfolio_revision", params=(control_root,)), 0)
        self.assertEqual(self.core.workspace.read(str(self.owner), str(control_root), connection=self.app).snapshot_json, control.snapshot_json)
        equal_root = uuid.uuid5(self.owner, "equal-opening-control")
        self.store.create_portfolio(str(self.owner), {**default_body, "opening_date": "2026-01-02"},
            self.world, connection=self.app, portfolio_id=equal_root)
        equal_dates = self.observer.execute("SELECT e.event_date FROM ledger_event e JOIN account a USING(account_id) "
            "WHERE a.portfolio_id=%s ORDER BY e.ledger_seq", (equal_root,)).fetchall()
        self.assertEqual(equal_dates, dates)

    def test_c23_real_connection_durability(self):
        saved = self.create()
        reopened = self.conn("executor")
        loaded = self.core.archive_read(self.owner, self.root, self.create_op, connection=reopened)
        self.assertEqual(loaded[0], saved.issued_bytes)
        self.assertEqual(loaded[1], saved.response_bytes)
        self.rights({**ALL_RIGHTS, "EXECUTE_CREATE": False}, 2)
        self.assert_db_refused(lambda: self.core.create(self.owner, self.create_op, self.body, connection=reopened), "F2_RIGHT_REFUSED")

    def test_c24_finite_unknown_and_resource_refusal(self):
        self.rights(ALL_RIGHTS, 2, "FINITE")
        self.assert_db_refused(lambda: self.core.create(self.owner, self.create_op, self.body, connection=self.app), "F2_EXPIRY_HOLD")
        self.rights(ALL_RIGHTS, 3, "UNKNOWN")
        self.assert_db_refused(lambda: self.core.create(self.owner, self.create_op, self.body, connection=self.app), "F2_EXPIRY_HOLD")
        self.rights(ALL_RIGHTS, 4)
        with self.assertRaises(GuardedWorkspaceError) as caught:
            self.core.create(self.owner, self.create_op, {**self.body, "name": "x" * 65536}, connection=self.app)
        self.assertEqual(caught.exception.code, "F2_COMMAND_CAP")
        with self.app.transaction():
            self.core._admit(self.app, self.owner, self.root, self.create_op, "1" * 64, "EXECUTE_CREATE", new_root=True)
            with self.assertRaises(psycopg.Error):
                with self.app.transaction():
                    self.q(self.app, "gw_seal", ("CREATE", self.root, None, b" " * 2000001, b"{}", b"{}"))
            raise psycopg.Rollback()
        self.absent()
        # Trusted owner fixture: metadata-only occupied saved slots, deliberately
        # NOT thirty-two financial-service executions or valid issued archives.
        with self.observer.transaction():
            for index in range(32):
                seeded = uuid.uuid5(self.owner, "capacity-metadata-only:" + str(index))
                self.observer.execute("INSERT INTO portfolio VALUES(%s,%s,'USD')", (seeded, self.owner))
                self.observer.execute("INSERT INTO web_saved_sandbox VALUES(%s,'LOCAL_SYNTHETIC_ACCOUNT','metadata-only cap seed','{}','{}',%s,1,%s)",
                    (seeded, digest(b"{}"), self.store.clock()))
                self.observer.execute("INSERT INTO gw_root VALUES(%s,%s,%s)", (seeded, self.owner, self.ctx))
        self.assertEqual(self.app.execute("SELECT count(*) FROM web_saved_sandbox s JOIN portfolio p USING(portfolio_id) WHERE p.user_id=%s", (self.owner,)).fetchone()[0], 0)
        tables = ("portfolio", "account", "ledger_event", "web_saved_sandbox", "web_portfolio_revision",
            "web_csv_report", "web_csv_source_key", "gw_root", "gw_lease", "gw_journal", "gw_artifact", "gw_operation")
        def totals():
            return {name: self.observer.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(self.schema), sql.Identifier(name))).fetchone()[0] for name in tables}
        before = totals()
        self.assertEqual(self.count("portfolio", "user_id=%s", (self.owner,)), 32)
        for branch in ("guarded", "default"):
            with self.subTest(branch=branch), self.assertRaises(AccountStoreError) as caught:
                if branch == "guarded":
                    self.core.create(self.owner, self.create_op, self.body, connection=self.app)
                else:
                    self.store.create_portfolio(str(self.owner), self.body, self.world, connection=self.app)
            self.assertEqual((caught.exception.status, caught.exception.code), (429, "PORTFOLIO_CAPACITY_REACHED"))
            self.assertEqual(totals(), before)
            self.absent()
        CASE_EVENTS.append(dict(case="C24", fixture="TRUSTED_METADATA_ONLY_NOT_32_FINANCIAL_PROOFS", seeded_saved_roots=32,
            guarded_33rd="REFUSED_429_WHOLE_ROLLBACK", default_33rd="REFUSED_429_WHOLE_ROLLBACK"))
