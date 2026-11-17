"""F1 R5: the SHARED CREATE TAIL and the SHARED READ TAIL of the real gateway (design 3.1, 3.2, 4.4, E23).

There is ONE create tail and ONE read tail. Both branches' creates (the real branch, and the test-scope create that is the fictional
branch of the one parameterised module) call the create tail; read, reproduce and every list entry (both branches) call the read tail. Neither
branch's own code contains a `COMMIT`, a `SET CONSTRAINTS` or a classification of a commit-time error: a static audit of the sources checks that,
so the function the tests exercise is the function the real run will use.

THE CREATE TAIL (`CreateTail.run`), in order:

  1. the branch's staging function runs inside the tail's one transaction (admit, link check, world, economic writes, the service call, seal,
     archive re-read). A refusal there, of the gateway or of the service, rolls the whole transaction back: nothing is addressable;
  2. `fire_by_name`: the INVENTORY CHECK, then `SET CONSTRAINTS <schema>.<name> IMMEDIATE` for each deferrable constraint of the inventory BY NAME,
     never `SET CONSTRAINTS ALL`, never the deadline guard (`rw_lease_deadline_guard`), which stays pending so that the COMMIT itself fires it
     and a create stalled past `complete_by` is refused at COMMIT (`RW_DEADLINE`). A deferrable constraint that is not on the inventory is
     refused (`RW_UNKNOWN_DEFERRABLE`), as is an inventory that lacks an expected one;
  3. the pre-commit seam (`_before_commit`, a private injection point as F2's `_after_commit_ack` was) and COMMIT;
  4. the COMMIT-time classification of design 3.1 (E4), which is `OneTransaction._classify`: at or after the commit point ONLY a gateway `RW_*`
     code on a connection that is back at IDLE is a definite refusal; every other error is UNKNOWN. Nothing is retried, here or anywhere.

THE READ TAIL (`ReadTail.run`): the same transaction runner with no firing at all. The body admits, reads under the held locks and RETURNS its
value; the value leaves the tail only after the COMMIT succeeded, and a COMMIT-time `RW_DEADLINE` is a refusal with no value. No code on the
read path issues a `SET CONSTRAINTS` of any form, so the deadline guard is still pending at the COMMIT.

RECONCILIATION (`reconcile`): on a NEW connection, as a read of its own (an `ARCHIVE_READ` admission at the CURRENT generation): the operation's
exact owner, operation id and command digest (`rw_precheck`), the current authority (the admission) and the integrity checks (`rw_archive`, which
runs the seal's acceptance again). It reports COMMITTED or UNKNOWN. It NEVER reports a rolled-back state: absence is not proof of rollback
(E10 section 6; F2 `guarded_workspace_store.reconcile`), and a refused admission (a lapsed context, a pending drain mark, a completed
withdrawal) is UNKNOWN, not the refusal. A definite refusal is reported only by the create call itself.

Pure Python over `psycopg`, which is imported inside the functions that need it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import contextlib
import uuid

from persistence import real_catalog_audit
from persistence.real_workspace_context import OneTransaction, RealWorkspaceError, database_refusal, identifier, query_one

DEADLINE_GUARD = "rw_lease_deadline_guard"
DEFAULT_LOCK_TIMEOUT_MS = 10_000
NO_COMMAND = "0" * 64


class ServiceRefusal(RealWorkspaceError):
    """The financial service refused (for the real branch on made-up test data: `SYNTHETIC_MARKET_DATA_REFUSED`, design fact 12, FF1-C08). It is
    raised INSIDE the tail's transaction, so the whole transaction rolls back and nothing is addressable. `issued_bytes` are the service's own
    refusal bytes, returned to the caller for diagnosis; they are never stored."""

    def __init__(self, code, issued_bytes=None):
        super().__init__(code)
        self.issued_bytes = issued_bytes


# ---- results ---------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Done:
    """The transaction committed (the tail saw the COMMIT succeed); `value` is what the body returned."""
    value: object = field(repr=False)
    persisted: bool = field(default=True, init=False)


@dataclass(frozen=True)
class Refused:
    """A definite refusal: the transaction was rolled back, nothing is recorded. `issued_bytes` is set for a service refusal only."""
    code: str
    detail: str = ""
    issued_bytes: object = field(default=None, repr=False)
    persisted: bool = field(default=False, init=False)


@dataclass(frozen=True)
class Unknown:
    """The outcome is not known. Nothing was retried. For a create the caller reconciles (`reconcile`); a read has no value to deliver."""
    operation_id: object = None
    reason: str = ""
    disposition: str = field(default="UNKNOWN", init=False)


@dataclass(frozen=True)
class Reconciled:
    """The only two things reconciliation reports: COMMITTED (with the archive it read) or UNKNOWN (with the reason). Never rolled back."""
    status: str
    archive: object = field(default=None, repr=False)
    reason: str = ""


# ---- the inventory and firing by name ---------------------------------------------------------------------------------------------------
def fire_by_name(conn, schema):
    """The create tail's firing step (E23). Reads the deferrable constraints of the schema, refuses any that is not expected (the F2 pattern,
    `guarded_workspace_context.validate_domain_constraints`) or any expected one that is missing, then names each but the deadline guard in a
    `SET CONSTRAINTS ... IMMEDIATE`. Returns the names fired. `SET CONSTRAINTS ALL` appears nowhere in this module."""
    from psycopg import sql
    schema = identifier(schema)
    inventory = set(real_catalog_audit.deferrable_inventory(conn, schema))
    unknown = sorted(inventory - real_catalog_audit.EXPECTED_DEFERRABLE)
    if unknown:
        raise RealWorkspaceError("RW_UNKNOWN_DEFERRABLE", ",".join("%s on %s" % (name, table) for name, table, _kind in unknown))
    missing = sorted(real_catalog_audit.EXPECTED_DEFERRABLE - inventory)
    if missing:
        raise RealWorkspaceError("RW_DEFERRABLE_INVENTORY_DIFFERS", ",".join(name for name, _table, _kind in missing))
    fired = []
    for name, _table, _kind in sorted(inventory):
        if name == DEADLINE_GUARD:
            continue                      # NEVER early: the COMMIT fires it, and a stall past complete_by is refused there
        conn.execute(sql.SQL("SET CONSTRAINTS {}.{} IMMEDIATE").format(sql.Identifier(schema), sql.Identifier(name)))
        fired.append(name)
    return tuple(fired)


# ---- the tails ---------------------------------------------------------------------------------------------------------------------------
class _Tail(OneTransaction):
    """`conn` is the executor's connection, IDLE on entry (`OneTransaction._transact` requires it)."""

    def __init__(self, conn, schema, *, lock_timeout_ms=DEFAULT_LOCK_TIMEOUT_MS):
        self.conn = conn
        self.schema = identifier(schema)
        self.lock_timeout_ms = lock_timeout_ms

    def _pin(self, conn):
        """The services this path calls write unqualified table names (the ledger store, the performance and diversification services). The
        transaction pins its search path to the gateway schema, `pg_temp` last, so a temporary relation is never reached (C2-5)."""
        from psycopg import sql
        conn.execute(sql.SQL("SET LOCAL search_path TO {}, pg_temp").format(sql.Identifier(self.schema)))

    def _finish(self, status, payload, operation_id):
        if status == "OK":
            return Done(payload)
        if status == "REFUSED":
            return Refused(payload.code, payload.detail, getattr(payload, "issued_bytes", None))
        if status == "LOCK_TIMEOUT":
            return Refused("RW_LOCK_TIMEOUT")             # before the commit point: the transaction was rolled back
        return Unknown(operation_id, "COMMIT_OUTCOME_NOT_KNOWN")


class CreateTail(_Tail):
    def run(self, stage, *, operation_id=None):
        """`stage(conn)` does the branch's work in the open transaction and returns the value to deliver after the COMMIT."""
        def work(conn):
            self._pin(conn)
            value = stage(conn)
            fire_by_name(conn, self.schema)
            return value
        status, payload = self._transact(work)
        return self._finish(status, payload, operation_id)


class ReadTail(_Tail):
    def run(self, body, *, operation_id=None):
        """`body(conn)` admits, reads and returns its value. The tail adds nothing to the transaction: no firing, no `SET CONSTRAINTS`."""
        def work(conn):
            self._pin(conn)
            return body(conn)
        status, payload = self._transact(work)
        return self._finish(status, payload, operation_id)


# ---- reconciliation -----------------------------------------------------------------------------------------------------------------------
def reconcile(connect, schema, *, owner, root, operation_id, command_sha256, context_id, generation,
              expected_issued_sha256=None, expected_response_sha256=None, lock_timeout_ms=DEFAULT_LOCK_TIMEOUT_MS):
    """Read-only reconciliation of one operation on a NEW connection (`connect()` returns an IDLE executor connection that this function
    closes). Returns `Reconciled("COMMITTED", archive)` only when the operation row exists for this exact owner, operation id and command
    digest, the admission at the current generation is granted, the archive reads (the seal's acceptance runs again) and, when the caller
    supplies them, the archive's digests are the expected ones. Everything else is `Reconciled("UNKNOWN", reason)`."""
    import psycopg
    from persistence import real_workspace_store as store

    def body(conn):
        row = query_one(conn, schema, "rw_precheck", (owner, operation_id, command_sha256))
        if row is None:
            return Reconciled("UNKNOWN", reason="ABSENT")               # absent is not proof of rollback
        if row[0] != root or row[1] != context_id:
            return Reconciled("UNKNOWN", reason="OPERATION_ELSEWHERE")
        store.admit(conn, schema, owner=owner, root=root, context_id=context_id, generation=generation, purpose="ARCHIVE_READ",
                    operation_id=operation_id, command_sha256=NO_COMMAND)
        archive = query_one(conn, schema, "rw_archive", (owner, operation_id))
        if archive is None:
            return Reconciled("UNKNOWN", reason="ARCHIVE_ABSENT")
        if (expected_issued_sha256 is not None and archive[3] != expected_issued_sha256) or (
                expected_response_sha256 is not None and archive[4] != expected_response_sha256):
            return Reconciled("UNKNOWN", reason="ARCHIVE_DIFFERS")
        return Reconciled("COMMITTED", tuple(archive))

    try:
        conn = connect()
    except psycopg.Error:
        return Reconciled("UNKNOWN", reason="NO_CONNECTION")
    with contextlib.closing(conn):
        outcome = ReadTail(conn, schema, lock_timeout_ms=lock_timeout_ms).run(body, operation_id=operation_id)
    if isinstance(outcome, Done):
        return outcome.value
    if isinstance(outcome, Refused):
        return Reconciled("UNKNOWN", reason=outcome.code)               # a refused reconciliation is UNKNOWN, not the refusal
    return Reconciled("UNKNOWN", reason=outcome.reason)


def entry_operation_id(root, generation, label):
    """A deterministic operation id for a read admission of a list entry or a reconciliation (reads store no operation)."""
    return uuid.uuid5(uuid.NAMESPACE_URL, "finweb.rw.read:%s:%s:%s" % (label, root, generation))


__all__ = ("CreateTail", "ReadTail", "Done", "Refused", "Unknown", "Reconciled", "ServiceRefusal", "fire_by_name", "reconcile", "database_refusal")
