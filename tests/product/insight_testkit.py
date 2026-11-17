"""Actual source adapters for CP6 tests, using unmodified Quant CP4 inputs."""
import datetime as dt
import json
import uuid
from dataclasses import replace

from tests.product import cp4_golden_kit as g
from tests.product.test_diversification_integration import compute_case, configuration
from diversification.engine import compute_diversification_current
from insight_service.sources import DiversificationSource, RiskSource
from product_contract.analytics_policy import load_approved_capital_policy
from performance.engine import compute, compute_current
from domain.currency import CurrencyCode


def cp5_source(*, with_freshness=False, **overrides):
    overrides.setdefault("capital_policy", load_approved_capital_policy())
    result, runner, portfolio, kw = compute_case(**overrides)
    source = DiversificationSource(result, tuple(runner.events[portfolio["name"]]), runner.market.store, runner.market.ident,
                                   runner.market.conventions, runner.perf, tuple(kw["suppressions"]), kw["metadata"], tuple(kw["coverage"]))
    return (with_valuation(source) if with_freshness else source), runner, portfolio, kw


def with_valuation(source):
    manifest = json.loads(source.result.manifest_json)["valuation_manifest"]
    kwargs = dict(suppressions=source.suppressions, portfolio_id=uuid.UUID(manifest["portfolio_id"]),
                  account_scope=None if manifest["scope"] == "PORTFOLIO" else uuid.UUID(manifest["scope"].split(":", 1)[1]),
                  detection=manifest["split_detection"], detection_policy=tuple(tuple(v) for v in manifest["detection_policy"]))
    if manifest["instant"] is None:
        result = compute(source.events, manifest["ledger_version"], dt.date.fromisoformat(manifest["as_of"]), CurrencyCode(manifest["reporting_currency"]),
                         source.port, source.resolver, source.market_conventions, source.conventions, **kwargs)
    else:
        result = compute_current(source.events, manifest["ledger_version"], dt.datetime.fromisoformat(manifest["instant"].replace("Z", "+00:00")),
                                 CurrencyCode(manifest["reporting_currency"]), source.resolver, source.market_at, source.conventions, **kwargs)
    return replace(source, freshness_result=result)


def cp5_current_source(instant="2026-01-09T09:00:00Z", *, with_freshness=False):
    runner = g.shared_runner(3)
    portfolio = next(p for p in runner.data["portfolios"] if p["name"].startswith("R7 "))
    events = tuple(runner.events[portfolio["name"]])
    pin = max(e.ledger_seq for e in events)
    kw = configuration(runner, runner.ids(portfolio["portfolio_id"]))
    kw["capital_policy"] = load_approved_capital_policy()
    result = compute_diversification_current(events, pin, g._utc(instant), CurrencyCode(portfolio["reporting_currency"]), runner.market.market_at,
                                             runner.market.ident, runner.perf, suppressions=(), portfolio_id=runner.ids(portfolio["portfolio_id"]), **kw)
    source = DiversificationSource(result, events, runner.market.store, runner.market.ident, runner.market.conventions, runner.perf, (), kw["metadata"], kw["coverage"], runner.market.market_at)
    return (with_valuation(source) if with_freshness else source), runner, portfolio


def cp4_source(aid="Q1-B1", metrics=("risk_active_return",), *, part=2, prefix="Q1 "):
    runner = g.shared_runner(part)
    portfolio = next(p for p in runner.data["portfolios"] if p["name"].startswith(prefix))
    assertion = next(a for a in portfolio["assertions"] if a["id"] == aid)
    item = next(i for i in assertion["expect"] if i.get("kind") == "active_return")
    result = runner.risk(portfolio, assertion, item, metrics)
    version = runner.version(portfolio, assertion)
    return RiskSource(result, tuple(runner.events[portfolio["name"]]), runner.market.store, runner.market.ident,
                      runner.market.conventions, runner.perf, tuple(runner.suppressions_for(portfolio, version)),
                      risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=runner.catalog,
                      selections=tuple(g.selections_of(portfolio, runner.ids))), runner, portfolio, assertion, item
