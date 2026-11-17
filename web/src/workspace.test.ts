import { afterEach, describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AccountApi } from './account';
import { eventDraft, eventInput } from './LedgerPanel';
import PreferencesPanel from './PreferencesPanel';
import i18n from './i18n';
import { ApiError, packetPolicy, readSavedSnapshot, SCHEMA, type Packet } from './transport';
import { observationClaim } from './presentation';
import { readWorkspace, readWorkspaceResult, validExactLimit, WorkspaceReadEpoch, type LedgerCommand, type LedgerRow } from './workspace';

// Scope/transport probes only: none of these values are financial engine expectations.
function workspace() {
  return { schema_version: SCHEMA, portfolio_id: 'portfolio', revision_id: 'revision', current_revision_id: 'revision', as_of: '2026-01-02',
    history: [{ revision_id: 'revision', parent_revision_id: null, created_at: '2026-10-19', operation: 'OPENING' }],
    accounts: [{ account_id: 'account', name: 'Synthetic account' }], listings: [{ listing_id: 'listing', symbol: 'SYN-A', currency: 'USD' }],
    ledger: { version: 12, events: [], field_rules: { DEPOSIT: { amount: 'REQUIRED', quantity: 'FORBIDDEN' } },
      current_state: { convention_set: 'ledger-replay/test', as_of: '2026-01-02', ledger_version: 12, accounts: [
        { account_id: 'account', status: 'RECONSTRUCTED', snapshot_date: '2026-01-02', positions: [], cash: [{ currency: 'USD', amount: '123456789.123456789012345678901234' }], unrepresentable_cash: [] },
      ] } },
    policies: { state: 'NOT_STATED', items: [] as unknown[], targets: [{ source_kind: 'CP5', scope_kind: 'PORTFOLIO', account_id: null, metric_id: 'largest_security_weight', subject: [], semantic_key: 'semantic', unit: null }] },
    benchmark: { state: 'NOT_STATED', pin: { schema: 'finweb.benchmark_selection_pin/1', portfolio_id: 'portfolio', version: 0, state: 'NONE' }, catalog_id: 'catalog', entries: [] as unknown[], selection_available: false },
  };
}
function snapshot() {
  return { schema_version: SCHEMA, portfolio_id: 'portfolio', name: 'Transport-only sandbox', mode: 'LOCAL_SYNTHETIC_ACCOUNT', synthetic: true, persisted: true, reporting_currency: 'USD', as_of: '2026-01-02', limitations: ['SAVED_SYNTHETIC_SANDBOX: test'],
    inputs: { positions: [], cash: '1' }, provenance: {}, valuation: { manifest_id: 'v', result_digest: 'v1', metrics: [] }, diversification: { manifest_id: 'd', result_digest: 'd1', metrics: [] }, insights: { manifest_id: 'i', result_digest: 'i1', packets: [], diagnostics: [] } };
}
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const session = { schema_version: SCHEMA, authenticated: true, user: { user_id: 'user', username: 'test_user' }, csrf_token: 'a'.repeat(64) };
const command: LedgerCommand = { operation_id: 'same-operation', expected_revision_id: 'revision', operation: 'APPEND', as_of: '2026-01-02', events: [{ account_id: 'account', event_type: 'DEPOSIT', event_date: '2026-01-02', currency: 'USD', amount: '1' }], target_event_ids: [] };
afterEach(() => { vi.unstubAllGlobals(); });

describe('private workspace semantic bindings', () => {
  it('preserves exact native cash strings and accepts an unknown optional unit without inventing one', () => {
    const value = readWorkspace(workspace(), 'portfolio');
    expect(value.ledger.current_state.accounts[0].cash[0].amount).toBe('123456789.123456789012345678901234');
    expect(value.policies.targets[0].unit).toBeNull();
  });
  it('refuses foreign portfolio/revision responses and a revision missing from history', () => {
    expect(() => readWorkspace(workspace(), 'foreign')).toThrow(ApiError);
    expect(() => readWorkspace(workspace(), 'portfolio', 'another-revision')).toThrow(ApiError);
    expect(() => readWorkspace({ ...workspace(), history: [] }, 'portfolio')).toThrow(ApiError);
  });
  it('refuses a foreign benchmark pin even when its outer portfolio matches', () => {
    const value = workspace(); value.benchmark.pin.portfolio_id = 'foreign';
    expect(() => readWorkspace(value, 'portfolio')).toThrow(ApiError);
  });
  it('keeps never stated, explicitly none and selected benchmark states distinct', () => {
    const value = workspace(); value.benchmark.state = 'NONE';
    expect(() => readWorkspace(value, 'portfolio')).toThrow(ApiError);
    value.benchmark.pin.state = 'CLEARED'; expect(readWorkspace(value, 'portfolio').benchmark.state).toBe('NONE');
    value.benchmark.state = 'SELECTED'; value.benchmark.pin.state = 'IN_FORCE';
    expect(() => readWorkspace(value, 'portfolio')).toThrow(ApiError);
  });
  it('refuses no-limit states containing policies and account policies bound to an unrelated account', () => {
    const value = workspace(); value.policies.items = [{ policy_id: 'policy', version: 'v', evidence: 'User statement', portfolio_id: 'portfolio', scope_kind: 'ACCOUNT', account_id: 'foreign-account', source_kind: 'CP5', metric_id: 'largest_security_weight', semantic_key: 'semantic', direction: 'MAXIMUM', limit: '1/2', effective_from: '2026-01-02', subject: [], origin: 'USER_CONFIRMED' }];
    expect(() => readWorkspace(value, 'portfolio')).toThrow(ApiError);
    value.policies.state = 'ACTIVE'; expect(() => readWorkspace(value, 'portfolio')).toThrow(ApiError);
    (value.policies.items[0] as { account_id: string }).account_id = 'account';
    expect(readWorkspace(value, 'portfolio').policies.items).toHaveLength(1);
  });
  it('refuses a native reconstruction bound to another as-of date or ledger pin', () => {
    const value = workspace(); value.ledger.current_state.as_of = '2026-01-03';
    expect(() => readWorkspace(value, 'portfolio')).toThrow(ApiError);
    value.ledger.current_state.as_of = value.as_of; value.ledger.current_state.ledger_version = 11;
    expect(() => readWorkspace(value, 'portfolio')).toThrow(ApiError);
  });
  it('refuses numeric native money and an insufficient quantity leaking a value', () => {
    const value = workspace(); (value.ledger.current_state.accounts[0].cash[0] as unknown as { amount: number }).amount = 1;
    expect(() => readWorkspace(value, 'portfolio')).toThrow(ApiError);
    const malformed = workspace(); (malformed.ledger.current_state.accounts[0].positions as unknown[]) = [{ listing_id: 'listing', quantity: { value: '0', state: 'INSUFFICIENT_DATA', reason: 'MISSING_COST_BASIS', detail: [] }, cost_basis: [] }];
    expect(() => readWorkspace(malformed, 'portfolio')).toThrow(ApiError);
  });
  it('accepts an explicitly requested historical result while preserving the actual latest-head identity', () => {
    const value = workspace(); value.current_revision_id = 'newer'; value.history.push({ revision_id: 'newer', parent_revision_id: 'revision' as never, created_at: '2026-10-19', operation: 'APPEND' });
    expect(readWorkspace(value, 'portfolio', 'revision').current_revision_id).toBe('newer');
  });
});

describe('preview and immutable command transport', () => {
  it('allows a labelled rollback-only account preview only through the preview reader', () => {
    const proposal = { ...snapshot(), persisted: false, limitations: ['PREVIEW_NOT_SAVED: rollback-only proposal'] };
    expect(() => readSavedSnapshot(proposal)).toThrow(ApiError);
    expect(() => readWorkspaceResult({ preview: true, workspace: workspace(), snapshot: proposal }, 'portfolio')).toThrow(ApiError);
    expect(readWorkspaceResult({ preview: true, workspace: workspace(), snapshot: proposal }, 'portfolio', true).snapshot.persisted).toBe(false);
    expect(() => readWorkspaceResult({ preview: true, workspace: workspace(), snapshot: snapshot() }, 'portfolio', true)).toThrow(ApiError);
    expect(() => readWorkspaceResult({ preview: true, workspace: workspace(), snapshot: { ...proposal, limitations: [] } }, 'portfolio', true)).toThrow(ApiError);
  });
  it('refuses a confirmed response whose snapshot belongs to another portfolio', () => {
    expect(() => readWorkspaceResult({ workspace: workspace(), snapshot: { ...snapshot(), portfolio_id: 'foreign' } }, 'portfolio')).toThrow(ApiError);
  });
  it('uses the same explicit command in preview and manual retry; a stale refusal causes no automatic repeat', async () => {
    const preview = { preview: true, workspace: workspace(), snapshot: { ...snapshot(), persisted: false, limitations: ['PREVIEW_NOT_SAVED: test'] } };
    const fetchMock = vi.fn().mockResolvedValueOnce(reply(session)).mockResolvedValueOnce(reply(preview))
      .mockResolvedValueOnce(reply({ error: { code: 'STALE_REVISION', detail: 'Reload' } }, 409)); vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi(); await api.ledgerCommand('portfolio', command, true);
    await expect(api.ledgerCommand('portfolio', command)).rejects.toMatchObject({ code: 'STALE_REVISION' });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/portfolios/portfolio/ledger-commands/preview');
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/portfolios/portfolio/ledger-commands');
    expect(fetchMock.mock.calls[1][1].body).toBe(fetchMock.mock.calls[2][1].body);
    expect(fetchMock.mock.calls[2][1].credentials).toBe('same-origin');
    expect(fetchMock.mock.calls[2][1].headers['X-Finweb-CSRF']).toBe('a'.repeat(64));
  });
  it('pins workspace and saved snapshot requests to the selected historical revision', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(reply(workspace())).mockResolvedValueOnce(reply(snapshot())); vi.stubGlobal('fetch', fetchMock);
    const api = new AccountApi(); await api.workspace('portfolio', 'revision'); await api.snapshot('portfolio', 'revision');
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/v1/portfolios/portfolio/workspace?revision_id=revision', '/api/v1/portfolios/portfolio?revision_id=revision']);
  });
  it('discards a pending private workspace response after session identity changes', async () => {
    let finish!: (response: Response) => void; vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise((resolve) => { finish = resolve; })));
    const api = new AccountApi(); const pending = api.workspace('portfolio'); api.reset(); finish(reply(workspace()));
    await expect(pending).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' });
  });
  it('does not let a delayed same-account refresh replace a newer confirmed revision', async () => {
    let finish!: (revision: string) => void; const reads = new WorkspaceReadEpoch(); let displayed = 'initial';
    const oldRead = reads.begin(); const refresh = new Promise<string>((resolve) => { finish = resolve; })
      .then((revision) => { if (reads.isCurrent(oldRead)) displayed = revision; });
    reads.invalidate(); displayed = 'new-confirmed'; finish('old-refresh'); await refresh;
    expect(displayed).toBe('new-confirmed');
  });
});

describe('explicit source entry boundaries', () => {
  it('preserves exact string event facts while dropping server-owned audit fields from a correction draft', () => {
    const row = { event_id: 'old', account_id: 'account', event_type: 'CURRENCY_CONVERSION', event_date: '2026-01-03', currency: 'USD', amount: '10.123456789012345678901234', bought_amount: { amount: '70', currency: 'CNY' }, source_reference: 'original', corrects_event_id: null } as LedgerRow;
    const input = eventInput(eventDraft(row), { amount: 'REQUIRED', bought_amount: 'REQUIRED' });
    expect(input.amount).toBe(row.amount); expect(input.bought_amount).toEqual(row.bought_amount);
    expect(input).not.toHaveProperty('event_id'); expect(input).not.toHaveProperty('source_reference'); expect(input).not.toHaveProperty('corrects_event_id');
  });
  it('preserves signed exact limits without parsing or choosing a personal threshold', () => {
    for (const value of ['0', '1/2', '-1/2', '-0.25', '0.123456789012345678901234']) expect(validExactLimit(value)).toBe(true);
    for (const value of ['', '50%', '1/0', '1e-2', 'NaN', ' 0.5']) expect(validExactLimit(value)).toBe(false);
  });
  it('renders no prefilled personal-limit rows and an unavailable catalog choice in both languages', async () => {
    for (const language of ['en', 'zh-CN']) {
      await i18n.changeLanguage(language);
      const html = renderToStaticMarkup(createElement(PreferencesPanel, { workspace: readWorkspace(workspace(), 'portfolio'), api: new AccountApi(), onUpdate: () => undefined }));
      expect(html).not.toContain('id="policy-0-limit"'); expect(html).toContain('<option value="SELECT" disabled="">');
      expect(html).toContain(i18n.t('policyBlankDisclosure')); expect(html).toContain(i18n.t('benchmarkCatalogEmpty'));
    }
    await i18n.changeLanguage('en');
  });
  it('keeps a user-limit judgment preference-dependent and translates the issued exact limit without comparing it', async () => {
    const policy = { policy_id: 'policy', version: 'version', evidence: 'Explicit user source', portfolio_id: 'portfolio', scope_kind: 'PORTFOLIO', account_id: null,
      source_kind: 'CP5', metric_id: 'largest_security_weight', semantic_key: 'semantic', subject: [], direction: 'MAXIMUM', limit: '1/3', effective_from: '2026-01-02', effective_until: null, origin: 'USER_CONFIRMED' };
    const packet = { insight_id: 'insight', insight_type: 'user_limit', judgment_class: 'PREFERENCE_DEPENDENT', portfolio_id: 'portfolio', severity: 'ATTENTION', synthetic: true,
      confidence_availability_state: 'AVAILABLE', limitations: [],
      comparison_basis: { kind: 'USER_POLICY', policy_id: 'policy', version: 'version', policy_digest: 'digest' },
      thresholds_limits: { policy, policy_digest: 'digest', decision_basis: 'EXACT_UPSTREAM_WITNESS', equality_is_breach: false },
      metrics_used: [{ reference: { metric_id: 'largest_security_weight', subject: [] }, metric: { metric_id: 'largest_security_weight', value: '0.333333', state: 'AVAILABLE', reason: null, subject: [], details: [] } }],
      claim: { text: 'Original issued claim', caveats: [], parameters: {} } } as unknown as Packet;
    expect(packetPolicy(packet)?.limit).toBe('1/3'); expect(packetPolicy({ ...packet, judgment_class: 'FACT' })).toBeNull();
    expect(packetPolicy({ ...packet, thresholds_limits: { ...packet.thresholds_limits as object, policy: { ...policy, limit: 1 / 3 } } })).toBeNull();
    const body = snapshot();
    expect(readSavedSnapshot({ ...body, insights: { ...body.insights, packets: [packet] } }).insights.packets).toHaveLength(1);
    const foreign = { ...packet, portfolio_id: 'foreign', thresholds_limits: { ...packet.thresholds_limits as object, policy: { ...policy, portfolio_id: 'foreign' } } };
    expect(() => readSavedSnapshot({ ...body, insights: { ...body.insights, packets: [foreign] } })).toThrow(ApiError);
    await i18n.changeLanguage('zh-CN'); const claim = observationClaim(i18n.t.bind(i18n), packet, '2026-01-02');
    expect(claim).toContain('超过了你声明的上限（1/3）'); expect(claim).toContain('0.333333'); expect(claim).not.toContain('Original issued claim');
    await i18n.changeLanguage('en'); expect(observationClaim(i18n.t.bind(i18n), packet, '2026-01-02')).toContain('your stated maximum (1/3)');
  });
});
