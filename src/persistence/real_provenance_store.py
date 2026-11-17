"""F1 R2: the real gateway's candidate registry, DATABASE side in Python (design 3.3, 4.1, 4.2): N2a's store generalised to the three
scopes and re-targeted to the real gateway.

Three things live here and they are deliberately separate capabilities:

  * `RealProvenanceStore` is the LOADER's. It registers a candidate (`register`), reads one back (`load_context`) and settles an
    unknown registration (`reconcile`). It runs on the loader's connection and can call nothing else: the database grants the loader
    EXECUTE on the registry's put and get functions only (persistence/real_roles.py). It cannot publish; it has no lease.
  * `load_guarded` is the EXECUTOR's. It reads a registered candidate under an admitted lease, through `rwp_load_context`, which
    checks the lease again in the database (mode, head, generation, expiry kind, rights, root and, strictly, `complete_by`). Nothing
    else reads a candidate for an execution, so the guard is the only door.
  * `verify_registry_install` is the installer's check, run in the installer's transaction after the SQL: the registry's objects, ACLs
    and triggers are exactly what the shipped SQL defines, and the loader holds exactly its list.

THE LOADER AND LOGIN (exit statement R2 (b)). The install check accepts a loader with or without LOGIN. Every registry call checks in
the database that the caller's role CAN log in; a loader that the owner has set NOLOGIN (PD-0070 decision 1) is refused there
(`RW_PROV_ROLE_REFUSED`) even from a session opened earlier, while that session's own `md_*` INSERTs are unaffected.

COMMIT OUTCOMES. `register` runs the E4 rule of `OneTransaction` (design 3.1): before the commit point a gateway code is a refusal and
the transaction was rolled back; at or after it ONLY a gateway code on a connection back at IDLE is a refusal, and every other error is
UNKNOWN. Nothing is retried. `reconcile` re-reads the operation by id; a registration is idempotent by operation id.

This module reads no environment variable and takes no credential: a connection is handed in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import uuid

from marketdata.acquisition import TrustedAcquisitionWitness
from persistence import real_roles
from persistence.real_provenance import (ArtifactBundle, MemberKey, ProvenanceError, registration_request, registration_response,
                                         require_digest, sha256, validate_bundle, validate_loaded_bundle)
from persistence.real_scope import ScopeError, scope_by_snapshot_field
from persistence.real_workspace_context import (OneTransaction, RealWorkspaceError, database_refusal, identifier, query_one,
                                                require_in_transaction)
from persistence.real_workspace_store import AdmittedLease

DEFAULT_LOCK_TIMEOUT_MS = 10_000
TABLES = ("rwp_payload", "rwp_acquisition", "rwp_manifest", "rwp_context", "rwp_registration")
#: name -> (SECURITY DEFINER, volatility, argument count). The catalog check compares the installed functions with this table.
FUNCTIONS = {
    "rwp_json": (False, "i", 2), "rwp_keys": (False, "i", 2), "rwp_permits": (False, "i", 1), "rwp_origin": (False, "i", 2),
    "rwp_caller": (True, "s", 1), "rwp_validate_bundle": (False, "i", 5), "rwp_collect_context": (True, "s", 2),
    "rwp_guard": (True, "v", 1), "rwp_immutable": (False, "v", 0), "rwp_put_context": (True, "v", 7),
    "rwp_get_context": (True, "s", 2), "rwp_load_context": (True, "v", 2), "rwp_origin_failures": (True, "s", 1),
}
#: Who may EXECUTE what. The loader's two are the shared installer list (real_roles); the executor's one is granted by the SQL (R3
#: folds it into the executor's list); the publisher has none (publish reaches `rwp_origin_failures` through the owner's definer).
LOADER_EXECUTE = frozenset(name for name, _args in real_roles.LOADER_FUNCTIONS)
EXECUTOR_EXECUTE = frozenset(("rwp_load_context",))
_LOADABLE = ("EXECUTE_CREATE", "EXECUTE_REPRODUCE")


def _refusal(error):
    """The `ProvenanceError` for a database error, or None when it is not one the registry reports."""
    gateway = database_refusal(error)
    if gateway is not None:
        return ProvenanceError(gateway.code, gateway.codes[1:])
    if getattr(error, "sqlstate", None) == "42501":
        return ProvenanceError("RW_PROV_ROLE_REFUSED")
    return None


def _entry(conn):
    """The connection is IDLE and in autocommit: `transaction()` is then a real transaction, never a savepoint of an outer one."""
    from psycopg.pq import TransactionStatus
    if conn.info.transaction_status != TransactionStatus.IDLE or conn.autocommit is not True:
        raise ProvenanceError("RW_OUTER_TRANSACTION_REQUIRED")


def _role(conn, expected):
    """The session is the expected role, logged in as itself, with no SET ROLE. (Whether the role may log in is the database's check.)"""
    row = conn.execute("SELECT current_user::text,session_user::text,current_setting('role')").fetchone()
    if row is None or tuple(row) != (expected, expected, "none"):
        raise ProvenanceError("RW_PROV_ROLE_REFUSED")


def _query(conn, schema, function, values):
    from psycopg import sql
    return conn.execute(sql.SQL("SELECT * FROM {}.{}(" + ",".join(["%s"] * len(values)) + ")").format(
        sql.Identifier(schema), sql.Identifier(function)), values)


def _bytes(value):
    if type(value) not in (bytes, memoryview):
        raise ProvenanceError()
    return bytes(value)


def _expectations(members, witnesses):
    if type(members) is not tuple or not 1 <= len(members) <= 16 or any(type(x) is not MemberKey for x in members):
        raise ProvenanceError()
    keys = [x.sort_key() for x in members]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise ProvenanceError()
    if type(witnesses) is not tuple or len(witnesses) > 16 or any(type(x) is not TrustedAcquisitionWitness for x in witnesses):
        raise ProvenanceError("RW_PROV_BINDING_DIFFERS")
    keys = [x.expected_manifest_sha256 for x in witnesses]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise ProvenanceError("RW_PROV_BINDING_DIFFERS")


def _bundle(row):
    """The six-column row of the get and load functions as an `ArtifactBundle` and the registration response (or None)."""
    if row is None:
        raise ProvenanceError("RW_PROV_INPUT_MISSING")
    if len(row) != 6:
        raise ProvenanceError()
    raw, *arrays, response = row
    values = []
    for arr in arrays:
        if type(arr) not in (list, tuple) or len(arr) > 16:
            raise ProvenanceError()
        values.append(tuple((sha256(_bytes(x)), _bytes(x)) for x in arr))     # SQL order is kept; the validator rejects unsorted results
    return ArtifactBundle(_bytes(raw), *values), None if response is None else _bytes(response)


# =====================================================================================================================
# Results
# =====================================================================================================================
@dataclass(frozen=True)
class CommittedRegistration:
    operation_id: uuid.UUID
    response_bytes: bytes
    response_sha256: str
    persisted: bool = field(default=True, init=False)
    admitted: bool = field(default=False, init=False)           # a registration is never an admission


@dataclass(frozen=True)
class UnknownRegistration:
    operation_id: uuid.UUID
    disposition: str = field(default="UNKNOWN", init=False)


# =====================================================================================================================
# The loader's store
# =====================================================================================================================
class RealProvenanceStore(OneTransaction):
    """Register, read back and reconcile candidates on the LOADER's connection (IDLE, autocommit). It can call nothing but the
    registry's put and get functions: the role holds nothing else."""

    def __init__(self, conn, schema, *, loader_role, lock_timeout_ms=DEFAULT_LOCK_TIMEOUT_MS):
        self.conn, self.schema, self.loader_role = conn, identifier(schema), identifier(loader_role)
        if type(lock_timeout_ms) is not int or isinstance(lock_timeout_ms, bool) or not 1 <= lock_timeout_ms <= 600_000:
            raise ProvenanceError()
        self.lock_timeout_ms = lock_timeout_ms

    def register(self, scope, operation_id, bundle, *, expected_context_sha256, expected_members, witnesses):
        """Store a candidate. `scope` is a `ResolvedScope`. The candidate is validated in memory first (every byte, the scope's rules and,
        in the REAL scope, O1 to O3 with every failed code), then registered by the loader's put function and read back by the loader's
        get function inside the same transaction. Returns `CommittedRegistration` or `UnknownRegistration`; raises `ProvenanceError` for
        a definite refusal (nothing was recorded). A candidate is stored, never admitted."""
        if type(operation_id) is not uuid.UUID:
            raise ProvenanceError()
        context = validate_bundle(scope, bundle, expected_context_sha256=expected_context_sha256, expected_members=expected_members,
                                  witnesses=witnesses)
        request = registration_request(operation_id, context)
        expected_response = registration_response(operation_id, request, context)
        arrays = [[raw for _key, raw in x] for x in (bundle.payloads, bundle.manifests, bundle.envelopes, bundle.witnesses)]
        _entry(self.conn)
        _role(self.conn, self.loader_role)

        def work(conn):
            row = _query(conn, self.schema, "rwp_put_context", (operation_id, request, bundle.context_bytes, *arrays)).fetchone()
            if row is None or _bytes(row[0]) != expected_response:
                raise ProvenanceError("RW_PROV_BINDING_DIFFERS")
            stored_bundle, original = _bundle(_query(conn, self.schema, "rwp_get_context", (None, operation_id)).fetchone())
            validate_bundle(scope, stored_bundle, expected_context_sha256=expected_context_sha256, expected_members=expected_members,
                            witnesses=witnesses)
            if original != expected_response:
                raise ProvenanceError("RW_PROV_BINDING_DIFFERS")
            return original
        state, value = self._transact(work)
        if state == "REFUSED":
            raise ProvenanceError(value.code, value.codes[1:])
        if state == "LOCK_TIMEOUT":
            raise ProvenanceError("RW_PROV_LOCK_TIMEOUT")
        if state == "UNKNOWN":
            return UnknownRegistration(operation_id)
        return CommittedRegistration(operation_id, value, sha256(value))

    def load_context(self, scope, context_sha256, *, expected_members, witnesses):
        """Read a registered candidate back by its digest, as the loader, and validate every byte. The payload bytes are returned (the
        registry's get function returns them: design 3.3, TR5-M1). Not an admission and not a guarded load."""
        require_digest(context_sha256)
        _expectations(expected_members, witnesses)
        _entry(self.conn)
        _role(self.conn, self.loader_role)
        import psycopg
        try:
            with self.conn.transaction():
                bundle, response = _bundle(_query(self.conn, self.schema, "rwp_get_context", (context_sha256, None)).fetchone())
                if response is not None:
                    raise ProvenanceError("RW_PROV_BINDING_DIFFERS")
                return validate_bundle(scope, bundle, expected_context_sha256=context_sha256, expected_members=expected_members,
                                       witnesses=witnesses)
        except psycopg.Error as error:
            refusal = _refusal(error)
            if refusal is None:
                raise
            raise refusal from None

    def reconcile(self, scope, operation_id, *, expected_request_sha256, expected_context_sha256, expected_members, witnesses):
        """Settle an unknown registration by its operation id: `CommittedRegistration` when it is stored and equals what the identical
        command would have written, `UnknownRegistration` when it is not found. A stored registration that differs is a conflict."""
        if type(operation_id) is not uuid.UUID:
            raise ProvenanceError()
        require_digest(expected_request_sha256)
        require_digest(expected_context_sha256)
        _expectations(expected_members, witnesses)
        _entry(self.conn)
        _role(self.conn, self.loader_role)
        import psycopg
        try:
            with self.conn.transaction():
                row = _query(self.conn, self.schema, "rwp_get_context", (None, operation_id)).fetchone()
                if row is None:
                    return UnknownRegistration(operation_id)
                bundle, original = _bundle(row)
                context = validate_bundle(scope, bundle, expected_context_sha256=expected_context_sha256,
                                          expected_members=expected_members, witnesses=witnesses)
                request = registration_request(operation_id, context)
                if sha256(request) != expected_request_sha256 or original != registration_response(operation_id, request, context):
                    raise ProvenanceError("RW_PROV_OPERATION_CONFLICT")
            return CommittedRegistration(operation_id, original, sha256(original))
        except psycopg.Error as error:
            refusal = _refusal(error)
            if refusal is None:
                return UnknownRegistration(operation_id)
            raise refusal from None


# =====================================================================================================================
# The executor's guarded load
# =====================================================================================================================
def load_guarded(conn, schema, executor_role, lease, context_sha256, *, expected_members, witnesses):
    """Read a registered candidate under an admitted lease, in the caller's open transaction on the EXECUTOR's connection.

    The database checks the lease again (`rwp_guard`): mode, head, generation, the re-derived expiry kind, rights, root and the lease's
    `complete_by`, refusing AT OR AFTER it with `RW_DEADLINE`. Only a registration bound to the lease's own context is returned. The scope
    is read from the lease's snapshot (data: the proposal verifier's rule), never granted here. Raises `ProvenanceError`."""
    import psycopg
    require_digest(context_sha256)
    _expectations(expected_members, witnesses)
    schema = identifier(schema)
    if type(lease) is not AdmittedLease or lease.purpose not in _LOADABLE:
        raise ProvenanceError("RW_PROV_LEASE_REQUIRED")
    try:
        require_in_transaction(conn)
    except RealWorkspaceError:
        raise ProvenanceError("RW_PROV_LEASE_REQUIRED") from None
    _role(conn, identifier(executor_role))
    try:
        snapshot = json.loads(lease.snapshot.decode("utf8"))
        scope = scope_by_snapshot_field(snapshot.get("scope"))
        snapshot_members = {(m["payload_sha256"], m["manifest_sha256"]) for m in snapshot["members"]}
    except (ValueError, KeyError, TypeError, AttributeError, ScopeError):
        raise ProvenanceError("RW_PROV_SCOPE_REFUSED") from None
    if sha256(lease.snapshot) != lease.context_id:
        raise ProvenanceError("RW_PROV_CONTEXT_DIFFERS")
    try:
        row = _query(conn, schema, "rwp_load_context", (context_sha256, lease.purpose)).fetchone()
        bundle, response = _bundle(row)
        context = validate_loaded_bundle(scope, bundle, expected_context_sha256=context_sha256, expected_members=expected_members,
                                         witnesses=witnesses)
    except psycopg.Error as error:
        refusal = _refusal(error)
        if refusal is None:
            raise
        raise refusal from None
    if response is not None or context.financial_context_sha256 != lease.context_id:
        raise ProvenanceError("RW_PROV_CONTEXT_DIFFERS")
    if {(m.payload_sha256, m.manifest_sha256) for m in context.members} != snapshot_members:
        raise ProvenanceError("RW_PROV_BINDING_DIFFERS")
    return context


# =====================================================================================================================
# The installer's check
# =====================================================================================================================
def verify_registry_install(conn, schema, owner_role, executor_role, loader_role, publisher_role=None):
    """Read the catalog in the installer's transaction and refuse (`RW_INSTALL_REFUSED`, DETAIL names the first difference) unless the
    registry is exactly what the shipped SQL defines and the loader holds exactly its list. Accepts a loader with or without LOGIN."""
    schema, owner_role, executor_role, loader_role = (identifier(x) for x in (schema, owner_role, executor_role, loader_role))
    roles = {"loader": loader_role, "executor": executor_role}
    if publisher_role is not None:
        roles["publisher"] = identifier(publisher_role)

    def refuse(why):
        raise RealWorkspaceError("RW_INSTALL_REFUSED", why)

    rows = conn.execute(
        "SELECT p.proname,p.pronargs,p.prosecdef,p.provolatile,p.proowner::regrole::text,p.proconfig,"
        "EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE'),"
        "has_function_privilege(%s,p.oid,'EXECUTE'),has_function_privilege(%s,p.oid,'EXECUTE'),"
        "CASE WHEN %s::name IS NULL THEN false ELSE has_function_privilege(%s::name,p.oid,'EXECUTE') END "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND left(p.proname,4)='rwp_' ORDER BY p.proname",
        (loader_role, executor_role, roles.get("publisher"), roles.get("publisher"), schema)).fetchall()
    if {r[0] for r in rows} != set(FUNCTIONS) or len(rows) != len(FUNCTIONS):
        refuse("the registry's functions differ from the shipped set")
    for name, nargs, definer, volatility, owner, config, public_exec, loader_exec, executor_exec, publisher_exec in rows:
        if (FUNCTIONS[name] != (definer, volatility, nargs) or owner != owner_role or public_exec
                or loader_exec != (name in LOADER_EXECUTE) or executor_exec != (name in EXECUTOR_EXECUTE) or publisher_exec
                or not config or [x.replace(" ", "") for x in config] != ["search_path=pg_catalog," + schema + ",pg_temp"]):
            refuse("function %s differs from the shipped definition or its ACL" % name)
    rows = conn.execute("SELECT c.relname,c.relowner::regrole::text,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND left(c.relname,4)='rwp_' AND c.relkind='r' "
                        "ORDER BY c.relname", (schema,)).fetchall()
    if {r[0] for r in rows} != set(TABLES) or any(r[1:] != (owner_role, False, False) for r in rows):
        refuse("the registry's tables differ from the shipped set")
    triggers = conn.execute("SELECT t.tgname,c.relname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE n.nspname=%s AND left(c.relname,4)='rwp_' AND NOT t.tgisinternal", (schema,)).fetchall()
    if set(triggers) != {(t + suffix, t) for t in TABLES for suffix in ("_immutable_rows", "_immutable_truncate")}:
        refuse("the registry's immutability triggers differ from the shipped set")
    for table in TABLES:
        for role in roles.values():
            if conn.execute("SELECT has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')",
                            (role, schema + "." + table)).fetchone()[0]:
                refuse("role %s holds a privilege on %s" % (role, table))
    actual = real_roles.loader_catalog(conn, schema, loader_role)
    if actual != real_roles.loader_catalog_expected():
        refuse("the loader's privileges differ from its list: %s" % real_roles.catalog_difference(actual))
