/*
 * shell.js — application shell, router, and shared UI primitives.
 * Owned by designer-09 (phase 1). Do not edit from js/surfaces/*, js/ai.js, js/evidence.js.
 * See ../CONTRACT.md for the full, authoritative contract this file implements.
 *
 * Load order requirement: this file MUST be the first <script> in index.html after
 * nothing (it defines window.APP before any other module runs). data.js and charts.js
 * attach their own namespaces onto window.APP and may load in either order relative to
 * each other, but both must load AFTER this file and BEFORE any surface module.
 *
 * Zero dependencies. Zero build step. Plain global script, no ES modules.
 */
(function () {
  "use strict";

  window.APP = window.APP || {};
  var APP = window.APP;
  // CONTRACT.md §1's namespace-initialization rule, applied at the top of this file's
  // own IIFE, before ANY assignment into APP.ui — not at the point this file first
  // happened to need it. Fix for a real regression: a round-4 edit added
  // `APP.ui.getColorConvention = ...` (and two siblings) far above this file's own
  // original `APP.ui = APP.ui || {}` line, which aborted this entire IIFE on load
  // ("Cannot set properties of undefined") before registerSurface/registerAI/
  // registerEvidence were ever defined — every surface's registration call then failed
  // against a function that didn't exist, and the app rendered header/footer only. This
  // is the exact failure mode CONTRACT.md's rule already names (charts.js's own earlier
  // instance of it): the rule is "create the namespace first, unconditionally, before
  // any incremental write to it," not "create the namespace somewhere in the file."
  APP.ui = APP.ui || {};

  // ---------------------------------------------------------------------
  // Internal registries (private — surfaces must use the register* functions)
  // ---------------------------------------------------------------------
  var _surfaces = {};          // key -> config
  var _aiHandler = null;       // { renderPanel(mountEl, context) }
  var _evidenceHandler = null; // { open(claimId, mountEl) }
  var _inspectorPayload = null;

  // =======================================================================
  // Bilingual V1 support (PD-0012 §3, feedback log §12) — English | 简体中文.
  //
  // SCOPE, STATED PLAINLY (see this designer's handoff for the full account): this
  // dictionary covers structural/navigational "chrome" — nav, table headers, badges,
  // depth-ladder labels, freshness words, Settings (including the three new PD-0012
  // controls), Evidence & Methodology section headers, common buttons, Scenario Lab's
  // own static chrome, and the OCR ingestion workflow labels §12 names explicitly.
  // It does NOT translate dynamic claim narrative (conclusionQuick/explanationSimple/
  // professionalDetail/caveat/insight text) — that content is authored in js/data.js,
  // which is outside this designer's write path (owned by designer-19). Translating
  // only the connective words around untranslated claim text would silently produce
  // mixed-language sentences, which is worse than staying English — so those sentences
  // stay English in both language settings until data.js can carry parallel content or
  // a real translation layer exists. This is reported as an explicit, bounded gap, not
  // silently left incomplete (§28's discipline: document what was and wasn't done).
  //
  // Layer separation (§12.1, honored structurally): interface language (this
  // dictionary) / professional financial terminology (also this dictionary, since HG1's
  // "terminology" is mostly chrome — metric NAMES are separate below) / canonical
  // security identity (NEVER touched here — ticker/exchange/currency codes and security
  // names come from js/data.js's raw fields and are never passed through APP.i18n.t()).
  // =======================================================================
  var _lang = "en";

  // =======================================================================
  // The three PD-0012 human-approved additions, plus §14/§15's confirmed-missing
  // controls — all simulated session state (module-scoped vars, never persisted; no
  // write accessor exists in js/data.js and none is invented here, per this build's
  // own established "simulated staged/confirm" convention already used throughout
  // js/surfaces/portfolio.js and js/surfaces/ingest.js).
  // =======================================================================
  var _reportingCurrency = "USD";        // PD-0012 §1 — Reporting Currency (USD | CNY)
  var _benchmarkSelection = "MSCI ACWI (ACWI)"; // feedback log §14 — selection affordance
  var _colorConvention = "intl";         // PD-0012 §4 — "intl" (green-up) | "cn" (red-up)
  var _simulatedPolicy = { positionCap: null, sectorCap: null, saved: false };

  APP.ui.getColorConvention = function () { return _colorConvention; };
  APP.ui.getReportingCurrency = function () { return _reportingCurrency; };
  APP.ui.getSelectedBenchmark = function () { return _benchmarkSelection; };

  // =======================================================================
  // HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1 §1.1/§1.2, the audit's most
  // consequential finding). Explanation mode is now APPLICATION STATE, not
  // per-card state: one value, read by every surface's own render function and
  // by renderClaim's own ladder as its DEFAULT depth. Set from Settings AND
  // from a persistent header control (both call APP.state.setExplanationMode,
  // below) — never two independent pieces of state that could disagree.
  //
  // "Per-card ladders become local overrides" (PD-0016) is implemented
  // literally, not left as a sentence: renderClaim's own depth-pill control
  // (renderLadderControl, further down this file) still exists on every claim
  // card and still works exactly as before — clicking it changes THAT card's
  // own depth via its private rerender() closure, without touching this
  // shared value at all. Changing the value here (the global control, or
  // Settings) triggers a full route re-render (mirroring APP.i18n.setLang's
  // own pattern immediately above), so every claim card not carrying its own
  // local override picks up the new default the next time it is built.
  //
  // Simulated session state only, same as every other PD-0012/§14/§15 control
  // on this file — no write accessor exists in js/data.js and none is invented
  // here; resets on reload.
  // =======================================================================
  // Reuses DEPTH_LEVELS (defined once, further down this file, alongside
  // renderLadderControl) rather than a second, separately-typed literal array of
  // the same three strings — two arrays that happen to agree today is exactly the
  // "parallel truths" shape PD-0014 §2.5 warns against, even for a static list.
  // Safe to reference here despite the textual forward-reference: `var`
  // declarations in this IIFE all execute, top to bottom, during the script's own
  // initial synchronous run — long before any function below (including this one)
  // is ever CALLED (boot() waits for DOMContentLoaded; every click handler waits
  // for a click) — so DEPTH_LEVELS is always assigned by the time it is read here.
  var _explanationMode = "quick";
  APP.state = APP.state || {};
  APP.state.getExplanationMode = function () { return _explanationMode; };
  APP.state.setExplanationMode = function (mode) {
    if (DEPTH_LEVELS.indexOf(mode) < 0 || mode === _explanationMode) return;
    _explanationMode = mode;
    if (_booted) { renderGlobalHeader(); renderRoute(); }
  };
  APP.state.explanationModeRank = function (mode) { return DEPTH_LEVELS.indexOf(mode); };
  // "at least" — the comparison every minMode gate (APP.ui.renderModule, below) and
  // every module-visibility decision in js/surfaces/*.js is built on: is the CURRENT
  // global mode at or above the mode a given module declared as its own floor.
  APP.state.explanationModeAtLeast = function (mode) {
    return APP.state.explanationModeRank(_explanationMode) >= APP.state.explanationModeRank(mode);
  };
  // Quiet setter — the exact same reasoning as setLangQuiet (this file's own i18n
  // section, above): a read-only diagnostic (js/selfcheck.js's
  // explanationMode.claimFactsInvariant assertion, added this pass) needs to read
  // every accessor's output "as of" each of the three modes without forcing the whole
  // app to re-render three times just to run a comparison. NOT the primary API — a
  // real, user-facing mode change always goes through APP.state.setExplanationMode
  // above, which also re-renders; this exists only so a verification pass can restore
  // the mode it found exactly as it found it, silently.
  APP.state.setExplanationModeQuiet = function (mode) {
    if (DEPTH_LEVELS.indexOf(mode) >= 0) _explanationMode = mode;
  };
  // Convenience aliases on APP.ui (same reasoning as APP.ui.t/APP.ui.getLang, just
  // above) — CONTRACT.md's ctx shape exposes ctx.ui/ctx.data/ctx.charts only, never a
  // bare ctx.state, so every surface reaches this the same way it reaches language.
  APP.ui.getExplanationMode = APP.state.getExplanationMode;
  APP.ui.setExplanationMode = APP.state.setExplanationMode;
  APP.ui.explanationModeAtLeast = APP.state.explanationModeAtLeast;

  var I18N = {
    en: {
      "nav.overview": "Overview", "nav.portfolio": "Portfolio", "nav.analytics": "Analytics",
      "nav.scenario": "Scenario Lab",
      "subnav.portfolio": "Holdings & Activity", "subnav.ingest": "Import & Ingestion",
      "depth.quick": "Quick", "depth.simple": "Simple", "depth.professional": "Professional",
      "depth.controlLabel": "Explanation depth",
      "badge.actual": "ACTUAL", "badge.scenario": "SCENARIO — HYPOTHETICAL",
      "badge.staged": "STAGED — NOT YET IN YOUR PORTFOLIO", "badge.committed": "COMMITTED",
      "freshness.live": "Live", "freshness.delayed": "Delayed", "freshness.end_of_day": "EOD",
      "freshness.stale": "Stale", "freshness.leastFresh": "Least fresh: ",
      "freshness.leastFreshTied": "Least fresh (tied): ",
      "common.comparabilityFlag": "Limited comparability",
      "common.evidence": "Evidence", "common.evidenceMethodology": "Evidence & Methodology",
      // HG1 Round 5, Phase 2 correction pass (Blocker 3 — persistent overlay chrome
      // present on every route; PD-0012 §3 names Evidence & Methodology and Settings
      // explicitly, and this is the third such overlay). Used for the AI Analyst
      // overlay's title AND its aria-label (js/shell.js's localizeStaticChrome).
      "ai.analystTitle": "AI Analyst",
      // HG1 Round 5 SECOND micro-pass (Defect 3) — the lowercase footer sentence
      // (index.html's `#app-footer-synthetic-note`), present on all five routes.
      // Distinct from `brandAndBanner`'s ALL-CAPS compliance banner, which stays
      // canonical/untranslated by policy — this is ordinary UI prose.
      // Post-HG1 Checkpoint A — S1 (designer-33, 2026-09-15): "Not an
      // approval." removed — false since PD-0017 (HG1 = APPROVED). Durable
      // artifact-status language only; kept in sync with index.html's
      // pre-boot fallback span and the zh counterpart below.
      "common.syntheticFooterNote": "Synthetic data. HG1 design-review prototype. Not an implementation.",
      "common.askAboutThis": "Ask about this", "common.askFollowUp": "Ask a follow-up:",
      "common.askPortfolio": "Ask your portfolio", "common.close": "Close",
      "common.notAvailable": "not available", "common.insufficientData": "insufficient data",
      // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.1(b)) — the single
      // source for the lowercase sufficiency-state word used inside qualifierShort
      // strings, matching this app's own established plain-language register
      // ("insufficient data"/"not available" above, never an uppercase enum token). A
      // second, forked name for this state anywhere else would itself be PD-0014
      // §2.5's "parallel truths" — every qualifierShort reads this ONE key.
      "common.limited": "limited",
      // HG1 Round 5 micro-pass (Item 3) — the raw-English fallback reasonCodeText()
      // (below) reads, for a LIMITED/INSUFFICIENT_DATA claim that has a
      // reasonCode but no qualifierShort/caveat of its own. Register matches
      // common.limited/common.insufficientData above (lowercase, plain
      // language) — never the raw enum token itself, which stays untranslated
      // everywhere else in this app (see the canonicalEnumToken classifier rule).
      "reasonCode.UNSUPPORTED_ASSET": "unsupported asset type",
      "reasonCode.MISSING_BENCHMARK": "no benchmark on file",
      "reasonCode.MISSING_COST_BASIS": "cost basis missing",
      "reasonCode.MISSING_FX_HISTORY": "FX history missing for this date",
      "reasonCode.CALCULATION_ERROR": "calculation could not complete",
      "reasonCode.STALE_DATA": "inputs not current",
      "common.confirm": "Confirm", "common.cancel": "Cancel", "common.save": "Save",
      "common.edit": "Edit", "common.language": "Language",
      "common.seeAllInsights": "See all insights ({n})",
      // HG1 M3 fix — a shared, generic one-click affordance label for a
      // ctx.ui.renderModule gate whose block already carries a persistent
      // `.block-kicker` heading with the section's own name immediately above it
      // (Overview Blocks B/C/D/E). Using the block's own heading text again as the
      // gate's `label` produced an exact duplicate `<summary>`/heading pair; this key
      // exists so the collapsed affordance reads as an action ("show the detail"),
      // never a second copy of the section title it sits directly beneath.
      "common.showSectionDetail": "Show details",
      // HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1 §1.3, "Simple adds the reference
      // point beside each figure"). Fixes I7/I8 (shell.js:1549's hardcoded English
      // "Reference: ", visible on a Chinese screen because Professional was previously
      // the only depth that ever showed a reference point at all).
      "claim.referenceLabel": "Reference: ",
      "common.to": "to",
      "settings.title": "Portfolio Settings / Policy",
      "settings.reportingCurrency": "Reporting currency",
      "settings.reportingCurrencyNote": "Simulated for HG1 — recomputing every reporting-currency-dependent figure (historical series, FX attribution, Proof Packet values) against historical FX rates is Priority-D implementation work (PD-0012), not built in this prototype. Native security currency is never affected by this setting.",
      "settings.benchmark": "Benchmark",
      "settings.benchmarkNote": "Selecting a different benchmark here does not yet recompute this build's figures — excess return, beta, alpha, and the SML below are still computed against MSCI ACWI, the benchmark actually used for every number on this screen. A production benchmark switch would recompute every dependent statistic and update every label; this control demonstrates the selection affordance without mislabeling MSCI-ACWI-based figures as if they belonged to a different benchmark.",
      "settings.language": "Language",
      "settings.explanationMode": "Explanation mode",
      "settings.explanationModeNote": "Controls how much detail every claim shows at rest across Overview, Portfolio, Analytics, and Scenario Lab — Quick, Simple, or Professional. The same setting as the depth control in the header; changing it here changes that control too. Any individual card's own depth control still lets you go deeper on just that one figure.",
      "settings.colorConvention": "Gain / loss color convention",
      "settings.colorConventionIntl": "Green up / Red down (international convention)",
      "settings.colorConventionCn": "Red up / Green down (Mainland China convention)",
      "settings.colorConventionNote": "Color is never the only signal either way — the ▲ / ▼ glyph and the explicit +/- sign always carry direction too.",
      "settings.accounts": "Account containers",
      "settings.policy": "Portfolio Policy",
      "settings.positionCap": "Single-position weight cap (%)",
      "settings.sectorCap": "Sector concentration cap (%)",
      "settings.saveSimulated": "Save (simulated)",
      "settings.policySavedNote": "Simulated — not persisted; resets on reload. This prototype has no policy-write accessor; a production build would call one here.",

      // PD-0015 Part 1 — V1 has two valuation-time modes over one architecture, not two
      // analytics systems. HG1 scope is the interaction/product contract represented
      // honestly, not full Current-mode computation (CP1, blocked pending Priority A).
      "valuationMode.title": "Valuation Time Mode",
      "valuationMode.current": "Current / Latest",
      "valuationMode.historical": "Historical as-of",
      "valuationMode.badge": "Historical as-of · {date}",
      "valuationMode.intro": "V1 supports two valuation-time modes over one deterministic architecture — not two separate analytics systems.",
      "valuationMode.currentDesc": "Evaluates the portfolio against the latest permissible market/reference data. Live, delayed, and end-of-day freshness states may all be meaningful, depending on market and provider state.",
      "valuationMode.historicalDesc": "Evaluates the portfolio at a specific historical cutoff. No input may post-date the cutoff; a Live state is never used just to make the freshness badge reachable.",
      // Post-HG1 Checkpoint A — S1 (designer-33, 2026-09-15): surgical removal
      // of "which is blocked until HG1 is approved" — false since PD-0017
      // (HG1 = APPROVED). Everything else preserved: Current mode is still
      // not computed in this prototype, still requires the real market-data
      // spine (Priority A), and this build still does not simulate a live
      // feed.
      "valuationMode.currentNotComputed": "Not computed in this prototype. Full Current-mode computation requires the real market-data spine (Priority A) — this build does not simulate a live feed to make this mode appear active.",
      "valuationMode.historicalActive": "This is the mode this prototype represents. Every figure on this build is evaluated as of the snapshot date below; no live or post-cutoff input is used.",
      "settings.noPositionCap": "No single-position weight cap is set. Insights that reference concentration will use comparative/educational language, not a personal threshold, until you set one below.",
      "settings.noSectorCap": "No sector concentration cap is set.",
      "settings.positionCapSet": "Single-position weight cap: ",
      "settings.sectorCapSet": "Sector concentration cap: ",
      "table.security": "Security", "table.qty": "Qty", "table.avgCost": "Avg Cost",
      "table.price": "Price", "table.marketValueUsd": "Market Value (USD)",
      "table.pctPortfolio": "% of Portfolio", "table.unrealizedGl": "Unrealized G/L",
      "table.freshness": "Freshness", "table.actions": "",
      "table.position": "Position", "table.weight": "Weight", "table.marketValue": "Market Value",
      "table.riskMetrics": "Risk Metrics",
      "table.account": "Account", "table.type": "Type", "table.market": "Market",
      "table.currency": "Currency", "table.cashBalances": "Cash Balance(s)",
      "table.date": "Date", "table.txType": "Type", "table.instrument": "Instrument",
      "table.quantity": "Quantity", "table.priceAmount": "Price / Amount",
      "table.reportingConversion": "Reporting-Currency Conversion", "table.note": "Note",
      // HG1 Round 5, Phase 2 (S7) — Portfolio surface block headers. I7/I8 named
      // "Accounts & Cash" specifically (portfolio.js:606) as a hardcoded literal.
      "pf.portfolioKicker": "Portfolio", "pf.accountsAndCash": "Accounts & Cash",
      "pf.holdings": "Holdings", "pf.holdingsHint": "Every position, grouped by account. Click a row to inspect; use Edit to reconcile.",
      "pf.transactionsActivity": "Transactions & Activity",
      "pf.searchHoldingsPlaceholder": "Search holdings by name or ticker…",
      "pf.noHoldingsMatch": "No holdings match “{query}”.",
      "evidence.breadcrumb": "Visual conclusion → key number → explanation → evidence → methodology",
      "evidence.keyNumber": "Key number", "evidence.explanation": "Explanation",
      "evidence.proofPacket": "Evidence (Proof Packet)", "evidence.methodology": "Methodology",
      "evidence.notPublished": "Not yet published.",
      "ai.disclaimer": "Every figure below is read directly from your portfolio's computed metrics; the AI never types a number itself. Click any highlighted figure for its source and method.",
      "ai.suggestFollowUp": "Ask a follow-up:",
      "scenario.title": "Scenario Lab — hypothetical analysis",
      "scenario.actualLegend": "Your real, recorded portfolio.",
      "scenario.scenarioLegend": "A hypothetical modeled outcome — never a holding.",
      "scenario.notForecast": "Every figure in this comparison is a deterministic recalculation under a hypothetical allocation, applied to the SAME historical return series your actual portfolio uses (P6) — a historical replay, not a forecast of future risk or return.",
      "scenario.allocationHeader": "Allocation — current vs. scenario",
      "scenario.allocationLegendHeader": "Segments (current → scenario)",
      "scenario.deltaHeader": "Change by segment",
      "scenario.riskHeader": "Risk — current vs. scenario",
      "scenario.concentrationHeader": "Concentration — current vs. scenario",
      "scenario.metricHeader": "Portfolio metric — Sharpe ratio, current vs. scenario",
      "scenario.whatThisMeans": "What exactly does this model?",
      "scenario.introText": "Model a hypothetical change to your portfolio and compare it against your actual, current holdings. Nothing below changes your real portfolio unless you separately edit it.",
      "scenario.noneDefined": "No scenarios are defined.",
      "scenario.hypotheticalInputsLabel": "Hypothetical inputs modeled:",
      // HG1 Round 5 micro-pass (Item 3) — field-key labels for the raw
      // modifications[] readout (js/surfaces/scenario.js). SUPERSEDED IN PART
      // (Post-HG1 Checkpoint A — D3, 2026-09-15): the `action` field's VALUE
      // no longer stays untranslated canonical syntax on screen — see
      // scenario.action.* immediately below and js/surfaces/scenario.js's
      // presentModificationLine. These five remain the field-key LABELS only.
      "scenario.modField.action": "action", "scenario.modField.target": "target",
      "scenario.modField.amount": "amount", "scenario.modField.from": "from", "scenario.modField.to": "to",
      // Post-HG1 Checkpoint A — D3 (designer-33). Human-readable labels for
      // this app's three scenario-construction action CODES (js/data.js's
      // SCENARIOS[].modifications[].action) — wording follows source PRD
      // §24.2's own vocabulary ("reduce weight," "add hypothetical
      // instrument," "shift exposure"; see designs/FEATURE_DESIGN.md §7),
      // capitalized here as a field-value label. The raw codes are UNCHANGED
      // in js/data.js; only what reaches the screen changes (see
      // js/surfaces/scenario.js's presentActionValue).
      "scenario.action.REDUCE_WEIGHT": "Reduce weight",
      "scenario.action.ADD_HYPOTHETICAL_INSTRUMENT": "Add hypothetical instrument",
      "scenario.action.SHIFT_EXPOSURE": "Shift exposure",
      "scenario.colSegment": "Segment", "scenario.colCurrent": "Current",
      "scenario.colScenario": "Scenario", "scenario.colChange": "Change",
      "scenario.centerActual": "Actual", "scenario.centerScenario": "Scenario",
      "scenario.exploreFullDetailBtn": "Explore full detail (actual Sharpe ratio)",
      "scenario.askAboutScenario": "Ask about this scenario",
      "ingest.title": "Import & Ingestion",
      "ingest.workflow": "Workflow",
      "ingest.csvImport": "CSV Import", "ingest.ocrImport": "OCR-Assisted Ingestion",
      // HG1 Round 5, Phase 2 (S7). Structural/step headers and the CSV preview table's
      // own column headers — the highest-visibility gaps on this surface; this pass
      // does not claim full coverage of every OCR field label/hint on this surface
      // (a real, disclosed remaining gap — see this designer's report).
      "ingest.step12": "1–2. Upload & Column Mapping", "ingest.step3": "3. Preview & Correction",
      "ingest.step4": "4. Import Report & Confirmation",
      "ingest.sourceColumn": "Source Column", "ingest.mapsTo": "Maps To",
      "ingest.rawRow": "Raw Row", "ingest.mapped": "Mapped",
      "ingest.statusCol": "Status", "ingest.issuesResolution": "Issues / Resolution",
      "ingest.confirmImportSimulated": "Confirm Import (simulated)",
      "ingest.confirmCommitSimulated": "Confirm & Commit to Portfolio (simulated)",
      "ingest.importAnyway": "Import anyway", "ingest.skip": "Skip",

      // HG1 round-4, second bilingual pass — Overview and Analytics chrome (coordinator
      // review: "the screens are still mixed-language, and the remaining English is in
      // your files"). §12.2 requires representative FULL screens, not chrome-only
      // coverage — Portfolio/Ingest/Scenario stay English on purpose (their claim layer
      // is also untranslated; see this designer's handoff), but Overview and Analytics
      // must be complete. Canonical identifiers (MSCI ACWI, tickers, currency codes)
      // are never placed in this dictionary — they are concatenated around translated
      // text at the call site, unchanged in either language.
      "riskGroup.overallRisk": "Overall risk", "riskGroup.marketSensitivity": "Market sensitivity",
      "riskGroup.downside": "Downside", "riskGroup.riskAdjusted": "Risk-adjusted performance",
      "riskGroup.riskDrivers": "Risk drivers",

      "ov.blockA": "Overview · How am I doing?", "ov.blockB": "Overview · What is driving the portfolio?",
      "ov.blockC": "Overview · What are the main risks?", "ov.blockD": "Overview · What deserves my attention?",
      "ov.blockE": "Overview · Portfolio Brief",
      "ov.totalPortfolioValue": "Total Portfolio Value", "ov.gainLoss1y": "Gain / Loss (1Y)",
      "ov.gainLossPct": "Gain / Loss %",
      "ov.yourPortfolio": "Your Portfolio", "ov.benchmarkAcwiSeries": "Benchmark (MSCI ACWI)",
      "ov.askAboutThisChart": "Ask about this chart",
      "ov.majorHoldings": "Major Holdings",
      "ov.holdingsDetailTop5": "Holdings detail (top 5 of {n} positions)",
      "ov.showEntirePortfolio": "Show entire portfolio ({n} positions)",
      "ov.viewFullHoldings": "View full Holdings & Transactions →",
      "ov.summarizeExposures": "Summarize my largest exposures",
      "ov.assetMix": "Asset Mix",
      "ov.largestAssetClassAllocation": "{label} is the largest asset-class allocation, at {pct}.",
      "ov.seeBreakdown": "See sector, listing-market/economic-geography, and currency breakdown",
      "ov.sectorExposureDirect": "Sector Exposure — direct equity holdings only",
      "ov.noDirectEquitySector": "No direct-equity sector exposure is classified in this portfolio.",
      "ov.notSectorsCaveat": "The categories below are not sectors — they are pooled funds, fixed-income/other non-equity instruments, and structured/unsupported holdings, shown separately so a fund is never presented as if it were a sector. ETF look-through (naming a fund's own underlying sector exposure) is out of scope for V1.",
      "ov.byListingMarket": "By Listing Market", "ov.byEconomicGeography": "By Economic Geography",
      "ov.currencyExposure": "Currency Exposure",
      "ov.rolling90dVolatility": "Rolling 90-Day Volatility", "ov.top5Concentration": "Top-5 Concentration",
      "ov.explainThisRisk": "Explain this risk",
      "ov.explainRiskStatsFull": "Explain these risk statistics in full (Beta, Sortino, Concentration)",
      "ov.noInsightsFlagged": "No insights are currently flagged.",
      "ov.acrossPortfolio": "across your portfolio.",
      "ov.warningCount": "warning", "ov.attentionItemCount": "attention item",
      "ov.askFollowUpBtn": "Ask a follow-up",
      "ov.outperformed": "outperformed", "ov.underperformed": "underperformed",
      "ov.returnedSentence": "Your portfolio returned {chip} over the trailing year, which {direction} its benchmark by {chip2}.",
      "ov.fxReduced": "reduced", "ov.fxAddedTo": "added to",
      "ov.fxSentence": "Currency movement {direction} that reporting-currency return by roughly {chip}.",
      "ov.volatilitySentence": "Annualized volatility ran {chip} for the period, historically.",
      "ov.concentrationSentence": "Your top five holdings make up {chip} of invested value, the largest single driver of concentration risk right now.",
      "ov.snapshotAsOf": "Snapshot as of {date}, reporting currency {ccy}.",

      "an.performance": "Performance", "an.riskReturnProfile": "Risk & Return Profile",
      "an.rollingAnalyticsDrawdown": "Rolling Analytics & Drawdown", "an.exposure": "Exposure",
      "an.correlationClustering": "Correlation & Clustering",
      "an.contributionToRisk": "Contribution to Portfolio Risk",
      "an.analyticsKicker": "Analytics",
      "an.analyticsLead": "Performance, risk, and exposure analytics for your cross-border portfolio — the same underlying facts as Overview and Portfolio, at full analytical depth.",
      "an.benchmarkNoteAcwi": "Benchmark: MSCI ACWI, the benchmark actually used for every figure below.",
      "an.benchmarkNoteOtherPrefix": "Settings shows “",
      "an.benchmarkNoteOtherSuffix": "” selected, but every figure below is still computed against MSCI ACWI — this prototype does not yet recompute benchmark-relative statistics for a different benchmark selection (see Settings' own note).",
      "an.localVsCurrencyContribution": "Local-market vs. currency contribution (trailing 1Y)",
      "an.localMarketReturn": "Local-market return", "an.fxEffect": "FX effect",
      "an.trailing1yReturnCategory": "Trailing 1Y return",
      "an.explainThisSplit": "Explain this split",
      "an.csopRiskMetricsSuffix": " — risk metrics",
      "an.rollingVol90dAnnualized": "90-day rolling volatility (annualized)",
      "an.portfolioDrawdown": "Portfolio drawdown",
      "an.realizedReturnVsBeta": "Realized return vs. beta — ex-post market line (trailing 1Y)",
      "an.betaVsAcwiAxis": "Beta vs. MSCI ACWI — trailing 1Y, daily returns",
      "an.realizedTotalReturnAxis": "Realized total return, trailing 1Y, USD, compounded",
      "an.observationsSuffix": " observations",
      "an.windowTrailingDaily": "Trailing 1Y · Daily returns",
      "chart.rollingWindow90d": "Trailing 1Y · Daily returns · 90-day rolling window",
      "an.benchmarkBetaDefinition": "Benchmark beta is 1 by definition.",
      "an.pointDetailTemplate": "{label} — beta {beta}, trailing return {ret}.",
      // HG1 ux_planning revision (review-06, secondary — duplicated disclosure
      // headings) — these four renamed from their prior bare form ("By listing
      // market"/"Asset class"/"Concentration") to match the exact wording their own
      // adjacent claim card already carries (js/data.js's exposure.listingMarket/
      // exposure.assetClass/metric.concentration `label` fields). This section
      // heading and its claim card's own label (js/surfaces/analytics.js's
      // focusableMetricCell) are now the SAME text for these four dimensions instead
      // of two similar-but-different phrasings sitting immediately adjacent to each
      // other — analytics.js now renders that shared text once (`showLabel: false` on
      // the claim card), not twice.
      "an.byListingMarket": "Listing-Market Exposure", "an.byEconomicGeographyCountry": "By economic geography (country)",
      "an.assetClass": "Asset Class Exposure", "an.sectorDirectEquityOnly": "Sector (direct equity holdings only)",
      "an.currencyExposureHeading": "Currency Exposure", "an.concentrationHeading": "Concentration (Top 5)",
      "an.viewFullCorrelationMatrix": "View full correlation matrix (Professional depth)",
      "an.sleeveCorrelationMatrixTitle": "Sleeve Correlation Matrix",
      "an.trailing1yDaily5series": "Trailing 1Y daily returns, 5 series. Full pairwise matrix.",
      "an.strongestRelationshipTemplate": "{a} and {b} show the strongest historical relationship in this sample, at a correlation of {chip}.",
      "an.weakestRelationshipTemplate": " {a} and {b} show the weakest (most diversifying) relationship, at {chip}.",
      "an.capitalWeightVsRiskContribution": "Capital weight vs. risk contribution",
      "an.capitalWeight": "Capital weight", "an.riskContribution": "Risk contribution",
      "an.sleeveDivergenceCaveat": "A sleeve can carry more (or less) risk than its capital weight alone would suggest — this is what that divergence looks like directly, rather than as two isolated figures.",
      "an.askAboutAnalyticsView": "Ask about this Analytics view",
      "an.noBreakdownAvailable": "No breakdown available.",
      // HG1 Round 5, Phase 2 correction pass (Blocker 1 — js/surfaces/analytics.js's
      // appendProfessionalDepthModule). Summary text for the Professional-only
      // module surfacing a claim's own investorDetail/professionalDetail/caveat at
      // rest — content already authored in js/data.js, previously reachable only
      // inside the click-required inspector.
      "an.professionalDepthHeading": "Methodology & assumptions (Professional depth)",

      // HG1 round-4, second bilingual pass — chart-INTERNAL strings (js/charts.js),
      // as distinct from strings a surface file passes into a chart call. These are
      // constants baked into charts.js itself (legend items, the relative-performance
      // callout, the drawdown trough label) that no caller could previously override at
      // all — the coordinator's own hint that chart-embedded strings are "the ones most
      // likely to be missed, because they are not in the surface's own prose." Read
      // defensively by charts.js via a fallback-safe helper (see that file's own
      // comment) so charts.js's stated design constraint — usable with only its own
      // module loaded — still holds when APP.i18n is absent.
      "chart.portfolio": "Portfolio", "chart.yourPortfolio": "Your portfolio",
      "chart.benchmark": "Benchmark", "chart.sleeve": "Sleeve",
      "chart.securityMarketLineExPost": "Security Market Line (ex-post)",
      "chart.thisPeriodPrefix": "This period: ", "chart.vsBenchmarkSuffix": " vs. benchmark",
      "chart.maxDrawdownPrefix": "Max drawdown ",
      "chart.capitalWeight": "Capital weight", "chart.riskContribution": "Risk contribution",
      "chart.insufficientData": "insufficient data",
      "chart.drawdownLabel": "Drawdown", "chart.differencePrefix": "Difference: ",
      "chart.notAvailable": "n/a",
      "chart.lineDistancePrefix": "Line distance ", "chart.historicalSuffix": " (historical)",

      "sector.pooledFund": "Pooled / fund exposure (no look-through)",
      "sector.fixedIncome": "Fixed income / non-equity",
      "sector.structuredUnsupported": "Structured / unsupported",

      // judgmentClass is a small, CLOSED taxonomy js/data.js's INSIGHTS array assigns
      // (three values total, checked directly against that file) — a UI category label
      // this product defines, not open-ended prose, so translating it via a fixed
      // lookup carries none of the "inventing a term" risk sector/asset-class names do.
      "judgmentClass.Fact": "Fact", "judgmentClass.Interpretation": "Interpretation",
      "judgmentClass.Preference-dependent judgment": "Preference-dependent judgment",

      // HG1 Round 5 correction pass (Objective 2 — finish localization). Keys below
      // close the measured Portfolio/Ingest/Scenario/AI/Evidence gaps
      // (reviews/gates/HG1_ROUND5_UX_AUDIT.md §8.6). Canonical identity (tickers, MIC
      // codes, ISO currency codes, security names, raw account/listing-market/type
      // enum values) is never placed in this dictionary — it is concatenated at the
      // call site unchanged in either language, per PD-0015 §2.3.
      "common.search": "Search", "common.na": "N/A",
      "common.reviewAndStage": "Review & Stage",
      "common.confirmAndAdd": "Confirm & Add (simulated)",
      "common.backToEdit": "Back to edit",
      "common.simulatedEntryNote": "Simulated entry. Nothing here is persisted.",

      "pf.accountsStat": "Accounts",
      "pf.addPositionBtn": "+ Add Position", "pf.addTransactionBtn": "+ Add Transaction",
      "pf.addAccountBtn": "+ Add Account", "pf.importStatementBtn": "Import a Statement (CSV / OCR)",
      "pf.noneOnFile": "None on file",
      "pf.cashNativeCurrencyNote": "Cash balances shown in native currency. No accessor exposes an FX rate to convert cash into reporting currency here.",
      "pf.addCashBalanceBtn": "+ Add Cash Balance",
      "pf.listingSuffix": "{market} listing",
      "pf.riskAnalyticsUnsupported": "Risk analytics unsupported for this instrument",
      "pf.notProvided": "Not provided",
      "pf.inKindTransferTitle": "In-kind transfer — original cost basis was not provided by the sending broker.",
      "pf.cashLabel": "Cash: ",
      "pf.allAccounts": "All accounts", "pf.allTypes": "All types",
      "pf.noConversionClaimNote": "No conversion claim recorded for this transaction",
      "pf.holdingInspectorDetail": "Account: {account} · Listing: {listing} · Economic geography: {geo}",
      "pf.securitySearchLabel": "Security search / identifier",
      "pf.securitySearchPlaceholder": "Ticker, name, or identifier (e.g. AAPL, 0700.HK, TSMC)",
      "pf.ambiguousMatchNote": "Multiple possible matches were found. Select the correct security below — an ambiguous identity is never resolved silently.",
      "pf.matchedTemplate": "Matched: {id} — {name} ({market} listing)",
      "pf.noMatchNote": "No match among this demo portfolio's known securities. You may still record this identifier; it is kept as entered, marked unverified, not guessed.",
      "pf.unverifiedIdentifierLabel": "{query} (unverified identifier)",
      "pf.newPositionTitle": "New manual position",
      "pf.simulatedPositionNote": "Simulated entry, demonstrating the intended workflow (PRD §27.1). Nothing here is persisted to the ledger shown elsewhere in this prototype.",
      "pf.qtyPlaceholderExample": "e.g. 100",
      "pf.averageCost": "Average cost",
      "pf.avgCostHint": "Leave blank if unknown — a missing cost basis renders as insufficient data, never a fabricated figure.",
      "pf.avgCostPlaceholder": "Per-share/unit, native currency",
      "pf.acquisitionDate": "Acquisition date",
      "pf.ccyOverrideSecurityLabel": "This security trades in a different currency than the account",
      "pf.currencyOverride": "Currency override",
      "pf.qtyRequired": "Quantity is required.",
      "pf.resolveSecurityFirstLong": "Search for and resolve a security identity first (or accept the unverified identifier) before staging.",
      "pf.newTransactionTitle": "New manual transaction",
      "pf.simulatedTransactionNote": "Simulated entry, demonstrating the intended workflow (PRD §27.2). Nothing here is persisted to the ledger shown elsewhere in this prototype.",
      "pf.qtyTxHint": "Required for BUY/SELL/TRANSFER; leave blank for cash-only entries (deposit, withdrawal, FX).",
      "pf.ccyOverrideTxLabel": "This transaction is in a different currency than the account",
      "pf.newAccountTitle": "New account",
      "pf.accountName": "Account name",
      "pf.accountNamePlaceholder": "e.g. Interactive Brokers (US)",
      "pf.marketGlobalMulti": "Global / multi-currency",
      "pf.accountNameRequired": "Account name is required.",
      "pf.confirmAndCreate": "Confirm & Create (simulated)",
      "pf.addCashTitle": "Add cash balance",
      "pf.amount": "Amount",
      "pf.amountRequired": "Amount is required.",
      "pf.confirmSimulated": "Confirm (simulated)",
      "pf.editRowNoteTemplate": "Editing {id} — reconciliation demo. Simulated: changes are not persisted.",
      // HG1 Round 5 micro-pass (Item 3) — the four staged-entry forms' own
      // preview/description/confirmation text (buildPositionForm/
      // buildTransactionForm/buildAccountForm/buildCashForm/buildEditRow), found
      // hardcoded English with no `ctx.ui.t()` call at all — genuine UI-chrome
      // gaps, not canonical or source content.
      "pf.unitsAccountTemplate": "{qty} units, {account}",
      "pf.avgCostSuffixTemplate": ", avg cost {amount} {ccy}",
      "pf.avgCostNotProvidedSuffix": ", average cost not provided",
      "pf.acquiredSuffixTemplate": ", acquired {date}",
      "pf.previewOnlyPositionNote": "Preview only. Confirming below simulates adding this position — it does not change the Holdings table above.",
      "pf.simulatedPositionWrittenNote": "Simulated: this would now be written to your ledger. This prototype does not persist it — the Holdings table above is unchanged.",
      "pf.noDateEntered": "no date entered",
      "pf.qtyInlineLabel": "qty",
      "pf.previewOnlyTransactionNote": "Preview only. Confirming simulates adding this transaction — it does not change the Transactions table above.",
      "pf.simulatedTransactionWrittenNote": "Simulated: this would now be written to your ledger. This prototype does not persist it — the Transactions table above is unchanged.",
      "pf.previewOnlyAccountNote": "Preview only. Confirming simulates creating this account — it will not appear in Accounts & Cash above.",
      "pf.simulatedAccountCreatedNote": "Simulated: this account would now exist. This prototype does not persist it.",
      "pf.previewOnlyCashNote": "Preview only. Confirming simulates recording this balance — it does not change Accounts & Cash above.",
      "pf.simulatedCashRecordedNote": "Simulated: this cash balance would now be recorded. This prototype does not persist it.",
      "pf.reconciliationStagedTemplate": "Reconciliation staged (simulated) — quantity {qty}, avg cost {avgCost}, account {account}. Not persisted; the table above is unchanged.",
      "pf.avgCostNotProvidedShort": "not provided",

      "ingest.introNote": "Two ingestion routes are demonstrated here: CSV import (PRD §27.3, Core V1) and OCR-assisted ingestion (added to V1 scope by explicit human decision — see specs/OCR_INGESTION_ADDENDUM.md). Both share one invariant: nothing here silently mutates your portfolio. Every staged row or field carries a STAGED badge and reaches your ledger only after an explicit confirmation you take yourself.",
      "ingest.csvFileNoteTemplate": "File: {filename} — simulated upload; no file is actually read. Demonstrates PRD §27.3's CSV import discipline against a fixed sample export.",
      "ingest.colMeaning.date": "date", "ingest.colMeaning.ticker": "ticker / security identifier",
      "ingest.colMeaning.txType": "transaction type", "ingest.colMeaning.quantity": "quantity",
      "ingest.colMeaning.price": "price", "ingest.colMeaning.account": "account",
      "ingest.unmapped": "(unmapped)", "ingest.missingValue": "missing",
      "ingest.reportSummaryTemplate": "Staged: {staged} · Confirmed: {confirmed} · Quarantined: {quarantined}",
      "ingest.importConfirmedNote": "Import confirmed (simulated). This would now be written to your ledger — this prototype does not persist it; the Transactions table in Holdings & Activity is unchanged.",
      "ingest.resolveBeforeConfirm": "Resolve every ambiguous, missing, or possible-duplicate row above (or explicitly skip it) before confirming import.",
      "ingest.willImportAnyway": "Will import anyway", "ingest.willSkipDuplicate": "Will skip as duplicate",
      "ingest.supplyMissingTemplate": "Supply the missing {field}",
      "ingest.ocrSimNote": "This prototype simulates OCR extraction with fixed sample documents, per the owner's explicit instruction — no production OCR pipeline exists or is built here.",
      "ingest.ocrVocabNote": "OCR confidence (High / Low / Ambiguous match / Missing / Possible duplicate / Corrected / Confirmed) is a different vocabulary from a metric's data-sufficiency state (Available / Limited / Insufficient data). The pills below use only the OCR vocabulary — no metric value on this page is ever rendered with an OCR confidence pill, and no OCR field is ever rendered through the metric-state renderer.",
      // HG1 Round 5 micro-pass (Item 3) — the actual pill labels CONFIDENCE_STATUS_MAP
      // (below) renders, previously hardcoded English with no i18n step at all. Same
      // seven-word vocabulary the note immediately above already names in prose; two
      // extras (highConfidence/ok) cover renderConfidencePill's own fallback branches.
      "ingest.confidence.staged": "Staged for review",
      "ingest.confidence.lowConfidence": "Low confidence",
      "ingest.confidence.ambiguousMatch": "Ambiguous match",
      "ingest.confidence.missing": "Missing",
      "ingest.confidence.possibleDuplicate": "Possible duplicate",
      "ingest.confidence.corrected": "Corrected",
      "ingest.confidence.confirmed": "Confirmed",
      "ingest.confidence.highConfidence": "High confidence",
      "ingest.confidence.ok": "OK",
      "ingest.step.upload": "Upload", "ingest.step.extract": "Extract", "ingest.step.resolve": "Resolve",
      "ingest.step.stage": "Stage", "ingest.step.review": "Review", "ingest.step.confirm": "Confirm",
      "ingest.step.commit": "Commit",
      "ingest.sourceLineTemplate": "Source: {sourceType} · Uploaded {uploadedAt} · Document ID {id}",
      "ingest.extractedTemplate": "Extracted: {value}",
      "ingest.extractedNothing": "Extracted: nothing readable — left empty, not inferred (OCR-6 / OCR-7).",
      "ingest.correctedToTemplate": "Corrected to: {value} (by {who}, {when})",
      "ingest.confirmedByTemplate": "Confirmed by {who} on {when}",
      "ingest.sourceEvidencePointerSuffix": " — source evidence pointer (OCR-2).",
      "ingest.ambiguousSelectNote": "Ambiguous identity — select the correct security. Never guessed automatically (OCR-5).",
      "ingest.correctionOptionalLabel": "Correction — a blank field is never auto-filled",
      "ingest.enterCorrectValuePlaceholder": "Enter the correct value (optional)",
      "ingest.quarantineFieldLabel": "Quarantine this field — commit the rest of the document without it",
      "ingest.possibleDuplicateNote": "Possible duplicate of an existing transaction. Choose how to proceed.",
      "ingest.committedSimulatedNote": "Committed (simulated). This would now appear in Holdings/Transactions — this prototype does not persist it.",
      "ingest.viewInHoldingsBtn": "View in Holdings",
      "ingest.resolveBeforeCommit": "Resolve every ambiguous, missing, or possible-duplicate field above (or explicitly quarantine it) before committing. Nothing reaches the ledger while a field is unresolved (OCR-11).",

      "ai.contextualQuestionTemplate": "Contextual question: {label}",
      "ai.template.positions": "How many positions do I hold, and across which markets?",
      "ai.template.underperform": "Why did my portfolio perform this way?",
      "ai.template.changed": "What changed recently?",
      "ai.template.exposures": "Summarize my largest exposures",
      "ai.template.risk": "Explain my portfolio risk",
      "ai.evidenceButtonTemplate": "Evidence: {label}",
      "ai.noScenarioSelected": "No scenario is currently selected in Scenario Lab.",
      "ai.performanceNotAvailable": "Performance data is not available.",
      "ai.riskNotAvailable": "Risk data is not available.",
      "ai.positionCountLabel": "Position Count", "ai.distinctMarketsLabel": "Distinct Listing Markets",
      "ai.theCurrentFigureIsPrefix": "The current figure is ",
      "ai.alsoRelevantPrefix": "Also relevant: ",
      "ai.scenarioLeadTemplate": "This is a hypothetical comparison for “{name}”. It does not describe your actual, current portfolio (P8) — nothing changes your real holdings unless you separately edit them.",
      "ai.scenarioMetricPrefixTemplate": "{label} under this scenario would be ",
      "ai.briefIntroPrefix": "Here is a brief read on your portfolio. Your total portfolio value is ",
      "ai.overTrailingYearPrefix": "Over the trailing year it returned ",
      "ai.whichIsRelativeMid": ", which is ",
      "ai.relativeToItsBenchmarkSuffix": " relative to its benchmark.",
      "ai.largestHoldingsPrefix": "Your largest holdings represent ",
      "ai.youHoldPrefix": "You hold ", "ai.acrossListingMarketsMid": " positions across ",
      "ai.listingMarketsSuffix": " listing markets. ",
      "ai.largestHoldingsShownNote": "Your largest holdings, by market value, are shown on the Portfolio surface.",
      "ai.currencyMovementLead": "Currency movement accounted for ",
      "ai.ofThatFigureSuffix": " of that figure",
      "ai.decomposingIntoLead": ", decomposing into ",
      "ai.changedIntro": "Here is what is currently drawing attention on your portfolio, ranked by severity. Each item traces back to its own evidence and, where applicable, methodology.",
      "ai.topHoldingsPrefix": "Your top ", "ai.topHoldingsSuffix": " holdings represent ",
      "ai.ofInvestedValueSuffix": " of invested value.",
      "ai.currentAnnualizedVolTemplate": " Current annualized volatility is ",

      "evidence.comparedAgainstLabel": "Compared against: ",
      "evidence.whatThisIs": "What this is", "evidence.scope": "Scope",
      "evidence.dataQualityLimitations": "Data quality & limitations", "evidence.whereToGoNext": "Where to go next",
      "evidence.none": "None", "evidence.notApplicable": "Not applicable",
      "evidence.sourceDataTimestamps": "Source data timestamps",
      "evidence.methodologyEngineVersion": "Methodology / engine version",
      "evidence.dataFreshnessD5": "Data freshness (D5)",
      "evidence.notYetPublishedFull": "Not yet published. This metric's registry entry has not been authored yet — the registry ships with a validated schema and, for most metrics, zero populated entries in this increment (AC-17). This is the honest empty state, not a placeholder standing in for missing content.",
      "evidence.noMethodologyPointer": "No methodology pointer is recorded for this claim.",
      "evidence.portfolioFactHeader": "Portfolio fact — not a computed metric",
      "evidence.scenarioHypotheticalHeader": "Scenario Lab — hypothetical claim",
      "evidence.scenarioFallbackTemplate": "This figure comes from the hypothetical scenario “{name}” ({description}). A dedicated Proof Packet entry for this specific scenario-comparison value does not exist in this prototype — data.js's evidence registry covers metric, holding, instrument, transaction, and insight claims, not the per-scenario comparison figures scenario.js and ai.js construct on the fly. Flagged as a genuine gap, not papered over with invented content.",
      "evidence.notFoundHeader": "Evidence",
      "evidence.notFoundTemplate": "No evidence record exists for claim “{id}”. This may indicate a broken reference from the surface that cited it.",
      "evidence.registryTitle": "Methodology & Evidence Registry",
      "evidence.registryIntro": "Every metric this product computes has, or will have, a methodology entry here: definition, formula, data inputs, minimum observations, FX/corporate-action treatment, known limitations, and version. Some entries below are fully populated for this prototype; most deliberately show “not yet published” — that is the honest state of a schema-validated but not-yet-authored registry, not a bug.",
      "evidence.noExplanationRecorded": "No explanatory text is recorded for this claim.",
      "evidence.fact.holdingsCount": "This is a direct count of records in your holdings ledger (a read of APP.data.getHoldings().length), not a computed analytical metric. It has no formula, benchmark, or annualization convention, so no methodology registry entry applies to it — but the value itself is real, read from your actual data, never estimated by the AI (PD-0008's rule on portfolio-fact counts).",
      "evidence.fact.marketsCount": "This is a direct count of the distinct listing markets present in your holdings ledger. The same reasoning as the position count above applies: a real ledger fact, not a modeled statistic, and not the AI's own estimate.",
      "evidence.fact.totalPortfolioValue": "This is the sum of your holdings' market value and cash balances (APP.data.getTotalPortfolioValue()) — a ledger aggregation, not a modeled statistic. It carries no separate methodology entry for the same reason the counts above do not."
    },
    zh: {
      "nav.overview": "总览", "nav.portfolio": "投资组合", "nav.analytics": "分析",
      "nav.scenario": "情景实验室",
      "subnav.portfolio": "持仓与活动", "subnav.ingest": "导入与录入",
      "depth.quick": "简要", "depth.simple": "简明", "depth.professional": "专业",
      "depth.controlLabel": "解释深度",
      "badge.actual": "实际", "badge.scenario": "情景 — 假设",
      "badge.staged": "暂存 — 尚未计入您的投资组合", "badge.committed": "已提交",
      "freshness.live": "实时", "freshness.delayed": "延迟", "freshness.end_of_day": "收盘价",
      "freshness.stale": "过期", "freshness.leastFresh": "时效最差：",
      "freshness.leastFreshTied": "时效并列最差：",
      "common.comparabilityFlag": "可比性受限",
      "common.evidence": "证据", "common.evidenceMethodology": "证据与方法论",
      "ai.analystTitle": "AI 分析师",
      // Post-HG1 Checkpoint A — S1 (designer-33, 2026-09-15): "非批准文件。"
      // removed — false since PD-0017 (HG1 = APPROVED).
      "common.syntheticFooterNote": "合成数据。HG1 设计评审原型。非实施版本。",
      "common.askAboutThis": "就此提问", "common.askFollowUp": "追问：",
      "common.askPortfolio": "询问您的投资组合", "common.close": "关闭",
      "common.notAvailable": "不可用", "common.insufficientData": "数据不足",
      "common.limited": "有限",
      "reasonCode.UNSUPPORTED_ASSET": "不支持的资产类型",
      "reasonCode.MISSING_BENCHMARK": "没有可用的基准",
      "reasonCode.MISSING_COST_BASIS": "缺少成本基础",
      "reasonCode.MISSING_FX_HISTORY": "该日期缺少汇率历史数据",
      "reasonCode.CALCULATION_ERROR": "计算未能完成",
      "reasonCode.STALE_DATA": "输入数据非最新",
      "common.confirm": "确认", "common.cancel": "取消", "common.save": "保存",
      "common.edit": "编辑", "common.language": "语言",
      "common.seeAllInsights": "查看全部洞察({n}个)",
      "common.showSectionDetail": "查看详情",
      "claim.referenceLabel": "参考：",
      "common.to": "至",
      "settings.title": "投资组合设置 / 政策",
      "settings.reportingCurrency": "报告币种",
      "settings.reportingCurrencyNote": "此为 HG1 原型的模拟切换——按历史汇率重算每一个依赖报告币种的数值（历史序列、汇率归因、证据包数值）属于优先级 D 的实施工作（见 PD-0012），本原型未实现。此设置永不影响证券自身的原始交易币种。",
      "settings.benchmark": "基准指数",
      "settings.benchmarkNote": "在此更改基准指数目前不会重新计算本原型的数值——下方的超额收益、贝塔系数、阿尔法及证券市场线仍基于 MSCI 全球指数（ACWI）计算，这是本页面所有数值实际使用的基准。生产环境中的基准切换应重新计算并更新每一个相关标签；此控件仅用于演示选择交互，不会将基于 MSCI ACWI 的数值错误标注为其他基准的结果。",
      "settings.language": "语言",
      "settings.explanationMode": "解释深度",
      "settings.explanationModeNote": "控制总览、投资组合、分析和情景实验室各页面上每个结论默认显示的详细程度——简要、简明或专业。与页眉中的深度控件是同一项设置;在此更改也会同步更改该控件。任意单张卡片自身的深度控件仍可让您单独深入了解该项数值。",
      "settings.colorConvention": "涨跌颜色约定",
      "settings.colorConventionIntl": "国际惯例：涨绿跌红",
      "settings.colorConventionCn": "中国大陆惯例：涨红跌绿",
      "settings.colorConventionNote": "无论采用哪种约定，方向永远不只靠颜色表示——▲ / ▼ 符号与明确的正负号始终同时标示方向。",
      "settings.accounts": "账户",
      "settings.policy": "投资组合政策",
      "settings.positionCap": "单一持仓权重上限（%）",
      "settings.sectorCap": "行业集中度上限（%）",
      "settings.saveSimulated": "保存（模拟）",
      "settings.policySavedNote": "模拟操作——不会持久化，刷新后重置。本原型没有政策写入接口；生产版本应在此调用真实接口。",

      "valuationMode.title": "估值时间模式",
      "valuationMode.current": "当前/最新",
      "valuationMode.historical": "历史断面(as-of)",
      "valuationMode.badge": "历史断面 · {date}",
      "valuationMode.intro": "V1 在同一套确定性架构上支持两种估值时间模式——而非两套独立的分析系统。",
      "valuationMode.currentDesc": "按最新可用的市场/参考数据评估投资组合。实时、延迟、收盘价等时效状态均可能出现,取决于具体市场与数据提供方的状态。",
      "valuationMode.historicalDesc": "按特定历史断面时点评估投资组合。任何输入数据均不得晚于该断面时点;绝不会为了让「实时」状态可达而人为使用实时数据。",
      // Post-HG1 Checkpoint A — S1 (designer-33, 2026-09-15): 移除
      // "该工作在 HG1 获批前处于阻塞状态"——自 PD-0017 起该说法已不成立(HG1 =
      // APPROVED)。其余内容保留:本原型仍未实现「当前」模式的计算,仍需要真实的
      // 市场数据基础设施(优先级 A),本构建仍不模拟实时数据源。
      "valuationMode.currentNotComputed": "本原型未实现该模式的计算。完整的「当前」模式计算需要真实的市场数据基础设施(优先级 A)——本构建不会通过模拟实时数据源来让该模式显得已激活。",
      "valuationMode.historicalActive": "本原型呈现的正是这一模式。本构建中的每一个数值均按下方快照日期计算;不使用任何实时或晚于该断面的输入数据。",
      "settings.noPositionCap": "尚未设置单一持仓权重上限。在您于下方设置之前，涉及集中度的洞察将使用比较性/教育性表述，而非个人化阈值。",
      "settings.noSectorCap": "尚未设置行业集中度上限。",
      "settings.positionCapSet": "单一持仓权重上限：",
      "settings.sectorCapSet": "行业集中度上限：",
      "table.security": "证券", "table.qty": "数量", "table.avgCost": "平均成本",
      "table.price": "价格", "table.marketValueUsd": "市值（美元）",
      "table.pctPortfolio": "占组合比例", "table.unrealizedGl": "未实现盈亏",
      "table.freshness": "时效", "table.actions": "",
      "table.position": "持仓", "table.weight": "权重", "table.marketValue": "市值",
      "table.riskMetrics": "风险指标",
      "table.account": "账户", "table.type": "类型", "table.market": "市场",
      "table.currency": "币种", "table.cashBalances": "现金余额",
      "table.date": "日期", "table.txType": "类型", "table.instrument": "证券",
      "table.quantity": "数量", "table.priceAmount": "价格 / 金额",
      "table.reportingConversion": "报告币种换算", "table.note": "备注",
      "pf.portfolioKicker": "投资组合", "pf.accountsAndCash": "账户与现金",
      "pf.holdings": "持仓", "pf.holdingsHint": "按账户分组显示每一笔持仓。点击某一行可查看详情;使用「编辑」进行核对调整。",
      "pf.transactionsActivity": "交易与活动记录",
      "pf.searchHoldingsPlaceholder": "按名称或代码搜索持仓…",
      "pf.noHoldingsMatch": "没有与“{query}”匹配的持仓。",
      "evidence.breadcrumb": "结论 → 关键数值 → 解释 → 证据 → 方法论",
      "evidence.keyNumber": "关键数值", "evidence.explanation": "解释",
      "evidence.proofPacket": "证据（证据包）", "evidence.methodology": "方法论",
      "evidence.notPublished": "尚未发布。",
      "ai.disclaimer": "以下每个数值都直接读取自您投资组合的已计算指标；AI 从不自行键入数字。点击任意高亮数值可查看其来源与方法。",
      "ai.suggestFollowUp": "追问：",
      "scenario.title": "情景实验室 — 假设性分析",
      "scenario.actualLegend": "您真实、已记录的投资组合。",
      "scenario.scenarioLegend": "一种假设性建模结果 — 绝非实际持仓。",
      "scenario.notForecast": "此比较中的每一个数值都是在假设配置下、基于与您实际投资组合相同的历史收益序列（P6）所做的确定性重新计算——是历史回放，而非对未来风险或收益的预测。",
      "scenario.allocationHeader": "配置 — 当前 vs. 情景",
      "scenario.allocationLegendHeader": "分项（当前 → 情景）",
      "scenario.deltaHeader": "分项变动",
      "scenario.riskHeader": "风险 — 当前 vs. 情景",
      "scenario.concentrationHeader": "集中度 — 当前 vs. 情景",
      "scenario.metricHeader": "组合指标 — 夏普比率，当前 vs. 情景",
      "scenario.whatThisMeans": "此情景具体建模了什么？",
      "scenario.introText": "对您的投资组合建模一项假设性变更,并将其与您实际、当前的持仓进行比较。除非您另行编辑,否则以下内容不会改变您的实际投资组合。",
      "scenario.noneDefined": "未定义任何情景。",
      "scenario.hypotheticalInputsLabel": "假设输入建模:",
      "scenario.modField.action": "操作", "scenario.modField.target": "目标",
      "scenario.modField.amount": "金额", "scenario.modField.from": "从", "scenario.modField.to": "至",
      // Post-HG1 Checkpoint A — D3 (designer-33). Chinese counterparts for
      // scenario.action.* above — see that entry's own comment.
      "scenario.action.REDUCE_WEIGHT": "降低权重",
      "scenario.action.ADD_HYPOTHETICAL_INSTRUMENT": "添加假设标的",
      "scenario.action.SHIFT_EXPOSURE": "转移敞口",
      "scenario.colSegment": "分项", "scenario.colCurrent": "当前",
      "scenario.colScenario": "情景", "scenario.colChange": "变化",
      "scenario.centerActual": "实际", "scenario.centerScenario": "情景",
      "scenario.exploreFullDetailBtn": "查看完整详情(实际夏普比率)",
      "scenario.askAboutScenario": "就此情景提问",
      "ingest.title": "导入与录入",
      "ingest.workflow": "工作流程",
      "ingest.csvImport": "CSV 导入", "ingest.ocrImport": "OCR 辅助录入",
      "ingest.step12": "1–2. 上传与列映射", "ingest.step3": "3. 预览与更正",
      "ingest.step4": "4. 导入报告与确认",
      "ingest.sourceColumn": "源列", "ingest.mapsTo": "映射到",
      "ingest.rawRow": "原始行", "ingest.mapped": "映射结果",
      "ingest.statusCol": "状态", "ingest.issuesResolution": "问题 / 处理方式",
      "ingest.confirmImportSimulated": "确认导入(模拟)",
      "ingest.confirmCommitSimulated": "确认并提交至投资组合(模拟)",
      "ingest.importAnyway": "仍然导入", "ingest.skip": "跳过",

      "riskGroup.overallRisk": "整体风险", "riskGroup.marketSensitivity": "市场敏感度",
      "riskGroup.downside": "下行风险", "riskGroup.riskAdjusted": "风险调整后表现",
      "riskGroup.riskDrivers": "风险驱动因素",

      "ov.blockA": "总览 · 我的表现如何?", "ov.blockB": "总览 · 是什么驱动了投资组合?",
      "ov.blockC": "总览 · 主要风险是什么?", "ov.blockD": "总览 · 有哪些值得关注的事项?",
      "ov.blockE": "总览 · 投资组合简报",
      "ov.totalPortfolioValue": "投资组合总价值", "ov.gainLoss1y": "盈亏(1年)",
      "ov.gainLossPct": "盈亏百分比",
      "ov.yourPortfolio": "您的投资组合", "ov.benchmarkAcwiSeries": "基准(MSCI ACWI)",
      "ov.askAboutThisChart": "就此图表提问",
      "ov.majorHoldings": "主要持仓",
      "ov.holdingsDetailTop5": "持仓明细(前5大,共{n}个持仓)",
      "ov.showEntirePortfolio": "显示完整投资组合(共{n}个持仓)",
      "ov.viewFullHoldings": "查看完整持仓与交易记录 →",
      "ov.summarizeExposures": "总结我的最大敞口",
      "ov.assetMix": "资产构成",
      "ov.largestAssetClassAllocation": "{label} 是您最大的资产类别配置,占比 {pct}。",
      "ov.seeBreakdown": "查看行业、上市地/经济地理及货币敞口明细",
      "ov.sectorExposureDirect": "行业敞口 — 仅限直接持有的股票",
      "ov.noDirectEquitySector": "本投资组合中没有可分类的直接股票行业敞口。",
      "ov.notSectorsCaveat": "以下类别并非行业——它们是集合基金、固定收益/其他非股票工具,以及结构性/不支持的持仓,单独列示是为了避免基金被当作行业呈现。ETF 穿透(说明基金自身底层行业敞口)不在 V1 范围内。",
      "ov.byListingMarket": "按上市地划分", "ov.byEconomicGeography": "按经济地理划分",
      "ov.currencyExposure": "货币敞口",
      "ov.rolling90dVolatility": "滚动90日波动率", "ov.top5Concentration": "前五大持仓集中度",
      "ov.explainThisRisk": "解释此风险",
      "ov.explainRiskStatsFull": "完整解释这些风险指标(贝塔、索提诺比率、集中度)",
      "ov.noInsightsFlagged": "目前没有标记任何洞察。",
      "ov.acrossPortfolio": "遍及您的投资组合。",
      "ov.warningCount": "个警告", "ov.attentionItemCount": "个关注事项",
      "ov.askFollowUpBtn": "追问",
      "ov.outperformed": "跑赢了", "ov.underperformed": "跑输了",
      "ov.returnedSentence": "过去一年,您的投资组合收益率为 {chip},{direction}基准 {chip2}。",
      "ov.fxReduced": "降低了", "ov.fxAddedTo": "提高了",
      "ov.fxSentence": "汇率变动{direction}本期以报告货币计的收益率,约 {chip}。",
      "ov.volatilitySentence": "历史上,本期年化波动率为 {chip}。",
      "ov.concentrationSentence": "您的前五大持仓占投资价值的 {chip},是当前集中度风险的最大单一驱动因素。",
      "ov.snapshotAsOf": "快照时间:{date},报告货币为 {ccy}。",

      "an.performance": "表现", "an.riskReturnProfile": "风险与回报概况",
      "an.rollingAnalyticsDrawdown": "滚动分析与回撤", "an.exposure": "敞口",
      "an.correlationClustering": "相关性与聚类",
      "an.contributionToRisk": "对投资组合风险的贡献",
      "an.analyticsKicker": "分析",
      "an.analyticsLead": "针对您跨境投资组合的表现、风险与敞口分析——与总览和投资组合页面基于相同的底层事实,但呈现完整的分析深度。",
      "an.benchmarkNoteAcwi": "基准:MSCI ACWI,下方所有数值实际使用的基准。",
      "an.benchmarkNoteOtherPrefix": "设置中显示已选择「",
      "an.benchmarkNoteOtherSuffix": "」,但下方所有数值仍基于 MSCI ACWI 计算——本原型尚未针对不同的基准选择重新计算基准相关统计量(详见设置中的说明)。",
      "an.localVsCurrencyContribution": "本币市场与汇率贡献分解(过去一年)",
      "an.localMarketReturn": "本币市场收益", "an.fxEffect": "汇率影响",
      "an.trailing1yReturnCategory": "过去一年收益率",
      "an.explainThisSplit": "解释此拆分",
      "an.csopRiskMetricsSuffix": " — 风险指标",
      "an.rollingVol90dAnnualized": "90日滚动波动率(年化)",
      "an.portfolioDrawdown": "投资组合回撤",
      "an.realizedReturnVsBeta": "已实现收益率 vs. 贝塔 — 事后市场线(过去一年)",
      "an.betaVsAcwiAxis": "贝塔 vs. MSCI ACWI — 过去一年,日频收益率",
      "an.realizedTotalReturnAxis": "已实现总收益率,过去一年,美元(USD),复利计算",
      "an.observationsSuffix": " 个观测值",
      "an.windowTrailingDaily": "过去一年 · 日频收益率",
      "chart.rollingWindow90d": "过去一年 · 日频收益率 · 90日滚动窗口",
      "an.benchmarkBetaDefinition": "按定义,基准的贝塔为1。",
      "an.pointDetailTemplate": "{label} — 贝塔 {beta},过去一年收益率 {ret}。",
      // HG1 ux_planning revision (review-06, secondary) — mirrors the English rename
      // immediately above; matches js/data.js's exposure.listingMarket/
      // exposure.assetClass/metric.concentration i18n.zh.label fields exactly.
      "an.byListingMarket": "上市地敞口", "an.byEconomicGeographyCountry": "按经济地理划分(国家/地区)",
      "an.assetClass": "资产类别敞口", "an.sectorDirectEquityOnly": "行业(仅限直接持有的股票)",
      "an.currencyExposureHeading": "货币敞口", "an.concentrationHeading": "集中度(前五大)",
      "an.viewFullCorrelationMatrix": "查看完整相关性矩阵(专业层级)",
      "an.sleeveCorrelationMatrixTitle": "板块相关性矩阵",
      "an.trailing1yDaily5series": "过去一年日频收益率,共5个序列。完整两两相关矩阵。",
      "an.strongestRelationshipTemplate": "{a} 与 {b} 在本样本中显示出最强的历史相关性,相关系数为 {chip}。",
      "an.weakestRelationshipTemplate": " {a} 与 {b} 显示出最弱(最具分散化效果)的相关性,为 {chip}。",
      "an.capitalWeightVsRiskContribution": "资本权重 vs. 风险贡献",
      "an.capitalWeight": "资本权重", "an.riskContribution": "风险贡献",
      "an.sleeveDivergenceCaveat": "一个板块所承担的风险可能高于(或低于)其资本权重单独所暗示的水平——这里直接展示这种差异,而非仅呈现两个孤立的数字。",
      "an.askAboutAnalyticsView": "就此分析视图提问",
      "an.noBreakdownAvailable": "暂无明细数据。",
      "an.professionalDepthHeading": "方法论与假设(专业层级)",

      "chart.portfolio": "投资组合", "chart.yourPortfolio": "您的投资组合",
      "chart.benchmark": "基准", "chart.sleeve": "板块",
      "chart.securityMarketLineExPost": "证券市场线(事后)",
      "chart.thisPeriodPrefix": "本期:", "chart.vsBenchmarkSuffix": " vs. 基准",
      "chart.maxDrawdownPrefix": "最大回撤 ",
      "chart.capitalWeight": "资本权重", "chart.riskContribution": "风险贡献",
      "chart.insufficientData": "数据不足",
      "chart.drawdownLabel": "回撤", "chart.differencePrefix": "差值:",
      "chart.notAvailable": "无数据",
      "chart.lineDistancePrefix": "直线距离 ", "chart.historicalSuffix": "(历史数据)",

      "sector.pooledFund": "集合/基金敞口(无穿透)",
      "sector.fixedIncome": "固定收益/非股票",
      "sector.structuredUnsupported": "结构性/不支持",

      "judgmentClass.Fact": "事实", "judgmentClass.Interpretation": "解读",
      "judgmentClass.Preference-dependent judgment": "取决于个人偏好的判断",

      "common.search": "搜索", "common.na": "不适用",
      "common.reviewAndStage": "审核并暂存",
      "common.confirmAndAdd": "确认并新增(模拟)",
      "common.backToEdit": "返回编辑",
      "common.simulatedEntryNote": "模拟操作,此处内容不会被持久化。",

      "pf.accountsStat": "账户",
      "pf.addPositionBtn": "+ 新增持仓", "pf.addTransactionBtn": "+ 新增交易",
      "pf.addAccountBtn": "+ 新增账户", "pf.importStatementBtn": "导入对账单(CSV / OCR)",
      "pf.noneOnFile": "暂无记录",
      "pf.cashNativeCurrencyNote": "现金余额以原始货币显示。此处没有可用的汇率接口可将现金折算为报告货币。",
      "pf.addCashBalanceBtn": "+ 新增现金余额",
      "pf.listingSuffix": "{market} 上市",
      "pf.riskAnalyticsUnsupported": "该证券不支持风险分析",
      "pf.notProvided": "未提供",
      "pf.inKindTransferTitle": "实物转入——原始成本基础未由转出券商提供。",
      "pf.cashLabel": "现金:",
      "pf.allAccounts": "所有账户", "pf.allTypes": "所有类型",
      "pf.noConversionClaimNote": "此交易未记录换算结果",
      "pf.holdingInspectorDetail": "账户:{account} · 上市地:{listing} · 经济地理:{geo}",
      "pf.securitySearchLabel": "证券搜索 / 标识符",
      "pf.securitySearchPlaceholder": "股票代码、名称或标识符(如 AAPL、0700.HK、TSMC)",
      "pf.ambiguousMatchNote": "找到多个可能匹配项。请在下方选择正确的证券——系统绝不会静默解析一个存在歧义的身份。",
      "pf.matchedTemplate": "已匹配:{id} — {name}({market} 上市)",
      "pf.noMatchNote": "在此演示投资组合已知的证券中未找到匹配项。您仍可记录此标识符;它将按原样保留,标记为未核实,而非被系统猜测。",
      "pf.unverifiedIdentifierLabel": "{query}(未核实的标识符)",
      "pf.newPositionTitle": "新建手动持仓",
      "pf.simulatedPositionNote": "模拟录入,用于演示预期工作流程(PRD §27.1)。此处内容不会写入本原型其他位置显示的账本。",
      "pf.qtyPlaceholderExample": "例如 100",
      "pf.averageCost": "平均成本",
      "pf.avgCostHint": "若未知可留空——缺失的成本基础将渲染为「数据不足」,而不会是一个编造出来的数值。",
      "pf.avgCostPlaceholder": "每股/每单位,原始货币",
      "pf.acquisitionDate": "买入日期",
      "pf.ccyOverrideSecurityLabel": "此证券的交易货币与账户货币不同",
      "pf.currencyOverride": "货币覆盖",
      "pf.qtyRequired": "数量为必填项。",
      "pf.resolveSecurityFirstLong": "请先搜索并解析证券身份(或接受未核实的标识符),然后再暂存。",
      "pf.newTransactionTitle": "新建手动交易",
      "pf.simulatedTransactionNote": "模拟录入,用于演示预期工作流程(PRD §27.2)。此处内容不会写入本原型其他位置显示的账本。",
      "pf.qtyTxHint": "买入/卖出/转仓为必填;仅涉及现金的条目(存款、取款、外汇)可留空。",
      "pf.ccyOverrideTxLabel": "此交易的货币与账户货币不同",
      "pf.newAccountTitle": "新建账户",
      "pf.accountName": "账户名称",
      "pf.accountNamePlaceholder": "例如 Interactive Brokers (US)",
      "pf.marketGlobalMulti": "全球/多币种",
      "pf.accountNameRequired": "账户名称为必填项。",
      "pf.confirmAndCreate": "确认并创建(模拟)",
      "pf.addCashTitle": "新增现金余额",
      "pf.amount": "金额",
      "pf.amountRequired": "金额为必填项。",
      "pf.confirmSimulated": "确认(模拟)",
      "pf.editRowNoteTemplate": "正在编辑 {id} ——核对调整演示。模拟操作:变更不会被持久化。",
      "pf.unitsAccountTemplate": "{qty} 单位,账户 {account}",
      "pf.avgCostSuffixTemplate": ",平均成本 {amount} {ccy}",
      "pf.avgCostNotProvidedSuffix": ",未提供平均成本",
      "pf.acquiredSuffixTemplate": ",购入日期 {date}",
      "pf.previewOnlyPositionNote": "仅为预览。确认后将模拟新增此持仓——不会更改上方的持仓表格。",
      "pf.simulatedPositionWrittenNote": "模拟操作:这将被写入您的账本。本原型不会持久化此操作——上方的持仓表格保持不变。",
      "pf.noDateEntered": "未填写日期",
      "pf.qtyInlineLabel": "数量",
      "pf.previewOnlyTransactionNote": "仅为预览。确认后将模拟新增此交易——不会更改上方的交易表格。",
      "pf.simulatedTransactionWrittenNote": "模拟操作:这将被写入您的账本。本原型不会持久化此操作——上方的交易表格保持不变。",
      "pf.previewOnlyAccountNote": "仅为预览。确认后将模拟创建此账户——不会出现在上方的「账户与现金」中。",
      "pf.simulatedAccountCreatedNote": "模拟操作:该账户将随即存在。本原型不会持久化此操作。",
      "pf.previewOnlyCashNote": "仅为预览。确认后将模拟记录此余额——不会更改上方的「账户与现金」。",
      "pf.simulatedCashRecordedNote": "模拟操作:此现金余额将随即被记录。本原型不会持久化此操作。",
      "pf.reconciliationStagedTemplate": "核对调整已暂存(模拟)——数量 {qty},平均成本 {avgCost},账户 {account}。未持久化;上方表格保持不变。",
      "pf.avgCostNotProvidedShort": "未提供",

      "ingest.introNote": "此处演示两条导入路径:CSV 导入(PRD §27.3,核心 V1 功能)与 OCR 辅助录入(经明确人工决策纳入 V1 范围——见 specs/OCR_INGESTION_ADDENDUM.md)。两者共享同一条不变量:此处任何操作都不会静默改变您的投资组合。每一条暂存的行或字段都带有「暂存」标记,只有在您本人明确确认后才会计入账本。",
      "ingest.csvFileNoteTemplate": "文件:{filename} ——模拟上传;实际并未读取任何文件。演示 PRD §27.3 针对固定示例导出文件的 CSV 导入规范。",
      "ingest.colMeaning.date": "日期", "ingest.colMeaning.ticker": "股票代码 / 证券标识符",
      "ingest.colMeaning.txType": "交易类型", "ingest.colMeaning.quantity": "数量",
      "ingest.colMeaning.price": "价格", "ingest.colMeaning.account": "账户",
      "ingest.unmapped": "(未映射)", "ingest.missingValue": "缺失",
      "ingest.reportSummaryTemplate": "已暂存:{staged} · 已确认:{confirmed} · 已隔离:{quarantined}",
      "ingest.importConfirmedNote": "导入已确认(模拟)。这将写入您的账本——本原型不会持久化此操作;「持仓与活动」中的交易表格保持不变。",
      "ingest.resolveBeforeConfirm": "请先处理上方每一条存在歧义、缺失或可能重复的行(或明确跳过),然后再确认导入。",
      "ingest.willImportAnyway": "将仍然导入", "ingest.willSkipDuplicate": "将作为重复项跳过",
      "ingest.supplyMissingTemplate": "请补充缺失的{field}",
      "ingest.ocrSimNote": "根据所有者的明确指示,本原型使用固定示例文档模拟 OCR 提取——此处不存在也未构建任何生产级 OCR 流水线。",
      "ingest.ocrVocabNote": "OCR 置信度(高 / 低 / 可能匹配 / 缺失 / 可能重复 / 已更正 / 已确认)与指标的数据充分性状态(可用 / 有限 / 数据不足)是两套不同的词汇体系。下方标记仅使用 OCR 词汇——本页面任何指标数值都不会以 OCR 置信度标记渲染,任何 OCR 字段也不会通过指标状态渲染器渲染。",
      "ingest.confidence.staged": "暂存待复核",
      "ingest.confidence.lowConfidence": "低置信度",
      "ingest.confidence.ambiguousMatch": "可能匹配",
      "ingest.confidence.missing": "缺失",
      "ingest.confidence.possibleDuplicate": "可能重复",
      "ingest.confidence.corrected": "已更正",
      "ingest.confidence.confirmed": "已确认",
      "ingest.confidence.highConfidence": "高置信度",
      "ingest.confidence.ok": "正常",
      "ingest.step.upload": "上传", "ingest.step.extract": "提取", "ingest.step.resolve": "解析",
      "ingest.step.stage": "暂存", "ingest.step.review": "审核", "ingest.step.confirm": "确认",
      "ingest.step.commit": "提交",
      "ingest.sourceLineTemplate": "来源:{sourceType} · 上传时间 {uploadedAt} · 文档编号 {id}",
      "ingest.extractedTemplate": "提取结果:{value}",
      "ingest.extractedNothing": "提取结果:未能读取到任何内容——留空,而非推断(OCR-6 / OCR-7)。",
      "ingest.correctedToTemplate": "已更正为:{value}(由 {who} 于 {when})",
      "ingest.confirmedByTemplate": "由 {who} 于 {when} 确认",
      "ingest.sourceEvidencePointerSuffix": " ——来源证据指针(OCR-2)。",
      "ingest.ambiguousSelectNote": "身份存在歧义——请选择正确的证券。系统绝不会自动猜测(OCR-5)。",
      "ingest.correctionOptionalLabel": "更正——空白字段绝不会被自动填充",
      "ingest.enterCorrectValuePlaceholder": "输入正确的值(可选)",
      "ingest.quarantineFieldLabel": "隔离此字段——在不含此字段的情况下提交本文档的其余部分",
      "ingest.possibleDuplicateNote": "可能与已有交易重复。请选择处理方式。",
      "ingest.committedSimulatedNote": "已提交(模拟)。这将出现在持仓/交易记录中——本原型不会持久化此操作。",
      "ingest.viewInHoldingsBtn": "在持仓中查看",
      "ingest.resolveBeforeCommit": "请先处理上方每一个存在歧义、缺失或可能重复的字段(或明确将其隔离),然后再提交。在字段解决之前,任何内容都不会进入账本(OCR-11)。",

      "ai.contextualQuestionTemplate": "情境问题:{label}",
      "ai.template.positions": "我持有多少个仓位,分布在哪些市场?",
      "ai.template.underperform": "为什么我的投资组合会有这样的表现?",
      "ai.template.changed": "最近有什么变化?",
      "ai.template.exposures": "总结我的最大敞口",
      "ai.template.risk": "解释我的投资组合风险",
      "ai.evidenceButtonTemplate": "证据:{label}",
      "ai.noScenarioSelected": "情景实验室当前未选择任何情景。",
      "ai.performanceNotAvailable": "表现数据不可用。",
      "ai.riskNotAvailable": "风险数据不可用。",
      "ai.positionCountLabel": "持仓数量", "ai.distinctMarketsLabel": "不同上市市场数",
      "ai.theCurrentFigureIsPrefix": "当前数值为 ",
      "ai.alsoRelevantPrefix": "同样相关:",
      "ai.scenarioLeadTemplate": "这是「{name}」这一假设情景下的比较。它并不描述您实际、当前的投资组合(P8)——除非您另行编辑,否则不会改变您的实际持仓。",
      "ai.scenarioMetricPrefixTemplate": "在此情景下,{label} 将为 ",
      "ai.briefIntroPrefix": "以下是您投资组合的简要解读。您的投资组合总价值为 ",
      "ai.overTrailingYearPrefix": "过去一年的收益率为 ",
      "ai.whichIsRelativeMid": ",相对基准而言为 ",
      "ai.relativeToItsBenchmarkSuffix": "。",
      "ai.largestHoldingsPrefix": "您的最大持仓占投资价值的 ",
      "ai.youHoldPrefix": "您持有 ", "ai.acrossListingMarketsMid": " 个仓位,分布在 ",
      "ai.listingMarketsSuffix": " 个上市市场。",
      "ai.largestHoldingsShownNote": "按市值排列的最大持仓显示在「投资组合」页面。",
      "ai.currencyMovementLead": "汇率变动占该数值的 ",
      "ai.ofThatFigureSuffix": "",
      "ai.decomposingIntoLead": ",可分解为 ",
      "ai.changedIntro": "以下是当前正在您投资组合上引起关注的事项,按严重程度排序。每一项均可追溯至其自身的证据,并在适用时追溯至方法论。",
      "ai.topHoldingsPrefix": "您的前 ", "ai.topHoldingsSuffix": " 大持仓占 ",
      "ai.ofInvestedValueSuffix": " 的投资价值。",
      "ai.currentAnnualizedVolTemplate": " 当前年化波动率为 ",

      "evidence.comparedAgainstLabel": "对比基准:",
      "evidence.whatThisIs": "这是什么", "evidence.scope": "范围",
      "evidence.dataQualityLimitations": "数据质量与局限性", "evidence.whereToGoNext": "后续可查看",
      "evidence.none": "无", "evidence.notApplicable": "不适用",
      "evidence.sourceDataTimestamps": "源数据时间戳",
      "evidence.methodologyEngineVersion": "方法论 / 引擎版本",
      "evidence.dataFreshnessD5": "数据时效性(D5)",
      "evidence.notYetPublishedFull": "尚未发布。此指标的注册表条目尚未编写——该注册表本身遵循经校验的架构,但在本迭代中大多数指标条目为空(AC-17)。这是诚实的空状态,而非用占位符掩盖缺失内容。",
      "evidence.noMethodologyPointer": "此项声明未记录方法论指引。",
      "evidence.portfolioFactHeader": "投资组合事实——非计算指标",
      "evidence.scenarioHypotheticalHeader": "情景实验室——假设性声明",
      "evidence.scenarioFallbackTemplate": "此数值来自假设情景「{name}」({description})。本原型尚未为这一具体的情景比较数值建立专门的证据包条目——data.js 的证据注册表覆盖指标、持仓、证券、交易和洞察类声明,但不包括 scenario.js 和 ai.js 动态构建的逐情景比较数值。已标记为真实存在的差距,而非以编造内容掩盖。",
      "evidence.notFoundHeader": "证据",
      "evidence.notFoundTemplate": "未找到声明「{id}」对应的证据记录。这可能表明引用它的界面存在失效引用。",
      "evidence.registryTitle": "方法论与证据注册表",
      "evidence.registryIntro": "本产品计算的每一项指标在此都拥有(或将拥有)一条方法论条目:定义、公式、数据输入、最少观测数要求、汇率/公司行为处理方式、已知局限性及版本号。以下部分条目已在本原型中完整填写;大多数则有意显示「尚未发布」——这是一个经过架构校验但尚未编写内容的注册表的诚实状态,而非缺陷。",
      "evidence.noExplanationRecorded": "此项声明未记录解释性文字。",
      "evidence.fact.holdingsCount": "这是对您持仓账本中记录数的直接计数(读取 APP.data.getHoldings().length),并非计算得出的分析指标。它没有公式、基准或年化换算规则,因此不适用任何方法论注册表条目——但该数值本身是真实的,直接读取自您的实际数据,绝非由 AI 估算而来(PD-0008 关于投资组合事实计数的规则)。",
      "evidence.fact.marketsCount": "这是对您持仓账本中不同上市市场数量的直接计数。与上方持仓数量相同的理由适用于此:这是真实的账本事实,而非建模得出的统计量,也不是 AI 自身的估计。",
      "evidence.fact.totalPortfolioValue": "这是您全部持仓市值与现金余额之和(APP.data.getTotalPortfolioValue())——一次账本汇总,而非建模得出的统计量。出于与上方计数相同的理由,它也没有单独的方法论条目。"
    }
  };
  // Sets `_lang` and the document's own lang attribute without triggering a full
  // re-render — used by APP.i18n.setLang (which adds the re-render for a real user-
  // facing language switch) and by verifySectorClassificationLanguageInvariant below
  // (a read-only diagnostic that must not cause the whole app to flicker/re-render
  // three times just to compare a classification's output under both languages).
  function setLangQuiet(l) {
    _lang = (l === "zh") ? "zh" : "en";
    document.documentElement.lang = _lang === "zh" ? "zh-Hans" : "en";
  }
  APP.i18n = {
    getLang: function () { return _lang; },
    setLang: function (l) {
      setLangQuiet(l);
      if (_booted) { renderGlobalHeader(); renderRoute(); }
    },
    // Falls back to English, then to the raw key itself (visibly odd but never blank —
    // the same "never silently disappear" discipline this build applies to numeric
    // placeholders, applied here to a missing translation key instead of a bare string).
    t: function (key) {
      var table = I18N[_lang] || I18N.en;
      if (Object.prototype.hasOwnProperty.call(table, key)) return table[key];
      if (Object.prototype.hasOwnProperty.call(I18N.en, key)) return I18N.en[key];
      return key;
    }
  };
  // Convenience alias — every js/surfaces/*.js file talks to this app only through
  // `ctx.ui`/`ctx.data`/`ctx.charts` (CONTRACT.md's ctx shape never exposed a bare
  // `ctx.i18n`), so the translator is reachable the same way: `ctx.ui.t(key)`, identical
  // to `APP.i18n.t(key)`.
  APP.ui.t = APP.i18n.t;
  // Convenience alias (same reasoning as APP.ui.t above) — lets a surface file branch
  // on current language without needing a bare `ctx.i18n` CONTRACT.md never exposed.
  APP.ui.getLang = APP.i18n.getLang;

  // =======================================================================
  // HG1 Round 5 micro-pass (Item 2) — TEST-ONLY diagnostics for
  // js/i18n-selfcheck.js. Same shape and same discipline as
  // APP.state.setExplanationModeQuiet elsewhere in this file: expose the
  // minimum needed for a read-only verification pass to inspect/restore
  // this module's private state without forcing a visible re-render or
  // reaching into the closure directly. Never called by product code.
  // =======================================================================
  APP.i18n.setLangQuiet = setLangQuiet;
  APP.i18n._allKeys = function () { return Object.keys(I18N.en); };
  // Reads/writes a single key in one language's table directly — used only to
  // construct and then clean up an injected defect (a key present in `en` with
  // no real `zh` counterpart), proving the completeness check below actually
  // detects that condition rather than trivially always passing. `value ===
  // undefined` deletes the key instead of setting it, so a test can restore
  // the dictionary to exactly its pre-test shape, not merely an overwritten one.
  APP.i18n._testSetKey = function (lang, key, value) {
    if (!I18N[lang]) return;
    if (value === undefined) delete I18N[lang][key];
    else I18N[lang][key] = value;
  };
  // Stage-5 testability seam (see normalizeUrlLocale near boot(), below in this file
  // — hoisted, so this forward reference is safe) — exposes the query-string locale
  // normalizer itself, read-only, so js/selfcheck.js can prove a URL-derived locale
  // and the existing interactive locale path converge on the same state without a
  // browser actually driving the native <select>. Same minimum-exposure discipline
  // as the two diagnostics immediately above; never called by product code.
  APP.i18n._normalizeUrlLocale = normalizeUrlLocale;

  // =======================================================================
  // Structural hook for the bilingual narrative gap (§12.2 — "representative full
  // screens in both languages"; raised on coordinator review). UI CHROME is translated
  // above; a claim's own analytical prose (conclusionQuick/explanationSimple/
  // investorDetail/professionalDetail/referencePoint/caveat/label/formatted) is authored
  // in js/data.js, outside this designer's write path, and is NOT translated by this
  // dictionary — translating only the connective words this file/js/ai.js/js/scenario.js
  // supply around an English claim sentence would produce a mixed-language sentence,
  // which is worse than leaving it English (stated in this designer's handoff, not
  // silently absorbed).
  //
  // This function is the PROPOSED structural fix, made real rather than left as a
  // paragraph: a claim object may optionally carry `claim.i18n = { zh: { <fieldName>:
  // "<translated string>", ... } }`, keyed per-language and per-field so `data.js` can
  // populate it INCREMENTALLY (one field, one language, one metric at a time) without an
  // atomic all-or-nothing translation pass. Every claim-text read site in this file
  // (renderClaim's ladder, appendCaveatSlot, formatClaimValue) now calls this instead of
  // reading `claim[field]` directly, so the moment `data.js` populates `claim.i18n.zh.*`
  // for a given metric, that metric's prose localizes with NO further shell.js change —
  // js/ai.js and js/surfaces/scenario.js (which also read these same claim fields to
  // build narrative sentences) should route through this same function for the same
  // reason, and are flagged to do so in this designer's handoff. Falls back to the
  // English field whenever a translation is absent for that specific field, so a
  // partially-translated claim never renders a blank string.
  APP.ui.localizeClaimField = function localizeClaimField(claim, field) {
    if (!claim) return "";
    var lang = APP.i18n.getLang();
    if (lang !== "en" && claim.i18n && claim.i18n[lang] &&
        Object.prototype.hasOwnProperty.call(claim.i18n[lang], field) &&
        claim.i18n[lang][field] != null) {
      return claim.i18n[lang][field];
    }
    return claim[field];
  };

  // HG1 round-4, second bilingual pass — template substitution for i18n strings that
  // embed a data-driven value (a count, a chip, a date) inside otherwise-translated
  // prose. `{token}` placeholders are replaced by the matching key in `vars`; a token
  // with no matching var is left as literal text (visibly odd, never silently dropped —
  // same "never silently disappear" discipline as APP.i18n.t's own missing-key
  // fallback). Values may themselves be HTML (e.g. a provenance chip) — this function
  // does no escaping of its own, so callers already escape/trust their own vars exactly
  // as they did before this template layer existed.
  APP.ui.tf = function tf(key, vars) {
    var template = APP.i18n.t(key);
    vars = vars || {};
    return template.replace(/\{(\w+)\}/g, function (match, name) {
      return Object.prototype.hasOwnProperty.call(vars, name) ? vars[name] : match;
    });
  };

  // HG1 round-4, second bilingual pass — professional-terminology consistency (§3 of
  // the coordinator's constraints): reuses the EXACT sleeve-name map js/data.js's own
  // sleeveNameZh() establishes (US/HK/CN/Bonds -> 美股/港股/A股/债券) for segment
  // labels that represent the SAME sleeve concept the correlation matrix and
  // contribution-to-risk blocks already show in Chinese — listing-market segments and
  // correlation/contribution labels are that same dimension. A SEPARATE, smaller map
  // handles economic-GEOGRAPHY labels ("US"/"China"), which is a genuinely different
  // dimension (business domicile, not listing market) — conflating the two would reuse
  // "A股" (A-shares, a listing/sleeve concept) for "China" as a business-geography
  // label that also covers Hong Kong-listed, China-domiciled holdings, which would be
  // actively wrong, not just untranslated (the coordinator's own "worse than English"
  // standard). Sector names, asset-class names, and fund/security names have no
  // established Chinese term from js/data.js's own translation pass and are
  // deliberately NOT translated here — inventing one risks exactly the inconsistency
  // §3 warns against; they pass through unchanged (see this designer's handoff).
  // Matches js/data.js's own sleeveNameZh() map exactly, including its two long-form
  // aliases ("Hong Kong" -> 港股, "Mainland China" -> A股) — CONTRIBUTION_TO_RISK's own
  // segment labels ("Hong Kong Equity Sleeve", "Mainland China Equity Sleeve") reduce to
  // these after the " Equity Sleeve"/" Sleeve" suffix strip, so both short ("HK") and
  // long ("Hong Kong") forms must resolve to the identical Chinese term.
  var SLEEVE_LABEL_ZH = {
    "US": "美股", "HK": "港股", "CN": "A股", "Bonds": "债券",
    "Hong Kong": "港股", "Mainland China": "A股",
    // js/data.js's SML_POINTS carries these two literal labels ("Your Portfolio",
    // "Benchmark (MSCI ACWI)") point-by-point — matched here to the SAME Chinese
    // rendering ov.yourPortfolio/ov.benchmarkAcwiSeries already use elsewhere, so a
    // reader never sees two different Chinese terms for the same thing across one
    // screen (the coordinator's own §3 standard).
    "Your Portfolio": "您的投资组合",
    // Exact match takes precedence over the generic "Benchmark (" prefix rule below —
    // guarantees byte-identical Chinese to ov.benchmarkAcwiSeries ("基准(MSCI ACWI)",
    // no space before the parenthesis) rather than the generic rule's spaced variant.
    "Benchmark (MSCI ACWI)": "基准(MSCI ACWI)",
    // HG1 round-4, fourth bilingual pass — js/data.js's FRESHNESS_AXES labels ("US
    // equity", "HK equity", "CN A-share") are the SAME market/sleeve concept this map
    // already translates elsewhere (US/HK/CN -> 美股/港股/A股); reused here rather than
    // a new term, and load-bearing this time, not cosmetic: the Holdings ledger table's
    // Freshness column is a FIXED-width column (one shared grid across all four account
    // tables, per its own establishing comment in js/surfaces/portfolio.js), sized
    // against the widest state actually present in the data — the degraded
    // "CN A-share · Stale/EOD" case. Coordinator-measured: at 1024px, the Chinese
    // rendering of that exact cell ("CN A-share · 收盘价") needed 148px against 145px
    // available, a 3px overflow the English rendering never hit. Shortening "CN
    // A-share" (10 Latin characters) to "A股" (2 CJK characters) removes far more than
    // 3px — it is the correct fix (content-side), not a column-width reallocation,
    // because the fixed grid must stay identical across languages (one column grid, not
    // two divergent ones — the same rule the original three-round Freshness-column
    // saga already established, now extended: "the worst case for a state column is the
    // degraded state in the widest-rendering language").
    "US equity": "美股", "HK equity": "港股", "CN A-share": "A股",
    // Currency codes (canonical) are untouched; only the English word "FX" translates.
    "USD/HKD FX": "USD/HKD 汇率", "USD/CNY FX": "USD/CNY 汇率"
  };
  var GEOGRAPHY_LABEL_ZH = { "US": "美国", "China": "中国", "Hong Kong": "香港", "Mainland China": "中国内地",
    // HG1 Round 5 correction pass — js/data.js's ACCOUNTS[].market carries "GLOBAL"
    // for the one multi-currency cash-sweep account; added here so
    // js/surfaces/portfolio.js's account-market display (which reuses this same
    // translator) has no untranslated fourth value.
    "GLOBAL": "全球" };
  function translateLabelViaMap(label, map) {
    if (APP.i18n.getLang() !== "zh") return label;
    if (Object.prototype.hasOwnProperty.call(map, label)) return map[label];
    // "Benchmark (MSCI ACWI)" — MSCI ACWI itself (canonical) is never touched; only the
    // English word "Benchmark" translates, matching js/data.js's own established
    // "基准 ..." phrasing used throughout its i18n.zh content.
    if (typeof label === "string" && label.indexOf("Benchmark (") === 0) {
      return "基准 (" + label.slice("Benchmark (".length);
    }
    return label;
  }
  APP.ui.translateSleeveLabel = function (label) { return translateLabelViaMap(label, SLEEVE_LABEL_ZH); };
  APP.ui.translateGeographyLabel = function (label) { return translateLabelViaMap(label, GEOGRAPHY_LABEL_ZH); };

  // HG1 ux_planning revision (review-06, B2) — a holding's DISPLAY name, keyed by its
  // own canonical `id` (never translated, never touched by this map). Before this
  // pass, js/surfaces/scenario.js's static zh prose (js/data.js's
  // "scenario.reduceCnExposure" i18n.zh.description) already named four of these
  // holdings in Chinese (腾讯控股/中国移动/阿里巴巴/美团) while Overview's "主要持仓"
  // and Portfolio's holdings table rendered the SAME holdings' raw `h.name` field
  // (English, e.g. "Tencent Holdings") regardless of language — one holding, two
  // different names depending which surface you were on. This map is the single
  // source both surfaces below now read (js/surfaces/overview.js,
  // js/surfaces/portfolio.js), matching the names Scenario Lab's own prose already
  // established rather than inventing new ones. `600519.SS` (Kweichow Moutai) is not
  // named anywhere in Scenario Lab's prose but is named in review-06's own B2 finding
  // as English-only on Overview/Portfolio; its Chinese entry here is the company's own,
  // real, widely-established name — not an invented term, the same standard already
  // applied to every other entry in this map. Every other holding in this build's
  // portfolio (Apple, Microsoft, NVIDIA, the two US-listed funds, CATL, Ping An, the
  // CSOP structured note) has no Chinese name established anywhere else in this app and
  // is deliberately left out of this map — inventing one here risks exactly the
  // inconsistency this fix exists to close (see SLEEVE_LABEL_ZH's own comment on the
  // same judgment for sector/fund names). Canonical identity — `id` ("0700.HK" etc.),
  // `listingMarket`, `currency` — is never read through this map or touched by it; the
  // Security column's own ticker line (js/surfaces/portfolio.js) always renders `h.id`
  // verbatim beside this display name, so a shortened Chinese form is never ambiguous.
  var HOLDING_DISPLAY_NAME_ZH = {
    "0700.HK": "腾讯控股",
    "0941.HK": "中国移动",
    "9988.HK": "阿里巴巴",
    "3690.HK": "美团",
    "600519.SS": "贵州茅台"
  };
  APP.ui.holdingDisplayName = function (holding) {
    if (!holding) return "";
    if (APP.i18n.getLang() === "zh" && Object.prototype.hasOwnProperty.call(HOLDING_DISPLAY_NAME_ZH, holding.id)) {
      return HOLDING_DISPLAY_NAME_ZH[holding.id];
    }
    return holding.name;
  };

  // ---------------------------------------------------------------------
  // PD-0015 Part 2 — sector and asset-class DISPLAY labels are now translated
  // ("Information Technology" -> "信息技术," the owner's own example), while the
  // canonical internal field these strings are read from (js/data.js's `sector`/
  // `assetClass`) is never touched — "translate what a human reads, never what a
  // system joins on" (PD-0015 §2.3). This map covers every sector value actually
  // present in this dataset (checked directly against js/data.js's HOLDINGS, not
  // assumed) plus the four assetClass values; standard GICS-register Chinese terms
  // where a widely-used one exists. Per PD-0015 §3, Chinese register/fluency/glossary
  // quality is explicitly NOT verified by a qualified language reviewer for this
  // pass — flagged here, not silently presented as final.
  var TAXONOMY_LABEL_ZH = {
    "Information Technology": "信息技术", "Communication Services": "通信服务",
    "Industrials": "工业", "Financials": "金融", "Consumer Discretionary": "非必需消费品",
    "Consumer Staples": "日常消费品", "Telecommunications": "电信服务",
    "Equity": "股票", "Equity Fund": "股票基金", "Fixed Income Fund": "固定收益基金",
    "Derivative": "衍生品"
  };
  APP.ui.translateTaxonomyLabel = function (label) { return translateLabelViaMap(label, TAXONOMY_LABEL_ZH); };

  // ---------------------------------------------------------------------
  // HG1 Round 5, Phase 2 (S7 — PD-0015 §2.3). `taxable`/`retirement`/`cash` (js/data.js's
  // ACCOUNTS[].type) previously printed straight from the raw field in every surface
  // that showed it (js/surfaces/portfolio.js's Accounts & Cash table, its Holdings
  // account-title line, and this file's own Settings account list) — "the display
  // string and the grouping key are the same string," PD-0015 §2.3's failure mode by
  // construction. Same fix shape as sector/asset-class above: a canonical
  // CLASSIFICATION step with zero APP.i18n calls in its body (classifyAccountsByType,
  // below — the actual, real aggregation this build groups accounts by, not merely a
  // hypothetical one, so the language-invariance guarantee is testable against
  // something genuinely used), and a separate DISPLAY step (translateAccountType)
  // applied by the caller. "Translate what a human reads, never what a system joins
  // on" — the canonical `type` string itself is never touched.
  // ---------------------------------------------------------------------
  var ACCOUNT_TYPE_LABEL_ZH = { taxable: "应税账户", retirement: "退休账户", cash: "现金账户" };
  APP.ui.translateAccountType = function (type) {
    if (APP.i18n.getLang() !== "zh") return type;
    return Object.prototype.hasOwnProperty.call(ACCOUNT_TYPE_LABEL_ZH, type) ? ACCOUNT_TYPE_LABEL_ZH[type] : type;
  };

  // HG1 Round 5, Phase 2 correction pass (Blocker 3 — "the same display-string-is-
  // the-grouping-key defect class already fixed correctly for account type,"
  // reviews/gates/HG1_ROUND5_PHASE2_CORRECTION_VERIFICATION.md §2). Identical shape
  // to ACCOUNT_TYPE_LABEL_ZH/translateAccountType immediately above: js/surfaces/
  // portfolio.js's `t.type` (js/data.js's TRANSACTIONS[].type — BUY/SELL/DIVIDEND/
  // DEPOSIT/WITHDRAWAL/FX/TRANSFER_IN/TRANSFER_OUT) is the canonical, filterable
  // grouping key and is NEVER touched; only the DISPLAY label a caller renders
  // (the Transactions table's Type column, its type filter's option labels, and the
  // "New transaction" form's type-select option labels) is translated here.
  // Vocabulary reused, not invented: 买入/卖出/存款/取款/外汇 are the EXACT words
  // `pf.qtyTxHint`'s own zh string already establishes for this same BUY/SELL/
  // deposit/withdrawal/FX vocabulary (a single source, per PD-0014 §2.5 — not a
  // second, independently-chosen name for the same concept); 转入/转出 give
  // TRANSFER_IN/TRANSFER_OUT the directional distinction that hint's own collective
  // "转仓" does not need to make.
  var TRANSACTION_TYPE_LABEL_ZH = {
    BUY: "买入", SELL: "卖出", DIVIDEND: "股息", DEPOSIT: "存款", WITHDRAWAL: "取款",
    FX: "外汇", TRANSFER_IN: "转入", TRANSFER_OUT: "转出"
  };
  // HG1 ux_planning revision (review-07, P1 item 5) — English previously fell through
  // this function's own `if (lang !== "zh") return type` line and rendered the raw
  // canonical enum value verbatim (js/data.js's TRANSACTIONS[].type — the English "All
  // types" filter combobox listed "DEPOSIT, BUY, DIVIDEND, FX, TRANSFER_IN" etc.
  // directly). Same shape of fix as TRANSACTION_TYPE_LABEL_ZH immediately above — a
  // finite DISPLAY-label map for the same finite, known set of type values, never
  // touching the canonical value itself. Every rendered use of translateTransactionType
  // (the Transactions table's Type column, its type filter's option labels, and the
  // "New transaction" form's type-select option labels — js/surfaces/portfolio.js) now
  // gets a real label in BOTH languages; option `value` stays the raw enum in every
  // caller (unchanged by this fix), so filtering still keys on the canonical value.
  var TRANSACTION_TYPE_LABEL_EN = {
    BUY: "Buy", SELL: "Sell", DIVIDEND: "Dividend", DEPOSIT: "Deposit", WITHDRAWAL: "Withdrawal",
    FX: "FX", TRANSFER_IN: "Transfer In", TRANSFER_OUT: "Transfer Out"
  };
  APP.ui.translateTransactionType = function (type) {
    var map = APP.i18n.getLang() === "zh" ? TRANSACTION_TYPE_LABEL_ZH : TRANSACTION_TYPE_LABEL_EN;
    return Object.prototype.hasOwnProperty.call(map, type) ? map[type] : type;
  };

  // HG1 Round 5 micro-pass (Item 3) — js/data.js's TRANSACTIONS[].note is a
  // human-authored, human-facing description of what a transaction WAS ("Wire
  // funding," "In-kind transfer from a legacy custodian...") — application
  // narrative, not source-upload content (contrast with ingest.js's CSV row
  // previews, which are literally the user's own file). js/surfaces/
  // portfolio.js's Transactions table renders `t.note` directly; this was
  // previously never routed through any i18n step, so every note rendered in
  // English regardless of language — a true UI gap, not a canonical exemption.
  // Exact-string map (like SLEEVE_LABEL_ZH/TAXONOMY_LABEL_ZH above), the
  // established shape this codebase already uses for finite, known,
  // non-enumerable-by-pattern content — covers every DISTINCT `note` value
  // TRANSACTIONS actually contains (checked against js/data.js, not invented).
  // Falls through to the original English for any note this map does not name,
  // matching every other translator function's own "never silently drop
  // content" rule.
  var TRANSACTION_NOTE_ZH = {
    "Initial funding": "初始入金",
    "Wire funding": "电汇入金",
    "Rebalance funding transfer": "再平衡资金划转",
    "Wire funding, China A-share brokerage account opened": "电汇入金,中国内地A股券商账户已开立",
    "Placeholder — no sells this period; kept for taxonomy coverage": "占位记录——本期无卖出;保留用于分类覆盖测试",
    "In-kind transfer from a legacy custodian; original cost basis not provided by sending broker":
      "以实物形式从原托管机构转入;发送方券商未提供原始成本基础",
    "Reporting-currency conversion pending — no FX print on file yet for this transaction date":
      "报告货币换算待定——该交易日期尚无可用的汇率成交记录"
  };
  APP.ui.translateTransactionNote = function (note) {
    if (!note || APP.i18n.getLang() !== "zh") return note;
    return Object.prototype.hasOwnProperty.call(TRANSACTION_NOTE_ZH, note) ? TRANSACTION_NOTE_ZH[note] : note;
  };

  // HG1 Round 5 micro-pass (Item 3) — js/data.js's OCR_FIXTURE[].sourceType
  // (portfolio_screenshot/brokerage_screenshot/statement) is an internal,
  // lowercase-with-underscore CLASSIFICATION of the uploaded document, not the
  // document's own filename or content — js/surfaces/ingest.js's
  // "ingest.sourceLineTemplate" composes it directly into an otherwise fully
  // translated sentence ("来源:{sourceType}..."), so an untranslated value here
  // is a genuine mixed-language defect, not a source-content exemption (it is
  // not text an upload contains — it is an application-authored classification
  // of that upload, the exact PD-0015 §2.3 distinction already drawn for sector/
  // asset-class/account-type labels above, applied to this one additional,
  // small, enumerable field).
  var OCR_SOURCE_TYPE_ZH = {
    portfolio_screenshot: "投资组合截图",
    brokerage_screenshot: "券商截图",
    statement: "对账单"
  };
  APP.ui.translateOcrSourceType = function (sourceType) {
    if (APP.i18n.getLang() !== "zh") return sourceType;
    return Object.prototype.hasOwnProperty.call(OCR_SOURCE_TYPE_ZH, sourceType) ? OCR_SOURCE_TYPE_ZH[sourceType] : sourceType;
  };

  // HG1 Round 5 micro-pass (Item 3) — the remaining application-authored English
  // prose inside js/data.js's CSV_FIXTURE/OCR_FIXTURE: three CSV row `issues[]`
  // explanations, three OCR field `note`s, the eight OCR field `label`s (each a
  // short description built from a canonical security name/row reference plus an
  // English descriptor — e.g. "Tencent Holdings (0700.HK) quantity" — the
  // canonical fragment is preserved verbatim below; only the descriptor is
  // translated), and the two OCR `candidates` entries for the one ambiguous-
  // security field. All of this is APPLICATION narrative explaining what the
  // ingestion pipeline found/did — not the user's own uploaded file content
  // (contrast with CSV_FIXTURE.rows[].raw, which is exempt as source content) —
  // so it belongs in a translation map, not the allowlist. One combined
  // exact-string map (same established shape as TRANSACTION_NOTE_ZH above);
  // falls through to the original English for anything not named, so a future
  // fixture addition degrades to "still English," never a thrown error or
  // fabricated translation.
  var INGEST_FIXTURE_TEXT_ZH = {
    // CSV_FIXTURE.rows[].issues[]
    "\"TSMC\" matches both TSM (NYSE ADR) and 2330.TW (TWSE) — resolve before import.":
      "「TSMC」同时匹配 TSM(纽约证券交易所存托凭证)和 2330.TW(台湾证券交易所)——请在导入前解决。",
    "Quantity column was blank in the source file — left empty, not inferred.":
      "源文件中的「数量」列为空——保持留空,未做推断。",
    "Matches existing transaction tx-0022 (same date, symbol, quantity, price).":
      "与现有交易 tx-0022 相匹配(日期、代码、数量、价格均相同)。",
    // OCR_FIXTURE.documents[].fields[].note
    "Character recognition for the listing suffix was unclear; candidate readings: '9988.HK' or '9988.SS'.":
      "上市后缀的字符识别结果不清晰;候选读数为「9988.HK」或「9988.SS」。",
    "Field was blank/unreadable in the source image — left empty, not inferred (OCR-6/OCR-7).":
      "源图像中该字段为空/无法读取——保持留空,未做推断(OCR-6/OCR-7)。",
    "Matches existing transaction tx-0014 (same date range, symbol, quantity, price).":
      "与现有交易 tx-0014 相匹配(日期区间、代码、数量、价格均相同)。",
    // OCR_FIXTURE.documents[].fields[].label — canonical security name / row
    // reference kept verbatim; only the trailing English descriptor translates.
    "Tencent Holdings (0700.HK) quantity": "Tencent Holdings (0700.HK) 数量",
    "China Mobile (0941.HK) average cost": "China Mobile (0941.HK) 平均成本",
    "Row 7 security name": "第7行 证券名称",
    "Row 9 security name": "第9行 证券名称",
    "Row 11 cost basis": "第11行 成本基础",
    "Row 12: Meituan (3690.HK), 300 sh @ HKD 102.00": "第12行:Meituan (3690.HK),300股 @ 102.00港元",
    "Row 7 security name (corrected)": "第7行 证券名称(已更正)",
    "CATL (300750.SZ) quantity": "CATL (300750.SZ) 数量",
    // OCR_FIXTURE.documents[0].fields[3].candidates[] — canonical ticker/name
    // kept verbatim; only the parenthetical English descriptor translates.
    "9988.HK — Alibaba Group (HK listing)": "9988.HK — Alibaba Group(香港上市)",
    "BABA — Alibaba Group (NYSE ADR)": "BABA — Alibaba Group(纽约证券交易所存托凭证)",
    // js/surfaces/ingest.js's CSV_AMBIGUOUS_CANDIDATES — same shape as the OCR
    // candidates immediately above (canonical ticker/name kept verbatim, only
    // the descriptor translates), for the CSV import path's own "TSMC" ambiguity.
    "TSM — Taiwan Semiconductor Mfg. (NYSE ADR)": "TSM — Taiwan Semiconductor Mfg.(纽约证券交易所存托凭证)",
    "2330.TW — Taiwan Semiconductor Mfg. (TWSE)": "2330.TW — Taiwan Semiconductor Mfg.(台湾证券交易所)"
  };
  APP.ui.translateIngestFixtureText = function (str) {
    if (!str || APP.i18n.getLang() !== "zh") return str;
    return Object.prototype.hasOwnProperty.call(INGEST_FIXTURE_TEXT_ZH, str) ? INGEST_FIXTURE_TEXT_ZH[str] : str;
  };

  // =======================================================================
  // HG1 Round 5, Phase 2 correction pass — Blocker 3's own instruction: "the
  // allowlist that encodes the distinction [true UI gap vs. intentionally
  // untranslated canonical/source content] should be a real artifact in the code
  // ... not a regex buried in a report." This is that artifact.
  //
  // A residual-English scan over this app's rendered DOM in `lang=zh` will always
  // find SOME English, and not all of it is a defect: canonical identifiers,
  // tickers, MICs, exchanges, ISO currency codes, canonical taxonomy/grouping
  // keys, and a CSV upload's own column names / literal row-preview content are
  // ENGLISH BY DEFINITION — translating them would either break identity (a
  // ticker is not a word) or misrepresent a user's own uploaded file as
  // application-authored UI (PD-0015 §2.3's "translate what a human reads, never
  // what a system joins on," extended here to "never what the user's own file
  // said"). `APP.i18n.isAllowlistedCanonical(str, opts)` is the single, checkable
  // place this distinction lives — a future language-invariance assertion
  // (js/selfcheck.js already has two siblings: verifySectorClassificationLanguage
  // Invariant, verifyAccountTypeLanguageInvariant) or an external residual-scan
  // tool can call this instead of re-deriving the same judgment ad hoc per scan.
  //
  // HG1 Round 5 MICRO-PASS (Item 2) — the prior round's own §3.1 finding: run
  // ALONE, this artifact returned `exempt: 0` on Overview, because it did not yet
  // cover canonical security names, user-entered account names, product
  // brand/banner text, or composed source-row previews using the fixture's
  // MAPPED (not just raw) field keys. Extended below, category by category, per
  // this pass's own instruction: classify by category/semantics wherever
  // practical, not by copying literals off a screenshot. Two of the four new
  // categories below are DERIVED LIVE from `APP.data` (security names, account
  // names) rather than enumerated, specifically so a fixture change needs no
  // allowlist edit — the failure mode this pass was asked to avoid.
  //
  // This is still not exhaustive over every string this app could ever render
  // (open-ended prose has no shape to allowlist by) — it is exhaustive over the
  // categories named in this pass's own brief.
  APP.i18n.CANONICAL_CONTENT_ALLOWLIST = {
    // ISO 4217 currency codes this app actually uses (js/data.js's ACCOUNTS/
    // HOLDINGS/TRANSACTIONS `currency` fields) — never translated, per PD-0012 §3
    // ("Canonical identifiers remain independent of localisation... HKD").
    currencyCodes: ["USD", "HKD", "CNY"],
    // Canonical index/benchmark identifiers a reader may select in Settings
    // (js/shell.js's benchmark selector) or see cited in an Analytics claim —
    // the parenthetical ticker-style code is canonical; only the surrounding
    // English word ("Benchmark") translates (see translateLabelViaMap's own
    // "Benchmark (" rule above).
    benchmarkIdentifiers: ["MSCI ACWI", "S&P 500 (SPX)", "MSCI ACWI (ACWI)"],
    // The uploaded CSV fixture's own RAW column headers (js/surfaces/ingest.js's
    // CSV_COLUMN_MEANING_KEY — kept as a literal duplicate of that map's keys
    // here, not a cross-file reference, because ingest.js's copy is a private,
    // unexported `var`; both lists must be kept in sync if either changes, and
    // each file's own comment now points at the other). These are the SOURCE
    // FILE's column headers, not application-authored UI — translating them
    // would misrepresent what the user actually uploaded.
    csvColumnNames: ["Date", "Symbol", "Action", "Quantity", "Price", "Account"],
    // NEW (Item 2) — the SAME six concepts as csvColumnNames above, but under the
    // fixture's own internal MAPPED field keys (js/data.js's CSV_FIXTURE.rows[].
    // mapped — "ticker" not "Symbol", "type" not "Action", "accountId" not
    // "Account"). js/surfaces/ingest.js's "Mapped" column renders these as the
    // SAME "Label: value" composed-preview shape the raw column renders in its
    // own "Raw Row" column, so a residual scan must recognize both vocabularies
    // as source-derived, not just whichever one happens to match the CSV's own
    // header text. "account" (the OCR/CSV-adjacent singular form some fixtures
    // use) is included alongside "accountId" for the same reason.
    mappedFieldKeys: ["date", "ticker", "type", "quantity", "price", "accountId", "account"],
    // NEW (Item 2) — product brand and the fixed synthetic-data compliance banner
    // (index.html's static markup, co-located with this file per CONTRACT.md's
    // load order). Not derivable from any data.js accessor (no field carries a
    // brand string) and not "individual strings copied from a screenshot" either
    // — these three are named directly, as a category, in this pass's own brief
    // ("product brand / banner text policy intentionally keeps canonical"), not
    // guessed after the fact from an observed residual. If index.html's banner
    // text or brand markup ever changes, this list and that markup must change
    // together — already true of csvColumnNames/CSV_FIXTURE.columns above.
    // Post-HG1 Checkpoint A — S1 (designer-33, 2026-09-15): the banner
    // literal below dropped "— NOT AN APPROVAL — HG1 remains
    // REVISION_REQUIRED" (both false since PD-0017; HG1 = APPROVED) — kept
    // in sync with the literal markup in index.html and the exempt sample in
    // js/i18n-selfcheck.js.
    brandAndBanner: [
      "Meridian Cross-Border", "Portfolio Intelligence",
      "SYNTHETIC DATA — HG1 DESIGN-REVIEW PROTOTYPE — NOT AN IMPLEMENTATION"
    ],
    // Pattern rules, for canonical content that cannot be enumerated because the
    // set is open-ended (a portfolio can hold any ticker; a CSV preview can
    // contain any cell value the user's own broker export happens to have).
    patterns: {
      // A ticker/instrument id in this app's own shape: 1-6 letters/digits,
      // optionally dot-suffixed with a 2-4 letter MIC-ish exchange code —
      // matches every instrumentId literal in js/data.js's HOLDINGS (AAPL,
      // VOO, MSFT, 0700.HK, 0941.HK, 300750.SZ, 601318.SS, 2800.HK) without
      // naming each one, so a NEW holding added later needs no allowlist edit.
      tickerLike: /^[A-Z0-9]{1,6}(\.[A-Z]{2,4})?$/,
      // NEW (Item 2) — this app's established shape for a canonical enum/status/
      // action CODE meant to be matched or switched on, never read as prose:
      // ALL-CAPS with at least one underscore (MISSING_FIELD,
      // AMBIGUOUS_SECURITY, POSSIBLE_DUPLICATE, UNSUPPORTED_ASSET,
      // MISSING_BENCHMARK, MISSING_COST_BASIS, MISSING_FX_HISTORY,
      // CALCULATION_ERROR, STALE_DATA, INSUFFICIENT_DATA, TRANSFER_IN,
      // TRANSFER_OUT, REDUCE_WEIGHT, ADD_HYPOTHETICAL_INSTRUMENT,
      // SHIFT_EXPOSURE). Deliberately requires an underscore (2+ words)
      // rather than matching any bare ALL-CAPS token, so it does NOT catch
      // this app's genuine, ALREADY-localized single-word UI badges —
      // ACTUAL, STAGED, COMMITTED, CONFIRMED, CORRECTED, MISSING — which
      // render through i18n keys today and would be a real defect if English
      // leaked through for them in `lang=zh`. A classifier that could not
      // tell these two apart would silently hide exactly the regression the
      // prior round's own residual scan caught (STAGED/AMBIGUOUS_SECURITY/
      // MISSING_FIELD's DISPLAY labels — "Staged for review," "Ambiguous
      // match," "Missing" — were untranslated; their underlying enum KEYS,
      // which this pattern matches, correctly never were meant to be).
      //
      // SUPERSEDED IN PART (Post-HG1 Checkpoint A — D3, 2026-09-15,
      // `designer-33`). The prior judgment named directly above this pattern
      // — that "action: REDUCE_WEIGHT" naming a scenario-construction action
      // CODE was correctly exempt because it is "read/compared, not read as
      // prose" — is corrected: Stage-0's rendered baseline showed a reader
      // literally the raw token "REDUCE_WEIGHT"/"ADD_HYPOTHETICAL_INSTRUMENT"/
      // "SHIFT_EXPOSURE" on screen, in both locales, as the ONLY thing on the
      // line naming what a scenario does — not matched/switched on
      // internally, READ, by a person, as if it were prose. `isAllowlistedCanonical`
      // below now carves these three specific values (derived LIVE from
      // APP.data.getScenarios(), never a hand list) out of this pattern's
      // exemption while every other canonicalEnumToken-shaped value (reason
      // codes, ingestion-status keys — none of which any surface renders
      // directly today) keeps the classification above unchanged. The
      // pattern itself is untouched; only the one open question it names by
      // name (REDUCE_WEIGHT) resolves the other way now that the value is
      // genuinely rendered.
      canonicalEnumToken: /^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$/
    }
  };

  // Post-HG1 Checkpoint A — D3 (designer-33). Live-derived set of this app's
  // scenario action codes (APP.data.getScenarios()'s modifications[].action)
  // — NOT a hand list, so a future scenario needs no edit here. Used only by
  // isAllowlistedCanonical's canonicalEnumToken branch, immediately below, to
  // carve these specific values out of that pattern's exemption (see the
  // "SUPERSEDED IN PART" comment above canonicalEnumToken's own definition).
  // Guarded for the case this runs before js/data.js has attached APP.data
  // (should not happen in practice given index.html's fixed load order,
  // matching this file's own established defensive pattern elsewhere) —
  // returns an empty set rather than throwing, which leaves
  // canonicalEnumToken's ordinary (exempt) behavior in effect for that edge
  // case rather than crashing the classifier.
  function liveScenarioActionValues() {
    try {
      var scenarios = (window.APP && window.APP.data && typeof window.APP.data.getScenarios === "function")
        ? window.APP.data.getScenarios() : [];
      var values = {};
      (scenarios || []).forEach(function (s) {
        (s.modifications || []).forEach(function (m) {
          if (m && typeof m.action === "string") values[m.action] = true;
        });
      });
      return values;
    } catch (e) {
      return {};
    }
  }

  // A composed "Label: value" source-row preview — js/surfaces/ingest.js's CSV
  // Raw Row / Mapped columns render exactly `k + ": " + v` for every key/value
  // pair in a fixture row (js/data.js's CSV_FIXTURE), so the SHAPE plus a known
  // field-name vocabulary (csvColumnNames OR mappedFieldKeys, both above) is
  // what marks this exempt — not memorizing every value a source file could
  // ever contain, which is impossible in principle for an open-ended upload.
  // The value may be EMPTY (a genuinely blank source cell — CSV_FIXTURE's own
  // blank Quantity row renders as "Quantity: ", i.e. "Quantity:" once trailing
  // whitespace is trimmed by a DOM scan); an empty value does not change what
  // produced the string, so both the "Label: value" and bare "Label:" shapes are
  // checked. NOTE, stated rather than silently resolved: "Quantity:" is
  // genuinely ambiguous in the abstract — the identical string could also be a
  // hand-authored UI form-field label a designer forgot to translate, and nothing
  // in the string ITSELF distinguishes the two without knowing where in the DOM
  // it came from (which this classifier, by design, never reads — see this
  // pass's own report for why that boundary is kept). This function resolves the
  // ambiguity in favor of "known source-field vocabulary wins," matching
  // PD-0015 §2.3's "translate what a human reads, never what a system joins
  // on" extended to source content — the safer default for NOT misrepresenting
  // a user's own (possibly blank) file cell as application prose.
  function isComposedSourceRowLabel(label) {
    var list = APP.i18n.CANONICAL_CONTENT_ALLOWLIST;
    return list.csvColumnNames.indexOf(label) >= 0 || list.mappedFieldKeys.indexOf(label) >= 0;
  }

  // `str` — the exact rendered text being questioned (not a substring search of
  // a longer sentence; callers should test each isolated text node/cell/column-
  // name, matching how a DOM residual scan actually walks the page). `opts.
  // sourceContent: true` marks content that is, by construction, always exempt
  // regardless of its shape — a literal CSV row-preview VALUE (e.g. a broker
  // export's own "Buy" or "AAPL" cell) has no canonical form to check against;
  // it is exempt because of WHERE it came from (the user's file), not because it
  // matches a pattern. Returns false (not exempt — a true candidate gap) for
  // anything not covered, which is the safe default: an unrecognized string is
  // reported as a gap, never silently waved through.
  APP.i18n.isAllowlistedCanonical = function isAllowlistedCanonical(str, opts) {
    opts = opts || {};
    if (str === null || str === undefined) return false;
    var s = String(str).trim();
    if (!s) return false;
    if (opts.sourceContent === true) return true;
    var list = APP.i18n.CANONICAL_CONTENT_ALLOWLIST;
    if (list.currencyCodes.indexOf(s) >= 0) return true;
    if (list.benchmarkIdentifiers.indexOf(s) >= 0) return true;
    if (list.csvColumnNames.indexOf(s) >= 0) return true;
    if (list.brandAndBanner.indexOf(s) >= 0) return true;
    if (list.patterns.tickerLike.test(s)) return true;
    if (list.patterns.canonicalEnumToken.test(s)) {
      // Post-HG1 Checkpoint A — D3: a live scenario action code is no longer
      // exempt (see liveScenarioActionValues' own comment, and the
      // "SUPERSEDED IN PART" comment above canonicalEnumToken's own
      // definition, both above) — it is now presented as a human-readable
      // bilingual label (js/surfaces/scenario.js's APP.scenarioPresentation)
      // and must never reach the DOM as the raw code. Every OTHER
      // canonicalEnumToken-shaped value (reason codes, ingestion-status
      // keys) keeps its prior classification, unchanged.
      if (Object.prototype.hasOwnProperty.call(liveScenarioActionValues(), s)) return false;
      return true;
    }
    // Composed "Label: value" / bare "Label:" source-row preview (see
    // isComposedSourceRowLabel's own comment immediately above).
    var colonIdx = s.indexOf(": ");
    if (colonIdx < 0 && s.charAt(s.length - 1) === ":") colonIdx = s.length - 1;
    if (colonIdx >= 0 && isComposedSourceRowLabel(s.slice(0, colonIdx))) return true;
    // NEW (Item 2) — canonical security name / user-entered account name, read
    // LIVE from APP.data rather than enumerated, so a fixture change needs no
    // allowlist edit (this pass's own instruction: "security names resolve from
    // the canonical holdings data already in data.js; account names from the
    // accounts collection"). Guarded for the (should-never-happen-in-practice,
    // per index.html's fixed load order) case this runs before data.js has
    // attached APP.data.
    if (APP.data) {
      if (typeof APP.data.getHoldings === "function") {
        var holdings = APP.data.getHoldings();
        for (var hIdx = 0; hIdx < holdings.length; hIdx++) {
          if (holdings[hIdx].name === s) return true;
        }
      }
      if (typeof APP.data.getAccounts === "function") {
        var accounts = APP.data.getAccounts();
        for (var aIdx = 0; aIdx < accounts.length; aIdx++) {
          if (accounts[aIdx].name === s) return true;
        }
      }
    }
    // HG1 Round 5 SECOND micro-pass (Defect 2) — composed "Name (TICKER)"
    // security identity, exactly the shape js/surfaces/overview.js's holdings
    // table renders (`h.name + " (" + h.id + ")"`, e.g. "Apple Inc. (AAPL)").
    // Both halves are ALREADY independently known-canonical elsewhere in this
    // function (the live holdings-name lookup immediately above; the
    // `tickerLike` pattern above that) — what was unhandled was the
    // COMPOSITION. Structural, not literal, per this pass's own instruction
    // ("do not add literal company-name exceptions"): parse the trailing
    // "(...)" group off the string, test the parenthesized candidate against
    // `patterns.tickerLike`, then resolve BOTH the name candidate and the
    // ticker candidate against `APP.data.getHoldings()` and require they name
    // the SAME holding record — not merely that each half independently
    // matches SOME known security. This is the clause the brief calls out by
    // name: a well-formed "Name (TICKER)" shape is not sufficient on its own.
    // Two failure modes this guards against, both real and both exercised by
    // this pass's own tests: (a) translated UI prose that happens to end in a
    // real ticker in parentheses (a benchmark citation, a cross-reference) —
    // the text before "(" will not equal any holding's canonical `name`, so
    // no match; (b) a fabricated or mismatched name paired with a real ticker
    // ("Fake Company (AAPL)") — the SAME-RECORD requirement means AAPL's own
    // canonical name ("Apple Inc.") must also match, so a real ticker paired
    // with the wrong name still returns false. Matching the visual shape alone
    // is deliberately not sufficient for either case.
    var composedMatch = /^(.+) \(([^()]+)\)$/.exec(s);
    if (composedMatch && APP.data && typeof APP.data.getHoldings === "function" &&
        list.patterns.tickerLike.test(composedMatch[2])) {
      var composedName = composedMatch[1];
      var composedCode = composedMatch[2];
      var composedHoldings = APP.data.getHoldings();
      for (var cIdx = 0; cIdx < composedHoldings.length; cIdx++) {
        if (composedHoldings[cIdx].id === composedCode && composedHoldings[cIdx].name === composedName) {
          return true;
        }
      }
    }
    return false;
  };

  // Canonical grouping — accepts `accounts` (APP.data.getAccounts()) directly. Groups
  // by the raw, canonical `type` field only; no display label, no APP.i18n call,
  // anywhere in this function's body — by construction, not merely by testing, this
  // cannot vary with the current language. Returns `{key, count}` sorted by count
  // descending, matching classifySectorExposure's own segment shape one field short
  // (accounts carry no market-value figure of their own to sum — see
  // js/surfaces/portfolio.js's separate per-account holdings/cash totals for that).
  APP.ui.classifyAccountsByType = function classifyAccountsByType(accounts) {
    accounts = accounts || [];
    var counts = {};
    accounts.forEach(function (a) {
      var key = a.type || "unknown";
      counts[key] = (counts[key] || 0) + 1;
    });
    return Object.keys(counts).map(function (key) { return { key: key, count: counts[key] }; })
      .sort(function (a, b) { return b.count - a.count; });
  };
  // The RUNTIME CHECK (mirrors verifySectorClassificationLanguageInvariant immediately
  // below, same reasoning) — compares canonical (key, count) fingerprints under "en"
  // and "zh", never the display label (expected to differ), restoring whatever
  // language was active before this check ran. Uses setLangQuiet (this file's own
  // quiet i18n setter) so a read-only diagnostic never forces a visible re-render.
  APP.ui.verifyAccountTypeLanguageInvariant = function verifyAccountTypeLanguageInvariant(accounts) {
    var originalLang = APP.i18n.getLang();
    function fingerprint(segments) { return segments.map(function (s) { return s.key + "=" + s.count; }).sort(); }
    setLangQuiet("en");
    var en = APP.ui.classifyAccountsByType(accounts);
    setLangQuiet("zh");
    var zh = APP.ui.classifyAccountsByType(accounts);
    setLangQuiet(originalLang);
    var enFp = fingerprint(en), zhFp = fingerprint(zh);
    return {
      identical: JSON.stringify(enFp) === JSON.stringify(zhFp),
      en: enFp, zh: zhFp
    };
  };

  // Static IA map. This is the navigation hypothesis this build commits to.
  // See CONTRACT.md "Navigation and IA" for the justification of every entry,
  // in particular why Portfolio hosts two registered surfaces.
  var GROUPS = [
    { key: "overview", label: "Overview", surfaces: [
      { key: "overview", label: "Overview" }
    ]},
    { key: "portfolio", label: "Portfolio", surfaces: [
      { key: "portfolio", label: "Holdings & Activity" },
      { key: "ingest", label: "Import & Ingestion" }
    ]},
    { key: "analytics", label: "Analytics", surfaces: [
      { key: "analytics", label: "Analytics" }
    ]},
    { key: "scenario", label: "Scenario Lab", surfaces: [
      { key: "scenario", label: "Scenario Lab" }
    ]}
  ];

  function findGroup(groupKey) {
    for (var i = 0; i < GROUPS.length; i++) if (GROUPS[i].key === groupKey) return GROUPS[i];
    return null;
  }

  // ---------------------------------------------------------------------
  // Registration API — the only way a surface module attaches itself.
  // ---------------------------------------------------------------------
  APP.registerSurface = function registerSurface(key, config) {
    if (!key || typeof config !== "object" || typeof config.render !== "function") {
      console.error("[shell] registerSurface(" + key + ") rejected: config.render must be a function.");
      return;
    }
    if (!findGroup(config.group)) {
      console.error("[shell] registerSurface(" + key + ") rejected: unknown group '" + config.group + "'. Must be one of overview|portfolio|analytics|scenario.");
      return;
    }
    _surfaces[key] = config;
    if (_booted) renderRoute(); // late registration still takes effect if the app already booted
  };

  APP.registerAI = function registerAI(handler) {
    if (!handler || typeof handler.renderPanel !== "function") {
      console.error("[shell] registerAI rejected: handler.renderPanel must be a function.");
      return;
    }
    _aiHandler = handler;
  };

  APP.registerEvidence = function registerEvidence(handler) {
    if (!handler || typeof handler.open !== "function") {
      console.error("[shell] registerEvidence rejected: handler.open must be a function.");
      return;
    }
    _evidenceHandler = handler;
  };

  // ---------------------------------------------------------------------
  // Router — hash-based, no history API dependency, works over file:// or http://.
  // Hash shape: #/<group>/<surfaceKey>?<params>
  // ---------------------------------------------------------------------
  function parseHash() {
    var raw = (location.hash || "").replace(/^#\/?/, "");
    var qIdx = raw.indexOf("?");
    var path = qIdx >= 0 ? raw.slice(0, qIdx) : raw;
    var query = qIdx >= 0 ? raw.slice(qIdx + 1) : "";
    var parts = path.split("/").filter(Boolean);
    var groupKey = parts[0] || "overview";
    var group = findGroup(groupKey) ? groupKey : "overview";
    var surfaceKey = parts[1] || (findGroup(group).surfaces[0] || {}).key;
    var params = {};
    query.split("&").filter(Boolean).forEach(function (pair) {
      var kv = pair.split("=");
      params[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || "");
    });
    return { group: group, key: surfaceKey, params: params };
  }

  APP.navigateTo = function navigateTo(hashPath) {
    var clean = String(hashPath || "").replace(/^#\/?/, "");
    location.hash = "#/" + clean;
  };

  // ---------------------------------------------------------------------
  // "Not yet built" placeholder — the structural tolerance this file must guarantee.
  // ---------------------------------------------------------------------
  function notBuilt(container, info) {
    info = info || {};
    container.innerHTML = "";
    var el = document.createElement("div");
    el.className = "not-built-panel";
    el.innerHTML =
      '<div class="not-built-badge">NOT YET BUILT</div>' +
      "<h3>" + escapeHTML(info.label || "This surface") + "</h3>" +
      "<p>" + escapeHTML(info.detail ||
        "This module has not registered with the app shell yet. It is owned by a " +
        "phase-2 designer and will appear here once " + (info.owner || "its owner") +
        " completes it.") + "</p>";
    container.appendChild(el);
  }
  APP.ui.notBuilt = notBuilt;

  // ---------------------------------------------------------------------
  // Rendering the current route into #app-content, with secondary nav
  // for groups that host more than one registered surface (Portfolio).
  // ---------------------------------------------------------------------
  var _lastRouteSignature = null;
  function renderRoute() {
    var route = parseHash();
    var group = findGroup(route.group) || GROUPS[0];

    // HG1 ux_planning revision (review-06, B6, fix 3) — deterministic route-change
    // reset. Compares the (group, surface) the user is actually navigating TO against
    // the last one rendered; only an ACTUAL route change clears the inspector dock —
    // a same-route re-render (triggered by APP.i18n.setLang / APP.state.
    // setExplanationMode / the color-convention control, all of which call this same
    // renderRoute()) leaves whatever the current surface has open untouched, matching
    // this build's existing behavior for every one of those three controls. See
    // APP.ui.inspector's own comment (above, this file) for the full account.
    var routeSignature = route.group + "/" + route.key;
    if (_lastRouteSignature !== null && _lastRouteSignature !== routeSignature) {
      APP.ui.inspector.clear();
    }
    _lastRouteSignature = routeSignature;

    renderPrimaryNav(route);
    renderSecondaryNav(group, route);

    var content = document.getElementById("app-content");
    content.innerHTML = "";
    var mount = document.createElement("div");
    mount.className = "surface-mount";
    mount.id = "surface-mount";
    content.appendChild(mount);

    var expected = null;
    for (var i = 0; i < group.surfaces.length; i++) {
      if (group.surfaces[i].key === route.key) { expected = group.surfaces[i]; break; }
    }
    if (!expected) expected = group.surfaces[0];

    var registered = _surfaces[expected.key];
    if (!registered) {
      notBuilt(mount, {
        label: expected.label,
        owner: ownerForSurface(expected.key),
        detail: "Route #/" + group.key + "/" + expected.key + " is reserved for this surface. " +
          "The app shell (index.html, shell.js) is fully wired for it; only the surface module itself is missing."
      });
      return;
    }
    try {
      registered.render(mount, buildCtx(group.key, expected.key, route.params));
    } catch (err) {
      console.error("[shell] surface '" + expected.key + "' threw during render:", err);
      mount.innerHTML = "";
      var errEl = document.createElement("div");
      errEl.className = "not-built-panel surface-error";
      errEl.innerHTML = '<div class="not-built-badge" style="background:var(--color-danger)">RENDER ERROR</div>' +
        "<h3>" + escapeHTML(expected.label) + " failed to render</h3>" +
        "<p>" + escapeHTML(String(err && err.message || err)) + "</p>";
      mount.appendChild(errEl);
    }
  }

  function ownerForSurface(key) {
    var map = {
      overview: "designer-10", portfolio: "designer-11", ingest: "designer-11",
      analytics: "designer-12", scenario: "designer-13"
    };
    return map[key] || "a phase-2 designer";
  }

  function renderPrimaryNav(route) {
    var nav = document.getElementById("app-nav");
    nav.innerHTML = "";
    GROUPS.forEach(function (g) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "nav-tab" + (g.key === route.group ? " nav-tab-active" : "");
      // i18n: nav labels are looked up live from APP.i18n.t (never the static
      // GROUPS.label) so a language switch re-renders every nav label immediately.
      btn.textContent = APP.i18n.t("nav." + g.key);
      btn.setAttribute("aria-current", g.key === route.group ? "page" : "false");
      btn.addEventListener("click", function () {
        APP.navigateTo(g.key + "/" + g.surfaces[0].key);
      });
      nav.appendChild(btn);
    });
  }

  function renderSecondaryNav(group, route) {
    var subnav = document.getElementById("app-subnav");
    subnav.innerHTML = "";
    if (group.surfaces.length < 2) { subnav.hidden = true; return; }
    subnav.hidden = false;
    group.surfaces.forEach(function (s) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "subnav-tab" + (s.key === route.key ? " subnav-tab-active" : "");
      btn.textContent = APP.i18n.t("subnav." + s.key);
      btn.addEventListener("click", function () {
        APP.navigateTo(group.key + "/" + s.key);
      });
      subnav.appendChild(btn);
    });
  }

  function buildCtx(group, key, params) {
    return {
      group: group,
      key: key,
      params: params || {},
      navigateTo: APP.navigateTo,
      data: APP.data,
      charts: APP.charts,
      ui: APP.ui
    };
  }

  // =======================================================================
  // HG1 Round 5 correction pass — APP.uicheck (Objective 1's acceptance check).
  //
  // Deliberately a SEPARATE namespace from APP.selfcheck (js/selfcheck.js), not an
  // extension of it. That boundary is intentional and documented at length in this
  // project's own record (reviews/gates/HG1_ROUND5_PHASE2_VERIFICATION.md §7,
  // reviews/gates/HG1_ROUND5_UX_AUDIT.md finding V3): `selfcheck` reads only
  // `window.APP.data` and never touches the DOM, and folding a DOM assertion into it
  // would make its "33/33" citable as visual coverage — exactly the confusion V3
  // warns is a documented past failure mode of this project. `APP.uicheck` has its
  // own `run()`, its own mutation-style `selfTest()`, and its own count, and neither
  // file references the other's internals.
  //
  // WHAT THIS CHECKS, AND WHY (Objective 1's measured defect): at DEFAULT render —
  // no forced-open disclosures, no clicked inspector — Simple and Professional were
  // byte-identical on #/overview (scrollHeight 3684/3684, visible text 5014/5014;
  // HG1_ROUND5_PHASE2_VERIFICATION.md §4.1). This assertion renders each REGISTERED
  // surface twice, off-screen, once at each of Simple and Professional, and requires
  // that Professional's set of VISIBLE module identities be a strict superset of
  // Simple's, and that Professional's visible text exceed Simple's by a meaningful
  // margin. It is the mechanical version of the owner's own sentence, verbatim:
  // "Clicking on simple and professional makes no difference."
  //
  // "Visible" is deliberately NOT `.textContent`/a bare DOM query: `.textContent`
  // reads every descendant text node regardless of whether a `<details>` ancestor is
  // open, so it would silently pass even if every disclosure were permanently
  // closed — exactly the defect this check exists to catch. `.innerText` is used
  // instead (layout-aware; a closed `<details>`'s non-`<summary>` children compute to
  // no rendered text), and module-identity visibility is computed by walking each
  // `[data-module-id]` element's own ancestor chain for a closed `<details>`, not by
  // trusting a single element's own `.open` in isolation (a module can be tagged
  // open while a PARENT module-gate is itself still collapsed).
  //
  // HG1 Round 5, Phase 2 CORRECTION pass — `#/analytics` reported `pass:false` on
  // this exact check (7 modules both Simple and Professional, 0 chars growth;
  // reviews/gates/HG1_ROUND5_PHASE2_CORRECTION_VERIFICATION.md §1). This is fixed
  // in js/surfaces/analytics.js (`appendProfessionalDepthModule`, four call sites)
  // and Analytics is now also listed in `UICHECK_REQUIRED_SURFACES` below, so this
  // check no longer tolerates a `pass:false` there as a passively-reported gap the
  // way it must for the three surfaces that genuinely have no mode-varying inline
  // content (`#/portfolio`, `#/ingest`, `#/scenario` — `noInlineContent:true`,
  // honestly still `pass:false` and NOT required, because forcing that to "pass"
  // would mean fabricating differentiation that does not exist).
  // =======================================================================
  APP.uicheck = APP.uicheck || {};

  function uicheckGroupKeyForSurface(surfaceKey) {
    for (var i = 0; i < GROUPS.length; i++) {
      for (var j = 0; j < GROUPS[i].surfaces.length; j++) {
        if (GROUPS[i].surfaces[j].key === surfaceKey) return GROUPS[i].key;
      }
    }
    return surfaceKey;
  }

  // Walks from `el` up to (but not past) `root`; visible iff no `<details>` in that
  // chain (INCLUDING `el` itself) is closed. This is what makes the check correct
  // for a module nested inside another module-gate, not just a top-level one.
  function uicheckIsVisible(el, root) {
    var node = el;
    while (node && node !== root) {
      if (node.tagName === "DETAILS" && !node.open) return false;
      node = node.parentElement;
    }
    return true;
  }

  function uicheckVisibleModuleIds(container) {
    var ids = [];
    var nodes = container.querySelectorAll("[data-module-id]");
    for (var i = 0; i < nodes.length; i++) {
      if (uicheckIsVisible(nodes[i], container)) ids.push(nodes[i].getAttribute("data-module-id"));
    }
    return ids.sort();
  }

  // Renders one registered surface's DEFAULT output (no route navigation, no visible
  // flicker — the live page's own hash/mode/mount are never touched) at a given
  // explanation mode, attached off-screen (`position:absolute; left:-99999px`, NOT
  // `visibility:hidden`/`display:none` — either of those would zero out `.innerText`,
  // which is the whole point of using it over `.textContent`). Caller is responsible
  // for removing the returned element from `document.body` once measured.
  function uicheckRenderOffscreen(surfaceKey, mode) {
    var registered = _surfaces[surfaceKey];
    if (!registered) return null;
    var savedMode = APP.state.getExplanationMode();
    APP.state.setExplanationModeQuiet(mode);
    var container = document.createElement("div");
    container.className = "uicheck-offscreen-mount";
    container.style.position = "absolute";
    container.style.left = "-99999px";
    container.style.top = "0px";
    container.style.width = "1512px"; // the owner's measured display (§ Phase 1/2 evidence)
    document.body.appendChild(container);
    try {
      registered.render(container, buildCtx(uicheckGroupKeyForSurface(surfaceKey), surfaceKey, {}));
    } catch (err) {
      console.error("[uicheck] surface '" + surfaceKey + "' threw while rendering at mode '" + mode + "':", err);
    } finally {
      APP.state.setExplanationModeQuiet(savedMode);
    }
    return container;
  }

  // HG1 ux_planning revision (review-07, P0 item 1 regression requirement) — exposes
  // the EXACT function above (no new rendering logic) so js/selfcheck.js can render a
  // real registered surface (analytics/overview/portfolio) off-screen and read back
  // what it ACTUALLY produces, the same technique chart.renderedReturnReconciles-
  // WithEngine already uses for a chart. Needed because holdingDisplayName.zh.
  // consistentAcrossSurfaces (below) checked APP.ui.holdingDisplayName() in isolation —
  // correct, but blind to a call site that bypasses the helper entirely (analytics.js's
  // concentration bar did, for every round this defect survived) — and selfcheck.js has
  // no other route to a real surface's rendered DOM. Caller owns removing the returned
  // element, exactly like uicheckRenderOffscreen's own existing callers.
  APP.uicheck.renderSurfaceOffscreen = uicheckRenderOffscreen;

  // A meaningful margin, not a token one — chosen so a single short qualifier string
  // (e.g. one `qualifierShort`, ~45 chars) could not alone satisfy it, while the
  // actual fix (beta's investorDetail 159 + professionalDetail 310 chars, this file's
  // own measured accounting) clears it by more than 10x.
  var UICHECK_MIN_TEXT_GROWTH_CHARS = 80;

  // HG1 Round 5, Phase 2 correction pass — Blocker 1's own instruction: "Analytics
  // is also REQUIRED to demonstrate a real default-visible Simple->Professional
  // difference — it must not stay a tolerated pass:false." Before this pass, every
  // surface's `pass:false` was reported with equal weight, which is how Analytics'
  // defect stayed live through a whole review round: `#/portfolio`, `#/ingest`, and
  // `#/scenario` genuinely have no mode-varying inline content today (verified,
  // `noInlineContent:true` — see uicheckMeasureSurface below) and their `pass:false`
  // is the HONEST, correct report for that state, not a defect. `#/overview` and
  // `#/analytics` are different in kind: PD-0012 §2 names Analytics as the surface
  // where "how it was measured; assumptions; benchmark; methodology; decomposition;
  // evidence" (Professional's own job) actually lives, so a `pass:false` there is a
  // real, currently-shipping defect, not an absence-of-applicability. Listing a
  // surface here does not change how `pass` is computed for it (same isStrictSuperset
  // + growthOk test as every other surface) — it only changes whether a `false`
  // result may be waved through as "not applicable" versus must be read as a defect
  // blocking Objective 1. `#/portfolio` / `#/ingest` / `#/scenario` are deliberately
  // NOT listed: forcing them to "pass" would mean inventing mode-varying inline
  // content they do not have, which is exactly the kind of check-shaped-to-fit-the-
  // code this project's own discipline (PD-0014 §2.5) forbids.
  var UICHECK_REQUIRED_SURFACES = ["overview", "analytics"];

  function uicheckMeasureSurface(surfaceKey) {
    var simpleEl = uicheckRenderOffscreen(surfaceKey, "simple");
    var proEl = uicheckRenderOffscreen(surfaceKey, "professional");
    if (!simpleEl || !proEl) {
      if (simpleEl) document.body.removeChild(simpleEl);
      if (proEl) document.body.removeChild(proEl);
      return { surface: surfaceKey, skipped: true, reason: "surface not registered" };
    }
    var simpleModules = uicheckVisibleModuleIds(simpleEl);
    var proModules = uicheckVisibleModuleIds(proEl);
    var simpleText = (simpleEl.innerText || simpleEl.textContent || "").trim();
    var proText = (proEl.innerText || proEl.textContent || "").trim();
    document.body.removeChild(simpleEl);
    document.body.removeChild(proEl);

    var addedModules = proModules.filter(function (id) { return simpleModules.indexOf(id) < 0; });
    var missingFromPro = simpleModules.filter(function (id) { return proModules.indexOf(id) < 0; });
    var isStrictSuperset = missingFromPro.length === 0 && addedModules.length > 0;
    var growthChars = proText.length - simpleText.length;
    var growthOk = growthChars >= UICHECK_MIN_TEXT_GROWTH_CHARS;

    // A surface with NO `[data-module-id]` content at all and NO text growth is not
    // "broken" by this assertion's own definition — it has no inline explanation-mode
    // ladder content to differentiate in the first place (e.g. a surface whose only
    // depth ladder lives inside a click-required inspector/expander, unchanged by
    // this pass — see this designer's report for exactly which surfaces this is true
    // of today, and why). Recorded as `noInlineContent`, distinctly from `pass`, so
    // it is never silently folded into either a pass or a fail.
    var noInlineContent = simpleModules.length === 0 && proModules.length === 0 && growthChars === 0;

    return {
      surface: surfaceKey,
      pass: isStrictSuperset && growthOk,
      required: UICHECK_REQUIRED_SURFACES.indexOf(surfaceKey) >= 0,
      noInlineContent: noInlineContent,
      simpleModuleCount: simpleModules.length,
      professionalModuleCount: proModules.length,
      addedModules: addedModules,
      missingFromProfessional: missingFromPro,
      simpleTextLength: simpleText.length,
      professionalTextLength: proText.length,
      growthChars: growthChars
    };
  }

  APP.uicheck.run = function run() {
    var savedMode = APP.state.getExplanationMode();
    var results = Object.keys(_surfaces).map(uicheckMeasureSurface);
    APP.state.setExplanationModeQuiet(savedMode);
    var checked = results.filter(function (r) { return !r.skipped; });
    var passCount = checked.filter(function (r) { return r.pass; }).length;
    // HG1 Round 5, Phase 2 correction pass — `requiredResults`/`allRequiredPass` is
    // the OPERATIVE acceptance signal for Objective 1: it is true only when every
    // surface actually required to differentiate (today: overview, analytics) does
    // so. `allPass` is kept, unchanged in meaning, as the raw across-every-registered-
    // surface count — it will almost never be true while portfolio/ingest/scenario
    // remain honestly `noInlineContent:true`, and that is not a target to chase (see
    // UICHECK_REQUIRED_SURFACES's own comment).
    var requiredResults = checked.filter(function (r) { return r.required; });
    var requiredPassCount = requiredResults.filter(function (r) { return r.pass; }).length;
    return {
      total: checked.length,
      passCount: passCount,
      allPass: checked.length > 0 && passCount === checked.length,
      requiredTotal: requiredResults.length,
      requiredPassCount: requiredPassCount,
      allRequiredPass: requiredResults.length > 0 && requiredPassCount === requiredResults.length,
      results: results
    };
  };

  function uicheckFindResult(runResult, surfaceKey) {
    for (var i = 0; i < runResult.results.length; i++) {
      if (runResult.results[i].surface === surfaceKey) return runResult.results[i];
    }
    return null;
  }

  // Mutation-style self-test (the discipline this project has used since Round 4,
  // applied here to a DOM assertion for the first time): injects the EXACT defect
  // this check exists to catch, confirms `run()` now reports `pass:false` for
  // `#/overview`, then restores and confirms it reports `pass:true` again.
  //
  // The injection point is `APP.ui.explanationModeAtLeast` — the function
  // overview.js's two Objective-1 disclosure sites call directly (via `ctx.ui`, i.e.
  // this exact property) to decide whether Professional-only content should be open
  // by default. Forcing it to always answer "no" for "professional" reproduces the
  // original bug precisely: `openDefault` never becomes true regardless of the
  // actual mode, which is exactly what shipped before this pass's fix
  // (js/surfaces/overview.js's own `disclosure()` never received a mode-aware
  // `openDefault` at all).
  //
  // CORRECTION (HG1 Round 5, Phase 2 correction pass): this comment previously
  // claimed `ui.renderModule`'s own minMode gate also reads `APP.ui.
  // explanationModeAtLeast`. That was wrong — `renderModule`'s gate (below,
  // `if (APP.state.explanationModeAtLeast(minMode))`) reads the `APP.state` copy,
  // a DIFFERENT property from `APP.ui.explanationModeAtLeast`, even though both
  // start out pointing at the same function (`APP.ui.explanationModeAtLeast =
  // APP.state.explanationModeAtLeast`, assigned once near the top of this file —
  // reassigning one property afterward does not touch the other). This distinction
  // is why Analytics needs its OWN, separate injection below: Analytics'
  // Blocker-1 fix (js/surfaces/analytics.js's appendProfessionalDepthModule) adds
  // no hand-built disclosure of its own — it uses `ctx.ui.renderModule({minMode:
  // "professional", ...})` exclusively, so it is governed by `APP.state.
  // explanationModeAtLeast`, not by the property this first injection patches.
  // Patching only `APP.ui.explanationModeAtLeast` would leave Analytics' gate
  // completely untouched and prove nothing about it — which is exactly why a
  // second, independent injection follows rather than folding Analytics into
  // this one.
  function uicheckSelfTestOverview() {
    var before = APP.uicheck.run();
    var overviewBefore = uicheckFindResult(before, "overview");

    var original = APP.ui.explanationModeAtLeast;
    APP.ui.explanationModeAtLeast = function (mode) {
      if (mode === "professional") return false;
      return original(mode);
    };
    var during = APP.uicheck.run();
    var overviewDuring = uicheckFindResult(during, "overview");
    APP.ui.explanationModeAtLeast = original;

    var after = APP.uicheck.run();
    var overviewAfter = uicheckFindResult(after, "overview");

    var provenToFail = !!overviewBefore && overviewBefore.pass === true &&
      !!overviewDuring && overviewDuring.pass === false &&
      !!overviewAfter && overviewAfter.pass === true;

    return { provenToFail: provenToFail, beforeInjection: overviewBefore, duringInjection: overviewDuring, afterRestore: overviewAfter };
  }

  // HG1 Round 5, Phase 2 correction pass — Blocker 1's own instruction: "prove the
  // updated check fails under deliberate regression injection... extend that
  // discipline to the Analytics case." The injection point here is `APP.state.
  // explanationModeAtLeast` — the actual function `ctx.ui.renderModule`'s minMode
  // gate reads (see the corrected comment above) and therefore the one every
  // `minMode:"professional"` gate on Analytics (this pass's own fix) depends on.
  // Reassigning it to make `explanationModeAtLeast("professional")` return exactly
  // what `explanationModeAtLeast("simple")` would have returned reproduces the
  // ORIGINAL defect precisely and generally, not just for this pass's specific new
  // modules: it collapses the "professional" threshold onto the "simple" one, i.e.
  // "Analytics' renderModule gates all share one minMode:'simple' threshold" —
  // reviews/gates/HG1_ROUND5_PHASE2_CORRECTION_VERIFICATION.md §1's own diagnosis —
  // restated as code, so every `minMode:"professional"` module opens at Simple too
  // and the Simple/Professional module sets collapse back to identical. Captures
  // `originalState` (the pre-patch function) once and calls THAT inside the patch,
  // never the live `APP.state.explanationModeAtLeast` property, so the patch does
  // not recurse into itself.
  function uicheckSelfTestAnalytics() {
    var before = APP.uicheck.run();
    var analyticsBefore = uicheckFindResult(before, "analytics");

    var originalState = APP.state.explanationModeAtLeast;
    APP.state.explanationModeAtLeast = function (mode) {
      if (mode === "professional") return originalState("simple");
      return originalState(mode);
    };
    var during = APP.uicheck.run();
    var analyticsDuring = uicheckFindResult(during, "analytics");
    APP.state.explanationModeAtLeast = originalState;

    var after = APP.uicheck.run();
    var analyticsAfter = uicheckFindResult(after, "analytics");

    var provenToFail = !!analyticsBefore && analyticsBefore.pass === true &&
      !!analyticsDuring && analyticsDuring.pass === false &&
      !!analyticsAfter && analyticsAfter.pass === true;

    return { provenToFail: provenToFail, beforeInjection: analyticsBefore, duringInjection: analyticsDuring, afterRestore: analyticsAfter };
  }

  APP.uicheck.selfTest = function selfTest() {
    var overview = uicheckSelfTestOverview();
    var analytics = uicheckSelfTestAnalytics();
    return {
      // Overall signal: both required surfaces' checks must be independently
      // proven to fail under their OWN mechanism's regression — neither
      // injection substitutes for the other (see the two functions' own
      // comments for why they must be separate).
      provenToFail: overview.provenToFail && analytics.provenToFail,
      overview: overview,
      analytics: analytics,
      // Back-compat shape for anything reading the pre-Phase-2-correction
      // return value directly (this file's own only caller today is manual
      // console verification, per this pass's report) — the overview result
      // at the top level, unchanged from before this pass.
      beforeInjection: overview.beforeInjection,
      duringInjection: overview.duringInjection,
      afterRestore: overview.afterRestore
    };
  };

  // ---------------------------------------------------------------------
  // Metric-state renderer (D3.2) — THE single source of truth.
  // No surface may hand-roll AVAILABLE/LIMITED/INSUFFICIENT_DATA rendering.
  // ---------------------------------------------------------------------
  function renderMetricValue(container, claim) {
    container.innerHTML = "";
    if (!claim) {
      // Not the same condition as a computed claim's own INSUFFICIENT_DATA state (no
      // claim object was even supplied to render) — kept structurally distinct from
      // that vocabulary (own wording, own class), and specifically NOT an em-dash: the
      // em-dash-as-placeholder mistake (finding P-1) recurred once already; this branch
      // is defensive/rarely exercised in practice (every real caller checks the claim
      // exists first, per CONTRACT.md's pattern), but "rarely executed" is exactly how
      // the second occurrence hid, so it is fixed here too rather than left as a latent
      // third copy of the same bug.
      var missingWrap = document.createElement("span");
      missingWrap.className = "metric-unit metric-missing";
      var missingLabel = document.createElement("span");
      missingLabel.className = "metric-insufficient-label";
      missingLabel.textContent = APP.i18n.t("common.notAvailable");
      missingWrap.appendChild(missingLabel);
      container.appendChild(missingWrap);
      return;
    }
    var wrap = document.createElement("span");
    wrap.className = "metric-unit metric-state-" + (claim.sufficiency || "AVAILABLE").toLowerCase();

    if (claim.sufficiency === "INSUFFICIENT_DATA") {
      // Rule (D3.2, row 4): no numeric glyph of any kind. Distinct component, not a
      // number-shaped field with substituted text. No em-dash used as a placeholder.
      wrap.classList.add("metric-insufficient");
      var label = document.createElement("span");
      label.className = "metric-insufficient-label";
      label.textContent = APP.i18n.t("common.insufficientData");
      wrap.appendChild(label);
      if (claim.reasonCode || claim.caveat) {
        var reason = document.createElement("span");
        reason.className = "metric-reason";
        // HG1 Round 5 micro-pass (Item 3) — BUG FIX. This read `claim.caveat`
        // directly, bypassing `APP.ui.localizeClaimField` entirely, so a claim
        // that HAD a correct `i18n.zh.caveat` (e.g. metric.sortino's own, already
        // present in js/data.js) still rendered the raw English caveat at this
        // exact compact rendering unit in `lang=zh` — the only render path
        // `renderMetricValue` uses for an INSUFFICIENT_DATA claim's inline
        // reason. `appendCaveatSlot` (this file, the full-card caveat slot) was
        // never affected; only this compact unit was. Confirmed against three
        // real claims this compact path renders: metric.sortino (Overview/
        // Analytics), holding.2800.HK.riskMetrics (Overview/Analytics/
        // Portfolio), and transaction.tx-0029.fxConversion (Portfolio).
        reason.textContent = APP.ui.localizeClaimField(claim, "caveat") || reasonCodeText(claim.reasonCode);
        wrap.appendChild(reason);
      }
      container.appendChild(wrap);
      return;
    }

    // AVAILABLE and LIMITED both render a real numeral.
    var valueEl = document.createElement("span");
    valueEl.className = "metric-number";
    valueEl.textContent = formatClaimValue(claim);

    // HG1 Condition 2 — genuinely directional financial results get real green/red,
    // reserved deliberately (see tokens.css/app.css comments): only when js/data.js has
    // marked the claim `directional: true` (a small, explicit list — portfolio return,
    // P&L, benchmark-relative performance, FX attribution, alpha, per-holding unrealized
    // gain/loss) AND sufficiency is plain AVAILABLE (LIMITED keeps its own amber
    // treatment undiluted; INSUFFICIENT_DATA already returned above). Color is never the
    // only signal: the numeral's own formatted sign ("+"/"-", from formatPercent/
    // formatCurrency) already carries the same information, and a small arrow glyph
    // (aria-hidden — redundant with the sign a screen reader already announces) repeats
    // it once more for a reader who cannot distinguish the color at a glance.
    var directionGlyph = null;
    if (claim.directional && claim.sufficiency === "AVAILABLE" &&
        typeof claim.value === "number" && claim.value !== 0) {
      var positive = claim.value > 0;
      valueEl.classList.add(positive ? "metric-positive" : "metric-negative");
      directionGlyph = document.createElement("span");
      directionGlyph.className = "metric-direction-glyph " + (positive ? "metric-positive" : "metric-negative");
      directionGlyph.setAttribute("aria-hidden", "true");
      directionGlyph.textContent = positive ? "▲" : "▼";
    }
    if (directionGlyph) wrap.appendChild(directionGlyph);
    wrap.appendChild(valueEl);

    if (claim.sufficiency === "LIMITED") {
      // Rule (D3.2, row 3): mandatory, non-dismissible qualifier in the SAME visual unit.
      // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.1(b)/F4). Renders
      // `qualifierShort` — an ADDED field, never `claim.caveat` itself (the caveat can
      // run to ~430 characters; rendering it in this inline pill is the mechanical
      // cause of Problems 7/8 the audit traced to this exact line). `claim.caveat`
      // stays fully intact for the Proof Packet (registerEvidenceFor, js/data.js) and
      // for `caveatFull`'s block-slot rendering at Simple/Professional
      // (appendCaveatSlot, below) — this line never reads it as a fallback, so a claim
      // that is LIMITED but has not yet been given a qualifierShort fails SHORT (the
      // bounded common.limited token) rather than reintroducing the unbounded-pill
      // defect by accident.
      var q = document.createElement("span");
      q.className = "metric-qualifier";
      var qShort = APP.ui.localizeClaimField(claim, "qualifierShort");
      q.textContent = qShort || reasonCodeText(claim.reasonCode) || APP.i18n.t("common.limited");
      wrap.appendChild(q);
    } else if (claim.reasonCode === "STALE_DATA" && claim.freshness) {
      // Rule (D3.2, row 2): identical numeral to plain AVAILABLE, PLUS a D5 freshness
      // indicator at this rendering unit — never a D3-style qualifier, never absent.
      wrap.appendChild(renderFreshnessPillEl(claim.freshness));
    }
    // Plain AVAILABLE (no reason code): no extra badge at this rendering unit by design —
    // see CONTRACT.md's note on why this is not the same thing as "no freshness disclosure
    // anywhere" (D5.2's surface-level freshness strip/column still applies independently).

    // HG1 round-4 fix (PD-0014 Part 1 §1.2 point 2; flagged directly by js/data.js's own
    // comment on `metric.benchmarkRelative.freshness.comparability`, confirmed missing by
    // `quant_analyst`'s review). Comparability is a DISCLOSURE DIMENSION independent of
    // both freshness (above) and sufficiency (LIMITED/INSUFFICIENT_DATA) — a claim can be
    // plain AVAILABLE, carry no STALE_DATA reason code at all (this is exactly
    // benchmarkRelative's case: the CN axis is routinely END_OF_DAY, not stale), and
    // still combine two legs measured at different effective instants. It therefore
    // cannot live inside the `if/else if` above (which is sufficiency/staleness-gated) —
    // it is checked separately, and can coexist with any of the three branches above.
    // Distinct from the freshness pill on purpose: a freshness pill names a STATE (Live/
    // Delayed/EOD/Stale) of a single axis; this flag names a COMPARABILITY LIMITATION
    // between two legs, which is a different assertion even when both happen to render
    // near the same value. Before this fix the only rendering path was `claim.caveat`
    // inside the full ladder (`renderClaim`) — never at the compact `renderMetricValue`
    // unit a table cell or metric-strip stat uses, and never with its own visual
    // vocabulary distinct from a plain caveat sentence.
    if (claim.freshness && claim.freshness.comparability && claim.freshness.comparability.limited) {
      wrap.appendChild(renderComparabilityFlagEl(claim.freshness.comparability, claim.id));
    }

    container.appendChild(wrap);
  }
  APP.ui.renderMetricValue = renderMetricValue;

  // HG1 Round 5 micro-pass (Item 3) — this fallback fires whenever an
  // INSUFFICIENT_DATA/LIMITED claim has a `reasonCode` but no `qualifierShort`/
  // `caveat` of its own, at the SAME compact rendering unit the fix immediately
  // above corrects — so an untranslated raw English phrase here was a genuine,
  // silent UI gap in `lang=zh` regardless of that fix. Routed through
  // APP.i18n.t() like every other piece of UI chrome in this file; `code` itself
  // (the map KEY) is untouched and stays the canonical enum value everywhere else
  // in this app reads it (matches this pass's own
  // `canonicalEnumToken` classifier rule — see APP.i18n.CANONICAL_CONTENT_
  // ALLOWLIST above).
  function reasonCodeText(code) {
    var keys = {
      UNSUPPORTED_ASSET: "reasonCode.UNSUPPORTED_ASSET",
      MISSING_BENCHMARK: "reasonCode.MISSING_BENCHMARK",
      MISSING_COST_BASIS: "reasonCode.MISSING_COST_BASIS",
      MISSING_FX_HISTORY: "reasonCode.MISSING_FX_HISTORY",
      CALCULATION_ERROR: "reasonCode.CALCULATION_ERROR",
      STALE_DATA: "reasonCode.STALE_DATA"
    };
    return code ? (keys[code] ? APP.i18n.t(keys[code]) : code) : "";
  }

  function formatClaimValue(claim) {
    if (claim.formatted) return APP.ui.localizeClaimField(claim, "formatted");
    if (claim.value === null || claim.value === undefined) return "—";
    // `signed` is forwarded through formatNumber to BOTH the currency- and percent-unit
    // cases (HG1 round-4 fix — percent no longer always signs itself; see
    // APP.ui.formatPercent's own comment). Only a claim js/data.js has explicitly marked
    // `directional: true` requests the leading "+", so an ordinary level (Total
    // Portfolio Value, a holding's price, market value, portfolio weight, volatility)
    // never grows an unexpected leading "+".
    return APP.ui.formatNumber(claim.value, { unit: claim.unit, signed: !!claim.directional });
  }

  // ---------------------------------------------------------------------
  // Formatting helpers — shared so four authors don't invent four number formats.
  // ---------------------------------------------------------------------
  APP.ui.formatCurrency = function formatCurrency(value, currency, opts) {
    currency = currency || "USD";
    opts = opts || {};
    if (value === null || value === undefined) return "—";
    // opts.signed: HG1 Condition 2's "signs... alongside color on directional values" —
    // a plain currency magnitude never gets a leading "+"; only a caller that explicitly
    // asks (directional claims, via formatClaimValue above) does.
    var sign = value < 0 ? "-" : (opts.signed && value > 0 ? "+" : "");
    var abs = Math.abs(value);
    return sign + (currency === "USD" ? "$" : currency + " ") +
      abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };
  // HG1 round-4 fix (feedback log §6.3 / PD confirmed defect): a static LEVEL (portfolio
  // weight, sector/exposure share, top-5 concentration, a risk statistic expressed as a
  // percent) must render "19.2%", not "+19.2%". A leading "+" is reserved for a CHANGE —
  // gains/losses, returns, alpha, a weight CHANGE, a signed contribution, a scenario
  // delta. Previously this function always prefixed "+" for any positive value with no
  // way to suppress it, and `formatNumber`'s "percent" branch below did not forward its
  // own `signed` option at all — so EVERY percent render in the app (directional or not)
  // got an unconditional leading "+", which is the confirmed root cause of the defect (see
  // reviews/gates/HG1_ROUND4_VERIFICATION.md §4). `signed` now defaults to `false` — a
  // level, by default, is not signed. A caller that IS rendering a genuine change passes
  // `{ signed: true }` explicitly (formatClaimValue below already does this correctly,
  // gated on `claim.directional`, for every claim-shaped render — this fix only had to
  // remove the override that made that gating ineffective). The literal "-" for a genuinely
  // negative value is NEVER suppressed by this flag — only the "+" is conditional; a
  // negative number reads as negative regardless of whether it represents a level or a
  // change (e.g. a level cannot normally be negative, but Max Drawdown magnitude and an
  // unrealized-loss level both still need their minus sign).
  APP.ui.formatPercent = function formatPercent(value, digits, opts) {
    if (value === null || value === undefined) return "—";
    opts = opts || {};
    digits = digits === undefined ? 1 : digits;
    var signed = opts.signed === true;
    var sign = value > 0 ? (signed ? "+" : "") : "";
    return sign + (value * 100).toFixed(digits) + "%";
  };
  APP.ui.formatNumber = function formatNumber(value, opts) {
    opts = opts || {};
    if (value === null || value === undefined) return "—";
    switch (opts.unit) {
      case "currency": return APP.ui.formatCurrency(value, opts.currency, { signed: opts.signed });
      case "percent": return APP.ui.formatPercent(value, opts.digits, { signed: opts.signed });
      case "ratio": return value.toFixed(opts.digits === undefined ? 2 : opts.digits);
      case "bps": return Math.round(value * 10000) + " bps";
      default: return String(Math.round(value * 100) / 100);
    }
  };

  // HG1 Condition 3 — "country, currency, sector and asset-class charts should use
  // consistent horizontal-bar conventions." Before this pass, Overview's exposure bars
  // showed a dollar figure (via APP.charts.bar's valueFormat) while Analytics' own
  // exposure bars showed a percent-of-portfolio figure for what is the SAME underlying
  // getExposure() segment shape — two different conventions for the same chart type
  // across the two surfaces that use it. One shared formatter, added here so both
  // surfaces read from a single definition rather than two that could drift apart again:
  // percent-of-portfolio first (comparable at a glance across dimensions of different
  // total size), the dollar amount second, for the reader who wants the underlying
  // magnitude. Pass a getExposure()/getConcentration() segment object directly.
  APP.ui.formatExposureSegment = function formatExposureSegment(seg) {
    if (!seg) return "—";
    var pctText = seg.pct !== undefined && seg.pct !== null ? APP.ui.formatPercent(seg.pct, 1) : null;
    var valText = seg.value !== undefined && seg.value !== null ? APP.ui.formatCurrency(seg.value) : null;
    if (pctText && valText) return pctText + " · " + valText;
    return pctText || valText || "—";
  };

  // ---------------------------------------------------------------------
  // Sector-classification presentation fix (feedback log §6.2, confirmed in
  // reviews/gates/HG1_ROUND4_VERIFICATION.md §3). `APP.data.getExposure("sector")`
  // mixes real GICS-style sectors (Information Technology, Communication Services, ...)
  // with values that are not sectors at all (Diversified Fund, Government Bonds,
  // Structured Product) — a polished bar chart makes "Diversified Fund" read as a peer
  // of "Information Technology," implying sector diversification the reader has not
  // actually been shown. ETF look-through stays out of scope (§26); the fix is not to
  // acquire the missing look-through data, it is to stop presenting a fund/bond/
  // structured-note holding as if its `sector` field were a sector.
  //
  // This is a PRESENTATION-LAYER fix, computed here from fields already exposed on
  // every holding (`assetClass`, `sector`, `marketValueUSD`, `analyticsSupport`) — not a
  // new analytical methodology. It does not recompute anything getExposure("sector")
  // doesn't already know per-holding; it only re-groups already-real, already-summed
  // dollar figures by a dimension (assetClass) the data model already carries. Every
  // dollar total below reconciles to the sum of real `marketValueUSD` fields.
  //
  // WHAT I ACTUALLY WANT FROM js/data.js INSTEAD (stated precisely, per this round's
  // instruction to "specify exactly what you need," not decide it silently): either (a)
  // `APP.data.getExposure("sector")`'s segments each carry a `classification` field —
  // "SECTOR" | "POOLED_FUND" | "FIXED_INCOME" | "STRUCTURED_UNSUPPORTED" — so this
  // partition is computed once, in the one place exposure aggregation already lives,
  // with its own Evidence/Proof-Packet entry; or (b) a dedicated
  // `APP.data.getSectorClassification()` accessor returning the same shape this helper
  // builds. Until either exists, this client-side fallback is a considered stand-in, not
  // a silent substitute — flagged here and in this designer's handoff.
  // ---------------------------------------------------------------------
  var ASSET_CLASS_TO_SECTOR_GROUP = {
    "Equity": "SECTOR",
    "Equity Fund": "POOLED_FUND",
    "Fixed Income Fund": "FIXED_INCOME"
    // "Derivative" and anything else fall through to the analyticsSupport check below,
    // then to STRUCTURED_UNSUPPORTED as the safe default for an asset class this list
    // does not explicitly recognize — never silently folded into "SECTOR".
  };
  // PD-0015 §2.3's invariant, applied structurally rather than just by convention:
  // "translate what a human reads, never what a system joins on." This function now
  // groups and returns CANONICAL keys only — `key` is either the raw `h.sector` string
  // (a js/data.js field, e.g. "Information Technology") or one of the three fixed
  // enum keys ("POOLED_FUND"/"FIXED_INCOME"/"STRUCTURED_UNSUPPORTED") — and contains
  // NO call to APP.i18n anywhere in its body. It is therefore, by construction, not
  // merely by testing, identical in both languages: nothing inside it can read
  // APP.i18n.getLang(). A prior version of this function called APP.i18n.t() to build
  // the non-sector labels INSIDE this classification step — functionally harmless
  // today (nothing downstream used those labels as a key), but it mixed the
  // classification and rendering concerns PD-0015 §2.3 requires kept apart. Display
  // translation is now a separate, explicit step — labelForSectorSegment() below —
  // applied by the CALLER when building chart items, never here.
  APP.ui.classifySectorExposure = function classifySectorExposure(holdings, totalValue) {
    holdings = holdings || [];
    var sectorTotals = {};
    var groupTotals = { POOLED_FUND: 0, FIXED_INCOME: 0, STRUCTURED_UNSUPPORTED: 0 };
    var total = typeof totalValue === "number" ? totalValue : holdings.reduce(function (s, h) { return s + (h.marketValueUSD || 0); }, 0);
    holdings.forEach(function (h) {
      var value = h.marketValueUSD || 0;
      // Any assetClass this map does not explicitly recognize (e.g. "Derivative") falls
      // through to STRUCTURED_UNSUPPORTED as the safe default — never silently folded
      // into "SECTOR". analyticsSupport === "UNSUPPORTED_ASSET" is already true for
      // every case that reaches this branch in the current dataset; the explicit
      // fallback is kept regardless of that flag so a FUTURE unrecognized assetClass
      // (with no analyticsSupport flag at all) still lands in the safe, non-sector
      // bucket rather than being silently counted as a sector.
      var group = ASSET_CLASS_TO_SECTOR_GROUP[h.assetClass] || "STRUCTURED_UNSUPPORTED";
      if (group === "SECTOR") {
        var key = h.sector || "Unclassified";
        sectorTotals[key] = (sectorTotals[key] || 0) + value;
      } else {
        groupTotals[group] += value;
      }
    });
    function toSegments(map) {
      return Object.keys(map).map(function (key) {
        var value = map[key];
        return { key: key, value: value, pct: total ? value / total : null };
      }).sort(function (a, b) { return b.value - a.value; });
    }
    var nonSectorSegments = Object.keys(groupTotals)
      .filter(function (k) { return groupTotals[k] > 0; })
      .map(function (k) { return { key: k, value: groupTotals[k], pct: total ? groupTotals[k] / total : null }; })
      .sort(function (a, b) { return b.value - a.value; });
    return { sectorSegments: toSegments(sectorTotals), nonSectorSegments: nonSectorSegments, total: total };
  };

  // The RENDER step, deliberately separate from the classification above — turns a
  // canonical `key` into the current-language display label. Called by every surface
  // that renders classifySectorExposure()'s output (js/surfaces/overview.js,
  // js/surfaces/analytics.js) when building chart items, never inside the classifier.
  var NON_SECTOR_KEY_TO_I18N_KEY = {
    POOLED_FUND: "sector.pooledFund", FIXED_INCOME: "sector.fixedIncome",
    STRUCTURED_UNSUPPORTED: "sector.structuredUnsupported"
  };
  APP.ui.labelForSectorSegment = function labelForSectorSegment(seg, isNonSector) {
    if (isNonSector) return APP.i18n.t(NON_SECTOR_KEY_TO_I18N_KEY[seg.key] || seg.key);
    // A real sector name (PD-0015 Part 2 — "Information Technology" -> "信息技术").
    return APP.ui.translateTaxonomyLabel(seg.key);
  };

  // ---------------------------------------------------------------------
  // PD-0015 §2.3 — "a self-check assertion that exposure groupings are identical in
  // both languages would enforce this ... and is worth having." classifySectorExposure
  // is now language-independent BY CONSTRUCTION (no APP.i18n call anywhere in its
  // body — see its own comment), which is the structural guarantee; this function is
  // the RUNTIME CHECK that guarantee actually holds, comparing the canonical (key,
  // value, pct) triples — never the display label, which is EXPECTED to differ — under
  // "en" and "zh", byte-for-byte, then restoring whatever language was active before
  // this check ran. Exposed on APP.ui (this function's own home) rather than
  // js/selfcheck.js (js/data.js/js/selfcheck.js are the other designer's write path) —
  // callable from a browser console today, and a real assertion for
  // js/selfcheck.js to adopt once its owner can add it there (flagged in this
  // designer's handoff, per the coordinator's request to say who should own it).
  // ---------------------------------------------------------------------
  APP.ui.verifySectorClassificationLanguageInvariant = function verifySectorClassificationLanguageInvariant(holdings, totalValue) {
    var originalLang = APP.i18n.getLang();
    function fingerprint(segments) {
      return segments.map(function (s) { return s.key + "=" + s.value + "@" + s.pct; }).sort();
    }
    // setLangQuiet (not APP.i18n.setLang) — this diagnostic is read-only and must not
    // trigger a full app re-render three times just to run a comparison.
    setLangQuiet("en");
    var en = APP.ui.classifySectorExposure(holdings, totalValue);
    setLangQuiet("zh");
    var zh = APP.ui.classifySectorExposure(holdings, totalValue);
    setLangQuiet(originalLang);
    var enSector = fingerprint(en.sectorSegments), zhSector = fingerprint(zh.sectorSegments);
    var enNon = fingerprint(en.nonSectorSegments), zhNon = fingerprint(zh.nonSectorSegments);
    var sectorMatch = JSON.stringify(enSector) === JSON.stringify(zhSector);
    var nonSectorMatch = JSON.stringify(enNon) === JSON.stringify(zhNon);
    return {
      identical: sectorMatch && nonSectorMatch,
      sectorSegmentsMatch: sectorMatch, nonSectorSegmentsMatch: nonSectorMatch,
      en: { sectorSegments: enSector, nonSectorSegments: enNon },
      zh: { sectorSegments: zhSector, nonSectorSegments: zhNon }
    };
  };

  // ---------------------------------------------------------------------
  // Donut legend (feedback log §9.1, "Scenario Lab donut charts lack sufficient
  // labels" — item 8 of the round-4 visual defects, §4.1's "fix the shared cause"):
  // APP.charts.donut draws an SVG ring with no labels at all beyond its optional single
  // center label. This is the shared textual legend every donut consumer (Scenario Lab's
  // allocation comparison, Overview's asset-mix donut) can mount BESIDE the chart — real
  // DOM text, not more SVG, which is also the more accessible route (a screen reader
  // reads this list; it does not read SVG path fills). Swatch colors read the exact same
  // chart-donut-seg-N cycle charts.js's donut() itself uses, so a segment's legend swatch
  // and its wedge are never two different colors for the same index.
  // ---------------------------------------------------------------------
  APP.ui.renderDonutLegend = function renderDonutLegend(container, segments, opts) {
    opts = opts || {};
    var list = document.createElement("ul");
    list.className = "donut-legend";
    (segments || []).forEach(function (seg, i) {
      var li = document.createElement("li");
      li.className = "donut-legend-row";
      var swatch = document.createElement("span");
      swatch.className = "donut-legend-swatch chart-donut-seg-" + (i % 6);
      li.appendChild(swatch);
      var labelSpan = document.createElement("span");
      labelSpan.className = "donut-legend-label";
      labelSpan.textContent = seg.label;
      li.appendChild(labelSpan);
      var valSpan = document.createElement("span");
      valSpan.className = "donut-legend-value";
      var pct = seg.pct !== undefined && seg.pct !== null ? seg.pct : (opts.total ? seg.value / opts.total : null);
      valSpan.textContent = pct !== null ? APP.ui.formatPercent(pct, 1) : APP.ui.formatCurrency(seg.value);
      li.appendChild(valSpan);
      list.appendChild(li);
    });
    container.appendChild(list);
    return list;
  };

  // ---------------------------------------------------------------------
  // Freshness renderer (D5) — two axes never merge; ranked by categorical
  // severity, not raw timestamp comparison. (Direction A's timezone bug —
  // comparing HKT vs CST clock values directly — is exactly what this avoids.)
  //
  // HG1 round-4 fix (coordinator review, fifth bilingual-adjacent pass) — the severity
  // order was DELAYED(1) < END_OF_DAY(2), so a merely-closed, fully-current session
  // (END_OF_DAY) outranked an actively-lagging live feed (DELAYED) as "worse." On this
  // build's real data (US/HK/CN all END_OF_DAY, both FX axes DELAYED) that produced
  // `leastFreshAxis: "us_equity"` — the SAME axis carrying the MOST RECENT equity
  // print of the three, asserted as the least fresh one, while ignoring that two other
  // axes sat in a strictly worse state. This is the exact defect class PD-0014 exists
  // to catch: a claim (the "least fresh" label) contradicting the very data it
  // describes. Corrected order: an end-of-day close is a COMPLETE, authoritative value
  // for a session that has fully concluded; a DELAYED feed is an INCOMPLETE, lagging
  // value during a session still in progress — worse, not better. STALE remains worst
  // overall (no update across one or more elapsed sessions, PD-0014 Part 1's
  // session-aware measure); LIVE remains best.
  var FRESHNESS_SEVERITY = { STALE: 3, DELAYED: 2, END_OF_DAY: 1, LIVE: 0 };

  // Shared ranking core — used by both APP.ui.rankLeastFresh (whose single-axis-key
  // return contract is depended on by js/data.js's getFreshness() and therefore fixed,
  // per CONTRACT.md) and by renderFreshnessStrip's OWN independent re-check for whether
  // a genuine tie exists (so the strip can say so rather than silently naming one axis
  // — the coordinator's explicit instruction). Recomputed fresh from the same `axes`
  // input each time, not cached/stateful, so the two call sites can never disagree.
  function computeLeastFreshRanking(axes) {
    axes = axes || [];
    if (!axes.length) return { axis: null, tied: [] };
    var maxSev = -1;
    axes.forEach(function (a) {
      var sev = FRESHNESS_SEVERITY[a.state] === undefined ? -1 : FRESHNESS_SEVERITY[a.state];
      if (sev > maxSev) maxSev = sev;
    });
    var tied = axes.filter(function (a) {
      return (FRESHNESS_SEVERITY[a.state] === undefined ? -1 : FRESHNESS_SEVERITY[a.state]) === maxSev;
    });
    if (tied.length > 1) {
      // Tier 2 — delayMinutes, only when EVERY tied axis reports one: a direct,
      // unambiguous "how much more delayed" measure that needs no timezone handling
      // at all (unlike comparing asOf timestamps), so it is tried first.
      if (tied.every(function (a) { return typeof a.delayMinutes === "number"; })) {
        var maxDelay = Math.max.apply(null, tied.map(function (a) { return a.delayMinutes; }));
        var byDelay = tied.filter(function (a) { return a.delayMinutes === maxDelay; });
        if (byDelay.length < tied.length) tied = byDelay;
      }
    }
    if (tied.length > 1) {
      // Tier 3 — asOf timestamp, ONLY when every still-tied axis reports the identical
      // timezone token. Comparing raw clock values across different timezones is
      // exactly the Direction A bug this whole function exists to avoid (see the
      // header comment above and CONTRACT.md §6); same timezone makes a direct string
      // comparison of the (identically-formatted) date/time prefix safe.
      var tzOf = function (a) { var m = /([A-Za-z]+)$/.exec(String(a.asOf || "")); return m ? m[1] : null; };
      var firstTz = tzOf(tied[0]);
      var sameTz = firstTz && tied.every(function (a) { return tzOf(a) === firstTz; });
      if (sameTz) {
        var oldestAsOf = tied.reduce(function (o, a) { return (o === null || a.asOf < o) ? a.asOf : o; }, null);
        var byAsOf = tied.filter(function (a) { return a.asOf === oldestAsOf; });
        if (byAsOf.length < tied.length) tied = byAsOf;
      }
    }
    // Any remaining multi-axis tie is genuine — severity, degree-of-delay, and safely-
    // comparable timestamps all agree there is no basis to prefer one axis over
    // another. The first tied axis is returned (stable/deterministic, never random)
    // for callers that need exactly one axis key (APP.ui.rankLeastFresh's fixed
    // contract); `tied` (every axis still in contention) is returned alongside it so a
    // renderer can choose to say "tied" instead of asserting a false precision.
    return { axis: tied[0].axis, tied: tied.map(function (a) { return a.axis; }) };
  }

  function renderFreshnessPillEl(axisEntry) {
    var pill = document.createElement("span");
    pill.className = "freshness-pill freshness-" + (axisEntry.state || "").toLowerCase();
    // HG1 round-4, fourth bilingual pass (coordinator review — the Freshness column's
    // third recurrence of the same lesson). `label` comes from js/data.js (e.g. "US
    // equity", "CN A-share") — now translated via the SAME established sleeve/market map
    // (translateLabelViaMap/SLEEVE_LABEL_ZH) every other sleeve-shaped label on this
    // surface already uses, not a new term. This is load-bearing, not cosmetic: see
    // SLEEVE_LABEL_ZH's own comment on the Freshness column's fixed-width constraint.
    // Only the STATE word (Live/Delayed/EOD/Stale) was translated before this pass;
    // both pieces of this pill are now translated consistently.
    var label = translateLabelViaMap(axisEntry.label || axisEntry.axis || "", SLEEVE_LABEL_ZH);
    var stateWord = APP.i18n.t("freshness." + String(axisEntry.state || "").toLowerCase()) || axisEntry.state;
    pill.textContent = label ? label + " · " + stateWord : stateWord;
    pill.title = (axisEntry.asOf ? "As of " + axisEntry.asOf : "") +
      (axisEntry.delayMinutes ? " (delayed " + axisEntry.delayMinutes + " min)" : "");
    return pill;
  }
  APP.ui.renderFreshnessPill = function (container, axisEntry) {
    container.appendChild(renderFreshnessPillEl(axisEntry));
  };

  // HG1 round-4 (PD-0014 Part 1 §1.2) — comparability's own rendering unit, deliberately
  // NOT a `.freshness-pill` (own class, own token family: `--color-comparability*` in
  // tokens.css) — freshness names a single axis's currency state; this names a temporal-
  // COMPARABILITY limitation between two legs of a multi-leg figure, which PD-0014 is
  // explicit is a different dimension, not a fourth sufficiency state and not folded into
  // the freshness vocabulary. The short label is always visible (never hidden behind a
  // hover-only tooltip, matching D3.2's "never dismissible" discipline).
  //
  // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.4, finding F5). BEFORE this
  // pass the full disclosure note lived ONLY in `title=` — a hover-only tooltip. That was
  // masked while `appendCaveatSlot` still rendered the identical text as `claim.caveat`
  // at every depth; once the qualifierShort/caveatFull split demotes caveatFull out of
  // Quick (this same pass), a PD-0014-mandated disclosure would exist SOLELY in a
  // tooltip at Quick — not keyboard-reachable, not touch-reachable, exactly what §D3.2
  // rules out. This is now a real `<button>`: focusable, and a click opens the same
  // Evidence & Methodology overlay every other claim's evidence control uses, for the
  // SAME claim this flag is attached to — `EVIDENCE[claimId].limitations` is this exact
  // note (registerEvidenceFor reads it straight from claim.caveat), so nothing is
  // duplicated, only made reachable a second way. `title` is kept as a supplementary
  // hover hint for a mouse user, never the only path.
  function renderComparabilityFlagEl(comparability, claimId) {
    var pill = document.createElement("button");
    pill.type = "button";
    pill.className = "comparability-flag";
    pill.textContent = APP.i18n.t("common.comparabilityFlag");
    if (comparability && comparability.note) pill.title = comparability.note;
    if (claimId) {
      pill.addEventListener("click", function (evt) {
        evt.stopPropagation(); // this pill often sits inside a clickable table row / focusableMetricCell
        APP.ui.openEvidence(claimId);
      });
    }
    return pill;
  }
  APP.ui.renderComparabilityFlag = function (container, comparability, claimId) {
    container.appendChild(renderComparabilityFlagEl(comparability, claimId));
  };

  APP.ui.renderFreshnessStrip = function renderFreshnessStrip(container, freshnessData) {
    container.innerHTML = "";
    var strip = document.createElement("div");
    strip.className = "freshness-strip";
    var axes = (freshnessData && freshnessData.axes) || [];
    axes.forEach(function (axis) {
      strip.appendChild(renderFreshnessPillEl(axis));
    });
    if (freshnessData && freshnessData.leastFreshAxis) {
      var least = null;
      for (var i = 0; i < axes.length; i++) if (axes[i].axis === freshnessData.leastFreshAxis) least = axes[i];
      var note = document.createElement("span");
      note.className = "freshness-least-note";
      if (least) {
        // FIX (coordinator review) — the axis NAME beside this label was still reading
        // raw js/data.js text ("US equity") while the label itself and the pills beside
        // it were already Chinese: exactly the "two renderings of one term on one
        // screen" defect this whole pass exists to close. Same map, same call, as the
        // pill above.
        var leastLabel = translateLabelViaMap(least.label || least.axis, SLEEVE_LABEL_ZH);
        // Independent re-check for a genuine tie (see computeLeastFreshRanking's own
        // comment) — recomputed from the SAME `axes` array `leastFreshAxis` was already
        // derived from, so this can never disagree with that value; it only adds
        // whether other axes are equally justified, which `leastFreshAxis` alone
        // (a single string) cannot express.
        var ranking = computeLeastFreshRanking(axes);
        if (ranking.tied.length > 1) {
          var tiedLabels = ranking.tied.map(function (axisKey) {
            var a = null;
            for (var j = 0; j < axes.length; j++) if (axes[j].axis === axisKey) a = axes[j];
            return a ? translateLabelViaMap(a.label || a.axis, SLEEVE_LABEL_ZH) : axisKey;
          });
          note.textContent = APP.i18n.t("freshness.leastFreshTied") + tiedLabels.join(APP.i18n.getLang() === "zh" ? "、" : ", ");
        } else {
          note.textContent = APP.i18n.t("freshness.leastFresh") + leastLabel;
        }
      } else {
        note.textContent = "";
      }
      strip.appendChild(note);
    }
    container.appendChild(strip);
  };

  APP.ui.rankLeastFresh = function rankLeastFresh(axes) {
    return computeLeastFreshRanking(axes).axis;
  };

  // ---------------------------------------------------------------------
  // ACTUAL vs SCENARIO (P8) and STAGED vs COMMITTED (OCR addendum §3) —
  // structurally parallel, never merged into one badge vocabulary.
  // ---------------------------------------------------------------------
  APP.ui.renderActualScenarioBadge = function (container, stateType) {
    var badge = document.createElement("span");
    badge.className = "state-badge badge-" + (stateType === "SCENARIO" ? "scenario" : "actual");
    badge.textContent = APP.i18n.t(stateType === "SCENARIO" ? "badge.scenario" : "badge.actual");
    container.appendChild(badge);
    return badge;
  };

  APP.ui.renderStagedBadge = function (container, status) {
    var badge = document.createElement("span");
    badge.className = "state-badge badge-" + (status === "COMMITTED" ? "committed" : "staged");
    badge.textContent = APP.i18n.t(status === "COMMITTED" ? "badge.committed" : "badge.staged");
    container.appendChild(badge);
    return badge;
  };

  // OCR confidence vocabulary — deliberately NOT AVAILABLE/LIMITED/INSUFFICIENT_DATA.
  // See specs/OCR_INGESTION_ADDENDUM.md §4.1 and CONTRACT.md's "two vocabularies" note.
  //
  // Takes a fixture object DIRECTLY from APP.data.getIngestionFixtures() — an OCR field
  // ({ confidence: "HIGH"|"LOW"|null, status: "OK"|"LOW_CONFIDENCE"|"MISSING_FIELD"|
  // "AMBIGUOUS_SECURITY"|"POSSIBLE_DUPLICATE"|"CORRECTED"|"CONFIRMED", ... }) or a CSV
  // row ({ status: "STAGED"|"AMBIGUOUS_SECURITY"|"MISSING_FIELD"|"POSSIBLE_DUPLICATE", ... }).
  // The fixture's own `status`/`confidence` ENUM VALUES (the map's KEYS) require
  // no translation step — they are this app's established canonical-code shape
  // (see the classifier's canonicalEnumToken pattern above) and are never
  // rendered directly. HG1 Round 5 micro-pass (Item 3) — the DISPLAY labels
  // (the map's VALUES) were the actual, confirmed gap: run alone, this map
  // returned hardcoded English with no i18n step at all, so "Staged for
  // review"/"Ambiguous match"/"Missing" rendered in `lang=zh` exactly as
  // observed. Routed through APP.i18n.t() below, same as every other piece of
  // UI chrome in this file.
  var CONFIDENCE_STATUS_MAP = {
    STAGED: { cls: "high", key: "ingest.confidence.staged" },
    LOW_CONFIDENCE: { cls: "low", key: "ingest.confidence.lowConfidence" },
    AMBIGUOUS_SECURITY: { cls: "ambiguous-security", key: "ingest.confidence.ambiguousMatch" },
    MISSING_FIELD: { cls: "missing-field", key: "ingest.confidence.missing" },
    POSSIBLE_DUPLICATE: { cls: "possible-duplicate", key: "ingest.confidence.possibleDuplicate" },
    CORRECTED: { cls: "corrected", key: "ingest.confidence.corrected" },
    CONFIRMED: { cls: "confirmed", key: "ingest.confidence.confirmed" }
  };
  APP.ui.renderConfidencePill = function (container, field) {
    field = field || {};
    var mapped = CONFIDENCE_STATUS_MAP[field.status];
    var cls, label;
    if (mapped) { cls = mapped.cls; label = APP.i18n.t(mapped.key); }
    else if (field.confidence === "HIGH") { cls = "high"; label = APP.i18n.t("ingest.confidence.highConfidence"); }
    else if (field.confidence === "LOW") { cls = "low"; label = APP.i18n.t("ingest.confidence.lowConfidence"); }
    else { cls = "high"; label = field.status || APP.i18n.t("ingest.confidence.ok"); }
    var pill = document.createElement("span");
    pill.className = "confidence-pill confidence-" + cls;
    pill.textContent = label;
    container.appendChild(pill);
    return pill;
  };

  // ---------------------------------------------------------------------
  // Provenance chip (P1) — the ONLY sanctioned way a numeral appears inside
  // AI-authored prose. Returns an HTML STRING for template-literal composition;
  // the click handler is delegated once, globally, below.
  // ---------------------------------------------------------------------
  APP.ui.chipHTML = function chipHTML(claim, displayText) {
    var claimId = typeof claim === "string" ? claim : (claim && claim.id) || "";
    var text = displayText !== undefined ? displayText : (claim && formatClaimValue(claim)) || "";
    return '<button type="button" class="chip" data-claim-id="' + escapeAttr(claimId) +
      '">' + escapeHTML(String(text)) + "</button>";
  };

  document.addEventListener("click", function (evt) {
    var chip = evt.target.closest && evt.target.closest(".chip[data-claim-id]");
    if (chip) {
      APP.ui.openEvidence(chip.getAttribute("data-claim-id"));
    }
  });

  // Selector/ordinal digit inside AI-authored prose (e.g. "top 5 holdings") —
  // the ONE sanctioned exception to "every digit is a chip," added during
  // integration (designer-14) to resolve a tension a phase-2 author flagged
  // rather than worked around silently: PD-0008 permits a selector digit as
  // plain text (it asserts nothing falsifiable about the portfolio — it only
  // names which segment "top 5" refers to), but the blunt checkNarrativeSafety
  // scanner below could not previously tell a selector digit from a claim
  // digit, so js/ai.js's original author avoided literal digits in selector
  // phrases entirely rather than trip a false-positive warning. This makes the
  // exception explicit and auditable instead: every use is a real, greppable
  // `.numeral-selector` span, not a scanner guessing from regex context. See
  // CONTRACT.md §6A for the refined rule this codifies.
  APP.ui.selectorHTML = function selectorHTML(text) {
    return '<span class="numeral-selector">' + escapeHTML(String(text)) + "</span>";
  };

  APP.ui.checkNarrativeSafety = function checkNarrativeSafety(containerEl) {
    var blocks = containerEl.querySelectorAll(".ai-narrative");
    blocks.forEach(function (block) {
      var clone = block.cloneNode(true);
      clone.querySelectorAll(".chip, .numeral-selector").forEach(function (c) { c.remove(); });
      if (/\d/.test(clone.textContent)) {
        console.warn("[shell] checkNarrativeSafety: a digit was found outside a .chip/.numeral-selector wrapper in", block);
      }
    });
  };

  // ---------------------------------------------------------------------
  // HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1 §1.1, "every module declares a
  // minMode"). A module hidden at the current explanation mode COLLAPSES to a
  // named, one-click affordance — a real, native <details>/<summary>, reachable
  // by keyboard, touch, and mouse alike, with no new CSS class needed — rather
  // than disappearing. P9 auditability requires that nothing become
  // permanently unreachable; AC-S5.5 requires it be reachable in exactly one
  // click. Lazy-built: `opts.build` only runs the first time the module
  // actually becomes visible (already at/above its minMode, or opened by a
  // click), so a collapsed module costs nothing until opened.
  // ---------------------------------------------------------------------
  APP.ui.renderModule = function renderModule(container, opts) {
    opts = opts || {};
    var minMode = opts.minMode || "quick";
    // HG1 Round 5 correction pass — `data-module-id` (opts.id, falling back to
    // opts.label) is read by APP.uicheck (this file, further down) to identify
    // "the same module" across two separate renders of a surface at different
    // explanation modes. Purely a diagnostic attribute — no CSS rule and no other
    // runtime behaviour depends on it, so adding it cannot change anything a
    // visual reviewer sees.
    var moduleId = opts.id || opts.label || "";
    if (APP.state.explanationModeAtLeast(minMode)) {
      var mount = document.createElement("div");
      mount.className = "module-gate module-gate-open";
      if (moduleId) mount.setAttribute("data-module-id", moduleId);
      if (typeof opts.build === "function") opts.build(mount);
      container.appendChild(mount);
      return mount;
    }
    var det = document.createElement("details");
    det.className = "module-gate module-gate-collapsed";
    if (moduleId) det.setAttribute("data-module-id", moduleId);
    var summary = document.createElement("summary");
    summary.className = "link-button";
    summary.textContent = opts.label || APP.i18n.t("depth." + minMode);
    det.appendChild(summary);
    var body = document.createElement("div");
    det.appendChild(body);
    det.addEventListener("toggle", function () {
      if (det.open && !det._built) {
        det._built = true;
        if (typeof opts.build === "function") opts.build(body);
      }
    });
    container.appendChild(det);
    return det;
  };

  // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.4's `exposure.currency`
  // exception: "safe to shorten, but the placement is the real requirement"). The
  // parent exposure.currency claim renders "See breakdown" and carries no number,
  // while the misleading figures are the CHILD (per-currency) segments a bar chart
  // draws directly — a qualifier on the collapsed parent claim card does not
  // discharge the disclosure for a reader looking at the CNY bar. Surfaces call this
  // directly, beside the currency exposure chart itself, independent of that claim
  // card's own depth/collapse state, so the illustrative-FX-snapshot disclosure is
  // present at the SAME rendering unit as every CNY-converted amount, not only on
  // the collapsed parent.
  APP.ui.renderQualifierNote = function renderQualifierNote(container, claim) {
    if (!claim) return null;
    var text = APP.ui.localizeClaimField(claim, "qualifierShort");
    if (!text) return null;
    var p = document.createElement("p");
    p.className = "metric-qualifier";
    p.textContent = text;
    container.appendChild(p);
    return p;
  };

  // ---------------------------------------------------------------------
  // Full claim ladder (D2): conclusion -> key number -> explanation -> evidence
  // -> methodology. Closed by default. Built on top of renderMetricValue, never
  // duplicating its state logic.
  // ---------------------------------------------------------------------
  APP.ui.renderClaim = function renderClaim(container, claim, opts) {
    opts = opts || {};
    // HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1 §1.1). `opts.depth`, when a caller
    // supplies it, IS the local override PD-0016 names ("per-card ladders become
    // local overrides") — left exactly as it always worked. Omitted, it now falls
    // back to the shared APP.state.explanationMode instead of a hardcoded "quick",
    // which is the actual architectural change this finding required: every claim
    // card that does not ask for a specific depth now follows the one global mode.
    var depth = opts.depth || APP.state.getExplanationMode();
    container.innerHTML = "";
    var card = document.createElement("div");
    card.className = "claim-card";
    if (claim.stateType === "SCENARIO") card.classList.add("claim-scenario");

    var head = document.createElement("div");
    head.className = "claim-head";
    var titleWrap = document.createElement("div");
    titleWrap.className = "claim-title-wrap";
    // HG1 ux_planning revision (review-06, secondary — duplicated disclosure
    // headings). `opts.showLabel` (new, default true — every existing caller is
    // unaffected) lets a caller that already renders this claim's own label as an
    // adjacent section heading (e.g. Overview's Currency Exposure block-kicker,
    // immediately above this exact claim) suppress the second, redundant copy
    // instead of showing the identical text twice in a row.
    if (opts.showLabel !== false) {
      var title = document.createElement("span");
      title.className = "claim-label";
      title.textContent = APP.ui.localizeClaimField(claim, "label") || "";
      titleWrap.appendChild(title);
    }
    if (claim.stateType === "SCENARIO") APP.ui.renderActualScenarioBadge(titleWrap, "SCENARIO");
    head.appendChild(titleWrap);

    if (opts.showLadder !== false) head.appendChild(renderLadderControl(claim, depth, rerender));
    card.appendChild(head);

    var body = document.createElement("div");
    body.className = "claim-body";
    card.appendChild(body);
    container.appendChild(card);

    function rerender(nextDepth) {
      depth = nextDepth;
      renderBody();
    }
    renderBody();

    function renderBody() {
      body.innerHTML = "";
      var conclusion = document.createElement("p");
      conclusion.className = "claim-conclusion";
      conclusion.textContent = APP.ui.localizeClaimField(claim, "conclusionQuick") || "";
      body.appendChild(conclusion);

      var valueRow = document.createElement("div");
      valueRow.className = "claim-value-row";
      renderMetricValue(valueRow, claim);
      body.appendChild(valueRow);

      if (depth === "quick") {
        // HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1 §1.3). A deterministic analogy,
        // when the claim carries one, renders BESIDE renderMetricValue's own output
        // above — never instead of it (PD-0012 §2's own condition, and the owner's
        // explicit counter-example: beta must not become "7% less risk"). Bakes the
        // rule into the shared ladder itself so any claim/any surface gets it for
        // free the moment js/data.js populates `claim.analogyQuick`, with no
        // per-call-site plumbing required.
        var analogyText = APP.ui.localizeClaimField(claim, "analogyQuick");
        if (analogyText) {
          var analogy = document.createElement("p");
          analogy.className = "claim-simple";
          analogy.textContent = analogyText;
          body.appendChild(analogy);
        }
        appendCaveatSlot(body, claim, "quick");
        appendEvidenceControl(body, claim);
        return;
      }

      // HG1 round-4 (PD-0012 §2, feedback log §11): the four-rung ladder
      // (Quick/Simple/Investor/Professional) is replaced by three
      // (Quick/Simple/Professional) — "Investor" is removed as a SELECTABLE rung. The
      // ladder MECHANISM and every field a claim already carries are untouched (this is
      // the owner's own explicit condition — "only the number and naming of the rungs
      // change"): referencePoint and investorDetail still exist on the claim object
      // (data.js is unchanged) and still render, now surfaced under Professional rather
      // than a separate middle rung, alongside professionalDetail — Professional's job
      // (per PD-0012) is "what happened; how it was measured; assumptions; benchmark;
      // window/frequency; methodology; limitations; decomposition; evidence; portfolio
      // implications," which is a strict superset of what the old Investor rung showed.
      // Quick and Simple both answer strictly fewer questions than before, exactly as
      // PD-0012 specifies — no content is deleted, only reachable at one fewer named depth.
      if (depth === "simple" || depth === "professional") {
        var simple = document.createElement("p");
        simple.className = "claim-simple";
        simple.textContent = APP.ui.localizeClaimField(claim, "explanationSimple") || "";
        body.appendChild(simple);
        // HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1 §1.4, "Simple adds the reference
        // point beside each figure" — P4, every judgment needs a reference point).
        // MOVED here from the Professional-only block below: it previously rendered
        // ONLY at Professional, so Simple asserted a judgment (e.g. a volatility/
        // drawdown comparison) with no visible reference point at all, and — because
        // Professional was the ONLY depth that ever showed it — a Chinese reader on
        // any other depth never saw a reference point to translate in the first
        // place. I7/I8's hardcoded "Reference: " is also fixed here, via the new
        // claim.referenceLabel i18n key, so this line is no longer English-only on a
        // Chinese screen (PD-0012 §3).
        if (claim.referencePoint) {
          var ref = document.createElement("p");
          ref.className = "claim-reference";
          ref.textContent = APP.i18n.t("claim.referenceLabel") + APP.ui.localizeClaimField(claim, "referencePoint");
          body.appendChild(ref);
        }
      }
      if (depth === "professional") {
        if (claim.investorDetail) {
          var inv = document.createElement("div");
          inv.className = "claim-investor-detail";
          var invText = APP.ui.localizeClaimField(claim, "investorDetail");
          inv.textContent = typeof invText === "string" ? invText : JSON.stringify(invText);
          body.appendChild(inv);
        }
        if (claim.professionalDetail) {
          var pro = document.createElement("p");
          pro.className = "claim-professional-detail";
          pro.textContent = APP.ui.localizeClaimField(claim, "professionalDetail");
          body.appendChild(pro);
        }
      }
      appendCaveatSlot(body, claim, depth);
      appendEvidenceControl(body, claim);
    }
  };

  function appendCaveatSlot(body, claim, depth) {
    // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling; AC-S5.6). `depth` was
    // accepted and never read — a dead parameter the audit named directly. It is
    // now the gate: `caveatFull` (this slot; `claim.caveat`, full and unshortened
    // per F4) renders in a block slot at Simple/Professional ONLY, never at Quick.
    // This is not a new omission — it is what makes Quick actually shorter than
    // Professional (S5) and what keeps the mandatory, non-dismissible
    // `qualifierShort` (rendered inside renderMetricValue, at every depth
    // including Quick) the ONLY sufficiency disclosure a Quick reader sees inline,
    // exactly the split the ruling specifies. The full caveat is never deleted or
    // shortened here — it is still fully present at Simple/Professional and, via
    // registerEvidenceFor (js/data.js), in the Proof Packet at every depth.
    if (depth === "quick") return;
    // D2.2: the caveat slot always exists when a caveat is non-empty; it is never
    // omitted by a rendering rule, only compressed by wording (compression itself is
    // quant_analyst's call, out of this file's authority — this slot just guarantees
    // the mechanism exists).
    if (!claim.caveat && claim.sufficiency === "AVAILABLE") return;
    var slot = document.createElement("p");
    slot.className = "claim-caveat";
    slot.textContent = APP.ui.localizeClaimField(claim, "caveat") || "";
    if (slot.textContent) body.appendChild(slot);
  }

  function appendEvidenceControl(body, claim) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "evidence-control";
    btn.textContent = APP.i18n.t("common.evidenceMethodology");
    btn.addEventListener("click", function () { APP.ui.openEvidence(claim.id); });
    body.appendChild(btn);
  }

  // HG1 round-4 (PD-0012 §2): three rungs, not four — "Investor" removed.
  // HG1 Round 5, Phase 2 (S5) — this is now also the single source APP.state's
  // explanation-mode machinery (top of this file) and the persistent header
  // control (renderExplanationModeControl, below) both read, so the per-card
  // ladder and the global control can never independently drift to a different
  // set of named rungs.
  var DEPTH_LEVELS = ["quick", "simple", "professional"];
  function renderLadderControl(claim, currentDepth, onChange) {
    var wrap = document.createElement("div");
    wrap.className = "depth-ladder";
    DEPTH_LEVELS.forEach(function (level) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "depth-pill" + (level === currentDepth ? " depth-pill-active" : "");
      btn.textContent = APP.i18n.t("depth." + level);
      btn.addEventListener("click", function () {
        wrap.querySelectorAll(".depth-pill").forEach(function (b) { b.classList.remove("depth-pill-active"); });
        btn.classList.add("depth-pill-active");
        onChange(level);
      });
      wrap.appendChild(btn);
    });
    return wrap;
  }

  // ---------------------------------------------------------------------
  // Shared insights list — Insights (D1 surface 6) is "integrated into
  // relevant surfaces," not a dedicated phase-2 file. Centralized here so
  // Overview and any other surface render insight rows identically.
  // ---------------------------------------------------------------------
  APP.ui.renderInsightsList = function renderInsightsList(container, insights, opts) {
    opts = opts || {};
    container.innerHTML = "";
    var list = document.createElement("div");
    list.className = "insights-list insights-" + (opts.mode || "compact");
    (insights || []).forEach(function (insight) {
      var row = document.createElement("div");
      row.className = "insight-row severity-" + insight.severity.toLowerCase();
      var glyph = document.createElement("span");
      glyph.className = "insight-glyph";
      glyph.textContent = { WARNING: "▲", ATTENTION: "●", OBSERVATION: "○" }[insight.severity] || "○";
      row.appendChild(glyph);
      var text = document.createElement("span");
      text.className = "insight-text";
      // insight.claim has no i18n field in js/data.js as of this pass (a real, specific
      // gap distinct from the 24 metric/exposure claims already translated — see this
      // designer's handoff). Routed through localizeClaimField anyway so it localizes
      // automatically, with no further change here, the moment that changes.
      text.textContent = APP.ui.localizeClaimField(insight, "claim");
      row.appendChild(text);
      var tag = document.createElement("span");
      tag.className = "insight-judgment-tag";
      // judgmentClass IS a closed taxonomy this product defines (three values, checked
      // against js/data.js directly) — translated via a fixed lookup, unlike the open-
      // ended insight.claim sentence above.
      tag.textContent = APP.i18n.t("judgmentClass." + insight.judgmentClass);
      row.appendChild(tag);
      var evBtn = document.createElement("button");
      evBtn.type = "button";
      evBtn.className = "evidence-control evidence-control-sm";
      evBtn.textContent = APP.i18n.t("common.evidence");
      evBtn.addEventListener("click", function () { APP.ui.openEvidence(insight.id); });
      row.appendChild(evBtn);
      list.appendChild(row);
    });
    container.appendChild(list);
  };

  // ---------------------------------------------------------------------
  // Contextual AI affordance — invoked from a chart/metric/section, never a
  // top-level nav destination. This is the ONLY way a surface should offer
  // "Ask about this" — do not hand-roll a second button style.
  // ---------------------------------------------------------------------
  APP.ui.aiAffordance = function aiAffordance(container, context) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ai-affordance";
    btn.textContent = (context && context.label) || APP.i18n.t("common.askAboutThis");
    btn.addEventListener("click", function () { APP.ui.openAI(context); });
    container.appendChild(btn);
    return btn;
  };

  APP.ui.openAI = function openAI(context) {
    var overlay = document.getElementById("app-ai-overlay");
    var mount = document.getElementById("app-ai-overlay-body");
    overlay.hidden = false;
    if (_aiHandler) {
      mount.innerHTML = "";
      _aiHandler.renderPanel(mount, context || {});
    } else {
      notBuilt(mount, {
        label: "AI Analyst",
        owner: "designer-13",
        detail: "The AI Analyst module (js/ai.js) has not registered yet via APP.registerAI(). " +
          "This shell intentionally does not synthesize placeholder AI narrative here — " +
          "authoring grounded, citation-chip narrative is designer-13's job, not the shell's."
      });
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    var closeBtn = document.getElementById("app-ai-overlay-close");
    if (closeBtn) closeBtn.addEventListener("click", function () {
      document.getElementById("app-ai-overlay").hidden = true;
    });
  });

  // ---------------------------------------------------------------------
  // Evidence / Methodology overlay (D4, P9). Fallback renders a real, if
  // basic, view straight from data.js (safe: formatting already-structured
  // fields, not authoring new narrative) — unlike AI's fallback above.
  // claimId === null means "browse all" (footer Methodology & Evidence link).
  // ---------------------------------------------------------------------
  APP.ui.openEvidence = function openEvidence(claimId) {
    var overlay = document.getElementById("app-evidence-overlay");
    var mount = document.getElementById("app-evidence-overlay-body");
    overlay.hidden = false;
    mount.innerHTML = "";
    if (_evidenceHandler) {
      _evidenceHandler.open(claimId, mount);
      return;
    }
    renderDefaultEvidence(mount, claimId);
  };

  function renderDefaultEvidence(mount, claimId) {
    var banner = document.createElement("div");
    banner.className = "evidence-default-banner";
    banner.textContent = "Default structural preview — js/evidence.js (designer-13) will replace this with the full designed interaction.";
    mount.appendChild(banner);

    if (claimId === null || claimId === undefined) {
      var heading = document.createElement("h3");
      heading.textContent = "Methodology & Evidence Registry";
      mount.appendChild(heading);
      var ids = (APP.data && APP.data.listMetricIds && APP.data.listMetricIds()) || [];
      ids.forEach(function (id) {
        mount.appendChild(renderMethodologyEntry(APP.data.getMethodology(id), id));
      });
      return;
    }

    var evidence = APP.data && APP.data.getEvidence ? APP.data.getEvidence(claimId) : null;
    if (!evidence) {
      var p = document.createElement("p");
      p.textContent = "No evidence record found for claim '" + claimId + "'.";
      mount.appendChild(p);
      return;
    }
    var title = document.createElement("h3");
    title.textContent = evidence.claim || claimId;
    mount.appendChild(title);
    var dl = document.createElement("dl");
    dl.className = "evidence-fields";
    Object.keys(evidence).forEach(function (field) {
      var dt = document.createElement("dt"); dt.textContent = field;
      var dd = document.createElement("dd"); dd.textContent = JSON.stringify(evidence[field]);
      dl.appendChild(dt); dl.appendChild(dd);
    });
    mount.appendChild(dl);
    if (evidence.methodologyId) {
      mount.appendChild(renderMethodologyEntry(APP.data.getMethodology(evidence.methodologyId), evidence.methodologyId));
    }
  }

  function renderMethodologyEntry(entry, id) {
    var box = document.createElement("div");
    box.className = "methodology-entry";
    if (!entry) {
      box.innerHTML = "<h4>" + escapeHTML(id) + "</h4><p class=\"methodology-not-published\">Not yet published.</p>";
      return box;
    }
    var h4 = document.createElement("h4");
    h4.textContent = entry.metricName || id;
    box.appendChild(h4);
    var dl = document.createElement("dl");
    dl.className = "methodology-fields";
    Object.keys(entry).forEach(function (field) {
      if (field === "metricName") return;
      var dt = document.createElement("dt"); dt.textContent = field;
      var dd = document.createElement("dd"); dd.textContent = String(entry[field]);
      dl.appendChild(dt); dl.appendChild(dd);
    });
    box.appendChild(dl);
    return box;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var closeBtn = document.getElementById("app-evidence-overlay-close");
    if (closeBtn) closeBtn.addEventListener("click", function () {
      document.getElementById("app-evidence-overlay").hidden = true;
    });
    var footerLink = document.getElementById("app-footer-methodology-link");
    if (footerLink) footerLink.addEventListener("click", function (e) {
      e.preventDefault();
      APP.ui.openEvidence(null);
    });
  });

  // ---------------------------------------------------------------------
  // Focus-and-inspect dock (Direction B graft, "where useful") — a
  // collapsible right-docked panel any surface may populate. Not mandatory;
  // Overview is not expected to use it, Analytics likely will.
  //
  // HG1 ux_planning revision (review-06, B6) — three fixes to this dock's lifecycle,
  // none of which touch the collapse/expand toggle's own existing behavior:
  //   1. `focus()` now builds its OWN visible close ("×") button into the title bar,
  //      wired to `.clear()` — a reachable UI dismissal that exists regardless of
  //      which route opened the dock or whether the user ever finds the collapse rail
  //      toggle (⋮, unchanged below). Previously the ONLY way to fully empty this dock
  //      was `.clear()`, which nothing but a route-signature change (added just below)
  //      ever called — review-06 found no close control and Escape doing nothing.
  //   2. A document-level Escape handler (added below, alongside the toggle's own
  //      listener) calls `.clear()` whenever the dock is open.
  //   3. `renderRoute()` (this file's router) now calls `.clear()` whenever the
  //      GROUP/SURFACE the user is navigating to differs from the one last rendered —
  //      never on a same-route re-render (language/explanation-mode/color-convention
  //      changes all re-run renderRoute() without changing the route itself, and must
  //      not discard whatever the CURRENT surface just opened). This is the
  //      deterministic route-change reset: navigating from Analytics (dock open,
  //      showing the correlation matrix) to Portfolio now closes and empties the dock
  //      instead of leaving Analytics content docked beside the Portfolio ledger.
  // `payload.wide` (new, optional) — see styles/tokens.css's `--inspector-width-wide`
  // comment; opts this one payload into the wider variant (currently: the Sleeve
  // Correlation Matrix, B5) without affecting any other caller's default width.
  // ---------------------------------------------------------------------
  function clearInspector() {
    _inspectorPayload = null;
    var dock = document.getElementById("app-inspector");
    dock.classList.remove("inspector-open");
    dock.classList.remove("inspector-wide");
    document.getElementById("app-inspector-body").innerHTML = "";
    document.getElementById("app-inspector-title").innerHTML = "";
  }
  APP.ui.inspector = {
    focus: function (payload) {
      _inspectorPayload = payload;
      var dock = document.getElementById("app-inspector");
      var mount = document.getElementById("app-inspector-body");
      var titleEl = document.getElementById("app-inspector-title");
      dock.classList.add("inspector-open");
      dock.classList.toggle("inspector-wide", !!payload.wide);
      titleEl.innerHTML = "";
      var titleText = document.createElement("span");
      titleText.textContent = payload.title || "";
      titleEl.appendChild(titleText);
      var closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.className = "app-overlay-close";
      closeBtn.setAttribute("aria-label", APP.i18n.t("common.close"));
      closeBtn.title = APP.i18n.t("common.close");
      closeBtn.textContent = "×";
      closeBtn.addEventListener("click", function () { APP.ui.inspector.clear(); });
      titleEl.appendChild(closeBtn);
      mount.innerHTML = "";
      if (typeof payload.render === "function") payload.render(mount);
    },
    clear: clearInspector
  };

  document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.getElementById("app-inspector-toggle");
    if (toggle) toggle.addEventListener("click", function () {
      document.getElementById("app-inspector").classList.toggle("inspector-open");
    });
  });

  // HG1 ux_planning revision (review-06, B6, fix 2) — Escape dismisses the inspector
  // dock whenever it is open, mirroring the Evidence/Settings overlays' own close
  // affordances (neither of which this dock previously had an equivalent for).
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" && e.keyCode !== 27) return;
    var dock = document.getElementById("app-inspector");
    if (dock && dock.classList.contains("inspector-open")) APP.ui.inspector.clear();
  });

  // ---------------------------------------------------------------------
  // Settings / Policy overlay (D1 surface 10) — outside primary nav, owned
  // and finished here in shell.js because no phase-2 file is assigned to it.
  // ---------------------------------------------------------------------
  // A labeled <select>, built once, used by every settings control below — no literal
  // hex/px, no bespoke markup per control, consistent with this file's own "one shared
  // primitive, not four" rule applied to its own overlay.
  function settingsField(labelText, controlEl, noteText) {
    var wrap = document.createElement("div");
    wrap.className = "settings-field";
    var label = document.createElement("label");
    label.className = "settings-field-label";
    label.textContent = labelText;
    var controlId = "settings-ctrl-" + Math.floor(Math.random() * 1e8);
    controlEl.id = controlId;
    label.htmlFor = controlId;
    wrap.appendChild(label);
    wrap.appendChild(controlEl);
    if (noteText) {
      var note = document.createElement("p");
      note.className = "settings-field-note";
      note.textContent = noteText;
      wrap.appendChild(note);
    }
    return wrap;
  }

  function openSettings() {
    var overlay = document.getElementById("app-settings-overlay");
    var mount = document.getElementById("app-settings-overlay-body");
    overlay.hidden = false;
    mount.innerHTML = "";
    var accounts = (APP.data && APP.data.getAccounts && APP.data.getAccounts()) || [];

    // HG1 ux_planning revision (review-06, secondary — "the settings-drawer title
    // twice"). This body-level <h3> repeated "settings.title" verbatim immediately
    // below the overlay's own head bar (index.html's #app-settings-overlay-title,
    // kept in sync by localizeStaticChrome below) — the SAME text rendered twice in
    // the same drawer, in both languages. Removed here; the head bar already states
    // the drawer's title.

    // ---- PD-0012 §3 — Language: English | 简体中文 ----------------------
    var langSelect = document.createElement("select");
    langSelect.className = "settings-select";
    [["en", "English"], ["zh", "简体中文"]].forEach(function (pair) {
      var opt = document.createElement("option");
      opt.value = pair[0]; opt.textContent = pair[1];
      if (pair[0] === APP.i18n.getLang()) opt.selected = true;
      langSelect.appendChild(opt);
    });
    langSelect.addEventListener("change", function () {
      APP.i18n.setLang(langSelect.value);
      openSettings(); // re-render this overlay itself in the new language too
    });
    mount.appendChild(settingsField(APP.i18n.t("settings.language"), langSelect));

    // ---- HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1 §1.1) — Explanation mode:
    // Quick | Simple | Professional, the SAME shared APP.state value the
    // persistent header control (renderExplanationModeControl) and every claim
    // card's own default depth all read — set here or there, never two
    // independent settings that could disagree. ----
    var modeSelect = document.createElement("select");
    modeSelect.className = "settings-select";
    DEPTH_LEVELS.forEach(function (level) {
      var opt = document.createElement("option");
      opt.value = level; opt.textContent = APP.i18n.t("depth." + level);
      if (level === APP.state.getExplanationMode()) opt.selected = true;
      modeSelect.appendChild(opt);
    });
    modeSelect.addEventListener("change", function () {
      APP.state.setExplanationMode(modeSelect.value);
      openSettings(); // re-render this overlay itself so its own select stays in sync
    });
    mount.appendChild(settingsField(APP.i18n.t("settings.explanationMode"), modeSelect,
      APP.i18n.t("settings.explanationModeNote")));

    // ---- PD-0012 §1 — Reporting Currency: USD | CNY (simulated switch) --
    var ccySelect = document.createElement("select");
    ccySelect.className = "settings-select";
    ["USD", "CNY"].forEach(function (c) {
      var opt = document.createElement("option");
      opt.value = c; opt.textContent = c;
      if (c === _reportingCurrency) opt.selected = true;
      ccySelect.appendChild(opt);
    });
    ccySelect.addEventListener("change", function () {
      _reportingCurrency = ccySelect.value;
      openSettings();
      // A real switch would re-render every reporting-currency-dependent surface; this
      // prototype's simulation is scoped to this control + note, per PD-0012 §1's
      // explicit "the prototype may simulate the switch."
    });
    mount.appendChild(settingsField(APP.i18n.t("settings.reportingCurrency"), ccySelect,
      APP.i18n.t("settings.reportingCurrencyNote")));

    // ---- feedback log §14 — Benchmark selection (confirmed-missing UX contract) ----
    var benchSelect = document.createElement("select");
    benchSelect.className = "settings-select";
    ["MSCI ACWI (ACWI)", "S&P 500 (SPX)", "Hang Seng Index (HSI)", "CSI 300 (000300.SH)"].forEach(function (b) {
      var opt = document.createElement("option");
      opt.value = b; opt.textContent = b;
      if (b === _benchmarkSelection) opt.selected = true;
      benchSelect.appendChild(opt);
    });
    benchSelect.addEventListener("change", function () {
      _benchmarkSelection = benchSelect.value;
      openSettings();
    });
    mount.appendChild(settingsField(APP.i18n.t("settings.benchmark"), benchSelect,
      APP.i18n.t("settings.benchmarkNote")));

    // ---- PD-0015 Part 1 — V1 has two valuation-time modes over one architecture, not
    // two analytics systems. HG1 scope: represent the interaction/product contract
    // honestly (that both modes exist, how they differ, which freshness states each
    // admits) — NOT full Current-mode computation, which needs the real market-data
    // spine (Priority A). [Post-HG1 Checkpoint A — S1, designer-33, 2026-09-15:
    // "blocked until HG1 is approved" removed here — false since PD-0017 (HG1 =
    // APPROVED).] This is deliberately NOT an
    // interactive toggle: Current mode has no computed destination state in this
    // prototype to switch TO, and building a selector that appears to switch but does
    // nothing (or worse, fakes a Live value) would be exactly the false-affordance
    // defect §15's Portfolio Policy fix already closed once this cycle, and exactly
    // the "manufacture a state the fixture cannot support" the owner explicitly
    // forbade (PD-0015 §1.3). Informational only; the one mode this build actually
    // computes (Historical as-of) is named as active, with its real cutoff date read
    // from APP.data.meta.asOf — never a placeholder.
    var valModeWrap = document.createElement("div");
    valModeWrap.className = "settings-field";
    var valModeHeading = document.createElement("h4");
    valModeHeading.textContent = APP.i18n.t("valuationMode.title");
    valModeWrap.appendChild(valModeHeading);
    var valModeIntro = document.createElement("p");
    valModeIntro.className = "settings-field-note";
    valModeIntro.textContent = APP.i18n.t("valuationMode.intro");
    valModeWrap.appendChild(valModeIntro);

    var asOfDate = (APP.data && APP.data.meta && APP.data.meta.asOf) || "";
    [
      { name: "valuationMode.current", desc: "valuationMode.currentDesc", status: APP.i18n.t("valuationMode.currentNotComputed"), active: false },
      { name: "valuationMode.historical", desc: "valuationMode.historicalDesc", status: APP.i18n.t("valuationMode.historicalActive") + (asOfDate ? " (" + asOfDate + ")" : ""), active: true }
    ].forEach(function (mode) {
      var row = document.createElement("div");
      row.className = "policy-disclosure";
      row.style.marginBottom = "var(--space-2)";
      var title = document.createElement("strong");
      title.textContent = APP.i18n.t(mode.name) + (mode.active ? " ✓" : "");
      row.appendChild(title);
      row.appendChild(document.createElement("br"));
      var desc = document.createElement("span");
      desc.textContent = APP.i18n.t(mode.desc);
      row.appendChild(desc);
      row.appendChild(document.createElement("br"));
      var status = document.createElement("span");
      status.className = "settings-field-note";
      status.textContent = mode.status;
      row.appendChild(status);
      valModeWrap.appendChild(row);
    });
    mount.appendChild(valModeWrap);

    // ---- PD-0012 §4 — Gain/loss color convention, user-selectable, defaults green-up ----
    var colorWrap = document.createElement("div");
    colorWrap.className = "settings-radio-group";
    [["intl", APP.i18n.t("settings.colorConventionIntl")], ["cn", APP.i18n.t("settings.colorConventionCn")]].forEach(function (pair) {
      var rowEl = document.createElement("label");
      rowEl.className = "settings-radio-row";
      var radio = document.createElement("input");
      radio.type = "radio"; radio.name = "color-convention"; radio.value = pair[0];
      radio.checked = _colorConvention === pair[0];
      radio.addEventListener("change", function () {
        _colorConvention = pair[0];
        document.body.classList.toggle("color-convention-cn", _colorConvention === "cn");
        renderRoute(); // repaint every currently-rendered directional value under the new convention
      });
      rowEl.appendChild(radio);
      rowEl.appendChild(document.createTextNode(" " + pair[1]));
      colorWrap.appendChild(rowEl);
    });
    mount.appendChild(settingsField(APP.i18n.t("settings.colorConvention"), colorWrap,
      APP.i18n.t("settings.colorConventionNote")));

    // ---- Account containers (unchanged content, translated headings) ----
    var accH = document.createElement("h4");
    accH.textContent = APP.i18n.t("settings.accounts");
    mount.appendChild(accH);
    var accUl = document.createElement("ul");
    accounts.forEach(function (a) {
      var li = document.createElement("li");
      // Account NAME is user-entered (never translated) and currency is a canonical
      // ISO code (never translated) — but `type` (taxable/retirement/cash) is exactly
      // PD-0015 Part 2's human-facing-taxonomy case, corrected this pass (S7):
      // previously printed straight from the raw field, which is PD-0015 §2.3's
      // failure mode ("the display string and the grouping key are the same string").
      // APP.ui.translateAccountType translates the DISPLAY text only; `a.type` itself,
      // and APP.ui.classifyAccountsByType's own grouping key, are untouched.
      li.textContent = a.name + " (" + a.currency + ", " + APP.ui.translateAccountType(a.type) + ")";
      accUl.appendChild(li);
    });
    mount.appendChild(accUl);

    // ---- feedback log §15 — Portfolio Policy: the false affordance is now a real
    // (simulated) control, not deleted copy. js/shell.js:905's old wording promised an
    // interaction with zero input elements behind it; there are now two number inputs
    // and a Save action, matching the "simulated staged/confirm" pattern already used
    // throughout js/surfaces/portfolio.js and js/surfaces/ingest.js. P7 still holds:
    // nothing is invented until the reader sets it themselves, right here. ----
    var polH = document.createElement("h4");
    polH.textContent = APP.i18n.t("settings.policy");
    mount.appendChild(polH);

    var posCapInput = document.createElement("input");
    posCapInput.type = "number"; posCapInput.min = "0"; posCapInput.max = "100"; posCapInput.step = "0.1";
    posCapInput.className = "settings-number-input";
    if (_simulatedPolicy.positionCap != null) posCapInput.value = _simulatedPolicy.positionCap;
    mount.appendChild(settingsField(APP.i18n.t("settings.positionCap"), posCapInput));

    var sectorCapInput = document.createElement("input");
    sectorCapInput.type = "number"; sectorCapInput.min = "0"; sectorCapInput.max = "100"; sectorCapInput.step = "0.1";
    sectorCapInput.className = "settings-number-input";
    if (_simulatedPolicy.sectorCap != null) sectorCapInput.value = _simulatedPolicy.sectorCap;
    mount.appendChild(settingsField(APP.i18n.t("settings.sectorCap"), sectorCapInput));

    var polNote = document.createElement("p");
    polNote.className = "policy-disclosure";
    polNote.textContent = _simulatedPolicy.positionCap == null
      ? APP.i18n.t("settings.noPositionCap")
      : APP.i18n.t("settings.positionCapSet") + _simulatedPolicy.positionCap + "%.";
    mount.appendChild(polNote);
    var sectorNote = document.createElement("p");
    sectorNote.className = "policy-disclosure";
    sectorNote.textContent = _simulatedPolicy.sectorCap == null
      ? APP.i18n.t("settings.noSectorCap")
      : APP.i18n.t("settings.sectorCapSet") + _simulatedPolicy.sectorCap + "%.";
    mount.appendChild(sectorNote);

    var saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "evidence-control";
    saveBtn.textContent = APP.i18n.t("settings.saveSimulated");
    saveBtn.addEventListener("click", function () {
      _simulatedPolicy.positionCap = posCapInput.value === "" ? null : Number(posCapInput.value);
      _simulatedPolicy.sectorCap = sectorCapInput.value === "" ? null : Number(sectorCapInput.value);
      _simulatedPolicy.saved = true;
      openSettings();
    });
    mount.appendChild(saveBtn);
    if (_simulatedPolicy.saved) {
      var savedNote = document.createElement("p");
      savedNote.className = "settings-field-note";
      savedNote.textContent = APP.i18n.t("settings.policySavedNote");
      mount.appendChild(savedNote);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var gear = document.getElementById("app-settings-btn");
    if (gear) gear.addEventListener("click", openSettings);
    var closeBtn = document.getElementById("app-settings-overlay-close");
    if (closeBtn) closeBtn.addEventListener("click", function () {
      document.getElementById("app-settings-overlay").hidden = true;
    });
  });

  // HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1 §1.1, AC-S5.1: "a single global
  // control re-renders all five routes"). Built entirely in JS — index.html is
  // not in this designer's write path this round — and mounted once into the
  // existing `.app-header-right` container (index.html already renders this
  // container; only its CHILDREN are added here, the same pattern `#app-ai-ask`'s
  // own `._wired` flag already uses on this file, immediately below). Reuses the
  // exact `.depth-ladder`/`.depth-pill` classes the per-card ladder uses — one
  // visual vocabulary for "pick a depth," not two — so this control and every
  // card's own local-override ladder are visually the same control at two scopes.
  function renderExplanationModeControl() {
    var right = document.querySelector(".app-header-right");
    if (!right) return;
    var wrap = document.getElementById("app-explanation-mode");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "app-explanation-mode";
      wrap.className = "depth-ladder";
      var askBtn = document.getElementById("app-ai-ask");
      right.insertBefore(wrap, askBtn || right.firstChild);
    }
    wrap.setAttribute("aria-label", APP.i18n.t("depth.controlLabel"));
    wrap.innerHTML = "";
    DEPTH_LEVELS.forEach(function (level) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "depth-pill" + (level === APP.state.getExplanationMode() ? " depth-pill-active" : "");
      btn.textContent = APP.i18n.t("depth." + level);
      btn.addEventListener("click", function () { APP.state.setExplanationMode(level); });
      wrap.appendChild(btn);
    });
  }

  // =======================================================================
  // HG1 Round 5 micro-pass (Item 1 — the 1024px sticky-header/inspector overlap).
  // `--sticky-header-clearance` is DERIVED from the header's own measured height,
  // not a breakpoint-specific guess — see tokens.css's own comment on the
  // property for why a second guessed constant (this pass's brief explicitly
  // warned against simply swapping 96px for 171px) would only move the same
  // failure to a new number instead of fixing its cause. `getBoundingClientRect()
  // .height` reads the actual rendered box (sub-pixel, includes borders — the
  // same geometry `position: sticky`'s own layout math uses), not the
  // integer-rounded `offsetHeight`; the acceptance criterion is 0px overlap, not
  // "close enough," so the measurement itself must not introduce its own
  // rounding error.
  //
  // HG1 Round 5 SECOND micro-pass (Defect 1 — the first pass's own mechanism
  // going stale on a bare viewport resize; reviews/gates/
  // HG1_ROUND5_MICROPASS_VERIFICATION.md §1). Two independent faults, fixed
  // together below because both live at this same seam:
  //
  // 1a — the property never corrected on a resize that crossed a wrap
  // breakpoint with no other state change (`observerFired: false`, per that
  // verification). Diagnosed against every hypothesis the brief named:
  // `header.app-header` is static markup in index.html, never replaced or
  // recreated by any render in this app (confirmed by reading every call
  // site — no surface, no route render, ever touches this element), so
  // "observing a node a later render replaces" and "watching a now-detached
  // element" are BOTH ruled out; the observer is created exactly once and is
  // never disconnected or recreated (the old `if (_headerResizeObserver...)
  // return` guard fired at most once, ever), so that is also ruled out. What
  // could not be ruled out by reading the code alone, and is reported as such
  // rather than assumed: this environment has no browser or JS runtime, so
  // whether the shipped `ResizeObserver` instance itself actually failed to
  // fire on a real cross-breakpoint resize (versus firing but racing something
  // else) could not be independently reproduced here. Rather than bet the fix
  // on one guessed hypothesis, this pass removes the single point of failure
  // itself: a `window` `resize` event fires on every viewport-width change
  // unconditionally, independent of which element or which CSS box a
  // ResizeObserver happens to be watching, and is layered on top of — not
  // instead of — the ResizeObserver, which remains primary. The observer is
  // also now given an EXPLICIT `border-box` observation, matching exactly what
  // `measureHeaderClearance` reads and writes (`getBoundingClientRect()`'s
  // border-box height), rather than the implicit default `content-box`, which
  // excludes padding/border and so watches a slightly different box than the
  // one actually measured.
  //
  // 1b — the measurement itself ran SYNCHRONOUSLY inside `renderGlobalHeader`,
  // reading the header's box before the browser had resolved the layout that
  // render just triggered (measured: a forced re-measure at 1512/English
  // recorded 95.75px while the header settled at 122px — JS execution and
  // layout do not interleave statement-by-statement, so a synchronous read
  // immediately after a DOM/text change can observe the PREVIOUS box). FIX:
  // every trigger below now funnels through `scheduleHeaderRemeasure`, which
  // defers the actual read one `requestAnimationFrame` — after the browser has
  // completed layout for whatever just changed — instead of any call site
  // reading the box mid-render.
  // =======================================================================
  var _headerEl = null;
  var _headerResizeObserver = null;
  var _headerRemeasureScheduled = false;
  var _windowResizeHeaderListenerInstalled = false;
  function measureHeaderClearance() {
    if (!_headerEl) _headerEl = document.querySelector("header.app-header");
    if (!_headerEl) return;
    var h = _headerEl.getBoundingClientRect().height;
    // A zero/negative height means the header has not actually been laid out yet
    // (e.g. called before the element exists) — never overwrite a previously
    // good value with a bogus one.
    if (h > 0) {
      document.documentElement.style.setProperty("--sticky-header-clearance", h + "px");
    }
  }
  // The single scheduling seam every trigger below goes through, rather than
  // any one of them calling `measureHeaderClearance()` directly (Defect 1b).
  // Coalesced with a boolean flag so multiple triggers landing in the same
  // tick — a resize that fires BOTH the `window` `resize` event and a
  // ResizeObserver notification, or a render that changes several header
  // children at once — produce exactly one deferred measurement, not one per
  // trigger.
  function scheduleHeaderRemeasure() {
    if (_headerRemeasureScheduled) return;
    _headerRemeasureScheduled = true;
    requestAnimationFrame(function () {
      _headerRemeasureScheduled = false;
      measureHeaderClearance();
    });
  }
  // Installed once, self-correcting for every cause of a header-height change
  // this pass's brief names — English vs. 简体中文 content width, wrapping at a
  // narrow breakpoint, browser zoom (a CSS-px layout change, not merely a visual
  // one), and any future header edit — because none of those causes needs its
  // own call site: whatever changes the header's rendered box size fires this
  // observer, unconditionally, including window-resize-driven wraps that never
  // call renderGlobalHeader() at all. Guarded for an environment with no global
  // `ResizeObserver` — never let a missing global throw and abort this IIFE, the
  // same discipline this file's own namespace-initialization fix (top of file)
  // exists to enforce elsewhere.
  //
  // SECOND micro-pass addition (Defect 1a): an explicit `{ box: "border-box" }`
  // observation, with a fallback to the default observation for an engine that
  // supports `ResizeObserver` but throws on the options argument, plus the
  // belt-and-suspenders `window` `resize` listener — a second, INDEPENDENT
  // trigger for the exact same `scheduleHeaderRemeasure` seam, not a second
  // measurement mechanism, so the two paths can never disagree about the
  // header's current height. Re-runnable on every `renderGlobalHeader()` call
  // (idempotent — both installs guard themselves), unlike the old version which
  // could only ever install once.
  function installHeaderResizeObserver() {
    if (!_headerEl) _headerEl = document.querySelector("header.app-header");
    if (!_headerEl) return;
    if (!_headerResizeObserver && typeof ResizeObserver !== "undefined") {
      _headerResizeObserver = new ResizeObserver(function () { scheduleHeaderRemeasure(); });
      try {
        _headerResizeObserver.observe(_headerEl, { box: "border-box" });
      } catch (e) {
        _headerResizeObserver.observe(_headerEl);
      }
    }
    if (!_windowResizeHeaderListenerInstalled) {
      _windowResizeHeaderListenerInstalled = true;
      window.addEventListener("resize", scheduleHeaderRemeasure);
    }
  }

  // HG1 Round 5 SECOND micro-pass — regression check for the exact defect this
  // block exists to close: a header-height change on a bare resize must reach
  // `--sticky-header-clearance`, not merely on the next `renderGlobalHeader()`
  // call. A SEPARATE check from `APP.uicheck.run()`/`.selfTest()` above (surface
  // inline-content differentiation — a different subject; kept apart for the
  // same reason that block gives) and, unlike every synchronous mutation
  // self-test in this file, necessarily ASYNC: the fix this check guards is
  // itself asynchronous (`scheduleHeaderRemeasure`'s `requestAnimationFrame`),
  // so a synchronous assertion cannot observe it. Forces the header TALLER by a
  // known amount via a direct inline `min-height` on the observed element —
  // mechanically the same shape of change a real viewport-crossing-a-wrap-
  // breakpoint resize produces (the header's own rendered border-box height
  // changes) — then dispatches a real `resize` event on `window` (the
  // production entry point the belt-and-suspenders listener above itself
  // listens for) and waits one animation frame, matching
  // `scheduleHeaderRemeasure`'s own single `rAF`, before reading the result.
  //
  // NOT executed by this designer — no browser/JS runtime is available in this
  // environment (see this pass's own report). Written to the same standard as
  // every other check in this file and structurally exercises the exact
  // production code path (the real `installHeaderResizeObserver` listener, the
  // real `scheduleHeaderRemeasure` scheduler), but its actual pass/fail result
  // in a live browser is unverified by me; the PM's dynamic resize sequence is
  // the verification this was written for.
  APP.uicheck.checkHeaderClearanceAfterResize = function checkHeaderClearanceAfterResize(done) {
    if (!_headerEl) _headerEl = document.querySelector("header.app-header");
    if (!_headerEl) { done({ skipped: true, reason: "header.app-header not found" }); return; }
    var originalMinHeight = _headerEl.style.minHeight;
    var beforeHeight = _headerEl.getBoundingClientRect().height;
    _headerEl.style.minHeight = (beforeHeight + 40) + "px";
    window.dispatchEvent(new Event("resize"));
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        var forcedHeight = _headerEl.getBoundingClientRect().height;
        var clearance = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--sticky-header-clearance"));
        var pass = !isNaN(clearance) && Math.abs(clearance - forcedHeight) < 1;
        // Restore, and let the same pipeline settle back to the ORIGINAL
        // height, so this check does not leave the live page permanently
        // taller nor the property pointed at the forced value.
        _headerEl.style.minHeight = originalMinHeight;
        window.dispatchEvent(new Event("resize"));
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            done({
              beforeHeight: beforeHeight, forcedHeight: forcedHeight,
              clearanceAfterForcedResize: clearance, pass: pass,
              restoredHeight: _headerEl.getBoundingClientRect().height,
              restoredClearance: getComputedStyle(document.documentElement).getPropertyValue("--sticky-header-clearance").trim()
            });
          });
        });
      });
    });
  };

  // Mutation self-test, same discipline as every other check in this file
  // (prove the check FAILS under the exact defect it exists to catch, then
  // restore and prove it passes again) — the async equivalent of
  // `APP.uicheck.selfTest`'s before/during/after shape above, chained through
  // callbacks instead of returned synchronously. The injection point is
  // `measureHeaderClearance` itself — reassigned (a function DECLARATION binds
  // a mutable identifier in this closure, same as `var`) to a no-op that still
  // lets `scheduleHeaderRemeasure`'s `rAF` run and still lets the `resize`
  // event fire and be received, but never writes the property — reproducing
  // Defect 1a's observable symptom exactly: the trigger fires, the value does
  // not update. Also unverified in a live browser, for the same reason noted
  // on `checkHeaderClearanceAfterResize` above.
  APP.uicheck.selfTestHeaderClearance = function selfTestHeaderClearance(done) {
    APP.uicheck.checkHeaderClearanceAfterResize(function (before) {
      var originalMeasure = measureHeaderClearance;
      measureHeaderClearance = function () {};
      APP.uicheck.checkHeaderClearanceAfterResize(function (during) {
        measureHeaderClearance = originalMeasure;
        APP.uicheck.checkHeaderClearanceAfterResize(function (after) {
          done({
            name: "sticky-header-clearance tracks a post-boot resize",
            beforeInjection: before, duringInjection: during, afterRestore: after,
            provenToFail: before.pass === true && during.pass === false && after.pass === true
          });
        });
      });
    });
  };

  // ---------------------------------------------------------------------
  // Global header: freshness summary + persistent "Ask" affordance.
  // ---------------------------------------------------------------------
  function renderGlobalHeader() {
    var freshMount = document.getElementById("app-freshness-global");
    if (freshMount && APP.data && APP.data.getFreshness) {
      APP.ui.renderFreshnessStrip(freshMount, APP.data.getFreshness());
    }
    renderExplanationModeControl();
    var askBtn = document.getElementById("app-ai-ask");
    if (askBtn) {
      askBtn.textContent = APP.i18n.t("common.askPortfolio");
      if (!askBtn._wired) {
        askBtn._wired = true;
        askBtn.addEventListener("click", function () {
          APP.ui.openAI({ label: APP.i18n.t("common.askPortfolio"), contextLabel: "global" });
        });
      }
    }
    // Accessibility + i18n: the three overlay close buttons carry a static English
    // aria-label in index.html (a real, wired-once markup attribute, not something a
    // language switch can reach on its own) — kept in sync here, on every header
    // (re-)render, which already runs once at boot and again after every language
    // switch (APP.i18n.setLang).
    ["app-evidence-overlay-close", "app-ai-overlay-close", "app-settings-overlay-close"].forEach(function (id) {
      var btn = document.getElementById(id);
      if (btn) btn.setAttribute("aria-label", APP.i18n.t("common.close"));
    });
    localizeStaticChrome();
    // HG1 Round 5 SECOND micro-pass (Defect 1b correction) — no longer measured
    // synchronously here. `installHeaderResizeObserver()` (idempotent — safe to
    // call on every render) guarantees the ResizeObserver + window-resize-listener
    // pair is live, and `scheduleHeaderRemeasure()` defers the actual read one
    // `requestAnimationFrame` so it runs AFTER this render's own layout (freshness
    // strip, explanation-mode control, "Ask" button text, any language-driven
    // width change) has settled, rather than reading the box mid-render as the
    // previous pass did — the exact cause of the 95.75px-recorded-while-122px-
    // settled discrepancy this pass fixes. Both installs and both triggers are
    // idempotent/coalesced, so calling this on every render (boot, language
    // switch, explanation-mode change) is safe and produces at most one
    // measurement per animation frame.
    installHeaderResizeObserver();
    scheduleHeaderRemeasure();
  }

  // HG1 Round 5, Phase 2 correction pass — Blocker 3 ("finish UI localization"; the
  // measured residual's own §2 named this class of gap explicitly: "persistent
  // overlay chrome present on every route" — Evidence & Methodology, Methodology &
  // Evidence Registry, AI Analyst, Settings / Policy). All five elements below are
  // static markup in index.html (title/aria-label attributes and `<strong>` text
  // nodes that a CSS-only or attribute-only fix cannot reach) — this is the exact
  // same pattern the three overlay close buttons already used above, extended to
  // every other piece of always-visible chrome index.html renders outside any
  // registered surface. Called from renderGlobalHeader(), which already runs once
  // at boot and again on every APP.i18n.setLang() — no new call site needed. Reuses
  // three keys another surface already established (common.evidenceMethodology,
  // evidence.registryTitle, settings.title) rather than forking a second name for
  // the same concept (PD-0014 §2.5) — only `ai.analystTitle` is new, because no
  // existing key named this overlay.
  function localizeStaticChrome() {
    var settingsBtn = document.getElementById("app-settings-btn");
    if (settingsBtn) {
      var settingsTitle = APP.i18n.t("settings.title");
      settingsBtn.title = settingsTitle;
      settingsBtn.setAttribute("aria-label", settingsTitle);
    }
    var methodologyLink = document.getElementById("app-footer-methodology-link");
    if (methodologyLink) methodologyLink.textContent = APP.i18n.t("evidence.registryTitle");
    // HG1 Round 5 SECOND micro-pass (Defect 3) — the footer's own lowercase
    // synthetic-data sentence, present on all five routes (see index.html's own
    // comment on this element for why it is distinct from the banner category).
    var footerNote = document.getElementById("app-footer-synthetic-note");
    if (footerNote) footerNote.textContent = APP.i18n.t("common.syntheticFooterNote");

    var evidenceOverlay = document.getElementById("app-evidence-overlay");
    var evidenceTitle = document.getElementById("app-evidence-overlay-title");
    if (evidenceOverlay) evidenceOverlay.setAttribute("aria-label", APP.i18n.t("common.evidenceMethodology"));
    if (evidenceTitle) evidenceTitle.textContent = APP.i18n.t("common.evidenceMethodology");

    var aiOverlay = document.getElementById("app-ai-overlay");
    var aiTitle = document.getElementById("app-ai-overlay-title");
    if (aiOverlay) aiOverlay.setAttribute("aria-label", APP.i18n.t("ai.analystTitle"));
    if (aiTitle) aiTitle.textContent = APP.i18n.t("ai.analystTitle");

    var settingsOverlay = document.getElementById("app-settings-overlay");
    var settingsOverlayTitle = document.getElementById("app-settings-overlay-title");
    if (settingsOverlay) settingsOverlay.setAttribute("aria-label", APP.i18n.t("settings.title"));
    if (settingsOverlayTitle) settingsOverlayTitle.textContent = APP.i18n.t("settings.title");
  }

  // ---------------------------------------------------------------------
  // Small utilities
  // ---------------------------------------------------------------------
  function textNode(tag, className, text) {
    var el = document.createElement(tag);
    el.className = className;
    el.textContent = text;
    return el;
  }
  function escapeHTML(str) {
    return String(str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function escapeAttr(str) { return escapeHTML(str); }

  // Polyfill closest() lookup used above is native in all evergreen browsers; no
  // shim added deliberately (zero dependency, and Element.prototype.closest has
  // been standard since 2015 — acceptable for an HG1 review prototype).

  // =======================================================================
  // Stage-5 testability seam (ADR-0031 Stage 4 — browser_interaction recorded
  // DEGRADED: Claude-in-Chrome cannot operate the native OS-level <select> at
  // openSettings() above, so a delegated browser-based reviewer cannot reach the
  // Chinese UI through the only visible language control). This does NOT add a
  // second visible control or a second translation system — it is one more INPUT
  // into the same setLangQuiet/_lang state the native <select> already writes to.
  //
  // Reads location.search ONLY, never location.hash: APP.navigateTo() (above)
  // rewrites location.hash wholesale on every route change (`location.hash = "#/" +
  // clean`), and parseHash() never reads location.search either — so a hash-borne
  // locale would be silently dropped on the first nav click, and a search-borne one
  // survives every hash-route navigation untouched. Confirmed by reading both
  // functions; neither one touches location.search.
  //
  // Normalizes case-insensitively: en/en-US -> "en", zh/zh-CN/zh-Hans -> "zh";
  // absent, empty, or anything else -> null ("no override" — caller leaves _lang at
  // its existing default). Never throws on malformed input.
  // =======================================================================
  function normalizeUrlLocale(search) {
    try {
      var s = String(search || "");
      var m = /[?&]lang=([^&]*)/i.exec(s);
      if (!m) return null;
      var raw = decodeURIComponent(m[1] || "").trim().toLowerCase();
      if (raw === "en" || raw === "en-us") return "en";
      if (raw === "zh" || raw === "zh-cn" || raw === "zh-hans") return "zh";
      return null;
    } catch (e) {
      return null;
    }
  }

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------
  var _booted = false;
  function boot() {
    _booted = true;
    // Stage-5 testability seam — applied BEFORE the first render (and before
    // renderGlobalHeader/renderRoute below) so the header, nav and the very first
    // route paint in the URL-derived language rather than flashing English first.
    // Goes through setLangQuiet — the SAME function the native <select>'s change
    // handler reaches via APP.i18n.setLang — so this is the existing localization
    // state path, not a parallel one; setLangQuiet itself never renders (that is
    // exactly why it is safe to call here, before renderGlobalHeader/renderRoute
    // below run for the first time). Absent/unrecognized ?lang= returns null and
    // _lang stays at its line-62 default ("en"), untouched.
    var urlLocale = normalizeUrlLocale(location.search);
    if (urlLocale !== null) setLangQuiet(urlLocale);
    // Default gain/loss color convention body class — PD-0012 §4's default
    // (green-up/red-down) needs no class; only the "cn" convention adds one, applied
    // here in case a future session-restore ever initializes _colorConvention to "cn".
    document.body.classList.toggle("color-convention-cn", _colorConvention === "cn");
    renderGlobalHeader();
    renderRoute();
  }
  window.addEventListener("hashchange", renderRoute);
  document.addEventListener("DOMContentLoaded", boot);
})();
