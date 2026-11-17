"""F1 R5: the real gateway's EXECUTOR-SIDE SERVICE: create, archive read, reproduce and list (design 7.1 R5 row, 4.2, 4.4, 2.4).

PLACEMENT. This package sits above `persistence` because it calls the performance engine and its service, which `persistence` must not import
(`tests/product/test_performance_boundaries.py`).

One class, `RealWorkspaceService`, over the executor's connection. It holds NO `COMMIT`, NO `SET CONSTRAINTS` and NO commit-outcome
classification of its own: every create goes through `real_tails.CreateTail`, and every read, reproduce and list entry through
`real_tails.ReadTail` (a static audit checks the source). A method here only says WHAT to do inside the tail's one transaction.

THE TWO CREATES, one parameterised module (PD-0066 decision 8):

  * the REAL branch (scopes `REAL` and `TEST_SWITCH`): admit; the guarded load of the provenance link; the world BUILT FROM THE LOCKED SNAPSHOT
    and checked against it (`worlds.build_real_world`, which reads the release through the lease-checked read functions); the staged
    portfolio, account, opening ledger events, root and first revision; the ACTUAL performance service on that ledger. On made-up test data the
    service refuses (`worlds.REFUSAL_CODE`, design fact 12) and the transaction rolls back whole: nothing is addressable (FF1-C08).
    The refusal is never turned into a result and the service is never parameterised to accept such data. A service-accepted result
    (flag false, first possible at R8) is sealed, archived and delivered after the COMMIT.
  * the test-scope create (the fictional branch, TEST installs only): the same staging over the made-up world of the EXISTING fictional
    integration, called UNCHANGED (`financial_service_integration.issue_local_service`, selector CP5_DIVERSIFICATION), stored in the S2 tables
    `rw_root` and `rw_revision`, sealed through R3's `rw_check_fictional`. It exists so that the shared tails run on product code with an accepted
    commit before R8.

ORIGIN. The four origin fields of a root come from the SCOPE of the context's locked snapshot (`real_scope.SCOPES`, a table, never a caller
argument), are written once into the root row and into the gateway `response`, and are read back from the stored response for every later output
(archive read, reproduce, list, labels, claim text). Nothing here hard-codes a flag, a market origin or a mode string: the column names are
`real_labels.ORIGIN_FIELDS`.

NOT HERE: any route (R7 installs the reviewed contract), the NAV oracle `10 x p + 500` (R8), a real run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import hashlib
import json
import uuid
from decimal import Decimal

from domain.currency import CurrencyCode, Money
from domain.ledger import EventType, LedgerEvent
from marketdata import claim_record as claim_records, claim_render
from marketdata.canonical import canonical_json
from persistence import ledger_replay_store, ledger_store, real_labels, real_scope, real_tails
from persistence import real_workspace_store as store
from persistence.real_provenance import ProvenanceError
from persistence.real_workspace_context import RealWorkspaceError, identifier, query_one, transaction_identity
from real_service import worlds as real_worlds
from web_api import real_scoped_contract as contract

USD = CurrencyCode("USD")
FLAG = real_labels.FLAG_FIELD
ORIGIN_COLUMNS = real_labels.ORIGIN_FIELDS
ACCOUNT_NAME = "constructed test account"
POSITION_REFERENCE = "constructed opening position"
CASH_REFERENCE = "constructed opening cash"
#: The refusal of a REAL create whose claim record cannot be built or whose claim block cannot be rendered (PD-0082 Q3). It is raised inside the create's transaction,
#: before the seal, so the transaction rolls back whole and nothing is addressable. The detail is the render code (`CLAIM_RECORD_*`, `CLAIM_PRECONDITION`, ...) and is never public.
CLAIM_RECORD_REFUSED = "RW_CLAIM_RECORD_REFUSED"


def response_of(*, root, intent, origin, labels, operation_id, revision, pin, claim_record=None):
    """The stored response of a create: the gateway's response document, written into `rw_root`, `rw_revision` and (sealed) `rw_artifact`. Pure. `claim_record`
    (O-7, PD-0082 Q1) is the REAL branch's claim record (K), a copy of the values the computation used; the test-scope create has none and its response is the
    document it always was."""
    response = {"portfolio_id": str(root), "as_of": intent["as_of"], "persisted": True, "reporting_currency": "USD", FLAG: origin[FLAG],
                "origin": origin, "labels": {k: labels[k] for k in contract.LABEL_FIELDS}, "name": intent["name"],
                "operation_id": str(operation_id), "revision_id": str(revision), "ledger_version": pin,
                "opening_positions": intent["opening_positions"], "opening_cash": intent["opening_cash"]}
    if claim_record is not None:
        response[claim_records.RECORD_KEY] = claim_record
    return response


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return canonical_json(value).encode("utf-8")


def root_id_for(owner, operation_id):
    """The root of a create is a function of its owner and operation id, so an identical command always addresses the same root."""
    return uuid.uuid5(owner, "finweb.rw.root:" + str(operation_id))


def command_digest(owner, root, operation_id, context_id, intent):
    """The digest the gateway stores as the operation's command: owner, root, operation, context and the validated intent, canonical."""
    return digest(encoded({"schema": "finweb.rw.create-command/1", "owner_id": str(owner), "root_id": str(root), "operation_id": str(operation_id),
                           "context_id": context_id, "intent": intent}))


@dataclass(frozen=True)
class ProvenanceLink:
    """The registered provenance candidate a create stands on (the mandatory link, PD-0059): its context digest and the expectations the guarded
    load checks it against."""
    context_sha256: str
    members: tuple
    witnesses: tuple


@dataclass(frozen=True)
class Archive:
    """One stored bundle as `rw_archive` returns it (the seal's acceptance has run again)."""
    issued: bytes = field(repr=False)
    response: bytes = field(repr=False)
    envelope: bytes = field(repr=False)
    issued_sha256: str
    response_sha256: str
    revision_id: uuid.UUID
    ledger_pin: int

    @property
    def response_obj(self):
        return json.loads(self.response)

    @property
    def origin(self):
        """The four origin fields, from the STORED response (never recomputed from a scope or a mode)."""
        return self.response_obj["origin"]

    @property
    def labels(self):
        return real_labels.root_labels(self.origin)


def _archive_of(row):
    if row is None:
        raise RealWorkspaceError("RW_NOT_FOUND")
    return Archive(bytes(row[0]), bytes(row[1]), bytes(row[2]), row[3], row[4], row[5], row[6])


@dataclass(frozen=True)
class Created:
    root_id: uuid.UUID
    operation_id: uuid.UUID
    archive: Archive
    replayed: bool
    state: str = field(default="COMMITTED", init=False)


@dataclass(frozen=True)
class Reproduction:
    """The outcome of a reproduce. `origin` is the four stored origin fields of the archive read in the SAME transaction and admission (PD-0073
    condition 3; TR5-M2): the reproduce route builds its payload from this object alone, from nothing re-derived from a scope and nothing read in
    a second transaction."""
    status: str
    detail: str = ""
    issued_sha256: object = None
    origin: object = None

    @property
    def labels(self):
        return real_labels.root_labels(self.origin)


class RealWorkspaceService:
    def __init__(self, schema, *, executor_role, connect, world_inputs=None, lock_timeout_ms=real_tails.DEFAULT_LOCK_TIMEOUT_MS):
        """`connect()` returns a NEW, IDLE connection of the executor role (reconciliation uses it). `world_inputs` (`worlds.WorldInputs`)
        is needed by the REAL branch only."""
        self.schema = identifier(schema)
        self.executor_role = identifier(executor_role)
        self.connect = connect
        self.world_inputs = world_inputs
        self.lock_timeout_ms = lock_timeout_ms

    # ---- tails (the ONLY place a transaction is run) ------------------------------------------------------------------------------
    def _create_tail(self, conn):
        return real_tails.CreateTail(conn, self.schema, lock_timeout_ms=self.lock_timeout_ms)

    def _read_tail(self, conn):
        return real_tails.ReadTail(conn, self.schema, lock_timeout_ms=self.lock_timeout_ms)

    # ---- create -------------------------------------------------------------------------------------------------------------------------
    def create(self, conn, *, owner, body, generation, link):
        """Create a root and its first operation. `body` is the create intent (`real_scoped_contract.validate_intent`); the context it names is
        `body["source_context_id"]`. Returns `Created`, `real_tails.Refused` (a definite refusal: nothing is recorded) or `real_tails.Unknown`
        (no retry; `reconcile` reads the outcome)."""
        try:
            intent = contract.validate_intent(body)
        except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
            return real_tails.Refused("REAL_REQUEST_INVALID")
        operation_id = uuid.UUID(intent["operation_id"])
        root = root_id_for(owner, operation_id)
        context_id = intent["source_context_id"]
        command = command_digest(owner, root, operation_id, context_id, intent)

        def stage(c):
            return self._stage_create(c, owner=owner, root=root, operation_id=operation_id, intent=intent, command=command,
                                      context_id=context_id, generation=generation, link=link)

        outcome = self._create_tail(conn).run(stage, operation_id=operation_id)
        if isinstance(outcome, real_tails.Done):
            archive, replayed = outcome.value
            return Created(root, operation_id, archive, replayed)
        return outcome

    def reconcile(self, *, owner, body, generation, expected=None):
        """Read-only reconciliation of a create that returned UNKNOWN: a NEW connection, the identical command. COMMITTED or UNKNOWN, never a
        rolled-back state (`real_tails.reconcile`)."""
        intent = contract.validate_intent(body)
        operation_id = uuid.UUID(intent["operation_id"])
        root = root_id_for(owner, operation_id)
        context_id = intent["source_context_id"]
        return real_tails.reconcile(self.connect, self.schema, owner=owner, root=root, operation_id=operation_id,
                                    command_sha256=command_digest(owner, root, operation_id, context_id, intent), context_id=context_id,
                                    generation=generation, expected_issued_sha256=None if expected is None else expected.issued_sha256,
                                    expected_response_sha256=None if expected is None else expected.response_sha256,
                                    lock_timeout_ms=self.lock_timeout_ms)

    def _archive(self, conn, owner, operation_id):
        return _archive_of(query_one(conn, self.schema, "rw_archive", (owner, operation_id)))

    def _stage_create(self, conn, *, owner, root, operation_id, intent, command, context_id, generation, link):
        lease = store.admit(conn, self.schema, owner=owner, root=root, context_id=context_id, generation=generation, purpose="EXECUTE_CREATE",
                            operation_id=operation_id, command_sha256=command, new_root=True)
        # Under the operation lock the admission took, the idempotency record is final: an operation that is already sealed and committed is an
        # exact replay (the gateway made this lease read-only). It reads the archive and calls NO service and writes NOTHING.
        if query_one(conn, self.schema, "rw_precheck", (owner, operation_id, command)) is not None:
            return self._archive(conn, owner, operation_id), True
        snapshot = json.loads(lease.snapshot.decode("utf-8"))
        try:
            scope = real_scope.scope_by_snapshot_field(snapshot.get("scope"))
            kind, _w = real_scope.read_install_kind(conn, self.schema)
            real_scope.check_install_kind(scope, kind)
        except real_scope.ScopeError as error:
            raise RealWorkspaceError(error.code) from error
        if intent["expected_release_id"] != snapshot["release"]["release_id"]:
            raise RealWorkspaceError("RW_CONTEXT_BINDING_DIFFERS")
        self._require_link(conn, lease, link)
        if scope.branch == "FICTIONAL":
            self._stage_fictional(conn, lease, scope, snapshot, owner, root, operation_id, intent, link)
        else:
            self._stage_real(conn, lease, scope, snapshot, owner, root, operation_id, intent, link)
        return self._archive(conn, owner, operation_id), False

    def _require_link(self, conn, lease, link):
        from persistence import real_provenance_store as provstore
        if type(link) is not ProvenanceLink:
            raise RealWorkspaceError("RW_LINK_MISSING")
        try:
            provstore.load_guarded(conn, self.schema, self.executor_role, lease, link.context_sha256, expected_members=link.members,
                                   witnesses=link.witnesses)
        except ProvenanceError as error:
            raise RealWorkspaceError(error.code) from error

    # ---- the writes both branches share ------------------------------------------------------------------------------------------------
    def _write_root(self, conn, *, scope, owner, root, operation_id, command, intent, lease, listing_ok, claim_record=None):
        """portfolio, account, the two opening ledger events, then the S2 root row and its first revision. Returns (revision_id, pin, response).
        `claim_record`: the REAL branch's claim record (K), which goes into the stored response (`response_of`)."""
        from psycopg import sql
        origin = scope.origin_fields()
        labels = real_labels.root_labels(origin)
        position = intent["opening_positions"][0]
        listing = uuid.UUID(position["listing_id"])
        if not listing_ok(listing):
            raise real_worlds.WorldError("listing")
        as_of = dt.date.fromisoformat(intent["as_of"])
        account = uuid.uuid5(root, "account")
        conn.execute(sql.SQL("INSERT INTO {}.portfolio(portfolio_id,user_id,reporting_currency) VALUES(%s,%s,%s)").format(sql.Identifier(self.schema)),
                     (root, owner, "USD"))
        conn.execute(sql.SQL("INSERT INTO {}.account(account_id,portfolio_id,name) VALUES(%s,%s,%s)").format(sql.Identifier(self.schema)),
                     (account, root, ACCOUNT_NAME))
        ledger_store.append_batch(conn, [
            LedgerEvent(uuid.uuid5(root, "event:position"), account, EventType.OPENING_POSITION, as_of, USD, listing_id=listing,
                        quantity=Decimal(position["quantity"]), source_reference=POSITION_REFERENCE),
            LedgerEvent(uuid.uuid5(root, "event:cash"), account, EventType.OPENING_CASH, as_of, USD,
                        amount=Money(Decimal(intent["opening_cash"]["amount"]), USD), source_reference=CASH_REFERENCE)])
        pin = ledger_replay_store.current_ledger_version(conn, root)
        revision = uuid.uuid5(root, "revision:" + str(operation_id))
        response = response_of(root=root, intent=intent, origin=origin, labels=labels, operation_id=operation_id, revision=revision, pin=pin,
                               claim_record=claim_record)
        text = canonical_json(response)
        sha = digest(text.encode("utf-8"))
        conn.execute(sql.SQL("INSERT INTO {}.rw_root(portfolio_id,context_id,{},name,account_label,"
                             "opening_label,request_json,snapshot_json,snapshot_sha256,ledger_version,created_at) "
                             "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())").format(
                         sql.Identifier(self.schema), sql.SQL(",").join(sql.Identifier(name) for name in ORIGIN_COLUMNS)),
                     (root, lease.context_id, *(origin[name] for name in ORIGIN_COLUMNS),
                      intent["name"], labels["holding_statement"], labels["origin_statement"], canonical_json(intent), text, sha, pin))
        conn.execute(sql.SQL("INSERT INTO {}.rw_revision(revision_id,portfolio_id,parent_revision_id,operation_id,operation,command_sha256,as_of,"
                             "ledger_version,selection_version,policies_json,policies_state,snapshot_json,snapshot_sha256,created_at) "
                             "VALUES(%s,%s,%s,%s,'CREATE',%s,%s,%s,0,'{{}}','NOT_STATED',%s,%s,now())").format(sql.Identifier(self.schema)),
                     (revision, root, revision, operation_id, command, as_of, pin, text, sha))
        return revision, pin, response

    def _seal(self, conn, *, revision, issued, response, envelope, link):
        from psycopg import sql
        conn.execute(sql.SQL("SELECT {}.rw_seal(%s,%s,%s,%s,%s)").format(sql.Identifier(self.schema)),
                     (revision, issued, encoded(response), encoded(envelope), link.context_sha256))

    # ---- the test-scope create ------------------------------------------------------------------------------------------------------
    def _stage_fictional(self, conn, lease, scope, snapshot, owner, root, operation_id, intent, link):
        import financial_service_integration as integration
        fictional = real_worlds.build_fictional_world(root)
        real_worlds.check_fictional_world(snapshot, scope, fictional)
        if dt.date.fromisoformat(intent["as_of"]) != fictional.as_of:
            raise real_worlds.WorldError("as_of")
        command = command_digest(owner, root, operation_id, lease.context_id, intent)
        revision, pin, response = self._write_root(conn, scope=scope, owner=owner, root=root, operation_id=operation_id, command=command,
                                                    intent=intent, lease=lease, listing_ok=lambda listing: listing == fictional.listing_id)
        world = fictional.world
        pid, xid = transaction_identity(conn)
        kw = dict(port=world.port, resolver=world.resolver, market_conventions=world.market_conventions, conventions=world.perf_conventions,
                  policy=world.policy, as_of=fictional.as_of, reporting_currency="USD", metadata=None, coverage=(),
                  capital_policy=fictional.capital_policy, request=fictional.request)
        fingerprint = integration.fingerprint_context_inputs(**kw)
        integration_context = digest(fingerprint)
        context = integration.LocalFictionalContext(connection=conn, backend_pid=pid, transaction_id=xid, context_id=integration_context,
                                                    generation=lease.generation, snapshot_bytes=fingerprint, **kw)
        request = integration.LocalServiceRequest(integration.LocalServiceKind.CP5_DIVERSIFICATION, owner, root, revision, operation_id, root, pin,
                                                  fictional.as_of, integration_context, lease.generation)
        try:
            result = integration.issue_local_service(conn, request=request, context=context)
        except integration.LocalServiceRefusal as refusal:
            raise real_tails.ServiceRefusal(refusal.code, refusal.issued_bytes) from refusal
        envelope = {"schema": "finweb.fictional.issued_envelope/1", "scope": scope.name, FLAG: scope.origin_fields()[FLAG], "owner_id": str(owner),
                    "root_id": str(root), "operation_id": str(operation_id), "revision_id": str(revision), "ledger_pin": pin,
                    "context_id": lease.context_id, "generation": lease.generation, "issued_sha256": result.issued_sha256,
                    "response_sha256": digest(encoded(response)), "manifest_id": result.manifest_id, "result_digest": result.result_digest,
                    "question_sha256": result.question_sha256, "binding_sha256": result.binding_sha256, "question_hex": result.question_bytes.hex(),
                    "binding_hex": result.binding_bytes.hex(), "selector": integration.LocalServiceKind.CP5_DIVERSIFICATION.value,
                    "family": result.family, "engine_id": result.engine_id}
        self._seal(conn, revision=revision, issued=result.issued_bytes, response=response, envelope=envelope, link=link)

    # ---- the REAL branch's create -------------------------------------------------------------------------------------------------------
    def _stage_real(self, conn, lease, scope, snapshot, owner, root, operation_id, intent, link):
        from performance.manifest import ComputationResult
        from performance_service import service as performance_service
        world = real_worlds.build_real_world(conn, snapshot, scope, self.world_inputs)
        command = command_digest(owner, root, operation_id, lease.context_id, intent)
        # O-7 (PD-0082 Q1): the claim record (K) is copied from the values this computation uses (the snapshot, the release's files, the lookup of the one holding), and is
        # written into the stored response, which the seal stores with the root. A build failure is held until the service has run, so that the service's own refusal of
        # a result it did not compute from real data (FF1-C08) keeps its place; it is then a refusal of the create (below), never a root without a record.
        as_of = dt.date.fromisoformat(intent["as_of"])
        try:
            record, record_error = self._claim_record_of(conn, snapshot, world, uuid.UUID(intent["opening_positions"][0]["listing_id"]), as_of), None
        except claim_render.ClaimRenderError as error:
            record, record_error = None, error
        revision, pin, response = self._write_root(conn, scope=scope, owner=owner, root=root, operation_id=operation_id, command=command,
                                                    intent=intent, lease=lease, listing_ok=lambda listing: True, claim_record=record)
        result = performance_service.compute_for_portfolio(
            conn, root, as_of, USD, world.port, world.resolver, world.market_conventions, world.perf_conventions,
            policy=world.policy, ledger_version=pin)
        if type(result) is not ComputationResult:
            raise real_tails.ServiceRefusal(getattr(result, "code", "RW_SERVICE_RESULT_INVALID"))
        issued = result.canonical_json().encode("utf-8")
        if real_worlds.service_refused(result):
            # FF1-C08: the service's refusal is never turned into a result and never bypassed. Whole rollback; nothing is addressable.
            raise real_tails.ServiceRefusal(real_worlds.REFUSAL_CODE, issued)
        self._require_claim_block(response, issued, pin, record_error)
        envelope = real_envelope(scope=scope, owner=owner, root=root, operation_id=operation_id, revision=revision, pin=pin, lease=lease,
                                 issued=issued, response=response, result=result)
        self._seal(conn, revision=revision, issued=issued, response=response, envelope=envelope, link=link)

    def _claim_record_of(self, conn, snapshot, world, listing_id, as_of):
        """The claim record (K) from this lease's own reads: the release's files (lease-checked) and the lookup of the holding on the world's port."""
        return claim_records.build_claim_record(snapshot=snapshot, files=real_worlds.read_claim_files(conn, snapshot), port=world.port,
                                                conventions=world.market_conventions, listing_id=listing_id, as_of=as_of)

    @staticmethod
    def _require_claim_block(response, issued, pin, record_error):
        """The pre-seal check (PD-0082 Q3): the claim block must be renderable from exactly what the seal will store, or the create is refused here, inside
        its transaction, and rolls back whole. A root whose block cannot be shown is never committed (no real result is shown without its block, P3)."""
        if record_error is not None:
            raise RealWorkspaceError(CLAIM_RECORD_REFUSED, record_error.code)
        try:
            claim_records.block_of(response["origin"], json.loads(issued.decode("utf-8")), response, pin)
        except claim_render.ClaimRenderError as error:
            raise RealWorkspaceError(CLAIM_RECORD_REFUSED, error.code) from error

    # ---- read, reproduce, list ---------------------------------------------------------------------------------------------------------
    def archive_read(self, conn, *, owner, root, operation_id, context_id, generation):
        """Admit `ARCHIVE_READ` at `generation`, read the bundle, deliver it after the COMMIT. No service is called."""
        def body(c):
            store.admit(c, self.schema, owner=owner, root=root, context_id=context_id, generation=generation, purpose="ARCHIVE_READ",
                        operation_id=operation_id, command_sha256=real_tails.NO_COMMAND)
            return self._archive(c, owner, operation_id)
        return self._read_tail(conn).run(body, operation_id=operation_id)

    def reproduce(self, conn, *, owner, root, operation_id, context_id, generation):
        """Admit `EXECUTE_REPRODUCE`, read the bundle, run the SAME service again on the same inputs and compare the complete issued bytes."""
        def body(c):
            lease = store.admit(c, self.schema, owner=owner, root=root, context_id=context_id, generation=generation, purpose="EXECUTE_REPRODUCE",
                                operation_id=operation_id, command_sha256=real_tails.NO_COMMAND)
            archive = self._archive(c, owner, operation_id)
            snapshot = json.loads(lease.snapshot.decode("utf-8"))
            scope = real_scope.scope_by_snapshot_field(snapshot.get("scope"))
            if scope.branch == "FICTIONAL":
                return self._reproduce_fictional(c, lease, scope, snapshot, owner, root, operation_id, archive)
            return self._reproduce_real(c, lease, scope, snapshot, owner, root, archive)
        return self._read_tail(conn).run(body, operation_id=operation_id)

    def _reproduce_fictional(self, conn, lease, scope, snapshot, owner, root, operation_id, archive):
        import financial_service_integration as integration
        fictional = real_worlds.build_fictional_world(root)
        real_worlds.check_fictional_world(snapshot, scope, fictional)
        envelope = json.loads(archive.envelope)
        world = fictional.world
        pid, xid = transaction_identity(conn)
        kw = dict(port=world.port, resolver=world.resolver, market_conventions=world.market_conventions, conventions=world.perf_conventions,
                  policy=world.policy, as_of=fictional.as_of, reporting_currency="USD", metadata=None, coverage=(),
                  capital_policy=fictional.capital_policy, request=fictional.request)
        fingerprint = integration.fingerprint_context_inputs(**kw)
        integration_context = digest(fingerprint)
        # reproduction uses the ORIGINAL generation binding (the question names it) under the current generation's own read lease
        context = integration.LocalFictionalContext(connection=conn, backend_pid=pid, transaction_id=xid, context_id=integration_context,
                                                    generation=envelope["generation"], snapshot_bytes=fingerprint, **kw)
        request = integration.LocalServiceRequest(integration.LocalServiceKind(envelope["selector"]), owner, root, archive.revision_id, operation_id,
                                                  root, archive.ledger_pin, fictional.as_of, integration_context, envelope["generation"])
        again = integration.reproduce_local_service(conn, request=request, context=context, saved_issued_bytes=archive.issued,
                                                    expected_issued_sha256=archive.issued_sha256)
        return Reproduction(again.status, again.detail, again.issued_sha256, archive.origin)

    def _reproduce_real(self, conn, lease, scope, snapshot, owner, root, archive):
        from performance.manifest import ComputationResult
        from performance_service import service as performance_service
        world = real_worlds.build_real_world(conn, snapshot, scope, self.world_inputs)
        stored = archive.response_obj
        as_of = dt.date.fromisoformat(stored["as_of"])
        result = performance_service.compute_for_portfolio(
            conn, root, as_of, USD, world.port, world.resolver, world.market_conventions,
            world.perf_conventions, policy=world.policy, ledger_version=archive.ledger_pin)
        if type(result) is not ComputationResult:
            return Reproduction("SOURCE_REFUSED", str(getattr(result, "code", "")), None, archive.origin)
        issued = result.canonical_json().encode("utf-8")
        if real_worlds.service_refused(result):
            return Reproduction("SOURCE_REFUSED", real_worlds.REFUSAL_CODE, digest(issued), archive.origin)
        if issued != archive.issued:
            return Reproduction("RESULT_DIFFERS", "complete canonical issued answer differs", digest(issued), archive.origin)
        # O-7 (PD-0082 Q1): the claim record is rebuilt from the same inputs and compared byte for byte with the stored one, so the reproduce covers the copied facts too.
        try:
            rebuilt = self._claim_record_of(conn, snapshot, world, uuid.UUID(stored["opening_positions"][0]["listing_id"]), as_of)
        except claim_render.ClaimRenderError:
            return Reproduction("RESULT_DIFFERS", "the claim record cannot be rebuilt", digest(issued), archive.origin)
        if claim_records.RECORD_KEY not in stored or claim_records.record_bytes(rebuilt) != claim_records.record_bytes(stored[claim_records.RECORD_KEY]):
            return Reproduction("RESULT_DIFFERS", "claim record differs", digest(issued), archive.origin)
        return Reproduction("REPRODUCED", "", digest(issued), archive.origin)

    def roots_of(self, conn, *, owner):
        """Step 1 of the list alone (F1 R7): the owner's own root identifiers `(root, context_id, generation)` from `rw_list_roots`, with no lease and
        nothing else read. A route uses it to answer "is this root the caller's?" BEFORE it decodes anything else (a foreign or unknown root is one
        generic 404). Returns `real_tails.Done`, `Refused` or `Unknown`."""
        return self._read_tail(conn).run(lambda c: store.list_roots(c, self.schema, owner))

    def list_roots(self, conn, *, owner):
        """The owner's roots (design 2.4): step 1 the identifiers (`rw_list_roots`, no lease), step 2 one short read transaction per root under its
        own `ARCHIVE_READ` admission. A refused admission is listed with its code and none of the stored fields. Returns the contract's entries."""
        ids = self._read_tail(conn).run(lambda c: store.list_roots(c, self.schema, owner))
        if not isinstance(ids, real_tails.Done):
            return ids
        entries = []
        for root, context_id, generation in ids.value:
            outcome = self._read_tail(conn).run(self._entry_body(owner, root, context_id, generation))
            if isinstance(outcome, real_tails.Done):
                entries.append(outcome.value)
            elif isinstance(outcome, real_tails.Refused):
                entries.append(contract.list_entry(root_id=root, context_id=context_id, status=outcome.code if outcome.code in contract.ERRORS else "REAL_UNAVAILABLE"))
            else:
                entries.append(contract.list_entry(root_id=root, context_id=context_id, status="REAL_UNAVAILABLE"))
        return real_tails.Done(entries)

    def _entry_body(self, owner, root, context_id, generation):
        from psycopg import sql

        def body(c):
            store.admit(c, self.schema, owner=owner, root=root, context_id=context_id, generation=generation, purpose="ARCHIVE_READ",
                        operation_id=real_tails.entry_operation_id(root, generation, "list"), command_sha256=real_tails.NO_COMMAND)
            row = c.execute(sql.SQL("SELECT {},created_at FROM {}.rw_root WHERE portfolio_id=%s").format(
                sql.SQL(",").join(sql.Identifier(name) for name in ORIGIN_COLUMNS), sql.Identifier(self.schema)), (root,)).fetchone()
            if row is None:
                raise RealWorkspaceError("RW_NOT_FOUND")
            origin = dict(zip(ORIGIN_COLUMNS, row))
            # The root's create operation id, read from the stored revision under the SAME admission (the row policy filters it like rw_root). A root has
            # exactly one revision (operation CREATE; the root id is a function of owner and operation id), so there is no "latest" to choose.
            revision = c.execute(sql.SQL("SELECT operation_id FROM {}.rw_revision WHERE portfolio_id=%s ORDER BY revision_seq LIMIT 1").format(
                sql.Identifier(self.schema)), (root,)).fetchone()
            if revision is None:
                raise RealWorkspaceError("RW_NOT_FOUND")
            return contract.list_entry(root_id=root, operation_id=revision[0], context_id=context_id, generation=generation,
                                       created_at=row[len(ORIGIN_COLUMNS)].isoformat(), origin=origin)
        return body


def real_envelope(*, scope, owner, root, operation_id, revision, pin, lease, issued, response, result):
    """The gateway's envelope around the performance service's issued bytes, in the key set `rw_check_real` accepts (R3). Pure."""
    return {"schema": "finweb.real.issued_envelope/1", "scope": scope.name, FLAG: scope.origin_fields()[FLAG], "owner_id": str(owner), "root_id": str(root),
            "operation_id": str(operation_id), "revision_id": str(revision), "ledger_pin": pin, "context_id": lease.context_id,
            "generation": lease.generation, "issued_sha256": digest(issued), "response_sha256": digest(encoded(response)),
            "manifest_id": result.manifest.manifest_id, "result_digest": result.result_digest}
