-- Explicit new SYNTHETIC_TEST instance only. Not a migration/startup hook.
CREATE TABLE __NP_SCHEMA__.np_payload (
 payload_sha256 text CONSTRAINT np_payload_pkey PRIMARY KEY,
 size_bytes bigint NOT NULL, payload bytea NOT NULL,
 CONSTRAINT np_payload_digest_ck CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
 CONSTRAINT np_payload_size_ck CHECK(size_bytes BETWEEN 0 AND 65536),
 CONSTRAINT np_payload_bytes_ck CHECK(size_bytes=octet_length(payload) AND payload_sha256=encode(sha256(payload),'hex'))
);
CREATE TABLE __NP_SCHEMA__.np_acquisition (
 envelope_sha256 text CONSTRAINT np_acquisition_pkey PRIMARY KEY, envelope bytea NOT NULL,
 CONSTRAINT np_acquisition_digest_ck CHECK(envelope_sha256 ~ '^[0-9a-f]{64}$'),
 CONSTRAINT np_acquisition_bytes_ck CHECK(octet_length(envelope) BETWEEN 2 AND 65536 AND envelope_sha256=encode(sha256(envelope),'hex'))
);
CREATE TABLE __NP_SCHEMA__.np_manifest (
 manifest_sha256 text CONSTRAINT np_manifest_pkey PRIMARY KEY, manifest bytea NOT NULL,
 payload_sha256 text NOT NULL CONSTRAINT np_manifest_payload_fkey REFERENCES __NP_SCHEMA__.np_payload(payload_sha256),
 envelope_sha256 text CONSTRAINT np_manifest_envelope_fkey REFERENCES __NP_SCHEMA__.np_acquisition(envelope_sha256),
 witness_sha256 text, witness bytea,
 CONSTRAINT np_manifest_digest_ck CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
 CONSTRAINT np_manifest_bytes_ck CHECK(octet_length(manifest) BETWEEN 2 AND 65536 AND manifest_sha256=encode(sha256(manifest),'hex')),
 CONSTRAINT np_manifest_witness_ck CHECK((envelope_sha256 IS NULL AND witness_sha256 IS NULL AND witness IS NULL) OR
 (envelope_sha256 IS NOT NULL AND witness_sha256 IS NOT NULL AND witness IS NOT NULL AND witness_sha256 ~ '^[0-9a-f]{64}$'
 AND octet_length(witness) BETWEEN 2 AND 4096 AND witness_sha256=encode(sha256(witness),'hex')))
);
CREATE TABLE __NP_SCHEMA__.np_context (
 context_sha256 text CONSTRAINT np_context_pkey PRIMARY KEY, context bytea NOT NULL,
 financial_context_sha256 text CONSTRAINT np_context_financial_fkey REFERENCES __NP_SCHEMA__.gw_snapshot(context_id),
 CONSTRAINT np_context_digest_ck CHECK(context_sha256 ~ '^[0-9a-f]{64}$'),
 CONSTRAINT np_context_bytes_ck CHECK(octet_length(context) BETWEEN 2 AND 65536 AND context_sha256=encode(sha256(context),'hex'))
);
CREATE TABLE __NP_SCHEMA__.np_registration (
 operation_id uuid CONSTRAINT np_registration_pkey PRIMARY KEY,
 request bytea NOT NULL,request_sha256 text NOT NULL,
 context_sha256 text NOT NULL CONSTRAINT np_registration_context_fkey REFERENCES __NP_SCHEMA__.np_context(context_sha256),
 response bytea NOT NULL,response_sha256 text NOT NULL,backend_pid integer NOT NULL,xid text NOT NULL,committed_at timestamptz NOT NULL,
 CONSTRAINT np_registration_request_ck CHECK(octet_length(request) BETWEEN 2 AND 65536 AND request_sha256 ~ '^[0-9a-f]{64}$' AND request_sha256=encode(sha256(request),'hex')),
 CONSTRAINT np_registration_response_ck CHECK(octet_length(response) BETWEEN 2 AND 65536 AND response_sha256 ~ '^[0-9a-f]{64}$' AND response_sha256=encode(sha256(response),'hex')),
 CONSTRAINT np_registration_origin_ck CHECK(backend_pid>0 AND length(xid)>0)
);
CREATE FUNCTION __NP_SCHEMA__.np_json(v jsonb,depth integer DEFAULT 0) RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,__NP_SCHEMA__,pg_temp AS $$
DECLARE result text;
BEGIN
 IF v IS NULL OR depth IS NULL OR depth NOT BETWEEN 0 AND 8 THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
 CASE jsonb_typeof(v)
 WHEN 'object' THEN SELECT '{'||COALESCE(string_agg(to_jsonb(key)::text||':'||__NP_SCHEMA__.np_json(value,depth+1),',' ORDER BY key COLLATE "C"),'')||'}' INTO result FROM jsonb_each(v);
 WHEN 'array' THEN SELECT '['||COALESCE(string_agg(__NP_SCHEMA__.np_json(value,depth+1),',' ORDER BY ord),'')||']' INTO result FROM jsonb_array_elements(v) WITH ORDINALITY a(value,ord);
 ELSE result:=v::text;
 END CASE;
 RETURN result;
END $$;
CREATE FUNCTION __NP_SCHEMA__.np_keys(v jsonb,keys text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,__NP_SCHEMA__,pg_temp AS $$
 SELECT COALESCE(jsonb_typeof(v)='object' AND v ?& keys AND (SELECT count(*) FROM jsonb_object_keys(v))=cardinality(keys),false)
$$;
CREATE FUNCTION __NP_SCHEMA__.np_caller(expected_role text) RETURNS void
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,__NP_SCHEMA__,pg_temp AS $$
DECLARE r pg_roles%ROWTYPE;
BEGIN
 IF expected_role NOT IN ('__NP_LOADER__','__NP_EXECUTOR__') OR session_user::text IS DISTINCT FROM expected_role OR current_setting('role') IS DISTINCT FROM 'none' THEN RAISE EXCEPTION 'NP_ROLE_REFUSED'; END IF;
 SELECT * INTO r FROM pg_roles WHERE rolname=expected_role;
 IF NOT FOUND OR NOT r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolbypassrls OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication
 OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid OR roleid=r.oid) THEN RAISE EXCEPTION 'NP_ROLE_REFUSED'; END IF;
END $$;
CREATE FUNCTION __NP_SCHEMA__.np_validate_bundle(context_b bytea,payloads bytea[],manifests bytea[],envelopes bytea[],witnesses bytea[]) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,__NP_SCHEMA__,pg_temp AS $$
DECLARE c jsonb;m jsonb;e jsonb;w jsonb;member jsonb;source jsonb;raw bytea;arr bytea[];kind integer;total bigint;lo integer;hi integer;
 last_sha text;k text;sort_key text;last_member text;keys text[];refs text[];source_ids text[];selected_sources text[];envelope_key text;witness_key text;
BEGIN
 IF context_b IS NULL OR octet_length(context_b) NOT BETWEEN 2 AND 65536 THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
 total:=octet_length(context_b);
 FOR kind IN 1..4 LOOP
  CASE kind WHEN 1 THEN arr:=payloads;lo:=0;hi:=65536; WHEN 2 THEN arr:=manifests;lo:=2;hi:=65536; WHEN 3 THEN arr:=envelopes;lo:=2;hi:=65536; ELSE arr:=witnesses;lo:=2;hi:=4096; END CASE;
  IF arr IS NULL OR cardinality(arr)>16 OR COALESCE(array_ndims(arr),1)<>1 OR cardinality(arr)>0 AND array_lower(arr,1)<>1 THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
  last_sha:=NULL;
  FOREACH raw IN ARRAY arr LOOP
   IF raw IS NULL OR octet_length(raw) NOT BETWEEN lo AND hi THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
   total:=total+octet_length(raw);k:=encode(sha256(raw),'hex');
   IF last_sha IS NOT NULL AND k COLLATE "C"<=last_sha COLLATE "C" THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
   last_sha:=k;
  END LOOP;
 END LOOP;
 IF total>4194304 THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
 c:=convert_from(context_b,'UTF8')::jsonb;
 IF NOT __NP_SCHEMA__.np_keys(c,ARRAY['schema','scope','state','promotable','source_admitted','financial_context_sha256','source_records','members']) OR c->>'schema' IS DISTINCT FROM 'finweb.synthetic_provenance_context/1' THEN RAISE EXCEPTION 'NP_UNSUPPORTED_PROVENANCE'; END IF;
 IF c->>'scope' IS DISTINCT FROM 'SYNTHETIC_TEST' OR c->>'state' IS DISTINCT FROM 'INTEGRITY_BOUND_NOT_ADMITTED' OR c->'promotable' IS DISTINCT FROM 'false'::jsonb OR c->'source_admitted' IS DISTINCT FROM 'false'::jsonb THEN RAISE EXCEPTION 'NP_SCOPE_REFUSED'; END IF;
 IF c->'financial_context_sha256'<>'null'::jsonb AND (jsonb_typeof(c->'financial_context_sha256')<>'string' OR c->>'financial_context_sha256' !~ '^[0-9a-f]{64}$') THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
 IF jsonb_typeof(c->'members') IS DISTINCT FROM 'array' OR jsonb_typeof(c->'source_records') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
 IF jsonb_array_length(c->'members') NOT BETWEEN 1 AND 16 OR jsonb_array_length(c->'source_records') NOT BETWEEN 1 AND 16 THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
 last_sha:=NULL;source_ids:=ARRAY[]::text[];
 FOR source IN SELECT value FROM jsonb_array_elements(c->'source_records') LOOP
  IF NOT (__NP_SCHEMA__.np_keys(source,ARRAY['source_id','name','upstream_provider','independence_group','terms_url','terms_check','synthetic']) OR __NP_SCHEMA__.np_keys(source,ARRAY['source_id','name','upstream_provider','independence_group','terms_url','terms_check','synthetic','source_priority'])) THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
  IF source->'synthetic' IS DISTINCT FROM 'true'::jsonb OR source->'terms_url' IS DISTINCT FROM 'null'::jsonb OR source->'terms_check' IS DISTINCT FROM 'null'::jsonb THEN RAISE EXCEPTION 'NP_SCOPE_REFUSED'; END IF;
  FOREACH k IN ARRAY ARRAY['source_id','name','upstream_provider','independence_group'] LOOP
   IF jsonb_typeof(source->k) IS DISTINCT FROM 'string' OR octet_length(source->>k) NOT BETWEEN 1 AND 128 THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
  END LOOP;
  IF source ? 'source_priority' AND (jsonb_typeof(source->'source_priority') IS DISTINCT FROM 'number' OR source->>'source_priority' !~ '^[1-9][0-9]*$' OR (source->>'source_priority')::numeric>9223372036854775807) THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
  k:=source->>'source_id';IF last_sha IS NOT NULL AND k COLLATE "C"<=last_sha COLLATE "C" THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
  source_ids:=array_append(source_ids,k);last_sha:=k;
 END LOOP;
 last_member:=NULL;selected_sources:=ARRAY[]::text[];
 FOR member IN SELECT value FROM jsonb_array_elements(c->'members') LOOP
  IF NOT __NP_SCHEMA__.np_keys(member,ARRAY['role','payload_sha256','manifest_sha256','envelope_sha256','witness_sha256']) THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
  IF jsonb_typeof(member->'role') IS DISTINCT FROM 'string' OR member->>'role' NOT IN ('QUOTE','FX','CORPORATE_ACTION','BENCHMARK','RISK_FREE','IDENTITY','CALENDAR','RESOLUTION_RECORD') THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
  FOREACH k IN ARRAY ARRAY['payload_sha256','manifest_sha256'] LOOP
   IF jsonb_typeof(member->k) IS DISTINCT FROM 'string' OR member->>k !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
  END LOOP;
  envelope_key:=member->>'envelope_sha256';witness_key:=member->>'witness_sha256';
  IF (envelope_key IS NULL)<>(witness_key IS NULL) OR envelope_key IS NOT NULL AND (envelope_key !~ '^[0-9a-f]{64}$' OR witness_key !~ '^[0-9a-f]{64}$') THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
  sort_key:=(member->>'role')||':'||(member->>'payload_sha256')||':'||(member->>'manifest_sha256')||':'||COALESCE(envelope_key,'')||':'||COALESCE(witness_key,'');
  IF last_member IS NOT NULL AND sort_key COLLATE "C"<=last_member COLLATE "C" THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;last_member:=sort_key;
  SELECT b INTO raw FROM unnest(manifests) b WHERE encode(sha256(b),'hex')=member->>'manifest_sha256';
  IF NOT FOUND THEN RAISE EXCEPTION 'NP_INPUT_MISSING'; END IF;m:=convert_from(raw,'UTF8')::jsonb;
  IF m->>'schema'='finweb.marketdata.file_manifest/2' THEN IF NOT __NP_SCHEMA__.np_keys(m,ARRAY['schema','file_sha256','size_bytes','payload_filename','payload_format','source_id','data_kind','market','retrieval_time','retrieved_by','request','declared_adjustment','adjustment_anchor','declared_currency','declared_delay','source_identifiers','script','libraries','usage_scope','coverage']||ARRAY['acquisition']) OR NOT __NP_SCHEMA__.np_keys(m->'acquisition',ARRAY['schema','envelope_sha256']) OR m->'acquisition'->>'schema' IS DISTINCT FROM 'finweb.marketdata.acquisition_ref/1' THEN RAISE EXCEPTION 'NP_SHAPE';END IF;
  ELSIF m->>'schema'='finweb.marketdata.file_manifest/1' THEN IF NOT __NP_SCHEMA__.np_keys(m,ARRAY['schema','file_sha256','size_bytes','payload_filename','payload_format','source_id','data_kind','market','retrieval_time','retrieved_by','request','declared_adjustment','adjustment_anchor','declared_currency','declared_delay','source_identifiers','script','libraries','usage_scope','coverage']) THEN RAISE EXCEPTION 'NP_SHAPE';END IF;
  ELSE RAISE EXCEPTION 'NP_UNSUPPORTED_PROVENANCE';END IF;
  SELECT b INTO raw FROM unnest(payloads) b WHERE encode(sha256(b),'hex')=member->>'payload_sha256';
  IF NOT FOUND THEN RAISE EXCEPTION 'NP_INPUT_MISSING'; END IF;
  IF m->>'file_sha256' IS DISTINCT FROM member->>'payload_sha256' OR m->>'data_kind' IS DISTINCT FROM member->>'role' OR m->'size_bytes' IS DISTINCT FROM to_jsonb(octet_length(raw)) THEN RAISE EXCEPTION 'NP_BINDING_DIFFERS'; END IF;
  selected_sources:=array_append(selected_sources,m->>'source_id');
  IF m->>'schema'='finweb.marketdata.file_manifest/2' THEN
   IF envelope_key IS NULL OR m->>'retrieved_by' IS DISTINCT FROM 'agent' OR m->>'usage_scope' IS DISTINCT FROM 'INTERNAL_DEVELOPMENT_ONLY' OR m->'acquisition'->>'envelope_sha256' IS DISTINCT FROM envelope_key THEN RAISE EXCEPTION 'NP_SCOPE_REFUSED'; END IF;
   SELECT b INTO raw FROM unnest(envelopes) b WHERE encode(sha256(b),'hex')=envelope_key;
   IF NOT FOUND THEN RAISE EXCEPTION 'NP_INPUT_MISSING'; END IF;e:=convert_from(raw,'UTF8')::jsonb;
   IF NOT __NP_SCHEMA__.np_keys(e,ARRAY['schema','actor','authorization','tool','request','attempt','result','evidence','visibility']) THEN RAISE EXCEPTION 'NP_SHAPE';END IF;
   SELECT b INTO raw FROM unnest(witnesses) b WHERE encode(sha256(b),'hex')=witness_key;
   IF NOT FOUND THEN RAISE EXCEPTION 'NP_INPUT_MISSING'; END IF;w:=convert_from(raw,'UTF8')::jsonb;
   IF NOT __NP_SCHEMA__.np_keys(w,ARRAY['expected_envelope_sha256','expected_manifest_sha256','actor_agent_id','actor_role','approved_full_request_sha256']) THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
   IF e->>'schema' IS DISTINCT FROM 'finweb.marketdata.acquisition_envelope/1' OR w->>'expected_envelope_sha256' IS DISTINCT FROM envelope_key OR w->>'expected_manifest_sha256' IS DISTINCT FROM member->>'manifest_sha256'
    OR e->'actor'->>'agent_id' IS DISTINCT FROM w->>'actor_agent_id' OR e->'actor'->>'role' IS DISTINCT FROM w->>'actor_role' OR e->'request'->>'sha256' IS DISTINCT FROM w->>'approved_full_request_sha256'
    OR e->'result'->>'payload_sha256' IS DISTINCT FROM member->>'payload_sha256' OR e->'result'->'size_bytes' IS DISTINCT FROM m->'size_bytes'
    OR e->'result'->>'retrieved_at' IS DISTINCT FROM m->>'retrieval_time' OR e->'request'->>'source_id' IS DISTINCT FROM m->>'source_id'
    OR e->'request'->'parameters' IS DISTINCT FROM m->'request' OR m->'script' IS DISTINCT FROM jsonb_build_object('name',e->'tool'->'name','version',e->'tool'->'version','script_sha256',e->'tool'->'sha256') THEN RAISE EXCEPTION 'NP_BINDING_DIFFERS'; END IF;
  ELSIF m->>'schema'='finweb.marketdata.file_manifest/1' THEN
   IF envelope_key IS NOT NULL OR m->>'retrieved_by' IS DISTINCT FROM 'synthetic' OR m->>'usage_scope' IS DISTINCT FROM 'SYNTHETIC_TEST' THEN RAISE EXCEPTION 'NP_SCOPE_REFUSED'; END IF;
  ELSE RAISE EXCEPTION 'NP_UNSUPPORTED_PROVENANCE';END IF;
 END LOOP;
 SELECT array_agg(DISTINCT x ORDER BY x) INTO selected_sources FROM unnest(selected_sources) x;
 IF source_ids IS DISTINCT FROM selected_sources THEN RAISE EXCEPTION 'NP_BINDING_DIFFERS'; END IF;
 FOR kind IN 1..4 LOOP
  CASE kind WHEN 1 THEN arr:=payloads;k:='payload_sha256';WHEN 2 THEN arr:=manifests;k:='manifest_sha256';WHEN 3 THEN arr:=envelopes;k:='envelope_sha256';ELSE arr:=witnesses;k:='witness_sha256';END CASE;
  SELECT COALESCE(array_agg(encode(sha256(b),'hex') ORDER BY encode(sha256(b),'hex') COLLATE "C"),ARRAY[]::text[]) INTO keys FROM unnest(arr) b;
  SELECT COALESCE(array_agg(DISTINCT value->>k ORDER BY value->>k),ARRAY[]::text[]) INTO refs FROM jsonb_array_elements(c->'members') WHERE value->>k IS NOT NULL;
  IF keys IS DISTINCT FROM refs THEN RAISE EXCEPTION 'NP_BINDING_DIFFERS'; END IF;
 END LOOP;
EXCEPTION WHEN data_exception THEN RAISE EXCEPTION 'NP_SHAPE';
END $$;
CREATE FUNCTION __NP_SCHEMA__.np_collect_context(context_sha text,op uuid)
RETURNS TABLE(context_b bytea,payloads bytea[],manifests bytea[],envelopes bytea[],witnesses bytea[],registration_response bytea)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,__NP_SCHEMA__,pg_temp AS $$
DECLARE c jsonb;q jsonb;r __NP_SCHEMA__.np_registration%ROWTYPE;k text;expected bytea;
BEGIN
 IF (context_sha IS NULL)=(op IS NULL) OR context_sha IS NOT NULL AND context_sha !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
 IF op IS NOT NULL THEN
  SELECT * INTO r FROM __NP_SCHEMA__.np_registration WHERE operation_id=op;IF NOT FOUND THEN RETURN;END IF;context_sha:=r.context_sha256;
 END IF;
 SELECT x.context INTO context_b FROM __NP_SCHEMA__.np_context x WHERE x.context_sha256=context_sha;IF NOT FOUND THEN RETURN;END IF;
 IF encode(sha256(context_b),'hex') IS DISTINCT FROM context_sha THEN RAISE EXCEPTION 'NP_BINDING_DIFFERS'; END IF;c:=convert_from(context_b,'UTF8')::jsonb;
 IF c->>'financial_context_sha256' IS DISTINCT FROM (SELECT x.financial_context_sha256 FROM __NP_SCHEMA__.np_context x WHERE x.context_sha256=context_sha) THEN RAISE EXCEPTION 'NP_CONTEXT_DIFFERS'; END IF;
 SELECT COALESCE(array_agg(x.payload ORDER BY x.payload_sha256 COLLATE "C"),ARRAY[]::bytea[]) INTO payloads FROM __NP_SCHEMA__.np_payload x WHERE x.payload_sha256 IN (SELECT value->>'payload_sha256' FROM jsonb_array_elements(c->'members'));
 SELECT COALESCE(array_agg(x.manifest ORDER BY x.manifest_sha256 COLLATE "C"),ARRAY[]::bytea[]) INTO manifests FROM __NP_SCHEMA__.np_manifest x WHERE x.manifest_sha256 IN (SELECT value->>'manifest_sha256' FROM jsonb_array_elements(c->'members'));
 SELECT COALESCE(array_agg(x.envelope ORDER BY x.envelope_sha256 COLLATE "C"),ARRAY[]::bytea[]) INTO envelopes FROM __NP_SCHEMA__.np_acquisition x WHERE x.envelope_sha256 IN (SELECT value->>'envelope_sha256' FROM jsonb_array_elements(c->'members'));
 SELECT COALESCE(array_agg(x.witness ORDER BY x.witness_sha256 COLLATE "C"),ARRAY[]::bytea[]) INTO witnesses FROM (SELECT DISTINCT witness_sha256,witness FROM __NP_SCHEMA__.np_manifest WHERE manifest_sha256 IN (SELECT value->>'manifest_sha256' FROM jsonb_array_elements(c->'members')) AND witness_sha256 IS NOT NULL) x;
 PERFORM __NP_SCHEMA__.np_validate_bundle(context_b,payloads,manifests,envelopes,witnesses);
 IF EXISTS(SELECT 1 FROM __NP_SCHEMA__.np_manifest x JOIN jsonb_array_elements(c->'members') a ON x.manifest_sha256=a.value->>'manifest_sha256' WHERE x.payload_sha256 IS DISTINCT FROM a.value->>'payload_sha256' OR x.envelope_sha256 IS DISTINCT FROM a.value->>'envelope_sha256' OR x.witness_sha256 IS DISTINCT FROM a.value->>'witness_sha256') THEN RAISE EXCEPTION 'NP_BINDING_DIFFERS'; END IF;
 IF op IS NOT NULL THEN
  q:=convert_from(r.request,'UTF8')::jsonb;
  IF NOT __NP_SCHEMA__.np_keys(q,ARRAY['schema','scope','operation_id','context_sha256','payload_sha256s','manifest_sha256s','envelope_sha256s','witness_sha256s']) OR q->>'schema' IS DISTINCT FROM 'finweb.synthetic_provenance_registration/1' OR q->>'scope' IS DISTINCT FROM 'SYNTHETIC_TEST' OR q->>'operation_id' IS DISTINCT FROM op::text OR q->>'context_sha256' IS DISTINCT FROM context_sha OR encode(sha256(r.request),'hex') IS DISTINCT FROM r.request_sha256 THEN RAISE EXCEPTION 'NP_BINDING_DIFFERS'; END IF;
  FOREACH k IN ARRAY ARRAY['payload','manifest','envelope','witness'] LOOP
   IF q->(k||'_sha256s') IS DISTINCT FROM (SELECT COALESCE(jsonb_agg(DISTINCT value->(k||'_sha256') ORDER BY value->(k||'_sha256')),'[]'::jsonb) FROM jsonb_array_elements(c->'members') WHERE value->>(k||'_sha256') IS NOT NULL) THEN RAISE EXCEPTION 'NP_BINDING_DIFFERS'; END IF;
  END LOOP;
  expected:=convert_to(__NP_SCHEMA__.np_json(jsonb_build_object('schema','finweb.synthetic_provenance_registration_result/1','scope','SYNTHETIC_TEST','state','INTEGRITY_BOUND_NOT_ADMITTED','promotable',false,'source_admitted',false,'operation_id',op::text,'request_sha256',r.request_sha256,'context_sha256',context_sha,'payload_count',cardinality(payloads),'manifest_count',cardinality(manifests),'envelope_count',cardinality(envelopes),'member_count',jsonb_array_length(c->'members'))),'UTF8');
  IF r.response IS DISTINCT FROM expected OR encode(sha256(r.response),'hex') IS DISTINCT FROM r.response_sha256 THEN RAISE EXCEPTION 'NP_BINDING_DIFFERS'; END IF;registration_response:=r.response;
 ELSE registration_response:=NULL;END IF;
 RETURN NEXT;
EXCEPTION WHEN data_exception THEN RAISE EXCEPTION 'NP_SHAPE';
END $$;
CREATE FUNCTION __NP_SCHEMA__.np_guard(purpose text) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__NP_SCHEMA__,pg_temp AS $$
DECLARE m text;l __NP_SCHEMA__.gw_lease%ROWTYPE;h __NP_SCHEMA__.gw_head%ROWTYPE;r __NP_SCHEMA__.gw_root%ROWTYPE;
BEGIN
 IF purpose IS NULL OR purpose NOT IN ('EXECUTE_CREATE','ARCHIVE_READ','ARCHIVE_EXPORT','EXECUTE_REPRODUCE') THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'F2_ISOLATION'; END IF;
 SELECT mode INTO m FROM __NP_SCHEMA__.gw_mode WHERE singleton FOR SHARE;
 IF m IS DISTINCT FROM 'FICTIONAL_ONLY' THEN RAISE EXCEPTION 'F2_MODE_HOLD'; END IF;
 SELECT * INTO l FROM __NP_SCHEMA__.gw_lease WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text;
 IF NOT FOUND THEN RAISE EXCEPTION 'NP_LEASE_REQUIRED'; END IF;
 IF l.purpose IS DISTINCT FROM purpose OR purpose='EXECUTE_CREATE' AND l.phase NOT IN ('OPEN','SEALED','REPLAY') OR purpose<>'EXECUTE_CREATE' AND l.phase IS DISTINCT FROM 'READONLY' THEN RAISE EXCEPTION 'F2_SCOPE_DIFFERS'; END IF;
 SELECT * INTO h FROM __NP_SCHEMA__.gw_head WHERE context_id=l.context_id FOR SHARE;
 IF NOT FOUND OR h.generation IS DISTINCT FROM l.generation THEN RAISE EXCEPTION 'F2_GENERATION_DIFFERS'; END IF;
 IF h.expiry IS DISTINCT FROM 'NONE' THEN RAISE EXCEPTION 'F2_EXPIRY_HOLD'; END IF;
 IF NOT __NP_SCHEMA__.gw_rights_valid(h.rights) OR NOT COALESCE((h.rights->>'ARCHIVE_READ')::boolean,false) OR NOT COALESCE((h.rights->>purpose)::boolean,false) THEN RAISE EXCEPTION 'F2_RIGHT_REFUSED'; END IF;
 SELECT * INTO r FROM __NP_SCHEMA__.gw_root WHERE root_id=l.root_id;
 IF NOT FOUND OR r.owner_id IS DISTINCT FROM l.owner_id OR r.context_id IS DISTINCT FROM l.context_id OR l.generation<1 THEN RAISE EXCEPTION 'F2_NOT_FOUND'; END IF;
END $$;
CREATE FUNCTION __NP_SCHEMA__.np_immutable() RETURNS trigger
LANGUAGE plpgsql VOLATILE SET search_path=pg_catalog,__NP_SCHEMA__,pg_temp AS $$ BEGIN RAISE EXCEPTION 'NP_STORAGE_CONFLICT'; END $$;
CREATE FUNCTION __NP_SCHEMA__.np_put_context(op uuid,request_b bytea,context_b bytea,payloads bytea[],manifests bytea[],envelopes bytea[],witnesses bytea[]) RETURNS bytea
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__NP_SCHEMA__,pg_temp AS $$
DECLARE c jsonb;q jsonb;m jsonb;b bytea;prior_b bytea;k text;wkey text;wraw bytea;cs text;rs text;result bytea;r __NP_SCHEMA__.np_registration%ROWTYPE;arr bytea[];kind integer;req_keys jsonb;prior_record record;
BEGIN
 PERFORM __NP_SCHEMA__.np_caller('__NP_LOADER__');
 IF op IS NULL OR request_b IS NULL OR octet_length(request_b) NOT BETWEEN 2 AND 65536 THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
 PERFORM __NP_SCHEMA__.np_validate_bundle(context_b,payloads,manifests,envelopes,witnesses);
 c:=convert_from(context_b,'UTF8')::jsonb;cs:=encode(sha256(context_b),'hex');q:=convert_from(request_b,'UTF8')::jsonb;rs:=encode(sha256(request_b),'hex');
 IF NOT __NP_SCHEMA__.np_keys(q,ARRAY['schema','scope','operation_id','context_sha256','payload_sha256s','manifest_sha256s','envelope_sha256s','witness_sha256s']) OR q->>'schema' IS DISTINCT FROM 'finweb.synthetic_provenance_registration/1' OR q->>'scope' IS DISTINCT FROM 'SYNTHETIC_TEST' OR q->>'operation_id' IS DISTINCT FROM op::text OR q->>'context_sha256' IS DISTINCT FROM cs THEN RAISE EXCEPTION 'NP_SHAPE'; END IF;
 FOR kind IN 1..4 LOOP
  CASE kind WHEN 1 THEN arr:=payloads;k:='payload';WHEN 2 THEN arr:=manifests;k:='manifest';WHEN 3 THEN arr:=envelopes;k:='envelope';ELSE arr:=witnesses;k:='witness';END CASE;
  SELECT COALESCE(jsonb_agg(encode(sha256(x),'hex') ORDER BY encode(sha256(x),'hex') COLLATE "C"),'[]'::jsonb) INTO req_keys FROM unnest(arr) x;
  IF q->(k||'_sha256s') IS DISTINCT FROM req_keys THEN RAISE EXCEPTION 'NP_BINDING_DIFFERS'; END IF;
 END LOOP;
 PERFORM pg_advisory_xact_lock(hashtextextended('finweb.n2a.register:'||'__NP_SCHEMA__',0));
 SELECT * INTO r FROM __NP_SCHEMA__.np_registration WHERE operation_id=op;
 IF FOUND THEN
  IF r.request IS DISTINCT FROM request_b OR r.context_sha256 IS DISTINCT FROM cs THEN RAISE EXCEPTION 'NP_OPERATION_CONFLICT'; END IF;
  SELECT * INTO prior_record FROM __NP_SCHEMA__.np_collect_context(NULL,op);
  IF NOT FOUND THEN RAISE EXCEPTION 'NP_INPUT_MISSING'; END IF;RETURN prior_record.registration_response;
 END IF;
 IF (SELECT count(*) FROM __NP_SCHEMA__.np_registration)>=4096 OR (SELECT count(*) FROM __NP_SCHEMA__.np_context)+(CASE WHEN EXISTS(SELECT 1 FROM __NP_SCHEMA__.np_context WHERE context_sha256=cs) THEN 0 ELSE 1 END)>1024
 OR (SELECT count(*) FROM __NP_SCHEMA__.np_payload)+(SELECT count(*) FROM unnest(payloads) x WHERE NOT EXISTS(SELECT 1 FROM __NP_SCHEMA__.np_payload WHERE payload_sha256=encode(sha256(x),'hex')))>16384
 OR (SELECT count(*) FROM __NP_SCHEMA__.np_acquisition)+(SELECT count(*) FROM unnest(envelopes) x WHERE NOT EXISTS(SELECT 1 FROM __NP_SCHEMA__.np_acquisition WHERE envelope_sha256=encode(sha256(x),'hex')))>16384
 OR (SELECT count(*) FROM __NP_SCHEMA__.np_manifest)+(SELECT count(*) FROM unnest(manifests) x WHERE NOT EXISTS(SELECT 1 FROM __NP_SCHEMA__.np_manifest WHERE manifest_sha256=encode(sha256(x),'hex')))>16384 THEN RAISE EXCEPTION 'NP_CAPACITY'; END IF;
 FOREACH b IN ARRAY payloads LOOP
  k:=encode(sha256(b),'hex');SELECT x.payload INTO prior_b FROM __NP_SCHEMA__.np_payload x WHERE x.payload_sha256=k;
  IF FOUND THEN IF prior_b IS DISTINCT FROM b THEN RAISE EXCEPTION 'NP_STORAGE_CONFLICT';END IF; ELSE INSERT INTO __NP_SCHEMA__.np_payload VALUES(k,octet_length(b),b);END IF;
 END LOOP;
 FOREACH b IN ARRAY envelopes LOOP
  k:=encode(sha256(b),'hex');SELECT x.envelope INTO prior_b FROM __NP_SCHEMA__.np_acquisition x WHERE x.envelope_sha256=k;
  IF FOUND THEN IF prior_b IS DISTINCT FROM b THEN RAISE EXCEPTION 'NP_STORAGE_CONFLICT';END IF; ELSE INSERT INTO __NP_SCHEMA__.np_acquisition VALUES(k,b);END IF;
 END LOOP;
 FOREACH b IN ARRAY manifests LOOP
  k:=encode(sha256(b),'hex');m:=convert_from(b,'UTF8')::jsonb;SELECT a.value->>'witness_sha256' INTO wkey FROM jsonb_array_elements(c->'members') a WHERE a.value->>'manifest_sha256'=k;
  wraw:=NULL;IF wkey IS NOT NULL THEN SELECT x INTO wraw FROM unnest(witnesses) x WHERE encode(sha256(x),'hex')=wkey;END IF;
  SELECT x.manifest INTO prior_b FROM __NP_SCHEMA__.np_manifest x WHERE x.manifest_sha256=k;
  IF FOUND THEN
   IF prior_b IS DISTINCT FROM b OR NOT EXISTS(SELECT 1 FROM __NP_SCHEMA__.np_manifest x WHERE x.manifest_sha256=k AND x.payload_sha256=m->>'file_sha256' AND x.envelope_sha256 IS NOT DISTINCT FROM m->'acquisition'->>'envelope_sha256' AND x.witness_sha256 IS NOT DISTINCT FROM wkey AND x.witness IS NOT DISTINCT FROM wraw) THEN RAISE EXCEPTION 'NP_STORAGE_CONFLICT';END IF;
  ELSE INSERT INTO __NP_SCHEMA__.np_manifest VALUES(k,b,m->>'file_sha256',m->'acquisition'->>'envelope_sha256',wkey,wraw);END IF;
 END LOOP;
 SELECT x.context INTO prior_b FROM __NP_SCHEMA__.np_context x WHERE x.context_sha256=cs;
 IF FOUND THEN IF prior_b IS DISTINCT FROM context_b THEN RAISE EXCEPTION 'NP_CONTEXT_DIFFERS';END IF;ELSE INSERT INTO __NP_SCHEMA__.np_context VALUES(cs,context_b,c->>'financial_context_sha256');END IF;
 result:=convert_to(__NP_SCHEMA__.np_json(jsonb_build_object('schema','finweb.synthetic_provenance_registration_result/1','scope','SYNTHETIC_TEST','state','INTEGRITY_BOUND_NOT_ADMITTED','promotable',false,'source_admitted',false,'operation_id',op::text,'request_sha256',rs,'context_sha256',cs,'payload_count',cardinality(payloads),'manifest_count',cardinality(manifests),'envelope_count',cardinality(envelopes),'member_count',jsonb_array_length(c->'members'))),'UTF8');
 INSERT INTO __NP_SCHEMA__.np_registration VALUES(op,request_b,rs,cs,result,encode(sha256(result),'hex'),pg_backend_pid(),pg_current_xact_id()::text,clock_timestamp());
 RETURN result;
EXCEPTION WHEN data_exception THEN RAISE EXCEPTION 'NP_SHAPE';WHEN foreign_key_violation THEN RAISE EXCEPTION 'NP_INPUT_MISSING';
END $$;
CREATE FUNCTION __NP_SCHEMA__.np_get_context(context_sha text,op uuid)
RETURNS TABLE(context_b bytea,payloads bytea[],manifests bytea[],envelopes bytea[],witnesses bytea[],registration_response bytea)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,__NP_SCHEMA__,pg_temp AS $$
BEGIN PERFORM __NP_SCHEMA__.np_caller('__NP_LOADER__');RETURN QUERY SELECT * FROM __NP_SCHEMA__.np_collect_context(context_sha,op);END $$;
CREATE FUNCTION __NP_SCHEMA__.np_load_context(context_sha text,purpose text)
RETURNS TABLE(context_b bytea,payloads bytea[],manifests bytea[],envelopes bytea[],witnesses bytea[],registration_response bytea)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__NP_SCHEMA__,pg_temp AS $$
DECLARE l __NP_SCHEMA__.gw_lease%ROWTYPE;f text;
BEGIN
 PERFORM __NP_SCHEMA__.np_caller('__NP_EXECUTOR__');
 IF context_sha IS NULL OR context_sha !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'NP_SHAPE';END IF;
 PERFORM __NP_SCHEMA__.np_guard(purpose);
 SELECT * INTO l FROM __NP_SCHEMA__.gw_lease WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text;
 SELECT x.financial_context_sha256 INTO f FROM __NP_SCHEMA__.np_context x WHERE x.context_sha256=context_sha;
 IF NOT FOUND THEN RETURN;END IF;
 IF f IS NULL OR f IS DISTINCT FROM l.context_id THEN RAISE EXCEPTION 'NP_CONTEXT_DIFFERS';END IF;
 RETURN QUERY SELECT * FROM __NP_SCHEMA__.np_collect_context(context_sha,NULL);
END $$;
CREATE TRIGGER np_payload_immutable_rows BEFORE UPDATE OR DELETE ON __NP_SCHEMA__.np_payload FOR EACH ROW EXECUTE FUNCTION __NP_SCHEMA__.np_immutable();
CREATE TRIGGER np_payload_immutable_truncate BEFORE TRUNCATE ON __NP_SCHEMA__.np_payload FOR EACH STATEMENT EXECUTE FUNCTION __NP_SCHEMA__.np_immutable();
CREATE TRIGGER np_acquisition_immutable_rows BEFORE UPDATE OR DELETE ON __NP_SCHEMA__.np_acquisition FOR EACH ROW EXECUTE FUNCTION __NP_SCHEMA__.np_immutable();
CREATE TRIGGER np_acquisition_immutable_truncate BEFORE TRUNCATE ON __NP_SCHEMA__.np_acquisition FOR EACH STATEMENT EXECUTE FUNCTION __NP_SCHEMA__.np_immutable();
CREATE TRIGGER np_manifest_immutable_rows BEFORE UPDATE OR DELETE ON __NP_SCHEMA__.np_manifest FOR EACH ROW EXECUTE FUNCTION __NP_SCHEMA__.np_immutable();
CREATE TRIGGER np_manifest_immutable_truncate BEFORE TRUNCATE ON __NP_SCHEMA__.np_manifest FOR EACH STATEMENT EXECUTE FUNCTION __NP_SCHEMA__.np_immutable();
CREATE TRIGGER np_context_immutable_rows BEFORE UPDATE OR DELETE ON __NP_SCHEMA__.np_context FOR EACH ROW EXECUTE FUNCTION __NP_SCHEMA__.np_immutable();
CREATE TRIGGER np_context_immutable_truncate BEFORE TRUNCATE ON __NP_SCHEMA__.np_context FOR EACH STATEMENT EXECUTE FUNCTION __NP_SCHEMA__.np_immutable();
CREATE TRIGGER np_registration_immutable_rows BEFORE UPDATE OR DELETE ON __NP_SCHEMA__.np_registration FOR EACH ROW EXECUTE FUNCTION __NP_SCHEMA__.np_immutable();
CREATE TRIGGER np_registration_immutable_truncate BEFORE TRUNCATE ON __NP_SCHEMA__.np_registration FOR EACH STATEMENT EXECUTE FUNCTION __NP_SCHEMA__.np_immutable();
REVOKE ALL ON FUNCTION __NP_SCHEMA__.np_json(jsonb,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION __NP_SCHEMA__.np_keys(jsonb,text[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION __NP_SCHEMA__.np_caller(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION __NP_SCHEMA__.np_validate_bundle(bytea,bytea[],bytea[],bytea[],bytea[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION __NP_SCHEMA__.np_collect_context(text,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION __NP_SCHEMA__.np_guard(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION __NP_SCHEMA__.np_immutable() FROM PUBLIC;
REVOKE ALL ON FUNCTION __NP_SCHEMA__.np_put_context(uuid,bytea,bytea,bytea[],bytea[],bytea[],bytea[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION __NP_SCHEMA__.np_get_context(text,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION __NP_SCHEMA__.np_load_context(text,text) FROM PUBLIC;
REVOKE ALL ON TABLE __NP_SCHEMA__.np_payload,__NP_SCHEMA__.np_acquisition,__NP_SCHEMA__.np_manifest,__NP_SCHEMA__.np_context,__NP_SCHEMA__.np_registration FROM PUBLIC;
GRANT USAGE ON SCHEMA __NP_SCHEMA__ TO __NP_LOADER__;
GRANT EXECUTE ON FUNCTION __NP_SCHEMA__.np_put_context(uuid,bytea,bytea,bytea[],bytea[],bytea[],bytea[]),__NP_SCHEMA__.np_get_context(text,uuid) TO __NP_LOADER__;
GRANT EXECUTE ON FUNCTION __NP_SCHEMA__.np_load_context(text,text) TO __NP_EXECUTOR__;
