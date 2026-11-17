"""Pure transport/resource/zero-null contracts over the shipped fictional world."""
import datetime as dt
import json
import sys
import unittest
import uuid
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))

from domain.catalogs import parse_benchmark_catalog,parse_risk_free_catalog
from domain.currency import Money
from marketdata.canonical import canonical_json
from pydantic import ValidationError
from web_api.analytics_composer import bounded,compose,reproduce,resolve_proof
from web_api.analytics_context import AnalyticsContext,AnalyticsError,LIMITS,guard_span,verify_fixture_bytes
from web_api.analytics_requests import AnalyticsProofRequest,AnalyticsQuestion
from web_api.synthetic import SyntheticWorld

IDENT=uuid.UUID(int=10001)
ROOT=Path(__file__).resolve().parents[2]


def question(family="PERFORMANCE_WINDOW",**changes):
    value=dict(revision_id=str(IDENT),as_of="2026-01-02",family=family,
        window=dict(rule="SINCE_INCEPTION",months=None,base=None),frequency="WEEKLY" if family=="RISK" else None,
        scope=dict(kind="PORTFOLIO",account_id=None),view="REQUESTED",synthetic_acknowledged=True)
    value.update(changes)
    return AnalyticsQuestion(**value).model_dump()


def context(*,basis=None,as_of=dt.date(2026,1,2)):
    world=SyntheticWorld()
    request=dict(name="Fictional unit contract",positions=[dict(symbol="SYN-A",quantity="1")],cash="0")
    events=world.opening_events(IDENT,request)
    if basis is not None:
        events=(replace(events[0],event=replace(events[0].event,cost_basis=Money(Decimal(basis),world.currency),acquired_on=dt.date(2026,1,1))),)
    return AnalyticsContext(IDENT,dict(revision_id=IDENT,ledger_version=events[-1].ledger_seq,selection_version=0,as_of=as_of),events,
        (dict(account_id=str(events[0].event.account_id),name="Fictional account"),),world.currency,world,(),
        parse_benchmark_catalog((ROOT/"data/marketdata/BENCHMARKS.json").read_bytes()),
        parse_risk_free_catalog((ROOT/"data/marketdata/RISK_FREE.json").read_bytes()))


def proof(payload,index=0):
    result=payload["results"][index]
    return dict(question=payload["question"],result_id=result["result_id"],expected_binding_digest=result["binding_digest"],
        expected_manifest_id=result["engine_result"]["manifest_id"],expected_result_digest=result["engine_result"]["result_digest"])


class AnalyticsPureTests(unittest.TestCase):
    def test_strict_required_variants_and_no_caller_pin_or_values(self):
        self.assertEqual(question()["as_of"],"2026-01-02")
        for changes in (dict(ledger_version=1),dict(frequency="WEEKLY"),dict(synthetic_acknowledged=False),
                        dict(window=dict(rule="TRAILING_MONTHS",months=True,base=None)),
                        dict(window=dict(rule="CUSTOM",months=None,base="2026-02-30")),
                        dict(window=dict(rule="MAX_AVAILABLE",months=None,base=None)),
                        dict(scope=dict(kind="ACCOUNT",account_id=None))):
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                question(**changes)
        with self.assertRaises(ValidationError):
            question("RISK",view="DEFAULT")

    def test_all_four_families_preserve_canonical_result_and_exact_reproduction(self):
        ctx=context()
        for family in ("PERFORMANCE_WINDOW","GAINS","ATTRIBUTION","RISK"):
            q=question(family)
            payload,typed=compose(ctx,q)
            for wrapper in payload["results"]:
                result=typed[wrapper["result_id"]]
                self.assertEqual(canonical_json(wrapper["engine_result"]),result.canonical_json())
                report=reproduce(ctx,q,wrapper,result,result.result_digest)
                self.assertEqual(report["status"],"REPRODUCED",(family,report))
                report=reproduce(ctx,q,wrapper,result,"0"*64)
                self.assertEqual(report["status"],"RESULT_DIFFERS")

    def test_the_binding_names_the_registry_text_it_used(self):
        # market-data/1.16 label re-issue (section 11 item 35): risk/1.11 is a new id; the performance appendix keeps registry_id performance/1.12 under
        # appendix performance-registry/1.2, so the binding prints the appendix id and the digest, not the shared id alone
        from product_contract.performance_methodology_registry import REGISTRY as performance_registry  # noqa: PLC0415
        from risk.registry import REGISTRY as risk_registry  # noqa: PLC0415

        ctx=context()
        payload,_=compose(ctx,question("PERFORMANCE_WINDOW"))
        self.assertEqual({row["binding"]["registry"]["id"] for row in payload["results"]},{"performance/1.12"})
        for row in payload["results"]:
            self.assertEqual(row["binding"]["registry"],dict(id="performance/1.12",digest=performance_registry.digest,appendix_id="performance-registry/1.2"))
        payload,_=compose(ctx,question("RISK"))
        for row in payload["results"]:
            self.assertEqual(row["binding"]["registry"],dict(id="risk/1.11",digest=risk_registry.digest))  # a risk id is unique to its text: no appendix id

    def test_zero_basis_zero_gain_and_missing_basis_are_distinct(self):
        # Shipped fictional quote is100. One unit with basis100 has exact gain0;
        # basis0 has gain100, while an absent basis cannot assert either amount.
        for basis,expected in (("100","0"),("0","100"),(None,None)):
            payload,_=compose(context(basis=basis),question("GAINS"))
            metrics=payload["results"][0]["engine_result"]["metrics"]
            rows=[m for m in metrics if m["metric_id"]=="unrealized_gain" and m["view"]=="REPORTING"]
            self.assertEqual(len(rows),1)
            metric=json.loads(canonical_json(rows[0]))
            self.assertEqual(metric["value"],expected)
            self.assertEqual(metric["exact"],None if expected is None else expected+"/1")
            if expected is None:
                self.assertEqual(metric["state"],"INSUFFICIENT_DATA")

    def test_default_uses_original_xy_groups_and_preserves_null_count(self):
        q=question("RISK",window=dict(rule="TRAILING_MONTHS",months=36,base=None),view="DEFAULT")
        payload,_=compose(context(),q)
        self.assertEqual({row["group"] for row in payload["results"]},{"INDEPENDENT","BENCHMARK"})
        self.assertTrue(any(view["fallback"] for view in payload["views"]))
        by_id={row["result_id"]:row for row in payload["results"]}
        for view in payload["views"]:
            shown=by_id[view["shown_result_id"]]["engine_result"]["metrics"][view["metric_index"]]
            self.assertIsNone(shown["value"])
            self.assertIsNone(shown["observation_count"])
            self.assertEqual(shown["metric_id"],view["metric_id"])
            if view["fallback"]:
                self.assertEqual(view["composition"]["x_manifest_id"],by_id[view["refused_result_id"]]["engine_result"]["manifest_id"])
                self.assertEqual(view["composition"]["y_manifest_id"],by_id[view["shown_result_id"]]["engine_result"]["manifest_id"])

    def test_proof_binding_refuses_wrong_family_group_manifest_but_wrong_digest_reaches_engine(self):
        ctx=context();payload,typed=compose(ctx,question("GAINS"));body=proof(payload)
        AnalyticsProofRequest(**body)
        wrapper=resolve_proof(payload,{**body,"expected_result_digest":"0"*64})
        report=reproduce(ctx,payload["question"],wrapper,typed[wrapper["result_id"]],"0"*64)
        self.assertEqual(report["status"],"RESULT_DIFFERS")
        for field in ("expected_binding_digest","expected_manifest_id"):
            with self.assertRaises(AnalyticsError):
                resolve_proof(payload,{**body,field:"0"*64})
        with self.assertRaises(ValidationError):
            AnalyticsProofRequest(**{**body,"question":question("ATTRIBUTION")})

    def test_span_guard_covers_default_max_acquisition_and_requested_dates(self):
        ctx=context()
        for q in (question(as_of="9999-12-31"),question(window=dict(rule="CUSTOM",months=None,base="1900-01-01")),
                  question("RISK",as_of="9999-12-31",window=dict(rule="MAX_AVAILABLE",months=None,base=None))):
            with self.assertRaises(AnalyticsError) as error:
                guard_span(ctx.events,ctx.record["ledger_version"],q,ctx.world.as_of)
            self.assertEqual(error.exception.code,"ANALYTICS_SPAN_LIMIT")
        old=(replace(ctx.events[0],event=replace(ctx.events[0].event,acquired_on=dt.date(1900,1,1))),)
        with self.assertRaises(AnalyticsError):
            guard_span(old,1,question("GAINS"),ctx.world.as_of)

    def test_output_bound_counts_whole_utf8_and_never_truncates(self):
        with patch.dict(LIMITS,output_bytes=20):
            with self.assertRaises(AnalyticsError) as error:
                bounded(dict(value="界"*20))
            self.assertEqual(error.exception.code,"ANALYTICS_OUTPUT_LIMIT")

    def test_changed_raw_fixture_is_not_hidden_by_cached_world(self):
        world=SyntheticWorld();verify_fixture_bytes(world)
        with patch("web_api.analytics_context.Path.read_bytes",return_value=b"changed"):
            with self.assertRaises(AnalyticsError) as error:
                verify_fixture_bytes(world)
            self.assertEqual(error.exception.code,"ANALYTICS_SOURCE_DIFFERS")
