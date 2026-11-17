"""Author actual PG/API cases; CONFIG only from a root-provisioned runner (see below).

No native startup, provider request or browser. Old fixtures/tests stay unchanged.

CONFIG must be injected by a reviewed runner (as for `test_postgres_guarded_http`) and supply: `app` (the ASGI app from
`web_api.guarded_dev`-style construction, allowing origin http://127.0.0.1:5174), `schema` (product schema with F2, the F3
HTTP add-on and `persistence.guarded_csv_report_store.install_guarded_csv_report` already installed), `connect(role)` and
`owner_role` (the schema-owner role, read-only use). Without CONFIG every test skips.
"""
import asyncio
import base64
from copy import deepcopy
from http.cookies import SimpleCookie
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import uuid

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import psycopg  # noqa: E402
from persistence.guarded_csv_report_store import GuardedCsvReportStore  # noqa: E402
from persistence.guarded_workspace_store import GuardedWorkspaceStore  # noqa: E402
CONFIG = None
ORIGIN = "http://127.0.0.1:5174"

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
                    # Keep the real request connection open until the response
                    # completes; StreamingResponse cancels this listener itself.
                    await asyncio.Event().wait()
                delivered = True
                return {"type": "http.request", "body": raw, "more_body": False}
            async def send(value):
                sent.append(value)
            values = {"host": "127.0.0.1:8003", "origin": ORIGIN,
                "cookie": "; ".join(k + "=" + v for k, v in self.cookies.items())}
            if body is not None:
                values.update({"content-type": "application/json", "x-finweb-csrf": self.csrf or ""})
            values.update(headers or {})
            await asyncio.wait_for(self.app(dict(type="http", asgi={"version": "3.0"}, http_version="1.1", method=method,
                scheme="http", path=url.path, raw_path=url.path.encode(), query_string=url.query.encode(), root_path="",
                headers=[(k.encode(), v.encode()) for k, v in values.items()], client=(self.peer, 12345), server=("127.0.0.1", 8003)), receive, send), timeout=30)
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


class PostgresCsvReports(unittest.TestCase):
    serial = 0

    def setUp(self):
        if CONFIG is None:
            self.skipTest("root-provisioned F3 CONFIG with the CSV report SQL installed required")
        type(self).serial += 1
        self.prefix = uuid.uuid4().hex[:12]
        self.client = HttpClient(CONFIG["app"], "127.0.5." + str(type(self).serial))
        self.client.call("GET", "/api/v1/auth/session")
        status, session, _ = self.client.call("POST", "/api/v1/auth/register", dict(username="zr" + self.prefix, password="Fictional candidate only passphrase"))
        self.assertEqual(status, 201, session)
        self.owner = session["user"]["user_id"]
        status, value, _ = self.client.call("POST", "/api/v1/portfolios", dict(mode="LOCAL_SYNTHETIC_ACCOUNT", name="Invented report test", reporting_currency="USD",
            positions=[dict(symbol="SYN-A", quantity="2")], cash="20", synthetic_acknowledged=True,
            operation_id=str(uuid.uuid4()), opening_date="2026-01-01"))
        self.assertEqual(status, 200, value)
        self.root, self.revision = value["portfolio_id"], value["revision_id"]
        self.path = "/api/v1/portfolios/" + self.root

    def proposal(self, amount="5", kind="DEPOSIT", key="shared-row"):
        raw = ("reference,day,type,cash\n" + key + ",2026-01-02," + kind + "," + amount + "\n").encode()
        return dict(operation_id=str(uuid.uuid4()), expected_revision_id=self.revision, as_of="2026-01-02", file_base64=base64.b64encode(raw).decode(),
            filename="candidate-fictional.csv", kind="TRANSACTIONS", source_namespace="zr:" + self.prefix, source_account_key=None, snapshot_key=None,
            new_account_name=None, mapping=dict(source_row_key=0, event_date=1, event_type=2, amount=3), constants=dict(currency="USD", account_id=str(uuid.uuid5(uuid.UUID(self.root), "guest-account"))),
            corrections=[], classifications=[], format=dict(delimiter=",", date_format="ISO", decimal_separator=".", thousands_separator=None), synthetic_acknowledged=True)

    def preview(self, proposal):
        status, value, _ = self.client.call("POST", self.path + "/imports/preview", proposal)
        self.assertEqual(status, 200, value)
        return value

    def financial(self, proposal):
        preview = self.preview(proposal)
        self.assertIsNotNone(preview["financial_preview"])
        status, value, _ = self.client.call("POST", self.path + "/imports/commit", dict(proposal=proposal, preview_receipt=preview["preview_receipt"]))
        self.assertEqual((status, value.get("disposition")), (200, "COMMITTED"), value)
        self.revision = value["revision_id"]
        return value

    def save(self, proposal):
        preview = self.preview(proposal)
        self.assertIsNone(preview["financial_preview"])
        body = dict(proposal=proposal, preview_receipt=preview["preview_receipt"])
        status, value, _ = self.client.call("POST", self.path + "/import-report-operations", body)
        self.assertEqual((status, value.get("disposition")), (200, "REPORT_COMMITTED"), value)
        return body, value

    def economic(self):
        result = {}
        with CONFIG["connect"](CONFIG["owner_role"]) as conn:
            for table in ("portfolio", "account", "ledger_event", "benchmark_selection", "web_saved_sandbox", "web_portfolio_revision", "web_csv_source_key"):
                if table == "portfolio":
                    where = "t.portfolio_id=%s"
                elif table == "ledger_event":
                    where = "t.account_id IN (SELECT account_id FROM account WHERE portfolio_id=%s)"
                else:
                    where = "t.portfolio_id=%s"
                result[table] = conn.execute('SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\'::jsonb) FROM "' + CONFIG["schema"] + '"."' + table + '" t WHERE ' + where, (uuid.UUID(self.root),)).fetchone()[0]
        return result

    def test_a01_duplicate_commit_exact_replay_and_merged_reads(self):
        self.financial(self.proposal())
        before = self.economic()
        proposal = self.proposal()
        body, saved = self.save(proposal)
        report = json.loads(saved["response_json"])["report"]
        self.assertEqual((report["status"], report["counts"]["already_imported"], report["counts"]["imported"], report["revision_id"]), ("ALREADY_IMPORTED", 1, 0, None))
        self.assertEqual(self.economic(), before)
        with patch.object(GuardedWorkspaceStore, "csv_preview", side_effect=AssertionError("committed replay re-previewed")):
            status, replay, _ = self.client.call("POST", self.path + "/import-report-operations", body)
        self.assertEqual((status, replay), (200, saved))
        bad = deepcopy(body); bad["preview_receipt"] = "0" * 64
        self.assertEqual(self.client.call("POST", self.path + "/import-report-operations", bad)[0], 409)
        status, page, _ = self.client.call("GET", self.path + "/imports")
        self.assertEqual(status, 200, page)
        self.assertEqual({row["operation_kind"] for row in page["reports"]}, {"FINANCIAL_CSV", "CSV_REPORT_ONLY"})
        status, read, _ = self.client.call("GET", self.path + "/imports/" + saved["report_id"])
        self.assertEqual(status, 200, read); self.assertIn("guarded_report", read); self.assertNotIn("guarded", read)
        status, _, headers = self.client.call("GET", self.path + "/imports/" + saved["report_id"] + "/export?format=csv")
        self.assertEqual(status, 200); self.assertEqual(headers["x-finweb-report-id"], saved["report_id"])

    def test_a02_quarantine_and_exclusion_save_no_economic_effects(self):
        before = self.economic()
        bad = self.proposal(amount="unresolved")
        _, saved = self.save(bad)
        report = json.loads(saved["response_json"])["report"]
        self.assertEqual((report["status"], report["counts"]["quarantined"]), ("REPORT_ONLY", 1))
        excluded = self.proposal(key="explicit-non-data")
        excluded["classifications"] = [dict(row_number=1, classification="NON_DATA", reason="Invented non-economic example")]
        _, saved = self.save(excluded)
        self.assertEqual(json.loads(saved["response_json"])["report"]["counts"]["excluded"], 1)
        self.assertEqual(self.economic(), before)

    def test_a03_batch_refusal_historical_report_survives_later_import(self):
        # Use an actual importer refusal (33 READY exceeds its32-event cap).
        # Negative cash is a financial INSUFFICIENT_DATA result, not necessarily
        # a refused import, and must not be reclassified to satisfy this test.
        proposal = self.proposal(amount="1", key="batch-0")
        raw = "reference,day,type,cash\n" + "".join("batch-" + str(i) + ",2026-01-02,DEPOSIT,1\n" for i in range(33))
        proposal["file_base64"] = base64.b64encode(raw.encode()).decode()
        preview = self.preview(proposal)
        self.assertIsNone(preview["financial_preview"])
        self.assertEqual(preview["report"]["counts"]["ready"], 33)
        self.assertIn("EVENT_LIMIT", [issue["code"] for issue in preview["report"]["batch_errors"]])
        _, saved = self.save(proposal)
        original = saved["response_json"]
        # A separate, explicitly constructed one-row operation later imports
        # one of those source identities; this is not automatic chunking.
        later = self.proposal(amount="1", key="batch-0")
        self.financial(later)
        status, archive, _ = self.client.call("GET", saved["archive_url"])
        self.assertEqual(status, 200, archive)
        self.assertEqual(archive["response_json"], original)
        status, report, _ = self.client.call("GET", self.path + "/imports/" + saved["report_id"])
        self.assertEqual(status, 200, report)
        self.assertEqual(report["report"], json.loads(original)["report"])
        status, report, _ = self.client.call("GET", self.path + "/imports/" + saved["report_id"] + "/export?format=json")
        self.assertEqual(status, 200, report)
        self.assertEqual(report, json.loads(original)["report"])

    def test_a04_source_conflict_and_financial_namespace_collision(self):
        self.financial(self.proposal())
        before = self.economic()
        conflicting = self.proposal(amount="6")
        preview = self.preview(conflicting)
        status, refused, _ = self.client.call("POST", self.path + "/import-report-operations", dict(proposal=conflicting, preview_receipt=preview["preview_receipt"]))
        self.assertEqual(status, 409, refused)
        _, saved = self.save(self.proposal())
        command = dict(operation_id=saved["operation_id"], expected_revision_id=self.revision, as_of="2026-01-02", operation="APPEND",
            events=[dict(event_type="DEPOSIT", account_id=str(uuid.uuid5(uuid.UUID(self.root), "guest-account")), event_date="2026-01-02", currency="USD", amount="1")], target_event_ids=[], account_name=None)
        self.assertEqual(self.client.call("POST", self.path + "/ledger-commands", command)[0], 409)
        self.assertEqual(self.economic(), before)

    def test_a05_real_ack_loss_and_precommit_failure(self):
        self.financial(self.proposal())
        for seam, durable in (("_before_commit", False), ("_after_commit_ack", True)):
            proposal = self.proposal()
            preview = self.preview(proposal)
            before = self.economic()
            with patch.object(GuardedCsvReportStore, seam, side_effect=psycopg.OperationalError("labelled candidate test fault")):
                status, value, _ = self.client.call("POST", self.path + "/import-report-operations", dict(proposal=proposal, preview_receipt=preview["preview_receipt"]))
            self.assertEqual((status, value["disposition"]), (202, "UNKNOWN"), value)
            status, recovered, _ = self.client.call("GET", value["reconcile_url"])
            self.assertEqual((status, recovered["disposition"]), (200, "REPORT_COMMITTED") if durable else (202, "UNKNOWN"))
            with CONFIG["connect"](CONFIG["owner_role"]) as conn:
                row = conn.execute('SELECT count(*) FROM "' + CONFIG["schema"] + '".gh_csv_report_operation WHERE owner_id=%s AND operation_id=%s', (uuid.UUID(self.owner), uuid.UUID(proposal["operation_id"]))).fetchone()
            self.assertEqual(row, (int(durable),)); self.assertEqual(self.economic(), before)

    def test_a06_foreign_identity_and_stale_baseline_refuse(self):
        self.financial(self.proposal())
        stale = self.proposal(); preview = self.preview(stale)
        self.financial(self.proposal(key="next"))
        status, value, _ = self.client.call("POST", self.path + "/import-report-operations", dict(proposal=stale, preview_receipt=preview["preview_receipt"]))
        self.assertEqual(status, 409, value)
        _, saved = self.save(self.proposal())
        foreign_path = "/api/v1/portfolios/" + str(uuid.uuid4()) + "/import-report-operations/" + saved["operation_id"]
        status, value, _ = self.client.call("GET", foreign_path)
        self.assertEqual(status, 404, value); self.assertNotIn("response_json", value)
