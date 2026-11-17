import { ApiError, isObject, type DataState, type JsonObject } from './transport';
import { issuedPartialCounts } from './partial-value';

export const ANALYTICS_SCHEMA = 'finweb.cp7.analytics/1';
export type AnalyticsFamily = 'PERFORMANCE_WINDOW' | 'GAINS' | 'ATTRIBUTION' | 'RISK';
export interface AnalyticsQuestion {
  revision_id: string; as_of: string; family: AnalyticsFamily;
  window: { rule: 'TRAILING_MONTHS' | 'YTD' | 'SINCE_INCEPTION' | 'CUSTOM' | 'MAX_AVAILABLE'; months: number | null; base: string | null };
  frequency: 'DAILY' | 'WEEKLY' | 'MONTHLY' | null; scope: { kind: 'PORTFOLIO' | 'ACCOUNT'; account_id: string | null };
  view: 'REQUESTED' | 'DEFAULT'; synthetic_acknowledged: true;
}
export type AnalyticsMetric = JsonObject & {
  metric_id: string; value: string | null; state: DataState; reason: string | null; details: string[];
  window: JsonObject | null; exact: string | null; exact_square?: string | null; sign?: number | null;
  subject?: unknown[]; unit?: string; currency?: string | null; method_id?: string; method_key?: string;
  causes: JsonObject[]; manifest_id: string; partial?: boolean; excluded?: JsonObject[];
  excluded_weight?: string | null; excluded_weight_presented?: string | null;
};
export interface AnalyticsResult {
  result_id: string; family: AnalyticsFamily; group: 'PERFORMANCE' | 'INDEPENDENT' | 'BENCHMARK';
  binding: JsonObject; binding_digest: string;
  engine_result: { manifest_id: string; result_digest: string; manifest: JsonObject; metrics: AnalyticsMetric[] };
  definitions: JsonObject[];
}
export interface AnalyticsView {
  metric_id: string; metric_index: number; fallback: boolean; shown_result_id: string;
  refused_result_id: string | null; refused_metric_index: number | null; composition: JsonObject | null;
}
export interface AnalyticsEvaluation {
  schema_version: typeof ANALYTICS_SCHEMA; portfolio_id: string; revision_id: string; persisted: false; synthetic: true;
  question: AnalyticsQuestion; revision: { as_of: string; ledger_version: number; selection_version: number; reporting_currency: string };
  results: AnalyticsResult[]; views: AnalyticsView[]; limits: JsonObject; limitations: string[];
}
export interface AnalyticsEvidence {
  schema_version: typeof ANALYTICS_SCHEMA; portfolio_id: string; revision_id: string; question: AnalyticsQuestion;
  result: AnalyticsResult; ledger_reference: { portfolio_id: string; revision_id: string; ledger_version: number; workspace_path: string }; limits: JsonObject;
}
export interface AnalyticsReproduction extends JsonObject {
  status: string; detail: string; rerun_manifest_id: string | null; rerun_result_digest: string | null;
}
const string = (v: unknown): v is string => typeof v === 'string';
const optional = (v: unknown) => v === null || string(v);
const integer = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0;
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(string);
const digest = (v: unknown) => string(v) && /^[a-f0-9]{64}$/.test(v);
const decimal = (v: unknown) => string(v) && /^-?\d+(?:\.\d+)?$/.test(v);
const exact = (v: unknown) => v === null || string(v) && /^-?\d+(?:\/[1-9]\d*)?$/.test(v);
function invalid(): never { throw new ApiError('INVALID_RESPONSE', 'Analytical result scope or evidence mismatch'); }
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (isObject(value)) return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
export const sameAnalytics = (left: unknown, right: unknown) => canonical(left) === canonical(right);
function metric(value: unknown, manifestId: string): value is AnalyticsMetric {
  if (!isObject(value) || !string(value.metric_id) || value.manifest_id !== manifestId || !['AVAILABLE', 'LIMITED', 'INSUFFICIENT_DATA'].includes(String(value.state))
    || !optional(value.reason) || !strings(value.details) || !Array.isArray(value.causes) || !value.causes.every(isObject)
    || !(value.window === null || isObject(value.window)) || !exact(value.exact)
    || value.exact_square !== undefined && !exact(value.exact_square)
    || value.sign !== undefined && value.sign !== null && (typeof value.sign !== 'number' || ![-1, 0, 1].includes(value.sign))
    || value.partial !== undefined && typeof value.partial !== 'boolean'
    || value.excluded !== undefined && (!Array.isArray(value.excluded) || !value.excluded.every(isObject))
    || value.excluded_weight !== undefined && !exact(value.excluded_weight)
    || value.excluded_weight_presented !== undefined && value.excluded_weight_presented !== null && !decimal(value.excluded_weight_presented)) return false;
  if (value.partial === true && issuedPartialCounts(value) === null) return false;
  if (value.state === 'INSUFFICIENT_DATA') return value.value === null && value.exact === null && value.exact_square == null && value.sign == null
    && value.excluded_weight == null && value.excluded_weight_presented == null && value.stale_weight == null && value.stale_weight_presented == null
    && (value.breakdown === undefined || Array.isArray(value.breakdown) && value.breakdown.length === 0)
    && (value.intermediates === undefined || Array.isArray(value.intermediates) && value.intermediates.length === 0)
    && value.comparability == null && value.decomposition == null && value.drawdown == null;
  return decimal(value.value) && (value.exact !== null || typeof value.exact_square === 'string' && typeof value.sign === 'number')
    && !(value.exact !== null && value.exact_square != null)
    && !(value.state === 'AVAILABLE' && ['SOURCE_CONFLICT', 'MISSING_PRICE_HISTORY'].includes(String(value.reason)));
}
function limits(value: unknown): value is JsonObject {
  return isObject(value) && value.calculation_days === 3660 && value.output_bytes === 2_000_000 && value.http_bytes === 32_768;
}
function readResult(value: unknown, portfolioId: string, question: AnalyticsQuestion, ledgerVersion: number): AnalyticsResult {
  if (!isObject(value) || value.family !== question.family || !['PERFORMANCE', 'INDEPENDENT', 'BENCHMARK'].includes(String(value.group))
    || (question.family === 'RISK') === (value.group === 'PERFORMANCE') || !digest(value.binding_digest) || !isObject(value.binding)
    || !isObject(value.engine_result) || !digest(value.engine_result.manifest_id) || !digest(value.engine_result.result_digest)
    || value.result_id !== `${value.family}:${value.group}:${value.engine_result.manifest_id}:${value.engine_result.result_digest}`
    || !isObject(value.engine_result.manifest) || !Array.isArray(value.engine_result.metrics)
    || !value.engine_result.metrics.every((row) => metric(row, String((value.engine_result as JsonObject).manifest_id)))
    || !Array.isArray(value.definitions) || !value.definitions.every(isObject)) return invalid();
  const binding = value.binding; const manifest = value.engine_result.manifest;
  if (binding.portfolio_id !== portfolioId || binding.revision_id !== question.revision_id || binding.as_of !== question.as_of || binding.ledger_version !== ledgerVersion
    || binding.family !== question.family || binding.group !== value.group || !sameAnalytics(binding.scope, question.scope)
    || !digest(binding.question_digest) || !(binding.release_id === null || digest(binding.release_id)) || !digest(binding.input_sha256) || !digest(binding.calendar_sha256)
    || !string(binding.fixture_as_of) || !string(binding.reporting_currency) || !string(binding.engine_id)
    || !['benchmark_catalog', 'risk_free_catalog', 'registry'].every((key) => binding[key] === null || isObject(binding[key]) && string(binding[key].id) && digest(binding[key].digest))
    || !Array.isArray(binding.conventions)) return invalid();
  if (question.family !== 'RISK' && (binding.selection_pin !== null || binding.benchmark_catalog !== null || binding.risk_free_catalog !== null)
    || question.family === 'RISK' && value.group === 'INDEPENDENT' && (binding.selection_pin !== null || binding.benchmark_catalog !== null)
    || binding.selection_pin !== null && (!isObject(binding.selection_pin) || binding.selection_pin.portfolio_id !== portfolioId)) return invalid();
  const portfolioManifest = question.family === 'RISK' ? manifest.series_manifest : manifest;
  if (!isObject(portfolioManifest) || portfolioManifest.portfolio_id !== portfolioId || portfolioManifest.ledger_version !== ledgerVersion
    || portfolioManifest.reporting_currency !== binding.reporting_currency || portfolioManifest.as_of !== question.as_of
    || portfolioManifest.scope !== (question.scope.kind === 'PORTFOLIO' ? 'PORTFOLIO' : `ACCOUNT:${question.scope.account_id}`)
    || portfolioManifest.state_kind !== 'ACTUAL' || portfolioManifest.synthetic !== true || portfolioManifest.release_id !== binding.release_id
    || !sameAnalytics(portfolioManifest.conventions, binding.conventions)
    || binding.engine_id !== (question.family === 'RISK' ? manifest.risk_engine_id : portfolioManifest.engine_id)
    || question.family === 'RISK' && (manifest.end !== question.as_of || manifest.frequency !== question.frequency || manifest.state_kind !== 'ACTUAL' || manifest.synthetic !== true)) return invalid();
  if (question.family !== 'RISK') {
    if (!isObject(manifest.window) || manifest.window.rule !== question.window.rule || manifest.window.end !== question.as_of || manifest.window.months !== question.window.months
      || question.window.rule === 'CUSTOM' && manifest.window.start !== question.window.base) return invalid();
  } else {
    const isFallbackWindow = question.view === 'DEFAULT' && manifest.request_rule === 'MAX_AVAILABLE';
    if (!isFallbackWindow && (manifest.request_rule !== question.window.rule || manifest.request_months !== question.window.months || manifest.request_base !== question.window.base)
      || isFallbackWindow && (manifest.request_months !== null || manifest.request_base !== null)) return invalid();
    if (!isObject(binding.registry) || binding.registry.id !== manifest.registry_id || binding.registry.digest !== manifest.registry_digest
      || value.engine_result.metrics.some((row) => !isObject(row) || row.frequency !== manifest.frequency)) return invalid();
    if (manifest.benchmark === null) {
      if (binding.selection_pin !== null || binding.benchmark_catalog !== null) return invalid();
    } else if (!isObject(manifest.benchmark) || !sameAnalytics(manifest.benchmark.pin, binding.selection_pin) || !isObject(binding.benchmark_catalog)
      || binding.benchmark_catalog.id !== manifest.benchmark.catalog_id || binding.benchmark_catalog.digest !== manifest.benchmark.catalog_digest) return invalid();
    if (manifest.risk_free === null) {
      if (binding.risk_free_catalog !== null) return invalid();
    } else if (!isObject(manifest.risk_free) || !isObject(binding.risk_free_catalog)
      || binding.risk_free_catalog.id !== manifest.risk_free.catalog_id || binding.risk_free_catalog.digest !== manifest.risk_free.catalog_digest) return invalid();
  }
  return value as unknown as AnalyticsResult;
}
export function readAnalyticsEvaluation(value: unknown, portfolioId: string, question: AnalyticsQuestion, ledgerVersion: number): AnalyticsEvaluation {
  if (!isObject(value) || value.schema_version !== ANALYTICS_SCHEMA || value.portfolio_id !== portfolioId || value.revision_id !== question.revision_id
    || value.persisted !== false || value.synthetic !== true || !sameAnalytics(value.question, question) || !isObject(value.revision)
    || value.revision.as_of !== question.as_of || value.revision.ledger_version !== ledgerVersion || !integer(value.revision.selection_version)
    || !string(value.revision.reporting_currency) || !limits(value.limits) || !strings(value.limitations) || !Array.isArray(value.results) || !Array.isArray(value.views)) return invalid();
  const results = value.results.map((result) => readResult(result, portfolioId, question, ledgerVersion));
  if (results.length === 0 || value.views.length === 0 || new Set(results.map((result) => result.result_id)).size !== results.length) return invalid();
  const shownAddresses = new Set<string>(); const defaultKeys = new Set<string>();
  for (const view of value.views) {
    if (!isObject(view) || !string(view.metric_id) || !integer(view.metric_index) || typeof view.fallback !== 'boolean'
      || !string(view.shown_result_id) || !optional(view.refused_result_id) || !(view.refused_metric_index === null || integer(view.refused_metric_index))
      || !(view.composition === null || isObject(view.composition))) return invalid();
    const shown = results.find((result) => result.result_id === view.shown_result_id); const shownMetric = shown?.engine_result.metrics[view.metric_index];
    if (!shown || !shownMetric || shownMetric.metric_id !== view.metric_id || shown.binding.reporting_currency !== value.revision.reporting_currency) return invalid();
    const address = `${shown.result_id}:${view.metric_index}`;
    if (shownAddresses.has(address)) return invalid(); shownAddresses.add(address);
    const defaultKey = `${shown.group}:${view.metric_id}`;
    if (question.view === 'DEFAULT' && defaultKeys.has(defaultKey)) return invalid(); defaultKeys.add(defaultKey);
    if (view.fallback) {
      const refused = results.find((result) => result.result_id === view.refused_result_id); const refusedMetric = refused?.engine_result.metrics[Number(view.refused_metric_index)];
      if (question.view !== 'DEFAULT' || !refused || refused.group !== shown.group || !refusedMetric || refusedMetric.metric_id !== view.metric_id || refusedMetric.state !== 'INSUFFICIENT_DATA'
        || refused.engine_result.manifest.request_rule !== question.window.rule || refused.engine_result.manifest.request_months !== question.window.months
        || shown.engine_result.manifest.request_rule !== 'MAX_AVAILABLE'
        || !isObject(view.composition) || view.composition.fallback !== true || view.composition.metric_id !== view.metric_id
        || !sameAnalytics(view.composition.default_request, { rule: question.window.rule, months: question.window.months })
        || view.composition.x_manifest_id !== refused.engine_result.manifest_id || view.composition.x_result_digest !== refused.engine_result.result_digest
        || view.composition.y_manifest_id !== shown.engine_result.manifest_id || view.composition.y_result_digest !== shown.engine_result.result_digest) return invalid();
    } else {
      if (view.refused_result_id !== null || view.refused_metric_index !== null) return invalid();
      if (question.view === 'DEFAULT') {
        if (shown.engine_result.manifest.request_rule !== question.window.rule || shown.engine_result.manifest.request_months !== question.window.months
          || !isObject(view.composition) || view.composition.fallback !== false || view.composition.metric_id !== view.metric_id
          || !sameAnalytics(view.composition.default_request, { rule: question.window.rule, months: question.window.months })
          || view.composition.x_manifest_id !== shown.engine_result.manifest_id || view.composition.x_result_digest !== shown.engine_result.result_digest
          || view.composition.y_manifest_id !== null || view.composition.y_result_digest !== null) return invalid();
      } else if (view.composition !== null) return invalid();
    }
  }
  if (question.view === 'REQUESTED' && results.some((result) => result.engine_result.metrics.some((_, index) => !shownAddresses.has(`${result.result_id}:${index}`)))) return invalid();
  if (question.view === 'DEFAULT' && results.some((result) => result.engine_result.metrics.some((row) => !defaultKeys.has(`${result.group}:${row.metric_id}`)))) return invalid();
  return { ...value, results } as unknown as AnalyticsEvaluation;
}
export function analyticalProof(question: AnalyticsQuestion, result: AnalyticsResult) {
  return { question, result_id: result.result_id, expected_binding_digest: result.binding_digest,
    expected_manifest_id: result.engine_result.manifest_id, expected_result_digest: result.engine_result.result_digest };
}
export function readAnalyticsEvidence(value: unknown, portfolioId: string, question: AnalyticsQuestion, result: AnalyticsResult): AnalyticsEvidence {
  if (!isObject(value) || value.schema_version !== ANALYTICS_SCHEMA || value.portfolio_id !== portfolioId || value.revision_id !== question.revision_id
    || !sameAnalytics(value.question, question) || !sameAnalytics(value.result, result) || !limits(value.limits) || !isObject(value.ledger_reference)
    || value.ledger_reference.portfolio_id !== portfolioId || value.ledger_reference.revision_id !== question.revision_id || value.ledger_reference.ledger_version !== result.binding.ledger_version
    || value.ledger_reference.workspace_path !== `/api/v1/portfolios/${portfolioId}/workspace?revision_id=${question.revision_id}`) return invalid();
  return value as unknown as AnalyticsEvidence;
}
export function readAnalyticsReproduction(value: unknown, portfolioId: string, question: AnalyticsQuestion, result: AnalyticsResult): AnalyticsReproduction {
  if (!isObject(value) || value.schema_version !== ANALYTICS_SCHEMA || value.portfolio_id !== portfolioId || value.revision_id !== question.revision_id
    || value.family !== result.family || value.group !== result.group || value.result_id !== result.result_id || value.binding_digest !== result.binding_digest
    || value.expected_manifest_id !== result.engine_result.manifest_id || value.expected_result_digest !== result.engine_result.result_digest
    || !string(value.status) || !string(value.detail) || !optional(value.rerun_manifest_id) || !optional(value.rerun_result_digest) || !limits(value.limits)
    || value.status === 'REPRODUCED' && (value.rerun_manifest_id !== result.engine_result.manifest_id || value.rerun_result_digest !== result.engine_result.result_digest)) return invalid();
  return value as AnalyticsReproduction;
}
