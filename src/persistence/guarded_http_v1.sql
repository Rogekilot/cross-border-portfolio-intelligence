-- F3 metadata plus one explicitly reviewed fixed-fictional policy extension.
-- Historical F2 source files and old migrations stay unchanged.
CREATE FUNCTION __GH_SCHEMA__.gh_head(k text) RETURNS TABLE(generation bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GH_SCHEMA__,pg_temp AS $$
BEGIN
 IF k IS NULL OR k !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'F3_SHAPE'; END IF;
 RETURN QUERY SELECT h.generation FROM __GH_SCHEMA__.gw_head h WHERE h.context_id=k;
END $$;

CREATE FUNCTION __GH_SCHEMA__.gh_owned_roots(o uuid,k text) RETURNS TABLE(root_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GH_SCHEMA__,pg_temp AS $$
BEGIN
 IF o IS NULL OR k IS NULL OR k !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'F3_SHAPE'; END IF;
 IF (SELECT count(*) FROM __GH_SCHEMA__.gw_root x WHERE x.owner_id=o AND x.context_id=k)>32 THEN RAISE EXCEPTION 'F3_ROOT_BOUND'; END IF;
 RETURN QUERY SELECT x.root_id FROM __GH_SCHEMA__.gw_root x WHERE x.owner_id=o AND x.context_id=k ORDER BY x.root_id LIMIT 32;
END $$;

CREATE FUNCTION __GH_SCHEMA__.gh_operation(o uuid,r uuid,k text,op uuid DEFAULT NULL,rev uuid DEFAULT NULL,rep uuid DEFAULT NULL)
RETURNS TABLE(operation_id uuid,revision_id uuid,report_id uuid,kind text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GH_SCHEMA__,pg_temp AS $$
BEGIN
 IF o IS NULL OR r IS NULL OR k IS NULL OR k !~ '^[0-9a-f]{64}$' OR num_nonnulls(op,rev,rep)>1 THEN RAISE EXCEPTION 'F3_SHAPE'; END IF;
 RETURN QUERY SELECT x.operation_id,x.revision_id,x.report_id,x.kind
 FROM __GH_SCHEMA__.gw_operation x JOIN __GH_SCHEMA__.gw_root g ON g.root_id=x.root_id
 LEFT JOIN __GH_SCHEMA__.web_portfolio_revision v ON v.portfolio_id=x.root_id AND v.revision_id=x.revision_id
 WHERE x.owner_id=o AND x.root_id=r AND x.context_id=k AND g.owner_id=o AND g.context_id=k
 AND (op IS NULL OR x.operation_id=op) AND (rev IS NULL OR x.revision_id=rev) AND (rep IS NULL OR x.report_id=rep)
 ORDER BY COALESCE(v.revision_seq,0) DESC,x.operation_id LIMIT 1;
END $$;

REVOKE ALL ON FUNCTION __GH_SCHEMA__.gh_head(text),__GH_SCHEMA__.gh_owned_roots(uuid,text),__GH_SCHEMA__.gh_operation(uuid,uuid,text,uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION __GH_SCHEMA__.gh_head(text),__GH_SCHEMA__.gh_owned_roots(uuid,text),__GH_SCHEMA__.gh_operation(uuid,uuid,text,uuid,uuid,uuid) TO __GH_EXECUTOR__;

-- F3_POLICY_EXTENSION_BEGIN
-- Owner installation only: exact original body/hash, exactly one predicate.
-- No runtime function, grant, table, role or authority capability is added.
DO $f3_policy$
DECLARE original text; revised text; target oid;
 old_pred text := $f3_old$IF m->'capital_policy' IS DISTINCT FROM snapshot->'capital_policy'->'fields' OR m->'capital_policy'->>'origin' IS DISTINCT FROM 'SYNTHETIC_CANDIDATE' OR m->'capital_policy'->>'scope_kind' IS DISTINCT FROM 'PORTFOLIO' OR m->'capital_policy'->>'portfolio_id' IS DISTINCT FROM a.root_id::text THEN RAISE EXCEPTION 'F2_POLICY_DIFFERS'; END IF;$f3_old$;
 new_pred text := $f3_new$IF m->'capital_policy' IS DISTINCT FROM snapshot->'capital_policy'->'fields' OR m->'capital_policy'->>'origin' IS DISTINCT FROM 'SYNTHETIC_CANDIDATE' OR NOT ((m->'capital_policy'->>'scope_kind' IS NOT DISTINCT FROM 'PORTFOLIO' AND m->'capital_policy'->>'portfolio_id' IS NOT DISTINCT FROM a.root_id::text) OR m->'capital_policy' IS NOT DISTINCT FROM jsonb_build_object('choice','FULL_NAV','origin','SYNTHETIC_CANDIDATE','evidence','F3 fictional local trial only','decision_id','f3-fictional:1','scope_kind','GLOBAL_PRODUCT','product_id','cross-border-portfolio-intelligence','portfolio_id',NULL,'account_id',NULL)) THEN RAISE EXCEPTION 'F2_POLICY_DIFFERS'; END IF;$f3_new$;
BEGIN
 target:=to_regprocedure('__GH_SCHEMA__.gw_check_artifact(__GH_SCHEMA__.gw_artifact,text,uuid)');
 SELECT p.prosrc INTO original FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner
 WHERE p.oid=target AND p.proowner=current_user::regrole AND NOT r.rolcanlogin
 AND p.prosecdef AND p.prolang=(SELECT oid FROM pg_language WHERE lanname='plpgsql')
 AND p.prorettype='void'::regtype
 AND p.proconfig=ARRAY['search_path=pg_catalog, __GH_BARE_SCHEMA__, pg_temp'];
 IF original IS NULL OR encode(sha256(convert_to(original,'UTF8')),'hex') IS DISTINCT FROM '__GH_F2_PROSRC_SHA256__'
 OR (length(original)-length(replace(original,old_pred,'')))<>length(old_pred)
 THEN RAISE EXCEPTION 'F3_POLICY_TEMPLATE_DIFFERS'; END IF;
 revised:=replace(original,old_pred,new_pred);
 EXECUTE 'CREATE OR REPLACE FUNCTION __GH_SCHEMA__.gw_check_artifact(a __GH_SCHEMA__.gw_artifact,kind text,report uuid) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,__GH_SCHEMA__,pg_temp AS '||quote_literal(revised);
 IF (SELECT p.prosrc FROM pg_proc p WHERE p.oid=target) IS DISTINCT FROM revised THEN RAISE EXCEPTION 'F3_POLICY_EXTENSION_DIFFERS'; END IF;
END $f3_policy$;
