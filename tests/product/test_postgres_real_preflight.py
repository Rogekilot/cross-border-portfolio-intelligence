"""F1 R6, PostgreSQL (disposable databases on the development cluster, TEST installs only): what the preflight and the real installer's parts can be
shown to do against a SERVER, and what they cannot.

WHAT THE DEVELOPMENT CLUSTER CAN SHOW (design 1.2 rule 7, technical TR3-L2). It trusts its roles over the socket by design, so the probe's
`CONNECTED` outcome is the one it produces: these tests show the REFUSAL SIDE ONLY. No attempt here is `CHALLENGED` or `REJECTED`, so those two
classes are NOT calibrated here (the opt-in `test_preflight_calibration` does that, in the owner's cloud environment). The accepting side of the installer
and of the runtime gate, and the first read of a REAL catalog, are first exercised at R8 step 1.

Nothing here creates a database in the reserved namespace or runs the real installer's Phase 1 against a cluster; `install_in_database` is run on the
kit's disposable TEST-named database, with that install's own names (E11: the REAL file list and REAL lists in a database that holds no real content).
Crafted drift is made by the administrative role of the disposable database, inside a transaction that is rolled back.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from unittest import mock

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402

import real_gateway_fixtures as fx  # noqa: E402
from persistence import real_catalog_audit as audit_module, real_install, real_preflight as pf, real_roles, real_workspace_store as store  # noqa: E402
from real_gateway_kit import GatewayCase, KIT, setUpModule, tearDownModule  # noqa: E402,F401

SOCKET = os.environ.get("FINWEB_PG_SOCKET", "")
GUARDS = ("md_require_open_release", "md_release_stamp", "ledger_event_before_insert", "ledger_event_check_transfer_pairing",
          "benchmark_selection_before_insert")


class Pg(GatewayCase):
    ACCOUNT = True              # PD-0078: every install of this module has the fifth role, made and granted by the product installer

    def names(self):
        r = self.inst.roles
        return real_install.InstallNames(KIT.prov.db, self.s, r["owner"], r["executor"], r["loader"], r["publisher"], r["account"])

    def real_roles_of_install(self):
        r = self.inst.roles
        return {"owner": r["owner"], "executor": r["executor"], "loader": r["loader"], "publisher": r["publisher"], "account": r["account"]}

    def audit_in_transaction(self, replacement_sql, *, as_kind="TEST"):
        """Run `replacement_sql` as the administrative role inside a transaction, audit on the same session, ROLL BACK. E11: crafted, reverted."""
        r = self.inst.roles
        conn = self.inst.connect("admin")
        self.addCleanup(self._close, conn)
        conn.execute("BEGIN")
        try:
            for statement in replacement_sql:
                conn.execute(statement)
            return audit_module.audit(conn, self.s, r["owner"], r["executor"], r["loader"], r["publisher"], as_kind=as_kind, account_role=r["account"])
        finally:
            conn.execute("ROLLBACK")


class GuardDefinitionTests(Pg):
    """FR-L1 (b): the audit compares the five INSERT-path guard functions by definition (Python only; no gateway SQL)."""
    INSTALL = "preflight_guards"

    HOLLOW = 'CREATE OR REPLACE FUNCTION "{s}".{f}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$'

    def test_a_clean_install_has_no_guard_finding_and_the_five_digests_are_reported(self):
        r = self.inst.roles
        result = audit_module.audit(self.admin, self.s, r["owner"], r["executor"], r["loader"], r["publisher"], as_kind="TEST")
        self.assertEqual([f for f in result.findings if f.code == "RW_AUDIT_GUARD_DEFINITION"], [])
        self.assertEqual(tuple(name for name, _digest in result.inspected["guard_digests"]), tuple(sorted(GUARDS)))

    def test_a_hollowed_guard_is_seen_for_each_of_the_five(self):
        for name in GUARDS:
            result = self.audit_in_transaction([self.HOLLOW.format(s=self.s, f=name)])
            found = [f for f in result.findings if f.code == "RW_AUDIT_GUARD_DEFINITION"]
            self.assertEqual([f.subject for f in found], [name], name)
            self.assertIn("prosrc", found[0].detail, name)
        self.test_a_clean_install_has_no_guard_finding_and_the_five_digests_are_reported()       # the control after each: reverted

    def test_a_changed_body_with_the_schema_pin_restored_is_seen_by_the_body_alone(self):
        name = "md_release_stamp"
        result = self.audit_in_transaction([self.HOLLOW.format(s=self.s, f=name),
                                            'ALTER FUNCTION "%s".%s() SET search_path = "%s", pg_temp' % (self.s, name, self.s)])
        found = [f for f in result.findings if f.code == "RW_AUDIT_GUARD_DEFINITION"]
        self.assertEqual(len(found), 1)
        self.assertIn("prosrc", found[0].detail)
        self.assertNotIn("settings", found[0].detail)

    def test_a_guard_whose_pin_was_dropped_is_seen_by_its_settings(self):
        name = "ledger_event_before_insert"
        real_body = self.owner.execute("SELECT prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND p.proname=%s",
                                       (self.s, name)).fetchone()[0]
        result = self.audit_in_transaction(['ALTER FUNCTION "%s".%s() RESET search_path' % (self.s, name)])
        found = [f for f in result.findings if f.code == "RW_AUDIT_GUARD_DEFINITION"]
        self.assertEqual([f.subject for f in found], [name])
        self.assertIn("settings", found[0].detail)
        self.assertNotIn("prosrc", found[0].detail)
        self.assertTrue(real_body)

    def test_a_dropped_guard_is_seen_as_missing_or_as_a_function_set_finding(self):
        result = self.audit_in_transaction(['DROP FUNCTION "%s".md_release_stamp() CASCADE' % self.s])
        self.assertIn("RW_AUDIT_GUARD_DEFINITION", result.codes())

    def test_the_expected_definitions_are_built_from_the_migrations_alone(self):
        expected = audit_module.migration_guard_definitions(self.s)
        self.assertEqual(sorted(expected), sorted(GUARDS))
        migrations = {p.name: p.read_text("utf8") for p in (HERE.parents[1] / "src" / "persistence" / "migrations").glob("*.sql")}
        # the LAST definition in migration order wins: 0006 replaces the 0003/0004 ledger functions
        self.assertIn("epoch", expected["ledger_event_before_insert"]["prosrc"].lower() + migrations["0006_epoch_safe_correction_and_pin_guard.sql"].lower())
        for name in GUARDS:
            self.assertEqual(expected[name]["settings"], ("search_path=%s,pg_temp" % self.s,), name)
            self.assertEqual(expected[name]["language"], "plpgsql", name)
            self.assertFalse(expected[name]["security_definer"], name)


class FactsOfRuntimeToolTests(Pg):
    """A runtime tool's vantage: the PUBLISHER role reads the facts. What a non-superuser can read is shown here; anything it cannot read refuses
    (design 5.3 (c); 'not shown' in the design)."""
    INSTALL = "preflight_facts"
    _facts = None

    def gather(self):
        cls = type(self)
        if cls._facts is None:
            conn = self.inst.connect("publisher", autocommit=True)
            try:
                cls._facts = pf.gather_facts(conn, vantage="runtime", database=KIT.prov.db, socket=SOCKET, real_roles=self.real_roles_of_install(),
                                             real_database=KIT.prov.db, sysconfdir=pf.installation_sysconfdir())
            finally:
                conn.close()
        return cls._facts

    def test_a_non_superuser_reads_every_catalog_the_runtime_gate_needs(self):
        facts = self.gather()
        self.assertEqual(facts.not_inspected, (), facts.not_inspected)
        self.assertGreaterEqual(facts.version_num, 170000)
        self.assertEqual(str(facts.max_prepared_transactions), "0")
        self.assertIsNotNone(facts.listen_addresses)
        self.assertEqual(facts.session_replication_role, "origin")
        for field in ("roles", "escalation", "databases", "connect", "db_role_settings", "parameter_privileges"):
            self.assertIsNotNone(getattr(facts, field), field)
        self.assertIn(("public", "SET"), facts.parameter_privileges)                    # has_parameter_privilege accepts the name public
        self.assertIn(KIT.prov.db, [d for d, _a in facts.databases])

    def test_the_development_cluster_is_refused_and_only_by_the_refusal_side(self):
        facts = self.gather()
        decision = pf.decide(facts, vantage="runtime", real_roles=self.real_roles_of_install(), real_database=KIT.prov.db)
        self.assertFalse(decision.ok)
        self.assertIn("PF_CONNECTED", decision.codes())                                  # the cluster trusts its roles: a connection with no credential
        outcomes = {a.outcome for a in facts.attempts}
        self.assertIn(pf.CONNECTED, outcomes)
        self.assertNotIn(pf.CHALLENGED, outcomes)                                         # NOT calibrated here: a trust cluster never challenges
        self.assertNotIn(pf.REJECTED, outcomes)

    def test_a_role_that_was_never_created_is_other_on_a_trust_cluster(self):
        facts = self.gather()
        never = [a for a in facts.attempts if a.role == facts.never_role and a.probe_pass == "A"]
        self.assertTrue(never)
        for attempt in never:
            self.assertEqual(attempt.outcome, pf.OTHER, attempt)                          # an error after authentication: role does not exist
            self.assertIn("does not exist", attempt.message)

    def test_every_required_attempt_was_made_in_both_passes(self):
        facts = self.gather()
        have = {a.key for a in facts.attempts}
        for key in pf.required_attempts(facts.roles, facts.databases, facts.never_role):
            self.assertIn(key, have)
        self.assertTrue(any(a.replication for a in facts.attempts))                       # the cluster's superuser is probed with replication=true

    def test_the_probe_opened_connections_only_and_stored_nothing(self):
        text = pf.decide(self.gather(), vantage="runtime", real_roles=self.real_roles_of_install(), real_database=KIT.prov.db).text
        self.assertNotIn("password", text.lower().replace("password authentication", "").replace("no password supplied", ""))

    def test_a_stored_credential_for_this_cluster_is_found_without_connecting(self):
        with tempfile.TemporaryDirectory() as home:
            Path(home, ".pgpass").write_text("%s:%s:*:somebody:SENTINEL-PW\n" % (os.path.dirname(SOCKET), SOCKET.rsplit(".", 1)[1]))
            findings, _m, _n = pf.scan_stored_credentials({}, home, socket_dir=os.path.dirname(SOCKET), port=SOCKET.rsplit(".", 1)[1], login_roles=set())
        self.assertEqual(len(findings), 1)


class ProbeOnDevelopmentClusterTests(Pg):
    """Disposable roles, the probe and its classifier: the refusal side only."""
    INSTALL = "preflight_probe"

    def prober(self):
        prober = pf.Prober(os.path.dirname(SOCKET), SOCKET.rsplit(".", 1)[1], environ=dict(os.environ))
        self.addCleanup(prober.close)
        return prober

    def test_a_disposable_role_with_a_password_connects_without_one_on_a_trust_cluster(self):
        prober = self.prober()
        for probe_pass in ("A", "B"):
            attempt = prober.attempt(self.inst.roles["executor"], KIT.prov.db, probe_pass, False)
            self.assertEqual(attempt.outcome, pf.CONNECTED, attempt)

    def test_a_missing_socket_is_other(self):
        prober = pf.Prober("/nonexistent-finweb-dir", "5432", environ={})
        self.addCleanup(prober.close)
        attempt = prober.attempt("anyone", "postgres", "A", False)
        self.assertEqual(attempt.outcome, pf.OTHER, attempt)

    def test_a_database_that_does_not_exist_is_other_not_challenged(self):
        attempt = self.prober().attempt(self.inst.roles["executor"], "finweb_pf_no_such_database", "A", False)
        self.assertEqual(attempt.outcome, pf.OTHER, attempt)
        self.assertIn("does not exist", attempt.message)

    def test_the_child_process_sends_no_statement(self):
        """The tracked statements of the disposable database do not grow by a probe: pg_stat_database counts transactions, the probe opens none."""
        before = self.admin.execute("SELECT xact_commit+xact_rollback FROM pg_stat_database WHERE datname=%s", (KIT.prov.db,)).fetchone()[0]
        self.prober().attempt(self.inst.roles["executor"], KIT.prov.db, "A", False)
        import time
        time.sleep(1.0)                               # the statistics collector flushes lazily
        after = self.admin.execute("SELECT xact_commit+xact_rollback FROM pg_stat_database WHERE datname=%s", (KIT.prov.db,)).fetchone()[0]
        self.assertLessEqual(after - before, 3)       # this test's own query is the only transaction (plus the statistics read itself)


class AccountRoleChecksOfTheInstallerTests(Pg):
    """PD-0078 (R7 fix round): the installer's own checks (`real_install.run_checks(phase="check")`) judge the fifth role. The install is a crafted REAL
    kind (E11, in the disposable database; the REAL file list, the five roles granted by the product's body) so that the audit reads it as REAL. The
    development cluster's own refusals (trust rows, TCP) are present, so the assertions look for the codes of the account role only. Each crafted
    grant is written by the administrative role of the disposable database and reverted in `finally`."""
    INSTALL = "r7acctreal"
    KIND = "REAL"

    def crafted(self, grant, revoke):
        import contextlib
        fmt = dict(s=self.s, a=self.inst.roles["account"])

        @contextlib.contextmanager
        def window():
            self.admin.execute(grant.format(**fmt))
            try:
                yield
            finally:
                self.admin.execute(revoke.format(**fmt))
        return window()

    def test_the_installers_checks_refuse_an_extra_grant_an_economic_grant_and_a_missing_role(self):
        names = self.names()

        def checks(n=names):
            return real_install.run_checks(self.admin, SOCKET, phase="check", names=n, say=lambda line: None)
        self.assertNotIn("PF_CATALOG_AUDIT", checks().codes())
        self.assertNotIn("PF_REAL_ROLE_MISSING", checks().codes())
        for label, grant, revoke in (("an extra grant", "GRANT DELETE ON {s}.web_identity TO {a}", "REVOKE DELETE ON {s}.web_identity FROM {a}"),
                                     ("an economic grant", "GRANT SELECT ON {s}.portfolio TO {a}", "REVOKE SELECT ON {s}.portfolio FROM {a}")):
            with self.subTest(label), self.crafted(grant, revoke):
                decision = checks()
                self.assertIn("PF_CATALOG_AUDIT", decision.codes(), label)
                self.assertTrue(any(a in decision.text for a in ("web_identity", "portfolio")), decision.text)
        absent = real_install.InstallNames(names.database, names.schema, names.owner, names.executor, names.loader, names.publisher, names.account + "_gone")
        decision = checks(absent)
        self.assertIn("PF_REAL_ROLE_MISSING", decision.codes())
        self.assertIn("PF_CATALOG_AUDIT", decision.codes())
        self.assertNotIn("PF_CATALOG_AUDIT", checks().codes(), "reverted")


class InstallerOnTestInstallTests(Pg):
    """The real installer's parts against a disposable database. `install_in_database` writes the REAL kind row and runs the REAL file list; the
    checks of Phase 2 / `check` run on the development cluster and show their refusal side."""

    def test_install_in_database_runs_the_real_file_list_and_the_real_lists_and_writes_real_last(self):
        prov = KIT.prov
        tag = "ri%d" % (id(self) % 1000)
        names = real_install.InstallNames(prov.db, prov.owned_name("%s_%s" % (prov.own, tag)), *(prov.owned_name("%s_%s_%s" % (prov.own, tag, k))
                                                                                                 for k in ("owner", "executor", "loader", "publisher", "account")))
        with prov.admin(prov.database) as conn:
            for kind, mode in (("owner", "NOLOGIN"), ("executor", "PASSWORD"), ("loader", "PASSWORD"), ("publisher", "PASSWORD"), ("account", "PASSWORD")):
                prov.create_role(conn, getattr(names, kind), mode)
        lines = []
        conn = prov.admin(prov.db)
        real_install.install_in_database(conn, names, w_seconds=600, say=lines.append)
        self.assertTrue(any("file list " + ", ".join(real_roles.sql_files("REAL")) in line for line in lines), lines)
        self.assertFalse(any("fictional" in line for line in lines))
        rows = conn.execute('SELECT kind,w_seconds FROM "%s".rw_install' % names.schema).fetchall()
        self.assertEqual(rows, [("REAL", 600)])
        # the audit as REAL passes: the TEST-only part is absent, every list is exactly as the installer applies it
        result = audit_module.audit(conn, names.schema, names.owner, names.executor, names.loader, names.publisher, as_kind="REAL", account_role=names.account)
        self.assertEqual(result.findings, (), [f.short() for f in result.findings])
        functions = conn.execute("SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND proname=ANY(%s)",
                                 (names.schema, [n for n, _a in real_roles.TEST_ONLY_FUNCTIONS])).fetchall()
        self.assertEqual(functions, [])
        # the same catalog read as TEST reports the missing TEST-only part: the audit can see
        as_test = audit_module.audit(conn, names.schema, names.owner, names.executor, names.loader, names.publisher, as_kind="TEST", account_role=names.account)
        self.assertIn("RW_AUDIT_TEST_ONLY_MISSING", as_test.codes())
        # Phase 2 / check on this install, as REAL, on the development cluster: the catalog audit passes and the cluster is refused for what it is
        decision = real_install.run_checks(conn, SOCKET, phase="check", names=names, say=lambda line: None)
        self.assertFalse(decision.ok)
        codes = set(decision.codes())
        self.assertNotIn("PF_CATALOG_AUDIT", codes)                                       # the audit found nothing: the install holds exactly its lists
        self.assertTrue({"PF_CONNECTED", "PF_HBA_NOT_LOCAL", "PF_HBA_METHOD", "PF_LISTEN_ADDRESSES"} <= codes, codes)    # the trust cluster's hba rows and TCP
        conn.close()

    def test_the_audit_of_a_test_install_read_as_real_is_a_catalog_audit_refusal_of_the_installer(self):
        """The same audit, on a TEST install, asked as REAL: the TEST-only part is present. Through the installer's own run_checks, the phase-2 facts
        carry it as PF_CATALOG_AUDIT."""
        conn = self.inst.connect("admin")
        self.addCleanup(self._close, conn)
        decision = real_install.run_checks(conn, SOCKET, phase="check", names=self.names(), say=lambda line: None)
        self.assertIn("PF_CATALOG_AUDIT", decision.codes())
        self.assertIn("RW_AUDIT_TEST_ONLY_PRESENT", decision.text)

    def test_phase_zero_against_the_development_cluster_is_refused_and_creates_nothing(self):
        conn = self.inst.connect("admin")
        self.addCleanup(self._close, conn)
        before = conn.execute("SELECT count(*) FROM pg_database").fetchone()[0], conn.execute("SELECT count(*) FROM pg_roles").fetchone()[0]
        decision = real_install.run_checks(conn, SOCKET, phase="0", names=real_install.REAL_NAMES, say=lambda line: None)
        self.assertFalse(decision.ok)
        self.assertTrue({"PF_CONNECTED", "PF_HBA_NOT_LOCAL"} <= set(decision.codes()), decision.codes())
        after = conn.execute("SELECT count(*) FROM pg_database").fetchone()[0], conn.execute("SELECT count(*) FROM pg_roles").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(conn.execute("SELECT count(*) FROM pg_database WHERE datname LIKE 'finweb\\_real%'").fetchone()[0], 0)

    def test_phase_one_refuses_at_phase_zero_on_the_development_cluster_and_runs_no_statement(self):
        conn = self.inst.connect("admin")
        self.addCleanup(self._close, conn)
        executed = []

        class Recording:
            def __init__(self, inner):
                self.inner = inner

            def execute(self, sql, params=()):
                executed.append(sql if isinstance(sql, str) else sql.as_string())
                return self.inner.execute(sql, params)

            def transaction(self):
                return self.inner.transaction()
        lines = []
        status = real_install.phase1(Recording(conn), lambda: self.fail("the real database was opened"), SOCKET, loader_login="login",
                                     names=real_install.REAL_NAMES, say=lines.append)
        self.assertEqual(status, real_install.EXIT_REFUSED)
        self.assertTrue(any("Phase 0 refused: nothing was created." in line for line in lines))
        self.assertEqual([s for s in executed if re.match(r"\s*(CREATE|ALTER|DROP|GRANT|REVOKE)", s)], [])


class RoleClosureTests(Pg):
    """FF1-C09: effective role closure of the deployment, on a TEST install."""
    INSTALL = "preflight_closure"

    def test_the_four_roles_of_an_install_hold_no_membership_anywhere_and_the_preflight_sees_none(self):
        roles = list(self.inst.roles.values())
        for a in roles:
            for b in roles:
                if a != b:
                    self.assertFalse(self.admin.execute("SELECT pg_has_role(%s::name,%s::name,'MEMBER')", (a, b)).fetchone()[0], (a, b))
        conn = self.inst.connect("publisher", autocommit=True)
        facts = pf.gather_facts(conn, vantage="runtime", database=KIT.prov.db, socket=SOCKET, real_roles=self.real_roles_of_install(),
                                real_database=KIT.prov.db, run_probe=False, sysconfdir=pf.installation_sysconfdir())
        conn.close()
        mine = [(u, x) for (u, x), flags in facts.escalation.items() if u in roles and any(flags)]
        self.assertEqual(mine, [])
        self.assertEqual(facts.not_inspected, ())

    def test_a_granted_membership_is_an_escalation_path_in_the_gathered_facts(self):
        """Crafted (E11): the administrative role grants the executor membership in the loader (Install.set_membership), reverted."""
        self.inst.set_membership("executor", "loader", True)
        try:
            conn = self.inst.connect("publisher", autocommit=True)
            facts = pf.gather_facts(conn, vantage="runtime", database=KIT.prov.db, socket=SOCKET, real_roles=self.real_roles_of_install(),
                                    real_database=KIT.prov.db, run_probe=False, sysconfdir=pf.installation_sysconfdir())
            conn.close()
        finally:
            self.inst.set_membership("executor", "loader", False)
        r = self.inst.roles
        self.assertEqual(facts.escalation[(r["executor"], r["loader"])][0], True)
        decision = pf.decide(facts, vantage="runtime", real_roles=self.real_roles_of_install(), real_database=KIT.prov.db)
        self.assertIn("PF_ESCALATION_PATH", decision.codes())


class LifecycleTests(Pg):
    """FF1-C10: a later migration needs the revoke re-run (design 1.2 rule 5.3 (e); R6's plan states the step). Crafted, rolled back."""
    INSTALL = "preflight_lifecycle"

    def test_a_routine_a_later_migration_creates_leaves_the_audit_refusing_until_the_revoke_is_re_run(self):
        r = self.inst.roles
        migration = 'CREATE FUNCTION "%s".added_by_a_later_migration() RETURNS int LANGUAGE sql AS $$ SELECT 1 $$' % self.s
        revoke = real_roles.grant_statements("REAL", self.s, r["executor"], r["loader"], r["publisher"])[0]
        self.assertEqual(revoke, 'REVOKE EXECUTE ON ALL ROUTINES IN SCHEMA "%s" FROM PUBLIC' % self.s)
        run_as_owner = ['SET ROLE "%s"' % r["owner"], migration, "RESET ROLE"]            # a later migration runs as the owner, like the first ones
        before = self.audit_in_transaction(run_as_owner)
        self.assertIn("RW_AUDIT_PRIVILEGE_DIFFERS", before.codes())                       # PUBLIC's default EXECUTE on the new routine: fail closed
        after = self.audit_in_transaction(run_as_owner + [revoke])
        # the revoke removes PUBLIC's EXECUTE on the new routine: the audit is clean again (a routine outside the gateway's prefixes is not in its set)
        self.assertEqual(after.findings, (), [f.short() for f in after.findings])
        control = self.audit_in_transaction([])
        self.assertEqual(control.findings, ())


class GateByCommandOnTestInstallTests(Pg):
    """5.1 end to end through the PUBLISHER TOOL's `main`: a REAL target is simulated by putting a failing or passing preflight decision in the
    place of the gate and the kind rows (the two module-level functions of the tool); the writes are real, on a TEST install. A real REAL target
    does not exist before R8 step 1."""
    INSTALL = "preflight_commands"

    def failing(self, *codes):
        refusals = tuple(pf.Refusal(c) for c in (codes or ("PF_CONNECTED",)))
        return pf.Decision(False, refusals, ("attempt: simulated -> CONNECTED",) + tuple("REFUSED " + r.short() for r in refusals) + ("preflight: REFUSED (%d)" % len(refusals),))

    def passing(self):
        return pf.Decision(True, (), ("preflight: PASSED",))

    def run_main(self, extra, *, gate, kinds=("REAL",), database="finweb_real_simulated"):
        out = io.StringIO()
        conn = self.conn("publisher", autocommit=False)
        args = ["--socket", SOCKET, "--database", database, "--user", "x", "--schema", self.s] + extra
        with mock.patch.object(store, "_read_kind_rows", return_value=kinds), mock.patch.object(store, "_run_gate", gate):
            status = store.main(args, connect=lambda a: conn, out=out)
        return status, out.getvalue()

    def decision_args(self, ref=fx.REF):
        return ["--actor", fx.ACTOR, "--pd", ref.pd_id, "--commit", ref.git_commit, "--sha", ref.doc_sha256]

    def files(self, snapshot, tmp, *, rights_json=None):
        proposal, evidence = Path(tmp, "p.json"), Path(tmp, "e.json")
        proposal.write_bytes(self.proposal(snapshot))
        evidence.write_text(json.dumps([e.as_json() for e in fx.hg4_shape(self.bound())]))
        valid = (self.db_now() + fx.seconds(300)).astimezone(store.dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return ["--proposal", str(proposal), "--evidence-file", str(evidence), "--valid-until", valid] + self.decision_args()

    def published(self):
        snapshot, _valid, result = self.publish(valid_in=300)
        return snapshot, result.data["context_id"]

    # -- publish ---------------------------------------------------------------------------------------------------------
    def test_publish_is_refused_on_a_failing_preflight_and_writes_nothing(self):
        snapshot = self.snapshot()
        before = (self.count("rw_snapshot"), self.count("rw_history"), self.count("rw_head"))
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            status, text = self.run_main(["publish"] + self.files(snapshot, tmp), gate=lambda c, a: (calls.append(1), self.failing())[1])
        self.assertEqual(status, store.EXIT_REFUSED)
        self.assertIn("PF_PREFLIGHT_REFUSED", text)
        self.assertIn("PF_CONNECTED", text)
        self.assertIn("nothing was recorded", text)
        self.assertEqual(calls, [1])
        self.assertEqual((self.count("rw_snapshot"), self.count("rw_history"), self.count("rw_head")), before)

    def test_publish_proceeds_on_a_passing_preflight_and_prints_its_result(self):
        snapshot = self.snapshot()
        with tempfile.TemporaryDirectory() as tmp:
            status, text = self.run_main(["publish"] + self.files(snapshot, tmp), gate=lambda c, a: self.passing())
        self.assertEqual(status, 0, text)
        self.assertIn("preflight: PASSED", text)
        self.assertIn("published context " + snapshot.context_id, text)
        self.assertEqual(len(self.history(snapshot.context_id)), 1)

    # -- renew -----------------------------------------------------------------------------------------------------------
    def renew_args(self, ctx, generation):
        evidence = Path(tempfile.mkdtemp(), "e.json")
        self.addCleanup(lambda: evidence.unlink(missing_ok=True))
        evidence.write_text(json.dumps([e.as_json() for e in fx.hg4_shape(self.bound())]))
        valid = (self.db_now() + fx.seconds(400)).astimezone(store.dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return ["renew", "--context", ctx, "--generation", str(generation), "--evidence-file", str(evidence), "--valid-until", valid] + self.decision_args(fx.REF_OTHER)

    def test_renew_is_refused_on_a_failing_preflight_and_proceeds_on_a_passing_one(self):
        _snapshot, ctx = self.published()
        status, text = self.run_main(self.renew_args(ctx, 1), gate=lambda c, a: self.failing("PF_OTHER_OUTCOME"))
        self.assertEqual(status, store.EXIT_REFUSED, text)
        self.assertIn("PF_OTHER_OUTCOME", text)
        self.assertEqual(len(self.history(ctx)), 1)
        status, text = self.run_main(self.renew_args(ctx, 1), gate=lambda c, a: self.passing())
        self.assertEqual(status, 0, text)
        self.assertEqual(len(self.history(ctx)), 2)

    # -- withdraw: never gated -------------------------------------------------------------------------------------------
    def withdraw_args(self, ctx, generation):
        return ["withdraw", "--context", ctx, "--generation", str(generation)] + self.decision_args(fx.REF_OTHER)

    def test_withdraw_proceeds_on_a_failing_preflight_prints_its_result_after_the_withdrawal_and_exits_with_its_own_status(self):
        _snapshot, ctx = self.published()
        seen = []

        def gate(conn, args):
            seen.append((len(self.marks(ctx)), len(self.history(ctx))))          # at the moment the gate runs, the mark and the generation are COMMITTED
            return self.failing()
        status, text = self.run_main(self.withdraw_args(ctx, 1), gate=gate)
        self.assertEqual(status, 0, text)
        self.assertEqual(seen, [(1, 2)])
        self.assertIn("all four rights are off", text)
        self.assertIn("preflight result", text)
        self.assertIn("PF_CONNECTED", text)
        self.assertLess(text.index("all four rights are off"), text.index("preflight result"))
        self.assertEqual(self.head(ctx)[1], {k: False for k in store.RIGHTS})

    def test_withdraw_proceeds_when_the_preflight_itself_raises_or_times_out(self):
        _snapshot, ctx = self.published()

        def gate(conn, args):
            raise TimeoutError("probe took too long")
        status, text = self.run_main(self.withdraw_args(ctx, 1), gate=gate)
        self.assertEqual(status, 0, text)
        self.assertIn("preflight could not run: TimeoutError", text)
        self.assertEqual(self.head(ctx)[1], {k: False for k in store.RIGHTS})

    def test_re_running_a_withdrawal_and_a_pending_one_proceed_likewise(self):
        _snapshot, ctx = self.published()
        self.assertEqual(self.run_main(self.withdraw_args(ctx, 1), gate=lambda c, a: self.failing())[0], 0)
        status, text = self.run_main(self.withdraw_args(ctx, 1), gate=lambda c, a: self.failing())          # identical command again
        self.assertEqual(status, 0, text)
        self.assertIn("preflight result", text)
        # a pending withdrawal (its own status 3): the preflight still prints and the status stays the withdrawal's own
        pending = store.CommandResult(store.EXIT_NOT_YET_EFFECTIVE, "NOT_YET_EFFECTIVE", ("not yet effective",), {})
        with mock.patch.object(store.RealPublisher, "withdraw", return_value=pending):
            status, text = self.run_main(self.withdraw_args(ctx, 1), gate=lambda c, a: self.failing())
        self.assertEqual(status, store.EXIT_NOT_YET_EFFECTIVE)
        self.assertIn("not yet effective", text)
        self.assertIn("preflight result", text)

    def test_withdraw_is_not_stopped_by_a_kind_and_name_that_disagree_or_by_a_test_kind(self):
        for kinds, database in ((("TEST",), "finweb_real_simulated"), (("REAL",), "finweb_dev_x"), (("TEST",), "finweb_dev_x")):
            _snapshot, ctx = self.published()
            calls = []
            status, text = self.run_main(self.withdraw_args(ctx, 1), gate=lambda c, a: (calls.append(1), self.failing())[1], kinds=kinds, database=database)
            self.assertEqual(status, 0, (kinds, database, text))
            self.assertEqual(calls, [], (kinds, database))                         # the result is not printed for a non-REAL target
            self.assertNotIn("preflight result", text)

    def test_withdraw_with_no_kind_row_says_so_and_writes_nothing(self):
        _snapshot, ctx = self.published()
        before = (len(self.history(ctx)), len(self.marks(ctx)))
        for kinds in ((), None, ("REAL", "REAL")):
            status, text = self.run_main(self.withdraw_args(ctx, 1), gate=lambda c, a: self.fail("gate called"), kinds=kinds)
            self.assertEqual(status, store.EXIT_REFUSED, kinds)
            self.assertIn("PF_NO_KIND_ROW", text)
            self.assertIn("nothing was recorded", text)
        self.assertEqual((len(self.history(ctx)), len(self.marks(ctx))), before)

    # -- the table of 5.2 through the tool ---------------------------------------------------------------------------------
    def test_a_test_target_meets_no_preflight_and_a_disagreeing_one_is_refused_for_the_gated_commands(self):
        calls = []
        gate = lambda c, a: (calls.append(1), self.failing())[1]                        # noqa: E731
        snapshot = self.snapshot()
        with tempfile.TemporaryDirectory() as tmp:
            status, text = self.run_main(["publish"] + self.files(snapshot, tmp), gate=gate, kinds=("TEST",), database="finweb_dev_x")
            self.assertEqual((status, calls), (0, []), text)                              # TEST kind, TEST name: no preflight, as R1's tests ran
            other = self.snapshot()
            for kinds, database, code in ((("TEST",), "finweb_real_simulated", "PF_KIND_NAME_DISAGREE"), (("REAL",), "finweb_dev_x", "PF_KIND_NAME_DISAGREE"),
                                          ((), "finweb_real_simulated", "PF_NO_KIND_ROW"), (("TEST", "TEST"), "finweb_dev_x", "PF_NO_KIND_ROW")):
                before = self.count("rw_snapshot")
                status, text = self.run_main(["publish"] + self.files(other, tmp), gate=gate, kinds=kinds, database=database)
                self.assertEqual(status, store.EXIT_REFUSED, (kinds, database))
                self.assertIn(code, text)
                self.assertEqual(self.count("rw_snapshot"), before)
        self.assertEqual(calls, [])

    def test_the_real_gate_reads_the_install_kind_through_the_publishers_own_grant(self):
        """No patch: the kind rows are read by the tool as the publisher role, on a TEST install."""
        rows = store._read_kind_rows(self.conn("publisher", autocommit=False), self.s)
        self.assertEqual(rows, ("TEST",))
        self.assertEqual(pf.decide_target(KIT.prov.db, rows).decision, "TEST")
        self.assertEqual(pf.decide_target(KIT.prov.db, store._read_kind_rows(self.conn("executor", autocommit=False), self.s)).decision, "TEST")


if __name__ == "__main__":
    import unittest
    unittest.main()
