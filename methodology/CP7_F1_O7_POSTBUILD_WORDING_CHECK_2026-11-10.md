# CP7 F1 O-7 post-build check: client wording, the documentation reference's binding, the INSUFFICIENT_DATA kit case (2026-11-10)

**Author:** quant-analyst. **Asked by:** the main session (PM), after O-7 was built (uncommitted) under PD-0082.
**Governs:** my ruling `methodology/CP7_F1_O7_CLAIM_LINEAGE_RULING_2026-11-10.md` (cited below as "the ruling"). That ruling's §2 S1 row, §1
and §3.1 are corrected in place by §2 of this note, and its §9.2 by §3.

**What I read:**
- `web/src/real-mode-claims.ts` (EN, ZH, EN_WITHHELD, ZH_WITHHELD) and `web/src/real-mode-i18n.ts` (the refusal);
- `web/src/real-mode.test.ts` (PHRASES, WITHHELD_PHRASES and the withheld tests);
- `src/marketdata/claim_limits.py`, `claim_render.py` and `claim_record.py`;
- `src/real_service/service.py` (create, and reproduce at lines 431-437), `src/real_service/worlds.py:181`;
- `src/persistence/real_digests.py` (`profile_digest`), `src/marketdata/profiles.py:25-32`, and the pins in `tests/product/test_marketdata_cp2c2_exit.py`
  and `test_marketdata_r4a_inputs.py:84, 1157`;
- `tests/product/test_claim_record.py`, `performance_kit.py` (FIXINGS, SESSIONS), `src/performance/results.py` (`FreshnessVector.union`) and
  `valuation.py` (`price_freshness`, `fx_freshness`).

**What I ran.** No PostgreSQL. Nothing was written outside this file and the ruling.
- `uv run ... python -m unittest tests.product.test_claim_record`: **41 tests, OK** (pure, in memory).
- `cd web && npx vitest run src/real-mode.test.ts`: **119 tests passed**.
- An in-memory comparison: the client's EN professional templates were filled from the slots of the server-rendered block (`claim_record.block_of`)
  for the AVAILABLE, LIMITED and SUPPRESSED kit cases, then compared with the server's item text. **36 items, 0 differences.** The EN professional
  tables, normal and withheld, are the server's text byte for byte.
- One in-memory engine run of the H@XHKG world as of 2025-03-27, to confirm the engineer's report in point 3. It only confirms. It derives no
  expected value (§3).

## 0. Verdict

- **Server text (`claim_limits.py`, `claim_render.py`): PASS.** It is my §5 and §6 exactly. That includes `WITHHELD_LIMIT_IDS`, `WITHHELD_SLOT_FIELDS`
  and `WITHHELD_S2_TEXT`.
- **Client EN, all depths, both variants: PASS.** No change is needed.
- **Client zh: PASS WITH REQUIRED CHANGES.**
  - W-1 is a term error (the bare 净值, against R-10).
  - W-2 and W-3 apply the F-7 term 持仓市值.
  - W-4 narrows a non-claim, so the translation is not faithful.
  - None of them is a P3 loss in EN. W-1 and W-4 are meaning errors in zh.
- **Refusal text `RW_CLAIM_RECORD_REFUSED`, EN and zh: PASS.**
- **Tests: one required addition (W-5).** It is the pin that would have caught W-1 to W-3.
- **Point 2 (`profile_digest` does not cover the reference): acceptable for R8.**
  - My wording was wrong and is corrected below.
  - One convention is fixed here: the counter rule.
  - The digest method does not change.
- **Point 3 (the US world for the INSUFFICIENT_DATA case): accepted.** All expected values agree with my hand values. My own §9.2 stated a wrong
  delay for the H@XHKG world, and that is corrected.

## 1. Wording check

The standard is that of R7 and PD-0079:
- no caveat that changes the conclusion is dropped at a simpler depth (P3);
- no forecast (P6);
- no real-origin wording outside `REAL_SOURCE`;
- status words and field names are not translated;
- the zh terms of R-10 and F-7 apply.

### 1.1 EN, item by item

| Item | Professional | Simple | Quick |
|---|---|---|---|
| S1, normal | = server | OK. It drops "inclusive" and the V1/V4 clause, and keeps both dates, the missed count, the reference and "not a verification". C1 and C2 carry the unchecked status. | OK. "{n} sessions missed since" after "{price_session_date}" keeps the split. |
| S2, normal | = server | OK | OK |
| S3, normal | = server | OK | OK |
| S4 | = server | OK. It drops the identity-fact list and the staging/reproduce sentence. The caveat "by its version, not its content" stays. | OK |
| S5, normal | = server | OK. "the session list is not stated" stays. | OK |
| C1 to C7, normal | = server | unchanged since R7 (accepted there) | unchanged since R7 |
| S1, withheld | = server | OK | OK |
| S2, withheld | = server | OK | OK |
| S3, withheld | = server | OK. State, cause, freshness and delay are all present. | OK |
| S5, withheld | = server | OK | OK |
| C1 to C3, withheld | = server | OK | OK. C2 drops "exchange's", as the normal quick C2 does. C3 drops "for this market", as the normal quick C3 does. |
| S4 and C4 to C7, withheld | the normal entries (spread) | | |

The withheld S4 and C4 to C7 are the normal entries, and each is true over a withheld NAV:
- C6's `{S1.quantity}` is a slot of the withheld S1 mapping;
- S4 names only inputs.

No string at any depth is predictive. No string carries real-origin wording into a test origin: the block renders only for `REAL_SOURCE`
(PD79-TEST, unchanged).

### 1.2 zh, item by item

The normal ZH table:
- S1 (all depths) keeps the split: 自该收盘之后至 {valuation_date}（含）… / 其后至 … / 其后已有 ….
- S3 uses 资产净值. S4 uses 约定集.
- S5 keeps "market-data/1.16 Ruling 3.2 item 5" as an identifier.
- UNVERIFIABLE and RAW are kept.
- **One term defect:** simple S1, 该持仓价值为 (W-3). This is my own R7 replacement text, which predates F-7.

The withheld ZH table:

| Item | Finding |
|---|---|
| S1, professional and simple | 持仓价值 is not the F-7 term (W-2). 资产净值的状态 is correct. |
| S1, quick | **净值状态: the bare 净值 violates R-10**. It also has 持仓价值 (W-1). |
| S2, S3, S5 | OK. 未陈述标签来源 / 资产净值（…）未予陈述 / 原因, 新鲜度, 延迟 / 未陈述标签状态、暴露窗口或 V1 声明. |
| C1 | OK |
| C2, professional and simple | It adds 经核对的 ("as checked"), which the EN withheld C2 deliberately does not carry (the ruling §6). That narrows the non-claim. It would then not cover "the close is the official closing-cross price" as an unchecked claim (W-4). The quick C2 is correct. |
| C3 | OK |

### 1.3 Refusal

- EN: "The result's claim limits could not be stated, so it was not stored".
- zh: 无法陈述该结果的声明限制，因此未存储.

Both are true for the only path that raises the code: create, before the seal, with a whole rollback (`service.py:356-370`). 声明限制 is the zh
term for "claim limits" used by `figuresNote` and `rawNote`. Neither text implies that a retry would help, and neither states a cause. **PASS.**

### 1.4 Required changes, exact text (`web/src/real-mode-claims.ts`)

**W-1** (MEDIUM, R-10 and F-7). ZH_WITHHELD `quick.S1`. Replace
```
    S1: '{S1.valuation_date} 持仓价值未予陈述：无收盘价对该持仓估值；净值状态 {S1.state}。',
```
with
```
    S1: '{S1.valuation_date} 持仓市值未予陈述：无收盘价对该持仓估值；资产净值状态 {S1.state}。',
```

**W-2** (LOW, F-7). ZH_WITHHELD `professional.S1` **and** `simple.S1`, identical today. Replace each
```
    S1: '{S1.valuation_date} 的持仓价值未予陈述：没有任何收盘价对该持仓估值，资产净值的状态为 {S1.state}。',
```
with
```
    S1: '{S1.valuation_date} 的持仓市值未予陈述：没有任何收盘价对该持仓估值，资产净值的状态为 {S1.state}。',
```

**W-3** (LOW, F-7; it corrects my own R7 text). ZH `simple.S1`. Replace
```
    S1: '{S1.valuation_date} 该持仓价值为 {S1.quantity} x p，p 为 {S1.source} 就 {S1.price_session_date} {S1.exchange} 交易日提供的收盘价（{S1.call}），其后至 {S1.valuation_date} 该交易所另有 {S1.missed_sessions} 个交易日；依据供应商文档（所有者阅读：{S1.documentation_reference}）按不复权口径（RAW）读取。标签来源：{S1.label_source}。这是供应商的声明，并非核实。',
```
with
```
    S1: '{S1.valuation_date} 该持仓的市值为 {S1.quantity} x p，p 为 {S1.source} 就 {S1.price_session_date} {S1.exchange} 交易日提供的收盘价（{S1.call}），其后至 {S1.valuation_date} 该交易所另有 {S1.missed_sessions} 个交易日；依据供应商文档（所有者阅读：{S1.documentation_reference}）按不复权口径（RAW）读取。标签来源：{S1.label_source}。这是供应商的声明，并非核实。',
```

**W-4** (LOW, the translation narrows a non-claim). ZH_WITHHELD `professional.C2` **and** `simple.C2`, identical today. Replace each
```
    C2: '不声称曾使用任何收盘价，也不声称任何收盘价是经核对的交易所官方收盘集合竞价价格。',
```
with
```
    C2: '不声称曾使用任何收盘价，也不声称任何收盘价是交易所官方收盘集合竞价价格。',
```

**W-5** (required test change, `web/src/real-mode.test.ts`). In WITHHELD_PHRASES, replace the `'zh-CN'` S1 and S3 entries
```
S1: ['未予陈述'],
S3: ['未予陈述', '新鲜度', '延迟'],
```
with
```
S1: ['持仓市值', '未予陈述', '资产净值'],
S3: ['资产净值', '未予陈述', '新鲜度', '延迟'],
```
Then add one test inside the same `describe`. `TEMPLATES` and `TEMPLATES_WITHHELD` are already imported.
```ts
    it('zh templates of both variants use the R-10 and F-7 terms at every depth', () => {
      for (const tables of [TEMPLATES['zh-CN'], TEMPLATES_WITHHELD['zh-CN']]) for (const depth of DEPTHS) {
        for (const [id, text] of Object.entries(tables[depth])) expect(text, `${depth} ${id}`).not.toMatch(/净资产|(?<!资产)净值|持仓价值/);
      }
    });
```
The regex does not touch 未经核对 or 已定价持仓价值. The latter is the PD-0079 `figurePartial` label in `real-mode-i18n.ts`, outside these tables, and
stays as accepted there.

After W-1 to W-4:
- the existing phrase checks still hold: 未予陈述, 收盘集合竞价价格 and the rest stay present;
- the W-5 test passes;
- before them, W-5 fails on S1 (W-1, W-2, W-3).

## 2. Point 2: `profile_digest` does not bind `call_adjustment.reference`

**The facts:**
- `real_digests.profile_digest` hashes `PROFILE_SET_VERSION` and, per member source, status, role, markets and admission. It does not hash
  `call_adjustment` and therefore not `reference`.
- `worlds.py:181` refuses a world whose current `profile_digest` differs from the snapshot's.
- `claim_record._valuing` copies `profile_of(source_id).call_adjustment[vendor_call].reference` at create.
- Reproduce rebuilds (K) from the same inputs and current profile table, and returns `RESULT_DIFFERS` when its canonical bytes differ from the
  stored (K) (`service.py:431-437`).
- The `profiles` module is AST-pinned (`test_marketdata_cp2c2_exit.py`, key `profiles`). The triple `(RAW, DECLARED, "PD-0066 decision 3")` is
  pinned for both Alpha Vantage `TIME_SERIES_DAILY` entries (`test_marketdata_r4a_inputs.py:84, 1157`).

**My ruling text was wrong.** "As bound by the snapshot's `profile_digest`" claims a runtime binding that does not exist. The same error is in
the ruling's §1 ("the profile the snapshot's `profile_digest` binds") and §3.1 ("bound to the context by the snapshot's `profile_digest`").

**Ruling: acceptable for R8. No new binding is required, and the digest method is not changed.**
- **What the claim needs (P9)** is that the reference shown with a root is the one the root's create used, and that any later drift is detected.
  - The first is met: (K) is written at create, stored in the response and sealed with the root. Every read renders from the stored (K), never
    from the current profile.
  - The second is met: reproduce compares the rebuilt (K) byte for byte, so a changed reference makes an old root `RESULT_DIFFERS`.
- **The remaining gap.** Two creates on one snapshot would differ only if the reference were edited in code between them **without** the profile
  set counter moving. That cannot pass silently: the AST pin and the triple pins fail on any such edit.
- **The counter rule is now a fixed convention.** It turns the review into a method rule. `profiles.py:28` lists it "for the Quant to confirm",
  and I confirm it:
  - `PROFILE_SET_VERSION`'s counter moves with any change to profile content, including any field of any `call_adjustment` entry: `adjustment`,
    `status` or `reference`.
  - Since the counter is inside `profile_digest`, such a change moves the digest, and `worlds.py:181` then refuses older snapshots.
  - So the binding is **indirect but total**: reference → profile content → counter → `profile_digest`.
  - Comment wording is not content.
- **Changing `profile_digest` to hash `call_adjustment` directly is not required.** It is a pinned method, and it would change every snapshot's
  digest and force requalification before R8. That is an owner-level choice with no method gain over the counter rule. If it is ever wanted, it is
  a new digest version, decided separately.

**Corrected text.** These replace the ruling's wording, applied in place there with a pointer here.
- The §2 S1 row, `documentation_reference`, source column: "(K) the profile's `call_adjustment[<vendor_call>].reference` for the file's
  `source_id`.
  - It is copied when (K) is built at create, from the profile table the computation used, and from then on it is protected by the seal and by
    reproduce's byte comparison of (K).
  - The snapshot's `profile_digest` does not hash it. It binds it only through `PROFILE_SET_VERSION`, whose counter moves with any `call_adjustment`
    change (post-build note §2)."
- §1, the second sub-bullet of "(K) is a copy": "the profile table at create, whose set version the snapshot's `profile_digest` holds (it does not
  hash `call_adjustment`; see the post-build note §2)".
- §3.1: "… bound to the context only through the profile set version in the snapshot's `profile_digest` (post-build note §2)".

**One clarification of the ruling's §1** ("Nothing is read from code constants at read time"). The rule is about **field values**: no slot value
comes from a code constant. The preconditions compare stored values with the method's fixed constants. Examples are P-5 (the `UNBUILT_1_16` V4
line), P-6 (`market-data/1.16`), and P-1 to P-3 (enum texts). That is correct, and it is how `claim_record._normal` does it.

A consequence to record for the V4 increment. When Test V4 is built and its line leaves `UNBUILT_1_16`, P-5 refuses at read for every stored root,
so their blocks, and with them the roots, stop rendering. That is fail-closed and correct: "no V4 record exists for this file" can no longer be
asserted unchecked. The V4 increment must therefore bring the new wording and a rule for old roots. That is not an R8 issue.

*(Refined by §5.2 below, after TR-O7-L-2: the read-time dependence is intended, but by the marker, not by the exact line text.)*

## 3. Point 3: the INSUFFICIENT_DATA kit case on AAPL@XNAS

**Accepted.** The US world is a better test than the one my §9.2 named, for two reasons.
1. It is the real HG4 path's shape: USD listing, USD cash, USD reporting, no FX leg.
2. Its delay list is the price's alone.

**My §9.2 was wrong for the H@XHKG world.** I wrote "Freshness and delay are `UNKNOWN`". Under Ruling 1.6 the NAV's freshness vector is the union
of its components: `FreshnessVector.union` takes the sorted set of the delays.
- In H@XHKG the price leg has no lookup, so it is `UNKNOWN` (`price_freshness`).
- The HKD→USD leg has the kit's 2025-03-27 fixings (8.4000 and 1.0800, both `END_OF_DAY`), so it is `END_OF_DAY` (`fx_freshness`).
- The delay is therefore `["END_OF_DAY","UNKNOWN"]`. The summary is still `UNKNOWN`, since it is the worst state over the entries.

The in-memory run confirms exactly that: state `INSUFFICIENT_DATA`, reason `MISSING_PRICE_HISTORY`, summary `UNKNOWN`, delays
`['END_OF_DAY','UNKNOWN']`, entries `CURRENCY HKD CURRENT` and `EXCHANGE_CALENDAR HKEX_SESSIONS UNKNOWN`. The ruling's §9.2 bullet is corrected in
place.

**Hand check of `test_SUPPRESSED_...`.** The inputs are USD 500 deposit and 10 AAPL transfer-in on 2025-03-25, one close on 2025-03-28 (150.00),
no FX reading, and an as-of of 2025-03-27.

| Field | Expected in the test | My hand value and reason | Agree |
|---|---|---|---|
| `valuation_date` | `2025-03-27` | the as-of | yes |
| price used | absent | the only close is 2025-03-28 > as-of, so there is no close on or before the as-of | yes |
| `metric_state`, `nav_cause` | `INSUFFICIENT_DATA`, `MISSING_PRICE_HISTORY` | an unpriced position with no history at the as-of (§32, P5) | yes |
| `freshness` | `UNKNOWN` | one entry (the XNAS calendar), state `UNKNOWN` because there is no lookup | yes |
| `delay_status` | `["UNKNOWN"]` | the price leg only. A USD position and USD cash in USD reporting have no FX leg. | yes |
| `ledger_quantity` | `10` | integer 10 as base-10 digits | yes |
| `reporting_currency` | `USD` | | yes |
| `file_hashes` | the four members, in snapshot order | §7: every file of M, in stored order. The FX member stays listed although no FX is consumed, because M is the snapshot's set and not the consumed set. | yes |
| `ledger_version` | `2` | two events | yes |
| `convention_ids` | `market-data/1.16`, `performance/1.12` | the manifest's two sets, in the §2 order | yes |
| (K) `valuing` | `[]` | no reading values the holding | yes |
| S1 / S2 / S3 / S5 / C1 / C2 / C3 text | as in the test | the §6 text with these slots | yes |

**AVAILABLE and LIMITED (H@XHKG).** These agree with my §9.2.
- **AVAILABLE**, as of 2025-03-28: missed sessions 0; freshness `CURRENT`; delay `["END_OF_DAY"]` (both legs `END_OF_DAY`, fixing on 03-28);
  ledger version `2`; `opening_cash` `500`.
- **LIMITED**, as of 2025-04-02: sessions after 03-28 up to 04-02 are 03-31, 04-01 and 04-02, so 3 missed. The kit's weekday calendar and the HKEX
  2025 calendar agree on this window; 04-04 lies outside it. That gives freshness `STALE`, reason `STALE_DATA` and delay `["END_OF_DAY"]`.

**Two follow-ups, recommended (not required for R8):**
- **A second withheld case on H@XHKG**, as of 2025-03-27. It is the only case with a two-element delay list, so it tests the ", " join in the block
  text. Hand-derived expected S3:
  `No NAV in USD on 2025-03-27 is stated. The state is INSUFFICIENT_DATA, cause MISSING_PRICE_HISTORY, freshness UNKNOWN, delay END_OF_DAY, UNKNOWN.`
- **The docstring.** The test module says its kit values come from "section 9.2". It should add that the INSUFFICIENT_DATA case uses AAPL@XNAS as
  accepted in this note §3, so a reviewer does not look for the H@XHKG world.

## 4. Summary of required changes

| Id | Where | Change |
|---|---|---|
| W-1 | `real-mode-claims.ts` ZH_WITHHELD quick S1 | 持仓价值 → 持仓市值; 净值状态 → 资产净值状态 (exact text §1.4) |
| W-2 | ZH_WITHHELD professional S1, simple S1 | 持仓价值 → 持仓市值 |
| W-3 | ZH simple S1 | 该持仓价值为 → 该持仓的市值为 |
| W-4 | ZH_WITHHELD professional C2, simple C2 | delete 经核对的 |
| W-5 | `real-mode.test.ts` | the zh withheld phrases, plus the term pin test (exact text §1.4) |
| M-1 | the ruling, §1, §2 S1 row, §3.1, §9.2 | corrected in place by me (§2 and §3 of this note) |

No server text changes. No expected value in `tests/product/test_claim_record.py` changes. *(Superseded by §5.1: P-9 moves the AVAILABLE
and LIMITED kit cases to AAPL@XNAS. No claim sentence changes.)*

## 5. Addendum after the independent review (2026-11-10): TR-O7-M-1, TR-O7-L-2, and the `.status` binding

Source: `reviews/TECH_REVIEW.md`, "F1 O-7 claim-lineage extraction (PD-0082) — independent review (2026-11-10)". In memory I ran:
- the reviewer's FX-missing world;
- the AVAILABLE and LIMITED kit cases, to read their stored values;
- two stale US worlds.

I ran no PostgreSQL. The values below are hand-derived. Those runs only show what the code does today.

### 5.1 TR-O7-M-1: ruling (b), plus a precondition the reviewer's case exposes in my own §5 text

**A finding against my own ruling, found while checking M-1. It is more serious than M-1.** My §5 S3, "The NAV in {reporting_currency} on
{valuation_date} is {quantity} x p + {cash}", and S1, "is {quantity} x p", state **no FX conversion**. They are true only when the holding trades
in the reporting currency. No precondition said so: P-7 checks only that the cash currency equals the reporting currency.
- The AVAILABLE and LIMITED kit cases, which I placed on H@XHKG in §9.2, render "The NAV in USD on 2025-03-28 is 10 x p + 500", and that block
  passes `check_block`.
- By hand from the kit:
  - p = HKD 400.00, and the 2025-03-28 fixings are USD 1.0800 and HKD 8.4000 per EUR;
  - so the NAV is 10 x 400 x 1.08 / 8.40 + 500 = 514.2857... + 500 = **USD 1014.29** (to the cent);
  - "10 x p + 500" read in USD is 4500.
- The issued document stores `holding_value`/`REPORTING` 514.29 USD and `portfolio_value`/`REPORTING` 1014.29 USD, so the block contradicts the
  stored figures.
- This is the §38.6 failure: consistent, tested, and wrong. The test literals that assert it were written from my §9.2.
- **Reach:** none at R8.
  - The real service reports in USD (`service.py:50, 65, 343`).
  - The only admitted price profile is `alphavantage.us`, market US.
  - So every real holding trades USD.

**Required: a new precondition P-9, for both variants, checked before the variant is picked.**
- **P-9:** the issued document has exactly one `holding_value` row with `view` `NATIVE`, and its `currency` equals `reporting_currency`. Otherwise
  `CLAIM_PRECONDITION`, "P-9: the holding does not trade in the reporting currency".
- Under P-9 no FX leg exists, so S1 and S3 are true as written. The reviewer's M-1 world, an HKD holding in USD reporting, refuses at P-9 before
  the withheld text is reached.

**On M-1 itself: option (b), as a precondition of the withheld variant.**
- **P-10**, withheld variant only: (K) `valuing` is empty, **and** no `holding_value` row (either view) carries a `price_date_used` lineage pair.
  Otherwise `CLAIM_PRECONDITION`, "P-10: a reading values the holding, so the withheld text does not apply".
- **Why (b) and not (a).** The only way to reach a withheld NAV with a used reading is an FX leg that cannot be valued. Wording that case by cause
  (option (a)) means stating the FX side of S1 and S3: the fixing, its date, its source and the missing leg. That is new (K) fields and a new §5,
  and it is the same method work the FX-aware normal text needs. It belongs to the increment that admits a real listing outside the reporting
  currency. I am not inventing it here. It is **recorded as an open item for that increment**.
- **Evidence that P-10 removes no R8 root.** On the US world (no FX leg):
  - a withheld NAV from missing history (§3) gives `valuing` = `[]`;
  - a withheld NAV from staleness gives `valuing` = `[]`: as of 2025-04-04, five sessions after the 2025-03-28 close, `STALE_DATA` and no
    `price_date_used`;
  - so P-10 never fires on a P-9-passing root I can construct.
  - It is a guard against the contradiction the reviewer found, not a filter.

**Does (b) leave a real root unreadable that PD-0035 §2 requires to show its partial figure? No.**
- P-9 and P-10 are checked in `block_of` **before the seal** (PD-0082 Q3). A failing create is refused whole (`RW_CLAIM_RECORD_REFUSED`), so
  no stored root becomes unreadable.
- On every root R8 can create (USD only), the withheld variant still renders, and with it the PD-0035 §2 partial figure. That is the
  MISSING_PRICE_HISTORY and STALE_DATA cases.
- The cost lies outside R8: a future real root with a non-reporting-currency holding would be **refused at create**, so its partial figure is not
  shown. That is the same open item: the increment that admits such a listing must bring the FX-aware text before such roots exist. The PM may
  want the owner to know this boundary.
- Seen in passing: a NAV withheld for a calendar coverage gap has `reason` null and empty `details`, with the cause in `causes[].note`. It
  already refuses ("an INSUFFICIENT_DATA NAV names no cause"). That is fail-closed and needs no change.

**Kit cases under P-9: hand-derived replacements for the ruling's §9.2.** The world is `us_world`: AAPL@XNAS, one close on 2025-03-28
(150.00 USD), 10 AAPL and USD 500 on 2025-03-25.
- **AVAILABLE, as of 2025-03-28:**
  - `valuation_date` and `price_session_date` are `2025-03-28`, and `missed_sessions` is `0`;
  - `exchange_mic` `XNAS`, freshness `CURRENT`, delay `["END_OF_DAY"]` (the price leg only);
  - every other field as in the current AVAILABLE literal;
  - S3 is true: 10 x 150 + 500 = USD 2000.
- **LIMITED, as of 2025-04-02:**
  - the NYSE sessions after 03-28, up to 04-02, are 03-31, 04-01 and 04-02. The 2025 NYSE calendar has no holiday there (Good Friday is 04-18),
    and the kit's weekday calendar agrees;
  - so `missed_sessions` is `3`: state `LIMITED`, freshness `STALE`, reason `STALE_DATA`, delay `["END_OF_DAY"]`, `exchange_mic` `XNAS`;
  - `price_session_date` `2025-03-28` ≠ `valuation_date` `2025-04-02`;
  - the S1 sentence in the test becomes "… delivered for the 2025-03-28 XNAS session through TIME_SERIES_DAILY; 3 sessions of that exchange lie
    after that close, up to 2025-04-02 inclusive."
- **The SUPPRESSED case** is unchanged (§3).
- **New refusal cases:**
  - H@XHKG AVAILABLE, as of 2025-03-28 with fixings → `CLAIM_PRECONDITION`, "P-9";
  - the reviewer's H@XHKG with no FX fixing, as of 2025-03-28 → `CLAIM_PRECONDITION`, "P-9" (P-9 is checked before the variant);
  - SUPPRESSED with AVAILABLE's `valuing` entry put into (K) → "P-10";
  - SUPPRESSED with a `price_date_used` pair added to the `NATIVE` holding row → "P-10".
- **Recommended:** the quote file's `request` symbol in `FILES` becomes `AAPL`, to match the listing. It is not a claim field.

**Design text.** `implementation/CP7_F1_REAL_PATH_DESIGN.md` lists P-1 to P-8. It should append: "P-9 the holding's `NATIVE` row trades in the
reporting currency (no FX leg; both variants); P-10 (withheld variant only) the claim record holds no valuing reading and no holding row has a
`price_date_used`."

### 5.2 TR-O7-L-2: the read-time check is intended, by the marker; the wording is corrected

**Ruling:** keep P-5's read-time dependence on the engine's present build state, but compare by the **marker**, not by the exact line text.
The design wording and my §1 wording are corrected to say so.
- **Why it must stay at read time.**
  - C-1 says "no V4 record exists for this file" and C2 says "unless a Test V4 record exists", both in the present tense.
  - The root's stored manifest shows that V4 was unbuilt **when the result was computed**. It cannot show that no V4 record exists **when the
    block is read**.
  - That is true exactly while the engine cannot make a V4 record, which is a fact about today's engine.
  - A stored-only check would keep printing "no V4 record exists" after V4 is built and records exist. That is a false present-tense claim (P9,
    P3).
  - So the read-time input is deliberate. Its failure mode, the block refusing, is the right one.
- **What is wrong today** is the exact-text match. Rewording the line, with no change in what is built, makes every stored root
  `REAL_UNAVAILABLE`. A cosmetic edit should not do that.
- **Required P-5**, the same check at create and at every read:
  - (i) the stored manifest's `open_items` holds exactly one line that begins `market_data: ` and contains `Ruling 3.3, Test V4`
    (`V4_NOT_BUILT_MARKER`);
  - (ii) `market11.UNBUILT_1_16` holds exactly one line containing that marker.
  - If either fails, `CLAIM_PRECONDITION`, "P-5: Test V4 is not stated as not built".
  - At create (i) holds automatically whenever (ii) does, since the manifest is fresh, so no separate create-only check is needed.
- **Determinism (P12)** holds: the output is a function of the stored root and the method version. A V4 build is a method change, and changes
  the output by design.
- **Exact corrected wording.**
  - Ruling §1 is applied in place: "No slot value is read from a code constant at read time, nor from a clock, the network or a default. The
    preconditions (§3.4) compare stored values with constants of the method (the claim list's convention set, the enum texts, the Test V4
    marker). P-5 alone also reads the engine's present build state, by that marker, at create and at every read, because C-1 and C2 state in the
    present tense that no V4 record exists."
  - `implementation/CP7_F1_REAL_PATH_DESIGN.md:2971`: replace "nothing is read from a code constant, a clock or a default." with "no field value
    is read from a code constant, a clock or a default; the preconditions compare stored values with the method's constants, and P-5 also checks,
    at every read, that the engine still has Test V4 unbuilt (C-1 and C2 say in the present tense that no V4 record exists)."
  - The `src/marketdata/claim_record.py:15` docstring gets the same correction: "No field value is read from a code constant …; P-5 reads the
    engine's V4 build state at every read, by design."
- **For the V4 increment, as before:** when the marker leaves `UNBUILT_1_16`, every stored root's block refuses until that increment brings
  wording for results computed before V4. A root's own stored data is not enough to keep rendering it.

### 5.3 The `.status` binding

**Confirmed.** The counter rule of §2 covers every field of every `call_adjustment` entry: `adjustment`, `status` and `reference`. A change of
`.status` moves `PROFILE_SET_VERSION`, hence `profile_digest`, hence the world check (`worlds.py:181`) refuses older snapshots at create and at
reproduce.

For a stored root:
- P-2 is judged at read on the **copied** `call_adjustment_status` in (K), which is sealed, not on the present table;
- so a later table change cannot alter what an existing root says;
- it is caught at reproduce, by the world check or by `RESULT_DIFFERS`;
- that is the intended split: reads state what was computed, and reproduce detects drift.

The AST pin of `profiles.py` and the triple pins (`test_marketdata_r4a_inputs.py:84, 1157`, which include `DECLARED`) stop a status edit that
leaves the counter alone.

### 5.4 Summary of the addendum's required changes

| Id | Where | Change |
|---|---|---|
| P-9 | `claim_record._lineage`, before the variant branch | the one `holding_value`/`NATIVE` row's `currency` = `reporting_currency`, else `CLAIM_PRECONDITION` "P-9: …" |
| P-10 | `claim_record._lineage`, withheld branch | (K) `valuing` empty and no `holding_value` row with `price_date_used`, else `CLAIM_PRECONDITION` "P-10: …" |
| P-5 | `claim_record._normal` | by marker: (i) stored line with the marker, (ii) exactly one marker line in `UNBUILT_1_16`; not exact text |
| K-1 | `tests/product/test_claim_record.py` | AVAILABLE and LIMITED on `us_world` with the §5.1 values; the four refusal cases; a P-5 test in which the line is reworded but keeps the marker (renders) and one in which it is removed (refuses) |
| D-1 | `implementation/CP7_F1_REAL_PATH_DESIGN.md:2971` and the precondition list; the `claim_record.py:15` docstring | the §5.1 and §5.2 wording |
| M-2 | the ruling, §1, §3.4, §6, §9.2 | applied in place by me |

No client string changes. The block's sentences are unchanged: the fix is in when they may be used.
