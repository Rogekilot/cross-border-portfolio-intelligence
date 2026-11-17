import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { isCancelled } from './account';
import { downloadCsvArtifact } from './csv-file';
import { errorLabel } from './presentation';
import { ApiError } from './transport';
import { type GuardedArchiveApi, type GuardedCommitted, type GuardedRead, type GuardedReproduction, type PendingGuardedOperation, type VerifiedGuardedArchive } from './guarded';

export type { PendingGuardedOperation } from './guarded';
interface Props {
  api: GuardedArchiveApi; reference?: GuardedRead | GuardedCommitted | null;
  pending?: PendingGuardedOperation | null; onRecovered: (result: GuardedCommitted) => void;
  onRetry?: () => Promise<void>;
}

/** This panel only reads, exports or deliberately reproduces the fixed authenticated artifact. */
export default function GuardedArchivePanel({ api, reference, pending, onRecovered, onRetry }: Props) {
  const { t } = useTranslation(); const epoch = useRef(0);
  const title = useRef<HTMLHeadingElement>(null);
  const [archive, setArchive] = useState<VerifiedGuardedArchive | null>(null);
  const [reproduction, setReproduction] = useState<GuardedReproduction | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<unknown>(null);
  const [status, setStatus] = useState('');
  const root = reference?.portfolio_id; const operation = reference?.operation_id;
  const selection = `${root ?? ''}:${operation ?? ''}:${reference?.revision_id ?? ''}:${pending?.operationId ?? ''}`;
  const currentSelection = useRef(selection); currentSelection.current = selection;
  const current = (token: number) => token === epoch.current && currentSelection.current === selection;
  useEffect(() => {
    epoch.current += 1; setArchive(null); setReproduction(null); setError(null); setBusy(false); setStatus('');
    return () => { epoch.current += 1; };
  }, [root, operation, reference?.revision_id, pending?.operationId, pending?.portfolioId, api]);
  function matchReference(value: VerifiedGuardedArchive): void {
    if (!reference || value.wire.revision_id !== reference.revision_id || value.wire.issued_sha256 !== reference.issued_sha256
      || value.wire.response_sha256 !== (reference.schema === 'finweb.guarded_read/1' ? reference.archived_response_sha256 : reference.response_sha256)
      || reference.schema === 'finweb.guarded_read/1' && value.wire.context_id !== reference.context_id) throw new ApiError('INVALID_RESPONSE', 'The selected immutable archive differs');
  }

  async function read() {
    if (!root || !operation) return;
    const token = ++epoch.current; setBusy(true); setError(null); setArchive(null); setReproduction(null); setStatus('');
    try { const value = await api.guardedArchive(root, operation); matchReference(value); if (current(token)) { setArchive(value); setStatus('guardedHashVerified'); } }
    catch (failure) { if (current(token) && !isCancelled(failure)) setError(failure); }
    finally { if (current(token)) setBusy(false); }
  }
  async function exportArchive() {
    if (!root || !operation) return;
    const token = ++epoch.current; setBusy(true); setError(null); setStatus('');
    try {
      const value = await api.guardedArchiveExport(root, operation);
      matchReference(value.archive);
      if (current(token)) { downloadCsvArtifact(value.content, value.filename, 'JSON'); setStatus('csvDownloadReady'); }
    } catch (failure) { if (current(token) && !isCancelled(failure)) setError(failure); }
    finally { if (current(token)) setBusy(false); }
  }
  async function reproduce() {
    if (!root || !operation || !archive) return;
    const token = ++epoch.current; setBusy(true); setError(null); setReproduction(null); setStatus('');
    try {
      const value = await api.guardedReproduce(root, operation, archive.wire.issued_sha256);
      if (current(token)) setReproduction(value);
    } catch (failure) { if (current(token) && !isCancelled(failure)) setError(failure); }
    finally { if (current(token)) setBusy(false); }
  }
  async function reconcile() {
    if (!pending) return;
    const token = ++epoch.current; setBusy(true); setError(null); setStatus('guardedReconciling');
    try {
      const result = await (pending.portfolioId ? api.guardedReconcile(pending.portfolioId, pending.operationId)
        : api.guardedCreationReconcile(pending.operationId));
      if (!current(token)) return;
      if (result.disposition === 'COMMITTED') { setStatus('guardedCommitted'); onRecovered(result); }
      else setStatus('guardedUnknown');
      title.current?.focus();
    } catch (failure) { if (current(token) && !isCancelled(failure)) { setError(failure); setStatus('guardedUnknown'); } }
    finally { if (current(token)) setBusy(false); }
  }
  async function retry() {
    if (!onRetry) return;
    const token = ++epoch.current; setBusy(true); setError(null);
    try { await onRetry(); } catch (failure) { if (current(token) && !isCancelled(failure)) setError(failure); }
    finally { if (current(token)) setBusy(false); }
  }
  return <section className="guarded-archive" aria-labelledby="guarded-archive-title" aria-busy={busy}>
    <h2 id="guarded-archive-title" tabIndex={-1} ref={title}>{t('guardedArchiveTitle')}</h2>
    <p>{t('guardedArchiveHint')}</p><p className="fine-print">{t('guardedHashLimit')}</p>
    {pending && <div className="notice neutral-notice guarded-pending" role="status">
      <strong>{t('guardedUnknown')}</strong><p>{t('guardedUnknownHint')}</p>
      <p>{t('guardedOperation')}: <code>{pending.operationId}</code></p><p className="fine-print">{t('guardedUnknownReload')}</p>
      <div className="form-actions"><button type="button" className="primary-button" disabled={busy} onClick={() => { void reconcile(); }}>{t('guardedReconcile')}</button>
        {onRetry && <button type="button" className="text-button" disabled={busy} onClick={() => { void retry(); }}>{t('guardedRetrySame')}</button>}</div>
    </div>}
    {root && operation ? <><p>{t('guardedOperation')}: <code>{operation}</code></p>
      <div className="form-actions"><button type="button" className="primary-button" disabled={busy} onClick={() => { void read(); }}>{t('guardedArchiveRead')}</button>
        <button type="button" className="text-button" disabled={busy} onClick={() => { void exportArchive(); }}>{t('guardedArchiveExport')}</button>
        <button type="button" className="text-button" disabled={busy || !archive} onClick={() => { void reproduce(); }}>{t('guardedReproduce')}</button></div></>
      : !pending && <p>{t('guardedArchiveEmpty')}</p>}
    {archive && <div className="guarded-archive-result">
      <p>{t('guardedHashVerified')}</p><dl className="technical-details">
        <div><dt>{t('guardedCurrentGeneration')}</dt><dd>{archive.wire.admission_generation}</dd></div>
        <div><dt>{t('guardedIssuedGeneration')}</dt><dd>{archive.issuedGeneration}</dd></div>
        <div><dt>{t('evidenceRevision')}</dt><dd><code>{archive.wire.revision_id}</code></dd></div>
        <div><dt>SHA-256</dt><dd><code>{archive.wire.issued_sha256}</code></dd></div>
      </dl>
      <ul className="guarded-issued-metrics">{archive.metrics.map((metric, index) => <li key={`${metric.metric_id}:${metric.subject.join(':')}:${index}`}>
        <code>{metric.metric_id}</code> · {metric.subject.join(' · ')} · <span className="mono">{metric.value ?? t('INSUFFICIENT_DATA')}</span>
        <span className="state-badge">{t(metric.state)}</span>{metric.reason && <code>{metric.reason}</code>}
      </li>)}</ul>
      <details><summary>{t('guardedArchiveRaw')}</summary><pre className="raw-packet">{archive.wire.issued_json}</pre><pre className="raw-packet">{archive.wire.envelope_json}</pre></details>
      <details><summary>{t('guardedArchiveResponse')}</summary><pre className="raw-packet">{archive.wire.response_json}</pre></details>
    </div>}
    {reproduction && <div className={`reproduction-result${reproduction.status === 'REPRODUCED' ? ' is-reproduced' : ''}`} role="status">
      <strong>{t(`guardedReproduction_${reproduction.status}`)}</strong><p>{reproduction.detail}</p><code>{reproduction.issued_sha256 ?? t('UNKNOWN')}</code>
    </div>}
    {error !== null && <div className="notice error-notice" role="alert"><strong>{t('guardedArchiveFailure')}</strong><p>{errorLabel(t, error)}</p></div>}
    <p role="status" aria-live="polite">{busy ? t(pending ? 'guardedReconciling' : 'guardedArchiveLoading') : status ? t(status) : ''}</p>
    <p className="fine-print">{t('guardedTrialNext')}</p>
  </section>;
}
