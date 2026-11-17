import { afterEach, describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AccountApi } from './account';
import { ANALYTICS_SCHEMA, analyticalProof, readAnalyticsEvaluation, readAnalyticsEvidence, readAnalyticsReproduction, type AnalyticsEvaluation, type AnalyticsMetric, type AnalyticsQuestion } from './analytics';
import AnalyticalMetric, { gainDirection, PartialValuationContext } from './AnalyticalMetric';
import { issuedPartialCounts } from './partial-value';
import { sharedClaimCaveats } from './presentation';
import i18n from './i18n';

// Metadata/transport records only. No financial expectation is derived here.
const sha = (letter: string) => letter.repeat(64);
const question = (): AnalyticsQuestion => ({ revision_id: 'revision', as_of: '2026-01-02', family: 'GAINS', window: { rule: 'SINCE_INCEPTION', months: null, base: null }, frequency: null, scope: { kind: 'PORTFOLIO', account_id: null }, view: 'REQUESTED', synthetic_acknowledged: true });
function evaluation(): AnalyticsEvaluation {
  const q = question(); const manifest = { portfolio_id: 'portfolio', ledger_version: 9, reporting_currency: 'USD', as_of: q.as_of, scope: 'PORTFOLIO', state_kind: 'ACTUAL', synthetic: true, release_id: sha('b'), engine_id: 'engine-test', conventions: [], window: { rule: 'SINCE_INCEPTION', months: null, start: q.as_of, end: q.as_of } };
  const metric: AnalyticsMetric = { metric_id: 'unrealized_gain_total', value: '0', state: 'AVAILABLE', reason: null, details: [], exact: '0/1', causes: [], manifest_id: sha('c'), unit: 'CURRENCY_AMOUNT', currency: 'USD', view: 'REPORTING', subject: [], method_id: 'transport-only', partial: false, excluded: [], excluded_weight: null, excluded_weight_presented: null, window: { start: q.as_of, end: q.as_of, rule: 'AS_OF' } };
  const result = { result_id: `GAINS:PERFORMANCE:${sha('c')}:${sha('d')}`, family: 'GAINS' as const, group: 'PERFORMANCE' as const, binding_digest: sha('e'), binding: { portfolio_id: 'portfolio', revision_id: 'revision', ledger_version: 9, as_of: q.as_of, scope: q.scope, reporting_currency: 'USD', family: 'GAINS', group: 'PERFORMANCE', question_digest: sha('a'), release_id: sha('b'), input_sha256: sha('f'), calendar_sha256: sha('a'), fixture_as_of: q.as_of, engine_id: 'engine-test', selection_pin: null, benchmark_catalog: null, risk_free_catalog: null, registry: null, conventions: [] }, engine_result: { manifest_id: sha('c'), result_digest: sha('d'), manifest, metrics: [metric] }, definitions: [] };
  return { schema_version: ANALYTICS_SCHEMA, portfolio_id: 'portfolio', revision_id: 'revision', persisted: false, synthetic: true, question: q, revision: { as_of: q.as_of, ledger_version: 9, selection_version: 0, reporting_currency: 'USD' }, results: [result], views: [{ metric_id: metric.metric_id, metric_index: 0, shown_result_id: result.result_id, fallback: false, refused_result_id: null, refused_metric_index: null, composition: null }], limits: { calculation_days: 3660, output_bytes: 2_000_000, http_bytes: 32_768 }, limitations: [] };
}
const parse = (value: unknown) => readAnalyticsEvaluation(value, 'portfolio', question(), 9);
const row = (value: AnalyticsEvaluation) => value.results[0].engine_result.metrics[0];
function riskEvaluation(): AnalyticsEvaluation {
  const value = evaluation(); const original = value.results[0];
  const q: AnalyticsQuestion = { ...question(), family: 'RISK', window: { rule: 'TRAILING_MONTHS', months: 36, base: null }, frequency: 'WEEKLY', view: 'DEFAULT' };
  const make = (letter: string, maximum: boolean) => {
    const manifestId = sha(letter); const resultDigest = sha(maximum ? 'a' : 'b');
    return { ...original, result_id: `RISK:INDEPENDENT:${manifestId}:${resultDigest}`, family: 'RISK' as const, group: 'INDEPENDENT' as const,
      binding: { ...original.binding, family: 'RISK', group: 'INDEPENDENT', engine_id: 'risk-test', registry: { id: 'risk-test', digest: sha('f') } },
      engine_result: { manifest_id: manifestId, result_digest: resultDigest,
        manifest: { risk_engine_id: 'risk-test', registry_id: 'risk-test', registry_digest: sha('f'), request_rule: maximum ? 'MAX_AVAILABLE' : 'TRAILING_MONTHS', request_months: maximum ? null : 36, request_base: null, end: q.as_of, frequency: 'WEEKLY', state_kind: 'ACTUAL', synthetic: true, benchmark: null, risk_free: null, series_manifest: { ...original.engine_result.manifest } },
        metrics: [{ metric_id: 'risk_volatility', value: null, exact: null, exact_square: null, sign: null, state: 'INSUFFICIENT_DATA' as const, reason: 'NOT_RECONSTRUCTABLE', details: [], causes: [], window: null, observation_count: null, frequency: 'WEEKLY', method_key: 'risk-test', manifest_id: manifestId }] },
    };
  };
  const x = make('c', false); const y = make('d', true);
  return { ...value, question: q, results: [x, y], views: [{ metric_id: 'risk_volatility', metric_index: 0, fallback: true, shown_result_id: y.result_id, refused_result_id: x.result_id, refused_metric_index: 0,
    composition: { default_request: { rule: 'TRAILING_MONTHS', months: 36 }, fallback: true, metric_id: 'risk_volatility', x_manifest_id: x.engine_result.manifest_id, x_result_digest: x.engine_result.result_digest, y_manifest_id: y.engine_result.manifest_id, y_result_digest: y.engine_result.result_digest } }] };
}
const session = { schema_version: 'finweb.cp7/1', authenticated: true, user: { user_id: 'user', username: 'transport_test' }, csrf_token: sha('a') };
const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200 });
afterEach(() => { vi.unstubAllGlobals(); });

describe('analytical result identity and completeness', () => {
  it('keeps AVAILABLE exact zero distinct from missing', () => {
    const value = parse(evaluation()); expect(row(value).value).toBe('0'); expect(row(value).exact).toBe('0/1'); expect(gainDirection(row(value))).toBe('zero');
  });
  it('keeps LIMITED zero gain and its issued excluded weight without rewriting valuation flags', () => {
    const value = evaluation(); Object.assign(row(value), { state: 'LIMITED', reason: 'MISSING_COST_BASIS', excluded_weight: '1/3', excluded_weight_presented: '0.333333333333' });
    const metric = row(parse(value)); expect(metric.partial).toBe(false); expect(metric.excluded).toEqual([]); expect(metric.value).toBe('0'); expect(metric.excluded_weight).toBe('1/3');
    const html = renderToStaticMarkup(createElement(AnalyticalMetric, { metric, result: value.results[0], question: value.question, depth: 'quick', colors: 'GREEN_GAIN', onEvidence: () => {} }));
    expect(html).toContain('1/3'); expect(html).toContain('Excluded components: Unknown'); expect(html).not.toContain('Value of priced holdings (partial)');
  });
  it('uses exact sign for color even when the presented value is rounded to zero', () => {
    const value = row(evaluation()); value.exact = '-1/100000'; value.value = '0.00'; expect(gainDirection(value)).toBe('negative');
  });
  it('rejects another owner, revision, ledger pin, scope or as-of even with matching outer family', () => {
    for (const change of [{ portfolio_id: 'foreign' }, { revision_id: 'other' }, { ledger_version: 10 }, { as_of: '2026-01-03' }, { scope: { kind: 'ACCOUNT', account_id: 'other' } }]) {
      const value = evaluation(); Object.assign(value.results[0].binding, change); expect(() => parse(value)).toThrow();
    }
  });
  it('refuses a response for another selected question or an engine manifest for another period', () => {
    const value = evaluation(); value.question.window = { rule: 'TRAILING_MONTHS', months: 36, base: null }; expect(() => parse(value)).toThrow();
    const wrong = evaluation(); wrong.results[0].engine_result.manifest.window = { rule: 'CUSTOM', months: null, start: '2025-01-01', end: question().as_of }; expect(() => parse(wrong)).toThrow();
  });
  it('refuses empty success or duplicate views that hide a different same-id subject', () => {
    const empty = evaluation(); empty.results = []; empty.views = []; expect(() => parse(empty)).toThrow();
    const value = evaluation(); value.results[0].engine_result.metrics.push({ ...row(value), subject: [['account', 'another']] }); value.views.push({ ...value.views[0] }); expect(() => parse(value)).toThrow();
    value.views[1].metric_index = 1; expect(parse(value).views).toHaveLength(2);
  });
  it('requires exact financial strings and an exact or complete radical witness when a value is present', () => {
    for (const change of [{ value: 0 }, { exact: null }, { exact_square: '1/2' }]) { const value = evaluation(); Object.assign(row(value), change); expect(() => parse(value)).toThrow(); }
  });
  it('suppresses all numerical witnesses, breakdowns and exclusion weights with unavailable values', () => {
    const value = evaluation(); Object.assign(row(value), { value: null, exact: null, state: 'INSUFFICIENT_DATA', reason: 'MISSING_COST_BASIS' }); expect(row(parse(value)).value).toBeNull();
    for (const leak of [{ exact: '0/1' }, { exact_square: '0/1', sign: 0 }, { breakdown: [['LEAK', '12', '12/1']] }, { excluded_weight: '1/3' }, { stale_weight: '1/3' }, { decomposition: [['LEAK', '12']] }]) {
      const attack = structuredClone(value); Object.assign(row(attack), leak); expect(() => parse(attack)).toThrow();
    }
  });
  it('does not attach a benchmark selection or catalog to a performance-only question', () => {
    const value = evaluation(); value.results[0].binding.selection_pin = { portfolio_id: 'foreign', state: 'IN_FORCE' }; expect(() => parse(value)).toThrow();
  });
  it('rejects a metric bound to a different manifest', () => { const value = evaluation(); row(value).manifest_id = sha('f'); expect(() => parse(value)).toThrow(); });
  it('preserves null risk observations and original/shown request roles without recomputing fallback', () => {
    const baseline = riskEvaluation(); const read = (value: AnalyticsEvaluation) => readAnalyticsEvaluation(value, 'portfolio', baseline.question, 9);
    expect(read(baseline).results[0].engine_result.metrics[0].observation_count).toBeNull();
    const hiddenOriginal = structuredClone(baseline); Object.assign(hiddenOriginal.views[0], { fallback: false, refused_result_id: null, refused_metric_index: null, composition: null }); expect(() => read(hiddenOriginal)).toThrow();
    const frequency = structuredClone(baseline); frequency.results[0].engine_result.metrics[0].frequency = 'DAILY'; expect(() => read(frequency)).toThrow();
    const registry = structuredClone(baseline); (registry.results[0].binding.registry as { digest: string }).digest = sha('a'); expect(() => read(registry)).toThrow();
    const swapped = structuredClone(baseline); const view = swapped.views[0]; [view.shown_result_id, view.refused_result_id] = [view.refused_result_id!, view.shown_result_id]; const composition = view.composition!;
    [composition.x_manifest_id, composition.y_manifest_id] = [composition.y_manifest_id, composition.x_manifest_id]; [composition.x_result_digest, composition.y_result_digest] = [composition.y_result_digest, composition.x_result_digest]; expect(() => read(swapped)).toThrow();
  });
});

describe('analytical evidence and identity lifetime', () => {
  it('requests the result’s own family/group/binding/manifest/digest, never a CP5 packet', async () => {
    const value = evaluation(); const result = value.results[0]; const proof = analyticalProof(value.question, result);
    const response = { schema_version: ANALYTICS_SCHEMA, portfolio_id: 'portfolio', revision_id: 'revision', question: value.question, result, ledger_reference: { portfolio_id: 'portfolio', revision_id: 'revision', ledger_version: 9, workspace_path: '/api/v1/portfolios/portfolio/workspace?revision_id=revision' }, limits: value.limits };
    const fetchMock = vi.fn().mockResolvedValueOnce(json(session)).mockResolvedValueOnce(json(response)); vi.stubGlobal('fetch', fetchMock);
    await new AccountApi().analyticalEvidence('portfolio', value.question, result); expect(fetchMock.mock.calls[1][0]).toContain('/analytics/evidence'); expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual(proof); expect(fetchMock.mock.calls[1][1].headers['X-Finweb-CSRF']).toBe(sha('a'));
    expect(() => readAnalyticsEvidence({ ...response, revision_id: 'other' }, 'portfolio', value.question, result)).toThrow();
  });
  it('does not certify a mismatched digest as reproduced', () => {
    const value = evaluation(); const result = value.results[0];
    const response = { schema_version: ANALYTICS_SCHEMA, portfolio_id: 'portfolio', revision_id: 'revision', family: result.family, group: result.group, result_id: result.result_id, binding_digest: result.binding_digest, expected_manifest_id: result.engine_result.manifest_id, expected_result_digest: result.engine_result.result_digest, status: 'REPRODUCED', detail: 'transport test', rerun_manifest_id: result.engine_result.manifest_id, rerun_result_digest: sha('a'), limits: value.limits };
    expect(() => readAnalyticsReproduction(response, 'portfolio', value.question, result)).toThrow(); response.status = 'RESULT_DIFFERS'; expect(readAnalyticsReproduction(response, 'portfolio', value.question, result).status).toBe('RESULT_DIFFERS');
  });
  it('drops a late analytical body after identity/workspace reset even when fetch ignores abort', async () => {
    let finish!: (value: unknown) => void; const callback = vi.fn();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json(session)).mockResolvedValueOnce({ ok: true, status: 200, json: () => new Promise((resolve) => { finish = resolve; }) }));
    const api = new AccountApi(); await api.session(); const pending = api.evaluateAnalytics('portfolio', question(), 9).then(callback); await Promise.resolve(); api.reset(); finish(evaluation());
    await expect(pending).rejects.toMatchObject({ code: 'REQUEST_CANCELLED' }); expect(callback).not.toHaveBeenCalled();
  });
});

describe('issued partial metadata and progressive explanation', () => {
  it('reads valuation component and holding counts separately from issued lineage, never array length', () => {
    const metric = { metric_id: 'portfolio_value_priced_holdings', partial: true, excluded: [], lineage: [['excluded_components', '2'], ['excluded_holdings', '1']] };
    expect(issuedPartialCounts(metric)).toEqual({ components: '2', holdings: '1' });
    for (const lineage of [[], [['excluded_components', '2']], [['excluded_components', '2'], ['excluded_holdings', 'NaN']], [['excluded_components', '2'], ['excluded_holdings', '1'], ['excluded_holdings', '1']]]) expect(issuedPartialCounts({ ...metric, lineage })).toBeNull();
  });
  it('does not use a gain exclusion weight as valuation partial metadata', () => { const value = row(evaluation()); value.excluded_weight = '7/11'; expect(issuedPartialCounts(value)).toBeNull(); });
  it('keeps issued partial exclusions and missing-input context visible while disclosing only the intact raw records', () => {
    const metric = { metric_id: 'portfolio_value_priced_holdings', value: '2200', currency: 'USD', state: 'LIMITED' as const, reason: 'INCOMPLETE_VALUATION', subject: [], details: [], partial: true, lineage: [['excluded_components', '1'], ['excluded_holdings', '0']],
      excluded: [{ ref: 'CASH:owned-account:CNY', kind: 'CASH', currency: 'CNY', native: '0', causes: [{ ref: 'CNY/USD:2026-01-02', state: 'INSUFFICIENT_DATA', reason: 'MISSING_FX_HISTORY', detail: 'FX_INPUT_MISSING', note: 'Original source note, retained in full.' }] }] };
    const before = JSON.stringify(metric); const html = renderToStaticMarkup(createElement(PartialValuationContext, { metric }));
    const disclosure = html.indexOf('<details class="partial-complete-exclusions">'); expect(disclosure).toBeGreaterThan(0);
    const visible = html.slice(0, disclosure); expect(visible).toContain('never the true portfolio total/NAV'); expect(visible).toContain('Excludes 0 unpriced holdings'); expect(visible).toContain('Excluded NAV components: 1');
    for (const fact of ['CASH:owned-account:CNY', 'CNY', '>0</span>', 'MISSING_FX_HISTORY', 'FX_INPUT_MISSING', 'CNY/USD:2026-01-02']) expect(visible).toContain(fact);
    expect(visible).not.toContain('Original source note'); expect(html).toContain(renderToStaticMarkup(createElement('pre', { className: 'raw-packet' }, JSON.stringify(metric.excluded, null, 2)))); expect(JSON.stringify(metric)).toBe(before);
  });
  it('shares only identical source-time context and keeps conclusion-changing limitations beside every claim', () => {
    const time = 'Source observation/retrieval timestamps are UNKNOWN unless supplied by the upstream manifest; as-of is not a retrieval timestamp';
    const split = sharedClaimCaveats([[time, 'MISSING_COST_BASIS', 'LIMITED_TEMPORAL_COMPARABILITY'], [time, 'MISSING_COST_BASIS']]); expect(split.shared).toEqual([time]); expect(split.local).toEqual([['MISSING_COST_BASIS', 'LIMITED_TEMPORAL_COMPARABILITY'], ['MISSING_COST_BASIS']]); expect(sharedClaimCaveats([[time], []]).shared).toEqual([]);
  });
  it('shares only the reviewed common restrictions present verbatim in every displayed packet, keeping all local financial qualifications', () => {
    const common = [
      'Cash/receivables use zero native interest and omit credit/liquidity/default risk',
      'Current fixed weights, historical association, not actual portfolio TWR or forecast',
      'No ETF look-through', 'Non-synchronous market closes can distort covariance',
      'Source observation/retrieval timestamps are UNKNOWN unless supplied by the upstream manifest; as-of is not a retrieval timestamp',
    ];
    const local = ['MISSING_COST_BASIS', 'SOURCE_FRESHNESS_UNKNOWN', 'LIMITED_TEMPORAL_COMPARABILITY', 'USER_POLICY', 'excluded_weight=7/11'];
    const claims = Array.from({ length: 12 }, (_, index) => [...common, ...local, `scope-${index}`]); const before = JSON.stringify(claims);
    const partition = sharedClaimCaveats(claims); expect(partition.shared).toEqual(common); expect(partition.local).toEqual(claims.map((_, index) => [...local, `scope-${index}`])); expect(JSON.stringify(claims)).toBe(before);
    const changed = claims.map((items) => [...items]); changed[11][2] = 'No ETF look-through except a separately issued scope';
    const qualified = sharedClaimCaveats(changed); expect(qualified.shared).not.toContain('No ETF look-through'); expect(qualified.local[0]).toContain('No ETF look-through'); expect(qualified.local[11]).toContain('No ETF look-through except a separately issued scope');
    expect(sharedClaimCaveats([claims[0]]).shared).toEqual([]);
  });
  it('keeps professional evidence and depth controls before the complete binding while retaining visible exact context pins', () => {
    const value = evaluation(); const before = JSON.stringify(value); value.results[0].binding.input_sha256 = sha('f');
    const html = renderToStaticMarkup(createElement(AnalyticalMetric, { metric: row(value), result: value.results[0], question: value.question, depth: 'professional', colors: 'GREEN_GAIN', onEvidence: () => {} }));
    const controls = html.indexOf('evidence-button'); const depth = html.indexOf('claim-depth'); const complete = html.indexOf('analytics-complete-binding');
    expect(controls).toBeGreaterThan(0); expect(depth).toBeGreaterThan(controls); expect(complete).toBeGreaterThan(depth);
    expect(html).toContain('transport-only'); expect(html).toContain(value.results[0].engine_result.manifest_id); expect(html).toContain('revision'); expect(html).toContain('Ledger sequence pin'); expect(html).toContain(sha('f'));
    expect(html).toContain('<details class="analytics-complete-binding">'); expect(JSON.stringify(value)).toBe(before);
  });
  it('preserves exact zero, own as-of window and evidence across all three depths and both languages', async () => {
    const value = evaluation(); const before = JSON.stringify(value);
    for (const language of ['en', 'zh-CN']) { await i18n.changeLanguage(language); for (const depth of ['quick', 'simple', 'professional'] as const) {
      const html = renderToStaticMarkup(createElement(AnalyticalMetric, { metric: row(value), result: value.results[0], question: value.question, depth, colors: 'GREEN_GAIN', onEvidence: () => {} }));
      expect(html).toContain('gain-zero'); expect(html).toContain('2026-01-02'); expect(html).toContain('evidence-button'); expect(html).not.toContain('unavailable-value'); if (depth === 'professional') expect(html).toContain('transport-only');
    } }
    expect(JSON.stringify(value)).toBe(before); await i18n.changeLanguage('en');
  });
});
