import { useMemo, useRef, useState, type FormEvent, type ReactElement } from 'react';
import { ApiError } from './transport';
import { claimLimitText, ClaimTextError, DEPTHS, LOCALES, type Depth, type Locale, type Slots } from './real-mode-claims';
import { common, createTranslator, realOriginZh, refusalZh, testOrigin, testOriginZh, translator, type Translate } from './real-mode-i18n';
import { isRealOrigin, keyFigures, originKind, partialBlock, RealModeApi, UnknownOutcome, type ClaimBlock, type CreateForm, type FigureRow, type Labels, type Origin,
  type RealReproduction, type RealRoot, type RealSession, type RootEntry } from './real-mode';
import { clearTyped, createRoot, EMPTY_FORM, EMPTY_IDS, enterSession, leaveSession, openEntry, openStored, readTyped, refreshList, reproduceRoot, SessionEpoch, sessionLost,
  shownRoot, withoutPassword, type Context } from './real-mode-session';

/* ---- pure presentation: props in, markup out; no request, no clock ---------------------------------------------------------------------- */

/** The origin of one root, read from its STORED fields. A real-origin root shows the real-source labels; any other origin shows the invented-data banner
 * and nothing from the real-origin table. English shows the server's own label text; Chinese shows the client's translation of the same label kind. */
export function OriginBanner({ origin, labels, locale, t }: { origin: Origin; labels: Labels; locale: Locale; t: Translate }): ReactElement {
  const kind = originKind(origin);
  if (isRealOrigin(origin)) {
    const zh = realOriginZh[kind as keyof typeof realOriginZh];
    return (
      <section className="origin-banner real-origin" data-origin-kind={kind} aria-label={t('title')}>
        <p className="origin-statement">{locale === 'en' ? labels.origin_statement : zh.origin_statement}</p>
        <p className="holding-statement">{locale === 'en' ? labels.holding_statement : zh.holding_statement}</p>
      </section>
    );
  }
  const zh = testOriginZh[kind as keyof typeof testOriginZh];
  return (
    <section className="origin-banner test-origin" data-origin-kind={kind} aria-label={testOrigin[locale].banner}>
      <p className="origin-banner-title">{testOrigin[locale].banner}</p>
      <p className="origin-statement">{locale === 'en' ? labels.origin_statement : zh.origin_statement}</p>
      <p className="holding-statement">{locale === 'en' ? labels.holding_statement : zh.holding_statement}</p>
    </section>
  );
}

/** The claim-limit block. Over a real source: S1 to S5 and C1 to C7, filled from the slots, in the chosen locale and depth. Over any other origin: the
 * invented-data mark only. A slot that cannot be filled shows an error and NO text (a caveat that cannot be filled is not softened). */
export function ClaimLimits({ block, origin, locale, depth, t }: { block: ClaimBlock; origin: Origin; locale: Locale; depth: Depth; t: Translate }): ReactElement {
  if (!isRealOrigin(origin)) {
    return (
      <section className="claim-limits invented-mark" aria-label={t('claimsHeading')}>
        <p className="invented-data-mark">{locale === 'en' ? block.invented_data_mark : testOrigin[locale].mark}</p>
      </section>
    );
  }
  let items;
  try { items = claimLimitText(block.slots as Slots, locale, depth); }
  catch (error) {
    if (!(error instanceof ClaimTextError)) throw error;
    return <section className="claim-limits" role="alert">{t('invalidResponse')}</section>;
  }
  const part = (kind: string) => items.filter((item) => item.kind === kind);
  return (
    <section className="claim-limits" aria-label={t('claimsHeading')} data-depth={depth}>
      <h2>{t('claimsHeading')}</h2>
      <h3>{t('claimsMay')}</h3>
      <ol className="claim-may">{part('MAY_CLAIM').map((item) => <li key={item.id} data-claim-id={item.id}>{item.text}</li>)}</ol>
      <h3>{t('claimsMayNot')}</h3>
      <ol className="claim-may-not">{part('MAY_NOT_CLAIM').map((item) => <li key={item.id} data-claim-id={item.id}>{item.text}</li>)}</ol>
    </section>
  );
}

/** The key figures of a stored result (PD-0079): a read-only list of the fixed figures, each row showing its label, its stored value, its state and its stored
 * reason, as stored. The client computes, rounds, formats, converts and sorts nothing. A figure in state INSUFFICIENT_DATA shows no number even if the stored row
 * has one (P5); a LIMITED figure shows its state and reason beside its value and a marker, so it cannot read as a plain one; a listed figure the result does not
 * hold shows as absent. Over a non-real origin the invented-data mark heads the list, so the figures cannot read as real. */
export function KeyFigures({ result, origin, locale, t }: { result: RealRoot['result']; origin: Origin; locale: Locale; t: Translate }): ReactElement {
  const groups = keyFigures(result);
  const real = isRealOrigin(origin);
  // PD-0080: over invented test data the stored document is a different one (it holds no valuation). When the result holds none of the listed figures, a
  // statement replaces the four lines: four "not in this result" lines could be read as four zeros. Nothing is derived from the document's other content.
  const holdsNone = groups.every((group) => group.rows.length === 0);
  const partial = partialBlock(result);
  const rowLine = (row: FigureRow, index: number) => (
    <li key={index} className="figure-row" data-figure-state={row.state}>
      {row.subject ? <code className="figure-subject">{row.subject}</code> : null}
      {row.unreadable ? <span className="figure-no-value">{t('figureUnreadable')}</span>
        : row.value !== null ? <span className="figure-value">{row.value}{row.currency ? ' ' + row.currency : ''}</span> : <span className="figure-no-value">{t('figureNoValue')}</span>}
      {' '}{t('figureState')}: <code className="figure-state">{row.state}</code>
      {row.state === 'LIMITED' ? <span className="figure-limited"> {t('figureLimited')}</span> : null}
      {row.stale_weight !== null ? <span className="figure-stale"> {t('figureStaleWeight')}: <code className="figure-stale-weight">{row.stale_weight}</code></span> : null}
      {row.stale_weight_bad ? <span className="figure-stale"> {t('figureStaleWeight')}: <span className="figure-no-value">{t('figureUnreadable')}</span></span> : null}
      {row.stale_not_stated ? <span className="figure-stale-not-stated"> {t('figureStaleNotStated')}</span> : null}
      {row.reason !== null ? <> {t('figureReason')}: <code className="figure-reason">{row.reason}</code></> : null}
      {row.details.length > 0 ? <> {t('figureDetail')}: <code className="figure-detail">{row.details.join(' ')}</code></> : null}
    </li>
  );
  const count = (label: 'figureExcludedHoldings' | 'figureExcludedComponents', stored: string | null) => (
    <p className="figure-partial-count" data-count={label}>{t(label)}: {stored !== null ? <code>{stored}</code> : <span className="figure-no-value">{t('figureUnreadable')}</span>}</p>
  );
  return (
    <section className="key-figures" aria-label={t('figuresHeading')} data-origin-kind={originKind(origin)}>
      <h3>{t('figuresHeading')}</h3>
      {!real ? <p className="figures-mark">{testOrigin[locale].mark}</p> : null}
      {!real && holdsNone ? <p className="figures-none">{testOrigin[locale].figuresNone}</p> : (
        <>
          <p className="figures-note">{real ? t('figuresNote') : testOrigin[locale].figuresNote}</p>
          <ul>
            {groups.map((group) => (
              <li key={group.id + group.view} data-figure-id={group.id} data-figure-view={group.view}>
                <strong>{t(group.label)}</strong> <code>{group.id}</code>
                {group.rows.length === 0 ? (real && group.id === 'portfolio_value' ? <p className="figure-no-nav" role="note"><strong>{t('figureNoNav')}</strong></p> : <p className="figure-absent">{t('figureAbsent')}</p>) : (
                  <ul>{group.rows.map(rowLine)}</ul>
                )}
              </li>
            ))}
          </ul>
          {partial !== null ? (
            <div className="figure-partial" data-figure-id="portfolio_value_priced_holdings">
              <strong>{t('figurePartial')}</strong> <code>portfolio_value_priced_holdings</code>
              <ul>{rowLine(partial.row, 0)}</ul>
              <p className="figure-partial-note">{t('figurePartialNotNav')}</p>
              {/* H-2: a count shows only beside a number (a split-unresolved row stores 0 and 0 with no number; those would read as "nothing is left out") */}
              {partial.row.value !== null && !partial.row.unreadable ? <>
                {count('figureExcludedHoldings', partial.excluded_holdings)}
                {count('figureExcludedComponents', partial.excluded_components)}
              </> : null}
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

export function RootEntries({ entries, locale, t, onOpen, busy }: { entries: RootEntry[]; locale: Locale; t: Translate; onOpen?: (entry: RootEntry) => void; busy: boolean }): ReactElement {
  if (entries.length === 0) return <p className="empty">{t('noRoots')}</p>;
  return (
    <>
    <p className="generation-note">{t('generationNote')}</p>
    <ul className="real-root-list">
      {entries.map((entry) => (
        <li key={entry.root_id} data-root-id={entry.root_id}>
          <code>{entry.root_id}</code> <span>{t('contextId')} <code>{entry.context_id.slice(0, 12)}</code></span>
          {entry.origin === undefined ? <span className="refused-entry"> {t('refusedEntry')}: <code>{entry.status}</code></span>
            : <span> {t('contextGenerationNow')} {entry.generation} · {t('createdAt')} {entry.created_at} · <span className="origin-tag" data-origin-kind={originKind(entry.origin)}>
              {isRealOrigin(entry.origin) ? (locale === 'en' ? 'Real source' : '真实来源') : testOrigin[locale].banner}</span></span>}
          {onOpen && entry.origin !== undefined ? <button type="button" disabled={busy} onClick={() => onOpen(entry)}>{t('openRoot')}</button> : null}
        </li>
      ))}
    </ul>
    </>
  );
}

export function RootDetail({ root, locale, depth, t, reproduction }: { root: RealRoot; locale: Locale; depth: Depth; t: Translate; reproduction?: RealReproduction | null }): ReactElement {
  return (
    <article className="real-root-detail" data-root-id={root.root_id}>
      <h2>{t('detailHeading')}</h2>
      <OriginBanner origin={root.origin} labels={root.labels} locale={locale} t={t} />
      {root.replayed ? <p className="replayed">{t('replayed')}</p> : null}
      <dl>
        <dt>{t('rootId')}</dt><dd><code>{root.root_id}</code></dd>
        <dt>{t('operation')}</dt><dd><code>{root.operation_id}</code></dd>
        <dt>{t('revision')}</dt><dd><code>{root.revision_id}</code></dd>
        <dt>{t('ledgerPin')}</dt><dd>{root.ledger_pin}</dd>
        {root.created_under_generation !== undefined ? <><dt>{t('createdUnderGeneration')}</dt><dd>{root.created_under_generation}</dd></> : null}
        <dt>{t('responseDigest')}</dt><dd><code>{root.response_sha256}</code></dd>
        <dt>{t('issuedDigest')}</dt><dd><code>{root.issued_sha256}</code></dd>
      </dl>
      <ClaimLimits block={root.claim_limits} origin={root.origin} locale={locale} depth={depth} t={t} />
      <KeyFigures result={root.result} origin={root.origin} locale={locale} t={t} />
      <p className="raw-note">{isRealOrigin(root.origin) ? t('rawNote') : testOrigin[locale].rawNote}</p>
      <details><summary>{t('resultJson')}</summary><pre className="issued-result">{JSON.stringify(root.result, null, 2)}</pre></details>
      {reproduction ? (
        <section className="reproduction" aria-label={t('reproduceHeading')}>
          <h3>{t('reproduceHeading')}</h3>
          <p>{t('reproduceStatus')}: <code>{reproduction.status}</code></p>
          {reproduction.detail ? <p>{t('reproduceDetail')}: {reproduction.detail}</p> : null}
          {reproduction.issued_sha256 ? <p><code>{reproduction.issued_sha256}</code></p> : null}
        </section>
      ) : null}
    </article>
  );
}

export function refusalText(error: unknown, locale: Locale, t: Translate): string {
  if (error instanceof ApiError) {
    if (error.code === 'NETWORK_ERROR') return t('networkError');
    if (error.code === 'INVALID_RESPONSE') return t('invalidResponse');
    if (locale !== 'en' && refusalZh[error.code]) return `${error.code}: ${refusalZh[error.code]}`;
    return error.detail ? `${error.code}: ${error.detail}` : error.code;
  }
  return t('invalidResponse');
}

/** DR-R8-3: a refused sign-in or sign-up. The server answers every validation failure with the one code `INVALID_REQUEST` and reflects nothing of the input, so the
 * page states the rule it knows (the hint under the password field says the same) and keeps the code visible as audit text. Any other refusal reads as before. */
export function credentialsRefusalText(error: unknown, locale: Locale, t: Translate): string {
  if (error instanceof ApiError && error.code === 'INVALID_REQUEST') return `${error.code}: ${t('credentialsInvalid')}`;
  return refusalText(error, locale, t);
}

/** Sign out is disabled while any command runs: an interrupted create must keep its unknown outcome (rule 0.3), and a stale command must not touch the next session. */
export function SignedInBar({ username, busy, t, onSignOut }: { username: string; busy: boolean; t: Translate; onSignOut: () => void }): ReactElement {
  return <p>{t('signedInAs')} <strong>{username}</strong> <button type="button" disabled={busy} onClick={onSignOut}>{t('signOut')}</button></p>;
}

/* The commands (open, read, refresh, create, reproduce, sign in, sign out, session loss) live in real-mode-session.ts, where their effects are tested. */
export { clearTyped, EMPTY_FORM, EMPTY_IDS, openEntry, withoutPassword };

/* ---- the app ---------------------------------------------------------------------------------------------------------------------------- */

export default function RealModeApp(): ReactElement {
  const api = useRef(new RealModeApi()).current;
  const instance = useMemo(() => createTranslator(), []);
  const [locale, setLocale] = useState<Locale>('en');
  const [depth, setDepth] = useState<Depth>('simple');
  const t = translator(locale, instance);
  const [session, setSession] = useState<RealSession | null>(null);
  const [entries, setEntries] = useState<RootEntry[] | null>(null);
  const [root, setRoot] = useState<RealRoot | null>(null);
  const [reproduction, setReproduction] = useState<RealReproduction | null>(null);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [ack, setAck] = useState(false);
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [problem, setProblem] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState<UnknownOutcome | null>(null);
  const [busy, setBusy] = useState(false);
  const [ids, setIds] = useState({ ...EMPTY_IDS });
  const epoch = useRef(new SessionEpoch()).current;
  // Every request goes through the commands of real-mode-session.ts: a result that arrives after a sign-out, a session loss or another sign-in is dropped there.
  const ctx: Context = {
    api, epoch, format: (error) => refusalText(error, locale, t),
    sinks: { busy: setBusy, problem: setProblem, session: setSession, entries: setEntries, root: setRoot, reproduction: setReproduction, ids: setIds, form: setForm, ack: setAck,
      uncertain: setUncertain, credentials: setCredentials },
  };
  api.onSessionLost = () => sessionLost(ctx);
  const shown = shownRoot(root, session);
  const refresh = () => refreshList(ctx);
  const enter = (kind: 'register' | 'login') => enterSession(ctx, kind, credentials, (error) => credentialsRefusalText(error, locale, t));
  const leave = () => leaveSession(ctx);
  const open = (event: FormEvent) => { event.preventDefault(); void readTyped(ctx, ids); };
  const openListed = (entry: RootEntry) => void openStored(ctx, entry);
  const submit = (event: FormEvent, repeat?: UnknownOutcome) => { event.preventDefault(); void createRoot(ctx, form, repeat); };
  const field = (key: keyof CreateForm, label: string) => (
    <label key={key}>{label}<input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} /></label>
  );

  return (
    <div className="real-mode-app" lang={locale}>
      <header>
        <h1>{t('brand')} <small>{t('brandSub')}</small></h1>
        <label className="language-control">{t('language')}
          <select value={locale} onChange={(e) => setLocale(e.target.value as Locale)}>
            {LOCALES.map((l) => <option key={l} value={l}>{l === 'en' ? 'English' : '简体中文'}</option>)}
          </select>
        </label>
        <div role="group" aria-label={t('depth')}>
          {DEPTHS.map((d) => <button key={d} type="button" aria-pressed={depth === d} onClick={() => setDepth(d)}>{t(d)}</button>)}
        </div>
      </header>
      <main>
        <h1 className="screen-title">{t('title')}</h1>
        {problem ? <p role="alert" className="problem"><strong>{t('errorHeading')}</strong> {problem}</p> : null}
        <section aria-label={t('authHeading')}>
          <h2>{t('authHeading')}</h2>
          {session?.authenticated ? (
            <SignedInBar username={session.user?.username ?? ''} busy={busy} t={t} onSignOut={() => void leave()} />
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); void enter('login'); }}>
              <label>{t('username')}<input value={credentials.username} onChange={(e) => setCredentials({ ...credentials, username: e.target.value })} autoComplete="username" aria-describedby="username-hint" /></label>
              <p id="username-hint" className="field-hint">{t('usernameHint')}</p>
              <label>{t('password')}<input type="password" value={credentials.password} onChange={(e) => setCredentials({ ...credentials, password: e.target.value })} autoComplete="current-password" aria-describedby="password-hint" /></label>
              <p id="password-hint" className="field-hint">{t('passwordHint')}</p>
              <button type="submit" disabled={busy}>{t('signIn')}</button>
              <button type="button" disabled={busy} onClick={() => void enter('register')}>{t('signUp')}</button>
              <p>{t('signInRequired')}</p>
            </form>
          )}
        </section>
        {session?.authenticated ? (
          <>
            <section aria-label={t('rootsHeading')}>
              <h2>{t('rootsHeading')}</h2>
              <button type="button" disabled={busy} onClick={() => void refresh()}>{t('refreshList')}</button>
              {entries ? <RootEntries entries={entries} locale={locale} t={t} onOpen={openListed} busy={busy} /> : null}
            </section>
            <section aria-label={t('readHeading')}>
              <h2>{t('readHeading')}</h2>
              <form onSubmit={open}>
                <label>{t('rootId')}<input value={ids.rootId} onChange={(e) => setIds({ ...ids, rootId: e.target.value })} /></label>
                <label>{t('fieldOperation')}<input value={ids.operationId} onChange={(e) => setIds({ ...ids, operationId: e.target.value })} /></label>
                <button type="submit" disabled={busy}>{t('readStored')}</button>
              </form>
            </section>
            <section aria-label={t('createHeading')}>
              <h2>{t('createHeading')}</h2>
              <p>{t('createHint')}</p>
              <form onSubmit={(e) => submit(e)}>
                {field('contextId', t('fieldContext'))}{field('releaseId', t('fieldRelease'))}{field('listingId', t('fieldListing'))}
                {field('name', t('fieldName'))}{field('asOf', t('fieldAsOf'))}{field('quantity', t('fieldQuantity'))}
                {field('cash', t('fieldCash'))}{field('currency', t('fieldCurrency'))}
                <label><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />{t('fieldAck')}</label>
                <button type="submit" disabled={busy || !ack}>{busy ? t('creating') : t('create')}</button>
              </form>
              {uncertain ? (
                <p role="alert" className="unknown-outcome">{t('unknownOutcome')} <button type="button" onClick={(e) => submit(e, uncertain)}>{t('repeatCommand')}</button></p>
              ) : null}
            </section>
          </>
        ) : null}
        {shown ? (
          <>
            <RootDetail root={shown}locale={locale} depth={depth} t={t} reproduction={reproduction} />
            <button type="button" disabled={busy} onClick={() => void reproduceRoot(ctx, shown)}>
              {busy ? t('reproducing') : t('reproduce')}
            </button>
          </>
        ) : null}
      </main>
    </div>
  );
}

export { common };
