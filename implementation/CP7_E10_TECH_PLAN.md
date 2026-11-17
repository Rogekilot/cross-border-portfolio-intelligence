# CP7-E10 fictional split compatibility — technical plan

2026-10-19; implementation author `/root/cp7e10_adapter_author`. Scope is exactly one
new pure adapter, one new fixed test module, and this plan. No existing source, test,
financial method, registry/profile, fixture, migration, dependency or old evidence is
changed. Root PM owns authority, execution GO and acceptance; a different agent owns
the independent review. This file does not authorize source admission or real UAT.

## Contract

`marketdata.adapters.eodhd_split_candidate.EodhdSplitCandidateAdapter()` implements
`SourceAdapter.translate(FileManifest, bytes) -> AdapterOutput`. There is no configurable
constructor or caller-provided classification authority. The module declares
`REAL_CLASSIFICATION_BINDING = None`.

Only the invented source `fictional.eodhd_split_candidate`, format
`fictional_eodhd_split_rows/1`, vendor id `FICTITIOUS.SPLIT.001`, synthetic retrieval,
`UsageScope.SYNTHETIC_TEST`, exact invented product/version/function/input-contract,
semantic-rule/evidence and adapter-version request tuple, fixed fixture script recipe,
coverage (2001), filename, retrieval instant and undeclared market/currency can reach
the body parser. Evidence hashes attest only the documented invented recipes in code;
they do not attest a real provider. File SHA and size must match the supplied bytes.

Wrong source or absent/conflicting semantic binding returns `UNMAPPED_ACTION`; wrong
synthetic/input contract returns `CONTRACT_VIOLATION`. These checks run before the body
is inspected. Copying the fixture constants cannot grant real semantics: non-synthetic
scope, human retrieval, a real source/vendor identity or any extra caller flag refuses.
This is a code-level fictional contract, not a cryptographic trust boundary against
modifying the trusted Python program.

Rows are invented `{date, split}` objects. `date` must be a canonical, valid ISO calendar
date within the fixed fictional coverage. `split` is lexical `new/old`, each positive,
unsigned fixed-point component having at most 18 integer digits and 12 fraction digits.
Components go directly to `Decimal` and `SplitRatio`; no division, floating point,
quantization, scale normalization or rounding occurs. Forward and reverse direction and
lexical text remain intact. Ordinary SPLIT comes only from the frozen fictional
semantic contract, never the ratio, a known-event match, endpoint or self-reported type.

Only actions/issues can be emitted. Identifiers contain solely the explicit fictional
vendor id and source namespace: no ticker, MIC, currency, listing, FIGI, pay date or
record date is inferred. Existing `lineage_for` and `timing_for` retain manifest hash,
retrieval, synthetic scope, adapter id/version, row reference and lexical ratio.
`AdapterRegistry` remains unchanged and empty by default; an explicitly constructed
private registry can select only this fictional key. Nothing appends a ledger event.

## Parsing and failure policy

Limits: 65,536 body bytes; JSON nesting depth 8; decoded UTF-8 string/numeric literal
4,096 bytes; 4,096 strings/primitives (keys included); 128 rows. Body bytes are bound
before decoding. A lexical walk uses the stdlib JSON string scanner for one decoded
string at a time, and bounds decoded UTF-8 string/numeric tokens, primitive count and
nesting before `json.loads` constructs the object tree. The same post-tree token check
remains as a second check. A sentinel constructor test proves over-limit inputs stop
before tree construction and exact-limit inputs can reach it.
Strict UTF-8/JSON refuses BOM, malformed/trailing values, duplicate object keys,
nonfinite literals, exponent numbers and escaped surrogates. Unknown row fields,
noncanonical/invalid/out-of-coverage dates, ratio syntax/bounds and nonpositive values
receive existing typed issues, with bounded static details rather than echoed inputs.

A file-level grammar/bound/manifest failure refuses the whole body. Otherwise every
row produces one action or one issue. Duplicate canonical date labels are identified
before ratio validation, and every row for that label is refused (even when one ratio
is malformed); no arbitrary winner. Other valid rows remain and all row refs preserve
original array indices. Invalid dates never acquire an effective date.

## Validation freeze and execution

The author module contains six explicit E9 classification oracles plus strict parsing,
byte/digest, numeric precision, direction/scale, row accounting, default registry,
lineage and unchanged mock-adapter compatibility checks. All bodies and expected values
are invented locally; no E7/E8 raw response or source data is read. Independent literal
oracles were frozen by a different reviewer before this implementation.

Before any project import or test, root must approve exact source/test/runner hashes
and the independent guard review. Author scratch is confined to
`/tmp/finweb-cp7e10-20261019/author`. The runner installs the unchanged E8 offline
network/process guard and a reviewed path/audit guard before loading the fixed test
module. No network, fork, runtime, PostgreSQL, browser, source-data read, arbitrary file
read or write outside that leaf is needed. Bytecode stays disabled. The guard is a
cooperative Python control, not OS/native isolation. Only fixed explicit test targets
are permitted; no broad discovery or legacy-data traversal.

At initial static freeze, runtime tests are **NOT_RUN**. Actual results, any failures,
repair diffs and final hashes are recorded separately after root execution GO; this
document is not a claim that tests passed. Independent static V1 finding (not an executed
RED): token/primitive bounds initially followed tree construction. All three V1 file
preimages are preserved in the assigned scratch `v1-static` folder; V2 corrects that
precedence and adds the constructor-sentinel cases. Existing source preservation and independent
review/PM acceptance are separate checks. Real-source classification, executor-manifest
compatibility, provider rights/identity/coverage, immutable context and F1 remain open.
