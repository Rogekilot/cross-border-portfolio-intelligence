"""Pinned ledger/currency and existing synthetic/F8-B gates for CP5."""
from dataclasses import dataclass
import json
from diversification.engine import compute_diversification
from risk_service.service import currency_of, pin_ledger, _gate, _suppressions
from performance_service import service as perf


def compute_diversification_for_portfolio(conn, portfolio_id, as_of, port, resolver, market_conventions, conventions, *,
                                           policy, metadata, coverage=(), capital_policy=None, request=None, frequency=None, cluster_threshold=None,
                                           ledger_version=None, account_scope=None, allow_synthetic=False):
    reporting = currency_of(conn, portfolio_id)
    pin, events = pin_ledger(conn, portfolio_id, ledger_version)
    refusal = _gate(events, pin, port, policy, allow_synthetic)
    if refusal is not None:
        return refusal
    suppressions = _suppressions(events, pin, portfolio_id, port, resolver, market_conventions, policy)
    return compute_diversification(events, pin, as_of, reporting, port, resolver, market_conventions, conventions,
                                   suppressions=suppressions, metadata=metadata, coverage=coverage, capital_policy=capital_policy, request=request, frequency=frequency,
                                   cluster_threshold=cluster_threshold, portfolio_id=portfolio_id, account_scope=account_scope,
                                   detection=perf.DETECTION, detection_policy=perf.policy_reference(policy))


def compute_diversification_current_for_portfolio(conn, portfolio_id, instant, market_at, resolver, conventions, *,
                                                   policy, metadata, coverage=(), ledger_version=None, allow_synthetic=False, **kwargs):
    from diversification.engine import compute_diversification_current
    reporting = currency_of(conn, portfolio_id)
    pin, events = pin_ledger(conn, portfolio_id, ledger_version)
    view = market_at.view(instant)
    refusal = _gate(events, pin, view.port, policy, allow_synthetic)
    if refusal is not None:
        return refusal
    def suppressions(v):
        return perf.detect_suppressions(events, pin, portfolio_id, v.port, resolver, v.calendars, policy)
    return compute_diversification_current(events, pin, instant, reporting, market_at, resolver, conventions, suppressions=suppressions,
                                           metadata=metadata, coverage=coverage, portfolio_id=portfolio_id,
                                           detection=perf.DETECTION, detection_policy=perf.policy_reference(policy), **kwargs)


@dataclass(frozen=True)
class AnalyticsBundle:
    """The actual CP5 snapshot and drift, plus CP4 sources for §19 risk drift."""
    diversification: object
    diversification_drift: object
    risk: object
    risk_drift: object


def compute_analytics_for_portfolio(conn, portfolio_id, as_of, port, resolver, market_conventions, conventions, *,
                                    policy, metadata, coverage=(), capital_policy=None, request=None, frequency=None, cluster_threshold=None,
                                    ledger_version=None, account_scope=None, allow_synthetic=False, baseline=None, targets=(),
                                    risk_baseline=None, risk_targets=(), benchmark_catalog=None, risk_free_catalog=None, selection_version=None):
    """One service call for all CP5 and §19 metrics, with explicit immutable baselines.

    The risk call uses the SAME ledger pin as the snapshot, and pins the benchmark
    log independently. Missing owner decisions, baselines and targets stay explicit
    refusals; no acceptance or target is generated here.
    """
    from diversification.drift import compute_drift_result
    from performance.grid import Frequency
    from performance.periods import WindowRule, WindowSpec
    from risk_service.service import compute_risk_for_portfolio, RiskRefusal
    from risk_service.catalogs import load_benchmark_catalog
    request = WindowSpec(WindowRule.TRAILING_MONTHS, 36) if request is None else request
    frequency = Frequency.WEEKLY if frequency is None else frequency
    current = compute_diversification_for_portfolio(conn, portfolio_id, as_of, port, resolver, market_conventions, conventions,
                                                    policy=policy, metadata=metadata, coverage=coverage, capital_policy=capital_policy, request=request, frequency=frequency,
                                                    cluster_threshold=cluster_threshold, ledger_version=ledger_version, account_scope=account_scope, allow_synthetic=allow_synthetic)
    if isinstance(current, RiskRefusal):
        return current
    pin = json.loads(current.manifest_json)["valuation_manifest"]["ledger_version"]
    # No user selection is an ordinary insufficient-data result. Load the
    # committed admitted catalog when the caller did not inject one; never pass
    # a missing configuration into CP4 or invent a benchmark entry.
    if benchmark_catalog is None:
        benchmark_catalog = load_benchmark_catalog()
    risk = compute_risk_for_portfolio(conn, portfolio_id, request, as_of, frequency, port, resolver, market_conventions, conventions,
                                     policy=policy, benchmark_catalog=benchmark_catalog, risk_free_catalog=risk_free_catalog, ledger_version=pin,
                                     selection_version=selection_version, account_scope=account_scope, allow_synthetic=allow_synthetic,
                                     metrics=("risk_beta", "risk_volatility", "risk_active_return", "risk_tracking_error", "risk_max_drawdown"))
    return AnalyticsBundle(current, compute_drift_result(current, baseline, targets), risk,
                           risk if isinstance(risk, RiskRefusal) else compute_drift_result(risk, risk_baseline, risk_targets))
