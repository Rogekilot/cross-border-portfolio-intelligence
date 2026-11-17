"""F1 R4b: the sidecar acquisition record (design 6.1), its reader, and the O5 validator (design 4.2).

A sidecar is the owner's record, one per file, that the file entered the data version as the owner's act. It is canonical JSON and lives
OUTSIDE `data/marketdata/files/`, whose manifest scan must not change [E10]. A snapshot member carries it by DIGEST, in the provenance
slot `acquisition_record_sha256` (the SHA-256 of the sidecar's bytes). Shape (`finweb.acquisition_sidecar/1`):

    {"schema", "payload_sha256": hex64, "manifest_sha256": hex64,
     "approver_role": "designated human product owner"   (a role, never a personal name),
     "decision": {"pd_id": "PD-NNNN", "git_commit": 40 hex, "doc_sha256": 64 hex}   (the approving decision record, as in design 2.5),
     "request": text (the request as approved), "tool": text, "terms_check_reference": text}

O5 (design 4.2): in the REAL scope every member has a valid sidecar. VALID means: present; schema-valid; its payload and manifest digests
equal the member's; its approver role is the designated human product owner; its decision-reference triple is present (and well-formed);
and the member's slot equals the digest of the bytes. The explicit legacy null of the slot is refused in the REAL scope (technical
re-review L-7) and accepted in the two test scopes, where O5 is BYPASSED: an invented release needs no sidecar, and an invented sidecar
is an invented human attestation that must never be stored (design 4.2: "the controls are in-memory validator inputs only").

Everything here is pure: bytes in, verdict out. No function reads a file, a clock, the environment or a connection, and none writes: the
reader parses bytes it is given, the encoder returns bytes and writes nothing, and the validator takes sidecars BY VALUE. No sidecar file
is written for an invented payload. (The three real sidecars are written by the main session, R8's step; `encode_sidecar` is the one
canonical form it should use.)

Like the other origin predicates (E15) the validator reports EVERY failed predicate of every member, not the first, and does not call
anything that stops at a first failure. The SQL publish cannot see sidecar bytes, so O5 is enforced in Python: `RealPublisher.publish`
takes the sidecars of a REAL proposal and refuses unless this validator passes, and the qualification run refuses to write a REAL
proposal otherwise. A gateway that evaluated O5 itself would need the bytes in the database and is a gateway change (not made).
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from marketdata.canonical import CanonicalEncodingError, canonical_json
from persistence.real_scope import ResolvedScope, ScopeDef, ScopeError

SIDECAR_SCHEMA = "finweb.acquisition_sidecar/1"
#: The role, never the person (design 6.1): extra names in metadata that a model may see add exposure without proof.
APPROVER_ROLE = "designated human product owner"
MAX_SIDECAR_BYTES = 16_384

O5_MISSING = "RW_O5_SIDECAR_MISSING"
O5_LEGACY_NULL = "RW_O5_LEGACY_NULL"
O5_SCHEMA = "RW_O5_SIDECAR_SCHEMA"
O5_PAYLOAD = "RW_O5_PAYLOAD_DIGEST"
O5_MANIFEST = "RW_O5_MANIFEST_DIGEST"
O5_SLOT = "RW_O5_SLOT_DIGEST"
O5_ROLE = "RW_O5_APPROVER_ROLE"
O5_TRIPLE = "RW_O5_DECISION_TRIPLE"
O5_FAILED = "RW_O5_FAILED"
O5_SLOT_IN_TEST_SCOPE = "RW_O5_SLOT_IN_TEST_SCOPE"

_HEX64 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_PD = re.compile(r"PD-[0-9]{4,}")
_REQUIRED = frozenset(("schema", "payload_sha256", "manifest_sha256", "approver_role", "request", "tool", "terms_check_reference"))
_TEXT_FIELDS = (("approver_role", 256), ("request", 4096), ("tool", 512), ("terms_check_reference", 1024))


class SidecarError(ValueError):
    """A sidecar refusal. `code` is stable; `failures` is the full list of (payload_sha256, code) of an O5 refusal."""

    def __init__(self, code, detail="Sidecar refused", failures=()):
        self.code = code
        self.failures = tuple(failures)
        super().__init__("%s: %s" % (code, detail))


@dataclass(frozen=True)
class Sidecar:
    payload_sha256: str
    manifest_sha256: str
    approver_role: str
    pd_id: object
    git_commit: object
    doc_sha256: object
    request: str
    tool: str
    terms_check_reference: str
    digest: str


def sidecar_digest(data):
    """The SHA-256 of a sidecar's bytes: the value of the member's provenance slot."""
    if type(data) is not bytes:
        raise SidecarError(O5_SCHEMA, "sidecar bytes are required")
    return hashlib.sha256(data).hexdigest()


def encode_sidecar(*, payload_sha256, manifest_sha256, pd_id, git_commit, doc_sha256, request, tool, terms_check_reference,
                   approver_role=APPROVER_ROLE):
    """The canonical bytes of a sidecar. Returns bytes and WRITES NOTHING; whoever calls it decides what to do with them. The arguments
    are not validated here (the validator is the judge, and a test needs to build faulty sidecars to see it refuse them)."""
    document = {"schema": SIDECAR_SCHEMA, "payload_sha256": payload_sha256, "manifest_sha256": manifest_sha256,
                "approver_role": approver_role, "request": request, "tool": tool, "terms_check_reference": terms_check_reference}
    if pd_id is not None or git_commit is not None or doc_sha256 is not None:
        document["decision"] = {"pd_id": pd_id, "git_commit": git_commit, "doc_sha256": doc_sha256}
    return canonical_json(document).encode("utf-8")


def _no_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError("duplicate key " + key)
        seen[key] = value
    return seen


def _refuse_float(text):
    raise ValueError("floats are not allowed")


def _parse(data):
    """(document, codes). `document` is the parsed object when the bytes are strict canonical JSON of the right outline, else None; `codes`
    lists every schema-level problem found (never more than the schema code: a bad outline is one fact)."""
    if type(data) is not bytes or not 2 <= len(data) <= MAX_SIDECAR_BYTES:
        return None, [O5_SCHEMA]
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicates, parse_float=_refuse_float)
        if type(document) is not dict or canonical_json(document).encode("utf-8") != data:
            return None, [O5_SCHEMA]
    except (UnicodeDecodeError, ValueError, CanonicalEncodingError, TypeError):
        return None, [O5_SCHEMA]
    keys = set(document)
    if document.get("schema") != SIDECAR_SCHEMA or not _REQUIRED <= keys or not keys <= _REQUIRED | {"decision"}:
        return None, [O5_SCHEMA]
    for name, limit in _TEXT_FIELDS:
        value = document[name]
        if type(value) is not str or not value or len(value) > limit:
            return None, [O5_SCHEMA]
    for name in ("payload_sha256", "manifest_sha256"):
        if type(document[name]) is not str or _HEX64.fullmatch(document[name]) is None:
            return None, [O5_SCHEMA]
    return document, []


def _triple(document):
    """(pd_id, git_commit, doc_sha256) when the decision-reference triple is complete and well formed, else None."""
    decision = document.get("decision")
    if type(decision) is not dict or set(decision) != {"pd_id", "git_commit", "doc_sha256"}:
        return None
    pd_id, commit, doc = decision["pd_id"], decision["git_commit"], decision["doc_sha256"]
    if type(pd_id) is not str or _PD.fullmatch(pd_id) is None or type(commit) is not str or _COMMIT.fullmatch(commit) is None \
            or type(doc) is not str or _HEX64.fullmatch(doc) is None:
        return None
    return pd_id, commit, doc


def sidecar_failures(data, *, payload_sha256, manifest_sha256, slot):
    """Every O5 predicate that fails for ONE sidecar against the member it claims to record, as a tuple of codes in a fixed order (empty:
    the sidecar is valid). The predicates are independent: a sidecar with a wrong payload digest AND a wrong role lists both."""
    document, codes = _parse(data)
    if document is None:
        return tuple(codes)
    failures = []
    if document["payload_sha256"] != payload_sha256:
        failures.append(O5_PAYLOAD)
    if document["manifest_sha256"] != manifest_sha256:
        failures.append(O5_MANIFEST)
    if slot != hashlib.sha256(data).hexdigest():
        failures.append(O5_SLOT)
    if document["approver_role"] != APPROVER_ROLE:
        failures.append(O5_ROLE)
    if _triple(document) is None:
        failures.append(O5_TRIPLE)
    return tuple(failures)


def read_sidecar(data):
    """Parse a sidecar given as BYTES (writes nothing, reads nothing else). Raises `SidecarError` when the bytes are not a schema-valid
    sidecar; the approver role and the decision triple are NOT judged here (they are O5 predicates, so a sidecar that fails them can be
    read and then reported), and `pd_id`, `git_commit` and `doc_sha256` are None when the triple is absent or malformed."""
    document, codes = _parse(data)
    if document is None:
        raise SidecarError(codes[0], "not a %s document" % SIDECAR_SCHEMA)
    triple = _triple(document) or (None, None, None)
    return Sidecar(document["payload_sha256"], document["manifest_sha256"], document["approver_role"], *triple, document["request"],
                   document["tool"], document["terms_check_reference"], sidecar_digest(data))


def _axis(scope):
    if type(scope) not in (ScopeDef, ResolvedScope):
        raise ScopeError("RW_SCOPE_UNKNOWN", "a ScopeDef or a ResolvedScope is required")
    return scope.origin_axis


def _field(member, name):
    return member[name] if isinstance(member, dict) else getattr(member, name)


@dataclass(frozen=True)
class O5Report:
    """The verdict of O5 over a set of members: every (payload_sha256, code) that failed, sorted. `bypassed` is True for a test scope."""
    failures: tuple
    bypassed: bool

    @property
    def ok(self):
        return not self.failures

    def codes(self, payload_sha256=None):
        return tuple(sorted({code for sha, code in self.failures if payload_sha256 in (None, sha)}))


def o5_failures(scope, members, sidecars=()):
    """O5 over `members` (`real_proposal.Member` values or the member dicts of a snapshot) and `sidecars`, an iterable of sidecar BYTES taken by
    value. In a test scope O5 is bypassed (an empty report, `bypassed=True`): the legacy null is accepted and a sidecar is neither needed nor
    looked at. In the REAL scope, for each member: a null slot is `RW_O5_LEGACY_NULL` and has no sidecar to read (`RW_O5_SIDECAR_MISSING` too);
    a slot with no sidecar of that digest among `sidecars` is `RW_O5_SIDECAR_MISSING`; otherwise `sidecar_failures` lists the rest.
    Reports every failure of every member; writes nothing."""
    axis = _axis(scope)
    if axis != "REAL":
        return O5Report((), True)
    members = tuple(members)
    by_digest = {}
    for data in sidecars:
        by_digest.setdefault(sidecar_digest(data), data)
    failures = []
    for member in members:
        payload, manifest, slot = _field(member, "payload_sha256"), _field(member, "manifest_sha256"), _field(member, "acquisition_record_sha256")
        if slot is None:
            failures += [(payload, O5_LEGACY_NULL), (payload, O5_MISSING)]
            continue
        data = by_digest.get(slot)
        if data is None:
            failures.append((payload, O5_MISSING))
            continue
        failures += [(payload, code) for code in sidecar_failures(data, payload_sha256=payload, manifest_sha256=manifest, slot=slot)]
    return O5Report(tuple(sorted(set(failures))), False)


def require_null_slots_in_test_scope(scope, members):
    """TR4B-M1 (design 4.2, L-4): in a test scope every member's provenance slot is null, because the digest of an invented sidecar is an invented
    human attestation and is never stored in a snapshot. Raises `SidecarError(RW_O5_SLOT_IN_TEST_SCOPE)` listing the members that hold one; a no-op
    in the REAL scope. The proposal verifier refuses the same thing; the publisher calls this too, before any statement, so the refusal does not
    depend on the verifier alone."""
    if _axis(scope) == "REAL":
        return
    held = sorted(_field(m, "payload_sha256") for m in members if _field(m, "acquisition_record_sha256") is not None)
    if held:
        raise SidecarError(O5_SLOT_IN_TEST_SCOPE, "a test scope stores no sidecar digest: %s" % ", ".join(sha[:12] for sha in held),
                           tuple((sha, O5_SLOT_IN_TEST_SCOPE) for sha in held))


def require_o5(scope, members, sidecars=()):
    """`o5_failures`, raised: `SidecarError(RW_O5_FAILED)` carrying the full failure list when anything failed. Returns the report."""
    report = o5_failures(scope, members, sidecars)
    if not report.ok:
        raise SidecarError(O5_FAILED, "O5 failed: " + ", ".join("%s %s" % (sha[:12], code) for sha, code in report.failures), report.failures)
    return report


def candidate_failures(scope, sources, origin_members, members, sidecars=()):
    """The candidate validation of design 4.2: O1, O2, O3 (`real_provenance.origin_report`, over the STORED facts: no attestation is passed by
    a product call site) and O5 (`o5_failures`), evaluated INDEPENDENTLY, every failed predicate reported (the origin codes in their order, then
    the sorted O5 codes). Neither stops at a first failure, and the O5 verdict does not depend on the origin verdict or the reverse: a REAL-scope
    candidate with synthetic sources and a fully valid sidecar lists O1 and O2 and no O5 code. The sidecars come in by value; nothing is written.
    (A test that needs an invented terms check or acquisition calls `origin_report` with it and joins the codes itself, as this function does.)"""
    from persistence import real_provenance           # a function-level import: the origin module is pure, but this one is imported by the publisher

    origin = real_provenance.origin_report(sources, origin_members)
    return tuple(origin.failed) + o5_failures(scope, members, sidecars).codes()


def sidecar_for(sidecars, member):
    """The sidecar BYTES among `sidecars` that record `member` (matched by the payload and manifest digests they state), or None. Used by
    the qualification run to fill the member's slot; a sidecar that states the right digests but is otherwise invalid is still matched,
    so that O5 reports what is wrong with it instead of a bare 'missing'."""
    payload, manifest = _field(member, "payload_sha256"), _field(member, "manifest_sha256")
    found = None
    for data in sidecars:
        document, _codes = _parse(data)
        if document is not None and document["payload_sha256"] == payload and document["manifest_sha256"] == manifest:
            if found is not None and found != data:
                raise SidecarError(O5_SCHEMA, "two different sidecars record the file %s" % payload[:12])
            found = data
    return found
