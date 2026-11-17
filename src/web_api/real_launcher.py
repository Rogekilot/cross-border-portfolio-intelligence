"""F1 R7: the REAL-MODE LAUNCHER (design 7.1 R7, 1.2 rules 5.1 and 5.2, W14). Starts the app of `real_mode_routes` on loopback.

    python -m web_api.real_launcher --socket /dir/.s.PGSQL.5432 --database NAME --user EXECUTOR --schema SCHEMA --account-user ACCOUNT \\
        --contexts-file FILE [--port 8004]

ONE DECISION, FROM THE DATABASE. What the launcher is pointed at is decided from two facts it READS: the database's NAME and the install-kind rows
(`rw_install_info()`). Over a `TEST` install (a name outside the reserved namespace) it runs no preflight; over a `REAL` install (a name inside it)
it runs the preflight of design 1.2 first and refuses to start on any failure, writing nothing. That decision is `real_tool_gate.start_gate`, keyed
to this tool's command `serve`. There is no option, variable or key that selects, skips or relaxes it, and none that selects a scope or opens the
scope module's reviewed switch: the launcher imports nothing from the scope or proposal modules (a static test checks the module's source).

NO CREDENTIAL OPTION AND NO ENVIRONMENT READ. A TEST target is reached with no credential (the development cluster trusts its roles on the Unix
socket, as for the publisher tool). A REAL target is reached with `require_auth=scram-sha-256` from the first connection and a password typed at the
terminal prompt (`real_preflight.terminal_prompt`, the only credential route, PD-0077), once for the executor and once for the account role; the
launcher keeps what was typed in this process's memory for its reconnects and never writes it anywhere.

TWO ROLES. The EXECUTOR role (`--user`) runs the contract's operations: create, read, reproduce and list. The ACCOUNT role (`--account-user`) holds the
session: it may read and insert `app_user` and `web_identity`, and read, insert, update and delete `web_session` and `web_auth_rate`, and nothing else.
The real gateway's four roles (design 1 item 5) hold no identity privilege (R3 fix round, M-1); the fifth, account role is created by the real installer
(Phase 1), granted in Phase 2 and covered by the preflight and the catalog audit (PD-0078). Its password is typed at the prompt, like the executor's.

THE CONTEXTS FILE names, for each context the app may create under, the generation the launcher serves and the trusted provenance expectations the
create stands on (`ProvenanceLink`). It is read once, before any connection is opened, and a malformed file refuses to start.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from marketdata.acquisition import TrustedAcquisitionWitness
from persistence import real_preflight as pf
from persistence import prompt_route, real_tool_gate
from persistence.connection import build_conninfo, conninfo_with, is_reserved_real_name
from persistence.real_provenance import MemberKey
from persistence.real_workspace_context import RealWorkspaceError, identifier
from persistence.web_account_store import AccountStoreError

EXIT_OK, EXIT_REFUSED = 0, 2
COMMAND = "serve"
LOOPBACK = "127.0.0.1"
DEFAULT_PORT = 8004
ORIGIN_PORTS = (DEFAULT_PORT, 5175)
CONTEXTS_SCHEMA = "finweb.real_mode_contexts/1"
SESSION_SETTINGS = ("SET TIME ZONE 'UTC'", "SET statement_timeout TO '30000ms'")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class LaunchError(ValueError):
    def __init__(self, code, detail=""):
        self.code, self.detail = code, detail
        super().__init__(code if not detail else "%s: %s" % (code, detail))


# ---- the contexts file ------------------------------------------------------------------------------------------------------------------------
def _exact(value, keys, what):
    if type(value) is not dict or set(value) != set(keys):
        raise LaunchError("LAUNCH_CONTEXTS_SHAPE", what)
    return value


def _hash(value, what):
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise LaunchError("LAUNCH_CONTEXTS_SHAPE", what)
    return value


def parse_contexts(raw):
    """The contexts file's bytes -> `{context_id: ContextPin}`. Strict: exact key sets, hashes in lowercase hex, members and witnesses in the order
    the registry's expectations need, no duplicate context. A defect is `LaunchError`; nothing is repaired."""
    from real_service.service import ProvenanceLink
    from web_api.real_mode_routes import ContextPin
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError):
        raise LaunchError("LAUNCH_CONTEXTS_SHAPE", "not JSON") from None
    _exact(value, ("schema", "contexts"), "top level")
    if value["schema"] != CONTEXTS_SCHEMA or type(value["contexts"]) is not list or not 1 <= len(value["contexts"]) <= 8:
        raise LaunchError("LAUNCH_CONTEXTS_SHAPE", "schema or context count")
    pins = {}
    for item in value["contexts"]:
        _exact(item, ("context_id", "generation", "provenance"), "context")
        context_id = _hash(item["context_id"], "context_id")
        if type(item["generation"]) is not int or isinstance(item["generation"], bool) or item["generation"] < 1:
            raise LaunchError("LAUNCH_CONTEXTS_SHAPE", "generation")
        provenance = _exact(item["provenance"], ("context_sha256", "members", "witnesses"), "provenance")
        members, witnesses = [], []
        for member in provenance["members"] if type(provenance["members"]) is list else ():
            _exact(member, ("role", "payload_sha256", "manifest_sha256", "envelope_sha256", "witness_sha256"), "member")
            try:
                members.append(MemberKey(member["role"], member["payload_sha256"], member["manifest_sha256"], member["envelope_sha256"],
                                         member["witness_sha256"]))
            except Exception:       # noqa: BLE001 - the registry's own refusal of a malformed member
                raise LaunchError("LAUNCH_CONTEXTS_SHAPE", "member") from None
        for witness in provenance["witnesses"] if type(provenance["witnesses"]) is list else ():
            _exact(witness, ("expected_envelope_sha256", "expected_manifest_sha256", "actor_agent_id", "actor_role", "approved_full_request_sha256"), "witness")
            try:
                witnesses.append(TrustedAcquisitionWitness(**witness))
            except Exception:       # noqa: BLE001
                raise LaunchError("LAUNCH_CONTEXTS_SHAPE", "witness") from None
        if not members or len(members) != len(provenance["members"]) or len(witnesses) != len(provenance["witnesses"]):
            raise LaunchError("LAUNCH_CONTEXTS_SHAPE", "members")
        members.sort(key=lambda m: m.sort_key())
        witnesses.sort(key=lambda w: w.expected_manifest_sha256)
        if context_id in pins:
            raise LaunchError("LAUNCH_CONTEXTS_SHAPE", "duplicate context")
        link = ProvenanceLink(_hash(provenance["context_sha256"], "context_sha256"), tuple(members), tuple(witnesses))
        pins[context_id] = ContextPin(context_id, item["generation"], link)
    return pins


def _read_contexts_file(path):
    """The one file this tool reads: the contexts file named on the command line."""
    try:
        with open(path, "rb") as handle:
            raw = handle.read(1_000_001)
    except OSError as error:
        raise LaunchError("LAUNCH_CONTEXTS_UNREADABLE", type(error).__name__) from error
    if len(raw) > 1_000_000:
        raise LaunchError("LAUNCH_CONTEXTS_SHAPE", "file too large")
    return raw


# ---- command line -----------------------------------------------------------------------------------------------------------------------------
def _build_parser():
    parser = argparse.ArgumentParser(prog="real_launcher", description="Real-mode app launcher (R7). Loopback only.")
    parser.add_argument("--socket", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True, help="the executor role")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--account-user", required=True, help="the account role (sessions only)")
    parser.add_argument("--contexts-file", required=True)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser


def remembered(prompt):
    """A prompt that asks the terminal once per role and remembers the answer in this process (the app reconnects for each request)."""
    answers = {}

    def ask(role):
        if role not in answers:
            answers[role] = prompt(role)
        return answers[role]
    return ask


def default_connect(args, user, prompt, autocommit):
    """A new connection as `user`. A name in the reserved namespace is a REAL target: scram from the first connection and the password from the
    prompt alone. Any other name is reached with no credential (the development cluster trusts its roles on the socket)."""
    import psycopg
    if is_reserved_real_name(args.database):
        conn = pf.connect_with_prompt(args.socket, args.database, user, require_auth=pf.GATED_REQUIRE_AUTH, prompt=prompt, autocommit=autocommit)
    else:
        conn = psycopg.connect(conninfo_with(build_conninfo(socket=args.socket, dbname=args.database, user=user), passfile="/dev/null",
                                             sslmode="disable", gssencmode="disable", connect_timeout="5", application_name="finweb_real_mode"),
                               autocommit=autocommit)
    try:
        for statement in SESSION_SETTINGS:
            conn.execute(statement)
        if not autocommit:
            conn.commit()
    except BaseException:
        conn.close()
        raise
    return conn


def check_executor_role(conn, args):
    """The role the app runs as is the one named, is no superuser and does not own the gateway schema. Refuses (`LaunchError`) otherwise."""
    row = conn.execute("SELECT current_user::text, r.rolsuper, n.nspowner=r.oid FROM pg_roles r JOIN pg_namespace n ON n.nspname=%s "
                       "WHERE r.rolname=current_user", (identifier(args.schema),)).fetchone()
    if row is None or row[0] != args.user or row[1] or row[2]:
        raise LaunchError("LAUNCH_ROLE", "the executor role must be the named role, not a superuser and not the schema owner")


def _serve(app, port):
    import uvicorn
    uvicorn.run(app, host=LOOPBACK, port=port, log_level="warning", access_log=False)


def make_account_store(args, connect, prompt):
    """The session store over the account role. Opens no connection itself."""
    from persistence.web_account_store import WebAccountStore
    return WebAccountStore(None, args.schema, opener=lambda: connect(args, args.account_user, prompt, True))


def build(args, connect, prompt, pins, account_store):
    """The service and the app for validated arguments. Opens no connection itself. `world_inputs` is the REAL branch's world (G8): the identity (the one the
    owner's seed carries), the conventions and the F8B policy of `real_service.real_identity`, the same module the qualification run uses, so the
    identity digest of a proposal is the one the create rebuilds; the test scopes' creates still run on the invented world. `lineage_of` is the O-7 extractor
    (`marketdata.claim_record.lineage_of`): it reads a real root's issued document, stored response and claim record and nothing else; a test root never calls it."""
    from marketdata.claim_record import lineage_of
    from real_service.real_identity import real_world_inputs
    from real_service.service import RealWorkspaceService
    from web_api.auth import AuthSettings
    from web_api.real_mode_routes import create_real_mode_app
    executor = lambda: connect(args, args.user, prompt, True)            # noqa: E731
    service = RealWorkspaceService(args.schema, executor_role=args.user, connect=executor, world_inputs=real_world_inputs())
    origins = tuple("http://%s:%d" % (LOOPBACK, port) for port in sorted(set(ORIGIN_PORTS + (args.port,))))
    return create_real_mode_app(service=service, contexts=pins, account_store=account_store, connect=executor, settings=AuthSettings.local(),
                                origins=origins, lineage_of=lineage_of)


def main(argv=None, *, connect=None, prompt=None, serve=None, out=None):
    """Start the app; returns the exit status. `connect(args, user, prompt, autocommit)`, `prompt(role)` and `serve(app, port)` are the tests' seams.
    Every refusal below happens BEFORE the app is built or served, and nothing is written."""
    import psycopg
    out = out or sys.stdout
    args = _build_parser().parse_args(argv)
    try:
        prompt_route.require_genuine(pf)                 # TR7R4-L-1: before any prompt is built or used
    except prompt_route.PromptRouteError as error:
        print("REFUSED LAUNCH_PROMPT_ROUTE. Nothing was started and nothing was written.", file=out)
        print(error.reason, file=out)
        return EXIT_REFUSED
    connect = connect or default_connect
    prompt = remembered(prompt or pf.terminal_prompt)
    serve = serve or _serve

    def refuse(code, *lines):
        print("REFUSED %s. Nothing was started and nothing was written." % code, file=out)
        for line in lines:
            print(line, file=out)
        return EXIT_REFUSED

    if not 1024 <= args.port <= 65535:
        return refuse("LAUNCH_PORT")
    try:
        for name in (args.schema, args.user, args.account_user, args.database):
            identifier(name)
    except RealWorkspaceError:
        return refuse("LAUNCH_NAMES")
    try:
        pins = parse_contexts(_read_contexts_file(args.contexts_file))                 # inputs first: a defect sends nothing to the database
    except LaunchError as error:
        return refuse(error.code, error.detail)
    try:
        conn = connect(args, args.user, prompt, True)
    except psycopg.Error as error:
        return refuse("LAUNCH_CONNECT_FAILED", pf.classify_own_connection_error(str(error)))
    try:
        decision = real_tool_gate.start_gate(conn, COMMAND, database=args.database, schema=args.schema, socket=args.socket)
        if not decision.proceed:
            for line in decision.lines:
                print(line, file=out)
            return refuse(decision.code)
        try:
            check_executor_role(conn, args)
        except (LaunchError, RealWorkspaceError, psycopg.Error) as error:
            return refuse(getattr(error, "code", "LAUNCH_ROLE"))
    finally:
        conn.close()
    for line in decision.lines:
        print(line, file=out)
    try:
        account_store = make_account_store(args, connect, prompt)
        account_store.connect().close()          # the account role exists, logs in, and is no superuser and not the schema owner
    except (AccountStoreError, psycopg.Error, ValueError) as error:
        return refuse("LAUNCH_ACCOUNT_ROLE", getattr(error, "code", type(error).__name__))
    app = build(args, connect, prompt, pins, account_store)
    print("real-mode app: %s target, loopback port %d, %d context(s)." % (decision.target, args.port, len(pins)), file=out)
    serve(app, args.port)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
