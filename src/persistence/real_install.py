"""F1 R6: the REAL installer (design 1.2 rule 5.1 and 7, section 1 item 3; E8, E24).

RUN ONLY BY THE OWNER, in the owner's own terminal, as the cluster's superuser, typing its password at a prompt. It installs the real database
and writes install kind `REAL` and NO OTHER: there is no kind parameter and no TEST mode. The TEST provisioner (`tests/product/guarded_pg_provision.py`)
is a different tool and writes `TEST` only. This tool is not imported by any runtime path and no agent session runs it (an agent holds no superuser
password: rule 2).

    real_install phase0 --socket DIR/.s.PGSQL.PORT --user SUPERUSER
    real_install phase1 --socket ...  --user ...  --loader-login {login,nologin}
    real_install phase2 --socket ...  --user ...
    real_install check  --socket ...  --user ...

PHASE 0   Writes nothing. The checks that can be made before anything exists (the probe, Pass S, the server's settings, the hba rows, the roles
          and databases that are there), `decide(..., phase="0")`. Phase 1 runs it first and creates nothing if it refuses.
PHASE 1   Creates the database, the five roles (PD-0078 added `account`; no password: the owner sets each with psql's `\\password`), the revokes of PUBLIC's CONNECT on
          every other connectable database of the cluster, the schema, the migrations and the gateway, and writes the kind row `REAL` last.
          NO CONTENT: no market data, no snapshot, no record. It is a sequence of statements and not one transaction (`CREATE DATABASE` cannot run in
          a transaction block): a failure partway leaves what had run, and this tool says so (rule 7). Re-running over a partial install is not claimed.
PHASE 2   After the owner has set the passwords. Writes nothing. Every check, including the verifiers and the catalog audit
          (`real_catalog_audit.audit(as_kind="REAL")`, R3's function) against the REAL database: the first and only read of a REAL catalog, at R8
          step 1. A refusal here comes AFTER Phase 1 created the install (rule 7); the owner waits for a reviewed fix and re-runs `check`, or drops and
          reinstalls, or approves SQL in the existing database.
CHECK     Phase 2's checks, read-only, on demand (after a change of `pg_hba.conf`, roles or grants, and after a later migration plus the revoke).

WHAT IT TAKES FROM WHERE. Its file list is `real_roles.sql_files("REAL")` and its grants are `real_roles.grant_statements("REAL", ...)`, both applied
by `real_workspace_store._install_gateway_body(kind="REAL")`; it never names the TEST-only part's file (R6's static test). Its credentials come from the
terminal prompt only: no option, no file, no environment variable.
"""
from __future__ import annotations

from dataclasses import dataclass
import sys

from persistence import prompt_route, real_catalog_audit, real_preflight as pf, real_roles
from persistence.real_workspace_context import RealWorkspaceError, identifier
from persistence.real_workspace_store import _check_install_inputs, _install_gateway_body

EXIT_OK, EXIT_REFUSED, EXIT_FAILED_PARTWAY = 0, 2, 4
ROLE_FLAGS = "NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"


@dataclass(frozen=True)
class InstallNames:
    database: str
    schema: str
    owner: str
    executor: str
    loader: str
    publisher: str
    account: str          # PD-0078: the fifth role, which holds the web accounts and nothing else

    def validated(self):
        for value in (self.database, self.schema, self.owner, self.executor, self.loader, self.publisher, self.account):
            identifier(value)
        return self


REAL_NAMES = InstallNames(pf.REAL_DATABASE, pf.REAL_SCHEMA, pf.REAL_ROLES["owner"], pf.REAL_ROLES["executor"], pf.REAL_ROLES["loader"],
                          pf.REAL_ROLES["publisher"], pf.REAL_ROLES["account"])


# ---- Phase 1 as statements: pure, so that the test reads exactly what would run --------------------------------------------------------
def role_statements(names, loader_login):
    """CREATE ROLE for the five roles (PD-0078 added the account role). NO PASSWORD anywhere: the owner sets each with `\\password` in their own
    terminal, and a role without one cannot log in over scram (`auth-password`). The owner is NOLOGIN; the loader is created LOGIN or NOLOGIN as the
    owner decided (R6 plan, OPEN); the account role is LOGIN."""
    if loader_login not in ("login", "nologin"):
        raise RealWorkspaceError("RW_SHAPE", "the loader's login state is chosen explicitly: login or nologin")
    n = names.validated()
    return ['CREATE ROLE "%s" NOLOGIN %s' % (n.owner, ROLE_FLAGS), 'CREATE ROLE "%s" LOGIN %s' % (n.executor, ROLE_FLAGS),
            'CREATE ROLE "%s" %s %s' % (n.loader, "LOGIN" if loader_login == "login" else "NOLOGIN", ROLE_FLAGS),
            'CREATE ROLE "%s" LOGIN %s' % (n.publisher, ROLE_FLAGS), 'CREATE ROLE "%s" LOGIN %s' % (n.account, ROLE_FLAGS)]


def database_statements(names, other_databases):
    """The database, its connection barrier (1 item 2) and the revoke of PUBLIC's CONNECT on every other connectable database (1.2 rule 3)."""
    n = names.validated()
    q = '"%s"' % n.database
    out = ["CREATE DATABASE %s TEMPLATE template0 ENCODING 'UTF8' LOCALE_PROVIDER libc LC_COLLATE 'C' LC_CTYPE 'C'" % q,
           "REVOKE ALL ON DATABASE %s FROM PUBLIC" % q,
           'GRANT CONNECT ON DATABASE %s TO "%s", "%s", "%s", "%s", "%s"' % (q, n.owner, n.executor, n.loader, n.publisher, n.account)]
    for other in sorted(other_databases):
        if other != n.database:
            out.append('REVOKE CONNECT ON DATABASE "%s" FROM PUBLIC' % identifier(other))
    return out


def schema_statements(names):
    n = names.validated()
    return ["REVOKE CREATE ON SCHEMA public FROM PUBLIC", 'CREATE SCHEMA "%s" AUTHORIZATION "%s"' % (n.schema, n.owner)]


def install_in_database(conn, names, *, w_seconds=pf.REAL_W_SECONDS, say=print):
    """Inside the real database, on the SUPERUSER's connection (autocommit): the schema, the migrations as the owner, the gateway (the CORE file
    list and the REAL role lists, `kind="REAL"`) and the install-kind row `REAL`, last, in the gateway's transaction. Writes no content."""
    from persistence.migrator import apply_migrations, load_migrations
    n = names.validated()
    for statement in schema_statements(n):
        conn.execute(statement)
        say("  ran: " + statement)
    conn.execute('SET ROLE "%s"' % n.owner)
    conn.execute('SET search_path TO "%s", pg_temp' % n.schema)
    migrations = load_migrations()
    applied = apply_migrations(conn, migrations)
    if applied != [m.filename for m in migrations]:
        raise RealWorkspaceError("RW_INSTALL_MIGRATIONS_MISSING", "the migration history differs from the product migrations")
    say("  applied %d migrations" % len(applied))
    checked = _check_install_inputs(n.schema, n.owner, n.executor, n.loader, n.publisher, w_seconds, n.account)
    with conn.transaction():
        _install_gateway_body(conn, checked, n.owner, n.executor, n.loader, n.publisher, kind="REAL", account_role=n.account)
        conn.execute('INSERT INTO "%s".rw_install(singleton,kind,w_seconds) VALUES(true,\'REAL\',%%s)' % n.schema, (w_seconds,))
    conn.execute("RESET ROLE")
    say("  gateway installed (file list %s), install kind row REAL written" % ", ".join(real_roles.sql_files("REAL")))


# ---- the phases ------------------------------------------------------------------------------------------------------------------------
def _audit_fn(conn, names):
    def run():
        result = real_catalog_audit.audit(conn, names.schema, names.owner, names.executor, names.loader, names.publisher, as_kind="REAL",
                                          account_role=names.account)
        return result.findings
    return run


def run_checks(conn, args_socket, *, phase, names=REAL_NAMES, say=print, environ=None, home=None, prober=None, sysconfdir=None):
    """Gather the facts at the superuser's vantage and judge them. Writes nothing. Returns the `Decision`."""
    audit = _audit_fn(conn, names) if phase in ("2", "check") else None
    roles = {"owner": names.owner, "executor": names.executor, "loader": names.loader, "publisher": names.publisher, "account": names.account}
    facts = pf.gather_facts(conn, vantage="installer", database=names.database if phase != "0" else "postgres", socket=args_socket, phase=phase,
                            environ=environ, home=home, prober=prober,
                            sysconfdir=sysconfdir if sysconfdir is not None else pf.installation_sysconfdir(), audit=audit, real_roles=roles,
                            real_database=names.database)
    decision = pf.decide(facts, vantage="installer", phase=phase, real_roles=roles, real_database=names.database)
    for line in decision.lines:
        say(line)
    return decision


def other_connectable_databases(conn, names):
    return [r[0] for r in conn.execute("SELECT datname::text FROM pg_database WHERE datallowconn AND datname<>%s ORDER BY 1", (names.database,)).fetchall()]


def phase1(admin_conn, open_real_database, socket, *, loader_login, names=REAL_NAMES, say=print, **check_kw):
    """Phase 0, then (only if it passes) Phase 1. `admin_conn`: the superuser's autocommit connection to a maintenance database;
    `open_real_database()` opens the superuser's autocommit connection to the new database. Returns an exit status."""
    say("== Phase 0: checks before anything is created ==")
    decision = run_checks(admin_conn, socket, phase="0", names=names, say=say, **check_kw)
    if not decision.ok:
        say("Phase 0 refused: nothing was created.")
        return EXIT_REFUSED
    others = other_connectable_databases(admin_conn, names)
    steps = role_statements(names, loader_login) + database_statements(names, others)
    say("== Phase 1: creating the real database, the five roles and the gateway (no content) ==")
    done = []
    try:
        for statement in steps:
            admin_conn.execute(statement)
            done.append(statement)
            say("  ran: " + statement)
        real = open_real_database()
        try:
            install_in_database(real, names, say=say)
        finally:
            real.close()
    except Exception as error:      # noqa: BLE001 - report exactly what ran, whatever failed
        say("PHASE 1 FAILED PARTWAY (%s): %d statement(s) of the cluster-level steps ran; the real database, some or all of the five roles, part of the "
            "gateway and the revokes of PUBLIC's CONNECT done so far STAY. No content is held. Nothing is used until a reviewed fix: wait for it, then "
            "drop the real database and the roles (they hold no content) and re-run, or approve SQL in the existing database. Re-running Phase 1 over a "
            "partial install is not claimed." % (type(error).__name__, len(done)))
        return EXIT_FAILED_PARTWAY
    say("Phase 1 done. NEXT, in your own terminal as the superuser, set each password with psql's \\password (never a literal PASSWORD statement):")
    to_set = {"publisher": names.publisher, "executor": names.executor, "loader": names.loader, "account": names.account}
    for who in ("publisher", "executor", "account") + (("loader",) if loader_login == "login" else ()):
        say("    \\password %s" % to_set[who])
    say("then run:  real_install phase2 --socket ... --user ...")
    return EXIT_OK


def phase2(open_real_database, socket, *, phase="2", names=REAL_NAMES, say=print, **check_kw):
    """Phase 2 or `check`: every check, read-only, against the REAL database, the catalog audit included."""
    say("== %s: read-only checks against the real database ==" % ("Phase 2" if phase == "2" else "check"))
    conn = open_real_database()
    try:
        decision = run_checks(conn, socket, phase=phase, names=names, say=say, **check_kw)
    finally:
        conn.close()
    return EXIT_OK if decision.ok else EXIT_REFUSED


# ---- the command line ------------------------------------------------------------------------------------------------------------------
def _build_parser():
    import argparse
    parser = argparse.ArgumentParser(prog="real_install", description="The real installer (owner only; REAL installs only; superuser password at a prompt).")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("phase0", "phase1", "phase2", "check"):
        p = sub.add_parser(name)
        p.add_argument("--socket", required=True, help="the cluster's Unix socket, <dir>/.s.PGSQL.<port>")
        p.add_argument("--user", required=True, help="the cluster's superuser")
        if name == "phase1":
            p.add_argument("--loader-login", required=True, choices=("login", "nologin"),
                           help="whether Phase 1 creates the loader with LOGIN or NOLOGIN (an owner decision, no default)")
    return parser


def _remembered(prompt):
    """One prompt per run: the answer is kept in memory for the length of the process and written nowhere."""
    cache = {}

    def ask(role):
        if role not in cache:
            cache[role] = prompt(role)
        return cache[role]
    return ask


def main(argv=None, *, prompt=None, out=None, connect=None):
    """`prompt(role)` is the credential seam (default: the terminal prompt). `connect(socket, database, user)` is a seam for the tests of the
    command line (default: a scram-only connection with `require_auth`)."""
    args = _build_parser().parse_args(argv)
    say = (lambda text: print(text, file=out)) if out is not None else print
    try:
        prompt_route.require_genuine(pf)                 # TR7R4-L-1: before any prompt is built or used
    except prompt_route.PromptRouteError as error:
        say("REFUSED INSTALL_PROMPT_ROUTE: %s. Nothing was changed." % error.reason)
        return EXIT_REFUSED
    ask = _remembered(prompt or pf.terminal_prompt)
    if connect is None:
        def connect(socket, database, user):
            return pf.connect_with_prompt(socket, database, user, require_auth=pf.GATED_REQUIRE_AUTH, prompt=ask, autocommit=True)
    import psycopg
    try:
        if args.command == "phase0":
            admin = connect(args.socket, "postgres", args.user)
            try:
                return EXIT_OK if run_checks(admin, args.socket, phase="0", say=say).ok else EXIT_REFUSED
            finally:
                admin.close()
        if args.command == "phase1":
            admin = connect(args.socket, "postgres", args.user)
            try:
                return phase1(admin, lambda: connect(args.socket, REAL_NAMES.database, args.user), args.socket, loader_login=args.loader_login, say=say)
            finally:
                admin.close()
        return phase2(lambda: connect(args.socket, REAL_NAMES.database, args.user), args.socket, phase="2" if args.command == "phase2" else "check",
                      say=say)
    except psycopg.Error as error:
        say("REFUSED %s (%s): the installer's own connection failed; nothing was changed by this step" % (pf.classify_own_connection_error(str(error)),
                                                                                                      type(error).__name__))
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
