import { createHash } from 'node:crypto';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AccountApi } from './account';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { ErrorNotice } from './App';
import i18n from './i18n';
import { SCHEMA } from './transport';
import { guardedTranslations } from './guarded-i18n';
import { GUARDED_OPERATIONS, GUARDED_PROFILE, GUARDED_UNSUPPORTED, GUARDED_OUTPUT_BYTES, guardedOperationPath,
  guardedResponseText, guardedSubmission, readGuardedArchive, readGuardedCommitted, readGuardedOutcome,
  readGuardedProfile, readGuardedRead, readGuardedRefused, readGuardedReproduction, readGuardedUnknown, validGuardedOpeningDate, GuardedUnconfirmedError } from './guarded';

const root = '11111111-1111-4111-8111-111111111111';
const op = '22222222-2222-4222-8222-222222222222';
const revision = '33333333-3333-4333-8333-333333333333';
const owner = '44444444-4444-4444-8444-444444444444';
const other = '55555555-5555-4555-8555-555555555555';
const context = 'a'.repeat(64); const manifest = 'b'.repeat(64); const result = 'c'.repeat(64);
const hash = (raw: string) => createHash('sha256').update(raw, 'utf8').digest('hex');
const binding = { portfolioId: root, operationId: op };
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const profile = () => ({ schema: 'finweb.guarded_profile/1', profile: GUARDED_PROFILE, synthetic: true, saved_only: true,
  source_as_of: '2026-01-02', opening_date_required: true, opening_date_max: '2026-01-02', opening_date_recommended: '2026-01-01',
  selector: 'CP5_DIVERSIFICATION', operations: [...GUARDED_OPERATIONS], unsupported: [...GUARDED_UNSUPPORTED] });
const readMeta = () => ({ schema: 'finweb.guarded_read/1', profile: GUARDED_PROFILE, portfolio_id: root, revision_id: revision,
  operation_id: op, context_id: context, generation: 2, issued_sha256: 'd'.repeat(64), archived_response_sha256: 'e'.repeat(64),
  archive_url: `/api/v1/portfolios/${root}/operations/${op}` });
function committed() {
  const response_json = JSON.stringify({ portfolio_id: root, name: 'Invented zero-only transport fixture', cash: '0' });
  return { schema: 'finweb.guarded_http/1', profile: GUARDED_PROFILE, disposition: 'COMMITTED', synthetic: true,
    portfolio_id: root, operation_id: op, revision_id: revision, response_json, response: { portfolio_id: other, cash: '999' },
    response_sha256: hash(response_json), issued_sha256: 'd'.repeat(64), archive_url: guardedOperationPath(root, op),
    reconcile_url: `${guardedOperationPath(root, op)}/reconcile` };
}
const unknown = () => ({ schema: 'finweb.guarded_http/1', profile: GUARDED_PROFILE, disposition: 'UNKNOWN', synthetic: true,
  portfolio_id: root, operation_id: op, reconcile_url: `${guardedOperationPath(root, op)}/reconcile` });
function artifact() {
  const question = { schema: 'finweb.local_fictional.service_question/1', selector: 'CP5_DIVERSIFICATION', owner_id: owner,
    root_id: root, revision_id: revision, operation_id: op, portfolio_id: root, ledger_pin: '3', as_of: '2026-01-02',
    context_id: context, generation: 1, account_scope: null, reporting_currency: 'USD' };
  const issued = { manifest: { schema: 'finweb.diversification_manifest/1', synthetic: true, portfolio_id: root,
    engine_id: 'diversification/cp5-0.2', as_of: '2026-01-02', reporting_currency: 'USD' }, manifest_id: manifest, result_digest: result,
    metrics: [{ metric_id: 'portfolio_value', subject: [], value: '0', state: 'AVAILABLE', reason: null, details: [],
      exact: '0/1', exact_square: null, observation_count: null, sign: null, radical_terms: [], manifest_id: manifest }],
    clusters: [], exposure_decompositions: [] };
  const issued_json = JSON.stringify(issued); const response_json = JSON.stringify({ portfolio_id: root, cash: '0' });
  const question_json = JSON.stringify(question);
  const native = { schema: 'finweb.local_fictional.service_binding/1', question, question_sha256: hash(question_json),
    context_snapshot_sha256: context, generation: 1, family: 'CP5_DIVERSIFICATION', engine_id: 'diversification/cp5-0.2',
    manifest_id: manifest, result_digest: result, issued_sha256: hash(issued_json), synthetic: true, release_id: 'f'.repeat(64),
    source_registry_digest: '1'.repeat(64), consumed_identity_digest: '2'.repeat(64), f8b_policy: [] };
  const native_json = JSON.stringify(native);
  const envelope = { schema: 'finweb.f2.fictional-issued-envelope/1', synthetic: true, actual_executor: 'local_application',
    approval_scope: 'fictional_local_only', owner_id: owner, root_id: root, operation_id: op, revision_id: revision, ledger_pin: 3,
    context_id: context, generation: 1, issued_sha256: hash(issued_json), response_sha256: hash(response_json),
    family: 'CP5_DIVERSIFICATION', engine_id: 'diversification/cp5-0.2', manifest_id: manifest, result_digest: result,
    question_sha256: hash(question_json), binding_sha256: hash(native_json), question_hex: Buffer.from(question_json).toString('hex'),
    binding_hex: Buffer.from(native_json).toString('hex'), selector: 'CP5_DIVERSIFICATION',
    fixture_quotes_sha256: '3'.repeat(64), fixture_calendar_sha256: '4'.repeat(64) };
  const envelope_json = JSON.stringify(envelope);
  return { schema: 'finweb.guarded_archive/1', profile: GUARDED_PROFILE, synthetic: true, portfolio_id: root, operation_id: op,
    revision_id: revision, context_id: context, generation: 1, admission_generation: 2, issued_json, response_json, envelope_json,
    issued_sha256: hash(issued_json), response_sha256: hash(response_json), envelope_sha256: hash(envelope_json) };
}

describe('guarded fictional capability and byte transport', () => {
  it('accepts only the exact frozen profile and distinct opening/source dates', () => {
    const value = readGuardedProfile(profile()); expect(value.profile).toBe('F3_FICTIONAL_CP5');
    expect(validGuardedOpeningDate('2026-01-01', value)).toBe(true); expect(validGuardedOpeningDate('2026-01-02', value)).toBe(true);
    for (const date of ['2026-01-03', '2025-02-30', '2026-1-1', '0000-01-01']) expect(validGuardedOpeningDate(date, value)).toBe(false);
    for (const wrong of [{ ...profile(), synthetic: false }, { ...profile(), profile: 'REAL' }, { ...profile(), grant: true },
      { ...profile(), operations: [...GUARDED_OPERATIONS].reverse() }]) expect(() => readGuardedProfile(wrong)).toThrow();
  });
  it('retains exact immutable request bytes without creating an operation or performing a retry', () => {
    const body = { operation_id: op, cash: '0', opening_date: '2026-01-01' }; const saved = guardedSubmission(body);
    body.cash = '999'; expect(saved.requestJson).toBe(`{"operation_id":"${op}","cash":"0","opening_date":"2026-01-01"}`);
    expect(saved.operationId).toBe(op); expect(Object.isFrozen(saved)).toBe(true);
    expect(() => guardedSubmission({ operation_id: 'not-a-uuid' })).toThrow();
    expect(() => guardedSubmission({ operation_id: op, text: 'x'.repeat(32_768) })).toThrow();
  });
  it('bounds actual streamed bytes and rejects invalid UTF-8 before any JSON parser', async () => {
    const raw = new Response('中文', { headers: { 'Content-Length': '6' } }); expect(await guardedResponseText(raw)).toBe('中文');
    await expect(guardedResponseText(new Response('x', { headers: { 'Content-Length': String(GUARDED_OUTPUT_BYTES + 1) } }))).rejects.toThrow();
    await expect(guardedResponseText(new Response(new Uint8Array([0xff])))).rejects.toThrow();
    let cancelled = false;
    const stream = new ReadableStream<Uint8Array>({ start(controller) { controller.enqueue(new Uint8Array(GUARDED_OUTPUT_BYTES)); controller.enqueue(new Uint8Array([1])); }, cancel() { cancelled = true; } });
    await expect(guardedResponseText(new Response(stream))).rejects.toThrow(); expect(cancelled).toBe(true);
  });
  it('uses normative raw bytes rather than the contradictory convenience response', async () => {
    const parsed = await readGuardedCommitted(committed(), binding); expect(parsed.response.cash).toBe('0'); expect(parsed.response.portfolio_id).toBe(root);
    await expect(readGuardedCommitted({ ...committed(), response_json: '{"portfolio_id":"foreign"}' }, binding)).rejects.toThrow();
    await expect(readGuardedCommitted(committed(), { ...binding, operationId: other })).rejects.toThrow();
    await expect(readGuardedCommitted({ ...committed(), archive_url: 'https://example.invalid/' }, binding)).rejects.toThrow();
  });
  it('requires UNKNOWN exact keys and matching HTTP disposition without numeric or rollback claims', async () => {
    expect(readGuardedUnknown(unknown(), binding).disposition).toBe('UNKNOWN');
    for (const wrong of [{ ...unknown(), response: {} }, { ...unknown(), persisted: false }, { ...unknown(), economic_writes: 0 }]) expect(() => readGuardedUnknown(wrong, binding)).toThrow();
    await expect(readGuardedOutcome(unknown(), 200, binding)).rejects.toThrow();
    await expect(readGuardedOutcome(committed(), 202, binding)).rejects.toThrow();
  });
  it('keeps actual refused diagnostic bytes separate from any successful financial value', async () => {
    const issued_json = '{"metrics":[{"state":"INSUFFICIENT_DATA","value":null}]}';
    const value = { schema: 'finweb.guarded_http/1', profile: GUARDED_PROFILE, disposition: 'REFUSED', synthetic: true, portfolio_id: root,
      operation_id: op, error: { code: 'SYNTHETIC_MARKET_DATA_REFUSED', detail: 'Invented refusal transport fixture', state: 'INSUFFICIENT_DATA' },
      issued_json, issued_sha256: hash(issued_json) };
    expect((await readGuardedRefused(value, binding)).issued_json).toBe(issued_json);
    await expect(readGuardedRefused({ ...value, response: { value: '0' } }, binding)).rejects.toThrow();
    const numeric = '{"metrics":[{"state":"AVAILABLE","value":"0"}]}';
    await expect(readGuardedRefused({ ...value, issued_json: numeric, issued_sha256: hash(numeric) }, binding)).rejects.toThrow();
  });
  it('binds pure reads to their selected root/revision and rejects unsafe generation rounding', () => {
    expect(readGuardedRead(readMeta(), root, revision).generation).toBe(2);
    for (const generation of [0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, Infinity]) expect(() => readGuardedRead({ ...readMeta(), generation }, root)).toThrow();
    expect(() => readGuardedRead(readMeta(), other)).toThrow(); expect(() => readGuardedRead(readMeta(), root, other)).toThrow();
    expect(() => guardedOperationPath(root, '../escape')).toThrow();
  });
});

describe('exact archived CP5 bindings and explicit reproduction', () => {
  it('accepts a current generation2 read of original generation1 bytes and preserves exact zero', async () => {
    const wire = artifact(); const parsed = await readGuardedArchive(wire, binding);
    expect(parsed.wire.admission_generation).toBe(2); expect(parsed.issuedGeneration).toBe(1); expect(parsed.metrics[0].value).toBe('0');
    expect(parsed.wire.issued_json).toBe(wire.issued_json);
  });
  it('rejects archive byte tampering, extra fields and foreign operation metadata', async () => {
    for (const wire of [{ ...artifact(), issued_json: artifact().issued_json + ' ' }, { ...artifact(), admin: true },
      { ...artifact(), operation_id: other }, { ...artifact(), admission_generation: Number.MAX_SAFE_INTEGER + 1 }]) await expect(readGuardedArchive(wire, binding)).rejects.toThrow();
  });
  it('rejects internally rehashed native root/generation/ledger binding substitutions', async () => {
    for (const patch of [{ root_id: other }, { generation: 3 }, { ledger_pin: Number.MAX_SAFE_INTEGER + 1 }]) {
      const wire = artifact(); const envelope_json = JSON.stringify({ ...JSON.parse(wire.envelope_json), ...patch });
      await expect(readGuardedArchive({ ...wire, envelope_json, envelope_sha256: hash(envelope_json) }, binding)).rejects.toThrow();
    }
  });
  it('never promotes a truthy mismatch or a wrong hash to REPRODUCED', () => {
    const value = { schema: 'finweb.guarded_reproduce/1', profile: GUARDED_PROFILE, synthetic: true,
      portfolio_id: root, operation_id: op, status: 'REPRODUCED', detail: '', issued_sha256: 'd'.repeat(64) };
    expect(readGuardedReproduction(value, binding, 'd'.repeat(64)).status).toBe('REPRODUCED');
    expect(() => readGuardedReproduction({ ...value, issued_sha256: 'e'.repeat(64) }, binding, 'd'.repeat(64))).toThrow();
    expect(readGuardedReproduction({ ...value, status: 'RESULT_DIFFERS', issued_sha256: 'e'.repeat(64) }, binding, 'd'.repeat(64)).status).toBe('RESULT_DIFFERS');
    expect(() => readGuardedReproduction({ ...value, operation_id: other }, binding, 'd'.repeat(64))).toThrow();
  });
  it('provides matching English and Chinese recovery/evidence labels', () => {
    expect(Object.keys(guardedTranslations.en).sort()).toEqual(Object.keys(guardedTranslations['zh-CN']).sort());
    expect(guardedTranslations.en.guardedUnknownHint).toContain('same operation');
    expect(guardedTranslations['zh-CN'].guardedUnknownHint).toContain('不要替换');
  });
  it('rejects alternate numeric witnesses even when insufficient archive/refusal byte hashes are self-consistent', async () => {
    for (const alternate of [{ exact: '1/1' }, { exact_square: '1/1' }, { sign: 1 }, { radical_terms: [['1/1', '1/1']] }]) {
      const wire = artifact(); const issued = JSON.parse(wire.issued_json);
      issued.metrics[0] = { ...issued.metrics[0], state: 'INSUFFICIENT_DATA', value: null, exact: null, details: ['INVENTED_MISSING_INPUT'], ...alternate };
      wire.issued_json = JSON.stringify(issued); wire.issued_sha256 = hash(wire.issued_json);
      const envelope = JSON.parse(wire.envelope_json); const native = JSON.parse(Buffer.from(envelope.binding_hex, 'hex').toString('utf8'));
      native.issued_sha256 = wire.issued_sha256; const native_json = JSON.stringify(native);
      envelope.issued_sha256 = wire.issued_sha256; envelope.binding_hex = Buffer.from(native_json).toString('hex'); envelope.binding_sha256 = hash(native_json);
      wire.envelope_json = JSON.stringify(envelope); wire.envelope_sha256 = hash(wire.envelope_json);
      await expect(readGuardedArchive(wire, binding)).rejects.toThrow();
      const issued_json = JSON.stringify({ metrics: [{ state: 'INSUFFICIENT_DATA', value: null, ...alternate }] });
      await expect(readGuardedRefused({ schema: 'finweb.guarded_http/1', profile: GUARDED_PROFILE, disposition: 'REFUSED', synthetic: true,
        portfolio_id: root, operation_id: op, error: { code: 'SOURCE_REFUSED', detail: 'Invented diagnostic', state: 'INSUFFICIENT_DATA' },
        issued_json, issued_sha256: hash(issued_json) }, binding)).rejects.toThrow();
    }
  });
});

const session = () => ({ schema_version: SCHEMA, authenticated: true, user: { user_id: owner, username: 'f3_transport_only' },
  csrf_token: 'f'.repeat(64), guarded_profile: profile() });
function snapshotCommit() {
  const response_json = JSON.stringify({ schema_version: SCHEMA, portfolio_id: root, name: 'Fictional transport only', mode: 'LOCAL_SYNTHETIC_ACCOUNT',
    synthetic: true, persisted: true, reporting_currency: 'USD', as_of: '2026-01-02', limitations: [], inputs: { cash: '1', positions: [] },
    valuation: { manifest_id: manifest, result_digest: result, metrics: [] }, diversification: { manifest_id: manifest, result_digest: result, metrics: [] },
    insights: { manifest_id: manifest, result_digest: result, packets: [], diagnostics: [] }, provenance: {} });
  return { ...committed(), response_json, response_sha256: hash(response_json), response: JSON.parse(response_json) };
}
const createInput = () => ({ name: 'Fictional transport only', reporting_currency: 'USD' as const, positions: [], cash: '1',
  synthetic_acknowledged: true as const, operation_id: op, opening_date: '2026-01-01' });
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });

describe('guarded authenticated client lifetime', () => {
  it('does not automatically retry a lost create; manual retry sends the exact original UUID/body', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(session())).mockRejectedValueOnce(new TypeError('Invented transport loss'))
      .mockResolvedValueOnce(json(snapshotCommit()));
    vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); const pending = vi.fn(); api.onGuardedPending = pending;
    await api.session(); await expect(api.create(createInput())).rejects.toMatchObject({ code: 'F3_OUTCOME_UNKNOWN', causeCode: 'NETWORK_ERROR', operationId: op, portfolioId: undefined, status: 0 });
    expect(fetchMock).toHaveBeenCalledTimes(2); expect(pending).toHaveBeenLastCalledWith({ operationId: op });
    const result = await api.retryGuardedOperation(op); expect(result.disposition).toBe('COMMITTED');
    expect(fetchMock.mock.calls[1][1].body).toBe(fetchMock.mock.calls[2][1].body);
    expect(JSON.parse(fetchMock.mock.calls[2][1].body).operation_id).toBe(op); expect(fetchMock).toHaveBeenCalledTimes(3);
  });
  it('rechecks the identity after WebCrypto and prevents a stale private commit from publishing', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(session())).mockResolvedValueOnce(json(snapshotCommit())); vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi(); const reference = vi.fn(); api.onGuardedReference = reference; await api.session();
    let started!: () => void; let release!: () => void;
    const reached = new Promise<void>((resolve) => { started = resolve; }); const barrier = new Promise<void>((resolve) => { release = resolve; });
    const actualDigest = crypto.subtle.digest.bind(crypto.subtle);
    vi.spyOn(crypto.subtle, 'digest').mockImplementationOnce(async (algorithm, bytes) => { started(); await barrier; return actualDigest(algorithm, bytes); });
    const pending = api.create(createInput()); await reached; api.reset(); release();
    await expect(pending).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' }); expect(reference).not.toHaveBeenCalled();
  });
  it('renders explicit uncertain-write guidance without generic retry advice or a fabricated root', async () => {
    await i18n.changeLanguage('en'); const error = new GuardedUnconfirmedError(op, undefined, 'NETWORK_ERROR', 0);
    const html = renderToStaticMarkup(createElement(ErrorNotice, { error }));
    expect(html).toContain(guardedTranslations.en.guardedUnknown); expect(html).toContain(guardedTranslations.en.guardedUnknownHint);
    expect(html).not.toContain(i18n.t('retryHint')); expect(error.portfolioId).toBeUndefined(); expect(error.status).toBe(0);
  });
  it('uses the server rootless creation lookup and preserves an absent operation as UNKNOWN', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(session())).mockResolvedValueOnce(json(unknown(), 202)); vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi(); await api.session(); const value = await api.guardedCreationReconcile(op);
    expect(value.disposition).toBe('UNKNOWN'); expect(fetchMock.mock.calls[1][0]).toBe(`/api/v1/creation-operations/${op}/reconcile`);
    expect(fetchMock.mock.calls[1][1].method).toBe('GET'); expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(value).not.toHaveProperty('response'); expect(value).not.toHaveProperty('economic_writes');
  });
  it('keeps an ambiguous preview typed UNKNOWN without displaying or retrying a saved result', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(session())).mockResolvedValueOnce(json(unknown(), 202)); vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi(); await api.session();
    await expect(api.ledgerCommand(root, { operation_id: op, expected_revision_id: revision, operation: 'APPEND', as_of: '2026-01-02', events: [], target_event_ids: [] }, true))
      .rejects.toMatchObject({ code: 'F3_OUTCOME_UNKNOWN', outcome: { disposition: 'UNKNOWN' } });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
  it('resolves the selected revision before refusing a foreign portfolio-export operation header', async () => {
    const workspace = { schema_version: SCHEMA, portfolio_id: root, revision_id: revision, current_revision_id: revision, as_of: '2026-01-02',
      history: [{ revision_id: revision, parent_revision_id: null, created_at: '2026-01-02', operation: 'OPENING' }], accounts: [], listings: [],
      ledger: { version: 3, events: [], field_rules: {}, current_state: { convention_set: 'invented-wire-only', as_of: '2026-01-02', ledger_version: 3, accounts: [] } },
      policies: { state: 'NOT_STATED', items: [], targets: [] }, benchmark: { state: 'NOT_STATED', pin: { schema: 'finweb.benchmark_selection_pin/1', portfolio_id: root, version: 0, state: 'NONE' },
        catalog_id: 'invented-empty', entries: [], selection_available: false }, guarded: readMeta() };
    const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(url.endsWith('/auth/session') ? json(session())
      : url.includes('/workspace?') ? json(workspace) : new Response('{}', { headers: { 'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="finweb-wire.json"',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'X-Finweb-Portfolio-Id': root, 'X-Finweb-Revision-Id': revision, 'X-Finweb-Operation-Id': other } })));
    vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); await api.session();
    await expect(api.exportPortfolio(root, revision, 'transactions', 'JSON')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/v1/auth/session', `/api/v1/portfolios/${root}/workspace?revision_id=${revision}`,
      `/api/v1/portfolios/${root}/exports/transactions?revision_id=${revision}&format=json`]);
  });
  it('resolves the selected CSV report before refusing a foreign report-export operation header', async () => {
    const reportId = '66666666-6666-4666-8666-666666666666';
    const report = { schema: 'finweb.csv_import/1', report_id: reportId, portfolio_id: root, operation_id: op, expected_revision_id: revision,
      proposal_digest: 'a'.repeat(64), persisted: true, status: 'REPORT_ONLY', file: { filename: 'fictional.csv', sha256: 'b'.repeat(64), byte_count: 1, bom: false },
      proposal: { operation_id: op, expected_revision_id: revision, filename: 'fictional.csv', synthetic_acknowledged: true }, parser: {}, rows: [],
      counts: { total: 0, economic: 0, ready: 0, quarantined: 0, excluded: 0, already_imported: 0, imported: 0 }, batch_errors: [], revision_id: null, created_at: '2026-01-02' };
    const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(url.endsWith('/auth/session') ? json(session())
      : url.endsWith(`/imports/${reportId}`) ? json({ schema_version: SCHEMA, portfolio_id: root, report, guarded: readMeta() })
        : new Response('{}', { headers: { 'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="finweb-wire.json"',
          'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'X-Finweb-Portfolio-Id': root, 'X-Finweb-Report-Id': reportId, 'X-Finweb-Operation-Id': other } })));
    vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); await api.session();
    await expect(api.exportCsvReport(root, reportId, 'JSON')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/v1/auth/session', `/api/v1/portfolios/${root}/imports/${reportId}`,
      `/api/v1/portfolios/${root}/imports/${reportId}/export?format=json`]);
  });
});
