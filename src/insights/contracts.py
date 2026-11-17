"""Immutable questions, evidence references and machine-readable Proof Packets."""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Optional, Tuple

from marketdata.canonical import canonical_json, sha256_hex


def digest(value):
    return sha256_hex(canonical_json(value).encode("utf-8"))


@dataclass(frozen=True, order=True)
class MetricRef:
    source_id: str
    metric_id: str
    subject: Tuple[str, ...] = ()

    def __post_init__(self):
        if (not isinstance(self.source_id, str) or not self.source_id.strip() or not isinstance(self.metric_id, str) or not self.metric_id.strip()
                or not isinstance(self.subject, tuple) or not all(isinstance(v, str) for v in self.subject)):
            raise ValueError("metric reference needs a source, metric and immutable string subject")

    def to_obj(self):
        return {"source_id": self.source_id, "metric_id": self.metric_id, "subject": list(self.subject)}


@dataclass(frozen=True)
class HistoryComparison:
    current: MetricRef
    baseline: MetricRef

    def to_obj(self):
        return {"current": self.current.to_obj(), "baseline": self.baseline.to_obj()}


@dataclass(frozen=True)
class UserLimit:
    """A recorded personal constraint, never the product's capital denominator."""
    policy_id: str
    version: str
    evidence: str
    portfolio_id: str
    scope_kind: str
    source_kind: str
    metric_id: str
    semantic_key: str
    direction: str
    limit: Fraction
    effective_from: dt.date
    account_id: Optional[str] = None
    effective_until: Optional[dt.date] = None
    subject: Tuple[str, ...] = ()
    origin: str = "USER_CONFIRMED"

    def __post_init__(self):
        for name in ("policy_id", "version", "evidence", "portfolio_id", "semantic_key", "metric_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError("user policy needs " + name)
        if self.origin != "USER_CONFIRMED" or self.scope_kind not in ("PORTFOLIO", "ACCOUNT"):
            raise ValueError("personal limits require explicit user provenance and scope")
        if (self.scope_kind == "ACCOUNT") != (isinstance(self.account_id, str) and bool(self.account_id.strip())):
            raise ValueError("only an ACCOUNT policy names an account")
        if self.source_kind not in ("CP4", "CP5") or self.direction not in ("MAXIMUM", "MINIMUM"):
            raise ValueError("invalid source kind or limit direction")
        if not isinstance(self.limit, Fraction):
            raise TypeError("user limits must be exact Fractions")
        if type(self.effective_from) is not dt.date or (self.effective_until is not None and type(self.effective_until) is not dt.date):
            raise TypeError("policy validity uses explicit calendar dates")
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise ValueError("policy validity is reversed")
        if not isinstance(self.subject, tuple) or not all(isinstance(v, str) for v in self.subject):
            raise TypeError("policy subject must be an immutable tuple")

    def to_obj(self):
        return {name: (list(value) if name == "subject" else value) for name, value in self.__dict__.items()}

    @property
    def policy_digest(self):
        return digest(self.to_obj())


@dataclass(frozen=True)
class SourceEvidence:
    """Internal adapter output: immutable canonical upstream result and metadata."""
    source_id: str
    source_kind: str
    payload_json: str
    context_json: str

    def payload(self):
        return json.loads(self.payload_json)

    def context(self):
        return json.loads(self.context_json)

    def to_obj(self):
        return {"source_id": self.source_id, "source_kind": self.source_kind, "payload": self.payload(), "context": self.context()}


@dataclass(frozen=True)
class ProofPacket:
    packet_json: str

    def to_obj(self):
        return json.loads(self.packet_json)

    @property
    def insight_id(self):
        return self.to_obj()["insight_id"]


@dataclass(frozen=True)
class InsightResult:
    manifest_json: str
    packets: Tuple[ProofPacket, ...]
    diagnostics_json: str

    @property
    def manifest_id(self):
        return sha256_hex(self.manifest_json.encode("utf-8"))

    @property
    def result_digest(self):
        return digest({"packets": [p.to_obj() for p in self.packets], "diagnostics": json.loads(self.diagnostics_json)})

    def to_obj(self):
        return {"manifest_id": self.manifest_id, "manifest": json.loads(self.manifest_json), "result_digest": self.result_digest,
                "packets": [p.to_obj() for p in self.packets], "diagnostics": json.loads(self.diagnostics_json)}

    def canonical_json(self):
        return canonical_json(self.to_obj())


@dataclass(frozen=True)
class InsightRefusal:
    code: str
    detail: str
    source_id: Optional[str] = None
    state: str = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class Reproduction:
    status: str
    detail: str = ""
    result: Optional[InsightResult] = None
