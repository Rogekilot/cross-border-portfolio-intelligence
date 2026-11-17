import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { AccountApi } from './account';
import type { ExplanationDepth } from './ClaimDepth';
import { ApiError } from './transport';
import { errorLabel, reasonLabel } from './presentation';
import { RealReadinessLoad, type RealReadinessState } from './real-source';

export function RealSourceReadinessContent({ state, depth, onRetry, onReturn }: { state: RealReadinessState; depth: ExplanationDepth; onRetry: () => void; onReturn: () => void }) {
  const { t } = useTranslation();
  return <><div className="real-source-origins"><p>{t('realSourceMarket')}</p><p>{t('realSourceLedger')}</p></div><p>{t('realSourceScope')}</p>
    {state.kind === 'loading' ? <p role="status">{t('realSourceLoading')}</p> : state.kind === 'error' ? <div className="notice error-notice" role="alert"><strong>{t('errorTitle')}</strong><p>{errorLabel(t, state.error)}</p>{state.error instanceof ApiError && <code>{state.error.code}</code>}</div>
      : <div className="notice neutral-notice"><h2>{t('realSourceBlocked')}</h2><ul>{state.value.blockers.map((code) => <li key={code}>{reasonLabel(t, code)} <code>{code}</code></li>)}</ul>
        {state.value.contexts.length === 0 ? <p>{t('realSourceNoContexts')}</p> : <><h3>{t('realSourceConfigured')}</h3>{state.value.contexts.map((context) => <div className="real-source-context" key={context.context_id}><p>{t('realSourceMetadata')}</p><dl className="technical-details">
          <div><dt>{t('realSourceContextId')}</dt><dd className="mono">{context.context_id}</dd></div><div><dt>{t('realSourceRelease')}</dt><dd className="mono">{context.declared_release_id}</dd></div>
          {depth === 'professional' && <><div><dt>{t('realSourceConfiguration')}</dt><dd className="mono">{context.configuration_digest}</dd></div><div><dt>{t('realSourceSources')}</dt><dd>{context.declared_source_ids.join(' · ')}</dd></div></>}
        </dl></div>)}</>}
      </div>}
    <p id="real-source-disabled-reason" className="real-source-disabled-reason">{t('realSourceDisabled')}</p><div className="real-source-actions">{['realSourceCreate', 'realSourceSave', 'realSourceAnalyze'].map((label) => <button key={label} type="button" disabled aria-describedby="real-source-disabled-reason">{t(label)}</button>)}</div>
    {depth !== 'quick' && <p>{t('realSourceExplanation')}</p>}
    <div className="form-actions"><button className="primary-button" type="button" disabled={state.kind === 'loading'} onClick={onRetry}>{t('realSourceRetry')}</button><button className="text-button" type="button" onClick={onReturn}>{t('realSourceReturn')}</button></div>
    {state.kind === 'blocked' && depth === 'professional' && <details><summary>{t('realSourceDetails')}</summary><p>{t('realSourceNoEvidence')}</p><pre className="raw-packet">{JSON.stringify(state.value, null, 2)}</pre></details>}
  </>;
}

export default function RealSourceReadiness({ api, authenticated, depth, onReturn }: { api: AccountApi; authenticated: boolean; depth: ExplanationDepth; onReturn: () => void }) {
  const { t } = useTranslation(); const title = useRef<HTMLHeadingElement>(null); const loader = useRef(new RealReadinessLoad());
  const retryFocus = useRef(false);
  const [state, setState] = useState<RealReadinessState>({ kind: 'loading' });
  const read = () => { if (authenticated) { retryFocus.current = true; void loader.current.run(() => api.realSourceReadiness(), setState); } };
  useEffect(() => {
    if (authenticated) { title.current?.focus(); void loader.current.run(() => api.realSourceReadiness(), setState); }
    return () => { retryFocus.current = false; loader.current.invalidate(); };
  }, [api, authenticated]);
  useEffect(() => {
    if (authenticated && retryFocus.current && state.kind !== 'loading') { retryFocus.current = false; title.current?.focus(); }
  }, [authenticated, state]);
  return <section className="real-source-readiness card" aria-labelledby="real-source-readiness-title" aria-busy={authenticated && state.kind === 'loading'}>
    <h1 id="real-source-readiness-title" tabIndex={-1} ref={title}>{t('realSourceTitle')}</h1>
    {authenticated ? <RealSourceReadinessContent state={state} depth={depth} onRetry={read} onReturn={onReturn} /> : <p>{t('realSourceGuest')}</p>}
  </section>;
}
