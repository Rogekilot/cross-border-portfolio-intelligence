/*
 * evidence.js — Methodology & Evidence overlay (D1 surface 11, D4, P9, FR-032).
 * Owned by designer-13 (phase 2, cold-started worker). Calls APP.registerEvidence(handler).
 *
 * The §D4/§21/§5(Direction-C-evidence-note) path this file renders, every time:
 *   visual/conclusion  ->  key number  ->  explanation  ->  evidence  ->  methodology
 * "Visual conclusion" and (usually) "key number" were already shown on the surface the
 * user clicked from — this overlay picks up from "key number" (re-shown compactly, when
 * resolvable) through "methodology," closing the trace. Reachable from a single click
 * anywhere a claim is rendered (D4.2: every depth level, not gated to Professional);
 * closed until then — this file never renders unsolicited, only inside the overlay
 * shell.js already opens on APP.ui.openEvidence(claimId).
 *
 * TWO FACTS THIS FILE HONORS RATHER THAN PAPERS OVER (see CONTRACT.md §7, AC-17):
 *  1. The methodology registry is EMPTY BY DESIGN for most metrics — five entries are
 *     fully populated, the rest deliberately return null from APP.data.getMethodology().
 *     This file renders that as an explicit "not yet published" state, never fabricated
 *     formula/field content to make a panel look complete.
 *  2. Not every claim id this overlay is asked to open has a registered evidence record.
 *     Rather than a bare failure, this file distinguishes three honest cases: (a) a normal
 *     registered claim (metric/holding/instrument/transaction/insight) — full path; (b) one
 *     of ai.js's synthesized "fact.*" ids (a raw ledger count/sum with no metric registry
 *     entry to point to) — a short honest note, not a fabricated methodology; (c) a
 *     scenario-derived composite id (scenario.js's/ai.js's per-comparison claim ids,
 *     scenarioId + "." + key and scenarioId + ".allocation." + dimension).
 *     UPDATE, integration pass (designer-14): case (c) is no longer an uncovered gap for
 *     the ids scenario.js and ai.js actually construct — data.js now registers a real
 *     Proof Packet for every one of them (see data.js's "Scenario-comparison claims"
 *     section) and exposes APP.data.getScenarioComparisonClaim(id) so this file can also
 *     re-show the "key number" step (with its SCENARIO badge) for them, not just
 *     Explanation onward. renderScenarioFallback() below is kept as defense-in-depth for
 *     any scenario-prefixed id that is NOT one of those (a genuinely unknown/future one),
 *     not as the primary path anymore.
 *
 * I could not execute or render this file. No browser or JS runtime exists in this
 * sandbox. See the handback for exactly what that means was/was not verified.
 *
 * HG1 ROUND 5 CORRECTION PASS (designer, this pass) — Objective 2. Every structural
 * string this file authors (block headers, field-value fallbacks, fallback-path
 * messages) now routes through APP.ui.t()/tf(), closing the two hardcoded strings named
 * explicitly in this round's brief (`"Reference: "` / `"Compared against: "`, both
 * below) plus the rest of this file's own English-only content. `claim.referenceLabel`
 * (added in an earlier pass, js/shell.js) is reused for the first rather than a second,
 * separately-named key — one label for "a reference point follows," not two.
 */
(function () {
  "use strict";
  window.APP = window.APP || {};
  var APP = window.APP;

  // -----------------------------------------------------------------------
  // Small local helpers
  // -----------------------------------------------------------------------
  function textNode(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined && text !== null) el.textContent = text;
    return el;
  }

  function blockHeader(text) {
    var header = document.createElement("div");
    header.className = "block-header";
    header.appendChild(textNode("span", "block-kicker", text));
    return header;
  }

  function block(className) {
    var el = document.createElement("div");
    el.className = "block " + className;
    return el;
  }

  function labelize(key) {
    return String(key)
      .replace(/_/g, " ")
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function pathBreadcrumb() {
    return textNode("p", "evidence-path-breadcrumb text-faint", APP.ui.t("evidence.breadcrumb"));
  }

  // -----------------------------------------------------------------------
  // Known non-metric FACT ids ai.js synthesizes (see its factClaim() comment).
  // These are real accessor-derived numbers with no metric registry entry —
  // honestly explained here, never given a fabricated methodology.
  // -----------------------------------------------------------------------
  var NON_METRIC_FACT_NOTES_KEY = {
    "fact.holdingsCount": "evidence.fact.holdingsCount",
    "fact.marketsCount": "evidence.fact.marketsCount",
    "fact.totalPortfolioValue": "evidence.fact.totalPortfolioValue"
  };

  // -----------------------------------------------------------------------
  // Key number — re-shown compactly when the claim id resolves through
  // APP.data.getMetric(id) (true for "metric.*"/"exposure.*" ids, since those
  // ids equal their own map keys in data.js). For holding/instrument/
  // transaction claim ids, no reverse "resolve this claim's own id back to
  // its object" accessor is exposed in CONTRACT.md — a real gap, noted in the
  // handback — so this section is simply omitted for those, and the trace
  // still proceeds from Explanation onward using the Evidence record's own
  // fields (which already carry the claim's conclusion text either way).
  // -----------------------------------------------------------------------
  function renderKeyNumber(container, claim) {
    var wrap = block("evidence-keynumber");
    wrap.appendChild(blockHeader(APP.ui.t("evidence.keyNumber")));
    if (claim.stateType === "SCENARIO") {
      var badgeWrap = document.createElement("div");
      APP.ui.renderActualScenarioBadge(badgeWrap, "SCENARIO");
      wrap.appendChild(badgeWrap);
    }
    wrap.appendChild(textNode("p", "claim-label", APP.ui.localizeClaimField(claim, "label") || ""));
    var valueRow = document.createElement("div");
    valueRow.className = "claim-value-row";
    APP.ui.renderMetricValue(valueRow, claim);
    wrap.appendChild(valueRow);
    // HG1 Round 5 correction pass (Objective 2 — the two hardcoded strings this
    // round's brief names explicitly). Reuses `claim.referenceLabel` (shell.js),
    // the SAME key an earlier pass already introduced to fix the identical
    // literal at shell.js:1549 — one "Reference: " label across this codebase,
    // not two independently-maintained copies.
    if (claim.referencePoint) wrap.appendChild(textNode("p", "claim-reference", APP.ui.t("claim.referenceLabel") + APP.ui.localizeClaimField(claim, "referencePoint")));
    container.appendChild(wrap);
  }

  // -----------------------------------------------------------------------
  // Explanation — the deterministic conclusion text this claim/insight
  // already carries (evidence.claim), plus its comparison basis (P4).
  // -----------------------------------------------------------------------
  function renderExplanation(container, evidence) {
    var wrap = block("evidence-explanation");
    wrap.appendChild(blockHeader(APP.ui.t("evidence.explanation")));
    wrap.appendChild(textNode("p", "claim-simple", evidence.claim || APP.ui.t("evidence.noExplanationRecorded")));
    if (evidence.comparison_basis) wrap.appendChild(textNode("p", "claim-reference", APP.ui.t("evidence.comparedAgainstLabel") + evidence.comparison_basis));
    container.appendChild(wrap);
  }

  // -----------------------------------------------------------------------
  // Evidence — the full §21 Proof Packet, grouped for readability rather
  // than dumped as one flat field list (an explicit improvement over
  // shell.js's own basic fallback, per CONTRACT.md §7's framing of what this
  // file is meant to replace).
  // -----------------------------------------------------------------------
  var PROOF_PACKET_GROUPS = [
    { titleKey: "evidence.whatThisIs", fields: ["insight_id", "insight_type", "severity", "judgment_class"] },
    { titleKey: "evidence.scope", fields: ["metrics_used", "portfolio_snapshot_id", "scenario_id", "benchmark", "period", "frequency", "observations"] },
    { titleKey: "evidence.dataQualityLimitations", fields: ["thresholds_limits_if_used", "confidence_availability_state", "limitations"] },
    { titleKey: "evidence.whereToGoNext", fields: ["permitted_suggested_explorations"] }
  ];

  function renderFieldValue(dl, field, value) {
    dl.appendChild(textNode("dt", null, labelize(field)));
    var dd = document.createElement("dd");
    if (Array.isArray(value)) {
      dd.textContent = value.length ? value.join("; ") : APP.ui.t("evidence.none");
    } else if (value === null || value === undefined || value === "") {
      dd.textContent = APP.ui.t("evidence.notApplicable");
    } else {
      dd.textContent = String(value);
    }
    dl.appendChild(dd);
  }

  function renderProofPacket(container, evidence) {
    var wrap = block("evidence-proof-packet");
    wrap.appendChild(blockHeader(APP.ui.t("evidence.proofPacket")));

    PROOF_PACKET_GROUPS.forEach(function (group) {
      var hasAny = group.fields.some(function (f) { return evidence[f] !== null && evidence[f] !== undefined && evidence[f] !== ""; });
      if (!hasAny) return;
      wrap.appendChild(textNode("h4", "evidence-fields-group-title", APP.ui.t(group.titleKey)));
      var dl = document.createElement("dl");
      dl.className = "evidence-fields";
      group.fields.forEach(function (f) {
        if (evidence[f] === null || evidence[f] === undefined || evidence[f] === "") return;
        renderFieldValue(dl, f, evidence[f]);
      });
      wrap.appendChild(dl);
    });

    // source_data_timestamps, methodology_versions, data_freshness get their
    // own dedicated, structurally-correct renderers rather than a flat dl.
    if (evidence.source_data_timestamps && evidence.source_data_timestamps.length) {
      wrap.appendChild(textNode("h4", "evidence-fields-group-title", APP.ui.t("evidence.sourceDataTimestamps")));
      var tsList = document.createElement("ul");
      tsList.className = "evidence-timestamp-list";
      evidence.source_data_timestamps.forEach(function (ts) { tsList.appendChild(textNode("li", null, ts)); });
      wrap.appendChild(tsList);
    }
    if (evidence.methodology_versions) {
      wrap.appendChild(textNode("h4", "evidence-fields-group-title", APP.ui.t("evidence.methodologyEngineVersion")));
      var mvDl = document.createElement("dl");
      mvDl.className = "evidence-fields";
      Object.keys(evidence.methodology_versions).forEach(function (k) { renderFieldValue(mvDl, k, evidence.methodology_versions[k]); });
      wrap.appendChild(mvDl);
    }
    if (evidence.data_freshness) {
      wrap.appendChild(textNode("h4", "evidence-fields-group-title", APP.ui.t("evidence.dataFreshnessD5")));
      var freshMount = document.createElement("div");
      APP.ui.renderFreshnessStrip(freshMount, evidence.data_freshness);
      wrap.appendChild(freshMount);
    }

    container.appendChild(wrap);
  }

  // -----------------------------------------------------------------------
  // Methodology — the destination D4 points to. Honest "not yet published"
  // for the many deliberately-unpopulated registry entries (AC-17) — never
  // fabricated formula/limitation text.
  // -----------------------------------------------------------------------
  function renderMethodologyEntry(entry, id) {
    var box = document.createElement("div");
    box.className = "methodology-entry";
    if (!entry) {
      box.appendChild(textNode("h4", null, id));
      box.appendChild(textNode("p", "methodology-not-published", APP.ui.t("evidence.notYetPublishedFull")));
      return box;
    }
    box.appendChild(textNode("h4", null, entry.metricName || id));
    var dl = document.createElement("dl");
    dl.className = "methodology-fields";
    Object.keys(entry).forEach(function (field) {
      if (field === "metricName") return;
      dl.appendChild(textNode("dt", null, labelize(field)));
      dl.appendChild(textNode("dd", null, String(entry[field])));
    });
    box.appendChild(dl);
    return box;
  }

  function renderMethodologySection(container, methodologyId) {
    var wrap = block("evidence-methodology");
    wrap.appendChild(blockHeader(APP.ui.t("evidence.methodology")));
    if (!methodologyId) {
      wrap.appendChild(textNode("p", "methodology-not-published", APP.ui.t("evidence.noMethodologyPointer")));
    } else {
      wrap.appendChild(renderMethodologyEntry(APP.data.getMethodology(methodologyId), methodologyId));
    }
    container.appendChild(wrap);
  }

  // -----------------------------------------------------------------------
  // Fallbacks for claim ids the evidence registry does not cover.
  // -----------------------------------------------------------------------
  function renderFactFallback(claimId, note) {
    var wrap = block("evidence-fact-fallback");
    wrap.appendChild(blockHeader(APP.ui.t("evidence.portfolioFactHeader")));
    wrap.appendChild(textNode("p", "claim-simple", note));
    return wrap;
  }

  // DEFENSE-IN-DEPTH ONLY (see file header UPDATE note): every composite id
  // scenario.js/ai.js actually construct now resolves through the normal
  // `evidence` branch above via data.js's registered SCENARIO_CLAIMS, so this
  // function is only reached for a scenario-prefixed id this build did not
  // anticipate. It recovers the owning scenario by prefix match against
  // APP.data.getScenarios() (real data, not string-guessing an undocumented
  // id format beyond the one documented convention scenario ids themselves
  // already use) and shows what is honestly available: the scenario's own
  // description, warnings,
  // and SCENARIO badge — never a fabricated Proof Packet.
  function renderScenarioFallback(claimId) {
    var scenarios = (APP.data && APP.data.getScenarios) ? APP.data.getScenarios() : [];
    var match = null;
    scenarios.forEach(function (s) {
      if (claimId.indexOf(s.id + ".") === 0) match = s;
    });
    if (!match) return null;

    var wrap = block("evidence-scenario-fallback");
    wrap.appendChild(blockHeader(APP.ui.t("evidence.scenarioHypotheticalHeader")));
    var badgeWrap = document.createElement("div");
    APP.ui.renderActualScenarioBadge(badgeWrap, "SCENARIO");
    wrap.appendChild(badgeWrap);
    wrap.appendChild(textNode("p", "claim-simple",
      APP.ui.tf("evidence.scenarioFallbackTemplate", {
        name: APP.ui.localizeClaimField(match, "name"),
        description: APP.ui.localizeClaimField(match, "description")
      })));
    (match.warnings || []).forEach(function (w) { wrap.appendChild(textNode("p", "claim-caveat", w)); });
    return wrap;
  }

  function renderNotFound(claimId) {
    var wrap = block("evidence-not-found");
    wrap.appendChild(blockHeader(APP.ui.t("evidence.notFoundHeader")));
    wrap.appendChild(textNode("p", "claim-simple", APP.ui.tf("evidence.notFoundTemplate", { id: claimId })));
    return wrap;
  }

  // -----------------------------------------------------------------------
  // Browse-all view (claimId === null) — the footer "Methodology & Evidence
  // Registry" link. Every metric id is listed; unpopulated entries render
  // the same honest "not yet published" state as a single-claim view would,
  // demonstrated alongside the populated ones rather than only in prose
  // (CONTRACT.md §7). Each entry is a native <details>, closed by default,
  // so browsing the whole registry stays discoverable without dominating —
  // this view is itself an explicit opt-in action, but individual entries
  // still don't dump fifteen fields onto the screen unasked.
  // -----------------------------------------------------------------------
  function renderRegistryBrowseAll() {
    var wrap = document.createElement("div");
    wrap.className = "evidence-registry-browse";
    wrap.appendChild(blockHeader(APP.ui.t("evidence.registryTitle")));
    wrap.appendChild(textNode("p", "claim-simple", APP.ui.t("evidence.registryIntro")));

    var ids = (APP.data && APP.data.listMetricIds) ? APP.data.listMetricIds() : [];
    ids.forEach(function (id) {
      var metric = APP.data.getMetric(id);
      var details = document.createElement("details");
      details.className = "evidence-registry-item";
      var summary = document.createElement("summary");
      summary.textContent = (metric && APP.ui.localizeClaimField(metric, "label")) || id;
      details.appendChild(summary);
      details.appendChild(renderMethodologyEntry(APP.data.getMethodology(id), id));
      wrap.appendChild(details);
    });
    return wrap;
  }

  // -----------------------------------------------------------------------
  // Entry point
  // -----------------------------------------------------------------------
  function open(claimId, mountEl) {
    mountEl.innerHTML = "";
    var wrap = document.createElement("div");
    wrap.className = "evidence-panel";
    wrap.appendChild(pathBreadcrumb());

    if (claimId === null || claimId === undefined) {
      wrap.appendChild(renderRegistryBrowseAll());
      mountEl.appendChild(wrap);
      return;
    }

    var evidence = (APP.data && APP.data.getEvidence) ? APP.data.getEvidence(claimId) : null;
    if (evidence) {
      // Resolves a normal metric/holding/instrument/transaction/insight claim first;
      // falls back to a scenario-comparison claim (scenarioId + "." + key, or
      // scenarioId + ".allocation." + dimension — see data.js's "Scenario-comparison
      // claims" section, added during integration) for the composite ids scenario.js
      // and ai.js construct. Either way this is the SAME object renderMetricValue
      // and the SCENARIO badge check already know how to render — no new rendering
      // path, just a second place to look the id up.
      var metricClaim = (APP.data && APP.data.getMetric) ? APP.data.getMetric(claimId) : null;
      if (!metricClaim && APP.data && APP.data.getScenarioComparisonClaim) {
        metricClaim = APP.data.getScenarioComparisonClaim(claimId);
      }
      if (metricClaim) renderKeyNumber(wrap, metricClaim);
      renderExplanation(wrap, evidence);
      renderProofPacket(wrap, evidence);
      renderMethodologySection(wrap, evidence.methodologyId);
      mountEl.appendChild(wrap);
      return;
    }

    var factNoteKey = NON_METRIC_FACT_NOTES_KEY[claimId];
    if (factNoteKey) {
      wrap.appendChild(renderFactFallback(claimId, APP.ui.t(factNoteKey)));
      mountEl.appendChild(wrap);
      return;
    }

    var scenarioFallback = renderScenarioFallback(claimId);
    if (scenarioFallback) {
      wrap.appendChild(scenarioFallback);
      mountEl.appendChild(wrap);
      return;
    }

    wrap.appendChild(renderNotFound(claimId));
    mountEl.appendChild(wrap);
  }

  window.APP.registerEvidence({ open: open });
})();
