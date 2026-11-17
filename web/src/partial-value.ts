/** These are issued lineage counts, not counts inferred from the excluded list. */
export function issuedPartialCounts(value: unknown): { components: string; holdings: string } | null {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return null;
  const metric = value as Record<string, unknown>;
  if (metric.metric_id !== 'portfolio_value_priced_holdings' || metric.partial !== true || !Array.isArray(metric.lineage)) return null;
  const values = new Map<string, string>();
  for (const pair of metric.lineage) {
    if (!Array.isArray(pair) || pair.length !== 2 || typeof pair[0] !== 'string') return null;
    if (['excluded_components', 'excluded_holdings'].includes(pair[0])) {
      if (values.has(pair[0]) || typeof pair[1] !== 'string' || !/^(?:0|[1-9]\d*)$/.test(pair[1])) return null;
      values.set(pair[0], pair[1]);
    }
  }
  return values.has('excluded_components') && values.has('excluded_holdings')
    ? { components: values.get('excluded_components')!, holdings: values.get('excluded_holdings')! } : null;
}
