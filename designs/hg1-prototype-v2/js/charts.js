/*
 * charts.js — hand-authored SVG chart primitives. No charting library exists in this
 * environment and none can be fetched (zero network egress), so every chart here is
 * built with raw SVG DOM nodes.
 *
 * Contract: every APP.charts.<name>(options) function RETURNS an SVGSVGElement. It does
 * NOT append itself anywhere. Callers mount it themselves:
 *   mountEl.appendChild(APP.charts.lineCompare({ ... }));
 * This keeps the API composable and avoids double-render bugs from a function that both
 * renders and appends.
 *
 * All colors are read from CSS custom properties (theme tokens) at draw time via
 * getComputedStyle, so charts stay in sync with styles/tokens.css without duplicating
 * the palette here.
 */
(function () {
  "use strict";
  window.APP = window.APP || {};
  var APP = window.APP;
  APP.charts = APP.charts || {}; // this file's own namespace — must self-create it,
  // exactly like shell.js does for APP.ui (see js/shell.js, "APP.ui = APP.ui || {}").
  // Nothing else in this codebase creates APP.charts; every assignment below
  // (APP.charts.lineCompare = ..., etc.) is an incremental property write onto it, so
  // without this line the very first one throws "Cannot set properties of undefined."
  var SVG_NS = "http://www.w3.org/2000/svg";

  function svg(tag, attrs) {
    var el = document.createElementNS(SVG_NS, tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    return el;
  }
  function token(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  }
  // HG1 round-4 accessibility fix (§23 — "charts must not be inaccessible islands").
  // `role="img"` already existed; it was never paired with an accessible name, which
  // means a screen reader announced every chart in this build identically ("image"),
  // with no way to tell an SML scatter from a drawdown chart without visual inspection.
  // The 4th, optional argument is a short textual equivalent of what the chart shows —
  // every call site below now passes one, built from the same data already handed to
  // the function (never a separately invented description).
  function makeRoot(width, height, extraClass, ariaLabel) {
    var attrs = { width: "100%", viewBox: "0 0 " + width + " " + height, preserveAspectRatio: "xMidYMid meet", role: "img" };
    if (ariaLabel) attrs["aria-label"] = ariaLabel;
    var root = svg("svg", attrs);
    if (extraClass) root.setAttribute("class", extraClass);
    return root;
  }
  // HG1 Condition 1A/1B — chart-family classes. See tokens.css's "chart family
  // DIMENSIONS" block for why this is the fix for BOTH the "charts get huge for no
  // reason" complaint and the "chart labels are disproportionately large" complaint:
  // capping max-width at each family's own authored size stops the SVG (and every text
  // node drawn inside it, since SVG type lives in the same viewBox user units as
  // everything else) from being stretched by a wide parent container. Every
  // APP.charts.* function below now passes its family name here instead of each caller
  // having to remember to wrap its own chart in the right CSS class — "make charts.js
  // consume the tokens," per the owner's instruction, applied structurally rather than
  // left to four different surface authors to each get right.
  function familyClass(name) { return "chart-family-" + name; }
  function scaleLinear(domain, range) {
    var d0 = domain[0], d1 = domain[1], r0 = range[0], r1 = range[1];
    var span = (d1 - d0) || 1;
    return function (v) { return r0 + ((v - d0) / span) * (r1 - r0); };
  }
  function niceTicks(min, max, count) {
    if (min === max) { min -= 1; max += 1; }
    var step = (max - min) / count;
    var out = [];
    for (var i = 0; i <= count; i++) out.push(min + step * i);
    return out;
  }
  function pickDateTicks(dates, count) {
    var out = [];
    var step = Math.max(1, Math.floor(dates.length / count));
    for (var i = 0; i < dates.length; i += step) out.push(i);
    if (out[out.length - 1] !== dates.length - 1) out.push(dates.length - 1);
    return out;
  }
  function pathFrom(points) {
    return points.map(function (p, i) { return (i === 0 ? "M" : "L") + p[0].toFixed(2) + "," + p[1].toFixed(2); }).join(" ");
  }
  // HG1 Condition 3 — shared "+X.X%" formatter for chart-native text (end labels, hover
  // readouts, relative-performance callouts). Deliberately independent of js/shell.js's
  // APP.ui.formatPercent: charts.js must stay usable with only its own module loaded
  // (CONTRACT.md's chart API never calls back into APP.ui), and every value this touches
  // is a display-only derivation of an array data.js already returned (index/return
  // series), never an invented figure.
  function pctText(v, digits) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    digits = digits === undefined ? 1 : digits;
    return (v >= 0 ? "+" : "") + (v * 100).toFixed(digits) + "%";
  }
  // HG1 M1 fix (RULING 4(iii), methodology/HG1_M1_PERIOD_RETURN_BASE_CONVENTION_RULING.md)
  // — exposed, read-only, so js/selfcheck.js's render-layer regression (RC-2) can format
  // the ENGINE side of a reconciliation with this EXACT function rather than a
  // second, independently-authored copy of "+X.X%" that could silently drift from it.
  // "pctText(v,1) and APP_fmtPct(v) are character-for-character the same function" only
  // holds as a reconciliation argument if a caller outside this file can actually reach
  // one of them; this is the minimal export that makes RC-2's string-equality check
  // (rather than a re-derivation of the formatting rule) possible. Formatting behavior
  // is unchanged — this adds a reference, not a new function.
  APP.charts.pctText = pctText;
  // HG1 round-4, second bilingual pass — chart-INTERNAL strings this file bakes in
  // itself (legend items, the relative-performance callout, the drawdown trough label)
  // could not previously be overridden by any caller at all, which the coordinator's
  // review named specifically as the class of string most likely to be missed by a
  // surface-level translation sweep. `ct()` (chart translate) reads APP.i18n.t when it
  // exists and falls back to the literal English default otherwise — a DEFENSIVE,
  // optional dependency, not a hard one: this file's own stated design constraint
  // ("charts.js must stay usable with only its own module loaded," see pctText's
  // comment above) still holds when APP.i18n is absent, because every call site below
  // supplies its own English fallback and never assumes APP.i18n exists. In this
  // product's actual fixed load order (index.html: shell.js, then data.js, then
  // charts.js) APP.i18n is always already defined by the time any chart renders, so in
  // practice this always localizes; the fallback exists for the hypothetical case
  // CONTRACT.md's original constraint was written to protect.
  function ct(key, fallback) {
    return (window.APP && window.APP.i18n && window.APP.i18n.t) ? window.APP.i18n.t(key) : fallback;
  }
  // Drops a trailing parenthetical from a series label for use in the hero chart's own
  // END labels only (e.g. "Benchmark (MSCI ACWI)" -> "Benchmark") — the full identity is
  // already stated once, in the legend above the plot; repeating it a second time at
  // the line's end is redundant text that was also the direct cause of the end-label
  // clipping risk this pass fixes (see lineCompare's own comment).
  function shortEndLabel(text) {
    return String(text || "").replace(/\s*\(.*$/, "");
  }
  // Legend swatch for a LINE series (as opposed to legendItem's rect swatch, used for
  // area/bar/point fills) — e.g. the dashed Security Market Line in the SML scatter.
  function legendLineItem(xOff, label, cls) {
    var g = svg("g", { transform: "translate(" + xOff + ",0)" });
    g.appendChild(svg("line", { x1: 0, x2: 14, y1: -6, y2: -6, class: cls }));
    var t = svg("text", { x: 20, y: -4, class: "chart-legend-label" });
    t.textContent = label;
    g.appendChild(t);
    return g;
  }

  // =====================================================================
  // HG1 round-4 — §4.1's governing instruction ("fix the shared causes, not the
  // screenshots") applied to legend placement. Every legend in this file previously
  // hand-placed its items at fixed magic-number x-offsets (0/118/215/285 in scatter,
  // 0/90 in the rolling family, 0/120 in lineCompare, 0/130 in pairedBar, si*110 in
  // stackedBar) sized for whatever label text the chart's original author happened to
  // be looking at. `stackedBar`'s local/FX-attribution legend is the confirmed case
  // (feedback log §3 item 4, "poor arrangement of the local-market-return/FX
  // contribution chart"): "Local-market return" (19 characters) does not fit in the
  // 110px gap its own hardcoded offset reserved for it, so the second legend item's
  // swatch rendered on top of the first item's own label text.
  //
  // HG1 Round 5 (S2) — MEASURED, not estimated. The round-4 comment this replaces
  // justified a monospace character-count heuristic on the grounds that "no canvas/
  // measureText call exists without a real DOM." The independent UX audit's S2 finding
  // is that this does not hold at RUN TIME: charts.js executes in a browser, where
  // `SVGTextElement.getComputedTextLength()`/`getSubStringLength()` exist. The
  // heuristic was also SCRIPT-BLIND: every chart label class inherits --font-sans (a
  // proportional face, ~3.2-9.6px per glyph at 11.5px), while CJK glyphs are full-
  // width — a 6-character Chinese label at 11.5px measures ~69 units; the old
  // estimator returned 36, a systematic ~48% underestimate in the second language,
  // which is the mechanical cause of every "+Npx overflow, only in Chinese" defect
  // this round closes (the hero end label, the SML callout's Chinese form, etc).
  //
  // `measureTextWidth`/`truncateToWidth` below append a hidden, unrendered <text> node
  // — carrying the SAME CSS class the real label will render with, inside an <svg
  // class="chart"> ancestor so it inherits the same --font-sans/--font-mono rule the
  // real chart does — to a single shared off-screen measurement node, attached to
  // `document.body`. This is a REAL DOM measurement of the ACTUAL font, size, and CSS
  // text-transform (e.g. `.chart-subtitle`'s uppercase) that will render, not an
  // estimate of it, and it is font-stack-independent — correct on any machine, in any
  // language, which the S8 font change (Arial pinned first) makes reproducible instead
  // of merely close (P12 — determinism).
  //
  // `estimateTextWidthHeuristic`/`truncateToWidthHeuristic` are KEPT, renamed, and
  // demoted to a LAST-RESORT fallback for the hypothetical non-browser context this
  // file's own header comment says its API must nominally still support (no DOM /
  // no document.body) — never the primary path (AC-S2.2: "no estimateTextWidth in any
  // position-computing path" — satisfied by the rename: nothing calls the heuristic by
  // that name, or as anything but a fallback, any more).
  // =====================================================================
  function estimateTextWidthHeuristic(text, charPx) {
    return String(text == null ? "" : text).length * (charPx || 6.2);
  }
  function truncateToWidthHeuristic(text, maxWidth, charPx) {
    text = String(text == null ? "" : text);
    charPx = charPx || 6.2;
    var maxChars = Math.max(1, Math.floor(maxWidth / charPx));
    if (text.length <= maxChars) return text;
    return text.slice(0, Math.max(1, maxChars - 1)) + "…";
  }
  // Single shared, reused measurement node (one <svg class="chart"><text/></svg>,
  // hidden via an off-screen absolute position rather than display:none/visibility:
  // hidden — both of THOSE remove an element from layout, which would make
  // getComputedTextLength() return 0). class="chart" on the wrapping <svg> is what
  // makes the measurement node inherit the SAME --font-sans rule (app.css's `.chart`
  // rule) every real chart root does, so a label class with no font-family of its own
  // (e.g. .chart-bar-label) measures against the correct inherited face, exactly like
  // its real, later-rendered counterpart will.
  var _measureNode = null;
  function ensureMeasureNode() {
    if (_measureNode) return _measureNode;
    if (typeof document === "undefined" || !document.body || !document.createElementNS) return null;
    var root = svg("svg", { width: "0", height: "0" });
    root.setAttribute("class", "chart");
    root.setAttribute("aria-hidden", "true");
    root.style.cssText = "position:absolute; left:-99999px; top:0; width:0; height:0; overflow:hidden; visibility:hidden; pointer-events:none;";
    _measureNode = svg("text", { x: 0, y: 0 });
    root.appendChild(_measureNode);
    document.body.appendChild(root);
    return _measureNode;
  }
  // Returns the rendered width, in the chart's own SVG user units, of `text` AS the
  // class `className` would actually render it (font, size, letter-spacing, and any
  // CSS text-transform all apply, because this is a real styled DOM measurement, not a
  // string-metrics estimate). Falls back to the old heuristic ONLY when no document
  // exists — see the block comment above.
  function measureTextWidth(text, className, fallbackCharPx) {
    text = text == null ? "" : String(text);
    if (!text) return 0;
    var node = ensureMeasureNode();
    if (!node) return estimateTextWidthHeuristic(text, fallbackCharPx);
    node.setAttribute("class", className || "");
    node.textContent = text;
    try {
      var w = node.getComputedTextLength();
      if (typeof w === "number" && isFinite(w)) return w;
    } catch (e) { /* fall through to the heuristic below */ }
    return estimateTextWidthHeuristic(text, fallbackCharPx);
  }
  // Truncates `text` (appending an ellipsis) to the longest prefix whose MEASURED
  // width — as className would actually render it — is <= maxWidth. Binary search
  // over `getComputedTextLength()` on real candidate strings, rather than dividing
  // maxWidth by an assumed per-character advance — correct for proportional glyphs
  // (a "W" and an "i" have never had the same advance) and for CJK strings (a mix of
  // full-width and, e.g., embedded Latin digits) alike, which a fixed charPx cannot be.
  function truncateToWidth(text, maxWidth, className, fallbackCharPx) {
    text = String(text == null ? "" : text);
    if (!text) return text;
    var node = ensureMeasureNode();
    if (!node) return truncateToWidthHeuristic(text, maxWidth, fallbackCharPx);
    node.setAttribute("class", className || "");
    node.textContent = text;
    var full;
    try { full = node.getComputedTextLength(); } catch (e) { return truncateToWidthHeuristic(text, maxWidth, fallbackCharPx); }
    if (typeof full !== "number" || !isFinite(full)) return truncateToWidthHeuristic(text, maxWidth, fallbackCharPx);
    if (full <= maxWidth) return text;
    var lo = 0, hi = text.length, best = 0;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      node.textContent = text.slice(0, mid) + "…";
      var w;
      try { w = node.getComputedTextLength(); } catch (e2) { w = Infinity; }
      if (w <= maxWidth) { best = mid; lo = mid + 1; } else { hi = mid - 1; }
    }
    best = Math.max(1, best);
    return text.slice(0, best) + "…";
  }
  // =====================================================================
  // placeAnnotation — HG1 Round 5 (I1). ONE shared boundary-safe, collision-aware text
  // placement routine for every point/callout annotation this chart draws. Round 4
  // gave the SML scatter's POINT labels a boundary flip + vertical clamp + de-collision
  // pass (see scatter()'s own comment, still accurate about that code) but left the
  // DISTANCE CALLOUT a few lines above them — in the SAME function, added in the SAME
  // round-4 pass — on the original fixed `text-anchor:start`, no-clamp, no-flip, no-
  // truncation code path. That is I1: the callout overflows the SVG (+118 CSS px in
  // English, measured) and renders as `Line distance +8`, truncated by the browser's
  // own default overflow:hidden, not by this file. Routing BOTH annotation types
  // through this one helper means a future annotation added to this chart cannot opt
  // out of boundary-safety by omission the way the callout did.
  //
  // opts: {
  //   anchorX, anchorY — the point/feature this annotation is attached to (SVG user
  //     units, already through the chart's own x()/y() scales).
  //   dx, dy — preferred offset from (anchorX, anchorY) before any boundary
  //     correction (defaults 8, 0).
  //   text, className — the rendered text and the CSS class it will carry (also the
  //     class MEASURED against — see measureTextWidth above).
  //   bounds: {left, right, top, bottom} — the plot's own inner boundary, in the same
  //     user-unit space; the annotation's bounding box must never cross `right` (via
  //     an anchor flip) or `top`/`bottom` (via a vertical clamp). `left` is accepted
  //     for symmetry but unused today (no caller's flip direction needs it).
  //   placed — optional array of {x,y} anchors already placed by earlier calls in the
  //     SAME chart; when supplied, a new label within 12px vertically of an existing
  //     one is nudged down (up to 8 attempts) exactly like the pre-existing point-
  //     label de-collision pass this replaces, and this call's own result is pushed
  //     onto it before returning, so several annotations placed in a loop accumulate
  //     de-collision for free.
  // }
  // Returns the appended <text> element.
  // =====================================================================
  function placeAnnotation(root, opts) {
    var text = opts.text == null ? "" : String(opts.text);
    var className = opts.className || "";
    var w = measureTextWidth(text, className);
    var dx = opts.dx === undefined ? 8 : opts.dx;
    var dy = opts.dy === undefined ? 0 : opts.dy;
    var bounds = opts.bounds || {};
    var right = bounds.right, top = bounds.top, bottom = bounds.bottom;

    var flip = (right !== undefined) && ((opts.anchorX + Math.abs(dx) + w) > right);
    var tx = flip ? opts.anchorX - Math.abs(dx) : opts.anchorX + dx;
    var ty = opts.anchorY + dy;

    if (top !== undefined) ty = Math.max(top + 10, ty);
    if (bottom !== undefined) ty = Math.min(bottom - 4, ty);

    var placed = opts.placed;
    if (placed) {
      var attempts = 0;
      while (attempts < 8 && placed.some(function (pl) { return Math.abs(pl.y - ty) < 12; })) {
        ty += 13;
        attempts++;
      }
      if (bottom !== undefined) ty = Math.min(bottom - 4, ty);
      placed.push({ x: tx, y: ty });
    }

    var el = svg("text", { x: tx, y: ty, class: className, "text-anchor": flip ? "end" : "start" });
    el.textContent = text;
    root.appendChild(el);
    return el;
  }
  // items: [{label, swatchClass, isLine?}]. Lays out left-to-right with spacing computed
  // from each label's OWN estimated width instead of a fixed per-chart constant, so a
  // long label reserves the room it actually needs and never collides with the next
  // item. Returns an ungrouped <g> — the caller still sets its own transform (position),
  // exactly like the single-purpose legendItem/legendLineItem this replaces call sites
  // of, so every existing caller's own y-positioning convention is untouched.
  function legendRow(items, opts) {
    opts = opts || {};
    var gap = opts.gap === undefined ? 16 : opts.gap;
    // opts.charPx survives as the fallback-heuristic parameter ONLY (no-document case);
    // the primary path below measures the label with the SAME class legendItem/
    // legendLineItem actually render it with ("chart-legend-label"), so a caller no
    // longer needs to guess this chart's own font metrics per call site (HG1 Round 5,
    // S2).
    var charPx = opts.charPx || 6.2;
    var g = svg("g", { class: "chart-legend" });
    var xOff = 0;
    (items || []).forEach(function (it) {
      var itemG = it.isLine ? legendLineItem(xOff, it.label, it.swatchClass) : legendItem(xOff, it.label, it.swatchClass);
      g.appendChild(itemG);
      // 20px is legendItem/legendLineItem's own fixed swatch+gap offset before their text
      // starts (see both functions above) — the same constant, read here, not redefined.
      xOff += 20 + measureTextWidth(it.label, "chart-legend-label", charPx) + gap;
    });
    return g;
  }

  var CHART_MARGIN = { top: 16, right: 16, bottom: 28, left: 48 };

  // =====================================================================
  // lineCompare — cumulative performance, portfolio vs benchmark. This is the hero
  // chart both accepted directions treat as the single most important visual.
  // HG1 Condition 3 additions (this pass): direct end labels with each series' period
  // return, a persistent relative-performance callout, and a hover crosshair with a
  // per-date readout — all on by default. Drawdown shading is opt-in (showDrawdown),
  // not default — see this pass's handoff/CONTRACT.md addendum for the judgment call.
  // opts: { dates, series: {portfolio:[], benchmark:[]}, width, height,
  //         showDrawdown?, drawdown?: {portfolio:[]}, labelA, labelB,
  //         showEndLabels? (default true), showHover? (default true) }
  // =====================================================================
  APP.charts.lineCompare = function lineCompare(opts) {
    var width = opts.width || 720, height = opts.height || 320;
    // HG1 Condition 3 — own margin object (not the shared CHART_MARGIN constant used
    // nowhere else) so a wider right gutter for end labels never affects any other
    // chart type. showEndLabels defaults on for this chart (the hero) since it is
    // "where practical" per the owner's instruction — width is always >= 480 in every
    // caller in this build, which is enough room for two short end labels.
    var showEndLabels = opts.showEndLabels !== false;
    // HG1 round-4 — end-label text is shortened (drops a parenthetical, e.g. "Benchmark
    // (MSCI ACWI)" -> "Benchmark"; the full identity is already stated once, in the
    // legend above) AND the right margin is now sized to what that shortened text
    // actually needs, worst-case, rather than a fixed 108px that a longer benchmark
    // name could exceed and get clipped by the SVG's own default overflow:hidden
    // boundary — part of the confirmed "SML/benchmark text clipping" defect class
    // (feedback log §3 item 5; the same geometry mistake recurs on this chart's own end
    // labels, not just the SML scatter). "+999.9%" is a fixed worst-case percent
    // suffix — the margin must not visibly jump between renders depending on the
    // actual period return, so it is sized against a stable upper bound, not the
    // specific number this call happens to compute.
    var endLabelA = shortEndLabel(opts.labelA || ct("chart.portfolio", "Portfolio"));
    var endLabelB = shortEndLabel(opts.labelB || ct("chart.benchmark", "Benchmark"));
    // HG1 Round 5 (S2) — measured against each label's OWN real class (portfolio's is
    // bold — .chart-end-label-portfolio adds font-weight:700 — which is not the same
    // rendered width as the benchmark's regular weight at the same character count, a
    // distinction the old character-count heuristic could not see either). This is
    // also the fix for the localization-only overflow the audit found here (S2 point
    // 3): "您的投资组合 +999.9%" measured via the old estimator at 92 units when its real
    // rendered width is ~112 — this now measures the true value directly, in either
    // language, because CJK full-width glyphs are not a special case for a real DOM
    // measurement the way they were for a per-character heuristic.
    var endMarginRight = showEndLabels
      ? Math.max(108, Math.ceil(Math.max(
          measureTextWidth(endLabelA + " +999.9%", "chart-end-label chart-end-label-portfolio", 6.6),
          measureTextWidth(endLabelB + " +999.9%", "chart-end-label chart-end-label-benchmark", 6.6)
        )) + 16)
      : 16;
    var m = { top: 16, right: endMarginRight, bottom: 28, left: 48 };
    // HG1 Round 5 (S2) — defensive floor: a very long measured end-label margin (a long
    // localized series name plus the worst-case "+999.9%" suffix) must not be allowed
    // to crush the plot area itself to near-zero or negative width; grow the chart's
    // own authored width rather than let innerW go unreasonably small. This mirrors
    // the same "assert the reservation, grow instead of overflow" principle applied to
    // bar()/pairedBar() below, generalized to this chart's own margin math.
    var MIN_PLOT_INNER_W = 200;
    if (width - m.left - m.right < MIN_PLOT_INNER_W) width = m.left + m.right + MIN_PLOT_INNER_W;
    var innerW = width - m.left - m.right, innerH = height - m.top - m.bottom - (opts.showDrawdown ? 60 : 0);
    var root = makeRoot(width, height, "chart chart-line-compare " + familyClass("hero"),
      "Cumulative performance line chart, " + (opts.labelA || ct("chart.portfolio", "Portfolio")) + " vs. " + (opts.labelB || ct("chart.benchmark", "Benchmark")));

    var dates = opts.dates || [];
    var a = opts.series.portfolio, b = opts.series.benchmark;
    var allVals = a.concat(b);
    var yMin = Math.min.apply(null, allVals), yMax = Math.max.apply(null, allVals);
    var pad = (yMax - yMin) * 0.08 || 1;
    var y = scaleLinear([yMin - pad, yMax + pad], [m.top + innerH, m.top]);
    var x = scaleLinear([0, dates.length - 1], [m.left, m.left + innerW]);

    // gridlines + y ticks
    var yTicks = niceTicks(yMin - pad, yMax + pad, 4);
    yTicks.forEach(function (t) {
      root.appendChild(svg("line", { x1: m.left, x2: m.left + innerW, y1: y(t), y2: y(t), class: "chart-gridline" }));
      var lbl = svg("text", { x: m.left - 8, y: y(t) + 4, class: "chart-tick chart-tick-y", "text-anchor": "end" });
      lbl.textContent = t.toFixed(0);
      root.appendChild(lbl);
    });
    pickDateTicks(dates, 6).forEach(function (i) {
      var lbl = svg("text", { x: x(i), y: m.top + innerH + 18, class: "chart-tick chart-tick-x", "text-anchor": "middle" });
      lbl.textContent = dates[i];
      root.appendChild(lbl);
    });

    var bPoints = b.map(function (v, i) { return [x(i), y(v)]; });
    var aPoints = a.map(function (v, i) { return [x(i), y(v)]; });
    // Portfolio drawn LAST (on top) and at a heavier stroke weight (see app.css
    // .chart-line-portfolio vs .chart-line-benchmark) — "make the portfolio line
    // visually dominant and the benchmark secondary" (HG1 Condition 3), reinforced by a
    // non-color cue too: benchmark is dashed, portfolio solid (Condition 2's "color is
    // never the only encoding," applied to the series distinction as well as to
    // gain/loss).
    root.appendChild(svg("path", { d: pathFrom(bPoints), class: "chart-line chart-line-benchmark", fill: "none" }));
    root.appendChild(svg("path", { d: pathFrom(aPoints), class: "chart-line chart-line-portfolio", fill: "none" }));

    // Drawdown shading is opt-in (opts.showDrawdown), not the previous default-on
    // behavior. HG1 Condition 3's own wording is a hedge — "perhaps drawdown shading
    // only when it helps" — and asks for an honest judgment, not an assumption. Judgment
    // recorded here (see this pass's handoff for the fuller account): bundling a
    // portfolio-only drawdown band under THIS chart mixes two different y-axes
    // (cumulative index vs. drawdown %) into one visual unit competing with the single
    // question this chart exists to answer ("who's ahead"), and a dedicated underwater
    // chart (APP.charts.drawdown, used in Analytics' own Rolling & Drawdown block, itself
    // strengthened this same pass with a benchmark reference line) already answers "how
    // deep did it fall" on its own axis without that conflict. Neither current caller in
    // this build (Overview, Analytics Performance) opts in; the parameter remains
    // functional for a future caller who judges differently for a different context.
    if (opts.showDrawdown && opts.drawdown) {
      var dd = opts.drawdown.portfolio;
      var ddMin = Math.min.apply(null, dd), ddMax = 0;
      var ddTop = m.top + innerH + 40, ddH = 40;
      var ddY = scaleLinear([ddMin, ddMax], [ddTop + ddH, ddTop]);
      var ddPoints = dd.map(function (v, i) { return [x(i), ddY(v)]; });
      var areaPoints = ddPoints.concat([[x(dd.length - 1), ddY(0)], [x(0), ddY(0)]]);
      root.appendChild(svg("path", { d: pathFrom(areaPoints) + " Z", class: "chart-area chart-area-drawdown" }));
      var ddLabel = svg("text", { x: m.left, y: ddTop - 6, class: "chart-tick chart-subtitle" });
      ddLabel.textContent = ct("chart.drawdownLabel", "Drawdown");
      root.appendChild(ddLabel);
    }

    var legend = legendRow([
      { label: opts.labelA || ct("chart.portfolio", "Portfolio"), swatchClass: "chart-swatch-portfolio" },
      { label: opts.labelB || ct("chart.benchmark", "Benchmark"), swatchClass: "chart-swatch-benchmark" }
    ], { charPx: 6.0 });
    legend.setAttribute("transform", "translate(" + m.left + "," + 12 + ")");
    root.insertBefore(legend, root.firstChild);

    // Relative performance — a persistent callout, not just a hover-only fact (HG1
    // Condition 3: "Include ... relative performance"). Computed from the exact
    // portfolio/benchmark arrays this call already received (whatever period the caller's
    // own period selector sliced) — not a second, independently-fetched figure, so it
    // never contradicts the chart it sits on; it is deliberately labeled "this period"
    // rather than a fixed window name so it never impersonates the separate, always-
    // trailing-1Y metric.benchmarkRelative figure a caller may also render elsewhere.
    var relEl = null;
    if (a.length > 1 && a[0] && b[0]) {
      var retAAll = a[a.length - 1] / a[0] - 1, retBAll = b[b.length - 1] / b[0] - 1;
      var relDiff = retAAll - retBAll;
      relEl = svg("text", {
        x: m.left + innerW, y: 8, class: "chart-relative-callout" + (relDiff >= 0 ? " chart-relative-positive" : " chart-relative-negative"),
        "text-anchor": "end"
      });
      relEl.textContent = ct("chart.thisPeriodPrefix", "This period: ") + pctText(relDiff) + ct("chart.vsBenchmarkSuffix", " vs. benchmark");
      root.appendChild(relEl);
    }

    // Direct end labels ("where practical" — always practical here: width is never below
    // ~480 in this build's callers, comfortably wider than two short labels need).
    if (showEndLabels && dates.length > 0) {
      var lastIdx = dates.length - 1;
      var aEndY = y(a[lastIdx]), bEndY = y(b[lastIdx]);
      var minGap = 15;
      if (Math.abs(aEndY - bEndY) < minGap) {
        if (aEndY <= bEndY) { aEndY -= minGap / 2; bEndY += minGap / 2; }
        else { aEndY += minGap / 2; bEndY -= minGap / 2; }
      }
      var retAEnd = a[0] ? a[lastIdx] / a[0] - 1 : null;
      var retBEnd = b[0] ? b[lastIdx] / b[0] - 1 : null;
      root.appendChild(svg("circle", { cx: x(lastIdx), cy: y(a[lastIdx]), r: 3, class: "chart-end-dot chart-end-dot-portfolio" }));
      root.appendChild(svg("circle", { cx: x(lastIdx), cy: y(b[lastIdx]), r: 3, class: "chart-end-dot chart-end-dot-benchmark" }));
      var aEndLbl = svg("text", { x: x(lastIdx) + 7, y: aEndY + 4, class: "chart-end-label chart-end-label-portfolio" });
      aEndLbl.textContent = endLabelA + " " + pctText(retAEnd);
      root.appendChild(aEndLbl);
      var bEndLbl = svg("text", { x: x(lastIdx) + 7, y: bEndY + 4, class: "chart-end-label chart-end-label-benchmark" });
      bEndLbl.textContent = endLabelB + " " + pctText(retBEnd);
      root.appendChild(bEndLbl);
    }

    // Hover values (HG1 Condition 3). A single transparent hit-rectangle over the plot
    // area tracks the nearest date index and updates a crosshair + both series' point
    // markers + a small readout box showing date, each series' period return so far, and
    // their difference at that point — all arithmetic on the same two arrays already
    // drawn, nothing fetched or invented. Prefer this lightweight inline handler over a
    // tooltip engine per this pass's technical constraints.
    if (opts.showHover !== false && dates.length > 1) {
      var hoverGroup = svg("g", { class: "chart-hover-group" });
      hoverGroup.style.display = "none";
      var hoverLine = svg("line", { x1: 0, x2: 0, y1: m.top, y2: m.top + innerH, class: "chart-hover-line" });
      var hoverDotA = svg("circle", { r: 4, class: "chart-hover-dot chart-hover-dot-portfolio" });
      var hoverDotB = svg("circle", { r: 4, class: "chart-hover-dot chart-hover-dot-benchmark" });
      var hoverBoxBg = svg("rect", { rx: 4, class: "chart-hover-box" });
      var hoverText1 = svg("text", { class: "chart-hover-text chart-hover-text-title" });
      var hoverText2 = svg("text", { class: "chart-hover-text" });
      var hoverText3 = svg("text", { class: "chart-hover-text" });
      var hoverText4 = svg("text", { class: "chart-hover-text chart-hover-text-diff" });
      [hoverLine, hoverDotA, hoverDotB, hoverBoxBg, hoverText1, hoverText2, hoverText3, hoverText4].forEach(function (n) { hoverGroup.appendChild(n); });
      root.appendChild(hoverGroup);

      var hitRect = svg("rect", { x: m.left, y: m.top, width: Math.max(1, innerW), height: Math.max(1, innerH), fill: "transparent", class: "chart-hover-hitarea" });
      root.appendChild(hitRect);

      var boxW = 176, boxH = 62;
      function updateHover(evt) {
        var localX;
        var ctm = root.getScreenCTM && root.getScreenCTM();
        if (ctm && root.createSVGPoint) {
          var pt = root.createSVGPoint();
          pt.x = evt.clientX; pt.y = evt.clientY;
          localX = pt.matrixTransform(ctm.inverse()).x;
        } else {
          var rect = root.getBoundingClientRect();
          localX = (evt.clientX - rect.left) * (width / rect.width);
        }
        var idx = Math.round((localX - m.left) / innerW * (dates.length - 1));
        idx = Math.max(0, Math.min(dates.length - 1, idx));
        var px = x(idx);
        hoverLine.setAttribute("x1", px); hoverLine.setAttribute("x2", px);
        hoverDotA.setAttribute("cx", px); hoverDotA.setAttribute("cy", y(a[idx]));
        hoverDotB.setAttribute("cx", px); hoverDotB.setAttribute("cy", y(b[idx]));
        var retAi = a[0] ? a[idx] / a[0] - 1 : null;
        var retBi = b[0] ? b[idx] / b[0] - 1 : null;
        var diff = (retAi !== null && retBi !== null) ? retAi - retBi : null;
        hoverText1.textContent = dates[idx] || "";
        hoverText2.textContent = (opts.labelA || ct("chart.portfolio", "Portfolio")) + ": " + pctText(retAi);
        hoverText3.textContent = (opts.labelB || ct("chart.benchmark", "Benchmark")) + ": " + pctText(retBi);
        hoverText4.textContent = ct("chart.differencePrefix", "Difference: ") + pctText(diff);
        var boxX = px + 10;
        if (boxX + boxW > m.left + innerW) boxX = px - boxW - 10;
        if (boxX < 0) boxX = 0;
        var boxY = m.top + 4;
        hoverBoxBg.setAttribute("x", boxX); hoverBoxBg.setAttribute("y", boxY);
        hoverBoxBg.setAttribute("width", boxW); hoverBoxBg.setAttribute("height", boxH);
        hoverText1.setAttribute("x", boxX + 8); hoverText1.setAttribute("y", boxY + 14);
        hoverText2.setAttribute("x", boxX + 8); hoverText2.setAttribute("y", boxY + 30);
        hoverText3.setAttribute("x", boxX + 8); hoverText3.setAttribute("y", boxY + 45);
        hoverText4.setAttribute("x", boxX + 8); hoverText4.setAttribute("y", boxY + 59);
        hoverGroup.style.display = "block";
      }
      hitRect.addEventListener("mousemove", updateHover);
      hitRect.addEventListener("mouseleave", function () { hoverGroup.style.display = "none"; });
    }

    return root;
  };

  function legendItem(xOff, label, swatchClass) {
    var g = svg("g", { transform: "translate(" + xOff + ",0)" });
    g.appendChild(svg("rect", { x: 0, y: -8, width: 14, height: 4, class: "chart-swatch " + swatchClass }));
    var t = svg("text", { x: 20, y: -4, class: "chart-legend-label" });
    t.textContent = label;
    g.appendChild(t);
    return g;
  }

  // =====================================================================
  // HG1 Condition 3 (round 3) — "Rolling analytics should share a coherent
  // visual grammar rather than looking like unrelated charts placed in
  // separate cards." rollingLine (90-day rolling volatility) and drawdown
  // (the underwater chart) are the rolling/time-windowed instruments on the
  // Analytics surface (rollingLine is also reused, unchanged, on Overview's
  // risk snapshot — same primitive, same grammar, everywhere it appears).
  // Both now read through this ONE shared frame — same margins, same y-tick
  // convention, same x-axis tick cadence, same window/frequency subtitle
  // placement, same legend placement, same hover behavior — rather than each
  // hand-rolling its own. A future rolling/time-windowed chart should extend
  // this frame too, not hand-roll a fifth convention.
  // =====================================================================
  var ROLLING_MARGIN = { top: 40, right: 16, bottom: 28, left: 52 };
  // HG1 Round 5 (S2) — `rollingXTicks` (below) always places a tick+label at the LAST
  // date, `text-anchor:middle`, at the plot's own right edge (x = m.left + innerW).
  // Half of that label's own measured width therefore overhangs PAST the plot edge,
  // and the previous fixed `right:16` margin was not sized to absorb it — confirmed
  // overflow "2026-09-03" +7px (Overview, scale 0.469) / +10px (Analytics, scale
  // 0.727), both the SAME 14-user-unit geometric overhang, only the chart's own
  // render scale differing (S3). `rollingMargin` reserves enough right margin for
  // HALF the measured width of the specific date that will land there — the last
  // element of the ACTUAL (already date-range-sliced, where applicable) dates array a
  // caller renders — falling back to ROLLING_MARGIN's original constant right value
  // when no dates are available yet to measure against.
  function rollingMargin(dates) {
    if (!dates || !dates.length) return ROLLING_MARGIN;
    var lastLabel = String(dates[dates.length - 1] || "");
    var halfW = measureTextWidth(lastLabel, "chart-tick chart-tick-x") / 2;
    return { top: ROLLING_MARGIN.top, right: Math.max(ROLLING_MARGIN.right, Math.ceil(halfW) + 4), bottom: ROLLING_MARGIN.bottom, left: ROLLING_MARGIN.left };
  }

  // Window/frequency subtitle — same class, same position (top-left, above
  // the legend row) as the SML scatter's own windowLabel, so "how do I read
  // the measurement window on this chart" has ONE learned answer across the
  // whole surface, not a per-chart convention.
  //
  // HG1 Round 5 (S2, second pass) — this function had NO boundary check at all, in
  // either the original build or this designer's first Round 5 pass: unlike the SML
  // scatter's own windowLabel (which Round 4 already ran through truncateToWidth),
  // this one set `textContent` unconditionally. Given a long enough windowLabel (e.g.
  // analytics.js's drawdown() call, "Trailing 1Y · Daily returns …" — Overview's
  // rolling-volatility chart uses a shorter windowLabel and would not hit this) this
  // has the same unbounded-overflow shape S2 exists to close; brought in line with
  // the SML subtitle's own truncation pattern rather than left as the one subtitle
  // path with none at all. Correction, third pass: the PM's specific +27px measurement
  // this fix was originally attributed to turned out, by the viewBox it reported, to
  // be the SML/scatter chart's OWN subtitle (see scatter()'s own comment on the
  // identical className bug) — not this function, which had not yet been live-tested
  // at the time. Recorded accurately rather than left mis-attributed. This function's
  // own version of that exact className bug (measuring "chart-subtitle" alone against
  // an element actually classed "chart-tick chart-subtitle", missing the font-family:
  // mono rule .chart-tick supplies) is fixed here regardless, on the same reasoning,
  // since nothing yet proves this path is exempt from the class of defect that hit
  // its sibling.
  function rollingSubtitle(root, m, width, text) {
    if (!text) return;
    var maxWidth = width - m.right - m.left - 4;
    var fullText = String(text);
    var truncated = truncateToWidth(fullText, maxWidth, "chart-tick chart-subtitle");
    var lbl = svg("text", { x: m.left, y: 12, class: "chart-tick chart-subtitle" });
    lbl.textContent = truncated;
    if (truncated !== fullText) {
      lbl.appendChild(svg("title", {})).textContent = fullText;
    }
    root.appendChild(lbl);
  }

  // Legend — always Portfolio; Benchmark only when a second series is
  // actually drawn. Fixed row position (y=30) under the subtitle row (y=12)
  // in every rolling-family chart, so a reader's eye returns to the same
  // place regardless of which of these charts they are looking at.
  function rollingLegend(root, m, hasBenchmark) {
    var items = [{ label: ct("chart.portfolio", "Portfolio"), swatchClass: "chart-swatch-portfolio" }];
    if (hasBenchmark) items.push({ label: ct("chart.benchmark", "Benchmark"), swatchClass: "chart-swatch-benchmark" });
    var legend = legendRow(items, { charPx: 6.0 });
    legend.setAttribute("transform", "translate(" + m.left + ",30)");
    root.appendChild(legend);
  }

  // Y-axis gridlines + percent-formatted ticks — the same niceTicks/gridline
  // convention lineCompare and scatter already use, applied here so the
  // rolling-family charts stop being the only two chart types on the surface
  // without gridlines of their own.
  function rollingYTicks(root, m, innerW, y, minV, maxV) {
    niceTicks(minV, maxV, 4).forEach(function (t) {
      root.appendChild(svg("line", { x1: m.left, x2: m.left + innerW, y1: y(t), y2: y(t), class: "chart-gridline" }));
      var lbl = svg("text", { x: m.left - 8, y: y(t) + 4, class: "chart-tick chart-tick-y", "text-anchor": "end" });
      lbl.textContent = (t * 100).toFixed(1) + "%";
      root.appendChild(lbl);
    });
  }

  // X-axis date ticks — identical cadence (pickDateTicks(..., 4)) and
  // placement in both rolling-family charts.
  function rollingXTicks(root, m, innerH, x, dates) {
    pickDateTicks(dates, 4).forEach(function (i) {
      var lbl = svg("text", { x: x(i), y: m.top + innerH + 18, class: "chart-tick chart-tick-x", "text-anchor": "middle" });
      lbl.textContent = dates[i];
      root.appendChild(lbl);
    });
  }

  // Hover crosshair + readout box, generalized to 1 or 2 series (unlike
  // lineCompare's hero-specific version, which also draws a relative-
  // performance difference line that has no meaning for a single-series
  // rolling-volatility read) — same interaction model (mousemove on an
  // invisible hit-rect over the plot area; nearest-date snap; a small
  // readout box that flips side near the right edge) as the hero chart, so
  // "how do I read a value at a specific date" behaves identically across
  // every time-series chart in the app, not just the hero.
  // opts: { width, m, innerW, innerH, dates, x, y, series: [{values, cls, label}] }
  function mountRollingHover(root, opts) {
    var width = opts.width, m = opts.m, innerW = opts.innerW, innerH = opts.innerH;
    var dates = opts.dates, x = opts.x, y = opts.y, series = opts.series;
    if (!dates || dates.length < 2) return;
    var hoverGroup = svg("g", { class: "chart-hover-group" });
    hoverGroup.style.display = "none";
    var hoverLine = svg("line", { x1: 0, x2: 0, y1: m.top, y2: m.top + innerH, class: "chart-hover-line" });
    hoverGroup.appendChild(hoverLine);
    var dots = series.map(function (s) {
      var d = svg("circle", { r: 4, class: "chart-hover-dot " + s.cls });
      hoverGroup.appendChild(d);
      return d;
    });
    var lineCount = 1 + series.length;
    var texts = [];
    for (var i = 0; i < lineCount; i++) {
      var t = svg("text", { class: "chart-hover-text" + (i === 0 ? " chart-hover-text-title" : "") });
      texts.push(t);
    }
    var hoverBoxBg = svg("rect", { rx: 4, class: "chart-hover-box" });
    hoverGroup.appendChild(hoverBoxBg);
    texts.forEach(function (t) { hoverGroup.appendChild(t); });
    root.appendChild(hoverGroup);
    var hitRect = svg("rect", { x: m.left, y: m.top, width: Math.max(1, innerW), height: Math.max(1, innerH), fill: "transparent", class: "chart-hover-hitarea" });
    root.appendChild(hitRect);

    var boxW = 176, boxH = 16 + lineCount * 15;
    function update(evt) {
      var localX;
      var ctm = root.getScreenCTM && root.getScreenCTM();
      if (ctm && root.createSVGPoint) {
        var pt = root.createSVGPoint();
        pt.x = evt.clientX; pt.y = evt.clientY;
        localX = pt.matrixTransform(ctm.inverse()).x;
      } else {
        var rect = root.getBoundingClientRect();
        localX = (evt.clientX - rect.left) * (width / rect.width);
      }
      var idx = Math.round((localX - m.left) / innerW * (dates.length - 1));
      idx = Math.max(0, Math.min(dates.length - 1, idx));
      var px = x(idx);
      hoverLine.setAttribute("x1", px); hoverLine.setAttribute("x2", px);
      texts[0].textContent = dates[idx] || "";
      series.forEach(function (s, si) {
        var v = s.values[idx];
        var has = v !== null && v !== undefined;
        dots[si].setAttribute("cx", px);
        dots[si].setAttribute("cy", has ? y(v) : -9999);
        texts[si + 1].textContent = s.label + ": " + (has ? pctText(v, 1) : ct("chart.notAvailable", "n/a"));
      });
      var boxX = px + 10;
      if (boxX + boxW > m.left + innerW) boxX = px - boxW - 10;
      if (boxX < 0) boxX = 0;
      var boxY = m.top + 4;
      hoverBoxBg.setAttribute("x", boxX); hoverBoxBg.setAttribute("y", boxY);
      hoverBoxBg.setAttribute("width", boxW); hoverBoxBg.setAttribute("height", boxH);
      texts.forEach(function (t, i2) {
        t.setAttribute("x", boxX + 8);
        t.setAttribute("y", boxY + 14 + i2 * 15);
      });
      hoverGroup.style.display = "block";
    }
    hitRect.addEventListener("mousemove", update);
    hitRect.addEventListener("mouseleave", function () { hoverGroup.style.display = "none"; });
  }

  // =====================================================================
  // drawdown — standalone underwater chart (Analytics' own drawdown block;
  // HG1 Condition 3: "use an actual negative-underwater chart" — zero at top,
  // drawdown descending below it, which this chart already draws that way;
  // this pass adds an optional benchmark reference line (P4 — every judgment
  // needs a reference point) and marks the trough explicitly rather than
  // leaving the deepest point to be read off the axis by eye.
  // opts: { dates, values, benchmarkValues?, width, height, windowLabel? }
  // =====================================================================
  APP.charts.drawdown = function drawdown(opts) {
    // Height 224 (was 200) — the shared rolling-family top margin grew from
    // ~12-22px to a fixed 40px to hold the new subtitle+legend rows
    // (ROLLING_MARGIN, shared with rollingLine below); height grew by the same
    // amount so the actual PLOT area stays about the size it was, rather than
    // silently shrinking to make room. Matches rollingLine's height exactly —
    // the two charts that always sit side-by-side in Analytics' Rolling
    // Analytics & Drawdown block are still the same height as each other.
    var width = opts.width || 640, height = opts.height || 224;
    var values = opts.values, dates = opts.dates;
    var m = rollingMargin(dates); // HG1 Round 5 (S2) — see rollingMargin's own comment above
    var innerW = width - m.left - m.right, innerH = height - m.top - m.bottom;
    var root = makeRoot(width, height, "chart chart-drawdown " + familyClass("rolling"),
      "Underwater drawdown chart, portfolio" + (opts.benchmarkValues ? " vs. benchmark" : ""));
    var benchValues = opts.benchmarkValues || null;
    var hasBench = !!(benchValues && benchValues.length === values.length);
    var allVals = hasBench ? values.concat(benchValues) : values;
    var minV = Math.min.apply(null, allVals);
    var x = scaleLinear([0, values.length - 1], [m.left, m.left + innerW]);
    var y = scaleLinear([minV, 0], [m.top + innerH, m.top]);
    var points = values.map(function (v, i) { return [x(i), y(v)]; });
    var area = points.concat([[x(values.length - 1), y(0)], [x(0), y(0)]]);

    rollingYTicks(root, m, innerW, y, minV, 0);
    root.appendChild(svg("line", { x1: m.left, x2: m.left + innerW, y1: y(0), y2: y(0), class: "chart-axis-zero" }));
    root.appendChild(svg("path", { d: pathFrom(area) + " Z", class: "chart-area chart-area-drawdown" }));
    if (hasBench) {
      var benchPoints = benchValues.map(function (v, i) { return [x(i), y(v)]; });
      root.appendChild(svg("path", { d: pathFrom(benchPoints), class: "chart-line chart-line-benchmark", fill: "none" }));
    }
    root.appendChild(svg("path", { d: pathFrom(points), class: "chart-line chart-line-portfolio", fill: "none" }));

    // Trough marker — the single deepest point, explicit rather than implied by shape.
    var minIdx = 0;
    values.forEach(function (v, i) { if (v < values[minIdx]) minIdx = i; });
    root.appendChild(svg("circle", { cx: x(minIdx), cy: y(values[minIdx]), r: 3.5, class: "chart-drawdown-trough-dot" }));
    var minLabel = svg("text", {
      x: x(minIdx), y: y(values[minIdx]) - 8, class: "chart-tick chart-drawdown-trough-label",
      "text-anchor": minIdx > values.length / 2 ? "end" : "start"
    });
    minLabel.textContent = ct("chart.maxDrawdownPrefix", "Max drawdown ") + pctText(values[minIdx], 1) + (dates && dates[minIdx] ? " (" + dates[minIdx] + ")" : "");
    root.appendChild(minLabel);

    rollingSubtitle(root, m, width, opts.windowLabel);
    rollingLegend(root, m, hasBench);
    rollingXTicks(root, m, innerH, x, dates);

    mountRollingHover(root, {
      width: width, m: m, innerW: innerW, innerH: innerH, dates: dates, x: x, y: y,
      series: [{ values: values, cls: "chart-hover-dot-portfolio", label: ct("chart.portfolio", "Portfolio") }]
        .concat(hasBench ? [{ values: benchValues, cls: "chart-hover-dot-benchmark", label: ct("chart.benchmark", "Benchmark") }] : [])
    });

    return root;
  };

  // =====================================================================
  // rollingLine — rolling analytics (e.g. 90-day rolling volatility)
  // opts: { dates, series: {portfolio:[], benchmark:[]}, width, height, unit,
  //         windowLabel? }
  // =====================================================================
  APP.charts.rollingLine = function rollingLine(opts) {
    var width = opts.width || 640, height = opts.height || 224; // see drawdown's note above
    var a = opts.series.portfolio.filter(function (v) { return v !== null; });
    var dates = opts.dates.slice(opts.dates.length - a.length);
    var m = rollingMargin(dates); // HG1 Round 5 (S2) — see rollingMargin's own comment above
    var innerW = width - m.left - m.right, innerH = height - m.top - m.bottom;
    var root = makeRoot(width, height, "chart chart-rolling " + familyClass("rolling"),
      "Rolling volatility line chart" + (opts.series.benchmark ? ", portfolio vs. benchmark" : ""));
    var b = (opts.series.benchmark || []).filter(function (v) { return v !== null; });
    var hasBench = b.length === a.length;
    var all = hasBench ? a.concat(b) : a;
    var minV = Math.min.apply(null, all), maxV = Math.max.apply(null, all);
    var pad = (maxV - minV) * 0.1 || 0.01;
    var x = scaleLinear([0, a.length - 1], [m.left, m.left + innerW]);
    var y = scaleLinear([minV - pad, maxV + pad], [m.top + innerH, m.top]);

    rollingYTicks(root, m, innerW, y, minV - pad, maxV + pad);
    if (hasBench) {
      var bPoints = b.map(function (v, i) { return [x(i), y(v)]; });
      root.appendChild(svg("path", { d: pathFrom(bPoints), class: "chart-line chart-line-benchmark", fill: "none" }));
    }
    var aPoints = a.map(function (v, i) { return [x(i), y(v)]; });
    root.appendChild(svg("path", { d: pathFrom(aPoints), class: "chart-line chart-line-portfolio", fill: "none" }));

    rollingSubtitle(root, m, width, opts.windowLabel);
    rollingLegend(root, m, hasBench);
    rollingXTicks(root, m, innerH, x, dates);

    mountRollingHover(root, {
      width: width, m: m, innerW: innerW, innerH: innerH, dates: dates, x: x, y: y,
      series: [{ values: a, cls: "chart-hover-dot-portfolio", label: ct("chart.portfolio", "Portfolio") }]
        .concat(hasBench ? [{ values: b, cls: "chart-hover-dot-benchmark", label: ct("chart.benchmark", "Benchmark") }] : [])
    });

    return root;
  };

  // =====================================================================
  // sparkline — small inline trend indicator
  // opts: { values, width, height }
  // =====================================================================
  APP.charts.sparkline = function sparkline(opts) {
    var width = opts.width || 96, height = opts.height || 28;
    var root = makeRoot(width, height, "chart chart-sparkline " + familyClass("compact"));
    // Purely decorative — a trend hint beside a numeral that already states the value;
    // role="img" (set by makeRoot) with no name would still announce as a bare, unnamed
    // image to a screen reader. aria-hidden removes it from the accessibility tree
    // entirely rather than giving it an empty or redundant name (§23).
    root.setAttribute("aria-hidden", "true");
    root.removeAttribute("role");
    var values = opts.values || [];
    var minV = Math.min.apply(null, values), maxV = Math.max.apply(null, values);
    var x = scaleLinear([0, values.length - 1], [2, width - 2]);
    var y = scaleLinear([minV, maxV], [height - 3, 3]);
    var points = values.map(function (v, i) { return [x(i), y(v)]; });
    root.appendChild(svg("path", { d: pathFrom(points), class: "chart-line chart-line-portfolio chart-sparkline-path", fill: "none" }));
    return root;
  };

  // =====================================================================
  // donut — asset-class / allocation summary
  // opts: { segments: [{label, value}], size, centerLabel }
  // =====================================================================
  APP.charts.donut = function donut(opts) {
    var size = opts.size || 140;
    var segmentNames = (opts.segments || []).map(function (s) { return s.label; }).join(", ");
    var root = makeRoot(size, size, "chart chart-donut " + familyClass("donut"),
      "Allocation donut chart" + (opts.centerLabel ? " — " + opts.centerLabel : "") + (segmentNames ? ": " + segmentNames : ""));
    var cx = size / 2, cy = size / 2, rOuter = size / 2 - 6, rInner = rOuter - 18;
    var segments = opts.segments || [];
    var total = segments.reduce(function (s, seg) { return s + seg.value; }, 0) || 1;
    var angle = -Math.PI / 2;
    segments.forEach(function (seg, i) {
      var frac = seg.value / total;
      var a0 = angle, a1 = angle + frac * Math.PI * 2;
      angle = a1;
      root.appendChild(donutArc(cx, cy, rInner, rOuter, a0, a1, "chart-donut-seg chart-donut-seg-" + (i % 6)));
    });
    var label = svg("text", { x: cx, y: cy - 4, class: "chart-donut-center", "text-anchor": "middle" });
    label.textContent = opts.centerLabel || "";
    root.appendChild(label);
    return root;
  };
  function donutArc(cx, cy, r0, r1, a0, a1, cls) {
    var large = (a1 - a0) > Math.PI ? 1 : 0;
    function pt(r, a) { return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; }
    var p0 = pt(r1, a0), p1 = pt(r1, a1), p2 = pt(r0, a1), p3 = pt(r0, a0);
    var d = "M" + p0[0] + "," + p0[1] +
      " A" + r1 + "," + r1 + " 0 " + large + " 1 " + p1[0] + "," + p1[1] +
      " L" + p2[0] + "," + p2[1] +
      " A" + r0 + "," + r0 + " 0 " + large + " 0 " + p3[0] + "," + p3[1] + " Z";
    return svg("path", { d: d, class: cls });
  }

  // =====================================================================
  // bar — horizontal bar, used for concentration / top-holdings / exposure
  // opts: { items: [{label, value}], width, height, valueFormat(v) }
  // =====================================================================
  // HG1 Condition 1A — "exposure bar chart: consistent fixed row height." rowH/gap are a
  // single pair of constants shared by every caller (Major Holdings on Overview, every
  // exposure breakdown, Top-5 concentration) so the same horizontal-bar convention and
  // row rhythm is used everywhere this function is used, per Condition 3's exposure note
  // ("country, currency, sector and asset-class charts should use consistent
  // horizontal-bar conventions"), extended here to the Major Holdings visualization too
  // since it is the same primitive.
  var BAR_ROW_HEIGHT = 24, BAR_ROW_GAP = 6;
  // HG1 round-4 (§4.2's "annotation/value gutter" region + "long labels must never
  // enter the plot area" + "plot marks must not cover labels") — this function's
  // gutters were both FIXED (labelW=96 always; the value gutter was an implicit
  // `width - labelW - 56`, i.e. only 56px, never checked against what the value text
  // actually needed). `item.displayValue` (added for Condition 3's "percent · dollar"
  // convention) routinely produces strings like "19.2% · $206,741.00" — at this chart's
  // mono value-label font, comfortably wider than 56px minus its own 8px left padding —
  // which the SVG root's default overflow:hidden then clips at the chart's right edge.
  // This is a confirmed, mechanical root cause of "exposure rows mispositioned" /
  // "risk-contribution rows mispositioned" (feedback log §3 items 6–7): the bars
  // themselves were never mispositioned, but their value labels were being cut off past
  // the chart boundary, which reads as the row's own content being wrong. Both gutters
  // are now sized from the ACTUAL text each item will render, not a guessed constant —
  // the category label gutter also gets a bounded max width plus truncation-with-title
  // for the (rare) label longer than that bound, so a long category name can never
  // itself bleed into the plot area either.
  var BAR_LABEL_MIN_W = 60, BAR_LABEL_MAX_W = 170, BAR_LABEL_PAD = 8;
  var BAR_VALUE_MIN_W = 40, BAR_VALUE_PAD = 16;
  // HG1 Round 5 (S2 + S3) — width at/above which bar()/pairedBar() attach the WIDE bar
  // family (app.css .chart-family-bar-wide / tokens.css --chart-bar-wide-*) instead of
  // the standard one. Chosen inside charts.js, from the caller's OWN width option
  // (after this pass's width-growth assertion below has already run), so no caller in
  // js/surfaces/*.js needed to be edited to get two differently-capped families — see
  // tokens.css's comment on --chart-bar-wide-max-width for the arithmetic on why one
  // shared cap could not fit both the ~320px-default callers and the two 400/420px-
  // explicit callers inside AC-S3.1's [0.9, 1.1] band at once.
  //
  // CORRECTED (PM live probe, second pass) — originally 360, which put
  // `exposureBarChart(ctx, curExp.segments, 360)` (analytics.js's Currency Exposure
  // chart, the ONE real caller that passes exactly 360) into the WIDE family at its
  // low end: 440/360 = 1.222, the exact ceiling the PM measured on #/analytics,
  // breaching AC-S3.1's 1.1 upper bound. 360 fits the STANDARD family far better
  // than the wide one regardless of the standard family's exact cap (see below) —
  // moved to 380, strictly between the known real widths 360 (standard) and 400/420
  // (wide), so every width this file's actual callers use (verified by reading
  // js/surfaces/*.js, read-only) lands in the family that keeps its scale inside
  // [0.9, 1.1]: 320 and 360 -> standard; 400 and 420 -> wide (see each family's own
  // tokens.css bounds for the resulting per-width scale — --chart-bar-max-width/
  // --chart-bar-min-width were themselves raised in a THIRD correction pass after
  // this one, so a number quoted here would go stale independently of this
  // threshold; tokens.css is the single source for the current bounds).
  var BAR_WIDE_FAMILY_THRESHOLD = 380;
  function barFamilyName(width) { return width >= BAR_WIDE_FAMILY_THRESHOLD ? "bar-wide" : "bar"; }
  // HG1 Round 5 (S2) — the smallest plot region this chart is willing to render; also
  // the floor `barMaxW` is clamped to when the caller's own `width` cannot hold both
  // gutters. Named so the growth assertion below and the clamp below read as the same
  // number, not two independent guesses.
  var BAR_MIN_PLOT_W = 40;
  APP.charts.bar = function bar(opts) {
    var rowH = BAR_ROW_HEIGHT, gap = BAR_ROW_GAP;
    var items = opts.items || [];
    var height = items.length * (rowH + gap) + 8;
    // Only a real (non-withheld) item's value counts toward the shared scale — an
    // INSUFFICIENT_DATA segment (item.insufficient, added this pass for the
    // capital-weight-vs-risk-contribution pairing) must never stretch or shrink every
    // other bar's proportion by a magnitude that was never actually rendered as a number.
    var scaleItems = items.filter(function (it) { return !it.insufficient; });
    var maxV = Math.max.apply(null, scaleItems.map(function (it) { return it.value; }).concat([0])) || 1;

    function valueTextFor(it) {
      if (it.insufficient) return it.insufficientLabel || ct("chart.insufficientData", "insufficient data");
      return it.displayValue !== undefined ? it.displayValue :
        (opts.valueFormat ? opts.valueFormat(it.value) : String(it.value));
    }
    // HG1 Round 5 (S2) — measured against each label/value's OWN real class
    // ("chart-bar-label" / "chart-bar-value", the latter on --font-mono) instead of an
    // assumed per-character advance. This is the direct fix for the confirmed
    // overflows "16.5% · $43,545.50" (+20px) and "5.0% · $13,215.00" (+13px): both are
    // `displayValue` strings measured here against the mono value-label font, exactly
    // as `valueTextFor` will render them below.
    var labelW = Math.max(BAR_LABEL_MIN_W, Math.min(BAR_LABEL_MAX_W,
      Math.ceil(Math.max.apply(null, items.map(function (it) { return measureTextWidth(it.label, "chart-bar-label", 6.0); }).concat([0]))) + BAR_LABEL_PAD));
    // HG1 Round 5 (S2, third pass — self-audit after the PM's className-mismatch
    // diagnosis on the subtitle) — an `it.insufficient` item renders its value text
    // with class "chart-bar-value chart-bar-insufficient-label", not "chart-bar-value"
    // alone; `.chart-bar-insufficient-label` sets `font-family: var(--font-sans)`,
    // which (later in app.css's source order, equal specificity) OVERRIDES
    // `.chart-bar-value`'s own `font-family: var(--font-mono)` for that combined
    // element. Measuring only "chart-bar-value" for such an item is the identical
    // bug class the PM found on the subtitle — the measurement node would not carry
    // the class that actually wins the font-family cascade for what gets rendered.
    // Match the real combined class per item instead of assuming one class fits all.
    var valueGutter = Math.max(BAR_VALUE_MIN_W,
      Math.ceil(Math.max.apply(null, items.map(function (it) {
        var valueClass = it.insufficient ? "chart-bar-value chart-bar-insufficient-label" : "chart-bar-value";
        return measureTextWidth(valueTextFor(it), valueClass, 6.6);
      }).concat([0]))) + BAR_VALUE_PAD);

    // HG1 Round 5 (S2) — ASSERT the reservation fits, don't clamp-and-overflow. Round 4
    // (§4.2) reserved labelW/valueGutter but never checked their sum against `width`;
    // `barMaxW` was floored at 40 while `width` stayed fixed, so the value label's own
    // x position (labelW + barMaxW + 8) landed past the viewBox's right edge, silently
    // clipped by the SVG root's default overflow:hidden — the mechanical cause of the
    // two confirmed overflows named above. Grow the chart's own authored width to fit
    // what it just measured, instead of overflowing past an unmoved one.
    var width = opts.width || 320;
    var required = labelW + valueGutter + BAR_MIN_PLOT_W;
    if (required > width) width = required;
    var barMaxW = Math.max(BAR_MIN_PLOT_W, width - labelW - valueGutter);

    var root = makeRoot(width, height, "chart chart-bar " + familyClass(barFamilyName(width)),
      opts.ariaLabel || "Bar chart with " + items.length + " categories");

    items.forEach(function (it, i) {
      var yPos = i * (rowH + gap) + 4;
      var label = svg("text", { x: 0, y: yPos + rowH / 2 + 4, class: "chart-bar-label" });
      var fullLabel = String(it.label);
      var truncated = truncateToWidth(fullLabel, labelW - BAR_LABEL_PAD, "chart-bar-label", 6.0);
      label.textContent = truncated;
      if (truncated !== fullLabel) {
        // Long category label: truncated with an ellipsis rather than allowed to run
        // into the plot area (§4.2) — full text stays reachable via a native tooltip.
        label.appendChild(svg("title", {})).textContent = fullLabel;
      }
      root.appendChild(label);
      if (it.insufficient) {
        // P5 (D3.2) applied to a chart context: no fabricated bar length for a withheld
        // value — a dashed empty-outline placeholder and a text label, never a numeral,
        // never an em-dash used as a value stand-in.
        root.appendChild(svg("rect", { x: labelW, y: yPos, width: barMaxW, height: rowH - 6, rx: 3, class: "chart-bar-insufficient" }));
        var insText = svg("text", { x: labelW + 8, y: yPos + rowH / 2 + 4, class: "chart-bar-value chart-bar-insufficient-label" });
        insText.textContent = valueTextFor(it);
        root.appendChild(insText);
        return;
      }
      var w = (it.value / maxV) * barMaxW;
      root.appendChild(svg("rect", { x: labelW, y: yPos, width: Math.max(2, w), height: rowH - 6, rx: 3, class: "chart-bar-fill" }));
      var valText = svg("text", { x: labelW + barMaxW + 8, y: yPos + rowH / 2 + 4, class: "chart-bar-value" });
      // displayValue lets a caller show a combined string (e.g. "43.2% · $412,345") while
      // `value` alone still drives bar-length proportion — added this pass so Overview's
      // and Analytics' exposure bars can be reconciled onto one shared convention
      // (HG1 Condition 3: "consistent horizontal-bar conventions ... everywhere") without
      // losing either the percent-of-portfolio or the dollar figure either surface used
      // to show alone.
      valText.textContent = valueTextFor(it);
      root.appendChild(valText);
    });
    return root;
  };

  // =====================================================================
  // pairedBar — capital weight vs. risk contribution (HG1 Condition 3: "eventually
  // show: capital weight vs risk contribution rather than another isolated set of
  // numbers"). Two aligned horizontal bars per category, same shared scale, same row
  // order — a grouped-bar comparison, not two independently-scaled charts a reader has
  // to reconcile by eye. An item with `insufficientB: true` renders NO bar for its own
  // second value (P5 applied to a chart: no fabricated magnitude for a withheld figure)
  // — only its first value (capital weight, a fact regardless) still renders normally.
  // opts: { items: [{label, valueA, valueB, insufficientB?}], width, labelA, labelB,
  //         valueFormat(v) }
  // =====================================================================
  var PAIR_BAR_HEIGHT = 13, PAIR_BAR_GAP = 3, PAIR_GROUP_GAP = 13;
  APP.charts.pairedBar = function pairedBar(opts) {
    var items = opts.items || [];
    var groupH = PAIR_BAR_HEIGHT * 2 + PAIR_BAR_GAP;
    var topOffset = 34;
    var height = items.length * (groupH + PAIR_GROUP_GAP) + topOffset + 6;
    // HG1 round-4 (§4.2) — same fixed-gutter risk as APP.charts.bar, applied here too:
    // a segment label like "Mainland China A-Shares" (23 characters) does not fit the
    // previous fixed 118px labelW at this chart's category-label font, and would bleed
    // into the plot area (the exact failure §4.2 names). labelW is now sized (bounded,
    // with truncation-with-title as a backstop) from the items actually passed in.
    // HG1 Round 5 (S2) — measured, not estimated; same rationale as APP.charts.bar
    // above (shares its BAR_LABEL_* bounds and BAR_MIN_PLOT_W floor deliberately —
    // one convention, not two).
    var labelW = Math.max(BAR_LABEL_MIN_W, Math.min(BAR_LABEL_MAX_W,
      Math.ceil(Math.max.apply(null, items.map(function (it) { return measureTextWidth(it.label, "chart-bar-label", 6.0); }).concat([0]))) + BAR_LABEL_PAD));
    var valueGutter = Math.max(48,
      Math.ceil(Math.max.apply(null, items.map(function (it) {
        return measureTextWidth(opts.valueFormat ? opts.valueFormat(it.valueA) : String(it.valueA), "chart-bar-value", 6.6);
      }).concat([0]))) + 10);

    // HG1 Round 5 (S2) — same "assert, grow, don't clamp-and-overflow" fix as
    // APP.charts.bar above.
    var width = opts.width || 380;
    var required = labelW + valueGutter + BAR_MIN_PLOT_W;
    if (required > width) width = required;
    var barMaxW = Math.max(BAR_MIN_PLOT_W, width - labelW - valueGutter);

    var root = makeRoot(width, height, "chart chart-paired-bar " + familyClass(barFamilyName(width)),
      "Paired bar chart comparing " + (opts.labelA || "capital weight") + " and " + (opts.labelB || "risk contribution") + " per segment");

    var scaleVals = [0];
    items.forEach(function (it) {
      scaleVals.push(it.valueA || 0);
      if (!it.insufficientB) scaleVals.push(it.valueB || 0);
    });
    var maxV = Math.max.apply(null, scaleVals) || 1;

    var legend = legendRow([
      { label: opts.labelA || ct("chart.capitalWeight", "Capital weight"), swatchClass: "chart-pair-seg-a" },
      { label: opts.labelB || ct("chart.riskContribution", "Risk contribution"), swatchClass: "chart-pair-seg-b" }
    ], { charPx: 6.0, gap: 20 });
    legend.setAttribute("transform", "translate(" + labelW + ",14)");
    root.appendChild(legend);

    items.forEach(function (it, i) {
      var yTop = topOffset + i * (groupH + PAIR_GROUP_GAP);
      var label = svg("text", { x: 0, y: yTop + groupH / 2 + 4, class: "chart-bar-label" });
      var fullLabel = String(it.label);
      var truncated = truncateToWidth(fullLabel, labelW - BAR_LABEL_PAD, "chart-bar-label", 6.0);
      label.textContent = truncated;
      if (truncated !== fullLabel) label.appendChild(svg("title", {})).textContent = fullLabel;
      root.appendChild(label);

      var wA = (it.valueA / maxV) * barMaxW;
      root.appendChild(svg("rect", { x: labelW, y: yTop, width: Math.max(2, wA), height: PAIR_BAR_HEIGHT, rx: 2, class: "chart-bar-fill chart-pair-seg-a" }));
      var vA = svg("text", { x: labelW + Math.max(2, wA) + 6, y: yTop + PAIR_BAR_HEIGHT - 2, class: "chart-bar-value" });
      vA.textContent = opts.valueFormat ? opts.valueFormat(it.valueA) : String(it.valueA);
      root.appendChild(vA);

      var yB = yTop + PAIR_BAR_HEIGHT + PAIR_BAR_GAP;
      if (it.insufficientB) {
        root.appendChild(svg("rect", { x: labelW, y: yB, width: barMaxW, height: PAIR_BAR_HEIGHT, rx: 2, class: "chart-bar-insufficient" }));
        var insText = svg("text", { x: labelW + 8, y: yB + PAIR_BAR_HEIGHT - 2, class: "chart-bar-value chart-bar-insufficient-label" });
        insText.textContent = it.insufficientLabel || ct("chart.insufficientData", "insufficient data");
        root.appendChild(insText);
      } else {
        var wB = (it.valueB / maxV) * barMaxW;
        root.appendChild(svg("rect", { x: labelW, y: yB, width: Math.max(2, wB), height: PAIR_BAR_HEIGHT, rx: 2, class: "chart-bar-fill chart-pair-seg-b" }));
        var vB = svg("text", { x: labelW + Math.max(2, wB) + 6, y: yB + PAIR_BAR_HEIGHT - 2, class: "chart-bar-value" });
        vB.textContent = opts.valueFormat ? opts.valueFormat(it.valueB) : String(it.valueB);
        root.appendChild(vB);
      }
    });
    return root;
  };

  // =====================================================================
  // stackedBar — e.g. FX vs local-return attribution band
  // opts: { categories: [label...], series: [{label, values:[...]}], width, height }
  // =====================================================================
  APP.charts.stackedBar = function stackedBar(opts) {
    var width = opts.width || 640, height = opts.height || 220;
    var m = { top: 16, right: 16, bottom: 28, left: 48 };
    var innerW = width - m.left - m.right, innerH = height - m.top - m.bottom;
    var root = makeRoot(width, height, "chart chart-stacked-bar " + familyClass("analytical"),
      "Stacked bar chart: " + (opts.series || []).map(function (s) { return s.label; }).join(" and "));
    var categories = opts.categories || [];
    var series = opts.series || [];
    var n = categories.length;
    var bw = innerW / n * 0.6;
    var allTotals = categories.map(function (_, i) {
      var pos = 0, neg = 0;
      series.forEach(function (s) { var v = s.values[i]; if (v >= 0) pos += v; else neg += v; });
      return { pos: pos, neg: neg };
    });
    var maxPos = Math.max.apply(null, allTotals.map(function (t) { return t.pos; }).concat([0]));
    var minNeg = Math.min.apply(null, allTotals.map(function (t) { return t.neg; }).concat([0]));
    var y = scaleLinear([minNeg, maxPos], [m.top + innerH, m.top]);
    var zeroY = y(0);
    root.appendChild(svg("line", { x1: m.left, x2: m.left + innerW, y1: zeroY, y2: zeroY, class: "chart-axis-zero" }));
    categories.forEach(function (cat, i) {
      var xCenter = m.left + (i + 0.5) * (innerW / n);
      var posOffset = 0, negOffset = 0;
      series.forEach(function (s, si) {
        var v = s.values[i];
        var top, h;
        if (v >= 0) { top = y(posOffset + v); h = zeroY - top; posOffset += v; }
        else { top = zeroY; h = y(negOffset + v) - zeroY; negOffset += v; }
        root.appendChild(svg("rect", {
          x: xCenter - bw / 2, y: Math.min(top, top + h), width: bw, height: Math.abs(h),
          class: "chart-stack-seg chart-stack-seg-" + si
        }));
      });
      var lbl = svg("text", { x: xCenter, y: m.top + innerH + 18, class: "chart-tick chart-tick-x", "text-anchor": "middle" });
      lbl.textContent = cat;
      root.appendChild(lbl);
    });
    // HG1 round-4 confirmed defect (feedback log §3 item 4) — this is the exact legend
    // whose fixed 110px-per-item offset collided: "Local-market return" (19 characters,
    // ~120px at this legend's font/size) does not fit ahead of the next item's swatch at
    // a fixed 110px offset. legendRow (above) sizes each gap from the label's own
    // estimated width instead.
    var legend = legendRow(series.map(function (s, si) {
      return { label: s.label, swatchClass: "chart-stack-seg chart-stack-seg-" + si };
    }), { charPx: 6.2, gap: 18 });
    legend.setAttribute("transform", "translate(" + m.left + "," + 10 + ")");
    root.insertBefore(legend, root.firstChild);
    return root;
  };

  // =====================================================================
  // scatter — realized return (y) vs. beta (x): portfolio + benchmark + sleeves against
  // an EX-POST market line. HG1 Condition 3 — this is named as "the single highest-value
  // item" in the interpretability pass: it must clearly identify x=beta, y=historical
  // annualized return, the benchmark, the portfolio, the ex-post market line, the true
  // vertical distance from the portfolio's point to that line, and the window/frequency.
  // Every one of those is now an explicit, labeled element on the chart itself, not left
  // to be inferred from a caller's surrounding prose.
  // HG1 round-4 (methodology/HG1_ROUND4_VERIFICATION.md §2.1) — `distanceCallout.distance`
  // must be the geometric vertical distance (`getSMLPoints().verticalDistance`), never
  // the regression Jensen's alpha (`metric.alpha.value`) — the two are different
  // quantities computed on different bases; see distanceCallout's own render-site
  // comment below for the full account of why this was a confirmed HG1 blocker.
  // opts: { points: [{beta,ret,label,group}], line: {slope, intercept}, width, height,
  //         windowLabel?, distanceCallout?: { beta, ret, distance },
  //         xAxisTitle?, yAxisTitle? }
  // =====================================================================
  APP.charts.scatter = function scatter(opts) {
    // Default widened 480 -> 560 (HG1 Condition 1A: "SML/risk-return scatter — wider
    // plot with sufficient axis space"); height 380 -> 440 this round (methodology
    // §2.4's required Y-axis title, "Realized total return, trailing 1Y, USD,
    // compounded," is ~53 characters — rotated along the left margin, its estimated
    // rendered length needs more vertical room than the shorter default title this
    // replaces ever required; the extra height is pure margin, it does not narrow the
    // plot area Condition 1A asked to widen).
    var width = opts.width || 560, height = opts.height || 440;
    // top margin holds two stacked rows above the plot: the window/frequency subtitle
    // (y=12) and the legend (y=32) — kept as two separate rows, not sharing one, so
    // neither text competes with the other for the same pixels.
    var m = { top: 48, right: 20, bottom: 46, left: 68 };
    var innerW = width - m.left - m.right, innerH = height - m.top - m.bottom;
    var root = makeRoot(width, height, "chart chart-scatter " + familyClass("scatter"),
      "Realized return vs. beta scatter chart, ex-post market line: portfolio, benchmark, and sleeves");
    var points = opts.points || [];
    var xs = points.map(function (p) { return p.beta !== undefined ? p.beta : p.x; });
    var ys = points.map(function (p) { return p.ret !== undefined ? p.ret : p.y; });
    // HG1 Round 5 — SUPERSEDES the previous `Math.min(0, min(betas)) - 0.1` domain, per
    // the quant_analyst ruling this designer was instructed to implement exactly
    // (methodology/HG1_ROUND5_CAVEAT_AND_SML_DOMAIN_RULING.md, Part B, "Ruling 2").
    // That domain forced beta=0 into view and left ~65% of the plot empty (a named
    // contributor to Feedback Log 2 Problem 8 / this file's own I1 finding).
    // RULING 2 — beta=0 is NOT required to be visible; the domain may be data-driven.
    // Why (the ruling's own reasoning, restated here so this is not a bare number
    // change): beta=0 is a STIPULATED line parameter (R_f), never an observation — the
    // line is y(beta) = R_f + beta*(R_b - R_f), and a reader does not, and must not,
    // read R_f off this chart; it is stated in words in the required line annotation
    // (Ruling 2(iv) — see the note at this function's distanceCallout block on where
    // that annotation actually lives, outside this file). The chart already excludes
    // its own y-origin (yMin below is `min(ys) - 0.05`, not 0) with no objection, so
    // demanding zero-inclusion on only one axis of a position-encoded (not length-
    // encoded) scatter was an inconsistency, not a rule. The anchor that IS load-
    // bearing is beta=1 (Ruling 2(i)): the benchmark's own beta, the point the line
    // passes through by construction, and this chart's P4 reference point.
    //
    // RULING 2(i) — beta=1 must ALWAYS be inside the domain, with a LABELLED tick
    // (enforced below by betaAxisTicks, not left to niceTicks landing on it by luck).
    var betaLo = Math.min.apply(null, xs.concat([1]));
    var betaHi = Math.max.apply(null, xs.concat([1]));
    var xPad = Math.max(0.05, 0.08 * (betaHi - betaLo));
    // RULING 2(ii) — minimum domain width, so a tightly-clustered beta set (portfolio
    // ~0.99, benchmark exactly 1.0 by construction) cannot be magnified into a
    // horizontal separation LARGER than the estimate's own uncertainty — the same
    // error class the 1.96-se directional-claim threshold exists to prevent elsewhere
    // in this product, appearing here in geometry instead of prose. The multiplier (4)
    // and the 0.5 floor are the quant's OWN named conventions, not derived, and are
    // NOT this designer's or product_manager's to change (PD-0014 §3) — kept as named
    // constants for exactly that reason, not inlined as magic numbers.
    var BETA_CI95_WIDTH_MULTIPLIER = 4; // quant_analyst's ruling, Part B, Ruling 2(ii)
    var BETA_DOMAIN_WIDTH_FLOOR = 0.5;  // quant_analyst's ruling, Part B, Ruling 2(ii)
    // opts.betaCI95 ([lo, hi], the portfolio beta's own 95% CI) is the ONE input this
    // ruling needs that charts.js does not itself hold — it lives on metric.beta in
    // js/data.js. This designer's write scope this round is styles/ + this file only;
    // js/surfaces/analytics.js (the caller) is NOT wired to pass it yet. Rather than
    // silently skip the multiplier term, this falls back to the ruling's OWN stated
    // floor (0.5), which the ruling itself designates as the safe default "where no
    // standard error exists" — i.e. this is still ruling-compliant, not a shortcut
    // around it; the moment a future caller passes betaCI95, the tighter, data-derived
    // width takes over automatically with no further change here. Reported to the
    // coordinator as an outside-this-scope wiring gap, not silently absorbed.
    var betaCI95 = opts.betaCI95;
    var ci95Width = (betaCI95 && betaCI95.length === 2) ? Math.abs(betaCI95[1] - betaCI95[0]) : 0;
    var xDomainMinWidth = Math.max(BETA_DOMAIN_WIDTH_FLOOR, BETA_CI95_WIDTH_MULTIPLIER * ci95Width);
    var xMin = betaLo - xPad, xMax = betaHi + xPad;
    if ((xMax - xMin) < xDomainMinWidth) {
      var xDomainMid = (xMin + xMax) / 2;
      xMin = xDomainMid - xDomainMinWidth / 2;
      xMax = xDomainMid + xDomainMinWidth / 2;
    }
    var yMin = Math.min.apply(null, ys) - 0.05, yMax = Math.max.apply(null, ys) + 0.05;
    var x = scaleLinear([xMin, xMax], [m.left, m.left + innerW]);
    var y = scaleLinear([yMin, yMax], [m.top + innerH, m.top]);

    // RULING 2(i)/2(iii) — betaAxisTicks guarantees beta=1 is always ONE of the
    // labelled ticks (not merely inside the domain) and that at least 3 labelled ticks
    // render on a plain linear scale — no zero baseline, no axis break, no implied
    // zero anywhere on this axis (niceTicks's own even spacing happened to land a tick
    // near 1.0 in today's fixture by coincidence; this makes it a requirement).
    function betaAxisTicks(lo, hi, count) {
      var ticks = niceTicks(lo, hi, count);
      var hasOne = ticks.some(function (t) { return Math.abs(t - 1) < 1e-9; });
      if (!hasOne) { ticks.push(1); ticks.sort(function (a, b) { return a - b; }); }
      return ticks;
    }
    betaAxisTicks(xMin, xMax, 4).forEach(function (t) {
      var lbl = svg("text", { x: x(t), y: m.top + innerH + 18, class: "chart-tick chart-tick-x", "text-anchor": "middle" });
      lbl.textContent = t.toFixed(1);
      root.appendChild(lbl);
      root.appendChild(svg("line", { x1: x(t), x2: x(t), y1: m.top, y2: m.top + innerH, class: "chart-gridline" }));
    });
    niceTicks(yMin, yMax, 4).forEach(function (t) {
      var lbl = svg("text", { x: m.left - 8, y: y(t) + 4, class: "chart-tick chart-tick-y", "text-anchor": "end" });
      lbl.textContent = (t * 100).toFixed(0) + "%";
      root.appendChild(lbl);
      root.appendChild(svg("line", { x1: m.left, x2: m.left + innerW, y1: y(t), y2: y(t), class: "chart-gridline" }));
    });

    // Explicit axis titles — "clearly identify x-axis = beta; y-axis = historical
    // annualized return" (HG1 Condition 3), not left to be inferred from unlabeled
    // ticks. HG1 round-4 (methodology/HG1_ROUND4_VERIFICATION.md §2, adopting
    // methodology/HG1_ROUND4_METHODOLOGY_FINDINGS.md §2.4's exact wording) — both
    // titles are now caller-overridable so the SML block (js/surfaces/analytics.js)
    // can pass the precise, dated, observation-counted wording the methodology
    // requires, without this chart primitive hardcoding a number (like an observation
    // count) that belongs to js/data.js and could go stale here. The literal defaults
    // below are only the fallback for a hypothetical future caller that passes none.
    var xTitle = svg("text", { x: m.left + innerW / 2, y: height - 6, class: "chart-axis-title", "text-anchor": "middle" });
    xTitle.textContent = opts.xAxisTitle || "Beta (systematic risk vs. benchmark)";
    root.appendChild(xTitle);
    var yTitle = svg("text", {
      x: 14, y: m.top + innerH / 2, class: "chart-axis-title", "text-anchor": "middle",
      transform: "rotate(-90 14 " + (m.top + innerH / 2) + ")"
    });
    yTitle.textContent = opts.yAxisTitle || "Historical annualized return";
    root.appendChild(yTitle);

    // Window/frequency — "identify ... window/frequency" (HG1 Condition 3), stated once
    // as a subtitle rather than requiring the reader to already know the methodology.
    // HG1 round-4 — this subtitle now also carries the observation count and dated
    // window (methodology §2's requirement), which makes it considerably longer than
    // when this truncation-free rendering was first written; a left-anchored, single-
    // line SVG string with no wrap would otherwise risk exactly the boundary-clipping
    // defect class this same round fixed elsewhere (§4.2) if a caller's string runs
    // long. Truncated (with a full-text <title> tooltip) against the actual available
    // width, rather than trusted to fit.
    if (opts.windowLabel) {
      var subtitleMaxWidth = (width - m.right) - m.left - 4;
      var fullSubtitle = String(opts.windowLabel);
      // HG1 Round 5 (S2, third pass — PM live probe) — CORRECTED. The rendered
      // element below carries BOTH "chart-tick" and "chart-subtitle" — `.chart-tick`
      // is the rule that actually sets `font-family: var(--font-mono)`;
      // `.chart-subtitle` alone sets no font-family. Measuring against
      // "chart-subtitle" alone (this designer's own earlier bug) left the
      // measurement node on the INHERITED sans-serif face instead of the real
      // rendered mono one, under-measuring the string and letting more of it survive
      // truncation than actually fits once rendered in the real (wider, per-glyph)
      // mono font — the exact +27 CSS px (English only; ZH's shorter string never
      // crossed the miscalculated budget) the PM measured. Measuring className must
      // always match the FULL class list of the element it is measuring, not a
      // subset of it.
      var truncatedSubtitle = truncateToWidth(fullSubtitle, subtitleMaxWidth, "chart-tick chart-subtitle", 6.6);
      var winLbl = svg("text", { x: m.left, y: 12, class: "chart-tick chart-subtitle" });
      winLbl.textContent = truncatedSubtitle;
      if (truncatedSubtitle !== fullSubtitle) {
        winLbl.appendChild(svg("title", {})).textContent = fullSubtitle;
      }
      root.appendChild(winLbl);
    }

    if (opts.line) {
      var lx0 = xMin, lx1 = xMax;
      var ly0 = opts.line.intercept + opts.line.slope * lx0;
      var ly1 = opts.line.intercept + opts.line.slope * lx1;
      root.appendChild(svg("line", { x1: x(lx0), y1: y(ly0), x2: x(lx1), y2: y(ly1), class: "chart-sml-line" }));
    }

    // HG1 round-4 fix (methodology/HG1_ROUND4_VERIFICATION.md §2.1 — confirmed live,
    // ruled an HG1 blocker). This connector draws the vertical distance from the
    // portfolio's point to the SML line at the same beta — a GEOMETRIC quantity
    // (concept 4, `getSMLPoints().verticalDistance` in js/data.js). The previous label
    // text annotated that geometric distance with the regression Jensen's alpha (concept
    // 3, `metric.alpha.value`) — two different quantities, computed on different bases
    // (a geometric-return difference vs. an OLS regression on arithmetic daily excess
    // returns), that happen to be numerically close but are not the same number. The gap
    // was 0.11pp pre-correction and grew to 0.397pp (3.6×) once beta moved toward 1,
    // which is exactly why "close enough to eyeball" was never a safe basis for this.
    //
    // The parameter is named `distance` (not `alpha`) so a future caller cannot repeat
    // the same mistake by passing the wrong claim into a field whose name invites it.
    // The caller (js/surfaces/analytics.js) now passes `getSMLPoints().verticalDistance`
    // directly — the SAME value already used to draw the connector's own geometry below
    // (`ac.ret` vs. `lineValAtBeta`), so the label can never disagree with what the
    // connector visually shows (P12 — read once, label what is drawn). Regression alpha
    // remains a legitimate, separately reported statistic (shown via metric.sml's own
    // `formatted` field and metric.alpha's claim card) — it is simply never the number
    // that labels THIS line.
    // HG1 Round 5 (I1) — this callout previously placed itself at a fixed `acX + 9,
    // text-anchor:start`, with NO width clamp, NO anchor flip, and NO truncation — in
    // the same round-4 pass that gave the POINT labels below (and the subtitle above)
    // exactly those protections. Measured overflow was +118 CSS px in English (+37px
    // in Chinese), rendering as the truncated `Line distance +8` the owner's P8.png
    // shows: the browser's own default overflow:hidden clipping the SVG, not this
    // file. Now routed through the SAME placeAnnotation() helper the point labels use
    // below, so this annotation type cannot opt out of boundary-safety by omission
    // again. AC-I1.1 requires the FULL text stay present in the DOM (never "fixed" by
    // truncating it away) — placeAnnotation only ever moves/flips the anchor; it does
    // not truncate.
    if (opts.distanceCallout && opts.line) {
      var dc = opts.distanceCallout;
      var lineValAtBeta = opts.line.intercept + opts.line.slope * dc.beta;
      var acX = x(dc.beta);
      root.appendChild(svg("line", {
        x1: acX, y1: y(dc.ret), x2: acX, y2: y(lineValAtBeta),
        class: "chart-alpha-connector"
      }));
      var acLabelY = (y(dc.ret) + y(lineValAtBeta)) / 2;
      placeAnnotation(root, {
        anchorX: acX, anchorY: acLabelY, dx: 9, dy: 4,
        className: "chart-alpha-label" + (dc.distance >= 0 ? " chart-alpha-positive" : " chart-alpha-negative"),
        text: ct("chart.lineDistancePrefix", "Line distance ") + pctText(dc.distance, 1) + ct("chart.historicalSuffix", " (historical)"),
        bounds: { left: m.left, right: m.left + innerW, top: m.top, bottom: m.top + innerH }
      });
    }
    // RULING 2(iv) (methodology/HG1_ROUND5_CAVEAT_AND_SML_DOMAIN_RULING.md, Part B) —
    // now that beta=0 is not necessarily visible, the R_f / realized-benchmark-return
    // annotation (stating R_f=4.5% p.a. and the realized benchmark return in words)
    // becomes the reader's ONLY way to recover the line's intercept, and the ruling
    // requires it render at every depth the chart itself renders. Per
    // js/surfaces/analytics.js's own comment at its `ctx.charts.scatter({...})` call
    // site ("the compounding-basis disclosure ... is already stated in full,
    // permanently visible, in the line-annotation paragraph mounted directly above
    // this chart"), that annotation is authored OUTSIDE this file, in analytics.js —
    // outside this designer's write scope this round (styles/ + this file only). Per
    // the coordinator's own instruction ("if that annotation lives outside charts.js,
    // do not chase it — report it"): reported, not touched. Phase 2 must confirm it
    // still renders at whatever depth(s) this chart is shown at, including if
    // Analytics gains a Quick mode under a future S5 pass.

    // HG1 round-4 — boundary-safe, collision-aware point-label placement (§4.2's
    // "point annotations must use collision-aware placement" and "labels must remain
    // within the visible chart boundary"; feedback log §3 item 5, "SML/benchmark text
    // clipping"). Every point previously placed its label at a fixed (+8, -8) offset
    // regardless of how close the point sat to the plot's own right edge — a point near
    // xMax whose label ran past `width - m.right` was silently clipped by the SVG root's
    // own default overflow:hidden. Each label now: (1) flips to the LEFT of its point
    // (text-anchor end) when its estimated width would cross the right boundary; (2) is
    // clamped vertically inside [m.top, m.top+innerH] so it can never sit above the plot
    // area or collide with the legend/subtitle rows above it; (3) is nudged apart from
    // any other label estimated to land within 12px of it vertically, a minimal collision
    // pass sufficient for this chart's small (3-6) point count.
    // HG1 Round 5 (I1) — now routed through the SAME placeAnnotation() helper as the
    // distance callout above, instead of its own separate (if similar) inline
    // boundary/collision logic — one implementation of "boundary-safe, collision-
    // aware" for every annotation this chart draws, not two that can drift apart.
    // dy:-8 matches this loop's previous `cy - 8` before vertical clamping.
    var placedLabels = [];
    points.forEach(function (p, i) {
      var px = p.beta !== undefined ? p.beta : p.x, py = p.ret !== undefined ? p.ret : p.y;
      var cx = x(px), cy = y(py);
      var g = svg("g", { class: "chart-scatter-point chart-scatter-" + (p.group || "default") });
      g.appendChild(svg("circle", { cx: cx, cy: cy, r: p.group === "portfolio" ? 7 : 5 }));
      root.appendChild(g);
      placeAnnotation(g, {
        anchorX: cx, anchorY: cy, dx: 8, dy: -8,
        className: "chart-scatter-label",
        text: p.label,
        bounds: { left: m.left, right: m.left + innerW, top: m.top, bottom: m.top + innerH },
        placed: placedLabels
      });
    });

    // Legend — group colors (portfolio/benchmark/sleeve) AND the SML line, all named
    // explicitly. Every point already also carries its own text label beside it
    // (chart-scatter-label above), so the legend is reinforcement, not the only place
    // group identity is readable — same accessibility posture as the hero chart's
    // dashed-vs-solid line distinction (HG1 Condition 2: color is never the only
    // encoding). Spacing is now computed per label (legendRow), not a fixed offset —
    // "Security Market Line" (21 characters) is the longest item here and the one most
    // likely to have been under-spaced by a guessed constant.
    var legendItems = [
      { label: ct("chart.yourPortfolio", "Your portfolio"), swatchClass: "chart-scatter-portfolio" },
      { label: ct("chart.benchmark", "Benchmark"), swatchClass: "chart-scatter-benchmark" },
      { label: ct("chart.sleeve", "Sleeve"), swatchClass: "chart-scatter-sleeve" }
    ];
    // HG1 round-4 (methodology §2.4) — "Security Market Line" may not appear unqualified
    // anywhere; qualified as ex-post in the same visual unit, everywhere it appears.
    if (opts.line) legendItems.push({ label: ct("chart.securityMarketLineExPost", "Security Market Line (ex-post)"), swatchClass: "chart-sml-line", isLine: true });
    var legend = legendRow(legendItems, { charPx: 6.0, gap: 18 });
    legend.setAttribute("transform", "translate(" + m.left + ",32)");
    root.appendChild(legend);

    return root;
  };

  // =====================================================================
  // heatmap — correlation matrix
  // opts: { labels: [...], matrix: [[...]], width }
  // =====================================================================
  APP.charts.heatmap = function heatmap(opts) {
    var labels = opts.labels || [];
    var matrix = opts.matrix || [];
    var n = labels.length;
    var cell = opts.cell || 44;
    // HG1 ux_planning revision (review-07, P0 item 2) — labelW/topMargin/rightMargin
    // (formerly the fixed constants 100/60/16, tuned for the shortest-label case) clipped
    // the English row label ("Benchmark (MSCI ACWI)," 21 characters — DOM text was
    // correct, per review-07; only the visual rendering clipped) at the left edge, and
    // the same string's rotated column header at the top/right edges — while zh's
    // shorter "基准(MSCI ACWI)" fit inside the same fixed margins without issue. Exactly
    // the "only clips in the language with the longer rendered string" shape this file's
    // own measureTextWidth/truncateToWidth were built to close (see that function's own
    // header comment) — reused here rather than a second, hand-guessed constant. Sized
    // from the ACTUAL labels this call receives, via a REAL DOM measurement (the same
    // .chart-heatmap-label class the labels render with) when a document is available,
    // falling back to the same 6.2px/char heuristic every other measureTextWidth caller
    // in this file falls back to otherwise — so a shorter label set (zh) gets its own
    // correspondingly narrower layout instead of inheriting English's larger margins,
    // per the owner's "do not regress it" instruction, and neither language's longest
    // label can clip regardless of its rendered width.
    var maxLabelW = 0;
    labels.forEach(function (lbl) {
      var w = measureTextWidth(lbl, "chart-heatmap-label", 6.2);
      if (w > maxLabelW) maxLabelW = w;
    });
    // Row labels are text-anchor:"end", ending 8px left of the grid (below) — needs the
    // measured width plus that 8px gutter; floored at the old default (100) so a
    // pathologically short label set never shrinks the row-label gutter into the grid.
    var labelW = opts.labelWidth || Math.max(100, Math.ceil(maxLabelW) + 8);
    // Column headers are the SAME label set, rotated -40deg (below): the longest one's
    // rendered run reaches roughly maxLabelW*cos(40deg) to the right of its own anchor
    // and maxLabelW*sin(40deg) above it — reprojecting an already-measured length
    // through the SAME rotation the text itself gets, not a second independent guess at
    // it. +12/+18 are rounding/anchor-offset margin, not a second guess at the length.
    var rotRad = 40 * Math.PI / 180;
    var colHeaderRise = Math.ceil(maxLabelW * Math.sin(rotRad)) + 12;
    var colHeaderReach = Math.ceil(maxLabelW * Math.cos(rotRad)) + 12;
    var topMargin = Math.max(60, colHeaderRise + 18); // 18: anchor's own y-offset above the grid (was the fixed "52" vs "60" gap)
    var rightMargin = Math.max(16, colHeaderReach - Math.floor(cell / 2));
    var width = labelW + n * cell + rightMargin;
    var height = n * cell + topMargin;
    // NOTE (this designer, filesystem-only this round — cannot verify in a browser):
    // widening this chart's intrinsic viewBox on real (likely wider-than-heuristic)
    // English content means styles/tokens.css's --chart-matrix-max-width/-min-width and
    // --inspector-width-wide (widened alongside this change, with the same caveat) must
    // still keep the DISPLAYED scale within the documented font-size floor (AC-S3.1,
    // ~11px) and inside the inspector's usable width — reasoned from this same
    // measurement heuristic, not measured live. Flagged for live confirmation.
    var root = makeRoot(width, height, "chart chart-heatmap " + familyClass("matrix"),
      "Correlation heatmap for " + labels.join(", ") + ". A plain-language summary of the strongest and weakest pairs is provided alongside this chart.");
    labels.forEach(function (lbl, i) {
      var rowLabel = svg("text", { x: labelW - 8, y: topMargin + i * cell + cell / 2 + 4, class: "chart-heatmap-label", "text-anchor": "end" });
      rowLabel.textContent = lbl;
      root.appendChild(rowLabel);
      var colAnchorX = labelW + i * cell + cell / 2, colAnchorY = topMargin - 8;
      var colLabel = svg("text", {
        x: colAnchorX, y: colAnchorY, class: "chart-heatmap-label chart-heatmap-collabel",
        "text-anchor": "start", transform: "rotate(-40 " + colAnchorX + " " + colAnchorY + ")"
      });
      colLabel.textContent = lbl;
      root.appendChild(colLabel);
    });
    for (var r = 0; r < n; r++) {
      for (var c = 0; c < n; c++) {
        var v = matrix[r][c];
        var cellG = svg("g", {});
        var opacity = Math.min(1, Math.abs(v));
        cellG.appendChild(svg("rect", {
          x: labelW + c * cell, y: topMargin + r * cell, width: cell - 2, height: cell - 2,
          class: "chart-heatmap-cell " + (v >= 0 ? "chart-heatmap-pos" : "chart-heatmap-neg"),
          "fill-opacity": (0.15 + opacity * 0.75).toFixed(2)
        }));
        var t = svg("text", {
          x: labelW + c * cell + cell / 2, y: topMargin + r * cell + cell / 2 + 4,
          class: "chart-heatmap-value", "text-anchor": "middle"
        });
        t.textContent = v.toFixed(2);
        cellG.appendChild(t);
        root.appendChild(cellG);
      }
    }
    return root;
  };
})();
