"""F1 R2: the role-grant lists of the real gateway's SHARED INSTALLER CODE (design 3.3, 4.2 build table, PD-0070 decision 1).

One list, in one place, for every install kind. R2 fixes the LOADER's list; R3 adds the executor's and moves the publisher's here, and
builds the catalog audit that compares a role with its list. Nothing in this module opens a connection: it returns data and SQL text.

THE LOADER'S LIST (design 3.3 "The narrowing"; PD-0070 decision 1 keeps it, "with no further narrowing"):

    INSERT   on the thirteen md_* tables;
    SELECT   on md_file and md_release, and on nothing else;
    EXECUTE  on the registry's put function and its get function, and on nothing else;
    USAGE    on the gateway schema (granted by the gateway SQL; without it no object of the schema can be named at all).

Why the two SELECTs (read from the HEAD code and the migrations, and shown by R2's test that loads as the loader):
  * `md_file`: `INSERT ... ON CONFLICT (file_sha256) DO NOTHING RETURNING file_sha256` needs SELECT on the columns it names, and a
    conflict re-reads the stored manifest (`market_data_store._insert_files`);
  * `md_release`: the idempotence check (`write_release` reads `projection_digest`) and the sealed-release trigger, which has no
    SECURITY DEFINER and reads `md_release.release_id` and `append_xid` with the inserting role's own privileges.
The loader passes `count_rows=False` to `write_release`: the per-table count read-back would need SELECT on the other eleven tables and
is not loading.

What the list does NOT include, deliberately: SELECT on md_quote or any other observation table (the loader reads no quote), UPDATE,
DELETE, TRUNCATE, REFERENCES, TRIGGER, MAINTAIN, any column-level privilege, any sequence privilege, any privilege on a gateway table
and EXECUTE on any other function. PUBLIC's default EXECUTE on the twelve migration functions is revoked by R3's statement; until then
"no other function" is not asserted by any test (design 7.1, R2 and R3 rows).

A widening of this list is a decision for the owner, not an edit: if a load as the loader fails with `42501` the list does not suffice,
and that is a finding.
"""
from __future__ import annotations

from persistence.real_workspace_context import identifier

#: The thirteen md_* tables, in the order of `persistence.market_data_store.MD_TABLES` (a test compares the two, and the catalog).
MD_TABLES = (
    "md_file", "md_release", "md_release_file", "md_quote", "md_fx_rate", "md_corporate_action",
    "md_benchmark", "md_benchmark_point", "md_adjusted_quote", "md_calendar", "md_series_exclusion",
    "md_risk_free", "md_risk_free_point",
)

LOADER_INSERT_TABLES = MD_TABLES
LOADER_SELECT_TABLES = ("md_file", "md_release")

#: The registry's two loader functions: (name, argument TYPES). The put function registers a candidate; the get function returns the
#: stored bundle, payload bytes included (design 3.3, technical TR5-M1: the owner did not take the narrower option).
REGISTRY_PUT = ("rwp_put_context", "uuid,bytea,bytea,bytea[],bytea[],bytea[],bytea[]")
REGISTRY_GET = ("rwp_get_context", "text,uuid")
LOADER_FUNCTIONS = (REGISTRY_PUT, REGISTRY_GET)


def loader_expected():
    """The loader's exact privileges as data, for the catalog assertion and for R3's audit:
    {"table_privileges": {table: frozenset(privileges)}, "functions": frozenset(function names)}."""
    tables = {t: frozenset(("INSERT", "SELECT") if t in LOADER_SELECT_TABLES else ("INSERT",)) for t in LOADER_INSERT_TABLES}
    return {"table_privileges": tables, "functions": frozenset(name for name, _args in LOADER_FUNCTIONS)}


def loader_grant_statements(schema, loader_role):
    """The GRANT statements of the loader's list, as plain SQL text (identifiers are validated, then double-quoted)."""
    schema, role = identifier(schema), identifier(loader_role)
    qs, qr = '"%s"' % schema, '"%s"' % role
    statements = ["GRANT INSERT ON %s TO %s" % (", ".join("%s.%s" % (qs, t) for t in LOADER_INSERT_TABLES), qr),
                  "GRANT SELECT ON %s TO %s" % (", ".join("%s.%s" % (qs, t) for t in LOADER_SELECT_TABLES), qr)]
    for name, arguments in LOADER_FUNCTIONS:
        statements.append("GRANT EXECUTE ON FUNCTION %s.%s(%s) TO %s" % (qs, name, arguments, qr))
    return statements


_TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def loader_catalog_expected():
    """What `loader_catalog` returns for a loader that holds exactly its list (and USAGE on the schema, nothing else)."""
    expected = loader_expected()
    return {"schema": (True, False), "table_privileges": expected["table_privileges"], "column_acl": frozenset(),
            "gateway_table_privileges": frozenset(), "sequences": frozenset(), "functions": expected["functions"],
            "grantable": frozenset()}


def loader_catalog(conn, schema, role):
    """The loader's ACTUAL privileges in the gateway schema, read from the catalog (read-only; `has_*_privilege` includes what the role
    gets through PUBLIC). Same shape as `loader_catalog_expected`:

      schema                    (USAGE, CREATE) on the schema;
      table_privileges          for each md_* table, the table privileges the role holds (MAINTAIN too on PostgreSQL 17 and later);
      column_acl                md_* tables with a COLUMN-level ACL entry for the role;
      gateway_table_privileges  (table, privilege) for every privilege on an rw_* or rwp_* table;
      sequences                 sequences of the schema on which the role holds any privilege;
      functions                 names of the rw_* and rwp_* functions the role may EXECUTE;
      grantable                 objects (tables, functions, the schema, columns) on which the role holds a privilege WITH GRANT OPTION.

    The migration functions of the schema are NOT listed: PUBLIC's default EXECUTE on them is R3's revoke, and until then no test
    asserts "no other function" (design 7.1, R2 and R3 rows)."""
    schema, role = identifier(schema), identifier(role)
    privileges = _TABLE_PRIVILEGES + (("MAINTAIN",) if int(conn.execute("SHOW server_version_num").fetchone()[0]) >= 170000 else ())
    usage, create = conn.execute("SELECT has_schema_privilege(%s::name,%s::name,'USAGE'),has_schema_privilege(%s::name,%s::name,'CREATE')",
                                 (role, schema, role, schema)).fetchone()
    tables = {}
    for table in MD_TABLES:
        qualified = '"%s"."%s"' % (schema, table)
        tables[table] = frozenset(p for p in privileges if conn.execute("SELECT has_table_privilege(%s::name,%s::regclass,%s)",
                                                                        (role, qualified, p)).fetchone()[0])
    column_acl = frozenset(r[0] for r in conn.execute(
        "SELECT DISTINCT c.relname FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "CROSS JOIN LATERAL aclexplode(a.attacl) x WHERE n.nspname=%s AND c.relname LIKE 'md\\_%%' AND a.attacl IS NOT NULL "
        "AND x.grantee=(SELECT oid FROM pg_roles WHERE rolname=%s)", (schema, role)).fetchall())
    gateway = frozenset((r[0], p) for r in conn.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='r' "
        "AND c.relname LIKE 'rw%%'", (schema,)).fetchall() for p in privileges if conn.execute(
            "SELECT has_table_privilege(%s::name,%s::regclass,%s)", (role, '"%s"."%s"' % (schema, r[0]), p)).fetchone()[0])
    sequences = frozenset(r[0] for r in conn.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='S' "
        "AND CASE WHEN c.relkind='S' THEN has_sequence_privilege(%s::name,c.oid,'USAGE,SELECT,UPDATE') ELSE false END",
        (schema, role)).fetchall())
    functions = frozenset(r[0] for r in conn.execute(
        "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND p.proname LIKE 'rw%%' "
        "AND has_function_privilege(%s::name,p.oid,'EXECUTE')", (schema, role)).fetchall())
    grantee = "x.grantee=(SELECT oid FROM pg_roles WHERE rolname=%s) AND x.is_grantable"
    grantable = frozenset(r[0] for r in conn.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(c.relacl) x "
        "WHERE n.nspname=%s AND " + grantee + " UNION ALL "
        "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(p.proacl) x "
        "WHERE n.nspname=%s AND " + grantee + " UNION ALL "
        "SELECT n.nspname FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) x WHERE n.nspname=%s AND " + grantee + " UNION ALL "
        "SELECT c.relname FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "CROSS JOIN LATERAL aclexplode(a.attacl) x WHERE n.nspname=%s AND a.attacl IS NOT NULL AND " + grantee,
        (schema, role, schema, role, schema, role, schema, role)).fetchall())
    return {"schema": (usage, create), "table_privileges": tables, "column_acl": column_acl, "gateway_table_privileges": gateway,
            "sequences": sequences, "functions": functions, "grantable": grantable}


def catalog_difference(actual):
    """The first keys of `actual` (a `loader_catalog` result) that differ from the loader's list, as short text."""
    expected = loader_catalog_expected()
    return ", ".join(sorted(k for k in expected if actual.get(k) != expected[k])) or "none"


def apply_loader_grants(conn, schema, loader_role):
    """Run the loader's list in the caller's transaction (the installer's, as the schema owner). Returns the statements run."""
    statements = loader_grant_statements(schema, loader_role)
    for statement in statements:
        conn.execute(statement)
    return statements


# ===================================================================================================================================
# F1 R3: THE SQL FILES AND THE ROLE LISTS PER INSTALL KIND (design 1 item 1, 4.2 build table, 1.2 rule 5.3 (e)).
#
# One place, for the TEST provisioner and the real installer alike. A REAL install exists only at R8 step 1, so no test can read a REAL
# catalog before it: R3's tests read the LISTS these functions return for each kind, and the audit (real_catalog_audit.py) reads a TEST
# catalog. The real installer (R6) takes its file list and its grants only from `sql_files("REAL")` and `grant_statements(..."REAL")` and
# never names the TEST-only file (R6's static test).
# ===================================================================================================================================
#: The core: installed by every install kind, in this order, in one transaction.
CORE_SQL_FILES = ("real_workspace_v1.sql", "real_provenance_v1.sql", "real_fence_v1.sql")
#: The TEST-only part (design 1 item 1): functions only. Only the TEST provisioner runs it; a REAL install does not hold it.
TEST_ONLY_SQL_FILES = ("real_workspace_fictional_v1.sql",)
#: The functions that file creates, (name, argument types). The catalog audit refuses a REAL catalog that holds any of them, and a test
#: compares this tuple with the CREATE FUNCTION statements of the file.
TEST_ONLY_FUNCTIONS = (("rw_check_fictional", "jsonb,jsonb,jsonb,jsonb"),)


def sql_files(kind):
    """The gateway SQL files of an install kind, in install order. REAL omits the TEST-only part (and nothing else)."""
    if kind == "TEST":
        return CORE_SQL_FILES + TEST_ONLY_SQL_FILES
    if kind == "REAL":
        return CORE_SQL_FILES
    raise ValueError("install kind is TEST or REAL")


#: The thirteen lease-checked md_* read functions of the executor (2.6 item 6): rw_md_<table>(release_id text).
MD_READ_FUNCTIONS = tuple(("rw_md_" + t[len("md_"):], "text") for t in MD_TABLES)

#: THE EXECUTOR'S LIST (design 1 item 5, 2.6, 4.2 role plan). The same for TEST and REAL. It has no privilege on any md_* table (PD-0069),
#: on web_saved_sandbox, web_portfolio_revision or web_csv_*, and no UPDATE, DELETE or TRUNCATE anywhere (the ledger and the S2 tables are
#: append-only). The fence and the row policy decide, per row, which of these it may actually touch. R3 FIX ROUND (technical review M-1, L-6):
#: no privilege on issuer, instrument, listing or app_user. The first three have no root, no fence and no journal, so an executor write to
#: them would be a durable, lease-less write (P9); the design lists the executor's DML as portfolio, account, ledger_event, the other
#: canonical ledger tables and the rw_* tables (section 1 item 5; 2.6 item 1). The foreign keys of ledger_event and portfolio are checked
#: with the table owner's rights, and admit reads app_user in a definer function, so no R3 path needs them. If R5's world builder needs to
#: READ or WRITE an identity row, that is a design question (a lease-checked read or write is gateway SQL), not a grant.
EXECUTOR_TABLES = {
    "portfolio": frozenset(("SELECT", "INSERT")), "account": frozenset(("SELECT", "INSERT")), "ledger_event": frozenset(("SELECT", "INSERT")),
    "benchmark_selection": frozenset(("SELECT", "INSERT")),
    "rw_root": frozenset(("SELECT", "INSERT")), "rw_revision": frozenset(("SELECT", "INSERT")),
}
EXECUTOR_SEQUENCES = {"ledger_event_ledger_seq_seq": frozenset(("USAGE",)), "benchmark_selection_seq_seq": frozenset(("USAGE",))}
EXECUTOR_FUNCTIONS = (
    ("rw_admit", "uuid,uuid,text,bigint,text,uuid,text,boolean"), ("rw_scope", ""), ("rw_list_roots", "uuid"), ("rw_install_info", ""),
    ("rw_precheck", "uuid,uuid,text"), ("rw_seal", "uuid,bytea,bytea,bytea,text"), ("rw_archive", "uuid,uuid"),
    ("rw_row_allowed", "text,jsonb,boolean"), ("rwp_load_context", "text,text"),
) + MD_READ_FUNCTIONS

#: THE PUBLISHER'S LIST (design 2.5; R1's, moved here by R3): the owner's commands and the status views, and no table privilege.
PUBLISHER_TABLES = {"rw_pending_marks": frozenset(("SELECT",)), "rw_status": frozenset(("SELECT",))}
PUBLISHER_FUNCTIONS = (
    ("rw_publish", "bytea,jsonb,timestamptz,jsonb,text,text,text,text"),
    ("rw_renew", "text,bigint,jsonb,timestamptz,jsonb,text,text,text,text,bigint"), ("rw_withdraw_mark", "text,bigint,text,text,text,text"),
    ("rw_withdraw_apply", "text,bigint"), ("rw_in_flight", "text"), ("rw_install_info", ""),
)

#: THE ACCOUNT ROLE'S LIST (PD-0078, 2026-11-07; the fifth role). The real-mode web app's identity and session rows, and nothing else: no economic or
#: rooted table, no md_* table, no gateway or md_* function, no sequence, no UPDATE or DELETE on the identity rows. A registration writes `app_user` and
#: `web_identity`; a session and the sign-up rate limit live in `web_session` and `web_auth_rate`. The R7 fix round may narrow this list; a wider one
#: needs a new owner decision.
ACCOUNT_TABLES = {
    "app_user": frozenset(("SELECT", "INSERT")), "web_identity": frozenset(("SELECT", "INSERT")),
    "web_session": frozenset(("SELECT", "INSERT", "UPDATE", "DELETE")), "web_auth_rate": frozenset(("SELECT", "INSERT", "UPDATE", "DELETE")),
}

#: THE LOADER'S LIST as the same shape (R2's, unchanged): INSERT on the thirteen md_* tables, SELECT on two of them, the registry's put and get.
LOADER_TABLES = {t: frozenset(("INSERT", "SELECT") if t in LOADER_SELECT_TABLES else ("INSERT",)) for t in LOADER_INSERT_TABLES}


def role_lists(kind):
    """{role: {"tables": {name: privileges}, "sequences": {name: privileges}, "functions": frozenset((name, args))}} for an install kind.
    The table and sequence lists do not depend on the kind (a test compares the two kinds); the function lists differ by the TEST-only
    part's functions only, and that part is granted to NO runtime role (the core calls it as the owner), so they are equal too."""
    if kind not in ("TEST", "REAL"):
        raise ValueError("install kind is TEST or REAL")
    return {
        "executor": {"tables": dict(EXECUTOR_TABLES), "sequences": dict(EXECUTOR_SEQUENCES), "functions": frozenset(EXECUTOR_FUNCTIONS)},
        "loader": {"tables": dict(LOADER_TABLES), "sequences": {}, "functions": frozenset(LOADER_FUNCTIONS)},
        "publisher": {"tables": dict(PUBLISHER_TABLES), "sequences": {}, "functions": frozenset(PUBLISHER_FUNCTIONS)},
        "account": {"tables": dict(ACCOUNT_TABLES), "sequences": {}, "functions": frozenset()},
        "public": {"tables": {}, "sequences": {}, "functions": frozenset()},
    }


def grant_statements(kind, schema, executor_role, loader_role, publisher_role, account_role=None):
    """The installer's statements after the last SQL file: ONE statement that revokes PUBLIC's EXECUTE on every routine of the schema
    (the HEAD migrations leave that default on twelve functions, technical TR5-L2), then USAGE on the schema and each role's list.
    `account_role` (PD-0078) adds the fifth role's list; None is the four-role install of the earlier fixtures."""
    schema = identifier(schema)
    qs = '"%s"' % schema
    roles = {"executor": identifier(executor_role), "loader": identifier(loader_role), "publisher": identifier(publisher_role)}
    if account_role is not None:
        roles["account"] = identifier(account_role)
    lists = role_lists(kind)
    statements = ["REVOKE EXECUTE ON ALL ROUTINES IN SCHEMA %s FROM PUBLIC" % qs]
    for name in tuple(roles):
        quoted, spec = '"%s"' % roles[name], lists[name]
        statements.append("GRANT USAGE ON SCHEMA %s TO %s" % (qs, quoted))
        for table in sorted(spec["tables"]):
            statements.append("GRANT %s ON %s.%s TO %s" % (", ".join(sorted(spec["tables"][table])), qs, table, quoted))
        for sequence in sorted(spec["sequences"]):
            statements.append("GRANT %s ON SEQUENCE %s.%s TO %s" % (", ".join(sorted(spec["sequences"][sequence])), qs, sequence, quoted))
        for fname, args in sorted(spec["functions"]):
            statements.append("GRANT EXECUTE ON FUNCTION %s.%s(%s) TO %s" % (qs, fname, args, quoted))
    return statements


def apply_role_grants(conn, schema, executor_role, loader_role, publisher_role, kind="TEST", account_role=None):
    """Run `grant_statements` in the caller's transaction (the installer's, as the schema owner). Returns the statements run."""
    statements = grant_statements(kind, schema, executor_role, loader_role, publisher_role, account_role)
    for statement in statements:
        conn.execute(statement)
    return statements
