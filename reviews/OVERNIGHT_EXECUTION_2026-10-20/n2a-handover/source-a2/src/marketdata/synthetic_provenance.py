"""Opt-in invented-byte provenance; never admission, discovery, or current rights.

Witnesses and expected pins are separate trusted-operator inputs. Storing them
cannot authenticate a collector. E11 remains unchanged and authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import uuid

from marketdata.acquisition import (AcquisitionCode, AcquisitionError, EnvelopeIndex,
    TrustedAcquisitionWitness, canonical_bytes, parse_canonical_metadata)
from marketdata.canonical import canonical_json
from marketdata.manifest import DataKind, SourceRecord
from marketdata.manifest_v2 import FileManifestV2, read_manifest_metadata, verify_acquisition_binding

CONTEXT_SCHEMA = "finweb.synthetic_provenance_context/1"
REQUEST_SCHEMA = "finweb.synthetic_provenance_registration/1"
RESPONSE_SCHEMA = "finweb.synthetic_provenance_registration_result/1"
SCOPE = "SYNTHETIC_TEST"
STATE = "INTEGRITY_BOUND_NOT_ADMITTED"
MAX_ITEMS, MAX_PAYLOAD, MAX_METADATA, MAX_WITNESS, MAX_BUNDLE = 16, 65536, 65536, 4096, 4194304
CONTEXT_KEYS = frozenset("schema scope state promotable source_admitted financial_context_sha256 source_records members".split())
MEMBER_KEYS = frozenset("role payload_sha256 manifest_sha256 envelope_sha256 witness_sha256".split())
WITNESS_KEYS = ("expected_envelope_sha256", "expected_manifest_sha256", "actor_agent_id", "actor_role", "approved_full_request_sha256")


class ProvenanceError(ValueError):
    def __init__(self, code="NP_SHAPE"):
        self.code = code
        super().__init__(code)


def refuse(code="NP_SHAPE"):
    raise ProvenanceError(code)


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def require_digest(value):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        refuse()
    return value


def metadata(raw, limit=MAX_METADATA):
    if type(raw) is not bytes or not 2 <= len(raw) <= limit:
        refuse()
    try:
        return parse_canonical_metadata(raw)
    except AcquisitionError as exc:
        refuse("NP_UNSUPPORTED_PROVENANCE" if exc.code is AcquisitionCode.SCHEMA_UNSUPPORTED else "NP_SHAPE")


@dataclass(frozen=True)
class SyntheticMemberKey:
    role: str
    payload_sha256: str
    manifest_sha256: str
    envelope_sha256: str | None
    witness_sha256: str | None

    def __post_init__(self):
        if type(self.role) is not str:
            refuse()
        try:
            DataKind(self.role)
        except ValueError:
            refuse()
        require_digest(self.payload_sha256)
        require_digest(self.manifest_sha256)
        if (self.envelope_sha256 is None) != (self.witness_sha256 is None):
            refuse()
        if self.envelope_sha256 is not None:
            require_digest(self.envelope_sha256)
            require_digest(self.witness_sha256)

    def sort_key(self):
        return (self.role, self.payload_sha256, self.manifest_sha256,
                self.envelope_sha256 or "", self.witness_sha256 or "")

    def to_obj(self):
        return {k: getattr(self, k) for k in MEMBER_KEYS}


@dataclass(frozen=True)
class SyntheticArtifactBundle:
    context_bytes: bytes
    payloads: tuple
    manifests: tuple
    envelopes: tuple
    witnesses: tuple


@dataclass(frozen=True)
class ValidatedSyntheticContext:
    context_sha256: str
    bundle: SyntheticArtifactBundle
    members: tuple
    source_records: tuple
    envelope_index: EnvelopeIndex = field(repr=False)
    state: str = field(default=STATE, init=False)
    scope: str = field(default=SCOPE, init=False)
    promotable: bool = field(default=False, init=False)
    source_admitted: bool = field(default=False, init=False)

    @property
    def financial_context_sha256(self):
        return metadata(self.bundle.context_bytes)["financial_context_sha256"]


def witness_bytes(witness):
    if type(witness) is not TrustedAcquisitionWitness:
        refuse("NP_BINDING_DIFFERS")
    return canonical_bytes({key: getattr(witness, key) for key in WITNESS_KEYS})


def _artifacts(items, maximum):
    if type(items) is not tuple or len(items) > MAX_ITEMS:
        refuse()
    keys, result = [], {}
    for pair in items:
        if type(pair) is not tuple or len(pair) != 2:
            refuse()
        key, raw = pair
        require_digest(key)
        if type(raw) is not bytes or len(raw) > maximum:
            refuse()
        if sha256(raw) != key:
            refuse("NP_BINDING_DIFFERS")
        if key in result:
            refuse()
        keys.append(key)
        result[key] = raw
    if keys != sorted(keys):
        refuse()
    return result


def _members(items):
    if type(items) is not tuple or not 1 <= len(items) <= MAX_ITEMS or any(type(x) is not SyntheticMemberKey for x in items):
        refuse()
    keys = [x.sort_key() for x in items]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        refuse()
    return items


def _sources(items):
    if type(items) is not list or not 1 <= len(items) <= MAX_ITEMS:
        refuse()
    records = []
    required = {"source_id", "name", "upstream_provider", "independence_group", "terms_url", "terms_check", "synthetic"}
    for item in items:
        if type(item) is not dict or set(item) not in (required, required | {"source_priority"}):
            refuse()
        if item["synthetic"] is not True or item["terms_url"] is not None or item["terms_check"] is not None:
            refuse("NP_SCOPE_REFUSED")
        if any(type(item[k]) is not str or not item[k] or len(item[k].encode("utf8")) > 128 for k in
               ("source_id", "name", "upstream_provider", "independence_group")):
            refuse()
        if "source_priority" in item and (type(item["source_priority"]) is not int or not 1 <= item["source_priority"] < 2**63):
            refuse()
        try:
            record = SourceRecord(**item)
        except (TypeError, ValueError):
            refuse()
        if record.to_obj() != item:
            refuse()
        records.append(record)
    ids = [x.source_id for x in records]
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        refuse()
    return tuple(records)


def validate_bundle(bundle, *, expected_context_sha256, expected_members, witnesses):
    """Validate every byte before storage; expected values are never read from it."""
    require_digest(expected_context_sha256)
    expected_members = _members(expected_members)
    if type(bundle) is not SyntheticArtifactBundle:
        refuse()
    raw = bundle.context_bytes
    if type(raw) is not bytes or len(raw) > MAX_METADATA:
        refuse()
    if sha256(raw) != expected_context_sha256:
        refuse("NP_CONTEXT_DIFFERS")
    # Byte/count bounds precede metadata tree construction.
    payloads = _artifacts(bundle.payloads, MAX_PAYLOAD)
    manifests = _artifacts(bundle.manifests, MAX_METADATA)
    envelopes = _artifacts(bundle.envelopes, MAX_METADATA)
    stored_witnesses = _artifacts(bundle.witnesses, MAX_WITNESS)
    if len(raw) + sum(len(v) for values in (payloads, manifests, envelopes, stored_witnesses) for v in values.values()) > MAX_BUNDLE:
        refuse()
    obj = metadata(raw)
    if set(obj) != CONTEXT_KEYS or obj["schema"] != CONTEXT_SCHEMA:
        refuse("NP_UNSUPPORTED_PROVENANCE")
    if (obj["scope"] != SCOPE or obj["state"] != STATE or obj["promotable"] is not False or obj["source_admitted"] is not False):
        refuse("NP_SCOPE_REFUSED")
    if obj["financial_context_sha256"] is not None:
        require_digest(obj["financial_context_sha256"])
    raw_members = obj["members"]
    if type(raw_members) is not list or not 1 <= len(raw_members) <= MAX_ITEMS:
        refuse()
    members = []
    for value in raw_members:
        if type(value) is not dict or set(value) != MEMBER_KEYS:
            refuse()
        members.append(SyntheticMemberKey(**value))
    members = _members(tuple(members))
    if members != expected_members:
        refuse("NP_CONTEXT_DIFFERS")
    sources = _sources(obj["source_records"])
    if type(witnesses) is not tuple or len(witnesses) > MAX_ITEMS or any(type(x) is not TrustedAcquisitionWitness for x in witnesses):
        refuse("NP_BINDING_DIFFERS")
    wk = [x.expected_manifest_sha256 for x in witnesses]
    if wk != sorted(wk) or len(set(wk)) != len(wk):
        refuse("NP_BINDING_DIFFERS")
    trusted = {x.expected_manifest_sha256: x for x in witnesses}
    refs = (set(x.payload_sha256 for x in members), set(x.manifest_sha256 for x in members),
            set(x.envelope_sha256 for x in members if x.envelope_sha256 is not None),
            set(x.witness_sha256 for x in members if x.witness_sha256 is not None))
    for supplied, selected in ((payloads, refs[0]), (manifests, refs[1]), (envelopes, refs[2]), (stored_witnesses, refs[3])):
        if set(supplied) != selected:
            refuse("NP_INPUT_MISSING" if selected - set(supplied) else "NP_BINDING_DIFFERS")
    if set(trusted) != {x.manifest_sha256 for x in members if x.envelope_sha256 is not None}:
        refuse("NP_BINDING_DIFFERS")
    index = EnvelopeIndex(tuple(envelopes.items()))
    source_ids = set()
    for member in members:
        mraw = manifests[member.manifest_sha256]
        mobj = metadata(mraw)
        try:
            manifest = read_manifest_metadata(mraw)
        except AcquisitionError as exc:
            refuse("NP_UNSUPPORTED_PROVENANCE" if exc.code is AcquisitionCode.SCHEMA_UNSUPPORTED else "NP_SHAPE")
        if (mobj["file_sha256"] != member.payload_sha256 or mobj["data_kind"] != member.role
                or mobj["size_bytes"] != len(payloads[member.payload_sha256])):
            refuse("NP_BINDING_DIFFERS")
        source_ids.add(mobj["source_id"])
        if type(manifest) is FileManifestV2:
            if member.envelope_sha256 is None or mobj["acquisition"]["envelope_sha256"] != member.envelope_sha256:
                refuse("NP_BINDING_DIFFERS")
            witness = trusted[member.manifest_sha256]
            wraw = stored_witnesses[member.witness_sha256]
            metadata(wraw, MAX_WITNESS)
            if witness_bytes(witness) != wraw:
                refuse("NP_BINDING_DIFFERS")
            try:
                verify_acquisition_binding(manifest, index, witness)
            except AcquisitionError:
                refuse("NP_BINDING_DIFFERS")
        elif (member.envelope_sha256 is not None or mobj["retrieved_by"] != "synthetic" or mobj["usage_scope"] != SCOPE):
            refuse("NP_SCOPE_REFUSED")
    if source_ids != {x.source_id for x in sources}:
        refuse("NP_BINDING_DIFFERS")
    return ValidatedSyntheticContext(expected_context_sha256, bundle, members, sources, index)


def registration_request(operation_id, context):
    if type(operation_id) is not uuid.UUID or type(context) is not ValidatedSyntheticContext:
        refuse()
    b = context.bundle
    return canonical_bytes(dict(schema=REQUEST_SCHEMA, scope=SCOPE, operation_id=str(operation_id),
        context_sha256=context.context_sha256, payload_sha256s=[k for k, _ in b.payloads],
        manifest_sha256s=[k for k, _ in b.manifests], envelope_sha256s=[k for k, _ in b.envelopes],
        witness_sha256s=[k for k, _ in b.witnesses]))


def registration_response(operation_id, request_bytes, context):
    if type(operation_id) is not uuid.UUID or type(context) is not ValidatedSyntheticContext or type(request_bytes) is not bytes:
        refuse()
    b = context.bundle
    return canonical_json(dict(schema=RESPONSE_SCHEMA, scope=SCOPE, state=STATE, promotable=False,
        source_admitted=False, operation_id=str(operation_id), request_sha256=sha256(request_bytes),
        context_sha256=context.context_sha256, payload_count=len(b.payloads), manifest_count=len(b.manifests),
        envelope_count=len(b.envelopes), member_count=len(context.members))).encode("utf8")
