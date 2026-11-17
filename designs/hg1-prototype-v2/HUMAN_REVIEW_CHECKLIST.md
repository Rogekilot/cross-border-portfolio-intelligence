# HG1 revision-2 prototype — guided human review checklist

Modeled on `reviews/gates/HG1_PROTOTYPE_INSPECTION.md`'s guided-inspection style, which
the owner has used before. Serve the prototype first — see `README.md`, "Running it."

Work down each list. Every item names **what to click** and **what decision you are
being asked to make** — the point is not whether it looks nice, but whether the design
underneath is one you want. Where a control is simulated rather than fully wired, that is
named plainly (see `SIMULATED_VS_IMPLEMENTED.md` for the complete, unflattering account) —
judge the *design* of the interaction regardless of what currently persists.

---

## Part A — the owner's eleven judging criteria (§2 item 10)

### 1. Does Overview provide strong portfolio understanding on first use?

Go to **`#/overview`**. Read top to bottom without clicking anything first.
*Judge:* in one screen, without navigating, can you answer "how am I doing, why, what's
driving it, what are my main risks, what deserves attention" — the four/five questions
§26 fixes? Note the stat strip (total value, gain/loss) at the very top, the hero
portfolio-vs-benchmark chart with its period selector, the asset-mix donut, the risk
stat strip, the top insights, and the Portfolio Brief at the bottom.

### 2. Does navigation feel substantially simpler?

Look at the header. *Judge:* four primary tabs (Overview / Portfolio / Analytics /
Scenario Lab), no dedicated AI tab, no dedicated Insights tab, no dedicated Evidence
tab. Click into **Portfolio** and note the secondary tab strip (Holdings & Activity /
Import & Ingestion) — *judge:* does folding Import under Portfolio, and Transactions
inside Holdings & Activity, feel like a reduction, or does it hide something you'd
rather see at the top level?

### 3. Does analytical depth remain comprehensive?

Go to **`#/analytics`**. *Judge:* scroll the whole page once. Performance (hero chart +
FX/local split), a full risk-and-return metric grid (volatility, beta, alpha, Sharpe,
Sortino, max drawdown, tracking error, VaR), rolling volatility + drawdown charts,
SML/CAPM scatter, exposure (listing market, economic geography, asset class, sector,
currency, concentration), correlation matrix, contribution to risk. Does this read as
the "real breadth of V1" the owner asked for, or as several KPI cards with a chart
attached?

### 4. Do visualizations materially improve comprehension?

On the same Analytics page, click a **correlation cell / point on the SML scatter /
a metric cell** to open the focus-and-inspect dock on the right. *Judge:* for each chart
type present (line-compare, drawdown, rolling line, donut, bar, stacked bar, scatter,
heatmap) — does the visual form show something a sentence or a bare number could not
(a trend, a spatial position relative to a line, two overlapping contributions to one
number, relative proportion across many segments)? Or does any of them feel decorative?

### 5. Does Portfolio feel capable of handling real ingestion and reconciliation?

Go to **`#/portfolio/portfolio`**. Click **"+ Add Position,"** **"+ Add Transaction,"**
**"+ Add Account,"** **"+ Add Cash Balance,"** and a Holdings row's **"Edit"** button.
*Judge the design of each form and its staged/confirm flow* — not whether it persists
(it does not; see `SIMULATED_VS_IMPLEMENTED.md`). Then search for **"TSMC"** in any of
the security-resolution fields and confirm you are forced to choose between two
candidates rather than have one silently guessed.

### 6. Is OCR trustworthy and human-controlled?

Go to **`#/portfolio/ingest`**, click **"OCR-Assisted Ingestion."** Read the seven-step
workflow strip (Upload → Extract → Resolve → Stage → Review → Confirm → Commit). Open
each of the three documents and find: a high-confidence field, a low-confidence field, an
ambiguous-security match (with two named candidates, never auto-picked), a missing field
(never auto-filled), a possible-duplicate flag, a correction record, and a final human
confirmation record. Try clicking **"Confirm & Commit"** on the first document before
resolving every flagged field. *Judge:* is it structurally impossible to reach "Commit"
with an unresolved field? Does every field visibly carry a `STAGED` badge until you
commit?

### 7. Does progressive disclosure successfully reduce persistent text?

On **Overview**, note how much is a `<details>` disclosure (closed by default) versus
permanently visible — "Holdings detail," "Show entire portfolio," "See sector/market/
currency breakdown," "Explain these risk statistics in full," "See all insights." On any
claim card, click through **Quick → Simple → Investor → Professional**. *Judge:* does
the default view stay calm, and does going deeper feel like a deliberate choice rather
than something forced on you?

### 8. Is evidence discoverable without dominating the interface?

Click any **"Evidence & Methodology"** button (Overview's total value or gain/loss cells,
any Analytics metric cell via the focus dock, any Scenario Lab comparison row, any AI
answer's cited-figure chip). *Judge:* the visual conclusion → key number → explanation →
evidence → methodology path — is it one click away everywhere, and is it closed by
default everywhere? Then open the footer's **"Methodology & Evidence Registry"** link and
expand a few entries — *judge* the mix of fully-populated and "not yet published"
entries (five metrics are populated; the rest are the honest empty state, AC-17 — this is
demonstrating a real product state, not a placeholder).

### 9. Does AI feel useful without taking control of deterministic facts?

Open the AI panel from the header **"Ask your portfolio"** button, then from a specific
chart's **"Ask about this…"** affordance. Read a response and find a highlighted figure
(a chip); click it — *judge:* does it open the same Evidence overlay as everywhere else,
proving the number traces back to a real claim rather than being typed by the AI? Note
that responses are a fixed set of templates, not free-text Q&A (see
`SIMULATED_VS_IMPLEMENTED.md`) — *judge the interaction design*, not the current answer
coverage.

### 10. Is Scenario Lab clearly isolated?

Go to **`#/scenario`**. *Judge:* the legend at the top (ACTUAL vs. SCENARIO badges,
explained in plain language) and every comparison row below it — does every single row,
not just the page as a whole, carry its own unmistakable badge? Switch between the three
scenarios. Then return to **Overview** and **Portfolio** and confirm no scenario number
appears anywhere on either page.

### 11. Does the interface feel like a premium financial-intelligence product rather than an internal compliance console?

This is a judgment across every screen, not one control. Look at the type (serif
headings, tabular-mono numerals), the warm cream/forest-green/gold palette, the card
language, and the denser "Analyst Desk" treatment specifically on Analytics and inside
the focus-and-inspect dock. *Judge:* does the visual register hold up under the density
Analytics and Scenario Lab both require, or does it start to look like a spreadsheet
somewhere?

---

## Part B — the thirteen required experiences (§2 item 9), traced to their route

| # | Experience | Route / control | Notes |
|---|---|---|---|
| 1 | Portfolio Overview | `#/overview` | Primary tab, direct. |
| 2 | Holdings exploration | `#/portfolio/portfolio`, "Holdings" block; click a row to inspect, "Edit" to reconcile | |
| 3 | Manual portfolio entry | `#/portfolio/portfolio`, "+ Add Position" | Simulated persistence — see `SIMULATED_VS_IMPLEMENTED.md`. |
| 4 | Transaction entry | `#/portfolio/portfolio`, "+ Add Transaction" | Simulated persistence. |
| 5 | CSV/import workflow | `#/portfolio/ingest`, "CSV Import" toggle | Fixed fixture data; resolution UI is real, commit is simulated. |
| 6 | OCR ingestion/review flow | `#/portfolio/ingest`, "OCR-Assisted Ingestion" toggle | All seven required states present (see item 6 above); commit is simulated. |
| 7 | Exposure exploration | `#/analytics`, "Exposure" block (also a top-level summary on Overview, Block B) | |
| 8 | Risk/performance analytics | `#/analytics`, "Risk & Return Profile" + "Rolling Analytics & Drawdown" blocks | |
| 9 | Benchmark comparison | `#/analytics`, "Performance" block's hero chart + `metric.benchmarkRelative`; also on Overview | |
| 10 | Evidence/methodology disclosure | Any "Evidence & Methodology" control, or footer "Methodology & Evidence Registry" link | |
| 11 | Contextual AI | Header "Ask your portfolio," or any inline "Ask about this…" affordance | Canned templates, not free-text Q&A — see item 9 above. |
| 12 | Scenario Lab | `#/scenario` | |
| 13 | Representative `AVAILABLE`/`LIMITED`/`INSUFFICIENT_DATA`/freshness/caveat states | See table below | |

**Item 13, spelled out** — every state appears at least once, and each is independently
reachable:

- **`AVAILABLE`** — most metrics, e.g. `metric.return.1y` on Overview.
- **`AVAILABLE` + `STALE_DATA`** — `metric.benchmarkRelative` (Overview and Analytics);
  identical numeral to plain `AVAILABLE`, plus a freshness pill naming the CN A-share
  axis specifically.
- **`LIMITED`** — `metric.beta` (Risk & Return grid); the currency-exposure claim
  (`exposure.currency`, `MISSING_FX_HISTORY`); the Ping An Insurance holding
  (`thinlyTraded`, on Holdings).
- **`INSUFFICIENT_DATA`** — `metric.sortino` (Risk & Return grid); the Mainland China
  segment of Contribution to Risk (`CALCULATION_ERROR`); the Kweichow Moutai holding's
  unrealized gain/loss (`MISSING_COST_BASIS`); the CSOP Structured Note's risk metrics
  (`UNSUPPORTED_ASSET`); transaction `tx-0029`'s FX conversion (`MISSING_FX_HISTORY`, on
  Portfolio's Transactions table); the `reduceCnExposure` scenario's Sharpe ratio
  (`MISSING_BENCHMARK`, on Scenario Lab).
- **Freshness** — the persistent header strip (five axes: `LIVE`, `END_OF_DAY`, `STALE`,
  and two `DELAYED` FX axes); the per-position freshness column on Holdings; the "Least
  fresh" callout.
- **Caveat preservation** — click through the depth ladder on `metric.beta` or
  `metric.benchmarkRelative` and confirm the caveat survives (compressed, never dropped)
  at every depth (item 7 above).

**Nothing in this list is missing or unreachable.** Where a phase-2 or integration-pass
gap existed against this list (the missing `metric.totalPortfolioValue` claim, the
scenario-evidence gap), it was fixed rather than left for the owner to discover — see
`README.md`'s "What changed in this integration pass."
