/*
 * js/surfaces/overview.js — Overview ("portfolio command center"), owned by designer-10.
 *
 * Sole write path for this worker. Do not touch index.html, shell.js, data.js,
 * charts.js, styles/, or any sibling js/surfaces/* file — see CONTRACT.md.
 *
 * Composition (Direction C block language + Direction B's hero visual + risk grafts),
 * per reviews/gates/HG1_DIRECTION_SELECTION.md §2 objective 2:
 *   0. Freshness strip (persistent, not a block — D5, never merged axes)
 *   A. "How am I doing?"        — value, gain/loss, hero portfolio-vs-benchmark chart,
 *                                  vs. benchmark explain, expandable top/full holdings
 *   B. "What is driving it?"    — asset-class donut + economic-geography divergence,
 *                                  expandable sector/market/currency exposure detail
 *   C. "What are the main risks?" — risk stat strip, rolling volatility, concentration,
 *                                  expandable full explain ladders
 *   D. "What deserves attention?" — top severity insights, expandable full list
 *   E. Portfolio Brief            — citation-chip-grounded AI narrative + ask-a-follow-up
 *
 * Every claim rendered here comes from an APP.data accessor — nothing is fabricated.
 *
 * =====================================================================================
 * HG1 ROUND 5, PHASE 2 (designer, this pass) — S5 progressive-explanation rebuild +
 * S1 item (b) + the S4 currency-exposure placement exception. Summary; see this
 * designer's report for the full account.
 *
 *   - Every module below now declares a minMode via ctx.ui.renderModule (js/shell.js,
 *     Phase 2). Block A stays structurally present at every mode but its OWN content is
 *     trimmed internally (gain/loss cells, the benchmark-relative explanation, and the
 *     holdings section all move behind minMode "simple"); Blocks B, C, D, and E are
 *     each a single gated module, collapsed at Quick to a one-click affordance named
 *     after the block's own existing heading — nothing is deleted, only reachable at a
 *     depth of at least "simple" (P9 auditability is unaffected; every module is still
 *     in the DOM, in <details>, once opened).
 *   - `metric.return.1y`'s new `claim.analogyQuick` field (js/data.js) now renders
 *     directly beside the headline conclusion and the hero figure — this hero region
 *     does not go through the full renderClaim ladder (it never did), so the analogy is
 *     rendered explicitly here rather than relying on renderClaim's own automatic
 *     analogyQuick branch (which still fires for every OTHER claim rendered through
 *     ui.renderClaim on this surface, e.g. the benchmark-relative card below, with zero
 *     further change needed here).
 *   - S1 item (b): `row()` and every inline element-style write in this file are removed.
 *     Multi-column rows now use Phase 1's `.layout-row` primitive
 *     (styles/app.css — "LAYOUT PRIMITIVE (HG1 Round 5, S1)"); the vertical stat/
 *     disclosure spacing that previously came from a hand-set `margin-top` now comes
 *     from an existing structural class where one fits (`.metric-cell`'s own
 *     `gap`, `.block-sub`'s divider, `.contribution-row`'s list-divider pattern,
 *     `.chart-range-selector`, `.link-button`) — never a new rule. Where no existing
 *     class carried the exact spacing, the gap is simply narrower than before; this is
 *     a disclosed, minor visual trade-off, not a functional change, and is NOT verified
 *     in a browser (no browser exists in this environment — see this designer's report).
 *   - S4's placement exception for `exposure.currency`: `ctx.ui.renderQualifierNote`
 *     now renders directly beside the currency exposure bar chart in Block B, not only
 *     inside the (now Simple+-gated) claim card — the illustrative-FX-snapshot
 *     disclosure is present at the same rendering unit as every CNY-converted amount.
 *   - Every previously-hardcoded `depth: "quick"` override on a `ui.renderClaim` call
 *     is removed so these cards follow the shared APP.state.explanationMode instead
 *     (PD-0016 Part 1's "per-card ladders become local overrides" — the per-card ladder
 *     pill still exists and still works; it just no longer starts pinned to "quick"
 *     regardless of the global setting).
 *
 * NOT done, disclosed rather than silently skipped: the hero chart itself (lineCompare)
 * does not visually simplify further at Quick (fewer gridlines, no callout) — that would
 * require a new charts.js option, and charts.js is Phase 1's file, out of this pass's
 * write scope. The same chart renders at every depth; only the surrounding module
 * scaffolding changes. See this designer's report.
 *
 * I have no browser or JS runtime in this sandbox — I re-read this file after writing
 * it and traced every APP.data/APP.charts/APP.ui reference against CONTRACT.md and the
 * definitions in data.js/charts.js/shell.js, but none of that is the same as having
 * loaded the page. The PM should verify this surface in a real browser before relying
 * on it.
 */
(function () {
  "use strict";
  window.APP = window.APP || {};

  var SEVERITY_RANK = { WARNING: 0, ATTENTION: 1, OBSERVATION: 2 };

  // -----------------------------------------------------------------------
  // Small local DOM helpers — structural only. No literal hex/px value; no
  // inline element-style write anywhere in this file (HG1 Round 5, S1 item b) —
  // every layout/spacing need below is expressed through an existing class
  // (styles/app.css), never an inline style.
  // -----------------------------------------------------------------------
  function el(tag, className, text) {
    var e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  function blockShell(kickerText) {
    var b = el("div", "block");
    var header = el("div", "block-header");
    header.appendChild(el("span", "block-kicker", kickerText));
    b.appendChild(header);
    var body = el("div");
    b.appendChild(body);
    return { block: b, body: body };
  }

  function headline(text) {
    var h = el("h3", "mt-0", text);
    return h;
  }

  // A compact label+value cell. Uses `.metric-cell` (flex-column, `gap:4px`) so a
  // label, a rendered value, an evidence button, and/or a reference-point line stack
  // with consistent spacing with NO inline style needed. Callers gated behind minMode
  // "simple" or higher may use this freely; Block A's own always-visible-at-Quick hero
  // stat below builds its OWN plain (unclassed) cell instead, because AC-S5.3 forbids
  // `.metric-cell` from appearing anywhere in the Quick DOM.
  function statCell(labelText) {
    var cell = el("div", "metric-cell");
    cell.appendChild(el("div", "block-kicker", labelText));
    var mount = el("div");
    cell.appendChild(mount);
    return { cell: cell, mount: mount };
  }

  // Reuses `.link-button` (styles/app.css) for the clickable summary text — the same
  // underlined-link look this build already uses for "View full correlation matrix"
  // etc. — instead of a one-off inline cursor/color/weight style.
  //
  // HG1 Round 5 correction pass (Objective 1 — "Simple and Professional must differ
  // at rest," PM's HG1_ROUND5_PHASE2_VERIFICATION.md §4.1). ROOT CAUSE of the
  // byte-identical-at-rest defect: this helper's `openDefault` was never wired to
  // anything mode-dependent, so every disclosure built through it — including the two
  // below that wrap the ONLY claims on this route carrying `investorDetail`/
  // `professionalDetail` content (beta, concentration; see this designer's report for
  // the exact accounting) — stayed collapsed regardless of explanation mode. Switching
  // Simple -> Professional therefore changed the claim body markup but never made it
  // reachable without a SECOND, unrelated click. Fix: any disclosure that exists to
  // hold Professional-defining depth now has its call site pass
  // `{ openDefault: ui.explanationModeAtLeast("professional") }` — computed at the
  // call site (which already has `ui` in its closure, per this file's own
  // ctx.ui/ctx.data/ctx.charts-only boundary) and re-evaluated fresh on every mode
  // change, because every mode change already triggers a full renderRoute() that
  // rebuilds this whole block from scratch. Ordinary disclosures (the two
  // holdings-detail ones, "see all insights") are UNCHANGED — no second argument is
  // passed at their call sites, so they stay closed at every mode, matching
  // PD-0016's "Professional may still use disclosures for secondary detail."
  function disclosure(summaryText, opts) {
    opts = opts || {};
    var openDefault = opts === true || opts.openDefault === true;
    var d = document.createElement("details");
    // `data-module-id`, read by APP.uicheck (js/shell.js) — see that file's own
    // comment. Keyed on the (already-localized) summary text, which is unique
    // per disclosure on this route and stable across the two renders (Simple,
    // Professional) uicheck compares, since the language does not change between
    // them.
    d.setAttribute("data-module-id", summaryText);
    if (openDefault) d.open = true;
    var s = document.createElement("summary");
    s.className = "link-button";
    s.textContent = summaryText;
    d.appendChild(s);
    var body = el("div");
    d.appendChild(body);
    return { details: d, body: body };
  }

  function sortedInsights(insights) {
    return (insights || []).slice().sort(function (a, b) {
      var ra = SEVERITY_RANK[a.severity] === undefined ? 9 : SEVERITY_RANK[a.severity];
      var rb = SEVERITY_RANK[b.severity] === undefined ? 9 : SEVERITY_RANK[b.severity];
      return ra - rb;
    });
  }

  function sortByValueDesc(list, valueFn) {
    return (list || []).slice().sort(function (a, b) { return valueFn(b) - valueFn(a); });
  }

  function evidenceLinkFor(ui) {
    return function evidenceLink(mount, claim) {
      if (!claim) return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "evidence-control evidence-control-sm";
      btn.textContent = ui.t("common.evidenceMethodology");
      btn.addEventListener("click", function () { ui.openEvidence(claim.id); });
      mount.appendChild(btn);
    };
  }

  // -----------------------------------------------------------------------
  // Block A — "How am I doing?"
  //
  // HG1 Round 5, Phase 2 (S5) — the ONLY block that stays structurally visible at
  // every mode, because it IS the audit's own description of Quick: "one headline
  // conclusion... one figure at hero scale... one visual... one analogy sentence."
  // Everything else this block used to show at rest (the two extra gain/loss cells,
  // the benchmark-relative explanation card, the holdings section) is now behind an
  // internal ctx.ui.renderModule gate at minMode "simple" — present, one click away,
  // never deleted.
  // -----------------------------------------------------------------------
  function buildBlockA(ctx) {
    var data = ctx.data, charts = ctx.charts, ui = ctx.ui;
    var parts = blockShell(ui.t("ov.blockA"));
    var body = parts.body;
    var evidenceLink = evidenceLinkFor(ui);

    var returnClaim = data.getMetric("metric.return.1y");
    var totalValueClaim = data.getMetric("metric.totalPortfolioValue");
    var plAbs = data.getMetric("metric.pl.absolute");
    var plPct = data.getMetric("metric.pl.percent");
    var benchRel = data.getMetric("metric.benchmarkRelative");

    if (returnClaim) {
      body.appendChild(headline(ui.localizeClaimField(returnClaim, "conclusionQuick")));

      // HG1 M2 fix (PD-0016 Part 1 §1.3 — "rendered beside the literal figure, never
      // instead of it"). Confirmed defect: the analogy sentence below previously
      // rendered with NO numeric figure above it — the headline is prose only, and
      // metric.return.1y's own literal value was gated behind minMode "simple" inside
      // the Gain/Loss row further down. A sweep of everything above the analogy
      // returned zero numbers, and the first figure a reader actually reached was
      // Total Portfolio Value — a different quantity, not the one being analogized.
      // This cell renders metric.return.1y's OWN literal value through the SAME
      // one-renderer path (ui.renderMetricValue, CONTRACT.md §6 — "one renderer, no
      // exceptions") every other metric on this route uses, so it carries the same
      // glyph/color/state-chip treatment, directly ABOVE the analogy — giving the
      // analogy a real, correctly-labeled referent to sit beside. Deliberately built
      // WITHOUT statCell()/`.metric-cell` (AC-S5.3: that class may not appear anywhere
      // in the Quick DOM) — same construction as the Total Portfolio Value cell below.
      var returnCell = el("div");
      returnCell.appendChild(el("span", "block-kicker", ui.localizeClaimField(returnClaim, "label")));
      var returnMount = el("div");
      returnCell.appendChild(returnMount);
      ui.renderMetricValue(returnMount, returnClaim);
      evidenceLink(returnCell, returnClaim);
      body.appendChild(returnCell);

      // HG1 M2 fix — rendered directly beside (immediately after, same visual unit as)
      // the figure above, never instead of it (PD-0012 §2 / PD-0016 §1.3). The phrase
      // "the number above is the actual figure" (js/data.js's returnAnalogyQuick) is
      // now genuinely true at every mode, including Quick, because the cell
      // immediately above this paragraph IS that number — this is no longer an
      // assertion the DOM order could contradict, and Total Portfolio Value (a
      // different quantity) is never its referent.
      var analogyText = ui.localizeClaimField(returnClaim, "analogyQuick");
      if (analogyText) body.appendChild(el("p", "claim-simple", analogyText));
    }

    // The "one figure at hero scale" — Total Portfolio Value, always visible, a
    // DIFFERENT quantity from the return figure above (HG1 M2 fix — never the
    // analogy's referent; see the return cell above for that). State chips (the
    // freshness pill) stay at every mode (P3/P5) — never suppressed here. Deliberately
    // built WITHOUT statCell()/`.metric-cell`: AC-S5.3 forbids that class from
    // appearing anywhere in the Quick DOM, and this is the one cell that must still
    // render there.
    var heroCell = el("div");
    heroCell.appendChild(el("span", "block-kicker", ui.t("ov.totalPortfolioValue")));
    var heroMount = el("div");
    heroCell.appendChild(heroMount);
    if (totalValueClaim) {
      ui.renderMetricValue(heroMount, totalValueClaim);
    } else {
      // Defensive fallback only — metric.totalPortfolioValue should always resolve.
      heroMount.appendChild(el("span", "metric-number", ui.formatCurrency(data.getTotalPortfolioValue())));
    }
    var fresh = data.getFreshness();
    var leastFreshEntry = null;
    (fresh.axes || []).forEach(function (a) { if (a.axis === fresh.leastFreshAxis) leastFreshEntry = a; });
    if (leastFreshEntry) ui.renderFreshnessPill(heroMount, leastFreshEntry);
    evidenceLink(heroCell, totalValueClaim);
    body.appendChild(heroCell);

    // HG1 Round 5, Phase 2 (S5) — gain/loss (absolute and percent) duplicate what the
    // headline conclusion above already states qualitatively; moved behind Simple
    // rather than shown as a second/third always-visible stat.
    ui.renderModule(body, {
      minMode: "simple",
      label: ui.t("ov.gainLoss1y"),
      build: function (mount) {
        var strip = el("div", "layout-row");
        var glAbsCell = statCell(ui.t("ov.gainLoss1y"));
        if (plAbs) ui.renderMetricValue(glAbsCell.mount, plAbs);
        evidenceLink(glAbsCell.cell, plAbs);
        strip.appendChild(glAbsCell.cell);
        var glPctCell = statCell(ui.t("ov.gainLossPct"));
        if (plPct) ui.renderMetricValue(glPctCell.mount, plPct);
        strip.appendChild(glPctCell.cell);
        mount.appendChild(strip);
      }
    });

    // Hero visual — the largest, best-executed chart on the page (Direction B graft),
    // and the audit's "one visual." Always visible, every mode.
    var chartSection = el("div");
    var periodRow = el("div", "chart-range-selector");
    var ranges = ["1M", "3M", "6M", "1Y", "ALL"];
    var currentRange = "1Y";
    var chartMount = el("div");

    function renderHero() {
      chartMount.innerHTML = "";
      var series = data.getPortfolioSeries({ range: currentRange });
      // HG1 Condition 3 — drawdown shading removed from this hero chart, a considered
      // judgment call rather than an assumption either way (the owner's own instruction
      // was itself a hedge: "perhaps drawdown shading only when it helps"). Bundling a
      // portfolio-only drawdown band under a two-line comparison chart mixes two
      // different y-axes into one visual competing with the single question this chart
      // exists to answer in five seconds ("who's ahead, portfolio or benchmark") — and
      // Block C already surfaces the Max Drawdown figure, while Analytics' own dedicated
      // underwater chart (strengthened this same pass with a benchmark reference line)
      // is the considered place to answer "how deep did it fall." Kept out here so this
      // chart answers exactly one question well; see this pass's handoff for the fuller
      // account. showEndLabels/showHover default on (new this pass — direct end labels,
      // a persistent relative-performance callout, and a hover crosshair are what this
      // chart now uses to answer that one question faster).
      chartMount.appendChild(charts.lineCompare({
        dates: series.dates,
        series: { portfolio: series.portfolio, benchmark: series.benchmark },
        labelA: ui.t("ov.yourPortfolio"),
        labelB: ui.t("ov.benchmarkAcwiSeries")
      }));
    }

    ranges.forEach(function (r) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "depth-pill" + (r === currentRange ? " depth-pill-active" : "");
      btn.textContent = r;
      btn.addEventListener("click", function () {
        currentRange = r;
        periodRow.querySelectorAll(".depth-pill").forEach(function (b) { b.classList.remove("depth-pill-active"); });
        btn.classList.add("depth-pill-active");
        renderHero();
      });
      periodRow.appendChild(btn);
    });

    chartSection.appendChild(periodRow);
    chartSection.appendChild(chartMount);
    renderHero();

    var askChartMount = el("div");
    ui.aiAffordance(askChartMount, {
      label: ui.t("ov.askAboutThisChart"),
      contextLabel: "portfolio vs. benchmark performance",
      contextClaims: ["metric.return.1y", "metric.benchmarkRelative"]
    });
    chartSection.appendChild(askChartMount);
    body.appendChild(chartSection);

    // The "why" behind the chart — full claim ladder, caveat included at Simple/
    // Professional only (never at Quick — appendCaveatSlot's own depth gate,
    // js/shell.js). HG1 Round 5, Phase 2 (S5) — kept ALWAYS VISIBLE, deliberately NOT
    // module-gated, unlike the sections below: metric.benchmarkRelative is the one
    // claim on this surface whose STATE CHIP (the "Limited comparability" flag, when
    // its sufficiency reaches LIMITED) the audit names explicitly as required to stay
    // at every mode ("the state chips stay ... they render as short tokens per S4").
    // The appendCaveatSlot depth-gate (js/shell.js) already keeps this card short at
    // Quick on its own — no caveat body, no reference-point line — without needing to
    // hide the card, and its own chip, entirely.
    if (benchRel) {
      var benchMount = el("div");
      ui.renderClaim(benchMount, benchRel, {});
      body.appendChild(benchMount);
    }

    // Expandable key holdings — top 5 by value, consistent with Block C's own
    // concentration figures (same getConcentration() call, not re-derived).
    // HG1 Round 5, Phase 2 (S5) — "the holdings table" is named explicitly as hidden
    // at rest in Quick; gated behind Simple, reachable in one click.
    var concentration = data.getConcentration();
    var top5Holdings = (concentration.topPositions || []).map(function (p) {
      return data.getHolding(p.id);
    }).filter(Boolean);

    ui.renderModule(body, {
      minMode: "simple",
      // HG1 ux_planning revision (review-07, P1 item 6) — same defect shape, and the
      // same fix already applied to buildBlockB above ("HG1 M3 fix"): when this module
      // is collapsed (below Simple), APP.ui.renderModule (js/shell.js) renders `label`
      // as the <summary> disclosure-toggle text; once expanded, that <summary> stays
      // visible ALONGSIDE the body build() renders below it — so `label` and the
      // `.block-kicker` div immediately below used to be the identical string
      // ("主要持仓" / "Major Holdings") shown twice, once as the toggle and once as the
      // card's own kicker. `id` is kept as the module's stable name (unaffected by this
      // change) so APP.uicheck's cross-mode module-identity tracking still resolves the
      // same module before and after; only the VISIBLE disclosure-toggle text changes,
      // to the same generic phrase buildBlockB already established for this exact class
      // of fix rather than inventing a second one.
      id: ui.t("ov.majorHoldings"),
      label: ui.t("common.showSectionDetail"),
      build: function (mount) {
        mount.appendChild(el("div", "block-kicker", ui.t("ov.majorHoldings")));
        // HG1 Round 5 correction pass (Objective 3 — the owner's Problem 2, "the
        // green bar still doesn't seem to be on the same row... centering the
        // holdings or enhancing the visual effects to reduce the empty space").
        // Same root cause and same fix as Block B's donut, above: this bar chart's
        // own `.chart-family-bar` caps at 350px and centres itself via
        // `margin-inline: auto` (Phase 1), but its ENCLOSING mount was unbounded, so
        // that centring happened inside a ~1310px box. `.compact-chart-card`'s
        // default (420px) covers the standard bar family with room to spare.
        var barMount = el("div", "compact-chart-card");
        if (top5Holdings.length) {
          barMount.appendChild(charts.bar({
            // HG1 ux_planning revision (review-06, B2) — ui.holdingDisplayName(h)
            // resolves to the same Chinese name Scenario Lab's own prose and
            // Portfolio's holdings table now use, instead of the raw (always-English)
            // h.name.
            items: top5Holdings.map(function (h) { return { label: ui.holdingDisplayName(h), value: h.marketValueUSD }; }),
            valueFormat: function (v) { return ui.formatCurrency(v); }
          }));
        }
        mount.appendChild(barMount);

        var allHoldings = sortByValueDesc(data.getHoldings(), function (h) { return h.marketValueUSD; });
        var top5Disc = disclosure(ui.tf("ov.holdingsDetailTop5", { n: allHoldings.length }));
        top5Disc.body.appendChild(buildHoldingsTable(ctx, top5Holdings));
        mount.appendChild(top5Disc.details);

        var allDisc = disclosure(ui.tf("ov.showEntirePortfolio", { n: allHoldings.length }));
        allDisc.body.appendChild(buildHoldingsTable(ctx, allHoldings));
        mount.appendChild(allDisc.details);

        var viewAllBtn = document.createElement("button");
        viewAllBtn.type = "button";
        viewAllBtn.className = "evidence-control";
        viewAllBtn.textContent = ui.t("ov.viewFullHoldings");
        viewAllBtn.addEventListener("click", function () { ctx.navigateTo("portfolio/portfolio"); });
        mount.appendChild(viewAllBtn);
      }
    });

    return parts.block;
  }

  function buildHoldingsTable(ctx, holdings) {
    var data = ctx.data, ui = ctx.ui;
    var table = document.createElement("table");
    table.className = "data-table";
    var thead = document.createElement("thead");
    var hr = document.createElement("tr");
    // HG1 Condition 1C — numeric-column headers marked "num" so they right-align over
    // their own .num data cells below (same fix applied to Portfolio's fuller ledger
    // table in js/surfaces/portfolio.js). This compact table intentionally has fewer
    // columns than Portfolio's — a documented different row type, not an oversight: it
    // is a condensed top-5/full-portfolio SUMMARY embedded on Overview (no Qty/Avg
    // Cost/Price/Freshness/Actions, which belong to the full ledger view) — see
    // CONTRACT.md's "Checkpoint A visual-polish pass" addendum for the recorded reason.
    // i18n (§12) — table headers are structural chrome, translated; scope="col" (§23 —
    // semantic tables) marks each header as the header of its own column for assistive
    // tech, which plain visual styling alone never conveyed.
    [
      { label: ui.t("table.position"), num: false },
      { label: ui.t("table.weight"), num: true },
      { label: ui.t("table.marketValue"), num: true },
      { label: ui.t("table.unrealizedGl"), num: true },
      { label: ui.t("table.riskMetrics"), num: true }
    ].forEach(function (col) {
      var th = el("th", col.num ? "num" : null, col.label);
      th.setAttribute("scope", "col");
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    var tbody = document.createElement("tbody");
    (holdings || []).forEach(function (h) {
      var tr = document.createElement("tr");
      // HG1 ux_planning revision (review-06, B2) — same shared display-name lookup as
      // the bar chart above; `h.id` (canonical ticker) is still always shown alongside
      // it, unchanged.
      tr.appendChild(el("td", null, ui.holdingDisplayName(h) + " (" + h.id + ")"));
      var wcell = document.createElement("td");
      wcell.className = "num";
      // HG1 round-4 §6.3 — a static weight LEVEL, never signed; formatPercent's new
      // default (unsigned) is correct here without an explicit override.
      wcell.textContent = ui.formatPercent(h.pctOfPortfolio, 1);
      tr.appendChild(wcell);
      var vcell = document.createElement("td");
      vcell.className = "num";
      vcell.textContent = ui.formatCurrency(h.marketValueUSD);
      tr.appendChild(vcell);
      var glcell = document.createElement("td");
      glcell.className = "num";
      var glClaim = data.getHoldingClaim(h.id);
      if (glClaim) ui.renderMetricValue(glcell, glClaim);
      else glcell.appendChild(el("span", "text-faint", "·"));
      tr.appendChild(glcell);
      var riskCell = document.createElement("td");
      riskCell.className = "num";
      var riskClaim = data.getInstrumentRiskClaim(h.id);
      if (riskClaim) ui.renderMetricValue(riskCell, riskClaim);
      else riskCell.appendChild(el("span", "text-faint", "·"));
      tr.appendChild(riskCell);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    // HG1 round-4 §20 — controlled horizontal scrolling, scoped to this table only (not
    // the page), is the chosen narrow-width strategy (see styles/app.css's own comment
    // for the full account of what was considered and not taken).
    var wrap = el("div", "table-scroll-wrap");
    wrap.appendChild(table);
    return wrap;
  }

  // -----------------------------------------------------------------------
  // Block B — "What is driving the portfolio?"
  //
  // HG1 Round 5, Phase 2 (S5) — the entire block body is one ctx.ui.renderModule
  // gate at minMode "simple" ("the exposure charts" are named explicitly as hidden
  // at rest in Quick); the block's own heading stays visible as chrome, and the
  // collapsed affordance is labelled with that same heading — a named,
  // one-click-reachable module, never deleted.
  // -----------------------------------------------------------------------
  function buildBlockB(ctx) {
    var data = ctx.data, charts = ctx.charts, ui = ctx.ui;
    var block = el("div", "block");
    var header = el("div", "block-header");
    header.appendChild(el("span", "block-kicker", ui.t("ov.blockB")));
    block.appendChild(header);

    ui.renderModule(block, {
      minMode: "simple",
      // HG1 M3 fix — `label` no longer repeats the `.block-kicker` text immediately
      // above (that produced an exact-duplicate heading/summary pair when collapsed).
      // `id` is kept as the block's OWN name (stable across languages/modes) so
      // APP.uicheck's cross-mode module-identity tracking is unaffected — only the
      // VISIBLE affordance text changes.
      id: ui.t("ov.blockB"),
      label: ui.t("common.showSectionDetail"),
      build: function (body) {
        var geo = data.getExposure("economicGeography");
        if (geo.claim) body.appendChild(headline(ui.localizeClaimField(geo.claim, "conclusionQuick")));

        var mainRow = el("div", "layout-row");

        var assetClass = data.getExposure("assetClass");
        // HG1 Round 5 correction pass (Objective 3 — content-sensitive card sizing;
        // the owner's decision, "centering alone is not sufficient..."). Measured
        // worst case: a 150px donut in a 1310px block (HG1_ROUND5_PHASE2_
        // VERIFICATION.md §5). Root cause was one level up from the chart itself:
        // `.layout-row`'s default child rule (`flex: 1 1 240px`, styles/app.css)
        // makes a LONE child grow to the row's full width, so the donut's own
        // `margin-inline: auto` (Phase 1) was centring it inside an oversized box,
        // not binding the box itself. `.compact-chart-card` (styles/app.css, new
        // this pass) opts this cluster OUT of that stretch and gives it its own
        // bound instead — the donut, its legend, and the "largest allocation"
        // caption together, not just the SVG — so the residual becomes a
        // symmetric page/card margin (which the owner accepted in P8_2.png) rather
        // than empty space stranded inside an oversized card.
        var donutMount = el("div", "compact-chart-card");
        if (assetClass.segments && assetClass.segments.length) {
          // PD-0015 Part 2 — asset-class DISPLAY labels are now translated (the owner's own
          // ruling covers this alongside sector labels: "sector AND asset-class taxonomy
          // display labels"). The underlying `getExposure("assetClass")` grouping (js/data.js)
          // is untouched — it already keys off the canonical `assetClass` field, never a
          // label — only this rendering step's copy of the segments gets a translated
          // `label`, per PD-0015 §2.3's "translate what a human reads, never what a system
          // joins on."
          var assetClassDisplaySegs = assetClass.segments.map(function (s) {
            return { label: ui.translateTaxonomyLabel(s.label), value: s.value, pct: s.pct };
          });
          donutMount.appendChild(charts.donut({
            segments: assetClassDisplaySegs.map(function (s) { return { label: s.label, value: s.value }; }),
            centerLabel: ui.t("ov.assetMix")
          }));
          // HG1 round-4 (§4.1 "fix shared causes" / §9.1's donut-labeling requirement,
          // applied everywhere a donut appears, not only Scenario Lab) — a donut with no
          // legend forces a reader to guess which wedge is which from color alone. This is
          // a static allocation LEVEL, not a change — formatPercent's new default (unsigned)
          // is correct here without an explicit override.
          ui.renderDonutLegend(donutMount, assetClassDisplaySegs);
          var topSeg = assetClassDisplaySegs[0];
          donutMount.appendChild(el("p", "text-faint", ui.tf("ov.largestAssetClassAllocation", { label: topSeg.label, pct: ui.formatPercent(topSeg.pct, 1) })));
        }
        mainRow.appendChild(donutMount);
        body.appendChild(mainRow);

        var askExposureMount = el("div");
        ui.aiAffordance(askExposureMount, {
          label: ui.t("ov.summarizeExposures"),
          contextLabel: "exposure",
          contextClaims: ["exposure.assetClass", "exposure.sector", "exposure.economicGeography", "exposure.currency"]
        });
        body.appendChild(askExposureMount);

        // HG1 Round 5 correction pass (Objective 1). This disclosure holds the
        // sector/geography/currency DECOMPOSITION — exactly the content PD-0012 §2
        // names as part of what Professional adds ("decomposition") that Simple does
        // not. Auto-opens at Professional so that depth is visible without a second,
        // unrelated click; stays a normal one-click disclosure at Quick/Simple.
        var disc = disclosure(ui.t("ov.seeBreakdown"), { openDefault: ui.explanationModeAtLeast("professional") });
        // HG1 round-4 §6.2 (confirmed defect, reviews/gates/HG1_ROUND4_VERIFICATION.md §3):
        // js/data.js's getExposure("sector") mixes real sectors (Information Technology,
        // Communication Services, ...) with values that are not sectors at all (Diversified
        // Fund, Government Bonds, Structured Product) — a polished bar chart made a fund
        // holding look like a sector peer of an operating company. ETF look-through stays
        // out of scope (§26); the fix instead separates known direct sector exposure from
        // pooled/fund, fixed-income, and structured/unsupported exposure, via
        // ctx.ui.classifySectorExposure (js/shell.js) — a presentation-layer regrouping of
        // already-real per-holding data (assetClass/sector/marketValueUSD), not a new
        // analytical methodology. See that helper's own comment for exactly what a future
        // data.js accessor should provide instead of this client-side fallback.
        var sectorSplit = ui.classifySectorExposure(data.getHoldings(), data.getTotalPortfolioValue());
        if (sectorSplit.sectorSegments.length || sectorSplit.nonSectorSegments.length) {
          disc.body.appendChild(el("div", "block-kicker", ui.t("ov.sectorExposureDirect")));
          if (sectorSplit.sectorSegments.length) {
            // HG1 Condition 3 — "country, currency, sector and asset-class charts should use
            // consistent horizontal-bar conventions." Every exposure bar on this surface and on
            // Analytics now reads through the same ctx.ui.formatExposureSegment(seg) — percent-
            // of-portfolio first, dollar amount second — instead of each surface having picked
            // its own convention (this surface previously showed dollar only; Analytics'
            // exposureBarChart previously showed percent only, for the identical segment shape).
            // PD-0015 Part 2 — classifySectorExposure's segments now carry a canonical
            // `key` (never translated, matches js/data.js's own `sector` field exactly) and
            // no `label` at all; ui.labelForSectorSegment translates the display text at
            // THIS render step, never inside the classifier itself (PD-0015 §2.3: "translate
            // what a human reads, never what a system joins on").
            disc.body.appendChild(charts.bar({
              items: sectorSplit.sectorSegments.map(function (s) { return { label: ui.labelForSectorSegment(s, false), value: s.value, displayValue: ui.formatExposureSegment(s) }; })
            }));
          } else {
            disc.body.appendChild(el("p", "text-faint", ui.t("ov.noDirectEquitySector")));
          }
          if (sectorSplit.nonSectorSegments.length) {
            disc.body.appendChild(el("p", "claim-caveat", ui.t("ov.notSectorsCaveat")));
            disc.body.appendChild(charts.bar({
              items: sectorSplit.nonSectorSegments.map(function (s) { return { label: ui.labelForSectorSegment(s, true), value: s.value, displayValue: ui.formatExposureSegment(s) }; })
            }));
          }
        }

        var geoRow = el("div", "layout-row");
        var listingMarket = data.getExposure("listingMarket");
        var byMarket = el("div");
        byMarket.appendChild(el("div", "block-kicker", ui.t("ov.byListingMarket")));
        if (listingMarket.segments && listingMarket.segments.length) {
          // HG1 round-4, second bilingual pass — listing-market segment labels ("US"/"HK"/
          // "CN") are the SAME sleeve concept the correlation/contribution blocks already
          // translate; ui.translateSleeveLabel reuses that exact established map (§3 of the
          // coordinator's constraints), never a separately invented term.
          byMarket.appendChild(charts.bar({
            items: listingMarket.segments.map(function (s) { return { label: ui.translateSleeveLabel(s.label), value: s.value, displayValue: ui.formatExposureSegment(s) }; })
          }));
        }
        geoRow.appendChild(byMarket);

        var byGeo = el("div");
        byGeo.appendChild(el("div", "block-kicker", ui.t("ov.byEconomicGeography")));
        if (geo.segments && geo.segments.length) {
          // Economic-GEOGRAPHY labels ("US"/"China") are a different dimension from listing
          // market (business domicile, not where listed) — translateGeographyLabel uses its
          // own small country-name map, deliberately never the sleeve map above (see
          // js/shell.js's comment on why conflating the two would be actively wrong, not
          // just untranslated).
          byGeo.appendChild(charts.bar({
            items: geo.segments.map(function (s) { return { label: ui.translateGeographyLabel(s.label), value: s.value, displayValue: ui.formatExposureSegment(s) }; })
          }));
        }
        geoRow.appendChild(byGeo);
        disc.body.appendChild(geoRow);

        var currency = data.getExposure("currency");
        var currMount = el("div", "block-sub");
        currMount.appendChild(el("div", "block-kicker", ui.t("ov.currencyExposure")));
        if (currency.claim) {
          var currClaimMount = el("div");
          // HG1 ux_planning revision (review-06, secondary — "section CURRENCY
          // EXPOSURE immediately above card kicker CURRENCY EXPOSURE") — showLabel:
          // false: the block-kicker just above and this claim's own label
          // (exposure.currency, js/data.js) are the identical text ("Currency
          // Exposure"/"货币敞口"); renderClaim no longer repeats it inside the card.
          ui.renderClaim(currClaimMount, currency.claim, { showLabel: false });
          currMount.appendChild(currClaimMount);
        }
        // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.4's exposure.currency
        // placement exception). The illustrative-FX-snapshot disclosure renders directly
        // beside the currency bar chart below — the rendering unit that actually shows the
        // CNY-converted amounts — independent of whether the claim card above is collapsed.
        ui.renderQualifierNote(currMount, currency.claim);
        if (currency.segments && currency.segments.length) {
          currMount.appendChild(charts.bar({
            items: currency.segments.map(function (s) { return { label: s.label, value: s.value, displayValue: ui.formatExposureSegment(s) }; })
          }));
        }
        disc.body.appendChild(currMount);

        body.appendChild(disc.details);
      }
    });

    return block;
  }

  // -----------------------------------------------------------------------
  // Block C — "What are the main risks?"
  //
  // HG1 Round 5, Phase 2 (S5) — gated at minMode "simple" as a whole: "the
  // six-statistic risk inventory, the statistics grid, the rolling chart" are all
  // named explicitly as hidden at rest in Quick.
  // -----------------------------------------------------------------------
  function buildBlockC(ctx) {
    var data = ctx.data, charts = ctx.charts, ui = ctx.ui;
    var block = el("div", "block");
    var header = el("div", "block-header");
    header.appendChild(el("span", "block-kicker", ui.t("ov.blockC")));
    block.appendChild(header);

    ui.renderModule(block, {
      minMode: "simple",
      // HG1 M3 fix — see Block B's identical comment above.
      id: ui.t("ov.blockC"),
      label: ui.t("common.showSectionDetail"),
      build: function (body) {
        var vol = data.getMetric("metric.volatility");
        var beta = data.getMetric("metric.beta");
        var sharpe = data.getMetric("metric.sharpe");
        var sortino = data.getMetric("metric.sortino");
        var maxDD = data.getMetric("metric.maxDrawdown");
        var var95 = data.getMetric("metric.var95");
        var concentration = data.getMetric("metric.concentration");

        if (vol) body.appendChild(headline(ui.localizeClaimField(vol, "conclusionQuick")));

        // HG1 round-4 §5.1 — the Risk Overview is reorganized around the investor
        // questions the owner named, not a flat metric inventory: Overall risk -> Market
        // sensitivity -> Downside -> Risk-adjusted performance -> Risk drivers (this last
        // group continues below in the existing rolling-volatility/concentration chart row,
        // which already IS the "risk drivers" content — grouped here by an explicit label
        // rather than left implicit). Tracking error is grouped with Market sensitivity
        // (it measures dispersion from the benchmark, the same relationship beta
        // describes) and alpha is not shown on this compact Overview strip at all (it
        // already has its own dedicated presentation on Analytics' SML block) — an
        // assumption stated here, not invented silently.
        var riskGroups = [
          { heading: ui.t("riskGroup.overallRisk"), items: [vol] },
          { heading: ui.t("riskGroup.marketSensitivity"), items: [beta] },
          { heading: ui.t("riskGroup.downside"), items: [maxDD, var95] },
          { heading: ui.t("riskGroup.riskAdjusted"), items: [sharpe, sortino] }
        ];
        riskGroups.forEach(function (group, idx) {
          var present = group.items.filter(function (c) { return !!c; });
          if (!present.length) return;
          // `.block-sub` (existing class — a top border + top margin/padding) reused as a
          // section divider between risk-question groups; its own CSS gives the FIRST
          // occurrence the same top border as the rest (unlike `.contribution-row`, which
          // special-cases `:first-child` to remove it) — a visible rule above "Overall
          // risk" as well as the groups after it, which is an acceptable, minor visual
          // difference from a bespoke top-margin-only first group, not a functional one.
          var groupWrap = el("div", "block-sub");
          groupWrap.appendChild(el("div", "block-subheading", group.heading));
          var strip = el("div", "layout-row");
          present.forEach(function (claim) {
            // HG1 round-4, second bilingual pass — reads claim.label via localizeClaimField
            // instead of a hardcoded English name duplicated here: this both removes a
            // second, independently-maintained copy of js/data.js's own metric name AND
            // means this cell picks up a Chinese label automatically the moment js/data.js
            // populates claim.i18n.zh.label (not yet populated for `label` specifically as
            // of this pass — see this designer's handoff — so this still displays English
            // today, but correctly, not from a redundant hardcoded string).
            var cell = statCell(ui.localizeClaimField(claim, "label"));
            ui.renderMetricValue(cell.mount, claim);
            // HG1 round-4 §5.2 — "comparative claims need visible comparative evidence."
            // metric.volatility and metric.maxDrawdown already carry a benchmark-relative
            // referencePoint string in js/data.js (e.g. "MSCI ACWI annualized volatility:
            // 12.1%") — it existed, but was only ever shown after clicking into the
            // Professional-depth ladder. Shown here, faintly, at rest, right under the
            // primary number, so a comparative claim is never asserted without its
            // comparison visibly nearby (P4) even before the reader opens Evidence.
            var localizedRef = ui.localizeClaimField(claim, "referencePoint");
            if (localizedRef) cell.cell.appendChild(el("p", "metric-cell-conclusion", localizedRef));
            strip.appendChild(cell.cell);
          });
          groupWrap.appendChild(strip);
          body.appendChild(groupWrap);
        });

        var chartRow = el("div", "block-sub");
        chartRow.appendChild(el("div", "block-subheading", ui.t("riskGroup.riskDrivers")));
        var chartsInnerRow = el("div", "layout-row");

        var volSection = el("div");
        volSection.appendChild(el("div", "block-kicker", ui.t("ov.rolling90dVolatility")));
        var rollSeries = data.getRollingVolatilitySeries({ range: "1Y" });
        // HG1 Condition 3 (round 3) — same windowLabel text as Analytics' identical chart
        // (js/surfaces/analytics.js), since this is the same APP.charts.rollingLine
        // primitive reused here: one rolling-analytics grammar, not a per-surface variant.
        volSection.appendChild(charts.rollingLine({ dates: rollSeries.dates, series: rollSeries, windowLabel: ui.t("chart.rollingWindow90d") }));
        chartsInnerRow.appendChild(volSection);

        var concSection = el("div");
        concSection.appendChild(el("div", "block-kicker", ui.t("ov.top5Concentration")));
        if (concentration) {
          var concValueMount = el("div");
          ui.renderMetricValue(concValueMount, concentration);
          concSection.appendChild(concValueMount);
        }
        var topPositions = data.getConcentration().topPositions || [];
        if (topPositions.length) {
          // HG1 ux_planning revision (review-07, P0 item 1 sweep) — this Block C
          // top-5-concentration bar (distinct from the majorHoldings bar above, which
          // already went through ui.holdingDisplayName) still read the raw, always-
          // English `p.name` directly. Same holding-shaped objects as the majorHoldings
          // bar's `top5Holdings` (both come from getConcentration().topPositions), so
          // the same helper applies unchanged.
          concSection.appendChild(charts.bar({
            items: topPositions.map(function (p) { return { label: ui.holdingDisplayName(p), value: p.value }; }),
            valueFormat: function (v) { return ui.formatCurrency(v); }
          }));
        }
        chartsInnerRow.appendChild(concSection);
        chartRow.appendChild(chartsInnerRow);
        body.appendChild(chartRow);

        var askRiskMount = el("div");
        ui.aiAffordance(askRiskMount, {
          label: ui.t("ov.explainThisRisk"),
          contextLabel: "risk statistics",
          contextClaims: ["metric.volatility", "metric.beta", "metric.maxDrawdown", "metric.concentration"]
        });
        body.appendChild(askRiskMount);

        // HG1 Round 5 correction pass (Objective 1 — the measured defect's direct
        // cause). This is the ONLY place on this route the beta/sortino/concentration
        // claims' `investorDetail`/`professionalDetail` fields ever render — before
        // this fix they stayed behind this unrelated "explain in full" click at every
        // mode, so Professional never looked any different from Simple at rest.
        // Auto-opens once the global mode reaches Professional.
        var disc = disclosure(ui.t("ov.explainRiskStatsFull"), { openDefault: ui.explanationModeAtLeast("professional") });
        [beta, sortino, concentration].forEach(function (claim, i) {
          if (!claim) return;
          // `.contribution-row` (existing class, Analytics' contribution-to-risk list) —
          // a top-border divider between stacked claim cards, with no divider on the
          // first, via its own `:first-child` rule — reused here for the identical "a
          // short list of stacked cards" shape.
          var mount = el("div", "contribution-row");
          ui.renderClaim(mount, claim, {});
          disc.body.appendChild(mount);
        });
        body.appendChild(disc.details);
      }
    });

    return block;
  }

  // -----------------------------------------------------------------------
  // Block D — "What deserves my attention?"
  //
  // HG1 Round 5, Phase 2 (S5) — gated at minMode "simple" as a whole, consistent
  // with Blocks B/C/E; nothing here carries a mandatory state chip of its own (the
  // insight severity glyphs are a judgment classification, not a P3/P5 sufficiency
  // or freshness chip), so gating the whole block does not suppress anything P3/P5
  // requires to stay visible at Quick.
  // -----------------------------------------------------------------------
  function buildBlockD(ctx) {
    var data = ctx.data, ui = ctx.ui;
    var block = el("div", "block");
    var header = el("div", "block-header");
    header.appendChild(el("span", "block-kicker", ui.t("ov.blockD")));
    block.appendChild(header);

    ui.renderModule(block, {
      minMode: "simple",
      // HG1 M3 fix — see Block B's identical comment above.
      id: ui.t("ov.blockD"),
      label: ui.t("common.showSectionDetail"),
      build: function (body) {
        var all = sortedInsights(data.getInsights());
        if (all.length) {
          // insight.claim (js/data.js's own INSIGHTS array) has no i18n field as of this
          // pass — a real, specific residual gap distinct from the metric/exposure claims
          // js/data.js's owner already translated; stated plainly rather than silently
          // left untested. ui.localizeClaimField is still called (not a bare `all[0].claim`
          // read) so this line localizes automatically, with no further change needed
          // here, the moment insight objects gain one.
          body.appendChild(headline(ui.localizeClaimField(all[0], "claim")));
          var warnCount = all.filter(function (i) { return i.severity === "WARNING"; }).length;
          var attnCount = all.filter(function (i) { return i.severity === "ATTENTION"; }).length;
          body.appendChild(el("p", "text-faint", warnCount + " " + ui.t("ov.warningCount") +
            " · " + attnCount + " " + ui.t("ov.attentionItemCount") + " " + ui.t("ov.acrossPortfolio")));

          var topMount = el("div");
          ui.renderInsightsList(topMount, all.slice(0, 2), { mode: "compact" });
          body.appendChild(topMount);

          var disc = disclosure(ui.tf("common.seeAllInsights", { n: all.length }));
          ui.renderInsightsList(disc.body, all, { mode: "full" });
          body.appendChild(disc.details);
        } else {
          body.appendChild(el("p", "text-faint", ui.t("ov.noInsightsFlagged")));
        }
      }
    });

    return block;
  }

  // -----------------------------------------------------------------------
  // Block E — Portfolio Brief (AI narrative, P1 citation-chip mechanism)
  //
  // HG1 Round 5, Phase 2 (S5) — gated at minMode "simple" as a whole. Its content
  // substantially restates figures already summarized in Block A's headline +
  // hero stat, in fuller narrative form — supporting elaboration, not the "minimal
  // supporting detail" Quick is scoped to (PD-0012 §2).
  // -----------------------------------------------------------------------
  function buildBlockE(ctx) {
    var data = ctx.data, ui = ctx.ui;
    var block = el("div", "block");
    var header = el("div", "block-header");
    header.appendChild(el("span", "block-kicker", ui.t("ov.blockE")));
    block.appendChild(header);

    ui.renderModule(block, {
      minMode: "simple",
      // HG1 M3 fix — see Block B's identical comment above.
      id: ui.t("ov.blockE"),
      label: ui.t("common.showSectionDetail"),
      build: function (body) {
        var returnClaim = data.getMetric("metric.return.1y");
        var benchRel = data.getMetric("metric.benchmarkRelative");
        var vol = data.getMetric("metric.volatility");
        var concentration = data.getMetric("metric.concentration");
        var fx = data.getMetric("metric.fxAttribution");

        var narrative = el("div", "ai-narrative");
        var htmlParts = [];

        // HG1 round-4, second bilingual pass — every connective sentence below is now
        // built from ui.tf(key, vars) rather than hand-concatenated English, with the
        // chip HTML (the only claim-bearing content, P1) substituted in as a template
        // variable — never itself translated (a chip's own displayed number/label already
        // localizes independently via ui.chipHTML -> formatClaimValue ->
        // localizeClaimField, see js/shell.js).
        if (returnClaim && benchRel) {
          var direction = (benchRel.value >= 0) ? ui.t("ov.outperformed") : ui.t("ov.underperformed");
          htmlParts.push(ui.tf("ov.returnedSentence", {
            chip: ui.chipHTML(returnClaim), direction: direction, chip2: ui.chipHTML(benchRel)
          }));
          if (benchRel.caveat) {
            htmlParts.push(" " + escapeHtml(ui.localizeClaimField(benchRel, "caveat")));
          }
        }
        if (fx) {
          var fxDirection = fx.value < 0 ? ui.t("ov.fxReduced") : ui.t("ov.fxAddedTo");
          htmlParts.push(" " + ui.tf("ov.fxSentence", {
            direction: fxDirection, chip: ui.chipHTML(fx, ui.formatPercent(Math.abs(fx.value), 1))
          }));
        }
        if (vol) {
          // Note: metric.volatility's own referencePoint field embeds a formatted
          // percentage (the benchmark's own volatility) — that string is NOT wrapped
          // in a chip, so it must never be dropped into this .ai-narrative block as
          // plain text (would put a bare digit outside a chip, the exact P1 failure
          // mode this surface exists to prevent). The comparison is still reachable
          // via this chip's own Evidence popout, which resolves to referencePoint.
          htmlParts.push(" " + ui.tf("ov.volatilitySentence", { chip: ui.chipHTML(vol) }));
        }
        if (concentration) {
          htmlParts.push(" " + ui.tf("ov.concentrationSentence", { chip: ui.chipHTML(concentration) }));
        }

        narrative.innerHTML = htmlParts.join("");
        body.appendChild(narrative);

        var askMount = el("div");
        ui.aiAffordance(askMount, {
          label: ui.t("ov.askFollowUpBtn"),
          contextLabel: "portfolio brief",
          contextClaims: ["metric.return.1y", "metric.benchmarkRelative", "metric.volatility",
            "metric.concentration", "metric.fxAttribution"]
        });
        body.appendChild(askMount);

        // Dev-time self-check only — never blocks rendering, just a console.warn if a
        // digit slipped outside a .chip wrapper. See CONTRACT.md §6A.
        if (ui.checkNarrativeSafety) {
          try { ui.checkNarrativeSafety(block); } catch (e) { /* non-fatal, dev aid only */ }
        }
      }
    });

    return block;
  }

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // -----------------------------------------------------------------------
  // Registration
  // -----------------------------------------------------------------------
  window.APP.registerSurface("overview", {
    group: "overview",
    render: function (mountEl, ctx) {
      mountEl.innerHTML = "";
      var data = ctx.data, ui = ctx.ui;

      // HG1 M3 fix — this surface-local freshness strip is REMOVED (confirmed defect:
      // it rendered a second time here, duplicating js/shell.js's persistent global
      // header strip — `#app-freshness-global`, via renderGlobalHeader() — so
      // "Least fresh:" appeared twice in the DOM on every render of this route). D5.1's
      // requirement ("persistent, never folded into a block") is satisfied by the
      // GLOBAL header, which renders on every route including this one; state chips
      // (P3/P5) still stay visible at every explanation mode there — nothing is
      // suppressed, only the duplicate copy is removed.
      if (data.meta && data.meta.asOf) {
        // data.meta.asOf/reportingCurrency (a date string and a currency code) are
        // canonical/data values, never translated themselves — only the surrounding
        // sentence is.
        var snapshotLine = el("p", "text-faint", ui.tf("ov.snapshotAsOf", {
          date: data.meta.asOf, ccy: data.meta.reportingCurrency || "USD"
        }));
        // PD-0015 Part 1 — a small, non-interactive mode indicator, inline with the
        // snapshot sentence it clarifies. This build only ever computes the Historical
        // as-of mode (never a simulated Current/Live feed), so the badge always names
        // that mode; see Settings > Valuation Time Mode for the full two-mode contract.
        // Not a toggle — see openSettings() note.
        var valBadge = el("span", "valuation-mode-badge");
        valBadge.textContent = ui.tf("valuationMode.badge", { date: data.meta.asOf });
        snapshotLine.appendChild(valBadge);
        mountEl.appendChild(snapshotLine);
      }

      try { mountEl.appendChild(buildBlockA(ctx)); } catch (e) { console.error("[overview] Block A failed", e); }
      try { mountEl.appendChild(buildBlockB(ctx)); } catch (e) { console.error("[overview] Block B failed", e); }
      try { mountEl.appendChild(buildBlockC(ctx)); } catch (e) { console.error("[overview] Block C failed", e); }
      try { mountEl.appendChild(buildBlockD(ctx)); } catch (e) { console.error("[overview] Block D failed", e); }
      try { mountEl.appendChild(buildBlockE(ctx)); } catch (e) { console.error("[overview] Block E failed", e); }
    }
  });
})();
