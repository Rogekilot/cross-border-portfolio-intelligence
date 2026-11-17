-- Candidate-only report operations. Original F2 objects are not replaced.
CREATE TABLE __CR_SCHEMA__.gh_csv_report_operation (
 owner_id uuid NOT NULL, operation_id uuid NOT NULL, root_id uuid NOT NULL REFERENCES __CR_SCHEMA__.gw_root,
 context_id text NOT NULL REFERENCES __CR_SCHEMA__.gw_snapshot, commit_generation bigint NOT NULL CHECK(commit_generation>0),
 command_sha256 text NOT NULL, request_sha256 text NOT NULL, proposal_sha256 text NOT NULL, preview_receipt_sha256 text NOT NULL,
 base_revision_id uuid NOT NULL, base_operation_id uuid NOT NULL, base_ledger_pin bigint NOT NULL,
 report_id uuid NOT NULL, response bytea NOT NULL CHECK(octet_length(response) BETWEEN 2 AND 2000000),
 response_sha256 text NOT NULL CHECK(response_sha256=encode(sha256(response),'hex')),
 envelope bytea NOT NULL CHECK(octet_length(envelope) BETWEEN 2 AND 65536),
 envelope_sha256 text NOT NULL CHECK(envelope_sha256=encode(sha256(envelope),'hex')),
 committed_at timestamptz NOT NULL, backend_pid integer NOT NULL,xid text NOT NULL,
 PRIMARY KEY(owner_id,operation_id), UNIQUE(root_id,report_id),
 FOREIGN KEY(backend_pid,xid) REFERENCES __CR_SCHEMA__.gw_lease(backend_pid,xid),
 CHECK(command_sha256 ~ '^[0-9a-f]{64}$' AND request_sha256 ~ '^[0-9a-f]{64}$'
 AND proposal_sha256 ~ '^[0-9a-f]{64}$' AND preview_receipt_sha256 ~ '^[0-9a-f]{64}$')
);
CREATE TRIGGER gh_csv_report_immutable BEFORE UPDATE OR DELETE ON __CR_SCHEMA__.gh_csv_report_operation
 FOR EACH ROW EXECUTE FUNCTION __CR_SCHEMA__.gw_no_mutation();
CREATE TRIGGER gh_csv_report_no_truncate BEFORE TRUNCATE ON __CR_SCHEMA__.gh_csv_report_operation
 FOR EACH STATEMENT EXECUTE FUNCTION __CR_SCHEMA__.gw_no_mutation();

CREATE FUNCTION __CR_SCHEMA__.gh_csv_report_scope(p text,writing boolean) RETURNS __CR_SCHEMA__.gw_lease
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__CR_SCHEMA__,pg_temp AS $$
DECLARE l __CR_SCHEMA__.gw_lease%ROWTYPE; h __CR_SCHEMA__.gw_head%ROWTYPE;
BEGIN
 SELECT * INTO l FROM __CR_SCHEMA__.gw_lease WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text;
 IF l.owner_id IS NULL OR l.phase IS DISTINCT FROM 'READONLY' OR l.purpose IS DISTINCT FROM p
 OR p NOT IN ('ARCHIVE_READ','ARCHIVE_EXPORT') THEN RAISE EXCEPTION 'F3_CSV_REPORT_SCOPE'; END IF;
 SELECT * INTO h FROM __CR_SCHEMA__.gw_head WHERE context_id=l.context_id;
 IF h.generation IS DISTINCT FROM l.generation THEN RAISE EXCEPTION 'F2_GENERATION_DIFFERS'; END IF;
 IF h.expiry IS DISTINCT FROM 'NONE' THEN RAISE EXCEPTION 'F2_EXPIRY_HOLD'; END IF;
 IF (SELECT mode FROM __CR_SCHEMA__.gw_mode WHERE singleton) IS DISTINCT FROM 'FICTIONAL_ONLY' THEN RAISE EXCEPTION 'F2_MODE_HOLD'; END IF;
 IF NOT COALESCE((h.rights->>'ARCHIVE_READ')::boolean,false) OR NOT COALESCE((h.rights->>p)::boolean,false)
 OR writing AND NOT COALESCE((h.rights->>'EXECUTE_CREATE')::boolean,false) THEN RAISE EXCEPTION 'F2_RIGHT_REFUSED'; END IF;
 IF NOT EXISTS(SELECT 1 FROM __CR_SCHEMA__.gw_root WHERE root_id=l.root_id AND owner_id=l.owner_id AND context_id=l.context_id)
 THEN RAISE EXCEPTION 'F2_NOT_FOUND'; END IF;
 RETURN l;
END $$;

CREATE FUNCTION __CR_SCHEMA__.gh_csv_report_precheck(o uuid,op uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__CR_SCHEMA__,pg_temp AS $$
BEGIN
 IF o IS NULL OR op IS NULL THEN RAISE EXCEPTION 'F3_SHAPE'; END IF;
 IF EXISTS(SELECT 1 FROM __CR_SCHEMA__.gh_csv_report_operation WHERE owner_id=o AND operation_id=op)
 THEN RAISE EXCEPTION 'F3_CSV_REPORT_IDEMPOTENCY_CONFLICT'; END IF;
END $$;

CREATE FUNCTION __CR_SCHEMA__.gh_csv_report_read(o uuid,r uuid,k text,op uuid,rep uuid,p text)
RETURNS SETOF __CR_SCHEMA__.gh_csv_report_operation
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__CR_SCHEMA__,pg_temp AS $$
DECLARE l __CR_SCHEMA__.gw_lease%ROWTYPE; v __CR_SCHEMA__.gh_csv_report_operation%ROWTYPE;
BEGIN
 l:=__CR_SCHEMA__.gh_csv_report_scope(p,false);
 IF o IS DISTINCT FROM l.owner_id OR r IS DISTINCT FROM l.root_id OR k IS DISTINCT FROM l.context_id
 OR num_nonnulls(op,rep)<>1 THEN RAISE EXCEPTION 'F3_CSV_REPORT_SCOPE'; END IF;
 SELECT * INTO v FROM __CR_SCHEMA__.gh_csv_report_operation WHERE owner_id=o AND root_id=r AND context_id=k
 AND (op IS NULL OR operation_id=op) AND (rep IS NULL OR report_id=rep);
 IF NOT FOUND THEN RETURN; END IF;
 IF v.response_sha256 IS DISTINCT FROM encode(sha256(v.response),'hex') OR v.envelope_sha256 IS DISTINCT FROM encode(sha256(v.envelope),'hex')
 THEN RAISE EXCEPTION 'F3_CSV_REPORT_ARCHIVE_DIFFERS'; END IF;
 RETURN NEXT v;
END $$;

CREATE FUNCTION __CR_SCHEMA__.gh_csv_report_list(o uuid,r uuid,k text) RETURNS SETOF jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__CR_SCHEMA__,pg_temp AS $$
DECLARE l __CR_SCHEMA__.gw_lease%ROWTYPE; v __CR_SCHEMA__.gh_csv_report_operation%ROWTYPE; b jsonb;
BEGIN
 l:=__CR_SCHEMA__.gh_csv_report_scope('ARCHIVE_READ',false);
 IF o IS DISTINCT FROM l.owner_id OR r IS DISTINCT FROM l.root_id OR k IS DISTINCT FROM l.context_id THEN RAISE EXCEPTION 'F3_CSV_REPORT_SCOPE'; END IF;
 IF (SELECT count(*) FROM __CR_SCHEMA__.gh_csv_report_operation WHERE root_id=r)>1000 THEN RAISE EXCEPTION 'F3_CSV_REPORT_CAPACITY'; END IF;
 FOR v IN SELECT * FROM __CR_SCHEMA__.gh_csv_report_operation WHERE owner_id=o AND root_id=r AND context_id=k LOOP
  IF v.response_sha256 IS DISTINCT FROM encode(sha256(v.response),'hex') OR v.envelope_sha256 IS DISTINCT FROM encode(sha256(v.envelope),'hex') THEN RAISE EXCEPTION 'F3_CSV_REPORT_ARCHIVE_DIFFERS'; END IF;
  b:=convert_from(v.response,'UTF8')::jsonb->'report';
  RETURN NEXT jsonb_build_object('report_id',v.report_id,'operation_id',v.operation_id,'status',b->>'status','created_at',b->>'created_at',
    'kind','TRANSACTIONS','file_sha256',b->'file'->>'sha256','counts',b->'counts','revision_id',NULL,'operation_kind','CSV_REPORT_ONLY');
 END LOOP;
END $$;

CREATE FUNCTION __CR_SCHEMA__.gh_csv_report_commit(command bytea,response bytea,envelope bytea)
RETURNS SETOF __CR_SCHEMA__.gh_csv_report_operation
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__CR_SCHEMA__,pg_temp AS $$
DECLARE l __CR_SCHEMA__.gw_lease%ROWTYPE; prior __CR_SCHEMA__.gh_csv_report_operation%ROWTYPE;
 c jsonb; e jsonb; v jsonb; b jsonb; rw jsonb; cnt jsonb; n integer; pin bigint; base uuid; src __CR_SCHEMA__.web_csv_source_key%ROWTYPE;
BEGIN
 l:=__CR_SCHEMA__.gh_csv_report_scope('ARCHIVE_READ',true);
 IF command IS NULL OR octet_length(command) NOT BETWEEN 2 AND 4096 OR (response IS NULL)<>(envelope IS NULL) THEN RAISE EXCEPTION 'F3_SHAPE'; END IF;
 c:=convert_from(command,'UTF8')::jsonb;
 IF NOT __CR_SCHEMA__.gw_keys(c,ARRAY['schema','owner_id','root_id','context_id','kind','request_sha256'])
 OR command IS DISTINCT FROM convert_to(__CR_SCHEMA__.gw_json(c),'UTF8') OR encode(sha256(command),'hex') IS DISTINCT FROM l.command_sha256
 OR c->>'schema' IS DISTINCT FROM 'finweb.f3.csv-report-command/1' OR c->>'kind' IS DISTINCT FROM 'CSV_REPORT_ONLY'
 OR c->>'owner_id' IS DISTINCT FROM l.owner_id::text OR c->>'root_id' IS DISTINCT FROM l.root_id::text
 OR c->>'context_id' IS DISTINCT FROM l.context_id OR c->>'request_sha256' !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'F3_CSV_REPORT_BINDING_DIFFERS'; END IF;
 IF EXISTS(SELECT 1 FROM __CR_SCHEMA__.gw_operation WHERE owner_id=l.owner_id AND operation_id=l.operation_id)
 THEN RAISE EXCEPTION 'F3_CSV_REPORT_IDEMPOTENCY_CONFLICT'; END IF;
 SELECT * INTO prior FROM __CR_SCHEMA__.gh_csv_report_operation WHERE owner_id=l.owner_id AND operation_id=l.operation_id;
 IF FOUND THEN
  IF prior.command_sha256 IS DISTINCT FROM l.command_sha256 OR prior.root_id IS DISTINCT FROM l.root_id OR prior.context_id IS DISTINCT FROM l.context_id
  THEN RAISE EXCEPTION 'F3_CSV_REPORT_IDEMPOTENCY_CONFLICT'; END IF;
  RETURN NEXT prior; RETURN;
 END IF;
 IF response IS NULL THEN RETURN; END IF;
 IF octet_length(response) NOT BETWEEN 2 AND 2000000 OR octet_length(envelope) NOT BETWEEN 2 AND 65536 THEN RAISE EXCEPTION 'F3_SHAPE'; END IF;
 v:=convert_from(response,'UTF8')::jsonb; e:=convert_from(envelope,'UTF8')::jsonb; b:=v->'report'; cnt:=b->'counts';
 IF NOT __CR_SCHEMA__.gw_keys(v,ARRAY['report','workspace_result']) OR v->'workspace_result' IS DISTINCT FROM 'null'::jsonb
 OR response IS DISTINCT FROM convert_to(__CR_SCHEMA__.gw_json(v),'UTF8') OR envelope IS DISTINCT FROM convert_to(__CR_SCHEMA__.gw_json(e),'UTF8')
 OR NOT __CR_SCHEMA__.gw_keys(e,ARRAY['schema','profile','synthetic','operation_kind','owner_id','portfolio_id','operation_id','report_id','context_id','commit_generation','base_revision_id','base_operation_id','base_ledger_pin','request_sha256','proposal_sha256','preview_receipt_sha256','response_sha256','report_status','created_at'])
 OR e->>'schema' IS DISTINCT FROM 'finweb.csv_report_envelope/1' OR e->>'profile' IS DISTINCT FROM 'F3_FICTIONAL_CP5' OR e->'synthetic' IS DISTINCT FROM 'true'::jsonb
 OR e->>'operation_kind' IS DISTINCT FROM 'CSV_REPORT_ONLY' OR e->>'owner_id' IS DISTINCT FROM l.owner_id::text
 OR e->>'portfolio_id' IS DISTINCT FROM l.root_id::text OR e->>'operation_id' IS DISTINCT FROM l.operation_id::text
 OR e->>'context_id' IS DISTINCT FROM l.context_id OR e->'commit_generation' IS DISTINCT FROM to_jsonb(l.generation)
 OR e->>'request_sha256' IS DISTINCT FROM c->>'request_sha256' OR e->>'response_sha256' IS DISTINCT FROM encode(sha256(response),'hex')
 OR e->>'proposal_sha256' IS DISTINCT FROM encode(sha256(convert_to(__CR_SCHEMA__.gw_json(b->'proposal'),'UTF8')),'hex')
 OR e->>'preview_receipt_sha256' !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'F3_CSV_REPORT_BINDING_DIFFERS'; END IF;
 IF NOT __CR_SCHEMA__.gw_keys(b,ARRAY['schema','report_id','portfolio_id','operation_id','expected_revision_id','proposal_digest','persisted','status','file','proposal','parser','rows','counts','batch_errors','revision_id','created_at'])
 OR b->>'schema' IS DISTINCT FROM 'finweb.csv_import/1' OR b->'persisted' IS DISTINCT FROM 'true'::jsonb
 OR b->>'portfolio_id' IS DISTINCT FROM l.root_id::text OR b->>'operation_id' IS DISTINCT FROM l.operation_id::text
 OR b->>'report_id' IS DISTINCT FROM e->>'report_id' OR b->>'expected_revision_id' IS DISTINCT FROM e->>'base_revision_id'
 OR b->'revision_id' IS DISTINCT FROM 'null'::jsonb OR b->'proposal'->>'kind' IS DISTINCT FROM 'TRANSACTIONS'
 OR b->'proposal'->>'operation_id' IS DISTINCT FROM l.operation_id::text OR b->'proposal'->>'expected_revision_id' IS DISTINCT FROM e->>'base_revision_id'
 OR b->'proposal'->>'as_of' IS DISTINCT FROM '2026-01-02' OR b->'proposal'->'synthetic_acknowledged' IS DISTINCT FROM 'true'::jsonb
 OR b->>'proposal_digest' IS DISTINCT FROM e->>'proposal_sha256' OR b->>'created_at' IS DISTINCT FROM e->>'created_at'
 OR b->>'status' IS DISTINCT FROM e->>'report_status' OR b->>'status' NOT IN ('ALREADY_IMPORTED','REPORT_ONLY')
 OR cnt->'imported' IS DISTINCT FROM '0'::jsonb OR jsonb_typeof(b->'rows') IS DISTINCT FROM 'array'
 OR jsonb_array_length(b->'rows') NOT BETWEEN 0 AND 128 THEN RAISE EXCEPTION 'F3_CSV_REPORT_BINDING_DIFFERS'; END IF;
 SELECT revision_id,ledger_version INTO base,pin FROM __CR_SCHEMA__.web_portfolio_revision WHERE portfolio_id=l.root_id ORDER BY revision_seq DESC LIMIT 1;
 IF NOT FOUND THEN SELECT portfolio_id,ledger_version INTO base,pin FROM __CR_SCHEMA__.web_saved_sandbox WHERE portfolio_id=l.root_id; END IF;
 IF base IS DISTINCT FROM (e->>'base_revision_id')::uuid OR pin::text IS DISTINCT FROM e->>'base_ledger_pin' THEN RAISE EXCEPTION 'STALE_REVISION'; END IF;
 IF NOT EXISTS(SELECT 1 FROM __CR_SCHEMA__.gw_operation WHERE owner_id=l.owner_id AND root_id=l.root_id AND context_id=l.context_id
   AND operation_id=(e->>'base_operation_id')::uuid AND revision_id=base) THEN RAISE EXCEPTION 'F3_CSV_REPORT_BINDING_DIFFERS'; END IF;
 IF NOT __CR_SCHEMA__.gw_keys(cnt,ARRAY['total','economic','ready','quarantined','excluded','already_imported','imported'])
 OR EXISTS(SELECT 1 FROM jsonb_each(cnt) WHERE jsonb_typeof(value)<>'number' OR value::text !~ '^(0|[1-9][0-9]*)$')
 OR (cnt->>'total')::integer<>jsonb_array_length(b->'rows') OR (cnt->>'total')::integer<>(cnt->>'economic')::integer+(cnt->>'excluded')::integer
 OR (cnt->>'economic')::integer<>(cnt->>'ready')::integer+(cnt->>'quarantined')::integer+(cnt->>'already_imported')::integer
 OR b->'file'->>'sha256' IS DISTINCT FROM encode(sha256(decode(b->'proposal'->>'file_base64','base64')),'hex')
 OR jsonb_typeof(b->'batch_errors') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'F3_CSV_REPORT_BINDING_DIFFERS'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(b->'batch_errors') er WHERE er->>'code' IN ('SOURCE_KEY_CONFLICT','SOURCE_SNAPSHOT_CONFLICT'))
 OR EXISTS(SELECT 1 FROM jsonb_array_elements(b->'rows') rr CROSS JOIN LATERAL jsonb_array_elements(rr->'errors') er WHERE er->>'code' IN ('SOURCE_KEY_CONFLICT','SOURCE_SNAPSHOT_CONFLICT'))
 THEN RAISE EXCEPTION 'F3_CSV_REPORT_SOURCE_DIFFERS'; END IF;
 FOR rw IN SELECT value FROM jsonb_array_elements(b->'rows') LOOP
  IF rw->>'disposition' NOT IN ('ALREADY_IMPORTED','READY','QUARANTINED','EXCLUDED')
  OR rw->>'disposition'<>'ALREADY_IMPORTED' AND rw->'event_id' IS DISTINCT FROM 'null'::jsonb THEN RAISE EXCEPTION 'F3_CSV_REPORT_BINDING_DIFFERS'; END IF;
  IF rw->>'disposition'='ALREADY_IMPORTED' THEN
   SELECT * INTO src FROM __CR_SCHEMA__.web_csv_source_key WHERE portfolio_id=l.root_id AND source_key=rw->>'source_key';
   IF NOT FOUND OR src.source_kind<>'EVENT' OR src.identity_json::jsonb IS DISTINCT FROM rw->'source_identity'
   OR src.source_key IS DISTINCT FROM encode(sha256(convert_to(__CR_SCHEMA__.gw_json(rw->'source_identity'),'UTF8')),'hex')
   OR src.event_id::text IS DISTINCT FROM rw->>'event_id' OR rw->>'existing_event_id' IS DISTINCT FROM rw->>'event_id'
   OR NOT EXISTS(SELECT 1 FROM __CR_SCHEMA__.web_csv_report WHERE portfolio_id=l.root_id AND report_id=src.report_id AND status='COMMITTED')
   OR NOT EXISTS(SELECT 1 FROM __CR_SCHEMA__.ledger_event le JOIN __CR_SCHEMA__.account ac USING(account_id) WHERE ac.portfolio_id=l.root_id AND le.event_id=src.event_id AND le.account_id=src.account_id AND le.ledger_seq<=pin)
   THEN RAISE EXCEPTION 'F3_CSV_REPORT_SOURCE_DIFFERS'; END IF;
  END IF;
 END LOOP;
 FOREACH n IN ARRAY ARRAY[0,1,2,3,4] LOOP
  IF (cnt->>(ARRAY['ready','quarantined','excluded','already_imported','economic'])[n+1])::integer IS DISTINCT FROM
    (SELECT count(*) FROM jsonb_array_elements(b->'rows') rr WHERE CASE WHEN n=4 THEN rr->>'classification'='ECONOMIC' ELSE rr->>'disposition'=(ARRAY['READY','QUARANTINED','EXCLUDED','ALREADY_IMPORTED'])[n+1] END)
  THEN RAISE EXCEPTION 'F3_CSV_REPORT_BINDING_DIFFERS'; END IF;
 END LOOP;
 IF b->>'status'='ALREADY_IMPORTED' AND ((cnt->>'ready')::integer<>0 OR (cnt->>'quarantined')::integer<>0 OR (cnt->>'already_imported')::integer<1 OR b->'batch_errors'<>'[]'::jsonb)
 OR b->>'status'='REPORT_ONLY' AND (cnt->>'ready')::integer>0 AND (cnt->>'quarantined')::integer=0 AND b->'batch_errors'='[]'::jsonb THEN RAISE EXCEPTION 'F3_CSV_REPORT_BINDING_DIFFERS'; END IF;
 IF EXISTS(SELECT 1 FROM __CR_SCHEMA__.gw_journal WHERE backend_pid=l.backend_pid AND xid=l.xid) THEN RAISE EXCEPTION 'F2_READONLY_MUTATED'; END IF;
 IF (SELECT count(*) FROM __CR_SCHEMA__.web_csv_report WHERE portfolio_id=l.root_id)+(SELECT count(*) FROM __CR_SCHEMA__.gh_csv_report_operation WHERE root_id=l.root_id)>=1000 THEN RAISE EXCEPTION 'F3_CSV_REPORT_CAPACITY'; END IF;
 INSERT INTO __CR_SCHEMA__.gh_csv_report_operation VALUES(l.owner_id,l.operation_id,l.root_id,l.context_id,l.generation,l.command_sha256,c->>'request_sha256',e->>'proposal_sha256',e->>'preview_receipt_sha256',base,(e->>'base_operation_id')::uuid,pin,(e->>'report_id')::uuid,response,encode(sha256(response),'hex'),envelope,encode(sha256(envelope),'hex'),(e->>'created_at')::timestamptz,l.backend_pid,l.xid);
 RETURN QUERY SELECT * FROM __CR_SCHEMA__.gh_csv_report_operation WHERE owner_id=l.owner_id AND operation_id=l.operation_id;
END $$;
REVOKE ALL ON __CR_SCHEMA__.gh_csv_report_operation FROM PUBLIC;
REVOKE ALL ON FUNCTION __CR_SCHEMA__.gh_csv_report_scope(text,boolean),__CR_SCHEMA__.gh_csv_report_precheck(uuid,uuid),__CR_SCHEMA__.gh_csv_report_read(uuid,uuid,text,uuid,uuid,text),__CR_SCHEMA__.gh_csv_report_list(uuid,uuid,text),__CR_SCHEMA__.gh_csv_report_commit(bytea,bytea,bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION __CR_SCHEMA__.gh_csv_report_precheck(uuid,uuid),__CR_SCHEMA__.gh_csv_report_read(uuid,uuid,text,uuid,uuid,text),__CR_SCHEMA__.gh_csv_report_list(uuid,uuid,text),__CR_SCHEMA__.gh_csv_report_commit(bytea,bytea,bytea) TO __CR_EXECUTOR__;
