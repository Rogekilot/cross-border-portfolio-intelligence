"""F1 R2: static checks of the candidate registry's SQL (persistence/real_provenance_v1.sql) and of the Python that installs and calls it.

No database; these read files. They pin properties the design states about the SQL text (pinned search paths, no dynamic SQL, one strict
time predicate, advisory locks outside the marker range, the grant plan, the order of the guard's checks, the order of the put function's
checks) so that an edit that breaks one fails in the default suite. They do NOT replace the PostgreSQL tests: a file that passes these has
not been run (see the self-validation record).
"""
from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src" / "persistence"
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

from persistence import real_provenance_store as provstore, real_roles  # noqa: E402

SQL_TEXT = (SRC / "real_provenance_v1.sql").read_text("utf8")
GATEWAY_TEXT = (SRC / "real_workspace_v1.sql").read_text("utf8")
PLACEHOLDERS = {"__RW_SCHEMA__", "__RW_EXECUTOR__", "__RW_LOADER__", "__RW_PUBLISHER__"}


def strip_comments(text):
    return "\n".join(re.sub(r"--.*$", "", line) for line in text.splitlines())


CODE = strip_comments(SQL_TEXT)
FUNCTIONS = {m.group(1): (m.group(2), m.group(3)) for m in re.finditer(r"CREATE FUNCTION __RW_SCHEMA__\.(\w+)\((.*?)\$\$(.*?)\$\$;", CODE, flags=re.S)}
TABLES = re.findall(r"CREATE TABLE __RW_SCHEMA__\.(\w+)", CODE)


def body_of(name):
    return FUNCTIONS[name][1]


def header_of(name):
    return FUNCTIONS[name][0]


def positions(body, order):
    found = [body.index(token) for token in order]
    return found


class RegistrySqlShapeTests(unittest.TestCase):
    def test_placeholders_are_exactly_the_four_validated_identifiers(self):
        self.assertEqual(set(re.findall(r"__RW_[A-Z]+__", SQL_TEXT)), PLACEHOLDERS)
        substituted = SQL_TEXT
        for marker in PLACEHOLDERS:
            substituted = substituted.replace(marker, "x_" + marker.strip("_").lower())
        self.assertNotIn("__RW_", substituted)

    def test_the_functions_are_the_thirteen_the_installer_checks(self):
        self.assertEqual(len(FUNCTIONS), len(re.findall(r"CREATE FUNCTION ", CODE)))
        self.assertEqual(set(FUNCTIONS), set(provstore.FUNCTIONS))
        self.assertEqual(len(FUNCTIONS), 13)
        self.assertEqual(CODE.count("$$") % 2, 0)
        stripped = re.sub(r"'(?:[^']|'')*'", "''", CODE)
        self.assertEqual(stripped.count("("), stripped.count(")"))

    def test_the_installers_table_matches_each_functions_header(self):
        volatility = {"IMMUTABLE": "i", "STABLE": "s", "VOLATILE": "v"}
        for name, (header, _body) in FUNCTIONS.items():
            kinds = [v for k, v in volatility.items() if re.search(r"\b" + k + r"\b", header)]
            self.assertEqual(len(kinds), 1, name)
            definer = "SECURITY DEFINER" in header
            self.assertEqual(provstore.FUNCTIONS[name][:2], (definer, kinds[0]), name)

    def test_every_function_pins_its_search_path_with_pg_temp_last(self):
        for name in FUNCTIONS:
            self.assertIn("SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp", header_of(name), name)

    def test_no_function_builds_dynamic_sql(self):
        for name, (_header, body) in FUNCTIONS.items():
            self.assertIsNone(re.search(r"\bEXECUTE\b", body), name)
            self.assertNotIn("format(", body, name)
        # The only EXECUTE of the file is the install-time revoke loop, which runs once, as the owner.
        self.assertEqual(len(re.findall(r"^DO \$\$", CODE, flags=re.M)), 1)
        self.assertEqual(len(re.findall(r"\bEXECUTE format\(", CODE)), 1)

    def test_the_pure_functions_cannot_write(self):
        for name in ("rwp_json", "rwp_keys", "rwp_permits", "rwp_origin", "rwp_validate_bundle"):
            self.assertIn("IMMUTABLE", header_of(name), name)
            self.assertIsNone(re.search(r"\b(INSERT|UPDATE|DELETE|TRUNCATE)\b", body_of(name)), name)
        # Not even a read of a table: the predicates and the validator take everything by value.
        for name in ("rwp_json", "rwp_keys", "rwp_permits", "rwp_origin", "rwp_validate_bundle"):
            self.assertIsNone(re.search(r"\bFROM\s+__RW_SCHEMA__\.rw", body_of(name)), name)

    def test_the_clock_is_read_by_the_guard_and_the_registration_stamp_only_and_compared_by_the_one_predicate(self):
        for word in ("now", "statement_timestamp", "transaction_timestamp", "current_timestamp", "localtimestamp", "current_date", "current_time", "localtime", "timeofday"):
            self.assertIsNone(re.search(r"\b" + word + r"\b", CODE, flags=re.I), word)
        self.assertEqual(sorted(re.findall(r"current_setting\('([^']+)'\)", CODE)), ["role", "transaction_isolation"])
        users = sorted(name for name, (_h, body) in FUNCTIONS.items() if "clock_timestamp()" in body)
        self.assertEqual(users, ["rwp_guard", "rwp_put_context"])
        self.assertIn("rw_reached(clock_timestamp(),l.complete_by)", body_of("rwp_guard"))
        self.assertEqual(body_of("rwp_guard").count("clock_timestamp()"), 1)
        # In put, clock_timestamp() is a recorded stamp (a VALUES item), never compared.
        self.assertEqual(body_of("rwp_put_context").count("clock_timestamp()"), 1)
        self.assertIsNone(re.search(r"(<=|>=|<|>)\s*clock_timestamp\(\)|clock_timestamp\(\)\s*(<=|>=|<|>)", CODE))
        for forbidden in ("set_config", "ALTER SYSTEM", "ALTER ROLE", "ALTER DATABASE", "CREATE ROLE", "CREATE DATABASE", "CREATE EXTENSION", "DISABLE TRIGGER"):
            self.assertNotIn(forbidden, CODE.upper(), forbidden)

    def test_exclusive_advisory_locks_stay_out_of_the_marker_key_range(self):
        exclusive = re.findall(r"pg_advisory_xact_lock\((.*?)\);", CODE)
        self.assertEqual(len(exclusive), 1)                                     # the registration lock
        self.assertTrue(exclusive[0].startswith("hashtextextended(") and exclusive[0].endswith("& 4611686018427387903"), exclusive[0])
        self.assertEqual(re.findall(r"pg_(?:try_)?advisory_xact_lock_shared", CODE), [])
        self.assertEqual(CODE.count("4611686018427387904"), 0)                  # no marker key is taken or read here

    def test_the_binding_key_leaves_the_registry_and_nothing_points_in(self):
        self.assertEqual(TABLES, ["rwp_payload", "rwp_acquisition", "rwp_manifest", "rwp_context", "rwp_registration"])
        references = re.findall(r"REFERENCES __RW_SCHEMA__\.(\w+)", CODE)
        self.assertEqual(sorted(references), sorted(["rwp_payload", "rwp_acquisition", "rw_snapshot", "rwp_context"]))
        self.assertNotIn("md_", CODE)
        for table in TABLES:
            self.assertIn("CREATE TRIGGER %s_immutable_rows BEFORE UPDATE OR DELETE ON __RW_SCHEMA__.%s FOR EACH ROW" % (table, table), CODE)
            self.assertIn("CREATE TRIGGER %s_immutable_truncate BEFORE TRUNCATE ON __RW_SCHEMA__.%s FOR EACH STATEMENT" % (table, table), CODE)
        # No gateway function reads a candidate except through the publish consultation.
        users = [name for name, _h, body in re.findall(r"CREATE FUNCTION __RW_SCHEMA__\.(\w+)\((.*?)\$\$(.*?)\$\$;", strip_comments(GATEWAY_TEXT), flags=re.S) if "rwp_" in body]
        self.assertEqual(users, ["rw_publish"])


class RegistrySqlGrantTests(unittest.TestCase):
    def test_public_holds_nothing_and_no_sql_file_grants_anything(self):
        """R3 moved the one grant this file held (EXECUTE on the executor's guarded load) into the executor's list in
        `persistence.real_roles`; the file now holds the revokes only, and the list is asserted below and against the catalog."""
        revoke = re.search(r"REVOKE ALL ON (.*?) FROM PUBLIC;", CODE, flags=re.S).group(1)
        for table in TABLES:
            self.assertIn("__RW_SCHEMA__." + table, revoke, table)
        self.assertIn("REVOKE ALL ON FUNCTION %I.%I(%s) FROM PUBLIC", CODE)
        self.assertIn("p.proname LIKE 'rwp\\_%'", CODE)
        grants = re.findall(r"^GRANT (.*?);", CODE, flags=re.S | re.M)
        self.assertEqual(grants, [])
        self.assertIn(("rwp_load_context", "text,text"), real_roles.role_lists("TEST")["executor"]["functions"])
        self.assertIn(("rwp_load_context", "text,text"), real_roles.role_lists("REAL")["executor"]["functions"])

    def test_the_loader_and_the_publisher_are_granted_nothing_in_the_sql(self):
        for grant in re.findall(r"^GRANT (.*?);", CODE, flags=re.S | re.M):
            self.assertNotIn("__RW_LOADER__", grant)
            self.assertNotIn("__RW_PUBLISHER__", grant)
        # The loader's placeholder is the identity the per-call role check compares with, and nothing else.
        for name, (_header, body) in FUNCTIONS.items():
            if "__RW_LOADER__" in body:
                self.assertIn(name, ("rwp_caller", "rwp_put_context", "rwp_get_context"))
        self.assertEqual(provstore.LOADER_EXECUTE, {"rwp_put_context", "rwp_get_context"})
        self.assertEqual(provstore.EXECUTOR_EXECUTE, {"rwp_load_context"})

    def test_the_loaders_grant_list_names_functions_that_exist_with_those_argument_types(self):
        for name, arguments in real_roles.LOADER_FUNCTIONS:
            self.assertIn(name, FUNCTIONS)
            header = header_of(name)
            declared = [part.split()[1] for part in re.split(r",\s*", header[:header.index(")") + 1].rstrip(")")) if part.strip()]
            normalised = ",".join(declared).replace("bytea[]", "bytea[]")
            self.assertEqual(normalised, arguments, name)

    def test_the_executors_function_is_security_definer_and_checks_the_executor_first(self):
        self.assertIn("SECURITY DEFINER", header_of("rwp_load_context"))
        body = body_of("rwp_load_context")
        self.assertTrue(body.strip().split("BEGIN", 1)[1].lstrip().startswith("PERFORM __RW_SCHEMA__.rwp_caller('__RW_EXECUTOR__')"))
        for name in ("rwp_put_context", "rwp_get_context"):
            self.assertIn("rwp_caller('__RW_LOADER__')", body_of(name))
        self.assertIn("RW_PROV_ROLE_REFUSED", body_of("rwp_caller"))
        # The per-call check requires LOGIN (exit statement R2 (b)) and names no inheritance condition (a role with no membership has none).
        self.assertIn("NOT r.rolcanlogin", body_of("rwp_caller"))


class RegistrySqlOrderTests(unittest.TestCase):
    def test_the_guard_checks_in_the_documented_order_and_the_deadline_before_any_read_of_a_candidate(self):
        body = body_of("rwp_guard")
        order = ["purpose IS NULL OR purpose NOT IN", "transaction_isolation", "FROM __RW_SCHEMA__.rw_mode WHERE singleton FOR SHARE",
                 "FROM __RW_SCHEMA__.rw_lease WHERE backend_pid=pg_backend_pid()", "RW_PROV_LEASE_REQUIRED", "RW_PROV_PURPOSE_REFUSED",
                 "rw_reached(clock_timestamp(),l.complete_by)", "FROM __RW_SCHEMA__.rw_head WHERE context_id=l.context_id FOR SHARE",
                 "rw_expiry_derive(", "rw_rights_valid(h.rights)", "FROM __RW_SCHEMA__.rw_root_link WHERE root_id=l.root_id", "rw_scope_allowed("]
        found = positions(body, order)
        self.assertEqual(found, sorted(found), dict(zip(order, found)))
        self.assertIn("RAISE EXCEPTION 'RW_DEADLINE'", body)
        self.assertNotIn("rwp_payload", body)                                  # the guard reads no candidate

    def test_the_guarded_load_runs_the_guard_before_it_reads_anything(self):
        body = body_of("rwp_load_context")
        order = ["rwp_caller('__RW_EXECUTOR__')", "rwp_guard(purpose)", "FROM __RW_SCHEMA__.rw_lease", "rwp_context x WHERE", "RW_PROV_CONTEXT_DIFFERS", "rwp_collect_context("]
        found = positions(body, order)
        self.assertEqual(found, sorted(found), dict(zip(order, found)))
        self.assertEqual(body.count("rwp_collect_context("), 1)

    def test_the_only_reader_of_a_candidate_for_a_caller_is_reached_through_get_or_load(self):
        readers = sorted(name for name, (_h, body) in FUNCTIONS.items() if "rwp_collect_context(" in body and name != "rwp_collect_context")
        self.assertEqual(readers, ["rwp_get_context", "rwp_load_context", "rwp_put_context"])           # put reads it back only for an idempotent replay

    def test_put_checks_in_order_caller_shape_structure_install_kind_origin_lock_binding_replay_then_writes(self):
        body = body_of("rwp_put_context")
        order = ["rwp_caller('__RW_LOADER__')", "RW_PROV_SHAPE", "rwp_validate_bundle(", "rw_scope_allowed(v_install", "'RW_INSTALL_KIND'",
                 "'RW_PROV_ORIGIN_REFUSED'", "pg_advisory_xact_lock(", "f:=c->>'financial_context_sha256'", "SELECT s.snapshot INTO v_snap",
                 "FROM __RW_SCHEMA__.rwp_registration WHERE operation_id=op", "RW_PROV_OPERATION_CONFLICT", "RW_PROV_CAPACITY",
                 "INSERT INTO __RW_SCHEMA__.rwp_payload", "INSERT INTO __RW_SCHEMA__.rwp_manifest", "INSERT INTO __RW_SCHEMA__.rwp_context",
                 "INSERT INTO __RW_SCHEMA__.rwp_registration"]
        found = positions(body, order)
        self.assertEqual(found, sorted(found), dict(zip(order, found)))

    def test_the_validators_return_the_origin_codes_and_the_callers_refuse(self):
        self.assertIn("RETURNS text[]", header_of("rwp_validate_bundle"))
        self.assertNotIn("RW_PROV_ORIGIN_REFUSED", body_of("rwp_validate_bundle"))
        self.assertIn("RW_PROV_ORIGIN_REFUSED", body_of("rwp_put_context"))
        self.assertIn("RW_PROV_ORIGIN_REFUSED", body_of("rwp_collect_context"))
        self.assertIn("USING DETAIL=array_to_string(v_codes,',')", body_of("rwp_put_context"))

    def test_the_origin_function_publish_calls_reads_registered_candidates_and_lists_a_missing_one(self):
        body = body_of("rwp_origin_failures")
        for token in ("rwp_origin(to_jsonb(recs),to_jsonb(facts))", "RW_PROV_CANDIDATE_MISSING", "FROM __RW_SCHEMA__.rwp_manifest x WHERE x.manifest_sha256=m->>'manifest_sha256'"):
            self.assertIn(token, body)
        self.assertIn("SECURITY DEFINER", header_of("rwp_origin_failures"))
        self.assertIn("STABLE", header_of("rwp_origin_failures"))


class OriginPredicateSqlShapeTests(unittest.TestCase):
    def test_o1_o2_o3_are_independent_branches_of_one_pure_function(self):
        body = body_of("rwp_origin")
        for code in ("'RW_O1_SYNTHETIC_SOURCE'", "'RW_O2_TERMS_CHECK'", "'RW_O3_ACQUISITION'"):
            self.assertIn(code, body)
        self.assertIn("x.value->'synthetic' IS DISTINCT FROM 'false'::jsonb", body)                    # O1: exactly the JSON value false
        self.assertIn("NOT __RW_SCHEMA__.rwp_permits(x.value->'terms_check')", body)                   # O2: the source's own terms check, read directly
        self.assertIn("x.value->>'schema'='v1' AND x.value->>'retrieved_by'='human' AND x.value->>'usage_scope'='INTERNAL_DEVELOPMENT_ONLY'",
                      " ".join(body.split()))                                                                   # O3: the member's own fields
        self.assertNotIn("terms_attested", CODE)
        permits = body_of("rwp_permits")
        self.assertIn("tc->'permits_internal_development_use'='true'::jsonb", permits)
        self.assertNotIn("synthetic", permits)                                                          # O2 never looks at the synthetic flag


if __name__ == "__main__":
    unittest.main()
