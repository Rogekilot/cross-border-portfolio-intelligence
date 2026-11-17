"""Immutable, auditable inputs and results for diversification/1.2 (the methods are those of 1.0; 1.1 and 1.2 re-issue the registry's labels).

Classification is explicit input: a trading venue never implies issuer country or
sector. Every numerical result composes the product MetricResult envelope.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, replace
from decimal import Decimal
from fractions import Fraction
from typing import Optional, Tuple

from marketdata.canonical import canonical_json, sha256_hex
from performance.numerics import apportion, round_half_up, to_decimal_exact
from product_contract.metric_state import MetricResult
from product_contract.vocabulary import ReasonCode, SufficiencyState
from risk.sqrt import sqrt_rounded

AVAILABLE = SufficiencyState.AVAILABLE
LIMITED = SufficiencyState.LIMITED
INSUFFICIENT = SufficiencyState.INSUFFICIENT_DATA
PRODUCT_ID = "cross-border-portfolio-intelligence"
#: What a result cites as `method_key` is `<registry_id>#<metric_id>` (drift refuses any other form, `drift._qualifier`). The id is the bundled
#: registry's own; a test asserts this prefix equals it, so the two cannot drift apart. diversification/1.1 and 1.2 are label re-issues of 1.0 (CP5 change notes 1.1 and 1.2).
METHOD_KEY_PREFIX = "diversification/1.2#"


def digest(value):
    return sha256_hex(canonical_json(value).encode("utf-8"))


@dataclass(frozen=True)
class Classification:
    listing_id: str
    country: Optional[str] = None
    sector: Optional[str] = None
    asset_class: Optional[str] = None

    def to_obj(self):
        return {"listing_id": self.listing_id, "country": self.country, "sector": self.sector, "asset_class": self.asset_class}


@dataclass(frozen=True)
class MetadataSnapshot:
    version: str
    source: str
    taxonomy: str
    as_of: datetime.date
    rows: Tuple[Classification, ...] = ()
    synthetic: bool = False

    def __post_init__(self):
        if not all(isinstance(s, str) and s.strip() for s in (self.version, self.source, self.taxonomy)):
            raise ValueError("classification metadata needs version, source and taxonomy")
        if len({r.listing_id for r in self.rows}) != len(self.rows):
            raise ValueError("duplicate classification listing")
        object.__setattr__(self, "rows", tuple(sorted(self.rows, key=lambda r: r.listing_id)))

    def to_obj(self):
        return {"version": self.version, "source": self.source, "taxonomy": self.taxonomy, "as_of": self.as_of, "rows": [r.to_obj() for r in self.rows], "synthetic": self.synthetic}

    @property
    def digest(self):
        return digest(self.to_obj())


@dataclass(frozen=True)
class Bucket:
    key: str
    kind: str
    currency: str
    value: Optional[Fraction]
    state: SufficiencyState = AVAILABLE
    reason: Optional[str] = None
    details: Tuple[str, ...] = ()

    def __post_init__(self):
        if self.kind not in ("SECURITY", "CASH", "RECEIVABLE"):
            raise ValueError("unknown capital bucket kind")
        if (self.value is None) != (self.state is INSUFFICIENT):
            raise ValueError("a missing bucket value must be insufficient")
        if self.value is not None and not isinstance(self.value, Fraction):
            raise TypeError("bucket values must be exact Fractions")

    def to_obj(self):
        return {"key": self.key, "kind": self.kind, "currency": self.currency, "value": self.value, "state": self.state.value, "reason": self.reason, "details": list(self.details)}


@dataclass(frozen=True)
class Observation:
    start: datetime.date
    end: datetime.date
    value: Optional[Fraction]
    state: SufficiencyState = AVAILABLE
    reason: Optional[str] = None
    details: Tuple[str, ...] = ()

    def __post_init__(self):
        if self.start >= self.end or (self.value is None) != (self.state is INSUFFICIENT):
            raise ValueError("invalid period observation")
        if self.value is not None and not isinstance(self.value, Fraction):
            raise TypeError("observations must be exact Fractions")

    def to_obj(self):
        return {"start": self.start, "end": self.end, "value": self.value, "state": self.state.value, "reason": self.reason, "details": list(self.details)}


@dataclass(frozen=True)
class History:
    key: str
    observations: Tuple[Observation, ...]
    lineage: Tuple[Tuple[str, str], ...] = ()

    def to_obj(self):
        return {"key": self.key, "observations": [o.to_obj() for o in self.observations], "lineage": [list(p) for p in self.lineage]}


@dataclass(frozen=True)
class TotalReturnCoverage:
    """Explicit auditable assertion of action coverage, never inferred from no rows."""
    listing_id: str
    source: str
    version: str
    evidence: str
    start: datetime.date
    end: datetime.date
    as_of: datetime.date
    confirmed: bool
    return_basis: str = "TOTAL_RETURN_GROSS"
    synthetic: bool = False

    def __post_init__(self):
        if not all(isinstance(v, str) and v.strip() for v in (self.listing_id, self.source, self.version, self.evidence)):
            raise ValueError("coverage needs listing, source, version and evidence")
        if self.start > self.end or type(self.confirmed) is not bool:
            raise ValueError("invalid coverage interval or confirmation")

    def to_obj(self):
        return {"listing_id": self.listing_id, "source": self.source, "version": self.version, "evidence": self.evidence,
                "start": self.start, "end": self.end, "as_of": self.as_of, "confirmed": self.confirmed, "return_basis": self.return_basis, "synthetic": self.synthetic}


@dataclass(frozen=True)
class CapitalUniverseChoice:
    """The owner-reserved denominator decision, supplied rather than inferred."""
    choice: str
    origin: str
    evidence: str
    decision_id: Optional[str] = None
    scope_kind: Optional[str] = None
    product_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    account_id: Optional[str] = None

    def to_obj(self):
        return {"choice": self.choice, "origin": self.origin, "evidence": self.evidence, "decision_id": self.decision_id,
                "scope_kind": self.scope_kind, "product_id": self.product_id, "portfolio_id": self.portfolio_id, "account_id": self.account_id}

    def applies_to(self, portfolio_id, account_scope):
        """Explicit request binding. Missing scope never means global approval."""
        if not all(isinstance(value, str) and value.strip() for value in (self.decision_id, self.evidence)):
            return False
        if self.scope_kind == "GLOBAL_PRODUCT":
            return self.product_id == PRODUCT_ID and self.portfolio_id is None and self.account_id is None
        if self.product_id is not None or portfolio_id is None or self.portfolio_id != str(portfolio_id):
            return False
        if self.scope_kind == "PORTFOLIO":
            return account_scope is None and self.account_id is None
        if self.scope_kind == "ACCOUNT":
            return account_scope is not None and self.account_id == str(account_scope)
        return False

    @property
    def digest(self):
        return digest(self.to_obj())


@dataclass(frozen=True)
class Metric:
    metric_id: str
    subject: Tuple[str, ...]
    result: MetricResult
    exact: Optional[Fraction] = None
    exact_square: Optional[Fraction] = None
    sign: Optional[int] = None
    details: Tuple[str, ...] = ()
    observation_count: Optional[int] = None
    thresholds: Optional[Tuple[int, int]] = None
    lineage: Tuple[Tuple[str, str], ...] = ()
    radical_terms: Tuple[Tuple[Fraction, Fraction], ...] = ()
    manifest_id: Optional[str] = None

    def __post_init__(self):
        if self.result.value is None and (self.exact is not None or self.exact_square is not None or self.radical_terms or self.sign is not None):
            raise ValueError("suppressed metric cannot carry a numeric result")
        if self.result.value is None and not self.details:
            raise ValueError("suppressed metric must explain why")

    @property
    def state(self):
        return self.result.sufficiency_state

    def to_obj(self):
        return {"metric_id": self.metric_id, "subject": list(self.subject), "value": self.result.value, "state": self.state.value,
                "reason": None if self.result.reason_code is None else self.result.reason_code.value, "exact": self.exact,
                "exact_square": self.exact_square, "sign": self.sign, "details": list(self.details), "observation_count": self.observation_count,
                "thresholds": self.thresholds, "lineage": [list(p) for p in self.lineage], "radical_terms": [list(t) for t in self.radical_terms],
                "method_key": METHOD_KEY_PREFIX + self.metric_id, "manifest_id": self.manifest_id}


def metric(metric_id, subject=(), *, exact=None, square=None, sign=1, state=AVAILABLE, reason=None, details=(), n=None, thresholds=None, lineage=(), terms=(), presented=None):
    if state is INSUFFICIENT:
        exact, square, sign, terms, value = None, None, None, (), None
        lineage = ()  # no computed intermediate may become an alternate answer
    elif presented is not None:
        value = presented
    elif square is not None:
        root = sqrt_rounded(square, sign)
        sign = root.sign
        value = to_decimal_exact(root.value)
    else:
        value = to_decimal_exact(round_half_up(exact, 12))
        sign = None
    return Metric(metric_id, tuple(subject), MetricResult(value, state, None if reason is None else ReasonCode(reason)), exact, square, sign,
                  tuple(sorted(set(details))), n, thresholds, tuple(sorted(lineage)), tuple(terms))


@dataclass(frozen=True)
class ExposurePart:
    category: str
    exact: Fraction
    scalar: Decimal
    apportioned: Decimal

    def to_obj(self):
        return {"category": self.category, "exact": self.exact, "scalar": self.scalar, "apportioned": self.apportioned}


@dataclass(frozen=True)
class ExposureDecomposition:
    metric_id: str
    exact_total: Fraction
    displayed_total: Decimal
    state: str
    parts: Tuple[ExposurePart, ...]
    method_id: str = "performance/1.12#2.4"

    def to_obj(self):
        return {"metric_id": self.metric_id, "exact_total": self.exact_total, "displayed_total": self.displayed_total, "state": self.state,
                "method_id": self.method_id, "parts": [p.to_obj() for p in self.parts]}


def exposure_decompositions(metrics, complete_maps):
    """Separate display partitions; exact metrics and individual scalars are untouched."""
    out = []
    for metric_id in sorted(complete_maps):
        rows = sorted((m for m in metrics if m.metric_id == metric_id), key=lambda m: m.subject)
        if (not rows or any(m.state is INSUFFICIENT or m.exact is None or len(m.subject) != 1 for m in rows)
                or sum((m.exact for m in rows), Fraction()) != 1):
            continue
        shown = apportion(Fraction(1), tuple(m.exact for m in rows), 12)
        parts = tuple(ExposurePart(m.subject[0], m.exact, m.result.value, to_decimal_exact(value)) for m, value in zip(rows, shown))
        out.append(ExposureDecomposition(metric_id, Fraction(1), Decimal(1), "LIMITED" if any(m.state is LIMITED for m in rows) else "AVAILABLE", parts))
    return tuple(out)


@dataclass(frozen=True)
class Result:
    manifest_json: str
    metrics: Tuple[Metric, ...]
    clusters: Tuple[Tuple[str, ...], ...] = ()
    exposure_decompositions: Tuple[ExposureDecomposition, ...] = ()

    @property
    def manifest_id(self):
        return sha256_hex(self.manifest_json.encode("utf-8"))

    @property
    def result_digest(self):
        return digest({"metrics": [m.to_obj() for m in self.metrics], "clusters": self.clusters,
                       "exposure_decompositions": [p.to_obj() for p in self.exposure_decompositions]})

    def metric(self, metric_id, subject=()):
        (found,) = [m for m in self.metrics if m.metric_id == metric_id and m.subject == tuple(subject)]
        return found

    def canonical_json(self):
        import json
        return canonical_json({"manifest": json.loads(self.manifest_json), "manifest_id": self.manifest_id, "result_digest": self.result_digest,
                               "metrics": [m.to_obj() for m in self.metrics], "clusters": self.clusters,
                               "exposure_decompositions": [p.to_obj() for p in self.exposure_decompositions]})


def seal(manifest, metrics, clusters=()):
    text = canonical_json(manifest)
    mid = sha256_hex(text.encode("utf-8"))
    stamped = tuple(replace(m, manifest_id=mid) for m in sorted(metrics, key=lambda m: (m.metric_id, m.subject)))
    return Result(text, stamped, tuple(clusters), exposure_decompositions(stamped, manifest.get("complete_exposure_maps", ())))
