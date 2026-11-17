/*
 * i18n-selfcheck.js — HG1 Round 5 micro-pass (Item 2), tests for the localization
 * classifier (APP.i18n.CANONICAL_CONTENT_ALLOWLIST / isAllowlistedCanonical, both
 * js/shell.js) and for translation-coverage over the shared I18N dictionary.
 *
 * A SIBLING to js/selfcheck.js, not an addition to it, on this pass's own
 * instruction: js/selfcheck.js reads ONLY window.APP.data, by design (see its own
 * header comment) — it never touches window.APP.i18n/APP.ui, and this file's checks
 * are entirely about the i18n layer, not the deterministic data layer. Keeping them
 * separate preserves that boundary rather than blurring it for convenience.
 *
 * Depends on js/shell.js (APP.i18n, APP.ui) and js/data.js (APP.data — the
 * classifier's security-name/account-name categories read it live). Loaded after
 * both in index.html.
 *
 * Every assertion below follows this project's own established discipline (see
 * js/shell.js's APP.uicheck mutation tests): run the check in its PASSING state,
 * then deliberately introduce the exact defect the check exists to catch, confirm
 * the check now FAILS, then restore and confirm it passes again. A check that
 * cannot be shown to fail is not yet a check.
 */
(function () {
  "use strict";
  window.APP = window.APP || {};
  var APP = window.APP;
  APP.i18nCheck = APP.i18nCheck || {};

  function isAllowlisted(str, opts) {
    return APP.i18n && typeof APP.i18n.isAllowlistedCanonical === "function"
      ? APP.i18n.isAllowlistedCanonical(str, opts)
      : false;
  }

  // =========================================================================
  // 1. Exempt canonical / source content -> exempt
  // =========================================================================
  // One representative per category this pass's brief named, plus the
  // categories the classifier already covered before this pass (kept, so a
  // regression in an OLD category is caught by this same suite, not only new
  // ones). Security/account names are read LIVE from APP.data (first two
  // entries), matching the classifier's own derivation — if the fixture ever
  // changes these two holdings/accounts, this test still passes without
  // editing this file, exactly as intended.
  function exemptSamples() {
    var samples = [
      // NEW categories (Item 2)
      { label: "canonical security name (from APP.data.getHoldings)", value: (function () {
        var h = APP.data && APP.data.getHoldings ? APP.data.getHoldings() : [];
        return h.length ? h[0].name : "Apple Inc.";
      })() },
      { label: "user-entered account name (from APP.data.getAccounts)", value: (function () {
        var a = APP.data && APP.data.getAccounts ? APP.data.getAccounts() : [];
        return a.length ? a[0].name : "US Broker Brokerage (US)";
      })() },
      { label: "product brand", value: "Meridian Cross-Border" },
      { label: "product brand subtitle", value: "Portfolio Intelligence" },
      // Post-HG1 Checkpoint A — S1 (designer-33, 2026-09-15): updated to match
      // the banner literal's own correction (index.html, js/shell.js's
      // CANONICAL_CONTENT_ALLOWLIST.brandAndBanner) — the false, mutable
      // gate-state clause is gone.
      { label: "synthetic-data banner", value: "SYNTHETIC DATA — HG1 DESIGN-REVIEW PROTOTYPE — NOT AN IMPLEMENTATION" },
      { label: "composed source-row preview (raw CSV column)", value: "Date: 2026-08-28" },
      { label: "composed source-row preview (mapped field key)", value: "ticker: AAPL" },
      { label: "composed source-row preview (mapped field key, enum value)", value: "type: BUY" },
      { label: "composed source-row preview, blank value (trailing colon)", value: "Quantity:" },
      // Post-HG1 Checkpoint A — D3 (designer-33, 2026-09-15): "REDUCE_WEIGHT"
      // REMOVED from this exempt-samples list. It is a scenario action code,
      // now presented as a human-readable bilingual label
      // (js/surfaces/scenario.js's APP.scenarioPresentation) rather than
      // rendered raw — it must NOT be exempt any more. See
      // testScenarioActionsNotExempt() below for its own dedicated,
      // live-derived coverage (never a hand list), and
      // APP.i18n.isAllowlistedCanonical's own "SUPERSEDED IN PART" comment
      // (js/shell.js) for the classifier-side change this test verifies.
      { label: "canonical multi-word enum/reason code", value: "MISSING_FX_HISTORY" },
      // Pre-existing categories (regression coverage)
      { label: "currency code", value: "HKD" },
      { label: "benchmark identifier", value: "MSCI ACWI (ACWI)" },
      { label: "bare CSV column name", value: "Symbol" },
      { label: "ticker-like instrument id", value: "0700.HK" }
    ];
    return samples;
  }

  function runExemptCheck() {
    var samples = exemptSamples();
    var failures = samples.filter(function (s) { return isAllowlisted(s.value) !== true; });
    return { pass: failures.length === 0, total: samples.length, failures: failures };
  }

  function testExemptContent() {
    var before = runExemptCheck();
    // Defect injection: corrupt the classifier itself so it always says "not
    // exempt" — the exact failure mode this test exists to catch (a category
    // silently stops being recognized).
    var original = APP.i18n.isAllowlistedCanonical;
    APP.i18n.isAllowlistedCanonical = function () { return false; };
    var during = runExemptCheck();
    APP.i18n.isAllowlistedCanonical = original;
    var after = runExemptCheck();
    return {
      name: "exempt canonical/source content -> exempt",
      beforeInjection: before, duringInjection: during, afterRestore: after,
      provenToFail: before.pass === true && during.pass === false && after.pass === true
    };
  }

  // =========================================================================
  // 2. Genuine UI chrome / prose -> not exempt
  // =========================================================================
  // Real UI strings this app renders (pulled from js/shell.js's own I18N table
  // and this pass's own new prose) plus the actual DISPLAY forms of the OCR
  // confidence vocabulary this pass just localized ("Missing," "Confirmed,"
  // "Staged for review") — mixed-case, so they cannot match either ALL-CAPS
  // pattern (tickerLike or canonicalEnumToken) by construction, which is
  // exactly the point: a pattern broad enough to correctly exempt the
  // canonical KEY "MISSING_FIELD" must not also exempt its own human-facing
  // DISPLAY label "Missing." (NOTE: this deliberately does NOT test the bare
  // ALL-CAPS single word "STAGED" — that string is a known, PRE-EXISTING
  // false positive of the tickerLike pattern this pass did not touch, since
  // any 1-6 letter uppercase word is indistinguishable from a hypothetical
  // ticker under that pattern; recorded in this designer's report rather than
  // silently worked around in this test.)
  function nonExemptSamples() {
    return [
      "Explanation depth", "Ask your portfolio", "Portfolio Settings / Policy",
      "This scenario's hypothetical cash reallocation has no benchmark-relative convention defined yet for a partial-liquidation scenario.",
      "Staged for review", "Ambiguous match", "Missing", "Confirmed",
      "A completely invented sentence of application prose that matches no category."
    ];
  }

  function runNonExemptCheck() {
    var samples = nonExemptSamples();
    var failures = samples.filter(function (s) { return isAllowlisted(s) !== false; });
    return { pass: failures.length === 0, total: samples.length, failures: failures };
  }

  function testNonExemptContent() {
    var before = runNonExemptCheck();
    // Defect injection: corrupt the classifier so it always says "exempt" —
    // the OPPOSITE failure mode from test 1, and the more dangerous one in
    // practice (it silently hides every real gap behind a false "exempt").
    var original = APP.i18n.isAllowlistedCanonical;
    APP.i18n.isAllowlistedCanonical = function () { return true; };
    var during = runNonExemptCheck();
    APP.i18n.isAllowlistedCanonical = original;
    var after = runNonExemptCheck();
    return {
      name: "genuine UI chrome/prose -> not exempt",
      beforeInjection: before, duringInjection: during, afterRestore: after,
      provenToFail: before.pass === true && during.pass === false && after.pass === true
    };
  }

  // =========================================================================
  // 5. Composed "Name (TICKER)" security identity -> exempt ONLY when both
  // halves resolve to the SAME known security (HG1 Round 5 SECOND micro-pass,
  // Defect 2). The three cases this pass's own brief requires, as two tests
  // (mirroring how tests 1/2 above group several samples by expected
  // outcome rather than one test per sample).
  // =========================================================================

  // Required case 1 — canonical `Name (TICKER)` -> exempt. Derived LIVE from
  // APP.data.getHoldings() (same reasoning as exemptSamples' first entry
  // above) so a fixture change needs no edit here.
  function composedCanonicalSample() {
    var h = APP.data && APP.data.getHoldings ? APP.data.getHoldings() : [];
    var first = h.length ? h[0] : { name: "Apple Inc.", id: "AAPL" };
    return first.name + " (" + first.id + ")";
  }

  function runComposedExemptCheck() {
    var sample = composedCanonicalSample();
    return { pass: isAllowlisted(sample) === true, sample: sample };
  }

  function testComposedCanonicalExempt() {
    var before = runComposedExemptCheck();
    var original = APP.i18n.isAllowlistedCanonical;
    APP.i18n.isAllowlistedCanonical = function () { return false; };
    var during = runComposedExemptCheck();
    APP.i18n.isAllowlistedCanonical = original;
    var after = runComposedExemptCheck();
    return {
      name: "composed canonical \"Name (TICKER)\" -> exempt",
      beforeInjection: before, duringInjection: during, afterRestore: after,
      provenToFail: before.pass === true && during.pass === false && after.pass === true
    };
  }

  // Required cases 2 and 3, bundled (same convention as nonExemptSamples()
  // above bundling several distinct non-exempt reasons into one array/check):
  // - case 2, translated UI prose that happens to END in a real ticker-shaped
  //   token in parentheses. "ACWI" is a real, tickerLike-shaped token — it is
  //   even part of the ALREADY-exempt literal "MSCI ACWI (ACWI)" — but it is
  //   not any HOLDING's `id`, so a different sentence that merely happens to
  //   end the same way must not ride along on that literal's own exemption.
  // - case 3, an unknown `Name (TICKER)` composition, two sub-cases: a wholly
  //   fabricated pairing (neither half real), and the sharper case the
  //   brief calls out specifically — a REAL ticker (AAPL) paired with the
  //   WRONG name, proving the rule requires both halves to resolve to the
  //   SAME record, not merely that each half independently matches
  //   something known.
  function composedNotExemptSamples() {
    return [
      "Selected benchmark for this comparison (ACWI)",
      "Nonexistent Corp (ZZZZ)",
      "Fake Company (AAPL)"
    ];
  }

  function runComposedNotExemptCheck() {
    var samples = composedNotExemptSamples();
    var failures = samples.filter(function (s) { return isAllowlisted(s) !== false; });
    return { pass: failures.length === 0, total: samples.length, failures: failures };
  }

  function testComposedCanonicalNotExempt() {
    var before = runComposedNotExemptCheck();
    var original = APP.i18n.isAllowlistedCanonical;
    APP.i18n.isAllowlistedCanonical = function () { return true; };
    var during = runComposedNotExemptCheck();
    APP.i18n.isAllowlistedCanonical = original;
    var after = runComposedNotExemptCheck();
    return {
      name: "composed \"Name (TICKER)\" -> NOT exempt (translated prose ending in a real ticker; unknown pairing; real ticker + wrong name)",
      beforeInjection: before, duringInjection: during, afterRestore: after,
      provenToFail: before.pass === true && during.pass === false && after.pass === true
    };
  }

  // =========================================================================
  // 6. Post-HG1 Checkpoint A — D3 (designer-33, 2026-09-15). Scenario action
  // codes (js/data.js's SCENARIOS[].modifications[].action) must no longer be
  // exempt canonical content, and the human-readable presentation
  // js/surfaces/scenario.js now renders through (APP.scenarioPresentation)
  // must actually carry distinct bilingual labels and never leak the raw
  // machine token. Both derived LIVE from APP.data.getScenarios() — never a
  // hand list — so a future scenario needs no edit here.
  // =========================================================================
  function liveScenarioActions() {
    var scenarios = APP.data && APP.data.getScenarios ? APP.data.getScenarios() : [];
    var values = {};
    (scenarios || []).forEach(function (s) {
      (s.modifications || []).forEach(function (m) {
        if (m && typeof m.action === "string") values[m.action] = true;
      });
    });
    return Object.keys(values);
  }

  function scenarioModificationsSample() {
    var scenarios = APP.data && APP.data.getScenarios ? APP.data.getScenarios() : [];
    var mods = [];
    (scenarios || []).forEach(function (s) { (s.modifications || []).forEach(function (m) { mods.push(m); }); });
    return mods;
  }

  function runScenarioActionsNotExemptCheck() {
    var actions = liveScenarioActions();
    if (!actions.length) return { pass: false, total: 0, failures: ["no live scenario action codes found via APP.data.getScenarios()"] };
    var failures = actions.filter(function (a) { return isAllowlisted(a) !== false; });
    return { pass: failures.length === 0, total: actions.length, failures: failures };
  }

  function testScenarioActionsNotExempt() {
    var before = runScenarioActionsNotExemptCheck();
    // Defect injection: corrupt the classifier so it always says "exempt" —
    // the exact regression this test exists to catch (a scenario action code
    // silently sliding back into the canonicalEnumToken exemption D3 carved
    // it out of).
    var original = APP.i18n.isAllowlistedCanonical;
    APP.i18n.isAllowlistedCanonical = function () { return true; };
    var during = runScenarioActionsNotExemptCheck();
    APP.i18n.isAllowlistedCanonical = original;
    var after = runScenarioActionsNotExemptCheck();
    return {
      name: "live scenario action codes -> NOT exempt (Post-HG1 Checkpoint A D3)",
      beforeInjection: before, duringInjection: during, afterRestore: after,
      provenToFail: before.pass === true && during.pass === false && after.pass === true
    };
  }

  // Matches this app's canonical enum/status/action CODE shape (same pattern
  // APP.i18n.CANONICAL_CONTENT_ALLOWLIST.patterns.canonicalEnumToken uses,
  // js/shell.js — reproduced here, unanchored, so it can find the token
  // anywhere inside a longer rendered line rather than only at a full-string
  // match) and a raw "<dimension>:<CODE>" token (e.g. "listingMarket:CN")
  // with no space after the colon — the exact pre-D3 shape Stage-0's
  // baseline showed on screen.
  var CANONICAL_ENUM_TOKEN_IN_TEXT_RE = /\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/;
  var DIMENSION_CODE_TOKEN_IN_TEXT_RE = /\b[a-zA-Z]+:[A-Z0-9]+\b/;

  function runScenarioActionPresentationCheck() {
    var actions = liveScenarioActions();
    var mods = scenarioModificationsSample();
    if (!actions.length || !mods.length) return { pass: false, total: 0, failures: ["no live scenario actions/modifications found"] };
    if (!APP.scenarioPresentation || typeof APP.scenarioPresentation.presentModificationLine !== "function") {
      return { pass: false, total: actions.length, failures: ["APP.scenarioPresentation.presentModificationLine is not available"] };
    }
    var failures = [];
    var originalLang = APP.i18n.getLang();
    ["en", "zh"].forEach(function (lang) {
      APP.i18n.setLangQuiet(lang);
      actions.forEach(function (a) {
        var label = APP.i18n.t("scenario.action." + a);
        if (!label || label === a) failures.push(lang + ": action '" + a + "' has no label distinct from the raw code");
      });
      mods.forEach(function (m) {
        var line = APP.scenarioPresentation.presentModificationLine(m);
        if (CANONICAL_ENUM_TOKEN_IN_TEXT_RE.test(line)) failures.push(lang + ": modification line still contains a canonicalEnumToken-shaped token: " + line);
        if (DIMENSION_CODE_TOKEN_IN_TEXT_RE.test(line)) failures.push(lang + ": modification line still contains a dimension:CODE-shaped token: " + line);
      });
    });
    APP.i18n.setLangQuiet(originalLang);
    return { pass: failures.length === 0, total: actions.length * 2 + mods.length * 2, failures: failures };
  }

  function testScenarioActionPresentation() {
    var before = runScenarioActionPresentationCheck();
    // Defect injection: revert BOTH mechanisms this check verifies to their
    // pre-Post-HG1-Checkpoint-A behavior at once — APP.i18n.t() falling
    // through to the raw code for scenario.action.* (simulating the missing
    // translation this pass added), and presentModificationLine falling back
    // to the OLD raw "key: value" join (simulating the pre-D3 rendering) —
    // proving both halves of this check (label-differs-from-code,
    // no-raw-machine-token-in-the-rendered-line) actually detect their own
    // named regression, not just one of the two.
    var originalT = APP.i18n.t;
    APP.i18n.t = function (key) {
      if (typeof key === "string" && key.indexOf("scenario.action.") === 0) return key.slice("scenario.action.".length);
      return originalT(key);
    };
    var originalPresent = APP.scenarioPresentation.presentModificationLine;
    APP.scenarioPresentation.presentModificationLine = function (m) {
      return Object.keys(m).map(function (k) { return k + ": " + m[k]; }).join(" · ");
    };
    var during = runScenarioActionPresentationCheck();
    APP.i18n.t = originalT;
    APP.scenarioPresentation.presentModificationLine = originalPresent;
    var after = runScenarioActionPresentationCheck();
    return {
      name: "scenario action presentation -> distinct bilingual labels, no raw machine token in the rendered line (Post-HG1 Checkpoint A D3)",
      beforeInjection: before, duringInjection: during, afterRestore: after,
      provenToFail: before.pass === true && during.pass === false && after.pass === true
    };
  }

  // =========================================================================
  // Shared helper — "is this key's rendered text identical in en and zh?" A
  // key whose en/zh strings are identical is either genuinely untranslated (no
  // real zh entry, t() fell back to en) or was mistakenly given a zh value
  // equal to its en value — both are the same observable defect a residual
  // DOM scan would report. Uses APP.i18n.setLangQuiet (this pass's own
  // diagnostic hook) so this comparison never triggers a visible re-render.
  // =========================================================================
  function stringsIdenticalAcrossLangs(key) {
    var originalLang = APP.i18n.getLang();
    APP.i18n.setLangQuiet("en");
    var en = APP.i18n.t(key);
    APP.i18n.setLangQuiet("zh");
    var zh = APP.i18n.t(key);
    APP.i18n.setLangQuiet(originalLang);
    return en === zh;
  }

  // =========================================================================
  // 3. Chinese-translated UI -> no gap
  // =========================================================================
  // A representative sample of REAL, already-translated keys spanning several
  // surfaces (nav, common chrome, settings, a claim-adjacent key, this pass's
  // own new reasonCode.*/ingest.confidence.* keys) — if any of these ever
  // regresses to an untranslated/identical value, this test must catch it.
  function translatedKeySample() {
    return [
      "nav.overview", "nav.analytics", "common.evidence", "common.askPortfolio",
      "settings.title", "depth.controlLabel", "reasonCode.UNSUPPORTED_ASSET",
      "ingest.confidence.staged", "ingest.confidence.ambiguousMatch",
      "pf.previewOnlyPositionNote", "scenario.modField.target",
      // HG1 Round 5 SECOND micro-pass (Defect 3) — the footer sentence this
      // pass closed; regression coverage for it going forward.
      "common.syntheticFooterNote",
      // Post-HG1 Checkpoint A — D3 (designer-33): the new scenario-action
      // label key; regression coverage for it going forward.
      "scenario.action.REDUCE_WEIGHT"
    ];
  }

  function runTranslationCoverageCheck(keys) {
    var gaps = keys.filter(function (k) { return stringsIdenticalAcrossLangs(k); });
    return { pass: gaps.length === 0, total: keys.length, gaps: gaps };
  }

  function testTranslatedUiNoGap() {
    var keys = translatedKeySample();
    var before = runTranslationCoverageCheck(keys);
    // Defect injection: corrupt ONE real, currently-good zh entry to equal its
    // English value — simulating exactly the regression this check exists to
    // catch (a translation silently reverting/never being added).
    var targetKey = "common.evidence";
    var enValue = (function () {
      var originalLang = APP.i18n.getLang();
      APP.i18n.setLangQuiet("en");
      var v = APP.i18n.t(targetKey);
      APP.i18n.setLangQuiet(originalLang);
      return v;
    })();
    var originalZhValue = (function () {
      var originalLang = APP.i18n.getLang();
      APP.i18n.setLangQuiet("zh");
      var v = APP.i18n.t(targetKey);
      APP.i18n.setLangQuiet(originalLang);
      return v;
    })();
    APP.i18n._testSetKey("zh", targetKey, enValue);
    var during = runTranslationCoverageCheck(keys);
    APP.i18n._testSetKey("zh", targetKey, originalZhValue);
    var after = runTranslationCoverageCheck(keys);
    return {
      name: "Chinese-translated UI -> no gap",
      beforeInjection: before, duringInjection: during, afterRestore: after,
      provenToFail: before.pass === true && during.pass === false &&
        during.gaps.indexOf(targetKey) >= 0 && after.pass === true
    };
  }

  // =========================================================================
  // 4. An injected untranslated UI string is detected as a gap
  // =========================================================================
  // Distinct from test 3: test 3 proves a REGRESSION in an existing
  // translation is caught; this proves a BRAND NEW string added to the
  // dictionary with no zh counterpart at all (the exact way a future feature
  // would introduce a real gap) is also caught, and that adding the missing
  // translation clears it — both states exercised, not just one.
  function testInjectedGapDetected() {
    var fakeKey = "test.i18nSelfcheck.injectedGapKey";
    APP.i18n._testSetKey("en", fakeKey, "Fake English UI Text");
    // No zh entry yet — t() falls back to the English value in `lang=zh`.
    var gapPresent = stringsIdenticalAcrossLangs(fakeKey);
    APP.i18n._testSetKey("zh", fakeKey, "假的中文界面文本");
    var gapFixed = !stringsIdenticalAcrossLangs(fakeKey);
    // Clean up — this key must not leak into the real dictionary.
    APP.i18n._testSetKey("en", fakeKey, undefined);
    APP.i18n._testSetKey("zh", fakeKey, undefined);
    return {
      name: "an injected untranslated UI string is detected as a gap",
      gapDetectedBeforeTranslation: gapPresent,
      gapClearedAfterTranslation: gapFixed,
      provenToFail: gapPresent === true && gapFixed === true
    };
  }

  // =========================================================================
  // Runner
  // =========================================================================
  APP.i18nCheck.run = function run() {
    var results = [
      testExemptContent(),
      testNonExemptContent(),
      testComposedCanonicalExempt(),
      testComposedCanonicalNotExempt(),
      testTranslatedUiNoGap(),
      testInjectedGapDetected(),
      // Post-HG1 Checkpoint A — D3 (designer-33).
      testScenarioActionsNotExempt(),
      testScenarioActionPresentation()
    ];
    var allPass = results.every(function (r) {
      // Tests 1/2/3 report pass via their own beforeInjection/afterRestore
      // shape; test 4 via its two boolean fields. Normalize to one signal.
      if (Object.prototype.hasOwnProperty.call(r, "beforeInjection")) {
        return r.beforeInjection.pass === true && r.afterRestore.pass === true;
      }
      return r.gapDetectedBeforeTranslation === true && r.gapClearedAfterTranslation === true;
    });
    var allProvenToFail = results.every(function (r) { return r.provenToFail === true; });
    return { allPass: allPass, allProvenToFail: allProvenToFail, results: results };
  };
})();
