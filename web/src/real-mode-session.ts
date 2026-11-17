/** HG4 revision (PD-0087): the commands of the real-mode screen, as plain functions over a set of state sinks, so their effects can be tested without a DOM.
 *
 * Every request the screen sends goes through here. A SESSION EPOCH counts sign-outs, session losses and sign-ins. A command notes the epoch when it starts, and a
 * result that arrives after the epoch moved on is DROPPED: a read, list or create that was in flight when the user signed out (or another user signed in) is never
 * shown on the next screen (TR8F L-1). Nothing here computes or formats a figure. */
import { ApiError } from './transport';
import { createBody, newOperationId, UnknownOutcome, type CreateForm, type RealModeApi, type RealReproduction, type RealRoot, type RealSession, type RootEntry } from './real-mode';

export const EMPTY_FORM: CreateForm = { contextId: '', releaseId: '', listingId: '', name: '', asOf: '', quantity: '', cash: '', currency: 'USD' };
export const EMPTY_IDS = { rootId: '', operationId: '' };
export interface Credentials { username: string; password: string }

/** DR-R8-3: after a refused sign-in or sign-up the username stays and the password does not. */
export function withoutPassword(credentials: Credentials): Credentials {
  return { username: credentials.username, password: '' };
}

/** DR-R8-1: Open reads the stored result of a listed root with the operation id the list carries (stored with the root, read by the server); nothing is derived or
 * guessed here. Returns the ids to show in the Read form and the root read. */
export async function openEntry(api: Pick<RealModeApi, 'read'>, entry: RootEntry): Promise<{ ids: { rootId: string; operationId: string }; root: RealRoot }> {
  if (entry.operation_id === undefined) throw new ApiError('INVALID_RESPONSE', 'Invalid list');
  return { ids: { rootId: entry.root_id, operationId: entry.operation_id }, root: await api.read(entry.root_id, entry.operation_id) };
}

export class SessionEpoch {
  private count = 0;
  private running = 0;
  bump(): void { this.count += 1; this.running = 0; }
  /** The epoch now; the returned function is true while it is still the current one. */
  begin(): () => boolean { const at = this.count; return () => this.count === at; }
  /** A command starts. The returned release says how many commands of THIS epoch are still running, or null when the epoch has moved on: a command of an
   * earlier session never changes the busy state of the current one (TR8F2 L-1b). */
  track(): () => number | null {
    const at = this.count; this.running += 1;
    return () => { if (this.count !== at) return null; this.running -= 1; return this.running; };
  }
}

/** Every piece of screen state a command may set. All are required, so a command that stops setting one is a type error where the sinks are built. */
export interface Sinks {
  busy: (value: boolean) => void;
  problem: (value: string | null) => void;
  session: (value: RealSession | null) => void;
  entries: (value: RootEntry[] | null) => void;
  root: (value: RealRoot | null) => void;
  reproduction: (value: RealReproduction | null) => void;
  ids: (value: typeof EMPTY_IDS) => void;
  form: (value: CreateForm) => void;
  ack: (value: boolean) => void;
  uncertain: (value: UnknownOutcome | null) => void;
  credentials: (value: Credentials | ((previous: Credentials) => Credentials)) => void;
}
export type Api = Pick<RealModeApi, 'read' | 'list' | 'create' | 'reproduce' | 'credentials' | 'logout'>;
export interface Context { api: Api; epoch: SessionEpoch; sinks: Sinks; format: (error: unknown) => string }

/** DR-R8-4: what one user typed must not outlive that user's session: the Read ids, the Create form, its acknowledgement and a kept unknown-outcome command (which
 * holds the typed create body). */
export function clearTyped(sinks: Pick<Sinks, 'ids' | 'form' | 'ack' | 'uncertain'>): void {
  sinks.ids({ ...EMPTY_IDS }); sinks.form({ ...EMPTY_FORM }); sinks.ack(false); sinks.uncertain(null);
}
/** Everything the previous session showed. */
export function clearScreen(sinks: Sinks): void {
  sinks.entries(null); sinks.root(null); sinks.reproduction(null); clearTyped(sinks);
}

/** A stored result is shown only while a user is signed in. */
export function shownRoot(root: RealRoot | null, session: RealSession | null): RealRoot | null {
  return session?.authenticated ? root : null;
}

/** Busy while the task runs; a refusal becomes the problem text, unless the session moved on meanwhile (then it is not this screen's). */
export async function runCommand(ctx: Context, fresh: () => boolean, task: () => Promise<void>, format: (error: unknown) => string = ctx.format): Promise<void> {
  const release = ctx.epoch.track();
  ctx.sinks.busy(true); ctx.sinks.problem(null);
  try { await task(); }
  catch (error) { if (fresh() || (error instanceof ApiError && error.status === 401)) ctx.sinks.problem(format(error)); }   // a lost session is itself the news
  finally { const left = release(); if (left !== null) ctx.sinks.busy(left > 0); }
}

/** The session changes: later results of the old one are dropped, and nothing of the old session is still "running" on the new screen. */
function moveEpoch(ctx: Context): void {
  ctx.epoch.bump(); ctx.sinks.busy(false);
}

export function refreshList(ctx: Context): Promise<void> {
  const fresh = ctx.epoch.begin();
  return runCommand(ctx, fresh, async () => { const list = await ctx.api.list(); if (fresh()) ctx.sinks.entries(list); });
}

/** Open from the list (DR-R8-1). */
export function openStored(ctx: Context, entry: RootEntry): Promise<void> {
  const fresh = ctx.epoch.begin();
  return runCommand(ctx, fresh, async () => {
    ctx.sinks.reproduction(null);
    const opened = await openEntry(ctx.api, entry);
    if (!fresh()) return;
    ctx.sinks.ids(opened.ids); ctx.sinks.root(opened.root);
  });
}

/** The Read form. */
export function readTyped(ctx: Context, ids: { rootId: string; operationId: string }): Promise<void> {
  const fresh = ctx.epoch.begin();
  return runCommand(ctx, fresh, async () => {
    ctx.sinks.reproduction(null);
    const read = await ctx.api.read(ids.rootId.trim(), ids.operationId.trim());
    if (fresh()) ctx.sinks.root(read);
  });
}

export function reproduceRoot(ctx: Context, root: RealRoot): Promise<void> {
  const fresh = ctx.epoch.begin();
  return runCommand(ctx, fresh, async () => { const again = await ctx.api.reproduce(root.root_id, root.operation_id); if (fresh()) ctx.sinks.reproduction(again); });
}

/** Create, or repeat the identical command of an unknown outcome (the repeat sends the kept body, never a new operation id). */
export function createRoot(ctx: Context, form: CreateForm, repeat?: UnknownOutcome): Promise<void> {
  const fresh = ctx.epoch.begin();
  return runCommand(ctx, fresh, async () => {
    try {
      const body = repeat ? JSON.parse(repeat.body) : createBody(form, newOperationId());
      const created = await ctx.api.create(body);
      if (!fresh()) return;
      ctx.sinks.uncertain(null); ctx.sinks.reproduction(null); ctx.sinks.root(created);
      const list = await ctx.api.list();
      if (fresh()) ctx.sinks.entries(list);
    } catch (error) {
      if (error instanceof UnknownOutcome) { if (fresh()) ctx.sinks.uncertain(error); return; }
      throw error;
    }
  });
}

/** Sign in or sign up. A refusal keeps the username and clears the password (DR-R8-3). On success the epoch moves, so anything still in flight for the previous
 * session is dropped, and the screen starts empty for this (possibly different) user (DR-R8-4). */
export function enterSession(ctx: Context, kind: 'register' | 'login', credentials: Credentials, format: (error: unknown) => string): Promise<void> {
  return runCommand(ctx, () => true, async () => {
    let next: RealSession;
    try { next = await ctx.api.credentials(kind, credentials.username, credentials.password); }
    catch (error) { ctx.sinks.credentials(withoutPassword); throw error; }
    moveEpoch(ctx);
    const fresh = ctx.epoch.begin();
    clearScreen(ctx.sinks);
    ctx.sinks.session(next); ctx.sinks.credentials({ username: '', password: '' });
    const list = await ctx.api.list();
    if (fresh()) ctx.sinks.entries(list);
  }, format);
}

/** Sign out. The button is disabled while any command runs (`SignedInBar`), so nothing of this session is in flight when it starts, and the epoch moves only when
 * the logout is answered. There is NO bump before the call: a logout that fails would otherwise drop the still-signed-in user's own results, including an unknown
 * create outcome (TR8F2 L-1a). A result that arrives between the answer and the clearing lands on this session's own screen and is cleared with it. */
export function leaveSession(ctx: Context): Promise<void> {
  return runCommand(ctx, () => true, async () => {
    const next = await ctx.api.logout();
    moveEpoch(ctx);
    ctx.sinks.session(next); clearScreen(ctx.sinks);
  });
}

/** The server said the session is gone (401 or a rejected token). */
export function sessionLost(ctx: Context): void {
  moveEpoch(ctx);
  ctx.sinks.session(null); clearScreen(ctx.sinks);
}
