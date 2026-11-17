import { afterEach, describe, expect, it, vi } from 'vitest';
import { AccountApi, readSession, validAccountInput } from './account';
import { ApiError, readSavedSnapshot, readSnapshot, SCHEMA, type CreatePortfolio } from './transport';

// Adversarial transport records only; these are not financial expected outputs.
const session = (authenticated = true) => ({ schema_version: SCHEMA, authenticated,
  user: authenticated ? { user_id: 'test-user-id', username: 'test_user' } : null, csrf_token: 'a'.repeat(64) });
const snapshot = () => ({
  schema_version: SCHEMA, portfolio_id: 'test-portfolio', name: 'Test sandbox', mode: 'LOCAL_SYNTHETIC_ACCOUNT',
  synthetic: true, persisted: true, reporting_currency: 'USD', as_of: '2026-01-02', limitations: [],
  inputs: { positions: [], cash: '1' }, provenance: { synthetic: true },
  valuation: { manifest_id: 'm1', result_digest: 'r1', metrics: [] },
  diversification: { manifest_id: 'm2', result_digest: 'r2', metrics: [] },
  insights: { manifest_id: 'm3', result_digest: 'r3', packets: [], diagnostics: [] },
});
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const input: CreatePortfolio = { name: 'Test sandbox', reporting_currency: 'USD', positions: [], cash: '1', synthetic_acknowledged: true };
afterEach(() => { vi.unstubAllGlobals(); });

describe('saved synthetic scope', () => {
  it('counts Unicode password characters for the minimum and UTF-8 bytes for the maximum', () => {
    expect(validAccountInput('test_user', '合成测试密码')).toBe(false);
    expect(validAccountInput('test_user', '合'.repeat(15))).toBe(true);
    expect(validAccountInput('test_user', '🧪'.repeat(14))).toBe(false);
    expect(validAccountInput('test_user', '🧪'.repeat(32))).toBe(true);
    expect(validAccountInput('test_user', '🧪'.repeat(33))).toBe(false);
  });
  it('accepts only paired account/synthetic/persisted identity and keeps the guest validator strict', () => {
    expect(readSavedSnapshot(snapshot()).persisted).toBe(true);
    expect(() => readSnapshot(snapshot())).toThrow(ApiError);
    for (const change of [{ mode: 'LOCAL_SYNTHETIC_GUEST' }, { mode: 'REAL_USER_PORTFOLIO' }, { synthetic: false }, { persisted: false }]) {
      expect(() => readSavedSnapshot({ ...snapshot(), ...change })).toThrow(ApiError);
    }
  });
  it('refuses authenticated sessions without an identified user or a CSRF token', () => {
    for (const change of [{ user: null }, { user: { username: 'test' } }, { csrf_token: '' }, { csrf_token: null }]) {
      expect(() => readSession({ ...session(), ...change })).toThrow(ApiError);
    }
    expect(readSession(session(false)).user).toBeNull();
  });
  it('refuses an unlabelled saved collection rather than displaying it as a synthetic sandbox', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ schema_version: SCHEMA, portfolios: [
      { ...snapshot(), mode: 'REAL_USER_PORTFOLIO', created_at: '2026-10-19' },
    ] })));
    await expect(new AccountApi().portfolios()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it('refuses a saved snapshot returned for a different requested portfolio identity', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(snapshot())));
    await expect(new AccountApi().snapshot('different-requested-portfolio')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
});

describe('cookie and CSRF account transport', () => {
  it('bootstraps a CSRF token, sends cookie credentials only same-origin, and explicitly labels saved sandbox creation', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(session(false)))
      .mockResolvedValueOnce(response(session(), 201)).mockResolvedValueOnce(response(snapshot(), 201));
    vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi();
    await api.authenticate('register', 'test_user', 'test-only-password-never-real'); await api.create(input);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/v1/auth/session', '/api/v1/auth/register', '/api/v1/portfolios']);
    const auth = fetchMock.mock.calls[1][1];
    expect(auth.credentials).toBe('same-origin'); expect(auth.cache).toBe('no-store');
    expect(auth.headers['X-Finweb-CSRF']).toBe('a'.repeat(64));
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ ...input, mode: 'LOCAL_SYNTHETIC_ACCOUNT' });
    expect(fetchMock.mock.calls.every(([url, options]) => !url.includes('password') && !url.includes('csrf') && !options.headers['X-Finweb-Session'])).toBe(true);
  });
  it('clears account capability and notifies the view on 401 without retrying a mutation', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(session()))
      .mockResolvedValueOnce(response({ error: { code: 'AUTHENTICATION_REQUIRED', detail: 'Expired' } }, 401))
      .mockResolvedValueOnce(response(session(false))).mockResolvedValueOnce(response(session()));
    vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi(); const lost = vi.fn(); api.onSessionLost = lost;
    await api.session();
    await expect(api.create(input)).rejects.toMatchObject({ code: 'AUTHENTICATION_REQUIRED', status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(2); expect(lost).toHaveBeenCalledTimes(1);
    await api.authenticate('login', 'test_user', 'test-only-password-never-real');
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/auth/session');
  });
  it('invalidates a failed CSRF token and never silently repeats the command', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(session()))
      .mockResolvedValueOnce(response({ error: { code: 'CSRF_REJECTED', detail: 'Refused' } }, 403));
    vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi(); const lost = vi.fn(); api.onSessionLost = lost; await api.session();
    await expect(api.logout()).rejects.toMatchObject({ code: 'CSRF_REJECTED' });
    expect(fetchMock).toHaveBeenCalledTimes(2); expect(lost).toHaveBeenCalledTimes(1);
  });
  it('discards an old private response after an identity transition even if the network ignores abort', async () => {
    let finish!: (value: Response) => void;
    const fetchMock = vi.fn().mockImplementation(() => new Promise<Response>((resolve) => { finish = resolve; }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi(); const pending = api.snapshot('test-portfolio');
    api.cancelPending(); finish(response(snapshot()));
    await expect(pending).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' });
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true);
  });
  it('checks the revision again after asynchronously reading a private JSON response', async () => {
    let finish!: (value: unknown) => void;
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200,
      json: () => new Promise((resolve) => { finish = resolve; }) }));
    const api = new AccountApi(); const pending = api.snapshot('test-portfolio');
    await Promise.resolve(); api.reset(); finish(snapshot());
    await expect(pending).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' });
  });
  it('never starts an account mutation if identity changes between bootstrap and the command', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(session(false))); vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi(); const bootstrap = api.session.bind(api);
    vi.spyOn(api, 'session').mockImplementation(async () => { const value = await bootstrap(); api.cancelPending(); return value; });
    await expect(api.authenticate('login', 'test_user', 'test-only-password-never-real')).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' });
    expect(fetchMock).toHaveBeenCalledTimes(1); expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/auth/session');
  });
  it('does not claim successful login/logout when the server returns the opposite authentication state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(session(false)))
      .mockResolvedValueOnce(response(session(false))).mockResolvedValueOnce(response(session())));
    const api = new AccountApi();
    await expect(api.authenticate('login', 'test_user', 'test-only-password-never-real')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    await expect(api.logout()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it('refuses successful reproduction with a foreign portfolio ID or mismatched digest', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(session()))
      .mockResolvedValueOnce(response({ schema_version: SCHEMA, portfolio_id: 'other-portfolio', insight_id: 'i1',
        status: 'REPRODUCED', detail: '', synthetic: true, expected_result_digest: 'expected', actual_result_digest: 'expected' }))
      .mockResolvedValueOnce(response({ schema_version: SCHEMA, portfolio_id: 'test-portfolio', insight_id: 'i1',
        status: 'REPRODUCED', detail: '', synthetic: true, expected_result_digest: 'expected', actual_result_digest: 'different' }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi(); await api.session();
    await expect(api.reproduce('test-portfolio', 'i1', 'expected')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    await expect(api.reproduce('test-portfolio', 'i1', 'expected')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
});
