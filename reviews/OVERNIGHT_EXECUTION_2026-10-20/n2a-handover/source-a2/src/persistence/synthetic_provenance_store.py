"""Explicit synthetic metadata repository; no provider, runtime or HTTP factory.

Only registration owns writes. Real PostgreSQL COMMIT/identity/lease gates are
required; typed Python witnesses are trusted-operator integrity expectations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import uuid

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from marketdata.acquisition import TrustedAcquisitionWitness
from marketdata.canonical import canonical_json
from marketdata.synthetic_provenance import (ProvenanceError, SyntheticArtifactBundle,
    SyntheticMemberKey, ValidatedSyntheticContext, registration_request, registration_response,
    require_digest, sha256, validate_bundle)
from persistence.guarded_workspace_context import ExecutionScope

TABLES = ("np_payload", "np_acquisition", "np_manifest", "np_context", "np_registration")
FUNCTIONS = {
 "np_json": (False, "i", 2), "np_keys": (False, "i", 2),
 "np_caller": (True, "s", 1), "np_validate_bundle": (False, "i", 5),
 "np_collect_context": (True, "s", 2), "np_guard": (True, "v", 1),
 "np_immutable": (False, "v", 0), "np_put_context": (True, "v", 7),
 "np_get_context": (True, "s", 2), "np_load_context": (True, "v", 2),
}
NP_CODES = frozenset("NP_SHAPE NP_SCOPE_REFUSED NP_UNSUPPORTED_PROVENANCE NP_INPUT_MISSING NP_BINDING_DIFFERS NP_STORAGE_CONFLICT NP_OPERATION_CONFLICT NP_CONTEXT_DIFFERS NP_OUTER_TRANSACTION_REQUIRED NP_LEASE_REQUIRED NP_CAPACITY NP_ROLE_REFUSED NP_INSTALL_REFUSED".split())
F2_CODES = frozenset("F2_ISOLATION F2_MODE_HOLD F2_SCOPE_DIFFERS F2_GENERATION_DIFFERS F2_EXPIRY_HOLD F2_RIGHT_REFUSED F2_NOT_FOUND F2_SINGLE_SCOPE".split())
IDENT = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")


def _identifier(value):
    if type(value) is not str or IDENT.fullmatch(value) is None:
        raise ProvenanceError()
    return value


def _entry(conn):
    # These properties are checked BEFORE any identity/metadata SELECT. A false
    # autocommit otherwise turns transaction() into an implicit savepoint.
    if conn.info.transaction_status != TransactionStatus.IDLE or conn.autocommit is not True:
        raise ProvenanceError("NP_OUTER_TRANSACTION_REQUIRED")


def _role(conn, expected, *, owner=False):
    row = conn.execute("SELECT current_user::text,session_user::text,current_setting('role')").fetchone()
    if row is None or row[0] != expected or not owner and tuple(row) != (expected, expected, "none"):
        raise ProvenanceError("NP_ROLE_REFUSED")
    flags = conn.execute("SELECT r.rolcanlogin,r.rolinherit,r.rolsuper,r.rolbypassrls,r.rolcreatedb,r.rolcreaterole,r.rolreplication,"
        "EXISTS(SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid OR m.roleid=r.oid) FROM pg_roles r WHERE r.rolname=%s", (expected,)).fetchone()
    if flags != (not owner, False, False, False, False, False, False, False):
        raise ProvenanceError("NP_ROLE_REFUSED")


def _query(conn, schema, function, values):
    return conn.execute(sql.SQL("SELECT * FROM {}.{}(" + ",".join(["%s"] * len(values)) + ")").format(
        sql.Identifier(schema), sql.Identifier(function)), values)


def _translate(error):
    primary = getattr(getattr(error, "diag", None), "message_primary", None)
    if primary in NP_CODES or primary in F2_CODES:
        raise ProvenanceError(primary) from None
    code = getattr(error, "sqlstate", None) or ""
    if code.startswith("22"):
        raise ProvenanceError("NP_SHAPE") from None
    if code == "23503":
        raise ProvenanceError("NP_INPUT_MISSING") from None
    if code == "42501":
        raise ProvenanceError("NP_ROLE_REFUSED") from None
    # No arbitrary PostgreSQL diagnostic, caller value, or credential is echoed.


def _f2_recordset(conn, schema):
    functions = []
    rows = conn.execute("SELECT p.proname,pg_get_function_identity_arguments(p.oid),pg_get_functiondef(p.oid),"
        "p.proowner::regrole::text,CASE WHEN p.proacl IS NULL THEN NULL ELSE ARRAY(SELECT a::text FROM unnest(p.proacl) a ORDER BY a::text) END,"
        "p.prosecdef,p.provolatile,CASE WHEN p.proconfig IS NULL THEN NULL ELSE ARRAY(SELECT c FROM unnest(p.proconfig) c ORDER BY c) END "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND left(p.proname,3)='gw_' ORDER BY p.proname,pg_get_function_identity_arguments(p.oid)", (schema,)).fetchall()
    names = ("name", "identity_arguments", "definition", "owner", "acl", "security_definer", "volatility", "config")
    for row in rows:
        functions.append(dict(zip(names, row)))
    relations = []
    rows = conn.execute("SELECT c.oid,c.relname,c.relowner::regrole::text,CASE WHEN c.relacl IS NULL THEN NULL ELSE ARRAY(SELECT a::text FROM unnest(c.relacl) a ORDER BY a::text) END,c.relrowsecurity,c.relforcerowsecurity "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND left(c.relname,3)='gw_' AND c.relkind='r' ORDER BY c.relname", (schema,)).fetchall()
    for oid, name, owner, acl, rls, force in rows:
        constraints = [dict(zip(("name", "type", "deferrable", "deferred", "definition"), x)) for x in conn.execute(
            "SELECT conname,contype,condeferrable,condeferred,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s ORDER BY conname", (oid,)).fetchall()]
        relations.append(dict(name=name, owner=owner, acl=acl, row_security=rls, force_row_security=force, constraints=constraints))
    return dict(functions=functions, relations=relations)


def fingerprint_installed_f2(conn, *, schema):
    """Read-only explicit operator helper; NOT an independent expected value."""
    return sha256(canonical_json(_f2_recordset(conn, _identifier(schema))).encode("utf8"))


def install_synthetic_provenance(conn, *, schema, owner_role, loader_role, executor_role, expected_f2_fingerprint):
    names = tuple(_identifier(x) for x in (schema, owner_role, loader_role, executor_role))
    if len(set(names[1:])) != 3:
        raise ProvenanceError("NP_INSTALL_REFUSED")
    require_digest(expected_f2_fingerprint)
    _entry(conn)
    with conn.transaction():
        _role(conn, owner_role, owner=True)
        for role, login in ((loader_role, True), (executor_role, True)):
            flags = conn.execute("SELECT r.rolcanlogin,r.rolinherit,r.rolsuper,r.rolbypassrls,r.rolcreatedb,r.rolcreaterole,r.rolreplication,"
                "EXISTS(SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid OR m.roleid=r.oid) FROM pg_roles r WHERE r.rolname=%s", (role,)).fetchone()
            if flags != (login, False, False, False, False, False, False, False):
                raise ProvenanceError("NP_INSTALL_REFUSED")
        owner = conn.execute("SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname=%s", (schema,)).fetchone()
        if owner != (owner_role,):
            raise ProvenanceError("NP_INSTALL_REFUSED")
        for catalog, namespace, name in (("pg_class", "relnamespace", "relname"), ("pg_type", "typnamespace", "typname"), ("pg_proc", "pronamespace", "proname")):
            if conn.execute(sql.SQL("SELECT EXISTS(SELECT 1 FROM pg_catalog.{} x JOIN pg_namespace n ON n.oid=x.{} WHERE n.nspname=%s AND left(x.{},3)='np_')").format(
                    sql.Identifier(catalog), sql.Identifier(namespace), sql.Identifier(name)), (schema,)).fetchone()[0]:
                raise ProvenanceError("NP_INSTALL_REFUSED")
        before = _f2_recordset(conn, schema)
        if (sha256(canonical_json(before).encode("utf8")) != expected_f2_fingerprint
                or len(before["relations"]) != 9 or not {"gw_mode", "gw_head", "gw_lease", "gw_root", "gw_snapshot"}.issubset({x["name"] for x in before["relations"]})
                or not {"gw_admit", "gw_scope", "gw_rights_valid", "gw_validate"}.issubset({x["name"] for x in before["functions"]})):
            raise ProvenanceError("NP_INSTALL_REFUSED")
        body = Path(__file__).with_name("synthetic_provenance_v1.sql").read_text("utf8")
        for marker, name in zip(("__NP_SCHEMA__", "__NP_OWNER__", "__NP_LOADER__", "__NP_EXECUTOR__"), names):
            body = body.replace(marker, name)
        conn.execute(body)
        if _f2_recordset(conn, schema) != before:
            raise ProvenanceError("NP_INSTALL_REFUSED")
        rows = conn.execute("SELECT p.proname,p.pronargs,p.prosecdef,p.provolatile,p.proowner::regrole::text,p.proconfig,"
            "has_function_privilege(%s,p.oid,'EXECUTE'),has_function_privilege(%s,p.oid,'EXECUTE'),"
            "EXISTS(SELECT 1 FROM aclexplode(p.proacl) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE') "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND left(p.proname,3)='np_' ORDER BY p.proname", (loader_role, executor_role, schema)).fetchall()
        if len(rows) != len(FUNCTIONS):
            raise ProvenanceError("NP_INSTALL_REFUSED")
        for name, nargs, definer, volatility, owner, config, loader_exec, app_exec, public_exec in rows:
            if (FUNCTIONS.get(name) != (definer, volatility, nargs) or owner != owner_role or public_exec
                    or loader_exec != (name in ("np_put_context", "np_get_context")) or app_exec != (name == "np_load_context")
                    or not config or [x.replace(" ", "") for x in config] != ["search_path=pg_catalog," + schema + ",pg_temp"]):
                raise ProvenanceError("NP_INSTALL_REFUSED")
        rows = conn.execute("SELECT c.relname,c.relowner::regrole::text,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND left(c.relname,3)='np_' AND c.relkind='r' ORDER BY c.relname", (schema,)).fetchall()
        if {x[0] for x in rows} != set(TABLES) or any(x[1:] != (owner_role, False, False) for x in rows):
            raise ProvenanceError("NP_INSTALL_REFUSED")
        triggers = conn.execute("SELECT t.tgname,c.relname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND left(c.relname,3)='np_' AND NOT t.tgisinternal", (schema,)).fetchall()
        if set(triggers) != {(t + suffix, t) for t in TABLES for suffix in ("_immutable_rows", "_immutable_truncate")}:
            raise ProvenanceError("NP_INSTALL_REFUSED")
        for table in TABLES:
            for role in (loader_role, executor_role):
                if conn.execute("SELECT has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')", (role, schema + "." + table)).fetchone()[0]:
                    raise ProvenanceError("NP_INSTALL_REFUSED")
    _entry(conn)


@dataclass(frozen=True)
class CommittedSyntheticRegistration:
    operation_id: uuid.UUID
    response_bytes: bytes
    response_sha256: str
    persisted: bool = field(default=True, init=False)
    synthetic: bool = field(default=True, init=False)


@dataclass(frozen=True)
class UnknownSyntheticRegistration:
    operation_id: uuid.UUID
    disposition: str = field(default="UNKNOWN", init=False)


def _expectations(members, witnesses):
    if type(members) is not tuple or not 1 <= len(members) <= 16 or any(type(x) is not SyntheticMemberKey for x in members):
        raise ProvenanceError()
    keys = [x.sort_key() for x in members]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise ProvenanceError()
    if type(witnesses) is not tuple or len(witnesses) > 16 or any(type(x) is not TrustedAcquisitionWitness for x in witnesses):
        raise ProvenanceError("NP_BINDING_DIFFERS")
    keys = [x.expected_manifest_sha256 for x in witnesses]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise ProvenanceError("NP_BINDING_DIFFERS")


def _bytes(value):
    if type(value) not in (bytes, memoryview):
        raise ProvenanceError("NP_SHAPE")
    return bytes(value)


def _loaded(row, context_sha, members, witnesses):
    if row is None:
        raise ProvenanceError("NP_INPUT_MISSING")
    if len(row) != 6:
        raise ProvenanceError()
    raw, *arrays, response = row
    values = []
    for arr in arrays:
        if type(arr) not in (list, tuple) or len(arr) > 16:
            raise ProvenanceError()
        # Preserve SQL order; validate_bundle rejects unsorted results.
        values.append(tuple((sha256(_bytes(x)), _bytes(x)) for x in arr))
    bundle = SyntheticArtifactBundle(_bytes(raw), *values)
    context = validate_bundle(bundle, expected_context_sha256=context_sha, expected_members=members, witnesses=witnesses)
    return context, None if response is None else _bytes(response)


class SyntheticProvenanceStore:
    def __init__(self, connect, *, schema, loader_role, executor_role):
        if not callable(connect):
            raise ProvenanceError()
        self.connect = connect
        self.schema, self.loader_role, self.executor_role = (_identifier(x) for x in (schema, loader_role, executor_role))
        if self.loader_role == self.executor_role:
            raise ProvenanceError()

    @staticmethod
    def _before_commit(conn):
        if conn.info.transaction_status != TransactionStatus.INTRANS:
            raise ProvenanceError("NP_OUTER_TRANSACTION_REQUIRED")

    @staticmethod
    def _after_commit_ack(conn):
        _entry(conn)

    def register(self, operation_id, bundle, *, expected_context_sha256, expected_members, witnesses):
        if type(operation_id) is not uuid.UUID:
            raise ProvenanceError()
        context = validate_bundle(bundle, expected_context_sha256=expected_context_sha256, expected_members=expected_members, witnesses=witnesses)
        request = registration_request(operation_id, context)
        expected_response = registration_response(operation_id, request, context)
        arrays = [list(raw for _, raw in x) for x in (bundle.payloads, bundle.manifests, bundle.envelopes, bundle.witnesses)]
        try:
            with self.connect() as conn:
                _entry(conn)
                _role(conn, self.loader_role)
                with conn.transaction():
                    row = _query(conn, self.schema, "np_put_context", (operation_id, request, bundle.context_bytes, *arrays)).fetchone()
                    if row is None or _bytes(row[0]) != expected_response:
                        raise ProvenanceError("NP_BINDING_DIFFERS")
                    stored = _query(conn, self.schema, "np_get_context", (None, operation_id)).fetchone()
                    _, original = _loaded(stored, expected_context_sha256, expected_members, witnesses)
                    if original != expected_response:
                        raise ProvenanceError("NP_BINDING_DIFFERS")
                    self._before_commit(conn)
                _entry(conn)
                self._after_commit_ack(conn)
            return CommittedSyntheticRegistration(operation_id, expected_response, sha256(expected_response))
        except psycopg.Error as exc:
            _translate(exc)
            return UnknownSyntheticRegistration(operation_id)

    def load_context(self, context_sha256, *, expected_members, witnesses):
        require_digest(context_sha256)
        _expectations(expected_members, witnesses)
        try:
            with self.connect() as conn:
                _entry(conn)
                _role(conn, self.loader_role)
                with conn.transaction():
                    row = _query(conn, self.schema, "np_get_context", (context_sha256, None)).fetchone()
                    context, response = _loaded(row, context_sha256, expected_members, witnesses)
                    if response is not None:
                        raise ProvenanceError("NP_BINDING_DIFFERS")
                _entry(conn)
            return context
        except psycopg.Error as exc:
            _translate(exc)
            raise ProvenanceError("NP_INPUT_MISSING") from None

    def load_guarded(self, conn, scope, context_sha256, *, expected_members, witnesses):
        require_digest(context_sha256)
        _expectations(expected_members, witnesses)
        if type(scope) is not ExecutionScope or scope.schema != self.schema or conn.info.transaction_status != TransactionStatus.INTRANS:
            raise ProvenanceError("NP_LEASE_REQUIRED")
        scope.assert_current(conn)
        _role(conn, self.executor_role)
        try:
            row = _query(conn, self.schema, "np_load_context", (context_sha256, scope.purpose)).fetchone()
            context, response = _loaded(row, context_sha256, expected_members, witnesses)
            if response is not None or context.financial_context_sha256 != scope.context_id:
                raise ProvenanceError("NP_CONTEXT_DIFFERS")
            scope.assert_current(conn)
            return context
        except psycopg.Error as exc:
            _translate(exc)
            raise ProvenanceError("NP_INPUT_MISSING") from None

    def reconcile(self, operation_id, *, expected_request_sha256, expected_context_sha256, expected_members, witnesses):
        if type(operation_id) is not uuid.UUID:
            raise ProvenanceError()
        require_digest(expected_request_sha256)
        require_digest(expected_context_sha256)
        _expectations(expected_members, witnesses)
        try:
            with self.connect() as conn:
                _entry(conn)
                _role(conn, self.loader_role)
                with conn.transaction():
                    row = _query(conn, self.schema, "np_get_context", (None, operation_id)).fetchone()
                    if row is None:
                        return UnknownSyntheticRegistration(operation_id)
                    context, original = _loaded(row, expected_context_sha256, expected_members, witnesses)
                    request = registration_request(operation_id, context)
                    expected = registration_response(operation_id, request, context)
                    if sha256(request) != expected_request_sha256 or original != expected:
                        raise ProvenanceError("NP_OPERATION_CONFLICT")
                _entry(conn)
            return CommittedSyntheticRegistration(operation_id, original, sha256(original))
        except psycopg.Error as exc:
            _translate(exc)
            return UnknownSyntheticRegistration(operation_id)
