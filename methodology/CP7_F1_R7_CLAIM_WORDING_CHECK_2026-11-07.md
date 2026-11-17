# CP7 F1 R7: methodology check of the real-mode claim-limit wording (2026-11-07)

**Author:** quant-analyst. **Asked by:** the main session (PM). **Subject:** the uncommitted R7 client text written by the engineer:
- `web/src/real-mode-claims.ts`: the templates `EN` and `ZH` × `quick`, `simple` and `professional`;
- `web/src/real-mode-i18n.ts`: the strings that sit next to the claim block;
- `web/src/real-mode.test.ts`: the `PHRASES` table and the tests that use it.

**Checked against:**
- `implementation/CP7_F1_REAL_PATH_DESIGN.md` 7.4: S1 to S5 and C1 to C7, the R7 test clause, and the R7 row of 7.1;
- `src/marketdata/claim_render.py`, the R5 server render, with its `SLOT_FIELDS`, `S_ITEMS`, `C_ITEMS` and `SEAL_LIMIT`;
- `src/marketdata/claim_limits.py`: C-1 to C-6 and N-1 to N-9, with their `required_terms`;
- `methodology/CP2_MARKET_DATA_CONVENTIONS.md` Ruling 6.5 item 6 (the 1.16 numbered list), and §11 item 31;
- PD-0073, and `implementation/CP7_F1_R3_SEAL_PREDICATE_DISPOSITION.md` 5.2 and 5.4;
- `designs/FEATURE_DESIGN.md` D2.2 (the caveat is a fixed field; a depth may compress its wording but may not omit it).

This note rules on wording only. It changes no method, no convention, no value and no fixture.

## Verdict: **ACCEPTED_WITH_CHANGES**

**What is sound:**
- The structure is right: twelve items at every depth and in both locales, every slot filled from the lineage field that
  `claim_render.SLOT_FIELDS` names, and a refusal when a slot is missing.
- The English professional depth is the server's text exactly. I checked this mechanically, see "Agreement with the server" below.
- No string at any depth says the seal verifies identity (PD-0073; disposition 5.2).
- No string says the close was compared with another source. Every string keeps C1's dividend component `UNVERIFIABLE`.

**What needs changing:** **12 required changes (R-1 to R-12).** They are made by replacing three template tables and the test's
phrase table with the text in "Replacement text" below, plus two test additions.

**Worst problem (R-1, with R-2).** At quick depth, in both languages, the two split caveats turn into a statement that no split
exists:
- C5 reads "Split response: zero records only." and "拆股响应：仅零条记录。". It states as a fact that a split response was
  obtained and held zero records. Under PD-0066 decision 2 (option (a)) `M` holds no corporate-action file at all, so there is no
  such response.
- C4 reads "No split history claim, complete or verified." and drops N-6's first clause, "that the listing had no split".

A quick-depth reader is left with "the vendor reported no splits". That is the conclusion N-6 and N-7 exist to forbid (P3).

**Next worst:**
- R-3: at simple and quick depth, several may-not items are written as negations ("Not compared with any other source",
  "Nothing about another date", "并非经核对的官方收盘集合竞价价格", …). Shown under the heading "Does not claim" / "不声称",
  each one reads as a double negative, which can reverse it.
- R-7: zh S3 hard-codes "（单一来源）" after the reconciliation slot. A status is printed that the lineage did not supply.
- R-11: the phrase table could not catch either the worst problem or the loss of C1's second `UNVERIFIABLE`.

## The tables, item × depth × language

Key to the columns:
- **Kept?** Q1: is the caveat present with its meaning?
- **zh terms:** Q2.
- **Server:** Q3: does the text carry the server's `required_terms` for the Quant items behind it (`claim_render.S_ITEMS` and
  `C_ITEMS`)? For zh, the reviewed zh equivalent counts; status words stay untranslated (see "Agreement with the server").
- **Test catches a drop?** Q4: under the current `PHRASES` table.
- **Change:** the required change that applies.

"OK" means no finding.

### S1: holding value `quantity x p`, `RAW`, the vendor's declaration (C-1)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK | yes (`RAW`, `not a verification`) | none |
| professional | zh | OK in meaning | "实际成交口径" is understandable but not the market term. The term for an as-traded, unadjusted price is **不复权**. | OK by equivalent | yes | R-10 |
| simple | EN | OK. The V1/V4 sentence is dropped, which is precision only: "not a verification" is kept. "as read on" hides who read it. | n/a | OK | yes | editorial, carried in the R-5 table |
| simple | zh | OK | as professional | OK | yes | R-10 |
| quick | EN | Kept, but "read {date}" can be taken as the date the price was read, when it is the date the documentation was read. | n/a | OK | yes | editorial, carried in the R-5 table |
| quick | zh | Kept | as professional | OK | yes | R-10 |

### S2: the label source and the declaration (C-1)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK | partly: `RAW` is not in the table | R-11 |
| professional | zh | OK | 不复权 (R-10) | OK | partly | R-10, R-11 |
| simple | EN | OK | n/a | OK | partly | R-11 |
| simple | zh | OK | 不复权 (R-10) | OK | partly | R-10, R-11 |
| quick | EN | **No.** "Label source {..}; not a verification." does not say what is not verified: `RAW` is gone. | n/a | **lacks `RAW`** | no | **R-5** |
| quick | zh | **No.** Same as EN. | | lacks RAW | no | **R-5** |

### S3: NAV, state, freshness, delay, reconciliation (C-2, C-3, C-4)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK | **no**: the table row is empty. `SINGLE_SOURCE` is checked once, outside the removal test. | R-11 |
| professional | zh | **Hard-coded status.** "对账状态为 {reconciliation}（单一来源）" prints 单一来源 whatever the slot holds. | "净资产" means book net assets (equity). NAV is **资产净值**. | OK by equivalent | no | **R-7**, R-10 |
| simple | EN | OK | n/a | OK | no | R-11 |
| simple | zh | Hard-coded "（单一来源）", as professional | 净资产 → 资产净值 | OK by equivalent | no | **R-7**, R-10 |
| quick | EN | The values are shown without their names ("CURRENT, END_OF_DAY"), so the reader cannot tell freshness from delay. | n/a | **lacks `freshness`, `delay`** | no | **R-6** |
| quick | zh | Same as EN | 净资产 → 资产净值 | lacks 新鲜度, 延迟 | no | **R-6**, R-10 |

### S4: the named inputs and the seal limit (C-5, PD-0073, disposition 5.2)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to `SEAL_LIMIT`. Nothing says the seal verifies identity. | n/a | OK | partly: `convention`, "not … content" and `manifest` are not in the table | R-11 |
| professional | zh | **Incomplete.** The sentence on what does catch a different ledger ("the staging and the reproduce of the result") is missing. Professional depth must carry the whole item. This is not an overclaim. | 封印, 清单 and 标的身份事实 are acceptable | OK by equivalent | partly | **R-9** |
| simple | EN | OK. The staging and reproduce sentence is dropped, which is precision: it is a reassurance, not a caveat. | n/a | OK | partly | R-11 |
| simple | zh | OK | OK | OK | partly | R-11 |
| quick | EN | Kept, but "manifest origin unverified" reads as "the result's origin is unverified". Under PD-0073 the result's origin is the stored response's, and the seal does check it. The subject must stay "the engine's manifest". | n/a | OK | partly | **R-8** |
| quick | zh | Same as EN ("清单来源未核实") | OK | OK | partly | **R-8** |

### S5: the lineage's label status and source, exposure window and V1 statement (C-6)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK. `UNVERIFIABLE` comes from the slot. | slot-fill test only. The table row is empty. | R-11 |
| professional | zh | OK | "暴露窗口" and "谱系" are acceptable | OK | slot-fill only | R-11 |
| simple | EN | OK | n/a | OK | slot-fill only | R-11 |
| simple | zh | OK | OK | OK | slot-fill only | R-11 |
| quick | EN | Kept: "Label {status} / {source}" carries both values, though the names are gone | n/a | OK | slot-fill only | editorial, carried in the R-5 table |
| quick | zh | Kept | OK | OK | slot-fill only | as EN |

### C1: verified as-traded; split label `UNVERIFIABLE`; dividend component `UNVERIFIABLE` (N-1, N-2, N-3)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK | **No, for the second `UNVERIFIABLE`.** A text that keeps the split's `UNVERIFIABLE` and drops the dividend's passes, because `includes` counts one. `declaration` is not in the table. | **R-11** |
| professional | zh | OK in meaning | "股息部分" reads as "the dividend part of the value". The item is the dividend **adjustment** component of the series: **股息调整部分**. "拆股标签" → **拆股调整标签**. "按实际成交口径" → **不复权**. "备案文件" (registration filing) → **监管申报文件**. | OK by equivalent | as EN; "核实" alone is too generic to catch anything | R-10, R-11 |
| simple | EN | OK in content. Under "Does not claim" the form "Not verified: …" is ambiguous. | n/a | OK | as above | **R-3**, R-11 |
| simple | zh | OK in content. Form "未核实：…" under 不声称. | as professional | OK by equivalent | as above | **R-3**, R-10 |
| quick | EN | **N-3 is dropped.** "not verified as-traded" survives, but "the vendor's declaration … checked" is gone. | n/a | **lacks `declaration`** | no | **R-4**, R-3 |
| quick | zh | **N-3 is dropped.** "未核实。" stands alone: what is not verified is lost (both "as-traded" and "declaration"). | as professional | lacks the equivalents | no ("核实" matches the dangling word) | **R-4**, R-3, R-10 |

### C2: not the official closing-cross price as checked; single-source (N-4)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK | yes; "unchecked" is not checked | R-11 |
| professional | zh | OK | 收盘集合竞价价格, 单一来源 and 未经核对 are correct | OK | yes | none |
| simple | EN | **Form.** "Not the official closing-cross price as checked" has no subject. Under "Does not claim" it reads as "does not claim it is not the official close". | n/a | OK | yes | **R-3** |
| simple | zh | **Form.** "并非经核对的…" under 不声称 is the same double negative | OK | OK | yes | **R-3** |
| quick | EN | Form as simple; "unchecked" is dropped. That loss is precision only, because single-source is kept. | n/a | OK | yes | **R-3** |
| quick | zh | Form as simple | OK | OK | yes | **R-3** |

### C3: no comparison with any other source (N-5)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK | yes | none |
| professional | zh | OK | OK | OK | yes | none |
| simple | EN | Content OK. Form: "Not compared …" under "Does not claim" | n/a | OK | yes | **R-3** |
| simple | zh | Content OK. Form: "未与…比较" under 不声称 | OK | OK | yes | **R-3** |
| quick | EN | Content OK. "there is none" is dropped, which is precision. Form as simple. | n/a | OK | yes | **R-3** |
| quick | zh | as quick EN | OK | OK | yes | **R-3** |

### C4: no claim that the listing had no split, or that split history is complete or verified (N-6)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK | **no**: "had no split" is not in the table | R-11 |
| professional | zh | OK | "该证券" → "该上市标的", to match the UI's 上市标的 for listing | OK | no | R-10 |
| simple | EN | OK. "in any period" is dropped, which is acceptable. | n/a | OK | no | R-11 |
| simple | zh | OK | OK | OK | no | R-11 |
| quick | EN | **No.** "No split history claim, complete or verified." drops "that the listing had no split". | n/a | OK (`split history` is present) | **no** | **R-2** |
| quick | zh | **No.** "不涉及拆股历史（完整或已核实）。" drops it the same way. | OK | OK | no | **R-2** |

### C5: nothing about a split response beyond "zero records at R" (N-7)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK | **no**: "if one exists" is not in the table | R-11 |
| professional | zh | OK. "（若存在）" and "R 时刻" are both kept. | OK | OK | no | none |
| simple | EN | **No.** "An empty split response shows zero records and nothing more." drops "if one exists" and "at R", and reads as if a response exists. Form as R-3. | n/a | OK | no | **R-1** |
| simple | zh | **No.** "空的拆股响应只表示零条记录。" is the same | OK | OK | no | **R-1** |
| quick | EN | **No, it overclaims.** "Split response: zero records only." states a fact about a response `M` does not hold, and reads as "no splits". | n/a | OK (`zero records` is present) | **no** | **R-1** |
| quick | zh | **No, it overclaims.** "拆股响应：仅零条记录。" is the same | OK | OK | no | **R-1** |

### C6: the quantity is not verified and not the owner's holding; it is a ledger fact (N-8)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK | yes; "verified" is not checked | R-11 |
| professional | zh | OK | 账本事实 and 所有者的持仓 are correct | OK | yes | none |
| simple | EN | Content OK. **Form:** a positive sentence ("The quantity … is a ledger fact …") under "Does not claim" reads as "does not claim it is a ledger fact". | n/a | OK | yes | **R-3** |
| simple | zh | Same as EN | OK | OK | yes | **R-3** |
| quick | EN | Same as EN simple | n/a | OK | yes | **R-3** |
| quick | zh | Same as EN simple | OK | OK | yes | **R-3** |

### C7: nothing about another date, a return, performance or risk (N-9)

| Depth | Lang | Kept? | zh terms | Server | Test catches a drop? | Change |
|---|---|---|---|---|---|---|
| professional | EN | OK. Identical to the server. | n/a | OK | partly: only "another date" is in the table, so dropping "return" or "risk" passes | R-11 |
| professional | zh | OK | 收益 for return is correct | OK | partly | R-11 |
| simple | EN | Content OK. Form: "Nothing about …" under "Does not claim" is a double negative. | n/a | OK | partly | **R-3** |
| simple | zh | Content OK. Form: "不涉及…" under 不声称. | OK | OK | partly | **R-3** |
| quick | EN | as simple | n/a | OK | partly | **R-3** |
| quick | zh | as simple | OK | OK | partly | **R-3** |

### The neighbouring strings in `real-mode-i18n.ts`

No finding. The strings checked:
- `fieldAck`;
- `realOriginZh.REAL_SOURCE_CONSTRUCTED_ACCOUNT`, which agrees with the server's English labels;
- `claimsHeading`;
- `testOrigin` and `testOriginZh`.

They agree with C6 and with the origin rule of 7.4: the account is constructed by the project, it is not the owner's holding, and
there is no real-source wording over test data.

The headings `claimsMayNot` ("Does not claim" / "不声称") are UI wording and outside my remit. R-3 makes the items read correctly
under them as they stand. The zh items then begin with 不声称 under the heading 不声称. That repetition is redundant but
unambiguous. Whether to soften it with a heading such as "不作以下声称" is the designer's call.

## The required changes

| # | Severity | Item, depth, locale | Problem | Fix |
|---|---|---|---|---|
| **R-1** | HIGH | C5; simple and quick; EN and zh | "if one exists" and "at R" are dropped. Quick states a zero-record split response as a fact, which reads as "no splits". `M` holds no corporate-action file (PD-0066 d2). | Replacement tables |
| **R-2** | HIGH | C4; quick; EN and zh | N-6's "that the listing had no split" is dropped | Replacement tables |
| **R-3** | MEDIUM | C1 to C7; simple and quick; EN and zh | The items are written as negations or as positive statements. Under "Does not claim" / "不声称" they read as double negatives. Every C-item must name **the claim not made**: EN starts with "That …" or "Anything …", as professional does; zh starts with "不声称", as zh professional does. | Replacement tables; form test in R-11 |
| **R-4** | MEDIUM | C1; quick; EN and zh | N-3 (the vendor's declaration unchecked) is dropped. zh "未核实。" stands alone. | Replacement tables |
| **R-5** | MEDIUM | S2; quick; EN and zh | `RAW` is dropped (a required term of C-1). Also carries the editorial fixes to S1 and S5 quick and S1 simple EN noted in the tables. | Replacement tables |
| **R-6** | LOW | S3; quick; EN and zh | The names freshness and delay are dropped (required terms of C-3) | Replacement tables |
| **R-7** | MEDIUM | S3; professional and simple; zh | "（单一来源）" is hard-coded after the reconciliation slot. A slot's status must come from the lineage, never from the template (7.4, S2's rule; the `claim_render` docstring). `SINGLE_SOURCE` stays untranslated. A zh gloss of it is allowed only from a table keyed by the value that refuses an unknown value. Removing the gloss is the fix given here. | Replacement ZH table |
| **R-8** | LOW | S4; quick; EN and zh | "manifest origin unverified" loses the subject, the **engine's** manifest. A reader can take it as "the result's origin is unverified", which PD-0073 contradicts. Also states "not content". | Replacement tables |
| **R-9** | LOW | S4; professional; zh | The professional-depth sentence on staging and reproduce is missing | Replacement ZH table |
| **R-10** | MEDIUM | zh, all depths | Terminology, see the R-10 list below | Replacement ZH table |
| **R-11** | MEDIUM | `real-mode.test.ts` `PHRASES` | It cannot catch R-1, R-2 or R-4, or a dropped second `UNVERIFIABLE` in C1. It omits server required terms (`RAW` in S2, `freshness` and `delay` in S3, `convention` in S4, `declaration` in C1). zh "核实" is too generic. | Replacement table, plus the added test below |
| **R-12** | LOW | test | Nothing pins the English professional text to the server render. Today they are identical (checked below), but a later change to `claim_limits.py` or `SEAL_LIMIT` would make them differ silently, because the client renders its own text from the slots and never shows `items[].text`. | Add a pinning test (below) |

**R-10, the zh terms:**
- as-traded (RAW): **不复权（RAW，即实际成交价）** at first use, then **不复权**;
- dividend component: **股息调整部分**;
- split label: **拆股调整标签**;
- NAV: **资产净值**. 净资产 is balance-sheet equity;
- a filing: **监管申报文件**. 备案 is a registration record;
- the listing: **上市标的**, as the UI's `fieldListing` says.

**Terms I checked and accept:**
- 拆股 (split);
- 股息 (dividend);
- 单一来源 (single-source);
- 未经核对 (unchecked) and 并非核实 (not a verification). The pair keeps EN's distinction between checked and verified;
- 收盘集合竞价价格 (closing-cross price);
- 账本事实 (ledger fact);
- 所有者的持仓 (owner's holding);
- 公司行动 (corporate action; HKEX usage. Mainland usage is 公司行为; either is correct);
- 新鲜度 (freshness);
- 延迟 (delay);
- 对账 (reconciliation);
- 暴露窗口 (exposure window);
- 谱系 (lineage);
- 标的身份事实 (instrument identity facts);
- 复现 (reproduce);
- 暂存 (staging).

Status words (`RAW`, `UNVERIFIABLE`, `SINGLE_SOURCE`, `V1`, `V4`) stay untranslated (P3).

## Replacement text (apply verbatim)

**In `web/src/real-mode-claims.ts`:**
- **(a)** Replace the `simple` and `quick` members of `const EN` with block **R7-EN**. The EN `professional` member is unchanged.
- **(b)** Replace the whole `const ZH` with block **R7-ZH**.

**In `web/src/real-mode.test.ts`:**
- **(c)** Replace `const PHRASES` with block **R7-PHRASES**.
- **(d)** Add the test in block **R7-TEST-FORM** inside the `describe(\`${locale} / ${depth}\`)` loop, next to the existing tests.
- **(e)** Add a pinning test for R-12. How it is built is the engineer's choice; one option is a Python test that renders
  `claim_render.render_claim_block` over a lineage and compares each item with the TS template filled from the same slots, as my
  check below does. It must fail on any difference between the client's EN professional text and the server's `items[].text`.

```ts R7-EN
  simple: {
    S1: 'On {S1.session_date} the holding is worth {S1.quantity} x p, where p is the close from {S1.source} ({S1.call}, {S1.exchange} session), read as RAW as-traded on the vendor\'s documentation as the owner read it on {S1.reading_date}. Label source: {S1.label_source}. This is the vendor\'s declaration, not a verification.',
    S2: 'Label source: {S2.label_source}. RAW as-traded is the vendor\'s declaration, not a verification.',
    S3: 'NAV in {S3.reporting_currency} on {S3.session_date}: {S3.quantity} x p + {S3.cash}. State {S3.state}, freshness {S3.freshness}, delay {S3.delay}, reconciliation {S3.reconciliation}.',
    S4: 'Inputs: file hashes ({S4.file_hashes}), ledger version {S4.ledger_version}, convention id {S4.convention_id}. The storage seal checks the ledger by its version, not its content, and does not verify the instrument identity facts or the origin in the engine\'s manifest.',
    S5: 'Label status {S5.label_status}, label source {S5.label_source}, exposure window {S5.exposure_window}, V1 events in M: {S5.v1_statement}.',
    C1: 'That the split label is verified (it is UNVERIFIABLE); that the dividend component is verified (it is UNVERIFIABLE, and nothing is known about any such dividend); or that the series is verified as-traded, or the vendor\'s declaration checked against the exchange or a filing.',
    C2: 'That p is the exchange\'s official closing-cross price as checked: it is single-source and unchecked.',
    C3: 'That the close was compared with any other source: there is none for this market.',
    C4: 'That the listing had no split, or that its split history is complete or verified, in any period.',
    C5: 'That an empty split response, if one exists, shows more than zero records at the retrieval time R.',
    C6: 'That the quantity {S1.quantity} is verified or is the owner\'s holding: it is a ledger fact the project entered.',
    C7: 'Anything about another date, a return, or any performance or risk figure.',
  },
  quick: {
    S1: '{S1.session_date}: {S1.quantity} x p; p = {S1.source} close ({S1.call}, {S1.exchange}); RAW per the vendor\'s documentation, read by the owner {S1.reading_date}; label source {S1.label_source}; not a verification.',
    S2: 'Label source {S2.label_source}; RAW is the vendor\'s declaration, not a verification.',
    S3: 'NAV ({S3.reporting_currency}, {S3.session_date}) {S3.quantity} x p + {S3.cash}; state {S3.state}, freshness {S3.freshness}, delay {S3.delay}, reconciliation {S3.reconciliation}.',
    S4: 'Inputs: hashes {S4.file_hashes}; ledger version {S4.ledger_version}; convention {S4.convention_id}. Seal: checks the ledger by version, not content; does not verify the instrument identity facts or the engine-manifest origin.',
    S5: 'Label status {S5.label_status}, source {S5.label_source}; exposure window {S5.exposure_window}; V1 events in M: {S5.v1_statement}.',
    C1: 'That the series is verified: split label UNVERIFIABLE, dividend component UNVERIFIABLE; RAW is the vendor\'s declaration, unchecked.',
    C2: 'That p is the official closing-cross price as checked: it is single-source, unchecked.',
    C3: 'That the close was compared with any other source (there is none).',
    C4: 'That the listing had no split, or that its split history is complete or verified.',
    C5: 'That an empty split response, if one exists, shows more than zero records at R.',
    C6: 'That the quantity {S1.quantity} is verified or is the owner\'s holding: it is a ledger fact.',
    C7: 'Anything about another date, a return, performance or risk.',
  },
```

```ts R7-ZH
const ZH: Record<Depth, Table> = {
  professional: {
    S1: '{S1.session_date} 当日该持仓的市值为 {S1.quantity} x p。其中 p 为 {S1.source} 通过 {S1.call} 就 {S1.session_date} {S1.exchange} 交易日提供的收盘价。p 依据供应商对该调用的文档说明按不复权口径（RAW，即实际成交价）读取，该文档由所有者于 {S1.reading_date} 阅读。标签来源为 {S1.label_source}。这是供应商的声明，并非核实：该文件不存在 V1 事件，也不存在 V4 记录。',
    S2: '标签来源为 {S2.label_source}。该序列依据供应商的声明按不复权口径（RAW）读取，并非核实（V1 与 V4 均未检查）。',
    S3: '{S3.session_date} 的资产净值（{S3.reporting_currency}）为 {S3.quantity} x p + {S3.cash}。状态为 {S3.state}，新鲜度 {S3.freshness}，延迟 {S3.delay}。对账状态为 {S3.reconciliation}。',
    S4: '已列明输入：M 的各文件及其哈希（{S4.file_hashes}）、L（账本版本 {S4.ledger_version}）以及约定标识 {S4.convention_id}。存储该结果的封印按账本的版本号（账本版本）而非账本内容核对账本；能发现账本不同的是该结果的暂存与复现。封印不核实计算所用的标的身份事实（交易币种、交易所和证券类型），也不核实引擎清单中记录的来源。',
    S5: '谱系载明标签状态（{S5.label_status}）、标签来源（{S5.label_source}）、暴露窗口 {S5.exposure_window}，以及 M 中 V1 事件的声明（{S5.v1_statement}）。',
    C1: '不声称序列的拆股调整标签已核实：它是 UNVERIFIABLE。不声称股息调整部分已核实：它是 UNVERIFIABLE。M 中没有任何公司行动记录，因此对此类股息一无所知，也不作任何声称。不声称该序列已核实为不复权（实际成交价）序列，也不声称供应商的声明已对照交易所或监管申报文件核对。',
    C2: '不声称 p 是经核对的交易所官方收盘集合竞价价格。它来自单一来源，未经核对，除非存在 V4 检验记录。',
    C3: '不声称该收盘价曾与任何其他来源比较。该市场没有其他来源。',
    C4: '不声称该上市标的在任何时期未发生拆股，也不声称其拆股历史完整或已核实。',
    C5: '不声称空的拆股响应（若存在）能说明“R 时刻零条记录”以外的任何事。',
    C6: '不声称数量 {S1.quantity} 已核实，也不声称它是所有者的持仓。它是项目录入的账本事实。',
    C7: '不声称任何关于其他日期、收益，或任何业绩或风险数字的内容。',
  },
  simple: {
    S1: '{S1.session_date} 该持仓价值为 {S1.quantity} x p，p 为 {S1.source} 提供的收盘价（{S1.call}，{S1.exchange} 交易日），依据供应商文档（所有者于 {S1.reading_date} 阅读）按不复权口径（RAW）读取。标签来源：{S1.label_source}。这是供应商的声明，并非核实。',
    S2: '标签来源：{S2.label_source}。不复权（RAW）口径是供应商的声明，并非核实。',
    S3: '{S3.session_date} 资产净值（{S3.reporting_currency}）：{S3.quantity} x p + {S3.cash}。状态 {S3.state}，新鲜度 {S3.freshness}，延迟 {S3.delay}，对账 {S3.reconciliation}。',
    S4: '输入：文件哈希（{S4.file_hashes}）、账本版本 {S4.ledger_version}、约定标识 {S4.convention_id}。封印按账本版本而非内容核对账本，不核实标的身份事实，也不核实引擎清单中的来源。',
    S5: '标签状态 {S5.label_status}，标签来源 {S5.label_source}，暴露窗口 {S5.exposure_window}，M 中的 V1 事件：{S5.v1_statement}。',
    C1: '不声称拆股调整标签已核实（它是 UNVERIFIABLE），不声称股息调整部分已核实（它是 UNVERIFIABLE，对任何此类股息一无所知），也不声称该序列已核实为不复权序列，或供应商的声明已对照交易所或监管申报文件核对。',
    C2: '不声称 p 是经核对的交易所官方收盘集合竞价价格：它来自单一来源，未经核对。',
    C3: '不声称该收盘价与任何其他来源比较过：该市场没有其他来源。',
    C4: '不声称该上市标的在任何时期未发生拆股，也不声称其拆股历史完整或已核实。',
    C5: '不声称空的拆股响应（若存在）能说明检索时刻 R 零条记录以外的任何事。',
    C6: '不声称数量 {S1.quantity} 已核实或是所有者的持仓：它是项目录入的账本事实。',
    C7: '不声称任何关于其他日期、收益，或任何业绩或风险数字的内容。',
  },
  quick: {
    S1: '{S1.session_date}：{S1.quantity} x p；p = {S1.source} 收盘价（{S1.call}，{S1.exchange}）；不复权（RAW），依据供应商文档（所有者于 {S1.reading_date} 阅读）；标签来源 {S1.label_source}；并非核实。',
    S2: '标签来源 {S2.label_source}；不复权（RAW）是供应商的声明，并非核实。',
    S3: '资产净值（{S3.reporting_currency}，{S3.session_date}）{S3.quantity} x p + {S3.cash}；状态 {S3.state}，新鲜度 {S3.freshness}，延迟 {S3.delay}，对账 {S3.reconciliation}。',
    S4: '输入：哈希 {S4.file_hashes}；账本版本 {S4.ledger_version}；约定 {S4.convention_id}。封印：按版本而非内容核对账本；不核实标的身份事实与引擎清单中的来源。',
    S5: '标签状态 {S5.label_status}，来源 {S5.label_source}；暴露窗口 {S5.exposure_window}；M 中的 V1 事件：{S5.v1_statement}。',
    C1: '不声称已核实：拆股调整标签 UNVERIFIABLE，股息调整部分 UNVERIFIABLE；不复权口径为供应商声明，未经核对。',
    C2: '不声称 p 是经核对的收盘集合竞价价格：单一来源，未经核对。',
    C3: '不声称与其他来源比较过（没有其他来源）。',
    C4: '不声称未发生拆股，或拆股历史完整、已核实。',
    C5: '不声称空的拆股响应（若存在）说明 R 时刻零条记录以外的事。',
    C6: '不声称数量 {S1.quantity} 已核实或是所有者的持仓：它是账本事实。',
    C7: '不声称其他日期、收益、业绩或风险方面的任何内容。',
  },
};
```

```ts R7-PHRASES
const PHRASES: Record<Locale, Record<string, string[]>> = {
  en: { S1: ['RAW', 'not a verification'], S2: ['RAW', 'not a verification'], S3: ['freshness', 'delay', 'reconciliation'],
    S4: ['hashes', 'convention', 'content', 'identity facts', 'manifest'], S5: ['exposure window', 'V1'],
    C1: ['split label', 'dividend component', 'UNVERIFIABLE', 'verified', 'declaration'], C2: ['closing-cross', 'single-source', 'unchecked'],
    C3: ['compared', 'other source'], C4: ['no split', 'split history'], C5: ['if one exists', 'zero records'],
    C6: ['verified', 'ledger fact', 'owner\'s holding'], C7: ['another date', 'return', 'performance', 'risk'] },
  'zh-CN': { S1: ['RAW', '不复权', '并非核实'], S2: ['RAW', '并非核实'], S3: ['新鲜度', '延迟', '对账'],
    S4: ['哈希', '约定', '内容', '标的身份事实', '清单'], S5: ['暴露窗口', 'V1'],
    C1: ['拆股调整标签', '股息调整部分', 'UNVERIFIABLE', '已核实', '不复权', '声明'], C2: ['收盘集合竞价价格', '单一来源', '未经核对'],
    C3: ['比较', '其他来源'], C4: ['未发生拆股', '拆股历史'], C5: ['若存在', '零条记录'],
    C6: ['已核实', '账本事实', '所有者的持仓'], C7: ['其他日期', '收益', '业绩', '风险'] },
};
```

```ts R7-TEST-FORM
      it('states two UNVERIFIABLE labels in C1 (split and dividend component), and phrases every C-item as a claim not made', () => {
        const by = Object.fromEntries(items().map((item) => [item.id, item.text]));
        expect(by.C1.split('UNVERIFIABLE').length - 1).toBeGreaterThanOrEqual(2);
        for (const id of ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7']) {
          if (locale === 'en') expect(by[id], id).toMatch(/^(That|Anything) /);
          else expect(by[id].startsWith('不声称'), id).toBe(true);
        }
        expect(by.S4).not.toMatch(locale === 'en' ? /seal (verifies|checks the (instrument )?identity)/i : /封印核实|封印已核实/);
      });
```

**The phrase table's rule, so that later edits stay within it.** For each item, the EN phrases are the server's `required_terms`
for the Quant items behind it, plus:
- every clause whose loss would let the reader reach the forbidden conclusion: "no split", "if one exists", "unchecked", and the
  four subjects of N-9;
- for S4, the seal limit: "content" and "manifest".

The zh phrases are the reviewed zh equivalents of the same list. Status words appear literally in both. A phrase that a slot value
supplies (`SINGLE_SOURCE`, `UNVERIFIABLE` in S5) is covered by the slot-fill test, not by this table. A depth may shorten anything
that is not in the table.

## Agreement with the server (Q3), and how I checked

The client renders its text from `slots` and does not show the server's `items[].text`. Agreement therefore means the client's
template, filled from the same slots, says what the server says.

**My check.** I ran `$TMPDIR/r7q/check.py` with `python3 -I`; it imports only `marketdata.claim_render` and
`marketdata.claim_limits`, so it is pure, with no database. It did three things:
- it rendered the server block over an in-memory `REAL_SOURCE` lineage (status fields `SINGLE_SOURCE`, `AVAILABLE`, `CURRENT`,
  `END_OF_DAY`, `UNVERIFIABLE`, `DECLARED`; placeholders elsewhere);
- it filled every client template from the server's own `slots`;
- it checked each against the server's text and `required_terms`.

**Results:**
- The server's `check_block` returns no problem.
- **EN professional equals the server text for all twelve items**, and `SEAL_EN` equals `claim_render.SEAL_LIMIT`.
- **EN simple** carries every server required term.
- **EN quick** lacks the terms R-5, R-6 and R-4 name.
- **zh** carries no English descriptive term, as expected. I rule that a zh rendering meets a required term through its reviewed
  zh equivalent (R7-PHRASES), and that a status word stays literal. That is how I read `ClaimLimit.required_terms`' docstring
  ("in whatever wording and locale it uses them … a status word or a field name is not translated").

The slot table equals the server's (the existing vitest pins it). The kind of each item (MAY_CLAIM for S1 to S5, MAY_NOT_CLAIM for
C1 to C7) and the origin rule (the mark and no item over a non-`REAL_SOURCE` origin) agree with `render_claim_block`.

**Tests run.**
- `cd web && npx vitest run src/real-mode.test.ts` on the engineer's tree: 57 passed.
- **The replacement blocks were not run under vitest.** Copying the web tree to `$TMPDIR` was refused by the permission system.
  Instead, an in-memory Python check (stdin script, no file written) parsed the four blocks out of this note, filled them from
  the server's slots, and found no problem on any of these counts:
  - all twelve items present at each depth and locale;
  - every placeholder names a real slot, and every slot of an S-group appears in its item;
  - no brace left after filling, and no banned wording;
  - every R7-PHRASES phrase present;
  - the C-item form rule holds;
  - C1 carries `UNVERIFIABLE` at least twice;
  - S3 carries `SINGLE_SOURCE` from the slot, and no zh S3 hard-codes 单一来源;
  - EN carries all server `required_terms`;
  - EN professional still equals the server text.
- **The same check over the current templates** fails on the defects named above: R-1 to R-5 and R-10, and the form rule of R-3
  at simple and quick in both locales. So the new table and the form test would have caught them.
- The engineer should run the vitest file after applying the blocks. Nothing under `web/` was changed by me.

## Observations for the server text (not R7 changes; the client must keep agreeing with the server)

- **O-1.** `SEAL_LIMIT` says the seal "does not verify the origin recorded in the engine's manifest". Under PD-0073 the engine
  manifest carries no origin object, so the sentence is true of the four-field origin. The manifest does carry the synthetic flag,
  and the seal does check that flag (`real_fence_v1.sql`, O4a, lines 331-334). A reader may therefore take the sentence as
  understating the seal. It does not overclaim, so P3 is not breached.
  - At the next reviewed change to `claim_render.py`, I recommend: "The engine's manifest carries no origin object of its own; the
    result's origin is the one its stored response states, which the seal checks against the root."
  - The client's S4 at every depth would then follow it.
- **O-2.** C-1's sentence "That is the vendor's declaration" and "as the owner read it on {reading_date}" are written for label
  source `DECLARED` (1.16).
  - A stored result citing 1.15 says `MEMORY` (Ruling 6.5 item 6) and would render a reading the owner never made.
  - No real result citing 1.15 can exist, because real results first exist at R8 under 1.16 code, so this does not arise in R7.
  - Before any surface renders a stored 1.15-cited result, the server should choose the C-1 sentence by the label source.
