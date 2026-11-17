"""Production CP5 composition: pinned ledger -> CP3 valuation -> CP4 security legs.

No new data source, caller-supplied price, or rounded display value is used.
Explicit metadata and action coverage are input records and are fully manifested.
"""
from __future__ import annotations

import json
import datetime
import uuid
from dataclasses import dataclass
from fractions import Fraction

from diversification import core, registry
from diversification.contracts import INSUFFICIENT, CapitalUniverseChoice, digest, metric, seal
from diversification.inputs import capital_buckets, history_for
from performance.engine import compute
from performance.grid import effective_window, grid_dates
from performance.identity import RecordingResolver
from performance.ledger_view import Inception, inception_of
from performance.periods import WindowRule, WindowSpec, resolve_window
from performance.series import MaxAvailable

ENGINE_ID = "diversification/cp5-0.2"


def compute_diversification(events, ledger_version, as_of, reporting_currency, port, resolver, market_conventions, conventions, *,
                            suppressions, metadata, coverage=(), capital_policy=None, request=None, frequency=None, cluster_threshold=None,
                            portfolio_id=None, account_scope=None, detection="CALLER_SUPPLIED", detection_policy=(),
                            _valuation=None, _instant=None):
    """ACTUAL state only. Default statistical request is explicitly 36 months WEEKLY."""
    from performance.grid import Frequency
    events = tuple(events)
    request = WindowSpec(WindowRule.TRAILING_MONTHS, 36) if request is None else request
    frequency = Frequency.WEEKLY if frequency is None else frequency
    if cluster_threshold is not None and not isinstance(cluster_threshold, Fraction):
        raise TypeError("cluster_threshold must be an exact Fraction or None")
    if metadata is not None and metadata.as_of > as_of:
        raise ValueError("metadata cannot look ahead of the valuation date")
    coverage = tuple(sorted(coverage, key=lambda c: c.listing_id))
    if len({c.listing_id for c in coverage}) != len(coverage):
        raise ValueError("duplicate total-return coverage")
    recorded_resolver = RecordingResolver(resolver)
    valuation = _valuation if _valuation is not None else compute(events, ledger_version, as_of, reporting_currency, port, recorded_resolver, market_conventions, conventions,
                        suppressions=suppressions, portfolio_id=portfolio_id, account_scope=account_scope, detection=detection, detection_policy=detection_policy)
    buckets = capital_buckets(valuation)
    (total,) = [m for m in valuation.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"]
    types = {b.key.split(":", 1)[1]: recorded_resolver.security_type(uuid.UUID(b.key.split(":", 1)[1])) for b in buckets if b.kind == "SECURITY"}
    metrics, weights = core.capital(buckets, total.exact, total.result.sufficiency_state,
                                   None if total.result.reason_code is None else total.result.reason_code.value,
                                   tuple(c.detail for c in total.causes if c.detail), metadata, types)
    is_max = isinstance(request, MaxAvailable)
    spec = WindowSpec(WindowRule.SINCE_INCEPTION) if is_max else request
    inception = inception_of(events, ledger_version, account_scope)
    uses_inception = is_max or spec.rule is WindowRule.SINCE_INCEPTION
    # Fixed constituent histories can predate acquisition and the portfolio.
    # The minimal date disables only the actual-TWR inception floor; CP3's
    # calendar-month resolution and positive-window validation remain unchanged.
    floor = inception if uses_inception else Inception(datetime.date.min, False)
    resolved = resolve_window(spec, as_of, floor, "NOT_RECONSTRUCTABLE")
    dates = () if resolved.window is None or valuation.manifest.as_of_causes else grid_dates(frequency, resolved.window.start, as_of)
    window = None if resolved.window is None else effective_window("MAX_AVAILABLE" if is_max else spec.rule.value, spec.months, frequency, resolved.window.start, as_of, dates)
    window_detail = (resolved.cause.detail if resolved.cause is not None else "NO_FULL_PERIOD") if window is None else None
    if valuation.manifest.as_of_causes:
        window_detail = "CALENDAR_COVERAGE_GAP"
    cov = {c.listing_id: c for c in coverage}
    histories, consumed = [], set()
    for b in buckets:
        if b.value == 0:
            continue
        history, files = history_for(b, dates, reporting_currency, port, recorded_resolver, market_conventions,
                                     coverage=cov.get(b.key.split(":", 1)[1]), as_of=as_of, instant=_instant)
        histories.append(history)
        consumed.update(files)
    # An explicit MAX_AVAILABLE may trim only a common leading run through the
    # last insufficient period, and it records why. Fixed windows never trim.
    max_after, max_cause = None, None
    if is_max and dates:
        bad = [i for h in histories for i, o in enumerate(h.observations) if o.state is INSUFFICIENT]
        if bad:
            cut = max(bad) + 1
            max_after = dates[cut]
            max_cause = "; ".join(sorted(h.key + ":" + (h.observations[cut - 1].reason or ",".join(h.observations[cut - 1].details) or "PERIOD_INSUFFICIENT")
                                         for h in histories if h.observations[cut - 1].state is INSUFFICIENT))
            dates = dates[cut:]
            from dataclasses import replace
            histories = [replace(h, observations=h.observations[cut:]) for h in histories]
            window = effective_window("MAX_AVAILABLE", None, frequency, resolved.window.start, as_of, dates)
            window_detail = "NO_FULL_PERIOD" if window is None else None
        if window is not None:
            from dataclasses import replace
            window = replace(window, max_available_start="INCEPTION" if max_after is None else "AFTER_INSUFFICIENT_PERIOD", max_available_after=max_after,
                             max_available_cause=max_cause)
    statistical, clusters = core.statistics(buckets, weights, histories, dates, registry.thresholds(frequency.value), registry.annualization(frequency.value), cluster_threshold,
                                           window_detail=window_detail)
    metrics += statistical
    synthetic = valuation.manifest.synthetic or bool(metadata is not None and metadata.synthetic) or any(c.synthetic for c in coverage)
    # Candidate use needs an explicit synthetic input chain, not merely the
    # presence of one synthetic file mixed into an otherwise real release.
    entirely_synthetic = False
    if hasattr(port, "export"):
        contents = port.export()
        lineages = [r.observation.lineage for r in contents.readings]
        lineages += [r.lineage for r in contents.adjusted]
        lineages += [e.series.lineage for e in contents.benchmarks + contents.risk_free]
        calendars = getattr(market_conventions.freshness, "calendars", None)
        if calendars is not None:
            lineages += [c.lineage for c in calendars.calendars()]
        entirely_synthetic = bool(lineages) and all(l.is_synthetic for l in lineages) and (metadata is None or metadata.synthetic) and all(c.synthetic for c in coverage)
    policy_confirmed = (isinstance(capital_policy, CapitalUniverseChoice) and capital_policy.choice == "FULL_NAV" and capital_policy.applies_to(portfolio_id, account_scope)
                        and (capital_policy.origin == "USER_CONFIRMED" or capital_policy.origin == "SYNTHETIC_CANDIDATE" and entirely_synthetic))
    if not policy_confirmed:
        independent = {"pairwise_correlation", "correlation_cluster_count"}
        metrics = [m if m.metric_id in independent else metric(m.metric_id, m.subject, state=INSUFFICIENT, details=("CAPITAL_UNIVERSE_UNCONFIRMED",), n=m.observation_count,
                                                              thresholds=m.thresholds) for m in metrics]
    manifest = {
        "schema": "finweb.diversification_manifest/1", "engine_id": ENGINE_ID, "registry_id": registry.REGISTRY_ID, "registry_digest": registry.REGISTRY_DIGEST,
        "state_kind": "ACTUAL", "portfolio_id": None if portfolio_id is None else str(portfolio_id), "account_scope": None if account_scope is None else str(account_scope),
        "reporting_currency": reporting_currency.code, "as_of": as_of, "synthetic": synthetic,
        "instant": _instant,
        "capital_policy": None if capital_policy is None else capital_policy.to_obj(), "capital_policy_confirmed": policy_confirmed,
        "capital_policy_digest": None if capital_policy is None else capital_policy.digest,
        "valuation_manifest": valuation.manifest.to_obj(), "valuation_result_digest": valuation.result_digest,
        "identity_digest": recorded_resolver.digest(), "identity_facts": [[a, b, v] for (a, b), v in sorted(recorded_resolver.seen.items())],
        "metadata": None if metadata is None else metadata.to_obj(), "metadata_digest": None if metadata is None else metadata.digest,
        "coverage": [c.to_obj() for c in coverage], "coverage_digest": digest([c.to_obj() for c in coverage]),
        "request": {"rule": "MAX_AVAILABLE" if is_max else spec.rule.value, "months": spec.months, "custom_base": spec.custom_base},
        "frequency": frequency.value, "window": None if window is None else window.to_obj(), "window_refusal": window_detail,
        "history_floor": {"rule": "PORTFOLIO_INCEPTION" if uses_inception else "NONE_FIXED_REQUEST", "date": inception.date if uses_inception else None,
                          "since_snapshot": inception.since_snapshot if uses_inception else False, "suffix_after": max_after, "suffix_cause": max_cause},
        "grid": list(dates), "cluster_threshold": cluster_threshold, "buckets": [b.to_obj() for b in buckets],
        "weights": None if weights is None or not policy_confirmed else [[k, weights[k]] for k in sorted(weights)],
        "complete_exposure_maps": [] if weights is None or not policy_confirmed else list(core.EXPOSURE_IDS),
        "histories": [h.to_obj() for h in histories], "histories_digest": digest([h.to_obj() for h in histories]),
        "history_files": [[f.file_sha256, f.adapter_id, f.adapter_version] for f in sorted(consumed)],
        "limitations": ["Current fixed weights, historical association, not actual portfolio TWR or forecast", "No ETF look-through",
                        "Non-synchronous market closes can distort covariance", "Cash/receivables use zero native interest and omit credit/liquidity/default risk"],
    }
    return seal(manifest, metrics, clusters)


def compute_diversification_current(events, ledger_version, instant, reporting_currency, market_at, resolver, conventions, *,
                                    suppressions, metadata, coverage=(), **kwargs):
    """Current mode uses CP3's date choice and only the derived market release M_t."""
    from performance.engine import compute_current
    view = market_at.view(instant)
    suppressed = tuple(suppressions(view) if callable(suppressions) else suppressions)
    class FixedView:
        def view(self, _instant):
            return view
    valuation = compute_current(events, ledger_version, instant, reporting_currency, resolver, FixedView(), conventions, suppressions=suppressed,
                                **{k: v for k, v in kwargs.items() if k in ("portfolio_id", "account_scope", "detection", "detection_policy")})
    return compute_diversification(events, ledger_version, valuation.manifest.as_of, reporting_currency, view.port, resolver, view.conventions, conventions,
                                   suppressions=suppressed, metadata=metadata, coverage=coverage, _valuation=valuation, _instant=instant, **kwargs)


@dataclass(frozen=True)
class Reproduction:
    status: str
    detail: str
    result: object = None


def reproduce_diversification(saved, expected_digest, events, port, resolver, market_conventions, conventions, *, suppressions, metadata, coverage=(), market_at=None):
    """Re-run the pinned question and compare every manifest field in both directions."""
    try:
        return _reproduce_diversification(saved, expected_digest, events, port, resolver, market_conventions, conventions,
                                          suppressions=suppressions, metadata=metadata, coverage=coverage, market_at=market_at)
    except (KeyError, TypeError, ValueError) as error:
        return Reproduction("INPUT_MISMATCH", "invalid or incompatible manifest input: " + str(error))


def _reproduce_diversification(saved, expected_digest, events, port, resolver, market_conventions, conventions, *, suppressions, metadata, coverage=(), market_at=None):
    from datetime import date
    from domain.currency import CurrencyCode
    from performance.grid import Frequency
    old = json.loads(saved.manifest_json if hasattr(saved, "manifest_json") else saved)
    from marketdata.canonical import canonical_json
    if not isinstance(old, dict):
        return Reproduction("INPUT_MISMATCH", "manifest must be an object")
    canonical_json(old)  # reject unsupported numbers/types rather than coercing them
    request = old["request"]
    spec = MaxAvailable() if request["rule"] == "MAX_AVAILABLE" else WindowSpec(WindowRule(request["rule"]), request["months"], None if request["custom_base"] is None else date.fromisoformat(request["custom_base"]))
    v = old["valuation_manifest"]
    def fraction(value):
        if value is None:
            return None
        if isinstance(value, dict):
            return Fraction(int(value["numerator"]), int(value["denominator"]))
        return Fraction(value)
    kwargs = dict(suppressions=suppressions, metadata=metadata, coverage=coverage, capital_policy=None if old.get("capital_policy") is None else CapitalUniverseChoice(**old["capital_policy"]),
                  request=spec, frequency=Frequency(old["frequency"]), cluster_threshold=fraction(old["cluster_threshold"]),
                                    portfolio_id=None if old["portfolio_id"] is None else uuid.UUID(old["portfolio_id"]), account_scope=None if old["account_scope"] is None else uuid.UUID(old["account_scope"]),
                                    detection=v["split_detection"], detection_policy=tuple(tuple(p) for p in v.get("detection_policy", ())))
    if old.get("instant") is not None:
        from datetime import datetime
        if market_at is None:
            raise ValueError("Current-mode reproduction requires the original market-at-instant provider")
        result = compute_diversification_current(events, v["ledger_version"], datetime.fromisoformat(old["instant"].replace("Z", "+00:00")), CurrencyCode(old["reporting_currency"]), market_at, resolver, conventions, **kwargs)
    else:
        result = compute_diversification(events, v["ledger_version"], date.fromisoformat(old["as_of"]), CurrencyCode(old["reporting_currency"]), port, resolver, market_conventions, conventions, **kwargs)
    new = json.loads(result.manifest_json)
    changed = sorted(k for k in set(old) | set(new) if k not in old or k not in new or canonical_json(old[k]) != canonical_json(new[k]))
    if changed:
        return Reproduction("INPUT_MISMATCH", ", ".join(changed), result)
    if expected_digest is None:
        return Reproduction("RESULT_NOT_COMPARED", "no expected result digest was supplied", result)
    return Reproduction("REPRODUCED" if result.result_digest == expected_digest else "RESULT_DIFFERS", "", result)
