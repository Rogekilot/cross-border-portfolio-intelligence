"""Exact diversification/1.0 mathematics over explicit audited inputs."""
from fractions import Fraction
from itertools import combinations

from diversification.contracts import AVAILABLE, LIMITED, INSUFFICIENT, metric
from diversification.numerics import PresentationTie, radical_sum
from performance.results import Cause, Part
from risk.states import combine
from risk.stats import sum_cross_deviations, sum_squared_deviations, sign_of

CAPITAL_IDS = ("largest_position_weight", "largest_security_weight", "top5_concentration", "hhi_concentration", "effective_positions")
EXPOSURE_IDS = ("country_exposure", "sector_exposure", "currency_exposure", "asset_class_exposure")


def aggregate(rows, extra=()):
    parts = [Part(str(i), row.state, row.reason, tuple(Cause(str(i), row.state.value, row.reason, d, d) for d in row.details)) for i, row in enumerate(rows)]
    return combine(parts + list(extra))


def capital(buckets, total, total_state, total_reason, total_details, metadata, security_types):
    """The full-NAV denominator and all four explicit exposure partitions."""
    agg = aggregate(buckets, (Part("total", total_state, total_reason),))
    details = set(total_details) | {d for b in buckets for d in b.details}
    if total is None or any(b.value is None for b in buckets):
        details.add("INCOMPLETE_VALUATION")
    elif total <= 0:
        details.add("NON_POSITIVE_TOTAL")
    elif any(b.value < 0 for b in buckets) or "NEGATIVE_COMPONENT" in details:
        details.add("NEGATIVE_COMPONENT")
    elif sum((b.value for b in buckets), Fraction()) != total:
        details.add("INCOMPLETE_VALUATION")
    else:
        details.discard("INCOMPLETE_VALUATION")
    refused = agg.state is INSUFFICIENT or bool(details & {"INCOMPLETE_VALUATION", "NON_POSITIVE_TOTAL", "NEGATIVE_COMPONENT"})
    if refused:
        return [metric(mid, state=INSUFFICIENT, reason=agg.reason if agg.state is INSUFFICIENT else None, details=details or {"INCOMPLETE_VALUATION"}) for mid in CAPITAL_IDS + EXPOSURE_IDS], None
    active = tuple(b for b in buckets if b.value != 0)
    weights = {b.key: b.value / total for b in active}
    ordered = sorted(weights, key=lambda key: (-weights[key], key))
    hhi = sum((w * w for w in weights.values()), Fraction())
    line = (("denominator", str(total)), ("universe", "listing-and-cash-bucket concentration; receivables included; no issuer or ETF look-through"),
            ("weights", ";".join(k + "=" + str(weights[k]) for k in sorted(weights))),
            ("zero_value_exclusions", ";".join(b.key for b in buckets if b.value == 0)))
    common = dict(state=agg.state, reason=agg.reason, details=details, lineage=line)
    securities = [b for b in active if b.kind == "SECURITY"]
    out = [metric("largest_position_weight", exact=weights[ordered[0]], **common), metric("top5_concentration", exact=sum((weights[k] for k in ordered[:5]), Fraction()), **common),
           metric("hhi_concentration", exact=hhi, **common), metric("effective_positions", exact=1 / hhi, **common)]
    out.append(metric("largest_security_weight", exact=max((weights[b.key] for b in securities), default=None), **common) if securities else
               metric("largest_security_weight", state=INSUFFICIENT, details=("NO_SECURITY_POSITIONS",)))
    rows = {} if metadata is None else {r.listing_id: r for r in metadata.rows}
    for dimension in ("country", "sector", "currency", "asset_class"):
        exposures = {}
        for b in active:
            listing = b.key.split(":", 1)[1] if b.kind == "SECURITY" else None
            row = rows.get(listing)
            security_type = security_types.get(listing)
            if dimension == "currency":
                category = b.currency or "UNKNOWN"
            elif b.kind != "SECURITY":
                category = b.kind
            elif dimension == "asset_class":
                category = {"COMMON_STOCK": "EQUITY", "ETF": "ETF"}.get(security_type, "UNKNOWN")
            elif dimension == "sector" and security_type == "ETF":
                category = "UNKNOWN"
            else:
                category = getattr(row, dimension, None) or "UNKNOWN"
            exposures[category] = exposures.get(category, Fraction()) + weights[b.key]
        unknown = exposures.get("UNKNOWN", Fraction())
        state = LIMITED if unknown and agg.state is AVAILABLE else agg.state
        dim_details = details | ({"UNKNOWN_CLASSIFICATION"} if unknown else set())
        # UNKNOWN_CLASSIFICATION supplies no lower-severity reason code.
        reason = None if unknown and agg.state is AVAILABLE else agg.reason
        for category, value in sorted(exposures.items()):
            out.append(metric(dimension + "_exposure", (category,), exact=value, state=state, reason=reason, details=dim_details,
                              lineage=line + (("classified_share", str(1 - unknown)), ("unknown_share", str(unknown)), ("metadata_digest", "NONE" if metadata is None else metadata.digest))))
    return out, weights


def _assessment(histories, dates, thresholds):
    expected = tuple(zip(dates, dates[1:]))
    rows = [o for h in histories for o in h.observations]
    n = len(expected)
    extra = []
    if any(tuple((o.start, o.end) for o in h.observations) != expected for h in histories):
        extra.append(Part("grid", INSUFFICIENT, None, (Cause("grid", INSUFFICIENT.value, None, "", "GRID_MISMATCH"),)))
    if n < thresholds[0]:
        extra.append(Part("count", INSUFFICIENT, None, (Cause("count", INSUFFICIENT.value, None, "", "INSUFFICIENT_OBSERVATIONS"),)))
    elif n < thresholds[1]:
        extra.append(Part("count", LIMITED, None, (Cause("count", LIMITED.value, None, "", "OBSERVATIONS_BELOW_STANDARD"),)))
    agg = aggregate(rows, extra)
    details = {c.detail for c in agg.causes if c.detail} | {d for row in rows for d in row.details}
    if any(row.state is INSUFFICIENT for row in rows):
        details.add("PERIOD_INSUFFICIENT")
    return agg, details


def statistics(buckets, weights, histories, dates, thresholds, annualization, cluster_threshold, *, window_detail=None):
    """Pair-specific availability, full-universe aggregates and signed Euler contributions."""
    securities = sorted(b.key for b in buckets if b.kind == "SECURITY" and b.value != 0)
    capital_keys = sorted(b.key for b in buckets if b.value != 0)
    by_key = {h.key: h for h in histories}
    n = max(0, len(dates) - 1)
    out, pairs, clusters = [], {}, ()
    def assessed(keys, capital_required=False):
        agg, details = _assessment([by_key[k] for k in keys], dates, thresholds)
        if capital_required:
            agg = aggregate([b for b in buckets if b.value != 0], (Part("history", agg.state, agg.reason, agg.causes),))
            details |= {d for b in buckets for d in b.details}
            if weights is None:
                return INSUFFICIENT, None, details | {"INCOMPLETE_VALUATION"}
        if window_detail:
            return INSUFFICIENT, None, details | {window_detail}
        return agg.state, agg.reason, details
    for left, right in combinations(securities, 2):
        state, reason, details = assessed((left, right))
        kw = dict(state=state, reason=reason, details=details, n=n, thresholds=thresholds)
        if state is INSUFFICIENT:
            m = metric("pairwise_correlation", (left, right), **kw)
        else:
            x, y = [o.value for o in by_key[left].observations], [o.value for o in by_key[right].observations]
            xx, yy, xy = sum_squared_deviations(x), sum_squared_deviations(y), sum_cross_deviations(x, y)
            if not xx or not yy:
                m = metric("pairwise_correlation", (left, right), state=INSUFFICIENT, details=details | {"ZERO_VARIANCE"}, n=n, thresholds=thresholds)
            else:
                m = metric("pairwise_correlation", (left, right), square=xy * xy / (xx * yy), sign=sign_of(xy),
                           lineage=(("S_ii", str(xx)), ("S_jj", str(yy)), ("S_ij", str(xy))), **kw)
        pairs[left, right] = m
        out.append(m)
    state, reason, details = assessed(securities)
    if len(securities) < 2:
        state, reason, details = INSUFFICIENT, None, details | {"TOO_FEW_SECURITIES"}
    elif any(m.state is INSUFFICIENT for m in pairs.values()):
        combined_pairs = combine([Part("pair:" + "/".join(pair), m.state, None if m.result.reason_code is None else m.result.reason_code.value)
                                  for pair, m in sorted(pairs.items())])
        state, reason = combined_pairs.state, combined_pairs.reason
        details |= {d for m in pairs.values() for d in m.details} | {"PAIR_UNAVAILABLE"}
    pair_state, pair_reason, pair_details = state, reason, set(details)
    if weights is None:
        denominator, line = Fraction(), ()
        state, reason, details = INSUFFICIENT, None, details | {"INCOMPLETE_VALUATION"}
    else:
        denominator = sum((weights[a] * weights[b] for a, b in pairs), Fraction())
        line = (("security_capital_coverage", str(sum((weights[k] for k in securities), Fraction()))),
            ("excluded_capital", ";".join(k + "=" + str(weights[k]) for k in capital_keys if k not in securities)),
            ("pair_count", str(len(pairs))), ("pair_weight_denominator", str(denominator)),
            ("limitations", "Historical association; non-synchronous market closes; no causality or forecast"))
        weighted_state, weighted_reason, weighted_details = assessed(securities, True)
        combined = combine((Part("pairs", state, reason), Part("weights", weighted_state, weighted_reason)))
        state, reason, details = combined.state, combined.reason, details | weighted_details
    common = dict(state=state, reason=reason, details=details, n=n, thresholds=thresholds, lineage=line)
    if state is INSUFFICIENT:
        out.append(metric("average_correlation", **common))
    else:
        terms = tuple((weights[a] * weights[b] * m.sign / denominator, m.exact_square) for (a, b), m in sorted(pairs.items()))
        try:
            out.append(metric("average_correlation", terms=terms, presented=radical_sum(terms), **common))
        except PresentationTie as tie:
            disclosed = dict(common, details=details | {"PRESENTATION_TIE"}, lineage=line + (("presentation", "PRESENTATION_TIE"),
                             ("tie_boundary", str(tie.boundary)), ("tie_low", str(tie.low)), ("tie_high", str(tie.high)),
                             ("tie_proof", "EXACT_RATIONAL" if tie.exact is not None else "CERTIFIED_INTERVAL_WIDTH_BELOW_1E-40")))
            out.append(metric("average_correlation", exact=tie.exact, terms=terms, presented=tie.value, **disclosed))
    state, reason, details = pair_state, pair_reason, pair_details
    common = dict(state=state, reason=reason, details=details, n=n, thresholds=thresholds)
    if cluster_threshold is None:
        out.append(metric("correlation_cluster_count", state=INSUFFICIENT, details=("CLUSTER_THRESHOLD_REQUIRED",), n=n, thresholds=thresholds))
    elif not isinstance(cluster_threshold, Fraction) or not 0 < cluster_threshold <= 1:
        out.append(metric("correlation_cluster_count", state=INSUFFICIENT, details=("INVALID_CLUSTER_THRESHOLD",), n=n, thresholds=thresholds))
    elif state is INSUFFICIENT:
        out.append(metric("correlation_cluster_count", **common))
    else:
        adjacency = {k: set() for k in securities}
        for (a, b), m in pairs.items():
            if m.sign > 0 and m.exact_square >= cluster_threshold * cluster_threshold:
                adjacency[a].add(b)
                adjacency[b].add(a)
        remaining, components = set(securities), []
        while remaining:
            pending, component = [min(remaining)], set()
            while pending:
                k = pending.pop()
                if k not in component:
                    component.add(k)
                    pending.extend(adjacency[k] - component)
            remaining -= component
            components.append(tuple(sorted(component)))
        clusters = tuple(sorted(components))
        out.append(metric("correlation_cluster_count", exact=Fraction(len(clusters)), **common))
    state, reason, details = assessed(capital_keys, True)
    common = dict(state=state, reason=reason, details=details, n=n, thresholds=thresholds)
    if state is INSUFFICIENT:
        out.append(metric("modeled_volatility", **common))
        out += [metric(mid, (key,), **common) for key in capital_keys for mid in ("risk_contribution_share", "risk_contribution_component")]
        return out, clusters
    vectors = {key: [o.value for o in by_key[key].observations] for key in capital_keys}
    covariance = {(a, b): sum_cross_deviations(vectors[a], vectors[b]) / (n - 1) for a in capital_keys for b in capital_keys}
    contributions = {a: weights[a] * sum((covariance[a, b] * weights[b] for b in capital_keys), Fraction()) for a in capital_keys}
    q = sum(contributions.values(), Fraction())
    if q < 0:
        refused = dict(state=INSUFFICIENT, details=("INVALID_COVARIANCE",), n=n, thresholds=thresholds)
        out.append(metric("modeled_volatility", **refused))
        out += [metric(mid, (k,), **refused) for k in capital_keys for mid in ("risk_contribution_share", "risk_contribution_component")]
        return out, clusters
    model_line = (("periodic_variance", str(q)), ("annualization", str(annualization)), ("model", "current fixed weights; history may predate acquisition; cash/receivable zero native interest"))
    out.append(metric("modeled_volatility", square=q * annualization, lineage=model_line, **common))
    for key in capital_keys:
        if not q:
            out += [metric(mid, (key,), state=INSUFFICIENT, details=details | {"ZERO_MODEL_VARIANCE"}, n=n, thresholds=thresholds) for mid in ("risk_contribution_share", "risk_contribution_component")]
        else:
            share = contributions[key] / q
            line = model_line + (("capital_weight", str(weights[key])), ("variance_contribution", str(contributions[key])))
            out.append(metric("risk_contribution_share", (key,), exact=share, lineage=line, **common))
            out.append(metric("risk_contribution_component", (key,), square=share * share * q * annualization, sign=sign_of(share), lineage=line, **common))
    return out, clusters
