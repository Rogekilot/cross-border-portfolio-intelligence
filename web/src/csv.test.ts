import { afterEach, describe, expect, it, vi } from 'vitest';
import { AccountApi } from './account';
import { readCsvCommit, readCsvDownload, readCsvParse, readCsvPreview, readCsvReport, readCsvSummaries, sameCsvProposal, type CsvProposal } from './csv';
import { SCHEMA } from './transport';
import { csvIssueLabel } from './csv-presentation';
import i18n from './i18n';

// Deliberately synthetic wire records, not financial calculation expectations.
const proposal = (): CsvProposal => ({ operation_id: 'operation', expected_revision_id: 'revision', file_base64: 'a2V5LGFtb3VudApyMSwxCg==', filename: 'fictional.csv',
  kind: 'TRANSACTIONS', as_of: '2026-01-03', source_namespace: 'test-only-source', source_account_key: null, snapshot_key: null, new_account_name: null,
  mapping: { source_row_key: 0, amount: 1 }, constants: {}, corrections: [], classifications: [], format: { delimiter: ',', date_format: 'ISO', decimal_separator: '.', thousands_separator: null }, synthetic_acknowledged: true });
function report() {
  const source = proposal();
  return { schema: 'finweb.csv_import/1', report_id: 'report', portfolio_id: 'portfolio', operation_id: source.operation_id, expected_revision_id: source.expected_revision_id,
    proposal_digest: 'a'.repeat(64), persisted: false, status: 'QUARANTINED', file: { filename: source.filename, sha256: 'b'.repeat(64), byte_count: 20, bom: false }, proposal: source,
    parser: { version: 'csv/cp7-1', dialect: 'stdlib-explicit-v1' }, rows: [
      { row_number: 1, physical_start: 2, physical_end: 2, cells: ['r1', '1'], classification: 'ECONOMIC', reason: '', fields: { source_row_key: 'r1', amount: '1' }, errors: [], event: { account_id: 'account', event_type: 'DEPOSIT', event_date: '2026-01-03', currency: 'USD', amount: '1' }, source_identity: ['portfolio', 'test-only-source', 'TRANSACTIONS', 'account', '', 'r1'], source_key: 'c'.repeat(64), existing_event_id: null, disposition: 'READY', event_id: null },
      { row_number: 2, physical_start: 3, physical_end: 3, cells: ['r2', 'unknown'], classification: 'ECONOMIC', reason: '', fields: { source_row_key: 'r2', amount: 'unknown' }, errors: [{ code: 'EXPLICIT_NATIVE_CURRENCY_REQUIRED', field: null, detail: 'Synthetic test issue' }], event: null, source_identity: null, source_key: null, existing_event_id: null, disposition: 'QUARANTINED', event_id: null },
    ], counts: { total: 2, economic: 2, ready: 1, quarantined: 1, excluded: 0, already_imported: 0, imported: 0 }, batch_errors: [] as unknown[], revision_id: null, created_at: null };
}
const preview = () => ({ schema_version: SCHEMA, portfolio_id: 'portfolio', proposal_digest: 'a'.repeat(64), preview_receipt: 'd'.repeat(64), report: report(), financial_preview: null });
const session = { schema_version: SCHEMA, authenticated: true, user: { user_id: 'user', username: 'test_user' }, csrf_token: 'a'.repeat(64) };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { vi.unstubAllGlobals(); });

describe('CSV preview scope and complete-row semantics', () => {
  it('accepts a mixed valid/invalid economic report only with a null financial preview and imported zero', () => {
    const value = readCsvPreview(preview(), 'portfolio', proposal());
    expect(value.report.counts.ready).toBe(1); expect(value.report.counts.quarantined).toBe(1);
    expect(value.financial_preview).toBeNull(); expect(value.report.counts.imported).toBe(0);
  });
  it('binds the full current proposal, not just a matching operation and head', () => {
    for (const change of [{ file_base64: 'different' }, { source_namespace: 'other' }, { mapping: { amount: 0 } }, { corrections: [{ row_number: 1, fields: { currency: 'USD' }, reason: 'Explicit correction' }] }]) {
      expect(() => readCsvPreview(preview(), 'portfolio', { ...proposal(), ...change })).toThrowError('INVALID_RESPONSE');
    }
    expect(sameCsvProposal({ b: 2, a: { d: 'same', c: 1 } }, { a: { c: 1, d: 'same' }, b: 2 })).toBe(true);
  });
  it('refuses malformed or absent server receipts and foreign response portfolios', () => {
    expect(() => readCsvPreview({ ...preview(), preview_receipt: '' }, 'portfolio', proposal())).toThrow();
    expect(() => readCsvPreview({ ...preview(), preview_receipt: 'z'.repeat(64) }, 'portfolio', proposal())).toThrow();
    expect(() => readCsvPreview(preview(), 'foreign', proposal())).toThrow();
  });
  it('refuses contradictory ready/economic/imported counts and unsaved committed status', () => {
    for (const change of [{ counts: { ...report().counts, ready: 2 } }, { counts: { ...report().counts, economic: 1 } }, { counts: { ...report().counts, imported: 1 } }, { status: 'COMMITTED' }]) {
      expect(() => readCsvReport({ ...report(), ...change }, 'portfolio')).toThrow();
    }
    expect(() => readCsvReport({ ...report(), persisted: true, status: 'READY' }, 'portfolio')).toThrow();
  });
  it('refuses a claimed ready financial batch with no corresponding server financial simulation', () => {
    const value = preview(); value.report.rows = value.report.rows.slice(0, 1); value.report.counts = { total: 1, economic: 1, ready: 1, quarantined: 0, excluded: 0, already_imported: 0, imported: 0 }; value.report.status = 'READY';
    expect(() => readCsvPreview(value, 'portfolio', proposal())).toThrow();
  });
  it('binds an otherwise valid same-portfolio financial preview to the proposal head and as-of date', () => {
    const ready = report(); ready.rows = ready.rows.slice(0, 1); ready.status = 'READY';
    ready.counts = { total: 1, economic: 1, ready: 1, quarantined: 0, excluded: 0, already_imported: 0, imported: 0 };
    const financial = { preview: true, workspace: {
      schema_version: SCHEMA, portfolio_id: 'portfolio', revision_id: 'revision', current_revision_id: 'revision', as_of: '2026-01-03',
      history: [{ revision_id: 'revision', parent_revision_id: null, created_at: '2026-10-19', operation: 'OPENING' }],
      accounts: [{ account_id: 'account', name: 'Synthetic account' }], listings: [],
      ledger: { version: 12, events: [], field_rules: {}, current_state: { convention_set: 'ledger-replay/test', as_of: '2026-01-03', ledger_version: 12, accounts: [] } },
      policies: { state: 'NOT_STATED', items: [], targets: [] },
      benchmark: { state: 'NOT_STATED', pin: { schema: 'finweb.benchmark_selection_pin/1', portfolio_id: 'portfolio', version: 0, state: 'NONE' }, catalog_id: 'catalog', entries: [], selection_available: false },
    }, snapshot: { schema_version: SCHEMA, portfolio_id: 'portfolio', name: 'Transport-only sandbox', mode: 'LOCAL_SYNTHETIC_ACCOUNT', synthetic: true, persisted: false, reporting_currency: 'USD', as_of: '2026-01-03', limitations: ['PREVIEW_NOT_SAVED: transport test'],
      inputs: { positions: [], cash: '1' }, provenance: {}, valuation: { manifest_id: 'v', result_digest: 'v1', metrics: [] }, diversification: { manifest_id: 'd', result_digest: 'd1', metrics: [] }, insights: { manifest_id: 'i', result_digest: 'i1', packets: [], diagnostics: [] } } };
    const value = { ...preview(), report: ready, financial_preview: financial };
    expect(readCsvPreview(value, 'portfolio', proposal()).financial_preview).not.toBeNull();
    const otherHead = structuredClone(value); otherHead.financial_preview.workspace.revision_id = 'other'; otherHead.financial_preview.workspace.current_revision_id = 'other'; otherHead.financial_preview.workspace.history[0].revision_id = 'other';
    expect(() => readCsvPreview(otherHead, 'portfolio', proposal())).toThrow();
    const newerHead = structuredClone(value); newerHead.financial_preview.workspace.current_revision_id = 'newer'; newerHead.financial_preview.workspace.history.push({ revision_id: 'newer', parent_revision_id: null, created_at: '2026-10-19', operation: 'APPEND' });
    expect(() => readCsvPreview(newerHead, 'portfolio', proposal())).toThrow();
    const otherDate = structuredClone(value); otherDate.financial_preview.workspace.as_of = '2026-01-04'; otherDate.financial_preview.workspace.ledger.current_state.as_of = '2026-01-04'; otherDate.financial_preview.snapshot.as_of = '2026-01-04';
    expect(() => readCsvPreview(otherDate, 'portfolio', proposal())).toThrow();
  });
  it('refuses numeric financial event values and preserves original cells in zero-import durable reports', () => {
    const malformed = report(); (malformed.rows[0].event as unknown as { amount: number }).amount = 1;
    expect(() => readCsvReport(malformed, 'portfolio')).toThrow();
    const durable = { ...report(), persisted: true, status: 'REPORT_ONLY', created_at: '2026-10-19' };
    const value = readCsvCommit({ schema_version: SCHEMA, portfolio_id: 'portfolio', report: durable, workspace_result: null }, 'portfolio', proposal());
    expect(value.workspace_result).toBeNull(); expect(value.report.rows[1].cells).toEqual(['r2', 'unknown']);
    expect(() => readCsvCommit({ schema_version: SCHEMA, portfolio_id: 'portfolio', report: { ...durable, counts: { ...durable.counts, imported: 1 } }, workspace_result: null }, 'portfolio', proposal())).toThrow();
  });
  it('refuses an indexed parse for another owner scope and preserves duplicate/blank headers by index', () => {
    const parsed = { schema_version: SCHEMA, portfolio_id: 'portfolio', file_sha256: 'a'.repeat(64), byte_count: 20, bom: true,
      columns: [{ index: 0, header: '' }, { index: 1, header: 'amount' }, { index: 2, header: 'amount' }], rows: [{ row_number: 1, physical_start: 2, physical_end: 3, cells: ['', '1', '2'] }], limits: {} };
    expect(readCsvParse(parsed, 'portfolio').columns.map((column) => column.header)).toEqual(['', 'amount', 'amount']);
    expect(() => readCsvParse(parsed, 'foreign')).toThrow();
  });
  it('gives local recovery instructions for known and unknown row/batch issues while keeping canonical audit text unchanged', async () => {
    const original = report(); const before = JSON.stringify(original);
    await i18n.changeLanguage('zh-CN');
    expect(csvIssueLabel(i18n.t.bind(i18n), 'EXPLICIT_DATE_FORMAT_REQUIRED')).toContain('日期');
    expect(csvIssueLabel(i18n.t.bind(i18n), 'EVENT_LIMIT')).toContain('整批被拒绝');
    expect(csvIssueLabel(i18n.t.bind(i18n), 'unexpected canonical source detail')).toContain('服务器拒绝');
    expect(JSON.stringify(original)).toBe(before); await i18n.changeLanguage('en');
  });
  it('refuses an implicit exclusion or durable report with mismatched source metadata', () => {
    const implicit = report(); implicit.rows[1].classification = 'NON_DATA'; implicit.rows[1].disposition = 'EXCLUDED'; implicit.rows[1].errors = [];
    implicit.counts = { total: 2, economic: 1, ready: 1, quarantined: 0, excluded: 1, already_imported: 0, imported: 0 };
    expect(() => readCsvReport(implicit, 'portfolio')).toThrow();
    expect(() => readCsvReport({ ...report(), persisted: true, status: 'REPORT_ONLY', created_at: '2026-10-19', file: { ...report().file, filename: 'foreign.csv' } }, 'portfolio')).toThrow();
  });
  it('requires an explicit pagination boundary rather than silently treating a partial report page as all history', () => {
    expect(readCsvSummaries({ schema_version: SCHEMA, portfolio_id: 'portfolio', reports: [], next_cursor: 'opaque-next-page' }, 'portfolio').next_cursor).toBe('opaque-next-page');
    expect(() => readCsvSummaries({ schema_version: SCHEMA, portfolio_id: 'portfolio', reports: [] }, 'portfolio')).toThrow();
  });
});

describe('CSV mutation and binary export lifetime', () => {
  it('checks the complete actual commit envelope before any network bootstrap', async () => {
    const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock);
    await expect(new AccountApi().commitCsv('portfolio', { ...proposal(), file_base64: 'a'.repeat(32_000), corrections: [{ row_number: 1, fields: { amount: '1' }, reason: '理由'.repeat(1000) }] }, 'd'.repeat(64)))
      .rejects.toMatchObject({ code: 'CSV_REQUEST_TOO_LARGE' });
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it('keeps raw bytes in a POST body and sends the explicit delimiter with normal CSRF/cookie protection', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(session)).mockResolvedValueOnce(json({ schema_version: SCHEMA, portfolio_id: 'portfolio', file_sha256: 'a'.repeat(64), byte_count: 20, bom: false, columns: [], rows: [], limits: {} })); vi.stubGlobal('fetch', fetchMock);
    const body = { file_base64: proposal().file_base64, filename: 'fictional.csv', delimiter: ';' as const, synthetic_acknowledged: true as const };
    await new AccountApi().parseCsv('portfolio', body);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual(body); expect(fetchMock.mock.calls[1][0]).not.toContain(body.file_base64);
    expect(fetchMock.mock.calls[1][1].credentials).toBe('same-origin'); expect(fetchMock.mock.calls[1][1].headers['X-Finweb-CSRF']).toBe('a'.repeat(64));
  });
  it('never silently retries a commit or substitutes a new operation after a network error', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(session)).mockRejectedValueOnce(new Error('uncertain')); vi.stubGlobal('fetch', fetchMock);
    await expect(new AccountApi().commitCsv('portfolio', proposal(), 'd'.repeat(64))).rejects.toMatchObject({ code: 'NETWORK_ERROR' });
    expect(fetchMock).toHaveBeenCalledTimes(2); expect(JSON.parse(fetchMock.mock.calls[1][1].body).proposal.operation_id).toBe('operation');
  });
  it('requires fixed-scope no-store export headers and refuses a foreign binding or unsafe filename', () => {
    const value = { content: 'source,text\r\nfictional,\'=text', portfolioId: 'portfolio', revisionId: 'revision', reportId: null, contentType: 'text/csv; charset=utf-8', disposition: 'attachment; filename="finweb-transactions-revision.csv"', cacheControl: 'no-store', noSniff: 'nosniff', redirected: false };
    expect(readCsvDownload(value, 'portfolio', { revisionId: 'revision' }, 'CSV').content).toBe(value.content);
    for (const change of [{ portfolioId: 'foreign' }, { revisionId: 'other' }, { disposition: 'attachment; filename="../secret.csv"' }, { redirected: true }, { cacheControl: 'public' }, { contentType: 'text/html' }]) {
      expect(() => readCsvDownload({ ...value, ...change }, 'portfolio', { revisionId: 'revision' }, 'CSV')).toThrow();
    }
  });
  it('discards a late binary body after account identity changes', async () => {
    let finish!: (text: string) => void;
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, redirected: false, headers: new Headers(), text: () => new Promise<string>((resolve) => { finish = resolve; }) }));
    const api = new AccountApi(); const pending = api.exportPortfolio('portfolio', 'revision', 'holdings', 'JSON');
    await Promise.resolve(); api.reset(); finish('private synthetic export');
    await expect(pending).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' });
  });
  it('never delivers a late committed report to a parent callback after changing account/workspace identity, even if fetch ignores abort', async () => {
    let finish!: (value: unknown) => void; const parent = vi.fn();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json(session)).mockResolvedValueOnce({ ok: true, status: 201, json: () => new Promise((resolve) => { finish = resolve; }) }));
    const api = new AccountApi(); await api.session();
    const pending = api.commitCsv('portfolio', proposal(), 'd'.repeat(64)).then((result) => { parent(result); return result; });
    await Promise.resolve(); api.reset();
    finish({ schema_version: SCHEMA, portfolio_id: 'portfolio', report: { ...report(), persisted: true, status: 'REPORT_ONLY', created_at: '2026-10-19' }, workspace_result: null });
    await expect(pending).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' }); expect(parent).not.toHaveBeenCalled();
  });
});
