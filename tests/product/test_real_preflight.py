"""F1 R6, no database: the preflight of the install rule (design 1.2 rule 5 and rule 7) on FAKE FACTS.

Each case is a fact set in and a decision out. The expected refusal codes are written here by hand from the design's case list (rule 7); they are
not read from the code under test. Nothing here connects to a server. The probe's classifier is checked on message texts; which texts a real
scram-only server produces is calibrated by the opt-in test (`test_preflight_calibration`), not by anything in this module.
"""
from __future__ import annotations

from dataclasses import replace
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from persistence import connection, real_preflight as pf, real_workspace_store as store  # noqa: E402
from persistence.real_preflight import (Attempt, CHALLENGED, CONNECTED, Facts, HbaRow, OTHER, REJECTED, RoleFact, ScanFinding,  # noqa: E402
                                        required_attempts)

SENTINEL = "SENTINEL-PASSWORD-7c1e"
SOCKET_DIR, PORT = "/srv/finweb/real/socket", "55432"
R = pf.REAL_ROLES
SU = "cluster_owner"
POWER = {"superuser": True, "createrole": True, "createdb": True, "replication": True, "bypassrls": True}
PG_ROLES = ("pg_write_all_data", "pg_read_all_data", "pg_execute_server_program", "pg_read_server_files", "pg_write_server_files",
            "pg_signal_backend", "pg_database_owner")


def roles(*, loader_login=True):
    out = [RoleFact(SU, login=True, **POWER), RoleFact(R["owner"]), RoleFact(R["executor"], login=True), RoleFact(R["loader"], login=loader_login),
           RoleFact(R["publisher"], login=True), RoleFact(R["account"], login=True)]       # PD-0078: the fifth role
    return tuple(out) + tuple(RoleFact(name) for name in PG_ROLES)


def clean(**overrides):
    """A clean REAL cluster at Phase 2: one LOGIN superuser, the four real roles, scram everywhere, nothing connects, the audit has no finding."""
    rs = roles()
    databases = (("postgres", True), ("template1", True), ("template0", False), (pf.REAL_DATABASE, True))
    never = "finweb_pf_0123456789ab"
    attempts = tuple(Attempt(*key, CHALLENGED, "") for key in required_attempts(rs, databases, never))
    login_plain = [r for r in rs if r.login and not r.superuser]
    facts = Facts(
        database=pf.REAL_DATABASE, version_num=170011, max_prepared_transactions="0", listen_addresses="", session_replication_role="origin", roles=rs,
        escalation={(u.name, x.name): (False, False, False) for u in login_plain for x in rs if x.name != u.name}, databases=databases,
        connect={(r, d): False for r in R.values() for d, allow in databases if allow and d != pf.REAL_DATABASE}, db_role_settings=(),
        parameter_privileges={(w, p): False for w in [u.name for u in login_plain] + ["public"] for p in ("SET", "ALTER SYSTEM")},
        never_role=never, attempts=attempts, stored=(), not_inspected=(),
        hba_rows=(HbaRow(1, "local", ("all",), ("all",), "scram-sha-256"), HbaRow(2, "local", ("replication",), ("all",), "scram-sha-256")),
        verifiers={r.name: True for r in rs if r.login},
        settings={"password_encryption": "scram-sha-256", "log_statement": "none", "log_min_duration_statement": "-1", "log_min_error_statement": "error",
                  "data_directory": "/srv/finweb/real/data", "hba_file": "/srv/finweb/real/data/pg_hba.conf",
                  "ident_file": "/srv/finweb/real/data/pg_ident.conf", "unix_socket_directories": SOCKET_DIR},
        forbidden_roots=("/Users/owner/Desktop/Fin Web", "/private/tmp", "/tmp"), audit_findings=())
    return replace(facts, **overrides)


def add_roles(facts, *new):
    """The fact set with more roles in the catalog, everything else about them clean: no membership, no parameter privilege, every attempt
    CHALLENGED, a scram verifier. A test then changes the one fact it is about."""
    rs = tuple(facts.roles) + tuple(new)
    escalation = dict(facts.escalation)
    privileges = dict(facts.parameter_privileges)
    verifiers = dict(facts.verifiers)
    for u in rs:
        if u.login and not u.superuser:
            for x in rs:
                if x.name != u.name:
                    escalation.setdefault((u.name, x.name), (False, False, False))
            privileges.setdefault((u.name, "SET"), False)
            privileges.setdefault((u.name, "ALTER SYSTEM"), False)
        if u.login:
            verifiers.setdefault(u.name, True)
    have = {a.key for a in facts.attempts}
    attempts = tuple(facts.attempts) + tuple(Attempt(*k, CHALLENGED) for k in required_attempts(rs, facts.databases, facts.never_role) if k not in have)
    return replace(facts, roles=rs, escalation=escalation, parameter_privileges=privileges, verifiers=verifiers, attempts=attempts)


def with_attempt(facts, role, database, probe_pass, replication, outcome, message=""):
    key = (role, database, probe_pass, replication)
    return replace(facts, attempts=tuple(Attempt(*key, outcome, message) if a.key == key else a for a in facts.attempts))


class Base(unittest.TestCase):
    def decide(self, facts, **kw):
        kw.setdefault("vantage", "installer")
        kw.setdefault("phase", "2")
        decision = pf.decide(facts, **kw)
        self.assertNotIn(SENTINEL, decision.text)
        return decision

    def assertRefused(self, facts, code, **kw):
        decision = self.decide(facts, **kw)
        self.assertFalse(decision.ok, "expected a refusal with %s; got %s" % (code, decision.text))
        self.assertIn(code, decision.codes(), decision.text)
        return decision

    def assertPasses(self, facts, **kw):
        decision = self.decide(facts, **kw)
        self.assertTrue(decision.ok, decision.text)
        return decision


class ControlTests(Base):
    def test_a_clean_real_cluster_passes_at_phase_two_and_at_check_and_for_a_runtime_tool(self):
        self.assertPasses(clean())
        self.assertPasses(clean(), phase="check")
        self.assertPasses(clean(hba_rows=None, verifiers=None, settings=None, audit_findings=None), vantage="runtime", phase=None)

    def test_the_output_never_holds_a_password(self):
        facts = clean(stored=(ScanFinding("passfile (default)", "/h/.pgpass", "line 3", "host=/x port=1 db=* user=u", "could address"),))
        self.assertNotIn(SENTINEL, self.decide(facts).text)


class ServerTests(Base):
    """Two new refusals of this increment, each with its own named code."""

    def test_a_server_below_17_is_refused_with_its_own_code_and_nothing_else_is_judged(self):
        for version in (160015, 150000, 90600):
            decision = self.assertRefused(clean(version_num=version), "PF_SERVER_VERSION_BELOW_17")
            self.assertEqual(decision.codes(), ("PF_SERVER_VERSION_BELOW_17",))        # the later reads may not exist on an older server
        self.assertPasses(clean(version_num=170000))
        self.assertPasses(clean(version_num=180001))
        self.assertRefused(clean(version_num=None), "PF_NOT_INSPECTED")

    def test_max_prepared_transactions_must_be_zero(self):
        for value in ("1", "10", 5, None, "off"):
            self.assertRefused(clean(max_prepared_transactions=value), "PF_PREPARED_TRANSACTIONS")
        for value in ("0", 0):
            self.assertPasses(clean(max_prepared_transactions=value))

    def test_listen_addresses_must_be_empty_at_the_installer_and_at_a_runtime_tool(self):
        for vantage, phase in (("installer", "2"), ("runtime", None)):
            for value in ("localhost", "*", "127.0.0.1"):
                self.assertRefused(clean(listen_addresses=value), "PF_LISTEN_ADDRESSES", vantage=vantage, phase=phase)
            self.assertRefused(clean(listen_addresses=None), "PF_NOT_INSPECTED", vantage=vantage, phase=phase)       # a tool that cannot read it refuses

    def test_session_replication_role_must_be_origin(self):
        self.assertRefused(clean(session_replication_role="replica"), "PF_SESSION_REPLICATION_ROLE")
        self.assertRefused(clean(session_replication_role=None), "PF_NOT_INSPECTED")


class ConnectionPathTests(Base):
    """Rule 7, cases: connection paths."""

    def test_a_trust_line_for_the_superuser_for_the_publisher_and_for_the_executor_each_refuse(self):
        for role in (SU, R["publisher"], R["executor"]):
            for probe_pass in ("A", "B"):
                self.assertRefused(with_attempt(clean(), role, "postgres", probe_pass, False, CONNECTED, "trust"), "PF_CONNECTED")

    def test_local_all_all_trust_on_another_database_refuses(self):
        self.assertRefused(with_attempt(clean(), R["executor"], "template1", "A", False, CONNECTED), "PF_CONNECTED")

    def test_a_peer_or_ident_line_looks_like_a_connection_and_refuses(self):
        self.assertRefused(with_attempt(clean(), R["loader"], "postgres", "A", False, CONNECTED, "peer"), "PF_CONNECTED")

    def test_a_never_created_role_that_connects_refuses(self):
        facts = clean()
        self.assertRefused(with_attempt(facts, facts.never_role, "postgres", "A", False, CONNECTED), "PF_CONNECTED")

    def test_a_replication_attempt_that_connects_refuses(self):
        self.assertRefused(with_attempt(clean(), SU, "replication", "A", True, CONNECTED), "PF_CONNECTED")

    def test_an_error_after_authentication_a_timeout_and_a_missing_socket_are_other_and_refuse(self):
        for message in ('FATAL:  database "x" does not exist', "timeout", "No such file or directory"):
            self.assertRefused(with_attempt(clean(), R["executor"], "postgres", "B", False, OTHER, message), "PF_OTHER_OUTCOME")

    def test_every_attempt_challenged_passes_and_reject_and_no_replication_line_pass(self):
        self.assertPasses(clean())
        # a `reject` record for a role and database, which the rows predict
        rows = (HbaRow(1, "local", ("postgres",), (R["executor"],), "reject"), HbaRow(2, "local", ("all",), ("all",), "scram-sha-256"),
                HbaRow(3, "local", ("replication",), ("all",), "scram-sha-256"))
        facts = with_attempt(clean(hba_rows=rows), R["executor"], "postgres", "A", False, REJECTED)
        facts = with_attempt(facts, R["executor"], "postgres", "B", False, REJECTED)
        self.assertPasses(facts)
        # no `replication` line at all: the replication attempt is REJECTED (no record matches), and the rows predict it
        rows = (HbaRow(1, "local", ("all",), ("all",), "scram-sha-256"),)
        facts = clean(hba_rows=rows)
        for probe_pass in ("A", "B"):
            facts = with_attempt(facts, SU, "replication", probe_pass, True, REJECTED)
        self.assertPasses(facts)

    def test_a_rejected_the_rows_do_not_predict_refuses_as_a_file_loaded_disagreement(self):
        facts = with_attempt(clean(), R["executor"], "postgres", "A", False, REJECTED)
        self.assertRefused(facts, "PF_HBA_FILE_LOADED_DIFFER")
        # and a CHALLENGED where the file says reject
        rows = (HbaRow(1, "local", ("all",), ("all",), "reject"),)
        self.assertRefused(clean(hba_rows=rows), "PF_HBA_FILE_LOADED_DIFFER")

    def test_a_role_that_is_a_member_of_itself_is_not_a_finding(self):
        facts = clean()
        facts = replace(facts, escalation={**facts.escalation, (R["executor"], R["executor"]): (True, True, True)})
        self.assertPasses(facts)

    def test_an_attempt_the_probe_did_not_make_is_a_refusal_not_a_pass(self):
        facts = clean()
        self.assertRefused(replace(facts, attempts=facts.attempts[1:]), "PF_PROBE_NOT_RUN")
        self.assertRefused(replace(facts, attempts=()), "PF_PROBE_NOT_RUN")


class EscalationTests(Base):
    """Rule 7, cases: escalation (5.3 (a), (b)); no exemption list exists."""

    def escalate(self, user, other, flags):
        facts = clean()
        return replace(facts, escalation={**facts.escalation, (user, other): flags})

    def test_a_missing_escalation_answer_for_any_pair_refuses_as_not_inspected(self):
        """TR6B-L-1 (B6b): one (login role, other role) pair that was not asked is a refusal, never a pass."""
        facts = clean()
        for key in sorted(facts.escalation)[:3] + [(R["publisher"], R["executor"])]:
            missing = {k: v for k, v in facts.escalation.items() if k != key}
            decision = self.assertRefused(replace(facts, escalation=missing), "PF_NOT_INSPECTED")
            self.assertIn("%s in %s" % key, decision.text)

    def test_a_trusted_createrole_login_role_refuses(self):
        self.assertRefused(add_roles(clean(), RoleFact("helper", login=True, createrole=True)), "PF_LOGIN_POWER_ROLE")

    def test_a_login_role_with_set_but_no_inherit_in_a_nologin_role_with_each_power_attribute_refuses(self):
        for attribute in ("superuser", "createrole", "bypassrls"):
            holder = RoleFact("nologin_" + attribute, **{attribute: True})
            facts = add_roles(clean(), holder)
            facts = replace(facts, escalation={**facts.escalation, (R["executor"], holder.name): (False, False, True)})
            decision = self.assertRefused(facts, "PF_ESCALATION_PATH")
            self.assertEqual(decision.codes(), ("PF_ESCALATION_PATH",))

    def test_a_login_role_with_membership_only_in_any_role_refuses(self):
        self.assertRefused(self.escalate(R["loader"], R["owner"], (True, False, False)), "PF_ESCALATION_PATH")
        self.assertRefused(self.escalate(R["publisher"], "pg_signal_backend", (True, False, False)), "PF_ESCALATION_PATH")

    def test_a_login_role_that_is_a_member_of_the_login_superuser_and_the_executor_granted_the_superuser_refuse(self):
        self.assertRefused(self.escalate(R["publisher"], SU, (True, True, True)), "PF_ESCALATION_PATH")
        self.assertRefused(self.escalate(R["executor"], SU, (True, False, True)), "PF_ESCALATION_PATH")

    def test_each_predefined_role_directly_and_through_an_intermediate_nologin_role_refuses(self):
        for predefined in PG_ROLES:
            if predefined == "pg_database_owner":
                continue
            # directly
            self.assertRefused(self.escalate(R["executor"], predefined, (True, True, True)), "PF_ESCALATION_PATH")
            # through an intermediate NOLOGIN role: pg_has_role reports indirect membership, so the fact for the predefined role is the same
            facts = add_roles(clean(), RoleFact("via_" + predefined))
            facts = replace(facts, escalation={**facts.escalation, (R["executor"], "via_" + predefined): (True, True, True),
                                               (R["executor"], predefined): (True, True, True)})
            self.assertRefused(facts, "PF_ESCALATION_PATH")

    def test_a_pg_role_under_an_unlisted_name_refuses_with_no_enumeration(self):
        facts = add_roles(clean(), RoleFact("pg_added_by_a_later_server"))
        facts = replace(facts, escalation={**facts.escalation, (R["executor"], "pg_added_by_a_later_server"): (True, False, False)})
        self.assertRefused(facts, "PF_ESCALATION_PATH")

    def test_a_login_role_that_owns_the_real_database_refuses_through_pg_database_owner(self):
        self.assertRefused(self.escalate(R["loader"], "pg_database_owner", (True, True, True)), "PF_ESCALATION_PATH")

    def test_a_second_login_superuser_and_a_login_createrole_role_each_refuse(self):
        self.assertRefused(add_roles(clean(), RoleFact("second_su", login=True, superuser=True)), "PF_LOGIN_POWER_ROLE")
        self.assertRefused(add_roles(clean(), RoleFact("cr", login=True, createrole=True)), "PF_LOGIN_POWER_ROLE")

    def test_controls_the_login_superuser_alone_a_nologin_power_role_with_no_member_and_a_login_role_with_no_membership_pass(self):
        self.assertPasses(clean())
        self.assertPasses(add_roles(clean(), RoleFact("ops_admin", createrole=True, superuser=True)))
        self.assertPasses(add_roles(clean(), RoleFact("plain", login=True)))

    def test_there_is_no_exemption_to_add_to(self):
        """The decision takes facts and two names, nothing that names roles to excuse: a pinned signature."""
        import inspect
        self.assertEqual(list(inspect.signature(pf.decide).parameters), ["facts", "vantage", "phase", "real_roles", "real_database"])
        self.assertNotIn("exempt", inspect.getsource(pf).lower().replace("exemption", ""))


class SettingsTests(Base):
    """Rule 7, cases: settings (5.3 (a))."""

    def test_a_non_empty_rolconfig_on_each_real_role_refuses(self):
        for kind in ("executor", "loader", "publisher"):
            changed = tuple(replace(r, config=("session_replication_role=replica",)) if r.name == R[kind] else r for r in clean().roles)
            self.assertRefused(replace(clean(), roles=changed), "PF_ROLE_SETTING")

    def test_a_pg_db_role_setting_row_for_the_real_database_and_one_for_a_real_role_refuse(self):
        self.assertRefused(clean(db_role_settings=(("", pf.REAL_DATABASE),)), "PF_DB_ROLE_SETTING_ROW")
        self.assertRefused(clean(db_role_settings=((R["executor"], ""),)), "PF_DB_ROLE_SETTING_ROW")

    def test_a_row_naming_neither_the_real_roles_nor_the_real_database_passes(self):
        self.assertPasses(clean(db_role_settings=(("", ""),)))                       # ALTER ROLE ALL SET: setrole and setdatabase both 0
        self.assertPasses(clean(db_role_settings=(("some_other_role", "postgres"),)))

    def test_set_or_alter_system_on_session_replication_role_refuses_for_a_real_login_role_another_login_role_and_public(self):
        for who in (R["executor"], R["publisher"], "public"):
            for privilege in ("SET", "ALTER SYSTEM"):
                facts = clean()
                self.assertRefused(replace(facts, parameter_privileges={**facts.parameter_privileges, (who, privilege): True}), "PF_PARAMETER_PRIVILEGE")

    def test_a_missing_parameter_privilege_answer_refuses_as_not_inspected(self):
        """TR6B-L-1 (B23): one (role, privilege) answer that was not read is a refusal, never a pass."""
        facts = clean()
        for key in sorted(facts.parameter_privileges):
            missing = {k: v for k, v in facts.parameter_privileges.items() if k != key}
            decision = self.assertRefused(replace(facts, parameter_privileges=missing), "PF_NOT_INSPECTED")
            self.assertIn(key[0], decision.text)

    def test_another_login_role_that_is_not_one_of_the_four_is_asked_too(self):
        facts = add_roles(clean(), RoleFact("outsider", login=True))
        facts = replace(facts, parameter_privileges={**facts.parameter_privileges, ("outsider", "SET"): True})
        self.assertRefused(facts, "PF_PARAMETER_PRIVILEGE")

    def test_a_replica_session_and_a_tool_that_cannot_read_the_settings_refuse(self):
        self.assertRefused(clean(session_replication_role="replica"), "PF_SESSION_REPLICATION_ROLE")
        self.assertRefused(clean(db_role_settings=None), "PF_NOT_INSPECTED")
        self.assertRefused(clean(parameter_privileges=None), "PF_NOT_INSPECTED")

    def test_none_of_these_passes(self):
        self.assertPasses(clean(db_role_settings=()))


class DatabaseTests(Base):
    """Rule 7, cases: databases (5.3 (c)); the `CONNECT` case."""

    def test_connect_held_by_a_real_role_on_postgres_or_template1_refuses_and_the_installers_revoke_makes_it_pass(self):
        for role in ("executor", "publisher", "loader"):
            for database in ("postgres", "template1"):
                facts = clean()
                self.assertRefused(replace(facts, connect={**facts.connect, (R[role], database): True}), "PF_CONNECT_OUTSIDE_REAL_DATABASE")
        self.assertPasses(clean())                                       # the revoke done: no real role holds CONNECT outside the real database

    def test_template0_is_not_connectable_and_not_asked(self):
        facts = clean()
        self.assertNotIn((R["executor"], "template0"), facts.connect)
        self.assertPasses(facts)

    def test_a_catalog_the_tool_cannot_read_refuses(self):
        self.assertRefused(clean(connect=None), "PF_NOT_INSPECTED")
        self.assertRefused(clean(databases=None), "PF_NOT_INSPECTED")


class AuditCaseTests(Base):
    """Rule 7, cases: the catalog audit, on fake findings. The audit's own behaviour on real catalogs is R3's, and the installer's
    use of it on a TEST install is in `test_postgres_real_preflight`."""

    CASES = {
        "a function of the TEST-only part present": ("RW_AUDIT_TEST_ONLY_PRESENT", "rw_check_fictional"),
        "the executor owning a table": ("RW_AUDIT_OWNS_OBJECT", "portfolio"),
        "EXECUTE on a publisher function granted to the executor": ("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_publish"),
        "the same for the loader": ("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_publish"),
        "EXECUTE on a TEST-only function granted to the executor": ("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_check_fictional"),
        "a privilege on web_saved_sandbox for the executor": ("RW_AUDIT_PRIVILEGE_DIFFERS", "web_saved_sandbox"),
        "the loader with INSERT/UPDATE/DELETE/TRUNCATE/MAINTAIN on the history table": ("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_history"),
        "the executor with MAINTAIN on the drain-mark table": ("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_drain_mark"),
        "the loader with SELECT on md_quote": ("RW_AUDIT_PRIVILEGE_DIFFERS", "md_quote"),
        "a column-level UPDATE grant on an authority table": ("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_head"),
        "the executor with SELECT on an md table": ("RW_AUDIT_PRIVILEGE_DIFFERS", "md_file"),
        "EXECUTE on an md read function granted to public": ("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_md_quote"),
        "public with EXECUTE on a migration trigger function": ("RW_AUDIT_PRIVILEGE_DIFFERS", "md_require_open_release"),
        "a hollowed INSERT-path guard function (FR-L1 (b))": ("RW_AUDIT_GUARD_DEFINITION", "md_release_stamp"),
        # PD-0078: the account role (the fifth) is judged like the other four
        "the account role with an extra privilege on an identity table": ("RW_AUDIT_PRIVILEGE_DIFFERS", "web_identity"),
        "the account role with SELECT on an economic table": ("RW_AUDIT_PRIVILEGE_DIFFERS", "portfolio"),
        "the account role with EXECUTE on a gateway function": ("RW_AUDIT_PRIVILEGE_DIFFERS", "rw_admit"),
        "the account role missing from the catalog": ("RW_AUDIT_ACCOUNT_ROLE", "finweb_real_account"),
    }

    def test_each_finding_becomes_its_own_refusal(self):
        from persistence.real_catalog_audit import Finding
        for label, (code, subject) in self.CASES.items():
            decision = self.assertRefused(clean(audit_findings=(Finding(code, subject, label),)), "PF_CATALOG_AUDIT")
            self.assertIn(code, decision.text, label)

    def test_the_lists_as_the_installer_applies_them_pass(self):
        self.assertPasses(clean(audit_findings=()))

    def test_a_catalog_the_audit_cannot_read_refuses_as_not_inspected(self):
        self.assertRefused(clean(audit_findings=None), "PF_NOT_INSPECTED")
        self.assertRefused(clean(audit_findings=None), "PF_NOT_INSPECTED", phase="check")

    def test_the_audit_runs_in_phase_two_and_check_only(self):
        # Phase 0 (nothing exists yet) never asks for it: no refusal for a missing audit
        facts = clean(audit_findings=None, roles=roles()[:1], escalation={}, connect={}, db_role_settings=(), verifiers={SU: True},
                      parameter_privileges={("public", "SET"): False, ("public", "ALTER SYSTEM"): False},
                      databases=(("postgres", True), ("template1", True), ("template0", False)))
        facts = replace(facts, attempts=tuple(Attempt(*k, CHALLENGED) for k in required_attempts(facts.roles, facts.databases, facts.never_role)))
        self.assertPasses(facts, phase="0")


class StoredCredentialDecisionTests(Base):
    def test_any_pass_s_finding_refuses(self):
        finding = ScanFinding("environment", "PGPASSWORD", "set", "(value not shown)", "set")
        self.assertRefused(clean(stored=(finding,)), "PF_STORED_CREDENTIAL")

    def test_a_file_that_exists_and_cannot_be_read_refuses_as_not_inspected(self):
        self.assertRefused(clean(not_inspected=("passfile (default) /h/.pgpass exists and cannot be read",)), "PF_NOT_INSPECTED")


class AccountsAndFileTests(Base):
    """Rule 7, cases: accounts and file."""

    def test_a_verifier_that_is_md5_or_null_refuses_in_phase_two(self):
        for state in (False, None):
            facts = clean()
            self.assertRefused(replace(facts, verifiers={**facts.verifiers, R["publisher"]: state}), "PF_VERIFIER_NOT_SCRAM")
        self.assertRefused(clean(verifiers=None), "PF_NOT_INSPECTED")

    def test_a_nologin_loader_needs_no_verifier_and_is_not_probed(self):
        rs = roles(loader_login=False)
        databases = clean().databases
        facts = clean(roles=rs, verifiers={r.name: True for r in rs if r.login})
        facts = replace(facts, escalation={k: v for k, v in facts.escalation.items() if k[0] != R["loader"]},
                        attempts=tuple(Attempt(*k, CHALLENGED) for k in required_attempts(rs, databases, facts.never_role)))
        self.assertPasses(facts)

    def test_an_hba_row_that_is_host_md5_or_unlisted_refuses(self):
        self.assertRefused(clean(hba_rows=(HbaRow(1, "host", ("all",), ("all",), "scram-sha-256"),)), "PF_HBA_NOT_LOCAL")
        for method in ("md5", "trust", "peer", "ident", "password", "cert"):
            self.assertRefused(clean(hba_rows=(HbaRow(1, "local", ("all",), ("all",), method), HbaRow(2, "local", ("replication",), ("all",), "scram-sha-256"))),
                               "PF_HBA_METHOD")
        self.assertRefused(clean(hba_rows=(HbaRow(1, "local", ("all",), ("all",), "scram-sha-256", error="syntax"),)), "PF_HBA_ROW_ERROR")
        self.assertRefused(clean(hba_rows=None), "PF_NOT_INSPECTED")

    def test_a_later_trust_row_shadowed_by_a_scram_row_still_refuses(self):
        rows = (HbaRow(1, "local", ("all",), ("all",), "scram-sha-256"), HbaRow(2, "local", ("all",), ("all",), "trust"),
                HbaRow(3, "local", ("replication",), ("all",), "scram-sha-256"))
        self.assertRefused(clean(hba_rows=rows), "PF_HBA_METHOD")

    def test_log_statement_must_be_none_and_the_other_settings_are_checked(self):
        for value in ("ddl", "mod", "all"):
            facts = clean()
            self.assertRefused(replace(facts, settings=dict(facts.settings, log_statement=value)), "PF_LOG_STATEMENT")
        facts = clean()
        self.assertRefused(replace(facts, settings=dict(facts.settings, password_encryption="md5")), "PF_PASSWORD_ENCRYPTION")
        self.assertRefused(clean(settings=None), "PF_NOT_INSPECTED")

    def test_a_data_directory_hba_file_or_socket_directory_under_the_repository_root_or_the_temporary_directory_refuses(self):
        for name, value in (("data_directory", "/Users/owner/Desktop/Fin Web/.local/pg"), ("hba_file", "/tmp/x/pg_hba.conf"),
                            ("ident_file", "/private/tmp/y/pg_ident.conf"), ("unix_socket_directories", "/srv/ok, /tmp/claude-503/sock")):
            facts = clean()
            self.assertRefused(replace(facts, settings={**facts.settings, name: value}), "PF_PATH_UNDER_FORBIDDEN_ROOT")

    def test_kind_and_name_disagreeing_and_no_kind_row(self):
        self.assertEqual(pf.decide_target("finweb_real", ("TEST",)).code, "PF_KIND_NAME_DISAGREE")
        self.assertEqual(pf.decide_target("finweb_dev", ("REAL",)).code, "PF_KIND_NAME_DISAGREE")
        for rows in ((), None, ("REAL", "REAL"), ("TEST", "REAL"), ("BOGUS",)):
            self.assertEqual(pf.decide_target("finweb_real", rows).code, "PF_NO_KIND_ROW", rows)

    def test_a_missing_real_role_refuses_in_phase_two(self):
        rs = tuple(r for r in clean().roles if r.name != R["executor"])
        self.assertRefused(replace(clean(), roles=rs), "PF_REAL_ROLE_MISSING")

    def test_the_account_role_is_judged_like_the_other_four(self):
        """PD-0078 consequence 3: the fifth role is a real role for the gate. Missing at Phase 2, present at Phase 0, a member of another role, or
        without a scram verifier each refuses."""
        facts = clean()
        self.assertEqual(R["account"], "finweb_real_account")
        self.assertIn(R["account"], [r.name for r in facts.roles])
        without = replace(facts, roles=tuple(r for r in facts.roles if r.name != R["account"]))
        decision = self.assertRefused(without, "PF_REAL_ROLE_MISSING")
        self.assertIn(R["account"], [r.subject for r in decision.refusals if r.code == "PF_REAL_ROLE_MISSING"])
        decision = self.assertRefused(facts, "PF_REAL_ALREADY_EXISTS", phase="0")
        self.assertIn(R["account"], [r.subject for r in decision.refusals if r.code == "PF_REAL_ALREADY_EXISTS"])
        member = dict(facts.escalation)
        member[(R["account"], R["executor"])] = (True, False, False)
        self.assertRefused(replace(facts, escalation=member), "PF_ESCALATION_PATH")
        self.assertRefused(replace(facts, verifiers={**facts.verifiers, R["account"]: False}), "PF_VERIFIER_NOT_SCRAM")
        self.assertIn("real role account (%s): can log in: true" % R["account"], self.assertPasses(facts).lines)

    def test_phase_zero_refuses_an_existing_real_database_or_role(self):
        self.assertRefused(clean(), "PF_REAL_ALREADY_EXISTS", phase="0")

    def test_phase_zero_refuses_an_existing_real_role_with_no_real_database(self):
        """TR6B-L-1 (B26): the role refusal on its own, not hidden by the database refusal."""
        facts = clean()
        without_database = replace(facts, databases=tuple((n, a) for n, a in facts.databases if n != pf.REAL_DATABASE))
        decision = self.assertRefused(without_database, "PF_REAL_ALREADY_EXISTS", phase="0")
        self.assertEqual({r.subject for r in decision.refusals if r.code == "PF_REAL_ALREADY_EXISTS"}, set(R.values()))
        bare = replace(without_database, roles=tuple(r for r in without_database.roles if r.name not in R.values()))
        self.assertNotIn("PF_REAL_ALREADY_EXISTS", self.decide(bare, phase="0").codes())

    def test_every_login_role_needs_a_scram_verifier_the_cluster_superuser_included(self):
        """TR6B-L-1 (B27): a superuser (LOGIN) with an md5 or null verifier refuses in Phase 2 and in check. 5.3 (e): every LOGIN role."""
        for state in (False, None):
            facts = clean()
            for phase in ("2", "check"):
                decision = self.assertRefused(replace(facts, verifiers={**facts.verifiers, SU: state}), "PF_VERIFIER_NOT_SCRAM", phase=phase)
                self.assertEqual([r.subject for r in decision.refusals if r.code == "PF_VERIFIER_NOT_SCRAM"], [SU])
        facts = clean()
        self.assertRefused(replace(facts, verifiers={k: v for k, v in facts.verifiers.items() if k != SU}), "PF_VERIFIER_NOT_SCRAM")     # absent = not shown


class LoginStateTests(Base):
    """Rule 7, case: login state (5.3 (g); E29) - a print and never a refusal."""

    def test_the_line_of_each_real_role_carries_its_own_value_and_the_decision_is_the_same(self):
        for loader_login in (False, True):
            rs = roles(loader_login=loader_login)
            facts = clean(roles=rs, verifiers={r.name: True for r in rs if r.login})
            facts = replace(facts, escalation={k: v for k, v in facts.escalation.items() if loader_login or k[0] != R["loader"]},
                            attempts=tuple(Attempt(*k, CHALLENGED) for k in required_attempts(rs, facts.databases, facts.never_role)))
            decision = self.assertPasses(facts)
            lines = {line.split(":")[0]: line for line in decision.lines if line.startswith("real role ")}
            self.assertIn("can log in: %s" % ("true" if loader_login else "false"), lines["real role loader (%s)" % R["loader"]])
            for kind, expected in (("owner", "false"), ("executor", "true"), ("publisher", "true")):
                self.assertIn("can log in: " + expected, lines["real role %s (%s)" % (kind, R[kind])])

    def test_no_decision_rule_keys_on_a_login_state(self):
        import inspect
        source = inspect.getsource(pf.decide) + inspect.getsource(pf._installer_checks)
        self.assertNotIn("rolcanlogin", source)
        # the only use of a role's login state in the judgement is to decide WHICH roles are probed or need a verifier (the LOGIN-keyed checks),
        # never to refuse because a real role can or cannot log in
        self.assertNotRegex(source, r"refuse\([^)]*\.login")


class ByCommandTests(Base):
    """5.1: the same failing facts make `publish` and `renew` refuse and write nothing, and make `withdraw` proceed."""

    FAILING = {
        "trust for the superuser": lambda f: with_attempt(f, SU, "postgres", "A", False, CONNECTED),
        "trust for the publisher": lambda f: with_attempt(f, R["publisher"], "postgres", "B", False, CONNECTED),
        "an error after authentication": lambda f: with_attempt(f, R["executor"], "postgres", "A", False, OTHER, 'database "x" does not exist'),
        "a probe that times out": lambda f: with_attempt(f, R["executor"], "template1", "A", False, OTHER, "timeout"),
        "a missing socket": lambda f: with_attempt(f, R["executor"], "template1", "B", False, OTHER, "No such file or directory"),
        "listen_addresses": lambda f: replace(f, listen_addresses="localhost"),
        "a server below 17": lambda f: replace(f, version_num=160015),
        "prepared transactions": lambda f: replace(f, max_prepared_transactions="4"),
        "a stored credential": lambda f: replace(f, stored=(ScanFinding("environment", "PGPASSWORD", "set", "", ""),)),
        "membership": lambda f: replace(f, escalation={**f.escalation, (R["executor"], "pg_write_all_data"): (True, True, True)}),
        "CONNECT elsewhere": lambda f: replace(f, connect={**f.connect, (R["executor"], "postgres"): True}),
    }

    def test_each_failing_fact_refuses_the_gated_commands_and_never_withdraw(self):
        real = pf.decide_target(pf.REAL_DATABASE, ("REAL",))
        for label, make in self.FAILING.items():
            decision = pf.decide(make(clean()), vantage="runtime")
            self.assertFalse(decision.ok, label)
            for command in ("publish", "renew"):
                plan = pf.command_plan(command, real)
                self.assertTrue(plan.proceed and plan.preflight_before, label)         # proceed only if the preflight passes
            plan = pf.command_plan("withdraw", real)
            self.assertTrue(plan.proceed, label)
            self.assertFalse(plan.preflight_before, label)                              # never gated
            self.assertTrue(plan.preflight_after, label)                                # the result is printed beside the withdrawal's own

    def test_the_table_of_5_2_by_command(self):
        cases = {
            ("finweb_real", ("REAL",)): ("REAL", {"publish": (True, True, False), "renew": (True, True, False), "withdraw": (True, False, True), "status": (True, False, False)}),
            ("finweb_dev", ("TEST",)): ("TEST", {"publish": (True, False, False), "renew": (True, False, False), "withdraw": (True, False, False)}),
            ("finweb_real", ("TEST",)): ("REFUSE", {"publish": (False, False, False), "renew": (False, False, False), "withdraw": (True, False, False)}),
            ("finweb_dev", ("REAL",)): ("REFUSE", {"publish": (False, False, False), "renew": (False, False, False), "withdraw": (True, False, False)}),
            ("finweb_real", ()): ("REFUSE", {"publish": (False, False, False), "renew": (False, False, False), "withdraw": (False, False, False)}),
            ("finweb_real", None): ("REFUSE", {"publish": (False, False, False), "renew": (False, False, False), "withdraw": (False, False, False)}),
            ("finweb_dev", ("TEST", "TEST")): ("REFUSE", {"publish": (False, False, False), "renew": (False, False, False), "withdraw": (False, False, False)}),
        }
        for (database, rows), (decision, commands) in cases.items():
            target = pf.decide_target(database, rows)
            self.assertEqual(target.decision, decision, (database, rows))
            for command, (proceed, before, after) in commands.items():
                plan = pf.command_plan(command, target)
                self.assertEqual((plan.proceed, plan.preflight_before, plan.preflight_after), (proceed, before, after), (database, rows, command))

    def test_a_refusal_of_a_gated_command_names_the_code_and_a_withdrawal_with_no_kind_row_says_there_is_nothing_to_withdraw_from(self):
        self.assertEqual(pf.command_plan("publish", pf.decide_target("finweb_real", ("TEST",))).code, "PF_KIND_NAME_DISAGREE")
        self.assertEqual(pf.command_plan("withdraw", pf.decide_target("finweb_real", ())).code, "PF_NO_KIND_ROW")


class ClassifierTests(unittest.TestCase):
    """5.3 (f). The texts are libpq's and the server's; the opt-in calibration test checks them against a real scram-only server."""

    def test_classes(self):
        prefix = 'connection to server on socket "/s/.s.PGSQL.5432" failed: '
        cases = (
            (CHALLENGED, prefix + "fe_sendauth: no password supplied"),
            (CHALLENGED, prefix + 'FATAL:  password authentication failed for user "u"'),
            (REJECTED, prefix + 'FATAL:  pg_hba.conf rejects connection for host "[local]", user "u", database "d", no encryption'),
            (REJECTED, prefix + 'FATAL:  no pg_hba.conf entry for host "[local]", user "u", database "d", no encryption'),
            (REJECTED, prefix + 'FATAL:  no pg_hba.conf entry for replication connection from host "[local]", user "u", no encryption'),
            (REJECTED, prefix + 'FATAL:  pg_hba.conf rejects replication connection for host "[local]", user "u", no encryption'),
            (OTHER, prefix + 'FATAL:  database "d" does not exist'),
            (OTHER, prefix + 'FATAL:  role "u" does not exist'),
            (OTHER, prefix + "No such file or directory"),
            (OTHER, prefix + 'FATAL:  the database system is starting up'),
            # TR6B-L-1 (B25): a message that merely mentions pg_hba is not a rejection
            (OTHER, prefix + "FATAL:  could not load pg_hba.conf"),
            (OTHER, prefix + 'FATAL:  pg_hba.conf is invalid'),
            (OTHER, prefix + 'FATAL:  could not open file "pg_hba.conf": Permission denied'),
            (OTHER, prefix + 'authentication method requirement "scram-sha-256" failed: server did not complete authentication'),
            (OTHER, "timeout"),
            (OTHER, ""),
            (OTHER, "child error: unreadable result"),
        )
        for expected, message in cases:
            self.assertEqual(pf.classify_attempt(False, message), expected, message)
        self.assertEqual(pf.classify_attempt(True, ""), CONNECTED)
        self.assertEqual(pf.classify_attempt(True, "password authentication failed"), CONNECTED)        # a connection that opened is CONNECTED

    def test_the_tools_own_connection_error_has_its_own_code(self):
        self.assertEqual(pf.classify_own_connection_error('authentication method requirement "scram-sha-256" failed: server did not complete authentication'),
                         "PF_REQUIRE_AUTH")
        self.assertEqual(pf.classify_own_connection_error("could not connect"), "PF_CONNECT_FAILED")


class HbaPredictionTests(unittest.TestCase):
    def test_prediction(self):
        rows = (HbaRow(1, "host", ("all",), ("all",), "trust"), HbaRow(2, "local", ("sameuser",), ("alice",), "reject"),
                HbaRow(3, "local", ("all",), ("all",), "scram-sha-256"))
        self.assertEqual(pf.predict_hba(rows, "alice", "alice", False), "reject")
        self.assertEqual(pf.predict_hba(rows, "alice", "other", False), "scram-sha-256")
        self.assertEqual(pf.predict_hba(rows, "alice", "other", True), "no-match")           # `all` does not match a replication connection
        self.assertEqual(pf.predict_hba((HbaRow(1, "local", ("@file",), ("all",), "scram-sha-256"),), "a", "b", False), "unpredictable")

    def test_regular_expression_and_group_tokens_cannot_be_predicted(self):
        """TR6B-L-3: PostgreSQL 16+ regular expressions (`/...`) and samerole / samegroup are not evaluated; the row makes the prediction impossible."""
        for databases, users in ((("all",), ("/^finweb_real",)), (("/^db",), ("all",)), (("samerole",), ("all",)), (("samegroup",), ("all",)),
                                 (("all",), ("+group",)), (("all",), ("@users",))):
            rows = (HbaRow(1, "local", databases, users, "reject"), HbaRow(2, "local", ("all",), ("all",), "scram-sha-256"))
            self.assertEqual(pf.predict_hba(rows, "a", "b", False), "unpredictable", (databases, users))
        plain = (HbaRow(1, "local", ("sameuser",), ("a",), "reject"), HbaRow(2, "local", ("all",), ("all",), "scram-sha-256"))
        self.assertEqual(pf.predict_hba(plain, "a", "b", False), "scram-sha-256")

    def test_a_regular_expression_row_in_the_file_makes_the_installer_refuse_an_attempt_as_unpredictable(self):
        facts = clean(hba_rows=(HbaRow(1, "local", ("all",), ("/^finweb_real",), "reject"), HbaRow(2, "local", ("all",), ("all",), "scram-sha-256"),
                                HbaRow(3, "local", ("replication",), ("all",), "scram-sha-256")))
        decision = pf.decide(facts, vantage="installer", phase="2")
        self.assertIn("PF_HBA_FILE_LOADED_DIFFER", decision.codes())
        self.assertIn("unpredictable", decision.text)


class PassSTests(unittest.TestCase):
    """5.3 (d) Pass S, over files under a temporary HOME. No connection is made."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name, "home")
        self.home.mkdir()
        self.addCleanup(self.tmp.cleanup)
        self.etc_empty = Path(self.tmp.name, "etc_empty")
        self.etc_empty.mkdir()
        self.login = {R["publisher"], R["executor"], SU}

    def scan(self, environ=None, **kw):
        # hermetic: a known empty installation etc directory, and none of the libpq compiled defaults of the machine running the test
        kw.setdefault("sysconfdir", str(self.etc_empty))
        kw.setdefault("compiled_sysconfdirs", ())
        findings, missing, notes = pf.scan_stored_credentials(environ or {}, self.home, socket_dir=SOCKET_DIR, port=PORT, login_roles=self.login, **kw)
        for f in findings:
            self.assertNotIn(SENTINEL, f.short())
        return findings, missing, notes

    def pgpass(self, text, mode=0o600, name=".pgpass"):
        path = self.home / name
        path.write_text(text)
        path.chmod(mode)
        return path

    def test_pgpassword_set_to_a_right_value_a_wrong_value_and_the_empty_string_each_refuses(self):
        for value in (SENTINEL, "wrong", ""):
            findings, _m, _n = self.scan({"PGPASSWORD": value})
            self.assertEqual([f.store for f in findings], ["environment"])
            self.assertNotIn(value or "\0", " ".join(f.short() for f in findings) if value else "")
        self.assertEqual(self.scan({})[0], ())

    def test_a_0644_passfile_with_an_entry_for_the_socket_directory_and_port_refuses_though_libpq_would_ignore_it(self):
        self.pgpass("%s:%s:*:somebody:%s\n" % (SOCKET_DIR, PORT, SENTINEL), mode=0o644)
        findings, _m, _n = self.scan()
        self.assertEqual(len(findings), 1)
        self.assertIn("line 1", findings[0].where)

    def test_the_same_at_0600_refuses(self):
        self.pgpass("%s:%s:*:somebody:%s\n" % (SOCKET_DIR, PORT, SENTINEL))
        self.assertEqual(len(self.scan()[0]), 1)

    def test_host_star_and_port_star_refuses_and_localhost_too(self):
        self.pgpass("*:*:*:*:%s\nlocalhost:%s:db:u:%s\n" % (SENTINEL, PORT, SENTINEL))
        self.assertEqual(len(self.scan()[0]), 2)

    def test_an_entry_for_another_host_or_port_passes(self):
        self.pgpass("db.example.com:5432:*:someone:%s\n%s:9999:*:someone:%s\n# comment\n\n" % (SENTINEL, SOCKET_DIR, SENTINEL))
        self.assertEqual(self.scan()[0], ())

    def test_a_star_username_with_an_unrelated_host_passes(self):
        self.pgpass("db.example.com:5432:*:*:%s\n" % SENTINEL)
        self.assertEqual(self.scan()[0], ())

    def test_a_line_naming_a_real_login_role_refuses_whatever_its_host_and_port(self):
        self.pgpass("127.0.0.1:5433:finweb_real:%s:%s\n" % (R["publisher"], SENTINEL))
        findings, _m, _n = self.scan()
        self.assertEqual(len(findings), 1)
        self.assertIn("LOGIN role", findings[0].reason)

    def test_an_entry_in_the_default_pgpass_while_pgpassfile_names_another_file_refuses(self):
        self.pgpass("%s:%s:*:somebody:%s\n" % (SOCKET_DIR, PORT, SENTINEL))
        other = self.pgpass("db.example.com:5432:*:x:y\n", name=".pgpass_dev")
        findings, _m, _n = self.scan({"PGPASSFILE": str(other)})
        self.assertEqual(len(findings), 1)
        self.assertIn(".pgpass", findings[0].file)

    def test_escaped_colons_in_the_fields_are_honoured(self):
        self.pgpass("%s:%s:db\\:name:user\\:x:%s\n" % (SOCKET_DIR, PORT, SENTINEL))
        findings, _m, _n = self.scan()
        self.assertEqual(len(findings), 1)
        self.assertIn("db:name", findings[0].fields)

    def test_a_service_file_with_a_password_section_that_no_service_names_refuses(self):
        self.pgpass("", name=".none")
        (self.home / ".pg_service.conf").write_text("[unused]\nhost=%s\nport=%s\nuser=somebody\npassword=%s\n" % (SOCKET_DIR, PORT, SENTINEL))
        findings, _m, _n = self.scan()
        self.assertEqual(len(findings), 1)
        self.assertIn("[unused]", findings[0].where)
        (self.home / ".pg_service.conf").write_text("[unused]\npassword=%s\n" % SENTINEL)           # host and port absent: they fall back to the defaults
        self.assertEqual(len(self.scan()[0]), 1)

    def test_a_service_section_whose_user_names_a_real_role_refuses_with_a_host_elsewhere(self):
        (self.home / ".pg_service.conf").write_text("[x]\nhost=db.example.com\nport=5432\nuser=%s\npassword=%s\n" % (R["publisher"], SENTINEL))
        self.assertEqual(len(self.scan()[0]), 1)

    def test_a_service_file_whose_sections_hold_no_password_passes(self):
        (self.home / ".pg_service.conf").write_text("[x]\nhost=%s\nport=%s\nuser=somebody\n" % (SOCKET_DIR, PORT))
        self.assertEqual(self.scan()[0], ())

    def test_a_service_password_for_another_cluster_passes(self):
        (self.home / ".pg_service.conf").write_text("[x]\nhost=db.example.com\nport=5432\nuser=somebody\npassword=%s\n" % SENTINEL)
        self.assertEqual(self.scan()[0], ())

    def test_a_section_whose_passfile_leads_to_such_an_entry_refuses(self):
        target = self.pgpass("%s:%s:*:somebody:%s\n" % (SOCKET_DIR, PORT, SENTINEL), name="elsewhere_passfile")
        (self.home / ".pg_service.conf").write_text("[x]\nhost=db.example.com\npassfile=%s\n" % target)
        findings, _m, _n = self.scan()
        self.assertEqual(len(findings), 1)
        self.assertIn("service x", findings[0].store)

    def test_the_named_service_file_and_the_sysconfdir_ones_are_scanned_too(self):
        named = Path(self.tmp.name, "svc.conf")
        named.write_text("[a]\nhost=%s\npassword=%s\n" % (SOCKET_DIR, SENTINEL))
        self.assertEqual(len(self.scan({"PGSERVICEFILE": str(named)})[0]), 1)
        etc = Path(self.tmp.name, "etc")
        etc.mkdir()
        (etc / "pg_service.conf").write_text("[b]\npassword=%s\n" % SENTINEL)
        self.assertEqual(len(self.scan({"PGSYSCONFDIR": str(etc)})[0]), 1)
        self.assertEqual(len(self.scan(sysconfdir=str(etc))[0]), 1)

    def test_a_file_that_exists_and_cannot_be_read_is_not_inspected(self):
        path = self.pgpass("x:y:z:u:p\n")
        with mock.patch.object(Path, "read_text", side_effect=PermissionError("no")):
            findings, missing, _n = self.scan()
        self.assertTrue(any(str(path) in m for m in missing), missing)
        decision = pf.decide(clean(not_inspected=missing), vantage="installer", phase="2")
        self.assertIn("PF_NOT_INSPECTED", decision.codes())

    def test_an_installation_etc_directory_that_cannot_be_determined_is_not_inspected_and_refuses(self):
        """TR6B-M-1: `pg_config` missing or failing is a REFUSAL (not a note), because the scan cannot say it covered the directory."""
        findings, missing, _notes = self.scan(sysconfdir=None)
        self.assertEqual(findings, ())
        self.assertTrue(any("pg_config --sysconfdir" in m for m in missing), missing)
        decision = pf.decide(clean(not_inspected=missing), vantage="runtime")
        self.assertIn("PF_NOT_INSPECTED", decision.codes())
        self.assertEqual(self.scan()[1], ())                              # with a determined (empty) directory: nothing missing

    def test_pg_config_missing_or_failing_gives_none_and_a_failing_one_too(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("pg_config")):
            self.assertIsNone(pf.installation_sysconfdir())
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=1, stdout="")):
            self.assertIsNone(pf.installation_sysconfdir())
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0, stdout="/opt/x/etc\n")):
            self.assertEqual(pf.installation_sysconfdir(), "/opt/x/etc")

    def test_the_bundled_libpqs_compiled_default_directory_is_scanned(self):
        """TR6B-M-1: psycopg-binary's libpq looks in /etc/postgresql-common, which `pg_config` does not name."""
        self.assertIn("/etc/postgresql-common", pf.LIBPQ_COMPILED_SYSCONFDIRS)
        compiled = Path(self.tmp.name, "postgresql-common")
        compiled.mkdir()
        (compiled / "pg_service.conf").write_text("[real]\nhost=%s\nport=%s\npassword=%s\n" % (SOCKET_DIR, PORT, SENTINEL))
        findings, missing, _n = self.scan(compiled_sysconfdirs=(str(compiled),))
        self.assertEqual((len(findings), missing), (1, ()))
        self.assertIn("libpq compiled default", findings[0].store)
        (compiled / "pg_service.conf").write_text("[real]\npassword=%s\n" % SENTINEL)                    # host and port absent, no user
        self.assertEqual(len(self.scan(compiled_sysconfdirs=(str(compiled),))[0]), 1)
        self.assertEqual(self.scan()[0], ())                                                              # not scanned when not listed

    def test_each_service_file_location_is_scanned_on_its_own(self):
        """PGSYSCONFDIR, pg_config's directory, the compiled default, PGSERVICEFILE and ~/.pg_service.conf: each alone refuses."""
        body = "[real]\nhost=%s\nport=%s\npassword=%s\n" % (SOCKET_DIR, PORT, SENTINEL)
        for label in ("PGSYSCONFDIR", "pg_config", "compiled", "PGSERVICEFILE", "home"):
            where = Path(self.tmp.name, "loc_" + label)
            where.mkdir()
            environ, kw = {}, {}
            if label == "PGSERVICEFILE":
                (where / "named.conf").write_text(body)
                environ = {"PGSERVICEFILE": str(where / "named.conf")}
            elif label == "home":
                (self.home / ".pg_service.conf").write_text(body)
            else:
                (where / "pg_service.conf").write_text(body)
                if label == "PGSYSCONFDIR":
                    environ = {"PGSYSCONFDIR": str(where)}
                elif label == "pg_config":
                    kw = {"sysconfdir": str(where)}
                else:
                    kw = {"compiled_sysconfdirs": (str(where),)}
            self.assertEqual(len(self.scan(environ, **kw)[0]), 1, label)
            (self.home / ".pg_service.conf").unlink(missing_ok=True)

    def test_a_service_file_in_a_scanned_directory_that_cannot_be_read_is_not_inspected(self):
        compiled = Path(self.tmp.name, "postgresql-common")
        compiled.mkdir()
        path = compiled / "pg_service.conf"
        path.write_text("[x]\npassword=p\n")
        with mock.patch.object(Path, "read_text", side_effect=PermissionError("no")):
            _f, missing, _n = self.scan(compiled_sysconfdirs=(str(compiled),))
        self.assertTrue(any(str(path) in m for m in missing), missing)

    def test_a_passfile_host_spelled_with_a_trailing_slash_or_through_a_symlink_still_matches(self):
        """TR6B-L-4: compared by real path."""
        real = Path(self.tmp.name, "realsocket")
        real.mkdir()
        link = Path(self.tmp.name, "linksocket")
        link.symlink_to(real)

        def scan_for(host_in_file):
            self.pgpass("%s:%s:*:*:%s\n" % (host_in_file, PORT, SENTINEL))
            return pf.scan_stored_credentials({}, self.home, socket_dir=str(real), port=PORT, login_roles=self.login, sysconfdir=str(self.etc_empty),
                                              compiled_sysconfdirs=())[0]
        for spelling in (str(real), str(real) + "/", str(real) + "//", str(real) + "/.", str(link), str(link) + "/"):
            self.assertEqual(len(scan_for(spelling)), 1, spelling)
        self.assertEqual(scan_for(str(real) + "_other"), ())
        (self.home / ".pg_service.conf").write_text("[x]\nhost=%s/\nport=%s\npassword=%s\n" % (real, PORT, SENTINEL))
        self.pgpass("")
        self.assertEqual(len(pf.scan_stored_credentials({}, self.home, socket_dir=str(real), port=PORT, login_roles=self.login,
                                                         sysconfdir=str(self.etc_empty), compiled_sysconfdirs=())[0]), 1)

    def test_the_scan_makes_no_connection_and_prints_no_password(self):
        self.pgpass("%s:%s:*:somebody:%s\n" % (SOCKET_DIR, PORT, SENTINEL))
        with mock.patch("subprocess.run", side_effect=AssertionError("the scan spawned a process")):
            findings, _m, _n = self.scan()
        self.assertEqual(len(findings), 1)
        self.assertNotIn(SENTINEL, repr(findings))


class ProberLogicTests(unittest.TestCase):
    """5.3 (d): the probe's wiring, with a fake child. The real child is exercised against the development cluster (refusal side) in
    `test_postgres_real_preflight` and against a scram-only server by the opt-in calibration."""

    def test_pass_a_is_scrubbed_and_pass_b_uses_the_callers_environment(self):
        seen = []

        def spawn(conninfo, env, timeout):
            seen.append((conninfo, env))
            return False, "fe_sendauth: no password supplied"
        prober = pf.Prober(SOCKET_DIR, PORT, environ={"PGPASSFILE": "/home/u/.pgpass_dev", "HOME": "/home/u", "FOO": "bar"}, spawn=spawn)
        self.addCleanup(prober.close)
        a = prober.attempt("someone", "postgres", "A", False)
        b = prober.attempt("someone", "postgres", "B", False)
        self.assertEqual((a.outcome, b.outcome), (CHALLENGED, CHALLENGED))
        (a_info, a_env), (b_info, b_env) = seen
        self.assertIn("passfile='/dev/null'", a_info)
        self.assertNotIn("FOO", a_env)
        self.assertNotEqual(a_env["HOME"], "/home/u")
        self.assertEqual(b_env["HOME"], "/home/u")
        self.assertEqual(b_env["FOO"], "bar")
        self.assertNotIn("passfile", b_info)
        for info in (a_info, b_info):
            self.assertNotIn("password=", info)
            self.assertIn("host='%s'" % SOCKET_DIR, info)
            self.assertIn("connect_timeout='3'", info)

    def test_a_replication_attempt_asks_for_a_replication_connection(self):
        seen = []
        prober = pf.Prober(SOCKET_DIR, PORT, environ={}, spawn=lambda c, e, t: (seen.append(c), (False, 'no pg_hba.conf entry for replication connection from host "[local]", user "u"'))[1])
        self.addCleanup(prober.close)
        attempt = prober.attempt(SU, "replication", "A", True)
        self.assertEqual(attempt.outcome, REJECTED)
        self.assertIn("replication='true'", seen[0])

    def test_the_child_sends_no_statement(self):
        self.assertNotIn("execute", pf._CHILD)
        self.assertNotIn("cursor", pf._CHILD)
        self.assertNotIn("password", pf._CHILD.lower())

    def test_a_child_that_times_out_or_gives_no_answer_is_other(self):
        import subprocess
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertEqual(pf._spawn_child("host=x", {}, 1), (False, "timeout"))
        with mock.patch("subprocess.run", return_value=types.SimpleNamespace(stdout="", stderr="", returncode=1)):
            connected, message = pf._spawn_child("host=x", {}, 1)
        self.assertEqual(pf.classify_attempt(connected, message), OTHER)

    def test_the_required_attempts_cover_every_login_role_the_never_created_name_and_each_connectable_database_in_both_passes(self):
        rs, databases = roles(), clean().databases
        keys = required_attempts(rs, databases, "never")
        for probe_pass in ("A", "B"):
            for name in (SU, R["executor"], R["loader"], R["publisher"], "never"):
                for database in ("postgres", "template1", pf.REAL_DATABASE):
                    self.assertIn((name, database, probe_pass, False), keys)
            self.assertIn((SU, "replication", probe_pass, True), keys)
            self.assertNotIn((R["executor"], "replication", probe_pass, True), keys)
            self.assertNotIn((R["owner"], "postgres", probe_pass, False), keys)               # NOLOGIN
        self.assertFalse([k for k in keys if k[1] == "template0"])


class GateOnFactsTests(unittest.TestCase):
    def test_an_exception_while_gathering_is_a_refusal_never_a_pass(self):
        with mock.patch.object(pf, "gather_facts", side_effect=RuntimeError("boom")):
            decision = pf.run_runtime_gate(object(), database="finweb_real", socket="/a/.s.PGSQL.1")
        self.assertFalse(decision.ok)
        self.assertEqual(decision.codes(), ("PF_NOT_INSPECTED",))

    def test_a_server_below_17_stops_the_reads_after_the_version(self):
        calls = []

        class Conn:
            def transaction(self):
                return types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda *a: False)

            def execute(self, sql, params=()):
                calls.append(sql)
                return types.SimpleNamespace(fetchone=lambda: ("160015",), fetchall=lambda: [])

        class Tx:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        conn = Conn()
        conn.transaction = lambda: Tx()
        facts = pf.gather_facts(conn, vantage="runtime", database="d", socket="/a/.s.PGSQL.1", environ={}, home="/nonexistent", run_probe=False)
        self.assertEqual(facts.version_num, 160015)
        self.assertEqual(len(calls), 1)
        self.assertEqual(pf.decide(facts, vantage="runtime").codes(), ("PF_SERVER_VERSION_BELOW_17",))


class SysconfdirFallbackTests(unittest.TestCase):
    """TR6B-R-2 (R7). The tools that gather facts ask `pg_config --sysconfdir` for the installation's etc directory when the caller names none
    (`pf.installation_sysconfdir()`): `run_runtime_gate` (the launcher, the probe and the publisher's gate) and `real_install.run_checks`. Nothing
    pinned that fallback: dropping it left every PostgreSQL-free test green and would have refused every Phase 0 at R8 step 1. These tests give the
    fallback a directory that holds a service file with a password and require `PF_STORED_CREDENTIAL`, which only a scan of THAT directory produces.
    The connection is a fake that answers the version and fails every other read, so every other group is "not inspected" and the scan still runs."""

    class Conn:
        def transaction(self):
            conn = self

            class Tx:
                def __enter__(self):
                    return conn

                def __exit__(self, *a):
                    return False
            return Tx()

        def execute(self, sql, params=()):
            if "server_version_num" in sql:
                return types.SimpleNamespace(fetchone=lambda: ("170011",), fetchall=lambda: [])
            raise RuntimeError("not answered")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.etc = Path(self.tmp.name, "etc")
        self.etc.mkdir()
        (self.etc / "pg_service.conf").write_text("[real]\nhost=%s\nport=%s\npassword=%s\n" % (SOCKET_DIR, PORT, SENTINEL))
        self.home = Path(self.tmp.name, "home")
        self.home.mkdir()

    def test_the_runtime_gate_scans_the_directory_pg_config_names_when_the_caller_names_none(self):
        with mock.patch.object(pf, "installation_sysconfdir", return_value=str(self.etc)) as asked:
            decision = pf.run_runtime_gate(self.Conn(), database=pf.REAL_DATABASE, socket=SOCKET_DIR + "/.s.PGSQL." + PORT, environ={}, home=str(self.home))
        asked.assert_called_once_with()
        self.assertFalse(decision.ok)
        self.assertIn("PF_STORED_CREDENTIAL", decision.codes())
        self.assertNotIn(SENTINEL, decision.text)

    def test_the_installers_checks_scan_the_same_directory(self):
        from persistence import real_install
        lines = []
        with mock.patch.object(pf, "installation_sysconfdir", return_value=str(self.etc)) as asked:
            decision = real_install.run_checks(self.Conn(), SOCKET_DIR + "/.s.PGSQL." + PORT, phase="check", say=lines.append, environ={}, home=str(self.home))
        asked.assert_called_once_with()
        self.assertFalse(decision.ok)
        self.assertIn("PF_STORED_CREDENTIAL", decision.codes())
        self.assertNotIn(SENTINEL, "\n".join(lines))

    def test_a_directory_the_caller_names_wins_and_the_fallback_is_not_asked(self):
        """The fallback is a default, not an override: with a directory named, `pg_config` is not consulted."""
        with mock.patch.object(pf, "installation_sysconfdir", side_effect=AssertionError("asked")):
            decision = pf.run_runtime_gate(self.Conn(), database=pf.REAL_DATABASE, socket=SOCKET_DIR + "/.s.PGSQL." + PORT, environ={},
                                           home=str(self.home), sysconfdir=str(self.etc))
        self.assertIn("PF_STORED_CREDENTIAL", decision.codes())

    def test_with_no_directory_determined_the_gate_refuses_as_not_inspected(self):
        with mock.patch.object(pf, "installation_sysconfdir", return_value=None):
            decision = pf.run_runtime_gate(self.Conn(), database=pf.REAL_DATABASE, socket=SOCKET_DIR + "/.s.PGSQL." + PORT, environ={}, home=str(self.home))
        self.assertFalse(decision.ok)
        self.assertNotIn("PF_STORED_CREDENTIAL", decision.codes())
        self.assertIn("PF_NOT_INSPECTED", decision.codes())


class NameTripwireTests(unittest.TestCase):
    """Rule 6: the name-level refusal in `connection.missing_env_vars`, and the cluster refusal in `Provisioner.preflight`."""

    ENV = {"FINWEB_PG_INTEGRATION": "1", "FINWEB_PG_SOCKET": "/tmp/.s.PGSQL.5432", "FINWEB_PG_DATABASE": "finweb_dev", "FINWEB_PG_USER": "u"}

    def test_a_database_name_in_the_reserved_namespace_is_reported_as_not_usable(self):
        self.assertEqual(connection.missing_env_vars(self.ENV), [])
        for name in ("finweb_real", "finweb_real_main", "finweb_realistic"):
            missing = connection.missing_env_vars(dict(self.ENV, FINWEB_PG_DATABASE=name))
            self.assertEqual(len(missing), 1, name)
            self.assertIn("reserved real-install namespace", missing[0])
        self.assertEqual(connection.missing_env_vars(dict(self.ENV, FINWEB_PG_DATABASE="finweb_it_rw_ab")), [])
        self.assertEqual(connection.missing_env_vars(dict(self.ENV, FINWEB_PG_DATABASE="postgres")), [])        # the stated residual: another name passes the tripwire

    def test_the_name_refusal_builds_no_connection(self):
        with mock.patch.object(connection, "connect", side_effect=AssertionError("connected")), mock.patch.object(connection, "build_conninfo", side_effect=AssertionError("built")):
            connection.missing_env_vars(dict(self.ENV, FINWEB_PG_DATABASE="finweb_real"))

    def test_the_provisioner_refuses_a_cluster_holding_a_reserved_database(self):
        from guarded_pg_provision import Provisioner
        Provisioner.refuse_real_cluster(["postgres", "template1", "finweb_dev", "finweb_it_rw_ab12"])
        for names in (["postgres", "finweb_real"], ["finweb_real_x"]):
            with self.assertRaises(RuntimeError) as caught:
                Provisioner.refuse_real_cluster(names)
            self.assertIn("reserved real-install namespace", str(caught.exception))

    def test_provisioner_preflight_runs_the_refusal_after_its_own_checks(self):
        from guarded_pg_provision import Provisioner

        class Cursor:
            def __init__(self, rows):
                self.rows = rows

            def fetchone(self):
                return self.rows[0]

            def fetchall(self):
                return self.rows

        class Conn:
            def __init__(self, names):
                self.names = names

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=()):
                if "pg_database" in sql:
                    return Cursor([(n,) for n in self.names])
                return Cursor([("finweb_dev", "admin", True, True, True)])
        for names, refused in ((["postgres", "finweb_dev"], False), (["postgres", "finweb_real"], True)):
            prov = Provisioner("/tmp/.s.PGSQL.5432", "finweb_dev", "admin", "finweb_it_x")
            prov.admin = lambda database, names=names: Conn(names)
            if refused:
                with self.assertRaises(RuntimeError) as caught:
                    prov.preflight()
                self.assertIn("reserved real-install namespace", str(caught.exception))
            else:
                prov.preflight()

    def test_the_test_provisioner_writes_no_kind_row_and_the_installer_writes_real_only(self):
        text = (HERE / "guarded_pg_provision.py").read_text("utf8")
        self.assertNotIn("rw_install", text)
        self.assertNotIn("'REAL'", text)


class PromptTests(unittest.TestCase):
    def test_the_prompt_is_the_one_credential_route_and_reads_no_environment(self):
        captured = {}

        def fake_connect(conninfo, autocommit=False):
            captured["conninfo"] = conninfo
            return object()
        import psycopg
        asked = []
        with mock.patch.object(psycopg, "connect", fake_connect):
            pf.connect_with_prompt("/a/.s.PGSQL.5432", "finweb_real", "u", require_auth="scram-sha-256", prompt=lambda role: (asked.append(role), SENTINEL)[1])
        self.assertEqual(asked, ["u"])
        self.assertIn("require_auth='scram-sha-256'", captured["conninfo"])
        self.assertIn("passfile='/dev/null'", captured["conninfo"])
        with mock.patch.object(psycopg, "connect", fake_connect):
            pf.connect_with_prompt("/a/.s.PGSQL.5432", "finweb_real", "u", require_auth=None, prompt=lambda role: "x")
        self.assertNotIn("require_auth", captured["conninfo"])

    def test_withdraw_connects_under_its_own_constant(self):
        self.assertEqual(pf.WITHDRAW_REQUIRE_AUTH, "!password")   # PD-0076 choice E: refuse only a request for a cleartext password
        self.assertEqual(pf.GATED_REQUIRE_AUTH, "scram-sha-256")
        seen = []

        def fake(socket, database, user, *, require_auth, prompt, autocommit=False):
            seen.append(require_auth)
            return object()

        def connect_as(command):
            args = types.SimpleNamespace(command=command, socket="/a/.s.PGSQL.5432", database="finweb_real", user="u")
            with mock.patch.object(pf, "connect_with_prompt", fake):
                store._default_connect(lambda role: "x")(args)
        for command, expected in (("publish", "scram-sha-256"), ("renew", "scram-sha-256"), ("withdraw", "!password"), ("status", "scram-sha-256")):
            seen.clear()
            connect_as(command)
            self.assertEqual(seen, [expected], command)
        for preference in ("scram-sha-256", "!password", None):          # the constant is the only thing that moves withdraw's demand
            seen.clear()
            with mock.patch.object(pf, "WITHDRAW_REQUIRE_AUTH", preference):
                connect_as("withdraw")
            self.assertEqual(seen, [preference])

    def test_the_connection_parameters_of_each_command_carry_the_require_auth_of_pd_0076(self):
        """PD-0076 choice E: the connection string that reaches libpq has `require_auth=!password` for withdraw and `scram-sha-256` for publish, renew
        and status, in the reserved namespace; a TEST-named database carries none. The real `connect_with_prompt` runs; only `psycopg.connect` is faked."""
        import psycopg
        captured = []

        def fake_connect(conninfo, autocommit=False):
            captured.append(conninfo)
            return object()
        for command, expected in (("publish", "scram-sha-256"), ("renew", "scram-sha-256"), ("withdraw", "!password"), ("status", "scram-sha-256")):
            args = types.SimpleNamespace(command=command, socket="/a/.s.PGSQL.5432", database="finweb_real", user="u")
            captured.clear()
            with mock.patch.object(psycopg, "connect", fake_connect):
                store._default_connect(lambda role: SENTINEL)(args)
            self.assertEqual(len(captured), 1, command)
            self.assertIn("require_auth='%s'" % expected, captured[0], command)
            self.assertIn("passfile='/dev/null'", captured[0], command)
            self.assertEqual(captured[0].count("require_auth="), 1, command)
        args = types.SimpleNamespace(command="withdraw", socket="/a/.s.PGSQL.5432", database="finweb_dev", user="u")
        captured.clear()
        with mock.patch.object(psycopg, "connect", fake_connect):
            store._default_connect(lambda role: self.fail("a prompt for a TEST database"))(args)
        self.assertNotIn("require_auth", captured[0])

    def test_withdraw_stays_ungated_whatever_its_connection_demands(self):
        """Only withdraw's OWN connection changed (PD-0076 E): the command plan still never runs the preflight before it."""
        for decision in ("REAL", "TEST"):
            plan = pf.command_plan("withdraw", pf.Target(decision))
            self.assertTrue(plan.proceed)
            self.assertFalse(plan.preflight_before)
        self.assertEqual(pf.NEVER_GATED_COMMANDS, ("withdraw",))

    def test_the_withdrawals_own_result_is_printed_and_its_status_fixed_before_the_post_withdrawal_preflight_and_an_interrupt_changes_neither(self):
        """TR6B-L-2 (5.1, withdraw row): Ctrl-C (KeyboardInterrupt), SystemExit, a timeout or any error in the post-withdrawal preflight."""
        done = store.CommandResult(0, "WITHDRAWN", ("withdrawn: all four rights are off",), {})
        pending = store.CommandResult(store.EXIT_NOT_YET_EFFECTIVE, "NOT_YET_EFFECTIVE", ("not yet effective",), {})
        argv = ["--socket", "/a/.s.PGSQL.5432", "--database", "finweb_real", "--user", "u", "--schema", "finweb", "withdraw", "--context", "c",
                "--generation", "1", "--actor", "a", "--pd", "PD-9001", "--commit", "a" * 40, "--sha", "b" * 64]
        for outcome in (done, pending):
            for failure in (KeyboardInterrupt(), SystemExit(9), TimeoutError("slow"), RuntimeError("x"), MemoryError()):
                out = io.StringIO()
                seen = []

                def gate(conn, args, out=out, outcome=outcome, failure=failure):
                    seen.append(outcome.lines[0] in out.getvalue())          # the withdrawal's own lines are already printed when the gate starts
                    raise failure
                conn = types.SimpleNamespace(closed=False, close=lambda: None)
                with mock.patch.object(store, "_read_kind_rows", return_value=("REAL",)), mock.patch.object(store, "_run_gate", gate), \
                        mock.patch.object(store.RealPublisher, "withdraw", return_value=outcome):
                    status = store.main(argv, connect=lambda a: conn, out=out)
                self.assertEqual(status, outcome.status, failure)
                self.assertEqual(seen, [True], failure)
                text = out.getvalue()
                self.assertTrue(text.startswith("\n".join(outcome.lines)) or outcome.lines[0] in text.splitlines()[0], text)
                self.assertIn("preflight could not run: %s" % type(failure).__name__, text)
                self.assertEqual(text.count(outcome.lines[0]), 1)

    def test_a_test_named_database_connects_with_no_prompt(self):
        import psycopg
        prompted = []
        args = types.SimpleNamespace(command="publish", socket="/a/.s.PGSQL.5432", database="finweb_dev", user="u")
        with mock.patch.object(psycopg, "connect", lambda *a, **k: object()):
            store._default_connect(lambda role: prompted.append(role))(args)
        self.assertEqual(prompted, [])


if __name__ == "__main__":
    unittest.main()
