"""Owned CSV proposals, atomic financial imports and immutable provenance reports."""
from __future__ import annotations

import csv
import base64
import hashlib
import hmac
import io
import json
import re
import uuid
from contextlib import nullcontext
from dataclasses import replace

import psycopg

from domain.replay import reconstruct,reconstruct_fifo
from marketdata.canonical import canonical_json,sha256_hex
from persistence import ledger_store
from persistence.web_account_store import AccountStoreError,not_found
from persistence.web_workspace_store import WorkspaceStore,_uuid
from portfolio_import.csv_source import CsvSourceError,LIMITS,VERSION,normalized_event,parse_source,validate_proposal

REPORT_FIELDS=set("schema report_id portfolio_id operation_id expected_revision_id proposal_digest persisted status file proposal parser rows counts batch_errors revision_id created_at".split())
ROW_FIELDS=set("row_number physical_start physical_end cells classification reason fields errors event source_identity source_key existing_event_id disposition event_id".split())
PROPOSAL_FIELDS=set("operation_id expected_revision_id as_of file_base64 filename kind source_namespace source_account_key snapshot_key new_account_name mapping constants corrections classifications format synthetic_acknowledged".split())
COUNT_FIELDS=set("total economic ready quarantined excluded already_imported imported".split())


def _digest(value):
    return sha256_hex(canonical_json(value).encode())


def _bounded_report_text(report,*,prospective=False):
    value=report
    if prospective:
        # Final metadata can grow after a rollback-only preview. Reserve its
        # maximum serialized shape, without binding time or sequence to identity.
        value={**report,"persisted":True,"status":"ALREADY_IMPORTED",
            "revision_id":"ffffffff-ffff-ffff-ffff-ffffffffffff","created_at":"9999-12-31T23:59:59.999999Z",
            "counts":{**report["counts"],"imported":32}}
    text=canonical_json(value)
    if len(text.encode("utf-8"))>LIMITS["report_bytes"]:
        raise AccountStoreError(422,"CSV_REPORT_TOO_LARGE","The complete immutable report exceeds2000000 UTF-8 bytes; no report or financial facts were saved")
    return text


def _facts(event,holdings=False):
    value=dict(zip(ledger_store.EVENT_COLUMNS,ledger_store.event_to_row(event)))
    value={key:str(item) if isinstance(item,uuid.UUID) else item for key,item in value.items()}
    value.pop("event_id")
    value.pop("source_reference")
    if holdings:
        value["account_id"]="NEW_SOURCE_ACCOUNT"
    return _digest(value)


class CsvImportStore:
    def __init__(self,store,world,preview_key):
        self.store,self.world,self.key=store,world,preview_key
        self.workspace=WorkspaceStore(store,world)

    def _owned(self,conn,user_id,ident):
        return self.workspace._initial(conn,user_id,ident)

    def parse(self,user_id,portfolio_id,body):
        ident=_uuid(portfolio_id)
        with self.store.connect() as conn:
            self._owned(conn,user_id,ident)
        try:
            parsed=parse_source(body["file_base64"],body["filename"],body["delimiter"])
        except CsvSourceError as error:
            raise AccountStoreError(422,"CSV_FILE_REFUSED",str(error)) from None
        return dict(schema_version="finweb.cp7/1",portfolio_id=str(ident),**parsed)

    def _receipt(self,user_id,ident,proposal):
        value=[str(user_id),str(ident),proposal["operation_id"],proposal["expected_revision_id"],_digest(proposal)]
        return hmac.new(self.key,canonical_json(value).encode(),hashlib.sha256).hexdigest()

    @staticmethod
    def _lock(conn,schema,ident):
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",("finweb.web_revision.portfolio:"+schema+":"+str(ident),))

    def _source(self,conn,ident,key):
        return conn.execute("SELECT identity_json,content_sha256,source_kind,report_id,row_number,account_id,event_id "
            "FROM web_csv_source_key WHERE portfolio_id=%s AND source_key=%s",(ident,key)).fetchone()

    def _verify_origin(self,conn,user_id,ident,key,source,cache):
        try:
            origin_id=str(source[3])
            if origin_id not in cache:
                # Validate the exact original committed row without recursively
                # traversing other rows' earlier aliases across1000 reports.
                cache[origin_id]=self._read(conn,user_id,ident,origin_id,_verify_origins=False)
            report=cache[origin_id]
            if report["status"]!="COMMITTED":
                raise ValueError("source key has no successful original import")
            if source[2]=="EVENT":
                row=next((row for row in report["rows"] if row["row_number"]==source[4]),None)
                if row is None or row["disposition"]!="READY" or row["source_key"]!=key or row["event_id"]!=str(source[6]) or row["event"]["account_id"]!=str(source[5]):
                    raise ValueError("source key/report/raw row/event/account mismatch")
            elif source[2]=="SNAPSHOT":
                if source[4]!=0 or report["proposal"]["kind"]!="HOLDINGS" or any(row["event"]["account_id"]!=str(source[5]) for row in report["rows"] if row["classification"]=="ECONOMIC"):
                    raise ValueError("snapshot source/original account mismatch")
            else:
                raise ValueError("invalid source kind")
            return report
        except AccountStoreError as error:
            if error.status!=404:
                raise
            raise AccountStoreError(503,"IMPORT_REPORT_DIFFERS","An owned financial source key points to an unavailable original report") from None
        except (ValueError,TypeError,KeyError,AttributeError):
            raise AccountStoreError(503,"IMPORT_REPORT_DIFFERS","An owned financial source key no longer matches its original successful report") from None

    def _evaluate(self,conn,user_id,ident,proposal):
        validate_proposal(proposal)
        parsed=parse_source(proposal["file_base64"],proposal["filename"],proposal["format"]["delimiter"])
        if any(index>=len(parsed["columns"]) for index in proposal["mapping"].values()):
            raise CsvSourceError("CSV_MAPPING_COLUMN_OUT_OF_RANGE")
        known_rows={row["row_number"] for row in parsed["rows"]}
        if any(row["row_number"] not in known_rows for row in proposal["corrections"]+proposal["classifications"]):
            raise CsvSourceError("CSV_UNKNOWN_OVERRIDE_ROW")
        account_rows=conn.execute("SELECT account_id,name FROM account WHERE portfolio_id=%s ORDER BY account_id",(ident,)).fetchall()
        accounts=[dict(account_id=str(row[0]),name=row[1]) for row in account_rows]
        holdings=proposal["kind"]=="HOLDINGS"
        snapshot_identity=["SNAPSHOT",str(ident),proposal["source_namespace"],proposal["source_account_key"],proposal["snapshot_key"]]
        snapshot_key=_digest(snapshot_identity)
        old_snapshot=self._source(conn,ident,snapshot_key) if holdings else None
        verified_origins={}
        if old_snapshot:
            self._verify_origin(conn,user_id,ident,snapshot_key,old_snapshot,verified_origins)
        account_id=old_snapshot[5] if old_snapshot else uuid.uuid5(ident,"csv-account:"+proposal["operation_id"])
        owned_accounts={row[0] for row in account_rows}|({account_id} if holdings else set())
        corrections={row["row_number"]:row for row in proposal["corrections"]}
        classes={row["row_number"]:row for row in proposal["classifications"]}
        listings=[dict(row,mic=self.world.raw["mic"]) for row in self.world.capabilities()["listings"]]
        rows=[]
        events=[]
        fingerprints={}
        seen={}
        for original in parsed["rows"]:
            number=original["row_number"]
            fields=dict(proposal["constants"])
            fields.update({name:original["cells"][index] for name,index in proposal["mapping"].items() if index<len(original["cells"])})
            fields.update(corrections.get(number,{}).get("fields",{}))
            classification=classes.get(number,{"classification":"ECONOMIC","reason":""})
            row=dict(**original,classification=classification["classification"],reason=classification["reason"],fields=fields,errors=[],event=None,
                source_identity=None,source_key=None,existing_event_id=None,disposition="READY",event_id=None)
            rows.append(row)
            if classification["classification"]!="ECONOMIC":
                row["disposition"]="EXCLUDED"
                continue
            try:
                if len(original["cells"])!=len(parsed["columns"]):
                    raise ValueError("RAGGED_RECORD")
                source_row=fields.get("source_row_key","")
                if not source_row or source_row!=source_row.strip() or len(source_row)>128 or any(ord(char)<32 for char in source_row):
                    raise ValueError("EXPLICIT_STABLE_SOURCE_ROW_KEY_REQUIRED")
                event_body=normalized_event(fields,proposal,accounts,listings,str(account_id))
                identity=["EVENT",str(ident),proposal["source_namespace"],proposal["kind"],
                    proposal["source_account_key"] if holdings else event_body["account_id"],proposal["snapshot_key"] if holdings else "",source_row]
                key=_digest(identity)
                row.update(event=event_body,source_identity=identity,source_key=key)
                if key in seen:
                    previous=seen[key]
                    previous["errors"].append(dict(code="DUPLICATE_SOURCE_KEY",field="source_row_key",detail="Each intended economic record needs a distinct source key"))
                    previous["disposition"]="QUARANTINED"
                    raise ValueError("DUPLICATE_SOURCE_KEY")
                seen[key]=row
                event=self.workspace._event(event_body,uuid.UUID(proposal["operation_id"]),number,owned_accounts)
                event=replace(event,event_id=uuid.uuid5(ident,"csv-event:"+key),source_reference="CP7 CSV source:"+key)
                fingerprint=_facts(event,holdings)
                fingerprints[key]=fingerprint
                prior=self._source(conn,ident,key)
                if prior is not None:
                    self._verify_origin(conn,user_id,ident,key,prior,verified_origins)
                    if prior[0]!=canonical_json(identity) or prior[1]!=fingerprint or prior[2]!="EVENT":
                        raise ValueError("SOURCE_KEY_CONFLICT")
                    row.update(disposition="ALREADY_IMPORTED",existing_event_id=str(prior[6]),event_id=str(prior[6]))
                else:
                    row["event_id"]=str(event.event_id)
                    events.append((row,event,fingerprint))
            except AccountStoreError as error:
                if error.status!=404:
                    raise
                row["errors"].append(dict(code="OWNED_ACCOUNT_REQUIRED",field="account_id",detail="The record must name an owned account"))
                row["disposition"]="QUARANTINED"
            except (ValueError,TypeError,KeyError) as error:
                row["errors"].append(dict(code=str(error).split("\n",1)[0][:160],field="*",detail="Correct the explicit source interpretation before importing any economic row"))
                row["disposition"]="QUARANTINED"
        counts=dict(total=len(rows),economic=sum(row["classification"]=="ECONOMIC" for row in rows),
            ready=sum(row["disposition"]=="READY" for row in rows),quarantined=sum(row["disposition"]=="QUARANTINED" for row in rows),
            excluded=sum(row["disposition"]=="EXCLUDED" for row in rows),already_imported=sum(row["disposition"]=="ALREADY_IMPORTED" for row in rows),imported=0)
        batch=[]
        if counts["ready"]>32:
            batch.append(dict(code="EVENT_LIMIT",detail="At most32 new events may be confirmed together; no truncation or automatic chunking"))
        snapshot_fingerprint=_digest(sorted(fingerprints.items()))
        if holdings and not counts["quarantined"]:
            if old_snapshot and (old_snapshot[0]!=canonical_json(snapshot_identity) or old_snapshot[1]!=snapshot_fingerprint):
                batch.append(dict(code="SOURCE_SNAPSHOT_CONFLICT",detail="The complete economic record set differs from the already recorded snapshot"))
            if not old_snapshot and counts["ready"] and len(accounts)>=16:
                batch.append(dict(code="ACCOUNT_CAPACITY",detail="At most16 account containers are supported"))
        status="QUARANTINED" if counts["quarantined"] else "BATCH_REFUSED" if batch else "READY"
        report=dict(schema="finweb.csv_import/1",report_id=str(uuid.uuid5(ident,"csv-report:"+proposal["operation_id"])),portfolio_id=str(ident),
            operation_id=proposal["operation_id"],expected_revision_id=proposal["expected_revision_id"],proposal_digest=_digest(proposal),persisted=False,status=status,
            file=dict(filename=proposal["filename"],sha256=parsed["file_sha256"],byte_count=parsed["byte_count"],bom=parsed["bom"]),proposal=proposal,
            parser=dict(version=VERSION,dialect="stdlib-explicit-v1"),rows=rows,counts=counts,batch_errors=batch,revision_id=None,created_at=None)
        return report,events,account_id,(snapshot_key,snapshot_identity,snapshot_fingerprint,old_snapshot)

    def _apply(self,conn,user_id,ident,proposal,report,events,account_id,*,execution_scope=None):
        # A prior rollback preview may have made deferred constraints immediate.
        # Restore batch insertion semantics; command validates the whole batch
        # with SET CONSTRAINTS ALL IMMEDIATE before issuing its result.
        conn.execute("SET CONSTRAINTS ALL DEFERRED")
        if proposal["kind"]=="HOLDINGS":
            conn.execute("INSERT INTO account VALUES(%s,%s,%s)",(account_id,ident,proposal["new_account_name"]))
        body=dict(operation_id=str(uuid.uuid5(ident,"csv-command:"+proposal["operation_id"])),expected_revision_id=proposal["expected_revision_id"],as_of=proposal["as_of"],
            operation="APPEND",events=[row["event"] for row,event,fingerprint in events],target_event_ids=[],account_name=None)
        return self.workspace.command(user_id,str(ident),body,connection=conn,prepared_events=[event for row,event,fingerprint in events],execution_scope=execution_scope)

    def _proposal(self,conn,user_id,ident,proposal,*,execution_scope=None):
        record=self.workspace._record(conn,user_id,ident)
        if str(record["revision_id"])!=proposal["expected_revision_id"]:
            raise AccountStoreError(409,"STALE_REVISION","The saved workspace changed; re-preview before confirming")
        try:
            report,events,account_id,snapshot=self._evaluate(conn,user_id,ident,proposal)
        except CsvSourceError as error:
            raise AccountStoreError(422,"CSV_FILE_REFUSED",str(error)) from None
        result=None
        if not report["counts"]["quarantined"] and not report["batch_errors"] and events:
            try:
                with conn.transaction():
                    result=self._apply(conn,user_id,ident,proposal,report,events,account_id,execution_scope=execution_scope)
                    WorkspaceStore._preview(result)
                    result["workspace"]["revision_id"]=str(record["revision_id"])
                    result["workspace"]["current_revision_id"]=str(record["revision_id"])
                    result["workspace"]["history"]=[row for row in result["workspace"]["history"] if row["revision_id"]!=str(uuid.uuid5(uuid.uuid5(ident,"csv-command:"+proposal["operation_id"]),"revision"))]
                    raise psycopg.Rollback()
            except AccountStoreError as error:
                if error.status not in (422,409):
                    raise
                report["batch_errors"].append(dict(code=error.code,detail=error.detail))
                report["status"]="BATCH_REFUSED"
                result=None
        _bounded_report_text(report,prospective=True)
        return report,events,account_id,snapshot,result

    def preview(self,user_id,portfolio_id,proposal,*,connection=None,execution_scope=None):
        ident=_uuid(portfolio_id)
        context=self.store.connect() if connection is None else nullcontext(connection)
        with context as conn,conn.transaction():
            self._owned(conn,user_id,ident)
            self._lock(conn,self.store.schema,ident)
            report,events,account_id,snapshot,result=self._proposal(conn,user_id,ident,proposal,execution_scope=execution_scope)
            return dict(schema_version="finweb.cp7/1",portfolio_id=str(ident),proposal_digest=_digest(proposal),
                preview_receipt=self._receipt(user_id,ident,proposal),report=report,financial_preview=result)

    def _insert_report(self,conn,report):
        text=_bounded_report_text(report)
        conn.execute("INSERT INTO web_csv_report VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (uuid.UUID(report["report_id"]),uuid.UUID(report["portfolio_id"]),uuid.UUID(report["operation_id"]),report["proposal_digest"],text,
             sha256_hex(text.encode()),None if report["revision_id"] is None else uuid.UUID(report["revision_id"]),report["status"],report["created_at"]))

    def commit(self,user_id,portfolio_id,proposal,receipt,*,connection=None,execution_scope=None):
        ident=_uuid(portfolio_id)
        context=self.store.connect() if connection is None else nullcontext(connection)
        with context as conn,conn.transaction():
            self._owned(conn,user_id,ident)
            self._lock(conn,self.store.schema,ident)
            prior=conn.execute("SELECT report_id,proposal_sha256 FROM web_csv_report WHERE portfolio_id=%s AND operation_id=%s",(ident,uuid.UUID(proposal["operation_id"]))).fetchone()
            if prior:
                if prior[1]!=_digest(proposal):
                    raise AccountStoreError(409,"IDEMPOTENCY_CONFLICT","This import operation already names different source or interpretation")
                report=self._read(conn,user_id,ident,str(prior[0]))
                result=None if report["revision_id"] is None else dict(workspace=self.workspace.workspace(user_id,str(ident),revision_id=report["revision_id"],connection=conn),
                    snapshot=self.workspace.read(user_id,str(ident),revision_id=report["revision_id"],connection=conn).snapshot())
                return dict(schema_version="finweb.cp7/1",portfolio_id=str(ident),report=report,workspace_result=result)
            if conn.execute("SELECT count(*) FROM web_csv_report WHERE portfolio_id=%s",(ident,)).fetchone()[0]>=1000:
                raise AccountStoreError(429,"CSV_REPORT_CAPACITY","This portfolio already has1000 immutable import reports; no financial data was written")
            if not hmac.compare_digest(receipt,self._receipt(user_id,ident,proposal)):
                raise AccountStoreError(409,"CSV_PREVIEW_REQUIRED","A matching preview from this server process is required; re-preview after restart or edits")
            report,events,account_id,snapshot,preview=self._proposal(conn,user_id,ident,proposal,execution_scope=execution_scope)
            conflict=next((error["code"] for row in report["rows"] for error in row["errors"] if error["code"]=="SOURCE_KEY_CONFLICT"),None)
            conflict=conflict or next((error["code"] for error in report["batch_errors"] if error["code"]=="SOURCE_SNAPSHOT_CONFLICT"),None)
            if conflict:
                raise AccountStoreError(409,conflict,"The already recorded source identity has different financial content; use an explicit correction instead")
            result=None
            claims=[]
            if preview is not None:
                result=self._apply(conn,user_id,ident,proposal,report,events,account_id,execution_scope=execution_scope)
                report.update(status="COMMITTED",revision_id=result["workspace"]["revision_id"])
                report["counts"]["imported"]=len(events)
                for row,event,fingerprint in events:
                    claims.append((row["source_key"],ident,canonical_json(row["source_identity"]),fingerprint,"EVENT",uuid.UUID(report["report_id"]),row["row_number"],event.account_id,event.event_id))
                if proposal["kind"]=="HOLDINGS":
                    key,identity,fingerprint,prior_snapshot=snapshot
                    claims.append((key,ident,canonical_json(identity),fingerprint,"SNAPSHOT",uuid.UUID(report["report_id"]),0,account_id,None))
            else:
                report["status"]="ALREADY_IMPORTED" if not report["batch_errors"] and not report["counts"]["quarantined"] and report["counts"]["already_imported"] else "REPORT_ONLY"
                for row in report["rows"]:
                    if row["disposition"]!="ALREADY_IMPORTED":
                        row["event_id"]=None
            report.update(persisted=True,created_at=self.store.clock())
            self._insert_report(conn,report)
            for claim in claims:
                conn.execute("INSERT INTO web_csv_source_key VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",claim)
            return dict(schema_version="finweb.cp7/1",portfolio_id=str(ident),report=report,workspace_result=result)

    def _read(self,conn,user_id,ident,report_id,*,_verify_origins=True):
        self._owned(conn,user_id,ident)
        report_uuid=_uuid(report_id)
        stored=conn.execute("SELECT proposal_sha256,report_json,report_sha256,revision_id,status,created_at,operation_id "
            "FROM web_csv_report WHERE portfolio_id=%s AND report_id=%s",(ident,report_uuid)).fetchone()
        if stored is None:
            not_found()
        try:
            origins={}
            report=json.loads(stored[1])
            if not isinstance(report,dict) or set(report)!=REPORT_FIELDS or sha256_hex(stored[1].encode())!=stored[2] or canonical_json(report)!=stored[1]:
                raise ValueError("report shape/checksum")
            proposal=report["proposal"]
            validate_proposal(proposal)
            if not isinstance(proposal,dict) or set(proposal)!=PROPOSAL_FIELDS or proposal["synthetic_acknowledged"] is not True:
                raise ValueError("explicit proposal fields")
            if (report["schema"]!="finweb.csv_import/1" or report["persisted"] is not True or report["portfolio_id"]!=str(ident)
                or report["report_id"]!=str(report_uuid) or report["operation_id"]!=str(stored[6]) or proposal["operation_id"]!=report["operation_id"]
                or report["expected_revision_id"]!=proposal["expected_revision_id"] or report["proposal_digest"]!=stored[0] or _digest(proposal)!=stored[0]
                or report["revision_id"]!=(None if stored[3] is None else str(stored[3])) or report["status"]!=stored[4]
                or report["created_at"]!=json.loads(canonical_json(stored[5])) or report["parser"]!=dict(version=VERSION,dialect="stdlib-explicit-v1")):
                raise ValueError("report identity/provenance")
            if set(proposal["format"])!={"delimiter","date_format","decimal_separator","thousands_separator"}:
                raise ValueError("explicit format")
            parsed=parse_source(proposal["file_base64"],proposal["filename"],proposal["format"]["delimiter"])
            if report["file"]!=dict(filename=proposal["filename"],sha256=parsed["file_sha256"],byte_count=parsed["byte_count"],bom=parsed["bom"]):
                raise ValueError("source bytes")
            if not isinstance(report["rows"],list) or len(report["rows"])!=len(parsed["rows"]) or not isinstance(report["batch_errors"],list):
                raise ValueError("row inventory")
            if any(not isinstance(error,dict) or set(error)!={"code","detail"} for error in report["batch_errors"]):
                raise ValueError("batch issue fields")
            accounts=[dict(account_id=str(row[0]),name=row[1]) for row in conn.execute("SELECT account_id,name FROM account WHERE portfolio_id=%s",(ident,)).fetchall()]
            owned_accounts={uuid.UUID(row["account_id"]) for row in accounts}
            listings=[dict(row,mic=self.world.raw["mic"]) for row in self.world.capabilities()["listings"]]
            financial_fingerprints=[]
            for correction in proposal["corrections"]:
                if set(correction)!={"row_number","fields","reason"} or not correction["reason"].strip():
                    raise ValueError("explicit correction confirmation")
            for classification in proposal["classifications"]:
                if set(classification)!={"row_number","classification","reason"} or not classification["reason"].strip():
                    raise ValueError("explicit exclusion confirmation")
            corrections={row["row_number"]:row for row in proposal["corrections"]}
            classes={row["row_number"]:row for row in proposal["classifications"]}
            for row,original in zip(report["rows"],parsed["rows"]):
                if not isinstance(row,dict) or set(row)!=ROW_FIELDS or any(row[key]!=value for key,value in original.items()):
                    raise ValueError("raw record lineage")
                fields=dict(proposal["constants"])
                fields.update({name:original["cells"][index] for name,index in proposal["mapping"].items() if index<len(original["cells"])})
                fields.update(corrections.get(original["row_number"],{}).get("fields",{}))
                classification=classes.get(original["row_number"],{"classification":"ECONOMIC","reason":""})
                if row["fields"]!=fields or row["classification"]!=classification["classification"] or row["reason"]!=classification["reason"]:
                    raise ValueError("mapping/correction/classification")
                if not isinstance(row["errors"],list) or any(not isinstance(error,dict) or set(error)!={"code","field","detail"} for error in row["errors"]):
                    raise ValueError("explicit row issues")
                if row["disposition"] not in ("READY","QUARANTINED","EXCLUDED","ALREADY_IMPORTED"):
                    raise ValueError("row disposition")
                if (row["classification"]!="ECONOMIC")!=(row["disposition"]=="EXCLUDED") or bool(row["errors"])!=(row["disposition"]=="QUARANTINED"):
                    raise ValueError("row classification consistency")
                if row["event"] is not None:
                    if not isinstance(row["event"],dict) or normalized_event(fields,proposal,accounts,listings,row["event"]["account_id"])!=row["event"]:
                        raise ValueError("recorded interpretation differs from explicit source fields")
                elif row["disposition"] in ("READY","ALREADY_IMPORTED") or row["source_identity"] is not None or row["source_key"] is not None:
                    raise ValueError("missing recorded economic interpretation")
                if (row["disposition"]=="ALREADY_IMPORTED")!=(row["existing_event_id"] is not None) or row["existing_event_id"] is not None and row["existing_event_id"]!=row["event_id"]:
                    raise ValueError("explicit prior event linkage")
                if report["status"]!="COMMITTED" and row["disposition"]!="ALREADY_IMPORTED" and row["event_id"] is not None:
                    raise ValueError("uncommitted report cannot assert a stored event")
                if row["source_key"] is not None and _digest(row["source_identity"])!=row["source_key"]:
                    raise ValueError("structured source identity")
                if row["source_identity"] is not None:
                    expected_identity=["EVENT",str(ident),proposal["source_namespace"],proposal["kind"],
                        proposal["source_account_key"] if proposal["kind"]=="HOLDINGS" else row["event"]["account_id"],
                        proposal["snapshot_key"] if proposal["kind"]=="HOLDINGS" else "",fields["source_row_key"]]
                    if row["source_identity"]!=expected_identity:
                        raise ValueError("explicit source tuple from mapped fields")
                committed=(report["status"]=="COMMITTED" and row["disposition"]=="READY") or row["disposition"]=="ALREADY_IMPORTED"
                if committed:
                    source=self._source(conn,ident,row["source_key"])
                    if source is None or source[0]!=canonical_json(row["source_identity"]) or source[2]!="EVENT" or str(source[6])!=row["event_id"]:
                        raise ValueError("stored financial source linkage")
                    if _verify_origins and row["disposition"]=="ALREADY_IMPORTED":
                        self._verify_origin(conn,user_id,ident,row["source_key"],source,origins)
                    event=ledger_store.get_event(conn,source[6])
                    if normalized_event(fields,proposal,accounts,listings,str(source[5]))!=row["event"]:
                        raise ValueError("source fields to economic interpretation")
                    expected=self.workspace._event(row["event"],uuid.UUID(proposal["operation_id"]),row["row_number"],owned_accounts)
                    expected=replace(expected,event_id=uuid.UUID(row["event_id"]),source_reference="CP7 CSV source:"+row["source_key"])
                    if event is None or not event.event.has_same_content(expected) or _facts(event.event,proposal["kind"]=="HOLDINGS")!=source[1]:
                        raise ValueError("stored canonical event mapping")
                    if report["status"]=="COMMITTED" and row["disposition"]=="READY" and (str(source[3])!=report["report_id"] or source[4]!=row["row_number"]):
                        raise ValueError("committed report ownership")
                    financial_fingerprints.append((row["source_key"],source[1]))
            expected_counts=dict(total=len(report["rows"]),economic=sum(row["classification"]=="ECONOMIC" for row in report["rows"]),
                ready=sum(row["disposition"]=="READY" for row in report["rows"]),quarantined=sum(row["disposition"]=="QUARANTINED" for row in report["rows"]),
                excluded=sum(row["disposition"]=="EXCLUDED" for row in report["rows"]),already_imported=sum(row["disposition"]=="ALREADY_IMPORTED" for row in report["rows"]),
                imported=sum(row["disposition"]=="READY" for row in report["rows"]) if report["status"]=="COMMITTED" else 0)
            if report["counts"]!=expected_counts or set(report["counts"])!=COUNT_FIELDS or any(type(value)is not int or value<0 for value in report["counts"].values()):
                raise ValueError("report counts")
            if (report["status"]=="COMMITTED")!=(report["revision_id"] is not None) or report["status"]=="COMMITTED" and (report["counts"]["quarantined"] or report["batch_errors"]):
                raise ValueError("whole financial batch state")
            if report["status"]=="COMMITTED":
                revision=self.workspace._record(conn,user_id,ident,report["revision_id"])
                self.workspace._item(conn,ident,revision)
                link=conn.execute("SELECT parent_revision_id,operation_id FROM web_portfolio_revision WHERE portfolio_id=%s AND revision_id=%s",(ident,uuid.UUID(report["revision_id"]))).fetchone()
                command_id=uuid.uuid5(ident,"csv-command:"+proposal["operation_id"])
                if (link is None or str(link[0])!=proposal["expected_revision_id"] or link[1]!=command_id or report["revision_id"]!=str(uuid.uuid5(command_id,"revision"))
                    or str(revision["as_of"])!=proposal["as_of"] or report["counts"]["imported"]<1 or report["counts"]["imported"]>32):
                    raise ValueError("committed import revision provenance")
                pinned={str(entry.event.event_id) for entry in self.workspace._events(conn,ident,revision["ledger_version"])}
                if any(row["event_id"] not in pinned for row in report["rows"] if row["disposition"] in ("READY","ALREADY_IMPORTED")):
                    raise ValueError("import event outside committed revision pin")
            if report["status"]=="ALREADY_IMPORTED" and (report["counts"]["ready"] or report["counts"]["quarantined"] or report["batch_errors"] or not report["counts"]["already_imported"]):
                raise ValueError("already imported source state")
            if proposal["kind"]=="HOLDINGS" and report["status"] in ("COMMITTED","ALREADY_IMPORTED"):
                identity=["SNAPSHOT",str(ident),proposal["source_namespace"],proposal["source_account_key"],proposal["snapshot_key"]]
                source=self._source(conn,ident,_digest(identity))
                if source is None or source[0]!=canonical_json(identity) or source[1]!=_digest(sorted(financial_fingerprints)) or source[2]!="SNAPSHOT" or source[4]!=0:
                    raise ValueError("complete holdings snapshot source binding")
                if report["status"]=="COMMITTED" and str(source[3])!=report["report_id"]:
                    raise ValueError("snapshot original report provenance")
                if _verify_origins and report["status"]=="ALREADY_IMPORTED":
                    self._verify_origin(conn,user_id,ident,_digest(identity),source,origins)
            return report
        except AccountStoreError:
            raise AccountStoreError(503,"IMPORT_REPORT_DIFFERS","The saved import's financial revision or source provenance is unavailable") from None
        except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError,ledger_store.LedgerStoreError):
            raise AccountStoreError(503,"IMPORT_REPORT_DIFFERS","Saved import source,explicit provenance or financial mapping does not reproduce exactly") from None

    def get(self,user_id,portfolio_id,report_id,*,connection=None):
        ident=_uuid(portfolio_id)
        context=self.store.connect() if connection is None else nullcontext(connection)
        with context as conn:
            return dict(schema_version="finweb.cp7/1",portfolio_id=str(ident),report=self._read(conn,user_id,ident,report_id))

    def list(self,user_id,portfolio_id,cursor=None,*,connection=None):
        ident=_uuid(portfolio_id)
        context=self.store.connect() if connection is None else nullcontext(connection)
        with context as conn:
            self._owned(conn,user_id,ident)
            params=[ident]
            clause=""
            if cursor is not None:
                try:
                    token,signature=cursor.split(".")
                    if not hmac.compare_digest(signature,hmac.new(self.key,token.encode(),hashlib.sha256).hexdigest()):
                        raise ValueError("cursor signature")
                    raw=base64.b64decode(token+"="*((-len(token))%4),altchars=b"-_",validate=True)
                    bound=json.loads(raw)
                    if not isinstance(bound,list) or len(bound)!=4 or bound[:2]!=[str(user_id),str(ident)]:
                        raise ValueError("cursor owner")
                    import datetime as dt
                    timestamp=dt.datetime.fromisoformat(bound[2].replace("Z","+00:00"))
                    report_uuid=uuid.UUID(bound[3])
                    clause=" AND (created_at,report_id)<(%s,%s)"
                    params.extend((timestamp,report_uuid))
                except (ValueError,TypeError,KeyError,AttributeError):
                    raise AccountStoreError(422,"CSV_REPORT_CURSOR","This report cursor is invalid for the current account/portfolio or server; refresh the list") from None
            ids=conn.execute("SELECT report_id,created_at FROM web_csv_report WHERE portfolio_id=%s"+clause+" ORDER BY created_at DESC,report_id DESC LIMIT 33",params).fetchall()
            more=len(ids)>32
            ids=ids[:32]
            reports=[self._read(conn,user_id,ident,str(row[0])) for row in ids]
            next_cursor=None
            if more:
                last=ids[-1]
                token=base64.urlsafe_b64encode(canonical_json([str(user_id),str(ident),json.loads(canonical_json(last[1])),str(last[0])]).encode()).decode().rstrip("=")
                next_cursor=token+"."+hmac.new(self.key,token.encode(),hashlib.sha256).hexdigest()
            return dict(schema_version="finweb.cp7/1",portfolio_id=str(ident),reports=[dict(report_id=report["report_id"],status=report["status"],created_at=report["created_at"],
                kind=report["proposal"]["kind"],file_sha256=report["file"]["sha256"],counts=report["counts"],revision_id=report["revision_id"]) for report in reports],next_cursor=next_cursor)

    def export_report(self,user_id,portfolio_id,report_id,format,*,connection=None):
        report=self.get(user_id,portfolio_id,report_id,connection=connection)["report"]
        if format=="json":
            return canonical_json(report),"application/json"
        rows=[dict(row_number=row["row_number"],physical_start=row["physical_start"],physical_end=row["physical_end"],classification=row["classification"],
            reason=row["reason"],disposition=row["disposition"],source_key=row["source_key"],event_id=row["event_id"],cells=canonical_json(row["cells"]),
            fields=canonical_json(row["fields"]),errors=canonical_json(row["errors"]),
            corrections=canonical_json([change for change in report["proposal"]["corrections"] if change["row_number"]==row["row_number"]]),
            text_protection="apostrophe-prefixed untrusted text; authoritative lossless JSON available") for row in report["rows"]]
        return protected_csv(rows),"text/csv; charset=utf-8"

    def export_portfolio(self,user_id,portfolio_id,revision_id,kind,format,*,connection=None):
        ident=_uuid(portfolio_id)
        context=self.store.connect() if connection is None else nullcontext(connection)
        with context as conn:
            record=self.workspace._record(conn,user_id,ident,revision_id)
            item,events=self.workspace._item(conn,ident,record)
            workspace=self.workspace._workspace(conn,ident,record,item,events,catalog_metadata=False)
            csv_sources=[]
            verified={}
            for event in workspace["ledger"]["events"]:
                reference=event["source_reference"]
                if reference and reference.startswith("CP7 CSV source:"):
                    key=reference.removeprefix("CP7 CSV source:")
                    source=self._source(conn,ident,key)
                    if source is None or str(source[6])!=event["event_id"]:
                        raise AccountStoreError(503,"IMPORT_REPORT_DIFFERS","A CSV ledger fact has no matching owned raw-row provenance")
                    origin=self._verify_origin(conn,user_id,ident,key,source,verified)
                    csv_sources.append(dict(event_id=event["event_id"],source_key=key,report_id=str(source[3]),row_number=source[4],file_sha256=origin["file"]["sha256"],source_identity=json.loads(source[0])))
            lot_witness=reconstruct_fifo(events,record["as_of"],record["ledger_version"]).to_canonical_dict()
        payload=dict(schema="finweb.portfolio_export/1",portfolio_id=str(ident),revision_id=str(record["revision_id"]),kind=kind,
            as_of=record["as_of"],ledger_version=record["ledger_version"],synthetic=True,events=workspace["ledger"]["events"],
            accounts=workspace["accounts"],
            csv_sources=csv_sources,lot_witness=lot_witness,
            native_state=workspace["ledger"]["current_state"],policies=workspace["policies"],benchmark=workspace["benchmark"],
            limitations=["Native source facts and states only; no missing market data is fabricated", "CSV protects untrusted text with apostrophes; JSON preserves original content",
                "Nondecimal/unrepresentable replay quantities remain unavailable rather than rounded; retain original event/split facts"])
        if format=="json":
            return canonical_json(payload),"application/json"
        rows=[]
        if kind=="transactions":
            rows=[{key:canonical_json(value) if isinstance(value,(dict,list)) else value for key,value in event.items()} for event in payload["events"]]
        else:
            for account in payload["native_state"]["accounts"]:
                for position in account["positions"]:
                    rows.append(dict(record_type="POSITION",account_id=account["account_id"],listing_id=position["listing_id"],quantity=position["quantity"]["value"],
                        state=position["quantity"]["state"],reason=position["quantity"]["reason"],cost_basis=canonical_json(position["cost_basis"]),currency=None,amount=None))
                for cash in account["cash"]:
                    rows.append(dict(record_type="CASH",account_id=account["account_id"],listing_id=None,quantity=None,state="AVAILABLE",reason=None,cost_basis=None,currency=cash["currency"],amount=cash["amount"]))
                for currency in account["unrepresentable_cash"]:
                    rows.append(dict(record_type="CASH",account_id=account["account_id"],listing_id=None,quantity=None,state="INSUFFICIENT_DATA",reason="VALUE_NOT_REPRESENTABLE",cost_basis=None,currency=currency,amount=None))
        for row in rows:
            row["account_name"]=next(account["name"] for account in workspace["accounts"] if account["account_id"]==row["account_id"])
            row["account_event_ids"]=canonical_json([event["event_id"] for event in payload["events"] if event["account_id"]==row["account_id"]])
            if kind=="transactions":
                direct=next((source for source in csv_sources if source["event_id"]==row["event_id"]),None)
                row["source_report_id"]=None if direct is None else direct["report_id"]
                row["source_row_number"]=None if direct is None else direct["row_number"]
                row["source_file_sha256"]=None if direct is None else direct["file_sha256"]
                row["source_relation"]="DIRECT_CSV_ROW" if direct is not None else "B2_CORRECTION_OR_REVERSAL" if row["corrects_event_id"] or row["reverses_event_id"] else "OTHER_CANONICAL_FACT"
            elif row["record_type"]=="POSITION":
                book=next((book for book in lot_witness["books"] if book["account_id"]==row["account_id"] and book["listing_id"]==row["listing_id"]),None)
                row["quantity_exact"]=None if book is None else book["quantity"]
                row["lot_method"]=lot_witness["lot_method"]
                row["lot_causes"]=canonical_json([] if book is None else book["causes"])
                row["fifo_lots"]=canonical_json([] if book is None else book["lots"])
            row.update(revision_id=str(record["revision_id"]),as_of=str(record["as_of"]),synthetic=True,text_protection="apostrophe-protected text; lossless JSON/original ledger available")
        return protected_csv(rows),"text/csv; charset=utf-8"


def protected_csv(rows):
    fields=list(dict.fromkeys(key for row in rows for key in row)) or ["no_records"]
    stream=io.StringIO(newline="")
    writer=csv.writer(stream,lineterminator="\r\n",quoting=csv.QUOTE_ALL)
    writer.writerow(fields)
    for row in rows:
        values=[]
        for key in fields:
            value=row.get(key)
            text="" if value is None else str(value)
            if text and (text.lstrip().startswith(("=","+","-","@")) or any(ord(char)<32 for char in text)):
                # Protect all user text. Canonical signed numeric fields retain native numbers.
                numeric=key in ("amount","quantity","cost_basis","ledger_seq") and re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?",text)
                if not numeric:
                    text="'"+text
            values.append(text)
        writer.writerow(values)
    return stream.getvalue()
