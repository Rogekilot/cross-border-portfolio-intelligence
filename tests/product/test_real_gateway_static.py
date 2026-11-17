"""F1 R1: static checks of the real gateway's SQL and Python. No database; these read files.

They pin properties the design states about the SQL text (the trusted clock, no dynamic SQL, pinned search paths, grants, the
deadline guard's shape and name, the admit order) so that an edit that breaks one fails in the default suite. They do NOT replace
the PostgreSQL tests: a file that passes these has not been run (see the self-validation record).
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src" / "persistence"
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

from persistence import real_roles, real_workspace_store as store  # noqa: E402

SQL_TEXT = (SRC / "real_workspace_v1.sql").read_text("utf8")
PLACEHOLDERS = {"__RW_SCHEMA__", "__RW_EXECUTOR__", "__RW_LOADER__", "__RW_PUBLISHER__"}


def strip_comments(text):
    return "\n".join(re.sub(r"--.*$", "", line) for line in text.splitlines())


CODE = strip_comments(SQL_TEXT)
# name -> (header: everything from the argument list to the opening $$, body: the text between the dollar quotes)
FUNCTIONS = {m.group(1): (m.group(2), m.group(3)) for m in re.finditer(
    r"CREATE FUNCTION __RW_SCHEMA__\.(\w+)\((.*?)\$\$(.*?)\$\$;", CODE, flags=re.S)}
EXECUTOR_FUNCTIONS = {"rw_admit", "rw_scope", "rw_list_roots", "rw_install_info"}
PUBLISHER_FUNCTIONS = {"rw_publish", "rw_renew", "rw_withdraw_mark", "rw_withdraw_apply", "rw_in_flight", "rw_install_info"}


def body_of(name):
    return FUNCTIONS[name][1]


def header_of(name):
    return FUNCTIONS[name][0]


class SqlShapeTests(unittest.TestCase):
    def test_placeholders_are_exactly_the_four_validated_identifiers(self):
        self.assertEqual(set(re.findall(r"__RW_[A-Z]+__", SQL_TEXT)), PLACEHOLDERS)
        substituted = SQL_TEXT
        for marker in PLACEHOLDERS:
            substituted = substituted.replace(marker, "x_" + marker.strip("_").lower())
        self.assertNotIn("__RW_", substituted)

    def test_every_create_function_was_parsed_and_quotes_balance(self):
        self.assertEqual(len(FUNCTIONS), len(re.findall(r"CREATE FUNCTION ", CODE)))
        self.assertEqual(len(FUNCTIONS), 22)             # R1's twenty-one plus rw_origin_expected (R3, the SQL twin of ScopeDef.origin_fields)
        self.assertEqual(CODE.count("$$") % 2, 0)
        stripped = re.sub(r"'(?:[^']|'')*'", "''", CODE)
        self.assertEqual(stripped.count("("), stripped.count(")"))
        for name, (header, body) in FUNCTIONS.items():
            text = body.strip()
            if "LANGUAGE plpgsql" in header:
                self.assertTrue(text.upper().startswith(("DECLARE", "BEGIN")), name)
                self.assertTrue(re.search(r"\bEND\s*$", text, flags=re.I), name)
            else:
                self.assertIn("LANGUAGE sql", header, name)
                self.assertTrue(text.upper().startswith(("SELECT", "WITH")), name)

    def test_every_function_pins_its_search_path_with_pg_temp_last(self):
        for name in FUNCTIONS:
            self.assertIn("SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp", header_of(name), name)

    def test_no_function_builds_dynamic_sql(self):
        for name, (_header, body) in FUNCTIONS.items():
            self.assertIsNone(re.search(r"\bEXECUTE\b", body), name)
            self.assertNotIn("format(", body, name)
        # The only EXECUTE is in the two install-time DO blocks (trigger loop, revoke loop), which run once, as the owner.
        self.assertEqual(len(re.findall(r"^DO \$\$", CODE, flags=re.M)), 2)

    def test_trusted_clock_is_clock_timestamp_alone_and_has_no_override(self):
        for word in ("now", "statement_timestamp", "transaction_timestamp", "current_timestamp", "localtimestamp", "current_date",
                     "current_time", "localtime", "timeofday"):
            self.assertIsNone(re.search(r"\b" + word + r"\b", CODE, flags=re.I), word)
        self.assertNotIn("set_config", CODE)
        self.assertEqual(sorted(set(re.findall(r"current_setting\('([^']+)'\)", CODE))), ["transaction_isolation"])
        for forbidden in ("ALTER SYSTEM", "ALTER ROLE", "ALTER DATABASE", "CREATE ROLE", "CREATE DATABASE", "CREATE EXTENSION", "DISABLE TRIGGER"):
            self.assertNotIn(forbidden, CODE.upper(), forbidden)
        # Admit takes no time: owner, root, context, generation, purpose, operation, command and new_root only.
        self.assertNotRegex(header_of("rw_admit").split(")")[0], r"timestamp|interval|clock|now|time")

    def test_admit_reads_latest_before_it_samples_and_samples_once(self):
        body = body_of("rw_admit")
        order = ["FROM rw_mode m WHERE m.singleton FOR SHARE", "FROM rw_head h WHERE h.context_id=p_context FOR SHARE",
                 "AND NOT EXISTS(SELECT 1 FROM rw_history x WHERE x.drain_mark_id=dm.mark_id)", "rw_expiry_derive(",
                 "NOT rw_scope_allowed(", "v_latest:=rw_latest_instant();", "v_now:=clock_timestamp();", "RW_CLOCK_REGRESSION", "RW_LAPSED",
                 "RW_WITHDRAWN", "RW_RIGHT_REFUSED", "pg_advisory_xact_lock(hashtextextended(", "INSERT INTO rw_lease("]
        positions = [body.index(token) for token in order]
        self.assertEqual(positions, sorted(positions), dict(zip(order, positions)))
        self.assertEqual(body.count("clock_timestamp()"), 1)
        self.assertIn("NOT rw_reached(v_now,v_latest)", body)
        self.assertIn("rw_reached(v_now,v_hist.valid_until)", body)
        self.assertIn("LEAST(v_now+(v_w*interval '1 second'),v_hist.valid_until)", body)

    def test_admit_checks_the_drain_mark_again_after_it_holds_the_root_lock(self):
        # Technical review R1, L-2: an admission that queued on the root lock behind another lease must still be refused by a mark
        # committed while it waited. The second check is a statement of its own after the lock and before the lease row.
        body = body_of("rw_admit")
        self.assertEqual(body.count("'RW_WITHDRAWAL_PENDING'"), 2)
        self.assertLess(body.index("pg_advisory_xact_lock(hashtextextended("), body.rindex("'RW_WITHDRAWAL_PENDING'"))
        self.assertLess(body.rindex("'RW_WITHDRAWAL_PENDING'"), body.index("INSERT INTO rw_lease("))

    def test_only_the_one_predicate_compares_an_instant_with_the_clock(self):
        # Technical review R1, L-10: the strict comparisons (guard, lapse, publish and renewal floor, clock regression) are one function,
        # `rw_reached`, which a test calls with EQUAL instants (the real clock cannot produce them). No other body compares the clock.
        self.assertEqual(body_of("rw_reached").strip(), "SELECT COALESCE(p_now>=p_limit,false)")
        self.assertIn("rw_reached(clock_timestamp(),NEW.complete_by)", body_of("rw_deadline_check"))
        self.assertIn("rw_reached(v_now,p_valid_until)", body_of("rw_publish"))
        self.assertIn("rw_reached(v_now,p_valid_until)", body_of("rw_renew"))
        for name in ("rw_deadline_check", "rw_admit", "rw_publish", "rw_renew"):
            body = body_of(name)
            self.assertIsNone(re.search(r"(v_now|clock_timestamp\(\))\s*(<=|>=|<|>)", body), name)
            self.assertIsNone(re.search(r"(<=|>=|<|>)\s*(v_now\b|clock_timestamp\(\))", body), name)
        # Nothing but the predicate's own helpers is callable by a runtime role: the predicate takes instants and is never granted
        # (since R3 the grants are the lists of persistence.real_roles, not statements of this file).
        for role, spec in real_roles.role_lists("TEST").items():
            self.assertNotIn("rw_reached", {name for name, _args in spec["functions"]}, role)

    def test_exclusive_advisory_locks_stay_out_of_the_marker_key_range(self):
        # Technical review R1, L-1: the lease markers own the one-bigint keys [2^62, 2^62 + 2^53) and the two-int class
        # hashtext('rw.lease.ctx'). The gateway's own exclusive locks are masked below 2^62, and the markers are TRY locks.
        exclusive = re.findall(r"pg_advisory_xact_lock\((.*?)\);", CODE)
        self.assertEqual(len(exclusive), 3)                    # the root lock, the operation lock (R3, replay) and the publish lock
        for argument in exclusive:
            self.assertTrue(argument.startswith("hashtextextended(") and argument.endswith("& 4611686018427387903"), argument)
        self.assertEqual(re.findall(r"pg_advisory_xact_lock_shared", CODE), [])
        self.assertEqual(len(re.findall(r"pg_try_advisory_xact_lock_shared\(", CODE)), 2)
        self.assertEqual(CODE.count("4611686018427387904"), 2)                  # the marker key, and the lower bound in rw_in_flight
        self.assertIn("[2^62, 2^62 + 2^53)", SQL_TEXT)
        self.assertIn("b.classid::bigint>=1073741824 AND b.classid::bigint<1075838976", body_of("rw_in_flight"))     # 2^30 .. 2^30 + 2^21
        self.assertEqual(1073741824 * 2 ** 32, 2 ** 62)
        self.assertEqual((1075838976 - 1073741824) * 2 ** 32, 2 ** 53)

    def test_the_cap_is_a_table_check(self):
        check = re.search(r"CONSTRAINT rw_lease_deadline_cap CHECK\((.*?)\)\s*\n\);", CODE, flags=re.S)
        self.assertIsNotNone(check)
        self.assertIn("complete_by>admitted_at", check.group(1))
        self.assertIn("valid_until IS NULL OR complete_by<=valid_until", check.group(1))

    def test_the_deadline_guard_is_one_constraint_trigger_of_its_own(self):
        triggers = re.findall(r"CREATE CONSTRAINT TRIGGER (\w+) (.*?);", CODE, flags=re.S)
        self.assertEqual(len(triggers), 1)
        name, rest = triggers[0]
        self.assertEqual(name, "rw_lease_deadline_guard")
        self.assertIn("AFTER INSERT ON __RW_SCHEMA__.rw_lease", rest)
        self.assertIn("DEFERRABLE INITIALLY DEFERRED", rest)
        self.assertIn("FOR EACH ROW", rest)
        self.assertIn("rw_deadline_check()", rest)
        self.assertEqual(CODE.count("rw_lease_deadline_guard"), 1)
        self.assertEqual(CODE.count("SET CONSTRAINTS"), 0)
        deadline = body_of("rw_deadline_check")
        self.assertIn("rw_reached(clock_timestamp(),NEW.complete_by)", deadline)       # strict: the first refused instant is complete_by
        self.assertIn("RAISE EXCEPTION 'RW_DEADLINE'", deadline)
        self.assertEqual(deadline.count("clock_timestamp()"), 1)

    def test_the_root_link_foreign_key_is_named_deferrable_and_deferred(self):
        self.assertRegex(CODE, r"CONSTRAINT rw_root_link_portfolio_fkey FOREIGN KEY\(root_id\) REFERENCES __RW_SCHEMA__\.portfolio\(portfolio_id\) "
                                r"DEFERRABLE INITIALLY DEFERRED")
        # The lease-to-root-link key is NOT deferrable: SET CONSTRAINTS names only deferrable constraints.
        lease_fk = re.search(r"CONSTRAINT rw_lease_root_fkey[^\n]*", CODE).group(0)
        self.assertNotIn("DEFERRABLE", lease_fk)
        # Two deferrable objects in the whole file: the root-link key and the deadline guard.
        self.assertEqual(len(re.findall(r"\bDEFERRABLE\b", CODE)), 2)

    def test_grants_follow_the_role_plan(self):
        """R3 (design 4.2 build table, 1.2 rule 5.3 (e)): NO SQL FILE OF THE GATEWAY GRANTS ANYTHING. The lists are data in
        `persistence.real_roles`, applied once by the installer after the last file, for TEST and REAL alike (R1 had the publisher's and the
        executor's grants here; R2 had the loader's USAGE here). The lists are checked against the catalog in test_postgres_real_gateway_core."""
        for filename in real_roles.sql_files("TEST"):
            code = strip_comments((SRC / filename).read_text("utf8"))
            self.assertIsNone(re.search(r"^\s*GRANT\b", code, flags=re.M | re.I), filename)
            # (the registry names the loader and executor as the identities its per-call role check compares with: not a grant)
        self.assertEqual({"__RW_SCHEMA__"}, set(re.findall(r"__RW_[A-Z]+__", CODE)))
        lists = real_roles.role_lists("TEST")
        self.assertEqual({n for n, _a in lists["publisher"]["functions"]}, PUBLISHER_FUNCTIONS)
        self.assertEqual({n for n, _a in lists["executor"]["functions"] if n.startswith("rw_") and not n.startswith("rw_md_")} & PUBLISHER_FUNCTIONS,
                         {"rw_install_info"})
        self.assertTrue(EXECUTOR_FUNCTIONS <= {n for n, _a in lists["executor"]["functions"]})
        self.assertEqual(lists["publisher"]["tables"], {"rw_pending_marks": frozenset(("SELECT",)), "rw_status": frozenset(("SELECT",))})

    def test_public_holds_nothing(self):
        revoke = re.search(r"REVOKE ALL ON (.*?) FROM PUBLIC;", CODE, flags=re.S).group(1)
        objects = {"rw_install", "rw_mode", "rw_snapshot", "rw_drain_mark", "rw_history", "rw_head", "rw_root_link", "rw_lease",
                   "rw_pending_marks", "rw_status"}
        for name in objects:
            self.assertIn("__RW_SCHEMA__." + name, revoke, name)
        self.assertIn("REVOKE ALL ON FUNCTION %I.%I(%s) FROM PUBLIC", CODE)
        created = set(re.findall(r"CREATE (?:TABLE|VIEW) __RW_SCHEMA__\.(\w+)", CODE))
        self.assertEqual(created, objects)

    def test_functions_the_roles_may_call_run_as_the_owner(self):
        for name in sorted(EXECUTOR_FUNCTIONS | PUBLISHER_FUNCTIONS):
            self.assertIn("SECURITY DEFINER", header_of(name), name)
        # And nothing a role cannot call is granted by accident: a helper of this file that no list names has no EXECUTE grant to any role.
        granted = {n for spec in real_roles.role_lists("TEST").values() for n, _a in spec["functions"]}
        for name in set(FUNCTIONS) - EXECUTOR_FUNCTIONS - PUBLISHER_FUNCTIONS:
            self.assertNotIn(name, granted, name)

    def test_immutable_objects_have_triggers(self):
        for table in ("rw_install", "rw_snapshot", "rw_history", "rw_drain_mark", "rw_root_link"):
            self.assertIn("'" + table + "'", CODE)
        self.assertIn("rw_head_guard_delete BEFORE DELETE ON __RW_SCHEMA__.rw_head", CODE)
        self.assertIn("rw_lease_guard_write BEFORE UPDATE OR DELETE ON __RW_SCHEMA__.rw_lease", CODE)

    def test_drain_mark_columns_are_all_not_null_with_format_checks(self):
        table = re.search(r"CREATE TABLE __RW_SCHEMA__\.rw_drain_mark \((.*?)\n\);", CODE, flags=re.S).group(1)
        for column in ("context_id", "generation", "issuer_actor", "pd_id", "git_commit", "doc_sha256", "marked_at", "db_session_user"):
            self.assertRegex(table, r"\b" + column + r"\b[^,\n]*NOT NULL")
        self.assertIn("pd_id ~ '^PD-[0-9]{4,}$'", table)
        self.assertIn("git_commit ~ '^[0-9a-f]{40}$'", table)
        self.assertIn("doc_sha256 ~ '^[0-9a-f]{64}$'", table)

    def test_publish_cannot_name_sources_and_runs_the_origin_validators_for_the_real_scope(self):
        self.assertNotIn("source", header_of("rw_publish").split("RETURNS")[0])
        body = body_of("rw_publish")
        self.assertIn("rw_snapshot_sources(p_snapshot)", body)
        # R2: the R1 placeholder is gone and the REAL branch consults the registry's validators, whose result is appended to the same
        # list of codes (every failed predicate is reported). The call is made for the REAL scope and passes the stored bytes only.
        self.assertNotIn("RW_REAL_SCOPE_UNWIRED", SQL_TEXT)
        self.assertRegex(body, r"IF v_scope='REAL' THEN v_codes:=v_codes\|\|rwp_origin_failures\(p_snapshot\); END IF;")
        self.assertIn("RW_INSTALL_KIND", body)


class PythonShapeTests(unittest.TestCase):
    # R2 adds the registry's three modules and the loader's list: none reads the environment, a file store or a guarded (F2) module.
    MODULES = ("real_scope.py", "real_proposal.py", "real_workspace_context.py", "real_workspace_store.py",
               "real_provenance.py", "real_provenance_store.py", "real_roles.py")

    def trees(self):
        return {name: ast.parse((SRC / name).read_text("utf8")) for name in self.MODULES}

    def test_no_environment_file_store_or_guarded_module_in_the_real_gateway(self):
        for name in self.MODULES:
            text = (SRC / name).read_text("utf8")
            for token in ("os.environ", "getenv", "FileStore", "SOURCES.json", "load_registry"):
                self.assertNotIn(token, text, "%s: %s" % (name, token))
        for name, tree in self.trees().items():
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [(node.module or "")] + [(node.module or "") + "." + a.name for a in node.names]
                for module in modules:
                    self.assertNotRegex(module, r"guarded_|web_workspace|web_account|web_csv|market_data_store|marketdata\.files|^os$",
                                        "%s imports %s" % (name, module))

    def test_no_python_code_issues_set_constraints_all(self):
        for name in self.MODULES:
            self.assertNotRegex((SRC / name).read_text("utf8").upper(), r"SET\s+CONSTRAINTS\s+ALL", name)

    def test_only_a_test_install_is_ever_written_by_product_code(self):
        text = (SRC / "real_workspace_store.py").read_text("utf8")
        self.assertEqual(re.findall(r"VALUES\(true,'(\w+)'", text), ["TEST"])
        parameters = inspect.signature(store.install_test_gateway).parameters
        self.assertEqual(set(parameters), {"conn", "schema", "owner_role", "executor_role", "loader_role", "publisher_role", "w_seconds", "account_role"})
        # R6: the reserved real-install prefix is ONE constant, defined in `persistence/connection.py` (the lowest module, so that the provisioner, the
        # environment-driven tests and the tools read the same one); no module of the gateway's Python side spells it any more.
        literals = []
        for name, tree in self.trees().items():
            literals += [(name, n.value) for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                         and "finweb_real" in n.value]
        self.assertEqual(literals, [])
        connection_tree = ast.parse((SRC / "connection.py").read_text("utf8"))
        defining = [n for n in ast.walk(connection_tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RESERVED_REAL_PREFIX" for t in n.targets)]
        self.assertEqual(len(defining), 1)
        self.assertEqual(store.RESERVED_REAL_PREFIX, "finweb_real")
        self.assertNotIn("finweb_real", (SRC / "real_workspace_v1.sql").read_text("utf8"))

    def test_cli_has_no_credential_switch_or_preflight_option(self):
        options, stack = set(), [store._build_parser()]
        while stack:
            current = stack.pop()
            for action in current._actions:
                options.update(action.option_strings)
                if isinstance(getattr(action, "choices", None), dict):
                    stack.extend(action.choices.values())
        for forbidden in ("--password", "--passfile", "--pgpass", "--dsn", "--url", "--switch", "--test-switch", "--kind", "--install-kind",
                          "--preflight", "--skip-preflight", "--no-preflight", "--superuser", "--role", "--w", "--clock", "--now"):
            self.assertNotIn(forbidden, options, forbidden)
        self.assertEqual({"--socket", "--database", "--user", "--schema"} - options, set())

    def test_publish_has_no_input_that_names_sources(self):
        # R4b adds `sidecars` (the sidecar acquisition records, as bytes, of a REAL proposal's members: O5 is evaluated in Python because the
        # database cannot see sidecar bytes). It names no source and sets no expiry kind, right or lease: a sidecar is evidence about a FILE
        # that the member already names by digest, and a test scope ignores it. The parameter is keyword-only (the check below).
        self.assertEqual(list(inspect.signature(store.RealPublisher.publish).parameters),
                         ["self", "proposal", "rights", "valid_until", "evidence", "actor", "ref", "sidecars"])
        self.assertEqual(inspect.signature(store.RealPublisher.publish).parameters["sidecars"].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_plausibility_wording_is_an_upper_bound_and_never_within(self):
        wording = store.PLAUSIBILITY_WORDING
        self.assertEqual(wording, "`valid_until` is not later than the recorded upper bound of the term end; "
                                  "no lower bound of the term end is recorded")
        self.assertNotIn("within", wording.lower())
        self.assertNotIn("margin", wording.lower())
        self.assertIn("upper bound", wording)

    def test_exit_statuses_are_distinct_and_only_done_is_zero(self):
        codes = [store.EXIT_DONE, store.EXIT_REFUSED, store.EXIT_NOT_YET_EFFECTIVE, store.EXIT_UNKNOWN, store.EXIT_LOCK_TIMEOUT]
        self.assertEqual(len(set(codes)), 5)
        self.assertEqual([c for c in codes if c == 0], [store.EXIT_DONE])


if __name__ == "__main__":
    unittest.main()
