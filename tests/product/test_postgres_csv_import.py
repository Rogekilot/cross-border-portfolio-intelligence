"""Actual PG atomic CSV reports/source keys/revisions, with synthetic input only."""
import base64
import datetime as dt
import io
import json
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import psycopg

from tests.product import test_postgres_web_workspace as kit
from tests.product.test_postgres_web_auth import Client,SKIP
from persistence.web_account_store import AccountStoreError
from persistence.web_csv_store import CsvImportStore,_digest
from web_api.app import create_app
from web_api.auth import AuthSettings
from web_api.csv_requests import ImportProposal


@unittest.skipIf(bool(SKIP),SKIP)
class PostgresCsvTests(unittest.TestCase):
    setUpClass=classmethod(kit.PostgresWorkspaceTests.setUpClass.__func__)

    def setUp(self):
        kit.PostgresWorkspaceTests.setUp(self)
        self.csv=CsvImportStore(self.store,self.world,b"C"*32)

    def proposal(self,rows=None,kind="HOLDINGS",**changes):
        import csv
        stream=io.StringIO(newline="")
        writer=csv.writer(stream,lineterminator="\r\n")
        writer.writerow(["key","type","date","currency","symbol","quantity","amount","basis"])
        writer.writerows(rows or [["a","POSITION","2026-01-02","USD","SYN-A","2","","0"],["cash","CASH","2026-01-02","USD","","","100",""]])
        value=dict(operation_id=str(uuid.uuid4()),expected_revision_id=self.store.workspace(self.user["user_id"],self.ident,self.world)["current_revision_id"],
            as_of="2026-01-02" if kind=="HOLDINGS" else "2026-01-05",file_base64=base64.b64encode(stream.getvalue().encode()).decode(),filename="fictional.csv",kind=kind,
            source_namespace="fictional broker",source_account_key="fictional source account" if kind=="HOLDINGS" else None,
            snapshot_key="2026-01-02 opening" if kind=="HOLDINGS" else None,new_account_name="CSV fictional account" if kind=="HOLDINGS" else None,
            mapping=dict(source_row_key=0,event_type=1,event_date=2,currency=3,symbol=4,quantity=5,amount=6,cost_basis=7),
            constants={} if kind=="HOLDINGS" else dict(account_id=self.account),corrections=[],classifications=[],
            format=dict(delimiter=",",date_format="ISO",decimal_separator=".",thousands_separator=None),synthetic_acknowledged=True)
        value.update(changes)
        return ImportProposal(**value).model_dump()

    def preview(self,proposal):
        return self.csv.preview(self.user["user_id"],self.ident,proposal)

    def commit(self,proposal):
        preview=self.preview(proposal)
        return self.csv.commit(self.user["user_id"],self.ident,proposal,preview["preview_receipt"])

    def counts(self):
        return tuple(self.pg.owner.execute("SELECT count(*) FROM "+table+" WHERE "+("portfolio_id=%s" if table!="ledger_event" else "account_id IN(SELECT account_id FROM account WHERE portfolio_id=%s)"),(uuid.UUID(self.ident),)).fetchone()[0]
            for table in ("account","ledger_event","web_portfolio_revision","web_csv_report","web_csv_source_key"))

    def test_holdings_preview_commit_exact_report_and_old_proof(self):
        proposal=self.proposal()
        before=self.counts()
        preview=self.preview(proposal)
        self.assertEqual(preview["report"]["status"],"READY",preview)
        self.assertFalse(preview["financial_preview"]["snapshot"]["persisted"])
        self.assertEqual(self.counts(),before)
        saved=self.csv.commit(self.user["user_id"],self.ident,proposal,preview["preview_receipt"])
        self.assertEqual(saved["report"]["counts"]["imported"],2)
        self.assertEqual(saved["report"]["status"],"COMMITTED")
        self.assertEqual(self.counts(),tuple(a+b for a,b in zip(before,(1,2,1,1,3))))
        report=self.csv.get(self.user["user_id"],self.ident,saved["report"]["report_id"])["report"]
        self.assertEqual(report["file"],saved["report"]["file"])
        self.assertEqual(self.store.get_portfolio(self.user["user_id"],self.ident,self.world,revision_id=self.ident).snapshot(),self.snapshot)

    def test_quarantined_economic_fact_blocks_valid_cash_and_corrected_source_is_unclaimed(self):
        bad=self.proposal(rows=[["cash","CASH","2026-01-02","USD","","","100",""],["a","POSITION","2026-01-02","USD","REAL","2","",""]])
        before=self.counts()
        preview=self.preview(bad)
        self.assertIsNone(preview["financial_preview"])
        rejected=self.csv.commit(self.user["user_id"],self.ident,bad,preview["preview_receipt"])
        self.assertEqual(rejected["report"]["status"],"REPORT_ONLY")
        self.assertEqual(rejected["report"]["counts"]["imported"],0)
        self.assertEqual(self.counts(),tuple(a+b for a,b in zip(before,(0,0,0,1,0))))
        fixed=self.proposal(file_base64=bad["file_base64"],corrections=[dict(row_number=2,fields=dict(symbol="SYN-A"),reason="Explicit fictional identity correction")])
        saved=self.commit(fixed)
        self.assertEqual(saved["report"]["counts"]["imported"],2)
        self.assertEqual(saved["report"]["rows"][1]["cells"][4],"REAL")
        self.assertEqual(saved["report"]["rows"][1]["fields"]["symbol"],"SYN-A")

    def test_prior_snapshot_new_operation_no_account_and_changed_set_conflicts(self):
        first=self.commit(self.proposal())
        before=self.counts()
        same=self.proposal()
        repeated=self.commit(same)
        self.assertEqual(repeated["report"]["status"],"ALREADY_IMPORTED")
        self.assertEqual(repeated["report"]["counts"]["already_imported"],2)
        self.assertEqual(self.counts(),tuple(a+b for a,b in zip(before,(0,0,0,1,0))))
        changed=self.proposal(rows=[["a","POSITION","2026-01-02","USD","SYN-A","2","","0"],["cash","CASH","2026-01-02","USD","","","100",""],["b","POSITION","2026-01-02","USD","SYN-B","1","",""]])
        preview=self.preview(changed)
        with self.assertRaises(AccountStoreError) as error:
            self.csv.commit(self.user["user_id"],self.ident,changed,preview["preview_receipt"])
        self.assertEqual((error.exception.status,error.exception.code),(409,"SOURCE_SNAPSHOT_CONFLICT"))

    def test_exact_operation_retry_after_new_key_restart_and_changed_content_conflict(self):
        proposal=self.proposal()
        saved=self.commit(proposal)
        restarted=CsvImportStore(self.store,self.world,b"D"*32)
        repeat=restarted.commit(self.user["user_id"],self.ident,proposal,"0"*64)
        self.assertEqual(repeat["report"]["report_id"],saved["report"]["report_id"])
        with self.assertRaises(AccountStoreError) as error:
            restarted.commit(self.user["user_id"],self.ident,{**proposal,"filename":"changed.csv"},"0"*64)
        self.assertEqual(error.exception.code,"IDEMPOTENCY_CONFLICT")
        pending=self.proposal(source_account_key="other fictional account",snapshot_key="other")
        preview=self.preview(pending)
        with self.assertRaises(AccountStoreError) as error:
            restarted.commit(self.user["user_id"],self.ident,pending,preview["preview_receipt"])
        self.assertEqual(error.exception.code,"CSV_PREVIEW_REQUIRED")

    def test_zero_report_exact_retry_is_durable_and_does_not_claim_source(self):
        proposal=self.proposal(rows=[["a","POSITION","2026-01-02","USD","REAL","2","",""]])
        saved=self.commit(proposal)
        before=self.counts()
        restarted=CsvImportStore(self.store,self.world,b"D"*32)
        repeat=restarted.commit(self.user["user_id"],self.ident,proposal,"0"*64)
        self.assertEqual(repeat["report"]["report_id"],saved["report"]["report_id"])
        self.assertEqual(self.counts(),before)
        self.assertEqual(before[-1],0)

    def test_report_failure_rolls_back_account_ledger_revision_and_keys(self):
        proposal=self.proposal()
        preview=self.preview(proposal)
        before=self.counts()
        with patch.object(self.csv,"_insert_report",side_effect=AccountStoreError(503,"TEST_REPORT_FAILURE","Injected failure")):
            with self.assertRaises(AccountStoreError):
                self.csv.commit(self.user["user_id"],self.ident,proposal,preview["preview_receipt"])
        self.assertEqual(self.counts(),before)

    def test_report_growth_refuses_preview_and_commit_without_writes(self):
        from portfolio_import.csv_source import FIELDS
        raw=("key\n"+"".join("r"+str(index)+"\n" for index in range(128))).encode()
        constants={field:"x"*1400 for field in FIELDS if field!="source_row_key"}
        constants.update(account_id=self.account,event_type="DEPOSIT",event_date="2026-01-05",currency="USD")
        proposal=self.proposal(kind="TRANSACTIONS",file_base64=base64.b64encode(raw).decode(),mapping=dict(source_row_key=0),constants=constants)
        self.assertLess(len(json.dumps(dict(proposal=proposal,preview_receipt="0"*64),separators=(",",":")).encode()),32768)
        before=self.counts()
        for action in (lambda:self.preview(proposal),lambda:self.csv.commit(self.user["user_id"],self.ident,proposal,self.csv._receipt(self.user["user_id"],uuid.UUID(self.ident),proposal))):
            with self.assertRaises(AccountStoreError) as error:
                action()
            self.assertEqual((error.exception.status,error.exception.code),(422,"CSV_REPORT_TOO_LARGE"))
            self.assertEqual(self.counts(),before)
        normal=self.proposal();preview=self.preview(normal)
        from persistence import web_csv_store
        original=web_csv_store._bounded_report_text
        def final_refusal(report,**options):
            if report["persisted"]:
                raise AccountStoreError(422,"CSV_REPORT_TOO_LARGE","Injected final-size refusal")
            return original(report,**options)
        with patch("persistence.web_csv_store._bounded_report_text",side_effect=final_refusal):
            with self.assertRaises(AccountStoreError) as error:
                self.csv.commit(self.user["user_id"],self.ident,normal,preview["preview_receipt"])
            self.assertEqual(error.exception.code,"CSV_REPORT_TOO_LARGE")
        self.assertEqual(self.counts(),before)

    def test_concurrent_commands_keep_one_head_and_new_tables_are_append_only(self):
        left=self.proposal(rows=[["left","DEPOSIT","2026-01-05","USD","","","1",""]],kind="TRANSACTIONS")
        right=self.proposal(rows=[["right","DEPOSIT","2026-01-05","USD","","","2",""]],kind="TRANSACTIONS")
        previews=[self.preview(proposal) for proposal in (left,right)]
        before=self.counts()
        def commit(index):
            try:
                return self.csv.commit(self.user["user_id"],self.ident,(left,right)[index],previews[index]["preview_receipt"])["report"]["status"]
            except AccountStoreError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(commit,(0,1)))
        self.assertEqual(sorted(results),["COMMITTED","STALE_REVISION"])
        self.assertEqual(self.counts(),tuple(a+b for a,b in zip(before,(0,1,1,1,1))))
        for table in ("web_csv_report","web_csv_source_key"):
            with self.store.connect() as conn:
                for privilege in ("UPDATE","DELETE","TRUNCATE"):
                    self.assertFalse(conn.execute("SELECT has_table_privilege(current_user,%s,%s)",(table,privilege)).fetchone()[0])
            with self.assertRaises(psycopg.errors.RestrictViolation) as error:
                self.pg.owner.execute("UPDATE "+table+" SET portfolio_id=portfolio_id WHERE portfolio_id=%s",(uuid.UUID(self.ident),))
            self.assertEqual(error.exception.sqlstate,"23001")

    def test_already_imported_read_verifies_original_report_and_refuses_cycles(self):
        self.commit(self.proposal())
        repeated=self.commit(self.proposal())
        report_id=repeated["report"]["report_id"]
        self.csv.get(self.user["user_id"],self.ident,report_id)
        self.pg.owner.execute("ALTER TABLE web_csv_source_key DISABLE TRIGGER web_csv_source_immutable")
        self.pg.owner.execute("UPDATE web_csv_source_key SET report_id=%s WHERE portfolio_id=%s AND source_kind='EVENT'",(uuid.UUID(report_id),uuid.UUID(self.ident)))
        self.pg.owner.execute("ALTER TABLE web_csv_source_key ENABLE TRIGGER web_csv_source_immutable")
        with self.assertRaises(AccountStoreError) as error:
            self.csv.get(self.user["user_id"],self.ident,report_id)
        self.assertEqual((error.exception.status,error.exception.code),(503,"IMPORT_REPORT_DIFFERS"))

    def test_report_only_ready_interpretation_cannot_diverge_from_original_cells(self):
        from marketdata.canonical import canonical_json,sha256_hex
        proposal=self.proposal(rows=[["cash","CASH","2026-01-02","USD","","","100",""],["bad","POSITION","2026-01-02","USD","REAL","1","",""]])
        saved=self.commit(proposal)
        report_id=uuid.UUID(saved["report"]["report_id"])
        self.csv.get(self.user["user_id"],self.ident,str(report_id))
        changed=json.loads(canonical_json(saved["report"]));changed["rows"][0]["event"]["amount"]="999"
        text=canonical_json(changed)
        self.pg.owner.execute("ALTER TABLE web_csv_report DISABLE TRIGGER web_csv_report_immutable")
        self.pg.owner.execute("UPDATE web_csv_report SET report_json=%s,report_sha256=%s WHERE report_id=%s",(text,sha256_hex(text.encode()),report_id))
        self.pg.owner.execute("ALTER TABLE web_csv_report ENABLE TRIGGER web_csv_report_immutable")
        with self.assertRaises(AccountStoreError) as error:
            self.csv.get(self.user["user_id"],self.ident,str(report_id))
        self.assertEqual((error.exception.status,error.exception.code),(503,"IMPORT_REPORT_DIFFERS"))

    def test_transactions_identical_distinct_keys_and_cross_operation_source_noop(self):
        rows=[["one","DEPOSIT","2026-01-05","USD","","","25",""],["two","DEPOSIT","2026-01-05","USD","","","25",""]]
        first=self.commit(self.proposal(rows=rows,kind="TRANSACTIONS"))
        self.assertEqual(first["report"]["counts"]["imported"],2)
        self.assertEqual(first["workspace_result"]["workspace"]["ledger"]["current_state"]["accounts"][0]["cash"][0]["amount"],"550")
        second=self.commit(self.proposal(rows=rows,kind="TRANSACTIONS"))
        self.assertEqual(second["report"]["status"],"ALREADY_IMPORTED")
        changed=self.proposal(rows=[["one","DEPOSIT","2026-01-05","USD","","","26",""]],kind="TRANSACTIONS")
        with self.assertRaises(AccountStoreError) as error:
            self.commit(changed)
        self.assertEqual(error.exception.code,"SOURCE_KEY_CONFLICT")

    def test_same_batch_duplicate_keys_and_incomplete_transfer_are_report_only(self):
        for proposal in (self.proposal(rows=[["one","DEPOSIT","2026-01-05","USD","","","25",""],["one","DEPOSIT","2026-01-05","USD","","","25",""]],kind="TRANSACTIONS"),
                         self.proposal(rows=[["out","TRANSFER_OUT","2026-01-05","USD","","","1",""]],kind="TRANSACTIONS",constants=dict(account_id=self.account,counterparty_account_id=self.account))):
            before=self.counts()
            saved=self.commit(proposal)
            self.assertEqual(saved["report"]["status"],"REPORT_ONLY")
            self.assertEqual(saved["report"]["counts"]["imported"],0)
            self.assertEqual(self.counts(),tuple(a+b for a,b in zip(before,(0,0,0,1,0))))

    def test_explicit_nondata_preserved_and_not_claimed_as_imported(self):
        proposal=self.proposal(rows=[["a","POSITION","2026-01-02","USD","SYN-A","2","",""] , ["note","=SUM(1)","bad","","","","",""]],
            classifications=[dict(row_number=2,classification="NON_DATA",reason="I confirm this is a note,not a holding")])
        saved=self.commit(proposal)
        self.assertEqual(saved["report"]["counts"]["imported"],1)
        self.assertEqual(saved["report"]["counts"]["excluded"],1)
        raw,_=self.csv.export_report(self.user["user_id"],self.ident,saved["report"]["report_id"],"json")
        self.assertIn("=SUM(1)",raw)
        self.assertIn("I confirm",raw)

    def test_owner_csrf_and_report_export_headers(self):
        app=create_app(account_store=self.store,auth_settings=AuthSettings.local(),enable_saved_synthetic=True)
        client=Client(app,"127.0.0.61")
        client.cookies["finweb_session"]=self.store.start_session(self.user,3600)
        client.call("GET","/api/v1/auth/session")
        proposal=self.proposal()
        self.assertEqual(client.call("POST",self.base+"/imports/preview",proposal,extra={"X-Finweb-CSRF":""})[0],403)
        status,preview,_=client.call("POST",self.base+"/imports/preview",proposal)
        self.assertEqual(status,200,preview)
        status,saved,_=client.call("POST",self.base+"/imports/commit",dict(proposal=proposal,preview_receipt=preview["preview_receipt"]))
        self.assertEqual(status,201,saved)
        status,data,headers=client.call("GET",self.base+"/imports/"+saved["report"]["report_id"]+"/export")
        self.assertEqual(status,200,data)
        header=dict(headers)
        self.assertEqual(header[b"x-finweb-portfolio-id"].decode(),self.ident)
        self.assertIn(b"finweb-report-",header[b"content-disposition"])

    def test_corrupt_report_fields_refuse_after_owner_check(self):
        saved=self.commit(self.proposal())
        ident=uuid.UUID(saved["report"]["report_id"])
        original=self.pg.owner.execute("SELECT report_json,report_sha256 FROM web_csv_report WHERE report_id=%s",(ident,)).fetchone()
        other=self.store.register("user"+uuid.uuid4().hex[:15],"scrypt$131072$8$1$"+"0"*100)
        changed=json.loads(original[0]);changed["proposal"].pop("synthetic_acknowledged")
        text=json.dumps(changed,sort_keys=True,separators=(",",":"))
        self.pg.owner.execute("ALTER TABLE web_csv_report DISABLE TRIGGER web_csv_report_immutable")
        self.pg.owner.execute("UPDATE web_csv_report SET report_json=%s,report_sha256=%s WHERE report_id=%s",(text,__import__('hashlib').sha256(text.encode()).hexdigest(),ident))
        self.pg.owner.execute("ALTER TABLE web_csv_report ENABLE TRIGGER web_csv_report_immutable")
        with self.assertRaises(AccountStoreError) as error:
            self.csv.get(self.user["user_id"],self.ident,str(ident))
        self.assertEqual((error.exception.status,error.exception.code),(503,"IMPORT_REPORT_DIFFERS"))
        with self.assertRaises(AccountStoreError) as error:
            self.csv.get(other["user_id"],self.ident,str(ident))
        self.assertEqual(error.exception.status,404)

    def test_report_only_strict_nested_metadata_enums_and_source_bytes(self):
        bad=self.proposal(rows=[["bad","POSITION","2026-01-02","USD","REAL","1","",""]])
        saved=self.commit(bad)
        report_id=uuid.UUID(saved["report"]["report_id"])
        original=json.loads(self.pg.owner.execute("SELECT report_json FROM web_csv_report WHERE report_id=%s",(report_id,)).fetchone()[0])
        from marketdata.canonical import canonical_json,sha256_hex
        for mutate in (lambda r:r["proposal"].update(kind="UNKNOWN"),lambda r:r["proposal"]["format"].update(date_format="AUTO"),
                       lambda r:r["proposal"]["constants"].update(unknown_field="value"),
                       lambda r:r["proposal"].update(classifications=[dict(row_number=1,classification="IMPLICITLY_CONFIRMED",reason="changed")]),
                       lambda r:r["proposal"].update(file_base64=base64.b64encode(b"bad\nchanged\n").decode())):
            changed=json.loads(json.dumps(original));mutate(changed);changed["proposal_digest"]=_digest(changed["proposal"])
            text=canonical_json(changed)
            self.pg.owner.execute("ALTER TABLE web_csv_report DISABLE TRIGGER web_csv_report_immutable")
            self.pg.owner.execute("UPDATE web_csv_report SET report_json=%s,report_sha256=%s,proposal_sha256=%s WHERE report_id=%s",(text,sha256_hex(text.encode()),changed["proposal_digest"],report_id))
            self.pg.owner.execute("ALTER TABLE web_csv_report ENABLE TRIGGER web_csv_report_immutable")
            with self.assertRaises(AccountStoreError) as error:
                self.csv.get(self.user["user_id"],self.ident,str(report_id))
            self.assertEqual((error.exception.status,error.exception.code),(503,"IMPORT_REPORT_DIFFERS"))

    def test_fixed_revision_exports_preserve_native_zeros_unknown_and_links(self):
        first=self.commit(self.proposal())
        text,_=self.csv.export_portfolio(self.user["user_id"],self.ident,self.ident,"transactions","json")
        old=json.loads(text)
        self.assertEqual(len(old["events"]),3)
        current,_=self.csv.export_portfolio(self.user["user_id"],self.ident,first["report"]["revision_id"],"transactions","json")
        current=json.loads(current)
        self.assertEqual(len(current["events"]),5)
        self.assertTrue(any(row["source_reference"].startswith("CP7 CSV source:") for row in current["events"]))
        self.assertTrue(any(row["cost_basis"]=="0" for row in current["events"]))
        self.assertTrue(any(row["cost_basis"] is None for row in old["events"]))

    def test_report_capacity_and_exact_retry_before_cap(self):
        proposal=self.proposal(rows=[["bad","POSITION","2026-01-02","USD","REAL","1","",""]])
        first=self.commit(proposal)
        template=json.loads(self.pg.owner.execute("SELECT report_json FROM web_csv_report WHERE report_id=%s",(uuid.UUID(first["report"]["report_id"]),)).fetchone()[0])
        for index in range(999):
            copy=json.loads(json.dumps(template))
            op=str(uuid.uuid4());rid=str(uuid.uuid5(uuid.UUID(self.ident),"csv-report:"+op))
            copy["operation_id"]=op;copy["report_id"]=rid;copy["proposal"]["operation_id"]=op;copy["proposal_digest"]=_digest(copy["proposal"])
            from marketdata.canonical import canonical_json,sha256_hex
            text=canonical_json(copy)
            self.pg.owner.execute("INSERT INTO web_csv_report VALUES(%s,%s,%s,%s,%s,%s,NULL,'REPORT_ONLY',%s)",
                (uuid.UUID(rid),uuid.UUID(self.ident),uuid.UUID(op),copy["proposal_digest"],text,sha256_hex(text.encode()),copy["created_at"]))
        before=self.counts()
        retry=self.csv.commit(self.user["user_id"],self.ident,proposal,"0"*64)
        self.assertEqual(retry["report"]["report_id"],first["report"]["report_id"])
        pending=self.proposal(source_account_key="other")
        preview=self.preview(pending)
        with self.assertRaises(AccountStoreError) as error:
            self.csv.commit(self.user["user_id"],self.ident,pending,preview["preview_receipt"])
        self.assertEqual((error.exception.status,error.exception.code),(429,"CSV_REPORT_CAPACITY"))
        self.assertEqual(self.counts(),before)
        found=[];cursor=None;first_cursor=None
        while True:
            page=self.csv.list(self.user["user_id"],self.ident,cursor)
            self.assertLessEqual(len(page["reports"]),32)
            found.extend(row["report_id"] for row in page["reports"])
            cursor=page["next_cursor"]
            if first_cursor is None:
                first_cursor=cursor
            if cursor is None:
                break
        self.assertEqual(len(set(found)),1000)
        self.assertEqual(len(found),1000)
        other=self.store.register("user"+uuid.uuid4().hex[:15],"scrypt$131072$8$1$"+"0"*100)
        with self.assertRaises(AccountStoreError) as error:
            self.csv.list(other["user_id"],self.ident,first_cursor)
        self.assertEqual(error.exception.status,404)
        import hashlib,hmac
        from marketdata.canonical import canonical_json
        token=base64.urlsafe_b64encode(canonical_json([self.user["user_id"],self.ident,"2000-01-01T00:00:00.000000Z",str(uuid.UUID(int=0))]).encode()).decode().rstrip("=")
        empty_cursor=token+"."+hmac.new(b"C"*32,token.encode(),hashlib.sha256).hexdigest()
        page=self.csv.list(self.user["user_id"],self.ident,empty_cursor)
        self.assertEqual((page["reports"],page["next_cursor"]),([],None))

    def test_corrupt_financial_key_is_refused_before_preview_or_new_commit(self):
        saved=self.commit(self.proposal())
        source=self.pg.owner.execute("SELECT source_key,event_id,report_id,row_number,account_id FROM web_csv_source_key WHERE portfolio_id=%s AND source_kind='EVENT' ORDER BY row_number LIMIT 1",(uuid.UUID(self.ident),)).fetchone()
        other_event=uuid.UUID(self.initial["ledger"]["events"][0]["event_id"])
        for field,value in (("event_id",other_event),("row_number",128),("account_id",uuid.UUID(self.account))):
            self.pg.owner.execute("ALTER TABLE web_csv_source_key DISABLE TRIGGER web_csv_source_immutable")
            self.pg.owner.execute("UPDATE web_csv_source_key SET "+field+"=%s WHERE source_key=%s",(value,source[0]))
            self.pg.owner.execute("ALTER TABLE web_csv_source_key ENABLE TRIGGER web_csv_source_immutable")
            with self.assertRaises(AccountStoreError) as error:
                self.preview(self.proposal())
            self.assertEqual((error.exception.status,error.exception.code),(503,"IMPORT_REPORT_DIFFERS"))
            original={"event_id":source[1],"report_id":source[2],"row_number":source[3],"account_id":source[4]}[field]
            self.pg.owner.execute("ALTER TABLE web_csv_source_key DISABLE TRIGGER web_csv_source_immutable")
            self.pg.owner.execute("UPDATE web_csv_source_key SET "+field+"=%s WHERE source_key=%s",(original,source[0]))
            self.pg.owner.execute("ALTER TABLE web_csv_source_key ENABLE TRIGGER web_csv_source_immutable")

    def test_all_32_events_are_atomic_and_33_never_truncated(self):
        def rows(count):
            return [[str(index),"DEPOSIT","2026-01-05","USD","","","1",""] for index in range(count)]
        before=self.counts()
        saved=self.commit(self.proposal(rows=rows(33),kind="TRANSACTIONS"))
        self.assertEqual((saved["report"]["status"],saved["report"]["counts"]["imported"]),("REPORT_ONLY",0))
        self.assertEqual(self.counts(),tuple(a+b for a,b in zip(before,(0,0,0,1,0))))
        saved=self.commit(self.proposal(rows=rows(32),kind="TRANSACTIONS"))
        self.assertEqual(saved["report"]["counts"]["imported"],32)
        self.assertEqual(saved["workspace_result"]["workspace"]["ledger"]["current_state"]["accounts"][0]["cash"][0]["amount"],"532")

    def test_valid_pair_and_ambiguous_name_are_not_guessed(self):
        holdings=self.commit(self.proposal(rows=[["cash","CASH","2026-01-02","USD","","","100",""]]))
        second=next(row["account_id"] for row in holdings["workspace_result"]["workspace"]["accounts"] if row["account_id"]!=self.account)
        import csv
        stream=io.StringIO(newline="");writer=csv.writer(stream)
        writer.writerow(["key","type","date","currency","amount","account","counterparty"])
        writer.writerow(["out","TRANSFER_OUT","2026-01-05","USD","25",self.account,second])
        writer.writerow(["in","TRANSFER_IN","2026-01-05","USD","25",second,self.account])
        p=self.proposal(kind="TRANSACTIONS",file_base64=base64.b64encode(stream.getvalue().encode()).decode(),constants={},
            mapping=dict(source_row_key=0,event_type=1,event_date=2,currency=3,amount=4,account_id=5,counterparty_account_id=6))
        saved=self.commit(p)
        self.assertEqual(saved["report"]["counts"]["imported"],2)
        self.csv.get(self.user["user_id"],self.ident,saved["report"]["report_id"])
        self.pg.owner.execute("UPDATE account SET name='Duplicate visible name' WHERE portfolio_id=%s",(uuid.UUID(self.ident),))
        ambiguous=self.proposal(rows=[["new","DEPOSIT","2026-01-05","USD","","","1",""]],kind="TRANSACTIONS",constants=dict(account_name="Duplicate visible name"))
        self.assertEqual(self.commit(ambiguous)["report"]["status"],"REPORT_ONLY")

    def test_preview_receipt_changes_and_foreign_parse_are_refused_before_source(self):
        proposal=self.proposal();preview=self.preview(proposal)
        with self.assertRaises(AccountStoreError) as error:
            self.csv.commit(self.user["user_id"],self.ident,{**proposal,"filename":"changed.csv"},preview["preview_receipt"])
        self.assertEqual(error.exception.code,"CSV_PREVIEW_REQUIRED")
        with self.assertRaises(AccountStoreError):
            self.csv.commit(self.user["user_id"],self.ident,proposal,_digest(proposal))
        other=self.store.register("user"+uuid.uuid4().hex[:15],"scrypt$131072$8$1$"+"0"*100)
        with patch("persistence.web_csv_store.parse_source",side_effect=AssertionError("foreign source work")):
            with self.assertRaises(AccountStoreError) as error:
                self.csv.parse(other["user_id"],self.ident,dict(file_base64="!",filename="fictional.csv",delimiter=","))
            self.assertEqual(error.exception.status,404)

    def test_public_fifo_witness_exact_unit_cost_and_fractional_split_refusal_export(self):
        from web_api.workspace_requests import LedgerCommand
        proposal=self.proposal(rows=[["a","POSITION","2026-01-02","USD","SYN-A","3","","1"]],constants=dict(acquired_on="2026-01-01"),new_account_name="=SUM(1)")
        saved=self.commit(proposal)
        account=next(row["account_id"] for row in saved["workspace_result"]["workspace"]["accounts"] if row["name"]=="=SUM(1)")
        listing=self.initial["listings"][0]["listing_id"]
        body=LedgerCommand(operation_id=str(uuid.uuid4()),expected_revision_id=saved["report"]["revision_id"],as_of="2026-01-03",operation="APPEND",
            events=[dict(event_type="SPLIT",account_id=account,event_date="2026-01-03",currency="USD",listing_id=listing,split_ratio=dict(new_units="2",old_units="1"))]).model_dump()
        split=self.store.command(self.user["user_id"],self.ident,body,self.world)
        text,_=self.csv.export_portfolio(self.user["user_id"],self.ident,split["workspace"]["revision_id"],"holdings","json")
        payload=json.loads(text);book=next(book for book in payload["lot_witness"]["books"] if book["account_id"]==account)
        self.assertEqual((book["quantity"],book["lots"][0]["unit_cost"],book["lots"][0]["basis"]),("6","1/6","1"))
        self.assertEqual(payload["lot_witness"]["lot_method"],"FIFO/1")
        csv_text,_=self.csv.export_portfolio(self.user["user_id"],self.ident,split["workspace"]["revision_id"],"holdings","csv")
        self.assertIn("1/6",csv_text);self.assertIn("'=SUM(1)",csv_text)
        fractional=self.commit(self.proposal(rows=[["a","POSITION","2026-01-02","USD","SYN-A","1","",""]],source_account_key="fractional source",snapshot_key="fractional"))
        account2=next(row["account_id"] for row in fractional["workspace_result"]["workspace"]["accounts"] if row["account_id"] not in {row["account_id"] for row in split["workspace"]["accounts"]})
        body=LedgerCommand(operation_id=str(uuid.uuid4()),expected_revision_id=fractional["report"]["revision_id"],as_of="2026-01-03",operation="APPEND",
            events=[dict(event_type="SPLIT",account_id=account2,event_date="2026-01-03",currency="USD",listing_id=listing,split_ratio=dict(new_units="1",old_units="3"))]).model_dump()
        refused=self.store.command(self.user["user_id"],self.ident,body,self.world)
        text,_=self.csv.export_portfolio(self.user["user_id"],self.ident,refused["workspace"]["revision_id"],"holdings","json")
        payload=json.loads(text);book=next(book for book in payload["lot_witness"]["books"] if book["account_id"]==account2)
        self.assertIsNone(book["quantity"]);self.assertIn("SPLIT_FRACTION",book["causes"])
        self.assertNotIn("0.333333",text)

    def test_export_old_and_corrected_csv_event_relations_are_distinct(self):
        from web_api.workspace_requests import LedgerCommand
        saved=self.commit(self.proposal(rows=[["one","DEPOSIT","2026-01-05","USD","","","25",""]],kind="TRANSACTIONS"))
        old_revision=saved["report"]["revision_id"];event_id=saved["report"]["rows"][0]["event_id"]
        body=LedgerCommand(operation_id=str(uuid.uuid4()),expected_revision_id=old_revision,as_of="2026-01-05",operation="CORRECT",target_event_ids=[event_id],
            events=[dict(event_type="DEPOSIT",account_id=self.account,event_date="2026-01-05",currency="USD",amount="40")]).model_dump()
        corrected=self.store.command(self.user["user_id"],self.ident,body,self.world)
        old,_=self.csv.export_portfolio(self.user["user_id"],self.ident,old_revision,"transactions","json")
        current,_=self.csv.export_portfolio(self.user["user_id"],self.ident,corrected["workspace"]["revision_id"],"transactions","json")
        old=json.loads(old);current=json.loads(current)
        self.assertEqual(len(old["events"]),4);self.assertEqual(len(current["events"]),6)
        self.assertEqual(current["csv_sources"],[dict(event_id=event_id,source_key=saved["report"]["rows"][0]["source_key"],report_id=saved["report"]["report_id"],row_number=1,
            file_sha256=saved["report"]["file"]["sha256"],source_identity=saved["report"]["rows"][0]["source_identity"])])
        self.assertEqual(set(current["benchmark"]),{"state","pin"})
        self.assertFalse(any(row["corrects_event_id"] for row in old["events"]))
