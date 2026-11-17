import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router';
import { AccountApi, isCancelled } from './account';
import type { Workspace } from './workspace';
import type { ExplanationDepth } from './ClaimDepth';
import type { AnalyticsEvaluation, AnalyticsFamily, AnalyticsQuestion, AnalyticsResult } from './analytics';
import AnalyticalMetric, { type GainColors } from './AnalyticalMetric';
import AnalyticalEvidenceDialog, { type AnalyticalSelection } from './AnalyticalEvidence';
import { errorLabel, metricLabel, limitationLabel, reasonLabel } from './presentation';

export function analyticalQuestion(workspace: Workspace, family: AnalyticsFamily): AnalyticsQuestion {
  return { revision_id: workspace.revision_id, as_of: workspace.as_of, family,
    window: { rule: family === 'RISK' ? 'TRAILING_MONTHS' : 'SINCE_INCEPTION', months: family === 'RISK' ? 36 : null, base: null },
    frequency: family === 'RISK' ? 'WEEKLY' : null, scope: { kind: 'PORTFOLIO', account_id: null }, view: family === 'RISK' ? 'DEFAULT' : 'REQUESTED', synthetic_acknowledged: true };
}
function ResultViews({ evaluation, depth, colors, onEvidence, compact = false }: {
  evaluation: AnalyticsEvaluation; depth: ExplanationDepth; colors: GainColors; onEvidence: (result: AnalyticsResult) => void; compact?: boolean;
}) {
  const { t } = useTranslation();
  const views = compact ? evaluation.views.filter((view) => evaluation.question.family === 'RISK' ? view.metric_id === 'risk_volatility' : view.metric_id === 'return_twr' || view.metric_id === 'gain_absolute') : evaluation.views;
  return <><div className="scope-strip"><strong>{t(`analyticsFamily_${evaluation.question.family}`)}</strong><span>{evaluation.question.as_of}</span><span>{t(`analyticsRule_${evaluation.question.window.rule}`)}{evaluation.question.window.months !== null ? ` · ${evaluation.question.window.months}` : ''}</span><code>{evaluation.revision_id}</code></div>
    <p className="input-help">{t('analyticsFixtureDate')}: {String(evaluation.results[0].binding.fixture_as_of)} · {t('analyticsFreshnessNote')}</p>
    <div className="metric-grid analytics-results">{views.map((view, index) => {
      const result = evaluation.results.find((item) => item.result_id === view.shown_result_id)!; const metric = result.engine_result.metrics[view.metric_index];
      const refused = view.refused_result_id ? evaluation.results.find((item) => item.result_id === view.refused_result_id) : null;
      return <div className="analytics-view" key={`${view.shown_result_id}:${view.metric_index}:${index}`}>
        <p className="meta-label">{t(`analyticsGroup_${result.group}`)}</p>
        <AnalyticalMetric metric={metric} result={result} question={evaluation.question} depth={depth} colors={colors} onEvidence={onEvidence} />
        {view.fallback && refused && <div className="fallback-evidence"><p>{t('analyticsFallback')}</p><p className="input-help">{t('analyticsRefused')}: {metricLabel(t, view.metric_id)} · {t('INSUFFICIENT_DATA')}</p>
          <p>{reasonLabel(t, refused.engine_result.metrics[view.refused_metric_index!].reason ?? 'UNKNOWN')}</p>
          <button type="button" className="text-button" onClick={() => onEvidence(refused)}>{t('analyticsRefused')} · {t('evidence')}</button><code>{refused.engine_result.manifest_id}</code>
          <details><summary>{t('analyticsContext')}</summary><pre className="raw-packet">{JSON.stringify({ refused_metric: refused.engine_result.metrics[view.refused_metric_index!], composition: view.composition }, null, 2)}</pre></details></div>}
      </div>;
    })}</div>
    {!compact && <><p className="notice neutral-notice">{t(`analyticsDefinition_${evaluation.question.family}`)} {evaluation.question.family === 'GAINS' ? t('analyticsGainCaveat') : evaluation.question.family === 'ATTRIBUTION' ? t('analyticsAttributionCaveat') : ''}</p>
      <div className="limitations compact"><strong>{t('limitations')}</strong><ul>{evaluation.limitations.map((item) => <li key={item}>{limitationLabel(t, item)}</li>)}</ul></div>
      <details><summary>{t('analyticsContext')}</summary><pre className="raw-packet">{JSON.stringify({ question: evaluation.question, revision: evaluation.revision, limits: evaluation.limits }, null, 2)}</pre></details></>}
  </>;
}

export function ContextualAiEntry() { const { t } = useTranslation(); return <aside className="notice neutral-notice contextual-ai"><strong>{t('aiDeferredTitle')}</strong><p>{t('aiDeferredBody')}</p></aside>; }

export function AnalyticsSummary({ workspace, api, family, depth, colors }: { workspace: Workspace | null | undefined; api: AccountApi; family: 'PERFORMANCE_WINDOW' | 'RISK'; depth: ExplanationDepth; colors: GainColors }) {
  const { t } = useTranslation(); const [evaluation, setEvaluation] = useState<AnalyticsEvaluation | null>(null); const [error, setError] = useState<unknown>(null);
  const [selection, setSelection] = useState<AnalyticalSelection | null>(null); const epoch = useRef(0);
  useEffect(() => {
    const token = ++epoch.current; setEvaluation(null); setSelection(null); setError(null);
    if (workspace) { const question = analyticalQuestion(workspace, family);
      void api.evaluateAnalytics(workspace.portfolio_id, question, workspace.ledger.version).then((value) => { if (epoch.current === token) setEvaluation(value); })
        .catch((failure: unknown) => { if (epoch.current === token && !isCancelled(failure)) setError(failure); }); }
    return () => { epoch.current += 1; };
  }, [workspace, family, api]);
  return <section className="analytics-summary" aria-label={t(family === 'RISK' ? 'analyticsRiskSummary' : 'analyticsPerformanceSummary')}><div className="section-heading"><h2>{t(family === 'RISK' ? 'analyticsRiskSummary' : 'analyticsPerformanceSummary')}</h2><NavLink className="text-button" to="/analytics">{t('analyticsOpen')}</NavLink></div>
    {!workspace ? <p className="notice neutral-notice">{t('analyticsGuest')}</p> : error !== null ? <p className="notice error-notice" role="alert">{errorLabel(t, error)}</p> : !evaluation ? <p role="status">{t('analyticsLoading')}</p>
      : <ResultViews evaluation={evaluation} depth={depth} colors={colors} compact onEvidence={(result) => setSelection({ portfolioId: workspace.portfolio_id, question: evaluation.question, result })} />}
    {selection && <AnalyticalEvidenceDialog key={`${selection.question.revision_id}:${selection.result.result_id}`} api={api} selection={selection} onClose={() => setSelection(null)} />}
  </section>;
}

export default function AnalyticsPanel({ workspace, api, depth, colors }: { workspace: Workspace | null | undefined; api: AccountApi; depth: ExplanationDepth; colors: GainColors }) {
  const { t } = useTranslation(); const [family, setFamily] = useState<AnalyticsFamily>('PERFORMANCE_WINDOW');
  const [rule, setRule] = useState<AnalyticsQuestion['window']['rule']>('SINCE_INCEPTION'); const [months, setMonths] = useState(36); const [base, setBase] = useState('');
  const [frequency, setFrequency] = useState<'DAILY' | 'WEEKLY' | 'MONTHLY'>('WEEKLY'); const [scope, setScope] = useState(''); const [defaultRisk, setDefaultRisk] = useState(false);
  const [evaluation, setEvaluation] = useState<AnalyticsEvaluation | null>(null); const [error, setError] = useState<unknown>(null); const [busy, setBusy] = useState(false);
  const [selection, setSelection] = useState<AnalyticalSelection | null>(null); const epoch = useRef(0);
  useEffect(() => () => { epoch.current += 1; }, []);
  function changed() { epoch.current += 1; setEvaluation(null); setSelection(null); setError(null); setBusy(false); }
  async function evaluate() {
    if (!workspace) return;
    const question: AnalyticsQuestion = { revision_id: workspace.revision_id, as_of: workspace.as_of, family,
      window: { rule, months: rule === 'TRAILING_MONTHS' ? months : null, base: rule === 'CUSTOM' ? base : null }, frequency: family === 'RISK' ? frequency : null,
      scope: scope ? { kind: 'ACCOUNT', account_id: scope } : { kind: 'PORTFOLIO', account_id: null }, view: family === 'RISK' && defaultRisk ? 'DEFAULT' : 'REQUESTED', synthetic_acknowledged: true };
    const token = ++epoch.current; setEvaluation(null); setSelection(null); setError(null); setBusy(true);
    try { const value = await api.evaluateAnalytics(workspace.portfolio_id, question, workspace.ledger.version); if (epoch.current === token) setEvaluation(value); }
    catch (failure) { if (epoch.current === token && !isCancelled(failure)) setError(failure); }
    finally { if (epoch.current === token) setBusy(false); }
  }
  return <section className="analytical-workspace" aria-labelledby="analytical-questions"><div className="section-heading"><h2 id="analytical-questions">{t('analyticsQuestions')}</h2></div><p className="input-help">{t('analyticsScope')}</p><p className="input-help">{t('analyticsLimits')}</p>
    {!workspace ? <p className="notice neutral-notice">{t('analyticsGuest')}</p> : <><div className="card command-form analytics-form"><div className="editor-grid">
      <div className="form-row"><label htmlFor="analytics-family">{t('analyticsFamily')}</label><select id="analytics-family" value={family} onChange={(event) => { changed(); const next = event.target.value as AnalyticsFamily; setFamily(next); setRule(next === 'RISK' ? 'TRAILING_MONTHS' : 'SINCE_INCEPTION'); setMonths(36); setDefaultRisk(next === 'RISK'); }}>
        {(['PERFORMANCE_WINDOW', 'GAINS', 'ATTRIBUTION', 'RISK'] as const).map((item) => <option key={item} value={item}>{t(`analyticsFamily_${item}`)}</option>)}</select></div>
      <div className="form-row"><label htmlFor="analytics-scope">{t('analyticsAccountScope')}</label><select id="analytics-scope" value={scope} onChange={(event) => { changed(); setScope(event.target.value); }}><option value="">{t('analyticsPortfolio')}</option>{workspace.accounts.map((account) => <option key={account.account_id} value={account.account_id}>{account.name}</option>)}</select></div>
      <div className="form-row"><label htmlFor="analytics-rule">{t('analyticsWindow')}</label><select id="analytics-rule" value={rule} disabled={family === 'RISK' && defaultRisk} onChange={(event) => { changed(); setRule(event.target.value as typeof rule); }}>
        {(['TRAILING_MONTHS', 'YTD', 'SINCE_INCEPTION', 'CUSTOM', ...(family === 'RISK' ? ['MAX_AVAILABLE'] : [])] as const).map((item) => <option key={item} value={item}>{t(`analyticsRule_${item}`)}</option>)}</select></div>
      {rule === 'TRAILING_MONTHS' && <div className="form-row"><label htmlFor="analytics-months">{t('analyticsMonths')}</label><select id="analytics-months" value={months} disabled={family === 'RISK' && defaultRisk} onChange={(event) => { changed(); setMonths(Number(event.target.value)); }}>{[1, 3, 6, 12, 36, 60].map((item) => <option key={item} value={item}>{item}</option>)}</select></div>}
      {rule === 'CUSTOM' && <div className="form-row"><label htmlFor="analytics-base">{t('analyticsBase')}</label><input id="analytics-base" type="date" value={base} onChange={(event) => { changed(); setBase(event.target.value); }} /></div>}
      {family === 'RISK' && <><div className="form-row"><label htmlFor="analytics-frequency">{t('analyticsFrequency')}</label><select id="analytics-frequency" value={frequency} onChange={(event) => { changed(); setFrequency(event.target.value as typeof frequency); }}>{(['DAILY', 'WEEKLY', 'MONTHLY'] as const).map((item) => <option key={item} value={item}>{t(`analyticsFrequency_${item}`)}</option>)}</select></div>
        <div className="form-row"><label htmlFor="analytics-risk-view">{t('analyticsView')}</label><select id="analytics-risk-view" value={defaultRisk ? 'DEFAULT' : 'REQUESTED'} onChange={(event) => { changed(); const useDefault = event.target.value === 'DEFAULT'; setDefaultRisk(useDefault); if (useDefault) { setRule('TRAILING_MONTHS'); setMonths(36); } }}><option value="REQUESTED">{t('analyticsRequested')}</option><option value="DEFAULT">{t('analyticsDefault')}</option></select></div></>}
      </div><p className="input-help">{t('asOf')}: {workspace.as_of} · <code>{workspace.revision_id}</code></p><button className="primary-button" type="button" disabled={busy || rule === 'CUSTOM' && !base} onClick={() => { void evaluate(); }}>{t('analyticsEvaluate')}</button></div>
      <div className="analytics-result-region" aria-live="polite" aria-busy={busy}>{busy ? <p role="status">{t('analyticsLoading')}</p> : error !== null ? <p className="notice error-notice" role="alert">{errorLabel(t, error)}</p> : evaluation ? <ResultViews evaluation={evaluation} depth={depth} colors={colors} onEvidence={(result) => setSelection({ portfolioId: workspace.portfolio_id, question: evaluation.question, result })} /> : <p>{t('analyticsNoResult')}</p>}</div>
    </>}
    {selection && <AnalyticalEvidenceDialog key={`${selection.question.revision_id}:${selection.result.result_id}`} api={api} selection={selection} onClose={() => setSelection(null)} />}
  </section>;
}
