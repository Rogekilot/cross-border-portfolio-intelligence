"""Bring up / tear down a disposable local development environment for the web app's browser tests.

Not a test module: the name does not match `test*.py`, so `unittest discover` never imports it.

    uv run --no-cache --no-sync --frozen --offline python tests/product/dev_env.py up \\
        --socket /tmp/finweb-cp7b-20261019/socket/.s.PGSQL.55419 --database finweb_dev --admin-user finweb_dev \\
        --runtime-dir /private/tmp/finweb-dev-env-1
    uv run --no-cache --no-sync --frozen --offline python tests/product/dev_env.py down \\
        --socket ... --database finweb_dev --admin-user finweb_dev --runtime-dir /private/tmp/finweb-dev-env-1

`FINWEB_IT_ADMIN_PASSWORD` in the environment if the cluster does not trust the admin role over the socket. The two
application roles (guarded executor, account app) are created WITHOUT a password, exactly like the existing CP7 application
role: the cluster must trust them over its private Unix socket, because `guarded_dev` and `account_dev` build passwordless
connection strings. `up` checks this by logging in as both before it reports success.

`up` creates, under ONE random prefix `finweb_dev_env_<hex8>`, and nothing else:
  * one database `finweb_dev_env_<hex8>` (template0, UTF8, C locale; CREATE/TEMPORARY revoked from PUBLIC);
  * a guarded F3 schema `<prefix>_f3` provisioned exactly as `guarded_pg_runner.py` does (real migrations, F2 installer, HTTP
    add-on, mandatory R1 report SQL, issuer USAGE, APP_GRANTS to executor and legacy), with roles `<prefix>_f3_owner` (NOLOGIN),
    `_f3_executor` (LOGIN, no password), `_f3_issuer` (LOGIN, random password kept only in memory), `_f3_legacy` (NOLOGIN); the
    issuer then publishes the fictional context and generation-1 rights the guarded app needs;
  * an account schema `<prefix>_acct` for `web_api.account_dev` with the real migrations and exactly APP_GRANTS for the NEW
    non-owner role `<prefix>_acct_app` (owner `<prefix>_acct_owner`, NOLOGIN). The retained `finweb_cp7*` schemas and
    `finweb_cp7_app` are never touched;
  * in the runtime directory (created 0700 if absent; must be empty if present): `app-config.json` (0600, the file
    `web_api.guarded_dev` validates) and `dev-env-state.json` (0600, the exact list of what was created, rewritten after each
    successful CREATE so a failed `up` can be torn down).
A failed `up` tears down whatever it had already created. `down` reads the state file, refuses anything whose name does not
fully match the recorded prefix, terminates sessions on the database, drops the database (WITH FORCE) and then the roles,
verifies nothing with the prefix is left, and removes `app-config.json` (a fixed name, only if it is a regular file we own; the
state file's `files` list is validated to hold nothing else and is never used as a path) and the state file (and the runtime directory if `up` created it and it is
then empty). Stop the servers first; `down` does not stop them.

Socket rule. `guarded_dev` formerly required the PostgreSQL socket to live inside its runtime directory, which a shared cluster
cannot satisfy. The config now records the real socket path and `guarded_dev` requires it to be an absolute resolved
`.s.PGSQL.<port>` Unix socket owned by the current user inside an owned 0700 directory. `up` applies that same check
(`guarded_dev._checked_socket`) before it creates anything. A cluster whose socket sits directly in the shared `/tmp`
(for example `/tmp/.s.PGSQL.5432`) can never pass it: the bootstrap needs a private-socket cluster such as the CP7 cluster.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402

from guarded_pg_provision import Provisioner  # noqa: E402

PREFIX = "finweb_dev_env_"
PREFIX_RE = re.compile(r"finweb_dev_env_[0-9a-f]{8}")
STATE_NAME = "dev-env-state.json"
STATE_SCHEMA = "finweb.dev_env_state/1"
CONFIG_NAME = "app-config.json"
DEV_PLAN = dict(owner="NOLOGIN", executor="NOPASSWORD", issuer="PASSWORD", legacy="NOLOGIN")
SOCKET_RE = re.compile(r"\.s\.PGSQL\.[0-9]{1,5}")


class DevEnvError(RuntimeError):
    pass


# ---- filesystem helpers ---------------------------------------------------------------------------------------------
def write_private(path, data, *, replace=False):
    """Write a 0600 file owned by us; never follow a symlink. `replace` swaps atomically (state file)."""
    target = Path(str(path) + ".tmp") if replace else Path(path)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(descriptor, data)
    finally:
        os.close(descriptor)
    if replace:
        os.replace(target, path)


def check_runtime_dir(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise DevEnvError("runtime directory must be an owned 0700 directory: %s" % path)


def resolve_runtime(raw):
    path = Path(raw)
    if not path.is_absolute():
        raise DevEnvError("--runtime-dir must be absolute")
    resolved = path.resolve()
    if resolved != path:
        print("note: --runtime-dir resolved to %s (no symlink components are accepted)" % resolved, file=sys.stderr)
    return resolved


def check_socket(value):
    path = Path(value)
    if not path.is_absolute() or SOCKET_RE.fullmatch(path.name) is None:
        raise DevEnvError("--socket must be an absolute .s.PGSQL.<port> path")
    if not path.exists() or not stat.S_ISSOCK(path.lstat().st_mode):
        raise DevEnvError("--socket is not a Unix socket: %s" % path)
    return str(path.resolve())


def require_private_socket(socket):
    """L-2: apply the launcher's own startup rule (guarded_dev._checked_socket) BEFORE anything is provisioned, so a cluster
    the launcher would refuse (for example one whose socket sits directly in the shared /tmp) creates nothing."""
    from web_api import guarded_dev
    try:
        guarded_dev._checked_socket(socket)
    except ValueError as exc:
        raise DevEnvError("REFUSED: the guarded launcher would not accept this socket (%s). The bootstrap needs a cluster whose "
                          "socket lives in an owned 0700 directory, such as the CP7 cluster; nothing was created: %s" % (exc, socket)) from exc


# ---- state ----------------------------------------------------------------------------------------------------------
class State:
    def __init__(self, runtime, socket, admin_database, admin_user, prefix):
        self.path = runtime / STATE_NAME
        self.data = dict(schema=STATE_SCHEMA, prefix=prefix, socket=socket, admin_database=admin_database, admin_user=admin_user,
            runtime_dir=str(runtime), runtime_created=False, db_created=False, database=None, roles=[], schemas=[], files=[])

    def save(self):
        write_private(self.path, (json.dumps(self.data, indent=2, sort_keys=True) + "\n").encode(), replace=True)

    def record(self, kind, name):
        """Called by the provisioner AFTER the object exists (L-1)."""
        if kind == "database":
            self.data["database"], self.data["db_created"] = name, True
        elif kind == "role":
            self.data["roles"].append(name)
        elif kind == "schema":
            self.data["schemas"].append(name)
        self.save()


def load_state(runtime):
    path = runtime / STATE_NAME
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 65536:
            raise DevEnvError("state file must be an owned 0600 regular file")
        raw = os.read(descriptor, 65537)
    finally:
        os.close(descriptor)
    data = json.loads(raw)
    keys = {"schema", "prefix", "socket", "admin_database", "admin_user", "runtime_dir", "runtime_created", "db_created", "database", "roles", "schemas", "files"}
    if (not isinstance(data, dict) or set(data) != keys or data["schema"] != STATE_SCHEMA or PREFIX_RE.fullmatch(str(data["prefix"])) is None
            or data["runtime_dir"] != str(runtime)):
        raise DevEnvError("state file does not describe this runtime directory")
    own = re.escape(data["prefix"]) + r"(_[a-z0-9_]+)?"
    names = list(data["roles"]) + list(data["schemas"]) + ([data["database"]] if data["database"] else [])
    if any(not isinstance(n, str) or re.fullmatch(own, n) is None for n in names):
        raise DevEnvError("REFUSED: state file names an object outside its prefix")
    if not isinstance(data["files"], list) or any(item != CONFIG_NAME for item in data["files"]):
        raise DevEnvError("REFUSED: state file names a file other than %s" % CONFIG_NAME)
    if data["database"] not in (None, data["prefix"]) or bool(data["db_created"]) != (data["database"] is not None):
        raise DevEnvError("state file database differs from its prefix")
    return data


# ---- teardown (shared by `down` and a failed `up`) -------------------------------------------------------------------
def teardown(runtime, data):
    errors = []
    if data["db_created"] or data["roles"]:      # otherwise nothing was created on the cluster: do not even connect
        prov = Provisioner(data["socket"], data["admin_database"], data["admin_user"], data["prefix"])
        try:
            prov.drop_objects(db_created=bool(data["db_created"]), roles=data["roles"])
        finally:
            prov.close_connections()
        errors = list(prov.errors)
    if errors:
        return errors
    # L-1: the only file `up` creates besides the state file is the fixed-name config. Nothing is read from the state file.
    config = runtime / CONFIG_NAME
    try:
        info = config.lstat()
    except FileNotFoundError:
        info = None
    if info is not None:
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            return ["REFUSED: %s is not a regular file owned by the current user; it was left in place" % config]
        os.unlink(config)
    state_path = runtime / STATE_NAME
    if state_path.exists():
        os.unlink(state_path)
    if data["runtime_created"]:
        try:
            os.rmdir(runtime)
        except OSError as exc:
            print("note: runtime directory not removed (%s)" % exc.strerror, file=sys.stderr)
    return []


# ---- up -------------------------------------------------------------------------------------------------------------
def commands(runtime, socket, database, acct_schema, acct_app):
    uv = "uv run --no-cache --no-sync --frozen --offline"
    chrome = '"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"'
    return "\n".join([
        "# 1. account API (accounts + saved made-up portfolios), 127.0.0.1:8000",
        "FINWEB_CP7_PG_SOCKET=%s FINWEB_CP7_PG_DATABASE=%s FINWEB_CP7_PG_USER=%s FINWEB_CP7_PG_SCHEMA=%s \\" % (socket, database, acct_app, acct_schema),
        "  PYTHONPATH=src %s uvicorn web_api.account_dev:app --host 127.0.0.1 --port 8000" % uv,
        "# 2. guarded F3 API, 127.0.0.1:8003",
        "FINWEB_F3_RUNTIME_DIR=%s PYTHONPATH=src \\" % runtime,
        "  %s uvicorn web_api.guarded_dev:create_local_app --factory --host 127.0.0.1 --port 8003" % uv,
        "# 3. Vite, normal config, 127.0.0.1:5173 (proxies /api to 8000)",
        "(cd web && ./node_modules/.bin/vite)",
        "# 4. Vite, guarded F3 config, 127.0.0.1:5174 (proxies /api to 8003)",
        "(cd web && ./node_modules/.bin/vite --config vite.f3.config.ts)",
        "# 5. Playwright (guarded-flow.spec.ts needs servers 2 and 4; the other specs need servers 1 and 3)",
        "#    SIGN-UP LIMIT: the product allows 10 sign-ups per peer per 15 minutes per account store (not weakened for tests).",
        "#    One full run uses 9 on the account API (account-flow 4; analytics, csv, workspace, real-source-flow, real-source-focus 1",
        "#    each) and 3 on the guarded API (owner, other, rpt). Run the suite ONCE per `up`; to run it again within 15 minutes,",
        "#    run `down` and then `up` (a new schema, so a fresh counter). A 429 AUTH_RATE_LIMITED here is this limit, not a defect.",
        "(cd web && FINWEB_CHROMIUM_EXECUTABLE_PATH=%s FINWEB_WEB_BASE_URL=http://127.0.0.1:5173 \\" % chrome,
        "  ./node_modules/.bin/playwright test e2e/guarded-flow.spec.ts)",
        "(cd web && FINWEB_CHROMIUM_EXECUTABLE_PATH=%s FINWEB_WEB_BASE_URL=http://127.0.0.1:5173 \\" % chrome,
        "  ./node_modules/.bin/playwright test --grep-invert 'guarded')",
        "# 6. after stopping all four servers",
        "%s python tests/product/dev_env.py down --socket %s --database <admin database> --admin-user <admin user> --runtime-dir %s" % (uv, socket, runtime),
    ])


def up(args):
    runtime = resolve_runtime(args.runtime_dir)
    socket = check_socket(args.socket)
    require_private_socket(socket)
    runtime_created = False
    if runtime.exists():
        check_runtime_dir(runtime)
        if any(runtime.iterdir()):
            raise DevEnvError("REFUSED: runtime directory is not empty (run `down` first?): %s" % runtime)
    else:
        if not runtime.parent.is_dir():
            raise DevEnvError("parent of --runtime-dir must exist: %s" % runtime.parent)
        os.mkdir(runtime, 0o700)
        runtime_created = True
        check_runtime_dir(runtime)
    prefix = PREFIX + secrets.token_hex(4)
    state = State(runtime, socket, args.database, args.admin_user, prefix)
    state.data["runtime_created"] = runtime_created
    state.save()
    prov = Provisioner(socket, args.database, args.admin_user, prefix)
    prov.on_created = state.record
    try:
        prov.preflight()
        prov.refuse_if_prefix_exists()
        prov.create_database()
        f3_schema, roles, passwords = prov.provision_f3("f3", http=True, plan=DEV_PLAN)
        acct_schema, _acct_owner, acct_app = prov.provision_account("acct")
        config = build_config(prov, runtime, state, socket, f3_schema, roles, passwords)
        verify(prov, runtime, socket, config, acct_schema, acct_app)
        state.data["runtime_created"] = runtime_created
        state.save()
    except BaseException:
        traceback.print_exc()
        prov.close_connections()
        print("up FAILED; tearing down what was created", file=sys.stderr)
        errors = teardown(runtime, state.data)
        for error in errors:
            print("ERROR", error, file=sys.stderr)
        raise
    prov.close_connections()
    print("UP OK prefix=%s database=%s runtime=%s" % (prefix, prefix, runtime))
    print("Created: database %s; schemas %s; roles %s" % (prefix, ", ".join(state.data["schemas"]), ", ".join(state.data["roles"])))
    print("Files: %s, %s\n" % (runtime / CONFIG_NAME, runtime / STATE_NAME))
    print(commands(runtime, socket, prefix, acct_schema, acct_app))
    return 0


def build_config(prov, runtime, state, socket, f3_schema, roles, passwords):
    from persistence.web_account_store import WebAccountStore
    from web_api import guarded_dev
    probe = dict(socket=socket, database=prov.db, executor_role=roles["executor"])
    store = WebAccountStore(guarded_dev.executor_dsn(probe), f3_schema)
    profile = guarded_dev.build_profile(store, None)
    issuer = psycopg.connect(prov.dsn(prov.db, roles["issuer"], passwords["issuer"]), autocommit=True)
    prov.connections.append(issuer)
    issuer.execute(sql.SQL("SET search_path TO {}, pg_temp").format(sql.Identifier(f3_schema)))
    prov.publish(issuer, f3_schema, profile)
    config = dict(schema="finweb.f3.app_config/1", socket=socket, database=prov.db, product_schema=f3_schema,
        executor_role=roles["executor"], context_id=profile.context_id)
    state.data["files"].append(CONFIG_NAME)      # recorded first so a failed write is still cleaned up
    state.save()
    write_private(runtime / CONFIG_NAME, (json.dumps(config, indent=2, sort_keys=True) + "\n").encode())
    return config


def verify(prov, runtime, socket, config, acct_schema, acct_app):
    """Re-read everything the way the two launchers will, before reporting success."""
    from persistence.connection import build_conninfo
    from persistence.web_account_store import WebAccountStore
    from web_api import guarded_dev
    previous = os.environ.get(guarded_dev.RUNTIME_ENV)
    os.environ[guarded_dev.RUNTIME_ENV] = str(runtime)
    try:
        loaded = guarded_dev.load_config()
    finally:
        if previous is None:
            os.environ.pop(guarded_dev.RUNTIME_ENV, None)
        else:
            os.environ[guarded_dev.RUNTIME_ENV] = previous
    if loaded != config:
        raise DevEnvError("guarded_dev.load_config differs from the configuration just written")
    store = WebAccountStore(guarded_dev.executor_dsn(loaded), loaded["product_schema"])
    try:
        guarded_dev.require_report_installed(store)
        guarded_dev.build_profile(store, loaded["context_id"])
    except psycopg.OperationalError as exc:
        raise DevEnvError("the guarded executor role could not log in without a password; the cluster must trust it over the "
                          "Unix socket (%s)" % str(exc).strip()) from exc
    account = WebAccountStore(build_conninfo(socket=socket, dbname=prov.db, user=acct_app), acct_schema)
    try:
        account.connect().close()
    except psycopg.OperationalError as exc:
        raise DevEnvError("the account application role could not log in without a password; the cluster must trust it over the "
                          "Unix socket (%s)" % str(exc).strip()) from exc


# ---- down -----------------------------------------------------------------------------------------------------------
def down(args):
    runtime = resolve_runtime(args.runtime_dir)
    check_runtime_dir(runtime)
    data = load_state(runtime)
    if data["socket"] != check_socket(args.socket) or data["admin_database"] != args.database or data["admin_user"] != args.admin_user:
        raise DevEnvError("REFUSED: --socket/--database/--admin-user differ from the ones `up` recorded")
    errors = teardown(runtime, data)
    if errors:
        for error in errors:
            print("ERROR", error, file=sys.stderr)
        print("DOWN FAILED; the state file is kept so `down` can be retried", file=sys.stderr)
        return 1
    print("DOWN OK: dropped database %s and %d role(s); nothing with prefix %s remains" % (data["prefix"], len(data["roles"]), data["prefix"]))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Disposable local development environment (guarded F3 + account schemas).")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("up", "down"):
        item = sub.add_parser(name)
        item.add_argument("--socket", required=True, help="Unix socket FILE path inside an owned 0700 directory, e.g. /tmp/x/socket/.s.PGSQL.55419 "
                            "(`up` refuses a socket directly in /tmp; use a private-socket cluster such as the CP7 cluster)")
        item.add_argument("--database", required=True, help="existing database to administer from (must match current_database())")
        item.add_argument("--admin-user", required=True, help="superuser that can CREATE ROLE and CREATE DATABASE")
        item.add_argument("--runtime-dir", required=True, help="absolute directory for app-config.json and the state file")
    args = parser.parse_args(argv)
    try:
        return up(args) if args.command == "up" else down(args)
    except (RuntimeError, ValueError, OSError, psycopg.Error) as exc:
        print("ERROR %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
