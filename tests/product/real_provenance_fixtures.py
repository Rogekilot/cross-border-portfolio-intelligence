"""Pure fixtures of the F1 R2 registry tests. Not a test module.

Ported from N2a's invented-byte fixture (`reviews/OVERNIGHT_EXECUTION_2026-10-20/n2a-handover/`), generalised to the three scopes.
EVERYTHING HERE IS INVENTED: source ids are fictional, digests are SHA-256 of invented text, the agent and the decision are made up.
No value comes from a real file, source or licence, and nothing here opens a connection or a file.

Two rules from the design (4.2) are kept by construction:

  * invented data is never `synthetic = false`. A `candidate()` carries `synthetic=True` sources unless a test asks for the other value
    to build bytes that a validator must REFUSE, and such bytes are only ever passed to a validator;
  * an invented permitting terms check or invented human acquisition is an invented attestation by a human. `candidate()` can build a
    manifest that claims a human acquirer (`retrieved_by`/`usage_scope`) for the refusal cases of a test scope, and never stores one:
    the registry refuses it. The validator controls (O2, O3) are passed BY VALUE to the pure predicates, not through this module.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from marketdata.acquisition import TrustedAcquisitionWitness  # noqa: E402
from persistence.real_provenance import ArtifactBundle, MemberKey  # noqa: E402

SOURCE_ID = "fictional.source"
PAYLOAD = b"synthetic-payload-one\n"


def h(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


@dataclass(frozen=True)
class Candidate:
    bundle: ArtifactBundle
    members: tuple
    witnesses: tuple

    @property
    def context_sha256(self):
        return h(self.bundle.context_bytes)

    def args(self):
        """The keyword set of `validate_bundle` / `register` that names the independent expectations."""
        return dict(expected_context_sha256=self.context_sha256, expected_members=self.members, witnesses=self.witnesses)

    def context(self):
        return json.loads(self.bundle.context_bytes)


def source_record(source_id=SOURCE_ID, *, synthetic=True, terms_check=None, terms_url=None):
    return dict(source_id=source_id, name="Invented source", upstream_provider="InventedProvider", independence_group="InventedProvider",
                terms_url=terms_url, terms_check=terms_check, synthetic=synthetic)


def candidate(payload=PAYLOAD, acquisitions=(1,), *, scope="SYNTHETIC_TEST", financial_context=None, v1=False, source_id=SOURCE_ID,
              synthetic=True, terms_check=None, terms_url=None, retrieved_by=None, usage_scope=None, role="CORPORATE_ACTION", salt=""):
    """An invented candidate. `v1=True` builds the legacy manifest (no acquisition envelope); the default is the agent-acquired v2 form
    that N2a's tests use. `salt` makes the digests unique to a test. `retrieved_by`/`usage_scope` override a v1 manifest's own fields."""
    manifests, envelopes, raw_witnesses, members, witnesses = {}, {}, {}, [], []
    for n in acquisitions:
        request_pin = h(("invented full request " + str(n) + salt).encode())
        tool_pin = h(b"invented frozen tool")
        time = "2001-02-" + str(n + 3).zfill(2) + "T03:02:01Z"
        parameters = [["from", "2001-02-03"], ["to", "2001-02-03"], ["fmt", "json"]]
        env = dict(schema="finweb.marketdata.acquisition_envelope/1",
                   actor=dict(kind="AGENT", agent_id="/root/invented_collector", role="engineer"),
                   authorization=dict(kind="HUMAN_DECISION", decision_record="decisions/product/PD-9001-invented-evaluation.md",
                                      decision_sha256=h(b"invented decision"), approval_receipt_sha256=h(b"invented receipt")),
                   tool=dict(name="invented_collector.py", version="1.0.0", sha256=tool_pin),
                   request=dict(fingerprint_schema="fictional.request_spec/1", sha256=request_pin, source_id=source_id,
                                provider="InventedProvider", product="invented_rows", method="GET", host="fictional.invalid",
                                path="/api/splits/FICTION", parameters=parameters),
                   attempt=dict(max_attempts=1, ordinal=1, reservation_receipt_sha256=h(("reservation" + str(n) + salt).encode()),
                                execution_receipt_sha256=h(("execution" + str(n) + salt).encode())),
                   result=dict(state="COMPLETE", http_status=200, payload_sha256=h(payload), size_bytes=len(payload), retrieved_at=time),
                   evidence=[dict(role=r, sha256=h(("invented " + r).encode()))
                             for r in ("APPROVAL_PACKET", "REQUEST_SPEC", "EXECUTION_METADATA", "EXECUTION_REVIEW")],
                   visibility=dict(raw="PRIVATE_LOCAL_ONLY", model="APPROVED_METADATA_ONLY"))
        eraw = encode(env)
        manifest = dict(schema="finweb.marketdata.file_manifest/2", file_sha256=h(payload), size_bytes=len(payload),
                        payload_filename="invented.json", payload_format="fictional_rows/1", source_id=source_id, data_kind=role, market=None,
                        retrieval_time=time, retrieved_by="agent", request=parameters, declared_adjustment="RAW", adjustment_anchor=None,
                        declared_currency=None, declared_delay="UNKNOWN", source_identifiers=["FICTION.US"],
                        script=dict(name="invented_collector.py", version="1.0.0", script_sha256=tool_pin), libraries=[],
                        usage_scope="INTERNAL_DEVELOPMENT_ONLY", coverage=[["from", "2001-02-03"], ["to", "2001-02-03"]],
                        acquisition=dict(schema="finweb.marketdata.acquisition_ref/1", envelope_sha256=h(eraw)))
        if v1:
            del manifest["acquisition"]
            manifest.update(schema="finweb.marketdata.file_manifest/1", retrieved_by=retrieved_by or "synthetic",
                            usage_scope=usage_scope or "SYNTHETIC_TEST")
        mraw = encode(manifest)
        manifests[h(mraw)] = mraw
        if v1:
            members.append(MemberKey(role, h(payload), h(mraw), None, None))
        else:
            witness = TrustedAcquisitionWitness(h(eraw), h(mraw), "/root/invented_collector", "engineer", request_pin)
            wraw = encode(dict(expected_envelope_sha256=h(eraw), expected_manifest_sha256=h(mraw), actor_agent_id="/root/invented_collector",
                               actor_role="engineer", approved_full_request_sha256=request_pin))
            raw_witnesses[h(wraw)] = wraw
            envelopes[h(eraw)] = eraw
            witnesses.append(witness)
            members.append(MemberKey(role, h(payload), h(mraw), h(eraw), h(wraw)))
    members = tuple(sorted(members, key=lambda x: x.sort_key()))
    ctx = encode(dict(schema="finweb.provenance_context/1", scope=scope, state="INTEGRITY_BOUND_NOT_ADMITTED", promotable=False,
                      source_admitted=False, financial_context_sha256=financial_context,
                      source_records=[source_record(source_id, synthetic=synthetic, terms_check=terms_check, terms_url=terms_url)],
                      members=[x.to_obj() for x in members]))
    bundle = ArtifactBundle(ctx, ((h(payload), payload),), tuple(sorted(manifests.items())), tuple(sorted(envelopes.items())),
                            tuple(sorted(raw_witnesses.items())))
    return Candidate(bundle, members, tuple(sorted(witnesses, key=lambda x: x.expected_manifest_sha256)))


def with_context(cand, **changes):
    """The candidate with fields of its context document replaced. The independent context pin follows the new bytes (a test that wants
    a mismatching pin builds it from `cand.args()` before the change)."""
    obj = json.loads(cand.bundle.context_bytes)
    obj.update(changes)
    bundle = replace(cand.bundle, context_bytes=encode(obj))
    return Candidate(bundle, cand.members, cand.witnesses)


def with_members(cand, members, **bundle_changes):
    obj = json.loads(cand.bundle.context_bytes)
    obj["members"] = [m.to_obj() for m in members]
    bundle = replace(cand.bundle, context_bytes=encode(obj), **bundle_changes)
    return Candidate(bundle, tuple(members), cand.witnesses)


def with_manifest_fields(cand, **fields):
    """Replace fields of the (single) v1 manifest; the member and the context follow the new manifest bytes."""
    (_old_key, old_raw), = cand.bundle.manifests
    obj = json.loads(old_raw)
    obj.update(fields)
    raw = encode(obj)
    member = replace(cand.members[0], manifest_sha256=h(raw))
    changed = Candidate(replace(cand.bundle, manifests=((h(raw), raw),)), cand.members, cand.witnesses)
    return with_members(changed, (member,))
