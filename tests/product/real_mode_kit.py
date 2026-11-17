"""Shared fakes and an ASGI client for the F1 R7 real-mode app tests. Not a test module.

Nothing here opens a connection or a socket: the app is called as an ASGI application, the account store is an in-memory fake with the methods the
auth routes call, and the service is a recording fake with the methods the routes call (the PostgreSQL module runs the real ones). Everything stored
is invented.
"""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from marketdata.canonical import canonical_json  # noqa: E402
from persistence import real_labels, real_tails  # noqa: E402
from persistence.web_account_store import AccountStoreError  # noqa: E402
from real_service.service import Archive, Created, ProvenanceLink, Reproduction  # noqa: E402
from web_api import auth  # noqa: E402
from web_api.real_mode_routes import ContextPin, create_real_mode_app  # noqa: E402

HOST = "127.0.0.1:8004"
ORIGIN = "http://127.0.0.1:8004"
ORIGINS = ("http://127.0.0.1:8004", "http://127.0.0.1:5175")
TEST_ORIGIN = {"market_origin": "SYNTHETIC_TEST", "ledger_origin": "INVENTED_TEST_LEDGER", "personal_holdings": False, "synthetic": True}
REAL_ORIGIN = {"market_origin": "REAL_SOURCE", "ledger_origin": "PROJECT_CONSTRUCTED_NONPERSONAL_UAT", "personal_holdings": False, "synthetic": False}
CONTEXT = "c" * 64
RELEASE = "d" * 64
LISTING = "22222222-2222-4222-8222-222222222222"
#: Invented sentinels for the raw-local fields (FF1-C11): they sit in the stored envelope and in the stored request, and must reach no response.
RAW_SENTINEL = "RAW-LOCAL-SENTINEL-7f3a91"
PATH_SENTINEL = "/Users/invented/raw/payload-SENTINEL-55b0.json"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def intent(op=None, **changes):
    value = {"schema_version": "finweb.cp7.real_scoped_create/1", "operation_id": str(op or uuid.uuid4()), "source_context_id": CONTEXT,
             "expected_release_id": RELEASE, "name": "invented probe root", "reporting_currency": "USD", "as_of": "2026-01-05",
             "constructed_ledger_acknowledged": True,
             "opening_positions": [{"listing_id": LISTING, "quantity": "2", "cost_basis": None, "acquired_on": None}],
             "opening_cash": {"currency": "USD", "amount": "20"}}
    value.update(changes)
    return value


def archive_for(root, operation, origin=TEST_ORIGIN, *, revision=None, issued=None, generation=1):
    """A stored bundle as `rw_archive` returns it, built in memory. The envelope and the stored request carry the raw-local sentinels."""
    response = {"portfolio_id": str(root), "as_of": "2026-01-05", "persisted": True, "reporting_currency": "USD", "synthetic": origin["synthetic"],
                "origin": origin, "labels": {}, "name": "invented probe root", "operation_id": str(operation), "revision_id": str(revision or uuid.uuid4()),
                "ledger_version": 2, "opening_positions": [], "opening_cash": {}}
    issued_bytes = canonical_json(issued if issued is not None else {"metrics": [], "state": "INSUFFICIENT_DATA"}).encode()
    response_bytes = canonical_json(response).encode()
    envelope = canonical_json({"schema": "invented.envelope/1", "generation": generation, "raw_payload_path": PATH_SENTINEL, "raw_vendor_text": RAW_SENTINEL}).encode()
    return Archive(issued_bytes, response_bytes, envelope, sha(issued_bytes), sha(response_bytes), uuid.UUID(response["revision_id"]), 2)


class FakeConnection:
    closed = False

    def close(self):
        self.closed = True


class FakeService:
    """Records every call by name. `roots` maps an owner to the (root, context, generation) triples `roots_of` returns."""

    def __init__(self):
        self.calls = []
        self.roots = {}
        self.archives = {}                 # (root, operation) -> Archive
        self.create_outcome = None         # what `create` returns; None builds a `Created` from the intent
        self.read_outcome = None
        self.reproduce_outcome = None
        self.list_entries = None

    def _record(self, name, **kw):
        self.calls.append((name, kw))

    def names(self):
        return [name for name, _ in self.calls]

    def roots_of(self, conn, *, owner):
        self._record("roots_of", owner=owner)
        return real_tails.Done(list(self.roots.get(owner, [])))

    def list_roots(self, conn, *, owner):
        self._record("list_roots", owner=owner)
        return real_tails.Done(self.list_entries if self.list_entries is not None else [])

    def create(self, conn, *, owner, body, generation, link):
        self._record("create", owner=owner, body=body, generation=generation, link=link)
        if self.create_outcome is not None:
            return self.create_outcome
        operation = uuid.UUID(body["operation_id"])
        root = uuid.uuid5(owner, "root:" + str(operation))
        archive = archive_for(root, operation)
        self.archives[(root, operation)] = archive
        return Created(root, operation, archive, False)

    def archive_read(self, conn, *, owner, root, operation_id, context_id, generation):
        self._record("archive_read", owner=owner, root=root, operation_id=operation_id, context_id=context_id, generation=generation)
        if self.read_outcome is not None:
            return self.read_outcome
        archive = self.archives.get((root, operation_id))
        if archive is None:
            return real_tails.Refused("RW_NOT_FOUND")
        return real_tails.Done(archive)

    def reproduce(self, conn, *, owner, root, operation_id, context_id, generation):
        self._record("reproduce", owner=owner, root=root, operation_id=operation_id, context_id=context_id, generation=generation)
        if self.reproduce_outcome is not None:
            return self.reproduce_outcome
        archive = self.archives.get((root, operation_id))
        if archive is None:
            return real_tails.Refused("RW_NOT_FOUND")
        return real_tails.Done(Reproduction("REPRODUCED", "", archive.issued_sha256, archive.origin))


class FakeAccounts:
    """The methods the auth routes call, in memory: registration, credentials, sessions. No persistence, no database."""

    def __init__(self):
        self.users, self.sessions = {}, {}

    def rate_limit(self, action, peer, username):
        return None

    def register(self, username, password_hash):
        if username in self.users:
            raise AccountStoreError(409, "USERNAME_UNAVAILABLE", "Username is unavailable")
        user_id = str(uuid.uuid4())
        self.users[username] = (user_id, password_hash)
        return {"user_id": user_id, "username": username}

    def credential(self, username):
        found = self.users.get(username)
        return None if found is None else ({"user_id": found[0], "username": username}, found[1])

    def start_session(self, user, lifetime):
        token = auth.new_token()
        self.sessions[auth.digest_token(token)] = user
        return token

    def session_user(self, token):
        return self.sessions.get(auth.digest_token(token))

    def logout(self, token):
        self.sessions.pop(auth.digest_token(token), None)


def build_app(service=None, accounts=None, *, pins=None, lineage_of=None):
    service = service or FakeService()
    accounts = accounts or FakeAccounts()
    pins = pins if pins is not None else {CONTEXT: ContextPin(CONTEXT, 3, ProvenanceLink("e" * 64, (), ()))}
    kw = {} if lineage_of is None else {"lineage_of": lineage_of}
    app = create_real_mode_app(service=service, contexts=pins, account_store=accounts, connect=FakeConnection, settings=auth.AuthSettings.local(),
                               origins=ORIGINS, **kw)
    return app, service, accounts


class Client:
    """A minimal ASGI client with a cookie jar. `request` returns (status, parsed body or raw bytes, headers)."""

    def __init__(self, app, peer="127.0.0.77"):
        """`peer` is the client address the app sees; the sign-up limit is per peer, so a module that signs up many users uses distinct peers."""
        self.app, self.cookies, self.csrf, self.peer = app, {}, None, peer

    async def _call(self, method, path, body, headers):
        raw = body if isinstance(body, bytes) else b"" if body is None else json.dumps(body).encode()
        sent, delivered = [], False

        async def receive():
            nonlocal delivered
            if delivered:
                return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": raw, "more_body": False}

        async def send(message):
            sent.append(message)
        target, _, query = path.partition("?")
        header_list = [(b"host", HOST.encode()), (b"origin", ORIGIN.encode())]
        if self.cookies:
            header_list.append((b"cookie", "; ".join("%s=%s" % kv for kv in self.cookies.items()).encode()))
        if method in ("POST", "PUT", "PATCH", "DELETE") or body is not None:
            header_list.append((b"content-type", b"application/json"))
        header_list += [(k.encode(), v.encode()) for k, v in headers.items()]
        await self.app(dict(type="http", asgi={"version": "3.0"}, http_version="1.1", method=method, scheme="http", path=target, raw_path=target.encode(),
                            query_string=query.encode(), root_path="", headers=header_list, client=(self.peer, 4242), server=("127.0.0.1", 8004)),
                       receive, send)
        start = next(m for m in sent if m["type"] == "http.response.start")
        content = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        out_headers = [(k.decode().lower(), v.decode()) for k, v in start["headers"]]
        for key, value in out_headers:
            if key == "set-cookie":
                name, _, rest = value.partition("=")
                token = rest.split(";", 1)[0]
                if token:
                    self.cookies[name] = token
        return start["status"], content, dict(out_headers)

    def request(self, method, path, body=None, *, csrf=True, headers=None):
        import asyncio
        extra = dict(headers or {})
        if csrf and method != "GET" and self.csrf:
            extra["x-finweb-csrf"] = self.csrf
        status, content, out = asyncio.run(self._call(method, path, body, extra))
        try:
            parsed = json.loads(content) if content else None
        except ValueError:
            parsed = content
        return status, parsed, content

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, {} if body is None else body, **kw)

    def sign_up(self, username):
        status, body, _ = self.get("/api/v1/auth/session")
        self.csrf = body["csrf_token"]
        status, body, _ = self.post("/api/v1/auth/register", {"username": username, "password": "invented-disposable-pass-" + username})
        assert status == 201, (status, body)
        self.csrf = body["csrf_token"]
        return uuid.UUID(body["user"]["user_id"])


def labels_of(origin):
    return {k: real_labels.root_labels(origin)[k] for k in ("origin_kind", "origin_statement", "holding_statement")}


NS = SimpleNamespace
