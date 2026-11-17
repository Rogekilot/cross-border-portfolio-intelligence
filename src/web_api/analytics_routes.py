"""Session/CSRF protected, read-only owned analytics endpoints."""
from fastapi import Request

from web_api.analytics_composer import SCHEMA,bounded,compose,reproduce,resolve_proof
from web_api.analytics_context import AnalyticsError,LIMITS,load_context
from web_api.analytics_requests import AnalyticsProofRequest,AnalyticsQuestion
from web_api.app import response


def install_analytics_routes(app,*,store,world,authenticated,database):
    @app.exception_handler(AnalyticsError)
    async def analytics_error(request,error):
        return response(dict(schema_version=SCHEMA,error=dict(code=error.code,detail=error.detail,kind=error.kind)),error.status)

    def perform(user_id,portfolio_id,question,proof=None,action="evaluate"):
        with store.connect() as conn,conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            group=None if proof is None else proof["result_id"].split(":")[1]
            context=load_context(conn,store,world,user_id,portfolio_id,question,group=group)
            try:
                payload,typed=compose(context,question,group=group)
                if action=="evaluate":
                    return payload
                wrapper=resolve_proof(payload,proof)
                if action=="reproduce":
                    return reproduce(context,question,wrapper,typed[wrapper["result_id"]],proof["expected_result_digest"])
                if proof["expected_result_digest"]!=wrapper["engine_result"]["result_digest"]:
                    raise AnalyticsError(409,"ANALYTICS_BINDING_DIFFERS","The requested evidence answer digest differs from its issued result","BINDING")
                ident=str(context.portfolio_id)
                revision=str(context.record["revision_id"])
                return bounded(dict(schema_version=SCHEMA,portfolio_id=ident,revision_id=revision,question=question,result=wrapper,
                    ledger_reference=dict(portfolio_id=ident,revision_id=revision,ledger_version=context.record["ledger_version"],
                        workspace_path="/api/v1/portfolios/"+ident+"/workspace?revision_id="+revision),limits=LIMITS.copy()))
            except AnalyticsError:
                raise
            except (ValueError,TypeError,KeyError,ArithmeticError,RuntimeError):
                raise AnalyticsError(503,"ANALYTICS_ENGINE_ERROR","The existing engine or source context refused this computation; no replacement value is issued","ENGINE") from None

    @app.post("/api/v1/portfolios/{portfolio_id}/analytics/evaluate")
    def evaluate(portfolio_id:str,body:AnalyticsQuestion,request:Request):
        _,user=authenticated(request,mutation=True)
        return response(database(lambda:perform(user["user_id"],portfolio_id,body.model_dump())))

    @app.post("/api/v1/portfolios/{portfolio_id}/analytics/evidence")
    def evidence(portfolio_id:str,body:AnalyticsProofRequest,request:Request):
        _,user=authenticated(request,mutation=True)
        proof=body.model_dump()
        return response(database(lambda:perform(user["user_id"],portfolio_id,proof["question"],proof,"evidence")))

    @app.post("/api/v1/portfolios/{portfolio_id}/analytics/reproduce")
    def reproduce_result(portfolio_id:str,body:AnalyticsProofRequest,request:Request):
        _,user=authenticated(request,mutation=True)
        proof=body.model_dump()
        return response(database(lambda:perform(user["user_id"],portfolio_id,proof["question"],proof,"reproduce")))
