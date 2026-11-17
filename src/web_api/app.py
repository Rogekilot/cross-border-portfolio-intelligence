"""Thin versioned FastAPI boundary for the explicitly enabled local guest slice."""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, field_validator, model_validator

from insight_service.service import reproduce_insights
from marketdata.canonical import canonical_json
from web_api.synthetic import MODE, LIMITATIONS, SyntheticWorld

SCHEMA = "finweb.cp7/1"
DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,6})?\Z")
DEFAULT_ORIGINS = frozenset("http://" + host + ":" + port for host in ("127.0.0.1", "localhost")
                            for port in ("5173", "8000"))


def response(value, status=200):
    return Response(canonical_json(value), status_code=status, media_type="application/json",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


class Refusal(Exception):
    def __init__(self, status, code, detail):
        self.status, self.code, self.detail = status, code, detail


def refused(status, code, detail):
    return response({"schema_version": SCHEMA,
                     "error": {"code": code, "detail": detail, "state": "INSUFFICIENT_DATA"}}, status)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SessionRequest(StrictModel):
    mode: Literal["LOCAL_SYNTHETIC_GUEST"]


class PositionRequest(StrictModel):
    symbol: Literal["SYN-A", "SYN-B"]
    quantity: StrictStr

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value):
        if not DECIMAL.fullmatch(value) or not 0 < Decimal(value) <= Decimal("1000000"):
            raise ValueError("quantity must be an exact decimal string in (0,1000000], at most six decimal places")
        return value


class PortfolioRequest(StrictModel):
    name: StrictStr = Field(min_length=1, max_length=80)
    reporting_currency: Literal["USD", "CNY"]
    positions: list[PositionRequest] = Field(max_length=2)
    cash: StrictStr
    synthetic_acknowledged: StrictBool

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("name must contain visible text and no control characters")
        return value.strip()

    @field_validator("cash")
    @classmethod
    def valid_cash(cls, value):
        if not DECIMAL.fullmatch(value) or not 0 <= Decimal(value) <= Decimal("1000000000"):
            raise ValueError("cash must be an exact decimal string in [0,1000000000], at most six decimal places")
        return value

    @model_validator(mode="after")
    def valid_snapshot(self):
        if not self.synthetic_acknowledged:
            raise ValueError("explicit synthetic acknowledgement is required")
        if len({p.symbol for p in self.positions}) != len(self.positions):
            raise ValueError("duplicate synthetic symbol")
        if not self.positions and Decimal(self.cash) == 0:
            raise ValueError("at least one positive synthetic position or cash balance is required")
        return self


class ReproduceRequest(StrictModel):
    expected_result_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


@dataclass
class Session:
    created: float
    portfolios: dict = field(default_factory=dict)


class GuestRepository:
    """Bounded process-local capability isolation, not a saved account repository."""
    def __init__(self, clock=time.monotonic, max_sessions=32, max_portfolios=8, ttl=3600):
        self.clock, self.max_sessions, self.max_portfolios, self.ttl = clock, max_sessions, max_portfolios, ttl
        self.sessions = {}
        self.lock = threading.RLock()

    def _prune(self):
        now = self.clock()
        self.sessions = {key: value for key, value in self.sessions.items() if now - value.created < self.ttl}

    def create_session(self):
        with self.lock:
            self._prune()
            if len(self.sessions) >= self.max_sessions:
                raise Refusal(429, "GUEST_CAPACITY_REACHED", "Local guest session capacity reached; wait for expiry or restart the development process")
            token = secrets.token_urlsafe(32)
            self.sessions[token] = Session(self.clock())
            return token

    def session(self, token):
        with self.lock:
            self._prune()
            if not isinstance(token, str) or len(token) > 100 or token not in self.sessions:
                raise Refusal(401, "GUEST_SESSION_REQUIRED", "A valid unexpired local guest session capability is required")
            return self.sessions[token]

    def create(self, token, make):
        with self.lock:
            session = self.session(token)
            if len(session.portfolios) >= self.max_portfolios:
                raise Refusal(429, "GUEST_CAPACITY_REACHED", "Per-session synthetic portfolio limit reached")
            ident = str(uuid.uuid4())
            value = make(uuid.UUID(ident))
            session.portfolios[ident] = value
            return ident, value

    def get(self, token, ident):
        with self.lock:
            value = self.session(token).portfolios.get(ident)
            if value is None:
                raise Refusal(404, "NOT_FOUND", "Portfolio or packet is not available in this guest session")
            return value


class LocalBoundary:
    """No cross-origin CORS grants; validate loopback Host and actual body size."""
    def __init__(self, app, *, allowed_origins, max_body=32768):
        self.app, self.allowed_origins, self.max_body = app, allowed_origins, max_body

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.decode("latin1").lower(): value.decode("latin1") for key, value in scope["headers"]}
        host = headers.get("host", "")
        authority = re.fullmatch(r"(?:127\.0\.0\.1|localhost)(?::([1-9][0-9]{0,4}))?", host)
        host_count = sum(key.lower() == b"host" for key, _ in scope["headers"])
        if authority is None or host_count != 1 or (authority.group(1) is not None and int(authority.group(1)) > 65535):
            await refused(403, "FORBIDDEN_HOST", "This increment accepts loopback development hosts only")(scope, receive, send)
            return
        origin = headers.get("origin")
        if origin is not None and origin not in self.allowed_origins:
            await refused(403, "FORBIDDEN_ORIGIN", "Request origin is not an explicitly configured local development origin")(scope, receive, send)
            return
        if headers.get("sec-fetch-site") == "cross-site":
            await refused(403, "FORBIDDEN_ORIGIN", "Cross-site requests are not supported")(scope, receive, send)
            return
        if scope["method"] in ("POST", "PUT", "PATCH"):
            if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                await refused(400, "JSON_REQUIRED", "Mutation requests require application/json")(scope, receive, send)
                return
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > self.max_body:
                    await refused(413, "REQUEST_TOO_LARGE", "JSON request exceeds the local guest body limit")(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break
            delivered = False
            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()
            await self.app(scope, replay, send)
        else:
            await self.app(scope, receive, send)


def create_app(*, enable_local_guest=False, repository=None, allowed_origins=DEFAULT_ORIGINS,
               account_store=None, auth_settings=None, enable_saved_synthetic=False, guarded_profile=None):
    """Default closed; local launcher must explicitly opt into fictional guest data."""
    app = FastAPI(title="Fin Web CP7 local guest", docs_url=None, redoc_url=None, openapi_url=None)
    repo = GuestRepository() if repository is None else repository
    if guarded_profile is not None and (account_store is not guarded_profile.store or not enable_saved_synthetic or auth_settings is None):
        raise ValueError("An explicit guarded account profile and auth configuration are required")
    world = guarded_profile.world if guarded_profile is not None else SyntheticWorld() if enable_local_guest else None
    app.add_middleware(LocalBoundary, allowed_origins=frozenset(allowed_origins))

    @app.exception_handler(Refusal)
    async def refusal_handler(request, error):
        return refused(error.status, error.code, error.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, error):
        # Do not reflect raw input/capabilities or framework exception internals.
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
        return refused(422, "INVALID_REQUEST", "Invalid or unsupported request fields: " + ", ".join(fields))

    def enabled():
        if guarded_profile is not None:
            raise Refusal(503, "F3_GUARDED_SAVED_ONLY", "This guarded fictional profile requires an authenticated saved account")
        if world is None:
            raise Refusal(503, "LOCAL_GUEST_DISABLED", "Explicit local synthetic guest enablement is required")

    def token_of(request):
        enabled()
        return request.headers.get("x-finweb-session")

    def packet_of(request, portfolio_id, insight_id):
        item = repo.get(token_of(request), portfolio_id)
        matches = [packet for packet in item.insights.packets if packet.insight_id == insight_id]
        if not matches:
            raise Refusal(404, "NOT_FOUND", "Portfolio or packet is not available in this guest session")
        return item, matches[0]

    @app.get("/api/v1/capabilities")
    def capabilities():
        if guarded_profile is not None:
            return response({"schema_version": SCHEMA, **world.capabilities(), "guarded_profile": guarded_profile.capabilities()})
        enabled()
        return response({"schema_version": SCHEMA, **world.capabilities()})

    @app.post("/api/v1/guest-sessions")
    def new_session(body: SessionRequest):
        enabled()
        return response({"schema_version": SCHEMA, "session_token": repo.create_session(), "mode": MODE,
                         "limitations": list(LIMITATIONS)}, 201)

    @app.post("/api/v1/guest-portfolios")
    def new_portfolio(body: PortfolioRequest, request: Request):
        token = token_of(request)
        repo.session(token)
        if body.reporting_currency != "USD":
            raise Refusal(422, "FX_PATH_UNAVAILABLE", "The local synthetic fixture supports USD only; no CNY FX path is admitted")
        try:
            _, item = repo.create(token, lambda ident: world.create(ident, body.model_dump()))
        except ValueError:
            raise Refusal(503, "DETERMINISTIC_SOURCE_REFUSED", "The deterministic engine refused the local synthetic source") from None
        return response(item.snapshot(), 201)

    @app.get("/api/v1/guest-portfolios/{portfolio_id}")
    def get_portfolio(portfolio_id: str, request: Request):
        return response(repo.get(token_of(request), portfolio_id).snapshot())

    @app.get("/api/v1/guest-portfolios/{portfolio_id}/packets/{insight_id}")
    def get_packet(portfolio_id: str, insight_id: str, request: Request):
        item, packet = packet_of(request, portfolio_id, insight_id)
        return response({"schema_version": SCHEMA, "portfolio_id": portfolio_id, "synthetic": True,
                         "packet": packet.to_obj(), "result_digest": item.insights.result_digest})

    @app.post("/api/v1/guest-portfolios/{portfolio_id}/packets/{insight_id}/reproduce")
    def reproduce_packet(portfolio_id: str, insight_id: str, body: ReproduceRequest, request: Request):
        item, _ = packet_of(request, portfolio_id, insight_id)
        report = reproduce_insights(item.insights, body.expected_result_digest, (item.source,), allow_synthetic=True)
        return response({"schema_version": SCHEMA, "portfolio_id": portfolio_id, "insight_id": insight_id,
                         "status": report.status, "detail": report.detail, "expected_result_digest": body.expected_result_digest,
                         "actual_result_digest": None if report.result is None else report.result.result_digest, "synthetic": True})

    from web_api.account_routes import install_account_routes
    install_account_routes(app, store=account_store,
        world=guarded_profile.world if guarded_profile is not None else SyntheticWorld() if enable_saved_synthetic else None, settings=auth_settings,
        allowed_origins=frozenset(allowed_origins), guarded_profile=guarded_profile)
    return app
