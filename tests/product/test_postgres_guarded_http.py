"""Actual F3 cookie/CSRF ASGI requests over a root-supplied fresh fictional PG.

No ambient .env/DSN or process start. A reviewed runner injects CONFIG; root owns
provision/issuer/lifecycle. Independent cases do not import these fixtures.
"""
import asyncio
import base64
import hashlib
from http.cookies import SimpleCookie
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import uuid

import psycopg
from persistence.guarded_http_store import RIGHTS, ArchivedWorkspaceProjection
from persistence.guarded_workspace_store import GuardedWorkspaceStore

CONFIG = None
CASE_EVENTS = []
ORIGIN = "http://127.0.0.1:5174"


def cleanup():
    pass  # Every direct test handle has its own context; root owns native processes.


class HttpClient:
    def __init__(self, app, peer):
        self.app, self.peer, self.cookies, self.csrf = app, peer, {}, None

    def call(self, method, target, body=None, *, headers=None):
        async def request():
            url = urlsplit(target)
            raw = b"" if body is None else json.dumps(body).encode()
            sent, delivered = [], False
            async def receive():
                nonlocal delivered
                if delivered:
                    return {"type": "http.disconnect"}
                delivered = True
                return {"type": "http.request", "body": raw, "more_body": False}
            async def send(value):
                sent.append(value)
            values = {"host": "127.0.0.1:8003", "origin": ORIGIN,
                "cookie": "; ".join(k + "=" + v for k, v in self.cookies.items())}
            if body is not None:
                values.update({"content-type": "application/json", "x-finweb-csrf": self.csrf or ""})
            values.update(headers or {})
            await self.app(dict(type="http", asgi={"version": "3.0"}, http_version="1.1", method=method,
                scheme="http", path=url.path, raw_path=url.path.encode(), query_string=url.query.encode(), root_path="",
                headers=[(k.encode(), v.encode()) for k, v in values.items()], client=(self.peer, 12345), server=("127.0.0.1", 8003)), receive, send)
            start = next(v for v in sent if v["type"] == "http.response.start")
            content = b"".join(v.get("body", b"") for v in sent if v["type"] == "http.response.body")
            for key, value in start["headers"]:
                if key == b"set-cookie":
                    jar = SimpleCookie(); jar.load(value.decode())
                    for name, item in jar.items():
                        if item["max-age"] == "0":
                            self.cookies.pop(name, None)
                        else:
                            self.cookies[name] = item.value
            try:
                value = json.loads(content)
            except ValueError:
                value = content.decode()
            if type(value) is dict and "csrf_token" in value:
                self.csrf = value["csrf_token"]
            return start["status"], value, dict((k.decode(), v.decode()) for k, v in start["headers"])
        return asyncio.run(request())


class PostgresGuardedHttpTests(unittest.TestCase):
    serial = 0

    def setUp(self):
        if CONFIG is None:
            self.skipTest("explicit root-provisioned F3 CONFIG required")
        type(self).serial += 1
        self.profile = CONFIG["profile"]
        self.prefix = uuid.uuid4().hex[:12]
        self.client = HttpClient(CONFIG["app"], "127.0.2." + str(type(self).serial))
        self.client.call("GET", "/api/v1/auth/session")
        status, session, _ = self.client.call("POST", "/api/v1/auth/register", dict(username="f3" + self.prefix, password="Fictional local F3 passphrase only"))
        self.assertEqual(status, 201)
        self.owner = session["user"]["user_id"]
        self.op = str(uuid.uuid4())
        self.body = dict(mode="LOCAL_SYNTHETIC_ACCOUNT", name="F3 actual invented HTTP", reporting_currency="USD",
            positions=[dict(symbol="SYN-A", quantity="2")], cash="20", synthetic_acknowledged=True,
            operation_id=self.op, opening_date="2026-01-01")
        self.rights(RIGHTS)

    def rights(self, values, expiry="NONE"):
        schema = CONFIG["schema"]
        with CONFIG["connect"](CONFIG["executor_role"]) as conn:
            generation = conn.execute('SELECT generation FROM "' + schema + '".gh_head(%s)', (self.profile.context_id,)).fetchone()
        # Issuer receives only the existing authority-changing function capability.
        if generation is None:
            raise AssertionError("published current head missing")
        with CONFIG["connect"](CONFIG["issuer_role"]) as conn:
            conn.execute('SELECT "' + schema + '".gw_set_rights(%s,%s,%s::jsonb,%s)', (self.profile.context_id, generation[0] + 1, json.dumps(values), expiry))

    def create(self):
        status, value, _ = self.client.call("POST", "/api/v1/portfolios", self.body)
        self.assertEqual((status, value.get("disposition")), (200, "COMMITTED"), value)
        self.root, self.revision = value["portfolio_id"], value["revision_id"]
        self.assertEqual(hashlib.sha256(value["response_json"].encode()).hexdigest(), value["response_sha256"])
        return value

    def command(self, amount="3"):
        return dict(operation_id=str(uuid.uuid4()), expected_revision_id=self.revision, as_of="2026-01-02", operation="APPEND",
            events=[dict(event_type="DEPOSIT", account_id=str(uuid.uuid5(uuid.UUID(self.root), "guest-account")), event_date="2026-01-02", currency="USD", amount=amount)],
            target_event_ids=[], account_name=None)

    def proposal(self):
        raw = b"key,date,type,currency,amount\nhttp-row,2026-01-02,DEPOSIT,USD,7\n"
        return dict(operation_id=str(uuid.uuid4()), expected_revision_id=self.revision, as_of="2026-01-02",
            file_base64=base64.b64encode(raw).decode(), filename="invented-http.csv", kind="TRANSACTIONS",
            source_namespace="f3:" + self.prefix, source_account_key=None, snapshot_key=None, new_account_name=None,
            mapping=dict(source_row_key=0, event_date=1, event_type=2, currency=3, amount=4),
            constants=dict(account_id=str(uuid.uuid5(uuid.UUID(self.root), "guest-account"))), corrections=[], classifications=[],
            format=dict(delimiter=",", date_format="ISO", decimal_separator=".", thousands_separator=None), synthetic_acknowledged=True)

    def test_h01_create_exact_raw_archive_and_initial_native_workspace(self):
        saved = self.create()
        status, archive, _ = self.client.call("GET", saved["archive_url"])
        self.assertEqual(status, 200)
        for kind in ("issued", "response", "envelope"):
            self.assertEqual(hashlib.sha256(archive[kind + "_json"].encode()).hexdigest(), archive[kind + "_sha256"])
        status, workspace, _ = self.client.call("GET", "/api/v1/portfolios/" + self.root + "/workspace")
        self.assertEqual(status, 200, workspace)
        self.assertEqual(workspace["guarded"]["operation_id"], self.op)
        self.assertTrue(workspace["policies"]["targets"])
        self.assertEqual(workspace["ledger"]["events"][0]["event_date"], "2026-01-01")

    def test_h02_real_ledger_csv_preview_commit_and_replay(self):
        self.create()
        path = "/api/v1/portfolios/" + self.root
        command = self.command()
        status, preview, _ = self.client.call("POST", path + "/ledger-commands/preview", command)
        self.assertEqual(status, 200, preview)
        self.assertTrue(preview["preview"])
        status, value, _ = self.client.call("POST", path + "/ledger-commands", command)
        self.assertEqual((status, value.get("disposition")), (200, "COMMITTED"), value)
        self.revision = value["revision_id"]
        proposal = self.proposal()
        status, preview, _ = self.client.call("POST", path + "/imports/preview", proposal)
        self.assertEqual(status, 200, preview)
        payload = dict(proposal=proposal, preview_receipt=preview["preview_receipt"])
        first = self.client.call("POST", path + "/imports/commit", payload)
        second = self.client.call("POST", path + "/imports/commit", payload)
        self.assertEqual(first[:2], second[:2])
        self.assertEqual(first[0], 200, first[1])

    def test_h03_all_read_export_paths_are_pure_with_csv_origin_checks(self):
        saved = self.create()
        path = "/api/v1/portfolios/" + self.root
        proposal = self.proposal()
        status, preview, _ = self.client.call("POST", path + "/imports/preview", proposal)
        self.assertEqual(status, 200, preview)
        status, committed, _ = self.client.call("POST", path + "/imports/commit", dict(proposal=proposal, preview_receipt=preview["preview_receipt"]))
        self.assertEqual(status, 200, committed)
        report = json.loads(committed["response_json"])["report"]["report_id"]
        revision = committed["revision_id"]
        paths = ["/api/v1/portfolios", path, path + "/workspace", path + "?revision_id=" + self.root,
            path + "/imports", path + "/imports/" + report, path + "/imports/" + report + "/export?format=json",
            path + "/exports/holdings?revision_id=" + revision, path + "/exports/transactions?revision_id=" + revision + "&format=csv",
            saved["archive_url"], saved["archive_url"] + "/export", saved["reconcile_url"]]
        with patch.object(self.profile.world, "create", side_effect=AssertionError("READ reissued World")), \
             patch("persistence.web_workspace_store.verify_source", side_effect=AssertionError("READ reproduced source")), \
             patch("persistence.guarded_workspace_store.issue_local_service", side_effect=AssertionError("READ dispatched service")):
            for target in paths:
                status, value, _ = self.client.call("GET", target)
                self.assertEqual(status, 200, (target, value))
        real_targets = ArchivedWorkspaceProjection._targets
        def forged(projection, item):
            rows = real_targets(projection, item)
            return [{**row, "semantic_key": "0" * 64} for row in rows]
        with patch.object(ArchivedWorkspaceProjection, "_targets", forged):
            status, value, _ = self.client.call("GET", path + "/workspace")
        self.assertEqual((status, value["error"]["code"]), (503, "F3_ARCHIVE_PROJECTION_DIFFERS"))

    def test_h04_stable_create_retry_changed_content_and_rootless_reconcile(self):
        saved = self.create()
        status, retry, _ = self.client.call("POST", "/api/v1/portfolios", self.body)
        self.assertEqual((status, retry), (200, saved))
        status, conflict, _ = self.client.call("POST", "/api/v1/portfolios", {**self.body, "name": "changed"})
        self.assertEqual((status, conflict["error"]["code"]), (409, "F2_IDEMPOTENCY_CONFLICT"))
        status, confirmed, _ = self.client.call("GET", "/api/v1/creation-operations/" + self.op + "/reconcile")
        self.assertEqual((status, confirmed), (200, saved))
        status, unknown, _ = self.client.call("GET", "/api/v1/creation-operations/" + str(uuid.uuid4()) + "/reconcile")
        self.assertEqual((status, unknown["disposition"]), (202, "UNKNOWN"))
        self.assertNotIn("response_json", unknown)

    def test_h05_current_rights_and_original_generation_are_distinct(self):
        saved = self.create()
        self.rights({**RIGHTS, "EXECUTE_CREATE": False})
        status, archive, _ = self.client.call("GET", saved["archive_url"])
        self.assertEqual(status, 200, archive)
        self.assertGreater(archive["admission_generation"], archive["generation"])
        status, value, _ = self.client.call("POST", "/api/v1/portfolios", self.body)
        self.assertEqual((status, value["error"]["code"]), (403, "F2_RIGHT_REFUSED"))
        self.rights({**RIGHTS, "ARCHIVE_READ": False})
        status, value, _ = self.client.call("GET", saved["archive_url"])
        self.assertEqual((status, value["error"]["code"]), (403, "F2_RIGHT_REFUSED"))
        self.rights(RIGHTS)

    def test_h06_explicit_reproduce_calls_actual_service_and_preserves_hash(self):
        saved = self.create()
        status, result, _ = self.client.call("POST", saved["archive_url"] + "/reproduce", {})
        self.assertEqual(status, 200, result)
        self.assertEqual((result["schema"], result["status"], result["issued_sha256"]),
            ("finweb.guarded_reproduce/1", "REPRODUCED", saved["issued_sha256"]))

    def test_h07_actual_postcommit_ack_loss_is_unknown_then_reconciled(self):
        with patch.object(GuardedWorkspaceStore, "_after_commit_ack", side_effect=psycopg.OperationalError("test-only actual postcommit ACK loss")):
            status, unknown, _ = self.client.call("POST", "/api/v1/portfolios", self.body)
        self.assertEqual((status, unknown["disposition"]), (202, "UNKNOWN"))
        self.assertEqual(set(unknown), {"schema", "profile", "disposition", "synthetic", "portfolio_id", "operation_id", "reconcile_url"})
        status, value, _ = self.client.call("GET", "/api/v1/creation-operations/" + self.op + "/reconcile")
        self.assertEqual((status, value["disposition"]), (200, "COMMITTED"))
        CASE_EVENTS.append(dict(case="H07", outcome="ACTUAL_COMMIT_THEN_INJECTED_ACK_LOSS_THEN_CONFIRMED"))

    def test_h08_auth_csrf_owner_and_explicit_unsupported_routes(self):
        saved = self.create()
        status, value, _ = self.client.call("POST", saved["archive_url"] + "/reproduce", {}, headers={"x-finweb-csrf": "0" * 64})
        self.assertEqual((status, value["error"]["code"]), (403, "CSRF_REJECTED"))
        for method, target, body in (("GET", "/api/v1/real-source-contexts", None),
                ("POST", "/api/v1/portfolios/" + self.root + "/analytics/evaluate", {}),
                ("POST", "/api/v1/portfolios/" + self.root + "/packets/any/reproduce", {})):
            status, value, _ = self.client.call(method, target, body)
            self.assertEqual((status, value["error"]["code"]), (503, "F3_GUARDED_UNSUPPORTED"))
        anonymous = HttpClient(CONFIG["app"], "127.0.3.1")
        self.assertEqual(anonymous.call("GET", saved["archive_url"])[0], 401)
