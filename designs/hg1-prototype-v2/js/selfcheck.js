/*
 * selfcheck.js — HG1 round 4, Task 3 (PD-0014 §2.2 claim-traceability invariant).
 * Owned by designer-19. Recomputes and verifies hardcoded conclusion/caveat/insight
 * strings in js/data.js against the structured values they describe, at page load.
 *
 * Governing rule (PD-0014 §2.4): "The Proof Packet must not be able to refute the
 * sentence that links to it." Every assertion below either recomputes a claimed
 * comparison from the underlying data, or compares two independently-sourced numbers
 * that a hand-authored sentence asserts agree.
 *
 * =====================================================================================
 * REVISION 2 (this file). pm-01 proved by live mutation that binding1 (and, on
 * inspection, binding4 and one additional assertion) PASSED while their exact defect
 * was reintroduced — a control that cannot fail is worse than no control. Root cause,
 * found and fixed here:
 *
 *   1. VACUOUS PASS BY FIELD-CONCATENATION. binding1 tested
 *      `conclusionQuick + " " + explanationSimple` as one string. explanationSimple is
 *      generated dynamically from BETA and is therefore ALWAYS correct; when only
 *      conclusionQuick was mutated to the false defect text, the untouched, correct
 *      explanationSimple's wording made the combined regex test pass anyway. Same bug
 *      shape in binding4 (caveat's defect text doesn't even contain the word "daily",
 *      so the check silently matched the correct number in the untouched
 *      investorDetail field instead) and in the SML alpha/distance check. FIX: every
 *      assertion below tests each field INDEPENDENTLY — never concatenates two fields
 *      that could each independently be correct before testing them as one string.
 *   2. A TAUTOLOGICAL CHECK. The prior fxAttribution.portfolioIdentityExact computed
 *      `local = total - fx` and then re-added fx to confirm it produced `total` again —
 *      algebraically guaranteed regardless of any real defect. FIX: it now cross-checks
 *      the SAME quantity from two INDEPENDENT sources (the total-minus-FX arithmetic
 *      analytics.js performs vs. the actual PERIOD_RETURN_LOCAL exposed by
 *      getFxAttributionDetail()), which CAN disagree if the identity is ever broken.
 *   3. FACT-ONLY CHECKS THAT NEVER READ THE PROSE. exposure.economicGeography.
 *      chinaLargerThanCnListing and exposure.assetClass.predominantlyEquity verified an
 *      underlying number but never actually inspected the claim string they were named
 *      after — a wording regression would have gone undetected. FIX: both now compare
 *      the claim's own conclusionQuick text against the fact.
 *
 * EVERY assertion below is now demonstrated, not assumed, to detect its own named
 * defect: see selfTest() and its acceptance bar in the module doc below.
 *
 * REVISION 3 (quant_analyst verification, HG1_ROUND4_VERIFICATION.md §6). Beyond the
 * revision-2 fixes above, quant_analyst found that revision 2's OWN fix to binding1 —
 * a bare `value < 1` boundary — would have PUNISHED the correct, statistically-hedged
 * sentence once beta moved to 0.994 ± 0.042 (a 0.143-standard-error difference from
 * 1.0, which the sample cannot distinguish from zero): a confident "moved less than
 * the market" claim on that data is itself a false-precision defect. binding1 now
 * enforces a tolerance band (an estimate must clear ONE STANDARD ERROR of its own
 * reference point before a direction may be asserted at all) instead of a bare
 * inequality, reading se(β̂) from the SAME Proof Packet object the claim is judged
 * against. A new assertion, correlation.bandClassificationPrecision, implements the
 * analogous quant-specified precision guard for correlation band labels (se(ρ) ≈
 * (1-ρ²)/√(n-1)).
 *
 * =====================================================================================
 *
 * SCOPE LIMITATION, recorded here so a green run is never mistaken for full coverage
 * (quant_analyst verification §5.4, and worth restating because a 21+/21+ pass is
 * exactly the kind of result that gets mistaken for a gate signal — CLAUDE.md's human
 * gates section is explicit that no automated check substitutes for the human owner's
 * decision):
 *
 * REVISION 4 (review-07, P0 item 1) — a further, deliberate, individually-justified bend
 * of the "reads ONLY window.APP.data" rule below (the third: stage5.urlLocale reads
 * APP.i18n, chart.renderedReturnReconcilesWithEngine reads APP.charts,
 * holdingDisplayName.zh.consistentAcrossSurfaces already read APP.ui). That last
 * assertion is EXTENDED this round to also render the real 'analytics'/'overview'
 * surfaces off-screen (via the newly-exposed APP.uicheck.renderSurfaceOffscreen) and
 * read back their actual .chart-bar-label DOM text — because checking
 * APP.ui.holdingDisplayName()'s return value in isolation is exactly the shape of check
 * that stayed green while a call site (analytics.js) bypassed the helper entirely. See
 * that assertion's own comment for the full account.
 *
 * **This file reads ONLY `window.APP.data`. It never inspects the DOM, a chart, or any
 * surface module (analytics.js, charts.js, shell.js, evidence.js, ai.js, scenario.js).**
 * (Read literally, this line has not been fully true since the exceptions listed in
 * REVISION 4 above — kept as the DEFAULT discipline every OTHER assertion in this file
 * still follows, not as a claim that zero exceptions exist.)
 * A defect can be fully fixed in data.js and still be live on screen if the surface
 * that renders it does not read the corrected field — this happened in this very round:
 * data.js exposes `getSMLPoints().verticalDistance` specifically so the SML chart's
 * alpha annotation could be corrected, and as of this revision no surface consumes it
 * (quant_analyst verification §2.1) — a defect this file's assertions cannot see at
 * all, because it lives in `analytics.js`/`charts.js`, not in any `APP.data` accessor.
 * A 21-of-21 (or however many) `run()`/`selfTest()` pass means: every prose string this
 * file knows how to read is consistent with the structured values behind it. It does
 * NOT mean: the screen is correct, the chart annotations are correct, or HG1 is ready
 * to approve. See CONTRACT.md's round-4 addendum for the same limitation recorded
 * against the module's own write-path boundary.
 * =====================================================================================
 *
 * DEFENSIVE BY DESIGN. This file must never take the page down, and must never assume
 * any other namespace is ready:
 *   - It creates its OWN namespace (APP.selfcheck = APP.selfcheck || {}) rather than
 *     assuming APP.ui/APP.charts exist.
 *   - It reads ONLY window.APP.data (never APP.ui/APP.charts).
 *   - Every assertion runs inside its own try/catch; a thrown error inside one
 *     assertion is recorded as a FAILED assertion, never an uncaught exception and
 *     never silently converted to a pass.
 *   - run() itself is safe to call multiple times and safe to call before APP.data
 *     exists (it reports a single failing "data missing" result and returns).
 *
 * Exposes:
 *   window.APP.selfcheck.run()      -> array of { id, description, pass, detail }.
 *     Runs automatically at page load and logs a summary to the console.
 *   window.APP.selfcheck.selfTest() -> array of { id, description, pass, detail }.
 *     THE ACCEPTANCE BAR FOR THIS FILE. For every assertion in run(), reintroduces
 *     that assertion's own named defect into a live claim object (or, where the
 *     accessor rebuilds its return value fresh each call, temporarily wraps the
 *     accessor function itself), confirms the assertion FAILS while the defect is
 *     present, then restores the original value/function before moving to the next
 *     assertion. `pass: true` on an entry here means "this assertion was PROVEN, by
 *     mechanical negative test, to detect its own defect" — not merely that it is
 *     plausible in the author's judgment. Every mutation is restored, including on a
 *     thrown error (try/finally), so a self-test run never leaves the live app in a
 *     mutated state. NOT run automatically at page load — call it manually to verify.
 */
(function () {
  "use strict";
  window.APP = window.APP || {};
  var APP = window.APP;
  APP.selfcheck = APP.selfcheck || {};

  // =======================================================================
  // Shared helpers
  // =======================================================================
  function approxEqual(a, b, eps) {
    if (typeof a !== "number" || typeof b !== "number") return false;
    return Math.abs(a - b) <= (eps === undefined ? 1e-9 : eps);
  }

  function shortSleeveName(label) {
    return String(label || "").replace(" Equity Sleeve", "").replace(" Sleeve", "");
  }

  function escapeRegExp(s) { return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

  function containsWholeWord(text, phrase) {
    var re = new RegExp("\\b" + escapeRegExp(phrase) + "\\b", "i");
    return re.test(String(text || ""));
  }

  function mentionsAny(text, aliases) {
    return aliases.some(function (a) { return containsWholeWord(text, a); });
  }

  function mentionsPair(text, aliasesA, aliasesB) {
    return mentionsAny(text, aliasesA) && mentionsAny(text, aliasesB);
  }

  // Splits on a period/semicolon followed by WHITESPACE only — deliberately does NOT
  // split on a bare "." with no following space, so a decimal number ("46.4%") is never
  // mistaken for a sentence boundary the way a naive [^.;]* character-class scan would.
  function splitSentences(text) {
    return String(text || "").split(/[.;]\s+/).filter(Boolean);
  }

  // Mutates `obj[key] = value` for each key in `changes`, returns a function that
  // restores every original value. Used as the negative-test injector for any claim
  // object obtained by reference from a data.js accessor (confirmed by pm-01:
  // getMetric() returns the same shared object across calls, and a mutation on it is
  // visible on the next call — this is exactly that mechanism, used deliberately and
  // always paired with a restore).
  function withMutatedFields(obj, changes) {
    var original = {};
    Object.keys(changes).forEach(function (k) {
      original[k] = obj[k];
      obj[k] = changes[k];
    });
    return function restore() {
      Object.keys(original).forEach(function (k) { obj[k] = original[k]; });
    };
  }

  // For an accessor that BUILDS a fresh return object on every call (rather than
  // handing back a stored reference) — e.g. getFxAttributionDetail() — direct mutation
  // of a previously-returned object has no effect on the next call. This instead
  // temporarily wraps the accessor FUNCTION itself (a plain property on `data`, safe to
  // reassign and restore) so its result is transformed on the way out, then restores
  // the original function.
  function withMutatedAccessor(data, name, transform) {
    var original = data[name];
    data[name] = function () {
      var result = original.apply(data, arguments);
      // `arguments` (index-accessible, array-like) is passed through as a second
      // parameter so a transform can condition its mutation on which call it is
      // (e.g. only mutate the result for one specific test date/argument set) —
      // existing callers that only use the first parameter are unaffected.
      return transform(result, arguments);
    };
    return function restore() { data[name] = original; };
  }

  // Runs `fn`, catching any thrown error so one bad assertion can never abort the run
  // or the page — and a thrown error is recorded as FAILED, never converted to a pass.
  function safeCheck(fn) {
    try {
      var result = fn();
      if (typeof result === "boolean") return { pass: result, detail: "" };
      if (result && typeof result === "object") return { pass: !!result.pass, detail: result.detail || "" };
      return { pass: false, detail: "assertion function returned neither boolean nor {pass,detail}" };
    } catch (e) {
      return { pass: false, detail: "threw: " + (e && e.message ? e.message : String(e)) };
    }
  }

  function runOne(def, data) {
    var r = safeCheck(function () { return def.check(data); });
    return { id: def.id, description: def.description, pass: r.pass, detail: r.detail };
  }

  // HG1 M1 fix (methodology/HG1_M1_PERIOD_RETURN_BASE_CONVENTION_RULING.md) — shared
  // range set for the period-window regression family below (RC-1/RC-2, RULING 5/6).
  var M1_RANGES = ["1M", "3M", "6M", "1Y", "ALL"];

  // =======================================================================
  // ASSERTIONS — each is { id, description, check(data), injectDefect(data) }.
  // `injectDefect` reintroduces THIS assertion's own named historical (or
  // structurally-equivalent) defect and returns a restore() function. Every entry has
  // one — per this pass's acceptance bar, an assertion that cannot be demonstrated to
  // fail is not shipped (requirement 4: "say so and remove it" — none needed removing
  // once each was given a working injector).
  // =======================================================================
  var ASSERTIONS = [

    // ---- Stage-5 testability seam (ADR-0031 Stage 4 — browser_interaction recorded
    // DEGRADED: Claude-in-Chrome cannot operate the native OS-level <select> that is
    // this prototype's only visible language control, so a delegated browser-based
    // reviewer could not reach the Chinese UI at all). js/shell.js's boot() now
    // accepts a query-string locale override (?lang=en|zh-CN|...), normalized by
    // APP.i18n._normalizeUrlLocale and applied through setLangQuiet — the SAME
    // primitive APP.i18n.setLang (the native <select>'s own change handler) calls as
    // its first statement. This assertion is a deliberate, narrow exception to this
    // file's own stated scope ("reads ONLY window.APP.data... never touches
    // window.APP.i18n/APP.ui" — see this file's header) because the seam it verifies
    // lives entirely in the i18n/shell layer, not js/data.js; js/i18n-selfcheck.js
    // (this build's i18n-layer sibling) was not extended per the explicit task scope
    // that placed this entry here instead. ----
    {
      id: "stage5.urlLocale.convergesWithInteractivePath",
      description: "The Stage-5 query-string locale override (APP.i18n._normalizeUrlLocale, applied via setLangQuiet in boot() — js/shell.js) and the existing interactive locale path (the settings drawer's native <select>, whose change handler calls APP.i18n.setLang(...), which calls the SAME setLangQuiet as its own first statement — js/shell.js ~3325) must converge on identical (1) internal language state (APP.i18n.getLang()), (2) document.documentElement.lang ('en' | 'zh-Hans'), and (3) a representative translated rendering (APP.i18n.t('nav.overview'), which has a real zh translation: 'Overview' | '总览'). Checked causally for BOTH 'en' and 'zh': normalizes a representative raw query value for each ('en-US' / 'zh-CN'), confirms it resolves to the locale token the interactive path's own setLang(...) expects, drives the shared setLangQuiet primitive with that token, and compares all three signals against fixed expected values per locale. Uses setLangQuiet (never setLang) so this read-only check never forces a visible re-render mid-selfcheck, matching this build's own established diagnostic discipline (js/shell.js:1578-1584, js/i18n-selfcheck.js:231-235); language is saved before and restored after, even on failure.",
      check: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.i18n) {
          return { pass: false, detail: "window.APP.i18n is not available — cannot verify locale convergence." };
        }
        var i18n = window.APP.i18n;
        if (typeof i18n._normalizeUrlLocale !== "function" || typeof i18n.setLangQuiet !== "function" ||
            typeof i18n.getLang !== "function" || typeof i18n.t !== "function") {
          return { pass: false, detail: "APP.i18n._normalizeUrlLocale / setLangQuiet / getLang / t are not all available — cannot verify locale convergence." };
        }
        var originalLang = i18n.getLang();
        var problems = [];
        var cases = [
          { locale: "en", rawParam: "en-US", expectedDocLang: "en", expectedRendered: "Overview" },
          { locale: "zh", rawParam: "zh-CN", expectedDocLang: "zh-Hans", expectedRendered: "总览" }
        ];
        try {
          cases.forEach(function (c) {
            var normalized = i18n._normalizeUrlLocale("?lang=" + c.rawParam);
            if (normalized !== c.locale) {
              problems.push("normalizeUrlLocale('?lang=" + c.rawParam + "') = '" + normalized + "', expected '" + c.locale + "'");
              return;
            }
            // setLangQuiet is the exact shared primitive both the URL path (boot(),
            // js/shell.js) and the interactive path (APP.i18n.setLang, called from the
            // native <select>'s change handler) funnel through — driving it here with
            // the normalizer's own output exercises the identical machinery both paths
            // share, not two independent implementations that merely happen to agree.
            i18n.setLangQuiet(normalized);
            var stateLang = i18n.getLang();
            var docLang = (typeof document !== "undefined" && document.documentElement) ? document.documentElement.lang : null;
            var rendered = i18n.t("nav.overview");
            if (stateLang !== c.locale) problems.push(c.locale + ": APP.i18n.getLang() = '" + stateLang + "', expected '" + c.locale + "'");
            if (docLang !== c.expectedDocLang) problems.push(c.locale + ": document.documentElement.lang = '" + docLang + "', expected '" + c.expectedDocLang + "'");
            if (rendered !== c.expectedRendered) problems.push(c.locale + ": APP.i18n.t('nav.overview') = '" + rendered + "', expected '" + c.expectedRendered + "'");
          });
        } finally {
          i18n.setLangQuiet(originalLang);
        }
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "en (lang=en-US) and zh (lang=zh-CN) both converge on getLang(), document.documentElement.lang, and t('nav.overview') via the shared setLangQuiet primitive." };
      },
      // Real divergence, not a hypothetical one: forces the normalizer itself to
      // return the MIRRORED wrong locale (zh-CN -> "en", en-US -> "zh") rather than
      // patching the comparison — proving `check` actually reads the normalizer's live
      // output rather than a hardcoded expectation. Every case above then disagrees
      // with its own expected values, on all three signals, for both locales.
      injectDefect: function (data) {
        var i18n = window.APP.i18n;
        var original = i18n._normalizeUrlLocale;
        i18n._normalizeUrlLocale = function (search) {
          var r = original(search);
          if (r === "en") return "zh";
          if (r === "zh") return "en";
          return r;
        };
        return function restore() { i18n._normalizeUrlLocale = original; };
      }
    },

    // ---- Binding assertion 1 (PD-0014 §2.3 #1) ----
    {
      id: "binding1.beta.directionClaim",
      // REVISION 3 (quant_analyst verification §6) — pm-01 demonstrated the field-
      // concatenation bug fixed in revision 2 was real, but revision 2's bare
      // `value < 1` boundary was ITSELF wrong in a way live testing had not yet
      // exposed: at beta=0.994 (se=0.042, a 0.143-sigma difference from 1.0), the
      // implementer's own derived fix asserted "moved less than the market" — a
      // false-precision claim quant_analyst's own §7.1 spec had no tolerance band to
      // forbid. This assertion now enforces the quant's tolerance-band rule instead of
      // a bare inequality: a directional claim requires the estimate to clear beta's
      // OWN standard error (exposed on the Proof Packet, read from there rather than
      // recomputed here, so this can never silently drift from what the claim itself
      // was judged against). Still checks conclusionQuick and explanationSimple
      // INDEPENDENTLY — never concatenated — so a correct field can never mask a
      // defective one.
      // REVISION 4 (harmonized threshold) — the multiplier applied to `se` is now
      // 1.96 (95% confidence), not a bare 1, matching the correlation classification-
      // band guard: two different thresholds for the same class of judgment ("may a
      // directional/classification claim be asserted") was itself a parallel-truths
      // defect (PD-0014 §2.5) once the correlation guard was independently tightened.
      // Read from data._internal.directionalClaimSeMultiplier — the SAME constant
      // data.js's own betaDirectionConclusion multiplies by — rather than a separately
      // hardcoded "1.96" here that could silently drift from it.
      // HG1 round 4 (bilingual gap) — extended to ALSO check claim.i18n.zh's
      // conclusionQuick/explanationSimple when present, using a bilingual classifier.
      // A Chinese sentence that contradicts its own number is the same defect wearing
      // a different language, and would otherwise be invisible to this file (which
      // previously read only the English fields). NOT separately negative-tested for a
      // Chinese-only defect (the existing injector mutates only the English field) —
      // recorded honestly rather than claimed as fully proven; the mechanism reuses
      // the identical, already-tested classify() logic, only with added Chinese
      // phrase alternatives, so it is not untested machinery, but it has not been
      // exercised by a dedicated zh injection. See CONTRACT.md's round-4 addendum.
      description: "A directional beta claim ('moved more/less than the market') may be asserted only when beta differs from 1.0 by more than 1.96 standard errors of the estimate (95% confidence — harmonized with the correlation classification-band guard, HG1_ROUND4_VERIFICATION.md §6); within that band the claim must state 'broadly in line' and disclose the margin. Checks conclusionQuick and explanationSimple INDEPENDENTLY, in English AND (when populated) in claim.i18n.zh.",
      check: function (data) {
        var m = data.getMetric("metric.beta");
        if (!m) return { pass: false, detail: "metric.beta not found" };
        if (typeof m.value !== "number") return { pass: true, detail: "no numeric value — nothing to check" };
        var ev = data.getEvidence ? data.getEvidence("metric.beta") : null;
        var se = ev && typeof ev.standard_error === "number" ? ev.standard_error : null;
        if (se === null) {
          return { pass: false, detail: "metric.beta's Proof Packet exposes no standard_error — cannot verify the directional-claim tolerance band (quant_analyst's rule requires se(β̂) on the evidence object)." };
        }
        var multiplier = (data._internal && typeof data._internal.directionalClaimSeMultiplier === "number") ? data._internal.directionalClaimSeMultiplier : 1.96;
        var diff = m.value - 1;
        var withinBand = Math.abs(diff) <= multiplier * se;
        var expected = withinBand ? "same" : (diff < 0 ? "less" : "more");
        function classify(text) {
          var more = /\b(moved more|more than the (market|benchmark)|amplifies)\b/i.test(text) || /大于市场|放大/.test(text);
          var less = /\b(moved less|less than the (market|benchmark)|dampens)\b/i.test(text) || /小于市场|弱化/.test(text);
          var same = /\b(in line with|broadly in line|about the same as|matches|cannot be (statistically )?distinguished|does not distinguish)\b/i.test(text) || /大体一致|大致相同|无法.{0,20}区分开|同步波动/.test(text);
          var flags = (more ? 1 : 0) + (less ? 1 : 0) + (same ? 1 : 0);
          if (flags !== 1) return null; // no claim, or an ambiguous/contradictory one — never a free pass
          return more ? "more" : (less ? "less" : "same");
        }
        var problems = [];
        var fields = [["conclusionQuick", m.conclusionQuick], ["explanationSimple", m.explanationSimple]];
        if (m.i18n && m.i18n.zh) {
          fields.push(["i18n.zh.conclusionQuick", m.i18n.zh.conclusionQuick], ["i18n.zh.explanationSimple", m.i18n.zh.explanationSimple]);
        }
        fields.forEach(function (pair) {
          var name = pair[0], text = pair[1] || "";
          if (!text) return;
          var actual = classify(text);
          if (actual === null) problems.push(name + ": direction claim is ambiguous/unclassifiable (\"" + text + "\")");
          else if (actual !== expected) problems.push(name + ": claims '" + actual + "' but beta=" + m.value + " (se=" + se + ", " + (withinBand ? "WITHIN" : "beyond") + " " + multiplier + " se of 1.0) implies '" + expected + "' (\"" + text + "\")");
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "beta=" + m.value + " se=" + se + " expected='" + expected + "'; conclusionQuick: " + m.conclusionQuick };
      },
      injectDefect: function (data) {
        var m = data.getMetric("metric.beta");
        // The REAL defect quant_analyst found: a confident directional claim asserted
        // on a difference the sample cannot actually distinguish from zero. This is a
        // meaningful negative test precisely because it is the live defect, not a
        // hypothetical one — on this dataset beta sits WITHIN the tolerance band, so
        // the correct claim is "broadly in line" and this injected text is wrong.
        return withMutatedFields(m, { conclusionQuick: "Your portfolio has historically moved less than the market (beta " + m.value.toFixed(2) + ", below 1)." });
      }
    },

    // ---- Binding assertion 2 (PD-0014 §2.3 #2) ----
    {
      id: "binding2.contributionToRisk.rankingClaim",
      description: "'X and Y contribute the most' must name the actual top-ranked AVAILABLE segment(s) IN THE SPECIFIC SENTENCE making that claim, and must never name a withheld segment there without disclosing the withholding.",
      check: function (data) {
        var c = data.getContributionToRisk();
        var segs = (c && c.segments) || [];
        if (!segs.length) return { pass: false, detail: "no contribution-to-risk segments returned" };
        var avail = segs.filter(function (s) { return s.sufficiency === "AVAILABLE" && typeof s.value === "number"; });
        var withheld = segs.filter(function (s) { return s.sufficiency !== "AVAILABLE"; });
        var text = (c.claim && c.claim.conclusionQuick) || "";
        if (avail.length === 0) return { pass: true, detail: "no AVAILABLE segment to rank; text: " + text };
        var ranked = avail.slice().sort(function (a, b) { return b.value - a.value; });
        var top = ranked[0];
        var sentences = splitSentences(text);
        var mostSentence = sentences.filter(function (s) { return /\bthe most\b|\blargest contributor\b|\bcontributes?\s+most\b/i.test(s); })[0];
        if (!mostSentence) return { pass: false, detail: "text contains no 'contributes the most'-style claim to check: " + text };
        var topName = shortSleeveName(top.label);
        if (!containsWholeWord(mostSentence, topName)) {
          return { pass: false, detail: "the 'most'-claiming sentence (\"" + mostSentence + "\") does not name the actual top-ranked segment '" + top.label + "' (" + top.value + ")" };
        }
        var withheldNamedWithoutDisclosure = withheld.some(function (s) {
          return containsWholeWord(mostSentence, shortSleeveName(s.label)) && !/withheld|excluded|insufficient/i.test(mostSentence);
        });
        if (withheldNamedWithoutDisclosure) {
          return { pass: false, detail: "the 'most'-claiming sentence names a withheld segment without disclosing the withholding: \"" + mostSentence + "\"" };
        }
        return { pass: true, detail: "sentence: \"" + mostSentence + "\"; top=" + top.label + " (" + top.value + ")" };
      },
      injectDefect: function (data) {
        var c = data.getContributionToRisk();
        return withMutatedFields(c.claim, { conclusionQuick: "Hong Kong and Mainland China sleeves contribute the most to overall portfolio risk." });
      }
    },

    // ---- Binding assertion 3 (PD-0014 §2.3 #3) ----
    {
      id: "binding3.correlation.rankClaim",
      description: "A sentence naming the HK/CN pair as strong/together (or asserting bonds differentially diversify) must match the actual ranked matrix values — scoped to the SPECIFIC sentence making that claim, not the whole text, and using no invented absolute strong/weak threshold (that rule is quant_analyst's to set; this checks rank-consistency only).",
      check: function (data) {
        var cm = data.getCorrelationMatrix();
        if (!cm || !cm.matrix || !cm.labels) return { pass: false, detail: "no correlation matrix available" };
        var labels = cm.labels, matrix = cm.matrix;
        var hkIdx = labels.indexOf("HK Equity Sleeve"), cnIdx = labels.indexOf("CN Equity Sleeve"), bondIdx = labels.indexOf("Bonds");
        if (hkIdx < 0 || cnIdx < 0) return { pass: false, detail: "expected sleeve labels not found: " + labels.join(", ") };
        var hkCn = matrix[hkIdx][cnIdx];
        var equityIdx = labels.map(function (l, i) { return { l: l, i: i }; }).filter(function (x) { return x.l.indexOf("Equity Sleeve") >= 0; });
        var pairs = [];
        for (var a = 0; a < equityIdx.length; a++) {
          for (var b = a + 1; b < equityIdx.length; b++) {
            pairs.push({ a: equityIdx[a].l, b: equityIdx[b].l, v: matrix[equityIdx[a].i][equityIdx[b].i] });
          }
        }
        if (!pairs.length) return { pass: false, detail: "fewer than two equity sleeves found in matrix labels" };
        pairs.sort(function (x, y) { return y.v - x.v; });
        var strongest = pairs[0], weakest = pairs[pairs.length - 1];
        var hkCnIsWeakest = approxEqual(hkCn, weakest.v, 1e-9);
        var hkCnIsStrongest = approxEqual(hkCn, strongest.v, 1e-9);
        var text = (cm.claim && cm.claim.conclusionQuick) || "";
        var sentences = splitSentences(text);
        var hkAliases = ["HK", "Hong Kong"], cnAliases = ["CN", "Mainland China"];
        var strongWordRe = /\b(strong|strongly|high|closely|highly correlated|move together)\b/i;
        var weakWordRe = /\b(weak|weakest|low|least|not meaningfully|no more)\b/i;
        var pairSentence = sentences.filter(function (s) { return mentionsPair(s, hkAliases, cnAliases); })[0];
        if (pairSentence) {
          var strong = strongWordRe.test(pairSentence), weak = weakWordRe.test(pairSentence);
          if (strong && !weak && hkCnIsWeakest && !hkCnIsStrongest) {
            return { pass: false, detail: "sentence claims the HK/CN pair is strong, but rho(HK,CN)=" + hkCn + " is the WEAKEST equity pair in this matrix: \"" + pairSentence + "\"" };
          }
        }
        if (bondIdx >= 0) {
          var bondsSentence = sentences.filter(function (s) { return /bonds?\s+diversif/i.test(s); })[0];
          if (bondsSentence && !/not meaningfully|no more|similarly/i.test(bondsSentence)) {
            var hkBond = matrix[hkIdx][bondIdx];
            if (approxEqual(hkBond, hkCn, 0.03)) {
              return { pass: false, detail: "sentence claims bonds diversify, but bonds are no more diversifying against HK (rho=" + hkBond + ") than CN itself is (rho=" + hkCn + "): \"" + bondsSentence + "\"" };
            }
          }
        }
        return { pass: true, detail: "rho(HK,CN)=" + hkCn + "; strongest=" + strongest.a + "/" + strongest.b + "=" + strongest.v + "; weakest=" + weakest.a + "/" + weakest.b + "=" + weakest.v + "; text: " + text };
      },
      injectDefect: function (data) {
        var cm = data.getCorrelationMatrix();
        return withMutatedFields(cm.claim, { conclusionQuick: "Your Hong Kong and Mainland China sleeves move together strongly; bonds diversify both." });
      }
    },

    // ---- Correlation classification-band precision guard (quant_analyst verification
    // §5.2, TIGHTENED to 1.96 se on re-verification) — a STRICT ADDITION alongside
    // binding3 above (which keeps its rank-based check unchanged, per the quant's
    // explicit instruction), implemented as its own assertion so it gets its own
    // demonstrated negative test rather than being buried inside a check whose
    // early-return-on-first-failure structure would make a band-specific defect
    // unreachable behind the rank check. Verifies: (1) any band label asserted for the
    // HK/CN pair matches the value's actual band, and (2) a label may only be
    // asserted when the precision guard holds (nearest boundary ≥1.96 standard errors
    // away — 95% confidence). quant_analyst's original threshold was a bare 1 se,
    // quoting se(HK/CN)=0.048 — actually the US/HK row's figure; the correct se
    // (~0.060) let the 1-se guard's verdict flip depending on whether the local or
    // base basis was used to evaluate the SAME pair. At 1.96 se the HK/CN pair no
    // longer clears on either basis (only US/HK does), so the ambiguity is gone
    // rather than merely narrowed. This designer correctly declined to invent the
    // original threshold; quant_analyst set it, then corrected it. ----
    {
      id: "correlation.bandClassificationPrecision",
      description: "A correlation band label (e.g. 'weakly co-moving') may only be asserted when the value clears the nearest band boundary by at least 1.96 standard errors (95% confidence; se(ρ) ≈ (1-ρ²)/√(n-1)), and the asserted label must match the value's actual band — checked on the HK/CN pair, on the reporting-currency (base) basis per §4.3, via data._internal.correlationBandInfo.",
      check: function (data) {
        var cm = data.getCorrelationMatrix ? data.getCorrelationMatrix() : null;
        var text = (cm && cm.claim && cm.claim.conclusionQuick) || "";
        var bandLabels = ["move almost identically", "strongly co-moving", "moderately co-moving", "weakly co-moving", "largely independent"];
        var sentences = splitSentences(text);
        var hkAliases = ["HK", "Hong Kong"], cnAliases = ["CN", "Mainland China"];
        var bandSentence = sentences.filter(function (s) {
          return mentionsPair(s, hkAliases, cnAliases) && bandLabels.some(function (lbl) { return s.toLowerCase().indexOf(lbl) >= 0; });
        })[0];
        if (!bandSentence) return { pass: true, detail: "no band-label claim present for the HK/CN pair — nothing to check (rank-only language is always permitted without this guard)" };
        var info = data._internal && data._internal.correlationBandInfo && data._internal.correlationBandInfo.hkCn;
        if (!info) return { pass: false, detail: "a band-label claim is present but data._internal.correlationBandInfo.hkCn is not exposed to verify it: \"" + bandSentence + "\"" };
        if (!info.assertable) {
          return { pass: false, detail: "band label asserted (rho_base=" + info.rhoBase + ", se=" + info.se + ") but the precision guard FAILS — the nearest boundary is within 1.96 standard errors (95% confidence), so no band label may be asserted here: \"" + bandSentence + "\"" };
        }
        var assertedLabel = bandLabels.filter(function (lbl) { return bandSentence.toLowerCase().indexOf(lbl) >= 0; })[0];
        if (assertedLabel !== info.band) {
          return { pass: false, detail: "asserted band '" + assertedLabel + "' does not match rho_base=" + info.rhoBase + "'s actual band '" + info.band + "': \"" + bandSentence + "\"" };
        }
        return { pass: true, detail: "band '" + assertedLabel + "' correctly matches rho_base=" + info.rhoBase + " (se=" + info.se + ", assertable)" };
      },
      injectDefect: function (data) {
        var cm = data.getCorrelationMatrix();
        // Appends a band label for HK/CN that is wrong on TWO counts under the current
        // (1.96 se) guard: this pair's underlying classification is "weakly co-moving"
        // (not "strongly"), AND at 1.96 se it no longer clears the precision guard at
        // all, so no band label is assertable for it under any name. Either count alone
        // makes this a mechanically real defect of the shape this assertion exists to
        // catch; the check reports via the (now more common) "precision guard FAILS"
        // branch first.
        return withMutatedFields(cm.claim, { conclusionQuick: cm.claim.conclusionQuick + " On the reporting-currency basis, Hong Kong and Mainland China are strongly co-moving." });
      }
    },

    // ---- Binding assertion 4 (PD-0014 §2.3 #4 / §2.4) ----
    {
      id: "binding4.beta.observationCountMatchesEvidence",
      description: "An observation-count caveat must itself state the SAME count the Proof Packet exposes — checked in the caveat field alone (never concatenated with investorDetail, which could independently be correct and mask a defective caveat).",
      check: function (data) {
        var m = data.getMetric("metric.beta");
        var ev = data.getEvidence ? data.getEvidence("metric.beta") : null;
        if (!m) return { pass: false, detail: "metric.beta not found" };
        if (!ev || typeof ev.observations !== "number") return { pass: false, detail: "no Evidence/Proof Packet observations field found for metric.beta" };
        function extractDailyCount(text) {
          var match = String(text || "").match(/(\d+)\s*daily/i);
          return match ? Number(match[1]) : null;
        }
        var caveatCount = extractDailyCount(m.caveat);
        if (caveatCount === null) return { pass: false, detail: "metric.beta.caveat contains no 'N daily' observation count to check against the Proof Packet: \"" + m.caveat + "\"" };
        if (caveatCount !== ev.observations) return { pass: false, detail: "caveat states " + caveatCount + " daily observations; Proof Packet (getEvidence) states " + ev.observations };
        var investorCount = extractDailyCount(m.investorDetail);
        if (investorCount !== null && investorCount !== ev.observations) {
          return { pass: false, detail: "investorDetail states " + investorCount + " daily observations; Proof Packet states " + ev.observations };
        }
        return { pass: true, detail: "caveat=" + caveatCount + " investorDetail=" + investorCount + " evidence=" + ev.observations };
      },
      injectDefect: function (data) {
        var m = data.getMetric("metric.beta");
        return withMutatedFields(m, { caveat: "24 monthly-equivalent observations in the current window (36 preferred minimum)." });
      }
    },

    // ---- Additional assertions ----
    {
      id: "sleeveWeights.matchHoldings",
      description: "SLEEVE_WEIGHTS must match the actual holdings' market-value weights, recomputed independently from the public getHoldings() accessor (PD-0014 §2.5's 'one canonical portfolio state').",
      check: function (data) {
        var holdings = data.getHoldings ? data.getHoldings() : null;
        var internal = data._internal;
        if (!holdings || !holdings.length) return { pass: false, detail: "no holdings returned" };
        if (!internal || !internal.sleeveWeights) return { pass: false, detail: "APP.data._internal.sleeveWeights not exposed" };
        var total = holdings.reduce(function (s, h) { return s + (h.marketValueUSD || 0); }, 0);
        if (!total) return { pass: false, detail: "total holdings value computed as 0" };
        function sumWhere(pred) { return holdings.filter(pred).reduce(function (s, h) { return s + (h.marketValueUSD || 0); }, 0); }
        var expected = {
          bond: sumWhere(function (h) { return h.assetClass === "Fixed Income Fund"; }) / total,
          us: sumWhere(function (h) { return h.listingMarket === "US" && h.assetClass !== "Fixed Income Fund"; }) / total,
          hk: sumWhere(function (h) { return h.listingMarket === "HK"; }) / total,
          cn: sumWhere(function (h) { return h.listingMarket === "CN"; }) / total
        };
        var actual = internal.sleeveWeights;
        var keys = ["us", "hk", "cn", "bond"];
        var mismatches = keys.filter(function (k) { return !approxEqual(actual[k], expected[k], 1e-6); });
        return {
          pass: mismatches.length === 0,
          detail: mismatches.length ? ("mismatch on " + mismatches.join(", ") + "; expected=" + JSON.stringify(expected) + " actual=" + JSON.stringify(actual))
            : "expected=" + JSON.stringify(expected) + " actual=" + JSON.stringify(actual)
        };
      },
      injectDefect: function (data) {
        return withMutatedFields(data._internal.sleeveWeights, { us: 0.40, hk: 0.30, cn: 0.20, bond: 0.10 });
      }
    },

    {
      id: "fxAttribution.portfolioIdentityExact",
      description: "The 'local return' analytics.js derives as total-minus-FX must equal the INDEPENDENTLY-tracked PERIOD_RETURN_LOCAL — cross-checked from two separate sources, not re-derived from itself (a prior version of this check was tautological and could never fail).",
      check: function (data) {
        var ret = data.getMetric("metric.return.1y");
        var fx = data.getMetric("metric.fxAttribution");
        var detail = data.getFxAttributionDetail ? data.getFxAttributionDetail() : null;
        if (!ret || !fx || !detail || !detail.portfolio || typeof ret.value !== "number" || typeof fx.value !== "number") {
          return { pass: false, detail: "missing metric.return.1y, metric.fxAttribution, or getFxAttributionDetail()" };
        }
        var derivedLocal = ret.value - fx.value;          // what analytics.js's waterfall computes
        var actualLocal = detail.portfolio.local;          // the independently-tracked PERIOD_RETURN_LOCAL
        return { pass: approxEqual(derivedLocal, actualLocal, 1e-9), detail: "derived local (total-FX)=" + derivedLocal + " independently-tracked local=" + actualLocal };
      },
      injectDefect: function (data) {
        var fx = data.getMetric("metric.fxAttribution");
        return withMutatedFields(fx, { value: fx.value + 0.05 });
      }
    },

    {
      id: "fxAttribution.sleeveIdentityExact",
      description: "Sleeve-level FX identity R_base=(1+R_local)(1+R_fx)-1 must hold exactly for HK and CN (methodology findings §4.3) — re-derived independently of data.js's own combineLocalFx implementation.",
      check: function (data) {
        if (typeof data.getFxAttributionDetail !== "function") return { pass: false, detail: "getFxAttributionDetail() accessor not found" };
        var detail = data.getFxAttributionDetail();
        if (!detail || !detail.sleeves) return { pass: false, detail: "getFxAttributionDetail() returned no sleeves" };
        var msgs = [], ok = true;
        ["hk", "cn"].forEach(function (k) {
          var s = detail.sleeves[k];
          if (!s) { ok = false; msgs.push(k + ": missing"); return; }
          var expectedBase = (1 + s.local) * (1 + s.fx) - 1;
          var pass = approxEqual(expectedBase, s.base, 1e-9);
          if (!pass) ok = false;
          msgs.push(k + ": expected=" + expectedBase + " actual=" + s.base);
        });
        return { pass: ok, detail: msgs.join("; ") };
      },
      injectDefect: function (data) {
        return withMutatedAccessor(data, "getFxAttributionDetail", function (result) {
          if (result && result.sleeves && result.sleeves.hk) {
            // Arithmetic sum instead of exact geometric compounding — the exact defect
            // class methodology findings §4.2 named (interaction term silently dropped).
            result.sleeves.hk.base = result.sleeves.hk.local + result.sleeves.hk.fx;
          }
          return result;
        });
      }
    },

    {
      id: "insight.drawdown.directionClaim",
      description: "Drawdown insight's 'deeper'/'shallower' wording must match the actual portfolio-vs-benchmark max-drawdown values.",
      check: function (data) {
        var maxDD = data.getMetric("metric.maxDrawdown");
        var insight = data.getInsight ? data.getInsight("insight.drawdown.deeper") : null;
        if (!maxDD || !insight) return { pass: false, detail: "missing metric.maxDrawdown or insight.drawdown.deeper" };
        var benchMatch = (maxDD.referencePoint || "").match(/(-?\d+(?:\.\d+)?)%/);
        if (!benchMatch) return { pass: false, detail: "could not parse benchmark drawdown from referencePoint: " + maxDD.referencePoint };
        var benchDD = Number(benchMatch[1]) / 100;
        var pfDD = maxDD.value;
        if (typeof pfDD !== "number") return { pass: false, detail: "metric.maxDrawdown has no numeric value" };
        var actuallyDeeper = pfDD < benchDD;
        var textSaysDeeper = /deeper/i.test(insight.claim || "");
        var textSaysShallower = /shallower/i.test(insight.claim || "");
        if (actuallyDeeper && !textSaysDeeper) return { pass: false, detail: "portfolio DD " + pfDD + " IS deeper than benchmark " + benchDD + " but text doesn't say 'deeper': " + insight.claim };
        if (!actuallyDeeper && !textSaysShallower) return { pass: false, detail: "portfolio DD " + pfDD + " is NOT deeper than benchmark " + benchDD + " but text doesn't say 'shallower': " + insight.claim };
        return { pass: true, detail: "portfolio=" + pfDD + " benchmark=" + benchDD + "; text: " + insight.claim };
      },
      injectDefect: function (data) {
        var insight = data.getInsight("insight.drawdown.deeper");
        var isDeeper = /deeper/i.test(insight.claim || "");
        var flipped = isDeeper ? insight.claim.replace(/deeper/i, "shallower") : insight.claim.replace(/shallower/i, "deeper");
        return withMutatedFields(insight, { claim: flipped });
      }
    },

    {
      id: "metric.volatility.comparisonClaim",
      description: "Volatility's 'more/less/about the same as benchmark' wording must match ANNUAL_VOL vs BENCHMARK_ANNUAL_VOL.",
      check: function (data) {
        var m = data.getMetric("metric.volatility");
        if (!m || typeof m.value !== "number") return { pass: true, detail: "metric.volatility not AVAILABLE — nothing to check" };
        var benchMatch = (m.referencePoint || "").match(/(-?\d+(?:\.\d+)?)%/);
        if (!benchMatch) return { pass: false, detail: "could not parse benchmark vol from referencePoint: " + m.referencePoint };
        var benchVol = Number(benchMatch[1]) / 100;
        var text = m.conclusionQuick || "";
        var moreClaimed = /varied more/i.test(text), lessClaimed = /varied less/i.test(text), sameClaimed = /about the same/i.test(text);
        if (m.value > benchVol && !moreClaimed) return { pass: false, detail: "portfolio vol " + m.value + " > benchmark " + benchVol + " but text doesn't say 'more': " + text };
        if (m.value < benchVol && !lessClaimed) return { pass: false, detail: "portfolio vol " + m.value + " < benchmark " + benchVol + " but text doesn't say 'less': " + text };
        if (m.value === benchVol && !sameClaimed) return { pass: false, detail: "portfolio vol equals benchmark but text doesn't say 'about the same': " + text };
        return { pass: true, detail: "portfolio=" + m.value + " benchmark=" + benchVol + "; text: " + text };
      },
      injectDefect: function (data) {
        var m = data.getMetric("metric.volatility");
        var isMore = /varied more/i.test(m.conclusionQuick || "");
        var wrong = isMore ? "Your portfolio's return has historically varied less than its benchmark." : "Your portfolio's return has historically varied more than its benchmark.";
        return withMutatedFields(m, { conclusionQuick: wrong });
      }
    },

    {
      id: "metric.concentration.majorityClaim",
      description: "Concentration's 'majority' vs. 'significant, but not majority' claim must match TOP5_SUM / total-holdings-value actually being > 50%.",
      check: function (data) {
        var m = data.getMetric("metric.concentration");
        if (!m || typeof m.value !== "number") return { pass: true, detail: "metric.concentration not AVAILABLE — nothing to check" };
        var text = m.conclusionQuick || "";
        var claimsMajority = /\bmajority\b/i.test(text) && !/not majority/i.test(text);
        var isMajority = m.value > 0.5;
        return { pass: claimsMajority === isMajority, detail: "value=" + m.value + " isMajority=" + isMajority + " claimsMajority=" + claimsMajority + "; text: " + text };
      },
      injectDefect: function (data) {
        var m = data.getMetric("metric.concentration");
        var isMajority = m.value > 0.5;
        var wrong = isMajority ? "Your top five holdings make up a significant, but not majority, share of invested value." : "Your top five holdings make up a majority of invested value.";
        return withMutatedFields(m, { conclusionQuick: wrong });
      }
    },

    {
      id: "var95.magnitudeConvention",
      description: "1-Day 95% VaR must render as a non-negative magnitude with no sign character and must not be marked directional (methodology findings §3.2).",
      check: function (data) {
        var m = data.getMetric("metric.var95");
        if (!m) return { pass: false, detail: "metric.var95 not found" };
        if (m.directional) return { pass: false, detail: "metric.var95 must not be marked directional" };
        if (m.formatted != null && /^[-+]/.test(m.formatted)) return { pass: false, detail: "metric.var95.formatted carries a leading sign character: " + m.formatted };
        return { pass: true, detail: "formatted=" + m.formatted + " directional=" + m.directional };
      },
      injectDefect: function (data) {
        var m = data.getMetric("metric.var95");
        return withMutatedFields(m, { directional: true, formatted: "-" + (m.formatted || "1.3% of portfolio value") });
      }
    },

    // ---- SSE trading-session calendar (HG1 round 4 — owner-mandated correction).
    // REPLACES the prior `freshness.cnSessionAware` assertion, whose premise the
    // owner falsified: 2026-09-03 is an ordinary SSE/SZSE trading Thursday, not a
    // market holiday, so the CN A-share print (dated 2026-09-02) is genuinely STALE
    // by one completed session, not "session-current." Keeping the old assertion
    // around, even inert, would have meant shipping a control that asserts something
    // now known to be false — worse than no control (the same principle that governs
    // every injector in this file). The five assertions below are the owner's own
    // specified regression coverage: (1) a normal weekday session, (2) a weekend,
    // (3) an official exchange holiday, (4) a normally completed trading session
    // (zero sessions elapsed), and (5) a previous-session price carried into a new
    // open trading day — the exact shape of the shipped defect, and the one that
    // matters most. Each calls data.js's OWN calendar functions
    // (data._internal.sseSessionInfo / sseSessionsElapsed) against independently
    // verifiable reference facts (day-of-week is deterministic; specific dates in
    // 2026-08 are verified here by fixed offset from the owner's own verified anchor,
    // 2026-09-03 = Thursday) rather than re-implementing the calendar to check it —
    // there is a ground truth here to test against, unlike a ranking judgment. ----
    {
      id: "sseCalendar.normalWeekday",
      description: "A normal weekday with no holiday entry (2026-08-18, a Tuesday — 16 days before the owner's independently verified anchor 2026-09-03=Thursday, computed by fixed 7-day-cycle offset, not asserted) must classify as a trading day.",
      check: function (data) {
        if (typeof data._internal !== "object" || typeof data._internal.sseSessionInfo !== "function") {
          return { pass: false, detail: "data._internal.sseSessionInfo not exposed" };
        }
        var info = data._internal.sseSessionInfo("2026-08-18");
        return { pass: info.tradingDay === true && info.reason === "TRADING_DAY", detail: "sseSessionInfo('2026-08-18') = " + JSON.stringify(info) };
      },
      injectDefect: function (data) {
        // Realistic negative test: a wrong calendar entry (the actual root-cause
        // shape of the shipped defect) rather than a hypothetical code bug.
        data._internal.sseHolidayDates["2026-08-18"] = "injected false holiday";
        return function restore() { delete data._internal.sseHolidayDates["2026-08-18"]; };
      }
    },
    {
      id: "sseCalendar.weekend",
      description: "A Saturday (2026-09-05 — two days after the verified 2026-09-03=Thursday anchor) must classify as a non-trading day for the WEEKEND reason, independent of the holiday list.",
      check: function (data) {
        if (typeof data._internal !== "object" || typeof data._internal.sseSessionInfo !== "function") {
          return { pass: false, detail: "data._internal.sseSessionInfo not exposed" };
        }
        var info = data._internal.sseSessionInfo("2026-09-05");
        return { pass: info.tradingDay === false && info.reason === "WEEKEND", detail: "sseSessionInfo('2026-09-05') = " + JSON.stringify(info) };
      },
      injectDefect: function (data) {
        // Weekend determination is native Date arithmetic, not a data table, so the
        // realistic injector here wraps the function itself (same technique already
        // used elsewhere in this file for computed, not tabular, accessors).
        return withMutatedAccessor(data._internal, "sseSessionInfo", function (result, args) {
          if (args && args[0] === "2026-09-05") return { date: "2026-09-05", tradingDay: true, reason: "TRADING_DAY" };
          return result;
        });
      }
    },
    {
      id: "sseCalendar.officialHoliday",
      description: "An official exchange holiday (2026-10-01, National Day — a Thursday, so this is a clean holiday-only test unconfounded by weekend logic) must classify as a non-trading day for the HOLIDAY reason.",
      check: function (data) {
        if (typeof data._internal !== "object" || typeof data._internal.sseSessionInfo !== "function") {
          return { pass: false, detail: "data._internal.sseSessionInfo not exposed" };
        }
        var info = data._internal.sseSessionInfo("2026-10-01");
        return { pass: info.tradingDay === false && info.reason === "HOLIDAY", detail: "sseSessionInfo('2026-10-01') = " + JSON.stringify(info) };
      },
      injectDefect: function (data) {
        var original = data._internal.sseHolidayDates["2026-10-01"];
        delete data._internal.sseHolidayDates["2026-10-01"];
        return function restore() { data._internal.sseHolidayDates["2026-10-01"] = original; };
      }
    },
    {
      id: "sseCalendar.normallyCompletedSession",
      description: "A normally completed trading session — the print's own date IS the most recent session and no newer session has occurred since (hk_equity's real print date vs. the snapshot's own as-of date) — must show zero elapsed sessions, and a Friday-to-Monday gap must count as exactly one session (a weekend in between must not inflate the count).",
      check: function (data) {
        if (typeof data._internal !== "object" || typeof data._internal.sseSessionsElapsed !== "function") {
          return { pass: false, detail: "data._internal.sseSessionsElapsed not exposed" };
        }
        var sameDay = data._internal.sseSessionsElapsed("2026-09-03", "2026-09-03");
        var fridayToMonday = data._internal.sseSessionsElapsed("2026-08-28", "2026-08-31"); // Fri -> Mon, verified offsets from the 09-03=Thursday anchor
        var problems = [];
        if (sameDay !== 0) problems.push("same-day sessionsElapsed should be 0, got " + sameDay);
        if (fridayToMonday !== 1) problems.push("Friday-to-Monday sessionsElapsed should be 1 (weekend must not inflate it), got " + fridayToMonday);
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "sameDay=" + sameDay + " fridayToMonday=" + fridayToMonday };
      },
      injectDefect: function (data) {
        return withMutatedAccessor(data._internal, "sseSessionsElapsed", function (result, args) {
          if (args && args[0] === "2026-09-03" && args[1] === "2026-09-03") return result + 1; // wrongly claim a session elapsed on a same-day check
          return result;
        });
      }
    },
    {
      id: "sseCalendar.previousSessionCarriedIntoNewTradingDay",
      description: "THE case the fixture originally got wrong: a print dated 2026-09-02, with 2026-09-03 (an ordinary trading day, not a holiday) having since occurred, must show exactly 1 session elapsed, and the CN A-share freshness axis itself must be classified STALE (not END_OF_DAY) as a direct, derived consequence — checked against the live axis, not just the calendar function in isolation.",
      check: function (data) {
        if (typeof data._internal !== "object" || typeof data._internal.sseSessionsElapsed !== "function") {
          return { pass: false, detail: "data._internal.sseSessionsElapsed not exposed" };
        }
        var elapsed = data._internal.sseSessionsElapsed("2026-09-02", "2026-09-03");
        if (elapsed !== 1) return { pass: false, detail: "sseSessionsElapsed('2026-09-02','2026-09-03') should be 1, got " + elapsed };
        var fr = data.getFreshness ? data.getFreshness() : null;
        var cn = fr && fr.axes && fr.axes.filter(function (a) { return a.axis === "cn_equity"; })[0];
        if (!cn) return { pass: false, detail: "no cn_equity freshness axis found" };
        if (cn.state !== "STALE") return { pass: false, detail: "cn_equity.state should be STALE (1 session elapsed with no update) but is '" + cn.state + "'" };
        return { pass: true, detail: "sessionsElapsed=" + elapsed + " cn_equity.state=" + cn.state };
      },
      injectDefect: function (data) {
        // Reproduces the EXACT shipped defect: the axis claiming END_OF_DAY /
        // "session-current" while the calendar (unmutated, still correctly computing
        // 1 session elapsed) says otherwise — the real historical inconsistency, not
        // a hypothetical one.
        var fr = data.getFreshness();
        var cn = fr.axes.filter(function (a) { return a.axis === "cn_equity"; })[0];
        return withMutatedFields(cn, { state: "END_OF_DAY" });
      }
    },

    // ---- getFreshness().leastFreshAxis (PD-0014 §2.2 — "least fresh: X" is a
    // material claim about the data, no different in kind from a metric conclusion,
    // even though it renders as a status strip rather than a claim card). A real
    // shipped regression: shell.js's severity table ranked END_OF_DAY worse than
    // DELAYED (backwards — an end-of-day close is a complete, authoritative value for
    // a concluded session; a delayed feed is an incomplete, lagging one mid-session),
    // then broke the resulting three-way END_OF_DAY tie by array position, so
    // `us_equity` (listed first) won even though two DELAYED FX axes were in a
    // strictly worse state. Fixed in shell.js; this assertion is the control that
    // would have caught it, and guards the regression going forward. It slipped past
    // every other assertion in this file because everyone — this designer included —
    // treated the freshness strip as chrome rather than as a claim; see CONTRACT.md's
    // round-4 addendum for the generalization.
    //
    // Deliberately does NOT re-implement rankLeastFresh (shell.js, out of this
    // designer's write path) to diff its output against the real one — two
    // implementations that happen to agree proves nothing, and two that happen to
    // share the same bug would still agree. Instead it asserts PROPERTIES of the
    // returned axis against the full set, using a severity order reasoned
    // independently from what each state actually MEANS (not copied from shell.js's
    // table): a market/feed that never updated (STALE) is worse than one actively
    // lagging mid-session (DELAYED), which is worse than a completed, authoritative
    // end-of-day close (END_OF_DAY), which is worse than a genuinely real-time feed
    // (LIVE). Two properties, matching the coordinator's exact framing: (1) no axis
    // present has strictly worse severity than the named one, and (2) among axes tied
    // on severity, none has a larger delayMinutes than the named one. ----
    {
      id: "freshness.leastFreshAxisCorrect",
      description: "getFreshness().leastFreshAxis must name an axis whose severity is at least as bad as every other axis present, and — among axes tied on severity — must not be beaten by one with a larger delayMinutes. Checks PROPERTIES of the returned axis against the full set; does not re-implement rankLeastFresh's own algorithm.",
      check: function (data) {
        if (typeof data.getFreshness !== "function") return { pass: false, detail: "getFreshness() accessor not found" };
        var fr = data.getFreshness();
        var axes = (fr && fr.axes) || [];
        var namedKey = fr && fr.leastFreshAxis;
        if (!axes.length) return { pass: false, detail: "no freshness axes returned" };
        if (namedKey === null || namedKey === undefined) {
          return { pass: true, detail: "leastFreshAxis is null (a declared tie) — nothing to check" };
        }
        var named = axes.filter(function (a) { return a.axis === namedKey; })[0];
        if (!named) return { pass: false, detail: "leastFreshAxis '" + namedKey + "' does not match any axis in the returned set" };
        var SEVERITY_RANK = { STALE: 3, DELAYED: 2, END_OF_DAY: 1, LIVE: 0 };
        function severityOf(axis) {
          return Object.prototype.hasOwnProperty.call(SEVERITY_RANK, axis.state) ? SEVERITY_RANK[axis.state] : null;
        }
        var namedSeverity = severityOf(named);
        if (namedSeverity === null) return { pass: false, detail: "leastFreshAxis '" + namedKey + "' has an unrecognized state '" + named.state + "' — cannot verify" };
        var problems = [];
        axes.forEach(function (a) {
          if (a.axis === namedKey) return;
          var s = severityOf(a);
          if (s === null) { problems.push("axis '" + a.axis + "' has an unrecognized state '" + a.state + "'"); return; }
          if (s > namedSeverity) {
            problems.push("axis '" + a.axis + "' (state=" + a.state + ", severity=" + s + ") is WORSE than the named leastFreshAxis '" + namedKey + "' (state=" + named.state + ", severity=" + namedSeverity + ")");
          } else if (s === namedSeverity) {
            var namedDelay = typeof named.delayMinutes === "number" ? named.delayMinutes : 0;
            var otherDelay = typeof a.delayMinutes === "number" ? a.delayMinutes : 0;
            if (otherDelay > namedDelay) {
              problems.push("axis '" + a.axis + "' shares severity with '" + namedKey + "' but has a larger delayMinutes (" + otherDelay + " > " + namedDelay + ")");
            }
          }
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "leastFreshAxis='" + namedKey + "' (state=" + named.state + ") correctly dominates every other axis present" };
      },
      injectDefect: function (data) {
        // Reproduces the actual shipped regression: force leastFreshAxis to an
        // END_OF_DAY axis (us_equity) while DELAYED FX axes remain present in the
        // set — exactly the bug this control exists to catch, not a hypothetical one.
        return withMutatedAccessor(data, "getFreshness", function (result) {
          if (result) result.leastFreshAxis = "us_equity";
          return result;
        });
      }
    },

    {
      id: "benchmarkRelative.comparabilityDisclosed",
      description: "A two-leg comparison metric with mixed-timestamp legs must disclose limited temporal comparability and must never claim 'not degraded' (PD-0014 Part 1).",
      check: function (data) {
        var m = data.getMetric("metric.benchmarkRelative");
        if (!m) return { pass: false, detail: "metric.benchmarkRelative not found" };
        var text = m.caveat || "";
        if (/not degraded/i.test(text)) return { pass: false, detail: "caveat still claims 'not degraded': " + text };
        var disclosesTiming = /same instant|timing gap|behind this comparison/i.test(text);
        var hasComparabilityField = !!(m.freshness && m.freshness.comparability && m.freshness.comparability.limited);
        if (!disclosesTiming && !hasComparabilityField) return { pass: false, detail: "no temporal-comparability disclosure found in caveat or freshness.comparability: " + text };
        return { pass: true, detail: "caveat: " + text };
      },
      injectDefect: function (data) {
        var m = data.getMetric("metric.benchmarkRelative");
        return withMutatedFields(m, { caveat: "One input market (Mainland China A-shares) is priced as of a stale print; the comparison remains computable and is not degraded — see the freshness indicator." });
      }
    },

    {
      id: "sortino.noFalseObservationClaim",
      description: "Sortino's caveat must not assert a specific downside-observation shortfall that contradicts the actual downside-day count in this file (methodology findings §7.5).",
      check: function (data) {
        var m = data.getMetric("metric.sortino");
        if (!m) return { pass: false, detail: "metric.sortino not found" };
        var text = m.caveat || "";
        var claimsFewerThan = /fewer than/i.test(text);
        var internalCount = data._internal && data._internal.downsideDayCount;
        if (claimsFewerThan && typeof internalCount === "number" && internalCount > 0 && !/no minimum/i.test(text)) {
          return { pass: false, detail: "caveat claims a shortfall ('fewer than...') while " + internalCount + " downside days exist and no threshold is on file: " + text };
        }
        return { pass: true, detail: text };
      },
      injectDefect: function (data) {
        var m = data.getMetric("metric.sortino");
        return withMutatedFields(m, { caveat: "Fewer than the minimum required downside-return observations in the current window." });
      }
    },

    {
      id: "sml.distanceVsAlphaDistinct",
      description: "The SML claim must not present the regression Jensen's alpha as literally the line's vertical distance (concept 3 vs concept 4) — checked in conclusionQuick and explanationSimple INDEPENDENTLY, never concatenated.",
      check: function (data) {
        if (typeof data.getSMLPoints !== "function") return { pass: false, detail: "getSMLPoints() accessor not found" };
        var sml = data.getSMLPoints();
        var alpha = data.getMetric("metric.alpha");
        if (!sml || !alpha || typeof alpha.value !== "number" || typeof sml.verticalDistance !== "number") {
          return { pass: false, detail: "missing sml.verticalDistance or metric.alpha.value" };
        }
        var smlClaim = sml.claim || {};
        function checkField(name, text) {
          if (!text) return null;
          var assertsIdentical = /vertical distance.{0,60}\bis\b.{0,10}alpha\b/i.test(text);
          if (!assertsIdentical) return null;
          var hasHedge = /different quantit|two different|not identical|not the same number/i.test(text);
          return hasHedge ? null : (name + ": asserts the vertical distance IS alpha without distinguishing the two bases (\"" + text + "\")");
        }
        var problem = checkField("conclusionQuick", smlClaim.conclusionQuick) || checkField("explanationSimple", smlClaim.explanationSimple);
        if (problem) return { pass: false, detail: problem };
        return { pass: true, detail: "verticalDistance=" + sml.verticalDistance + " regressionAlpha=" + alpha.value };
      },
      injectDefect: function (data) {
        var sml = data.getSMLPoints();
        return withMutatedFields(sml.claim, { explanationSimple: "The line shows the return a portfolio at each beta would have needed. The vertical distance between your point and that line is alpha — how far actual results diverged from that model, in this specific historical sample." });
      }
    },

    {
      id: "exposure.sector.largestClaim",
      description: "'X is your largest sector exposure' must match the actual ranked sector-exposure segments.",
      check: function (data) {
        var claimObj = data.getMetric("exposure.sector");
        var ex = data.getExposure ? data.getExposure("sector") : null;
        if (!claimObj || !ex || !ex.segments || !ex.segments.length) return { pass: false, detail: "missing exposure.sector claim or segments" };
        var top = ex.segments[0];
        var claimsIT = /information technology/i.test(claimObj.conclusionQuick || "");
        var isIT = /information technology/i.test(top.label || "");
        return { pass: claimsIT === isIT, detail: "largest segment=" + top.label + " (" + top.value + "); text: " + claimObj.conclusionQuick };
      },
      injectDefect: function (data) {
        var claimObj = data.getMetric("exposure.sector");
        return withMutatedFields(claimObj, { conclusionQuick: "Financials is your largest sector exposure." });
      }
    },

    {
      id: "exposure.economicGeography.chinaLargerThanCnListing",
      description: "'China is larger than the listing-market view suggests' must match economicGeography's China total actually exceeding listingMarket's CN-only total — checks the CLAIM TEXT against the fact, not the fact alone.",
      check: function (data) {
        var claimObj = data.getMetric("exposure.economicGeography");
        var geo = data.getExposure ? data.getExposure("economicGeography") : null;
        var listing = data.getExposure ? data.getExposure("listingMarket") : null;
        if (!claimObj || !geo || !listing) return { pass: false, detail: "missing exposure accessors" };
        var china = (geo.segments.filter(function (s) { return s.label === "China"; })[0] || {}).value || 0;
        var cnListing = (listing.segments.filter(function (s) { return s.label === "CN"; })[0] || {}).value || 0;
        var claimsLarger = /china is larger/i.test(claimObj.conclusionQuick || "");
        var isLarger = china > cnListing;
        return { pass: claimsLarger === isLarger, detail: "economicGeography.China=" + china + " listingMarket.CN=" + cnListing + " claimsLarger=" + claimsLarger };
      },
      injectDefect: function (data) {
        var claimObj = data.getMetric("exposure.economicGeography");
        return withMutatedFields(claimObj, { conclusionQuick: "China's economic-geography exposure matches its listing-market exposure exactly." });
      }
    },

    {
      id: "exposure.assetClass.predominantlyEquity",
      description: "'Predominantly equities, with a fixed-income allocation via TLT' must match the actual largest assetClass segment being equity-labelled — checks the CLAIM TEXT against the fact, not the fact alone.",
      check: function (data) {
        var claimObj = data.getMetric("exposure.assetClass");
        var ex = data.getExposure ? data.getExposure("assetClass") : null;
        if (!claimObj || !ex || !ex.segments || !ex.segments.length) return { pass: false, detail: "missing exposure.assetClass claim or segments" };
        var top = ex.segments[0];
        var topIsEquity = /equity/i.test(top.label || "");
        var claimsPredominantlyEquity = /predominantly equities/i.test(claimObj.conclusionQuick || "");
        return { pass: claimsPredominantlyEquity === topIsEquity, detail: "largest assetClass segment=" + top.label + " (" + top.value + ") claimsPredominantlyEquity=" + claimsPredominantlyEquity };
      },
      injectDefect: function (data) {
        var claimObj = data.getMetric("exposure.assetClass");
        return withMutatedFields(claimObj, { conclusionQuick: "Fixed income dominates this portfolio's asset-class mix." });
      }
    },

    // ---- Sign convention for static levels (owner's §6.3; pm-01 live verification) —
    // a STATIC LEVEL (annualized volatility, a risk-free-rate assumption, a top-5
    // concentration share) must never carry a leading "+"; only a genuine CHANGE
    // (gain/loss, return, alpha, a distance/delta, a weight CHANGE, a signed
    // contribution, a scenario delta) does. `data.js` fixed three concrete sites this
    // was found at (metric.volatility.referencePoint, metric.sml.professionalDetail's
    // risk-free-rate mention, insight.concentration.top5); this assertion checks all
    // three, anchored to the specific phrase preceding each number so a legitimate "+"
    // elsewhere in the same string (e.g. the literal formula "Rf + β×(...)" inside
    // metric.sml.professionalDetail) is never mistaken for the defect. ----
    {
      id: "levelFormatting.noSuperfluousSign",
      description: "A claim describing a static level (volatility, a risk-free-rate assumption, a top-5 concentration share) must not carry a leading '+' — signs are reserved for gains/losses, returns, alpha, weight changes, signed contributions, and scenario deltas (owner's §6.3). Checked at the three concrete sites this defect was found at, each anchored to its own preceding phrase so a legitimate '+' elsewhere (e.g. a formula) is never mistaken for it.",
      check: function (data) {
        var problems = [];
        var vol = data.getMetric("metric.volatility");
        if (vol && /volatility:\s*\+/i.test(vol.referencePoint || "")) {
          problems.push("metric.volatility.referencePoint carries a leading '+' on a level: " + vol.referencePoint);
        }
        var sml = data.getMetric("metric.sml");
        if (sml && /Rf = \+/.test(sml.professionalDetail || "")) {
          problems.push("metric.sml.professionalDetail carries a leading '+' on the risk-free-rate level: " + sml.professionalDetail);
        }
        var top5 = data.getInsight ? data.getInsight("insight.concentration.top5") : null;
        if (top5 && /represent \+/i.test(top5.claim || "")) {
          problems.push("insight.concentration.top5 carries a leading '+' on a concentration level: " + top5.claim);
        }
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "no superfluous '+' found on the three checked level fields" };
      },
      injectDefect: function (data) {
        // Reintroduces the EXACT live defect pm-01 found: "represent +75.1%".
        var top5 = data.getInsight("insight.concentration.top5");
        return withMutatedFields(top5, { claim: top5.claim.replace(/represent (\d)/, "represent +$1") });
      }
    },

    // ---- Scenario reconciliation (PD-0014 §2.2 extended from claims-about-metrics to
    // claims-about-scenarios, per the coordinator's instruction). A scenario's declared
    // `modifications` entry is itself a material claim about what the product did; each
    // of these recomputes the dollar amount that claim implies from an INDEPENDENT
    // source (getHoldings()/the OTHER side of the same allocation table) and confirms
    // it matches the actual change in `comparison.allocation`. Found live by the
    // visual-track designer and pm-01: scenario.reduceCnExposure declared "-50%"
    // against a target string that mixed two dimensions, and computed a 0.85
    // multiplier that reconciled with neither reading. ----
    {
      id: "scenario.reduceCnExposure.reconciles",
      description: "scenario.reduceCnExposure's declared '-50% of the CN-listed sleeve' must match the actual dollar change in the China economic-geography segment it produces — the removed amount is recomputed independently from getHoldings(), not read back from data.js's own internal variable.",
      check: function (data) {
        var scenario = data.getScenario ? data.getScenario("scenario.reduceCnExposure") : null;
        if (!scenario || !scenario.comparison || !scenario.comparison.allocation) return { pass: false, detail: "scenario.reduceCnExposure or its allocation comparison not found" };
        var holdings = data.getHoldings ? data.getHoldings() : null;
        if (!holdings || !holdings.length) return { pass: false, detail: "getHoldings() not found or empty" };
        var cnListedValue = holdings.filter(function (h) { return h.listingMarket === "CN"; }).reduce(function (s, h) { return s + (h.marketValueUSD || 0); }, 0);
        var expectedRemoval = cnListedValue * 0.5;
        var current = scenario.comparison.allocation.current.filter(function (e) { return e.label === "China"; })[0];
        var scenarioSeg = scenario.comparison.allocation.scenario.filter(function (e) { return e.label === "China"; })[0];
        if (!current || !scenarioSeg) return { pass: false, detail: "China segment not found in allocation.current/scenario" };
        var actualRemoval = current.value - scenarioSeg.value;
        return { pass: approxEqual(actualRemoval, expectedRemoval, 0.01), detail: "expected removal (50% of independently-recomputed CN-listed sleeve, " + cnListedValue + ") = " + expectedRemoval + "; actual removal from the China segment = " + actualRemoval };
      },
      injectDefect: function (data) {
        var scenario = data.getScenario("scenario.reduceCnExposure");
        var scenarioSeg = scenario.comparison.allocation.scenario.filter(function (e) { return e.label === "China"; })[0];
        return withMutatedFields(scenarioSeg, { value: scenarioSeg.value + 3000 });
      }
    },

    {
      id: "scenario.addTreasuryCash.reconciles",
      description: "scenario.addTreasuryCash's declared '+$50,000' must match the actual dollar increase in its Fixed-Income-labelled allocation segment.",
      check: function (data) {
        var scenario = data.getScenario ? data.getScenario("scenario.addTreasuryCash") : null;
        if (!scenario || !scenario.comparison || !scenario.comparison.allocation) return { pass: false, detail: "scenario.addTreasuryCash or its allocation comparison not found" };
        var mod = (scenario.modifications || [])[0];
        var match = mod && String(mod.amount || "").match(/\$?([\d,]+)/);
        if (!match) return { pass: false, detail: "could not parse a dollar amount from modifications[0].amount: " + (mod && mod.amount) };
        var declaredAmount = Number(match[1].replace(/,/g, ""));
        var current = scenario.comparison.allocation.current.filter(function (e) { return e.label.indexOf("Fixed Income") >= 0; })[0];
        var scenarioSeg = scenario.comparison.allocation.scenario.filter(function (e) { return e.label.indexOf("Fixed Income") >= 0; })[0];
        if (!current || !scenarioSeg) return { pass: false, detail: "Fixed Income assetClass segment not found" };
        var actualIncrease = scenarioSeg.value - current.value;
        return { pass: approxEqual(actualIncrease, declaredAmount, 0.01), detail: "declared=" + declaredAmount + " actual increase=" + actualIncrease };
      },
      injectDefect: function (data) {
        var scenario = data.getScenario("scenario.addTreasuryCash");
        var scenarioSeg = scenario.comparison.allocation.scenario.filter(function (e) { return e.label.indexOf("Fixed Income") >= 0; })[0];
        return withMutatedFields(scenarioSeg, { value: scenarioSeg.value + 10000 });
      }
    },

    {
      id: "scenario.shiftHkToUs.reconciles",
      description: "scenario.shiftHkToUs's declared '10% of HK sleeve' must match the actual dollar amount removed from HK, and that amount must equal what was added to US (a pure like-for-like reallocation, not two independently-rounded multipliers).",
      check: function (data) {
        var scenario = data.getScenario ? data.getScenario("scenario.shiftHkToUs") : null;
        if (!scenario || !scenario.comparison || !scenario.comparison.allocation) return { pass: false, detail: "scenario.shiftHkToUs or its allocation comparison not found" };
        var hkCurrent = scenario.comparison.allocation.current.filter(function (e) { return e.label === "HK"; })[0];
        var hkScenario = scenario.comparison.allocation.scenario.filter(function (e) { return e.label === "HK"; })[0];
        var usCurrent = scenario.comparison.allocation.current.filter(function (e) { return e.label === "US"; })[0];
        var usScenario = scenario.comparison.allocation.scenario.filter(function (e) { return e.label === "US"; })[0];
        if (!hkCurrent || !hkScenario || !usCurrent || !usScenario) return { pass: false, detail: "HK/US listingMarket segments not found in allocation.current/scenario" };
        var hkRemoved = hkCurrent.value - hkScenario.value;
        var usAdded = usScenario.value - usCurrent.value;
        var expectedRemoved = hkCurrent.value * 0.10;
        var problems = [];
        if (!approxEqual(hkRemoved, expectedRemoved, 0.01)) problems.push("HK removal " + hkRemoved + " != declared 10% of HK's current value (" + expectedRemoved + ")");
        if (!approxEqual(hkRemoved, usAdded, 0.01)) problems.push("HK removal " + hkRemoved + " != US addition " + usAdded + " (not a like-for-like reallocation)");
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "HK removed=" + hkRemoved + " US added=" + usAdded + " (both = 10% of HK's current value)" };
      },
      injectDefect: function (data) {
        var scenario = data.getScenario("scenario.shiftHkToUs");
        var usScenario = scenario.comparison.allocation.scenario.filter(function (e) { return e.label === "US"; })[0];
        return withMutatedFields(usScenario, { value: usScenario.value + 500 });
      }
    },

    // ---- Sector-classification language invariant (PD-0015 §2.3) — handed over by
    // the visual designer, who built APP.ui.classifySectorExposure() and
    // APP.ui.verifySectorClassificationLanguageInvariant() in shell.js (out of this
    // designer's write path) and explicitly asked this file to own the ASSERTED
    // version, since selfcheck.js is the only thing that runs automatically. The
    // trap: classifySectorExposure() groups holdings by sector; if that grouping ever
    // keyed off the DISPLAYED (translatable) label instead of a canonical key,
    // switching language would silently change which holdings bucket together, and
    // each screen would still look internally correct in whichever language it
    // rendered — invisible from either language alone, exactly the shape of defect
    // this whole round-4 cycle exists to close, one layer under the prose this time. ----
    {
      id: "sectorClassification.languageInvariant",
      // The caveat the coordinator asked to be encoded here, not just mentioned in
      // conversation: verifySectorClassificationLanguageInvariant() switches language
      // twice (en, zh) and restores the original — but ITS OWN restore is not wrapped
      // in a try/finally (shell.js, out of this designer's write path), so if
      // classifySectorExposure() ever throws mid-comparison, the app can be stranded
      // in "zh" (or whatever the last switch was). This check wraps its OWN call in a
      // try/catch and attempts a best-effort recovery via the PUBLIC, non-quiet
      // APP.i18n.setLang(originalLang) on catch — visibly re-rendering once, which is
      // not as clean as the quiet restore the utility was supposed to guarantee, but
      // is the only recovery mechanism available from outside shell.js
      // (APP.ui.setLangQuiet is not exported publicly). A throw during the check
      // itself is still reported as a FAILED assertion either way (safeCheck's own
      // try/catch converts it, never a pass).
      description: "classifySectorExposure()'s groupings (canonical key/value/pct) must be identical in English and Chinese — a grouping key must never be a localized string (PD-0015 §2.3). Calls APP.ui.verifySectorClassificationLanguageInvariant(holdings, totalValue) (visual designer's utility, shell.js) and compares canonical fingerprints, never display labels (expected to differ). Degrades to a reported FAILURE — never a silent pass — if APP.ui or the utility is unavailable when this file runs (APP.ui may not exist yet if shell.js has not finished loading). Wraps the call so a throw mid-language-switch attempts a best-effort recovery via the public APP.i18n.setLang rather than leaving the app stranded in the wrong language.",
      check: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.ui || typeof window.APP.ui.verifySectorClassificationLanguageInvariant !== "function") {
          return { pass: false, detail: "APP.ui.verifySectorClassificationLanguageInvariant is not available — cannot verify the sector-classification language invariant. Reported as FAILED (not skipped/passed) so its absence is visible rather than read as a green check that never ran." };
        }
        var holdings = data.getHoldings ? data.getHoldings() : null;
        if (!holdings || !holdings.length) return { pass: false, detail: "no holdings returned from getHoldings() — cannot verify" };
        var total = data.getTotalPortfolioValue ? data.getTotalPortfolioValue() : undefined;
        var langBefore = null;
        try {
          if (window.APP.ui.getLang) langBefore = window.APP.ui.getLang();
          else if (window.APP.i18n && window.APP.i18n.getLang) langBefore = window.APP.i18n.getLang();
        } catch (eLang) { /* if even reading the current language throws, there is nothing to restore to */ }
        var result;
        try {
          result = window.APP.ui.verifySectorClassificationLanguageInvariant(holdings, total);
        } catch (e) {
          try {
            if (langBefore && window.APP.i18n && typeof window.APP.i18n.setLang === "function") {
              window.APP.i18n.setLang(langBefore); // best-effort, visible recovery — see this assertion's own description
            }
          } catch (eRestore) { /* recovery must never itself throw further */ }
          return { pass: false, detail: "verifySectorClassificationLanguageInvariant threw: " + (e && e.message ? e.message : String(e)) + " — attempted best-effort language recovery to '" + langBefore + "'." };
        }
        if (!result) return { pass: false, detail: "verifySectorClassificationLanguageInvariant returned no result" };
        if (!result.identical) {
          return {
            pass: false,
            detail: "sector classification diverges between languages (sectorSegmentsMatch=" + result.sectorSegmentsMatch +
              ", nonSectorSegmentsMatch=" + result.nonSectorSegmentsMatch + ") — en=" + JSON.stringify(result.en) + " zh=" + JSON.stringify(result.zh)
          };
        }
        return { pass: true, detail: "identical in both languages — en sector fingerprint sample: " + (result.en.sectorSegments[0] || "n/a") };
      },
      // Reproduces the EXACT regression PD-0015 §2.3 warns about: a classifier keyed
      // off the current-language DISPLAY label rather than the canonical key. This
      // designer cannot edit shell.js, so — per the coordinator's explicit permission
      // to use a runtime override rather than fake teeth or claim it cannot be tested
      // — this temporarily MONKEY-PATCHES the live APP.ui.classifySectorExposure
      // function (a runtime object-property reassignment, not a file edit; the same
      // technique already used throughout this file for APP.data's own accessors) so
      // that under "zh" it returns keys that differ from "en"'s, exactly simulating a
      // classifier whose bucketing changed with the display language. Restored
      // immediately after the check via the returned restore() function.
      injectDefect: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.ui || typeof window.APP.ui.classifySectorExposure !== "function") {
          return function restore() {}; // nothing to patch; the check itself already reports FAILURE for a missing utility
        }
        var ui = window.APP.ui;
        var original = ui.classifySectorExposure;
        ui.classifySectorExposure = function (holdings, totalValue) {
          var result = original(holdings, totalValue);
          var lang = (window.APP.i18n && window.APP.i18n.getLang) ? window.APP.i18n.getLang() : "en";
          if (lang !== "zh") return result;
          // Simulate "keyed off the display label": perturb only the zh-side
          // canonical keys, so the en vs. zh fingerprints diverge exactly as the
          // real regression (grouping changing with language) would produce.
          return {
            sectorSegments: result.sectorSegments.map(function (s) { return { key: s.key + "__zh_display_label", value: s.value, pct: s.pct }; }),
            nonSectorSegments: result.nonSectorSegments,
            total: result.total
          };
        };
        return function restore() { ui.classifySectorExposure = original; };
      }
    },

    // =====================================================================
    // HG1 ROUND 5, PHASE 2 (designer, this pass) — S5/S4/S7 additions below. Same
    // discipline as every assertion above: each has a demonstrated negative test
    // (selfTest() reintroduces the named defect and confirms the check fails),
    // and each avoids REVISION 2's two historical bugs (field-concatenation
    // masking a defect; a tautological check that cannot fail).
    // =====================================================================

    // ---- AC-S5.4 (PD-0016 Part 1 §1.3) — the mechanical guarantee that three
    // explanation modes render one deterministic fact set, never three independent
    // conclusions. This file's own stated scope is "reads ONLY window.APP.data" — but
    // the invariant this checks is specifically about whether js/data.js's accessors
    // vary with js/shell.js's APP.state.explanationMode, so it necessarily reads that
    // one additional, public, app-level surface (the SAME class of exception the
    // sectorClassification.languageInvariant assertion immediately above already
    // makes into window.APP.ui/window.APP.i18n). Uses APP.state.setExplanationModeQuiet
    // (js/shell.js) rather than the public setExplanationMode, specifically so this
    // read-only verification never forces the whole app to re-render three times just
    // to run a comparison — the exact reason setLangQuiet exists, applied here to the
    // newer state. ----
    {
      id: "explanationMode.claimFactsInvariant",
      description: "For a representative sample of claim ids, value/sufficiency/freshness and the Proof Packet (Evidence) entry set must be byte-identical whether read while APP.state.explanationMode is 'quick', 'simple', or 'professional' (AC-S5.4, PD-0016 Part 1 §1.3, PD-0012 §2's 'same underlying deterministic fact set'). Degrades to a reported FAILURE — never a silent pass — if APP.state's quiet mode-setter is unavailable, and always restores the mode it found on entry, even on a thrown error.",
      check: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.state ||
            typeof window.APP.state.getExplanationMode !== "function" ||
            typeof window.APP.state.setExplanationModeQuiet !== "function") {
          return { pass: false, detail: "APP.state.getExplanationMode/setExplanationModeQuiet not available — cannot verify the mode-invariance guarantee. Reported as FAILED (not skipped)." };
        }
        var CLAIM_IDS = ["metric.beta", "metric.return.1y", "metric.benchmarkRelative", "metric.volatility"];
        var modeBefore = window.APP.state.getExplanationMode();
        var snapshots = {};
        try {
          ["quick", "simple", "professional"].forEach(function (mode) {
            window.APP.state.setExplanationModeQuiet(mode);
            snapshots[mode] = CLAIM_IDS.map(function (id) {
              var m = data.getMetric(id);
              var ev = data.getEvidence ? data.getEvidence(id) : null;
              return {
                id: id,
                value: m ? m.value : undefined,
                sufficiency: m ? m.sufficiency : undefined,
                freshness: m && m.freshness ? JSON.stringify(m.freshness) : null,
                evidenceJSON: ev ? JSON.stringify(ev) : null
              };
            });
          });
        } finally {
          window.APP.state.setExplanationModeQuiet(modeBefore);
        }
        var problems = [];
        CLAIM_IDS.forEach(function (id, i) {
          var q = snapshots.quick[i], s = snapshots.simple[i], p = snapshots.professional[i];
          if (q.value !== s.value || q.value !== p.value) problems.push(id + ": value differs across modes (quick=" + q.value + " simple=" + s.value + " professional=" + p.value + ")");
          if (q.sufficiency !== s.sufficiency || q.sufficiency !== p.sufficiency) problems.push(id + ": sufficiency differs across modes");
          if (q.freshness !== s.freshness || q.freshness !== p.freshness) problems.push(id + ": freshness differs across modes");
          if (q.evidenceJSON !== s.evidenceJSON || q.evidenceJSON !== p.evidenceJSON) problems.push(id + ": Proof Packet (Evidence) entry set differs across modes");
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "value/sufficiency/freshness/Evidence identical across quick/simple/professional for: " + CLAIM_IDS.join(", ") };
      },
      injectDefect: function (data) {
        // Simulates the exact regression this assertion exists to prevent: a claim
        // whose VALUE depends on the currently-selected explanation mode (three modes
        // producing three conclusions — the PD-0012 §2 failure this whole rebuild
        // exists to close). Wraps getMetric so ONLY calls made while mode is
        // "professional" return a mutated value for metric.beta; quick/simple are left
        // correct, so the defect is real and detectable, not a permanent state change.
        return withMutatedAccessor(data, "getMetric", function (result, args) {
          if (result && args && args[0] === "metric.beta" && typeof window !== "undefined" &&
              window.APP && window.APP.state && window.APP.state.getExplanationMode &&
              window.APP.state.getExplanationMode() === "professional") {
            return Object.assign({}, result, { value: result.value + 0.5 });
          }
          return result;
        });
      }
    },

    // ---- S4 (quant_analyst ruling, methodology/HG1_ROUND5_CAVEAT_AND_SML_DOMAIN_
    // RULING.md, Part A). Two obligations in one assertion: (1) every claim currently
    // sufficiency:"LIMITED" in this fixture must carry a non-empty qualifierShort whose
    // ESTIMATED RENDERED WIDTH (script-aware — the ruling's own correction: "the
    // 48-character cap is a rendered-width bound, not a character count") stays under
    // the ~288px bound (48 Latin glyphs at ~6.0px/glyph, charts.js's own labelCharPx
    // convention); (2) claim.caveat must remain substantially fuller than
    // qualifierShort — the mechanical guard against F4 (shortening caveat in place,
    // which would silently strip the Proof Packet's thresholds_limits_if_used /
    // limitations and break binding4). ----
    {
      id: "qualifierShort.presenceAndBoundedForLimited",
      description: "Every currently-LIMITED claim checked here (metric.beta, exposure.currency, the Ping An thinly-traded holding claim) must carry a non-empty qualifierShort whose estimated rendered width (script-aware: ~6.0px/Latin glyph, ~11.5px/CJK glyph) stays within a ~288px bound (the ruling's rendered-width restatement of the 48-Latin-character cap), and claim.caveat must remain substantially fuller than qualifierShort — guards F4 (caveat must never be shortened in place to double as the qualifier).",
      check: function (data) {
        function estWidth(s) {
          s = String(s || "");
          var w = 0;
          for (var i = 0; i < s.length; i++) { w += (s.codePointAt(i) > 0x2E80) ? 11.5 : 6.0; }
          return w;
        }
        var targets = [];
        var beta = data.getMetric("metric.beta");
        if (beta) targets.push(["metric.beta", beta]);
        var curExp = data.getExposure ? data.getExposure("currency") : null;
        if (curExp && curExp.claim) targets.push(["exposure.currency", curExp.claim]);
        var pingAn = data.getHoldingClaim ? data.getHoldingClaim("601318.SS") : null;
        if (pingAn) targets.push(["holding.601318.SS.unrealizedGL", pingAn]);
        if (!targets.length) return { pass: false, detail: "no LIMITED-claim targets resolved to check" };
        var problems = [];
        targets.forEach(function (pair) {
          var name = pair[0], c = pair[1];
          if (c.sufficiency !== "LIMITED") return; // only check claims that ARE limited today
          if (!c.qualifierShort) { problems.push(name + ": LIMITED claim has no qualifierShort"); return; }
          var w = estWidth(c.qualifierShort);
          if (w > 288) problems.push(name + ": qualifierShort estimated width " + w.toFixed(0) + "px exceeds the 288px bound: \"" + c.qualifierShort + "\"");
          if (!c.caveat || c.caveat.length <= c.qualifierShort.length * 2) {
            problems.push(name + ": caveat is not substantially fuller than qualifierShort (F4 risk — caveat may have been shortened in place) — caveat.length=" + (c.caveat || "").length + " qualifierShort.length=" + c.qualifierShort.length);
          }
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: targets.map(function (p) { return p[0]; }).join(", ") + " each carry a bounded qualifierShort and an unshortened caveat" };
      },
      injectDefect: function (data) {
        var beta = data.getMetric("metric.beta");
        // Reproduces F4 exactly: caveat collapsed to (a copy of) the short form,
        // instead of an added field beside an untouched caveat.
        return withMutatedFields(beta, { caveat: beta.qualifierShort });
      }
    },

    // ---- F6 (quant ruling) — "binding4... must be extended to assert the same
    // equality on qualifierShort." Implemented as its OWN assertion, deliberately NOT
    // by editing binding4's already-proven check/injectDefect above: binding4's
    // existing negative test (a wrong caveat) is historically load-bearing (proven
    // across four revisions) and this keeps that proof completely undisturbed, while
    // still independently proving detection of a wrong count specifically INSIDE
    // qualifierShort — which today's INTERIM string (Ruling 1(c)/F1) does not even
    // contain, so this guard is dormant on live data until either a future primary-
    // form qualifierShort or a regression introduces one; dormant is not the same as
    // untested, per this file's own injectDefect discipline. ----
    {
      id: "qualifierShort.beta.observationCountMatchesEvidenceWhenPresent",
      description: "If metric.beta.qualifierShort ever states a daily observation count (it does not today, since the interim disagreement-disclosure string is in force per Ruling 1(c)/F1), that count must match the Proof Packet's observations field, exactly like binding4 already requires of caveat/investorDetail — guards the newly-visible string from becoming an unguarded parallel truth (PD-0014 §2.5, F6).",
      check: function (data) {
        var m = data.getMetric("metric.beta");
        var ev = data.getEvidence ? data.getEvidence("metric.beta") : null;
        if (!m) return { pass: false, detail: "metric.beta not found" };
        if (!ev || typeof ev.observations !== "number") return { pass: false, detail: "no Evidence/Proof Packet observations field found for metric.beta" };
        var match = String(m.qualifierShort || "").match(/(\d+)\s*daily/i);
        if (!match) return { pass: true, detail: "qualifierShort states no daily observation count today (interim string, Ruling 1(c)/F1) — nothing to check" };
        var count = Number(match[1]);
        if (count !== ev.observations) return { pass: false, detail: "qualifierShort states " + count + " daily observations; Proof Packet states " + ev.observations };
        return { pass: true, detail: "qualifierShort count " + count + " matches evidence " + ev.observations };
      },
      injectDefect: function (data) {
        var m = data.getMetric("metric.beta");
        return withMutatedFields(m, { qualifierShort: "limited · 99 daily obs · 3Y standard not met" });
      }
    },

    // ---- S7 (PD-0015 §2.3) — the account-type analogue of
    // sectorClassification.languageInvariant above. `taxable`/`retirement`/`cash`
    // (js/data.js's ACCOUNTS[].type) is now translated for DISPLAY via
    // APP.ui.translateAccountType while APP.ui.classifyAccountsByType (both js/shell.js,
    // this pass) groups by the untouched canonical field — this is the runtime proof
    // that the grouping cannot vary with the current language, the identical shape of
    // proof sectorClassification.languageInvariant already gives sector/asset-class
    // grouping. ----
    {
      id: "accountType.languageInvariant",
      description: "APP.ui.classifyAccountsByType()'s groupings (canonical key/count) must be identical in English and Chinese — a grouping key must never be a localized display label (PD-0015 §2.3). Calls APP.ui.verifyAccountTypeLanguageInvariant(accounts) (js/shell.js) and compares canonical fingerprints, never the display label (expected to differ). Degrades to a reported FAILURE — never a silent pass — if APP.ui or the utility is unavailable.",
      check: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.ui || typeof window.APP.ui.verifyAccountTypeLanguageInvariant !== "function") {
          return { pass: false, detail: "APP.ui.verifyAccountTypeLanguageInvariant is not available — cannot verify the account-type language invariant. Reported as FAILED (not skipped)." };
        }
        var accounts = data.getAccounts ? data.getAccounts() : null;
        if (!accounts || !accounts.length) return { pass: false, detail: "no accounts returned from getAccounts() — cannot verify" };
        var result;
        try {
          result = window.APP.ui.verifyAccountTypeLanguageInvariant(accounts);
        } catch (e) {
          return { pass: false, detail: "verifyAccountTypeLanguageInvariant threw: " + (e && e.message ? e.message : String(e)) };
        }
        if (!result) return { pass: false, detail: "verifyAccountTypeLanguageInvariant returned no result" };
        if (!result.identical) {
          return { pass: false, detail: "account-type classification diverges between languages — en=" + JSON.stringify(result.en) + " zh=" + JSON.stringify(result.zh) };
        }
        return { pass: true, detail: "identical in both languages — fingerprint: " + JSON.stringify(result.en) };
      },
      // Reproduces the EXACT regression PD-0015 §2.3 warns against: a classifier keyed
      // off the current-language DISPLAY label rather than the canonical `type` field.
      // Monkey-patches the live APP.ui.classifyAccountsByType function (a runtime
      // property reassignment, not a file edit — the same technique already used
      // throughout this file), restored immediately after the check.
      injectDefect: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.ui || typeof window.APP.ui.classifyAccountsByType !== "function") {
          return function restore() {};
        }
        var ui = window.APP.ui;
        var original = ui.classifyAccountsByType;
        ui.classifyAccountsByType = function (accounts) {
          var result = original(accounts);
          var lang = (window.APP.i18n && window.APP.i18n.getLang) ? window.APP.i18n.getLang() : "en";
          if (lang !== "zh") return result;
          return result.map(function (s) { return { key: s.key + "__zh_display_label", count: s.count }; });
        };
        return function restore() { ui.classifyAccountsByType = original; };
      }
    },

    // =====================================================================
    // HG1 M1 fix — RENDERED-FACT RECONCILIATION (RULING 5(a), BINDING). No rendered
    // financial quantity may be produced by arithmetic the deterministic engine does not
    // also perform, on the same inputs, over the same window. RC-1 (below) is the DATA-
    // layer half: it reconciles the array js/charts.js is handed against the engine's
    // own formula. RC-2 (further below) is the RENDER-layer half: it reads the quantity
    // back from an actually-rendered chart node, never from window.APP.data alone — the
    // exact gap this file's header (§7.1, M1-F5) names as the reason 33/33 stayed green
    // while M1 stood: "no rendered quantity was ever an input to any control."
    // =====================================================================

    // ---- RC-1.1 (RULING 5(b)) — render-INPUT reconciliation, portfolio leg. ----
    {
      id: "periodWindow.rc1_1.portfolioSeriesReconcilesWithEngine",
      description: "RC-1.1 — for every range selector (1M/3M/6M/1Y/ALL), the portfolio series data.getPortfolioSeries({range}) hands to the chart must reconcile with the engine's own period-return arithmetic (data._internal.enginePeriodReturn(range,'portfolio')) within 1e-9 — the M1 arithmetic itself: a series of N level points must contain the SAME N-1 inter-point return the engine publishes for that window, not one fewer.",
      check: function (data) {
        if (!data._internal || typeof data._internal.enginePeriodReturn !== "function") {
          return { pass: false, detail: "data._internal.enginePeriodReturn is not exposed — cannot reconcile." };
        }
        var problems = [];
        M1_RANGES.forEach(function (range) {
          var s = data.getPortfolioSeries({ range: range });
          if (!s.portfolio || s.portfolio.length < 2) { problems.push(range + ": fewer than 2 points returned"); return; }
          var actual = s.portfolio[s.portfolio.length - 1] / s.portfolio[0] - 1;
          var expected = data._internal.enginePeriodReturn(range, "portfolio");
          var diff = Math.abs(actual - expected);
          if (diff > 1e-9) problems.push(range + ": chart=" + actual + " engine=" + expected + " |diff|=" + diff);
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "portfolio series reconciles with the engine at every range (1e-9): " + M1_RANGES.join(", ") };
      },
      // M6.3 (RULING 6) — "Non-vacuity, portfolio leg": patch ONLY the portfolio
      // series' base by dropping its own leading element, leaving benchmark/dates
      // untouched. Must fail RC-1.1 ALONE (RC-1.2's own, separate self-test below still
      // passes under ITS OWN check) — guards against a combined check silently passing
      // on an untouched leg, the exact failure shape this file's revision-2 history
      // records against itself (see file header).
      injectDefect: function (data) {
        return withMutatedAccessor(data, "getPortfolioSeries", function (result) {
          return { dates: result.dates, portfolio: result.portfolio.slice(1), benchmark: result.benchmark, window: result.window };
        });
      }
    },

    // ---- RC-1.2 (RULING 5(b)) — render-INPUT reconciliation, benchmark leg. ----
    {
      id: "periodWindow.rc1_2.benchmarkSeriesReconcilesWithEngine",
      description: "RC-1.2 — mirror of RC-1.1 for the benchmark leg (the methodology ruling's §1.4 point: the ~1.43 pp benchmark-side error nobody separately measured, masked by near-cancellation in the relative figure). The benchmark series must reconcile with data._internal.enginePeriodReturn(range,'benchmark') within 1e-9, at every range.",
      check: function (data) {
        if (!data._internal || typeof data._internal.enginePeriodReturn !== "function") {
          return { pass: false, detail: "data._internal.enginePeriodReturn is not exposed — cannot reconcile." };
        }
        var problems = [];
        M1_RANGES.forEach(function (range) {
          var s = data.getPortfolioSeries({ range: range });
          if (!s.benchmark || s.benchmark.length < 2) { problems.push(range + ": fewer than 2 points returned"); return; }
          var actual = s.benchmark[s.benchmark.length - 1] / s.benchmark[0] - 1;
          var expected = data._internal.enginePeriodReturn(range, "benchmark");
          var diff = Math.abs(actual - expected);
          if (diff > 1e-9) problems.push(range + ": chart=" + actual + " engine=" + expected + " |diff|=" + diff);
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "benchmark series reconciles with the engine at every range (1e-9): " + M1_RANGES.join(", ") };
      },
      // M6.4 (RULING 6) — mirror of M6.3, benchmark leg only.
      injectDefect: function (data) {
        return withMutatedAccessor(data, "getPortfolioSeries", function (result) {
          return { dates: result.dates, portfolio: result.portfolio, benchmark: result.benchmark.slice(1), window: result.window };
        });
      }
    },

    // ---- RC-1.3 (RULING 5(b)) — the −0.14 pp leg. ----
    {
      id: "periodWindow.rc1_3.relativeReconcilesWithBenchmarkRelativeAtOneYear",
      description: "RC-1.3 — at 1Y, (portfolio return minus benchmark return) computed from the SAME base-anchored series must equal metric.benchmarkRelative.value within 1e-9. The methodology ruling names this the MORE dangerous of the two gaps (§1.4): it is a near-cancellation of two ~1.3 pp errors, not a small defect, and a reviewer who ranks by observed magnitude would miss it.",
      check: function (data) {
        var s = data.getPortfolioSeries({ range: "1Y" });
        var m = data.getMetric("metric.benchmarkRelative");
        if (!m || typeof m.value !== "number") return { pass: false, detail: "metric.benchmarkRelative not found or non-numeric" };
        if (!s.portfolio || s.portfolio.length < 2 || !s.benchmark || s.benchmark.length < 2) return { pass: false, detail: "1Y series too short to compute a return" };
        var retP = s.portfolio[s.portfolio.length - 1] / s.portfolio[0] - 1;
        var retB = s.benchmark[s.benchmark.length - 1] / s.benchmark[0] - 1;
        var diff = Math.abs((retP - retB) - m.value);
        if (diff > 1e-9) return { pass: false, detail: "chart relative=" + (retP - retB) + " metric.benchmarkRelative=" + m.value + " |diff|=" + diff };
        return { pass: true, detail: "chart relative " + (retP - retB) + " matches metric.benchmarkRelative " + m.value + " within 1e-9" };
      },
      // M6.4 (RULING 6) — "must ALSO trip RC-1.3, since a one-sided base shift moves the
      // relative figure." Same benchmark-only-leg mutation as RC-1.2's, its own copy so
      // this assertion's self-test proof is independent of RC-1.2's.
      injectDefect: function (data) {
        return withMutatedAccessor(data, "getPortfolioSeries", function (result) {
          return { dates: result.dates, portfolio: result.portfolio, benchmark: result.benchmark.slice(1), window: result.window };
        });
      }
    },

    // ---- RC-1.4 (RULING 5(b)) — anchor added to all three arrays, or to none. ----
    {
      id: "periodWindow.rc1_4.arrayLengthsMatch",
      description: "RC-1.4 — dates.length === portfolio.length === benchmark.length at every range: the anchor point (RULING 1(b)) must be added to all three arrays together, or to none of them — a chart cannot draw a portfolio line one point longer than its own x-axis.",
      check: function (data) {
        var problems = [];
        M1_RANGES.forEach(function (range) {
          var s = data.getPortfolioSeries({ range: range });
          var lens = [s.dates.length, s.portfolio.length, s.benchmark.length];
          if (lens[0] !== lens[1] || lens[1] !== lens[2]) problems.push(range + ": dates=" + lens[0] + " portfolio=" + lens[1] + " benchmark=" + lens[2]);
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "dates/portfolio/benchmark array lengths agree at every range: " + M1_RANGES.join(", ") };
      },
      // Not one of RULING 6's named mutations (that table enumerates the ARITHMETIC
      // defects, not this structural one) — authored here because RC-1.4 is itself
      // REQUIRED by RULING 5(b), and this file's own rule (see selfTest()) is that an
      // assertion with no demonstrated negative test is not a verified control. Drops
      // one element from ONLY the benchmark array, leaving dates/portfolio untouched.
      injectDefect: function (data) {
        return withMutatedAccessor(data, "getPortfolioSeries", function (result) {
          return { dates: result.dates, portfolio: result.portfolio, benchmark: result.benchmark.slice(1), window: result.window };
        });
      }
    },

    // ---- RC-1.5 (RULING 5(b)) — the declared rule must be true, not coincidental. ----
    {
      id: "periodWindow.rc1_5.windowDeclarationIsStructurallyValid",
      description: "RC-1.5 — the declared window must actually describe the returned arrays (baseDate === dates[0]; windowStart === dates[1], at every range), and the declared baseRule must match WHY that base was chosen, not merely restate a coincidence: 'PRIOR_CLOSE' requires a genuine prior close (baseIndex > 0); 'FIRST_AVAILABLE_CLOSE' requires there to be none (baseIndex === 0). Forces the rule to be DECLARED and TRUE (RULING 3), not an undeclared clamp (was M1-F4).",
      check: function (data) {
        var problems = [];
        M1_RANGES.forEach(function (range) {
          var s = data.getPortfolioSeries({ range: range });
          var w = s.window;
          if (!w) { problems.push(range + ": no window metadata returned"); return; }
          if (w.baseDate !== s.dates[0]) problems.push(range + ": baseDate (" + w.baseDate + ") !== dates[0] (" + s.dates[0] + ")");
          if (s.dates.length > 1 && w.windowStart !== s.dates[1]) problems.push(range + ": windowStart (" + w.windowStart + ") !== dates[1] (" + s.dates[1] + ")");
          if (w.baseRule === "PRIOR_CLOSE") {
            if (!(w.baseIndex > 0)) problems.push(range + ": declares PRIOR_CLOSE but baseIndex=" + w.baseIndex + " — no genuine prior close exists");
          } else if (w.baseRule === "FIRST_AVAILABLE_CLOSE") {
            if (w.baseIndex !== 0) problems.push(range + ": declares FIRST_AVAILABLE_CLOSE but baseIndex=" + w.baseIndex + " (expected 0)");
          } else {
            problems.push(range + ": baseRule '" + w.baseRule + "' is not a recognized declared convention");
          }
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "window declaration is structurally valid and matches the returned arrays at every range: " + M1_RANGES.join(", ") };
      },
      // M6.7 (RULING 6) — "ALL is not exempt": patch baseRule for ALL to PRIOR_CLOSE
      // while leaving baseIndex=0. ALL currently reconciles by coincidence (ruling
      // §5.1); this proves the check distinguishes DECLARED from ACCIDENTAL agreement —
      // a bare "does the ratio come out right" check would miss this entirely.
      injectDefect: function (data) {
        return withMutatedAccessor(data, "getPortfolioSeries", function (result, args) {
          var opts = (args && args[0]) || {};
          if ((opts.range || "1Y") !== "ALL") return result;
          var w = Object.assign({}, result.window, { baseRule: "PRIOR_CLOSE" });
          return { dates: result.dates, portfolio: result.portfolio, benchmark: result.benchmark, window: w };
        });
      }
    },

    // ---- RC-1.6 (RULING 5(b)) — "N levels ⇒ N-1 returns," made mechanical. ----
    {
      id: "periodWindow.rc1_6.observationCountMatchesArrayLength",
      description: "RC-1.6 — window.observationCount === dates.length - 1 at every range: a series of N level points contains only N-1 inter-point returns (methodology ruling §2.1) — the window's own DECLARATION must state that arithmetic fact.",
      check: function (data) {
        var problems = [];
        M1_RANGES.forEach(function (range) {
          var s = data.getPortfolioSeries({ range: range });
          var w = s.window;
          if (!w) { problems.push(range + ": no window metadata returned"); return; }
          if (w.observationCount !== s.dates.length - 1) problems.push(range + ": observationCount=" + w.observationCount + " but dates.length-1=" + (s.dates.length - 1));
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "observationCount === dates.length - 1 at every range: " + M1_RANGES.join(", ") };
      },
      // M6.6 (RULING 6) — "Declaration drift": patch window.observationCount to
      // dates.length (N instead of N-1), changing no rendered number. Proves the
      // DECLARATION is under control independently of the value — what PD-0014 claim
      // traceability actually protects.
      injectDefect: function (data) {
        return withMutatedAccessor(data, "getPortfolioSeries", function (result) {
          var w = Object.assign({}, result.window, { observationCount: result.dates.length });
          return { dates: result.dates, portfolio: result.portfolio, benchmark: result.benchmark, window: w };
        });
      }
    },

    // ---- RC-1.7 (RULING 5(b)) — binds the chart's array to the Proof Packet. ----
    {
      id: "periodWindow.rc1_7.oneYearBindsToProofPacketWindow",
      description: "RC-1.7 — at 1Y, the array handed to the chart binds to the SAME window the Proof Packet declares (data._internal.windowStart/windowEnd/windowObservationCount): window.observationCount === _internal.windowObservationCount (252), window.windowStart === _internal.windowStart, window.windowEnd === _internal.windowEnd. Catches M1 from the OTHER direction — the Proof Packet says 252 observations over a named span, so the array must contain exactly 253 points whose 2nd through 253rd dates are those.",
      check: function (data) {
        var s = data.getPortfolioSeries({ range: "1Y" });
        var w = s.window;
        var iv = data._internal;
        if (!w || !iv) return { pass: false, detail: "window metadata or _internal not available" };
        var problems = [];
        if (w.observationCount !== iv.windowObservationCount) problems.push("observationCount=" + w.observationCount + " !== _internal.windowObservationCount=" + iv.windowObservationCount);
        if (w.windowStart !== iv.windowStart) problems.push("windowStart=" + w.windowStart + " !== _internal.windowStart=" + iv.windowStart);
        if (w.windowEnd !== iv.windowEnd) problems.push("windowEnd=" + w.windowEnd + " !== _internal.windowEnd=" + iv.windowEnd);
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "1Y array's window binds exactly to the Proof Packet's declared window (" + iv.windowObservationCount + " obs, " + iv.windowStart + " to " + iv.windowEnd + ")" };
      },
      // M6.6 (RULING 6) — same "declaration drift" mutation as RC-1.6, applied at 1Y:
      // RULING 6's table lists M6.6 against BOTH RC-1.6 and RC-1.7, and this proves this
      // assertion independently detects it too (not merely inheriting RC-1.6's proof).
      injectDefect: function (data) {
        return withMutatedAccessor(data, "getPortfolioSeries", function (result, args) {
          var opts = (args && args[0]) || {};
          if ((opts.range || "1Y") !== "1Y") return result;
          var w = Object.assign({}, result.window, { observationCount: result.dates.length });
          return { dates: result.dates, portfolio: result.portfolio, benchmark: result.benchmark, window: w };
        });
      }
    },

    // ---- RULING 6(a) — tolerance-calibration guard: M6.1 must fail at EVERY
    // non-ALL range, not merely 1Y (the only range with an independent engine fact to
    // catch it against before this fix). Kept as its own assertion, separate from
    // RC-1.1's own M6.3 proof, specifically to demonstrate the multi-range requirement
    // RULING 6(a) states by name. ----
    {
      id: "periodWindow.m1HistoricalDefectFailsAtEveryNonAllRange",
      description: "RULING 6(a) — the M1 defect itself (restoring js/data.js's pre-fix .slice(i): the array loses its leading anchor point while the window's OWN declaration does not follow it) must FAIL at every one of 1M, 3M, 6M and 1Y — not merely at 1Y, where an engine fact happened to already exist to catch it against. 3M's own disagreement is only ~0.03 pp; a reconciliation tolerance looser than that would let this defect pass at 3M while failing at 1Y, a partially-blind control. τ=1e-9 (RULING 4) forecloses that. ALL is deliberately excluded here: it has no prior close to drop, so this specific mutation is a no-op there by construction (ALL agrees 'for the wrong reason,' per ruling §1.3/§5.1 — a different, already-covered concern, RC-1.5/M6.7).",
      check: function (data) {
        if (!data._internal || typeof data._internal.enginePeriodReturn !== "function") {
          return { pass: false, detail: "data._internal.enginePeriodReturn is not exposed — cannot reconcile." };
        }
        var problems = [];
        ["1M", "3M", "6M", "1Y"].forEach(function (range) {
          var s = data.getPortfolioSeries({ range: range });
          var actual = s.portfolio[s.portfolio.length - 1] / s.portfolio[0] - 1;
          var expected = data._internal.enginePeriodReturn(range, "portfolio");
          var diff = Math.abs(actual - expected);
          if (diff > 1e-9) problems.push(range + ": chart=" + actual + " engine=" + expected + " |diff|=" + diff);
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "reconciles at 1M, 3M, 6M and 1Y" };
      },
      // M6.1 (RULING 6) — "The M1 defect itself": restores the pre-fix slice by dropping
      // each series' leading element WHILE LEAVING `window` untouched — the actual
      // historical shape of the bug (the array shrinks; the Proof Packet's declared
      // window does not follow it). A no-op at ALL (baseRule FIRST_AVAILABLE_CLOSE has
      // no anchor to drop), which is why this check only runs 1M/3M/6M/1Y.
      injectDefect: function (data) {
        return withMutatedAccessor(data, "getPortfolioSeries", function (result) {
          if (!result.window || result.window.baseRule !== "PRIOR_CLOSE") return result;
          return { dates: result.dates.slice(1), portfolio: result.portfolio.slice(1), benchmark: result.benchmark.slice(1), window: result.window };
        });
      }
    },

    // =====================================================================
    // HG1 M1 fix — RC-2 (RULING 5(c), BINDING IN FORM). Render-LAYER reconciliation:
    // reads the quantity back from the rendered chart's OWN DOM node, never from
    // window.APP.data alone and never by re-executing js/charts.js's own formula. This
    // is the control this file's own header (§7.1, M1-F5) names as structurally
    // impossible before this fix: this file's sole prior `document` reference was
    // `document.readyState`, at boot, for timing only — no rendered quantity was ever an
    // input to any control here.
    // =====================================================================
    {
      id: "chart.renderedReturnReconcilesWithEngine",
      description: "RC-2 — builds the 1Y hero chart via APP.charts.lineCompare into a DETACHED node (its return value, never appended to the visible document — viable because measureTextWidth falls back to a heuristic with no measurement node available, and textContent is set regardless of measurement), reads back the textContent of .chart-end-label-portfolio / .chart-end-label-benchmark / .chart-relative-callout, and asserts CHARACTER EQUALITY (RULING 4(iii) — a strictly stronger check than numeric equality, and one that additionally catches a side that rounds a pre-rounded input) against the engine side formatted with the SAME pctText() function charts.js itself uses (APP.charts.pctText, exposed for exactly this reconciliation). Proves the rendered chart — not merely the array behind it — actually shows the engine's own numbers.",
      check: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.charts || typeof window.APP.charts.lineCompare !== "function") {
          return { pass: false, detail: "APP.charts.lineCompare is not available — cannot verify the rendered chart." };
        }
        var pctText = window.APP.charts.pctText;
        if (typeof pctText !== "function") {
          return { pass: false, detail: "APP.charts.pctText is not exposed — cannot format the engine side with the SAME function the chart uses (RULING 4(iii))." };
        }
        var s = data.getPortfolioSeries({ range: "1Y" });
        var root;
        try {
          root = window.APP.charts.lineCompare({ dates: s.dates, series: { portfolio: s.portfolio, benchmark: s.benchmark } });
        } catch (e) {
          return { pass: false, detail: "APP.charts.lineCompare threw: " + (e && e.message ? e.message : String(e)) };
        }
        if (!root || typeof root.querySelector !== "function") return { pass: false, detail: "lineCompare did not return a queryable node" };
        var elPortfolio = root.querySelector(".chart-end-label-portfolio");
        var elBenchmark = root.querySelector(".chart-end-label-benchmark");
        var elCallout = root.querySelector(".chart-relative-callout");
        if (!elPortfolio || !elBenchmark || !elCallout) {
          return { pass: false, detail: "rendered chart is missing .chart-end-label-portfolio / .chart-end-label-benchmark / .chart-relative-callout — cannot read back a rendered quantity" };
        }
        function extractPctToken(text) {
          var m = String(text || "").match(/[+\-]?\d+\.\d+%/);
          return m ? m[0] : null;
        }
        var renderedPortfolio = extractPctToken(elPortfolio.textContent);
        var renderedBenchmark = extractPctToken(elBenchmark.textContent);
        var renderedRelative = extractPctToken(elCallout.textContent);

        var engineReturn1y = data.getMetric("metric.return.1y");
        var engineBenchRel = data.getMetric("metric.benchmarkRelative");
        if (!engineReturn1y || typeof engineReturn1y.value !== "number") return { pass: false, detail: "metric.return.1y missing/non-numeric" };
        if (!engineBenchRel || typeof engineBenchRel.value !== "number") return { pass: false, detail: "metric.benchmarkRelative missing/non-numeric" };
        if (!data._internal || typeof data._internal.enginePeriodReturn !== "function") return { pass: false, detail: "data._internal.enginePeriodReturn not exposed" };
        var engineBenchmarkPeriodReturn = data._internal.enginePeriodReturn("1Y", "benchmark");

        var expectedPortfolio = pctText(engineReturn1y.value, 1);
        var expectedBenchmark = pctText(engineBenchmarkPeriodReturn, 1);
        var expectedRelative = pctText(engineBenchRel.value, 1);

        var problems = [];
        if (renderedPortfolio !== expectedPortfolio) problems.push("portfolio end label: rendered='" + renderedPortfolio + "' expected='" + expectedPortfolio + "'");
        if (renderedBenchmark !== expectedBenchmark) problems.push("benchmark end label: rendered='" + renderedBenchmark + "' expected='" + expectedBenchmark + "'");
        if (renderedRelative !== expectedRelative) problems.push("relative callout: rendered='" + renderedRelative + "' expected='" + expectedRelative + "'");
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "rendered portfolio=" + renderedPortfolio + " benchmark=" + renderedBenchmark + " relative=" + renderedRelative + " — all character-equal to the engine side" };
      },
      // M6.5 (RULING 6) — "Readback is real": wraps APP.charts.lineCompare so that,
      // AFTER the SVG is built, .chart-end-label-portfolio's textContent is rewritten
      // 0.5pp off, leaving every array and every engine fact untouched. RC-1 (above)
      // must still pass (nothing data-layer changed) and RC-2 must fail — proof this
      // assertion reads the DOM, not the array; "the single most important negative
      // test here, because a 'render check' that quietly recomputes a[last]/a[0]-1 is
      // testing its own formula and is worthless" (the ruling's own words).
      injectDefect: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.charts || typeof window.APP.charts.lineCompare !== "function") {
          return function restore() {};
        }
        var charts = window.APP.charts;
        var original = charts.lineCompare;
        charts.lineCompare = function () {
          var root = original.apply(charts, arguments);
          var el = root && root.querySelector && root.querySelector(".chart-end-label-portfolio");
          if (el) {
            var m = String(el.textContent || "").match(/([+\-]?)(\d+\.\d+)%/);
            if (m) {
              var shifted = (parseFloat(m[2]) + 0.5).toFixed(1);
              el.textContent = el.textContent.replace(m[0], m[1] + shifted + "%");
            }
          }
          return root;
        };
        return function restore() { charts.lineCompare = original; };
      }
    },

    // =====================================================================
    // HG1 ux_planning revision (review-06, B3 — the missing Chinese Beta disclosure).
    // The English metric.beta.professionalDetail states the directional-claim
    // threshold itself (1.96 se / 95% confidence) — WHY the direction claim above it
    // is allowed to be asserted at all; the zh counterpart dropped that entire
    // sentence (P3: plainer wording may drop precision, never a caveat that changes
    // the conclusion; P9: auditability). This assertion is the machine-checkable
    // parity guard the fix's own report promised: it does not merely check "some
    // string exists" in each locale — it derives the expected multiplier from
    // data._internal.directionalClaimSeMultiplier (the SAME constant
    // betaDirectionConclusion and the correlation classification-band guard both
    // multiply by; see js/data.js) and confirms BOTH locales' professionalDetail
    // state that exact value, plus the 95% confidence level, rather than trusting a
    // hardcoded "1.96"/"95" literal here that could silently drift from the real
    // constant.
    // =====================================================================
    {
      id: "beta.professionalDetailDirectionalThresholdParity",
      description: "metric.beta's professionalDetail must state the directional-claim threshold (the multiplier exposed at data._internal.directionalClaimSeMultiplier, e.g. 1.96 se) AND the 95% confidence level, in BOTH English and claim.i18n.zh — not just that some disclosure sentence exists in each. Catches review-06's B3 regression: the zh professionalDetail dropped this sentence entirely while the English field kept it, silently losing the ONE place a reader is told why the beta direction claim above it was allowed to be asserted (P3, P9). Reads the expected multiplier from the SAME source value the English string interpolates, so a future change to the constant cannot silently desync this check from what the claim actually asserts.",
      check: function (data) {
        var m = data.getMetric("metric.beta");
        if (!m) return { pass: false, detail: "metric.beta not found" };
        var mult = data._internal && data._internal.directionalClaimSeMultiplier;
        if (typeof mult !== "number") {
          return { pass: false, detail: "data._internal.directionalClaimSeMultiplier is not exposed — cannot verify either locale against the same source value the claim's own threshold sentence is supposed to interpolate." };
        }
        var multToken = mult.toFixed(2);
        var en = m.professionalDetail || "";
        var zh = (m.i18n && m.i18n.zh && m.i18n.zh.professionalDetail) || "";
        var problems = [];
        if (en.indexOf(multToken) < 0) problems.push("en professionalDetail does not state the directional-claim threshold multiplier (" + multToken + ")");
        if (en.indexOf("95") < 0) problems.push("en professionalDetail does not state the 95% confidence level");
        if (!zh) {
          problems.push("claim.i18n.zh.professionalDetail is missing entirely");
        } else {
          if (zh.indexOf(multToken) < 0) problems.push("zh professionalDetail does not state the directional-claim threshold multiplier (" + multToken + ")");
          if (zh.indexOf("95") < 0) problems.push("zh professionalDetail does not state the 95% confidence level");
        }
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "en and zh professionalDetail both state the directional-claim threshold (" + multToken + " se) and the 95% confidence level, matching data._internal.directionalClaimSeMultiplier." };
      },
      // Reintroduces review-06's B3 exactly: the zh professionalDetail loses its
      // threshold/confidence sentence while the English field (and the multiplier
      // constant itself) are untouched — proving this assertion actually reads the
      // zh field independently rather than being satisfied by the English side alone.
      injectDefect: function (data) {
        var m = data.getMetric("metric.beta");
        if (!m || !m.i18n || !m.i18n.zh) return function restore() {};
        return withMutatedFields(m.i18n.zh, {
          professionalDetail: "OLS 回归,日频收益率,报告货币计价(含汇率影响,HG1 第四轮修正)。完整披露信息见方法论。"
        });
      }
    },

    // =====================================================================
    // HG1 ux_planning revision (review-06, B2 — Chinese holding-name consistency).
    // Bends this file's own "reads ONLY window.APP.data" scope note (already bent
    // twice above — stage5.urlLocale reads APP.i18n, chart.renderedReturnReconciles-
    // WithEngine reads APP.charts) to also read APP.ui.holdingDisplayName, the shared
    // lookup js/shell.js now exposes precisely so Overview/Portfolio/Scenario Lab
    // never each pick their own Chinese name for the same holding again.
    // =====================================================================
    {
      id: "holdingDisplayName.zh.consistentAcrossSurfaces",
      description: "APP.ui.holdingDisplayName(holding), in zh, must return the EXACT Chinese name Scenario Lab's own static zh prose already established for that holding (js/data.js's scenario.reduceCnExposure i18n.zh.description names Tencent/China Mobile/Alibaba/Meituan explicitly) — not a separately-chosen or untranslated name. Catches review-06's B2 regression: Overview's major-holdings block and Portfolio's ledger rendered the raw (always-English) h.name while Scenario Lab's prose named the same holdings in Chinese, so one holding carried two different names depending which surface you were on. EXTENDED (review-07, P0 item 1) — the original form of this assertion checked ONLY APP.ui.holdingDisplayName()'s own return value, so it stayed green while js/surfaces/analytics.js's concentration bar called ctx.charts.bar with the raw p.name directly, never calling the helper at all: a correct helper with a bypassing call site is exactly the shape this assertion could not previously catch. Now ALSO renders the real 'analytics' and 'overview' surfaces off-screen (via APP.uicheck.renderSurfaceOffscreen, the same technique chart.renderedReturnReconcilesWithEngine uses for a chart) and reads back the ACTUAL rendered .chart-bar-label text their concentration/top-position bars produce — asserting on what the rendering path produces, not re-deriving from the helper a second time.",
      check: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.ui || typeof window.APP.ui.holdingDisplayName !== "function") {
          return { pass: false, detail: "APP.ui.holdingDisplayName is not available — cannot verify cross-surface Chinese holding-name consistency." };
        }
        if (!window.APP.i18n || typeof window.APP.i18n.setLangQuiet !== "function" || typeof window.APP.i18n.getLang !== "function") {
          return { pass: false, detail: "APP.i18n.setLangQuiet/getLang not available — cannot verify the zh display name without forcing a visible re-render." };
        }
        var ui = window.APP.ui, i18n = window.APP.i18n;
        var scenarios = data.getScenarios ? data.getScenarios() : null;
        var reduceCn = (scenarios || []).filter(function (s) { return s.id === "scenario.reduceCnExposure"; })[0];
        if (!reduceCn || !reduceCn.i18n || !reduceCn.i18n.zh || typeof reduceCn.i18n.zh.description !== "string") {
          return { pass: false, detail: "scenario.reduceCnExposure's zh description is not available — cannot cross-check against Scenario Lab's own established Chinese holding names." };
        }
        var scenarioDescriptionZh = reduceCn.i18n.zh.description;
        var holdings = data.getHoldings ? data.getHoldings() : [];
        // Exactly the four HK-listed, China-domiciled holdings Scenario Lab's own zh
        // prose already names — review-06's B2 finding's own worked example.
        var namedIds = ["0700.HK", "0941.HK", "9988.HK", "3690.HK"];
        var originalLang = i18n.getLang();
        var problems = [];
        // HARDCODED literals (review-07 fix) — NOT derived from a live call to
        // ui.holdingDisplayName(). Deriving "expected" from the same function the
        // render-comparison below also depends on would make that comparison circular:
        // under this assertion's own injectDefect (which monkey-patches
        // ui.holdingDisplayName itself), BOTH sides would read the identically-broken
        // value and the check would pass vacuously. These are the exact literal values
        // js/shell.js's HOLDING_DISPLAY_NAME_ZH map establishes for these two holdings
        // (checked directly against that file, not re-derived here).
        var EXPECTED_ZH_DISPLAY_NAME = { "0700.HK": "腾讯控股", "0941.HK": "中国移动" };
        try {
          i18n.setLangQuiet("zh");
          namedIds.forEach(function (id) {
            var h = holdings.filter(function (x) { return x.id === id; })[0];
            if (!h) { problems.push(id + ": holding not found"); return; }
            var displayName = ui.holdingDisplayName(h);
            if (!displayName || scenarioDescriptionZh.indexOf(displayName) < 0) {
              problems.push(id + ": ui.holdingDisplayName() returned '" + displayName + "', which does not appear in Scenario Lab's own zh description");
            }
          });

          // EXTENDED (review-07, P0 item 1) — real-render check. Top-5 concentration by
          // market value (checked directly against js/data.js's HOLDINGS/FX_RATES, not
          // assumed) includes 0700.HK (Tencent) and 0941.HK (China Mobile), so BOTH the
          // Analytics concentration bar (js/surfaces/analytics.js:816) and Overview's
          // Block C concentration bar (js/surfaces/overview.js, the "top5Concentration"
          // block, a DIFFERENT call site from Overview's already-fixed majorHoldings bar)
          // have real, non-trivial signal to check — this is not a check that could pass
          // vacuously because the relevant holdings never appear.
          if (typeof window.APP.uicheck === "object" && typeof window.APP.uicheck.renderSurfaceOffscreen === "function") {
            var rawEnglishById = { "0700.HK": "Tencent Holdings", "0941.HK": "China Mobile" };
            ["analytics", "overview"].forEach(function (surfaceKey) {
              var container = null;
              try {
                container = window.APP.uicheck.renderSurfaceOffscreen(surfaceKey, "professional");
                if (!container) { problems.push(surfaceKey + ": surface not registered — cannot render for the call-site check"); return; }
                var labelEls = container.querySelectorAll(".chart-bar-label");
                var renderedTexts = [];
                for (var i = 0; i < labelEls.length; i++) renderedTexts.push(labelEls[i].textContent);
                ["0700.HK", "0941.HK"].forEach(function (id) {
                  var expected = EXPECTED_ZH_DISPLAY_NAME[id];
                  if (renderedTexts.indexOf(expected) < 0) {
                    problems.push(surfaceKey + ": no rendered .chart-bar-label reads '" + expected + "' for " + id + " (rendered labels: " + renderedTexts.join(", ") + ") — a call site is bypassing ui.holdingDisplayName");
                  }
                  var rawEnglish = rawEnglishById[id];
                  if (rawEnglish && renderedTexts.indexOf(rawEnglish) >= 0) {
                    problems.push(surfaceKey + ": a rendered .chart-bar-label reads the raw English '" + rawEnglish + "' for " + id + " instead of the zh display name");
                  }
                });
              } finally {
                if (container && container.parentNode) container.parentNode.removeChild(container);
              }
            });
          } else {
            problems.push("APP.uicheck.renderSurfaceOffscreen is not available — cannot verify actual rendered call sites, only the helper in isolation (the exact blind spot this extension exists to close)");
          }
        } finally {
          i18n.setLangQuiet(originalLang);
        }
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "ui.holdingDisplayName() (zh) for Tencent/China Mobile/Alibaba/Meituan all match the exact Chinese names Scenario Lab's own zh description already established, AND the real rendered Analytics/Overview concentration bars actually show those zh names for Tencent/China Mobile, not the raw English." };
      },
      // Reproduces the EXACT pre-fix regression: holdingDisplayName ignoring the
      // current language and always returning the raw (English) holding.name, the
      // same shape of defect as accountType.languageInvariant's own injector above.
      // Monkey-patches the live function, restored immediately after the check.
      // EXTENDED (review-07) — because analytics.js/overview.js's concentration bars
      // now call this SAME function (ctx.ui.holdingDisplayName === APP.ui.
      // holdingDisplayName), this one injection also corrupts what the real-render
      // check above reads back — proving that check reads the ACTUAL rendered DOM
      // output (whatever produced it) rather than silently re-deriving its expectation
      // from the same (now-broken) helper call: with this defect injected, the
      // rendered .chart-bar-label text becomes the raw English, so the real-render
      // assertion above fails on ITS OWN evidence, independent of the isolated check.
      // This is the same visible symptom a future call site reverting to `p.name`
      // directly would produce, which is the regression this extension exists to catch.
      injectDefect: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.ui || typeof window.APP.ui.holdingDisplayName !== "function") {
          return function restore() {};
        }
        var ui = window.APP.ui;
        var original = ui.holdingDisplayName;
        ui.holdingDisplayName = function (holding) { return holding ? holding.name : ""; };
        return function restore() { ui.holdingDisplayName = original; };
      }
    },

    // =====================================================================
    // HG1 ux_planning revision (review-07, P0 item 3 — transaction chronology).
    // =====================================================================
    {
      id: "transactions.chronology.monotonicDespiteSourceInsertionPosition",
      description: "data.getTransactions() must return transactions strictly ascending by `date` (ties broken deterministically by `id`) REGARDLESS of the position an entry occupies in js/data.js's own TRANSACTIONS array — the ordering guarantee belongs to the accessor, not to an implicit 'the source array happens to be sorted' contract js/surfaces/portfolio.js's `.slice().reverse()` render previously depended on silently. Uses the REAL, currently-present out-of-order entry (tx-0030, dated 2025-12-01, appended in js/data.js after tx-0029 dated 2026-09-02 — checked directly against js/data.js, not invented) as its fixture: tx-0030's correct chronological position is strictly between tx-0019 (2025-11-04) and tx-0020 (2026-01-12), and this assertion checks it actually lands there in getTransactions()'s own output, not at the tail its source-array position would put it at. Also checks the full ascending order end-to-end, and the descending (rendered) order after `.slice().reverse()` — this bears on P9: the UI must not present stale activity as the most recent transaction.",
      check: function (data) {
        if (typeof data.getTransactions !== "function") {
          return { pass: false, detail: "data.getTransactions is not available — cannot verify transaction chronology." };
        }
        var txs = data.getTransactions();
        if (!txs || !txs.length) return { pass: false, detail: "getTransactions() returned no transactions." };
        var problems = [];
        for (var i = 1; i < txs.length; i++) {
          if (txs[i].date < txs[i - 1].date) {
            problems.push("ascending index " + i + ": '" + txs[i].id + "' (" + txs[i].date + ") sorts before '" + txs[i - 1].id + "' (" + txs[i - 1].date + ")");
          }
        }
        var idx30 = -1, idx19 = -1, idx20 = -1;
        txs.forEach(function (t, i) {
          if (t.id === "tx-0019") idx19 = i;
          if (t.id === "tx-0020") idx20 = i;
          if (t.id === "tx-0030") idx30 = i;
        });
        if (idx30 < 0 || idx19 < 0 || idx20 < 0) {
          problems.push("tx-0019/tx-0020/tx-0030 were not all found in getTransactions()'s output");
        } else if (!(idx19 < idx30 && idx30 < idx20)) {
          problems.push("tx-0030 (2025-12-01) is at index " + idx30 + ", not strictly between tx-0019 (index " + idx19 + ") and tx-0020 (index " + idx20 + ") — its source-array insertion position (appended after tx-0029) is leaking into the accessor's chronological order");
        }
        var reversed = txs.slice().reverse();
        for (var j = 1; j < reversed.length; j++) {
          if (reversed[j].date > reversed[j - 1].date) {
            problems.push("rendered (reversed) index " + j + ": '" + reversed[j].id + "' (" + reversed[j].date + ") sorts after '" + reversed[j - 1].id + "' (" + reversed[j - 1].date + ")");
          }
        }
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "getTransactions() is strictly ascending by date across " + txs.length + " transactions; tx-0030 sits correctly between tx-0019 and tx-0020 despite its out-of-order source-array position; the rendered (reversed) order is strictly descending." };
      },
      // Reproduces the EXACT pre-fix visible symptom — tx-0030 surfacing at the tail
      // (the most-recent-looking position once reversed for render) regardless of its
      // true date — by wrapping the live accessor to pull tx-0030 out of its correctly-
      // sorted position and re-append it at the end, exactly where TRANSACTIONS' own
      // out-of-order insertion (js/data.js:568) put it before this round's fix. Restored
      // immediately after the check.
      injectDefect: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.data || typeof window.APP.data.getTransactions !== "function") {
          return function restore() {};
        }
        var d = window.APP.data;
        var original = d.getTransactions;
        d.getTransactions = function (filter) {
          var sorted = original.call(d, filter);
          var idx = -1;
          for (var i = 0; i < sorted.length; i++) { if (sorted[i].id === "tx-0030") { idx = i; break; } }
          if (idx < 0) return sorted;
          var out = sorted.slice(0, idx).concat(sorted.slice(idx + 1));
          out.push(sorted[idx]);
          return out;
        };
        return function restore() { d.getTransactions = original; };
      }
    },

    // =====================================================================
    // HG1 ux_planning revision (review-07, P0 item 4 — Beta explanation constant leak).
    // =====================================================================
    {
      id: "beta.professionalDetail.noInternalConstantNameLeak",
      description: "metric.beta's English professionalDetail previously printed the internal constant NAME `DIRECTIONAL_CLAIM_SE_MULTIPLIER` verbatim (js/data.js) alongside a second, independently-hardcoded '1.96' literal — an implementation identifier leaking into user-facing prose, plus a value that could silently drift from the real constant. This assertion checks NEITHER locale's professionalDetail contains that identifier (or the bare word 'MULTIPLIER', a slightly looser net), while STILL requiring the substantive disclosure survive: the threshold VALUE (read from data._internal.directionalClaimSeMultiplier, the same source both locales must interpolate from — never a second hardcoded number) and the 95% confidence level. The fix removes the internal name; it must not have removed the threshold itself.",
      check: function (data) {
        var m = data.getMetric("metric.beta");
        if (!m) return { pass: false, detail: "metric.beta not found" };
        var mult = data._internal && data._internal.directionalClaimSeMultiplier;
        if (typeof mult !== "number") {
          return { pass: false, detail: "data._internal.directionalClaimSeMultiplier is not exposed — cannot verify the disclosed value against its source." };
        }
        var multToken = mult.toFixed(2);
        var en = m.professionalDetail || "";
        var zh = (m.i18n && m.i18n.zh && m.i18n.zh.professionalDetail) || "";
        var problems = [];
        if (en.indexOf("DIRECTIONAL_CLAIM_SE_MULTIPLIER") >= 0) problems.push("en professionalDetail leaks the internal constant name DIRECTIONAL_CLAIM_SE_MULTIPLIER");
        if (zh.indexOf("DIRECTIONAL_CLAIM_SE_MULTIPLIER") >= 0) problems.push("zh professionalDetail leaks the internal constant name DIRECTIONAL_CLAIM_SE_MULTIPLIER");
        if (/\bMULTIPLIER\b/.test(en)) problems.push("en professionalDetail contains the bare identifier fragment 'MULTIPLIER'");
        if (en.indexOf(multToken) < 0) problems.push("en professionalDetail is missing the threshold VALUE (" + multToken + ") — the disclosure itself, not just the internal name, must survive");
        if (en.indexOf("95") < 0) problems.push("en professionalDetail is missing the 95% confidence level");
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "en and zh professionalDetail state the threshold (" + multToken + " se) and 95% confidence without leaking the internal constant name." };
      },
      // Reproduces the EXACT pre-fix regression: the internal constant name printed
      // verbatim, appended to the (otherwise still-correct) English sentence. Mutates
      // the live claim field via the shared withMutatedFields helper, restored
      // immediately after the check.
      injectDefect: function (data) {
        var m = data.getMetric("metric.beta");
        if (!m) return function restore() {};
        return withMutatedFields(m, {
          professionalDetail: m.professionalDetail + " (DIRECTIONAL_CLAIM_SE_MULTIPLIER)"
        });
      }
    },

    // =====================================================================
    // HG1 ux_planning revision (review-07, P1 item 5 — transaction filter raw enums).
    // =====================================================================
    {
      id: "transactionType.presentation.englishHumanReadableLabel",
      description: "The English 'All types' transaction filter combobox previously listed the raw canonical enum values verbatim (DEPOSIT, BUY, DIVIDEND, FX, TRANSFER_IN, ...) because APP.ui.translateTransactionType fell straight through to the raw type whenever the language was not zh. Checks translateTransactionType(type), in en, returns the established human-readable label (js/shell.js's TRANSACTION_TYPE_LABEL_EN) for every canonical js/data.js TRANSACTIONS[].type value — the SAME finite domain TRANSACTION_TYPE_LABEL_ZH already covers — never the raw value itself (except FX, whose canonical value already reads as an ordinary English abbreviation and is not changed). The canonical `value` attribute a caller filters on is untouched by this fix and not this assertion's concern.",
      check: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.ui || typeof window.APP.ui.translateTransactionType !== "function") {
          return { pass: false, detail: "APP.ui.translateTransactionType is not available." };
        }
        if (!window.APP.i18n || typeof window.APP.i18n.setLangQuiet !== "function" || typeof window.APP.i18n.getLang !== "function") {
          return { pass: false, detail: "APP.i18n.setLangQuiet/getLang not available." };
        }
        var ui = window.APP.ui, i18n = window.APP.i18n;
        // Checked directly against js/data.js's TRANSACTIONS[].type domain and
        // js/surfaces/portfolio.js's own TX_TYPES, not assumed.
        var expectedEn = {
          BUY: "Buy", SELL: "Sell", DIVIDEND: "Dividend", DEPOSIT: "Deposit", WITHDRAWAL: "Withdrawal",
          FX: "FX", TRANSFER_IN: "Transfer In", TRANSFER_OUT: "Transfer Out"
        };
        var originalLang = i18n.getLang();
        var problems = [];
        try {
          i18n.setLangQuiet("en");
          Object.keys(expectedEn).forEach(function (type) {
            var label = ui.translateTransactionType(type);
            if (label !== expectedEn[type]) {
              problems.push(type + ": expected '" + expectedEn[type] + "', got '" + label + "'");
            }
          });
        } finally {
          i18n.setLangQuiet(originalLang);
        }
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "translateTransactionType() (en) returns the established human-readable label for all " + Object.keys(expectedEn).length + " canonical transaction types." };
      },
      // Reproduces the EXACT pre-fix regression: English falling straight through to the
      // raw canonical value (js/shell.js's old `if (lang !== "zh") return type;`).
      // Wraps the live function, restored immediately after the check.
      injectDefect: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.ui || typeof window.APP.ui.translateTransactionType !== "function") {
          return function restore() {};
        }
        var ui = window.APP.ui;
        var original = ui.translateTransactionType;
        ui.translateTransactionType = function (type) {
          if (window.APP.i18n.getLang() !== "zh") return type;
          return original(type);
        };
        return function restore() { ui.translateTransactionType = original; };
      }
    },

    // =====================================================================
    // POST-HG1 CHECKPOINT A — D2 (designer-33). Regression coverage for the
    // per-holding `professionalDetail`/`i18n.zh.professionalDetail` fields
    // added to js/data.js's HOLDING_CLAIMS (see that file's own block comment
    // above HOLDING_CLAIMS for the content boundary). Reads ONLY
    // window.APP.data (getHoldings/getHolding/getHoldingClaim), matching this
    // file's own discipline. =====================================================================
    {
      id: "holding.professionalDetail.presentAndDistinctFromEnglish",
      description: "Every holding claim (HOLDING_CLAIMS, js/data.js) must carry a non-empty professionalDetail AND a non-empty i18n.zh.professionalDetail that is not byte-identical to the English string — proving this pass actually populated a genuine Chinese translation for every holding, not a placeholder or an English fallback masquerading as one.",
      check: function (data) {
        var holdings = data.getHoldings ? data.getHoldings() : null;
        if (!holdings || !holdings.length) return { pass: false, detail: "no holdings returned from getHoldings()" };
        var problems = [];
        holdings.forEach(function (h) {
          var c = data.getHoldingClaim ? data.getHoldingClaim(h.id) : null;
          if (!c) { problems.push(h.id + ": no holding claim found via getHoldingClaim()"); return; }
          var en = c.professionalDetail;
          var zh = c.i18n && c.i18n.zh ? c.i18n.zh.professionalDetail : null;
          if (!en || typeof en !== "string" || !en.trim()) problems.push(h.id + ": missing/empty professionalDetail (en)");
          if (!zh || typeof zh !== "string" || !zh.trim()) problems.push(h.id + ": missing/empty i18n.zh.professionalDetail");
          if (en && zh && en === zh) problems.push(h.id + ": i18n.zh.professionalDetail is byte-identical to the English professionalDetail");
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: holdings.length + " holding claims each carry a non-empty, English-distinct professionalDetail/i18n.zh.professionalDetail." };
      },
      injectDefect: function (data) {
        var c = data.getHoldingClaim("AAPL");
        return withMutatedFields(c, { professionalDetail: "" });
      }
    },
    {
      // Post-HG1 Checkpoint A correction round (designer-34, F6) — the prior version
      // matched quantity as a bare substring (e.g. "20" also occurs inside the date
      // "2026-07-02") and reconciled the price only in the English professionalDetail,
      // never the Chinese one. Now: quantity is matched as the exact LABELLED fragment
      // both branches actually render ("Quantity: <n>" en / "数量:<n>" zh — see F1), and
      // price is reconciled in BOTH professionalDetail and i18n.zh.professionalDetail
      // against window.APP.ui.formatCurrency(h.price, h.currency) — the canonical
      // formatter itself (the same rule js/data.js's own fmtNativeAmount is required to
      // mirror, per F4(b)), not a second hand-typed copy of its formatting rule that
      // could independently drift out of step with both.
      id: "holding.professionalDetail.numeralsReconcileWithRecord",
      description: "Every holding's professionalDetail (en) and i18n.zh.professionalDetail (zh) must contain that SAME holding's quantity as the exact labelled fragment 'Quantity: <n>' (en) / '数量:<n>' (zh) — never a bare substring that could coincidentally match unrelated digits such as a date — and its current price, native-currency, formatted via the canonical window.APP.ui.formatCurrency(h.price, h.currency) — both recomputed independently from getHoldings()/getHoldingClaim(), never a hand-typed literal that could drift from the underlying record.",
      check: function (data) {
        if (typeof window === "undefined" || !window.APP || !window.APP.ui || typeof window.APP.ui.formatCurrency !== "function") {
          return { pass: false, detail: "window.APP.ui.formatCurrency is not available — cannot independently reconcile native-currency price tokens. Reported as FAILED (not skipped)." };
        }
        var holdings = data.getHoldings ? data.getHoldings() : null;
        if (!holdings || !holdings.length) return { pass: false, detail: "no holdings returned from getHoldings()" };
        var problems = [];
        holdings.forEach(function (h) {
          var c = data.getHoldingClaim ? data.getHoldingClaim(h.id) : null;
          if (!c || !c.professionalDetail) { problems.push(h.id + ": no professionalDetail to check"); return; }
          var en = c.professionalDetail;
          var zh = (c.i18n && c.i18n.zh && c.i18n.zh.professionalDetail) || "";
          var expectedQtyEn = "Quantity: " + h.quantity;
          var expectedQtyZh = "数量:" + h.quantity;
          if (en.indexOf(expectedQtyEn) < 0) problems.push(h.id + ": expected labelled quantity fragment '" + expectedQtyEn + "' not found in professionalDetail");
          if (!zh || zh.indexOf(expectedQtyZh) < 0) problems.push(h.id + ": expected labelled quantity fragment '" + expectedQtyZh + "' not found in i18n.zh.professionalDetail");
          var expectedPrice = window.APP.ui.formatCurrency(h.price, h.currency);
          if (en.indexOf(expectedPrice) < 0) problems.push(h.id + ": expected price token '" + expectedPrice + "' not found in professionalDetail");
          if (!zh || zh.indexOf(expectedPrice) < 0) problems.push(h.id + ": expected price token '" + expectedPrice + "' not found in i18n.zh.professionalDetail");
        });
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "labelled quantity and native-currency price tokens in every holding's professionalDetail (en and zh) reconcile to that holding's own record via the canonical formatter (" + holdings.length + " holdings checked)." };
      },
      injectDefect: function (data) {
        var c = data.getHoldingClaim("MSFT");
        var restoreEn = withMutatedFields(c, {
          professionalDetail: "Position detail: Quantity: 999999, listing market: US, currency USD. Average cost: $1.00. Current price: $1.00. Sufficiency: available. The per-position methodology registry entry for this figure is not yet published (see Evidence & Methodology)."
        });
        var restoreZh = withMutatedFields(c.i18n.zh, {
          // Post-HG1 Checkpoint A correction round 3 (F-2, designer-35) — "充足" -> "可用",
          // moved together with js/data.js's own fix so this fixture keeps matching the
          // real professionalDetail shape it is standing in for. Does not affect this
          // test's check logic (quantity/price token reconciliation only).
          professionalDetail: "持仓明细:数量:999999,上市地:US,货币:USD。平均成本:$1.00。现价:$1.00。数据充分性:可用。该数值对应的单一持仓层面方法论登记条目尚未发布(见证据与方法论)。"
        });
        return function restore() { restoreEn(); restoreZh(); };
      }
    },
    {
      id: "holding.professionalDetail.insufficientDataHasNoPercentage",
      description: "600519.SS's holding claim is INSUFFICIENT_DATA (missing cost basis) in this fixture; its professionalDetail (en AND zh) must carry no percentage figure at all, since no gain/loss figure is estimated or shown for this position — a Professional-depth reader must never see a number the claim itself says cannot be computed.",
      check: function (data) {
        var c = data.getHoldingClaim ? data.getHoldingClaim("600519.SS") : null;
        if (!c || c.sufficiency !== "INSUFFICIENT_DATA") return { pass: false, detail: "600519.SS holding claim not found or not INSUFFICIENT_DATA (fixture may have changed) — cannot verify" };
        var en = c.professionalDetail || "";
        var zh = (c.i18n && c.i18n.zh && c.i18n.zh.professionalDetail) || "";
        var problems = [];
        if (en.indexOf("%") >= 0) problems.push("English professionalDetail contains a '%' character");
        if (zh.indexOf("%") >= 0) problems.push("Chinese professionalDetail contains a '%' character");
        if (problems.length) return { pass: false, detail: problems.join(" | ") };
        return { pass: true, detail: "600519.SS's INSUFFICIENT_DATA professionalDetail (en and zh) carries no percentage figure." };
      },
      injectDefect: function (data) {
        var c = data.getHoldingClaim("600519.SS");
        return withMutatedFields(c, { professionalDetail: (c.professionalDetail || "") + " Unrealized gain/loss: +12.3%." });
      }
    }
  ];

  // =======================================================================
  // run() — the ordinary, page-load check. No mutation, ever.
  // =======================================================================
  function run() {
    var data = APP.data;
    if (!data || typeof data.getMetric !== "function") {
      var results = [{
        id: "selfcheck.dataMissing",
        description: "window.APP.data must exist (with its accessor functions) before any other assertion can run.",
        pass: false,
        detail: "window.APP.data is " + (data ? "present but missing accessor functions" : "undefined") + " at the time selfcheck.run() executed."
      }];
      logResults("run", results);
      return results;
    }
    var results = ASSERTIONS.map(function (def) { return runOne(def, data); });
    logResults("run", results);
    return results;
  }

  // =======================================================================
  // selfTest() — THE ACCEPTANCE BAR. For each assertion: confirm it currently passes,
  // reintroduce its own named defect, confirm it now FAILS, then restore — always,
  // even if something throws (try/finally). `pass: true` here means "mechanically
  // demonstrated to detect its own defect," not "the author believes it would."
  // =======================================================================
  function selfTest() {
    var data = APP.data;
    if (!data || typeof data.getMetric !== "function") {
      var results = [{ id: "selfTest.dataMissing", description: "window.APP.data must exist before self-test can run.", pass: false, detail: "window.APP.data is undefined or incomplete." }];
      logResults("selfTest", results);
      return results;
    }
    var results = ASSERTIONS.map(function (def) {
      if (typeof def.injectDefect !== "function") {
        // Requirement 4: an assertion with no demonstrated negative test is not a
        // verified control. None of the assertions above are missing one, but this
        // branch exists so a future addition can never ship silently unverified.
        return { id: def.id, description: def.description, pass: false, detail: "NO NEGATIVE TEST DEFINED for this assertion — it has not been demonstrated to detect its own defect and must not be trusted as a control until one is added (or it should be removed)." };
      }
      var restore = null;
      try {
        var before = runOne(def, data);
        restore = def.injectDefect(data);
        var during = runOne(def, data);
        var detected = before.pass === true && during.pass === false;
        return {
          id: def.id,
          description: def.description,
          pass: detected,
          detail: "before-injection: pass=" + before.pass + " (" + before.detail + ") | after-injection: pass=" + during.pass + " (" + during.detail + ")" +
            (detected ? "" : " — EXPECTED before=true and after=false; this assertion did NOT behave as a working control.")
        };
      } catch (e) {
        return { id: def.id, description: def.description, pass: false, detail: "selfTest threw: " + (e && e.message ? e.message : String(e)) };
      } finally {
        if (restore) {
          try { restore(); } catch (e2) { /* restoration must never itself throw further */ }
        }
      }
    });
    logResults("selfTest", results);
    return results;
  }

  function logResults(label, results) {
    if (typeof console === "undefined") return;
    try {
      var failed = results.filter(function (r) { return !r.pass; });
      if (console.table) console.table(results);
      else results.forEach(function (r) { console.log("[selfcheck." + label + "]", r.pass ? "PASS" : "FAIL", r.id, "-", r.detail); });
      if (failed.length) {
        console.warn("[selfcheck." + label + "] " + failed.length + " of " + results.length + " FAILED:");
        failed.forEach(function (r) { console.warn("  FAIL " + r.id + ": " + r.description + " — " + r.detail); });
      } else {
        console.log("[selfcheck." + label + "] all " + results.length + " passed.");
      }
    } catch (e) { /* logging must never throw or block anything */ }
  }

  APP.selfcheck.run = run;
  APP.selfcheck.selfTest = selfTest;

  function boot() {
    // "running at page load" for run() only — selfTest() mutates live claim objects
    // (always restoring immediately afterward) and is deliberately manual-invocation
    // only, so a page load never causes visible flicker or unnecessary mutation.
    try {
      if (typeof document === "undefined") return;
      if (document.readyState === "complete") run();
      else window.addEventListener("load", function () { run(); });
    } catch (e) { /* never let boot-time wiring throw */ }
  }
  boot();
})();
