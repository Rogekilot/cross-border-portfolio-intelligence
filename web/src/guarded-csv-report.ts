import { ApiError, isObject, SCHEMA, type JsonObject } from './transport';
import { CSV_FIELDS, readCsvReport, sameCsvProposal, type CsvProposal, type CsvReport } from './csv';
import { GUARDED_PROFILE, guardedOperationPath, guardedSha256, guardedUuid, type GuardedSubmission } from './guarded';

export const CSV_REPORT_RESPONSE_BYTES = 2_000_000;
export const CSV_REPORT_ENVELOPE_BYTES = 65_536;
export interface GuardedCsvReportBinding {
  portfolioId: string; operationId: string; baseRevisionId?: string; reportId?: string; ownerId?: string;
  submission?: GuardedSubmission;
}
export interface GuardedCsvReportCommitted {
  schema: 'finweb.guarded_csv_report/1'; profile: typeof GUARDED_PROFILE; disposition: 'REPORT_COMMITTED'; synthetic: true;
  portfolio_id: string; operation_id: string; base_revision_id: string; report_id: string;
  response_json: string; response_sha256: string; archive_url: string; reconcile_url: string;
}
export interface GuardedCsvReportUnknown {
  schema: 'finweb.guarded_csv_report/1'; profile: typeof GUARDED_PROFILE; disposition: 'UNKNOWN'; synthetic: true;
  portfolio_id: string; operation_id: string; reconcile_url: string;
}
export interface GuardedCsvReportRead {
  schema: 'finweb.guarded_csv_report_read/1'; profile: typeof GUARDED_PROFILE; synthetic: true;
  portfolio_id: string; operation_id: string; report_id: string; base_revision_id: string; context_id: string;
  commit_generation: number; admission_generation: number; response_sha256: string; archive_url: string;
}
export type GuardedCsvReportReference = GuardedCsvReportCommitted | GuardedCsvReportRead;
export interface GuardedCsvReportArchiveWire {
  schema: 'finweb.guarded_csv_report_archive/1'; profile: typeof GUARDED_PROFILE; synthetic: true;
  portfolio_id: string; operation_id: string; base_revision_id: string; report_id: string; context_id: string;
  commit_generation: number; admission_generation: number; response_json: string; response_sha256: string;
  envelope_json: string; envelope_sha256: string;
}
export interface VerifiedGuardedCsvReportArchive { wire: GuardedCsvReportArchiveWire; report: CsvReport; envelope: JsonObject }
export interface GuardedCsvReportApi {
  guardedCsvReportArchive(root: string, operation: string): Promise<VerifiedGuardedCsvReportArchive>;
  guardedCsvReportArchiveExport(root: string, operation: string): Promise<{ content: string; filename: string; archive: VerifiedGuardedCsvReportArchive }>;
  guardedCsvReportReconcile(root: string, operation: string): Promise<GuardedCsvReportCommitted | GuardedCsvReportUnknown>;
}
export class GuardedCsvReportOutcomeError extends ApiError {
  constructor(public outcome: GuardedCsvReportUnknown) {
    super('F3_OUTCOME_UNKNOWN', 'The report operation is not confirmed. Keep its unchanged original request.', 202);
  }
}
const own = (value: unknown, names: readonly string[]): value is JsonObject => isObject(value)
  && Object.keys(value).length === names.length && names.every((name) => Object.hasOwn(value, name));
const sha = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const natural = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
const positive = (value: unknown): value is number => natural(value) && value > 0;
const text = (value: unknown): value is string => typeof value === 'string';
const visible = (value: unknown, limit: number) => text(value) && value.trim().length > 0 && value.length <= limit && !/[\u0000-\u001f]/.test(value);
function invalid(): never { throw new ApiError('INVALID_RESPONSE', 'The fictional CSV report bytes or operation binding differ'); }
function objectText(value: unknown, maximum: number): JsonObject {
  if (!text(value) || new TextEncoder().encode(value).byteLength > maximum) return invalid();
  let parsed: unknown; try { parsed = JSON.parse(value); } catch { return invalid(); }
  return isObject(parsed) ? parsed : invalid();
}
/** Canonical request/proposal hashing; exact transport bytes are separately retained for retries. */
function canonical(value: unknown, depth: number): string {
  if (depth > 32) return invalid();
  if (text(value)) {
    for (let index = 0; index < value.length; index += 1) {
      const code = value.charCodeAt(index);
      if (code >= 0xd800 && code <= 0xdbff) { const next = value.charCodeAt(++index); if (!(next >= 0xdc00 && next <= 0xdfff)) return invalid(); }
      else if (code >= 0xdc00 && code <= 0xdfff) return invalid();
    }
    return JSON.stringify(value);
  }
  if (value === null || typeof value === 'boolean') return JSON.stringify(value);
  if (typeof value === 'number' && Number.isSafeInteger(value)) return String(value);
  if (Array.isArray(value)) return `[${value.map((part) => canonical(part, depth + 1)).join(',')}]`;
  if (isObject(value)) return `{${Object.keys(value).sort().map((key) => `${canonical(key, depth + 1)}:${canonical(value[key], depth + 1)}`).join(',')}}`;
  return invalid();
}
export function csvReportCanonical(value: unknown): string { return canonical(value, 0); }
export function guardedCsvReportPath(root: string, operation?: string): string {
  if (!guardedUuid(root) || operation !== undefined && !guardedUuid(operation)) return invalid();
  return `/api/v1/portfolios/${root}/import-report-operations${operation === undefined ? '' : `/${operation}`}`;
}
function identity(value: JsonObject, binding: GuardedCsvReportBinding): boolean {
  return value.profile === GUARDED_PROFILE && value.synthetic === true
    && guardedUuid(value.portfolio_id) && value.portfolio_id === binding.portfolioId
    && guardedUuid(value.operation_id) && value.operation_id === binding.operationId
    && (binding.reportId === undefined || value.report_id === binding.reportId)
    && (binding.baseRevisionId === undefined || value.base_revision_id === binding.baseRevisionId);
}
function validateProposal(value: unknown): asserts value is CsvProposal & JsonObject {
  if (!own(value, ['operation_id', 'expected_revision_id', 'as_of', 'file_base64', 'filename', 'kind', 'source_namespace', 'source_account_key', 'snapshot_key', 'new_account_name', 'mapping', 'constants', 'corrections', 'classifications', 'format', 'synthetic_acknowledged'])
    || !guardedUuid(value.operation_id) || !guardedUuid(value.expected_revision_id) || value.kind !== 'TRANSACTIONS'
    || value.synthetic_acknowledged !== true || !visible(value.filename, 120) || !visible(value.source_namespace, 128)
    || value.source_namespace !== String(value.source_namespace).trim() || !text(value.as_of) || !/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(value.as_of)
    || value.source_account_key !== null || value.snapshot_key !== null || value.new_account_name !== null
    || !text(value.file_base64) || value.file_base64.length > 21_848
    || !own(value.format, ['delimiter', 'date_format', 'decimal_separator', 'thousands_separator'])
    || ![',', ';', '\t'].includes(String(value.format.delimiter)) || !['ISO', 'DMY', 'MDY'].includes(String(value.format.date_format))
    || !['.', ','].includes(String(value.format.decimal_separator)) || ![null, ',', '.', ' '].includes(value.format.thousands_separator as string | null)
    || value.format.thousands_separator === value.format.decimal_separator || !isObject(value.mapping) || !isObject(value.constants)
    || Object.keys(value.mapping).length > 22 || Object.keys(value.constants).length > 22
    || Object.keys(value.mapping).some((key) => !CSV_FIELDS.includes(key as typeof CSV_FIELDS[number]) || Object.hasOwn(value.constants as object, key))
    || Object.values(value.mapping).some((index) => !natural(index) || index >= 32)
    || Object.entries(value.constants).some(([key, cell]) => !CSV_FIELDS.includes(key as typeof CSV_FIELDS[number]) || !text(cell) || new TextEncoder().encode(cell).byteLength > 2048)
    || !Array.isArray(value.corrections) || value.corrections.length > 128 || !Array.isArray(value.classifications) || value.classifications.length > 128) return invalid();
  const date = new Date(`${value.as_of}T00:00:00Z`);
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value.as_of) return invalid();
  for (const [name, rows] of [['corrections', value.corrections], ['classifications', value.classifications]] as const) {
    const seen = new Set<number>();
    for (const row of rows) {
      if (!own(row, name === 'corrections' ? ['row_number', 'fields', 'reason'] : ['row_number', 'classification', 'reason'])
        || !positive(row.row_number) || row.row_number > 128 || seen.has(row.row_number) || !visible(row.reason, 500)) return invalid();
      seen.add(row.row_number);
      if (name === 'corrections' ? !isObject(row.fields) || Object.keys(row.fields).length === 0 || Object.keys(row.fields).length > 22
        || Object.entries(row.fields).some(([key, cell]) => !CSV_FIELDS.includes(key as typeof CSV_FIELDS[number]) || !text(cell) || new TextEncoder().encode(cell).byteLength > 2048)
        : !['NON_DATA', 'OUT_OF_SCOPE'].includes(String(row.classification))) return invalid();
    }
  }
}
async function fileIdentity(proposal: CsvProposal): Promise<{ sha256: string; byteCount: number; bom: boolean }> {
  let binary: string; try { binary = atob(proposal.file_base64); } catch { return invalid(); }
  if (!binary.length || binary.length > 16_384 || btoa(binary) !== proposal.file_base64) return invalid();
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  let decoded: string; try { decoded = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes); } catch { return invalid(); }
  if (decoded.includes('\0')) return invalid();
  let digest: ArrayBuffer; try { digest = await crypto.subtle.digest('SHA-256', bytes.buffer); } catch { return invalid(); }
  return { sha256: [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join(''), byteCount: bytes.length, bom: decoded.startsWith('\u{FEFF}') };
}
export async function readGuardedCsvReportDocument(value: unknown, binding: GuardedCsvReportBinding): Promise<CsvReport> {
  if (!own(value, ['schema', 'report_id', 'portfolio_id', 'operation_id', 'expected_revision_id', 'proposal_digest', 'persisted', 'status', 'file', 'proposal', 'parser', 'rows', 'counts', 'batch_errors', 'revision_id', 'created_at'])) return invalid();
  const report = readCsvReport(value, binding.portfolioId, binding.reportId, true);
  validateProposal(report.proposal);
  if (!guardedUuid(report.report_id) || report.operation_id !== binding.operationId || !guardedUuid(report.operation_id)
    || !guardedUuid(report.expected_revision_id) || binding.baseRevisionId !== undefined && report.expected_revision_id !== binding.baseRevisionId
    || !['ALREADY_IMPORTED', 'REPORT_ONLY'].includes(report.status) || report.revision_id !== null || report.counts.imported !== 0
    || report.rows.length === 0 || report.rows.length > 128 || !own(report.counts, ['total', 'economic', 'ready', 'quarantined', 'excluded', 'already_imported', 'imported'])
    || !own(report.file, ['filename', 'sha256', 'byte_count', 'bom']) || !own(report.parser, ['version', 'dialect'])
    || report.parser.version !== 'csv/cp7-1' || report.parser.dialect !== 'stdlib-explicit-v1'
    || !visible(report.created_at, 64)
    || report.status === 'ALREADY_IMPORTED' && report.counts.already_imported === 0
    || report.status === 'REPORT_ONLY' && report.counts.quarantined === 0 && report.batch_errors.length === 0 && (report.counts.ready > 0 || report.counts.already_imported > 0)
    || report.batch_errors.some((error) => ['SOURCE_KEY_CONFLICT', 'SOURCE_SNAPSHOT_CONFLICT'].includes(error.code))) return invalid();
  if (binding.submission) {
    const body = objectText(binding.submission.requestJson, 32_768);
    if (!own(body, ['proposal', 'preview_receipt']) || !sameCsvProposal(body.proposal, report.proposal) || !sha(body.preview_receipt)) return invalid();
  }
  const [file, proposalSha] = await Promise.all([fileIdentity(report.proposal), guardedSha256(csvReportCanonical(report.proposal))]);
  if (file.sha256 !== report.file.sha256 || file.byteCount !== report.file.byte_count || file.bom !== report.file.bom || proposalSha !== report.proposal_digest) return invalid();
  const seen = new Set<number>();
  for (const row of report.rows) {
    if (!own(row, ['row_number', 'physical_start', 'physical_end', 'cells', 'classification', 'reason', 'fields', 'errors', 'event', 'source_identity', 'source_key', 'existing_event_id', 'disposition', 'event_id'])
      || seen.has(row.row_number) || row.row_number > 128 || row.physical_start < 2 || row.physical_end < row.physical_start
      || row.cells.length > 32 || row.cells.some((cell) => new TextEncoder().encode(cell).byteLength > 2048)
      || Object.keys(row.fields).some((key) => !CSV_FIELDS.includes(key as typeof CSV_FIELDS[number]))
      || row.errors.some((error) => !own(error, ['code', 'field', 'detail']) || ['SOURCE_KEY_CONFLICT', 'SOURCE_SNAPSHOT_CONFLICT'].includes(error.code))
      || row.disposition !== 'ALREADY_IMPORTED' && row.event_id !== null
      || row.existing_event_id !== null && !guardedUuid(row.existing_event_id)) return invalid();
    seen.add(row.row_number);
    if (row.source_identity !== null) {
      const expected = ['EVENT', binding.portfolioId, report.proposal.source_namespace, 'TRANSACTIONS', row.event?.account_id, '', row.fields.source_row_key];
      if (!Array.isArray(row.source_identity) || row.source_identity.length !== expected.length || row.source_identity.some((part, index) => part !== expected[index])
        || !guardedUuid(row.event?.account_id) || !sha(row.source_key) || await guardedSha256(csvReportCanonical(row.source_identity)) !== row.source_key) return invalid();
    } else if (row.source_key !== null || row.disposition === 'ALREADY_IMPORTED' || row.existing_event_id !== null) return invalid();
    if (row.disposition === 'ALREADY_IMPORTED' && (!guardedUuid(row.existing_event_id) || row.event_id !== row.existing_event_id)) return invalid();
  }
  return report;
}
async function responseDocument(raw: unknown, expectedSha: unknown, binding: GuardedCsvReportBinding): Promise<CsvReport> {
  if (!text(raw) || !sha(expectedSha) || await guardedSha256(raw) !== expectedSha) return invalid();
  const response = objectText(raw, CSV_REPORT_RESPONSE_BYTES);
  if (!own(response, ['report', 'workspace_result']) || response.workspace_result !== null || csvReportCanonical(response) !== raw) return invalid();
  return readGuardedCsvReportDocument(response.report, binding);
}
export async function readGuardedCsvReportCommitted(value: unknown, binding: GuardedCsvReportBinding): Promise<GuardedCsvReportCommitted> {
  if (!own(value, ['schema', 'profile', 'disposition', 'synthetic', 'portfolio_id', 'operation_id', 'base_revision_id', 'report_id', 'response_json', 'response_sha256', 'archive_url', 'reconcile_url'])
    || value.schema !== 'finweb.guarded_csv_report/1' || value.disposition !== 'REPORT_COMMITTED' || !identity(value, binding)
    || !guardedUuid(value.base_revision_id) || !guardedUuid(value.report_id)
    || value.archive_url !== guardedCsvReportPath(binding.portfolioId, binding.operationId)
    || value.reconcile_url !== `${guardedCsvReportPath(binding.portfolioId, binding.operationId)}/reconcile`) return invalid();
  await responseDocument(value.response_json, value.response_sha256, { ...binding, reportId: String(value.report_id), baseRevisionId: String(value.base_revision_id) });
  return value as unknown as GuardedCsvReportCommitted;
}
export function readGuardedCsvReportUnknown(value: unknown, binding: GuardedCsvReportBinding): GuardedCsvReportUnknown {
  if (!own(value, ['schema', 'profile', 'disposition', 'synthetic', 'portfolio_id', 'operation_id', 'reconcile_url'])
    || value.schema !== 'finweb.guarded_csv_report/1' || value.disposition !== 'UNKNOWN'
    || !identity(value, { portfolioId: binding.portfolioId, operationId: binding.operationId })
    || value.reconcile_url !== `${guardedCsvReportPath(binding.portfolioId, binding.operationId)}/reconcile`) return invalid();
  return value as unknown as GuardedCsvReportUnknown;
}
export async function readGuardedCsvReportOutcome(value: unknown, status: number, binding: GuardedCsvReportBinding): Promise<GuardedCsvReportCommitted | GuardedCsvReportUnknown> {
  if (status === 200) return readGuardedCsvReportCommitted(value, binding);
  if (status === 202) return readGuardedCsvReportUnknown(value, binding);
  return invalid();
}
export async function readGuardedCsvReportArchive(value: unknown, binding: GuardedCsvReportBinding): Promise<VerifiedGuardedCsvReportArchive> {
  if (!own(value, ['schema', 'profile', 'synthetic', 'portfolio_id', 'operation_id', 'base_revision_id', 'report_id', 'context_id', 'commit_generation', 'admission_generation', 'response_json', 'response_sha256', 'envelope_json', 'envelope_sha256'])
    || value.schema !== 'finweb.guarded_csv_report_archive/1' || !identity(value, binding)
    || !guardedUuid(value.base_revision_id) || !guardedUuid(value.report_id) || !sha(value.context_id)
    || !positive(value.commit_generation) || !positive(value.admission_generation) || value.admission_generation < value.commit_generation || !sha(value.envelope_sha256)
    || !text(value.envelope_json) || await guardedSha256(value.envelope_json) !== value.envelope_sha256) return invalid();
  const report = await responseDocument(value.response_json, value.response_sha256, { ...binding, reportId: String(value.report_id), baseRevisionId: String(value.base_revision_id) });
  const envelope = objectText(value.envelope_json, CSV_REPORT_ENVELOPE_BYTES);
  if (!own(envelope, ['schema', 'profile', 'synthetic', 'operation_kind', 'owner_id', 'portfolio_id', 'operation_id', 'report_id', 'context_id', 'commit_generation', 'base_revision_id', 'base_operation_id', 'base_ledger_pin', 'request_sha256', 'proposal_sha256', 'preview_receipt_sha256', 'response_sha256', 'report_status', 'created_at'])
    || csvReportCanonical(envelope) !== value.envelope_json || envelope.schema !== 'finweb.csv_report_envelope/1'
    || envelope.operation_kind !== 'CSV_REPORT_ONLY' || !identity(envelope, { ...binding, baseRevisionId: String(value.base_revision_id), reportId: String(value.report_id) })
    || !guardedUuid(envelope.owner_id) || binding.ownerId !== undefined && envelope.owner_id !== binding.ownerId
    || !guardedUuid(envelope.base_operation_id) || !text(envelope.base_ledger_pin) || !/^(?:0|[1-9]\d*)$/.test(envelope.base_ledger_pin)
    || envelope.context_id !== value.context_id || envelope.commit_generation !== value.commit_generation
    || envelope.response_sha256 !== value.response_sha256 || envelope.proposal_sha256 !== report.proposal_digest
    || !sha(envelope.request_sha256) || !sha(envelope.preview_receipt_sha256)
    || envelope.report_status !== report.status || envelope.created_at !== report.created_at) return invalid();
  if (binding.submission) {
    const body = objectText(binding.submission.requestJson, 32_768);
    if (!own(body, ['proposal', 'preview_receipt']) || !sha(body.preview_receipt)) return invalid();
    const [requestSha, proposalSha, receiptSha] = await Promise.all([
      guardedSha256(csvReportCanonical(body)), guardedSha256(csvReportCanonical(body.proposal)), guardedSha256(body.preview_receipt),
    ]);
    if (envelope.request_sha256 !== requestSha || envelope.proposal_sha256 !== proposalSha || envelope.preview_receipt_sha256 !== receiptSha) return invalid();
  }
  return { wire: value as unknown as GuardedCsvReportArchiveWire, report, envelope };
}
export async function readGuardedCsvReportRead(value: unknown, root: string, reportId: string): Promise<{ report: CsvReport; reference: GuardedCsvReportRead }> {
  if (!own(value, ['schema_version', 'portfolio_id', 'report', 'guarded_report']) || value.schema_version !== SCHEMA || value.portfolio_id !== root
    || !own(value.guarded_report, ['schema', 'profile', 'synthetic', 'portfolio_id', 'operation_id', 'report_id', 'base_revision_id', 'context_id', 'commit_generation', 'admission_generation', 'response_sha256', 'archive_url'])) return invalid();
  const metadata = value.guarded_report;
  if (metadata.schema !== 'finweb.guarded_csv_report_read/1' || !guardedUuid(metadata.operation_id)
    || !identity(metadata, { portfolioId: root, operationId: metadata.operation_id, reportId })
    || !guardedUuid(metadata.base_revision_id) || !sha(metadata.context_id) || !positive(metadata.commit_generation) || !positive(metadata.admission_generation)
    || metadata.admission_generation < metadata.commit_generation
    || !sha(metadata.response_sha256) || metadata.archive_url !== guardedCsvReportPath(root, metadata.operation_id)) return invalid();
  const report = await readGuardedCsvReportDocument(value.report, { portfolioId: root, operationId: metadata.operation_id, reportId, baseRevisionId: String(metadata.base_revision_id) });
  if (await guardedSha256(csvReportCanonical({ report, workspace_result: null })) !== metadata.response_sha256) return invalid();
  return { report, reference: metadata as unknown as GuardedCsvReportRead };
}
export function assertGuardedCsvSummaries(value: unknown, root: string): void {
  if (!isObject(value) || !Array.isArray(value.reports) || value.reports.length > 25
    || !(value.next_cursor === null || text(value.next_cursor) && value.next_cursor.length > 0 && value.next_cursor.length <= 512)) return invalid();
  const seen = new Set<string>();
  for (const row of value.reports) {
    if (!own(row, ['report_id', 'status', 'created_at', 'kind', 'file_sha256', 'counts', 'revision_id', 'operation_kind', 'operation_id', 'archive_url'])
      || !guardedUuid(row.report_id) || seen.has(row.report_id) || !guardedUuid(row.operation_id) || !sha(row.file_sha256)
      || !visible(row.created_at, 64) || !own(row.counts, ['total', 'economic', 'ready', 'quarantined', 'excluded', 'already_imported', 'imported'])
      || Object.values(row.counts).some((value) => !natural(value) || value > 128)
      || row.counts.economic !== Number(row.counts.ready) + Number(row.counts.quarantined) + Number(row.counts.already_imported)
      || row.counts.total !== Number(row.counts.economic) + Number(row.counts.excluded)) return invalid();
    seen.add(row.report_id);
    if (row.operation_kind === 'CSV_REPORT_ONLY') {
      if (row.kind !== 'TRANSACTIONS' || !['ALREADY_IMPORTED', 'REPORT_ONLY'].includes(String(row.status)) || row.revision_id !== null
        || row.counts.imported !== 0 || row.archive_url !== guardedCsvReportPath(root, row.operation_id)
        || row.status === 'ALREADY_IMPORTED' && (row.counts.ready !== 0 || row.counts.quarantined !== 0 || row.counts.already_imported === 0)) return invalid();
    } else if (row.operation_kind !== 'FINANCIAL_CSV' || row.status !== 'COMMITTED' || !guardedUuid(row.revision_id)
      || row.counts.imported !== row.counts.ready || row.counts.imported === 0 || row.archive_url !== guardedOperationPath(root, row.operation_id)) return invalid();
  }
}
