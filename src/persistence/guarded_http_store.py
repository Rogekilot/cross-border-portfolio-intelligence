"""Opt-in fictional HTTP facade; READ projects immutable answers, never reissues.

Authentication supplies owners. PostgreSQL supplies current rights/transaction
leases. The runtime holds executor access only; issuer operations live elsewhere.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import FunctionType
import uuid

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from corporate_actions_service.split_confirmation import ConfirmationPolicy
from diversification.contracts import CapitalUniverseChoice, PRODUCT_ID
from domain.catalogs import BenchmarkCatalog
from financial_service_integration import LocalServiceKind
from insights.evidence import semantic_key
from insights.registry import POLICY_SELECTORS
from marketdata.canonical import canonical_json
from persistence.guarded_workspace_context import GuardedWorkspaceError, identifier, require_idle
from persistence.guarded_workspace_store import (GuardedWorkspaceStore, CommittedWorkspaceResult,
    RefusedWorkspaceResult, UnknownWorkspaceResult, root_id_for)
from persistence.web_account_store import AccountStoreError
from persistence.web_workspace_store import WorkspaceStore
from persistence.web_csv_store import CsvImportStore
from persistence.guarded_csv_report_store import ReportAwareWorkspaceStore, GuardedCsvReportStore, export_report
from web_api.synthetic import SyntheticWorld

PROFILE = "F3_FICTIONAL_CP5"
HTTP_SCHEMA = "finweb.guarded_http/1"
MAX_HTTP_BYTES = 20000000
RIGHTS = {name: True for name in ("EXECUTE_CREATE", "ARCHIVE_READ", "ARCHIVE_EXPORT", "EXECUTE_REPRODUCE")}
F2_SQL_SHA256 = "9c5733a9b9760952cce106a6a90dfadea44342a5235dcc233f4bc9e927e5f423"
POLICY_EXTENSION_MARKER = "-- F3_POLICY_EXTENSION_BEGIN\n"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def uid(value):
    if type(value) is uuid.UUID:
        return value
    try:
        if type(value) is not str or str(uuid.UUID(value)) != value:
            raise ValueError()
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise AccountStoreError(404, "NOT_FOUND", "Owned fictional operation is unavailable") from None


def install_guarded_http(conn, *, schema, executor_role):
    schema, executor_role = identifier(schema), identifier(executor_role)
    require_idle(conn)
    row = conn.execute("SELECT n.nspowner=r.oid,r.rolcanlogin FROM pg_namespace n JOIN pg_roles r ON r.rolname=current_user WHERE n.nspname=%s", (schema,)).fetchone()
    if row != (True, False):
        raise GuardedWorkspaceError("F3_INSTALL_OWNER_REQUIRED")
    if conn.execute("SELECT to_regclass(%s) IS NOT NULL AND to_regprocedure(%s) IS NULL", (schema + ".gw_root", schema + ".gh_head(text)")).fetchone() != (True,):
        raise GuardedWorkspaceError("F3_INSTALL_FRESH_F2_REQUIRED")
    body = _addon_sql(schema, executor_role)
    with conn.transaction():
        conn.execute(body, prepare=False)


def _addon_sql(schema, executor_role=None, *, policy_only=False):
    """Exact frozen F2 prosrc plus a single fixed-fictional policy predicate."""
    original = Path(__file__).with_name("guarded_workspace_v1.sql").read_bytes()
    if sha(original) != F2_SQL_SHA256:
        raise GuardedWorkspaceError("F3_POLICY_TEMPLATE_DIFFERS")
    source = original.decode("utf8")
    block = source.split("CREATE FUNCTION __GW_SCHEMA__.gw_check_artifact(", 1)[1].split("\nCREATE FUNCTION __GW_SCHEMA__.gw_validate(", 1)[0]
    prosrc = block.split("AS $$", 1)[1].rsplit("$$;", 1)[0].replace("__GW_SCHEMA__", schema)
    body = Path(__file__).with_name("guarded_http_v1.sql").read_text("utf8")
    if body.count(POLICY_EXTENSION_MARKER) != 1:
        raise GuardedWorkspaceError("F3_POLICY_TEMPLATE_DIFFERS")
    if policy_only:
        body = body.split(POLICY_EXTENSION_MARKER, 1)[1]
    return body.replace("__GH_F2_PROSRC_SHA256__", sha(prosrc.encode("utf8"))).replace("__GH_BARE_SCHEMA__", schema).replace("__GH_SCHEMA__", '"' + schema + '"').replace("__GH_EXECUTOR__", '"' + (executor_role or "") + '"')


def upgrade_guarded_http_policy(conn, *, schema):
    """Root-operated one-time F3 correction; no app endpoint or extra grant."""
    schema = identifier(schema)
    require_idle(conn)
    if conn.execute("SELECT n.nspowner=r.oid,r.rolcanlogin FROM pg_namespace n JOIN pg_roles r ON r.rolname=current_user WHERE n.nspname=%s", (schema,)).fetchone() != (True, False):
        raise GuardedWorkspaceError("F3_INSTALL_OWNER_REQUIRED")
    query = "SELECT p.prosrc,pg_get_functiondef(p.oid),p.proacl::text,p.proowner::regrole::text,p.prosecdef,p.proconfig FROM pg_proc p WHERE p.oid=to_regprocedure(%s)"
    target = schema + ".gw_check_artifact(" + schema + ".gw_artifact,text,uuid)"
    with conn.transaction():
        before = conn.execute(query, (target,)).fetchone()
        conn.execute(_addon_sql(schema, policy_only=True), prepare=False)
        after = conn.execute(query, (target,)).fetchone()
        if before is None or after is None or before[2:] != after[2:] or before[0] == after[0]:
            raise GuardedWorkspaceError("F3_POLICY_EXTENSION_DIFFERS")
    return dict(schema="finweb.f3.policy_extension/1", result="APPLIED", product_schema=schema,
        original_prosrc_sha256=sha(before[0].encode()), revised_prosrc_sha256=sha(after[0].encode()),
        original_ddl_sha256=sha(before[1].encode()), revised_ddl_sha256=sha(after[1].encode()),
        original_ddl=before[1], revised_ddl=after[1], acl=before[2], owner=before[3],
        security_definer=before[4], search_path=before[5], app_privileges_added=False)


def _is_engine_ledger_digest(value):
    """True only for the genuine `performance.ledger_view.ledger_digest` function, without importing `performance`.

    Persistence may not import the engine, so identity cannot be tested directly. Instead require a plain Python function
    (not a callable object, `functools.partial` or bound method, so no `__eq__`/`__call__` trick passes) whose code name,
    qualified name and defining-module globals all name the engine's module. A lambda or wrapper defined by a caller has
    its caller's module globals, and `__globals__` is read-only on a function, so renaming `__module__`/`__qualname__`
    alone cannot pass. The wiring test in `web_api.guarded_dev` pins the object to the real import.
    """
    if type(value) is not FunctionType:
        return False
    module = value.__globals__.get("__name__")
    return (type(module) is str and module == "performance.ledger_view"
        and type(value.__qualname__) is str and value.__qualname__ == "ledger_digest"
        and value.__code__.co_name == "ledger_digest" and value.__module__ == "performance.ledger_view")


@dataclass(frozen=True)
class FictionalProfile:
    store: object
    world: object
    policy: object
    capital_policy: object
    context_id: str
    snapshot_bytes: bytes
    preview_key: bytes
    # Injected by the caller above persistence (`performance.ledger_view.ledger_digest`): persistence may not import the
    # engine, and the digest has exactly one implementation. Called as `ledger_digest(events, ledger_version)`.
    ledger_digest: object = None

    def __post_init__(self):
        # Every construction path (build_fictional_profile, direct, dataclasses.replace) lands here.
        if not _is_engine_ledger_digest(self.ledger_digest):
            raise GuardedWorkspaceError("F3_LEDGER_DIGEST_REQUIRED")

    def core(self, generation=1):
        return ReportAwareWorkspaceStore(self.store, self.world, context_id=self.context_id,
            generation=generation, policy=self.policy, capital_policy=self.capital_policy, preview_key=self.preview_key)

    def capabilities(self):
        day = self.world.as_of.isoformat()
        return dict(schema="finweb.guarded_profile/1", profile=PROFILE, synthetic=True, saved_only=True,
            source_as_of=day, opening_date_required=True, opening_date_max=day, opening_date_recommended="2026-01-01",
            selector="CP5_DIVERSIFICATION", operations=["CREATE", "LEDGER", "PREFERENCES", "CSV_PARSE", "CSV_PREVIEW",
                "CSV_COMMIT", "READ", "EXPORT", "ARCHIVE", "REPRODUCE", "RECONCILE"],
            unsupported=["LEGACY_ANALYTICS", "LEGACY_PACKETS", "REAL_DATA", "GUEST"])


def build_fictional_profile(store, *, expected_context=None, preview_key, ledger_digest=None):
    if type(preview_key) is not bytes or len(preview_key) < 32:
        raise GuardedWorkspaceError("F3_PREVIEW_KEY_REQUIRED")
    if not _is_engine_ledger_digest(ledger_digest):
        raise GuardedWorkspaceError("F3_LEDGER_DIGEST_REQUIRED")
    world = SyntheticWorld(benchmark_catalog_provider=lambda: BenchmarkCatalog("f3-empty:1", ()))
    policy = ConfirmationPolicy(frozenset(("f3.synthetic.feed",)), frozenset(("f3.synthetic.filing",)))
    capital = CapitalUniverseChoice("FULL_NAV", "SYNTHETIC_CANDIDATE", "F3 fictional local trial only",
        decision_id="f3-fictional:1", scope_kind="GLOBAL_PRODUCT", product_id=PRODUCT_ID)
    core = GuardedWorkspaceStore(store, world, context_id="0" * 64, generation=1,
        policy=policy, capital_policy=capital, preview_key=preview_key)
    snapshot = core.source_snapshot()
    context = sha(snapshot)
    if expected_context is not None and context != expected_context:
        raise GuardedWorkspaceError("F3_CONTEXT_DIFFERS")
    return FictionalProfile(store, world, policy, capital, context, snapshot, preview_key, ledger_digest)


@dataclass(frozen=True)
class ArchivedSemanticProjection:
    payload_json: str
    source_kind: str = "CP5"

    def payload(self):
        return json.loads(self.payload_json)

    def context(self):
        m = self.payload()["manifest"]
        return dict(reporting_currency=m["reporting_currency"], portfolio_state=m["state_kind"], scenario_id=None,
            capital_universe=m["capital_policy"]["choice"] if m["capital_policy_confirmed"] else None,
            registry_id=m["registry_id"], registry_digest=m["registry_digest"], engine_id=m["engine_id"],
            valuation_mode=m["valuation_manifest"]["valuation_mode"], frequency=m["frequency"], request=m["request"])


@dataclass(frozen=True)
class StoredSnapshotProjection:
    snapshot_json: str
    policies: tuple
    evidence: ArchivedSemanticProjection

    def snapshot(self):
        return json.loads(self.snapshot_json)


class ArchivedWorkspaceProjection(WorkspaceStore):
    """Only native facts and authenticated saved JSON; no financial Result constructor."""
    def __init__(self, facade, core, scope, owner):
        super().__init__(facade.profile.store, facade.profile.world)
        self.facade, self.core, self.scope, self.owner = facade, core, scope, owner

    def _item(self, conn, ident, record):
        self.scope.assert_current(conn)
        if ident != self.scope.root_id or self.owner != self.scope.owner_id:
            raise GuardedWorkspaceError("F3_READ_SCOPE_DIFFERS")
        try:
            meta = self.facade._meta(conn, self.owner, ident, rev=record["revision_id"])
            issued, response, envelope, revision, pin = self.core._archive(conn, self.owner, meta[0])
            raw, env = json.loads(response), json.loads(envelope)
            snapshot = self.facade._snapshot(raw, meta[3])
            if (env["owner_id"] != str(self.owner) or env["root_id"] != str(ident)
                    or env["revision_id"] != str(record["revision_id"]) or revision != record["revision_id"]
                    or env["context_id"] != self.scope.context_id or pin != record["ledger_version"]
                    or env["issued_sha256"] != sha(issued) or env["response_sha256"] != sha(response)
                    or canonical_json(snapshot) != record["snapshot_json"]
                    or sha(record["snapshot_json"].encode()) != record["snapshot_sha256"]
                    or record["request"]["source_sha256"] != self.world.input_sha256
                    or record["request"]["calendar_sha256"] != self.world.calendar_sha256
                    or record["request"]["as_of"] != self.world.as_of.isoformat()):
                raise ValueError("saved archive binding")
            native = json.loads(issued)
            events = self._events(conn, ident, pin)
            if native["manifest"]["valuation_manifest"]["ledger_digest"] != self.facade.profile.ledger_digest(events, pin):
                raise ValueError("native ledger digest")
            def content(rows):
                result = {}
                for row in rows:
                    key = (row["metric_id"], tuple(row.get("subject", ())))
                    if key in result:
                        raise ValueError("duplicate metric")
                    result[key] = {k: v for k, v in row.items() if k != "manifest_id"}
                return result
            if content(snapshot["diversification"]["metrics"]) != content(native["metrics"]):
                raise ValueError("saved/native metric semantics")
            item = StoredSnapshotProjection(record["snapshot_json"], tuple(record["policies"]), ArchivedSemanticProjection(issued.decode("utf8")))
            if meta[3] != "CREATE":
                archived_workspace = raw["workspace_result"]["workspace"] if meta[3] == "CSV" else raw["workspace"]
                if canonical_json(archived_workspace["policies"]["targets"]) != canonical_json(self._targets(item)):
                    raise ValueError("archived policy target semantics differ")
            return item, events
        except (KeyError, ValueError, TypeError, AttributeError):
            raise AccountStoreError(503, "F3_ARCHIVE_PROJECTION_DIFFERS", "Stored fictional evidence or native fact projection differs") from None

    def _targets(self, item):
        if type(item) is not StoredSnapshotProjection:
            raise GuardedWorkspaceError("F3_STORED_PROJECTION_REQUIRED")
        return [dict(source_kind="CP5", metric_id=row["metric_id"], subject=row.get("subject", []),
            semantic_key=semantic_key(item.evidence, row), scope_kind="PORTFOLIO", account_id=None,
            unit=row.get("unit"), state=row["state"])
            for row in item.evidence.payload()["metrics"] if row["metric_id"] in POLICY_SELECTORS["CP5"]]


class ArchivedCsvProjection(CsvImportStore):
    def __init__(self, facade, workspace):
        super().__init__(facade.profile.store, facade.profile.world, facade.profile.preview_key)
        self.workspace = workspace


class GuardedHttpStore:
    def __init__(self, profile):
        if type(profile) is not FictionalProfile:
            raise GuardedWorkspaceError("F3_PROFILE_REQUIRED")
        self.profile, self.schema = profile, identifier(profile.store.schema)
        self.reports = GuardedCsvReportStore(self)

    def _query(self, conn, name, params):
        if name not in ("gh_head", "gh_owned_roots", "gh_operation"):
            raise GuardedWorkspaceError("F3_FIXED_METADATA_QUERY")
        return conn.execute(sql.SQL("SELECT * FROM {}.{}(" + ",".join(["%s"] * len(params)) + ")").format(sql.Identifier(self.schema), sql.Identifier(name)), params)

    def _meta(self, conn, owner, root, *, op=None, rev=None, report=None, required=True):
        row = self._query(conn, "gh_operation", (owner, root, self.profile.context_id, op, rev, report)).fetchone()
        if row is None and required:
            raise AccountStoreError(404, "NOT_FOUND", "Owned fictional operation is unavailable")
        return row

    def _core(self, conn):
        row = self._query(conn, "gh_head", (self.profile.context_id,)).fetchone()
        if row is None:
            raise GuardedWorkspaceError("F2_MODE_HOLD")
        core = self.profile.core(row[0])
        if core.source_snapshot() != self.profile.snapshot_bytes:
            raise GuardedWorkspaceError("F2_CONTEXT_DIFFERS")
        return core

    @staticmethod
    def _snapshot(value, kind):
        if kind == "CREATE":
            return value
        if kind == "CSV":
            return value["workspace_result"]["snapshot"]
        if kind in ("LEDGER", "PREFERENCES"):
            return value["snapshot"]
        raise GuardedWorkspaceError("F3_ARCHIVE_VARIANT")

    @contextmanager
    def _lease(self, owner, root, purpose, *, op=None, rev=None, report=None):
        owner, root = uid(owner), uid(root)
        with self.profile.store.connect() as conn:
            require_idle(conn)
            meta = self._meta(conn, owner, root, op=op, rev=rev, report=report)
            core = self._core(conn)
            with conn.transaction():
                scope = core._admit(conn, owner, root, meta[0], "0" * 64, purpose)
                core._archive(conn, owner, meta[0])
                workspace = ArchivedWorkspaceProjection(self, core, scope, owner)
                yield conn, core, scope, meta, workspace, ArchivedCsvProjection(self, workspace)
            require_idle(conn)

    def _read_meta(self, core, scope, meta, saved):
        return dict(schema="finweb.guarded_read/1", profile=PROFILE, portfolio_id=str(scope.root_id),
            revision_id=str(meta[1]), operation_id=str(meta[0]), context_id=scope.context_id,
            generation=scope.generation, issued_sha256=sha(saved[0]), archived_response_sha256=sha(saved[1]),
            archive_url=self.archive_url(scope.root_id, meta[0]))

    @staticmethod
    def archive_url(root, op):
        return "/api/v1/portfolios/" + str(root) + "/operations/" + str(op)

    def unknown(self, root, op):
        return dict(schema=HTTP_SCHEMA, profile=PROFILE, disposition="UNKNOWN", synthetic=True,
            portfolio_id=str(root), operation_id=str(op), reconcile_url=self.archive_url(root, op) + "/reconcile")

    def committed(self, root, op, response, issued_sha):
        value = json.loads(response)
        if "workspace_result" in value:
            revision = value["workspace_result"]["workspace"]["revision_id"]
        elif "workspace" in value:
            revision = value["workspace"]["revision_id"]
        else:
            revision = str(root)
        return dict(schema=HTTP_SCHEMA, profile=PROFILE, disposition="COMMITTED", synthetic=True,
            portfolio_id=str(root), operation_id=str(op), revision_id=revision, response_json=response.decode("utf8"),
            response=value, response_sha256=sha(response), issued_sha256=issued_sha,
            archive_url=self.archive_url(root, op), reconcile_url=self.archive_url(root, op) + "/reconcile")

    def execute(self, owner, root, op, kind, body, receipt=None):
        owner, root, op = uid(owner), uid(root), uid(op)
        with self.profile.store.connect() as conn:
            require_idle(conn)
            core = self._core(conn)
            result = core.execute(owner, root, op, kind, body, receipt=receipt, connection=conn)
        if type(result) is UnknownWorkspaceResult:
            return self.unknown(root, op), 202
        if type(result) is RefusedWorkspaceResult:
            return dict(schema=HTTP_SCHEMA, profile=PROFILE, disposition="REFUSED", synthetic=True,
                portfolio_id=str(root), operation_id=str(op), error=dict(code=result.code, detail="The actual fictional financial service refused this operation", state="INSUFFICIENT_DATA"),
                issued_json=result.issued_bytes.decode("utf8"), issued_sha256=sha(result.issued_bytes)), 422
        if type(result) is not CommittedWorkspaceResult:
            raise GuardedWorkspaceError("F3_OUTCOME_TYPE")
        return self.committed(root, op, result.response_bytes, result.issued_sha256), 200

    def create(self, owner, op, body):
        owner, op = uid(owner), uid(op)
        return self.execute(owner, root_id_for(owner, op), op, "CREATE", body)

    def list(self, owner):
        owner = uid(owner)
        with self.profile.store.connect() as conn:
            roots = self._query(conn, "gh_owned_roots", (owner, self.profile.context_id)).fetchall()
        rows = []
        for (root,) in roots:
            with self._lease(owner, root, "ARCHIVE_READ") as (conn, core, scope, meta, workspace, _):
                record = workspace._record(conn, str(owner), root)
                item, _ = workspace._item(conn, root, record)
                snap = item.snapshot()
                created = conn.execute("SELECT created_at FROM web_saved_sandbox WHERE portfolio_id=%s", (root,)).fetchone()[0]
                saved = core._archive(conn, owner, meta[0])
                rows.append(dict(portfolio_id=str(root), name=snap["name"], mode="LOCAL_SYNTHETIC_ACCOUNT", synthetic=True,
                    reporting_currency="USD", as_of=str(record["as_of"]), created_at=created,
                    guarded=self._read_meta(core, scope, meta, saved)))
        return dict(schema_version="finweb.cp7/1", portfolios=rows)

    def read(self, owner, root, *, revision=None, workspace_only=False):
        owner, root = uid(owner), uid(root)
        with self._lease(owner, root, "ARCHIVE_READ", rev=None if revision is None else uid(revision)) as (conn, core, scope, meta, workspace, _):
            record = workspace._record(conn, str(owner), root, str(meta[1]))
            item, events = workspace._item(conn, root, record)
            value = workspace._workspace(conn, root, record, item, events) if workspace_only else item.snapshot()
            saved = core._archive(conn, owner, meta[0])
            return {**value, "guarded": self._read_meta(core, scope, meta, saved)}

    def preview(self, owner, root, body, *, csv=False):
        owner, root, op = uid(owner), uid(root), uid(body["operation_id"])
        with self.profile.store.connect() as conn:
            core = self._core(conn)
            if csv:
                value = core.csv_preview(owner, root, body, connection=conn)
                if type(value) is UnknownWorkspaceResult:
                    return self.unknown(root, op), 202
            else:
                with conn.transaction():
                    command_sha = core._command(owner, root, op, "LEDGER", body, LocalServiceKind.CP5_DIVERSIFICATION, None)
                    core._query(conn, "gw_precheck", (owner, op, command_sha)).fetchone()
                    scope = core._admit(conn, owner, root, op, command_sha, "EXECUTE_CREATE")
                    value = core.workspace.command(str(owner), str(root), body, preview=True, connection=conn, execution_scope=scope)
                    raise psycopg.Rollback()
                if conn.info.transaction_status != TransactionStatus.IDLE:
                    return self.unknown(root, op), 202
        # A new current READ is explicit; base metadata never calls proposal committed.
        with self._lease(owner, root, "ARCHIVE_READ", rev=uid(body["expected_revision_id"])) as (conn, core, scope, meta, _, _):
            saved = core._archive(conn, owner, meta[0])
            return {**value, "guarded": self._read_meta(core, scope, meta, saved)}, 200

    def csv_read(self, owner, root, action, *, body=None, report=None, cursor=None, format="json", revision=None, kind=None):
        owner, root = uid(owner), uid(root)
        purpose = "ARCHIVE_EXPORT" if action in ("export_report", "export_portfolio") else "ARCHIVE_READ"
        with self._lease(owner, root, purpose, rev=None if revision is None else uid(revision)) as (conn, core, scope, meta, workspace, importer):
            if report is not None:
                stored = self.reports.find(conn, scope, report=uid(report))
                if stored is not None:
                    document = self.reports._verify(conn, core, scope, workspace, importer, stored)
                    if action == "get":
                        return dict(schema_version="finweb.cp7/1", portfolio_id=str(root), report=document["report"],
                            guarded_report=self.reports.metadata(stored, scope.generation))
                    if action == "export_report":
                        return export_report(document["report"], format), str(stored["operation_id"])
                    raise GuardedWorkspaceError("F3_FIXED_READ_ACTION")
                meta = self._meta(conn, owner, root, report=uid(report))
                core._archive(conn, owner, meta[0])
            if action == "parse":
                from portfolio_import.csv_source import parse_source, CsvSourceError
                importer._owned(conn, str(owner), root)
                try:
                    value = dict(schema_version="finweb.cp7/1", portfolio_id=str(root), **parse_source(body["file_base64"], body["filename"], body["delimiter"]))
                except CsvSourceError as error:
                    raise AccountStoreError(422, "CSV_FILE_REFUSED", str(error)) from None
            elif action == "get":
                value = importer.get(str(owner), str(root), str(report), connection=conn)
            elif action == "list":
                value = self.reports.list(conn, core, scope, importer, cursor)
            elif action == "export_report":
                return importer.export_report(str(owner), str(root), str(report), format, connection=conn), str(meta[0])
            elif action == "export_portfolio":
                return importer.export_portfolio(str(owner), str(root), str(revision), kind, format, connection=conn), str(meta[0])
            else:
                raise GuardedWorkspaceError("F3_FIXED_READ_ACTION")
            saved = core._archive(conn, owner, meta[0])
            return {**value, "guarded": self._read_meta(core, scope, meta, saved)}

    def archive(self, owner, root, op, *, export=False):
        owner, root, op = uid(owner), uid(root), uid(op)
        with self._lease(owner, root, "ARCHIVE_EXPORT" if export else "ARCHIVE_READ", op=op) as (conn, core, scope, meta, _, _):
            issued, response, envelope, _, _ = core._archive(conn, owner, op)
            env = json.loads(envelope)
            return dict(schema="finweb.guarded_archive/1", profile=PROFILE, synthetic=True, portfolio_id=str(root), operation_id=str(op),
                revision_id=str(meta[1]), context_id=scope.context_id, generation=env["generation"], admission_generation=scope.generation,
                issued_json=issued.decode("utf8"), response_json=response.decode("utf8"), envelope_json=envelope.decode("utf8"),
                issued_sha256=sha(issued), response_sha256=sha(response), envelope_sha256=sha(envelope))

    def reproduce(self, owner, root, op):
        owner, root, op = uid(owner), uid(root), uid(op)
        with self.profile.store.connect() as conn:
            core = self._core(conn)
            value = core.reproduce(owner, root, op, connection=conn)
        return dict(schema="finweb.guarded_reproduce/1", profile=PROFILE, synthetic=True, portfolio_id=str(root),
            operation_id=str(op), status=value.status, detail=value.detail, issued_sha256=value.issued_sha256)

    def reconcile(self, owner, op, root=None, *, creation=False):
        owner, op = uid(owner), uid(op)
        root = root_id_for(owner, op) if creation else uid(root)
        with self.profile.store.connect() as conn:
            core = self._core(conn)
            try:
                with conn.transaction():
                    # Even absence first checks locked current head/purpose. A
                    # missing root cannot mint a lease; absence stays UNKNOWN.
                    core._admit(conn, owner, root, op, "0" * 64, "ARCHIVE_READ")
                    saved = core._archive(conn, owner, op)
                    meta = self._meta(conn, owner, root, op=op)
                    if creation and (meta[3] != "CREATE" or root != root_id_for(owner, op)):
                        raise AccountStoreError(404, "NOT_FOUND", "Owned creation is unavailable")
            except psycopg.errors.RaiseException as error:
                if str(error).split("\n", 1)[0] == "F2_NOT_FOUND":
                    return self.unknown(root, op), 202
                raise
            except GuardedWorkspaceError as error:
                if error.code == "F2_NOT_FOUND":
                    return self.unknown(root, op), 202
                raise
            return self.committed(root, op, saved[1], sha(saved[0])), 200
