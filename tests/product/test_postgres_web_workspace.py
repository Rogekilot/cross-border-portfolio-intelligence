"""Actual PostgreSQL append/correction, immutable revision and preference probes."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import psycopg

from tests.product.pg_market_kit import PgSchema
from tests.product.test_postgres_web_auth import BODY, Client, ROLE, SKIP, PASSWORD
from persistence import connection
from persistence.web_account_store import APP_GRANTS,AccountStoreError,WebAccountStore
from web_api.app import create_app
from web_api.auth import AuthSettings
from web_api.synthetic import SyntheticWorld
from web_api.workspace_requests import LedgerCommand,PreferencesCommand


@unittest.skipIf(bool(SKIP),SKIP)
class PostgresWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pg=PgSchema("finweb_it_workspace_").open(grant=False)
        cls.addClassCleanup(cls.pg.close)
        for statement in APP_GRANTS:
            cls.pg.owner.execute(statement.format(schema=cls.pg.schema,role=ROLE))
        cls.conninfo=connection.build_conninfo(dbname=os.environ[connection.DATABASE_VAR],user=ROLE,socket=os.environ.get(connection.SOCKET_VAR))

    def setUp(self):
        self.world=SyntheticWorld()
        self.store=WebAccountStore(self.conninfo,self.pg.schema)
        self.user=self.store.register("user"+uuid.uuid4().hex[:15],"scrypt$131072$8$1$"+"0"*100)
        self.snapshot=self.store.create_portfolio(self.user["user_id"],BODY,self.world).snapshot()
        self.ident=self.snapshot["portfolio_id"]
        self.base="/api/v1/portfolios/"+self.ident
        self.initial=self.store.workspace(self.user["user_id"],self.ident,self.world)
        self.account=self.initial["accounts"][0]["account_id"]

    def command(self,**changes):
        head=self.store.workspace(self.user["user_id"],self.ident,self.world)["current_revision_id"]
        value=dict(operation_id=str(uuid.uuid4()),expected_revision_id=head,as_of="2026-01-05",operation="APPEND",
            events=[dict(event_type="DEPOSIT",account_id=self.account,event_date="2026-01-05",currency="USD",amount="25")])
        value.update(changes)
        return LedgerCommand(**value).model_dump()

    def apply(self,body,**options):
        return self.store.command(self.user["user_id"],self.ident,body,self.world,**options)

    def pref(self,**changes):
        value=dict(operation_id=str(uuid.uuid4()),expected_revision_id=self.store.workspace(self.user["user_id"],self.ident,self.world)["current_revision_id"],
            as_of="2026-01-02",policies=[],policies_confirmed=True,benchmark=dict(action="KEEP"))
        value.update(changes)
        return PreferencesCommand(**value).model_dump()

    def test_preview_rolls_back_every_fact_revision_and_empty_account(self):
        body=self.command()
        preview=self.apply(body,preview=True)
        self.assertTrue(preview["preview"])
        self.assertEqual(preview["workspace"]["ledger"]["current_state"]["accounts"][0]["cash"][0]["amount"],"525")
        self.assertEqual(self.store.workspace(self.user["user_id"],self.ident,self.world),self.initial)
        self.assertEqual(self.store.get_portfolio(self.user["user_id"],self.ident,self.world).snapshot(),self.snapshot)
        add=self.command(operation="ADD_ACCOUNT",events=[],account_name="Second fictional account")
        self.assertEqual(len(self.apply(add,preview=True)["workspace"]["accounts"]),2)
        self.assertEqual(len(self.store.workspace(self.user["user_id"],self.ident,self.world)["accounts"]),1)

    def test_append_actual_gapped_pin_and_exact_native_state_later_market_suppressed(self):
        body=self.command()
        self.apply(body,preview=True)
        saved=self.apply(body)
        workspace=saved["workspace"]
        self.assertGreater(workspace["ledger"]["version"],self.initial["ledger"]["version"]+1)
        self.assertEqual(workspace["ledger"]["current_state"]["accounts"][0]["cash"][0]["amount"],"525")
        self.assertEqual(str(saved["snapshot"]["as_of"]),"2026-01-05")
        self.assertEqual(self.store.list_portfolios(self.user["user_id"])[0]["as_of"],"2026-01-05")
        nav=next(row for row in saved["snapshot"]["valuation"]["metrics"] if row["metric_id"]=="portfolio_value" and row["view"]=="REPORTING")
        self.assertEqual(nav["state"],"INSUFFICIENT_DATA")
        self.assertIsNone(nav["value"])

    def test_correction_reversal_atomic_old_proof_and_original_bytes_preserved(self):
        first=self.apply(self.command())
        target=first["workspace"]["ledger"]["events"][-1]["event_id"]
        body=self.command(operation="CORRECT",target_event_ids=[target],events=[dict(event_type="DEPOSIT",account_id=self.account,event_date="2026-01-05",currency="USD",amount="40")])
        corrected=self.apply(body)
        values=corrected["workspace"]["ledger"]["events"]
        self.assertEqual([row["event_type"] for row in values[-2:]],["REVERSAL","DEPOSIT"])
        self.assertEqual(values[-1]["corrects_event_id"],target)
        self.assertEqual(corrected["workspace"]["ledger"]["current_state"]["accounts"][0]["cash"][0]["amount"],"540")
        old=self.store.get_portfolio(self.user["user_id"],self.ident,self.world,revision_id=self.ident)
        self.assertEqual(old.snapshot(),self.snapshot)
        from insight_service.service import reproduce_insights
        self.assertEqual(reproduce_insights(old.insights,old.insights.result_digest,(old.source,),policies=old.policies,allow_synthetic=True).status,"REPRODUCED")

    def test_idempotent_retry_even_after_head_changed_and_conflict_does_not_append(self):
        body=self.command()
        first=self.apply(body)
        self.apply(self.command())
        retried=self.apply(body)
        self.assertEqual(retried["snapshot"],first["snapshot"])
        self.assertEqual(retried["workspace"]["revision_id"],first["workspace"]["revision_id"])
        self.assertNotEqual(retried["workspace"]["revision_id"],retried["workspace"]["current_revision_id"])
        with self.assertRaises(AccountStoreError) as error:
            self.apply({**body,"as_of":"2026-01-06"})
        self.assertEqual(error.exception.code,"IDEMPOTENCY_CONFLICT")

    def test_stale_and_concurrent_commands_cannot_lose_updates(self):
        one,two=self.command(),self.command()
        def run(body):
            try:
                return self.apply(body)["workspace"]["revision_id"]
            except AccountStoreError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,(one,two)))
        self.assertEqual(results.count("STALE_REVISION"),1)
        current=self.store.workspace(self.user["user_id"],self.ident,self.world)
        self.assertEqual(len(current["history"]),2)

    def test_invalid_snapshot_date_and_incomplete_transfer_roll_back(self):
        for body in (self.command(events=[dict(event_type="DEPOSIT",account_id=self.account,event_date="2026-01-02",currency="USD",amount="1")]),
                     self.command(events=[dict(event_type="TRANSFER_OUT",account_id=self.account,event_date="2026-01-05",currency="USD",amount="1",counterparty_account_id=self.account)])):
            with self.assertRaises(AccountStoreError):
                self.apply(body)
            self.assertEqual(self.store.workspace(self.user["user_id"],self.ident,self.world)["ledger"]["events"],self.initial["ledger"]["events"])

    def test_extreme_calendar_dates_are_typed_refusals_and_preview_rolls_back(self):
        for day in ("0001-01-01","9999-12-31"):
            with self.assertRaises(AccountStoreError) as error:
                self.apply(self.command(as_of=day),preview=True)
            self.assertEqual((error.exception.status,error.exception.code),(422,"WORKSPACE_COMMAND_REFUSED"))
            self.assertEqual(self.store.workspace(self.user["user_id"],self.ident,self.world)["ledger"]["events"],self.initial["ledger"]["events"])

    def test_new_accounts_history_visibility_openings_and_internal_pair(self):
        added=self.apply(self.command(operation="ADD_ACCOUNT",events=[],account_name="Second fictional account"))
        second=next(row["account_id"] for row in added["workspace"]["accounts"] if row["account_id"]!=self.account)
        self.assertEqual(len(self.store.workspace(self.user["user_id"],self.ident,self.world,revision_id=self.ident)["accounts"]),1)
        self.apply(self.command(events=[dict(event_type="OPENING_CASH",account_id=second,event_date="2026-01-02",currency="USD",amount="100")]))
        paired=self.apply(self.command(events=[dict(event_type="TRANSFER_OUT",account_id=self.account,counterparty_account_id=second,event_date="2026-01-05",currency="USD",amount="25"),
            dict(event_type="TRANSFER_IN",account_id=second,counterparty_account_id=self.account,event_date="2026-01-05",currency="USD",amount="25")]))
        balances={row["account_id"]:row["cash"][0]["amount"] for row in paired["workspace"]["ledger"]["current_state"]["accounts"]}
        self.assertEqual(balances,{self.account:"475",second:"125"})

    def test_personal_policy_exact_binding_effective_dates_and_reproduced_packet(self):
        target=next(row for row in self.initial["policies"]["targets"] if row["metric_id"]=="largest_security_weight")
        policy={**{key:target[key] for key in ("source_kind","metric_id","scope_kind","account_id","subject","semantic_key")},"policy_id":str(uuid.uuid4()),
            "direction":"MAXIMUM","limit":"1/3","effective_from":"2026-01-02","evidence":"I explicitly choose this fictional personal maximum"}
        saved=self.apply(self.pref(policies=[policy]),preferences=True)
        self.assertEqual(saved["workspace"]["policies"]["state"],"ACTIVE")
        self.assertEqual(saved["workspace"]["policies"]["items"][0]["limit"],__import__('fractions').Fraction(1,3))
        packet=next(row for row in saved["snapshot"]["insights"]["packets"] if row["insight_type"]=="user_limit")
        self.assertEqual(packet["judgment_class"],"PREFERENCE_DEPENDENT")
        item=self.store.get_portfolio(self.user["user_id"],self.ident,self.world)
        from insight_service.service import reproduce_insights
        self.assertEqual(reproduce_insights(item.insights,item.insights.result_digest,(item.source,),policies=item.policies,allow_synthetic=True).status,"REPRODUCED")
        for change in (dict(semantic_key="wrong-semantic"),dict(effective_until="2026-01-01"),dict(scope_kind="ACCOUNT",account_id=self.account)):
            with self.assertRaises(AccountStoreError):
                self.apply(self.pref(policies=[{**policy,**change}]),preferences=True)
        cleared=self.apply(self.pref(),preferences=True)
        self.assertEqual(cleared["workspace"]["policies"]["state"],"NONE")
        self.assertEqual(self.store.workspace(self.user["user_id"],self.ident,self.world,revision_id=self.ident)["policies"]["state"],"NOT_STATED")

    def test_empty_catalog_never_selects_spy_and_clear_distinct_from_not_stated(self):
        self.assertEqual(self.initial["benchmark"]["state"],"NOT_STATED")
        self.assertEqual(self.initial["benchmark"]["entries"],[])
        with self.assertRaises(AccountStoreError) as error:
            self.apply(self.pref(benchmark=dict(action="SELECT",benchmark_id="SPY",selected_on="2026-10-19")),preferences=True)
        self.assertEqual(error.exception.code,"BENCHMARK_NOT_ADMITTED")
        clear=self.apply(self.pref(benchmark=dict(action="CLEAR",selected_on="2026-10-19")),preferences=True)
        self.assertEqual((clear["workspace"]["benchmark"]["state"],clear["workspace"]["benchmark"]["pin"]["state"]),("NONE","CLEARED"))
        self.assertEqual(clear["snapshot"]["preferences"]["benchmark_pin"],clear["workspace"]["benchmark"]["pin"])
        from domain.catalogs import CatalogError
        other=self.store.register("user"+uuid.uuid4().hex[:15],"scrypt$131072$8$1$"+"0"*100)
        command=self.pref(benchmark=dict(action="SELECT",benchmark_id="SPY",selected_on="2026-10-19"))
        with patch("web_api.app.SyntheticWorld",return_value=self.world):
            app=create_app(account_store=self.store,auth_settings=AuthSettings.local(),enable_saved_synthetic=True)
        clients=[]
        for user in (self.user,other):
            client=Client(app,"127.0.0.55")
            client.cookies["finweb_session"]=self.store.start_session(user,3600)
            client.call("GET","/api/v1/auth/session")
            clients.append(client)
        for provider in (dict(side_effect=CatalogError("missing or malformed fixture catalog")),dict(return_value=None)):
            with patch.object(self.world,"benchmark_catalog_provider",**provider):
                for client,status,code in ((clients[0],503,"BENCHMARK_CATALOG_UNAVAILABLE"),(clients[1],404,"NOT_FOUND")):
                    for method,path,body in (("GET",self.base+"/workspace",None),("POST",self.base+"/preferences",command)):
                        actual,data,_=client.call(method,path,body)
                        self.assertEqual((actual,data["error"]["code"]),(status,code))
                # Reproducing a saved proof uses its pinned selection, not today's catalog.
                self.assertEqual(self.store.get_portfolio(self.user["user_id"],self.ident,self.world).snapshot(),clear["snapshot"])

    def test_owner_isolation_before_financial_work_all_new_routes_and_csrf(self):
        other=self.store.register("user"+uuid.uuid4().hex[:15],"scrypt$131072$8$1$"+"0"*100)
        command=self.command()
        with patch.object(self.world,"create",side_effect=AssertionError("foreign financial work")):
            with self.assertRaises(AccountStoreError) as error:
                self.store.workspace(other["user_id"],self.ident,self.world)
            self.assertEqual(error.exception.status,404)
            with self.assertRaises(AccountStoreError) as error:
                self.store.command(other["user_id"],self.ident,command,self.world)
            self.assertEqual(error.exception.status,404)
        app=create_app(account_store=self.store,auth_settings=AuthSettings.local(),enable_saved_synthetic=True)
        client=Client(app,"127.0.0.44")
        client.call("GET","/api/v1/auth/session")
        client.cookies["finweb_session"]=self.store.start_session(self.user,3600)
        client.call("GET","/api/v1/auth/session")
        for path,body in ((self.base+"/ledger-commands",self.command()),(self.base+"/ledger-commands/preview",self.command()),(self.base+"/preferences",self.pref())):
            self.assertEqual(client.call("POST",path,body,extra={"X-Finweb-CSRF":""})[0],403)
        self.assertEqual(client.call("GET",self.base+"/workspace")[0],200)

    def test_actual_database_grants_revision_ledger_immutability_and_restart(self):
        saved=self.apply(self.command())
        restarted=WebAccountStore(self.conninfo,self.pg.schema)
        self.assertEqual(restarted.get_portfolio(self.user["user_id"],self.ident,self.world).snapshot(),saved["snapshot"])
        with self.store.connect() as conn:
            for table in ("ledger_event","web_portfolio_revision","benchmark_selection"):
                self.assertEqual(conn.execute("SELECT has_table_privilege(current_user,%s,'UPDATE'),has_table_privilege(current_user,%s,'DELETE')",(table,table)).fetchone(),(False,False))
                with self.assertRaises(psycopg.Error):
                    conn.execute("DELETE FROM "+table)
        with self.assertRaises(psycopg.Error):
            self.pg.owner.execute("UPDATE web_portfolio_revision SET policies_state='NONE' WHERE portfolio_id=%s",(uuid.UUID(self.ident),))

    def test_positive_benchmark_selection_only_through_test_catalog_preserves_pin(self):
        from domain.catalogs import BenchmarkCatalog,BenchmarkEntry,ReturnBasis,SeriesForm
        entry=BenchmarkEntry("TEST-ONLY","Fictional test reference","Fixture","test.source","TEST_ONLY","USD",ReturnBasis.TOTAL_RETURN_GROSS,
            "fictional gross reinvestment","TEST_CALENDAR",SeriesForm.LEVELS,None,True)
        catalog=BenchmarkCatalog("test-only:cp7b",(entry,),synthetic=True)
        with patch.object(self.world,"benchmark_catalog_provider",return_value=catalog):
            saved=self.apply(self.pref(benchmark=dict(action="SELECT",benchmark_id="TEST-ONLY",selected_on="2026-10-19")),preferences=True)
            benchmark=saved["workspace"]["benchmark"]
            self.assertEqual((benchmark["state"],benchmark["pin"]["state"]),("SELECTED","IN_FORCE"))
            self.assertEqual(benchmark["pin"]["catalog_version"],catalog.catalog_id)
            self.assertEqual(benchmark["pin"]["origin"],"USER_CHOSEN")
            self.assertEqual(self.store.get_portfolio(self.user["user_id"],self.ident,self.world).snapshot(),saved["snapshot"])
        # The production catalog itself was never changed.
        from risk_service.catalogs import load_benchmark_catalog
        self.assertEqual(load_benchmark_catalog().entries,())

    def test_all_manual_event_families_preserve_native_facts_and_date_rules(self):
        listing=self.initial["listings"][0]["listing_id"]
        def event(kind,**fields):
            return dict(event_type=kind,account_id=self.account,event_date="2026-01-05",currency="USD",**fields)
        values=[event("BUY",listing_id=listing,quantity="1",amount="100"),event("SELL",listing_id=listing,quantity="1",amount="100"),
            event("DIVIDEND",listing_id=listing,amount="10",ex_date="2026-01-03"),event("INTEREST",amount="1"),event("FEE",amount="1"),event("TAX",amount="1"),
            event("DEPOSIT",amount="10"),event("WITHDRAWAL",amount="10"),event("INTEREST_CHARGED",amount="1"),
            event("CURRENCY_CONVERSION",amount="1",bought_amount=dict(currency="HKD",amount="7.8")),
            event("TRANSFER_IN",listing_id=listing,quantity="1",cost_basis="0",acquired_on="2025-12-01"),event("TRANSFER_OUT",listing_id=listing,quantity="1")]
        saved=self.apply(self.command(events=values))
        split=event("SPLIT",listing_id=listing,split_ratio=dict(new_units="2",old_units="1"))
        split["event_date"]="2026-01-06"
        saved=self.apply(self.command(events=[split],as_of="2026-01-06"))
        kinds={row["event_type"] for row in saved["workspace"]["ledger"]["events"]}
        self.assertEqual(kinds,{"OPENING_POSITION","OPENING_CASH","BUY","SELL","DIVIDEND","INTEREST","FEE","TAX","DEPOSIT","WITHDRAWAL","INTEREST_CHARGED","CURRENCY_CONVERSION","TRANSFER_IN","TRANSFER_OUT","SPLIT"})
        balances={row["currency"]:row["amount"] for row in saved["workspace"]["ledger"]["current_state"]["accounts"][0]["cash"]}
        self.assertEqual(balances,{"HKD":"7.8","USD":"507"})

    def test_corrupt_stored_metadata_typed_refusal_after_ownership(self):
        saved=self.apply(self.pref(benchmark=dict(action="CLEAR",selected_on="2026-10-19")),preferences=True)
        other=self.store.register("user"+uuid.uuid4().hex[:15],"scrypt$131072$8$1$"+"0"*100)
        original=self.pg.owner.execute("SELECT request_json FROM web_saved_sandbox WHERE portfolio_id=%s",(uuid.UUID(self.ident),)).fetchone()[0]
        self.pg.owner.execute("UPDATE web_saved_sandbox SET request_json='[' WHERE portfolio_id=%s",(uuid.UUID(self.ident),))
        try:
            for owner,code in ((self.user["user_id"],"SAVED_SOURCE_DIFFERS"),(other["user_id"],"NOT_FOUND")):
                with self.assertRaises(AccountStoreError) as error:
                    self.store.workspace(owner,self.ident,self.world)
                self.assertEqual(error.exception.code,code)
        finally:
            self.pg.owner.execute("UPDATE web_saved_sandbox SET request_json=%s WHERE portfolio_id=%s",(original,uuid.UUID(self.ident)))
        self.pg.owner.execute("ALTER TABLE web_portfolio_revision DISABLE TRIGGER web_revision_immutable")
        self.pg.owner.execute("UPDATE web_portfolio_revision SET policies_json='[' WHERE portfolio_id=%s",(uuid.UUID(self.ident),))
        self.pg.owner.execute("ALTER TABLE web_portfolio_revision ENABLE TRIGGER web_revision_immutable")
        with self.assertRaises(AccountStoreError) as error:
            self.store.get_portfolio(self.user["user_id"],self.ident,self.world)
        self.assertEqual((error.exception.status,error.exception.code),(503,"SAVED_RESULT_DIFFERS"))

    def test_policy_container_and_state_corruption_are_typed_after_ownership(self):
        target=next(row for row in self.initial["policies"]["targets"] if row["metric_id"]=="largest_security_weight")
        policy={**{key:target[key] for key in ("source_kind","metric_id","scope_kind","account_id","subject","semantic_key")},"policy_id":str(uuid.uuid4()),
            "direction":"MAXIMUM","limit":"1/3","effective_from":"2026-01-02","evidence":"I explicitly choose this fictional personal maximum"}
        self.apply(self.pref(policies=[policy]),preferences=True)
        original=self.pg.owner.execute("SELECT policies_json,policies_state FROM web_portfolio_revision WHERE portfolio_id=%s",(uuid.UUID(self.ident),)).fetchone()
        other=self.store.register("user"+uuid.uuid4().hex[:15],"scrypt$131072$8$1$"+"0"*100)
        app=create_app(account_store=self.store,auth_settings=AuthSettings.local(),enable_saved_synthetic=True)
        clients=[]
        for user in (self.user,other):
            client=Client(app,"127.0.0.44")
            client.cookies["finweb_session"]=self.store.start_session(user,3600)
            clients.append(client)
        missing_fields=[]
        for field in ("origin","account_id","effective_until","subject"):
            missing=json.loads(original[0])
            missing[0].pop(field)
            missing_fields.append((json.dumps(missing),"ACTIVE"))
        for raw,state in [("{}","NONE"),("[]","ACTIVE"),(original[0],"NONE"),("[null]","ACTIVE"),*missing_fields]:
            self.pg.owner.execute("ALTER TABLE web_portfolio_revision DISABLE TRIGGER web_revision_immutable")
            try:
                self.pg.owner.execute("UPDATE web_portfolio_revision SET policies_json=%s,policies_state=%s WHERE portfolio_id=%s",(raw,state,uuid.UUID(self.ident)))
            finally:
                self.pg.owner.execute("ALTER TABLE web_portfolio_revision ENABLE TRIGGER web_revision_immutable")
            for owner,code in ((self.user["user_id"],"SAVED_RESULT_DIFFERS"),(other["user_id"],"NOT_FOUND")):
                for read in (self.store.workspace,self.store.get_portfolio):
                    with self.assertRaises(AccountStoreError) as error:
                        read(owner,self.ident,self.world)
                    self.assertEqual(error.exception.code,code)
            for client,status,code in ((clients[0],503,"SAVED_RESULT_DIFFERS"),(clients[1],404,"NOT_FOUND")):
                for path in (self.base,self.base+"/workspace"):
                    actual,data,_=client.call("GET",path)
                    self.assertEqual((actual,data["error"]["code"]),(status,code))
