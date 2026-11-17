import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { validAccountInput, type AccountSession, type SavedPortfolio } from './account';

interface Props {
  session: AccountSession | null; checking: boolean; busy: boolean; portfolios: SavedPortfolio[];
  onAuthenticate: (kind: 'register' | 'login', username: string, password: string) => Promise<void>;
  onLogout: () => void; onNewSaved: () => void; onOpen: (id: string) => void; onRefresh: () => void; onRealSourceReadiness: () => void;
}
export default function AccountPanel({ session, checking, busy, portfolios, onAuthenticate, onLogout, onNewSaved, onOpen, onRefresh, onRealSourceReadiness }: Props) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [kind, setKind] = useState<'register' | 'login'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [validation, setValidation] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setValidation(false);
    if (!validAccountInput(username, password)) { setValidation(true); return; }
    const submitted = password; setPassword('');
    await onAuthenticate(kind, username, submitted);
  }
  return <section className="account-panel" aria-label={t('account')} aria-busy={busy || checking}>
    <div className="account-summary"><div><span className="meta-label">{t('account')}</span><p role="status">{t(checking ? 'checkingAccount' : session?.authenticated ? 'signedIn' : 'signedOut', { username: session?.user?.username ?? '' })}</p></div>
      {session?.authenticated ? <div className="account-actions"><button className="text-button" type="button" disabled={busy} onClick={onNewSaved}>{t('newSavedPortfolio')}</button><button className="text-button" type="button" disabled={busy} onClick={onRealSourceReadiness}>{t('realSourceEntry')}</button><button className="text-button" type="button" disabled={busy} onClick={onLogout}>{t('signOut')}</button></div>
        : <button className="text-button" type="button" disabled={busy || checking} aria-expanded={expanded} aria-controls="account-signin" onClick={() => { setPassword(''); setExpanded(!expanded); }}>{t('signIn')}</button>}
    </div>
    {!session?.authenticated && <p className="input-help">{t('realSourceGuest')}</p>}
    {session?.authenticated ? <div className="saved-portfolios"><div className="saved-heading"><h2>{t('savedPortfolios')}</h2><button className="text-button" type="button" disabled={busy} onClick={onRefresh}>{t('refreshSaved')}</button></div>
      <p className="input-help">{t('savedNotice')}</p>{portfolios.length ? <ul>{portfolios.map((portfolio) => <li key={portfolio.portfolio_id}><button className="text-button" type="button" disabled={busy} onClick={() => onOpen(portfolio.portfolio_id)} aria-label={t('openSaved', { name: portfolio.name })}>{portfolio.name}</button><span>{portfolio.reporting_currency} · {portfolio.as_of}</span></li>)}</ul> : <p className="muted">{t('noSavedPortfolios')}</p>}</div>
      : expanded && <div id="account-signin" className="account-signin"><p className="muted">{t('accountPurpose')}</p><div className="account-tabs" role="group" aria-label={t('account')}>
        {(['login', 'register'] as const).map((mode) => <button key={mode} type="button" className="text-button" aria-pressed={kind === mode} disabled={busy} onClick={() => { setKind(mode); setPassword(''); setValidation(false); }}>{t(mode === 'login' ? 'signIn' : 'register')}</button>)}</div>
        <form onSubmit={(event) => { void submit(event); }} noValidate>
          <div className="form-row"><label htmlFor="account-username">{t('username')}</label><input id="account-username" value={username} maxLength={32} autoComplete="username" autoCapitalize="none" spellCheck={false} disabled={busy} onChange={(e) => setUsername(e.target.value)} aria-describedby="username-help"/><p className="input-help" id="username-help">{t('usernameHint')}</p></div>
          <div className="form-row"><label htmlFor="account-password">{t('password')}</label><input id="account-password" type="password" value={password} autoComplete={kind === 'register' ? 'new-password' : 'current-password'} disabled={busy} onChange={(e) => setPassword(e.target.value)} aria-describedby="password-help"/><p className="input-help" id="password-help">{t('passwordHint')}</p></div>
          {validation && <p role="alert" className="validation">{t('accountFormInvalid')}</p>}
          <button className="primary-button" type="submit" disabled={busy}>{t(busy ? 'accountWorking' : kind === 'login' ? 'signIn' : 'register')}</button>
        </form></div>}
  </section>;
}
