"""F1 R1: the real gateway's installer for TEST databases, its admit wrapper, and the PUBLISHER TOOL (publish, renew, withdraw).

Forked from the shape of `guarded_workspace_store.py` (which is not edited). Nothing here installs REAL: `install_test_gateway`
writes install kind `TEST` and no other, and refuses a database whose name uses the reserved real-install prefix. The real
installer is R6's (`real_install.py`). R6 also adds, in `main`, the preflight that gates `publish` and `renew` against a REAL target and is never
applied to `withdraw` (design 1.2 5.1; `real_preflight.py`). Credentials: this module reads no environment variable and takes no credential
option; a connection is handed in, or the default connection takes a password from the terminal prompt alone, for a REAL target only.

The publisher commands are one-transaction database calls with the mandatory decision reference (PD id, git commit, SHA-256 at
that commit) and the issuer actor. They return a `CommandResult` with an exit status of its own for each outcome (design 3.2):

    EXIT_DONE 0               done
    EXIT_REFUSED 2            a definite refusal: a gateway code, a malformed input, or a statement that failed before the commit
                              point on a usable connection (a rollback). The output says "nothing was recorded", except for a
                              withdrawal refused after its drain mark committed: that output says the mark stays recorded
    EXIT_NOT_YET_EFFECTIVE 3  a withdrawal whose drain mark is committed but whose generation was not appended: it waits for
                              in-flight work, or its wait ended by a lock timeout, a statement timeout, a cancel or a deadlock
    EXIT_UNKNOWN 4            the outcome is not known: no answer, or any error at or after the commit point that is not a
                              gateway code on a connection back at IDLE. Check the status view, then re-run the identical command
    EXIT_LOCK_TIMEOUT 5       a publish, renewal or drain mark waited for a lock until its lock_timeout and recorded nothing

The trusted clock is the database's `clock_timestamp()`; nothing here samples a clock.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys

from persistence import real_proposal
from persistence import real_roles
from persistence import real_sidecar
from persistence.real_workspace_context import (OneTransaction, RealWorkspaceError, database_refusal, identifier, query_all, query_one,
                                                require_idle, require_in_transaction)

EXIT_DONE, EXIT_REFUSED, EXIT_NOT_YET_EFFECTIVE, EXIT_UNKNOWN, EXIT_LOCK_TIMEOUT = 0, 2, 3, 4, 5
RIGHTS = ("EXECUTE_CREATE", "ARCHIVE_READ", "ARCHIVE_EXPORT", "EXECUTE_REPRODUCE")
BASES = ("LEASE_TERM", "NO_EXPIRY_READING", "NOT_ASSESSED")
from persistence.connection import RESERVED_REAL_PREFIX         # the one constant (R6): see connection.py
DEFAULT_LOCK_TIMEOUT_MS = 10_000
#: The gateway's SQL, in install order, run in ONE transaction with the same four validated identifiers: the CORE (the authority core,
#: the candidate registry of R2 and the fence/seal/archive/read-function file of R3) and, for a TEST install only, the TEST-only part.
#: The list is `real_roles.sql_files(kind)`; this installer writes TEST installs only, so it takes the TEST list.
GATEWAY_SQL_FILES = real_roles.sql_files("TEST")

#: The wording of the plausibility rule (design 3.1, conformance R2-M1). `term_end_not_after` is an UPPER bound. The rule only
#: refuses a `valid_until` that lies after the latest the term could possibly end. It does not show that the lease stays inside
#: the licence term and is not a safety margin, so no output may say "within the term". A test compares this text.
PLAUSIBILITY_WORDING = ("`valid_until` is not later than the recorded upper bound of the term end; "
                        "no lower bound of the term end is recorded")

_PD = re.compile(r"PD-[0-9]{4,}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_UTC_SECONDS = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


def iso(value):
    """A UTC instant as text, to the microsecond; deterministic, no clock."""
    if value is None:
        return "none"
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_utc(text, field_name="time"):
    """`YYYY-MM-DDTHH:MM:SSZ` to an aware UTC datetime; anything else is a refusal."""
    if type(text) is not str or _UTC_SECONDS.fullmatch(text) is None:
        raise RealWorkspaceError("RW_SHAPE", field_name + " must be YYYY-MM-DDTHH:MM:SSZ")
    try:
        return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError as error:
        raise RealWorkspaceError("RW_SHAPE", field_name + " is not a date") from error


def digest(data):
    return hashlib.sha256(data).hexdigest()


# ===================================================================================================================
# Installer (TEST only)
# ===================================================================================================================
def _check_install_inputs(schema, owner_role, executor_role, loader_role, publisher_role, w_seconds, account_role=None):
    """`account_role` (PD-0078) is the fifth role of the web accounts; None is the four-role install of the earlier fixtures."""
    names = [identifier(x) for x in (schema, owner_role, executor_role, loader_role, publisher_role)
             + (() if account_role is None else (account_role,))]
    if len(set(names[1:])) != len(names) - 1:
        raise RealWorkspaceError("RW_ROLE_DIFFERS")
    if type(w_seconds) is not int or isinstance(w_seconds, bool) or not 1 <= w_seconds <= 86400:
        raise RealWorkspaceError("RW_SHAPE", "W is a whole number of seconds from 1 to 86400")
    return names


def _install_gateway_body(conn, names, owner_role, executor_role, loader_role, publisher_role, kind="TEST", account_role=None):
    """Checks, then the gateway SQL, in the caller's open transaction. Writes NO install row: the kind is the caller's act.

    `kind` selects the SQL files and the role lists (`real_roles.sql_files(kind)`, `real_roles.grant_statements(kind, ...)`) and the audit
    run at the end. `install_test_gateway` passes "TEST", the only kind product code ever installs and records. The test kit's crafted
    REAL fixture (E11, in a disposable database) passes "REAL" to run the REAL file list, which omits the TEST-only part; the real
    installer (R6) will take the same two lists and call this body. The body never writes a kind row."""
    if kind not in ("TEST", "REAL"):
        raise RealWorkspaceError("RW_SHAPE", "install kind is TEST or REAL")
    schema = names[0]
    database = conn.execute("SELECT current_database()").fetchone()[0]
    if kind == "TEST" and database.startswith(RESERVED_REAL_PREFIX):
        # R6: the refusal is for a TEST install. The real installer (kind REAL) is the one tool that installs INTO the reserved namespace.
        raise RealWorkspaceError("RW_INSTALL_KIND_REFUSED", "a TEST install is never written into the reserved real-install namespace")
    roles = conn.execute("SELECT rolname,rolsuper,rolbypassrls,rolcanlogin FROM pg_roles WHERE rolname=ANY(%s::text[])", (names[1:],)).fetchall()
    by_name = {r[0]: r[1:] for r in roles}
    # The LOADER may or may not have LOGIN at install time (R2; PD-0070 decision 1: the owner sets it NOLOGIN while no load runs, and a
    # second installer run in that state must not fail). The owner is NOLOGIN; the executor and the publisher are LOGIN.
    # PD-0078: the account role, when named, is the fifth: non-superuser, non-BYPASSRLS, LOGIN (its password is set by the owner at a prompt).
    login_roles = (executor_role, publisher_role) + (() if account_role is None else (account_role,))
    if len(by_name) != len(names) - 1 or any(by_name[n][:2] != (False, False) for n in names[1:]) or by_name[owner_role][2] \
            or not all(by_name[n][2] for n in login_roles):
        raise RealWorkspaceError("RW_ROLE_DIFFERS", "exact non-superuser, non-BYPASSRLS roles; owner NOLOGIN, executor, publisher and account LOGIN")
    current = conn.execute("SELECT current_user::text,n.nspowner::regrole::text FROM pg_namespace n WHERE n.nspname=%s", (schema,)).fetchone()
    if current != (owner_role, owner_role):
        raise RealWorkspaceError("RW_INSTALL_OWNER_DIFFERS")
    for role in names[1:]:
        for other in names[1:]:
            if role != other and conn.execute("SELECT pg_has_role(%s::name,%s::name,'MEMBER')", (role, other)).fetchone()[0]:
                raise RealWorkspaceError("RW_ROLE_DIFFERS", "no role may be a member of another")
    for table in ("app_user", "portfolio"):
        if conn.execute("SELECT to_regclass(%s)", (schema + "." + table,)).fetchone()[0] is None:
            raise RealWorkspaceError("RW_INSTALL_MIGRATIONS_MISSING", table)
    if conn.execute("SELECT to_regclass(%s)", (schema + ".rw_install",)).fetchone()[0] is not None:
        raise RealWorkspaceError("RW_ALREADY_INSTALLED")
    for filename in real_roles.sql_files(kind):          # TEST: the core, then the TEST-only part; REAL: the core alone
        body = Path(__file__).with_name(filename).read_text("utf8")
        for marker, name in zip(("__RW_SCHEMA__", "__RW_EXECUTOR__", "__RW_LOADER__", "__RW_PUBLISHER__"),
                                (schema, executor_role, loader_role, publisher_role)):
            body = body.replace(marker, name)
        conn.execute(body)
    # The role lists (R3): one list per runtime role in the shared installer code (real_roles), applied here after the last file so that
    # every function it names exists, with the one statement that revokes PUBLIC's EXECUTE on every routine of the schema. Nothing in the
    # SQL files grants a runtime role anything.
    real_roles.apply_role_grants(conn, schema, executor_role, loader_role, publisher_role, kind, account_role)
    from persistence import real_catalog_audit, real_provenance_store
    real_provenance_store.verify_registry_install(conn, schema, owner_role, executor_role, loader_role, publisher_role)
    # The catalog audit (T03), run as the install's kind: an install that does not hold exactly its lists is refused whole (rolled back).
    findings = real_catalog_audit.audit(conn, schema, owner_role, executor_role, loader_role, publisher_role, as_kind=kind,
                                        require_install_row=False, account_role=account_role)        # the kind row is the caller's act, after this body
    if findings.findings:
        raise RealWorkspaceError("RW_INSTALL_REFUSED", "catalog audit: " + "; ".join(f.short() for f in findings.findings[:5]))


def install_test_gateway(conn, *, schema, owner_role, executor_role, loader_role, publisher_role, w_seconds, account_role=None):
    """Install the real gateway's authority core in a freshly migrated schema of a disposable TEST database.

    The connection must be the schema owner's (`SET ROLE` owner). Writes install kind `TEST` and `W` once, and no other kind:
    there is no parameter for the kind. No role creation, no migration-history edit, no real-database discovery. Four exact roles
    are required: owner NOLOGIN, the other three LOGIN, none a superuser or BYPASSRLS, none a member of another. Refuses a
    database named with the reserved real-install prefix.
    """
    names = _check_install_inputs(schema, owner_role, executor_role, loader_role, publisher_role, w_seconds, account_role)
    require_idle(conn)
    from psycopg import sql
    with conn.transaction():
        _install_gateway_body(conn, names, owner_role, executor_role, loader_role, publisher_role, account_role=account_role)
        # The install row is written once, here, and is immutable afterwards. This installer writes TEST and no other kind.
        conn.execute(sql.SQL("INSERT INTO {}.rw_install(singleton,kind,w_seconds) VALUES(true,'TEST',%s)").format(sql.Identifier(schema)),
                     (w_seconds,))


# ===================================================================================================================
# Decision reference and expiry evidence
# ===================================================================================================================
@dataclass(frozen=True)
class DecisionRef:
    """The decision reference (E13): PD id, the git commit that holds it, and the SHA-256 of the file at that commit.
    The tool records all three and refuses a command that lacks one. It does not check them against git."""
    pd_id: str
    git_commit: str
    doc_sha256: str

    def __post_init__(self):
        if type(self.pd_id) is not str or _PD.fullmatch(self.pd_id) is None or type(self.git_commit) is not str \
                or _COMMIT.fullmatch(self.git_commit) is None or type(self.doc_sha256) is not str or _HEX64.fullmatch(self.doc_sha256) is None:
            raise RealWorkspaceError("RW_DECISION_REF_REQUIRED", "a PD id, a 40-hex git commit and a 64-hex SHA-256 are all required")


@dataclass(frozen=True)
class BasisEntry:
    """One expiry-basis entry, for exactly one member source: (source_id, basis, decision reference), and for a LEASE_TERM the
    latest instant the source's current term can end (an UPPER bound)."""
    source_id: str
    basis: str
    ref: DecisionRef
    term_end_not_after: object = None

    def as_json(self):
        if self.basis not in BASES or type(self.source_id) is not str or not self.source_id:
            raise RealWorkspaceError("RW_SHAPE", "an expiry entry names a source and one of " + ", ".join(BASES))
        out = {"source_id": self.source_id, "basis": self.basis, "pd_id": self.ref.pd_id, "git_commit": self.ref.git_commit,
               "doc_sha256": self.ref.doc_sha256}
        if self.basis == "LEASE_TERM":
            value = self.term_end_not_after
            if type(value) is not dt.datetime or value.tzinfo is None or value.microsecond:
                raise RealWorkspaceError("RW_SHAPE", "term_end_not_after is a UTC instant to the second")
            out["term_end_not_after"] = value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif self.term_end_not_after is not None:
            raise RealWorkspaceError("RW_SHAPE", "only a LEASE_TERM entry carries term_end_not_after")
        return out


def evidence_json(evidence):
    if not isinstance(evidence, (list, tuple)) or any(type(e) is not BasisEntry for e in evidence):
        raise RealWorkspaceError("RW_SHAPE", "evidence is a list of BasisEntry")
    return sorted((e.as_json() for e in evidence), key=lambda e: e["source_id"])


def rights_json(rights):
    if type(rights) is not dict or set(rights) != set(RIGHTS) or any(type(v) is not bool for v in rights.values()):
        raise RealWorkspaceError("RW_SHAPE", "rights are the four booleans " + ", ".join(RIGHTS))
    return dict(rights)


def _valid_until(value, *, nullable):
    if value is None and nullable:
        return None
    if type(value) is not dt.datetime or value.tzinfo is None:
        raise RealWorkspaceError("RW_SHAPE", "valid_until is a timezone-aware instant")
    return value.astimezone(dt.timezone.utc)


def _actor(actor):
    if type(actor) is not str or not 1 <= len(actor) <= 128:
        raise RealWorkspaceError("RW_DECISION_REF_REQUIRED", "the issuer actor is required")
    return actor


def _ref(ref):
    if type(ref) is not DecisionRef:
        raise RealWorkspaceError("RW_DECISION_REF_REQUIRED", "a DecisionRef is required")
    return ref


# ===================================================================================================================
# The publisher tool
# ===================================================================================================================
@dataclass(frozen=True)
class CommandResult:
    status: int
    outcome: str
    lines: tuple
    data: dict = field(default_factory=dict)

    @property
    def text(self):
        return "\n".join(self.lines)


class RealPublisher(OneTransaction):
    """publish / renew / withdraw / status against one schema, on a connection handed in by the caller (IDLE, autocommit off or
    on). The tool sets its own `lock_timeout` for the waits that matter and sets no other session option."""

    def __init__(self, conn, schema, *, lock_timeout_ms=DEFAULT_LOCK_TIMEOUT_MS):
        self.conn, self.schema = conn, identifier(schema)
        if type(lock_timeout_ms) is not int or isinstance(lock_timeout_ms, bool) or not 1 <= lock_timeout_ms <= 600_000:
            raise RealWorkspaceError("RW_SHAPE", "lock_timeout_ms is from 1 to 600000")
        self.lock_timeout_ms = lock_timeout_ms

    # The one-transaction runner and its commit-outcome classification (E4) are `OneTransaction` in real_workspace_context.py
    # (moved there in R2 so that the loader's registration runs the same code). The seams `_before_commit` and `_after_commit`
    # are inherited, and tests override them on a subclass of this class as before.

    @staticmethod
    def _refused(refusal, *, then=None):
        """A definite refusal. `then` replaces the closing line "nothing was recorded" when an earlier step of the same command
        has already committed something (a withdrawal's drain mark), so the output never denies a record that exists."""
        lines = ["refused: " + refusal.code + ("  (" + refusal.detail + ")" if refusal.detail else "")]
        lines += list(then) if then is not None else ["nothing was recorded"]
        return CommandResult(EXIT_REFUSED, "REFUSED", tuple(lines), {"code": refusal.code, "codes": refusal.codes, "detail": refusal.detail})

    @staticmethod
    def _unknown(what, *, recorded=()):
        """The outcome is not known: no answer, or an error at the commit that is not a gateway code. Never says that nothing was
        recorded. `recorded` lists what an earlier step of the command is known to have committed."""
        lines = [what + ": the outcome is not known"] + list(recorded)
        lines += ["check the status view for this context before anything else: the command may or may not have been recorded",
                  "re-run the identical command on a new connection; it reconciles and never duplicates"]
        return CommandResult(EXIT_UNKNOWN, "UNKNOWN", tuple(lines), {})

    # ---- publish ------------------------------------------------------------------------------------------------------
    def publish(self, proposal, *, rights, valid_until, evidence, actor, ref, sidecars=()):
        """Publish a verified proposal: generation 1, the head and the mode, in one transaction. Re-running with identical input
        returns the original. The expiry kind is DERIVED from `evidence` by the database; this method cannot name a source.

        `sidecars` (R4b): the sidecar acquisition records, as BYTES, of a `REAL` proposal's members. O5 is evaluated here, in Python, before
        any statement is sent: the database cannot see sidecar bytes, so a `REAL` proposal whose members do not each have a valid sidecar
        (design 6.1) is refused with `RW_O5_FAILED` and nothing is recorded. For a test scope O5 is bypassed and `sidecars` is not looked at."""
        try:
            verified = real_proposal.verify_proposal(proposal)
            real_sidecar.require_null_slots_in_test_scope(verified.scope, verified.snapshot.content["members"])
            real_sidecar.require_o5(verified.scope, verified.snapshot.content["members"], sidecars)
            args = (verified.snapshot.data, _jsonb(rights_json(rights)), _valid_until(valid_until, nullable=True),
                    _jsonb(evidence_json(evidence)), _actor(actor), _ref(ref))
        except (real_proposal.ProposalError, real_sidecar.SidecarError) as error:
            return self._refused(RealWorkspaceError(error.code, str(error).split(": ", 1)[-1]))
        except RealWorkspaceError as error:
            return self._refused(error)
        snapshot, rights_v, valid, basis, actor_v, ref_v = args

        def work(conn):
            return query_one(conn, self.schema, "rw_publish", (snapshot, rights_v, valid, basis, actor_v, ref_v.pd_id, ref_v.git_commit, ref_v.doc_sha256))
        state, value = self._transact(work)
        if state == "REFUSED":
            return self._refused(value)
        if state == "LOCK_TIMEOUT":
            return CommandResult(EXIT_LOCK_TIMEOUT, "LOCK_TIMEOUT", ("publish waited %d ms for a lock and recorded nothing" % self.lock_timeout_ms,), {})
        if state == "UNKNOWN":
            return self._unknown("publish")
        context_id, generation, created = value
        lines = ["published context %s at generation %d" % (context_id, generation) if created
                 else "already published: context %s, the original at generation %d is returned" % (context_id, generation),
                 "scope %s; valid_until %s" % (verified.scope.name, iso(valid))]
        lines += self._plausibility_lines(valid, evidence)
        return CommandResult(EXIT_DONE, "PUBLISHED" if created else "ALREADY_PUBLISHED", tuple(lines),
                             {"context_id": context_id, "generation": generation, "created": created})

    # ---- renew ----------------------------------------------------------------------------------------------------------
    def renew(self, context_id, expected_generation, *, rights, valid_until, evidence, actor, ref, names_mark=None):
        """Record a new generation of the same context (a human act). `valid_until` must be strictly later than the server clock;
        an EARLIER value than the current one is a date correction (E25) and is printed as such."""
        try:
            args = (_context(context_id), _generation(expected_generation), _jsonb(rights_json(rights)),
                    _valid_until(valid_until, nullable=True), _jsonb(evidence_json(evidence)), _actor(actor), _ref(ref),
                    None if names_mark is None else _mark(names_mark))
        except RealWorkspaceError as error:
            return self._refused(error)
        context_v, generation_v, rights_v, valid, basis, actor_v, ref_v, mark_v = args

        def work(conn):
            return query_one(conn, self.schema, "rw_renew", (context_v, generation_v, rights_v, valid, basis, actor_v,
                                                              ref_v.pd_id, ref_v.git_commit, ref_v.doc_sha256, mark_v))
        state, value = self._transact(work)
        if state == "REFUSED":
            return self._refused(value)
        if state == "UNKNOWN":
            return self._unknown("renew")
        if state == "LOCK_TIMEOUT":
            lines = ["renewal not appended: waited %d ms for in-flight work and recorded nothing" % self.lock_timeout_ms]
            lines += self._in_flight_lines(context_v)
            return CommandResult(EXIT_LOCK_TIMEOUT, "LOCK_TIMEOUT", tuple(lines), {"context_id": context_v})
        generation, old_valid, new_valid, moved_earlier, superseded = value
        lines = ["renewed context %s: generation %d recorded" % (context_v, generation)]
        if moved_earlier:
            lines.append("`valid_until` moved earlier: %s to %s" % (iso(old_valid), iso(new_valid)))
        else:
            lines.append("valid_until %s (was %s)" % (iso(new_valid), iso(old_valid)))
        if superseded is not None:
            lines.append("drain mark %d is superseded by this renewal and stays readable" % superseded)
        lines += self._plausibility_lines(new_valid, evidence)
        return CommandResult(EXIT_DONE, "RENEWED", tuple(lines), {"generation": generation, "old_valid_until": old_valid,
                             "new_valid_until": new_valid, "moved_earlier": moved_earlier, "superseded_mark": superseded})

    # ---- withdraw ---------------------------------------------------------------------------------------------------------
    def withdraw(self, context_id, expected_generation, *, actor, ref, lock_timeout_ms=None):
        """Withdraw a context: all four rights false, in two steps. Step 1 commits the DRAIN MARK (issuer, reference, server time) in
        a transaction of its own, so no new admission starts. Step 2 waits for in-flight work under a lock_timeout and appends the
        generation that names the mark. A timeout leaves the mark pending and exits with a status of its own; it never prints "done".
        Re-running finds the mark and continues from step 2."""
        try:
            context_v, generation_v, actor_v, ref_v = _context(context_id), _generation(expected_generation), _actor(actor), _ref(ref)
        except RealWorkspaceError as error:
            return self._refused(error)
        timeout = self.lock_timeout_ms if lock_timeout_ms is None else lock_timeout_ms
        state, mark = self._transact(lambda conn: query_one(conn, self.schema, "rw_withdraw_mark",
                                     (context_v, generation_v, actor_v, ref_v.pd_id, ref_v.git_commit, ref_v.doc_sha256)))
        if state == "REFUSED":
            return self._refused(mark)
        if state == "UNKNOWN":
            return self._unknown("withdraw (drain mark)")
        if state == "LOCK_TIMEOUT":
            return CommandResult(EXIT_LOCK_TIMEOUT, "LOCK_TIMEOUT", ("the drain mark waited for a lock and recorded nothing",), {})
        mark_id, mark_generation, marked_at, mark_created, _named, mark_actor, mark_pd = mark
        recorded = "drain mark %d %s at %s" % (mark_id, "recorded" if mark_created else "already recorded", iso(marked_at))
        header = [recorded]
        if not mark_created and (mark_actor, mark_pd) != (actor_v, ref_v.pd_id):
            # A concurrent or earlier withdrawal of this generation holds the record (technical review R1, L-4).
            header.append("that mark was recorded by %s under %s; this command's actor and reference were not recorded" % (mark_actor, mark_pd))
        # From here the drain mark is COMMITTED. Every outcome of step 2 says so, and none says that nothing was recorded.
        state, applied = self._transact(lambda conn: query_one(conn, self.schema, "rw_withdraw_apply", (context_v, mark_id)), lock_timeout_ms=timeout)
        data = {"mark_id": mark_id, "marked_at": marked_at, "context_id": context_v}
        if state == "LOCK_TIMEOUT" or (state == "REFUSED" and applied.code == "RW_STATEMENT_FAILED"):
            # The wait ended without the generation: by the lock timeout, or by a statement timeout, a cancel or a deadlock. The
            # mark is pending either way (M-3, technical review R1), so this is the not-yet-effective state with its own status.
            lines = [recorded + ": new admissions are refused with RW_WITHDRAWAL_PENDING"] + header[1:]
            if state == "REFUSED":
                lines.append("the wait ended before the lock was granted (%s): no generation was appended" % applied.detail)
            lines.append("not yet effective for in-flight work; new admissions refused since %s" % iso(marked_at))
            lines += self._in_flight_lines(context_v)
            lines.append("re-run the withdrawal after the in-flight work ends, or end it as the owner role; a renewal that names the mark supersedes it")
            return CommandResult(EXIT_NOT_YET_EFFECTIVE, "NOT_YET_EFFECTIVE", tuple(lines), data)
        if state == "REFUSED":
            then = ["the drain mark %d stays recorded; this refusal did not change it, and no generation was appended" % mark_id]
            result = self._refused(applied, then=then)
            return CommandResult(EXIT_REFUSED, "REFUSED", tuple(header + list(result.lines)), dict(result.data, mark_id=mark_id))
        if state == "UNKNOWN":
            result = self._unknown("withdraw (generation)", recorded=["the drain mark %d is recorded; whether the generation was appended is not known" % mark_id])
            return CommandResult(EXIT_UNKNOWN, "UNKNOWN", tuple(header + list(result.lines)), {"mark_id": mark_id})
        generation, recorded_at, created, withdrawn = applied
        if not withdrawn:
            return CommandResult(EXIT_REFUSED, "REFUSED", tuple(header + ["drain mark %d is superseded by a renewal" % mark_id,
                                 "refused: RW_MARK_STALE  (generation %d, a renewal, names the mark; start a new withdrawal at the current "
                                 "generation)" % generation, "no generation was appended by this command"]), {"code": "RW_MARK_STALE", "mark_id": mark_id})
        lines = header + ["done: generation %d names drain mark %d; all four rights are off" % (generation, mark_id)]
        if not created:
            lines[-1] = "done (already effective): generation %d names drain mark %d" % (generation, mark_id)
        return CommandResult(EXIT_DONE, "WITHDRAWN", tuple(lines), {"generation": generation, "mark_id": mark_id, "recorded_at": recorded_at})

    # ---- status -----------------------------------------------------------------------------------------------------------
    def status(self, context_id=None):
        """One line per context and the pending drain marks with their age. Read-only."""
        from psycopg import sql
        require_idle(self.conn)
        lines = []
        with self.conn.transaction():
            where = sql.SQL(" WHERE context_id = {}").format(sql.Literal(_context(context_id))) if context_id is not None else sql.SQL("")
            rows = self.conn.execute(sql.SQL("SELECT context_id,generation,rights,expiry_kind,valid_until,earliest_term_end_not_after,pending_marks "
                                             "FROM {}.rw_status{} ORDER BY context_id").format(sql.Identifier(self.schema), where)).fetchall()
            marks = self.conn.execute(sql.SQL("SELECT mark_id,context_id,generation,issuer_actor,pd_id,marked_at,age FROM {}.rw_pending_marks "
                                              "ORDER BY mark_id").format(sql.Identifier(self.schema))).fetchall()
        for ctx, generation, rights, kind, valid_until, earliest, pending in rows:
            lines.append("context %s generation %d kind %s valid_until %s rights %s" % (ctx, generation, kind, iso(valid_until),
                         ",".join("%s=%s" % (k, "true" if rights[k] else "false") for k in RIGHTS)))
            if kind == "LEASE" and earliest is not None:
                lines.append("  " + PLAUSIBILITY_WORDING + " (valid_until %s; recorded upper bound %s)" % (iso(valid_until), iso(earliest)))
        for mark_id, ctx, generation, actor, pd_id, marked_at, age in marks:
            if context_id is None or ctx == context_id:
                lines.append("pending drain mark %d on context %s generation %d by %s under %s since %s (age %s)" %
                             (mark_id, ctx, generation, actor, pd_id, iso(marked_at), age))
        return CommandResult(EXIT_DONE, "STATUS", tuple(lines or ["no context is published"]), {"contexts": len(rows), "pending": len(marks)})

    # ---- output helpers ---------------------------------------------------------------------------------------------------
    @staticmethod
    def _plausibility_lines(valid_until, evidence):
        bounds = [e.term_end_not_after for e in evidence if e.basis == "LEASE_TERM" and e.term_end_not_after is not None]
        if valid_until is None or not bounds:
            return []
        return [PLAUSIBILITY_WORDING + " (valid_until %s; recorded upper bound %s)" % (iso(valid_until), iso(min(bounds)))]

    def _in_flight_lines(self, context_id):
        """The leases in flight on a context, named by backend and complete_by (read on a fresh transaction; an uncommitted lease row
        is invisible to this session, so the gateway names it through pg_locks)."""
        import psycopg
        try:
            with self.conn.transaction():
                rows = query_all(self.conn, self.schema, "rw_in_flight", (context_id,))
        except psycopg.Error:
            return ["in-flight leases could not be listed"]
        if not rows:
            return ["no in-flight lease is listed"]
        return ["blocking lease: backend %d, complete_by %s" % (pid, iso(complete_by)) for pid, complete_by in rows]


def _jsonb(value):
    from psycopg.types.json import Jsonb
    return Jsonb(value)


def _context(value):
    if type(value) is not str or _HEX64.fullmatch(value) is None:
        raise RealWorkspaceError("RW_SHAPE", "a context id is 64 lower-case hex characters")
    return value


def _generation(value):
    if type(value) is not int or isinstance(value, bool) or not 1 <= value < 2 ** 63:
        raise RealWorkspaceError("RW_SHAPE", "a generation is a positive whole number")
    return value


def _mark(value):
    if type(value) is not int or isinstance(value, bool) or value < 1:
        raise RealWorkspaceError("RW_SHAPE", "a drain mark id is a positive whole number")
    return value


# ===================================================================================================================
# Executor side: admit and list (thin wrappers; R5 builds the real executor store on them)
# ===================================================================================================================
@dataclass(frozen=True)
class AdmittedLease:
    snapshot: bytes = field(repr=False)
    owner_id: object
    root_id: object
    context_id: str
    generation: int
    operation_id: object
    purpose: str
    complete_by: object


def admit(conn, schema, *, owner, root, context_id, generation, purpose, operation_id, command_sha256, new_root=False):
    """Mint a lease in the caller's OUTER transaction (the caller commits or rolls back) and read it back. The snapshot returned
    is the stored tuple, and its hash is checked against the context id. A refusal is a `RealWorkspaceError` with the `RW_*` code."""
    import psycopg
    schema = identifier(schema)
    require_in_transaction(conn)
    try:
        snapshot = bytes(query_one(conn, schema, "rw_admit", (owner, root, context_id, generation, purpose, operation_id, command_sha256, new_root))[0])
        row = query_one(conn, schema, "rw_scope")
    except psycopg.Error as error:
        refusal = database_refusal(error)
        if refusal is None:
            raise
        raise refusal from error
    if row is None or digest(snapshot) != context_id:
        raise RealWorkspaceError("RW_CONTEXT_DIFFERS")
    return AdmittedLease(snapshot, *row)


def list_roots(conn, schema, owner):
    """The owner-scoped enumeration: identifiers only, no lease needed (design 2.4)."""
    import psycopg
    try:
        return [tuple(r) for r in query_all(conn, identifier(schema), "rw_list_roots", (owner,))]
    except psycopg.Error as error:
        refusal = database_refusal(error)
        if refusal is None:
            raise
        raise refusal from error


# ===================================================================================================================
# Command line (publisher tool). Options name a target and the command's own inputs; there is no credential option, no
# environment read, no preflight switch and no test switch. The gate and the prompt are `main`'s (R6); no option reaches either.
# ===================================================================================================================
def _read_input(path, what, *, binary=False):
    """A file named on the command line: a missing, unreadable or non-UTF-8 file is a typed refusal, not a traceback (L-8)."""
    try:
        return Path(path).read_bytes() if binary else Path(path).read_text("utf8")
    except (OSError, ValueError) as error:
        raise RealWorkspaceError("RW_INPUT_UNREADABLE", "%s: %s" % (what, type(error).__name__)) from error


def _json_input(text, what):
    try:
        return json.loads(text)
    except ValueError as error:
        raise RealWorkspaceError("RW_SHAPE", "%s is not JSON" % what) from error


def _read_evidence(path):
    raw = _json_input(_read_input(path, "the evidence file"), "the evidence file")
    if not isinstance(raw, list):
        raise RealWorkspaceError("RW_SHAPE", "the evidence file is a JSON list")
    out = []
    for item in raw:
        if not isinstance(item, dict) or set(item) - {"source_id", "basis", "pd_id", "git_commit", "doc_sha256", "term_end_not_after"}:
            raise RealWorkspaceError("RW_SHAPE", "an evidence entry has unknown keys")
        term = item.get("term_end_not_after")
        out.append(BasisEntry(item.get("source_id"), item.get("basis"), DecisionRef(item.get("pd_id"), item.get("git_commit"), item.get("doc_sha256")),
                              None if term is None else parse_utc(term, "term_end_not_after")))
    return out


def _build_parser():
    import argparse
    parser = argparse.ArgumentParser(prog="real_workspace_store", description="Publisher tool of the real gateway (R1; TEST installs).")
    parser.add_argument("--socket", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--lock-timeout-ms", type=int, default=DEFAULT_LOCK_TIMEOUT_MS)
    sub = parser.add_subparsers(dest="command", required=True)

    def decision(p):
        p.add_argument("--actor", required=True)
        p.add_argument("--pd", required=True)
        p.add_argument("--commit", required=True)
        p.add_argument("--sha", required=True)

    pub = sub.add_parser("publish")
    pub.add_argument("--proposal", required=True)
    pub.add_argument("--sidecar", action="append", default=[], help="a sidecar acquisition record file (repeatable, read-only); a REAL proposal needs one per member (O5)")
    pub.add_argument("--valid-until")
    pub.add_argument("--evidence-file", required=True)
    pub.add_argument("--rights-json")
    decision(pub)
    ren = sub.add_parser("renew")
    ren.add_argument("--context", required=True)
    ren.add_argument("--generation", type=int, required=True)
    ren.add_argument("--valid-until")
    ren.add_argument("--evidence-file", required=True)
    ren.add_argument("--rights-json")
    ren.add_argument("--names-mark", type=int)
    decision(ren)
    wd = sub.add_parser("withdraw")
    wd.add_argument("--context", required=True)
    wd.add_argument("--generation", type=int, required=True)
    decision(wd)
    st = sub.add_parser("status")
    st.add_argument("--context")
    return parser


def _read_kind_rows(conn, schema):
    """The install-kind rows the database holds (`rw_install_info()`, which the publisher may execute), as a tuple of kinds, or None when they
    cannot be read. Read on a transaction of its own, so the connection is IDLE again afterwards."""
    import psycopg
    try:
        with conn.transaction():
            return tuple(r[0] for r in query_all(conn, identifier(schema), "rw_install_info", ()))
    except (psycopg.Error, RealWorkspaceError):
        return None


def _run_gate(conn, args):
    """The preflight of design 1.2 for this tool's own connection (a non-superuser). Returns a `Decision`. Module-level so that a test of the
    command rule can put a failing decision in its place; it is not reachable from the command line."""
    from persistence import real_preflight
    return real_preflight.run_runtime_gate(conn, database=args.database, socket=args.socket)


def _default_connect(prompt):
    def connect(a):
        import psycopg
        from persistence import real_preflight as pf
        from persistence.connection import build_conninfo, is_reserved_real_name
        if is_reserved_real_name(a.database):
            # a name in the reserved namespace is a REAL target: scram from the first connection, the password from the terminal prompt alone.
            # `withdraw` connects under its own constant (design 5.1; R6 plan, OPEN): never gated, so never stopped by a stricter demand than the owner chose.
            require = pf.WITHDRAW_REQUIRE_AUTH if a.command == "withdraw" else pf.GATED_REQUIRE_AUTH
            return pf.connect_with_prompt(a.socket, a.database, a.user, require_auth=require, prompt=prompt)
        return psycopg.connect(build_conninfo(socket=a.socket, dbname=a.database, user=a.user), autocommit=False)
    return connect


def _with_gate_lines(result, lines):
    return CommandResult(result.status, result.outcome, tuple(lines) + result.lines, result.data)


def main(argv=None, *, connect=None, out=None, prompt=None):
    """Run one command; returns its exit status. `connect(args)` returns a psycopg connection (the tests' seam; the default connects to a
    TEST-named database with no credential, and to a name in the reserved namespace with `require_auth` and a password from `prompt`, which is the
    terminal prompt unless a test passes another).

    THE GATE (design 1.2 5.1, 5.2). The target is decided from the database's name and its install-kind rows (`decide_target`), never from an
    option. `publish` and `renew` run the preflight first against a REAL target and refuse, writing nothing, on any failure; a TEST target meets no
    preflight; a kind and name that disagree, or a missing kind row, refuse. `withdraw` is NEVER gated: it commits its drain mark first, waits and
    appends the generation, and only then, for a REAL target, runs the preflight and prints its result beside its own; its exit status is its own."""
    from persistence import prompt_route, real_preflight as pf
    out = out or sys.stdout
    args = _build_parser().parse_args(argv)
    try:
        prompt_route.require_genuine(pf)                 # TR7R4-L-1: before any prompt is built or used
    except prompt_route.PromptRouteError as error:
        print("REFUSED PUB_PROMPT_ROUTE: %s. Nothing was sent and nothing was written." % error.reason, file=out)
        return EXIT_REFUSED
    if connect is None:
        connect = _default_connect(prompt or pf.terminal_prompt)
    import psycopg
    try:
        conn = connect(args)
    except psycopg.Error as error:
        # No connection, so nothing was sent and nothing was recorded (a typed refusal, not a traceback).
        result = RealPublisher._refused(RealWorkspaceError("RW_CONNECT_FAILED", "%s %s" % (pf.classify_own_connection_error(str(error)), type(error).__name__)))
        print(result.text, file=out)
        return result.status
    post_withdrawal = False
    try:
        try:
            tool = RealPublisher(conn, args.schema, lock_timeout_ms=args.lock_timeout_ms)
            if args.command == "status":
                result = tool.status(args.context)
            else:
                # Inputs first: a malformed input is a refusal that sends nothing to the database (R1, L-8).
                ref = DecisionRef(args.pd, args.commit, args.sha)
                rights = _json_input(args.rights_json, "--rights-json") if getattr(args, "rights_json", None) else {k: True for k in RIGHTS}
                valid = parse_utc(args.valid_until, "valid-until") if getattr(args, "valid_until", None) else None
                if args.command == "publish":
                    proposal_bytes = _read_input(args.proposal, "the proposal", binary=True)
                    evidence = _read_evidence(args.evidence_file)
                    sidecar_bytes = tuple(_read_input(path, "a sidecar", binary=True) for path in args.sidecar)

                    def run_command():
                        return tool.publish(proposal_bytes, rights=rights, valid_until=valid, evidence=evidence, actor=args.actor, ref=ref,
                                            sidecars=sidecar_bytes)
                elif args.command == "renew":
                    evidence = _read_evidence(args.evidence_file)

                    def run_command():
                        return tool.renew(args.context, args.generation, rights=rights, valid_until=valid, evidence=evidence, actor=args.actor,
                                          ref=ref, names_mark=args.names_mark)
                else:
                    def run_command():
                        return tool.withdraw(args.context, args.generation, actor=args.actor, ref=ref)
                plan = pf.command_plan(args.command, pf.decide_target(args.database, _read_kind_rows(conn, args.schema)))
                gate_lines = []
                result = None
                if not plan.proceed:
                    result = RealPublisher._refused(RealWorkspaceError(plan.code, plan.detail))
                elif plan.preflight_before:
                    decision = _run_gate(conn, args)
                    gate_lines = list(decision.lines)
                    if not decision.ok:
                        refused = RealPublisher._refused(RealWorkspaceError("PF_PREFLIGHT_REFUSED", ", ".join(decision.codes())))
                        result = CommandResult(refused.status, refused.outcome, tuple(gate_lines) + refused.lines,
                                               dict(refused.data, preflight_codes=decision.codes()))
                if result is None:
                    result = run_command()
                    if gate_lines:
                        result = _with_gate_lines(result, gate_lines)
                    post_withdrawal = plan.preflight_after
        except RealWorkspaceError as refusal:
            result = RealPublisher._refused(refusal)
        # The command's own result is printed, and its status is fixed, BEFORE any post-withdrawal preflight runs (TR6B-L-2): the preflight can take
        # minutes (serial probe, timeouts), and an interrupt or any failure of it must change neither the withdrawal's lines nor its status.
        print(result.text, file=out)
        status = result.status
        if post_withdrawal:
            _print_post_withdrawal_preflight(conn, args, out)
        return status
    finally:
        conn.close()


def _print_post_withdrawal_preflight(conn, args, out):
    """AFTER the withdrawal, never before (design 5.1): a failing, timing-out, interrupted or refusing preflight changes nothing about the
    withdrawal. Everything is caught, `BaseException` included (Ctrl-C), and nothing is returned."""
    try:
        try:
            after = list(_run_gate(conn, args).lines)
        except BaseException as error:      # noqa: BLE001 - the withdrawal is done and printed; this report is best effort
            after = ["preflight could not run: %s" % type(error).__name__]
        print("-- preflight result (printed beside the withdrawal; it does not change the status above) --", file=out)
        for line in after:
            print(line, file=out)
    except BaseException:       # noqa: BLE001 - even printing is best effort once the withdrawal is reported
        pass


if __name__ == "__main__":
    raise SystemExit(main())
