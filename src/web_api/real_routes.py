"""Account-only E1 metadata capability and zero-write refusal endpoints."""
from fastapi import Request
from starlette.concurrency import run_in_threadpool

from web_api.app import response
from web_api.real_requests import parse_create_gate
from web_api.real_source_contexts import MetadataProvider, RealSourceError, SCHEMA, real_capabilities


def install_real_source_routes(app, *, authenticated, database, provider=None):
    # Authentication already uses the injected database boundary. No new store/SQL.
    provider = MetadataProvider() if provider is None else provider

    @app.exception_handler(RealSourceError)
    async def real_source_error(request, error):
        return response(dict(schema_version=SCHEMA, error=dict(code=error.code, detail=error.detail, kind=error.kind)), error.status)

    @app.get("/api/v1/real-source-contexts")
    async def source_contexts(request: Request):
        await run_in_threadpool(authenticated, request)
        if request.query_params:
            raise RealSourceError(422, "INVALID_REQUEST", "E1 metadata GET accepts no query or body", "REQUEST")
        async for chunk in request.stream():
            if chunk:
                raise RealSourceError(422, "INVALID_REQUEST", "E1 metadata GET accepts no query or body", "REQUEST")
        return response(await run_in_threadpool(real_capabilities, provider))

    @app.post("/api/v1/real-portfolios")
    async def real_portfolio_gate(request: Request):
        await run_in_threadpool(authenticated, request, mutation=True)
        if request.query_params:
            raise RealSourceError(422, "INVALID_REQUEST", "E1 intent accepts no query fields", "REQUEST")
        body = parse_create_gate(await request.body())  # Existing middleware enforces32768 actual bytes.
        await run_in_threadpool(provider.refuse, body)
        raise RuntimeError("E1 provider unexpectedly accepted creation")
