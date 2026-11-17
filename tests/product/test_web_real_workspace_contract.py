"""Closed RAM/request/ASGI compatibility checks; run only via root-approved guard.

No database, listener, browser, source payload or external request is used. App
construction/legacy synthetic compatibility use the existing two web fixtures and
approved product-contract JSON, not data/marketdata payloads. Do not use discover.
"""
import asyncio
import copy
import json
import sys
import unittest
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import psycopg
from marketdata.canonical import canonical_json
from web_api import auth
from web_api.app import create_app
from web_api.real_workspace_contract import (ClosedCatalogue, ClosedContext, ContractRefusal,
    MODE, REQUEST_SCHEMA, _bounded_json, contract_payload, parse_intent, refuse_intent, refusal_payload)

GET = "/api/v1/real-workspace-contract"
POST = "/api/v1/real-workspace-intents"
TOKEN = "T" * 43
ORIGIN = "http://127.0.0.1:5173"


def intent(**changes):
    value = dict(schema_version=REQUEST_SCHEMA, operation_id=str(uuid.UUID(int=0xabcdef)), mode=MODE,
        source_context_id="a" * 64, expected_release_id="b" * 64, name="Constructed test",
        reporting_currency="USD", as_of="2026-09-30", constructed_ledger_acknowledged=True,
        opening_positions=[dict(listing_id=str(uuid.UUID(int=2)), quantity="1", cost_basis=None, acquired_on=None)],
        opening_cash=dict(currency="USD", amount="0"))
    value.update(changes)
    return value


def encoded(value):
    return json.dumps(value, ensure_ascii=True).encode("utf-8")


def catalogue(status="UNQUALIFIED"):
    return ClosedCatalogue((ClosedContext("a" * 64, "b" * 64, status),))


class SessionOnlyStore:
    def __init__(self):
        self.lookups, self.active, self.failure = [], True, False

    def session_user(self, token):
        self.lookups.append(token)
        if self.failure:
            raise psycopg.OperationalError("PRIVATE_DB_EXCEPTION")
        return dict(user_id=str(uuid.UUID(int=1)), username="fictional") if self.active and token == TOKEN else None

    def __getattr__(self, name):
        raise AssertionError("unexpected store/operation/financial call: " + name)


def make_app(rows=None, *, store=None, guest=False):
    store = SessionOnlyStore() if store is None else store
    if rows is None:
        return create_app(account_store=store, auth_settings=auth.AuthSettings.local(),
            enable_saved_synthetic=True, enable_local_guest=guest), store
    with patch("web_api.real_workspace_routes.ClosedCatalogue", return_value=rows):
        return create_app(account_store=store, auth_settings=auth.AuthSettings.local(),
            enable_saved_synthetic=True, enable_local_guest=guest), store


async def raw_request(app, method, path, *, body=b"", headers=None, query=b"", chunks=None,
                      reads=None, content_type="application/json"):
    pairs = [(b"host", b"127.0.0.1:8000")]
    if method == "POST" and content_type is not None:
        pairs.append((b"content-type", content_type.encode()))
    headers = headers if headers is not None else [("Origin", ORIGIN),
        ("Cookie", "finweb_session=" + TOKEN), ("X-Finweb-CSRF", auth.csrf_token(TOKEN))]
    pairs += [(key.lower().encode(), value.encode()) for key, value in headers]
    chunks = list(chunks) if chunks is not None else [body]
    messages = [dict(type="http.request", body=chunk, more_body=index < len(chunks) - 1)
        for index, chunk in enumerate(chunks)]
    sent = []
    async def receive():
        if reads is not None:
            reads.append(True)
        return messages.pop(0) if messages else dict(type="http.disconnect")
    async def send(message):
        sent.append(message)
    await app(dict(type="http", asgi=dict(version="3.0"), http_version="1.1", method=method,
        scheme="http", path=path, raw_path=path.encode(), query_string=query, root_path="",
        headers=pairs, client=("127.0.0.1", 12345), server=("127.0.0.1", 8000)), receive, send)
    start = next(item for item in sent if item["type"] == "http.response.start")
    raw = b"".join(item.get("body", b"") for item in sent if item["type"] == "http.response.body")
    return start["status"], raw, dict(start["headers"])


def call(app, method, path, **kwargs):
    return asyncio.run(raw_request(app, method, path, **kwargs))


class IntentTests(unittest.TestCase):
    def reject(self, raw):
        with self.assertRaises(ContractRefusal) as caught:
            parse_intent(raw)
        self.assertEqual((caught.exception.status, caught.exception.code), (422, "REAL_REQUEST_INVALID"))
        self.assertEqual(refusal_payload(caught.exception)["error"]["detail"], "The real-workspace contract request is invalid")

    def test_valid_request_nulls_zero_cash_and_exact_canonical_decimals(self):
        for quantity in ("0.000001", "1", "999999.999999", "1000000"):
            for cash in ("0", "0.000001", "1000000000"):
                body = intent()
                body["opening_positions"][0]["quantity"] = quantity
                body["opening_cash"]["amount"] = cash
                self.assertEqual(parse_intent(encoded(body)), body)

    def test_decimal_lexical_forms_and_numeric_ranges_are_rejected_without_rounding(self):
        for value in ("", "-0", "+1", "01", "1.0", "0.00", "1e2", " 1", "1 ", ".1", "1.",
                      "0.0000001", "1000000.000001", "NaN", "Infinity", 1, True, None, "0"):
            with self.subTest(quantity=value):
                body = intent(); body["opening_positions"][0]["quantity"] = value
                self.reject(encoded(body))
        for value in ("1000000000.000001", "10000000000", "1.0", "-1", 1, False, None):
            body = intent(); body["opening_cash"]["amount"] = value
            self.reject(encoded(body))

    def test_required_extra_fields_exact_array_currency_and_nulls(self):
        for key in intent():
            body = intent(); del body[key]
            self.reject(encoded(body))
        for key in ("owner_id", "portfolio_id", "price", "path", "approved", "raw", "source_registry"):
            self.reject(encoded(intent(**{key: "PRIVATE_VALUE"})))
        for key in ("listing_id", "quantity", "cost_basis", "acquired_on"):
            body = intent(); del body["opening_positions"][0][key]
            self.reject(encoded(body))
        for key, value in (("cost_basis", "0"), ("cost_basis", 0), ("acquired_on", "2026-09-30"), ("price", "100")):
            body = intent(); body["opening_positions"][0][key] = value
            self.reject(encoded(body))
        for positions in ([], [intent()["opening_positions"][0]] * 2, {}, None):
            self.reject(encoded(intent(opening_positions=positions)))
        for changes in (dict(mode="LOCAL_SYNTHETIC_ACCOUNT"), dict(reporting_currency="CNY"),
                dict(constructed_ledger_acknowledged=False), dict(constructed_ledger_acknowledged=1)):
            self.reject(encoded(intent(**changes)))
        for cash in ({"currency": "CNY", "amount": "1"}, {"currency": "USD"},
                {"currency": "USD", "amount": "1", "account_id": "PRIVATE"}):
            self.reject(encoded(intent(opening_cash=cash)))

    def test_name_scalar_rules_are_concrete_and_do_not_invent_visual_normalization(self):
        for name in ("测试", "😀" * 80, "e\u0301", "\u200b"):
            self.assertEqual(parse_intent(encoded(intent(name=name)))["name"], name)
        for name in ("", " ", " a", "a ", "a\n", "a\x7f", "a\x85", "a\x9f", "😀" * 81, "\ud800"):
            self.reject(encoded(intent(name=name)))

    def test_uuid_dates_hashes_and_schema_require_exact_values(self):
        for changes in (dict(operation_id=intent()["operation_id"].upper()), dict(operation_id="{00000000-0000-0000-0000-000000000001}"),
                dict(as_of="2026-02-30"), dict(as_of="0000-01-01"), dict(as_of="2026-9-30"),
                dict(source_context_id="A" * 64), dict(expected_release_id="b" * 64 + "\n"),
                dict(schema_version="finweb.cp7.real_workspace_create/2")):
            self.reject(encoded(intent(**changes)))
        body = intent(); body["opening_positions"][0]["listing_id"] = "1"
        self.reject(encoded(body))

    def test_invalid_json_duplicate_keys_surrogates_finite_constants_and_bom(self):
        raw = encoded(intent())
        for bad in (b"", b"[]", b"{}", b"null", b"\xff", b"\xef\xbb\xbf" + raw, raw + b"{}",
                b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e9999}', b'{"x":01}',
                raw.replace(b'"cost_basis": null', b'"cost_basis": null, "cost_basis": null'),
                raw.replace(b'"name": "Constructed test"', b'"name": "\\udc00"'),
                raw.replace(b'"name": "Constructed test"', b'"name": "a", "name": "a"')):
            self.reject(bad)

    def test_depth_and_decoded_token_bounds_precede_container_tree_parse(self):
        raw = b'[' * 9 + b'"x"' + b']' * 9
        for oversized in (raw, b'"' + b'x' * 4097 + b'"', b'"' + b'\\u0061' * 4097 + b'"', b'1' * 4097):
            with self.subTest(size=len(oversized)), patch("web_api.real_workspace_contract.json.loads", side_effect=AssertionError("tree parse reached")):
                self.reject(oversized)
        self.assertEqual(_bounded_json(b'[' * 8 + b'"x"' + b']' * 8), [[[[[[[["x"]]]]]]]])
        self.assertEqual(_bounded_json(b'"' + b'x' * 4096 + b'"'), "x" * 4096)
        self.reject(b'[{]}')

    def test_actual_body_limit_accepts_exact_bound_and_rejects_over_before_tree(self):
        raw = encoded(intent())
        at_limit = raw + b" " * (32768 - len(raw))
        self.assertEqual(parse_intent(at_limit), intent())
        with patch("web_api.real_workspace_contract.json.loads", side_effect=AssertionError("tree parse reached")):
            self.reject(at_limit + b" ")


class CatalogueTests(unittest.TestCase):
    def test_empty_and_16_contexts_are_blocked_immutable_and_no_filesystem_needed(self):
        records = tuple(ClosedContext(format(i, "064x"), "b" * 64, "UNQUALIFIED") for i in range(16))
        with patch("builtins.open", side_effect=AssertionError("file open")), patch.object(Path, "read_bytes", side_effect=AssertionError("file read")):
            empty = contract_payload(ClosedCatalogue())
            populated = contract_payload(ClosedCatalogue(records))
        self.assertEqual(empty["contexts"], [])
        self.assertEqual(len(populated["contexts"]), 16)
        self.assertEqual(populated["approved_context_count"], 0)
        self.assertFalse(any(populated["capabilities"].values()))
        self.assertEqual(populated["state"], "BLOCKED")
        self.assertLessEqual(len(canonical_json(populated).encode()), 65536)
        with self.assertRaises(AttributeError):
            records[0].status = "QUALIFIED"

    def test_whole_validation_rejects_unsorted_duplicates_oversize_extras_and_positive(self):
        first, second = ClosedContext("a" * 64, "b" * 64, "UNQUALIFIED"), ClosedContext("c" * 64, "b" * 64, "WITHDRAWN")
        invalid = (ClosedCatalogue([first]), ClosedCatalogue((second, first)), ClosedCatalogue((first, first)),
            ClosedCatalogue(tuple(ClosedContext(format(i, "064x"), "b" * 64, "UNQUALIFIED") for i in range(17))),
            ClosedCatalogue((dict(context_id="a" * 64, declared_release_id="b" * 64, status="UNQUALIFIED", approved=True),)),
            catalogue("QUALIFIED"), catalogue("READY"), ClosedCatalogue((ClosedContext("A" * 64, "b" * 64, "UNQUALIFIED"),)))
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ContractRefusal) as caught:
                refuse_intent(value, intent(source_context_id="0" * 64))
            self.assertEqual(caught.exception.code, "REAL_CONTRACT_CONFIGURATION_UNAVAILABLE")

    def test_context_binding_withdrawal_and_unqualified_precedence_and_retries(self):
        cases = ((ClosedCatalogue(), intent(), "REAL_CONTEXT_NOT_CONFIGURED"),
            (catalogue("WITHDRAWN"), intent(expected_release_id="c" * 64), "REAL_CONTEXT_BINDING_DIFFERS"),
            (catalogue("WITHDRAWN"), intent(), "REAL_CONTEXT_EXECUTION_WITHDRAWN"),
            (catalogue(), intent(), "REAL_CONTEXT_NOT_QUALIFIED"))
        for rows, body, code in cases:
            for again in (body, body, {**body, "operation_id": str(uuid.UUID(int=77))}):
                with self.assertRaises(ContractRefusal) as caught:
                    refuse_intent(rows, again)
                error = refusal_payload(caught.exception)
                self.assertEqual(error["error"]["code"], code)
                self.assertEqual((error["persisted"], error["operation_recorded"], error["economic_writes"]), (False, False, 0))
                self.assertLessEqual(len(canonical_json(error).encode()), 4096)

    def test_output_refuses_whole_envelope_instead_of_truncating(self):
        with patch("web_api.real_workspace_contract.MAX_OUTPUT_BYTES", 1), self.assertRaises(ContractRefusal) as caught:
            contract_payload(ClosedCatalogue())
        self.assertEqual(caught.exception.code, "REAL_CONTRACT_CONFIGURATION_UNAVAILABLE")


class RouteTests(unittest.TestCase):
    def test_default_exact_bytes_headers_and_permanent_no_write_retries(self):
        app, store = make_app()
        status, raw, headers = call(app, "GET", GET)
        self.assertEqual((status, raw), (200, canonical_json(contract_payload(ClosedCatalogue())).encode()))
        self.assertEqual(headers[b"cache-control"], b"no-store")
        self.assertEqual(headers[b"x-content-type-options"], b"nosniff")
        self.assertNotIn(b"set-cookie", headers)
        errors = [call(app, "POST", POST, body=encoded(body)) for body in (intent(), intent(), intent(name="Changed content"))]
        self.assertTrue(all(status == 409 for status, _, _ in errors))
        self.assertEqual(len({raw for _, raw, _ in errors}), 1)
        error = json.loads(errors[0][1])
        self.assertEqual(error["error"]["code"], "REAL_CONTEXT_NOT_CONFIGURED")
        self.assertFalse(error["operation_recorded"])
        self.assertEqual(store.lookups, [TOKEN] * 4)

    def test_request_invalid_precedes_bad_catalogue_and_bad_catalogue_precedes_unknown(self):
        app, _ = make_app(catalogue("QUALIFIED"))
        for body, status, code in ((b"bad", 422, "REAL_REQUEST_INVALID"),
                (encoded(intent(source_context_id="0" * 64)), 503, "REAL_CONTRACT_CONFIGURATION_UNAVAILABLE")):
            actual, raw, _ = call(app, "POST", POST, body=body)
            self.assertEqual((actual, json.loads(raw)["error"]["code"]), (status, code))

    def test_auth_and_csrf_precede_parser_catalogue_and_query_errors(self):
        app, store = make_app(catalogue("QUALIFIED"))
        with patch("web_api.real_workspace_routes.parse_intent", side_effect=AssertionError("parser before auth")), patch("web_api.real_workspace_routes.contract_payload", side_effect=AssertionError("catalogue before auth")):
            store.active = False
            for method, path, kw in (("GET", GET, dict(query=b"private=x")), ("GET", GET, dict(body=b"private")), ("POST", POST, dict(body=b"bad"))):
                actual, raw, _ = call(app, method, path, **kw)
                self.assertEqual((actual, json.loads(raw)["error"]["code"]), (401, "AUTHENTICATION_REQUIRED"))
            store.active = True
            headers = [("Origin", ORIGIN), ("Cookie", "finweb_session=" + TOKEN)]
            actual, raw, _ = call(app, "POST", POST, body=b"bad", headers=headers)
            self.assertEqual((actual, json.loads(raw)["error"]["code"]), (403, "CSRF_REJECTED"))

    def test_transport_precedes_route_auth_for_bad_host_content_type_and_oversize(self):
        app, store = make_app(); store.active = False
        cases = ((dict(headers=[("Host", "external.example")]), 403, "FORBIDDEN_HOST"),
            (dict(content_type="text/plain"), 400, "JSON_REQUIRED"),
            (dict(body=b"x" * 32769), 413, "REQUEST_TOO_LARGE"))
        for kw, status, code in cases:
            options = {"body": b"bad", **kw}
            actual, raw, _ = call(app, "POST", POST, **options)
            self.assertEqual((actual, json.loads(raw)["error"]["code"]), (status, code))
        self.assertEqual(store.lookups, [])

    def test_get_query_and_chunk_stop_and_empty_stream_exhaustion(self):
        app, _ = make_app()
        for query in (b"x=1", b"x=1&x=2"):
            reads = []; status, raw, _ = call(app, "GET", GET, query=query, reads=reads)
            self.assertEqual((status, reads), (422, []))
        reads = []; status, _, _ = call(app, "GET", GET, chunks=[b"", b"x", b"never"], reads=reads)
        self.assertEqual((status, len(reads)), (422, 2))
        reads = []; status, _, _ = call(app, "GET", GET, chunks=[b"", b"", b""], reads=reads)
        self.assertEqual((status, len(reads)), (200, 3))
        status, _, _ = call(app, "POST", POST, body=encoded(intent()), query=b"x=1")
        self.assertEqual(status, 422)

    def test_raw_query_segments_refuse_even_when_parsed_params_are_empty(self):
        app, _ = make_app()
        for query in (b"&", b"&&", b";"):
            with self.subTest(query=query):
                reads = []
                status, raw, _ = call(app, "GET", GET, query=query, body=b"PRIVATE_BODY", reads=reads)
                self.assertEqual((status, json.loads(raw)["error"]["code"], reads),
                    (422, "REAL_REQUEST_INVALID", []))
                status, raw, _ = call(app, "POST", POST, query=query, body=encoded(intent()))
                self.assertEqual((status, json.loads(raw)["error"]["code"]), (422, "REAL_REQUEST_INVALID"))
                self.assertNotIn(b"PRIVATE_BODY", raw)

    def test_duplicate_csrf_origins_storage_and_disabled_errors_keep_old_envelope(self):
        app, store = make_app()
        headers = [("Origin", ORIGIN), ("Cookie", "finweb_session=" + TOKEN), ("X-Finweb-CSRF", auth.csrf_token(TOKEN))]
        for extra in (("Origin", ORIGIN), ("X-Finweb-CSRF", auth.csrf_token(TOKEN))):
            status, raw, _ = call(app, "POST", POST, body=b"bad", headers=headers + [extra])
            self.assertEqual((status, json.loads(raw)["schema_version"]), (403, "finweb.cp7/1"))
        store.failure = True
        status, raw, _ = call(app, "GET", GET)
        self.assertEqual((status, json.loads(raw)["error"]["code"]), (503, "ACCOUNT_STORAGE_UNAVAILABLE"))
        self.assertNotIn(b"PRIVATE_DB_EXCEPTION", raw)
        status, raw, _ = call(create_app(), "GET", GET)
        self.assertEqual((status, json.loads(raw)["error"]["code"]), (503, "ACCOUNT_MODE_DISABLED"))

    def test_no_financial_operation_or_source_file_calls_from_new_routes(self):
        app, _ = make_app(catalogue())
        targets = ("marketdata.files.FileStore.read_by_hash", "persistence.market_data_store.read_release",
            "performance_service.service.compute_for_portfolio", "persistence.web_account_store.WebAccountStore.create_portfolio",
            "web_api.synthetic.SyntheticWorld.create")
        with ExitStack() as stack:
            for target in targets:
                stack.enter_context(patch(target, side_effect=AssertionError("financial/source/operation called")))
            stack.enter_context(patch("builtins.open", side_effect=AssertionError("new source file read")))
            stack.enter_context(patch.object(Path, "read_bytes", side_effect=AssertionError("new source bytes read")))
            self.assertEqual(call(app, "GET", GET)[0], 200)
            for raw in (encoded(intent()), encoded(intent(name="PRIVATE_VALUE", path="PRIVATE_PATH"))):
                status, body, _ = call(app, "POST", POST, body=raw)
                self.assertIn(status, (409, 422))
                self.assertNotIn(b"PRIVATE_", body)


class OldCompatibilityTests(unittest.TestCase):
    def test_old_e1_default_complete_body_and_refusal_remain_exact(self):
        app, _ = make_app()
        expected = dict(schema_version="finweb.cp7.real_source/1", milestone="E1_GATE_ONLY", mode=MODE,
            state="BLOCKED", readiness_stage="METADATA_ONLY",
            provenance=dict(ledger_origin="PROJECT_CONSTRUCTED_NONPERSONAL_UAT_REQUESTED", market_origin="REAL_SOURCE_REQUESTED_NOT_QUALIFIED", personal_holdings=False),
            capabilities=dict(source_metadata=True, payload_verification=False, source_qualification=False, create=False,
                saved=False, workspace=False, analytics=False, imports=False, exports=False, evidence=False),
            approved_context_count=0, contexts=[], blockers=["NO_APPROVED_REAL_SOURCE_CONTEXT", "REAL_PORTFOLIO_STORAGE_NOT_IMPLEMENTED", "REAL_ANALYTICS_NOT_IMPLEMENTED"],
            limits=dict(http_bytes=32768, output_bytes=65536), scope=dict(markets=["US"], reporting_currencies=["USD"]),
            support=dict(data_action="EXISTING_REGISTERED_PROJECT_METADATA_ONLY", download_or_admission=False, real_uat_verified=False, hg4_approved=False))
        before = call(app, "GET", "/api/v1/real-source-contexts")
        self.assertEqual((before[0], before[1]), (200, canonical_json(expected).encode()))
        old_intent = dict(operation_id=str(uuid.UUID(int=1)), mode=MODE, source_context_id="a" * 64,
            expected_configuration_digest="b" * 64, release_id="c" * 64, as_of="2026-09-30", constructed_ledger_acknowledged=True)
        old_error = call(app, "POST", "/api/v1/real-portfolios", body=encoded(old_intent))
        self.assertEqual(old_error[0], 409)
        self.assertEqual(old_error[1], canonical_json(dict(schema_version="finweb.cp7.real_source/1",
            error=dict(code="REAL_SOURCE_NOT_CONFIGURED", detail="No matching real-source context is configured", kind="CAPABILITY"))).encode())
        call(app, "POST", POST, body=encoded(intent()))
        self.assertEqual(call(app, "GET", "/api/v1/real-source-contexts"), before)

    def test_existing_synthetic_complete_object_is_unchanged_with_hook_and_after_intents(self):
        with patch("web_api.real_workspace_routes.install_real_workspace_routes", return_value=None):
            baseline, _ = make_app(guest=True)
        enabled, _ = make_app(guest=True)
        request = dict(name="Existing fictional fixture", reporting_currency="USD", positions=[dict(symbol="SYN-A", quantity="10"), dict(symbol="SYN-B", quantity="10")], cash="500", synthetic_acknowledged=True)
        snapshots = []
        for app in (baseline, enabled):
            _, session, _ = call(app, "POST", "/api/v1/guest-sessions", body=encoded(dict(mode="LOCAL_SYNTHETIC_GUEST")))
            token = json.loads(session)["session_token"]
            headers = [("Origin", ORIGIN), ("X-Finweb-Session", token)]
            with patch("web_api.app.uuid.uuid4", return_value=uuid.UUID(int=303)):
                status, raw, _ = call(app, "POST", "/api/v1/guest-portfolios", body=encoded(request), headers=headers)
            self.assertEqual(status, 201)
            snapshots.append(raw)
            if app is enabled:
                for body in (intent(), intent(name="Different fictional request")):
                    self.assertEqual(call(app, "POST", POST, body=encoded(body))[0], 409)
                status, reloaded, _ = call(app, "GET", "/api/v1/guest-portfolios/" + json.loads(raw)["portfolio_id"], headers=headers)
                self.assertEqual((status, reloaded), (200, raw))
        self.assertEqual(snapshots[0], snapshots[1])
        value = json.loads(snapshots[1])
        metric = next(m for m in value["valuation"]["metrics"] if m["metric_id"] == "portfolio_value" and m["view"] == "REPORTING")
        self.assertEqual((metric["value"], metric["exact"], metric["state"]), ("2000", "2000/1", "AVAILABLE"))
        self.assertTrue(value["synthetic"])


if __name__ == "__main__":
    unittest.main()
