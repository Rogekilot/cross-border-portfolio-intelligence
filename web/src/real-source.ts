import { ApiError, isObject } from './transport';

export const REAL_SOURCE_SCHEMA = 'finweb.cp7.real_source/1';
export const REAL_SOURCE_BLOCKERS = ['NO_APPROVED_REAL_SOURCE_CONTEXT', 'REAL_PORTFOLIO_STORAGE_NOT_IMPLEMENTED', 'REAL_ANALYTICS_NOT_IMPLEMENTED'] as const;
const capabilities = { source_metadata: true, payload_verification: false, source_qualification: false, create: false, saved: false, workspace: false, analytics: false, imports: false, exports: false, evidence: false } as const;
export interface ConfiguredRealSource {
  context_id: string; configuration_digest: string; declared_release_id: string; declared_source_ids: string[];
  status: 'CONFIGURED_NOT_VERIFIED'; readiness_stage: 'METADATA_ONLY'; metadata_integrity: 'EXPECTED_METADATA_BYTES_MATCHED';
  payload_integrity: 'NOT_VERIFIED'; financially_qualified: false;
}
export interface RealSourceReadiness {
  schema_version: typeof REAL_SOURCE_SCHEMA; milestone: 'E1_GATE_ONLY'; mode: 'LOCAL_REAL_SOURCE_TEST_ACCOUNT'; state: 'BLOCKED'; readiness_stage: 'METADATA_ONLY';
  provenance: { ledger_origin: 'PROJECT_CONSTRUCTED_NONPERSONAL_UAT_REQUESTED'; market_origin: 'REAL_SOURCE_REQUESTED_NOT_QUALIFIED'; personal_holdings: false };
  capabilities: typeof capabilities; approved_context_count: 0; contexts: ConfiguredRealSource[]; blockers: typeof REAL_SOURCE_BLOCKERS;
  limits: { http_bytes: 32768; output_bytes: 65536 }; scope: { markets: ['US']; reporting_currencies: ['USD'] };
  support: { data_action: 'EXISTING_REGISTERED_PROJECT_METADATA_ONLY'; download_or_admission: false; real_uat_verified: false; hg4_approved: false };
}
const exact = (value: unknown, keys: readonly string[]): value is Record<string, unknown> => isObject(value) && Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));
const same = (value: unknown, expected: unknown): boolean => JSON.stringify(value) === JSON.stringify(expected);
const hash = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
function fixedCapabilities(value: unknown): boolean {
  return exact(value, Object.keys(capabilities)) && Object.entries(capabilities).every(([key, expected]) => value[key] === expected);
}
function context(value: unknown): value is ConfiguredRealSource {
  if (!exact(value, ['context_id', 'configuration_digest', 'declared_release_id', 'declared_source_ids', 'status', 'readiness_stage', 'metadata_integrity', 'payload_integrity', 'financially_qualified'])
    || !hash(value.context_id) || !hash(value.configuration_digest) || !hash(value.declared_release_id)
    || value.status !== 'CONFIGURED_NOT_VERIFIED' || value.readiness_stage !== 'METADATA_ONLY' || value.metadata_integrity !== 'EXPECTED_METADATA_BYTES_MATCHED'
    || value.payload_integrity !== 'NOT_VERIFIED' || value.financially_qualified !== false || !Array.isArray(value.declared_source_ids)
    || value.declared_source_ids.length < 1 || value.declared_source_ids.length > 6
    || !value.declared_source_ids.every((id): id is string => typeof id === 'string' && /^[a-z0-9][a-z0-9_.:-]{0,63}$/.test(id))) return false;
  return value.declared_source_ids.every((id, index, ids) => index === 0 || ids[index - 1] < id);
}
/** E1 is a blocked metadata envelope, never a financial or source-admission reader. */
export function readRealSourceReadiness(value: unknown): RealSourceReadiness {
  const invalid = (): never => { throw new ApiError('INVALID_RESPONSE', 'Real-source readiness contract mismatch'); };
  if (!exact(value, ['schema_version', 'milestone', 'mode', 'state', 'readiness_stage', 'provenance', 'capabilities', 'approved_context_count', 'contexts', 'blockers', 'limits', 'scope', 'support'])
    || value.schema_version !== REAL_SOURCE_SCHEMA || value.milestone !== 'E1_GATE_ONLY' || value.mode !== 'LOCAL_REAL_SOURCE_TEST_ACCOUNT'
    || value.state !== 'BLOCKED' || value.readiness_stage !== 'METADATA_ONLY' || value.approved_context_count !== 0
    || !exact(value.provenance, ['ledger_origin', 'market_origin', 'personal_holdings'])
    || value.provenance.ledger_origin !== 'PROJECT_CONSTRUCTED_NONPERSONAL_UAT_REQUESTED' || value.provenance.market_origin !== 'REAL_SOURCE_REQUESTED_NOT_QUALIFIED' || value.provenance.personal_holdings !== false
    || !fixedCapabilities(value.capabilities)
    || !Array.isArray(value.contexts) || value.contexts.length > 16 || !value.contexts.every(context)
    || !value.contexts.every((item, index, rows) => index === 0 || rows[index - 1].context_id < item.context_id)
    || !same(value.blockers, REAL_SOURCE_BLOCKERS) || !exact(value.limits, ['http_bytes', 'output_bytes']) || value.limits.http_bytes !== 32768 || value.limits.output_bytes !== 65536
    || !exact(value.scope, ['markets', 'reporting_currencies']) || !same(value.scope.markets, ['US']) || !same(value.scope.reporting_currencies, ['USD'])
    || !exact(value.support, ['data_action', 'download_or_admission', 'real_uat_verified', 'hg4_approved']) || value.support.data_action !== 'EXISTING_REGISTERED_PROJECT_METADATA_ONLY'
    || value.support.download_or_admission !== false || value.support.real_uat_verified !== false || value.support.hg4_approved !== false) return invalid();
  if (new TextEncoder().encode(JSON.stringify(value)).length > 65536) return invalid();
  return value as unknown as RealSourceReadiness;
}

export type RealReadinessState = { kind: 'loading' } | { kind: 'blocked'; value: RealSourceReadiness } | { kind: 'error'; error: unknown };
/** One view's pending read: clearing or a newer retry prevents old data/errors returning. */
export class RealReadinessLoad {
  private generation = 0;
  invalidate(): void { this.generation += 1; }
  async run(read: () => Promise<RealSourceReadiness>, publish: (state: RealReadinessState) => void): Promise<void> {
    const generation = ++this.generation; publish({ kind: 'loading' });
    try { const value = await read(); if (generation === this.generation) publish({ kind: 'blocked', value }); }
    catch (error) { if (generation === this.generation && !(error instanceof ApiError && error.code === 'REQUEST_CANCELLED')) publish({ kind: 'error', error }); }
  }
}
