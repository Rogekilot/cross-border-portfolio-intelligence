"""Pure fixtures of the F1 real-gateway tests (R1). Not a test module.

Everything here is INVENTED and synthetic: source ids start with `syn.`, hashes are SHA-256 of a test tag, no value comes from a
real file, source or licence. Nothing here opens a connection. Snapshots are NOT built here: the product factory builds them
(`persistence.real_scope.make_snapshot` for a database, `persistence.real_proposal.build_snapshot` with a `ScopeDef` in memory);
this module only supplies the content keywords they take, the decision-reference values and the expiry evidence shapes.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from persistence.real_proposal import Member, SourceRecord  # noqa: E402
from persistence.real_workspace_store import BasisEntry, DecisionRef, RIGHTS  # noqa: E402

SOURCES = ("syn.alpha", "syn.beta", "syn.cal")
REF = DecisionRef("PD-9001", "a" * 40, "b" * 64)
REF_OTHER = DecisionRef("PD-9002", "c" * 40, "d" * 64)
ACTOR = "invented-owner"
ALL_RIGHTS = {k: True for k in RIGHTS}
FAR = dt.datetime(2099, 1, 1, tzinfo=dt.timezone.utc)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content(tag, *, sources=SOURCES, unused_sources=()):
    """The keyword set of `build_snapshot` for invented members, one member per source. `tag` makes every digest unique to a test,
    so two tests never publish the same context. `unused_sources` adds source records that no member uses (so the full-registry and
    used-source digests differ)."""
    members = [Member(payload_sha256=sha(tag + "/payload/" + s), manifest_sha256=sha(tag + "/manifest/" + s), source_id=s,
                      acquisition_record_sha256=None, adapter_id="syn.adapter." + s, adapter_version="1") for s in sources]
    records = [SourceRecord(s, "Invented source " + s, "invented-provider", "group-" + s, "", None)
               for s in tuple(sources) + tuple(unused_sources)]
    return dict(members=members, source_records=records, release_id=sha(tag + "/release"), release_digest=sha(tag + "/release-digest"),
                projection_digest=sha(tag + "/projection"), identity_digest=sha(tag + "/identity"), calendar_digest=sha(tag + "/calendar"),
                convention_digest=sha(tag + "/convention"), profile_digest=sha(tag + "/profile"), f8b_policy_digest=sha(tag + "/f8b"))


def hg4_shape(bound, *, sources=SOURCES, ref=REF):
    """One LEASE_TERM and the rest NOT_ASSESSED: the shape of the HG4 entries, on invented sources. A fixture shape, not a margin."""
    return [BasisEntry(sources[0], "LEASE_TERM", ref, bound)] + [BasisEntry(s, "NOT_ASSESSED", ref) for s in sources[1:]]


def none_shape(*, sources=SOURCES, ref=REF):
    return [BasisEntry(s, "NO_EXPIRY_READING", ref) for s in sources]


def entry_json(source_id, basis, *, ref=REF, bound=None):
    """A basis entry as stored JSON, for crafted rows only."""
    out = {"source_id": source_id, "basis": basis, "pd_id": ref.pd_id, "git_commit": ref.git_commit, "doc_sha256": ref.doc_sha256}
    if bound is not None:
        out["term_end_not_after"] = bound.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def seconds(n):
    return dt.timedelta(seconds=n)
