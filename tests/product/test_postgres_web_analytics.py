"""Actual PG plus in-process ASGI; no shared API, external HTTP or new data."""
import json
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))

from domain.catalogs import CatalogError
from marketdata.canonical import canonical_json
from persistence.web_csv_store import CsvImportStore
from tests.product import test_postgres_csv_import as csv_kit
from tests.product import test_postgres_web_workspace as kit
from tests.product.test_postgres_web_auth import Client,SKIP
from tests.product.test_web_analytics import proof,question
from web_api.analytics_context import LIMITS
from web_api.app import create_app
from web_api.auth import AuthSettings


@unittest.skipIf(bool(SKIP),SKIP)
class PostgresAnalyticsTests(unittest.TestCase):
    setUpClass=classmethod(kit.PostgresWorkspaceTests.setUpClass.__func__)

    def setUp(self):
        kit.PostgresWorkspaceTests.setUp(self)
        self.csv=CsvImportStore(self.store,self.world,b"D"*32)
        with patch("web_api.app.SyntheticWorld",return_value=self.world):
            self.app=create_app(account_store=self.store,auth_settings=AuthSettings.local(),enable_saved_synthetic=True)
        self.client=Client(self.app,"127.0.0.63")
        self.client.cookies["finweb_session"]=self.store.start_session(self.user,3600)
        self.client.call("GET","/api/v1/auth/session")

    def q(self,family="PERFORMANCE_WINDOW",**changes):
        return question(family,**{"revision_id":self.ident,**changes})

    def call(self,action,body):
        return self.client.call("POST",self.base+"/analytics/"+action,body)

    def evaluate(self,q):
        status,payload,_=self.call("evaluate",q)
        self.assertEqual(status,200,payload)
        return payload

    def counts(self):
        tables=("ledger_event","web_portfolio_revision","web_csv_report","web_csv_source_key","benchmark_selection")
        return tuple(self.pg.owner.execute("SELECT count(*) FROM "+table).fetchone()[0] for table in tables)+tuple(
            self.pg.owner.execute("SELECT last_value FROM "+sequence).fetchone()[0] for sequence in
            ("ledger_event_ledger_seq_seq","web_portfolio_revision_seq_seq"))

    def command(self,**changes):
        return kit.PostgresWorkspaceTests.command(self,**changes)

    def apply(self,body):
        return self.store.command(self.user["user_id"],self.ident,body,self.world)

    def csv_holdings(self,rows):
        proposal=csv_kit.PostgresCsvTests.proposal(self,rows=rows)
        preview=self.csv.preview(self.user["user_id"],self.ident,proposal)
        return self.csv.commit(self.user["user_id"],self.ident,proposal,preview["preview_receipt"])

    def test_all_families_owned_canonical_read_only_and_independent_reproduction(self):
        before=self.counts()
        for family in ("PERFORMANCE_WINDOW","GAINS","ATTRIBUTION","RISK"):
            payload=self.evaluate(self.q(family))
            self.assertEqual(payload["portfolio_id"],self.ident)
            self.assertFalse(payload["persisted"])
            for index,wrapper in enumerate(payload["results"]):
                ref=proof(payload,index)
                status,evidence,headers=self.call("evidence",ref)
                self.assertEqual(status,200,evidence)
                self.assertEqual(evidence["result"],wrapper)
                self.assertEqual(dict(headers)[b"cache-control"],b"no-store")
                status,reproduced,_=self.call("reproduce",ref)
                self.assertEqual((status,reproduced["status"]),(200,"REPRODUCED"))
        self.assertEqual(self.counts(),before)

    def test_csrf_and_origin_protect_every_new_post(self):
        payload=self.evaluate(self.q())
        for action,body in (("evaluate",self.q()),("evidence",proof(payload)),("reproduce",proof(payload))):
            for headers in ({"X-Finweb-CSRF":""},{"Origin":"https://invalid.example"}):
                status,data,_=self.client.call("POST",self.base+"/analytics/"+action,body,extra=headers)
                self.assertEqual(status,403,data)

    def test_foreign_ownership_precedes_source_and_catalog_and_scope(self):
        other=self.store.register("user"+uuid.uuid4().hex[:15],"scrypt$131072$8$1$"+"0"*100)
        self.client.cookies["finweb_session"]=self.store.start_session(other,3600)
        self.client.call("GET","/api/v1/auth/session")
        with patch("web_api.analytics_context.verify_fixture_bytes",side_effect=AssertionError("foreign source read")),patch.object(self.world,"benchmark_catalog_provider",side_effect=AssertionError("foreign catalog read")):
            status,data,_=self.call("evaluate",self.q("RISK"))
        self.assertEqual((status,data["error"]["code"]),(404,"NOT_FOUND"))

    def test_foreign_or_later_scope_refuses_before_poisoned_source_work(self):
        from web_api.analytics_context import AnalyticsError
        added=self.apply(self.command(operation="ADD_ACCOUNT",events=[],account_name="Later fictional scope",as_of="2026-01-02"))
        later=next(row["account_id"] for row in added["workspace"]["accounts"] if row["account_id"]!=self.account)
        for account in (str(uuid.uuid4()),later):
            with patch("web_api.analytics_context.verify_fixture_bytes",side_effect=AnalyticsError(503,"TEST_SOURCE_POISON","source work ran","SOURCE")),patch("web_api.analytics_context.WorkspaceStore._item",side_effect=AssertionError("scope replay ran")):
                status,data,_=self.call("evaluate",self.q(scope=dict(kind="ACCOUNT",account_id=account)))
            self.assertEqual((status,data["error"]["code"]),(404,"NOT_FOUND"))
        with patch("web_api.analytics_context.verify_fixture_bytes",side_effect=AnalyticsError(503,"TEST_SOURCE_POISON","owned source failure","SOURCE")):
            status,data,_=self.call("evaluate",self.q(scope=dict(kind="ACCOUNT",account_id=self.account)))
        self.assertEqual((status,data["error"]["code"]),(503,"TEST_SOURCE_POISON"))

    def test_revision_and_scope_identity_precede_corrupt_saved_source_decode(self):
        added=self.apply(self.command(operation="ADD_ACCOUNT",events=[],account_name="Later scope",as_of="2026-01-02"))
        later=next(row["account_id"] for row in added["workspace"]["accounts"] if row["account_id"]!=self.account)
        from tests.product.test_postgres_web_auth import BODY
        other=self.store.create_portfolio(self.user["user_id"],BODY,self.world).snapshot()
        self.pg.owner.execute("UPDATE web_saved_sandbox SET request_json='not-valid-json' WHERE portfolio_id=%s",(uuid.UUID(self.ident),))
        with patch("web_api.analytics_context.verify_fixture_bytes",side_effect=AssertionError("source disk read before identity")):
            for revision in (str(uuid.uuid4()),other["portfolio_id"]):
                status,data,_=self.call("evaluate",self.q(revision_id=revision))
                self.assertEqual((status,data["error"]["code"]),(404,"NOT_FOUND"))
            for account in (str(uuid.uuid4()),later):
                status,data,_=self.call("evaluate",self.q(scope=dict(kind="ACCOUNT",account_id=account)))
                self.assertEqual((status,data["error"]["code"]),(404,"NOT_FOUND"))
            for changes in ({},{"scope":dict(kind="ACCOUNT",account_id=self.account)},
                            {"revision_id":added["workspace"]["revision_id"],"scope":dict(kind="ACCOUNT",account_id=later)}):
                status,data,_=self.call("evaluate",self.q(**changes))
                self.assertEqual((status,data["error"]["code"]),(503,"SAVED_SOURCE_DIFFERS"))

    def test_wrong_digest_reaches_each_engine_and_wrong_binding_refuses(self):
        for family in ("PERFORMANCE_WINDOW","GAINS","ATTRIBUTION","RISK"):
            payload=self.evaluate(self.q(family));ref=proof(payload)
            status,data,_=self.call("reproduce",{**ref,"expected_result_digest":"0"*64})
            self.assertEqual((status,data["status"]),(200,"RESULT_DIFFERS"),data)
            for field in ("expected_binding_digest","expected_manifest_id"):
                status,data,_=self.call("reproduce",{**ref,field:"0"*64})
                self.assertEqual((status,data["error"]["code"]),(409,"ANALYTICS_BINDING_DIFFERS"))

    def test_historical_revision_stays_identical_after_new_cash_and_old_packet_reproduces(self):
        q=self.q("GAINS");initial=self.evaluate(q)
        initial_packet=self.snapshot["insights"]["packets"][0]
        self.apply(self.command())
        self.assertEqual(self.evaluate(q),initial)
        self.assertEqual(self.store.get_portfolio(self.user["user_id"],self.ident,self.world,revision_id=self.ident).snapshot(),self.snapshot)
        status,data,_=self.call("reproduce",proof(initial))
        self.assertEqual((status,data["status"]),(200,"REPRODUCED"))
        path=self.base+"/packets/"+initial_packet["insight_id"]+"/reproduce"
        # Existing ASGI helper has no query-string support, so use the old pinned
        # object directly through its established service, without touching HTTP.
        from insight_service.service import reproduce_insights
        item=self.store.get_portfolio(self.user["user_id"],self.ident,self.world,revision_id=self.ident)
        self.assertEqual(reproduce_insights(item.insights,item.insights.result_digest,(item.source,),policies=item.policies,allow_synthetic=True).status,"REPRODUCED")

    def test_added_account_cannot_enter_an_older_revision_scope(self):
        added=self.apply(self.command(operation="ADD_ACCOUNT",events=[],account_name="Later empty fictional account",as_of="2026-01-02"))
        account=next(row["account_id"] for row in added["workspace"]["accounts"] if row["account_id"]!=self.account)
        scope=dict(kind="ACCOUNT",account_id=account)
        status,data,_=self.call("evaluate",self.q(scope=scope))
        self.assertEqual(status,404,data)
        payload=self.evaluate(self.q(revision_id=added["workspace"]["revision_id"],scope=scope))
        self.assertEqual(payload["question"]["scope"],scope)

    def test_unused_catalog_damage_does_not_block_performance_or_independent_proof(self):
        risk_payload=self.evaluate(self.q("RISK"))
        independent_index=next(index for index,row in enumerate(risk_payload["results"]) if row["group"]=="INDEPENDENT")
        with patch.object(self.world,"benchmark_catalog_provider",side_effect=CatalogError("damaged test-only source")):
            for family in ("PERFORMANCE_WINDOW","GAINS","ATTRIBUTION"):
                self.evaluate(self.q(family))
            status,data,_=self.call("reproduce",proof(risk_payload,independent_index))
            self.assertEqual((status,data["status"]),(200,"REPRODUCED"))
            status,data,_=self.call("evaluate",self.q("RISK"))
            self.assertEqual((status,data["error"]["code"]),(503,"ANALYTICS_CATALOG_UNAVAILABLE"))
        for provider in (dict(side_effect=CatalogError("missing test-only rates")),dict(return_value=None)):
            with patch("web_api.analytics_context.load_risk_free_catalog",**provider):
                status,data,_=self.call("evaluate",self.q("RISK"))
                self.assertEqual((status,data["error"]["code"]),(503,"ANALYTICS_CATALOG_UNAVAILABLE"))

    def test_actual_default_xy_keep_null_count_and_distinct_group_bindings(self):
        payload=self.evaluate(self.q("RISK",window=dict(rule="TRAILING_MONTHS",months=36,base=None),view="DEFAULT"))
        self.assertEqual(len(payload["results"]),4)
        by_id={row["result_id"]:row for row in payload["results"]}
        for row in payload["results"]:
            for metric in row["engine_result"]["metrics"]:
                self.assertIsNone(metric["value"])
                self.assertIsNone(metric["observation_count"])
            if row["group"]=="INDEPENDENT":
                self.assertIsNone(row["binding"]["selection_pin"])
                self.assertIsNone(row["binding"]["benchmark_catalog"])
        for view in payload["views"]:
            shown=by_id[view["shown_result_id"]]
            self.assertEqual(shown["engine_result"]["metrics"][view["metric_index"]]["metric_id"],view["metric_id"])
            if view["fallback"]:
                refused=by_id[view["refused_result_id"]]
                self.assertEqual(shown["group"],refused["group"])
                self.assertNotEqual(shown["result_id"],refused["result_id"])

    def test_selection_clear_does_not_rebind_old_revision_or_independent_manifest(self):
        from web_api.workspace_requests import PreferencesCommand
        initial=self.evaluate(self.q("RISK"))
        body=PreferencesCommand(operation_id=str(uuid.uuid4()),expected_revision_id=self.ident,as_of="2026-01-02",policies=[],policies_confirmed=True,
            benchmark=dict(action="CLEAR",selected_on="2026-01-02")).model_dump()
        current=self.store.command(self.user["user_id"],self.ident,body,self.world,preferences=True)
        new=self.evaluate(self.q("RISK",revision_id=current["workspace"]["revision_id"]))
        self.assertEqual(self.evaluate(self.q("RISK")),initial)
        old_ind=next(row for row in initial["results"] if row["group"]=="INDEPENDENT")
        new_ind=next(row for row in new["results"] if row["group"]=="INDEPENDENT")
        self.assertEqual(old_ind["engine_result"],new_ind["engine_result"])
        benchmark=next(row for row in new["results"] if row["group"]=="BENCHMARK")
        self.assertEqual(benchmark["binding"]["selection_pin"]["state"],"CLEARED")

    def test_current_raw_fixture_change_refuses_cached_evaluation_and_reproduce(self):
        payload=self.evaluate(self.q())
        before=self.counts()
        with patch("web_api.analytics_context.Path.read_bytes",return_value=b"damaged raw bytes"):
            for action,body in (("evaluate",self.q()),("reproduce",proof(payload))):
                status,data,_=self.call(action,body)
                self.assertEqual((status,data["error"]["code"]),(503,"ANALYTICS_SOURCE_DIFFERS"))
        self.assertEqual(self.counts(),before)

    def test_span_and_output_limits_are_whole_request_transport_errors(self):
        distant=self.apply(self.command(as_of="2050-01-01"))
        q=self.q(revision_id=distant["workspace"]["revision_id"],as_of="2050-01-01")
        before=self.counts()
        with patch("web_api.analytics_context.WorkspaceStore._item",side_effect=AssertionError("unbounded old engine ran")):
            status,data,_=self.call("evaluate",q)
        self.assertEqual((status,data["error"]["code"]),(422,"ANALYTICS_SPAN_LIMIT"))
        self.assertNotIn("state",data["error"])
        with patch.dict(LIMITS,output_bytes=100):
            status,data,_=self.call("evaluate",self.q())
        self.assertEqual((status,data["error"]["code"]),(422,"ANALYTICS_OUTPUT_LIMIT"))
        self.assertEqual(self.counts(),before)

    def test_gains_partial_weight_zero_and_null_are_actual_issued_values(self):
        # Separate newly imported account: market values100+50. The known lot
        # has basis100 and gain0. Unknown basis on the50 lot is excluded:1/3.
        saved=self.csv_holdings([["known","POSITION","2026-01-02","USD","SYN-A","1","","100"],
                                 ["unknown","POSITION","2026-01-02","USD","SYN-B","1","",""]])
        account=next(row["account_id"] for row in saved["workspace_result"]["workspace"]["accounts"] if row["account_id"]!=self.account)
        payload=self.evaluate(self.q("GAINS",revision_id=saved["report"]["revision_id"],scope=dict(kind="ACCOUNT",account_id=account)))
        metrics=payload["results"][0]["engine_result"]["metrics"]
        total=next(row for row in metrics if row["metric_id"]=="unrealized_gain_total")
        self.assertEqual((total["state"],total["value"],total["exact"],total["excluded_weight"]),("LIMITED","0","0/1","1/3"))
        self.assertFalse(total["partial"]);self.assertEqual(total["excluded"],[])
        remaining=[row for row in metrics if row["metric_id"]=="remaining_basis" and row["view"]=="REPORTING"]
        self.assertEqual({row["value"] for row in remaining},{"100",None})
        old=self.csv.get(self.user["user_id"],self.ident,saved["report"]["report_id"])
        self.assertEqual(canonical_json(old["report"]),canonical_json(saved["report"]))

    def test_as_of_and_source_corruption_are_refused_without_head_substitution(self):
        status,data,_=self.call("evaluate",self.q(as_of="2026-01-03"))
        self.assertEqual((status,data["error"]["code"]),(409,"ANALYTICS_AS_OF_DIFFERS"))
        self.pg.owner.execute("UPDATE web_saved_sandbox SET snapshot_sha256=%s WHERE portfolio_id=%s",("0"*64,uuid.UUID(self.ident)))
        status,data,_=self.call("evaluate",self.q())
        self.assertEqual((status,data["error"]["code"]),(503,"SAVED_SOURCE_DIFFERS"))
