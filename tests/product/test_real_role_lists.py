"""F1 R3, no database: the role lists and the SQL file lists that the shared installer code returns for each install kind (design 4.2 build
table, 1.2 rule 5.3 (e), section 1 item 1).

These are tests ON THE LISTS. A REAL install exists only at R8 step 1, so R3 shows the lists, the file split and that the catalog audit can see
(test_postgres_real_catalog_audit); it does not show that a REAL database holds no fictional-branch function or that REAL's grants are right.
The expected values below are written by hand from the design; they are not read from `real_roles`.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src" / "persistence"
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from persistence import real_roles, real_workspace_store as store  # noqa: E402
from persistence.real_workspace_context import RealWorkspaceError  # noqa: E402

RUNTIME = ("executor", "loader", "publisher")
MD_TABLES = ("md_file", "md_release", "md_release_file", "md_quote", "md_fx_rate", "md_corporate_action", "md_benchmark", "md_benchmark_point",
             "md_adjusted_quote", "md_calendar", "md_series_exclusion", "md_risk_free", "md_risk_free_point")
SELECT_INSERT = frozenset(("SELECT", "INSERT"))
# The executor's table list, by hand from design 1 item 5 and 2.6. R3 fix round (technical review M-1, L-6): no privilege on issuer, instrument,
# listing or app_user, which carry no root, fence or journal and which no R3 path needs.
EXECUTOR_TABLES = {"portfolio": SELECT_INSERT, "account": SELECT_INSERT, "ledger_event": SELECT_INSERT, "benchmark_selection": SELECT_INSERT,
                   "rw_root": SELECT_INSERT, "rw_revision": SELECT_INSERT}


def code(filename):
    return "\n".join(re.sub(r"--.*$", "", line) for line in (SRC / filename).read_text("utf8").splitlines())


class TableAndSequenceListsTests(unittest.TestCase):
    def test_for_every_runtime_role_the_two_table_grant_lists_are_identical(self):
        test, real = real_roles.role_lists("TEST"), real_roles.role_lists("REAL")
        for role in RUNTIME + ("public",):
            self.assertEqual(test[role]["tables"], real[role]["tables"], role)
            self.assertEqual(test[role]["sequences"], real[role]["sequences"], role)

    def test_the_executors_table_list_is_exactly_the_designed_one(self):
        for kind in ("TEST", "REAL"):
            self.assertEqual(real_roles.role_lists(kind)["executor"]["tables"], EXECUTOR_TABLES, kind)
            self.assertEqual(real_roles.role_lists(kind)["executor"]["sequences"],
                             {"ledger_event_ledger_seq_seq": frozenset(("USAGE",)), "benchmark_selection_seq_seq": frozenset(("USAGE",))}, kind)

    def test_the_executor_has_none_of_the_legacy_web_tables_and_none_of_the_md_tables(self):
        for kind in ("TEST", "REAL"):
            held = set(real_roles.role_lists(kind)["executor"]["tables"])
            self.assertFalse({"web_saved_sandbox", "web_portfolio_revision"} & held, kind)
            self.assertFalse([t for t in held if t.startswith("web_") or t.startswith("md_")], kind)
            self.assertFalse(held & set(MD_TABLES), kind)
            # nor any authority-core table: the lease, the registry, the snapshot, the head, the history, the marks, the mode, the install row
            self.assertFalse(held & {"rw_install", "rw_mode", "rw_snapshot", "rw_history", "rw_head", "rw_drain_mark", "rw_root_link", "rw_lease",
                                     "rw_artifact", "rw_operation", "rw_journal", "rw_pending_marks", "rw_status"}, kind)
            self.assertFalse([t for t in held if t.startswith("rwp_")], kind)

    def test_the_loader_and_the_publisher_lists_are_the_designed_ones(self):
        for kind in ("TEST", "REAL"):
            lists = real_roles.role_lists(kind)
            self.assertEqual(lists["loader"]["tables"], {t: (SELECT_INSERT if t in ("md_file", "md_release") else frozenset(("INSERT",))) for t in MD_TABLES}, kind)
            self.assertEqual(lists["loader"]["sequences"], {}, kind)
            self.assertEqual(lists["publisher"]["tables"], {"rw_pending_marks": frozenset(("SELECT",)), "rw_status": frozenset(("SELECT",))}, kind)
            self.assertEqual(lists["publisher"]["sequences"], {}, kind)
            self.assertEqual(lists["public"], {"tables": {}, "sequences": {}, "functions": frozenset()}, kind)

    def test_no_list_grants_a_privilege_that_could_change_or_remove_a_row_or_a_definition(self):
        for kind in ("TEST", "REAL"):
            for role, spec in real_roles.role_lists(kind).items():
                if role == "account":
                    continue                # PD-0078: the account role's session tables are the one place where UPDATE and DELETE are granted (below)
                for table, privileges in spec["tables"].items():
                    self.assertTrue(privileges <= SELECT_INSERT, (kind, role, table, privileges))

    def test_the_account_roles_list_is_exactly_the_one_of_pd_0078(self):
        """PD-0078 consequence 1: SELECT and INSERT on app_user and web_identity; SELECT, INSERT, UPDATE and DELETE on web_session and web_auth_rate;
        USAGE on the schema; nothing else (no sequence, no function, no economic, rooted or md_* table). The list may be narrowed, never widened."""
        full = frozenset(("SELECT", "INSERT", "UPDATE", "DELETE"))
        for kind in ("TEST", "REAL"):
            spec = real_roles.role_lists(kind)["account"]
            self.assertEqual(spec["tables"], {"app_user": SELECT_INSERT, "web_identity": SELECT_INSERT, "web_session": full, "web_auth_rate": full}, kind)
            self.assertEqual((spec["sequences"], spec["functions"]), ({}, frozenset()), kind)
            statements = real_roles.grant_statements(kind, "rw_x", "e", "l", "p", "rw_x_acct")
            mine = [s for s in statements if s.endswith('TO "rw_x_acct"')]
            self.assertEqual(sorted(mine), sorted([
                'GRANT USAGE ON SCHEMA "rw_x" TO "rw_x_acct"', 'GRANT INSERT, SELECT ON "rw_x".app_user TO "rw_x_acct"',
                'GRANT INSERT, SELECT ON "rw_x".web_identity TO "rw_x_acct"', 'GRANT DELETE, INSERT, SELECT, UPDATE ON "rw_x".web_session TO "rw_x_acct"',
                'GRANT DELETE, INSERT, SELECT, UPDATE ON "rw_x".web_auth_rate TO "rw_x_acct"']), kind)
            self.assertEqual(real_roles.grant_statements(kind, "rw_x", "e", "l", "p"), [s for s in statements if not s.endswith('TO "rw_x_acct"')], kind)
            for bad in ("Bad", "a b", "", 5):                       # None is the four-role install
                with self.assertRaises(RealWorkspaceError):
                    real_roles.grant_statements(kind, "rw_x", "e", "l", "p", bad)
                for sequence, privileges in spec["sequences"].items():
                    self.assertEqual(privileges, frozenset(("USAGE",)), (kind, role, sequence))

    def test_the_statements_are_a_revoke_of_public_then_exactly_the_lists(self):
        for kind in ("TEST", "REAL"):
            statements = real_roles.grant_statements(kind, "rw_x", "rw_x_exec", "rw_x_load", "rw_x_pub")
            self.assertEqual(statements[0], 'REVOKE EXECUTE ON ALL ROUTINES IN SCHEMA "rw_x" FROM PUBLIC')
            self.assertEqual([s for s in statements if s.startswith("REVOKE")], statements[:1])
            joined = "\n".join(statements)
            self.assertNotRegex(joined, r"(?i)\bTO PUBLIC\b|WITH GRANT OPTION|\bALL PRIVILEGES\b|\bGRANT ALL\b")
            for statement in statements[1:]:
                self.assertRegex(statement, r'^GRANT [A-Z, ]+ ON (SCHEMA "rw_x"|SEQUENCE "rw_x"\.\w+|"rw_x"\.\w+|FUNCTION "rw_x"\.\w+\([a-z0-9_,\[\]]*\)) TO "rw_x_(exec|load|pub)"$')
            # each role's statements name only that role
            for role, suffix in (("executor", "exec"), ("loader", "load"), ("publisher", "pub")):
                mine = [s for s in statements[1:] if s.endswith('TO "rw_x_%s"' % suffix)]
                self.assertEqual(len(mine), 1 + len(real_roles.role_lists(kind)[role]["tables"]) + len(real_roles.role_lists(kind)[role]["sequences"])
                                 + len(real_roles.role_lists(kind)[role]["functions"]), (kind, role))
            self.assertEqual(len(statements), 1 + 3 + sum(len(spec["tables"]) + len(spec["sequences"]) + len(spec["functions"])
                                                           for role, spec in real_roles.role_lists(kind).items() if role not in ("public", "account")))

    def test_identifiers_are_validated(self):
        for bad in ("Rw_x", "rw x", 'rw";drop', "", None, "a" * 64):
            with self.subTest(bad), self.assertRaises(RealWorkspaceError):
                real_roles.grant_statements("TEST", bad, "e", "l", "p")
            with self.subTest(role=bad), self.assertRaises(RealWorkspaceError):
                real_roles.grant_statements("TEST", "rw_x", bad, "l", "p")
        with self.assertRaises(ValueError):
            real_roles.role_lists("PRODUCTION")
        with self.assertRaises(ValueError):
            real_roles.sql_files("PRODUCTION")


class FileSplitTests(unittest.TestCase):
    def test_reals_file_list_omits_the_test_only_part_and_nothing_else(self):
        self.assertEqual(real_roles.sql_files("REAL"), ("real_workspace_v1.sql", "real_provenance_v1.sql", "real_fence_v1.sql"))
        self.assertEqual(real_roles.sql_files("TEST"), real_roles.sql_files("REAL") + ("real_workspace_fictional_v1.sql",))
        self.assertEqual(set(real_roles.sql_files("TEST")) - set(real_roles.sql_files("REAL")), {"real_workspace_fictional_v1.sql"})
        self.assertNotIn("fictional", " ".join(real_roles.sql_files("REAL")))
        for name in real_roles.sql_files("TEST"):
            self.assertTrue((SRC / name).is_file(), name)

    def test_the_test_only_part_is_functions_only_and_its_list_is_the_files(self):
        text = code("real_workspace_fictional_v1.sql")
        self.assertEqual(re.findall(r"\bCREATE\s+(?!FUNCTION\b)\w+", text, flags=re.I), [])             # no table, trigger, policy, view, constraint
        self.assertNotRegex(text, r"(?i)\b(GRANT|REVOKE|ALTER|DROP|INSERT|UPDATE|DELETE|DISABLE)\b")
        created = re.findall(r"CREATE FUNCTION __RW_SCHEMA__\.(\w+)\((.*?)\)\s+RETURNS", text, flags=re.S)
        listed = {(n, a) for n, a in real_roles.TEST_ONLY_FUNCTIONS}
        found = {(n, ",".join(re.sub(r"\bp_\w+\s+", "", part.strip()) for part in a.split(","))) for n, a in created}
        self.assertEqual(found, listed)
        self.assertEqual(real_roles.TEST_ONLY_SQL_FILES, ("real_workspace_fictional_v1.sql",))

    def test_the_core_names_the_test_only_function_in_one_place_and_only_at_run_time(self):
        for name in real_roles.CORE_SQL_FILES:
            text = code(name)
            if name == "real_fence_v1.sql":
                self.assertEqual(len(re.findall(r"rw_check_fictional", text)), 1)
                self.assertRegex(text, r"IF scope='SYNTHETIC_TEST' THEN\s+codes:=codes\|\|rw_check_fictional\(e,issued_obj,response_obj,ctx\);")
            else:
                self.assertNotIn("rw_check_fictional", text, name)
            self.assertNotIn("real_workspace_fictional", text, name)

    def test_the_function_grants_of_the_two_kinds_differ_by_the_test_only_functions_only(self):
        test, real = real_roles.role_lists("TEST"), real_roles.role_lists("REAL")
        test_only = set(real_roles.TEST_ONLY_FUNCTIONS)
        for role in RUNTIME + ("public",):
            difference = test[role]["functions"] ^ real[role]["functions"]
            self.assertTrue(difference <= test_only, (role, difference))
            # in fact the difference is empty: the core calls the TEST-only function as the owner, so no runtime role is granted it
            self.assertEqual(difference, set(), role)
            self.assertFalse(test[role]["functions"] & test_only, role)

    def test_every_function_a_list_names_is_created_by_a_file_of_that_kind(self):
        declared = {kind: set() for kind in ("TEST", "REAL")}
        for kind in declared:
            for name in real_roles.sql_files(kind):
                declared[kind].update(re.findall(r"CREATE FUNCTION __RW_SCHEMA__\.(\w+)\(", code(name)))
        for kind in ("TEST", "REAL"):
            for role in RUNTIME:
                names = {n for n, _a in real_roles.role_lists(kind)[role]["functions"]}
                self.assertTrue(names <= declared[kind], (kind, role, names - declared[kind]))
        self.assertEqual(declared["TEST"] - declared["REAL"], {n for n, _a in real_roles.TEST_ONLY_FUNCTIONS})

    def test_no_sql_file_grants_anything_and_the_installer_takes_both_lists_from_the_shared_module(self):
        for kind in ("TEST", "REAL"):
            for name in real_roles.sql_files(kind):
                self.assertNotRegex(code(name), r"(?im)^\s*GRANT\b", name)
        source = (SRC / "real_workspace_store.py").read_text("utf8")
        self.assertIn("real_roles.sql_files(kind)", source)
        self.assertIn("real_roles.apply_role_grants(conn, schema, executor_role, loader_role, publisher_role, kind, account_role)", source)
        self.assertEqual(store.GATEWAY_SQL_FILES, real_roles.sql_files("TEST"))
        # the product installer's own signature has no kind, it calls the body with the body's default (TEST), and it records TEST only
        import inspect
        self.assertNotIn("kind", inspect.signature(store.install_test_gateway).parameters)
        installer = inspect.getsource(store.install_test_gateway)
        self.assertIn("_install_gateway_body(conn, names, owner_role, executor_role, loader_role, publisher_role, account_role=account_role)", installer)
        self.assertNotIn("kind=", installer)
        self.assertEqual(inspect.signature(store._install_gateway_body).parameters["kind"].default, "TEST")
        self.assertEqual(re.findall(r"VALUES\(true,'(\w+)'", source), ["TEST"])


class MdReadListTests(unittest.TestCase):
    def test_the_thirteen_read_functions_are_the_executors_alone(self):
        names = {"rw_md_" + t[len("md_"):] for t in MD_TABLES}
        self.assertEqual({n for n, _a in real_roles.MD_READ_FUNCTIONS}, names)
        for kind in ("TEST", "REAL"):
            lists = real_roles.role_lists(kind)
            self.assertTrue(set(real_roles.MD_READ_FUNCTIONS) <= lists["executor"]["functions"])
            for role in ("loader", "publisher", "public"):
                self.assertFalse({n for n, _a in lists[role]["functions"]} & names, (kind, role))
        self.assertNotIn(("rw_md_guard", "text"), real_roles.role_lists("TEST")["executor"]["functions"])


if __name__ == "__main__":
    unittest.main()
