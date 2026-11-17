/*
 * js/surfaces/analytics.js — Analytics surface (group "analytics", key "analytics").
 * Owned by designer-12 (phase 2). See ../../CONTRACT.md for the full module contract
 * this file implements; nothing here re-decides anything CONTRACT.md already settled.
 *
 * I could not execute or render any of this — no browser or JS runtime exists in my
 * sandbox. Every cross-reference below (APP.ui.*, APP.data.*, APP.charts.*) was traced
 * by hand against CONTRACT.md and js/data.js's actual accessor list, not observed
 * running. pm-01 should verify in a real browser before relying on it — see my
 * handoff message for the precise list of what that means was/was not checked.
 *
 * Reading order this file builds, top to bottom (a returning-analyst surface, denser
 * default depth than Overview, per Direction B's own stated distinction):
 *   1. Performance      — hero portfolio-vs-benchmark chart (period selector, shaded
 *                         drawdown band) + quick metric strip + local/FX split.
 *   2. Risk & Return     — dense metric-card grid (Volatility, Beta, Alpha, Sharpe,
 *                         Sortino, Max Drawdown, Tracking Error, VaR), each focusable
 *                         into the inspector for the full Quick->Professional ladder.
 *   3. Rolling & Drawdown — two supporting time-series charts (trend/timing a scalar
 *                         cannot show).
 *   4. SML / CAPM        — scatter, portfolio vs benchmark vs sleeves against the
 *                         security market line; points focusable.
 *   5. Exposure          — listing-market vs economic-geography (the load-bearing
 *                         divergence), asset-class, sector, currency (LIMITED demo),
 *                         concentration.
 *   6. Correlation        — quick cluster conclusion at rest; full matrix only inside
 *                         the inspector (Professional depth), per §18.2's four-step
 *                         ladder composed with D2.
 *   7. Contribution to risk — per-segment renderMetricValue rows (one deliberately
 *                         INSUFFICIENT_DATA/CALCULATION_ERROR), plus a supplementary
 *                         bar of the available segments only.
 *   8. Contextual AI affordance (never a destination of its own).
 *
 * Every chart is used because it shows something a sentence or bare numeral would not
 * (trend/timing, a spatial position relative to a line, two overlapping contributions
 * to one number, relative proportion across many segments) — not to raise chart count.
 */
(function () {
  "use strict";
  window.APP = window.APP || {};
  var APP = window.APP;

  // -----------------------------------------------------------------------
  // Small DOM helpers — no hand-rolled SVG, no reimplemented formatting.
  // -----------------------------------------------------------------------
  function el(tag, className, text) {
    var e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  function blockHeader(kicker) {
    var header = document.createElement("div");
    header.className = "block-header";
    header.appendChild(el("span", "block-kicker", kicker));
    return header;
  }

  // A compact, focusable claim cell — the "calm at rest" rung of the depth ladder.
  // Shows label + renderMetricValue (which itself carries the mandatory D3.2 qualifier
  // for LIMITED, and the D3.2 "no numeric glyph" treatment for INSUFFICIENT_DATA) plus
  // an optional one-line Quick conclusion. Clicking opens the full Quick->Professional
  // ladder in the docked inspector (Direction B's focus-and-inspect graft) rather than
  // permanently expanding inline — this is the visual-conclusion -> metric ->
  // explanation -> evidence -> methodology path for every metric card on this surface.
  function focusableMetricCell(ctx, claim, opts) {
    opts = opts || {};
    if (!claim) return null;
    var cell = document.createElement("button");
    cell.type = "button";
    cell.className = "card metric-cell metric-cell-button";
    // Routed through ctx.ui.localizeClaimField (js/shell.js) — the single choke point
    // this surface's own metric cards all pass through, so it is also the single place
    // the bilingual narrative-gap fix (once js/data.js populates claim.i18n.zh.*) takes
    // effect for every metric-grid/exposure/contribution card on this surface at once.
    // HG1 ux_planning revision (review-06, secondary — duplicated disclosure
    // headings). `opts.showLabel` (new, default true — every existing caller is
    // unaffected) lets a caller that already rendered this claim's own label as an
    // adjacent `.block-subheading` immediately above this cell (buildExposureBlock's
    // Currency Exposure / Concentration (Top 5) subsections, and exposureColumn's
    // Listing-Market/Asset-Class-Exposure columns) suppress the second, redundant
    // copy instead of showing the identical text twice in a row.
    if (opts.showLabel !== false) {
      cell.appendChild(el("span", "metric-cell-label", ctx.ui.localizeClaimField(claim, "label") || ""));
    }
    var valueMount = document.createElement("div");
    valueMount.className = "metric-cell-value";
    ctx.ui.renderMetricValue(valueMount, claim);
    cell.appendChild(valueMount);
    var conclusionText = ctx.ui.localizeClaimField(claim, "conclusionQuick");
    if (opts.showConclusion !== false && conclusionText) {
      cell.appendChild(el("p", "metric-cell-conclusion", conclusionText));
    }
    cell.addEventListener("click", function () {
      ctx.ui.inspector.focus({
        title: ctx.ui.localizeClaimField(claim, "label"),
        render: function (mount) {
          // HG1 round-4 (PD-0012 §2): "Investor" is removed as a selectable ladder rung;
          // its content (referencePoint + investorDetail) now renders under Professional.
          // HG1 Round 5, Phase 2 (S5) — the inspector's own default depth now follows
          // the shared APP.state.explanationMode instead of a hardcoded "professional"
          // (opts.depth, when a caller supplies one, remains the local override).
          ctx.ui.renderClaim(mount, claim, { depth: opts.depth || ctx.ui.getExplanationMode() });
        }
      });
    });
    return cell;
  }

  // HG1 Condition 3 — "country, currency, sector and asset-class charts should use
  // consistent horizontal-bar conventions." This previously showed percent-of-portfolio
  // only, while Overview's own exposure bars (identical getExposure() segment shape)
  // showed dollar only — two conventions for one chart type. Both surfaces now read
  // through the same ctx.ui.formatExposureSegment(seg) (percent first, dollar second).
  // opts.labelTranslate — HG1 round-4, second bilingual pass: an optional per-segment
  // label translator (ctx.ui.translateSleeveLabel / ctx.ui.translateGeographyLabel),
  // applied only by the two dimensions ("by listing market," "by economic geography")
  // that map onto an established Chinese term; every other caller omits it and segment
  // labels pass through unchanged (see js/shell.js's own comment on why sector/asset-
  // class names are not translated here).
  function exposureBarChart(ctx, segments, width, labelTranslate) {
    var items = (segments || []).map(function (s) {
      return { label: labelTranslate ? labelTranslate(s.label) : s.label, value: s.value, displayValue: ctx.ui.formatExposureSegment(s) };
    });
    if (!items.length) return el("p", "block-subheading", ctx.ui.t("an.noBreakdownAvailable"));
    return ctx.charts.bar({ items: items, width: width || 320 });
  }

  // title + optional claimId (D4: every exposure dimension carries its own evidence/
  // methodology affordance, per D1 Exposure item 5 — "on every claim in items 1-4")
  // + the segment bar chart. opts.showConclusion lets a caller suppress the repeated
  // Quick-conclusion sentence when a headline callout above already shows it.
  function exposureColumn(ctx, title, claimId, exposureResult, opts) {
    opts = opts || {};
    var col = document.createElement("div");
    col.className = "analytics-exposure-col";
    col.appendChild(el("h4", "block-subheading", title));
    var claim = claimId ? ctx.data.getMetric(claimId) : null;
    var cell = focusableMetricCell(ctx, claim, { showConclusion: opts.showConclusion, showLabel: opts.showLabel });
    if (cell) col.appendChild(cell);
    col.appendChild(exposureBarChart(ctx, exposureResult && exposureResult.segments, undefined, opts.labelTranslate));
    return col;
  }

  // HG1 round-4 §6.2 (confirmed defect, reviews/gates/HG1_ROUND4_VERIFICATION.md §3):
  // js/data.js's getExposure("sector") mixes real sectors (Information Technology,
  // Communication Services, ...) with values that are not sectors (Diversified Fund,
  // Government Bonds, Structured Product) — a polished bar chart made a fund holding
  // look like a sector peer of an operating company. Replaces the plain
  // exposureColumn(ctx, "Sector", ...) call with a presentation that separates known
  // direct sector exposure from pooled/fund, fixed-income, and structured/unsupported
  // exposure, via the shared ctx.ui.classifySectorExposure helper (js/shell.js) — see
  // that helper's own comment for exactly what a future data.js accessor should provide
  // instead of this client-side fallback. Mirrors the identical fix in
  // js/surfaces/overview.js so both surfaces present this the same way (§4.1).
  function sectorExposureColumn(ctx) {
    var col = document.createElement("div");
    col.className = "analytics-exposure-col";
    col.appendChild(el("h4", "block-subheading", ctx.ui.t("an.sectorDirectEquityOnly")));
    var split = ctx.ui.classifySectorExposure(ctx.data.getHoldings(), ctx.data.getTotalPortfolioValue());
    // PD-0015 Part 2 / §2.3 — classifySectorExposure's segments now carry a canonical
    // `key`, never a `label` (the classifier itself has no APP.i18n dependency at all —
    // see its own comment in js/shell.js). Translated to a display `label` HERE, at the
    // render step, via ctx.ui.labelForSectorSegment — mirrors js/surfaces/overview.js's
    // identical fix so both surfaces present this the same way (§4.1).
    var sectorDisplaySegs = split.sectorSegments.map(function (s) {
      return { label: ctx.ui.labelForSectorSegment(s, false), value: s.value, pct: s.pct };
    });
    var nonSectorDisplaySegs = split.nonSectorSegments.map(function (s) {
      return { label: ctx.ui.labelForSectorSegment(s, true), value: s.value, pct: s.pct };
    });
    if (sectorDisplaySegs.length) {
      col.appendChild(exposureBarChart(ctx, sectorDisplaySegs));
    } else {
      col.appendChild(el("p", "block-subheading", ctx.ui.t("ov.noDirectEquitySector")));
    }
    if (nonSectorDisplaySegs.length) {
      col.appendChild(el("p", "claim-caveat", ctx.ui.t("ov.notSectorsCaveat")));
      col.appendChild(exposureBarChart(ctx, nonSectorDisplaySegs));
    }
    return col;
  }

  // HG1 round-4 §14 — benchmark selection was a confirmed-missing UX contract; MSCI
  // ACWI was an invisible, hardcoded assumption behind excess return, beta, alpha, and
  // the SML. A selector now exists in Settings (js/shell.js's openSettings). This note
  // mounts wherever a benchmark-relative figure is shown so a reader who has selected a
  // DIFFERENT benchmark there is never left assuming these figures already reflect it —
  // "stale benchmark-dependent results must never remain mislabeled" (§14) is honored by
  // stating plainly which benchmark actually produced the numbers below, every time,
  // rather than silently relabeling an MSCI-ACWI-computed figure as if it were something
  // else.
  function benchmarkNote(ctx) {
    var selected = ctx.ui.getSelectedBenchmark ? ctx.ui.getSelectedBenchmark() : "MSCI ACWI (ACWI)";
    var p = document.createElement("p");
    p.className = "text-faint";
    p.style.marginTop = "var(--space-1)";
    if (selected.indexOf("ACWI") >= 0) {
      p.textContent = ctx.ui.t("an.benchmarkNoteAcwi");
    } else {
      // "selected" is the benchmark NAME the reader picked in Settings (e.g. "S&P 500
      // (SPX)") — a canonical index identifier, never translated; only the sentence
      // around it is.
      p.textContent = ctx.ui.t("an.benchmarkNoteOtherPrefix") + selected + ctx.ui.t("an.benchmarkNoteOtherSuffix");
    }
    return p;
  }

  // -----------------------------------------------------------------------
  // HG1 Round 5, Phase 2 correction pass — Blocker 1 (Analytics must
  // differentiate Simple vs Professional AT DEFAULT RENDER; reviews/gates/
  // HG1_ROUND5_PHASE2_CORRECTION_VERIFICATION.md §1). Root cause recorded
  // there: every ctx.ui.renderModule call on this surface shared one
  // minMode:"simple" threshold, so Simple and Professional opened the
  // identical module set at rest — the actual depth difference
  // (investorDetail / professionalDetail / caveat) already existed, but only
  // inside the click-required inspector (focusableMetricCell ->
  // ctx.ui.inspector.focus -> ctx.ui.renderClaim, which already gates
  // investorDetail/professionalDetail to depth "professional" — see
  // js/shell.js's renderClaim). This helper surfaces that SAME
  // already-authored text — no new copy, no changed financial conclusion
  // (PD-0012 §2; PD-0016 Part 1 §1.3) — at rest, through a SECOND,
  // independently-gated ctx.ui.renderModule at minMode:"professional": the
  // identical mechanism this file already uses everywhere else, nested one
  // level deeper. uicheck's own visibility walk (js/shell.js's
  // uicheckIsVisible) is explicitly built to handle a module-gate nested
  // inside another module-gate, so this composes correctly with the outer
  // minMode:"simple" gates already wrapping every block below.
  //
  // Deliberately appended as a SIBLING after the grid/list/button it
  // documents, never inside a `.metric-cell-button` itself: that element is
  // a `<button>`, and a collapsed renderModule renders a `<details>` —
  // interactive content, which is invalid inside a `<button>` and would also
  // make a click on the inner `<summary>` bubble into the outer button's own
  // click handler (opening the inspector) at the same time it toggles the
  // disclosure. Also kept out of any `.metric-grid`/`.layout-grid`, so it
  // cannot become an extra, unstyled grid track next to the metric cards —
  // appended to the enclosing `block`, which is a plain flow container.
  // -----------------------------------------------------------------------
  function appendProfessionalDepthModule(ctx, container, opts) {
    opts = opts || {};
    var items = [];
    (opts.claims || []).forEach(function (c) {
      if (!c) return;
      var inv = ctx.ui.localizeClaimField(c, "investorDetail");
      var pro = ctx.ui.localizeClaimField(c, "professionalDetail");
      var cav = opts.includeCaveat ? ctx.ui.localizeClaimField(c, "caveat") : null;
      if (!inv && !pro && !cav) return;
      items.push({ label: ctx.ui.localizeClaimField(c, "label") || "", inv: inv, pro: pro, cav: cav });
    });
    if (!items.length) return null;
    return ctx.ui.renderModule(container, {
      minMode: "professional",
      id: opts.id,
      label: opts.label || ctx.ui.t("an.professionalDepthHeading"),
      build: function (mount) {
        items.forEach(function (it) {
          if (items.length > 1) mount.appendChild(el("p", "metric-cell-label", it.label));
          if (it.inv) mount.appendChild(el("p", "claim-investor-detail", it.inv));
          if (it.pro) mount.appendChild(el("p", "claim-professional-detail", it.pro));
          if (it.cav) mount.appendChild(el("p", "claim-caveat", it.cav));
        });
      }
    });
  }

  // -----------------------------------------------------------------------
  // 1. Performance
  // -----------------------------------------------------------------------
  function buildPerformanceBlock(ctx) {
    var block = document.createElement("div");
    block.className = "block analytics-performance";
    block.appendChild(blockHeader(ctx.ui.t("an.performance")));
    block.appendChild(benchmarkNote(ctx));

    var rangeBar = document.createElement("div");
    rangeBar.className = "chart-range-selector";
    block.appendChild(rangeBar);

    var chartWrap = document.createElement("div");
    chartWrap.className = "analytics-hero-chart-wrap";
    block.appendChild(chartWrap);

    var ranges = ["1M", "3M", "6M", "1Y", "ALL"];
    var currentRange = "1Y";

    function renderHero(range) {
      chartWrap.innerHTML = "";
      var series = ctx.data.getPortfolioSeries({ range: range });
      // HG1 Condition 3 — drawdown shading removed from this hero, same judgment call as
      // Overview's identical chart (see js/surfaces/overview.js's renderHero for the full
      // reasoning): the dedicated underwater chart in this surface's own Rolling &
      // Drawdown block below (now with a benchmark reference line) is where "how deep did
      // it fall" is answered; this chart's one job is "who's ahead." End labels, hover,
      // and the relative-performance callout are on by default (charts.js).
      chartWrap.appendChild(ctx.charts.lineCompare({
        dates: series.dates,
        series: { portfolio: series.portfolio, benchmark: series.benchmark },
        labelA: ctx.ui.t("ov.yourPortfolio"),
        labelB: ctx.ui.t("ov.benchmarkAcwiSeries")
      }));
    }
    renderHero(currentRange);

    ranges.forEach(function (r) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "range-pill" + (r === currentRange ? " range-pill-active" : "");
      btn.textContent = r;
      btn.addEventListener("click", function () {
        rangeBar.querySelectorAll(".range-pill").forEach(function (b) { b.classList.remove("range-pill-active"); });
        btn.classList.add("range-pill-active");
        renderHero(r);
      });
      rangeBar.appendChild(btn);
    });

    // HG1 Round 5, Phase 2 (S5 — "the state chips stay ... they render as short
    // tokens per S4"). metric.benchmarkRelative is the one claim on this surface
    // whose comparability flag/qualifierShort chip must not be suppressed at Quick —
    // rendered here, always visible, through a PLAIN (unclassed) mount rather than
    // focusableMetricCell, specifically so it never carries the `.metric-cell` class
    // AC-S5.3 forbids in the Quick DOM. Removed from the gated metric-strip below (it
    // would otherwise render twice at Simple+).
    var benchRelClaim = ctx.data.getMetric("metric.benchmarkRelative");
    if (benchRelClaim) {
      var benchRelWrap = document.createElement("div");
      benchRelWrap.appendChild(el("span", "metric-cell-label", ctx.ui.localizeClaimField(benchRelClaim, "label") || ""));
      var benchRelValueMount = document.createElement("div");
      benchRelValueMount.className = "metric-cell-value";
      ctx.ui.renderMetricValue(benchRelValueMount, benchRelClaim);
      benchRelWrap.appendChild(benchRelValueMount);
      block.appendChild(benchRelWrap);
    }

    // HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1; AC-S5.3). The hero chart above (plus
    // the always-visible benchmark-relative stat just added) is Analytics' own
    // Quick-visible content — everything below renders through focusableMetricCell,
    // i.e. carries the `.metric-cell` class AC-S5.3 forbids anywhere in the Quick
    // DOM. Gated as one module rather than deleted; the collapsed affordance is
    // labelled with this same sub-section's own heading.
    ctx.ui.renderModule(block, {
      minMode: "simple",
      label: ctx.ui.t("an.localVsCurrencyContribution"),
      build: function (mount) {
        var strip = document.createElement("div");
        strip.className = "metric-strip";
        ["metric.return.1y", "metric.fxAttribution"].forEach(function (id) {
          var c = ctx.data.getMetric(id);
          var cell = focusableMetricCell(ctx, c);
          if (cell) strip.appendChild(cell);
        });
        mount.appendChild(strip);

        // Local-market vs. currency contribution — a stacked band because a sentence
        // cannot show two overlapping contributions to one number as legibly as this can.
        var attribWrap = document.createElement("div");
        attribWrap.className = "block-sub analytics-attribution";
        attribWrap.appendChild(el("h4", "block-subheading", ctx.ui.t("an.localVsCurrencyContribution")));
        var retClaim = ctx.data.getMetric("metric.return.1y");
        var fxClaim = ctx.data.getMetric("metric.fxAttribution");
        var perfAttribClaim = ctx.data.getMetric("metric.performanceAttribution");
        if (retClaim && fxClaim && retClaim.value !== null && retClaim.value !== undefined &&
            fxClaim.value !== null && fxClaim.value !== undefined) {
          // Derived purely from two already-fetched accessor values (total return minus
          // FX attribution = local-market component) — the same arithmetic data.js's own
          // metric.performanceAttribution.formatted string already encodes. Not a new
          // fact: no per-sleeve (HK vs. CN) local/FX split is exposed by data.js, so this
          // chart is necessarily portfolio-level, not sleeve-level — see handoff.
          var localVal = retClaim.value - fxClaim.value;
          attribWrap.appendChild(ctx.charts.stackedBar({
            categories: [ctx.ui.t("an.trailing1yReturnCategory")],
            series: [
              { label: ctx.ui.t("an.localMarketReturn"), values: [localVal] },
              { label: ctx.ui.t("an.fxEffect"), values: [fxClaim.value] }
            ],
            width: 360,
            height: 200
          }));
        }
        if (perfAttribClaim) {
          var pMount = document.createElement("div");
          pMount.className = "metric-cell-value";
          ctx.ui.renderMetricValue(pMount, perfAttribClaim);
          attribWrap.appendChild(pMount);
          var explainBtn = document.createElement("button");
          explainBtn.type = "button";
          explainBtn.className = "link-button";
          explainBtn.textContent = ctx.ui.t("an.explainThisSplit");
          explainBtn.addEventListener("click", function () {
            ctx.ui.inspector.focus({
              title: ctx.ui.localizeClaimField(perfAttribClaim, "label"),
              // HG1 Round 5, Phase 2 (S5) — follows the shared global mode instead of a
              // hardcoded "professional"; the inspector's own ladder pills still let a
              // reader go deeper locally from whatever depth this opens at.
              render: function (mount) { ctx.ui.renderClaim(mount, perfAttribClaim, {}); }
            });
          });
          attribWrap.appendChild(explainBtn);
        }
        mount.appendChild(attribWrap);
      }
    });

    return block;
  }

  // -----------------------------------------------------------------------
  // 2. Risk & Return metric grid
  // -----------------------------------------------------------------------
  function buildRiskGridBlock(ctx) {
    var block = document.createElement("div");
    block.className = "block analytics-risk-grid";
    block.appendChild(blockHeader(ctx.ui.t("an.riskReturnProfile")));

    // HG1 round-4 §5.1 — "the current Risk Overview should be reorganized around
    // investor questions, not a flat metric inventory." The previous single 8-item
    // `.metric-grid` (volatility/beta/alpha/sharpe/sortino/maxDrawdown/trackingError/
    // var95, in that arbitrary order) is exactly the flat inventory the owner named.
    // Regrouped into the owner's own five questions: Overall risk -> Market sensitivity
    // -> Downside -> Risk-adjusted performance -> Risk drivers (risk drivers continues
    // below, in the existing Rolling & Drawdown / Exposure-concentration / Contribution-
    // to-risk blocks, which already ARE risk-driver content — this group is not
    // duplicated here). Alpha and Tracking Error are not explicitly named in the owner's
    // suggested mapping; both are grouped under Market Sensitivity here (both describe
    // dispersion/deviation from the benchmark, the same relationship beta describes) —
    // an assumption stated here, not decided silently.
    var riskGroups = [
      { heading: ctx.ui.t("riskGroup.overallRisk"), ids: ["metric.volatility"] },
      { heading: ctx.ui.t("riskGroup.marketSensitivity"), ids: ["metric.beta", "metric.alpha", "metric.trackingError"] },
      { heading: ctx.ui.t("riskGroup.downside"), ids: ["metric.maxDrawdown", "metric.var95"] },
      { heading: ctx.ui.t("riskGroup.riskAdjusted"), ids: ["metric.sharpe", "metric.sortino"] }
    ];
    riskGroups.forEach(function (group) {
      var claims = group.ids.map(function (id) { return ctx.data.getMetric(id); }).filter(Boolean);
      if (!claims.length) return;
      block.appendChild(el("h4", "block-subheading", group.heading));
      var grid = document.createElement("div");
      grid.className = "metric-grid";
      claims.forEach(function (c) {
        var cell = focusableMetricCell(ctx, c);
        if (!cell) return;
        // HG1 round-4 §5.2 — "comparative claims need visible comparative evidence...
        // even before the user opens the full Proof Packet." Several of these claims
        // already carry a benchmark-relative referencePoint string in js/data.js (e.g.
        // "MSCI ACWI annualized volatility: 12.1%," "Benchmark max drawdown: -9.4%") —
        // it existed, but was only ever shown after clicking into the (now) Professional
        // depth. Shown here, faintly, at rest, directly under the number.
        // FIX (second bilingual pass) — this read bypassed localizeClaimField, the
        // exact bug the coordinator's live review caught ("MSCI ACWI annualized
        // volatility: +12.5%" still English with 简体中文 selected, despite js/data.js
        // having translated this very field).
        var localizedRef = ctx.ui.localizeClaimField(c, "referencePoint");
        if (localizedRef) cell.appendChild(el("p", "metric-cell-conclusion", localizedRef));
        grid.appendChild(cell);
      });
      block.appendChild(grid);
    });

    // Blocker 1 (see appendProfessionalDepthModule's own comment) — the three
    // Market-Sensitivity/Downside claims that actually carry investorDetail +
    // professionalDetail content (beta, alpha, VaR95) surface it here, open by
    // default at Professional, one click away at Simple. Sharpe/Sortino/
    // Volatility/Max Drawdown/Tracking Error carry no such fields in js/data.js
    // (referencePoint only, already shown at every mode above) — nothing is
    // fabricated to pad this out.
    appendProfessionalDepthModule(ctx, block, {
      id: "an.riskReturnProfile.professionalDepth",
      claims: ["metric.beta", "metric.alpha", "metric.var95"].map(function (id) { return ctx.data.getMetric(id); })
    });

    // UNSUPPORTED_ASSET demo — a per-instrument risk-metric support flag, not a
    // per-position holding claim (that belongs to Holdings, not here).
    var riskClaim = ctx.data.getInstrumentRiskClaim("2800.HK");
    if (riskClaim) {
      var note = document.createElement("div");
      note.className = "card analytics-unsupported-note";
      // "CSOP Structured Note (2800.HK)" is a security name/ticker (canonical, never
      // translated); only the trailing " — risk metrics" label is this file's own text.
      note.appendChild(el("span", "metric-cell-label", "CSOP Structured Note (2800.HK)" + ctx.ui.t("an.csopRiskMetricsSuffix")));
      var vm = document.createElement("div");
      vm.className = "metric-cell-value";
      ctx.ui.renderMetricValue(vm, riskClaim);
      note.appendChild(vm);
      if (riskClaim.caveat) note.appendChild(el("p", "claim-caveat", ctx.ui.localizeClaimField(riskClaim, "caveat")));
      block.appendChild(note);
    }
    return block;
  }

  // -----------------------------------------------------------------------
  // 3. Rolling analytics + drawdown
  // -----------------------------------------------------------------------
  function buildRollingDrawdownBlock(ctx) {
    var block = document.createElement("div");
    block.className = "block analytics-rolling";
    block.appendChild(blockHeader(ctx.ui.t("an.rollingAnalyticsDrawdown")));

    var row = document.createElement("div");
    row.className = "analytics-chart-row";

    var volWrap = document.createElement("div");
    volWrap.className = "analytics-chart-cell";
    volWrap.appendChild(el("h4", "block-subheading", ctx.ui.t("an.rollingVol90dAnnualized")));
    var rollSeries = ctx.data.getRollingVolatilitySeries({ range: "1Y" });
    // HG1 Condition 3 (round 3) — windowLabel is the shared rolling-analytics grammar's
    // window/frequency statement (charts.js's rollingSubtitle), stated the same way and
    // in the same on-chart position as the drawdown chart beside it, so the two no longer
    // read as unrelated charts. The h4 above states WHAT the metric is (and its own
    // "annualized" calculation convention, which is not a window/frequency duplicate);
    // the chart itself now states WHEN, once, consistently.
    var rollChart = ctx.charts.rollingLine({ dates: rollSeries.dates, series: rollSeries, windowLabel: ctx.ui.t("chart.rollingWindow90d") });
    rollChart.style.cursor = "pointer";
    rollChart.addEventListener("click", function () {
      var volClaim = ctx.data.getMetric("metric.volatility");
      if (volClaim) {
        ctx.ui.inspector.focus({
          title: ctx.ui.localizeClaimField(volClaim, "label"),
          render: function (mount) { ctx.ui.renderClaim(mount, volClaim, {}); } // HG1 Round 5, Phase 2 (S5) — follows the shared global mode
        });
      }
    });
    volWrap.appendChild(rollChart);
    row.appendChild(volWrap);

    var ddWrap = document.createElement("div");
    ddWrap.className = "analytics-chart-cell";
    ddWrap.appendChild(el("h4", "block-subheading", ctx.ui.t("an.portfolioDrawdown")));
    var ddSeries = ctx.data.getDrawdownSeries({ range: "1Y" });
    // HG1 Condition 6 — "use an actual negative-underwater chart" (already true of this
    // primitive: zero at top, drawdown descending below it) + P4 ("every judgment needs a
    // reference point") — the benchmark's own drawdown series (already returned by
    // getDrawdownSeries, previously fetched and then never plotted) is now drawn as the
    // same dashed-gray reference line the hero chart uses, so "was this deep for MY
    // portfolio specifically, or did the whole market fall this far too" is answerable on
    // the chart itself, not only in the metric card's referencePoint text below it.
    // windowLabel matches the rolling-volatility chart's own subtitle prefix exactly
    // ("Trailing 1Y · Daily returns") — HG1 Condition 3 (round 3): the measurement window
    // stated the same way in the same on-chart place across both rolling instruments. The
    // "(trailing 1Y)" previously in this h4 is dropped, not duplicated, now that the chart
    // itself is the single place that states it.
    var ddChart = ctx.charts.drawdown({ dates: ddSeries.dates, values: ddSeries.portfolio, benchmarkValues: ddSeries.benchmark, windowLabel: ctx.ui.t("an.windowTrailingDaily") });
    ddChart.style.cursor = "pointer";
    ddChart.addEventListener("click", function () {
      var mdClaim = ctx.data.getMetric("metric.maxDrawdown");
      if (mdClaim) {
        ctx.ui.inspector.focus({
          title: ctx.ui.localizeClaimField(mdClaim, "label"),
          render: function (mount) { ctx.ui.renderClaim(mount, mdClaim, {}); } // HG1 Round 5, Phase 2 (S5) — follows the shared global mode
        });
      }
    });
    ddWrap.appendChild(ddChart);
    row.appendChild(ddWrap);

    block.appendChild(row);
    return block;
  }

  // -----------------------------------------------------------------------
  // 4. SML / CAPM scatter — the one visualization a text description genuinely
  //    cannot replace (a scatter position relative to a line is spatial).
  // -----------------------------------------------------------------------
  function buildSmlBlock(ctx) {
    var block = document.createElement("div");
    block.className = "block analytics-sml";
    // HG1 round-4 blocker fix (methodology/HG1_ROUND4_VERIFICATION.md §2.2, adopting
    // methodology/HG1_ROUND4_METHODOLOGY_FINDINGS.md §2.4's exact wording verbatim).
    // The prior title, "Portfolio vs. Market (SML / CAPM)," invited the theoretical-
    // CAPM reading; this IS an ex-post realized market line (a negative realized market
    // premium legitimately produces its downward slope — that slope is correct and
    // must never be "fixed"). "Security Market Line" may not appear anywhere unqualified
    // as a title; this title does not use the phrase at all.
    // ui.t() preserves the quant's exact-specified English string verbatim in English
    // mode (copied unchanged into the dictionary's "en" entry) while adding a matching
    // Chinese rendering — reusing "事后市场线" ("ex-post market line"), the exact term
    // js/data.js's own metric.sml.i18n.zh text already establishes for this concept.
    block.appendChild(blockHeader(ctx.ui.t("an.realizedReturnVsBeta")));
    block.appendChild(benchmarkNote(ctx));

    var smlData = ctx.data.getSMLPoints();
    var smlClaim = smlData.claim;

    // HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1; AC-S5.3) + Ruling 2(iv) (methodology/
    // HG1_ROUND5_CAVEAT_AND_SML_DOMAIN_RULING.md, Part B). The claim cell below carries
    // `.metric-cell` (AC-S5.3 forbids that anywhere in the Quick DOM), so this whole
    // block's substantive content — the claim cell, the chart, AND the required R_f/
    // realized-benchmark-return line annotation — is one gated module. This is what
    // makes Ruling 2(iv) hold by construction rather than by careful coordination: the
    // annotation and the chart it describes are inside the SAME build() callback, so
    // they are never rendered independently of each other at any mode — if the chart
    // is visible, the annotation is too; if the module is collapsed, neither renders.
    ctx.ui.renderModule(block, {
      minMode: "simple",
      label: ctx.ui.t("an.realizedReturnVsBeta"),
      build: function (mount) {
        // The claim's own D4 evidence/methodology control — the scatter is the visual
        // conclusion, this compact cell is the metric/explanation/evidence/methodology
        // path for the SML claim itself (independent of the per-point focus below).
        var smlCell = focusableMetricCell(ctx, smlClaim);
        if (smlCell) mount.appendChild(smlCell);

        // HG1 round-4 blocker fix (§2 — "the line annotation is required, adjacent to the
        // line, not in a tooltip"). `metric.sml.professionalDetail` already states the exact
        // line equation, Rf, the realized benchmark return, and the P6 "not a forecast, must
        // not be corrected toward a conventional upward slope" instruction — reading it here
        // (never re-typing the numbers) is what keeps this paragraph unable to disagree with
        // the claim card below it (P12). Rendered as a permanently visible paragraph, not
        // gated behind a depth click, because "not in a tooltip" means always-visible
        // whenever this module itself is visible (Ruling 2(iv)).
        if (smlClaim && smlClaim.professionalDetail) {
          var lineAnnotation = document.createElement("p");
          lineAnnotation.className = "claim-investor-detail";
          // FIX (coordinator review, third bilingual pass): this was a DIRECT read of
          // smlClaim.professionalDetail, bypassing localizeClaimField — the "keeps this
          // paragraph unable to disagree with the claim card" reasoning above is still
          // exactly right, it just has to go THROUGH the hook to get there; a direct
          // property read and a localized read of the SAME field are equally immune to
          // disagreeing with each other (both trace to the one field on the one claim
          // object), and only the latter actually localizes. metric.sml.i18n.zh.
          // professionalDetail is already populated by js/data.js — this was pure wiring,
          // no new translation needed.
          lineAnnotation.textContent = ctx.ui.localizeClaimField(smlClaim, "professionalDetail");
          mount.appendChild(lineAnnotation);
        }

        var row = document.createElement("div");
        row.className = "analytics-sml-row";

        var internal = (ctx.data._internal) || {};
        var obsCount = internal.windowObservationCount;
        var windowStart = internal.windowStart, windowEnd = internal.windowEnd;

        var chartWrap = document.createElement("div");
        chartWrap.className = "analytics-chart-cell";
        // Width/height no longer overridden here — HG1 Condition 1A names the SML scatter
        // specifically as needing "a wider plot with sufficient axis space"; charts.js's own
        // default for this chart type now reflects that directly, so this call site doesn't
        // need to know or repeat the number (single source of truth in charts.js).
        //
        // HG1 round-4 blocker fix (§2.1 — "wire the callout to getSMLPoints().
        // verticalDistance, and label the two distinctly"). The chart previously annotated
        // its own geometric vertical distance with the regression Jensen's alpha
        // (metric.alpha.value) — two different quantities computed on different bases; the
        // gap was 0.11pp before the analytical-truth corrections and grew to 0.397pp (3.6×)
        // once beta moved toward 1. `distanceCallout.distance` now reads
        // `smlData.verticalDistance` (concept 4) directly — the SAME field js/data.js
        // exposes for exactly this — never `metric.alpha.value` (concept 3, still shown
        // separately, via the side panel's own alpha claim card below and via
        // smlClaim.formatted's "α (regression)" figure — never as the line's own distance).
        var portfolioPoint = smlData.points.filter(function (p) { return p.group === "portfolio"; })[0];
        // HG1 round-4, third bilingual pass — js/data.js's SML_POINTS carries literal
        // English point labels ("Your Portfolio", "Benchmark (MSCI ACWI)", "US/HK/CN
        // Sleeve") with no i18n field; correlationLabelZh (below) already establishes the
        // exact translation for this same label shape (used for the correlation matrix and
        // contribution-to-risk blocks) — reused here rather than invented a second time, so
        // the ON-CHART scatter point text (charts.js draws p.label directly) localizes too,
        // not just the surrounding chrome.
        var localizedPoints = smlData.points.map(function (p) {
          return Object.assign({}, p, { label: correlationLabelZh(ctx, p.label) });
        });
        // HG1 Round 5, Phase 2 — routed from the quant ruling (methodology/
        // HG1_ROUND5_CAVEAT_AND_SML_DOMAIN_RULING.md, Part B, Ruling 2(ii)). Phase 1
        // built charts.js's scatter() to accept `opts.betaCI95` and fall back to the
        // ruling's own 0.5-beta-unit floor when it is absent, precisely so this
        // (Phase 2's) call site could wire it later with no charts.js change — this is
        // that wiring. The value already exists on the Proof Packet
        // (registerEvidenceFor, js/data.js); reading it from there rather than
        // recomputing it here means this can never independently drift from what
        // metric.beta's own Evidence record states. Tightens the SML x-domain's
        // minimum width from the 0.5 floor to 4×CI95 width (≈0.658 on this dataset) —
        // charts.js does the actual domain math; this call site only supplies the input
        // it was always missing.
        var betaEvidence = ctx.data.getEvidence ? ctx.data.getEvidence("metric.beta") : null;
        var betaCI95 = betaEvidence && betaEvidence.confidence_interval_95;
        var scatterEl = ctx.charts.scatter({
          points: localizedPoints, line: smlData.line, betaCI95: betaCI95,
          // Kept concise — the compounding-basis disclosure ("geometric line distance,
          // arithmetic regression alpha") is already stated in full, permanently visible,
          // in the line-annotation paragraph mounted directly above this chart; repeating
          // it here would be redundant text competing for the same subtitle line.
          windowLabel: ctx.ui.t("an.windowTrailingDaily") +
            (obsCount ? " · " + obsCount + ctx.ui.t("an.observationsSuffix") : "") +
            (windowStart && windowEnd ? " (" + windowStart + " " + ctx.ui.t("common.to") + " " + windowEnd + ")" : ""),
          xAxisTitle: ctx.ui.t("an.betaVsAcwiAxis") + (obsCount ? ", " + obsCount + ctx.ui.t("an.observationsSuffix") : ""),
          yAxisTitle: ctx.ui.t("an.realizedTotalReturnAxis"),
          distanceCallout: (portfolioPoint && smlData && typeof smlData.verticalDistance === "number")
            ? { beta: portfolioPoint.beta, ret: portfolioPoint.ret, distance: smlData.verticalDistance }
            : null
        });
        chartWrap.appendChild(scatterEl);
        row.appendChild(chartWrap);

        // Points render in the same order as smlData.points (charts.js appends them via a
        // single forEach over that same array) — safe to zip by index for click-to-focus.
        var pointEls = scatterEl.querySelectorAll(".chart-scatter-point");
        pointEls.forEach(function (g, i) {
          var p = smlData.points[i];
          if (!p) return;
          // Same established sleeve-map translation applied to the ON-CHART point label
          // above, reused here for the click-to-focus title/detail — "Your Portfolio" and
          // "Benchmark (MSCI ACWI)" are NOT an open-ended term (see correlationLabelZh's own
          // comment); everything else on this point (beta, ret, group) is a plain number/
          // enum, unaffected by translation.
          var pointLabelZh = correlationLabelZh(ctx, p.label);
          g.style.cursor = "pointer";
          g.addEventListener("click", function () {
            ctx.ui.inspector.focus({
              title: pointLabelZh,
              render: function (focusMount) {
                // HG1 round-4 §6.3: a return is a CHANGE, not a static level — signed:true
                // is correct here (the one formatPercent call site in this build that
                // legitimately wants the leading "+"), unlike every other direct
                // formatPercent call in this codebase, which renders a static level.
                focusMount.appendChild(el("p", "claim-investor-detail",
                  ctx.ui.tf("an.pointDetailTemplate", {
                    label: pointLabelZh, beta: p.beta.toFixed(2), ret: ctx.ui.formatPercent(p.ret, 1, { signed: true })
                  })));
                if (p.group === "portfolio") {
                  var betaClaim = ctx.data.getMetric("metric.beta");
                  var alphaClaim = ctx.data.getMetric("metric.alpha");
                  // HG1 Round 5, Phase 2 (S5) — follows the shared global mode instead of
                  // a hardcoded "professional".
                  if (betaClaim) ctx.ui.renderClaim(focusMount.appendChild(document.createElement("div")), betaClaim, {});
                  if (alphaClaim) ctx.ui.renderClaim(focusMount.appendChild(document.createElement("div")), alphaClaim, {});
                } else if (p.group === "benchmark") {
                  focusMount.appendChild(el("p", "claim-caveat", ctx.ui.t("an.benchmarkBetaDefinition")));
                }
              }
            });
          });
        });

        var sidePanel = document.createElement("div");
        sidePanel.className = "analytics-sml-side";
        var betaCell = focusableMetricCell(ctx, ctx.data.getMetric("metric.beta"));
        var alphaCell = focusableMetricCell(ctx, ctx.data.getMetric("metric.alpha"));
        if (betaCell) sidePanel.appendChild(betaCell);
        if (alphaCell) sidePanel.appendChild(alphaCell);
        row.appendChild(sidePanel);

        mount.appendChild(row);
      }
    });

    return block;
  }

  // -----------------------------------------------------------------------
  // 5. Exposure — listing market vs. economic geography must never merge into
  //    one number (the ADR/dual-listing distinction); asset class, sector,
  //    currency (LIMITED demo), concentration.
  // -----------------------------------------------------------------------
  function buildExposureBlock(ctx) {
    var block = document.createElement("div");
    block.className = "block analytics-exposure";
    block.appendChild(blockHeader(ctx.ui.t("an.exposure")));

    var geoClaim = ctx.data.getMetric("exposure.economicGeography");
    if (geoClaim && geoClaim.conclusionQuick) block.appendChild(el("p", "claim-conclusion", ctx.ui.localizeClaimField(geoClaim, "conclusionQuick")));

    var dualRow = document.createElement("div");
    dualRow.className = "analytics-exposure-dual";
    // HG1 ux_planning revision (review-06, secondary) — showLabel:false: the h4 title
    // just above ("an.byListingMarket") and this claim's own label
    // (exposure.listingMarket, js/data.js) are now the identical text ("Listing-Market
    // Exposure"/"上市地敞口"), so the card no longer repeats it a second time.
    dualRow.appendChild(exposureColumn(ctx, ctx.ui.t("an.byListingMarket"), "exposure.listingMarket", ctx.data.getExposure("listingMarket"), { labelTranslate: ctx.ui.translateSleeveLabel, showLabel: false }));
    // showConclusion:false here — the same claim's Quick conclusion is already the
    // highlighted callout above; this cell still carries its own D4 evidence control.
    dualRow.appendChild(exposureColumn(ctx, ctx.ui.t("an.byEconomicGeographyCountry"), "exposure.economicGeography", ctx.data.getExposure("economicGeography"), { showConclusion: false, labelTranslate: ctx.ui.translateGeographyLabel }));
    block.appendChild(dualRow);

    var secondRow = document.createElement("div");
    secondRow.className = "analytics-exposure-dual";
    // PD-0015 Part 2 — asset-class display labels are translated (labelTranslate),
    // matching js/surfaces/overview.js's identical asset-mix donut fix.
    // HG1 ux_planning revision (review-06, secondary) — same fix as Listing-Market
    // Exposure above; "an.assetClass" and exposure.assetClass's own label are now the
    // identical text ("Asset Class Exposure"/"资产类别敞口").
    secondRow.appendChild(exposureColumn(ctx, ctx.ui.t("an.assetClass"), "exposure.assetClass", ctx.data.getExposure("assetClass"), { labelTranslate: ctx.ui.translateTaxonomyLabel, showLabel: false }));
    secondRow.appendChild(sectorExposureColumn(ctx));
    block.appendChild(secondRow);

    // Currency exposure — LIMITED / MISSING_FX_HISTORY demo.
    var curExp = ctx.data.getExposure("currency");
    var curWrap = document.createElement("div");
    curWrap.className = "block-sub";
    curWrap.appendChild(el("h4", "block-subheading", ctx.ui.t("an.currencyExposureHeading")));
    // HG1 ux_planning revision (review-06, secondary — "section CURRENCY EXPOSURE
    // immediately above card kicker CURRENCY EXPOSURE") — showLabel:false: the h4
    // title just above and this claim's own label (exposure.currency) are the
    // identical text; the card no longer repeats it.
    var curCell = focusableMetricCell(ctx, curExp.claim, { showLabel: false });
    if (curCell) curWrap.appendChild(curCell);
    // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.4's exposure.currency
    // placement exception) — mirrors js/surfaces/overview.js's identical fix: the
    // illustrative-FX-snapshot disclosure renders directly beside the currency bar
    // chart itself, the rendering unit that actually shows the CNY-converted amounts,
    // independent of whether curCell above is inside a collapsed module.
    ctx.ui.renderQualifierNote(curWrap, curExp.claim);
    curWrap.appendChild(exposureBarChart(ctx, curExp.segments, 360));
    block.appendChild(curWrap);

    // Concentration.
    var conc = ctx.data.getConcentration();
    var concWrap = document.createElement("div");
    concWrap.className = "block-sub";
    concWrap.appendChild(el("h4", "block-subheading", ctx.ui.t("an.concentrationHeading")));
    // HG1 ux_planning revision (review-06, secondary) — showLabel:false: the h4 title
    // just above ("an.concentrationHeading", now "Concentration (Top 5)") and this
    // claim's own label (metric.concentration) are the identical text.
    var concCell = focusableMetricCell(ctx, conc.claim, { showLabel: false });
    if (concCell) concWrap.appendChild(concCell);
    // HG1 ux_planning revision (review-07, P0 item 1) — this call site bypassed
    // ctx.ui.holdingDisplayName entirely (the review's own verified count: analytics.js
    // had ZERO call sites while overview.js/portfolio.js had 3/2), so the zh Analytics
    // concentration/top-position bar rendered every holding's raw (always-English) name
    // even for the four HK-listed holdings with an established Chinese name — the exact
    // defect class holdingDisplayName exists to prevent. `conc.topPositions` items are
    // the same holding-shaped objects (`id`, `name`, ...) getConcentration() slices from
    // holdingsWithValue, so ctx.ui.holdingDisplayName(p) is a direct, safe substitution.
    var concItems = (conc.topPositions || []).map(function (p) { return { label: ctx.ui.holdingDisplayName(p), value: p.value }; });
    if (concItems.length) {
      concWrap.appendChild(ctx.charts.bar({
        items: concItems, width: 420,
        valueFormat: function (v) { return ctx.ui.formatCurrency(v); }
      }));
    }
    block.appendChild(concWrap);

    // Blocker 1 — concentration's own investorDetail (HHI, Effective N) is
    // exactly the "professional analytical depth" PD-0012 §2 names for this
    // rung; shown here at rest for Professional, one click away at Simple via
    // concCell's own inspector.
    appendProfessionalDepthModule(ctx, block, {
      id: "an.exposure.concentration.professionalDepth",
      claims: [conc.claim]
    });

    return block;
  }

  // -----------------------------------------------------------------------
  // 6. Correlation & clustering — §18.2's own four-step ladder (quick
  //    conclusion -> cluster interpretation -> important pairs -> full matrix),
  //    composed with D2: the full matrix is Professional-only and only ever
  //    renders inside the inspector, never permanently on the canvas.
  // -----------------------------------------------------------------------
  // js/data.js's CORR_LABELS are full descriptive English forms ("US Equity Sleeve",
  // ..., "Benchmark (MSCI ACWI)") with no i18n field of their own. In zh mode, this
  // reproduces data.js's OWN shortSleeveName() stripping (" Equity Sleeve"/" Sleeve")
  // before applying the same established sleeve map ctx.ui.translateSleeveLabel already
  // uses elsewhere — never a new term, and English mode is untouched (still the full
  // descriptive label, unchanged from before this pass).
  function correlationLabelZh(ctx, label) {
    if (ctx.ui.getLang() !== "zh") return label;
    var shortName = String(label).replace(" Equity Sleeve", "").replace(" Sleeve", "");
    return ctx.ui.translateSleeveLabel(shortName);
  }

  function buildCorrelationBlock(ctx) {
    var block = document.createElement("div");
    block.className = "block analytics-correlation";
    block.appendChild(blockHeader(ctx.ui.t("an.correlationClustering")));

    var corr = ctx.data.getCorrelationMatrix();
    if (corr.claim && corr.claim.conclusionQuick) block.appendChild(el("p", "claim-conclusion", ctx.ui.localizeClaimField(corr.claim, "conclusionQuick")));

    // HG1 Condition 3 — "prefer heatmap/cluster visualization with a simple AI
    // conclusion." The heatmap already existed (behind the Professional-depth inspector
    // view, per §18.2's four-step ladder — unchanged this pass); the missing half was a
    // plain-language conclusion grounded in the actual matrix values, not just the
    // claim's own pre-written conclusionQuick sentence above. Built here as a real
    // .ai-narrative block per P1: the two correlation figures it cites are the
    // strongest and weakest pairwise relationships in the SAME matrix already fetched
    // above (no separate computation, no invented number), each wrapped in a provenance
    // chip pointing at metric.correlation's own registered Evidence record — clicking
    // either opens the identical Proof Packet the heatmap's own claim card would.
    var labels = corr.labels || [], matrix = corr.matrix || [];
    if (labels.length > 1 && matrix.length === labels.length) {
      var strongest = null, weakest = null;
      for (var ri = 0; ri < labels.length; ri++) {
        for (var ci = ri + 1; ci < labels.length; ci++) {
          var v = matrix[ri][ci];
          if (!strongest || Math.abs(v) > Math.abs(strongest.v)) strongest = { i: ri, j: ci, v: v };
          if (!weakest || v < weakest.v) weakest = { i: ri, j: ci, v: v };
        }
      }
      if (strongest && corr.claim) {
        var narrative = el("div", "ai-narrative");
        var pieces = [];
        pieces.push(ctx.ui.tf("an.strongestRelationshipTemplate", {
          a: correlationLabelZh(ctx, labels[strongest.i]), b: correlationLabelZh(ctx, labels[strongest.j]),
          chip: ctx.ui.chipHTML(corr.claim, ctx.ui.formatNumber(strongest.v, { unit: "ratio" }))
        }));
        if (weakest && (weakest.i !== strongest.i || weakest.j !== strongest.j)) {
          pieces.push(ctx.ui.tf("an.weakestRelationshipTemplate", {
            a: correlationLabelZh(ctx, labels[weakest.i]), b: correlationLabelZh(ctx, labels[weakest.j]),
            chip: ctx.ui.chipHTML(corr.claim, ctx.ui.formatNumber(weakest.v, { unit: "ratio" }))
          }));
        }
        narrative.innerHTML = pieces.join("");
        block.appendChild(narrative);
        if (ctx.ui.checkNarrativeSafety) {
          try { ctx.ui.checkNarrativeSafety(block); } catch (e) { /* non-fatal, dev aid only */ }
        }
      }
    }

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "link-button";
    btn.textContent = ctx.ui.t("an.viewFullCorrelationMatrix");
    btn.addEventListener("click", function () {
      ctx.ui.inspector.focus({
        title: ctx.ui.t("an.sleeveCorrelationMatrixTitle"),
        // HG1 ux_planning revision (review-06, B5) — this is the one inspector payload
        // wide enough to need the dock's wider variant (see styles/tokens.css's
        // `--inspector-width-wide` comment); the 5-series matrix's own min-width
        // (--chart-matrix-min-width) exceeds the dock's default usable content width,
        // which is what clipped the benchmark column before this pass.
        wide: true,
        render: function (mount) {
          mount.appendChild(el("p", "claim-caveat", ctx.ui.t("an.trailing1yDaily5series")));
          mount.appendChild(ctx.charts.heatmap({
            labels: corr.labels.map(function (l) { return correlationLabelZh(ctx, l); }),
            matrix: corr.matrix
          }));
          if (corr.claim) {
            ctx.ui.renderClaim(mount.appendChild(document.createElement("div")), corr.claim, {}); // HG1 Round 5, Phase 2 (S5) — follows the shared global mode
          }
        }
      });
    });
    block.appendChild(btn);

    // Blocker 1 — the matrix's own caveat (the currency-basis mismatch: the
    // benchmark row/column is USD reporting-currency while the four sleeve
    // rows/columns are local-currency) is genuine methodology/evidence
    // content that, before this pass, was reachable only inside the
    // click-required "View full correlation matrix" inspector above. Shown
    // here at rest for Professional; the full matrix itself stays
    // inspector-only exactly as designed above (§18.2's four-step ladder —
    // untouched).
    appendProfessionalDepthModule(ctx, block, {
      id: "an.correlationClustering.professionalDepth",
      claims: [corr.claim],
      includeCaveat: true
    });

    return block;
  }

  // -----------------------------------------------------------------------
  // 7. Contribution to portfolio risk — each segment is minimal claim-shaped
  //    (value/unit/sufficiency/reasonCode/caveat), rendered through
  //    renderMetricValue like any other claim, per CONTRACT.md's explicit note.
  // -----------------------------------------------------------------------
  function buildContributionBlock(ctx) {
    var block = document.createElement("div");
    block.className = "block analytics-contribution";
    block.appendChild(blockHeader(ctx.ui.t("an.contributionToRisk")));

    var data = ctx.data.getContributionToRisk();
    // The parent claim's own D4 control (methodology.contributionToRisk) — separate
    // from the per-segment renderMetricValue rows below, which carry no methodology
    // pointer of their own (they are minimal claim-shaped values, per CONTRACT.md).
    var parentCell = focusableMetricCell(ctx, data.claim);
    if (parentCell) block.appendChild(parentCell);

    var list = document.createElement("div");
    list.className = "contribution-list";
    (data.segments || []).forEach(function (seg) {
      var row = document.createElement("div");
      row.className = "contribution-row";
      // seg.label ("US Equity Sleeve" etc.) reduces via the same established sleeve map
      // correlationLabelZh already applies for the correlation block's identical label
      // shape — reused here rather than a second, separately-maintained translation.
      row.appendChild(el("span", "metric-cell-label", correlationLabelZh(ctx, seg.label)));
      var valMount = document.createElement("div");
      valMount.className = "metric-cell-value";
      ctx.ui.renderMetricValue(valMount, seg);
      row.appendChild(valMount);
      if (seg.caveat) row.appendChild(el("p", "claim-caveat", ctx.ui.localizeClaimField(seg, "caveat")));
      list.appendChild(row);
    });
    block.appendChild(list);

    // HG1 Condition 3 — "eventually show: capital weight vs risk contribution rather
    // than another isolated set of numbers." Achievable with data already in js/data.js:
    // SLEEVE_WEIGHTS was already computed there (it drives the portfolio return series
    // itself) but had never been attached to this segment list before this pass — see
    // js/data.js's CONTRIBUTION_TO_RISK for the added `weight` field. The withheld
    // (Mainland China) segment still shows its real capital weight — that figure is a
    // fact regardless — with no risk-contribution bar drawn for it (charts.js's
    // pairedBar renders a dashed placeholder + "Insufficient data" label there, never a
    // fabricated bar length; P5 applied to a chart, not just a numeral).
    var pairedItems = (data.segments || []).map(function (seg) {
      return {
        label: correlationLabelZh(ctx, seg.label),
        valueA: seg.weight,
        valueB: seg.value,
        insufficientB: seg.sufficiency === "INSUFFICIENT_DATA" || seg.value === null || seg.value === undefined
      };
    });
    if (pairedItems.length && pairedItems.some(function (it) { return typeof it.valueA === "number"; })) {
      block.appendChild(el("p", "block-subheading", ctx.ui.t("an.capitalWeightVsRiskContribution")));
      block.appendChild(ctx.charts.pairedBar({
        items: pairedItems, width: 400,
        labelA: ctx.ui.t("an.capitalWeight"), labelB: ctx.ui.t("an.riskContribution"),
        valueFormat: function (v) { return ctx.ui.formatPercent(v, 1); }
      }));
      block.appendChild(el("p", "claim-caveat", ctx.ui.t("an.sleeveDivergenceCaveat")));
    }

    // Blocker 1 — the parent claim's own caveat (the exact-Euler-decomposition
    // statement plus the labelled-remainder note for the withheld segment) is
    // this block's own "decomposition" and "methodology" content per PD-0012
    // §2's definition of Professional. Shown here at rest for Professional;
    // unchanged for Simple/Quick, where it stays one click away via
    // parentCell's own inspector.
    appendProfessionalDepthModule(ctx, block, {
      id: "an.contributionToRisk.professionalDepth",
      claims: [data.claim],
      includeCaveat: true
    });

    return block;
  }

  // -----------------------------------------------------------------------
  // 8. Contextual AI affordance — never a top-level destination.
  // -----------------------------------------------------------------------
  function buildAiBlock(ctx) {
    var block = document.createElement("div");
    block.className = "block analytics-ai";
    ctx.ui.aiAffordance(block, {
      label: ctx.ui.t("an.askAboutAnalyticsView"),
      contextLabel: "analytics",
      contextClaims: [
        "metric.return.1y", "metric.benchmarkRelative", "metric.fxAttribution",
        "metric.performanceAttribution", "metric.beta", "metric.alpha",
        "metric.volatility", "metric.sharpe", "metric.sortino", "metric.maxDrawdown",
        "metric.trackingError", "metric.var95", "metric.concentration",
        "metric.correlation", "metric.contributionToRisk", "metric.sml"
      ]
    });
    return block;
  }

  // -----------------------------------------------------------------------
  // Registration
  // -----------------------------------------------------------------------
  window.APP.registerSurface("analytics", {
    group: "analytics",
    render: function (mountEl, ctx) {
      mountEl.innerHTML = "";
      var root = document.createElement("div");
      root.className = "analytical-surface analytics-surface";
      mountEl.appendChild(root);

      var intro = document.createElement("div");
      intro.className = "block analytics-intro";
      intro.appendChild(el("span", "block-kicker", ctx.ui.t("an.analyticsKicker")));
      intro.appendChild(el("p", "block-lead", ctx.ui.t("an.analyticsLead")));
      root.appendChild(intro);

      // HG1 Round 5, Phase 2 (S5 — PD-0016 Part 1; AC-S5.3). buildPerformanceBlock and
      // buildSmlBlock each self-gate their own `.metric-cell`-bearing content
      // internally (their header/hero chart stays visible at every mode; only their
      // metric-strip/side-panel content is behind minMode "simple"). The blocks below
      // are ENTIRELY `.metric-cell`-based content with no Quick-visible hero of their
      // own, so each is gated here, as a whole, at minMode "simple" — collapsed to a
      // one-click affordance named after the block's own existing heading, never
      // deleted (P9 auditability holds: every module is still in the DOM, in
      // <details>, once opened).
      root.appendChild(buildPerformanceBlock(ctx));
      ctx.ui.renderModule(root, { minMode: "simple", label: ctx.ui.t("an.riskReturnProfile"), build: function (mount) { mount.appendChild(buildRiskGridBlock(ctx)); } });
      ctx.ui.renderModule(root, { minMode: "simple", label: ctx.ui.t("an.rollingAnalyticsDrawdown"), build: function (mount) { mount.appendChild(buildRollingDrawdownBlock(ctx)); } });
      root.appendChild(buildSmlBlock(ctx));
      ctx.ui.renderModule(root, { minMode: "simple", label: ctx.ui.t("an.exposure"), build: function (mount) { mount.appendChild(buildExposureBlock(ctx)); } });
      ctx.ui.renderModule(root, { minMode: "simple", label: ctx.ui.t("an.correlationClustering"), build: function (mount) { mount.appendChild(buildCorrelationBlock(ctx)); } });
      ctx.ui.renderModule(root, { minMode: "simple", label: ctx.ui.t("an.contributionToRisk"), build: function (mount) { mount.appendChild(buildContributionBlock(ctx)); } });
      // buildAiBlock is a single contextual "Ask" affordance, not data — stays visible
      // at every mode, same reasoning as Overview's own always-visible aiAffordance
      // calls.
      root.appendChild(buildAiBlock(ctx));
    }
  });
})();
