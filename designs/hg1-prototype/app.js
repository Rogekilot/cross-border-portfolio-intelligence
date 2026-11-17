/*
 * app.js — HG1 CP0 prototype. Vanilla JS, no framework, no build step.
 * Renders one surface at a time into #surface-root from data.js.
 */

const SURFACES = [
  "overview",
  "holdings",
  "exposure",
  "risk",
  "transactions",
  "insights",
  "ai",
  "scenario",
  "methodology",
  "settings",
];

const SURFACE_LABELS = {
  overview: "Overview",
  holdings: "Holdings",
  exposure: "Exposure",
  risk: "Risk & Analytics",
  transactions: "Transactions",
  insights: "Insights",
  ai: "AI Analyst",
  scenario: "Scenario Lab",
  methodology: "Methodology & Evidence",
  settings: "Portfolio Settings / Policy",
};

let currentDepth = "investor"; // shared default depth for worked examples

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function fmtMoney(v, currency) {
  const sign = v < 0 ? "-" : "";
  return sign + (currency ? currency + " " : "$") + Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// --------------------------------------------------------------- lookAt

function lookAt(items) {
  return `<div class="look-at"><strong>What to look at here:</strong> ${items.join(" &nbsp;·&nbsp; ")}</div>`;
}

// ---------------------------------------------------------- metric card

function freshnessPillHTML(freshness) {
  if (!freshness) return "";
  const cls = freshness.state === "LIVE" ? "fresh-LIVE" : "";
  const delay = freshness.delay ? ` (${freshness.delay})` : "";
  return `<span class="freshness-pill ${cls}">${esc(freshness.axis)}: ${esc(freshness.state)}${delay}</span>`;
}

function reasonTagHTML(reasonCode) {
  if (!reasonCode) return "";
  return `<span class="reason-tag">${esc(reasonCode)}</span>`;
}

function evidenceButtonHTML(methodologyId, label) {
  if (!methodologyId) return "";
  return `<button class="evidence-btn" onclick="openMethodology('${methodologyId}')">Evidence (D4)${label ? " — " + esc(label) : ""}</button>`;
}

/**
 * Render one metric as a card, per §D3.2's per-state rendering rules.
 * metric: {id, label, unit, state, value, qualifier, reasonCode, referencePoint, freshness, methodologyId, explanation}
 */
function metricCardHTML(metric, opts) {
  opts = opts || {};
  const state = metric.state;
  let inner = "";
  const unit = metric.unit || "";
  const valStr = metric.value === null || metric.value === undefined
    ? ""
    : (typeof metric.value === "number" ? metric.value.toLocaleString() : metric.value);

  if (state === "AVAILABLE") {
    inner = `<div class="metric-value">${esc(valStr)}${unit ? " " + esc(unit) : ""}</div>`;
    if (metric.referencePoint) inner += `<div class="metric-refpoint">${esc(metric.referencePoint)}</div>`;
    if (metric.reasonCode === "STALE_DATA" && metric.freshness) {
      inner += freshnessPillHTML({ axis: metric.freshness.leastFreshAxis || metric.freshness.axis, state: metric.freshness.leastFreshState || metric.freshness.state, delay: metric.freshness.delay });
    } else if (metric.freshness && metric.freshness.axis) {
      inner += freshnessPillHTML(metric.freshness);
    }
  } else if (state === "LIMITED") {
    inner = `<div class="metric-value">${esc(valStr)}${unit ? " " + esc(unit) : ""}</div>`;
    if (metric.referencePoint) inner += `<div class="metric-refpoint">${esc(metric.referencePoint)}</div>`;
    inner += `<div class="limited-qualifier">&#9888; LIMITED — ${esc(metric.qualifier || "")}${reasonTagHTML(metric.reasonCode)}</div>`;
  } else if (state === "INSUFFICIENT_DATA") {
    inner = `<div class="insufficient-data-render">&mdash; insufficient data${reasonTagHTML(metric.reasonCode)}</div>`;
    inner += `<div class="insufficient-data-explain">${esc(metric.explanation || "")}</div>`;
  } else {
    inner = `<div class="metric-value placeholder-value">n/a</div>`;
  }

  const evidence = opts.noEvidence ? "" : evidenceButtonHTML(metric.methodologyId);

  return `
    <div class="metric-card state-${esc(state)}">
      <div class="metric-label"><span>${esc(metric.label)}</span>${evidence}</div>
      ${inner}
    </div>`;
}

// --------------------------------------------------------- evidence modal

function openMethodology(methodologyId) {
  const rows = METHODOLOGY_FIELDS.map((f) => {
    const label = f.replace(/_/g, " ");
    return `<div class="field-row"><div class="field-name">${esc(label)}</div><div class="placeholder-value">— not yet published (registry ships empty, AC-17)</div></div>`;
  }).join("");
  showModal(`
    <button class="modal-close" onclick="closeModal()">&times;</button>
    <h2>Methodology view <span class="tag-empty-registry">EMPTY REGISTRY — AC-17</span></h2>
    <p style="font-size:12.5px;color:#5b6674;">Destination: Methodology &amp; Evidence surface, entry <code>${esc(methodologyId)}</code>.
    This increment ships the registry schema and validator with <strong>zero entries</strong> by design
    (specs/FEATURE_PRD.md §3.3, AC-17). The fifteen §33 fields below are shown to demonstrate
    structure only — every value is a placeholder, not fabricated content.</p>
    ${rows}
  `);
}

function openProofPacket(packetId) {
  const pkt = PROOF_PACKETS[packetId];
  if (!pkt) return;
  const scenarioNote = pkt.scenario_id
    ? `<div class="hypothetical-badge">SCENARIO — hypothetical (${esc(pkt.scenario_id)})</div>`
    : "";
  const rows = PROOF_PACKET_FIELDS.map((f) => {
    const v = pkt[f];
    const display = v === null || v === undefined || v === "" ? `<span class="placeholder-value">— n/a</span>` : esc(Array.isArray(v) ? v.join(", ") : v);
    return `<div class="field-row"><div class="field-name">${esc(f)}</div><div>${display}</div></div>`;
  }).join("");
  showModal(`
    <button class="modal-close" onclick="closeModal()">&times;</button>
    <h2>Proof Packet <span class="tag-empty-registry">SYNTHETIC</span></h2>
    ${scenarioNote}
    <p style="font-size:12.5px;color:#5b6674;">§21 minimum conceptual schema, filled with illustrative synthetic content for this prototype only.</p>
    ${rows}
  `);
}

function showModal(html) {
  document.getElementById("modal-box").innerHTML = html;
  document.getElementById("modal-backdrop").classList.add("open");
}

function closeModal() {
  document.getElementById("modal-backdrop").classList.remove("open");
}

// ------------------------------------------------------------ depth toggle

function depthToggleHTML(exampleId) {
  const levels = ["quick", "simple", "investor", "professional"];
  const btns = levels
    .map((lv) => `<button class="depth-btn ${lv === currentDepth ? "active" : ""}" data-example="${exampleId}" data-level="${lv}" onclick="setDepth(this)">${lv[0].toUpperCase() + lv.slice(1)}</button>`)
    .join("");
  return `<div class="depth-toggle">${btns}</div>`;
}

function setDepth(btn) {
  const level = btn.getAttribute("data-level");
  currentDepth = level;
  renderSurface(); // re-render whole surface at new shared depth
}

function workedExampleHTML(ex) {
  const content = ex.levels[currentDepth];
  return `
    <div class="worked-example">
      <div class="metric-label"><strong>${esc(ex.title)}</strong></div>
      ${depthToggleHTML(ex.id)}
      <div class="depth-conclusion"><strong>${currentDepth[0].toUpperCase() + currentDepth.slice(1)}:</strong> ${esc(content.conclusion)}</div>
      <div class="depth-caveat">${esc(content.caveat)}</div>
      <div class="must-not-say"><strong>Must NOT say:</strong> ${esc(ex.mustNotSay)}</div>
    </div>`;
}

// ------------------------------------------------------------------- nav

function renderNav() {
  const nav = document.getElementById("surface-nav");
  nav.innerHTML =
    SURFACES.map((s) => `<button data-surface="${s}" class="${s === activeSurface ? "active" : ""}" onclick="switchSurface('${s}')">${esc(SURFACE_LABELS[s])}</button>`).join("") +
    `<button class="gaps-tab ${activeSurface === "gaps" ? "active" : ""}" onclick="switchSurface('gaps')">Contract Checks &amp; Known Gaps</button>`;
}

let activeSurface = "overview";

function switchSurface(s) {
  activeSurface = s;
  renderSurface();
}

function renderSurface() {
  renderNav();
  const root = document.getElementById("surface-root");
  const fn = RENDERERS[activeSurface];
  root.innerHTML = fn ? fn() : "<p>Unknown surface.</p>";
}

// =====================================================================
// Surface renderers
// =====================================================================

const RENDERERS = {
  overview: renderOverview,
  holdings: renderHoldings,
  exposure: renderExposure,
  risk: renderRisk,
  transactions: renderTransactions,
  insights: renderInsights,
  ai: renderAI,
  scenario: renderScenario,
  methodology: renderMethodology,
  settings: renderSettings,
  gaps: renderGaps,
};

function renderOverview() {
  return `
    <h1 class="surface-title">1. Overview</h1>
    <p class="surface-purpose">The single-glance answer to "where do I stand." §26.</p>
    ${lookAt([
      "(1) AVAILABLE plain — Gain/Loss card",
      "(2) AVAILABLE + STALE_DATA — Total Portfolio Value (identical numeric styling; freshness pill carries the distinction)",
      "(5) D4 evidence — value/gain-loss carry their own control; risk snapshot below shares the SAME claim object as Risk &amp; Analytics (click Evidence in both places)",
    ])}
    <div class="panel">
      <h2>Total Portfolio Value <span style="font-weight:400;color:#5b6674;font-size:12px;">— aggregation-only claim (§D1 Overview item 1, own D4 control)</span></h2>
      <div class="grid">
        ${metricCardHTML(METRICS.total_portfolio_value)}
        ${metricCardHTML(METRICS.portfolio_gain_loss)}
      </div>
      <div class="isolation-note">Portfolio-level rollup names the <strong>least-fresh axis</strong> (D5.4) rather than blending into one "Live" label. See per-axis detail below.</div>
      <details style="margin-top:8px;font-size:12px;">
        <summary style="cursor:pointer;color:#1f5fa8;">Per-axis freshness detail (D5.1)</summary>
        <ul>${METRICS.total_portfolio_value.freshness.axes.map((a) => `<li>${esc(a.axis)}: <strong>${esc(a.state)}</strong>${a.delay ? " (" + esc(a.delay) + ")" : ""}</li>`).join("")}</ul>
      </details>
    </div>

    <div class="panel">
      <h2>Risk snapshot <span style="font-weight:400;color:#5b6674;font-size:12px;">— same claim object as Risk &amp; Analytics's Beta card (D2.2/D4.1 inheritance)</span></h2>
      <div class="grid">${metricCardHTML(METRICS.risk_snapshot_beta)}</div>
    </div>

    <div class="panel">
      <h2>Top Insights <span style="font-weight:400;color:#5b6674;font-size:12px;">— Insights surface owns the full list</span></h2>
      <ul>${INSIGHTS.slice(0, 2).map((i) => `<li><span class="badge badge-${i.severity.toLowerCase()}">${esc(i.severity)}</span> ${esc(i.claim)}</li>`).join("")}</ul>
    </div>

    <div class="panel">
      <h2>Portfolio Brief / Ask Your Portfolio</h2>
      <p style="font-size:12.5px;color:#5b6674;">Entry points only — the claim itself renders once, on <a href="#" onclick="switchSurface('ai');return false;">AI Analyst</a>.</p>
    </div>

    <div class="isolation-note">
      <strong>P8 isolation:</strong> this surface never renders Scenario Lab hypothetical data. There is no toggle
      anywhere on this screen that would show a <code>SCENARIO</code>-typed claim — by design, there is no code path.
      See <a href="#" onclick="switchSurface('scenario');return false;">Scenario Lab</a>.
    </div>
  `;
}

function holdingRowD3(h) {
  if (h.kind === "cash") {
    return `<td>${fmtMoney(h.marketValueNative, h.currency)}</td><td colspan="2" style="color:#9aa2ac;font-style:italic;">fact — no D3/D4 (not a judgment)</td>`;
  }
  const g = h.gainLoss;
  let cell;
  if (g.state === "AVAILABLE") {
    cell = `<span class="metric-value" style="font-size:14px;">${fmtMoney(g.value, h.currency)}</span>${g.reasonCode ? reasonTagHTML(g.reasonCode) : ""}`;
    if (g.reasonCode === "STALE_DATA") cell += `<br>${freshnessPillHTML(h.freshness)}`;
  } else if (g.state === "LIMITED") {
    cell = `<span class="metric-value" style="font-size:14px;color:#9a6400;">${fmtMoney(g.value, h.currency)}</span><div class="limited-qualifier" style="margin-top:3px;">&#9888; ${esc(g.qualifier)}</div>`;
  } else {
    cell = `<span class="insufficient-data-render">&mdash; insufficient data${reasonTagHTML(g.reasonCode)}</span><div class="insufficient-data-explain">${esc(g.explanation)}</div>`;
  }
  return `<td>${fmtMoney(h.marketValueNative, h.currency)} <span style="color:#9aa2ac;">(${fmtMoney(h.marketValueReporting)})</span><br>${freshnessPillHTML(h.freshness)}</td><td>${cell}</td><td>${evidenceButtonHTML("meth_cost_basis_" + h.id)}</td>`;
}

function renderHoldings() {
  return `
    <h1 class="surface-title">2. Holdings</h1>
    <p class="surface-purpose">The ledger-derived truth of what is actually held, at position granularity.</p>
    ${lookAt([
      "(3) LIMITED — Tencent (0700.HK) unrealized gain: value + mandatory qualifier, same visual unit",
      "(4) INSUFFICIENT_DATA — Kweichow Moutai (600519.SS): no numeric glyph at all",
      "(2) AVAILABLE + STALE_DATA — Alibaba (9988.HK)",
      "(10) PD-0006 — MISSING_COST_BASIS (five-code group) never accompanies AVAILABLE",
      "(8) PD-0008 — this table is exactly 7 rows, the number the AI must slot rather than free-type",
    ])}
    <div class="panel">
      <table class="data-table">
        <thead><tr><th>Instrument / Market</th><th>Qty</th><th>Market Value (native / reporting)</th><th>Cost basis &amp; Gain/Loss</th><th></th></tr></thead>
        <tbody>
          ${HOLDINGS.map(
            (h) => `<tr>
              <td><strong>${esc(h.ticker)}</strong><br><span style="color:#5b6674;">${esc(h.name)} · ${esc(h.market)}</span></td>
              <td>${h.quantity === null ? "—" : h.quantity}</td>
              ${holdingRowD3(h)}
            </tr>`
          ).join("")}
        </tbody>
      </table>
    </div>
    <div class="isolation-note">
      <strong>P8 isolation:</strong> Holdings renders only the actual, ledger-derived state. Structurally, there is
      no code path by which a <code>SCENARIO</code> claim reaches this surface — see <a href="#" onclick="switchSurface('scenario');return false;">Scenario Lab</a>.
    </div>
  `;
}

function exposureBarsHTML(items) {
  return items.map((i) => `<div style="margin-bottom:6px;"><div style="display:flex;justify-content:space-between;font-size:12px;"><span>${esc(i.label)}</span><span>${i.pct}%</span></div><div style="background:#eef0f2;border-radius:4px;height:8px;"><div style="width:${i.pct}%;background:#1f5fa8;height:8px;border-radius:4px;"></div></div></div>`).join("");
}

let exposureView = "listing";

function toggleExposureView() {
  exposureView = exposureView === "listing" ? "geo" : "listing";
  renderSurface();
}

function renderExposure() {
  const corrEx = WORKED_EXAMPLES.find((e) => e.id === "correlation");
  return `
    <h1 class="surface-title">4. Exposure</h1>
    <p class="surface-purpose">Where risk actually sits, separated from where securities are listed (§10.3/§10.4).</p>
    ${lookAt([
      "§10.4 — listing-market vs economic-geography, never merged into one number (toggle, not blended)",
      "(3) LIMITED — Effective N",
      "(6) Depth ladder — Correlation worked example (corrected Quick wording, closing NF-2)",
      "(5) D4 evidence — explicit line for this surface (own §D1 item 5)",
    ])}
    <div class="panel">
      <h2>Exposure view</h2>
      <button class="toggle-btn" onclick="toggleExposureView()">Currently: ${exposureView === "listing" ? "Listing-market" : "Economic-geography"} — click to toggle</button>
      ${exposureBarsHTML(exposureView === "listing" ? EXPOSURE.byListingMarket : EXPOSURE.byEconomicGeography)}
      <p style="font-size:11.5px;color:#5b6674;">These two views are never merged into one number (§10.4, rule §44.12) — a US-listed ADR of a China-domiciled company is not "US exposure."</p>
    </div>
    <div class="panel">
      <h2>Sector / Currency exposure</h2>
      <h3>Sector</h3>${exposureBarsHTML(EXPOSURE.bySector)}
      <h3>Currency</h3>${exposureBarsHTML(EXPOSURE.byCurrency)}
    </div>
    <div class="panel">
      <h2>Concentration</h2>
      <div class="grid">${metricCardHTML(METRICS.effective_n)}${metricCardHTML(METRICS.hhi)}${metricCardHTML(METRICS.aapl_weight)}</div>
    </div>
    <div class="panel">
      <h2>Correlation — depth ladder (worked example 2)</h2>
      ${workedExampleHTML(corrEx)}
    </div>
  `;
}

function renderRisk() {
  const betaEx = WORKED_EXAMPLES.find((e) => e.id === "beta");
  const alphaEx = WORKED_EXAMPLES.find((e) => e.id === "alpha");
  return `
    <h1 class="surface-title">5. Risk &amp; Analytics</h1>
    <p class="surface-purpose">The professional risk metric surface — every metric traces to a methodology registry entry (§16.3).</p>
    ${lookAt([
      "(1) AVAILABLE plain — Volatility, Sharpe, Sortino, Max Drawdown",
      "(3) LIMITED — Beta (thin sample)",
      "(6) Depth ladder — Beta and negative-Alpha worked examples",
      "(5) D4 — Methodology link on every metric card (own §D1 text)",
      "CALCULATION_ERROR is intentionally NOT demonstrated as a resolved card here — see Contract Checks &amp; Known Gaps",
    ])}
    <div class="panel">
      <h2>Core metrics</h2>
      <div class="grid">
        ${metricCardHTML(METRICS.volatility)}
        ${metricCardHTML(METRICS.sharpe)}
        ${metricCardHTML(METRICS.sortino)}
        ${metricCardHTML(METRICS.max_drawdown)}
      </div>
    </div>
    <div class="panel">
      <h2>Beta — depth ladder (worked example 1)</h2>
      ${workedExampleHTML(betaEx)}
      ${metricCardHTML(METRICS.risk_snapshot_beta)}
    </div>
    <div class="panel">
      <h2>Jensen's Alpha — depth ladder (worked example 3)</h2>
      ${workedExampleHTML(alphaEx)}
    </div>
    <div class="panel">
      <h2>Advanced V1 metrics (Professional depth only)</h2>
      <p style="font-size:12.5px;">Tracking Error, VaR, rolling metrics — not default-visible at Investor depth or below (§26).</p>
      <p style="font-size:12px;color:#9c2b2b;">Tracking Error hit a CALCULATION_ERROR in this mock scenario. Whether it should render LIMITED-with-a-value or INSUFFICIENT_DATA is unsettled (NF-5/N-17) — see <a href="#" onclick="switchSurface('gaps');return false;" style="color:#9c2b2b;">Contract Checks &amp; Known Gaps</a> rather than a resolved card here.</p>
    </div>
  `;
}

function renderTransactions() {
  const rows = [
    { date: "2026-06-02", account: "US Broker", ticker: "AAPL", qty: 120, price: "150.00 USD", fxNote: null, computed: { state: "AVAILABLE", value: "18,000.00 USD", methodologyId: "meth_fx_conversion" } },
    { date: "2026-07-14", account: "China Brokerage", ticker: "600519.SS", qty: 50, price: "1,600.00 CNY", fxNote: "converted at trade-date FX", computed: { state: "AVAILABLE", value: "222.85 USD", methodologyId: "meth_fx_conversion" } },
    { date: "2026-08-20", account: "Futu HK", ticker: "0700.HK", qty: 300, price: "300.00 HKD", fxNote: "FX history missing for this date", computed: { state: "INSUFFICIENT_DATA", reasonCode: "MISSING_FX_HISTORY", explanation: "No USD/HKD FX rate on record for 2026-08-20; reporting-currency value cannot be shown." } },
  ];
  return `
    <h1 class="surface-title">9. Transactions</h1>
    <p class="surface-purpose">The ledger input surface — where transactions are entered and imported.</p>
    ${lookAt([
      "(4)/(10) INSUFFICIENT_DATA + MISSING_FX_HISTORY — row 3's reporting-currency conversion",
      "D4 scoped narrowly: only the computed FX-conversion column carries evidence; raw entered fields do not (they are facts)",
    ])}
    <div class="panel">
      <table class="data-table">
        <thead><tr><th>Date</th><th>Account</th><th>Ticker</th><th>Qty</th><th>Native price</th><th>Reporting-currency value (computed)</th></tr></thead>
        <tbody>
          ${rows.map((r) => {
            let cell;
            if (r.computed.state === "AVAILABLE") {
              cell = `<span class="metric-value" style="font-size:14px;">${esc(r.computed.value)}</span> ${evidenceButtonHTML(r.computed.methodologyId)}`;
            } else {
              cell = `<span class="insufficient-data-render">&mdash; insufficient data${reasonTagHTML(r.computed.reasonCode)}</span><div class="insufficient-data-explain">${esc(r.computed.explanation)}</div>`;
            }
            return `<tr><td>${r.date}</td><td>${r.account}</td><td>${r.ticker}</td><td>${r.qty}</td><td>${r.price}</td><td>${cell}</td></tr>`;
          }).join("")}
        </tbody>
      </table>
      <p style="font-size:11.5px;color:#5b6674;margin-top:8px;">Date, account, ticker, quantity, native price are entered/imported facts — not claims, no D4 control. Only the computed reporting-currency conversion is registry-traced.</p>
    </div>
    <div class="panel">
      <h2>Entry / import</h2>
      <button class="mock-btn" disabled>+ Add transaction</button>
      <button class="mock-btn" disabled>Import CSV</button>
      <p style="font-size:11.5px;color:#5b6674;">Presence and position only — forms are out of visual-design scope for this increment.</p>
    </div>
  `;
}

function renderInsights() {
  return `
    <h1 class="surface-title">6. Insights</h1>
    <p class="surface-purpose">Proactively generated, severity-ranked observations (§20).</p>
    ${lookAt([
      "(5) D4 — each insight opens a Proof Packet (not a Methodology view — insights are generated claims)",
      "P4 reference points: user policy vs. own history vs. benchmark, shown per insight",
      "Drift subtype (§19) marked distinctly",
    ])}
    ${INSIGHTS.map(
      (i) => `<div class="panel">
        <div class="metric-label">
          <span><span class="badge badge-${i.severity.toLowerCase()}">${esc(i.severity)}</span> ${i.driftType ? `<span class="badge" style="background:#eef0f2;color:#5b6674;">${esc(i.driftType)}</span>` : ""} <span style="color:#5b6674;font-size:11px;">${esc(i.judgmentClass)}</span></span>
          ${evidenceButtonHTML(null)}
          <button class="evidence-btn" onclick="openProofPacket('${i.proofPacketId}')">Evidence (D4) — Proof Packet</button>
        </div>
        <p style="margin:8px 0 4px;">${esc(i.claim)}</p>
        <p style="font-size:11.5px;color:#5b6674;">Reference point: ${esc(i.referencePoint)}</p>
      </div>`
    ).join("")}
  `;
}

function chipHTML(metricId) {
  const m = METRICS[metricId] || {};
  const call = AI_TOOL_CALLS[metricId];
  const label = metricId === "position_count" ? POSITION_COUNT : metricId === "market_count" ? MARKET_COUNT : metricId === "policy_limit" ? "25%" : (m.value + (m.unit ? " " + m.unit : ""));
  const cls = m.state === "LIMITED" ? "chip-LIMITED" : "";
  return `<span class="citation-chip ${cls}" onclick="openToolCall('${metricId}')">${esc(label)}</span>`;
}

function openToolCall(metricId) {
  const call = AI_TOOL_CALLS[metricId];
  if (!call) return;
  showModal(`
    <button class="modal-close" onclick="closeModal()">&times;</button>
    <h2>Logged tool call (P1 boundary)</h2>
    <p style="font-size:12.5px;color:#5b6674;">The AI did not type this number. It resolved a slot against a logged, deterministic tool call:</p>
    <div class="field-row"><div class="field-name">call</div><div><code>${esc(call.call)}</code></div></div>
    <div class="field-row"><div class="field-name">result</div><div><code>${esc(call.result)}</code></div></div>
  `);
}

function renderNarrative(text) {
  return esc(text)
    .replace(/\{\{chip:(\w+)\}\}/g, (m, id) => chipHTML(id))
    .replace(/top 3 holdings/g, '<span class="selector-text">top 3 holdings</span>');
}
// esc() already escaped braces? No — esc only escapes & < > " which does not
// touch {{ }}, so the replace above runs on the escaped string safely.

function renderAI() {
  return `
    <h1 class="surface-title">8. AI Analyst</h1>
    <p class="surface-purpose">Conversational access to the same deterministic facts (§22).</p>
    ${lookAt([
      "(7) P1 boundary — every number is a citation chip resolving to a logged tool call; click a chip",
      "(8) PD-0008 — \"top 3 holdings\" (selector, plain text) vs \"7 positions / 3 markets\" (claim, chip)",
      "Chips carry their metric's own state — the LIMITED beta chip stays visibly LIMITED even inside AI prose",
    ])}
    <div class="legend-row">
      <span class="legend-swatch"><span class="citation-chip">1.30</span> AVAILABLE claim (slotted)</span>
      <span class="legend-swatch"><span class="citation-chip chip-LIMITED">1.30</span> LIMITED claim (slotted, qualifier travels with it)</span>
      <span class="legend-swatch"><span class="selector-text">top 3 holdings</span> selector (free text, not a claim — PD-0008)</span>
    </div>
    <div class="panel">
      <div class="chat-bubble chat-user">How risky is my portfolio right now, and what should I look at first?</div>
      <div class="chat-bubble chat-ai">${renderNarrative(AI_NARRATIVE[currentDepth])}</div>
      ${depthToggleHTML("ai")}
      <p style="font-size:11.5px;color:#5b6674;">${esc(AI_SELECTOR_NOTE)}</p>
    </div>
  `;
}

function renderScenario() {
  return `
    <h1 class="surface-title">7. Scenario Lab</h1>
    <p class="surface-purpose">Hypothetical portfolio modification and comparison — never mutates the actual ledger (§24).</p>
    ${lookAt([
      "(11) P8 isolation — persistent, non-dismissible ACTUAL vs SCENARIO separation",
      "(4)/(10) INSUFFICIENT_DATA — hypothetical instrument has no price history; a scenario does not exempt suppression",
      "(5) D4 on both columns — the Scenario Proof Packet is visibly stamped hypothetical (scenario_id), never rendered as if it were a holding",
    ])}
    <div class="panel">
      <h2>${esc(SCENARIO.description)}</h2>
      <button class="mock-btn" disabled>Reduce position weight</button>
      <button class="mock-btn" disabled>Remove position</button>
      <button class="mock-btn" disabled>Add hypothetical instrument</button>
      <button class="mock-btn" disabled>Increase cash</button>
      <button class="mock-btn" disabled>Shift exposure</button>
      <button class="mock-btn" disabled>Enforce concentration constraint</button>
      <p style="font-size:11px;color:#5b6674;">Controls shown for structure only — not wired in this prototype.</p>
    </div>
    ${SCENARIO.comparison.map((row) => `
      <div class="scenario-row-label">${esc(row.metric)}</div>
      <div class="scenario-columns">
        <div>
          <div class="col-header actual">ACTUAL</div>
          <div class="scenario-cell-wrap">
            <span class="actual-badge">CURRENT PORTFOLIO</span>
            ${row.actual.state ? metricCardHTML({ label: "", state: row.actual.state, value: row.actual.value, qualifier: row.actual.qualifier }, { noEvidence: true }) : '<p style="font-size:12px;color:#9aa2ac;font-style:italic;">Does not exist in the actual portfolio.</p>'}
          </div>
        </div>
        <div>
          <div class="col-header scenario">SCENARIO</div>
          <div class="scenario-cell-wrap is-scenario">
            <span class="hypothetical-badge">HYPOTHETICAL — ${esc(SCENARIO.id)}</span>
            ${metricCardHTML({ label: "", state: row.scenario.state, value: row.scenario.value, qualifier: row.scenario.qualifier, reasonCode: row.scenario.reasonCode, explanation: row.scenario.explanation }, { noEvidence: true })}
            <button class="evidence-btn" onclick="openProofPacket('${SCENARIO.proofPacketId}')" style="margin-top:6px;">Evidence (D4) — Proof Packet</button>
          </div>
        </div>
      </div>
    `).join("")}
    <div class="isolation-note">
      Try switching to <a href="#" onclick="switchSurface('overview');return false;">Overview</a> or
      <a href="#" onclick="switchSurface('holdings');return false;">Holdings</a> — there is no control anywhere
      in this prototype that shows this scenario's figures there. Per P8, that is not a missing feature; there is
      no code path, structurally, by which a <code>SCENARIO</code> claim reaches those two surfaces.
    </div>
  `;
}

function renderMethodology() {
  return `
    <h1 class="surface-title">11. Methodology &amp; Evidence</h1>
    <p class="surface-purpose">The destination of the D4 evidence path — the audit trail's UI, not a help page.</p>
    ${lookAt([
      "(5) The registry ships EMPTY in this increment (AC-17) — every entry below is a labelled placeholder",
      "This surface does NOT have its own D4 control pointing at itself — see note below",
    ])}
    <div class="panel">
      <h2>Registry entries <span class="tag-empty-registry">0 published entries — AC-17</span></h2>
      <table class="data-table">
        <thead><tr><th>Metric</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${METHODOLOGY_REGISTRY_NAMES.map((id) => `<tr><td><code>${esc(id)}</code></td><td><span class="tag-empty-registry">not yet published</span></td><td><button class="evidence-btn" onclick="openMethodology('${id}')">View structure</button></td></tr>`).join("")}
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h2>Proof Packet — synthetic example</h2>
      <button class="evidence-btn" onclick="openProofPacket('pp_vol_observation')">Open example Proof Packet</button>
    </div>
    <div class="no-d4-note">
      <strong>Why no evidence link here (D1 surface 11 disposition, option (c)):</strong> this surface is the
      destination D4 points <em>to</em>. A methodology entry documents method in general, not a portfolio-specific
      judgment — it is what the methodology pointer points at, not a fourth field needing its own pointer. A Proof
      Packet renders evidence for a claim that lives on another surface. Requiring D4 to point at itself would not
      terminate the audit trail P9 requires; arriving here is the termination.
    </div>
  `;
}

function renderSettings() {
  return `
    <h1 class="surface-title">10. Portfolio Settings / Policy</h1>
    <p class="surface-purpose">Reporting currency, accounts, and Portfolio Policy (§25) — user-authored inputs.</p>
    ${lookAt([
      "P7 — an unset policy field is disclosed explicitly, not filled with an invented threshold",
      "This surface displays no claims in D2.2's sense — no D4 control anywhere (disposition (c))",
    ])}
    <div class="panel">
      <h2>Reporting currency</h2>
      <p>${esc(POLICY.reportingCurrency)} (mock selector)</p>
    </div>
    <div class="panel">
      <h2>Accounts</h2>
      <ul>${POLICY.accounts.map((a) => `<li>${esc(a.name)} — ${esc(a.market)} — ${esc(a.currency)}</li>`).join("")}</ul>
    </div>
    <div class="panel">
      <h2>Portfolio Policy</h2>
      <table class="data-table">
        <tbody>
          ${POLICY.fields.map((f) => `<tr><td>${esc(f.label)}</td><td>${f.set ? `<strong>${esc(f.value)}</strong>` : `<span class="placeholder-value">unset</span> — <span style="font-size:11px;color:#5b6674;">the product will use comparative/educational language here, never an invented personal threshold (P7)</span>`}</td></tr>`).join("")}
        </tbody>
      </table>
    </div>
    <div class="no-d4-note">This surface only records your own choices; it makes no claims about your portfolio to audit — see design doc §D1 surface 10.</div>
  `;
}

// ------------------------------------------------------------------ Gaps

function runContractChecks() {
  const results = [];
  function collect(id, m) {
    if (!m || !m.state) return;
    // PD-0007: value is None <=> INSUFFICIENT_DATA
    const hasValue = m.value !== null && m.value !== undefined;
    const pd7ok = m.state === "INSUFFICIENT_DATA" ? !hasValue : hasValue;
    results.push({ id, rule: "PD-0007 value⇔INSUFFICIENT_DATA", pass: pd7ok });
    // PD-0006 second amendment: five reason codes ⇒ non-AVAILABLE
    if (m.reasonCode && NON_AVAILABLE_REASON_CODES.includes(m.reasonCode)) {
      results.push({ id, rule: `PD-0006 ${m.reasonCode} ⇒ non-AVAILABLE`, pass: m.state !== "AVAILABLE" });
    }
    if (m.reasonCode === "STALE_DATA") {
      results.push({ id, rule: "PD-0006 STALE_DATA legal with AVAILABLE", pass: m.state === "AVAILABLE" || m.state === "LIMITED" });
    }
  }
  Object.values(METRICS).forEach((m) => collect(m.id, m));
  HOLDINGS.forEach((h) => h.gainLoss && collect(h.id + "_gain", h.gainLoss));
  return results;
}

function renderGaps() {
  const checks = runContractChecks();
  const allPass = checks.every((c) => c.pass);
  return `
    <h1 class="surface-title">Contract Checks &amp; Known Gaps</h1>
    <p class="surface-purpose">A prototype tool, not one of the eleven product surfaces — kept separate so it is never mistaken for one.</p>
    <div class="panel">
      <h2>Live contract checks (PD-0006 / PD-0007) — ${allPass ? '<span class="check-pass">ALL PASS</span>' : '<span class="check-fail">FAILURES FOUND</span>'}</h2>
      ${checks.map((c) => `<div class="check-row"><span>${esc(c.id)} — ${esc(c.rule)}</span><span class="${c.pass ? "check-pass" : "check-fail"}">${c.pass ? "PASS" : "FAIL"}</span></div>`).join("")}
      <p style="font-size:11px;color:#5b6674;margin-top:8px;">Computed at page load from data.js's own mock objects — a live, inspectable demonstration that the contract's rules are mechanically checkable, not just asserted in prose.</p>
    </div>
    ${KNOWN_GAPS.map(
      (g) => `<div class="gap-card">
        <h3>${esc(g.title)}<span class="gap-marker">UNRESOLVED</span></h3>
        <p style="font-size:12.5px;">${esc(g.body)}</p>
        ${
          g.renderings
            ? `<div class="grid">${g.renderings
                .map((r) => `<div>${metricCardHTML({ label: r.label, state: r.state, value: r.value, qualifier: r.qualifier, reasonCode: r.reasonCode, explanation: r.explanation }, { noEvidence: true })}</div>`)
                .join("")}</div><p style="font-size:11px;color:#9c2b2b;">Neither rendering above is asserted as correct — both are mechanically legal under today's decided rules; which one belongs here is quant_analyst's call and has not been made.</p>`
            : ""
        }
      </div>`
    ).join("")}
  `;
}

// ------------------------------------------------------------------ boot

document.addEventListener("DOMContentLoaded", () => {
  renderSurface();
  document.getElementById("modal-backdrop").addEventListener("click", (e) => {
    if (e.target.id === "modal-backdrop") closeModal();
  });
});
