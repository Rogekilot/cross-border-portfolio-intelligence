/*
 * portfolio.js — Holdings & Activity surface.
 * Owned by designer-11 (phase 2). See ../../CONTRACT.md for the module contract this
 * file is written against, and specs/OCR_INGESTION_ADDENDUM.md / PD-0009 for the
 * boundaries that also govern this file's sibling, ingest.js.
 *
 * Registers key "portfolio", group "portfolio" (CONTRACT.md §2).
 *
 * What this file demonstrates (owner's objective 3 — "Portfolio must demonstrate
 * that this is a usable portfolio-management/intelligence product, not merely an
 * analytics dashboard"):
 *   - manual position entry (simulated, staged/confirm pattern)
 *   - manual transaction entry (simulated, staged/confirm pattern)
 *   - cash and account management (accounts table, add-account, add-cash, all simulated)
 *   - complete holdings view (every position, grouped by account, not a top-5 summary)
 *   - editing and reconciliation (inline per-row edit, simulated)
 *   - security resolution, including the ambiguous case (search demo; "TSMC" query
 *     triggers a forced explicit choice between two candidates — never a silent guess)
 *   - transaction/history inspection (filterable ledger table)
 *
 * NOTHING in this file mutates APP.data. There is no write accessor exposed by
 * data.js, and none is invented here. Every "Add" / "Edit" / "Confirm" flow ends in a
 * locally rendered acknowledgment card that says plainly it is simulated and that nothing
 * elsewhere on the page changes. This is a deliberate honesty requirement, not an
 * oversight — see this designer's handoff for the full simulated-vs-wired accounting.
 */
(function () {
  "use strict";

  // -----------------------------------------------------------------------
  // Style constants — every value is a var(--token) reference, per CONTRACT.md §12's
  // "no literal hex/pixel" rule, applied via inline style because styles/app.css has
  // no form-control classes yet (flagged in this designer's handoff as a real gap for
  // designer-09/designer-14 to close). "#fff" for text-on-accent-background matches an
  // existing literal already used in app.css (.nav-tab-active, .ai-ask-btn:hover) rather
  // than introducing a new one.
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

  // -----------------------------------------------------------------------
  // Small DOM helpers — private to this file, not exported.
  // -----------------------------------------------------------------------
  function el(tag, opts, kids) {
    opts = opts || {};
    var e = document.createElement(tag);
    if (opts.className) e.className = opts.className;
    if (opts.text !== undefined) e.textContent = opts.text;
    if (opts.style) e.style.cssText = opts.style;
    if (opts.attrs) {
      Object.keys(opts.attrs).forEach(function (k) { e.setAttribute(k, opts.attrs[k]); });
    }
    if (opts.value !== undefined) e.value = opts.value;
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

  function selectEl(options, opts) {
    opts = opts || {};
    var s = el("select", { style: S.input });
    options.forEach(function (o) {
      s.appendChild(el("option", { attrs: { value: o.value }, text: o.label }));
    });
    if (opts.value !== undefined) s.value = opts.value;
    return s;
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

  function uniqueValues(items, keyFn) {
    var seen = {}, out = [];
    items.forEach(function (it) {
      var k = keyFn(it);
      if (!seen[k]) { seen[k] = true; out.push(k); }
    });
    return out;
  }

  function stagedCard(ctx) {
    var card = el("div", { style: S.panel });
    var badgeMount = el("div", {});
    ctx.ui.renderStagedBadge(badgeMount, "STAGED");
    card.appendChild(badgeMount);
    return card;
  }

  function commitCardInPlace(ctx, card, message) {
    card.innerHTML = "";
    var badgeMount = el("div", {});
    ctx.ui.renderStagedBadge(badgeMount, "COMMITTED");
    card.appendChild(badgeMount);
    card.appendChild(el("p", { style: "margin-top:var(--space-2);", text: message }));
  }

  // -----------------------------------------------------------------------
  // Security resolution — reused by both manual-entry forms. Demonstrates PRD §27.3's
  // "do not silently guess an ambiguous security" for the manual-entry route (the
  // ingest.js surface demonstrates the same discipline for CSV/OCR routes).
  //
  // This is a SIMULATED lookup only: it matches against the real getHoldings()/
  // getHolding() accessors (so any single match uses real portfolio data), plus one
  // hardcoded illustrative ambiguous pair ("TSMC" -> TSM vs 2330.TW) reused from the
  // same illustrative case already present in ingest.js's CSV fixture, so no new
  // security identity is invented here. There is no general-purpose instrument-search
  // accessor in data.js; flagged in this designer's handoff as a gap.
  // -----------------------------------------------------------------------
  var AMBIGUOUS_DEMO_QUERY = "tsmc";
  var AMBIGUOUS_DEMO_CANDIDATES = [
    { id: "TSM", label: "TSM — Taiwan Semiconductor Mfg. (NYSE ADR)" },
    { id: "2330.TW", label: "2330.TW — Taiwan Semiconductor Mfg. (TWSE)" }
  ];

  function buildSecurityResolver(ctx) {
    var state = { id: null, label: null };
    var wrap = el("div", { style: S.formRow });
    wrap.appendChild(el("label", { style: S.label, text: ctx.ui.t("pf.securitySearchLabel") }));
    var row = el("div", { style: "display:flex;gap:var(--space-2);" });
    var input = inputEl("text", { placeholder: ctx.ui.t("pf.securitySearchPlaceholder") });
    input.style.cssText = S.input + "flex:1 1 auto;";
    var searchBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("common.search") });
    row.appendChild(input);
    row.appendChild(searchBtn);
    wrap.appendChild(row);
    var resultMount = el("div", { style: "margin-top:var(--space-2);" });
    wrap.appendChild(resultMount);

    searchBtn.addEventListener("click", function () {
      resultMount.innerHTML = "";
      state.id = null; state.label = null;
      var q = input.value.trim();
      if (!q) return;
      var qLower = q.toLowerCase();

      if (qLower === AMBIGUOUS_DEMO_QUERY) {
        resultMount.appendChild(el("p", {
          style: "font-size:var(--text-sm);color:var(--color-limited);background:var(--color-limited-bg);border:1px solid var(--color-limited-border);border-radius:var(--radius-sm);padding:var(--space-2) var(--space-3);",
          text: ctx.ui.t("pf.ambiguousMatchNote")
        }));
        AMBIGUOUS_DEMO_CANDIDATES.forEach(function (c, idx) {
          var radioId = "sec-resolve-" + idx + "-" + Math.floor(Math.random() * 100000);
          var candRow = el("div", { style: "display:flex;align-items:center;gap:6px;margin-top:4px;" });
          var radio = el("input", { attrs: { type: "radio", name: "sec-resolve-group", id: radioId } });
          var label = el("label", { attrs: { "for": radioId }, style: "font-size:var(--text-sm);", text: c.label });
          radio.addEventListener("change", function () { state.id = c.id; state.label = c.label; });
          candRow.appendChild(radio);
          candRow.appendChild(label);
          resultMount.appendChild(candRow);
        });
        return;
      }

      var direct = ctx.data.getHolding(q.toUpperCase());
      var byName = direct ? null : ctx.data.getHoldings().filter(function (h) {
        return h.name.toLowerCase().indexOf(qLower) >= 0;
      })[0];
      var match = direct || byName;
      if (match) {
        // HG1 ux_planning revision (review-07, P0 item 1 sweep) — this manual-entry
        // security-resolver confirmation rendered `match.name` (the raw, always-English
        // holding name) directly. The search itself still matches on the raw English
        // `h.name` above (Chinese search-by-localized-name stays out of this round's
        // scope, per the owner's own deferred list) — only the CONFIRMATION TEXT for a
        // resolved match is a rendered holding name and goes through the same canonical
        // path every other surface now uses, so a match on one of the five holdings with
        // an established Chinese name is confirmed back to the user in that name.
        var matchDisplayName = ctx.ui.holdingDisplayName(match);
        resultMount.appendChild(el("p", {
          style: "font-size:var(--text-sm);color:var(--color-fresh-live);",
          text: ctx.ui.tf("pf.matchedTemplate", { id: match.id, name: matchDisplayName, market: match.listingMarket })
        }));
        state.id = match.id; state.label = match.id + " — " + matchDisplayName;
      } else {
        resultMount.appendChild(el("p", {
          style: "font-size:var(--text-sm);color:var(--color-ink-faint);",
          text: ctx.ui.t("pf.noMatchNote")
        }));
        state.id = "UNVERIFIED:" + q; state.label = ctx.ui.tf("pf.unverifiedIdentifierLabel", { query: q });
      }
    });

    return { el: wrap, state: state };
  }

  // -----------------------------------------------------------------------
  // Manual position entry (PRD §27.1). Simulated staged/confirm pattern reusing the
  // STAGED/COMMITTED badge vocabulary (CONTRACT.md §10 documents it for ingestion;
  // this is a considered extension to manual entry too, since the vocabulary's own
  // meaning — "not yet written to the ledger" — applies here just as directly. Flagged
  // as a deliberate reuse, not a redefinition, in this designer's handoff.
  // -----------------------------------------------------------------------
  function buildPositionForm(ctx) {
    var panel = el("div", { style: S.panel });
    panel.appendChild(el("h4", { text: ctx.ui.t("pf.newPositionTitle"), style: "margin-top:0;" }));
    panel.appendChild(el("p", { style: S.note, text: ctx.ui.t("pf.simulatedPositionNote") }));

    var secResolver = buildSecurityResolver(ctx);
    panel.appendChild(secResolver.el);

    var qtyInput = inputEl("number", { attrs: { min: "0", step: "any" }, placeholder: ctx.ui.t("pf.qtyPlaceholderExample") });
    panel.appendChild(formRow(ctx.ui.t("table.quantity"), qtyInput));

    var accounts = ctx.data.getAccounts();
    var acctSelect = selectEl(accounts.map(function (a) { return { value: a.id, label: a.name + " (" + a.currency + ")" }; }));
    panel.appendChild(formRow(ctx.ui.t("table.account"), acctSelect));

    var avgCostInput = inputEl("number", { attrs: { min: "0", step: "any" }, placeholder: ctx.ui.t("pf.avgCostPlaceholder") });
    panel.appendChild(formRow(ctx.ui.t("pf.averageCost"), avgCostInput, { optional: true, hint: ctx.ui.t("pf.avgCostHint") }));

    var acqDateInput = inputEl("date", {});
    panel.appendChild(formRow(ctx.ui.t("pf.acquisitionDate"), acqDateInput, { optional: true }));

    var overrideCheckbox = el("input", { attrs: { type: "checkbox", id: "pos-ccy-override" } });
    var overrideWrap = el("div", { style: "display:flex;align-items:center;gap:6px;margin-bottom:var(--space-2);" });
    overrideWrap.appendChild(overrideCheckbox);
    overrideWrap.appendChild(el("label", { attrs: { "for": "pos-ccy-override" }, style: "font-size:var(--text-sm);", text: ctx.ui.t("pf.ccyOverrideSecurityLabel") }));
    panel.appendChild(overrideWrap);
    var ccySelect = selectEl([{ value: "USD", label: "USD" }, { value: "HKD", label: "HKD" }, { value: "CNY", label: "CNY" }]);
    var ccyRow = formRow(ctx.ui.t("pf.currencyOverride"), ccySelect, { optional: true });
    ccyRow.hidden = true;
    overrideCheckbox.addEventListener("change", function () { ccyRow.hidden = !overrideCheckbox.checked; });
    panel.appendChild(ccyRow);

    var actionsRow = el("div", { style: "display:flex;gap:var(--space-2);margin-top:var(--space-3);" });
    var stageBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("common.reviewAndStage") });
    var cancelBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("common.cancel") });
    actionsRow.appendChild(stageBtn);
    actionsRow.appendChild(cancelBtn);
    panel.appendChild(actionsRow);

    var previewMount = el("div", {});
    panel.appendChild(previewMount);

    stageBtn.addEventListener("click", function () {
      previewMount.innerHTML = "";
      if (!qtyInput.value) {
        previewMount.appendChild(el("p", { style: "color:var(--color-danger);font-size:var(--text-sm);", text: ctx.ui.t("pf.qtyRequired") }));
        return;
      }
      if (!secResolver.state.id) {
        previewMount.appendChild(el("p", { style: "color:var(--color-danger);font-size:var(--text-sm);", text: ctx.ui.t("pf.resolveSecurityFirstLong") }));
        return;
      }
      var acct = accounts.filter(function (a) { return a.id === acctSelect.value; })[0];
      var card = stagedCard(ctx);
      var descP = el("p", { style: "margin-top:var(--space-2);" });
      descP.appendChild(el("strong", { text: secResolver.state.label }));
      // HG1 Round 5 micro-pass (Item 3) — this whole composed sentence
      // (including the bare English word "units") was previously assembled
      // with no `ctx.ui.t()`/`ctx.ui.tf()` call anywhere in it.
      descP.appendChild(document.createTextNode(
        " — " + ctx.ui.tf("pf.unitsAccountTemplate", { qty: qtyInput.value, account: acct.name }) +
        (avgCostInput.value
          ? ctx.ui.tf("pf.avgCostSuffixTemplate", { amount: avgCostInput.value, ccy: (overrideCheckbox.checked ? ccySelect.value : acct.currency) })
          : ctx.ui.t("pf.avgCostNotProvidedSuffix")) +
        (acqDateInput.value ? ctx.ui.tf("pf.acquiredSuffixTemplate", { date: acqDateInput.value }) : "")
      ));
      card.appendChild(descP);
      card.appendChild(el("p", { style: S.note, text: ctx.ui.t("pf.previewOnlyPositionNote") }));
      var confirmRow = el("div", { style: "display:flex;gap:var(--space-2);margin-top:var(--space-2);" });
      var confirmBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("common.confirmAndAdd") });
      var editBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("common.backToEdit") });
      confirmRow.appendChild(confirmBtn);
      confirmRow.appendChild(editBtn);
      card.appendChild(confirmRow);
      editBtn.addEventListener("click", function () { previewMount.innerHTML = ""; });
      confirmBtn.addEventListener("click", function () {
        commitCardInPlace(ctx, card, ctx.ui.t("pf.simulatedPositionWrittenNote"));
      });
      previewMount.appendChild(card);
    });
    cancelBtn.addEventListener("click", function () { panel.hidden = true; });

    return panel;
  }

  // -----------------------------------------------------------------------
  // Manual transaction entry (PRD §27.2).
  // -----------------------------------------------------------------------
  var TX_TYPES = ["BUY", "SELL", "DIVIDEND", "DEPOSIT", "WITHDRAWAL", "FX", "TRANSFER_IN", "TRANSFER_OUT"];
  var TX_TYPES_NEEDING_INSTRUMENT = ["BUY", "SELL", "DIVIDEND", "TRANSFER_IN", "TRANSFER_OUT"];

  function buildTransactionForm(ctx) {
    var panel = el("div", { style: S.panel });
    panel.appendChild(el("h4", { text: ctx.ui.t("pf.newTransactionTitle"), style: "margin-top:0;" }));
    panel.appendChild(el("p", { style: S.note, text: ctx.ui.t("pf.simulatedTransactionNote") }));

    var dateInput = inputEl("date", {});
    panel.appendChild(formRow(ctx.ui.t("table.date"), dateInput));

    // HG1 Round 5, Phase 2 correction pass (Blocker 3) — `value` stays the raw,
    // canonical TX_TYPES string (what this form submits/keys on); only `label`
    // (what the option text renders) is translated. Same split as buildAccountForm's
    // own type-select just below (ctx.ui.translateAccountType) and account-type's own
    // established fix.
    var typeSelect = selectEl(TX_TYPES.map(function (t) { return { value: t, label: ctx.ui.translateTransactionType(t) }; }));
    panel.appendChild(formRow(ctx.ui.t("table.type"), typeSelect));

    var accounts = ctx.data.getAccounts();
    var acctSelect = selectEl(accounts.map(function (a) { return { value: a.id, label: a.name + " (" + a.currency + ")" }; }));
    panel.appendChild(formRow(ctx.ui.t("table.account"), acctSelect));

    var secResolverWrap = el("div", {});
    var secResolver = buildSecurityResolver(ctx);
    secResolverWrap.appendChild(secResolver.el);
    panel.appendChild(secResolverWrap);

    function updateSecVisibility() {
      secResolverWrap.hidden = TX_TYPES_NEEDING_INSTRUMENT.indexOf(typeSelect.value) < 0;
    }
    typeSelect.addEventListener("change", updateSecVisibility);
    updateSecVisibility();

    var qtyInput = inputEl("number", { attrs: { min: "0", step: "any" } });
    panel.appendChild(formRow(ctx.ui.t("table.quantity"), qtyInput, { optional: true, hint: ctx.ui.t("pf.qtyTxHint") }));

    var priceInput = inputEl("number", { attrs: { min: "0", step: "any" } });
    panel.appendChild(formRow(ctx.ui.t("table.priceAmount"), priceInput));

    var overrideCheckbox = el("input", { attrs: { type: "checkbox", id: "tx-ccy-override" } });
    var overrideWrap = el("div", { style: "display:flex;align-items:center;gap:6px;margin-bottom:var(--space-2);" });
    overrideWrap.appendChild(overrideCheckbox);
    overrideWrap.appendChild(el("label", { attrs: { "for": "tx-ccy-override" }, style: "font-size:var(--text-sm);", text: ctx.ui.t("pf.ccyOverrideTxLabel") }));
    panel.appendChild(overrideWrap);
    var ccySelect = selectEl([{ value: "USD", label: "USD" }, { value: "HKD", label: "HKD" }, { value: "CNY", label: "CNY" }]);
    var ccyRow = formRow(ctx.ui.t("pf.currencyOverride"), ccySelect, { optional: true });
    ccyRow.hidden = true;
    overrideCheckbox.addEventListener("change", function () { ccyRow.hidden = !overrideCheckbox.checked; });
    panel.appendChild(ccyRow);

    var noteInput = inputEl("text", {});
    panel.appendChild(formRow(ctx.ui.t("table.note"), noteInput, { optional: true }));

    var actionsRow = el("div", { style: "display:flex;gap:var(--space-2);margin-top:var(--space-3);" });
    var stageBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("common.reviewAndStage") });
    var cancelBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("common.cancel") });
    actionsRow.appendChild(stageBtn);
    actionsRow.appendChild(cancelBtn);
    panel.appendChild(actionsRow);

    var previewMount = el("div", {});
    panel.appendChild(previewMount);

    stageBtn.addEventListener("click", function () {
      previewMount.innerHTML = "";
      var needsInstrument = !secResolverWrap.hidden;
      if (needsInstrument && !secResolver.state.id) {
        previewMount.appendChild(el("p", { style: "color:var(--color-danger);font-size:var(--text-sm);", text: ctx.ui.t("pf.resolveSecurityFirstLong") }));
        return;
      }
      var acct = accounts.filter(function (a) { return a.id === acctSelect.value; })[0];
      var card = stagedCard(ctx);
      var descP = el("p", { style: "margin-top:var(--space-2);" });
      // HG1 Round 5 micro-pass (Item 3) — this preview headline previously
      // rendered the raw canonical TX_TYPES code (typeSelect.value, e.g. "BUY")
      // directly as display text instead of through the SAME
      // translateTransactionType() every other display of this value already
      // uses (the Transactions table's own Type column, its filter, and this
      // form's own type-select options) — the canonical value itself is
      // unchanged; only what this ONE spot rendered is fixed to match.
      descP.appendChild(el("strong", { text: ctx.ui.translateTransactionType(typeSelect.value) }));
      descP.appendChild(document.createTextNode(
        " · " + (dateInput.value || ctx.ui.t("pf.noDateEntered")) + " · " + acct.name +
        (needsInstrument ? " · " + secResolver.state.label : "") +
        (qtyInput.value ? " · " + ctx.ui.t("pf.qtyInlineLabel") + " " + qtyInput.value : "") +
        (priceInput.value ? " · " + priceInput.value + " " + (overrideCheckbox.checked ? ccySelect.value : acct.currency) : "")
      ));
      card.appendChild(descP);
      if (noteInput.value) card.appendChild(el("p", { style: S.note, text: ctx.ui.t("table.note") + ": " + noteInput.value }));
      card.appendChild(el("p", { style: S.note, text: ctx.ui.t("pf.previewOnlyTransactionNote") }));
      var confirmRow = el("div", { style: "display:flex;gap:var(--space-2);margin-top:var(--space-2);" });
      var confirmBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("common.confirmAndAdd") });
      var editBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("common.backToEdit") });
      confirmRow.appendChild(confirmBtn);
      confirmRow.appendChild(editBtn);
      card.appendChild(confirmRow);
      editBtn.addEventListener("click", function () { previewMount.innerHTML = ""; });
      confirmBtn.addEventListener("click", function () {
        commitCardInPlace(ctx, card, ctx.ui.t("pf.simulatedTransactionWrittenNote"));
      });
      previewMount.appendChild(card);
    });
    cancelBtn.addEventListener("click", function () { panel.hidden = true; });

    return panel;
  }

  // -----------------------------------------------------------------------
  // Account and cash management (part of the owner's "cash and account management"
  // objective). Simulated staged/confirm pattern, same as above.
  // -----------------------------------------------------------------------
  function buildAccountForm(ctx) {
    var panel = el("div", { style: S.panel });
    panel.appendChild(el("h4", { text: ctx.ui.t("pf.newAccountTitle"), style: "margin-top:0;" }));
    panel.appendChild(el("p", { style: S.note, text: ctx.ui.t("common.simulatedEntryNote") }));

    var nameInput = inputEl("text", { placeholder: ctx.ui.t("pf.accountNamePlaceholder") });
    panel.appendChild(formRow(ctx.ui.t("pf.accountName"), nameInput));
    var ccySelect = selectEl([{ value: "USD", label: "USD" }, { value: "HKD", label: "HKD" }, { value: "CNY", label: "CNY" }]);
    panel.appendChild(formRow(ctx.ui.t("table.currency"), ccySelect));
    var typeSelect = selectEl([
      { value: "taxable", label: ctx.ui.translateAccountType("taxable") },
      { value: "retirement", label: ctx.ui.translateAccountType("retirement") },
      { value: "cash", label: ctx.ui.translateAccountType("cash") }
    ]);
    panel.appendChild(formRow(ctx.ui.t("table.type"), typeSelect));
    var marketSelect = selectEl([
      { value: "US", label: ctx.ui.translateGeographyLabel("US") },
      { value: "HK", label: ctx.ui.translateGeographyLabel("Hong Kong") },
      { value: "CN", label: ctx.ui.translateGeographyLabel("Mainland China") },
      { value: "GLOBAL", label: ctx.ui.t("pf.marketGlobalMulti") }
    ]);
    panel.appendChild(formRow(ctx.ui.t("table.market"), marketSelect));

    var actionsRow = el("div", { style: "display:flex;gap:var(--space-2);margin-top:var(--space-3);" });
    var stageBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("common.reviewAndStage") });
    var cancelBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("common.cancel") });
    actionsRow.appendChild(stageBtn);
    actionsRow.appendChild(cancelBtn);
    panel.appendChild(actionsRow);

    var previewMount = el("div", {});
    panel.appendChild(previewMount);
    stageBtn.addEventListener("click", function () {
      previewMount.innerHTML = "";
      if (!nameInput.value.trim()) {
        previewMount.appendChild(el("p", { style: "color:var(--color-danger);font-size:var(--text-sm);", text: ctx.ui.t("pf.accountNameRequired") }));
        return;
      }
      var card = stagedCard(ctx);
      card.appendChild(el("p", {
        style: "margin-top:var(--space-2);",
        text: nameInput.value + " · " + ccySelect.value + " · " + typeSelect.options[typeSelect.selectedIndex].text + " · " + marketSelect.options[marketSelect.selectedIndex].text
      }));
      card.appendChild(el("p", { style: S.note, text: ctx.ui.t("pf.previewOnlyAccountNote") }));
      var confirmBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("pf.confirmAndCreate") });
      confirmBtn.addEventListener("click", function () {
        commitCardInPlace(ctx, card, ctx.ui.t("pf.simulatedAccountCreatedNote"));
      });
      card.appendChild(confirmBtn);
      previewMount.appendChild(card);
    });
    cancelBtn.addEventListener("click", function () { panel.hidden = true; });

    return panel;
  }

  function buildCashForm(ctx) {
    var panel = el("div", { style: S.panel });
    panel.appendChild(el("h4", { text: ctx.ui.t("pf.addCashTitle"), style: "margin-top:0;" }));
    panel.appendChild(el("p", { style: S.note, text: ctx.ui.t("common.simulatedEntryNote") }));

    var accounts = ctx.data.getAccounts();
    var acctSelect = selectEl(accounts.map(function (a) { return { value: a.id, label: a.name }; }));
    panel.appendChild(formRow(ctx.ui.t("table.account"), acctSelect));
    var ccySelect = selectEl([{ value: "USD", label: "USD" }, { value: "HKD", label: "HKD" }, { value: "CNY", label: "CNY" }]);
    panel.appendChild(formRow(ctx.ui.t("table.currency"), ccySelect));
    var amountInput = inputEl("number", { attrs: { min: "0", step: "any" } });
    panel.appendChild(formRow(ctx.ui.t("pf.amount"), amountInput));

    var actionsRow = el("div", { style: "display:flex;gap:var(--space-2);margin-top:var(--space-3);" });
    var stageBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("common.reviewAndStage") });
    var cancelBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("common.cancel") });
    actionsRow.appendChild(stageBtn);
    actionsRow.appendChild(cancelBtn);
    panel.appendChild(actionsRow);

    var previewMount = el("div", {});
    panel.appendChild(previewMount);
    stageBtn.addEventListener("click", function () {
      previewMount.innerHTML = "";
      if (!amountInput.value) {
        previewMount.appendChild(el("p", { style: "color:var(--color-danger);font-size:var(--text-sm);", text: ctx.ui.t("pf.amountRequired") }));
        return;
      }
      var acct = accounts.filter(function (a) { return a.id === acctSelect.value; })[0];
      var card = stagedCard(ctx);
      card.appendChild(el("p", {
        style: "margin-top:var(--space-2);",
        text: ctx.ui.formatCurrency(Number(amountInput.value), ccySelect.value) + " " + ctx.ui.t("common.to") + " " + acct.name
      }));
      card.appendChild(el("p", { style: S.note, text: ctx.ui.t("pf.previewOnlyCashNote") }));
      var confirmBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("pf.confirmSimulated") });
      confirmBtn.addEventListener("click", function () {
        commitCardInPlace(ctx, card, ctx.ui.t("pf.simulatedCashRecordedNote"));
      });
      card.appendChild(confirmBtn);
      previewMount.appendChild(card);
    });
    cancelBtn.addEventListener("click", function () { panel.hidden = true; });

    return panel;
  }

  // -----------------------------------------------------------------------
  // Reconciliation / edit-in-place for an existing holding row.
  // -----------------------------------------------------------------------
  function buildEditRow(ctx, holding, acct, colspan) {
    var tr = el("tr", {});
    var td = el("td", { attrs: { colspan: String(colspan) }, style: "background:var(--color-bg-recessed);" });
    var wrap = el("div", { style: "padding:var(--space-3);" });
    wrap.appendChild(el("p", { style: S.note, text: ctx.ui.tf("pf.editRowNoteTemplate", { id: holding.id }) }));

    var qtyInput = inputEl("number", { value: holding.quantity, attrs: { min: "0", step: "any" } });
    wrap.appendChild(formRow(ctx.ui.t("table.quantity"), qtyInput));
    var avgCostInput = inputEl("number", { value: holding.avgCost === null ? "" : holding.avgCost, attrs: { min: "0", step: "any" } });
    wrap.appendChild(formRow(ctx.ui.t("pf.averageCost"), avgCostInput, { optional: true }));
    var accounts = ctx.data.getAccounts();
    var acctSelect = selectEl(accounts.map(function (a) { return { value: a.id, label: a.name }; }), { value: acct.id });
    wrap.appendChild(formRow(ctx.ui.t("table.account"), acctSelect));

    var saveRow = el("div", { style: "display:flex;gap:var(--space-2);" });
    var saveBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("settings.saveSimulated") });
    var cancelBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("common.cancel") });
    saveRow.appendChild(saveBtn);
    saveRow.appendChild(cancelBtn);
    wrap.appendChild(saveRow);

    var resultMount = el("div", {});
    wrap.appendChild(resultMount);
    saveBtn.addEventListener("click", function () {
      resultMount.innerHTML = "";
      var badgeMount = el("div", {});
      ctx.ui.renderStagedBadge(badgeMount, "STAGED");
      resultMount.appendChild(badgeMount);
      resultMount.appendChild(el("p", {
        style: "margin-top:var(--space-2);",
        text: ctx.ui.tf("pf.reconciliationStagedTemplate", {
          qty: qtyInput.value,
          avgCost: avgCostInput.value || ctx.ui.t("pf.avgCostNotProvidedShort"),
          account: acctSelect.options[acctSelect.selectedIndex].text
        })
      }));
    });
    cancelBtn.addEventListener("click", function () { tr.remove(); });

    td.appendChild(wrap);
    tr.appendChild(td);
    return tr;
  }

  // -----------------------------------------------------------------------
  // Block: header / summary / entry-point actions
  // -----------------------------------------------------------------------
  function statBlock(label, value) {
    var wrap = el("div", {});
    wrap.appendChild(el("div", { style: "font-size:var(--text-xs);color:var(--color-ink-faint);text-transform:uppercase;letter-spacing:.05em;", text: label }));
    wrap.appendChild(el("div", { style: "font-family:var(--font-mono);font-variant-numeric:tabular-nums;font-size:var(--text-lg);font-weight:600;", text: value }));
    return wrap;
  }

  function renderHeaderBlock(ctx) {
    var block = el("div", { className: "block" });
    var header = el("div", { className: "block-header" });
    header.appendChild(el("span", { className: "block-kicker", text: ctx.ui.t("pf.portfolioKicker") }));
    block.appendChild(header);

    var summaryRow = el("div", { style: "display:flex;gap:var(--space-6);flex-wrap:wrap;margin-bottom:var(--space-4);" });
    summaryRow.appendChild(statBlock(ctx.ui.t("ov.totalPortfolioValue"), ctx.ui.formatCurrency(ctx.data.getTotalPortfolioValue(), "USD")));
    summaryRow.appendChild(statBlock(ctx.ui.t("pf.accountsStat"), String(ctx.data.getAccounts().length)));
    summaryRow.appendChild(statBlock(ctx.ui.t("pf.holdings"), String(ctx.data.getHoldings().length)));
    block.appendChild(summaryRow);

    var actionsRow = el("div", { style: "display:flex;gap:var(--space-2);flex-wrap:wrap;" });
    var addPositionBtn = el("button", { attrs: { type: "button" }, style: S.btnPrimary, text: ctx.ui.t("pf.addPositionBtn") });
    var addTxBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("pf.addTransactionBtn") });
    var addAccountBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("pf.addAccountBtn") });
    var importBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("pf.importStatementBtn") });
    importBtn.addEventListener("click", function () { ctx.navigateTo("portfolio/ingest"); });
    actionsRow.appendChild(addPositionBtn);
    actionsRow.appendChild(addTxBtn);
    actionsRow.appendChild(addAccountBtn);
    actionsRow.appendChild(importBtn);
    block.appendChild(actionsRow);

    var formsMount = el("div", {});
    block.appendChild(formsMount);

    addPositionBtn.addEventListener("click", function () {
      formsMount.innerHTML = "";
      formsMount.appendChild(buildPositionForm(ctx));
    });
    addTxBtn.addEventListener("click", function () {
      formsMount.innerHTML = "";
      formsMount.appendChild(buildTransactionForm(ctx));
    });
    addAccountBtn.addEventListener("click", function () {
      formsMount.innerHTML = "";
      formsMount.appendChild(buildAccountForm(ctx));
    });

    return block;
  }

  // -----------------------------------------------------------------------
  // Block: Accounts & Cash
  // HG1 Condition 1C, extended to accounts (round 3: "holdings/account tables" — only
  // Holdings had received this treatment before this pass). Same pattern as
  // HOLDINGS_COLS above: each header states whether its OWN column is numeric so the
  // <th> carries the same right-aligned .num class as the <td>s beneath it, and every
  // account's row — regardless of currency (USD/HKD/CNY), account type, or how many
  // cash balances it holds — renders through the exact same five-cell structure. A
  // USD-only account, an HKD-only account, and a multi-currency account never produce a
  // different number of columns or a different alignment; only the CONTENT of the last
  // cell varies (one amount, several joined by " · ", or the explicit no-data label).
  // -----------------------------------------------------------------------
  // `labelKey` (not a literal label) so a language switch re-resolves the header text at
  // render time (ctx.ui.t(col.labelKey)) rather than baking in whatever language was
  // active when this module-level array was first evaluated.
  var ACCOUNTS_COLS = [
    { labelKey: "table.account", num: false },
    { labelKey: "table.type", num: false },
    { labelKey: "table.market", num: false },
    { labelKey: "table.currency", num: false },
    { labelKey: "table.cashBalances", num: true }
  ];

  function renderAccountsBlock(ctx) {
    var block = el("div", { className: "block" });
    var header = el("div", { className: "block-header" });
    // HG1 Round 5, Phase 2 (S7 — I7/I8's confirmed hardcoded literal) — routed
    // through a real i18n key instead of a bare English string.
    header.appendChild(el("span", { className: "block-kicker", text: ctx.ui.t("pf.accountsAndCash") }));
    block.appendChild(header);

    var table = el("table", { className: "data-table sticky-head" });
    var thead = el("thead", {});
    var headRow = el("tr", {});
    ACCOUNTS_COLS.forEach(function (col) {
      var th = el("th", { text: ctx.ui.t(col.labelKey), className: col.num ? "num" : null });
      th.setAttribute("scope", "col");
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
    var tbody = el("tbody", {});
    var cash = ctx.data.getCashBalances();
    ctx.data.getAccounts().forEach(function (a) {
      var row = el("tr", {});
      row.appendChild(el("td", { text: a.name }));
      // HG1 Round 5, Phase 2 (S7 — PD-0015 §2.3). `a.type` (taxable/retirement/cash) is
      // a human-facing taxonomy value, not canonical identity — previously printed
      // straight from the raw field, "the display string and the grouping key are the
      // same string" by construction. ctx.ui.translateAccountType (js/shell.js)
      // translates the DISPLAY text only; `a.type` itself is untouched.
      row.appendChild(el("td", { text: ctx.ui.translateAccountType(a.type) }));
      // HG1 Round 5, Phase 2 correction pass (Blocker 3) — this cell previously read
      // `a.market` straight from the canonical field with no translation call at all
      // (unlike the account-title line below, which already routes the same field
      // through this same expression). `a.market` is untouched; only the text this
      // cell renders changes. Fixes "GLOBAL" (the one value with no short ISO-style
      // form, and the one the residual scan actually flagged) along with HK/CN/US.
      row.appendChild(el("td", { text: ctx.ui.translateGeographyLabel(a.market === "HK" ? "Hong Kong" : a.market === "CN" ? "Mainland China" : a.market) }));
      row.appendChild(el("td", { text: a.currency }));
      // Every currency's amount goes through the SAME ctx.ui.formatCurrency helper
      // (2 decimal places, currency-code/symbol prefix, per its own shared convention)
      // regardless of which currency it is — a USD row is never rendered to a different
      // precision or a different sign convention than an HKD or CNY row in the same
      // column. An account with no cash on file gets the SAME right-aligned, tabular-
      // numeral cell class (.num), reusing Holdings' own "num-placeholder" convention
      // (short italic label, not a bare em-dash — P5 applied to a raw ledger field, same
      // as the Holdings table's missing-avg-cost cell above) rather than a left-aligned
      // sentence that would break this column's scannable right-aligned rhythm.
      var acctCash = cash.filter(function (c) { return c.accountId === a.id; });
      var cashCell;
      if (acctCash.length) {
        cashCell = el("td", {
          className: "num",
          text: acctCash.map(function (c) { return ctx.ui.formatCurrency(c.amount, c.currency); }).join(" · ")
        });
      } else {
        cashCell = el("td", { className: "num num-placeholder", text: ctx.ui.t("pf.noneOnFile") });
      }
      row.appendChild(cashCell);
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    // HG1 round-4 §20 — controlled horizontal scrolling (scoped to this table, not the
    // whole page) is the chosen narrow-width strategy; see styles/app.css's own comment
    // for the full account of what was considered and not taken.
    var scrollWrap = el("div", { className: "table-scroll-wrap" }, [table]);
    block.appendChild(scrollWrap);

    // HG1 Round 5, Phase 2 — same defect class as I6 (a first-person worker reference
    // rendered into product UI text), found here while working nearby; reworded to
    // state the real, still-open gap without the self-reference.
    var note = el("p", { style: S.note, text: ctx.ui.t("pf.cashNativeCurrencyNote") });
    block.appendChild(note);

    var addCashBtn = el("button", { attrs: { type: "button" }, style: S.btnSecondary, text: ctx.ui.t("pf.addCashBalanceBtn") });
    block.appendChild(el("div", { style: "margin-top:var(--space-3);" }, [addCashBtn]));
    var cashFormMount = el("div", {});
    block.appendChild(cashFormMount);
    addCashBtn.addEventListener("click", function () {
      cashFormMount.innerHTML = "";
      cashFormMount.appendChild(buildCashForm(ctx));
    });

    return block;
  }

  // -----------------------------------------------------------------------
  // Block: Holdings (complete view, grouped by account)
  // -----------------------------------------------------------------------
  var LISTING_MARKET_TO_FRESHNESS_AXIS = { US: "us_equity", HK: "hk_equity", CN: "cn_equity" };
  // HG1 Condition 1C — strict column grid. Each header now says whether ITS OWN column
  // is numeric (num: true), so the <th> can carry the same right-aligned .num class as
  // the <td> cells beneath it. Previously every header was left-aligned regardless of
  // its column's data alignment, so a right-aligned number sat under a left-aligned
  // label — exactly "numbers do not always align cleanly under their intended columns."
  // Freshness/Actions are pills/buttons, not numerals — left-aligned is correct for them.
  // Fix (post-Checkpoint-A round-3 review, second follow-up): each account's Holdings
  // table is a SEPARATE <table> element, and the browser's default (auto) table-layout
  // sizes a table's columns from ITS OWN content only — one account's "Security" column
  // has no knowledge of another account's longest security name, so four independently
  // laid-out tables resolved to four slightly different track widths (a measured 17px
  // spread on the G/L column's right edge alone), even after every column inside each
  // individual table aligned perfectly. `width` here (percentages summing to 100) is
  // consumed by a shared `<colgroup>` (built once per table, see holdingsColgroup()
  // below) together with `table-layout: fixed` (styles/app.css's
  // `.holdings-ledger-table`, scoped to ONLY these per-account ledger tables — not
  // Accounts & Cash or Transactions, which are single tables with a different column
  // count and never had this cross-table problem) — this makes every account's table
  // resolve to the SAME track widths regardless of its own content, closing the gap
  // between "each table is internally a strict grid" (already fixed) and "the tables
  // form one strict grid together" (this fix).
  // Rebalance (post-Checkpoint-A round-3 review, third follow-up): the widths above,
  // as originally chosen, gave Freshness only 10% — real-browser measurement found this
  // 95px column 27px too narrow for its own pill (114px) plus the ~8px/side cell
  // padding a fixed-width column no longer waives, so the pill visibly spilled into the
  // Actions column (overflow was `visible`, so nothing was clipped or hidden — no P10
  // breach — but two columns visually overlapped, which is a worse defect than the
  // cross-table variance this whole colgroup exists to remove).
  //
  // Freshness now gets +3.5 points (10 -> 13.5, ~128px at this table's ~950px measured
  // width — at/above the 122-125px the real pill needed, with a few px of margin this
  // time rather than an exact fit). Donors were chosen by CHECKING THIS BUILD'S OWN
  // DATA (js/data.js's HOLDINGS/FX_RATES), not by assuming "numeric = safe to shrink":
  //   - Qty -1 (7 -> 6): every quantity in this dataset is <= 4 digits ("2000"); a
  //     6%-wide column has clear, checked slack over that worst case.
  //   - Market Value (USD) -2.5 (13 -> 10.5): the largest of all 13 holdings' computed
  //     marketValueUSD is VOO's $43,545.50 (10 characters, "$43,545.50") — always USD,
  //     so never carries a currency-code prefix; a 10.5%-wide column still has clear
  //     margin over that specific, checked worst case.
  // Avg Cost, Price, and % of Portfolio were deliberately NOT touched, even though they
  // are also short/right-aligned and were named as candidates: their own worst-case
  // values include a currency-code prefix for non-USD holdings (e.g. "CNY 1,542.00" for
  // Price on 600519.SS) that already run closer to their column's width than Qty or
  // Market Value do, so shrinking them further was judged the higher-risk move; Security
  // was checked against its own longest value ("iShares 20+ Year Treasury Bond ETF") and
  // left untouched because it wraps onto a second line by design (no `nowrap`) rather
  // than forcing a single unbroken run past its column, so it was never actually at risk
  // of the hard `scrollWidth > clientWidth` failure this fix is being judged against.
  // Unrealized G/L was left untouched (at that time) because it was the column already
  // independently browser-verified correct in the prior follow-up.
  //
  // Second rebalance (post-Checkpoint-A round-3 review, fourth follow-up): real-browser
  // measurement found the above still 4 cells short of clean (down from 14), both by a
  // WORST-CASE SELECTION error, not an arithmetic one:
  //   - Freshness (13.5%, ~128px) was sized against the two HEALTHY-state pills this
  //     dataset happens to render most often ("US equity · Live" 122px, "HK equity ·
  //     EOD" 125px). The real worst case is "CN A-share · Stale" at 140px — the ONLY
  //     stale axis, and the longest label, because a degraded state adds words
  //     ("· Stale") a healthy one doesn't need. LESSON, worth keeping for the next
  //     person to size a column like this: in a cross-border, multi-freshness-axis
  //     product, the widest value in a freshness/state column will tend to be the
  //     DEGRADED case, not the healthy one — size against the worst state actually
  //     present in the data, never against whichever value happens to be most common.
  //   - Unrealized G/L (12%, ~114px) was sized against a plain directional numeral
  //     ("▲ +56.2%" and similar); it was never checked against this column's OWN worst
  //     case, the INSUFFICIENT_DATA row (Kweichow Moutai, 600519.SS), whose cell
  //     carries the "insufficient data" label plus its reason text — a wider unit than
  //     any plain numeral in the column, by construction (D3.2's own rule: this state
  //     renders a labeled component, not a number).
  // Both widened against their REAL worst case (140px, 138px respectively) with a
  // deliberate margin this time, not an exact fit — the last two rounds each landed
  // uncomfortably close to their target and one still missed, so "measures clean with
  // margin" is now preferred over "measures clean at the boundary." Both are widened by
  // taking the width from Security (22 -> 15.5): established twice already as the one
  // column structurally immune to this failure (it wraps by design, no `nowrap`
  // anywhere on that cell), so it is the correct donor regardless of how much either
  // of the other two still needs. Qty, Avg Cost, Price, Market Value, and % of
  // Portfolio are all untouched from the prior rebalance — none of them were reported
  // as still short, and re-touching an already-verified-sufficient column risks
  // reopening a defect that is not actually present.
  // `labelKey` added (HG1 round-4, §12) so a language switch re-resolves each header at
  // render time via ctx.ui.t(col.labelKey) — the `width` percentages below were sized
  // against this build's own English worst-case values (CONTRACT.md/CHANGELOG's own
  // multi-round account of exactly how) and are UNCHANGED by this addition; see this
  // designer's handoff for the explicit flag that Chinese header/cell text changes the
  // worst case those widths were sized against, and has not been re-verified in a
  // browser (§12.2's own warning, stated precisely rather than silently assumed safe).
  var HOLDINGS_COLS = [
    { labelKey: "table.security", num: false, width: 15.5 },
    { labelKey: "table.qty", num: true, width: 6 },
    { labelKey: "table.avgCost", num: true, width: 10 },
    { labelKey: "table.price", num: true, width: 9 },
    { labelKey: "table.marketValueUsd", num: true, width: 10.5 },
    { labelKey: "table.pctPortfolio", num: true, width: 9 },
    { labelKey: "table.unrealizedGl", num: true, width: 16 },
    { labelKey: "table.freshness", num: false, width: 16 },
    { labelKey: "table.actions", num: false, width: 8 }
  ];

  function holdingsColgroup() {
    return el("colgroup", {}, HOLDINGS_COLS.map(function (col) {
      return el("col", { style: "width:" + col.width + "%;" });
    }));
  }

  // Fix (post-Checkpoint-A round-3 review): Unrealized G/L is the one HOLDINGS_COLS
  // column whose cell is built from a CLAIM (via ctx.ui.renderMetricValue — the
  // directional ▲/▼ glyph + numeral path, HG1 Condition 2) rather than a plain
  // formatted string. Every other numeric cell in this table is constructed with its
  // own `el("td", { className: "num" })`; this one was built as a bare `el("td", {})`
  // with renderMetricValue filling it afterward, so it had no class at all — text-align
  // defaulted to `start` and font-variant-numeric to `normal` at the cell level, while
  // its own header still (correctly) carried `.num`. `renderMetricValue` itself (js/
  // shell.js) has no opinion about right-alignment — it is reused in many non-tabular
  // contexts (metric-strip cells, claim cards) where forcing right-align would be
  // wrong, so the fix belongs at THIS table's cell-construction step, not inside the
  // shared renderer. Centralizing it here — rather than repeating
  // `el("td", { className: "num" })` by hand at the one call site — is what actually
  // prevents recurrence: any future claim-rendered numeric column added to this ledger
  // should be built through this helper, not by hand.
  //
  // The glyph and the numeral do NOT need to be visually separated to stay in a
  // strict right-aligned track: renderMetricValue's own wrap (`.metric-unit`, an
  // inline-flex box with the glyph first and the numeral last) is a single inline unit
  // positioned by the <td>'s own text-align — so the numeral, being the trailing
  // child, still lands flush against the column's right edge regardless of the
  // glyph's width, exactly like every other right-aligned numeric cell in this table.
  function claimNumCell(ctx, claim) {
    var cell = el("td", { className: "num" });
    ctx.ui.renderMetricValue(cell, claim);
    return cell;
  }

  function renderHoldingsBlock(ctx) {
    var block = el("div", { className: "block" });
    var header = el("div", { className: "block-header" });
    header.appendChild(el("span", { className: "block-kicker", text: ctx.ui.t("pf.holdings") }));
    header.appendChild(el("span", { style: S.note, text: ctx.ui.t("pf.holdingsHint") }));
    block.appendChild(header);

    // HG1 round-4 §16 — portfolio-scale interaction strategy for a real (larger) V1
    // portfolio, not just described but built: a real, working search filter across
    // every account's holdings by security name or ticker. Sort, pagination/
    // virtualization, and collapsible account sections are the recommended NEXT steps at
    // real V1 scale (hundreds of holdings) — deliberately NOT built here (a 13-row demo
    // does not need them, and building them against a 13-row fixture risks a UI that
    // LOOKS solved without being checked against the case it exists for); named
    // explicitly, not silently deferred, in this designer's handoff.
    var searchWrap = el("div", { style: "margin-bottom:var(--space-3);max-width:340px;" });
    var searchInput = inputEl("search", { placeholder: ctx.ui.t("pf.searchHoldingsPlaceholder") });
    searchWrap.appendChild(searchInput);
    block.appendChild(searchWrap);

    var resultsMount = el("div", {});
    block.appendChild(resultsMount);

    var accounts = ctx.data.getAccounts();
    var holdings = ctx.data.getHoldings();
    var cash = ctx.data.getCashBalances();
    var freshness = ctx.data.getFreshness();
    var axisByKey = {};
    freshness.axes.forEach(function (a) { axisByKey[a.axis] = a; });

    function matchesQuery(h, q) {
      if (!q) return true;
      q = q.toLowerCase();
      return h.name.toLowerCase().indexOf(q) >= 0 || h.id.toLowerCase().indexOf(q) >= 0;
    }

    function renderAll(query) {
      resultsMount.innerHTML = "";
      var anyRendered = false;
      accounts.forEach(function (acct) {
        var acctHoldings = holdings.filter(function (h) { return h.accountId === acct.id && matchesQuery(h, query); });
        var acctCash = cash.filter(function (c) { return c.accountId === acct.id; });
        // An account with cash but no matching holding still renders (its cash summary
        // line, no ledger table) when a search is active — cash has no name/ticker to
        // match, so hiding a cash-only account whenever ANY search text is typed would
        // make the account itself appear to vanish, a structural surprise a filter
        // should never introduce. It is hidden only when it has neither a matching
        // holding nor any cash at all (same rule as with no query active).
        if (acctHoldings.length === 0 && acctCash.length === 0) return;
        anyRendered = true;

      var acctWrap = el("div", { style: "margin-bottom:var(--space-5);" });
      var acctTitle = el("div", { style: "display:flex;align-items:baseline;justify-content:space-between;gap:var(--space-3);margin-bottom:var(--space-2);flex-wrap:wrap;" });
      acctTitle.appendChild(el("strong", { text: acct.name }));
      // HG1 Round 5, Phase 2 (S7 — PD-0015 §2.3) — same account-type display-label fix
      // as renderAccountsBlock above.
      acctTitle.appendChild(el("span", { style: S.note, text: ctx.ui.translateAccountType(acct.type) + " · " + ctx.ui.translateGeographyLabel(acct.market === "HK" ? "Hong Kong" : acct.market === "CN" ? "Mainland China" : acct.market) + " · " + acct.currency }));
      acctWrap.appendChild(acctTitle);

      if (acctHoldings.length > 0) {
        var table = el("table", { className: "data-table holdings-ledger-table sticky-head" });
        table.appendChild(holdingsColgroup());
        var thead = el("thead", {});
        var headRow = el("tr", {});
        HOLDINGS_COLS.forEach(function (col) {
          var th = el("th", { text: ctx.ui.t(col.labelKey), className: col.num ? "num" : null });
          th.setAttribute("scope", "col");
          headRow.appendChild(th);
        });
        thead.appendChild(headRow);
        table.appendChild(thead);
        var tbody = el("tbody", {});

        acctHoldings.forEach(function (h) {
          var row = el("tr", { style: "cursor:pointer;" });

          var secCell = el("td", {});
          secCell.appendChild(el("div", { text: h.id }));
          // HG1 ux_planning revision (review-06, B2) — ctx.ui.holdingDisplayName(h)
          // resolves to the same Chinese name Scenario Lab's prose and Overview's
          // major-holdings block now use, instead of the raw (always-English) h.name.
          // h.id (canonical ticker, e.g. "9988.HK") is rendered on its own line
          // immediately above this one, unchanged, so a shortened display name here is
          // never ambiguous about which specific listing this row is.
          secCell.appendChild(el("div", { style: S.note, text: ctx.ui.holdingDisplayName(h) + " · " + ctx.ui.tf("pf.listingSuffix", { market: h.listingMarket }) }));
          if (h.analyticsSupport === "UNSUPPORTED_ASSET") {
            secCell.appendChild(el("div", { className: "text-faint", style: "font-size:11px;", text: ctx.ui.t("pf.riskAnalyticsUnsupported") }));
          }
          row.appendChild(secCell);

          row.appendChild(el("td", { className: "num", text: String(h.quantity) }));
          // HG1 Condition 1C — a missing avg-cost previously rendered as a full sentence
          // ("Not provided (in-kind transfer)") jammed right-aligned into a numeric/mono
          // column, breaking the column's scannable rhythm. Now a short right-aligned
          // placeholder (own class, deliberately NOT .metric-insufficient-label — this is
          // a raw ledger field with no claim object behind it, not a D3.2 sufficiency
          // state) carries the full explanation as a title attribute instead.
          var avgCostCell = h.avgCost === null
            ? el("td", { className: "num num-placeholder", text: ctx.ui.t("pf.notProvided") })
            : el("td", { className: "num", text: ctx.ui.formatCurrency(h.avgCost, h.currency) });
          if (h.avgCost === null) avgCostCell.title = ctx.ui.t("pf.inKindTransferTitle");
          row.appendChild(avgCostCell);
          row.appendChild(el("td", { className: "num", text: ctx.ui.formatCurrency(h.price, h.currency) }));
          row.appendChild(el("td", { className: "num", text: ctx.ui.formatCurrency(h.marketValueUSD, "USD") }));
          row.appendChild(el("td", { className: "num", text: ctx.ui.formatPercent(h.pctOfPortfolio) }));

          row.appendChild(claimNumCell(ctx, ctx.data.getHoldingClaim(h.id)));

          var freshCell = el("td", {});
          var axisKey = LISTING_MARKET_TO_FRESHNESS_AXIS[h.listingMarket];
          var axis = axisKey ? axisByKey[axisKey] : null;
          if (axis) ctx.ui.renderFreshnessPill(freshCell, axis);
          row.appendChild(freshCell);

          var actionsCell = el("td", {});
          var editBtn = el("button", { attrs: { type: "button" }, className: "evidence-control evidence-control-sm", text: ctx.ui.t("common.edit") });
          actionsCell.appendChild(editBtn);
          row.appendChild(actionsCell);

          row.addEventListener("click", function () {
            ctx.ui.inspector.focus({
              // HG1 ux_planning revision (review-06, B2) — same shared display-name
              // lookup as the ledger row above, for the same holding's inspector title.
              title: h.id + " — " + ctx.ui.holdingDisplayName(h),
              render: function (mount) {
                mount.appendChild(el("p", { style: S.note, text: ctx.ui.tf("pf.holdingInspectorDetail", { account: acct.name, listing: h.listingMarket, geo: ctx.ui.translateGeographyLabel(h.economicGeography) }) }));
                var claimMount = el("div", {});
                mount.appendChild(claimMount);
                // HG1 ux_planning revision (review-07, P0 item 1) — this claim's own
                // `label` field is built in js/data.js as `h.name + " — Unrealized
                // Gain/Loss"`, baked from the raw (always-English) holding name at
                // module load, never through ctx.ui.holdingDisplayName. Rendered without
                // showLabel:false, it put the raw-English name ~40px directly below this
                // same drawer's own title (line above, already localized via
                // holdingDisplayName), e.g. "Tencent Holdings — Unrealized Gain/Loss"
                // sitting right under "0700.HK — 腾讯控股" in zh mode. Same established
                // pattern as Overview's Currency Exposure/Listing-Market/Asset-Class/
                // Concentration blocks (js/surfaces/overview.js): when an adjacent
                // heading already names the same thing, suppress the claim's own
                // internal label rather than derive a second, independently-sourced
                // name string here (which would reintroduce exactly the two-sources-for-
                // one-name defect this round's regression test now guards against).
                ctx.ui.renderClaim(claimMount, ctx.data.getHoldingClaim(h.id), { depth: "simple", showLabel: false });
                if (h.analyticsSupport === "UNSUPPORTED_ASSET") {
                  var riskClaim = ctx.data.getInstrumentRiskClaim(h.id);
                  if (riskClaim) {
                    var riskMount = el("div", { style: "margin-top:var(--space-3);" });
                    mount.appendChild(riskMount);
                    ctx.ui.renderClaim(riskMount, riskClaim, { depth: "simple" });
                  }
                }
              }
            });
          });

          editBtn.addEventListener("click", function (evt) {
            evt.stopPropagation();
            if (row.nextSibling && row.nextSibling._editRowFor === h.id) { row.nextSibling.remove(); return; }
            var existingEdit = tbody.querySelector("tr[data-edit-open]");
            if (existingEdit) existingEdit.remove();
            var editRow = buildEditRow(ctx, h, acct, HOLDINGS_COLS.length);
            editRow._editRowFor = h.id;
            editRow.setAttribute("data-edit-open", "true");
            row.parentNode.insertBefore(editRow, row.nextSibling);
          });

          tbody.appendChild(row);
        });
        table.appendChild(tbody);
        // HG1 round-4 §20 — controlled horizontal scrolling scoped to this table, not
        // the whole page; see styles/app.css's own comment for the full account.
        acctWrap.appendChild(el("div", { className: "table-scroll-wrap" }, [table]));
      }

      if (acctCash.length > 0) {
        var cashNote = el("div", { style: "margin-top:var(--space-2);font-size:var(--text-sm);" });
        cashNote.appendChild(el("span", { style: "font-weight:600;", text: ctx.ui.t("pf.cashLabel") }));
        cashNote.appendChild(document.createTextNode(acctCash.map(function (c) { return ctx.ui.formatCurrency(c.amount, c.currency); }).join(" · ")));
        acctWrap.appendChild(cashNote);
      }

        resultsMount.appendChild(acctWrap);
      });
      if (query && !anyRendered) {
        resultsMount.appendChild(el("p", { className: "text-faint", text: ctx.ui.tf("pf.noHoldingsMatch", { query: query }) }));
      }
    }

    searchInput.addEventListener("input", function () { renderAll(searchInput.value.trim()); });
    renderAll("");

    return block;
  }

  // HG1 ux_planning revision (review-06, B4) — the Transactions table previously had
  // no `<colgroup>` and relied on the browser's plain `auto` table-layout. Auto-layout
  // shrinks a column toward its MIN-CONTENT width when the row's combined preferred
  // widths exceed the table's own width, and CJK text (no spaces, so a line can break
  // between ANY two characters) has a min-content width of a single glyph — far
  // smaller than an English word's own unbreakable min-content. At `?lang=zh-CN`, the
  // long free-text Note/Reporting-Currency-Conversion columns' own preferred widths
  // dominated that shrink, so short enumerable columns (类型/类型 values, and Quantity's
  // 不适用 placeholder) were squeezed down to a single glyph per line — exactly the
  // "类/型", "存/款", "不适/用" defect, and independent of English column sizing at all
  // (this is the SAME root cause `.holdings-ledger-table` (above) already fixed for a
  // different symptom — cross-table column drift). `table-layout: fixed` plus an
  // explicit percentage colgroup (below) gives every column a guaranteed share of the
  // table's own 100%-of-card width regardless of any one column's content, which is
  // also the direct fix for "ample horizontal space is unused at 1512px": auto-layout's
  // shrink algorithm was consuming that width asymmetrically instead of the table
  // simply using all of it. Percentages sized against this build's own worst-case
  // values in BOTH languages (js/data.js's TRANSACTIONS, js/shell.js's
  // TRANSACTION_TYPE_LABEL_ZH/TRANSACTION_NOTE_ZH) — not measured in a live browser
  // (no browser tool this round; see this designer's report). Type/Instrument/Currency
  // additionally get `white-space: nowrap` on both header and cell (below) as
  // defense-in-depth: even if a future content change narrows their fixed share, they
  // overflow visibly rather than silently stacking one glyph per line again. Scoped to
  // `.transactions-ledger-table` only, matching `.holdings-ledger-table`'s own
  // precedent — Accounts & Cash is untouched (different column count, never reported
  // this defect).
  var TRANSACTIONS_COLS = [
    { labelKey: "table.date", num: false, width: 8, nowrap: true },
    { labelKey: "table.txType", num: false, width: 7, nowrap: true },
    { labelKey: "table.account", num: false, width: 15 },
    { labelKey: "table.instrument", num: false, width: 9, nowrap: true },
    { labelKey: "table.quantity", num: true, width: 7 },
    { labelKey: "table.priceAmount", num: true, width: 11 },
    { labelKey: "table.currency", num: false, width: 7, nowrap: true },
    { labelKey: "table.reportingConversion", num: false, width: 14 },
    { labelKey: "table.note", num: false, width: 22 }
  ];

  function transactionsColgroup() {
    return el("colgroup", {}, TRANSACTIONS_COLS.map(function (col) {
      return el("col", { style: "width:" + col.width + "%;" });
    }));
  }

  // -----------------------------------------------------------------------
  // Block: Transactions & Activity (owner: "Transactions contained within Portfolio")
  // -----------------------------------------------------------------------
  function renderTransactionsBlock(ctx) {
    var block = el("div", { className: "block" });
    var header = el("div", { className: "block-header" });
    header.appendChild(el("span", { className: "block-kicker", text: ctx.ui.t("pf.transactionsActivity") }));
    block.appendChild(header);

    var accounts = ctx.data.getAccounts();
    var allTx = ctx.data.getTransactions();
    var types = uniqueValues(allTx, function (t) { return t.type; });

    var filterRow = el("div", { style: "display:flex;gap:var(--space-4);flex-wrap:wrap;" });
    var acctFilter = selectEl([{ value: "", label: ctx.ui.t("pf.allAccounts") }].concat(accounts.map(function (a) { return { value: a.id, label: a.name }; })));
    // HG1 Round 5, Phase 2 correction pass (Blocker 3) — `value` stays each raw
    // canonical type string (what filtering keys on, via ctx.data.getTransactions'
    // own `type` param below); only the option `label` is translated.
    var typeFilter = selectEl([{ value: "", label: ctx.ui.t("pf.allTypes") }].concat(types.map(function (t) { return { value: t, label: ctx.ui.translateTransactionType(t) }; })));
    filterRow.appendChild(formRow(ctx.ui.t("table.account"), acctFilter));
    filterRow.appendChild(formRow(ctx.ui.t("table.type"), typeFilter));
    block.appendChild(filterRow);

    var tableMount = el("div", {});
    block.appendChild(tableMount);

    function renderTable() {
      tableMount.innerHTML = "";
      var filtered = ctx.data.getTransactions({
        accountId: acctFilter.value || undefined,
        type: typeFilter.value || undefined
      });
      var table = el("table", { className: "data-table sticky-head transactions-ledger-table" });
      table.appendChild(transactionsColgroup());
      var thead = el("thead", {});
      var headRow = el("tr", {});
      // HG1 Condition 1C — Quantity/Price-Amount headers marked numeric so they align
      // over their own right-aligned .num data cells, same fix as the Holdings table.
      // HG1 ux_planning revision (B4) — now reads TRANSACTIONS_COLS (above) so the
      // header's own `nowrap` flag stays a single source with the colgroup widths,
      // rather than a second, separately-typed literal list of the same nine columns.
      TRANSACTIONS_COLS.forEach(function (col) {
        var th = el("th", {
          text: ctx.ui.t(col.labelKey),
          className: col.num ? "num" : null,
          style: col.nowrap ? "white-space:nowrap;" : null
        });
        th.setAttribute("scope", "col");
        headRow.appendChild(th);
      });
      thead.appendChild(headRow);
      table.appendChild(thead);
      var tbody = el("tbody", {});

      filtered.slice().reverse().forEach(function (t) {
        var acct = accounts.filter(function (a) { return a.id === t.accountId; })[0];
        var row = el("tr", {});
        row.appendChild(el("td", { text: t.date, style: "white-space:nowrap;" }));
        // HG1 Round 5, Phase 2 correction pass (Blocker 3) — `t.type` (js/data.js's
        // canonical TRANSACTIONS[].type) is untouched; only this cell's rendered text
        // is translated, via the same TRANSACTION_TYPE_LABEL_ZH map the form's own
        // type-select and this block's own type filter (above) now use — one source
        // for the label, not three independently-typed ones.
        // HG1 ux_planning revision (B4) — `white-space:nowrap` so a short zh value
        // (存款/股息/转入, 2 characters) never breaks one character per line; the
        // colgroup above already gives this column enough width for its own worst
        // case, this is defense-in-depth against a future content change.
        row.appendChild(el("td", { text: ctx.ui.translateTransactionType(t.type), style: "white-space:nowrap;" }));
        row.appendChild(el("td", { text: acct ? acct.name : t.accountId }));
        row.appendChild(el("td", { text: t.instrumentId || ctx.ui.t("common.na"), style: "white-space:nowrap;" }));
        row.appendChild(el("td", { className: "num", text: (t.quantity !== undefined && t.quantity !== null) ? String(t.quantity) : ctx.ui.t("common.na") }));

        var priceOrAmount;
        if (t.price !== undefined && t.price !== null) priceOrAmount = ctx.ui.formatCurrency(t.price, t.currency);
        else if (t.amount !== undefined && t.amount !== null) priceOrAmount = ctx.ui.formatCurrency(t.amount, t.currency);
        else priceOrAmount = ctx.ui.t("common.na");
        row.appendChild(el("td", { className: "num", text: priceOrAmount }));

        var ccyText = t.currency || (t.toCurrency ? (t.fromCurrency + " → " + t.toCurrency) : ctx.ui.t("common.na"));
        row.appendChild(el("td", { text: ccyText, style: "white-space:nowrap;" }));

        var convCell = el("td", {});
        var fxClaim = ctx.data.getTransactionFxClaim(t.id);
        if (fxClaim) {
          var claimValMount = el("div", {});
          convCell.appendChild(claimValMount);
          ctx.ui.renderMetricValue(claimValMount, fxClaim);
          var evBtn = el("button", { attrs: { type: "button" }, className: "evidence-control evidence-control-sm", style: "margin-top:4px;", text: ctx.ui.t("common.evidence") });
          evBtn.addEventListener("click", function () { ctx.ui.openEvidence(fxClaim.id); });
          convCell.appendChild(evBtn);
        } else {
          convCell.appendChild(el("span", { className: "text-faint", text: ctx.ui.t("pf.noConversionClaimNote") }));
        }
        row.appendChild(convCell);

        // HG1 Round 5 micro-pass (Item 3) — `t.note` is application-authored
        // ledger narrative (e.g. "Wire funding," "In-kind transfer from a legacy
        // custodian...") describing what the transaction WAS, not the user's own
        // uploaded file content — a genuine UI-text gap, not a canonical
        // exemption. See js/shell.js's translateTransactionNote and its own
        // comment for why this is a translation map, not an allowlist entry.
        row.appendChild(el("td", { style: S.note, text: ctx.ui.translateTransactionNote(t.note) || "" }));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      // HG1 round-4 §20 — controlled horizontal scrolling scoped to this table.
      tableMount.appendChild(el("div", { className: "table-scroll-wrap" }, [table]));
    }

    acctFilter.addEventListener("change", renderTable);
    typeFilter.addEventListener("change", renderTable);
    renderTable();

    return block;
  }

  // -----------------------------------------------------------------------
  // Registration
  // -----------------------------------------------------------------------
  window.APP.registerSurface("portfolio", {
    group: "portfolio",
    render: function (mountEl, ctx) {
      mountEl.innerHTML = "";
      var root = el("div", {});
      root.appendChild(renderHeaderBlock(ctx));
      root.appendChild(renderAccountsBlock(ctx));
      root.appendChild(renderHoldingsBlock(ctx));
      root.appendChild(renderTransactionsBlock(ctx));
      mountEl.appendChild(root);
    }
  });
})();
