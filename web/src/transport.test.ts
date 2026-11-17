import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, GuestApi, readSnapshot, SCHEMA, type CreatePortfolio } from './transport';
import { exactWitnesses, metricSubject, metricUnit, subjectLabel } from './presentation';
import i18n from './i18n';

// Transport-only adversarial records: not a financial expectation or engine fixture.
function snapshot(value: unknown = '123456789.123456', state = 'AVAILABLE') {
  return {
    schema_version: SCHEMA, portfolio_id: 'p1', name: 'transport test', mode: 'LOCAL_SYNTHETIC_GUEST',
    synthetic: true, persisted: false, reporting_currency: 'USD', as_of: '2026-01-02', limitations: [],
    inputs: { positions: [], cash: '1' }, provenance: { synthetic: true },
    valuation: { manifest_id: 'manifest', result_digest: 'result', metrics: [
      { metric_id: 'portfolio_value', state, value, reason: null, exact: state === 'INSUFFICIENT_DATA' ? null : '1/3', subject: [], details: [] },
    ] },
    diversification: { manifest_id: 'dmanifest', result_digest: 'dresult', metrics: [] },
    insights: { manifest_id: 'imanifest', result_digest: 'iresult', packets: [], diagnostics: [] },
  };
}
const input: CreatePortfolio = { name: 'Guest', reporting_currency: 'USD', positions: [], cash: '1', synthetic_acknowledged: true };
const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
afterEach(() => { vi.unstubAllGlobals(); });

describe('exact financial transport boundary', () => {
  it('preserves a financial decimal string byte-for-byte', () => {
    expect(readSnapshot(snapshot()).valuation.metrics[0].value).toBe('123456789.123456');
  });
  it('refuses a JSON numeric financial value instead of rounding it', () => {
    expect(() => readSnapshot(snapshot(123456789.123456))).toThrow(ApiError);
  });
  it('refuses a leaked number on an insufficient metric', () => {
    expect(() => readSnapshot(snapshot('0', 'INSUFFICIENT_DATA'))).toThrow(ApiError);
    expect(readSnapshot(snapshot(null, 'INSUFFICIENT_DATA')).valuation.metrics[0].value).toBeNull();
    for (const leaked of [{ exact: '1/2' }, { exact_square: '1/1' }, { sign: 0 }, { radical_terms: [['1/2', '3/4']] }]) {
      const value = snapshot(null, 'INSUFFICIENT_DATA');
      const invalid = { ...value, valuation: { ...value.valuation, metrics: [{ ...value.valuation.metrics[0], ...leaked }] } };
      expect(() => readSnapshot(invalid)).toThrow(ApiError);
    }
    const valid = snapshot(null, 'INSUFFICIENT_DATA');
    expect(readSnapshot({ ...valid, valuation: { ...valid.valuation, metrics: [
      { ...valid.valuation.metrics[0], exact_square: null, sign: null, radical_terms: [] },
    ] } }).valuation.metrics[0].state).toBe('INSUFFICIENT_DATA');
  });
  it('refuses unlabelled or persisted/non-synthetic output', () => {
    expect(() => readSnapshot({ ...snapshot(), synthetic: false })).toThrow(ApiError);
    expect(() => readSnapshot({ ...snapshot(), persisted: true })).toThrow(ApiError);
  });
  it('refuses AVAILABLE paired with a reason that requires a non-available state', () => {
    for (const reason of ['SOURCE_CONFLICT', 'MISSING_PRICE_HISTORY']) {
      const value = snapshot();
      value.valuation.metrics[0].reason = reason as never;
      expect(() => readSnapshot(value)).toThrow(ApiError);
    }
  });
});

describe('guest capability lifetime', () => {
  it('discards an expired token and obtains a new session on the next explicit retry', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ schema_version: SCHEMA, session_token: 'expired-capability' }))
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'GUEST_SESSION_REQUIRED', detail: 'Expired' } }, 401))
      .mockResolvedValueOnce(jsonResponse({ schema_version: SCHEMA, session_token: 'new-capability' }))
      .mockResolvedValueOnce(jsonResponse(snapshot(), 201));
    vi.stubGlobal('fetch', fetchMock);
    const api = new GuestApi();
    await expect(api.create(input)).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(2); // No hidden automatic mutation retry.
    await api.create(input);
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/guest-sessions');
    expect(fetchMock.mock.calls[3][1].headers['X-Finweb-Session']).toBe('new-capability');
    expect(fetchMock.mock.calls.every(([url]) => !String(url).includes('capability'))).toBe(true);
  });
  it('explicit New guest reset prevents reuse of the previous session capability', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ schema_version: SCHEMA, session_token: 'first' }))
      .mockResolvedValueOnce(jsonResponse(snapshot(), 201))
      .mockResolvedValueOnce(jsonResponse({ schema_version: SCHEMA, session_token: 'second' }))
      .mockResolvedValueOnce(jsonResponse(snapshot(), 201));
    vi.stubGlobal('fetch', fetchMock);
    const api = new GuestApi();
    await api.create(input); api.reset(); await api.create(input);
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/guest-sessions');
    expect(fetchMock.mock.calls[3][1].headers['X-Finweb-Session']).toBe('second');
  });
  it('never reports REPRODUCED when the actual digest differs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      schema_version: SCHEMA, portfolio_id: 'p1', insight_id: 'i1', status: 'REPRODUCED', detail: '',
      expected_result_digest: 'expected', actual_result_digest: 'different', synthetic: true,
    })));
    await expect(new GuestApi().reproduce('p1', 'i1', 'expected')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it('discards a guest response after resetting the workspace even when fetch ignores abort', async () => {
    let finish!: (value: Response) => void;
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise<Response>((resolve) => { finish = resolve; })));
    const api = new GuestApi(); const pending = api.snapshot('p1'); api.reset(); finish(jsonResponse(snapshot()));
    await expect(pending).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' });
  });
});

describe('claim subject survives simplified presentation', () => {
  it('keeps CASH and EQUITY distinct and translated without changing canonical identity', async () => {
    const metric = readSnapshot(snapshot()).valuation.metrics[0];
    await i18n.changeLanguage('zh-CN');
    const cash = { ...metric, subject: ['CASH'] };
    const equity = { ...metric, subject: ['EQUITY'] };
    expect(subjectLabel(i18n.t.bind(i18n), cash)).toBe('现金');
    expect(subjectLabel(i18n.t.bind(i18n), equity)).toBe('权益');
    expect(metricSubject(cash)).toBe('CASH');
    expect(subjectLabel(i18n.t.bind(i18n), { ...metric, subject: ['UNKNOWN'] })).toBe('分类未知');
    await i18n.changeLanguage('en');
  });
});

describe('issued representations and semantic units', () => {
  it('keeps an AVAILABLE zero volatility square/sign witness without inventing insufficient data', () => {
    const metric = { ...readSnapshot(snapshot('0')).valuation.metrics[0], metric_id: 'modeled_volatility', exact: null, exact_square: '0/1', sign: 0, radical_terms: [] };
    expect(metric.state).toBe('AVAILABLE');
    expect(exactWitnesses(metric)).toEqual([{ label: 'exactSquare', value: '0/1' }, { label: 'witnessSign', value: '0' }]);
  });
  it('retains signed radical witnesses and distinguishes their units from bounded capital shares', async () => {
    const metric = { ...readSnapshot(snapshot()).valuation.metrics[0], exact: null, radical_terms: [['-1/2', '3/4']] };
    expect(exactWitnesses(metric)).toEqual([{ label: 'radicalWitness', value: '[["-1/2","3/4"]]' }]);
    for (const language of ['en', 'zh-CN']) {
      await i18n.changeLanguage(language);
      const t = i18n.t.bind(i18n);
      expect(metricUnit(t, 'largest_security_weight')).toContain('0–1');
      expect(metricUnit(t, 'risk_contribution_share')).not.toContain('0–1');
      expect(metricUnit(t, 'modeled_volatility')).not.toContain('0–1');
      expect(metricUnit(t, 'hhi_concentration')).not.toBe(metricUnit(t, 'effective_positions'));
      expect(metricUnit(t, 'risk_contribution_component')).not.toBe(metricUnit(t, 'risk_contribution_share'));
    }
    await i18n.changeLanguage('en');
  });
});
