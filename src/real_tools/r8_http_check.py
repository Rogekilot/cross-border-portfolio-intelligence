"""F1 R8 supplementary run: the LOOPBACK CHECK TOOL (`implementation/CP7_F1_R8_SUPPLEMENT_PLAN.md`, revision 2; TR8S H-1, M-1 to M-4).

    uv run --no-sync --frozen --offline python -m real_tools.r8_http_check --phase b|pre|post ...        (started by `real_tools.r8_supplement`, never by hand)

WHAT IT DOES. It signs in to the real-mode launcher the way the screen does and sends the requests the screen cannot send: an exact replay of a real create, a
conflicting reuse of its operation id, refused requests whose bodies it compares byte for byte with the contract's own refusal body, user B's reading of
user A's root, and the reads and the reproduce after a restart. It compares and prints what it saw. It decides nothing about the product.

TRANSPORT (TR8S H-1). `http.client.HTTPConnection("127.0.0.1", 8004)` and nothing else. The host and the port are constants (the port is the launcher's default),
not options, so a password cannot be pointed at another listener. No redirect is followed, and no proxy API is used, so an `http_proxy` variable or a system
proxy cannot receive the password or a cookie. The cookies are read by hand from `Set-Cookie` for the two names the real-mode app uses.

SECRETS (TR8S M-4). The password comes from `real_preflight.terminal_prompt` alone, after `prompt_route.require_genuine`, with a label that names the web
account and says it is not a database role. It goes into one `json.dumps` call (the login body) and nowhere else. The session cookie, the CSRF token, every
response header and every raw authentication body stay inside `Session`; nothing of them is printed or logged. The ONLY output is `emit`: one `S8 {json}` line
of safe fields (label, status, code, ids, digests, counts, the fixed text of a contract refusal that equals the contract's own body). The tool reads no
file, no environment variable and no standard input (`input()` is never called); the runner reads the acknowledgement, B's username and the optional name and
passes them as options. Logout is in a `finally`.

EXIT STATUS. 0 everything as expected. 3 a retry is safe, nothing was sent that can write: the connection was refused, or the login was refused as mistyped
(`S8` line `retry`, `count` true), or rate limited (`count` false: wait, do not count). 5 a finding BEFORE any create-route request was sent: nothing was
created. 2 an unexpected answer after one was sent. 4 the outcome of a create-route request is unknown. 7 the arguments are not usable: nothing was sent.
1 an uncaught error (the runner treats it as a stop). The runner latches on every status except 0, 3, 5 and 7.

EXPECTED REFUSAL BODIES (TR8S M-1). `canonical_json(refusal_payload(ContractRefusal(code)))`: with a bare code string `refusal_payload` returns the
`REAL_UNAVAILABLE` body, so it is never called with one.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import sys
import uuid

from marketdata.canonical import canonical_json
from persistence import prompt_route
from persistence import real_preflight as pf
from web_api import real_scoped_contract as contract

HOST, PORT = "127.0.0.1", 8004          # = real_launcher.DEFAULT_PORT (a test pins it); constants, never options
ORIGIN = "http://127.0.0.1:5175"          # the Vite origin the launcher allows
SESSION_COOKIE, BOOTSTRAP_COOKIE = "finweb_real_session", "finweb_real_csrf"
COOKIE_NAMES = (SESSION_COOKIE, BOOTSTRAP_COOKIE)
BASE = "/api/real/v1"
MAX_REPLY_BYTES = 7_000_000
EXIT_OK, EXIT_UNEXPECTED, EXIT_RETRY, EXIT_UNKNOWN, EXIT_FINDING, EXIT_USAGE = 0, 2, 3, 4, 5, 7

NAME_Y, NAME_CONFLICT = "R8 supplement", "R8 supplement conflict"
QUANTITY, CONFLICT_QUANTITY, CASH, AS_OF = "10", "11", "500", "2026-09-30"           # R8's inputs (the Quant's HG4 case)
UNKNOWN_ROOT = "00000000-0000-4000-8000-000000000001"
MALFORMED_ROOT = "not-a-uuid"                                                        # no "/": a path with another segment is the closed route
UNSERVED_CONTEXT = hashlib.sha256(b"r8 supplement: a well-formed context the launcher does not serve").hexdigest()
EXPECTED_ROOTS_BEFORE_Y = 2                                                          # R8: create_a and create_c2 (the create under the withdrawal wrote nothing)
SAFE_FIELDS = frozenset(("status", "code", "kind", "detail", "replayed", "root_id", "operation_id", "response_sha256", "issued_sha256", "count", "body_text",
                         "body_sha256", "body_bytes", "verdict", "note", "expected", "reproduce_status", "differs", "counts_as_typo"))
REPRODUCE_FINDINGS = {"RESULT_DIFFERS": "REPRODUCE_RESULT_DIFFERS", "INPUT_MISMATCH": "REPRODUCE_INPUT_MISMATCH", "SOURCE_REFUSED": "REPRODUCE_SOURCE_REFUSED"}   # literal codes only
_CODE = re.compile(r"[A-Za-z0-9_]{1,64}\Z")
_USERNAME = re.compile(r"[A-Za-z0-9._@-]{1,64}\Z")


class NoConnect(Exception):
    """The connection was refused or could not be opened: nothing was sent."""


class Lost(Exception):
    """The request may have been sent and no readable answer came back."""


class Retry(Exception):
    def __init__(self, code, counts):
        super().__init__(code)
        self.code, self.counts = code, counts


class Finding(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Unknown(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class UsageError(Exception):
    pass


def emit(label, **fields):
    """The only output. One `S8 {json}` line; only the safe field names, and only strings, integers, booleans or None."""
    line = {"label": label}
    for key, value in fields.items():
        if key not in SAFE_FIELDS or not (value is None or isinstance(value, (str, int, bool))):
            raise ValueError("an unsafe output field")
        line[key] = value
    print("S8 " + json.dumps(line, sort_keys=True), flush=True)


def sha256_hex(raw):
    return hashlib.sha256(raw).hexdigest()


def raw_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def expected_body(code):
    """The contract's own refusal body for `code`, as the server sends it (TR8S M-1: the argument is a `ContractRefusal`, not a string)."""
    return canonical_json(contract.refusal_payload(contract.ContractRefusal(code))).encode("utf-8")


# ---- the one network function (a seam: tests pass a fake) ----------------------------------------------------------------------------------------
def default_send(method, path, headers, body):
    """(status, the Set-Cookie header values, the body bytes). `NoConnect` before anything is sent; `Lost` after."""
    connection = http.client.HTTPConnection(HOST, PORT, timeout=60)
    try:
        try:
            connection.connect()
        except OSError:
            raise NoConnect() from None
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(MAX_REPLY_BYTES + 1)
            cookies = response.msg.get_all("Set-Cookie") or []
            status = response.status
        except (OSError, http.client.HTTPException):
            raise Lost() from None
        if len(raw) > MAX_REPLY_BYTES:
            raise Lost()
        return status, cookies, raw
    finally:
        connection.close()


class Reply:
    def __init__(self, status, raw):
        self.status, self.raw = status, raw
        try:
            self.value = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.value = None

    def error_code(self):
        error = self.value.get("error") if isinstance(self.value, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        return code if isinstance(code, str) and _CODE.fullmatch(code) else None


class Session:
    """One signed-in browser, in memory. The cookies and the CSRF token never leave this class."""

    def __init__(self, send):
        self.send, self.cookies, self.csrf, self.signed_in = send, {}, None, False

    def _absorb(self, set_cookies):
        for item in set_cookies:
            first = item.split(";", 1)[0]
            name, _, value = first.partition("=")
            name = name.strip()
            if name in COOKIE_NAMES:
                if value == "" or "max-age=0" in item.lower():
                    self.cookies.pop(name, None)
                else:
                    self.cookies[name] = value

    def request(self, method, path, body=None, *, create=False, mutation=False):
        headers = {"Origin": ORIGIN, "Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = body.encode("utf-8")
        if mutation:
            headers["X-Finweb-CSRF"] = self.csrf or ""
        if self.cookies:
            headers["Cookie"] = "; ".join("%s=%s" % (k, v) for k, v in sorted(self.cookies.items()))
        try:
            status, set_cookies, raw = self.send(method, path, headers, data)
        except NoConnect:
            raise
        except Lost:
            raise Unknown("TRANSPORT_LOST") if create else Finding("TRANSPORT_LOST") from None
        self._absorb(set_cookies)
        return Reply(status, raw)


class Ctx:
    def __init__(self, session):
        self.session = session
        self.sent = False          # a create-route request has been sent (or a create was made earlier in the run): every later surprise is a stop


def _csrf_of(reply):
    token = reply.value.get("csrf_token") if isinstance(reply.value, dict) else None
    return token if isinstance(token, str) and re.fullmatch(r"[0-9a-f]{64}", token) else None


def login(ctx, username, prompt):
    session = ctx.session
    try:
        first = session.request("GET", "/api/v1/auth/session")
    except NoConnect:
        raise Retry("NO_CONNECT", True) from None
    session.csrf = _csrf_of(first)
    if first.status != 200 or session.csrf is None:
        raise Finding("SESSION_UNAVAILABLE")
    password = prompt("web account %s (screen sign-in, not a database role)" % username)
    reply = session.request("POST", "/api/v1/auth/login", json.dumps({"username": username, "password": password}), mutation=True)
    password = None
    if reply.status == 200 and SESSION_COOKIE in session.cookies and _csrf_of(reply) is not None:
        session.csrf, session.signed_in = _csrf_of(reply), True
        emit("login", status=200, verdict="SIGNED_IN")
        return
    code = reply.error_code()
    if (reply.status == 401 and code == "INVALID_CREDENTIALS") or (reply.status == 422 and code == "INVALID_REQUEST"):
        raise Retry("LOGIN_REFUSED", True)
    if reply.status == 429:
        raise Retry("AUTH_RATE_LIMITED", False)
    emit("login", status=reply.status, code=code, body_sha256=sha256_hex(reply.raw), body_bytes=len(reply.raw))
    raise Finding("LOGIN_UNEXPECTED")


def logout(ctx):
    if not ctx.session.signed_in:
        return
    try:
        reply = ctx.session.request("POST", "/api/v1/auth/logout", "{}", mutation=True)
        emit("logout", status=reply.status)
    except (NoConnect, Finding, Unknown):
        emit("logout", code="LOGOUT_NOT_CONFIRMED")


# ---- comparison and expectations -----------------------------------------------------------------------------------------------------------------
def unexpected(ctx, label, reply, *, create):
    emit(label, status=reply.status, code=reply.error_code(), body_sha256=sha256_hex(reply.raw), body_bytes=len(reply.raw), verdict="UNEXPECTED")
    unknown = isinstance(reply.value, dict) and reply.value.get("schema_version") == contract.UNKNOWN_SCHEMA
    if create and (reply.status >= 500 or unknown):
        raise Unknown("CREATE_UNKNOWN")
    raise Finding("UNEXPECTED_RESPONSE")


def expect_refusal(ctx, label, reply, code, *, create):
    """The answer must be the contract's own refusal body for `code`, byte for byte, with the status of `ERRORS[code]`."""
    body = expected_body(code)
    status, kind, detail = contract.ERRORS[code]
    if reply.raw != body or reply.status != status:
        unexpected(ctx, label, reply, create=create)
    emit(label, status=reply.status, code=code, kind=kind, detail=detail, body_text=body.decode("utf-8"), body_sha256=sha256_hex(body), verdict="EXPECTED_REFUSAL")


def _is_committed(value, schema):
    return (isinstance(value, dict) and value.get("schema_version") == schema and value.get("state") == "COMMITTED" and value.get("persisted") is True
            and all(isinstance(value.get(k), str) for k in ("root_id", "operation_id")) and contract.HASH.fullmatch(str(value.get("response_sha256"))) is not None
            and contract.HASH.fullmatch(str(value.get("issued_sha256"))) is not None)


def _committed_line(label, reply, **extra):
    v = reply.value
    emit(label, status=reply.status, root_id=v["root_id"], operation_id=v["operation_id"], response_sha256=v["response_sha256"], issued_sha256=v["issued_sha256"], **extra)


def view(value):
    """The stored result without the fields a create, a replay and a read legitimately differ in: the schema version, `replayed`, and (read/2, HG4
    condition 2) `created_under_generation`, which only a read carries."""
    return {k: v for k, v in value.items() if k not in ("schema_version", "replayed", "created_under_generation")}


def same(label, a, b):
    differs = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    emit(label, verdict="EQUAL" if not differs else "DIFFERS", differs=",".join(differs) or None)
    if differs:
        raise Finding("RESULT_DIFFERS")


def read_root(ctx, label, root, operation):
    reply = ctx.session.request("GET", "%s/roots/%s/operations/%s" % (BASE, root, operation))
    if reply.status != 200 or not _is_committed(reply.value, contract.READ_SCHEMA) or reply.value["root_id"] != root or reply.value["operation_id"] != operation:
        unexpected(ctx, label, reply, create=False)
    _committed_line(label, reply)
    return reply.value


def list_roots(ctx, label):
    reply = ctx.session.request("GET", BASE + "/roots")
    value = reply.value
    if reply.status != 200 or not isinstance(value, dict) or value.get("schema_version") != contract.LIST_SCHEMA or not isinstance(value.get("roots"), list):
        unexpected(ctx, label, reply, create=False)
    entries = value["roots"]
    refused = [e for e in entries if isinstance(e, dict) and "status" in e]
    if refused or not all(isinstance(e, dict) and isinstance(e.get("root_id"), str) for e in entries):
        status = refused[0].get("status") if refused else None
        emit(label, count=len(entries), code=status if isinstance(status, str) and _CODE.fullmatch(status) else None, verdict="LIST_ENTRY_REFUSED")
        raise Finding("LIST_ENTRY_REFUSED")
    emit(label, count=len(entries))
    return entries


def check_count(ctx, label, expected):
    entries = list_roots(ctx, label)
    if len(entries) != expected:
        emit(label, count=len(entries), expected=expected, verdict="COUNT_CHANGED")
        raise Finding("COUNT_CHANGED")
    return entries


# ---- the create-route requests -----------------------------------------------------------------------------------------------------------------
def create_body(args, *, name, quantity=QUANTITY, operation_id=None, context=None):
    return {"schema_version": contract.CREATE_SCHEMA, "operation_id": operation_id or args.operation_id, "source_context_id": context or args.context,
            "expected_release_id": args.release, "name": name, "reporting_currency": "USD", "as_of": AS_OF, "constructed_ledger_acknowledged": True,
            "opening_positions": [{"listing_id": args.listing, "quantity": quantity, "cost_basis": None, "acquired_on": None}],
            "opening_cash": {"currency": "USD", "amount": CASH}}


def send_create(ctx, body):
    ctx.sent = True
    return ctx.session.request("POST", BASE + "/roots", raw_json(body), create=True, mutation=True)


def expect_created(ctx, label, reply, *, status, replayed):
    v = reply.value
    if reply.status != status or not _is_committed(v, contract.CREATE_RESULT_SCHEMA) or v.get("replayed") is not replayed:
        unexpected(ctx, label, reply, create=True)
    _committed_line(label, reply, replayed=replayed)
    return v


# ---- the phases ----------------------------------------------------------------------------------------------------------------------------------
def phase_b(ctx, args, prompt):
    """User B, read-only and before any create: B sees none of A's roots, and A's root, an unknown id and a malformed id all answer the one 404."""
    login(ctx, args.user_b, prompt)
    entries = list_roots(ctx, "b_list")
    if any(e.get("root_id") == args.root for e in entries):
        raise Finding("FOREIGN_ROOT_LISTED")
    if entries:                       # B made no root at R8 (check 10.5: "B sees no roots"): a non-empty list is a finding, whatever it holds (TR8S2 L-5)
        emit("b_list", count=len(entries), verdict="B_LIST_NOT_EMPTY")
        raise Finding("B_LIST_NOT_EMPTY")
    session = ctx.session
    op = args.root_operation
    cases = (("b_read_foreign", "GET", "%s/roots/%s/operations/%s" % (BASE, args.root, op), None),
             ("b_reproduce_foreign", "POST", "%s/roots/%s/operations/%s/reproduce" % (BASE, args.root, op), "{}"),
             ("b_read_unknown", "GET", "%s/roots/%s/operations/%s" % (BASE, UNKNOWN_ROOT, op), None),
             ("b_read_malformed", "GET", "%s/roots/%s/operations/%s" % (BASE, MALFORMED_ROOT, op), None))
    for label, method, path, body in cases:
        expect_refusal(ctx, label, session.request(method, path, body, mutation=body is not None), "RW_NOT_FOUND", create=False)


def phase_pre(ctx, args, prompt):
    login(ctx, args.user_a, prompt)
    entries = list_roots(ctx, "list_before")
    present = any(e.get("operation_id") == args.operation_id for e in entries)
    if present and not args.resume:
        raise Finding("Y_ALREADY_PRESENT")
    expected = EXPECTED_ROOTS_BEFORE_Y + (1 if present else 0)
    if len(entries) != expected:
        emit("list_before", count=len(entries), expected=expected, verdict="COUNT_UNEXPECTED")
        raise Finding("COUNT_UNEXPECTED")
    first = [e for e in entries if e.get("root_id") == args.root]
    if len(first) != 1 or first[0].get("operation_id") != args.root_operation:
        raise Finding("FIRST_ROOT_MISMATCH")
    read_root(ctx, "read_first", args.root, args.root_operation)
    y_body = create_body(args, name=NAME_Y)
    if present:
        created = expect_created(ctx, "create_y", send_create(ctx, y_body), status=200, replayed=True)
    else:
        created = expect_created(ctx, "create_y", send_create(ctx, y_body), status=201, replayed=False)
    root_y = created["root_id"]
    stored = read_root(ctx, "read_y", root_y, args.operation_id)
    replay = expect_created(ctx, "replay_y", send_create(ctx, y_body), status=200, replayed=True)
    same("replay_equals_create", view(created), view(replay))
    same("replay_equals_read", view(stored), view(replay))
    check_count(ctx, "list_after_replay", EXPECTED_ROOTS_BEFORE_Y + 1)
    conflict = create_body(args, name=NAME_CONFLICT, quantity=CONFLICT_QUANTITY)
    expect_refusal(ctx, "conflict_y", send_create(ctx, conflict), "RW_IDEMPOTENCY_CONFLICT", create=True)
    check_count(ctx, "list_after_conflict", EXPECTED_ROOTS_BEFORE_Y + 1)
    same("read_y_after_conflict", view(stored), view(read_root(ctx, "read_y_again", root_y, args.operation_id)))
    invalid = create_body(args, name=NAME_Y, quantity="0", operation_id=str(uuid.uuid5(uuid.UUID(args.operation_id), "r8-supplement-error-422")))
    expect_refusal(ctx, "error_invalid", send_create(ctx, invalid), "REAL_REQUEST_INVALID", create=True)
    unserved = create_body(args, name=NAME_Y, operation_id=str(uuid.uuid5(uuid.UUID(args.operation_id), "r8-supplement-error-404")), context=UNSERVED_CONTEXT)
    expect_refusal(ctx, "error_unserved_context", send_create(ctx, unserved), "RW_NOT_FOUND", create=True)
    check_count(ctx, "list_after_errors", EXPECTED_ROOTS_BEFORE_Y + 1)
    if args.replay_name:
        attempt = send_create(ctx, create_body(args, name=args.replay_name, operation_id=args.root_operation))
        first_view = read_root(ctx, "read_first_again", args.root, args.root_operation)
        if attempt.status == 200 and _is_committed(attempt.value, contract.CREATE_RESULT_SCHEMA) and attempt.value.get("replayed") is True:
            _committed_line("attempt_r8_own_id", attempt, replayed=True)
            same("attempt_equals_first_read", view(first_view), view(attempt.value))
        elif attempt.status == 409 and attempt.raw == expected_body("RW_IDEMPOTENCY_CONFLICT"):
            emit("attempt_r8_own_id", status=409, code="RW_IDEMPOTENCY_CONFLICT", verdict="NAME_DIFFERS", note="a conflict; nothing was written")
        else:
            unexpected(ctx, "attempt_r8_own_id", attempt, create=True)         # a 201 lands here: it latches
        check_count(ctx, "list_after_attempt", EXPECTED_ROOTS_BEFORE_Y + 1)


def phase_post(ctx, args, prompt):
    login(ctx, args.user_a, prompt)
    ctx.sent = True                        # Y was created earlier in this run: from here every difference is a stop
    entries = check_count(ctx, "list_post", EXPECTED_ROOTS_BEFORE_Y + 1)
    y = [e for e in entries if e.get("operation_id") == args.operation_id]
    if len(y) != 1:
        raise Finding("Y_MISSING")
    first = read_root(ctx, "read_first", args.root, args.root_operation)
    if (first["response_sha256"], first["issued_sha256"]) != (args.first_response_sha, args.first_issued_sha):
        emit("read_first", verdict="RESULT_DIFFERS")
        raise Finding("RESULT_DIFFERS")
    reply = ctx.session.request("POST", "%s/roots/%s/operations/%s/reproduce" % (BASE, args.root, args.root_operation), "{}", mutation=True)
    value = reply.value
    if reply.status != 200 or not isinstance(value, dict) or value.get("schema_version") != contract.REPRODUCE_SCHEMA or value.get("status") not in contract.REPRODUCE_STATUSES:
        unexpected(ctx, "reproduce_first", reply, create=False)
    emit("reproduce_first", status=200, reproduce_status=value["status"], issued_sha256=value.get("issued_sha256"))
    if value["status"] != "REPRODUCED":
        raise Finding(REPRODUCE_FINDINGS[value["status"]])
    if value.get("issued_sha256") != args.first_issued_sha:
        raise Finding("RESULT_DIFFERS")
    stored = read_root(ctx, "read_y", y[0]["root_id"], args.operation_id)
    if (stored["response_sha256"], stored["issued_sha256"]) != (args.y_response_sha, args.y_issued_sha):
        emit("read_y", verdict="RESULT_DIFFERS")
        raise Finding("RESULT_DIFFERS")
    replay = expect_created(ctx, "replay_y", send_create(ctx, create_body(args, name=NAME_Y)), status=200, replayed=True)
    same("replay_equals_read", view(stored), view(replay))
    expect_refusal(ctx, "conflict_y", send_create(ctx, create_body(args, name=NAME_CONFLICT, quantity=CONFLICT_QUANTITY)), "RW_IDEMPOTENCY_CONFLICT", create=True)
    check_count(ctx, "list_after", EXPECTED_ROOTS_BEFORE_Y + 1)


PHASES = {"b": phase_b, "pre": phase_pre, "post": phase_post}


# ---- the command line -----------------------------------------------------------------------------------------------------------------------------
class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError()


def _build_parser():
    parser = _Parser(prog="r8_http_check", description="Loopback checks for the R8 supplementary run. Started by r8_supplement.")
    parser.add_argument("--phase", required=True, choices=sorted(PHASES))
    parser.add_argument("--resume", action="store_true")
    for name in ("--operation-id", "--context", "--release", "--listing", "--root", "--root-operation", "--user-a", "--user-b", "--replay-name",
                 "--first-response-sha", "--first-issued-sha", "--y-response-sha", "--y-issued-sha"):
        parser.add_argument(name)
    parser.add_argument("--acknowledged", choices=("yes",))
    return parser


def _canonical_uuid(value):
    try:
        return value is not None and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _validate(args):
    """Refuse an unusable command line before anything is sent."""
    need = {"b": ("user_b", "root", "root_operation"),
            "pre": ("user_a", "root", "root_operation", "operation_id", "context", "release", "listing", "acknowledged"),
            "post": ("user_a", "root", "root_operation", "operation_id", "context", "release", "listing", "acknowledged", "first_response_sha", "first_issued_sha",
                     "y_response_sha", "y_issued_sha")}[args.phase]
    values = {"user_a": args.user_a, "user_b": args.user_b, "root": args.root, "root_operation": args.root_operation, "operation_id": args.operation_id, "context": args.context,
              "release": args.release, "listing": args.listing, "acknowledged": args.acknowledged, "first_response_sha": args.first_response_sha,
              "first_issued_sha": args.first_issued_sha, "y_response_sha": args.y_response_sha, "y_issued_sha": args.y_issued_sha}
    if any(values[name] is None for name in need):
        raise UsageError()
    if any(values[name] is not None and not _USERNAME.fullmatch(values[name]) for name in ("user_a", "user_b")):
        raise UsageError()
    if not all(_canonical_uuid(values[name]) for name in ("root", "root_operation") + (("operation_id",) if args.phase != "b" else ())):
        raise UsageError()
    for name in ("context", "release", "first_response_sha", "first_issued_sha", "y_response_sha", "y_issued_sha"):
        if values[name] is not None and not contract.HASH.fullmatch(values[name]):
            raise UsageError()
    if args.phase != "b":
        try:
            contract.validate_intent(create_body(args, name=NAME_Y))
            contract.validate_intent(create_body(args, name=NAME_CONFLICT, quantity=CONFLICT_QUANTITY))
            if args.replay_name:
                contract.validate_intent(create_body(args, name=args.replay_name, operation_id=args.root_operation))
        except (ValueError, TypeError):
            raise UsageError() from None


def main(argv=None, *, send=None, prompt=None):
    try:
        args = _build_parser().parse_args(argv)
        _validate(args)
    except UsageError:
        emit("usage", code="USAGE", verdict="NOTHING_SENT")
        return EXIT_USAGE
    try:
        prompt_route.require_genuine(pf)               # before any prompt is built or used
    except prompt_route.PromptRouteError:
        emit("prompt_route", code="PROMPT_ROUTE", verdict="NOTHING_SENT")
        return EXIT_USAGE
    ctx = Ctx(Session(send or default_send))
    try:
        PHASES[args.phase](ctx, args, prompt or pf.terminal_prompt)
        return EXIT_OK
    except Retry as retry:
        emit("retry", code=retry.code, counts_as_typo=retry.counts)
        return EXIT_RETRY
    except NoConnect:
        emit("retry", code="NO_CONNECT", counts_as_typo=True)
        return EXIT_RETRY if not ctx.sent else EXIT_UNEXPECTED
    except Unknown as unknown:
        emit("finding", code=unknown.code, verdict="UNKNOWN")
        return EXIT_UNKNOWN
    except Finding as finding:
        emit("finding", code=finding.code, verdict="AFTER_A_CREATE" if ctx.sent else "BEFORE_ANY_CREATE")
        return EXIT_UNEXPECTED if ctx.sent else EXIT_FINDING
    except Exception as error:                                       # noqa: BLE001 - the class name only
        emit("uncaught", code=type(error).__name__, verdict="STOP")
        return 1
    finally:
        logout(ctx)


if __name__ == "__main__":
    sys.exit(main())
