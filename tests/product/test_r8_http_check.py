"""F1 R8 supplementary run: the loopback check tool (`src/real_tools/r8_http_check.py`), against a FAKE launcher. No socket, no database, no cluster, no network.

The fake stands in for the real-mode app at the level the tool sees: the session and login routes (a cookie and a CSRF token, both SENTINEL values that must
never appear in the tool's output), the list, read and reproduce routes, and the create route with its replay, its conflict and its two early refusals. Its
refusal bodies are built by the contract (`canonical_json(refusal_payload(ContractRefusal(code)))`), as the server builds them (TR8S M-1).
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
import uuid

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from marketdata.canonical import canonical_json  # noqa: E402
from real_tools import r8_http_check as t  # noqa: E402
from web_api import auth, real_launcher, real_scoped_contract as contract  # noqa: E402

CTX, REL = "c" * 64, "d" * 64
LISTING = "8dc364a1-67c8-5d46-8654-cff17ebe25de"
FIRST_ROOT, FIRST_OP = "a51651b9-26b9-520e-a0db-46f912743153", "a454d861-dc6f-438b-ac77-d48162835ebc"
SECOND_ROOT, SECOND_OP = "33333333-3333-4333-8333-333333333333", "44444444-4444-4444-8444-444444444444"
Y_OP = "55555555-5555-4555-8555-555555555555"
PASSWORDS = {"alice": "ALICE-PASSWORD-SENTINEL-1", "bob": "BOB-PASSWORD-SENTINEL-2"}
COOKIE_SENTINEL = "COOKIE-SENTINEL-"
HEADER_SENTINEL = "HEADER-SENTINEL-VALUE"
# The real tokens (TR8S2 L-2): the bootstrap cookie and the session cookie each have their own CSRF token, `sha256("finweb.cp7.csrf/1:" + cookie value)` (auth.csrf_token).
BOOT_COOKIE = COOKIE_SENTINEL + "boot"
BOOT_TOKEN = auth.csrf_token(BOOT_COOKIE)
SESSION_TOKENS = {"alice": auth.csrf_token(COOKIE_SENTINEL + "alice"), "bob": auth.csrf_token(COOKIE_SENTINEL + "bob")}
CSRF_SENTINEL = BOOT_TOKEN                                  # kept for the tests that name "the token"
SENTINELS = (PASSWORDS["alice"], PASSWORDS["bob"], BOOT_TOKEN, *SESSION_TOKENS.values(), COOKIE_SENTINEL, HEADER_SENTINEL)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def refusal(code):
    return canonical_json(contract.refusal_payload(contract.ContractRefusal(code))).encode("utf-8"), contract.ERRORS[code][0]


def digests(op):
    return sha("response:" + op), sha("issued:" + op)


def committed(schema, root, op, replayed=None):
    r, i = digests(op)
    value = {"schema_version": schema, "state": "COMMITTED", "persisted": True, "root_id": root, "operation_id": op, "revision_id": str(uuid.uuid5(uuid.NAMESPACE_URL, op)),
             "ledger_pin": 2, "response_sha256": r, "issued_sha256": i, "result": {"holding": "1234.5"}}
    if replayed is not None:
        value["replayed"] = replayed
    return value


def body_of(value):
    return canonical_json(value).encode("utf-8")


class FakeLauncher:
    """The real-mode app as the tool sees it. `hooks` may answer a request first: hook(method, path, body_dict, fake) -> (status, raw) or None."""

    def __init__(self):
        self.log, self.hooks, self.logouts, self.cookie_log = [], [], 0, []
        self.sessions = {}                                      # session cookie value -> user
        self.owner = {FIRST_ROOT: "alice", SECOND_ROOT: "alice"}
        self.root_op = {FIRST_ROOT: FIRST_OP, SECOND_ROOT: SECOND_OP}
        self.ops = {}                                           # operation id -> (owner, body dict, root)
        self.ops[FIRST_OP] = ("alice", None, FIRST_ROOT)       # R8's own create: its body is whatever a test sets
        self.login_mode = None                                  # None | "typo" | "short" | "busy" | "weird"
        self.refuse_connect = False
        self.extra_roots = 0

    def user_of(self, headers):
        cookie = headers.get("Cookie", "")
        for part in cookie.split("; "):
            name, _, value = part.partition("=")
            if name == "finweb_real_session":
                return self.sessions.get(value)
        return None

    def send(self, method, path, headers, body):
        if self.refuse_connect:
            raise t.NoConnect()
        assert headers.get("Origin") == t.ORIGIN, "the launcher allows only the Vite origin"
        body_dict = json.loads(body.decode()) if body else None
        self.log.append((method, path, body_dict))
        self.cookie_log.append((path, headers.get("Cookie", "")))
        for hook in self.hooks:
            answer = hook(method, path, body_dict, self)
            if answer is not None:
                return answer[0], [], answer[1]
        user = self.user_of(headers)
        if path == "/api/v1/auth/session":
            if user is not None:
                return 200, [], body_of({"csrf_token": SESSION_TOKENS[user], "authenticated": True})
            return 200, ["finweb_real_csrf=%s; Max-Age=900; Path=/api; HttpOnly" % BOOT_COOKIE, "X-Other=%s" % HEADER_SENTINEL], body_of({"csrf_token": BOOT_TOKEN, "authenticated": False})
        if method == "POST":
            # the real routes: a session's mutation needs the SESSION token; the login (no session yet) needs the token of the bootstrap cookie it holds
            expected = SESSION_TOKENS[user] if user is not None else (BOOT_TOKEN if "finweb_real_csrf=%s" % BOOT_COOKIE in headers.get("Cookie", "") else None)
            if headers.get("X-Finweb-CSRF") != expected:
                return 403, [], body_of({"schema_version": "x", "error": {"code": "CSRF_REJECTED", "detail": "An explicitly configured request origin and CSRF token are required",
                                                                         "state": "INSUFFICIENT_DATA"}})
            assert headers.get("Content-Type") == "application/json"
        if path == "/api/v1/auth/login":
            who = body_dict["username"]
            if self.login_mode == "typo" or PASSWORDS.get(who) != body_dict["password"]:
                return 401, [], body_of({"schema_version": "x", "error": {"code": "INVALID_CREDENTIALS", "detail": "Username or password is incorrect", "state": "INSUFFICIENT_DATA"}})
            if self.login_mode == "short":
                return 422, [], body_of({"schema_version": "x", "error": {"code": "INVALID_REQUEST", "detail": "Invalid request", "state": "INSUFFICIENT_DATA"}})
            if self.login_mode == "busy":
                return 429, [], body_of({"schema_version": "x", "error": {"code": "AUTH_RATE_LIMITED", "detail": "retry shortly", "state": "INSUFFICIENT_DATA"}})
            if self.login_mode == "weird":
                return 503, [], b"LEAK " + COOKIE_SENTINEL.encode() + b" " + CSRF_SENTINEL.encode()
            cookie = COOKIE_SENTINEL + who
            self.sessions[cookie] = who
            return 200, ["finweb_real_session=%s; Max-Age=86400; Path=/api; HttpOnly; SameSite=Strict" % cookie,
                         "finweb_real_csrf=; Max-Age=0; Path=/api; HttpOnly; SameSite=Strict"], body_of({"authenticated": True, "csrf_token": SESSION_TOKENS[who]})
        if path == "/api/v1/auth/logout":
            self.logouts += 1
            return 200, [], body_of({"authenticated": False, "csrf_token": BOOT_TOKEN})
        if user is None:
            return 401, [], body_of({"error": {"code": "AUTHENTICATION_REQUIRED"}})
        if path == "/api/real/v1/roots" and method == "GET":
            roots = [{"root_id": r, "operation_id": self.root_op[r], "context_id": CTX, "generation": 3, "created_at": "2026-11-16T00:00:00Z", "origin": {}}
                     for r, o in self.owner.items() if o == user]
            roots += [{"root_id": "99999999-9999-4999-8999-%012d" % n, "operation_id": "88888888-8888-4888-8888-%012d" % n, "context_id": CTX, "generation": 3,
                       "created_at": "x", "origin": {}} for n in range(self.extra_roots)] if user == "alice" else []
            return 200, [], body_of({"schema_version": contract.LIST_SCHEMA, "roots": roots})
        parts = path.split("/")
        if len(parts) == 7 and parts[:4] == ["", "api", "real", "v1"] and parts[4] == "roots" and parts[6] == "operations":
            pass
        if path.startswith("/api/real/v1/roots/") and "/operations/" in path:
            tail = path[len("/api/real/v1/roots/"):]
            root, _, rest = tail.partition("/operations/")
            op, _, action = rest.partition("/")
            if self.owner.get(root) != user:
                raw, status = refusal("RW_NOT_FOUND")
                return status, [], raw
            if action == "reproduce":
                return 200, [], body_of({"schema_version": contract.REPRODUCE_SCHEMA, "root_id": root, "operation_id": op, "status": "REPRODUCED", "detail": "",
                                         "issued_sha256": digests(op)[1]})
            return 200, [], body_of(committed(contract.READ_SCHEMA, root, op))
        if path == "/api/real/v1/roots" and method == "POST":
            return self.create(user, body_dict)
        return 404, [], b"{}"

    def create(self, user, body):
        def answer(code):
            raw, status = refusal(code)
            return status, [], raw
        try:
            contract.validate_intent(body)
        except (ValueError, TypeError):
            return answer("REAL_REQUEST_INVALID")
        if body["source_context_id"] != CTX:
            return answer("RW_NOT_FOUND")
        op = body["operation_id"]
        if op in self.ops:
            owner, prior, root = self.ops[op]
            if prior is None or prior != body:
                return answer("RW_IDEMPOTENCY_CONFLICT")
            return 200, [], body_of(committed(contract.CREATE_RESULT_SCHEMA, root, op, replayed=True))
        root = str(uuid.uuid5(uuid.NAMESPACE_URL, op))
        self.ops[op] = (user, body, root)
        self.owner[root], self.root_op[root] = user, op
        return 201, [], body_of(committed(contract.CREATE_RESULT_SCHEMA, root, op, replayed=False))

    def creates(self):
        return [entry for entry in self.log if entry[0] == "POST" and entry[1] == "/api/real/v1/roots"]


def run_tool(fake, *argv, passwords=None, prompts=None):
    """Run `main` against the fake; returns (exit status, [S8 lines], raw stdout)."""
    out = io.StringIO()
    asked = prompts if prompts is not None else []

    def prompt(label):
        asked.append(label)
        for name, password in (passwords or PASSWORDS).items():
            if name in label:
                return password
        return "wrong-password-sentinel-0"
    with contextlib.redirect_stdout(out):
        code = t.main(list(argv), send=fake.send, prompt=prompt)
    text = out.getvalue()
    lines = [json.loads(line[3:]) for line in text.splitlines() if line.startswith("S8 ")]
    return code, lines, text


def pre_args(op=Y_OP, *extra):
    return ["--phase", "pre", "--user-a", "alice", "--root", FIRST_ROOT, "--root-operation", FIRST_OP, "--operation-id", op, "--context", CTX, "--release", REL,
            "--listing", LISTING, "--acknowledged", "yes", *extra]


def post_args(op=Y_OP):
    first, y = digests(FIRST_OP), digests(op)
    return ["--phase", "post", "--user-a", "alice", "--root", FIRST_ROOT, "--root-operation", FIRST_OP, "--operation-id", op, "--context", CTX, "--release", REL,
            "--listing", LISTING, "--acknowledged", "yes", "--first-response-sha", first[0], "--first-issued-sha", first[1], "--y-response-sha", y[0], "--y-issued-sha", y[1]]


B_ARGS = ["--phase", "b", "--user-b", "bob", "--root", FIRST_ROOT, "--root-operation", FIRST_OP]


def label_of(lines, label):
    return [line for line in lines if line["label"] == label]


def fresh():
    return FakeLauncher()


class ExpectedBodyTests(unittest.TestCase):
    def test_the_expected_body_is_built_from_a_contract_refusal_not_from_a_string(self):
        for code in ("RW_NOT_FOUND", "RW_IDEMPOTENCY_CONFLICT", "REAL_REQUEST_INVALID"):
            body = json.loads(t.expected_body(code))
            self.assertEqual(body["error"]["code"], code)                     # the trap: refusal_payload("CODE") would say REAL_UNAVAILABLE
            self.assertEqual(body["state"], "REFUSED")
            self.assertIs(body["persisted"], False)
            self.assertIs(body["operation_recorded"], False)
        trap = json.loads(canonical_json(contract.refusal_payload("RW_NOT_FOUND")))
        self.assertEqual(trap["error"]["code"], "REAL_UNAVAILABLE")
        self.assertNotEqual(canonical_json(contract.refusal_payload("RW_NOT_FOUND")).encode(), t.expected_body("RW_NOT_FOUND"))

    def test_the_fakes_refusals_equal_the_expected_bodies(self):
        for code in ("RW_NOT_FOUND", "RW_IDEMPOTENCY_CONFLICT", "REAL_REQUEST_INVALID"):
            self.assertEqual(refusal(code), (t.expected_body(code), contract.ERRORS[code][0]))

    def test_the_port_is_the_launchers_default_and_the_origin_is_one_it_allows(self):
        self.assertEqual((t.HOST, t.PORT), ("127.0.0.1", real_launcher.DEFAULT_PORT))
        self.assertIn(5175, real_launcher.ORIGIN_PORTS)
        self.assertEqual(t.ORIGIN, "http://127.0.0.1:5175")

    def test_the_list_schema_is_version_2_with_the_operation_id_the_tool_reads(self):
        self.assertEqual(contract.LIST_SCHEMA, "finweb.cp7.real_scoped_list/2")
        fake = fresh()
        code, lines, _ = run_tool(fake, *pre_args())
        self.assertEqual(code, 0)                                   # the tool found A's first root by the list entry's operation_id

    def test_the_acknowledgement_sentence_the_runner_shows_is_the_screens(self):
        from real_tools import r8_supplement
        text = (HERE.parents[1] / "web" / "src" / "real-mode-i18n.ts").read_text("utf8")
        self.assertIn("fieldAck: '%s'" % r8_supplement.ACK_SENTENCE, text)


class PhaseBTests(unittest.TestCase):
    def test_b_sees_none_of_as_roots_and_four_answers_are_the_one_404(self):
        fake = fresh()
        code, lines, _ = run_tool(fake, *B_ARGS)
        self.assertEqual(code, 0)
        for label in ("b_read_foreign", "b_reproduce_foreign", "b_read_unknown", "b_read_malformed"):
            (line,) = label_of(lines, label)
            self.assertEqual((line["status"], line["code"], line["verdict"]), (404, "RW_NOT_FOUND", "EXPECTED_REFUSAL"))
            self.assertEqual(line["body_text"], t.expected_body("RW_NOT_FOUND").decode())
        self.assertEqual(len({line["body_sha256"] for line in lines if line.get("body_sha256")}), 1)
        self.assertEqual(label_of(lines, "b_list")[0]["count"], 0)
        self.assertEqual(fake.creates(), [])
        self.assertEqual(fake.logouts, 1)
        self.assertIn("/api/real/v1/roots/not-a-uuid/operations/%s" % FIRST_OP, [p for _, p, _ in fake.log])      # no "/" in the malformed id: it must not fall to the closed route

    def test_b_phase_sends_no_create_route_request_even_when_it_finds_something(self):
        fake = fresh()
        fake.owner[FIRST_ROOT] = "bob"                       # A's root listed for B
        code, lines, _ = run_tool(fake, *B_ARGS)
        self.assertEqual(code, t.EXIT_FINDING)
        self.assertEqual(fake.creates(), [])
        self.assertEqual(label_of(lines, "finding")[0]["code"], "FOREIGN_ROOT_LISTED")

    def test_a_foreign_answer_that_is_not_the_contract_body_is_a_finding(self):
        fake = fresh()
        fake.hooks.append(lambda m, p, b, f: (404, b'{"error":{"code":"RW_NOT_FOUND"}}') if "/operations/" in p and "reproduce" not in p and FIRST_ROOT in p else None)
        code, lines, _ = run_tool(fake, *B_ARGS)
        self.assertEqual(code, t.EXIT_FINDING)
        self.assertEqual(label_of(lines, "b_read_foreign")[0]["verdict"], "UNEXPECTED")


class PhasePreTests(unittest.TestCase):
    def test_the_whole_phase_passes_and_each_expectation_is_printed(self):
        fake = fresh()
        code, lines, _ = run_tool(fake, *pre_args())
        self.assertEqual(code, 0, lines[-3:])
        self.assertEqual(label_of(lines, "list_before")[0]["count"], 2)
        self.assertEqual((label_of(lines, "create_y")[0]["status"], label_of(lines, "create_y")[0]["replayed"]), (201, False))
        self.assertEqual((label_of(lines, "replay_y")[0]["status"], label_of(lines, "replay_y")[0]["replayed"]), (200, True))
        self.assertEqual({line["verdict"] for line in lines if line["label"].startswith("replay_equals")}, {"EQUAL"})
        for label, code_expected, status in (("conflict_y", "RW_IDEMPOTENCY_CONFLICT", 409), ("error_invalid", "REAL_REQUEST_INVALID", 422), ("error_unserved_context", "RW_NOT_FOUND", 404)):
            (line,) = label_of(lines, label)
            self.assertEqual((line["status"], line["code"], line["verdict"], line["body_text"]), (status, code_expected, "EXPECTED_REFUSAL", t.expected_body(code_expected).decode()))
            self.assertEqual(line["body_sha256"], hashlib.sha256(t.expected_body(code_expected)).hexdigest())
        for label in ("list_after_replay", "list_after_conflict", "list_after_errors"):
            self.assertEqual(label_of(lines, label)[0]["count"], 3)
        self.assertEqual(label_of(lines, "read_first")[0]["response_sha256"], digests(FIRST_OP)[0])
        self.assertEqual(len(fake.ops), 2)                    # R8's operation and Y: the refused requests and the replay wrote nothing
        self.assertEqual(fake.logouts, 1)

    def test_y_is_created_with_the_inputs_of_r8_and_the_acknowledgement_flag(self):
        fake = fresh()
        run_tool(fake, *pre_args())
        body = fake.creates()[0][2]
        self.assertEqual((body["as_of"], body["opening_positions"][0]["quantity"], body["opening_cash"]["amount"], body["name"]), ("2026-09-30", "10", "500", "R8 supplement"))
        self.assertIs(body["constructed_ledger_acknowledged"], True)
        self.assertEqual(body["operation_id"], Y_OP)

    def test_a_count_other_than_two_stops_before_any_create(self):
        for extra in (1, 0):
            fake = fresh()
            fake.extra_roots = extra
            if extra == 0:
                del fake.owner[SECOND_ROOT]
            code, lines, _ = run_tool(fake, *pre_args())
            self.assertEqual(code, t.EXIT_FINDING)
            self.assertEqual(fake.creates(), [])
            self.assertEqual(label_of(lines, "list_before")[-1]["verdict"], "COUNT_UNEXPECTED")
            self.assertEqual(fake.logouts, 1)

    def test_y_already_present_without_resume_is_a_finding_and_with_resume_expects_the_200(self):
        fake = fresh()
        self.assertEqual(run_tool(fake, *pre_args())[0], 0)
        code, lines, _ = run_tool(fake, *pre_args())
        self.assertEqual((code, label_of(lines, "finding")[0]["code"]), (t.EXIT_FINDING, "Y_ALREADY_PRESENT"))
        before = len(fake.creates())
        code, lines, _ = run_tool(fake, *pre_args(Y_OP, "--resume"))
        self.assertEqual(code, 0, lines[-3:])                         # a rerun does not latch on the expected 200
        self.assertEqual((label_of(lines, "create_y")[0]["status"], label_of(lines, "create_y")[0]["replayed"]), (200, True))
        self.assertEqual(label_of(lines, "list_before")[0]["count"], 3)
        self.assertGreater(len(fake.creates()), before)
        self.assertEqual(len(fake.ops), 2)

    def test_a_resume_after_a_run_that_died_before_the_create_expects_the_201(self):
        fake = fresh()
        code, lines, _ = run_tool(fake, *pre_args(Y_OP, "--resume"))
        self.assertEqual(code, 0)
        self.assertEqual(label_of(lines, "create_y")[0]["status"], 201)

    def test_first_root_mismatch_is_a_finding_before_the_create(self):
        fake = fresh()
        fake.root_op[FIRST_ROOT] = "77777777-7777-4777-8777-777777777777"
        code, lines, _ = run_tool(fake, *pre_args())
        self.assertEqual((code, fake.creates()), (t.EXIT_FINDING, []))

    def test_unexpected_answers_after_the_create_stop_with_no_further_request(self):
        def hook_for(match, answer):
            seen = []

            def hook(method, path, body, fake):
                if method == "POST" and path == "/api/real/v1/roots" and match(body, len(fake.creates())):
                    seen.append(1)
                    return answer
                return None
            return hook, seen
        wrong_body = (409, b'{"error":{"code":"RW_IDEMPOTENCY_CONFLICT"}}')
        cases = {
            "the create answers 500": (lambda b, n: n == 1, (500, b"oops"), t.EXIT_UNKNOWN),
            "the create answers a 503 UNKNOWN body": (lambda b, n: n == 1, (503, body_of({"schema_version": contract.UNKNOWN_SCHEMA, "state": "UNKNOWN"})), t.EXIT_UNKNOWN),
            "the create answers a refusal": (lambda b, n: n == 1, refusal("RW_WITHDRAWN")[::-1], t.EXIT_UNEXPECTED),
            "the create is not JSON": (lambda b, n: n == 1, (201, b"<html>"), t.EXIT_UNEXPECTED),
            "the replay is a 201": (lambda b, n: n == 2, (201, body_of(committed(contract.CREATE_RESULT_SCHEMA, "x", Y_OP, replayed=False))), t.EXIT_UNEXPECTED),
            "the replay result differs": (lambda b, n: n == 2, (200, body_of(dict(committed(contract.CREATE_RESULT_SCHEMA, str(uuid.uuid5(uuid.NAMESPACE_URL, Y_OP)), Y_OP, replayed=True), result={"holding": "1"}))), t.EXIT_UNEXPECTED),
            "the conflict answers the wrong bytes": (lambda b, n: n == 3, wrong_body, t.EXIT_UNEXPECTED),
            "the conflict is a replay": (lambda b, n: n == 3, (200, body_of(committed(contract.CREATE_RESULT_SCHEMA, "x", Y_OP, replayed=True))), t.EXIT_UNEXPECTED),
            "the invalid request is a 201": (lambda b, n: n == 4, (201, body_of(committed(contract.CREATE_RESULT_SCHEMA, "x", "y", replayed=False))), t.EXIT_UNEXPECTED),
            "the unserved context is a 503": (lambda b, n: n == 5, (503, b"closed"), t.EXIT_UNKNOWN),
        }
        for name, (match, answer, expected_exit) in cases.items():
            with self.subTest(name):
                fake = fresh()
                hook, seen = hook_for(match, answer)
                fake.hooks.append(hook)
                code, lines, _ = run_tool(fake, *pre_args())
                self.assertEqual(code, expected_exit, (name, lines[-2:]))
                self.assertTrue(seen)
                self.assertEqual(len(fake.creates()), next(n for n in range(1, 6) if match(None, n)))        # nothing was sent after the failing create
                self.assertEqual(fake.logouts, 1)

    def test_a_count_that_changes_after_a_refusal_is_a_stop(self):
        fake = fresh()
        state = {"n": 0}

        def hook(method, path, body, f):
            if method == "POST" and path == "/api/real/v1/roots" and body and body.get("opening_positions", [{}])[0].get("quantity") == "11":
                f.extra_roots = 1                                  # the conflicting request "wrote" a root
            return None
        fake.hooks.append(hook)
        code, lines, _ = run_tool(fake, *pre_args())
        self.assertEqual(code, t.EXIT_UNEXPECTED)
        self.assertEqual(label_of(lines, "list_after_conflict")[-1]["verdict"], "COUNT_CHANGED")

    def test_failures_before_the_create_are_findings_not_retries_and_send_no_create(self):
        cases = {"the list is a 503": lambda m, p, b, f: (503, b"x") if m == "GET" and p == "/api/real/v1/roots" else None,
                 "a list entry carries a refusal status": lambda m, p, b, f: (200, body_of({"schema_version": contract.LIST_SCHEMA, "roots": [{"root_id": FIRST_ROOT, "context_id": CTX, "status": "RW_WITHDRAWN"}]}))
                 if m == "GET" and p == "/api/real/v1/roots" else None,
                 "reading the first root is a 503": lambda m, p, b, f: (503, body_of({"error": {"code": "REAL_UNAVAILABLE"}})) if m == "GET" and "/operations/" in p else None,
                 "reading the first root is a 409": lambda m, p, b, f: refusal("RW_RIGHT_REFUSED")[::-1] if m == "GET" and "/operations/" in p else None}
        for name, hook in cases.items():
            with self.subTest(name):
                fake = fresh()
                fake.hooks.append(hook)
                code, lines, _ = run_tool(fake, *pre_args())
                self.assertEqual(code, t.EXIT_FINDING, name)
                self.assertEqual(fake.creates(), [])
                self.assertEqual(fake.logouts, 1)

    def test_the_single_attempt_at_r8s_own_id(self):
        for case in ("match", "differs", "created"):
            with self.subTest(case):
                fake = fresh()
                name = "the name I remember"
                if case == "match":
                    fake.ops[FIRST_OP] = ("alice", t.create_body(type("A", (), dict(operation_id=Y_OP, context=CTX, release=REL, listing=LISTING)), name=name, operation_id=FIRST_OP), FIRST_ROOT)
                if case == "created":
                    del fake.ops[FIRST_OP]                         # not possible on the real gateway: a 201 here must latch
                code, lines, _ = run_tool(fake, *pre_args(Y_OP, "--replay-name", name))
                (line,) = label_of(lines, "attempt_r8_own_id")
                if case == "match":
                    self.assertEqual((code, line["status"], line["replayed"]), (0, 200, True))
                    self.assertEqual(label_of(lines, "attempt_equals_first_read")[0]["verdict"], "EQUAL")
                elif case == "differs":
                    self.assertEqual((code, line["status"], line["code"], line["verdict"]), (0, 409, "RW_IDEMPOTENCY_CONFLICT", "NAME_DIFFERS"))
                else:
                    self.assertEqual((code, line["verdict"]), (t.EXIT_UNEXPECTED, "UNEXPECTED"))
                    self.assertEqual(len(fake.creates()), 6)     # Y, replay, conflict, 422, 404, the attempt

    def test_without_a_replay_name_no_attempt_is_made(self):
        fake = fresh()
        code, lines, _ = run_tool(fake, *pre_args())
        self.assertEqual(label_of(lines, "attempt_r8_own_id"), [])
        self.assertEqual(len(fake.creates()), 5)


class PhasePostTests(unittest.TestCase):
    def after_pre(self):
        fake = fresh()
        self.assertEqual(run_tool(fake, *pre_args())[0], 0)
        return fake

    def test_after_the_restart_everything_reads_and_replays_equal(self):
        fake = self.after_pre()
        code, lines, _ = run_tool(fake, *post_args())
        self.assertEqual(code, 0, lines[-3:])
        self.assertEqual(label_of(lines, "reproduce_first")[0]["reproduce_status"], "REPRODUCED")
        self.assertEqual((label_of(lines, "replay_y")[0]["status"], label_of(lines, "conflict_y")[0]["status"]), (200, 409))
        self.assertEqual(label_of(lines, "list_post")[0]["count"], 3)
        self.assertEqual(len(fake.ops), 2)

    def test_a_digest_that_differs_after_the_restart_is_a_stop_with_no_create_sent(self):
        fake = self.after_pre()
        args = post_args()
        args[args.index("--first-response-sha") + 1] = "0" * 64
        before = len(fake.creates())
        code, lines, _ = run_tool(fake, *args)
        self.assertEqual(code, t.EXIT_UNEXPECTED)
        self.assertEqual(len(fake.creates()), before)

    def test_the_post_restart_comparisons_each_stop_the_run(self):
        """Each of these was a surviving mutant at TR8S2: the Y digests, the reproduce's issued digest, a root that appeared, a refused connection after a create."""
        first_issued = digests(FIRST_OP)[1]
        cases = {}
        args = post_args()
        args[args.index("--y-response-sha") + 1] = "0" * 64
        cases["Y's response digest differs after the restart"] = (args, None, "RESULT_DIFFERS")
        args = post_args()
        args[args.index("--y-issued-sha") + 1] = "0" * 64
        cases["Y's issued digest differs after the restart"] = (args, None, "RESULT_DIFFERS")
        cases["the reproduce reports REPRODUCED with another issued digest"] = (post_args(), lambda m, p, b, f: (200, body_of({"schema_version": contract.REPRODUCE_SCHEMA, "root_id": FIRST_ROOT,
                                                                       "operation_id": FIRST_OP, "status": "REPRODUCED", "detail": "", "issued_sha256": "9" * 64})) if p.endswith("/reproduce") else None, "RESULT_DIFFERS")
        for name, (argv, hook, code) in cases.items():
            with self.subTest(name):
                fake = self.after_pre()
                if hook:
                    fake.hooks.append(hook)
                before = len(fake.creates())
                exit_code, lines, _ = run_tool(fake, *argv)
                self.assertEqual((exit_code, label_of(lines, "finding")[0]["code"]), (t.EXIT_UNEXPECTED, code))
                self.assertEqual(len(fake.creates()), before)              # stopped before the replay and the conflict
        fake = self.after_pre()
        fake.extra_roots = 1                                               # the start-of-post count check
        exit_code, lines, _ = run_tool(fake, *post_args())
        self.assertEqual((exit_code, label_of(lines, "list_post")[-1]["verdict"]), (t.EXIT_UNEXPECTED, "COUNT_CHANGED"))
        self.assertEqual(len(fake.creates()), 5)
        self.assertEqual(first_issued, digests(FIRST_OP)[1])

    def test_a_refused_connection_after_a_create_was_sent_is_a_stop_not_a_retry(self):
        fake = fresh()

        def refuse_second_create(method, path, body, f):
            if method == "POST" and path == "/api/real/v1/roots" and len(f.creates()) == 2:
                f.refuse_connect = True
            return None
        fake.hooks.append(refuse_second_create)
        code, lines, _ = run_tool(fake, *pre_args())
        self.assertEqual(code, t.EXIT_UNEXPECTED)

    def test_b_with_any_root_of_its_own_is_a_finding_and_a_listed_foreign_root_too(self):
        fake = fresh()
        fake.owner["bob-root"], fake.root_op["bob-root"] = "bob", "66666666-6666-4666-8666-666666666666"
        code, lines, _ = run_tool(fake, *B_ARGS)
        self.assertEqual((code, label_of(lines, "finding")[0]["code"], fake.creates()), (t.EXIT_FINDING, "B_LIST_NOT_EMPTY", []))

    def test_every_other_reproduce_status_is_a_stop(self):
        for status in ("RESULT_DIFFERS", "INPUT_MISMATCH", "SOURCE_REFUSED"):
            with self.subTest(status):
                fake = self.after_pre()
                fake.hooks.append(lambda m, p, b, f, status=status: (200, body_of({"schema_version": contract.REPRODUCE_SCHEMA, "root_id": FIRST_ROOT, "operation_id": FIRST_OP,
                                                                                    "status": status, "detail": "x", "issued_sha256": None})) if p.endswith("/reproduce") else None)
                code, lines, _ = run_tool(fake, *post_args())
                self.assertEqual((code, label_of(lines, "finding")[0]["code"]), (t.EXIT_UNEXPECTED, "REPRODUCE_" + status))

    def test_a_coded_read_refusal_after_the_restart_is_a_stop_not_a_retry(self):
        fake = self.after_pre()
        fake.hooks.append(lambda m, p, b, f: (503, body_of({"error": {"code": "REAL_UNAVAILABLE"}})) if m == "GET" and "/operations/" in p else None)
        code, lines, _ = run_tool(fake, *post_args())
        self.assertEqual(code, t.EXIT_UNEXPECTED)


class LoginTests(unittest.TestCase):
    def test_a_mistyped_password_is_a_counted_retry_and_a_short_one_too(self):
        for mode in ("typo", "short"):
            fake = fresh()
            fake.login_mode = mode
            code, lines, _ = run_tool(fake, *pre_args())
            self.assertEqual(code, t.EXIT_RETRY)
            self.assertEqual((label_of(lines, "retry")[0]["code"], label_of(lines, "retry")[0]["counts_as_typo"]), ("LOGIN_REFUSED", True))
            self.assertEqual(fake.creates(), [])

    def test_rate_limiting_is_a_retry_that_is_not_counted(self):
        fake = fresh()
        fake.login_mode = "busy"
        code, lines, _ = run_tool(fake, *pre_args())
        self.assertEqual((code, label_of(lines, "retry")[0]["counts_as_typo"]), (t.EXIT_RETRY, False))

    def test_a_refused_connection_is_a_counted_retry_and_sends_nothing(self):
        fake = fresh()
        fake.refuse_connect = True
        code, lines, _ = run_tool(fake, *pre_args())
        self.assertEqual((code, label_of(lines, "retry")[0]["code"]), (t.EXIT_RETRY, "NO_CONNECT"))

    def test_an_unexpected_login_answer_is_a_finding_and_its_body_is_never_printed(self):
        fake = fresh()
        fake.login_mode = "weird"
        code, lines, text = run_tool(fake, *pre_args())
        self.assertEqual(code, t.EXIT_FINDING)
        self.assertNotIn("LEAK", text)
        self.assertIn(hashlib.sha256(b"LEAK " + COOKIE_SENTINEL.encode() + b" " + CSRF_SENTINEL.encode()).hexdigest(), text)

    def test_the_prompt_names_the_web_account_and_says_it_is_not_a_database_role(self):
        fake, asked = fresh(), []
        run_tool(fake, *B_ARGS, prompts=asked)
        self.assertEqual(len(asked), 1)
        self.assertIn("web account bob", asked[0])
        self.assertIn("not a database role", asked[0])
        self.assertNotIn("finweb_real", asked[0])

    def test_the_session_token_replaces_the_bootstrap_token_and_the_bootstrap_cookie_is_dropped_after_login(self):
        fake = fresh()
        self.assertEqual(run_tool(fake, *B_ARGS)[0], 0)             # the fake refuses a mutation after login unless it carries the SESSION token
        login_at = next(i for i, (p, _) in enumerate(fake.cookie_log) if p == "/api/v1/auth/login")
        self.assertIn("finweb_real_csrf=", fake.cookie_log[login_at][1])
        for path, cookie in fake.cookie_log[login_at + 1:]:
            self.assertNotIn("finweb_real_csrf", cookie, path)
            self.assertIn("finweb_real_session=", cookie)

    def test_the_password_reaches_only_the_login_body(self):
        fake = fresh()
        run_tool(fake, *pre_args())
        carrying = [entry for entry in fake.log if entry[2] and "password" in json.dumps(entry[2])]
        self.assertEqual([p for _, p, _ in carrying], ["/api/v1/auth/login"])


class SecretTests(unittest.TestCase):
    def test_no_secret_reaches_the_output_in_any_phase_or_failure(self):
        scenarios = []
        for args in (B_ARGS, pre_args(), pre_args(Y_OP, "--replay-name", "x")):
            scenarios.append((fresh(), args))
        f = fresh()
        f.hooks.append(lambda m, p, b, fk: (500, b"X " + COOKIE_SENTINEL.encode() + CSRF_SENTINEL.encode()) if m == "POST" and p == "/api/real/v1/roots" else None)
        scenarios.append((f, pre_args()))
        f = fresh()
        f.login_mode = "typo"
        scenarios.append((f, pre_args()))
        f = fresh()
        f.hooks.append(lambda m, p, b, fk: (409, b"RAW " + HEADER_SENTINEL.encode()) if m == "GET" and "/operations/" in p else None)
        scenarios.append((f, pre_args()))
        for fake, args in scenarios:
            _, _, text = run_tool(fake, *args)
            for secret in SENTINELS + ("Set-Cookie", "finweb_real_session"):
                self.assertNotIn(secret, text)
            for cookie in fake.sessions:
                self.assertNotIn(cookie, text)

    def test_the_session_cookie_and_token_are_sent_back_and_nothing_else_is_stored(self):
        fake = fresh()
        run_tool(fake, *B_ARGS)
        self.assertEqual(len(fake.sessions), 1)

    def test_every_output_line_uses_only_safe_fields(self):
        fake = fresh()
        _, lines, _ = run_tool(fake, *pre_args())
        for line in lines:
            self.assertTrue(set(line) - {"label"} <= t.SAFE_FIELDS, line)
        with self.assertRaises(ValueError):
            t.emit("x", cookie="no")
        with self.assertRaises(ValueError):
            t.emit("x", note=["a list"])


class UsageAndLogoutTests(unittest.TestCase):
    def test_an_unusable_command_line_sends_nothing_and_exits_7(self):
        bad = (["--phase", "pre"], pre_args()[:-2], [a for a in pre_args() if a not in ("--acknowledged", "yes")], ["--phase", "b", "--user-b", "bob", "--root", "nope", "--root-operation", FIRST_OP],
               ["--phase", "x"], pre_args(Y_OP, "--replay-name", "x" * 200), post_args()[:-2], ["--phase", "b", "--user-b", "bad name!", "--root", FIRST_ROOT, "--root-operation", FIRST_OP])
        for argv in bad:
            fake = fresh()
            code, lines, _ = run_tool(fake, *argv)
            self.assertEqual(code, t.EXIT_USAGE, argv)
            self.assertEqual(fake.log, [])

    def test_logout_is_in_a_finally_and_ends_the_session_after_a_stop(self):
        fake = fresh()
        fake.hooks.append(lambda m, p, b, f: (500, b"x") if m == "POST" and p == "/api/real/v1/roots" else None)
        code, _, _ = run_tool(fake, *pre_args())
        self.assertEqual((code, fake.logouts), (t.EXIT_UNKNOWN, 1))

    def test_an_uncaught_error_exits_1_and_still_logs_out(self):
        fake = fresh()

        def boom(method, path, body, f):
            if method == "GET" and path == "/api/real/v1/roots":
                raise RuntimeError("boom")
            return None
        fake.hooks.append(boom)
        code, lines, text = run_tool(fake, *pre_args())
        self.assertEqual((code, label_of(lines, "uncaught")[0]["code"]), (1, "RuntimeError"))
        self.assertNotIn("boom", text)
        self.assertEqual(fake.logouts, 1)

    def test_a_lost_connection_on_a_create_is_unknown_and_on_a_read_a_finding(self):
        fake = fresh()

        def lost_create(method, path, body, f):
            if method == "POST" and path == "/api/real/v1/roots":
                raise t.Lost()
            return None
        fake.hooks.append(lost_create)
        self.assertEqual(run_tool(fake, *pre_args())[0], t.EXIT_UNKNOWN)
        fake = fresh()

        def lost_read(method, path, body, f):
            if method == "GET" and "/operations/" in path:
                raise t.Lost()
            return None
        fake.hooks.append(lost_read)
        self.assertEqual(run_tool(fake, *pre_args())[0], t.EXIT_FINDING)


class TransportTests(unittest.TestCase):
    def test_default_send_opens_only_the_loopback_launcher_and_reads_set_cookie_by_hand(self):
        import http.client
        from unittest import mock

        class Msg:
            def get_all(self, name):
                return ["finweb_real_session=abc; Path=/api"] if name == "Set-Cookie" else None

        class Resp:
            status, msg = 200, Msg()

            def read(self, n):
                return b"{}"
        made = []

        class Conn:
            def __init__(self, host, port, timeout):
                made.append((host, port))

            def connect(self):
                pass

            def request(self, *a, **k):
                pass

            def getresponse(self):
                return Resp()

            def close(self):
                pass
        with mock.patch.object(http.client, "HTTPConnection", Conn):
            self.assertEqual(t.default_send("GET", "/x", {}, None), (200, ["finweb_real_session=abc; Path=/api"], b"{}"))
        self.assertEqual(made, [("127.0.0.1", 8004)])

    def test_a_refused_connect_is_noconnect_and_a_failure_after_the_send_is_lost(self):
        import http.client
        from unittest import mock

        class Refuse:
            def __init__(self, *a, **k):
                pass

            def connect(self):
                raise ConnectionRefusedError()

            def close(self):
                pass

        class Reset(Refuse):
            def connect(self):
                pass

            def request(self, *a, **k):
                raise ConnectionResetError()
        with mock.patch.object(http.client, "HTTPConnection", Refuse):
            with self.assertRaises(t.NoConnect):
                t.default_send("GET", "/x", {}, None)
        with mock.patch.object(http.client, "HTTPConnection", Reset):
            with self.assertRaises(t.Lost):
                t.default_send("GET", "/x", {}, None)


if __name__ == "__main__":
    unittest.main()
