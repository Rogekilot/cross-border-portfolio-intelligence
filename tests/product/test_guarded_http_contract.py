"""F3 strict transport/route contracts, no PG connection or server process."""
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid

from pydantic import ValidationError
from performance.ledger_view import ledger_digest
from persistence.guarded_http_store import (GuardedHttpStore, build_fictional_profile, PROFILE)
from web_api.app import create_app
from web_api.auth import AuthSettings
from web_api.guarded_dev import executor_dsn, load_config
from web_api.guarded_routes import GuardedCreation, error_status


BODY = dict(mode="LOCAL_SYNTHETIC_ACCOUNT", name="Invented contract input", reporting_currency="USD",
    positions=[dict(symbol="SYN-A", quantity="2")], cash="20", synthetic_acknowledged=True,
    operation_id="f3000000-0000-4000-8000-000000000001", opening_date="2026-01-01")
ORIGINS = frozenset(("http://127.0.0.1:5174", "http://127.0.0.1:8003"))


async def asgi(app, method, path, body=None):
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
    headers = [(b"host", b"127.0.0.1:8003"), (b"origin", b"http://127.0.0.1:5174")]
    if body is not None:
        headers.append((b"content-type", b"application/json"))
    await app(dict(type="http", asgi={"version": "3.0"}, http_version="1.1", method=method,
        scheme="http", path=path, raw_path=path.encode(), query_string=b"", root_path="", headers=headers,
        client=("127.0.0.88", 12345), server=("127.0.0.1", 8003)), receive, send)
    start = next(value for value in sent if value["type"] == "http.response.start")
    content = b"".join(value.get("body", b"") for value in sent if value["type"] == "http.response.body")
    return start["status"], json.loads(content)


class GuardedHttpContractTests(unittest.TestCase):
    def profile(self):
        # No connect() method: a hidden DB call in these contracts is an error.
        return build_fictional_profile(SimpleNamespace(schema="f3_contract"), preview_key=b"F3_contract_only_32_byte_key______",
            ledger_digest=ledger_digest)

    def app(self):
        profile = self.profile()
        return create_app(account_store=profile.store, auth_settings=AuthSettings.local(),
            enable_saved_synthetic=True, guarded_profile=profile, allowed_origins=ORIGINS)

    def test_strict_create_identity_date_and_no_authority_fields(self):
        self.assertEqual(GuardedCreation(**BODY).model_dump(), BODY)
        for changes in ({"operation_id": "BAD"}, {"opening_date": "2026-W01-4"}, {"opening_date": None},
                        {"owner_id": str(uuid.UUID(int=1))}, {"generation": 2}, {"selector": "OTHER"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                GuardedCreation(**{**BODY, **changes})
        for name in ("operation_id", "opening_date"):
            with self.subTest(missing=name), self.assertRaises(ValidationError):
                GuardedCreation(**{key: value for key, value in BODY.items() if key != name})

    def test_profile_context_is_fixed_and_capabilities_are_not_authority(self):
        a, b = self.profile(), self.profile()
        self.assertEqual(a.snapshot_bytes, b.snapshot_bytes)
        self.assertEqual(a.context_id, hashlib.sha256(a.snapshot_bytes).hexdigest())
        facts = a.capabilities()
        self.assertEqual((facts["profile"], facts["source_as_of"], facts["opening_date_recommended"]), (PROFILE, "2026-01-02", "2026-01-01"))
        self.assertEqual(facts["unsupported"], ["LEGACY_ANALYTICS", "LEGACY_PACKETS", "REAL_DATA", "GUEST"])

    def test_guarded_mode_replaces_all_saved_installers(self):
        guarded = self.app()
        selected = [route for route in guarded.routes if getattr(route, "path", "").startswith("/api/v1/portfolios")]
        self.assertTrue(selected)
        self.assertTrue(all(route.endpoint.__module__ == "web_api.guarded_routes" for route in selected))
        self.assertTrue(any(route.path == "/api/v1/creation-operations/{operation_id}/reconcile" for route in guarded.routes))
        legacy = create_app()
        route = next(route for route in legacy.routes if getattr(route, "path", "") == "/api/v1/portfolios" and "POST" in route.methods)
        self.assertEqual(route.endpoint.__module__, "web_api.account_routes")

    def test_capabilities_saved_only_and_auth_boundaries_actual_asgi(self):
        app = self.app()
        status, value = asyncio.run(asgi(app, "GET", "/api/v1/capabilities"))
        self.assertEqual(status, 200)
        self.assertEqual(value["guarded_profile"]["profile"], PROFILE)
        status, value = asyncio.run(asgi(app, "POST", "/api/v1/guest-sessions", {"mode": "LOCAL_SYNTHETIC_GUEST"}))
        self.assertEqual((status, value["error"]["code"]), (503, "F3_GUARDED_SAVED_ONLY"))
        for method, path, body in (("GET", "/api/v1/portfolios", None),
                                   ("POST", "/api/v1/real-portfolios", {}),
                                   ("GET", "/api/v1/real-workspace-contract", None)):
            status, value = asyncio.run(asgi(app, method, path, body))
            self.assertEqual((status, value["error"]["code"]), (401, "AUTHENTICATION_REQUIRED"))

    def test_unknown_has_only_identity_and_reconciliation(self):
        facade = object.__new__(GuardedHttpStore)
        value = facade.unknown(uuid.UUID(int=1), uuid.UUID(int=2))
        self.assertEqual(set(value), {"schema", "profile", "disposition", "synthetic", "portfolio_id", "operation_id", "reconcile_url"})
        self.assertEqual(value["disposition"], "UNKNOWN")

    def test_commit_normative_raw_utf8_hash_and_parsed_response(self):
        facade = object.__new__(GuardedHttpStore)
        raw = '{"name":"虚构","portfolio_id":"00000000-0000-0000-0000-000000000001"}'.encode()
        value = facade.committed(uuid.UUID(int=1), uuid.UUID(int=2), raw, "a" * 64)
        self.assertEqual(value["response_json"].encode(), raw)
        self.assertEqual(value["response_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(value["response"], json.loads(raw))
        self.assertEqual(value["disposition"], "COMMITTED")

    def test_error_mapping_does_not_turn_storage_into_rollback(self):
        for code, status in (("F2_NOT_FOUND", 404), ("F2_IDEMPOTENCY_CONFLICT", 409),
                             ("F2_RIGHT_REFUSED", 403), ("F2_EXPIRY_HOLD", 423),
                             ("F2_GENERATION_DIFFERS", 423), ("F2_SHAPE", 422), ("unknown private error", 503)):
            self.assertEqual(error_status(code), status)

    def test_launcher_has_explicit_native_config_and_rejects_other_paths(self):
        with self.assertRaises(ValueError):
            load_config(Path("/tmp/unapproved.json"))
        dsn = executor_dsn(dict(socket="/private/tmp/finweb-cp7f3-20261020/runtime-a1/socket/.s.PGSQL.55433",
            database="finweb_f3_a1", executor_role="f3_a1_executor"))
        for literal in ("passfile=/dev/null", "sslmode=disable", "gssencmode=disable", "connect_timeout=2", "55433"):
            self.assertIn(literal, dsn)
