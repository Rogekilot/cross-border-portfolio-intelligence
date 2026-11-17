"""F1 R8 tooling: the INPUTS of the real qualification run, in code (a library of `real_tools`; not a program, and never imported by product code).

`qualification.qualify` takes a store, a release, adapters, an identity resolver, conventions, a policy and (REAL scope) the sidecars. The two R8
command-line tools (`qualify_run`, offline; `loader_window`, the loader's window tool) must build the SAME qualification from the SAME inputs, because
the loader tool loads only the release whose proposal the owner reviewed: it rebuilds the qualification here and refuses unless its proposal bytes
equal the reviewed file (`RW_LOADER_PROPOSAL_DIFFERS`). Both therefore call `rebuild_real`, and nothing else in the tools builds a world.

What is fixed in code here, and where it comes from (each is an ENGINEER'S choice that no approved document names; listed for the PM in the report):

  * the adapters: the five real adapters of `performance_tools.real_slice` plus the OpenFIGI identity adapter (the HG4 release holds a quote file, an
    identity file and a calendar; the FX adapters are registered so a later release needs no change here);
  * the identity: `REAL_INSTRUMENTS`, the same one instrument (AAPL on XNAS, USD) that `real_slice.REAL_INSTRUMENTS` registers (a copy: the
    demonstration module can change without moving the real identity), with listing ids `uuid5(IDENTITY_NAMESPACE, "real-identity-N")` in registration order;
  * the F8B policy: option B of PD-0072, the one `test_real_qualification.POLICY` and `real_slice` already use (no corporate-action source is admitted);
  * `catalog_calendars = {}`: the release has no benchmark;
  * the market conventions are `market11_conventions` over the calendars of a first build of the release, the way every existing caller does it.

Nothing is read but the store's own files (through `FileStore`), the sidecar files and the proposal file named on the command line. Nothing is written.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json
import re
from pathlib import Path

from marketdata.adapters.alphavantage import AlphaVantageQuoteAdapter
from marketdata.adapters.base import AdapterRegistry
from marketdata.adapters.calendar_file import CalendarFileAdapter
from marketdata.adapters.ecb_eurofxref import EcbEurofxrefFxAdapter
from marketdata.adapters.frankfurter import FrankfurterFxAdapter
from marketdata.adapters.openfigi import OpenFigiIdentityAdapter
from marketdata.files import FileStore
from marketdata.ingest import build_in_memory_market_data
from marketdata.manifest import FileManifest, MarketDataRelease
from marketdata.market11 import market11_conventions
from marketdata.profiles import ProfileNotAdmittedError
from performance.engine import performance_conventions
from persistence import market_data_store as mds, real_loader, real_proposal
from persistence.real_scope import resolve_scope
from persistence.real_workspace_context import RealWorkspaceError
from persistence.real_workspace_store import BasisEntry, DecisionRef, evidence_json
from real_service.real_identity import IDENTITY_NAMESPACE, REAL_INSTRUMENTS, REAL_POLICY, real_resolver  # noqa: F401  (one definition, shared with the launcher)
from real_tools import candidates as cand, qualification as q

_HASH = re.compile(r"[0-9a-f]{64}\Z")


class InputError(ValueError):
    def __init__(self, code, detail="The inputs are refused"):
        self.code = code
        super().__init__("%s: %s" % (code, detail))


#: What the tools treat as a refusal of the INPUTS (raised before any connection): every coded refusal of the proposal, sidecar, qualification, candidate and
#: scope modules is a `ValueError`; a store with a missing file or source is a `LookupError`; an identifier is a `RealWorkspaceError`.
INPUT_REFUSALS = (ValueError, LookupError, RealWorkspaceError)
#: What the loader's `load` step treats as a definite refusal: the loader entry's own, the market-data store's typed errors (raised before a write or
#: inside the one transaction, which rolls back), the source-admission refusal and any plain `ValueError`.
LOAD_REFUSALS = (real_loader.RealLoaderError, mds.MarketDataStoreError, ProfileNotAdmittedError, ValueError)


@dataclass(frozen=True)
class Rebuilt:
    """What both tools work from: the resolved scope, the store (read-only), the qualification and the identity resolver the qualification used."""
    scope: object
    store: object
    qualification: object
    resolver: object


def real_adapters():
    return AdapterRegistry([AlphaVantageQuoteAdapter(), OpenFigiIdentityAdapter(), CalendarFileAdapter(), FrankfurterFxAdapter(), EcbEurofxrefFxAdapter()])


def _hashes(values, what):
    values = list(values)
    for value in values:
        if type(value) is not str or _HASH.fullmatch(value) is None:
            raise InputError("RW_INPUT_HASH", "%s must be a lower-case SHA-256 hex digest" % what)
    if len(set(values)) != len(values):
        raise InputError("RW_INPUT_DUPLICATE", "%s names a hash twice" % what)
    return values


def cut_release(store, release_name, file_shas):
    """The release of exactly `file_shas` (payload hashes), cut by the engine's own `from_manifests` (it refuses two vintages of one series)."""
    shas = _hashes(file_shas, "--file")
    if not shas:
        raise InputError("RW_INPUT_NO_FILE", "a release names at least one file")
    if type(release_name) is not str or not release_name.strip():
        raise InputError("RW_INPUT_NAME", "a release has a name")
    index = store.index()
    absent = sorted(s for s in shas if s not in index)
    if absent:
        raise InputError("RW_INPUT_FILE_MISSING", "the store holds no file %s" % ", ".join(s[:12] for s in absent))
    manifests = [FileManifest.from_json(index[s].read_text(encoding="utf-8")) for s in sorted(shas)]
    return MarketDataRelease.from_manifests(release_name, manifests, [])


def read_bytes_files(paths, what):
    """The bytes of each file named on the command line, in the order named. An unreadable file is a refusal, never skipped."""
    out = []
    for path in paths:
        try:
            out.append(Path(path).read_bytes())
        except OSError as error:
            raise InputError("RW_INPUT_UNREADABLE", "%s %s cannot be read (%s)" % (what, path, type(error).__name__)) from error
    return out


def require_new_files(paths):
    """Refuse before anything is built if an output path already exists or is named twice: an output is never overwritten."""
    paths = [str(p) for p in paths]
    if len(set(paths)) != len(paths):
        raise InputError("RW_INPUT_OUTPUT_TWICE", "two outputs name the same file")
    for path in paths:
        if Path(path).exists():
            raise InputError("RW_INPUT_OUTPUT_EXISTS", "%s already exists and is never overwritten" % path)


def write_new_file(path, data, *, mode=None):
    """Write `data` to a NEW file (exclusive create; an existing file is never overwritten). The seed file's write; the proposal's is `qualification.save_proposal`.
    With `mode` (the contexts file: 0o600) the file is created with that mode FIRST, by `Path.touch(mode=..., exist_ok=False)`, and only then written."""
    target = Path(path)
    if mode is not None:
        target.touch(mode=mode, exist_ok=False)
        with open(target, "wb") as handle:
            handle.write(data)
        return
    with open(target, "xb") as handle:
        handle.write(data)


#: PD-0068 answer 4: one expiry-evidence entry per member source of the HG4 release. `LEASE_TERM` for `alphavantage.us` with the latest instant its current term can
#: end, `NOT_ASSESSED` for the other two.
EVIDENCE_LEASE_TERM = ("alphavantage.us", dt.datetime(2027, 10, 1, tzinfo=dt.timezone.utc))
EVIDENCE_NOT_ASSESSED = ("calendar.manual", "openfigi")
CONTEXTS_SCHEMA = "finweb.real_mode_contexts/1"


def evidence_document(refs):
    """The bytes of the publish's expiry-evidence file `E`: a JSON list of three entries, EACH citing its own decision. `refs` maps each of the three source ids
    (`EVIDENCE_LEASE_TERM[0]` and `EVIDENCE_NOT_ASSESSED`) to a `(pd_id, git_commit, doc_sha256)` triple; a missing or extra source, or a malformed triple, is a
    `RealWorkspaceError`. Pure."""
    sources = (EVIDENCE_LEASE_TERM[0],) + EVIDENCE_NOT_ASSESSED
    if type(refs) is not dict or sorted(refs) != sorted(sources):
        raise InputError("RW_INPUT_EVIDENCE", "one decision triple for each of %s" % ", ".join(sources))
    ref = {s: DecisionRef(*refs[s]) for s in sources}
    entries = [BasisEntry(EVIDENCE_LEASE_TERM[0], "LEASE_TERM", ref[EVIDENCE_LEASE_TERM[0]], EVIDENCE_LEASE_TERM[1])] + \
              [BasisEntry(s, "NOT_ASSESSED", ref[s]) for s in EVIDENCE_NOT_ASSESSED]
    return (json.dumps(evidence_json(entries), indent=2, sort_keys=True) + "\n").encode("utf-8")


def contexts_document(rebuilt, generation):
    """The bytes of the launcher's contexts file `C` for the context of `rebuilt.qualification`, at `generation` (the number the publish printed): the BOUND
    candidate's context digest and its members, with no witness (v1 manifests carry none). Pure."""
    if type(generation) is not int or isinstance(generation, bool) or generation < 1:
        raise InputError("RW_INPUT_GENERATION", "the generation is the integer the publish printed, at least 1")
    context_id = rebuilt.qualification.context_id
    bound = cand.build_candidate(rebuilt.scope, rebuilt.store, rebuilt.qualification, financial_context=context_id)
    document = {"schema": CONTEXTS_SCHEMA, "contexts": [{"context_id": context_id, "generation": generation, "provenance": {
        "context_sha256": bound.context_sha256, "members": [m.to_obj() for m in bound.members], "witnesses": []}}]}
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_proposal(path):
    """The bytes of the proposal file the owner reviewed, verified as a proposal (a `real_proposal.ProposalError` otherwise). Returns (bytes, `VerifiedProposal`)."""
    (data,) = read_bytes_files([path], "the proposal")
    return data, real_proposal.verify_proposal(data)


def proposal_projection_digest(proposal):
    """The `projection_digest` of a VERIFIED proposal's snapshot (what `md_release` must hold once the release is loaded)."""
    return real_proposal.verify_proposal(proposal).snapshot.content["projection_digest"]


def rebuild_real(args):
    """The REAL-scope qualification of `args.release_name` over `args.file` in `args.store_root`, with the sidecars `args.sidecar` and the registered
    checks `args.registered_check`. Returns `Rebuilt`. Reads the store and the sidecar files; writes and publishes nothing; opens no connection."""
    scope = resolve_scope("REAL")
    store = FileStore(Path(args.store_root))
    release = cut_release(store, args.release_name, args.file)
    sidecars = read_bytes_files(args.sidecar or (), "a sidecar")
    registered = frozenset(_hashes(args.registered_check or (), "--registered-check"))
    adapters = real_adapters()
    first = build_in_memory_market_data(release, store, store.load_registry(), adapters, real_resolver(), catalog_calendars={})
    resolver = real_resolver()
    qualification = q.qualify(scope, store, release, adapters, resolver, market_conventions=market11_conventions(first.calendars),
                              perf_conventions=performance_conventions(), policy=REAL_POLICY, catalog_calendars={}, sidecars=sidecars,
                              registered_checks=registered)
    return Rebuilt(scope, store, qualification, resolver)
