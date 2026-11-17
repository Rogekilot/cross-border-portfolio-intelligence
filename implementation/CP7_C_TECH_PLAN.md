# CP7-C CSV API and persistence contract

Authority: PD-0045 and reviews/CP7_C_VALIDATION_PLAN.md. B2 is accepted; existing
methods/engines/domain/catalogs/raw fixtures and18 SQL migrations remain frozen.
Use only Python standard library and installed dependencies. Current execution
is synthetic-only; no personal real file, data admission or external service.

## HTTP contract v1

Every route is under `/api/v1/portfolios/{portfolio_id}` and owner-scoped.
All POSTs require existing Origin+CSRF/session authorization before source work.
JSON schema_version is `finweb.cp7/1`. CSV text never appears in a URL or log.

`POST /imports/parse` takes `{file_base64,filename,delimiter,synthetic_acknowledged:true}`.
Delimiter is explicitly comma,semicolon or TAB; the first record is the header.
Return `{schema_version,portfolio_id,file_sha256,byte_count,bom,columns,rows,limits}`.
Columns are `{index,header}`; duplicate/blank headers remain explicit indexed
columns. Parsed rows are `{row_number,physical_start,physical_end,cells}`; row_number
counts logical data records beginning1; physical spans include the header offset.
Raw bytes must be strict canonical base64, at most16384 bytes and strict UTF-8.
Initial UTF-8 BOM is retained in byte provenance and removed only for parsing.
No File.text normalization is used. The complete JSON request remains <=32768 bytes.

`POST /imports/preview` takes ImportProposal:

```
{
 operation_id: UUID, expected_revision_id: UUID,
 file_base64: string, filename: string,
 kind: "HOLDINGS" | "TRANSACTIONS", as_of: ISO_DATE,
 source_namespace: string,
 source_account_key: string | null, snapshot_key: string | null,
 new_account_name: string | null,
 mapping: {canonical_field: zero_based_column_index},
 constants: {canonical_field: string},
 corrections: [{row_number: integer, fields:{canonical_field:string}, reason:string}],
 classifications: [{row_number:integer, classification:"NON_DATA"|"OUT_OF_SCOPE",reason:string}],
 format: {delimiter:","|";"|"\t", date_format:"ISO"|"DMY"|"MDY",
          decimal_separator:"."|",", thousands_separator:null|","|"."|" "},
 synthetic_acknowledged:true
}
```

Mapping uses column indexes, not header names. Constants fill only unmapped
fields; corrections override explicitly and retain original cells/reasons. No
duplicate correction/classification rows, undefined row references or unknown
canonical fields are accepted. All source keys/names/reasons are visible bounded
strings. Filename is provenance text only, never a filesystem path or response
header. Missing required business fields become row issues, not implicit defaults.

Canonical fields: source_row_key, account_id, account_name, event_type, event_date,
currency, listing_id, symbol, mic, quantity, amount, cost_basis, bought_amount,
bought_currency, split_new, split_old, counterparty_account_id, settlement_date,
ex_date and acquired_on. HOLDINGS uses explicit event_type OPENING_POSITION or
OPENING_CASH, or row kind POSITION/CASH mapped as event_type. It requires a new
account name plus stable source_account_key and snapshot_key and an explicit
2026-01-02 event_date. TRANSACTIONS names owned existing accounts. No inferred
event direction, currency, account, date, ticker or average-cost conversion.

Preview returns `{schema_version,portfolio_id,proposal_digest,preview_receipt,
report,financial_preview}`. Report shape:

```
{
 schema:"finweb.csv_import/1", report_id:UUID, portfolio_id:UUID,
 operation_id:UUID, expected_revision_id:UUID, proposal_digest:SHA256,
 persisted:false|true, status:"READY"|"QUARANTINED"|"BATCH_REFUSED"|
   "COMMITTED"|"REPORT_ONLY"|"ALREADY_IMPORTED",
 file:{filename,sha256,byte_count,bom}, proposal:ImportProposal,
 parser:{version:"csv/cp7-1",dialect:"stdlib-explicit-v1"},
 rows:[{row_number,physical_start,physical_end,cells,classification,reason,
   fields,errors:[{code,field,detail}],event:null|LedgerInput,
   source_identity:null|array,source_key:null|SHA256,
   existing_event_id:null|UUID,disposition:"READY"|"QUARANTINED"|
     "EXCLUDED"|"ALREADY_IMPORTED",event_id:null|UUID}],
 counts:{total,economic,ready,quarantined,excluded,already_imported,imported},
 batch_errors:[{code,detail}], revision_id:null|UUID, created_at:null|UTC_TEXT
}
```

`financial_preview` is null or B2 `{preview:true,workspace,snapshot}` with
persisted:false/PREVIEW_NOT_SAVED. It cannot enter committed proof UI. Any unresolved
economic row or complete-batch rule refusal prevents all financial writes. Preview
itself persists no report/account/ledger/revision/source key. Its receipt is HMAC
over owner,portfolio,operation,head and the canonical proposal digest, using a
process-memory key. It excludes rollback-only sequence numbers. Restart requires
repreview. Changed source/configuration/corrections/head invalidates confirmation.

`POST /imports/commit` takes `{proposal:ImportProposal,preview_receipt:string}`.
Return `{schema_version,portfolio_id,report,workspace_result:null|{workspace,snapshot}}`.
Commit revalidates the proposal under the same owned head lock. Any unresolved
economic row or batch refusal saves REPORT_ONLY with imported0, no account or
revision/source key. Explicit nondata/out-of-scope rows retain classification and
reason. All intended facts that are already recorded yield ALREADY_IMPORTED, no
new account/revision. Successful facts yield COMMITTED and one APPEND revision.
Operation idempotency includes zero-import reports: same operation/content returns
its saved report/result even after later heads; changed content409.

`GET /imports[?cursor=opaque]` returns `{schema_version,portfolio_id,reports:[{report_id,status,
created_at,kind,file_sha256,counts,revision_id}],next_cursor:null|string}` newest first,
in fixed32-report pages. The signed cursor binds owner/portfolio and ordering keys;
server restart invalidates cursors with422 CSV_REPORT_CURSOR and requires refresh.
`GET /imports/{report_id}` returns `{schema_version,portfolio_id,report}`.
`GET /imports/{report_id}/export?format=json|csv` exports the full report.
`GET /exports/{kind}?revision_id=UUID&format=json|csv`, kind transactions|holdings,
exports only the explicit pinned revision (required). JSON is authoritative and
lossless; CSV discloses apostrophe protection for untrusted text and cannot promise
universal spreadsheet safety or decimal round-trip for nondecimal split quantities.
Names are fixed UUID-based ASCII filenames, no-store/nosniff headers.
Exports include X-Finweb-Portfolio-Id and X-Finweb-Revision-Id or
X-Finweb-Report-Id, according to the selected export.

## Financial/provenance and transaction boundaries

New migration0019 adds append-only `web_csv_report` and `web_csv_source_key`.
Only SELECT/INSERT grants are added. Rows include canonical JSON plus SHA256 and
typed correlation columns. No UPDATE/DELETE/TRUNCATE or file writes in persistence.
Every read validates checksum, exact required fields, owner/portfolio/operation/
source correlations, byte provenance, report counts and committed event linkage;
malformed/incomplete metadata503 after foreign404. No constructor defaults may
manufacture confirmation or provenance.

Source identity is a canonical structured tuple:
`[portfolio,namespace,kind,source_account_or_owned_account,snapshot_or_empty,row_key]`.
Keys are claimed only with successful financial commit; report-only attempts do
not poison later corrected imports. Holdings checks prior snapshot source identity
before creating its deterministic new account. Identical economic rows with
different explicit keys remain distinct. Same source key and changed interpretation
409, never overwrite. CSV ledger source_reference is `CP7 CSV source:<keySHA>`;
the durable source-key row points to report/raw row and stored event.
An additional snapshot-level identity binds the complete holdings economic row-key
set before account creation. Adding/removing/changing a row under an already
imported snapshot is409. Economic fingerprints exclude operation-derived IDs,
retain null versuszero and preserve canonical native event fields. Completed
exact-operation retries restore the durable result before checking a pending
preview's memory HMAC; only uncommitted previews expire on restart.

An optional internal existing-connection seam is added to WorkspaceStore.command;
the existing no-argument B2 behavior is preserved. CSV owns one outer transaction,
locks the owner/head, creates a new holdings account if needed, executes one
APPEND with trusted CSV event/source identities, inserts the revision/source keys
and full report, then commits. Report failure rolls everything back. Preview uses
the same operations in a nested rollback-only transaction, preserving no facts.

## Bounds and parsing

At most128 logical data rows/32 columns/2048 UTF-8 bytes per cell; at most32 newly
accepted events. No silent truncation/chunking. Internal-transfer legs stay in the
same canonical batch. Header plus strict csv.reader configured explicit delimiter,
doublequote:true, quotechar:"\"", escapechar:null, skipinitialspace:false,strict:true.
Ragged rows are quarantined. Empty records are retained, not silently dropped.
Invalid UTF-8/NUL/structural CSV errors are typed whole-file refusal. Decimal and
thousands conventions are explicit and cannot coincide. Grouping is validated;
no scientific notation/NaN/float/sign inference. Existing exact numeric bounds and
zero-basis rules apply. Date formats are explicit and validated as calendar dates.
Each portfolio has an independent1000 durable-report cap, checked under its lock
after completed exact-operation recovery. Full capacity returns429
CSV_REPORT_CAPACITY with zero new financial/report/source writes; retries do not
consume capacity. Parse/preview limits publish this bound. Paging keeps every older
report reachable without increasing the unrelated owned-portfolio list cap.
The complete canonical report is limited to2,000,000 UTF-8 bytes, matching the
unchanged0019 table constraint. Preview checks a conservative prospective-final
metadata shape; insertion checks the exact final bytes again inside the outer
transaction. Oversize returns422 CSV_REPORT_TOO_LARGE with no report or financial
writes, no truncation and no automatic splitting. Limits publish report_bytes.

Validation follows the PM matrix: actual parser, source-key, preview-receipt,
zero-report correction, full rollback/concurrency, restart/report integrity,
fixed-revision export and owner/CSRF tests; independent review and full regression
are separate from author evidence. Runtime only new C schemas on the approved
private cluster. No release/data/owner-gate claims follow from technical closure.

Final regression compatibility note:0019's event source-key foreign key requires
the old ledger TRUNCATE guard test to name both ledger_event and
web_csv_source_key, ledger first. The test retains23001 and additionally pins the
original ledger guard's constraint name and message. No applied SQL, FK, grant or
immutable guard is changed; see the additive author self-validation record.
