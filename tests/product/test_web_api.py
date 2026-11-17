"""CP7 HTTP and real-engine slice. Expectations below are derived from raw inputs.

Two fictional holdings: 10*100=1000, 10*50=500 and 500 cash give NAV2000,
weights1/2,1/4,1/4, HHI3/8, effective positions8/3. These expectations are
written from the shipped raw inputs, never captured from the engine response.
No new HTTP test-client dependency is needed: exercise the actual ASGI app.
"""
from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from web_api.app import GuestRepository, create_app


async def asgi_request(app, method, path, body=None, *, token=None, headers=None, raw=None, chunk=0):
    payload = raw if raw is not None else b"" if body is None else json.dumps(body).encode()
    pairs = [(b"host", b"127.0.0.1:8000")]
    if method == "POST":
        pairs.append((b"content-type", b"application/json"))
    if token is not None:
        pairs.append((b"x-finweb-session", token.encode()))
    if headers:
        for key, value in headers.items():
            pairs = [(k, v) for k, v in pairs if k != key.lower().encode()]
            pairs.append((key.lower().encode(), value.encode()))
    parts = [payload] if not chunk else [payload[i:i + chunk] for i in range(0, len(payload), chunk)]
    parts = parts or [b""]
    messages = [{"type": "http.request", "body": value, "more_body": index < len(parts) - 1}
                for index, value in enumerate(parts)]
    sent = []
    async def receive():
        return messages.pop(0) if messages else {"type": "http.disconnect"}
    async def send(message):
        sent.append(message)
    await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
               "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
               "query_string": b"", "root_path": "", "headers": pairs,
               "client": ("127.0.0.1", 12345), "server": ("127.0.0.1", 8000)}, receive, send)
    start = next(m for m in sent if m["type"] == "http.response.start")
    data = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], json.loads(data), dict(start["headers"])


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(enable_local_guest=True)
        self.body = {"name": "Manual synthetic portfolio", "reporting_currency": "USD",
                     "positions": [{"symbol": "SYN-A", "quantity": "10"}, {"symbol": "SYN-B", "quantity": "10"}],
                     "cash": "500", "synthetic_acknowledged": True}
        self.token = self.session()

    def call(self, method, path, body=None, **kw):
        return asyncio.run(asgi_request(self.app, method, path, body, **kw))

    def session(self):
        status, data, _ = self.call("POST", "/api/v1/guest-sessions", {"mode": "LOCAL_SYNTHETIC_GUEST"})
        self.assertEqual(status, 201)
        return data["session_token"]

    def create(self, body=None):
        status, value, _ = self.call("POST", "/api/v1/guest-portfolios", self.body if body is None else body, token=self.token)
        self.assertEqual(status, 201, value)
        return value

    def test_actual_engines_match_raw_snapshot_arithmetic_and_preserve_exact_numbers(self):
        result = self.create()
        values = [m for m in result["valuation"]["metrics"] if m["metric_id"] == "portfolio_value" and m["view"] == "REPORTING"]
        self.assertEqual(len(values), 1)
        self.assertEqual((values[0]["value"], values[0]["exact"], values[0]["state"]), ("2000", "2000/1", "AVAILABLE"))
        concentration = {m["metric_id"]: m for m in result["diversification"]["metrics"] if not m["subject"]}
        self.assertEqual(concentration["hhi_concentration"]["exact"], "3/8")
        self.assertEqual(concentration["effective_positions"]["exact"], "8/3")
        self.assertEqual(concentration["largest_security_weight"]["exact"], "1/2")
        self.assertEqual(result["as_of"], "2026-01-02")
        self.assertTrue(result["synthetic"])
        self.assertFalse(result["persisted"])
        self.assertIn("HISTORICAL_AS_OF", " ".join(result["limitations"]))

    def test_unavailable_history_and_unknown_classification_never_become_available(self):
        result = self.create()
        risk = [m for m in result["diversification"]["metrics"] if m["metric_id"] == "modeled_volatility"]
        self.assertEqual((risk[0]["state"], risk[0]["value"], risk[0]["exact"]), ("INSUFFICIENT_DATA", None, None))
        self.assertIn("TOTAL_RETURN_COVERAGE_UNCONFIRMED", risk[0]["details"])
        countries = [m for m in result["diversification"]["metrics"] if m["metric_id"] == "country_exposure"]
        self.assertTrue(all(m["state"] == "LIMITED" for m in countries))
        self.assertTrue(any(m["subject"] == ["UNKNOWN"] for m in countries))
        self.assertTrue(all(p["severity"] == "OBSERVATION" for p in result["insights"]["packets"]))

    def test_proof_packet_open_reproduces_actual_cp3_cp5_cp6_and_compares_digest(self):
        result = self.create()
        packet = result["insights"]["packets"][0]
        path = "/api/v1/guest-portfolios/" + result["portfolio_id"] + "/packets/" + packet["insight_id"]
        status, opened, _ = self.call("GET", path, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(opened["packet"], packet)
        self.assertTrue(packet["metrics_used"])
        self.assertTrue(packet["methodology_versions"])
        self.assertTrue(packet["limitations"])
        status, replay, _ = self.call("POST", path + "/reproduce", {"expected_result_digest": opened["result_digest"]}, token=self.token)
        self.assertEqual((status, replay["status"]), (200, "REPRODUCED"))
        self.assertEqual(replay["actual_result_digest"], opened["result_digest"])
        status, replay, _ = self.call("POST", path + "/reproduce", {"expected_result_digest": "0" * 64}, token=self.token)
        self.assertEqual((status, replay["status"]), (200, "RESULT_DIFFERS"))
        status, _, _ = self.call("POST", path + "/reproduce", {}, token=self.token)
        self.assertEqual(status, 422)

    def test_session_capabilities_isolate_portfolio_packet_and_reproduction(self):
        result = self.create()
        other = self.session()
        base = "/api/v1/guest-portfolios/" + result["portfolio_id"]
        packet = base + "/packets/" + result["insights"]["packets"][0]["insight_id"]
        for method, path, body in (("GET", base, None), ("GET", packet, None), ("POST", packet + "/reproduce", {"expected_result_digest": result["insights"]["result_digest"]})):
            with self.subTest(path=path):
                status, refusal, _ = self.call(method, path, body, token=other)
                self.assertEqual((status, refusal["error"]["code"]), (404, "NOT_FOUND"))
        status, own, _ = self.call("GET", base, token=self.token)
        self.assertEqual((status, own), (200, result))

    def test_no_session_and_unknown_packet_are_refused(self):
        status, _, _ = self.call("POST", "/api/v1/guest-portfolios", self.body)
        self.assertEqual(status, 401)
        result = self.create()
        status, _, _ = self.call("GET", "/api/v1/guest-portfolios/" + result["portfolio_id"] + "/packets/absent", token=self.token)
        self.assertEqual(status, 404)

    def test_decimal_strings_remain_exact_and_do_not_round_through_binary_float(self):
        body = copy.deepcopy(self.body)
        body.update(positions=[{"symbol": "SYN-A", "quantity": "0.100001"}], cash="0.000001")
        result = self.create(body)
        total = next(m for m in result["valuation"]["metrics"] if m["metric_id"] == "portfolio_value" and m["view"] == "REPORTING")
        self.assertEqual(total["exact"], "10000101/1000000")
        self.assertEqual(result["inputs"]["positions"][0]["quantity"], "0.100001")

    def test_validation_blocks_float_numbers_real_symbols_negative_exponents_and_oversized_precision(self):
        for quantity in (10, 0.1, True, "1e2", "NaN", "-1", "0", "1000001", "0.0000001", "01"):
            body = copy.deepcopy(self.body)
            body["positions"][0]["quantity"] = quantity
            status, _, _ = self.call("POST", "/api/v1/guest-portfolios", body, token=self.token)
            self.assertEqual(status, 422, quantity)
        for patch in ({"cash": "-1"}, {"cash": "1000000001"}, {"cash": 1}, {"synthetic_acknowledged": False},
                      {"name": ""}, {"name": "\n"}, {"unknown": "field"},
                      {"positions": [{"symbol": "AAPL", "quantity": "10"}]},
                      {"positions": [{"symbol": "SYN-A", "quantity": "1"}, {"symbol": "SYN-A", "quantity": "2"}]},
                      {"positions": [], "cash": "0"}):
            status, _, _ = self.call("POST", "/api/v1/guest-portfolios", {**self.body, **patch}, token=self.token)
            self.assertEqual(status, 422, patch)

    def test_cash_only_uses_existing_engine_and_does_not_invent_security_risk(self):
        result = self.create({**self.body, "positions": [], "cash": "10"})
        total = next(m for m in result["valuation"]["metrics"] if m["metric_id"] == "portfolio_value" and m["view"] == "REPORTING")
        self.assertEqual(total["exact"], "10/1")
        largest = next(m for m in result["diversification"]["metrics"] if m["metric_id"] == "largest_security_weight")
        self.assertIsNone(largest["value"])
        self.assertIn("NO_SECURITY_POSITIONS", largest["details"])

    def test_capabilities_are_server_owned_and_unsupported_reporting_currency_is_refused(self):
        status, capabilities, _ = self.call("GET", "/api/v1/capabilities")
        self.assertEqual(status, 200)
        self.assertEqual([item["symbol"] for item in capabilities["listings"]], ["SYN-A", "SYN-B"])
        self.assertEqual(capabilities["reporting_currencies"][1], {"code": "CNY", "available": False, "reason": "FX_PATH_UNAVAILABLE"})
        status, refusal, _ = self.call("POST", "/api/v1/guest-portfolios", {**self.body, "reporting_currency": "CNY"}, token=self.token)
        self.assertEqual((status, refusal["error"]["code"]), (422, "FX_PATH_UNAVAILABLE"))

    def test_guest_path_is_disabled_unless_explicitly_enabled(self):
        status, refusal, _ = asyncio.run(asgi_request(create_app(), "GET", "/api/v1/capabilities"))
        self.assertEqual((status, refusal["error"]["code"]), (503, "LOCAL_GUEST_DISABLED"))

    def test_loopback_same_origin_json_and_actual_chunked_body_boundaries(self):
        for headers, expected in (({"origin": "https://attacker.invalid"}, 403),
                                  ({"host": "attacker.invalid"}, 403),
                                  ({"sec-fetch-site": "cross-site"}, 403),
                                  ({"content-type": "text/plain"}, 400)):
            status, _, _ = self.call("POST", "/api/v1/guest-sessions", {"mode": "LOCAL_SYNTHETIC_GUEST"}, headers=headers)
            self.assertEqual(status, expected)
        status, _, _ = self.call("POST", "/api/v1/guest-sessions", raw=b"x" * 32769, chunk=4096)
        self.assertEqual(status, 413)
        status, _, headers = self.call("GET", "/api/v1/capabilities", headers={"origin": "http://localhost:5173"})
        self.assertEqual(status, 200)
        self.assertNotIn(b"access-control-allow-origin", headers)
        self.assertEqual(headers[b"cache-control"], b"no-store")

    def test_expiry_and_capacity_have_typed_refusals(self):
        now = [0]
        repository = GuestRepository(clock=lambda: now[0], max_sessions=1, max_portfolios=1, ttl=3600)
        self.app = create_app(enable_local_guest=True, repository=repository)
        self.token = self.session()
        result = self.create()
        status, _, _ = self.call("POST", "/api/v1/guest-sessions", {"mode": "LOCAL_SYNTHETIC_GUEST"})
        self.assertEqual(status, 429)
        status, _, _ = self.call("POST", "/api/v1/guest-portfolios", self.body, token=self.token)
        self.assertEqual(status, 429)
        now[0] = 3600
        status, _, _ = self.call("GET", "/api/v1/guest-portfolios/" + result["portfolio_id"], token=self.token)
        self.assertEqual(status, 401)
        self.session()  # Capacity is reusable after explicit expiry, not silently evicted.

    def test_malformed_host_authorities_are_canonical_refusals(self):
        for host in ("[broken", "127.0.0.1:garbage", "localhost:8000/attacker", "localhost:8000?x=1",
                     "localhost:8000#x", "user@localhost:8000", "localhost:65536", "localhost:", "localhost:0"):
            with self.subTest(host=host):
                status, refusal, _ = self.call("GET", "/api/v1/capabilities", headers={"host": host})
                self.assertEqual((status, refusal["error"]["code"]), (403, "FORBIDDEN_HOST"))


if __name__ == "__main__":
    unittest.main()
