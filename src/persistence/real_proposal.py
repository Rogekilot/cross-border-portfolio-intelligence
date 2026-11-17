"""F1 R1: the proposal format `finweb.real_proposal/1`, its pure writer and its verifier (design 2.3 item 2).

A proposal is the file a qualification run writes and the owner reviews before a publish. It carries the CONTENT of a
snapshot (design 2.1) and nothing else: no rights, no expiry, no decision reference, no `valid_until`. Those are inputs of
the publish command, so a proposal file can never carry a lease and a publisher cannot be made to publish one by editing it.

Everything here is pure: no connection, no clock, no environment, no file. R1's tests build proposals from invented members
with `write_proposal`; R4b's qualification run calls the same writer, and R4b's exit requires its output to pass `verify_proposal`.

Shapes (canonical JSON, `marketdata.canonical.canonical_json`: sorted keys, no whitespace, no floats):

    proposal  {"context_id": hex64, "schema": "finweb.real_proposal/1", "snapshot": <snapshot>}
    snapshot  {"calendar_digest","convention_digest","f8b_policy_digest","identity_digest","profile_digest": hex64,
               "members": [member...]  (ordered),
               "origin": {"ledger_origin","market_origin","personal_holdings","synthetic"},
               "projection_digest": hex64,
               "registry": {"full_registry_digest","used_source_digest": hex64},
               "release": {"release_digest","release_id": hex64},
               "schema": "finweb.real_snapshot/1", "scope": "SYNTHETIC_TEST"|"TEST_SWITCH"|"REAL",
               "source_records": [source record...]  (the FULL registry the snapshot was published with, by source_id)}
    member    {"acquisition_record_sha256": hex64|null, "adapter_id", "adapter_version", "manifest_sha256", "payload_sha256",
               "source_id"}

`context_id` is the SHA-256 of the canonical snapshot bytes (content hash, design 2.2). The full-registry digest and the
used-source digest are DERIVED by the writer from the source records and recomputed by the verifier, so a run cannot report a
digest the records do not produce, and the two cannot be swapped unnoticed.

R4b (disposition note 5.3, obligation 1): both digests are the ENGINE's `marketdata.manifest.source_registry_digest` over the engine's
`SourceRecord`s that the proposal's records stand for (`real_registry_map`), not a digest of the proposal's own dicts. This is the
encoding the engine puts in `manifest.source_registry_digest`, so the seal's `RW_REAL_REGISTRY_DIFFERS` can pass. A proposal record has no
`synthetic` and no `source_priority` key: `synthetic` is the scope's origin (a test scope's sources are all synthetic; the REAL scope's
none is: O1), and a record with a priority is not representable (the registry file carries none). `terms_url` may be null (the
registry's `calendar.manual` has none) and, in the REAL scope, `terms_check` is exactly the engine's four fields.

R4b (E10, technical re-review L-7): in the REAL scope a member whose provenance slot (`acquisition_record_sha256`) is the explicit legacy
null is refused HERE, in the writer and the verifier alike, so the D6 requirement cannot lapse silently. The test scopes REQUIRE the null
(TR4B-M1): a sidecar digest in a test-scope member would store an invented human attestation in a snapshot (design 4.2, L-4).
The rest of O5 (the sidecar's bytes) needs those bytes and lives in `real_sidecar`.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from marketdata.canonical import CanonicalEncodingError, canonical_json
from persistence.real_registry_map import RegistryMapError, engine_source_record, registry_digests as _registry_digests
from persistence.real_scope import ScopeDef, ScopeError, REAL_ORIGIN_MARKER, require_resolved, scope_by_snapshot_field

PROPOSAL_SCHEMA = "finweb.real_proposal/1"
SNAPSHOT_SCHEMA = "finweb.real_snapshot/1"
MAX_PROPOSAL_BYTES = 2_000_000
MAX_MEMBERS = 64
MAX_SOURCE_RECORDS = 64

_HEX64 = re.compile(r"[0-9a-f]{64}")
_SOURCE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")

_SNAPSHOT_KEYS = frozenset(("schema", "scope", "members", "release", "projection_digest", "registry", "identity_digest",
                            "calendar_digest", "convention_digest", "profile_digest", "f8b_policy_digest", "origin",
                            "source_records"))
_MEMBER_KEYS = frozenset(("payload_sha256", "manifest_sha256", "source_id", "acquisition_record_sha256", "adapter_id",
                          "adapter_version"))
_RECORD_KEYS = frozenset(("source_id", "name", "upstream_provider", "independence_group", "terms_url", "terms_check"))
_DIGEST_FIELDS = ("projection_digest", "identity_digest", "calendar_digest", "convention_digest", "profile_digest",
                  "f8b_policy_digest")


class ProposalError(ValueError):
    def __init__(self, code, detail="Proposal refused"):
        self.code = code
        super().__init__("%s: %s" % (code, detail))


@dataclass(frozen=True)
class Member:
    payload_sha256: str
    manifest_sha256: str
    source_id: str
    acquisition_record_sha256: object   # hex64, or None (the explicit legacy null of the E10 provenance slot)
    adapter_id: str
    adapter_version: str

    def as_dict(self):
        return {"payload_sha256": self.payload_sha256, "manifest_sha256": self.manifest_sha256, "source_id": self.source_id,
                "acquisition_record_sha256": self.acquisition_record_sha256, "adapter_id": self.adapter_id,
                "adapter_version": self.adapter_version}


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    name: str
    upstream_provider: str
    independence_group: str
    terms_url: object                   # text, or None (the registry's `calendar.manual` has no URL)
    terms_check: object                 # None, or the engine's four fields as an object (a real terms check; test scopes never store one)

    def as_dict(self):
        return {"source_id": self.source_id, "name": self.name, "upstream_provider": self.upstream_provider,
                "independence_group": self.independence_group, "terms_url": self.terms_url, "terms_check": self.terms_check}


@dataclass(frozen=True)
class Snapshot:
    scope: str
    content: dict
    data: bytes
    context_id: str


@dataclass(frozen=True)
class VerifiedProposal:
    snapshot: Snapshot
    scope: ScopeDef
    member_sources: tuple


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def snapshot_bytes(content):
    return canonical_json(content).encode("utf-8")


def _hex64(value, field, *, nullable=False):
    if value is None and nullable:
        return None
    if type(value) is not str or _HEX64.fullmatch(value) is None:
        raise ProposalError("RW_PROPOSAL_SHAPE", "%s must be 64 lower-case hex characters" % field)
    return value


def _text(value, field, limit, *, allow_empty=False):
    if type(value) is not str or (not value and not allow_empty) or len(value) > limit:
        raise ProposalError("RW_PROPOSAL_SHAPE", "%s must be text of 1 to %d characters" % (field, limit))
    return value


def _source_id(value, field):
    if type(value) is not str or _SOURCE_ID.fullmatch(value) is None:
        raise ProposalError("RW_PROPOSAL_SHAPE", "%s is not a source id" % field)
    return value


def _json_value(value, field):
    try:
        canonical_json(value)
    except (CanonicalEncodingError, TypeError, ValueError) as error:
        raise ProposalError("RW_PROPOSAL_SHAPE", "%s is not plain JSON" % field) from error
    return value


def _member_dict(member, scope):
    if type(member) is not Member:
        raise ProposalError("RW_PROPOSAL_SHAPE", "members must be Member values")
    if scope.origin_axis == "REAL" and member.acquisition_record_sha256 is None:
        raise ProposalError("RW_O5_LEGACY_NULL", "the REAL scope refuses a member whose provenance slot is the legacy null (O5)")
    if scope.origin_axis != "REAL" and member.acquisition_record_sha256 is not None:
        # TR4B-M1 (design 4.2, L-4): a sidecar is an invented human attestation in a test scope, and its digest is never written to a snapshot
        raise ProposalError("RW_O5_SLOT_IN_TEST_SCOPE", "a test scope stores no sidecar digest: the provenance slot is null (O5 is bypassed)")
    return {"payload_sha256": _hex64(member.payload_sha256, "payload_sha256"),
            "manifest_sha256": _hex64(member.manifest_sha256, "manifest_sha256"),
            "source_id": _source_id(member.source_id, "member source_id"),
            "acquisition_record_sha256": _hex64(member.acquisition_record_sha256, "acquisition_record_sha256", nullable=True),
            "adapter_id": _text(member.adapter_id, "adapter_id", 128),
            "adapter_version": _text(member.adapter_version, "adapter_version", 64)}


def _record_dict(record, scope):
    if type(record) is not SourceRecord:
        raise ProposalError("RW_PROPOSAL_SHAPE", "source records must be SourceRecord values")
    terms = record.terms_check
    if terms is not None:
        if type(terms) is not dict:
            raise ProposalError("RW_PROPOSAL_SHAPE", "terms_check is null or an object")
        if scope.origin_axis != "REAL":
            # An invented permitting terms check is an invented human attestation: it is never written to a snapshot, in
            # any test scope (design 4.2, "The controls are in-memory validator inputs only").
            raise ProposalError("RW_ORIGIN_MIXED", "a test scope stores no terms check")
        _json_value(terms, "terms_check")
    out = {"source_id": _source_id(record.source_id, "source record source_id"),
           "name": _text(record.name, "name", 256), "upstream_provider": _text(record.upstream_provider, "upstream_provider", 256),
           "independence_group": _text(record.independence_group, "independence_group", 128),
           "terms_url": None if record.terms_url is None else _text(record.terms_url, "terms_url", 1024, allow_empty=True),
           "terms_check": terms}
    try:
        engine_source_record(out, synthetic=scope.synthetic)       # the engine's own constructors judge the record (shape of terms_check)
    except RegistryMapError as error:
        raise ProposalError("RW_PROPOSAL_SHAPE", str(error)) from error
    return out


def registry_digests(source_records, member_sources, *, synthetic):
    """(full-registry digest, used-source digest) of source-record dicts (design 2.1): the ENGINE's `source_registry_digest` over the
    engine records the dicts stand for (R4b, disposition note 5.3; `real_registry_map`). The used set holds exactly the records of the
    members' sources, so the two differ whenever a source is unused."""
    try:
        return _registry_digests(source_records, member_sources, synthetic=synthetic)
    except RegistryMapError as error:
        raise ProposalError("RW_PROPOSAL_SHAPE", str(error)) from error


def _reject_real_marker(scope, content):
    if scope.origin_axis == "SYNTHETIC" and REAL_ORIGIN_MARKER in canonical_json(content):
        raise ProposalError("RW_ORIGIN_MIXED", "a test scope never carries a real-origin string (I1, I3)")


def build_snapshot(scope, **content):
    """The pure builder of a snapshot of `scope`, a `ResolvedScope` from `real_scope.resolve_scope` (and nothing else: a name, a
    `ScopeDef` or a copy of one is refused, so this function is not a way round the reviewed test switch). The origin labels come
    from the scope, never from the caller. `content` is the keyword set of `_build_snapshot`."""
    return _build_snapshot(require_resolved(scope), **content)


def _build_snapshot(scope, *, members, source_records, release_id, release_digest, projection_digest, identity_digest,
                    calendar_digest, convention_digest, profile_digest, f8b_policy_digest):
    """The builder behind `build_snapshot` and `verify_proposal` (which rebuilds the scope its BYTES name, to check them). Private:
    it takes a `ScopeDef`, so nothing outside this module calls it (a static test checks the call sites)."""
    if type(scope) is not ScopeDef:
        raise ScopeError("RW_SCOPE_UNKNOWN", "A ScopeDef is required")
    members = tuple(members)
    source_records = tuple(source_records)
    if not 1 <= len(members) <= MAX_MEMBERS or not 1 <= len(source_records) <= MAX_SOURCE_RECORDS:
        raise ProposalError("RW_PROPOSAL_SHAPE", "a snapshot needs 1 to %d members and records" % MAX_MEMBERS)
    member_dicts = [_member_dict(m, scope) for m in members]
    record_dicts = sorted((_record_dict(r, scope) for r in source_records), key=lambda r: r["source_id"])
    if len({r["source_id"] for r in record_dicts}) != len(record_dicts):
        raise ProposalError("RW_PROPOSAL_SHAPE", "a source id appears in two source records")
    if len({m["payload_sha256"] for m in member_dicts}) != len(member_dicts):
        raise ProposalError("RW_PROPOSAL_SHAPE", "one manifest per payload: a payload appears twice")
    member_sources = frozenset(m["source_id"] for m in member_dicts)
    if not member_sources <= {r["source_id"] for r in record_dicts}:
        raise ProposalError("RW_PROPOSAL_SHAPE", "a member's source has no source record")
    full, used = registry_digests(record_dicts, member_sources, synthetic=scope.synthetic)
    content = {"schema": SNAPSHOT_SCHEMA, "scope": scope.name, "members": member_dicts,
               "release": {"release_id": _hex64(release_id, "release_id"), "release_digest": _hex64(release_digest, "release_digest")},
               "projection_digest": _hex64(projection_digest, "projection_digest"),
               "registry": {"full_registry_digest": full, "used_source_digest": used},
               "identity_digest": _hex64(identity_digest, "identity_digest"),
               "calendar_digest": _hex64(calendar_digest, "calendar_digest"),
               "convention_digest": _hex64(convention_digest, "convention_digest"),
               "profile_digest": _hex64(profile_digest, "profile_digest"),
               "f8b_policy_digest": _hex64(f8b_policy_digest, "f8b_policy_digest"),
               "origin": scope.origin_fields(), "source_records": record_dicts}
    _reject_real_marker(scope, content)
    data = snapshot_bytes(content)
    return Snapshot(scope.name, content, data, _sha256(data))


def proposal_document(snapshot):
    if type(snapshot) is not Snapshot:
        raise ProposalError("RW_PROPOSAL_SHAPE", "a Snapshot is required")
    return {"schema": PROPOSAL_SCHEMA, "context_id": snapshot.context_id, "snapshot": snapshot.content}


def proposal_bytes(snapshot):
    return canonical_json(proposal_document(snapshot)).encode("utf-8")


def write_proposal(scope, **content):
    """The pure proposal writer: content in, canonical proposal bytes out. R4b's qualification run calls this. `scope` is a
    `ResolvedScope` (see `build_snapshot`): a `TEST_SWITCH` proposal needs the reviewed switch of `real_scope.resolve_scope`."""
    return proposal_bytes(build_snapshot(scope, **content))


def _no_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ProposalError("RW_PROPOSAL_NOT_CANONICAL", "duplicate key " + key)
        seen[key] = value
    return seen


def _refuse_float(text):
    raise ProposalError("RW_PROPOSAL_SHAPE", "floats are not allowed")


def verify_proposal(data):
    """Check proposal bytes completely and return the verified snapshot. Raises `ProposalError` with a stable code.

    The scope comes from the scope field of the BYTES (`scope_by_snapshot_field`: data, never a grant of the test switch). Bytes
    of a `TEST_SWITCH` proposal therefore verify, wherever they came from; publish and admit refuse them in a `REAL` install, and
    the factory is the only product path that makes them. `VerifiedProposal.scope` is a `ScopeDef` and cannot be passed back to a
    builder.

    The checks, in order: bytes and size; strict canonical JSON (no duplicate key, no float, re-serialisation equals the input);
    the exact key sets; the scope and its origin labels; the shape of every member and record; the recomputed full-registry and
    used-source digests; the absence of a real-origin string in a test scope; and the content hash against `context_id`."""
    if type(data) is not bytes or not 2 <= len(data) <= MAX_PROPOSAL_BYTES:
        raise ProposalError("RW_PROPOSAL_SHAPE", "proposal bytes of 2 to %d bytes are required" % MAX_PROPOSAL_BYTES)
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicates, parse_float=_refuse_float)
    except (UnicodeDecodeError, ValueError) as error:
        if isinstance(error, ProposalError):
            raise
        raise ProposalError("RW_PROPOSAL_SHAPE", "not JSON") from error
    if type(document) is not dict or set(document) != {"schema", "context_id", "snapshot"} or document["schema"] != PROPOSAL_SCHEMA:
        raise ProposalError("RW_PROPOSAL_SHAPE", "not a %s document" % PROPOSAL_SCHEMA)
    try:
        canonical = canonical_json(document).encode("utf-8")
    except (CanonicalEncodingError, TypeError, ValueError) as error:
        raise ProposalError("RW_PROPOSAL_SHAPE", "not plain JSON") from error
    if canonical != data:
        raise ProposalError("RW_PROPOSAL_NOT_CANONICAL", "the bytes are not the canonical encoding")
    content = document["snapshot"]
    if type(content) is not dict or set(content) != _SNAPSHOT_KEYS or content["schema"] != SNAPSHOT_SCHEMA:
        raise ProposalError("RW_PROPOSAL_SHAPE", "not a %s snapshot" % SNAPSHOT_SCHEMA)
    try:
        scope = scope_by_snapshot_field(content["scope"])
    except ScopeError as error:
        raise ProposalError("RW_PROPOSAL_SHAPE", "unknown scope") from error
    if content["origin"] != scope.origin_fields():
        raise ProposalError("RW_ORIGIN_MISMATCH", "origin labels do not match the scope")
    members, records = content["members"], content["source_records"]
    if type(members) is not list or type(records) is not list:
        raise ProposalError("RW_PROPOSAL_SHAPE", "members and source records are lists")
    rebuilt_members = []
    for member in members:
        if type(member) is not dict or set(member) != _MEMBER_KEYS:
            raise ProposalError("RW_PROPOSAL_SHAPE", "a member has the wrong keys")
        rebuilt_members.append(Member(**member))
    rebuilt_records = []
    for record in records:
        if type(record) is not dict or set(record) != _RECORD_KEYS:
            raise ProposalError("RW_PROPOSAL_SHAPE", "a source record has the wrong keys")
        rebuilt_records.append(SourceRecord(**record))
    release, registry = content["release"], content["registry"]
    if type(release) is not dict or set(release) != {"release_id", "release_digest"} or type(registry) is not dict \
            or set(registry) != {"full_registry_digest", "used_source_digest"}:
        raise ProposalError("RW_PROPOSAL_SHAPE", "release or registry has the wrong keys")
    rebuilt = _build_snapshot(scope, members=rebuilt_members, source_records=rebuilt_records, release_id=release["release_id"],
                              release_digest=release["release_digest"], **{f: content[f] for f in _DIGEST_FIELDS})
    if rebuilt.content != content:
        # The digests of the registry are the only derived fields; an ordering or digest difference is reported as such.
        if rebuilt.content["registry"] != registry:
            raise ProposalError("RW_PROPOSAL_REGISTRY_DIGEST", "the registry digests do not match the source records")
        raise ProposalError("RW_PROPOSAL_NOT_CANONICAL", "the snapshot differs from its rebuilt form")
    if document["context_id"] != rebuilt.context_id or _hex64(document["context_id"], "context_id") != _sha256(rebuilt.data):
        raise ProposalError("RW_PROPOSAL_CONTEXT_DIFFERS", "context_id is not the content hash of the snapshot")
    return VerifiedProposal(rebuilt, scope, tuple(sorted({m["source_id"] for m in members})))
