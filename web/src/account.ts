import { ApiError, isObject, readPacketResponse, readReproduction, readSavedSnapshot, SCHEMA, type CreatePortfolio, type Snapshot } from './transport';
import { readWorkspace, readWorkspaceResult, revisionQuery, type LedgerCommand, type PreferencesCommand } from './workspace';
import { assertCsvEnvelope } from './csv-file';
import { readCsvCommit, readCsvDownload, readCsvParse, readCsvPreview, readCsvReport, readCsvSummaries, type CsvProposal } from './csv';
import { analyticalProof, readAnalyticsEvaluation, readAnalyticsEvidence, readAnalyticsReproduction, type AnalyticsQuestion, type AnalyticsResult } from './analytics';
import { readRealSourceReadiness } from './real-source';
import { assertGuardedCsvSummaries, csvReportCanonical, guardedCsvReportPath, GuardedCsvReportOutcomeError,
  readGuardedCsvReportArchive, readGuardedCsvReportCommitted, readGuardedCsvReportOutcome, readGuardedCsvReportRead,
  type GuardedCsvReportBinding, type GuardedCsvReportCommitted, type GuardedCsvReportReference, type GuardedCsvReportUnknown } from './guarded-csv-report';
import { guardedOperationPath, guardedResponseText, guardedSubmission, guardedUuid, GuardedOutcomeError, GuardedUnconfirmedError, readGuardedArchive,
  readGuardedCommitted, readGuardedOutcome, readGuardedProfile, readGuardedRead, readGuardedReproduction,
  type GuardedBinding, type GuardedCommitted, type GuardedProfile, type GuardedRead, type GuardedSubmission, type GuardedUnknown,
  type PendingGuardedOperation } from './guarded';

export interface User { user_id: string; username: string }
export interface AccountSession { schema_version: typeof SCHEMA; authenticated: boolean; user: User | null; csrf_token: string; guarded_profile?: GuardedProfile }
export interface SavedPortfolio {
  portfolio_id: string; name: string; mode: 'LOCAL_SYNTHETIC_ACCOUNT'; synthetic: true;
  reporting_currency: 'USD'; as_of: string; created_at: string;
  guarded?: GuardedRead;
}
export function readSession(value: unknown): AccountSession {
  if (!isObject(value) || value.schema_version !== SCHEMA || typeof value.authenticated !== 'boolean'
    || typeof value.csrf_token !== 'string' || !/^[0-9a-f]{64}$/.test(value.csrf_token)
    || (value.authenticated ? !isObject(value.user) || typeof value.user.user_id !== 'string' || typeof value.user.username !== 'string' : value.user !== null)) {
    throw new ApiError('INVALID_RESPONSE', 'Invalid account session');
  }
  if (value.guarded_profile !== undefined) readGuardedProfile(value.guarded_profile);
  return value as unknown as AccountSession;
}
export function isCancelled(error: unknown): boolean { return error instanceof ApiError && error.code === 'REQUEST_CANCELLED'; }
export function validAccountInput(username: string, password: string): boolean {
  return /^[a-zA-Z][a-zA-Z0-9_.-]{2,31}$/.test(username)
    && Array.from(password).length >= 15 && new TextEncoder().encode(password).length <= 128;
}

/** Cookie credentials are HttpOnly. Only the CSRF token lives in this instance's memory. */
export class AccountApi {
  private csrf: string | null = null;
  private revision = 0;
  private pending = new Set<AbortController>();
  private profile: GuardedProfile | null = null;
  private ownerId: string | null = null;
  private uncertain = new Map<string, { submission: GuardedSubmission; path: string; portfolioId?: string; kind?: 'CSV_REPORT'; baseRevisionId?: string }>();
  onSessionLost: ((error: ApiError) => void) | null = null;
  onGuardedPending: ((operation: PendingGuardedOperation | null) => void) | null = null;
  onGuardedReference: ((reference: GuardedRead | GuardedCommitted) => void) | null = null;
  onGuardedCsvReportReference: ((reference: GuardedCsvReportReference) => void) | null = null;
  get guardedProfile(): GuardedProfile | null { return this.profile; }

  cancelPending(): void {
    this.revision += 1;
    this.pending.forEach((controller) => controller.abort()); this.pending.clear();
  }
  reset(): void { this.cancelPending(); this.csrf = null; this.profile = null; this.ownerId = null; this.uncertain.clear(); this.onGuardedPending?.(null); }
  private assertRevision(revision: number): void {
    if (revision !== this.revision) throw new ApiError('REQUEST_CANCELLED', 'Identity changed');
  }
  private async request(path: string, body?: unknown, download = false, guardedBinding?: GuardedBinding, requestJson?: string, reportBinding?: GuardedCsvReportBinding): Promise<unknown> {
    const revision = this.revision;
    const controller = new AbortController(); this.pending.add(controller);
    try {
      let response: Response;
      try {
        response = await fetch(`/api/v1${path}`, {
          method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
          headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-Finweb-CSRF': this.csrf ?? '' },
          ...(body === undefined ? {} : { body: requestJson ?? JSON.stringify(body) }),
        });
      } catch {
        if (revision !== this.revision || controller.signal.aborted) throw new ApiError('REQUEST_CANCELLED', 'Identity changed');
        throw new ApiError('NETWORK_ERROR', 'Local API unavailable');
      }
      let value: unknown;
      try {
        value = response.ok && download ? { content: this.profile ? await guardedResponseText(response) : await response.text(), portfolioId: response.headers.get('X-Finweb-Portfolio-Id'),
          revisionId: response.headers.get('X-Finweb-Revision-Id'), reportId: response.headers.get('X-Finweb-Report-Id'),
          operationId: response.headers.get('X-Finweb-Operation-Id'),
          contentType: response.headers.get('Content-Type'), disposition: response.headers.get('Content-Disposition'),
          cacheControl: response.headers.get('Cache-Control'), noSniff: response.headers.get('X-Content-Type-Options'), redirected: response.redirected }
          : this.profile ? JSON.parse(await guardedResponseText(response)) : await response.json();
      }
      catch { throw new ApiError('INVALID_RESPONSE', 'Invalid JSON', response.status); }
      if (revision !== this.revision || controller.signal.aborted) throw new ApiError('REQUEST_CANCELLED', 'Identity changed');
      if (guardedBinding && isObject(value) && value.schema === 'finweb.guarded_http/1') {
        const outcome = await readGuardedOutcome(value, response.status, guardedBinding);
        this.assertRevision(revision); if (controller.signal.aborted) throw new ApiError('REQUEST_CANCELLED', 'Identity changed');
        if (outcome.disposition !== 'COMMITTED') throw new GuardedOutcomeError(outcome);
        return outcome;
      }
      if (reportBinding && response.ok) {
        const outcome = await readGuardedCsvReportOutcome(value, response.status, reportBinding);
        this.assertRevision(revision); if (controller.signal.aborted) throw new ApiError('REQUEST_CANCELLED', 'Identity changed');
        if (outcome.disposition === 'UNKNOWN') throw new GuardedCsvReportOutcomeError(outcome);
        return outcome;
      }
      if (!response.ok) {
        const error = isObject(value) && isObject(value.error) ? value.error : null;
        const failure = new ApiError(typeof error?.code === 'string' ? error.code : 'API_ERROR',
          typeof error?.detail === 'string' ? error.detail : '', response.status);
        if (response.status === 401 || error?.code === 'CSRF_REJECTED') {
          this.reset(); this.onSessionLost?.(failure);
        }
        throw failure;
      }
      return value;
    } finally { this.pending.delete(controller); }
  }
  private acceptSession(session: AccountSession): void { this.csrf = session.csrf_token; this.profile = session.guarded_profile ?? null; this.ownerId = session.user?.user_id ?? null; }
  private readGuarded(value: unknown, portfolioId: string, revisionId?: string): GuardedRead | null {
    if (!this.profile) return null;
    if (!isObject(value)) throw new ApiError('INVALID_RESPONSE', 'Missing guarded read metadata');
    return readGuardedRead(value.guarded, portfolioId, revisionId);
  }
  private clearOperation(op: string): void { this.uncertain.delete(op); if (this.uncertain.size === 0) this.onGuardedPending?.(null); }
  private async guardedMutation(path: string, body: Record<string, unknown>, portfolioId?: string, saved?: GuardedSubmission, operationId?: string): Promise<GuardedCommitted> {
    const revision = this.revision;
    if (!this.csrf) await this.session(); this.assertRevision(revision);
    if (!this.profile) throw new ApiError('F3_GUARDED_UNSUPPORTED', 'The guarded profile is unavailable');
    const submission = saved ?? guardedSubmission(body, operationId ?? body.operation_id); const prior = this.uncertain.get(submission.operationId);
    if (prior?.kind === 'CSV_REPORT') throw new ApiError('IDEMPOTENCY_CONFLICT', 'This operation is pending on the report-specific recovery path');
    if (prior && prior.submission.requestJson !== submission.requestJson) throw new ApiError('IDEMPOTENCY_CONFLICT', 'The uncertain operation must keep its exact request');
    if ([...this.uncertain.keys()].some((op) => op !== submission.operationId)) throw new ApiError('F3_PENDING_OPERATION', 'Resolve the uncertain operation before sending another');
    let knownRoot = portfolioId;
    try {
      const result = await this.request(path, body, false, { operationId: submission.operationId, portfolioId }, submission.requestJson);
      this.assertRevision(revision);
      const envelope = await readGuardedCommitted(result, { operationId: submission.operationId, portfolioId });
      knownRoot = envelope.portfolio_id;
      if (path === '/portfolios') readSavedSnapshot(envelope.response);
      else if (path.endsWith('/imports/commit')) readCsvCommit(envelope.response, envelope.portfolio_id, body.proposal as CsvProposal);
      else readWorkspaceResult(envelope.response, envelope.portfolio_id);
      this.assertRevision(revision); this.clearOperation(submission.operationId); this.onGuardedReference?.(envelope); return envelope;
    } catch (failure) {
      if (revision === this.revision && (failure instanceof GuardedOutcomeError && failure.outcome.disposition === 'UNKNOWN'
        || failure instanceof ApiError && ['NETWORK_ERROR', 'INVALID_RESPONSE'].includes(failure.code)
        || failure instanceof ApiError && failure.status >= 500)) {
        const uncertainRoot = failure instanceof GuardedOutcomeError ? failure.outcome.portfolio_id : knownRoot;
        this.uncertain.set(submission.operationId, { submission, path, portfolioId: uncertainRoot });
        this.onGuardedPending?.({ operationId: submission.operationId, ...(uncertainRoot ? { portfolioId: uncertainRoot } : {}) });
        if (!(failure instanceof GuardedOutcomeError)) throw new GuardedUnconfirmedError(submission.operationId, uncertainRoot,
          failure instanceof ApiError ? failure.code : 'UNRESOLVED', failure instanceof ApiError ? failure.status : 0);
      }
      throw failure;
    }
  }
  async retryGuardedOperation(operationId: string): Promise<GuardedCommitted> {
    const saved = this.uncertain.get(operationId);
    if (!saved) throw new ApiError('F3_OUTCOME_UNKNOWN', 'The original request is no longer available in this tab');
    if (saved.kind === 'CSV_REPORT') throw new ApiError('F3_OUTCOME_UNKNOWN', 'Use this report operation recovery controls');
    return this.guardedMutation(saved.path, JSON.parse(saved.submission.requestJson), saved.portfolioId, saved.submission);
  }
  async session(): Promise<AccountSession> {
    const revision = this.revision;
    const session = readSession(await this.request('/auth/session')); this.assertRevision(revision);
    this.acceptSession(session); return session;
  }
  async realSourceReadiness() {
    return readRealSourceReadiness(await this.request('/real-source-contexts'));
  }
  async authenticate(kind: 'register' | 'login', username: string, password: string): Promise<AccountSession> {
    const revision = this.revision;
    if (!this.csrf) await this.session(); this.assertRevision(revision);
    const session = readSession(await this.request(`/auth/${kind}`, { username, password }));
    this.assertRevision(revision);
    if (!session.authenticated) throw new ApiError('INVALID_RESPONSE', 'Authentication did not establish a session');
    this.acceptSession(session); return session;
  }
  async logout(): Promise<AccountSession> {
    const revision = this.revision;
    if (!this.csrf) await this.session(); this.assertRevision(revision);
    const session = readSession(await this.request('/auth/logout', {}));
    this.assertRevision(revision);
    if (session.authenticated) throw new ApiError('INVALID_RESPONSE', 'Logout did not end the session');
    this.uncertain.clear(); this.onGuardedPending?.(null); this.acceptSession(session); return session;
  }
  async portfolios(): Promise<SavedPortfolio[]> {
    const value = await this.request('/portfolios');
    if (!isObject(value) || value.schema_version !== SCHEMA || !Array.isArray(value.portfolios)
      || !value.portfolios.every((p) => isObject(p) && typeof p.portfolio_id === 'string' && typeof p.name === 'string'
        && p.mode === 'LOCAL_SYNTHETIC_ACCOUNT' && p.synthetic === true && p.reporting_currency === 'USD'
        && typeof p.as_of === 'string' && typeof p.created_at === 'string')) throw new ApiError('INVALID_RESPONSE', 'Invalid saved portfolio list');
    if (this.profile) value.portfolios.forEach((entry) => { if (isObject(entry) && typeof entry.portfolio_id === 'string') readGuardedRead(entry.guarded, entry.portfolio_id); });
    return value.portfolios as SavedPortfolio[];
  }
  async create(input: CreatePortfolio & { operation_id?: string; opening_date?: string }): Promise<Snapshot> {
    const revision = this.revision;
    if (!this.csrf) await this.session(); this.assertRevision(revision);
    const body = { ...input, mode: 'LOCAL_SYNTHETIC_ACCOUNT' };
    if (this.profile) return readSavedSnapshot((await this.guardedMutation('/portfolios', body)).response);
    return readSavedSnapshot(await this.request('/portfolios', body));
  }
  async snapshot(id: string, revisionId?: string): Promise<Snapshot> {
    const value = await this.request(`/portfolios/${encodeURIComponent(id)}${revisionQuery(revisionId)}`); const reference = this.readGuarded(value, id, revisionId);
    const snapshot = readSavedSnapshot(value);
    if (snapshot.portfolio_id !== id) throw new ApiError('INVALID_RESPONSE', 'Saved portfolio identity mismatch');
    if (reference) this.onGuardedReference?.(reference);
    return snapshot;
  }
  async workspace(portfolioId: string, revisionId?: string) {
    const value = await this.request(`/portfolios/${encodeURIComponent(portfolioId)}/workspace${revisionQuery(revisionId)}`); const reference = this.readGuarded(value, portfolioId, revisionId);
    const workspace = readWorkspace(value, portfolioId, revisionId); if (reference) this.onGuardedReference?.(reference); return workspace;
  }
  async ledgerCommand(portfolioId: string, command: LedgerCommand, preview = false) {
    const revision = this.revision;
    if (!this.csrf) await this.session(); this.assertRevision(revision);
    const path = `/portfolios/${encodeURIComponent(portfolioId)}/ledger-commands${preview ? '/preview' : ''}`;
    if (this.profile && !preview) return readWorkspaceResult((await this.guardedMutation(path, { ...command }, portfolioId)).response, portfolioId);
    const value = await this.request(path, command, false, this.profile ? { portfolioId, operationId: command.operation_id } : undefined); this.readGuarded(value, portfolioId, command.expected_revision_id);
    return readWorkspaceResult(value, portfolioId, preview);
  }
  async preferences(portfolioId: string, command: PreferencesCommand) {
    const revision = this.revision;
    if (!this.csrf) await this.session(); this.assertRevision(revision);
    const path = `/portfolios/${encodeURIComponent(portfolioId)}/preferences`;
    if (this.profile) return readWorkspaceResult((await this.guardedMutation(path, { ...command }, portfolioId)).response, portfolioId);
    return readWorkspaceResult(await this.request(path, command), portfolioId);
  }
  private async analyticsRequest(portfolioId: string, action: 'evaluate' | 'evidence' | 'reproduce', body: unknown) {
    if (this.profile) throw new ApiError('F3_GUARDED_UNSUPPORTED', 'Historical analytics is unavailable in this fictional profile');
    const revision = this.revision;
    if (new TextEncoder().encode(JSON.stringify(body)).byteLength > 32_768) throw new ApiError('ANALYTICS_REQUEST_REFUSED', 'The complete analytical request exceeds 32 KiB');
    if (!this.csrf) await this.session(); this.assertRevision(revision);
    return this.request(`/portfolios/${encodeURIComponent(portfolioId)}/analytics/${action}`, body);
  }
  async evaluateAnalytics(portfolioId: string, question: AnalyticsQuestion, ledgerVersion: number) {
    return readAnalyticsEvaluation(await this.analyticsRequest(portfolioId, 'evaluate', question), portfolioId, question, ledgerVersion);
  }
  async analyticalEvidence(portfolioId: string, question: AnalyticsQuestion, result: AnalyticsResult) {
    return readAnalyticsEvidence(await this.analyticsRequest(portfolioId, 'evidence', analyticalProof(question, result)), portfolioId, question, result);
  }
  async reproduceAnalytics(portfolioId: string, question: AnalyticsQuestion, result: AnalyticsResult) {
    return readAnalyticsReproduction(await this.analyticsRequest(portfolioId, 'reproduce', analyticalProof(question, result)), portfolioId, question, result);
  }
  private async csvMutation(path: string, body: unknown, binding?: GuardedBinding): Promise<unknown> {
    assertCsvEnvelope(body); const revision = this.revision;
    if (!this.csrf) await this.session(); this.assertRevision(revision);
    return this.request(path, body, false, binding);
  }
  async parseCsv(portfolioId: string, body: { file_base64: string; filename: string; delimiter: ',' | ';' | '\t'; synthetic_acknowledged: true }) {
    const value = await this.csvMutation(`/portfolios/${encodeURIComponent(portfolioId)}/imports/parse`, body); this.readGuarded(value, portfolioId);
    return readCsvParse(value, portfolioId);
  }
  async previewCsv(portfolioId: string, proposal: CsvProposal) {
    const value = await this.csvMutation(`/portfolios/${encodeURIComponent(portfolioId)}/imports/preview`, proposal,
      this.profile ? { portfolioId, operationId: proposal.operation_id } : undefined); this.readGuarded(value, portfolioId, proposal.expected_revision_id);
    return readCsvPreview(value, portfolioId, proposal);
  }
  async commitCsv(portfolioId: string, proposal: CsvProposal, previewReceipt: string) {
    const path = `/portfolios/${encodeURIComponent(portfolioId)}/imports/commit`; const body = { proposal, preview_receipt: previewReceipt };
    if (this.profile) {
      assertCsvEnvelope(body);
      return readCsvCommit((await this.guardedMutation(path, body, portfolioId, undefined, proposal.operation_id)).response, portfolioId, proposal);
    }
    return readCsvCommit(await this.csvMutation(path, body), portfolioId, proposal);
  }
  private reportBinding(portfolioId: string, operationId: string, submission?: GuardedSubmission, baseRevisionId?: string): GuardedCsvReportBinding {
    this.requireGuarded();
    if (!guardedUuid(this.ownerId)) throw new ApiError('INVALID_RESPONSE', 'Missing authenticated report owner');
    return { portfolioId, operationId, ownerId: this.ownerId, ...(submission ? { submission } : {}), ...(baseRevisionId ? { baseRevisionId } : {}) };
  }
  private async verifiedCsvReportArchive(binding: GuardedCsvReportBinding, expected?: GuardedCsvReportCommitted) {
    const epoch = this.revision;
    const value = await this.request(guardedCsvReportPath(binding.portfolioId, binding.operationId).slice('/api/v1'.length)); this.assertRevision(epoch);
    const archive = await readGuardedCsvReportArchive(value, binding); this.assertRevision(epoch);
    if (expected && (archive.wire.report_id !== expected.report_id || archive.wire.base_revision_id !== expected.base_revision_id
      || archive.wire.response_json !== expected.response_json || archive.wire.response_sha256 !== expected.response_sha256)) throw new ApiError('INVALID_RESPONSE', 'Report acknowledgement and exact archive differ');
    return archive;
  }
  private async csvReportMutation(portfolioId: string, body: { proposal: CsvProposal; preview_receipt: string }, saved?: GuardedSubmission) {
    const epoch = this.revision;
    if (!this.csrf) await this.session(); this.assertRevision(epoch);
    if (body.proposal.kind !== 'TRANSACTIONS') throw new ApiError('F3_CSV_REPORT_HOLDINGS_UNSUPPORTED', 'This fictional profile does not support a zero-import holdings report');
    assertCsvEnvelope(body);
    const submission = saved ?? guardedSubmission(body, body.proposal.operation_id);
    const prior = this.uncertain.get(submission.operationId);
    if (prior && (prior.kind !== 'CSV_REPORT' || prior.submission.requestJson !== submission.requestJson || prior.portfolioId !== portfolioId)) throw new ApiError('IDEMPOTENCY_CONFLICT', 'Keep the same report operation and exact request');
    if ([...this.uncertain.keys()].some((op) => op !== submission.operationId)) throw new ApiError('F3_PENDING_OPERATION', 'Resolve the uncertain operation before sending another');
    const path = guardedCsvReportPath(portfolioId).slice('/api/v1'.length);
    const binding = this.reportBinding(portfolioId, submission.operationId, submission, body.proposal.expected_revision_id);
    let acknowledged = false;
    try {
      const value = await this.request(path, body, false, undefined, submission.requestJson, binding); this.assertRevision(epoch);
      const envelope = await readGuardedCsvReportCommitted(value, binding); this.assertRevision(epoch); acknowledged = true;
      // The success wire has no request digest. Verify the same operation's
      // archive before clearing uncertainty or publishing a saved report.
      const archive = await this.verifiedCsvReportArchive(binding, envelope); this.assertRevision(epoch);
      this.clearOperation(submission.operationId); this.onGuardedCsvReportReference?.(envelope);
      return { envelope, report: archive.report };
    } catch (failure) {
      if (epoch === this.revision && (acknowledged || failure instanceof GuardedCsvReportOutcomeError
        || failure instanceof ApiError && (['NETWORK_ERROR', 'INVALID_RESPONSE'].includes(failure.code) || failure.status >= 500))) {
        this.uncertain.set(submission.operationId, { submission, path, portfolioId, kind: 'CSV_REPORT', baseRevisionId: body.proposal.expected_revision_id });
        this.onGuardedPending?.({ operationId: submission.operationId, portfolioId, kind: 'CSV_REPORT', baseRevisionId: body.proposal.expected_revision_id });
        if (!(failure instanceof GuardedCsvReportOutcomeError)) throw new GuardedUnconfirmedError(submission.operationId, portfolioId,
          acknowledged ? 'F3_REPORT_EVIDENCE_UNVERIFIED' : failure instanceof ApiError ? failure.code : 'UNRESOLVED', failure instanceof ApiError ? failure.status : 0);
      }
      throw failure;
    }
  }
  async commitCsvReport(portfolioId: string, proposal: CsvProposal, previewReceipt: string) {
    const result = await this.csvReportMutation(portfolioId, { proposal, preview_receipt: previewReceipt });
    return { report: result.report, workspace_result: null };
  }
  async retryGuardedCsvReportOperation(operationId: string): Promise<GuardedCsvReportCommitted> {
    const saved = this.uncertain.get(operationId);
    if (!saved || saved.kind !== 'CSV_REPORT' || !saved.portfolioId) throw new ApiError('F3_OUTCOME_UNKNOWN', 'The original report request is no longer available in this tab');
    return (await this.csvReportMutation(saved.portfolioId, JSON.parse(saved.submission.requestJson), saved.submission)).envelope;
  }
  async guardedCsvReportReconcile(portfolioId: string, operationId: string): Promise<GuardedCsvReportCommitted | GuardedCsvReportUnknown> {
    this.requireGuarded(); const epoch = this.revision; const saved = this.uncertain.get(operationId);
    if (saved && (saved.kind !== 'CSV_REPORT' || saved.portfolioId !== portfolioId)) throw new ApiError('IDEMPOTENCY_CONFLICT', 'The pending operation belongs to a different recovery path');
    const binding = this.reportBinding(portfolioId, operationId, saved?.submission, saved?.baseRevisionId);
    try {
      const value = await this.request(`${guardedCsvReportPath(portfolioId, operationId).slice('/api/v1'.length)}/reconcile`, undefined, false, undefined, undefined, binding);
      this.assertRevision(epoch);
      const outcome = await readGuardedCsvReportCommitted(value, binding); this.assertRevision(epoch);
      await this.verifiedCsvReportArchive(binding, outcome); this.assertRevision(epoch);
      return outcome;
    } catch (failure) { if (failure instanceof GuardedCsvReportOutcomeError) return failure.outcome; throw failure; }
  }
  async guardedCsvReportArchive(portfolioId: string, operationId: string) {
    const saved = this.uncertain.get(operationId);
    return this.verifiedCsvReportArchive(this.reportBinding(portfolioId, operationId,
      saved?.kind === 'CSV_REPORT' && saved.portfolioId === portfolioId ? saved.submission : undefined,
      saved?.kind === 'CSV_REPORT' && saved.portfolioId === portfolioId ? saved.baseRevisionId : undefined));
  }
  async guardedCsvReportArchiveExport(portfolioId: string, operationId: string) {
    const epoch = this.revision; const binding = this.reportBinding(portfolioId, operationId);
    const value = await this.request(`${guardedCsvReportPath(portfolioId, operationId).slice('/api/v1'.length)}/export`, undefined, true); this.assertRevision(epoch);
    if (!isObject(value) || typeof value.content !== 'string' || value.portfolioId !== portfolioId || value.operationId !== operationId
      || value.redirected !== false || value.noSniff !== 'nosniff' || typeof value.cacheControl !== 'string' || !value.cacheControl.includes('no-store')
      || typeof value.contentType !== 'string' || value.contentType.split(';')[0].trim().toLowerCase() !== 'application/json') throw new ApiError('INVALID_RESPONSE', 'Report archive download scope mismatch');
    let parsed: unknown; try { parsed = JSON.parse(value.content); } catch { throw new ApiError('INVALID_RESPONSE', 'Invalid report archive JSON'); }
    const archive = await readGuardedCsvReportArchive(parsed, binding); this.assertRevision(epoch);
    const filename = `finweb-csv-report-${archive.wire.report_id}.json`;
    if (value.reportId !== archive.wire.report_id || value.disposition !== `attachment; filename="${filename}"`) throw new ApiError('INVALID_RESPONSE', 'Report archive download identity differs');
    return { content: value.content, filename, archive };
  }
  async csvReports(portfolioId: string, cursor?: string) {
    const value = await this.request(`/portfolios/${encodeURIComponent(portfolioId)}/imports${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`); this.readGuarded(value, portfolioId);
    if (this.profile) assertGuardedCsvSummaries(value, portfolioId);
    return readCsvSummaries(value, portfolioId);
  }
  async csvReport(portfolioId: string, reportId: string) {
    const epoch = this.revision;
    const value = await this.request(`/portfolios/${encodeURIComponent(portfolioId)}/imports/${encodeURIComponent(reportId)}`);
    if (!isObject(value) || value.schema_version !== SCHEMA || value.portfolio_id !== portfolioId) throw new ApiError('INVALID_RESPONSE', 'Report scope mismatch');
    if (this.profile && value.guarded_report !== undefined) {
      const result = await readGuardedCsvReportRead(value, portfolioId, reportId); this.assertRevision(epoch);
      this.onGuardedCsvReportReference?.(result.reference); return result.report;
    }
    this.readGuarded(value, portfolioId);
    return readCsvReport(value.report, portfolioId, reportId, true);
  }
  async exportCsvReport(portfolioId: string, reportId: string, format: 'CSV' | 'JSON') {
    const epoch = this.revision; let expectedOperation: string | undefined; let reportDocument: unknown;
    if (this.profile) {
      const source = await this.request(`/portfolios/${encodeURIComponent(portfolioId)}/imports/${encodeURIComponent(reportId)}`); this.assertRevision(epoch);
      if (!isObject(source) || source.schema_version !== SCHEMA || source.portfolio_id !== portfolioId) throw new ApiError('INVALID_RESPONSE', 'Report scope mismatch');
      if (source.guarded_report !== undefined) {
        const result = await readGuardedCsvReportRead(source, portfolioId, reportId); this.assertRevision(epoch);
        expectedOperation = result.reference.operation_id; reportDocument = result.report;
      } else {
        const report = readCsvReport(source.report, portfolioId, reportId, true); const metadata = this.readGuarded(source, portfolioId);
        if (!metadata || metadata.operation_id !== report.operation_id || metadata.revision_id !== (report.revision_id ?? report.expected_revision_id)) throw new ApiError('INVALID_RESPONSE', 'Report operation binding mismatch');
        expectedOperation = metadata.operation_id;
      }
    }
    const value = await this.request(`/portfolios/${encodeURIComponent(portfolioId)}/imports/${encodeURIComponent(reportId)}/export?format=${format.toLowerCase()}`, undefined, true); this.assertRevision(epoch);
    if (expectedOperation && (!isObject(value) || value.operationId !== expectedOperation)) throw new ApiError('INVALID_RESPONSE', 'Report download operation mismatch');
    if (reportDocument && format === 'JSON') {
      if (!isObject(value) || typeof value.content !== 'string') throw new ApiError('INVALID_RESPONSE', 'Missing report document');
      let document: unknown; try { document = JSON.parse(value.content); } catch { throw new ApiError('INVALID_RESPONSE', 'Invalid report document'); }
      if (csvReportCanonical(document) !== csvReportCanonical(reportDocument)) throw new ApiError('INVALID_RESPONSE', 'Downloaded report bytes identify a different document');
    }
    return readCsvDownload(value, portfolioId, { reportId }, format);
  }
  async exportPortfolio(portfolioId: string, revisionId: string, kind: 'holdings' | 'transactions', format: 'CSV' | 'JSON') {
    const epoch = this.revision; let expectedOperation: string | undefined;
    if (this.profile) {
      const workspace = await this.workspace(portfolioId, revisionId); this.assertRevision(epoch);
      const metadata = this.readGuarded(workspace, portfolioId, revisionId);
      if (!metadata) throw new ApiError('INVALID_RESPONSE', 'Missing revision operation binding');
      expectedOperation = metadata.operation_id;
    }
    const value = await this.request(`/portfolios/${encodeURIComponent(portfolioId)}/exports/${kind}?revision_id=${encodeURIComponent(revisionId)}&format=${format.toLowerCase()}`, undefined, true); this.assertRevision(epoch);
    if (expectedOperation && (!isObject(value) || value.operationId !== expectedOperation)) throw new ApiError('INVALID_RESPONSE', 'Revision download operation mismatch');
    return readCsvDownload(value, portfolioId, { revisionId }, format);
  }
  async packet(portfolioId: string, insightId: string, revisionId?: string) {
    if (this.profile) throw new ApiError('F3_GUARDED_UNSUPPORTED', 'Legacy packets are unavailable in this fictional profile');
    return readPacketResponse(await this.request(`/portfolios/${encodeURIComponent(portfolioId)}/packets/${encodeURIComponent(insightId)}${revisionQuery(revisionId)}`), portfolioId, insightId);
  }
  async reproduce(portfolioId: string, insightId: string, expected: string, revisionId?: string) {
    if (this.profile) throw new ApiError('F3_GUARDED_UNSUPPORTED', 'Legacy packets are unavailable in this fictional profile');
    const revision = this.revision;
    if (!this.csrf) await this.session(); this.assertRevision(revision);
    return readReproduction(await this.request(`/portfolios/${encodeURIComponent(portfolioId)}/packets/${encodeURIComponent(insightId)}/reproduce${revisionQuery(revisionId)}`,
      { expected_result_digest: expected }), portfolioId, insightId, expected);
  }
  private requireGuarded(): void { if (!this.profile) throw new ApiError('F3_GUARDED_UNSUPPORTED', 'This is not a guarded workspace'); }
  async guardedArchive(portfolioId: string, operationId: string) {
    this.requireGuarded(); const revision = this.revision;
    const value = await this.request(guardedOperationPath(portfolioId, operationId).slice('/api/v1'.length));
    const parsed = await readGuardedArchive(value, { portfolioId, operationId }); this.assertRevision(revision); return parsed;
  }
  async guardedArchiveExport(portfolioId: string, operationId: string) {
    this.requireGuarded(); const revision = this.revision;
    const value = await this.request(`${guardedOperationPath(portfolioId, operationId).slice('/api/v1'.length)}/export`, undefined, true);
    if (!isObject(value) || typeof value.content !== 'string' || value.portfolioId !== portfolioId || value.operationId !== operationId
      || value.redirected !== false || value.noSniff !== 'nosniff' || typeof value.cacheControl !== 'string' || !value.cacheControl.includes('no-store')
      || typeof value.contentType !== 'string' || !value.contentType.startsWith('application/json') || typeof value.disposition !== 'string') throw new ApiError('INVALID_RESPONSE', 'Archive download scope mismatch');
    const filename = /^attachment; filename="(finweb-[a-zA-Z0-9._-]+\.json)"$/.exec(value.disposition)?.[1];
    if (!filename || filename.length > 160) throw new ApiError('INVALID_RESPONSE', 'Unsafe archive download filename');
    let raw: unknown; try { raw = JSON.parse(value.content); } catch { throw new ApiError('INVALID_RESPONSE', 'Invalid archive JSON'); }
    const archive = await readGuardedArchive(raw, { portfolioId, operationId }); this.assertRevision(revision); return { content: value.content, filename, archive };
  }
  async guardedReproduce(portfolioId: string, operationId: string, expectedIssuedSha: string) {
    this.requireGuarded(); const revision = this.revision;
    if (!this.csrf) await this.session(); this.assertRevision(revision);
    return readGuardedReproduction(await this.request(`${guardedOperationPath(portfolioId, operationId).slice('/api/v1'.length)}/reproduce`, {}), { portfolioId, operationId }, expectedIssuedSha);
  }
  private async reconcileGuarded(path: string, binding: GuardedBinding): Promise<GuardedCommitted | GuardedUnknown> {
    this.requireGuarded(); const revision = this.revision;
    const result = await this.request(path, undefined, false, binding); this.assertRevision(revision);
    const committed = await readGuardedCommitted(result, binding); this.assertRevision(revision);
    return committed;
  }
  completeGuardedRecovery(operationId: string): void { this.clearOperation(operationId); }
  async guardedReconcile(portfolioId: string, operationId: string): Promise<GuardedCommitted | GuardedUnknown> {
    try { return await this.reconcileGuarded(`${guardedOperationPath(portfolioId, operationId).slice('/api/v1'.length)}/reconcile`, { portfolioId, operationId }); }
    catch (failure) { if (failure instanceof GuardedOutcomeError && failure.outcome.disposition === 'UNKNOWN') return failure.outcome; throw failure; }
  }
  async guardedCreationReconcile(operationId: string): Promise<GuardedCommitted | GuardedUnknown> {
    if (!guardedUuid(operationId)) throw new ApiError('INVALID_RESPONSE', 'Invalid operation identity');
    try { return await this.reconcileGuarded(`/creation-operations/${operationId}/reconcile`, { operationId }); }
    catch (failure) { if (failure instanceof GuardedOutcomeError && failure.outcome.disposition === 'UNKNOWN') return failure.outcome; throw failure; }
  }
}
