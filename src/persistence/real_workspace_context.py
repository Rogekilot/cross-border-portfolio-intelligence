"""F1 R1: shared helpers of the real gateway's Python side (errors, identifiers, SQL call helpers).

Forked from the shape of `guarded_workspace_context.py` (which is not edited). `psycopg` is imported inside the functions
that need it, so this module and the pure modules above it import without the driver.
"""
from __future__ import annotations

import re


class RealWorkspaceError(ValueError):
    """A refusal of the real gateway. `code` is the stable `RW_*` code of the database function or of the Python check;
    `detail` is the database's DETAIL line (a comma list of reason codes for a publish refusal) or a short text."""

    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail or ""
        super().__init__(code if not detail else "%s: %s" % (code, detail))

    @property
    def codes(self):
        """Every code this refusal reports: its own and, for a publish refusal, the listed reasons."""
        listed = tuple(x for x in self.detail.split(",") if x.startswith("RW_"))
        return (self.code,) + listed


_IDENT = re.compile(r"[a-z][a-z0-9_]{0,62}")


def identifier(value):
    if type(value) is not str or _IDENT.fullmatch(value) is None:
        raise RealWorkspaceError("RW_SHAPE", "An exact bounded SQL identifier is required")
    return value


def require_idle(conn):
    from psycopg.pq import TransactionStatus
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise RealWorkspaceError("RW_OUTER_TRANSACTION_REQUIRED", "Public operations must own an initially IDLE connection")


def require_in_transaction(conn):
    from psycopg.pq import TransactionStatus
    if conn.info.transaction_status != TransactionStatus.INTRANS:
        raise RealWorkspaceError("RW_ACTIVE_TRANSACTION_REQUIRED")


def transaction_identity(conn):
    require_in_transaction(conn)
    pid, xid = conn.execute("SELECT pg_backend_pid(),pg_current_xact_id()::text").fetchone()
    return int(pid), str(xid)


def _call(conn, schema, name, params):
    from psycopg import sql
    return conn.execute(sql.SQL("SELECT * FROM {}.{}(" + ",".join(["%s"] * len(params)) + ")").format(
        sql.Identifier(identifier(schema)), sql.Identifier(identifier(name))), tuple(params))


def query_one(conn, schema, name, params=()):
    return _call(conn, schema, name, params).fetchone()


def query_all(conn, schema, name, params=()):
    return _call(conn, schema, name, params).fetchall()


def database_refusal(error):
    """The `RealWorkspaceError` for a database error raised by a gateway function or trigger, or None.

    Gateway refusals are `RAISE EXCEPTION 'RW_...'`: SQLSTATE P0001, the code in the primary message, optional reason codes in
    DETAIL. Anything else (a lock timeout, a check violation of a crafted insert, a connection error) is not a gateway code."""
    import psycopg
    if not isinstance(error, psycopg.errors.RaiseException):
        return None
    primary = (error.diag.message_primary or str(error)).splitlines()[0]
    if not primary.startswith("RW_"):
        return None
    return RealWorkspaceError(primary, error.diag.message_detail or "")


class OneTransaction:
    """The one-transaction runner of every command that commits (R1's publisher tool; R2's registration by the loader), with the
    fail-closed commit-outcome classification of design 3.1 (E4). Moved here from `RealPublisher` in R2 so that a second command
    set uses the SAME code, not a copy that could drift. A subclass has `self.conn` and `self.lock_timeout_ms`."""

    # ---- private seams for the commit-outcome tests (like F2's `_after_commit_ack`); no retry anywhere ----------------
    def _before_commit(self):
        require_in_transaction(self.conn)

    def _after_commit(self):
        require_idle(self.conn)

    def _set_lock_timeout(self, ms):
        from psycopg import sql
        self.conn.execute(sql.SQL("SET LOCAL lock_timeout = {}").format(sql.Literal("%dms" % ms)))

    def _transact(self, work, *, lock_timeout_ms=None):
        """Run `work(conn)` in ONE transaction and commit it. Returns ("OK", value) / ("REFUSED", RealWorkspaceError) /
        ("LOCK_TIMEOUT", None) / ("UNKNOWN", None). Nothing is retried here or anywhere in this tool.

        The commit point is the line `reached_commit = True`, just before the block ends and the driver sends COMMIT. The rule is
        design 3.1 (E4): at or after it, ONLY a gateway `RW_*` code on a connection that is back at IDLE is a definite refusal
        (the deadline guard's `RW_DEADLINE` is the case: the transaction was rolled back and nothing is recorded). EVERY other error
        at or after the commit point is UNKNOWN: a lock timeout, a deadlock, a cancel, a constraint error with no gateway code, a
        driver error, a lost connection, a failure of the post-commit check. The identical command reconciles. This is stricter than
        design 4.4 item 4 ("an error reply to COMMIT means the transaction rolled back"), whose order of steps inside PostgreSQL's
        commit is marked not shown, and the PM chose the stricter rule.

        Before the commit point the transaction is rolled back by the `with` block. A gateway code is a refusal; a lock timeout is
        `LOCK_TIMEOUT`; any other error on a connection that is still usable and back at IDLE (a statement timeout, a cancel, a
        deadlock, an error with no gateway code) is a definite rollback, reported as the refusal `RW_STATEMENT_FAILED` with the
        exception's class name; a connection that is closed or not IDLE is UNKNOWN.

        Against F2 (`guarded_workspace_store.py:271-272`): F2 maps every `OperationalError` and `InterfaceError`, before or at the
        COMMIT, to UNKNOWN and lets any other database error propagate. R1 is FINER before the commit point (an error on a usable
        IDLE connection is a definite rollback, so a deadlock is not UNKNOWN) and STRICTER at it (an error with no gateway code, and a
        lock timeout, are UNKNOWN where F2 propagates the first and has no second)."""
        import psycopg
        require_idle(self.conn)
        reached_commit = False
        try:
            with self.conn.transaction():
                self._set_lock_timeout(self.lock_timeout_ms if lock_timeout_ms is None else lock_timeout_ms)
                value = work(self.conn)
                self._before_commit()
                reached_commit = True
            self._after_commit()
            return "OK", value
        except psycopg.errors.LockNotAvailable:
            return ("UNKNOWN", None) if reached_commit else ("LOCK_TIMEOUT", None)
        except psycopg.Error as error:
            return self._classify(error, reached_commit)
        except RealWorkspaceError as refusal:
            return ("UNKNOWN", None) if reached_commit else ("REFUSED", refusal)

    def _classify(self, error, reached_commit):
        from psycopg.pq import TransactionStatus
        usable = not self.conn.closed and self.conn.info.transaction_status == TransactionStatus.IDLE
        gateway = database_refusal(error)
        if reached_commit:
            return ("REFUSED", gateway) if gateway is not None and usable else ("UNKNOWN", None)
        if gateway is not None:
            return "REFUSED", gateway
        if usable:
            return "REFUSED", RealWorkspaceError("RW_STATEMENT_FAILED", type(error).__name__)
        return "UNKNOWN", None
