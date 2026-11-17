import { afterEach, describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AccountApi } from './account';
import { ApiError, readSavedSnapshot, readSnapshot } from './transport';
import { REAL_SOURCE_BLOCKERS, REAL_SOURCE_SCHEMA, readRealSourceReadiness, RealReadinessLoad, type RealReadinessState } from './real-source';
import RealSourceReadiness, { RealSourceReadinessContent } from './RealSourceReadiness';
import i18n from './i18n';

const context = (letter = 'a') => ({ context_id: letter.repeat(64), configuration_digest: 'b'.repeat(64), declared_release_id: 'c'.repeat(64), declared_source_ids: ['registered.source'], status: 'CONFIGURED_NOT_VERIFIED', readiness_stage: 'METADATA_ONLY', metadata_integrity: 'EXPECTED_METADATA_BYTES_MATCHED', payload_integrity: 'NOT_VERIFIED', financially_qualified: false });
function blocked() {
  return { schema_version: REAL_SOURCE_SCHEMA, milestone: 'E1_GATE_ONLY', mode: 'LOCAL_REAL_SOURCE_TEST_ACCOUNT', state: 'BLOCKED', readiness_stage: 'METADATA_ONLY',
    provenance: { ledger_origin: 'PROJECT_CONSTRUCTED_NONPERSONAL_UAT_REQUESTED', market_origin: 'REAL_SOURCE_REQUESTED_NOT_QUALIFIED', personal_holdings: false },
    capabilities: { source_metadata: true, payload_verification: false, source_qualification: false, create: false, saved: false, workspace: false, analytics: false, imports: false, exports: false, evidence: false },
    approved_context_count: 0, contexts: [] as ReturnType<typeof context>[], blockers: [...REAL_SOURCE_BLOCKERS], limits: { http_bytes: 32768, output_bytes: 65536 }, scope: { markets: ['US'], reporting_currencies: ['USD'] }, support: { data_action: 'EXISTING_REGISTERED_PROJECT_METADATA_ONLY', download_or_admission: false, real_uat_verified: false, hg4_approved: false } };
}
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const session = { schema_version: 'finweb.cp7/1', authenticated: true, user: { user_id: 'user', username: 'test_user' }, csrf_token: 'a'.repeat(64) };
afterEach(async () => { vi.unstubAllGlobals(); await i18n.changeLanguage('en'); });

describe('E1 metadata-only transport boundary', () => {
  it('keeps both empty and configured declarations blocked without rewriting inputs', () => {
    for (const contexts of [[], [context()]]) { const value = { ...blocked(), contexts }; const before = JSON.stringify(value); const parsed = readRealSourceReadiness(value);
      expect(parsed.approved_context_count).toBe(0); expect(parsed.capabilities.create).toBe(false); expect(parsed.state).toBe('BLOCKED'); expect(JSON.stringify(value)).toBe(before); }
  });
  it('rejects financial readiness and all contradictory capability/provenance/approval flags', () => {
    for (const change of [{ state: 'READY' }, { milestone: 'E2' }, { readiness_stage: 'QUALIFIED' }, { approved_context_count: 1 }, { mode: 'LOCAL_SYNTHETIC_ACCOUNT' }, { schema_version: 'finweb.cp7/1' }]) expect(() => readRealSourceReadiness({ ...blocked(), ...change })).toThrow(ApiError);
    for (const key of Object.keys(blocked().capabilities)) { const value = blocked(); (value.capabilities as Record<string, boolean>)[key] = key !== 'source_metadata'; expect(() => readRealSourceReadiness(value)).toThrow(ApiError); }
    for (const section of ['provenance', 'support'] as const) { const value = blocked(); const row = value[section] as Record<string, unknown>; for (const key of Object.keys(row)) { const altered = structuredClone(value); (altered[section] as Record<string, unknown>)[key] = true; expect(() => readRealSourceReadiness(altered)).toThrow(ApiError); } }
  });
  it('requires exact field sets at every envelope layer', () => {
    const baseline = { ...blocked(), contexts: [context()] };
    const rows = [baseline, baseline.provenance, baseline.capabilities, baseline.limits, baseline.scope, baseline.support, baseline.contexts[0]];
    for (let index = 0; index < rows.length; index += 1) {
      for (const key of Object.keys(rows[index])) { const value = structuredClone(baseline); const targets = [value, value.provenance, value.capabilities, value.limits, value.scope, value.support, value.contexts[0]]; delete (targets[index] as Record<string, unknown>)[key]; expect(() => readRealSourceReadiness(value)).toThrow(ApiError); }
      const value = structuredClone(baseline); const targets = [value, value.provenance, value.capabilities, value.limits, value.scope, value.support, value.contexts[0]]; (targets[index] as Record<string, unknown>).payload = 'never accept a payload'; expect(() => readRealSourceReadiness(value)).toThrow(ApiError);
    }
  });
  it('bounds and binds declared context identities, ordering and source strings', () => {
    for (const alteration of [{ context_id: 'A'.repeat(64) }, { configuration_digest: 'b'.repeat(63) }, { declared_release_id: 1 }, { financially_qualified: true }, { payload_integrity: 'VERIFIED' }, { status: 'READY' }, { declared_source_ids: [] }, { declared_source_ids: ['a', 'a'] }, { declared_source_ids: ['b', 'a'] }, { declared_source_ids: ['Bad/source'] }, { declared_source_ids: ['a'.repeat(65)] }, { declared_source_ids: ['a', 'b', 'c', 'd', 'e', 'f', 'g'] }]) expect(() => readRealSourceReadiness({ ...blocked(), contexts: [{ ...context(), ...alteration }] })).toThrow(ApiError);
    for (const contexts of [[context('b'), context('a')], [context(), context()], Array.from({ length: 17 }, () => context())]) expect(() => readRealSourceReadiness({ ...blocked(), contexts })).toThrow(ApiError);
    expect(readRealSourceReadiness({ ...blocked(), contexts: [context('a'), context('b')] }).contexts).toHaveLength(2);
  });
  it('rejects altered fixed blockers, resource/scope declarations and financial data injection', () => {
    for (const change of [{ blockers: [] }, { blockers: [...REAL_SOURCE_BLOCKERS, 'UNKNOWN'] }, { blockers: [...REAL_SOURCE_BLOCKERS].reverse() }, { limits: { http_bytes: 32768, output_bytes: 2_000_000 } }, { scope: { markets: ['US', 'HK'], reporting_currencies: ['USD'] } }, { positions: [] }, { synthetic: false }, { payload: 'x'.repeat(65537) }]) expect(() => readRealSourceReadiness({ ...blocked(), ...change })).toThrow(ApiError);
  });
  it('leaves the existing saved and guest financial readers strict', () => {
    expect(() => readSavedSnapshot(blocked())).toThrow(ApiError); expect(() => readSnapshot(blocked())).toThrow(ApiError);
  });
});

describe('authenticated GET and view lifetime', () => {
  it('uses only the explicit no-store same-origin readiness GET, without bootstrap or financial write', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(blocked())); vi.stubGlobal('fetch', fetchMock); const api = new AccountApi();
    expect(fetchMock).not.toHaveBeenCalled(); await api.realSourceReadiness(); expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0]; expect(url).toBe('/api/v1/real-source-contexts'); expect(options).toMatchObject({ method: 'GET', credentials: 'same-origin', cache: 'no-store' }); expect(options).not.toHaveProperty('body'); expect(options.headers).toEqual({});
  });
  it('discards a late decoded readiness response after the shared identity is cleared', async () => {
    let finish!: (value: unknown) => void; vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => new Promise((resolve) => { finish = resolve; }) }));
    const api = new AccountApi(); const pending = api.realSourceReadiness(); await Promise.resolve(); api.reset(); finish(blocked()); await expect(pending).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' });
  });
  it('clears expired authenticated capability and does not retry GET or mutate', async () => {
    for (const [status, code] of [[401, 'AUTHENTICATION_REQUIRED'], [403, 'CSRF_REJECTED']] as const) { const fetchMock = vi.fn().mockResolvedValueOnce(response(session)).mockResolvedValueOnce(response({ error: { code, detail: 'Refused' } }, status)); vi.stubGlobal('fetch', fetchMock); const api = new AccountApi(); const lost = vi.fn(); api.onSessionLost = lost; await api.session(); await expect(api.realSourceReadiness()).rejects.toMatchObject({ code, status }); expect(lost).toHaveBeenCalledTimes(1); expect(fetchMock).toHaveBeenCalledTimes(2); }
  });
  it('keeps network failure distinct from a valid blocked response and clears old data while retrying', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline'))); const states: RealReadinessState[] = []; const loader = new RealReadinessLoad();
    await loader.run(() => new AccountApi().realSourceReadiness(), (state) => states.push(state)); expect(states.map((state) => state.kind)).toEqual(['loading', 'error']); expect(states[1]).toMatchObject({ error: { code: 'NETWORK_ERROR' } });
    await loader.run(async () => readRealSourceReadiness(blocked()), (state) => states.push(state)); expect(states.map((state) => state.kind)).toEqual(['loading', 'error', 'loading', 'blocked']);
  });
  it('does not let an older response or error overwrite a later read or a departed view', async () => {
    const loader = new RealReadinessLoad(); const states: RealReadinessState[] = []; let finish!: (value: ReturnType<typeof readRealSourceReadiness>) => void;
    const old = loader.run(() => new Promise((resolve) => { finish = resolve; }), (state) => states.push(state)); await loader.run(async () => readRealSourceReadiness(blocked()), (state) => states.push(state)); finish(readRealSourceReadiness({ ...blocked(), contexts: [context()] })); await old;
    expect(states.map((state) => state.kind)).toEqual(['loading', 'loading', 'blocked']); expect(states[2]).toMatchObject({ value: { contexts: [] } });
    let fail!: (error: unknown) => void; const leaving = loader.run(() => new Promise((_, reject) => { fail = reject; }), (state) => states.push(state)); loader.invalidate(); fail(new ApiError('NETWORK_ERROR', 'late error')); await leaving; expect(states.map((state) => state.kind)).toEqual(['loading', 'loading', 'blocked', 'loading']);
  });
});

describe('readiness presentation without a financial workflow', () => {
  it('retains both origins, blocked reasons and disabled actions in both languages at every depth', async () => {
    const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock);
    for (const language of ['en', 'zh-CN']) { await i18n.changeLanguage(language); for (const depth of ['quick', 'simple', 'professional'] as const) { const value = readRealSourceReadiness({ ...blocked(), contexts: [context()] }); const before = JSON.stringify(value); const html = renderToStaticMarkup(createElement(RealSourceReadinessContent, { state: { kind: 'blocked', value }, depth, onRetry: () => {}, onReturn: () => {} }));
      expect(html.match(/disabled=""/g)).toHaveLength(3); expect(html.match(/aria-describedby="real-source-disabled-reason"/g)).toHaveLength(3); expect(html).toContain('real-source-origins'); expect(html).toContain(value.contexts[0].context_id);
      for (const code of REAL_SOURCE_BLOCKERS) expect(html).toContain(code); expect(html).not.toContain('<input'); expect(html).not.toContain('<form'); expect(html).not.toContain('metric-value'); expect(JSON.stringify(value)).toBe(before);
      if (depth === 'professional') expect(html).toContain('<details>'); else expect(html).not.toContain('<pre');
    } } expect(fetchMock).not.toHaveBeenCalled();
  });
  it('does not label a failed GET as an empty configured-source result', () => {
    const html = renderToStaticMarkup(createElement(RealSourceReadinessContent, { state: { kind: 'error', error: new ApiError('NETWORK_ERROR', 'offline') }, depth: 'quick', onRetry: () => {}, onReturn: () => {} })); expect(html).toContain('role="alert"'); expect(html).not.toContain(i18n.t('realSourceNoContexts')); expect(html.match(/disabled=""/g)).toHaveLength(3);
  });
  it('offers no active readiness controls to a guest', () => {
    const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); const html = renderToStaticMarkup(createElement(RealSourceReadiness, { api: new AccountApi(), authenticated: false, depth: 'quick', onReturn: () => {} })); expect(html).toContain(i18n.t('realSourceGuest')); expect(html).not.toContain('<button'); expect(fetchMock).not.toHaveBeenCalled();
  });
});
