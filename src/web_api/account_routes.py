"""Cookie/CSRF authenticated, owner-scoped CP7-B HTTP adapter."""
from __future__ import annotations

import secrets
import re
from typing import Literal

import psycopg
from fastapi import Request
from pydantic import StrictStr, field_validator

from insight_service.service import reproduce_insights
from persistence.web_account_store import AccountStoreError
from web_api import auth
from web_api.app import PortfolioRequest, Refusal, ReproduceRequest, SCHEMA, StrictModel, response
from web_api.workspace_requests import LedgerCommand, PreferencesCommand

SESSION_COOKIE = "finweb_session"
BOOTSTRAP_COOKIE = "finweb_csrf"


class Credentials(StrictModel):
    username: StrictStr
    password: StrictStr

    @field_validator("username")
    @classmethod
    def valid_username(cls, value):
        return auth.username(value)

    @field_validator("password")
    @classmethod
    def valid_password(cls, value):
        return auth.password(value)


class EmptyRequest(StrictModel):
    pass


class SavedPortfolioRequest(PortfolioRequest):
    mode: Literal["LOCAL_SYNTHETIC_ACCOUNT"]


def install_account_routes(app, *, store, world, settings, allowed_origins, guarded_profile=None, auth_only=False, cookie_path="/api/v1",
                         session_cookie=SESSION_COOKIE, bootstrap_cookie=BOOTSTRAP_COOKIE):
    """`auth_only=True` (F1 R7, the real-mode app): install the session, register, login and logout routes ONLY and return the `authenticated`
    check for the caller's own routes. No saved-portfolio, guarded, CSV, analytics, E1 or E5 route is installed, and `world` is not needed.
    `cookie_path` is the path scope of the two cookies; the real-mode app's routes are not under the default scope, so it passes the wider `/api`."""
    enabled = store is not None and settings is not None and (world is not None or auth_only)

    @app.exception_handler(AccountStoreError)
    async def account_error(request, error):
        from web_api.app import refused
        return refused(error.status, error.code, error.detail)

    @app.exception_handler(auth.PasswordCapacityError)
    async def password_capacity(request, error):
        from web_api.app import refused
        return refused(429, "AUTH_BUSY", "Password verification capacity reached; retry shortly")

    def database(call):
        try:
            return call()
        except psycopg.Error:
            raise Refusal(503, "ACCOUNT_STORAGE_UNAVAILABLE", "Account storage is unavailable; no saved result is substituted") from None

    def boundary(request, *, mutation=False):
        if not enabled:
            raise Refusal(503, "ACCOUNT_MODE_DISABLED", "Explicit PostgreSQL account and synthetic sandbox configuration is required")
        if not settings.local_development and request.scope["scheme"] != "https":
            raise Refusal(403, "HTTPS_REQUIRED", "Account operations require HTTPS")
        if mutation:
            origins = request.headers.getlist("origin")
            if len(origins) != 1 or origins[0] not in allowed_origins:
                raise Refusal(403, "CSRF_REJECTED", "An explicitly configured request origin and CSRF token are required")

    def session(request):
        boundary(request)
        token = request.cookies.get(session_cookie)
        user = database(lambda: store.session_user(token)) if auth.valid_token(token) else None
        return token, user

    def csrf(request, token):
        boundary(request, mutation=True)
        candidates = request.headers.getlist("x-finweb-csrf")
        if (not auth.valid_token(token) or len(candidates) != 1 or re.fullmatch(r"[0-9a-f]{64}", candidates[0]) is None
                or not secrets.compare_digest(candidates[0], auth.csrf_token(token))):
            raise Refusal(403, "CSRF_REJECTED", "An explicitly configured request origin and CSRF token are required")

    def authenticated(request, *, mutation=False):
        token, user = session(request)
        if user is None:
            raise Refusal(401, "AUTHENTICATION_REQUIRED", "A valid unexpired account session is required")
        if mutation:
            csrf(request, token)
        return token, user

    def cookie(result, key, value, seconds):
        result.set_cookie(key, value, max_age=seconds, httponly=True, secure=settings.secure_cookie,
                          samesite="strict", path=cookie_path)

    def state(request, user=None, token=None, *, status=200):
        bootstrap = token if user is not None else new_bootstrap(request)
        result = response({"schema_version": SCHEMA, "authenticated": user is not None,
                           "user": user, "csrf_token": auth.csrf_token(bootstrap),
                           **({"guarded_profile": guarded_profile.capabilities()} if guarded_profile is not None else {})}, status)
        if user is None:
            cookie(result, bootstrap_cookie, bootstrap, 900)
        else:
            cookie(result, session_cookie, token, settings.session_seconds)
            result.delete_cookie(bootstrap_cookie, path=cookie_path, secure=settings.secure_cookie,
                                 httponly=True, samesite="strict")
        return result

    def new_bootstrap(request):
        value = request.cookies.get(bootstrap_cookie)
        return value if auth.valid_token(value) else auth.new_token()

    def credentials_csrf(request):
        # Existing valid account sessions may also deliberately switch identities.
        old_token, old_user = session(request)
        token = old_token if old_user is not None else request.cookies.get(bootstrap_cookie)
        csrf(request, token)
        return old_token if old_user is not None else None

    def peer(request):
        # Never trust client-supplied forwarding/user identity headers.
        return request.client.host if request.client is not None else "unknown"

    def finish_login(request, user, old_token, status):
        if old_token:
            database(lambda: store.logout(old_token))
        token = database(lambda: store.start_session(user, settings.session_seconds))
        return state(request, user, token, status=status)

    @app.get("/api/v1/auth/session")
    def current_session(request: Request):
        token, user = session(request)
        return state(request, user, token)

    @app.post("/api/v1/auth/register")
    def register(body: Credentials, request: Request):
        old_token = credentials_csrf(request)
        database(lambda: store.rate_limit("register", peer(request), body.username))
        encoded = auth.password_hash(body.password)
        user = database(lambda: store.register(body.username, encoded))
        return finish_login(request, user, old_token, 201)

    @app.post("/api/v1/auth/login")
    def login(body: Credentials, request: Request):
        old_token = credentials_csrf(request)
        database(lambda: store.rate_limit("login", peer(request), body.username))
        credential = database(lambda: store.credential(body.username))
        if not auth.verify_password(body.password, None if credential is None else credential[1]):
            raise Refusal(401, "INVALID_CREDENTIALS", "Username or password is incorrect")
        return finish_login(request, credential[0], old_token, 200)

    @app.post("/api/v1/auth/logout")
    def logout(body: EmptyRequest, request: Request):
        token, _ = authenticated(request, mutation=True)
        database(lambda: store.logout(token))
        result = state(request)
        result.delete_cookie(session_cookie, path=cookie_path, secure=settings.secure_cookie,
                             httponly=True, samesite="strict")
        return result

    if auth_only:
        return authenticated

    if guarded_profile is not None:
        from web_api.guarded_routes import install_guarded_routes
        install_guarded_routes(app, profile=guarded_profile, authenticated=authenticated)
        return

    @app.get("/api/v1/portfolios")
    def list_portfolios(request: Request):
        _, user = authenticated(request)
        return response({"schema_version": SCHEMA,
                         "portfolios": database(lambda: store.list_portfolios(user["user_id"]))})

    @app.post("/api/v1/portfolios")
    def save_portfolio(body: SavedPortfolioRequest, request: Request):
        _, user = authenticated(request, mutation=True)
        if body.reporting_currency != "USD":
            raise Refusal(422, "FX_PATH_UNAVAILABLE", "The fictional saved sandbox supports USD only; no CNY FX path is admitted")
        try:
            item = database(lambda: store.create_portfolio(user["user_id"], body.model_dump(), world))
        except ValueError:
            raise Refusal(503, "DETERMINISTIC_SOURCE_REFUSED", "The deterministic engine refused the saved synthetic source") from None
        return response(item.snapshot(), 201)

    def owned(request, portfolio_id, revision_id=None):
        _, user = authenticated(request)
        return database(lambda: store.get_portfolio(user["user_id"], portfolio_id, world, revision_id=revision_id))

    def packet(request, portfolio_id, insight_id, revision_id=None):
        item = owned(request, portfolio_id, revision_id)
        found = next((p for p in item.insights.packets if p.insight_id == insight_id), None)
        if found is None:
            raise AccountStoreError(404, "NOT_FOUND", "Portfolio or packet is not available in this account")
        return item, found

    @app.get("/api/v1/portfolios/{portfolio_id}")
    def get_portfolio(portfolio_id: str, request: Request, revision_id: str | None = None):
        return response(owned(request, portfolio_id, revision_id).snapshot())

    @app.get("/api/v1/portfolios/{portfolio_id}/packets/{insight_id}")
    def get_packet(portfolio_id: str, insight_id: str, request: Request, revision_id: str | None = None):
        item, found = packet(request, portfolio_id, insight_id, revision_id)
        return response({"schema_version": SCHEMA, "portfolio_id": portfolio_id, "synthetic": True,
                         "packet": found.to_obj(), "result_digest": item.insights.result_digest})

    @app.post("/api/v1/portfolios/{portfolio_id}/packets/{insight_id}/reproduce")
    def reproduce_packet(portfolio_id: str, insight_id: str, body: ReproduceRequest, request: Request, revision_id: str | None = None):
        authenticated(request, mutation=True)
        item, _ = packet(request, portfolio_id, insight_id, revision_id)
        report = reproduce_insights(item.insights, body.expected_result_digest, (item.source,), policies=item.policies, allow_synthetic=True)
        return response({"schema_version": SCHEMA, "portfolio_id": portfolio_id, "insight_id": insight_id,
            "status": report.status, "detail": report.detail, "expected_result_digest": body.expected_result_digest,
            "actual_result_digest": None if report.result is None else report.result.result_digest, "synthetic": True})

    @app.get("/api/v1/portfolios/{portfolio_id}/workspace")
    def workspace(portfolio_id: str, request: Request, revision_id: str | None = None):
        _, user = authenticated(request)
        return response(database(lambda: store.workspace(user["user_id"], portfolio_id, world, revision_id=revision_id)))

    @app.post("/api/v1/portfolios/{portfolio_id}/ledger-commands/preview")
    def preview_ledger(portfolio_id: str, body: LedgerCommand, request: Request):
        _, user = authenticated(request, mutation=True)
        return response(database(lambda: store.command(user["user_id"], portfolio_id, body.model_dump(), world, preview=True)))

    @app.post("/api/v1/portfolios/{portfolio_id}/ledger-commands")
    def append_ledger(portfolio_id: str, body: LedgerCommand, request: Request):
        _, user = authenticated(request, mutation=True)
        return response(database(lambda: store.command(user["user_id"], portfolio_id, body.model_dump(), world)),201)

    @app.post("/api/v1/portfolios/{portfolio_id}/preferences")
    def preferences(portfolio_id: str, body: PreferencesCommand, request: Request):
        _, user = authenticated(request, mutation=True)
        return response(database(lambda: store.command(user["user_id"], portfolio_id, body.model_dump(), world, preferences=True)),201)

    from web_api.csv_routes import install_csv_routes
    install_csv_routes(app,store=store,world=world,authenticated=authenticated,database=database)
    from web_api.analytics_routes import install_analytics_routes
    install_analytics_routes(app,store=store,world=world,authenticated=authenticated,database=database)
    from web_api.real_routes import install_real_source_routes
    install_real_source_routes(app,authenticated=authenticated,database=database)
    from web_api.real_workspace_routes import install_real_workspace_routes
    install_real_workspace_routes(app,authenticated=authenticated)
