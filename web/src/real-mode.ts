/** F1 R7: the client of the scoped real-mode contract (`web_api/real_scoped_contract.py`). It transports and reads; it computes nothing.
 *
 * Every response is read STRICTLY: exact key sets, the stored origin fields, the labels the server derived from them, and the claim-limit block.
 * A value that does not fit is `INVALID_RESPONSE`, never repaired. The origin of a root is read from its stored fields and from nothing else; the client
 * has no list type in common with the fictional account list (`account.ts`), which types every saved portfolio as synthetic.
 */
import { ApiError, isObject, SCHEMA, type JsonObject } from './transport';
import { assertSlots, claimLimitText, ClaimTextError, ITEM_IDS, NORMAL_STATES, QUANT_IDS, S_SLOTS, variantOfSlots, WITHHELD_STATE, type Slots } from './real-mode-claims';

export const REAL_BASE = '/api/real/v1';
export const SCHEMAS = {
  created: 'finweb.cp7.real_scoped_create_result/1', read: 'finweb.cp7.real_scoped_read/2', reproduce: 'finweb.cp7.real_scoped_reproduce/1',
  list: 'finweb.cp7.real_scoped_list/2', refusal: 'finweb.cp7.real_scoped_refusal/1', unknown: 'finweb.cp7.real_scoped_unknown/1',
  create: 'finweb.cp7.real_scoped_create/1',
} as const;
const HASH = /^[0-9a-f]{64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export const ORIGIN_FIELDS = ['market_origin', 'ledger_origin', 'personal_holdings', 'synthetic'] as const;
export const REAL_MARKET = 'REAL_SOURCE';

export interface Origin { market_origin: string; ledger_origin: string; personal_holdings: boolean; synthetic: boolean }
export type OriginKind = 'REAL_SOURCE_CONSTRUCTED_ACCOUNT' | 'INVENTED_TEST_DATA';
export interface Labels { origin_kind: string; origin_statement: string; holding_statement: string }
export interface ClaimBlock {
  items: { id: string; kind: string; quant_ids: string[]; text: string }[];
  slots: Slots | Record<string, string>;
  invented_data_mark: string | null;
}
export interface RootEntry { root_id: string; operation_id?: string; context_id: string; generation?: number; created_at?: string; origin?: Origin; status?: string }
export interface RealRoot {
  state: 'COMMITTED'; replayed: boolean; root_id: string; operation_id: string; revision_id: string; ledger_pin: number;
  /** Opened (read) results only: the generation the root was created under, from the stored envelope. Not the list's current generation. The create result carries none. */
  created_under_generation?: number;
  origin: Origin; labels: Labels; response_sha256: string; issued_sha256: string; result: JsonObject; claim_limits: ClaimBlock;
}
export interface RealReproduction {
  root_id: string; operation_id: string; origin: Origin; labels: Labels; status: string; detail: string; issued_sha256: string | null;
}
export interface RealSession { authenticated: boolean; user: { user_id: string; username: string } | null; csrf_token: string }

function bad(what: string): never { throw new ApiError('INVALID_RESPONSE', `Invalid ${what}`); }
function exactKeys(value: JsonObject, keys: readonly string[], what: string): void {
  const have = Object.keys(value).sort().join();
  if (have !== [...keys].sort().join()) bad(what);
}
function text(value: unknown, what: string): string {
  if (typeof value !== 'string' || value === '') bad(what);
  return value;
}

/** (market_origin, ledger_origin, synthetic) -> kind. Mirrors `persistence/real_labels.py`; a contradiction is refused, as the server refuses it. */
const KINDS: [string, string, boolean, OriginKind][] = [
  ['REAL_SOURCE', 'PROJECT_CONSTRUCTED_NONPERSONAL_UAT', false, 'REAL_SOURCE_CONSTRUCTED_ACCOUNT'],
  ['SYNTHETIC_TEST', 'INVENTED_TEST_LEDGER', true, 'INVENTED_TEST_DATA'],
];
export function readOrigin(value: unknown): Origin {
  if (!isObject(value)) bad('origin');
  exactKeys(value, ORIGIN_FIELDS, 'origin');
  if (typeof value.market_origin !== 'string' || typeof value.ledger_origin !== 'string' || typeof value.personal_holdings !== 'boolean'
    || typeof value.synthetic !== 'boolean') bad('origin');
  const origin = value as unknown as Origin;
  originKind(origin);
  return origin;
}
export function originKind(origin: Origin): OriginKind {
  if (origin.personal_holdings) bad('origin');
  const found = KINDS.find(([m, l, s]) => m === origin.market_origin && l === origin.ledger_origin && s === origin.synthetic);
  if (!found) bad('origin');
  return found[3];
}
export function isRealOrigin(origin: Origin): boolean { return origin.market_origin === REAL_MARKET; }

export function readLabels(value: unknown, origin: Origin): Labels {
  if (!isObject(value)) bad('labels');
  const keys = ['origin_kind', 'origin_statement', 'holding_statement'];
  for (const key of keys) text(value[key], 'labels');
  if (value.origin_kind !== originKind(origin)) bad('labels');
  return { origin_kind: value.origin_kind as string, origin_statement: value.origin_statement as string, holding_statement: value.holding_statement as string };
}

export function readClaimBlock(value: unknown, origin: Origin): ClaimBlock {
  if (!isObject(value)) bad('claim limits');
  exactKeys(value, ['items', 'slots', 'invented_data_mark'], 'claim limits');
  if (!Array.isArray(value.items) || !isObject(value.slots)) bad('claim limits');
  if (!isRealOrigin(origin)) {
    // Any other origin: the mark in every S-slot and no item. The client never renders a real-source sentence from this block.
    const mark = text(value.invented_data_mark, 'claim limits');
    if (value.items.length !== 0 || S_SLOTS.some((name) => (value.slots as JsonObject)[name] !== mark)
      || Object.keys(value.slots).length !== S_SLOTS.length) bad('claim limits');
    return value as unknown as ClaimBlock;
  }
  if (value.invented_data_mark !== null) bad('claim limits');
  try { assertSlots(value.slots); } catch (error) { if (error instanceof ClaimTextError) bad('claim limits'); throw error; }
  const ids = value.items.map((item) => (isObject(item) ? item.id : null));
  if (ids.join() !== ITEM_IDS.join()) bad('claim limits');
  // the server's contract refuses a block whose state disagrees with its variant, whose two state slots differ, or whose Quant ids are not the variant's
  // (TR-O7-L-3); so does the client's strict reader
  const variant = variantOfSlots(value.slots);
  const slots = value.slots as Record<string, Record<string, string>>;
  if (variant === 'withheld' ? (slots.S1.state !== WITHHELD_STATE || slots.S3.state !== WITHHELD_STATE) : !NORMAL_STATES.includes(slots.S3.state)) bad('claim limits');
  // TR-O7C-L-1: each item's kind and text must equal the client's own rendering of the slots (the English professional templates are pinned equal to the
  // server's text by a Python test), as the server's re-render equality requires
  const rendered = claimLimitText(slots, 'en', 'professional');
  for (const [index, item] of value.items.entries()) {
    if (!isObject(item)) bad('claim limits');
    exactKeys(item, ['id', 'kind', 'quant_ids', 'text'], 'claim limits');
    text(item.text, 'claim limits');
    if (item.kind !== rendered[index].kind || item.text !== rendered[index].text) bad('claim limits');
    if (!Array.isArray(item.quant_ids) || item.quant_ids.join() !== QUANT_IDS[variant][item.id as string].join()) bad('claim limits');
  }
  return value as unknown as ClaimBlock;
}

function digest(value: unknown, what: string): string {
  if (typeof value !== 'string' || !HASH.test(value)) bad(what);
  return value;
}
function uuid(value: unknown, what: string): string {
  if (typeof value !== 'string' || !UUID.test(value)) bad(what);
  return value;
}

export function readRoot(value: unknown, kind: 'created' | 'read'): RealRoot {
  if (!isObject(value)) bad('root');
  const keys = ['schema_version', 'state', 'persisted', 'root_id', 'operation_id', 'revision_id', 'ledger_pin', 'origin', 'labels', 'response_sha256',
    'issued_sha256', 'result', 'claim_limits'];
  exactKeys(value, kind === 'created' ? [...keys, 'replayed'] : [...keys, 'created_under_generation'], 'root');
  const generation = value.created_under_generation;
  if (kind === 'read' && !(Number.isSafeInteger(generation) && (generation as number) >= 1)) bad('root');
  if (value.schema_version !== SCHEMAS[kind] || value.state !== 'COMMITTED' || value.persisted !== true || !Number.isInteger(value.ledger_pin)
    || !isObject(value.result) || (kind === 'created' && typeof value.replayed !== 'boolean')) bad('root');
  const origin = readOrigin(value.origin);
  return {
    state: 'COMMITTED', replayed: kind === 'created' ? (value.replayed as boolean) : false, root_id: uuid(value.root_id, 'root'),
    operation_id: uuid(value.operation_id, 'root'), revision_id: uuid(value.revision_id, 'root'), ledger_pin: value.ledger_pin as number, origin,
    ...(kind === 'read' ? { created_under_generation: generation as number } : {}),
    labels: readLabels(value.labels, origin), response_sha256: digest(value.response_sha256, 'root'), issued_sha256: digest(value.issued_sha256, 'root'),
    result: value.result, claim_limits: readClaimBlock(value.claim_limits, origin),
  };
}

export function readReproduction(value: unknown): RealReproduction {
  if (!isObject(value)) bad('reproduction');
  exactKeys(value, ['schema_version', 'root_id', 'operation_id', 'origin', 'labels', 'status', 'detail', 'issued_sha256'], 'reproduction');
  if (value.schema_version !== SCHEMAS.reproduce || typeof value.detail !== 'string') bad('reproduction');
  const status = text(value.status, 'reproduction');
  if (!['REPRODUCED', 'RESULT_DIFFERS', 'INPUT_MISMATCH', 'SOURCE_REFUSED'].includes(status)) bad('reproduction');
  const optional = status === 'INPUT_MISMATCH' || status === 'SOURCE_REFUSED';
  if (!(optional && value.issued_sha256 === null)) digest(value.issued_sha256, 'reproduction');
  const origin = readOrigin(value.origin);
  return { root_id: uuid(value.root_id, 'reproduction'), operation_id: uuid(value.operation_id, 'reproduction'), origin, labels: readLabels(value.labels, origin),
    status, detail: value.detail, issued_sha256: value.issued_sha256 as string | null };
}

/** The list route. An entry is either readable (identifiers including the root's create operation id, origin, generation, creation time) or refused (identifiers and the refusal code only). */
export function readRootList(value: unknown): RootEntry[] {
  if (!isObject(value)) bad('list');
  exactKeys(value, ['schema_version', 'roots'], 'list');
  if (value.schema_version !== SCHEMAS.list || !Array.isArray(value.roots)) bad('list');
  return value.roots.map((entry) => {
    if (!isObject(entry)) bad('list');
    if ('status' in entry) {
      exactKeys(entry, ['root_id', 'context_id', 'status'], 'list');
      return { root_id: uuid(entry.root_id, 'list'), context_id: digest(entry.context_id, 'list'), status: text(entry.status, 'list') };
    }
    exactKeys(entry, ['root_id', 'operation_id', 'context_id', 'generation', 'created_at', 'origin'], 'list');
    if (!Number.isInteger(entry.generation)) bad('list');
    return { root_id: uuid(entry.root_id, 'list'), operation_id: uuid(entry.operation_id, 'list'), context_id: digest(entry.context_id, 'list'), generation: entry.generation as number,
      created_at: text(entry.created_at, 'list'), origin: readOrigin(entry.origin) };
  });
}

export function readSession(value: unknown): RealSession {
  if (!isObject(value) || value.schema_version !== SCHEMA || typeof value.authenticated !== 'boolean' || typeof value.csrf_token !== 'string'
    || !HASH.test(value.csrf_token)) bad('session');
  const user = value.user;
  if (value.authenticated ? !isObject(user) || typeof user.user_id !== 'string' || typeof user.username !== 'string' : user !== null) bad('session');
  return { authenticated: value.authenticated, user: user as RealSession['user'], csrf_token: value.csrf_token };
}

/* ---- key figures (PD-0079): a FIXED list of stored metrics, shown as stored ----------------------------------------------------------------- */

/** The figures of the single-date valuation that the screen lists, chosen by metric id and view, in this order. Not by value, not by what looks
 * interesting. `portfolio_value`/`REPORTING` is the NAV. `portfolio_value_priced_holdings` (the partial figure, "never the total") is not one of these groups: the
 * engine emits it only when the total has no number (Ruling 1.4a), and `partialBlock` shows it then, apart from the groups, with its excluded counts (PD-0035 section 2). */
export const FIGURE_LIST = [
  { id: 'portfolio_value', view: 'REPORTING', label: 'figureNav' },
  { id: 'holding_value', view: 'REPORTING', label: 'figureHolding' },
  { id: 'cash_value', view: 'REPORTING', label: 'figureCash' },
  { id: 'receivable_value', view: 'REPORTING', label: 'figureReceivable' },
] as const;
export type FigureLabel = (typeof FIGURE_LIST)[number]['label'];
export const FIGURE_STATES = ['AVAILABLE', 'LIMITED', 'INSUFFICIENT_DATA'] as const;

/** One stored metric as the screen shows it. Every field is a stored value, copied: nothing is computed, rounded, converted, sorted or derived. `value` is
 * null whenever the number must not show (state INSUFFICIENT_DATA, or a state outside the three known ones: no metric without a state). */
export interface FigureRow {
  metric_id: string; view: string; subject: string; value: string | null; currency: string | null; state: string; reason: string | null; known_state: boolean;
  /** The stored cause codes (`details`), copied and uninterpreted: where a row has no reason code this is where the engine names its cause (F-9). */
  details: string[];
  /** True when the row cannot be shown as a figure: a state outside the three, or AVAILABLE or LIMITED with no stored string value (F-10). A JSON number is
   * never shown: `String(number)` is not "as stored" (the engine stores decimals as strings and refuses floats). */
  unreadable: boolean;
  /** The stored `stale_weight_presented`, as text (F-1); null when the row stores none. */
  stale_weight: string | null;
  /** True on a LIMITED `portfolio_value` row that stores no stale weight: the screen then says it is not stated (F-1). */
  stale_not_stated: boolean;
  /** True when the row has a number and stores a stale weight that is not decimal text: the screen then shows the weight label with "not readable" (TR7F-L-1). */
  stale_weight_bad: boolean;
}
export interface FigureGroup { id: string; view: string; label: FigureLabel; rows: FigureRow[] }
/** The partial figure block (F-2): the stored row and two stored counts, as text. A count the row does not store is null. */
export interface PartialBlock { row: FigureRow; excluded_holdings: string | null; excluded_components: string | null }
/** Whether the result holds the NAV row, and whether that row carries a number: ABSENT (no row at all), NUMBER, NO_NUMBER (a row with no number to show). */
export type NavStatus = 'ABSENT' | 'NUMBER' | 'NO_NUMBER' | 'AMBIGUOUS';

const storedText = (value: unknown): string | null => (typeof value === 'string' ? value : null);
/** A SHAPE check, not a conversion: plain decimal text as the engine writes it ("4000", "-0.10", "1.00"): optional minus, digits, optional fraction. The engine's
 * `canonical_decimal` always writes plain digits, so text with an exponent ("1e3"), or empty, "NaN" or "abc", can only come from a defect upstream: it is not a stored
 * figure and is never shown as one (TR7F-L-1, TR7F2-L-1). The text itself is never parsed, converted or rewritten. */
const DECIMAL_TEXT = /^-?\d+(\.\d+)?$/;
const COUNT_TEXT = /^\d+$/;
const decimalText = (value: unknown): string | null => (typeof value === 'string' && DECIMAL_TEXT.test(value) ? value : null);
function figureRow(metric: JsonObject): FigureRow {
  const state = storedText(metric.state) ?? '';
  const known = (FIGURE_STATES as readonly string[]).includes(state);
  const stored = decimalText(metric.value);
  const hasNumber = known && state !== 'INSUFFICIENT_DATA';
  const shown = hasNumber && stored !== null;                      // the row has a number to show
  const weightStored = metric.stale_weight_presented;
  const noWeight = weightStored === null || weightStored === undefined;
  const weight = decimalText(weightStored);
  const subject = Array.isArray(metric.subject)
    ? metric.subject.map((pair) => (Array.isArray(pair) ? pair.map((part) => String(part)).join('=') : String(pair))).join(' · ') : '';
  return {
    metric_id: String(metric.metric_id), view: String(metric.view), subject, value: shown ? stored : null,
    currency: storedText(metric.currency), state, reason: storedText(metric.reason), known_state: known,
    details: Array.isArray(metric.details) ? metric.details.filter((item): item is string => typeof item === 'string') : [],
    unreadable: !known || (hasNumber && stored === null),
    // the weight shows only on a row that shows a number (a suppressed or unreadable row shows none)
    // H-1 (the Quant): the weight shows only on a LIMITED row that shows a number. Never on AVAILABLE, never on a suppressed or unknown-state row.
    stale_weight: state === 'LIMITED' && shown ? weight : null,
    stale_weight_bad: state === 'LIMITED' && shown && !noWeight && weight === null,
    stale_not_stated: String(metric.metric_id) === 'portfolio_value' && state === 'LIMITED' && shown && noWeight,
  };
}
const reportingRows = (metrics: JsonObject[], id: string): JsonObject[] => metrics.filter((metric) => metric.metric_id === id && metric.view === 'REPORTING');
const resultMetrics = (result: JsonObject): JsonObject[] => (Array.isArray(result.metrics) ? result.metrics.filter(isObject) : []);
const subjectValue = (metric: JsonObject, key: string): string | null => {
  if (!Array.isArray(metric.subject)) return null;
  for (const pair of metric.subject) if (Array.isArray(pair) && pair[0] === key && typeof pair[1] === 'string') return pair[1];
  return null;
};
/** The stored `breakdown` ref of a part, built from its stored subject (F-3): `holding:{account}/{listing}`, `cash:{account}/{currency}`,
 * `receivable:{account}/{event}`. Null when the subject lacks a piece. */
function partRef(metric: JsonObject): string | null {
  const account = subjectValue(metric, 'account');
  const parts: Record<string, string[]> = { holding_value: ['holding', 'listing'], cash_value: ['cash', 'currency'], receivable_value: ['receivable', 'event'] };
  const second = parts[String(metric.metric_id)];
  const tail = second ? subjectValue(metric, second[1]) : null;
  return account !== null && second && tail !== null ? `${second[0]}:${account}/${tail}` : null;
}
/** The breakdown as a lookup from ref to its `shown` entry (index 1), or null when the breakdown breaks the contract: a line that is not `[ref, decimal text, ...]`,
 * or two lines with one ref. Nothing is taken from a breakdown like that, not the first line and not the next good one (TR7F-L-1). */
function breakdownLookup(breakdown: unknown[]): Map<string, string> | null {
  const lookup = new Map<string, string>();
  for (const line of breakdown) {
    if (!Array.isArray(line) || typeof line[0] !== 'string' || decimalText(line[1]) === null || lookup.has(line[0])) return null;
    lookup.set(line[0], line[1] as string);
  }
  return lookup;
}
/** The NAV status of a stored result (the `portfolio_value`/REPORTING rows): ABSENT, one row with or without a number, or AMBIGUOUS (more than one row). */
export function navStatus(result: JsonObject): NavStatus {
  const rows = reportingRows(resultMetrics(result), 'portfolio_value');
  if (rows.length === 0) return 'ABSENT';
  if (rows.length > 1) return 'AMBIGUOUS';
  return figureRow(rows[0]).value !== null ? 'NUMBER' : 'NO_NUMBER';
}
/** The listed figures of a stored result, in the fixed list's order, and within a figure in the stored order. A listed figure the result does not hold is a
 * group with no rows (shown as absent), never dropped. A result without a metrics array holds none of them. */
export function keyFigures(result: JsonObject): FigureGroup[] {
  const metrics = resultMetrics(result);
  // F-3 (amended, TR7F3-L-1): where the total has a number, a part with a number shows the breakdown's own `shown` entry (the engine's apportioned value), never its
  // separate row's value (the two can differ in the last place). If the breakdown cannot supply that entry (absent, null, not an array, empty, malformed, or no
  // matching line) the part shows no number. Where the total has no number, each part shows its own stored value.
  // More than one NAV row breaks the contract: every NAV row then shows "not readable" and no number, and no part is apportioned from any of them.
  const navRows = reportingRows(metrics, 'portfolio_value');
  const nav = navRows.length === 1 ? navRows[0] : undefined;
  const total = nav !== undefined ? figureRow(nav) : null;
  const raw = nav !== undefined ? nav.breakdown : undefined;
  // No lookup can be built from an absent, null, non-array or empty breakdown; a part with a number then shows none (via `withoutNumber`).
  const breakdown = Array.isArray(raw) && raw.length > 0 ? raw : null;
  const lookup = breakdown !== null ? breakdownLookup(breakdown) : null;
  const apportioned = total !== null && total.value !== null;
  const withoutNumber = (row: FigureRow): FigureRow => ({ ...row, value: null, unreadable: true, stale_weight: null, stale_weight_bad: false, stale_not_stated: false });
  return FIGURE_LIST.map((entry) => ({
    id: entry.id, view: entry.view, label: entry.label,
    rows: metrics.filter((metric) => metric.metric_id === entry.id && metric.view === entry.view).map((metric) => {
      const row = figureRow(metric);
      if (entry.id === 'portfolio_value') return navRows.length > 1 ? withoutNumber(row) : row;
      if (!apportioned || row.value === null) return row;
      const part = lookup !== null ? partRef(metric) : null;
      const found = part !== null && lookup !== null ? lookup.get(part) : undefined;
      return found === undefined ? withoutNumber(row) : { ...row, value: found };
    }),
  }));
}
/** The partial figure block (F-2): present only when the NAV has no number to show AND the result stores a `portfolio_value_priced_holdings`/REPORTING row.
 * The counts are the stored `lineage` entries, copied as text. */
export function partialBlock(result: JsonObject): PartialBlock | null {
  const metrics = resultMetrics(result);
  const partials = reportingRows(metrics, 'portfolio_value_priced_holdings');
  const partial = partials[0];
  const status = navStatus(result);
  if (partial === undefined || status === 'NUMBER' || status === 'AMBIGUOUS') return null;
  // a count is the stored lineage entry, copied; none, two, or text that is not a count shows as "not readable"
  const count = (key: string): string | null => {
    if (!Array.isArray(partial.lineage)) return null;
    const found = partial.lineage.filter((pair) => Array.isArray(pair) && pair[0] === key);
    const only = found.length === 1 ? found[0] : null;
    return Array.isArray(only) && typeof only[1] === 'string' && COUNT_TEXT.test(only[1]) ? only[1] : null;
  };
  // two partial rows break the contract (the engine emits one): the block shows "not readable", no number and so no count
  const row = figureRow(partial);
  const shown: FigureRow = partials.length > 1 ? { ...row, value: null, unreadable: true, stale_weight: null, stale_weight_bad: false, stale_not_stated: false } : row;
  return { row: shown, excluded_holdings: count('excluded_holdings'), excluded_components: count('excluded_components') };
}

export interface CreateForm {
  contextId: string; releaseId: string; listingId: string; name: string; asOf: string; quantity: string; cash: string; currency: string;
}
export function newOperationId(): string { return globalThis.crypto.randomUUID(); }
/** The create body exactly as the contract's intent. The caller supplies the operation id so that an identical retry can be repeated. */
export function createBody(form: CreateForm, operationId: string): JsonObject {
  return {
    schema_version: SCHEMAS.create, operation_id: operationId, source_context_id: form.contextId, expected_release_id: form.releaseId, name: form.name,
    reporting_currency: form.currency, as_of: form.asOf, constructed_ledger_acknowledged: true,
    opening_positions: [{ listing_id: form.listingId, quantity: form.quantity, cost_basis: null, acquired_on: null }],
    opening_cash: { currency: form.currency, amount: form.cash },
  };
}

export class UnknownOutcome extends Error {
  constructor(public operationId: string, public body: string) { super('UNKNOWN_OUTCOME'); }
}

/** Cookie credentials are HttpOnly; only the CSRF token lives in this instance's memory. */
export class RealModeApi {
  private csrf: string | null = null;
  onSessionLost: (() => void) | null = null;

  private async call(path: string, method: 'GET' | 'POST', body?: string): Promise<{ status: number; value: unknown }> {
    let response: Response;
    try {
      response = await fetch(path, {
        method, credentials: 'same-origin', cache: 'no-store',
        headers: method === 'GET' ? {} : { 'Content-Type': 'application/json', 'X-Finweb-CSRF': this.csrf ?? '' },
        ...(method === 'GET' ? {} : { body: body ?? '{}' }),
      });
    } catch { throw new ApiError('NETWORK_ERROR', 'Local API unavailable'); }
    let value: unknown;
    try { value = await response.json(); } catch { throw new ApiError('INVALID_RESPONSE', 'Invalid JSON', response.status); }
    return { status: response.status, value };
  }
  private failure(status: number, value: unknown): ApiError {
    const error = isObject(value) && isObject(value.error) ? value.error : null;
    const code = typeof error?.code === 'string' ? error.code : 'API_ERROR';
    if (status === 401 || code === 'CSRF_REJECTED') { this.csrf = null; this.onSessionLost?.(); }
    return new ApiError(code, typeof error?.detail === 'string' ? error.detail : '', status);
  }
  private accept(session: RealSession): RealSession { this.csrf = session.csrf_token; return session; }

  async session(): Promise<RealSession> {
    const { status, value } = await this.call('/api/v1/auth/session', 'GET');
    if (status !== 200) throw this.failure(status, value);
    return this.accept(readSession(value));
  }
  async credentials(kind: 'register' | 'login', username: string, password: string): Promise<RealSession> {
    if (!this.csrf) await this.session();
    const { status, value } = await this.call(`/api/v1/auth/${kind}`, 'POST', JSON.stringify({ username, password }));
    if (status !== 200 && status !== 201) throw this.failure(status, value);
    return this.accept(readSession(value));
  }
  async logout(): Promise<RealSession> {
    const { status, value } = await this.call('/api/v1/auth/logout', 'POST', '{}');
    if (status !== 200) throw this.failure(status, value);
    return this.accept(readSession(value));
  }
  async list(): Promise<RootEntry[]> {
    const { status, value } = await this.call(`${REAL_BASE}/roots`, 'GET');
    if (status !== 200) throw this.failure(status, value);
    return readRootList(value);
  }
  async create(body: JsonObject): Promise<RealRoot> {
    const json = JSON.stringify(body);
    // TR7-L-5: a create whose outcome the client cannot read (no answer, an answer that is not JSON, a 5xx that is not a contract refusal, or a 200/201 that
    // fails the strict reader) may have committed. It is an unknown outcome: the id and the exact body are kept so the identical command can be repeated
    // (the repeat returns the stored result, marked as a replay). It is never a plain error that lets the next Create mint a new id.
    const unknown = () => new UnknownOutcome(String(body.operation_id), json);
    let answer: { status: number; value: unknown };
    try { answer = await this.call(`${REAL_BASE}/roots`, 'POST', json); }
    catch (error) { if (error instanceof ApiError && (error.code === 'NETWORK_ERROR' || error.code === 'INVALID_RESPONSE')) throw unknown(); throw error; }
    const { status, value } = answer;
    if (isObject(value) && value.schema_version === SCHEMAS.unknown) throw unknown();
    if (status !== 200 && status !== 201) {
      if (status >= 500 && !(isObject(value) && isObject(value.error) && typeof value.error.code === 'string')) throw unknown();
      throw this.failure(status, value);
    }
    try { return readRoot(value, 'created'); }
    catch (error) { if (error instanceof ApiError && error.code === 'INVALID_RESPONSE') throw unknown(); throw error; }
  }
  async read(rootId: string, operationId: string): Promise<RealRoot> {
    const { status, value } = await this.call(`${REAL_BASE}/roots/${uuid(rootId, 'id')}/operations/${uuid(operationId, 'id')}`, 'GET');
    if (status !== 200) throw this.failure(status, value);
    return readRoot(value, 'read');
  }
  async reproduce(rootId: string, operationId: string): Promise<RealReproduction> {
    const { status, value } = await this.call(`${REAL_BASE}/roots/${uuid(rootId, 'id')}/operations/${uuid(operationId, 'id')}/reproduce`, 'POST', '{}');
    if (status !== 200) throw this.failure(status, value);
    return readReproduction(value);
  }
}
