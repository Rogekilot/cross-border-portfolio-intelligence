"""Internal same-transaction scope for the fictional guarded writer integration.

This Python seal prevents accidental mixing of connections/transactions. Rights
are minted and enforced by PostgreSQL; this is not hostile-Python isolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import uuid

from psycopg import sql
from psycopg.pq import TransactionStatus


class GuardedWorkspaceError(ValueError):
    def __init__(self, code, detail="Guarded fictional workspace refused"):
        self.code = code
        super().__init__(detail)


_SEAL = object()
_IDENT = re.compile(r"[a-z][a-z0-9_]{0,62}")


def identifier(value):
    if type(value) is not str or _IDENT.fullmatch(value) is None:
        raise GuardedWorkspaceError("F2_SHAPE", "An exact bounded SQL identifier is required")
    return value


def require_idle(conn):
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise GuardedWorkspaceError("F2_OUTER_TRANSACTION_REQUIRED", "Public operations must own an initially IDLE connection")


def transaction_identity(conn):
    if conn.info.transaction_status != TransactionStatus.INTRANS:
        raise GuardedWorkspaceError("F2_ACTIVE_TRANSACTION_REQUIRED")
    pid, xid = conn.execute("SELECT pg_backend_pid(),pg_current_xact_id()::text").fetchone()
    return int(pid), str(xid)


@dataclass(frozen=True)
class ExecutionScope:
    connection: object = field(repr=False, compare=False)
    schema: str
    backend_pid: int
    transaction_id: str
    owner_id: uuid.UUID
    root_id: uuid.UUID
    context_id: str
    generation: int
    operation_id: uuid.UUID
    purpose: str
    snapshot_bytes: bytes = field(repr=False)
    _seal: object = field(repr=False, compare=False)

    def assert_current(self, conn):
        if self._seal is not _SEAL or self.connection is not conn:
            raise GuardedWorkspaceError("F2_SCOPE_DIFFERS")
        if transaction_identity(conn) != (self.backend_pid, self.transaction_id):
            raise GuardedWorkspaceError("F2_SCOPE_DIFFERS")
        row = conn.execute(sql.SQL("SELECT * FROM {}.gw_scope()").format(sql.Identifier(self.schema))).fetchone()
        if row is None or tuple(row) != (self.owner_id, self.root_id, self.context_id, self.generation, self.operation_id, self.purpose):
            raise GuardedWorkspaceError("F2_SCOPE_DIFFERS")


def _scope_from_database(conn, schema, snapshot_bytes):
    """Called only after gw_admit; no caller bool, GUC or cached authority."""
    identifier(schema)
    pid, xid = transaction_identity(conn)
    row = conn.execute(sql.SQL("SELECT * FROM {}.gw_scope()").format(sql.Identifier(schema))).fetchone()
    if row is None or type(snapshot_bytes) is not bytes:
        raise GuardedWorkspaceError("F2_SCOPE_DIFFERS")
    return ExecutionScope(conn, schema, pid, xid, *row, snapshot_bytes, _SEAL)


def validate_domain_constraints(conn, scope):
    if type(scope) is not ExecutionScope:
        raise GuardedWorkspaceError("F2_SCOPE_DIFFERS")
    scope.assert_current(conn)
    # Inspect actual names: the historical CSV FK has a generated SQL name.
    rows = conn.execute("SELECT c.conname,t.relname,c.contype,c.condeferrable "
        "FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
        "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=%s AND c.condeferrable "
        "ORDER BY c.conname", (scope.schema,)).fetchall()
    allowed = {("ledger_event_transfer_pairing", "ledger_event", "t"),
               ("web_csv_source_key_report_id_fkey", "web_csv_source_key", "f")}
    excluded = {("gw_root_portfolio_fkey", "gw_root", "f"),
                ("gw_bundle_complete", "gw_lease", "t")}
    seen = set()
    for name, table, kind, deferred in rows:
        key = (name, table, kind)
        if key in excluded:
            continue
        if key not in allowed:
            raise GuardedWorkspaceError("F2_UNKNOWN_CONSTRAINT", str(key))
        seen.add(key)
        conn.execute(sql.SQL("SET CONSTRAINTS {}.{} IMMEDIATE").format(sql.Identifier(scope.schema), sql.Identifier(name)))
    if seen != allowed:
        raise GuardedWorkspaceError("F2_CONSTRAINT_INVENTORY_DIFFERS")
