"""F1 R4b: the provenance candidate of a qualified release (design 2.3 item 1, 3.3 item 1; R3 disposition note, "tool that registers the
context-bound candidates after the publish").

A candidate (`persistence.real_provenance`) is the registry's record of the FILES of a release: the context document, the payload bytes and the
manifest bytes of every member, and no acquisition envelope (the files of a `FileStore` are v1 manifests; v2 loading is later work, design 6.1).
It is registered by the LOADER role through `RealProvenanceStore.register`, twice and in this order (3.3 item 1; R8 steps 2 to 4a):

  1. UNBOUND (`financial_context_sha256` null), before the publish: the publish consults the registry for each member's manifest and reports
     `RW_PROV_CANDIDATE_MISSING` for a member whose candidate is not registered (`rwp_origin_failures`);
  2. BOUND to the published context (`financial_context_sha256` = the snapshot's `context_id`), after the publish, because the registration's
     financial context is a foreign key to the snapshot. The executor's guarded load refuses unless it equals the lease's context.

`build_candidate` is pure (it reads the store's bytes and writes nothing). `registration_operation_id` makes the operation id a function of the
context bytes, so re-running the identical command reconciles and never duplicates. The tool returns what the store returns; it opens no
connection of its own and never calls the loader's other functions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import uuid

from marketdata.acquisition import canonical_bytes
from persistence.real_provenance import (ArtifactBundle, CONTEXT_SCHEMA, MemberKey, STATE, registration_request, sha256, validate_bundle)
from persistence.real_scope import require_resolved

#: A fixed namespace: the operation id of a registration is `uuid5(NAMESPACE, context_sha256)`. It is an idempotence key, not a secret.
OPERATION_NAMESPACE = uuid.UUID("5e7e0d2a-4b1c-5c1e-9d57-52b0c0a0f1b4")


class CandidateError(ValueError):
    def __init__(self, code, detail="Candidate refused"):
        self.code = code
        super().__init__("%s: %s" % (code, detail))


@dataclass(frozen=True)
class BuiltCandidate:
    bundle: ArtifactBundle
    members: tuple
    witnesses: tuple
    context_sha256: str
    bound_to: object                        # the financial context digest, or None for the unbound candidate


def registration_operation_id(context_sha256):
    return uuid.uuid5(OPERATION_NAMESPACE, context_sha256)


def _source_record(record, definition):
    terms = record.terms_check
    if definition.origin_axis == "SYNTHETIC":
        # a test scope's candidate stores no URL and no terms check (I1; `real_provenance._sources`)
        return {"source_id": record.source_id, "name": record.name, "upstream_provider": record.upstream_provider,
                "independence_group": record.independence_group, "terms_url": None, "terms_check": None, "synthetic": record.synthetic}
    return {"source_id": record.source_id, "name": record.name, "upstream_provider": record.upstream_provider,
            "independence_group": record.independence_group, "terms_url": record.terms_url, "synthetic": record.synthetic,
            "terms_check": None if terms is None else {"checked_by": terms.checked_by, "checked_on": terms.checked_on.isoformat(),
                                                       "permits_internal_development_use": terms.permits_internal_development_use,
                                                       "notes": terms.notes}}


def build_candidate(scope, store, qualification, *, financial_context=None):
    """The candidate of `qualification`'s release: every member's payload and manifest bytes, read from `store` (read-only), and the source
    records of the members' sources. `financial_context` is None (unbound) or the published snapshot's context id (bound)."""
    definition = require_resolved(scope)
    if qualification.scope != definition.name:
        raise CandidateError("RW_CAND_SCOPE", "the qualification is of scope %s, not %s" % (qualification.scope, definition.name))
    if financial_context is not None and (type(financial_context) is not str or len(financial_context) != 64):
        raise CandidateError("RW_CAND_CONTEXT", "a financial context is a SHA-256 hex digest")
    index = store.index()
    registry = store.load_registry()
    members, payloads, manifests = [], {}, {}
    for member, manifest in zip(qualification.members, qualification.manifests):
        path = index[member.payload_sha256]
        verified = store.read_verified(path)                                        # the engine re-verifies the payload bytes against the manifest
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != member.manifest_sha256:
            raise CandidateError("RW_CAND_MANIFEST", "the manifest file of %s changed since the qualification" % member.payload_sha256[:12])
        payloads[member.payload_sha256] = verified.payload
        manifests[member.manifest_sha256] = raw
        members.append(MemberKey(manifest.data_kind.value, member.payload_sha256, member.manifest_sha256, None, None))
    members = tuple(sorted(members, key=lambda m: m.sort_key()))
    source_ids = sorted({m.source_id for m in qualification.members})
    context = canonical_bytes({"schema": CONTEXT_SCHEMA, "scope": definition.name, "state": STATE, "promotable": False, "source_admitted": False,
                               "financial_context_sha256": financial_context,
                               "source_records": [_source_record(registry.get(s), definition) for s in source_ids],
                               "members": [m.to_obj() for m in members]})
    bundle = ArtifactBundle(context, tuple(sorted(payloads.items())), tuple(sorted(manifests.items())), (), ())
    return BuiltCandidate(bundle, members, (), hashlib.sha256(context).hexdigest(), financial_context)


def register_candidate(store_on_loader_connection, scope, candidate):
    """Register `candidate` through a `RealProvenanceStore` on the LOADER's connection (the store validates every byte first, in memory, and
    refuses a REAL candidate that fails O1 to O3 with every failed code). Returns the store's `CommittedRegistration` or `UnknownRegistration`;
    a definite refusal is the store's `ProvenanceError`. The operation id is derived from the context bytes."""
    if type(candidate) is not BuiltCandidate:
        raise CandidateError("RW_CAND_SHAPE", "a BuiltCandidate is required")
    return store_on_loader_connection.register(scope, registration_operation_id(candidate.context_sha256), candidate.bundle,
                                               expected_context_sha256=candidate.context_sha256, expected_members=candidate.members,
                                               witnesses=candidate.witnesses)


def reconcile_candidate(store_on_loader_connection, scope, candidate):
    """Settle the registration of `candidate` (R8, TR6R-L1) through the loader's `RealProvenanceStore.reconcile`, by the same operation id
    `register_candidate` derives. The expected request digest is the digest of the request the identical `register` would have sent (the
    candidate is validated in memory first, so a candidate that could not be registered cannot be reconciled either). Returns the store's
    `CommittedRegistration` (stored, and equal to what the identical command writes) or `UnknownRegistration` (not found, or not readable:
    NOT a definite answer); a stored registration that differs is the store's `ProvenanceError` (`RW_PROV_OPERATION_CONFLICT`)."""
    if type(candidate) is not BuiltCandidate:
        raise CandidateError("RW_CAND_SHAPE", "a BuiltCandidate is required")
    operation_id = registration_operation_id(candidate.context_sha256)
    context = validate_bundle(scope, candidate.bundle, expected_context_sha256=candidate.context_sha256, expected_members=candidate.members,
                              witnesses=candidate.witnesses)
    return store_on_loader_connection.reconcile(scope, operation_id, expected_request_sha256=sha256(registration_request(operation_id, context)),
                                                expected_context_sha256=candidate.context_sha256, expected_members=candidate.members,
                                                witnesses=candidate.witnesses)
