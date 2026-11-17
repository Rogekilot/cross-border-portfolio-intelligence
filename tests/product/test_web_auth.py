"""Auth primitive/boundary tests; actual persistence tests are separately opt-in."""
from __future__ import annotations

import asyncio
import unittest
from http.cookies import SimpleCookie

from tests.product.test_web_api import asgi_request
from web_api import auth
from web_api.app import create_app


def cookie_header(headers):
    # For one bootstrap cookie; the actual integration client preserves all headers.
    jar = SimpleCookie()
    jar.load(headers[b"set-cookie"].decode())
    return "; ".join(key + "=" + value.value for key, value in jar.items())


class PasswordTests(unittest.TestCase):
    def test_salted_scrypt_correct_wrong_and_unknown_user(self):
        value = "correct horse test only"
        one, two = auth.password_hash(value), auth.password_hash(value)
        self.assertTrue(one.startswith("scrypt$131072$8$1$"))
        self.assertNotEqual(one, two)
        self.assertTrue(auth.verify_password(value, one))
        self.assertFalse(auth.verify_password("different password test", one))
        self.assertFalse(auth.verify_password(value, None))

    def test_malformed_storage_does_not_choose_unbounded_kdf_parameters(self):
        self.assertFalse(auth.verify_password("a sufficiently long phrase", "scrypt$999999999$8$1$aa$bb"))
        self.assertFalse(auth.verify_password("a sufficiently long phrase", "scrypt$131072$8$1$xx$yy"))

    def test_credential_bounds_and_normalization(self):
        self.assertEqual(auth.username("Alice_01"), "alice_01")
        for value in ("ab", "1alice", "ali ce", "爱丽丝", "Kalvin", "a" * 33, "alice\n"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                auth.username(value)
        for value in ("short", "x" * 129, "密码" * 64):
            with self.subTest(value=value), self.assertRaises(ValueError):
                auth.password(value)
        self.assertEqual(auth.password(" " * 15), " " * 15)  # Never silently trim passwords.

    def test_opaque_token_and_csrf_domains_and_secure_defaults(self):
        token = auth.new_token()
        self.assertTrue(auth.valid_token(token))
        self.assertEqual(len(auth.digest_token(token)), 64)
        self.assertNotEqual(auth.digest_token(token), auth.csrf_token(token))
        self.assertFalse(auth.valid_token("x" * 10000))
        self.assertTrue(auth.AuthSettings().secure_cookie)
        with self.assertRaises(ValueError):
            auth.AuthSettings(secure_cookie=False)

    def test_hash_concurrency_limit_fails_without_waiting_or_allocating(self):
        auth._KDF_SLOTS.acquire()
        auth._KDF_SLOTS.acquire()
        try:
            with self.assertRaises(auth.PasswordCapacityError):
                auth.password_hash("a sufficiently long phrase")
        finally:
            auth._KDF_SLOTS.release()
            auth._KDF_SLOTS.release()


class NeverStore:
    def __getattr__(self, name):
        raise AssertionError("Database must not be touched before boundary authorization: " + name)


class AuthBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(account_store=NeverStore(), auth_settings=auth.AuthSettings.local(), enable_saved_synthetic=True)

    def call(self, method, path, body=None, **kwargs):
        return asyncio.run(asgi_request(self.app, method, path, body, **kwargs))

    def test_disabled_by_default_and_https_by_default(self):
        default = create_app()
        status, data, _ = asyncio.run(asgi_request(default, "GET", "/api/v1/auth/session"))
        self.assertEqual((status, data["error"]["code"]), (503, "ACCOUNT_MODE_DISABLED"))
        secure = create_app(account_store=NeverStore(), auth_settings=auth.AuthSettings(), enable_saved_synthetic=True)
        status, data, _ = asyncio.run(asgi_request(secure, "GET", "/api/v1/auth/session"))
        self.assertEqual((status, data["error"]["code"]), (403, "HTTPS_REQUIRED"))

    def test_bootstrap_http_only_strict_and_no_credential_reflection(self):
        status, data, headers = self.call("GET", "/api/v1/auth/session")
        self.assertEqual(status, 200)
        self.assertFalse(data["authenticated"])
        self.assertIsNone(data["user"])
        raw = headers[b"set-cookie"].decode()
        self.assertIn("HttpOnly", raw)
        self.assertIn("SameSite=strict", raw)
        self.assertIn("Path=/api/v1", raw)
        self.assertEqual(headers[b"cache-control"], b"no-store")

    def test_csrf_and_origin_required_before_any_account_lookup(self):
        credentials = {"username": "alice", "password": "a sufficiently long phrase"}
        for route in ("register", "login"):
            for headers in ({}, {"Origin": "http://127.0.0.1:5173"}, {"Origin": "null"}):
                status, data, _ = self.call("POST", "/api/v1/auth/" + route, credentials, headers=headers)
                self.assertEqual(status, 403)
        for route in ("/api/v1/portfolios", "/api/v1/portfolios/not-a-uuid", "/api/v1/portfolios/foreign/packets/id"):
            status, data, _ = self.call("GET", route)
            self.assertEqual((status, data["error"]["code"]), (401, "AUTHENTICATION_REQUIRED"))

    def test_invalid_credential_body_never_reflects_password(self):
        status, data, _ = self.call("POST", "/api/v1/auth/login", {"username": "alice", "password": "secret-value"})
        self.assertEqual(status, 422)
        self.assertNotIn("secret-value", str(data))

    def test_non_ascii_csrf_is_typed_refusal_before_database_access(self):
        status, data, _ = self.call("POST", "/api/v1/auth/login",
            {"username": "alice", "password": "a sufficiently long phrase"},
            headers={"Origin": "http://127.0.0.1:5173", "Cookie": "finweb_csrf=" + "b" * 43,
                     "X-Finweb-CSRF": "é" * 32})
        self.assertEqual((status, data["error"]["code"]), (403, "CSRF_REJECTED"))

    def test_account_mode_and_client_identity_injection_rejected(self):
        body = {"name": "Example", "reporting_currency": "USD", "positions": [], "cash": "10", "synthetic_acknowledged": True}
        status, _, _ = self.call("POST", "/api/v1/portfolios", body)
        self.assertEqual(status, 422)  # No silent genuine-to-synthetic conversion.
        body.update(mode="LOCAL_SYNTHETIC_ACCOUNT", user_id="foreign")
        status, _, _ = self.call("POST", "/api/v1/portfolios", body)
        self.assertEqual(status, 422)
