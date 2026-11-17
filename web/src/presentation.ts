import type { TFunction } from 'i18next';
import { ApiError, isObject, packetPolicy, type Metric, type Packet } from './transport';

/** Translate an issued claim; do not decide whether the source value breaches a limit. */
export function observationClaim(t: TFunction, packet: Packet, asOf: string): string {
  const metric = packet.metrics_used[0]?.metric;
  if (packet.insight_type === 'metric_snapshot' && metric) return t('snapshotObservation', { metric: metricLabel(t, metric.metric_id), value: metric.value, asOf });
  const policy = packetPolicy(packet);
  if (packet.insight_type === 'user_limit' && policy && metric) return t(policy.direction === 'MAXIMUM' ? 'userLimitClaimMaximum' : 'userLimitClaimMinimum', {
    metric: metricLabel(t, metric.metric_id), value: metric.value, limit: policy.limit,
  });
  return packet.claim.text;
}

export function metricLabel(t: TFunction, id: string): string {
  return t(`metric_${id}`, { defaultValue: id });
}
export function reasonLabel(t: TFunction, reason: string): string {
  return t(`reason_${reason}`, { defaultValue: t('unknownReason', { code: reason }) });
}
export function limitationLabel(t: TFunction, text: string): string {
  return t([`limitation_${text}`, `reason_${text}`], { keySeparator: false, defaultValue: text });
}
export function errorLabel(t: TFunction, error: unknown): string {
  if (!(error instanceof ApiError)) return t('apiError');
  if (error.code === 'NETWORK_ERROR') return t('networkError');
  if (error.code === 'INVALID_RESPONSE') return t('invalidResponse');
  if (error.code === 'INVALID_CREDENTIALS') return t('reason_INVALID_CREDENTIALS');
  if (error.code === 'AUTHENTICATION_REQUIRED') return t('accountSessionExpired');
  if (error.status === 401) return t('sessionExpired');
  return reasonLabel(t, error.code);
}
export function metricSubject(metric: Metric): string {
  return metric.subject.map((v) => Array.isArray(v) ? v.join(': ') : String(v)).join(' · ');
}
export function subjectLabel(t: TFunction, metric: Metric): string {
  return metric.subject.map((value) => {
    if (Array.isArray(value)) return value.map(String).join(': ');
    const code = String(value);
    return t(`subject_${code}`, { defaultValue: code });
  }).join(' · ');
}
/** Semantic units from the issued CP5 method, without formatting or recomputation. */
export function metricUnit(t: TFunction, id: string): string {
  if (['largest_position_weight', 'largest_security_weight', 'top5_concentration', 'asset_class_exposure',
    'country_exposure', 'currency_exposure', 'sector_exposure'].includes(id)) return t('unit_navShare');
  const keys: Record<string, string> = {
    portfolio_value: 'unit_currencyAmount', portfolio_value_priced_holdings: 'unit_currencyAmount', hhi_concentration: 'unit_hhi',
    effective_positions: 'unit_effectiveCount', modeled_volatility: 'unit_volatility',
    risk_contribution_component: 'unit_volatilityContribution', risk_contribution_share: 'unit_varianceShare',
    average_correlation: 'unit_correlation', pairwise_correlation: 'unit_correlation',
    correlation_cluster_count: 'unit_clusterCount',
  };
  return keys[id] ? t(keys[id]) : t('unit_seeMethod');
}
/** Retain each issued exact representation; a missing rational is not a data state. */
export function exactWitnesses(metric: Metric): { label: string; value: string }[] {
  const rows: { label: string; value: string }[] = [];
  if (typeof metric.exact === 'string') rows.push({ label: 'exactValue', value: metric.exact });
  if (typeof metric.exact_square === 'string') {
    rows.push({ label: 'exactSquare', value: metric.exact_square });
    if (typeof metric.sign === 'number' || typeof metric.sign === 'string') rows.push({ label: 'witnessSign', value: String(metric.sign) });
  }
  if (Array.isArray(metric.radical_terms) && metric.radical_terms.length > 0) {
    rows.push({ label: 'radicalWitness', value: JSON.stringify(metric.radical_terms) });
  }
  return rows;
}
export function packetForMetric(packets: Packet[], metric: Metric): Packet | undefined {
  const subject = metricSubject(metric);
  return packets.find((p) => p.metrics_used.some((m) => m.reference.metric_id === metric.metric_id
    && m.reference.subject.join(' · ') === subject));
}
export function freshnessEntries(metric: Metric): Record<string, unknown>[] {
  return isObject(metric.freshness) && Array.isArray(metric.freshness.entries)
    ? metric.freshness.entries.filter(isObject) : [];
}
/** Reviewed group restrictions only, and only when every displayed claim carries them. */
export function sharedClaimCaveats(claims: string[][]): { shared: string[]; local: string[][] } {
  const allowed = [
    'Cash/receivables use zero native interest and omit credit/liquidity/default risk',
    'Current fixed weights, historical association, not actual portfolio TWR or forecast',
    'No ETF look-through',
    'Non-synchronous market closes can distort covariance',
    'Source observation/retrieval timestamps are UNKNOWN unless supplied by the upstream manifest; as-of is not a retrieval timestamp',
  ];
  const shared = claims.length > 1 ? allowed.filter((context) => claims.every((items) => items.includes(context))) : [];
  return { shared, local: claims.map((items) => [...new Set(items)].filter((item) => !shared.includes(item))) };
}
