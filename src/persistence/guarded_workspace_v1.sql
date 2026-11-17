-- Explicit fresh-fictional-DB addon, never an old migration or startup installer.
-- Installer replaces only validated __GW_SCHEMA__ / __GW_EXECUTOR__ / __GW_ISSUER__ / __GW_LEGACY__ identifiers.
CREATE TABLE __GW_SCHEMA__.gw_snapshot (
    context_id text PRIMARY KEY CHECK(context_id ~ '^[0-9a-f]{64}$'),
    snapshot bytea NOT NULL CHECK(octet_length(snapshot) BETWEEN 2 AND 2000000),
    CHECK(context_id=encode(sha256(snapshot),'hex'))
);
CREATE TABLE __GW_SCHEMA__.gw_head (
    context_id text PRIMARY KEY REFERENCES __GW_SCHEMA__.gw_snapshot,
    generation bigint NOT NULL CHECK(generation>0),
    rights jsonb NOT NULL,
    expiry text NOT NULL CHECK(expiry IN ('NONE','FINITE','UNKNOWN'))
);
CREATE TABLE __GW_SCHEMA__.gw_history (
    context_id text NOT NULL REFERENCES __GW_SCHEMA__.gw_snapshot,
    generation bigint NOT NULL CHECK(generation>0),
    rights jsonb NOT NULL,
    expiry text NOT NULL,
    PRIMARY KEY(context_id,generation)
);
CREATE TABLE __GW_SCHEMA__.gw_mode (singleton boolean PRIMARY KEY CHECK(singleton), mode text NOT NULL CHECK(mode IN ('FICTIONAL_ONLY','CLOSED')));
INSERT INTO __GW_SCHEMA__.gw_mode VALUES(true,'FICTIONAL_ONLY');
CREATE TABLE __GW_SCHEMA__.gw_root (
    root_id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES __GW_SCHEMA__.app_user,
    context_id text NOT NULL REFERENCES __GW_SCHEMA__.gw_snapshot,
    CONSTRAINT gw_root_portfolio_fkey FOREIGN KEY(root_id) REFERENCES __GW_SCHEMA__.portfolio(portfolio_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE __GW_SCHEMA__.gw_lease (
    backend_pid integer NOT NULL,
    xid text NOT NULL,
    owner_id uuid NOT NULL,
    root_id uuid NOT NULL REFERENCES __GW_SCHEMA__.gw_root,
    context_id text NOT NULL,
    generation bigint NOT NULL,
    operation_id uuid NOT NULL,
    command_sha256 text NOT NULL CHECK(command_sha256 ~ '^[0-9a-f]{64}$'),
    purpose text NOT NULL CHECK(purpose IN ('EXECUTE_CREATE','ARCHIVE_READ','ARCHIVE_EXPORT','EXECUTE_REPRODUCE')),
    phase text NOT NULL CHECK(phase IN ('OPEN','SEALED','READONLY','REPLAY')),
    state_sha256 text,
    PRIMARY KEY(backend_pid,xid)
);
CREATE TABLE __GW_SCHEMA__.gw_journal (
    seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    backend_pid integer NOT NULL,
    xid text NOT NULL,
    root_id uuid NOT NULL,
    table_name text NOT NULL,
    action text NOT NULL CHECK(action IN ('INSERT','UPDATE','DELETE')),
    row_key jsonb NOT NULL,
    old_row jsonb,
    new_row jsonb
);
CREATE TABLE __GW_SCHEMA__.gw_artifact (
    owner_id uuid NOT NULL,
    operation_id uuid NOT NULL,
    root_id uuid NOT NULL REFERENCES __GW_SCHEMA__.gw_root,
    context_id text NOT NULL REFERENCES __GW_SCHEMA__.gw_snapshot,
    generation bigint NOT NULL,
    revision_id uuid NOT NULL,
    ledger_pin bigint NOT NULL CHECK(ledger_pin>0),
    issued bytea NOT NULL CHECK(octet_length(issued) BETWEEN 2 AND 2000000),
    issued_sha256 text NOT NULL CHECK(issued_sha256=encode(sha256(issued),'hex')),
    response bytea NOT NULL CHECK(octet_length(response) BETWEEN 2 AND 6000000),
    response_sha256 text NOT NULL CHECK(response_sha256=encode(sha256(response),'hex')),
    envelope bytea NOT NULL CHECK(octet_length(envelope) BETWEEN 2 AND 65536),
    envelope_sha256 text NOT NULL CHECK(envelope_sha256=encode(sha256(envelope),'hex')),
    PRIMARY KEY(owner_id,operation_id)
);
CREATE TABLE __GW_SCHEMA__.gw_operation (
    owner_id uuid NOT NULL,
    operation_id uuid NOT NULL,
    root_id uuid NOT NULL,
    context_id text NOT NULL,
    generation bigint NOT NULL,
    command_sha256 text NOT NULL CHECK(command_sha256 ~ '^[0-9a-f]{64}$'),
    kind text NOT NULL CHECK(kind IN ('CREATE','LEDGER','PREFERENCES','CSV')),
    revision_id uuid NOT NULL,
    report_id uuid,
    journal_count bigint NOT NULL CHECK(journal_count>0),
    state_sha256 text NOT NULL,
    PRIMARY KEY(owner_id,operation_id),
    FOREIGN KEY(owner_id,operation_id) REFERENCES __GW_SCHEMA__.gw_artifact
);

CREATE FUNCTION __GW_SCHEMA__.gw_rights_valid(r jsonb) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
 SELECT COALESCE(jsonb_typeof(r)='object' AND r ?& ARRAY['EXECUTE_CREATE','ARCHIVE_READ','ARCHIVE_EXPORT','EXECUTE_REPRODUCE']
 AND (SELECT count(*)=4 FROM jsonb_object_keys(r))
 AND jsonb_typeof(r->'EXECUTE_CREATE')='boolean' AND jsonb_typeof(r->'ARCHIVE_READ')='boolean'
 AND jsonb_typeof(r->'ARCHIVE_EXPORT')='boolean' AND jsonb_typeof(r->'EXECUTE_REPRODUCE')='boolean',false)
$$;
CREATE FUNCTION __GW_SCHEMA__.gw_publish(b bytea) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE k text; v jsonb;
BEGIN
 IF b IS NULL OR octet_length(b) NOT BETWEEN 2 AND 2000000 THEN RAISE EXCEPTION 'F2_SHAPE'; END IF;
 v:=convert_from(b,'UTF8')::jsonb;
 IF jsonb_typeof(v) IS DISTINCT FROM 'object' THEN RAISE EXCEPTION 'F2_SHAPE'; END IF;
 k:=encode(sha256(b),'hex');
 INSERT INTO __GW_SCHEMA__.gw_snapshot VALUES(k,b);
 RETURN k;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_set_rights(k text,g bigint,r jsonb,e text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE old_g bigint;
BEGIN
 IF k IS NULL OR k !~ '^[0-9a-f]{64}$' OR g IS NULL OR g<1 OR e IS NULL OR e NOT IN ('NONE','FINITE','UNKNOWN') OR NOT __GW_SCHEMA__.gw_rights_valid(r) THEN RAISE EXCEPTION 'F2_SHAPE'; END IF;
 PERFORM 1 FROM __GW_SCHEMA__.gw_mode WHERE singleton FOR UPDATE;
 SELECT generation INTO old_g FROM __GW_SCHEMA__.gw_head WHERE context_id=k FOR UPDATE;
 IF old_g IS NOT NULL AND g<>old_g+1 OR old_g IS NULL AND g<>1 THEN RAISE EXCEPTION 'F2_GENERATION_DIFFERS'; END IF;
 INSERT INTO __GW_SCHEMA__.gw_history VALUES(k,g,r,e);
 INSERT INTO __GW_SCHEMA__.gw_head VALUES(k,g,r,e) ON CONFLICT(context_id) DO UPDATE SET generation=EXCLUDED.generation,rights=EXCLUDED.rights,expiry=EXCLUDED.expiry;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_precheck(o uuid,op uuid,h text)
RETURNS TABLE(root_id uuid,context_id text,generation bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE v __GW_SCHEMA__.gw_operation%ROWTYPE;
BEGIN
 IF o IS NULL OR op IS NULL OR h IS NULL OR h !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'F2_SHAPE'; END IF;
 SELECT * INTO v FROM __GW_SCHEMA__.gw_operation WHERE owner_id=o AND operation_id=op;
 IF FOUND THEN
   IF v.command_sha256 IS DISTINCT FROM h THEN RAISE EXCEPTION 'F2_IDEMPOTENCY_CONFLICT'; END IF;
   RETURN QUERY SELECT v.root_id,v.context_id,v.generation;
 END IF;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_root_metadata(o uuid,r uuid)
RETURNS TABLE(context_id text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
BEGIN
 IF o IS NULL OR r IS NULL THEN RAISE EXCEPTION 'F2_SHAPE'; END IF;
 RETURN QUERY SELECT x.context_id FROM __GW_SCHEMA__.gw_root x WHERE x.root_id=r AND x.owner_id=o;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_admit(o uuid,r uuid,k text,g bigint,p text,op uuid,h text,new_root boolean DEFAULT false) RETURNS bytea
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE head __GW_SCHEMA__.gw_head%ROWTYPE; root __GW_SCHEMA__.gw_root%ROWTYPE; prior __GW_SCHEMA__.gw_operation%ROWTYPE; b bytea; m text; replay boolean:=false;
BEGIN
 IF o IS NULL OR r IS NULL OR k IS NULL OR k !~ '^[0-9a-f]{64}$' OR g IS NULL OR g<1 OR p IS NULL OR p NOT IN ('EXECUTE_CREATE','ARCHIVE_READ','ARCHIVE_EXPORT','EXECUTE_REPRODUCE') OR op IS NULL OR h IS NULL OR h !~ '^[0-9a-f]{64}$' OR new_root IS NULL THEN RAISE EXCEPTION 'F2_SHAPE'; END IF;
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'F2_ISOLATION'; END IF;
 IF EXISTS(SELECT 1 FROM __GW_SCHEMA__.gw_lease WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text) THEN RAISE EXCEPTION 'F2_SINGLE_SCOPE'; END IF;
 SELECT mode INTO m FROM __GW_SCHEMA__.gw_mode WHERE singleton FOR SHARE;
 IF m IS DISTINCT FROM 'FICTIONAL_ONLY' THEN RAISE EXCEPTION 'F2_MODE_HOLD'; END IF;
 SELECT * INTO head FROM __GW_SCHEMA__.gw_head WHERE context_id=k FOR SHARE;
 IF NOT FOUND OR head.generation IS DISTINCT FROM g THEN RAISE EXCEPTION 'F2_GENERATION_DIFFERS'; END IF;
 IF head.expiry IS DISTINCT FROM 'NONE' THEN RAISE EXCEPTION 'F2_EXPIRY_HOLD'; END IF;
 IF NOT COALESCE((head.rights->>'ARCHIVE_READ')::boolean,false) OR NOT COALESCE((head.rights->>p)::boolean,false) THEN RAISE EXCEPTION 'F2_RIGHT_REFUSED'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('finweb.f2.root:'||'__GW_SCHEMA__'||':'||r::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('finweb.f2.op:'||'__GW_SCHEMA__'||':'||o::text||':'||op::text,0));
 SELECT * INTO prior FROM __GW_SCHEMA__.gw_operation WHERE owner_id=o AND operation_id=op;
 IF FOUND AND p='EXECUTE_CREATE' THEN
   IF prior.command_sha256 IS DISTINCT FROM h OR prior.root_id IS DISTINCT FROM r OR prior.context_id IS DISTINCT FROM k THEN RAISE EXCEPTION 'F2_IDEMPOTENCY_CONFLICT'; END IF;
   replay:=true;
 END IF;
 SELECT * INTO root FROM __GW_SCHEMA__.gw_root WHERE root_id=r;
 IF NOT FOUND THEN
   IF NOT new_root OR p<>'EXECUTE_CREATE' OR replay OR EXISTS(SELECT 1 FROM __GW_SCHEMA__.portfolio WHERE portfolio_id=r) THEN RAISE EXCEPTION 'F2_NOT_FOUND'; END IF;
   INSERT INTO __GW_SCHEMA__.gw_root VALUES(r,o,k);
 ELSE
   IF root.owner_id IS DISTINCT FROM o OR root.context_id IS DISTINCT FROM k OR new_root AND NOT replay THEN RAISE EXCEPTION 'F2_NOT_FOUND'; END IF;
 END IF;
 INSERT INTO __GW_SCHEMA__.gw_lease(backend_pid,xid,owner_id,root_id,context_id,generation,operation_id,command_sha256,purpose,phase)
 VALUES(pg_backend_pid(),pg_current_xact_id()::text,o,r,k,g,op,h,p,CASE WHEN replay THEN 'REPLAY' WHEN p='EXECUTE_CREATE' THEN 'OPEN' ELSE 'READONLY' END);
 SELECT snapshot INTO b FROM __GW_SCHEMA__.gw_snapshot WHERE context_id=k;
 RETURN b;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_scope()
RETURNS TABLE(owner_id uuid,root_id uuid,context_id text,generation bigint,operation_id uuid,purpose text)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
 SELECT owner_id,root_id,context_id,generation,operation_id,purpose FROM __GW_SCHEMA__.gw_lease
 WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text
$$;
CREATE FUNCTION __GW_SCHEMA__.gw_target_root(t text,v jsonb) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE r uuid;
BEGIN
 IF t IS NULL OR v IS NULL OR jsonb_typeof(v) IS DISTINCT FROM 'object' THEN RAISE EXCEPTION 'F2_ROOT_UNKNOWN'; END IF;
 IF t='ledger_event' THEN
   SELECT portfolio_id INTO r FROM __GW_SCHEMA__.account WHERE account_id=(v->>'account_id')::uuid;
 ELSE
   IF t NOT IN ('portfolio','account','benchmark_selection','web_saved_sandbox','web_portfolio_revision','web_csv_report','web_csv_source_key') THEN RAISE EXCEPTION 'F2_TARGET_UNKNOWN'; END IF;
   r:=(v->>'portfolio_id')::uuid;
 END IF;
 IF r IS NULL THEN RAISE EXCEPTION 'F2_ROOT_UNKNOWN'; END IF;
 RETURN r;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_row_allowed(t text,v jsonb,w boolean) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE r uuid;
BEGIN
 IF w IS NULL THEN RETURN false; END IF;
 r:=__GW_SCHEMA__.gw_target_root(t,v);
 IF NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.gw_root WHERE root_id=r) THEN RETURN true; END IF;
 RETURN EXISTS(SELECT 1 FROM __GW_SCHEMA__.gw_lease l JOIN __GW_SCHEMA__.gw_root x USING(root_id)
 WHERE l.backend_pid=pg_backend_pid() AND l.xid=pg_current_xact_id()::text AND l.root_id=r AND l.owner_id=x.owner_id AND l.context_id=x.context_id
 AND (NOT w OR l.purpose='EXECUTE_CREATE' AND l.phase='OPEN'));
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_write_fence() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE v jsonb; ov jsonb; r uuid; ro uuid; l __GW_SCHEMA__.gw_lease%ROWTYPE; selected boolean; actual_owner uuid;
BEGIN
 IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'F2_TRUNCATE_REFUSED'; END IF;
 IF TG_OP<>'INSERT' THEN ov:=to_jsonb(OLD); ro:=__GW_SCHEMA__.gw_target_root(TG_TABLE_NAME,ov); END IF;
 IF TG_OP<>'DELETE' THEN v:=to_jsonb(NEW); r:=__GW_SCHEMA__.gw_target_root(TG_TABLE_NAME,v); ELSE r:=ro; END IF;
 IF ro IS NOT NULL AND ro IS DISTINCT FROM r THEN RAISE EXCEPTION 'F2_ROOT_DIFFERS'; END IF;
 selected:=EXISTS(SELECT 1 FROM __GW_SCHEMA__.gw_root WHERE root_id=r);
 IF selected THEN
   SELECT * INTO l FROM __GW_SCHEMA__.gw_lease WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text;
   IF NOT FOUND OR l.root_id IS DISTINCT FROM r OR l.purpose IS DISTINCT FROM 'EXECUTE_CREATE' OR l.phase IS DISTINCT FROM 'OPEN' THEN RAISE EXCEPTION 'F2_WRITE_REFUSED'; END IF;
 END IF;
 IF TG_OP='INSERT' AND TG_TABLE_NAME='web_saved_sandbox' THEN
   SELECT user_id INTO actual_owner FROM __GW_SCHEMA__.portfolio WHERE portfolio_id=r;
   IF actual_owner IS NULL THEN RAISE EXCEPTION 'F2_ROOT_UNKNOWN'; END IF;
   -- Match the existing application's key literally: current_schema() here is
   -- pg_catalog because this function has a fixed definer search_path.
   PERFORM pg_advisory_xact_lock(hashtextextended('web-user:'||actual_owner::text||'__GW_SCHEMA__',0));
   -- BEFORE also runs for ON CONFLICT. An existing row consumes no new slot.
   IF NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.web_saved_sandbox WHERE portfolio_id=r)
      AND (SELECT count(*) FROM __GW_SCHEMA__.web_saved_sandbox s JOIN __GW_SCHEMA__.portfolio p USING(portfolio_id) WHERE p.user_id=actual_owner)>=32 THEN
     RAISE EXCEPTION 'F2_PORTFOLIO_CAPACITY' USING ERRCODE='23514',CONSTRAINT='gw_web_portfolio_capacity',SCHEMA='__GW_SCHEMA__',TABLE='web_saved_sandbox';
   END IF;
 END IF;
 IF NOT selected THEN
   IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
 END IF;
 IF TG_OP<>'DELETE' AND TG_TABLE_NAME='ledger_event' AND v->>'counterparty_account_id' IS NOT NULL THEN
   IF NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.account WHERE account_id=(v->>'counterparty_account_id')::uuid AND portfolio_id=r) THEN RAISE EXCEPTION 'F2_MULTI_ROOT_REFUSED'; END IF;
 END IF;
 IF TG_OP<>'DELETE' AND TG_TABLE_NAME='web_csv_source_key' THEN
   IF NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.account WHERE account_id=(v->>'account_id')::uuid AND portfolio_id=r) OR NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.web_csv_report WHERE report_id=(v->>'report_id')::uuid AND portfolio_id=r) OR v->>'event_id' IS NOT NULL AND NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.ledger_event WHERE event_id=(v->>'event_id')::uuid AND account_id=(v->>'account_id')::uuid) THEN RAISE EXCEPTION 'F2_CSV_SCOPE_DIFFERS'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_journal_after() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE v jsonb; ov jsonb; r uuid; l __GW_SCHEMA__.gw_lease%ROWTYPE; key jsonb;
BEGIN
 IF TG_OP<>'INSERT' THEN ov:=to_jsonb(OLD); END IF;
 IF TG_OP<>'DELETE' THEN v:=to_jsonb(NEW); END IF;
 r:=__GW_SCHEMA__.gw_target_root(TG_TABLE_NAME,COALESCE(v,ov));
 IF NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.gw_root WHERE root_id=r) THEN RETURN NULL; END IF;
 SELECT * INTO l FROM __GW_SCHEMA__.gw_lease WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text;
 IF NOT FOUND OR l.root_id IS DISTINCT FROM r OR l.purpose IS DISTINCT FROM 'EXECUTE_CREATE' OR l.phase IS DISTINCT FROM 'OPEN' THEN RAISE EXCEPTION 'F2_WRITE_REFUSED'; END IF;
 key:=CASE TG_TABLE_NAME WHEN 'portfolio' THEN jsonb_build_object('portfolio_id',r) WHEN 'account' THEN jsonb_build_object('account_id',COALESCE(v,ov)->>'account_id') WHEN 'ledger_event' THEN jsonb_build_object('event_id',COALESCE(v,ov)->>'event_id') WHEN 'benchmark_selection' THEN jsonb_build_object('selection_id',COALESCE(v,ov)->>'selection_id') WHEN 'web_saved_sandbox' THEN jsonb_build_object('portfolio_id',r) WHEN 'web_portfolio_revision' THEN jsonb_build_object('revision_id',COALESCE(v,ov)->>'revision_id') WHEN 'web_csv_report' THEN jsonb_build_object('report_id',COALESCE(v,ov)->>'report_id') WHEN 'web_csv_source_key' THEN jsonb_build_object('source_key',COALESCE(v,ov)->>'source_key') END;
 -- AFTER fires only for actual row outcomes, unlike BEFORE with ON CONFLICT.
 INSERT INTO __GW_SCHEMA__.gw_journal(backend_pid,xid,root_id,table_name,action,row_key,old_row,new_row) VALUES(l.backend_pid,l.xid,r,TG_TABLE_NAME,TG_OP,key,ov,v);
 IF (SELECT count(*) FROM __GW_SCHEMA__.gw_journal WHERE backend_pid=l.backend_pid AND xid=l.xid)>2048 THEN RAISE EXCEPTION 'F2_JOURNAL_CAP'; END IF;
 RETURN NULL;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_state(r uuid) RETURNS text
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
 SELECT encode(sha256(convert_to(COALESCE(jsonb_agg(x ORDER BY x::text),'[]'::jsonb)::text,'UTF8')),'hex') FROM (
 SELECT jsonb_build_object('table','portfolio','row',to_jsonb(t)) x FROM __GW_SCHEMA__.portfolio t WHERE portfolio_id=r
 UNION ALL SELECT jsonb_build_object('table','account','row',to_jsonb(t)) FROM __GW_SCHEMA__.account t WHERE portfolio_id=r
 UNION ALL SELECT jsonb_build_object('table','ledger_event','row',to_jsonb(t)) FROM __GW_SCHEMA__.ledger_event t WHERE account_id IN (SELECT account_id FROM __GW_SCHEMA__.account WHERE portfolio_id=r)
 UNION ALL SELECT jsonb_build_object('table','benchmark_selection','row',to_jsonb(t)) FROM __GW_SCHEMA__.benchmark_selection t WHERE portfolio_id=r
 UNION ALL SELECT jsonb_build_object('table','web_saved_sandbox','row',to_jsonb(t)) FROM __GW_SCHEMA__.web_saved_sandbox t WHERE portfolio_id=r
 UNION ALL SELECT jsonb_build_object('table','web_portfolio_revision','row',to_jsonb(t)) FROM __GW_SCHEMA__.web_portfolio_revision t WHERE portfolio_id=r
 UNION ALL SELECT jsonb_build_object('table','web_csv_report','row',to_jsonb(t)) FROM __GW_SCHEMA__.web_csv_report t WHERE portfolio_id=r
 UNION ALL SELECT jsonb_build_object('table','web_csv_source_key','row',to_jsonb(t)) FROM __GW_SCHEMA__.web_csv_source_key t WHERE portfolio_id=r
 ) all_rows
$$;
-- Bounded canonical JSON hashing of the issued OUTER contract; no financial
-- Result decoder, arithmetic, or claim that SQL proves a Python dispatch.
CREATE FUNCTION __GW_SCHEMA__.gw_json(v jsonb,depth integer DEFAULT 0) RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE result text;
BEGIN
 IF v IS NULL OR depth IS NULL OR depth>48 THEN RAISE EXCEPTION 'F2_JSON_SHAPE'; END IF;
 CASE jsonb_typeof(v)
 WHEN 'object' THEN SELECT '{'||COALESCE(string_agg(to_jsonb(key)::text||':'||__GW_SCHEMA__.gw_json(value,depth+1),',' ORDER BY key COLLATE "C"),'')||'}' INTO result FROM jsonb_each(v);
 WHEN 'array' THEN SELECT '['||COALESCE(string_agg(__GW_SCHEMA__.gw_json(value,depth+1),',' ORDER BY ord),'')||']' INTO result FROM jsonb_array_elements(v) WITH ORDINALITY a(value,ord);
 ELSE result:=v::text;
 END CASE;
 RETURN result;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_keys(v jsonb,keys text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
 SELECT COALESCE(jsonb_typeof(v)='object' AND v ?& keys AND (SELECT count(*) FROM jsonb_object_keys(v))=cardinality(keys),false)
$$;
CREATE FUNCTION __GW_SCHEMA__.gw_check_artifact(a __GW_SCHEMA__.gw_artifact,kind text,report uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE e jsonb; issued_obj jsonb; response_obj jsonb; snap jsonb; saved_snap jsonb; ws jsonb; m jsonb; vm jsonb; q jsonb; b jsonb; qb bytea; bb bytea; snapshot jsonb; required_q jsonb; required_b jsonb; expected_policy jsonb; registry jsonb; fact jsonb; lookup jsonb; answer text; asof_day text; actual_pin bigint; origin __GW_SCHEMA__.gw_lease%ROWTYPE; j __GW_SCHEMA__.gw_journal%ROWTYPE; actual jsonb;
BEGIN
 -- Check each byte bound BEFORE UTF8 decoding, hex decoding or JSON parsing.
 IF a.issued IS NULL OR octet_length(a.issued) NOT BETWEEN 2 AND 2000000 OR a.response IS NULL OR octet_length(a.response) NOT BETWEEN 2 AND 6000000 OR a.envelope IS NULL OR octet_length(a.envelope) NOT BETWEEN 2 AND 65536 THEN RAISE EXCEPTION 'F2_ARCHIVE_BOUNDS'; END IF;
 IF a.issued_sha256 IS DISTINCT FROM encode(sha256(a.issued),'hex') OR a.response_sha256 IS DISTINCT FROM encode(sha256(a.response),'hex') OR a.envelope_sha256 IS DISTINCT FROM encode(sha256(a.envelope),'hex') THEN RAISE EXCEPTION 'F2_ARCHIVE_DIFFERS'; END IF;
 e:=convert_from(a.envelope,'UTF8')::jsonb; issued_obj:=convert_from(a.issued,'UTF8')::jsonb; response_obj:=convert_from(a.response,'UTF8')::jsonb;
 IF NOT __GW_SCHEMA__.gw_keys(e,ARRAY['schema','synthetic','actual_executor','approval_scope','owner_id','root_id','operation_id','revision_id','ledger_pin','context_id','generation','issued_sha256','response_sha256','manifest_id','result_digest','question_sha256','binding_sha256','selector','family','engine_id','question_hex','binding_hex','fixture_quotes_sha256','fixture_calendar_sha256']) OR convert_to(__GW_SCHEMA__.gw_json(e),'UTF8') IS DISTINCT FROM a.envelope THEN RAISE EXCEPTION 'F2_ENVELOPE_SHAPE'; END IF;
 IF e->>'schema' IS DISTINCT FROM 'finweb.f2.fictional-issued-envelope/1' OR e->'synthetic' IS DISTINCT FROM 'true'::jsonb OR e->>'actual_executor' IS DISTINCT FROM 'local_application' OR e->>'approval_scope' IS DISTINCT FROM 'fictional_local_only' OR e->>'owner_id' IS DISTINCT FROM a.owner_id::text OR e->>'root_id' IS DISTINCT FROM a.root_id::text OR e->>'operation_id' IS DISTINCT FROM a.operation_id::text OR e->>'revision_id' IS DISTINCT FROM a.revision_id::text OR e->'generation' IS DISTINCT FROM to_jsonb(a.generation) OR e->'ledger_pin' IS DISTINCT FROM to_jsonb(a.ledger_pin) OR e->>'context_id' IS DISTINCT FROM a.context_id OR e->>'issued_sha256' IS DISTINCT FROM a.issued_sha256 OR e->>'response_sha256' IS DISTINCT FROM a.response_sha256 OR e->>'selector' IS DISTINCT FROM 'CP5_DIVERSIFICATION' OR e->>'family' IS DISTINCT FROM 'CP5_DIVERSIFICATION' OR e->>'engine_id' IS DISTINCT FROM 'diversification/cp5-0.2' THEN RAISE EXCEPTION 'F2_ENVELOPE_DIFFERS'; END IF;
 IF e->>'fixture_quotes_sha256' IS DISTINCT FROM 'ec3c1def6d88a5f76c514af39697c6eb53fb2d2d2d60c7bfe8f45aefb11eae51' OR e->>'fixture_calendar_sha256' IS DISTINCT FROM '836c573f65c5fee8b94e361fd265da0886a8729c9c83d216545207d884c97f7a' THEN RAISE EXCEPTION 'F2_FIXED_FIXTURE_DIFFERS'; END IF;
 IF jsonb_typeof(e->'question_hex') IS DISTINCT FROM 'string' OR length(e->>'question_hex') NOT BETWEEN 4 AND 65536 OR (e->>'question_hex') !~ '^([0-9a-f]{2})+$' OR jsonb_typeof(e->'binding_hex') IS DISTINCT FROM 'string' OR length(e->>'binding_hex') NOT BETWEEN 4 AND 65536 OR (e->>'binding_hex') !~ '^([0-9a-f]{2})+$' THEN RAISE EXCEPTION 'F2_BINDING_SHAPE'; END IF;
 qb:=decode(e->>'question_hex','hex'); bb:=decode(e->>'binding_hex','hex'); q:=convert_from(qb,'UTF8')::jsonb; b:=convert_from(bb,'UTF8')::jsonb;
 IF e->>'question_sha256' IS DISTINCT FROM encode(sha256(qb),'hex') OR e->>'binding_sha256' IS DISTINCT FROM encode(sha256(bb),'hex') OR qb IS DISTINCT FROM convert_to(__GW_SCHEMA__.gw_json(q),'UTF8') OR bb IS DISTINCT FROM convert_to(__GW_SCHEMA__.gw_json(b),'UTF8') THEN RAISE EXCEPTION 'F2_BINDING_DIFFERS'; END IF;
 SELECT convert_from(s.snapshot,'UTF8')::jsonb INTO snapshot FROM __GW_SCHEMA__.gw_snapshot s WHERE s.context_id=a.context_id;
 IF snapshot IS NULL OR snapshot->>'scope' IS DISTINCT FROM 'LOCAL_FICTIONAL_ONLY' OR NOT COALESCE(snapshot->'release'->'fields'->'files' ? (e->>'fixture_quotes_sha256'),false) OR NOT COALESCE(snapshot->'release'->'fields'->'files' ? (e->>'fixture_calendar_sha256'),false) THEN RAISE EXCEPTION 'F2_SOURCE_DIFFERS'; END IF;
 IF kind='CREATE' THEN
   SELECT (request_json::jsonb)->>'as_of',ledger_version,snapshot_json::jsonb INTO asof_day,actual_pin,saved_snap FROM __GW_SCHEMA__.web_saved_sandbox WHERE portfolio_id=a.root_id;
   snap:=response_obj;
 ELSE
   SELECT as_of::text,ledger_version,snapshot_json::jsonb INTO asof_day,actual_pin,saved_snap FROM __GW_SCHEMA__.web_portfolio_revision WHERE portfolio_id=a.root_id AND revision_id=a.revision_id;
   IF kind='CSV' THEN
     snap:=response_obj->'workspace_result'->'snapshot';
     ws:=response_obj->'workspace_result'->'workspace';
     IF NOT __GW_SCHEMA__.gw_keys(response_obj,ARRAY['schema_version','portfolio_id','report','workspace_result']) OR NOT __GW_SCHEMA__.gw_keys(response_obj->'workspace_result',ARRAY['snapshot','workspace']) OR NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.web_csv_report WHERE report_id=report AND portfolio_id=a.root_id AND report_json::jsonb=response_obj->'report') THEN RAISE EXCEPTION 'F2_RESPONSE_DIFFERS'; END IF;
     IF response_obj->'report'->>'report_id' IS DISTINCT FROM report::text OR response_obj->'report'->>'revision_id' IS DISTINCT FROM a.revision_id::text OR response_obj->'report'->>'status' IS DISTINCT FROM 'COMMITTED' THEN RAISE EXCEPTION 'F2_RESPONSE_DIFFERS'; END IF;
   ELSE
     snap:=response_obj->'snapshot'; ws:=response_obj->'workspace';
     IF NOT __GW_SCHEMA__.gw_keys(response_obj,ARRAY['snapshot','workspace']) THEN RAISE EXCEPTION 'F2_RESPONSE_DIFFERS'; END IF;
   END IF;
   IF NOT __GW_SCHEMA__.gw_keys(ws,ARRAY['schema_version','portfolio_id','revision_id','current_revision_id','as_of','fixture_as_of','history','accounts','ledger','listings','policies','benchmark']) OR ws->>'schema_version' IS DISTINCT FROM 'finweb.cp7/1' OR ws->>'portfolio_id' IS DISTINCT FROM a.root_id::text OR ws->>'revision_id' IS DISTINCT FROM a.revision_id::text OR ws->>'current_revision_id' IS DISTINCT FROM a.revision_id::text OR ws->'ledger'->'version' IS DISTINCT FROM to_jsonb(a.ledger_pin) THEN RAISE EXCEPTION 'F2_RESPONSE_DIFFERS'; END IF;
 END IF;
 IF snap IS DISTINCT FROM saved_snap OR convert_to(__GW_SCHEMA__.gw_json(response_obj),'UTF8') IS DISTINCT FROM a.response THEN RAISE EXCEPTION 'F2_RESPONSE_DIFFERS'; END IF;
 IF asof_day IS NULL OR actual_pin IS DISTINCT FROM a.ledger_pin OR snapshot->>'as_of' IS DISTINCT FROM asof_day OR snap->>'portfolio_id' IS DISTINCT FROM a.root_id::text OR snap->>'as_of' IS DISTINCT FROM asof_day OR snap->'synthetic' IS DISTINCT FROM 'true'::jsonb OR snap->'persisted' IS DISTINCT FROM 'true'::jsonb OR snap->>'reporting_currency' IS DISTINCT FROM 'USD' THEN RAISE EXCEPTION 'F2_RESPONSE_DIFFERS'; END IF;
 required_q:=jsonb_build_object('schema','finweb.local_fictional.service_question/1','selector','CP5_DIVERSIFICATION','owner_id',a.owner_id,'root_id',a.root_id,'revision_id',a.revision_id,'operation_id',a.operation_id,'portfolio_id',a.root_id,'ledger_pin',a.ledger_pin::text,'as_of',asof_day,'context_id',a.context_id,'generation',a.generation,'account_scope',NULL,'reporting_currency','USD');
 IF q IS DISTINCT FROM required_q THEN RAISE EXCEPTION 'F2_QUESTION_DIFFERS'; END IF;
 IF NOT __GW_SCHEMA__.gw_keys(issued_obj,ARRAY['manifest','manifest_id','result_digest','metrics','clusters','exposure_decompositions']) OR convert_to(__GW_SCHEMA__.gw_json(issued_obj),'UTF8') IS DISTINCT FROM a.issued OR jsonb_typeof(issued_obj->'metrics') IS DISTINCT FROM 'array' OR jsonb_typeof(issued_obj->'clusters') IS DISTINCT FROM 'array' OR jsonb_typeof(issued_obj->'exposure_decompositions') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'F2_ISSUED_SHAPE'; END IF;
 m:=issued_obj->'manifest'; vm:=m->'valuation_manifest';
 IF m->>'schema' IS DISTINCT FROM 'finweb.diversification_manifest/1' OR m->>'engine_id' IS DISTINCT FROM 'diversification/cp5-0.2' OR m->'synthetic' IS DISTINCT FROM 'true'::jsonb OR m->>'state_kind' IS DISTINCT FROM 'ACTUAL' OR m->>'portfolio_id' IS DISTINCT FROM a.root_id::text OR m->'account_scope' IS DISTINCT FROM 'null'::jsonb OR m->>'as_of' IS DISTINCT FROM asof_day OR m->>'reporting_currency' IS DISTINCT FROM 'USD' OR m->'capital_policy_confirmed' IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION 'F2_MANIFEST_DIFFERS'; END IF;
 IF vm->>'portfolio_id' IS DISTINCT FROM a.root_id::text OR vm->'ledger_version' IS DISTINCT FROM to_jsonb(a.ledger_pin) OR vm->>'as_of' IS DISTINCT FROM asof_day OR vm->>'reporting_currency' IS DISTINCT FROM 'USD' OR vm->>'scope' IS DISTINCT FROM 'PORTFOLIO' OR vm->>'state_kind' IS DISTINCT FROM 'ACTUAL' OR vm->'synthetic' IS DISTINCT FROM 'true'::jsonb OR vm->>'split_detection' IS DISTINCT FROM 'F8B_DRY_RUN' OR vm->>'release_id' IS DISTINCT FROM encode(sha256(convert_to(__GW_SCHEMA__.gw_json(snapshot->'release'->'fields'),'UTF8')),'hex') THEN RAISE EXCEPTION 'F2_VALUATION_DIFFERS'; END IF;
 IF m->'capital_policy' IS DISTINCT FROM snapshot->'capital_policy'->'fields' OR m->'capital_policy'->>'origin' IS DISTINCT FROM 'SYNTHETIC_CANDIDATE' OR m->'capital_policy'->>'scope_kind' IS DISTINCT FROM 'PORTFOLIO' OR m->'capital_policy'->>'portfolio_id' IS DISTINCT FROM a.root_id::text THEN RAISE EXCEPTION 'F2_POLICY_DIFFERS'; END IF;
 expected_policy:=jsonb_build_array(jsonb_build_array('digest',encode(sha256(convert_to(__GW_SCHEMA__.gw_json(jsonb_build_object('feed',snapshot->'policy'->'fields'->'feed_sources','filing',snapshot->'policy'->'fields'->'filing_sources')),'UTF8')),'hex')),jsonb_build_array('feed',(SELECT string_agg(value,',' ORDER BY value COLLATE "C") FROM jsonb_array_elements_text(snapshot->'policy'->'fields'->'feed_sources'))),jsonb_build_array('filing',(SELECT string_agg(value,',' ORDER BY value COLLATE "C") FROM jsonb_array_elements_text(snapshot->'policy'->'fields'->'filing_sources'))));
 IF vm->'detection_policy' IS DISTINCT FROM expected_policy THEN RAISE EXCEPTION 'F2_POLICY_DIFFERS'; END IF;
 IF jsonb_typeof(snapshot->'source_records') IS DISTINCT FROM 'array' OR jsonb_array_length(snapshot->'source_records') NOT BETWEEN 1 AND 16 OR EXISTS(SELECT 1 FROM jsonb_array_elements(snapshot->'source_records') r WHERE r->'fields'->'synthetic' IS DISTINCT FROM 'true'::jsonb OR r->'fields'->'terms_check' IS DISTINCT FROM 'null'::jsonb) THEN RAISE EXCEPTION 'F2_SOURCE_DIFFERS'; END IF;
 SELECT jsonb_agg(CASE WHEN r->'fields'->'source_priority'='null'::jsonb THEN (r->'fields')-'source_priority' ELSE r->'fields' END ORDER BY r->'fields'->>'source_id' COLLATE "C") INTO registry FROM jsonb_array_elements(snapshot->'source_records') r;
 IF vm->>'source_registry_digest' IS DISTINCT FROM encode(sha256(convert_to(__GW_SCHEMA__.gw_json(registry),'UTF8')),'hex') THEN RAISE EXCEPTION 'F2_SOURCE_DIFFERS'; END IF;
 IF jsonb_typeof(m->'identity_facts') IS DISTINCT FROM 'array' OR jsonb_array_length(m->'identity_facts')>48 OR m->>'identity_digest' IS DISTINCT FROM encode(sha256(convert_to(__GW_SCHEMA__.gw_json(m->'identity_facts'),'UTF8')),'hex') THEN RAISE EXCEPTION 'F2_IDENTITY_DIFFERS'; END IF;
 FOR fact IN SELECT value FROM jsonb_array_elements(m->'identity_facts') LOOP
   IF jsonb_typeof(fact) IS DISTINCT FROM 'array' OR jsonb_array_length(fact)<>3 OR fact->>0 NOT IN ('trading_currency','exchange_mic','security_type') THEN RAISE EXCEPTION 'F2_IDENTITY_DIFFERS'; END IF;
   SELECT value INTO lookup FROM jsonb_array_elements(snapshot->'lookup_answers') WHERE value->0->>'uuid'=fact->>1;
   IF lookup IS NULL THEN RAISE EXCEPTION 'F2_IDENTITY_DIFFERS'; END IF;
   answer:=CASE fact->>0 WHEN 'trading_currency' THEN lookup->1->'fields'->>'code' WHEN 'exchange_mic' THEN lookup->>2 WHEN 'security_type' THEN lookup->>3 END;
   IF fact->>2 IS DISTINCT FROM answer THEN RAISE EXCEPTION 'F2_IDENTITY_DIFFERS'; END IF;
 END LOOP;
 IF issued_obj->>'manifest_id' IS DISTINCT FROM encode(sha256(convert_to(__GW_SCHEMA__.gw_json(m),'UTF8')),'hex') OR issued_obj->>'result_digest' IS DISTINCT FROM encode(sha256(convert_to(__GW_SCHEMA__.gw_json(jsonb_build_object('metrics',issued_obj->'metrics','clusters',issued_obj->'clusters','exposure_decompositions',issued_obj->'exposure_decompositions')),'UTF8')),'hex') OR e->>'manifest_id' IS DISTINCT FROM issued_obj->>'manifest_id' OR e->>'result_digest' IS DISTINCT FROM issued_obj->>'result_digest' THEN RAISE EXCEPTION 'F2_NATIVE_DIGEST_DIFFERS'; END IF;
 required_b:=jsonb_build_object('schema','finweb.local_fictional.service_binding/1','question',q,'question_sha256',e->>'question_sha256','context_snapshot_sha256',a.context_id,'generation',a.generation,'family','CP5_DIVERSIFICATION','engine_id','diversification/cp5-0.2','manifest_id',e->>'manifest_id','result_digest',e->>'result_digest','issued_sha256',a.issued_sha256,'synthetic',true,'release_id',vm->>'release_id','source_registry_digest',vm->>'source_registry_digest','consumed_identity_digest',m->>'identity_digest','f8b_policy',vm->'detection_policy');
 IF b IS DISTINCT FROM required_b THEN RAISE EXCEPTION 'F2_BINDING_DIFFERS'; END IF;
 IF NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.portfolio WHERE portfolio_id=a.root_id AND user_id=a.owner_id) THEN RAISE EXCEPTION 'F2_ROOT_DIFFERS'; END IF;
 -- Revalidate original actual row witnesses even after later append-only ops.
 SELECT * INTO origin FROM __GW_SCHEMA__.gw_lease WHERE owner_id=a.owner_id AND operation_id=a.operation_id AND phase='SEALED';
 IF NOT FOUND THEN RAISE EXCEPTION 'F2_ORIGIN_DIFFERS'; END IF;
 FOR j IN SELECT * FROM __GW_SCHEMA__.gw_journal WHERE backend_pid=origin.backend_pid AND xid=origin.xid LOOP
   EXECUTE format('SELECT to_jsonb(t) FROM %I.%I t WHERE to_jsonb(t) @> $1','__GW_SCHEMA__',j.table_name) INTO actual USING j.row_key;
   IF j.root_id IS DISTINCT FROM a.root_id OR j.action<>'INSERT' OR actual IS DISTINCT FROM j.new_row THEN RAISE EXCEPTION 'F2_JOURNAL_DIFFERS'; END IF;
 END LOOP;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_validate(pid integer,tx text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE l __GW_SCHEMA__.gw_lease%ROWTYPE; op __GW_SCHEMA__.gw_operation%ROWTYPE; a __GW_SCHEMA__.gw_artifact%ROWTYPE; j __GW_SCHEMA__.gw_journal%ROWTYPE; actual jsonb; n bigint; pin bigint;
BEGIN
 SELECT * INTO l FROM __GW_SCHEMA__.gw_lease WHERE backend_pid=pid AND xid=tx;
 IF NOT FOUND THEN RAISE EXCEPTION 'F2_BUNDLE_MISSING'; END IF;
 IF l.phase IN ('READONLY','REPLAY') THEN
   IF EXISTS(SELECT 1 FROM __GW_SCHEMA__.gw_journal WHERE backend_pid=pid AND xid=tx) THEN RAISE EXCEPTION 'F2_READONLY_MUTATED'; END IF;
   RETURN;
 END IF;
 IF l.phase IS DISTINCT FROM 'SEALED' THEN RAISE EXCEPTION 'F2_UNSEALED'; END IF;
 SELECT * INTO op FROM __GW_SCHEMA__.gw_operation WHERE owner_id=l.owner_id AND operation_id=l.operation_id;
 SELECT * INTO a FROM __GW_SCHEMA__.gw_artifact WHERE owner_id=l.owner_id AND operation_id=l.operation_id;
 IF op.owner_id IS NULL OR a.owner_id IS NULL OR op.root_id IS DISTINCT FROM l.root_id OR op.context_id IS DISTINCT FROM l.context_id OR op.generation IS DISTINCT FROM l.generation OR op.command_sha256 IS DISTINCT FROM l.command_sha256 OR a.root_id IS DISTINCT FROM op.root_id OR a.context_id IS DISTINCT FROM op.context_id OR a.generation IS DISTINCT FROM op.generation OR a.revision_id IS DISTINCT FROM op.revision_id THEN RAISE EXCEPTION 'F2_BUNDLE_DIFFERS'; END IF;
 SELECT count(*) INTO n FROM __GW_SCHEMA__.gw_journal WHERE backend_pid=pid AND xid=tx;
 IF n<1 OR n<>op.journal_count OR op.state_sha256 IS DISTINCT FROM l.state_sha256 OR l.state_sha256 IS DISTINCT FROM __GW_SCHEMA__.gw_state(l.root_id) THEN RAISE EXCEPTION 'F2_JOURNAL_DIFFERS'; END IF;
 IF NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.portfolio WHERE portfolio_id=l.root_id AND user_id=l.owner_id) OR NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.web_saved_sandbox WHERE portfolio_id=l.root_id) THEN RAISE EXCEPTION 'F2_ROOT_DIFFERS'; END IF;
 SELECT max(e.ledger_seq) INTO pin FROM __GW_SCHEMA__.ledger_event e JOIN __GW_SCHEMA__.account c USING(account_id) WHERE c.portfolio_id=l.root_id;
 IF pin IS DISTINCT FROM a.ledger_pin THEN RAISE EXCEPTION 'F2_PIN_DIFFERS'; END IF;
 IF op.kind='CREATE' THEN
   IF op.revision_id IS DISTINCT FROM l.root_id OR NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.gw_journal WHERE backend_pid=pid AND xid=tx AND table_name='portfolio' AND action='INSERT') THEN RAISE EXCEPTION 'F2_CREATE_DIFFERS'; END IF;
 ELSE
   IF NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.web_portfolio_revision WHERE portfolio_id=l.root_id AND revision_id=op.revision_id AND ledger_version=pin) THEN RAISE EXCEPTION 'F2_REVISION_DIFFERS'; END IF;
 END IF;
 IF op.kind='CSV' THEN
   IF op.report_id IS NULL OR NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.web_csv_report WHERE portfolio_id=l.root_id AND report_id=op.report_id AND revision_id=op.revision_id AND status='COMMITTED') OR NOT EXISTS(SELECT 1 FROM __GW_SCHEMA__.gw_journal WHERE backend_pid=pid AND xid=tx AND table_name='web_csv_source_key') THEN RAISE EXCEPTION 'F2_CSV_BUNDLE_DIFFERS'; END IF;
   IF EXISTS(SELECT 1 FROM __GW_SCHEMA__.gw_journal WHERE backend_pid=pid AND xid=tx AND table_name IN ('web_csv_report','web_csv_source_key') AND new_row->>'report_id' IS DISTINCT FROM op.report_id::text) THEN RAISE EXCEPTION 'F2_CSV_BUNDLE_DIFFERS'; END IF;
 ELSE
   IF op.report_id IS NOT NULL OR EXISTS(SELECT 1 FROM __GW_SCHEMA__.gw_journal WHERE backend_pid=pid AND xid=tx AND table_name IN ('web_csv_report','web_csv_source_key')) THEN RAISE EXCEPTION 'F2_CSV_BUNDLE_DIFFERS'; END IF;
 END IF;
 FOR j IN SELECT * FROM __GW_SCHEMA__.gw_journal WHERE backend_pid=pid AND xid=tx LOOP
   IF j.root_id IS DISTINCT FROM l.root_id OR j.action<>'INSERT' THEN RAISE EXCEPTION 'F2_JOURNAL_DIFFERS'; END IF;
   EXECUTE format('SELECT to_jsonb(t) FROM %I.%I t WHERE to_jsonb(t) @> $1','__GW_SCHEMA__',j.table_name) INTO actual USING j.row_key;
   IF actual IS DISTINCT FROM j.new_row THEN RAISE EXCEPTION 'F2_JOURNAL_DIFFERS'; END IF;
 END LOOP;
 IF a.issued_sha256 IS DISTINCT FROM encode(sha256(a.issued),'hex') OR a.response_sha256 IS DISTINCT FROM encode(sha256(a.response),'hex') THEN RAISE EXCEPTION 'F2_ARCHIVE_DIFFERS'; END IF;
 PERFORM __GW_SCHEMA__.gw_check_artifact(a,op.kind,op.report_id);
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_bundle_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __GW_SCHEMA__.gw_validate(NEW.backend_pid,NEW.xid); RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER gw_bundle_complete AFTER INSERT ON __GW_SCHEMA__.gw_lease DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION __GW_SCHEMA__.gw_bundle_guard();
CREATE FUNCTION __GW_SCHEMA__.gw_seal(kind text,rev uuid,report uuid,issued_b bytea,response_b bytea,envelope_b bytea) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE l __GW_SCHEMA__.gw_lease%ROWTYPE; n bigint; pin bigint; state text; env jsonb;
BEGIN
 IF kind IS NULL OR kind NOT IN ('CREATE','LEDGER','PREFERENCES','CSV') OR rev IS NULL OR issued_b IS NULL OR octet_length(issued_b) NOT BETWEEN 2 AND 2000000 OR response_b IS NULL OR octet_length(response_b) NOT BETWEEN 2 AND 6000000 OR envelope_b IS NULL OR octet_length(envelope_b) NOT BETWEEN 2 AND 65536 THEN RAISE EXCEPTION 'F2_SHAPE'; END IF;
 SELECT * INTO l FROM __GW_SCHEMA__.gw_lease WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text FOR UPDATE;
 IF NOT FOUND OR l.purpose IS DISTINCT FROM 'EXECUTE_CREATE' OR l.phase IS DISTINCT FROM 'OPEN' THEN RAISE EXCEPTION 'F2_SEAL_REFUSED'; END IF;
 env:=convert_from(envelope_b,'UTF8')::jsonb;
 IF jsonb_typeof(env) IS DISTINCT FROM 'object' OR env->>'context_id' IS DISTINCT FROM l.context_id OR env->>'root_id' IS DISTINCT FROM l.root_id::text OR env->>'operation_id' IS DISTINCT FROM l.operation_id::text OR env->>'synthetic' IS DISTINCT FROM 'true' OR env->>'issued_sha256' IS DISTINCT FROM encode(sha256(issued_b),'hex') THEN RAISE EXCEPTION 'F2_ENVELOPE_DIFFERS'; END IF;
 SELECT count(*) INTO n FROM __GW_SCHEMA__.gw_journal WHERE backend_pid=l.backend_pid AND xid=l.xid;
 SELECT max(e.ledger_seq) INTO pin FROM __GW_SCHEMA__.ledger_event e JOIN __GW_SCHEMA__.account a USING(account_id) WHERE a.portfolio_id=l.root_id;
 state:=__GW_SCHEMA__.gw_state(l.root_id);
 INSERT INTO __GW_SCHEMA__.gw_artifact VALUES(l.owner_id,l.operation_id,l.root_id,l.context_id,l.generation,rev,pin,issued_b,encode(sha256(issued_b),'hex'),response_b,encode(sha256(response_b),'hex'),envelope_b,encode(sha256(envelope_b),'hex'));
 INSERT INTO __GW_SCHEMA__.gw_operation VALUES(l.owner_id,l.operation_id,l.root_id,l.context_id,l.generation,l.command_sha256,kind,rev,report,n,state);
 UPDATE __GW_SCHEMA__.gw_lease SET phase='SEALED',state_sha256=state WHERE backend_pid=l.backend_pid AND xid=l.xid;
 PERFORM __GW_SCHEMA__.gw_validate(l.backend_pid,l.xid);
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_archive(o uuid,op uuid) RETURNS TABLE(issued bytea,response bytea,envelope bytea,issued_sha256 text,response_sha256 text,revision_id uuid,ledger_pin bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$
DECLARE l __GW_SCHEMA__.gw_lease%ROWTYPE; a __GW_SCHEMA__.gw_artifact%ROWTYPE; original __GW_SCHEMA__.gw_operation%ROWTYPE;
BEGIN
 IF o IS NULL OR op IS NULL THEN RAISE EXCEPTION 'F2_SHAPE'; END IF;
 SELECT * INTO l FROM __GW_SCHEMA__.gw_lease WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text;
 SELECT * INTO a FROM __GW_SCHEMA__.gw_artifact WHERE owner_id=o AND operation_id=op;
 IF l.owner_id IS NULL OR a.owner_id IS NULL OR l.owner_id IS DISTINCT FROM o OR l.root_id IS DISTINCT FROM a.root_id OR l.context_id IS DISTINCT FROM a.context_id THEN RAISE EXCEPTION 'F2_NOT_FOUND'; END IF;
 IF a.issued_sha256 IS DISTINCT FROM encode(sha256(a.issued),'hex') OR a.response_sha256 IS DISTINCT FROM encode(sha256(a.response),'hex') THEN RAISE EXCEPTION 'F2_ARCHIVE_DIFFERS'; END IF;
 SELECT * INTO original FROM __GW_SCHEMA__.gw_operation WHERE owner_id=o AND operation_id=op;
 IF NOT FOUND OR original.root_id IS DISTINCT FROM a.root_id OR original.context_id IS DISTINCT FROM a.context_id OR original.generation IS DISTINCT FROM a.generation OR original.revision_id IS DISTINCT FROM a.revision_id THEN RAISE EXCEPTION 'F2_OPERATION_DIFFERS'; END IF;
 PERFORM __GW_SCHEMA__.gw_check_artifact(a,original.kind,original.report_id);
 RETURN QUERY SELECT a.issued,a.response,a.envelope,a.issued_sha256,a.response_sha256,a.revision_id,a.ledger_pin;
END $$;
CREATE FUNCTION __GW_SCHEMA__.gw_no_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,__GW_SCHEMA__,pg_temp AS $$ BEGIN RAISE EXCEPTION 'F2_IMMUTABLE'; END $$;

DO $$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['portfolio','account','ledger_event','benchmark_selection','web_saved_sandbox','web_portfolio_revision','web_csv_report','web_csv_source_key'] LOOP
   EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY','__GW_SCHEMA__',t);
   -- The definer owner bypass is explicit; FORCE is not enabled because
   -- metadata lookup must resolve rows hidden from the caller. Owner is NOLOGIN.
   EXECUTE format('CREATE POLICY gw_baseline ON %I.%I AS PERMISSIVE FOR ALL TO __GW_EXECUTOR__,__GW_LEGACY__ USING(true) WITH CHECK(true)','__GW_SCHEMA__',t);
   EXECUTE format('CREATE POLICY gw_selected_guard ON %I.%I AS RESTRICTIVE FOR ALL TO __GW_EXECUTOR__,__GW_LEGACY__ USING(__GW_SCHEMA__.gw_row_allowed(%L,to_jsonb(%I),false)) WITH CHECK(__GW_SCHEMA__.gw_row_allowed(%L,to_jsonb(%I),true))','__GW_SCHEMA__',t,t,t,t,t);
   EXECUTE format('CREATE TRIGGER zz_gw_write BEFORE INSERT OR UPDATE OR DELETE ON %I.%I FOR EACH ROW EXECUTE FUNCTION __GW_SCHEMA__.gw_write_fence()','__GW_SCHEMA__',t);
   EXECUTE format('CREATE TRIGGER zz_gw_journal AFTER INSERT OR UPDATE OR DELETE ON %I.%I FOR EACH ROW EXECUTE FUNCTION __GW_SCHEMA__.gw_journal_after()','__GW_SCHEMA__',t);
   EXECUTE format('CREATE TRIGGER zz_gw_truncate BEFORE TRUNCATE ON %I.%I FOR EACH STATEMENT EXECUTE FUNCTION __GW_SCHEMA__.gw_write_fence()','__GW_SCHEMA__',t);
 END LOOP;
 FOREACH t IN ARRAY ARRAY['gw_snapshot','gw_history','gw_root','gw_journal','gw_artifact','gw_operation'] LOOP
   EXECUTE format('CREATE TRIGGER gw_immutable BEFORE UPDATE OR DELETE ON %I.%I FOR EACH ROW EXECUTE FUNCTION __GW_SCHEMA__.gw_no_mutation()','__GW_SCHEMA__',t);
   EXECUTE format('CREATE TRIGGER gw_no_truncate BEFORE TRUNCATE ON %I.%I FOR EACH STATEMENT EXECUTE FUNCTION __GW_SCHEMA__.gw_no_mutation()','__GW_SCHEMA__',t);
 END LOOP;
END $$;
REVOKE ALL ON __GW_SCHEMA__.gw_snapshot,__GW_SCHEMA__.gw_head,__GW_SCHEMA__.gw_history,__GW_SCHEMA__.gw_mode,__GW_SCHEMA__.gw_root,__GW_SCHEMA__.gw_lease,__GW_SCHEMA__.gw_journal,__GW_SCHEMA__.gw_artifact,__GW_SCHEMA__.gw_operation FROM PUBLIC;
REVOKE ALL ON SEQUENCE __GW_SCHEMA__.gw_journal_seq_seq FROM PUBLIC;
DO $$ DECLARE f record; BEGIN
 FOR f IN SELECT p.oid::regprocedure AS signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='__GW_SCHEMA__' AND p.proname LIKE 'gw_%' LOOP
   EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',f.signature);
 END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION __GW_SCHEMA__.gw_publish(bytea),__GW_SCHEMA__.gw_set_rights(text,bigint,jsonb,text) TO __GW_ISSUER__;
GRANT EXECUTE ON FUNCTION __GW_SCHEMA__.gw_precheck(uuid,uuid,text),__GW_SCHEMA__.gw_root_metadata(uuid,uuid),__GW_SCHEMA__.gw_admit(uuid,uuid,text,bigint,text,uuid,text,boolean),__GW_SCHEMA__.gw_scope(),__GW_SCHEMA__.gw_seal(text,uuid,uuid,bytea,bytea,bytea),__GW_SCHEMA__.gw_archive(uuid,uuid) TO __GW_EXECUTOR__;
GRANT EXECUTE ON FUNCTION __GW_SCHEMA__.gw_row_allowed(text,jsonb,boolean) TO __GW_EXECUTOR__,__GW_LEGACY__;
