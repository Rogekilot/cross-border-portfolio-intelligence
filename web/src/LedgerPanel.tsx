import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { AccountApi, isCancelled } from './account';
import { errorLabel, metricLabel, reasonLabel } from './presentation';
import { ApiError, type Snapshot } from './transport';
import type { FieldRule, LedgerCommand, LedgerInput, LedgerRow, Workspace, WorkspaceResult } from './workspace';

type Draft = Record<string, string>;
const userFields = ['listing_id', 'quantity', 'amount', 'cost_basis', 'bought_amount', 'split_ratio', 'counterparty_account_id', 'settlement_date', 'ex_date', 'acquired_on'];
export function eventDraft(row?: LedgerRow, accountId = '', asOf = ''): Draft {
  const draft: Draft = { event_type: 'DEPOSIT', account_id: accountId, event_date: '', currency: '', bought_currency: '', split_new_units: '', split_old_units: '' };
  if (!row) return { ...draft, event_date: asOf };
  for (const key of ['event_type', 'account_id', 'event_date', 'currency', ...userFields]) {
    const value = row[key as keyof LedgerRow]; if (typeof value === 'string') draft[key] = value;
  }
  if (row.bought_amount) { draft.bought_amount = row.bought_amount.amount; draft.bought_currency = row.bought_amount.currency; }
  if (row.split_ratio) { draft.split_new_units = row.split_ratio.new_units; draft.split_old_units = row.split_ratio.old_units; }
  return draft;
}
export function eventInput(draft: Draft, rules: Record<string, FieldRule>): LedgerInput {
  const input: LedgerInput = { account_id: draft.account_id, event_type: draft.event_type, event_date: draft.event_date, currency: draft.currency };
  for (const field of userFields) {
    if (rules[field] === 'FORBIDDEN' || !rules[field]) continue;
    if (field === 'bought_amount') {
      if (draft.bought_amount || draft.bought_currency) input.bought_amount = { amount: draft.bought_amount ?? '', currency: draft.bought_currency ?? '' };
    } else if (field === 'split_ratio') {
      if (draft.split_new_units || draft.split_old_units) input.split_ratio = { new_units: draft.split_new_units ?? '', old_units: draft.split_old_units ?? '' };
    } else if (draft[field]) (input as unknown as Record<string, string>)[field] = draft[field];
  }
  return input;
}

export function CurrentBalances({ workspace }: { workspace: Workspace }) {
  const { t } = useTranslation();
  const accountName = (id: string) => workspace.accounts.find((a) => a.account_id === id)?.name ?? id;
  const listingName = (id: string) => workspace.listings.find((l) => l.listing_id === id)?.symbol ?? id;
  return <section className="native-balances" aria-label={t('nativeBalances')}>
    <h3>{t('nativeBalances')}</h3><p className="input-help">{t('nativeBalanceHint')}</p>
    {workspace.ledger.current_state.accounts.map((account) => <div className="native-account" key={account.account_id}>
      <h4>{accountName(account.account_id)} <span className="state-badge">{t(`ledgerState_${account.status}`, { defaultValue: account.status })}</span></h4>
      {account.positions.length > 0 && <ul>{account.positions.map((position) => <li key={position.listing_id}>
        <strong>{listingName(position.listing_id)}</strong> · {t('quantity')}: <span className="mono">{position.quantity.value ?? t('INSUFFICIENT_DATA')}</span>
        <span className="state-badge">{t(position.quantity.state, { defaultValue: position.quantity.state })}</span>
        {position.quantity.reason && <span>{reasonLabel(t, position.quantity.reason)} <code>{position.quantity.reason}</code></span>}
        {position.quantity.detail.length > 0 && <span className="input-help">{position.quantity.detail.join(' · ')}</span>}
      </li>)}</ul>}
      <ul>{account.cash.map((cash) => <li key={cash.currency}><strong>{t('cash')} · {cash.currency}</strong> <span className="mono">{cash.amount}</span></li>)}</ul>
      {account.unrepresentable_cash.length > 0 && <p className="validation">{t('INSUFFICIENT_DATA')}: {account.unrepresentable_cash.join(', ')}</p>}
      {account.positions.length === 0 && account.cash.length === 0 && <p className="muted">{t('noNativeEvents')}</p>}
    </div>)}
    <p className="fine-print mono">{workspace.ledger.current_state.convention_set} · {t('asOf')} {workspace.ledger.current_state.as_of} · {t('ledgerVersion')} {workspace.ledger.current_state.ledger_version}</p>
  </section>;
}

function EventEditor({ draft, index, workspace, disabled, onChange }: { draft: Draft; index: number; workspace: Workspace; disabled: boolean; onChange: (key: string, value: string) => void }) {
  const { t } = useTranslation(); const rules = workspace.ledger.field_rules[draft.event_type] ?? {};
  const id = (field: string) => `ledger-event-${index}-${field}`;
  const input = (field: string, required = false) => <div className="form-row" key={field}>
    <label htmlFor={id(field)}>{t(`ledgerField_${field}`, { defaultValue: field })}{required ? ` · ${t('requiredField')}` : ` · ${t('optionalField')}`}</label>
    {field === 'listing_id' ? <select id={id(field)} value={draft[field] ?? ''} onChange={(e) => onChange(field, e.target.value)} disabled={disabled}>
      <option value="">{t('chooseExplicitly')}</option>{workspace.listings.map((listing) => <option key={listing.listing_id} value={listing.listing_id}>{listing.symbol} · {listing.currency}</option>)}</select>
      : field === 'counterparty_account_id' ? <select id={id(field)} value={draft[field] ?? ''} onChange={(e) => onChange(field, e.target.value)} disabled={disabled}>
        <option value="">{t('externalTransfer')}</option>{workspace.accounts.filter((a) => a.account_id !== draft.account_id).map((a) => <option key={a.account_id} value={a.account_id}>{a.name}</option>)}</select>
        : <input id={id(field)} type={['settlement_date', 'ex_date', 'acquired_on'].includes(field) ? 'date' : 'text'}
          inputMode={['quantity', 'amount', 'cost_basis', 'bought_amount', 'split_new_units', 'split_old_units'].includes(field) ? 'decimal' : undefined}
          maxLength={field === 'bought_currency' ? 3 : undefined} autoComplete="off" value={draft[field] ?? ''} disabled={disabled}
          onChange={(e) => onChange(field, e.target.value)} aria-describedby="ledger-decimal-help" />}
  </div>;
  return <fieldset className="ledger-event-editor" disabled={disabled}><legend>{t('eventNumber', { count: index + 1 })}</legend>
    <div className="editor-grid"><div className="form-row"><label htmlFor={id('event_type')}>{t('ledgerField_event_type')} · {t('requiredField')}</label>
      <select id={id('event_type')} value={draft.event_type} onChange={(e) => onChange('event_type', e.target.value)}>
        {Object.keys(workspace.ledger.field_rules).filter((type) => type !== 'REVERSAL').map((type) => <option key={type} value={type}>{t(`event_${type}`, { defaultValue: type })} · {type}</option>)}</select></div>
      <div className="form-row"><label htmlFor={id('account_id')}>{t('ledgerField_account_id')} · {t('requiredField')}</label><select id={id('account_id')} value={draft.account_id} onChange={(e) => onChange('account_id', e.target.value)}>
        <option value="">{t('chooseExplicitly')}</option>{workspace.accounts.map((account) => <option key={account.account_id} value={account.account_id}>{account.name}</option>)}</select></div>
      <div className="form-row"><label htmlFor={id('event_date')}>{t('ledgerField_event_date')} · {t('requiredField')}</label><input id={id('event_date')} type="date" value={draft.event_date} onChange={(e) => onChange('event_date', e.target.value)} /></div>
      <div className="form-row"><label htmlFor={id('currency')}>{t('ledgerField_currency')} · {t('requiredField')}</label><input id={id('currency')} maxLength={3} value={draft.currency} onChange={(e) => onChange('currency', e.target.value)} autoComplete="off" aria-describedby="ledger-currency-help" /></div>
      {userFields.filter((field) => rules[field] && rules[field] !== 'FORBIDDEN').flatMap((field) => field === 'split_ratio'
        ? [input('split_new_units', true), input('split_old_units', true)] : field === 'bought_amount'
          ? [input('bought_amount', true), input('bought_currency', true)] : [input(field, rules[field] === 'REQUIRED')])}
    </div>
  </fieldset>;
}

function PreviewSummary({ result }: { result: WorkspaceResult }) {
  const { t } = useTranslation(); const snapshot: Snapshot = result.snapshot;
  return <section className="command-preview" aria-label={t('ledgerPreview')}>
    <h3>{t('ledgerPreview')}</h3><p>{t('previewNotSaved')}</p><CurrentBalances workspace={result.workspace} />
    <div className="preview-metrics">{snapshot.valuation.metrics.filter((metric) => metric.metric_id === 'portfolio_value').map((metric, index) => <p key={index}>
      <strong>{metricLabel(t, metric.metric_id)}</strong> <span className="mono">{metric.value ?? t('INSUFFICIENT_DATA')}</span> {metric.currency}
      <span className={`state-badge state-${metric.state.toLowerCase()}`}>{t(metric.state)}</span>
      {metric.reason && <span>{reasonLabel(t, metric.reason)} <code>{metric.reason}</code></span>}
      {metric.details.map((detail) => <span className="input-help" key={detail}>{detail}</span>)}
    </p>)}</div><p className="fine-print">{t('syntheticCalendarBoundary')}</p>
  </section>;
}

interface Props { workspace: Workspace; api: AccountApi; onUpdate: (result: WorkspaceResult) => void; onHistory: (revisionId: string) => Promise<void> }
export default function LedgerPanel({ workspace, api, onUpdate, onHistory }: Props) {
  const { t } = useTranslation(); const historical = workspace.revision_id !== workspace.current_revision_id;
  const [operation, setOperation] = useState<LedgerCommand['operation']>('APPEND');
  const [drafts, setDrafts] = useState<Draft[]>([eventDraft(undefined, workspace.accounts[0]?.account_id ?? '', workspace.as_of)]);
  const [selected, setSelected] = useState<string[]>([]); const [targets, setTargets] = useState<string[]>([]);
  const [asOf, setAsOf] = useState(workspace.as_of); const [accountName, setAccountName] = useState('');
  const [command, setCommand] = useState<LedgerCommand | null>(null); const [preview, setPreview] = useState<WorkspaceResult | null>(null);
  const [confirmed, setConfirmed] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState<unknown>(null);
  const [validation, setValidation] = useState(''); const [status, setStatus] = useState('');
  function changed() { setCommand(null); setPreview(null); setConfirmed(false); setError(null); setValidation(''); setStatus(''); }
  function edit(index: number, field: string, value: string) {
    changed(); setDrafts((current) => current.map((draft, at) => at !== index ? draft : field === 'event_type'
      ? { ...eventDraft(undefined, draft.account_id, draft.event_date), currency: draft.currency, event_type: value }
      : { ...draft, [field]: value }));
  }
  function chooseOperation(next: LedgerCommand['operation']) {
    changed(); setOperation(next); setTargets(next === 'CORRECT' || next === 'REVERSE' ? selected : []);
    setDrafts(next === 'CORRECT' ? selected.map((id) => eventDraft(workspace.ledger.events.find((event) => event.event_id === id)))
      : [eventDraft(undefined, workspace.accounts[0]?.account_id ?? '', workspace.as_of)]);
  }
  async function makePreview(event: FormEvent) {
    event.preventDefault(); setError(null); setValidation(''); setStatus(''); setPreview(null); setConfirmed(false);
    if (!asOf || (operation === 'ADD_ACCOUNT' ? !accountName.trim() : operation === 'REVERSE' ? targets.length === 0
      : drafts.length === 0 || drafts.some((draft) => !draft.account_id || !draft.event_type || !draft.event_date || !/^[A-Z]{3}$/.test(draft.currency)))) {
      setValidation('ledgerFormInvalid'); return;
    }
    const next: LedgerCommand = command ?? { operation_id: crypto.randomUUID(), expected_revision_id: workspace.revision_id,
      operation, as_of: asOf, events: operation === 'REVERSE' || operation === 'ADD_ACCOUNT' ? [] : drafts.map((draft) => eventInput(draft, workspace.ledger.field_rules[draft.event_type] ?? {})),
      target_event_ids: targets, ...(operation === 'ADD_ACCOUNT' ? { account_name: accountName.trim() } : {}) };
    setCommand(next); setBusy(true);
    try { setPreview(await api.ledgerCommand(workspace.portfolio_id, next, true)); setStatus('previewReady'); }
    catch (failure) { if (!isCancelled(failure)) setError(failure); } finally { setBusy(false); }
  }
  async function commit() {
    if (!command || !preview || !confirmed) return;
    setBusy(true); setError(null); setStatus('');
    try { const result = await api.ledgerCommand(workspace.portfolio_id, command); onUpdate(result); }
    catch (failure) { if (!isCancelled(failure)) setError(failure); } finally { setBusy(false); }
  }
  const accountLabel = (id: string) => workspace.accounts.find((a) => a.account_id === id)?.name ?? id;
  const listingLabel = (id?: string) => workspace.listings.find((listing) => listing.listing_id === id)?.symbol ?? id;
  return <section className="ledger-workspace" aria-labelledby="ledger-title" aria-busy={busy}>
    <div className="section-heading"><div><p className="eyebrow">{t('savedNotice')}</p><h2 id="ledger-title">{t('ledgerTitle')}</h2></div><span className="small-note">{t('ledgerImmutable')}</span></div>
    <CurrentBalances workspace={workspace} />
    <div className="revision-strip"><strong>{t(historical ? 'historicalRevision' : 'currentRevision')}</strong><code>{workspace.revision_id}</code>
      {historical && <button className="text-button" type="button" disabled={busy} onClick={() => { void onHistory(workspace.current_revision_id); }}>{t('openLatestRevision')}</button>}</div>
    <details className="revision-history"><summary>{t('revisionHistory')}</summary><ol>{workspace.history.map((revision) => <li key={revision.revision_id}>
      <span>{t(`operation_${revision.operation}`, { defaultValue: revision.operation })} · {revision.created_at}</span><code>{revision.revision_id}</code>
      <button className="text-button" type="button" disabled={busy || revision.revision_id === workspace.revision_id} onClick={() => { void onHistory(revision.revision_id); }}>{t('openRevisionEvidence')}</button>
    </li>)}</ol></details>
    <section className="card table-card"><p className="table-scroll-hint">{t('scrollTable')} {t('rawLedgerHint')}</p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label={t('ledgerHistory')}><table className="ledger-table"><caption>{t('ledgerHistory')} · {t('ledgerVersion')} {workspace.ledger.version}</caption>
        <thead><tr><th scope="col">{t('selectEvent')}</th><th scope="col">{t('ledgerField_event_date')}</th><th scope="col">{t('ledgerField_account_id')}</th><th scope="col">{t('ledgerField_event_type')}</th><th scope="col">{t('security')}</th><th scope="col">{t('nativeSourceFacts')}</th><th scope="col">{t('auditStatus')}</th></tr></thead>
        <tbody>{[...workspace.ledger.events].sort((left, right) => accountLabel(left.account_id).localeCompare(accountLabel(right.account_id))
          || left.event_date.localeCompare(right.event_date) || (left.ledger_seq < right.ledger_seq ? -1 : left.ledger_seq > right.ledger_seq ? 1 : 0)).map((event) => <tr key={event.event_id}><td><input type="checkbox" aria-label={t('selectEventId', { id: event.event_id })} checked={selected.includes(event.event_id)} disabled={busy || historical || event.event_type === 'REVERSAL' || event.reversed_by !== null}
          onChange={(e) => setSelected(e.target.checked ? [...selected, event.event_id] : selected.filter((id) => id !== event.event_id))} /></td>
          <td>{event.event_date}</td><td>{accountLabel(event.account_id)}</td><td>{t(`event_${event.event_type}`, { defaultValue: event.event_type })}<code>{event.event_type}</code></td>
          <td>{listingLabel(event.listing_id) ?? '—'}</td><td>
            {event.quantity != null && <span>{t('quantity')}: <span className="mono">{event.quantity}</span></span>}
            {event.amount != null && <span>{t('ledgerField_amount')}: <span className="mono">{event.amount} {event.currency}</span></span>}
            {event.cost_basis != null && <span>{t('ledgerField_cost_basis')}: <span className="mono">{event.cost_basis} {event.currency}</span></span>}
            {event.bought_amount && <span>{t('ledgerField_bought_amount')}: <span className="mono">{event.bought_amount.amount} {event.bought_amount.currency}</span></span>}
            {event.split_ratio && <span>{t('event_SPLIT')}: <span className="mono">{event.split_ratio.new_units}:{event.split_ratio.old_units}</span></span>}
            <details><summary>{t('rawEventFields')}</summary><pre className="raw-packet">{JSON.stringify(event, null, 2)}</pre></details></td>
          <td>{t(event.event_type === 'REVERSAL' ? 'reversalRecord' : event.reversed_by ? 'reversedRecord' : 'liveRecord')}<code>{event.event_id}</code>
            {event.corrects_event_id && <span>{t('correctsEvent')} <code>{event.corrects_event_id}</code></span>}
            {event.reverses_event_id && <span>{t('reversesEvent')} <code>{event.reverses_event_id}</code></span>}
            {event.reversed_by && <span>{t('reversedBy')} <code>{event.reversed_by}</code></span>}</td></tr>)}</tbody>
      </table></div></section>
    <div className="form-actions"><button className="text-button" type="button" disabled={busy || historical} onClick={() => chooseOperation('APPEND')}>{t('appendEvents')}</button>
      <button className="text-button" type="button" disabled={busy || historical || selected.length === 0} onClick={() => chooseOperation('CORRECT')}>{t('correctSelected')}</button>
      <button className="text-button" type="button" disabled={busy || historical || selected.length === 0} onClick={() => chooseOperation('REVERSE')}>{t('reverseSelected')}</button>
      <button className="text-button" type="button" disabled={busy || historical} onClick={() => chooseOperation('ADD_ACCOUNT')}>{t('addAccount')}</button></div>
    {historical ? <p className="notice neutral-notice">{t('historicalReadOnly')}</p> : <form className="card command-form" onSubmit={(e) => { void makePreview(e); }} noValidate>
      <h3>{t(`operation_${operation}`)}</h3><p className="input-help">{t('ledgerEntryHint')}</p>
      <div className="form-row"><label htmlFor="ledger-as-of">{t('revisionAsOf')} · {t('requiredField')}</label><input id="ledger-as-of" type="date" value={asOf} disabled={busy} onChange={(e) => { changed(); setAsOf(e.target.value); }} aria-describedby="ledger-calendar-help" />
        <p id="ledger-calendar-help" className="input-help">{t('syntheticCalendarBoundary')}</p></div>
      <p id="ledger-currency-help" className="input-help">{t('ledgerCurrencyHint')}</p><p id="ledger-decimal-help" className="input-help">{t('ledgerDecimalHint')}</p>
      {operation === 'CORRECT' || operation === 'REVERSE' ? <div className="target-events"><strong>{t('targetEvents')}</strong>{targets.map((id) => <code key={id}>{id}</code>)}<p>{t(operation === 'CORRECT' ? 'correctionAtomicHint' : 'reversalHint')}</p></div> : null}
      {operation === 'ADD_ACCOUNT' ? <div className="form-row"><label htmlFor="new-account-name">{t('accountContainerName')}</label><input id="new-account-name" value={accountName} maxLength={80} disabled={busy} onChange={(e) => { changed(); setAccountName(e.target.value); }} /></div>
        : operation !== 'REVERSE' && <>{drafts.map((draft, index) => <div key={index}><EventEditor workspace={workspace} draft={draft} index={index} disabled={busy} onChange={(field, value) => edit(index, field, value)} />
          {operation === 'APPEND' && drafts.length > 1 && <button className="text-button" type="button" disabled={busy} onClick={() => { changed(); setDrafts(drafts.filter((_, at) => at !== index)); }}>{t('removeDraftEvent')}</button>}</div>)}
          {operation === 'APPEND' && <button className="text-button" type="button" disabled={busy || drafts.length >= 32} onClick={() => { changed(); setDrafts([...drafts, eventDraft(undefined, workspace.accounts[0]?.account_id ?? '', asOf)]); }}>{t('addBatchEvent')}</button>}
          <p className="input-help">{t('transferPairHint')}</p></>}
      {validation && <p role="alert" className="validation">{t(validation)}</p>}
      <button className="primary-button" disabled={busy} type="submit">{t(busy ? 'validatingCommand' : 'validatePreview')}</button>
      {preview && <><PreviewSummary result={preview} /><label className="checkbox-label"><input type="checkbox" checked={confirmed} disabled={busy} onChange={(e) => setConfirmed(e.target.checked)} /><span>{t('confirmLedgerCommand')}</span></label>
        <button className="primary-button" type="button" disabled={busy || !confirmed} onClick={() => { void commit(); }}>{t(busy ? 'savingCommand' : 'commitLedgerCommand')}</button>
        <p className="input-help">{t('idempotencyHint')}</p><code>{command?.operation_id}</code></>}
    </form>}
    <div role="status" aria-live="polite">{busy ? t('validatingCommand') : status ? t(status) : ''}</div>
    {error !== null && <div role="alert" className="notice error-notice"><strong>{errorLabel(t, error)}</strong>
      {error instanceof ApiError && <details><summary>{t('commandValidationDetails')}</summary><p>{error.detail}</p><code>{error.code}</code></details>}<p>{t(api.guardedProfile ? 'guardedMutationHint' : 'mutationErrorHint')}</p></div>}
  </section>;
}
