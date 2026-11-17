/*
 * scenario.js — Scenario Lab surface (D1 surface 7).
 * Owned by designer-13 (phase 2). Registers key "scenario", group "scenario".
 *
 * The single non-negotiable this file exists to prove: a SCENARIO value must never be
 * visually confusable with a holding. Every hypothetical number on this screen is wrapped
 * through APP.ui.renderMetricValue (never a hand-rolled if/else on sufficiency) and is
 * preceded by APP.ui.renderActualScenarioBadge("SCENARIO") at the point of render — not
 * once at the top of the page, but at every comparison row/column, so a reader scrolled to
 * any single row still sees the marker (per designs/FEATURE_DESIGN.md's cross-cutting P8
 * note: "attached at the claim level, not the page level").
 *
 * I could not execute or render this file. No browser or JS runtime exists in this
 * sandbox — see my handback for exactly what that means was/was not verified.
 */
(function () {
  "use strict";
  window.APP = window.APP || {};
  var APP = window.APP;

  // ---------------------------------------------------------------------
  // Which exposure dimension each scenario's `comparison.allocation` field
  // represents. data.js (designer-09, phase 1) does not name this on the
  // scenario object itself — this mapping is inferred by reading how each
  // scenario's allocation array was actually constructed in data.js. Flagged
  // in the handback as a gap: a `dimension` field on the scenario object
  // would remove the need for this inference in a future revision.
  // ---------------------------------------------------------------------
  var ALLOCATION_DIMENSION_BY_SCENARIO = {
    "scenario.reduceCnExposure": "economicGeography",
    "scenario.addTreasuryCash": "assetClass",
    "scenario.shiftHkToUs": "listingMarket"
  };

  // HG1 round-4 §9.2 — "several scenario presets contain hidden ambiguity... define
  // each precisely in the UI." js/data.js's own `modifications` field already carries
  // real disambiguating detail (target dimension, from/to sleeves, amount convention) —
  // it existed, it was just rendered as a raw "key: value" dump (see the old
  // modification-line rendering below) rather than read and stated in prose. This map
  // adds the explicit clarification per scenario id, grounded in what modifications[]
  // actually says for each — never inventing a convention data.js did not already
  // establish.
  var SCENARIO_ACTION_CLARIFICATION = {
    // HG1 Round 5, Phase 2 (I6 — PD-0016 Part 3). The trailing sentence here used to
    // read "NOTE: this scenario's own modeled amount says '-50%', but the computed
    // allocation change below is roughly -15% ... (not something this designer's
    // presentation layer can resolve; see this designer's handoff)" — an internal,
    // first-person build note addressed to another worker, rendered into the product
    // UI. Removed per PD-0016 Part 3: a bounded content deletion, not a redesign of
    // this accepted surface. The underlying -50%/-15% discrepancy is NOT resolved by
    // removing the note — it stays open, recorded in the Round-4 record and the
    // open-items list, and must not be read as closed.
    "scenario.reduceCnExposure": "“Mainland China exposure” here means economic geography, " +
      "restricted to Mainland China (CN)-listed A-shares only — it does NOT include Hong Kong- or " +
      "US-listed securities of Mainland Chinese companies, which also carry “China” as their " +
      "economic geography but are not touched by this scenario. “Reallocating proceeds to cash” " +
      "is modeled at the portfolio level only in this prototype — it does not specify which cash " +
      "bucket/account or which currency receives the proceeds, or whether an FX conversion occurs; " +
      "flagged as a genuine open question, not resolved silently.",
    "scenario.addTreasuryCash": "The added amount is USD 50,000 (TLT trades in USD) — stated explicitly " +
      "here because a multi-currency product should never leave a bare “$” ambiguous between USD, " +
      "HKD, and CNY.",
    "scenario.shiftHkToUs": "“10%” is 10% of the Hong Kong listing-market SLEEVE's own weight " +
      "(i.e. a tenth of whatever the HK sleeve is currently worth), not 10 percentage points of total " +
      "portfolio weight — those are different magnitudes and this scenario uses the former."
  };
  // HG1 Round 5 correction pass (Objective 2). Chinese counterparts for the three
  // clarifications above, keyed identically — this is scenario.js's own local
  // content (like SCENARIO_ACTION_CLARIFICATION itself), not routed through
  // shell.js's shared I18N table, matching that map's own established shape.
  var SCENARIO_ACTION_CLARIFICATION_ZH = {
    "scenario.reduceCnExposure": "此处「中国内地敞口」指经济地理维度,仅限于中国内地(CN)上市的A股——不包括在香港或美国" +
      "上市、但同样以「中国」为经济地理归属的中国内地企业证券,本情景不触及这些持仓。「所得资金转为现金」" +
      "在本原型中仅在投资组合层面建模——并未指明具体由哪个现金账户/币种接收该资金,也未说明是否发生汇率换算;" +
      "已标记为真实存在的开放问题,而非被静默解决。",
    "scenario.addTreasuryCash": "追加金额为5万美元(TLT以美元计价)——在此明确说明,是因为在多币种产品中," +
      "裸露的「$」符号绝不应在美元、港元和人民币之间产生歧义。",
    "scenario.shiftHkToUs": "「10%」指的是香港上市板块自身权重的10%(即当前港股板块价值的十分之一)," +
      "而非投资组合总权重的10个百分点——二者量级不同,本情景采用前者。"
  };

  // HG1 Round 5 micro-pass (Item 3) — the raw `modifications[]` technical
  // readout rendered below (PM-cited example: "action: REDUCE_WEIGHT ·
  // target: ..."). js/data.js's own comment on SCENARIOS[].modifications
  // records this as a deliberate, disclosed, bounded gap from the prior round
  // — "a raw action/target/amount technical readout" — and this pass's own
  // brief asks that it be judged rather than mechanically translated whole.
  // The judgment THEN: `action` values (REDUCE_WEIGHT, ADD_HYPOTHETICAL_
  // INSTRUMENT, SHIFT_EXPOSURE) are this app's established canonical
  // enum-code shape (ALL-CAPS with an underscore — matched by
  // APP.i18n.CANONICAL_CONTENT_ALLOWLIST's canonicalEnumToken pattern) and
  // stay untouched, exactly like TX_TYPES/reasonCode elsewhere; they are
  // read/compared, not read as prose. `target`/`amount`/`from`/`to` VALUES
  // are genuine English prose where they contain English words — translated
  // below. "HK equity"/"US equity" reuse the SAME `ctx.ui.translateSleeveLabel`
  // every other surface already uses for the identical strings (not a
  // second, independently-chosen name for the same concept — PD-0014 §2.5);
  // the two remaining prose fragments (a dimension:value target and a
  // percentage-of-sleeve amount) are translated by exact string, the same
  // shape as SCENARIO_ACTION_CLARIFICATION_ZH immediately above.
  // `amount: "+$50,000"` (scenario.addTreasuryCash) and `target: "TLT"` are
  // pure symbols/a canonical ticker — nothing to translate — and are
  // correctly left as-is by falling through this map.
  //
  // SUPERSEDED IN PART (Post-HG1 Checkpoint A — D3, 2026-09-15, `designer-33`).
  // The owner decision that day reversed the ONE judgment above that named
  // `action` VALUES as intended, exempt, visible content: Stage-0's rendered
  // baseline showed a reader literally the raw token "REDUCE_WEIGHT" on
  // screen, in both locales, which is not "read/compared, not read as
  // prose" once it is the ONLY thing on the line naming what the scenario
  // does. `presentActionValue`/`presentTargetValue`/`presentModificationLine`
  // below now render a human-readable bilingual label for `action` and for
  // any `target` shaped `"<dimension>:<CODE> (<gloss>)"`, while the raw
  // `modifications[]` DATA this map/function reads from (js/data.js) is
  // completely untouched — still the same canonical enum syntax, still
  // available (unchanged) via `data-canonical-action`/`data-canonical-target`
  // on the rendered line. `target`/`amount`/`from`/`to` prose translation via
  // this map is UNCHANGED by this pass; only how `action` (and the one
  // dimension:code-shaped `target`) reach the screen changes.
  var MODIFICATION_VALUE_ZH = {
    "listingMarket:CN (Mainland China A-share sleeve)": "listingMarket:CN(中国内地A股板块)",
    "-50% of the CN-listed sleeve's market value, reallocated to cash": "CN上市板块市值的-50%,转为现金",
    "10% of HK sleeve": "港股板块的10%"
  };
  function translateModificationValue(ctx, key, value) {
    if (ctx.ui.getLang() !== "zh") return value;
    if (key === "from" || key === "to") return ctx.ui.translateSleeveLabel(value);
    return Object.prototype.hasOwnProperty.call(MODIFICATION_VALUE_ZH, value) ? MODIFICATION_VALUE_ZH[value] : value;
  }

  // =========================================================================
  // Post-HG1 Checkpoint A — D3 (designer-33, 2026-09-15). Human-readable
  // bilingual presentation for a modification's `action` code and its
  // `target` value (where shaped "<dimension>:<CODE> (<gloss>)"). The
  // underlying `modifications[]` data (js/data.js) is UNCHANGED by this —
  // this is presentation only. Action labels are new APP.i18n keys
  // ("scenario.action.<CODE>", js/shell.js, both locales) rather than a
  // local map here, matching this file's own established pattern of routing
  // ordinary UI-chrome vocabulary through the shared I18N table
  // (`scenario.modField.*` immediately does the same for the field-key
  // labels). Exposed on APP.scenarioPresentation so js/i18n-selfcheck.js's
  // manual-only regression checks (Stage-0 §8 H4) exercise the SAME function
  // this file renders through, not a second, independently-built copy that
  // could silently drift from what actually reaches the screen.
  // =========================================================================
  var TARGET_PRESENTATION = {
    // Only one target value in this fixture has the "<dimension>:<CODE>
    // (<gloss>)" shape today (scenario.reduceCnExposure's). Composed from
    // the SAME per-dimension/market labels this app already established
    // elsewhere — ctx.ui.translateGeographyLabel("Mainland China") ->
    // "中国内地" (GEOGRAPHY_LABEL_ZH, shell.js); ctx.ui.translateSleeveLabel
    // ("CN") -> "A股" (SLEEVE_LABEL_ZH, shell.js); the dimension label
    // "上市地" is data.js's own SCENARIO_ALLOCATION_DIMENSION_ZH value for
    // this exact dimension, reproduced here as the one other file-local copy
    // that map already requires (data.js's own is a private, unexported
    // var) — one name per concept (PD-0014 §2.5), not a second,
    // independently-chosen one.
    "listingMarket:CN (Mainland China A-share sleeve)": {
      en: "Listing market: Mainland China (CN) — A-share sleeve",
      zh: "上市地:中国内地(CN)——A股板块"
    }
  };
  function presentActionValue(action) {
    var key = "scenario.action." + action;
    var label = window.APP.i18n.t(key);
    // Falls back to the raw code only if the I18N table has no entry for a
    // future action this pass did not name — never silently blank (matches
    // this file's own established "never invent, never silently drop" rule;
    // APP.i18n.t() itself already falls back key-to-key, this just detects
    // that fallback so a caller can tell "no label" from "the label IS the
    // code").
    return (label && label !== key) ? label : action;
  }
  function presentTargetValue(rawValue) {
    var entry = TARGET_PRESENTATION[rawValue];
    if (!entry) return rawValue; // e.g. "TLT" — a canonical ticker/symbol, unchanged in either locale
    return window.APP.i18n.getLang() === "zh" ? entry.zh : entry.en;
  }
  function presentModificationLine(m) {
    return Object.keys(m).map(function (k) {
      var keyLabel = window.APP.ui.t("scenario.modField." + k) || k;
      var value;
      if (k === "action") value = presentActionValue(m[k]);
      else if (k === "target") value = presentTargetValue(m[k]);
      else value = translateModificationValue({ ui: window.APP.ui }, k, m[k]);
      return keyLabel + ": " + value;
    }).join(" · ");
  }
  window.APP.scenarioPresentation = window.APP.scenarioPresentation || {};
  window.APP.scenarioPresentation.presentModificationLine = presentModificationLine;
  window.APP.scenarioPresentation.presentActionValue = presentActionValue;
  window.APP.scenarioPresentation.presentTargetValue = presentTargetValue;

  var METRIC_META = {
    volatility: { label: "Annualized Volatility", unit: "percent", actualId: "metric.volatility", methodologyId: "methodology.volatility" },
    beta: { label: "Beta (vs. Benchmark)", unit: "ratio", actualId: "metric.beta", methodologyId: "methodology.beta" },
    concentration: { label: "Concentration (Top 5)", unit: "percent", actualId: "metric.concentration", methodologyId: "methodology.concentration" },
    sharpe: { label: "Sharpe Ratio", unit: "ratio", actualId: "metric.sharpe", methodologyId: "methodology.sharpe" }
  };

  var currentScenarioId = null;

  // ---------------------------------------------------------------------
  // Build a minimal claim-shaped object for a scenario's SIDE of a
  // current/scenario comparison entry — the same pattern data.js's own
  // CONTRIBUTION_TO_RISK segments already use so APP.ui.renderMetricValue can
  // render them. This does NOT invent a value: `entry.scenario` always comes
  // straight from APP.data.getScenario(id).comparison[key], per CONTRACT.md
  // §3's documented shape ("scenario is USUALLY a plain value... check for a
  // .sufficiency field... render THAT side through renderMetricValue").
  //
  // UPDATE, integration pass (designer-14): this now DELEGATES to the shared,
  // single-source builder in data.js (APP.data.getScenarioComparisonClaim),
  // which this file's sibling ai.js also calls — so both surfaces render the
  // identical object, and evidence.js can resolve a real Proof Packet for it
  // (previously this file's own locally-built object had no EVIDENCE entry
  // behind its id at all, so its own "Evidence" button resolved to nothing —
  // see data.js's "Scenario-comparison claims" section for the fix). The
  // local build below is kept only as a defensive fallback if that accessor
  // is somehow unavailable; it should never be reached in practice given the
  // fixed load order (data.js loads before this file).
  // ---------------------------------------------------------------------
  function scenarioSideClaim(scenarioId, key, entry) {
    var id = scenarioId + "." + key;
    if (APP.data && APP.data.getScenarioComparisonClaim) {
      var shared = APP.data.getScenarioComparisonClaim(id);
      if (shared) return shared;
    }
    var meta = METRIC_META[key];
    var hasSufficiency = entry && Object.prototype.hasOwnProperty.call(entry, "sufficiency");
    return {
      id: id,
      label: meta.label + " (Scenario)",
      unit: meta.unit,
      value: entry ? entry.scenario : null,
      sufficiency: hasSufficiency ? entry.sufficiency : "AVAILABLE",
      reasonCode: hasSufficiency ? (entry.reasonCode || null) : null,
      caveat: hasSufficiency ? (entry.caveat || "") : "",
      stateType: "SCENARIO",
      scenarioId: scenarioId,
      methodologyId: meta.methodologyId
    };
  }

  function evidenceButton(ctx, claimId, label) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "evidence-control evidence-control-sm";
    btn.textContent = label || ctx.ui.t("common.evidence");
    btn.addEventListener("click", function () { ctx.ui.openEvidence(claimId); });
    return btn;
  }

  function badge(ctx, stateType) {
    var span = document.createElement("span");
    ctx.ui.renderActualScenarioBadge(span, stateType);
    return span;
  }

  // One row: label + ACTUAL cell + SCENARIO cell, both through
  // renderMetricValue, both carrying their own badge and Evidence control
  // (designs/FEATURE_DESIGN.md's D1 surface 7 item 5: "Evidence affordance on
  // every metric in the Current-vs-Scenario comparison, on both columns").
  function metricRow(ctx, key, scenario) {
    var meta = METRIC_META[key];
    var row = document.createElement("div");
    row.className = "scenario-compare-row";

    var actualClaim = ctx.data.getMetric(meta.actualId);
    // HG1 Round 5 correction pass (Objective 2 — PD-0012 §3 names "metric names"
    // explicitly). Reads the label from the ACTUAL claim object (now carrying
    // `i18n.zh.label`, this pass's own addition in js/data.js) via the same
    // `localizeClaimField` hook every other surface uses, rather than this file's
    // own separately-typed, English-only `METRIC_META.label` — one source for a
    // metric's display name, not two that could drift apart (PD-0014 §2.5). Falls
    // back to `meta.label` only if the real claim is somehow unavailable.
    var labelEl = document.createElement("div");
    labelEl.className = "scenario-compare-label";
    labelEl.textContent = actualClaim ? ctx.ui.localizeClaimField(actualClaim, "label") : meta.label;
    row.appendChild(labelEl);

    var actualCell = document.createElement("div");
    actualCell.className = "scenario-compare-cell scenario-compare-actual";
    actualCell.appendChild(badge(ctx, "ACTUAL"));
    var actualVal = document.createElement("div");
    actualVal.className = "scenario-compare-value";
    ctx.ui.renderMetricValue(actualVal, actualClaim);
    actualCell.appendChild(actualVal);
    actualCell.appendChild(evidenceButton(ctx, actualClaim.id));
    row.appendChild(actualCell);

    var entry = scenario.comparison[key];
    var scenClaim = scenarioSideClaim(scenario.id, key, entry);
    var scenCell = document.createElement("div");
    scenCell.className = "scenario-compare-cell scenario-compare-scenario";
    scenCell.appendChild(badge(ctx, "SCENARIO"));
    var scenVal = document.createElement("div");
    scenVal.className = "scenario-compare-value";
    ctx.ui.renderMetricValue(scenVal, scenClaim);
    scenCell.appendChild(scenVal);
    scenCell.appendChild(evidenceButton(ctx, scenClaim.id));
    row.appendChild(scenCell);

    return row;
  }

  function blockHeader(text) {
    var header = document.createElement("div");
    header.className = "block-header";
    var kicker = document.createElement("span");
    kicker.className = "block-kicker";
    kicker.textContent = text;
    header.appendChild(kicker);
    return header;
  }

  // HG1 round-4 §9.1 — "Actual vs Scenario must clearly show what categories exist,
  // what changed, and the magnitude of change. Unlabeled donut segments are
  // insufficient." Builds a current-vs-scenario delta table matched by segment label —
  // this is also the mechanism that makes a real, independently-discovered data
  // discrepancy self-checkable rather than hidden (see this designer's handoff): the
  // "Reduce Mainland China exposure by half" scenario's own modification amount says
  // "-50%," but the actual computed China segment only drops ~15% (0.85× multiplier) —
  // a genuine PD-0014-class internal-consistency question for data.js/quant_analyst,
  // not something this table silently corrects or hides.
  function allocationDeltaTable(ctx, currentSegs, scenarioSegs) {
    var byLabel = {};
    (currentSegs || []).forEach(function (s) { byLabel[s.label] = { label: s.label, current: s.pct }; });
    (scenarioSegs || []).forEach(function (s) {
      byLabel[s.label] = byLabel[s.label] || { label: s.label, current: null };
      byLabel[s.label].scenario = s.pct;
    });
    var rows = Object.keys(byLabel).map(function (k) { return byLabel[k]; });
    var table = document.createElement("table");
    table.className = "scenario-delta-table";
    var thead = document.createElement("thead");
    var hr = document.createElement("tr");
    [ctx.ui.t("scenario.colSegment"), ctx.ui.t("scenario.colCurrent"), ctx.ui.t("scenario.colScenario"), ctx.ui.t("scenario.colChange")].forEach(function (h, i) {
      var th = document.createElement("th");
      th.textContent = h;
      if (i > 0) th.className = "num";
      th.setAttribute("scope", "col");
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    var tbody = document.createElement("tbody");
    rows.forEach(function (r) {
      var tr = document.createElement("tr");
      var labelTd = document.createElement("td");
      labelTd.className = "scenario-delta-label";
      labelTd.textContent = r.label;
      tr.appendChild(labelTd);
      var curTd = document.createElement("td");
      curTd.className = "num";
      curTd.textContent = r.current != null ? (r.current * 100).toFixed(1) + "%" : "—";
      tr.appendChild(curTd);
      var scenTd = document.createElement("td");
      scenTd.className = "num";
      scenTd.textContent = r.scenario != null ? (r.scenario * 100).toFixed(1) + "%" : "—";
      tr.appendChild(scenTd);
      var deltaTd = document.createElement("td");
      deltaTd.className = "num";
      if (r.current != null && r.scenario != null) {
        var delta = (r.scenario - r.current) * 100;
        deltaTd.textContent = (delta >= 0 ? "+" : "") + delta.toFixed(1) + " pp";
        // classList.add("") throws in a real browser — only add a class when the sign is
        // genuinely non-zero, never an empty string for the flat (no-change) case.
        if (delta > 0) deltaTd.classList.add("metric-positive");
        else if (delta < 0) deltaTd.classList.add("metric-negative");
      } else {
        deltaTd.textContent = "—";
      }
      tr.appendChild(deltaTd);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  // HG1 Round 5 correction pass (Objective 2). The three allocation dimensions this
  // file's own donuts render (`economicGeography`/`assetClass`/`listingMarket`) are
  // the SAME three dimensions Overview/Analytics already translate via shell.js's
  // established per-dimension maps — reused here rather than a fourth, invented
  // translation, and picked by the SAME `ALLOCATION_DIMENSION_BY_SCENARIO` lookup
  // this file already uses to resolve the Evidence id for each donut. A dimension
  // this map does not name (defensive default) passes segments through unchanged,
  // matching this file's own established "never invent a translation" discipline.
  function translateAllocationSegments(ctx, dimension, segments) {
    var translateFn = dimension === "economicGeography" ? ctx.ui.translateGeographyLabel
      : dimension === "listingMarket" ? ctx.ui.translateSleeveLabel
      : dimension === "assetClass" ? ctx.ui.translateTaxonomyLabel
      : null;
    if (!translateFn) return segments;
    return (segments || []).map(function (s) { return Object.assign({}, s, { label: translateFn(s.label) }); });
  }

  function allocationBlock(ctx, scenario) {
    var dimension = ALLOCATION_DIMENSION_BY_SCENARIO[scenario.id] || "assetClass";
    var block = document.createElement("div");
    block.className = "block scenario-allocation-block";
    block.appendChild(blockHeader(ctx.ui.t("scenario.allocationHeader")));

    var row = document.createElement("div");
    row.className = "scenario-allocation-row";

    var actualSegsDisplay = translateAllocationSegments(ctx, dimension, scenario.comparison.allocation.current);
    var scenSegsDisplay = translateAllocationSegments(ctx, dimension, scenario.comparison.allocation.scenario);

    var actualCol = document.createElement("div");
    actualCol.className = "scenario-allocation-col scenario-allocation-actual";
    actualCol.appendChild(badge(ctx, "ACTUAL"));
    var actualChart = document.createElement("div");
    actualChart.className = "scenario-allocation-chart";
    actualChart.appendChild(ctx.charts.donut({ segments: actualSegsDisplay, centerLabel: ctx.ui.t("scenario.centerActual") }));
    actualCol.appendChild(actualChart);
    // HG1 round-4 §9.1/§4.1 — "Scenario Lab donut charts lack sufficient labels" (round-4
    // visual defect #8). A real, textual legend (label + swatch + share) beside each
    // donut, not just an unlabeled ring — the same shared primitive Overview's asset-mix
    // donut now also uses (js/shell.js's APP.ui.renderDonutLegend), so this is one fix
    // applied everywhere a donut appears, not a one-off patch here.
    ctx.ui.renderDonutLegend(actualCol, actualSegsDisplay);
    var actualExposureClaim = ctx.data.getExposure(dimension).claim;
    actualCol.appendChild(evidenceButton(ctx, actualExposureClaim.id));
    row.appendChild(actualCol);

    var scenCol = document.createElement("div");
    scenCol.className = "scenario-allocation-col scenario-allocation-scenario";
    scenCol.appendChild(badge(ctx, "SCENARIO"));
    var scenChart = document.createElement("div");
    scenChart.className = "scenario-allocation-chart";
    scenChart.appendChild(ctx.charts.donut({ segments: scenSegsDisplay, centerLabel: ctx.ui.t("scenario.centerScenario") }));
    scenCol.appendChild(scenChart);
    ctx.ui.renderDonutLegend(scenCol, scenSegsDisplay);
    var scenAllocId = scenario.id + ".allocation." + dimension;
    scenCol.appendChild(evidenceButton(ctx, scenAllocId));
    row.appendChild(scenCol);

    block.appendChild(row);

    // §9.1's "and/or delta table" — a paired-comparison table naming every segment,
    // its current share, its scenario share, and the signed change in percentage
    // points, matched by segment label across both donuts above. Matched on the
    // (now-translated) DISPLAY label deliberately: both sides of any one row must
    // already be the same string to match at all, and translating both sides via
    // the identical dimension map above keeps that true in either language.
    var deltaKicker = document.createElement("div");
    deltaKicker.className = "block-kicker";
    deltaKicker.style.marginTop = "var(--space-4)";
    deltaKicker.textContent = ctx.ui.t("scenario.deltaHeader");
    block.appendChild(deltaKicker);
    block.appendChild(allocationDeltaTable(ctx, actualSegsDisplay, scenSegsDisplay));

    return block;
  }

  function paint(mountEl, ctx) {
    mountEl.innerHTML = "";
    var scenarios = ctx.data.getScenarios();
    if (!currentScenarioId || !scenarios.some(function (s) { return s.id === currentScenarioId; })) {
      currentScenarioId = scenarios.length ? scenarios[0].id : null;
    }
    var scenario = currentScenarioId ? ctx.data.getScenario(currentScenarioId) : null;

    var page = document.createElement("div");
    page.className = "scenario-lab-page";

    // ---- Intro / legend — the vocabulary a reader needs before the numbers ----
    var intro = document.createElement("div");
    intro.className = "block scenario-lab-intro";
    intro.appendChild(blockHeader(ctx.ui.t("scenario.title")));
    var introText = document.createElement("p");
    introText.textContent = ctx.ui.t("scenario.introText");
    intro.appendChild(introText);
    var legend = document.createElement("div");
    legend.className = "scenario-legend";
    legend.appendChild(badge(ctx, "ACTUAL"));
    var legendActualText = document.createElement("span");
    legendActualText.className = "scenario-legend-text";
    legendActualText.textContent = ctx.ui.t("scenario.actualLegend");
    legend.appendChild(legendActualText);
    legend.appendChild(badge(ctx, "SCENARIO"));
    var legendScenarioText = document.createElement("span");
    legendScenarioText.className = "scenario-legend-text";
    legendScenarioText.textContent = ctx.ui.t("scenario.scenarioLegend");
    legend.appendChild(legendScenarioText);
    intro.appendChild(legend);
    // HG1 round-4 §9.3 — "scenario outputs must not look like forecasts." Every
    // volatility/beta/concentration/Sharpe figure below is a deterministic
    // recalculation of the SAME historical return series under a hypothetical
    // allocation (a historical replay), never a forward-looking prediction — stated
    // once, plainly, here, rather than left for a reader to assume from a confident-
    // looking number (P6).
    var notForecast = document.createElement("p");
    notForecast.className = "claim-caveat";
    notForecast.textContent = ctx.ui.t("scenario.notForecast");
    intro.appendChild(notForecast);
    page.appendChild(intro);

    // ---- Scenario selector ----
    var selector = document.createElement("div");
    selector.className = "scenario-selector";
    scenarios.forEach(function (s) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "scenario-selector-tab" + (s.id === currentScenarioId ? " scenario-selector-tab-active" : "");
      b.textContent = ctx.ui.localizeClaimField(s, "name");
      b.addEventListener("click", function () {
        currentScenarioId = s.id;
        paint(mountEl, ctx);
      });
      selector.appendChild(b);
    });
    page.appendChild(selector);

    if (!scenario) {
      var none = document.createElement("p");
      none.textContent = ctx.ui.t("scenario.noneDefined");
      page.appendChild(none);
      mountEl.appendChild(page);
      return;
    }

    // ---- Scenario description, modifications, warnings ----
    var desc = document.createElement("div");
    desc.className = "block scenario-description-block";
    desc.appendChild(blockHeader(ctx.ui.localizeClaimField(scenario, "name")));
    var descText = document.createElement("p");
    descText.textContent = ctx.ui.localizeClaimField(scenario, "description");
    desc.appendChild(descText);
    // HG1 Round 5 correction pass (Objective 2). `scenario.warnings` is now
    // localized via `scenario.i18n.zh.warnings` (js/data.js, this pass) — matched
    // by ARRAY INDEX against the English array (both are always the same single
    // "hypothetical only" sentence today; a future scenario adding a second warning
    // must keep the two arrays the same length and in the same order, same as any
    // other `i18n.{lang}.{field}` pair in this codebase).
    var warningsZh = (scenario.i18n && scenario.i18n.zh && scenario.i18n.zh.warnings) || null;
    (scenario.warnings || []).forEach(function (w, wIdx) {
      var warn = document.createElement("p");
      warn.className = "claim-caveat scenario-warning";
      warn.textContent = (ctx.ui.getLang() === "zh" && warningsZh && warningsZh[wIdx]) ? warningsZh[wIdx] : w;
      desc.appendChild(warn);
    });
    var modHeader = document.createElement("p");
    modHeader.className = "scenario-modifications-label";
    modHeader.textContent = ctx.ui.t("scenario.hypotheticalInputsLabel");
    desc.appendChild(modHeader);
    (scenario.modifications || []).forEach(function (m) {
      var mp = document.createElement("p");
      mp.className = "scenario-modification-line";
      // Post-HG1 Checkpoint A — D3 (designer-33). Field-key LABELS
      // ("action"/"target"/"amount"/"from"/"to") are translated as before;
      // the `action` VALUE and any dimension:code-shaped `target` VALUE now
      // render as human-readable bilingual labels via
      // presentModificationLine (this file, above) instead of the raw
      // machine token — see that function's own comment for what changed
      // and why. The raw canonical values are never deleted: they stay
      // available, unchanged, via `data-canonical-action`/
      // `data-canonical-target` on this same line, for anything that still
      // needs them.
      mp.textContent = presentModificationLine(m);
      if (Object.prototype.hasOwnProperty.call(m, "action")) mp.setAttribute("data-canonical-action", m.action);
      if (Object.prototype.hasOwnProperty.call(m, "target")) mp.setAttribute("data-canonical-target", m.target);
      desc.appendChild(mp);
    });
    // HG1 round-4 §9.2 — precise disambiguation of what this specific preset's action
    // actually refers to (dimension, sleeve-vs-total magnitude, currency, cash
    // destination) — see SCENARIO_ACTION_CLARIFICATION's own comment for exactly what
    // each clarification is grounded in.
    var clarification = (ctx.ui.getLang() === "zh" && SCENARIO_ACTION_CLARIFICATION_ZH[scenario.id]) ||
      SCENARIO_ACTION_CLARIFICATION[scenario.id];
    if (clarification) {
      var clarBlock = document.createElement("p");
      clarBlock.className = "claim-investor-detail";
      clarBlock.textContent = clarification;
      desc.appendChild(clarBlock);
    }
    page.appendChild(desc);

    // ---- Four representative comparisons ----
    page.appendChild(allocationBlock(ctx, scenario));

    var riskBlock = document.createElement("div");
    riskBlock.className = "block scenario-risk-block";
    riskBlock.appendChild(blockHeader(ctx.ui.t("scenario.riskHeader")));
    riskBlock.appendChild(metricRow(ctx, "volatility", scenario));
    riskBlock.appendChild(metricRow(ctx, "beta", scenario));
    page.appendChild(riskBlock);

    var concBlock = document.createElement("div");
    concBlock.className = "block scenario-concentration-block";
    concBlock.appendChild(blockHeader(ctx.ui.t("scenario.concentrationHeader")));
    concBlock.appendChild(metricRow(ctx, "concentration", scenario));
    page.appendChild(concBlock);

    var metricBlock = document.createElement("div");
    metricBlock.className = "block scenario-metric-block";
    metricBlock.appendChild(blockHeader(ctx.ui.t("scenario.metricHeader")));
    metricBlock.appendChild(metricRow(ctx, "sharpe", scenario));

    // Representative demonstration that D2's depth ladder applies identically
    // inside Scenario Lab (designs/FEATURE_DESIGN.md §D2 [J]) — shown for the
    // ACTUAL side, since data.js's scenario comparison entries carry only
    // {current, scenario[, sufficiency, reasonCode, caveat]}, not the
    // conclusionQuick/explanationSimple/professionalDetail fields a full
    // ladder needs; fabricating that narrative text for the SCENARIO side
    // would be inventing claim content data.js doesn't provide. Flagged in
    // the handback rather than papered over.
    var expandBtn = document.createElement("button");
    expandBtn.type = "button";
    expandBtn.className = "scenario-expand-actual";
    expandBtn.textContent = ctx.ui.t("scenario.exploreFullDetailBtn");
    var expandMount = document.createElement("div");
    expandMount.className = "scenario-expand-mount";
    expandMount.style.display = "none";
    var expanded = false;
    expandBtn.addEventListener("click", function () {
      expanded = !expanded;
      expandMount.style.display = expanded ? "" : "none";
      if (expanded) {
        ctx.ui.renderClaim(expandMount, ctx.data.getMetric("metric.sharpe"), { depth: "quick" });
      }
    });
    metricBlock.appendChild(expandBtn);
    metricBlock.appendChild(expandMount);
    page.appendChild(metricBlock);

    // ---- Contextual AI, never a top-level destination ----
    var aiMount = document.createElement("div");
    aiMount.className = "scenario-ai-affordance";
    ctx.ui.aiAffordance(aiMount, {
      label: ctx.ui.t("scenario.askAboutScenario"),
      contextLabel: "scenario:" + scenario.id,
      scenarioId: scenario.id,
      contextClaims: ["metric.volatility", "metric.beta", "metric.concentration", "metric.sharpe"]
    });
    page.appendChild(aiMount);

    mountEl.appendChild(page);
  }

  window.APP.registerSurface("scenario", {
    group: "scenario",
    render: function (mountEl, ctx) { paint(mountEl, ctx); }
  });
})();
