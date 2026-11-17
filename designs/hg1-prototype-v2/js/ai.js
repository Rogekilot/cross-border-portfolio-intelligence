/*
 * ai.js — AI Analyst (D1 surface 8).
 * Owned by designer-13 (phase 2, cold-started worker). Calls APP.registerAI(handler).
 *
 * Responses in this file are SIMULATED: canned, deterministic, assembled entirely from
 * APP.data accessors. No model call exists anywhere in this file and none is invoked.
 *
 * The one non-negotiable this file exists to prove (P1, and Direction C's own author's
 * "highest structural risk" naming, designs/hg1-revision/direction-c/DIRECTION.md §4):
 * AI narrative must never become the source of a portfolio number, label, classification,
 * or other deterministic fact. The mechanism: every numeral inside a `.ai-narrative`-classed
 * block is produced by APP.ui.chipHTML(claim) — never string-concatenated by hand — and
 * `APP.ui.checkNarrativeSafety` is called after every render as the dev-time self-check
 * CONTRACT.md §6A names. Plain connective words are the only hand-authored text inside
 * those blocks; every claim-bearing figure comes from an APP.data accessor (never invented
 * here), per PD-0008's exact test: "does the number assert something about the portfolio
 * that could be false?" — if yes, it goes through a chip; if it only selects/orders
 * ("your largest holdings," "top 5 holdings"), it is left as plain text.
 *
 * UPDATE, integration pass (designer-14): this file's original author avoided literal
 * digits in selector phrases entirely, because the mechanical checkNarrativeSafety scanner
 * could not distinguish a selector digit from a claim digit and would fire a false
 * positive — flagged in the handback rather than worked around silently. The scanner has
 * since been improved (shell.js's APP.ui.selectorHTML + the refined checkNarrativeSafety,
 * see CONTRACT.md §6A): a selector digit is now wrapped in an explicit, auditable
 * `.numeral-selector` span rather than avoided, and the scanner excludes both `.chip` and
 * `.numeral-selector` content before flagging a stray digit. See the "exposures" template
 * below for the worked example ("top 5 holdings").
 *
 * A caveat belonging to a cited claim (P3) is rendered via the SAME `.claim-caveat`/
 * freshness-pill components every other surface uses, adjacent to but outside the
 * `.ai-narrative` block itself — not folded into hand-authored prose. This is deliberate:
 * a caveat's own wording legitimately contains digits (e.g. beta's "24 monthly-equivalent
 * observations"), and that text is already deterministic, vetted, D3.2-governed content, not
 * AI-typed narrative — running it back through checkNarrativeSafety by pasting it into
 * `.ai-narrative` text would only produce a false-positive warning for content that already
 * has its own correct rendering rule. See the handback for the full reasoning.
 *
 * I could not execute or render this file. No browser or JS runtime exists in this sandbox.
 * See the handback for exactly what that means was/was not verified.
 *
 * HG1 ROUND 5 CORRECTION PASS (designer, this pass) — Objective 2. Standalone strings
 * (follow-up template labels, the "Contextual question:"/no-scenario/not-available
 * messages, evidenceRow's "Evidence: " prefix, factClaim labels) now route through
 * ctx.ui.t()/tf(). Composed narrative sentences that mix hand-authored prose with a
 * trusted chip fragment ({html: chip(...)}) are now built from SEPARATE translated
 * prefix/suffix parts (never one merged HTML string) so `narrativeP` still routes every
 * plain-text part through `document.createTextNode` exactly as before this pass — no
 * new escaping requirement, and `APP.ui.checkNarrativeSafety`'s chip/numeral-selector
 * stripping is unaffected by which language produced the surrounding text. Metric names
 * inside scenario-comparison sentences now read `i18n.zh.label` off the ACTUAL claim
 * (js/data.js, this pass's own addition) rather than this file's separately-typed
 * SCENARIO_METRIC_META.label, for the same "one source of truth" reason
 * js/surfaces/scenario.js's own metricRow was fixed this same pass.
 */
(function () {
  "use strict";
  window.APP = window.APP || {};
  var APP = window.APP;

  // -----------------------------------------------------------------------
  // Small local helpers (this file does not touch shell.js/data.js's own
  // private helpers — everything below is self-contained).
  // -----------------------------------------------------------------------
  function textNode(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined && text !== null) el.textContent = text;
    return el;
  }

  function claimById(id) {
    return (APP.data && APP.data.getMetric) ? APP.data.getMetric(id) : null;
  }

  function chip(claimOrId, displayText) {
    return APP.ui.chipHTML(claimOrId, displayText);
  }

  // Builds a <p class="ai-narrative"> from a mix of plain strings (inserted as
  // escaped text nodes — never raw innerHTML, so no digit inside a plain
  // string can silently become "safe" by accident) and pre-built trusted HTML
  // fragments (chip markup only, tagged {html: "..."}). This is the ONLY
  // function in this file that constructs `.ai-narrative` content, precisely
  // so there is exactly one place to audit for "does every numeral in here
  // come from a chip."
  function narrativeP(parts) {
    var p = document.createElement("p");
    p.className = "ai-narrative";
    parts.forEach(function (part) {
      if (part === null || part === undefined || part === "") return;
      if (typeof part === "string") {
        p.appendChild(document.createTextNode(part));
      } else if (part.html) {
        var span = document.createElement("span");
        span.innerHTML = part.html;
        while (span.firstChild) p.appendChild(span.firstChild);
      }
    });
    return p;
  }

  // A locally-built, claim-SHAPED object for a portfolio FACT that has no
  // registered metric/claim id in data.js (e.g. a raw position count). Value
  // is ALWAYS read straight off an APP.data accessor — never invented here —
  // matching the same minimal-claim-object pattern data.js's own
  // CONTRIBUTION_TO_RISK segments and scenario.js's scenarioSideClaim already
  // use. See CONTRACT.md §5 for the full claim shape this mirrors.
  //
  // WHY THIS EXISTS (PD-0008): "you hold 7 positions" is a claim about the
  // portfolio (could be wrong), not a selector, and must travel through the
  // same chip mechanism as every other number the AI cites. data.js does not
  // register a metric id for "position count" / "account count" / "total
  // portfolio value" — there is no accessor-backed claim object for these
  // today. This helper is the honest way to satisfy PD-0008 without silently
  // fabricating registry content: the VALUE is always real (read from
  // APP.data), only the wrapping claim SHAPE is synthesized here, and
  // evidence.js is written to say so plainly when one of these ids is opened
  // (see its NON_METRIC_FACT_NOTES) rather than pretending a methodology
  // entry exists. Flagged as a real data.js gap in the handback, not routed
  // around silently.
  function factClaim(id, label, value, opts) {
    opts = opts || {};
    return {
      id: id, label: label, stateType: "ACTUAL", sufficiency: "AVAILABLE", reasonCode: null,
      value: value, unit: opts.unit || "number", formatted: opts.formatted,
      referencePoint: opts.referencePoint || "", conclusionQuick: opts.conclusionQuick || "",
      caveat: "", freshness: null, methodologyId: null, proofPacketId: null, scenarioId: null
    };
  }

  // Renders a claim's D2.2 caveat slot and, for STALE_DATA, its D5 freshness
  // pill — deliberately OUTSIDE any `.ai-narrative`-classed element (see file
  // header comment for why). Reuses the same visual vocabulary every other
  // surface uses (`.claim-caveat`, `APP.ui.renderFreshnessPill`), never a
  // hand-rolled equivalent.
  function appendCitedCaveat(container, claim) {
    if (!claim) return;
    if (claim.caveat) {
      // Routed through the same localization hook as shell.js's own caveat slot
      // (APP.ui.localizeClaimField) — see js/shell.js's comment on the bilingual
      // narrative-gap proposal: falls back to English until js/data.js populates
      // claim.i18n.zh.caveat, and localizes automatically the moment it does, with no
      // further change needed here.
      container.appendChild(textNode("p", "claim-caveat", APP.ui.localizeClaimField(claim, "caveat")));
    }
    if (claim.reasonCode === "STALE_DATA" && claim.freshness) {
      var freshWrap = document.createElement("div");
      freshWrap.className = "ai-cited-freshness";
      APP.ui.renderFreshnessPill(freshWrap, claim.freshness);
      container.appendChild(freshWrap);
    }
    if (claim.sufficiency === "INSUFFICIENT_DATA") {
      // renderMetricValue already renders the INSUFFICIENT_DATA component
      // wherever the value itself is shown (e.g. inside renderClaim below);
      // nothing additional needed here beyond the caveat text above, if any.
    }
  }

  function evidenceRow(container, claims) {
    var row = document.createElement("div");
    row.className = "ai-cited-evidence";
    (claims || []).filter(Boolean).forEach(function (c) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "evidence-control evidence-control-sm";
      btn.textContent = APP.ui.tf("ai.evidenceButtonTemplate", { label: APP.ui.localizeClaimField(c, "label") || c.id });
      btn.addEventListener("click", function () { APP.ui.openEvidence(c.id); });
      row.appendChild(btn);
    });
    if (row.children.length) container.appendChild(row);
  }

  // -----------------------------------------------------------------------
  // Contextual auto-answer — used whenever the panel is opened FROM a
  // specific chart/metric affordance (context.contextClaims present). This
  // covers the owner's "Ask about this chart" and "Explain this risk"
  // examples generically: whichever claim the calling surface named is
  // rendered through the SAME shared claim ladder (`APP.ui.renderClaim`)
  // every other surface uses — this is not re-authored AI prose, it is the
  // existing deterministic claim card mounted inside the AI panel, so there
  // is zero risk of it inventing a number.
  // -----------------------------------------------------------------------
  function buildContextualAnswer(container, claims, context) {
    var primary = claims[0];
    var primaryConclusion = APP.ui.localizeClaimField(primary, "conclusionQuick");
    var lead = narrativeP([
      primaryConclusion ? primaryConclusion + " " : "",
      APP.ui.t("ai.theCurrentFigureIsPrefix"),
      { html: chip(primary) },
      "."
    ]);
    container.appendChild(lead);
    appendCitedCaveat(container, primary);

    var ladderMount = document.createElement("div");
    ladderMount.className = "ai-cited-claim";
    container.appendChild(ladderMount);
    APP.ui.renderClaim(ladderMount, primary, { depth: "quick" });

    claims.slice(1).forEach(function (c) {
      var p = narrativeP([
        APP.ui.t("ai.alsoRelevantPrefix"), { html: chip(c) },
        " (" + (APP.ui.localizeClaimField(c, "label") || c.id) + ")."
      ]);
      container.appendChild(p);
      appendCitedCaveat(container, c);
    });
  }

  // -----------------------------------------------------------------------
  // Scenario-aware answer — used when the panel is opened from Scenario
  // Lab's "Ask about this scenario" affordance (context.scenarioId). Every
  // rendering carries the SCENARIO badge (P8) so a hypothetical scenario
  // narrative can never be mistaken for actual portfolio state, matching the
  // same rule scenario.js's own comparison rows already enforce.
  // -----------------------------------------------------------------------
  var SCENARIO_METRIC_META = {
    volatility: { label: "Annualized Volatility", unit: "percent" },
    beta: { label: "Beta (vs. Benchmark)", unit: "ratio" },
    concentration: { label: "Concentration (Top 5)", unit: "percent" },
    sharpe: { label: "Sharpe Ratio", unit: "ratio" }
  };
  var SCENARIO_METRIC_ACTUAL_ID = {
    volatility: "metric.volatility", beta: "metric.beta",
    concentration: "metric.concentration", sharpe: "metric.sharpe"
  };

  // UPDATE, integration pass (designer-14): this used to duplicate
  // scenario.js's own private scenarioSideClaim helper because CONTRACT.md
  // exposed no shared accessor for "build a minimal claim from a scenario
  // comparison entry" — flagged in this file's original handback as a real
  // candidate for a shared primitive. That accessor now exists
  // (APP.data.getScenarioComparisonClaim, added to data.js) and both this
  // file and scenario.js delegate to it first, so they render the identical
  // object and evidence.js can resolve a real Proof Packet for it. The local
  // build below is kept only as a defensive fallback.
  function scenarioSideClaim(scenarioId, key, entry) {
    var id = scenarioId + "." + key;
    if (APP.data && APP.data.getScenarioComparisonClaim) {
      var shared = APP.data.getScenarioComparisonClaim(id);
      if (shared) return shared;
    }
    var meta = SCENARIO_METRIC_META[key];
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
      scenarioId: scenarioId
    };
  }

  function buildScenarioAnswer(container, context) {
    var scenario = APP.data.getScenario(context.scenarioId);
    if (!scenario) {
      container.appendChild(textNode("p", "ai-narrative", APP.ui.t("ai.noScenarioSelected")));
      return;
    }
    var badgeWrap = document.createElement("div");
    APP.ui.renderActualScenarioBadge(badgeWrap, "SCENARIO");
    container.appendChild(badgeWrap);

    var lead = narrativeP([
      APP.ui.tf("ai.scenarioLeadTemplate", { name: APP.ui.localizeClaimField(scenario, "name") })
    ]);
    container.appendChild(lead);

    ["volatility", "beta", "concentration", "sharpe"].forEach(function (key) {
      var entry = scenario.comparison[key];
      if (!entry) return;
      var scenClaim = scenarioSideClaim(scenario.id, key, entry);
      // HG1 Round 5 correction pass (Objective 2). `label` comes from the ACTUAL
      // metric claim (which now carries `i18n.zh.label`, this pass's own addition
      // to js/data.js) rather than this file's own English-only SCENARIO_METRIC_META,
      // for the identical reason js/surfaces/scenario.js's own metricRow was fixed
      // this same pass — one source for a metric's display name.
      var actualClaimForLabel = claimById(SCENARIO_METRIC_ACTUAL_ID[key]);
      var metricLabel = (actualClaimForLabel && APP.ui.localizeClaimField(actualClaimForLabel, "label")) || SCENARIO_METRIC_META[key].label;
      var p = narrativeP([
        APP.ui.tf("ai.scenarioMetricPrefixTemplate", { label: metricLabel }),
        { html: chip(scenClaim) },
        "."
      ]);
      container.appendChild(p);
      appendCitedCaveat(container, scenClaim);
    });

    // HG1 Round 5 correction pass (Objective 2). `scenario.warnings` now reads
    // through `localizeClaimField`-style array-index matching against
    // `scenario.i18n.zh.warnings` (js/data.js, this pass) — see
    // js/surfaces/scenario.js's own identical fix for the same convention.
    var warningsZh = (scenario.i18n && scenario.i18n.zh && scenario.i18n.zh.warnings) || null;
    (scenario.warnings || []).forEach(function (w, wIdx) {
      var text = (APP.ui.getLang() === "zh" && warningsZh && warningsZh[wIdx]) ? warningsZh[wIdx] : w;
      container.appendChild(textNode("p", "claim-caveat", text));
    });
  }

  // -----------------------------------------------------------------------
  // Global default answer — a short Portfolio Brief, shown when the panel is
  // opened from the global "Ask your portfolio" header affordance (no
  // specific chart/metric context). Historical framing only (P6) —
  // describes what happened, never projects.
  // -----------------------------------------------------------------------
  function buildBriefAnswer(container) {
    var totalClaim = factClaim(
      "fact.totalPortfolioValue", APP.ui.t("ov.totalPortfolioValue"),
      APP.data.getTotalPortfolioValue(),
      { unit: "currency", referencePoint: "As of " + APP.data.meta.asOf }
    );
    var ret = claimById("metric.return.1y");
    var rel = claimById("metric.benchmarkRelative");
    var conc = claimById("metric.concentration");

    var parts = [APP.ui.t("ai.briefIntroPrefix"), { html: chip(totalClaim) }, "."];
    container.appendChild(narrativeP(parts));

    if (ret && rel) {
      var relConclusion = APP.ui.localizeClaimField(rel, "conclusionQuick");
      container.appendChild(narrativeP([
        relConclusion ? relConclusion + " " : "",
        APP.ui.t("ai.overTrailingYearPrefix"), { html: chip(ret) },
        APP.ui.t("ai.whichIsRelativeMid"), { html: chip(rel) }, APP.ui.t("ai.relativeToItsBenchmarkSuffix")
      ]));
      appendCitedCaveat(container, rel);
    }
    if (conc) {
      container.appendChild(narrativeP([
        APP.ui.t("ai.largestHoldingsPrefix"), { html: chip(conc) }, APP.ui.t("ai.ofInvestedValueSuffix")
      ]));
      appendCitedCaveat(container, conc);
    }
    evidenceRow(container, [totalClaim, ret, rel, conc]);
  }

  // -----------------------------------------------------------------------
  // Suggested follow-up templates (always offered, regardless of how the
  // panel was opened) — this is the "Q&A" half of the AI Analyst surface,
  // covering the owner's remaining named examples ("Why did my portfolio
  // underperform?", "What changed?", "Summarize my largest exposures")
  // explicitly, plus one demonstrating PD-0008's exact ruling.
  //
  // HG1 Round 5 correction pass (Objective 2) — `label` is now a FUNCTION
  // (`APP.ui.t(key)`), called at render time (renderPanel, below), rather than a
  // fixed English string evaluated once when this array literal runs — the
  // ONLY change needed for these five follow-up buttons to re-localize on a
  // language switch (this module-level array is built once, before any
  // language switch could occur).
  // -----------------------------------------------------------------------
  var TEMPLATES = [
    {
      id: "positions",
      labelKey: "ai.template.positions",
      relevant: function () { return true; },
      build: function (container) {
        var holdings = APP.data.getHoldings();
        var markets = {};
        holdings.forEach(function (h) { markets[h.listingMarket] = true; });
        var marketCount = Object.keys(markets).length;
        var positionsClaim = factClaim("fact.holdingsCount", APP.ui.t("ai.positionCountLabel"), holdings.length, { unit: "number" });
        var marketsClaim = factClaim("fact.marketsCount", APP.ui.t("ai.distinctMarketsLabel"), marketCount, { unit: "number" });
        container.appendChild(narrativeP([
          APP.ui.t("ai.youHoldPrefix"), { html: chip(positionsClaim) }, APP.ui.t("ai.acrossListingMarketsMid"), { html: chip(marketsClaim) }, APP.ui.t("ai.listingMarketsSuffix"),
          APP.ui.t("ai.largestHoldingsShownNote")
        ]));
        evidenceRow(container, [positionsClaim, marketsClaim]);
      }
    },
    {
      id: "underperform",
      labelKey: "ai.template.underperform",
      relevant: function () { return true; },
      build: function (container) {
        var ret = claimById("metric.return.1y");
        var rel = claimById("metric.benchmarkRelative");
        var fx = claimById("metric.fxAttribution");
        var attrib = claimById("metric.performanceAttribution");
        if (!ret || !rel) {
          container.appendChild(textNode("p", "ai-narrative", APP.ui.t("ai.performanceNotAvailable")));
          return;
        }
        container.appendChild(narrativeP([
          (APP.ui.localizeClaimField(rel, "conclusionQuick") || "") + " ",
          APP.ui.t("ai.overTrailingYearPrefix"), { html: chip(ret) }, APP.ui.t("ai.whichIsRelativeMid"),
          { html: chip(rel) }, APP.ui.t("ai.relativeToItsBenchmarkSuffix")
        ]));
        appendCitedCaveat(container, rel);
        if (fx) {
          container.appendChild(narrativeP([
            (APP.ui.localizeClaimField(fx, "conclusionQuick") || "") + " ",
            APP.ui.t("ai.currencyMovementLead"), { html: chip(fx) }, APP.ui.t("ai.ofThatFigureSuffix"),
            attrib ? APP.ui.t("ai.decomposingIntoLead") : ".",
            attrib ? { html: chip(attrib) } : "",
            attrib ? "." : ""
          ]));
          appendCitedCaveat(container, fx);
        }
        evidenceRow(container, [ret, rel, fx, attrib]);
      }
    },
    {
      id: "changed",
      labelKey: "ai.template.changed",
      relevant: function () { return true; },
      build: function (container) {
        container.appendChild(narrativeP([
          APP.ui.t("ai.changedIntro")
        ]));
        var listMount = document.createElement("div");
        listMount.className = "ai-cited-insights";
        container.appendChild(listMount);
        APP.ui.renderInsightsList(listMount, APP.data.getInsights(), { mode: "compact" });
      }
    },
    {
      id: "exposures",
      labelKey: "ai.template.exposures",
      relevant: function () { return true; },
      build: function (container) {
        var sectorExposure = APP.data.getExposure("sector");
        var geoExposure = APP.data.getExposure("economicGeography");
        var conc = claimById("metric.concentration");
        container.appendChild(narrativeP([
          (sectorExposure.claim && sectorExposure.claim.conclusionQuick ? APP.ui.localizeClaimField(sectorExposure.claim, "conclusionQuick") + " " : ""),
          (geoExposure.claim && geoExposure.claim.conclusionQuick ? APP.ui.localizeClaimField(geoExposure.claim, "conclusionQuick") + " " : ""),
          // "5" here is a selector digit (which segment "top N" refers to,
          // matching metric.concentration's own established "Top 5"
          // convention) — not a claim about the portfolio, so it is wrapped
          // in APP.ui.selectorHTML rather than a chip, per PD-0008. The
          // percentage right after it IS a claim and stays chipped.
          conc ? APP.ui.t("ai.topHoldingsPrefix") : "",
          conc ? { html: APP.ui.selectorHTML("5") } : "",
          conc ? APP.ui.t("ai.topHoldingsSuffix") : "",
          conc ? { html: chip(conc) } : "",
          conc ? APP.ui.t("ai.ofInvestedValueSuffix") : ""
        ]));
        if (conc) appendCitedCaveat(container, conc);
        // HG1 round-4 (§6.2 / PD-0015 §2.3) — this chart previously read the RAW
        // getExposure("sector") dimension directly, which mixes real sectors with
        // non-sector categories (Diversified Fund, Government Bonds, Structured
        // Product) — the confirmed §6.2 defect already fixed on Overview and Analytics
        // via APP.ui.classifySectorExposure, but missed here. Fixed the same way, for
        // the same reason: a fund must never be presented as if it were a sector.
        // Direct-equity sector segments only, translated for display via
        // labelForSectorSegment (never inside the classifier itself — PD-0015 §2.3).
        var sectorSplit = APP.ui.classifySectorExposure(APP.data.getHoldings(), APP.data.getTotalPortfolioValue());
        var chartMount = document.createElement("div");
        chartMount.style.marginTop = "8px";
        chartMount.appendChild(APP.charts.bar({
          items: sectorSplit.sectorSegments.map(function (s) { return { label: APP.ui.labelForSectorSegment(s, false), value: s.value }; }),
          valueFormat: function (v) { return APP.ui.formatCurrency(v); }
        }));
        container.appendChild(chartMount);
        evidenceRow(container, [sectorExposure.claim, geoExposure.claim, conc]);
      }
    },
    {
      id: "risk",
      labelKey: "ai.template.risk",
      relevant: function () { return true; },
      build: function (container) {
        var vol = claimById("metric.volatility");
        if (!vol) { container.appendChild(textNode("p", "ai-narrative", APP.ui.t("ai.riskNotAvailable"))); return; }
        container.appendChild(narrativeP([
          (APP.ui.localizeClaimField(vol, "conclusionQuick") || ""),
          APP.ui.t("ai.currentAnnualizedVolTemplate"), { html: chip(vol) }, "."
        ]));
        appendCitedCaveat(container, vol);
        var ladderMount = document.createElement("div");
        ladderMount.className = "ai-cited-claim";
        container.appendChild(ladderMount);
        APP.ui.renderClaim(ladderMount, vol, { depth: "quick" });
      }
    }
  ];

  // -----------------------------------------------------------------------
  // Panel assembly
  // -----------------------------------------------------------------------
  function appendAnswer(thread, buildFn, context) {
    var msg = document.createElement("div");
    msg.className = "ai-message";
    buildFn(msg, context);
    thread.appendChild(msg);
    if (APP.ui.checkNarrativeSafety) APP.ui.checkNarrativeSafety(thread);
    return msg;
  }

  function renderPanel(mountEl, context) {
    context = context || {};
    mountEl.innerHTML = "";

    var wrap = document.createElement("div");
    wrap.className = "ai-panel";

    wrap.appendChild(textNode("p", "ai-context-label",
      context.label ? APP.ui.tf("ai.contextualQuestionTemplate", { label: context.label }) : APP.ui.t("common.askPortfolio")));

    var disclaimer = textNode("p", "ai-disclaimer text-faint", APP.ui.t("ai.disclaimer"));
    wrap.appendChild(disclaimer);

    var thread = document.createElement("div");
    thread.className = "ai-thread";
    wrap.appendChild(thread);

    var claims = (context.contextClaims || []).map(claimById).filter(Boolean);
    if (claims.length) {
      appendAnswer(thread, function (c) { buildContextualAnswer(c, claims, context); }, context);
    } else if (context.scenarioId) {
      appendAnswer(thread, buildScenarioAnswer, context);
    } else {
      appendAnswer(thread, buildBriefAnswer, context);
    }

    var suggestions = document.createElement("div");
    suggestions.className = "ai-suggestions";
    suggestions.appendChild(textNode("p", "ai-suggestions-label", APP.ui.t("ai.suggestFollowUp")));
    TEMPLATES.forEach(function (t) {
      if (!t.relevant(context)) return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ai-suggestion-btn";
      btn.textContent = APP.ui.t(t.labelKey);
      btn.addEventListener("click", function () {
        appendAnswer(thread, t.build, context);
      });
      suggestions.appendChild(btn);
    });
    wrap.appendChild(suggestions);

    mountEl.appendChild(wrap);
    if (APP.ui.checkNarrativeSafety) APP.ui.checkNarrativeSafety(wrap);
  }

  window.APP.registerAI({ renderPanel: renderPanel });
})();
