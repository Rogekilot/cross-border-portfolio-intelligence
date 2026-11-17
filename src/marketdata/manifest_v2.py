"""Additive canonical metadata v2; old FileManifest and readers stay unchanged."""
from __future__ import annotations

import re
from dataclasses import dataclass

from domain.currency import CurrencyCode
from marketdata.acquisition import (
    AcquisitionCode, AcquisitionEnvelope, EnvelopeIndex, IntegrityBoundAcquisition, PUBLIC_PARAMETER_KEYS,
    TrustedAcquisitionWitness, digest, exact_object, identifier, integer,
    parse_canonical_metadata, public_pairs, refuse, sha256_bytes, utc_instant,
)
from marketdata.contracts import AdjustmentStatus, DataDelayStatus, UsageScope
from marketdata.manifest import DataKind, FileManifest, MANIFEST_SCHEMA, ManifestError

MANIFEST_V2_SCHEMA = "finweb.marketdata.file_manifest/2"
ACQUISITION_REF_SCHEMA = "finweb.marketdata.acquisition_ref/1"
V1_KEYS = frozenset(("schema", "file_sha256", "size_bytes", "payload_filename", "payload_format", "source_id",
    "data_kind", "market", "retrieval_time", "retrieved_by", "request", "declared_adjustment", "adjustment_anchor",
    "declared_currency", "declared_delay", "source_identifiers", "script", "libraries", "usage_scope", "coverage"))


#: The request keys the v1 download tool (`marketdata_tools.download`, every `Fetched(request=...)` and the hand-made `register-file`) actually writes, and
#: that the registry's v1 read therefore accepts. Reviewed list, not a pattern; `acquisition.PUBLIC_PARAMETER_KEYS`, which guards the v2 acquisition path,
#: is NOT widened. A key outside this list (an `apikey`, a `token`, anything new) is refused.
V1_REQUEST_KEYS = frozenset((
    "function", "symbol", "start", "end", "adjust", "row_filter", "adjustflag",          # akshare, akshare_sina, baostock
    "outputsize",                                                                         # alphavantage
    "base", "symbols", "endpoint", "file", "read_start", "read_end",                      # frankfurter, ecb
    "idType", "idValue", "exchCode", "marketSecDes", "micCode",                           # openfigi
    "origin"))                                                                            # register-file
_SECRET_SHAPED = re.compile(r"(?i)api[-_ ]?key|access[-_ ]?key|private[-_ ]?key|token|secret|passw|credential|bearer|authorization|auth[-_ ]?key"
                            r"|[?&#;]\w*=|\w*key\w*\s*=|://[^/\s?#]*@")
_V1_TEXT = re.compile(r"[\x20-\x7e]{1,256}\Z")


def _v1_request_pairs(value):
    """The registry's v1 request check: reviewed keys (`V1_REQUEST_KEYS`, plus the public keys the strict reader already accepted), no repeats, printable text values, nothing secret-shaped (no key-like word, no query string)."""
    if type(value) is not list or len(value) > 32:
        refuse()
    seen = set()
    for pair in value:
        if type(pair) is not list or len(pair) != 2:
            refuse()
        key, val = pair
        if type(key) is not str or not (key in V1_REQUEST_KEYS or key in PUBLIC_PARAMETER_KEYS) or key in seen:
            refuse()
        seen.add(key)
        if type(val) is not str or _V1_TEXT.fullmatch(val) is None or _SECRET_SHAPED.search(val) is not None:
            refuse()


def _v1_anchor(value):
    """The v1 tool writes a free-text label as the anchor ("TIME_SERIES_DAILY as returned; label unverified", "<call> adjust=qfq"), or null."""
    if value is not None and (type(value) is not str or _V1_TEXT.fullmatch(value) is None or _SECRET_SHAPED.search(value) is not None):
        refuse()


def _pairs(value):
    if type(value) is not list or len(value) > 32:
        refuse()
    keys = set()
    for pair in value:
        if type(pair) is not list or len(pair) != 2:
            refuse()
        for item in pair:
            identifier(item)
        if pair[0] in keys:
            refuse()
        keys.add(pair[0])


def _manifest_shape(obj, version, registry_v1=False):
    exact_object(obj, V1_KEYS | ({"acquisition"} if version == 2 else set()))
    schema = MANIFEST_V2_SCHEMA if version == 2 else MANIFEST_SCHEMA
    if obj["schema"] != schema:
        refuse(AcquisitionCode.SCHEMA_UNSUPPORTED)
    digest(obj["file_sha256"])
    integer(obj["size_bytes"])
    identifier(obj["payload_filename"])
    if obj["payload_filename"] in (".", ".."):
        refuse()
    for name in ("payload_format",):
        if type(obj[name]) is not str or re.fullmatch(r"[A-Za-z0-9_.-]+/[1-9][0-9]*", obj[name]) is None:
            refuse()
    identifier(obj["source_id"])
    try:
        DataKind(obj["data_kind"])
        AdjustmentStatus(obj["declared_adjustment"])
        DataDelayStatus(obj["declared_delay"])
        UsageScope(obj["usage_scope"])
        if obj["declared_currency"] is not None:
            CurrencyCode(obj["declared_currency"])
    except (ValueError, TypeError):
        refuse()
    if obj["market"] is not None:
        identifier(obj["market"])
    if registry_v1:
        _v1_anchor(obj["adjustment_anchor"])
    elif obj["adjustment_anchor"] is not None:
        identifier(obj["adjustment_anchor"])
    utc_instant(obj["retrieval_time"])
    if registry_v1:
        _v1_request_pairs(obj["request"])
    else:
        public_pairs(obj["request"])
    identifiers = obj["source_identifiers"]
    if type(identifiers) is not list or len(identifiers) > 32:
        refuse()
    for value in identifiers:
        identifier(value)
    if len(set(identifiers)) != len(identifiers):
        refuse()
    exact_object(obj["script"], ("name", "version", "script_sha256"))
    for key in ("name", "version"):
        if obj["script"][key] is not None:
            identifier(obj["script"][key])
    if obj["script"]["script_sha256"] is not None:
        digest(obj["script"]["script_sha256"])
    _pairs(obj["libraries"])
    _pairs(obj["coverage"])
    if version == 2:
        if obj["retrieved_by"] != "agent" or obj["usage_scope"] != "INTERNAL_DEVELOPMENT_ONLY":
            refuse()
        if any(obj["script"][key] is None for key in ("name", "version", "script_sha256")):
            refuse()
        exact_object(obj["acquisition"], ("schema", "envelope_sha256"))
        if obj["acquisition"]["schema"] != ACQUISITION_REF_SCHEMA:
            refuse(AcquisitionCode.SCHEMA_UNSUPPORTED)
        digest(obj["acquisition"]["envelope_sha256"])
    elif obj["retrieved_by"] not in ("human", "synthetic"):
        refuse()


@dataclass(frozen=True)
class FileManifestV2:
    content: bytes

    def __post_init__(self):
        _manifest_shape(parse_canonical_metadata(self.content), 2)

    @classmethod
    def from_bytes(cls, payload: bytes):
        return cls(payload)

    def to_bytes(self):
        return self.content

    def to_obj(self):
        return parse_canonical_metadata(self.content)

    @property
    def sha256(self):
        return sha256_bytes(self.content)


def read_manifest_metadata(payload: bytes):
    """Explicit new opt-in gate; intentionally stricter than the old v1 reader.

No claim that every byte string accepted by legacy from_json is accepted here.
No filesystem discovery, v2-to-v1 conversion, adapter installation or admission.
"""
    obj = parse_canonical_metadata(payload)
    schema = obj.get("schema")
    if schema == MANIFEST_V2_SCHEMA:
        return FileManifestV2.from_bytes(payload)
    if schema == MANIFEST_SCHEMA:
        _manifest_shape(obj, 1)
        try:
            return FileManifest.from_json(payload.decode("utf-8"))
        except (ManifestError, ValueError, TypeError):
            refuse()
    refuse(AcquisitionCode.SCHEMA_UNSUPPORTED)


def read_registry_manifest_metadata(payload: bytes):
    """The candidate registry's manifest reader. A v2 manifest is read exactly as `read_manifest_metadata` reads it. A v1 manifest is the one the v1 download
    tool wrote, whose bytes the owner confirmed by digest (PD-0066 decision 9) and which must not change: its request keys are the reviewed
    `V1_REQUEST_KEYS` and its anchor is free text, still refusing anything secret-shaped. Nothing else is relaxed."""
    obj = parse_canonical_metadata(payload)
    if obj.get("schema") == MANIFEST_SCHEMA:
        _manifest_shape(obj, 1, registry_v1=True)
        try:
            return FileManifest.from_json(payload.decode("utf-8"))
        except (ManifestError, ValueError, TypeError):
            refuse()
    return read_manifest_metadata(payload)


def verify_acquisition_binding(manifest: FileManifestV2, envelopes: EnvelopeIndex,
                               witness: TrustedAcquisitionWitness) -> IntegrityBoundAcquisition:
    """Compare independently supplied expectations; no rights or promotion result."""
    if type(witness) is not TrustedAcquisitionWitness:
        refuse(AcquisitionCode.AUTHORITY_MISSING)
    if type(manifest) is not FileManifestV2 or type(envelopes) is not EnvelopeIndex:
        refuse()
    m = manifest.to_obj()
    envelope = envelopes.resolve(m["acquisition"]["envelope_sha256"])
    e = envelope.to_obj()
    if (e["actor"]["agent_id"], e["actor"]["role"]) != (witness.actor_agent_id, witness.actor_role):
        refuse(AcquisitionCode.ACTOR_UNVERIFIED)
    if (manifest.sha256 != witness.expected_manifest_sha256
            or envelope.sha256 != witness.expected_envelope_sha256
            or e["request"]["sha256"] != witness.approved_full_request_sha256):
        refuse(AcquisitionCode.BINDING_DIFFERS)
    if (m["file_sha256"] != e["result"]["payload_sha256"] or m["size_bytes"] != e["result"]["size_bytes"]
            or m["retrieval_time"] != e["result"]["retrieved_at"] or m["source_id"] != e["request"]["source_id"]
            or m["request"] != e["request"]["parameters"]
            or m["script"] != {"name": e["tool"]["name"], "version": e["tool"]["version"], "script_sha256": e["tool"]["sha256"]}):
        refuse(AcquisitionCode.BINDING_DIFFERS)
    return IntegrityBoundAcquisition(manifest.sha256, envelope.sha256)
