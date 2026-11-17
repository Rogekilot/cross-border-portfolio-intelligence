-- F1 R1: the real gateway's authority core (implementation/CP7_F1_REAL_PATH_DESIGN.md sections 2.1-2.5, 3.1).
-- A fork of the SHAPE of the F2 gateway (guarded_workspace_v1.sql, which is not edited). Explicit fresh-database add-on,
-- never an old migration or a startup installer. The installer replaces only the validated identifiers
-- __RW_SCHEMA__ / __RW_EXECUTOR__ / __RW_LOADER__ / __RW_PUBLISHER__, then writes the install row (kind, W) once.
--
-- R1 builds NO write fence, row policy, journal, seal, bundle guard, archive, md_* read function or guarded load (R3, R2).
-- Its in-flight work is a READONLY-phase lease on a registered root. Nothing here uses an object built later.
-- Every function below pins its search_path (pg_temp last); no function builds dynamic SQL. The trusted clock is
-- clock_timestamp() and nothing overrides it: there is no parameter, setting or hook for time.
--
-- Column references inside function bodies are always qualified, and the OUT columns of table-returning functions carry an
-- r_ prefix, so no OUT name can shadow a column.
--
-- ADVISORY-LOCK KEY SPACE (technical review R1, L-1). R3 and every later increment must respect it. Advisory locks need no
-- privilege, so ANY session connected to the database can take any key; nothing here keeps another session from taking one.
--   * Two-int keys with class hashtext('rw.lease.ctx'): lease-in-flight MARKERS (shared), one per admitted lease, second int
--     hashtext(context). Nobody else may take a two-int lock of that class.
--   * One-bigint keys in [2^62, 2^62 + 2^53): the deadline MARKER (shared), key = 2^62 + microseconds(complete_by). Nobody else
--     may take a one-bigint lock in that range. The gateway's own exclusive one-bigint locks (the root lock, the publish lock)
--     are masked below 2^62, so they can never fall in it. Any other one-bigint lock a later increment adds must be < 2^62 or
--     >= 2^62 + 2^53.
--   * The markers are taken with pg_try_advisory_xact_lock_shared, so a session that holds a conflicting EXCLUSIVE lock on a
--     marker key can never delay or deny an admission; it can only make that lease unnamed.
-- The markers only NAME leases (rw_in_flight, for the publisher tool's "blocking lease" lines). They are advisory, not
-- authoritative: a session can forge one (a phantom blocker with any complete_by), withhold one (the lease is then unnamed), and a
-- lease holder that also holds another shared lock in the range is listed twice. Safety never reads them: the withdrawal waits
-- on the head row lock and the drain mark refuses new admissions, and R3's fence reads the lease ROW inside the lease's own
-- transaction. Restrict who may connect (PD-0070 turns the loader's login off between loads) to narrow the forging.

-- ---------------------------------------------------------------------------------------------------------------------
-- Rows that are written once or never: install kind with W, mode.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE __RW_SCHEMA__.rw_install (
    singleton boolean PRIMARY KEY CHECK(singleton),
    kind text NOT NULL CHECK(kind IN ('TEST','REAL')),
    w_seconds integer NOT NULL CHECK(w_seconds BETWEEN 1 AND 86400)
);
CREATE TABLE __RW_SCHEMA__.rw_mode (
    singleton boolean PRIMARY KEY CHECK(singleton),
    mode text NOT NULL CHECK(mode IN ('CLOSED','DB_SNAPSHOT_V1','MAINTENANCE_HOLD'))
);
INSERT INTO __RW_SCHEMA__.rw_mode VALUES(true,'CLOSED');

CREATE FUNCTION __RW_SCHEMA__.rw_rights_valid(r jsonb) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT CASE WHEN jsonb_typeof(r)='object' THEN
  COALESCE(r ?& ARRAY['EXECUTE_CREATE','ARCHIVE_READ','ARCHIVE_EXPORT','EXECUTE_REPRODUCE']
   AND (SELECT count(*)=4 FROM jsonb_object_keys(r))
   AND jsonb_typeof(r->'EXECUTE_CREATE')='boolean' AND jsonb_typeof(r->'ARCHIVE_READ')='boolean'
   AND jsonb_typeof(r->'ARCHIVE_EXPORT')='boolean' AND jsonb_typeof(r->'EXECUTE_REPRODUCE')='boolean',false)
  ELSE false END
$$;

-- ---------------------------------------------------------------------------------------------------------------------
-- Authority objects (design 2.1): snapshot, drain mark, history, head.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE __RW_SCHEMA__.rw_snapshot (
    context_id text PRIMARY KEY CHECK(context_id ~ '^[0-9a-f]{64}$'),
    snapshot bytea NOT NULL CHECK(octet_length(snapshot) BETWEEN 2 AND 2000000),
    CHECK(context_id=encode(sha256(snapshot),'hex'))
);
-- A drain mark (a withdrawal request, E18): insert-only, every column NOT NULL with a format check, so a mark cannot exist
-- without its issuer, its decision-reference triple and its server time. Its state is derived, never stored.
CREATE TABLE __RW_SCHEMA__.rw_drain_mark (
    mark_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    context_id text NOT NULL REFERENCES __RW_SCHEMA__.rw_snapshot(context_id),
    generation bigint NOT NULL CHECK(generation>0),
    issuer_actor text NOT NULL CHECK(char_length(issuer_actor) BETWEEN 1 AND 128),
    pd_id text NOT NULL CHECK(pd_id ~ '^PD-[0-9]{4,}$'),
    git_commit text NOT NULL CHECK(git_commit ~ '^[0-9a-f]{40}$'),
    doc_sha256 text NOT NULL CHECK(doc_sha256 ~ '^[0-9a-f]{64}$'),
    marked_at timestamptz NOT NULL,
    db_session_user text NOT NULL DEFAULT session_user::text CHECK(char_length(db_session_user)>0),
    UNIQUE(context_id,generation)
);
CREATE INDEX rw_drain_mark_marked_at ON __RW_SCHEMA__.rw_drain_mark(marked_at);
CREATE TABLE __RW_SCHEMA__.rw_history (
    context_id text NOT NULL REFERENCES __RW_SCHEMA__.rw_snapshot(context_id),
    generation bigint NOT NULL CHECK(generation>0),
    rights jsonb NOT NULL CHECK(__RW_SCHEMA__.rw_rights_valid(rights)),
    expiry_kind text NOT NULL CHECK(expiry_kind IN ('LEASE','NONE','UNKNOWN')),
    valid_until timestamptz,
    basis jsonb NOT NULL CHECK(jsonb_typeof(basis)='array'),
    issuer_actor text NOT NULL CHECK(char_length(issuer_actor) BETWEEN 1 AND 128),
    pd_id text NOT NULL CHECK(pd_id ~ '^PD-[0-9]{4,}$'),
    git_commit text NOT NULL CHECK(git_commit ~ '^[0-9a-f]{40}$'),
    doc_sha256 text NOT NULL CHECK(doc_sha256 ~ '^[0-9a-f]{64}$'),
    recorded_at timestamptz NOT NULL,
    db_session_user text NOT NULL DEFAULT session_user::text CHECK(char_length(db_session_user)>0),
    drain_mark_id bigint REFERENCES __RW_SCHEMA__.rw_drain_mark(mark_id),
    PRIMARY KEY(context_id,generation),
    CHECK(expiry_kind='UNKNOWN' OR (expiry_kind='LEASE')=(valid_until IS NOT NULL))
);
CREATE UNIQUE INDEX rw_history_mark_named_once ON __RW_SCHEMA__.rw_history(drain_mark_id) WHERE drain_mark_id IS NOT NULL;
CREATE INDEX rw_history_recorded_at ON __RW_SCHEMA__.rw_history(recorded_at);
-- The head: one stable, never-deleted row per context, updated in place under an exclusive row lock (T02).
CREATE TABLE __RW_SCHEMA__.rw_head (
    context_id text PRIMARY KEY REFERENCES __RW_SCHEMA__.rw_snapshot(context_id),
    generation bigint NOT NULL CHECK(generation>0),
    rights jsonb NOT NULL CHECK(__RW_SCHEMA__.rw_rights_valid(rights)),
    expiry_kind text NOT NULL CHECK(expiry_kind IN ('LEASE','NONE','UNKNOWN')),
    valid_until timestamptz,
    FOREIGN KEY(context_id,generation) REFERENCES __RW_SCHEMA__.rw_history(context_id,generation)
);

-- ---------------------------------------------------------------------------------------------------------------------
-- Root registry and leases (design 2.6 item 4, 3.1). The root-link table is the registry of roots; only rw_admit with
-- new_root registers one. The deferred foreign key to portfolio makes a registered root without a portfolio fail by COMMIT.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE __RW_SCHEMA__.rw_root_link (
    root_id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES __RW_SCHEMA__.app_user(user_id),
    context_id text NOT NULL REFERENCES __RW_SCHEMA__.rw_snapshot(context_id),
    UNIQUE(root_id,context_id),
    CONSTRAINT rw_root_link_portfolio_fkey FOREIGN KEY(root_id) REFERENCES __RW_SCHEMA__.portfolio(portfolio_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE __RW_SCHEMA__.rw_lease (
    backend_pid integer NOT NULL,
    xid text NOT NULL,
    owner_id uuid NOT NULL,
    root_id uuid NOT NULL,
    context_id text NOT NULL,
    generation bigint NOT NULL,
    operation_id uuid NOT NULL,
    command_sha256 text NOT NULL CHECK(command_sha256 ~ '^[0-9a-f]{64}$'),
    purpose text NOT NULL CHECK(purpose IN ('EXECUTE_CREATE','ARCHIVE_READ','ARCHIVE_EXPORT','EXECUTE_REPRODUCE')),
    phase text NOT NULL CHECK(phase IN ('OPEN','SEALED','READONLY','REPLAY')),
    state_sha256 text,
    admitted_at timestamptz NOT NULL,
    valid_until timestamptz,
    complete_by timestamptz NOT NULL,
    PRIMARY KEY(backend_pid,xid),
    CONSTRAINT rw_lease_root_fkey FOREIGN KEY(root_id,context_id) REFERENCES __RW_SCHEMA__.rw_root_link(root_id,context_id),
    CONSTRAINT rw_lease_history_fkey FOREIGN KEY(context_id,generation) REFERENCES __RW_SCHEMA__.rw_history(context_id,generation),
    -- The cap (PD-0068 answer 1): a lease with a later deadline than valid_until cannot be stored.
    CONSTRAINT rw_lease_deadline_cap CHECK(complete_by>admitted_at AND (valid_until IS NULL OR complete_by<=valid_until))
);
CREATE INDEX rw_lease_admitted_at ON __RW_SCHEMA__.rw_lease(admitted_at);

-- ---------------------------------------------------------------------------------------------------------------------
-- Pure helpers.
-- ---------------------------------------------------------------------------------------------------------------------
-- THE ONE STRICT COMPARISON of time (E3, E4; technical review R1, L-10). "The clock has reached the limit" is now >= limit, so the
-- first refused instant is the limit itself. The deadline guard (limit = complete_by), the lapse of a lease (limit = valid_until)
-- and the floor of a publish or a renewal (the new valid_until must lie after the clock, so it is refused when the clock has reached
-- it) all call this, and no other function compares an instant with the clock. It takes both instants as arguments, so a test can
-- call it with equal instants, which the real clock cannot produce; no runtime role can call it, and no function takes a time.
CREATE FUNCTION __RW_SCHEMA__.rw_reached(p_now timestamptz,p_limit timestamptz) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT COALESCE(p_now>=p_limit,false)
$$;
CREATE FUNCTION __RW_SCHEMA__.rw_scope_allowed(p_kind text,p_scope text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT COALESCE((p_kind='TEST' AND p_scope IN ('SYNTHETIC_TEST','TEST_SWITCH')) OR (p_kind='REAL' AND p_scope='REAL'),false)
$$;
CREATE FUNCTION __RW_SCHEMA__.rw_snapshot_scope(p_snapshot bytea) RETURNS text
LANGUAGE sql STABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT convert_from(p_snapshot,'UTF8')::jsonb->>'scope'
$$;
-- The origin labels a snapshot of a scope must carry (design 1.1, 4.2; the SQL twin of real_scope.ScopeDef.origin_fields, which a
-- test compares). NULL for a scope this gateway does not know.
CREATE FUNCTION __RW_SCHEMA__.rw_origin_expected(p_scope text) RETURNS jsonb
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT CASE
  WHEN p_scope IN ('SYNTHETIC_TEST','TEST_SWITCH') THEN '{"market_origin":"SYNTHETIC_TEST","ledger_origin":"INVENTED_TEST_LEDGER","personal_holdings":false,"synthetic":true}'::jsonb
  WHEN p_scope='REAL' THEN '{"market_origin":"REAL_SOURCE","ledger_origin":"PROJECT_CONSTRUCTED_NONPERSONAL_UAT","personal_holdings":false,"synthetic":false}'::jsonb
  ELSE NULL END
$$;
-- The member sources of a snapshot, from its hashed member tuples (L-8): the publisher cannot declare them and a history
-- row cannot change them.
CREATE FUNCTION __RW_SCHEMA__.rw_snapshot_sources(p_snapshot bytea) RETURNS text[]
LANGUAGE sql STABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT COALESCE(array_agg(DISTINCT m.value->>'source_id' ORDER BY m.value->>'source_id'),'{}'::text[])
 FROM jsonb_array_elements(convert_from(p_snapshot,'UTF8')::jsonb->'members') m
$$;

-- The expiry kind is DERIVED from evidence, never defaulted and never inferred from silence (E14, FF1-C06).
-- Evidence: one basis entry per member source, each {source_id, basis, pd_id, git_commit, doc_sha256[, term_end_not_after]}.
--   LEASE   at least one LEASE_TERM entry, a valid_until, and valid_until <= the earliest term_end_not_after. This is a
--           PLAUSIBILITY refusal against an UPPER bound of the term end. It is not a safety margin and not a lower bound.
--   NONE    every member source has a NO_EXPIRY_READING, no other entry, and no valid_until.
--   UNKNOWN anything else (a missing, extra, duplicate or malformed entry; NOT_ASSESSED without a LEASE_TERM).
-- It reads no clock: admit re-derives with it, and a derivation must not change with time.
CREATE FUNCTION __RW_SCHEMA__.rw_expiry_derive(p_members text[],p_basis jsonb,p_valid_until timestamptz,OUT kind text,OUT reason text)
LANGUAGE plpgsql STABLE SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE e jsonb; b text; sid text; seen text[]:='{}'; te timestamptz; earliest timestamptz; n_lease integer:=0; n_none integer:=0; n_na integer:=0;
BEGIN
 kind:='UNKNOWN';
 IF p_members IS NULL OR cardinality(p_members)=0 THEN reason:='NO_MEMBER_SOURCES'; RETURN; END IF;
 IF p_basis IS NULL OR jsonb_typeof(p_basis) IS DISTINCT FROM 'array' THEN reason:='BASIS_SHAPE'; RETURN; END IF;
 IF jsonb_array_length(p_basis)<>cardinality(p_members) THEN reason:='BASIS_COUNT'; RETURN; END IF;
 FOR e IN SELECT x.value FROM jsonb_array_elements(p_basis) x LOOP
  IF jsonb_typeof(e) IS DISTINCT FROM 'object' OR NOT (e ?& ARRAY['source_id','basis','pd_id','git_commit','doc_sha256'])
     OR jsonb_typeof(e->'source_id') IS DISTINCT FROM 'string' OR jsonb_typeof(e->'basis') IS DISTINCT FROM 'string'
     OR jsonb_typeof(e->'pd_id') IS DISTINCT FROM 'string' OR jsonb_typeof(e->'git_commit') IS DISTINCT FROM 'string'
     OR jsonb_typeof(e->'doc_sha256') IS DISTINCT FROM 'string' THEN reason:='ENTRY_SHAPE'; RETURN; END IF;
  sid:=e->>'source_id'; b:=e->>'basis';
  IF (e->>'pd_id') !~ '^PD-[0-9]{4,}$' OR (e->>'git_commit') !~ '^[0-9a-f]{40}$' OR (e->>'doc_sha256') !~ '^[0-9a-f]{64}$' THEN reason:='ENTRY_DECISION_REF'; RETURN; END IF;
  IF NOT (sid=ANY(p_members)) THEN reason:='NON_MEMBER_ENTRY'; RETURN; END IF;
  IF sid=ANY(seen) THEN reason:='DUPLICATE_ENTRY'; RETURN; END IF;
  seen:=array_append(seen,sid);
  IF b='LEASE_TERM' THEN
   IF (SELECT count(*) FROM jsonb_object_keys(e))<>6 OR NOT (e ? 'term_end_not_after') OR jsonb_typeof(e->'term_end_not_after') IS DISTINCT FROM 'string'
      OR (e->>'term_end_not_after') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$' THEN reason:='ENTRY_TERM_END'; RETURN; END IF;
   BEGIN
    te:=(e->>'term_end_not_after')::timestamptz;
   EXCEPTION WHEN others THEN
    reason:='ENTRY_TERM_END'; RETURN;
   END;
   n_lease:=n_lease+1;
   IF earliest IS NULL OR te<earliest THEN earliest:=te; END IF;
  ELSIF b='NO_EXPIRY_READING' OR b='NOT_ASSESSED' THEN
   IF (SELECT count(*) FROM jsonb_object_keys(e))<>5 THEN reason:='ENTRY_SHAPE'; RETURN; END IF;
   IF b='NO_EXPIRY_READING' THEN n_none:=n_none+1; ELSE n_na:=n_na+1; END IF;
  ELSE
   reason:='ENTRY_BASIS'; RETURN;
  END IF;
 END LOOP;
 IF n_lease>0 THEN
  IF p_valid_until IS NULL THEN reason:='NO_VALID_UNTIL'; RETURN; END IF;
  IF p_valid_until>earliest THEN reason:='PLAUSIBILITY'; RETURN; END IF;
  kind:='LEASE'; RETURN;
 END IF;
 IF n_none=cardinality(p_members) AND n_na=0 THEN
  IF p_valid_until IS NOT NULL THEN reason:='VALID_UNTIL_WITH_NONE'; RETURN; END IF;
  kind:='NONE'; RETURN;
 END IF;
 reason:='NOT_EVERY_SOURCE_HAS_A_READING';
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- Triggers: immutability, the head/history agreement, the lease guard, and the DEADLINE GUARD.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rw_no_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN RAISE EXCEPTION 'RW_IMMUTABLE'; END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_head_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE hr __RW_SCHEMA__.rw_history%ROWTYPE;
BEGIN
 IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'RW_IMMUTABLE'; END IF;
 SELECT * INTO hr FROM rw_history h WHERE h.context_id=NEW.context_id AND h.generation=NEW.generation;
 IF NOT FOUND OR hr.rights IS DISTINCT FROM NEW.rights OR hr.expiry_kind IS DISTINCT FROM NEW.expiry_kind OR hr.valid_until IS DISTINCT FROM NEW.valid_until THEN RAISE EXCEPTION 'RW_HEAD_DIFFERS'; END IF;
 IF TG_OP='UPDATE' THEN
  IF NEW.context_id IS DISTINCT FROM OLD.context_id OR NEW.generation<>OLD.generation+1 THEN RAISE EXCEPTION 'RW_GENERATION_DIFFERS'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION __RW_SCHEMA__.rw_history_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 IF NEW.generation>1 AND NOT EXISTS(SELECT 1 FROM rw_history h WHERE h.context_id=NEW.context_id AND h.generation=NEW.generation-1) THEN RAISE EXCEPTION 'RW_GENERATION_DIFFERS'; END IF;
 IF NEW.drain_mark_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM rw_drain_mark m WHERE m.mark_id=NEW.drain_mark_id AND m.context_id=NEW.context_id AND m.generation=NEW.generation-1) THEN RAISE EXCEPTION 'RW_MARK_STALE'; END IF;
 RETURN NEW;
END $$;
-- A lease row is never deleted, and the columns that identify it or fix its deadline never change. R3's seal updates only the
-- phase and the state digest, which this guard allows.
CREATE FUNCTION __RW_SCHEMA__.rw_lease_guard() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'RW_IMMUTABLE'; END IF;
 IF NEW.backend_pid<>OLD.backend_pid OR NEW.xid<>OLD.xid OR NEW.owner_id<>OLD.owner_id OR NEW.root_id<>OLD.root_id OR NEW.context_id<>OLD.context_id
    OR NEW.generation<>OLD.generation OR NEW.operation_id<>OLD.operation_id OR NEW.command_sha256<>OLD.command_sha256 OR NEW.purpose<>OLD.purpose
    OR NEW.admitted_at<>OLD.admitted_at OR NEW.valid_until IS DISTINCT FROM OLD.valid_until OR NEW.complete_by<>OLD.complete_by THEN RAISE EXCEPTION 'RW_IMMUTABLE'; END IF;
 RETURN NEW;
END $$;
-- THE DEADLINE GUARD (design 3.1, E4 check (4)). A constraint trigger of its own on the lease table, DEFERRABLE INITIALLY
-- DEFERRED, queued by the admit insert and fired by PostgreSQL inside COMMIT processing. It is a different trigger from
-- the bundle guard R3 forks, on purpose, so product code can fire every other deferrable constraint early BY NAME and
-- leave this one pending. Its name is unique among the schema's constraints (an R1 catalog test asserts it), because
-- SET CONSTRAINTS <name> acts on every match. Strict: the first refused instant is complete_by itself.
CREATE FUNCTION __RW_SCHEMA__.rw_deadline_check() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 IF rw_reached(clock_timestamp(),NEW.complete_by) THEN RAISE EXCEPTION 'RW_DEADLINE'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER rw_lease_deadline_guard AFTER INSERT ON __RW_SCHEMA__.rw_lease DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rw_deadline_check();

DO $$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['rw_install','rw_snapshot','rw_history','rw_drain_mark','rw_root_link'] LOOP
  EXECUTE format('CREATE TRIGGER rw_immutable BEFORE UPDATE OR DELETE ON %I.%I FOR EACH ROW EXECUTE FUNCTION %I.rw_no_mutation()','__RW_SCHEMA__',t,'__RW_SCHEMA__');
  EXECUTE format('CREATE TRIGGER rw_no_truncate BEFORE TRUNCATE ON %I.%I FOR EACH STATEMENT EXECUTE FUNCTION %I.rw_no_mutation()','__RW_SCHEMA__',t,'__RW_SCHEMA__');
 END LOOP;
END $$;
CREATE TRIGGER rw_head_guard_write BEFORE INSERT OR UPDATE ON __RW_SCHEMA__.rw_head FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rw_head_guard();
CREATE TRIGGER rw_head_guard_delete BEFORE DELETE ON __RW_SCHEMA__.rw_head FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rw_head_guard();
CREATE TRIGGER rw_head_no_truncate BEFORE TRUNCATE ON __RW_SCHEMA__.rw_head FOR EACH STATEMENT EXECUTE FUNCTION __RW_SCHEMA__.rw_no_mutation();
CREATE TRIGGER rw_mode_no_delete BEFORE DELETE ON __RW_SCHEMA__.rw_mode FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rw_no_mutation();
CREATE TRIGGER rw_mode_no_truncate BEFORE TRUNCATE ON __RW_SCHEMA__.rw_mode FOR EACH STATEMENT EXECUTE FUNCTION __RW_SCHEMA__.rw_no_mutation();
CREATE TRIGGER rw_history_guard_write BEFORE INSERT ON __RW_SCHEMA__.rw_history FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rw_history_guard();
CREATE TRIGGER rw_lease_guard_write BEFORE UPDATE OR DELETE ON __RW_SCHEMA__.rw_lease FOR EACH ROW EXECUTE FUNCTION __RW_SCHEMA__.rw_lease_guard();
CREATE TRIGGER rw_lease_no_truncate BEFORE TRUNCATE ON __RW_SCHEMA__.rw_lease FOR EACH STATEMENT EXECUTE FUNCTION __RW_SCHEMA__.rw_lease_guard();

-- ---------------------------------------------------------------------------------------------------------------------
-- Reads for tools: the install kind (the row itself is readable by no runtime role), the trusted instant, the lease scope.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rw_install_info() RETURNS TABLE(r_kind text,r_w_seconds integer)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT i.kind,i.w_seconds FROM rw_install i WHERE i.singleton
$$;
-- The latest committed instant any gateway row records (E3): history times, drain-mark times and lease admission times.
CREATE FUNCTION __RW_SCHEMA__.rw_latest_instant() RETURNS timestamptz
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT max(x.t) FROM (SELECT max(h.recorded_at) AS t FROM rw_history h
  UNION ALL SELECT max(m.marked_at) FROM rw_drain_mark m
  UNION ALL SELECT max(l.admitted_at) FROM rw_lease l) x
$$;
CREATE FUNCTION __RW_SCHEMA__.rw_scope()
RETURNS TABLE(r_owner_id uuid,r_root_id uuid,r_context_id text,r_generation bigint,r_operation_id uuid,r_purpose text,r_complete_by timestamptz)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
 SELECT l.owner_id,l.root_id,l.context_id,l.generation,l.operation_id,l.purpose,l.complete_by FROM rw_lease l
 WHERE l.backend_pid=pg_backend_pid() AND l.xid=pg_current_xact_id()::text
$$;
-- The owner-scoped enumeration (design 2.4): IDENTIFIERS ONLY for the owner's own roots. It reads the root-link table and the
-- head, needs no lease, and returns no origin field, no number and nothing from rw_root or rw_revision.
CREATE FUNCTION __RW_SCHEMA__.rw_list_roots(p_owner uuid) RETURNS TABLE(root_id uuid,context_id text,generation bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 IF p_owner IS NULL THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 RETURN QUERY SELECT l.root_id,l.context_id,h.generation FROM rw_root_link l JOIN rw_head h ON h.context_id=l.context_id
  WHERE l.owner_id=p_owner ORDER BY l.root_id;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- ADMIT (design 3.1, "Admission under lock" and the trusted clock [E3]).
-- Order: shape, isolation, single scope; mode shared; head shared; no pending drain mark; expiry kind RE-DERIVED from the
-- stored snapshot and the stored entries; install-kind guard; READ latest; THEN sample now; regression; lapse; rights; root.
-- Reading latest before sampling removes the race of overlapping admissions: a row committed before the read has a sample
-- time earlier than the read, which is earlier than the sample.
-- complete_by = LEAST(admitted_at + W, valid_until) for every lease (PD-0068 answer 1); the table check enforces the cap.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rw_admit(p_owner uuid,p_root uuid,p_context text,p_generation bigint,p_purpose text,p_operation uuid,p_command text,p_new_root boolean DEFAULT false) RETURNS bytea
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE v_mode text; v_head __RW_SCHEMA__.rw_head%ROWTYPE; v_hist __RW_SCHEMA__.rw_history%ROWTYPE; v_root __RW_SCHEMA__.rw_root_link%ROWTYPE;
 v_snapshot bytea; v_kind text; v_reason text; v_install text; v_w integer; v_latest timestamptz; v_now timestamptz; v_complete timestamptz; v_phase text;
 v_replay boolean:=false; v_prior_command text; v_prior_root uuid; v_prior_context text; v_prior_found boolean:=false;
BEGIN
 IF p_owner IS NULL OR p_root IS NULL OR p_context IS NULL OR p_context !~ '^[0-9a-f]{64}$' OR p_generation IS NULL OR p_generation<1
    OR p_purpose IS NULL OR p_purpose NOT IN ('EXECUTE_CREATE','ARCHIVE_READ','ARCHIVE_EXPORT','EXECUTE_REPRODUCE') OR p_operation IS NULL
    OR p_command IS NULL OR p_command !~ '^[0-9a-f]{64}$' OR p_new_root IS NULL THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'RW_ISOLATION'; END IF;
 IF EXISTS(SELECT 1 FROM rw_lease l WHERE l.backend_pid=pg_backend_pid() AND l.xid=pg_current_xact_id()::text) THEN RAISE EXCEPTION 'RW_SINGLE_SCOPE'; END IF;
 SELECT m.mode INTO v_mode FROM rw_mode m WHERE m.singleton FOR SHARE;
 IF v_mode IS DISTINCT FROM 'DB_SNAPSHOT_V1' THEN RAISE EXCEPTION 'RW_MODE_HOLD'; END IF;
 SELECT * INTO v_head FROM rw_head h WHERE h.context_id=p_context FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_NOT_FOUND'; END IF;
 IF v_head.generation IS DISTINCT FROM p_generation THEN RAISE EXCEPTION 'RW_GENERATION_DIFFERS'; END IF;
 IF EXISTS(SELECT 1 FROM rw_drain_mark dm WHERE dm.context_id=p_context AND dm.generation=v_head.generation
           AND NOT EXISTS(SELECT 1 FROM rw_history x WHERE x.drain_mark_id=dm.mark_id)) THEN RAISE EXCEPTION 'RW_WITHDRAWAL_PENDING'; END IF;
 SELECT * INTO v_hist FROM rw_history x WHERE x.context_id=p_context AND x.generation=v_head.generation;
 SELECT s.snapshot INTO v_snapshot FROM rw_snapshot s WHERE s.context_id=p_context;
 SELECT d.kind,d.reason INTO v_kind,v_reason FROM rw_expiry_derive(rw_snapshot_sources(v_snapshot),v_hist.basis,v_hist.valid_until) d;
 IF v_kind IS DISTINCT FROM v_hist.expiry_kind OR v_kind='UNKNOWN' OR v_head.expiry_kind IS DISTINCT FROM v_hist.expiry_kind
    OR v_head.valid_until IS DISTINCT FROM v_hist.valid_until OR v_head.rights IS DISTINCT FROM v_hist.rights THEN
  RAISE EXCEPTION 'RW_EXPIRY_HOLD' USING DETAIL=COALESCE(v_reason,'KIND_DIFFERS');
 END IF;
 SELECT i.kind,i.w_seconds INTO v_install,v_w FROM rw_install i WHERE i.singleton;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_INSTALL_MISSING'; END IF;
 IF NOT rw_scope_allowed(v_install,rw_snapshot_scope(v_snapshot)) THEN RAISE EXCEPTION 'RW_INSTALL_KIND'; END IF;
 v_latest:=rw_latest_instant();
 v_now:=clock_timestamp();
 IF v_latest IS NOT NULL AND NOT rw_reached(v_now,v_latest) THEN RAISE EXCEPTION 'RW_CLOCK_REGRESSION'; END IF;
 IF v_hist.valid_until IS NOT NULL AND rw_reached(v_now,v_hist.valid_until) THEN RAISE EXCEPTION 'RW_LAPSED'; END IF;
 -- A completed withdrawal (all four rights false, written by a generation that names a drain mark) has a code of its own, distinct
 -- from a right that was never granted (design 2.1, 2.4; technical review R1, L-5).
 IF v_hist.drain_mark_id IS NOT NULL AND NOT (COALESCE((v_hist.rights->>'EXECUTE_CREATE')::boolean,false) OR COALESCE((v_hist.rights->>'ARCHIVE_READ')::boolean,false)
    OR COALESCE((v_hist.rights->>'ARCHIVE_EXPORT')::boolean,false) OR COALESCE((v_hist.rights->>'EXECUTE_REPRODUCE')::boolean,false)) THEN RAISE EXCEPTION 'RW_WITHDRAWN'; END IF;
 IF NOT COALESCE((v_hist.rights->>'ARCHIVE_READ')::boolean,false) OR NOT COALESCE((v_hist.rights->>p_purpose)::boolean,false) THEN RAISE EXCEPTION 'RW_RIGHT_REFUSED'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('rw.root:__RW_SCHEMA__:'||p_root::text,0) & 4611686018427387903);
 -- An admission that queued on the root lock behind another lease is checked against the drain mark AGAIN, now that it holds the
 -- lock: a mark committed while it waited still refuses it (design 2.1; technical review R1, L-2). Its head share lock has kept
 -- the generation from moving, so the generation read above is still the head's. This is a new statement, so under READ COMMITTED
 -- it sees marks committed during the wait.
 IF EXISTS(SELECT 1 FROM rw_drain_mark dm WHERE dm.context_id=p_context AND dm.generation=v_head.generation
           AND NOT EXISTS(SELECT 1 FROM rw_history x WHERE x.drain_mark_id=dm.mark_id)) THEN RAISE EXCEPTION 'RW_WITHDRAWAL_PENDING'; END IF;
 -- REPLAY (R3, T08): an EXECUTE_CREATE admission of an operation id that is already SEALED and committed finds its operation row under
 -- the operation lock. The same command, root and context replay (phase REPLAY: read-only, no economic write is allowed); anything
 -- else is a conflict. The operation table is created by the fence file, so it is named here only inside this statement.
 PERFORM pg_advisory_xact_lock(hashtextextended('rw.op:__RW_SCHEMA__:'||p_owner::text||':'||p_operation::text,0) & 4611686018427387903);
 SELECT true,o.command_sha256,o.root_id,o.context_id INTO v_prior_found,v_prior_command,v_prior_root,v_prior_context
  FROM rw_operation o WHERE o.owner_id=p_owner AND o.operation_id=p_operation;
 IF COALESCE(v_prior_found,false) AND p_purpose='EXECUTE_CREATE' THEN
  IF v_prior_command IS DISTINCT FROM p_command OR v_prior_root IS DISTINCT FROM p_root OR v_prior_context IS DISTINCT FROM p_context THEN
   RAISE EXCEPTION 'RW_IDEMPOTENCY_CONFLICT';
  END IF;
  v_replay:=true;
 END IF;
 SELECT * INTO v_root FROM rw_root_link r WHERE r.root_id=p_root;
 IF NOT FOUND THEN
  IF NOT p_new_root OR p_purpose<>'EXECUTE_CREATE' OR v_replay OR NOT EXISTS(SELECT 1 FROM app_user u WHERE u.user_id=p_owner)
     OR EXISTS(SELECT 1 FROM portfolio pf WHERE pf.portfolio_id=p_root) THEN RAISE EXCEPTION 'RW_NOT_FOUND'; END IF;
  INSERT INTO rw_root_link(root_id,owner_id,context_id) VALUES(p_root,p_owner,p_context);
 ELSE
  IF v_root.owner_id IS DISTINCT FROM p_owner OR v_root.context_id IS DISTINCT FROM p_context OR (p_new_root AND NOT v_replay) THEN RAISE EXCEPTION 'RW_NOT_FOUND'; END IF;
 END IF;
 v_complete:=LEAST(v_now+(v_w*interval '1 second'),v_hist.valid_until);
 v_phase:=CASE WHEN v_replay THEN 'REPLAY' WHEN p_purpose='EXECUTE_CREATE' THEN 'OPEN' ELSE 'READONLY' END;
 INSERT INTO rw_lease(backend_pid,xid,owner_id,root_id,context_id,generation,operation_id,command_sha256,purpose,phase,admitted_at,valid_until,complete_by)
 VALUES(pg_backend_pid(),pg_current_xact_id()::text,p_owner,p_root,p_context,p_generation,p_operation,p_command,p_purpose,v_phase,v_now,v_hist.valid_until,v_complete);
 -- An uncommitted lease row is invisible to other sessions, so an in-flight lease is made nameable through pg_locks, which any
 -- session may read: a shared advisory lock keyed by the context, and one whose key encodes complete_by (rw_in_flight). They are
 -- TRY locks: a session that holds a conflicting exclusive lock on a marker key cannot delay or deny this admission, it can only
 -- leave the lease unnamed (see the key-space note at the top of this file). Their result is deliberately ignored.
 PERFORM pg_try_advisory_xact_lock_shared(hashtext('rw.lease.ctx'),hashtext(p_context));
 PERFORM pg_try_advisory_xact_lock_shared(4611686018427387904+(extract(epoch FROM v_complete)*1000000)::bigint);
 RETURN v_snapshot;
END $$;

-- The leases in flight on a context, named by backend and complete_by (design 3.1 "Stalled work"). Read-only.
CREATE FUNCTION __RW_SCHEMA__.rw_in_flight(p_context text) RETURNS TABLE(r_pid integer,r_complete_by timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
BEGIN
 IF p_context IS NULL OR p_context !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 RETURN QUERY SELECT b.pid::integer,
   to_timestamp(((b.classid::bigint*4294967296+b.objid::bigint)-4611686018427387904)::numeric/1000000)
  FROM pg_locks b JOIN pg_locks a ON a.pid=b.pid AND a.database=b.database AND a.locktype='advisory' AND a.objsubid=2 AND a.granted AND a.mode='ShareLock'
   AND a.classid::bigint=(hashtext('rw.lease.ctx')::bigint & 4294967295) AND a.objid::bigint=(hashtext(p_context)::bigint & 4294967295)
  -- The deadline marker is a SHARED one-key lock whose key is 2^62 + microseconds since the epoch, so its high word lies in
  -- [2^30, 2^30 + 2^21). The root and publish locks are EXCLUSIVE, so they are never matched.
  WHERE b.locktype='advisory' AND b.objsubid=1 AND b.granted AND b.mode='ShareLock' AND b.classid::bigint>=1073741824 AND b.classid::bigint<1075838976
   AND b.database=(SELECT d.oid FROM pg_database d WHERE d.datname=current_database()) ORDER BY b.pid;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- PUBLISHER COMMANDS (design 2.3, 2.5, 3.1). Callable by the publisher role only. Each carries the mandatory decision
-- reference (PD id, git commit, SHA-256 at that commit) and the issuer actor, and is refused without all of them (E13).
-- Lock order everywhere: mode shared, then head (shared for a mark, exclusive for a generation change).
-- ---------------------------------------------------------------------------------------------------------------------
CREATE FUNCTION __RW_SCHEMA__.rw_publish(p_snapshot bytea,p_rights jsonb,p_valid_until timestamptz,p_basis jsonb,p_actor text,p_pd text,p_commit text,p_doc text)
RETURNS TABLE(r_context_id text,r_generation bigint,r_created boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE v_json jsonb; v_ctx text; v_scope text; v_install text; v_mode text; v_now timestamptz; v_kind text; v_reason text; v_basis jsonb;
 v_codes text[]:='{}'; v_hist __RW_SCHEMA__.rw_history%ROWTYPE;
BEGIN
 IF p_snapshot IS NULL OR octet_length(p_snapshot) NOT BETWEEN 2 AND 2000000 OR p_rights IS NULL OR NOT rw_rights_valid(p_rights)
    OR p_basis IS NULL OR jsonb_typeof(p_basis) IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 IF p_actor IS NULL OR char_length(p_actor) NOT BETWEEN 1 AND 128 OR p_pd IS NULL OR p_pd !~ '^PD-[0-9]{4,}$'
    OR p_commit IS NULL OR p_commit !~ '^[0-9a-f]{40}$' OR p_doc IS NULL OR p_doc !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RW_DECISION_REF_REQUIRED'; END IF;
 BEGIN
  v_json:=convert_from(p_snapshot,'UTF8')::jsonb;
 EXCEPTION WHEN others THEN
  RAISE EXCEPTION 'RW_SHAPE';
 END;
 IF jsonb_typeof(v_json) IS DISTINCT FROM 'object' OR v_json->>'schema' IS DISTINCT FROM 'finweb.real_snapshot/1'
    OR jsonb_typeof(v_json->'members') IS DISTINCT FROM 'array' OR jsonb_typeof(v_json->'origin') IS DISTINCT FROM 'object'
    OR v_json->>'scope' IS NULL OR v_json->>'scope' NOT IN ('SYNTHETIC_TEST','TEST_SWITCH','REAL') THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 IF jsonb_array_length(v_json->'members') NOT BETWEEN 1 AND 64 THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(v_json->'members') m WHERE jsonb_typeof(m.value) IS DISTINCT FROM 'object'
    OR jsonb_typeof(m.value->'source_id') IS DISTINCT FROM 'string' OR COALESCE(m.value->>'source_id','')=''
    OR COALESCE(m.value->>'payload_sha256','') !~ '^[0-9a-f]{64}$' OR COALESCE(m.value->>'manifest_sha256','') !~ '^[0-9a-f]{64}$') THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 v_scope:=v_json->>'scope';
 SELECT i.kind INTO v_install FROM rw_install i WHERE i.singleton;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_INSTALL_MISSING'; END IF;
 -- The install-kind guard in both directions, and (R2) the origin validators O1 to O3 for the REAL scope: every failed predicate
 -- is listed, not only the first (design 4.2, E15). The validators are rwp_origin_failures in real_provenance_v1.sql, installed in the
 -- same transaction; they read the registered candidates and write nothing. A test scope does not run them here (they are
 -- informational there and the scope's own invariants hold it).
 IF NOT rw_scope_allowed(v_install,v_scope) THEN v_codes:=array_append(v_codes,'RW_INSTALL_KIND'); END IF;
 IF v_scope='REAL' THEN v_codes:=v_codes||rwp_origin_failures(p_snapshot); END IF;
 -- R3: the origin labels of a TEST-scope snapshot must be the synthetic ones and carry no real-origin string (I1, I3). The same check
 -- for the REAL scope is part of rwp_origin_failures, with the REAL branch's other validators.
 IF v_scope<>'REAL' AND (v_json->'origin' IS DISTINCT FROM rw_origin_expected(v_scope) OR position('REAL_SOURCE' IN v_json::text)>0) THEN
  v_codes:=array_append(v_codes,'RW_ORIGIN_MISMATCH');
 END IF;
 IF cardinality(v_codes)>0 THEN RAISE EXCEPTION 'RW_PUBLISH_REFUSED' USING DETAIL=array_to_string(v_codes,','); END IF;
 SELECT m.mode INTO v_mode FROM rw_mode m WHERE m.singleton FOR SHARE;
 IF v_mode='MAINTENANCE_HOLD' THEN RAISE EXCEPTION 'RW_MODE_HOLD'; END IF;
 v_ctx:=encode(sha256(p_snapshot),'hex');
 PERFORM pg_advisory_xact_lock(hashtextextended('rw.publish:__RW_SCHEMA__:'||v_ctx,0) & 4611686018427387903);
 SELECT jsonb_agg(e.value ORDER BY e.value->>'source_id') INTO v_basis FROM jsonb_array_elements(p_basis) e;
 v_basis:=COALESCE(v_basis,'[]'::jsonb);
 SELECT * INTO v_hist FROM rw_history h WHERE h.context_id=v_ctx AND h.generation=1;
 IF FOUND THEN
  -- Re-running with identical input returns the original; anything else is a conflict (use renew).
  IF v_hist.rights=p_rights AND v_hist.valid_until IS NOT DISTINCT FROM p_valid_until AND v_hist.basis=v_basis
     AND v_hist.issuer_actor=p_actor AND v_hist.pd_id=p_pd AND v_hist.git_commit=p_commit AND v_hist.doc_sha256=p_doc THEN
   RETURN QUERY SELECT v_ctx,1::bigint,false; RETURN;
  END IF;
  RAISE EXCEPTION 'RW_PUBLISH_CONFLICT';
 END IF;
 SELECT d.kind,d.reason INTO v_kind,v_reason FROM rw_expiry_derive(rw_snapshot_sources(p_snapshot),v_basis,p_valid_until) d;
 IF v_kind='UNKNOWN' THEN RAISE EXCEPTION 'RW_EXPIRY_UNSUPPORTED' USING DETAIL=COALESCE(v_reason,'UNKNOWN'); END IF;
 v_now:=clock_timestamp();
 IF p_valid_until IS NOT NULL AND rw_reached(v_now,p_valid_until) THEN RAISE EXCEPTION 'RW_VALID_UNTIL_PAST'; END IF;
 INSERT INTO rw_snapshot(context_id,snapshot) VALUES(v_ctx,p_snapshot) ON CONFLICT (context_id) DO NOTHING;
 INSERT INTO rw_history(context_id,generation,rights,expiry_kind,valid_until,basis,issuer_actor,pd_id,git_commit,doc_sha256,recorded_at)
 VALUES(v_ctx,1,p_rights,v_kind,p_valid_until,v_basis,p_actor,p_pd,p_commit,p_doc,v_now);
 INSERT INTO rw_head(context_id,generation,rights,expiry_kind,valid_until) VALUES(v_ctx,1,p_rights,v_kind,p_valid_until);
 UPDATE rw_mode SET mode='DB_SNAPSHOT_V1' WHERE singleton AND mode='CLOSED';
 RETURN QUERY SELECT v_ctx,1::bigint,true;
END $$;

-- RENEW: a new generation of the SAME context, a human act only. valid_until must be strictly later than the server clock at
-- the record; it may be later than, equal to, or EARLIER than the current one (E25: an earlier one is a date correction).
-- Takes the head EXCLUSIVE, so it is appended only when no lease is in flight; the tool's lock_timeout bounds the wait.
CREATE FUNCTION __RW_SCHEMA__.rw_renew(p_context text,p_expected bigint,p_rights jsonb,p_valid_until timestamptz,p_basis jsonb,p_actor text,p_pd text,p_commit text,p_doc text,p_names_mark bigint DEFAULT NULL)
RETURNS TABLE(r_generation bigint,r_old_valid_until timestamptz,r_new_valid_until timestamptz,r_moved_earlier boolean,r_superseded_mark bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE v_mode text; v_head __RW_SCHEMA__.rw_head%ROWTYPE; v_hist __RW_SCHEMA__.rw_history%ROWTYPE; v_pending bigint; v_snapshot bytea; v_basis jsonb;
 v_kind text; v_reason text; v_now timestamptz; v_new bigint;
BEGIN
 IF p_context IS NULL OR p_context !~ '^[0-9a-f]{64}$' OR p_expected IS NULL OR p_expected<1 OR p_rights IS NULL OR NOT rw_rights_valid(p_rights)
    OR p_basis IS NULL OR jsonb_typeof(p_basis) IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 IF p_actor IS NULL OR char_length(p_actor) NOT BETWEEN 1 AND 128 OR p_pd IS NULL OR p_pd !~ '^PD-[0-9]{4,}$'
    OR p_commit IS NULL OR p_commit !~ '^[0-9a-f]{40}$' OR p_doc IS NULL OR p_doc !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RW_DECISION_REF_REQUIRED'; END IF;
 SELECT m.mode INTO v_mode FROM rw_mode m WHERE m.singleton FOR SHARE;
 IF v_mode='MAINTENANCE_HOLD' THEN RAISE EXCEPTION 'RW_MODE_HOLD'; END IF;
 SELECT * INTO v_head FROM rw_head h WHERE h.context_id=p_context FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_NOT_FOUND'; END IF;
 IF v_head.generation IS DISTINCT FROM p_expected THEN RAISE EXCEPTION 'RW_GENERATION_DIFFERS'; END IF;
 SELECT dm.mark_id INTO v_pending FROM rw_drain_mark dm WHERE dm.context_id=p_context AND dm.generation=v_head.generation
  AND NOT EXISTS(SELECT 1 FROM rw_history x WHERE x.drain_mark_id=dm.mark_id);
 IF v_pending IS NOT NULL AND p_names_mark IS DISTINCT FROM v_pending THEN RAISE EXCEPTION 'RW_WITHDRAWAL_PENDING' USING DETAIL='RENEWAL_MUST_NAME_MARK'; END IF;
 IF p_names_mark IS NOT NULL AND v_pending IS DISTINCT FROM p_names_mark THEN RAISE EXCEPTION 'RW_MARK_STALE'; END IF;
 v_now:=clock_timestamp();
 IF p_valid_until IS NOT NULL AND rw_reached(v_now,p_valid_until) THEN RAISE EXCEPTION 'RW_VALID_UNTIL_PAST'; END IF;
 SELECT s.snapshot INTO v_snapshot FROM rw_snapshot s WHERE s.context_id=p_context;
 SELECT jsonb_agg(e.value ORDER BY e.value->>'source_id') INTO v_basis FROM jsonb_array_elements(p_basis) e;
 v_basis:=COALESCE(v_basis,'[]'::jsonb);
 SELECT d.kind,d.reason INTO v_kind,v_reason FROM rw_expiry_derive(rw_snapshot_sources(v_snapshot),v_basis,p_valid_until) d;
 IF v_kind='UNKNOWN' THEN RAISE EXCEPTION 'RW_EXPIRY_UNSUPPORTED' USING DETAIL=COALESCE(v_reason,'UNKNOWN'); END IF;
 SELECT * INTO v_hist FROM rw_history x WHERE x.context_id=p_context AND x.generation=v_head.generation;
 v_new:=v_head.generation+1;
 INSERT INTO rw_history(context_id,generation,rights,expiry_kind,valid_until,basis,issuer_actor,pd_id,git_commit,doc_sha256,recorded_at,drain_mark_id)
 VALUES(p_context,v_new,p_rights,v_kind,p_valid_until,v_basis,p_actor,p_pd,p_commit,p_doc,v_now,p_names_mark);
 UPDATE rw_head SET generation=v_new,rights=p_rights,expiry_kind=v_kind,valid_until=p_valid_until WHERE context_id=p_context;
 RETURN QUERY SELECT v_new,v_hist.valid_until,p_valid_until,(v_hist.valid_until IS NOT NULL AND p_valid_until IS NOT NULL AND p_valid_until<v_hist.valid_until),p_names_mark;
END $$;

-- WITHDRAW, step 1: the DRAIN MARK, committed in a transaction of its own before the withdrawal waits (E18). It takes the head
-- SHARED, so it is never held up by readers. Re-running finds the existing mark for that generation.
CREATE FUNCTION __RW_SCHEMA__.rw_withdraw_mark(p_context text,p_expected bigint,p_actor text,p_pd text,p_commit text,p_doc text)
RETURNS TABLE(r_mark_id bigint,r_generation bigint,r_marked_at timestamptz,r_created boolean,r_named boolean,r_issuer_actor text,r_pd_id text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE v_mark __RW_SCHEMA__.rw_drain_mark%ROWTYPE; v_head __RW_SCHEMA__.rw_head%ROWTYPE; v_mode text;
BEGIN
 IF p_context IS NULL OR p_context !~ '^[0-9a-f]{64}$' OR p_expected IS NULL OR p_expected<1 THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 IF p_actor IS NULL OR char_length(p_actor) NOT BETWEEN 1 AND 128 OR p_pd IS NULL OR p_pd !~ '^PD-[0-9]{4,}$'
    OR p_commit IS NULL OR p_commit !~ '^[0-9a-f]{40}$' OR p_doc IS NULL OR p_doc !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'RW_DECISION_REF_REQUIRED'; END IF;
 SELECT * INTO v_mark FROM rw_drain_mark dm WHERE dm.context_id=p_context AND dm.generation=p_expected;
 IF FOUND THEN
  RETURN QUERY SELECT v_mark.mark_id,v_mark.generation,v_mark.marked_at,false,EXISTS(SELECT 1 FROM rw_history x WHERE x.drain_mark_id=v_mark.mark_id),
   v_mark.issuer_actor,v_mark.pd_id; RETURN;
 END IF;
 SELECT m.mode INTO v_mode FROM rw_mode m WHERE m.singleton FOR SHARE;
 SELECT * INTO v_head FROM rw_head h WHERE h.context_id=p_context FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_NOT_FOUND'; END IF;
 IF v_head.generation IS DISTINCT FROM p_expected THEN RAISE EXCEPTION 'RW_GENERATION_DIFFERS'; END IF;
 INSERT INTO rw_drain_mark(context_id,generation,issuer_actor,pd_id,git_commit,doc_sha256,marked_at)
 VALUES(p_context,p_expected,p_actor,p_pd,p_commit,p_doc,clock_timestamp())
 ON CONFLICT (context_id,generation) DO NOTHING
 RETURNING * INTO v_mark;
 IF FOUND THEN
  RETURN QUERY SELECT v_mark.mark_id,v_mark.generation,v_mark.marked_at,true,false,v_mark.issuer_actor,v_mark.pd_id; RETURN;
 END IF;
 -- A concurrent withdrawal of the same generation committed its mark first (the insert waited for it and did nothing). That mark
 -- is the record: this call created nothing, and says whose mark it is (technical review R1, L-4).
 SELECT * INTO v_mark FROM rw_drain_mark dm WHERE dm.context_id=p_context AND dm.generation=p_expected;
 RETURN QUERY SELECT v_mark.mark_id,v_mark.generation,v_mark.marked_at,false,EXISTS(SELECT 1 FROM rw_history x WHERE x.drain_mark_id=v_mark.mark_id),
  v_mark.issuer_actor,v_mark.pd_id;
END $$;

-- WITHDRAW, step 2: wait for in-flight work (the head EXCLUSIVE lock, under the tool's lock_timeout) and append the generation
-- that names the mark: all four rights false, the previous expiry fields carried forward, the mark's issuer and reference.
CREATE FUNCTION __RW_SCHEMA__.rw_withdraw_apply(p_context text,p_mark bigint)
RETURNS TABLE(r_generation bigint,r_recorded_at timestamptz,r_created boolean,r_withdrawn boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__RW_SCHEMA__,pg_temp AS $$
DECLARE v_mode text; v_head __RW_SCHEMA__.rw_head%ROWTYPE; v_mark __RW_SCHEMA__.rw_drain_mark%ROWTYPE; v_hist __RW_SCHEMA__.rw_history%ROWTYPE;
 v_named __RW_SCHEMA__.rw_history%ROWTYPE; v_now timestamptz; v_new bigint;
 v_off jsonb:='{"EXECUTE_CREATE":false,"ARCHIVE_READ":false,"ARCHIVE_EXPORT":false,"EXECUTE_REPRODUCE":false}'::jsonb;
BEGIN
 IF p_context IS NULL OR p_context !~ '^[0-9a-f]{64}$' OR p_mark IS NULL THEN RAISE EXCEPTION 'RW_SHAPE'; END IF;
 SELECT m.mode INTO v_mode FROM rw_mode m WHERE m.singleton FOR SHARE;
 SELECT * INTO v_head FROM rw_head h WHERE h.context_id=p_context FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_NOT_FOUND'; END IF;
 SELECT * INTO v_mark FROM rw_drain_mark dm WHERE dm.mark_id=p_mark AND dm.context_id=p_context;
 IF NOT FOUND THEN RAISE EXCEPTION 'RW_MARK_NOT_FOUND'; END IF;
 SELECT * INTO v_named FROM rw_history x WHERE x.drain_mark_id=p_mark;
 IF FOUND THEN
  -- A re-run after completion finds the generation that names the mark. r_withdrawn tells a withdrawal (all four rights
  -- false) from a renewal that superseded the mark.
  RETURN QUERY SELECT v_named.generation,v_named.recorded_at,false,NOT (COALESCE((v_named.rights->>'EXECUTE_CREATE')::boolean,false) OR COALESCE((v_named.rights->>'ARCHIVE_READ')::boolean,false)
   OR COALESCE((v_named.rights->>'ARCHIVE_EXPORT')::boolean,false) OR COALESCE((v_named.rights->>'EXECUTE_REPRODUCE')::boolean,false));
  RETURN;
 END IF;
 IF v_mark.generation IS DISTINCT FROM v_head.generation THEN RAISE EXCEPTION 'RW_MARK_STALE'; END IF;
 SELECT * INTO v_hist FROM rw_history x WHERE x.context_id=p_context AND x.generation=v_head.generation;
 v_now:=clock_timestamp();
 v_new:=v_head.generation+1;
 INSERT INTO rw_history(context_id,generation,rights,expiry_kind,valid_until,basis,issuer_actor,pd_id,git_commit,doc_sha256,recorded_at,drain_mark_id)
 VALUES(p_context,v_new,v_off,v_hist.expiry_kind,v_hist.valid_until,v_hist.basis,v_mark.issuer_actor,v_mark.pd_id,v_mark.git_commit,v_mark.doc_sha256,v_now,p_mark);
 UPDATE rw_head SET generation=v_new,rights=v_off,expiry_kind=v_hist.expiry_kind,valid_until=v_hist.valid_until WHERE context_id=p_context;
 RETURN QUERY SELECT v_new,v_now,true,true;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- Status views for the publisher tool: the pending drain marks with their age, and one line per context.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE VIEW __RW_SCHEMA__.rw_pending_marks AS
 SELECT dm.mark_id,dm.context_id,dm.generation,dm.issuer_actor,dm.pd_id,dm.git_commit,dm.doc_sha256,dm.marked_at,
        clock_timestamp()-dm.marked_at AS age
 FROM __RW_SCHEMA__.rw_drain_mark dm JOIN __RW_SCHEMA__.rw_head h ON h.context_id=dm.context_id AND h.generation=dm.generation
 WHERE NOT EXISTS(SELECT 1 FROM __RW_SCHEMA__.rw_history x WHERE x.drain_mark_id=dm.mark_id);
CREATE VIEW __RW_SCHEMA__.rw_status AS
 SELECT h.context_id,h.generation,h.rights,h.expiry_kind,h.valid_until,
        (SELECT min((e.value->>'term_end_not_after')::timestamptz) FROM jsonb_array_elements(y.basis) e WHERE e.value->>'basis'='LEASE_TERM') AS earliest_term_end_not_after,
        (SELECT count(*) FROM __RW_SCHEMA__.rw_pending_marks pm WHERE pm.context_id=h.context_id) AS pending_marks
 FROM __RW_SCHEMA__.rw_head h JOIN __RW_SCHEMA__.rw_history y ON y.context_id=h.context_id AND y.generation=h.generation;

-- ---------------------------------------------------------------------------------------------------------------------
-- Grants. PUBLIC holds nothing here. Since R3 NO SQL FILE GRANTS ANYTHING TO A RUNTIME ROLE: each role's table and function list is one
-- list in the shared installer code (persistence/real_roles.py), applied after every file of the install kind, together with one
-- statement that revokes PUBLIC's EXECUTE on every routine of the schema (design 1.2 rule 5.3 (e), technical TR5-L2). A static test
-- checks that no file of the gateway has a GRANT.
-- ---------------------------------------------------------------------------------------------------------------------
REVOKE ALL ON __RW_SCHEMA__.rw_install,__RW_SCHEMA__.rw_mode,__RW_SCHEMA__.rw_snapshot,__RW_SCHEMA__.rw_drain_mark,__RW_SCHEMA__.rw_history,__RW_SCHEMA__.rw_head,
 __RW_SCHEMA__.rw_root_link,__RW_SCHEMA__.rw_lease,__RW_SCHEMA__.rw_pending_marks,__RW_SCHEMA__.rw_status FROM PUBLIC;
DO $$ DECLARE f record; BEGIN
 FOR f IN SELECT p.proname AS fname, pg_get_function_identity_arguments(p.oid) AS fargs FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='__RW_SCHEMA__' AND p.proname LIKE 'rw\_%' LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %I.%I(%s) FROM PUBLIC','__RW_SCHEMA__',f.fname,f.fargs);
 END LOOP;
END $$;
