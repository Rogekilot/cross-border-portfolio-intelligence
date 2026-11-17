"""Actual PostgreSQL CP7-B auth, isolation, persistence and transaction tests.

Opt-in only; creates/drops its own finweb_it_* schema. The HTTP runtime uses
FINWEB_CP7_APP_USER, a separate non-owner role with explicit CP7 grants.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
import sys
import unittest
import uuid
from http.cookies import SimpleCookie
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pg_market_kit import PgSchema, skip_reason
from persistence import connection, ledger_store, migrator
from persistence.web_account_store import APP_GRANTS, AccountStoreError, WebAccountStore
from web_api.app import create_app
from web_api.auth import AuthSettings, csrf_token, digest_token
from web_api.synthetic import SyntheticWorld

ROLE = os.environ.get("FINWEB_CP7_APP_USER", "")
SKIP = skip_reason(need_app_role=False) or ("set FINWEB_CP7_APP_USER to a separate non-owner CP7 app role" if not ROLE else "")
PASSWORD = "fictional integration test passphrase"
ORIGIN = "http://127.0.0.1:5173"
BODY = {"mode": "LOCAL_SYNTHETIC_ACCOUNT", "name": "Saved fictional holdings", "reporting_currency": "USD",
        "positions": [{"symbol": "SYN-A", "quantity": "10"}, {"symbol": "SYN-B", "quantity": "10"}],
        "cash": "500", "synthetic_acknowledged": True}


async def request(app, method, path, body=None, *, headers=None, client="127.0.0.1"):
    payload = b"" if body is None else json.dumps(body).encode()
    pairs = [(b"host", b"127.0.0.1:8000")]
    if method == "POST":
        pairs.append((b"content-type", b"application/json"))
    pairs.extend((key.lower().encode(), value.encode()) for key, value in (headers or {}).items())
    sent, delivered = [], False
    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": payload, "more_body": False}
    async def send(message):
        sent.append(message)
    await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
        "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": pairs, "client": (client, 12345), "server": ("127.0.0.1", 8000)}, receive, send)
    start = next(item for item in sent if item["type"] == "http.response.start")
    data = b"".join(item.get("body", b"") for item in sent if item["type"] == "http.response.body")
    return start["status"], json.loads(data), start["headers"]


class Client:
    def __init__(self, app, peer):
        self.app, self.peer, self.cookies, self.csrf = app, peer, {}, None

    def call(self, method, path, body=None, *, extra=None):
        headers = {"Origin": ORIGIN, "Cookie": "; ".join(key + "=" + value for key, value in self.cookies.items())}
        if self.csrf is not None:
            headers["X-Finweb-CSRF"] = self.csrf
        headers.update(extra or {})
        status, data, raw = asyncio.run(request(self.app, method, path, body, headers=headers, client=self.peer))
        for key, value in raw:
            if key == b"set-cookie":
                jar = SimpleCookie()
                jar.load(value.decode())
                for name, morsel in jar.items():
                    if morsel["max-age"] == "0":
                        self.cookies.pop(name, None)
                    else:
                        self.cookies[name] = morsel.value
        if "csrf_token" in data:
            self.csrf = data["csrf_token"]
        return status, data, raw


@unittest.skipIf(bool(SKIP), SKIP)
class PostgresWebAuthTests(unittest.TestCase):
    serial = 0

    @classmethod
    def setUpClass(cls):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", ROLE):
            raise ValueError("validated test application role required")
        cls.pg = PgSchema("finweb_it_web_").open(grant=False)
        cls.addClassCleanup(cls.pg.close)
        for statement in APP_GRANTS:
            cls.pg.owner.execute(statement.format(schema=cls.pg.schema, role=ROLE))
        cls.conninfo = connection.build_conninfo(dbname=os.environ[connection.DATABASE_VAR], user=ROLE,
            socket=os.environ.get(connection.SOCKET_VAR), host=os.environ.get(connection.HOST_VAR), port=os.environ.get(connection.PORT_VAR))

    def setUp(self):
        type(self).serial += 1
        self.ident = str(type(self).serial) + uuid.uuid4().hex[:8]
        self.now = [dt.datetime(2026, 10, 19, 12, tzinfo=dt.timezone.utc)]
        self.store = WebAccountStore(self.conninfo, self.pg.schema, clock=lambda: self.now[0])
        self.app = create_app(account_store=self.store, auth_settings=AuthSettings.local(), enable_saved_synthetic=True, enable_local_guest=True)
        self.client = Client(self.app, "127.0.0." + str(type(self).serial))
        self.client.call("GET", "/api/v1/auth/session")

    def register(self, client=None, suffix="a"):
        client = client or self.client
        client.call("GET", "/api/v1/auth/session")
        status, data, raw = client.call("POST", "/api/v1/auth/register", {"username": "user" + self.ident + suffix, "password": PASSWORD})
        self.assertEqual(status, 201, data)
        self.assertTrue(data["authenticated"])
        return data

    def create(self, client=None):
        status, data, _ = (client or self.client).call("POST", "/api/v1/portfolios", BODY)
        self.assertEqual(status, 201, data)
        return data

    def test_real_credentials_sessions_are_hashed_and_logout_invalidates(self):
        state = self.register()
        raw_token = self.client.cookies["finweb_session"]
        row = self.pg.owner.execute("SELECT password_hash FROM web_identity WHERE user_id=%s", (uuid.UUID(state["user"]["user_id"]),)).fetchone()
        self.assertNotIn(PASSWORD, row[0])
        row = self.pg.owner.execute("SELECT token_hash FROM web_session WHERE user_id=%s", (uuid.UUID(state["user"]["user_id"]),)).fetchone()
        self.assertEqual(row[0], digest_token(raw_token))
        self.assertNotEqual(row[0], raw_token)
        status, data, _ = self.client.call("POST", "/api/v1/auth/logout", {})
        self.assertEqual(status, 200)
        self.assertFalse(data["authenticated"])
        self.assertIsNone(self.store.session_user(raw_token))
        self.assertEqual(self.client.call("GET", "/api/v1/portfolios")[0], 401)

    def test_cookie_attributes_csrf_missing_wrong_and_cross_origin(self):
        state = self.register()
        status, _, raw = self.client.call("GET", "/api/v1/auth/session")
        cookie = next(value.decode() for key, value in raw if key == b"set-cookie" and value.startswith(b"finweb_session="))
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertEqual(status, 200)
        for headers in ({"X-Finweb-CSRF": ""}, {"X-Finweb-CSRF": "0" * 64}, {"Origin": "null"}, {"Origin": "https://evil.invalid"}):
            self.assertEqual(self.client.call("POST", "/api/v1/portfolios", BODY, extra=headers)[0], 403)
        self.assertEqual(self.client.call("GET", "/api/v1/portfolios")[1]["portfolios"], [])

    def test_unknown_and_wrong_password_are_same_generic_refusal_and_login_rotates(self):
        state = self.register()
        original = self.client.cookies["finweb_session"]
        self.client.call("POST", "/api/v1/auth/logout", {})
        errors = []
        for username in (state["user"]["username"], "unknown" + self.ident):
            status, data, _ = self.client.call("POST", "/api/v1/auth/login", {"username": username, "password": "wrong but long test password"})
            self.assertEqual(status, 401)
            errors.append(data)
        self.assertEqual(errors[0], errors[1])
        status, data, _ = self.client.call("POST", "/api/v1/auth/login", {"username": state["user"]["username"].upper(), "password": PASSWORD})
        self.assertEqual(status, 200, data)
        self.assertNotEqual(original, self.client.cookies["finweb_session"])

    def test_two_users_no_portfolio_packet_or_replay_idor_before_source_work(self):
        self.register()
        value = self.create()
        other = Client(self.app, self.client.peer + "2")
        self.register(other, "b")
        packet_id = value["insights"]["packets"][0]["insight_id"]
        base = "/api/v1/portfolios/" + value["portfolio_id"]
        # A deliberately poisoned source proves denied requests never invoke financial reconstruction.
        import unittest.mock
        with unittest.mock.patch("web_api.synthetic.SyntheticWorld.create", side_effect=AssertionError("foreign financial read")):
            for path in (base, base + "/packets/" + packet_id, "/api/v1/portfolios/" + str(uuid.uuid4())):
                status, data, _ = other.call("GET", path)
                self.assertEqual((status, data["error"]["code"]), (404, "NOT_FOUND"))
            status, data, _ = other.call("POST", base + "/packets/" + packet_id + "/reproduce", {"expected_result_digest": value["insights"]["result_digest"]})
            self.assertEqual((status, data["error"]["code"]), (404, "NOT_FOUND"))
        self.assertEqual(other.call("GET", "/api/v1/portfolios")[1]["portfolios"], [])
        self.assertEqual(self.client.call("GET", base)[1], value)

    def test_saved_ledger_financial_facts_and_full_proof_survive_new_store_and_app(self):
        self.register()
        value = self.create()
        self.assertEqual((value["persisted"], value["synthetic"], value["mode"]), (True, True, "LOCAL_SYNTHETIC_ACCOUNT"))
        nav = next(m for m in value["valuation"]["metrics"] if m["metric_id"] == "portfolio_value" and m["view"] == "REPORTING")
        self.assertEqual((nav["value"], nav["exact"]), ("2000", "2000/1"))
        rows = self.pg.owner.execute("SELECT e.event_type FROM ledger_event e JOIN account a USING(account_id) WHERE a.portfolio_id=%s", (uuid.UUID(value["portfolio_id"]),)).fetchall()
        self.assertEqual(sorted(r[0] for r in rows), ["OPENING_CASH", "OPENING_POSITION", "OPENING_POSITION"])
        restarted = WebAccountStore(self.conninfo, self.pg.schema, clock=lambda: self.now[0])
        self.client.app = create_app(account_store=restarted, auth_settings=AuthSettings.local(), enable_saved_synthetic=True)
        base = "/api/v1/portfolios/" + value["portfolio_id"]
        self.assertEqual(self.client.call("GET", base)[1], value)
        self.assertEqual(len(self.client.call("GET", "/api/v1/portfolios")[1]["portfolios"]), 1)
        packet_id = value["insights"]["packets"][0]["insight_id"]
        status, report, _ = self.client.call("POST", base + "/packets/" + packet_id + "/reproduce", {"expected_result_digest": value["insights"]["result_digest"]})
        self.assertEqual((status, report["status"]), (200, "REPRODUCED"))
        status, report, _ = self.client.call("POST", base + "/packets/" + packet_id + "/reproduce", {"expected_result_digest": "0" * 64})
        self.assertEqual((status, report["status"]), (200, "RESULT_DIFFERS"))

    def test_absolute_expiry_and_malformed_cookie(self):
        self.register()
        token = self.client.cookies["finweb_session"]
        self.now[0] += dt.timedelta(seconds=28800)
        self.assertIsNone(self.store.session_user(token))
        self.assertEqual(self.client.call("GET", "/api/v1/portfolios")[0], 401)
        status, state, _ = self.client.call("GET", "/api/v1/auth/session", extra={"Cookie": "finweb_session=malformed"})
        self.assertEqual(status, 200)
        self.assertFalse(state["authenticated"])

    def test_two_portfolios_use_real_gapped_ledger_sequences_and_invalid_pin_refuses(self):
        self.register()
        first = self.create()
        second = self.create()
        one, two = uuid.UUID(first["portfolio_id"]), uuid.UUID(second["portfolio_id"])
        rows = self.pg.owner.execute("SELECT portfolio_id,ledger_version FROM web_saved_sandbox WHERE portfolio_id IN (%s,%s)", (one, two)).fetchall()
        pins = dict(rows)
        seqs = self.pg.owner.execute("SELECT e.ledger_seq FROM ledger_event e JOIN account a USING(account_id) WHERE a.portfolio_id=%s ORDER BY e.ledger_seq", (two,)).fetchall()
        self.assertEqual(pins[two], seqs[-1][0])
        self.assertGreater(pins[two], 3)
        self.assertGreater(seqs[0][0], pins[one])
        restarted = WebAccountStore(self.conninfo, self.pg.schema, clock=lambda: self.now[0])
        self.client.app = create_app(account_store=restarted, auth_settings=AuthSettings.local(), enable_saved_synthetic=True)
        self.assertEqual(self.client.call("GET", "/api/v1/portfolios/" + str(one))[1], first)
        self.assertEqual(self.client.call("GET", "/api/v1/portfolios/" + str(two))[1], second)
        self.pg.owner.execute("UPDATE web_saved_sandbox SET ledger_version=%s WHERE portfolio_id=%s", (seqs[0][0], two))
        status, data, _ = self.client.call("GET", "/api/v1/portfolios/" + str(two))
        self.assertEqual((status, data["error"]["code"]), (503, "SAVED_RESULT_DIFFERS"))

    def test_durable_rate_limit_survives_store_reconstruction_and_window_expires(self):
        for _ in range(20):
            self.store.rate_limit("login", self.client.peer, "unknown" + self.ident)
        fresh = WebAccountStore(self.conninfo, self.pg.schema, clock=lambda: self.now[0])
        with self.assertRaises(AccountStoreError) as error:
            fresh.rate_limit("login", self.client.peer, "unknown" + self.ident)
        self.assertEqual(error.exception.code, "AUTH_RATE_LIMITED")
        self.now[0] += dt.timedelta(minutes=15)
        fresh.rate_limit("login", self.client.peer, "unknown" + self.ident)

    def test_failed_financial_creation_rolls_back_portfolio_account_and_ledger(self):
        state = self.register()
        import unittest.mock
        with unittest.mock.patch("web_api.synthetic.SyntheticWorld.create", side_effect=ValueError("deliberate refusal")):
            status, data, _ = self.client.call("POST", "/api/v1/portfolios", BODY)
        self.assertEqual((status, data["error"]["code"]), (503, "DETERMINISTIC_SOURCE_REFUSED"))
        uid = uuid.UUID(state["user"]["user_id"])
        self.assertEqual(self.pg.owner.execute("SELECT count(*) FROM portfolio WHERE user_id=%s", (uid,)).fetchone()[0], 0)
        self.assertEqual(self.client.call("GET", "/api/v1/portfolios")[1]["portfolios"], [])

    def test_non_owner_grants_preserve_immutable_ledger_and_snapshot(self):
        self.register()
        self.create()
        import psycopg
        with self.store.connect() as conn:
            for table in ("ledger_event", "portfolio", "account", "web_saved_sandbox", "web_identity"):
                with self.subTest(table=table), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    conn.execute("UPDATE " + table + " SET " + ("snapshot_json=snapshot_json" if table == "web_saved_sandbox" else "user_id=user_id" if table in ("portfolio", "web_identity") else "account_id=account_id"))
        unsafe = WebAccountStore(connection.conninfo_from_env(os.environ), self.pg.schema)
        with self.assertRaises(AccountStoreError) as error:
            unsafe.list_portfolios(str(uuid.uuid4()))
        self.assertEqual(error.exception.code, "UNSAFE_DATABASE_ROLE")

    def test_source_and_stored_artifact_tampering_fail_closed(self):
        state = self.register()
        value = self.create()
        pid = uuid.UUID(value["portfolio_id"])
        original = self.pg.owner.execute("SELECT snapshot_json FROM web_saved_sandbox WHERE portfolio_id=%s", (pid,)).fetchone()[0]
        self.pg.owner.execute("UPDATE web_saved_sandbox SET snapshot_json='{}' WHERE portfolio_id=%s", (pid,))
        status, data, _ = self.client.call("GET", "/api/v1/portfolios/" + str(pid))
        self.assertEqual((status, data["error"]["code"]), (503, "SAVED_SOURCE_DIFFERS"))
        self.pg.owner.execute("UPDATE web_saved_sandbox SET snapshot_json=%s WHERE portfolio_id=%s", (original, pid))
        world = SyntheticWorld()
        world.input_sha256 = "0" * 64
        with self.assertRaises(AccountStoreError) as error:
            self.store.get_portfolio(state["user"]["user_id"], str(pid), world)
        self.assertEqual(error.exception.code, "SAVED_SOURCE_DIFFERS")

    def test_duplicate_username_atomic_and_session_count_bounded(self):
        state = self.register()
        other = Client(self.app, self.client.peer + "3")
        other.call("GET", "/api/v1/auth/session")
        status, data, _ = other.call("POST", "/api/v1/auth/register", {"username": state["user"]["username"].upper(), "password": PASSWORD})
        self.assertEqual((status, data["error"]["code"]), (409, "USERNAME_UNAVAILABLE"))
        tokens = []
        for _ in range(9):
            self.now[0] += dt.timedelta(microseconds=1)
            tokens.append(self.store.start_session(state["user"], 28800))
        self.assertIsNone(self.store.session_user(tokens[0]))
        self.assertIsNotNone(self.store.session_user(tokens[-1]))
        count = self.pg.owner.execute("SELECT count(*) FROM web_session WHERE user_id=%s", (uuid.UUID(state["user"]["user_id"]),)).fetchone()[0]
        self.assertEqual(count, 8)
