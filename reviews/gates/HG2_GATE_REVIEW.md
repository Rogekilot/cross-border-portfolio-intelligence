# HG2 — Financial Core Proof: gate review package

**Status: APPROVED WITH CONDITIONS** by the product owner on 2026-10-02 (PD-0038; see §14). Before
that it was AWAITING_HUMAN_REVIEW. The package was prepared by the main session (PM) on 2026-10-02.
Only the designated human product owner decides this gate (PRD §38.4). Passing tests and the
reviewer's verdicts are evidence, not approval. **CP4–CP9 do not start as production-intended work
until this gate is decided.**

---

## 1. Gate name and ID

**HG2 — Financial Core Proof.** It covers checkpoints CP1 (trust ledger), CP2 (market-data
normalization) and CP3 (performance engine).

## 2. Objective

PRD §38.4: *verify the ledger, cross-currency normalization, historical reconstruction, and
performance accounting before analytics, AI, or polished UX are trusted.*

The question for you:

> **Do I trust the financial accounting and cross-currency foundation enough to build the rest of
> the product on top of it?**

## 3. Required deliverables

PRD §38.4 asks for a demonstration portfolio with representative US, Mainland China and Hong Kong
holdings, USD/HKD/CNY cash, and meaningful transaction history. PD-0035 §3 shapes it for HG2: a
synthetic US/CN/HK portfolio, plus a real US/ECB slice. It needs evidence of these 16 items:

| # | PRD §38.4 evidence item | # | PRD §38.4 evidence item |
|---|---|---|---|
| 1 | reconstructed positions from ledger events | 9 | splits |
| 2 | current portfolio value | 10 | missing cost basis behaviour |
| 3 | reporting/native currencies | 11 | TWR |
| 4 | price and FX timestamps | 12 | MWR/IRR where supported |
| 5 | historical FX handling | 13 | realized/unrealized gain where supported |
| 6 | deposits vs investment gains | 14 | FX attribution |
| 7 | internal transfers | 15 | reconciliation proof |
| 8 | dividends | 16 | known numerical tolerances |

## 4. Actual deliverables

**Evidence packs.** Each has one file per item above. Every number carries its state, reason,
manifest id and an expected digest, and every manifest is re-run.

| Pack | Where | What it is |
|---|---|---|
| **A. Synthetic cross-border portfolio** | `reviews/gates/HG2_EVIDENCE/synthetic/` (start with `SUMMARY.md`) | A US account (AAPL with a 4:1 split, MSFT), a HK account (0700, with an accrued dividend and withholding tax) and a CN account (SYNA, CNY cash). It includes an internal transfer, a currency conversion and its correction, fees, financing, a missing and an unresolved cost basis, and a USD withdrawal. As of 2025-04-30, reporting in USD, over 4 windows. **Labelled SYNTHETIC in every file.** |
| **B. Real US slice** | Generated locally into `reviews/gates/HG2_EVIDENCE/real_slice/`, which is git-ignored because it is computed from real payload files (PD-0027/0028). See §12. | A hypothetical USD ledger in AAPL at the real Alpha Vantage closes (2026-05-08 to 2026-09-30), reported in USD, EUR and CNY. **Today it shows no numbers**: no calendar is registered, and no FX file covers the window. See §8. |

**Code:**

| Checkpoint | Code |
|---|---|
| CP1 (ledger) | `src/domain/`, `src/persistence/` (migrations 0001–0008, 0014) |
| CP2 (market data) | `src/marketdata/`, `src/marketdata_tools/`, `src/corporate_actions_service/` (migrations 0009–0013) |
| CP3 (performance engine) | `src/performance/`, `src/performance_service/`, `src/performance_tools/` |

**Methodology** (`quant-analyst`, independent of the code):

| Convention set | File |
|---|---|
| `ledger-replay/1.5` | `methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md` |
| `market-data/1.10` | `methodology/CP2_MARKET_DATA_CONVENTIONS.md` |
| `performance/1.10` | `methodology/CP3_PERFORMANCE_CONVENTIONS.md` |

Golden fixtures are in `methodology/fixtures/` (`cp1_golden/1.1`; `cp3_golden` parts 1–4, with
derivation calculators).

**Acceptance records:** `reviews/CP1_PM_ACCEPTANCE.md`, `reviews/CP2_PM_ACCEPTANCE.md` and
`reviews/CP3_PM_ACCEPTANCE.md`. Independent reviews are in `reviews/TECH_REVIEW.md`, from "CP1-B
review (809d4d8)" onward.

## 5. Sample outputs: pack A, synthetic, as of 2025-04-30, reporting currency USD

**Current value:** USD 22,168.59, AVAILABLE. Native: USD 13,998, HKD 29,350, CNY 32,000.

**Returns by window:**

| Window | G (gain) | TWR | MWR |
|---|---|---|---|
| Since inception | 1,937.82 | 11.2615 % | 12.0523 % |
| From 2025-03-31 / trailing 1 month | 160.05 | 0.7098 % | 0.7190 % |
| Year to date | **no value**: INSUFFICIENT_DATA, WINDOW_BEFORE_INCEPTION | same | same |

The year-to-date window starts before the first event, so the engine refuses it rather than
inventing a starting value.

**Attribution since inception** (8 exact daily lines, which sum exactly to G):

| Line | USD |
|---|---|
| Local price effect | 1,867.48 |
| FX effect | −34.76 |
| Price–FX interaction | −0.10 |
| Income | 128.00 |
| Fees | −2.00 |
| Taxes | −12.80 |
| Financing | 0.00 |
| Currency conversion result | −8.00 |
| **Total (= G)** | **1,937.82** |

- **State:** LIMITED + STALE_DATA. SYNA missed 1 to 3 sessions on 03-17 to 03-19, and attribution
  needs every day.
- **FX effect by currency:** CNY −30.65, HKD −4.11.
- **Cariño residual** against the TWR: 2E-50.

**The behaviours the PRD asks to see:**

| Behaviour | What the pack shows | File |
|---|---|---|
| Split | AAPL 4:1 on 2025-02-03: 50 → 200 units. Each date uses its as-traded close (150.00, then 37.50); no adjusted series is read. Detection ran in dry-run mode and found nothing missing from the ledger. | `09_splits.json` |
| Internal transfers | Removing the paired legs changes no portfolio-level G or TWR, in any window. | `07_internal_transfers.json` |
| Missing cost basis | Remaining basis, unrealized gain and since-acquisition gain for the affected listing are INSUFFICIENT_DATA + MISSING_COST_BASIS. No basis is invented. | `10_missing_cost_basis.json` |
| Realized gains | FIFO, with the caveat "may differ from your broker's own lot records" (PD-0035 §1). | `13_realized_unrealized.json` |
| Reproduction | 17 of 17 computations re-run with matching digests. | `00_manifests.json` |
| Reconciliation | Identity checks I-1 to I-9: 0 failures. | `15_reconciliation_proof.json` |

## 6. Tests performed and their results

Re-run by the main session on 2026-10-02. Python 3.12.14, PostgreSQL 17.11. Command:
`uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .`

| Run | Result |
|---|---|
| Default (no database) | **1611 tests OK**, 227 skipped (the opt-in database tests) |
| With PostgreSQL, run twice: `FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app` | **1611 OK**, 2 skipped (connectivity preflight only), both times |
| Test schemas left behind | 0 |

Key suites:
- **CP3 exit** (`test_cp3_exit.py`):
  - all 4 golden parts (366 hand-derived items), on the pure path and through PostgreSQL as the
    least-privilege role `finweb_app`;
  - identities on 525 windows, 0 failures;
  - determinism across processes and hash seeds;
  - `reproduce()` gives REPRODUCED for all 525.
- **CP2 exit:** one unchanged consumer gives byte-identical results across four adapter worlds and
  two stores.
- **CP1:** the golden fixture `cp1_golden/1.1`. A 21,000-permutation order check found 0
  mismatches. Basis numbers agree with FIFO, LIFO, highest-cost-first and average cost.

Independent review history (`technical-reviewer`, which never reviews its own work):

| Checkpoint | Outcome |
|---|---|
| CP1 | Sections "CP1-B review" through "CP1-D closure check": HOLD on the first CP1-B review (a HIGH trigger bypass), then PASS_WITH_FINDINGS. All HIGH and MEDIUM closed. |
| CP2 | "CP2 review", "re-check" and "final check": PASS_WITH_FINDINGS. C2-1 to C2-15 closed. |
| CP3 | Five rounds, §28–§32. The last is **"PASS_WITH_FINDINGS, no HIGH, no MEDIUM. CP3 is complete and fit for the HG2 gate."** CP3-1 to CP3-21 are closed, except two LOW items (§8). |

The reviewer independently re-derived an attribution case by hand (an HKD listing, a conversion, a
fee, an accrued dividend with its FX, tax and a sale). The engine matched it exactly: all eight
lines, G = 9,784/25 and TWR = MWR = 1,223/31,250.

## 7. Proof of work

- **Independence of expected values.** Every golden value was derived by hand by `quant-analyst`,
  with its derivation written out in the `CP*_GOLDEN_*_DERIVATION.md` files. The values were
  re-checked by calculators that import nothing from `src/`. The engineer never authors expected
  values. When engine and fixture disagreed (for example P22-V1 in CP3e), the Quant ruled, and
  sometimes the fixture was the one corrected.
- **Exactness.** Arithmetic inside the engine uses exact fractions, rounded once at presentation
  (half away from zero, by currency minor unit). Displayed breakdowns are apportioned so they sum
  exactly to the displayed bar.
- **Traceability.** Every result has a Computation Manifest. It records the inputs (ledger version,
  market-data release digest), the convention ids and the engine id. `reproduce()` re-runs it and
  compares the result digest. The pack's `00_manifests.json` lists every manifest, and
  `00_inputs.json` lists every input file with its sha256.
- **Rationale.** Each convention is a numbered Ruling in the methodology files, and each review
  finding links to file:line and to the ruling it violates.
- **Determinism.** Pack A regenerated by the main session is byte-identical to the engineer's copy.
  The reviewer's copies were identical across five hash seeds.

## 8. Known limitations and incomplete items

**About the evidence itself:**
1. **Mainland China and Hong Kong prices are synthetic only.** There is no admissible real CN/HK
   source (PD-0031/0032), so real CN/HK price behaviour is unproven. PD-0035 §3 accepted this for
   HG2, with a real source to be revisited before CP4/HG3.
2. **The real slice shows no numbers today.** Freshness is UNKNOWN because no calendar is
   registered, so every value is INSUFFICIENT_DATA with the cause stated. Its EUR and CNY views
   also lack FX data for May–September 2026: the only FX file on disk covers 2025-01-02 to
   2025-01-08. Your steps in §12 fix both.
3. **Real FX would come through Frankfurter,** labelled "ECB reference rates as republished by
   Frankfurter, provenance UNCONFIRMED". The ECB's own file (`ecb.eurofxref`) is refused at ingest
   until its number format has been profiled from a first real download (MD-OI-12). The CNY view
   is a cross through EUR, with no central-parity check (`PARITY_CHECK_NOT_RUN`).
4. **US prices** cover the free tier's last 100 sessions from one source (SINGLE_SOURCE). The
   instrument identity in the real slice is set by the tool's own configuration (AAPL, XNAS). US
   and CN exchange codes are still "from memory" until your OpenFIGI lookups (PD-0033).
5. **Split detection has no real input.** No corporate-action feed or issuer-filing source is
   admitted, so F8-B is shown on synthetic data only.

**Open findings and conformance:**

6. **Two LOW review findings are open.** Neither gives a wrong number on the HG2 data:
   - **CP3-15 remainder:** a misnamed detection policy can still be defeated by an old filing
     record of the same listing. The fix is to check per (listing, ex-date).
   - **CP3-21:** the real slice's file-version comparison reads 200.00 against 200.0000 as a
     disagreement. It is a report only; the file set is unaffected.
7. **`is_conformant = False`.** The currency minor-unit table is "from memory, owner to confirm
   against ISO 4217". The rows are AUD, CAD, CHF, CNY, EUR, GBP, HKD, SGD and USD with 2 decimals,
   and JPY with 0.

**Scope limits:**

8. **"Current value"** means the latest date with admissible data, labelled as such. Live valuation
   is refused (main-session ruling). There is no result storage yet.
9. **Not tested:**
   - PostgreSQL 16;
   - concurrency (database tests share fixed IDs and would deadlock if run concurrently);
   - Current-mode attribution with Frankfurter data.
10. **Production hardening is documented, not applied.** That covers `REVOKE TEMPORARY … FROM
    PUBLIC` and the application grants on a non-test schema.
11. **Carried CP1 LOW residuals** are in `reviews/CP1_PM_ACCEPTANCE.md` §6. They include:
    - extreme stored values (over 4,300 digits) make replay raise;
    - a wraparound proof by argument only.
12. **Over-labelling.** FX provenance notes also appear on some results that used no rate. This errs
    on the safe side.
13. **Not committed.** CP3e, CP3f and the fix rounds are uncommitted until you ask.

## 9. Deviations from the PRD

| PRD | What we did | Authority |
|---|---|---|
| §38.4: representative US, CN and HK holdings | CN/HK prices are synthetic; real data is US plus FX only | **PD-0035 §3** (your decision) |
| HG1 §4.3: constant-FX attribution split | The exact daily split, with a separate price–FX interaction line. The waterfall's first bar becomes "local price effect". | **PD-0035 §4** (your decision). The design artifacts are updated before CP7. |
| §38.4: "current portfolio value" | Historical as-of valuation: the latest date with admissible data, labelled; no live value | Main-session ruling for CP3/HG2 (STATUS). Live data waits for OQ-04b. |
| — | Margin and short positions are not in V1 | **PD-0024** (your decision) |
| — | Personal or academic project character; internal-use data only | **PD-0032** (your decision) |

## 10. New assumptions since HG1 (PD-0017, 2026-09-13)

**Your decisions:**

| Decisions | Subject |
|---|---|
| PD-0020, PD-0021 | Phase B architecture; the CP1 identity model |
| PD-0022, PD-0023 | Harness retirement; CP1-B rulings |
| PD-0024 | Taxonomy |
| PD-0025 | Decimal metric envelope and reason codes |
| PD-0026 | Ledger numeric bounds |
| PD-0027, PD-0028, PD-0029 | Free development data; the launch vendor deferred (OQ-04b); the download group |
| PD-0030 | SOURCE_CONFLICT / MISSING_PRICE_HISTORY; F8-B; strict CNH |
| PD-0031, PD-0032, PD-0033 | Source attestations; project character; ECB and calendars |
| PD-0034 | Calendar drafts |
| PD-0035 | FIFO; partial total; HG2 data; FX split |
| PD-0036 | `acquired_on`; no new reason codes |

**Main-session rulings:**
- performance reads never write the ledger;
- one lot engine;
- historical as-of valuation for CP3 and HG2;
- fixture convention versions are minimums (Ruling 11.6).

**Methodology:** the convention sets in §4. They were written by `quant-analyst` and not ratified by
you. They are a level-4 source under CLAUDE.md, and this gate is where you may challenge them.

## 11. Open risks and unresolved decisions

- **OQ-04b:** a licensed launch vendor with display rights is due before private beta. Until then
  all data is internal-only.
- **A real CN/HK price source,** to be revisited before CP4/HG3 (PD-0035).
- **Your open actions:**
  - check and register the calendar drafts (PD-0034);
  - confirm the minor-unit table (§8 item 7);
  - optionally run the OpenFIGI lookups;
  - optionally download the ECB's own file, so it can be profiled.
- **Open methodology debt:** the max-drawdown convention (STATUS item 7). It is a CP4 analytics
  matter.
- **The risk if HG2 is approved without the real slice showing numbers:** the real-data path
  (calendars, then freshness, then FX) has been tested on temporary file sets but not yet run on
  your registered files.

## 12. Reproduction and inspection

All commands run from the repository root.

**1. Re-run the tests:**
```bash
uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .
```

**2. Regenerate pack A.** This re-runs and re-checks every computation:
```bash
PYTHONPATH=src uv run --no-cache --no-sync --frozen --offline python -m performance_tools.evidence_pack synthetic --out reviews/gates/HG2_EVIDENCE/synthetic
```
`git diff` on that folder should then show no change.

**3. Make the real slice show numbers (recommended before you decide).**
- **a. Calendars.** Check `NYSE_SESSIONS.json` and `ECB.json` in `data/marketdata/calendars/drafts/`
  against `REVIEW.md`. In each file, set `version` (e.g. `2025-2026 v1`) and `prepared_by` (that you
  checked it, and when). Then register both:
  ```bash
  PYTHONPATH=src .venv-download/bin/python -m marketdata_tools.download register-file --path data/marketdata/calendars/drafts/NYSE_SESSIONS.json --source calendar.manual --kind CALENDAR --format finweb_calendar_json/1 --adjustment RAW --label NYSE_2025_2026 --ext json --identifiers NYSE_SESSIONS
  ```
  ```bash
  PYTHONPATH=src .venv-download/bin/python -m marketdata_tools.download register-file --path data/marketdata/calendars/drafts/ECB.json --source calendar.manual --kind CALENDAR --format finweb_calendar_json/1 --adjustment RAW --label ECB_2025_2026 --ext json --identifiers ECB
  ```
- **b. FX for the price window.** Run these in the same terminal; this step needs a network
  connection.
  ```bash
  export FINWEB_HUMAN_DOWNLOAD=1
  ```
  ```bash
  PYTHONPATH=src .venv-download/bin/python -m marketdata_tools.download fetch --source frankfurter_fx --symbols USD,CNY --start 2026-05-08 --end 2026-09-30
  ```
- **c. Build the slice:**
  ```bash
  PYTHONPATH=src uv run --no-cache --no-sync --frozen --offline python -m performance_tools.evidence_pack real --out reviews/gates/HG2_EVIDENCE/real_slice
  ```
  The new Frankfurter file and the January 2025 one are two versions of the same series, so the
  build will stop and name both files (market-data Ruling 0.1). Choose the new one by excluding
  the old one with the sha256 the report prints, and re-run:
  ```bash
  PYTHONPATH=src uv run --no-cache --no-sync --frozen --offline python -m performance_tools.evidence_pack real --out reviews/gates/HG2_EVIDENCE/real_slice --exclude-file <sha256 of the January 2025 file>
  ```
  Your choice is recorded in the pack as "file set chosen by the operator".
- **d. Read** `reviews/gates/HG2_EVIDENCE/real_slice/SUMMARY.md`. You can spot-check any AAPL close
  in it against a public quote page, and any EUR or CNY rate against the ECB's published reference
  rate for that date.

**4. What to inspect in pack A.** Read `SUMMARY.md`, then any item file. Each value's `exact`
fraction can be checked by hand. The golden derivations
(`methodology/fixtures/cp3_golden/CP3_GOLDEN_PART*_DERIVATION.md`) show the arithmetic behind the
same scenarios.

## 13. Agent recommendation

**Recommendation: APPROVED WITH CONDITIONS, decided after step §12.3 has been run.**

Reasons:
- **The accounting core is proven on hand-derived truth.** 366 independent golden items match on
  both paths, and 0 identity failures were found across 525 windows. Every computation reproduces.
  An independent reviewer's own hand-derived case matched exactly. Five independent CP3 review
  rounds ended with no HIGH or MEDIUM finding.
- **Refusals are explicit.** The engine says "no value" with a cause rather than guessing: the
  year-to-date window before inception, a missing basis, stale or unknown freshness, conflicting
  file versions and a suppressed split.
- **The weakest part of the evidence is real data, not the engine.** CN/HK is synthetic by your
  decision. The real slice needs your two short steps before it shows numbers. Seeing it produce
  real USD, EUR and CNY values that you can spot-check is the most direct answer to the gate
  question.

**Suggested conditions:**
1. Fix CP3-15 (per listing and ex-date) and CP3-21 (compare decimals by value) as the first CP4
   work item.
2. Confirm or correct the minor-unit table.
3. A real CN/HK price source, or an explicit decision to continue without one, before CP4
   analytics are presented as real (as in PD-0035).
4. Register the HK and CN calendars before any real HK or CN data is used.

The agent does not decide this gate. A different decision is equally valid: for example, REVISION
REQUIRED if the real slice must show numbers before you decide, or if you want the two LOW
findings closed first.

## 14. Human decision

```text
[ ] APPROVED
[x] APPROVED WITH CONDITIONS
[ ] REVISION REQUIRED
[ ] REJECTED

Human comments: "Approve with conditions (Recommended)", given after the real slice (§12.3) was
run and shown: 10,480.33 USD / 9,229.70 EUR / 70,265.74 CNY, hand-checked; 0 identity
failures; 21/21 reproduced. Conditions (verbatim in PD-0038):
  1. Fix CP3-15 and CP3-21 as the first CP4 task.
  2. Apply the minor-unit confirmation (PD-0037) so the engine marks itself conformant.
  3. A real CN/HK price source, or an explicit decision to go without one, before CP4 results
     are presented as real.
  4. Register the HK and CN calendars before any real HK/CN data is used.

Decision date: 2026-10-02
Approver: the product owner; recorded by the main session in
decisions/product/PD-0038-hg2-approved-with-conditions.md
```
