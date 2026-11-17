import { createHash } from 'node:crypto';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AccountApi } from './account';
import GuardedCsvReportPanel from './GuardedCsvReportPanel';
import { GUARDED_OPERATIONS, GUARDED_PROFILE, GUARDED_UNSUPPORTED, guardedSubmission } from './guarded';
import { assertGuardedCsvSummaries, csvReportCanonical, guardedCsvReportPath, readGuardedCsvReportArchive,
  readGuardedCsvReportCommitted, readGuardedCsvReportDocument, readGuardedCsvReportOutcome, readGuardedCsvReportRead,
  readGuardedCsvReportUnknown } from './guarded-csv-report';
import { guardedTranslations } from './guarded-i18n';
import { csvTranslations } from './csv-i18n';
import type { CsvProposal } from './csv';
import { ApiError, SCHEMA } from './transport';
import i18n from './i18n';

// These are fictional transport/provenance fixtures, never financial calculations.
const root = '10000000-0000-4000-8000-000000000001';
const owner = '20000000-0000-4000-8000-000000000001';
const operation = '30000000-0000-4000-8000-000000000001';
const base = '40000000-0000-4000-8000-000000000001';
const reportId = '50000000-0000-4000-8000-000000000001';
const account = '60000000-0000-4000-8000-000000000001';
const event = '70000000-0000-4000-8000-000000000001';
const priorOperation = '80000000-0000-4000-8000-000000000001';
const other = '90000000-0000-4000-8000-000000000001';
const receipt = 'a'.repeat(64); const context = 'b'.repeat(64);
const rawFile = 'reference,day,type,cash\nfictional-1,2026-01-02,DEPOSIT,5\n';
const hash = (raw: string) => createHash('sha256').update(raw).digest('hex');
const digest = (value: unknown) => hash(csvReportCanonical(value));
const proposal = (): CsvProposal => ({ operation_id: operation, expected_revision_id: base, file_base64: btoa(rawFile), filename: 'fictional.csv',
  kind: 'TRANSACTIONS', as_of: '2026-01-02', source_namespace: 'candidate-fictional', source_account_key: null, snapshot_key: null, new_account_name: null,
  mapping: { source_row_key: 0, event_date: 1, event_type: 2, amount: 3 }, constants: { account_id: account, currency: 'USD' }, corrections: [], classifications: [],
  format: { delimiter: ',', date_format: 'ISO', decimal_separator: '.', thousands_separator: null }, synthetic_acknowledged: true });
const submission = () => guardedSubmission({ proposal: proposal(), preview_receipt: receipt }, operation);
const binding = () => ({ portfolioId: root, operationId: operation, baseRevisionId: base, reportId, ownerId: owner, submission: submission() });
function report() {
  const source = proposal(); const identity = ['EVENT', root, source.source_namespace, 'TRANSACTIONS', account, '', 'fictional-1'];
  return { schema: 'finweb.csv_import/1', report_id: reportId, portfolio_id: root, operation_id: operation, expected_revision_id: base,
    proposal_digest: digest(source), persisted: true, status: 'ALREADY_IMPORTED', file: { filename: source.filename, sha256: hash(rawFile), byte_count: new TextEncoder().encode(rawFile).length, bom: false },
    proposal: source, parser: { version: 'csv/cp7-1', dialect: 'stdlib-explicit-v1' }, rows: [{ row_number: 1, physical_start: 2, physical_end: 2,
      cells: ['fictional-1', '2026-01-02', 'DEPOSIT', '5'], classification: 'ECONOMIC', reason: '', fields: { source_row_key: 'fictional-1', event_date: '2026-01-02', event_type: 'DEPOSIT', amount: '5', account_id: account, currency: 'USD' },
      errors: [] as { code: string; field: string | null; detail: string }[], event: { event_type: 'DEPOSIT', account_id: account, currency: 'USD', event_date: '2026-01-02', amount: '5' } as Record<string, unknown> | null,
      source_identity: identity as string[] | null, source_key: digest(identity) as string | null, existing_event_id: event as string | null, disposition: 'ALREADY_IMPORTED', event_id: event as string | null }],
    counts: { total: 1, economic: 1, ready: 0, quarantined: 0, excluded: 0, already_imported: 1, imported: 0 }, batch_errors: [] as { code: string; detail: string }[], revision_id: null as string | null, created_at: '2026-10-20T00:00:00.000000Z' };
}
function committed(document = report()) {
  const response_json = csvReportCanonical({ report: document, workspace_result: null });
  return { schema: 'finweb.guarded_csv_report/1', profile: GUARDED_PROFILE, disposition: 'REPORT_COMMITTED', synthetic: true,
    portfolio_id: root, operation_id: operation, base_revision_id: base, report_id: reportId, response_json, response_sha256: hash(response_json),
    archive_url: guardedCsvReportPath(root, operation), reconcile_url: `${guardedCsvReportPath(root, operation)}/reconcile` };
}
function unknown() { return { schema: 'finweb.guarded_csv_report/1', profile: GUARDED_PROFILE, disposition: 'UNKNOWN', synthetic: true,
  portfolio_id: root, operation_id: operation, reconcile_url: `${guardedCsvReportPath(root, operation)}/reconcile` }; }
function archive(document = report()) {
  const response = committed(document);
  const envelope = { schema: 'finweb.csv_report_envelope/1', profile: GUARDED_PROFILE, synthetic: true, operation_kind: 'CSV_REPORT_ONLY',
    owner_id: owner, portfolio_id: root, operation_id: operation, report_id: reportId, context_id: context, commit_generation: 1,
    base_revision_id: base, base_operation_id: priorOperation, base_ledger_pin: '100', request_sha256: digest({ proposal: proposal(), preview_receipt: receipt }),
    proposal_sha256: digest(proposal()), preview_receipt_sha256: hash(receipt), response_sha256: response.response_sha256, report_status: document.status, created_at: document.created_at };
  const envelope_json = csvReportCanonical(envelope);
  return { schema: 'finweb.guarded_csv_report_archive/1', profile: GUARDED_PROFILE, synthetic: true, portfolio_id: root, operation_id: operation,
    base_revision_id: base, report_id: reportId, context_id: context, commit_generation: 1, admission_generation: 2,
    response_json: response.response_json, response_sha256: response.response_sha256, envelope_json, envelope_sha256: hash(envelope_json) };
}
const profile = () => ({ schema: 'finweb.guarded_profile/1', profile: GUARDED_PROFILE, synthetic: true, saved_only: true,
  source_as_of: '2026-01-02', opening_date_required: true, opening_date_max: '2026-01-02', opening_date_recommended: '2026-01-01', selector: 'CP5_DIVERSIFICATION', operations: GUARDED_OPERATIONS, unsupported: GUARDED_UNSUPPORTED });
const session = () => ({ schema_version: SCHEMA, authenticated: true, user: { user_id: owner, username: 'fictional_user' }, csrf_token: 'f'.repeat(64), guarded_profile: profile() });
const json = (value: unknown, status = 200, headers?: HeadersInit) => new Response(JSON.stringify(value), { status, headers });
const outcomeCode = (value: Promise<unknown>) => value.then(() => 'ACCEPTED', (error: unknown) => error instanceof ApiError ? error.code : 'UNEXPECTED_ERROR');
function metadata() { const saved = archive(); return { schema: 'finweb.guarded_csv_report_read/1', profile: GUARDED_PROFILE, synthetic: true, portfolio_id: root,
  operation_id: operation, report_id: reportId, base_revision_id: base, context_id: context, commit_generation: 1, admission_generation: 2, response_sha256: saved.response_sha256, archive_url: guardedCsvReportPath(root, operation) }; }
const reportRead = () => ({ schema_version: SCHEMA, portfolio_id: root, report: report(), guarded_report: metadata() });
const summary = () => ({ report_id: reportId, status: 'ALREADY_IMPORTED', created_at: report().created_at, kind: 'TRANSACTIONS', file_sha256: hash(rawFile), counts: report().counts,
  revision_id: null, operation_kind: 'CSV_REPORT_ONLY', operation_id: operation, archive_url: guardedCsvReportPath(root, operation) });
function mutateEnvelope(change: Record<string, unknown>) { const value = archive(); value.envelope_json = csvReportCanonical({ ...JSON.parse(value.envelope_json), ...change }); value.envelope_sha256 = hash(value.envelope_json); return value; }
afterEach(async () => { vi.unstubAllGlobals(); vi.restoreAllMocks(); await i18n.changeLanguage('en'); });

describe('zero-import report strict contract', () => {
  it('bounds canonical nesting and refuses malformed Unicode rather than losing request certainty to an unexpected exception', () => {
    expect(() => csvReportCanonical({ bad: '\ud800' })).toThrow('INVALID_RESPONSE');
    let nested: unknown = 'fictional'; for (let depth = 0; depth < 34; depth += 1) nested = { nested };
    expect(() => csvReportCanonical(nested)).toThrow('INVALID_RESPONSE');
    expect(csvReportCanonical({ z: '😀', a: 1 })).toBe('{"a":1,"z":"😀"}');
  });
  it('accepts a distinct exact duplicate report with its original event, null result and no financial issuance fields', async () => {
    const value = await readGuardedCsvReportCommitted(committed(), binding());
    expect(value.disposition).toBe('REPORT_COMMITTED'); expect(Object.keys(value)).not.toContain('issued_sha256'); expect(Object.keys(value)).not.toContain('revision_id');
    const saved = await readGuardedCsvReportArchive(archive(), binding()); expect(saved.report.rows[0].event_id).toBe(event); expect(saved.report.revision_id).toBeNull();
    expect(saved.wire.admission_generation).toBe(2); expect(saved.wire.commit_generation).toBe(1);
  });
  it('keeps quarantined, excluded and refused whole-batch reports separate from imported money', async () => {
    const quarantined = report(); quarantined.status = 'REPORT_ONLY';
    Object.assign(quarantined.rows[0], { disposition: 'QUARANTINED', event: null, source_identity: null, source_key: null, event_id: null, existing_event_id: null,
      errors: [{ code: 'EXACT_DECIMAL_REQUIRED', field: 'amount', detail: 'Fictional invalid amount' }] });
    Object.assign(quarantined.counts, { already_imported: 0, quarantined: 1 });
    expect((await readGuardedCsvReportCommitted(committed(quarantined), binding())).disposition).toBe('REPORT_COMMITTED');
    const excluded = report(); excluded.status = 'REPORT_ONLY'; Object.assign(excluded.rows[0], { classification: 'NON_DATA', reason: 'Explicit fictional header', disposition: 'EXCLUDED', event: null, source_identity: null, source_key: null, event_id: null, existing_event_id: null });
    Object.assign(excluded.counts, { economic: 0, excluded: 1, already_imported: 0 });
    await expect(readGuardedCsvReportCommitted(committed(excluded), binding())).resolves.toHaveProperty('disposition', 'REPORT_COMMITTED');
    const refused = report(); refused.status = 'REPORT_ONLY'; refused.rows[0].disposition = 'READY'; refused.rows[0].event_id = null; refused.rows[0].existing_event_id = null;
    Object.assign(refused.counts, { ready: 1, already_imported: 0 }); refused.batch_errors = [{ code: 'F2_REQUEST_REFUSED', detail: 'Actual fictional whole-batch refusal' }];
    await expect(readGuardedCsvReportCommitted(committed(refused), binding())).resolves.toHaveProperty('disposition', 'REPORT_COMMITTED');
  });
  it('rejects financial substitutes, contradictory outcome types and payload-bearing UNKNOWN', async () => {
    for (const value of [{ ...committed(), issued_sha256: 'd'.repeat(64) }, { ...committed(), revision_id: base }, { ...committed(), disposition: 'COMMITTED' },
      { ...committed(), portfolio_id: other }, { ...committed(), operation_id: other }, { ...committed(), base_revision_id: other }, { ...committed(), archive_url: 'https://example.invalid' }]) {
      await expect(readGuardedCsvReportCommitted(value, binding())).rejects.toThrow('INVALID_RESPONSE');
    }
    expect(readGuardedCsvReportUnknown(unknown(), binding()).disposition).toBe('UNKNOWN');
    for (const value of [{ ...unknown(), report_id: reportId }, { ...unknown(), imported: 0 }, { ...unknown(), persisted: false }, { ...unknown(), base_revision_id: base }]) expect(() => readGuardedCsvReportUnknown(value, binding())).toThrow();
    await expect(readGuardedCsvReportOutcome(committed(), 202, binding())).rejects.toThrow(); await expect(readGuardedCsvReportOutcome(unknown(), 200, binding())).rejects.toThrow();
  });
  it('refuses tampered bytes, file/proposal/source identity and claimed persisted prospective events', async () => {
    await expect(readGuardedCsvReportCommitted({ ...committed(), response_json: `${committed().response_json} ` }, binding())).rejects.toThrow();
    await expect(readGuardedCsvReportCommitted({ ...committed(), response_sha256: '0'.repeat(64) }, binding())).rejects.toThrow();
    for (const change of [((value: ReturnType<typeof report>) => { value.file.sha256 = '0'.repeat(64); }),
      ((value: ReturnType<typeof report>) => { value.rows[0].source_key = '0'.repeat(64); }),
      ((value: ReturnType<typeof report>) => { value.proposal.source_namespace = 'changed'; value.proposal_digest = digest(value.proposal); }),
      ((value: ReturnType<typeof report>) => { value.rows[0].existing_event_id = other; }),
      ((value: ReturnType<typeof report>) => { value.revision_id = other; })]) {
      const value = report(); change(value); await expect(readGuardedCsvReportCommitted(committed(value), binding())).rejects.toThrow();
    }
    const ready = report(); ready.status = 'REPORT_ONLY'; ready.rows[0].disposition = 'READY'; ready.rows[0].existing_event_id = null;
    Object.assign(ready.counts, { ready: 1, already_imported: 0 }); ready.batch_errors = [{ code: 'BATCH_REFUSED', detail: 'Fictional refusal' }];
    await expect(readGuardedCsvReportCommitted(committed(ready), binding())).rejects.toThrow();
  });
  it('binds the full retained request including receipt, owner, baseline and original commitment in the exact archive', async () => {
    for (const change of [{ request_sha256: '0'.repeat(64) }, { preview_receipt_sha256: '0'.repeat(64) }, { proposal_sha256: '0'.repeat(64) }, { owner_id: other }, { base_revision_id: other }, { operation_kind: 'FINANCIAL_CSV' }, { commit_generation: 2 }]) {
      await expect(readGuardedCsvReportArchive(mutateEnvelope(change), binding())).rejects.toThrow();
    }
    const changed = guardedSubmission({ proposal: proposal(), preview_receipt: 'c'.repeat(64) }, operation);
    await expect(readGuardedCsvReportArchive(archive(), { ...binding(), submission: changed })).rejects.toThrow();
    await expect(readGuardedCsvReportArchive(archive(), { portfolioId: root, operationId: operation, ownerId: owner })).resolves.toHaveProperty('report.report_id', reportId);
  });
  it('rejects an archive whose current admission predates its original commitment, while allowing equal generations', async () => {
    const reversed = mutateEnvelope({ commit_generation: 2 }); reversed.commit_generation = 2; reversed.admission_generation = 1;
    expect(await outcomeCode(readGuardedCsvReportArchive(reversed, binding()))).toBe('INVALID_RESPONSE');
    await expect(readGuardedCsvReportArchive({ ...archive(), admission_generation: 1 }, binding())).resolves.toHaveProperty('wire.admission_generation', 1);
  });
  it('rejects a report GET whose current admission predates commitment without requiring a generation increase', async () => {
    const reversed = { ...reportRead(), guarded_report: { ...metadata(), commit_generation: 2, admission_generation: 1 } };
    expect(await outcomeCode(readGuardedCsvReportRead(reversed, root, reportId))).toBe('INVALID_RESPONSE');
    const equal = { ...reportRead(), guarded_report: { ...metadata(), admission_generation: 1 } };
    await expect(readGuardedCsvReportRead(equal, root, reportId)).resolves.toHaveProperty('reference.admission_generation', 1);
  });
  it('accepts exactly 2000000 UTF-8 response bytes and rejects the next byte even when character count is lower', async () => {
    const document = report(); document.status = 'REPORT_ONLY';
    Object.assign(document.rows[0], { disposition: 'QUARANTINED', event: null, source_identity: null, source_key: null, event_id: null, existing_event_id: null,
      errors: [{ code: 'F2_REQUEST_REFUSED', field: null, detail: '' }] });
    Object.assign(document.counts, { quarantined: 1, already_imported: 0 });
    const remaining = 2_000_000 - new TextEncoder().encode(committed(document).response_json).byteLength;
    document.rows[0].errors[0].detail = '界'.repeat(Math.floor(remaining / 3)) + 'x'.repeat(remaining % 3);
    const exact = committed(document); expect(new TextEncoder().encode(exact.response_json).byteLength).toBe(2_000_000);
    expect(exact.response_json.length).toBeLessThan(2_000_000);
    await expect(readGuardedCsvReportCommitted(exact, binding())).resolves.toHaveProperty('disposition', 'REPORT_COMMITTED');
    document.rows[0].errors[0].detail += 'x'; const over = committed(document);
    expect(new TextEncoder().encode(over.response_json).byteLength).toBe(2_000_001);
    expect(await outcomeCode(readGuardedCsvReportCommitted(over, binding()))).toBe('INVALID_RESPONSE');
  });
  it('refuses source conflicts relabelled as report-only success while allowing an actual mixed quarantined report', async () => {
    const conflicted = report(); conflicted.status = 'REPORT_ONLY'; Object.assign(conflicted.rows[0], { disposition: 'QUARANTINED', event_id: null, errors: [{ code: 'SOURCE_KEY_CONFLICT', field: '*', detail: 'Fictional conflicting source' }] });
    Object.assign(conflicted.counts, { quarantined: 1, already_imported: 0 });
    await expect(readGuardedCsvReportCommitted(committed(conflicted), binding())).rejects.toThrow();
    const mixed = report(); mixed.status = 'REPORT_ONLY'; mixed.rows.push({ ...mixed.rows[0], row_number: 2, physical_start: 3, physical_end: 3,
      cells: ['fictional-2', '2026-01-02', 'DEPOSIT', 'bad'], fields: { ...mixed.rows[0].fields, source_row_key: 'fictional-2', amount: 'bad' }, disposition: 'QUARANTINED', event: null, source_identity: null, source_key: null, event_id: null, existing_event_id: null,
      errors: [{ code: 'EXACT_DECIMAL_REQUIRED', field: 'amount', detail: 'Explicit fictional invalid row' }] });
    const mixedFile = `${rawFile}fictional-2,2026-01-02,DEPOSIT,bad\n`; mixed.proposal.file_base64 = btoa(mixedFile); mixed.proposal_digest = digest(mixed.proposal);
    Object.assign(mixed.file, { sha256: hash(mixedFile), byte_count: new TextEncoder().encode(mixedFile).length }); Object.assign(mixed.counts, { total: 2, economic: 2, quarantined: 1 });
    const expected = { ...binding(), submission: guardedSubmission({ proposal: mixed.proposal, preview_receipt: receipt }, operation) };
    await expect(readGuardedCsvReportCommitted(committed(mixed), expected)).resolves.toHaveProperty('disposition', 'REPORT_COMMITTED');
  });
  it('validates report-specific GET metadata without accepting invented financial metadata', async () => {
    await expect(readGuardedCsvReportRead(reportRead(), root, reportId)).resolves.toHaveProperty('reference.schema', 'finweb.guarded_csv_report_read/1');
    for (const value of [{ ...reportRead(), guarded: {} }, { ...reportRead(), guarded_report: { ...metadata(), response_sha256: '0'.repeat(64) } }, { ...reportRead(), guarded_report: { ...metadata(), base_revision_id: other } }]) {
      await expect(readGuardedCsvReportRead(value, root, reportId)).rejects.toThrow();
    }
    await expect(readGuardedCsvReportRead(reportRead(), root, other)).rejects.toThrow();
  });
  it('requires combined-list kinds and correct operation paths with bounded opaque cursors', () => {
    const financial = { ...summary(), report_id: other, status: 'COMMITTED', revision_id: base, counts: { ...report().counts, ready: 1, already_imported: 0, imported: 1 }, operation_kind: 'FINANCIAL_CSV', archive_url: `/api/v1/portfolios/${root}/operations/${operation}` };
    expect(() => assertGuardedCsvSummaries({ reports: [summary(), financial], next_cursor: null }, root)).not.toThrow();
    for (const value of [{ reports: [{ ...summary(), operation_kind: 'FINANCIAL_CSV' }], next_cursor: null }, { reports: [{ ...summary(), archive_url: financial.archive_url }], next_cursor: null },
      { reports: [summary(), summary()], next_cursor: null }, { reports: [], next_cursor: 'x'.repeat(513) }]) expect(() => assertGuardedCsvSummaries(value, root)).toThrow();
  });
});

describe('report client identity, acknowledgement and recovery', () => {
  it('uses only the dedicated report POST and its exact archive before publishing report success', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => url.endsWith('/auth/session') ? json(session()) : init?.method === 'POST' ? json(committed()) : json(archive()));
    vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); const financial = vi.fn(); const reference = vi.fn(); api.onGuardedReference = financial; api.onGuardedCsvReportReference = reference;
    await api.session(); const value = await api.commitCsvReport(root, proposal(), receipt);
    expect(value.workspace_result).toBeNull(); expect(value.report.counts.imported).toBe(0); expect(financial).not.toHaveBeenCalled(); expect(reference).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/v1/auth/session', guardedCsvReportPath(root), guardedCsvReportPath(root, operation)]);
  });
  it('retains the same request after lost acknowledgement, blocks another write and retries only explicitly', async () => {
    let posts = 0; const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/session')) return json(session()); if (init?.method === 'POST') { posts += 1; if (posts === 1) throw new Error('Fictional lost acknowledgement'); return json(committed()); } return json(archive());
    });
    vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); const pending = vi.fn(); api.onGuardedPending = pending; await api.session();
    await expect(api.commitCsvReport(root, proposal(), receipt)).rejects.toMatchObject({ code: 'F3_OUTCOME_UNKNOWN', operationId: operation });
    expect(pending).toHaveBeenLastCalledWith({ operationId: operation, portfolioId: root, kind: 'CSV_REPORT', baseRevisionId: base });
    await expect(api.commitCsvReport(root, { ...proposal(), operation_id: other }, receipt)).rejects.toMatchObject({ code: 'F3_PENDING_OPERATION' }); expect(posts).toBe(1);
    await expect(api.retryGuardedOperation(operation)).rejects.toMatchObject({ code: 'F3_OUTCOME_UNKNOWN' });
    const value = await api.retryGuardedCsvReportOperation(operation); expect(value.disposition).toBe('REPORT_COMMITTED'); expect(posts).toBe(2);
    const writes = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST'); expect(writes[0][1]?.body).toBe(writes[1][1]?.body); expect(pending).toHaveBeenLastCalledWith(null);
  });
  it('keeps an absent report query UNKNOWN without automatic retry or clearing the original request', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => url.endsWith('/auth/session') ? json(session()) : init?.method === 'POST' ? json(unknown(), 202) : json(unknown(), 202));
    vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); const pending = vi.fn(); api.onGuardedPending = pending; await api.session();
    await expect(api.commitCsvReport(root, proposal(), receipt)).rejects.toMatchObject({ code: 'F3_OUTCOME_UNKNOWN' });
    const value = await api.guardedCsvReportReconcile(root, operation); expect(value.disposition).toBe('UNKNOWN'); expect(pending).not.toHaveBeenCalledWith(null);
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  });
  it('does not publish a received 200 until its original request evidence matches, then recovers the same operation', async () => {
    let correctArchive = false; const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/session')) return json(session()); if (init?.method === 'POST' || url.endsWith('/reconcile')) return json(committed());
      return json(correctArchive ? archive() : mutateEnvelope({ request_sha256: '0'.repeat(64) }));
    });
    vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); const pending = vi.fn(); const reference = vi.fn(); api.onGuardedPending = pending; api.onGuardedCsvReportReference = reference; await api.session();
    await expect(api.commitCsvReport(root, proposal(), receipt)).rejects.toMatchObject({ code: 'F3_OUTCOME_UNKNOWN', causeCode: 'F3_REPORT_EVIDENCE_UNVERIFIED' }); expect(reference).not.toHaveBeenCalled();
    correctArchive = true; const value = await api.guardedCsvReportReconcile(root, operation); expect(value.disposition).toBe('REPORT_COMMITTED'); expect(pending).not.toHaveBeenCalledWith(null);
    api.completeGuardedRecovery(operation); expect(pending).toHaveBeenLastCalledWith(null); expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  });
  it('suppresses saved report callbacks if identity changes during evidence fetch', async () => {
    let finish: ((value: Response) => void) | undefined; let evidenceStarted: (() => void) | undefined;
    const started = new Promise<void>((resolve) => { evidenceStarted = resolve; });
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/session')) return json(session()); if (init?.method === 'POST') return json(committed());
      evidenceStarted?.(); return new Promise<Response>((resolve) => { finish = resolve; });
    }));
    const api = new AccountApi(); const reference = vi.fn(); api.onGuardedCsvReportReference = reference; await api.session();
    const result = api.commitCsvReport(root, proposal(), receipt); await started; api.reset(); finish?.(json(archive()));
    await expect(result).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' }); expect(reference).not.toHaveBeenCalled();
  });
  it('suppresses saved report callbacks if identity changes during a WebCrypto await', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/auth/session') ? json(session()) : json(committed())));
    const api = new AccountApi(); const reference = vi.fn(); api.onGuardedCsvReportReference = reference; await api.session();
    const original = crypto.subtle.digest.bind(crypto.subtle); let finish: ((value: ArrayBuffer) => void) | undefined; let digestStarted: (() => void) | undefined;
    const started = new Promise<void>((resolve) => { digestStarted = resolve; });
    vi.spyOn(crypto.subtle, 'digest').mockImplementationOnce(async (algorithm, bytes) => { const real = await original(algorithm, bytes); digestStarted?.(); return new Promise<ArrayBuffer>((resolve) => { finish = () => resolve(real); }); });
    const result = api.commitCsvReport(root, proposal(), receipt); await started; api.reset(); finish?.(new ArrayBuffer(0));
    await expect(result).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' }); expect(reference).not.toHaveBeenCalled();
  });
  it('refuses unsupported holdings report submissions before any report request', async () => {
    const fetchMock = vi.fn(async () => json(session())); vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); await api.session();
    await expect(api.commitCsvReport(root, { ...proposal(), kind: 'HOLDINGS' }, receipt)).rejects.toMatchObject({ code: 'F3_CSV_REPORT_HOLDINGS_UNSUPPORTED' }); expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('never accepts a report success as financial create success', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/auth/session') ? json(session()) : json(committed())));
    const api = new AccountApi(); const financial = vi.fn(); const reportReference = vi.fn(); api.onGuardedReference = financial; api.onGuardedCsvReportReference = reportReference; await api.session();
    await expect(api.create({ operation_id: operation, opening_date: '2026-01-01', name: 'Fictional transport only', reporting_currency: 'USD', cash: '0', positions: [], synthetic_acknowledged: true })).rejects.toMatchObject({ code: 'F3_OUTCOME_UNKNOWN' });
    expect(financial).not.toHaveBeenCalled(); expect(reportReference).not.toHaveBeenCalled();
  });
  it('opens and exports the exact report document using report metadata, preserving financial callback isolation', async () => {
    const fetchMock = vi.fn(async (url: string) => url.endsWith('/auth/session') ? json(session()) : url.endsWith('format=json') ? new Response(csvReportCanonical(report()), { headers: {
      'Content-Type': 'application/json', 'Content-Disposition': `attachment; filename="finweb-report-${reportId}.json"`, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
      'X-Finweb-Portfolio-Id': root, 'X-Finweb-Operation-Id': operation, 'X-Finweb-Report-Id': reportId,
    } }) : json(reportRead()));
    vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); const financial = vi.fn(); const reportReference = vi.fn(); api.onGuardedReference = financial; api.onGuardedCsvReportReference = reportReference; await api.session();
    await expect(api.csvReport(root, reportId)).resolves.toHaveProperty('report_id', reportId); expect(reportReference).toHaveBeenCalledTimes(1); expect(financial).not.toHaveBeenCalled();
    await expect(api.exportCsvReport(root, reportId, 'JSON')).resolves.toHaveProperty('filename', `finweb-report-${reportId}.json`);
  });
  it('checks report archive download headers, owner and body against the requested operation', async () => {
    let badHeader = false; const fetchMock = vi.fn(async (url: string) => url.endsWith('/auth/session') ? json(session()) : new Response(JSON.stringify(archive()), { headers: {
      'Content-Type': 'application/json', 'Content-Disposition': `attachment; filename="finweb-csv-report-${reportId}.json"`, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
      'X-Finweb-Portfolio-Id': root, 'X-Finweb-Operation-Id': operation, 'X-Finweb-Report-Id': badHeader ? other : reportId,
    } }));
    vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); await api.session(); await expect(api.guardedCsvReportArchiveExport(root, operation)).resolves.toHaveProperty('filename', `finweb-csv-report-${reportId}.json`);
    badHeader = true; await expect(api.guardedCsvReportArchiveExport(root, operation)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
});

describe('report presentation scope', () => {
  it('keeps report recovery explicit and offers no financial reproduction control', async () => {
    await i18n.changeLanguage('en'); const retry = vi.fn(); const recover = vi.fn();
    const html = renderToStaticMarkup(createElement(GuardedCsvReportPanel, { api: new AccountApi(), pending: { operationId: operation, portfolioId: root, kind: 'CSV_REPORT', baseRevisionId: base }, onRecovered: recover, onRetry: retry }));
    expect(html).toContain(guardedTranslations.en.guardedCsvReportUnknownHint); expect(html).toContain(operation); expect(html).toContain(guardedTranslations.en.guardedReconcile);
    expect(html).not.toContain(guardedTranslations.en.guardedReproduce); expect(retry).not.toHaveBeenCalled(); expect(recover).not.toHaveBeenCalled();
  });
  it('retains matching bilingual report labels and explicitly unimported candidate event wording', () => {
    expect(Object.keys(guardedTranslations.en).sort()).toEqual(Object.keys(guardedTranslations['zh-CN']).sort());
    expect(Object.keys(csvTranslations.en).sort()).toEqual(Object.keys(csvTranslations['zh-CN']).sort());
    expect(csvTranslations.en.csvProposedEvent).toContain('not imported'); expect(csvTranslations['zh-CN'].csvProposedEvent).toContain('尚未入账');
    expect(guardedTranslations['zh-CN'].guardedCsvReportCommitted).toContain('没有新增组合版本');
  });
  it('rejects a body claiming duplicate success with no duplicated source event', async () => {
    const value = report(); value.rows[0].disposition = 'READY'; value.rows[0].existing_event_id = null; value.rows[0].event_id = null;
    Object.assign(value.counts, { ready: 1, already_imported: 0 });
    await expect(readGuardedCsvReportDocument(value, binding())).rejects.toThrow();
  });
});
