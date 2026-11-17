"""F1 R7, PostgreSQL (disposable database, TEST installs only): the real-mode app over the real service, the launcher, the admission probe and the
D-3 question (design 7.1, R7 row), after the owner's PD-0078 (a fifth `account` role).

Everything stored is invented; the contexts are `SYNTHETIC_TEST` (the fictional branch), published through the product tool. The account role is the
FIFTH role of the install: the kit creates the login as it does the other four, and the PRODUCT installer (`install_test_gateway(account_role=...)`)
grants it exactly `real_roles.ACCOUNT_TABLES` and audits it. No `finweb_real*` database or cluster is touched; without a provisioning superuser
the tests SKIP with the reason.

Labels: "product path" = the product's launcher, routes, service or probe; "crafted (E11)" = a state written by a role of the disposable database.
"""
from __future__ import annotations

import dataclasses
import io
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402

import real_gateway_fixtures as fx  # noqa: E402
import real_mode_kit as kit  # noqa: E402
from persistence import real_tool_gate  # noqa: E402
from persistence.web_account_store import WebAccountStore  # noqa: E402
from real_gateway_kit import KIT, PURPOSES, GatewayCase, setUpModule, tearDownModule, wait_until  # noqa: E402,F401
from real_r5_case import R5Case  # noqa: E402
from real_tools import admission_probe  # noqa: E402
from web_api import auth, real_launcher  # noqa: E402
from web_api.real_mode_routes import ContextPin, create_real_mode_app  # noqa: E402

IDENTITY_TABLES = ("app_user", "web_identity", "web_session", "web_auth_rate")
ECONOMIC = ("portfolio", "account", "ledger_event", "rw_root", "rw_revision", "rw_root_link", "rw_lease", "rw_artifact", "rw_operation", "rw_journal")
PEERS = iter("127.0.%d.%d" % (a, b) for a in range(10, 250) for b in range(1, 250))


def account_role(inst):
    """The fifth role of an install made with `ACCOUNT = True` (PD-0078): the role is created by the kit as the other four are, and its grants are the
    PRODUCT installer's (`install_test_gateway(account_role=...)` applies `real_roles.ACCOUNT_TABLES` and audits it). Nothing is granted here."""
    return inst.roles["account"], inst.passwords["account"]


def opener_for(inst):
    role, password = account_role(inst)
    prov = inst.kit.prov

    def opener():
        conn = psycopg.connect(prov.dsn(prov.db, role, password), autocommit=True)
        prov.connections.append(conn)
        return conn
    return opener


def contexts_json(live, generation=1):
    link = live.cand
    return json.dumps({"schema": real_launcher.CONTEXTS_SCHEMA, "contexts": [{"context_id": live.ctx, "generation": generation, "provenance": {
        "context_sha256": link.context_sha256, "members": [dataclasses.asdict(m) for m in link.members],
        "witnesses": [dataclasses.asdict(w) for w in link.witnesses]}}]})


class R7Case(R5Case):
    INSTALL = "r7"
    ACCOUNT = True
    W = 30          # the per-operation window of the install (R5Case uses 4 s): a create through the HTTP app on a loaded machine must not meet RW_DEADLINE

    def setUp(self):
        super().setUp()
        self.live = self.fictional_live()
        self.accounts = WebAccountStore(None, self.s, opener=opener_for(self.inst))
        self.pins = {self.live.ctx: ContextPin(self.live.ctx, 1, self.link(self.live))}
        self.app = create_real_mode_app(service=self.service, contexts=self.pins, account_store=self.accounts,
                                        connect=lambda: self.inst.connect("executor"), settings=auth.AuthSettings.local(), origins=kit.ORIGINS)

    def client(self, app=None):
        return kit.Client(app or self.app, peer=next(PEERS))

    def economic(self):
        return {table: self.count(table) for table in ECONOMIC}


class AppOverTheRealServiceTests(R7Case):
    def test_create_read_reproduce_list_replay_through_the_app_over_a_test_install(self):
        """product path, shared tail on SYNTHETIC_TEST: the whole flow through the HTTP app, the real service and a real account role."""
        client = self.client()
        client.sign_up("alice_r7")
        body = self.intent(self.live)
        status, created, _ = client.post("/api/real/v1/roots", body)
        self.assertEqual(status, 201, created)
        self.assertEqual(created["origin"]["market_origin"], "SYNTHETIC_TEST")
        self.assertTrue(created["origin"]["synthetic"])
        self.assertEqual(created["labels"]["origin_kind"], "INVENTED_TEST_DATA")
        self.assertEqual(created["claim_limits"]["items"], [])
        self.assertTrue(created["claim_limits"]["invented_data_mark"])
        root, operation = created["root_id"], created["operation_id"]
        status, read, _ = client.get("/api/real/v1/roots/%s/operations/%s" % (root, operation))
        self.assertEqual((status, read["issued_sha256"], read["response_sha256"]), (200, created["issued_sha256"], created["response_sha256"]))
        status, reproduced, _ = client.post("/api/real/v1/roots/%s/operations/%s/reproduce" % (root, operation))
        self.assertEqual((status, reproduced["status"]), (200, "REPRODUCED"), reproduced)
        status, listed, _ = client.get("/api/real/v1/roots")
        self.assertEqual(status, 200)
        self.assertEqual([entry["root_id"] for entry in listed["roots"]], [root])
        self.assertEqual(listed["roots"][0]["origin"]["market_origin"], "SYNTHETIC_TEST")
        status, again, _ = client.post("/api/real/v1/roots", body)
        self.assertEqual((status, again["replayed"], again["root_id"]), (200, True, root))
        self.assertEqual(self.count("rw_root", "portfolio_id=%s", (uuid.UUID(root),)), 1)

    def test_the_list_generation_is_the_contexts_current_one_and_the_read_names_the_creation_generation_HG4_condition_2(self):
        """product path, shared tail on SYNTHETIC_TEST (TR-G2 L-1, design G5 check 5): a root created at generation 1, the context then renewed twice (head 3). Through the
        HTTP app, the real service and the installed SQL: the list entry's `generation` is the CURRENT generation (3, from `rw_list_roots`/the admission) and the read
        payload's `created_under_generation` is the sealed envelope's 1, the number the create stored. Neither value is built by the test."""
        import datetime as dt
        client = self.client()
        owner = client.sign_up("alice_r7g")
        status, created, _ = client.post("/api/real/v1/roots", self.intent(self.live))
        self.assertEqual(status, 201, created)
        self.assertNotIn("created_under_generation", created)
        root, operation = created["root_id"], created["operation_id"]
        for generation in (1, 2):
            renewed = self.renew(self.live.ctx, generation, valid_until=self.db_now() + dt.timedelta(seconds=120), evidence=self.evidence())
            self.assertEqual(renewed.status, 0, renewed.text)
        status, listed, _ = client.get("/api/real/v1/roots")
        self.assertEqual(status, 200, listed)
        self.assertEqual([entry["root_id"] for entry in listed["roots"]], [root])
        entry = listed["roots"][0]
        self.assertEqual((entry["generation"], entry["operation_id"], entry["context_id"]), (3, operation, self.live.ctx))
        status, read, _ = client.get("/api/real/v1/roots/%s/operations/%s" % (root, operation))
        self.assertEqual(status, 200, read)
        self.assertEqual((read["schema_version"], read["created_under_generation"]), ("finweb.cp7.real_scoped_read/2", 1))
        self.assertNotEqual(entry["generation"], read["created_under_generation"])
        # the 1 is the stored sealed envelope's own value, read through the service at the head generation (not a number this test supplied)
        archive = self.service.archive_read(self.conn("executor"), owner=owner, root=uuid.UUID(root),
                                            operation_id=uuid.UUID(operation), context_id=self.live.ctx, generation=3)
        self.assertEqual(json.loads(archive.value.envelope)["generation"], 1)

    def test_a_committed_create_whose_response_cannot_be_built_is_unknown_and_the_repeat_returns_the_same_root(self):
        """TR7R-L-1 on a TEST install. A TEST create cannot fail to build by itself (its block needs no lineage), so the failure after the COMMIT is
        produced by making the claim render raise for the first call only: the create has committed, the response cannot be built. The answer is the
        unknown outcome; the identical command is then a replay of the SAME root, and exactly one root exists."""
        from unittest import mock
        from marketdata import claim_render
        client = self.client()
        client.sign_up("alice_r7c")
        body = self.intent(self.live)
        real_render = claim_render.render_claim_block
        roots_before = self.count("rw_root")
        calls = []

        def fails_once(origin, lineage=None):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("SENTINEL-BOOM")
            return real_render(origin, lineage)
        with mock.patch.object(claim_render, "render_claim_block", side_effect=fails_once):
            status, first, raw = client.post("/api/real/v1/roots", body)
            self.assertEqual((status, first["state"], first["operation_id"]), (503, "UNKNOWN", body["operation_id"]), first)
            self.assertNotIn("error", first)
            self.assertNotIn(b"SENTINEL-BOOM", json.dumps(first).encode())
            self.assertEqual(self.count("rw_root"), roots_before + 1)                   # it DID commit (the install is shared: a delta, not an absolute)
            status, again, _ = client.post("/api/real/v1/roots", body)
        self.assertEqual((status, again["replayed"], again["operation_id"]), (200, True, body["operation_id"]), again)
        self.assertEqual(self.count("rw_root"), roots_before + 1)                       # the repeat created nothing new
        self.assertEqual(self.count("rw_root", "portfolio_id=%s", (uuid.UUID(again["root_id"]),)), 1)

    def test_a_second_user_gets_the_generic_404_for_the_first_users_root_and_does_not_list_it(self):
        """product path: two-user isolation through the app. The foreign root and an unknown root answer with the same bytes."""
        first, second = self.client(), self.client()
        first.sign_up("alice_r7b")
        second.sign_up("bob_r7b")
        status, created, _ = first.post("/api/real/v1/roots", self.intent(self.live))
        self.assertEqual(status, 201, created)
        root, operation = created["root_id"], created["operation_id"]
        unknown = str(uuid.uuid4())
        for method, path in (("get", "/api/real/v1/roots/%s/operations/%s"), ("post", "/api/real/v1/roots/%s/operations/%s/reproduce")):
            foreign = getattr(second, method)(path % (root, operation))
            missing = getattr(second, method)(path % (unknown, operation))
            self.assertEqual(foreign[0], 404)
            self.assertEqual(foreign[2], missing[2], "a foreign root and an unknown root are indistinguishable")
            self.assertNotIn(root.encode(), foreign[2])
        status, listed, _ = second.get("/api/real/v1/roots")
        self.assertEqual((status, listed["roots"]), (200, []))

    def test_a_signed_out_client_sees_nothing(self):
        client = self.client()
        for path in ("/api/real/v1/roots", "/api/real/v1/roots/%s/operations/%s" % (uuid.uuid4(), uuid.uuid4())):
            self.assertEqual(client.get(path)[0], 401)


class SecondUserWithoutAnEconomicWriteTests(R7Case):
    """The D-3 question (design 7.1, R7 exit): can the real-mode app hold a second user without an economic write?"""

    def test_registering_two_users_through_the_account_role_writes_no_economic_row(self):
        """product installer's account role: a registration writes identity and session rows only. Nothing the write fence guards is touched."""
        before = self.economic()
        identity_before = {t: self.count(t) for t in IDENTITY_TABLES}
        for name in ("alice_d3", "bob_d3"):
            self.client().sign_up(name)
        self.assertEqual(self.economic(), before)
        after = {t: self.count(t) for t in IDENTITY_TABLES}
        self.assertEqual(after["app_user"] - identity_before["app_user"], 2)
        self.assertEqual(after["web_identity"] - identity_before["web_identity"], 2)
        self.assertEqual(after["web_session"] - identity_before["web_session"], 2)

    def test_the_executor_still_cannot_register_anyone_so_the_account_role_is_what_holds_the_users(self):
        """product install: the executor keeps no identity or session grant (R3 M-1); PD-0078 gave those tables to the fifth role, not to it."""
        executor = self.conn("executor")
        for statement, params in ((f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (uuid.uuid4(),)),
                                  (f"SELECT count(*) FROM {self.s}.web_identity", ()), (f"SELECT count(*) FROM {self.s}.web_session", ()),
                                  (f"SELECT count(*) FROM {self.s}.app_user", ())):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege, msg=statement):
                executor.execute(statement, params)
        for role in ("loader", "publisher"):
            conn = self.conn(role)
            with self.assertRaises(psycopg.errors.InsufficientPrivilege, msg=role):
                conn.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (uuid.uuid4(),))

    def test_the_account_role_has_no_privilege_on_any_economic_table_or_gateway_function(self):
        """product installer: the fifth role is bounded to the four identity tables, by the catalog and by a refused read."""
        role, password = account_role(self.inst)
        rows = self.owner.execute(
            "SELECT c.relname, has_table_privilege(%s, c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind IN ('r','v','m','p')", (role, self.s)).fetchall()
        holds = {name for name, flag in rows if flag}
        self.assertEqual(holds, set(IDENTITY_TABLES))
        functions = self.owner.execute(
            "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND has_function_privilege(%s, p.oid, 'EXECUTE')",
            (self.s, role)).fetchall()
        self.assertEqual([name for (name,) in functions if name.startswith("rw")], [])
        conn = opener_for(self.inst)()
        for table in ("portfolio", "rw_root", "ledger_event"):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege, msg=table):
                conn.execute(f"SELECT count(*) FROM {self.s}.{table}")
        conn.close()

    def test_a_signed_in_user_cannot_create_without_the_service_and_the_account_store_never_writes_a_root(self):
        """product path: a create commits through the executor and the gateway; the account store wrote the two identity rows and no root."""
        client = self.client()
        client.sign_up("carol_d3")
        before = self.economic()
        status, created, _ = client.post("/api/real/v1/roots", self.intent(self.live))      # the install is shared by the class: compare with the count before
        self.assertEqual(status, 201, created)
        self.assertEqual(self.count("rw_root"), before["rw_root"] + 1)


class AccountRoleInstallerTests(GatewayCase):
    """PD-0078, on a TEST install made by the product installer: the fifth role has exactly the granted set, the catalog audit judges it like the other
    four, and the installer's own checks (`real_install.run_checks`) refuse an extra grant, an economic grant and a missing role. Each crafted state
    ("crafted (E11)") is written by the administrative role of the disposable database and reverted in `finally`."""
    INSTALL = "r7acct"
    ACCOUNT = True
    PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")

    def account(self):
        return self.inst.roles["account"]

    def audit(self, as_kind="TEST", account_role="default"):
        from persistence import real_catalog_audit
        r = self.inst.roles
        return real_catalog_audit.audit(self.admin, self.s, r["owner"], r["executor"], r["loader"], r["publisher"], as_kind=as_kind,
                                        account_role=self.account() if account_role == "default" else account_role)

    def crafted(self, grant, revoke):
        """crafted (E11): run `grant`, return a context manager that runs `revoke`."""
        import contextlib

        @contextlib.contextmanager
        def window():
            self.admin.execute(grant.format(s=self.s, a=self.account(), e=self.inst.roles["executor"]))
            try:
                yield
            finally:
                self.admin.execute(revoke.format(s=self.s, a=self.account(), e=self.inst.roles["executor"]))
        return window()

    def held(self):
        """{relation: privileges} the account role holds, from the catalog, over every relation of the schema."""
        out = {}
        for oid, name in self.admin.execute("SELECT c.oid,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s "
                                            "AND c.relkind IN ('r','p','v','m','f')", (self.s,)).fetchall():
            privileges = {p for p in self.PRIVILEGES if self.admin.execute("SELECT has_table_privilege(%s,%s,%s)", (self.account(), oid, p)).fetchone()[0]}
            if privileges:
                out[name] = frozenset(privileges)
        return out

    def test_the_role_exists_with_exactly_the_granted_set_and_nothing_else(self):
        from persistence import real_roles
        self.assertEqual(self.held(), real_roles.ACCOUNT_TABLES)
        role = self.admin.execute("SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication,rolinherit FROM pg_roles WHERE rolname=%s",
                                  (self.account(),)).fetchone()
        self.assertEqual(role, (True, False, False, False, False, False, False))
        usage, create = self.admin.execute("SELECT has_schema_privilege(%s,%s,'USAGE'),has_schema_privilege(%s,%s,'CREATE')",
                                           (self.account(), self.s, self.account(), self.s)).fetchone()
        self.assertEqual((usage, create), (True, False))
        sequences = self.admin.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='S' "
                                       "AND (has_sequence_privilege(%s,c.oid,'USAGE') OR has_sequence_privilege(%s,c.oid,'SELECT') "
                                       "OR has_sequence_privilege(%s,c.oid,'UPDATE'))", (self.s, self.account(), self.account(), self.account())).fetchall()
        functions = self.admin.execute("SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s "
                                       "AND has_function_privilege(%s,p.oid,'EXECUTE')", (self.s, self.account())).fetchall()
        self.assertEqual((sequences, functions), ([], []))
        self.assertEqual(self.audit().findings, ())
        members = self.admin.execute("SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname=%s", (self.account(),)).fetchone()[0]
        self.assertEqual(members, 0)

    def test_the_audit_refuses_an_extra_grant_an_economic_grant_a_function_a_membership_and_a_grant_option(self):
        cases = {
            "an extra privilege on an identity table": ("GRANT DELETE ON {s}.web_identity TO {a}", "REVOKE DELETE ON {s}.web_identity FROM {a}",
                                                       "RW_AUDIT_PRIVILEGE_DIFFERS", "web_identity"),
            "UPDATE on app_user": ("GRANT UPDATE ON {s}.app_user TO {a}", "REVOKE UPDATE ON {s}.app_user FROM {a}", "RW_AUDIT_PRIVILEGE_DIFFERS", "app_user"),
            "an economic grant": ("GRANT SELECT ON {s}.portfolio TO {a}", "REVOKE SELECT ON {s}.portfolio FROM {a}", "RW_AUDIT_PRIVILEGE_DIFFERS", "portfolio"),
            "a rooted-table grant": ("GRANT INSERT ON {s}.rw_root TO {a}", "REVOKE INSERT ON {s}.rw_root FROM {a}", "RW_AUDIT_PRIVILEGE_DIFFERS", "rw_root"),
            "a market-data grant": ("GRANT SELECT ON {s}.md_quote TO {a}", "REVOKE SELECT ON {s}.md_quote FROM {a}", "RW_AUDIT_PRIVILEGE_DIFFERS", "md_quote"),
            "a gateway function": ("GRANT EXECUTE ON FUNCTION {s}.rw_install_info() TO {a}", "REVOKE EXECUTE ON FUNCTION {s}.rw_install_info() FROM {a}",
                                   "RW_AUDIT_PRIVILEGE_DIFFERS", "rw_install_info"),
            "a sequence": ("GRANT USAGE ON SEQUENCE {s}.ledger_event_ledger_seq_seq TO {a}", "REVOKE USAGE ON SEQUENCE {s}.ledger_event_ledger_seq_seq FROM {a}",
                           "RW_AUDIT_PRIVILEGE_DIFFERS", "ledger_event_ledger_seq_seq"),
            "a grant option": ("GRANT SELECT ON {s}.web_identity TO {a} WITH GRANT OPTION", "REVOKE GRANT OPTION FOR SELECT ON {s}.web_identity FROM {a}",
                               "RW_AUDIT_GRANT_OPTION", "web_identity"),
            "a membership in the executor": ("GRANT {e} TO {a}", "REVOKE {e} FROM {a}", "RW_AUDIT_MEMBERSHIP", None),
        }
        self.assertEqual(self.audit().findings, (), "the control before the crafted states")
        for label, (grant, revoke, code, subject) in cases.items():
            with self.subTest(label), self.crafted(grant, revoke):
                result = self.audit()
                self.assertIn(code, result.codes(), (label, [f.short() for f in result.findings]))
                if subject is not None:
                    self.assertIn(subject, [f.subject for f in result.findings], label)
            self.assertEqual(self.audit().findings, (), "the control after the revert: " + label)

    def test_a_missing_account_role_is_a_finding_and_a_four_role_audit_names_none(self):
        result = self.audit(account_role=self.account() + "_gone")
        self.assertEqual(result.codes(), ("RW_AUDIT_ACCOUNT_ROLE",))
        self.assertEqual(self.audit(account_role=None).findings, (), "the earlier four-role audit is unchanged")

    def test_a_revoked_grant_is_also_a_finding_the_role_lacks_what_the_list_gives(self):
        with self.crafted("REVOKE INSERT ON {s}.web_identity FROM {a}", "GRANT INSERT ON {s}.web_identity TO {a}"):
            self.assertIn("RW_AUDIT_PRIVILEGE_DIFFERS", self.audit().codes())
        self.assertEqual(self.audit().findings, ())


class LauncherOverATestInstallTests(R7Case):
    def launch(self, **kw):
        out, served = io.StringIO(), []
        file = Path(self.tmp, "contexts.json")
        file.write_text(contexts_json(self.live))
        prov = self.inst.kit.prov
        argv = ["--socket", "/tmp/.s.PGSQL.5432", "--database", prov.db, "--user", self.inst.roles["executor"], "--schema", self.s,
                "--account-user", account_role(self.inst)[0], "--contexts-file", str(file)]
        opener = opener_for(self.inst)

        def connect(args, user, prompt, autocommit):
            return self.inst.connect("executor") if user == self.inst.roles["executor"] else opener()
        with mock.patch.object(real_tool_gate, "_run_gate", side_effect=AssertionError("a preflight ran over a TEST install")):
            status = real_launcher.main(argv, connect=connect, prompt=lambda role: self.fail("a password was asked for"),
                                        serve=lambda app, port: served.append((app, port)), out=out)
        return status, served, out.getvalue()

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def test_the_launcher_starts_over_a_test_install_without_a_preflight_and_serves_the_scoped_contract(self):
        """product path: the decision comes from the database (the name and the install-kind rows), so nothing is bypassed; the app it builds works."""
        status, served, text = self.launch()
        self.assertEqual(status, real_launcher.EXIT_OK, text)
        self.assertIn("TEST target", text)
        (app, port), = served
        self.assertEqual(port, real_launcher.DEFAULT_PORT)
        client = self.client(app)
        client.sign_up("dave_r7")
        status, created, _ = client.post("/api/real/v1/roots", self.intent(self.live))
        self.assertEqual((status, created["origin"]["market_origin"]), (201, "SYNTHETIC_TEST"), created)
        self.assertEqual(self.client(app).get("/api/real/v1/portfolios")[0], 503)         # every other route is a closed refusal

    def test_the_launcher_wrote_nothing_before_the_server_started(self):
        before = self.economic()
        identity = {t: self.count(t) for t in IDENTITY_TABLES}
        status, _served, text = self.launch()
        self.assertEqual(status, real_launcher.EXIT_OK, text)
        self.assertEqual((self.economic(), {t: self.count(t) for t in IDENTITY_TABLES}), (before, identity))


class LauncherOverACraftedRealKindInstallTests(GatewayCase):
    """crafted (E11): a REAL-kind install under a TEST-looking database name. The name and the rows disagree, so the launcher refuses before it serves."""
    INSTALL = "r7realkind"
    KIND = "REAL"

    def test_a_real_kind_row_under_a_test_name_is_refused_and_nothing_is_started(self):
        out, served = io.StringIO(), []
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp, "contexts.json")
            file.write_text(json.dumps({"schema": real_launcher.CONTEXTS_SCHEMA, "contexts": [{"context_id": "c" * 64, "generation": 1, "provenance": {
                "context_sha256": "6" * 64, "members": [{"role": "CORPORATE_ACTION", "payload_sha256": "1" * 64, "manifest_sha256": "2" * 64,
                                                         "envelope_sha256": "3" * 64, "witness_sha256": "4" * 64}], "witnesses": [{
                    "expected_envelope_sha256": "3" * 64, "expected_manifest_sha256": "2" * 64, "actor_agent_id": "/root/invented_collector",
                    "actor_role": "engineer", "approved_full_request_sha256": "5" * 64}]}}]}))
            argv = ["--socket", "/tmp/.s.PGSQL.5432", "--database", self.inst.kit.prov.db, "--user", self.inst.roles["executor"], "--schema", self.s,
                    "--account-user", "nobody", "--contexts-file", str(file)]
            status = real_launcher.main(argv, connect=lambda args, user, prompt, autocommit: self.inst.connect("executor"),
                                        prompt=lambda role: self.fail("a password was asked for"), serve=lambda app, port: served.append(app), out=out)
        self.assertEqual((status, served), (real_launcher.EXIT_REFUSED, []), out.getvalue())
        self.assertEqual(self.count("rw_lease"), 0)


class AdmissionProbeTests(GatewayCase):
    """product path (the probe) over a TEST install: direct gateway admission for the three purposes it can select."""
    INSTALL = "r7probe"

    def make(self, valid_in=120.0, rights=None):
        snap, valid, _ = self.publish(valid_in=valid_in, rights=rights)
        owner_id, root_id = self.craft_root(snap.context_id)
        return snap.context_id, valid, owner_id, root_id

    def probe(self, purpose, ctx, generation, owner_id, root_id):
        prov = self.inst.kit.prov
        argv = ["--socket", "/tmp/.s.PGSQL.5432", "--database", prov.db, "--user", self.inst.roles["executor"], "--schema", self.s, "--purpose", purpose,
                "--owner-id", str(owner_id), "--root-id", str(root_id), "--context", ctx, "--generation", str(generation)]
        out = io.StringIO()
        with mock.patch.object(real_tool_gate, "_run_gate", side_effect=AssertionError("a preflight ran over a TEST install")):
            status = admission_probe.main(argv, connect=lambda args, prompt: self.inst.connect("executor"), out=out)
        return status, out.getvalue()

    def assertNoLease(self, ctx, before=0):
        self.assertEqual(self.count("rw_lease"), before)
        self.assertEqual(self.leases(ctx), [])

    def test_each_purpose_is_admitted_while_the_right_is_on_and_leaves_no_lease(self):
        for purpose in admission_probe.PURPOSES:
            with self.subTest(purpose):
                ctx, _valid, owner_id, root_id = self.make()
                status, text = self.probe(purpose, ctx, 1, owner_id, root_id)
                self.assertEqual(status, admission_probe.EXIT_ADMITTED, text)
                self.assertTrue(text.startswith("direct gateway admission, not a product route"), text)
                self.assertIn("ADMITTED purpose=%s" % purpose, text)
                self.assertNoLease(ctx)

    def test_each_purpose_is_refused_with_its_code_when_its_right_is_off(self):
        for purpose in admission_probe.PURPOSES:
            with self.subTest(purpose):
                ctx, _valid, owner_id, root_id = self.make(rights={**fx.ALL_RIGHTS, purpose: False})
                status, text = self.probe(purpose, ctx, 1, owner_id, root_id)
                self.assertEqual(status, admission_probe.EXIT_REFUSED_BY_GATEWAY, text)
                self.assertIn("REFUSED RW_RIGHT_REFUSED", text)
                self.assertNoLease(ctx)

    def test_each_purpose_is_refused_after_a_withdrawal(self):
        ctx, _valid, owner_id, root_id = self.make()
        result = self.tool().withdraw(ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual((result.status, result.outcome), (0, "WITHDRAWN"), result.text)
        for purpose in admission_probe.PURPOSES:
            with self.subTest(purpose):
                status, text = self.probe(purpose, ctx, 2, owner_id, root_id)
                self.assertEqual(status, admission_probe.EXIT_REFUSED_BY_GATEWAY, text)
                self.assertIn("REFUSED RW_WITHDRAWN", text)
                self.assertNoLease(ctx)

    def test_each_purpose_is_refused_after_a_lapse(self):
        # FLAKE FIX (R7 fix round): the window was 2 s. `valid_until` is counted from before the publish call, and the positive control below opens a new
        # connection and runs the start gate, so on a loaded machine (the full PostgreSQL run) the control could land after the lapse and fail with
        # RW_LAPSED, and the publish itself could be late. 10 s costs at most 10 s of waiting.
        ctx, valid, owner_id, root_id = self.make(valid_in=10.0)
        status, text = self.probe("ARCHIVE_READ", ctx, 1, owner_id, root_id)              # the positive control, before valid_until
        self.assertEqual(status, admission_probe.EXIT_ADMITTED, text)
        self.wait_for_db_time(valid)
        for purpose in admission_probe.PURPOSES:
            with self.subTest(purpose):
                status, text = self.probe(purpose, ctx, 1, owner_id, root_id)
                self.assertEqual(status, admission_probe.EXIT_REFUSED_BY_GATEWAY, text)
                self.assertIn("REFUSED RW_LAPSED", text)
                self.assertNoLease(ctx)

    def test_the_probe_cannot_select_create_and_never_registers_a_root(self):
        ctx, _valid, owner_id, root_id = self.make()
        before = {t: self.count(t) for t in ("rw_root_link", "portfolio", "rw_lease")}
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr", io.StringIO()):
                self.probe("EXECUTE_CREATE", ctx, 1, owner_id, root_id)
        stranger = uuid.uuid4()                                   # a root nobody registered: the probe does not register it
        status, text = self.probe("ARCHIVE_READ", ctx, 1, owner_id, stranger)
        self.assertEqual(status, admission_probe.EXIT_REFUSED_BY_GATEWAY, text)
        self.assertEqual({t: self.count(t) for t in ("rw_root_link", "portfolio", "rw_lease")}, before)


if __name__ == "__main__":
    unittest.main()
