import { ApiError, isObject, SCHEMA, type JsonObject } from './transport';
import { readWorkspaceResult, type WorkspaceResult } from './workspace';

export const CSV_FIELDS = ['source_row_key', 'account_id', 'account_name', 'event_type', 'event_date', 'currency', 'listing_id', 'symbol', 'mic', 'quantity', 'amount', 'cost_basis', 'bought_amount', 'bought_currency', 'split_new', 'split_old', 'counterparty_account_id', 'settlement_date', 'ex_date', 'acquired_on'] as const;
export type CsvField = typeof CSV_FIELDS[number];
export interface CsvFormat { delimiter: ',' | ';' | '\t'; date_format: 'ISO' | 'DMY' | 'MDY'; decimal_separator: '.' | ','; thousands_separator: null | ',' | '.' | ' ' }
export interface CsvParse {
  schema_version: typeof SCHEMA; portfolio_id: string; file_sha256: string; byte_count: number; bom: boolean;
  columns: { index: number; header: string }[]; rows: { row_number: number; physical_start: number; physical_end: number; cells: string[] }[]; limits: JsonObject;
}
export interface CsvProposal {
  operation_id: string; expected_revision_id: string; file_base64: string; filename: string;
  kind: 'HOLDINGS' | 'TRANSACTIONS'; as_of: string; source_namespace: string; source_account_key: string | null;
  snapshot_key: string | null; new_account_name: string | null; mapping: Partial<Record<CsvField, number>>;
  constants: Partial<Record<CsvField, string>>; corrections: { row_number: number; fields: Partial<Record<CsvField, string>>; reason: string }[];
  classifications: { row_number: number; classification: 'NON_DATA' | 'OUT_OF_SCOPE'; reason: string }[];
  format: CsvFormat; synthetic_acknowledged: true;
}
export interface CsvRow {
  row_number: number; physical_start: number; physical_end: number; cells: string[]; classification: string; reason: string | null;
  fields: Record<string, string>; errors: { code: string; field: string | null; detail: string }[]; event: JsonObject | null;
  source_identity: unknown[] | null; source_key: string | null; existing_event_id: string | null;
  disposition: 'READY' | 'QUARANTINED' | 'EXCLUDED' | 'ALREADY_IMPORTED'; event_id: string | null;
}
export interface CsvReport {
  schema: 'finweb.csv_import/1'; report_id: string; portfolio_id: string; operation_id: string; expected_revision_id: string;
  proposal_digest: string; persisted: boolean; status: 'READY' | 'QUARANTINED' | 'BATCH_REFUSED' | 'COMMITTED' | 'REPORT_ONLY' | 'ALREADY_IMPORTED';
  file: { filename: string; sha256: string; byte_count: number; bom: boolean }; proposal: CsvProposal; parser: JsonObject;
  rows: CsvRow[]; counts: { total: number; economic: number; ready: number; quarantined: number; excluded: number; already_imported: number; imported: number };
  batch_errors: { code: string; detail: string }[]; revision_id: string | null; created_at: string | null;
}
export interface CsvPreview {
  schema_version: typeof SCHEMA; portfolio_id: string; proposal_digest: string; preview_receipt: string;
  report: CsvReport; financial_preview: WorkspaceResult | null;
}
export interface CsvCommit { report: CsvReport; workspace_result: WorkspaceResult | null }
export interface CsvReportSummary { report_id: string; status: string; created_at: string; revision_id: string | null; kind: 'HOLDINGS' | 'TRANSACTIONS'; file_sha256: string; counts: CsvReport['counts']; operation_kind?: 'FINANCIAL_CSV' | 'CSV_REPORT_ONLY'; operation_id?: string; archive_url?: string }
export interface CsvReportPage { reports: CsvReportSummary[]; next_cursor: string | null }
export interface CsvDownload { content: string; filename: string; format: 'CSV' | 'JSON' }
const text = (value: unknown): value is string => typeof value === 'string';
const optionalText = (value: unknown) => value === null || text(value);
const integer = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0;
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(text);
const digest = (value: unknown) => text(value) && /^[0-9a-f]{64}$/.test(value);
function invalid(): never { throw new ApiError('INVALID_RESPONSE', 'CSV response scope or audit contract mismatch'); }
function counts(value: unknown): boolean {
  return isObject(value) && ['total', 'economic', 'ready', 'quarantined', 'excluded', 'already_imported', 'imported'].every((key) => integer(value[key]));
}
function eventStrings(value: unknown): boolean {
  if (value === null) return true;
  if (!isObject(value) || !['event_type', 'account_id', 'event_date', 'currency'].every((field) => text(value[field]))) return false;
  if (!['quantity', 'amount', 'cost_basis'].every((field) => value[field] === undefined || value[field] === null || text(value[field]))) return false;
  return (value.bought_amount == null || isObject(value.bought_amount) && text(value.bought_amount.amount) && text(value.bought_amount.currency))
    && (value.split_ratio == null || isObject(value.split_ratio) && text(value.split_ratio.new_units) && text(value.split_ratio.old_units));
}
function canonicalProposal(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalProposal).join(',')}]`;
  if (isObject(value)) return `{${Object.keys(value).filter((key) => value[key] !== undefined).sort().map((key) => `${JSON.stringify(key)}:${canonicalProposal(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
export function sameCsvProposal(left: unknown, right: unknown): boolean { return canonicalProposal(left) === canonicalProposal(right); }
export function readCsvParse(value: unknown, portfolioId: string): CsvParse {
  if (!isObject(value) || value.schema_version !== SCHEMA || value.portfolio_id !== portfolioId || !digest(value.file_sha256)
    || !integer(value.byte_count) || Number(value.byte_count) > 16_384 || typeof value.bom !== 'boolean'
    || !Array.isArray(value.columns) || !value.columns.every((column, index) => isObject(column) && column.index === index && text(column.header))
    || !Array.isArray(value.rows) || !value.rows.every((row, index) => isObject(row) && row.row_number === index + 1
      && integer(row.physical_start) && integer(row.physical_end) && strings(row.cells)) || !isObject(value.limits)) return invalid();
  return value as unknown as CsvParse;
}
export function readCsvReport(value: unknown, portfolioId: string, reportId?: string, persisted?: boolean): CsvReport {
  if (!isObject(value) || value.schema !== 'finweb.csv_import/1' || value.portfolio_id !== portfolioId || !text(value.report_id)
    || reportId !== undefined && value.report_id !== reportId || typeof value.persisted !== 'boolean' || persisted !== undefined && value.persisted !== persisted
    || !text(value.operation_id) || !text(value.expected_revision_id) || !digest(value.proposal_digest)
    || !['READY', 'QUARANTINED', 'BATCH_REFUSED', 'COMMITTED', 'REPORT_ONLY', 'ALREADY_IMPORTED'].includes(String(value.status))
    || !isObject(value.file) || !text(value.file.filename) || !digest(value.file.sha256) || !integer(value.file.byte_count) || typeof value.file.bom !== 'boolean'
    || !isObject(value.proposal) || value.proposal.operation_id !== value.operation_id || value.proposal.expected_revision_id !== value.expected_revision_id
    || value.proposal.synthetic_acknowledged !== true || !isObject(value.parser) || !counts(value.counts)
    || !Array.isArray(value.rows) || !value.rows.every((row) => isObject(row) && integer(row.row_number) && Number(row.row_number) > 0
      && integer(row.physical_start) && integer(row.physical_end) && strings(row.cells) && ['ECONOMIC', 'NON_DATA', 'OUT_OF_SCOPE'].includes(String(row.classification)) && optionalText(row.reason)
      && isObject(row.fields) && Object.values(row.fields).every(text) && Array.isArray(row.errors)
      && row.errors.every((error) => isObject(error) && text(error.code) && optionalText(error.field) && text(error.detail))
      && eventStrings(row.event) && (row.source_identity === null || strings(row.source_identity))
      && optionalText(row.source_key) && optionalText(row.existing_event_id) && optionalText(row.event_id)
      && ['READY', 'QUARANTINED', 'EXCLUDED', 'ALREADY_IMPORTED'].includes(String(row.disposition)))
    || !Array.isArray(value.batch_errors) || !value.batch_errors.every((error) => isObject(error) && text(error.code) && text(error.detail))
    || !optionalText(value.revision_id) || !optionalText(value.created_at)) return invalid();
  const report = value as unknown as CsvReport;
  if (report.file.filename !== report.proposal.filename || report.rows.some((row) => (row.classification !== 'ECONOMIC') !== (row.disposition === 'EXCLUDED')
    || (row.errors.length > 0) !== (row.disposition === 'QUARANTINED') || row.classification !== 'ECONOMIC' && !row.reason?.trim())
    || (report.persisted ? report.created_at === null : report.created_at !== null)) return invalid();
  if (report.counts.total !== report.rows.length || report.counts.ready !== report.rows.filter((row) => row.disposition === 'READY').length
    || report.counts.quarantined !== report.rows.filter((row) => row.disposition === 'QUARANTINED').length
    || report.counts.excluded !== report.rows.filter((row) => row.disposition === 'EXCLUDED').length
    || report.counts.already_imported !== report.rows.filter((row) => row.disposition === 'ALREADY_IMPORTED').length
    || report.counts.economic !== report.counts.ready + report.counts.quarantined + report.counts.already_imported
    || report.counts.economic !== report.rows.filter((row) => row.classification === 'ECONOMIC').length
    || report.counts.total !== report.counts.economic + report.counts.excluded
    || report.persisted !== ['COMMITTED', 'REPORT_ONLY', 'ALREADY_IMPORTED'].includes(report.status) && report.status !== 'ALREADY_IMPORTED'
    || !report.persisted && (report.counts.imported !== 0 || report.revision_id !== null)
    || ['REPORT_ONLY', 'ALREADY_IMPORTED'].includes(report.status) && (report.counts.imported !== 0 || report.revision_id !== null)
    || report.status === 'COMMITTED' && (report.counts.imported !== report.counts.ready || report.counts.imported === 0 || report.revision_id === null || report.counts.quarantined !== 0 || report.batch_errors.length !== 0)
    || report.status === 'READY' && (report.counts.quarantined !== 0 || report.batch_errors.length !== 0)
    || report.status === 'BATCH_REFUSED' && report.batch_errors.length === 0
    || report.status === 'ALREADY_IMPORTED' && (report.counts.ready !== 0 || report.counts.quarantined !== 0 || report.batch_errors.length !== 0)) return invalid();
  return report;
}
export function readCsvPreview(value: unknown, portfolioId: string, proposal: CsvProposal): CsvPreview {
  if (!isObject(value) || value.schema_version !== SCHEMA || value.portfolio_id !== portfolioId || !digest(value.proposal_digest) || !digest(value.preview_receipt)) return invalid();
  const report = readCsvReport(value.report, portfolioId, undefined, false);
  if (report.proposal_digest !== value.proposal_digest || report.operation_id !== proposal.operation_id || report.expected_revision_id !== proposal.expected_revision_id || !sameCsvProposal(report.proposal, proposal)) return invalid();
  const financial = value.financial_preview === null ? null : readWorkspaceResult(value.financial_preview, portfolioId, true);
  if (financial && (report.status !== 'READY' || report.counts.quarantined > 0 || report.batch_errors.length > 0
    || financial.workspace.revision_id !== proposal.expected_revision_id || financial.workspace.current_revision_id !== proposal.expected_revision_id
    || financial.workspace.as_of !== proposal.as_of || financial.snapshot.as_of !== proposal.as_of)) return invalid();
  if (report.status === 'READY' && report.counts.ready > 0 && financial === null) return invalid();
  return { ...value, report, financial_preview: financial } as unknown as CsvPreview;
}
export function readCsvCommit(value: unknown, portfolioId: string, proposal: CsvProposal): CsvCommit {
  if (!isObject(value) || value.schema_version !== SCHEMA || value.portfolio_id !== portfolioId) return invalid();
  const report = readCsvReport(value.report, portfolioId, undefined, true);
  if (report.operation_id !== proposal.operation_id || report.expected_revision_id !== proposal.expected_revision_id || !sameCsvProposal(report.proposal, proposal)) return invalid();
  const result = value.workspace_result === null ? null : readWorkspaceResult(value.workspace_result, portfolioId);
  if ((report.status === 'COMMITTED') !== (result !== null) || result && result.workspace.revision_id !== report.revision_id) return invalid();
  return { report, workspace_result: result };
}
export function readCsvSummaries(value: unknown, portfolioId: string): CsvReportPage {
  if (!isObject(value) || value.schema_version !== SCHEMA || value.portfolio_id !== portfolioId || !Array.isArray(value.reports)
    || !value.reports.every((report) => isObject(report) && text(report.report_id) && text(report.status) && text(report.created_at)
      && optionalText(report.revision_id) && ['HOLDINGS', 'TRANSACTIONS'].includes(String(report.kind)) && digest(report.file_sha256) && counts(report.counts))
    || !optionalText(value.next_cursor)) return invalid();
  return { reports: value.reports as unknown as CsvReportSummary[], next_cursor: value.next_cursor as string | null };
}

export function readCsvDownload(value: unknown, portfolioId: string, binding: { revisionId?: string; reportId?: string }, format: 'CSV' | 'JSON'): CsvDownload {
  if (!isObject(value) || !text(value.content) || value.portfolioId !== portfolioId || value.redirected === true
    || binding.revisionId !== undefined && value.revisionId !== binding.revisionId
    || binding.reportId !== undefined && value.reportId !== binding.reportId
    || !text(value.contentType) || value.contentType.split(';')[0].trim().toLowerCase() !== (format === 'CSV' ? 'text/csv' : 'application/json')
    || !text(value.disposition) || !text(value.cacheControl) || !value.cacheControl.includes('no-store') || value.noSniff !== 'nosniff') return invalid();
  const match = /(?:^|;)\s*filename=(?:"([^"]+)"|([^;\s]+))/.exec(value.disposition);
  const filename = match?.[1] ?? match?.[2];
  if (!filename || !/^finweb-[a-zA-Z0-9._-]+\.(?:csv|json)$/.test(filename) || !filename.endsWith(format === 'CSV' ? '.csv' : '.json') || filename.length > 160) return invalid();
  return { content: value.content, filename, format };
}
