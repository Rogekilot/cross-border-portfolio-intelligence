-- F1 R3: the real gateway's WRITE FENCE, ROW POLICY, JOURNAL, SEAL, ARCHIVE, BUNDLE GUARD, S2 ROOT STORAGE and the thirteen LEASE-CHECKED
-- md_* READ FUNCTIONS (implementation/CP7_F1_REAL_PATH_DESIGN.md sections 1 item 6, 2.6, 3.1, 3.2, 4.2, 4.4; PD-0059, PD-0060, PD-0069,
-- PD-0070 decision 2). Installed by the installer after real_workspace_v1.sql and real_provenance_v1.sql, in the same transaction, with the
-- same four validated identifiers. It is part of the CORE: a REAL install holds it. The fictional branch's acceptance is NOT here (it is
-- the TEST-only file, real_workspace_fictional_v1.sql, which a REAL install does not run); the core reaches it only through
-- rw_check_artifact, by name, at run time, for the scope SYNTHETIC_TEST, which a REAL install refuses at publish and at admit.
--
-- AFTER THIS FILE NO INCREMENT ADDS GATEWAY SQL (technical TR3-L6): a later change to it reopens R3's review and re-runs the catalog audit.
--
-- WHOLE DATABASE IS THE NAMESPACE (2.6). Unlike F2's fork there is no "unselected" root: a write needs an open EXECUTE_CREATE lease on the
-- write's own root, which admit registered; a read of a rooted table needs a lease on that root and the clock before complete_by.
--   barrier 1  the write fence       BEFORE INSERT/UPDATE/DELETE per row (zz_rw_write), TRUNCATE refused for everyone
--   barrier 2  the row policy        RESTRICTIVE, for the executor: USING (read) / WITH CHECK (write) through rw_row_allowed
--   barrier 3  the journal           AFTER per row (zz_rw_journal): raises where the fence did not (it was disabled)
-- Each refuses alone; the executor cannot disable any of them (it owns nothing and has no TRIGGER privilege).
--
-- Every statement-time deadline check calls rw_reached(clock_timestamp(), complete_by), R1's one strict comparison, so the first refused
-- instant is complete_by itself. Every function pins its search_path (pg_temp last). Dynamic SQL is used in exactly two places and only
-- with identifiers taken from the journal's own table_name column, which a trigger wrote from TG_TABLE_NAME (rw_validate).

-- ---------------------------------------------------------------------------------------------------------------------
-- Pure helpers (copies of the F2 helpers gw_json / gw_keys, with the real prefix).
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rw_json(v jsonb,depth integer DEFAULT 0) RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE result text;
BEGIN
 IF v IS NULL OR depth IS NULL OR depth>48 THEN RAISE EXCEPTION 'RW_JSON_SHAPE'; END IF;
 CASE jsonb_typeof(v)
 WHEN 'object' THEN SELECT '{'||COALESCE(string_agg(to_jsonb(key)::text||':'||__RW_SCHEMA__.rw_json(value,depth+1),',' ORDER BY key COLLATE "C"),'')||'}' INTO result FROM jsonb_each(v);
 WHEN 'array' THEN SELECT '['||COALESCE(string_agg(__RW_SCHEMA__.rw_json(value,depth+1),',' ORDER BY ord),'')||']' INTO result FROM jsonb_array_elements(v) WITH ORDINALITY a(value,ord);
 ELSE result:=v::text;
 END CASE;
 RETURN result;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_keys(v jsonb,keys text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT COALESCE(jsonb_typeof(v)='object' AND v ?& keys AND (SELECT count(*) FROM jsonb_object_keys(v))=cardinality(keys),false)
$$;

-- ---------------------------------------------------------------------------------------------------------------------
-- S2 ROOT STORAGE (design 1 item 6, 1.1): the real root and its revisions live here and never in web_saved_sandbox or
-- web_portfolio_revision. The origin fields are written once with the root, immutably, and the row guard of the seal ties them to the
-- scope of the root's context. A root row references its registered root link (admit's), so no root row exists for an unregistered root.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE __RW_SCHEMA__.rw_root (
    portfolio_id uuid CONSTRAINT rw_root_pkey PRIMARY KEY,
    context_id text NOT NULL,
    market_origin text NOT NULL,
    ledger_origin text NOT NULL,
    personal_holdings boolean NOT NULL,
    synthetic boolean NOT NULL,
    name text NOT NULL,
    account_label text NOT NULL,
    opening_label text NOT NULL,
    request_json text NOT NULL,
    snapshot_json text NOT NULL,
    snapshot_sha256 text NOT NULL,
    ledger_version bigint NOT NULL,
    created_at timestamptz NOT NULL,
    CONSTRAINT rw_root_portfolio_fkey FOREIGN KEY(portfolio_id) REFERENCES __RW_SCHEMA__.portfolio(portfolio_id),
    CONSTRAINT rw_root_registered_fkey FOREIGN KEY(portfolio_id,context_id) REFERENCES __RW_SCHEMA__.rw_root_link(root_id,context_id),
    CONSTRAINT rw_root_origin_ck CHECK((market_origin='REAL_SOURCE' AND ledger_origin='PROJECT_CONSTRUCTED_NONPERSONAL_UAT' AND NOT synthetic)
        OR (market_origin='SYNTHETIC_TEST' AND ledger_origin='INVENTED_TEST_LEDGER' AND synthetic)),
    CONSTRAINT rw_root_text_ck CHECK(char_length(name) BETWEEN 1 AND 80 AND char_length(account_label) BETWEEN 1 AND 160
        AND char_length(opening_label) BETWEEN 1 AND 160 AND octet_length(request_json)<=32768 AND octet_length(snapshot_json)<=4000000),
    CONSTRAINT rw_root_digest_ck CHECK(snapshot_sha256 ~ '^[0-9a-f]{64}$' AND snapshot_sha256=encode(sha256(convert_to(snapshot_json,'UTF8')),'hex') AND ledger_version>0)
);
CREATE TABLE __RW_SCHEMA__.rw_revision (
    revision_seq bigint GENERATED ALWAYS AS IDENTITY CONSTRAINT rw_revision_pkey PRIMARY KEY,
    revision_id uuid NOT NULL CONSTRAINT rw_revision_id_key UNIQUE,
    portfolio_id uuid NOT NULL CONSTRAINT rw_revision_root_fkey REFERENCES __RW_SCHEMA__.rw_root(portfolio_id),
    parent_revision_id uuid NOT NULL,
    operation_id uuid NOT NULL,
    operation text NOT NULL CONSTRAINT rw_revision_operation_ck CHECK(operation IN ('CREATE')),
    command_sha256 text NOT NULL CONSTRAINT rw_revision_command_ck CHECK(command_sha256 ~ '^[0-9a-f]{64}$'),
    as_of date NOT NULL CONSTRAINT rw_revision_as_of_ck CHECK(as_of BETWEEN DATE '0001-01-01' AND DATE '9999-12-31'),
    ledger_version bigint NOT NULL CONSTRAINT rw_revision_ledger_ck CHECK(ledger_version>0),
    selection_version bigint NOT NULL CONSTRAINT rw_revision_selection_ck CHECK(selection_version>=0),
    policies_json text NOT NULL CONSTRAINT rw_revision_policies_ck CHECK(octet_length(policies_json)<=100000),
    policies_state text NOT NULL CONSTRAINT rw_revision_policies_state_ck CHECK(policies_state IN ('NOT_STATED','NONE','ACTIVE')),
    snapshot_json text NOT NULL CONSTRAINT rw_revision_snapshot_ck CHECK(octet_length(snapshot_json)<=4000000),
    snapshot_sha256 text NOT NULL,
    created_at timestamptz NOT NULL,
    CONSTRAINT rw_revision_op_key UNIQUE(portfolio_id,operation_id),
    CONSTRAINT rw_revision_digest_ck CHECK(snapshot_sha256 ~ '^[0-9a-f]{64}$' AND snapshot_sha256=encode(sha256(convert_to(snapshot_json,'UTF8')),'hex'))
);
CREATE INDEX rw_revision_portfolio ON __RW_SCHEMA__.rw_revision(portfolio_id,revision_seq);

-- The sealed bundle (F2's gw_artifact / gw_operation / gw_journal, re-keyed to the root-link table). The operation row carries the
-- MANDATORY LINK: the digest of the registered provenance candidate the sealed result stands on (design 3.3, 4.2; PD-0059). It is a
-- column, not a foreign key: nothing in the gateway references a candidate (R2: "candidates immutable and unreferenced"), and rw_seal and
-- the bundle guard verify the registry row instead.
CREATE TABLE __RW_SCHEMA__.rw_artifact (
    owner_id uuid NOT NULL,
    operation_id uuid NOT NULL,
    root_id uuid NOT NULL,
    context_id text NOT NULL,
    generation bigint NOT NULL,
    revision_id uuid NOT NULL,
    ledger_pin bigint NOT NULL CONSTRAINT rw_artifact_pin_ck CHECK(ledger_pin>0),
    issued bytea NOT NULL CONSTRAINT rw_artifact_issued_ck CHECK(octet_length(issued) BETWEEN 2 AND 2000000),
    issued_sha256 text NOT NULL CONSTRAINT rw_artifact_issued_digest_ck CHECK(issued_sha256=encode(sha256(issued),'hex')),
    response bytea NOT NULL CONSTRAINT rw_artifact_response_ck CHECK(octet_length(response) BETWEEN 2 AND 6000000),
    response_sha256 text NOT NULL CONSTRAINT rw_artifact_response_digest_ck CHECK(response_sha256=encode(sha256(response),'hex')),
    envelope bytea NOT NULL CONSTRAINT rw_artifact_envelope_ck CHECK(octet_length(envelope) BETWEEN 2 AND 65536),
    envelope_sha256 text NOT NULL CONSTRAINT rw_artifact_envelope_digest_ck CHECK(envelope_sha256=encode(sha256(envelope),'hex')),
    CONSTRAINT rw_artifact_pkey PRIMARY KEY(owner_id,operation_id),
    CONSTRAINT rw_artifact_root_fkey FOREIGN KEY(root_id,context_id) REFERENCES __RW_SCHEMA__.rw_root_link(root_id,context_id)
);
CREATE TABLE __RW_SCHEMA__.rw_operation (
    owner_id uuid NOT NULL,
    operation_id uuid NOT NULL,
    root_id uuid NOT NULL,
    context_id text NOT NULL,
    generation bigint NOT NULL,
    command_sha256 text NOT NULL CONSTRAINT rw_operation_command_ck CHECK(command_sha256 ~ '^[0-9a-f]{64}$'),
    kind text NOT NULL CONSTRAINT rw_operation_kind_ck CHECK(kind IN ('CREATE')),
    revision_id uuid NOT NULL,
    journal_count bigint NOT NULL CONSTRAINT rw_operation_journal_ck CHECK(journal_count>0),
    state_sha256 text NOT NULL,
    provenance_context_sha256 text NOT NULL CONSTRAINT rw_operation_link_ck CHECK(provenance_context_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT rw_operation_pkey PRIMARY KEY(owner_id,operation_id),
    CONSTRAINT rw_operation_artifact_fkey FOREIGN KEY(owner_id,operation_id) REFERENCES __RW_SCHEMA__.rw_artifact(owner_id,operation_id)
);
CREATE TABLE __RW_SCHEMA__.rw_journal (
    seq bigint GENERATED ALWAYS AS IDENTITY CONSTRAINT rw_journal_pkey PRIMARY KEY,
    backend_pid integer NOT NULL,
    xid text NOT NULL,
    root_id uuid NOT NULL,
    table_name text NOT NULL,
    action text NOT NULL CONSTRAINT rw_journal_action_ck CHECK(action IN ('INSERT','UPDATE','DELETE')),
    row_key jsonb NOT NULL,
    old_row jsonb,
    new_row jsonb
);

DO $$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['rw_root','rw_revision','rw_artifact','rw_operation','rw_journal'] LOOP
  EXECUTE format('CREATE TRIGGER rw_immutable BEFORE UPDATE OR DELETE ON %I.%I FOR EACH ROW EXECUTE FUNCTION %I.rw_no_mutation()','__RW_SCHEMA__',t,'__RW_SCHEMA__');
  EXECUTE format('CREATE TRIGGER rw_no_truncate BEFORE TRUNCATE ON %I.%I FOR EACH STATEMENT EXECUTE FUNCTION %I.rw_no_mutation()','__RW_SCHEMA__',t,'__RW_SCHEMA__');
 END LOOP;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- TARGET ROOT, ROW POLICY, WRITE FENCE, JOURNAL (design 2.6 items 1 to 3).
-- ---------------------------------------------------------------------------------------------------------------------
-- The root a row belongs to. Fails closed: an unknown table is RW_TARGET_UNKNOWN, a row with no resolvable root is RW_ROOT_UNKNOWN.
CREATE FUNCTION __RW_SCHEMA__.rw_target_root(t text,v jsonb) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE r uuid;
BEGIN
 IF t IS NULL OR v IS NULL OR jsonb_typeof(v) IS DISTINCT FROM 'object' THEN RAISE EXCEPTION 'RW_ROOT_UNKNOWN'; END IF;
 IF t='ledger_event' THEN
  SELECT a.portfolio_id INTO r FROM account a WHERE a.account_id=(v->>'account_id')::uuid;
 ELSIF t IN ('portfolio','account','benchmark_selection','rw_root','rw_revision') THEN
  r:=(v->>'portfolio_id')::uuid;
 ELSE
  RAISE EXCEPTION 'RW_TARGET_UNKNOWN';
 END IF;
 IF r IS NULL THEN RAISE EXCEPTION 'RW_ROOT_UNKNOWN'; END IF;
 RETURN r;
END $$;

-- The row policy's test. Its FIRST test is the lease, not the registry: no lease for the target root is false for a registered and an
-- unregistered root alike. A read needs a lease on that root with the clock before complete_by (so a SELECT at or after the deadline
-- returns no row: a restrictive policy filters silently); a write needs the open EXECUTE_CREATE lease.
CREATE FUNCTION __RW_SCHEMA__.rw_row_allowed(t text,v jsonb,w boolean) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE r uuid;
BEGIN
 IF w IS NULL THEN RETURN false; END IF;
 r:=__RW_SCHEMA__.rw_target_root(t,v);
 RETURN EXISTS(SELECT 1 FROM rw_lease l JOIN rw_root_link x ON x.root_id=l.root_id AND x.context_id=l.context_id AND x.owner_id=l.owner_id
  WHERE l.backend_pid=pg_backend_pid() AND l.xid=pg_current_xact_id()::text AND l.root_id=r
   AND NOT rw_reached(clock_timestamp(),l.complete_by)
   AND (NOT w OR (l.purpose='EXECUTE_CREATE' AND l.phase='OPEN')));
END $$;

CREATE FUNCTION __RW_SCHEMA__.rw_write_fence() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE v jsonb; ov jsonb; r uuid; ro uuid; l __RW_SCHEMA__.rw_lease%ROWTYPE;
BEGIN
 IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'RW_TRUNCATE_REFUSED'; END IF;
 IF TG_OP<>'INSERT' THEN ov:=to_jsonb(OLD); ro:=__RW_SCHEMA__.rw_target_root(TG_TABLE_NAME,ov); END IF;
 IF TG_OP<>'DELETE' THEN v:=to_jsonb(NEW); r:=__RW_SCHEMA__.rw_target_root(TG_TABLE_NAME,v); ELSE r:=ro; END IF;
 IF ro IS NOT NULL AND ro IS DISTINCT FROM r THEN RAISE EXCEPTION 'RW_ROOT_DIFFERS'; END IF;
 -- No "selected" test (2.6 item 1): every write of the executor needs the open create lease of the current transaction, strictly before
 -- its deadline, whether or not the target root is registered.
 SELECT * INTO l FROM rw_lease x WHERE x.backend_pid=pg_backend_pid() AND x.xid=pg_current_xact_id()::text;
 IF NOT FOUND OR l.purpose IS DISTINCT FROM 'EXECUTE_CREATE' OR l.phase IS DISTINCT FROM 'OPEN' OR rw_reached(clock_timestamp(),l.complete_by) THEN
  RAISE EXCEPTION 'RW_WRITE_REFUSED';
 END IF;
 IF l.root_id IS DISTINCT FROM r THEN RAISE EXCEPTION 'RW_ROOT_DIFFERS'; END IF;
 IF NOT EXISTS(SELECT 1 FROM rw_root_link x WHERE x.root_id=r AND x.context_id=l.context_id AND x.owner_id=l.owner_id) THEN RAISE EXCEPTION 'RW_WRITE_REFUSED'; END IF;
 -- A transfer leg must stay inside the root (F2's multi-root refusal).
 IF TG_OP<>'DELETE' AND TG_TABLE_NAME='ledger_event' AND v->>'counterparty_account_id' IS NOT NULL THEN
  IF NOT EXISTS(SELECT 1 FROM account a WHERE a.account_id=(v->>'counterparty_account_id')::uuid AND a.portfolio_id=r) THEN RAISE EXCEPTION 'RW_MULTI_ROOT_REFUSED'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;

-- DEFENCE IN DEPTH: where F2 returns early for an unregistered root, this raises. A write that reaches it without a lease, with an unregistered
-- root, with the wrong purpose or phase, or at or after complete_by means the fence (and, for an insert, the policy) was disabled.
CREATE FUNCTION __RW_SCHEMA__.rw_journal_after() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE v jsonb; ov jsonb; r uuid; l __RW_SCHEMA__.rw_lease%ROWTYPE; key jsonb;
BEGIN
 IF TG_OP<>'INSERT' THEN ov:=to_jsonb(OLD); END IF;
 IF TG_OP<>'DELETE' THEN v:=to_jsonb(NEW); END IF;
 r:=__RW_SCHEMA__.rw_target_root(TG_TABLE_NAME,COALESCE(v,ov));
 IF NOT EXISTS(SELECT 1 FROM rw_root_link x WHERE x.root_id=r) THEN RAISE EXCEPTION 'RW_WRITE_REFUSED'; END IF;
 SELECT * INTO l FROM rw_lease x WHERE x.backend_pid=pg_backend_pid() AND x.xid=pg_current_xact_id()::text;
 IF NOT FOUND OR l.root_id IS DISTINCT FROM r OR l.purpose IS DISTINCT FROM 'EXECUTE_CREATE' OR l.phase IS DISTINCT FROM 'OPEN'
    OR rw_reached(clock_timestamp(),l.complete_by) THEN RAISE EXCEPTION 'RW_WRITE_REFUSED'; END IF;
 key:=CASE TG_TABLE_NAME
  WHEN 'portfolio' THEN jsonb_build_object('portfolio_id',r)
  WHEN 'account' THEN jsonb_build_object('account_id',COALESCE(v,ov)->>'account_id')
  WHEN 'ledger_event' THEN jsonb_build_object('event_id',COALESCE(v,ov)->>'event_id')
  WHEN 'benchmark_selection' THEN jsonb_build_object('selection_id',COALESCE(v,ov)->>'selection_id')
  WHEN 'rw_root' THEN jsonb_build_object('portfolio_id',r)
  WHEN 'rw_revision' THEN jsonb_build_object('revision_id',COALESCE(v,ov)->>'revision_id')
 END;
 -- AFTER fires only for actual row outcomes, unlike BEFORE with ON CONFLICT.
 INSERT INTO rw_journal(backend_pid,xid,root_id,table_name,action,row_key,old_row,new_row) VALUES(l.backend_pid,l.xid,r,TG_TABLE_NAME,TG_OP,key,ov,v);
 IF (SELECT count(*) FROM rw_journal j WHERE j.backend_pid=l.backend_pid AND j.xid=l.xid)>2048 THEN RAISE EXCEPTION 'RW_JOURNAL_CAP'; END IF;
 RETURN NULL;
END $$;

DO $$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['portfolio','account','ledger_event','benchmark_selection','rw_root','rw_revision'] LOOP
  EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY','__RW_SCHEMA__',t);
  -- The owner is NOLOGIN and bypasses the policies (FORCE is not enabled: the definer functions must resolve rows hidden from the caller).
  EXECUTE format('CREATE POLICY rw_baseline ON %I.%I AS PERMISSIVE FOR ALL TO __RW_EXECUTOR__ USING(true) WITH CHECK(true)','__RW_SCHEMA__',t);
  EXECUTE format('CREATE POLICY rw_row_guard ON %I.%I AS RESTRICTIVE FOR ALL TO __RW_EXECUTOR__ USING(%I.rw_row_allowed(%L,to_jsonb(%I),false)) WITH CHECK(%I.rw_row_allowed(%L,to_jsonb(%I),true))','__RW_SCHEMA__',t,'__RW_SCHEMA__',t,t,'__RW_SCHEMA__',t,t);
  EXECUTE format('CREATE TRIGGER zz_rw_write BEFORE INSERT OR UPDATE OR DELETE ON %I.%I FOR EACH ROW EXECUTE FUNCTION %I.rw_write_fence()','__RW_SCHEMA__',t,'__RW_SCHEMA__');
  EXECUTE format('CREATE TRIGGER zz_rw_journal AFTER INSERT OR UPDATE OR DELETE ON %I.%I FOR EACH ROW EXECUTE FUNCTION %I.rw_journal_after()','__RW_SCHEMA__',t,'__RW_SCHEMA__');
  EXECUTE format('CREATE TRIGGER zz_rw_truncate BEFORE TRUNCATE ON %I.%I FOR EACH STATEMENT EXECUTE FUNCTION %I.rw_write_fence()','__RW_SCHEMA__',t,'__RW_SCHEMA__');
 END LOOP;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- STATE DIGEST of a root (F2's gw_state, over the S2 tables): the seal records it, the bundle guard recomputes it.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rw_state(r uuid) RETURNS text
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT encode(sha256(convert_to(COALESCE(jsonb_agg(x ORDER BY x::text),'[]'::jsonb)::text,'UTF8')),'hex') FROM (
 SELECT jsonb_build_object('table','portfolio','row',to_jsonb(t)) x FROM portfolio t WHERE portfolio_id=r
 UNION ALL SELECT jsonb_build_object('table','account','row',to_jsonb(t)) FROM account t WHERE portfolio_id=r
 UNION ALL SELECT jsonb_build_object('table','ledger_event','row',to_jsonb(t)) FROM ledger_event t WHERE account_id IN (SELECT account_id FROM account WHERE portfolio_id=r)
 UNION ALL SELECT jsonb_build_object('table','benchmark_selection','row',to_jsonb(t)) FROM benchmark_selection t WHERE portfolio_id=r
 UNION ALL SELECT jsonb_build_object('table','rw_root','row',to_jsonb(t)) FROM rw_root t WHERE portfolio_id=r
 UNION ALL SELECT jsonb_build_object('table','rw_revision','row',to_jsonb(t)) FROM rw_revision t WHERE portfolio_id=r
 ) all_rows
$$;

-- ---------------------------------------------------------------------------------------------------------------------
-- THE MANDATORY LINK (design 4.2 build table; PD-0059; case B06). A sealed create stands on exactly one registered provenance
-- candidate that the loader bound to the lease's published context. rw_seal takes the candidate's digest and refuses without it; the
-- bundle guard and the archive re-check it. The registry is read here and referenced nowhere.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rw_link_verify(p_context text,p_prov text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE c jsonb; f text; s jsonb; reg_a text[]; reg_b text[];
BEGIN
 IF p_prov IS NULL OR p_prov !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RW_LINK_MISSING'; END IF;
 SELECT convert_from(x.context,'UTF8')::jsonb,x.financial_context_sha256 INTO c,f FROM rwp_context x WHERE x.context_sha256=p_prov;
 IF NOT FOUND OR NOT EXISTS(SELECT 1 FROM rwp_registration r WHERE r.context_sha256=p_prov) THEN RAISE EXCEPTION 'RW_LINK_MISSING'; END IF;
 IF f IS DISTINCT FROM p_context THEN RAISE EXCEPTION 'RW_LINK_DIFFERS'; END IF;
 SELECT convert_from(sn.snapshot,'UTF8')::jsonb INTO s FROM rw_snapshot sn WHERE sn.context_id=p_context;
 IF s IS NULL OR c->>'scope' IS DISTINCT FROM s->>'scope' OR c->>'state' IS DISTINCT FROM 'INTEGRITY_BOUND_NOT_ADMITTED'
    OR c->'promotable' IS DISTINCT FROM 'false'::jsonb OR c->'source_admitted' IS DISTINCT FROM 'false'::jsonb THEN RAISE EXCEPTION 'RW_LINK_DIFFERS'; END IF;
 SELECT array_agg((m.value->>'payload_sha256')||':'||(m.value->>'manifest_sha256') ORDER BY (m.value->>'payload_sha256'),(m.value->>'manifest_sha256')) INTO reg_a
  FROM jsonb_array_elements(c->'members') m;
 SELECT array_agg((m.value->>'payload_sha256')||':'||(m.value->>'manifest_sha256') ORDER BY (m.value->>'payload_sha256'),(m.value->>'manifest_sha256')) INTO reg_b
  FROM jsonb_array_elements(s->'members') m;
 IF reg_a IS DISTINCT FROM reg_b THEN RAISE EXCEPTION 'RW_LINK_DIFFERS'; END IF;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- ACCEPTANCE OF A SEALED RESULT (design 4.2 build table; 4.4). One dispatcher, two branches:
--   * the REAL branch's predicates are in this file (rw_check_real): O4a (the result is not synthetic) and O4b (F8B is a dry run);
--   * the FICTIONAL branch's predicates (rw_check_fictional) are the TEST-only file, real_workspace_fictional_v1.sql, which a REAL install
--     does not run. The dispatcher names it at run time and only for the scope SYNTHETIC_TEST.
-- Both branches share the structural checks below and the ORIGIN-LABEL ROW GUARD: the root's origin labels, the labels the result states,
-- and the root's wording must be those of the scope of the root's context (REAL_SOURCE only under REAL, SYNTHETIC_TEST only under the two
-- test scopes). Every predicate failure is reported together as RW_SEAL_REFUSED with the codes in DETAIL; a structural failure raises its
-- own code at once. O4 needs a result with synthetic = false, which invented data never has, so the REAL branch's ACCEPTED side
-- first runs at R8 (design 4.4); R3 shows its refusals.
-- ---------------------------------------------------------------------------------------------------------------------
-- THE REAL BRANCH'S CHECK of the bytes the performance service issues, AS ISSUED: `ComputationResult.to_canonical_dict()`
-- (src/performance/manifest.py): {manifest_id, manifest, result_digest, metrics}, a FLAT manifest (finweb.computation_manifest/1) and
-- result_digest = sha256(canonical metrics list) (performance/results.py metrics_digest). Nothing is wrapped: every predicate below reads
-- a field of those bytes, or of the gateway's own envelope (owner, root, revision, operation, pin, context: fields the gateway knows).
--   O4a  the manifest and every metric state synthetic = false      (manifest.synthetic, metrics[].synthetic)
--   O4b  the F8B split detection ran as a dry run                   (manifest.split_detection)
--   RW_REAL_RELEASE_DIFFERS  the release the service read is the snapshot's   (manifest.parent_release_id, else manifest.release_id;
--                                                                    the snapshot's release.release_id)
--   RW_REAL_POLICY_DIFFERS   the F8B confirmation policy it ran under is the snapshot's (manifest.detection_policy[0] = ["digest", X];
--                                                                    snapshot.f8b_policy_digest = X)
--   RW_REAL_PROJECTION_DIFFERS  snapshot.projection_digest is md_release.projection_digest of the snapshot's release (read from the database,
--                               not from the manifest, which has no such field; a release the database does not hold differs)
--   RW_REAL_REGISTRY_DIFFERS    manifest.source_registry_digest = snapshot.registry.used_source_digest (R4b computes the latter with the engine's
--                               own source_registry_digest; until it does, every real-branch output lists this code)
--   RW_REAL_MEMBERS_DIFFER      the snapshot's members (payload_sha256, source_id) are exactly the release's files (md_release_file joined to md_file:
--                               file_sha256, source_id), read from the database; with the registry predicate this makes "the sources the snapshot
--                               names" the "sources with a file in the release" (RR-L4)
-- NOT checked here (disposition note, implementation/CP7_F1_R3_SEAL_PREDICATE_DISPOSITION.md): the snapshot's identity_digest (the manifest's
-- identity_digest digests the identity FACTS this computation asked for, a different quantity; 5.2), and an origin object in the manifest (it has
-- none; the stored response carries the origin and the origin-label row guard in rw_check_artifact enforces it against the root row; 5.4).
CREATE FUNCTION __RW_SCHEMA__.rw_check_real(p_env jsonb,p_issued jsonb,p_response jsonb,p_ctx jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE codes text[]:='{}'; m jsonb:=p_issued->'manifest'; snap jsonb:=p_ctx->'snapshot'; metrics jsonb:=p_issued->'metrics';
BEGIN
 IF NOT rw_keys(p_env,ARRAY['schema','scope','synthetic','owner_id','root_id','operation_id','revision_id','ledger_pin','context_id','generation',
    'issued_sha256','response_sha256','manifest_id','result_digest']) THEN RAISE EXCEPTION 'RW_ENVELOPE_SHAPE'; END IF;
 IF p_env->>'schema' IS DISTINCT FROM 'finweb.real.issued_envelope/1' THEN RAISE EXCEPTION 'RW_ENVELOPE_DIFFERS'; END IF;
 IF NOT rw_keys(p_issued,ARRAY['manifest_id','manifest','result_digest','metrics']) OR jsonb_typeof(metrics) IS DISTINCT FROM 'array'
    OR jsonb_array_length(metrics) NOT BETWEEN 1 AND 4096 THEN RAISE EXCEPTION 'RW_ISSUED_SHAPE'; END IF;
 IF p_issued->>'result_digest' IS DISTINCT FROM encode(sha256(convert_to(rw_json(metrics),'UTF8')),'hex') THEN RAISE EXCEPTION 'RW_NATIVE_DIGEST_DIFFERS'; END IF;
 IF m->>'schema' IS DISTINCT FROM 'finweb.computation_manifest/1' OR m->>'state_kind' IS DISTINCT FROM 'ACTUAL' OR m->>'scope' IS DISTINCT FROM 'PORTFOLIO'
    OR m->>'portfolio_id' IS DISTINCT FROM p_ctx->>'root_id' OR m->'ledger_version' IS DISTINCT FROM p_ctx->'ledger_pin'
    OR m->>'as_of' IS DISTINCT FROM p_ctx->>'as_of' OR m->>'reporting_currency' IS DISTINCT FROM p_ctx->>'reporting_currency'
    OR jsonb_typeof(m->'synthetic') IS DISTINCT FROM 'boolean' OR jsonb_typeof(m->'split_detection') IS DISTINCT FROM 'string'
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(metrics) x WHERE jsonb_typeof(x.value) IS DISTINCT FROM 'object' OR jsonb_typeof(x.value->'synthetic') IS DISTINCT FROM 'boolean')
    THEN RAISE EXCEPTION 'RW_MANIFEST_DIFFERS'; END IF;
 -- O4a: the service result is synthetic = false: its manifest and every metric.
 IF m->'synthetic' IS DISTINCT FROM 'false'::jsonb
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(metrics) x WHERE x.value->'synthetic' IS DISTINCT FROM 'false'::jsonb) THEN
  codes:=array_append(codes,'RW_O4A_SYNTHETIC_RESULT');
 END IF;
 -- O4b: the F8B split detection ran as a dry run.
 IF m->>'split_detection' IS DISTINCT FROM 'F8B_DRY_RUN' THEN codes:=array_append(codes,'RW_O4B_F8B_MODE'); END IF;
 IF COALESCE(m->>'parent_release_id',m->>'release_id') IS DISTINCT FROM snap->'release'->>'release_id' THEN codes:=array_append(codes,'RW_REAL_RELEASE_DIFFERS'); END IF;
 IF jsonb_typeof(m->'detection_policy') IS DISTINCT FROM 'array' OR m->'detection_policy'->0->>0 IS DISTINCT FROM 'digest'
    OR m->'detection_policy'->0->>1 IS DISTINCT FROM snap->>'f8b_policy_digest' THEN codes:=array_append(codes,'RW_REAL_POLICY_DIFFERS'); END IF;
 -- The snapshot's projection digest is the one the database holds for the snapshot's release (disposition note 5.1). md_release is append-only and
 -- a release id has one digest, so with the release-id binding above this pins the projection the service read. A release the database does not
 -- hold is a difference (no row: the subquery is NULL).
 IF (SELECT r.projection_digest FROM md_release r WHERE r.release_id=snap->'release'->>'release_id') IS DISTINCT FROM snap->>'projection_digest' THEN
  codes:=array_append(codes,'RW_REAL_PROJECTION_DIFFERS');
 END IF;
 -- The registry the service digested is the snapshot's (disposition note 5.3): the manifest's source_registry_digest is the engine's digest of the
 -- source records of the sources with a file in the release read; R4b computes the snapshot's used_source_digest with the same engine function.
 IF m->>'source_registry_digest' IS DISTINCT FROM snap->'registry'->>'used_source_digest' THEN codes:=array_append(codes,'RW_REAL_REGISTRY_DIFFERS'); END IF;
 -- The snapshot's members ARE the release's files (re-review RR-L4). The manifest digests the registry records of the sources with a file in the
 -- release (md_release_file joined to md_file); the snapshot's used_source_digest is over its members' sources. The two digests can agree only when
 -- those source sets agree, and nothing else compared the snapshot's members with the release the database holds. This compares the (file hash,
 -- source id) pairs themselves, so no extra snapshot field and no SQL-side digest is needed: R4b builds the members from the release's own rows.
 -- Fictional branch: not applied (the integration's world is inline and has no md_release row; T10).
 IF (SELECT COALESCE(jsonb_agg(jsonb_build_array(f.file_sha256,f.source_id) ORDER BY f.file_sha256,f.source_id),'[]'::jsonb)
       FROM md_release_file rf JOIN md_file f ON f.file_sha256=rf.file_sha256 WHERE rf.release_id=snap->'release'->>'release_id')
    IS DISTINCT FROM
    (SELECT COALESCE(jsonb_agg(jsonb_build_array(x.value->>'payload_sha256',x.value->>'source_id') ORDER BY x.value->>'payload_sha256',x.value->>'source_id'),'[]'::jsonb)
       FROM jsonb_array_elements(CASE WHEN jsonb_typeof(snap->'members')='array' THEN snap->'members' ELSE '[]'::jsonb END) x) THEN
  codes:=array_append(codes,'RW_REAL_MEMBERS_DIFFER');
 END IF;
 RETURN codes;
END $$;

CREATE FUNCTION __RW_SCHEMA__.rw_check_artifact(a __RW_SCHEMA__.rw_artifact) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE e jsonb; issued_obj jsonb; response_obj jsonb; snapshot jsonb; scope text; expected jsonb; ctx jsonb;
 root __RW_SCHEMA__.rw_root%ROWTYPE; rev __RW_SCHEMA__.rw_revision%ROWTYPE; pf __RW_SCHEMA__.portfolio%ROWTYPE; m jsonb; vm jsonb;
 codes text[]:='{}'; origin_row jsonb; flags_bad boolean;
 -- The manifest schemas the services issue today (grep of src/: computation, diversification, drift, insight, risk) and the market-data file manifests.
 rooted_manifests text[]:=ARRAY['finweb.computation_manifest/1','finweb.diversification_manifest/1','finweb.drift_manifest/1','finweb.insight_manifest/1','finweb.risk_manifest/1'];
 file_manifests text[]:=ARRAY['finweb.marketdata.file_manifest/1','finweb.marketdata.file_manifest/2'];
BEGIN
 -- Every byte bound BEFORE decoding or parsing.
 IF a.issued IS NULL OR octet_length(a.issued) NOT BETWEEN 2 AND 2000000 OR a.response IS NULL OR octet_length(a.response) NOT BETWEEN 2 AND 6000000
    OR a.envelope IS NULL OR octet_length(a.envelope) NOT BETWEEN 2 AND 65536 THEN RAISE EXCEPTION 'RW_ARCHIVE_BOUNDS'; END IF;
 IF a.issued_sha256 IS DISTINCT FROM encode(sha256(a.issued),'hex') OR a.response_sha256 IS DISTINCT FROM encode(sha256(a.response),'hex')
    OR a.envelope_sha256 IS DISTINCT FROM encode(sha256(a.envelope),'hex') THEN RAISE EXCEPTION 'RW_ARCHIVE_DIFFERS'; END IF;
 BEGIN
  e:=convert_from(a.envelope,'UTF8')::jsonb; issued_obj:=convert_from(a.issued,'UTF8')::jsonb; response_obj:=convert_from(a.response,'UTF8')::jsonb;
 EXCEPTION WHEN others THEN
  RAISE EXCEPTION 'RW_ENVELOPE_SHAPE';
 END;
 -- The key set of the envelope is the branch's (rw_check_real / rw_check_fictional); the canonical form is common.
 IF jsonb_typeof(e) IS DISTINCT FROM 'object' OR jsonb_typeof(issued_obj) IS DISTINCT FROM 'object' OR jsonb_typeof(response_obj) IS DISTINCT FROM 'object'
    OR convert_to(rw_json(e),'UTF8') IS DISTINCT FROM a.envelope THEN RAISE EXCEPTION 'RW_ENVELOPE_SHAPE'; END IF;
 SELECT convert_from(s.snapshot,'UTF8')::jsonb INTO snapshot FROM rw_snapshot s WHERE s.context_id=a.context_id;
 IF snapshot IS NULL THEN RAISE EXCEPTION 'RW_SOURCE_DIFFERS'; END IF;
 scope:=snapshot->>'scope';
 expected:=rw_origin_expected(scope);
 IF expected IS NULL THEN RAISE EXCEPTION 'RW_SOURCE_DIFFERS'; END IF;
 IF e->>'scope' IS DISTINCT FROM scope OR jsonb_typeof(e->'synthetic') IS DISTINCT FROM 'boolean'
    OR e->>'owner_id' IS DISTINCT FROM a.owner_id::text OR e->>'root_id' IS DISTINCT FROM a.root_id::text OR e->>'operation_id' IS DISTINCT FROM a.operation_id::text
    OR e->>'revision_id' IS DISTINCT FROM a.revision_id::text OR e->'generation' IS DISTINCT FROM to_jsonb(a.generation) OR e->'ledger_pin' IS DISTINCT FROM to_jsonb(a.ledger_pin)
    OR e->>'context_id' IS DISTINCT FROM a.context_id OR e->>'issued_sha256' IS DISTINCT FROM a.issued_sha256 OR e->>'response_sha256' IS DISTINCT FROM a.response_sha256
    THEN RAISE EXCEPTION 'RW_ENVELOPE_DIFFERS'; END IF;
 -- The stored root, revision and portfolio this bundle stands on.
 SELECT * INTO root FROM rw_root r WHERE r.portfolio_id=a.root_id AND r.context_id=a.context_id;
 SELECT * INTO rev FROM rw_revision v WHERE v.portfolio_id=a.root_id AND v.revision_id=a.revision_id;
 SELECT * INTO pf FROM portfolio p WHERE p.portfolio_id=a.root_id AND p.user_id=a.owner_id;
 IF root.portfolio_id IS NULL OR rev.revision_id IS NULL OR pf.portfolio_id IS NULL THEN RAISE EXCEPTION 'RW_ROOT_DIFFERS'; END IF;
 -- The response is the persisted snapshot, equal to the stored root and revision rows.
 IF convert_to(rw_json(response_obj),'UTF8') IS DISTINCT FROM a.response OR response_obj IS DISTINCT FROM root.snapshot_json::jsonb OR response_obj IS DISTINCT FROM rev.snapshot_json::jsonb
    OR response_obj->>'portfolio_id' IS DISTINCT FROM a.root_id::text OR response_obj->>'as_of' IS DISTINCT FROM rev.as_of::text
    OR response_obj->'persisted' IS DISTINCT FROM 'true'::jsonb OR response_obj->>'reporting_currency' IS DISTINCT FROM pf.reporting_currency
    OR jsonb_typeof(response_obj->'synthetic') IS DISTINCT FROM 'boolean' OR a.ledger_pin IS DISTINCT FROM rev.ledger_version THEN RAISE EXCEPTION 'RW_RESPONSE_DIFFERS'; END IF;
 -- The issued bytes, whichever service issued them: canonical, an object with a manifest, and the manifest's digest recomputed. The rest of the
 -- native shape (keys, the result digest, the manifest's fields) is the branch's, because the two services issue different documents.
 IF convert_to(rw_json(issued_obj),'UTF8') IS DISTINCT FROM a.issued OR jsonb_typeof(issued_obj->'manifest') IS DISTINCT FROM 'object'
    THEN RAISE EXCEPTION 'RW_ISSUED_SHAPE'; END IF;
 m:=issued_obj->'manifest'; vm:=m->'valuation_manifest';
 -- THE ROOT BINDING (PD-0073 condition 1): every manifest the issued bytes hold, nested ones included, names THIS root. portfolio_id is inside the
 -- manifest id, so a manifest cannot be moved to a root of another origin. A manifest with no portfolio_id (the diversification engine defaults it
 -- to None) is refused. Three rules over every object anywhere in the issued bytes (re-review RR-L1: a naming pattern decided what was scanned, so
 -- an unlisted spelling or a manifest with no schema key escaped):
 --  (1) an object that carries a portfolio_id key names THIS root, whatever its schema (or none);
 --  (2) an object whose schema is one of the manifest schemas the services issue today (rooted: they must carry portfolio_id = the root) is checked;
 --  (3) an object whose schema contains "manifest" in any case and is on neither list is refused: a new manifest schema is added to this list by a
 --      reviewed change, never accepted by spelling. The market-data file manifests are listed apart: they describe a file, have no portfolio_id,
 --      and may be cited in a result; they neither need the key nor are refused (if one carries the key, rule (1) applies).
 IF m->>'portfolio_id' IS DISTINCT FROM a.root_id::text OR EXISTS(
     SELECT 1 FROM jsonb_path_query(issued_obj,'lax $.**') x(v)
      WHERE jsonb_typeof(x.v)='object' AND (
        (x.v ? 'portfolio_id' AND x.v->'portfolio_id' IS DISTINCT FROM to_jsonb(a.root_id::text))
        OR (x.v->>'schema' = ANY(rooted_manifests) AND x.v->>'portfolio_id' IS DISTINCT FROM a.root_id::text)
        OR (x.v->>'schema' ~* 'manifest' AND NOT (x.v->>'schema' = ANY(rooted_manifests) OR x.v->>'schema' = ANY(file_manifests))))) THEN
  RAISE EXCEPTION 'RW_MANIFEST_DIFFERS';
 END IF;
 IF issued_obj->>'manifest_id' IS DISTINCT FROM encode(sha256(convert_to(rw_json(m),'UTF8')),'hex')
    OR e->>'manifest_id' IS DISTINCT FROM issued_obj->>'manifest_id' OR e->>'result_digest' IS DISTINCT FROM issued_obj->>'result_digest' THEN RAISE EXCEPTION 'RW_NATIVE_DIGEST_DIFFERS'; END IF;
 -- THE ORIGIN-LABEL ROW GUARD (design 1.1): the root's labels, the labels the result states and the root's wording follow the scope.
 origin_row:=jsonb_build_object('market_origin',root.market_origin,'ledger_origin',root.ledger_origin,'personal_holdings',root.personal_holdings,'synthetic',root.synthetic);
 -- The synthetic flags the issued bytes state, wherever they state them (the manifest, the nested valuation manifest of the CP5 result, each
 -- metric that carries one), and the envelope's and the response's, are the scope's axis.
 SELECT EXISTS(SELECT 1 FROM (
   SELECT m->'synthetic' AS f
   UNION ALL SELECT vm->'synthetic' WHERE jsonb_typeof(vm)='object'
   UNION ALL SELECT x.value->'synthetic' FROM jsonb_array_elements(CASE WHEN jsonb_typeof(issued_obj->'metrics')='array' THEN issued_obj->'metrics' ELSE '[]'::jsonb END) x
    WHERE jsonb_typeof(x.value)='object' AND x.value ? 'synthetic'
  ) t WHERE t.f IS DISTINCT FROM expected->'synthetic') INTO flags_bad;
 IF origin_row IS DISTINCT FROM expected
    -- the synthetic flag the result states, wherever it states it, is the scope's axis: invented data is never marked synthetic = false,
    -- so a TEST_SWITCH result that says false is a mismatch, and a REAL result that says true is one
    OR e->'synthetic' IS DISTINCT FROM expected->'synthetic' OR flags_bad OR response_obj->'synthetic' IS DISTINCT FROM expected->'synthetic'
    -- the stored result carries the root's four origin labels (PD-0073; the engine manifest carries none)
    OR response_obj->'origin' IS DISTINCT FROM origin_row
    OR (expected->>'synthetic'='false' AND (root.name ~* '(fictional|sandbox|synthetic|invented)' OR root.account_label ~* '(fictional|sandbox|synthetic|invented)' OR root.opening_label ~* '(fictional|sandbox|synthetic|invented)'))
    OR (expected->>'synthetic'='true' AND position('REAL_SOURCE' IN root.name||root.account_label||root.opening_label||root.request_json||root.snapshot_json||convert_from(a.issued,'UTF8'))>0) THEN
  codes:=array_append(codes,'RW_ORIGIN_MISMATCH');
 END IF;
 -- What the branch needs to know about the stored bundle: the snapshot and the gateway's own identifiers (the service issues none of them).
 ctx:=jsonb_build_object('snapshot',snapshot,'scope',scope,'owner_id',a.owner_id::text,'root_id',a.root_id::text,'revision_id',a.revision_id::text,
   'operation_id',a.operation_id::text,'ledger_pin',a.ledger_pin,'generation',a.generation,'context_id',a.context_id,'as_of',rev.as_of::text,
   'reporting_currency',pf.reporting_currency);
 IF scope='SYNTHETIC_TEST' THEN
  codes:=codes||rw_check_fictional(e,issued_obj,response_obj,ctx);
 ELSE
  codes:=codes||rw_check_real(e,issued_obj,response_obj,ctx);
 END IF;
 IF cardinality(codes)>0 THEN RAISE EXCEPTION 'RW_SEAL_REFUSED' USING DETAIL=array_to_string(codes,','); END IF;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- BUNDLE VALIDATION AT COMMIT AND AT SEAL (F2's gw_validate, re-keyed). A create lease must be SEALED with exactly its own bundle;
-- a read-phase lease must have written nothing. The deferred constraint trigger below fires it at COMMIT.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rw_validate(pid integer,tx text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE l __RW_SCHEMA__.rw_lease%ROWTYPE; op __RW_SCHEMA__.rw_operation%ROWTYPE; a __RW_SCHEMA__.rw_artifact%ROWTYPE; j __RW_SCHEMA__.rw_journal%ROWTYPE; actual jsonb; n bigint; pin bigint;
BEGIN
 SELECT * INTO l FROM rw_lease x WHERE x.backend_pid=pid AND x.xid=tx;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_BUNDLE_MISSING'; END IF;
 IF l.phase IN ('READONLY','REPLAY') THEN
  IF EXISTS(SELECT 1 FROM rw_journal x WHERE x.backend_pid=pid AND x.xid=tx) THEN RAISE EXCEPTION 'RW_READONLY_MUTATED'; END IF;
  RETURN;
 END IF;
 IF l.phase IS DISTINCT FROM 'SEALED' THEN RAISE EXCEPTION 'RW_UNSEALED'; END IF;
 SELECT * INTO op FROM rw_operation x WHERE x.owner_id=l.owner_id AND x.operation_id=l.operation_id;
 SELECT * INTO a FROM rw_artifact x WHERE x.owner_id=l.owner_id AND x.operation_id=l.operation_id;
 IF op.owner_id IS NULL OR a.owner_id IS NULL OR op.root_id IS DISTINCT FROM l.root_id OR op.context_id IS DISTINCT FROM l.context_id OR op.generation IS DISTINCT FROM l.generation
    OR op.command_sha256 IS DISTINCT FROM l.command_sha256 OR a.root_id IS DISTINCT FROM op.root_id OR a.context_id IS DISTINCT FROM op.context_id
    OR a.generation IS DISTINCT FROM op.generation OR a.revision_id IS DISTINCT FROM op.revision_id THEN RAISE EXCEPTION 'RW_BUNDLE_DIFFERS'; END IF;
 SELECT count(*) INTO n FROM rw_journal x WHERE x.backend_pid=pid AND x.xid=tx;
 IF n<1 OR n<>op.journal_count OR op.state_sha256 IS DISTINCT FROM l.state_sha256 OR l.state_sha256 IS DISTINCT FROM rw_state(l.root_id) THEN RAISE EXCEPTION 'RW_JOURNAL_DIFFERS'; END IF;
 IF NOT EXISTS(SELECT 1 FROM portfolio p WHERE p.portfolio_id=l.root_id AND p.user_id=l.owner_id) OR NOT EXISTS(SELECT 1 FROM rw_root r WHERE r.portfolio_id=l.root_id AND r.context_id=l.context_id) THEN
  RAISE EXCEPTION 'RW_ROOT_DIFFERS';
 END IF;
 SELECT max(e.ledger_seq) INTO pin FROM ledger_event e JOIN account c USING(account_id) WHERE c.portfolio_id=l.root_id;
 IF pin IS DISTINCT FROM a.ledger_pin THEN RAISE EXCEPTION 'RW_PIN_DIFFERS'; END IF;
 -- A CREATE writes the root row, its first revision and the portfolio, in this transaction and no other.
 IF NOT EXISTS(SELECT 1 FROM rw_revision v WHERE v.portfolio_id=l.root_id AND v.revision_id=op.revision_id AND v.operation_id=l.operation_id AND v.ledger_version=pin)
    OR NOT EXISTS(SELECT 1 FROM rw_journal x WHERE x.backend_pid=pid AND x.xid=tx AND x.table_name='portfolio' AND x.action='INSERT')
    OR NOT EXISTS(SELECT 1 FROM rw_journal x WHERE x.backend_pid=pid AND x.xid=tx AND x.table_name='rw_root' AND x.action='INSERT')
    OR NOT EXISTS(SELECT 1 FROM rw_journal x WHERE x.backend_pid=pid AND x.xid=tx AND x.table_name='rw_revision' AND x.action='INSERT') THEN RAISE EXCEPTION 'RW_CREATE_DIFFERS'; END IF;
 FOR j IN SELECT * FROM rw_journal x WHERE x.backend_pid=pid AND x.xid=tx LOOP
  IF j.root_id IS DISTINCT FROM l.root_id OR j.action<>'INSERT' THEN RAISE EXCEPTION 'RW_JOURNAL_DIFFERS'; END IF;
  EXECUTE format('SELECT to_jsonb(t) FROM %I.%I t WHERE to_jsonb(t) @> $1','__RW_SCHEMA__',j.table_name) INTO actual USING j.row_key;
  IF actual IS DISTINCT FROM j.new_row THEN RAISE EXCEPTION 'RW_JOURNAL_DIFFERS'; END IF;
 END LOOP;
 IF a.issued_sha256 IS DISTINCT FROM encode(sha256(a.issued),'hex') OR a.response_sha256 IS DISTINCT FROM encode(sha256(a.response),'hex') THEN RAISE EXCEPTION 'RW_ARCHIVE_DIFFERS'; END IF;
 PERFORM rw_link_verify(op.context_id,op.provenance_context_sha256);
 PERFORM rw_check_artifact(a);
END $$;

CREATE FUNCTION __RW_SCHEMA__.rw_bundle_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_validate(NEW.backend_pid,NEW.xid); RETURN NEW;
END $$;
-- The bundle guard is a constraint trigger of its own on the lease table, DEFERRABLE INITIALLY DEFERRED: it fires inside COMMIT unless
-- product code moves it early BY NAME. It is a different trigger from the deadline guard (rw_lease_deadline_guard, R1) on purpose, and
-- its name is unique among the schema's constraints (the catalog audit checks it).
CREATE CONSTRAINT TRIGGER rw_bundle_complete AFTER INSERT ON __RW_SCHEMA__.rw_lease DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rw_bundle_guard();

-- SEAL (F2's gw_seal, one kind): freezes the create bundle, requires the link, validates at statement time. Refused at or after complete_by.
CREATE FUNCTION __RW_SCHEMA__.rw_seal(rev uuid,issued_b bytea,response_b bytea,envelope_b bytea,prov text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE l __RW_SCHEMA__.rw_lease%ROWTYPE; n bigint; pin bigint; state text;
BEGIN
 IF rev IS NULL OR issued_b IS NULL OR octet_length(issued_b) NOT BETWEEN 2 AND 2000000 OR response_b IS NULL OR octet_length(response_b) NOT BETWEEN 2 AND 6000000
    OR envelope_b IS NULL OR octet_length(envelope_b) NOT BETWEEN 2 AND 65536 THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 SELECT * INTO l FROM rw_lease x WHERE x.backend_pid=pg_backend_pid() AND x.xid=pg_current_xact_id()::text FOR UPDATE;
 IF NOT FOUND OR l.purpose IS DISTINCT FROM 'EXECUTE_CREATE' OR l.phase IS DISTINCT FROM 'OPEN' THEN RAISE EXCEPTION 'RW_SEAL_REFUSED' USING DETAIL='LEASE'; END IF;
 IF rw_reached(clock_timestamp(),l.complete_by) THEN RAISE EXCEPTION 'RW_DEADLINE'; END IF;
 -- The mandatory link: no registered candidate bound to this context, no seal (case B06).
 PERFORM rw_link_verify(l.context_id,prov);
 SELECT count(*) INTO n FROM rw_journal x WHERE x.backend_pid=l.backend_pid AND x.xid=l.xid;
 SELECT max(e.ledger_seq) INTO pin FROM ledger_event e JOIN account a USING(account_id) WHERE a.portfolio_id=l.root_id;
 state:=rw_state(l.root_id);
 INSERT INTO rw_artifact VALUES(l.owner_id,l.operation_id,l.root_id,l.context_id,l.generation,rev,pin,issued_b,encode(sha256(issued_b),'hex'),response_b,encode(sha256(response_b),'hex'),envelope_b,encode(sha256(envelope_b),'hex'));
 INSERT INTO rw_operation VALUES(l.owner_id,l.operation_id,l.root_id,l.context_id,l.generation,l.command_sha256,'CREATE',rev,n,state,prov);
 UPDATE rw_lease SET phase='SEALED',state_sha256=state WHERE backend_pid=l.backend_pid AND xid=l.xid;
 PERFORM rw_validate(l.backend_pid,l.xid);
END $$;

-- ARCHIVE READ (F2's gw_archive, plus the TIME CHECK F2 lacks, technical TR3R-L4): the bundle of one operation, for a lease on the same
-- owner, root and context. Refused at or after complete_by, so a holder who keeps the transaction open past it cannot read.
CREATE FUNCTION __RW_SCHEMA__.rw_archive(o uuid,op uuid) RETURNS TABLE(issued bytea,response bytea,envelope bytea,issued_sha256 text,response_sha256 text,revision_id uuid,ledger_pin bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE l __RW_SCHEMA__.rw_lease%ROWTYPE; a __RW_SCHEMA__.rw_artifact%ROWTYPE; original __RW_SCHEMA__.rw_operation%ROWTYPE;
BEGIN
 IF o IS NULL OR op IS NULL THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 SELECT * INTO l FROM rw_lease x WHERE x.backend_pid=pg_backend_pid() AND x.xid=pg_current_xact_id()::text;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_LEASE_REQUIRED'; END IF;
 IF rw_reached(clock_timestamp(),l.complete_by) THEN RAISE EXCEPTION 'RW_DEADLINE'; END IF;
 SELECT * INTO a FROM rw_artifact x WHERE x.owner_id=o AND x.operation_id=op;
 IF a.owner_id IS NULL OR l.owner_id IS DISTINCT FROM o OR l.root_id IS DISTINCT FROM a.root_id OR l.context_id IS DISTINCT FROM a.context_id THEN RAISE EXCEPTION 'RW_NOT_FOUND'; END IF;
 IF a.issued_sha256 IS DISTINCT FROM encode(sha256(a.issued),'hex') OR a.response_sha256 IS DISTINCT FROM encode(sha256(a.response),'hex') THEN RAISE EXCEPTION 'RW_ARCHIVE_DIFFERS'; END IF;
 SELECT * INTO original FROM rw_operation x WHERE x.owner_id=o AND x.operation_id=op;
 IF NOT FOUND OR original.root_id IS DISTINCT FROM a.root_id OR original.context_id IS DISTINCT FROM a.context_id OR original.generation IS DISTINCT FROM a.generation
    OR original.revision_id IS DISTINCT FROM a.revision_id THEN RAISE EXCEPTION 'RW_OPERATION_DIFFERS'; END IF;
 PERFORM rw_link_verify(original.context_id,original.provenance_context_sha256);
 PERFORM rw_check_artifact(a);
 RETURN QUERY SELECT a.issued,a.response,a.envelope,a.issued_sha256,a.response_sha256,a.revision_id,a.ledger_pin;
END $$;

-- The idempotency pre-check (F2's gw_precheck): for an operation id that was already sealed and committed, the identifiers of its root, so
-- that the caller can re-admit it as a REPLAY. It returns identifiers only. A different command digest is a conflict.
CREATE FUNCTION __RW_SCHEMA__.rw_precheck(o uuid,op uuid,h text) RETURNS TABLE(root_id uuid,context_id text,generation bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE v __RW_SCHEMA__.rw_operation%ROWTYPE;
BEGIN
 IF o IS NULL OR op IS NULL OR h IS NULL OR h !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 SELECT * INTO v FROM rw_operation x WHERE x.owner_id=o AND x.operation_id=op;
 IF FOUND THEN
  IF v.command_sha256 IS DISTINCT FROM h THEN RAISE EXCEPTION 'RW_IDEMPOTENCY_CONFLICT'; END IF;
  RETURN QUERY SELECT v.root_id,v.context_id,v.generation;
 END IF;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- THE THIRTEEN LEASE-CHECKED md_* READ FUNCTIONS (design 2.6 item 6; PD-0069, PD-0070 decision 2). One definer function per md_* table,
-- RETURNS SETOF the table's row type, `rw_md_<table>(release_id text)`. The executor holds EXECUTE on them and no privilege on any md_*
-- table. Each call checks, in this order, and any failure REFUSES (it never filters), with the one code RW_MD_READ_REFUSED and the
-- reason in DETAIL: (a) a lease row for the current (backend_pid, xid); (b) its purpose is EXECUTE_CREATE or EXECUTE_REPRODUCE; (c)
-- the clock is before complete_by, at statement time on every call; (d) the release id is the release id of the snapshot of the lease's
-- context. The SQLSTATE is P0001: outside class 23 and not 22003 (technical TR5R observation). The function keeps no state: a lapse or a
-- withdrawal acts through the lease (admission is refused, and a lease admitted earlier ends at its complete_by).
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rw_md_guard(p_release text) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE l __RW_SCHEMA__.rw_lease%ROWTYPE; rid text;
BEGIN
 SELECT * INTO l FROM rw_lease x WHERE x.backend_pid=pg_backend_pid() AND x.xid=pg_current_xact_id()::text;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_MD_READ_REFUSED' USING DETAIL='NO_LEASE'; END IF;
 IF l.purpose NOT IN ('EXECUTE_CREATE','EXECUTE_REPRODUCE') THEN RAISE EXCEPTION 'RW_MD_READ_REFUSED' USING DETAIL='PURPOSE'; END IF;
 IF rw_reached(clock_timestamp(),l.complete_by) THEN RAISE EXCEPTION 'RW_MD_READ_REFUSED' USING DETAIL='DEADLINE'; END IF;
 SELECT convert_from(s.snapshot,'UTF8')::jsonb->'release'->>'release_id' INTO rid FROM rw_snapshot s WHERE s.context_id=l.context_id;
 IF p_release IS NULL OR rid IS DISTINCT FROM p_release THEN RAISE EXCEPTION 'RW_MD_READ_REFUSED' USING DETAIL='RELEASE'; END IF;
END $$;

CREATE FUNCTION __RW_SCHEMA__.rw_md_file(p_release text) RETURNS SETOF __RW_SCHEMA__.md_file
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT f.* FROM md_file f WHERE f.file_sha256 IN (SELECT rf.file_sha256 FROM md_release_file rf WHERE rf.release_id=p_release);
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_release(p_release text) RETURNS SETOF __RW_SCHEMA__.md_release
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_release t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_release_file(p_release text) RETURNS SETOF __RW_SCHEMA__.md_release_file
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_release_file t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_quote(p_release text) RETURNS SETOF __RW_SCHEMA__.md_quote
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_quote t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_fx_rate(p_release text) RETURNS SETOF __RW_SCHEMA__.md_fx_rate
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_fx_rate t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_corporate_action(p_release text) RETURNS SETOF __RW_SCHEMA__.md_corporate_action
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_corporate_action t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_benchmark(p_release text) RETURNS SETOF __RW_SCHEMA__.md_benchmark
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_benchmark t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_benchmark_point(p_release text) RETURNS SETOF __RW_SCHEMA__.md_benchmark_point
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_benchmark_point t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_adjusted_quote(p_release text) RETURNS SETOF __RW_SCHEMA__.md_adjusted_quote
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_adjusted_quote t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_calendar(p_release text) RETURNS SETOF __RW_SCHEMA__.md_calendar
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_calendar t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_series_exclusion(p_release text) RETURNS SETOF __RW_SCHEMA__.md_series_exclusion
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_series_exclusion t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_risk_free(p_release text) RETURNS SETOF __RW_SCHEMA__.md_risk_free
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_risk_free t WHERE t.release_id=p_release;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_md_risk_free_point(p_release text) RETURNS SETOF __RW_SCHEMA__.md_risk_free_point
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 PERFORM __RW_SCHEMA__.rw_md_guard(p_release);
 RETURN QUERY SELECT t.* FROM md_risk_free_point t WHERE t.release_id=p_release;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- PUBLIC holds nothing on any object of this file (the schema-wide revoke of PUBLIC's EXECUTE on every routine is the installer's one
-- statement, after the last file; the grants by name are the role lists of persistence/real_roles.py).
-- ---------------------------------------------------------------------------------------------------------------------
REVOKE ALL ON __RW_SCHEMA__.rw_root,__RW_SCHEMA__.rw_revision,__RW_SCHEMA__.rw_artifact,__RW_SCHEMA__.rw_operation,__RW_SCHEMA__.rw_journal FROM PUBLIC;
