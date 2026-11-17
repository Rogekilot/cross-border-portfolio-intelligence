"""F1 R3: the CATALOG AUDIT of the real gateway (design 1.2 rule 5.3 (e), 1 item 1, 2.6 item 5 and 6; T03).

One function, `audit`, for two callers: T03 on TEST installs (R3) and the real installer's Phase 2 and every `--check` against the REAL
catalog (R6, first run at R8 step 1). Both import this module, so "the same audit" is one function. It is READ-ONLY: it reads the
function, ownership, privilege, trigger, policy and constraint catalogs and writes nothing. Run it as the schema owner or any role that
can read the catalogs and ask `has_*_privilege` about other roles (a superuser does).

WHAT IT COMPARES. For each of the executor, the loader, the publisher and `public`, and for EVERY relation, sequence and function of the
gateway schema, not only those a list names (so `app_user`, `portfolio`, the migration tables and the migration functions are compared as
well; technical review of R2, L-2), whether the role holds each privilege, against that role's list in `real_roles.role_lists`:

  tables      SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER and (PostgreSQL 17 and later) MAINTAIN. `has_table_privilege`
              answers for the whole table; `has_any_column_privilege` "succeeds either if the privilege is held for the whole table, or if
              there is a column-level grant", so a column-level grant is seen where the list gives the role no privilege (no list names columns);
  sequences   USAGE, SELECT, UPDATE;
  functions   EXECUTE (compared by name: no function of the schema is overloaded, which the audit checks);
  schema      USAGE and CREATE;
  also        any grant option held by a runtime role or by `public`, any object a runtime role owns.

"Holds" is what `has_*_privilege` reports, which is the sum of the direct grants, the grants to the roles it is a member of and the grants to
PUBLIC (my reading of "does user have privilege", `functions-info`; `public` is asked as well). The audit does not compare privileges on
types, large objects, parameters or other schemas.

OTHER ASSERTIONS (T03). The install kind row; the TEST-only part (present in a TEST catalog, absent from a REAL one); the exact set of
`rw_`/`rwp_` functions; that the fence, the journal, the row policy and the two constraint triggers exist and are enabled on the tables they
guard; that the deadline guard's name and the bundle guard's name are each unique among the schema's constraints; the inventory of deferrable
constraints; that the thirteen `rw_md_*` read functions match the `md_*` tables; that every SECURITY DEFINER function pins its search_path
with pg_temp last.

DEFINITIONS, NOT EXISTENCE (technical review of R3, L-1). The row policies are compared by command, role list, kind and the USING and WITH CHECK
expressions (`RW_AUDIT_CONTROL_DIFFERS`); the fence, journal, truncate, immutability and the two lease-guard triggers by `tgtype`, the function
they run (`tgfoid`, by name and schema) and, for the guards, DEFERRABLE INITIALLY DEFERRED. Every routine of the schema is compared for EXECUTE,
procedures included. Role memberships (`RW_AUDIT_MEMBERSHIP`): a runtime role or the owner as the member of any role, whatever the options (a
membership with SET TRUE lets the role `SET ROLE` to the granted role, which `has_*_privilege` does not report for a NOINHERIT role), and any role
that may SET or INHERIT a runtime role or the owner; ADMIN OPTION alone is the preflight's (design 5.3 (a), (b)).

FUNCTION BODIES AND THE FULL TRIGGER SET (re-review RR-L2). Each gateway function (`rw_`/`rwp_`) is compared with the definition the installer's SQL
files give it: body exactly as stored (`prosrc`), language, SECURITY DEFINER, volatility, STRICT, LEAKPROOF, PARALLEL and settings
(`RW_AUDIT_FUNCTION_DEFINITION`); the report carries a digest per function (`inspected["function_digests"]`), so a `CREATE OR REPLACE` that keeps
the oid, the name and the grants is seen. On the fenced tables, every `rw_`/`rwp_` table and every `md_` table the WHOLE set of non-internal
triggers is compared with `EXPECTED_TRIGGERS` (name, function, `tgtype`, constraint kind, enabled for every session): a trigger the table does
not expect is a finding whatever function it runs. NOT covered, and stated as a limit: the bodies of the migration functions other than the five
INSERT-path guards (below) are not compared with the migration files, only the triggers that run them; triggers on tables outside the three
groups (the `web_*` tables, `app_user`, identity tables) are not read.

THE FIVE INSERT-PATH GUARDS (R6, FR-L1 (b); `GUARD_FUNCTIONS`). `md_require_open_release` and `md_release_stamp` (fired by the loader's inserts)
and `ledger_event_before_insert`, `ledger_event_check_transfer_pairing` and `benchmark_selection_before_insert` (fired by the executor's accepted
writes) are compared field for field with the definition the migrations give them (`migration_guard_definitions`), so a `CREATE OR REPLACE` that
keeps the name, the grants and the trigger is seen (`RW_AUDIT_GUARD_DEFINITION`). Python only: no gateway SQL.

RESULT. `AuditResult.findings` is empty when the catalog holds what `as_kind` says. A catalog the audit cannot read is a finding, never a pass.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from persistence import real_roles
from persistence.real_workspace_context import identifier

#: The deferrable constraints of the gateway schema, keyed (name, table, kind) like F2's inventory (`guarded_workspace_context.py:79-102`).
#: kind: "f" foreign key, "t" constraint trigger (`pg_constraint.contype`). The create tail (R5) fires the ones it may fire by name and
#: never the deadline guard; it refuses a deferrable constraint that is not on this list. Both branches share the schema, so both share it.
EXPECTED_DEFERRABLE = frozenset((
    ("ledger_event_transfer_pairing", "ledger_event", "t"),     # migration 0003: fired by name by the create tail
    ("rw_root_link_portfolio_fkey", "rw_root_link", "f"),       # a registered root without a portfolio fails by COMMIT
    ("rw_bundle_complete", "rw_lease", "t"),                    # the bundle guard (R3): fired by name after the seal
    ("rw_lease_deadline_guard", "rw_lease", "t"),               # the deadline guard (R1): NEVER fired early, only by COMMIT
    ("web_csv_source_key_report_id_fkey", "web_csv_source_key", "f"),   # migration 0019: a table no real path writes (the executor has no privilege on it)
))
#: The constraints whose names must be unique among the schema's constraints, because SET CONSTRAINTS acts on every match of a name.
UNIQUE_NAMES = ("rw_lease_deadline_guard", "rw_bundle_complete")
#: The tables the fence, the row policy and the journal guard (design 2.6 item 1).
FENCED_TABLES = ("portfolio", "account", "ledger_event", "benchmark_selection", "rw_root", "rw_revision")

#: The triggers each guarded table must carry, by DEFINITION (technical review L-1): name -> (pg_trigger.tgtype, the schema function it runs).
#: tgtype bits: 1 ROW, 2 BEFORE, 4 INSERT, 8 DELETE, 16 UPDATE, 32 TRUNCATE (64 INSTEAD OF). Written by hand from the CREATE TRIGGER
#: statements of real_fence_v1.sql and real_workspace_v1.sql, not read from the catalog.
FENCE_TRIGGERS = {"zz_rw_write": (1 + 2 + 4 + 8 + 16, "rw_write_fence"), "zz_rw_journal": (1 + 4 + 8 + 16, "rw_journal_after"),
                  "zz_rw_truncate": (2 + 32, "rw_write_fence")}
IMMUTABLE_TRIGGERS = {"rw_immutable": (1 + 2 + 8 + 16, "rw_no_mutation"), "rw_no_truncate": (2 + 32, "rw_no_mutation")}
LEASE_TRIGGERS = {"rw_bundle_complete": (1 + 4, "rw_bundle_guard"), "rw_lease_deadline_guard": (1 + 4, "rw_deadline_check")}

#: THE FULL TRIGGER SET of every table the audit reads the triggers of (re-review RR-L2): the fenced tables, every `rw_`/`rwp_` table and every `md_`
#: table of the schema. name -> (tgtype, the function it runs in this schema, a constraint trigger). Written by hand from the CREATE TRIGGER
#: statements of the SQL files and of migrations 0002-0011 and 0019, and checked against a clean TEST install. A trigger on one of these tables
#: that is not named here is a finding (a `BEFORE` trigger that fires after the fence and rewrites `NEW` has no `rw_` function behind it), whatever
#: it runs. A new migration trigger on one of these tables is therefore a reviewed change to this table.
_MD_TRIGGER = {"no_truncate": (2 + 32, "md_reject_mutation"), "no_update_delete": (1 + 2 + 8 + 16, "md_reject_mutation")}


def _md(table, *, opened="md_require_open_release"):
    out = {table + "_no_truncate": _MD_TRIGGER["no_truncate"] + (False,), table + "_no_update_delete": _MD_TRIGGER["no_update_delete"] + (False,)}
    if opened is not None:
        out[table + "_open_release"] = (1 + 2 + 4, opened, False)
    return out


def _plain(triggers):
    return {name: tuple(value) + (False,) for name, value in triggers.items()}


def _expected_trigger_sets():
    sets = {}
    for table in FENCED_TABLES:
        sets[table] = _plain(FENCE_TRIGGERS)
    sets["account"].update({"account_identity_immutable": (1 + 2 + 16, "account_guard_identity", False)})
    sets["benchmark_selection"].update({
        "benchmark_selection_before_insert": (1 + 2 + 4, "benchmark_selection_before_insert", False),
        "benchmark_selection_no_truncate": (2 + 32, "benchmark_selection_reject_mutation", False),
        "benchmark_selection_no_update_delete": (1 + 2 + 8 + 16, "benchmark_selection_reject_mutation", False)})
    sets["ledger_event"].update({
        "ledger_event_before_insert": (1 + 2 + 4, "ledger_event_before_insert", False),
        "ledger_event_no_truncate": (2 + 32, "ledger_event_reject_mutation", False),
        "ledger_event_no_update_delete": (1 + 2 + 8 + 16, "ledger_event_reject_mutation", False),
        "ledger_event_transfer_pairing": (1 + 4, "ledger_event_check_transfer_pairing", True)})
    for table in ("rw_root", "rw_revision", "rw_artifact", "rw_operation", "rw_journal", "rw_install", "rw_snapshot", "rw_history", "rw_drain_mark", "rw_root_link"):
        sets.setdefault(table, {}).update(_plain(IMMUTABLE_TRIGGERS))
    sets["rw_history"].update({"rw_history_guard_write": (1 + 2 + 4, "rw_history_guard", False)})
    sets["rw_head"] = {"rw_head_guard_delete": (1 + 2 + 8, "rw_head_guard", False), "rw_head_guard_write": (1 + 2 + 4 + 16, "rw_head_guard", False),
                       "rw_head_no_truncate": (2 + 32, "rw_no_mutation", False)}
    sets["rw_lease"] = {"rw_bundle_complete": (1 + 4, "rw_bundle_guard", True), "rw_lease_deadline_guard": (1 + 4, "rw_deadline_check", True),
                        "rw_lease_guard_write": (1 + 2 + 8 + 16, "rw_lease_guard", False), "rw_lease_no_truncate": (2 + 32, "rw_lease_guard", False)}
    sets["rw_mode"] = {"rw_mode_no_delete": (1 + 2 + 8, "rw_no_mutation", False), "rw_mode_no_truncate": (2 + 32, "rw_no_mutation", False)}
    for table in ("rwp_acquisition", "rwp_context", "rwp_manifest", "rwp_payload", "rwp_registration"):
        sets[table] = {table + "_immutable_rows": (1 + 2 + 8 + 16, "rwp_immutable", False), table + "_immutable_truncate": (2 + 32, "rwp_immutable", False)}
    for table in real_roles.MD_TABLES:
        sets[table] = _md(table, opened=None if table == "md_file" else "md_release_stamp" if table == "md_release" else "md_require_open_release")
    sets["md_release"] = {name.replace("_open_release", "_stamp_xid"): value for name, value in sets["md_release"].items()}
    return sets


EXPECTED_TRIGGERS = _expected_trigger_sets()

TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
COLUMN_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "REFERENCES")
SEQUENCE_PRIVILEGES = ("USAGE", "SELECT", "UPDATE")


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str = ""

    def short(self):
        return "%s %s%s" % (self.code, self.subject, (" (" + self.detail + ")") if self.detail else "")


@dataclass(frozen=True)
class AuditResult:
    as_kind: str
    findings: tuple
    inspected: dict

    @property
    def ok(self):
        return not self.findings

    def codes(self):
        return tuple(sorted({f.code for f in self.findings}))


def _declared_functions(kind):
    """The names of the `rw_`/`rwp_` functions the SQL files of `kind` create (read from the files, which are the installer's input)."""
    names = set()
    for filename in real_roles.sql_files(kind):
        text = (Path(__file__).with_name(filename)).read_text("utf8")
        names.update(re.findall(r"CREATE FUNCTION __RW_SCHEMA__\.(rwp?_[a-z0-9_]+)\(", text))
    return frozenset(names)


_CREATE_FUNCTION = re.compile(r"CREATE FUNCTION __RW_SCHEMA__\.(rwp?_[a-z0-9_]+)\(")
_BODY_START = re.compile(r"\bAS\s+(\$[A-Za-z0-9_]*\$)")


def _setting(value):
    """A function setting as it can be compared: no whitespace, no quotes, lower case (`search_path=pg_catalog, "s", pg_temp` and the file's
    `search_path=pg_catalog,s,pg_temp` are the same setting)."""
    return "".join(value.replace('"', "").split()).lower()


def _declared_definitions(kind, schema, executor, loader, publisher):
    """name -> the definition the installer's SQL files of `kind` give each gateway function (re-review RR-L2): the body exactly as PostgreSQL
    stores it (`prosrc`, with the installer's own marker substitution), the language, SECURITY DEFINER, volatility, STRICT, LEAKPROOF, PARALLEL
    and the function settings. The owner is compared by the ownership check, which already reports it."""
    out = {}
    for filename in real_roles.sql_files(kind):
        text = Path(__file__).with_name(filename).read_text("utf8")
        for marker, name in zip(("__RW_SCHEMA__", "__RW_EXECUTOR__", "__RW_LOADER__", "__RW_PUBLISHER__"), (schema, executor, loader, publisher)):
            text = text.replace(marker, name)
        pattern = re.compile(_CREATE_FUNCTION.pattern.replace("__RW_SCHEMA__", re.escape(schema)))
        for match in pattern.finditer(text):
            start = _BODY_START.search(text, match.end())
            header = text[match.end():start.start()]
            tag = start.group(1)
            body = text[start.end():text.index(tag, start.end())]
            upper = header.upper()
            parallel = re.search(r"\bPARALLEL\s+(SAFE|RESTRICTED|UNSAFE)\b", upper)
            out[match.group(1)] = {
                "prosrc": body,
                "language": re.search(r"\bLANGUAGE\s+(\w+)", header, re.I).group(1).lower(),
                "security_definer": re.search(r"\bSECURITY\s+DEFINER\b", upper) is not None,
                "volatility": "i" if re.search(r"\bIMMUTABLE\b", upper) else "s" if re.search(r"\bSTABLE\b", upper) else "v",
                "strict": re.search(r"\bSTRICT\b|RETURNS\s+NULL\s+ON\s+NULL\s+INPUT", upper) is not None,
                "leakproof": re.search(r"(?<!NOT\s)\bLEAKPROOF\b", upper) is not None,
                "parallel": {"SAFE": "s", "RESTRICTED": "r", "UNSAFE": "u"}[parallel.group(1)] if parallel else "u",
                "settings": tuple(sorted(_setting(a + "=" + b) for a, b in re.findall(r"\bSET\s+(\w+)\s*=\s*(\S+)", header))),
            }
    return out


def _installed_definition(row):
    """The same fields from `pg_proc`, for a row of the audit's function query."""
    return {"prosrc": row[8], "language": row[9], "security_definer": bool(row[2]), "volatility": row[13], "strict": bool(row[10]),
            "leakproof": bool(row[11]), "parallel": row[12], "settings": tuple(sorted(_setting(c) for c in (row[3] or [])))}


def definition_digest(definition):
    """The SHA-256 of one function definition, over its fields in a fixed order (evidence for a `--check` report)."""
    fields = ("prosrc", "language", "security_definer", "volatility", "strict", "leakproof", "parallel", "settings")
    return hashlib.sha256(json.dumps([definition[f] if f != "settings" else list(definition[f]) for f in fields], separators=(",", ":")).encode("utf8")).hexdigest()


def _definition_findings(gateway, definitions, findings, inspected):
    digests = {}
    for row in gateway:
        want = definitions.get(row[1])
        if want is None:
            continue                                  # a function the files do not create is RW_AUDIT_FUNCTION_SET already
        have = _installed_definition(row)
        digests[row[1]] = definition_digest(have)
        if have != want:
            differing =[field for field in want if have[field] != want[field]]
            detail = "differs from the installer's definition in %s (installed digest %s, installer's %s)" % (
                ", ".join(differing), definition_digest(have)[:16], definition_digest(want)[:16])
            findings.append(Finding("RW_AUDIT_FUNCTION_DEFINITION", row[1], detail))
    inspected["function_digests"] = tuple(sorted(digests.items()))


#: FR-L1 (b), carried from R3's final re-check to R6: the INSERT-path guard functions of the migrations, whose DEFINITIONS the audit compares with
#: the migrations' own text. The loader's inserts fire the first two and the executor's accepted writes fire the other three; a hollowed body would
#: leave every other comparison (names, grants, triggers) unchanged. The other migration functions fire on an UPDATE, DELETE or TRUNCATE (or on a
#: table no runtime role may write) and stay uncompared: no runtime role holds the privilege they guard (the R3 re-check's reading).
GUARD_FUNCTIONS = ("md_require_open_release", "md_release_stamp", "ledger_event_before_insert", "ledger_event_check_transfer_pairing",
                   "benchmark_selection_before_insert")
_MIGRATION_FUNCTION = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([a-z0-9_]+)\s*\(", re.I)


def migration_guard_definitions(schema, directory=None):
    """name -> the definition the MIGRATIONS give each guard function, as the audit compares it (`_installed_definition`'s fields): the LAST
    `CREATE [OR REPLACE] FUNCTION` of the name in migration order wins, its body is the text between its dollar quotes exactly (what
    `pg_proc.prosrc` stores), and the setting is the schema pin that the migrations apply to every function of the schema
    (`ALTER FUNCTION ... SET search_path = <schema>, pg_temp`, migrations 0006, 0011 and 0015). Python only: no gateway SQL, no connection."""
    schema = identifier(schema)
    if directory is None:
        directory = Path(__file__).with_name("migrations")
    out = {}
    for path in sorted(Path(directory).glob("[0-9][0-9][0-9][0-9]_*.sql")):
        text = path.read_text("utf8")
        for match in _MIGRATION_FUNCTION.finditer(text):
            name = match.group(1).lower()
            if name not in GUARD_FUNCTIONS:
                continue
            start = _BODY_START.search(text, match.end())
            header = text[match.end():start.start()]
            tag = start.group(1)
            upper = header.upper()
            parallel = re.search(r"\bPARALLEL\s+(SAFE|RESTRICTED|UNSAFE)\b", upper)
            out[name] = {
                "prosrc": text[start.end():text.index(tag, start.end())],
                "language": re.search(r"\bLANGUAGE\s+(\w+)", header + text[start.start():start.start() + 80], re.I).group(1).lower(),
                "security_definer": re.search(r"\bSECURITY\s+DEFINER\b", upper) is not None,
                "volatility": "i" if re.search(r"\bIMMUTABLE\b", upper) else "s" if re.search(r"\bSTABLE\b", upper) else "v",
                "strict": re.search(r"\bSTRICT\b|RETURNS\s+NULL\s+ON\s+NULL\s+INPUT", upper) is not None,
                "leakproof": False,
                "parallel": {"SAFE": "s", "RESTRICTED": "r", "UNSAFE": "u"}[parallel.group(1)] if parallel else "u",
                "settings": (_setting("search_path=%s,pg_temp" % schema),),
            }
    return out


def guard_definition_findings(functions, schema, findings, inspected, *, expected=None):
    """Findings (`RW_AUDIT_GUARD_DEFINITION`) for the five INSERT-path guard functions (FR-L1 (b)). `functions` are the audit's `pg_proc` rows."""
    expected = migration_guard_definitions(schema) if expected is None else expected
    digests = {}
    for name in GUARD_FUNCTIONS:
        want = expected.get(name)
        rows = [f for f in functions if f[1] == name]
        if want is None:
            findings.append(Finding("RW_AUDIT_GUARD_DEFINITION", name, "the migrations do not define it (the expected definition cannot be built)"))
        elif len(rows) != 1:
            findings.append(Finding("RW_AUDIT_GUARD_DEFINITION", name, "%d functions of this name in the schema, expected one" % len(rows)))
        else:
            have = _installed_definition(rows[0])
            digests[name] = definition_digest(have)
            if have != want:
                differing = [field for field in want if have[field] != want[field]]
                findings.append(Finding("RW_AUDIT_GUARD_DEFINITION", name, "differs from the migrations' definition in %s (installed digest %s, migrations' %s)" % (
                    ", ".join(differing), definition_digest(have)[:16], definition_digest(want)[:16])))
    inspected["guard_digests"] = tuple(sorted(digests.items()))


def _trigger_set_findings(conn, schema, tables, covered, findings):
    """The FULL trigger set of each table in `tables` ((name, oid) pairs) against `EXPECTED_TRIGGERS` (re-review RR-L2): every non-internal
    trigger must be one the table expects, whatever function it runs, and each expected one must be enabled ('O'), of the expected tgtype and
    constraint kind, and run the expected function of this schema. `covered[table]` names the triggers `_trigger_findings` already compares
    (not reported twice)."""
    for table, relid in tables:
        want = EXPECTED_TRIGGERS.get(table, {})
        found = {r[0]: r[1:] for r in conn.execute(
            "SELECT t.tgname::text,t.tgenabled::text,t.tgtype::int,p.proname::text,pn.nspname::text,t.tgconstraint<>0 "
            "FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace "
            "WHERE t.tgrelid=%s AND NOT t.tgisinternal ORDER BY t.tgname", (relid,)).fetchall()}
        for name in sorted(set(found) - set(want)):
            enabled, tgtype, function, function_schema, _constraint = found[name]
            findings.append(Finding("RW_AUDIT_CONTROL_DIFFERS", table, "unexpected trigger %s (tgtype %s, enabled %s, runs %s.%s)" % (name, tgtype, enabled, function_schema, function)))
        for name in sorted(set(want) - covered.get(table, set())):
            if name not in found:
                findings.append(Finding("RW_AUDIT_CONTROL_MISSING", table, "trigger %s is absent" % name))
                continue
            enabled, tgtype, function, function_schema, constraint = found[name]
            if enabled != "O":
                findings.append(Finding("RW_AUDIT_CONTROL_MISSING", table, "trigger %s is not enabled (tgenabled %s)" % (name, enabled)))
            if (tgtype, function, function_schema, constraint) != (want[name][0], want[name][1], schema, want[name][2]):
                findings.append(Finding("RW_AUDIT_CONTROL_DIFFERS", table, "trigger %s has tgtype %s and runs %s.%s (constraint trigger %s); expected tgtype %s and %s.%s (%s)" % (
                    name, tgtype, function_schema, function, constraint, want[name][0], schema, want[name][1], want[name][2])))


def _normalized(expression, schema):
    """A policy expression as PostgreSQL prints it, without quoting, whitespace or the schema qualification (which depends on the session's
    search_path), so that it can be compared with the expression written in the SQL file."""
    text = (expression or "").replace('"', "")
    text = text.replace(schema + ".", "")
    return "".join(text.split()).lower()


def _trigger_findings(conn, schema, table, relid, expected, findings, *, deferred=False):
    """Findings for the triggers `expected` ({name: (tgtype, function)}) on one table: present, enabled (origin and local sessions, 'O'),
    of the expected type and running the expected function of THIS schema. `deferred` also requires a constraint trigger that is
    DEFERRABLE INITIALLY DEFERRED."""
    found = {t[0]: t[1:] for t in conn.execute(
        "SELECT t.tgname::text,t.tgenabled::text,t.tgtype::int,p.proname::text,pn.nspname::text,t.tgconstraint<>0,t.tgdeferrable,t.tginitdeferred "
        "FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace WHERE t.tgrelid=%s AND NOT t.tgisinternal",
        (relid,)).fetchall()}
    for name, (tgtype, function) in expected.items():
        if name not in found:
            findings.append(Finding("RW_AUDIT_CONTROL_MISSING", table, "trigger %s is absent" % name))
            continue
        enabled, found_type, found_function, found_schema, is_constraint, deferrable, initially = found[name]
        if enabled != "O":
            findings.append(Finding("RW_AUDIT_CONTROL_MISSING", table, "trigger %s is disabled" % name))
        if (found_type, found_function, found_schema) != (tgtype, function, schema):
            findings.append(Finding("RW_AUDIT_CONTROL_DIFFERS", table, "trigger %s has tgtype %s and runs %s.%s; expected tgtype %s and %s.%s" % (
                name, found_type, found_schema, found_function, tgtype, schema, function)))
        if deferred and not (is_constraint and deferrable and initially):
            findings.append(Finding("RW_AUDIT_CONTROL_DIFFERS", table, "trigger %s is not a DEFERRABLE INITIALLY DEFERRED constraint trigger" % name))


def _policy_findings(conn, schema, table, relid, executor, findings):
    """Findings for the row policies of one fenced table, compared by DEFINITION (technical review L-1): exactly rw_baseline (permissive) and
    rw_row_guard (restrictive), each FOR ALL TO the executor alone, with the USING and WITH CHECK expressions the SQL file writes."""
    expected = {
        "rw_baseline": (True, "*", "true", "true"),
        "rw_row_guard": (False, "*", "rw_row_allowed('%s'::text,to_jsonb(%s.*),false)" % (table, table),
                         "rw_row_allowed('%s'::text,to_jsonb(%s.*),true)" % (table, table)),
    }
    found = {}
    for name, permissive, command, roles, using, check in conn.execute(
            "SELECT polname::text,polpermissive,polcmd::text,ARRAY(SELECT CASE WHEN r=0 THEN 'public' ELSE r::regrole::text END FROM unnest(polroles) r ORDER BY 1),"
            "pg_get_expr(polqual,polrelid),pg_get_expr(polwithcheck,polrelid) FROM pg_policy WHERE polrelid=%s", (relid,)).fetchall():
        found[name] = (permissive, command, [r.replace('"', "") for r in roles], _normalized(using, schema), _normalized(check, schema))
    if set(found) != set(expected):
        findings.append(Finding("RW_AUDIT_CONTROL_MISSING", table, "the row policies are %s, expected %s" % (sorted(found), sorted(expected))))
    for name, (permissive, command, using, check) in expected.items():
        if name not in found:
            continue
        have = found[name]
        want = (permissive, command, [executor], using, check)
        if have != want:
            findings.append(Finding("RW_AUDIT_CONTROL_DIFFERS", table, "policy %s is (permissive, command, roles, using, with check) = %s; expected %s" % (name, have, want)))


def _membership_findings(conn, runtime, owner, version, findings):
    """A runtime role is a member of NO role, and no role holds the right to become (SET) or to inherit (INHERIT) one (technical review L-1).
    The reviewer's case: a membership with SET TRUE lets the runtime role `SET ROLE` to the granted role, which has_*_privilege does not
    report when the role is NOINHERIT. A membership held with ADMIN OPTION alone (SET and INHERIT false) is not reported here: it gives no
    power to act as the role, and the escalation through a role that can grant itself membership is the preflight's (design 5.3 (a), (b))."""
    set_column = "m.set_option" if version >= 160000 else "true"
    inherit_column = "m.inherit_option" if version >= 160000 else "true"
    rows = conn.execute(
        f"SELECT g.rolname::text,r.rolname::text,{set_column},{inherit_column},m.admin_option FROM pg_auth_members m "
        "JOIN pg_roles g ON g.oid=m.roleid JOIN pg_roles r ON r.oid=m.member WHERE g.rolname=ANY(%s) OR r.rolname=ANY(%s)",
        (list(runtime) + [owner], list(runtime) + [owner])).fetchall()
    for granted, member, can_set, can_inherit, admin in rows:
        if member in runtime or owner == member:
            findings.append(Finding("RW_AUDIT_MEMBERSHIP", member, "is a member of %s (SET %s, INHERIT %s, ADMIN %s)" % (granted, can_set, can_inherit, admin)))
        elif can_set or can_inherit:
            findings.append(Finding("RW_AUDIT_MEMBERSHIP", granted, "has the member %s (SET %s, INHERIT %s, ADMIN %s)" % (member, can_set, can_inherit, admin)))


def deferrable_inventory(conn, schema):
    """The deferrable constraints of the schema as a sorted tuple of (name, table, kind). Read-only."""
    schema = identifier(schema)
    rows = conn.execute(
        "SELECT c.conname::text,t.relname::text,c.contype::text FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
        "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=%s AND c.condeferrable ORDER BY 1,2,3", (schema,)).fetchall()
    return tuple((r[0], r[1], r[2]) for r in rows)


def audit(conn, schema, owner_role, executor_role, loader_role, publisher_role, *, as_kind, require_install_row=True, account_role=None):
    """Audit the gateway schema of the connected database as an install of kind `as_kind` ("TEST" or "REAL"). Returns an `AuditResult`.

    `account_role` (PD-0078) names the fifth role of the web accounts. When it is named, it is a principal like the other three: it must exist, hold
    USAGE on the schema and exactly `real_roles.ACCOUNT_TABLES` and nothing else, own nothing, hold no grant option and be a member of nothing. None
    is the four-role audit of the earlier fixtures; the real installer always names it."""
    if as_kind not in ("TEST", "REAL"):
        raise ValueError("as_kind is TEST or REAL")
    schema = identifier(schema)
    roles = {"executor": identifier(executor_role), "loader": identifier(loader_role), "publisher": identifier(publisher_role)}
    if account_role is not None:
        roles["account"] = identifier(account_role)
    roles["public"] = "public"
    owner = identifier(owner_role)
    findings = []
    inspected = {}
    lists = real_roles.role_lists(as_kind)
    try:
        if account_role is not None and conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (roles["account"],)).fetchone() is None:
            return AuditResult(as_kind, (Finding("RW_AUDIT_ACCOUNT_ROLE", roles["account"], "the account role does not exist"),), {})
        version = int(conn.execute("SHOW server_version_num").fetchone()[0])
        if conn.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (schema,)).fetchone() is None:
            return AuditResult(as_kind, (Finding("RW_AUDIT_NOT_INSPECTED", schema, "the schema does not exist"),), {})

        # ---- (i) the TEST-only part and the exact function set -------------------------------------------------------------------
        functions = conn.execute(
            "SELECT p.oid,p.proname::text,p.prosecdef,p.proconfig,p.prorettype,p.proretset,p.proowner::regrole::text,p.prokind::text,"
            "p.prosrc,l.lanname::text,p.proisstrict,p.proleakproof,p.proparallel::text,p.provolatile::text "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang WHERE n.nspname=%s ORDER BY p.proname,p.oid",
            (schema,)).fetchall()
        gateway = [f for f in functions if f[1].startswith("rw_") or f[1].startswith("rwp_")]
        names = [f[1] for f in gateway]
        inspected["gateway_functions"] = tuple(sorted(set(names)))
        for name in sorted({n for n in names if names.count(n) > 1}):
            findings.append(Finding("RW_AUDIT_OVERLOADED", name, "a gateway function name is used by more than one function"))
        present = set(names)
        test_only = {n for n, _a in real_roles.TEST_ONLY_FUNCTIONS}
        if as_kind == "REAL":
            for name in sorted(present & test_only):
                findings.append(Finding("RW_AUDIT_TEST_ONLY_PRESENT", name, "a function of the TEST-only part exists in a REAL catalog"))
        else:
            for name in sorted(test_only - present):
                findings.append(Finding("RW_AUDIT_TEST_ONLY_MISSING", name, "a TEST install holds the TEST-only part"))
        declared = _declared_functions(as_kind)
        for name in sorted(present - declared):
            if as_kind == "REAL" and name in test_only:
                continue
            findings.append(Finding("RW_AUDIT_FUNCTION_SET", name, "a gateway function the SQL files of this install kind do not create"))
        for name in sorted(declared - present):
            findings.append(Finding("RW_AUDIT_FUNCTION_SET", name, "a gateway function the SQL files create is missing"))
        # the DEFINITION of each gateway function, not only its name and place (re-review RR-L2: `CREATE OR REPLACE` keeps the oid, the name and
        # the grants, so a hollowed `rw_row_allowed` or a pass-through `rw_write_fence` left every other comparison unchanged)
        _definition_findings(gateway, _declared_definitions(as_kind, schema, roles["executor"], roles["loader"], roles["publisher"]), findings, inspected)
        # FR-L1 (b): the five INSERT-path migration guard functions, by definition (R6; Python only)
        guard_definition_findings(functions, schema, findings, inspected)

        # ---- (ii) ownership ----------------------------------------------------------------------------------------------------
        runtime = tuple(r for p, r in roles.items() if p != "public")
        for relname, relkind, relowner in conn.execute(
                "SELECT c.relname::text,c.relkind::text,c.relowner::regrole::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname=%s AND c.relkind IN ('r','p','v','m','f','S')", (schema,)).fetchall():
            if relowner in runtime:
                findings.append(Finding("RW_AUDIT_OWNS_OBJECT", relname, "owned by " + relowner))
            elif relowner != owner:
                findings.append(Finding("RW_AUDIT_OWNER_DIFFERS", relname, "owned by " + relowner))
        for f in functions:
            if f[6] in runtime:
                findings.append(Finding("RW_AUDIT_OWNS_OBJECT", f[1], "function owned by " + f[6]))
            elif f[6] != owner:
                findings.append(Finding("RW_AUDIT_OWNER_DIFFERS", f[1], "function owned by " + f[6]))
        schema_owner = conn.execute("SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname=%s", (schema,)).fetchone()[0]
        if schema_owner in runtime:
            findings.append(Finding("RW_AUDIT_OWNS_OBJECT", schema, "the schema is owned by " + schema_owner))

        # ---- (iii) privileges: every relation, sequence and function, four principals ---------------------------------------------
        table_privileges = TABLE_PRIVILEGES + (("MAINTAIN",) if version >= 170000 else ())
        relations = conn.execute(
            "SELECT c.oid,c.relname::text,c.relkind::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=%s AND c.relkind IN ('r','p','v','m','f') ORDER BY c.relname", (schema,)).fetchall()
        sequences = conn.execute(
            "SELECT c.oid,c.relname::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='S' ORDER BY c.relname",
            (schema,)).fetchall()
        inspected["relations"] = tuple(r[1] for r in relations)
        inspected["sequences"] = tuple(s[1] for s in sequences)
        for principal, role in roles.items():
            usage, create = conn.execute("SELECT has_schema_privilege(%s::text,%s::text,'USAGE'),has_schema_privilege(%s::text,%s::text,'CREATE')",
                                         (role, schema, role, schema)).fetchone()
            want = (False, False) if principal == "public" else (True, False)
            if (usage, create) != want:
                findings.append(Finding("RW_AUDIT_PRIVILEGE_DIFFERS", "schema " + schema, "%s holds (USAGE, CREATE) = %s, the list has %s" % (principal, (usage, create), want)))
            spec = lists[principal]
            for oid, relname, _kind in relations:
                expected = spec["tables"].get(relname, frozenset())
                for privilege in table_privileges:
                    whole = conn.execute("SELECT has_table_privilege(%s::text,%s::oid,%s)", (role, oid, privilege)).fetchone()[0]
                    any_column = whole or (privilege in COLUMN_PRIVILEGES and conn.execute(
                        "SELECT has_any_column_privilege(%s::text,%s::oid,%s)", (role, oid, privilege)).fetchone()[0])
                    if privilege in expected and not whole:
                        findings.append(Finding("RW_AUDIT_PRIVILEGE_DIFFERS", relname, "%s lacks %s" % (principal, privilege)))
                    elif privilege not in expected and any_column:
                        findings.append(Finding("RW_AUDIT_PRIVILEGE_DIFFERS", relname, "%s holds %s%s" % (principal, privilege, "" if whole else " on a column")))
            for oid, seqname in sequences:
                expected = spec["sequences"].get(seqname, frozenset())
                for privilege in SEQUENCE_PRIVILEGES:
                    held = conn.execute("SELECT has_sequence_privilege(%s::text,%s::oid,%s)", (role, oid, privilege)).fetchone()[0]
                    if (privilege in expected) != held:
                        findings.append(Finding("RW_AUDIT_PRIVILEGE_DIFFERS", seqname, "%s %s %s" % (principal, "lacks" if privilege in expected else "holds", privilege)))
            expected_functions = {name for name, _args in spec["functions"]}
            for f in functions:                  # every kind (function, procedure, aggregate, window): a procedure with PUBLIC EXECUTE is a finding too
                held = conn.execute("SELECT has_function_privilege(%s::text,%s::oid,'EXECUTE')", (role, f[0])).fetchone()[0]
                if (f[1] in expected_functions) != held:
                    findings.append(Finding("RW_AUDIT_PRIVILEGE_DIFFERS", f[1], "%s %s EXECUTE" % (principal, "lacks" if f[1] in expected_functions else "holds")))
            missing = expected_functions - {f[1] for f in functions}
            for name in sorted(missing):
                findings.append(Finding("RW_AUDIT_PRIVILEGE_DIFFERS", name, "%s's list names a function that does not exist" % principal))
        # grant options and column ACLs, directly from the ACLs
        grantable = conn.execute(
            "SELECT c.relname::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(c.relacl) x "
            "WHERE n.nspname=%s AND x.is_grantable AND (x.grantee=0 OR x.grantee IN (SELECT oid FROM pg_roles WHERE rolname=ANY(%s))) "
            "UNION ALL SELECT p.proname::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(p.proacl) x "
            "WHERE n.nspname=%s AND x.is_grantable AND (x.grantee=0 OR x.grantee IN (SELECT oid FROM pg_roles WHERE rolname=ANY(%s))) "
            "UNION ALL SELECT n.nspname::text FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) x "
            "WHERE n.nspname=%s AND x.is_grantable AND (x.grantee=0 OR x.grantee IN (SELECT oid FROM pg_roles WHERE rolname=ANY(%s))) "
            "UNION ALL SELECT c.relname::text FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
            "CROSS JOIN LATERAL aclexplode(a.attacl) x WHERE n.nspname=%s AND a.attacl IS NOT NULL AND x.is_grantable "
            "AND (x.grantee=0 OR x.grantee IN (SELECT oid FROM pg_roles WHERE rolname=ANY(%s)))",
            (schema, list(runtime), schema, list(runtime), schema, list(runtime), schema, list(runtime))).fetchall()
        for (name,) in grantable:
            findings.append(Finding("RW_AUDIT_GRANT_OPTION", name, "a runtime role or public holds a privilege WITH GRANT OPTION"))

        # ---- (iv) the other assertions of T03 --------------------------------------------------------------------------------------
        rows = conn.execute('SELECT kind FROM "%s".rw_install' % schema).fetchall()
        if rows or require_install_row:
            if len(rows) != 1 or rows[0][0] != as_kind:
                findings.append(Finding("RW_AUDIT_INSTALL_ROW", "rw_install", "rows %s, expected one row of kind %s" % ([r[0] for r in rows], as_kind)))
        inspected["install_rows"] = tuple(r[0] for r in rows)
        # the fence, the journal, the truncate refusal and the row policy on each fenced table
        for table in FENCED_TABLES:
            row = conn.execute("SELECT c.oid,c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=%s", (schema, table)).fetchone()
            if row is None:
                findings.append(Finding("RW_AUDIT_CONTROL_MISSING", table, "the fenced table does not exist"))
                continue
            if not row[1]:
                findings.append(Finding("RW_AUDIT_CONTROL_MISSING", table, "row security is not enabled"))
            _trigger_findings(conn, schema, table, row[0], FENCE_TRIGGERS, findings)
            _policy_findings(conn, schema, table, row[0], roles["executor"], findings)
        for table in ("rw_root", "rw_revision", "rw_artifact", "rw_operation", "rw_journal"):
            row = conn.execute("SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=%s", (schema, table)).fetchone()
            if row is not None:
                _trigger_findings(conn, schema, table, row[0], IMMUTABLE_TRIGGERS, findings)
        lease = conn.execute("SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname='rw_lease'", (schema,)).fetchone()
        if lease is not None:
            _trigger_findings(conn, schema, "rw_lease", lease[0], LEASE_TRIGGERS, findings, deferred=True)
        # the FULL trigger set of the fenced tables, every gateway table and every md_* table (RR-L2): a trigger the table does not expect is a
        # finding whatever function it runs; the migration triggers and the md_* ones are compared here, the gateway's own above
        covered = {table: set(FENCE_TRIGGERS) for table in FENCED_TABLES}
        for table in ("rw_root", "rw_revision", "rw_artifact", "rw_operation", "rw_journal"):
            covered.setdefault(table, set()).update(IMMUTABLE_TRIGGERS)
        covered["rw_lease"] = set(LEASE_TRIGGERS)
        gateway_tables = [(r[1], r[0]) for r in relations if r[2] in ("r", "p") and (r[1] in FENCED_TABLES or r[1].startswith(("rw_", "rwp_", "md_")))]
        _trigger_set_findings(conn, schema, gateway_tables, covered, findings)
        inspected["trigger_tables"] = tuple(sorted(t[0] for t in gateway_tables))
        _membership_findings(conn, runtime, owner, version, findings)
        for name in UNIQUE_NAMES:
            count = conn.execute(
                "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname=%s AND c.conname=%s", (schema, name)).fetchone()[0]
            if count != 1:
                findings.append(Finding("RW_AUDIT_GUARD_NAME", name, "the name appears %d times among the schema's constraints" % count))
        inventory = frozenset(deferrable_inventory(conn, schema))
        inspected["deferrable"] = tuple(sorted(inventory))
        for item in sorted(inventory - EXPECTED_DEFERRABLE):
            findings.append(Finding("RW_AUDIT_DEFERRABLE_INVENTORY", item[0], "an unknown deferrable constraint on %s (%s)" % (item[1], item[2])))
        for item in sorted(EXPECTED_DEFERRABLE - inventory):
            findings.append(Finding("RW_AUDIT_DEFERRABLE_INVENTORY", item[0], "an expected deferrable constraint is missing on %s (%s)" % (item[1], item[2])))
        # the thirteen md read functions match the md_* tables
        md_tables = sorted(r[1] for r in relations if r[1].startswith("md_") and r[2] == "r")
        wanted = sorted("rw_md_" + t[len("md_"):] for t in md_tables)
        have = sorted(n for n in set(names) if n.startswith("rw_md_") and n != "rw_md_guard")
        if wanted != have or len(md_tables) != len(real_roles.MD_TABLES):
            findings.append(Finding("RW_AUDIT_MD_FUNCTIONS", "rw_md_*", "tables %s, functions %s" % (md_tables, have)))
        else:
            for table in md_tables:
                row = conn.execute(
                    "SELECT p.proretset,p.prorettype=t.reltype,p.prosecdef FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "JOIN pg_class t ON t.relname=%s AND t.relnamespace=n.oid WHERE n.nspname=%s AND p.proname=%s",
                    (table, schema, "rw_md_" + table[len("md_"):])).fetchone()
                if row != (True, True, True):
                    findings.append(Finding("RW_AUDIT_MD_FUNCTIONS", "rw_md_" + table[len("md_"):], "must be a SECURITY DEFINER SETOF %s function" % table))
        # every SECURITY DEFINER function pins its search_path, with pg_temp last
        for f in functions:
            if f[2]:
                setting = next((c for c in (f[3] or []) if c.startswith("search_path=")), None)
                if setting is None or not setting.rstrip().endswith("pg_temp"):
                    findings.append(Finding("RW_AUDIT_SEARCH_PATH", f[1], "a SECURITY DEFINER function without a search_path that ends in pg_temp"))
    except Exception as error:      # a catalog the audit cannot read is a finding, never a pass
        findings.append(Finding("RW_AUDIT_NOT_INSPECTED", schema, type(error).__name__))
    return AuditResult(as_kind, tuple(findings), inspected)
