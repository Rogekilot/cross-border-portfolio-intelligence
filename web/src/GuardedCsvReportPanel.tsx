import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { isCancelled } from './account';
import { downloadCsvArtifact } from './csv-file';
import { errorLabel } from './presentation';
import { ApiError } from './transport';
import type { PendingGuardedOperation } from './guarded';
import type { GuardedCsvReportApi, GuardedCsvReportCommitted, GuardedCsvReportReference, VerifiedGuardedCsvReportArchive } from './guarded-csv-report';

interface Props {
  api: GuardedCsvReportApi; reference?: GuardedCsvReportReference | null; pending?: PendingGuardedOperation | null;
  onRecovered: (result: GuardedCsvReportCommitted) => void; onRetry?: () => Promise<void>;
}
/** Report audit evidence is distinct from a financial answer and cannot reproduce CP5. */
export default function GuardedCsvReportPanel({ api, reference, pending, onRecovered, onRetry }: Props) {
  const { t } = useTranslation(); const epoch = useRef(0); const heading = useRef<HTMLHeadingElement>(null);
  const [archive, setArchive] = useState<VerifiedGuardedCsvReportArchive | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<unknown>(null); const [status, setStatus] = useState('');
  const selection = `${reference?.portfolio_id ?? ''}:${reference?.operation_id ?? ''}:${reference?.report_id ?? ''}:${pending?.operationId ?? ''}`;
  const selected = useRef(selection); selected.current = selection;
  const current = (token: number) => token === epoch.current && selected.current === selection;
  useEffect(() => {
    epoch.current += 1; setArchive(null); setError(null); setBusy(false); setStatus('');
    return () => { epoch.current += 1; };
  }, [selection, api]);
  function matches(value: VerifiedGuardedCsvReportArchive) {
    if (!reference || value.wire.portfolio_id !== reference.portfolio_id || value.wire.operation_id !== reference.operation_id
      || value.wire.report_id !== reference.report_id || value.wire.base_revision_id !== reference.base_revision_id
      || value.wire.response_sha256 !== reference.response_sha256
      || reference.schema === 'finweb.guarded_csv_report_read/1' && value.wire.context_id !== reference.context_id) throw new ApiError('INVALID_RESPONSE', 'The selected report archive differs');
  }
  async function read() {
    if (!reference) return;
    const token = ++epoch.current; setBusy(true); setError(null); setArchive(null); setStatus('');
    try { const result = await api.guardedCsvReportArchive(reference.portfolio_id, reference.operation_id); matches(result);
      if (current(token)) { setArchive(result); setStatus('guardedHashVerified'); } }
    catch (failure) { if (current(token) && !isCancelled(failure)) setError(failure); }
    finally { if (current(token)) setBusy(false); }
  }
  async function download() {
    if (!reference) return;
    const token = ++epoch.current; setBusy(true); setError(null); setStatus('');
    try { const result = await api.guardedCsvReportArchiveExport(reference.portfolio_id, reference.operation_id); matches(result.archive);
      if (current(token)) { downloadCsvArtifact(result.content, result.filename, 'JSON'); setStatus('csvDownloadReady'); } }
    catch (failure) { if (current(token) && !isCancelled(failure)) setError(failure); }
    finally { if (current(token)) setBusy(false); }
  }
  async function reconcile() {
    if (pending?.kind !== 'CSV_REPORT' || !pending.portfolioId) return;
    const token = ++epoch.current; setBusy(true); setError(null); setStatus('guardedReconciling');
    try { const result = await api.guardedCsvReportReconcile(pending.portfolioId, pending.operationId);
      if (!current(token)) return;
      if (result.disposition === 'REPORT_COMMITTED') { setStatus('guardedCsvReportCommitted'); onRecovered(result); }
      else setStatus('guardedUnknown'); heading.current?.focus(); }
    catch (failure) { if (current(token) && !isCancelled(failure)) { setError(failure); setStatus('guardedUnknown'); } }
    finally { if (current(token)) setBusy(false); }
  }
  async function retry() {
    if (!onRetry) return;
    const token = ++epoch.current; setBusy(true); setError(null);
    try { await onRetry(); }
    catch (failure) { if (current(token) && !isCancelled(failure)) setError(failure); }
    finally { if (current(token)) setBusy(false); }
  }
  return <section className="guarded-csv-report card" aria-labelledby="guarded-csv-report-title" aria-busy={busy}>
    <h2 id="guarded-csv-report-title" tabIndex={-1} ref={heading}>{t('guardedCsvReportTitle')}</h2>
    <p>{t('guardedCsvReportHint')}</p><p className="fine-print">{t('guardedHashLimit')}</p>
    {pending?.kind === 'CSV_REPORT' && <div className="notice neutral-notice guarded-report-pending" role="status">
      <strong>{t('guardedUnknown')}</strong><p>{t('guardedCsvReportUnknownHint')}</p>
      <p>{t('guardedOperation')}: <code>{pending.operationId}</code></p><p className="fine-print">{t('guardedUnknownReload')}</p>
      <div className="form-actions"><button className="primary-button" type="button" disabled={busy} onClick={() => { void reconcile(); }}>{t('guardedReconcile')}</button>
        {onRetry && <button className="text-button" type="button" disabled={busy} onClick={() => { void retry(); }}>{t('guardedRetrySame')}</button>}</div>
    </div>}
    {reference && <><p>{t('guardedOperation')}: <code>{reference.operation_id}</code></p>
      <p>{t('csvReportIdentity')}: <code>{reference.report_id}</code></p><p>{t('guardedCsvReportBaseline')}: <code>{reference.base_revision_id}</code></p>
      <p className="notice neutral-notice">{t('guardedCsvReportCommitted')}</p>
      <div className="form-actions"><button className="primary-button" type="button" disabled={busy} onClick={() => { void read(); }}>{t('guardedCsvReportRead')}</button>
        <button className="text-button" type="button" disabled={busy} onClick={() => { void download(); }}>{t('guardedCsvReportExport')}</button></div></>}
    {archive && <div className="guarded-report-archive-result">
      <p>{t('guardedHashVerified')}</p><p>{t(`csvStatus_${archive.report.status}`)}</p>
      <dl className="technical-details"><div><dt>{t('guardedCurrentGeneration')}</dt><dd>{archive.wire.admission_generation}</dd></div>
        <div><dt>{t('guardedCsvReportCommitGeneration')}</dt><dd>{archive.wire.commit_generation}</dd></div>
        <div><dt>SHA-256</dt><dd><code>{archive.wire.response_sha256}</code></dd></div></dl>
      <dl className="csv-counts">{Object.entries(archive.report.counts).map(([name, value]) => <div key={name}><dt>{t(`csvCount_${name}`)}</dt><dd>{value}</dd></div>)}</dl>
      {archive.report.rows.filter((row) => row.disposition === 'ALREADY_IMPORTED').map((row) => <p key={row.row_number}>{t('csvStoredEvent')}: <code>{row.existing_event_id}</code></p>)}
      <details><summary>{t('guardedCsvReportRaw')}</summary><pre className="raw-packet">{archive.wire.response_json}</pre><pre className="raw-packet">{archive.wire.envelope_json}</pre></details>
    </div>}
    {error !== null && <div className="notice error-notice" role="alert"><strong>{t('guardedCsvReportFailure')}</strong><p>{errorLabel(t, error)}</p></div>}
    <p role="status" aria-live="polite">{busy ? t('guardedReconciling') : status ? t(status) : ''}</p>
  </section>;
}
