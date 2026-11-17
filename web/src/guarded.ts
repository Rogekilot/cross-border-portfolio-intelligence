import { ApiError, isObject, type JsonObject } from './transport';

export const GUARDED_PROFILE = 'F3_FICTIONAL_CP5' as const;
export const GUARDED_OUTPUT_BYTES = 20_000_000;
export const GUARDED_OPERATIONS = ['CREATE', 'LEDGER', 'PREFERENCES', 'CSV_PARSE', 'CSV_PREVIEW', 'CSV_COMMIT', 'READ', 'EXPORT', 'ARCHIVE', 'REPRODUCE', 'RECONCILE'] as const;
export const GUARDED_UNSUPPORTED = ['LEGACY_ANALYTICS', 'LEGACY_PACKETS', 'REAL_DATA', 'GUEST'] as const;

export interface GuardedProfile {
  schema: 'finweb.guarded_profile/1'; profile: typeof GUARDED_PROFILE; synthetic: true; saved_only: true;
  source_as_of: '2026-01-02'; opening_date_required: true; opening_date_max: '2026-01-02';
  opening_date_recommended: '2026-01-01'; selector: 'CP5_DIVERSIFICATION';
  operations: typeof GUARDED_OPERATIONS; unsupported: typeof GUARDED_UNSUPPORTED;
}
export interface GuardedRead {
  schema: 'finweb.guarded_read/1'; profile: typeof GUARDED_PROFILE; portfolio_id: string; revision_id: string;
  operation_id: string; context_id: string; generation: number; issued_sha256: string;
  archived_response_sha256: string; archive_url: string;
}
export interface GuardedCommitted {
  schema: 'finweb.guarded_http/1'; profile: typeof GUARDED_PROFILE; disposition: 'COMMITTED'; synthetic: true;
  portfolio_id: string; operation_id: string; revision_id: string; response_json: string; response: JsonObject;
  response_sha256: string; issued_sha256: string; archive_url: string; reconcile_url: string;
}
export interface GuardedUnknown {
  schema: 'finweb.guarded_http/1'; profile: typeof GUARDED_PROFILE; disposition: 'UNKNOWN'; synthetic: true;
  portfolio_id: string; operation_id: string; reconcile_url: string;
}
export interface GuardedRefused {
  schema: 'finweb.guarded_http/1'; profile: typeof GUARDED_PROFILE; disposition: 'REFUSED'; synthetic: true;
  portfolio_id: string; operation_id: string; error: { code: string; detail: string; state: 'INSUFFICIENT_DATA' };
  issued_json: string; issued_sha256: string;
}
export interface GuardedBinding { operationId: string; portfolioId?: string; revisionId?: string }
export interface GuardedSubmission { readonly operationId: string; readonly requestJson: string }
export interface PendingGuardedOperation { operationId: string; portfolioId?: string; kind?: 'CSV_REPORT'; baseRevisionId?: string }
export interface GuardedArchiveWire {
  schema: 'finweb.guarded_archive/1'; profile: typeof GUARDED_PROFILE; synthetic: true;
  portfolio_id: string; operation_id: string; revision_id: string; context_id: string; generation: number; admission_generation: number;
  issued_json: string; response_json: string; envelope_json: string;
  issued_sha256: string; response_sha256: string; envelope_sha256: string;
}
export interface GuardedMetric {
  metric_id: string; subject: string[]; value: string | null; state: 'AVAILABLE' | 'LIMITED' | 'INSUFFICIENT_DATA';
  reason: string | null; details: string[]; manifest_id: string;
}
export interface VerifiedGuardedArchive {
  wire: GuardedArchiveWire; issued: JsonObject; response: JsonObject; envelope: JsonObject;
  issuedGeneration: number; metrics: GuardedMetric[];
}
export interface GuardedReproduction {
  schema: 'finweb.guarded_reproduce/1'; profile: typeof GUARDED_PROFILE; synthetic: true;
  portfolio_id: string; operation_id: string; status: 'REPRODUCED' | 'INPUT_MISMATCH' | 'SOURCE_REFUSED' | 'RESULT_DIFFERS';
  detail: string; issued_sha256: string | null;
}
export interface GuardedArchiveDownload { content: string; filename: string; archive: VerifiedGuardedArchive }
export interface GuardedArchiveApi {
  guardedArchive(portfolioId: string, operationId: string): Promise<VerifiedGuardedArchive>;
  guardedArchiveExport(portfolioId: string, operationId: string): Promise<GuardedArchiveDownload>;
  guardedReproduce(portfolioId: string, operationId: string, expectedIssuedSha: string): Promise<GuardedReproduction>;
  guardedReconcile(portfolioId: string, operationId: string): Promise<GuardedCommitted | GuardedUnknown>;
  guardedCreationReconcile(operationId: string): Promise<GuardedCommitted | GuardedUnknown>;
}

export class GuardedOutcomeError extends ApiError {
  constructor(public outcome: GuardedUnknown | GuardedRefused) {
    super(outcome.disposition === 'UNKNOWN' ? 'F3_OUTCOME_UNKNOWN' : outcome.error.code,
      outcome.disposition === 'UNKNOWN' ? 'The operation is not confirmed; retain the same operation identity.' : outcome.error.detail,
      outcome.disposition === 'UNKNOWN' ? 202 : 422);
  }
}
/** Client uncertainty, not a fabricated HTTP202 envelope or a statement that rollback occurred. */
export class GuardedUnconfirmedError extends ApiError {
  constructor(public operationId: string, public portfolioId: string | undefined, public causeCode: string, actualStatus = 0) {
    super('F3_OUTCOME_UNKNOWN', 'The request may have committed. Retain the same operation and unchanged request for explicit recovery.', actualStatus);
  }
}

const own = (value: unknown, names: readonly string[]): value is JsonObject => isObject(value)
  && Object.keys(value).length === names.length && names.every((name) => Object.hasOwn(value, name));
const text = (value: unknown): value is string => typeof value === 'string';
export const guardedUuid = (value: unknown): value is string => text(value) && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(value);
const sha = (value: unknown): value is string => text(value) && /^[0-9a-f]{64}$/.test(value);
const positiveSafe = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
const nonnegativeSafe = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(text);
const sameArray = (value: unknown, expected: readonly string[]) => Array.isArray(value)
  && value.length === expected.length && value.every((item, index) => item === expected[index]);
const decimal = (value: unknown) => text(value) && /^-?\d+(?:\.\d+)?$/.test(value);
const exact = (value: unknown) => value === null || text(value) && /^-?\d+(?:\.\d+|\/[1-9]\d*)?$/.test(value);
function invalid(): never { throw new ApiError('INVALID_RESPONSE', 'Guarded fictional response or artifact binding mismatch'); }
function wellFormed(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(++index); if (!(next >= 0xdc00 && next <= 0xdfff)) return false;
    } else if (code >= 0xdc00 && code <= 0xdfff) return false;
  }
  return true;
}
function bounded(value: unknown): void {
  let raw: string; try { raw = JSON.stringify(value); } catch { return invalid(); }
  if (!text(raw) || !wellFormed(raw) || new TextEncoder().encode(raw).byteLength > GUARDED_OUTPUT_BYTES) invalid();
}
function parseObject(raw: unknown): JsonObject {
  if (!text(raw) || !wellFormed(raw) || new TextEncoder().encode(raw).byteLength > GUARDED_OUTPUT_BYTES) return invalid();
  let value: unknown; try { value = JSON.parse(raw); } catch { return invalid(); }
  return isObject(value) ? value : invalid();
}
/** Preserve exact unchanged request bytes in memory; this helper never creates/retries an operation. */
export function guardedSubmission(body: JsonObject, operationId: unknown = body.operation_id): GuardedSubmission {
  if (!guardedUuid(operationId) || body.operation_id !== undefined && body.operation_id !== operationId
    || isObject(body.proposal) && body.proposal.operation_id !== operationId) return invalid();
  let raw: string; try { raw = JSON.stringify(body); } catch { return invalid(); }
  if (!wellFormed(raw) || new TextEncoder().encode(raw).byteLength > 32_768) throw new ApiError('REQUEST_TOO_LARGE', 'The complete request exceeds 32768 bytes', 413);
  return Object.freeze({ operationId, requestJson: raw });
}
export function guardedOperationPath(portfolioId: string, operationId: string): string {
  if (!guardedUuid(portfolioId) || !guardedUuid(operationId)) return invalid();
  return `/api/v1/portfolios/${portfolioId}/operations/${operationId}`;
}
function identity(value: JsonObject, binding: GuardedBinding): boolean {
  return value.profile === GUARDED_PROFILE && guardedUuid(value.portfolio_id) && guardedUuid(value.operation_id)
    && value.operation_id === binding.operationId && (binding.portfolioId === undefined || value.portfolio_id === binding.portfolioId)
    && (binding.revisionId === undefined || value.revision_id === binding.revisionId);
}
function links(value: JsonObject): boolean {
  if (!guardedUuid(value.portfolio_id) || !guardedUuid(value.operation_id)) return false;
  const path = guardedOperationPath(value.portfolio_id, value.operation_id);
  return value.archive_url === path && (value.reconcile_url === undefined || value.reconcile_url === `${path}/reconcile`);
}

/** Exact byte integrity only. The server remains responsible for current rights and financial validation. */
export async function guardedSha256(raw: string): Promise<string> {
  if (!wellFormed(raw) || new TextEncoder().encode(raw).byteLength > GUARDED_OUTPUT_BYTES) return invalid();
  try {
    const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw));
    return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  } catch { return invalid(); }
}
/** Bound actual bytes before parsing. Callers recheck identity/view epochs after this and every digest await. */
export async function guardedResponseText(response: Response): Promise<string> {
  const header = response.headers.get('Content-Length');
  if (header !== null && (!/^\d+$/.test(header) || Number(header) > GUARDED_OUTPUT_BYTES)) return invalid();
  if (!response.body) return '';
  const reader = response.body.getReader(); const decoder = new TextDecoder('utf-8', { fatal: true });
  const parts: string[] = []; let bytes = 0;
  try {
    while (true) {
      const item = await reader.read(); if (item.done) break;
      bytes += item.value.byteLength;
      if (bytes > GUARDED_OUTPUT_BYTES) { await reader.cancel(); return invalid(); }
      parts.push(decoder.decode(item.value, { stream: true }));
    }
    parts.push(decoder.decode()); return parts.join('');
  } catch (error) { if (error instanceof ApiError) throw error; return invalid(); }
  finally { reader.releaseLock(); }
}
export function readGuardedProfile(value: unknown): GuardedProfile {
  if (!own(value, ['schema', 'profile', 'synthetic', 'saved_only', 'source_as_of', 'opening_date_required', 'opening_date_max', 'opening_date_recommended', 'selector', 'operations', 'unsupported'])
    || value.schema !== 'finweb.guarded_profile/1' || value.profile !== GUARDED_PROFILE || value.synthetic !== true || value.saved_only !== true
    || value.source_as_of !== '2026-01-02' || value.opening_date_required !== true || value.opening_date_max !== '2026-01-02'
    || value.opening_date_recommended !== '2026-01-01' || value.selector !== 'CP5_DIVERSIFICATION'
    || !sameArray(value.operations, GUARDED_OPERATIONS) || !sameArray(value.unsupported, GUARDED_UNSUPPORTED)) return invalid();
  return value as unknown as GuardedProfile;
}
export function validGuardedOpeningDate(value: string, profile: GuardedProfile): boolean {
  if (!/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(value) || value > profile.opening_date_max) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}
export function readGuardedRead(value: unknown, portfolioId: string, revisionId?: string): GuardedRead {
  if (!own(value, ['schema', 'profile', 'portfolio_id', 'revision_id', 'operation_id', 'context_id', 'generation', 'issued_sha256', 'archived_response_sha256', 'archive_url'])
    || value.schema !== 'finweb.guarded_read/1' || value.profile !== GUARDED_PROFILE || value.portfolio_id !== portfolioId
    || !guardedUuid(value.portfolio_id) || !guardedUuid(value.revision_id) || !guardedUuid(value.operation_id)
    || revisionId !== undefined && value.revision_id !== revisionId || !sha(value.context_id) || !positiveSafe(value.generation)
    || !sha(value.issued_sha256) || !sha(value.archived_response_sha256) || !links(value)) return invalid();
  return value as unknown as GuardedRead;
}
function responseRoot(value: JsonObject, root: string, revision: string): boolean {
  if (value.portfolio_id === root) return true; // Snapshot; legacy reader checks the remaining fields.
  if (isObject(value.workspace) && value.workspace.portfolio_id === root && value.workspace.revision_id === revision) return true;
  return isObject(value.report) && value.report.portfolio_id === root && (value.report.revision_id === null || value.report.revision_id === revision)
    && (value.workspace_result === null || isObject(value.workspace_result) && isObject(value.workspace_result.workspace)
      && value.workspace_result.workspace.portfolio_id === root && value.workspace_result.workspace.revision_id === revision);
}
function noNumericWitness(value: JsonObject): boolean {
  return value.exact == null && value.exact_square == null && value.sign == null
    && (value.radical_terms == null || Array.isArray(value.radical_terms) && value.radical_terms.length === 0);
}
export async function readGuardedCommitted(value: unknown, binding: GuardedBinding): Promise<GuardedCommitted> {
  bounded(value);
  if (!own(value, ['schema', 'profile', 'disposition', 'synthetic', 'portfolio_id', 'operation_id', 'revision_id', 'response_json', 'response', 'response_sha256', 'issued_sha256', 'archive_url', 'reconcile_url'])
    || value.schema !== 'finweb.guarded_http/1' || value.disposition !== 'COMMITTED' || value.synthetic !== true || !identity(value, binding)
    || !guardedUuid(value.revision_id) || !text(value.response_json) || !isObject(value.response)
    || !sha(value.response_sha256) || !sha(value.issued_sha256) || !links(value)) return invalid();
  if (await guardedSha256(value.response_json) !== value.response_sha256) return invalid();
  const response = parseObject(value.response_json);
  if (!responseRoot(response, String(value.portfolio_id), String(value.revision_id))) return invalid();
  // Render the hashed raw response, never the convenience response object.
  return { ...value, response } as unknown as GuardedCommitted;
}
export function readGuardedUnknown(value: unknown, binding: GuardedBinding): GuardedUnknown {
  if (!own(value, ['schema', 'profile', 'disposition', 'synthetic', 'portfolio_id', 'operation_id', 'reconcile_url'])
    || value.schema !== 'finweb.guarded_http/1' || value.disposition !== 'UNKNOWN' || value.synthetic !== true || !identity(value, binding)
    || value.reconcile_url !== `${guardedOperationPath(String(value.portfolio_id), String(value.operation_id))}/reconcile`) return invalid();
  return value as unknown as GuardedUnknown;
}
export async function readGuardedRefused(value: unknown, binding: GuardedBinding): Promise<GuardedRefused> {
  bounded(value);
  if (!own(value, ['schema', 'profile', 'disposition', 'synthetic', 'portfolio_id', 'operation_id', 'error', 'issued_json', 'issued_sha256'])
    || value.schema !== 'finweb.guarded_http/1' || value.disposition !== 'REFUSED' || value.synthetic !== true || !identity(value, binding)
    || !own(value.error, ['code', 'detail', 'state']) || !text(value.error.code) || !text(value.error.detail)
    || value.error.state !== 'INSUFFICIENT_DATA' || !text(value.issued_json) || !sha(value.issued_sha256)
    || await guardedSha256(value.issued_json) !== value.issued_sha256) return invalid();
  const issued = parseObject(value.issued_json);
  if (!Array.isArray(issued.metrics) || issued.metrics.length === 0 || !issued.metrics.every((metric) => isObject(metric)
    && metric.value === null && metric.state === 'INSUFFICIENT_DATA' && noNumericWitness(metric))) return invalid();
  return value as unknown as GuardedRefused;
}
export async function readGuardedOutcome(value: unknown, status: number, binding: GuardedBinding): Promise<GuardedCommitted | GuardedUnknown | GuardedRefused> {
  if (status === 200 && isObject(value) && value.disposition === 'COMMITTED') return readGuardedCommitted(value, binding);
  if (status === 202 && isObject(value) && value.disposition === 'UNKNOWN') return readGuardedUnknown(value, binding);
  if (status === 422 && isObject(value) && value.disposition === 'REFUSED') return readGuardedRefused(value, binding);
  return invalid();
}

function hexText(value: unknown): string {
  if (!text(value) || value.length > 65_536 || value.length % 2 !== 0 || !/^[0-9a-f]+$/.test(value)) return invalid();
  try { return new TextDecoder('utf-8', { fatal: true }).decode(Uint8Array.from(value.match(/../g)!, (part) => Number.parseInt(part, 16))); }
  catch { return invalid(); }
}
function validMetric(value: unknown, manifestId: string): value is GuardedMetric {
  return isObject(value) && text(value.metric_id) && strings(value.subject) && strings(value.details) && value.manifest_id === manifestId
    && ['AVAILABLE', 'LIMITED', 'INSUFFICIENT_DATA'].includes(String(value.state)) && (value.reason === null || text(value.reason))
    && (value.state === 'INSUFFICIENT_DATA' ? value.value === null && noNumericWitness(value) : decimal(value.value))
    && ['exact', 'exact_square'].every((key) => exact(value[key]))
    && (value.observation_count === null || nonnegativeSafe(value.observation_count))
    && (value.sign === null || value.sign === -1 || value.sign === 0 || value.sign === 1)
    && Array.isArray(value.radical_terms) && value.radical_terms.every((pair) => Array.isArray(pair) && pair.length === 2 && pair.every(exact));
}
export async function readGuardedArchive(value: unknown, binding: GuardedBinding): Promise<VerifiedGuardedArchive> {
  bounded(value);
  if (!own(value, ['schema', 'profile', 'synthetic', 'portfolio_id', 'operation_id', 'revision_id', 'context_id', 'generation', 'admission_generation', 'issued_json', 'response_json', 'envelope_json', 'issued_sha256', 'response_sha256', 'envelope_sha256'])
    || value.schema !== 'finweb.guarded_archive/1' || value.synthetic !== true || !identity(value, binding)
    || !guardedUuid(value.revision_id) || !sha(value.context_id) || !positiveSafe(value.generation) || !positiveSafe(value.admission_generation)
    || !['issued_json', 'response_json', 'envelope_json'].every((key) => text(value[key]))
    || !['issued_sha256', 'response_sha256', 'envelope_sha256'].every((key) => sha(value[key]))) return invalid();
  const [issuedSha, responseSha, envelopeSha] = await Promise.all([
    guardedSha256(String(value.issued_json)), guardedSha256(String(value.response_json)), guardedSha256(String(value.envelope_json)),
  ]);
  if (issuedSha !== value.issued_sha256 || responseSha !== value.response_sha256 || envelopeSha !== value.envelope_sha256) return invalid();
  const issued = parseObject(value.issued_json); const response = parseObject(value.response_json); const envelope = parseObject(value.envelope_json);
  if (!own(envelope, ['schema', 'synthetic', 'actual_executor', 'approval_scope', 'owner_id', 'root_id', 'operation_id', 'revision_id', 'ledger_pin', 'context_id', 'generation', 'issued_sha256', 'response_sha256', 'family', 'engine_id', 'manifest_id', 'result_digest', 'question_sha256', 'binding_sha256', 'question_hex', 'binding_hex', 'selector', 'fixture_quotes_sha256', 'fixture_calendar_sha256'])
    || envelope.schema !== 'finweb.f2.fictional-issued-envelope/1' || envelope.synthetic !== true
    || envelope.actual_executor !== 'local_application' || envelope.approval_scope !== 'fictional_local_only'
    || envelope.root_id !== value.portfolio_id || envelope.operation_id !== value.operation_id || envelope.revision_id !== value.revision_id
    || envelope.context_id !== value.context_id || !positiveSafe(envelope.generation) || envelope.generation !== value.generation || !nonnegativeSafe(envelope.ledger_pin)
    || envelope.issued_sha256 !== issuedSha || envelope.response_sha256 !== responseSha || envelope.family !== 'CP5_DIVERSIFICATION'
    || envelope.selector !== 'CP5_DIVERSIFICATION' || envelope.engine_id !== 'diversification/cp5-0.2'
    || !sha(envelope.manifest_id) || !sha(envelope.result_digest) || !sha(envelope.question_sha256) || !sha(envelope.binding_sha256)
    || !sha(envelope.fixture_quotes_sha256) || !sha(envelope.fixture_calendar_sha256)
    || !responseRoot(response, String(value.portfolio_id), String(value.revision_id))) return invalid();
  const questionRaw = hexText(envelope.question_hex); const bindingRaw = hexText(envelope.binding_hex);
  const [questionSha, bindingSha] = await Promise.all([guardedSha256(questionRaw), guardedSha256(bindingRaw)]);
  if (questionSha !== envelope.question_sha256 || bindingSha !== envelope.binding_sha256) return invalid();
  const question = parseObject(questionRaw); const native = parseObject(bindingRaw);
  if (!own(question, ['schema', 'selector', 'owner_id', 'root_id', 'revision_id', 'operation_id', 'portfolio_id', 'ledger_pin', 'as_of', 'context_id', 'generation', 'account_scope', 'reporting_currency'])
    || question.schema !== 'finweb.local_fictional.service_question/1' || question.root_id !== value.portfolio_id
    || question.portfolio_id !== value.portfolio_id || question.operation_id !== value.operation_id || question.revision_id !== value.revision_id
    || question.owner_id !== envelope.owner_id || !guardedUuid(question.owner_id) || question.context_id !== value.context_id
    || question.generation !== envelope.generation || question.ledger_pin !== String(envelope.ledger_pin)
    || question.selector !== 'CP5_DIVERSIFICATION' || question.reporting_currency !== 'USD' || question.account_scope !== null
    || !own(native, ['schema', 'question', 'question_sha256', 'context_snapshot_sha256', 'generation', 'family', 'engine_id', 'manifest_id', 'result_digest', 'issued_sha256', 'synthetic', 'release_id', 'source_registry_digest', 'consumed_identity_digest', 'f8b_policy'])
    || native.schema !== 'finweb.local_fictional.service_binding/1' || native.context_snapshot_sha256 !== value.context_id
    || native.generation !== envelope.generation || native.question_sha256 !== questionSha || native.issued_sha256 !== issuedSha
    || native.manifest_id !== envelope.manifest_id || native.result_digest !== envelope.result_digest
    || native.family !== envelope.family || native.engine_id !== envelope.engine_id || native.synthetic !== true || !isObject(native.question)
    || Object.keys(native.question).length !== Object.keys(question).length
    || Object.keys(question).some((key) => isObject(native.question) && native.question[key] !== question[key])) return invalid();
  if (!own(issued, ['manifest', 'manifest_id', 'result_digest', 'metrics', 'clusters', 'exposure_decompositions'])
    || !isObject(issued.manifest) || issued.manifest.schema !== 'finweb.diversification_manifest/1' || issued.manifest.synthetic !== true
    || issued.manifest.portfolio_id !== value.portfolio_id || issued.manifest.engine_id !== envelope.engine_id
    || issued.manifest.as_of !== question.as_of || issued.manifest.reporting_currency !== 'USD'
    || issued.manifest_id !== envelope.manifest_id || issued.result_digest !== envelope.result_digest
    || !Array.isArray(issued.metrics) || !issued.metrics.every((metric) => validMetric(metric, String(issued.manifest_id)))) return invalid();
  // admission_generation is current; generation/envelope/question retain the original issuance generation.
  return { wire: value as unknown as GuardedArchiveWire, issued, response, envelope,
    issuedGeneration: envelope.generation, metrics: issued.metrics as GuardedMetric[] };
}
export function readGuardedReproduction(value: unknown, binding: GuardedBinding, expectedIssuedSha: string): GuardedReproduction {
  if (!own(value, ['schema', 'profile', 'synthetic', 'portfolio_id', 'operation_id', 'status', 'detail', 'issued_sha256'])
    || value.schema !== 'finweb.guarded_reproduce/1' || value.synthetic !== true || !identity(value, binding)
    || !['REPRODUCED', 'INPUT_MISMATCH', 'SOURCE_REFUSED', 'RESULT_DIFFERS'].includes(String(value.status)) || !text(value.detail)
    || !(value.issued_sha256 === null || sha(value.issued_sha256)) || !sha(expectedIssuedSha)
    || value.status === 'REPRODUCED' && value.issued_sha256 !== expectedIssuedSha) return invalid();
  return value as unknown as GuardedReproduction;
}
