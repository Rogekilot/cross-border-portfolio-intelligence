import { useEffect, useRef, useState, type FormEvent } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { ApiError, GuestApi, isDecimalInput, isObject, isZeroInput, packetPolicy, type CreatePortfolio, type JsonObject, type Metric, type Packet, type PacketResponse, type Reproduction, type Snapshot } from './transport';
import { errorLabel, exactWitnesses, freshnessEntries, limitationLabel, metricLabel, metricSubject, metricUnit, observationClaim, packetForMetric, reasonLabel, sharedClaimCaveats, subjectLabel } from './presentation';
import { AccountApi, isCancelled, type AccountSession, type SavedPortfolio } from './account';
import AccountPanel from './AccountPanel';
import LedgerPanel from './LedgerPanel';
import PreferencesPanel from './PreferencesPanel';
import CsvPanel from './CsvPanel';
import ClaimDepth from './ClaimDepth';
import AnalyticsPanel, { AnalyticsSummary, ContextualAiEntry } from './AnalyticsPanel';
import { PartialValuationContext, type GainColors } from './AnalyticalMetric';
import { WorkspaceReadEpoch, type Workspace, type WorkspaceResult } from './workspace';
import RealSourceReadiness from './RealSourceReadiness';
import GuardedArchivePanel from './GuardedArchivePanel';
import { guardedSurfaces } from './guarded-pending';
import { GuardedOutcomeError, GuardedUnconfirmedError, validGuardedOpeningDate, type GuardedCommitted, type GuardedProfile, type GuardedRead, type PendingGuardedOperation } from './guarded';
import GuardedCsvReportPanel from './GuardedCsvReportPanel';
import type { GuardedCsvReportCommitted, GuardedCsvReportReference } from './guarded-csv-report';

type Depth = 'quick' | 'simple' | 'professional';
type Evidence = { snapshot: Snapshot; revisionId?: string; packet?: Packet; metric?: Metric; group?: 'valuation' | 'diversification' };
const api = new GuestApi();
const accountApi = new AccountApi();

function StateBadge({ state }: { state: string }) {
  const { t } = useTranslation();
  return <span className={`state-badge state-${state.toLowerCase()}`}>{t(state, { defaultValue: state })}</span>;
}

export function ErrorNotice({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const uncertain = error instanceof GuardedUnconfirmedError || error instanceof GuardedOutcomeError && error.outcome.disposition === 'UNKNOWN';
  return <div className="notice error-notice" role="alert">
    <strong>{t(uncertain ? 'guardedUnknown' : 'errorTitle')}</strong><p>{errorLabel(t, error)}</p>
    {error instanceof ApiError && <code>{error.code}</code>}
    <p className="fine-print">{t(uncertain ? 'guardedUnknownHint' : 'retryHint')}</p>
  </div>;
}

function Limitations({ items, compact = false }: { items: string[]; compact?: boolean }) {
  const { t } = useTranslation();
  if (!items.length) return null;
  return <div className={compact ? 'limitations compact' : 'limitations'}>
    <strong>{t('limitations')}</strong>
    <ul>{[...new Set(items)].map((item) => <li key={item}>{limitationLabel(t, item)}</li>)}</ul>
  </div>;
}

function Freshness({ metric }: { metric?: Metric }) {
  const { t } = useTranslation();
  const entries = metric ? freshnessEntries(metric) : [];
  const axes = [
    { title: 'priceFreshness', entries: entries.filter((e) => String(e.kind).startsWith('EXCHANGE')) },
    { title: 'fxFreshness', entries: entries.filter((e) => e.kind === 'CURRENCY') },
  ];
  return <div className="freshness-panel">
    {axes.map((axis) => <div key={axis.title}><span className="meta-label">{t(axis.title)}</span>
      {axis.entries.length ? axis.entries.map((entry) => <p key={String(entry.key)}>
        <span>{t(String(entry.state), { defaultValue: String(entry.state) })}</span>
        <span className="freshness-date">{String(entry.key)} · {String(entry.date_used ?? t('UNKNOWN'))}</span>
      </p>) : <p>{t('UNKNOWN')}</p>}
    </div>)}
    <p className="freshness-explanation">{t('freshnessNote')}</p>
  </div>;
}

function CreateForm({ onCreate, saved, disabled, profile, uncertain }: { onCreate: (input: CreatePortfolio & { operation_id?: string; opening_date?: string }) => Promise<void>; saved: boolean; disabled: boolean; profile: GuardedProfile | null; uncertain: boolean }) {
  const { t } = useTranslation();
  const [capabilities, setCapabilities] = useState<JsonObject | null>(null);
  const [name, setName] = useState('');
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [cash, setCash] = useState('');
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [validation, setValidation] = useState('');
  const guarded = saved && profile !== null;
  const [openingDate, setOpeningDate] = useState(profile?.opening_date_recommended ?? '');
  const [operationId, setOperationId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void api.capabilities().then((data) => { if (active) setCapabilities(data); })
      .catch((failure: unknown) => { if (active) setError(failure); });
    return () => { active = false; };
  }, []);

  const symbols = capabilities && Array.isArray(capabilities.listings)
    ? capabilities.listings.filter(isObject) : [];

  function fillExample() {
    setOperationId(null);
    if (!capabilities || !isObject(capabilities.defaults)) return;
    const defaults = capabilities.defaults;
    if (Array.isArray(defaults.positions)) {
      setQuantities(Object.fromEntries(defaults.positions.filter(isObject)
        .filter((p) => typeof p.symbol === 'string' && typeof p.quantity === 'string')
        .map((p) => [String(p.symbol), String(p.quantity)])));
    }
    if (typeof defaults.cash === 'string') setCash(defaults.cash);
    if (!name.trim()) setName(t('portfolioNameDefault'));
    setValidation('');
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(null); setValidation('');
    const values = symbols.map((s) => ({ symbol: String(s.symbol), quantity: quantities[String(s.symbol)] ?? '' }));
    const positions = values.filter((p) => p.quantity !== '' && !isZeroInput(p.quantity));
    if (!name.trim() || !isDecimalInput(cash) || (positions.length === 0 && isZeroInput(cash))
      || values.some((p) => p.quantity !== '' && !isDecimalInput(p.quantity))) { setValidation('formRequired'); return; }
    if (!ack) { setValidation('formAcknowledgement'); return; }
    if (guarded && !validGuardedOpeningDate(openingDate, profile)) { setValidation('guardedOpeningInvalid'); return; }
    setBusy(true);
    try {
      const nextOperation = guarded ? operationId ?? crypto.randomUUID() : null;
      if (nextOperation) setOperationId(nextOperation);
      await onCreate({ name: name.trim(), reporting_currency: 'USD', positions, cash, synthetic_acknowledged: true,
        ...(nextOperation ? { operation_id: nextOperation, opening_date: openingDate } : {}) });
    } catch (failure) { if (!isCancelled(failure)) setError(failure); } finally { setBusy(false); }
  }

  return <section className="onboarding">
    <div className="page-intro onboarding-intro">
      <p className="eyebrow">{t('welcomeEyebrow')}</p><h1>{t('welcomeTitle')}</h1><p className="lede">{t('welcomeBody')}</p>
    </div>
    <div className="onboarding-grid">
      <section className="card create-card" aria-labelledby="create-title">
        <div className="section-number">01 / {t('portfolio')}</div>
        <h2 id="create-title">{t(saved ? 'createSavedTitle' : 'createTitle')}</h2><p className="muted">{t(saved ? 'savedDescription' : 'createDescription')}</p>
        {profile && <p className="notice neutral-notice">{t(saved ? 'guardedScope' : 'guardedGuestUnavailable')}</p>}
        <form onSubmit={(event) => { void submit(event); }} noValidate aria-busy={busy}>
          <div className="form-row"><label htmlFor="portfolio-name">{t('portfolioName')}</label>
            <input id="portfolio-name" name="name" maxLength={80} value={name} disabled={busy || uncertain} onChange={(e) => { setOperationId(null); setName(e.target.value); }} autoComplete="off" />
          </div>
          {guarded && <div className="form-row"><label htmlFor="guarded-opening-date">{t('guardedOpeningDate')}</label>
            <input id="guarded-opening-date" type="date" required max={profile.opening_date_max} value={openingDate} disabled={busy || uncertain}
              onChange={(event) => { setOperationId(null); setOpeningDate(event.target.value); }} aria-describedby="guarded-date-help" />
            <p id="guarded-date-help" className="input-help">{t('guardedOpeningHint')} {t('guardedSourceDate')}: {profile.source_as_of}</p></div>}
          <div className="form-row"><label htmlFor="reporting-currency">{t('reportingCurrency')}</label>
            <select id="reporting-currency" value="USD" onChange={() => undefined} aria-describedby="currency-help">
              <option value="USD">USD</option><option value="CNY" disabled>CNY — {t('notImplemented')}</option>
            </select>
            <p id="currency-help" className="input-help">{t('currencyHint')} {t('currencyUnavailable')}</p>
          </div>
          <fieldset><legend>{t('positions')}</legend><p className="input-help">{t('syntheticSymbols')} {t('quantityLimit')}</p>
            <div className="position-inputs">{symbols.map((symbol) => <div className="position-input" key={String(symbol.symbol)}>
              <div><label htmlFor={`quantity-${String(symbol.symbol)}`}>{String(symbol.symbol)}</label>
                <small>{String(symbol.currency)} · {String(capabilities?.as_of ?? '')}</small></div>
              <div><label className="sr-only" htmlFor={`quantity-${String(symbol.symbol)}`}>{t('quantity')} {String(symbol.symbol)}</label>
                <input id={`quantity-${String(symbol.symbol)}`} inputMode="decimal" value={quantities[String(symbol.symbol)] ?? ''} disabled={busy || uncertain}
                  onChange={(e) => { setOperationId(null); setQuantities({ ...quantities, [String(symbol.symbol)]: e.target.value }); }} placeholder="0" aria-describedby="decimal-help" />
              </div>
            </div>)}</div>
          </fieldset>
          <div className="form-row"><label htmlFor="opening-cash">{t('openingCash')}</label>
            <input id="opening-cash" inputMode="decimal" value={cash} disabled={busy || uncertain} onChange={(e) => { setOperationId(null); setCash(e.target.value); }} aria-describedby="decimal-help" />
          </div>
          <p id="decimal-help" className="input-help">{t('canonicalInput')} {t('cashLimit')}</p>
          <label className="checkbox-label"><input type="checkbox" checked={ack} disabled={busy || uncertain} onChange={(e) => { setOperationId(null); setAck(e.target.checked); }} />
            <span>{t('acknowledge')}</span></label>
          {validation && <p className="validation" role="alert">{t(validation)}</p>}
          {error !== null && <ErrorNotice error={error} />}
          <div className="form-actions"><button className="primary-button" disabled={busy || disabled || uncertain || !capabilities || profile !== null && !saved} type="submit">
            {t(busy ? 'creating' : saved ? 'saveAndAnalyze' : 'create')}<span aria-hidden="true">↗</span></button>
            <button type="button" className="text-button" disabled={busy || disabled || uncertain || !capabilities} onClick={fillExample}>{t('loadDemo')}</button></div>
          {operationId && <p className="input-help">{t('guardedOperation')}: <code>{operationId}</code></p>}
        </form>
      </section>
      <aside className="onboarding-notes"><p className="eyebrow">{t('flowHeading')}</p>
        <ol className="flow-steps">{[1, 2, 3].map((step) => <li key={step}><span className="step-marker">0{step}</span>
          <div><h3>{t(saved && step === 1 ? 'step1Saved' : `step${step}`)}</h3><p>{t(`step${step}Body`)}</p></div></li>)}</ol>
        <div className="boundary-note"><span className="boundary-mark" aria-hidden="true">i</span><div><h3>{t('noHistoryTitle')}</h3><p>{t('noHistory')}</p></div></div>
        <p className="fine-print persistence-note">{t(saved ? 'savedNotice' : 'noPersistence')}</p>
      </aside>
    </div>
  </section>;
}

function MetricDetails({ metric, snapshot, group }: { metric: Metric; snapshot: Snapshot; group: 'valuation' | 'diversification' }) {
  const { t } = useTranslation();
  const witnesses = exactWitnesses(metric);
  return <dl className="technical-details">
    {witnesses.length ? witnesses.map((row) => <div key={row.label}><dt>{t(row.label)}</dt><dd className="mono">{row.value}</dd></div>)
      : <div><dt>{t('exactValue')}</dt><dd>{t('noExactWitness')}</dd></div>}
    <div><dt>{t('unit')}</dt><dd>{metricUnit(t, metric.metric_id)}</dd></div>
    <div><dt>{t('subject')}</dt><dd>{subjectLabel(t, metric) || t('snapshotLabel')}</dd></div>
    <div><dt>{t('method')}</dt><dd className="mono">{metric.method_id ?? metric.method_key ?? t('UNKNOWN')}</dd></div>
    <div><dt>{t('source')}</dt><dd className="mono">{snapshot[group].manifest_id}</dd></div>
    <div><dt>{t('resultDigest')}</dt><dd className="mono">{snapshot[group].result_digest}</dd></div>
    {group === 'diversification' && <div><dt>{t('denominator')}</dt><dd>{t('fullNav')} · FULL_NAV / GLOBAL_PRODUCT</dd></div>}
  </dl>;
}

function MetricCard({ metric, snapshot, depth, group, onEvidence }: { metric: Metric; snapshot: Snapshot; depth: Depth; group: 'valuation' | 'diversification'; onEvidence: (evidence: Evidence) => void }) {
  const { t } = useTranslation();
  const packet = group === 'diversification' ? packetForMetric(snapshot.insights.packets, metric) : undefined;
  return <ClaimDepth depth={depth} claim={metricLabel(t, metric.metric_id)}>{(activeDepth, depthControl) => <article className={`card metric-card ${metric.state === 'INSUFFICIENT_DATA' ? 'metric-suppressed' : ''}`}>
    <div className="metric-topline"><span>{metricLabel(t, metric.metric_id)}</span><StateBadge state={metric.state} /></div>
    {metric.state === 'INSUFFICIENT_DATA' ? <p className="unavailable-value">{t('INSUFFICIENT_DATA')}</p>
      : <p className="metric-value"><span>{metric.value}</span>{metric.currency && <span className="metric-unit">{metric.currency}</span>}</p>}
    <p className="semantic-unit">{metricUnit(t, metric.metric_id)}</p>
    <PartialValuationContext metric={metric} />
    {metricSubject(metric) && <p className="scope-label">{t('subject')}: {subjectLabel(t, metric)}</p>}
    {metric.reason && <p className="reason-text">{reasonLabel(t, metric.reason)} <code>{metric.reason}</code></p>}
    {metric.details.length > 0 && <Limitations items={metric.details} compact />}
    {activeDepth !== 'quick' && <p className="metric-explanation">{t(`definition_${metric.metric_id}`, { defaultValue: t('limitedAlways') })}</p>}
    {activeDepth === 'professional' && <MetricDetails metric={metric} snapshot={snapshot} group={group} />}
    {snapshot.persisted && accountApi.guardedProfile ? <p className="input-help">{t('guardedEvidenceHint')}</p>
      : <button type="button" className="evidence-button" onClick={() => onEvidence({ snapshot, metric, group, packet })}>{t('evidence')} <span aria-hidden="true">↗</span></button>}
    {depthControl}
  </article>}</ClaimDepth>;
}

function Observations({ snapshot, depth, onEvidence, policySupplied = false }: { snapshot: Snapshot; depth: Depth; onEvidence: (evidence: Evidence) => void; policySupplied?: boolean }) {
  const { t } = useTranslation();
  const caveats = sharedClaimCaveats(snapshot.insights.packets.map((packet) => packet.limitations));
  return <section className="observations-section" aria-labelledby="observations-title" aria-describedby={caveats.shared.length ? 'observations-common-restrictions' : undefined}>
    <div className="section-heading"><div><p className="eyebrow">CP6 / {t('issuedObservations')}</p><h2 id="observations-title">{t('observations')}</h2></div><span className="small-note">{t(policySupplied ? 'policySupplied' : 'noPolicy')}</span></div>
    {caveats.shared.length > 0 && <div id="observations-common-restrictions" className="observation-common-restrictions" tabIndex={-1}>
      <h3>{t('observationCommonRestrictions')}</h3><Limitations items={caveats.shared} compact />
    </div>}
    {snapshot.insights.packets.length === 0 ? <p>{t('noInsights')}</p> : <div className="observation-list">{snapshot.insights.packets.map((packet, packetIndex) => {
      const metric = packet.metrics_used[0]?.metric;
      const policy = packetPolicy(packet);
      return <ClaimDepth key={packet.insight_id} depth={depth} claim={metric ? metricLabel(t, metric.metric_id) : packet.insight_id}>{(activeDepth, depthControl) => <article className="observation">
        <div className="observation-symbol" aria-hidden="true">↗</div><div className="observation-body">
          <span className={`severity severity-${packet.severity.toLowerCase()}`}>{t(packet.severity.toLowerCase(), { defaultValue: packet.severity })}</span>
          <span className="judgment-label">{t(`judgment_${packet.judgment_class}`, { defaultValue: packet.judgment_class })}</span>
          <p className="observation-claim">{observationClaim(t, packet, snapshot.as_of)}</p>
          {policy && <dl className="policy-claim-basis technical-details">
            <div><dt>{t('userPolicyReference')}</dt><dd>{t('judgment_PREFERENCE_DEPENDENT')} · USER_POLICY</dd></div>
            <div><dt>{t('policyLimit')}</dt><dd className="mono">{t(policy.direction === 'MAXIMUM' ? 'policyMaximum' : 'policyMinimum')} · {policy.limit}</dd></div>
            <div><dt>{t('policyDates')}</dt><dd>{policy.effective_from} → {policy.effective_until ?? t('noEndDate')}</dd></div>
            <div><dt>{t('policyEvidence')}</dt><dd>{policy.evidence}</dd></div>
            <div><dt>{t('policyIdentifier')}</dt><dd className="mono">{policy.policy_id} · {policy.version} · {policy.origin}</dd></div>
            <div><dt>{t('policyTarget')}</dt><dd className="mono">{policy.source_kind} · {policy.scope_kind} · {policy.metric_id} · {policy.subject.join(' · ')}{policy.account_id ? ` · ${policy.account_id}` : ''}</dd></div>
            <div><dt>{t('decisionBasis')}</dt><dd>{t('exactWitnessDecision')}</dd></div>
          </dl>}
          {metric && <p className="semantic-unit">{metricUnit(t, metric.metric_id)}</p>}
          {metric && metricSubject(metric) && <p className="scope-label">{t('subject')}: {subjectLabel(t, metric)}</p>}
          <StateBadge state={packet.confidence_availability_state} />
          {caveats.shared.length > 0 && <p className="shared-restriction-reference"><a href="#observations-common-restrictions">{t('observationCommonApplies')}</a></p>}
          {activeDepth !== 'quick' && metric && <p>{t(`definition_${metric.metric_id}`, { defaultValue: t('limitedAlways') })}</p>}
          <Limitations items={caveats.local[packetIndex]} compact />
          {activeDepth === 'professional' && metric && <MetricDetails metric={metric} snapshot={snapshot} group="diversification" />}
          {snapshot.persisted && accountApi.guardedProfile ? <p className="input-help">{t('guardedEvidenceHint')}</p>
            : <button type="button" className="evidence-button" onClick={() => onEvidence({ snapshot, packet })}>{t('evidence')} <span aria-hidden="true">↗</span></button>}
          {depthControl}
        </div>
      </article>}</ClaimDepth>;
    })}</div>}
  </section>;
}

function Overview({ snapshot, depth, onEvidence, workspace, colors }: { snapshot: Snapshot; depth: Depth; onEvidence: (evidence: Evidence) => void; workspace?: Workspace | null; colors: GainColors }) {
  const { t } = useTranslation();
  const total = snapshot.valuation.metrics.find((m) => m.metric_id === 'portfolio_value' && m.view === 'REPORTING');
  const summary = ['largest_security_weight', 'effective_positions'].flatMap((id) => snapshot.diversification.metrics.filter((m) => m.metric_id === id));
  return <>
    <div className="page-heading"><div><p className="eyebrow">{t(snapshot.persisted ? 'savedWorkspace' : 'workspace')}</p><h1>{snapshot.name}</h1><p className="muted">{t('overviewIntro')}</p></div>
      <div className="as-of"><span>{t('asOf')}</span><strong>{snapshot.as_of}</strong><span>{t('currentState')}</span></div></div>
    <div className="metric-grid">{total && <MetricCard metric={total} snapshot={snapshot} group="valuation" depth={depth} onEvidence={onEvidence} />}
      {snapshot.valuation.metrics.filter((metric) => metric.metric_id === 'portfolio_value_priced_holdings').map((metric) => <MetricCard key={`${metric.metric_id}:${metricSubject(metric)}`} metric={metric} snapshot={snapshot} group="valuation" depth={depth} onEvidence={onEvidence} />)}</div>
    <Freshness metric={total} />
    {accountApi.guardedProfile ? <p className="notice neutral-notice">{t('guardedUnsupported')}</p>
      : <AnalyticsSummary key={`performance:${workspace?.revision_id ?? snapshot.portfolio_id}`} workspace={workspace} api={accountApi} family="PERFORMANCE_WINDOW" depth={depth} colors={colors} />}
    <div className="section-heading"><h2>{t('exposures')}</h2></div><div className="metric-grid">{summary.map((metric) => <MetricCard key={metric.metric_id} metric={metric} snapshot={snapshot} group="diversification" depth={depth} onEvidence={onEvidence} />)}</div>
    {!accountApi.guardedProfile && <AnalyticsSummary key={`risk:${workspace?.revision_id ?? snapshot.portfolio_id}`} workspace={workspace} api={accountApi} family="RISK" depth={depth} colors={colors} />}
    <Observations snapshot={snapshot} depth={depth} onEvidence={onEvidence} policySupplied={workspace?.policies.state === 'ACTIVE'} />
    <div className="notice neutral-notice">{!workspace && <><strong>{t('historicalUnavailable')}</strong><p>{t('noHistory')}</p></>}<p>{workspace ? t('benchmarkCurrentNote', { state: t(`benchmarkState_${workspace.benchmark.state}`) }) : t(snapshot.persisted ? 'noBenchmarkSaved' : 'noBenchmark')}</p></div>
    <ContextualAiEntry />
    <Limitations items={snapshot.limitations} />
  </>;
}

function Portfolio({ snapshot, workspace, onUpdate, onHistory, csvReportRecovery = 0 }: { snapshot: Snapshot; workspace?: Workspace | null; onUpdate: (result: WorkspaceResult) => void; onHistory: (revisionId: string) => Promise<void>; csvReportRecovery?: number }) {
  const { t } = useTranslation();
  return <><div className="page-heading"><div><p className="eyebrow">{t(snapshot.persisted ? 'savedWorkspace' : 'workspace')}</p><h1>{t('holdingsTitle')}</h1><p className="muted">{t(workspace ? 'savedHoldingsBody' : 'holdingsBody')}</p></div></div>
    <section className="card table-card">{workspace && <><h2>{t('originalOpeningFacts')}</h2><p className="input-help">{t('originalOpeningHint')}</p></>}<p className="table-scroll-hint">{t('scrollTable')}</p><div className="table-scroll" tabIndex={0} role="region" aria-label={t(workspace ? 'originalOpeningFacts' : 'holdingsTitle')}>
      <table><caption>{snapshot.name} · {workspace ? t('originalOpeningFacts') : `${t('asOf')} ${snapshot.as_of} · ${t('currentState')}`}</caption>
        <thead><tr><th scope="col">{t('security')}</th><th scope="col" className="numeric">{t('quantity')}</th><th scope="col">{t('currency')}</th><th scope="col">{t('state')}</th></tr></thead>
        <tbody>{snapshot.inputs.positions.map((position) => <tr key={position.symbol}><th scope="row">{position.symbol}</th><td className="numeric">{position.quantity}</td><td>{snapshot.reporting_currency}</td><td>{t(workspace ? 'originalOpeningFacts' : 'currentState')}</td></tr>)}
          <tr><th scope="row">{t('cash')}</th><td className="numeric">{snapshot.inputs.cash}</td><td>{snapshot.reporting_currency}</td><td>{t(workspace ? 'originalOpeningFacts' : 'currentState')}</td></tr></tbody>
      </table></div></section>
    {workspace && <><LedgerPanel key={`ledger:${workspace.revision_id}`} workspace={workspace} api={accountApi} onUpdate={onUpdate} onHistory={onHistory} />
      <CsvPanel key={`csv:${workspace.revision_id}:${csvReportRecovery}`} workspace={workspace} api={accountApi} onUpdate={onUpdate} onHistory={onHistory} />
      <PreferencesPanel key={`preferences:${workspace.revision_id}`} workspace={workspace} api={accountApi} onUpdate={onUpdate} /></>}
    <div className="notice neutral-notice"><strong>{t('pendingTitle')}</strong><p>{t('pendingBody')}</p><p>{t(snapshot.persisted ? 'savedPersistence' : 'noPersistence')}</p></div>
  </>;
}

function Analytics({ snapshot, depth, onEvidence, policySupplied = false, workspace, colors }: { snapshot: Snapshot; depth: Depth; onEvidence: (evidence: Evidence) => void; policySupplied?: boolean; workspace?: Workspace | null; colors: GainColors }) {
  const { t } = useTranslation();
  return <><div className="page-heading"><div><p className="eyebrow">{t('savedWorkspace')}</p><h1>{t('analyticsTitle')}</h1><p className="muted">{t('analyticsScope')}</p></div></div>
    {accountApi.guardedProfile ? <p className="notice neutral-notice">{t('guardedUnsupported')}</p>
      : <AnalyticsPanel key={`analytics:${workspace?.revision_id ?? snapshot.portfolio_id}`} workspace={workspace} api={accountApi} depth={depth} colors={colors} />}
    <div className="section-heading"><h2>{t('exposures')}</h2></div>
    <div className="scope-strip"><strong>{t('denominator')}</strong><span>{t('fullNav')} · GLOBAL_PRODUCT</span></div>
    <div className="metric-grid analytics-grid">{snapshot.diversification.metrics.map((metric) => <MetricCard key={`${metric.metric_id}:${metricSubject(metric)}`} metric={metric} snapshot={snapshot} depth={depth} group="diversification" onEvidence={onEvidence} />)}</div>
    <div className="notice neutral-notice"><strong>{t('historicalUnavailable')}</strong><p>{t('noHistory')}</p><p>{t(policySupplied ? 'policySupplied' : 'noPolicy')}</p></div>
    <ContextualAiEntry />
  </>;
}

function Scenario() {
  const { t } = useTranslation();
  return <section className="empty-state"><span className="empty-marker" aria-hidden="true">◇</span><p className="eyebrow">CP8 / {t('notImplemented')}</p><h1>{t('scenarioTitle')}</h1><p>{t('scenarioBody')}</p></section>;
}

function EvidenceDialog({ evidence, onClose }: { evidence: Evidence; onClose: () => void }) {
  const { t } = useTranslation();
  const dialog = useRef<HTMLDialogElement>(null);
  // Capture before showModal changes focus; StrictMode repeats effects, not this identity.
  const opener = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null);
  const [response, setResponse] = useState<PacketResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [reproduction, setReproduction] = useState<Reproduction | null>(null);
  const [busy, setBusy] = useState(false);
  const active = useRef(true);

  useEffect(() => {
    const element = dialog.current;
    active.current = true;
    element?.showModal();
    return () => {
      active.current = false;
      element?.close();
      // Restore after React removes the modal. Focusing an inert background opener
      // while it is still mounted can be ignored by the browser. Skip StrictMode's
      // temporary effect cleanup, where the same dialog remains connected.
      queueMicrotask(() => {
        if (!element?.isConnected && opener.current?.isConnected) opener.current.focus();
      });
    };
  }, []);
  useEffect(() => {
    if (!evidence.packet) return;
    let active = true;
    const request = evidence.snapshot.persisted ? accountApi.packet(evidence.snapshot.portfolio_id, evidence.packet.insight_id, evidence.revisionId)
      : api.packet(evidence.snapshot.portfolio_id, evidence.packet.insight_id);
    void request.then((result) => {
      if (result.result_digest !== evidence.snapshot.insights.result_digest) throw new ApiError('INVALID_RESPONSE', 'Packet result digest mismatch');
      if (active) setResponse(result);
    }).catch((failure: unknown) => { if (active) setError(failure); });
    return () => { active = false; };
  }, [evidence]);

  async function reproduce() {
    if (!response) return;
    setBusy(true); setError(null); setReproduction(null);
    try {
      const result = await (evidence.snapshot.persisted
        ? accountApi.reproduce(evidence.snapshot.portfolio_id, response.packet.insight_id, response.result_digest, evidence.revisionId)
        : api.reproduce(evidence.snapshot.portfolio_id, response.packet.insight_id, response.result_digest));
      if (active.current) setReproduction(result);
    } catch (failure) { if (active.current && !isCancelled(failure)) setError(failure); }
    finally { if (active.current) setBusy(false); }
  }
  const packet = response?.packet;
  return <dialog ref={dialog} className="evidence-dialog" aria-labelledby="evidence-title" onCancel={onClose}>
    <div className="dialog-heading"><div><p className="eyebrow">{t('banner')}</p><h2 id="evidence-title">{t('evidenceTitle')}</h2></div>
      <button type="button" className="close-button" aria-label={t('closeEvidence')} onClick={onClose}>×</button></div>
    <div className="dialog-body">
      {error !== null && <ErrorNotice error={error} />}
      {evidence.revisionId && <div className="revision-strip"><strong>{t('evidenceRevision')}</strong><code>{evidence.revisionId}</code></div>}
      {evidence.packet && !response && error === null && <p role="status">{t('loadingEvidence')}</p>}
      {packet && <>
        <StateBadge state={packet.confidence_availability_state} />
        <dl className="technical-details packet-identities"><div><dt>{t('packetId')}</dt><dd className="mono">{packet.insight_id}</dd></div><div><dt>{t('resultDigest')}</dt><dd className="mono">{response.result_digest}</dd></div></dl>
        <Limitations items={packet.limitations} />
        <section className="reproduction-panel"><h3>{t('reproducibility')}</h3><p>{t('reproductionCaveat')}</p>
          <button type="button" className="primary-button" disabled={busy} onClick={() => { void reproduce(); }}>{t(busy ? 'reproducing' : 'reproduce')}</button>
          {reproduction && <div className={`reproduction-result ${reproduction.status === 'REPRODUCED' ? 'is-reproduced' : ''}`} role="status"><strong>{t(reproduction.status, { defaultValue: reproduction.status })}</strong>
            <p>{t(`reproduction_${reproduction.detail}`, { keySeparator: false, defaultValue: reproduction.detail })}</p>
            <code>{reproduction.actual_result_digest ?? t('UNKNOWN')}</code></div>}
        </section>
        <h3>{t('fullPacket')}</h3><p className="fine-print">{t('rawTechnical')}</p><pre className="raw-packet">{JSON.stringify(packet, null, 2)}</pre>
      </>}
      {!evidence.packet && evidence.metric && evidence.group && <>
        <h3>{metricLabel(t, evidence.metric.metric_id)}</h3><StateBadge state={evidence.metric.state} />
        <MetricDetails metric={evidence.metric} snapshot={evidence.snapshot} group={evidence.group} />
        <Freshness metric={evidence.metric} /><Limitations items={evidence.metric.details} />
        <p className="fine-print">{t('rawTechnical')}</p><pre className="raw-packet">{JSON.stringify({ metric: evidence.metric, provenance: evidence.snapshot.provenance }, null, 2)}</pre>
      </>}
    </div>
  </dialog>;
}

export default function App() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [depth, setDepth] = useState<Depth>('quick');
  const [gainColors, setGainColors] = useState<GainColors>('GREEN_GAIN');
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [workspaceStatus, setWorkspaceStatus] = useState('');
  const [session, setSession] = useState<AccountSession | null>(null);
  const [checkingAccount, setCheckingAccount] = useState(true);
  const [accountBusy, setAccountBusy] = useState(false);
  const [savedPortfolios, setSavedPortfolios] = useState<SavedPortfolio[]>([]);
  const [savedMode, setSavedMode] = useState(false);
  const [realReadinessOpen, setRealReadinessOpen] = useState(false);
  const [guardedReference, setGuardedReference] = useState<GuardedRead | GuardedCommitted | null>(null);
  const [guardedPending, setGuardedPending] = useState<PendingGuardedOperation | null>(null);
  const [guardedCsvReportReference, setGuardedCsvReportReference] = useState<GuardedCsvReportReference | null>(null);
  const [csvReportRecovery, setCsvReportRecovery] = useState(0);
  const profile = session?.guarded_profile ?? null;
  const readinessEntryLocation = useRef<string | null>(null);
  const showingRealReadiness = realReadinessOpen && location.pathname === '/portfolio' && session?.authenticated === true;
  const identity = useRef(0);
  const workspaceReads = useRef(new WorkspaceReadEpoch());
  const accountChannel = useRef<BroadcastChannel | null>(null);
  const currentSession = useRef(session); currentSession.current = session;
  useEffect(() => { document.documentElement.lang = i18n.language; }, [i18n.language]);
  useEffect(() => {
    if (!realReadinessOpen) return;
    if (location.pathname === '/portfolio') { readinessEntryLocation.current = null; return; }
    // Local intent can render before the router reaches Portfolio. Only a later
    // location closes it; reaching Portfolio clears that temporary allowance.
    if (location.key !== readinessEntryLocation.current) { setRealReadinessOpen(false); accountApi.cancelPending(); }
  }, [realReadinessOpen, location.pathname, location.key]);
  function clearWorkspace(clearGuarded = false) {
    identity.current += 1; api.reset(); accountApi.cancelPending();
    setCheckingAccount(false);
    workspaceReads.current.invalidate();
    setRealReadinessOpen(false);
    readinessEntryLocation.current = null;
    setSnapshot(null); setWorkspace(null); setEvidence(null); setSavedPortfolios([]); setBusy(false); setError(null); setWorkspaceStatus('');
    setGuardedReference(null); setGuardedCsvReportReference(null); if (clearGuarded) setGuardedPending(null);
    return identity.current;
  }
  async function loadSaved(expected = identity.current) {
    const values = await accountApi.portfolios();
    if (identity.current === expected) setSavedPortfolios(values);
  }
  useEffect(() => {
    let active = true;
    accountApi.onSessionLost = (failure) => {
      if (!active) return;
      clearWorkspace(true); setSession(null); setSavedMode(false); setAccountBusy(false); setCheckingAccount(false); setError(failure);
    };
    accountApi.onGuardedPending = (operation) => { if (active) setGuardedPending(operation); };
    accountApi.onGuardedReference = (reference) => { if (active) setGuardedReference(reference); };
    accountApi.onGuardedCsvReportReference = (reference) => { if (active) setGuardedCsvReportReference(reference); };
    function checkSession(invalidate: boolean) {
      if (invalidate) { clearWorkspace(true); accountApi.reset(); setSession(null); setSavedMode(false); setAccountBusy(false); }
      const expected = identity.current; setCheckingAccount(true);
      void accountApi.session().then(async (value) => {
        if (!active || identity.current !== expected) return;
        setSession(value); setSavedMode(value.authenticated);
        if (value.authenticated) await loadSaved(expected);
      }).catch((failure: unknown) => { if (active && identity.current === expected && !isCancelled(failure)) setError(failure); })
        .finally(() => { if (active && identity.current === expected) setCheckingAccount(false); });
    }
    checkSession(false);
    // Notify identity changes across tabs without storing credentials or user data.
    if (typeof BroadcastChannel !== 'undefined') {
      const channel = new BroadcastChannel('finweb-account-identity'); accountChannel.current = channel;
      channel.onmessage = (event: MessageEvent) => { if (event.data === 'changed') checkSession(true); };
    }
    const onVisibility = () => {
      if (document.visibilityState === 'visible' && currentSession.current?.authenticated) checkSession(true);
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      active = false; accountApi.onSessionLost = null; accountApi.onGuardedPending = null; accountApi.onGuardedReference = null; accountApi.onGuardedCsvReportReference = null; accountApi.reset();
      document.removeEventListener('visibilitychange', onVisibility);
      accountChannel.current?.close(); accountChannel.current = null;
    };
  }, []);
  async function authenticate(kind: 'register' | 'login', username: string, password: string) {
    const expected = clearWorkspace(true); accountApi.reset(); setSession(null); setSavedMode(false); setAccountBusy(true);
    try {
      const value = await accountApi.authenticate(kind, username, password);
      if (identity.current !== expected) return;
      accountChannel.current?.postMessage('changed');
      setSession(value); setSavedMode(true); navigate('/portfolio');
      await loadSaved(expected);
    } catch (failure) { if (identity.current === expected && !isCancelled(failure)) setError(failure); }
    finally { if (identity.current === expected) setAccountBusy(false); }
  }
  async function logout() {
    const expected = clearWorkspace(true); setSession(null); setSavedMode(false); setAccountBusy(true); navigate('/portfolio');
    try {
      const value = await accountApi.logout();
      if (identity.current === expected) { setSession(value); accountChannel.current?.postMessage('changed'); }
    } catch (failure) { if (identity.current === expected && !isCancelled(failure)) { accountApi.reset(); setError(failure); } }
    finally { if (identity.current === expected) setAccountBusy(false); }
  }
  async function create(input: CreatePortfolio & { operation_id?: string; opening_date?: string }) {
    const expected = identity.current;
    const value = await (savedMode ? accountApi : api).create(input);
    if (identity.current !== expected) return;
    const savedWorkspace = value.persisted ? await accountApi.workspace(value.portfolio_id) : null;
    if (identity.current !== expected) return;
    const displayed = savedWorkspace ? await accountApi.snapshot(value.portfolio_id, savedWorkspace.revision_id) : value;
    if (identity.current !== expected) return;
    setWorkspace(savedWorkspace);
    setSnapshot(displayed); setEvidence(null); setError(null); navigate('/overview');
    if (value.persisted) await loadSaved(expected);
  }
  async function openSaved(id: string, revisionId?: string) {
    const expected = clearWorkspace(); setSavedMode(true); setBusy(true);
    // Express this navigation before I/O. A later user navigation must survive
    // the same owned revision's delayed snapshot response.
    navigate(revisionId ? '/portfolio' : '/overview');
    try {
      const savedWorkspace = await accountApi.workspace(id, revisionId);
      if (identity.current !== expected) return;
      const value = await accountApi.snapshot(id, savedWorkspace.revision_id);
      if (identity.current !== expected) return;
      setSnapshot(value); setWorkspace(savedWorkspace); await loadSaved(expected);
    } catch (failure) { if (identity.current === expected && !isCancelled(failure)) setError(failure); }
    finally { if (identity.current === expected) setBusy(false); }
  }
  function newPortfolio(saved: boolean) {
    const expected = clearWorkspace(); setSavedMode(saved); navigate('/portfolio');
    if (session?.authenticated) void loadSaved(expected).catch((failure: unknown) => { if (identity.current === expected && !isCancelled(failure)) setError(failure); });
  }
  function openRealSourceReadiness() {
    if (!session?.authenticated) return;
    if (profile) { setError(new ApiError('F3_GUARDED_UNSUPPORTED', 'Real data is unavailable in the fictional guarded profile')); return; }
    const expected = clearWorkspace(); readinessEntryLocation.current = location.key; setRealReadinessOpen(true); navigate('/portfolio');
    void loadSaved(expected).catch((failure: unknown) => { if (identity.current === expected && !isCancelled(failure)) setError(failure); });
  }
  async function reload() {
    if (!snapshot) return;
    const expected = identity.current;
    const readEpoch = workspaceReads.current.begin();
    setBusy(true); setError(null);
    try {
      const savedWorkspace = snapshot.persisted ? await accountApi.workspace(snapshot.portfolio_id) : null;
      if (identity.current !== expected || !workspaceReads.current.isCurrent(readEpoch)) return;
      const value = snapshot.persisted ? await accountApi.snapshot(snapshot.portfolio_id, savedWorkspace?.revision_id) : await api.snapshot(snapshot.portfolio_id);
      if (identity.current === expected && workspaceReads.current.isCurrent(readEpoch)) { setSnapshot(value); setWorkspace(savedWorkspace); setEvidence(null); }
    } catch (failure) { if (identity.current === expected && workspaceReads.current.isCurrent(readEpoch) && !isCancelled(failure)) setError(failure); }
    finally { if (identity.current === expected && workspaceReads.current.isCurrent(readEpoch)) setBusy(false); }
  }
  function updateWorkspace(result: WorkspaceResult) {
    workspaceReads.current.invalidate(); setBusy(false);
    setSnapshot(result.snapshot); setWorkspace(result.workspace); setEvidence(null); setError(null); setWorkspaceStatus('revisionSaved');
    const expected = identity.current;
    void loadSaved(expected).catch((failure: unknown) => { if (identity.current === expected && !isCancelled(failure)) setError(failure); });
  }
  function openEvidence(value: Evidence) { if (profile && value.snapshot.persisted) return; setEvidence({ ...value, ...(value.snapshot.persisted && workspace ? { revisionId: workspace.revision_id } : {}) }); }
  async function openHistory(revisionId: string) { if (snapshot?.persisted) await openSaved(snapshot.portfolio_id, revisionId); }
  async function recoverGuarded(result: GuardedCommitted) {
    accountApi.completeGuardedRecovery(result.operation_id);
    const opened = openSaved(result.portfolio_id, result.revision_id); const expected = identity.current;
    await opened; if (identity.current === expected) setWorkspaceStatus('guardedCommitted');
  }
  async function retryGuarded() {
    if (!guardedPending) return;
    const expected = identity.current;
    try { const result = await accountApi.retryGuardedOperation(guardedPending.operationId); if (identity.current === expected) await recoverGuarded(result); }
    catch (failure) { if (identity.current === expected && !isCancelled(failure)) setError(failure); }
  }
  async function recoverCsvReport(result: GuardedCsvReportCommitted) {
    const expected = identity.current;
    accountApi.completeGuardedRecovery(result.operation_id); setGuardedCsvReportReference(result);
    setCsvReportRecovery((value) => value + 1);
    setWorkspaceStatus('guardedCsvReportCommitted'); setError(null);
    try { await accountApi.csvReport(result.portfolio_id, result.report_id); }
    catch (failure) { if (identity.current === expected && !isCancelled(failure)) setError(failure); }
  }
  async function retryCsvReport() {
    if (guardedPending?.kind !== 'CSV_REPORT') return;
    const expected = identity.current;
    try { const result = await accountApi.retryGuardedCsvReportOperation(guardedPending.operationId); if (identity.current === expected) await recoverCsvReport(result); }
    catch (failure) { if (identity.current === expected && !isCancelled(failure)) setError(failure); }
  }
  const surfaces = guardedSurfaces(guardedPending, guardedReference, guardedCsvReportReference);
  const createForm = <CreateForm key={`${identity.current}:${savedMode}:${profile?.profile ?? 'legacy'}`} onCreate={create} saved={savedMode} disabled={checkingAccount || accountBusy} profile={profile} uncertain={guardedPending !== null} />;
  return <>
    <a href="#main-content" className="skip-link">{t('skipContent')}</a>
    <div className={`synthetic-banner${showingRealReadiness ? ' real-source-banner' : ''}`}><strong>{t(showingRealReadiness ? 'realSourceBanner' : 'banner')}</strong><span>{t(showingRealReadiness ? 'realSourceBannerDetail' : 'bannerDetail')}</span></div>
    <header className="app-header"><NavLink to="/overview" className="brand"><span className="brand-emblem" aria-hidden="true">M</span><span><strong>{t('brand')}</strong><small>{t('brandSub')}</small></span></NavLink>
      <nav aria-label={t('primaryNavigation')} className="primary-nav">{['overview', 'portfolio', 'analytics', 'scenario'].map((key) => <NavLink key={key} to={`/${key}`}>{t(key)}{key === 'scenario' && <span className="nav-pending">CP8</span>}</NavLink>)}</nav>
      <label className="language-control"><span className="sr-only">{t('language')}</span><select aria-label={t('language')} value={i18n.language} onChange={(event) => { void i18n.changeLanguage(event.target.value); }}><option value="en">EN</option><option value="zh-CN">简体中文</option></select></label>
    </header>
    <div className="workspace-toolbar"><div className="depth-control" role="group" aria-label={t('explanation')}><span>{t('explanation')}</span>{(['quick', 'simple', 'professional'] as const).map((level) => <button type="button" key={level} aria-pressed={depth === level} onClick={() => setDepth(level)}>{t(level)}</button>)}</div>
      <label className="gain-color-control"><span>{t('gainColor')}</span><select value={gainColors} onChange={(event) => setGainColors(event.target.value as GainColors)}><option value="GREEN_GAIN">{t('gainGreen')}</option><option value="RED_GAIN">{t('gainRed')}</option></select></label>
      <div className="workspace-actions">{snapshot && <button type="button" className="text-button" disabled={busy || accountBusy} onClick={() => { void reload(); }}>{t(busy ? 'refreshing' : 'refresh')}</button>}<button type="button" className="text-button" disabled={busy || accountBusy || profile !== null} title={profile ? t('guardedGuestUnavailable') : undefined} onClick={() => newPortfolio(false)}>{t('startAgain')}</button></div>
    </div>
    <main id="main-content" className="main-content" tabIndex={-1}>
      <div className="async-status" aria-live="polite" role="status">{busy ? t('refreshing') : surfaces.workspaceStatusVisible && workspaceStatus ? t(workspaceStatus) : ''}</div>
      <AccountPanel key={session?.user?.user_id ?? 'guest'} session={session} checking={checkingAccount} busy={accountBusy || busy} portfolios={savedPortfolios}
        onAuthenticate={authenticate} onLogout={() => { void logout(); }} onNewSaved={() => newPortfolio(true)} onOpen={(id) => { void openSaved(id); }}
        onRealSourceReadiness={openRealSourceReadiness}
        onRefresh={() => { const expected = identity.current; void loadSaved(expected).catch((failure: unknown) => { if (identity.current === expected && !isCancelled(failure)) setError(failure); }); }} />
      {error !== null && <ErrorNotice error={error} />}
      {workspace && <div className="revision-strip"><strong>{t(workspace.revision_id === workspace.current_revision_id ? 'currentRevision' : 'historicalRevision')}</strong><code>{workspace.revision_id}</code>
        {workspace.revision_id !== workspace.current_revision_id && <span>{t('historicalReadOnly')}</span>}</div>}
      <Routes>
        <Route path="/scenario" element={<Scenario />} />
        <Route path="/overview" element={snapshot ? <Overview snapshot={snapshot} workspace={workspace} depth={depth} colors={gainColors} onEvidence={openEvidence} /> : createForm} />
        <Route path="/portfolio" element={showingRealReadiness ? <RealSourceReadiness key={identity.current} api={accountApi} authenticated={session?.authenticated === true} depth={depth} onReturn={() => newPortfolio(true)} /> : snapshot ? <Portfolio snapshot={snapshot} workspace={workspace} onUpdate={updateWorkspace} onHistory={openHistory} csvReportRecovery={csvReportRecovery} /> : createForm} />
        <Route path="/analytics" element={snapshot ? <Analytics snapshot={snapshot} workspace={workspace} depth={depth} colors={gainColors} onEvidence={openEvidence} policySupplied={workspace?.policies.state === 'ACTIVE'} /> : createForm} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Routes>
      {profile && session?.authenticated && surfaces.archive.visible && <GuardedArchivePanel key={identity.current} api={accountApi}
        reference={guardedReference} pending={surfaces.archive.pending} onRecovered={(result) => { void recoverGuarded(result); }} onRetry={surfaces.archive.retry ? retryGuarded : undefined} />}
      {profile && session?.authenticated && surfaces.report.visible && <GuardedCsvReportPanel key={`csv-report:${identity.current}`} api={accountApi}
        reference={guardedCsvReportReference} pending={surfaces.report.pending}
        onRecovered={(result) => { void recoverCsvReport(result); }} onRetry={surfaces.report.retry ? retryCsvReport : undefined} />}
    </main>
    <footer className="app-footer"><span>{t('footer')}</span><span>{t('sameFacts')}</span></footer>
    {evidence && <EvidenceDialog evidence={evidence} onClose={() => setEvidence(null)} />}
  </>;
}
