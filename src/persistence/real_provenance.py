"""F1 R2: the real gateway's candidate registry, PURE side (design 4.1, 4.2): N2a generalised to the three scopes.

A CANDIDATE is the bytes a qualification run proposes: a context document (scope, source records, member keys), the payloads, the
manifests, and for an agent-acquired (v2) member its acquisition envelope and a trusted-operator witness. Registering a candidate stores
its bytes; it never admits anything (`state` is always INTEGRITY_BOUND_NOT_ADMITTED, `promotable` and `source_admitted` are always
false). Admission is the gateway's publish, and publish consults the registry (design 4.2: "Publish evaluates the same list").

This module does no I/O: no connection, no file, no clock, no environment. It holds

  * the candidate validator `validate_bundle`, scope-parameterised (the structure checks are N2a's, every scope-specific rule is a
    branch on the scope's origin axis and says so);
  * the ORIGIN PREDICATES O1, O2 and O3 (design 4.2, E15), separate functions of their own inputs. They report EVERY failure, they
    take invented attestations only BY VALUE (the `terms_checks` and `acquisitions` arguments), and they write nothing;
  * the registration request and response encoders.

The predicates do not depend on the scope: they say whether a candidate meets the origin conditions. What differs by scope is the
policy. In the `REAL` scope any failure refuses the candidate (`RW_PROV_ORIGIN_REFUSED`, with every failed code). In the two test
scopes the failures are EXPECTED (the synthetic axis is what the reviewed switch bypasses), are reported on the validated context and
refuse nothing, while the scope's own invariants (I1: every source synthetic, no stored attestation) refuse a candidate that breaks
them. An invented permitting terms check or an invented human acquisition is an invented attestation by a human: it is never stored,
in any scope, and a test-scope candidate that carries one is refused (design 4.2, "The controls are in-memory validator inputs only").

The SQL side (`real_provenance_v1.sql`) implements the same predicates and the same scope rules for the database, because the loader
role can call the put function with any bytes and the publisher's publish reads the registry. A parity test runs one table of cases
through both and fails if they differ.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import hashlib
import re
import uuid

from marketdata.acquisition import (AcquisitionCode, AcquisitionError, EnvelopeIndex, TrustedAcquisitionWitness, canonical_bytes,
                                    parse_canonical_metadata)
from marketdata.canonical import canonical_json
from marketdata.manifest import DataKind
from marketdata.manifest_v2 import FileManifestV2, read_registry_manifest_metadata, verify_acquisition_binding
from persistence.real_scope import ScopeDef, ScopeError, require_resolved, scope_by_snapshot_field

CONTEXT_SCHEMA = "finweb.provenance_context/1"
REQUEST_SCHEMA = "finweb.provenance_registration/1"
RESPONSE_SCHEMA = "finweb.provenance_registration_result/1"
STATE = "INTEGRITY_BOUND_NOT_ADMITTED"
MAX_ITEMS, MAX_PAYLOAD, MAX_METADATA, MAX_WITNESS, MAX_BUNDLE = 16, 65536, 65536, 4096, 4194304
CONTEXT_KEYS = frozenset("schema scope state promotable source_admitted financial_context_sha256 source_records members".split())
MEMBER_KEYS = frozenset("role payload_sha256 manifest_sha256 envelope_sha256 witness_sha256".split())
WITNESS_KEYS = ("expected_envelope_sha256", "expected_manifest_sha256", "actor_agent_id", "actor_role", "approved_full_request_sha256")
SOURCE_KEYS = frozenset("source_id name upstream_provider independence_group terms_url terms_check synthetic".split())
TERMS_KEYS = frozenset("checked_by checked_on permits_internal_development_use notes".split())

#: The origin predicates' codes (design 4.2). `RW_PROV_CANDIDATE_MISSING` is publish's: a member whose candidate is not registered.
O1 = "RW_O1_SYNTHETIC_SOURCE"
O2 = "RW_O2_TERMS_CHECK"
O3 = "RW_O3_ACQUISITION"
ORIGIN_CODES = (O1, O2, O3)
CANDIDATE_MISSING = "RW_PROV_CANDIDATE_MISSING"
ORIGIN_REFUSED = "RW_PROV_ORIGIN_REFUSED"
ORIGIN_MIXED = "RW_ORIGIN_MIXED"

MANIFEST_V1, MANIFEST_V2 = "v1", "v2"
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_HEX = frozenset("0123456789abcdef")


class ProvenanceError(ValueError):
    """A refusal. `code` is the stable `RW_*` code; `codes` lists every failed predicate for an origin refusal (code first)."""

    def __init__(self, code="RW_PROV_SHAPE", codes=()):
        self.code = code
        self.codes = (code,) + tuple(codes)
        super().__init__(code)


def refuse(code="RW_PROV_SHAPE", codes=()):
    raise ProvenanceError(code, codes)


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def require_digest(value):
    if type(value) is not str or len(value) != 64 or any(c not in _HEX for c in value):
        refuse()
    return value


def metadata(raw, limit=MAX_METADATA):
    if type(raw) is not bytes or not 2 <= len(raw) <= limit:
        refuse()
    try:
        return parse_canonical_metadata(raw)
    except AcquisitionError as exc:
        refuse("RW_PROV_UNSUPPORTED" if exc.code is AcquisitionCode.SCHEMA_UNSUPPORTED else "RW_PROV_SHAPE")


# =====================================================================================================================
# The origin predicates (design 4.2, E15). Pure. Invented attestations come in BY VALUE and are never stored or retained.
# =====================================================================================================================
def _permits(terms_check):
    """A permitting HUMAN terms check: a real object with a named checker, a date, and `permits_internal_development_use` exactly true.
    A missing (None), negative, malformed or non-object value does not permit. Nothing here looks at whether the source is synthetic."""
    if type(terms_check) is not dict:
        return False
    checked_by, checked_on = terms_check.get("checked_by"), terms_check.get("checked_on")
    if type(checked_by) is not str or not checked_by.strip() or type(checked_on) is not str or _DATE.fullmatch(checked_on) is None:
        return False
    try:
        dt.date.fromisoformat(checked_on)
    except ValueError:
        return False
    return terms_check.get("permits_internal_development_use") is True


def o1_fails(sources):
    """O1, a source must NOT be synthetic: fails when there is no source to check or any source's `synthetic` is not exactly false."""
    return not sources or any(s.get("synthetic") is not False for s in sources)


def o2_fails(sources, terms_checks=None):
    """O2, a permitting human terms check, read from the source's `terms_check` DIRECTLY (not `terms_attested`, which is true for any
    synthetic source). `terms_checks` maps source_id to an in-memory attestation that replaces the stored one for this evaluation."""
    if not sources:
        return True
    terms_checks = {} if terms_checks is None else terms_checks
    for source in sources:
        effective = terms_checks[source.get("source_id")] if source.get("source_id") in terms_checks else source.get("terms_check")
        if not _permits(effective):
            return True
    return False


def o3_fails(members, acquisitions=None):
    """O3, the member's acquirer is `human` and its usage scope is INTERNAL_DEVELOPMENT_ONLY, read from the member's OWN manifest fields
    (not from ingest's tie of a file's usage scope to its source's synthetic flag). A v2 manifest is an agent acquisition and fails.
    `acquisitions` maps manifest_sha256 to an in-memory {schema, retrieved_by, usage_scope} that replaces the stored facts."""
    if not members:
        return True
    acquisitions = {} if acquisitions is None else acquisitions
    for member in members:
        facts = acquisitions[member.get("manifest_sha256")] if member.get("manifest_sha256") in acquisitions else member
        if not (facts.get("schema") == MANIFEST_V1 and facts.get("retrieved_by") == "human"
                and facts.get("usage_scope") == "INTERNAL_DEVELOPMENT_ONLY"):
            return True
    return False


@dataclass(frozen=True)
class OriginReport:
    """Every failed predicate, in the order O1, O2, O3. Empty means all three hold."""
    failed: tuple

    @property
    def ok(self):
        return not self.failed


def origin_report(sources, members, *, terms_checks=None, acquisitions=None):
    """Evaluate O1, O2 and O3 INDEPENDENTLY and report every one that fails (it does not stop at the first). `sources` is a sequence of
    {"source_id", "synthetic", "terms_check"}; `members` a sequence of {"manifest_sha256", "schema", "retrieved_by", "usage_scope"}.
    `terms_checks` and `acquisitions` are invented attestations by value (design 4.2): they change this evaluation and nothing else."""
    sources, members = tuple(sources), tuple(members)
    failed = tuple(code for code, bad in ((O1, o1_fails(sources)), (O2, o2_fails(sources, terms_checks)),
                                          (O3, o3_fails(members, acquisitions))) if bad)
    return OriginReport(failed)


# =====================================================================================================================
# Candidate values
# =====================================================================================================================
@dataclass(frozen=True)
class MemberKey:
    role: str
    payload_sha256: str
    manifest_sha256: str
    envelope_sha256: object
    witness_sha256: object

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
        return (self.role, self.payload_sha256, self.manifest_sha256, self.envelope_sha256 or "", self.witness_sha256 or "")

    def to_obj(self):
        return {k: getattr(self, k) for k in MEMBER_KEYS}


@dataclass(frozen=True)
class ArtifactBundle:
    context_bytes: bytes
    payloads: tuple
    manifests: tuple
    envelopes: tuple
    witnesses: tuple


@dataclass(frozen=True)
class ValidatedContext:
    context_sha256: str
    scope: str
    bundle: ArtifactBundle
    members: tuple
    source_records: tuple               # the stored source records, as plain dicts
    member_facts: tuple                 # per member: {"source_id", "manifest_sha256", "schema", "retrieved_by", "usage_scope"}
    envelope_index: EnvelopeIndex = field(repr=False)
    state: str = field(default=STATE, init=False)
    promotable: bool = field(default=False, init=False)
    source_admitted: bool = field(default=False, init=False)

    @property
    def financial_context_sha256(self):
        return metadata(self.bundle.context_bytes)["financial_context_sha256"]

    def origin(self, *, terms_checks=None, acquisitions=None):
        """The origin report of this candidate. Called with no argument it evaluates what is STORED. The two keyword arguments are for
        the validators' controls (invented attestations by value); no product call site passes them (a static test checks)."""
        return origin_report(self.source_records, self.member_facts, terms_checks=terms_checks, acquisitions=acquisitions)


def witness_bytes(witness):
    if type(witness) is not TrustedAcquisitionWitness:
        refuse("RW_PROV_BINDING_DIFFERS")
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
            refuse("RW_PROV_BINDING_DIFFERS")
        if key in result:
            refuse()
        keys.append(key)
        result[key] = raw
    if keys != sorted(keys):
        refuse()
    return result


def _members(items):
    if type(items) is not tuple or not 1 <= len(items) <= MAX_ITEMS or any(type(x) is not MemberKey for x in items):
        refuse()
    keys = [x.sort_key() for x in items]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        refuse()
    return items


def _terms_check_shape(value):
    if value is None:
        return
    if type(value) is not dict or set(value) != TERMS_KEYS:
        refuse()
    for key in ("checked_by", "checked_on", "notes"):
        if type(value[key]) is not str or len(value[key].encode("utf8")) > 1024:
            refuse()
    if type(value["permits_internal_development_use"]) is not bool or not value["checked_by"].strip():
        refuse()
    if _DATE.fullmatch(value["checked_on"]) is None:
        refuse()
    try:
        dt.date.fromisoformat(value["checked_on"])
    except ValueError:
        refuse()


def _sources(items, scope):
    """The source records, checked in this order: shape, then I2 (no mixing of synthetic and real origin in one candidate), then the scope's
    own rule. In a TEST scope every source is synthetic and no attestation is stored (I1); in the REAL scope a source's flag and
    terms check are whatever they are, and O1 and O2 judge them."""
    if type(items) is not list or not 1 <= len(items) <= MAX_ITEMS:
        refuse()
    for item in items:
        if type(item) is not dict or set(item) not in (SOURCE_KEYS, SOURCE_KEYS | {"source_priority"}):
            refuse()
        if any(type(item[k]) is not str or not item[k] or len(item[k].encode("utf8")) > 128
               for k in ("source_id", "name", "upstream_provider", "independence_group")):
            refuse()
        if type(item["synthetic"]) is not bool:
            refuse()
        if item["terms_url"] is not None and (type(item["terms_url"]) is not str or len(item["terms_url"].encode("utf8")) > 1024):
            refuse()
        _terms_check_shape(item["terms_check"])
        if "source_priority" in item and (type(item["source_priority"]) is not int or isinstance(item["source_priority"], bool)
                                          or not 1 <= item["source_priority"] < 2 ** 63):
            refuse()
    ids = [x["source_id"] for x in items]
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        refuse()
    if len({x["synthetic"] for x in items}) > 1:
        refuse(ORIGIN_MIXED)
    if scope.origin_axis == "SYNTHETIC":
        if any(x["synthetic"] is not True or x["terms_url"] is not None or x["terms_check"] is not None for x in items):
            refuse("RW_PROV_SCOPE_REFUSED")
    return tuple(dict(x) for x in items)


def validate_bundle(scope, bundle, *, expected_context_sha256, expected_members, witnesses):
    """Validate every byte of a candidate before storage; expected values are never read from it.

    `scope` is a `ResolvedScope` from `real_scope.resolve_scope`: a candidate of the test-switch scope needs the reviewed switch like a
    snapshot of it does. The context's own scope field must be that scope. Raises `ProvenanceError` (code, and `codes` for an origin
    refusal). Returns a `ValidatedContext`, whose `origin()` reports O1 to O3 (informational in a test scope, a refusal in REAL)."""
    return _validate_bundle(require_resolved(scope), bundle, expected_context_sha256=expected_context_sha256,
                            expected_members=expected_members, witnesses=witnesses)


def validate_loaded_bundle(scope, bundle, *, expected_context_sha256, expected_members, witnesses):
    """Validate a candidate that was READ BACK from the registry. `scope` is the `ScopeDef` named by the field of data already stored
    (the lease's snapshot, via `real_scope.scope_by_snapshot_field`), like the proposal verifier: reading back never grants the test
    switch, because nothing here can create a candidate. Only an entry of the scope table is accepted, not a copy."""
    try:
        known = type(scope) is ScopeDef and scope_by_snapshot_field(scope.name) is scope
    except ScopeError:
        known = False
    if not known:
        refuse("RW_PROV_SCOPE_REFUSED")
    return _validate_bundle(scope, bundle, expected_context_sha256=expected_context_sha256,
                            expected_members=expected_members, witnesses=witnesses)


def _validate_bundle(scope, bundle, *, expected_context_sha256, expected_members, witnesses):
    require_digest(expected_context_sha256)
    expected_members = _members(expected_members)
    if type(bundle) is not ArtifactBundle:
        refuse()
    raw = bundle.context_bytes
    if type(raw) is not bytes or len(raw) > MAX_METADATA:
        refuse()
    if sha256(raw) != expected_context_sha256:
        refuse("RW_PROV_CONTEXT_DIFFERS")
    # Byte and count bounds precede metadata tree construction.
    payloads = _artifacts(bundle.payloads, MAX_PAYLOAD)
    manifests = _artifacts(bundle.manifests, MAX_METADATA)
    envelopes = _artifacts(bundle.envelopes, MAX_METADATA)
    stored_witnesses = _artifacts(bundle.witnesses, MAX_WITNESS)
    if len(raw) + sum(len(v) for values in (payloads, manifests, envelopes, stored_witnesses) for v in values.values()) > MAX_BUNDLE:
        refuse()
    obj = metadata(raw)
    if set(obj) != CONTEXT_KEYS or obj["schema"] != CONTEXT_SCHEMA:
        refuse("RW_PROV_UNSUPPORTED")
    if (obj["scope"] != scope.name or obj["state"] != STATE or obj["promotable"] is not False or obj["source_admitted"] is not False):
        refuse("RW_PROV_SCOPE_REFUSED")
    if obj["financial_context_sha256"] is not None:
        require_digest(obj["financial_context_sha256"])
    raw_members = obj["members"]
    if type(raw_members) is not list or not 1 <= len(raw_members) <= MAX_ITEMS:
        refuse()
    members = []
    for value in raw_members:
        if type(value) is not dict or set(value) != MEMBER_KEYS:
            refuse()
        members.append(MemberKey(**value))
    members = _members(tuple(members))
    if members != expected_members:
        refuse("RW_PROV_CONTEXT_DIFFERS")
    sources = _sources(obj["source_records"], scope)
    if type(witnesses) is not tuple or len(witnesses) > MAX_ITEMS or any(type(x) is not TrustedAcquisitionWitness for x in witnesses):
        refuse("RW_PROV_BINDING_DIFFERS")
    wk = [x.expected_manifest_sha256 for x in witnesses]
    if wk != sorted(wk) or len(set(wk)) != len(wk):
        refuse("RW_PROV_BINDING_DIFFERS")
    trusted = {x.expected_manifest_sha256: x for x in witnesses}
    refs = (set(x.payload_sha256 for x in members), set(x.manifest_sha256 for x in members),
            set(x.envelope_sha256 for x in members if x.envelope_sha256 is not None),
            set(x.witness_sha256 for x in members if x.witness_sha256 is not None))
    for supplied, selected in ((payloads, refs[0]), (manifests, refs[1]), (envelopes, refs[2]), (stored_witnesses, refs[3])):
        if set(supplied) != selected:
            refuse("RW_PROV_INPUT_MISSING" if selected - set(supplied) else "RW_PROV_BINDING_DIFFERS")
    if set(trusted) != {x.manifest_sha256 for x in members if x.envelope_sha256 is not None}:
        refuse("RW_PROV_BINDING_DIFFERS")
    index = EnvelopeIndex(tuple(envelopes.items()))
    source_ids, facts = set(), []
    for member in members:
        mraw = manifests[member.manifest_sha256]
        mobj = metadata(mraw)
        try:
            manifest = read_registry_manifest_metadata(mraw)
        except AcquisitionError as exc:
            refuse("RW_PROV_UNSUPPORTED" if exc.code is AcquisitionCode.SCHEMA_UNSUPPORTED else "RW_PROV_SHAPE")
        if (mobj["file_sha256"] != member.payload_sha256 or mobj["data_kind"] != member.role
                or mobj["size_bytes"] != len(payloads[member.payload_sha256])):
            refuse("RW_PROV_BINDING_DIFFERS")
        source_ids.add(mobj["source_id"])
        if type(manifest) is FileManifestV2:
            if member.envelope_sha256 is None or mobj["acquisition"]["envelope_sha256"] != member.envelope_sha256:
                refuse("RW_PROV_BINDING_DIFFERS")
            witness = trusted[member.manifest_sha256]
            wraw = stored_witnesses[member.witness_sha256]
            metadata(wraw, MAX_WITNESS)
            if witness_bytes(witness) != wraw:
                refuse("RW_PROV_BINDING_DIFFERS")
            try:
                verify_acquisition_binding(manifest, index, witness)
            except AcquisitionError:
                refuse("RW_PROV_BINDING_DIFFERS")
            schema_tag = MANIFEST_V2
        else:
            if member.envelope_sha256 is not None:
                refuse("RW_PROV_SCOPE_REFUSED")
            if scope.origin_axis == "SYNTHETIC" and (mobj["retrieved_by"] != "synthetic" or mobj["usage_scope"] != "SYNTHETIC_TEST"):
                refuse("RW_PROV_SCOPE_REFUSED")                      # I1: a test scope stores no invented human attestation
            schema_tag = MANIFEST_V1
        facts.append({"source_id": mobj["source_id"], "manifest_sha256": member.manifest_sha256, "schema": schema_tag,
                      "retrieved_by": mobj["retrieved_by"], "usage_scope": mobj["usage_scope"]})
    if source_ids != {x["source_id"] for x in sources}:
        refuse("RW_PROV_BINDING_DIFFERS")
    context = ValidatedContext(expected_context_sha256, scope.name, bundle, members, sources, tuple(facts), index)
    report = context.origin()
    if scope.origin_axis == "REAL" and not report.ok:
        refuse(ORIGIN_REFUSED, report.failed)
    return context


def registration_request(operation_id, context):
    if type(operation_id) is not uuid.UUID or type(context) is not ValidatedContext:
        refuse()
    b = context.bundle
    return canonical_bytes(dict(schema=REQUEST_SCHEMA, scope=context.scope, operation_id=str(operation_id),
                                context_sha256=context.context_sha256, payload_sha256s=[k for k, _ in b.payloads],
                                manifest_sha256s=[k for k, _ in b.manifests], envelope_sha256s=[k for k, _ in b.envelopes],
                                witness_sha256s=[k for k, _ in b.witnesses]))


def registration_response(operation_id, request_bytes, context):
    if type(operation_id) is not uuid.UUID or type(context) is not ValidatedContext or type(request_bytes) is not bytes:
        refuse()
    b = context.bundle
    return canonical_json(dict(schema=RESPONSE_SCHEMA, scope=context.scope, state=STATE, promotable=False, source_admitted=False,
                               operation_id=str(operation_id), request_sha256=sha256(request_bytes), context_sha256=context.context_sha256,
                               payload_count=len(b.payloads), manifest_count=len(b.manifests), envelope_count=len(b.envelopes),
                               member_count=len(context.members))).encode("utf8")
