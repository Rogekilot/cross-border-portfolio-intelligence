"""E1 actual-PG/ASGI no-write checks. Prewritten; execution requires a root slot."""
import asyncio
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))

from tests.product import test_postgres_web_workspace as kit
from tests.product.test_postgres_web_auth import SKIP
from tests.product.test_web_real_source_gate import GET,POST,ORIGIN,intent,metadata_provider,raw_request
from web_api.app import create_app
from web_api.auth import AuthSettings,csrf_token


@unittest.skipIf(bool(SKIP),SKIP)
class PostgresRealSourceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        kit.PostgresWorkspaceTests.setUpClass.__func__(cls)
        count=cls.pg.owner.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
        if count!=19:
            raise AssertionError("E1 test schema must retain the existing 19 migrations")
        print(json.dumps({"e1_schema":cls.pg.schema,"migration_count":count}),flush=True)

    def setUp(self):
        # Existing fictional user/portfolio setup is separate from E1 route effects.
        kit.PostgresWorkspaceTests.setUp(self)
        self.token=self.store.start_session(self.user,3600)
        self.headers=[("Origin",ORIGIN),("Cookie","finweb_session="+self.token),("X-Finweb-CSRF",csrf_token(self.token))]
        with patch("web_api.app.SyntheticWorld",return_value=self.world):
            self.app=create_app(account_store=self.store,auth_settings=AuthSettings.local(),enable_saved_synthetic=True)

    def call(self,method,path,body=None,**kwargs):
        return asyncio.run(raw_request(self.app,method,path,
            body=b"" if body is None else json.dumps(body).encode(),headers=self.headers,**kwargs))

    def counts(self):
        names=("app_user","issuer","instrument","listing","portfolio","account","ledger_event","web_identity",
            "web_session","web_auth_rate","web_saved_sandbox","web_portfolio_revision","benchmark_selection",
            "web_csv_report","web_csv_source_key")
        return tuple((name,self.pg.owner.execute("SELECT count(*) FROM "+name).fetchone()[0]) for name in names)+tuple(
            (sequence,self.pg.owner.execute("SELECT last_value,is_called FROM "+sequence).fetchone()) for sequence in
            ("ledger_event_ledger_seq_seq","web_portfolio_revision_seq_seq","benchmark_selection_seq_seq"))

    @contextmanager
    def trace(self):
        statements=[]
        original=self.store.connect
        class Connection:
            def __init__(self,conn):self.conn=conn
            def execute(self,sql,*args,**kwargs):
                statements.append(" ".join(str(sql).split()))
                return self.conn.execute(sql,*args,**kwargs)
            def __getattr__(self,name):return getattr(self.conn,name)
        @contextmanager
        def connect():
            with original() as conn:
                yield Connection(conn)
        with patch.object(self.store,"connect",connect):
            yield statements

    def assert_session_selects_only(self,statements):
        self.assertTrue(statements)
        for statement in statements:
            self.assertTrue(statement.startswith("SELECT "),statement)
            self.assertIn("FROM web_session s JOIN web_identity i",statement)
            self.assertNotIn(self.token,statement)

    def assert_no_write(self,before,statements):
        after=self.counts()
        self.assert_session_selects_only(statements)
        self.assertEqual(before,after)
        print(json.dumps({"test":self._testMethodName,"before":dict(before),"after":dict(after),
            "sql_statement_count":len(statements),"sql_templates":sorted(set(statements))},sort_keys=True),flush=True)

    def test_default_capability_and_repeated_refusal_change_no_rows_or_sequences(self):
        before=self.counts()
        with self.trace() as statements:
            status,value,_=self.call("GET",GET)
            self.assertEqual((status,value["state"],value["approved_context_count"]),(200,"BLOCKED",0))
            for body in (intent(),intent(),intent(as_of="2026-01-03"),{**intent(),"positions":[]}):
                status,value,_=self.call("POST",POST,body)
                self.assertEqual(status,422 if "positions" in body else 409)
        self.assert_no_write(before,statements)

    def test_configured_metadata_gate_also_never_writes_and_corruption_is503(self):
        before=self.counts()
        with tempfile.TemporaryDirectory() as temp:
            provider=metadata_provider(Path(temp))
            with patch("web_api.real_routes.MetadataProvider",return_value=provider),patch("web_api.app.SyntheticWorld",return_value=self.world):
                self.app=create_app(account_store=self.store,auth_settings=AuthSettings.local(),enable_saved_synthetic=True)
            with self.trace() as statements:
                status,value,_=self.call("GET",GET);self.assertEqual(status,200)
                ctx=value["contexts"][0]
                body=intent(expected_configuration_digest=ctx["configuration_digest"],release_id=ctx["declared_release_id"])
                status,value,_=self.call("POST",POST,body)
                self.assertEqual((status,value["error"]["code"]),(409,"REAL_PORTFOLIO_CREATION_DISABLED"))
                status,value,_=self.call("POST",POST,{**body,"release_id":"0"*64})
                self.assertEqual((status,value["error"]["code"]),(409,"REAL_SOURCE_CONFIGURATION_DIFFERS"))
                (Path(temp)/"file_manifest.json").write_bytes(b"changed metadata")
                for method,path,payload in (("GET",GET,None),("POST",POST,body)):
                    status,value,_=self.call(method,path,payload)
                    self.assertEqual((status,value["error"]["code"]),(503,"REAL_SOURCE_CONFIGURATION_UNAVAILABLE"))
        self.assert_no_write(before,statements)

    def test_auth_query_body_and_csrf_failures_change_no_financial_state(self):
        before=self.counts()
        with self.trace() as statements:
            self.assertEqual(self.call("GET",GET,query=b"x=1&x=2")[0],422)
            status,_value,_=asyncio.run(raw_request(self.app,"GET",GET,headers=self.headers,chunks=[b"",b"x",b"unread"]))
            self.assertEqual(status,422)
            bad=[row for row in self.headers if row[0]!="X-Finweb-CSRF"]
            status,value,_=asyncio.run(raw_request(self.app,"POST",POST,body=b"malformed",headers=bad))
            self.assertEqual((status,value["error"]["code"]),(403,"CSRF_REJECTED"))
            status,value,_=asyncio.run(raw_request(self.app,"GET",GET,headers=[]))
            self.assertEqual((status,value["error"]["code"]),(401,"AUTHENTICATION_REQUIRED"))
        self.assert_no_write(before,statements)

    def test_old_snapshot_packet_and_explicit_synthetic_append_still_work(self):
        before=self.counts()
        self.assertEqual(self.call("GET",GET)[0],200)
        self.assertEqual(before,self.counts())
        status,value,_=self.call("GET",self.base)
        self.assertEqual((status,value),(200,self.snapshot))
        packet=self.snapshot["insights"]["packets"][0]
        status,value,_=self.call("GET",self.base+"/packets/"+packet["insight_id"])
        self.assertEqual(status,200)
        status,value,_=self.call("POST",self.base+"/packets/"+packet["insight_id"]+"/reproduce",
            dict(expected_result_digest=value["result_digest"]))
        self.assertEqual((status,value["status"]),(200,"REPRODUCED"))
        body=kit.PostgresWorkspaceTests.command(self)
        status,value,_=self.call("POST",self.base+"/ledger-commands",body)
        self.assertEqual(status,201)
        self.assertEqual(value["snapshot"]["mode"],"LOCAL_SYNTHETIC_ACCOUNT")
        self.assertEqual(self.call("GET",GET)[1]["contexts"],[])
        print(json.dumps({"test":self._testMethodName,"e1_before":dict(before),"e1_after":dict(before),
            "after_explicit_legacy_append":dict(self.counts()),"legacy_packet_status":"REPRODUCED"},sort_keys=True),flush=True)
