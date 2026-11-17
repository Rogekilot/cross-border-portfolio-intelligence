# CP7-F2 fixed local fictional service adapter

Static V2 correction F2S03 preserves the actual performance refusal's empty
`detection_policy`: refusal precedes policy evaluation in the unchanged service.
The CP5 positive path still requires the exact nonempty policy reference. The
original V1 three files remain byte-exact in `service-component-v1`; no test was
executed to discover this static finding or to verify this correction yet.

Static V3 completes that actual early-refusal contract: historical performance
records `release_id=null` and empty `data_set_refs`, because it has not consumed
a valuation release. The adapter validates those exact original facts instead of
inventing a consumed release; CP5 positive release equality and SHA checks remain
strict. V2 three-file preimages/diff are preserved in the service-author leaf.

Author `/root/cp7e10_adapter_author`; 2026-10-20 Asia/Shanghai. Exact three new
product files only: src/financial_service_integration.py,
tests/product/test_financial_service_integration.py and this plan. Root EDIT GO is
reviews/CP7_F2_EVIDENCE/pm/IMPLEMENTATION_EDIT_RELEASE_V1.json. No financial methods,
old defaults/source/migrations/CHECKSUMS/data/fixtures/dependencies/routes change.
Imports/tests/PG require separate frozen runner review and root GO; currently NOT_RUN.

## Service and source binding

The core owns current rights/lease,owner-root-op scope,actual outer transaction,
archive storage,RLS/fences and known commit/whole rollback. The new adapter opens
and commits no connection. Fixed enum CP5_DIVERSIFICATION invokes the existing
compute_diversification_for_portfolio on the same supplied connection with explicit
allow_synthetic=True. PERFORMANCE_SYNTHETIC_REFUSAL invokes the actual unchanged
performance service and raises LocalServiceRefusal with original issued typed
no-number canonical bytes. Only core,after confirmed whole rollback,may emit
economic_writes0 diagnostics. Performance positive remains BLOCKED.

Shared API: fingerprint_context_inputs(**actual_typed_inputs)->canonical bytes;
LocalFictionalContext binds actual conn/backend/xid plus context hash,generation,
locked snapshot bytes and actual objects; LocalServiceRequest binds exact
owner/root/revision/op/portfolio/staged pin/asof/context/generation/None account/USD.
Root equals portfolio. Snapshot hash excludes itself,live conn/backend/xid and
generation; those are separately bound by the core lease. Public Python construction
is trusted operator input,not cryptographic actor/current-rights or hostile-code proof.

Actual port export AND live indexed state,full source records,release,resolver
snapshot/identifier rows/all canonical-listing lookup answers,calendar indexes and
definitions,concrete convention rules/state,policy,metadata/candidate policy and
request/frequency/asof/currency are canonically fingerprinted before and after
actual dispatch. Supplied snapshot bytes must match exact actual content,not a
caller-stated UUID/digest alone. The port's known rank lambda is represented by its
fixed-module/qualname/code/constants/closure state without executing it; the bound
exchange lookup must belong to the exact resolver. Unsupported objects,unknown
lineage/markers,non-SYNTHETIC_TEST sources and mixed data refuse. Minimal local
scope is USD quote-only<=128 observations,<=16 listings/sources,<=8 calendars,no
FX/adjusted/benchmark/risk-free/action/exclusion data,explicit FULL_NAV typed policy.
Unchanged conventions and metadata are inputs,not financial method changes.

Typed CP5 result and actual source/policy/root/pin/asof/currency/F8B manifest fields
are checked. Native manifest ID,native result digest and SHA of complete issued
canonical bytes remain distinct. Generated issued bytes<=2000000,binding/question
<=32768,snapshot<=262144; recursive semantic state depth<=16,container<=4096,
strings<=8192. Whole output refuses at bound; no truncation or float roundtrip.
No permissive Result-from-JSON reader or arbitrary caller service callback exists.

Plain archive READ and exact committed create retry return stored bytes after
core integrity/current-purpose rights checks and NEVER issue a service call.
Explicit EXECUTE_REPRODUCE alone may invoke reproduce_local_service: verify stored
whole-byte hash/bounds,reissue actual fixed service under original pinned context,
then compare COMPLETE canonical bytes. This does not update old archive bytes.

## Tests and actual validation status

Twelve fixed service unit methods use only NEW inline invented price10/qty2 plus
cash20: fullNAV40,weights1/2 each,largest security1/2,HHI1/2,effective positions2,
top5=1. These literal arithmetic oracles come from the existing contract,not runtime
outputs. They are UNIT_ONLY; actual writer integration uses its SAME actualWorld
SYN-A100 port/resolver/calendar and independently frozen integration expectations.
Every market/lineage/source/result synthetic flag remains true. Country/sector
UNKNOWN and one-date insufficient history stay genuine. Unit connection is a
read-only SQL fake; it is not claimed as actual PG writer integration.

Tests cover actual CP5 dispatch,unchanged default refusal,actual performance
no-number refusal,conn/xid/scope/strict-type and source-index mutations,unknown
synthetic rejection,complete reproduction,whole-output bound and distinct hashes.
No fake financial success callback or relabelled market is used. The separate
core PG suite and independent16 target must prove real same-connection/backend/xid,
whole actual ledger/revision/CSV/archive/op commit/rollback,current purpose,RLS
and old writer denial,exact no-compute retry/read and root-owned restart durability.

Static drafting found live port indexes needed their own fingerprint beyond
export,including constructor rank-closure state; code includes both before first
freeze. This was source reasoning,not an executed test RED. Only AST parsing has
run. Runtime preparation is separate three scratch operators under
/private/tmp/finweb-cp7f2-20261019/service-author/runtime-operator; exact code/input/
dependency/public-OS pins and full guarded eager-import preflight must be reviewed
before any import/test/PG. Root alone provisions/restarts/stops fresh F2 PG; no old
runtime control. Native warnings/failures are retained; Python guards are not an
OS/native isolation claim. F1 stays NOT_CLOSED,D3 NOT_QUALIFIED,real UAT not ready;
E11 integrity binding does not grant financial rights or real source admission.
