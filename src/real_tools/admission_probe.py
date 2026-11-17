"""F1 R7: the ADMISSION PROBE (E27; design 7.1 R7 and R8 step 6; conformance R3C-L2, technical TR3-L8).

    python -m real_tools.admission_probe --socket /dir/.s.PGSQL.5432 --database NAME --user EXECUTOR --schema SCHEMA \\
        --purpose ARCHIVE_EXPORT --owner-id UUID --root-id UUID --context HASH --generation N

DIRECT GATEWAY ADMISSION, NOT A PRODUCT ROUTE. The scoped contract has no export route (design 2.4; a real export purpose is later work, 7.3), so the
export right can be shown refused only at the gateway. This one-shot command opens ONE transaction on the executor's connection, calls the gateway's
admit (`real_workspace_store.admit`) for exactly one of `ARCHIVE_READ`, `ARCHIVE_EXPORT` or `EXECUTE_REPRODUCE` on one existing root of one context,
prints the outcome or the refusal code, and ROLLS BACK, always. It stores nothing and leaves no lease: the lease row the admission inserts is inside the
transaction that is rolled back.

  * NEVER `EXECUTE_CREATE`. No option selects it: `--purpose` has three choices, `new_root` is not a parameter of this tool, and `main` re-checks the
    purpose against the constant tuple before it sends anything. (An `EXECUTE_CREATE` admission can register a root.)
  * It is not a route. Nothing here is imported by the app, and the app imports nothing from here.
  * The same start gate as the launcher (`real_tool_gate.start_gate`, command `admit`): over a REAL install it runs the preflight of design 1.2 and
    refuses to run on any failure, writing nothing; over a TEST install it runs none. The decision is read from the database; the tool has no option,
    variable or key that selects, skips or relaxes it, and no credential option and no environment read (a REAL target takes its password from the
    terminal prompt alone, PD-0077).

It runs as the named executor role only (not a superuser, not the schema owner), as the launcher does; any other role is refused before anything is sent.

Exit status: 0 admitted, 1 refused by the gateway (an `RW_*` code is printed), 2 the tool did not run (inputs, connection, start gate or role),
3 a database or permission error that is not a gateway answer (the right was NOT tested; it is not a refusal).
"""
from __future__ import annotations

import argparse
import re
import sys
import uuid

from persistence import real_preflight as pf
from persistence import prompt_route, real_tails, real_tool_gate
from persistence import real_workspace_store as store
from persistence.connection import build_conninfo, conninfo_with, is_reserved_real_name
from persistence.real_workspace_context import RealWorkspaceError, identifier

EXIT_ADMITTED, EXIT_REFUSED_BY_GATEWAY, EXIT_NOT_RUN, EXIT_DATABASE_ERROR = 0, 1, 2, 3
COMMAND = "admit"
PURPOSES = ("ARCHIVE_READ", "ARCHIVE_EXPORT", "EXECUTE_REPRODUCE")
BANNER = "direct gateway admission, not a product route"
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _build_parser():
    parser = argparse.ArgumentParser(prog="admission_probe", description="Direct gateway admission, not a product route (E27).")
    parser.add_argument("--socket", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True, help="the executor role")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--purpose", required=True, choices=PURPOSES)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--root-id", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--generation", type=int, required=True)
    return parser


def _default_connect(args, prompt):
    """A new connection as the executor (autocommit; the probe's one transaction is explicit). A reserved name is a REAL target: scram from the first
    connection, the password from the prompt alone. Any other name is reached with no credential."""
    import psycopg
    if is_reserved_real_name(args.database):
        conn = pf.connect_with_prompt(args.socket, args.database, args.user, require_auth=pf.GATED_REQUIRE_AUTH, prompt=prompt, autocommit=True)
    else:
        conn = psycopg.connect(conninfo_with(build_conninfo(socket=args.socket, dbname=args.database, user=args.user), passfile="/dev/null",
                                             sslmode="disable", gssencmode="disable", connect_timeout="5", application_name="finweb_admission_probe"),
                               autocommit=True)
    try:
        conn.execute("SET TIME ZONE 'UTC'")
        conn.execute("SET statement_timeout TO '30000ms'")
    except BaseException:
        conn.close()
        raise
    return conn


def _identifiers(args):
    """The validated inputs, or None. Nothing is sent to the database before this passes."""
    try:
        owner, root = uuid.UUID(args.owner_id), uuid.UUID(args.root_id)
        if str(owner) != args.owner_id or str(root) != args.root_id:
            return None
        if args.purpose not in PURPOSES or _HASH.fullmatch(args.context) is None or args.generation < 1:
            return None
        for name in (args.schema, args.user, args.database):
            identifier(name)
    except (ValueError, RealWorkspaceError):
        return None
    return owner, root


def _is_the_executor(conn, args):
    """TR7-L-4 (design 1.2 5.1): the connection is the named role, which is no superuser and does not own the gateway schema (the launcher's check).
    One read of the catalog on a transaction of its own; any failure to read it is a refusal."""
    import psycopg
    try:
        with conn.transaction():
            row = conn.execute("SELECT current_user::text, r.rolsuper, n.nspowner=r.oid FROM pg_roles r JOIN pg_namespace n ON n.nspname=%s "
                               "WHERE r.rolname=current_user", (identifier(args.schema),)).fetchone()
    except (psycopg.Error, RealWorkspaceError):
        return False
    return row is not None and row[0] == args.user and not row[1] and not row[2]


def main(argv=None, *, connect=None, out=None, prompt=None):
    """Run the probe once; returns the exit status. `connect(args, prompt)` returns an IDLE autocommit connection (the tests' seam)."""
    import psycopg
    out = out or sys.stdout
    args = _build_parser().parse_args(argv)
    print(BANNER, file=out)
    try:
        prompt_route.require_genuine(pf)                 # TR7R4-L-1: before any prompt is used
    except prompt_route.PromptRouteError as error:
        print("REFUSED PROBE_PROMPT_ROUTE %s. Nothing was sent and nothing was written." % error.reason, file=out)
        return EXIT_NOT_RUN
    ids = _identifiers(args)
    if ids is None:
        print("REFUSED PROBE_INPUT. Nothing was sent.", file=out)
        return EXIT_NOT_RUN
    owner, root = ids
    connect = connect or _default_connect
    try:
        conn = connect(args, prompt or pf.terminal_prompt)
    except psycopg.Error as error:
        print("REFUSED PROBE_CONNECT_FAILED %s. Nothing was sent." % pf.classify_own_connection_error(str(error)), file=out)
        return EXIT_NOT_RUN
    try:
        decision = real_tool_gate.start_gate(conn, COMMAND, database=args.database, schema=args.schema, socket=args.socket)
        for line in decision.lines:
            print(line, file=out)
        if not decision.proceed:
            print("REFUSED %s. The probe did not run; nothing was written." % decision.code, file=out)
            return EXIT_NOT_RUN
        if not _is_the_executor(conn, args):
            print("REFUSED PROBE_ROLE. The probe runs as the named executor role only: not a superuser and not the schema owner. Nothing was written.", file=out)
            return EXIT_NOT_RUN
        operation = real_tails.entry_operation_id(root, args.generation, "probe:" + args.purpose)
        try:
            with conn.transaction(force_rollback=True):
                lease = store.admit(conn, args.schema, owner=owner, root=root, context_id=args.context, generation=args.generation,
                                    purpose=args.purpose, operation_id=operation, command_sha256=real_tails.NO_COMMAND)
                outcome = (EXIT_ADMITTED, "ADMITTED purpose=%s context=%s generation=%d complete_by=%s" % (
                    lease.purpose, lease.context_id, lease.generation, lease.complete_by))
        except RealWorkspaceError as refusal:
            outcome = (EXIT_REFUSED_BY_GATEWAY, "REFUSED %s purpose=%s context=%s generation=%d" % (refusal.code, args.purpose, args.context, args.generation))
        except psycopg.Error as error:
            # TR7-L-4: a database or permission error is not a gateway refusal. It says nothing about the right; the probe did not get an answer.
            outcome = (EXIT_DATABASE_ERROR, "DATABASE_ERROR %s purpose=%s context=%s generation=%d. This is NOT a gateway refusal; the right was not tested." % (
                type(error).__name__, args.purpose, args.context, args.generation))
        print(outcome[1], file=out)
        print("The transaction was rolled back; no lease and no row was kept.", file=out)
        return outcome[0]
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
