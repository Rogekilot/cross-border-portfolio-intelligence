/*
 * ingest.js — Import & Ingestion surface (CSV + OCR-assisted).
 * Owned by designer-11 (phase 2). See ../../CONTRACT.md, specs/OCR_INGESTION_ADDENDUM.md,
 * and decisions/product/PD-0009-ocr-assisted-portfolio-ingestion-added-to-v1.md.
 *
 * Registers key "ingest", group "portfolio" (CONTRACT.md §2).
 *
 * The load-bearing invariant this whole file exists to make visually unmistakable:
 * OCR (and CSV) ingestion must NEVER silently mutate portfolio state. Every staged
 * row/field carries the STAGED badge (P8's ACTUAL-vs-SCENARIO mechanism, reused per
 * this designer's mandate) until an explicit, per-document/per-batch human confirm
 * action is taken — and even then, this prototype only simulates the resulting
 * commit (it never touches APP.data; there is no write accessor to touch). Nothing
 * here calls APP.ui.renderMetricValue on an OCR/CSV field — OCR confidence and CSV
 * row status are rendered exclusively through APP.ui.renderConfidencePill, a
 * deliberately separate vocabulary from metric sufficiency (see specs/
 * OCR_INGESTION_ADDENDUM.md §4.1).
 */
(function () {
  "use strict";

  // -----------------------------------------------------------------------
  // Style constants + DOM helpers — duplicated from portfolio.js by necessity (plain
  // scripts, no shared module system between surface files). See portfolio.js's own
  // comment on why inline var(--token) styles are used instead of new CSS classes.
  // -----------------------------------------------------------------------
  var S = {
    formRow: "display:flex;flex-direction:column;gap:4px;margin-bottom:var(--space-3);max-width:420px;",
    label: "font-size:var(--text-xs);font-weight:600;color:var(--color-ink-soft);text-transform:uppercase;letter-spacing:.04em;",
    input: "padding:var(--space-2) var(--space-3);border:1px solid var(--color-line-strong);border-radius:var(--radius-sm);font-size:var(--text-sm);font-family:inherit;background:var(--color-surface);color:var(--color-ink);",
    btnPrimary: "background:var(--color-accent);color:#fff;border:none;border-radius:var(--radius-sm);padding:var(--space-2) var(--space-4);font-weight:600;font-size:13.5px;",
    btnSecondary: "background:none;border:1px solid var(--color-line-strong);color:var(--color-ink-soft);border-radius:var(--radius-sm);padding:var(--space-2) var(--space-4);font-weight:600;font-size:13.5px;",
    panel: "border:1px solid var(--color-line);border-radius:var(--radius-md);background:var(--color-bg-recessed);padding:var(--space-4);margin-top:var(--space-3);",
    note: "font-size:var(--text-xs);color:var(--color-ink-faint);"
  };

  function el(tag, opts, kids) {
    opts = opts || {};
    var e = document.createElement(tag);
    if (opts.className) e.className = opts.className;
    if (opts.text !== undefined) e.textContent = opts.text;
    if (opts.style) e.style.cssText = opts.style;
    if (opts.attrs) {
      Object.keys(opts.attrs).forEach(function (k) { e.setAttribute(k, opts.attrs[k]); });
    }
    if (opts.value !== undefined && opts.value !== null) e.value = opts.value;
    (kids || []).forEach(function (k) { if (k) e.appendChild(k); });
    return e;
  }

  function formRow(labelText, controlEl, opts) {
    opts = opts || {};
    var row = el("div", { style: S.formRow });
    row.appendChild(el("label", { style: S.label, text: labelText + (opts.optional ? " (optional)" : "") }));
    row.appendChild(controlEl);
    if (opts.hint) row.appendChild(el("span", { style: S.note, text: opts.hint }));
    return row;
  }

  function inputEl(type, opts) {
    opts = opts || {};
    var attrs = { type: type };
    if (opts.attrs) Object.keys(opts.attrs).forEach(function (k) { attrs[k] = opts.attrs[k]; });
    var i = el("input", { style: S.input, attrs: attrs });
    if (opts.placeholder) i.placeholder = opts.placeholder;
    if (opts.value !== undefined && opts.value !== null) i.value = opts.value;
    return i;
  }

  function regionCitation(ctx, region) {
    if (!region) return "";
    return "Page " + region.page + ", region (x:" + region.x + ", y:" + region.y + ", " + region.w + "×" + region.h + ")";
  }

  // -----------------------------------------------------------------------
  // CSV import section (PRD §27.3). Uses APP.data.getIngestionFixtures().csv.
  // -----------------------------------------------------------------------
  var CSV_AMBIGUOUS_CANDIDATES = [
    { id: "TSM", label: "TSM — Taiwan Semiconductor Mfg. (NYSE ADR)" },
    { id: "2330.TW", label: "2330.TW — Taiwan Semiconductor Mfg. (TWSE)" }
  ];
  // HG1 Round 5 correction pass (Objective 2). Values routed through the new
  // `ingest.colMeaning.*` i18n keys (js/shell.js) instead of a hardcoded English
  // map — `Date`/`Symbol`/etc. below are the FIXTURE's own raw column names
  // (canonical to the sample export, never translated, per PD-0015 §2.3), only the
  // human-facing MEANING beside each is localized.
  // HG1 Round 5, Phase 2 correction pass (Blocker 3) — this map's own KEYS are
  // duplicated (not cross-referenced; this `var` is private to this file's IIFE)
  // in js/shell.js's `APP.i18n.CANONICAL_CONTENT_ALLOWLIST.csvColumnNames`, the
  // checkable artifact a future residual-localization scan should consult instead
  // of re-deriving "is this a CSV column name" per scan. Keep both lists in sync
  // if this map's keys ever change.
  var CSV_COLUMN_MEANING_KEY = {
    Date: "ingest.colMeaning.date", Symbol: "ingest.colMeaning.ticker", Action: "ingest.colMeaning.txType",
    Quantity: "ingest.colMeaning.quantity", Price: "ingest.colMeaning.price", Account: "ingest.colMeaning.account"
  };

  function buildCsvSection(ctx) {
    var wrap = el("div", {});
    var fixture = ctx.data.getIngestionFixtures().csv;

    // Step 1-2: Upload + column mapping
    var uploadBlock = el("div", { className: "block" });
    var uploadHeader = el("div", { className: "block-header" });
    uploadHeader.appendChild(el("span", { className: "block-kicker", text: ctx.ui.t("ingest.step12") }));
    uploadBlock.appendChild(uploadHeader);
    uploadBlock.appendChild(el("p", {
      text: ctx.ui.tf("ingest.csvFileNoteTemplate", { filename: fixture.filename })
    }));
    var mapTable = el("table", { className: "data-table" });
    var mapThead = el("thead", {});
    var mapHeadRow = el("tr", {});
    [ctx.ui.t("ingest.sourceColumn"), ctx.ui.t("ingest.mapsTo")].forEach(function (h) { mapHeadRow.appendChild(el("th", { text: h })); });
    mapThead.appendChild(mapHeadRow);
    mapTable.appendChild(mapThead);
    var mapTbody = el("tbody", {});
    fixture.columns.forEach(function (c) {
      var r = el("tr", {});
      r.appendChild(el("td", { text: c }));
      r.appendChild(el("td", { text: CSV_COLUMN_MEANING_KEY[c] ? ctx.ui.t(CSV_COLUMN_MEANING_KEY[c]) : ctx.ui.t("ingest.unmapped") }));
      mapTbody.appendChild(r);
    });
    mapTable.appendChild(mapTbody);
    uploadBlock.appendChild(mapTable);
    wrap.appendChild(uploadBlock);

    // Step 3: Preview + correction
    var previewBlock = el("div", { className: "block" });
    var previewHeader = el("div", { className: "block-header" });
    previewHeader.appendChild(el("span", { className: "block-kicker", text: ctx.ui.t("ingest.step3") }));
    previewBlock.appendChild(previewHeader);

    var localResolutions = {};
    var localMissingFill = {};
    var localDuplicateDecision = {};
    var confirmed = false;

    var rowsMount = el("div", {});
    previewBlock.appendChild(rowsMount);
    wrap.appendChild(previewBlock);

    function missingKeyFor(row) {
      return Object.keys(row.mapped).filter(function (k) { return row.mapped[k] === null || row.mapped[k] === ""; })[0];
    }
    // HG1 Round 5 micro-pass (Item 3) — `missingKeyFor` returns a raw internal
    // MAPPED field key (e.g. "quantity"), inserted directly into
    // "ingest.supplyMissingTemplate" ("Supply the missing {field}" /
    // "请补充缺失的{field}"). Untranslated, this produced a lowercase English
    // word inside an otherwise fully-Chinese sentence in `lang=zh` — reuses the
    // SAME `ingest.colMeaning.*` keys the column-mapping table above already
    // establishes for this exact set of six concepts, rather than a second,
    // independently-named translation (PD-0014 §2.5).
    function missingFieldDisplayName(key) {
      var byKey = { date: "ingest.colMeaning.date", ticker: "ingest.colMeaning.ticker", type: "ingest.colMeaning.txType",
        quantity: "ingest.colMeaning.quantity", price: "ingest.colMeaning.price", accountId: "ingest.colMeaning.account" };
      return byKey[key] ? ctx.ui.t(byKey[key]) : key;
    }

    function buildAmbiguousResolver(idx) {
      var w = el("div", {});
      CSV_AMBIGUOUS_CANDIDATES.forEach(function (c, cIdx) {
        var radioId = "csv-resolve-" + idx + "-" + cIdx;
        var row = el("div", { style: "display:flex;align-items:center;gap:6px;" });
        var radio = el("input", { attrs: { type: "radio", name: "csv-resolve-" + idx, id: radioId } });
        if (localResolutions[idx] === c.id) radio.checked = true;
        var label = el("label", { attrs: { "for": radioId }, style: "font-size:12px;", text: ctx.ui.translateIngestFixtureText(c.label) });
        radio.addEventListener("change", function () { localResolutions[idx] = c.id; });
        row.appendChild(radio);
        row.appendChild(label);
        w.appendChild(row);
      });
      return w;
    }

    function buildMissingFiller(idx, row) {
      var w = el("div", {});
      var input = inputEl("text", { placeholder: ctx.ui.tf("ingest.supplyMissingTemplate", { field: missingFieldDisplayName(missingKeyFor(row)) }), value: localMissingFill[idx] });
      input.addEventListener("input", function () { localMissingFill[idx] = input.value; });
      w.appendChild(input);
      return w;
    }

    function buildDuplicateResolver(idx) {
      var w = el("div", { style: "display:flex;gap:6px;align-items:center;flex-wrap:wrap;" });
      var acceptBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("ingest.importAnyway") });
      var skipBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("ingest.skip") });
      acceptBtn.addEventListener("click", function () { localDuplicateDecision[idx] = "accept"; renderRows(); });
      skipBtn.addEventListener("click", function () { localDuplicateDecision[idx] = "skip"; renderRows(); });
      w.appendChild(acceptBtn);
      w.appendChild(skipBtn);
      if (localDuplicateDecision[idx]) {
        w.appendChild(el("span", {
          style: "font-size:12px;font-weight:600;",
          text: localDuplicateDecision[idx] === "accept" ? ctx.ui.t("ingest.willImportAnyway") : ctx.ui.t("ingest.willSkipDuplicate")
        }));
      }
      return w;
    }

    function statusFieldFor(row) {
      return confirmed ? { status: "CONFIRMED" } : row;
    }

    function renderRows() {
      rowsMount.innerHTML = "";
      var table = el("table", { className: "data-table" });
      var thead = el("thead", {});
      var headRow = el("tr", {});
      [ctx.ui.t("ingest.rawRow"), ctx.ui.t("ingest.mapped"), ctx.ui.t("ingest.statusCol"), ctx.ui.t("ingest.issuesResolution")].forEach(function (h) { headRow.appendChild(el("th", { text: h })); });
      thead.appendChild(headRow);
      table.appendChild(thead);
      var tbody = el("tbody", {});

      fixture.rows.forEach(function (row, idx) {
        var tr = el("tr", {});

        var rawTd = el("td", {});
        Object.keys(row.raw).forEach(function (k) {
          rawTd.appendChild(el("div", { style: "font-size:12px;", text: k + ": " + row.raw[k] }));
        });
        tr.appendChild(rawTd);

        var mappedTd = el("td", {});
        Object.keys(row.mapped).forEach(function (k) {
          var v = row.mapped[k];
          mappedTd.appendChild(el("div", { style: "font-size:12px;", text: k + ": " + ((v === null || v === undefined || v === "") ? ctx.ui.t("ingest.missingValue") : v) }));
        });
        tr.appendChild(mappedTd);

        var statusTd = el("td", {});
        ctx.ui.renderConfidencePill(statusTd, statusFieldFor(row));
        tr.appendChild(statusTd);

        var issuesTd = el("td", {});
        // HG1 Round 5 micro-pass (Item 3) — `msg` is the import pipeline's own
        // generated explanation of the row's issue, not the source file's
        // content (contrast with `row.raw`, exempt above) — a genuine UI-text
        // gap. See js/shell.js's translateIngestFixtureText.
        (row.issues || []).forEach(function (msg) { issuesTd.appendChild(el("p", { style: "font-size:12px;margin:0 0 4px;", text: ctx.ui.translateIngestFixtureText(msg) })); });
        if (!confirmed) {
          if (row.status === "AMBIGUOUS_SECURITY") issuesTd.appendChild(buildAmbiguousResolver(idx));
          if (row.status === "MISSING_FIELD") issuesTd.appendChild(buildMissingFiller(idx, row));
          if (row.status === "POSSIBLE_DUPLICATE") issuesTd.appendChild(buildDuplicateResolver(idx));
        }
        tr.appendChild(issuesTd);

        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      rowsMount.appendChild(table);
    }
    renderRows();

    // Step 4: Import report + confirmation
    var reportBlock = el("div", { className: "block" });
    var reportHeader = el("div", { className: "block-header" });
    reportHeader.appendChild(el("span", { className: "block-kicker", text: ctx.ui.t("ingest.step4") }));
    reportBlock.appendChild(reportHeader);
    var reportMount = el("div", {});
    reportBlock.appendChild(reportMount);
    wrap.appendChild(reportBlock);

    function allResolved() {
      for (var i = 0; i < fixture.rows.length; i++) {
        var row = fixture.rows[i];
        if (row.status === "AMBIGUOUS_SECURITY" && !localResolutions[i]) return false;
        if (row.status === "MISSING_FIELD" && !localMissingFill[i]) return false;
        if (row.status === "POSSIBLE_DUPLICATE" && !localDuplicateDecision[i]) return false;
      }
      return true;
    }

    function renderReport() {
      reportMount.innerHTML = "";
      reportMount.appendChild(el("p", {
        text: ctx.ui.tf("ingest.reportSummaryTemplate", {
          staged: fixture.importReport.staged,
          confirmed: confirmed ? fixture.importReport.staged : fixture.importReport.confirmed,
          quarantined: fixture.importReport.quarantined
        })
      }));
      if (confirmed) {
        reportMount.appendChild(el("p", {
          style: "color:var(--color-fresh-live);font-weight:600;",
          text: ctx.ui.t("ingest.importConfirmedNote")
        }));
        return;
      }
      var confirmBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("ingest.confirmImportSimulated") });
      confirmBtn.addEventListener("click", function () {
        var existing = reportMount.querySelector(".ingest-csv-block-note");
        if (existing) existing.remove();
        if (!allResolved()) {
          var blockNote = el("p", { className: "ingest-csv-block-note", style: "color:var(--color-danger);font-size:var(--text-sm);", text: ctx.ui.t("ingest.resolveBeforeConfirm") });
          reportMount.appendChild(blockNote);
          return;
        }
        confirmed = true;
        renderRows();
        renderReport();
      });
      reportMount.appendChild(confirmBtn);
    }
    renderReport();

    return wrap;
  }

  // -----------------------------------------------------------------------
  // OCR-assisted ingestion section (specs/OCR_INGESTION_ADDENDUM.md).
  // Uses APP.data.getIngestionFixtures().ocr. Upload -> Extract -> Resolve -> Stage ->
  // Review -> Confirm -> Commit.
  // -----------------------------------------------------------------------
  function buildOcrDocumentCard(ctx, doc) {
    var localResolutions = {};   // fieldId -> chosen candidate string (AMBIGUOUS_SECURITY)
    var localMissingFill = {};   // fieldId -> typed correction, or fieldId+":skip" -> boolean
    var localDuplicateDecision = {}; // fieldId -> "accept" | "skip"
    var committed = false;

    var card = el("div", { className: "block" });
    var header = el("div", { className: "block-header" });
    header.appendChild(el("span", { className: "block-kicker", text: doc.filename }));
    var statusMount = el("span", {});
    header.appendChild(statusMount);
    card.appendChild(header);
    // HG1 Round 5 micro-pass (Item 3) — `doc.sourceType` is an internal
    // classification of the upload (portfolio_screenshot/brokerage_screenshot/
    // statement), not the document's own filename/content, so it was a genuine
    // mixed-language gap here (an untranslated English enum value inserted into
    // an otherwise fully-translated Chinese sentence), not a canonical
    // exemption — see js/shell.js's translateOcrSourceType.
    card.appendChild(el("p", { style: S.note, text: ctx.ui.tf("ingest.sourceLineTemplate", { sourceType: ctx.ui.translateOcrSourceType(doc.sourceType), uploadedAt: doc.uploadedAt, id: doc.id }) }));

    var fieldsMount = el("div", {});
    card.appendChild(fieldsMount);
    var actionMount = el("div", { style: "margin-top:var(--space-3);" });
    card.appendChild(actionMount);

    function renderStatus() {
      statusMount.innerHTML = "";
      if (committed) {
        ctx.ui.renderStagedBadge(statusMount, "COMMITTED");
      } else {
        ctx.ui.renderConfidencePill(statusMount, { status: doc.overallStatus });
      }
    }

    function buildFieldRow(field) {
      var row = el("div", { style: S.panel });
      var topLine = el("div", { style: "display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);flex-wrap:wrap;" });
      // HG1 Round 5 micro-pass (Item 3) — `field.label` mixes a canonical
      // security name/row reference with a short English descriptor ("...
      // quantity", "... average cost") — application narrative describing what
      // the field IS, not the source document's own text. See js/shell.js's
      // translateIngestFixtureText for the exact-string map (canonical
      // fragments kept verbatim; only the descriptor translates).
      topLine.appendChild(el("strong", { style: "font-size:var(--text-sm);", text: ctx.ui.translateIngestFixtureText(field.label) }));
      var badgesWrap = el("div", { style: "display:flex;gap:var(--space-2);align-items:center;flex-wrap:wrap;" });
      ctx.ui.renderStagedBadge(badgesWrap, committed ? "COMMITTED" : "STAGED");
      ctx.ui.renderConfidencePill(badgesWrap, field);
      topLine.appendChild(badgesWrap);
      row.appendChild(topLine);

      var valueLine = el("p", { style: "margin-top:var(--space-2);margin-bottom:0;" });
      if (field.extractedValue !== null && field.extractedValue !== undefined) {
        valueLine.textContent = ctx.ui.tf("ingest.extractedTemplate", { value: field.extractedValue });
      } else {
        valueLine.textContent = ctx.ui.t("ingest.extractedNothing");
      }
      row.appendChild(valueLine);

      if (field.correctedValue) {
        row.appendChild(el("p", {
          style: "margin-top:4px;margin-bottom:0;color:var(--color-confidence-corrected);",
          text: ctx.ui.tf("ingest.correctedToTemplate", { value: field.correctedValue, who: field.correctedBy, when: field.correctedAt })
        }));
      }
      if (field.confirmedBy) {
        row.appendChild(el("p", {
          style: "margin-top:4px;margin-bottom:0;color:var(--color-confidence-confirmed);",
          text: ctx.ui.tf("ingest.confirmedByTemplate", { who: field.confirmedBy, when: field.confirmedAt })
        }));
      }
      // HG1 Round 5 micro-pass (Item 3) — `field.note` is the OCR pipeline's own
      // generated explanation of what happened to this field, not the source
      // document's content — a genuine UI-text gap.
      if (field.note) row.appendChild(el("p", { style: S.note, text: ctx.ui.translateIngestFixtureText(field.note) }));
      if (field.region) row.appendChild(el("p", { style: S.note, text: regionCitation(ctx, field.region) + ctx.ui.t("ingest.sourceEvidencePointerSuffix") }));

      if (!committed && field.status === "AMBIGUOUS_SECURITY" && field.candidates) {
        var resolveWrap = el("div", { style: "margin-top:var(--space-2);" });
        resolveWrap.appendChild(el("p", {
          style: "font-size:var(--text-sm);font-weight:600;color:var(--color-limited);",
          text: ctx.ui.t("ingest.ambiguousSelectNote")
        }));
        field.candidates.forEach(function (c, idx) {
          var radioId = "ocr-resolve-" + field.id + "-" + idx;
          var candRow = el("div", { style: "display:flex;align-items:center;gap:6px;margin-top:4px;" });
          var radio = el("input", { attrs: { type: "radio", name: "ocr-resolve-" + field.id, id: radioId } });
          if (localResolutions[field.id] === c) radio.checked = true;
          // HG1 Round 5 micro-pass (Item 3) — `c` mixes a canonical ticker with a
          // short English descriptor ("HK listing"/"NYSE ADR"); `localResolutions`
          // still stores/compares the RAW candidate string `c` (unchanged) so the
          // resolution logic keys on the canonical value, per PD-0015 §2.3 —
          // only the rendered label text is translated.
          var label = el("label", { attrs: { "for": radioId }, style: "font-size:var(--text-sm);", text: ctx.ui.translateIngestFixtureText(c) });
          radio.addEventListener("change", function () { localResolutions[field.id] = c; });
          candRow.appendChild(radio);
          candRow.appendChild(label);
          resolveWrap.appendChild(candRow);
        });
        row.appendChild(resolveWrap);
      }

      if (!committed && field.status === "MISSING_FIELD") {
        var fillWrap = el("div", { style: "margin-top:var(--space-2);" });
        var fillInput = inputEl("text", { placeholder: ctx.ui.t("ingest.enterCorrectValuePlaceholder"), value: localMissingFill[field.id] });
        fillInput.addEventListener("input", function () { localMissingFill[field.id] = fillInput.value; });
        fillWrap.appendChild(formRow(ctx.ui.t("ingest.correctionOptionalLabel"), fillInput, { optional: true }));
        var skipRow = el("div", { style: "display:flex;align-items:center;gap:6px;" });
        var skipId = "ocr-skip-" + field.id;
        var skipCheckbox = el("input", { attrs: { type: "checkbox", id: skipId } });
        skipCheckbox.checked = !!localMissingFill[field.id + ":skip"];
        skipRow.appendChild(skipCheckbox);
        skipRow.appendChild(el("label", { attrs: { "for": skipId }, style: "font-size:var(--text-sm);", text: ctx.ui.t("ingest.quarantineFieldLabel") }));
        skipCheckbox.addEventListener("change", function () { localMissingFill[field.id + ":skip"] = skipCheckbox.checked; });
        fillWrap.appendChild(skipRow);
        row.appendChild(fillWrap);
      }

      if (!committed && field.status === "POSSIBLE_DUPLICATE") {
        var dupWrap = el("div", { style: "margin-top:var(--space-2);" });
        dupWrap.appendChild(el("p", { style: "font-size:var(--text-sm);color:var(--color-limited);", text: ctx.ui.t("ingest.possibleDuplicateNote") }));
        var dupRow = el("div", { style: "display:flex;gap:var(--space-2);align-items:center;flex-wrap:wrap;" });
        var acceptBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("ingest.importAnyway") });
        var skipBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("ingest.skip") });
        var dupResult = el("span", { style: "font-size:var(--text-sm);font-weight:600;" });
        if (localDuplicateDecision[field.id]) dupResult.textContent = localDuplicateDecision[field.id] === "accept" ? ctx.ui.t("ingest.willImportAnyway") : ctx.ui.t("ingest.willSkipDuplicate");
        acceptBtn.addEventListener("click", function () { localDuplicateDecision[field.id] = "accept"; dupResult.textContent = ctx.ui.t("ingest.willImportAnyway"); });
        skipBtn.addEventListener("click", function () { localDuplicateDecision[field.id] = "skip"; dupResult.textContent = ctx.ui.t("ingest.willSkipDuplicate"); });
        dupRow.appendChild(acceptBtn);
        dupRow.appendChild(skipBtn);
        dupRow.appendChild(dupResult);
        dupWrap.appendChild(dupRow);
        row.appendChild(dupWrap);
      }

      return row;
    }

    function renderFields() {
      fieldsMount.innerHTML = "";
      doc.fields.forEach(function (field) { fieldsMount.appendChild(buildFieldRow(field)); });
    }

    function allFieldsResolved() {
      for (var i = 0; i < doc.fields.length; i++) {
        var f = doc.fields[i];
        if (f.status === "AMBIGUOUS_SECURITY" && !localResolutions[f.id]) return false;
        if (f.status === "MISSING_FIELD" && !localMissingFill[f.id] && !localMissingFill[f.id + ":skip"]) return false;
        if (f.status === "POSSIBLE_DUPLICATE" && !localDuplicateDecision[f.id]) return false;
      }
      return true;
    }

    function renderAction() {
      actionMount.innerHTML = "";
      if (committed) {
        actionMount.appendChild(el("p", {
          style: "color:var(--color-fresh-live);font-weight:600;",
          text: ctx.ui.t("ingest.committedSimulatedNote")
        }));
        var viewBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("ingest.viewInHoldingsBtn") });
        viewBtn.addEventListener("click", function () { ctx.navigateTo("portfolio/portfolio"); });
        actionMount.appendChild(viewBtn);
        return;
      }
      var commitBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("ingest.confirmCommitSimulated") });
      commitBtn.addEventListener("click", function () {
        var existing = actionMount.querySelector(".ingest-ocr-block-note");
        if (existing) existing.remove();
        if (!allFieldsResolved()) {
          actionMount.appendChild(el("p", {
            className: "ingest-ocr-block-note",
            style: "color:var(--color-danger);font-size:var(--text-sm);",
            text: ctx.ui.t("ingest.resolveBeforeCommit")
          }));
          return;
        }
        committed = true;
        renderStatus();
        renderFields();
        renderAction();
      });
      actionMount.appendChild(commitBtn);
    }

    renderStatus();
    renderFields();
    renderAction();
    return card;
  }

  function buildOcrSection(ctx) {
    var wrap = el("div", {});

    var stepsBlock = el("div", { className: "block" });
    var stepsHeader = el("div", { className: "block-header" });
    stepsHeader.appendChild(el("span", { className: "block-kicker", text: ctx.ui.t("ingest.workflow") }));
    stepsBlock.appendChild(stepsHeader);
    var stepsRow = el("div", { style: "display:flex;gap:6px;flex-wrap:wrap;" });
    ["ingest.step.upload", "ingest.step.extract", "ingest.step.resolve", "ingest.step.stage",
      "ingest.step.review", "ingest.step.confirm", "ingest.step.commit"].forEach(function (key, i) {
      stepsRow.appendChild(el("span", {
        style: "font-size:11px;font-weight:600;padding:3px 10px;border-radius:999px;background:var(--color-accent-soft);color:var(--color-accent-strong);border:1px solid var(--color-accent);",
        text: (i + 1) + ". " + ctx.ui.t(key)
      }));
    });
    stepsBlock.appendChild(stepsRow);
    stepsBlock.appendChild(el("p", { style: S.note, text: ctx.ui.t("ingest.ocrSimNote") }));
    wrap.appendChild(stepsBlock);

    var noteBlock = el("div", { className: "block" });
    noteBlock.appendChild(el("p", {
      style: "font-size:var(--text-sm);",
      text: ctx.ui.t("ingest.ocrVocabNote")
    }));
    wrap.appendChild(noteBlock);

    var fixtures = ctx.data.getIngestionFixtures().ocr;
    fixtures.documents.forEach(function (doc) { wrap.appendChild(buildOcrDocumentCard(ctx, doc)); });

    return wrap;
  }

  // -----------------------------------------------------------------------
  // Registration
  // -----------------------------------------------------------------------
  window.APP.registerSurface("ingest", {
    group: "portfolio",
    render: function (mountEl, ctx) {
      mountEl.innerHTML = "";
      var root = el("div", {});

      var introBlock = el("div", { className: "block" });
      var introHeader = el("div", { className: "block-header" });
      introHeader.appendChild(el("span", { className: "block-kicker", text: ctx.ui.t("ingest.title") }));
      introBlock.appendChild(introHeader);
      introBlock.appendChild(el("p", {
        text: ctx.ui.t("ingest.introNote")
      }));
      var toggleRow = el("div", { style: "display:flex;gap:var(--space-2);" });
      var csvBtn = el("button", { attrs: { type: "button" } });
      var ocrBtn = el("button", { attrs: { type: "button" } });
      toggleRow.appendChild(csvBtn);
      toggleRow.appendChild(ocrBtn);
      introBlock.appendChild(toggleRow);
      root.appendChild(introBlock);

      var sectionMount = el("div", {});
      root.appendChild(sectionMount);
      mountEl.appendChild(root);

      var mode = (ctx.params && ctx.params.mode === "ocr") ? "ocr" : "csv";

      function setMode(m) {
        mode = m;
        csvBtn.style.cssText = m === "csv" ? S.btnPrimary : S.btnSecondary;
        ocrBtn.style.cssText = m === "ocr" ? S.btnPrimary : S.btnSecondary;
        csvBtn.textContent = ctx.ui.t("ingest.csvImport");
        ocrBtn.textContent = ctx.ui.t("ingest.ocrImport");
        sectionMount.innerHTML = "";
        sectionMount.appendChild(mode === "csv" ? buildCsvSection(ctx) : buildOcrSection(ctx));
      }
      csvBtn.addEventListener("click", function () { setMode("csv"); });
      ocrBtn.addEventListener("click", function () { setMode("ocr"); });
      setMode(mode);
    }
  });
})();
