"""Exact, reference-bound drift (diversification/1.0 §7).

Snapshots freeze the complete pinned computation, not a caller's compatibility
label. A baseline records an external acceptance; this module never grants one.
Targets are individual user policies, never completed into an allocation map.
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from diversification.contracts import AVAILABLE, INSUFFICIENT, CapitalUniverseChoice, Metric, Result, digest, metric, seal
from diversification.core import CAPITAL_IDS, EXPOSURE_IDS
from diversification.numerics import PresentationTie, radical_sum
from marketdata.canonical import canonical_json, sha256_hex
from performance.numerics import round_half_up, to_decimal_exact
from performance.results import Part
from product_contract.metric_state import MetricResult
from product_contract.vocabulary import ReasonCode, SufficiencyState
from risk.sqrt import isqrt
from risk.states import combine

RISK_IDS = ("risk_beta", "risk_volatility", "risk_active_return", "risk_tracking_error", "risk_max_drawdown")
SUPPORTED = frozenset(CAPITAL_IDS + EXPOSURE_IDS + RISK_IDS)
BENCHMARK_IDS = frozenset(("risk_beta", "risk_active_return", "risk_tracking_error"))


@dataclass(frozen=True)
class Snapshot:
    """Portable immutable source bytes plus their supplied content identity."""
    content_json: str
    content_digest: str

    @property
    def digest(self):
        return self.content_digest

    def to_obj(self):
        return {"content": json.loads(self.content_json), "digest": self.content_digest}


def snapshot(source):
    """Capture a CP5 Result or CP4 RiskResult without retaining mutable dicts."""
    if isinstance(source, Snapshot):
        return source
    from risk.manifest import RiskResult
    if not isinstance(source, (Result, RiskResult)):
        raise TypeError("drift requires a pinned diversification or risk result")
    text = source.canonical_json()
    return Snapshot(text, sha256_hex(text.encode("utf-8")))


@dataclass(frozen=True)
class Qualifier:
    """A source metric's unit and canonical semantic compatibility signature."""
    metric_id: str
    subject: tuple[str, ...]
    unit: str
    reporting_currency: str
    signature_json: str

    def __post_init__(self):
        object.__setattr__(self, "subject", tuple(self.subject))
        object.__setattr__(self, "signature_json", canonical_json(json.loads(self.signature_json)))

    def to_obj(self):
        return {"metric_id": self.metric_id, "subject": list(self.subject), "unit": self.unit,
                "reporting_currency": self.reporting_currency, "signature": json.loads(self.signature_json)}


@dataclass(frozen=True)
class Baseline:
    baseline_id: str
    snapshot: Snapshot
    accepted: bool
    acceptance_reference: str

    def __post_init__(self):
        if not isinstance(self.snapshot, Snapshot):
            object.__setattr__(self, "snapshot", snapshot(self.snapshot))

    def to_obj(self):
        return {"baseline_id": self.baseline_id, "snapshot": self.snapshot.to_obj(), "accepted": self.accepted,
                "acceptance_reference": self.acceptance_reference}

    @property
    def digest(self):
        return digest(self.to_obj())


@dataclass(frozen=True)
class Target:
    target_id: str
    qualifier: Qualifier
    exact: Fraction
    effective_date: datetime.date
    provenance: str
    evidence: str

    def to_obj(self):
        return {"target_id": self.target_id, "qualifier": self.qualifier.to_obj(), "exact": self.exact,
                "effective_date": self.effective_date, "provenance": self.provenance, "evidence": self.evidence}

    @property
    def digest(self):
        return digest(self.to_obj())


class _Invalid(ValueError):
    pass


def _required(obj, *keys):
    if not isinstance(obj, dict) or any(k not in obj for k in keys):
        raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
    return [obj[k] for k in keys]


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _date(value):
    if not isinstance(value, str):
        raise _Invalid("INVALID_SNAPSHOT_DATE")
    return datetime.date.fromisoformat(value)


def _unit(mid):
    return "COUNT" if mid == "effective_positions" else "RATIO" if mid == "risk_beta" else "FRACTION"


def _normal_terms(terms):
    rational, roots = Fraction(), {}
    for c, q in terms:
        if not isinstance(c, Fraction) or not isinstance(q, Fraction) or q < 0:
            raise _Invalid("INVALID_EXACT_SOURCE")
        if not c or not q:
            continue
        n, d = isqrt(q.numerator), isqrt(q.denominator)
        if n * n == q.numerator and d * d == q.denominator:
            rational += c * Fraction(n, d)
        else:
            roots[q] = roots.get(q, Fraction()) + c
    out = tuple((c, q) for q, c in sorted(roots.items()) if c)
    return rational, out


def _terms(m):
    if m.exact is not None:
        return ((m.exact, Fraction(1)),)
    if m.exact_square is not None:
        return ((Fraction(m.sign), m.exact_square),)
    return m.radical_terms


def _tie_lineage(tie):
    """The inherited presentation decision never replaces an exact witness."""
    return (("presentation", "PRESENTATION_TIE"), ("presentation_tie_boundary", str(tie.boundary)),
            ("presentation_tie_low", str(tie.low)), ("presentation_tie_high", str(tie.high)),
            ("presentation_tie_width", str(tie.high - tie.low)),
            ("presentation_tie_proof", "EXACT_EQUALITY" if tie.exact is not None else "CERTIFIED_INTERVAL_BOUNDARY"))


def _metric(row, kind):
    mid, value, state, reason = _required(row, "metric_id", "value", "state", "reason")
    state = SufficiencyState(state)
    exact = None if row.get("exact") is None else Fraction(row["exact"])
    square = None if row.get("exact_square") is None else Fraction(row["exact_square"])
    terms = tuple((Fraction(c), Fraction(q)) for c, q in row.get("radical_terms", ()))
    sign = row.get("sign")
    if (value is None) != (state is INSUFFICIENT):
        raise _Invalid("SOURCE_STATE_VALUE_CONTRADICTION")
    if value is None and (exact is not None or square is not None or terms or sign is not None):
        raise _Invalid("SOURCE_STATE_VALUE_CONTRADICTION")
    if value is not None:
        if sum((exact is not None, square is not None, bool(terms))) != 1:
            raise _Invalid("MISSING_OR_AMBIGUOUS_EXACT_SOURCE")
        if square is not None and (square < 0 or sign not in (-1, 0, 1) or (sign == 0) != (square == 0)):
            raise _Invalid("INVALID_EXACT_SOURCE")
        if square is None and not terms and sign is not None:
            raise _Invalid("INVALID_EXACT_SOURCE")
    details = tuple(row.get("details", ())) or (("SOURCE_INSUFFICIENT",) if value is None else ())
    m = Metric(mid, tuple(row.get("subject", ())), MetricResult(None if value is None else Decimal(value), state, None if reason is None else ReasonCode(reason)),
               exact, square, sign, details, row.get("observation_count"), None if row.get("thresholds") is None else tuple(row["thresholds"]),
               tuple(tuple(p) for p in row.get("lineage", ())), terms, row.get("manifest_id"))
    if value is not None:
        rational, radicals = _normal_terms(_terms(m))
        try:
            presented = (radical_sum(radicals + ((rational, Fraction(1)),)) if radicals else
                         to_decimal_exact(round_half_up(rational, 12)))
        except PresentationTie as tie:
            presented = tie.value
        if presented != m.result.value:
            raise _Invalid("SOURCE_STATE_VALUE_CONTRADICTION")
    return m


def _qualifier(manifest, row, kind):
    mid = row["metric_id"]
    registry, registry_digest, state = _required(manifest, "registry_id", "registry_digest", "state_kind")
    if state != "ACTUAL" or not _text(registry) or not _text(registry_digest):
        raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
    method = row.get("method_key")
    if method != registry + "#" + mid:
        raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
    source = manifest if kind == "CP5" else manifest["series_manifest"]
    portfolio, currency = _required(source, "portfolio_id", "reporting_currency")
    if not _text(portfolio) or not _text(currency):
        raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
    scope = source.get("account_scope") if kind == "CP5" else source.get("scope")
    if kind == "CP5":
        _required(source, "account_scope")
        scope = "PORTFOLIO" if scope is None else "ACCOUNT:" + scope
    elif not _text(scope):
        raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
    signature = {"portfolio_id": portfolio, "scope": scope, "state_kind": state, "method_key": method,
                 "registry_digest": registry_digest, "frequency": "NOT_APPLICABLE", "lookback_rule": "AS_OF",
                 "duration": "NOT_APPLICABLE", "grid_rule": "NOT_APPLICABLE", "benchmark": "NOT_APPLICABLE",
                 "risk_free": "NOT_APPLICABLE", "model": method}
    if kind == "CP5":
        valuation = manifest.get("valuation_manifest")
        vp, vc, vs, conventions = _required(valuation, "portfolio_id", "reporting_currency", "state_kind", "conventions")
        if (vp, vc, vs) != (portfolio, currency, state):
            raise _Invalid("INCONSISTENT_SOURCE_SIGNATURE")
        policy, confirmed = _required(manifest, "capital_policy", "capital_policy_confirmed")
        choice, origin, evidence = _required(policy, "choice", "origin", "evidence")
        _required(policy, "decision_id", "scope_kind", "product_id", "portfolio_id", "account_id")
        if (confirmed is not True or choice != "FULL_NAV" or not _text(evidence)
                or origin not in ("USER_CONFIRMED", "SYNTHETIC_CANDIDATE")
                or (origin == "SYNTHETIC_CANDIDATE" and manifest.get("synthetic") is not True)
                or not CapitalUniverseChoice(**policy).applies_to(portfolio, source["account_scope"])):
            raise _Invalid("CAPITAL_UNIVERSE_UNCONFIRMED")
        if "capital_policy_digest" in manifest and manifest["capital_policy_digest"] != digest(policy):
            raise _Invalid("INCONSISTENT_SOURCE_SIGNATURE")
        signature["capital_policy"] = policy
        signature["capital_policy_digest"] = digest(policy)
        signature["valuation_conventions"] = conventions
        if mid in EXPOSURE_IDS:
            metadata, md = _required(manifest, "metadata", "metadata_digest")
            if metadata is None or not _text(md) or digest(metadata) != md:
                raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
            taxonomy, = _required(metadata, "taxonomy")
            if not _text(taxonomy):
                raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
            signature.update(metadata_digest=md, taxonomy=taxonomy)
    else:
        if row.get("portfolio_state") != "ACTUAL" or source.get("state_kind") != "ACTUAL":
            raise _Invalid("INCONSISTENT_SOURCE_SIGNATURE")
        if source.get("as_of") != manifest.get("end"):
            raise _Invalid("INCONSISTENT_SOURCE_SIGNATURE")
        freq, rule, months, grid = _required(manifest, "frequency", "request_rule", "request_months", "boundary_rule_id")
        if freq not in ("DAILY", "WEEKLY", "MONTHLY") or not _text(grid):
            raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
        if row.get("frequency") != freq or row.get("requested_rule") != rule or row.get("requested_months") != months:
            raise _Invalid("INCONSISTENT_SOURCE_SIGNATURE")
        window = row.get("window")
        if not isinstance(window, dict) or window.get("grid_rule") != grid or window.get("frequency") != freq or window.get("rule") != rule:
            raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
        if window.get("requested_end") != manifest.get("end") or window.get("requested_base") != row.get("requested_base"):
            raise _Invalid("INCONSISTENT_SOURCE_SIGNATURE")
        if rule == "TRAILING_MONTHS":
            if type(months) is not int or months <= 0 or window.get("months") != months:
                raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
            duration = {"months": months}
        elif rule in ("CUSTOM", "YTD", "SINCE_INCEPTION", "MAX_AVAILABLE"):
            duration = {"requested_days": (_date(window["requested_end"]) - _date(window["requested_base"])).days}
        else:
            raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
        signature.update(frequency=freq, lookback_rule=rule, duration=duration, grid_rule=grid,
                         valuation_conventions=source["conventions"])
        if mid in BENCHMARK_IDS:
            bm = manifest.get("benchmark")
            bid, entry, treatment = _required(bm, "benchmark_id", "entry_digest", "currency_treatment")
            reference = row.get("benchmark")
            if not all(_text(v) for v in (bid, entry, treatment)) or not isinstance(reference, dict) or reference.get("benchmark_id") != bid or reference.get("currency_treatment") != treatment:
                raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
            signature["benchmark"] = {"benchmark_id": bid, "entry_digest": entry, "currency_treatment": treatment,
                                      "return_basis": reference.get("return_basis"), "currency": reference.get("currency")}
            if any(not _text(v) for v in signature["benchmark"].values()):
                raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
        if mid == "risk_max_drawdown":
            dd = row.get("drawdown")
            if not isinstance(dd, dict) or not _text(dd.get("peak_rule")):
                raise _Invalid("MISSING_COMPATIBILITY_SIGNATURE")
            signature["model"] = {"method_key": method, "peak_rule": dd["peak_rule"]}
    return Qualifier(mid, tuple(row.get("subject", ())), _unit(mid), currency, canonical_json(signature))


def _read(source):
    source = snapshot(source)
    obj = json.loads(source.content_json)
    manifest, rows = obj.get("manifest", {}), obj.get("metrics", ())
    kind = "CP5" if manifest.get("schema") == "finweb.diversification_manifest/1" else "CP4"
    error = None
    mid = digest(manifest)
    if source.digest != sha256_hex(source.content_json.encode("utf-8")) or obj.get("manifest_id") != mid:
        error = "SNAPSHOT_DIGEST_MISMATCH"
    answer = {"metrics": rows, "clusters": obj.get("clusters", ())} if kind == "CP5" else rows
    if kind == "CP5" and "exposure_decompositions" in obj:
        answer["exposure_decompositions"] = obj["exposure_decompositions"]
    if obj.get("result_digest") != digest(answer) or any(r.get("manifest_id") != mid for r in rows):
        error = "SNAPSHOT_DIGEST_MISMATCH"
    if manifest.get("schema") not in ("finweb.diversification_manifest/1", "finweb.risk_manifest/1"):
        error = "MISSING_COMPATIBILITY_SIGNATURE"
    entries = {}
    for row in rows:
        if row.get("metric_id") not in SUPPORTED:
            continue
        key = row["metric_id"], tuple(row.get("subject", ()))
        if key in entries:
            error = "DUPLICATE_SOURCE_METRIC"
        try:
            m = _metric(row, kind)
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            m = metric(key[0], key[1], state=INSUFFICIENT, details=("INVALID_EXACT_SOURCE", str(exc)))
        try:
            qualifier, problem = _qualifier(manifest, row, kind), None
        except (ValueError, TypeError, KeyError) as exc:
            qualifier, problem = None, str(exc)
        entries[key] = m, qualifier, problem
    try:
        as_of = _date(manifest["as_of"] if kind == "CP5" else manifest["end"])
    except (ValueError, TypeError, KeyError):
        as_of, error = None, "INVALID_SNAPSHOT_DATE"
    return source, manifest, entries, as_of, error


def qualifiers(source):
    """Return only signatures derivable from an intact pinned computation."""
    _, _, entries, _, error = _read(source)
    return () if error else tuple(q for _, q, _ in entries.values() if q is not None)


def _complete(manifest, entries, mid):
    rows = [m for (name, _), (m, _, _) in entries.items() if name == mid]
    complete = manifest.get("complete_exposure_maps", ())
    return (isinstance(complete, (list, tuple)) and mid in complete and bool(rows)
            and all(len(m.subject) == 1 and m.state is not INSUFFICIENT and m.exact is not None and m.exact >= 0 for m in rows)
            and sum((m.exact for m in rows), Fraction()) == 1)


def _at(manifest, entries, key):
    if key in entries:
        return entries[key]
    mid, subject = key
    if mid in EXPOSURE_IDS and len(subject) == 1 and _complete(manifest, entries, mid):
        siblings = [v for (name, _), v in entries.items() if name == mid]
        agg = combine([Part(str(i), m.state, None if m.result.reason_code is None else m.result.reason_code.value) for i, (m, _, _) in enumerate(siblings)])
        first_q = siblings[0][1]
        q = None if first_q is None else Qualifier(mid, subject, first_q.unit, first_q.reporting_currency, first_q.signature_json)
        return metric(mid, subject, exact=Fraction(), state=agg.state, reason=agg.reason, details=("COMPLETE_MAP_IMPLICIT_ZERO",)), q, None
    return metric(mid, subject, state=INSUFFICIENT, details=("MISSING_SOURCE_METRIC",)), None, "MISSING_COMPATIBILITY_SIGNATURE"


def _difference(mid, subject, left, right, lineage, extra=()):
    agg = combine([Part("current", left.state, None if left.result.reason_code is None else left.result.reason_code.value),
                   Part("reference", right.state, None if right.result.reason_code is None else right.result.reason_code.value)]
                  + ([Part("compatibility", INSUFFICIENT)] if extra else []))
    details = tuple(sorted(set(left.details + right.details + tuple(extra))))
    if agg.state is INSUFFICIENT:
        return metric(mid, subject, state=INSUFFICIENT, reason=agg.reason, details=details or ("SOURCE_INSUFFICIENT",), lineage=lineage)
    rational, radicals = _normal_terms(_terms(left) + tuple((-c, q) for c, q in _terms(right)))
    if not radicals:
        try:
            radical_sum(((rational, Fraction(1)),))
        except PresentationTie as tie:
            lineage = tuple(lineage) + _tie_lineage(tie)
        return metric(mid, subject, exact=rational, state=agg.state, reason=agg.reason, details=details, lineage=lineage)
    terms = radicals + (((rational, Fraction(1)),) if rational else ())
    try:
        return metric(mid, subject, terms=terms, presented=radical_sum(terms), state=agg.state, reason=agg.reason, details=details, lineage=lineage)
    except PresentationTie as tie:
        return metric(mid, subject, terms=terms, presented=tie.value, state=agg.state, reason=agg.reason,
                      details=details, lineage=tuple(lineage) + _tie_lineage(tie))


def compute_drift(current, baseline=None, targets=()):
    """Compare exact ACTUAL sources. Missing references are explicit refusals."""
    cur, cm, current_entries, current_date, current_error = _read(current)
    targets = tuple(sorted(targets, key=lambda t: (t.target_id, t.digest)))
    if len({t.target_id for t in targets}) != len(targets):
        raise ValueError("duplicate target identity")
    before = None if baseline is None else _read(baseline.snapshot)
    bm, baseline_entries = ({}, {}) if before is None else (before[1], before[2])
    keys = set(current_entries)
    keys.update(k for k in baseline_entries if k[0] in EXPOSURE_IDS)
    out = []
    for key in sorted(keys):
        left, cq, ce = _at(cm, current_entries, key)
        right, bq, be = _at(bm, baseline_entries, key)
        problems = []
        if current_error:
            problems.append(current_error)
        if baseline is None:
            problems.append("NO_BASELINE")
        elif baseline.accepted is not True or not _text(baseline.acceptance_reference):
            problems.append("BASELINE_NOT_ACCEPTED")
        else:
            if not _text(baseline.baseline_id) or before[4] or current_date is None or before[3] is None or before[3] >= current_date:
                problems.append("INCOMPATIBLE_BASELINE")
                if before[4]:
                    problems.append(before[4])
            if cq is None or bq is None or cq != bq:
                problems.append("INCOMPATIBLE_BASELINE")
            if key[0] in EXPOSURE_IDS and (not _complete(cm, current_entries, key[0]) or not _complete(bm, baseline_entries, key[0])):
                problems.append("INCOMPLETE_EXPOSURE_MAP")
        line = [("source_metric", key[0]), ("current_snapshot_digest", cur.digest), ("judgment_class", "FACT"), ("reference", "PORTFOLIO_HISTORY"),
                ("unit", _unit(key[0])), ("interpretation", "Signed difference; no causal, severity or rebalancing claim")]
        if baseline is not None:
            line += [("baseline_id", baseline.baseline_id), ("baseline_digest", baseline.digest), ("baseline_snapshot_digest", baseline.snapshot.digest)]
        if cq is not None:
            line.append(("compatibility_signature", canonical_json(cq.to_obj())))
        line.append(("synthetic", str(cm.get("synthetic") is True or bm.get("synthetic") is True)))
        if left.observation_count != right.observation_count and baseline is not None:
            line.append(("window_disclosure", "Effective observation counts differ at the grid endpoints; requested duration and rule must match"))
        current_vintage = cm.get("valuation_manifest", cm.get("series_manifest", {})).get("release_id")
        previous_vintage = bm.get("valuation_manifest", bm.get("series_manifest", {})).get("release_id")
        if baseline is not None and current_vintage != previous_vintage:
            line.append(("vintage_disclosure", "Different market-data vintages; possible restatement effects"))
        if key[0] == "risk_max_drawdown":
            line.append(("drawdown_definition", "Signed within-window maximum decline; not all-time peak or current underwater state"))
        if _unit(key[0]) == "FRACTION":
            line.append(("display_interpretation", "Fraction-unit difference; percentage-point change when displayed as percent"))
        out.append(_difference("drift_absolute", (key[0],) + key[1], left, right, tuple(line), problems))
    target_keys = {(t.qualifier.metric_id, t.qualifier.subject) for t in targets}
    for key in sorted(set(current_entries) - target_keys):
        left, _, _ = current_entries[key]
        out.append(_difference("drift_target_gap", (key[0],) + key[1], left, metric(key[0], state=INSUFFICIENT, details=("NO_USER_TARGET",)),
                               (("current_snapshot_digest", cur.digest), ("reference", "USER_POLICY")), ("NO_USER_TARGET",)))
    for target in targets:
        key = target.qualifier.metric_id, target.qualifier.subject
        left, cq, _ = _at(cm, current_entries, key)
        problems = []
        if target.provenance != "EXPLICIT_USER" or not _text(target.evidence):
            problems.append("TARGET_NOT_USER_DEFINED")
        if (current_error or not _text(target.target_id) or cq is None or cq != target.qualifier
                or type(target.effective_date) is not datetime.date or current_date is None or target.effective_date > current_date
                or not isinstance(target.exact, Fraction)):
            problems.append("INCOMPATIBLE_TARGET")
        right = (metric(key[0], key[1], exact=target.exact) if isinstance(target.exact, Fraction) else
                 metric(key[0], key[1], state=INSUFFICIENT, details=("INVALID_EXACT_TARGET",)))
        line = (("current_snapshot_digest", cur.digest), ("target_id", target.target_id), ("target_digest", target.digest), ("reference", "USER_POLICY"),
                ("judgment_class", "FACT"), ("unit", target.qualifier.unit), ("interpretation", "Signed gap; no default threshold or policy breach"))
        out.append(_difference("drift_target_gap", (key[0],) + key[1] + (target.target_id,), left, right, line, problems))
    return tuple(sorted(out, key=lambda m: (m.metric_id, m.subject)))


def compute_drift_result(current, baseline=None, targets=()):
    """Seal the comparison and its immutable sources for direct reproduction."""
    current, targets = snapshot(current), tuple(sorted(targets, key=lambda t: (t.target_id, t.digest)))
    synthetic = json.loads(current.content_json)["manifest"].get("synthetic") is True
    if baseline is not None:
        synthetic |= json.loads(baseline.snapshot.content_json)["manifest"].get("synthetic") is True
    manifest = {"schema": "finweb.drift_manifest/1", "engine_id": "diversification-drift/1.0", "state_kind": "ACTUAL",
                "synthetic": synthetic, "current": current.to_obj(), "baseline": None if baseline is None else baseline.to_obj(), "targets": [t.to_obj() for t in targets]}
    return seal(manifest, compute_drift(current, baseline, targets))


@dataclass(frozen=True)
class Reproduction:
    status: str
    result: Result


def reproduce_drift(saved, expected_digest=None):
    """Recompute the comparison from its pinned exact sources, with no I/O."""
    manifest = json.loads(saved.manifest_json if isinstance(saved, Result) else saved)
    if manifest.get("schema") != "finweb.drift_manifest/1":
        raise ValueError("not a drift manifest")
    def restore(value):
        return Snapshot(canonical_json(value["content"]), value["digest"])
    old_baseline = manifest["baseline"]
    baseline = None if old_baseline is None else Baseline(old_baseline["baseline_id"], restore(old_baseline["snapshot"]),
                                                       old_baseline["accepted"], old_baseline["acceptance_reference"])
    targets = []
    for row in manifest["targets"]:
        q = row["qualifier"]
        qualifier = Qualifier(q["metric_id"], tuple(q["subject"]), q["unit"], q["reporting_currency"], canonical_json(q["signature"]))
        exact = Fraction(row["exact"]) if isinstance(row["exact"], str) and "/" in row["exact"] else row["exact"]
        targets.append(Target(row["target_id"], qualifier, exact,
                              _date(row["effective_date"]), row["provenance"], row["evidence"]))
    rerun = compute_drift_result(restore(manifest["current"]), baseline, targets)
    if json.loads(rerun.manifest_json) != manifest:
        return Reproduction("MANIFEST_DIFFERS", rerun)
    if expected_digest is None:
        return Reproduction("RESULT_NOT_COMPARED", rerun)
    return Reproduction("REPRODUCED" if rerun.result_digest == expected_digest else "RESULT_DIFFERS", rerun)
