/** The browser transports financial strings; it never calculates a financial result. */
import { issuedPartialCounts } from './partial-value';
export const SCHEMA = 'finweb.cp7/1';
export type DataState = 'AVAILABLE' | 'LIMITED' | 'INSUFFICIENT_DATA';
export type JsonObject = { [key: string]: unknown };
export type Metric = JsonObject & {
  metric_id: string;
  value: string | null;
  state: DataState;
  reason: string | null;
  subject: unknown[];
  details: string[];
  exact?: string | null;
  unit?: string;
  currency?: string | null;
  method_id?: string;
  method_key?: string;
  manifest_id?: string;
};
export type Packet = JsonObject & {
  insight_id: string;
  insight_type: string;
  severity: string;
  judgment_class: string;
  claim: { text: string; caveats: string[]; parameters: JsonObject };
  confidence_availability_state: DataState;
  limitations: string[];
  metrics_used: (JsonObject & { reference: { metric_id: string; subject: string[] }; metric: Metric })[];
  synthetic: true;
};
export interface PacketPolicy {
  policy_id: string; version: string; evidence: string; portfolio_id: string; scope_kind: string; account_id: string | null;
  source_kind: string; metric_id: string; semantic_key: string; subject: string[]; direction: 'MAXIMUM' | 'MINIMUM';
  limit: string; effective_from: string; effective_until: string | null; origin: 'USER_CONFIRMED';
}
export interface Snapshot {
  schema_version: typeof SCHEMA;
  portfolio_id: string;
  name: string;
  mode: 'LOCAL_SYNTHETIC_GUEST' | 'LOCAL_SYNTHETIC_ACCOUNT';
  synthetic: true;
  persisted: boolean;
  reporting_currency: 'USD';
  as_of: string;
  limitations: string[];
  inputs: { positions: { symbol: string; quantity: string }[]; cash: string };
  valuation: { manifest_id: string; result_digest: string; metrics: Metric[] };
  diversification: { manifest_id: string; result_digest: string; metrics: Metric[] };
  insights: { manifest_id: string; result_digest: string; packets: Packet[]; diagnostics: JsonObject[] };
  provenance: JsonObject;
}
export interface CreatePortfolio {
  name: string;
  reporting_currency: 'USD';
  positions: { symbol: string; quantity: string }[];
  cash: string;
  synthetic_acknowledged: true;
}
export interface PacketResponse {
  schema_version: typeof SCHEMA;
  portfolio_id: string;
  synthetic: true;
  packet: Packet;
  result_digest: string;
}
export interface Reproduction {
  schema_version: typeof SCHEMA;
  portfolio_id: string;
  insight_id: string;
  status: string;
  detail: string;
  expected_result_digest: string;
  actual_result_digest: string | null;
  synthetic: true;
}
export class ApiError extends Error {
  constructor(public code: string, public detail: string, public status = 0) { super(code); }
}
export function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((v) => typeof v === 'string');
}
function validState(value: unknown): value is DataState {
  return value === 'AVAILABLE' || value === 'LIMITED' || value === 'INSUFFICIENT_DATA';
}
function validMetric(value: unknown): value is Metric {
  if (!isObject(value) || typeof value.metric_id !== 'string' || !validState(value.state)
    || !Array.isArray(value.subject) || !strings(value.details)
    || !(value.reason === null || typeof value.reason === 'string')) return false;
  if (value.state === 'AVAILABLE' && (value.reason === 'SOURCE_CONFLICT' || value.reason === 'MISSING_PRICE_HISTORY')) return false;
  if (value.partial === true && issuedPartialCounts(value) === null) return false;
  // Refuse malformed values, including a number leaked alongside an insufficient state.
  return value.state === 'INSUFFICIENT_DATA'
    ? value.value === null && (value.exact === null || value.exact === undefined)
      && (value.exact_square === null || value.exact_square === undefined)
      && (value.sign === null || value.sign === undefined)
      && (value.radical_terms === undefined || (Array.isArray(value.radical_terms) && value.radical_terms.length === 0))
    : typeof value.value === 'string' && /^-?\d+(?:\.\d+)?$/.test(value.value);
}
export function packetPolicy(value: unknown): PacketPolicy | null {
  if (!isObject(value) || value.insight_type !== 'user_limit' || value.judgment_class !== 'PREFERENCE_DEPENDENT'
    || !isObject(value.thresholds_limits) || !isObject(value.thresholds_limits.policy) || !isObject(value.comparison_basis)) return null;
  const policy = value.thresholds_limits.policy;
  if (!['policy_id', 'version', 'evidence', 'portfolio_id', 'scope_kind', 'source_kind', 'metric_id', 'semantic_key', 'effective_from'].every((key) => typeof policy[key] === 'string')
    || typeof policy.limit !== 'string' || !/^-?\d+(?:\.\d+|\/[1-9]\d*)?$/.test(policy.limit)
    || !strings(policy.subject) || !['MAXIMUM', 'MINIMUM'].includes(String(policy.direction)) || policy.origin !== 'USER_CONFIRMED'
    || !['CP4', 'CP5'].includes(String(policy.source_kind)) || !['PORTFOLIO', 'ACCOUNT'].includes(String(policy.scope_kind))
    || policy.scope_kind === 'PORTFOLIO' && policy.account_id !== null || policy.scope_kind === 'ACCOUNT' && typeof policy.account_id !== 'string'
    || !(policy.account_id === null || typeof policy.account_id === 'string') || !(policy.effective_until === null || typeof policy.effective_until === 'string')
    || value.comparison_basis.kind !== 'USER_POLICY' || value.comparison_basis.policy_id !== policy.policy_id
    || value.comparison_basis.version !== policy.version || value.comparison_basis.policy_digest !== value.thresholds_limits.policy_digest
    || typeof value.thresholds_limits.policy_digest !== 'string' || value.thresholds_limits.equality_is_breach !== false
    || value.thresholds_limits.decision_basis !== 'EXACT_UPSTREAM_WITNESS' || value.portfolio_id !== policy.portfolio_id) return null;
  return policy as unknown as PacketPolicy;
}
function validPacket(value: unknown): value is Packet {
  return isObject(value) && typeof value.insight_id === 'string'
    && typeof value.insight_type === 'string' && typeof value.severity === 'string'
    && typeof value.judgment_class === 'string' && value.synthetic === true
    && validState(value.confidence_availability_state) && isObject(value.claim)
    && typeof value.claim.text === 'string' && strings(value.claim.caveats)
    && strings(value.limitations) && Array.isArray(value.metrics_used)
    && value.metrics_used.every((m) => isObject(m) && validMetric(m.metric)
      && isObject(m.reference) && typeof m.reference.metric_id === 'string' && strings(m.reference.subject))
    && (value.insight_type !== 'user_limit' || packetPolicy(value) !== null);
}
function readScopedSnapshot(value: unknown, saved: boolean, preview = false): Snapshot {
  const validGroup = (group: unknown) => isObject(group) && typeof group.manifest_id === 'string'
    && typeof group.result_digest === 'string' && Array.isArray(group.metrics) && group.metrics.every(validMetric);
  if (!isObject(value) || value.schema_version !== SCHEMA || value.mode !== (saved ? 'LOCAL_SYNTHETIC_ACCOUNT' : 'LOCAL_SYNTHETIC_GUEST')
    || value.synthetic !== true || value.persisted !== (saved && !preview) || value.reporting_currency !== 'USD'
    || typeof value.portfolio_id !== 'string' || typeof value.name !== 'string'
    || typeof value.as_of !== 'string' || !strings(value.limitations) || !isObject(value.provenance)
    || !isObject(value.inputs) || typeof value.inputs.cash !== 'string' || !Array.isArray(value.inputs.positions)
    || !value.inputs.positions.every((p) => isObject(p) && typeof p.symbol === 'string' && typeof p.quantity === 'string')
    || !validGroup(value.valuation) || !validGroup(value.diversification) || !isObject(value.insights)
    || typeof value.insights.manifest_id !== 'string' || typeof value.insights.result_digest !== 'string'
    || !Array.isArray(value.insights.packets) || !value.insights.packets.every((packet) => validPacket(packet)
      && (packet.portfolio_id === undefined || packet.portfolio_id === value.portfolio_id))
    || !Array.isArray(value.insights.diagnostics)) throw new ApiError('INVALID_RESPONSE', 'Snapshot contract mismatch');
  return value as unknown as Snapshot;
}
export function readSnapshot(value: unknown): Snapshot { return readScopedSnapshot(value, false); }
export function readSavedSnapshot(value: unknown): Snapshot { return readScopedSnapshot(value, true); }
/** A rollback-only proposal is accepted only inside the explicit preview transport. */
export function readAccountPreviewSnapshot(value: unknown): Snapshot {
  if (!isObject(value) || !strings(value.limitations) || !value.limitations.some((item) => item.startsWith('PREVIEW_NOT_SAVED:'))
    || value.limitations.some((item) => item.startsWith('SAVED_SYNTHETIC_SANDBOX:'))) throw new ApiError('INVALID_RESPONSE', 'Unlabelled preview');
  return readScopedSnapshot(value, true, true);
}
export function readPacketResponse(value: unknown, portfolioId: string, insightId: string): PacketResponse {
  if (!isObject(value) || value.schema_version !== SCHEMA || value.portfolio_id !== portfolioId
    || value.synthetic !== true || !validPacket(value.packet) || value.packet.insight_id !== insightId
    || value.packet.portfolio_id !== undefined && value.packet.portfolio_id !== portfolioId
    || typeof value.result_digest !== 'string') throw new ApiError('INVALID_RESPONSE', 'Invalid packet response');
  return value as unknown as PacketResponse;
}
export function readReproduction(value: unknown, portfolioId: string, insightId: string, expected: string): Reproduction {
  if (!isObject(value) || value.schema_version !== SCHEMA || value.portfolio_id !== portfolioId
    || value.insight_id !== insightId || typeof value.status !== 'string' || typeof value.detail !== 'string'
    || value.expected_result_digest !== expected || !(typeof value.actual_result_digest === 'string' || value.actual_result_digest === null)
    || value.synthetic !== true || (value.status === 'REPRODUCED' && value.actual_result_digest !== expected)) {
    throw new ApiError('INVALID_RESPONSE', 'Invalid reproduction response');
  }
  return value as unknown as Reproduction;
}
/** Decimal syntax validation only. No conversions, sums, weights or limit decisions. */
export function isDecimalInput(value: string): boolean {
  return /^(?:0|[1-9]\d*)(?:\.\d{1,6})?$/.test(value);
}
export function isZeroInput(value: string): boolean { return /^0(?:\.0+)?$/.test(value); }

export class GuestApi {
  private token: string | null = null;
  private revision = 0;
  private pending = new Set<AbortController>();
  reset(): void {
    this.token = null; this.revision += 1;
    this.pending.forEach((controller) => controller.abort()); this.pending.clear();
  }

  private async request(path: string, body?: unknown): Promise<unknown> {
    const revision = this.revision;
    const controller = new AbortController(); this.pending.add(controller);
    let response: Response;
    try {
      response = await fetch(`/api/v1${path}`, {
        method: body === undefined ? 'GET' : 'POST',
        headers: {
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
          ...(this.token ? { 'X-Finweb-Session': this.token } : {}),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        cache: 'no-store',
        credentials: 'omit',
        signal: controller.signal,
      });
    } catch {
      this.pending.delete(controller);
      if (revision !== this.revision || controller.signal.aborted) throw new ApiError('REQUEST_CANCELLED', 'Workspace changed');
      throw new ApiError('NETWORK_ERROR', 'Local API unavailable');
    }
    let data: unknown;
    try { data = await response.json(); }
    catch { throw new ApiError('INVALID_RESPONSE', 'Invalid JSON', response.status); }
    finally { this.pending.delete(controller); }
    if (revision !== this.revision || controller.signal.aborted) throw new ApiError('REQUEST_CANCELLED', 'Workspace changed');
    if (!response.ok) {
      if (response.status === 401) this.reset();
      const error = isObject(data) && isObject(data.error) ? data.error : null;
      throw new ApiError(typeof error?.code === 'string' ? error.code : 'API_ERROR',
        typeof error?.detail === 'string' ? error.detail : '', response.status);
    }
    return data;
  }

  async capabilities(): Promise<JsonObject> {
    const value = await this.request('/capabilities');
    if (!isObject(value) || value.schema_version !== SCHEMA) throw new ApiError('INVALID_RESPONSE', 'Invalid capabilities');
    return value;
  }

  async create(input: CreatePortfolio): Promise<Snapshot> {
    const revision = this.revision;
    if (!this.token) {
      const session = await this.request('/guest-sessions', { mode: 'LOCAL_SYNTHETIC_GUEST' });
      if (revision !== this.revision) throw new ApiError('REQUEST_CANCELLED', 'Workspace changed');
      if (!isObject(session) || session.schema_version !== SCHEMA || typeof session.session_token !== 'string') {
        throw new ApiError('INVALID_RESPONSE', 'Invalid session');
      }
      this.token = session.session_token;
    }
    return readSnapshot(await this.request('/guest-portfolios', input));
  }
  async snapshot(id: string): Promise<Snapshot> {
    const snapshot = readSnapshot(await this.request(`/guest-portfolios/${encodeURIComponent(id)}`));
    if (snapshot.portfolio_id !== id) throw new ApiError('INVALID_RESPONSE', 'Guest portfolio identity mismatch');
    return snapshot;
  }
  async packet(portfolioId: string, insightId: string): Promise<PacketResponse> {
    const value = await this.request(`/guest-portfolios/${encodeURIComponent(portfolioId)}/packets/${encodeURIComponent(insightId)}`);
    return readPacketResponse(value, portfolioId, insightId);
  }
  async reproduce(portfolioId: string, insightId: string, expected: string): Promise<Reproduction> {
    const value = await this.request(`/guest-portfolios/${encodeURIComponent(portfolioId)}/packets/${encodeURIComponent(insightId)}/reproduce`,
      { expected_result_digest: expected });
    return readReproduction(value, portfolioId, insightId, expected);
  }
}
