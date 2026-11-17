# E11 additive truthful acquisition metadata

2026-10-19. Engineer `/root/cp7e10_adapter_author`. Exactly four new project paths:
`src/marketdata/acquisition.py`, `src/marketdata/manifest_v2.py`,
`tests/product/test_marketdata_acquisition_v2.py` and this plan. Existing v1 readers,
manifest bytes, adapters, registries, fixtures, storage, SQL, financial methods,
dependencies, routes and sealed evidence remain untouched. No real body or runtime
input is accessed; all tests use invented in-memory metadata. No new acquisition,
admission, personal access, HG4 or night activity is authorized by this implementation.

## Frozen metadata API

`AcquisitionEnvelope.from_bytes/to_bytes/to_obj/sha256` and
`FileManifestV2.from_bytes/to_bytes/to_obj/sha256` retain validated canonical immutable
bytes. `to_obj` returns a fresh caller-owned tree; no nested mutable object is retained.
Accepted bytes must be exact UTF-8, sorted keys, two-space indent, ensure_ascii=False,
LF trailing newline and no BOM. Digests are of those original accepted bytes. Non-NFC
strings and Unicode Cc/Cf/Cs controls are rejected, never normalized. This is a new
opt-in policy, not a change to legacy parsing or serialization.

Both metadata parsers bound 65,536 bytes, depth 8, decoded string token 4,096 UTF-8
bytes and 4,096 strings/primitives (keys included), before full JSON tree construction.
Metadata numbers are integer literals only, at most 19 lexical characters; typed
numeric fields disallow bool/coercion and enforce nonnegative signed-64-bit bounds.
Duplicate/unknown/missing keys, floating point/exponent/nonfinite literals, malformed
UTF-8, surrogates and noncanonical JSON refuse. Errors expose only an internal typed
code, never echoed input. No new installed HTTP vocabulary exists.

Envelope fields follow the adopted E10 proposal exactly. Agent execution, human scope
approval and human TermsCheck remain distinct. Tool version/hash and exact canonical
UTC-seconds retrieval time are mandatory. Only COMPLETE/200/ordinal1/max1 is represented;
failed/unknown evaluations cannot be converted to completion. Public parameters are
ordered unique pairs, at most 32, restricted to from/to/fmt/symbol/exchange/function,
with bounded public scalar values; no token/header/email/URL field. Evidence requires
all four roles in this exact order: APPROVAL_PACKET, REQUEST_SPEC, EXECUTION_METADATA,
EXECUTION_REVIEW. Each artifact digest retains its own meaning: role names do not
force unrelated packet, decision, full request, worker metadata or outer receipt
digests equal. Visibility records restrictions and never grants derived/model rights.
Fixed field syntax reduces accidental exposure; it is not general DLP for arbitrary
opaque identifier values. No environment/Keychain lookup or credentials are used.
Independent static V1 finding (not an executed RED): the HTTP-path grammar also
accepted local-looking paths. V2 rejects case-insensitive first segments
users/private/tmp/var/etc/volumes/home/root and any exact .local component, including
root-only forms, without normalizing stored bytes. Ordinary /api resource paths stay
valid. All four V1 files and narrow diffs remain preserved in the author evidence.

V2 retains exact v1 field meanings, requires retrieved_by=agent and
INTERNAL_DEVELOPMENT_ONLY, and adds only an acquisition reference. Script identity,
source, ordered request projection, payload hash/size and retrieval instant must agree
with the envelope. Numeric/source/action semantics and rights are not inferred.
`read_manifest_metadata` is the only new opt-in dispatcher: v1 delegates to the unchanged
legacy class after the new strict gate, v2 returns a v2 object, unknown refuses. It is
intentionally narrower than old from_json; not every legacy-accepted byte string
roundtrips through this new API. It never converts agent provenance into human or
synthetic v1 provenance and performs no filesystem discovery or storage operation.

## Integrity boundary

`EnvelopeIndex` is a frozen tuple of at most 16 unique (digest, bounded bytes) entries.
Only the exact selected digest is hashed/parsed; unavailable or inconsistent input
refuses, with no locator, fallback, file or raw-body read. Unselected metadata is not
parsed. It is not a real storage loader or promotion authority.

`TrustedAcquisitionWitness` is independently supplied typed server/operator expectation
input: expected whole manifest/envelope digests, actual agent/role and the approved
full request fingerprint. It is never parsed from caller JSON. Public Python
construction is not cryptographic identity or proof of current authority; invented
fixtures stand in for a future separately reviewed trusted runtime boundary.
`verify_acquisition_binding(manifest,index,witness)` compares those independent pins
and each relevant manifest/envelope cross-field. The full envelope pin binds the
approval, attempt, evidence, provider/product/host/path and ordered public projection;
the full approved fingerprint is not recomputed from that reduced projection.
Even success returns only INTEGRITY_BOUND_NOT_ADMITTED with promotable=false, never
rights, current qualification, actor authentication, source admission or execution
capability. A caller can construct trusted Python objects only within the stated
trusted-operator premise; this API is not a hostile-code security boundary.

## Validation and remaining work

Independent 22 literal oracles were frozen before implementation. The author fixed
test module covers canonical/immutable metadata, strict shape/bounds before tree,
human/agent separation, truthful old v1 behavior, exact index, all swapped artifact
and cross-field bindings, witness/default refusal and lack of authority claims.
No source bodies or files are fixtures. Existing dependencies only; guarded pinned
source loading, bytecode off, root grant and independent runner review precede imports.
At initial static freeze runtime tests are NOT_RUN; actual logs/results are separate.

E7/E8 promotability stays UNKNOWN: no body, timestamp or missing tool-version witness
was reinterpreted. Real v2 stores/loaders, payload collision handling, many-acquisition
identity, archives/compute/reproduce linkage, migrations and exact byte storage are
not implemented here. F1 synthetic transaction validation starts only after this
increment's independent acceptance; F1 remains NOT_CLOSED and real UAT NOT_READY_NOT_RUN.
