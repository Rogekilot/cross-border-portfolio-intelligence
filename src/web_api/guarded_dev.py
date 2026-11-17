"""Local F3 launcher; explicit owned config, executor only, no .env.

The runtime directory is named explicitly by `FINWEB_F3_RUNTIME_DIR`; there is no default. A missing variable, a missing
directory or a missing `app-config.json` refuses to start. `tests/product/dev_env.py up` creates the directory, the
disposable database and the configuration.
"""
from __future__ import annotations

import json
import os
from contextlib import closing
from pathlib import Path
import re
import secrets
import stat

from persistence.connection import build_conninfo
from performance.ledger_view import ledger_digest
from persistence.guarded_http_store import build_fictional_profile
from persistence.guarded_workspace_context import GuardedWorkspaceError
from persistence.web_account_store import WebAccountStore
from web_api.app import create_app
from web_api.auth import AuthSettings

RUNTIME_ENV = "FINWEB_F3_RUNTIME_DIR"
CONFIG_NAME = "app-config.json"
ORIGINS = frozenset(("http://127.0.0.1:8003", "http://127.0.0.1:5174"))
CONFIG_KEYS = {"schema", "socket", "database", "product_schema", "executor_role", "context_id"}
# The only database/schema/role names this launcher serves: one disposable dev-environment set, tied together by one tag.
DATABASE_NAME = re.compile(r"finweb_dev_env_[0-9a-f]{8}")
SOCKET_NAME = re.compile(r"\.s\.PGSQL\.[0-9]{1,5}")
# The four R1 report functions the guarded facade calls. Without them every guarded write fails at its first statement.
REPORT_FUNCTIONS = ("gh_csv_report_precheck(uuid,uuid)", "gh_csv_report_read(uuid,uuid,text,uuid,uuid,text)",
    "gh_csv_report_list(uuid,uuid,text)", "gh_csv_report_commit(bytea,bytea,bytea)")


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError("Duplicate F3 config field")
        value[key] = item
    return value


def runtime_dir():
    raw = os.environ.get(RUNTIME_ENV)
    if not raw:
        raise ValueError("F3_RUNTIME_DIR_REQUIRED: set %s to the runtime directory created by tests/product/dev_env.py up" % RUNTIME_ENV)
    path = Path(raw)
    if not path.is_absolute() or path != path.resolve():
        raise ValueError("F3 runtime directory must be an absolute, fully resolved path (no symlink components)")
    return path


def config_path():
    return runtime_dir() / CONFIG_NAME


def _private_dir(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("Owned private F3 runtime required")


def _checked_socket(value):
    """The socket file the config names must be an absolute resolved `.s.PGSQL.<port>` path inside an owned 0700 directory.

    The old rule "socket inside the runtime directory" is replaced by "socket inside an owned private directory"; the config
    records the real path. A cluster whose socket sits directly in the shared /tmp (for example /tmp/.s.PGSQL.5432) can never
    pass, because /tmp is not an owned 0700 directory. The bootstrap needs a private-socket cluster such as the CP7 cluster,
    and `dev_env up` applies this same check before it creates anything."""
    if type(value) is not str:
        raise ValueError("F3 configuration differs from the fixed fictional runtime")
    socket = Path(value)
    if not socket.is_absolute() or socket != socket.resolve() or SOCKET_NAME.fullmatch(socket.name) is None:
        raise ValueError("F3 socket must be an absolute resolved .s.PGSQL.<port> path")
    _private_dir(socket.parent)
    info = socket.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("F3 socket must be a Unix socket owned by the current user")
    return value


def load_config(path=None):
    expected = config_path()
    if path is not None and Path(path) != expected:
        raise ValueError("Only the explicitly named F3 app configuration is supported")
    runtime = expected.parent
    _private_dir(runtime)
    descriptor = os.open(expected, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 4096:
            raise ValueError("Owned bounded0600 configuration required")
        raw = os.read(descriptor, 4097)
    finally:
        os.close(descriptor)
    value = json.loads(raw, object_pairs_hook=_pairs)
    if (type(value) is not dict or set(value) != CONFIG_KEYS or value["schema"] != "finweb.f3.app_config/1"
            or type(value["database"]) is not str or DATABASE_NAME.fullmatch(value["database"]) is None
            or value["product_schema"] != value["database"] + "_f3"
            or value["executor_role"] != value["database"] + "_f3_executor"
            or type(value["context_id"]) is not str or re.fullmatch("[0-9a-f]{64}", value["context_id"]) is None):
        raise ValueError("F3 configuration differs from the fixed fictional runtime")
    _checked_socket(value["socket"])
    return value


def executor_dsn(config):
    # Existing WebAccountStore.connect enforces15000ms; declare that actual cap.
    return build_conninfo(socket=config["socket"], dbname=config["database"], user=config["executor_role"]) + " passfile=/dev/null sslmode=disable gssencmode=disable connect_timeout=2 options='-c timezone=UTC -c statement_timeout=15000 -c lock_timeout=3000'"


def require_report_installed(store):
    """Refuse to start unless the R1 report SQL is installed and executable by the executor (M-3).

    Per-request behaviour is unchanged (a missing function still fails closed with a storage error); this only turns a
    deployment mistake into a startup refusal with its own code instead of a permanent UNKNOWN on the first write."""
    schema = store.schema
    with closing(store.connect()) as conn:
        for signature in REPORT_FUNCTIONS:
            qualified = '"' + schema + '".' + signature
            row = conn.execute("SELECT CASE WHEN to_regprocedure(%s) IS NULL THEN false "
                "ELSE has_function_privilege(current_user, to_regprocedure(%s)::oid, 'EXECUTE') END", (qualified, qualified)).fetchone()
            if row is None or row[0] is not True:
                raise GuardedWorkspaceError("F3_CSV_REPORT_NOT_INSTALLED",
                    "The CSV report SQL (%s) is not installed or not executable for the application role" % signature.split("(")[0])


def build_profile(store, context_id):
    """The fictional profile with the engine's ledger digest injected (persistence may not import `performance`)."""
    return build_fictional_profile(store, expected_context=context_id, preview_key=secrets.token_bytes(32),
        ledger_digest=ledger_digest)


def create_local_app():
    for key in tuple(os.environ):
        if key.startswith("PG") or key.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
            del os.environ[key]
    os.environ.update(PGSERVICEFILE="/dev/null", PGSYSCONFDIR="/dev/null", PSYCOPG_IMPL="binary", TZ="UTC")
    config = load_config()
    store = WebAccountStore(executor_dsn(config), config["product_schema"])
    require_report_installed(store)
    profile = build_profile(store, config["context_id"])
    return create_app(account_store=store, auth_settings=AuthSettings.local(), enable_saved_synthetic=True,
        guarded_profile=profile, allowed_origins=ORIGINS)
