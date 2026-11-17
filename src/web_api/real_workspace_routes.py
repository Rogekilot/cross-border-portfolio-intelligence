"""Permanent authenticated contract/refusal routes; no real workspace store."""
from fastapi import Request
from starlette.concurrency import run_in_threadpool

from web_api.app import response
from web_api.real_workspace_contract import (ClosedCatalogue, ContractRefusal,
    MAX_HTTP_BYTES, contract_payload, invalid_request, parse_intent, refuse_intent, refusal_payload)


def install_real_workspace_routes(app, *, authenticated, catalogue=None):
    catalogue = ClosedCatalogue() if catalogue is None else catalogue

    @app.exception_handler(ContractRefusal)
    async def contract_error(request, error):
        return response(refusal_payload(error), error.status)

    @app.get("/api/v1/real-workspace-contract")
    async def workspace_contract(request: Request):
        await run_in_threadpool(authenticated, request)
        if request.scope.get("query_string", b""):
            raise invalid_request()
        async for chunk in request.stream():
            if chunk:
                raise invalid_request()
        return response(contract_payload(catalogue))

    @app.post("/api/v1/real-workspace-intents")
    async def workspace_intent(request: Request):
        await run_in_threadpool(authenticated, request, mutation=True)
        if request.scope.get("query_string", b""):
            raise invalid_request()
        raw = bytearray()
        async for chunk in request.stream():
            if len(chunk) > MAX_HTTP_BYTES - len(raw):
                raise invalid_request()
            raw.extend(chunk)
        body = parse_intent(bytes(raw))
        refuse_intent(catalogue, body)
        raise RuntimeError("closed workspace intent unexpectedly returned")
