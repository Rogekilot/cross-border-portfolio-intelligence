"""F1 R7: the REAL-MODE APP. The scoped contract reviewed at R5 (`real_scoped_contract`, design 2.4) installed on its four routes, behind the
account session, and nothing else.

WHAT IS INSTALLED. `create_real_mode_app` builds ONE app that answers

    POST /api/real/v1/roots                                               create    (EXECUTE_CREATE)
    GET  /api/real/v1/roots                                               list      (ARCHIVE_READ, one admission per root)
    GET  /api/real/v1/roots/{root_id}/operations/{operation_id}           read      (ARCHIVE_READ)
    POST /api/real/v1/roots/{root_id}/operations/{operation_id}/reproduce reproduce (EXECUTE_REPRODUCE)

plus the account session routes (`/api/v1/auth/*`, `install_account_routes(auth_only=True)`: session, register, login, logout and nothing that
stores or computes a portfolio). Every other path under `/api/` is a CLOSED refusal (`REAL_MODE_ROUTE_CLOSED`, 503): E5's closed contract
(`real_workspace_contract`, `real_workspace_routes`), E1's readiness routes, the saved-sandbox, guarded, CSV and analytics routes are not
installed here, so one URL is never answered by both contracts in one app. A static test checks that none of those modules is imported.

THE WIRE SHAPES ARE THE CONTRACT'S. Every response body is built by `real_scoped_contract` from values this module reads from the STORED bundle
(`Archive.origin` is the stored response's origin; the labels are derived from it; the claim block is rendered from it). Nothing is hard-coded
here: no origin value, no mode string, no flag. The contract re-renders the claim block from its slots and refuses anything that is not the
rendering (TR5-L5), so a block this module got wrong is refused and never sent.

FOREIGN ROOTS. A read or a reproduce first asks `service.roots_of(owner)` (`rw_list_roots`, identifiers only) whether the root is the caller's. A
root that is not, a root that does not exist and a path that is not a canonical identifier are ONE answer, `RW_NOT_FOUND` 404, with the same
bytes, and it is given BEFORE the request body is decoded and before anything is read from the stored bundle.

NO NUMBER IS COMPUTED HERE. The result is the stored issued document, parsed and passed through. The claim lineage of a `REAL_SOURCE` root is
read by `lineage_of` (injected; the launcher passes `marketdata.claim_record.lineage_of`, O-7, which copies stored values from the root's issued document,
stored response and claim record). The default refuses (`unbuilt_lineage`): an app built without an extractor never renders a real root with a hole, and the
root's read is `REAL_UNAVAILABLE`. A `TEST` root never reads lineage.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import uuid

import psycopg
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool

from marketdata import claim_render
from persistence import real_tails
from persistence.real_workspace_context import RealWorkspaceError
from web_api import real_scoped_contract as contract
from web_api.app import LocalBoundary, Refusal, refused, response

# TR7-L-6: cookies are scoped by host and path, not by port, so the real-mode app (Vite 5175) and the fictional app (5173) share 127.0.0.1. Distinct names keep
# either app's session and CSRF token from being sent to, or read by, the other.
REAL_SESSION_COOKIE = "finweb_real_session"
REAL_BOOTSTRAP_COOKIE = "finweb_real_csrf"

LOG = logging.getLogger("finweb.real_mode")
CLOSED_CODE = "REAL_MODE_ROUTE_CLOSED"
ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


@dataclass(frozen=True)
class ContextPin:
    """One context the app creates under: its content-hash id, the generation the launcher was started with, and the provenance link the create
    stands on (`real_service.service.ProvenanceLink`). The launcher reads these from the owner's contexts file; no request carries them."""
    context_id: str
    generation: int
    link: object


def unbuilt_lineage(_archive):
    """The default lineage extractor, for an app built without one: a `REAL_SOURCE` root is not rendered with a hole, so the read is refused. The extractor
    of the real-mode launcher is `marketdata.claim_record.lineage_of` (O-7)."""
    raise claim_render.ClaimRenderError("CLAIM_LINEAGE_UNBUILT", "no lineage extractor was given to this app")


def canonical_uuid(text):
    """The UUID a path segment spells, or None unless it is the canonical lowercase hyphenated form."""
    try:
        value = uuid.UUID(text)
    except (ValueError, AttributeError, TypeError):
        return None
    return value if str(value) == text else None


def parse_empty_object(raw):
    """The body of a reproduce: the empty JSON object, exactly. Anything else is `REAL_REQUEST_INVALID`."""
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError):
        raise contract.invalid_request() from None
    if type(value) is not dict or value:
        raise contract.invalid_request()
    return value


def create_real_mode_app(*, service, contexts, account_store, connect, settings, origins, lineage_of=unbuilt_lineage):
    """The real-mode app. `service` is a `real_service.service.RealWorkspaceService`; `contexts` maps a context id to its `ContextPin`; `connect()`
    returns a NEW, IDLE executor connection; `account_store` is a `WebAccountStore` over the account role; `settings` the `AuthSettings`."""
    from fastapi import FastAPI
    from web_api.account_routes import install_account_routes
    app = FastAPI(title="Fin Web real mode", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(LocalBoundary, allowed_origins=frozenset(origins))

    @app.exception_handler(Refusal)
    async def refusal_handler(request, error):
        return refused(error.status, error.code, error.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, error):
        return refused(422, "INVALID_REQUEST", "Invalid request")                  # nothing of the input is reflected

    authenticated = install_account_routes(app, store=account_store, world=None, settings=settings, allowed_origins=frozenset(origins),
                                           auth_only=True, cookie_path="/api", session_cookie=REAL_SESSION_COOKIE,
                                           bootstrap_cookie=REAL_BOOTSTRAP_COOKIE)
    install_real_mode_routes(app, service=service, contexts=contexts, connect=connect, authenticated=authenticated, lineage_of=lineage_of)

    @app.api_route("/api/{path:path}", methods=ALL_METHODS)
    async def closed(request: Request, path: str):
        return refused(503, CLOSED_CODE, "This route is closed in real mode")

    return app


def install_real_mode_routes(app, *, service, contexts, connect, authenticated, lineage_of=unbuilt_lineage):
    @app.exception_handler(contract.ContractRefusal)
    async def contract_refusal(request, error):
        return response(contract.refusal_payload(error), error.status)

    not_found = lambda: contract.ContractRefusal("RW_NOT_FOUND")        # noqa: E731 - one answer for a foreign, an unknown and a malformed id

    def owner_of(request, mutation=False):
        return uuid.UUID(authenticated(request, mutation=mutation)[1]["user_id"])

    def run(work, *, connected=True):
        """Run `work(conn)` on a NEW executor connection (`work()` without one when `connected` is false), in a worker thread. Only contract
        refusals leave: a gateway code becomes its public code (or `REAL_UNAVAILABLE`), and every other failure is `REAL_UNAVAILABLE` with nothing
        reflected."""
        conn = None
        try:
            if connected:
                conn = connect()
                return work(conn)
            return work()
        except contract.ContractRefusal:
            raise
        except RealWorkspaceError as error:
            raise contract.ContractRefusal(error.code) from None
        except claim_render.ClaimRenderError as error:
            LOG.error("real-mode claim render refused: %s", error.code)
            raise contract.ContractRefusal("REAL_UNAVAILABLE") from None
        except Exception as error:      # noqa: BLE001 - fail closed; the class name is logged, nothing else
            LOG.error("real-mode request failed: %s", type(error).__name__)
            raise contract.ContractRefusal("REAL_UNAVAILABLE") from None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except psycopg.Error:
                    pass

    def unwrap(outcome):
        if isinstance(outcome, real_tails.Done):
            return outcome.value
        if isinstance(outcome, real_tails.Refused):
            raise contract.ContractRefusal(outcome.code)
        raise contract.ContractRefusal("REAL_UNAVAILABLE")                          # an unknown read has no value to deliver

    def locate(conn, owner, root_text):
        """(root, context_id, generation) when `root_text` is one of the CALLER's roots, else the one generic 404."""
        root = canonical_uuid(root_text)
        if root is None:
            raise not_found()
        for found, context_id, generation in unwrap(service.roots_of(conn, owner=owner)):
            if found == root:
                return found, context_id, generation
        raise not_found()

    def block_for(origin, archive):
        lineage = lineage_of(archive) if origin.get("market_origin") == claim_render.REAL_SOURCE else None
        return claim_render.render_claim_block(origin, lineage)

    def stored_result(archive):
        result = json.loads(archive.issued.decode("utf-8"))
        if type(result) is not dict:
            raise contract.ContractRefusal("REAL_UNAVAILABLE")
        return result

    def committed(root, operation_id, archive, *, replayed=None):
        origin, labels = archive.origin, archive.labels
        common = dict(root_id=root, operation_id=operation_id, revision_id=archive.revision_id, ledger_pin=archive.ledger_pin, origin=origin,
                      labels=labels, response_sha256=archive.response_sha256, issued_sha256=archive.issued_sha256, result=stored_result(archive),
                      claim_limits=block_for(origin, archive))
        if replayed is not None:
            return contract.committed_payload(replayed=replayed, **common)
        # The generation the root was created under: the STORED sealed envelope (already loaded by the archive read, whose gateway call checked it against the
        # artifact's own generation). Not the context's head, not a lease. A malformed envelope is a refusal, never a guess.
        try:
            created_under = json.loads(archive.envelope.decode("utf-8"))["generation"]
        except (ValueError, KeyError, TypeError, AttributeError):
            raise contract.ContractRefusal("REAL_UNAVAILABLE") from None
        return contract.read_payload(created_under_generation=created_under, **common)

    # ---- create ----------------------------------------------------------------------------------------------------------------------
    @app.post("/api/real/v1/roots")
    async def create(request: Request):
        owner = await run_in_threadpool(owner_of, request, True)
        if request.query_params:
            raise contract.invalid_request()
        intent = contract.parse_intent(await request.body())
        pin = contexts.get(intent["source_context_id"])
        if pin is None:
            raise not_found()

        def work(conn):
            return service.create(conn, owner=owner, body=intent, generation=pin.generation, link=pin.link)
        outcome = await run_in_threadpool(run, work)
        if isinstance(outcome, real_tails.Unknown):
            return response(contract.unknown_payload(intent["operation_id"]), 503)
        if isinstance(outcome, real_tails.Refused):
            raise contract.ContractRefusal(outcome.code)
        # TR7R-L-1: the create has COMMITTED (the outcome is `Created`). From here a failure to build the response (the unbuilt lineage, a read error, a render
        # error, anything) is NOT a refusal: the root exists, so a coded refusal would tell the client the operation id is unused and every further click would
        # commit another root. It is the contract's unknown outcome; the client repeats the identical command and the repeat replays the stored root.
        try:
            payload = await run_in_threadpool(lambda: committed(outcome.root_id, outcome.operation_id, outcome.archive, replayed=outcome.replayed))
        except Exception as error:      # noqa: BLE001 - fail to "unknown", never to "refused"; the class name is logged, nothing else
            LOG.error("real-mode create committed but its response could not be built: %s", getattr(error, "code", type(error).__name__))
            return response(contract.unknown_payload(intent["operation_id"]), 503)
        return response(payload, 200 if outcome.replayed else 201)

    # ---- list ------------------------------------------------------------------------------------------------------------------------
    @app.get("/api/real/v1/roots")
    async def list_roots(request: Request):
        owner = await run_in_threadpool(owner_of, request)
        if request.query_params:
            raise contract.invalid_request()
        entries = await run_in_threadpool(run, lambda conn: unwrap(service.list_roots(conn, owner=owner)))
        return response(contract.list_payload(entries))

    # ---- read ------------------------------------------------------------------------------------------------------------------------
    @app.get("/api/real/v1/roots/{root_id}/operations/{operation_id}")
    async def read(root_id: str, operation_id: str, request: Request):
        owner = await run_in_threadpool(owner_of, request)
        if request.query_params:
            raise contract.invalid_request()

        def work(conn):
            root, context_id, generation = locate(conn, owner, root_id)                      # BEFORE anything is decoded
            operation = canonical_uuid(operation_id)
            if operation is None:
                raise not_found()
            archive = unwrap(service.archive_read(conn, owner=owner, root=root, operation_id=operation, context_id=context_id, generation=generation))
            if archive.response_obj.get("portfolio_id") != str(root):
                raise not_found()                                                               # an operation of another root of the same owner
            return committed(root, operation, archive)
        return response(await run_in_threadpool(run, work))

    # ---- reproduce -------------------------------------------------------------------------------------------------------------------
    @app.post("/api/real/v1/roots/{root_id}/operations/{operation_id}/reproduce")
    async def reproduce(root_id: str, operation_id: str, request: Request):
        owner = await run_in_threadpool(owner_of, request, True)
        if request.query_params:
            raise contract.invalid_request()
        raw = await request.body()               # read, NOT decoded: the ownership answer below comes first

        def work(conn):
            root, context_id, generation = locate(conn, owner, root_id)
            operation = canonical_uuid(operation_id)
            if operation is None:
                raise not_found()
            parse_empty_object(raw)
            done = unwrap(service.reproduce(conn, owner=owner, root=root, operation_id=operation, context_id=context_id, generation=generation))
            return contract.reproduce_payload(root_id=root, operation_id=operation, origin=done.origin, labels=done.labels, status=done.status,
                                              detail=done.detail, issued_sha256=done.issued_sha256)
        return response(await run_in_threadpool(run, work))
