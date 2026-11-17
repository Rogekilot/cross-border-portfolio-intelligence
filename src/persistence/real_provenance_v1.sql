-- F1 R2: the real gateway's CANDIDATE REGISTRY (implementation/CP7_F1_REAL_PATH_DESIGN.md sections 3.3, 4.1, 4.2): N2a generalised to the
-- three scopes and re-targeted from the F2 gateway (gw_*) to the real gateway's objects (rw_*). Installed by the installer AFTER
-- real_workspace_v1.sql, in the same transaction, with the same four validated identifiers (__RW_SCHEMA__ / __RW_EXECUTOR__ /
-- __RW_LOADER__ / __RW_PUBLISHER__). Nothing here is a migration or a startup hook.
--
-- WHAT IT HOLDS. Five append-only tables of CANDIDATE bytes (payloads, acquisition envelopes, manifests, contexts, registrations) and the
-- functions that put, get and guarded-load them. A candidate is stored, never admitted: state INTEGRITY_BOUND_NOT_ADMITTED, promotable
-- false, source_admitted false. Nothing in the gateway or in any md_* table references a candidate ("candidates immutable and
-- unreferenced"); the only foreign key that touches the registry points FROM it, to rw_snapshot, for a context-bound registration.
--
-- WHO MAY CALL WHAT.
--   loader    rwp_put_context, rwp_get_context   (granted by the shared installer code, persistence/real_roles.py, not by this file)
--   executor  rwp_load_context                   (the guarded load, below; granted here)
--   nobody    every other rwp_ function. rw_publish (the owner's definer function) calls rwp_origin_failures.
-- Every function pins its search_path with pg_temp last and builds no dynamic SQL.
--
-- THE THREE SCOPES (design 4.2). The context names its scope. In a TEST scope every source is synthetic and no attestation is stored
-- (I1); in the REAL scope the origin predicates O1 to O3 (rwp_origin) must all hold or the candidate is refused with every failed code
-- (RW_PROV_ORIGIN_REFUSED, DETAIL lists them). The install kind decides which scopes this database may hold (rw_scope_allowed).
--
-- BINDING (design 3.3 item 1). A registration may be UNBOUND (financial_context_sha256 null: the qualification run registers it before the
-- publish) or BOUND to a published context: the column references rw_snapshot(context_id), so a bound registration before the publish is
-- refused (RW_PROV_INPUT_MISSING), and after it the bundle's members must be exactly the snapshot's. The executor's guarded load returns
-- only a registration bound to the context of its own lease. So the loader registers the context-bound bundle AFTER the publish.
--
-- THE LOADER AND LOGIN. The install check (persistence/real_provenance_store.py) accepts a loader with or without LOGIN. Every call of
-- rwp_put_context / rwp_get_context checks that the caller's role CAN log in (rwp_caller): once the owner sets the loader NOLOGIN
-- (PD-0070 decision 1), a session that was already open is refused here too. That narrows the registry's reach only; it does not end the
-- session and it does not stop its md_* INSERTs.
--
-- ADVISORY LOCKS. The one exclusive lock this file takes is masked below 2^62, outside the lease-marker key space reserved at the top
-- of real_workspace_v1.sql.

CREATE TABLE __RW_SCHEMA__.rwp_payload (
 payload_sha256 text CONSTRAINT rwp_payload_pkey PRIMARY KEY,
 size_bytes bigint NOT NULL, payload bytea NOT NULL,
 CONSTRAINT rwp_payload_digest_ck CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
 CONSTRAINT rwp_payload_size_ck CHECK(size_bytes BETWEEN 0 AND 65536),
 CONSTRAINT rwp_payload_bytes_ck CHECK(size_bytes=octet_length(payload) AND payload_sha256=encode(sha256(payload),'hex'))
);
CREATE TABLE __RW_SCHEMA__.rwp_acquisition (
 envelope_sha256 text CONSTRAINT rwp_acquisition_pkey PRIMARY KEY, envelope bytea NOT NULL,
 CONSTRAINT rwp_acquisition_digest_ck CHECK(envelope_sha256 ~ '^[0-9a-f]{64}$'),
 CONSTRAINT rwp_acquisition_bytes_ck CHECK(octet_length(envelope) BETWEEN 2 AND 65536 AND envelope_sha256=encode(sha256(envelope),'hex'))
);
CREATE TABLE __RW_SCHEMA__.rwp_manifest (
 manifest_sha256 text CONSTRAINT rwp_manifest_pkey PRIMARY KEY, manifest bytea NOT NULL,
 payload_sha256 text NOT NULL CONSTRAINT rwp_manifest_payload_fkey REFERENCES __RW_SCHEMA__.rwp_payload(payload_sha256),
 envelope_sha256 text CONSTRAINT rwp_manifest_envelope_fkey REFERENCES __RW_SCHEMA__.rwp_acquisition(envelope_sha256),
 witness_sha256 text, witness bytea,
 CONSTRAINT rwp_manifest_digest_ck CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
 CONSTRAINT rwp_manifest_bytes_ck CHECK(octet_length(manifest) BETWEEN 2 AND 65536 AND manifest_sha256=encode(sha256(manifest),'hex')),
 CONSTRAINT rwp_manifest_witness_ck CHECK((envelope_sha256 IS NULL AND witness_sha256 IS NULL AND witness IS NULL) OR
 (envelope_sha256 IS NOT NULL AND witness_sha256 IS NOT NULL AND witness IS NOT NULL AND witness_sha256 ~ '^[0-9a-f]{64}$'
 AND octet_length(witness) BETWEEN 2 AND 4096 AND witness_sha256=encode(sha256(witness),'hex')))
);
CREATE TABLE __RW_SCHEMA__.rwp_context (
 context_sha256 text CONSTRAINT rwp_context_pkey PRIMARY KEY, context bytea NOT NULL,
 financial_context_sha256 text CONSTRAINT rwp_context_financial_fkey REFERENCES __RW_SCHEMA__.rw_snapshot(context_id),
 CONSTRAINT rwp_context_digest_ck CHECK(context_sha256 ~ '^[0-9a-f]{64}$'),
 CONSTRAINT rwp_context_bytes_ck CHECK(octet_length(context) BETWEEN 2 AND 65536 AND context_sha256=encode(sha256(context),'hex'))
);
CREATE TABLE __RW_SCHEMA__.rwp_registration (
 operation_id uuid CONSTRAINT rwp_registration_pkey PRIMARY KEY,
 request bytea NOT NULL,request_sha256 text NOT NULL,
 context_sha256 text NOT NULL CONSTRAINT rwp_registration_context_fkey REFERENCES __RW_SCHEMA__.rwp_context(context_sha256),
 response bytea NOT NULL,response_sha256 text NOT NULL,backend_pid integer NOT NULL,xid text NOT NULL,committed_at timestamptz NOT NULL,
 CONSTRAINT rwp_registration_request_ck CHECK(octet_length(request) BETWEEN 2 AND 65536 AND request_sha256 ~ '^[0-9a-f]{64}$' AND request_sha256=encode(sha256(request),'hex')),
 CONSTRAINT rwp_registration_response_ck CHECK(octet_length(response) BETWEEN 2 AND 65536 AND response_sha256 ~ '^[0-9a-f]{64}$' AND response_sha256=encode(sha256(response),'hex')),
 CONSTRAINT rwp_registration_origin_ck CHECK(backend_pid>0 AND length(xid)>0)
);

-- ---------------------------------------------------------------------------------------------------------------------
-- Pure helpers.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rwp_json(v jsonb,depth integer DEFAULT 0) RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE result text;
BEGIN
 IF v IS NULL OR depth IS NULL OR depth NOT BETWEEN 0 AND 8 THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
 CASE jsonb_typeof(v)
 WHEN 'object' THEN SELECT '{'||COALESCE(string_agg(to_jsonb(key)::text||':'||__RW_SCHEMA__.rwp_json(value,depth+1),',' ORDER BY key COLLATE "C"),'')||'}' INTO result FROM jsonb_each(v);
 WHEN 'array' THEN SELECT '['||COALESCE(string_agg(__RW_SCHEMA__.rwp_json(value,depth+1),',' ORDER BY ord),'')||']' INTO result FROM jsonb_array_elements(v) WITH ORDINALITY a(value,ord);
 ELSE result:=v::text;
 END CASE;
 RETURN result;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rwp_keys(v jsonb,keys text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT COALESCE(jsonb_typeof(v)='object' AND v ?& keys AND (SELECT count(*) FROM jsonb_object_keys(v))=cardinality(keys),false)
$$;
-- A permitting HUMAN terms check: an object with a named checker, a calendar date and permits_internal_development_use exactly true. A
-- missing (JSON null), negative, malformed or non-object value does not permit. It never looks at whether the source is synthetic
-- (design 4.2 O2: the real scope reads the source's terms_check DIRECTLY, not `terms_attested`).
CREATE FUNCTION __RW_SCHEMA__.rwp_permits(tc jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE d date;
BEGIN
 IF jsonb_typeof(tc) IS DISTINCT FROM 'object' OR jsonb_typeof(tc->'checked_by') IS DISTINCT FROM 'string'
    OR jsonb_typeof(tc->'checked_on') IS DISTINCT FROM 'string' THEN RETURN false; END IF;
 IF btrim(tc->>'checked_by',E' \t\n\r\f\v')='' OR (tc->>'checked_on') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN RETURN false; END IF;
 BEGIN
  d:=(tc->>'checked_on')::date;
 EXCEPTION WHEN others THEN
  RETURN false;
 END;
 RETURN COALESCE(tc->'permits_internal_development_use'='true'::jsonb,false);
END $$;
-- THE ORIGIN PREDICATES O1 to O3 (design 4.2, E15), evaluated independently, by value, writing nothing. p_sources is an array of
-- {source_id, synthetic, terms_check}; p_members an array of {schema ('v1'|'v2'), retrieved_by, usage_scope}. Returns the failed codes in
-- the order O1, O2, O3. No sources or no members is a failure of the predicates that need them (no evidence is not evidence).
--   O1  a source must not be synthetic: every source's `synthetic` is JSON false.
--   O2  a permitting human terms check, read from the source's terms_check directly.
--   O3  the member's acquirer is human and its usage scope is INTERNAL_DEVELOPMENT_ONLY, from the member's own manifest fields; a v2
--       (agent) manifest fails.
CREATE FUNCTION __RW_SCHEMA__.rwp_origin(p_sources jsonb,p_members jsonb) RETURNS text[]
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE codes text[]:='{}';
BEGIN
 IF jsonb_typeof(p_sources) IS DISTINCT FROM 'array' OR jsonb_array_length(p_sources)=0 THEN
  codes:=ARRAY['RW_O1_SYNTHETIC_SOURCE','RW_O2_TERMS_CHECK'];
 ELSE
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_sources) x WHERE x.value->'synthetic' IS DISTINCT FROM 'false'::jsonb) THEN
   codes:=array_append(codes,'RW_O1_SYNTHETIC_SOURCE');
  END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_sources) x WHERE NOT __RW_SCHEMA__.rwp_permits(x.value->'terms_check')) THEN
   codes:=array_append(codes,'RW_O2_TERMS_CHECK');
  END IF;
 END IF;
 IF jsonb_typeof(p_members) IS DISTINCT FROM 'array' OR jsonb_array_length(p_members)=0
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_members) x WHERE NOT COALESCE(x.value->>'schema'='v1' AND x.value->>'retrieved_by'='human'
       AND x.value->>'usage_scope'='INTERNAL_DEVELOPMENT_ONLY',false)) THEN
  codes:=array_append(codes,'RW_O3_ACQUISITION');
 END IF;
 RETURN codes;
END $$;

CREATE FUNCTION __RW_SCHEMA__.rwp_caller(expected_role text) RETURNS void
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE r pg_roles%ROWTYPE;
BEGIN
 IF expected_role NOT IN ('__RW_LOADER__','__RW_EXECUTOR__') OR session_user::text IS DISTINCT FROM expected_role OR current_setting('role') IS DISTINCT FROM 'none' THEN RAISE EXCEPTION 'RW_PROV_ROLE_REFUSED'; END IF;
 SELECT * INTO r FROM pg_roles WHERE rolname=expected_role;
 IF NOT FOUND OR NOT r.rolcanlogin OR r.rolsuper OR r.rolbypassrls OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication
 OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid OR roleid=r.oid) THEN RAISE EXCEPTION 'RW_PROV_ROLE_REFUSED'; END IF;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- Validation of a candidate (N2a's np_validate_bundle, scope-parameterised). The scope is the CONTEXT's own field; the caller of a
-- put or a guarded load decides separately whether the install may hold it.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rwp_validate_bundle(context_b bytea,payloads bytea[],manifests bytea[],envelopes bytea[],witnesses bytea[]) RETURNS text[]
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE c jsonb;m jsonb;e jsonb;w jsonb;member jsonb;source jsonb;raw bytea;arr bytea[];kind integer;total bigint;lo integer;hi integer;
 last_sha text;k text;sort_key text;last_member text;keys text[];refs text[];source_ids text[];selected_sources text[];envelope_key text;witness_key text;
 v_scope text;test_scope boolean;n_true integer:=0;n_false integer:=0;facts jsonb[]:='{}';tc jsonb;codes text[];schema_tag text;
BEGIN
 IF context_b IS NULL OR octet_length(context_b) NOT BETWEEN 2 AND 65536 THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
 total:=octet_length(context_b);
 FOR kind IN 1..4 LOOP
  CASE kind WHEN 1 THEN arr:=payloads;lo:=0;hi:=65536; WHEN 2 THEN arr:=manifests;lo:=2;hi:=65536; WHEN 3 THEN arr:=envelopes;lo:=2;hi:=65536; ELSE arr:=witnesses;lo:=2;hi:=4096; END CASE;
  IF arr IS NULL OR cardinality(arr)>16 OR COALESCE(array_ndims(arr),1)<>1 OR cardinality(arr)>0 AND array_lower(arr,1)<>1 THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  last_sha:=NULL;
  FOREACH raw IN ARRAY arr LOOP
   IF raw IS NULL OR octet_length(raw) NOT BETWEEN lo AND hi THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
   total:=total+octet_length(raw);k:=encode(sha256(raw),'hex');
   IF last_sha IS NOT NULL AND k COLLATE "C"<=last_sha COLLATE "C" THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
   last_sha:=k;
  END LOOP;
 END LOOP;
 IF total>4194304 THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
 c:=convert_from(context_b,'UTF8')::jsonb;
 IF NOT __RW_SCHEMA__.rwp_keys(c,ARRAY['schema','scope','state','promotable','source_admitted','financial_context_sha256','source_records','members']) OR c->>'schema' IS DISTINCT FROM 'finweb.provenance_context/1' THEN RAISE EXCEPTION 'RW_PROV_UNSUPPORTED'; END IF;
 v_scope:=c->>'scope';
 IF v_scope IS NULL OR v_scope NOT IN ('SYNTHETIC_TEST','TEST_SWITCH','REAL') OR c->>'state' IS DISTINCT FROM 'INTEGRITY_BOUND_NOT_ADMITTED' OR c->'promotable' IS DISTINCT FROM 'false'::jsonb OR c->'source_admitted' IS DISTINCT FROM 'false'::jsonb THEN RAISE EXCEPTION 'RW_PROV_SCOPE_REFUSED'; END IF;
 test_scope:=v_scope<>'REAL';
 IF c->'financial_context_sha256'<>'null'::jsonb AND (jsonb_typeof(c->'financial_context_sha256')<>'string' OR c->>'financial_context_sha256' !~ '^[0-9a-f]{64}$') THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
 IF jsonb_typeof(c->'members') IS DISTINCT FROM 'array' OR jsonb_typeof(c->'source_records') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
 IF jsonb_array_length(c->'members') NOT BETWEEN 1 AND 16 OR jsonb_array_length(c->'source_records') NOT BETWEEN 1 AND 16 THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
 -- Source records: shape, then I2 (no mixing of synthetic and real origin), then the scope's own rule.
 last_sha:=NULL;source_ids:=ARRAY[]::text[];
 FOR source IN SELECT value FROM jsonb_array_elements(c->'source_records') LOOP
  IF NOT (__RW_SCHEMA__.rwp_keys(source,ARRAY['source_id','name','upstream_provider','independence_group','terms_url','terms_check','synthetic']) OR __RW_SCHEMA__.rwp_keys(source,ARRAY['source_id','name','upstream_provider','independence_group','terms_url','terms_check','synthetic','source_priority'])) THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  FOREACH k IN ARRAY ARRAY['source_id','name','upstream_provider','independence_group'] LOOP
   IF jsonb_typeof(source->k) IS DISTINCT FROM 'string' OR octet_length(source->>k) NOT BETWEEN 1 AND 128 THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  END LOOP;
  IF jsonb_typeof(source->'synthetic') IS DISTINCT FROM 'boolean' THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  IF source->'terms_url'<>'null'::jsonb AND (jsonb_typeof(source->'terms_url')<>'string' OR octet_length(source->>'terms_url')>1024) THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  tc:=source->'terms_check';
  IF tc<>'null'::jsonb THEN
   IF NOT __RW_SCHEMA__.rwp_keys(tc,ARRAY['checked_by','checked_on','permits_internal_development_use','notes']) THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
   FOREACH k IN ARRAY ARRAY['checked_by','checked_on','notes'] LOOP
    IF jsonb_typeof(tc->k) IS DISTINCT FROM 'string' OR octet_length(tc->>k)>1024 THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
   END LOOP;
   IF jsonb_typeof(tc->'permits_internal_development_use') IS DISTINCT FROM 'boolean' OR btrim(tc->>'checked_by',E' \t\n\r\f\v')='' OR (tc->>'checked_on') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
   PERFORM (tc->>'checked_on')::date;
  END IF;
  IF source ? 'source_priority' AND (jsonb_typeof(source->'source_priority') IS DISTINCT FROM 'number' OR source->>'source_priority' !~ '^[1-9][0-9]*$' OR (source->>'source_priority')::numeric>9223372036854775807) THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  k:=source->>'source_id';IF last_sha IS NOT NULL AND k COLLATE "C"<=last_sha COLLATE "C" THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  source_ids:=array_append(source_ids,k);last_sha:=k;
  IF source->'synthetic'='true'::jsonb THEN n_true:=n_true+1; ELSE n_false:=n_false+1; END IF;
 END LOOP;
 IF n_true>0 AND n_false>0 THEN RAISE EXCEPTION 'RW_ORIGIN_MIXED'; END IF;
 IF test_scope AND EXISTS(SELECT 1 FROM jsonb_array_elements(c->'source_records') x WHERE x.value->'synthetic' IS DISTINCT FROM 'true'::jsonb
    OR x.value->'terms_url' IS DISTINCT FROM 'null'::jsonb OR x.value->'terms_check' IS DISTINCT FROM 'null'::jsonb) THEN RAISE EXCEPTION 'RW_PROV_SCOPE_REFUSED'; END IF;
 last_member:=NULL;selected_sources:=ARRAY[]::text[];
 FOR member IN SELECT value FROM jsonb_array_elements(c->'members') LOOP
  IF NOT __RW_SCHEMA__.rwp_keys(member,ARRAY['role','payload_sha256','manifest_sha256','envelope_sha256','witness_sha256']) THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  IF jsonb_typeof(member->'role') IS DISTINCT FROM 'string' OR member->>'role' NOT IN ('QUOTE','FX','CORPORATE_ACTION','BENCHMARK','RISK_FREE','IDENTITY','CALENDAR','RESOLUTION_RECORD') THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  FOREACH k IN ARRAY ARRAY['payload_sha256','manifest_sha256'] LOOP
   IF jsonb_typeof(member->k) IS DISTINCT FROM 'string' OR member->>k !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  END LOOP;
  envelope_key:=member->>'envelope_sha256';witness_key:=member->>'witness_sha256';
  IF (envelope_key IS NULL)<>(witness_key IS NULL) OR envelope_key IS NOT NULL AND (envelope_key !~ '^[0-9a-f]{64}$' OR witness_key !~ '^[0-9a-f]{64}$') THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
  sort_key:=(member->>'role')||':'||(member->>'payload_sha256')||':'||(member->>'manifest_sha256')||':'||COALESCE(envelope_key,'')||':'||COALESCE(witness_key,'');
  IF last_member IS NOT NULL AND sort_key COLLATE "C"<=last_member COLLATE "C" THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;last_member:=sort_key;
  SELECT b INTO raw FROM unnest(manifests) b WHERE encode(sha256(b),'hex')=member->>'manifest_sha256';
  IF NOT FOUND THEN RAISE EXCEPTION 'RW_PROV_INPUT_MISSING'; END IF;m:=convert_from(raw,'UTF8')::jsonb;
  IF m->>'schema'='finweb.marketdata.file_manifest/2' THEN IF NOT __RW_SCHEMA__.rwp_keys(m,ARRAY['schema','file_sha256','size_bytes','payload_filename','payload_format','source_id','data_kind','market','retrieval_time','retrieved_by','request','declared_adjustment','adjustment_anchor','declared_currency','declared_delay','source_identifiers','script','libraries','usage_scope','coverage']||ARRAY['acquisition']) OR NOT __RW_SCHEMA__.rwp_keys(m->'acquisition',ARRAY['schema','envelope_sha256']) OR m->'acquisition'->>'schema' IS DISTINCT FROM 'finweb.marketdata.acquisition_ref/1' THEN RAISE EXCEPTION 'RW_PROV_SHAPE';END IF;
  ELSIF m->>'schema'='finweb.marketdata.file_manifest/1' THEN IF NOT __RW_SCHEMA__.rwp_keys(m,ARRAY['schema','file_sha256','size_bytes','payload_filename','payload_format','source_id','data_kind','market','retrieval_time','retrieved_by','request','declared_adjustment','adjustment_anchor','declared_currency','declared_delay','source_identifiers','script','libraries','usage_scope','coverage']) THEN RAISE EXCEPTION 'RW_PROV_SHAPE';END IF;
  ELSE RAISE EXCEPTION 'RW_PROV_UNSUPPORTED';END IF;
  SELECT b INTO raw FROM unnest(payloads) b WHERE encode(sha256(b),'hex')=member->>'payload_sha256';
  IF NOT FOUND THEN RAISE EXCEPTION 'RW_PROV_INPUT_MISSING'; END IF;
  IF m->>'file_sha256' IS DISTINCT FROM member->>'payload_sha256' OR m->>'data_kind' IS DISTINCT FROM member->>'role' OR m->'size_bytes' IS DISTINCT FROM to_jsonb(octet_length(raw)) THEN RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS'; END IF;
  selected_sources:=array_append(selected_sources,m->>'source_id');
  IF m->>'schema'='finweb.marketdata.file_manifest/2' THEN
   schema_tag:='v2';
   IF envelope_key IS NULL OR m->>'retrieved_by' IS DISTINCT FROM 'agent' OR m->>'usage_scope' IS DISTINCT FROM 'INTERNAL_DEVELOPMENT_ONLY' OR m->'acquisition'->>'envelope_sha256' IS DISTINCT FROM envelope_key THEN RAISE EXCEPTION 'RW_PROV_SCOPE_REFUSED'; END IF;
   SELECT b INTO raw FROM unnest(envelopes) b WHERE encode(sha256(b),'hex')=envelope_key;
   IF NOT FOUND THEN RAISE EXCEPTION 'RW_PROV_INPUT_MISSING'; END IF;e:=convert_from(raw,'UTF8')::jsonb;
   IF NOT __RW_SCHEMA__.rwp_keys(e,ARRAY['schema','actor','authorization','tool','request','attempt','result','evidence','visibility']) THEN RAISE EXCEPTION 'RW_PROV_SHAPE';END IF;
   SELECT b INTO raw FROM unnest(witnesses) b WHERE encode(sha256(b),'hex')=witness_key;
   IF NOT FOUND THEN RAISE EXCEPTION 'RW_PROV_INPUT_MISSING'; END IF;w:=convert_from(raw,'UTF8')::jsonb;
   IF NOT __RW_SCHEMA__.rwp_keys(w,ARRAY['expected_envelope_sha256','expected_manifest_sha256','actor_agent_id','actor_role','approved_full_request_sha256']) THEN RAISE EXCEPTION 'RW_PROV_SHAPE';END IF;
   IF e->>'schema' IS DISTINCT FROM 'finweb.marketdata.acquisition_envelope/1' OR w->>'expected_envelope_sha256' IS DISTINCT FROM envelope_key OR w->>'expected_manifest_sha256' IS DISTINCT FROM member->>'manifest_sha256'
    OR e->'actor'->>'agent_id' IS DISTINCT FROM w->>'actor_agent_id' OR e->'actor'->>'role' IS DISTINCT FROM w->>'actor_role' OR e->'request'->>'sha256' IS DISTINCT FROM w->>'approved_full_request_sha256'
    OR e->'result'->>'payload_sha256' IS DISTINCT FROM member->>'payload_sha256' OR e->'result'->'size_bytes' IS DISTINCT FROM m->'size_bytes'
    OR e->'result'->>'retrieved_at' IS DISTINCT FROM m->>'retrieval_time' OR e->'request'->>'source_id' IS DISTINCT FROM m->>'source_id'
    OR e->'request'->'parameters' IS DISTINCT FROM m->'request' OR m->'script' IS DISTINCT FROM jsonb_build_object('name',e->'tool'->'name','version',e->'tool'->'version','script_sha256',e->'tool'->'sha256') THEN RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS'; END IF;
  ELSIF m->>'schema'='finweb.marketdata.file_manifest/1' THEN
   schema_tag:='v1';
   IF envelope_key IS NOT NULL THEN RAISE EXCEPTION 'RW_PROV_SCOPE_REFUSED'; END IF;
   IF test_scope THEN
    -- I1: a test scope stores no invented human attestation.
    IF m->>'retrieved_by' IS DISTINCT FROM 'synthetic' OR m->>'usage_scope' IS DISTINCT FROM 'SYNTHETIC_TEST' THEN RAISE EXCEPTION 'RW_PROV_SCOPE_REFUSED'; END IF;
   ELSIF m->>'retrieved_by' NOT IN ('human','synthetic') OR m->>'usage_scope' NOT IN ('INTERNAL_DEVELOPMENT_ONLY','SYNTHETIC_TEST','LICENSED_DISPLAY') THEN RAISE EXCEPTION 'RW_PROV_SHAPE';
   END IF;
  ELSE RAISE EXCEPTION 'RW_PROV_UNSUPPORTED';END IF;
  facts:=array_append(facts,jsonb_build_object('source_id',m->>'source_id','manifest_sha256',member->>'manifest_sha256','schema',schema_tag,
    'retrieved_by',m->>'retrieved_by','usage_scope',m->>'usage_scope'));
 END LOOP;
 SELECT array_agg(DISTINCT x ORDER BY x) INTO selected_sources FROM unnest(selected_sources) x;
 IF source_ids IS DISTINCT FROM selected_sources THEN RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS'; END IF;
 FOR kind IN 1..4 LOOP
  CASE kind WHEN 1 THEN arr:=payloads;k:='payload_sha256';WHEN 2 THEN arr:=manifests;k:='manifest_sha256';WHEN 3 THEN arr:=envelopes;k:='envelope_sha256';ELSE arr:=witnesses;k:='witness_sha256';END CASE;
  SELECT COALESCE(array_agg(encode(sha256(b),'hex') ORDER BY encode(sha256(b),'hex') COLLATE "C"),ARRAY[]::text[]) INTO keys FROM unnest(arr) b;
  SELECT COALESCE(array_agg(DISTINCT value->>k ORDER BY value->>k),ARRAY[]::text[]) INTO refs FROM jsonb_array_elements(c->'members') WHERE value->>k IS NOT NULL;
  IF keys IS DISTINCT FROM refs THEN RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS'; END IF;
 END LOOP;
 -- The REAL scope's policy: every origin predicate must hold, and every failed one is reported. The failed codes are RETURNED, not raised,
 -- so that a caller checks the install kind first (a candidate of the wrong kind of install is refused for that, whatever its origin) and
 -- then refuses with every code (RW_PROV_ORIGIN_REFUSED). A test scope returns the empty list (the predicates are what its synthetic
 -- axis bypasses); the invariants above are its own.
 IF NOT test_scope THEN
  RETURN __RW_SCHEMA__.rwp_origin(c->'source_records',to_jsonb(facts));
 END IF;
 RETURN '{}'::text[];
EXCEPTION WHEN data_exception THEN RAISE EXCEPTION 'RW_PROV_SHAPE';
END $$;

-- Read a registered candidate back (by context digest or by registration), re-validating every byte on the way out.
CREATE FUNCTION __RW_SCHEMA__.rwp_collect_context(context_sha text,op uuid)
RETURNS TABLE(context_b bytea,payloads bytea[],manifests bytea[],envelopes bytea[],witnesses bytea[],registration_response bytea)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE c jsonb;q jsonb;r __RW_SCHEMA__.rwp_registration%ROWTYPE;k text;expected bytea;v_codes text[];
BEGIN
 IF (context_sha IS NULL)=(op IS NULL) OR context_sha IS NOT NULL AND context_sha !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
 IF op IS NOT NULL THEN
  SELECT * INTO r FROM __RW_SCHEMA__.rwp_registration WHERE operation_id=op;IF NOT FOUND THEN RETURN;END IF;context_sha:=r.context_sha256;
 END IF;
 SELECT x.context INTO context_b FROM __RW_SCHEMA__.rwp_context x WHERE x.context_sha256=context_sha;IF NOT FOUND THEN RETURN;END IF;
 IF encode(sha256(context_b),'hex') IS DISTINCT FROM context_sha THEN RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS'; END IF;c:=convert_from(context_b,'UTF8')::jsonb;
 IF c->>'financial_context_sha256' IS DISTINCT FROM (SELECT x.financial_context_sha256 FROM __RW_SCHEMA__.rwp_context x WHERE x.context_sha256=context_sha) THEN RAISE EXCEPTION 'RW_PROV_CONTEXT_DIFFERS'; END IF;
 SELECT COALESCE(array_agg(x.payload ORDER BY x.payload_sha256 COLLATE "C"),ARRAY[]::bytea[]) INTO payloads FROM __RW_SCHEMA__.rwp_payload x WHERE x.payload_sha256 IN (SELECT value->>'payload_sha256' FROM jsonb_array_elements(c->'members'));
 SELECT COALESCE(array_agg(x.manifest ORDER BY x.manifest_sha256 COLLATE "C"),ARRAY[]::bytea[]) INTO manifests FROM __RW_SCHEMA__.rwp_manifest x WHERE x.manifest_sha256 IN (SELECT value->>'manifest_sha256' FROM jsonb_array_elements(c->'members'));
 SELECT COALESCE(array_agg(x.envelope ORDER BY x.envelope_sha256 COLLATE "C"),ARRAY[]::bytea[]) INTO envelopes FROM __RW_SCHEMA__.rwp_acquisition x WHERE x.envelope_sha256 IN (SELECT value->>'envelope_sha256' FROM jsonb_array_elements(c->'members'));
 SELECT COALESCE(array_agg(x.witness ORDER BY x.witness_sha256 COLLATE "C"),ARRAY[]::bytea[]) INTO witnesses FROM (SELECT DISTINCT witness_sha256,witness FROM __RW_SCHEMA__.rwp_manifest WHERE manifest_sha256 IN (SELECT value->>'manifest_sha256' FROM jsonb_array_elements(c->'members')) AND witness_sha256 IS NOT NULL) x;
 v_codes:=__RW_SCHEMA__.rwp_validate_bundle(context_b,payloads,manifests,envelopes,witnesses);
 IF cardinality(v_codes)>0 THEN RAISE EXCEPTION 'RW_PROV_ORIGIN_REFUSED' USING DETAIL=array_to_string(v_codes,','); END IF;
 IF EXISTS(SELECT 1 FROM __RW_SCHEMA__.rwp_manifest x JOIN jsonb_array_elements(c->'members') a ON x.manifest_sha256=a.value->>'manifest_sha256' WHERE x.payload_sha256 IS DISTINCT FROM a.value->>'payload_sha256' OR x.envelope_sha256 IS DISTINCT FROM a.value->>'envelope_sha256' OR x.witness_sha256 IS DISTINCT FROM a.value->>'witness_sha256') THEN RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS'; END IF;
 IF op IS NOT NULL THEN
  q:=convert_from(r.request,'UTF8')::jsonb;
  IF NOT __RW_SCHEMA__.rwp_keys(q,ARRAY['schema','scope','operation_id','context_sha256','payload_sha256s','manifest_sha256s','envelope_sha256s','witness_sha256s']) OR q->>'schema' IS DISTINCT FROM 'finweb.provenance_registration/1' OR q->>'scope' IS DISTINCT FROM c->>'scope' OR q->>'operation_id' IS DISTINCT FROM op::text OR q->>'context_sha256' IS DISTINCT FROM context_sha OR encode(sha256(r.request),'hex') IS DISTINCT FROM r.request_sha256 THEN RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS'; END IF;
  FOREACH k IN ARRAY ARRAY['payload','manifest','envelope','witness'] LOOP
   IF q->(k||'_sha256s') IS DISTINCT FROM (SELECT COALESCE(jsonb_agg(DISTINCT value->(k||'_sha256') ORDER BY value->(k||'_sha256')),'[]'::jsonb) FROM jsonb_array_elements(c->'members') WHERE value->>(k||'_sha256') IS NOT NULL) THEN RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS'; END IF;
  END LOOP;
  expected:=convert_to(__RW_SCHEMA__.rwp_json(jsonb_build_object('schema','finweb.provenance_registration_result/1','scope',c->>'scope','state','INTEGRITY_BOUND_NOT_ADMITTED','promotable',false,'source_admitted',false,'operation_id',op::text,'request_sha256',r.request_sha256,'context_sha256',context_sha,'payload_count',cardinality(payloads),'manifest_count',cardinality(manifests),'envelope_count',cardinality(envelopes),'member_count',jsonb_array_length(c->'members'))),'UTF8');
  IF r.response IS DISTINCT FROM expected OR encode(sha256(r.response),'hex') IS DISTINCT FROM r.response_sha256 THEN RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS'; END IF;registration_response:=r.response;
 ELSE registration_response:=NULL;END IF;
 RETURN NEXT;
EXCEPTION WHEN data_exception THEN RAISE EXCEPTION 'RW_PROV_SHAPE';
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- THE GUARDED LOAD (design 3.2, R2; N2a's np_guard re-targeted to the real gateway's mode, head, lease and root). Everything is read
-- under the locks the caller's lease already holds. It refuses AT OR AFTER the lease's complete_by with the gateway's one strict
-- predicate (rw_reached), so a holder that has set every session timeout to 0 and stalled is refused at this call. The generalised
-- guard tests the LEASE's complete_by, the stored rights and the re-derived expiry kind; it needs no separate valid_until test because
-- complete_by is never later than valid_until (design 3.1).
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rwp_guard(purpose text) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE m text;l __RW_SCHEMA__.rw_lease%ROWTYPE;h __RW_SCHEMA__.rw_head%ROWTYPE;y __RW_SCHEMA__.rw_history%ROWTYPE;r __RW_SCHEMA__.rw_root_link%ROWTYPE;
 v_snapshot bytea;v_kind text;v_reason text;v_install text;
BEGIN
 IF purpose IS NULL OR purpose NOT IN ('EXECUTE_CREATE','ARCHIVE_READ','ARCHIVE_EXPORT','EXECUTE_REPRODUCE') THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'RW_ISOLATION'; END IF;
 SELECT mode INTO m FROM __RW_SCHEMA__.rw_mode WHERE singleton FOR SHARE;
 IF m IS DISTINCT FROM 'DB_SNAPSHOT_V1' THEN RAISE EXCEPTION 'RW_MODE_HOLD'; END IF;
 SELECT * INTO l FROM __RW_SCHEMA__.rw_lease WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_PROV_LEASE_REQUIRED'; END IF;
 IF l.purpose IS DISTINCT FROM purpose OR purpose='EXECUTE_CREATE' AND l.phase NOT IN ('OPEN','SEALED','REPLAY') OR purpose<>'EXECUTE_CREATE' AND l.phase IS DISTINCT FROM 'READONLY' THEN RAISE EXCEPTION 'RW_SCOPE_DIFFERS'; END IF;
 -- The market data a candidate holds is read by create and reproduce only (the owner's narrowing for the stored market data, PD-0070
 -- decision 2, applied to the registry too): the read and export purposes read stored outputs and no market data.
 IF purpose NOT IN ('EXECUTE_CREATE','EXECUTE_REPRODUCE') THEN RAISE EXCEPTION 'RW_PROV_PURPOSE_REFUSED'; END IF;
 IF __RW_SCHEMA__.rw_reached(clock_timestamp(),l.complete_by) THEN RAISE EXCEPTION 'RW_DEADLINE'; END IF;
 SELECT * INTO h FROM __RW_SCHEMA__.rw_head WHERE context_id=l.context_id FOR SHARE;
 IF NOT FOUND OR h.generation IS DISTINCT FROM l.generation THEN RAISE EXCEPTION 'RW_GENERATION_DIFFERS'; END IF;
 SELECT * INTO y FROM __RW_SCHEMA__.rw_history x WHERE x.context_id=l.context_id AND x.generation=h.generation;
 SELECT s.snapshot INTO v_snapshot FROM __RW_SCHEMA__.rw_snapshot s WHERE s.context_id=l.context_id;
 SELECT d.kind,d.reason INTO v_kind,v_reason FROM __RW_SCHEMA__.rw_expiry_derive(__RW_SCHEMA__.rw_snapshot_sources(v_snapshot),y.basis,y.valid_until) d;
 IF v_kind IS DISTINCT FROM y.expiry_kind OR v_kind='UNKNOWN' OR h.expiry_kind IS DISTINCT FROM y.expiry_kind OR h.valid_until IS DISTINCT FROM y.valid_until THEN RAISE EXCEPTION 'RW_EXPIRY_HOLD'; END IF;
 IF NOT __RW_SCHEMA__.rw_rights_valid(h.rights) OR h.rights IS DISTINCT FROM y.rights OR NOT COALESCE((h.rights->>'ARCHIVE_READ')::boolean,false) OR NOT COALESCE((h.rights->>purpose)::boolean,false) THEN RAISE EXCEPTION 'RW_RIGHT_REFUSED'; END IF;
 SELECT * INTO r FROM __RW_SCHEMA__.rw_root_link WHERE root_id=l.root_id;
 IF NOT FOUND OR r.owner_id IS DISTINCT FROM l.owner_id OR r.context_id IS DISTINCT FROM l.context_id OR l.generation<1 THEN RAISE EXCEPTION 'RW_NOT_FOUND'; END IF;
 SELECT i.kind INTO v_install FROM __RW_SCHEMA__.rw_install i WHERE i.singleton;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_INSTALL_MISSING'; END IF;
 IF NOT __RW_SCHEMA__.rw_scope_allowed(v_install,__RW_SCHEMA__.rw_snapshot_scope(v_snapshot)) THEN RAISE EXCEPTION 'RW_INSTALL_KIND'; END IF;
END $$;

CREATE FUNCTION __RW_SCHEMA__.rwp_immutable() RETURNS trigger
LANGUAGE plpgsql VOLATILE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$ BEGIN RAISE EXCEPTION 'RW_PROV_STORAGE_CONFLICT'; END $$;

-- Register a candidate (the loader). N2a's np_put_context: validate every byte, then store idempotently by operation id.
CREATE FUNCTION __RW_SCHEMA__.rwp_put_context(op uuid,request_b bytea,context_b bytea,payloads bytea[],manifests bytea[],envelopes bytea[],witnesses bytea[]) RETURNS bytea
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE c jsonb;q jsonb;m jsonb;b bytea;prior_b bytea;k text;wkey text;wraw bytea;cs text;rs text;result bytea;r __RW_SCHEMA__.rwp_registration%ROWTYPE;arr bytea[];kind integer;req_keys jsonb;prior_record record;
 v_install text;v_snap bytea;sj jsonb;f text;v_codes text[];
BEGIN
 PERFORM __RW_SCHEMA__.rwp_caller('__RW_LOADER__');
 IF op IS NULL OR request_b IS NULL OR octet_length(request_b) NOT BETWEEN 2 AND 65536 THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
 v_codes:=__RW_SCHEMA__.rwp_validate_bundle(context_b,payloads,manifests,envelopes,witnesses);
 c:=convert_from(context_b,'UTF8')::jsonb;cs:=encode(sha256(context_b),'hex');q:=convert_from(request_b,'UTF8')::jsonb;rs:=encode(sha256(request_b),'hex');
 SELECT i.kind INTO v_install FROM __RW_SCHEMA__.rw_install i WHERE i.singleton;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_INSTALL_MISSING'; END IF;
 -- The install kind comes before the origin policy: a candidate of the other kind of install is refused for that, whatever its origin.
 IF NOT __RW_SCHEMA__.rw_scope_allowed(v_install,c->>'scope') THEN RAISE EXCEPTION 'RW_INSTALL_KIND'; END IF;
 IF cardinality(v_codes)>0 THEN RAISE EXCEPTION 'RW_PROV_ORIGIN_REFUSED' USING DETAIL=array_to_string(v_codes,','); END IF;
 IF NOT __RW_SCHEMA__.rwp_keys(q,ARRAY['schema','scope','operation_id','context_sha256','payload_sha256s','manifest_sha256s','envelope_sha256s','witness_sha256s']) OR q->>'schema' IS DISTINCT FROM 'finweb.provenance_registration/1' OR q->>'scope' IS DISTINCT FROM c->>'scope' OR q->>'operation_id' IS DISTINCT FROM op::text OR q->>'context_sha256' IS DISTINCT FROM cs THEN RAISE EXCEPTION 'RW_PROV_SHAPE'; END IF;
 FOR kind IN 1..4 LOOP
  CASE kind WHEN 1 THEN arr:=payloads;k:='payload';WHEN 2 THEN arr:=manifests;k:='manifest';WHEN 3 THEN arr:=envelopes;k:='envelope';ELSE arr:=witnesses;k:='witness';END CASE;
  SELECT COALESCE(jsonb_agg(encode(sha256(x),'hex') ORDER BY encode(sha256(x),'hex') COLLATE "C"),'[]'::jsonb) INTO req_keys FROM unnest(arr) x;
  IF q->(k||'_sha256s') IS DISTINCT FROM req_keys THEN RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS'; END IF;
 END LOOP;
 PERFORM pg_advisory_xact_lock(hashtextextended('rw.prov.register:'||'__RW_SCHEMA__',0) & 4611686018427387903);
 -- A context-bound registration needs the published snapshot (design 3.3 item 1): before the publish it is refused, and after it the
 -- bundle must be exactly the snapshot's members, each manifest naming the member's source.
 f:=c->>'financial_context_sha256';
 IF f IS NOT NULL THEN
  SELECT s.snapshot INTO v_snap FROM __RW_SCHEMA__.rw_snapshot s WHERE s.context_id=f;
  IF NOT FOUND THEN RAISE EXCEPTION 'RW_PROV_INPUT_MISSING'; END IF;
  sj:=convert_from(v_snap,'UTF8')::jsonb;
  IF sj->>'scope' IS DISTINCT FROM c->>'scope'
     OR (SELECT COALESCE(array_agg(DISTINCT (a.value->>'payload_sha256')||':'||(a.value->>'manifest_sha256') ORDER BY (a.value->>'payload_sha256')||':'||(a.value->>'manifest_sha256')),'{}'::text[]) FROM jsonb_array_elements(sj->'members') a)
        IS DISTINCT FROM (SELECT COALESCE(array_agg(DISTINCT (a.value->>'payload_sha256')||':'||(a.value->>'manifest_sha256') ORDER BY (a.value->>'payload_sha256')||':'||(a.value->>'manifest_sha256')),'{}'::text[]) FROM jsonb_array_elements(c->'members') a)
     OR (SELECT COALESCE(array_agg(DISTINCT (a.value->>'manifest_sha256')||':'||(a.value->>'source_id') ORDER BY (a.value->>'manifest_sha256')||':'||(a.value->>'source_id')),'{}'::text[]) FROM jsonb_array_elements(sj->'members') a)
        IS DISTINCT FROM (SELECT COALESCE(array_agg(DISTINCT encode(sha256(x),'hex')||':'||(convert_from(x,'UTF8')::jsonb->>'source_id') ORDER BY encode(sha256(x),'hex')||':'||(convert_from(x,'UTF8')::jsonb->>'source_id')),'{}'::text[]) FROM unnest(manifests) x) THEN
   RAISE EXCEPTION 'RW_PROV_BINDING_DIFFERS';
  END IF;
 END IF;
 SELECT * INTO r FROM __RW_SCHEMA__.rwp_registration WHERE operation_id=op;
 IF FOUND THEN
  IF r.request IS DISTINCT FROM request_b OR r.context_sha256 IS DISTINCT FROM cs THEN RAISE EXCEPTION 'RW_PROV_OPERATION_CONFLICT'; END IF;
  SELECT * INTO prior_record FROM __RW_SCHEMA__.rwp_collect_context(NULL,op);
  IF NOT FOUND THEN RAISE EXCEPTION 'RW_PROV_INPUT_MISSING'; END IF;RETURN prior_record.registration_response;
 END IF;
 IF (SELECT count(*) FROM __RW_SCHEMA__.rwp_registration)>=4096 OR (SELECT count(*) FROM __RW_SCHEMA__.rwp_context)+(CASE WHEN EXISTS(SELECT 1 FROM __RW_SCHEMA__.rwp_context WHERE context_sha256=cs) THEN 0 ELSE 1 END)>1024
 OR (SELECT count(*) FROM __RW_SCHEMA__.rwp_payload)+(SELECT count(*) FROM unnest(payloads) x WHERE NOT EXISTS(SELECT 1 FROM __RW_SCHEMA__.rwp_payload WHERE payload_sha256=encode(sha256(x),'hex')))>16384
 OR (SELECT count(*) FROM __RW_SCHEMA__.rwp_acquisition)+(SELECT count(*) FROM unnest(envelopes) x WHERE NOT EXISTS(SELECT 1 FROM __RW_SCHEMA__.rwp_acquisition WHERE envelope_sha256=encode(sha256(x),'hex')))>16384
 OR (SELECT count(*) FROM __RW_SCHEMA__.rwp_manifest)+(SELECT count(*) FROM unnest(manifests) x WHERE NOT EXISTS(SELECT 1 FROM __RW_SCHEMA__.rwp_manifest WHERE manifest_sha256=encode(sha256(x),'hex')))>16384 THEN RAISE EXCEPTION 'RW_PROV_CAPACITY'; END IF;
 FOREACH b IN ARRAY payloads LOOP
  k:=encode(sha256(b),'hex');SELECT x.payload INTO prior_b FROM __RW_SCHEMA__.rwp_payload x WHERE x.payload_sha256=k;
  IF FOUND THEN IF prior_b IS DISTINCT FROM b THEN RAISE EXCEPTION 'RW_PROV_STORAGE_CONFLICT';END IF; ELSE INSERT INTO __RW_SCHEMA__.rwp_payload VALUES(k,octet_length(b),b);END IF;
 END LOOP;
 FOREACH b IN ARRAY envelopes LOOP
  k:=encode(sha256(b),'hex');SELECT x.envelope INTO prior_b FROM __RW_SCHEMA__.rwp_acquisition x WHERE x.envelope_sha256=k;
  IF FOUND THEN IF prior_b IS DISTINCT FROM b THEN RAISE EXCEPTION 'RW_PROV_STORAGE_CONFLICT';END IF; ELSE INSERT INTO __RW_SCHEMA__.rwp_acquisition VALUES(k,b);END IF;
 END LOOP;
 FOREACH b IN ARRAY manifests LOOP
  k:=encode(sha256(b),'hex');m:=convert_from(b,'UTF8')::jsonb;SELECT a.value->>'witness_sha256' INTO wkey FROM jsonb_array_elements(c->'members') a WHERE a.value->>'manifest_sha256'=k;
  wraw:=NULL;IF wkey IS NOT NULL THEN SELECT x INTO wraw FROM unnest(witnesses) x WHERE encode(sha256(x),'hex')=wkey;END IF;
  SELECT x.manifest INTO prior_b FROM __RW_SCHEMA__.rwp_manifest x WHERE x.manifest_sha256=k;
  IF FOUND THEN
   IF prior_b IS DISTINCT FROM b OR NOT EXISTS(SELECT 1 FROM __RW_SCHEMA__.rwp_manifest x WHERE x.manifest_sha256=k AND x.payload_sha256=m->>'file_sha256' AND x.envelope_sha256 IS NOT DISTINCT FROM m->'acquisition'->>'envelope_sha256' AND x.witness_sha256 IS NOT DISTINCT FROM wkey AND x.witness IS NOT DISTINCT FROM wraw) THEN RAISE EXCEPTION 'RW_PROV_STORAGE_CONFLICT';END IF;
  ELSE INSERT INTO __RW_SCHEMA__.rwp_manifest VALUES(k,b,m->>'file_sha256',m->'acquisition'->>'envelope_sha256',wkey,wraw);END IF;
 END LOOP;
 SELECT x.context INTO prior_b FROM __RW_SCHEMA__.rwp_context x WHERE x.context_sha256=cs;
 IF FOUND THEN IF prior_b IS DISTINCT FROM context_b THEN RAISE EXCEPTION 'RW_PROV_CONTEXT_DIFFERS';END IF;ELSE INSERT INTO __RW_SCHEMA__.rwp_context VALUES(cs,context_b,c->>'financial_context_sha256');END IF;
 result:=convert_to(__RW_SCHEMA__.rwp_json(jsonb_build_object('schema','finweb.provenance_registration_result/1','scope',c->>'scope','state','INTEGRITY_BOUND_NOT_ADMITTED','promotable',false,'source_admitted',false,'operation_id',op::text,'request_sha256',rs,'context_sha256',cs,'payload_count',cardinality(payloads),'manifest_count',cardinality(manifests),'envelope_count',cardinality(envelopes),'member_count',jsonb_array_length(c->'members'))),'UTF8');
 INSERT INTO __RW_SCHEMA__.rwp_registration VALUES(op,request_b,rs,cs,result,encode(sha256(result),'hex'),pg_backend_pid(),pg_current_xact_id()::text,clock_timestamp());
 RETURN result;
EXCEPTION WHEN data_exception THEN RAISE EXCEPTION 'RW_PROV_SHAPE';WHEN foreign_key_violation THEN RAISE EXCEPTION 'RW_PROV_INPUT_MISSING';
END $$;

-- Read a registered candidate back (the loader): the PAYLOAD BYTES are returned (design 3.3, technical TR5-M1: the registry code
-- re-validates from the returned bytes, so the owner did not narrow this function). No lease reaches it; the owner's NOLOGIN
-- procedure governs it (PD-0070 decision 1).
CREATE FUNCTION __RW_SCHEMA__.rwp_get_context(context_sha text,op uuid)
RETURNS TABLE(context_b bytea,payloads bytea[],manifests bytea[],envelopes bytea[],witnesses bytea[],registration_response bytea)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN PERFORM __RW_SCHEMA__.rwp_caller('__RW_LOADER__');RETURN QUERY SELECT * FROM __RW_SCHEMA__.rwp_collect_context(context_sha,op);END $$;

-- The guarded load (the executor): only under a current lease of create or reproduce, only a registration bound to the lease's own
-- context, and only before the lease's complete_by.
CREATE FUNCTION __RW_SCHEMA__.rwp_load_context(context_sha text,purpose text)
RETURNS TABLE(context_b bytea,payloads bytea[],manifests bytea[],envelopes bytea[],witnesses bytea[],registration_response bytea)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE l __RW_SCHEMA__.rw_lease%ROWTYPE;f text;
BEGIN
 PERFORM __RW_SCHEMA__.rwp_caller('__RW_EXECUTOR__');
 IF context_sha IS NULL OR context_sha !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RW_PROV_SHAPE';END IF;
 PERFORM __RW_SCHEMA__.rwp_guard(purpose);
 SELECT * INTO l FROM __RW_SCHEMA__.rw_lease WHERE backend_pid=pg_backend_pid() AND xid=pg_current_xact_id()::text;
 SELECT x.financial_context_sha256 INTO f FROM __RW_SCHEMA__.rwp_context x WHERE x.context_sha256=context_sha;
 IF NOT FOUND THEN RETURN;END IF;
 IF f IS NULL OR f IS DISTINCT FROM l.context_id THEN RAISE EXCEPTION 'RW_PROV_CONTEXT_DIFFERS';END IF;
 RETURN QUERY SELECT * FROM __RW_SCHEMA__.rwp_collect_context(context_sha,NULL);
END $$;

-- PUBLISH'S CONSULTATION (design 4.2: "Publish evaluates the same list"). For a snapshot, find each member's REGISTERED manifest by its
-- digests, build by-value inputs for rwp_origin and return the failed codes; a member whose candidate is not registered (or whose
-- manifest names another source) is reported as RW_PROV_CANDIDATE_MISSING and counts as a failure of O3 (it cannot be shown to pass).
-- The snapshot has one origin axis: if its own origin says it is not real, or any member's manifest says the file is synthetic, every
-- source of that member is synthetic (O1). Writes nothing. Called by rw_publish (the owner's definer function) and by no role.
CREATE FUNCTION __RW_SCHEMA__.rwp_origin_failures(p_snapshot bytea) RETURNS text[]
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE s jsonb;m jsonb;man bytea;mj jsonb;rec jsonb;missing boolean:=false;codes text[];facts jsonb[]:='{}';recs jsonb[]:='{}';
 snap_synth boolean;member_synth boolean;sid text;synth_sources text[]:='{}';schema_tag text;
BEGIN
 s:=convert_from(p_snapshot,'UTF8')::jsonb;
 snap_synth:=(s->'origin'->'synthetic') IS DISTINCT FROM 'false'::jsonb;
 FOR m IN SELECT value FROM jsonb_array_elements(s->'members') LOOP
  sid:=m->>'source_id';
  SELECT x.manifest INTO man FROM __RW_SCHEMA__.rwp_manifest x WHERE x.manifest_sha256=m->>'manifest_sha256' AND x.payload_sha256=m->>'payload_sha256';
  IF FOUND THEN
   mj:=convert_from(man,'UTF8')::jsonb;
   IF mj->>'source_id' IS DISTINCT FROM sid THEN man:=NULL; END IF;
  END IF;
  IF man IS NULL THEN
   missing:=true;
   facts:=array_append(facts,jsonb_build_object('source_id',sid,'manifest_sha256',m->>'manifest_sha256','schema',NULL,'retrieved_by',NULL,'usage_scope',NULL));
  ELSE
   schema_tag:=CASE mj->>'schema' WHEN 'finweb.marketdata.file_manifest/1' THEN 'v1' WHEN 'finweb.marketdata.file_manifest/2' THEN 'v2' ELSE 'other' END;
   member_synth:=COALESCE(mj->>'usage_scope'='SYNTHETIC_TEST' OR mj->>'retrieved_by'='synthetic',false);
   IF member_synth THEN synth_sources:=array_append(synth_sources,sid); END IF;
   facts:=array_append(facts,jsonb_build_object('source_id',sid,'manifest_sha256',m->>'manifest_sha256','schema',schema_tag,
     'retrieved_by',mj->>'retrieved_by','usage_scope',mj->>'usage_scope'));
  END IF;
  man:=NULL;
 END LOOP;
 FOR sid IN SELECT DISTINCT x.value->>'source_id' FROM jsonb_array_elements(s->'members') x ORDER BY 1 LOOP
  SELECT r.value INTO rec FROM jsonb_array_elements(s->'source_records') r WHERE r.value->>'source_id'=sid;
  IF NOT FOUND THEN rec:=NULL; END IF;
  recs:=array_append(recs,jsonb_build_object('source_id',sid,'synthetic',snap_synth OR sid=ANY(synth_sources),
    'terms_check',COALESCE(rec->'terms_check','null'::jsonb)));
 END LOOP;
 codes:=__RW_SCHEMA__.rwp_origin(to_jsonb(recs),to_jsonb(facts));
 -- R3 (design 4.2, "R3 adds the origin-label mismatch"): the snapshot's own origin labels must be those of its scope. Listed first,
 -- after the install-kind code that rw_publish puts before this function's result.
 IF (s->'origin') IS DISTINCT FROM __RW_SCHEMA__.rw_origin_expected(s->>'scope') THEN codes:=array_prepend('RW_ORIGIN_MISMATCH',codes); END IF;
 IF missing THEN codes:=array_append(codes,'RW_PROV_CANDIDATE_MISSING'); END IF;
 RETURN codes;
END $$;

CREATE TRIGGER rwp_payload_immutable_rows BEFORE UPDATE OR DELETE ON __RW_SCHEMA__.rwp_payload FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rwp_immutable();
CREATE TRIGGER rwp_payload_immutable_truncate BEFORE TRUNCATE ON __RW_SCHEMA__.rwp_payload FOR EACH STATEMENT EXECUTE FUNCTION __RW_SCHEMA__.rwp_immutable();
CREATE TRIGGER rwp_acquisition_immutable_rows BEFORE UPDATE OR DELETE ON __RW_SCHEMA__.rwp_acquisition FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rwp_immutable();
CREATE TRIGGER rwp_acquisition_immutable_truncate BEFORE TRUNCATE ON __RW_SCHEMA__.rwp_acquisition FOR EACH STATEMENT EXECUTE FUNCTION __RW_SCHEMA__.rwp_immutable();
CREATE TRIGGER rwp_manifest_immutable_rows BEFORE UPDATE OR DELETE ON __RW_SCHEMA__.rwp_manifest FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rwp_immutable();
CREATE TRIGGER rwp_manifest_immutable_truncate BEFORE TRUNCATE ON __RW_SCHEMA__.rwp_manifest FOR EACH STATEMENT EXECUTE FUNCTION __RW_SCHEMA__.rwp_immutable();
CREATE TRIGGER rwp_context_immutable_rows BEFORE UPDATE OR DELETE ON __RW_SCHEMA__.rwp_context FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rwp_immutable();
CREATE TRIGGER rwp_context_immutable_truncate BEFORE TRUNCATE ON __RW_SCHEMA__.rwp_context FOR EACH STATEMENT EXECUTE FUNCTION __RW_SCHEMA__.rwp_immutable();
CREATE TRIGGER rwp_registration_immutable_rows BEFORE UPDATE OR DELETE ON __RW_SCHEMA__.rwp_registration FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rwp_immutable();
CREATE TRIGGER rwp_registration_immutable_truncate BEFORE TRUNCATE ON __RW_SCHEMA__.rwp_registration FOR EACH STATEMENT EXECUTE FUNCTION __RW_SCHEMA__.rwp_immutable();

-- ---------------------------------------------------------------------------------------------------------------------
-- Grants. PUBLIC holds nothing. Since R3 no SQL file grants anything to a runtime role: the loader's EXECUTE on rwp_put_context and
-- rwp_get_context and the executor's EXECUTE on rwp_load_context are entries of the role lists in the shared installer code
-- (persistence/real_roles.py), applied by the installer after the last file.
-- ---------------------------------------------------------------------------------------------------------------------
REVOKE ALL ON __RW_SCHEMA__.rwp_payload,__RW_SCHEMA__.rwp_acquisition,__RW_SCHEMA__.rwp_manifest,__RW_SCHEMA__.rwp_context,__RW_SCHEMA__.rwp_registration FROM PUBLIC;
DO $$ DECLARE f record; BEGIN
 FOR f IN SELECT p.proname AS fname, pg_get_function_identity_arguments(p.oid) AS fargs FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='__RW_SCHEMA__' AND p.proname LIKE 'rwp\_%' LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %I.%I(%s) FROM PUBLIC','__RW_SCHEMA__',f.fname,f.fargs);
 END LOOP;
END $$;
