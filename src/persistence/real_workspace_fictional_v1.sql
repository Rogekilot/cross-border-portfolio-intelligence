-- F1 R3: the TEST-ONLY SQL PART (implementation/CP7_F1_REAL_PATH_DESIGN.md section 1 item 1; 4.2 build table; 4.4 "What the SYNTHETIC_TEST
-- create is made of").
--
-- FUNCTIONS ONLY: no table, no trigger, no constraint, no policy, no grant. The FICTIONAL branch's acceptance, a fork of F2's
-- gw_check_artifact for the scope SYNTHETIC_TEST (never an edit of an F2 file). Only the TEST provisioner runs this file: the shared installer
-- code returns it for the install kind TEST and not for REAL (persistence/real_roles.sql_files), a static test checks that, and the catalog
-- audit (persistence/real_catalog_audit.py) refuses a REAL catalog in which a function of this part exists. The core (real_fence_v1.sql)
-- reaches this part only by name and at run time, from rw_check_artifact, for the scope SYNTHETIC_TEST, which a REAL install refuses at
-- publish and at admit; so the core installs and runs without it.
--
-- WHAT IT ACCEPTS: the bytes the EXISTING fictional integration issues, unchanged (src/financial_service_integration.py,
-- `issue_local_service`): the CP5 diversification Result {manifest, manifest_id, result_digest, metrics, clusters, exposure_decompositions},
-- the question `finweb.local_fictional.service_question/1` and the binding `finweb.local_fictional.service_binding/1` (the integration builds
-- both), and the gateway's envelope around them. The fork keeps F2's checks of those documents (guarded_workspace_v1.sql:288-336) wherever the
-- fact they bind exists in an S2 world, and maps each check onto a field the integration issues:
--   kept, as F2 has them   envelope shape, question (equal to the question the gateway's own fields imply), binding (equal to the binding the
--                          issued fields imply), issued keys, native digests, the CP5 manifest and valuation-manifest fields, the capital
--                          policy's origin, the identity-facts digest, synthetic = true, F8B dry run, source records with no terms check.
--   re-keyed to the S2 snapshot   release: valuation_manifest.release_id = the snapshot's release.release_id (F2: the hash of a fixed release
--                          object); F8B policy: valuation_manifest.detection_policy[0] = ["digest", snapshot.f8b_policy_digest].
--   NOT kept, because the S2 snapshot has no field to check them against (reported to the PM, R3 fix round): the F2 fixed-fixture hashes,
--                          the capital policy against the snapshot's, the source-registry digest against the snapshot's records, the identity
--                          facts against the snapshot's lookup answers, and the binding of the question's `context_id` to the LEASE's context:
--                          the integration's context id is the SHA-256 of its own fingerprint snapshot (`fingerprint_context_inputs`), which
--                          is not the S2 snapshot's id, and no issued field relates the two.
--
-- It RAISES a typed code for a structural failure and RETURNS the list of failed predicate codes (empty when acceptable); the core raises the
-- list together as RW_SEAL_REFUSED. Its fourth argument is the core's context object (the snapshot and the gateway's own identifiers).
CREATE FUNCTION __RW_SCHEMA__.rw_check_fictional(p_env jsonb,p_issued jsonb,p_response jsonb,p_ctx jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE codes text[]:='{}'; m jsonb:=p_issued->'manifest'; vm jsonb:=p_issued->'manifest'->'valuation_manifest'; snap jsonb:=p_ctx->'snapshot';
 q jsonb; b jsonb; qb bytea; bb bytea; required_q jsonb; required_b jsonb; fact jsonb;
BEGIN
 IF NOT rw_keys(p_env,ARRAY['schema','scope','synthetic','owner_id','root_id','operation_id','revision_id','ledger_pin','context_id','generation',
    'issued_sha256','response_sha256','manifest_id','result_digest','question_sha256','binding_sha256','question_hex','binding_hex','selector','family','engine_id'])
    THEN RAISE EXCEPTION 'RW_ENVELOPE_SHAPE'; END IF;
 IF p_env->>'schema' IS DISTINCT FROM 'finweb.fictional.issued_envelope/1' OR p_env->>'selector' IS DISTINCT FROM 'CP5_DIVERSIFICATION'
    OR p_env->>'family' IS DISTINCT FROM 'CP5_DIVERSIFICATION' OR p_env->>'engine_id' IS DISTINCT FROM 'diversification/cp5-0.2' THEN RAISE EXCEPTION 'RW_ENVELOPE_DIFFERS'; END IF;
 -- The question and the binding travel as canonical hex.
 IF jsonb_typeof(p_env->'question_hex') IS DISTINCT FROM 'string' OR length(p_env->>'question_hex') NOT BETWEEN 4 AND 65536 OR (p_env->>'question_hex') !~ '^([0-9a-f]{2})+$'
    OR jsonb_typeof(p_env->'binding_hex') IS DISTINCT FROM 'string' OR length(p_env->>'binding_hex') NOT BETWEEN 4 AND 65536 OR (p_env->>'binding_hex') !~ '^([0-9a-f]{2})+$' THEN
  RAISE EXCEPTION 'RW_BINDING_SHAPE';
 END IF;
 BEGIN
  qb:=decode(p_env->>'question_hex','hex'); bb:=decode(p_env->>'binding_hex','hex'); q:=convert_from(qb,'UTF8')::jsonb; b:=convert_from(bb,'UTF8')::jsonb;
 EXCEPTION WHEN others THEN
  RAISE EXCEPTION 'RW_BINDING_SHAPE';
 END;
 IF p_env->>'question_sha256' IS DISTINCT FROM encode(sha256(qb),'hex') OR p_env->>'binding_sha256' IS DISTINCT FROM encode(sha256(bb),'hex')
    OR qb IS DISTINCT FROM convert_to(rw_json(q),'UTF8') OR bb IS DISTINCT FROM convert_to(rw_json(b),'UTF8') THEN RAISE EXCEPTION 'RW_BINDING_DIFFERS'; END IF;
 -- The question is the one the gateway's own fields imply; its context id is the integration's (see the header).
 required_q:=jsonb_build_object('schema','finweb.local_fictional.service_question/1','selector','CP5_DIVERSIFICATION','owner_id',p_ctx->>'owner_id',
   'root_id',p_ctx->>'root_id','revision_id',p_ctx->>'revision_id','operation_id',p_ctx->>'operation_id','portfolio_id',p_ctx->>'root_id',
   'ledger_pin',(p_ctx->>'ledger_pin'),'as_of',p_ctx->>'as_of','context_id',q->>'context_id','generation',p_ctx->'generation','account_scope',NULL,
   'reporting_currency','USD');
 IF q IS DISTINCT FROM required_q OR q->>'context_id' !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RW_QUESTION_DIFFERS'; END IF;
 -- The CP5 Result, as issued.
 IF NOT rw_keys(p_issued,ARRAY['manifest','manifest_id','result_digest','metrics','clusters','exposure_decompositions'])
    OR jsonb_typeof(p_issued->'metrics') IS DISTINCT FROM 'array' OR jsonb_typeof(p_issued->'clusters') IS DISTINCT FROM 'array'
    OR jsonb_typeof(p_issued->'exposure_decompositions') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'RW_ISSUED_SHAPE'; END IF;
 IF p_issued->>'result_digest' IS DISTINCT FROM encode(sha256(convert_to(rw_json(jsonb_build_object('metrics',p_issued->'metrics','clusters',p_issued->'clusters',
    'exposure_decompositions',p_issued->'exposure_decompositions')),'UTF8')),'hex') THEN RAISE EXCEPTION 'RW_NATIVE_DIGEST_DIFFERS'; END IF;
 IF m->>'schema' IS DISTINCT FROM 'finweb.diversification_manifest/1' OR m->>'engine_id' IS DISTINCT FROM 'diversification/cp5-0.2'
    OR m->>'state_kind' IS DISTINCT FROM 'ACTUAL' OR m->>'portfolio_id' IS DISTINCT FROM p_ctx->>'root_id' OR m->'account_scope' IS DISTINCT FROM 'null'::jsonb
    OR m->>'as_of' IS DISTINCT FROM p_ctx->>'as_of' OR m->>'reporting_currency' IS DISTINCT FROM 'USD' OR m->'capital_policy_confirmed' IS DISTINCT FROM 'true'::jsonb
    OR jsonb_typeof(m->'synthetic') IS DISTINCT FROM 'boolean' THEN RAISE EXCEPTION 'RW_MANIFEST_DIFFERS'; END IF;
 IF jsonb_typeof(vm) IS DISTINCT FROM 'object' OR vm->>'portfolio_id' IS DISTINCT FROM p_ctx->>'root_id' OR vm->'ledger_version' IS DISTINCT FROM p_ctx->'ledger_pin'
    OR vm->>'as_of' IS DISTINCT FROM p_ctx->>'as_of' OR vm->>'reporting_currency' IS DISTINCT FROM 'USD' OR vm->>'scope' IS DISTINCT FROM 'PORTFOLIO'
    OR vm->>'state_kind' IS DISTINCT FROM 'ACTUAL' OR jsonb_typeof(vm->'synthetic') IS DISTINCT FROM 'boolean' OR jsonb_typeof(vm->'split_detection') IS DISTINCT FROM 'string'
    THEN RAISE EXCEPTION 'RW_VALUATION_DIFFERS'; END IF;
 IF m->'capital_policy'->>'origin' IS DISTINCT FROM 'SYNTHETIC_CANDIDATE' OR m->'capital_policy'->>'scope_kind' IS DISTINCT FROM 'PORTFOLIO'
    OR m->'capital_policy'->>'portfolio_id' IS DISTINCT FROM p_ctx->>'root_id' THEN RAISE EXCEPTION 'RW_POLICY_DIFFERS'; END IF;
 IF jsonb_typeof(m->'identity_facts') IS DISTINCT FROM 'array' OR jsonb_array_length(m->'identity_facts')>48
    OR m->>'identity_digest' IS DISTINCT FROM encode(sha256(convert_to(rw_json(m->'identity_facts'),'UTF8')),'hex') THEN RAISE EXCEPTION 'RW_IDENTITY_DIFFERS'; END IF;
 FOR fact IN SELECT x.value FROM jsonb_array_elements(m->'identity_facts') x LOOP
  IF jsonb_typeof(fact) IS DISTINCT FROM 'array' OR jsonb_array_length(fact)<>3 OR fact->>0 NOT IN ('trading_currency','exchange_mic','security_type') THEN
   RAISE EXCEPTION 'RW_IDENTITY_DIFFERS';
  END IF;
 END LOOP;
 -- The binding is the one the issued fields imply.
 required_b:=jsonb_build_object('schema','finweb.local_fictional.service_binding/1','question',q,'question_sha256',p_env->>'question_sha256',
   'context_snapshot_sha256',q->>'context_id','generation',p_ctx->'generation','family','CP5_DIVERSIFICATION','engine_id','diversification/cp5-0.2',
   'manifest_id',p_env->>'manifest_id','result_digest',p_env->>'result_digest','issued_sha256',p_env->>'issued_sha256','synthetic',true,
   'release_id',vm->>'release_id','source_registry_digest',vm->>'source_registry_digest','consumed_identity_digest',m->>'identity_digest',
   'f8b_policy',vm->'detection_policy');
 IF b IS DISTINCT FROM required_b THEN RAISE EXCEPTION 'RW_BINDING_DIFFERS'; END IF;
 -- The predicates (reported together).
 -- synthetic = true wherever the result states it (the converse of O4a).
 IF p_env->'synthetic' IS DISTINCT FROM 'true'::jsonb OR m->'synthetic' IS DISTINCT FROM 'true'::jsonb OR vm->'synthetic' IS DISTINCT FROM 'true'::jsonb
    OR p_response->'synthetic' IS DISTINCT FROM 'true'::jsonb THEN codes:=array_append(codes,'RW_FICTIONAL_NOT_SYNTHETIC'); END IF;
 -- Source records with no terms check (a test scope stores none, 4.2).
 IF jsonb_typeof(snap->'source_records') IS DISTINCT FROM 'array' OR jsonb_array_length(snap->'source_records') NOT BETWEEN 1 AND 64
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(snap->'source_records') r WHERE r.value->'terms_check' IS DISTINCT FROM 'null'::jsonb) THEN
  codes:=array_append(codes,'RW_FICTIONAL_SOURCE_DIFFERS');
 END IF;
 IF vm->>'split_detection' IS DISTINCT FROM 'F8B_DRY_RUN' THEN codes:=array_append(codes,'RW_FICTIONAL_F8B_MODE'); END IF;
 IF vm->>'release_id' IS DISTINCT FROM snap->'release'->>'release_id' THEN codes:=array_append(codes,'RW_FICTIONAL_RELEASE_DIFFERS'); END IF;
 IF jsonb_typeof(vm->'detection_policy') IS DISTINCT FROM 'array' OR vm->'detection_policy'->0->>0 IS DISTINCT FROM 'digest'
    OR vm->'detection_policy'->0->>1 IS DISTINCT FROM snap->>'f8b_policy_digest' THEN codes:=array_append(codes,'RW_FICTIONAL_POLICY_DIFFERS'); END IF;
 RETURN codes;
END $$;
