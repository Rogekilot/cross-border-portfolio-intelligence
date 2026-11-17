"""Complete opt-in saved route surface; never falls through legacy stores."""
from __future__ import annotations

import datetime as dt
import json
from typing import Literal

import psycopg
from fastapi import Request
from fastapi.responses import Response
from pydantic import StrictStr, field_validator

from marketdata.canonical import canonical_json
from persistence.guarded_http_store import GuardedHttpStore, MAX_HTTP_BYTES, uid
from persistence.guarded_workspace_context import GuardedWorkspaceError
from web_api.app import StrictModel, PortfolioRequest, Refusal, response, refused
from web_api.csv_requests import ParseCsvRequest, ImportProposal, CommitCsvRequest
from web_api.workspace_requests import LedgerCommand, PreferencesCommand, date_text, uuid_text


class GuardedCreation(PortfolioRequest):
    mode: Literal["LOCAL_SYNTHETIC_ACCOUNT"]
    operation_id: StrictStr
    opening_date: StrictStr
    _operation = field_validator("operation_id")(uuid_text)
    _opening = field_validator("opening_date")(date_text)


class EmptyGuardedRequest(StrictModel):
    pass


def error_status(code):
    if code in ("F2_NOT_FOUND", "NOT_FOUND"):
        return 404
    if "IDEMPOTENCY" in code or code == "STALE_REVISION":
        return 409
    if code == "F2_RIGHT_REFUSED":
        return 403
    if code in ("F2_GENERATION_DIFFERS", "F2_MODE_HOLD", "F2_EXPIRY_HOLD"):
        return 423
    if code in ("F2_SHAPE", "F3_SHAPE", "F2_ONE_DATE_PROFILE", "F2_COMMAND_CAP"):
        return 422
    if code in ("F3_CSV_REPORT_HOLDINGS_UNSUPPORTED", "CSV_REPORT_CURSOR"):
        return 422
    if code == "F3_CSV_REPORT_CAPACITY":
        return 429
    return 503


def bounded_response(value, status=200):
    raw = canonical_json(value).encode("utf8")
    if len(raw) > MAX_HTTP_BYTES:
        raise Refusal(503, "F3_RESPONSE_BOUND", "The complete fictional response exceeds the local transport bound")
    return Response(raw, status_code=status, media_type="application/json", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


def install_guarded_routes(app, *, profile, authenticated):
    facade = GuardedHttpStore(profile)

    @app.exception_handler(GuardedWorkspaceError)
    async def guarded_error(request, error):
        return refused(error_status(error.code), error.code, "The current fictional operation or evidence boundary refused this request")

    @app.exception_handler(psycopg.Error)
    async def database_error(request, error):
        code = str(error).split("\n", 1)[0] if isinstance(error, psycopg.errors.RaiseException) else "F3_STORAGE_UNAVAILABLE"
        if not (code.startswith("F2_") or code.startswith("F3_")) or not code.replace("_", "").isalnum() or len(code) > 80:
            code = "F3_STORAGE_UNAVAILABLE"
        return refused(error_status(code), code, "Current fictional storage or authority is unavailable; no outcome is substituted")

    def owner(request, mutation=False):
        return authenticated(request, mutation=mutation)[1]["user_id"]

    def outcome(value):
        payload, status = value
        return bounded_response(payload, status)

    @app.get("/api/v1/portfolios")
    def portfolios(request: Request):
        return bounded_response(facade.list(owner(request)))

    @app.post("/api/v1/portfolios")
    def create(body: GuardedCreation, request: Request):
        who = owner(request, True)
        if body.reporting_currency != "USD":
            raise Refusal(422, "FX_PATH_UNAVAILABLE", "Only the explicitly fictional USD source is available")
        if dt.date.fromisoformat(body.opening_date) > profile.world.as_of:
            raise Refusal(422, "INVALID_OPENING_DATE", "Opening facts cannot follow the fictional valuation date")
        data = body.model_dump()
        op = data.pop("operation_id")
        return outcome(facade.create(who, op, data))

    @app.get("/api/v1/creation-operations/{operation_id}/reconcile")
    def creation_reconcile(operation_id: str, request: Request):
        return outcome(facade.reconcile(owner(request), operation_id, creation=True))

    @app.get("/api/v1/portfolios/{portfolio_id}")
    def snapshot(portfolio_id: str, request: Request, revision_id: str | None = None):
        return bounded_response(facade.read(owner(request), portfolio_id, revision=revision_id))

    @app.get("/api/v1/portfolios/{portfolio_id}/workspace")
    def workspace(portfolio_id: str, request: Request, revision_id: str | None = None):
        return bounded_response(facade.read(owner(request), portfolio_id, revision=revision_id, workspace_only=True))

    @app.post("/api/v1/portfolios/{portfolio_id}/ledger-commands/preview")
    def ledger_preview(portfolio_id: str, body: LedgerCommand, request: Request):
        return outcome(facade.preview(owner(request, True), portfolio_id, body.model_dump()))

    @app.post("/api/v1/portfolios/{portfolio_id}/ledger-commands")
    def ledger(portfolio_id: str, body: LedgerCommand, request: Request):
        return outcome(facade.execute(owner(request, True), portfolio_id, body.operation_id, "LEDGER", body.model_dump()))

    @app.post("/api/v1/portfolios/{portfolio_id}/preferences")
    def preferences(portfolio_id: str, body: PreferencesCommand, request: Request):
        return outcome(facade.execute(owner(request, True), portfolio_id, body.operation_id, "PREFERENCES", body.model_dump()))

    @app.post("/api/v1/portfolios/{portfolio_id}/imports/parse")
    def parse(portfolio_id: str, body: ParseCsvRequest, request: Request):
        return bounded_response(facade.csv_read(owner(request, True), portfolio_id, "parse", body=body.model_dump()))

    @app.post("/api/v1/portfolios/{portfolio_id}/imports/preview")
    def csv_preview(portfolio_id: str, body: ImportProposal, request: Request):
        return outcome(facade.preview(owner(request, True), portfolio_id, body.model_dump(), csv=True))

    @app.post("/api/v1/portfolios/{portfolio_id}/imports/commit")
    def csv_commit(portfolio_id: str, body: CommitCsvRequest, request: Request):
        return outcome(facade.execute(owner(request, True), portfolio_id, body.proposal.operation_id, "CSV", body.proposal.model_dump(), body.preview_receipt))

    @app.get("/api/v1/portfolios/{portfolio_id}/imports")
    def reports(portfolio_id: str, request: Request, cursor: str | None = None):
        return bounded_response(facade.csv_read(owner(request), portfolio_id, "list", cursor=cursor))

    @app.post("/api/v1/portfolios/{portfolio_id}/import-report-operations")
    def report_commit(portfolio_id: str, body: CommitCsvRequest, request: Request):
        return outcome(facade.reports.commit(owner(request, True), portfolio_id, body.proposal.model_dump(), body.preview_receipt))

    @app.get("/api/v1/portfolios/{portfolio_id}/import-report-operations/{operation_id}")
    def report_archive(portfolio_id: str, operation_id: str, request: Request):
        return bounded_response(facade.reports.archive(owner(request), portfolio_id, operation_id))

    @app.get("/api/v1/portfolios/{portfolio_id}/import-report-operations/{operation_id}/reconcile")
    def report_reconcile(portfolio_id: str, operation_id: str, request: Request):
        return outcome(facade.reports.archive(owner(request), portfolio_id, operation_id, reconcile=True))

    @app.get("/api/v1/portfolios/{portfolio_id}/import-report-operations/{operation_id}/export")
    def report_operation_export(portfolio_id: str, operation_id: str, request: Request):
        value = facade.reports.archive(owner(request), portfolio_id, operation_id, export=True)
        raw = canonical_json(value)
        if len(raw.encode("utf8")) > MAX_HTTP_BYTES:
            raise Refusal(503, "F3_RESPONSE_BOUND", "Complete report archive exceeds its transport bound")
        return Response(raw, media_type="application/json", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'attachment; filename="finweb-csv-report-' + value["report_id"] + '.json"',
            "X-Finweb-Portfolio-Id": value["portfolio_id"], "X-Finweb-Operation-Id": value["operation_id"], "X-Finweb-Report-Id": value["report_id"]})

    @app.get("/api/v1/portfolios/{portfolio_id}/imports/{report_id}")
    def report(portfolio_id: str, report_id: str, request: Request):
        return bounded_response(facade.csv_read(owner(request), portfolio_id, "get", report=report_id))

    def download(root, identity, op, text, media, extension, identity_kind):
        if len(text.encode("utf8")) > MAX_HTTP_BYTES:
            raise Refusal(503, "F3_RESPONSE_BOUND", "Complete export exceeds its transport bound")
        return Response(text, media_type=media, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'attachment; filename="finweb-' + identity_kind + '-' + str(uid(identity)) + '.' + extension + '"',
            "X-Finweb-Portfolio-Id": str(uid(root)), "X-Finweb-Operation-Id": str(uid(op)),
            "X-Finweb-" + identity_kind.title() + "-Id": str(uid(identity))})

    @app.get("/api/v1/portfolios/{portfolio_id}/imports/{report_id}/export")
    def report_export(portfolio_id: str, report_id: str, request: Request, format: str = "json"):
        who = owner(request)
        if format not in ("json", "csv"):
            raise Refusal(422, "CSV_EXPORT_FORMAT", "Choose json or csv")
        (text, media), op = facade.csv_read(who, portfolio_id, "export_report", report=report_id, format=format)
        result = download(portfolio_id, report_id, op, text, media, format, "report")
        result.headers["X-Finweb-Report-Id"] = str(uid(report_id))
        return result

    @app.get("/api/v1/portfolios/{portfolio_id}/exports/{kind}")
    def export(portfolio_id: str, kind: str, request: Request, revision_id: str, format: str = "json"):
        who = owner(request)
        if kind not in ("holdings", "transactions") or format not in ("json", "csv"):
            raise Refusal(422, "CSV_EXPORT_FORMAT", "Choose holdings/transactions and json/csv")
        (text, media), op = facade.csv_read(who, portfolio_id, "export_portfolio", revision=revision_id, kind=kind, format=format)
        return download(portfolio_id, revision_id, op, text, media, format, "revision")

    @app.get("/api/v1/portfolios/{portfolio_id}/operations/{operation_id}")
    def archive(portfolio_id: str, operation_id: str, request: Request):
        return bounded_response(facade.archive(owner(request), portfolio_id, operation_id))

    @app.get("/api/v1/portfolios/{portfolio_id}/operations/{operation_id}/export")
    def archive_export(portfolio_id: str, operation_id: str, request: Request):
        value = facade.archive(owner(request), portfolio_id, operation_id, export=True)
        return download(portfolio_id, operation_id, operation_id, canonical_json(value), "application/json", "json", "operation")

    @app.post("/api/v1/portfolios/{portfolio_id}/operations/{operation_id}/reproduce")
    def reproduce(portfolio_id: str, operation_id: str, body: EmptyGuardedRequest, request: Request):
        return bounded_response(facade.reproduce(owner(request, True), portfolio_id, operation_id))

    @app.get("/api/v1/portfolios/{portfolio_id}/operations/{operation_id}/reconcile")
    def reconcile(portfolio_id: str, operation_id: str, request: Request):
        return outcome(facade.reconcile(owner(request), operation_id, portfolio_id))

    @app.api_route("/api/v1/portfolios/{portfolio_id}/packets/{path:path}", methods=["GET", "POST"])
    @app.api_route("/api/v1/portfolios/{portfolio_id}/analytics/{path:path}", methods=["GET", "POST"])
    @app.api_route("/api/v1/real-source-contexts{path:path}", methods=["GET", "POST"])
    @app.api_route("/api/v1/real-workspaces{path:path}", methods=["GET", "POST"])
    @app.api_route("/api/v1/real-portfolios{path:path}", methods=["GET", "POST"])
    @app.api_route("/api/v1/real-workspace-contract{path:path}", methods=["GET", "POST"])
    @app.api_route("/api/v1/real-workspace-intents{path:path}", methods=["GET", "POST"])
    def unsupported(request: Request, path: str, portfolio_id: str | None = None):
        owner(request, request.method == "POST")
        raise Refusal(503, "F3_GUARDED_UNSUPPORTED", "This feature is unavailable in the fictional guarded CP5 profile")
