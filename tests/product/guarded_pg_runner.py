"""In-repo runner for the guarded PostgreSQL integration modules (F2 workspace, F3 HTTP, CSV report, R1 startup check).

Not a test module: the name does not match `test*.py`, so `unittest discover` never imports it.

Run (explicit arguments only; Unix socket only; the admin role must be a superuser able to CREATE ROLE and CREATE DATABASE):

    uv run --no-cache --no-sync --frozen --offline python tests/product/guarded_pg_runner.py \\
        --socket /tmp/finweb-cp7b-20261019/socket/.s.PGSQL.55419 --database finweb_dev --admin-user finweb_dev

Optional: `--modules workspace,http,report,startup` (default all four); `FINWEB_IT_ADMIN_PASSWORD` in the environment if the
cluster does not trust the admin role over the socket. No .env, DSN, TCP or network is consulted.

What it does
  1. Connects as the admin role to the named database and fails closed unless current_database() and current_user equal the
     arguments and the role is a superuser.
  2. Creates ONE disposable database `finweb_it_guarded_<random8>` (template0, UTF8, C locale; CREATE/TEMPORARY revoked from
     PUBLIC, as the frozen F2/F3 runtimes did) and, per module, one schema plus four roles named
     `finweb_it_guarded_<random8>_<ws|http|rpt|r1s>_<owner|executor|issuer|legacy>`: owner NOLOGIN, the others LOGIN with a
     random password; all NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT. A role is recorded for
     cleanup only after its CREATE ROLE succeeded (L-1).
     A separate database (not just a schema) is needed because test_c17 requires that CREATE TEMP TABLE is refused for the
     executor, which cannot be true in a shared database where PUBLIC holds TEMPORARY.
  3. As the schema owner (SET ROLE from the admin session) applies the real migrations and the product installers in order:
     install_guarded_workspace [-> install_guarded_http -> install_guarded_csv_report; R1 is mandatory for any F3 schema
     except the deliberate `startup` schema, which stops before R1],
     then exactly the grants the frozen
     runtimes applied (issuer USAGE on the schema; APP_GRANTS to executor and legacy). R1 adds only its own EXECUTE grants.
     The shared logic lives in `guarded_pg_provision.py`.
  4. Builds each module's CONFIG per its documented contract, assigns it to the imported module, runs it with unittest and
     prints per-module counts. A module that runs 0 tests, or skips any, is a failure of this runner.
  5. Always, in `finally`: closes its connections, terminates sessions on its own database, drops the database (WITH FORCE),
     then drops its roles, refusing any name without its own random prefix, and verifies nothing with that prefix remains.
Exit status is non-zero on any test failure/error/skip, provisioning error or cleanup error.

Module CONFIGs
  workspace: connect(role in executor|owner|issuer|legacy), schema, executor_conninfo, owner_role, issuer_role, executor_role,
             legacy_role.  (owner = admin session after SET ROLE owner; others log in as themselves.)
  http:      the above plus profile (FictionalProfile from web_api.guarded_dev.build_profile, ledger_digest injected, context
             published by the issuer with generation-1 RIGHTS) and app (create_app with guarded_dev.ORIGINS, i.e. origin
             http://127.0.0.1:5174 / host 127.0.0.1:8003). connect also accepts the full role names.
  report:    same as http, in its own schema (both F3 schemas carry F2 + HTTP add-on + R1).
  startup:   same as http, but the schema has F2 + HTTP add-on and NO R1 (the test installs R1 itself as the owner).
Nothing in this contract needs a physical PostgreSQL restart, so no test is skipped by design.
"""
from __future__ import annotations

import argparse
import importlib
import secrets
import sys
import traceback
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402

# Shared provisioning (also used by dev_env.py); the L-1 ordering lives there.
from guarded_pg_provision import KINDS, SESSION_OPTIONS, Provisioner  # noqa: E402,F401

PREFIX = "finweb_it_guarded_"
MODULES = {
    "workspace": dict(tag="ws", module="test_postgres_guarded_workspace", http=False),
    "http": dict(tag="http", module="test_postgres_guarded_http", http=True),
    "report": dict(tag="rpt", module="test_postgres_guarded_csv_report", http=True),
    "startup": dict(tag="r1s", module="test_postgres_guarded_r1_startup", http=True, r1=False),
}


class Runner(Provisioner):
    def __init__(self, socket, database, admin_user):
        self.run = secrets.token_hex(4)
        super().__init__(socket, database, admin_user, PREFIX + self.run)   # every object name must start with this

    def provision(self, spec):
        return self.provision_f3(spec["tag"], http=spec["http"], r1=spec.get("r1", True))

    # ---- CONFIG ----------------------------------------------------------
    def base_config(self, schema, roles, passwords):
        aliases = {**{v: k for k, v in roles.items()}, **{k: k for k in roles}}
        def connect(role):
            if role not in aliases:
                raise ValueError("unknown role for this module: " + str(role))
            kind = aliases[role]
            if kind == "owner":
                conn = psycopg.connect(self.dsn(self.db, self.admin_user, self.password), autocommit=True)
            else:
                conn = psycopg.connect(self.dsn(self.db, roles[kind], passwords[kind]), autocommit=True)
            self.connections.append(conn)
            try:
                if kind == "owner":
                    conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(roles["owner"])))
                conn.execute(sql.SQL("SET search_path TO {}, pg_temp").format(sql.Identifier(schema)))
            except BaseException:
                conn.close()
                raise
            return conn
        return dict(connect=connect, schema=schema,
            executor_conninfo=self.dsn(self.db, roles["executor"], passwords["executor"]),
            owner_role=roles["owner"], executor_role=roles["executor"], issuer_role=roles["issuer"], legacy_role=roles["legacy"])

    def http_config(self, config):
        from persistence.web_account_store import WebAccountStore
        from web_api import guarded_dev
        from web_api.app import create_app
        from web_api.auth import AuthSettings
        store = WebAccountStore(config["executor_conninfo"], config["schema"])
        profile = guarded_dev.build_profile(store, None)
        with config["connect"]("issuer") as conn:
            self.publish(conn, config["schema"], profile)
        app = create_app(account_store=store, auth_settings=AuthSettings.local(), enable_saved_synthetic=True,
            guarded_profile=profile, allowed_origins=guarded_dev.ORIGINS)
        return {**config, "profile": profile, "app": app}

    # ---- run one module ----------------------------------------------------
    def run_module(self, name):
        spec = MODULES[name]
        schema, roles, passwords = self.provision(spec)
        config = self.base_config(schema, roles, passwords)
        if spec["http"]:
            config = self.http_config(config)
        module = importlib.import_module(spec["module"])
        module.CONFIG = config
        try:
            suite = unittest.defaultTestLoader.loadTestsFromModule(module)
            result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
        finally:
            module.CONFIG = None
            if hasattr(module, "cleanup"):
                module.cleanup()
        ok = result.wasSuccessful() and result.testsRun > 0 and not result.skipped
        print("MODULE %-9s run=%d failures=%d errors=%d skipped=%d -> %s" % (
            name, result.testsRun, len(result.failures), len(result.errors), len(result.skipped), "PASS" if ok else "FAIL"))
        for case, reason in result.skipped:
            print("  SKIPPED %s: %s" % (case.id(), reason))
        return ok

    # ---- cleanup ---------------------------------------------------------
    def cleanup(self):
        self.close_connections()
        self.drop_objects(db_created=self.db_created, roles=self.created_roles)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the guarded PostgreSQL integration modules on disposable objects.")
    parser.add_argument("--socket", required=True, help="Unix socket FILE path, e.g. /tmp/x/socket/.s.PGSQL.55419")
    parser.add_argument("--database", required=True, help="existing database to administer from (must match current_database())")
    parser.add_argument("--admin-user", required=True, help="superuser that can CREATE ROLE and CREATE DATABASE")
    parser.add_argument("--modules", default=",".join(MODULES))
    args = parser.parse_args(argv)
    wanted = [m for m in args.modules.split(",") if m]
    if not wanted or any(m not in MODULES for m in wanted):
        parser.error("--modules must be a comma list from: " + ",".join(MODULES))
    runner = Runner(args.socket, args.database, args.admin_user)
    results = {}
    try:
        runner.preflight()
        runner.refuse_if_prefix_exists()
        print("run prefix", runner.own)
        runner.create_database()
        for name in wanted:
            try:
                results[name] = runner.run_module(name)
            except BaseException as exc:  # noqa: BLE001
                traceback.print_exc()
                print("MODULE %-9s PROVISIONING/RUN ERROR: %r" % (name, exc))
                results[name] = False
    except BaseException as exc:  # noqa: BLE001
        traceback.print_exc()
        setup_error = repr(exc)
    else:
        setup_error = None
    finally:
        runner.cleanup()
    if setup_error:
        print("ERROR setup:", setup_error)
    for error in runner.errors:
        print("ERROR", error)
    ok = bool(results) and all(results.values()) and len(results) == len(wanted) and not runner.errors and not setup_error
    print("RESULT", "PASS" if ok else "FAIL", {k: ("PASS" if v else "FAIL") for k, v in results.items()},
          "cleanup=" + ("OK" if not runner.errors else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
