"""Opt-in acquisition metadata only; no I/O, admission or identity attestation.

Canonical bytes and independently supplied trusted-operator expectations are
integrity records. They cannot prove an actor or grant current rights. Existing
v1 readers and all real data paths remain untouched.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

ENVELOPE_SCHEMA = "finweb.marketdata.acquisition_envelope/1"
MAX_METADATA_BYTES = 65536
MAX_DEPTH = 8
MAX_TOKEN_BYTES = 4096
MAX_PRIMITIVES = 4096
MAX_PAIRS = 32
MAX_INDEX_ENTRIES = 16
PUBLIC_PARAMETER_KEYS = frozenset(("from", "to", "fmt", "symbol", "exchange", "function"))
EVIDENCE_ROLES = ("APPROVAL_PACKET", "REQUEST_SPEC", "EXECUTION_METADATA", "EXECUTION_REVIEW")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_AGENT = re.compile(r"/root(?:/[a-z0-9_]+)*\Z")
_DECISION = re.compile(r"decisions/product/PD-[0-9]{4}-[a-z0-9-]+\.md\Z")


class AcquisitionCode(Enum):
    SCHEMA_UNSUPPORTED = "ACQUISITION_SCHEMA_UNSUPPORTED"
    SHAPE_INVALID = "ACQUISITION_SHAPE_INVALID"
    ACTOR_UNVERIFIED = "ACQUISITION_ACTOR_UNVERIFIED"
    BINDING_DIFFERS = "ACQUISITION_BINDING_DIFFERS"
    AUTHORITY_MISSING = "ACQUISITION_AUTHORITY_MISSING"
    INPUT_UNAVAILABLE = "ACQUISITION_INPUT_UNAVAILABLE"
    STORAGE_CONFLICT = "ACQUISITION_STORAGE_CONFLICT"


class AcquisitionError(ValueError):
    def __init__(self, code: AcquisitionCode):
        self.code = code
        super().__init__(code.value)  # Never echo values, paths or credential-like input.


def refuse(code=AcquisitionCode.SHAPE_INVALID):
    raise AcquisitionError(code)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def exact_object(obj, keys):
    if type(obj) is not dict or set(obj) != set(keys):
        refuse()


def text(value, limit=128):
    if type(value) is not str or not value or len(value.encode("utf-8")) > limit:
        refuse()
    return value


def identifier(value):
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        refuse()
    return value


def digest(value):
    if type(value) is not str or _SHA.fullmatch(value) is None:
        refuse()
    return value


def integer(value, minimum=0, maximum=9223372036854775807):
    if type(value) is not int or not minimum <= value <= maximum:
        refuse()
    return value


def utc_instant(value):
    if type(value) is not str or _UTC.fullmatch(value) is None:
        refuse()
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        refuse()


def public_pairs(value):
    if type(value) is not list or len(value) > MAX_PAIRS:
        refuse()
    seen = set()
    for pair in value:
        if type(pair) is not list or len(pair) != 2:
            refuse()
        key, val = pair
        if type(key) is not str or key not in PUBLIC_PARAMETER_KEYS or key in seen:
            refuse()
        seen.add(key)
        if type(val) is not str or not val or len(val) > 128 or re.fullmatch(r"[A-Za-z0-9_.:+-]+", val) is None:
            refuse()


def _string(value):
    if len(value.encode("utf-8", "strict")) > MAX_TOKEN_BYTES or not unicodedata.is_normalized("NFC", value):
        refuse()
    if any(unicodedata.category(char) in ("Cc", "Cf", "Cs") for char in value):
        refuse()


def _literal(value):
    if len(value) > 19 or re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value) is None:
        refuse()
    return int(value)


def _reject_number(value):
    refuse()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            refuse()
        result[key] = value
    return result


def _lexical_bounds(value):
    depth, count, index = 0, 0, 0
    while index < len(value):
        char = value[index]
        if char == '"':
            try:
                decoded, index = json.decoder.scanstring(value, index + 1, True)
                _string(decoded)
            except (ValueError, UnicodeEncodeError):
                refuse()
            count += 1
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                refuse()
            index += 1
        elif char in "]}":
            depth -= 1
            index += 1
        elif char in " \r\n\t,:":
            index += 1
        else:
            end = index + 1
            while end < len(value) and value[end] not in " \r\n\t,:[{}]":
                end += 1
            token = value[index:end]
            if char in "-0123456789":
                _literal(token)
            elif token not in ("true", "false", "null"):
                refuse()
            count += 1
            index = end
        if count > MAX_PRIMITIVES:
            refuse()


def parse_canonical_metadata(payload: bytes):
    """Strict new opt-in gate; no project/body lookup and no silent normalization."""
    if type(payload) is not bytes or len(payload) > MAX_METADATA_BYTES:
        refuse()
    try:
        value = payload.decode("utf-8", "strict")
    except UnicodeDecodeError:
        refuse()
    if value.startswith("\ufeff"):
        refuse()
    _lexical_bounds(value)
    try:
        obj = json.loads(value, object_pairs_hook=_pairs, parse_int=_literal,
                         parse_float=_reject_number, parse_constant=_reject_number)
    except (ValueError, TypeError, OverflowError):
        refuse()
    if type(obj) is not dict or canonical_bytes(obj) != payload:
        refuse()
    return obj


def _validate_envelope(obj):
    exact_object(obj, ("schema", "actor", "authorization", "tool", "request", "attempt", "result", "evidence", "visibility"))
    if obj["schema"] != ENVELOPE_SCHEMA:
        refuse(AcquisitionCode.SCHEMA_UNSUPPORTED)
    actor = obj["actor"]
    exact_object(actor, ("kind", "agent_id", "role"))
    if actor["kind"] != "AGENT" or type(actor["agent_id"]) is not str or _AGENT.fullmatch(actor["agent_id"]) is None:
        refuse()
    identifier(actor["role"])
    auth = obj["authorization"]
    exact_object(auth, ("kind", "decision_record", "decision_sha256", "approval_receipt_sha256"))
    if auth["kind"] != "HUMAN_DECISION" or type(auth["decision_record"]) is not str or _DECISION.fullmatch(auth["decision_record"]) is None:
        refuse()
    digest(auth["decision_sha256"])
    digest(auth["approval_receipt_sha256"])
    tool = obj["tool"]
    exact_object(tool, ("name", "version", "sha256"))
    identifier(tool["name"])
    identifier(tool["version"])
    digest(tool["sha256"])
    request = obj["request"]
    exact_object(request, ("fingerprint_schema", "sha256", "source_id", "provider", "product", "method", "host", "path", "parameters"))
    if type(request["fingerprint_schema"]) is not str or re.fullmatch(r"[a-z0-9._-]+/[1-9][0-9]*", request["fingerprint_schema"]) is None:
        refuse()
    digest(request["sha256"])
    for key in ("source_id", "provider", "product"):
        identifier(request[key])
    if request["method"] != "GET" or type(request["host"]) is not str or re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,24}", request["host"]) is None:
        refuse()
    path = request["path"]
    if type(path) is not str or len(path) > 256 or re.fullmatch(r"/[A-Za-z0-9_./-]+", path) is None or any(part in (".", "..", "") for part in path[1:].split("/")):
        refuse()
    path_parts = tuple(part.lower() for part in path[1:].split("/"))
    if path_parts[0] in ("users", "private", "tmp", "var", "etc", "volumes", "home", "root") or ".local" in path_parts:
        refuse()
    public_pairs(request["parameters"])
    attempt = obj["attempt"]
    exact_object(attempt, ("max_attempts", "ordinal", "reservation_receipt_sha256", "execution_receipt_sha256"))
    integer(attempt["max_attempts"], 1, 1)
    integer(attempt["ordinal"], 1, 1)
    digest(attempt["reservation_receipt_sha256"])
    digest(attempt["execution_receipt_sha256"])
    result = obj["result"]
    exact_object(result, ("state", "http_status", "payload_sha256", "size_bytes", "retrieved_at"))
    if result["state"] != "COMPLETE":
        refuse()
    integer(result["http_status"], 200, 200)
    digest(result["payload_sha256"])
    integer(result["size_bytes"])
    utc_instant(result["retrieved_at"])
    evidence = obj["evidence"]
    if type(evidence) is not list or len(evidence) != len(EVIDENCE_ROLES):
        refuse()
    for item, role in zip(evidence, EVIDENCE_ROLES):
        exact_object(item, ("role", "sha256"))
        if item["role"] != role:
            refuse()
        digest(item["sha256"])
    exact_object(obj["visibility"], ("raw", "model"))
    if obj["visibility"] != {"raw": "PRIVATE_LOCAL_ONLY", "model": "APPROVED_METADATA_ONLY"}:
        refuse()


@dataclass(frozen=True)
class AcquisitionEnvelope:
    content: bytes

    def __post_init__(self):
        _validate_envelope(parse_canonical_metadata(self.content))

    @classmethod
    def from_bytes(cls, payload: bytes):
        return cls(payload)

    def to_bytes(self) -> bytes:
        return self.content

    def to_obj(self):
        return parse_canonical_metadata(self.content)  # fresh, caller-owned object

    @property
    def sha256(self):
        return sha256_bytes(self.content)


@dataclass(frozen=True)
class EnvelopeIndex:
    """Metadata bytes only; exact digest lookup, no locator or discovery fallback."""
    entries: tuple

    def __post_init__(self):
        if type(self.entries) is not tuple or len(self.entries) > MAX_INDEX_ENTRIES:
            refuse()
        keys = set()
        for item in self.entries:
            if type(item) is not tuple or len(item) != 2:
                refuse()
            key, value = item
            digest(key)
            if key in keys or type(value) is not bytes or len(value) > MAX_METADATA_BYTES:
                refuse()
            keys.add(key)

    def resolve(self, envelope_sha256: str) -> AcquisitionEnvelope:
        digest(envelope_sha256)
        for key, value in self.entries:
            if key == envelope_sha256:
                if sha256_bytes(value) != key:
                    refuse(AcquisitionCode.BINDING_DIFFERS)
                return AcquisitionEnvelope.from_bytes(value)
        refuse(AcquisitionCode.INPUT_UNAVAILABLE)


@dataclass(frozen=True)
class TrustedAcquisitionWitness:
    """Separately supplied trusted-operator expectations, never parsed from JSON.

Public Python construction is not cryptographic identity/current authority. A
future trusted runtime boundary remains separate; this slice uses invented facts.
"""
    expected_envelope_sha256: str
    expected_manifest_sha256: str
    actor_agent_id: str
    actor_role: str
    approved_full_request_sha256: str

    def __post_init__(self):
        for value in (self.expected_envelope_sha256, self.expected_manifest_sha256, self.approved_full_request_sha256):
            digest(value)
        if type(self.actor_agent_id) is not str or _AGENT.fullmatch(self.actor_agent_id) is None:
            refuse()
        identifier(self.actor_role)


@dataclass(frozen=True)
class IntegrityBoundAcquisition:
    manifest_sha256: str
    envelope_sha256: str

    @property
    def state(self):
        return "INTEGRITY_BOUND_NOT_ADMITTED"

    @property
    def promotable(self):
        return False
