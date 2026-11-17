import { useTranslation } from 'react-i18next';
import ClaimDepth, { type ExplanationDepth } from './ClaimDepth';
import { isObject, type Metric } from './transport';
import { exactWitnesses, metricLabel, reasonLabel, subjectLabel } from './presentation';
import type { AnalyticsMetric, AnalyticsQuestion, AnalyticsResult } from './analytics';
import { issuedPartialCounts } from './partial-value';

export type GainColors = 'GREEN_GAIN' | 'RED_GAIN';
const directional = new Set(['gain_absolute', 'return_twr', 'return_annualized', 'return_mwr', 'return_mwr_annualized', 'realized_gain', 'realized_gain_total', 'unrealized_gain', 'unrealized_gain_total', 'since_acquisition', 'attribution_money', 'attribution_return']);
/** String sign presentation only; never compare amounts or calculate a financial value. */
export function gainDirection(metric: AnalyticsMetric): 'positive' | 'negative' | 'zero' | null {
  if (!directional.has(metric.metric_id) || metric.state === 'INSUFFICIENT_DATA' || metric.value === null) return null;
  const witness = metric.exact ?? metric.value;
  return /^-?0(?:\.0+|\/[1-9]\d*)?$/.test(witness) ? 'zero' : witness.startsWith('-') ? 'negative' : 'positive';
}
export function metricPeriod(metric: AnalyticsMetric): string | null {
  return isObject(metric.window) && typeof metric.window.start === 'string' && typeof metric.window.end === 'string'
    ? `${metric.window.start} → ${metric.window.end}` : null;
}
const shown = (value: unknown, unknown: string) => value === null || value === undefined ? unknown : typeof value === 'string' || typeof value === 'number' ? String(value) : JSON.stringify(value);

export function PartialValuationContext({ metric }: { metric: Metric }) {
  const { t } = useTranslation(); const counts = issuedPartialCounts(metric);
  if (!counts) return null;
  const records = Array.isArray(metric.excluded) ? metric.excluded.filter(isObject) : [];
  return <div className="notice neutral-notice partial-valuation"><strong>{t('analyticsPartialNav')}</strong><p>{t('analyticsPartialNotNav')}</p>
    <p>{t('partialExcludesHoldings', { count: counts.holdings })}</p><p>{t('partialExcludesComponents', { count: counts.components })}</p>
    <ul className="partial-excluded-context">{records.map((record, index) => <li key={index}>
      <p className="mono">{typeof record.kind === 'string' ? record.kind : t('UNKNOWN')} · {typeof record.ref === 'string' ? record.ref : t('UNKNOWN')}</p>
      <p>{t('currency')}: {typeof record.currency === 'string' ? record.currency : t('UNKNOWN')} · {t('partialNativeFact')}: <span className="mono">{typeof record.native === 'string' ? record.native : t('UNKNOWN')}</span></p>
      {Array.isArray(record.causes) && record.causes.filter(isObject).map((cause, causeIndex) => <p className="reason-text" key={causeIndex}>
        {typeof cause.state === 'string' && <span>{t(cause.state, { defaultValue: cause.state })} · </span>}
        {typeof cause.reason === 'string' && <>{reasonLabel(t, cause.reason)} <code>{cause.reason}</code> </>}
        {typeof cause.detail === 'string' && cause.detail && <code>{cause.detail} </code>}
        {typeof cause.ref === 'string' && <span className="mono">{cause.ref}</span>}
      </p>)}
    </li>)}</ul>
    <details className="partial-complete-exclusions"><summary>{t('partialCompleteExclusions')}</summary><pre className="raw-packet">{JSON.stringify(metric.excluded ?? [], null, 2)}</pre></details>
  </div>;
}

export function AnalyticsFreshness({ metric }: { metric: AnalyticsMetric }) {
  const { t } = useTranslation(); const freshness = isObject(metric.freshness) ? metric.freshness : null;
  const entries = freshness && Array.isArray(freshness.entries) ? freshness.entries.filter(isObject) : [];
  return <div className="freshness-panel analytics-freshness">
    {[{ title: 'priceFreshness', rows: entries.filter((row) => String(row.kind).startsWith('EXCHANGE')) }, { title: 'fxFreshness', rows: entries.filter((row) => row.kind === 'CURRENCY') }].map((axis) => <div key={axis.title}><span className="meta-label">{t(axis.title)}</span>
      {axis.rows.length ? axis.rows.map((row, index) => <p key={index}><span>{String(row.key)} · {t(String(row.state), { defaultValue: String(row.state) })}</span><span className="freshness-date">{shown(row.date_used, t('UNKNOWN'))}</span>
        <span className="freshness-date">{t('analyticsSourceObserved')}: {shown(row.observed_at, t('UNKNOWN'))}</span><span className="freshness-date">{t('analyticsSourceRetrieved')}: {shown(row.retrieved_at, t('UNKNOWN'))}</span></p>) : <p>{t('analyticsFreshnessUnknown')}</p>}</div>)}
    <div className="historical-freshness"><span className="meta-label">{t('analyticsHistoricalFreshness')}</span><p>{metricPeriod(metric) ?? t('analyticsUnknownWindow')}</p>
      <p>{t('analyticsObservations')}: {shown(metric.observation_count, t('analyticsCountUnknown'))}</p>
      <p>{t('analyticsSourceObserved')}: {shown(freshness?.observed_at, t('UNKNOWN'))} · {t('analyticsSourceRetrieved')}: {shown(freshness?.retrieved_at, t('UNKNOWN'))}</p></div>
    <p className="freshness-explanation">{t('analyticsFreshnessNote')}</p>
  </div>;
}

export function AnalyticalDetails({ metric, result, question }: { metric: AnalyticsMetric; result: AnalyticsResult; question: AnalyticsQuestion }) {
  const { t } = useTranslation(); const witnesses = exactWitnesses({ ...metric, subject: metric.subject ?? [] });
  const rows: [string, unknown][] = [
    ['method', metric.method_id ?? metric.method_key], ['analyticsSource', result.engine_result.manifest_id], ['resultDigest', result.engine_result.result_digest],
    ['analyticsRequestedPeriod', question.window], ['analyticsPeriod', metric.window], ['analyticsFrequency', metric.frequency ?? null], ['analyticsObservations', metric.observation_count ?? null],
    ['analyticsThresholds', metric.thresholds ?? null], ['analyticsMetricView', metric.view ?? null],
    ['evidenceRevision', result.binding.revision_id], ['ledgerVersion', result.binding.ledger_version], ['analyticsAccountScope', result.binding.scope],
    ['asOf', result.binding.as_of], ['reportingCurrency', result.binding.reporting_currency], ['source', result.binding.release_id],
  ];
  return <><dl className="technical-details analytics-method-details">{witnesses.map((row) => <div key={row.label}><dt>{t(row.label)}</dt><dd className="mono">{row.value}</dd></div>)}
    {rows.map(([label, value]) => <div key={label}><dt>{t(label)}</dt><dd className="mono">{shown(value, t('UNKNOWN'))}</dd></div>)}</dl>
    <AnalyticsFreshness metric={metric} />
    <details className="analytics-complete-binding"><summary>{t('analyticsCompleteBinding')}</summary><pre className="raw-packet">{JSON.stringify(result.binding, null, 2)}</pre></details>
    <details><summary>{t('method')}</summary><pre className="raw-packet">{JSON.stringify(result.definitions, null, 2)}</pre></details></>;
}

export default function AnalyticalMetric({ metric, result, question, depth, colors, onEvidence }: {
  metric: AnalyticsMetric; result: AnalyticsResult; question: AnalyticsQuestion; depth: ExplanationDepth; colors: GainColors;
  onEvidence: (result: AnalyticsResult) => void;
}) {
  const { t } = useTranslation(); const direction = gainDirection(metric); const period = metricPeriod(metric);
  const subject = Array.isArray(metric.subject) ? subjectLabel(t, { ...metric, subject: metric.subject }) : '';
  const exclusions = metric.excluded_weight !== undefined && metric.excluded_weight !== null;
  const partialCounts = issuedPartialCounts(metric);
  const issues = [...new Set([...(metric.reason ? [metric.reason] : []), ...metric.details, ...metric.causes.map((cause) => String(cause.reason ?? cause.code ?? '')).filter(Boolean)])];
  return <ClaimDepth depth={depth} claim={metricLabel(t, metric.metric_id)}>{(activeDepth, control) => <article className={`card metric-card analytical-metric colors-${colors.toLowerCase()}`} data-metric-id={metric.metric_id} data-state={metric.state}>
    <div className="metric-topline"><span>{metricLabel(t, metric.metric_id)}</span><span className={`state-badge state-${metric.state.toLowerCase()}`}>{t(metric.state)}</span></div>
    {metric.partial === true && !partialCounts ? <p className="validation" role="alert">{t('invalidResponse')}</p> : metric.state === 'INSUFFICIENT_DATA' ? <p className="unavailable-value">{t('INSUFFICIENT_DATA')}</p>
      : <p className={`metric-value ${direction ? `gain-${direction}` : ''}`}><span>{metric.value}</span>{metric.currency && <span className="metric-unit">{metric.currency}</span>}</p>}
    {direction && <span className={`gain-label gain-${direction}`}>{t(direction === 'zero' ? 'gainZero' : direction === 'positive' ? 'gainPositive' : 'gainNegative')}</span>}
    <p className="semantic-unit">{metric.unit ? t(`analyticsUnit_${metric.unit}`, { defaultValue: metric.unit }) : t('unit_seeMethod')}</p>
    <p className="scope-label">{t('analyticsMetricView')}: {String(metric.view ?? result.group)}{subject ? ` · ${subject}` : ''}</p>
    <p className="scope-label">{t(isObject(metric.window) && metric.window.rule === 'AS_OF' ? 'asOf' : 'analyticsPeriod')}: {period ?? t('analyticsUnknownWindow')}</p>
    {question.family === 'RISK' && <p className="scope-label">{t('analyticsFrequency')}: {t(`analyticsFrequency_${metric.frequency ?? question.frequency}`)} · {t('analyticsObservations')}: {shown(metric.observation_count, t('analyticsCountUnknown'))}</p>}
    {exclusions && <div className="notice neutral-notice gain-exclusions"><strong>{t('analyticsPartial')}</strong><p>{t('analyticsExcludedWeight')}: <span className="mono">{metric.excluded_weight}</span>{metric.excluded_weight_presented !== null && metric.excluded_weight_presented !== undefined ? ` · ${metric.excluded_weight_presented}` : ''}</p><p>{t('analyticsExcludedCount', { count: t('UNKNOWN') })}</p></div>}
    {metric.partial === true && partialCounts && <PartialValuationContext metric={{ ...metric, subject: metric.subject ?? [] }} />}
    {issues.length > 0 && <div className="limitations compact"><strong>{t('limitations')}</strong><ul>{issues.map((issue) => <li key={issue}>{reasonLabel(t, issue)}</li>)}</ul></div>}
    {activeDepth !== 'quick' && <p className="metric-explanation">{t(`definition_${metric.metric_id}`, { defaultValue: t(`analyticsDefinition_${question.family}`) })}</p>}
    {Array.isArray(metric.breakdown) && metric.breakdown.length > 0 && <dl className="technical-details analytics-breakdown">{metric.breakdown.map((entry, index) => Array.isArray(entry) && entry.length >= 2 ? <div key={index}><dt>{t(`analyticsLine_${String(entry[0])}`, { keySeparator: false, defaultValue: String(entry[0]) })}</dt><dd className="mono">{shown(entry[1], t('UNKNOWN'))}</dd></div> : null)}</dl>}
    <button type="button" className="evidence-button" onClick={() => onEvidence(result)}>{t('analyticsEvidence')} ↗</button>{control}
    {activeDepth === 'professional' && <AnalyticalDetails metric={metric} result={result} question={question} />}
  </article>}</ClaimDepth>;
}
