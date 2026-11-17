"""F1 R2, PostgreSQL: the real loader role (design 3.3 "The narrowing", PD-0070 decision 1; design 7.1, R2 row).

The loader's list is `INSERT` on the thirteen md_* tables, `SELECT` on `md_file` and `md_release`, `EXECUTE` on the registry's put and get
functions, `USAGE` on the schema and nothing else. These tests assert, from the catalog and by behaviour, that each read the list allows is
PRESENT and every other is ABSENT:

  * the exact privileges (a catalog assertion, written here by hand, not read from the list under test);
  * `write_release(..., count_rows=False)` loads an invented release AS THE LOADER (the list suffices: no `42501` on the path);
  * the loader's `SELECT` of `md_quote` (and of every other observation table) is refused, `42501`;
  * the loader's call of the registry's get function returns the payload bytes (what 3.3 says it returns);
  * the loader cannot publish, renew, withdraw, admit or read any gateway table.

R3 revokes PUBLIC's default EXECUTE on every function of the schema (one statement in the role lists), and the installs these tests run on have
it in place: `write_release` below is therefore the R2 loader write RE-RUN with the revoke, and the "no other function" check covers every
function of the schema, migration functions included. The evidence for the two insert-trigger functions on md_* tables is that re-run and
the pin on which functions they are.

All data is invented. Rows are written to disposable databases only, and by the product's own `write_release`.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402

import marketdata_exit_kit as x  # noqa: E402
import pg_market_kit as pk  # noqa: E402
import real_gateway_fixtures as fx  # noqa: E402
from persistence import market_data_store as mds, real_provenance_store as provstore, real_roles, real_workspace_store as store  # noqa: E402
from real_gateway_kit import KIT, setUpModule, tearDownModule  # noqa: E402,F401
from real_provenance_case import ProvCase  # noqa: E402
from real_provenance_fixtures import PAYLOAD, candidate, h  # noqa: E402
from test_postgres_market_data_store import UPDATES, rich_release  # noqa: E402

# Written by hand from design 3.3 and PD-0070 decision 1 (not read from real_roles).
MD_TABLES = ("md_file", "md_release", "md_release_file", "md_quote", "md_fx_rate", "md_corporate_action", "md_benchmark", "md_benchmark_point",
             "md_adjusted_quote", "md_calendar", "md_series_exclusion", "md_risk_free", "md_risk_free_point")
PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
EXPECTED = {table: {"INSERT", "SELECT"} if table in ("md_file", "md_release") else {"INSERT"} for table in MD_TABLES}
REGISTRY_FUNCTIONS = {"rwp_put_context", "rwp_get_context"}
# The release `rich_release` writes, counted by hand from its construction (see test_postgres_market_data_store): rows per table.
RICH_ROWS = {"md_file": 7, "md_release": 1, "md_release_file": 7, "md_quote": 1, "md_fx_rate": 1, "md_corporate_action": 5, "md_benchmark": 1,
             "md_benchmark_point": 2, "md_adjusted_quote": 1, "md_calendar": 1, "md_series_exclusion": 1, "md_risk_free": 1, "md_risk_free_point": 2}


class LoaderCase(ProvCase):
    INSTALL = "loadercat"

    def held(self, role, table, privileges=PRIVILEGES):
        return {p for p in privileges if self.owner.execute("SELECT has_table_privilege(%s::name,%s::regclass,%s)", (role, f'"{self.s}"."{table}"', p)).fetchone()[0]}


class LoaderPrivilegeCatalogTests(LoaderCase):
    def test_the_loader_holds_exactly_its_table_privileges(self):
        role = self.inst.roles["loader"]
        server = int(self.owner.execute("SHOW server_version_num").fetchone()[0])
        privileges = PRIVILEGES + (("MAINTAIN",) if server >= 170000 else ())
        for table in MD_TABLES:
            self.assertEqual(self.held(role, table, privileges), EXPECTED[table], table)

    def test_the_loader_holds_no_column_level_privilege_no_sequence_and_no_gateway_table(self):
        role = self.inst.roles["loader"]
        columns = self.owner.execute(
            "SELECT c.relname,a.attname FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
            "CROSS JOIN LATERAL aclexplode(a.attacl) x WHERE n.nspname=%s AND a.attacl IS NOT NULL AND x.grantee=(SELECT oid FROM pg_roles WHERE rolname=%s)",
            (self.s, role)).fetchall()
        self.assertEqual(columns, [])
        sequences = self.owner.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='S' "
            "AND CASE WHEN c.relkind='S' THEN has_sequence_privilege(%s::name,c.oid,'USAGE,SELECT,UPDATE') ELSE false END", (self.s, role)).fetchall()
        self.assertEqual(sequences, [])
        gateway = [r[0] for r in self.owner.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s "
                                                    "AND c.relkind IN ('r','v','m','p') AND c.relname LIKE 'rw%%' ORDER BY 1", (self.s,)).fetchall()]
        self.assertGreater(len(gateway), 10)                                    # the gateway's tables and views are there to be checked
        for name in gateway:
            self.assertEqual(self.held(role, name), set(), name)

    def test_the_loader_may_execute_the_two_registry_functions_and_no_other_gateway_function(self):
        role = self.inst.roles["loader"]
        rows = self.owner.execute("SELECT p.proname,has_function_privilege(%s::name,p.oid,'EXECUTE') FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                                  "WHERE n.nspname=%s AND p.proname LIKE 'rw%%' ORDER BY 1", (role, self.s)).fetchall()
        self.assertGreater(len(rows), 20)
        self.assertEqual({name for name, allowed in rows if allowed}, REGISTRY_FUNCTIONS)

    def test_the_loader_and_public_hold_execute_on_no_other_function_of_the_schema_migration_functions_included(self):
        """R3 closes what R2 left open: the schema-wide `REVOKE EXECUTE ... FROM PUBLIC` is in place, so the loader's EXECUTE is the two registry
        functions and no more, over EVERY function of the schema (design 7.1, R3 row)."""
        role = self.inst.roles["loader"]
        rows = self.owner.execute("SELECT p.proname,has_function_privilege(%s::name,p.oid,'EXECUTE') FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                                  "WHERE n.nspname=%s ORDER BY 1", (role, self.s)).fetchall()
        self.assertGreater(len(rows), 60)                                       # the migration functions are among them
        self.assertTrue(any(name.startswith("ledger_event") for name, _a in rows))
        self.assertEqual({name for name, allowed in rows if allowed}, REGISTRY_FUNCTIONS)
        no_acl = self.owner.execute("SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND p.proacl IS NULL", (self.s,)).fetchall()
        self.assertEqual(no_acl, [])                                            # a NULL ACL is PostgreSQL's default: EXECUTE for PUBLIC
        public = self.owner.execute("SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(p.proacl) x "
                                    "WHERE n.nspname=%s AND x.grantee=0 AND x.privilege_type='EXECUTE'", (self.s,)).fetchall()
        self.assertEqual(public, [])

    def test_the_insert_trigger_functions_on_the_observation_tables_are_exactly_the_two_the_loader_write_reaches(self):
        """R2 carried the loader write as evidence for the two insert-trigger functions on md_* tables. With PUBLIC's EXECUTE revoked, the write
        still succeeds (LoaderWritesAReleaseTests, run on an install that has the revoke), because a trigger function runs for the inserting
        role without that role holding EXECUTE on it. This test pins WHICH functions those are, so a third one is a visible change, and shows the
        loader holds no EXECUTE on either."""
        role = self.inst.roles["loader"]
        rows = self.owner.execute(
            "SELECT DISTINCT p.proname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
            "JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname=%s AND c.relname LIKE 'md\\_%%' AND NOT t.tgisinternal "
            "AND (t.tgtype & 4) <> 0 ORDER BY 1", (self.s,)).fetchall()                    # tgtype bit 4: INSERT
        self.assertEqual([r[0] for r in rows], ["md_release_stamp", "md_require_open_release"])
        for (name,) in rows:
            self.assertFalse(self.owner.execute("SELECT has_function_privilege(%s::name,(%s)::regproc,'EXECUTE')", (role, f'"{self.s}"."{name}"')).fetchone()[0], name)

    def test_the_loader_may_use_the_schema_and_not_create_in_it(self):
        role = self.inst.roles["loader"]
        row = self.owner.execute("SELECT has_schema_privilege(%s::name,%s::name,'USAGE'),has_schema_privilege(%s::name,%s::name,'CREATE')", (role, self.s, role, self.s)).fetchone()
        self.assertEqual(row, (True, False))

    def test_the_explicit_grants_to_the_loader_are_exactly_the_list(self):
        role = self.inst.roles["loader"]
        tables = {}
        for relname, privilege in self.owner.execute(
                "SELECT c.relname,x.privilege_type FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(c.relacl) x "
                "WHERE n.nspname=%s AND x.grantee=(SELECT oid FROM pg_roles WHERE rolname=%s)", (self.s, role)).fetchall():
            tables.setdefault(relname, set()).add(privilege)
        self.assertEqual(tables, EXPECTED)
        functions = {r[0] for r in self.owner.execute(
            "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(p.proacl) x "
            "WHERE n.nspname=%s AND x.grantee=(SELECT oid FROM pg_roles WHERE rolname=%s) AND x.privilege_type='EXECUTE'", (self.s, role)).fetchall()}
        self.assertEqual(functions, REGISTRY_FUNCTIONS)
        self.assertFalse(self.owner.execute("SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(c.relacl) x "
                                            "WHERE n.nspname=%s AND x.grantee=(SELECT oid FROM pg_roles WHERE rolname=%s) AND x.is_grantable)", (self.s, role)).fetchone()[0])

    def test_the_shared_list_the_catalog_and_the_installers_check_agree(self):
        role = self.inst.roles["loader"]
        self.assertEqual(real_roles.loader_catalog(self.owner, self.s, role), real_roles.loader_catalog_expected())
        expected = real_roles.loader_expected()
        self.assertEqual({t: set(p) for t, p in expected["table_privileges"].items()}, EXPECTED)
        self.assertEqual(set(expected["functions"]), REGISTRY_FUNCTIONS)
        self.assertEqual(real_roles.catalog_difference(real_roles.loader_catalog(self.owner, self.s, role)), "none")

    def test_the_loader_role_is_an_exact_role(self):
        role = self.inst.roles["loader"]
        flags = self.owner.execute("SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication,rolinherit,"
                                   "EXISTS(SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid OR m.roleid=r.oid) FROM pg_roles r WHERE rolname=%s", (role,)).fetchone()
        self.assertEqual(flags, (False,) * 7)


class LoaderGrantAuditTests(LoaderCase):
    """The installer's check catches a widening: in an install of its own the owner role (E11 crafted, reverted after the test) grants one
    extra privilege, and the product's catalog check reports it and the install check refuses. Each case adds exactly one grant."""
    INSTALL = "loaderaudit"

    def test_one_extra_privilege_is_reported_and_refused(self):
        role = self.inst.roles["loader"]
        r = self.inst.roles
        cases = {"select md_quote": (f"GRANT SELECT ON {self.s}.md_quote TO {role}", f"REVOKE SELECT ON {self.s}.md_quote FROM {role}"),
                 "update md_file": (f"GRANT UPDATE ON {self.s}.md_file TO {role}", f"REVOKE UPDATE ON {self.s}.md_file FROM {role}"),
                 "select rw_head": (f"GRANT SELECT ON {self.s}.rw_head TO {role}", f"REVOKE SELECT ON {self.s}.rw_head FROM {role}"),
                 "execute rw_scope": (f"GRANT EXECUTE ON FUNCTION {self.s}.rw_scope() TO {role}", f"REVOKE EXECUTE ON FUNCTION {self.s}.rw_scope() FROM {role}"),
                 "execute load": (f"GRANT EXECUTE ON FUNCTION {self.s}.rwp_load_context(text,text) TO {role}",
                                  f"REVOKE EXECUTE ON FUNCTION {self.s}.rwp_load_context(text,text) FROM {role}"),
                 "column select": (f"GRANT SELECT (price) ON {self.s}.md_quote TO {role}", f"REVOKE SELECT (price) ON {self.s}.md_quote FROM {role}"),
                 "usage create": (f"GRANT CREATE ON SCHEMA {self.s} TO {role}", f"REVOKE CREATE ON SCHEMA {self.s} FROM {role}"),
                 "grant option": (f"GRANT INSERT ON {self.s}.md_quote TO {role} WITH GRANT OPTION", f"REVOKE GRANT OPTION FOR INSERT ON {self.s}.md_quote FROM {role}")}
        # The control: the install as shipped passes both checks.
        self.assertEqual(real_roles.loader_catalog(self.owner, self.s, role), real_roles.loader_catalog_expected())
        provstore.verify_registry_install(self.owner, self.s, r["owner"], r["executor"], role, r["publisher"])
        for label, (grant, revoke) in cases.items():
            self.owner.execute(grant)
            try:
                actual = real_roles.loader_catalog(self.owner, self.s, role)
                self.assertNotEqual(actual, real_roles.loader_catalog_expected(), label)
                with self.assertRaises(store.RealWorkspaceError, msg=label) as caught:
                    provstore.verify_registry_install(self.owner, self.s, r["owner"], r["executor"], role, r["publisher"])
                self.assertEqual(caught.exception.code, "RW_INSTALL_REFUSED", label)
            finally:
                self.owner.execute(revoke)
        self.assertEqual(real_roles.loader_catalog(self.owner, self.s, role), real_roles.loader_catalog_expected())


class LoaderRefusalTests(LoaderCase):
    def test_the_loader_cannot_read_an_observation_table_42501(self):
        loader = self.conn("loader")
        self.assertDenied(lambda: loader.execute(f"SELECT * FROM {self.s}.md_quote"))
        self.assertDenied(lambda: loader.execute(f"SELECT count(*) FROM {self.s}.md_quote"))
        for table in MD_TABLES:
            if table in ("md_file", "md_release"):
                loader.execute(f"SELECT count(*) FROM {self.s}.{table}").fetchone()            # the two it may read
            else:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege, msg=table) as caught:
                    loader.execute(f"SELECT 1 FROM {self.s}.{table} LIMIT 1")
                self.assertEqual(caught.exception.sqlstate, "42501", table)

    def test_the_loader_cannot_publish_renew_withdraw_admit_or_read_a_gateway_table(self):
        loader = self.conn("loader")
        s = self.s
        snap = self.snapshot()
        calls = (f"SELECT * FROM {s}.rw_publish(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)",
                 f"SELECT * FROM {s}.rw_renew(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)",
                 f"SELECT * FROM {s}.rw_withdraw_mark(NULL,NULL,NULL,NULL,NULL,NULL)",
                 f"SELECT * FROM {s}.rw_withdraw_apply(NULL,NULL)",
                 f"SELECT * FROM {s}.rw_admit(NULL,NULL,NULL,NULL,NULL,NULL,NULL)",
                 f"SELECT * FROM {s}.rw_scope()", f"SELECT * FROM {s}.rw_install_info()", f"SELECT * FROM {s}.rw_in_flight(NULL)",
                 f"SELECT * FROM {s}.rwp_load_context(NULL,NULL)", f"SELECT {s}.rwp_origin_failures(NULL)",
                 f"INSERT INTO {s}.rw_head SELECT * FROM {s}.rw_head", f"SELECT * FROM {s}.rw_head", f"SELECT * FROM {s}.rw_status",
                 f"INSERT INTO {s}.rw_snapshot VALUES('x','x')", f"INSERT INTO {s}.rwp_payload SELECT * FROM {s}.rwp_payload",
                 f"SET ROLE {self.inst.roles['publisher']}")
        for statement in calls:
            self.assertDenied(lambda st=statement: loader.execute(st))
        before = {t: self.count(t) for t in ("rw_snapshot", "rw_history", "rw_head", "rw_lease")}
        result = store.RealPublisher(self.conn("loader"), self.s).publish(self.proposal(snap), rights=fx.ALL_RIGHTS, valid_until=None, evidence=fx.none_shape(), actor=fx.ACTOR, ref=fx.REF)
        self.assertEqual(result.status, 2, result.text)                        # a refusal, not a publish
        self.assertNotEqual(result.outcome, "PUBLISHED")
        self.assertEqual({t: self.count(t) for t in before}, before)
        self.assertEqual(self.count("rw_snapshot", "context_id=%s", (snap.context_id,)), 0)


class LoaderRegistryGetTests(LoaderCase):
    def test_the_get_function_returns_the_payload_bytes_and_the_rest_of_the_bundle(self):
        """3.3 (technical TR5-M1): the owner did not take the narrower option; the get function returns the bundle, payload bytes included.
        The registry code re-validates from the returned bytes. By digest, and by operation id (which adds the stored response)."""
        for v1 in (True, False):
            cand = candidate(PAYLOAD + (b"v1" if v1 else b"v2"), scope="TEST_SWITCH", salt=self.tag("get"), v1=v1)
            op, saved = self.save(cand)
            row = self.get_sql(self.loader_conn(), cand.context_sha256, None)
            context_b, payloads, manifests, envelopes, witnesses, response = row
            self.assertEqual(bytes(context_b), cand.bundle.context_bytes)
            self.assertEqual([bytes(p) for p in payloads], [cand.bundle.payloads[0][1]])
            self.assertEqual(bytes(payloads[0]), PAYLOAD + (b"v1" if v1 else b"v2"))
            self.assertEqual([bytes(m) for m in manifests], [raw for _k, raw in cand.bundle.manifests])
            self.assertEqual([bytes(e) for e in envelopes], [raw for _k, raw in cand.bundle.envelopes])
            self.assertEqual([bytes(w) for w in witnesses], [raw for _k, raw in cand.bundle.witnesses])
            self.assertIsNone(response)                                        # by digest: no registration response
            by_operation = self.get_sql(self.loader_conn(), None, op)
            self.assertEqual(bytes(by_operation[5]), saved.response_bytes)
            self.assertEqual([bytes(p) for p in by_operation[1]], [bytes(p) for p in payloads])

    def loader_conn(self):
        return self.loader


class ReleaseCase(LoaderCase):
    """`write_release(..., count_rows=False)` as the loader. The loader's connection sets its own search path (a session setting any role may
    change), because the projection names its tables unqualified. Each subclass has an install of its own (the tests write a release)."""

    def setUp(self):
        super().setUp()
        pk.insert_identity(self.owner, x.identity())              # the listings the observation tables reference (E11: the owner role)
        self.loader_session = self.conn("loader")
        self.loader_session.execute(f'SET search_path TO "{self.s}", pg_temp')

    @staticmethod
    def project(conn, count_rows):
        release, manifests, contents, calendars = rich_release(x.identity())
        return mds.write_release(conn, release, manifests, contents, calendars, count_rows=count_rows)

    def owner_counts(self):
        return {t: self.count(t) for t in MD_TABLES}


class LoaderWritesAReleaseTests(ReleaseCase):
    INSTALL = "loaderwrite"

    def test_the_loader_writes_an_invented_release_with_count_rows_false(self):
        self.assertEqual(self.owner_counts(), {t: 0 for t in MD_TABLES})
        result = self.project(self.loader_session, False)
        self.assertTrue(result.created)
        self.assertEqual(result.row_counts, ())                                # the read-back the loader may not do is not done
        self.assertEqual(self.owner_counts(), RICH_ROWS)                       # every one of the 13 tables received exactly its rows
        stored = self.owner.execute(f"SELECT projection_digest FROM {self.s}.md_release").fetchone()[0]
        self.assertEqual(stored, result.projection_digest)
        # The identical release again: idempotent, still no count, still no error (the idempotence check reads md_release only).
        again = self.project(self.loader_session, False)
        self.assertFalse(again.created)
        self.assertEqual((again.projection_digest, again.row_counts), (result.projection_digest, ()))
        self.assertEqual(self.owner_counts(), RICH_ROWS)


class LoaderDefaultCountTests(ReleaseCase):
    INSTALL = "loaderwrite3"

    def test_the_default_count_rows_needs_a_select_the_loader_does_not_hold(self):
        """The reason for the parameter, shown on the idempotent path (so that nothing is written twice): with the old default the loader's
        read-back of the per-table counts is refused (42501)."""
        self.project(self.loader_session, False)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.project(self.loader_session, True)
        self.assertEqual(self.owner_counts(), RICH_ROWS)                       # and nothing was written twice


class LoaderEqualsOwnerTests(ReleaseCase):
    INSTALL = "loaderwrite4"

    def test_the_loaders_projection_equals_the_owners(self):
        """Control: the same release written by the owner role of another install, with the default count, has the same digest and counts."""
        result = self.project(self.loader_session, False)
        other = KIT.install("loaderwrite5", w_seconds=4, kind="TEST")
        owner = other.connect("owner")
        self.addCleanup(owner.close)
        pk.insert_identity(owner, x.identity())
        owned = self.project(owner, True)
        self.assertEqual(owned.projection_digest, result.projection_digest)
        counts = dict(owned.row_counts)
        self.assertEqual(set(counts), set(MD_TABLES) - {"md_file"})
        self.assertEqual(counts, {t: RICH_ROWS[t] for t in counts})
        self.assertEqual(self.owner_counts(), RICH_ROWS)                       # the loader's rows are the owner's rows, table by table


class LoaderEntryTests(ReleaseCase):
    """R4a review LOW-7, closed by `persistence.real_loader.load_release` (pure half: test_real_loader). As the loader role, on a disposable install."""
    INSTALL = "loaderwrite7"

    def test_the_entry_writes_an_invented_release_as_the_loader_and_refuses_a_us_labelled_cn_reading_with_nothing_written(self):
        import test_marketdata_listing_market_gate as g
        from persistence import real_loader
        ident = x.identity()
        release, manifests, contents, calendars = rich_release(ident)
        result = real_loader.load_release(self.loader_session, release, manifests, contents, calendars, exchange_of=ident.exchange_mic)
        self.assertTrue(result.created)
        self.assertEqual(result.row_counts, ())
        self.assertEqual(self.owner_counts(), RICH_ROWS)
        # no identity: refused with no statement sent (the connection is never reached), the tables unchanged
        with self.assertRaises(real_loader.RealLoaderError):
            real_loader.load_release(self.loader_session, release, manifests, contents, calendars, exchange_of=None)
        # the refused real reading: nothing is written by the loader role, in any table
        gident = g.identity()                                    # in memory only: the refusal comes before any statement
        cn = g.kit.listing_id(gident, "609999", "XSHG")
        m, _payload = g.manifest("alphavantage.us", "609999.SHH", g.k.CNY, g.CN_ROWS, tag="loader-entry")
        bad = g.StoreContents((g.real_quote(cn, sha=m.file_sha256),), (), (), (), (), False, ())
        bad_release = g.MarketDataRelease(name="loader-entry", files=(m.file_sha256,), source_precedence=())
        with self.assertRaises(g.ProfileNotAdmittedError) as caught:
            real_loader.load_release(self.loader_session, bad_release, [m], bad, g.CalendarSet(), exchange_of=gident.exchange_mic)
        self.assertEqual(caught.exception.gate_code, g.prof.SOURCE_MARKET_NOT_COVERED)
        self.assertEqual(self.count("md_release", "release_id=%s", (bad_release.release_id,)), 0)
        self.assertEqual(self.count("md_file", "file_sha256=%s", (m.file_sha256,)), 0)
        self.assertEqual(self.count("md_quote"), RICH_ROWS["md_quote"])


class LoaderOutsideItsListTests(ReleaseCase):
    INSTALL = "loaderwrite6"

    def test_a_write_outside_the_list_is_refused(self):
        self.project(self.loader_session, False)
        for table in MD_TABLES:
            for statement in (UPDATES[table], f"DELETE FROM {table}", f"TRUNCATE {table}"):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege, msg=statement):
                    self.loader_session.execute(statement)
        self.assertEqual(self.owner_counts(), RICH_ROWS)                       # nothing changed


if __name__ == "__main__":
    import unittest
    unittest.main()
