"""Bring up a disposable TEST install for the real-mode app's browser tests (F1 R7). Not a test module: the name does not match `test*.py`.

    FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev \\
    FINWEB_PG_ADMIN_USER=<superuser of the development cluster> \\
    uv run --no-cache --no-sync --frozen --offline python tests/product/real_dev_env.py --contexts-file <path to a new file>

It runs in the FOREGROUND and owns one disposable database `finweb_it_rw_<hex8>` (the gateway kit of the R1 to R5 tests): the product installer's TEST
install, the invented world's identity rows (owner-seeded), one published `SYNTHETIC_TEST` context with its provenance candidate, and a fifth, account
role holding the identity and session tables and nothing else (created and granted by the product installer, PD-0078). It prints one JSON line (database, schema, roles, socket, contexts file,
context id, release id, listing id, as-of date), writes the launcher's contexts file (mode 0600, refused if it exists), and waits. Ctrl-C (or EOF on
stdin) drops the database and every role it created, by the kit's prefix rules; nothing outside that prefix is touched. It never creates a
`finweb_real*` database, cluster or role.

The executor and the account role are made PASSWORDLESS here (`ALTER ROLE ... PASSWORD NULL` in the disposable database), because the launcher over a
TEST target opens its connections with no credential (the same requirement as `dev_env.py`: the cluster must trust these roles on its Unix socket). The
script checks that by logging in as both before it reports success, and reports the reason if the cluster does not.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402

from real_gateway_kit import KIT  # noqa: E402
from real_r5_case import AS_OF, R5Case  # noqa: E402
from test_postgres_real_mode import account_role, contexts_json  # noqa: E402

VALID_SECONDS = 4 * 3600.0


class Env(R5Case):
    """A TestCase used as a plain object: `setUp` provisions through the kit exactly as the R5 tests do; `runTest` exists only so it can be built."""
    INSTALL = "r7env"
    W = 30
    ACCOUNT = True              # PD-0078: the fifth role, granted and audited by the product installer

    def runTest(self):                                   # pragma: no cover
        raise NotImplementedError


def write_new_private(path, text):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(text)


def passwordless(inst, socket, roles):
    """Make the two application roles passwordless in the disposable database and check that the cluster lets them in with no credential."""
    prov = inst.kit.prov
    with prov.admin(prov.database) as conn:
        for role in roles:
            conn.execute(sql.SQL("ALTER ROLE {} PASSWORD NULL").format(sql.Identifier(role)))
    for role in roles:
        try:
            probe = psycopg.connect(prov.dsn(prov.db, role, None), autocommit=True)
        except psycopg.Error as error:
            raise SystemExit("the cluster does not trust role %s on its socket without a credential (%s); the launcher over a TEST target needs that"
                             % (role, str(error).splitlines()[0]))
        probe.close()


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)          # the JSON line must reach a pipe or a log file at once, not at exit
    parser = argparse.ArgumentParser(prog="real_dev_env")
    parser.add_argument("--contexts-file", required=True, help="a path that does not exist yet; written 0600 and removed on exit")
    args = parser.parse_args(argv)
    path = Path(args.contexts_file).resolve()
    if path.exists():
        raise SystemExit("refusing to overwrite %s" % path)
    KIT.acquire()
    case = None
    try:
        if not KIT.ready:
            raise SystemExit("not provisioned: %s" % KIT.skip_reason)
        case = Env()
        case.setUp()
        live = case.fictional_live(valid_in=VALID_SECONDS, label="r7env")
        account, _password = account_role(case.inst)
        executor = case.inst.roles["executor"]
        passwordless(case.inst, os.environ.get("FINWEB_PG_SOCKET"), (executor, account))
        write_new_private(path, contexts_json(live))
        ready = json.dumps({
            "database": case.inst.kit.prov.db, "schema": case.s, "executor_role": executor, "account_role": account, "socket": os.environ.get("FINWEB_PG_SOCKET"),
            "contexts_file": str(path), "context_id": live.ctx, "release_id": live.snap.content["release"]["release_id"],
            "listing_id": str(case.fictional.listing_id), "as_of": AS_OF, "valid_for_seconds": VALID_SECONDS})
        # The same line goes to a file beside the contexts file (0600, removed on exit), so a reader that does not see the pipe in time can read it there.
        ready_path = Path(str(path) + ".ready.json")
        write_new_private(ready_path, ready + "\n")
        print(ready, flush=True)
        sys.stdout.flush()
        stop = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        threading.Thread(target=lambda: (sys.stdin.read(), stop.set()), daemon=True).start()
        stop.wait()
    finally:
        if case is not None:
            case.doCleanups()
        for leftover in (path, Path(str(path) + ".ready.json")):
            if leftover.is_file():
                leftover.unlink()
        KIT.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
