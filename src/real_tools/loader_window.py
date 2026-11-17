"""F1 R8: the LOADER'S WINDOW TOOL (R6R-L1, TR6R-L1; design 3.3 item 1, 7.1 R8 steps (2) and (4a); install plan sections 5 and 6).

    python -m real_tools.loader_window load            --socket S --database D --user LOADER --schema SCH INPUTS
    python -m real_tools.loader_window register-bound  --socket S --database D --user LOADER --schema SCH INPUTS
    python -m real_tools.loader_window reconcile       --socket S --database D --user LOADER --schema SCH INPUTS --candidate {unbound,bound}
    python -m real_tools.loader_window check           --socket S --database D --user LOADER --schema SCH INPUTS

    INPUTS = --store-root DIR --release-name NAME --file SHA [--file SHA ...] [--sidecar PATH ...] [--registered-check SHA ...] --proposal FILE
             [--lock-timeout-ms N]

Run by the OWNER in the owner's own terminal, inside a loader window (install plan section 6), as the LOADER role and no other. The password is typed at the
terminal prompt alone (`real_preflight.terminal_prompt` through `connect_with_prompt`, PD-0077); there is no option, file or variable for it.

  * `load` (window 1, R8 step (2)): `qualification.load_qualified` projects the release into the `md_*` tables, then the UNBOUND candidate is registered
    (design 3.3 item 1, 2.3 item 1: the publish consults the registry for each member). Both are idempotent, so an identical re-run reconciles: it reports
    "already loaded" and registers nothing twice (the operation id is a function of the context bytes).
  * `register-bound` (window 2, step (4a), AFTER the publish): the BOUND candidate, whose financial context is the published snapshot's. The database
    refuses it until the snapshot exists, so it is refused before a publish and done after one.
  * `reconcile` (TR6R-L1): settles an UNKNOWN registration by its operation id. An unknown registration can be resolved ONLY by the loader, so THE WINDOW
    STAYS OPEN (or the owner reopens it) until this command answers definitely; the tool says so each time it reports UNKNOWN. It retries nothing.
  * `check` (E29, print only): the session's role facts, whether the release is loaded, and whether each candidate is registered. Writes nothing.

THE LOADER LOADS ONLY WHAT WAS REVIEWED. Every command rebuilds the qualification from INPUTS (the same build as the offline `qualify_run`) and refuses unless
its proposal bytes equal the file named by `--proposal`: the release loaded and the candidates registered are the ones of the reviewed proposal.

NO PREFLIGHT GATE HERE. The design gates `publish`, `renew`, the launcher and the admission probe and never `withdraw` (1.2 rule 5.1, 7.1 R6); it names no loader
tool, and `real_preflight.command_plan` leaves an unlisted command ungated. The start gate cannot serve this role in any case: it reads `rw_install_info()`,
which the loader holds no EXECUTE on (3.3, the narrowing). What this tool checks instead is stated in `_agreement` and `_is_the_loader`. The owner's `real_install
check` inside each window is the plan's check of the loader's state (plan section 6 item 3). Whether this tool should be gated is the PM's question.

Exit status (the publisher tool's): 0 done, 2 refused (a definite refusal; nothing was recorded by the step that refused), 4 unknown (the window stays
open; run `reconcile`), 5 lock timeout (the step recorded nothing).
"""
from __future__ import annotations

import sys

from persistence import prompt_route, real_preflight as pf
from persistence import real_provenance_store as provstore
from persistence.connection import build_conninfo, conninfo_with, is_reserved_real_name
from persistence.real_provenance import ProvenanceError
from persistence.real_workspace_context import identifier
from persistence.real_workspace_store import CommandResult, EXIT_DONE, EXIT_LOCK_TIMEOUT, EXIT_REFUSED, EXIT_UNKNOWN
from real_tools import candidates as cand, qualification as q, real_inputs

COMMANDS = ("load", "register-bound", "reconcile", "check")
CANDIDATES = ("unbound", "bound")
WINDOW_OPEN = ("THE LOADER WINDOW STAYS OPEN: do not set the loader NOLOGIN and do not end its sessions. An unknown registration can be resolved only by "
               "the loader (TR6R-L1). Run `loader_window reconcile --candidate %s` with the same inputs in this window; if the window was closed, the owner "
               "reopens it (install plan section 6 steps 1 to 3) and runs it. This tool retries nothing.")
WINDOW_OPEN_NOTHING_FOUND = ("THE LOADER WINDOW STAYS OPEN until an answer is definite: do not set the loader NOLOGIN yet. Running `reconcile` again will not change "
                             "this answer. What settles it: run the identical `loader_window %s` command again in this window. It is idempotent by operation id: if "
                             "the registration never committed it stores it now (DONE), and if it did commit it reports it stored. Only then may the owner close "
                             "the window (NOLOGIN, plan section 6 steps 5 to 7). This tool retries nothing.")
WINDOW_MAY_CLOSE = ("Definite. The window's work for this step is done; closing it (NOLOGIN, ending the loader's sessions, recording the times) is the owner's "
                    "procedure in plan section 6 steps 5 to 7, and no tool does it.")


def _build_parser():
    import argparse
    parser = argparse.ArgumentParser(prog="loader_window", description="The loader's window tool: load, register, reconcile, check (owner only; the loader "
                                     "role's password at a prompt).")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        p = sub.add_parser(name)
        p.add_argument("--socket", required=True)
        p.add_argument("--database", required=True)
        p.add_argument("--user", required=True, help="the loader role")
        p.add_argument("--schema", required=True)
        p.add_argument("--store-root", required=True)
        p.add_argument("--release-name", required=True)
        p.add_argument("--file", action="append", required=True)
        p.add_argument("--sidecar", action="append")
        p.add_argument("--registered-check", action="append")
        p.add_argument("--proposal", required=True)
        p.add_argument("--lock-timeout-ms", type=int, default=provstore.DEFAULT_LOCK_TIMEOUT_MS)
        if name == "reconcile":
            p.add_argument("--candidate", required=True, choices=CANDIDATES)
    return parser


def _default_connect(args, prompt):
    """A new connection as the loader (autocommit: the registry's `register` requires an IDLE autocommit connection). A reserved name is a REAL target:
    scram from the first connection, the password from the prompt alone. Any other name is reached with no credential."""
    import psycopg
    if is_reserved_real_name(args.database):
        conn = pf.connect_with_prompt(args.socket, args.database, args.user, require_auth=pf.GATED_REQUIRE_AUTH, prompt=prompt, autocommit=True)
    else:
        conn = psycopg.connect(conninfo_with(build_conninfo(socket=args.socket, dbname=args.database, user=args.user), passfile="/dev/null",
                                             sslmode="disable", gssencmode="disable", connect_timeout="5", application_name="finweb_loader_window"),
                               autocommit=True)
    return conn


def _prepare(conn, args):
    """The session settings the load needs (`write_release` names its tables unqualified): UTC, the schema first on the search path, a lock timeout.
    Sent after the role check, on any connection the tool is handed."""
    conn.execute("SET TIME ZONE 'UTC'")
    conn.execute('SET search_path TO "%s", pg_temp' % identifier(args.schema))
    conn.execute("SET lock_timeout TO '%dms'" % args.lock_timeout_ms)


def _agreement(args, rebuilt, proposal):
    """The refusals that need no connection. Returns a refusal text or None. (1) The qualification just rebuilt must be the reviewed proposal, byte for
    byte. (2) The database NAME and the proposal's scope agree: a name in the reserved REAL namespace takes the REAL scope only and any other name takes
    a test scope only (the install kind, which this role cannot read, is enforced by the database at publish and admit). (3) A REAL target is reached
    as the real loader role only, so no other real credential (owner, publisher, executor, superuser) is ever typed into this tool."""
    if rebuilt.qualification.proposal != proposal:
        return "RW_LOADER_PROPOSAL_DIFFERS: the qualification rebuilt from the inputs is not the proposal file %s; nothing is loaded that was not reviewed" % args.proposal
    definition = rebuilt.scope           # a `ResolvedScope` reads through to its definition; `build_candidate` refuses any other kind of scope right after
    real_name = is_reserved_real_name(args.database)
    if (definition.install_kind == "REAL") != real_name:
        return "RW_LOADER_TARGET_SCOPE: the database name %s the reserved real namespace but the proposal's scope is %s" % (
            "is in" if real_name else "is not in", definition.name)
    if real_name and args.user != pf.REAL_ROLES["loader"]:
        return "RW_LOADER_ROLE: a real target is reached as the real loader role %s only" % pf.REAL_ROLES["loader"]
    return None


def _is_the_loader(conn, args):
    """The session is the named role, logged in as itself, with no SET ROLE, and it is no superuser. One read of the catalog; a failure to read it is a refusal."""
    import psycopg
    try:
        row = conn.execute("SELECT current_user::text, session_user::text, current_setting('role'), r.rolsuper, r.rolcanlogin FROM pg_roles r "
                           "WHERE r.rolname=current_user").fetchone()
    except psycopg.Error:
        return None
    if row is None or tuple(row[:3]) != (args.user, args.user, "none") or row[3]:
        return None
    return row


def _refused(*lines):
    return CommandResult(EXIT_REFUSED, "REFUSED", tuple(lines) + ("nothing was recorded by this step",), {})


def _registration(store, scope, candidate, which, *, reconcile=False):
    """One registration (or its reconcile) as a `CommandResult`."""
    what = "reconcile of the %s candidate" % which if reconcile else "registration of the %s candidate" % which
    try:
        saved = (cand.reconcile_candidate if reconcile else cand.register_candidate)(store, scope, candidate)
    except ProvenanceError as error:
        if error.code == "RW_PROV_LOCK_TIMEOUT":
            return CommandResult(EXIT_LOCK_TIMEOUT, "LOCK_TIMEOUT", ("the %s waited for a lock and recorded nothing" % what,), {})
        if which == "bound" and not reconcile and error.code == "RW_PROV_INPUT_MISSING":
            return _refused("refused: the %s: %s" % (what, ", ".join(error.codes)),
                            "the usual cause: the snapshot this candidate is bound to has not been published (the registration's financial context is a "
                            "foreign key to it); the owner publishes first (R8 step (4)), then runs register-bound")
        return _refused("refused: the %s: %s" % (what, ", ".join(error.codes)))
    except cand.CandidateError as error:
        return _refused("refused: the %s: %s" % (what, error))
    if isinstance(saved, provstore.CommittedRegistration):
        return CommandResult(EXIT_DONE, "DONE", ("%s %s: stored; operation %s; response sha256 %s" % (
            which, "reconciled" if reconcile else "registered", saved.operation_id, saved.response_sha256), WINDOW_MAY_CLOSE), {"operation_id": str(saved.operation_id)})
    if reconcile:
        return CommandResult(EXIT_UNKNOWN, "UNKNOWN", ("the %s: no registration with this operation id was found or readable; this is NOT a definite answer" % what,
                                                       WINDOW_OPEN_NOTHING_FOUND % ("register-bound" if which == "bound" else "load")), {})
    return CommandResult(EXIT_UNKNOWN, "UNKNOWN", ("the %s: the outcome is not known" % what, WINDOW_OPEN % which), {})


def _load_step(conn, rebuilt):
    import psycopg
    try:
        result = q.load_qualified(conn, rebuilt.qualification, exchange_of=rebuilt.resolver.exchange_mic)
    except real_inputs.LOAD_REFUSALS as error:
        return _refused("refused: the load: %s" % error)
    except psycopg.errors.LockNotAvailable:
        return CommandResult(EXIT_LOCK_TIMEOUT, "LOCK_TIMEOUT", ("the load waited for a lock and recorded nothing; the load is idempotent, so the identical "
                                                                  "command may be run again",), {})
    except psycopg.Error as error:
        if conn.closed or isinstance(error, (psycopg.OperationalError, psycopg.InterfaceError)):
            return CommandResult(EXIT_UNKNOWN, "UNKNOWN", ("the load: the outcome is not known (%s); the load is one transaction and idempotent: run the "
                                                           "identical command again, which reports whether the release is present" % type(error).__name__,
                                                           "THE LOADER WINDOW STAYS OPEN until the identical command answers definitely"), {})
        return _refused("refused: the load failed inside its one transaction (%s), which rolled back" % type(error).__name__)
    return CommandResult(EXIT_DONE, "LOADED" if result.created else "ALREADY_LOADED", (
        ("loaded release %s" if result.created else "already loaded: release %s is present with the same projection digest") % result.release_id,
        "projection digest %s" % result.projection_digest), {"created": result.created})


def _check(conn, args, rebuilt, role_row, store, candidates):
    """Print only. Reads: the session's role, `md_release`, and the registry's get function through `load_context`."""
    lines = ["session: user %s, may log in %s, superuser %s" % (role_row[0], role_row[4], role_row[3])]
    release_id = rebuilt.qualification.release.release_id
    row = conn.execute("SELECT projection_digest FROM md_release WHERE release_id=%s", (release_id,)).fetchone()
    if row is None:
        lines.append("release %s: not loaded" % release_id)
    else:
        lines.append("release %s: loaded; projection digest %s, %s the proposal's" % (
            release_id, row[0], "equal to" if row[0] == real_inputs.proposal_projection_digest(rebuilt.qualification.proposal) else "NOT equal to"))
    for which, candidate in candidates.items():
        try:
            store.load_context(rebuilt.scope, candidate.context_sha256, expected_members=candidate.members, witnesses=candidate.witnesses)
            lines.append("%s candidate %s: registered" % (which, candidate.context_sha256[:16]))
        except ProvenanceError as error:
            lines.append("%s candidate %s: %s" % (which, candidate.context_sha256[:16], "not registered" if error.code == "RW_PROV_INPUT_MISSING"
                                                  else "not readable (%s)" % ", ".join(error.codes)))
    lines.append("print only: nothing was written. This is not a reconcile: an UNKNOWN registration is settled by `reconcile` alone.")
    return CommandResult(EXIT_DONE, "CHECKED", tuple(lines), {})


def main(argv=None, *, connect=None, out=None, prompt=None, build=None):
    """Run one command; returns its exit status. `connect(args, prompt)` returns an IDLE autocommit connection and `build(args)` a `real_inputs.Rebuilt`
    (the tests' seams; the default build is the REAL scope)."""
    import psycopg
    out = out or sys.stdout
    args = _build_parser().parse_args(argv)

    def say(result):
        for line in result.lines:
            print(line, file=out)
        return result.status
    try:
        prompt_route.require_genuine(pf)                 # TR7R4-L-1: before any prompt is used
    except prompt_route.PromptRouteError as error:
        print("REFUSED LOADER_PROMPT_ROUTE %s. Nothing was sent and nothing was written." % error.reason, file=out)
        return EXIT_REFUSED
    try:
        for name in (args.schema, args.user, args.database):
            identifier(name)
        if not 1 <= args.lock_timeout_ms <= 600_000:
            raise real_inputs.InputError("RW_INPUT_LOCK_TIMEOUT", "--lock-timeout-ms is from 1 to 600000")
        proposal, _verified = real_inputs.read_proposal(args.proposal)
        rebuilt = (build or real_inputs.rebuild_real)(args)
        refusal = _agreement(args, rebuilt, proposal)
        if refusal is not None:
            print("REFUSED %s. Nothing was sent." % refusal, file=out)
            return EXIT_REFUSED
        context_id = rebuilt.qualification.context_id
        candidates = {"unbound": cand.build_candidate(rebuilt.scope, rebuilt.store, rebuilt.qualification),
                      "bound": cand.build_candidate(rebuilt.scope, rebuilt.store, rebuilt.qualification, financial_context=context_id)}
    except real_inputs.INPUT_REFUSALS as error:
        print("REFUSED LOADER_INPUT %s. Nothing was sent." % (str(error) if hasattr(error, "code") else "%s: %s" % (type(error).__name__, error)), file=out)
        return EXIT_REFUSED
    print("loader window tool: %s of release %s (scope %s, context %s)" % (args.command, rebuilt.qualification.release.release_id, rebuilt.qualification.scope,
                                                                          context_id), file=out)
    connect = connect or _default_connect
    try:
        conn = connect(args, prompt or pf.terminal_prompt)
    except psycopg.Error as error:
        print("REFUSED LOADER_CONNECT_FAILED %s. Nothing was sent." % pf.classify_own_connection_error(str(error)), file=out)
        return EXIT_REFUSED
    try:
        role_row = _is_the_loader(conn, args)
        if role_row is None:
            print("REFUSED LOADER_ROLE. The tool runs as the named loader role only, logged in as itself: no SET ROLE, no superuser. Nothing was written.", file=out)
            return EXIT_REFUSED
        try:
            _prepare(conn, args)
        except psycopg.Error as error:
            print("REFUSED LOADER_SESSION %s. Nothing was written." % type(error).__name__, file=out)
            return EXIT_REFUSED
        store = provstore.RealProvenanceStore(conn, args.schema, loader_role=args.user, lock_timeout_ms=args.lock_timeout_ms)
        if args.command == "check":
            return say(_check(conn, args, rebuilt, role_row, store, candidates))
        if args.command == "reconcile":
            return say(_registration(store, rebuilt.scope, candidates[args.candidate], args.candidate, reconcile=True))
        if args.command == "register-bound":
            return say(_registration(store, rebuilt.scope, candidates["bound"], "bound"))
        loaded = _load_step(conn, rebuilt)
        status = say(loaded)
        if loaded.status != EXIT_DONE:
            return status
        registered = _registration(store, rebuilt.scope, candidates["unbound"], "unbound")
        if registered.status != EXIT_DONE:
            print("THE LOAD COMMITTED; " + ("whether the unbound registration committed is NOT known. The identical command settles it, or `reconcile --candidate unbound`."
                                           if registered.status == EXIT_UNKNOWN else
                                           "the unbound registration was not recorded. The identical command registers it."), file=out)
        return say(registered)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
