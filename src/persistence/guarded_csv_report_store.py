"""F3 zero-import CSV report operations: real READONLY lease, explicit CREATE, no financial bundle."""
from __future__ import annotations

import base64
from contextlib import contextmanager
from copy import deepcopy
import datetime as dt
import hashlib
import hmac
import json
from pathlib import Path
import re
import uuid

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from marketdata.canonical import canonical_json
from persistence.guarded_workspace_context import GuardedWorkspaceError, identifier, require_idle, transaction_identity
from persistence.guarded_workspace_store import GuardedWorkspaceStore, UnknownWorkspaceResult
from persistence.web_account_store import AccountStoreError
from persistence.web_csv_store import REPORT_FIELDS, protected_csv

PROFILE = "F3_FICTIONAL_CP5"
SCHEMA = "finweb.guarded_csv_report/1"
COLUMNS = ("owner_id", "operation_id", "root_id", "context_id", "commit_generation", "command_sha256",
    "request_sha256", "proposal_sha256", "preview_receipt_sha256", "base_revision_id", "base_operation_id",
    "base_ledger_pin", "report_id", "response", "response_sha256", "envelope", "envelope_sha256",
    "committed_at", "backend_pid", "xid")
ENVELOPE_KEYS = set("schema profile synthetic operation_kind owner_id portfolio_id operation_id report_id context_id commit_generation base_revision_id base_operation_id base_ledger_pin request_sha256 proposal_sha256 preview_receipt_sha256 response_sha256 report_status created_at".split())


def encoded(value):
    return canonical_json(value).encode("utf8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fail(code="F3_CSV_REPORT_ARCHIVE_DIFFERS", status=503):
    raise AccountStoreError(status, code, "The exact fictional report operation or its evidence is unavailable")


def query(conn, schema, name, params):
    return conn.execute(sql.SQL("SELECT * FROM {}.{}(" + ",".join(["%s"] * len(params)) + ")").format(
        sql.Identifier(schema), sql.Identifier(name)), params)


def _definitions(conn, schema):
    return conn.execute("SELECT p.oid,pg_get_functiondef(p.oid),p.proacl::text,p.proowner,p.prosecdef,p.proconfig "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND p.proname LIKE 'gw_%%' ORDER BY p.oid", (schema,)).fetchall()


def install_guarded_csv_report(conn, *, schema, executor_role):
    schema, executor_role = identifier(schema), identifier(executor_role)
    require_idle(conn)
    row = conn.execute("SELECT n.nspowner=r.oid,r.rolcanlogin FROM pg_namespace n JOIN pg_roles r ON r.rolname=current_user WHERE n.nspname=%s", (schema,)).fetchone()
    if row != (True, False):
        raise GuardedWorkspaceError("F3_INSTALL_OWNER_REQUIRED")
    frozen = Path(__file__).with_name("guarded_workspace_v1.sql").read_bytes()
    if digest(frozen) != "9c5733a9b9760952cce106a6a90dfadea44342a5235dcc233f4bc9e927e5f423":
        raise GuardedWorkspaceError("F3_POLICY_TEMPLATE_DIFFERS")
    if conn.execute("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND p.proname LIKE 'gh_csv_report_%%'", (schema,)).fetchone() != (0,):
        raise GuardedWorkspaceError("F3_CSV_REPORT_ALREADY_INSTALLED")
    before = _definitions(conn, schema)
    if not before or conn.execute("SELECT to_regprocedure(%s) IS NOT NULL", (schema + ".gh_head(text)",)).fetchone() != (True,):
        raise GuardedWorkspaceError("F3_INSTALL_FRESH_F2_REQUIRED")
    body = Path(__file__).with_name("guarded_csv_report_v1.sql").read_text("utf8").replace("__CR_SCHEMA__", '"' + schema + '"').replace("__CR_EXECUTOR__", '"' + executor_role + '"')
    with conn.transaction():
        conn.execute(body, prepare=False)
        if _definitions(conn, schema) != before:
            raise GuardedWorkspaceError("F3_CSV_REPORT_F2_CHANGED")


class ReportAwareWorkspaceStore(GuardedWorkspaceStore):
    """Only metadata namespace checks; the actual F2 staging/locks remain authoritative."""
    def _query(self, conn, name, params=(), *, columns="*"):
        if name == "gw_precheck":
            query(conn, self.schema, "gh_csv_report_precheck", params[:2]).fetchone()
        return super()._query(conn, name, params, columns=columns)


def command_bytes(owner, root, context, proposal, receipt):
    return encoded(dict(schema="finweb.f3.csv-report-command/1", owner_id=str(owner), root_id=str(root),
        context_id=context, kind="CSV_REPORT_ONLY", request_sha256=digest(encoded(dict(proposal=proposal, preview_receipt=receipt)))))


def final_report(report, root, op, created_at):
    result = deepcopy(report)
    if result["proposal"]["kind"] != "TRANSACTIONS":
        fail("F3_CSV_REPORT_HOLDINGS_UNSUPPORTED", 422)
    issues = [issue["code"] for row in result["rows"] for issue in row["errors"]] + [issue["code"] for issue in result["batch_errors"]]
    conflict = next((code for code in issues if code in ("SOURCE_KEY_CONFLICT", "SOURCE_SNAPSHOT_CONFLICT")), None)
    if conflict:
        fail(conflict, 409)
    if result["counts"]["ready"] and not result["counts"]["quarantined"] and not result["batch_errors"]:
        fail("F3_CSV_REPORT_FINANCIAL_REQUIRED", 409)
    result.update(report_id=str(uuid.uuid5(root, "f3-csv-report:" + str(op))), persisted=True,
        revision_id=None, created_at=created_at,
        status="ALREADY_IMPORTED" if not result["batch_errors"] and not result["counts"]["quarantined"] and result["counts"]["already_imported"] else "REPORT_ONLY")
    result["counts"]["imported"] = 0
    for row in result["rows"]:
        if row["disposition"] != "ALREADY_IMPORTED":
            row["event_id"] = None
    return result


class GuardedCsvReportStore:
    def __init__(self, facade):
        self.facade, self.profile, self.schema = facade, facade.profile, facade.schema

    @staticmethod
    def path(root, op):
        return "/api/v1/portfolios/" + str(root) + "/import-report-operations/" + str(op)

    def unknown(self, root, op):
        return dict(schema=SCHEMA, profile=PROFILE, disposition="UNKNOWN", synthetic=True,
            portfolio_id=str(root), operation_id=str(op), reconcile_url=self.path(root, op) + "/reconcile")

    def committed(self, row):
        return dict(schema=SCHEMA, profile=PROFILE, disposition="REPORT_COMMITTED", synthetic=True,
            portfolio_id=str(row["root_id"]), operation_id=str(row["operation_id"]),
            base_revision_id=str(row["base_revision_id"]), report_id=str(row["report_id"]),
            response_json=bytes(row["response"]).decode("utf8"), response_sha256=row["response_sha256"],
            archive_url=self.path(row["root_id"], row["operation_id"]), reconcile_url=self.path(row["root_id"], row["operation_id"]) + "/reconcile")

    @staticmethod
    def _row(value):
        return None if value is None else dict(zip(COLUMNS, value))

    def _sql_commit(self, conn, command, response=None, envelope=None):
        return self._row(query(conn, self.schema, "gh_csv_report_commit", (command, response, envelope)).fetchone())

    @contextmanager
    def _lease(self, owner, root, op, command, *, acknowledge=False):
        from persistence.guarded_http_store import ArchivedWorkspaceProjection, ArchivedCsvProjection
        with self.profile.store.connect() as conn:
            require_idle(conn)
            core = self.facade._core(conn)
            with conn.transaction():
                scope = core._admit(conn, owner, root, op, digest(command), "ARCHIVE_READ")
                workspace = ArchivedWorkspaceProjection(self.facade, core, scope, owner)
                importer = ArchivedCsvProjection(self.facade, workspace)
                yield conn, core, scope, workspace, importer
            require_idle(conn)
            if acknowledge:
                self._after_commit_ack(conn)

    @staticmethod
    def _before_commit(conn):
        transaction_identity(conn)

    @staticmethod
    def _after_commit_ack(conn):
        require_idle(conn)

    def _verify(self, conn, core, scope, workspace, importer, row):
        if row is None:
            fail("NOT_FOUND", 404)
        try:
            raw, envelope = bytes(row["response"]), bytes(row["envelope"])
            value, env = json.loads(raw), json.loads(envelope)
            report = value["report"]
            if (set(value) != {"report", "workspace_result"} or value["workspace_result"] is not None
                    or set(env) != ENVELOPE_KEYS or set(report) != REPORT_FIELDS
                    or digest(raw) != row["response_sha256"] or encoded(value) != raw
                    or digest(envelope) != row["envelope_sha256"] or encoded(env) != envelope
                    or row["owner_id"] != scope.owner_id or row["root_id"] != scope.root_id or row["context_id"] != scope.context_id
                    or env["schema"] != "finweb.csv_report_envelope/1" or env["profile"] != PROFILE or env["synthetic"] is not True
                    or env["operation_kind"] != "CSV_REPORT_ONLY"):
                raise ValueError()
            bindings = dict(owner_id=str(row["owner_id"]), portfolio_id=str(row["root_id"]), operation_id=str(row["operation_id"]),
                report_id=str(row["report_id"]), context_id=row["context_id"], commit_generation=row["commit_generation"],
                base_revision_id=str(row["base_revision_id"]), base_operation_id=str(row["base_operation_id"]),
                base_ledger_pin=str(row["base_ledger_pin"]), request_sha256=row["request_sha256"], proposal_sha256=row["proposal_sha256"],
                preview_receipt_sha256=row["preview_receipt_sha256"], response_sha256=row["response_sha256"], report_status=report["status"],
                created_at=json.loads(canonical_json(row["committed_at"])))
            if any(env[key] != expected for key, expected in bindings.items()):
                raise ValueError()
            proposal = report["proposal"]
            expected_command = encoded(dict(schema="finweb.f3.csv-report-command/1", owner_id=str(row["owner_id"]), root_id=str(row["root_id"]),
                context_id=row["context_id"], kind="CSV_REPORT_ONLY", request_sha256=row["request_sha256"]))
            if (digest(expected_command) != row["command_sha256"] or digest(encoded(proposal)) != row["proposal_sha256"]
                    or proposal["operation_id"] != str(row["operation_id"]) or proposal["expected_revision_id"] != str(row["base_revision_id"])):
                raise ValueError()
            meta = self.facade._meta(conn, scope.owner_id, scope.root_id, rev=row["base_revision_id"])
            if meta[0] != row["base_operation_id"]:
                raise ValueError()
            core._archive(conn, scope.owner_id, meta[0])
            record = workspace._record(conn, str(scope.owner_id), scope.root_id, str(row["base_revision_id"]))
            workspace._item(conn, scope.root_id, record)
            if record["ledger_version"] != row["base_ledger_pin"]:
                raise ValueError()
            pin = row["base_ledger_pin"]
            class PinnedReportSources(type(importer)):
                def _source(self, connection, ident, key):
                    source = super()._source(connection, ident, key)
                    if source is None:
                        return None
                    if source[2] != "EVENT":
                        fail("F3_CSV_REPORT_SOURCE_DIFFERS")
                    event = connection.execute("SELECT ledger_seq FROM ledger_event WHERE event_id=%s AND account_id=%s", (source[6], source[5])).fetchone()
                    if event is None:
                        fail("F3_CSV_REPORT_SOURCE_DIFFERS")
                    return source if event[0] <= pin else None
            historical_importer = PinnedReportSources(self.facade, workspace)
            evaluated, _, _, _ = historical_importer._evaluate(conn, str(scope.owner_id), scope.root_id, proposal)
            # Only batch errors introduced by the recorded rollback simulation
            # are not recalculated on reads. Their immutable bytes stay bound.
            if not isinstance(report["batch_errors"], list) or any(set(issue) != {"code", "detail"} or not all(type(v) is str for v in issue.values()) for issue in report["batch_errors"]):
                raise ValueError()
            if any(issue not in report["batch_errors"] for issue in evaluated["batch_errors"]):
                raise ValueError()
            evaluated["batch_errors"] = report["batch_errors"]
            expected = final_report(evaluated, scope.root_id, row["operation_id"], env["created_at"])
            if expected != report or report["expected_revision_id"] != str(row["base_revision_id"]):
                raise ValueError()
            scope.assert_current(conn)
            return value
        except (KeyError, ValueError, TypeError, AttributeError):
            fail()

    def commit(self, owner, root, proposal, receipt):
        from persistence.guarded_http_store import uid
        owner, root, op = uid(owner), uid(root), uid(proposal["operation_id"])
        command = command_bytes(owner, root, self.profile.context_id, proposal, receipt)
        try:
            with self._lease(owner, root, op, command) as (conn, core, scope, workspace, importer):
                prior = self._sql_commit(conn, command)
                if prior is not None:
                    self._verify(conn, core, scope, workspace, importer, prior)
            if prior is not None:
                return self.committed(prior), 200
            if proposal["kind"] != "TRANSACTIONS":
                fail("F3_CSV_REPORT_HOLDINGS_UNSUPPORTED", 422)
            # Validate only for a new operation, after immutable replay lookup.
            expected_receipt = self.profile.core().csv._receipt(str(owner), root, proposal)
            if not hmac.compare_digest(receipt, expected_receipt):
                fail("CSV_PREVIEW_REQUIRED", 409)
            with self.profile.store.connect() as conn:
                core = self.facade._core(conn)
                preview = core.csv_preview(owner, root, proposal, connection=conn)
            if type(preview) is UnknownWorkspaceResult:
                return self.unknown(root, op), 202
            if preview["financial_preview"] is not None:
                fail("F3_CSV_REPORT_FINANCIAL_REQUIRED", 409)
            staged = None
            with self._lease(owner, root, op, command, acknowledge=True) as (conn, core, scope, workspace, importer):
                prior = self._sql_commit(conn, command)
                if prior is None:
                    record = workspace._record(conn, str(owner), root)
                    if str(record["revision_id"]) != proposal["expected_revision_id"]:
                        fail("STALE_REVISION", 409)
                    workspace._item(conn, root, record)
                    meta = self.facade._meta(conn, owner, root, rev=record["revision_id"])
                    evaluated, _, _, _ = importer._evaluate(conn, str(owner), root, proposal)
                    observed = deepcopy(preview["report"])
                    pure = deepcopy(evaluated)
                    for value in (observed, pure):
                        value.pop("status"); value.pop("batch_errors")
                    if observed != pure or any(issue not in preview["report"]["batch_errors"] for issue in evaluated["batch_errors"]):
                        fail("F3_CSV_REPORT_SOURCE_DIFFERS", 409)
                    now = json.loads(canonical_json(self.profile.store.clock()))
                    report = final_report(preview["report"], root, op, now)
                    response = encoded(dict(report=report, workspace_result=None))
                    env = dict(schema="finweb.csv_report_envelope/1", profile=PROFILE, synthetic=True, operation_kind="CSV_REPORT_ONLY",
                        owner_id=str(owner), portfolio_id=str(root), operation_id=str(op), report_id=report["report_id"], context_id=scope.context_id,
                        commit_generation=scope.generation, base_revision_id=str(record["revision_id"]), base_operation_id=str(meta[0]),
                        base_ledger_pin=str(record["ledger_version"]), request_sha256=digest(encoded(dict(proposal=proposal, preview_receipt=receipt))),
                        proposal_sha256=digest(encoded(proposal)), preview_receipt_sha256=digest(receipt.encode("utf8")),
                        response_sha256=digest(response), report_status=report["status"], created_at=now)
                    staged = self._sql_commit(conn, command, response, encoded(env))
                    self._before_commit(conn)
                else:
                    staged = prior
                self._verify(conn, core, scope, workspace, importer, staged)
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
            return self.committed(staged), 200
        except (psycopg.OperationalError, psycopg.InterfaceError):
            return self.unknown(root, op), 202

    def find(self, conn, scope, *, op=None, report=None):
        return self._row(query(conn, self.schema, "gh_csv_report_read", (scope.owner_id, scope.root_id, scope.context_id, op, report, scope.purpose)).fetchone())

    def archive_value(self, row, generation):
        return dict(schema="finweb.guarded_csv_report_archive/1", profile=PROFILE, synthetic=True,
            portfolio_id=str(row["root_id"]), operation_id=str(row["operation_id"]), base_revision_id=str(row["base_revision_id"]),
            report_id=str(row["report_id"]), context_id=row["context_id"], commit_generation=row["commit_generation"], admission_generation=generation,
            response_json=bytes(row["response"]).decode(), response_sha256=row["response_sha256"],
            envelope_json=bytes(row["envelope"]).decode(), envelope_sha256=row["envelope_sha256"])

    def archive(self, owner, root, op, *, export=False, reconcile=False):
        from persistence.guarded_http_store import uid
        owner, root, op = uid(owner), uid(root), uid(op)
        purpose = "ARCHIVE_EXPORT" if export else "ARCHIVE_READ"
        with self.facade._lease(owner, root, purpose) as (conn, core, scope, _, workspace, importer):
            row = self.find(conn, scope, op=op)
            if row is None:
                if reconcile:
                    return self.unknown(root, op), 202
                fail("NOT_FOUND", 404)
            self._verify(conn, core, scope, workspace, importer, row)
            if reconcile:
                return self.committed(row), 200
            return self.archive_value(row, scope.generation)

    def metadata(self, row, generation):
        return dict(schema="finweb.guarded_csv_report_read/1", profile=PROFILE, synthetic=True,
            portfolio_id=str(row["root_id"]), operation_id=str(row["operation_id"]), report_id=str(row["report_id"]),
            base_revision_id=str(row["base_revision_id"]), context_id=row["context_id"], commit_generation=row["commit_generation"],
            admission_generation=generation, response_sha256=row["response_sha256"], archive_url=self.path(row["root_id"], row["operation_id"]))

    def list(self, conn, core, scope, importer, cursor):
        # Old importer remains protected by this actual lease and archived projection.
        ids = conn.execute("SELECT report_id FROM web_csv_report WHERE portfolio_id=%s ORDER BY created_at DESC,report_id DESC LIMIT 1001", (scope.root_id,)).fetchall()
        rows = []
        for (report_id,) in ids:
            report = importer._read(conn, str(scope.owner_id), scope.root_id, str(report_id))
            meta = self.facade._meta(conn, scope.owner_id, scope.root_id, report=report_id)
            rows.append(dict(report_id=report["report_id"], status=report["status"], created_at=report["created_at"], kind=report["proposal"]["kind"],
                file_sha256=report["file"]["sha256"], counts=report["counts"], revision_id=report["revision_id"], operation_kind="FINANCIAL_CSV",
                operation_id=str(meta[0]), archive_url=self.facade.archive_url(scope.root_id, meta[0])))
        for (row,) in query(conn, self.schema, "gh_csv_report_list", (scope.owner_id, scope.root_id, scope.context_id)).fetchall():
            row["archive_url"] = self.path(scope.root_id, row["operation_id"])
            rows.append(row)
        if len(rows) > 1000:
            fail("F3_CSV_REPORT_CAPACITY", 429)
        rows.sort(key=lambda row: (row["created_at"], row["report_id"]), reverse=True)
        if cursor is not None:
            bound = decode_cursor(cursor)
            if not any((row["created_at"], row["report_id"]) == bound for row in rows):
                fail("CSV_REPORT_CURSOR", 422)
            rows = [row for row in rows if (row["created_at"], row["report_id"]) < bound]
        page = rows[:25]
        next_cursor = encode_cursor(page[-1]) if len(rows) > 25 else None
        return dict(schema_version="finweb.cp7/1", portfolio_id=str(scope.root_id), reports=page, next_cursor=next_cursor)


def encode_cursor(row):
    return base64.urlsafe_b64encode(encoded({"created_at": row["created_at"], "report_id": row["report_id"]})).decode().rstrip("=")


def decode_cursor(cursor):
    try:
        if type(cursor) is not str or not 1 <= len(cursor) <= 512 or re.fullmatch("[A-Za-z0-9_-]+", cursor) is None:
            raise ValueError()
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        value = json.loads(raw)
        if (set(value) != {"created_at", "report_id"} or encoded(value) != raw or encode_cursor(value) != cursor
                or str(uuid.UUID(value["report_id"])) != value["report_id"]
                or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z", value["created_at"]) is None):
            raise ValueError()
        dt.datetime.fromisoformat(value["created_at"].replace("Z", "+00:00"))
        return value["created_at"], value["report_id"]
    except (ValueError, TypeError, AttributeError, KeyError):
        fail("CSV_REPORT_CURSOR", 422)


def export_report(report, format):
    if format == "json":
        return canonical_json(report), "application/json"
    rows = [dict(row_number=row["row_number"], physical_start=row["physical_start"], physical_end=row["physical_end"],
        classification=row["classification"], reason=row["reason"], disposition=row["disposition"], source_key=row["source_key"], event_id=row["event_id"],
        cells=canonical_json(row["cells"]), fields=canonical_json(row["fields"]), errors=canonical_json(row["errors"]),
        corrections=canonical_json([change for change in report["proposal"]["corrections"] if change["row_number"] == row["row_number"]]),
        text_protection="apostrophe-prefixed untrusted text; authoritative lossless JSON available") for row in report["rows"]]
    return protected_csv(rows), "text/csv; charset=utf-8"
