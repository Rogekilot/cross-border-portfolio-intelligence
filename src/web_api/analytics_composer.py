"""Existing pure-engine questions and their own manifests; no new financial math."""
import datetime as dt
import uuid

from marketdata.canonical import canonical_json,sha256_hex
from performance import engine as performance
from performance.manifest import ENGINE_ID
from performance.series import Frequency
from product_contract.performance_methodology_registry import REGISTRY as PERFORMANCE_REGISTRY
from risk import engine as risk
from risk.registry import REGISTRY as RISK_REGISTRY
from risk_service.default_view import default_view
from risk_service.groups import BENCHMARK_GROUP,INDEPENDENT_GROUP
from web_api.analytics_context import AnalyticsError,LIMITS,specification

SCHEMA="finweb.cp7.analytics/1"
LIMITATIONS=("SYNTHETIC_ONLY: fictional2026-01-02 quotes/calendar; no real holdings or real-data readiness.",
    "ON_DEMAND_NOT_ARCHIVED: this analytics answer is not a saved artifact across future source/engine replacement.",
    "ONE_DATE_MARKET_SOURCE: later native ledger facts do not create price/FX/calendar history.",
    "CALLER_SUPPLIED_SUPPRESSIONS: no F8B service or corporate-action corroboration claim.",
    "HG3_SUPPORTING_GAPS_RETAINED: the66 disclosed supporting-evidence gaps are not closed by this transport.")


def digest(value):
    return sha256_hex(canonical_json(value).encode("utf-8"))


def bounded(value):
    if len(canonical_json(value).encode("utf-8"))>LIMITS["output_bytes"]:
        raise AnalyticsError(422,"ANALYTICS_OUTPUT_LIMIT","The complete analytics/evidence output exceeds2000000 UTF-8 bytes; nothing is truncated or saved","RESOURCE")
    return value


def _catalog(block):
    return None if block is None or block.catalog_id is None else dict(id=block.catalog_id,digest=block.catalog_digest)


def _registry_block(registry,is_risk):
    """The registry a result cites: its id and the digest of its text. The performance appendix has a second id: two appendix texts (performance-registry/1.0
    and 1.1) share `registry_id` performance/1.12 by the Quant's ruling, so the appendix id is printed too and the id alone never stands for one text."""
    block=dict(id=registry.registry_id,digest=registry.digest)
    if not is_risk:
        block["appendix_id"]=registry.appendix_id
    return block


def _wrapper(context,question,result,group):
    is_risk=question["family"]=="RISK"
    manifest=result.manifest
    series=manifest.series if is_risk else manifest
    registry=RISK_REGISTRY if is_risk else PERFORMANCE_REGISTRY
    ids=sorted({metric.metric_id for metric in result.metrics})
    binding=dict(portfolio_id=str(context.portfolio_id),revision_id=str(context.record["revision_id"]),ledger_version=context.record["ledger_version"],
        as_of=question["as_of"],scope=question["scope"],reporting_currency=series.reporting_currency,family=question["family"],group=group,
        question_digest=digest(question),release_id=series.release_id,input_sha256=context.world.input_sha256,calendar_sha256=context.world.calendar_sha256,
        fixture_as_of=context.world.as_of.isoformat(),engine_id=manifest.risk_engine_id if is_risk else manifest.engine_id,
        selection_pin=None if not is_risk or manifest.benchmark is None else manifest.benchmark.pin,
        benchmark_catalog=None if not is_risk else _catalog(manifest.benchmark),risk_free_catalog=None if not is_risk else _catalog(manifest.risk_free),
        registry=_registry_block(registry,is_risk),conventions=[list(row) for row in series.conventions])
    return dict(result_id=question["family"]+":"+group+":"+manifest.manifest_id+":"+result.result_digest,
        family=question["family"],group=group,binding=binding,binding_digest=digest(binding),engine_result=result.to_canonical_dict(),
        definitions=[registry.resolved(ident) for ident in ids if ident in registry.metric_ids])


def compose(context,question,*,group=None):
    """Return transport and trusted typed results, all bound to this one context."""
    family=question["family"]
    end=dt.date.fromisoformat(question["as_of"])
    account=None if question["scope"]["account_id"] is None else uuid.UUID(question["scope"]["account_id"])
    world=context.world
    common=dict(suppressions=(),portfolio_id=context.portfolio_id,account_scope=account,detection="CALLER_SUPPLIED")
    spec=specification(question["window"])
    results={}
    typed={}
    views=[]
    def register(result,result_group):
        wrapper=_wrapper(context,question,result,result_group)
        results[wrapper["result_id"]]=wrapper
        typed[wrapper["result_id"]]=result
        return wrapper["result_id"]
    if family!="RISK":
        args=(context.events,context.record["ledger_version"])
        market=(context.reporting_currency,world.port,world.resolver,world.conventions,world.perf)
        if family=="PERFORMANCE_WINDOW":
            result=performance.compute_window(*args,spec,end,*market,verify_identities=True,**common)
        elif family=="GAINS":
            result=performance.compute_gains(*args,end,*market,window=spec,**common)
        else:
            result=performance.compute_attribution(*args,spec,end,*market,**common)
        result_id=register(result,"PERFORMANCE")
        views=[dict(metric_id=metric.metric_id,metric_index=index,fallback=False,shown_result_id=result_id,
            refused_result_id=None,refused_metric_index=None,composition=None) for index,metric in enumerate(result.metrics)]
    else:
        for result_group,metrics in (("INDEPENDENT",INDEPENDENT_GROUP),("BENCHMARK",BENCHMARK_GROUP)):
            if group is not None and group!=result_group:
                continue
            cache={}
            def compute(request):
                key=repr(request)
                if key not in cache:
                    cache[key]=risk.compute_risk(context.events,context.record["ledger_version"],request,end,Frequency(question["frequency"]),
                        context.reporting_currency,world.port,world.resolver,world.conventions,world.perf,
                        risk_free_catalog=context.risk_free_catalog,benchmark_catalog=context.benchmark_catalog,selections=context.selection_rows,
                        selection_version=context.record["selection_version"],metrics=metrics,verify_identities=True,**common)
                    register(cache[key],result_group)
                return cache[key]
            if question["view"]=="DEFAULT":
                for metric_id in metrics:
                    view=default_view(compute,metric_id,spec)
                    shown=view.y if view.fallback else view.x
                    shown_id=register(shown,result_group)
                    refused_id=register(view.x,result_group) if view.fallback else None
                    views.append(dict(metric_id=metric_id,metric_index=next(index for index,metric in enumerate(shown.metrics) if metric.metric_id==metric_id),
                        fallback=view.fallback,shown_result_id=shown_id,refused_result_id=refused_id,
                        refused_metric_index=None if not view.fallback else next(index for index,metric in enumerate(view.x.metrics) if metric.metric_id==metric_id),
                        composition=view.evidence()))
            else:
                result=compute(spec)
                result_id=register(result,result_group)
                views.extend(dict(metric_id=metric.metric_id,metric_index=index,fallback=False,shown_result_id=result_id,
                    refused_result_id=None,refused_metric_index=None,composition=None) for index,metric in enumerate(result.metrics))
    record=context.record
    payload=dict(schema_version=SCHEMA,portfolio_id=str(context.portfolio_id),revision_id=str(record["revision_id"]),persisted=False,synthetic=True,
        question=question,revision=dict(as_of=record["as_of"],ledger_version=record["ledger_version"],selection_version=record["selection_version"],
        reporting_currency=context.reporting_currency.code),results=list(results.values()),views=views,limits=LIMITS.copy(),limitations=list(LIMITATIONS))
    return bounded(payload),typed


def resolve_proof(payload,proof):
    found=next((result for result in payload["results"] if result["result_id"]==proof["result_id"]),None)
    if found is None or found["binding_digest"]!=proof["expected_binding_digest"] or found["engine_result"]["manifest_id"]!=proof["expected_manifest_id"]:
        raise AnalyticsError(409,"ANALYTICS_BINDING_DIFFERS","The requested family/group/revision/source question no longer matches this result identity","BINDING")
    return found


def reproduce(context,question,wrapper,result,expected):
    world=context.world
    common=dict(suppressions=())
    if question["family"]=="RISK":
        report=risk.reproduce_risk(result.manifest,expected,context.events,world.port,world.resolver,world.conventions,world.perf,
            risk_free_catalog=context.risk_free_catalog,benchmark_catalog=context.benchmark_catalog,selections=context.selection_rows,**common)
    else:
        report=performance.reproduce(result.manifest,expected,context.events,world.port,world.resolver,world.conventions,world.perf,**common)
    return bounded(dict(schema_version=SCHEMA,portfolio_id=str(context.portfolio_id),revision_id=str(context.record["revision_id"]),family=question["family"],
        group=wrapper["group"],result_id=wrapper["result_id"],binding_digest=wrapper["binding_digest"],expected_manifest_id=result.manifest.manifest_id,
        expected_result_digest=expected,status=report.status.value,detail=report.detail,
        rerun_manifest_id=None if report.rerun is None else report.rerun.manifest.manifest_id,
        rerun_result_digest=None if report.rerun is None else report.rerun.result_digest,limits=LIMITS.copy()))
