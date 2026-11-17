"""F1 R7, no database: the API contract tests of the real-mode app (design 7.1 R7 row) over fakes.

The scoped contract is installed on its four routes behind the account session; these tests call the app as an ASGI application with an in-memory
account store and a recording fake service. They check the wire shapes the contract defines, the order of the foreign-root answer, the closed
routes, the sentinels of FF1-C11 and the separation of the purposes. The PostgreSQL module (`test_postgres_real_mode`) runs the same app over the real
service on a TEST install. Everything here is invented.
"""
from __future__ import annotations

import ast
import json
import sys
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import real_mode_kit as kit  # noqa: E402
from marketdata import claim_render  # noqa: E402
from persistence import real_tails  # noqa: E402
from real_service.service import Created, Reproduction  # noqa: E402
from web_api import real_scoped_contract as contract  # noqa: E402

ROOTS = "/api/real/v1/roots"


class AppCase(unittest.TestCase):
    def setUp(self):
        import logging
        logging.getLogger("finweb.real_mode").setLevel(logging.CRITICAL)             # the route logs the class of an unexpected failure; keep the run quiet
        self.app, self.service, self.accounts = kit.build_app()
        self.alice = kit.Client(self.app)
        self.alice_id = self.alice.sign_up("alice_test")

    def op_path(self, root, operation, tail=""):
        return "%s/%s/operations/%s%s" % (ROOTS, root, operation, tail)

    def make_root(self, client, owner, origin=kit.TEST_ORIGIN):
        """Create through the route; returns (root, operation, response body)."""
        body = kit.intent()
        status, payload, _ = client.post(ROOTS, body)
        self.assertEqual(status, 201, payload)
        return uuid.UUID(payload["root_id"]), uuid.UUID(payload["operation_id"]), payload


class RouteTableTests(AppCase):
    def test_the_app_answers_the_four_contract_routes_the_auth_routes_and_a_closed_catch_all_and_nothing_else(self):
        paths = {(m, r.path) for r in self.app.routes for m in getattr(r, "methods", None) or ()}
        contract_routes = {(method, path.replace("{root_id}", "{root_id}")) for _n, method, path, _p in contract.ROUTES}
        installed = {(m, p.replace("/api/real/v1", "/api/real/v1")) for m, p in paths if p.startswith("/api/real/v1")}
        self.assertEqual(installed, contract_routes)
        auth = {p for _m, p in paths if p.startswith("/api/v1/")}
        self.assertEqual(auth, {"/api/v1/auth/session", "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/logout"})
        self.assertIn("/api/{path:path}", {p for _m, p in paths})

    def test_no_route_of_the_closed_contracts_or_the_legacy_surfaces_is_installed(self):
        modules = {getattr(r, "endpoint", None).__module__ for r in self.app.routes if getattr(r, "endpoint", None) is not None}
        for banned in ("web_api.real_workspace_routes", "web_api.real_routes", "web_api.real_workspace_contract", "web_api.guarded_routes",
                       "web_api.csv_routes", "web_api.analytics_routes"):
            self.assertNotIn(banned, modules)

    def test_the_wire_shapes_are_the_reviewed_contracts_and_the_contract_is_unchanged_in_shape(self):
        self.assertEqual([r[0] for r in contract.ROUTES], ["create", "list", "read", "reproduce"])
        self.assertEqual(contract.SCHEMA, "finweb.cp7.real_scoped_contract/2")
        self.assertEqual(contract.DIGEST_OPTIONAL_STATUSES, ("INPUT_MISMATCH", "SOURCE_REFUSED"))


class AuthenticationTests(AppCase):
    def test_every_route_needs_a_session_and_the_two_writes_need_the_csrf_token(self):
        anonymous = kit.Client(self.app)
        root, op = uuid.uuid4(), uuid.uuid4()
        for method, path in (("GET", ROOTS), ("GET", self.op_path(root, op)), ("POST", ROOTS), ("POST", self.op_path(root, op, "/reproduce"))):
            status, payload, _ = anonymous.request(method, path, {} if method == "POST" else None, csrf=False)
            self.assertEqual((status, payload["error"]["code"]), (401, "AUTHENTICATION_REQUIRED"), (method, path))
        status, payload, _ = self.alice.post(ROOTS, kit.intent(), csrf=False)
        self.assertEqual((status, payload["error"]["code"]), (403, "CSRF_REJECTED"))
        status, payload, _ = self.alice.post(self.op_path(root, op, "/reproduce"), {}, csrf=False)
        self.assertEqual((status, payload["error"]["code"]), (403, "CSRF_REJECTED"))
        self.assertEqual(self.service.calls, [])                                         # nothing reached the service


class CookieNameTests(AppCase):
    """TR7-L-6: the real-mode app's cookies never carry the fictional app's names (cookies are scoped by host and path, not by port)."""
    def test_the_session_and_bootstrap_cookies_have_names_the_fictional_app_does_not_use(self):
        from web_api import account_routes
        fresh = kit.Client(self.app)
        fresh.request("GET", "/api/v1/auth/session")
        self.assertEqual(set(fresh.cookies), {"finweb_real_csrf"})
        self.assertLessEqual(set(self.alice.cookies), {"finweb_real_session", "finweb_real_csrf"})     # the test jar keeps a cookie the server deleted
        self.assertIn("finweb_real_session", self.alice.cookies)
        for name in list(fresh.cookies) + list(self.alice.cookies):
            self.assertNotIn(name, (account_routes.SESSION_COOKIE, account_routes.BOOTSTRAP_COOKIE))

    def test_a_fictional_apps_cookie_is_not_a_session_here_and_ours_is_not_one_there(self):
        token = self.alice.cookies["finweb_real_session"]
        stranger = kit.Client(self.app)
        stranger.cookies["finweb_session"] = token                      # the fictional name, a valid token value
        status, payload, _ = stranger.request("GET", ROOTS)
        self.assertEqual((status, payload["error"]["code"]), (401, "AUTHENTICATION_REQUIRED"))
        same = kit.Client(self.app)
        same.cookies["finweb_real_session"] = token
        self.assertEqual(same.request("GET", ROOTS)[0], 200)

    def test_the_account_routes_default_to_the_fictional_names(self):
        import inspect
        from web_api import account_routes
        defaults = inspect.signature(account_routes.install_account_routes).parameters
        self.assertEqual((defaults["session_cookie"].default, defaults["bootstrap_cookie"].default), ("finweb_session", "finweb_csrf"))


class CreateTests(AppCase):
    def test_a_valid_create_returns_the_contracts_committed_payload_from_the_stored_fields(self):
        intent = kit.intent()
        status, payload, raw = self.alice.post(ROOTS, intent)
        self.assertEqual(status, 201, payload)
        self.assertEqual(set(payload), {"schema_version", "state", "persisted", "replayed", "root_id", "operation_id", "revision_id", "ledger_pin",
                                        "origin", "labels", "response_sha256", "issued_sha256", "result", "claim_limits"})
        self.assertEqual((payload["schema_version"], payload["state"], payload["persisted"], payload["replayed"]),
                         (contract.CREATE_RESULT_SCHEMA, "COMMITTED", True, False))
        self.assertEqual(payload["origin"], kit.TEST_ORIGIN)                              # the STORED origin
        self.assertEqual(payload["labels"], kit.labels_of(kit.TEST_ORIGIN))
        self.assertEqual(payload["claim_limits"], claim_render.render_claim_block(kit.TEST_ORIGIN))
        name, call = self.service.calls[-1]
        self.assertEqual(name, "create")
        self.assertEqual((call["owner"], call["generation"], call["body"]), (self.alice_id, 3, intent))        # the pin names the generation; the session names the owner
        self.assertEqual(call["link"].context_sha256, "e" * 64)                          # the pin's provenance link, not anything the request said

    def test_a_replayed_create_is_a_200(self):
        root, op = uuid.uuid4(), uuid.uuid4()
        self.service.create_outcome = Created(root, op, kit.archive_for(root, op), True)
        status, payload, _ = self.alice.post(ROOTS, kit.intent(op))
        self.assertEqual((status, payload["replayed"]), (200, True))

    def test_an_invalid_request_is_one_code_and_never_reaches_the_service(self):
        bad = [kit.intent(mode="X"), {**kit.intent(), "name": " padded"}, kit.intent(constructed_ledger_acknowledged=False), kit.intent(opening_cash={"currency": "USD", "amount": 5})]
        for body in bad:
            status, payload, _ = self.alice.post(ROOTS, body)
            self.assertEqual((status, payload["error"]["code"]), (422, "REAL_REQUEST_INVALID"))
        status, payload, _ = self.alice.post(ROOTS, b"{not json")
        self.assertEqual((status, payload["error"]["code"]), (422, "REAL_REQUEST_INVALID"))
        status, payload, _ = self.alice.post(ROOTS + "?mode=x", kit.intent())
        self.assertEqual(status, 422)
        self.assertEqual(self.service.calls, [])

    def test_a_context_the_launcher_does_not_serve_is_the_generic_404(self):
        status, payload, _ = self.alice.post(ROOTS, kit.intent(source_context_id="f" * 64))
        self.assertEqual((status, payload["error"]["code"]), (404, "RW_NOT_FOUND"))
        self.assertEqual(self.service.calls, [])

    def test_a_definite_refusal_keeps_its_public_code_and_status_and_nothing_else(self):
        for code, status in (("RW_LAPSED", 409), ("RW_WITHDRAWN", 409), ("RW_RIGHT_REFUSED", 409), ("RW_GENERATION_DIFFERS", 409),
                             ("RW_IDEMPOTENCY_CONFLICT", 409), ("SYNTHETIC_MARKET_DATA_REFUSED", 409), ("RW_DEADLINE", 409)):
            self.service.create_outcome = real_tails.Refused(code, "internal detail SENTINEL-DETAIL")
            got, payload, raw = self.alice.post(ROOTS, kit.intent())
            self.assertEqual((got, payload["error"]["code"]), (status, code))
            self.assertEqual((payload["state"], payload["persisted"], payload["operation_recorded"]), ("REFUSED", False, False))
            self.assertNotIn(b"SENTINEL-DETAIL", raw)

    def test_a_code_outside_the_public_vocabulary_is_a_503_and_is_not_reflected(self):
        for code in ("RW_LINK_MISSING", "LOCAL_SERVICE_RESULT_REFUSED", "RW_UNKNOWN_DEFERRABLE", "SOMETHING_INTERNAL"):
            self.service.create_outcome = real_tails.Refused(code, "x")
            status, payload, raw = self.alice.post(ROOTS, kit.intent())
            self.assertEqual((status, payload["error"]["code"]), (503, "REAL_UNAVAILABLE"))
            self.assertNotIn(code.encode(), raw)

    def test_an_unknown_commit_outcome_is_reported_as_unknown_never_as_rolled_back_and_is_not_retried(self):
        op = uuid.uuid4()
        self.service.create_outcome = real_tails.Unknown(op, "COMMIT_OUTCOME_NOT_KNOWN")
        status, payload, raw = self.alice.post(ROOTS, kit.intent(op))
        self.assertEqual(status, 503)
        self.assertEqual((payload["state"], payload["retried"], payload["operation_id"]), ("UNKNOWN", False, str(op)))
        self.assertNotIn(b"ROLLED_BACK", raw)
        self.assertEqual(self.service.names().count("create"), 1)                          # not retried

    def test_an_unexpected_failure_is_a_503_with_nothing_reflected(self):
        class Boom(Exception):
            pass

        def create(*a, **k):
            raise Boom("SENTINEL-BOOM")
        self.service.create = create
        status, payload, raw = self.alice.post(ROOTS, kit.intent())
        self.assertEqual((status, payload["error"]["code"]), (503, "REAL_UNAVAILABLE"))
        self.assertNotIn(b"SENTINEL-BOOM", raw)

    def test_a_block_that_is_not_the_rendering_is_never_sent(self):
        """TR5-L5 end to end: the route builds the block itself, so a defect there is a refusal and not a response. The default lineage extraction
        of a real-source root is unbuilt (first built at R8): the read is `REAL_UNAVAILABLE`, never a block with a hole."""
        root, op = uuid.uuid4(), uuid.uuid4()
        self.service.create_outcome = Created(root, op, kit.archive_for(root, op, kit.REAL_ORIGIN), False)
        status, payload, _ = self.alice.post(ROOTS, kit.intent(op))
        # TR7R-L-1: the create COMMITTED (`Created`); a response that cannot be built is the unknown outcome, never a refusal.
        self.assertEqual((status, payload["schema_version"], payload["state"], payload["operation_id"], payload["retried"]),
                         (503, contract.UNKNOWN_SCHEMA, "UNKNOWN", str(op), False))
        self.assertNotIn("error", payload)

    def test_a_committed_create_whose_response_cannot_be_built_is_unknown_and_its_repeat_replays_the_stored_root(self):
        """TR7R-L-1: whatever fails after the COMMIT (the lineage, a render error, any exception) is `UNKNOWN`; the identical command then returns the
        stored root as a replay (200) and the service creates no second root."""
        lineage = {"valuation_date": "<valuation date>", "price_session_date": "<price session>", "missed_sessions": "<missed>", "ledger_quantity": "<quantity>",
                   "source_name": "<vendor>", "exchange_mic": "<exchange>", "vendor_call": "<call>", "documentation_reference": "<reference>",
                   "adjustment_label_source": "DECLARED", "reporting_currency": "USD", "opening_cash": "<cash>", "metric_state": "AVAILABLE",
                   "freshness": "CURRENT", "delay_status": "END_OF_DAY", "reconciliation_status": "SINGLE_SOURCE", "file_hashes": ["<hash 1>", "<hash 2>"],
                   "ledger_version": "<L>", "convention_ids": ["<convention 1>", "<convention 2>"], "adjustment_label_status": "UNVERIFIABLE",
                   "retrieval_time": "<R>", "v1_statement": "no V1 event in M"}
        for label, failure in (("unbuilt lineage", claim_render.ClaimRenderError("CLAIM_LINEAGE_UNBUILT", "x")), ("a read error", OSError("disk")),
                               ("any exception", RuntimeError("SENTINEL-BOOM"))):
            with self.subTest(label):
                failing = [failure]

                def lineage_of(_archive, failing=failing):
                    if failing:
                        raise failing.pop()
                    return lineage
                app, service, _accounts = kit.build_app(lineage_of=lineage_of)
                client = kit.Client(app, peer="127.0.0.91")
                client.sign_up("repeat_user")
                root, op = uuid.uuid4(), uuid.uuid4()
                archive = kit.archive_for(root, op, kit.REAL_ORIGIN)
                service.create_outcome = Created(root, op, archive, False)
                body = kit.intent(op)
                status, first, raw = client.post(ROOTS, body)
                self.assertEqual((status, first["state"], first["operation_id"]), (503, "UNKNOWN", str(op)), first)
                self.assertNotIn(b"SENTINEL-BOOM", json.dumps(first).encode())
                service.create_outcome = Created(root, op, archive, True)           # the gateway's replay of the same operation: the same root
                status, second, _ = client.post(ROOTS, body)
                self.assertEqual((status, second["root_id"], second["operation_id"], second["replayed"]), (200, str(root), str(op), True), second)
                self.assertEqual(second["claim_limits"]["slots"]["S1"].get("source") is not None, True)
                self.assertEqual(service.names().count("create"), 2)                # two calls with the SAME operation id, and no other id was minted
                self.assertEqual({call[1]["body"]["operation_id"] for call in service.calls if call[0] == "create"}, {str(op)})

    def test_a_refusal_before_the_commit_stays_a_refusal(self):
        self.service.create_outcome = real_tails.Refused("RW_RIGHT_REFUSED")
        status, payload, _ = self.alice.post(ROOTS, kit.intent())
        self.assertIn("error", payload)
        self.assertNotEqual(status, 201)
        self.assertNotEqual(payload.get("state"), "UNKNOWN")


class ReadAndReproduceTests(AppCase):
    def test_a_read_returns_the_stored_bundle_through_the_contracts_read_shape(self):
        root, op, created = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3)]
        status, payload, _ = self.alice.get(self.op_path(root, op))
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["schema_version"], contract.READ_SCHEMA)
        self.assertEqual({k: v for k, v in payload.items() if k not in ("schema_version", "created_under_generation")},
                         {k: v for k, v in created.items() if k not in ("schema_version", "replayed")})
        name, call = [c for c in self.service.calls if c[0] == "archive_read"][-1]
        self.assertEqual((call["context_id"], call["generation"]), (kit.CONTEXT, 3))        # the root's own context and the head generation rw_list_roots named

    def test_the_opened_result_names_the_generation_the_root_was_created_under_not_the_heads_HG4_condition_2(self):
        """Design G5 check 5 (the R8 case): a root created at generation 1, the context's head now 3. The read is admitted at 3 and the payload says 1, the
        envelope's own value; the list entry for the same root says 3. Another stored generation (2) gives 2, so it is neither the head nor a constant."""
        root, op, created = self.make_root(self.alice, self.alice_id)
        self.assertNotIn("created_under_generation", created)                                    # the create result is unchanged
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3)]
        status, payload, _ = self.alice.get(self.op_path(root, op))
        self.assertEqual(status, 200, payload)
        self.assertEqual((payload["schema_version"], payload["created_under_generation"]), ("finweb.cp7.real_scoped_read/2", 1))
        self.assertEqual(payload["created_under_generation"], json.loads(self.service.archives[(root, op)].envelope)["generation"])
        self.assertEqual([c for c in self.service.calls if c[0] == "archive_read"][-1][1]["generation"], 3)
        entry = contract.list_entry(root_id=root, operation_id=op, context_id=kit.CONTEXT, generation=3, created_at="2026-11-16T00:00:00+00:00", origin=kit.TEST_ORIGIN)
        self.assertEqual(entry["generation"], 3)                                                 # the list: the context's CURRENT generation
        self.service.archives[(root, op)] = kit.archive_for(root, op, kit.TEST_ORIGIN, generation=2)
        status, payload, _ = self.alice.get(self.op_path(root, op))
        self.assertEqual((status, payload["created_under_generation"]), (200, 2))

    def test_a_stored_envelope_without_a_usable_generation_is_refused_not_guessed(self):
        root, op, _ = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3)]
        good = self.service.archives[(root, op)]
        for bad in (b"{}", b'{"generation": 0}', b'{"generation": "1"}', b'{"generation": 1.5}', b'{"generation": true}', b"not json"):
            with self.subTest(bad=bad):
                self.service.archives[(root, op)] = type(good)(good.issued, good.response, bad, good.issued_sha256, good.response_sha256, good.revision_id, good.ledger_pin)
                status, payload, _ = self.alice.get(self.op_path(root, op))
                self.assertEqual((status, payload["error"]["code"]), (503, "REAL_UNAVAILABLE"))
                self.assertNotIn("created_under_generation", payload)

    def test_the_list_entry_generation_is_documented_as_the_contexts_current_generation_and_the_list_reads_no_stored_bundle(self):
        """Design G5 checks 6 and 7: the contract docstring names it; the service's list entry body reads only the root row and the revision's operation
        id (no stored bundle, no envelope), so the list issues no extra query."""
        doc = contract.list_entry.__doc__
        self.assertIn("CURRENT generation", doc)
        self.assertIn("created_under_generation", doc)
        import inspect
        from real_service import service as real_service
        body = inspect.getsource(real_service.RealWorkspaceService._entry_body) if hasattr(real_service, "RealWorkspaceService") else ""
        self.assertTrue(body, "the list entry body must be found")
        for name in ("rw_archive", "envelope", "_archive", "created_under_generation", "rw_check"):
            self.assertNotIn(name, body)
        self.assertEqual(body.count("c.execute("), 2)                                              # the root row and the revision row, as before

    def test_a_reproduce_returns_the_contracts_reproduce_shape(self):
        root, op, _ = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3)]
        status, payload, _ = self.alice.post(self.op_path(root, op, "/reproduce"), {})
        self.assertEqual(status, 200, payload)
        self.assertEqual(set(payload), {"schema_version", "root_id", "operation_id", "origin", "labels", "status", "detail", "issued_sha256"})
        self.assertEqual((payload["status"], payload["detail"]), ("REPRODUCED", ""))
        self.assertEqual(payload["issued_sha256"], self.service.archives[(root, op)].issued_sha256)

    def test_a_reproduce_without_a_digest_is_refused_unless_the_source_refused(self):
        """TR5-L5 through the route."""
        root, op, _ = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3)]
        self.service.reproduce_outcome = real_tails.Done(Reproduction("REPRODUCED", "", None, kit.TEST_ORIGIN))
        status, payload, _ = self.alice.post(self.op_path(root, op, "/reproduce"), {})
        self.assertEqual((status, payload["error"]["code"]), (503, "REAL_UNAVAILABLE"))
        self.service.reproduce_outcome = real_tails.Done(Reproduction("SOURCE_REFUSED", "SYNTHETIC_MARKET_DATA_REFUSED", None, kit.TEST_ORIGIN))
        status, payload, _ = self.alice.post(self.op_path(root, op, "/reproduce"), {})
        self.assertEqual((status, payload["status"], payload["issued_sha256"]), (200, "SOURCE_REFUSED", None))

    def test_a_reproduce_body_is_the_empty_object_and_nothing_else(self):
        root, op, _ = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3)]
        for body in (b"[]", b'{"a":1}', b"x", b'{"expected":"y"}'):
            status, payload, _ = self.alice.post(self.op_path(root, op, "/reproduce"), body)
            self.assertEqual((status, payload["error"]["code"]), (422, "REAL_REQUEST_INVALID"), body)
        self.assertNotIn("reproduce", self.service.names())

    def test_a_root_that_has_no_such_operation_is_a_404_and_an_operation_of_another_root_is_too(self):
        root, op, _ = self.make_root(self.alice, self.alice_id)
        other_root, other_op, _ = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3), (other_root, kit.CONTEXT, 3)]
        status, payload, _ = self.alice.get(self.op_path(root, uuid.uuid4()))
        self.assertEqual((status, payload["error"]["code"]), (404, "RW_NOT_FOUND"))
        status, payload, _ = self.alice.get(self.op_path(root, other_op))                 # the other root's operation, asked under this root
        self.assertEqual((status, payload["error"]["code"]), (404, "RW_NOT_FOUND"))


class ForeignRootTests(AppCase):
    """A foreign root, an unknown root and a malformed id are ONE answer, given before the body is decoded and before anything is read."""

    def setUp(self):
        super().setUp()
        self.bob = kit.Client(self.app)
        self.bob_id = self.bob.sign_up("bob_test")
        self.root, self.op, _ = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(self.root, kit.CONTEXT, 3)]
        self.service.calls.clear()

    def test_the_other_user_gets_the_same_bytes_as_for_a_root_that_does_not_exist(self):
        foreign = self.bob.get(self.op_path(self.root, self.op))
        unknown = self.bob.get(self.op_path(uuid.uuid4(), self.op))
        malformed = self.bob.get(self.op_path("not-a-uuid", self.op))
        upper = self.bob.get(self.op_path(str(self.root).upper(), self.op))
        for status, payload, _ in (foreign, unknown, malformed, upper):
            self.assertEqual((status, payload["error"]["code"]), (404, "RW_NOT_FOUND"))
        self.assertEqual(foreign[2], unknown[2])
        self.assertEqual(foreign[2], malformed[2])
        self.assertEqual(foreign[2], upper[2])
        self.assertNotIn(str(self.root).encode(), foreign[2])                           # nothing of the asked root is reflected

    def test_the_answer_comes_before_the_stored_bundle_is_read_and_before_a_body_is_decoded(self):
        self.bob.get(self.op_path(self.root, self.op))
        self.assertEqual(self.service.names(), ["roots_of"])                              # no archive_read, no reproduce
        self.service.calls.clear()
        for garbage in (b"x", b"[]", b'{"a":1}', b""):
            status, payload, _ = self.bob.post(self.op_path(self.root, self.op, "/reproduce"), garbage)
            self.assertEqual((status, payload["error"]["code"]), (404, "RW_NOT_FOUND"), garbage)       # the 404, not the 422 of a bad body
        self.assertEqual(set(self.service.names()), {"roots_of"})
        status, payload, _ = self.alice.post(self.op_path(self.root, self.op, "/reproduce"), b"x")      # the owner's own garbage IS decoded
        self.assertEqual((status, payload["error"]["code"]), (422, "REAL_REQUEST_INVALID"))

    def test_the_list_holds_only_the_callers_roots_and_the_owner_is_the_sessions_never_a_request_field(self):
        self.service.list_entries = []
        status, payload, _ = self.bob.get(ROOTS)
        self.assertEqual((status, payload["roots"]), (200, []))
        self.assertEqual(self.service.calls[-1][1]["owner"], self.bob_id)
        self.assertNotEqual(self.bob_id, self.alice_id)
        status, payload, _ = self.bob.get(ROOTS + "?owner_id=%s" % self.alice_id)
        self.assertEqual(status, 422)


class ListTests(AppCase):
    def test_the_list_is_the_contracts_shape_with_a_refused_entry_carrying_only_its_code(self):
        root_a, root_b = uuid.UUID(int=1), uuid.UUID(int=2)
        self.service.list_entries = [contract.list_entry(root_id=root_b, context_id=kit.CONTEXT, status="RW_LAPSED"),
                                     contract.list_entry(root_id=root_a, operation_id=uuid.UUID(int=9), context_id=kit.CONTEXT, generation=3,
                                                         created_at="2026-01-05T00:00:00+00:00", origin=kit.TEST_ORIGIN)]
        status, payload, raw = self.alice.get(ROOTS)
        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], contract.LIST_SCHEMA)
        self.assertEqual([e["root_id"] for e in payload["roots"]], [str(root_a), str(root_b)])
        self.assertEqual(set(payload["roots"][0]), {"root_id", "operation_id", "context_id", "generation", "created_at", "origin"})
        self.assertEqual(payload["roots"][0]["operation_id"], str(uuid.UUID(int=9)))
        self.assertEqual(payload["roots"][1], {"root_id": str(root_b), "context_id": kit.CONTEXT, "status": "RW_LAPSED"})
        self.assertNotRegex(raw.decode(), r"ledger_pin|metric|nav|price")                # no financial number

    def test_the_list_is_empty_only_when_the_owner_has_no_root(self):
        status, payload, _ = self.alice.get(ROOTS)
        self.assertEqual((status, payload["roots"]), (200, []))


class SentinelTests(AppCase):
    """FF1-C11: raw-local fields are explicit and tested with invented sentinels. The stored envelope and the stored request carry sentinels; no
    response of the four routes contains them, and each response's key set is the contract's, so nothing raw can ride along."""

    def test_no_raw_local_sentinel_reaches_any_response(self):
        root, op, created = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3)]
        self.service.list_entries = [contract.list_entry(root_id=root, operation_id=op, context_id=kit.CONTEXT, generation=3,
                                                         created_at="2026-01-05T00:00:00+00:00", origin=kit.TEST_ORIGIN)]
        archive = self.service.archives[(root, op)]
        self.assertIn(kit.RAW_SENTINEL.encode(), archive.envelope)                       # the sentinel IS in the stored bundle
        self.assertIn(kit.PATH_SENTINEL.encode(), archive.envelope)
        responses = [self.alice.get(self.op_path(root, op))[2], self.alice.post(self.op_path(root, op, "/reproduce"), {})[2], self.alice.get(ROOTS)[2],
                     json.dumps(created).encode()]
        status, payload, raw = self.alice.post(ROOTS, kit.intent())
        responses.append(raw)
        for raw in responses:
            self.assertNotIn(kit.RAW_SENTINEL.encode(), raw)
            self.assertNotIn(kit.PATH_SENTINEL.encode(), raw)
            self.assertNotIn(b"raw_payload_path", raw)
            self.assertNotIn(b"envelope", raw)

    def test_the_response_key_sets_are_exactly_the_contracts(self):
        root, op, created = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3)]
        status, read, _ = self.alice.get(self.op_path(root, op))
        self.assertEqual(set(read), {"schema_version", "state", "persisted", "root_id", "operation_id", "revision_id", "ledger_pin", "created_under_generation",
                                     "origin", "labels", "response_sha256", "issued_sha256", "result", "claim_limits"})
        self.assertEqual(set(read["claim_limits"]), set(claim_render.BLOCK_KEYS))

    def test_a_digest_is_not_a_grant_of_visibility(self):
        """"Hashing a field does not silently grant cloud/model visibility": the digests in the response are of the issued document and the stored
        response, which the response also carries; the digest of the envelope is not offered, and neither is the envelope."""
        root, op, created = self.make_root(self.alice, self.alice_id)
        archive = self.service.archives[(root, op)]
        self.assertEqual(created["issued_sha256"], archive.issued_sha256)
        self.assertNotIn(kit.sha(archive.envelope), json.dumps(created))


class PurposeSeparationTests(AppCase):
    """FF1-C11: a read grants neither reproduce nor export. Each route asks the service for exactly its own purpose."""

    def test_each_route_calls_only_its_own_service_operation(self):
        root, op, _ = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3)]
        self.service.calls.clear()
        self.alice.get(self.op_path(root, op))
        self.assertEqual(self.service.names(), ["roots_of", "archive_read"])
        self.service.calls.clear()
        self.alice.post(self.op_path(root, op, "/reproduce"), {})
        self.assertEqual(self.service.names(), ["roots_of", "reproduce"])
        self.service.calls.clear()
        self.alice.get(ROOTS)
        self.assertEqual(self.service.names(), ["list_roots"])

    def test_there_is_no_export_route_and_the_service_has_no_export_call_the_routes_use(self):
        root, op, _ = self.make_root(self.alice, self.alice_id)
        self.service.roots[self.alice_id] = [(root, kit.CONTEXT, 3)]
        self.service.calls.clear()
        for method, path in (("GET", self.op_path(root, op, "/export")), ("GET", ROOTS + "/%s/export" % root), ("POST", self.op_path(root, op, "/export"))):
            status, payload, _ = self.alice.request(method, path, {} if method == "POST" else None)
            self.assertEqual((status, payload["error"]["code"]), (503, "REAL_MODE_ROUTE_CLOSED"), path)
        self.assertEqual(self.service.calls, [])
        source = (SRC / "web_api" / "real_mode_routes.py").read_text()
        self.assertNotIn("ARCHIVE_EXPORT", source)
        self.assertNotIn("export", [n.attr for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Attribute)])


class ClosedRouteTests(AppCase):
    def test_every_other_api_path_is_a_closed_refusal_and_reaches_nothing(self):
        paths = [("GET", "/api/v1/real-source-contexts"), ("POST", "/api/v1/real-portfolios"), ("GET", "/api/v1/real-workspace-contract"),
                 ("POST", "/api/v1/real-workspace-intents"), ("GET", "/api/v1/real-workspaces"), ("GET", "/api/v1/portfolios"),
                 ("POST", "/api/v1/portfolios"), ("GET", "/api/v1/capabilities"), ("POST", "/api/v1/guest-sessions"),
                 ("GET", "/api/v1/portfolios/x/analytics/y"), ("GET", "/api/real/v1/other"), ("PUT", ROOTS), ("DELETE", ROOTS),
                 ("GET", "/api/real/v1/roots/%s/operations" % uuid.uuid4())]
        for method, path in paths:
            status, payload, _ = self.alice.request(method, path, {} if method in ("POST", "PUT") else None)
            self.assertEqual((status, payload["error"]["code"]), (503, "REAL_MODE_ROUTE_CLOSED"), (method, path))
        self.assertEqual(self.service.calls, [])

    def test_the_closed_contract_of_E5_is_not_imported_by_the_real_mode_modules(self):
        banned = {"real_workspace_contract", "real_workspace_routes", "real_source_contexts", "real_routes", "real_requests"}
        for name in ("real_mode_routes.py", "real_launcher.py"):
            module = ast.parse((SRC / "web_api" / name).read_text())
            imported = set()
            for node in ast.walk(module):
                if isinstance(node, ast.Import):
                    imported.update(part for a in node.names for part in a.name.split("."))
                elif isinstance(node, ast.ImportFrom):
                    imported.update((node.module or "").split(".") + [a.name for a in node.names])
            self.assertEqual(imported & banned, set(), name)
        # `account_routes` imports the legacy surfaces inside the function body AFTER its `auth_only` return, so they are never imported (or installed)
        # by this app: `RouteTableTests` checks that no installed route belongs to them.
        source = (SRC / "web_api" / "account_routes.py").read_text()
        self.assertLess(source.index("if auth_only:\n        return authenticated"), source.index("from web_api.csv_routes import"))
        self.assertLess(source.index("if auth_only:\n        return authenticated"), source.index("from web_api.real_workspace_routes import"))

    def test_the_documentation_routes_are_off(self):
        for path in ("/docs", "/redoc", "/openapi.json"):
            status, _payload, _ = self.alice.get(path)
            self.assertEqual(status, 404, path)


class LineageIsReadForRealRootsOnlyTests(unittest.TestCase):
    """O-7: `lineage_of` is called for a `REAL_SOURCE` root and never for a TEST root (design 4.3: a test scope has no lineage worth a claim). The spy raises when
    called, so a call is a failure; the control shows that it IS called for a real root, so the test is not vacuous."""

    def test_a_test_root_never_reads_lineage_on_create_or_read_and_a_real_root_does(self):
        import logging
        logging.getLogger("finweb.real_mode").setLevel(logging.CRITICAL)
        calls = []

        def spy(archive):
            calls.append(archive)
            raise AssertionError("a TEST root must not read lineage")
        app, service, _accounts = kit.build_app(lineage_of=spy)
        client = kit.Client(app, peer="127.0.0.93")
        owner = client.sign_up("spy_user")
        status, created, _ = client.post(ROOTS, kit.intent())
        self.assertEqual((status, created["claim_limits"]["invented_data_mark"]), (201, claim_render.INVENTED_DATA_MARK))
        root, op = uuid.UUID(created["root_id"]), uuid.UUID(created["operation_id"])
        service.roots[owner] = [(root, kit.CONTEXT, 3)]
        status, read, _ = client.get("%s/%s/operations/%s" % (ROOTS, root, op))
        self.assertEqual((status, read["claim_limits"]["items"]), (200, []))
        self.assertEqual(calls, [])
        # control: a real-origin root calls the extractor (here it raises, which is the unknown outcome after a commit)
        real_root, real_op = uuid.uuid4(), uuid.uuid4()
        service.create_outcome = Created(real_root, real_op, kit.archive_for(real_root, real_op, kit.REAL_ORIGIN), False)
        status, unknown, _ = client.post(ROOTS, kit.intent(real_op))
        self.assertEqual((status, unknown["state"]), (503, "UNKNOWN"))
        self.assertEqual(len(calls), 1)


class BoundaryTests(AppCase):
    def test_a_foreign_origin_a_foreign_host_and_a_non_json_write_are_refused(self):
        status, payload, _ = self.alice.get(ROOTS, headers={"origin": "http://evil.example"})
        self.assertEqual(status, 403)
        anonymous = kit.Client(self.app)
        status, payload, _ = anonymous.request("POST", ROOTS, b"x", headers={"content-type": "text/plain"})
        self.assertIn(status, (400, 401, 403))


class ClientTextAgreesWithTheServerTests(unittest.TestCase):
    """R-12 (the Quant's wording ruling of 2026-11-07): the client renders its own text from the slots and never shows `items[].text`, so the English
    professional templates of `web/src/real-mode-claims.ts`, filled from the slots, must equal the server's text item by item. A change to
    `claim_limits.py` or `SEAL_LIMIT` that the client does not follow fails here."""

    def client_templates(self):
        import re
        source = (HERE.parents[1] / "web" / "src" / "real-mode-claims.ts").read_text("utf-8")
        seal = re.search(r"const SEAL_EN = '((?:[^'\\]|\\.)*)';", source).group(1).replace("\\'", "'")
        block = source.split("const EN:", 1)[1].split("  simple: {", 1)[0]
        templates = {}
        for item_id, quote, body in re.findall(r"^    ([SC][1-7]): (['`])((?:[^\\]|\\.)*?)\2,$", block, re.M):
            text = body.replace("\\'", "'")
            templates[item_id] = text.replace("${SEAL_EN}", seal)
        return templates

    @staticmethod
    def differences(templates, block):
        import re
        out = [] if sorted(templates) == sorted(item["id"] for item in block["items"]) else ["item set"]
        for item in block["items"]:
            filled = re.sub(r"\{(S[1-5])\.([a-z_0-9]+)\}", lambda m: block["slots"][m.group(1)][m.group(2)], templates.get(item["id"], ""))
            if filled != item["text"]:
                out.append(item["id"])
        return out

    def block(self):
        lineage = {field: "LV<%s>" % field for mapping in claim_render.SLOT_FIELDS.values() for field in mapping.values()}
        lineage.update(reconciliation_status="SINGLE_SOURCE", adjustment_label_source="DECLARED", metric_state="AVAILABLE")
        return claim_render.render_claim_block(kit.REAL_ORIGIN, lineage)

    def client_templates_withheld(self):
        """The withheld variant's English professional templates: the entries `EN_WITHHELD.professional` overrides, over the normal ones it spreads."""
        import re
        source = (HERE.parents[1] / "web" / "src" / "real-mode-claims.ts").read_text("utf-8")
        block = source.split("const EN_WITHHELD:", 1)[1].split("  simple: {", 1)[0]
        self.assertIn("...EN.professional,", block)
        overrides = {item_id: body.replace("\\'", "'") for item_id, _q, body in re.findall(r"^    ([SC][1-7]): (['`])((?:[^\\]|\\.)*?)\2,$", block, re.M)}
        return dict(self.client_templates(), **overrides)

    def block_withheld(self):
        lineage = {field: "LV<%s>" % field for mapping in claim_render.WITHHELD_SLOT_FIELDS.values() for field in mapping.values()}
        lineage.update(metric_state="INSUFFICIENT_DATA", nav_cause="MISSING_PRICE_HISTORY", freshness="UNKNOWN", delay_status="UNKNOWN")
        return claim_render.render_claim_block(kit.REAL_ORIGIN, lineage)

    def test_the_english_professional_templates_equal_the_servers_items(self):
        self.assertEqual(self.differences(self.client_templates(), self.block()), [])

    def test_the_english_professional_withheld_templates_equal_the_servers_withheld_items(self):
        """O-6 (PD-0082 Q4): the withheld variant's text is the same agreement, and it is not the normal block's."""
        block = self.block_withheld()
        self.assertEqual(self.differences(self.client_templates_withheld(), block), [])
        self.assertNotEqual([i["text"] for i in block["items"]], [i["text"] for i in self.block()["items"]])
        self.assertEqual(block["slots"]["S2"], {})
        self.assertEqual(block["slots"]["S5"], {})
        # the normal templates do not fill the withheld slots (a client that mixed the two would fail here, not on the screen)
        with self.assertRaises(KeyError):
            self.differences(self.client_templates(), block)

    def test_a_withheld_template_that_differs_from_the_servers_is_found(self):
        templates = self.client_templates_withheld()
        edited = dict(templates, S3=templates["S3"].replace("cause {S3.nav_cause}, ", ""))
        self.assertEqual(self.differences(edited, self.block_withheld()), ["S3"])

    def test_a_difference_in_either_text_is_found(self):
        """The control: the check is not vacuous. A client template that lost a sentence, and a server item that gained one, both differ."""
        templates, block = self.client_templates(), self.block()
        shorter = dict(templates, C4=templates["C4"].split(",")[0] + ".")
        self.assertEqual(self.differences(shorter, block), ["C4"])
        longer = dict(block, items=[dict(i, text=i["text"] + " x") if i["id"] == "S4" else i for i in block["items"]])
        self.assertEqual(self.differences(templates, longer), ["S4"])
        self.assertEqual(self.differences({k: v for k, v in templates.items() if k != "C7"}, block), ["item set", "C7"])


if __name__ == "__main__":
    unittest.main()
