# CP7 F1 PD-0079: methodology check of the real-mode key figures and their wording (2026-11-09)

**Author:** quant-analyst. **Asked by:** the main session (PM). **Subject:** the uncommitted PD-0079 build by the engineer:
- `web/src/real-mode.ts`: `FIGURE_LIST`, `figureRow`, `keyFigures`;
- `web/src/RealModeApp.tsx`: `KeyFigures`, and the raw-document label in `RootDetail`;
- `web/src/real-mode-i18n.ts`: the new strings;
- `web/src/real-mode.test.ts`: the PD-0079 tests.

**Checked against:**
- `methodology/CP3_PERFORMANCE_CONVENTIONS.md`: Rulings 1.3, 1.4, 1.4a, 2.2 and 2.4;
- `src/performance/engine.py`, `states.py`, `results.py` and `valuation.py`: what the engine stores;
- `src/product_contract/vocabulary.py` and `metric_state.py`: the three states and AC-15 as corrected by PD-0007;
- `methodology/CP2_MARKET_DATA_CONVENTIONS.md` Ruling 6.5 item 6: C-2 names the NAV;
- `methodology/CP7_F1_R7_CLAIM_WORDING_CHECK_2026-11-07.md` R-10;
- PD-0035 §2 and PD-0079;
- `designs/FEATURE_DESIGN.md` D3.2.

This note rules on the figures, the display rule and the wording. It changes no method, no value and no fixture.

## Verdict: **ACCEPTED_WITH_CHANGES**, with **11 required changes (F-1 to F-11)**

**Worst problem (F-1, HIGH).** A `LIMITED` NAV shows its number without the stale weight.
- Ruling 1.4 item 2 says the weight "is stated beside it as a number". HG1 round 4 §6 R1 allows a `LIMITED` aggregate only on that
  condition.
- The engine stores the weight (`stale_weight_presented`), but `figureRow` does not read it.
- zh makes this worse. "并非完整数字" says the figure is **incomplete**. A `LIMITED` total is complete: every component has a value,
  and some are stale (F-4). Incomplete is the meaning of the partial figure, a different metric.

**Next worst (F-2, HIGH).** The reason given for leaving out `portfolio_value_priced_holdings` does not hold.
- The engineer's reason is that "beside a NAV row the partial figure could read as NAV". Under Ruling 1.4a the partial figure is
  emitted **only** when the total has no number, so it never sits beside a NAV number.
- The omission therefore bites in exactly one state, the suppressed total, and that is the state PD-0035 §2 decided: the owner's
  answer was "Yes, labelled, with count".
- A collapsed JSON block is not "labelled, with count". If the PM prefers to keep the figure out, that departs from PD-0035 §2 and
  is the owner's decision, not mine.

## Question 1: the figure list

### Is it right to call `portfolio_value` "NAV" here? **Yes, within this scope.**

- `portfolio_value`/`REPORTING` is `TV_R(D)` (Ruling 1.4; `engine.py:338`). Ruling 6.5 item 6 C-2 and design 7.4 S3 call the same
  quantity "the NAV": `10 × p + 500.00`. So the label and the claim text name one figure.
- The real-mode contract admits only that valuation: one position, USD cash, USD reporting (`real_scoped_contract.py`,
  `validate_intent`).
- **Limitation, for the record.** `TV_R` is positions + cash + dividend receivables, with negative cash signed. It is not a fund's
  per-unit NAV. It deducts nothing beyond what the ledger holds. CP3 itself does not use the word "NAV", so this label rests on
  Ruling 6.5, and a later scope must not assume it carries over (Ruling 6.5 item 7).
- **Judgment class:** Fact. These rows are stored values, so they need no reference point of their own (P4).

### Does the list mislead by omission? **Yes, in three states. The rest of the selection is sound.**

| State of the result | What the list does | Finding |
|---|---|---|
| Total `AVAILABLE` | NAV and its parts | Sound, except for the parts' rounding (F-3). No partial figure exists (Ruling 1.4a). |
| Total `AVAILABLE` + `STALE_DATA` | NAV plus "Reason: STALE_DATA" | Sound. D3.2 would keep this row plain, with the stale axis in D5. PD-0079 says "reason as stored", and S3 states freshness. A PD ranks above the design. |
| Total `LIMITED` | Number, state, marker, reason; **no stale weight** | **Misleads. F-1.** |
| Total `INSUFFICIENT_DATA`, partial figure emitted | "No number", while the only figure Ruling 1.4a and PD-0035 §2 provide is in the JSON | **Misleads. F-2.** |
| Total `INSUFFICIENT_DATA`, partial itself `INSUFFICIENT_DATA` (`NO_VALUED_COMPONENT`) | "No number"; reason is null, so no cause is shown | F-2 and F-9. |
| Total `INSUFFICIENT_DATA` with no reason code (`NO_LIVE_LEDGER_EVENTS`, `CALENDAR_COVERAGE_GAP`) | State only. The stored cause is in `details`, which the row does not show. | **Thin. F-9.** The invariant is that such a metric names its causes (`results.py`, `ComputedMetric.__post_init__`). |
| Explicit refusal: one `portfolio_value` row and nothing else | The other three show "Not in this result" | **F-8.** The absence must not read as a zero. |
| No dividend event in the ledger (the HG4 case) | Receivables show "Not in this result" | **F-8.** zh "此结果中没有" reads as "there are none", which sits badly beside C1's "nothing is known about such a dividend". |

**Native views staying in the document is sound.** Under the contract they equal the reporting view, and PD-0079 leaves the
selection open.

**The note must say it is a selection (F-5).** As written, it claims the opposite of what the list does.

### F-3: a total shown above its parts is a decomposition

The list shows `holding_value`, `cash_value` and `receivable_value` from their own rows, under the total. Ruling 2.4:
- item 2: independently presented values reconcile only within `(k + 1)/2` quanta;
- item 4: a surface that shows a decomposition "shows the apportioned values for **every** line";
- item 5: a footnote "may not sum" is **rejected**.

The engine stores those apportioned values on the total's row, as `breakdown` (`engine.py:338`, `_breakdown`).

**It is reachable through the real-mode contract.** `DECIMAL` admits six decimals, so opening cash can be sub-cent. By hand, with
quantity 1, `p` = 1.004 and cash 1.004, all in USD:
- exact: holding 1.004, cash 1.004, total 2.008, so `T̂` = **2.01**;
- independently presented (Ruling 2.2, half away from zero): holding **1.00**, cash **1.00**. They sum to 2.00, not 2.01;
- apportioned (Ruling 2.4 item 3): floors 1.00 + 1.00 = 2.00, shortfall 1 quantum, remainders tie at 0.004, and the tie goes in the
  fixed line order (holding first), giving **1.01 + 1.00 = 2.01**.

The planned R8 world (`10 × p + 500.00`) cannot show this, because only one part rounds. The rule still binds the surface.

## Question 2: the strings

| Key | EN | zh | Change |
|---|---|---|---|
| `figuresHeading` | OK | OK. 关键数字 is correct. | none |
| `figuresNote` | **Overclaims.** "nothing is … reordered" is false: the fixed list puts `portfolio_value` first, whereas the stored order is by `metric_id`. It also does not say this is a selection. | same | **F-5**, **F-6** |
| `figureNav` | OK | **净值** is not R-10's term. Alone, it reads as a fund's unit value (单位净值). Use **资产净值**. | **F-7** |
| `figureHolding` | OK | 持仓价值 is understood, but the term is **持仓市值**, which zh S1 professional also uses (市值). | **F-7** |
| `figureCash` | OK | **现金价值 is an insurance term** (保单现金价值). The figure is a balance: **现金余额**. | **F-7** |
| `figureReceivable` | Loses "dividend". Ruling 1.3 defines only dividend receivables. | 应收款 is any receivable. Use **应收股息**. | **F-7** |
| `figureAbsent` | Neutral, but can read as zero | "此结果中没有" reads as "there are none" | **F-8** |
| `figureState`, `figureReason` | OK | OK | none |
| `figureNoValue` | OK | OK | none |
| `figureLimited` | "not a plain figure" names no limitation. It also presumes a reason exists. | **Wrong: "并非完整数字" = "not a complete figure".** | **F-4** |
| `figureUnreadable` | OK for a state. Must also cover a value that breaks the contract. | same | **F-10** |
| `rawNote` | "exactly as issued" keeps the owner's wording and is true of the content, but the screen adds indentation. | same | **F-6**, **F-11** |

### Does "the claim limits above" hold over TEST data? **No. The two notes must differ by origin (F-6).**

Over a non-real origin, `ClaimLimits` renders only the invented-data mark and no item (design 7.4, 4.3). So "the claim limits above"
points at nothing, and suggests that limits were stated for this data. PD-0079 consequence 3 is written for the real case, and
consequence 4 keeps the origin rules. Reading them together is not a change to the owner's decision:
- `common` keeps "the claim limits above" for a real origin;
- `testOrigin` gets its own two notes, which point at the mark.

### Other answers

- **The seal:** none of these strings mentions it. No PD-0073 issue.
- **P6:** no string is predictive.
- **Fixed terms:** 关键数字, 状态 and 原因 are correct. 报告币种视图 is a good rendering of "reporting view".

## Question 3: the display rule. **Matches P5, AC-15 and D3.2, with one tightening (F-10).**

- A number shows only for `AVAILABLE` and `LIMITED`. That is AC-15 as corrected by PD-0007: `value is None` if and only if the
  state is `INSUFFICIENT_DATA`.
- `INSUFFICIENT_DATA` shows no number even if a row holds one. That is correct (P5).
- Unknown and missing states show no number. That is correct: `SufficiencyState` has exactly three values, "never a fourth, and
  never absent".
- `LIMITED` carries its marker and reason in the value's own row, as D3.2 asks.
- `INSUFFICIENT_DATA` renders explicit text, not a blank or a dash. D3.2 is met.

**The tightening.** Two contract breaches are handled too softly:
- `AVAILABLE` or `LIMITED` with a null value renders "No number is shown for this state", which is false of those states;
- a JSON number is shown through `String(number)`. The engine forbids floats and stores decimals as strings
  (`marketdata/canonical.py`), so this branch can only be reached by a breach, and by then `JSON.parse` may already have changed the
  digits. That contradicts "as stored".

Both must show `figureUnreadable`.

## The required changes

| # | Severity | Problem | Fix |
|---|---|---|---|
| **F-1** | HIGH | `LIMITED` NAV without the stale weight (Ruling 1.4 item 2) | Behaviour F-1 below; strings in block PD79-EN and PD79-ZH |
| **F-2** | HIGH | Partial figure unreachable in the one state where it exists (PD-0035 §2, Ruling 1.4a) | Behaviour F-2; strings |
| **F-3** | MEDIUM | Parts are not the apportioned values (Ruling 2.4 item 4) | Behaviour F-3 |
| **F-4** | MEDIUM | `figureLimited`: zh says incomplete; EN names nothing | Strings |
| **F-5** | MEDIUM | `figuresNote` says nothing is reordered, and hides that it is a selection | Strings |
| **F-6** | MEDIUM | `figuresNote` and `rawNote` cite claim limits that do not render over TEST | Block PD79-TEST; behaviour F-6 |
| **F-7** | MEDIUM | zh labels: 净值, 现金价值, 应收款价值, 持仓价值. EN receivable loses "dividend". | Strings |
| **F-8** | LOW | `figureAbsent` can read as zero or "none" | Strings |
| **F-9** | LOW | A row with no reason code shows no cause | Behaviour F-9; strings |
| **F-10** | LOW | A contract breach renders softly (Question 3) | Behaviour F-10; strings |
| **F-11** | LOW | `rawNote` does not disclose the added layout | Strings |

### Behaviour (the engineer implements; every value below is a stored value, copied)

- **F-1.** `FigureRow` also carries the stored `stale_weight_presented`, as text.
  - On any row where it is a string, show `t('figureStaleWeight')` and the value in the row, next to the `LIMITED` marker.
  - On a `portfolio_value` row in state `LIMITED` where it is not a string, show `t('figureStaleNotStated')`. This is the
    gross-value-0 case (Ruling 1.4 item 2 (1.2)); F-9's detail then shows `STALE_SHARE_UNDEFINED`.
- **F-2.** After the four groups, render a separate block **only when** both hold: the `portfolio_value`/`REPORTING` row has no
  number, and the result stores a `portfolio_value_priced_holdings`/`REPORTING` row.
  - It shows `t('figurePartial')`, the row by the same rules as any figure, `t('figurePartialNotNav')`, and two counts copied from
    the row's stored `lineage`: `t('figureExcludedHoldings')` from `excluded_holdings`, and `t('figureExcludedComponents')` from
    `excluded_components`. Show both: a CNH cash balance is excluded with zero holdings excluded.
  - It stays out of `FIGURE_LIST`, is never placed in the NAV row, and carries no NAV wording except its own negation.
  - The existing assertion that `77.77` does not show beside an `AVAILABLE` NAV stays. That fixture is one the engine never emits, and
    the rule refuses it.
- **F-3.** When the `portfolio_value`/`REPORTING` row has a value and a non-empty stored `breakdown`, each listed part's value is the
  `shown` entry (index 1) of the line whose ref equals `holding:{account}/{listing}`, `cash:{account}/{currency}` or
  `receivable:{account}/{event}`, built from that row's stored `subject`.
  - A part with no matching line shows no number, and `figureUnreadable`.
  - With no breakdown, or with no number on the total, each part shows its own stored `value`.
    **Superseded on 2026-11-14 (TR7F3-L-1):** this bullet, and the words "and a non-empty stored `breakdown`" above, are replaced by
    §1 of the addendum "Addendum 2026-11-14: TR7F3-L-1, F-3 amended" at the end of this file. Apply that section, not this bullet.
  - This is a lookup. It adds, rounds and allocates nothing.
- **F-6.** `KeyFigures` and `RootDetail` read `figuresNote` and `rawNote` from `common` for a real origin, and from `testOrigin[locale]`
  otherwise. The test "puts the figures below the claim limits…" must expect the per-origin text. Add an assertion that over TEST the
  output contains neither `claim limits` nor `声明限制`. Keep the assertions on `common`.
- **F-9.** When the stored `details` array is non-empty, show `t('figureDetail')` and its entries as stored codes, uninterpreted, in the
  row. No selection among them.
- **F-10.** `figureRow`: `const stored = typeof metric.value === 'string' ? metric.value : null;`. A row in state `AVAILABLE` or
  `LIMITED` with no stored string value shows `figureUnreadable`, not `figureNoValue`. Only `INSUFFICIENT_DATA` shows `figureNoValue`.

**Tests to add:**
- a `LIMITED` total shows the stored weight byte for byte, and shows `figureStaleNotStated` when it is null;
- a suppressed total with a partial row shows the block, with both counts, in both languages, after the fourth group;
- the sub-cent example above, built with placeholder breakdown values: the parts show 1.01 and 1.00 from `breakdown`, not 1.00 and
  1.00 from their own rows;
- a null-reason row shows its `details`;
- an `AVAILABLE` row with a null value, and one with a numeric value, each show `figureUnreadable` and no number;
- a term guard over `common['zh-CN']`: no `净资产`, and no `净值` that is not part of `资产净值` (`/(?<!资产)净值/`).

## Replacement text (apply verbatim)

**In `common.en`**, replace these keys and add the new ones. `figuresHeading`, `figureNav`, `figureHolding`, `figureCash`, `figureState`,
`figureReason` and `figureNoValue` are unchanged.

```ts PD79-EN
    figuresNote: 'A fixed selection of the stored figures, in a fixed order; the complete set is in the document below. Each value is shown as the engine stored it: nothing is rounded, converted or summed here. Where the total has a number, its parts are the engine\'s apportioned values, which add up to it exactly. The claim limits above govern these figures.',
    figureReceivable: 'Dividend receivable value, reporting view',
    figureAbsent: 'Not in this result. That is not a stated zero.',
    figureLimited: 'Limited: computed on a weak basis, so this number does not stand alone; read it with what is stated beside it.',
    figureUnreadable: 'State or value not readable; no number is shown.',
    figureStaleWeight: 'Stale weight (share of the components\' gross value, as a decimal fraction)',
    figureStaleNotStated: 'Stale weight not stated by the engine.',
    figureDetail: 'Detail',
    figurePartial: 'Value of priced holdings (partial), reporting view',
    figurePartialNotNav: 'Partial: this is never the portfolio total or NAV.',
    figureExcludedHoldings: 'Holdings excluded because they cannot be valued',
    figureExcludedComponents: 'All components excluded (holdings, cash, receivables)',
    rawNote: 'The engine\'s document exactly as issued, with only line breaks and indentation added for reading. Its notes are in English and are not interpreted. The claim limits above govern it.',
```

**In `common['zh-CN']`**, replace these keys and add the new ones. `figuresHeading`, `figureState`, `figureReason` and `figureNoValue`
are unchanged.

```ts PD79-ZH
    figuresNote: '这里按固定顺序列出部分已存储数字；完整内容见下方文档。每个数值均按引擎存储的原样显示：此处不做舍入、换算或求和。总额有数值时，其组成项为引擎分摊后的数值，合计恰等于总额。以上的声明限制适用于这些数字。',
    figureNav: '组合价值（资产净值），报告币种视图',
    figureHolding: '持仓市值，报告币种视图',
    figureCash: '现金余额，报告币种视图',
    figureReceivable: '应收股息价值，报告币种视图',
    figureAbsent: '此结果未包含此项，这并不表示数值为零。',
    figureLimited: '受限：计算依据较弱，此数字不能单独理解；请结合旁边列明的内容阅读。',
    figureUnreadable: '状态或数值无法读取，不显示数值。',
    figureStaleWeight: '陈旧权重（占各组成项绝对值之和的比例，以小数表示）',
    figureStaleNotStated: '引擎未给出陈旧权重。',
    figureDetail: '详情',
    figurePartial: '已定价持仓价值（部分），报告币种视图',
    figurePartialNotNav: '部分金额：绝非组合总值或资产净值。',
    figureExcludedHoldings: '因无法估值而被排除的持仓数',
    figureExcludedComponents: '被排除的组成项总数（持仓、现金、应收股息）',
    rawNote: '引擎原样签发的文档，仅为便于阅读添加了换行和缩进。其中的说明为英文，未作解读。以上的声明限制适用于该文档。',
```

**In `testOrigin`**, add these keys to each language beside `banner` and `mark`. They keep "invented" in the table that may carry it,
and neither contains "real source", so the existing test of the TEST output stays true.

```ts PD79-TEST
  en: {
    figuresNote: 'A fixed selection of the stored figures, in a fixed order; the complete set is in the document below. Each value is shown as the engine stored it: nothing is rounded, converted or summed here. Where the total has a number, its parts are the engine\'s apportioned values, which add up to it exactly. These figures come from invented test data, as the mark above says.',
    rawNote: 'The engine\'s document exactly as issued, with only line breaks and indentation added for reading. Its notes are in English and are not interpreted. It comes from invented test data, as the marks above say.',
  },
  'zh-CN': {
    figuresNote: '这里按固定顺序列出部分已存储数字；完整内容见下方文档。每个数值均按引擎存储的原样显示：此处不做舍入、换算或求和。总额有数值时，其组成项为引擎分摊后的数值，合计恰等于总额。这些数字来自测试用虚构数据，如上方标记所示。',
    rawNote: '引擎原样签发的文档，仅为便于阅读添加了换行和缩进。其中的说明为英文，未作解读。该文档来自测试用虚构数据，如上方标记所示。',
  },
```

## Observations (not required changes)

- **O-1.** `RootDetail` renders the figures even when `ClaimLimits` falls to its alert, so a number could show with no caveats and with
  "the claim limits above" pointing at nothing. The path is not reachable today: `readClaimBlock` runs the same `assertSlots` first, so
  such a root is refused on read. If that reader is ever relaxed, the figures must fall with the claims.
- **O-2.** R-10 itself is applied: zh S3 uses 资产净值 at all three depths. The fictional screens' `analytics-i18n.ts` still uses 净值
  (`partialExcludesComponents`, `analyticsPartialNotNav`). That is outside this check and outside R-10's scope, and it is the PM's call
  whether to align it.
- **O-3.** A stored `conformant` flag is not shown in the list. It stays in the document and the manifest. It is false only when a
  placeholder is injected or a convention is unbuilt, and no such case is expected on the real path. This should be looked at again if
  that changes.

## How I checked

- `cd web && npx vitest run src/real-mode.test.ts` on the engineer's tree: 80 passed. That run is of the code as built, before any
  change here.
- The replacement text was not run under vitest. I hold no write path to `web/`, and a scratch copy of the web tree was refused by the
  permission system in the previous check. The engineer must run the file after applying the changes.
- The stored shape was read from the engine, not from the test fixture: `ComputedMetric.to_canonical_dict` has `stale_weight_presented`,
  `breakdown`, `details`, `lineage` and `partial` at the top level. `canonical_json` encodes a `Decimal` as a string and a `Fraction` as
  `n/d`, and refuses a float (run in memory).
- The apportionment in F-3 is derived by hand above. As a cross-check only, the engine's own `performance.numerics.apportion` gives
  the same 1.01 + 1.00 for it. That call confirms my arithmetic against the code; it is not where the expected value came from.
- An in-memory check (no file written) parsed the three blocks out of this note and found:
  - no banned wording in the `common` blocks;
  - no `净资产` and no bare `净值` in zh;
  - no "real source" and no "claim limits" in the TEST notes;
  - the test's existing `rawNote` patterns all still hold, in both languages;
  - the same new keys in EN and zh. zh has three further keys (`figureNav`, `figureHolding`, `figureCash`) that change only in zh.

---

# Follow-up after PD-0080: the figures on the valuation document (2026-11-09)

**Asked by:** the main session (PM). **Subject:** the uncommitted PD-0080 build: `web/src/real-mode.ts`, `web/src/RealModeApp.tsx`,
`web/src/real-mode-i18n.ts`, `web/src/real-mode.test.ts`, `web/src/real-mode-engine-result.fixture.json` and
`tests/product/real_figures_engine_fixture.py`.

**A correction to my earlier section.** I ruled on the valuation's shape and did not check which document a `TEST` create stores. So
that section's rules are right for the valuation document, and it did not notice that a `TEST` root would show every figure as absent.
PD-0080 closes that.

## Verdict: **ACCEPTED_WITH_CHANGES**, with **6 required changes (G-1 to G-6)**

F-1, F-2 and F-3 are built as I ruled, and the fixture's values agree with my hand derivations. The required changes are to the two new
strings, the place of the no-NAV notice, one string of my own, a stale code comment, and the fixture gap.

**Worst problem (G-1).** `figuresNone` says "This document holds no valuation figures". The `TEST` document holds `buckets` with
`value` amounts for cash and for a security (`CASH:USD` `20/1`, `SECURITY:…` `20/1` in `real-mode-stored-result.fixture.json`). A reader who
opens the document below finds what look like valuation figures, directly under a sentence saying there are none. What is true is that
it stores none of the **listed** figures and is not a valuation result.

## 1. The new strings

| Key | EN | zh | Change |
|---|---|---|---|
| `figuresNone` | **Overclaims** "holds no valuation figures" (above). "receivable" loses "dividend", against F-7. | Same overclaim. **持仓价值 and 现金价值 must follow F-7.** | **G-1** |
| `figureNoNav` | True, but it drops the conclusion: PD-0080 consequence 4 treats this as a defect of the document, and the notice does not say so. A reader may also add up the rows below. | Same. 组合总额 differs from the 组合总值 of `figurePartialNotNav`. 被抑制 is acceptable in the data-suppression sense. 明确给出的零 is good. | **G-2** |

**Must the zh of `figuresNone` follow F-7? Yes.** One figure has one term on one screen. 现金价值 is an insurance term wherever it appears,
and F-7's reason does not depend on the string's position. So the parenthesis reads 组合价值、持仓市值、现金余额或应收股息价值. 组合价值 stays,
because `figureNav` also opens with it.

## 2. F-1, F-2 and F-3 as built

My expected values below are derived from the rulings, not read from the fixture. The fixture is engine output, so it proves the
**shape**; it is not an independent oracle of value.

| Case | Hand derivation | Fixture | Result |
|---|---|---|---|
| `AVAILABLE` (Example V-1) | 359,950/39 = 9,229.487…, so **9229.49**. Parts 5,128.21, 101.28, 4,000. | same | Agrees |
| `LIMITED` (Example V-2(a)) | Total as above. Weight = 200,000/359,950 = 4,000/7,199 = 0.5556327267676…, so at 12 decimals (Ruling 2.2) **0.555632726768**. | same | Agrees |
| `SUPPRESSED` (CNH 1,000 with no FX, USD 4,000) | Total `INSUFFICIENT_DATA` + `MISSING_FX_HISTORY`, no number. Partial = **4000**. Excluded components **1**, excluded holdings **0**, included **1**. | same | Agrees |
| `SUBCENT` | `T̂` = **2.01**. Parts **1.01** and **1.00** (derivation in F-3 above). | NAV `2.01`, breakdown `1.01`, `1` | Agrees |

- **F-1: built as ruled.** The stored weight sits in the NAV's own row, after the marker, labelled as a decimal fraction. Ruling 1.4's
  "55.56 %" is the same number shown at a coarser precision. The screen copies the stored value and rightly does not convert it (PD-0079).
- **F-2: built as ruled, and yes, those are the two counts I meant.**
  - `excluded_components` is Ruling 1.4a's "excluded count": `len(p.excluded)`, the components with no reporting value.
  - `excluded_holdings` is the N of the ruling's label: the excluded items of kind `POSITION` (`valuation.py`).
  - The `SUPPRESSED` case, 1 and 0, is why both must show: "excludes 0 holdings" alone would read as nothing being left out.
  - Ruling 1.4a's excluded **list** stays in the document. The excluded component's own row, with its reason, is in the list above.
- **F-3: yes, that is the rendering I ruled.** NAV 2.01, holding 1.01, cash 1, while the document's holding row says 1.
  - Ruling 2.4 item 3 allows this: a displayed part is within one quantum of its exact value (1.01 against 1.004).
  - `figuresNote` already tells the reader the parts are apportioned, and the document holds both numbers.
- **"1 USD", not "1.00 USD": accepted, no change.** Ruling 2.2 (1.12) item 1 presents derived USD with two decimals, and item 7 says the
  exponent is presentation only and `canonical_decimal` normalizes it. So the stored text is `1`, and PD-0079 forbids the client from
  formatting. No value, state or caveat changes. **For R8:** compare NAV with the oracle numerically, as item 7 says, because `2000` and
  `2000.00` are the same value.

## 3. The TEST treatment: **accepted, with G-1's wording**

Replacing four absent lines with one statement is right. Four "not in this result" lines would read as a list of empty figures, and
nothing is derived from `buckets` (PD-0080 consequence 3). The condition is also right: it applies to a non-real origin holding **none**
of the figures. A non-real document holding some still gets the list, with the mark.

## 4. The real-source no-NAV treatment: **accepted in principle; the notice is in the wrong place (G-3)**

- **A suppressed NAV keeps its row and gets no notice: correct.** That row is a real answer with a state and a reason (P5, D3.2). The
  notice would be false of it.
- **The notice does not sit where the absent line was.** It renders above the list, and the NAV group then shows its label with nothing
  under it. D3.2 rules out a blank for a metric. The reader meets "Portfolio value (NAV)" followed directly by the holding row. The
  notice belongs inside the NAV group, which is also where it is most prominent.
- **"Always stores this figure" (G-2).** The engine emits a `portfolio_value`/`REPORTING` row on the valuation path, the explicit refusal
  and the calendar gap (`engine.py:338`, `:394`, `:456`). I read those sites; I did not prove there is no other path.

## 5. The receivable lookup: **the assumed subject matches. Close the gap with G-6.**

- **By the conventions.** Ruling 1.3 values a receivable per event (`Recv_R(e, D)`), and the breakdown table keys it by `event_id`.
  Ruling 8.1 places it in an account.
- **By the code.** `engine.py:327` stores the subject `account`, `event`. `valuation.py:176` builds the ref
  `receivable:{account_id}/{event_id}`. The client's `partRef` builds the same string.
- **Run in memory on the real engine (nothing stored or written).** USD 6,000, H 100 shares, and a HKD 780 dividend with ex-date
  2025-03-31 and pay date 2025-04-04, as of 2025-04-02. By hand:
  - holding 100 × 400 × 5/39 = 200,000/39 = 5,128.205…; cash 6,000; receivable 780 × 5/39 = 100;
  - total 11,228.205…, so `T̂` = **11,228.21**;
  - floors 5,128.20 + 6,000.00 + 100.00 = 11,228.20, shortfall 1 quantum, and the holding has the only remainder, so the parts are
    **5,128.21, 6,000, 100**.

  The engine agrees, and all three refs built from the stored subjects match breakdown lines.
- **Reach.** The real-mode contract admits one opening position and USD cash, and no dividend event, so no real create can hold a receivable at
  R8. A mismatch would fail closed in any case: no number, and `figureUnreadable`.

## The required changes

| # | Severity | Problem | Fix |
|---|---|---|---|
| **G-1** | MEDIUM | `figuresNone` overclaims, and its zh and EN terms miss F-7 | Replacement text |
| **G-2** | MEDIUM | `figureNoNav` omits that this is a defect, and invites adding up the rows | Replacement text |
| **G-3** | MEDIUM | The no-NAV notice leaves the NAV group blank | Code below |
| **G-4** | LOW | **My own wording in F-2:** "All components excluded" can read as "every component is excluded" | Replacement text |
| **G-5** | LOW | The `FIGURE_LIST` comment still says the partial figure stays in the document, which contradicts F-2 | Replacement text |
| **G-6** | LOW | No engine-made receivable case | Code below |

### G-1: `testOrigin` (replace both)

```ts G-FIGURESNONE
  en.figuresNone: 'This document stores none of the listed figures (portfolio, holding, cash or dividend receivable value): it is not a valuation result. Any amounts in it are not these figures, and none of these figures is derived from them. It comes from invented test data. A figure that is not here is not a stated zero.',
  'zh-CN'.figuresNone: '本文档未存储所列的任何数字（组合价值、持仓市值、现金余额或应收股息价值）：它不是估值结果。其中的金额并非这些数字，这些数字也不由其得出。它来自测试用虚构数据。此处没有的数字并不表示为零。',
```

### G-2: `common` (replace both)

```ts G-FIGURENONAV
  en.figureNoNav: 'This result stores no portfolio value (NAV). That is not a suppressed value and not a stated zero; no portfolio total is shown. A valuation always stores this figure, so this is a defect in the document: do not take a total from the figures below.',
  'zh-CN'.figureNoNav: '该结果未存储组合价值（资产净值）。这既不是被抑制的数值，也不是明确给出的零；此处不显示任何组合总值。估值结果总会存储此数字，因此这是该文档的缺陷：请勿根据下列数字得出总值。',
```

### G-3: `web/src/RealModeApp.tsx`, `KeyFigures`

Delete this line above the list:

```tsx
{real && noNav ? <p className="figure-no-nav" role="note"><strong>{t('figureNoNav')}</strong></p> : null}
```

and make the absent branch of the group:

```tsx
{group.rows.length === 0 ? (real && group.id === 'portfolio_value' ? <p className="figure-no-nav" role="note"><strong>{t('figureNoNav')}</strong></p> : <p className="figure-absent">{t('figureAbsent')}</p>) : (
```

Remove `noNav`, and the `navStatus` import if nothing else in the file uses it. Add a test: the notice sits inside the
`data-figure-id="portfolio_value"` item, and `figure-absent` is not in that item.

### G-4: `common.en` (replace; zh is unchanged)

```ts G-EXCLUDED
    figureExcludedComponents: 'Components excluded in total (holdings, cash, receivables)',
```

### G-5: `web/src/real-mode.ts` (replace the comment above `FIGURE_LIST`)

```ts G-COMMENT
/** The figures of the single-date valuation that the screen lists, chosen by metric id and view, in this order. Not by value, not by what looks
 * interesting. `portfolio_value`/`REPORTING` is the NAV. `portfolio_value_priced_holdings` (the partial figure, "never the total") is not one of these groups: the
 * engine emits it only when the total has no number (Ruling 1.4a), and `partialBlock` shows it then, apart from the groups, with its excluded counts (PD-0035 section 2). */
```

### G-6: `tests/product/real_figures_engine_fixture.py`

Add a fifth case to `documents()`, include it in the returned mapping as `"RECEIVABLE"`, and regenerate the fixture:

```py G-RECEIVABLE
    # RECEIVABLE: an accrued dividend (Ruling 8.1, ex-date <= as-of < pay date), valued per Ruling 1.3. By hand: holding 100 x 400 x 5/39 = 200,000/39, shown 5128.21;
    # cash 6000; receivable 780 x 5/39 = 100; total 11228.21.
    w = pk.world_w()
    L = pk.Ledger()
    L.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=pk.Money(Decimal(6000), USD))
    L.add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), HKD, listing_id=w.h, quantity=Decimal(100))
    L.add(pk.A1, EventType.DIVIDEND, D(2025, 4, 4), HKD, listing_id=w.h, amount=pk.Money(Decimal(780), HKD), ex_date=D(2025, 3, 31))
    receivable = _compute(L, D(2025, 4, 2), w)
```

Add a vitest case. The groups' values are `[['11228.21'], ['5128.21'], ['6000'], ['100']]`, and the receivable part comes from the
breakdown line (a mutant that changes that line's `shown` changes the part). Do not hard-code the event id; read it from the row's subject.

## Observations (not required changes)

- **O-4.** `stale_not_stated` covers only `portfolio_value`, as F-1 said. Ruling 1.4a also states a stale share on a `LIMITED` partial
  figure. A stored weight shows on that row already. Only the gross-value-0 case would pass silently, and it needs every included component worth
  exactly 0, so no change is required now.
- **O-5.** The generator's docstring calls `SUPPRESSED` "Example V-2(c)". The case has USD 4,000 and CNH 1,000 with no holding H, so it is a variant
  of V-2(c): it takes the state and reason from that example, not its portfolio. The values were checked by hand above.
- **O-6, for R8.** S1 and S3 of the claim block read "the market value … is `quantity x p`" and "the NAV … is `quantity x p + cash`". I
  the extraction of the slots from a real document is not built yet: `lineage_of` is injected into `real_mode_routes.py`, and its default
  (`unbuilt_lineage`) refuses. So I cannot say how a real result whose NAV is `INSUFFICIENT_DATA` will be treated. Unless that extraction
  refuses it, a suppressed NAV would sit under a "may say" sentence that assumes a close exists, even with its state stated. When the
  extraction is built, decide what the block says in that state, before any real suppressed result is shown. This is not an R7 change.

## How I checked this section

- `cd web && npx vitest run src/real-mode.test.ts` on the engineer's tree: 96 passed.
- `tests.product.test_real_figures_engine_fixture` (pure, no database): 6 tests, OK.
- The fixture's rows were read directly, and my derivations above were computed separately. The receivable case ran on the real engine, in memory.
- The replacement text was not run under vitest, because I have no write path to `web/`. An in-memory check of this section's blocks
  (no file written) found: none of the replaced zh terms, no `净资产` or bare `净值`, no "real source" or "claim limits" in `figuresNone`,
  and no banned wording in the `common` strings. The engineer must run vitest and the fixture test after applying the changes, including
  the test updates G-3 and G-6 call for.
- No PostgreSQL. Nothing outside `methodology/` was changed.

---

# Two questions from the independent review of the key-figures view (2026-11-09)

**Asked by:** the main session (PM), from "F1 R7 key-figures view (PD-0079, PD-0080) — independent review (2026-11-09)" in
`reviews/TECH_REVIEW.md` (TR7F-L-1, and the "For the Quant" line).

**Rulings:** Question 1: the PM's instruction fits, and a suppressed row never shows a stale weight. Question 2: **not an engine defect**;
they are different cases. It does not matter for HG4. Looking into question 2 turned up one further client change. **2 required changes
(H-1, H-2).**

## Question 1: F-1's scope

**Your instruction fits my ruling, and a suppressed row never needs its stale weight.** My F-1 sentence "on any row where it is a string"
was too wide. That is my wording's defect, and H-1 replaces it.

- **The weight has no meaning without the number.** Ruling 1.4 item 2 states it "beside" a `LIMITED` value. Its denominator is every
  component's value. A suppressed total has a component with no value, so its weight "cannot be measured" (Ruling 1.4, "Why").
- **The engine agrees.** `ComputedMetric.__post_init__` refuses a suppressed metric that carries a stale weight. So such a row can only
  come from a defect upstream, and a screen that shows it would put a number on a suppressed state (P5).
- **What explains a suppressed row** is its state, reason and `details`. No reading of the weight is needed.

## Question 2: `SPLIT_NOT_APPLIED` and the partial figure

**Different cases. The engine is right.** "Split-unresolved" in Ruling 1.4a is a defined term from `ledger-replay` (§7, and the table at
`CP1_LEDGER_REPLAY_CONVENTIONS.md:370`): a non-integral `SPLIT` **recorded in the ledger**, whose quantity replay cannot state
(`UNRESOLVED_CONVENTION`). `SPLIT_NOT_APPLIED` is a different thing: a corroborated split **missing** from the ledger (Example V-2a).

| | Split-unresolved | `SPLIT_NOT_APPLIED` |
|---|---|---|
| Source | `ledger-replay` §7: non-integral result of a recorded `SPLIT` | `market-data` Ruling 6.4a `NOT_RECORDED`: detection outside the engine |
| Quantity | Unknown: replay gives no number | **Known:** the ledger's pre-split quantity. The price is in other units, so the holding has no value. |
| Can the sum state what it leaves out? | No. That is Ruling 1.4a's reason for `INSUFFICIENT_DATA`. | **Yes:** this listing, this account, this ledger quantity, this cause |
| Partial figure | `INSUFFICIENT_DATA` + `UNRESOLVED_CONVENTION`, no value | The included components' sum, with the holding excluded and counted |

The ruling's reason decides this: "a partial sum over an unknown set cannot state what it leaves out". A suppressed holding is the ordinary
excluded component of Ruling 1.4a, like an unpriced one. Its state is the worst of the **included** components, so `AVAILABLE` is right
(an exclusion may never make an aggregate `LIMITED`). The engine tests this by `h.quantity is None` (`valuation.py`, `_partial`), which is the
ruling's distinction.

**Run on the real engine, in memory (nothing stored or written).** USD 4,000 and listing H, as of 2025-04-02:
- **100 H with a `SOURCE_CONFLICT` suppression, flag `SPLIT_NOT_APPLIED`.** By hand, the partial is the cash alone: **4000**, excluding 1
  component, 1 holding, native 100. The engine agrees: `AVAILABLE`, the excluded item names `SPLIT_NOT_APPLIED`.
- **3 H with a recorded 1-for-2 split.** By hand, 3 × 1/2 = 1.5, which is non-integral, so the quantity is unresolved. The engine agrees:
  holding, total and partial are all `INSUFFICIENT_DATA` + `UNRESOLVED_CONVENTION`, with no value.

**Wording clarification, owed to the next `performance` change note.** It changes no behaviour, value or fixture, so no version moves now:

> In Ruling 1.4a, "split-unresolved" means `ledger-replay` §7's state of a position's quantity. It does not cover a valuation suppression
> under `market-data` Rulings 6.4 to 6.4c, where the ledger quantity is known and the holding is an excluded component.

**HG4: no effect.** Neither case can arise in the single-date check:
- `M` holds no corporate-action file (PD-0066 decision 2), so detection has no key and no suppression exists (Ruling 6.4d case (d); Ruling
  6.5 item 2). Ruling 6.5 item 1 says the quantity is 10 whatever splits occurred.
- The real-mode contract admits one opening position and no `SPLIT` event.
- The partial figure can still appear at HG4 through a missing price: cash alone, with one holding excluded. That is the case already covered.

This says nothing about whether a split occurred. N-1, N-4 and N-6 keep that open, and they stand.

### What this question turned up: H-2

In the split-unresolved run the stored partial row carries lineage `excluded_components` 0, `excluded_holdings` 0, `included_components` 0,
because `_partial` returns no counts for an unknown set. The F-2 block I ruled would show **"Holdings excluded …: 0"** and **"Components
excluded in total …: 0"** beside no number. That is the exact statement Ruling 1.4a says cannot be made, and it reads as "nothing is left out".

- **On the screen (H-2):** a count may be shown only beside a number. PD-0035 §2 ties the count to the value it qualifies. This also removes
  the counts from `NO_VALUED_COMPONENT`, where they would be true but qualify nothing, and that case's excluded rows are in the list above.
- **In the engine: no fix needed for R8.** The `0`s are in stored lineage, so the document says slightly more than the ruling allows. An absent
  count would be more exact. It cannot arise at HG4, and changing it changes result digests, so it belongs with the next `performance`
  change. **I recommend that you log it; it is not a defect in any figure.**

## The required changes

### H-1: `web/src/real-mode.ts`, `figureRow` (replaces my F-1 behaviour)

Let `hasFigure` mean: the state is `AVAILABLE` or `LIMITED`, and the row has a stored string value that shows.

- `stale_weight`: the stored `stale_weight_presented` only when the state is `LIMITED`, `hasFigure` holds, and it is a string. Otherwise null.
  This excludes a suppressed or unknown-state row, and also an `AVAILABLE` row, which by Ruling 1.4 item 3 has no weight.
- `stale_not_stated`: only on a `portfolio_value` row in state `LIMITED` with `hasFigure`, where the stored `stale_weight_presented` is null or absent.
- A `portfolio_value` row in state `LIMITED` with `hasFigure` whose stored weight is present but not a string shows `figureUnreadable`
  in the weight's place, not `figureStaleNotStated`. The engine stated something; it is the stored form that cannot be read.

**Tests to add:** a stored weight on an `INSUFFICIENT_DATA` row, on an unknown-state row and on an `AVAILABLE` row shows no weight, and the
suppressed row shows no digit from it; a numeric weight on a `LIMITED` NAV shows `figureUnreadable` and not `figureStaleNotStated`.

### H-2: `web/src/RealModeApp.tsx`, `KeyFigures`

Render the two `count(...)` lines only when `partial.row.value !== null` and `partial.row.unreadable` is false. The rest of the block is unchanged.

**Test to add:** a partial row in state `INSUFFICIENT_DATA` whose lineage holds `0` and `0` (the engine's split-unresolved row) shows no count
and no `figure-partial-count`. Add an engine-made `SPLIT_UNRESOLVED` case to `real_figures_engine_fixture.py`, using the second run above,
so the test reads an engine document. The existing `SUPPRESSED` assertions (`1` and `0`, beside the number 4000) stay.

## How I checked this section

- Both engine runs are in memory, through `performance.engine.compute`, from `tests/product/performance_kit.py`'s invented world. Expected
  values are derived above before comparison.
- No vitest run for this section, because no client code was changed by me, and H-1 and H-2 are not applied yet. The engineer must run vitest
  and the fixture test after applying them.
- No PostgreSQL. Nothing outside `methodology/` was changed.

---

# Addendum 2026-11-14: TR7F3-L-1, F-3 amended

**Author:** quant-analyst. **Asked by:** the main session (PM). **Finding:** TR7F3-L-1 (LOW), `reviews/TECH_REVIEW.md`, section
"F1 R7 key-figures view — confirmation of the last fix round (2026-11-09)".

**Provenance.** A previous quant-analyst session ruled on this finding on 2026-11-14, but its write was refused by the path guard. Its
ruling is quoted in `reviews/HANDOVER_2026-11-14_PRE_R8.md` §1.2. I checked that ruling against the code and re-derived its expected values
by hand, as if it were someone else's work. It holds. I adopt it as my own, with two clarifications that change no behaviour (marked
**Clarification** below) and one widened observation. Nothing in it is changed silently.

## Ruling: accept the reviewer's fix and amend F-3

I prefer this to recording a limit. Under the old fallback the screen can show a sum that its own numbers contradict: NAV 2.01 over parts
1 and 1, beside `figuresNote`'s "its parts are the engine's apportioned values, which add up to it exactly". That breaks P3. A missing
`breakdown` key is a broken shape, just as a non-array is, and TR7F2-L-1 already refuses a non-array. No document the engine produces
changes, for these reasons, each checked in the code:
- `ComputedMetric.to_canonical_dict` always writes the `breakdown` key (`src/performance/results.py:231`, inside the method at 219).
- A suppressed metric carries an empty breakdown by construction (`results.py:213-214`, `__post_init__` refuses any other).
- `_breakdown` (`src/performance/engine.py:349-371`) returns `()` only when one of these holds:
  - the total has no exact value, so the total is suppressed;
  - the rounding rule has no `money_decimals`, or the reporting currency is not in the minor-unit table (USD is);
  - there are no components;
  - a component has no exact value. `total_of` (`valuation.py:199-221`) then makes the total `INSUFFICIENT_DATA`, because the entries
    it sums are exactly `components()` (`valuation.py:434-435` against `168-177`).
- The call site (`engine.py:336`) also stores `()` when I-1 fails, and then the total is `_identity_failure`, which has no number
  (`engine.py:976-978`).
- So with the engine's `PerformanceRounding` and a USD reporting currency, an empty breakdown under a total with a number means there are
  no components, and so no part rows to mislead.

## 1. What each part row shows

This **replaces** the F-3 bullet "With no breakdown, or with no number on the total, each part shows its own stored `value`." It also
replaces the condition "and a non-empty stored `breakdown`" in F-3's lead sentence. **Clarification:** the handover text named only the
bullet; left in place, the lead sentence's condition would make an empty array fall outside F-3 entirely, which is the defect itself.
F-3's other bullets stay: the ref construction, "a part with no matching line shows no number", and "this is a lookup".

- **Whether the total has a number** is the NAV row's own display: there is exactly one `portfolio_value`/`REPORTING` row, and
  `figureRow(nav).value !== null`.
- **The total has a number.**
  - A part row with a number of its own shows the `shown` entry (index 1) of its matching breakdown line, and nothing else.
  - If the stored `breakdown` cannot supply that entry, the part shows no number and shows `figureUnreadable`. That covers: the key is
    absent; it is `null`; it is not an array; it is an empty array; it is malformed (TR7F-L-1); or no line matches the part.
  - A part never falls back to its own row's `value` while the total has a number.
  - A part row with no number of its own (`INSUFFICIENT_DATA`, an unknown state, or a value that is not decimal text) shows as its own
    row says, unchanged.
- **The total has no number:** `INSUFFICIENT_DATA`, an unreadable value, no NAV row, or (**Clarification**) more than one NAV row, where
  every NAV row already shows `figureUnreadable` and no number. Each part shows its own stored `value`, whatever the `breakdown` holds.
  This is the engine's suppressed shape: an empty breakdown, and parts with numbers.
- The same holds for every origin. It is a lookup. It adds, rounds and allocates nothing.

**The code change in `keyFigures`** (`web/src/real-mode.ts`, now lines 273-299): a total with a number counts as apportioned whatever the
`breakdown` holds. Line 287 becomes `apportioned = total !== null && total.value !== null`. When no lookup can be built, a part with a
number already goes through `withoutNumber` (lines 295-297), because `lookup` is null and `found` is undefined.

## 2. `figuresNote`: shown in every case, text unchanged, no suppression rule

After the amendment, the clause "Where the total has a number, its parts are the engine's apportioned values, which add up to it exactly"
is true on every path:
- While the total has a number, no part shows any number except a breakdown line. A part that cannot be given one says it is not
  readable, so no displayed number contradicts the clause.
- When the total has no number, the clause's condition is false, so it claims nothing.

The strings in `web/src/real-mode-i18n.ts` stay as they are: `common.en` line 34, `common['zh-CN']` line 73, and `testOrigin` en and zh
lines 99 and 106. These line numbers were checked on 2026-11-14 and have not drifted.

## 3. Hand-derived expected values

Derived from Ruling 2.2 (half away from zero) and Ruling 2.4 item 3 (largest remainder, ties in the fixed line order: positions, cash,
receivables), not read from the fixture. The engine-made fixture agrees: NAV `2.01`, breakdown `1.01` and `1`, exact `251/250` each.

- **SUBCENT.** 1 AAPL at 1.004 USD, plus 1.004 USD cash, valued 2025-04-02.
  - Exact values: holding 1 × 1.004 = 1.004 (= 251/250); cash 1.004; total 2.008. The third decimal is 8, so the total shown is **2.01**.
  - Each row on its own: 1.004 rounds to 1.00, stored as "1" (`canonical_decimal` normalizes; see "F-3 as built" above).
  - Breakdown: floors 1.00 + 1.00 = 2.00, so the shortfall is (2.01 − 2.00)/0.01 = 1 quantum. The remainders tie at 0.004. The fixed
    line order puts the holding first, so the lines are **"1.01"** and **"1"**, which sum to 2.01.
- **Case A: breakdown intact (unchanged).** `keyFigures` values are `[['2.01'],['1.01'],['1'],[]]` (NAV, holding, cash, receivable).
  The HTML contains `>2.01 USD<` and `>1.01 USD<`, and `>1 USD<` exactly once. `figuresNote` is present.
- **Cases B, C and D: SUBCENT with `breakdown` deleted (B), set to `[]` (C), or set to `null` (D), in both locales, on REAL.**
  - `keyFigures` values are `[['2.01'],[null],[null],[]]`, with `unreadable` false for the NAV and true for the holding and the cash.
  - The HTML contains `>2.01 USD<`, and neither `1.01` nor any `>1 USD<`.
  - It contains `figureUnreadable` exactly twice: EN "State or value not readable; no number is shown." / zh "状态或数值无法读取，不显示数值。".
  - The receivable group shows `figureAbsent`, and the locale's `figuresNote` is present.
  - `navStatus` is `NUMBER`, and `partialBlock` is null.
  - D already behaves like this today (`null` is not an array, so `brokenBreakdown` is true). B and C are the behaviour changes.
- **Case E: SUPPRESSED, the engine's own shape, unchanged by the amendment.**
  - Inputs: USD 4,000 and CNH 1,000 deposited 2025-04-02, and no CNH fixing.
  - The NAV is `INSUFFICIENT_DATA` with `MISSING_FX_HISTORY`, has no number, and stores `breakdown` `[]`.
  - The USD cash part shows `4000 USD`. The CNH cash part shows `figureNoValue`, with state `INSUFFICIENT_DATA` and reason
    `MISSING_FX_HISTORY`.
  - The partial block shows 4000 USD, with excluded holdings 0 and excluded components 1 (CNH cash is the one excluded component; it is
    not a holding).
  - Add an assertion that deleting `breakdown` from this NAV row changes nothing: the USD cash part still shows `4000 USD`.

## 4. Existing tests in `web/src/real-mode.test.ts` that pin the old fallback and must change

Line numbers checked on 2026-11-14; they match the handover's.
- **Line 953 (the test title)** says "no breakdown falls back to the row". Rename it, for example to "...an empty breakdown under a total
  with a number gives no part a number...".
- **Lines 956-957 (`none`)** become case C: `>1 USD<` zero times, `figureUnreadable` twice, `>2.01 USD<` present. Line 958 stays.
- **Lines 1213-1215:** the two expectations become case C (1214) and case B (1215). Rewrite the comment on 1213 to "an empty array, or no
  breakdown key, under a total with a number gives no part a number".
- **Line 1089 (TR7F-L-1).** It still passes under the amendment, but it stops testing what it is for: with `breakdown = []` the holding
  would be refused by the empty breakdown even if `figureRow` accepted the bad text. Move it to SUPPRESSED: set the USD
  `cash_value`/`REPORTING` row's value to the bad text. In the cash group, that row shows `figureUnreadable` and no `figure-value`; the
  CNH row still shows `figureNoValue`. The second half of that test (lines 1094-1099, the NAV made `AVAILABLE` with a bad value) is
  unchanged.
- **Lines 1149-1151 (TR7F-L-2 "own").** This fails under the amendment, because the holding no longer shows its own value. Split it:
  - NAV own value: SUBCENT with `nav.value = u` and the breakdown intact. `>u USD<` appears once.
  - Part own value: SUPPRESSED with the USD cash row's value set to `u`. `>u USD<` appears once.
  - I checked every `u` in `UNSAFE` against the other text on those two screens (`1.01`, `1`, `4000`): none collides, so "once" is exact.
- **Line 1174 (exponent "own")** and **lines 1206-1212 (non-array):** unchanged. In 1174 the NAV's own value is unreadable, so the total
  has no number and the cash part still shows its own `1`.

## 5. Observation, not a required change

The client cannot check, without summing, that the shown breakdown lines add up to the total, and the note says the screen does not sum.
Two shapes would make the clause false while every part shows a breakdown line:
- (a) breakdown lines whose `shown` entries do not add up to the total;
- (b) a breakdown line with no part row, so a shown amount is missing from the screen. (**Widened:** the handover text named only (a).)

Neither occurs in an engine document. `apportion` guarantees (a) (`numerics.py:159-178`), and `_breakdown`'s lines and the part rows are
built from the same holdings, cash and receivables (`engine.py:304-332` against `valuation.py:168-177`), so (b) cannot happen either. The
byte-exact fixture regeneration test holds the engine's exact sum (Ruling 2.4 item 3). This does not need to hold R8.

## How I checked this addendum

- Read `engine.py` `_valuation_metrics`, `_i1_status`, `_breakdown` and `_identity_failure`; `results.py` `__post_init__` and
  `to_canonical_dict`; `valuation.py` `components` and `total_of`; `numerics.py` `apportion` and `to_decimal_money`.
- Read `keyFigures`, `figureRow` and `breakdownLookup` in `web/src/real-mode.ts`, the four `figuresNote` lines in
  `web/src/real-mode-i18n.ts`, and every test in `web/src/real-mode.test.ts` that sets or deletes `breakdown`.
- Derived SUBCENT by hand (above). As an arithmetic check only, an in-memory `fractions` computation, not the engine, gave the same
  total 2.01, floors 2.00, a shortfall of 1, and tied remainders of 1/250. The fixture's SUBCENT and SUPPRESSED rows were read only after
  that, and they agree.
- No vitest run and no PostgreSQL: no client code is changed by this note. The engineer must run vitest after applying §1 and §4.
  Nothing outside `methodology/` was changed.
