"""F1 R4b: the qualification run (design 6.4, [E9] proposal (a); design 7.1, R4b row).

The run READS a market-data store directly (no staging copy, so nothing for the withdrawal procedure of 3.3 to miss), builds the release
through the engine's own ingest (the terms gate, the label tests and the identity checks are the engine's), and writes a PROPOSAL with the
pure writer of `persistence.real_proposal` for the owner to review. It writes nothing else, publishes nothing and opens no connection;
`load_qualified` is the separate, explicit step that projects the release into a database, through the R3 entry point
`persistence.real_loader.load_release` and never through `market_data_store.write_release` (a static test checks that no R4b code calls it).

What the snapshot is built FROM (disposition note 5.3, R4b obligations 1 and 2):

  * `members` come from the release's OWN files: one member per file of the release, `payload_sha256` the file's hash, `source_id` its
    manifest's source, so they match what the loader writes to `md_release_file` joined to `md_file` and what the seal compares
    (`RW_REAL_MEMBERS_DIFFER`). A file is a member whatever its data kind (calendars and identity files included);
  * `registry.used_source_digest` is the engine's `source_registry_digest` over the engine records of the members' sources
    (`persistence.real_registry_map`), so `RW_REAL_REGISTRY_DIFFERS` can pass. The proposal carries the FULL registry of the store.

The digests the design does not define (identity, calendar, convention, profile, release) are defined here, each over plain data and
recomputable from the same inputs; see the functions below. They are R4b's choice, recorded in the self-validation, and R5's world builder
recomputes them from the locked snapshot.

O5 (design 4.2): in the REAL scope the run refuses unless every member has a valid sidecar (`persistence.real_sidecar`); the sidecars are
taken BY VALUE, as bytes, and nothing is written. A test scope takes no sidecar at all: an invented sidecar is an invented human
attestation, and its digest must not be stored in a snapshot.

The run lists every member against the owner's digest-confirmation table (6.3) and the rule under it ("any other file that enters `M` needs
its own confirmation or registered check before it counts"). The listing informs the owner; it gates nothing by itself (the gates are O5,
and the owner's decision at publish). Whatever the engine reports while building (issues, unresolved identities, series a label test
contradicted) is carried in the result and marks it `needs_review`; the run decides nothing about admissibility that the method does not.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from marketdata import profiles
from marketdata.canonical import canonical_json
from marketdata.ingest import build_in_memory_market_data
from performance_service.service import policy_reference
from persistence import market_data_store as mds, real_loader, real_proposal, real_sidecar
from persistence.real_scope import require_resolved

#: Design 6.3, recomputed from the files on disk (read-only) when this was written: payload SHA-256 -> (manifest SHA-256, path under files/).
#: `AAPL_XNGS.json` has the SAME payload as `AAPL_UW.json` and a different manifest (`cb4d862d...`); it is evidence only and is never a member.
HG4_CONFIRMATION_TABLE = {
    "066c65e6e7ce61c06f1f413b3e313f1b797fc9fff632ce2a2f2ca4b8b1b9d1fb":
        ("268535ddc8b6284a144cbe810668a3586a9e574f257b438794bbe08c1f0efb82", "alphavantage.us/quote/2026-10-01/AAPL_compact.csv"),
    "b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc":
        ("7952829ba052599cfb51ffd3715a9b99b5ad9bf7c4406f734ecaa3aaf986a738", "openfigi/identity/2026-10-23/AAPL_UW.json"),
}

CONFIRMED = "CONFIRMED"
MANIFEST_DIFFERS = "MANIFEST_DIFFERS"
REGISTERED_CHECK = "REGISTERED_CHECK"
NOT_CONFIRMED = "NOT_CONFIRMED"
TEST_SCOPE = "TEST_SCOPE"          # a test scope's members are invented: the owner's confirmation table does not apply


class QualificationError(ValueError):
    def __init__(self, code, detail="Qualification refused"):
        self.code = code
        super().__init__("%s: %s" % (code, detail))


@dataclass(frozen=True)
class MemberRow:
    """One member of the release listed against the 6.3 table."""
    path: str
    payload_sha256: str
    manifest_sha256: str
    source_id: str
    data_kind: str
    retrieved_by: str
    usage_scope: str
    confirmation: str
    sidecar_sha256: object


@dataclass(frozen=True)
class Qualification:
    proposal: bytes
    context_id: str
    scope: str
    release: object
    built: object
    members: tuple
    rows: tuple
    table_rows_without_member: tuple
    o5_bypassed: bool
    needs_review: bool
    review_lines: tuple

    @property
    def manifests(self):
        return self.built.manifests

    def lines(self):
        """The operator's listing: every member against the 6.3 table, the O5 state and whatever the build reported."""
        out = ["scope %s; context %s; %d member(s)" % (self.scope, self.context_id, len(self.rows))]
        for row in self.rows:
            out.append("  %-18s %s  %s/%s  %s  sidecar %s" % (row.confirmation, row.payload_sha256[:12], row.source_id, row.data_kind, row.path,
                                                          "-" if row.sidecar_sha256 is None else row.sidecar_sha256[:12]))
        for sha in self.table_rows_without_member:
            out.append("  table row with no member in this release: %s" % sha[:12])
        out.append("O5 (sidecars): " + ("bypassed in a test scope" if self.o5_bypassed else "every member has a valid sidecar"))
        out += ["needs review: " + line for line in self.review_lines]
        return out


# ---- the digests the design leaves to R4b ---------------------------------------------------------------------------------------------

# R5 moved the six digest functions, unchanged, to `persistence.real_digests`, because the product's world builder recomputes them and product code
# never imports this package. The names stay importable from here, so the run and its tests call the one implementation.
from persistence.real_digests import (  # noqa: E402,F401
    _sha, calendar_digest, convention_digest, identity_digest, profile_digest, projection_digest, release_digest)


# ---- the run ---------------------------------------------------------------------------------------------------------------------------

def classify(scope, payload_sha256, manifest_sha256, table, registered_checks):
    """A member against the owner's confirmation table (design 6.3) and the rule under it: CONFIRMED (payload and manifest digests are a table row),
    MANIFEST_DIFFERS (the payload is a table row, the manifest is not: the second OpenFIGI manifest, which is evidence only), REGISTERED_CHECK
    (no table row; the payload has a registered check), NOT_CONFIRMED (neither: it needs its own confirmation or registered check before it
    counts). A test scope's members are invented, so the table does not apply (TEST_SCOPE)."""
    if scope.origin_axis != "REAL":
        return TEST_SCOPE
    known = table.get(payload_sha256)
    if known is not None:
        return CONFIRMED if known[0] == manifest_sha256 else MANIFEST_DIFFERS
    return REGISTERED_CHECK if payload_sha256 in registered_checks else NOT_CONFIRMED


def _proposal_records(store, registry, definition):
    try:
        ids = [item["source_id"] for item in json.loads((store.root / "SOURCES.json").read_text(encoding="utf-8"))["sources"]]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise QualificationError("RW_QUAL_REGISTRY", "the source registry file cannot be read: %s" % type(error).__name__) from error
    records = []
    for source_id in sorted(ids):
        record = registry.get(source_id)
        if record.source_priority is not None:
            raise QualificationError("RW_QUAL_PRIORITY", "source %s has a priority, which a proposal record cannot carry" % source_id)
        if record.synthetic != definition.synthetic:
            raise QualificationError("RW_ORIGIN_MIXED", "source %s is %ssynthetic in a scope whose origin is %ssynthetic (I2)"
                                     % (source_id, "" if record.synthetic else "not ", "" if definition.synthetic else "not "))
        check = record.terms_check
        terms = None if check is None else {"checked_by": check.checked_by, "checked_on": check.checked_on.isoformat(),
                                            "permits_internal_development_use": check.permits_internal_development_use, "notes": check.notes}
        records.append(real_proposal.SourceRecord(record.source_id, record.name, record.upstream_provider, record.independence_group,
                                                  record.terms_url, terms))
    return records


def qualify(scope, store, release, adapters, resolver, *, market_conventions, perf_conventions, policy, catalog_calendars, sidecars=(),
            table=HG4_CONFIRMATION_TABLE, registered_checks=frozenset()):
    """Run the qualification over `release` in `store` (a `FileStore`, read directly) and return the `Qualification`.

    `scope` is a `ResolvedScope`. `sidecars` are the sidecar records as BYTES (REAL scope only). `table` is the 6.3 confirmation table
    and `registered_checks` the payload hashes that have a registered check instead (the NYSE calendar, HG2 condition 4).
    Raises `QualificationError`, `real_proposal.ProposalError` or `real_sidecar.SidecarError`; writes and publishes nothing."""
    definition = require_resolved(scope)
    sidecars = tuple(sidecars)
    if definition.origin_axis != "REAL" and sidecars:
        raise QualificationError("RW_O5_SIDECAR_IN_TEST_SCOPE", "a test scope takes no sidecar: O5 is bypassed and an invented attestation is never stored")
    registry = store.load_registry()
    built = build_in_memory_market_data(release, store, registry, adapters, resolver, catalog_calendars=catalog_calendars)
    index = store.index()
    summaries = {s.file_sha256: s for s in built.summaries}

    members, rows = [], []
    for manifest in built.manifests:
        manifest_path = index[manifest.file_sha256]
        manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        summary = summaries[manifest.file_sha256]
        stub = real_proposal.Member(manifest.file_sha256, manifest_sha, manifest.source_id, None, summary.adapter_id, summary.adapter_version)
        data = real_sidecar.sidecar_for(sidecars, stub) if definition.origin_axis == "REAL" else None
        slot = None if data is None else real_sidecar.sidecar_digest(data)
        members.append(real_proposal.Member(manifest.file_sha256, manifest_sha, manifest.source_id, slot, summary.adapter_id, summary.adapter_version))
        confirmation = classify(definition, manifest.file_sha256, manifest_sha, table, registered_checks)
        rows.append(MemberRow(manifest_path.relative_to(store.root / "files").as_posix()[: -len(".manifest.json")], manifest.file_sha256,
                              manifest_sha, manifest.source_id, manifest.data_kind.value, manifest.retrieved_by, manifest.usage_scope.value,
                              confirmation, slot))
    real_sidecar.require_o5(definition, members, sidecars)                      # the REAL scope: every failure of every member, before anything is written

    contents = built.store.export()
    content = dict(
        members=members, source_records=_proposal_records(store, registry, definition),
        release_id=release.release_id, release_digest=release_digest(release),
        projection_digest=projection_digest(release, contents, built.calendars),
        identity_digest=identity_digest(resolver), calendar_digest=calendar_digest(release, contents, built.calendars),
        convention_digest=convention_digest(market_conventions, perf_conventions, release),
        profile_digest=profile_digest(m.source_id for m in members), f8b_policy_digest=dict(policy_reference(policy))["digest"])
    data = real_proposal.write_proposal(scope, **content)
    verified = real_proposal.verify_proposal(data)                                # the exit: the output passes the verifier, or nothing is returned
    if verified.snapshot.content != real_proposal.build_snapshot(scope, **content).content:
        raise QualificationError("RW_QUAL_REVERIFY", "the verified proposal differs from the one built")

    review = []
    if built.issues:
        review.append("%d adapter issue(s)" % len(built.issues))
    if built.exceptions:
        review.append("%d resolution exception(s)" % len(built.exceptions))
    contradicted = [r for r in built.label_results if not r.admitted]
    if contradicted:
        review.append("%d series not admitted by a label test (%s)" % (len(contradicted), ", ".join(sorted({r.test for r in contradicted}))))
    unconfirmed = [r for r in rows if r.confirmation in (MANIFEST_DIFFERS, NOT_CONFIRMED)]
    if unconfirmed:
        review.append("%d member(s) not covered by the confirmation table or a registered check" % len(unconfirmed))
    listed = {r.payload_sha256 for r in rows}
    return Qualification(data, verified.snapshot.context_id, definition.name, release, built, tuple(members), tuple(rows),
                         tuple(sorted(sha for sha in table if sha not in listed)) if definition.origin_axis == "REAL" else (),
                         definition.origin_axis != "REAL", bool(review), tuple(review))


def save_proposal(path, qualification):
    """Write the proposal bytes to a NEW file (exclusive create: an existing file is never overwritten). The only write of this module."""
    if type(qualification) is not Qualification:
        raise QualificationError("RW_QUAL_SHAPE", "a Qualification is required")
    with open(Path(path), "xb") as handle:
        handle.write(qualification.proposal)


def load_qualified(conn, qualification, *, exchange_of):
    """Project the qualified release into a database as the loader role: `real_loader.load_release` (the listing-level admission gate runs
    first, `count_rows=False`). `exchange_of` is the identity's exchange MIC lookup and is required. The caller's connection is the
    loader's; this function opens none and sends no statement of its own."""
    return real_loader.load_release(conn, qualification.release, qualification.built.manifests, qualification.built.store.export(),
                                    qualification.built.calendars, exchange_of=exchange_of)
