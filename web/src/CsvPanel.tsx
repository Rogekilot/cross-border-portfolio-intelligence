import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { AccountApi, isCancelled } from './account';
import { CSV_FIELDS, type CsvField, type CsvParse, type CsvPreview, type CsvProposal, type CsvReport, type CsvReportSummary } from './csv';
import { assertCsvEnvelope, csvFileBytes, downloadCsvArtifact } from './csv-file';
import { ApiError } from './transport';
import { errorLabel } from './presentation';
import type { Workspace, WorkspaceResult } from './workspace';
import { CurrentBalances } from './LedgerPanel';
import { csvIssueLabel } from './csv-presentation';

type Correction = { fields: Partial<Record<CsvField, string>>; reason: string };
type Classification = { classification: 'NON_DATA' | 'OUT_OF_SCOPE'; reason: string };
const fieldLabel = (t: ReturnType<typeof useTranslation>['t'], field: CsvField) => t(`csvField_${field}`, { defaultValue: t(`ledgerField_${field}`, { defaultValue: field }) });

function ImportReport({ report, onOpenRevision }: { report: CsvReport; onOpenRevision: (revision: string) => void }) {
  const { t } = useTranslation();
  return <section className={`csv-report ${report.persisted ? 'is-persisted' : 'is-preview'}`} aria-label={t(report.persisted ? 'csvSavedReport' : 'csvPreviewReport')}>
    <h3>{t(report.persisted ? 'csvSavedReport' : 'csvPreviewReport')}</h3>
    <div className="scope-strip"><strong>{t(`csvStatus_${report.status}`, { defaultValue: report.status })}</strong><span>{t(report.persisted ? 'csvReportDurable' : 'csvReportNotSaved')}</span></div>
    <dl className="csv-counts">{Object.entries(report.counts).map(([key, value]) => <div key={key}><dt>{t(`csvCount_${key}`)}</dt><dd>{value}</dd></div>)}</dl>
    {['QUARANTINED', 'BATCH_REFUSED', 'REPORT_ONLY'].includes(report.status) && <p className="notice error-notice"><strong>{t('csvWholeBatchBlocked')}</strong>{t('csvNoPartialNav')}</p>}
    {report.status === 'ALREADY_IMPORTED' && <p className="notice neutral-notice">{t('csvAlreadyImportedHint')}</p>}
    <dl className="technical-details"><div><dt>{t('csvFilename')}</dt><dd>{report.file.filename}</dd></div><div><dt>{t('csvFileIdentity')}</dt><dd className="mono">{report.file.sha256}</dd></div>
      <div><dt>{t('csvReportIdentity')}</dt><dd className="mono">{report.report_id}</dd></div><div><dt>{t('csvOperation')}</dt><dd className="mono">{report.operation_id}</dd></div>
      <div><dt>{t('csvBoundRevision')}</dt><dd className="mono">{report.expected_revision_id}</dd></div><div><dt>{t('csvResultRevision')}</dt><dd className="mono">{report.revision_id ?? t('csvNoNewRevision')}</dd></div></dl>
    {report.batch_errors.length > 0 && <><ul className="validation">{report.batch_errors.map((error, index) => <li key={index}>{csvIssueLabel(t, error.code)}</li>)}</ul>
      <details><summary>{t('commandValidationDetails')}</summary><pre className="raw-packet">{JSON.stringify(report.batch_errors, null, 2)}</pre></details></>}
    <div className="csv-report-rows">{report.rows.map((row) => <details key={row.row_number} open={row.errors.length > 0} className="csv-report-row">
      <summary>{t('csvRowNumber', { number: row.row_number })} · {t(`csvDisposition_${row.disposition}`, { defaultValue: row.disposition })} · {t('csvPhysicalLines', { start: row.physical_start, end: row.physical_end })}</summary>
      <p className="input-help">{t('csvClassification')}: {t(`csvClass_${row.classification}`, { defaultValue: row.classification })}{row.reason ? ` · ${row.reason}` : ''}</p>
      {row.errors.length > 0 && <><ul className="validation">{row.errors.map((error, index) => <li key={index}>{csvIssueLabel(t, error.code)}{error.field && error.field !== '*' ? ` · ${fieldLabel(t, error.field as CsvField)}` : ''}</li>)}</ul>
        <details><summary>{t('commandValidationDetails')}</summary><pre className="raw-packet">{JSON.stringify(row.errors, null, 2)}</pre></details></>}
      <div className="csv-original-cells"><strong>{t('csvOriginalCells')}</strong><ol>{row.cells.map((cell, index) => <li key={index}><span>{t('csvColumnIndex', { index })}</span><pre>{cell || t('csvEmptyCell')}</pre></li>)}</ol></div>
      <dl className="technical-details">{Object.entries(row.fields).map(([key, value]) => <div key={key}><dt>{fieldLabel(t, key as CsvField)}</dt><dd className="mono">{value === '' ? t('csvEmptyCell') : value}</dd></div>)}</dl>
      <p className="input-help mono">{t('csvSourceIdentity')}: {JSON.stringify(row.source_identity)} · {row.source_key ?? '—'}</p>
      {(row.event_id || row.existing_event_id) && <p className="input-help mono">{t(row.disposition === 'ALREADY_IMPORTED' || report.persisted && report.status === 'COMMITTED' ? 'csvStoredEvent' : 'csvProposedEvent')}: {row.event_id ?? row.existing_event_id}</p>}
      {row.event && <details><summary>{t('csvCanonicalEvent')}</summary><pre className="raw-packet">{JSON.stringify(row.event, null, 2)}</pre></details>}
    </details>)}</div>
    <details><summary>{t('csvAuditProposal')}</summary><pre className="raw-packet">{JSON.stringify({ ...report.proposal, file_base64: `[${t('csvBytesInLosslessExport')}]` }, null, 2)}</pre></details>
    {report.persisted && report.revision_id && <button className="text-button" type="button" onClick={() => onOpenRevision(report.revision_id!)}>{t('csvOpenImportedRevision')}</button>}
  </section>;
}

interface Props { workspace: Workspace; api: AccountApi; onUpdate: (result: WorkspaceResult) => void; onHistory: (revisionId: string) => Promise<void> }
export default function CsvPanel({ workspace, api, onUpdate, onHistory }: Props) {
  const { t } = useTranslation(); const historical = workspace.revision_id !== workspace.current_revision_id;
  const epoch = useRef(0); const mounted = useRef(true);
  const [file, setFile] = useState<{ name: string; base64: string; byteLength: number } | null>(null);
  const [kind, setKind] = useState<'' | CsvProposal['kind']>(''); const [delimiter, setDelimiter] = useState<'' | ',' | ';' | '\t'>('');
  const [dateFormat, setDateFormat] = useState<'' | 'ISO' | 'DMY' | 'MDY'>(''); const [decimal, setDecimal] = useState<'' | '.' | ','>('');
  const [thousands, setThousands] = useState(''); const [ack, setAck] = useState(false); const [asOf, setAsOf] = useState(workspace.as_of);
  const [namespace, setNamespace] = useState(''); const [sourceAccount, setSourceAccount] = useState(''); const [snapshotKey, setSnapshotKey] = useState(''); const [newAccount, setNewAccount] = useState('');
  const [parsed, setParsed] = useState<CsvParse | null>(null); const [mapping, setMapping] = useState<Partial<Record<CsvField, number>>>({});
  const [constants, setConstants] = useState<Partial<Record<CsvField, string>>>({}); const [corrections, setCorrections] = useState<Record<number, Correction>>({}); const [classifications, setClassifications] = useState<Record<number, Classification>>({});
  const [proposal, setProposal] = useState<CsvProposal | null>(null); const [preview, setPreview] = useState<CsvPreview | null>(null); const [confirmed, setConfirmed] = useState(false);
  const [report, setReport] = useState<CsvReport | null>(null); const [reports, setReports] = useState<CsvReportSummary[]>([]);
  const [reportCursor, setReportCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<unknown>(null); const [validation, setValidation] = useState(''); const [status, setStatus] = useState('');
  useEffect(() => {
    mounted.current = true; const activeEpoch = epoch.current;
    void api.csvReports(workspace.portfolio_id).then(async (page) => {
      if (!mounted.current || epoch.current !== activeEpoch) return;
      setReports(page.reports); setReportCursor(page.next_cursor);
      if (page.reports[0]) { const latest = await api.csvReport(workspace.portfolio_id, page.reports[0].report_id); if (mounted.current && epoch.current === activeEpoch) setReport(latest); }
    }).catch((failure: unknown) => { if (mounted.current && epoch.current === activeEpoch && !isCancelled(failure)) setError(failure); });
    return () => { mounted.current = false; epoch.current += 1; };
  }, [workspace.portfolio_id, api]);
  function changed(resetParse = false) {
    epoch.current += 1; setPreview(null); setProposal(null); setConfirmed(false); setError(null); setValidation(''); setStatus('');
    if (resetParse) { setParsed(null); setMapping({}); setConstants({}); setCorrections({}); setClassifications({}); setReport(null); }
  }
  async function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    changed(true); setFile(null); const selected = event.target.files?.[0]; if (!selected) return;
    const token = epoch.current; setBusy(true);
    try { const result = await csvFileBytes(selected); if (mounted.current && epoch.current === token) setFile(result); }
    catch (failure) { if (mounted.current && epoch.current === token) setError(failure); }
    finally { if (mounted.current && epoch.current === token) setBusy(false); }
  }
  async function parseFile() {
    if (!file || !kind || !delimiter || !ack) { setValidation('csvParseRequired'); return; }
    changed(true); const token = epoch.current; setBusy(true);
    try { const value = await api.parseCsv(workspace.portfolio_id, { file_base64: file.base64, filename: file.name, delimiter, synthetic_acknowledged: true });
      if (mounted.current && epoch.current === token) { setParsed(value); setStatus('csvParsed'); }
    } catch (failure) { if (mounted.current && epoch.current === token && !isCancelled(failure)) setError(failure); }
    finally { if (mounted.current && epoch.current === token) setBusy(false); }
  }
  function constantControl(field: CsvField, value: string, onChange: (value: string) => void, id: string) {
    const selects = field === 'account_id' || field === 'counterparty_account_id' ? workspace.accounts.map((account) => ({ value: account.account_id, name: account.name }))
      : field === 'listing_id' ? workspace.listings.map((listing) => ({ value: listing.listing_id, name: `${listing.symbol} · ${listing.currency}` }))
        : field === 'event_type' ? (kind === 'HOLDINGS' ? ['OPENING_POSITION', 'OPENING_CASH'] : Object.keys(workspace.ledger.field_rules).filter((type) => !['REVERSAL', 'OPENING_POSITION', 'OPENING_CASH'].includes(type))).map((type) => ({ value: type, name: t(`event_${type}`, { defaultValue: type }) })) : null;
    return selects ? <select id={id} value={value} onChange={(event) => onChange(event.target.value)} disabled={busy}><option value="">{t('chooseExplicitly')}</option>{selects.map((option) => <option value={option.value} key={option.value}>{option.name}</option>)}</select>
      : <input id={id} value={value} onChange={(event) => onChange(event.target.value)} disabled={busy} autoComplete="off" maxLength={2048} />;
  }
  function changeCorrection(rowNumber: number, field: CsvField, value: string) {
    changed(); setCorrections((existing) => ({ ...existing, [rowNumber]: { reason: existing[rowNumber]?.reason ?? '', fields: { ...existing[rowNumber]?.fields, [field]: value } } }));
  }
  async function validate() {
    setError(null); setValidation('');
    if (!file || !parsed || !kind || !delimiter || !dateFormat || !decimal || !thousands || !namespace.trim() || !asOf || !ack
      || kind === 'HOLDINGS' && (!sourceAccount.trim() || !snapshotKey.trim() || !newAccount.trim())
      || Object.values(corrections).some((correction) => Object.keys(correction.fields).length > 0 && !correction.reason.trim())
      || Object.values(classifications).some((classification) => !classification.reason.trim())) { setValidation('csvProposalRequired'); return; }
    const next: CsvProposal = proposal ?? { operation_id: crypto.randomUUID(), expected_revision_id: workspace.revision_id, file_base64: file.base64, filename: file.name,
      kind, as_of: asOf, source_namespace: namespace, source_account_key: kind === 'HOLDINGS' ? sourceAccount : null, snapshot_key: kind === 'HOLDINGS' ? snapshotKey : null, new_account_name: kind === 'HOLDINGS' ? newAccount : null,
      mapping, constants: Object.fromEntries(Object.entries(constants).filter(([field, value]) => mapping[field as CsvField] === undefined && value !== '')),
      corrections: Object.entries(corrections).filter(([, correction]) => Object.keys(correction.fields).length > 0).map(([row_number, correction]) => ({ row_number: Number(row_number), ...correction })),
      classifications: Object.entries(classifications).map(([row_number, classification]) => ({ row_number: Number(row_number), ...classification })),
      format: { delimiter, date_format: dateFormat, decimal_separator: decimal, thousands_separator: thousands === 'NONE' ? null : thousands as ',' | '.' | ' ' }, synthetic_acknowledged: true };
    const token = epoch.current; setBusy(true); setPreview(null); setConfirmed(false); setProposal(next);
    try { assertCsvEnvelope({ proposal: next, preview_receipt: '0'.repeat(64) }); const value = await api.previewCsv(workspace.portfolio_id, next);
      if (mounted.current && epoch.current === token) { setPreview(value); setStatus('csvPreviewReady'); }
    } catch (failure) { if (mounted.current && epoch.current === token && !isCancelled(failure)) setError(failure); }
    finally { if (mounted.current && epoch.current === token) setBusy(false); }
  }
  async function commit() {
    if (!proposal || !preview || !confirmed) return;
    const token = epoch.current; setBusy(true); setError(null); setStatus('');
    try { const reportOnly = api.guardedProfile !== null && preview.financial_preview === null;
      const result = await (reportOnly ? api.commitCsvReport(workspace.portfolio_id, proposal, preview.preview_receipt) : api.commitCsv(workspace.portfolio_id, proposal, preview.preview_receipt));
      // AccountApi has already rejected identity changes and mismatched proposal/
      // portfolio results. Navigation alone may unmount this local panel while
      // the authorized financial commit still needs to update the parent view.
      if (result.workspace_result) onUpdate(result.workspace_result);
      if (!mounted.current || epoch.current !== token) return;
      setReport(result.report); setPreview(null); setProposal(null); setConfirmed(false); setStatus(reportOnly ? 'guardedCsvReportCommitted' : 'csvCommitSaved');
      if (!result.workspace_result) { const page = await api.csvReports(workspace.portfolio_id); if (mounted.current && epoch.current === token) { setReports(page.reports); setReportCursor(page.next_cursor); } }
    } catch (failure) { if (mounted.current && epoch.current === token && !isCancelled(failure)) setError(failure); }
    finally { if (mounted.current && epoch.current === token) setBusy(false); }
  }
  async function openReport(id: string) {
    const token = epoch.current; setBusy(true); setError(null);
    try { const value = await api.csvReport(workspace.portfolio_id, id); if (mounted.current && epoch.current === token) setReport(value); }
    catch (failure) { if (mounted.current && epoch.current === token && !isCancelled(failure)) setError(failure); }
    finally { if (mounted.current && epoch.current === token) setBusy(false); }
  }
  async function loadReports(more: boolean) {
    const token = epoch.current; setBusy(true); setError(null);
    if (!more) setReportCursor(null);
    try { const page = await api.csvReports(workspace.portfolio_id, more ? reportCursor ?? undefined : undefined);
      if (mounted.current && epoch.current === token) {
        setReports((current) => more ? [...current, ...page.reports.filter((item) => !current.some((prior) => prior.report_id === item.report_id))] : page.reports);
        setReportCursor(page.next_cursor);
      }
    } catch (failure) { if (mounted.current && epoch.current === token && !isCancelled(failure)) setError(failure); }
    finally { if (mounted.current && epoch.current === token) setBusy(false); }
  }
  async function exportArtifact(format: 'CSV' | 'JSON', kindOrReport: 'holdings' | 'transactions' | 'report') {
    const token = epoch.current; setBusy(true); setError(null);
    try { const value = kindOrReport === 'report' && report ? await api.exportCsvReport(workspace.portfolio_id, report.report_id, format)
      : kindOrReport !== 'report' ? await api.exportPortfolio(workspace.portfolio_id, workspace.revision_id, kindOrReport, format) : null;
      if (mounted.current && epoch.current === token && value) { downloadCsvArtifact(value.content, value.filename, value.format); setStatus('csvDownloadReady'); }
    } catch (failure) { if (mounted.current && epoch.current === token && !isCancelled(failure)) setError(failure); }
    finally { if (mounted.current && epoch.current === token) setBusy(false); }
  }
  return <section className="csv-workspace" aria-labelledby="csv-title" aria-busy={busy}>
    <div className="section-heading"><div><p className="eyebrow">{t('savedNotice')}</p><h2 id="csv-title">{t('csvTitle')}</h2></div><span className="small-note">{t('csvScope')}</span></div>
    <p className="input-help" id="csv-limit-help">{t('csvLimitHelp')}</p>
    {historical ? <p className="notice neutral-notice">{t('historicalReadOnly')}</p> : <div className="card command-form csv-import-form">
      <h3>{t('csvStepSource')}</h3><div className="editor-grid">
        <div className="form-row"><label htmlFor="csv-kind">{t('csvMode')} · {t('requiredField')}</label><select id="csv-kind" value={kind} disabled={busy} onChange={(e) => { changed(true); setKind(e.target.value as '' | CsvProposal['kind']); }}><option value="">{t('chooseExplicitly')}</option><option value="HOLDINGS">{t('csvHoldings')}</option><option value="TRANSACTIONS">{t('csvTransactions')}</option></select></div>
        <div className="form-row"><label htmlFor="csv-delimiter">{t('csvDelimiter')} · {t('requiredField')}</label><select id="csv-delimiter" value={delimiter} disabled={busy} onChange={(e) => { changed(true); setDelimiter(e.target.value as typeof delimiter); }}><option value="">{t('chooseExplicitly')}</option><option value=",">{t('csvComma')}</option><option value=";">{t('csvSemicolon')}</option><option value={'\t'}>{t('csvTab')}</option></select></div>
      </div><p className="input-help">{t('csvHeaderRule')}</p>
      <label className="checkbox-label"><input id="csv-ack" type="checkbox" checked={ack} disabled={busy} onChange={(e) => { changed(); setAck(e.target.checked); }} /><span>{t('csvSyntheticAck')}</span></label>
      <div className="form-row"><label htmlFor="csv-file">{t('csvChooseFile')}</label><input id="csv-file" type="file" accept=".csv,text/csv" disabled={busy || !ack || !kind || !delimiter} onChange={(e) => { void chooseFile(e); }} aria-describedby="csv-limit-help" />
        {file && <p className="input-help">{file.name} · {file.byteLength} {t('csvBytes')}</p>}</div>
      <button className="primary-button" type="button" disabled={busy || !file || !kind || !delimiter || !ack} onClick={() => { void parseFile(); }}>{t('csvParse')}</button>
      {parsed && <><p className="input-help mono">SHA-256: {parsed.file_sha256} · BOM: {String(parsed.bom)}</p><h3 className="csv-step-heading">{t('csvStepMap')}</h3>
        <div className="editor-grid"><div className="form-row"><label htmlFor="csv-date-format">{t('csvDateFormat')}</label><select id="csv-date-format" value={dateFormat} disabled={busy} onChange={(e) => { changed(); setDateFormat(e.target.value as typeof dateFormat); }}><option value="">{t('chooseExplicitly')}</option><option value="ISO">YYYY-MM-DD</option><option value="DMY">DD/MM/YYYY</option><option value="MDY">MM/DD/YYYY</option></select></div>
          <div className="form-row"><label htmlFor="csv-decimal">{t('csvDecimalSeparator')}</label><select id="csv-decimal" value={decimal} disabled={busy} onChange={(e) => { changed(); setDecimal(e.target.value as typeof decimal); }}><option value="">{t('chooseExplicitly')}</option><option value=".">.</option><option value=",">,</option></select></div>
          <div className="form-row"><label htmlFor="csv-thousands">{t('csvThousandsSeparator')}</label><select id="csv-thousands" value={thousands} disabled={busy} onChange={(e) => { changed(); setThousands(e.target.value); }}><option value="">{t('chooseExplicitly')}</option><option value="NONE">{t('csvNoGrouping')}</option><option value=",">,</option><option value=".">.</option><option value=" ">{t('csvSpace')}</option></select></div>
          <div className="form-row"><label htmlFor="csv-as-of">{t('revisionAsOf')}</label><input id="csv-as-of" type="date" value={asOf} disabled={busy} onChange={(e) => { changed(); setAsOf(e.target.value); }} /></div>
          <div className="form-row"><label htmlFor="csv-namespace">{t('csvSourceNamespace')}</label><input id="csv-namespace" value={namespace} disabled={busy} maxLength={120} onChange={(e) => { changed(); setNamespace(e.target.value); }} autoComplete="off" /></div>
          {kind === 'HOLDINGS' && <><div className="form-row"><label htmlFor="csv-source-account">{t('csvSourceAccountKey')}</label><input id="csv-source-account" value={sourceAccount} disabled={busy} maxLength={120} onChange={(e) => { changed(); setSourceAccount(e.target.value); }} autoComplete="off" /></div>
            <div className="form-row"><label htmlFor="csv-snapshot-key">{t('csvSnapshotKey')}</label><input id="csv-snapshot-key" value={snapshotKey} disabled={busy} maxLength={120} onChange={(e) => { changed(); setSnapshotKey(e.target.value); }} autoComplete="off" /></div>
            <div className="form-row"><label htmlFor="csv-new-account">{t('csvNewAccount')}</label><input id="csv-new-account" value={newAccount} disabled={busy} maxLength={80} onChange={(e) => { changed(); setNewAccount(e.target.value); }} autoComplete="off" /></div></>}
        </div><p className="input-help">{t(kind === 'HOLDINGS' ? 'csvHoldingsBoundary' : 'csvTransactionBoundary')}</p><p className="input-help">{t('csvStableSourceKeys')}</p>
        <div className="csv-mappings">{CSV_FIELDS.filter((field) => kind !== 'HOLDINGS' || !['account_id', 'account_name', 'counterparty_account_id'].includes(field)).map((field) => <div className="csv-mapping-row" key={field}>
          <div className="form-row"><label htmlFor={`csv-map-${field}`}>{fieldLabel(t, field)}</label><select id={`csv-map-${field}`} value={mapping[field] ?? ''} disabled={busy} onChange={(event) => { changed(); const next = { ...mapping }; if (event.target.value === '') delete next[field]; else next[field] = Number(event.target.value); setMapping(next); }}>
            <option value="">{t('csvUnmapped')}</option>{parsed.columns.map((column) => <option value={column.index} key={column.index}>{t('csvColumnIndex', { index: column.index })}: {column.header || t('csvBlankHeader')}</option>)}</select></div>
          {mapping[field] === undefined && <div className="form-row"><label htmlFor={`csv-constant-${field}`}>{t('csvExplicitConstant', { field: fieldLabel(t, field) })}</label>{constantControl(field, constants[field] ?? '', (value) => { changed(); setConstants({ ...constants, [field]: value }); }, `csv-constant-${field}`)}</div>}
        </div>)}</div>
        <h3 className="csv-step-heading">{t('csvStepRows')}</h3><p className="input-help">{t('csvCorrectionHint')}</p>
        <div className="csv-source-rows">{parsed.rows.map((row) => <details className="csv-edit-row" key={row.row_number}><summary>{t('csvRowNumber', { number: row.row_number })} · {t('csvPhysicalLines', { start: row.physical_start, end: row.physical_end })}</summary>
          <div className="csv-original-cells"><strong>{t('csvOriginalCells')}</strong><ol>{row.cells.map((cell, index) => <li key={index}><span>{t('csvColumnIndex', { index })}: {parsed.columns[index]?.header ?? t('csvExtraCell')}</span><pre>{cell || t('csvEmptyCell')}</pre></li>)}</ol></div>
          <div className="form-row"><label htmlFor={`csv-row-${row.row_number}-classification`}>{t('csvClassification')}</label><select id={`csv-row-${row.row_number}-classification`} value={classifications[row.row_number]?.classification ?? 'ECONOMIC'} disabled={busy} onChange={(e) => { changed(); const next = { ...classifications }; if (e.target.value === 'ECONOMIC') delete next[row.row_number]; else next[row.row_number] = { classification: e.target.value as Classification['classification'], reason: next[row.row_number]?.reason ?? '' }; setClassifications(next); }}>
            <option value="ECONOMIC">{t('csvClass_ECONOMIC')}</option><option value="NON_DATA">{t('csvClass_NON_DATA')}</option><option value="OUT_OF_SCOPE">{t('csvClass_OUT_OF_SCOPE')}</option></select></div>
          {classifications[row.row_number] && <div className="form-row"><label htmlFor={`csv-row-${row.row_number}-classification-reason`}>{t('csvClassificationReason')}</label><input id={`csv-row-${row.row_number}-classification-reason`} value={classifications[row.row_number].reason} maxLength={500} disabled={busy} onChange={(e) => { changed(); setClassifications({ ...classifications, [row.row_number]: { ...classifications[row.row_number], reason: e.target.value } }); }} /></div>}
          <details><summary>{t('csvCorrectFields')}</summary><div className="editor-grid">{CSV_FIELDS.filter((field) => kind !== 'HOLDINGS' || !['account_id', 'account_name', 'counterparty_account_id'].includes(field)).map((field) => <div className="form-row" key={field}><label htmlFor={`csv-row-${row.row_number}-${field}`}>{fieldLabel(t, field)} · {t('csvOverride')}</label>
            {constantControl(field, corrections[row.row_number]?.fields[field] ?? '', (value) => changeCorrection(row.row_number, field, value), `csv-row-${row.row_number}-${field}`)}</div>)}</div>
            <div className="form-row"><label htmlFor={`csv-row-${row.row_number}-correction-reason`}>{t('csvCorrectionReason')}</label><input id={`csv-row-${row.row_number}-correction-reason`} value={corrections[row.row_number]?.reason ?? ''} maxLength={500} disabled={busy} onChange={(e) => { changed(); setCorrections({ ...corrections, [row.row_number]: { fields: corrections[row.row_number]?.fields ?? {}, reason: e.target.value } }); }} /></div>
            <button className="text-button" type="button" disabled={busy} onClick={() => { changed(); const next = { ...corrections }; delete next[row.row_number]; setCorrections(next); }}>{t('csvClearCorrections')}</button></details>
        </details>)}</div>
        <p className="notice neutral-notice">{t('csvNoSubsetSelection')}</p><button className="primary-button" type="button" disabled={busy || !ack} onClick={() => { void validate(); }}>{t('csvValidatePreview')}</button>
      </>}
      {preview && <div className="csv-confirmation"><ImportReport report={preview.report} onOpenRevision={() => undefined} /><p className="input-help">{t('csvReceiptBound')}</p>
        <p className="notice neutral-notice">{t(preview.financial_preview ? 'csvFinancialPreviewOnly' : 'csvZeroFinancialPreview')}</p>
        {preview.financial_preview && <CurrentBalances workspace={preview.financial_preview.workspace} />}
        <label className="checkbox-label"><input id="csv-confirm" type="checkbox" checked={confirmed} disabled={busy} onChange={(e) => setConfirmed(e.target.checked)} /><span>{t('csvConfirmExact')}</span></label>
        {api.guardedProfile && proposal?.kind === 'HOLDINGS' && preview.financial_preview === null && <p className="notice neutral-notice">{t('guardedCsvReportHoldingsUnavailable')}</p>}
        <button className="primary-button" type="button" disabled={busy || !confirmed || api.guardedProfile !== null && proposal?.kind === 'HOLDINGS' && preview.financial_preview === null} onClick={() => { void commit(); }}>{t(preview.financial_preview ? 'csvCommitFinancial' : 'csvCommitReportOnly')}</button>
        <p className="input-help">{t(api.guardedProfile && preview.financial_preview === null ? 'guardedCsvReportPendingHint' : 'idempotencyHint')}</p></div>}
    </div>}
    {validation && <p className="validation" role="alert">{t(validation)}</p>}
    <div className="csv-export-panel card command-form"><h3>{t('csvExportTitle')}</h3><p className="input-help">{t('csvExportProtection')}</p><p className="input-help">{t('csvExportFractionBoundary')}</p><code>{workspace.revision_id}</code>
      {(['holdings', 'transactions'] as const).map((item) => <div className="form-actions" key={item}><strong>{t(item === 'holdings' ? 'csvHoldingsExport' : 'csvTransactionsExport')}</strong>{(['CSV', 'JSON'] as const).map((format) => <button key={format} className="text-button" type="button" disabled={busy} onClick={() => { void exportArtifact(format, item); }}>{t('csvDownloadKind', { kind: t(item === 'holdings' ? 'csvHoldingsExport' : 'csvTransactionsExport'), format })}</button>)}</div>)}
    </div>
    <section className="csv-reports-list"><div className="saved-heading"><h3>{t('csvReportsTitle')}</h3><button className="text-button" type="button" disabled={busy} onClick={() => { void loadReports(false); }}>{t('csvRefreshReports')}</button></div>
      {reports.length ? <><p className="input-help">{t('csvLoadedReportCount', { count: reports.length })}</p><ul>{reports.map((item) => <li key={item.report_id}><button className="text-button" type="button" disabled={busy} onClick={() => { void openReport(item.report_id); }}>{t('csvOpenReport', { status: t(`csvStatus_${item.status}`, { defaultValue: item.status }), time: item.created_at })}</button><code>{item.report_id}</code></li>)}</ul></> : <p className="muted">{t('csvNoReports')}</p>}
      {reportCursor && <button className="text-button" type="button" disabled={busy} onClick={() => { void loadReports(true); }}>{t('csvLoadOlderReports')}</button>}</section>
    {report && <><ImportReport report={report} onOpenRevision={(revision) => { void onHistory(revision); }} /><div className="form-actions">{(['CSV', 'JSON'] as const).map((format) => <button className="text-button" type="button" key={format} disabled={busy} onClick={() => { void exportArtifact(format, 'report'); }}>{t('csvDownloadReport', { format })}</button>)}</div></>}
    <div role="status" aria-live="polite">{busy ? t('csvWorking') : status ? t(status) : ''}</div>
    {error !== null && <div className="notice error-notice" role="alert"><strong>{errorLabel(t, error)}</strong>{error instanceof ApiError && <details><summary>{t('commandValidationDetails')}</summary><p>{error.detail}</p><code>{error.code}</code></details>}<p>{t(api.guardedProfile ? 'guardedMutationHint' : 'csvRecoveryHint')}</p></div>}
  </section>;
}
