/** HG4 revision (PD-0087): DR-R8-1 (Open opens), DR-R8-3 (the sign-in rules are stated), DR-R8-4 (typed values do not outlive a session), and the review TR8F
 * (M-1: the effects of Open are tested; L-1: a late result of a previous session is dropped; L-2: both rules in the refusal text). Node environment, no DOM: the
 * commands are plain functions over state sinks (real-mode-session.ts), so their EFFECTS are tested here, not their source text. */
import { readFileSync } from 'node:fs';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from './transport';
import { common, createTranslator, translator } from './real-mode-i18n';
import RealModeApp, { credentialsRefusalText, refusalText, RootEntries, SignedInBar } from './RealModeApp';
import { clearTyped, createRoot, EMPTY_FORM, EMPTY_IDS, enterSession, leaveSession, openEntry, openStored, readTyped, refreshList, reproduceRoot, SessionEpoch, sessionLost,
  shownRoot, withoutPassword, type Api, type Context, type Sinks } from './real-mode-session';
import { UnknownOutcome, type Origin, type RealReproduction, type RealRoot, type RealSession, type RootEntry } from './real-mode';

const UUID_A = '11111111-1111-4111-8111-111111111111';
const UUID_B = '22222222-2222-4222-8222-222222222222';
const HEX = (c: string) => c.repeat(64);
const REAL: Origin = { market_origin: 'REAL_SOURCE', ledger_origin: 'PROJECT_CONSTRUCTED_NONPERSONAL_UAT', personal_holdings: false, synthetic: false };
const t = translator('en', createTranslator());
const tz = translator('zh-CN', createTranslator());
const readable: RootEntry = { root_id: UUID_A, operation_id: UUID_B, context_id: HEX('c'), generation: 1, created_at: '2026-11-16T00:00:00+00:00', origin: REAL };
const ROOT_A = { root_id: UUID_A, operation_id: UUID_B, tag: 'A-root' } as unknown as RealRoot;
const SESSION = (name: string) => ({ authenticated: true, user: { user_id: 'u', username: name }, csrf_token: HEX('e') }) as RealSession;
const SIGNED_OUT = { authenticated: false, user: null, csrf_token: HEX('e') } as RealSession;

/** A promise whose resolution the test controls: the request that is "in flight". */
function deferred<T>() {
  let resolve!: (value: T) => void; let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

/** Sinks that record the last value set for each piece of state, and every call. */
function world(api: Partial<Api>, format: (error: unknown) => string = (error) => `F:${(error as ApiError).code}`) {
  const state: Record<string, unknown> = { busy: false, problem: null, session: null, entries: null, root: null, reproduction: null, ids: { ...EMPTY_IDS }, form: { ...EMPTY_FORM },
    ack: false, uncertain: null, credentials: { username: '', password: '' } };
  const log: string[] = [];
  const sinks = Object.fromEntries(Object.keys(state).map((key) => [key, (value: unknown) => {
    state[key] = typeof value === 'function' ? (value as (previous: unknown) => unknown)(state[key]) : value; log.push(key);
  }])) as unknown as Sinks;
  const ctx: Context = { api: api as Api, epoch: new SessionEpoch(), sinks, format };
  return { ctx, state, log };
}

describe('DR-R8-1 and M-1: Open shows the stored result of the listed root', () => {
  it('reads with the root id and the operation id of the list entry', async () => {
    const read = vi.fn(async (_root: string, _operation: string) => 'THE-ROOT' as never);
    const opened = await openEntry({ read }, readable);
    expect(read).toHaveBeenCalledWith(UUID_A, UUID_B);
    expect(opened).toEqual({ ids: { rootId: UUID_A, operationId: UUID_B }, root: 'THE-ROOT' });
  });
  it('does not guess: an entry without an operation id is not read', async () => {
    const read = vi.fn();
    const { operation_id: _gone, ...bare } = readable;
    await expect(openEntry({ read }, bare as RootEntry)).rejects.toBeInstanceOf(ApiError);
    expect(read).not.toHaveBeenCalled();
  });
  it('sets the root (the stored result is SHOWN) and the Read form ids, and is busy only while it runs', async () => {
    const read = deferred<RealRoot>();
    const w = world({ read: () => read.promise });
    const running = openStored(w.ctx, readable);
    expect(w.state.busy).toBe(true);
    read.resolve(ROOT_A);
    await running;
    expect(w.state.root).toBe(ROOT_A);
    expect(w.state.ids).toEqual({ rootId: UUID_A, operationId: UUID_B });
    expect(w.state.problem).toBeNull();
    expect(w.state.busy).toBe(false);
  });
  it('shows a refusal of the read as the problem text, with no unhandled rejection and no root', async () => {
    const w = world({ read: async () => { throw new ApiError('RW_WITHDRAWN', 'x', 409); } });
    await expect(openStored(w.ctx, readable)).resolves.toBeUndefined();
    expect(w.state.problem).toBe('F:RW_WITHDRAWN');
    expect(w.state.root).toBeNull();
    expect(w.state.busy).toBe(false);
  });
  it('disables Open for a command in flight (the prop is required) and shows it only for a readable entry', () => {
    const refused: RootEntry = { root_id: UUID_B, context_id: HEX('d'), status: 'RW_WITHDRAWN' };
    const html = (busy: boolean) => renderToStaticMarkup(createElement(RootEntries, { entries: [readable, refused], locale: 'en', t, onOpen: () => undefined, busy }));
    expect(html(false).match(/<button/g)).toHaveLength(1);
    expect(html(false)).not.toMatch(/<button[^>]*disabled/);
    expect(html(true)).toMatch(/<button[^>]*disabled/);
  });
  it('sends every request of the screen through the commands, never straight from the component', () => {
    const code = readFileSync(new URL('./RealModeApp.tsx', import.meta.url), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    expect(code).not.toMatch(/api\.(read|list|create|reproduce|credentials|logout)\(/);
    for (const command of ['openStored(ctx, entry)', 'readTyped(ctx, ids)', 'refreshList(ctx)', 'createRoot(ctx, form, repeat)', 'reproduceRoot(ctx, shown)', 'leaveSession(ctx)',
      'enterSession(ctx, kind, credentials', 'sessionLost(ctx)', 'shownRoot(root, session)', '<RootDetail root={shown}']) expect(code, command).toContain(command);
    expect(code).toContain('busy={busy}');
  });
});

describe('L-1: a result that arrives after the session changed is dropped', () => {
  it('Open, then sign-out before the read returns: nothing of A lands on the signed-out screen', async () => {
    const read = deferred<RealRoot>();
    const w = world({ read: () => read.promise, logout: async () => SIGNED_OUT });
    w.state.session = SESSION('alice'); w.state.entries = [readable];
    const opening = openStored(w.ctx, readable);
    await leaveSession(w.ctx);
    expect(w.state.session).toBe(SIGNED_OUT);
    expect(w.state.entries).toBeNull();
    read.resolve(ROOT_A);                                                                         // the late answer
    await opening;
    expect(w.state.root).toBeNull();
    expect(w.state.ids).toEqual(EMPTY_IDS);
    expect(w.state.busy).toBe(false);
  });
  it('Refresh, then sign-out and another sign-in before the list returns: A\'s roots do not appear under B', async () => {
    const late = deferred<RootEntry[]>();
    const lists = [late.promise, Promise.resolve([] as RootEntry[])];
    const w = world({ list: () => lists.shift()!, logout: async () => SIGNED_OUT, credentials: async () => SESSION('bob') });
    w.state.session = SESSION('alice');
    const refreshing = refreshList(w.ctx);
    await leaveSession(w.ctx);
    await enterSession(w.ctx, 'login', { username: 'bob', password: 'p'.repeat(15) }, w.ctx.format);
    expect(w.state.entries).toEqual([]);                                                          // B's own list
    late.resolve([readable]);
    await refreshing;
    expect(w.state.entries).toEqual([]);                                                          // A's late list was dropped
  });
  it('a read or a create in flight when the session is lost is dropped too', async () => {
    const read = deferred<RealRoot>(); const create = deferred<RealRoot>();
    const w = world({ read: () => read.promise, create: () => create.promise, list: async () => [readable] });
    const reading = readTyped(w.ctx, { rootId: UUID_A, operationId: UUID_B });
    const creating = createRoot(w.ctx, { ...EMPTY_FORM, contextId: HEX('c') });
    sessionLost(w.ctx);
    read.resolve(ROOT_A); create.resolve(ROOT_A);
    await Promise.all([reading, creating]);
    expect(w.state.root).toBeNull();
    expect(w.state.entries).toBeNull();
    expect(w.state.uncertain).toBeNull();
  });
  it('a reproduction in flight at sign-out is dropped', async () => {
    const again = deferred<RealReproduction>();
    const w = world({ reproduce: () => again.promise, logout: async () => SIGNED_OUT });
    const reproducing = reproduceRoot(w.ctx, ROOT_A);
    await leaveSession(w.ctx);
    again.resolve({ status: 'REPRODUCED' } as RealReproduction);
    await reproducing;
    expect(w.state.reproduction).toBeNull();
  });
  it('without a change of session the same commands do apply their results', async () => {
    const read = vi.fn(async (_root: string, _operation: string) => ROOT_A);
    const reproduce = vi.fn(async (_root: string, _operation: string) => ({ status: 'REPRODUCED' }) as RealReproduction);
    const w = world({ list: async () => [readable], read, create: async () => ROOT_A, reproduce });
    await refreshList(w.ctx); expect(w.state.entries).toEqual([readable]);
    await readTyped(w.ctx, { rootId: ` ${UUID_A} `, operationId: `${UUID_B}\n` }); expect(w.state.root).toBe(ROOT_A);
    expect(read).toHaveBeenCalledWith(UUID_A, UUID_B);                                            // the typed ids are trimmed (B5)
    await reproduceRoot(w.ctx, ROOT_A); expect(w.state.reproduction).toEqual({ status: 'REPRODUCED' });
    expect(reproduce).toHaveBeenCalledWith(UUID_A, UUID_B);                                       // the root id, then the OPERATION id (B12)
    w.state.root = null; w.state.entries = null;
    await createRoot(w.ctx, { ...EMPTY_FORM, contextId: HEX('c') }); expect(w.state.root).toBe(ROOT_A);
    expect(w.state.entries).toEqual([readable]);                                                  // a create refreshes the list (B4)
  });
  it('an unknown outcome that arrives after the session changed is dropped, so no Repeat of A\'s command appears for B (E6)', async () => {
    const create = deferred<RealRoot>();
    const w = world({ create: () => create.promise, logout: async () => SIGNED_OUT, list: async () => [] });
    const creating = createRoot(w.ctx, { ...EMPTY_FORM, contextId: HEX('c') });
    sessionLost(w.ctx);
    create.reject(new UnknownOutcome(UUID_B, '{"operation_id":"A"}'));
    await creating;
    expect(w.state.uncertain).toBeNull();
  });
  it('the list fetched after a create is dropped when the session changed meanwhile (E7)', async () => {
    const list = deferred<RootEntry[]>();
    const w = world({ create: async () => ROOT_A, list: () => list.promise });
    const creating = createRoot(w.ctx, { ...EMPTY_FORM, contextId: HEX('c') });
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();                    // the create answered; the list is in flight
    sessionLost(w.ctx);
    list.resolve([readable]);
    await creating;
    expect(w.state.entries).toBeNull();
  });
  it('Open, Read and Create each clear the reproduction of the previously shown root, which would otherwise be misattributed (B6, B7, B8)', async () => {
    const old = { status: 'REPRODUCED', tag: 'of-root-X' } as unknown as RealReproduction;
    for (const start of [(w: ReturnType<typeof world>) => openStored(w.ctx, readable), (w: ReturnType<typeof world>) => readTyped(w.ctx, { rootId: UUID_A, operationId: UUID_B }),
      (w: ReturnType<typeof world>) => createRoot(w.ctx, { ...EMPTY_FORM, contextId: HEX('c') })]) {
      const w = world({ read: async () => ROOT_A, create: async () => ROOT_A, list: async () => [] });
      w.state.reproduction = old;
      await start(w);
      expect(w.state.root).toBe(ROOT_A);
      expect(w.state.reproduction).toBeNull();
    }
  });
  it('a command clears the previous problem text when it starts (B9)', async () => {
    const w = world({ list: async () => [] });
    w.state.problem = 'F:OLD';
    await refreshList(w.ctx);
    expect(w.state.problem).toBeNull();
  });
});

describe('TR8F2 L-1: Sign out waits for running commands, and a stale command never changes the current busy state', () => {
  it('disables Sign out while a command runs', () => {
    const html = (busy: boolean) => renderToStaticMarkup(createElement(SignedInBar, { username: 'alice', busy, t, onSignOut: () => undefined }));
    expect(html(false)).not.toMatch(/disabled/);
    expect(html(true)).toMatch(/<button[^>]*disabled/);
    expect(html(true)).toContain('alice');
  });
  it('a failed logout leaves the signed-in user\'s screen and an unknown create outcome intact (no bump before the call)', async () => {
    const create = deferred<RealRoot>(); const logout = deferred<RealSession>();
    const w = world({ create: () => create.promise, logout: () => logout.promise });
    w.state.session = SESSION('alice');
    const creating = createRoot(w.ctx, { ...EMPTY_FORM, contextId: HEX('c') });
    const leaving = leaveSession(w.ctx);                                                          // (the button is disabled; this is the defence behind it)
    logout.reject(new ApiError('NETWORK_ERROR', 'x'));
    await leaving;
    const unknown = new UnknownOutcome(UUID_B, '{}');
    create.reject(unknown);
    await creating;
    expect(w.state.session).toEqual(SESSION('alice'));
    expect(w.state.uncertain).toBe(unknown);                                                      // the Repeat button stays: no second operation id
  });
  it('a stale command\'s end does not clear the busy flag of the next session\'s running command', async () => {
    const stale = deferred<RealRoot>(); const mine = deferred<RealRoot>();
    const w = world({ read: () => stale.promise, create: () => mine.promise, list: async () => [], logout: async () => SIGNED_OUT, credentials: async () => SESSION('bob') });
    const reading = readTyped(w.ctx, { rootId: UUID_A, operationId: UUID_B });
    sessionLost(w.ctx);
    expect(w.state.busy).toBe(false);                                                             // nothing of the old session is "running" on the new screen
    const creating = createRoot(w.ctx, { ...EMPTY_FORM, contextId: HEX('c') });
    expect(w.state.busy).toBe(true);
    stale.resolve(ROOT_A);
    await reading;
    expect(w.state.busy).toBe(true);                                                              // B's create is still in flight: Create stays disabled
    mine.resolve(ROOT_A);
    await creating;
    expect(w.state.busy).toBe(false);
  });
  it('busy lasts until the last of the running commands of a session ends', async () => {
    const a = deferred<RootEntry[]>(); const b = deferred<RootEntry[]>();
    const lists = [a.promise, b.promise];
    const w = world({ list: () => lists.shift()! });
    const first = refreshList(w.ctx); const second = refreshList(w.ctx);
    a.resolve([]); await first;
    expect(w.state.busy).toBe(true);
    b.resolve([]); await second;
    expect(w.state.busy).toBe(false);
  });
  it('shows a stored result only while signed in', () => {
    expect(shownRoot(ROOT_A, SESSION('alice'))).toBe(ROOT_A);
    expect(shownRoot(ROOT_A, SIGNED_OUT)).toBeNull();
    expect(shownRoot(ROOT_A, null)).toBeNull();
  });
});

describe('the late-result tests continue', () => {
  it('a lost session still shows its own news (a 401 is not dropped)', async () => {
    const w = world({ read: async () => { throw new ApiError('AUTHENTICATION_REQUIRED', 'x', 401); } });
    const opening = openStored(w.ctx, readable);
    sessionLost(w.ctx);
    await opening;
    expect(w.state.problem).toBe('F:AUTHENTICATION_REQUIRED');
  });
  it('an unknown outcome of a create keeps its command for a repeat, and the repeat sends the same body', async () => {
    const unknown = new UnknownOutcome(UUID_B, JSON.stringify({ operation_id: UUID_B }));
    const create = vi.fn().mockRejectedValueOnce(unknown).mockResolvedValueOnce(ROOT_A);
    const w = world({ create, list: async () => [] });
    await createRoot(w.ctx, { ...EMPTY_FORM, contextId: HEX('c') });
    expect(w.state.uncertain).toBe(unknown);
    await createRoot(w.ctx, EMPTY_FORM, unknown);
    expect(create.mock.calls[1][0]).toEqual({ operation_id: UUID_B });
    expect(w.state.uncertain).toBeNull();
    expect(w.state.root).toBe(ROOT_A);
  });
});

describe('DR-R8-4: typed values do not outlive a session', () => {
  const typed = (w: ReturnType<typeof world>) => {
    w.state.ids = { rootId: UUID_A, operationId: UUID_B }; w.state.form = { ...EMPTY_FORM, contextId: HEX('c'), name: 'R8 AAPL' }; w.state.ack = true;
    w.state.uncertain = new UnknownOutcome(UUID_B, '{}'); w.state.root = ROOT_A; w.state.entries = [readable]; w.state.reproduction = {} as RealReproduction;
  };
  const allCleared = (w: ReturnType<typeof world>) => {
    expect(w.state.ids).toEqual(EMPTY_IDS);
    expect(w.state.form).toEqual(EMPTY_FORM);
    expect(w.state.ack).toBe(false);
    expect(w.state.uncertain).toBeNull();
    expect(w.state.root).toBeNull();
    expect(w.state.entries).toBeNull();
    expect(w.state.reproduction).toBeNull();
  };
  it('clearTyped clears the Read form, the Create form, the acknowledgement and a kept command, with fresh copies', () => {
    const set = { ids: vi.fn(), form: vi.fn(), ack: vi.fn(), uncertain: vi.fn() };
    clearTyped(set);
    expect(set.ids).toHaveBeenCalledWith({ rootId: '', operationId: '' });
    expect(set.form.mock.calls[0][0]).toEqual({ contextId: '', releaseId: '', listingId: '', name: '', asOf: '', quantity: '', cash: '', currency: 'USD' });
    expect(set.ack).toHaveBeenCalledWith(false);
    expect(set.uncertain).toHaveBeenCalledWith(null);
    expect(set.ids.mock.calls[0][0]).not.toBe(EMPTY_IDS);
    expect(set.form.mock.calls[0][0]).not.toBe(EMPTY_FORM);
  });
  it('sign-out clears everything A typed and showed', async () => {
    const w = world({ logout: async () => SIGNED_OUT });
    typed(w);
    await leaveSession(w.ctx);
    allCleared(w);
  });
  it('session loss clears everything', () => {
    const w = world({});
    typed(w);
    sessionLost(w.ctx);
    allCleared(w);
    expect(w.state.session).toBeNull();
  });
  it('a successful sign-in of another user starts from empty forms and an empty list until their own list arrives', async () => {
    const list = deferred<RootEntry[]>();
    const w = world({ credentials: async () => SESSION('bob'), list: () => list.promise });
    typed(w);
    w.state.credentials = { username: 'bob', password: 'p'.repeat(15) };                          // what the form held when the button was pressed
    const entering = enterSession(w.ctx, 'login', { username: 'bob', password: 'p'.repeat(15) }, w.ctx.format);
    await Promise.resolve(); await Promise.resolve();
    allCleared(w);
    expect(w.state.session).toEqual(SESSION('bob'));
    expect(w.state.credentials).toEqual({ username: '', password: '' });
    list.resolve([]);
    await entering;
    expect(w.state.entries).toEqual([]);
  });
  it('a refused sign-in or sign-up clears nothing of the screen but the password, and shows the readable text with the code', async () => {
    const w = world({ credentials: async () => { throw new ApiError('INVALID_REQUEST', 'Invalid request', 422); } });
    typed(w);
    w.state.credentials = { username: 'alice', password: 'short' };
    await enterSession(w.ctx, 'register', { username: 'alice', password: 'short' }, (error) => credentialsRefusalText(error, 'en', t));
    expect(w.state.credentials).toEqual({ username: 'alice', password: '' });
    expect(w.state.problem).toBe(credentialsRefusalText(new ApiError('INVALID_REQUEST', 'x'), 'en', t));
    expect(w.state.session).toBeNull();
    expect(w.state.ids).toEqual({ rootId: UUID_A, operationId: UUID_B });                        // nobody signed in: nothing was swapped
  });
  it('withoutPassword keeps the username', () => {
    expect(withoutPassword({ username: 'alice', password: 'short' })).toEqual({ username: 'alice', password: '' });
  });
});

describe('DR-R8-3 and L-2: both sign-in rules are stated, and a refusal is readable with its code', () => {
  const auth = readFileSync(new URL('../../src/web_api/auth.py', import.meta.url), 'utf8');
  it('shows both rules under their fields, in both languages, as the server enforces them', () => {
    expect(common.en.passwordHint).toBe('At least 15 characters, at most 128 UTF-8 bytes.');
    expect(common['zh-CN'].passwordHint).toBe('至少 15 个字符，最多 128 个 UTF-8 字节。');
    expect(common.en.usernameHint).toContain('3 to 32 ASCII');
    expect(common['zh-CN'].usernameHint).toContain('3 至 32');
    const out = renderToStaticMarkup(createElement(RealModeApp));
    for (const [id, text] of [['password-hint', common.en.passwordHint], ['username-hint', common.en.usernameHint]]) {
      expect(out).toContain(`id="${id}"`); expect(out).toContain(text); expect(out).toContain(`aria-describedby="${id}"`);
    }
    // the numbers are the server's (src/web_api/auth.py)
    expect(auth).toContain('len(value) < 15');
    expect(auth).toContain('> 128');
    expect(auth).toContain('{2,31}');                                                             // first letter + 2 to 31 more = 3 to 32
    expect(auth).toContain('[a-z][a-z0-9_.-]');
    expect(auth).toContain('isascii()');
  });
  it('reads INVALID_REQUEST as BOTH rules, keeps the code, and reflects nothing of the input', () => {
    const refusal = new ApiError('INVALID_REQUEST', 'Invalid request', 422);
    expect(refusalText(refusal, 'en', t)).toBe('INVALID_REQUEST: Invalid request');
    const en = credentialsRefusalText(refusal, 'en', t);
    expect(en.startsWith('INVALID_REQUEST: ')).toBe(true);
    for (const piece of ['3 to 32 ASCII', 'starting with a letter', '15 characters', '128 UTF-8 bytes']) expect(en).toContain(piece);
    const zh = credentialsRefusalText(refusal, 'zh-CN', tz);
    expect(zh.startsWith('INVALID_REQUEST: ')).toBe(true);
    for (const piece of ['3 至 32', '以字母开头', '15 个字符', '128 个 UTF-8 字节']) expect(zh).toContain(piece);
    expect(credentialsRefusalText(new ApiError('INVALID_REQUEST', 'echo hunter2'), 'en', t)).not.toContain('hunter2');
  });
  it('leaves every other refusal as it was', () => {
    for (const code of ['INVALID_CREDENTIALS', 'NETWORK_ERROR', 'AUTHENTICATION_REQUIRED', 'RW_NOT_FOUND']) {
      const error = new ApiError(code, 'detail', 401);
      for (const [locale, tr] of [['en', t], ['zh-CN', tz]] as const) expect(credentialsRefusalText(error, locale, tr)).toBe(refusalText(error, locale, tr));
    }
    expect(credentialsRefusalText(new Error('x'), 'en', t)).toBe(common.en.invalidResponse);
  });
});
