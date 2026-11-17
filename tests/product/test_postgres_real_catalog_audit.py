"""F1 R3, PostgreSQL: the CATALOG AUDIT as product code (design 1.2 rule 5.3 (e), 1 item 1, T03; `persistence.real_catalog_audit`).

Shown here, on disposable databases: the audit passes a TEST install as TEST; it reports the TEST-only part's functions when asked to read the
same catalog as REAL; it passes the crafted REAL fixture (the REAL file list and REAL lists run in a disposable database: E11, NOT a REAL
database) as REAL and reports the missing TEST-only part when asked to read it as TEST; and it reports each crafted drift of any runtime role or
of `public`. Each drift is made by the administrative role of the disposable database (E11 crafted) and reverted; the control after each is a
clean audit. R3 does not claim that a REAL database holds no fictional-branch function or that REAL's grants are right: the REAL catalog is first
read by Phase 2 at R8 step 1, and what these tests show is that the audit can see.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from persistence import real_catalog_audit as audit_module, real_roles  # noqa: E402
from real_gateway_kit import GatewayCase, setUpModule, tearDownModule  # noqa: E402,F401

# Written by hand: the deferrable constraints of the gateway schema (migrations 0003 and 0019, R1's root-link key and the two R1/R3 guards).
DEFERRABLE = {("ledger_event_transfer_pairing", "ledger_event", "t"), ("rw_root_link_portfolio_fkey", "rw_root_link", "f"),
              ("rw_bundle_complete", "rw_lease", "t"), ("rw_lease_deadline_guard", "rw_lease", "t"),
              ("web_csv_source_key_report_id_fkey", "web_csv_source_key", "f")}
TEST_ONLY = {"rw_check_fictional"}


class AuditCase(GatewayCase):
    def audit(self, kind, conn=None):
        roles = self.inst.roles
        return audit_module.audit(conn or self.admin, self.s, roles["owner"], roles["executor"], roles["loader"], roles["publisher"], as_kind=kind)

    def codes_and_subjects(self, result):
        return {(f.code, f.subject) for f in result.findings}


class TestInstallTests(AuditCase):
    INSTALL = "audit"

    def test_a_test_install_passes_as_test(self):
        """Product path: the same function the installer runs at its end. A catalog the audit cannot read would be a finding, not a pass."""
        result = self.audit("TEST")
        self.assertEqual(result.findings, (), [f.short() for f in result.findings])
        self.assertTrue(result.ok)
        inspected = result.inspected
        self.assertIn("rw_check_fictional", inspected["gateway_functions"])
        self.assertGreater(len(inspected["gateway_functions"]), 60)
        self.assertGreater(len(inspected["relations"]), 40)             # every relation of the schema was inspected, migration tables included
        self.assertIn("app_user", inspected["relations"])
        self.assertEqual(inspected["install_rows"], ("TEST",))

    def test_the_same_catalog_read_as_real_reports_the_test_only_functions_and_the_kind_row(self):
        result = self.audit("REAL")
        self.assertIn(("RW_AUDIT_TEST_ONLY_PRESENT", "rw_check_fictional"), self.codes_and_subjects(result))
        self.assertIn(("RW_AUDIT_INSTALL_ROW", "rw_install"), self.codes_and_subjects(result))
        self.assertEqual({f.subject for f in result.findings if f.code == "RW_AUDIT_TEST_ONLY_PRESENT"}, TEST_ONLY)
        self.assertEqual(result.codes(), ("RW_AUDIT_INSTALL_ROW", "RW_AUDIT_TEST_ONLY_PRESENT"))

    def test_a_missing_schema_or_an_unreadable_catalog_is_a_finding_never_a_pass(self):
        roles = self.inst.roles
        missing = audit_module.audit(self.admin, "no_such_schema", roles["owner"], roles["executor"], roles["loader"], roles["publisher"], as_kind="TEST")
        self.assertEqual(missing.codes(), ("RW_AUDIT_NOT_INSPECTED",))
        # a role that cannot read the gateway's tables: the audit reads catalogs only, but a closed connection raises, and that is a finding too
        broken = self.conn("owner")
        broken.close()
        result = audit_module.audit(broken, self.s, roles["owner"], roles["executor"], roles["loader"], roles["publisher"], as_kind="TEST")
        self.assertEqual(result.codes(), ("RW_AUDIT_NOT_INSPECTED",))
        with self.assertRaises(ValueError):
            audit_module.audit(self.admin, self.s, roles["owner"], roles["executor"], roles["loader"], roles["publisher"], as_kind="PRODUCTION")

    def test_the_deferrable_inventory_of_the_test_install_is_the_hand_written_one(self):
        self.assertEqual(set(audit_module.deferrable_inventory(self.admin, self.s)), DEFERRABLE)
        self.assertEqual(audit_module.EXPECTED_DEFERRABLE, DEFERRABLE)
        self.assertEqual(self.audit("TEST").inspected["deferrable"], tuple(sorted(DEFERRABLE)))


class CraftedRealFixtureTests(AuditCase):
    """E11 crafted: the REAL file list and the REAL role lists run by the kit's installer body in a disposable database, and the owner role writes
    the kind row. It is not a REAL database; it shows that the core installs without the TEST-only part and that the audit then reads as REAL."""
    INSTALL = "auditreal"
    KIND = "REAL"

    def test_the_core_alone_installs_and_passes_as_real(self):
        result = self.audit("REAL")
        self.assertEqual(result.findings, (), [f.short() for f in result.findings])
        self.assertNotIn("rw_check_fictional", result.inspected["gateway_functions"])
        self.assertEqual(result.inspected["install_rows"], ("REAL",))

    def test_the_same_catalog_read_as_test_reports_the_missing_part_and_the_kind_row(self):
        result = self.audit("TEST")
        self.assertEqual(self.codes_and_subjects(result) & {("RW_AUDIT_TEST_ONLY_MISSING", "rw_check_fictional")}, {("RW_AUDIT_TEST_ONLY_MISSING", "rw_check_fictional")})
        self.assertIn("RW_AUDIT_INSTALL_ROW", result.codes())

    def test_a_test_only_function_added_to_the_real_catalog_is_reported(self):
        """The crafted drift the audit exists for: someone runs the TEST-only file against a REAL database."""
        text = (Path(__file__).resolve().parents[2] / "src" / "persistence" / "real_workspace_fictional_v1.sql").read_text("utf8").replace("__RW_SCHEMA__", self.s)
        self.admin.execute(f'SET ROLE "{self.inst.roles["owner"]}"')
        try:
            self.admin.execute(text)
        finally:
            self.admin.execute("RESET ROLE")
        try:
            result = self.audit("REAL")
            self.assertIn(("RW_AUDIT_TEST_ONLY_PRESENT", "rw_check_fictional"), self.codes_and_subjects(result))
            # the function the owner creates later carries PostgreSQL's default PUBLIC EXECUTE, which the audit also reports
            self.assertEqual(result.codes(), ("RW_AUDIT_PRIVILEGE_DIFFERS", "RW_AUDIT_TEST_ONLY_PRESENT"))
        finally:
            self.admin.execute(f"DROP FUNCTION {self.s}.rw_check_fictional(jsonb,jsonb,jsonb,jsonb)")
        self.assertEqual(self.audit("REAL").findings, ())

    def test_the_deferrable_inventory_is_the_same_with_and_without_the_test_only_part(self):
        """Design 4.4 Step 2, item 2: the inventory of each branch, keyed (name, table, kind). The TEST-only part creates no constraint, so the
        real branch's inventory (this catalog, the core alone) equals the fictional branch's (the TEST catalog) and the difference is empty."""
        from real_gateway_kit import KIT
        test_inventory = set(audit_module.deferrable_inventory(self.admin, KIT.install("audit", w_seconds=4, kind="TEST").schema))
        real_inventory = set(audit_module.deferrable_inventory(self.admin, self.s))
        self.assertEqual(real_inventory, DEFERRABLE)
        self.assertEqual(test_inventory, real_inventory)
        self.assertEqual(test_inventory ^ real_inventory, set())


class DriftBase(AuditCase):
    def drift(self, apply, revert, expected, *, connection="admin", allow=(), check_revert=True):
        """Make one crafted drift, check the audit reports every `expected` (code, subject) pair and no code outside the expected codes and
        `allow` (a new object also gets PostgreSQL's default privileges, so some drifts bring a second kind of finding with them), revert,
        and check that the audit is clean again. `check_revert=False` is for a drift whose revert cannot restore the grants (an owner change)."""
        conn = self.admin
        self.assertEqual(self.audit("TEST").findings, (), "the control before the drift")
        for statement in apply:
            conn.execute(statement)
        try:
            result = self.audit("TEST")
            found = self.codes_and_subjects(result)
            for item in expected:
                self.assertIn(item, found, [f.short() for f in result.findings])
            self.assertLessEqual({code for code, _s in found}, {code for code, _s in expected} | set(allow), [f.short() for f in result.findings])
        finally:
            for statement in revert:
                conn.execute(statement)
        if check_revert:
            self.assertEqual(self.audit("TEST").findings, (), "the control after the revert")


class OwnsATableTests(DriftBase):
    """An ownership change is not undone by changing the owner back (PostgreSQL moves the ACL entries with it), so each ownership drift has an
    install of its own, which is not reused."""
    INSTALL = "auditown1"

    def test_the_executor_owning_a_table(self):
        s, r = self.s, self.inst.roles
        self.drift([f'ALTER TABLE {s}.account OWNER TO "{r["executor"]}"'], [f'ALTER TABLE {s}.account OWNER TO "{r["owner"]}"'],
                   [("RW_AUDIT_OWNS_OBJECT", "account")], allow=("RW_AUDIT_PRIVILEGE_DIFFERS",), check_revert=False)
        self.assertEqual(self.audit("TEST").codes(), ("RW_AUDIT_PRIVILEGE_DIFFERS",))          # the owner role ends up with the owner's rights; the lost grants show


class OwnsAFunctionTests(DriftBase):
    INSTALL = "auditown2"

    def test_the_executor_owning_a_function(self):
        s, r = self.s, self.inst.roles
        sig = f"{s}.rw_json(jsonb,integer)"
        self.drift([f'ALTER FUNCTION {sig} OWNER TO "{r["executor"]}"'], [f'ALTER FUNCTION {sig} OWNER TO "{r["owner"]}"'],
                   [("RW_AUDIT_OWNS_OBJECT", "rw_json")], allow=("RW_AUDIT_PRIVILEGE_DIFFERS",), check_revert=False)


class DriftTests(DriftBase):
    INSTALL = "auditdrift"

    # ---- privileges of each runtime role and of public --------------------------------------------------------------------------
    def test_the_executor_granted_a_publisher_function(self):
        s, r = self.s, self.inst.roles
        sig = f"{s}.rw_publish(bytea,jsonb,timestamptz,jsonb,text,text,text,text)"
        self.drift([f'GRANT EXECUTE ON FUNCTION {sig} TO "{r["executor"]}"'], [f'REVOKE EXECUTE ON FUNCTION {sig} FROM "{r["executor"]}"'],
                   [("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_publish")])

    def test_the_loader_granted_a_write_on_an_authority_table(self):
        s, r = self.s, self.inst.roles
        self.drift([f'GRANT INSERT, UPDATE ON {s}.rw_head TO "{r["loader"]}"'], [f'REVOKE INSERT, UPDATE ON {s}.rw_head FROM "{r["loader"]}"'],
                   [("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_head")])

    def test_the_loader_granted_a_select_on_app_user(self):
        """R2 review L-2: the reviewer's probe, a table that is not a gateway table and that the old loader catalog (rw*/md_* only) never looked at."""
        s, r = self.s, self.inst.roles
        self.drift([f'GRANT SELECT ON {s}.app_user TO "{r["loader"]}"'], [f'REVOKE SELECT ON {s}.app_user FROM "{r["loader"]}"'],
                   [("RW_AUDIT_PRIVILEGE_DIFFERS", "app_user")])

    def test_the_executor_granted_a_select_on_md_quote(self):
        s, r = self.s, self.inst.roles
        self.drift([f'GRANT SELECT ON {s}.md_quote TO "{r["executor"]}"'], [f'REVOKE SELECT ON {s}.md_quote FROM "{r["executor"]}"'],
                   [("RW_AUDIT_PRIVILEGE_DIFFERS", "md_quote")])

    def test_a_column_level_grant(self):
        s, r = self.s, self.inst.roles
        self.drift([f'GRANT SELECT (price) ON {s}.md_quote TO "{r["executor"]}"'],
                   [f'REVOKE SELECT (price) ON {s}.md_quote FROM "{r["executor"]}"'], [("RW_AUDIT_PRIVILEGE_DIFFERS", "md_quote")])
        # and a column grant on a gateway table the role's list does not name at all
        self.drift([f'GRANT SELECT (context_id) ON {s}.rw_head TO "{r["loader"]}"'], [f'REVOKE SELECT (context_id) ON {s}.rw_head FROM "{r["loader"]}"'],
                   [("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_head")])

    def test_maintain_on_the_drain_mark_table_for_the_loader_and_the_executor(self):
        if int(self.owner.execute("SHOW server_version_num").fetchone()[0]) < 170000:
            self.skipTest("MAINTAIN exists from PostgreSQL 17")
        s, r = self.s, self.inst.roles
        for who in ("loader", "executor", "publisher"):
            with self.subTest(who):
                self.drift([f'GRANT MAINTAIN ON {s}.rw_drain_mark TO "{r[who]}"'], [f'REVOKE MAINTAIN ON {s}.rw_drain_mark FROM "{r[who]}"'],
                           [("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_drain_mark")])

    def test_maintain_on_the_registry_tables_for_the_executor_and_the_publisher(self):
        """R2 review L-2: MAINTAIN (and any other privilege) on the `rwp_` tables, which the old catalog did not compare for these two roles."""
        if int(self.owner.execute("SHOW server_version_num").fetchone()[0]) < 170000:
            self.skipTest("MAINTAIN exists from PostgreSQL 17")
        s, r = self.s, self.inst.roles
        for who in ("executor", "publisher"):
            for table in ("rwp_payload", "rwp_context", "rwp_registration"):
                with self.subTest(who=who, table=table):
                    self.drift([f'GRANT MAINTAIN ON {s}.{table} TO "{r[who]}"'], [f'REVOKE MAINTAIN ON {s}.{table} FROM "{r[who]}"'],
                               [("RW_AUDIT_PRIVILEGE_DIFFERS", table)])

    def test_public_holding_execute_on_a_function(self):
        s = self.s
        for sig in (f"{s}.rw_publish(bytea,jsonb,timestamptz,jsonb,text,text,text,text)", f"{s}.rw_md_quote(text)",
                    f"{s}.ledger_event_before_insert()"):                  # a gateway function and a migration function (PostgreSQL's default is PUBLIC)
            with self.subTest(sig):
                name = sig.split(".")[1].split("(")[0]
                self.drift([f"GRANT EXECUTE ON FUNCTION {sig} TO PUBLIC"], [f"REVOKE EXECUTE ON FUNCTION {sig} FROM PUBLIC"],
                           [("RW_AUDIT_PRIVILEGE_DIFFERS", name)])

    def test_a_runtime_role_granted_a_privilege_on_a_sequence_or_the_schema(self):
        s, r = self.s, self.inst.roles
        self.drift([f'GRANT USAGE ON SEQUENCE {s}.web_portfolio_revision_seq_seq TO "{r["executor"]}"'],
                   [f'REVOKE USAGE ON SEQUENCE {s}.web_portfolio_revision_seq_seq FROM "{r["executor"]}"'],
                   [("RW_AUDIT_PRIVILEGE_DIFFERS", "web_portfolio_revision_seq_seq")])
        self.drift([f'GRANT CREATE ON SCHEMA {s} TO "{r["publisher"]}"'], [f'REVOKE CREATE ON SCHEMA {s} FROM "{r["publisher"]}"'],
                   [("RW_AUDIT_PRIVILEGE_DIFFERS", "schema " + s)])
        self.drift([f"GRANT USAGE ON SCHEMA {s} TO PUBLIC"], [f"REVOKE USAGE ON SCHEMA {s} FROM PUBLIC"], [("RW_AUDIT_PRIVILEGE_DIFFERS", "schema " + s)])

    def test_a_grant_option_held_by_a_runtime_role(self):
        s, r = self.s, self.inst.roles
        self.drift([f'GRANT SELECT ON {s}.portfolio TO "{r["executor"]}" WITH GRANT OPTION'],
                   [f'REVOKE GRANT OPTION FOR SELECT ON {s}.portfolio FROM "{r["executor"]}"'], [("RW_AUDIT_GRANT_OPTION", "portfolio")])

    def test_a_runtime_role_missing_a_privilege_its_list_names(self):
        s, r = self.s, self.inst.roles
        self.drift([f'REVOKE INSERT ON {s}.account FROM "{r["executor"]}"'], [f'GRANT INSERT ON {s}.account TO "{r["executor"]}"'],
                   [("RW_AUDIT_PRIVILEGE_DIFFERS", "account")])
        self.drift([f'REVOKE EXECUTE ON FUNCTION {s}.rw_md_quote(text) FROM "{r["executor"]}"'], [f'GRANT EXECUTE ON FUNCTION {s}.rw_md_quote(text) TO "{r["executor"]}"'],
                   [("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_md_quote")])

    # ---- the controls on the objects ---------------------------------------------------------------------------------------------
    def test_a_barrier_switched_off_or_removed(self):
        s = self.s
        cases = (
            ([f"ALTER TABLE {s}.portfolio DISABLE TRIGGER zz_rw_write"], [f"ALTER TABLE {s}.portfolio ENABLE TRIGGER zz_rw_write"], "portfolio"),
            ([f"ALTER TABLE {s}.account DISABLE TRIGGER zz_rw_journal"], [f"ALTER TABLE {s}.account ENABLE TRIGGER zz_rw_journal"], "account"),
            ([f"ALTER TABLE {s}.ledger_event DISABLE TRIGGER zz_rw_truncate"], [f"ALTER TABLE {s}.ledger_event ENABLE TRIGGER zz_rw_truncate"], "ledger_event"),
            ([f"ALTER TABLE {s}.rw_root DISABLE ROW LEVEL SECURITY"], [f"ALTER TABLE {s}.rw_root ENABLE ROW LEVEL SECURITY"], "rw_root"),
            ([f"ALTER TABLE {s}.benchmark_selection DISABLE ROW LEVEL SECURITY"], [f"ALTER TABLE {s}.benchmark_selection ENABLE ROW LEVEL SECURITY"], "benchmark_selection"),
            ([f"ALTER TABLE {s}.rw_artifact DISABLE TRIGGER rw_immutable"], [f"ALTER TABLE {s}.rw_artifact ENABLE TRIGGER rw_immutable"], "rw_artifact"),
            ([f"ALTER TABLE {s}.rw_lease DISABLE TRIGGER rw_bundle_complete"], [f"ALTER TABLE {s}.rw_lease ENABLE TRIGGER rw_bundle_complete"], "rw_lease"),
            ([f"ALTER TABLE {s}.rw_lease DISABLE TRIGGER rw_lease_deadline_guard"], [f"ALTER TABLE {s}.rw_lease ENABLE TRIGGER rw_lease_deadline_guard"], "rw_lease"),
        )
        for apply, revert, subject in cases:
            with self.subTest(apply[0]):
                self.drift(apply, revert, [("RW_AUDIT_CONTROL_MISSING", subject)])

    def test_the_restrictive_row_policy_dropped_or_made_permissive(self):
        s, r = self.s, self.inst.roles
        guard = (f'CREATE POLICY rw_row_guard ON {s}.portfolio AS RESTRICTIVE FOR ALL TO "{r["executor"]}" '
                 f"USING ({s}.rw_row_allowed('portfolio',to_jsonb(portfolio),false)) WITH CHECK ({s}.rw_row_allowed('portfolio',to_jsonb(portfolio),true))")
        self.drift([f"DROP POLICY rw_row_guard ON {s}.portfolio"], [guard], [("RW_AUDIT_CONTROL_MISSING", "portfolio")])
        self.drift([f"DROP POLICY rw_row_guard ON {s}.portfolio",
                    f'CREATE POLICY rw_row_guard ON {s}.portfolio AS PERMISSIVE FOR ALL TO "{r["executor"]}" USING (true) WITH CHECK (true)'],
                   [f"DROP POLICY rw_row_guard ON {s}.portfolio", guard], [("RW_AUDIT_CONTROL_DIFFERS", "portfolio")])        # exists, but permissive and true

    # ---- the technical review's blind spots (L-1): definitions, not existence --------------------------------------------------------
    def test_a_procedure_with_public_execute(self):
        """L-1: a PROCEDURE carries PostgreSQL's default PUBLIC EXECUTE like a function does, and the privilege comparison covers every kind of
        routine. A procedure whose EXECUTE is revoked from PUBLIC is clean (the control)."""
        s, r = self.s, self.inst.roles
        create = [f'SET ROLE "{r["owner"]}"', f"CREATE PROCEDURE {s}.helper_proc() LANGUAGE sql AS 'SELECT 1'", "RESET ROLE"]
        self.drift(create, [f"DROP PROCEDURE {s}.helper_proc()"], [("RW_AUDIT_PRIVILEGE_DIFFERS", "helper_proc")])
        self.drift(create + [f"REVOKE EXECUTE ON PROCEDURE {s}.helper_proc() FROM PUBLIC"], [f"DROP PROCEDURE {s}.helper_proc()"], [])

    def policy_drifts(self):
        s, r = self.s, self.inst.roles
        executor = f'"{r["executor"]}"'
        guard = (f"CREATE POLICY rw_row_guard ON {s}.portfolio AS RESTRICTIVE FOR ALL TO {executor} "
                 f"USING ({s}.rw_row_allowed('portfolio',to_jsonb(portfolio),false)) WITH CHECK ({s}.rw_row_allowed('portfolio',to_jsonb(portfolio),true))")
        baseline = f"CREATE POLICY rw_baseline ON {s}.portfolio AS PERMISSIVE FOR ALL TO {executor} USING (true) WITH CHECK (true)"
        drop = lambda name: f"DROP POLICY {name} ON {s}.portfolio"            # noqa: E731
        restore = [drop("rw_row_guard"), guard]
        return {
            "the guard's USING is true": ([f"ALTER POLICY rw_row_guard ON {s}.portfolio USING (true)"], restore),
            "the guard's WITH CHECK is true": ([f"ALTER POLICY rw_row_guard ON {s}.portfolio WITH CHECK (true)"], restore),
            "the guard checks another table's name": (
                [f"ALTER POLICY rw_row_guard ON {s}.portfolio USING ({s}.rw_row_allowed('account',to_jsonb(portfolio),false))"], restore),
            "the guard is for SELECT alone": (
                [drop("rw_row_guard"), f"CREATE POLICY rw_row_guard ON {s}.portfolio AS RESTRICTIVE FOR SELECT TO {executor} "
                                       f"USING ({s}.rw_row_allowed('portfolio',to_jsonb(portfolio),false))"], restore),
            "the guard is for public, not the executor": ([f"ALTER POLICY rw_row_guard ON {s}.portfolio TO PUBLIC"], restore),
            "the guard is for the loader, not the executor": ([f'ALTER POLICY rw_row_guard ON {s}.portfolio TO "{r["loader"]}"'], restore),
            "the baseline is USING (false)": ([f"ALTER POLICY rw_baseline ON {s}.portfolio USING (false)"], [drop("rw_baseline"), baseline]),
            "a further permissive policy": ([f"CREATE POLICY rw_extra ON {s}.portfolio AS PERMISSIVE FOR ALL TO PUBLIC USING (true)"], [drop("rw_extra")]),
        }

    def test_a_row_policy_whose_definition_differs_is_reported_though_it_exists(self):
        """L-1: the policy has the right NAME and the right permissive/restrictive kind, and a different command, role list or expression. The
        control is the clean audit before and after each. A further policy is a different finding (the set of policies is not the two)."""
        for label, (apply, revert) in self.policy_drifts().items():
            with self.subTest(label):
                code = "RW_AUDIT_CONTROL_MISSING" if label == "a further permissive policy" else "RW_AUDIT_CONTROL_DIFFERS"
                self.drift(apply, revert, [(code, "portfolio")])

    def test_a_trigger_that_runs_another_function_or_has_another_type_is_reported_though_it_is_enabled(self):
        """L-1: `tgfoid` and `tgtype` are compared, not only the name and the enabled flag."""
        s = self.s

        def replace(table, name, create):
            return [f"DROP TRIGGER {name} ON {s}.{table}", create], [f"DROP TRIGGER {name} ON {s}.{table}", create_original[(table, name)]]
        create_original = {
            ("portfolio", "zz_rw_write"): f"CREATE TRIGGER zz_rw_write BEFORE INSERT OR UPDATE OR DELETE ON {s}.portfolio FOR EACH ROW EXECUTE FUNCTION {s}.rw_write_fence()",
            ("account", "zz_rw_journal"): f"CREATE TRIGGER zz_rw_journal AFTER INSERT OR UPDATE OR DELETE ON {s}.account FOR EACH ROW EXECUTE FUNCTION {s}.rw_journal_after()",
            ("ledger_event", "zz_rw_truncate"): f"CREATE TRIGGER zz_rw_truncate BEFORE TRUNCATE ON {s}.ledger_event FOR EACH STATEMENT EXECUTE FUNCTION {s}.rw_write_fence()",
            ("rw_artifact", "rw_immutable"): f"CREATE TRIGGER rw_immutable BEFORE UPDATE OR DELETE ON {s}.rw_artifact FOR EACH ROW EXECUTE FUNCTION {s}.rw_no_mutation()",
            ("rw_lease", "rw_bundle_complete"): f"CREATE CONSTRAINT TRIGGER rw_bundle_complete AFTER INSERT ON {s}.rw_lease DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.rw_bundle_guard()",
            ("rw_lease", "rw_lease_deadline_guard"): f"CREATE CONSTRAINT TRIGGER rw_lease_deadline_guard AFTER INSERT ON {s}.rw_lease DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.rw_deadline_check()",
        }
        cases = (
            ("the fence fires on INSERT and UPDATE only", "portfolio", "zz_rw_write",
             f"CREATE TRIGGER zz_rw_write BEFORE INSERT OR UPDATE ON {s}.portfolio FOR EACH ROW EXECUTE FUNCTION {s}.rw_write_fence()"),
            ("the fence runs the journal's function (same type)", "portfolio", "zz_rw_write",
             f"CREATE TRIGGER zz_rw_write BEFORE INSERT OR UPDATE OR DELETE ON {s}.portfolio FOR EACH ROW EXECUTE FUNCTION {s}.rw_journal_after()"),
            ("the journal fires once per statement", "account", "zz_rw_journal",
             f"CREATE TRIGGER zz_rw_journal AFTER INSERT OR UPDATE OR DELETE ON {s}.account FOR EACH STATEMENT EXECUTE FUNCTION {s}.rw_journal_after()"),
            ("the truncate trigger runs AFTER", "ledger_event", "zz_rw_truncate",
             f"CREATE TRIGGER zz_rw_truncate AFTER TRUNCATE ON {s}.ledger_event FOR EACH STATEMENT EXECUTE FUNCTION {s}.rw_write_fence()"),
            ("the immutability trigger watches UPDATE alone", "rw_artifact", "rw_immutable",
             f"CREATE TRIGGER rw_immutable BEFORE UPDATE ON {s}.rw_artifact FOR EACH ROW EXECUTE FUNCTION {s}.rw_no_mutation()"),
            ("the bundle guard is IMMEDIATE", "rw_lease", "rw_bundle_complete",
             f"CREATE CONSTRAINT TRIGGER rw_bundle_complete AFTER INSERT ON {s}.rw_lease DEFERRABLE INITIALLY IMMEDIATE FOR EACH ROW EXECUTE FUNCTION {s}.rw_bundle_guard()"),
            ("the bundle guard runs the deadline function", "rw_lease", "rw_bundle_complete",
             f"CREATE CONSTRAINT TRIGGER rw_bundle_complete AFTER INSERT ON {s}.rw_lease DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.rw_deadline_check()"),
            ("the deadline guard runs the bundle function", "rw_lease", "rw_lease_deadline_guard",
             f"CREATE CONSTRAINT TRIGGER rw_lease_deadline_guard AFTER INSERT ON {s}.rw_lease DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.rw_bundle_guard()"),
        )
        for label, table, name, create in cases:
            with self.subTest(label):
                apply, revert = replace(table, name, create)
                self.drift(apply, revert, [("RW_AUDIT_CONTROL_DIFFERS", table)])

    def test_a_runtime_role_that_is_a_member_of_another_role_or_has_a_member_who_can_set_it(self):
        """L-1: the reviewer's case, a membership FROM a runtime role with SET TRUE (the runtime roles are NOINHERIT, so no privilege is inherited
        and `has_*_privilege` does not see it; `SET ROLE` does). Also SET FALSE (still a membership of a runtime role), a role that can SET the
        runtime role, and, as the control that the audit is not over-eager, a member holding ADMIN OPTION alone."""
        r = self.inst.roles
        q = {k: f'"{v}"' for k, v in r.items()}
        cases = (
            ("the executor is a member of the publisher with SET TRUE", f"GRANT {q['publisher']} TO {q['executor']} WITH SET TRUE, INHERIT FALSE",
             f"REVOKE {q['publisher']} FROM {q['executor']}", [("RW_AUDIT_MEMBERSHIP", r["executor"])]),
            ("the loader is a member of the owner with SET TRUE", f"GRANT {q['owner']} TO {q['loader']} WITH SET TRUE, INHERIT FALSE",
             f"REVOKE {q['owner']} FROM {q['loader']}", [("RW_AUDIT_MEMBERSHIP", r["loader"])]),
            ("the publisher is a member of the loader with SET FALSE", f"GRANT {q['loader']} TO {q['publisher']} WITH SET FALSE, INHERIT FALSE",
             f"REVOKE {q['loader']} FROM {q['publisher']}", [("RW_AUDIT_MEMBERSHIP", r["publisher"])]),
            ("the loader can SET the executor", f"GRANT {q['executor']} TO {q['loader']} WITH SET TRUE, INHERIT FALSE",
             f"REVOKE {q['executor']} FROM {q['loader']}", [("RW_AUDIT_MEMBERSHIP", r["loader"])]),
        )
        for label, grant, revoke, expected in cases:
            with self.subTest(label):
                self.drift([grant], [revoke], expected)

    def test_a_role_outside_the_install_that_can_set_a_runtime_role_is_reported_and_one_with_admin_option_alone_is_not(self):
        """L-1: the other side of a membership. A role of the cluster outside this install that may `SET ROLE` to a runtime role is reported on
        the runtime role; the same role holding ADMIN OPTION alone (SET and INHERIT false) is not (the control that the check is not
        over-eager; the escalation through ADMIN OPTION is the preflight's, design 5.3 (a), (b)). The role is dropped in `finally`."""
        r = self.inst.roles
        outsider = "%s_outsider" % r["owner"]
        self.admin.execute(f'CREATE ROLE "{outsider}" NOLOGIN')
        try:
            self.drift([f'GRANT "{r["publisher"]}" TO "{outsider}" WITH ADMIN TRUE, SET FALSE, INHERIT FALSE'], [f'REVOKE "{r["publisher"]}" FROM "{outsider}"'], [])
            self.drift([f'GRANT "{r["publisher"]}" TO "{outsider}" WITH SET TRUE, INHERIT FALSE'], [f'REVOKE "{r["publisher"]}" FROM "{outsider}"'],
                       [("RW_AUDIT_MEMBERSHIP", r["publisher"])])
            self.drift([f'GRANT "{r["publisher"]}" TO "{outsider}" WITH SET FALSE, INHERIT TRUE'], [f'REVOKE "{r["publisher"]}" FROM "{outsider}"'],
                       [("RW_AUDIT_MEMBERSHIP", r["publisher"])])
        finally:
            self.admin.execute(f'DROP ROLE "{outsider}"')

    def test_a_second_constraint_with_a_guard_name_or_an_unknown_deferrable_constraint(self):
        s = self.s
        self.drift([f"ALTER TABLE {s}.app_user ADD CONSTRAINT rw_bundle_complete CHECK (true)"],
                   [f"ALTER TABLE {s}.app_user DROP CONSTRAINT rw_bundle_complete"], [("RW_AUDIT_GUARD_NAME", "rw_bundle_complete")])
        self.drift([f"ALTER TABLE {s}.app_user ADD CONSTRAINT app_user_deferred_key UNIQUE (user_id) DEFERRABLE INITIALLY DEFERRED"],
                   [f"ALTER TABLE {s}.app_user DROP CONSTRAINT app_user_deferred_key"], [("RW_AUDIT_DEFERRABLE_INVENTORY", "app_user_deferred_key")])

    def test_a_function_the_files_do_not_create_or_one_without_a_pinned_search_path(self):
        s, r = self.s, self.inst.roles
        self.drift([f'SET ROLE "{r["owner"]}"', f"CREATE FUNCTION {s}.rw_extra() RETURNS int LANGUAGE sql AS 'SELECT 1'", "RESET ROLE"],
                   [f"DROP FUNCTION {s}.rw_extra()"], [("RW_AUDIT_FUNCTION_SET", "rw_extra")],
                   allow=("RW_AUDIT_PRIVILEGE_DIFFERS",))              # a new function carries PostgreSQL's default PUBLIC EXECUTE
        self.drift([f'SET ROLE "{r["owner"]}"',
                    f"CREATE FUNCTION {s}.rw_hostile() RETURNS int LANGUAGE sql SECURITY DEFINER AS 'SELECT 1'", "RESET ROLE"],
                   [f"DROP FUNCTION {s}.rw_hostile()"], [("RW_AUDIT_FUNCTION_SET", "rw_hostile"), ("RW_AUDIT_SEARCH_PATH", "rw_hostile")],
                   allow=("RW_AUDIT_PRIVILEGE_DIFFERS",))

    def test_an_md_table_without_a_read_function(self):
        s, r = self.s, self.inst.roles
        self.drift([f'SET ROLE "{r["owner"]}"', f"CREATE TABLE {s}.md_extra (release_id text)", "RESET ROLE"], [f"DROP TABLE {s}.md_extra"],
                   [("RW_AUDIT_MD_FUNCTIONS", "rw_md_*")])

    def test_the_install_row_of_another_kind(self):
        """Read as REAL, a TEST install's row is a finding (and so is the TEST-only part); read as TEST, a REAL row would be."""
        result = self.audit("REAL")
        self.assertIn(("RW_AUDIT_INSTALL_ROW", "rw_install"), self.codes_and_subjects(result))


class DefinitionDriftTests(DriftBase):
    """E11 crafted drifts (re-review RR-L2): function bodies and properties compared with the installer's SQL files, and the FULL trigger set of
    the fenced, gateway and md_* tables. Every drift is made by the administrative role of a disposable database and reverted; the control
    before and after each is a clean audit (`DriftBase.drift`). The reviewer's three cases are `rw_row_allowed` -> `SELECT true`, a pass-through
    `rw_write_fence` and a `zzz_probe` BEFORE trigger on `portfolio`: each left the old audit empty."""
    INSTALL = "auditdef"

    def definition_of(self, name):
        return self.admin.execute(
            "SELECT pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND p.proname=%s",
            (self.s, name)).fetchone()[0]

    def with_body(self, name, body):
        """The function's own `CREATE OR REPLACE` text with another body: same name, signature, owner, grants, language, security and settings."""
        import re
        text = self.definition_of(name)
        return re.sub(r"(\$function\$).*(\$function\$)", lambda m: m.group(1) + body + m.group(2), text, flags=re.S)

    def test_every_gateway_function_has_a_definition_digest_in_the_report(self):
        result = self.audit("TEST")
        digests = dict(result.inspected["function_digests"])
        self.assertEqual(set(digests), set(result.inspected["gateway_functions"]))
        self.assertGreater(len(digests), 60)
        self.assertTrue(all(len(d) == 64 for d in digests.values()))

    def test_a_function_whose_body_was_replaced_is_reported_though_its_name_oid_and_grants_are_unchanged(self):
        """The reviewer's two body cases, and a comment-only change (the body is compared byte for byte)."""
        cases = (
            ("rw_row_allowed is SELECT true", "rw_row_allowed", "BEGIN RETURN true; END"),
            ("rw_write_fence is a pass-through", "rw_write_fence", "BEGIN IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW; END"),
            ("rw_check_real accepts everything", "rw_check_real", "BEGIN RETURN '{}'::text[]; END"),
            ("rw_journal_after writes nothing", "rw_journal_after", "BEGIN RETURN NULL; END"),
            ("a comment is added to rw_deadline_check", "rw_deadline_check", None),
        )
        for label, name, body in cases:
            with self.subTest(label):
                original = self.definition_of(name)
                changed = self.with_body(name, body) if body is not None else original.replace("$function$\n", "$function$\n-- edited\n", 1)
                self.assertNotEqual(changed, original)
                self.drift([changed], [original], [("RW_AUDIT_FUNCTION_DEFINITION", name)])

    def test_a_function_whose_property_changed_is_reported(self):
        """SECURITY DEFINER dropped, the function settings changed (a schema ahead of pg_temp that the old test, which only looked at the last
        entry, accepted), volatility, STRICT, LEAKPROOF and PARALLEL; each is reverted with the opposite statement."""
        s = self.s
        sig = {"rw_row_allowed": f"{s}.rw_row_allowed(text,jsonb,boolean)", "rw_check_real": f"{s}.rw_check_real(jsonb,jsonb,jsonb,jsonb)",
               "rw_json": f"{s}.rw_json(jsonb,integer)"}
        cases = (
            ("SECURITY INVOKER", f"ALTER FUNCTION {sig['rw_row_allowed']} SECURITY INVOKER", f"ALTER FUNCTION {sig['rw_row_allowed']} SECURITY DEFINER", "rw_row_allowed"),
            ("search_path with public before pg_temp", f"ALTER FUNCTION {sig['rw_row_allowed']} SET search_path = pg_catalog, public, {s}, pg_temp",
             f"ALTER FUNCTION {sig['rw_row_allowed']} SET search_path = pg_catalog, {s}, pg_temp", "rw_row_allowed"),
            ("a further function setting", f"ALTER FUNCTION {sig['rw_row_allowed']} SET work_mem = '64MB'", f"ALTER FUNCTION {sig['rw_row_allowed']} RESET work_mem", "rw_row_allowed"),
            ("VOLATILE for STABLE", f"ALTER FUNCTION {sig['rw_check_real']} VOLATILE", f"ALTER FUNCTION {sig['rw_check_real']} STABLE", "rw_check_real"),
            ("STRICT", f"ALTER FUNCTION {sig['rw_check_real']} STRICT", f"ALTER FUNCTION {sig['rw_check_real']} CALLED ON NULL INPUT", "rw_check_real"),
            ("LEAKPROOF", f"ALTER FUNCTION {sig['rw_json']} LEAKPROOF", f"ALTER FUNCTION {sig['rw_json']} NOT LEAKPROOF", "rw_json"),
            ("PARALLEL SAFE", f"ALTER FUNCTION {sig['rw_row_allowed']} PARALLEL SAFE", f"ALTER FUNCTION {sig['rw_row_allowed']} PARALLEL UNSAFE", "rw_row_allowed"),
        )
        for label, apply, revert, name in cases:
            with self.subTest(label):
                allow = ("RW_AUDIT_SEARCH_PATH",) if label.startswith("search_path") else ()
                self.drift([apply], [revert], [("RW_AUDIT_FUNCTION_DEFINITION", name)], allow=allow + (("RW_AUDIT_SEARCH_PATH",) if label == "SECURITY INVOKER" else ()))

    def probe_function(self):
        """A trigger function that is not a gateway function (its name is not rw_), with PUBLIC revoked so that no privilege comparison sees it."""
        s, r = self.s, self.inst.roles
        return ([f'SET ROLE "{r["owner"]}"', f"CREATE FUNCTION {s}.zzz_probe_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$",
                 f"REVOKE EXECUTE ON FUNCTION {s}.zzz_probe_fn() FROM PUBLIC", "RESET ROLE"],
                [f"DROP FUNCTION {s}.zzz_probe_fn()"])

    def test_a_trigger_the_table_does_not_expect_is_reported_whatever_function_it_runs(self):
        """The reviewer's `zzz_probe` (BEFORE INSERT, fires after the fence, runs a function that is not rw_*) on a fenced table, and the same on a
        gateway table, an md_* table and a migration-trigger table; an AFTER trigger too."""
        s = self.s
        create_fn, drop_fn = self.probe_function()
        cases = (
            ("BEFORE INSERT on portfolio", "portfolio", f"CREATE TRIGGER zzz_probe BEFORE INSERT ON {s}.portfolio FOR EACH ROW EXECUTE FUNCTION {s}.zzz_probe_fn()"),
            ("BEFORE INSERT on ledger_event", "ledger_event", f"CREATE TRIGGER zzz_probe BEFORE INSERT ON {s}.ledger_event FOR EACH ROW EXECUTE FUNCTION {s}.zzz_probe_fn()"),
            ("AFTER UPDATE on account", "account", f"CREATE TRIGGER zzz_probe AFTER UPDATE ON {s}.account FOR EACH ROW EXECUTE FUNCTION {s}.zzz_probe_fn()"),
            ("BEFORE INSERT on rw_root_link", "rw_root_link", f"CREATE TRIGGER zzz_probe BEFORE INSERT ON {s}.rw_root_link FOR EACH ROW EXECUTE FUNCTION {s}.zzz_probe_fn()"),
            ("BEFORE INSERT on rw_lease", "rw_lease", f"CREATE TRIGGER zzz_probe BEFORE INSERT ON {s}.rw_lease FOR EACH ROW EXECUTE FUNCTION {s}.zzz_probe_fn()"),
            ("BEFORE INSERT on rwp_payload", "rwp_payload", f"CREATE TRIGGER zzz_probe BEFORE INSERT ON {s}.rwp_payload FOR EACH ROW EXECUTE FUNCTION {s}.zzz_probe_fn()"),
            ("BEFORE INSERT on md_quote", "md_quote", f"CREATE TRIGGER zzz_probe BEFORE INSERT ON {s}.md_quote FOR EACH ROW EXECUTE FUNCTION {s}.zzz_probe_fn()"),
            ("BEFORE INSERT on md_file", "md_file", f"CREATE TRIGGER zzz_probe BEFORE INSERT ON {s}.md_file FOR EACH ROW EXECUTE FUNCTION {s}.zzz_probe_fn()"),
            ("a trigger that is disabled", "portfolio", None),
        )
        for label, table, create in cases:
            with self.subTest(label):
                if create is None:
                    create_trigger = [f"CREATE TRIGGER zzz_probe BEFORE INSERT ON {s}.{table} FOR EACH ROW EXECUTE FUNCTION {s}.zzz_probe_fn()",
                                      f"ALTER TABLE {s}.{table} DISABLE TRIGGER zzz_probe"]
                else:
                    create_trigger = [create]
                self.drift(create_fn + create_trigger, [f"DROP TRIGGER zzz_probe ON {s}.{table}"] + drop_fn, [("RW_AUDIT_CONTROL_DIFFERS", table)])

    def test_a_migration_or_md_trigger_that_was_disabled_replaced_or_retyped_is_reported(self):
        """The triggers the migrations put on the fenced tables and on the md_* tables, and the gateway's own on the tables the old comparison did
        not cover (rw_install, rw_snapshot, rw_history, rw_drain_mark, rw_root_link, rw_head, rw_mode, rwp_*), are in the expected set."""
        s = self.s
        create_fn, drop_fn = self.probe_function()
        disable = lambda t, n: ([f"ALTER TABLE {s}.{t} DISABLE TRIGGER {n}"], [f"ALTER TABLE {s}.{t} ENABLE TRIGGER {n}"])      # noqa: E731
        for table, name in (("ledger_event", "ledger_event_before_insert"), ("ledger_event", "ledger_event_transfer_pairing"),
                            ("account", "account_identity_immutable"), ("benchmark_selection", "benchmark_selection_no_update_delete"),
                            ("md_quote", "md_quote_open_release"), ("md_release", "md_release_stamp_xid"), ("md_file", "md_file_no_update_delete"),
                            ("rw_install", "rw_immutable"), ("rw_snapshot", "rw_no_truncate"), ("rw_history", "rw_history_guard_write"),
                            ("rw_head", "rw_head_guard_write"), ("rw_lease", "rw_lease_guard_write"), ("rw_mode", "rw_mode_no_delete"),
                            ("rwp_payload", "rwp_payload_immutable_rows")):
            with self.subTest("disabled: %s.%s" % (table, name)):
                apply, revert = disable(table, name)
                self.drift(apply, revert, [("RW_AUDIT_CONTROL_MISSING", table)])
        with self.subTest("enabled for replica sessions only"):
            self.drift([f"ALTER TABLE {s}.ledger_event ENABLE REPLICA TRIGGER ledger_event_before_insert"],
                       [f"ALTER TABLE {s}.ledger_event ENABLE TRIGGER ledger_event_before_insert"], [("RW_AUDIT_CONTROL_MISSING", "ledger_event")])
        with self.subTest("a migration trigger that runs another function"):
            original = f"CREATE TRIGGER ledger_event_before_insert BEFORE INSERT ON {s}.ledger_event FOR EACH ROW EXECUTE FUNCTION {s}.ledger_event_before_insert()"
            self.drift(create_fn + [f"DROP TRIGGER ledger_event_before_insert ON {s}.ledger_event",
                                    f"CREATE TRIGGER ledger_event_before_insert BEFORE INSERT ON {s}.ledger_event FOR EACH ROW EXECUTE FUNCTION {s}.zzz_probe_fn()"],
                       [f"DROP TRIGGER ledger_event_before_insert ON {s}.ledger_event", original] + drop_fn, [("RW_AUDIT_CONTROL_DIFFERS", "ledger_event")])
        with self.subTest("an md trigger of another type"):
            original = f"CREATE TRIGGER md_quote_open_release BEFORE INSERT ON {s}.md_quote FOR EACH ROW EXECUTE FUNCTION {s}.md_require_open_release()"
            self.drift([f"DROP TRIGGER md_quote_open_release ON {s}.md_quote",
                        f"CREATE TRIGGER md_quote_open_release BEFORE INSERT OR UPDATE ON {s}.md_quote FOR EACH ROW EXECUTE FUNCTION {s}.md_require_open_release()"],
                       [f"DROP TRIGGER md_quote_open_release ON {s}.md_quote", original], [("RW_AUDIT_CONTROL_DIFFERS", "md_quote")])

    def test_the_expected_trigger_sets_are_the_catalog_of_a_clean_install(self):
        """The hand-written table is exactly what a clean TEST install holds on the tables the audit reads (nothing expected is missing and
        nothing present is unexpected), and the report names the tables."""
        result = self.audit("TEST")
        self.assertEqual(result.findings, ())
        tables = set(result.inspected["trigger_tables"])
        self.assertEqual({t for t in audit_module.EXPECTED_TRIGGERS}, tables)
        found = {}
        for table, name, tgtype, function, constraint in self.admin.execute(
                "SELECT c.relname::text,t.tgname::text,t.tgtype::int,p.proname::text,t.tgconstraint<>0 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname=%s AND NOT t.tgisinternal", (self.s,)).fetchall():
            if table in tables:
                found.setdefault(table, {})[name] = (tgtype, function, constraint)
        self.assertEqual(found, {t: dict(v) for t, v in audit_module.EXPECTED_TRIGGERS.items()})


if __name__ == "__main__":
    import unittest
    unittest.main()
