import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AccountApi, isCancelled } from './account';
import type { AnalyticsEvidence, AnalyticsQuestion, AnalyticsReproduction, AnalyticsResult } from './analytics';
import { errorLabel } from './presentation';

export interface AnalyticalSelection { portfolioId: string; question: AnalyticsQuestion; result: AnalyticsResult }
export default function AnalyticalEvidenceDialog({ selection, api, onClose }: { selection: AnalyticalSelection; api: AccountApi; onClose: () => void }) {
  const { t } = useTranslation(); const dialog = useRef<HTMLDialogElement>(null); const active = useRef(true);
  const opener = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null);
  const [evidence, setEvidence] = useState<AnalyticsEvidence | null>(null); const [error, setError] = useState<unknown>(null);
  const [reproduction, setReproduction] = useState<AnalyticsReproduction | null>(null); const [busy, setBusy] = useState(false);
  useEffect(() => {
    active.current = true; const element = dialog.current; element?.showModal();
    void api.analyticalEvidence(selection.portfolioId, selection.question, selection.result).then((value) => { if (active.current) setEvidence(value); })
      .catch((failure: unknown) => { if (active.current && !isCancelled(failure)) setError(failure); });
    return () => { active.current = false; element?.close(); queueMicrotask(() => { if (!element?.isConnected && opener.current?.isConnected) opener.current.focus(); }); };
  }, [api, selection]);
  async function reproduce() {
    setBusy(true); setError(null); setReproduction(null);
    try { const value = await api.reproduceAnalytics(selection.portfolioId, selection.question, selection.result); if (active.current) setReproduction(value); }
    catch (failure) { if (active.current && !isCancelled(failure)) setError(failure); }
    finally { if (active.current) setBusy(false); }
  }
  return <dialog ref={dialog} className="evidence-dialog analytical-evidence" aria-labelledby="analytical-evidence-title" onCancel={onClose}>
    <div className="dialog-heading"><div><p className="eyebrow">{t('banner')}</p><h2 id="analytical-evidence-title">{t('analyticsEvidenceTitle')}</h2></div><button className="close-button" type="button" aria-label={t('closeEvidence')} onClick={onClose}>×</button></div>
    <div className="dialog-body"><div className="scope-strip"><strong>{t(`analyticsFamily_${selection.result.family}`)}</strong><span>{t(`analyticsGroup_${selection.result.group}`)}</span><code>{selection.question.revision_id}</code></div>
      {error !== null && <p className="notice error-notice" role="alert">{errorLabel(t, error)}</p>}
      {!evidence && error === null && <p role="status">{t('analyticsEvidenceLoading')}</p>}
      {evidence && <><p className="input-help">{t('analyticsNotArchived')}</p><dl className="technical-details"><div><dt>{t('analyticsSource')}</dt><dd className="mono">{evidence.result.engine_result.manifest_id}</dd></div><div><dt>{t('resultDigest')}</dt><dd className="mono">{evidence.result.engine_result.result_digest}</dd></div><div><dt>{t('analyticsQuestion')}</dt><dd className="mono">{JSON.stringify(evidence.question)}</dd></div><div><dt>{t('analyticsContext')}</dt><dd className="mono">{JSON.stringify(evidence.ledger_reference)}</dd></div></dl>
        <section className="reproduction-panel"><h3>{t('reproducibility')}</h3><p>{t('analyticsReproductionNote')}</p><button className="primary-button" type="button" disabled={busy} onClick={() => { void reproduce(); }}>{t(busy ? 'analyticsReproducing' : 'analyticsReproduce')}</button>
          {reproduction && <div className={`reproduction-result ${reproduction.status === 'REPRODUCED' ? 'is-reproduced' : ''}`} role="status"><strong>{t(reproduction.status, { defaultValue: reproduction.status })}</strong><code>{reproduction.rerun_result_digest ?? t('UNKNOWN')}</code><details><summary>{t('commandValidationDetails')}</summary><pre className="raw-packet">{JSON.stringify(reproduction, null, 2)}</pre></details></div>}</section>
        <h3>{t('analyticsRaw')}</h3><pre className="raw-packet">{JSON.stringify(evidence, null, 2)}</pre></>}
    </div>
  </dialog>;
}
