"""Local fictional integration of the actual canonical stores and financial service.

No routes, automatic installation, real source provider or retry is installed.
Only commit-owning methods return committed bytes. PostgreSQL is the authority.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
import datetime as dt
import hashlib
import json
from pathlib import Path
import uuid

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from financial_service_integration import (LocalFictionalContext, LocalServiceKind,
    LocalServiceRequest, LocalServiceRefusal, fingerprint_context_inputs,
    issue_local_service, reproduce_local_service)
from marketdata.canonical import canonical_json
from persistence import ledger_replay_store
from persistence.guarded_workspace_context import (GuardedWorkspaceError,
    _scope_from_database, identifier, require_idle, transaction_identity)
from persistence.web_csv_store import CsvImportStore
from persistence.web_workspace_store import WorkspaceStore


TARGETS = ("portfolio", "account", "ledger_event", "benchmark_selection", "web_saved_sandbox",
           "web_portfolio_revision", "web_csv_report", "web_csv_source_key")
RIGHTS = ("EXECUTE_CREATE", "ARCHIVE_READ", "ARCHIVE_EXPORT", "EXECUTE_REPRODUCE")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return canonical_json(value).encode("utf8")


def root_id_for(owner_id, operation_id):
    if type(owner_id) is not uuid.UUID or type(operation_id) is not uuid.UUID:
        raise GuardedWorkspaceError("F2_SHAPE")
    return uuid.uuid5(owner_id, "finweb.f2.fictional:" + str(operation_id))


def install_guarded_workspace(conn, *, schema, owner_role, executor_role, issuer_role, legacy_role):
    """Explicit installer after real old migrations, fresh fictional DB only.

    No role creation, migration history edit, ownership transfer, or real DB
    discovery. Operator provisions the exact roles and schema separately.
    """
    names = [identifier(x) for x in (schema, owner_role, executor_role, issuer_role, legacy_role)]
    if len(set(names[1:])) != 4:
        raise GuardedWorkspaceError("F2_ROLE_DIFFERS")
    require_idle(conn)
    with conn.transaction():
        roles = conn.execute("SELECT rolname,rolsuper,rolbypassrls,rolcanlogin FROM pg_roles WHERE rolname=ANY(%s)", (names[1:],)).fetchall()
        by_name = {r[0]: r[1:] for r in roles}
        if len(by_name) != 4 or any(by_name[n][:2] != (False, False) for n in names[1:]) or by_name[owner_role][2]:
            raise GuardedWorkspaceError("F2_ROLE_DIFFERS", "Exact non-superuser/non-BYPASSRLS roles and NOLOGIN owner required")
        current = conn.execute("SELECT current_user,n.nspowner::regrole::text FROM pg_namespace n WHERE n.nspname=%s", (schema,)).fetchone()
        if current != (owner_role, owner_role):
            raise GuardedWorkspaceError("F2_INSTALL_OWNER_DIFFERS")
        for role in names[1:]:
            for other in names[1:]:
                if role != other and conn.execute("SELECT pg_has_role(%s,%s,'MEMBER')", (role, other)).fetchone()[0]:
                    raise GuardedWorkspaceError("F2_ROLE_DIFFERS")
        for table in TARGETS:
            row = conn.execute("SELECT c.relowner::regrole::text,c.relrowsecurity,c.relforcerowsecurity,"
                "(SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname=%s AND c.relname=%s", (schema, table)).fetchone()
            if row != (owner_role, False, False, 0):
                raise GuardedWorkspaceError("F2_EXISTING_POLICY_OR_OWNER")
        if conn.execute("SELECT to_regclass(%s)", (schema + ".gw_mode",)).fetchone()[0] is not None:
            raise GuardedWorkspaceError("F2_ALREADY_INSTALLED")
        body = Path(__file__).with_name("guarded_workspace_v1.sql").read_text("utf8")
        for marker, name in zip(("__GW_SCHEMA__", "__GW_EXECUTOR__", "__GW_ISSUER__", "__GW_LEGACY__"),
                                (schema, executor_role, issuer_role, legacy_role)):
            body = body.replace(marker, name)
        conn.execute(body)


@dataclass(frozen=True)
class CommittedWorkspaceResult:
    root_id: uuid.UUID
    operation_id: uuid.UUID
    response_bytes: bytes
    response_sha256: str
    issued_bytes: bytes
    issued_sha256: str
    persisted: bool = field(default=True, init=False)
    synthetic: bool = field(default=True, init=False)


@dataclass(frozen=True)
class RefusedWorkspaceResult:
    code: str
    issued_bytes: bytes
    persisted: bool = field(default=False, init=False)
    economic_writes: int = field(default=0, init=False)


@dataclass(frozen=True)
class UnknownWorkspaceResult:
    operation_id: uuid.UUID
    disposition: str = field(default="UNKNOWN", init=False)


class _Provisional:
    """Opaque internal staging marker. No numeric/issued/public success fields."""
    __slots__ = ("__scope",)

    def __init__(self, scope):
        self.__scope = scope


class GuardedWorkspaceStore:
    def __init__(self, store, world, *, context_id, generation, policy, capital_policy,
                 preview_key, metadata=None, coverage=(), request=None, frequency=None):
        if type(context_id) is not str or len(context_id) != 64 or any(c not in "0123456789abcdef" for c in context_id):
            raise GuardedWorkspaceError("F2_SHAPE")
        if type(generation) is not int or not 1 <= generation < 2**63 or type(preview_key) is not bytes or len(preview_key) < 32:
            raise GuardedWorkspaceError("F2_SHAPE")
        self.store, self.world = store, world
        self.schema = identifier(store.schema)
        self.context_id, self.generation = context_id, generation
        self.policy, self.capital_policy, self.metadata = policy, capital_policy, metadata
        self.coverage, self.request, self.frequency = tuple(coverage), request, frequency
        self.workspace = WorkspaceStore(store, world)
        self.csv = CsvImportStore(store, world, preview_key)

    def source_snapshot(self):
        kw = dict(port=self.world.port, resolver=self.world.resolver,
            market_conventions=self.world.conventions, conventions=self.world.perf,
            policy=self.policy, as_of=self.world.as_of, reporting_currency="USD",
            metadata=self.metadata, coverage=self.coverage, capital_policy=self.capital_policy,
            request=self.request)
        if self.frequency is not None:
            kw["frequency"] = self.frequency
        return fingerprint_context_inputs(**kw)

    def _query(self, conn, name, params=(), *, columns="*"):
        if columns != "*":
            raise GuardedWorkspaceError("F2_SHAPE")
        return conn.execute(sql.SQL("SELECT " + columns + " FROM {}.{}(" + ",".join(["%s"] * len(params)) + ")").format(
            sql.Identifier(self.schema), sql.Identifier(name)), params)

    def _admit(self, conn, owner, root, op, command_sha, purpose, *, new_root=False):
        snapshot = bytes(self._query(conn, "gw_admit", (owner, root, self.context_id, self.generation,
            purpose, op, command_sha, new_root)).fetchone()[0])
        scope = _scope_from_database(conn, self.schema, snapshot)
        if digest(snapshot) != self.context_id:
            raise GuardedWorkspaceError("F2_CONTEXT_DIFFERS")
        return scope

    def _service_context(self, conn, scope):
        scope.assert_current(conn)
        if scope.snapshot_bytes != self.source_snapshot():
            raise GuardedWorkspaceError("F2_CONTEXT_DIFFERS")
        kw = dict(connection=conn, backend_pid=scope.backend_pid, transaction_id=scope.transaction_id,
            context_id=scope.context_id, generation=scope.generation, snapshot_bytes=scope.snapshot_bytes,
            port=self.world.port, resolver=self.world.resolver, market_conventions=self.world.conventions,
            conventions=self.world.perf, policy=self.policy, as_of=self.world.as_of, reporting_currency="USD",
            metadata=self.metadata, coverage=self.coverage, capital_policy=self.capital_policy, request=self.request)
        if self.frequency is not None:
            kw["frequency"] = self.frequency
        return LocalFictionalContext(**kw)

    @staticmethod
    def _identity(owner, root, op):
        if any(type(x) is not uuid.UUID for x in (owner, root, op)):
            raise GuardedWorkspaceError("F2_SHAPE")

    def _command(self, owner, root, op, kind, body, selector, receipt):
        self._identity(owner, root, op)
        if type(body) is not dict or type(selector) is not LocalServiceKind or kind not in ("CREATE", "LEDGER", "PREFERENCES", "CSV"):
            raise GuardedWorkspaceError("F2_SHAPE")
        if kind != "CREATE" and body.get("as_of") != self.world.as_of.isoformat():
            raise GuardedWorkspaceError("F2_ONE_DATE_PROFILE")
        data = encoded(dict(schema="finweb.f2.fictional-command/1", owner_id=str(owner), root_id=str(root),
            operation_id=str(op), kind=kind, selector=selector.value, body=body))
        if len(data) > 65536:
            raise GuardedWorkspaceError("F2_COMMAND_CAP")
        # Preview receipt is intentionally not identity: process restart must not
        # change an already committed immutable operation's canonical content.
        return digest(data)

    def _archive(self, conn, owner, op):
        row = self._query(conn, "gw_archive", (owner, op)).fetchone()
        if row is None:
            raise GuardedWorkspaceError("F2_NOT_FOUND")
        issued, response, envelope = (bytes(x) for x in row[:3])
        if digest(issued) != row[3] or digest(response) != row[4]:
            raise GuardedWorkspaceError("F2_ARCHIVE_DIFFERS")
        return issued, response, envelope, row[5], row[6]

    def _stage(self, conn, *, owner, root, op, kind, body, selector, receipt=None):
        transaction_identity(conn)  # requires an actual outer transaction
        command_sha = self._command(owner, root, op, kind, body, selector, receipt)
        self._query(conn, "gw_precheck", (owner, op, command_sha)).fetchone()
        if kind != "CREATE" and self._query(conn, "gw_root_metadata", (owner, root)).fetchone() is None:
            raise GuardedWorkspaceError("F2_NOT_FOUND")
        scope = self._admit(conn, owner, root, op, command_sha, "EXECUTE_CREATE", new_root=kind == "CREATE")
        # Recheck under the database-minted operation lock; a concurrent winner
        # may have committed after the readonly precheck.
        existing = self._query(conn, "gw_precheck", (owner, op, command_sha)).fetchone()
        if existing is not None:
            self._archive(conn, owner, op)
            return _Provisional(scope)
        if scope.snapshot_bytes != self.source_snapshot():
            raise GuardedWorkspaceError("F2_CONTEXT_DIFFERS")
        if kind == "CREATE":
            item = self.store.create_portfolio(str(owner), body, self.world, connection=conn, portfolio_id=root)
            response = item.snapshot()
            revision = root
            report = None
        elif kind in ("LEDGER", "PREFERENCES"):
            response = self.workspace.command(str(owner), str(root), body, preferences=kind == "PREFERENCES",
                connection=conn, execution_scope=scope)
            revision = uuid.UUID(response["workspace"]["revision_id"])
            report = None
        else:
            response = self.csv.commit(str(owner), str(root), body, receipt, connection=conn, execution_scope=scope)
            if response["report"]["status"] != "COMMITTED" or response["workspace_result"] is None:
                raise GuardedWorkspaceError("F2_CSV_NOT_COMMITTED")
            revision = uuid.UUID(response["report"]["revision_id"])
            report = uuid.UUID(response["report"]["report_id"])
        scope.assert_current(conn)
        pin = ledger_replay_store.current_ledger_version(conn, root)
        request = LocalServiceRequest(selector=selector, owner_id=owner, root_id=root, revision_id=revision,
            operation_id=op, portfolio_id=root, ledger_pin=pin, as_of=self.world.as_of,
            context_id=scope.context_id, generation=scope.generation)
        result = issue_local_service(conn, request=request, context=self._service_context(conn, scope))
        response_b = encoded(response)
        envelope = encoded(dict(schema="finweb.f2.fictional-issued-envelope/1", synthetic=True,
            actual_executor="local_application", approval_scope="fictional_local_only", owner_id=str(owner),
            root_id=str(root), operation_id=str(op), revision_id=str(revision), ledger_pin=pin, context_id=scope.context_id,
            generation=scope.generation, issued_sha256=result.issued_sha256,
            response_sha256=digest(response_b), family=result.family, engine_id=result.engine_id,
            manifest_id=result.manifest_id, result_digest=result.result_digest,
            question_sha256=result.question_sha256, binding_sha256=result.binding_sha256,
            question_hex=result.question_bytes.hex(), binding_hex=result.binding_bytes.hex(),
            selector=selector.value, fixture_quotes_sha256=self.world.input_sha256,
            fixture_calendar_sha256=self.world.calendar_sha256))
        self._query(conn, "gw_seal", (kind, revision, report, result.issued_bytes, response_b, envelope)).fetchone()
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return _Provisional(scope)

    def execute(self, owner, root, op, kind, body, *, selector=LocalServiceKind.CP5_DIVERSIFICATION,
                receipt=None, connection=None):
        context = self.store.connect() if connection is None else nullcontext(connection)
        with context as conn:
            require_idle(conn)
            staged = None
            try:
                with conn.transaction():
                    self._stage(conn, owner=owner, root=root, op=op, kind=kind, body=body,
                                selector=selector, receipt=receipt)
                    staged = self._archive(conn, owner, op)
                self._after_commit_ack(conn)
            except LocalServiceRefusal as error:
                if conn.info.transaction_status != TransactionStatus.IDLE:
                    return UnknownWorkspaceResult(op)
                if type(error.issued_bytes) is not bytes:
                    raise GuardedWorkspaceError("F2_REFUSAL_WITHOUT_ISSUED_BYTES") from error
                return RefusedWorkspaceResult(error.code, error.issued_bytes)
            except (psycopg.OperationalError, psycopg.InterfaceError):
                return UnknownWorkspaceResult(op)
            if conn.info.transaction_status != TransactionStatus.IDLE or staged is None:
                return UnknownWorkspaceResult(op)
            issued, response = staged[:2]
            return CommittedWorkspaceResult(root, op, response, digest(response), issued, digest(issued))

    @staticmethod
    def _after_commit_ack(conn):
        """Private injection seam for post-commit ACK-loss evidence, no retry."""
        require_idle(conn)

    def create(self, owner, op, body, **kwargs):
        return self.execute(owner, root_id_for(owner, op), op, "CREATE", body, **kwargs)

    def ledger_command(self, owner, root, body, *, preferences=False, **kwargs):
        if kwargs.get("connection") is not None:
            require_idle(kwargs["connection"])
        return self.execute(owner, root, uuid.UUID(body["operation_id"]), "PREFERENCES" if preferences else "LEDGER", body, **kwargs)

    def csv_commit(self, owner, root, proposal, receipt, **kwargs):
        if kwargs.get("connection") is not None:
            require_idle(kwargs["connection"])
        return self.execute(owner, root, uuid.UUID(proposal["operation_id"]), "CSV", proposal, receipt=receipt, **kwargs)

    def csv_preview(self, owner, root, proposal, *, connection=None):
        if connection is not None:
            require_idle(connection)
        op = uuid.UUID(proposal["operation_id"])
        command_sha = self._command(owner, root, op, "CSV", proposal, LocalServiceKind.CP5_DIVERSIFICATION, None)
        context = self.store.connect() if connection is None else nullcontext(connection)
        with context as conn:
            require_idle(conn)
            value = None
            with conn.transaction():
                self._query(conn, "gw_precheck", (owner, op, command_sha)).fetchone()
                if self._query(conn, "gw_root_metadata", (owner, root)).fetchone() is None:
                    raise GuardedWorkspaceError("F2_NOT_FOUND")
                scope = self._admit(conn, owner, root, op, command_sha, "EXECUTE_CREATE")
                value = self.csv.preview(str(owner), str(root), proposal, connection=conn, execution_scope=scope)
                raise psycopg.Rollback()
            if conn.info.transaction_status != TransactionStatus.IDLE:
                return UnknownWorkspaceResult(op)
            return value

    def _read_operation(self, owner, root, op, purpose, action, connection):
        self._identity(owner, root, op)
        context = self.store.connect() if connection is None else nullcontext(connection)
        with context as conn:
            require_idle(conn)
            with conn.transaction():
                # No archived payload or source I/O before current read purpose.
                if self._query(conn, "gw_root_metadata", (owner, root)).fetchone() is None:
                    raise GuardedWorkspaceError("F2_NOT_FOUND")
                scope = self._admit(conn, owner, root, op, "0" * 64, purpose)
                saved = self._archive(conn, owner, op)
                value = action(conn, scope, saved)
            require_idle(conn)
            return value

    def archive_read(self, owner, root, op, *, connection=None):
        return self._read_operation(owner, root, op, "ARCHIVE_READ", lambda conn, scope, saved: saved[:3], connection)

    def archive_export(self, owner, root, op, *, connection=None):
        return self._read_operation(owner, root, op, "ARCHIVE_EXPORT", lambda conn, scope, saved: saved[:3], connection)

    def reproduce(self, owner, root, op, *, connection=None):
        def run(conn, scope, saved):
            env = json.loads(saved[2])
            request = LocalServiceRequest(selector=LocalServiceKind(env["selector"]), owner_id=owner, root_id=root,
                revision_id=saved[3], operation_id=op, portfolio_id=root, ledger_pin=saved[4], as_of=self.world.as_of,
                context_id=scope.context_id, generation=env["generation"])
            # Reproduction uses original generation binding but still requires
            # the current generation's separate read+reproduce permission lease.
            original = self._service_context(conn, scope)
            from dataclasses import replace
            original = replace(original, generation=env["generation"])
            return reproduce_local_service(conn, request=request, context=original,
                saved_issued_bytes=saved[0], expected_issued_sha256=digest(saved[0]))
        return self._read_operation(owner, root, op, "EXECUTE_REPRODUCE", run, connection)

    def reconcile(self, owner, root, op, *, connection=None):
        """Existing committed bundle can be confirmed; absence remains UNKNOWN.

        This bounded product seam never accepts a caller bool as backend-end or
        prepared-transaction proof. A complete owned-disconnect proof is outside
        this API; callers needing it retain UNKNOWN instead of guessing rollback.
        """
        try:
            return self.archive_read(owner, root, op, connection=connection)
        except psycopg.errors.RaiseException as error:
            if str(error).splitlines()[0] == "F2_NOT_FOUND":
                return UnknownWorkspaceResult(op)
            raise
        except GuardedWorkspaceError as error:
            if error.code == "F2_NOT_FOUND":
                return UnknownWorkspaceResult(op)
            raise
