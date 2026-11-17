"""F1 R8 supplementary run: the loopback tool against the REAL real-mode app (TR8S2 L-2), in process.

The unmodified `r8_http_check.main` runs all three phases through an ASGI adapter for its `send` seam. The app is `real_mode_kit.build_app`: the real authentication routes
(session, login with the bootstrap and session CSRF tokens, logout), the real `LocalBoundary` and the real contract routes, over a fake account store and a small stateful fake
service. No socket, no PostgreSQL, no network. The gateway's own idempotency SQL is NOT exercised here (the fake service stands in for it; TR8S checked the SQL).
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
import uuid

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import real_mode_kit as kit  # noqa: E402
from persistence import real_tails  # noqa: E402
from real_service.service import Created  # noqa: E402
from real_tools import r8_http_check as t  # noqa: E402
from web_api import real_scoped_contract as contract  # noqa: E402

FIRST_OP = "a454d861-dc6f-438b-ac77-d48162835ebc"


class Svc(kit.FakeService):
    def __init__(self):
        super().__init__()
        self.ops, self.entries = {}, {}

    def add(self, owner, root, op, archive):
        self.roots.setdefault(owner, []).append((root, kit.CONTEXT, 3))
        self.archives[(root, op)] = archive
        self.entries.setdefault(owner, []).append(contract.list_entry(root_id=root, operation_id=op, context_id=kit.CONTEXT, generation=3, created_at="2026-11-16T00:00:00+00:00",
                                                                       origin=kit.TEST_ORIGIN))

    def list_roots(self, conn, *, owner):
        return real_tails.Done(list(self.entries.get(owner, [])))

    def create(self, conn, *, owner, body, generation, link):
        op = uuid.UUID(body["operation_id"])
        root = uuid.uuid5(owner, "root:" + str(op))
        if op in self.ops:
            if self.ops[op] != body:
                return real_tails.Refused("RW_IDEMPOTENCY_CONFLICT")
            return Created(root, op, self.archives[(root, op)], True)
        self.ops[op] = body
        archive = kit.archive_for(root, op)
        self.add(owner, root, op, archive)
        return Created(root, op, archive, False)


class KitHandshakeTests(unittest.TestCase):
    def setUp(self):
        self.svc = Svc()
        self.app, _, self.accounts = kit.build_app(service=self.svc)
        users = {}
        for name in ("alice_user", "bob_user"):
            users[name] = kit.Client(self.app, peer="127.0.0.9").sign_up(name)
        self.signup_sessions = len(self.accounts.sessions)
        self.first_root = uuid.uuid5(users["alice_user"], "root:first")
        self.svc.add(users["alice_user"], self.first_root, uuid.UUID(FIRST_OP), kit.archive_for(self.first_root, uuid.UUID(FIRST_OP)))
        other = uuid.uuid4()
        self.svc.add(users["alice_user"], other, uuid.uuid4(), kit.archive_for(other, uuid.uuid4()))
        self.passwords = {n: "invented-disposable-pass-" + n for n in users}
        self.seen = []

    def send(self, method, path, headers, body):
        async def call():
            out, delivered = [], False

            async def receive():
                nonlocal delivered
                if delivered:
                    return {"type": "http.disconnect"}
                delivered = True
                return {"type": "http.request", "body": body or b"", "more_body": False}

            async def respond(message):
                out.append(message)
            header_list = [(b"host", b"127.0.0.1:8004")] + [(k.lower().encode(), v.encode()) for k, v in headers.items()]
            await self.app(dict(type="http", asgi={"version": "3.0"}, http_version="1.1", method=method, scheme="http", path=path, raw_path=path.encode(), query_string=b"",
                                root_path="", headers=header_list, client=("127.0.0.1", 5000), server=("127.0.0.1", 8004)), receive, respond)
            start = next(m for m in out if m["type"] == "http.response.start")
            raw = b"".join(m.get("body", b"") for m in out if m["type"] == "http.response.body")
            return start["status"], [v.decode() for k, v in start["headers"] if k.decode().lower() == "set-cookie"], raw
        reply = asyncio.run(call())
        self.seen.append((path, reply[0], reply[1]))
        return reply

    def run_tool(self, argv, who):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = t.main(argv, send=self.send, prompt=lambda label: self.passwords[who])
        text = out.getvalue()
        return code, [json.loads(line[3:]) for line in text.splitlines() if line.startswith("S8 ")], text

    def test_all_three_phases_pass_against_the_real_routes(self):
        common = ["--root", str(self.first_root), "--root-operation", FIRST_OP]
        code, lines, _ = self.run_tool(["--phase", "b", "--user-b", "bob_user"] + common, "bob_user")
        self.assertEqual(code, 0, lines[-2:])
        self.assertEqual([(line["status"], line["code"]) for line in lines if line["label"].startswith("b_") and line.get("code")], [(404, "RW_NOT_FOUND")] * 4)
        y = str(uuid.uuid4())
        tail = ["--operation-id", y, "--context", kit.CONTEXT, "--release", kit.RELEASE, "--listing", kit.LISTING, "--acknowledged", "yes"]
        code, lines, _ = self.run_tool(["--phase", "pre", "--user-a", "alice_user"] + common + tail, "alice_user")
        self.assertEqual(code, 0, lines[-2:])
        by = {line["label"]: line for line in lines}
        self.assertEqual((by["create_y"]["status"], by["replay_y"]["status"], by["conflict_y"]["status"], by["error_invalid"]["status"], by["error_unserved_context"]["status"]),
                         (201, 200, 409, 422, 404))
        self.assertEqual(by["list_after_errors"]["count"], 3)
        digest = {k: by[k] for k in ("read_first", "read_y")}
        post = ["--phase", "post", "--user-a", "alice_user"] + common + tail + ["--first-response-sha", digest["read_first"]["response_sha256"], "--first-issued-sha",
                digest["read_first"]["issued_sha256"], "--y-response-sha", digest["read_y"]["response_sha256"], "--y-issued-sha", digest["read_y"]["issued_sha256"]]
        code, lines, _ = self.run_tool(post, "alice_user")
        self.assertEqual(code, 0, lines[-2:])
        self.assertEqual([line["reproduce_status"] for line in lines if line["label"] == "reproduce_first"], ["REPRODUCED"])

    def test_the_login_sets_the_session_cookie_deletes_the_bootstrap_cookie_and_every_session_is_logged_out(self):
        code, _, text = self.run_tool(["--phase", "b", "--user-b", "bob_user", "--root", str(self.first_root), "--root-operation", FIRST_OP], "bob_user")
        self.assertEqual(code, 0)
        names = [c.split("=")[0] + ("(deleted)" if "max-age=0" in c.lower() else "") for p, s, cookies in self.seen if p.endswith("/login") for c in cookies]
        self.assertEqual(sorted(names), ["finweb_real_csrf(deleted)", "finweb_real_session"])
        self.assertEqual(len(self.accounts.sessions), self.signup_sessions)          # the tool's session was logged out
        self.assertNotIn(self.passwords["bob_user"], text)


if __name__ == "__main__":
    unittest.main()
