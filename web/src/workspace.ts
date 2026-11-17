import { ApiError, isObject, readAccountPreviewSnapshot, readSavedSnapshot, SCHEMA, type JsonObject, type Snapshot } from './transport';

export type FieldRule = 'REQUIRED' | 'OPTIONAL' | 'FORBIDDEN';
export interface LedgerInput {
  account_id: string; event_type: string; event_date: string; currency: string;
  listing_id?: string; quantity?: string; amount?: string; cost_basis?: string;
  bought_amount?: { amount: string; currency: string }; split_ratio?: { new_units: string; old_units: string };
  counterparty_account_id?: string; settlement_date?: string; ex_date?: string; acquired_on?: string;
}
export interface LedgerRow extends LedgerInput {
  event_id: string; ledger_seq: number; reversed_by: string | null; reverses_event_id: string | null;
  corrects_event_id: string | null; source_reference: string | null;
}
export interface StatedValue { value: string | null; state: string; reason: string | null; detail: string[] }
export interface CurrentAccount {
  account_id: string; status: string; snapshot_date: string | null;
  positions: { listing_id: string; quantity: StatedValue; cost_basis: (StatedValue & { currency: string | null })[] }[];
  cash: { currency: string; amount: string }[]; unrepresentable_cash: string[];
}
export interface PolicyTarget {
  source_kind: string; scope_kind: string; account_id: string | null; metric_id: string;
  subject: string[]; semantic_key: string; unit: string | null;
}
export interface PolicyInput {
  policy_id: string; source_kind: string; scope_kind: string; account_id?: string | null; metric_id: string;
  subject: string[]; semantic_key: string; direction: 'MAXIMUM' | 'MINIMUM'; limit: string;
  effective_from: string; effective_until?: string | null; evidence: string;
}
export interface SavedPolicy extends PolicyInput { version: string; origin: 'USER_CONFIRMED'; portfolio_id: string }
export interface Workspace {
  schema_version: typeof SCHEMA; portfolio_id: string; current_revision_id: string; revision_id: string; as_of: string;
  history: { revision_id: string; parent_revision_id: string | null; created_at: string; operation: string }[];
  accounts: { account_id: string; name: string }[];
  listings: { symbol: string; listing_id: string; currency: string }[];
  ledger: { version: number; events: LedgerRow[]; field_rules: Record<string, Record<string, FieldRule>>;
    current_state: { convention_set: string; as_of: string; ledger_version: number; accounts: CurrentAccount[] } };
  policies: { state: 'NOT_STATED' | 'NONE' | 'ACTIVE'; items: SavedPolicy[]; targets: PolicyTarget[] };
  benchmark: { state: 'NOT_STATED' | 'NONE' | 'SELECTED'; pin: JsonObject; catalog_id: string;
    entries: (JsonObject & { benchmark_id: string; name: string })[]; selection_available: boolean };
}
export interface LedgerCommand {
  operation_id: string; expected_revision_id: string; operation: 'APPEND' | 'CORRECT' | 'REVERSE' | 'ADD_ACCOUNT';
  as_of: string; events: LedgerInput[]; target_event_ids: string[]; account_name?: string;
}
export interface PreferencesCommand {
  operation_id: string; expected_revision_id: string; as_of: string; policies: PolicyInput[]; policies_confirmed: true;
  benchmark: { action: 'KEEP' | 'CLEAR' | 'SELECT'; benchmark_id?: string; selected_on?: string };
}
export interface WorkspaceResult { workspace: Workspace; snapshot: Snapshot; preview?: true }

const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every((s) => typeof s === 'string');
const text = (value: unknown): value is string => typeof value === 'string';
const optionalText = (value: unknown) => value === undefined || value === null || text(value);
const sequence = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0;
const decimal = (value: unknown) => text(value) && /^-?\d+(?:\.\d+)?$/.test(value);
const rational = (value: unknown) => text(value) && /^-?\d+(?:\.\d+|\/[1-9]\d*)?$/.test(value);
const stated = (value: unknown) => isObject(value) && ['AVAILABLE', 'LIMITED', 'INSUFFICIENT_DATA'].includes(String(value.state)) && (value.reason === null || text(value.reason)) && strings(value.detail)
  && (value.state === 'INSUFFICIENT_DATA' ? value.value === null : decimal(value.value));
function validEvent(value: unknown): boolean {
  if (!isObject(value) || !['event_id', 'account_id', 'event_type', 'event_date', 'currency'].every((key) => text(value[key]))
    || !sequence(value.ledger_seq) || !['listing_id', 'reversed_by', 'reverses_event_id', 'corrects_event_id', 'source_reference',
      'counterparty_account_id', 'settlement_date', 'ex_date', 'acquired_on'].every((key) => optionalText(value[key]))) return false;
  if (!['quantity', 'amount', 'cost_basis'].every((key) => value[key] === null || value[key] === undefined || decimal(value[key]))) return false;
  if (value.bought_amount !== undefined && value.bought_amount !== null && (!isObject(value.bought_amount)
    || !decimal(value.bought_amount.amount) || !text(value.bought_amount.currency))) return false;
  return value.split_ratio === undefined || value.split_ratio === null || isObject(value.split_ratio)
    && decimal(value.split_ratio.new_units) && decimal(value.split_ratio.old_units);
}
export function readWorkspace(value: unknown, portfolioId: string, revisionId?: string): Workspace {
  const invalid = () => { throw new ApiError('INVALID_RESPONSE', 'Saved workspace contract mismatch'); };
  if (!isObject(value) || value.schema_version !== SCHEMA || value.portfolio_id !== portfolioId
    || !text(value.revision_id) || !text(value.current_revision_id) || revisionId !== undefined && value.revision_id !== revisionId
    || !text(value.as_of) || !Array.isArray(value.history) || !value.history.every((r) => isObject(r) && text(r.revision_id)
      && optionalText(r.parent_revision_id) && text(r.created_at) && text(r.operation))
    || !value.history.some((r) => isObject(r) && r.revision_id === value.revision_id)
    || !value.history.some((r) => isObject(r) && r.revision_id === value.current_revision_id)
    || !Array.isArray(value.accounts) || !value.accounts.every((a) => isObject(a) && text(a.account_id) && text(a.name))
    || !Array.isArray(value.listings) || !value.listings.every((l) => isObject(l) && text(l.listing_id) && text(l.symbol) && text(l.currency))
    || !isObject(value.ledger) || !sequence(value.ledger.version) || !Array.isArray(value.ledger.events)
    || !value.ledger.events.every(validEvent) || !isObject(value.ledger.field_rules)
    || !Object.values(value.ledger.field_rules).every((rules) => isObject(rules)
      && Object.values(rules).every((rule) => ['REQUIRED', 'OPTIONAL', 'FORBIDDEN'].includes(String(rule))))) return invalid();
  const current = value.ledger.current_state;
  if (!isObject(current) || !text(current.convention_set) || !text(current.as_of) || !sequence(current.ledger_version)
    || current.as_of !== value.as_of || current.ledger_version !== value.ledger.version
    || !Array.isArray(current.accounts) || !current.accounts.every((a) => isObject(a) && text(a.account_id) && ['RECONSTRUCTED', 'NOT_RECONSTRUCTABLE'].includes(String(a.status))
      && optionalText(a.snapshot_date) && Array.isArray(a.positions) && a.positions.every((p) => isObject(p)
        && text(p.listing_id) && stated(p.quantity) && Array.isArray(p.cost_basis)
        && p.cost_basis.every((basis) => stated(basis) && isObject(basis) && optionalText(basis.currency)))
      && Array.isArray(a.cash) && a.cash.every((cash) => isObject(cash) && text(cash.currency) && decimal(cash.amount))
      && strings(a.unrepresentable_cash))) return invalid();
  const policy = value.policies; const benchmark = value.benchmark;
  if (!isObject(policy) || !['NOT_STATED', 'NONE', 'ACTIVE'].includes(String(policy.state)) || !Array.isArray(policy.items)
    || !policy.items.every((p) => isObject(p) && ['policy_id', 'version', 'evidence', 'portfolio_id', 'scope_kind', 'source_kind',
      'metric_id', 'semantic_key', 'effective_from'].every((key) => text(p[key])) && p.portfolio_id === portfolioId
      && p.origin === 'USER_CONFIRMED' && ['MAXIMUM', 'MINIMUM'].includes(String(p.direction)) && rational(p.limit)
      && strings(p.subject) && optionalText(p.account_id) && optionalText(p.effective_until))
    || !Array.isArray(policy.targets) || !policy.targets.every((p) => isObject(p) && ['metric_id', 'semantic_key', 'source_kind',
      'scope_kind'].every((key) => text(p[key])) && optionalText(p.unit) && strings(p.subject) && optionalText(p.account_id))
    || !isObject(benchmark) || !['NOT_STATED', 'NONE', 'SELECTED'].includes(String(benchmark.state))
    || !isObject(benchmark.pin) || !text(benchmark.catalog_id) || typeof benchmark.selection_available !== 'boolean'
    || !Array.isArray(benchmark.entries) || !benchmark.entries.every((e) => isObject(e) && text(e.benchmark_id) && text(e.name))
    || benchmark.selection_available && benchmark.entries.length === 0) return invalid();
  const accountIds = new Set((value.accounts as { account_id: string }[]).map((account) => account.account_id));
  const scopeMatches = (policy: JsonObject) => policy.scope_kind === 'PORTFOLIO' ? policy.account_id === null || policy.account_id === undefined
    : policy.scope_kind === 'ACCOUNT' && text(policy.account_id) && accountIds.has(policy.account_id);
  if ((policy.state === 'ACTIVE') !== (policy.items.length > 0) || !policy.items.every((item) => isObject(item) && scopeMatches(item))
    || !policy.targets.every((target) => isObject(target) && scopeMatches(target))
    || !(value.ledger.events as LedgerRow[]).every((event) => accountIds.has(event.account_id)
      && (event.counterparty_account_id == null || accountIds.has(event.counterparty_account_id)))
    || !(current.accounts as CurrentAccount[]).every((account) => accountIds.has(account.account_id))
    || benchmark.pin.schema !== 'finweb.benchmark_selection_pin/1' || benchmark.pin.portfolio_id !== portfolioId
    || !sequence(benchmark.pin.version) || benchmark.pin.state !== ({ NOT_STATED: 'NONE', NONE: 'CLEARED', SELECTED: 'IN_FORCE' } as Record<string, string>)[String(benchmark.state)]) return invalid();
  if (benchmark.state === 'SELECTED' && (!text(benchmark.pin.benchmark_id) || !text(benchmark.pin.selection_id)
    || !sequence(benchmark.pin.selection_seq) || !text(benchmark.pin.catalog_version))) return invalid();
  return value as unknown as Workspace;
}
export function readWorkspaceResult(value: unknown, portfolioId: string, preview = false): WorkspaceResult {
  if (!isObject(value) || (preview ? value.preview !== true : value.preview === true)) {
    throw new ApiError('INVALID_RESPONSE', 'Mutation preview/commit mismatch');
  }
  const workspace = readWorkspace(value.workspace, portfolioId); const snapshot = preview ? readAccountPreviewSnapshot(value.snapshot) : readSavedSnapshot(value.snapshot);
  if (snapshot.portfolio_id !== portfolioId || snapshot.as_of !== workspace.as_of) throw new ApiError('INVALID_RESPONSE', 'Mutation identity mismatch');
  return { workspace, snapshot, ...(preview ? { preview: true as const } : {}) };
}
export function revisionQuery(revisionId?: string): string {
  return revisionId === undefined ? '' : `?revision_id=${encodeURIComponent(revisionId)}`;
}

/** A same-account read must not replace a later confirmed immutable revision. */
export class WorkspaceReadEpoch {
  private epoch = 0;
  begin(): number { this.epoch += 1; return this.epoch; }
  invalidate(): void { this.epoch += 1; }
  isCurrent(readEpoch: number): boolean { return this.epoch === readEpoch; }
}

/** Shape validation only; the server owns amount semantics, replay and policy decisions. */
export function validExactLimit(value: string): boolean { return /^-?(?:[0-9]{1,30}\/[1-9][0-9]{0,29}|[0-9]{1,30}(?:\.[0-9]{1,24})?)$/.test(value); }
