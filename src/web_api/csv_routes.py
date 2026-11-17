"""Session/Origin/CSRF boundary for exact-source account CSV workflows."""
import secrets

from fastapi import Request
from fastapi.responses import Response

from persistence.web_account_store import AccountStoreError
from persistence.web_csv_store import CsvImportStore
from web_api.app import response
from web_api.csv_requests import CommitCsvRequest,ImportProposal,ParseCsvRequest


def install_csv_routes(app,*,store,world,authenticated,database):
    importer=CsvImportStore(store,world,secrets.token_bytes(32))

    @app.post("/api/v1/portfolios/{portfolio_id}/imports/parse")
    def parse(portfolio_id:str,body:ParseCsvRequest,request:Request):
        _,user=authenticated(request,mutation=True)
        return response(database(lambda:importer.parse(user["user_id"],portfolio_id,body.model_dump())))

    @app.post("/api/v1/portfolios/{portfolio_id}/imports/preview")
    def preview(portfolio_id:str,body:ImportProposal,request:Request):
        _,user=authenticated(request,mutation=True)
        return response(database(lambda:importer.preview(user["user_id"],portfolio_id,body.model_dump())))

    @app.post("/api/v1/portfolios/{portfolio_id}/imports/commit")
    def commit(portfolio_id:str,body:CommitCsvRequest,request:Request):
        _,user=authenticated(request,mutation=True)
        return response(database(lambda:importer.commit(user["user_id"],portfolio_id,body.proposal.model_dump(),body.preview_receipt)),201)

    @app.get("/api/v1/portfolios/{portfolio_id}/imports")
    def reports(portfolio_id:str,request:Request,cursor:str|None=None):
        _,user=authenticated(request)
        return response(database(lambda:importer.list(user["user_id"],portfolio_id,cursor)))

    @app.get("/api/v1/portfolios/{portfolio_id}/imports/{report_id}")
    def report(portfolio_id:str,report_id:str,request:Request):
        _,user=authenticated(request)
        return response(database(lambda:importer.get(user["user_id"],portfolio_id,report_id)))

    def download(portfolio_id,text,media_type,identity,identity_type,format):
        filename="finweb-"+identity_type+"-"+identity+"."+format
        return Response(text,media_type=media_type,headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff",
            "Content-Disposition":"attachment; filename=\""+filename+"\"","X-Finweb-Portfolio-Id":portfolio_id,
            "X-Finweb-"+("Report" if identity_type=="report" else "Revision")+"-Id":identity})

    @app.get("/api/v1/portfolios/{portfolio_id}/imports/{report_id}/export")
    def report_export(portfolio_id:str,report_id:str,request:Request,format:str="json"):
        _,user=authenticated(request)
        if format not in ("json","csv"):
            raise AccountStoreError(422,"CSV_EXPORT_FORMAT","Choose json or csv")
        text,media=database(lambda:importer.export_report(user["user_id"],portfolio_id,report_id,format))
        # The owned read validated canonical UUIDs before they reach headers.
        import uuid
        return download(str(uuid.UUID(portfolio_id)),text,media,str(uuid.UUID(report_id)),"report",format)

    @app.get("/api/v1/portfolios/{portfolio_id}/exports/{kind}")
    def portfolio_export(portfolio_id:str,kind:str,request:Request,revision_id:str,format:str="json"):
        _,user=authenticated(request)
        if kind not in ("holdings","transactions") or format not in ("json","csv"):
            raise AccountStoreError(422,"CSV_EXPORT_FORMAT","Choose holdings/transactions and json/csv")
        text,media=database(lambda:importer.export_portfolio(user["user_id"],portfolio_id,revision_id,kind,format))
        import uuid
        return download(str(uuid.UUID(portfolio_id)),text,media,str(uuid.UUID(revision_id)),"revision",format)
