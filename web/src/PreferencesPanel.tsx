import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { AccountApi, isCancelled } from './account';
import { errorLabel, metricLabel, metricUnit } from './presentation';
import { ApiError } from './transport';
import { validExactLimit, type PolicyInput, type PreferencesCommand, type Workspace, type WorkspaceResult } from './workspace';

interface PolicyDraft { policy_id: string; target: string; direction: string; limit: string; effective_from: string; effective_until: string; evidence: string }
const targetKey = (target: { source_kind: string; scope_kind: string; account_id?: string | null; metric_id: string; subject: string[]; semantic_key: string }) =>
  JSON.stringify([target.source_kind, target.scope_kind, target.account_id ?? null, target.metric_id, target.subject, target.semantic_key]);
const blankPolicy = (): PolicyDraft => ({ policy_id: crypto.randomUUID(), target: '', direction: '', limit: '', effective_from: '', effective_until: '', evidence: '' });

export default function PreferencesPanel({ workspace, api, onUpdate }: { workspace: Workspace; api: AccountApi; onUpdate: (result: WorkspaceResult) => void }) {
  const { t } = useTranslation(); const historical = workspace.revision_id !== workspace.current_revision_id;
  const [policies, setPolicies] = useState<PolicyDraft[]>(workspace.policies.items.map((policy) => ({
    policy_id: policy.policy_id, target: targetKey(policy), direction: policy.direction, limit: policy.limit,
    effective_from: policy.effective_from, effective_until: policy.effective_until ?? '', evidence: policy.evidence,
  })));
  const [asOf, setAsOf] = useState(workspace.as_of); const [benchmark, setBenchmark] = useState<'KEEP' | 'CLEAR' | 'SELECT'>('KEEP');
  const [benchmarkId, setBenchmarkId] = useState(''); const [selectedOn, setSelectedOn] = useState('');
  const [confirmed, setConfirmed] = useState(false); const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null); const [validation, setValidation] = useState('');
  const [command, setCommand] = useState<PreferencesCommand | null>(null);
  function changed() { setCommand(null); setConfirmed(false); setError(null); setValidation(''); }
  function edit(index: number, field: keyof PolicyDraft, value: string) { changed(); setPolicies(policies.map((policy, at) => at === index ? { ...policy, [field]: value } : policy)); }
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(null); setValidation('');
    if (!confirmed || !asOf || policies.some((policy) => !workspace.policies.targets.some((target) => targetKey(target) === policy.target) || !['MAXIMUM', 'MINIMUM'].includes(policy.direction)
      || !validExactLimit(policy.limit) || !policy.effective_from || !policy.evidence.trim())
      || benchmark === 'SELECT' && (!workspace.benchmark.selection_available || !benchmarkId || !selectedOn)
      || benchmark === 'CLEAR' && !selectedOn) { setValidation('policyFormInvalid'); return; }
    const inputs: PolicyInput[] = policies.map((policy) => {
      const target = workspace.policies.targets.find((candidate) => targetKey(candidate) === policy.target);
      if (!target) throw new Error('Unknown policy target');
      return { policy_id: policy.policy_id, source_kind: target.source_kind, scope_kind: target.scope_kind,
        account_id: target.account_id, metric_id: target.metric_id, subject: target.subject, semantic_key: target.semantic_key,
        direction: policy.direction as 'MAXIMUM' | 'MINIMUM', limit: policy.limit, effective_from: policy.effective_from,
        ...(policy.effective_until ? { effective_until: policy.effective_until } : {}), evidence: policy.evidence };
    });
    const next: PreferencesCommand = command ?? { operation_id: crypto.randomUUID(), expected_revision_id: workspace.revision_id,
      as_of: asOf, policies: inputs, policies_confirmed: true, benchmark: { action: benchmark,
        ...(benchmark === 'SELECT' ? { benchmark_id: benchmarkId, selected_on: selectedOn } : benchmark === 'CLEAR' ? { selected_on: selectedOn } : {}) } };
    setCommand(next); setBusy(true);
    try { onUpdate(await api.preferences(workspace.portfolio_id, next)); }
    catch (failure) { if (!isCancelled(failure)) setError(failure); } finally { setBusy(false); }
  }
  return <section className="preferences-section" aria-labelledby="preferences-title" aria-busy={busy}>
    <div className="section-heading"><div><p className="eyebrow">{t('userChoices')}</p><h2 id="preferences-title">{t('preferencesTitle')}</h2></div><span className="small-note">{t('preferencesScope')}</span></div>
    <div className="scope-strip"><strong>{t('policyStatus')}</strong><span>{t(`policyState_${workspace.policies.state}`)}</span><strong>{t('benchmarkStatus')}</strong><span>{t(`benchmarkState_${workspace.benchmark.state}`)}</span></div>
    <p>{t('policyBlankDisclosure')}</p><p className="input-help">{t('policyNotDenominator')}</p>
    {workspace.policies.items.length > 0 && <details><summary>{t('recordedPolicyProvenance')}</summary>{workspace.policies.items.map((policy) => <dl className="technical-details" key={policy.policy_id}>
      <div><dt>{t('policyIdentifier')}</dt><dd className="mono">{policy.policy_id} · {policy.version}</dd></div>
      <div><dt>{t('policyOrigin')}</dt><dd>{policy.origin}</dd></div><div><dt>{t('policyEvidence')}</dt><dd>{policy.evidence}</dd></div>
      <div><dt>{t('policyDates')}</dt><dd>{policy.effective_from} → {policy.effective_until ?? t('noEndDate')}</dd></div>
      <div><dt>{t('policyTarget')}</dt><dd className="mono">{policy.source_kind} · {policy.scope_kind} · {policy.metric_id} · {policy.subject.join(' · ')} · {policy.semantic_key}</dd></div>
      <div><dt>{t('policyLimit')}</dt><dd className="mono">{policy.direction} · {policy.limit}</dd></div>
    </dl>)}</details>}
    <div className="notice neutral-notice"><strong>{t('benchmarkCatalog')}</strong><p>{t(workspace.benchmark.entries.length ? 'benchmarkExplicitChoice' : 'benchmarkCatalogEmpty')}</p>
      <p className="fine-print">{t('benchmarkRouteNotChoice')}</p><code>{workspace.benchmark.catalog_id}</code>
      <details><summary>{t('benchmarkPin')}</summary><pre className="raw-packet">{JSON.stringify(workspace.benchmark.pin, null, 2)}</pre></details></div>
    {historical ? <p className="notice neutral-notice">{t('historicalReadOnly')}</p> : <form className="card command-form" noValidate onSubmit={(e) => { void submit(e); }}>
      <div className="form-row"><label htmlFor="preferences-as-of">{t('revisionAsOf')}</label><input id="preferences-as-of" type="date" disabled={busy} value={asOf} onChange={(e) => { changed(); setAsOf(e.target.value); }} /><p className="input-help">{t('policyEffectivityHint')}</p></div>
      <h3>{t('optionalPersonalLimits')}</h3>
      {policies.length === 0 && <p className="muted">{t('noPersonalPolicyRows')}</p>}
      {policies.map((policy, index) => <fieldset className="policy-editor" key={policy.policy_id} disabled={busy}><legend>{t('policyNumber', { count: index + 1 })}</legend>
        <div className="form-row"><label htmlFor={`policy-${index}-target`}>{t('policyTarget')} · {t('requiredField')}</label><select id={`policy-${index}-target`} value={policy.target} onChange={(e) => edit(index, 'target', e.target.value)}>
          <option value="">{t('chooseExplicitly')}</option>{workspace.policies.targets.map((target) => <option key={targetKey(target)} value={targetKey(target)}>
            {metricLabel(t, target.metric_id)} · {target.subject.length ? target.subject.join(' / ') : t('portfolio')} · {target.source_kind} · {target.scope_kind} · {target.unit ?? metricUnit(t, target.metric_id)}
          </option>)}</select></div>
        <div className="editor-grid"><div className="form-row"><label htmlFor={`policy-${index}-direction`}>{t('policyDirection')} · {t('requiredField')}</label><select id={`policy-${index}-direction`} value={policy.direction} onChange={(e) => edit(index, 'direction', e.target.value)}>
          <option value="">{t('chooseExplicitly')}</option><option value="MAXIMUM">{t('policyMaximum')}</option><option value="MINIMUM">{t('policyMinimum')}</option></select></div>
          <div className="form-row"><label htmlFor={`policy-${index}-limit`}>{t('policyLimit')} · {t('requiredField')}</label><input id={`policy-${index}-limit`} value={policy.limit} onChange={(e) => edit(index, 'limit', e.target.value)} autoComplete="off" aria-describedby="policy-limit-help" /></div>
          <div className="form-row"><label htmlFor={`policy-${index}-from`}>{t('effectiveFrom')} · {t('requiredField')}</label><input id={`policy-${index}-from`} type="date" value={policy.effective_from} onChange={(e) => edit(index, 'effective_from', e.target.value)} /></div>
          <div className="form-row"><label htmlFor={`policy-${index}-until`}>{t('effectiveUntil')} · {t('optionalField')}</label><input id={`policy-${index}-until`} type="date" value={policy.effective_until} onChange={(e) => edit(index, 'effective_until', e.target.value)} /></div>
        </div><div className="form-row"><label htmlFor={`policy-${index}-evidence`}>{t('policyEvidence')} · {t('requiredField')}</label><input id={`policy-${index}-evidence`} value={policy.evidence} maxLength={500} onChange={(e) => edit(index, 'evidence', e.target.value)} autoComplete="off" /></div>
        <button className="text-button" type="button" onClick={() => { changed(); setPolicies(policies.filter((_, at) => at !== index)); }}>{t('removePolicyRow')}</button>
      </fieldset>)}
      <p id="policy-limit-help" className="input-help">{t('policyExactLimitHint')}</p>
      <button className="text-button" type="button" disabled={busy || workspace.policies.targets.length === 0 || policies.length >= 32} onClick={() => { changed(); setPolicies([...policies, blankPolicy()]); }}>{t('addPersonalLimit')}</button>
      <p className="input-help">{t('policyReplaceHint')}</p>
      <h3 className="benchmark-form-title">{t('benchmarkChoice')}</h3>
      <div className="form-row"><label htmlFor="benchmark-action">{t('benchmarkChoice')}</label><select id="benchmark-action" value={benchmark} disabled={busy} onChange={(e) => { changed(); setBenchmark(e.target.value as 'KEEP' | 'CLEAR' | 'SELECT'); }}>
        <option value="KEEP">{t('benchmarkKeep')}</option><option value="CLEAR">{t('benchmarkClear')}</option><option value="SELECT" disabled={!workspace.benchmark.selection_available}>{t('benchmarkSelect')}</option></select></div>
      {benchmark === 'SELECT' && <div className="form-row"><label htmlFor="benchmark-id">{t('benchmarkCatalogEntry')}</label><select id="benchmark-id" value={benchmarkId} disabled={busy} onChange={(e) => { changed(); setBenchmarkId(e.target.value); }}>
        <option value="">{t('chooseExplicitly')}</option>{workspace.benchmark.entries.map((entry) => <option key={entry.benchmark_id} value={entry.benchmark_id}>{entry.name} · {entry.benchmark_id}</option>)}</select></div>}
      {benchmark !== 'KEEP' && <div className="form-row"><label htmlFor="benchmark-selected-on">{t('benchmarkSelectedOn')} · {t('requiredField')}</label><input id="benchmark-selected-on" type="date" value={selectedOn} disabled={busy} onChange={(e) => { changed(); setSelectedOn(e.target.value); }} /></div>}
      <label className="checkbox-label"><input type="checkbox" checked={confirmed} disabled={busy} onChange={(e) => setConfirmed(e.target.checked)} /><span>{t('confirmPreferences')}</span></label>
      {validation && <p role="alert" className="validation">{t(validation)}</p>}
      <button className="primary-button" type="submit" disabled={busy || !confirmed}>{t(busy ? 'savingPreferences' : 'savePreferences')}</button>
      <p className="input-help">{t('idempotencyHint')}</p>{command && <code>{command.operation_id}</code>}
    </form>}
    <div role="status" aria-live="polite">{busy ? t('savingPreferences') : ''}</div>
    {error !== null && <div className="notice error-notice" role="alert"><strong>{errorLabel(t, error)}</strong>
      {error instanceof ApiError && <details><summary>{t('commandValidationDetails')}</summary><p>{error.detail}</p><code>{error.code}</code></details>}<p>{t(api.guardedProfile ? 'guardedMutationHint' : 'mutationErrorHint')}</p></div>}
  </section>;
}
