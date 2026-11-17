# CP1 ledger-replay conventions: as-of inclusion, reversals, ordering, income, transfers, splits

**Author:** `quant-analyst` subagent, dispatched by the main session (PM), 2026-09-30. Version
1.4 (§0.5) by a fresh `quant-analyst` subagent, 2026-10-01.
**Convention set ID:** `ledger-replay/1.5` (2026-10-01). It adds Ruling 0.6: how the optional
`acquired_on` date (PD-0036 §1) is read. **No 1.3 or 1.4 ruling text is changed.** The lot fold
has two modes:

- **`none` mode:** Rulings 0.1–0.4 and §1–§9 exactly as in 1.3. This mode never reads
  `acquired_on`. A state built in it is fully determined by the 1.3 text, and it **continues to
  cite `ledger-replay/1.3`**. The CP1 golden fixture (`cp1_golden/1.1`) and replay's
  `CONVENTION_SET_ID` for this mode are unchanged.
- **`FIFO/1` mode:** the same rulings, with Ruling 0.4's basis rules replaced by Rulings 0.5 and 0.6
  for cost basis only. A state built in this mode cites **`ledger-replay/1.5`** together with the
  lot method **`FIFO/1`**.
  - On a ledger with no `acquired_on` on any live event, 1.5 and 1.4 give identical output.

A later change to any RULING creates a new ID.

(Header as issued for 1.4: "`ledger-replay/1.4` … A state built in this mode cites
`ledger-replay/1.4` together with the lot method `FIFO/1`.")

**Change note, 1.4 → 1.5.** The owner added an optional, user-supplied `acquired_on` date to
`OPENING_POSITION` and to external security `TRANSFER_IN`. It may not be later than the event date
(PD-0036 §1). PD-0036 left how it is used to this role.

- **New Ruling 0.6:**
  - a third date kind, `RECORDED`;
  - `RECORDED` lots order FIFO by `acquired_on`;
  - snapshot lots keep the horizon at `S`;
  - several opening lots per position are allowed;
  - carries keep the date;
  - correction is how a date is added later;
  - the `none` mode ignores the field;
  - worked examples F-K to F-M.
- **0.5.1's table and 0.5.15 item 2 are superseded** for events that carry `acquired_on`. They stay
  as written for events without it.
- **OI-11 is answered** by PD-0036 and Ruling 0.6.
- **No earlier expected value changed.** No event in `cp1_golden` or in `cp3_golden` parts 1–3 (up to
  `1.0-part3`) carries `acquired_on`.

**Change note, 1.3 → 1.4.**

(Header as issued for 1.3: "`ledger-replay/1.3` (supersedes `ledger-replay/1.2`, same date). A
Computation Manifest's `methodology_version` (Tech Plan §6.2) should cite this ID for any state
built by CP1-C replay.")

**Change note, 1.3 → 1.4.** The owner chose FIFO as the lot-relief method (PD-0035 §1). The PM
ruled that there is one lot engine, in `domain`, shared by replay and CP3 gains (STATUS, CP3 PM
ruling 2; `performance` PF-3). This version specifies the FIFO mode of that engine.

- **New Ruling 0.5** (§0.5): lot creation, attributes and identity; carry history; relief per
  position; the candidate set; oldest acquisition date first with one date's lots relieved pro
  rata; each depleting event of a day takes the same mix; internal transfers; splits; unknown and
  mixed basis; flags, opaque lots and same-day cycles; snapshot lots; exactness; reversal and
  correction; consistency with the `none` mode; the interface the fold exposes, including what
  `market-data` Ruling 6.4c's taint by lot identity reads; known limitations; worked examples
  F-A to F-J.
- **New §11B:** build notes on `src/domain/replay.py` for the FIFO mode (read, not edited).
- **§12:** OI-10 and OI-11 added, and the OI-4 status is restated for 1.4. Existing items are
  unchanged.
- **The 1.3 statement "Out of scope, by instruction: the lot-depletion method"** (below) remains
  the 1.3 record, and it still describes the `none` mode. For the `FIFO/1` mode it is answered by
  PD-0035 §1 and Ruling 0.5.
- **No expected value in any 1.0–1.3 example changed.** CP1 fixture T1–T8 stand. In the `FIFO/1`
  mode, every value the `none` mode emits as determinate is reproduced (0.5.13).

**Change note, 1.2 → 1.3.** This version answers the CP1-C independent review
(`reviews/TECH_REVIEW.md` §20; findings C1C-1, C1C-3 and C1C-5).

- **Ruling 0.4.3 case 2 and Ruling 0.4.5 are reworded (C1C-1).** A carried basis is decided by
  the source's same-day **candidate set**, not by whether the source ends the day at 0. With a
  single candidate lot, every internal out-leg carries `c × q`, even when a same-day sale or
  another out-leg takes the rest. The 1.2 text allowed the opposite reading, because case 2
  ("ends at 0") appeared to preempt the single-lot rule. That reading was never intended: it
  withholds a value every depletion method agrees on. **Expected values:** Example 0.4-G.
- **Ruling 0.4.5 (c), inherited cause, is reworded (C1C-5).** A carried basis takes the
  source's **actual** reason, not "unresolved" for every inherited case. An inconsistent source
  gives `LEDGER_INCONSISTENT`.
- **Ruling 3.4 is new (C1C-3).** Two or more live `SPLIT`s for one position on one date are not
  combined and not applied in `ledger_seq` order. From that date the position is
  `LEDGER_INCONSISTENT`, and exactly one `SPLIT` per position per ex-date carries the combined
  ratio. **Finding F12** is a storage recommendation to match.
- **No earlier expected value changed.** Examples 3-A, 6-C and 0.4-A to 0.4-F, and fixture
  T1–T8, stand.

**Change note, 1.1 → 1.2.** This version adds **Ruling 0.4**: the cost basis that remains after
a depleting event, and the basis an internal transfer carries. It states exactly when that
basis is the same under every admissible lot-depletion method, so computing it decides nothing
PD-0021 §9 or PD-0024 §5 reserve, and exactly when it is not.

- Before 1.2, the effect table (§0.2), Ruling 6.3 and Examples 3-A and 6-C computed single-lot
  remaining basis in examples without a normative rule, and the table's wording ("depends on lot
  depletion") could be read as forbidding it. That ambiguity is removed.
- **New normative content.** A same-day rule: the lot set a depletion may draw on includes every
  acquisition dated the same day, because `ledger_seq` is entry order, not execution order.
  Also, a non-terminating proportional basis is reported as insufficient, not rounded.
- **Ruling 9.1** now states that the flag is sticky.
- **§10** records the T5/T7 disposition. **§11** adds findings R1–R6 on `src/domain/replay.py`.
- **No expected value** in any earlier example changed.
- **Engineer impact.** The 1.1 replay's `LOT_DEPLETION_UNRESOLVED` output for single-lot
  positions, and for whole-position or single-lot internal transfers, is **not** correct under
  1.2 (finding R1).

**Change note, 1.0 → 1.1.** The owner answered O1–O3, F3 and F4 in
`decisions/product/PD-0024-cp1-taxonomy-and-v1-exclusions.md`. This version adds:

- the `CURRENCY_CONVERSION` event type (new §5A);
- the `INTEREST_CHARGED` event type (§5, rewritten as rulings);
- both types in the effect table (§0.2), the event-date table (§1.2) and the ordering rule
  (§3.1);
- Ruling 9.1, confirmed as the V1 rule (short positions are not in V1);
- Ruling 1.3, cross-referenced: margin is not in V1, but negative cash stays a valid recorded
  state;
- O1, O2, O3, F3 and F4 in §11–§12, marked decided.

No other 1.0 ruling changed, and no expected value in any 1.0 example changed. Version 1.0 was
never cited by a stored result. It was superseded on its day of issue, before any
implementation.
**Authority:** PD-0021 §9 (the Engineer must not silently decide conventions; Quant is
required where implementation depends on them); CLAUDE.md invariants P12, NFR-001 and §34
(conventions are part of the method and are written down in `methodology/`).
**Inputs read:** PRD §3 (P5, P12), §5, §8.1–§8.4, §9.1–§9.7, §11.1, §12, §32, §34, §38.3 CP1;
PD-0015 Part 1; PD-0021 §7, §9, §10; PD-0024 (for 1.1); `specs/PHASE_B_CP1_IMPLEMENTATION_AUTHORITY.md`;
`implementation/FEATURE_TECH_PLAN.md` §6, §13.D, §13.E, §14; `src/domain/ledger.py` and
`src/domain/cash.py` as built (read only); `reviews/gates/PHASE_B0B_IMPLEMENTATION_PLAN.md`
§2.5, §3, §11; `methodology/HG1_ROUND4_VERIFICATION.md` §7.3.

> **This document approves nothing.** It does not ratify the CP1 golden fixture. That happens
> at CP1-D, from the implemented fixture file. §10 below is only a consistency check. It
> changes no product scope. Where a question needs the product owner, it says so and does
> not decide it.

**Label key.**

- **RULING** is binding within the Quant role's authority (methods, conventions, sufficiency
  semantics).
- **RECOMMENDATION** is an engineering or taxonomy change I believe is needed, offered as a
  finding. Someone else decides it.
- **OWNER DECISION** means a product-scope question. It is stated and left open.

**Out of scope, by instruction.** The lot-depletion method (FIFO, average or specific-lot)
and return denominators. Where a convention below depends on either, the dependency is named
and the text stops there.

**Worked examples.** Every expected value in this document was derived by hand from the
inputs shown. The derivation sits next to each value. No value comes from running
`src/` or any other code.

---

## 0. The object being defined: the replayed state `S(D, L)`

### RULING 0.1 — Two time axes, both explicit

A replayed state is a function of two arguments:

- **`D`**, the **economic as-of date**. It is a calendar date. The state is the state at the
  **end of day `D`**, and every event dated `D` is included (inclusive bound).
- **`L`**, the **ledger version**: a per-portfolio `ledger_seq` value assigned by storage.
  Only events with `ledger_seq ≤ L` exist for this replay. In the Current mode, `L` defaults
  to the latest committed version. It is always recorded in the Computation Manifest
  (Tech Plan §6.2), so the same `(D, L)` gives the same state (P12, NFR-001).

`S(D, L)` contains:

1. **Positions**, keyed by `(account_id, listing_id)`: a quantity, and a total cost basis in
   the basis currency. The basis is either known or unknown (§6.4).
2. **Cash balances**, keyed by `CashKey(account_id, currency)` (`src/domain/cash.py`). A
   balance is signed.

Portfolio-level figures are sums over accounts **within one key dimension only**:

- Positions are summed per `listing_id`. Two listings of one issuer (PRD §10.3) are **not**
  merged, because issuer aggregation is a CP5 exposure concern.
- Cash is summed per currency. Balances in different currencies are **never summed**
  (PRD §8.1, Tech Plan §13.E).
- CP1 replay contains no price, no FX rate and no valuation.

### RULING 0.2 — Event effect table (what replay does with each type)

`q` is `quantity` and `a` is `amount` (a positive magnitude). "Cash" means the key
`(account_id, event.currency)`.

| Type | Position `(account, listing)` | Cash `(account, event.currency)` | Cost basis | Flow class (§6) |
|---|---|---|---|---|
| `BUY` | `+q` | `−a` | acquisition basis `+a` (see note 1) | investment |
| `SELL` | `−q` | `+a` | reduced per **Ruling 0.4**: determinate for a single-lot position, unresolved otherwise | investment |
| `DIVIDEND` | none | `+a` | none | income |
| `INTEREST` | none | `+a` | none | income |
| `FEE` | none | `−a` | none in CP1 (see note 1) | expense |
| `TAX` | none | `−a` | none | tax |
| `DEPOSIT` | none | `+a` | none | **external** inflow |
| `WITHDRAWAL` | none | `−a` | none | **external** outflow |
| `TRANSFER_IN`, cash form | none | `+a` | none | external, or internal (§6) |
| `TRANSFER_OUT`, cash form | none | `−a` | none | external, or internal (§6) |
| `TRANSFER_IN`, security form | `+q` | none | §6.3 / §6.4 | external in kind, or internal (§6) |
| `TRANSFER_OUT`, security form | `−q` | none | reduced per **Ruling 0.4**. An internal out-leg's basis is carried to the in-leg (Ruling 0.4.5). | external in kind, or internal (§6) |
| `SPLIT` | `× new_units / old_units` (§7) | none | total unchanged | none |
| `OPENING_POSITION` | `+q` | none | `cost_basis`, or unknown | none (snapshot origin, §8) |
| `OPENING_CASH` | none | `+a` | none | none (snapshot origin, §8) |
| `INTEREST_CHARGED` (1.1) | none | `−a` | none | financing cost; **not** an external flow (§5) |
| `CURRENCY_CONVERSION` (1.1) | none | `−a` on `(account, event.currency)` **and** `+b` on `(account, b.currency)`, where `b` = `bought_amount` | none | **internal exchange**; not an external flow at portfolio or account level (§5A) |
| `REVERSAL` | removes its target (§2) | removes its target | removes its target | none |

**Note 1 — a named dependency, not decided here.** CP1 records a `BUY`'s acquisition basis as
its gross consideration `a`. A `FEE` or `TAX` attributed to a listing is **not** added to basis
in CP1. Whether transaction costs are capitalized into basis is a cost-basis convention that
CP3 needs. It also cannot be applied deterministically today, because nothing links a `FEE` to
the trade it belongs to (finding F9). **CP1 fixtures must therefore contain no listing-attributed
`FEE` or `TAX` on a trade date.** The B0b fixture contains none.

### RULING 0.3 — The event currency is the cash currency actually moved

Replay debits or credits cash in `event.currency`. So for every cash-moving event, the event
currency **must be the currency in which the account's cash was debited or credited**. That
can differ from the listing's trading currency.

The V1-native case is Southbound Stock Connect: an HKEX listing priced in HKD, settled from a
Mainland account in CNY. The event currency is CNY. The listing currency stays HKD. This is
consistent with `ledger.py`'s deferred rule that an event need not match its listing's trading
currency.

If an ingest records the HKD consideration while the account actually paid CNY, replay
correctly produces a negative HKD balance and an untouched CNY balance. That result is wrong
because the input was wrong, not because the method was. When cash in one currency is
converted into another inside the account, that is recorded as a `CURRENCY_CONVERSION` (§5A;
added in 1.1 per PD-0024 §1).

### RULING 0.4 (1.2) — Basis after a depleting event, and carried basis: when it is determinate

This ruling does **not** choose a lot-depletion method. It identifies the cases in which every
admissible method gives the same answer, so computing that answer decides nothing reserved
(PD-0021 §9, PD-0024 §5). In every other case the basis is reported unresolved.

The admissible methods are FIFO, LIFO, highest-cost-first, average cost and specific
identification: every method that selects whole units from recorded lots. All of them share
one property. **Within one lot, every unit carries the same unit cost.** A lot is the units
of one acquisition, and its total cost is spread evenly over them. No standard method
allocates cost unevenly inside a lot.

#### 0.4.1 The lot model replay must keep

- **A lot** is created, for one `(account, listing)`, by each acquiring event: a `BUY`, an
  `OPENING_POSITION`, or an external security `TRANSFER_IN`. An internal `TRANSFER_IN`
  delivers the lot or lots carried from the source (0.4.5).
- **Each lot has** a unit count `u` and either:
  - a **known** exact unit cost `c`, a rational number in one basis currency `k`, where
    `c = basis / u` at creation. For a `BUY` the basis is `amount` (§0.2 note 1). For the
    others it is `cost_basis`.
  - or an **unknown** basis (§6.4).
- **A `SPLIT`** with ratio `(n, o)` rescales every lot: `u ← u × n / o` and `c ← c × o / n`, so
  each lot's total basis `c × u` is unchanged. This holds only when the position-level result is
  integral. Otherwise §7's unresolved state governs (0.4.4 (e)).
- **The basis of a lot** is `c × u`, an exact rational. `c` is **never** materialized as a
  rounded decimal (0.4.6).

#### 0.4.2 The same-day candidate set (why `ledger_seq` may not decide basis)

For a position `(a, l)` and a date `d`, the **candidate lot set** that the day's depleting events
(`SELL`, security `TRANSFER_OUT`) may draw on is:

- every lot held at the end of `d − 1`, rescaled by any `SPLIT` dated `d` (a split is rank 0);
- **plus every lot created by an acquiring event for `(a, l)` dated `d`**, whatever its
  `ledger_seq`.

**Why.** The ledger holds dates, not execution times. `ledger_seq` is entry order and is only a
determinism tie-break (Ruling 3.1). If a same-day `BUY` could be treated as coming after a
same-day `SELL` merely because it was typed later, the reported basis would depend on data-entry
order, and different admissible methods would give different answers (Example 0.4-D).

Including all same-day acquisitions is conservative. It can only turn a determinate answer into
an unresolved one, never the reverse.

#### 0.4.3 The rule: single-lot determinacy

On date `d`, let `U` be the candidate set's total units (start-of-day units plus same-day
acquired units), and `q_dep` the total units the day's depleting events remove.

1. **No depleting event on `d`.** The lots are the start-of-day lots plus the day's
   acquisitions. The total basis is the sum of the lot bases. It is determinate, and it is
   unknown if any lot's basis is unknown (§6.4).
2. **`q_dep = U`**, so the position ends the day at exactly 0. Nothing remains in *this*
   position, so it has no remaining-basis question. Its lot set is emptied, and its own earlier
   unresolved status is cleared for later days.

   **This case says nothing about what an internal out-leg carries (1.3).** That is decided
   only by 0.4.5, from the day's candidate set. Ending at 0 neither creates nor removes
   determinacy for the receiver. In particular, a single candidate lot still carries `c × q` on
   every out-leg (0.4.5 (a), Example 0.4-G).
3. **The candidate set is exactly one lot**, with unit cost `c`, and `0 < q_dep < U`. (When
   `q_dep = U`, case 2 governs the source and 0.4.5 (a) the out-legs, with the same `c`.) At
   end of day the lot holds `U − q_dep` units at the same `c`. **Remaining basis = `c × (U − q_dep)`.**
   Every admissible method gives this, because there is one lot to draw from and every unit in
   it costs `c`. If that lot's basis is unknown, the remaining basis is **unknown**
   (`MISSING_COST_BASIS`), which is also method-independent. It is not a depletion problem.
4. **Any other case** (two or more candidate lots, `0 < q_dep < U`): the remaining basis is
   **unresolved** (`LOT_DEPLETION_UNRESOLVED`). The status is **sticky**. Later acquisitions add
   lots, but the position's total basis stays unresolved until a later day ends at exactly 0
   (case 2).

Repeated single-lot depletions on different days compose. The remaining basis at any `D` is
simply `c × u(D)`, computed from the lot's exact `c`, not from the previous day's decimal.

#### 0.4.4 Exactly where single-lot determinacy stops holding

| Situation | Determinate? | Why |
|---|---|---|
| (a) A **second lot** in the candidate set: a second `BUY`, an external `TRANSFER_IN`, or a carried lot from an internal `TRANSFER_IN` into a position that already has units | **no** once a depletion follows (case 4). Before any depletion the total is determinate (case 1). | FIFO, average and specific-lot diverge (Example 0.4-C). |
| (a′) Two lots with **identical unit cost** in the same currency | **no**, by rule in 1.2 | Mathematically every method agrees here. 1.2 deliberately does not recognize it, so one testable criterion (one lot) applies everywhere. Reporting unresolved is less informative but never wrong. |
| (a″) Lots in **different basis currencies** (for example a Southbound purchase in CNY plus one in HKD) | **no** once a depletion follows | They are different lots, and their bases are never summed (§0.1). |
| (b) **Any unknown-basis units** plus a known lot, then a depletion | **no**: `LOT_DEPLETION_UNRESOLVED` (the remainder may be known, unknown or mixed) | Which units were sold decides it. |
| (b′) A **single unknown-basis lot**, then a depletion | yes, **unknown** | It is unknown under every method (case 3). |
| (c) A **`SPLIT`** between acquisition and depletion, with an integral result | **yes**. A split rescales the lot and does not create one. | `c × u` is unchanged by a split (0.4.1). |
| (d) A **partial internal transfer out** of a single lot | **yes**, on both sides | 0.4.5 (b). |
| (e) A **`SPLIT` with a non-integral result** (§7) | **no**: quantity and basis carry `UNRESOLVED_SPLIT_FRACTION` | Cash in lieu, one candidate fractional convention, would remove basis for the fraction, so even total basis depends on the reserved convention. |
| (f) A **negative end-of-day quantity** (§9) | **no**: §9's inconsistency governs, and no basis is presented | The history is incomplete. |
| (g) An **acquisition and a depletion on the same day** with units held at the start of the day | **no**, unless the candidate set is still one lot | 0.4.2 and Example 0.4-D. Starting the day at 0, one `BUY` plus a `SELL` of part of it is determinate (one candidate lot). |
| (h) A **`REVERSAL`** of an acquisition | follows from §2 | A reversed lot never existed, at every `D`. Replay recomputes the lot set with it absent. |

#### 0.4.5 Internal security transfers: the carried basis

*Reworded in 1.3.* The pair is matched per Ruling 6.2. It is evaluated per **source position
and date `d`**, using:

- the source's candidate set `C` (0.4.2);
- its units `U`;
- `q_dep`, the total of **all** the day's depleting events on that position (sales and
  out-legs together).

**Precondition: the source is not flagged.** The rules below apply only if the source position
is not flagged on `d`. Flagged means any of these holds: its end-of-day quantity on `d` is
negative (§9); it is already `LEDGER_INCONSISTENT` (§9, Ruling 3.4); it is split-unresolved
(§7); or its basis is already unresolved by lot depletion from an earlier day (0.4.3 case 4,
sticky). In those cases (c) governs every out-leg on `d`.

- **(a) Single candidate lot** (`C` is exactly one lot, with unit cost `c` or unknown basis).
  **Every** out-leg on `d` carries one lot of `q` units at the same `c`, with carried basis
  **`c × q`** (or unknown). This holds however many other out-legs or sales the source has
  that day, and **whether or not the source ends the day at 0**.

  **Why.** Every unit in the lot costs `c`, so every admissible method assigns `c` to each moved
  unit. Which units went to the sale and which to the transfer changes nothing.

  The source keeps `U − q_dep` units at `c` (0.4.3 case 3), or nothing (case 2). Each carried
  value is then subject to 0.4.6's exactness test on its own. Examples: 6-C (3,750 / 1,875) and
  0.4-G.
- **(b) Two or more candidate lots.** An out-leg carries **every candidate lot intact** (its
  units, unit cost, basis currency and known or unknown status) **iff** its `q = U` **and** it
  is the only depleting event on the source position on `d`. That is a whole-position move.
  There is nothing to select, so this holds for any number of lots (Example 0.4-F).

  In **every other** multi-lot case, which lots moved is lot selection, and it is reserved. So
  **every** out-leg's carried basis is **unresolved** (`UNRESOLVED_CONVENTION`, detail lot
  depletion). That includes a partial move, several out-legs, and an out-leg plus a sale even
  when the source ends at 0. The source is handled by 0.4.3: its remaining basis is unresolved,
  or it is reset if it ends at 0.

  If the day's depletions on the source are **internal moves only**, the **portfolio-level**
  total basis for the listing is still determinate (unchanged). Replay may report it at
  portfolio level; it is not required in CP1. A same-day **sale** from two or more lots makes
  the portfolio total unresolved too (Example 0.4-G, G6).
- **(c) Inherited cause (C1C-5).** When the precondition fails, each out-leg's carried basis is
  `INSUFFICIENT_DATA` with **the source's own reason and detail**, never a substitute:

  | Source condition on `d` | Receiver's carried basis |
  |---|---|
  | end-of-day quantity negative on `d`, or already flagged inconsistent (§9) | `LEDGER_INCONSISTENT`, detail negative quantity |
  | two or more same-day `SPLIT`s (Ruling 3.4) | `LEDGER_INCONSISTENT`, detail multiple same-day splits |
  | split-unresolved (§7) | `UNRESOLVED_CONVENTION`, detail split fraction |
  | lot-depletion unresolved (0.4.3 case 4) | `UNRESOLVED_CONVENTION`, detail lot depletion |

  If several apply, all details are carried, and the primary reason follows the replay's
  priority order (the review, §20.2, accepted that inconsistency outranks convention).

  An unknown-basis lot is **not** a flag. Under (a) it arrives unknown (`MISSING_COST_BASIS`).

  **Why.** The reason tells the user what would resolve the value (P9, PD-0025 §1):
  - a methodology ruling resolves `UNRESOLVED_CONVENTION`;
  - a ledger correction, such as recording the missing acquisition, resolves
    `LEDGER_INCONSISTENT`.

  Relabelling an inconsistency as a convention gap points the user at the wrong remedy.
- **(d) Receiver's quantity.** The receiver's **quantity** is always the in-leg's `q`, which is a
  recorded fact, and it is `AVAILABLE` even when the carried basis is not. The receiver's
  position is **not** flagged by an inherited cause. Only its basis for the carried lot is
  insufficient, and like any insufficient lot that makes the receiver's total basis
  insufficient until its position ends a day at 0.
- **Pairing ambiguity cannot change a determinate result.** Two pairs identical in every
  Ruling 6.2 field share the same source and date. Then either `C` is one lot, so both carry the
  same `c`, or it is not, so neither is a sole whole-position move and both are unresolved.

#### 0.4.6 Exactness: no rounding; a non-terminating basis is insufficient

Unit costs and basis values are exact rationals throughout the fold. A basis value is emitted
`AVAILABLE` iff its exact value is a **terminating decimal**, meaning the reduced denominator has
no prime factor other than 2 and 5. The emitted value is exact and may have more decimal places
than the currency's minor unit, because display rounding is presentation. Otherwise the value is
`INSUFFICIENT_DATA` with a replay cause meaning *basis not exactly representable* (suggested
name `BASIS_NOT_EXACTLY_REPRESENTABLE`).

This outcome is a **state, never an exception**. Termination is tested **at the reported date**,
from the exact rational, so a non-terminating intermediate day does not taint later days
(Example 0.4-B).

**No rounding convention is named, and why.** Rounding a proportional basis needs two things
this product does not yet have:

- a currency minor-unit table (`CurrencyCode` deliberately carries none);
- an allocation rule guaranteeing that the removed and remaining parts still sum to the
  original basis.

Both are conventions. Choosing them now would fabricate precision the ledger does not hold.
Open issue OI-8.

#### 0.4.7 Known limitation: a recorded lot may aggregate several real acquisitions

An `OPENING_POSITION` or external `TRANSFER_IN` whose `cost_basis` is a broker's position total
is **one recorded lot**, even if it summarizes several purchases. Every admissible method applied
to the ledger's information then gives the pro-rata result of 0.4.3. That result equals the
average-cost figure for the underlying purchases and can differ from the broker's FIFO or
specific-lot record.

This is a data limitation, not a method choice. Any CP3 gain figure built on such a basis must
carry that caveat (P3). V1 is not tax guidance (PRD §5.3, §15.3).

#### 0.4.8 Unit basis is not part of the replayed state

The replayed state carries **total** basis per lot and per position. A unit basis
(`total / quantity`) is a derived quotient. Where a test or a surface needs it, it is computed
from two replayed values and is subject to 0.4.6's termination test.

#### Examples for Ruling 0.4 (hand-derived)

**0.4-A: one lot, a split, then a sale (the B0b T7 path).**
`BUY` 50 U for 7,500 USD on 2025-01-06: `c` = 7,500 / 50 = 150. `SPLIT` (4, 1) on 2025-02-03:
`u` = 200, `c` = 150 × 1 / 4 = 37.5. `SELL` 50 on 2025-03-03: the candidate set is one lot, and
there is no same-day acquisition.

- Remaining basis = 37.5 × 150 = **5,625 USD**.
- Cross-check: 7,500 × 150 / 200 = 5,625.
- It terminates, so it is `AVAILABLE`.

**0.4-B: non-terminating, then terminating again.**
`BUY` 6 units for 100 USD: `c` = 100/6 = 50/3.

- `SELL` 2 on day 1: `u` = 4, basis = 4 × 50/3 = 200/3 = 66.666…, which does not terminate. The
  basis is **`INSUFFICIENT_DATA`** (not exactly representable). The quantity is 4, `AVAILABLE`.
- `SELL` 1 on day 2: `u` = 3, basis = 3 × 50/3 = **50 USD**, `AVAILABLE`.
- Contrast stepwise rounding: 66.67 × 3/4 = **50.0025**. That is wrong, which is why `c` is
  carried exactly.

**0.4-C: two lots, where the methods disagree.**
Lot 1: `BUY` 100 for 1,000 USD (`c` = 10). Lot 2: `BUY` 100 for 1,200 USD (`c` = 12), on a later
date. Before any sale, the total basis is 2,200, `AVAILABLE` (case 1). Then `SELL` 50 on a later
date:

- FIFO removes 50 × 10 = 500, leaving **1,700**.
- Average cost removes 50 × 2,200/200 = 550, leaving **1,650**.
- Specific identification from lot 2 removes 50 × 12 = 600, leaving **1,600**.

The results differ, so the basis is **`LOT_DEPLETION_UNRESOLVED`**. The quantity is 150,
`AVAILABLE`.

**0.4-D: a same-day acquisition and depletion.**
Lot A: 100 units, 1,000 USD (`c` = 10), held at the start of day `d`. On `d`: seq 7 `SELL` 100,
then seq 8 `BUY` 50 for 600 USD (`c` = 12). End-of-day quantity = 100 − 100 + 50 = 50. The
candidate set is {A, B}. `q_dep` = 100 < `U` = 150, so the basis is **unresolved**.

The plausible truths:

- Sale executed first, under any method: **600**.
- Buy first, then FIFO: **600**.
- Buy first, then average cost: 1,600 × 50/150 = **533.33…**.
- Buy first, then LIFO: the sale takes 50 of B and 50 of A, leaving 50 of A = **500**.

Contrast: starting the day at 0, `BUY` 100 for 1,000, then `SELL` 40, the candidate set is one
lot. The remaining basis is 10 × 60 = **600**, `AVAILABLE`.

**0.4-E: a single unknown-basis lot.**
External `TRANSFER_IN` of 10 M with no `cost_basis`, then `SELL` 4 on a later day. The quantity
is 6. The basis is **unknown** (`MISSING_COST_BASIS`). There is no depletion cause.

**0.4-F: whole and partial internal moves of a two-lot position.**
A1 holds lot 1 (100 at `c` 10, basis 1,000) and lot 2 (100 at `c` 12, basis 1,200), both
acquired on earlier dates. A3 holds no U.

- **Whole move.** `TRANSFER_OUT` A1 200, with the matching `TRANSFER_IN` to A3, dated `d`. It is
  the only depletion on `d`, and there is no same-day acquisition.
  - A1 ends at 0 and emits no position.
  - A3: 200 units in two lots, basis 1,000 + 1,200 = **2,200 USD**, `AVAILABLE`.
  - A later A3 `SELL` 50 leaves A3 with a two-lot position, so its basis is unresolved (case 4).
- **Partial move instead**, 50 units: A1 has 150 units and A3 has 50. Both bases are
  **unresolved**. The portfolio total is 200 units and 2,200 USD, unchanged and determinate.

**0.4-G (1.3; C1C-1): a single lot emptied on one day by a sale and moves, or by several moves.**

Common start for every case: A1 holds one lot of U, 100 units for 1,000 USD, acquired on an
earlier date, so `c` = 1,000 / 100 = **10**. On day `d` there is no acquisition of U by A1. A2
and A3 hold no U. So `C` = {that lot} and `U` = 100 throughout.

| Case | Events on `d` (A1 side; every move is internal, with its matching in-leg) | `q_dep` | A1 at end of `d` | Receivers at end of `d` |
|---|---|---|---|---|
| G1 | `SELL` 40, move 60 → A3 | 100 | 0, no position | A3: qty **60**, basis 60 × 10 = **600 USD**, `AVAILABLE` |
| G2 | move 30 → A3, move 70 → A2 | 100 | 0, no position | A3: qty **30**, basis **300 USD**. A2: qty **70**, basis **700 USD**. Both `AVAILABLE`. |
| G3 (control) | move 30 → A3, move 20 → A2 | 50 | qty 50, basis 50 × 10 = **500 USD** | A3: **300 USD**. A2: **200 USD**. All `AVAILABLE`. |
| G4 | `SELL` 70, move 30 → A3 | 100 | 0, no position | A3: qty **30**, basis **300 USD**, `AVAILABLE` |
| G5 | move 100 → A3 (the only depletion) | 100 | 0, no position | A3: qty **100**, basis **1,000 USD**, `AVAILABLE`. This is also a whole move, and (a) and (b) agree. |

Conservation check: in G1 the portfolio keeps 60 units at 600, since the 40 sold left the
portfolio. In G2 it keeps 100 at 300 + 700 = 1,000. In G3 it keeps 100 at 500 + 300 + 200 =
1,000.

**Why the answer is method-independent.** Take G1. Whether the sale took the "first" 40 or the
"last" 40, every unit costs 10. The 60 moved units therefore cost 600 under FIFO, LIFO,
highest-cost-first, average cost and specific identification alike.

**Boundary cases, where the answer changes:**

- **G6. A second candidate lot the same day.** G1 plus a same-day A1 `BUY` of 20 for 240 USD
  (`c` 12). Now `C` = {lot 1, lot B}, `U` = 120 and `q_dep` = 100. A1 ends with 20 units, basis
  unresolved. A3's 60 units have basis **unresolved** (`UNRESOLVED_CONVENTION`, lot depletion).
  - The plausible truths for A3: 60 from lot 1 gives **600**; 40 from lot 1 plus 20 of B gives
    400 + 240 = **640**.
  - Portfolio: the quantity is 120 − 40 sold = **80**. The portfolio basis is also
    **unresolved**, because which lots the *sale* consumed is lot selection. Only when the day's
    depletions are internal moves alone is the portfolio total preserved (0.4.5 (b)).
- **G7. A non-terminating carried value.** One lot of 3 units for 100 USD (`c` = 100/3).
  - `SELL` 1 plus a move of 2 to A3: A3's basis = 2 × 100/3 = 66.666…, which does not
    terminate, so it is `INSUFFICIENT_DATA`, not exactly representable (0.4.6). A3's quantity 2
    is `AVAILABLE`.
  - A move of all 3 alone: 3 × 100/3 = **100 USD**, `AVAILABLE`.
- **G8. A single unknown-basis lot.** 10 units with no basis. `SELL` 4 plus a move of 6 to A3:
  A3 has qty 6 and basis **unknown** (`MISSING_COST_BASIS`). This is not a depletion cause and
  not an inconsistency.

**0.4-H (1.3; C1C-5): inherited causes.**

- **H1.** A1 holds 101 U as one lot. `SPLIT` (3, 2) on day 1: 101 × 3/2 = 151.5, which is not
  integral, so A1 is split-unresolved (§7). Day 2: internal move of 10 to A3. A3 has qty **10**,
  `AVAILABLE`, and basis `INSUFFICIENT_DATA`, **`UNRESOLVED_CONVENTION`**, detail **split
  fraction**, not lot depletion.
- **H2.** A1 holds 10 U. Same day: `SELL` 15 and an internal move of 5 to A3. A1's end of day is
  10 − 20 = −10, so A1 is inconsistent (§9). A3 has qty **5**, `AVAILABLE`, and basis
  `INSUFFICIENT_DATA`, **`LEDGER_INCONSISTENT`**, detail negative quantity.

### RULING 0.5 (1.4) — The FIFO mode of the lot fold (`FIFO/1`)

The owner chose FIFO (PD-0035 §1: "oldest lots sold first (pro rata within one date)"). The PM
ruled one lot engine, in `domain`. This ruling is the **normative definition of `FIFO/1`** for that
engine. `performance` Ruling 3.3 is its summary for CP3 (`performance/1.5` Ruling 3.3a); where
wording differs, this ruling governs. Replay never translates a currency: everything here is in
each lot's own basis currency.

#### 0.5.0 Two modes of one fold

| Mode | Basis rules | A state cites | Used by |
|---|---|---|---|
| `none` | Ruling 0.4 (0.4.1–0.4.8), unchanged | `ledger-replay/1.3` | CP1 replay output; `cp1_golden/1.1` |
| `FIFO/1` | the lot model of 0.4.1 extended by 0.5.1, and 0.5.2–0.5.12 | `ledger-replay/1.4` + `FIFO/1` | CP3 cost basis, realized and unrealized gain; `market-data` Ruling 6.4c taint |

- **The same in both modes:** event selection (§2), order (§3), cash, quantities, every flag (§7,
  §8, §9, Ruling 3.4), the snapshot horizon, and the internal-pair criteria (Ruling 6.2). Only cost
  basis differs, and the `FIFO/1` mode additionally exposes lots, relief records and carry
  histories (0.5.14).
- **The caller names the mode.** The existing CP1 replay entry point is the `none` mode, with its
  output and `CONVENTION_SET_ID` unchanged.
- **The `FIFO/1` mode is never less determinate than `none`** (0.5.13).

#### 0.5.1 Lots: creation, attributes and identity

| Acquiring event | Units `u` | Unit cost `c`, basis currency `k` | Acquisition date `a` | Date kind | Origin |
|---|---|---|---|---|---|
| `BUY` | `q` | `amount / q`, in the event currency (CNY for a Southbound purchase, Ruling 0.3) | `event_date` | `TRADE` | the event |
| `OPENING_POSITION` with `cost_basis` | `q` | `cost_basis / q`, in the event currency | `event_date` (= `S`, §8) | `ENTRY` | the event |
| external `TRANSFER_IN` with `cost_basis` | `q` | as above | `event_date` | `ENTRY` | the event |
| either of the two, without `cost_basis` | `q` | **unknown**: no `c`, no `k` (Ruling 6.4) | `event_date` | `ENTRY` | the event |
| internal `TRANSFER_IN` | the carried portions (0.5.5) | unchanged | **unchanged** (the source lot's) | unchanged | unchanged; one hop appended |

- **`cost_basis` of 0** is a known basis of 0, not an unknown one.
- **Transaction costs are never in `c`.** A `FEE` or `TAX` is never added to a lot (Note 1 of §0.2;
  `performance` Ruling 3.6).
- **Carry history.** An ordered list of hops. A hop is (source account, listing, out-leg
  `event_id`, in-leg `event_id`, date `T`). A lot created by an acquiring event has an empty
  history. Each internal move appends one hop.
- **Lot identity** = (origin `event_id`, the out-leg `event_id`s of its hops, in order).
  - Within one position, no two lots share an identity. A lot with an empty history enters a
    position only through its own acquiring event, which is unique. A carried lot enters only
    through its last hop's out-leg, and one out-leg carries at most one share of each source lot
    (0.5.5), whose identities are already distinct.
  - A remainder after partial relief keeps its identity. A carried share gets a new identity.
- **Date kind.** `TRADE` means `a` is the date the units were bought. `ENTRY` means `a` is only the
  date the units entered this portfolio; the purchase date is not recorded. `performance` Ruling
  3.7 translates `c` at `a`'s fixing only for a `TRADE` lot, or when `k` equals the reporting
  currency.
- A `SPLIT` changes `u` and `c` only (0.5.7). Nothing else ever changes a lot's attributes.

#### 0.5.2 Relief is per position

FIFO relieves only the lots of the depleting event's own position `(account, listing)`. It never
pools across accounts or across listings of one issuer. "FIFO, portfolio-wide" in `performance`
§3.2 means that the method is the same for every account. It does not mean that a sale in one
account relieves another account's lots. That also matches how brokers apply FIFO, per account.

#### 0.5.3 The candidate set

For position `(a, ℓ)` and date `d`, as in 0.4.2:

- every lot held at the end of `d − 1`, rescaled by any `SPLIT` dated `d`;
- plus every lot created on `d` by an acquiring event of the position;
- plus every carried lot delivered by an internal in-leg dated `d`;

whatever their `ledger_seq`.

#### 0.5.4 Order: oldest acquisition date first; one date's lots pro rata

Let `q_dep` be the total units of the day's depleting events on the position (`SELL`, external
`TRANSFER_OUT`, internal `TRANSFER_OUT`), and `U` the candidate set's units. When `0 < q_dep ≤ U`:

1. **Group** the candidate lots by `a`. Order the groups by `a` ascending.
2. **Walk** the groups with `need = q_dep`:
   - if `need ≥ U_g` (the group's units), every lot of the group is relieved whole, and
     `need ← need − U_g`;
   - otherwise each lot `λ` of the group relieves **`need × u_λ / U_g`** units, and `need ← 0`;
   - groups after that are untouched.
3. The **relieved portion** of `λ` has all of `λ`'s attributes, its relieved units, and basis
   `c_λ × units` (or unknown).

**Nothing else enters the order:** not `ledger_seq`, not lot identity, not unit cost, not
currency, not known or unknown basis. Lot units may become fractional rationals. They are exact,
and §7 condition 3 concerns only the position's quantity.

**Why.**

- PD-0035 §1 is "oldest lots sold first (pro rata within one date)".
- The ledger records dates, not times (0.4.2). Any fixed order among lots of one date would be
  invented, and `ledger_seq` is entry order. Pro rata is symmetric, so entry order cannot change a
  basis.
- **Carried lots keep their origin's `a`.** A receiver therefore relieves units it received before
  units it bought later, even though they arrived after its own lot was bought (Example F-D).

**Order independence.** The relief depends only on the multiset of candidate lots with their
dates and on `q_dep`. Neither depends on `ledger_seq`.

#### 0.5.5 Several depleting events on one day: each takes the same mix

Each depleting event `e` dated `d` receives **the share `q_e / q_dep` of every relieved portion**:
units and basis scaled by `q_e / q_dep`, every other attribute unchanged.

- **`SELL`:** its shares are its **relief record**. CP3 computes the realized gain from it
  (`performance` Ruling 3.8).
- **External `TRANSFER_OUT`:** its shares are its relief record. The units leave the portfolio,
  and nothing is realized (`performance` Ruling 3.8).
- **Internal `TRANSFER_OUT`:** its shares become lots of the receiving position, each with one hop
  appended (0.5.6).

**The rule for a partial internal transfer from several lots: FIFO selects which units move.** The
day's relief takes the oldest units. A move that is the day's only depletion therefore carries
exactly the oldest `q` units (Example F-D). When a sale and a move share a day, each carries the
same proportion of every relieved portion (Example F-E).

**Why pro rata across the day's events.** The ledger has no time of day. Any priority, such as
sales before moves, moves before sales, or `ledger_seq`, would be invented or entry-order
dependent. Pro rata is the one symmetric rule. It is a known difference from a broker that
executed the sale before the move (0.5.15).

#### 0.5.6 Internal transfers: carrying lots

- **Pairs** are matched per Ruling 6.2. Within a group of mutually matching legs on one day
  (identical in every 6.2 field), out-legs are matched to in-legs in **ascending `event_id` order
  (UUID integer)**, not `ledger_seq`.
  - Values never depend on the pairing, because matching legs share source, receiver and
    quantity.
  - The pairing order matters only for the in-leg `event_id` written into a hop. Fixing it by
    `event_id` keeps the carry history independent of entry order (Ruling 11.3 item 1 of
    `performance`).
- **Evaluation order** within a day: a position is resolved after every source of an internal
  in-leg it receives that day (as in 1.3, finding R5). Its candidate set then includes the carried
  lots.
- **Conservation (identity I-5).** For each pair: the lots the in-leg delivers have, per basis
  currency, exactly the basis the out-leg's relief record carries; the same units; the same known
  or unknown status; the same acquisition dates and kinds.
- **Precondition.** The source is not flagged and holds no opaque lot. Otherwise 0.5.9 governs.

#### 0.5.7 Splits

A `SPLIT (n, o)` dated `X` rescales every lot the position holds at the start of `X`:
`u ← u × n / o` and `c ← c × o / n`.

- `a`, the date kind, `k`, the origin and the carry history are unchanged, and so is `c × u`.
- Integrality is judged on the position's quantity (§7). A non-integral result flags the position
  (0.5.9 (a)). So does Ruling 3.4.
- A lot that arrives later on `X` (bought, or carried in) is not rescaled. Ruling 3.2 puts it in
  post-split units already.

#### 0.5.8 Unknown basis, and mixed known and unknown

- An unknown lot is ordered and relieved by its `a` like any other.
- Its relieved portions are unknown. Every other portion keeps its known basis.
  - A relief record with any unknown portion has an **unknown total basis**.
  - Its known portions are still exposed one by one.
- A position's total basis at the end of `D` is unknown iff its lot book holds an unknown lot
  (Ruling 6.4). The known part may be reported with the count of unknown units, never as the
  position's basis.
- **Mixed known and unknown never makes FIFO unresolved** (contrast 0.4.4 (b)). FIFO decides which
  units go, so the unknown basis stays with the units that have it (Example F-F).
- An unknown lot is not a flag (0.4.5 (c)).

#### 0.5.9 Flags, opaque lots and same-day cycles: what stays unresolved

- **(a) A flagged position** (the 0.4.5 precondition): an end-of-day quantity below zero (§9);
  two or more same-day `SPLIT`s (Ruling 3.4); a non-integral split (§7); or a value not
  representable (finding C1C-6). While it is flagged (sticky, as in 1.3):
  - no lot book is presented, and nothing is relieved;
  - every depleting event's relief record is `INSUFFICIENT_DATA` with **the position's own reason
    and details** (the 0.4.5 (c) table);
  - every internal out-leg delivers an **opaque lot** with that cause.
- **(b) An opaque lot** has units but no acquisition date and no unit cost, and it carries a cause.
  It arises:
  - from a flagged source, under (a);
  - from a source that itself holds an opaque lot, with that cause;
  - from an internal in-leg with no resolvable source, cause `LOT_DEPLETION`, as in 1.3 (storage
    forbids an unmatched leg, so a valid ledger never reaches this);
  - from a basis too large to represent, cause `VALUE_NOT_REPRESENTABLE`, as in 1.3.

  **A position holding an opaque lot is basis-unresolved**:
  - its quantity is `AVAILABLE` (0.4.5 (d));
  - its total basis and lot book are `INSUFFICIENT_DATA` with the opaque lot's causes;
  - every relief record of its depleting events carries those causes;
  - every internal out-leg delivers an opaque lot with those causes;
  - the status is sticky until the position ends a day at exactly 0, as in 1.3.

  **Why.** An opaque lot has no acquisition date, so its place in the FIFO order is unknown. Any
  relief from the position might or might not take it.
- **(c) A same-day cycle.** The internal in-legs of one listing on day `d` may form a cycle of
  positions, each needing another's carried lots before it can be resolved (for example A → B and
  B → A). Then the candidate sets and the carried lots determine each other, and FIFO does not
  define a unique result. Every position on the cycle is basis-unresolved from `d`, with
  **`UNRESOLVED_CONVENTION`**, detail `LOT_DEPLETION` (as in 1.3). Its out-legs on `d` deliver
  opaque lots with that cause. Positions downstream inherit it under (b).
- **(d) Ending a day at exactly 0** empties the lot book and clears a basis-unresolved status. It
  does not clear the flags of (a); only a ledger correction does.

**What remains `UNRESOLVED_CONVENTION` under `FIFO/1`:**

1. a non-integral split (§7; the fractional convention stays reserved);
2. a same-day transfer cycle (c);
3. whatever inherits 1 or 2 through a carry;
4. replay's **emitted decimal** of a non-terminating basis (0.4.6, `BASIS_NOT_EXACT`). CP3 reads
   the exact lot book instead (`performance` Ruling 2.5), so no CP3 value is withheld by it.

Everything 1.3 left unresolved for lot selection is now determinate: every multi-lot depletion,
every partial move from several lots, every same-day acquisition with a depletion, and every mixed
known and unknown position.

#### 0.5.10 Snapshot opening lots

- An `OPENING_POSITION` creates a lot on `S` of kind `ENTRY` (0.5.1).
- Before `S` the account is `NOT_RECONSTRUCTABLE` and has no lot book (§8).
- A `SPLIT` dated `S` scales zero units.
- The opening lot is **one recorded lot** even when the broker's figure sums several purchases
  (0.4.7). FIFO relieves it as one lot dated `S`. Its true purchase dates are not recorded.

#### 0.5.11 Exactness, and what is emitted

- Lot units, unit costs, relieved bases and remaining bases are exact rationals. Nothing in the
  fold rounds.
- For parity with the `none` mode, the `FIFO/1` replay state also emits a decimal total basis per
  position and currency. That emission follows 0.4.6: `BASIS_NOT_EXACT` if it does not terminate
  at `D`. CP3 never reads it. CP3 reads the exact lot book (`performance` Ruling 2.5).

#### 0.5.12 Reversal and correction

- The fold is a function of `(D, L)`. Live events are selected by Ruling 2.1, and FIFO is
  recomputed from them at every `(D, L)`.
- **A reversed acquisition never existed.** A sale that relieved it at an earlier `L` relieves
  other lots at the new `L`.
- **A correcting event** (with `corrects_event_id`) creates a new lot: its origin is the correcting
  event, `a` is its own date, and it takes its place in the FIFO order from that date. A
  correction that changes a date can change the relief of every sale dated on or after the earlier
  of the two dates. That is retroactive in economic time and effective by ledger version (Ruling
  2.1; Example F-H).
- **No lookahead.** Relief on day `d` depends only on live events dated `≤ d`. A relief record at a
  given `L` is therefore the same at every `D ≥ d`.
- A reversed `SELL` or `TRANSFER_OUT` relieved nothing. A reversed internal pair moved nothing:
  storage reverses both legs together.
- A pinned `L` reproduces a stored result (Ruling 2.2).

#### 0.5.13 Consistency with the `none` mode (a check, not a rule)

Wherever the `none` mode emits a determinate basis (0.4.3 cases 1–3; 0.4.5 (a); 0.4.5 (b), whole
move), the `FIFO/1` mode emits the same value. FIFO is one of the admissible methods Ruling 0.4
quantifies over, so a value every admissible method agrees on is FIFO's value too. Quantities,
cash and flags are identical in the two modes. A disagreement is an engine defect.

#### 0.5.14 What the fold exposes

At each `(D, L)`:

1. **Per position:**
   - its quantity;
   - its **lot book**: per lot, the identity, the origin event and its type, the carry history,
     `a`, the date kind, `k` (or unknown), the units, the unit cost and the basis;
   - its total basis per currency, or its state;
   - its flags and causes.

   Lots are sorted by (`a`; origin `event_id` as a UUID integer; hop out-leg `event_id`s).
2. **Per depleting event dated `≤ D`:** its relief record (portions with every lot attribute, units
   and basis), or its state with causes.
3. **Per internal pair:** the lots delivered. They are the out-leg's relief record with the hop
   appended.

The serialization is byte-identical across runs, and independent of `ledger_seq` within a day.

**The facts `market-data` Ruling 6.4c reads (taint by lot identity).** A lot was carried out of
position `P` on date `T` iff its carry history holds a hop from `P` dated `T`. Under `FIFO/1`:

- a receiving position **holds a unit of a tainted lot at the end of `D`** iff its end-of-day lot
  book on `D` holds a tainted lot;
- **the day the last tainted unit is relieved** is the first `D ≥ T` at whose end the lot book
  holds no tainted lot;
- a `SELL` or `TRANSFER_OUT` dated `D` **relieves tainted units** iff its relief record holds a
  tainted portion.

How each fact sets a state is `market-data` Ruling 6.4c and `performance/1.5` Ruling 1.1a. This
ruling only defines the facts.

#### 0.5.15 Known limitations (caveats CP3 carries, P3)

1. **Broker records.** A broker may relieve other lots. Every realized and unrealized figure
   carries the PD-0035 §1 caveat.
2. **`ENTRY` dates order by arrival.** A long-held position transferred in after a newer purchase
   is relieved after it, because its purchase date is not recorded. The remedy is a recorded
   acquisition date (`performance` PF-1).
3. **An aggregated opening or transfer lot** is one lot (0.4.7).
4. **Same-day pro rata**, within a date and across the day's events, differs from a broker's
   intraday sequence.
5. **Fractional lot units** are exact here. A broker would not show them.

#### Examples for Ruling 0.5 (hand-derived)

Each value below was derived by hand. The examples numbered as `cp3_golden` part 3 portfolios were
re-checked with that fixture's independent calculator.

**F-A: Example 0.4-C under FIFO.** Lot 1 holds 100 at 10 (date `d1`) and lot 2 holds 100 at 12
(`d2 > d1`). `SELL` 50 on `d3`. The groups are {lot 1} then {lot 2}. Relief: 50 of lot 1, basis
**500**. Remaining: lot 1 50 (500) + lot 2 100 (1,200) = **1,700**, `AVAILABLE`. The `none` mode
reports this unresolved.

**F-B: Example 0.4-D under FIFO, both entry orders.** Lot A holds 100 at 10, held at the start of
`d`. On `d`: `SELL` 100, and `BUY` B 50 for 600. The groups are {A} (`a < d`), then {B}
(`a = d`). Relief: A whole, **1,000**. Remaining: B, 50 units, **600**. The result is the same with
the `SELL` entered first or last. It equals "every plausible execution order under FIFO" in 0.4-D.

**F-C: one date's lots, pro rata, fractional lot units** (`cp3_golden` P14 and P15).

- L0: 30 at 9, dated 03-03.
- On 03-05: `SELL` 80; `BUY` L1, 100 for 1,040 (`c` 52/5); `BUY` L2, 50 for 580 (`c` 58/5).
- `q_dep` = 80. The groups are {L0}, then {L1, L2} (`U_g` = 150).
- L0 is relieved whole: 30 units, 270. The remaining need is 50.
  - L1: 50 × 100/150 = **100/3** units, basis 100/3 × 52/5 = **1,040/3**.
  - L2: 50 × 50/150 = **50/3** units, basis 50/3 × 58/5 = **580/3**.
- Relief total: 270 + 1,620/3 = **810**.
- Remaining:
  - L1: 200/3 units, 2,080/3;
  - L2: 100/3 units, 1,160/3;
  - total **1,080** on 100 units.
- On 03-10, `SELL` 40 from the one group {L1, L2} (`U_g` = 100):
  - L1: 40 × (200/3)/100 = 80/3 units, 832/3;
  - L2: 40/3 units, 464/3;
  - relieved **432**.
  - Remaining: L1 40 units (416) and L2 20 units (232), so **648** on 60 units.
- Entering the 03-05 events in any order gives the same values. Only the multiset of lots and
  dates is read.

**F-D: a partial internal move from two lots, and the receiver's FIFO** (`cp3_golden` P16).

- T1 holds `a` (100 at 9, dated 03-03) and `b` (100 at 11, dated 03-05).
- T2 holds `o` (100 at 56/5, dated 03-06).
- On 03-07, an internal move of 150 from T1 to T2, the only depletion. FIFO relieves `a` whole
  (900) and 50 of `b` (550), carried basis **1,450**.
  - T1 keeps `b`, 50 units, 550.
  - T2 holds `a′` (100 at 9, dated 03-03, one hop), `b′` (50 at 11, dated 03-05, one hop) and `o`.
  - Portfolio total 550 + 2,570 = 3,120, unchanged.
- On 03-10, T2 `SELL`s 120: it relieves `a′` 100 (900), then `b′` 20 (220), so **1,120**.
  - Realized at 12 each: 1,440 − 1,120 = **320**.
  - If T2's own `o` were relieved first, as "the receiver's oldest holding", the relief would be
    100 × 11.2 + 20 × 9 = 1,300 and the gain 140. That is wrong under 0.5.4, because carried lots
    keep their dates.

**F-E: a sale and a move on one day** (P16, 03-12).

- T2 holds `b′` (30 at 11, dated 03-05) and `o` (100 at 56/5, dated 03-06).
- On 03-12: `SELL` 40 and an internal move of 50 to T1. `q_dep` = 90.
- FIFO relieves `b′` 30 (330) and 60 of `o` (672).
- The sale takes 4/9 of each portion: `b′` 40/3 units (440/3) and `o` 80/3 units (896/3), so
  **1,336/3**.
- The move takes 5/9: `b′` 50/3 units (550/3) and `o` 100/3 units (1,120/3), so **1,670/3**.
- T2 keeps `o`, 40 units (448).
- Check: 1,336/3 + 1,670/3 = 3,006/3 = 1,002 = 330 + 672, and 1,002 + 448 = 1,450, which is T2's
  basis at the start of the day. ✓
- T1 now holds three lots: `b` 50 (550; no hop), `b″` 50/3 (550/3; two hops, T1 → T2 on 03-07 and
  T2 → T1 on 03-12) and `o′` 100/3 (1,120/3; one hop). Its basis is **3,320/3**.
- `b` and `b″` share `a` = 03-05, so they form one group. On 03-14, T1's `SELL` 60 relieves them pro
  rata: `b` 60 × 50/(200/3) = **45** (495) and `b″` **15** (165), so **660**.

**F-F: unknown and known basis (Example L-3 under FIFO).**

- Day 1: external `TRANSFER_IN` of 10 U with no `cost_basis`: lot X, unknown, `ENTRY`.
- Day 2: `BUY` 10 for 1,000: lot Y.
- Day 3: `SELL` 10. It relieves X whole, so the relief record is unknown (`MISSING_COST_BASIS`).
  The remaining Y, 10 units, **1,000**, is known.
- The `none` mode reports both unresolved (0.4.4 (b)).
- A `SELL` of 15 on day 3 instead: X 10 (unknown) and Y 5 (500). The relief total is unknown, and
  its known portion 500 is exposed. The remaining Y, 5 units, **500**, is known.

**F-G: an opaque lot (Example 0.4-H, H2, under FIFO).**

- A1 holds 10 U. Same day: `SELL` 15 and an internal move of 5 to A3. A1 ends at −10 and is
  flagged `LEDGER_INCONSISTENT`.
- A3 already held 20 U at 10, bought earlier. It receives an opaque lot of 5 with
  `LEDGER_INCONSISTENT`. A3's quantity, **25**, is `AVAILABLE`. Its basis is `INSUFFICIENT_DATA`,
  `LEDGER_INCONSISTENT`.
- A later A3 `SELL` 10 has a relief record that is `INSUFFICIENT_DATA`, `LEDGER_INCONSISTENT`,
  because the opaque units' date is unknown and they may or may not come first. A3's quantity is
  15, `AVAILABLE`.
- This stays so until A3 ends a day at 0.

**F-H: a re-dated purchase (reversal and correction)** (`cp3_golden` P19).

- seq 2: `BUY` A, 100 for 900, dated 03-03.
- seq 3: `BUY` B, 100 for 1,100, dated 03-05.
- seq 4: `SELL` 100 on 03-10.
- seq 5 and 6, appended together: `REVERSAL` of seq 2, and `BUY` A′, 100 for 1,120, dated 03-06,
  correcting seq 2.

| `(D, L)` | Lot book | Relief of seq 4 |
|---|---|---|
| (03-05, 4) | A 100 (900); B 100 (1,100) | not yet |
| (03-05, 6) | B 100 (1,100). A never existed, and A′ is dated after `D` | not yet |
| (03-31, 4) | B 100 (1,100) | A 100, **900** |
| (03-31, 6) | A′ 100 (1,120) | B 100, **1,100** |

The same sale relieves a different lot at the new `L`, because the corrected purchase is dated
after B. The old `L` still reproduces 900.

**F-I: the facts behind a carried taint** (`cp3_golden` P17).

- V1 holds `s` (100 at 80, dated 02-03).
- A split of 4:1 with ex-date 03-03 is corroborated but missing from the ledger, so V1 is
  suppressed from 03-03 (`market-data` 6.4).
- V2 buys `v` (100 at 39/2, dated 03-04).
- On 03-05, an internal move of 40 from V1 to V2 delivers `s′` (40 at 80, dated 02-03, hop V1 → V2
  on 03-05). It is tainted, because V1 was suppressed on 03-05.
- On 03-10 V2 `SELL`s 40. FIFO relieves `s′` whole, because 02-03 is older than 03-04.
  - The relief record holds a tainted portion.
  - V2's end-of-day lot book on 03-10 is {`v`}, with no tainted lot.
  - So 03-10 is the day the last tainted unit is relieved.
- Under the conservative rule (no lot identity), V2, which never ends a day at 0, would stay
  suppressed indefinitely.

**F-J: the `none`-mode values are reproduced (0.5.13).**

- Example 0.4-A under FIFO: the `SELL` of 50 relieves 50 of the one lot at 75/2, so 1,875, and the
  remaining basis is **5,625** (T7).
- Example 0.4-G G1: one candidate lot, with the 40 sold and the 60 moved each taking `c` = 10, so A3
  receives **600**.
- Example 6-C: **3,750 / 1,875**.

### RULING 0.6 (1.5) — The recorded acquisition date (`acquired_on`) in the FIFO mode

PD-0036 §1: `acquired_on` is optional and user-supplied. It is allowed only on `OPENING_POSITION`
and external security `TRANSFER_IN` (no counterparty), and it is not later than the event's
`event_date`. Storage enforces those conditions, and replay may assume them.

#### 0.6.1 A third date kind: `RECORDED`

| Acquiring event | `a` (acquisition date) | Date kind |
|---|---|---|
| `BUY` | `event_date` | `TRADE` (unchanged) |
| `OPENING_POSITION` or external `TRANSFER_IN` **with** `acquired_on` | **`acquired_on`** | **`RECORDED`** |
| the same **without** `acquired_on` | `event_date` | `ENTRY` (unchanged) |
| internal `TRANSFER_IN` | the source lot's | the source lot's (unchanged) |

- **Every other attribute** of 0.5.1 is unchanged. Units, unit cost and basis currency come from
  `quantity` and `cost_basis`. Without `cost_basis` the lot is unknown, whatever its date.
- **`RECORDED` means:** the user states that these units were acquired on that date. It is a fact
  supplied by the user, labelled as such (P9, PRD §9.3). It is never inferred, and nothing else ever
  sets it. In particular, an `ENTRY` lot is never given a `RECORDED` date by any rule.
- **`acquired_on` = `event_date`** is allowed and still gives `RECORDED`. The user states that the
  units were bought that day. That differs from `ENTRY`, where the purchase date is simply not
  recorded.
- **The date applies to the event's whole quantity.** A position bought on several dates is
  recorded as several events, one per date (0.6.3).

#### 0.6.2 FIFO order

- A `RECORDED` lot is ordered by its `a` = `acquired_on`, exactly like any other lot (0.5.4). It
  shares a pro-rata group with every lot of the same `a`, of any kind.
- So a holding transferred in with an old `acquired_on` is relieved **before** a newer purchase
  held in the same position. This removes the limitation of 0.5.15 item 2 for events that carry
  the date.

#### 0.6.3 Snapshots

- **`acquired_on` before `S` does not extend the history.** The account stays
  `NOT_RECONSTRUCTABLE` for `D < S` (§8). The date is an attribute of a lot. It is not an event, a
  flow, or a valuation date, and it moves no quantity or cash before `S`.
- **The lot's own `a` may precede `S`.** It orders FIFO and dates the reporting-currency basis
  (`performance/1.6` Ruling 3.7a). The portfolio's inception base stays `S` (`performance` Ruling
  4.4).
- **Several `OPENING_POSITION` events** for one `(account, listing)`, all dated `S`, are several
  lots. Each has its own `quantity`, `cost_basis` and `acquired_on`. This is how a user records a
  snapshot position bought on several dates. It removes 0.4.7's aggregation for users who record
  lots.
  - The position's quantity is their sum.
  - In the `none` mode they are simply several candidate lots (0.4.3). That is unchanged 1.3
    behaviour.

#### 0.6.4 Carries, splits, reversal and correction

- **An internal carry** keeps `a` and the kind `RECORDED`, like every attribute (0.5.6). The hop
  records nothing new.
- **A split** does not change `a` (0.5.7).
- **Adding or changing a date later** is a correction:
  - a `REVERSAL` of the original event, plus a replacement carrying `acquired_on`, with
    `corrects_event_id`, appended atomically (Ruling 2.3);
  - the replacement keeps the original's `event_date` (for a snapshot, `S`);
  - from the new `L` the lot is `RECORDED`, and FIFO is recomputed at every `D` (0.5.12);
  - a pinned earlier `L` still reproduces the `ENTRY` result.

  The ledger stays append-only, and the history of what was known stays visible.

#### 0.6.5 Modes and outputs

- **The `none` mode never reads `acquired_on`.** Its outputs are those of 1.3.
- **The `FIFO/1` lot book and relief records** carry the date kind `RECORDED` and `a` =
  `acquired_on` (0.5.14). Nothing else in the interface changes.
- **No currency is translated in replay.** What a `RECORDED` date does to the reporting-currency
  basis is `performance/1.6` Ruling 3.7a.

#### Examples for Ruling 0.6 (hand-derived; `cp3_golden/1.1-part3`, P20)

**F-K: opening lots ordered by their recorded dates.** Account Q1 has a snapshot `S` = 2025-03-31
with four 0700 opening events, all dated `S`:

| Lot | Units | `cost_basis` (HKD) | `acquired_on` | `a` | Kind |
|---|---|---|---|---|---|
| O1 | 400 | 14,000 (35) | 2025-01-04 | 01-04 | `RECORDED` |
| O2 | 600 | 18,000 (30) | 2025-01-08 | 01-08 | `RECORDED` |
| O3 | 200 | 7,600 (38) | — | 03-31 | `ENTRY` |
| O4 | 100 | 3,200 (32) | 2024-12-16 | 2024-12-16 | `RECORDED` |

The FIFO order is O4, O1, O2, O3, whatever the entry order.

- **04-07, `SELL` 450:** O4 100 (3,200) and O1 350 (12,250). Relieved 15,450 HKD.
- **04-10, `SELL` 250:** O1 50 (1,750) and O2 200 (6,000). Relieved 7,750 HKD.

**F-L: a carried recorded lot.** On 04-15 an internal move of 100 goes from Q1 to Q2. Q1's oldest
remaining lot is O2 (01-08), so FIFO relieves O2 100 (3,000). Q2 receives O2′: 100 at 30, `a`
2025-01-08, `RECORDED`, one hop. Q1 keeps O2 300 (9,000) and O3 200 (7,600).

**F-M: the snapshot horizon is unchanged.** At `D` = 2025-03-30, Q1 is `NOT_RECONSTRUCTABLE`,
although O4's `acquired_on` is 2024-12-16.

---

## 1. As-of inclusion: trade date or settlement date

### RULING 1.1 — `event_date` governs inclusion for every event type, securities and cash alike

An event is in `S(D, L)` iff `event_date ≤ D` (and §2's knowledge conditions hold).

For `BUY` and `SELL`, **both legs** (the position change and the cash change) enter on the
**trade date**. `settlement_date` is recorded, is **never read by CP1 replay**, and its absence
changes nothing.

**Why.**

1. **Both legs must share one basis.** Take securities on trade date and cash on settlement
   date. Between those dates the purchased shares and the cash that pays for them are both in
   the state, so value is counted twice (Example 1-A). The reverse mix undercounts instead.
2. **Trade-date is the standard for performance measurement.** GIPS requires trade-date
   accounting for portfolio valuation and returns. CP3 will need trade-date holdings, and
   using one convention from CP1 onward avoids a second replay basis.
3. **Settlement cycles differ across V1's markets and over time.** US equities moved from T+2
   to T+1 in May 2024. Hong Kong is T+2. A-shares settle securities T+1. Northbound Stock
   Connect settles securities T+0 and money T+1. A settlement-date state is heterogeneous
   across the portfolio. A trade-date state is uniform.

**Rejected alternatives.**

- **Settlement-date basis for both legs.** This is valid accounting (IFRS 9 allows either
  basis for regular-way trades, applied consistently), but it hides market exposure the
  investor already carries. It also makes the state depend on per-market settlement
  calendars the product does not yet hold.
- **Mixed basis** (securities on trade date, cash on settlement date). This is what broker
  statements show as "settled cash". It double-counts, as Example 1-A shows.

A **settled-cash view** can be added later as a second, separately labelled state. It is not
part of V1 CP1. Whether V1 ever shows it is an **OWNER DECISION** and is not needed now. If it
is ever built, an event without `settlement_date` makes that view **LIMITED** for the affected
key. The date must **never be inferred** from a T+n rule, because that needs market calendars
and settlement-cycle history (the 2024 US change is one example).

### RULING 1.2 — What `event_date` must mean for each type (a data-entry convention replay relies on)

| Type | `event_date` is |
|---|---|
| `BUY`, `SELL` | the trade date, as a local date on the listing venue's calendar |
| `DIVIDEND`, `INTEREST` | the date the cash was credited (the pay date), per §4 |
| `FEE`, `TAX`, `DEPOSIT`, `WITHDRAWAL`, cash transfers | the booking date on which the account balance changed |
| `INTEREST_CHARGED` | the booking date on which the account is debited. Accrual is not modelled in CP1 (§5). |
| `CURRENCY_CONVERSION` | the trade (execution) date of the conversion. Both legs enter on it (§5A). |
| security transfers | the date the units left or arrived. Both legs of an internal transfer carry the same date (§6.2). |
| `SPLIT` | the **ex-date**: the first day the listing trades on the split-adjusted basis (§3.2). There is **one** `SPLIT` per `(account, listing)` per ex-date, carrying the **combined** ratio of that date's share distribution. For example, an A-share "10送3转增2" is `(15, 10)` (1.3, Ruling 3.4). |
| `OPENING_POSITION`, `OPENING_CASH` | the snapshot date `S`. The snapshot is the end-of-day state on `S` (§8). |
| `REVERSAL` | the date the correction was booked. **Not used by replay** (§2). |

**Cross-market dates.** Each event's date is its own local business date. `D` is compared with
it as a calendar date. CP1 does not order events across time zones by instant.

Consequence for CP3: a valuation cutoff instant (PD-0015, and the HG1 as-of rule "the latest
instant at or before which every required input has a print") must include ledger events **by
this date rule**, not by converting event dates to instants. Otherwise an HKEX trade dated `D+1`
local, which executes before the US close of `D`, would land in two different states depending
on who computed it. **CP3 dependency, named here.**

### RULING 1.3 — A negative cash balance is a valid state

Under trade-date accounting, trade-date cash is legitimately negative whenever a purchase is
funded by a later deposit or settles on credit. Replay carries the signed balance exactly. It
must not clamp it to zero or reject it.

**Decided (PD-0024 §3): margin accounts are not in V1.** A negative cash balance is still
recorded and shown as a valid ledger state. V1 makes no claim to model financing, margin
requirements or leverage analytics. No ruling in this document computes anything from a
negative balance beyond the balance itself.

### Example 1-A — Trade date versus settlement date

Account A2. Listing H@XHKG (HKD).

| seq | Type | Detail | `event_date` | `settlement_date` |
|---|---|---|---|---|
| 1 | `DEPOSIT` | A2, 20,000 HKD | 2025-01-06 | — |
| 2 | `BUY` | A2, H, q = 500, a = 17,500 HKD | 2025-01-08 | 2025-01-10 |

With `L = 2`:

| `D` | H | A2 HKD | Derivation |
|---|---|---|---|
| 2025-01-07 | 0 | 20,000 | seq 2 is dated after `D`, so only seq 1 is in |
| 2025-01-08 | 500 | 2,500 | 20,000 − 17,500 = 2,500 |
| 2025-01-09 | 500 | 2,500 | unchanged, because settlement is pending and settlement is not read |
| 2025-01-10 | 500 | 2,500 | unchanged |

Rejected mixed basis at `D` = 2025-01-09: H = 500 **and** HKD = 20,000. The same 17,500 HKD
of value is present twice.

Remove `settlement_date` from seq 2: every row above is identical.

### Example 1-B — Negative trade-date cash

Account A1. Listing U@XNYS (USD).

| seq | Type | Detail | `event_date` |
|---|---|---|---|
| 1 | `BUY` | A1, U, q = 10, a = 1,000 USD | 2025-01-08 |
| 2 | `DEPOSIT` | A1, 1,000 USD | 2025-01-09 |

- `S(2025-01-08, 2)`: U = 10, A1 USD = 0 − 1,000 = **−1,000**.
- `S(2025-01-09, 2)`: U = 10, A1 USD = −1,000 + 1,000 = **0**.

---

## 2. Reversal semantics: economic date against knowledge version

### RULING 2.1 — A reversal is retroactive in economic time and effective in knowledge time

An event `e` contributes to `S(D, L)` iff **all** of the following hold:

- (i) `e.ledger_seq ≤ L`;
- (ii) `e.event_date ≤ D`;
- (iii) `e` is not a `REVERSAL`;
- (iv) there is **no** `REVERSAL r` with `r.reverses_event_id = e.event_id` and
  `r.ledger_seq ≤ L`.

The consequences:

- The reversal's own `event_date` plays **no role** in replay. Once a reversal is known (it
  is in `L`), the reversed event is treated as **never having happened, at every `D`**. That
  includes dates before the reversal was booked.
- A **correcting event** (one carrying `corrects_event_id`) is an ordinary event. It applies
  from **its own** `event_date`, which may differ from the original's.
- History "as it was believed" is recovered by pinning an earlier `L`. The Computation
  Manifest's `ledger_version` is exactly that pin.

**Why.** A `REVERSAL` states that a record was wrong. The fact it recorded did not occur.
Applying the reversal only from its booking date would make the economic history depend on
*when an error was noticed*. The state would then show, for the whole interval between the
original date and the correction, holdings that never existed (Example 2-A). Keeping economic
date and knowledge version on separate axes is the standard bitemporal treatment (valid time
against transaction time; Snodgrass, *Developing Time-Oriented Database Applications in SQL*,
1999). It is also what B0b §3.2 anticipated with `effective_date` and `recorded_at`.

**Rejected alternative: effective from the reversal's `event_date`.** This is the
closed-period accounting practice of booking a correcting entry in the current period. It
suits general-ledger period close, where earlier periods are locked. It is wrong for
point-in-time position reconstruction (PRD §9.7, P12). A portfolio-analytics product has no
closed periods, and its "past periods" are recomputed states.

### RULING 2.2 — Which views V1 needs

- **Required in CP1:** replay parameterized by both `D` and `L`. There are two uses:
  - `S(D, L_latest)` is the normal view: "as of `D`, with everything we know now".
  - `S(D, L_pinned)` reproduces a stored result exactly (§34). Without `L`, a later
    correction would silently change a result that had already been reproduced.
- **Not required in CP1:** a wall-clock "as known at time `T`" view keyed on a storage
  timestamp (`recorded_at`). With `L` in every manifest, reproduction never needs `T`. A
  `T → L` lookup is derivable if storage records both. Whether users ever see a
  knowledge-time view ("what did the product show on 2025-03-01?") is an **OWNER DECISION**
  and is not needed for CP1.

### RULING 2.3 — `L` must be commit-stable (a determinism requirement on storage)

Once any computation has pinned `L`, no event with `ledger_seq ≤ L` may become visible later.
Gaps in the sequence are harmless. Late visibility below a pinned `L` breaks reproducibility.

A plain database sequence does not guarantee this under concurrent appends, because a
transaction holding a lower number can commit after one holding a higher number. How storage
achieves commit-stability is an engineering choice (finding F7).

A `REVERSAL` and its correcting replacement must become visible **atomically**, with the
reversal's `ledger_seq` lower than the replacement's. Otherwise some `L` sees both the
original and the replacement (finding F10, Example 2-A, last row).

### RULING 2.4 — `REVERSAL` is for errors only, never for real economic reversals

A genuine later economic event must not be recorded as a `REVERSAL`. Examples are a dividend
reclaimed by the payer and a trade busted after cash has actually moved. Recording one as a
`REVERSAL` would erase an interval in which the cash really was in the account. The current
taxonomy has no type for such claw-backs. That gap is open issue OI-3. CP1 fixtures must not
contain one.

### Example 2-A — Correction of a wrong quantity and date

Account A1. Listing U (USD). seq 3 and seq 4 are appended in one transaction.

| seq | Type | Detail | `event_date` |
|---|---|---|---|
| 1 | `DEPOSIT` | A1, 10,000 USD | 2025-01-02 |
| 2 | `BUY` | A1, U, q = 50, a = 7,500 USD (wrong) | 2025-01-06 |
| 3 | `REVERSAL` | `reverses_event_id` = seq 2 | 2025-01-20 |
| 4 | `BUY` | A1, U, q = 40, a = 6,000 USD, `corrects_event_id` = seq 2 | 2025-01-07 |

| `(D, L)` | Events in | U | A1 USD | Derivation |
|---|---|---|---|---|
| (2025-01-10, 2) | 1, 2 | 50 | 2,500 | 10,000 − 7,500 |
| (2025-01-10, 4) | 1, 4 | 40 | 4,000 | seq 2 is excluded by (iv). 10,000 − 6,000 |
| (2025-01-06, 4) | 1 | 0 | 10,000 | seq 2 is excluded by (iv). seq 4 is dated 01-07, after `D` |
| (2025-01-25, 4) | 1, 4 | 40 | 4,000 | as above |

Rejected "effective from reversal date", at (2025-01-10, 4): seq 2 is active from 01-06 to
01-19 and seq 4 from 01-07. That gives U = 50 + 40 = **90** and USD = 10,000 − 7,500 − 6,000 =
**−3,500**, a holding that never existed.

The same 90 / −3,500 appears at an intermediate `L` if the replacement were ever visible
before its reversal. That is why Ruling 2.3 requires the atomic append.

---

## 3. Deterministic ordering of same-date events

### RULING 3.1 — Replay order is `(event_date ASC, rank ASC, ledger_seq ASC)`

`rank(SPLIT) = 0`. Every other contributing type has rank 1, including `INTEREST_CHARGED` and
`CURRENCY_CONVERSION` (both added in 1.1). `REVERSAL` rows do not enter the fold (§2).

`CURRENCY_CONVERSION` needs no special rank. Its two legs are additive, each on its own cash
key. So a same-day conversion and a purchase in the bought currency give the same end-of-day
state in either order (Example 5A-A). An intra-day negative balance in the bought currency,
when the purchase is folded first, is not a state (Ruling 3.3).

**Why the order barely matters, and where it does.** Every event except `SPLIT` is **additive**
on quantity and cash, so the end-of-day state is independent of their order within a day. Only
`SPLIT` is multiplicative, so it does not commute with same-day trades.

`ledger_seq` is the final tie-break. It makes the fold a total order: determinism does not
depend on it for the state, but an audit trace of the fold needs a fixed order.

Two rank-0 events on one position on one date would be the one place where `ledger_seq` could
matter. Ruling 3.4 (1.3) excludes that case: such a position is flagged, not folded.

### RULING 3.2 — A `SPLIT` applies at the **start** of its `event_date` (the ex-date)

On and after the ex-date, the market quotes and trades the listing in post-split units, so
every trade dated on or after the ex-date is recorded in post-split units. Applying the split
before them keeps every quantity in one unit system.

This matches trade-date accounting under exchange practice. A buyer before the ex-date is
entitled to the split. In the US, large forward splits are entitled through due bills, with the
ex-date set after the payable date. A-share bonus and capitalization issues use the same
ex-right date (除权日) logic.

It also fits snapshots. A `SPLIT` dated on an `OPENING_*` snapshot date `S` applies before the
opening quantity is added. Because the snapshot is already post-split, the result is correct.

**Rejected alternative: pure `ledger_seq` order within a day.** The state would then depend on
whether the user typed the split before or after the sale (Example 3-A).

### RULING 3.4 (1.3; C1C-3) — Two or more same-day `SPLIT`s on one position: `LEDGER_INCONSISTENT`

**Rule.** Suppose that, at ledger version `L`, two or more **live** `SPLIT` events name the same
`(account, listing)` with the same `event_date` `d`, and that position holds non-zero units at
the start of `d`, before splits. Then:

- **none** of those splits is applied;
- from `d` on, at that `L`, the position's **quantity and basis** are `INSUFFICIENT_DATA` with
  reason **`LEDGER_INCONSISTENT`**, detail *multiple same-day splits*;
- the flag is **sticky**, as in §9. Cash is unaffected.

Out-legs from the position inherit the cause (0.4.5 (c)).

If the position holds **zero** units at the start of `d`, the splits scale nothing. Same-day
acquisitions are already in post-split units (Ruling 3.2), so no flag is raised.

Only a ledger correction clears the flag, which gives a new `L`: reverse the extra `SPLIT`(s),
and if needed append one `SPLIT` with the intended combined ratio. The single remaining split is
then tested for integrality exactly as §7 says, which is unchanged.

**Why neither per-split nor composite integrality.** Two same-day splits on one position are
ambiguous. The ledger does not say which of three readings is meant, and they give different
quantities:

1. **A duplicate entry** of one split. It should apply **once**.
2. **Two components of one distribution.** A-share bonus shares plus a capitalization issue on
   one ex-right date (送股 + 转增) **add**: "10送3转增2" is 10 + 3 + 2 = 15 per 10, so
   `(15, 10)`, not `(13, 10) × (12, 10)`.
3. **Two successive actions.** These **multiply**, but an exchange does not set two successive
   splits of one listing on one ex-date.

Each fixed rule would therefore silently produce a wrong quantity for one of the readings:

- **Composite multiplication** is wrong for readings 1 and 2.
- **Per-split in `ledger_seq` order** is also order-dependent, which breaks Ruling 3.1.
- **Per-split in any other fixed order** still multiplies, so it is wrong for readings 1 and 2.

**Why `LEDGER_INCONSISTENT`, not `UNRESOLVED_CONVENTION`.** No methodology ruling could resolve
this, because the missing information is which event the user meant. The remedy is a ledger
correction, and that is what the reason must point to (PD-0025 §1).

This is not a fractional-split question. The reserved fractional convention (§7) is not
touched.

**Recommendation (finding F12).** Storage should refuse to append a second live `SPLIT` for the
same `(account, listing, event_date)`. Replay keeps the rule above regardless, because the
reviewer's probe shows storage admits it today.

### Example 3-B (1.3) — Same-day split pairs

- **(i) The review's probe P2.** A1 holds 3 U, one lot, basis 300 USD (`c` = 100). On `d`:
  `SPLIT (1, 2)` seq 11 and `SPLIT (2, 1)` seq 12.
  - **1.3 result**, at every `D ≥ d`: quantity and basis `INSUFFICIENT_DATA`,
    `LEDGER_INCONSISTENT`, multiple same-day splits.
  - **The same result** if the seqs are swapped, so it is order-independent.
  - Rejected readings:
    - seq order (1:2) first: 3 × 1/2 = 1.5, which is non-integral and unresolved;
    - seq order (2:1) first: 3 × 2 = 6, then 6 × 1/2 = 3;
    - composite 3 × (1/2) × (2/1) = 3, basis 300.

    That is two different answers from the same facts.
- **(ii) A-share distribution recorded as two events.** A2 holds 1,000 shares, basis 10,000
  CNY. `SPLIT (13, 10)` and `SPLIT (12, 10)` on one ex-right date.
  - Composite reading: 1,000 × 1.3 × 1.2 = **1,560**.
  - The distribution actually paid (10送3转增2): 1,000 × 15/10 = **1,500**.
  - **1.3 result:** `LEDGER_INCONSISTENT`.
  - **Correct recording:** one `SPLIT (15, 10)` gives quantity **1,500**, `AVAILABLE`, with
    total basis **10,000 CNY** unchanged.
- **(iii) Duplicate entry.** 1,000 shares, `SPLIT (2, 1)` entered twice on one date.
  - Composite: **4,000**. Intended: **2,000**.
  - **1.3 result:** `LEDGER_INCONSISTENT`.
  - After reversing one of them (new `L`): **2,000**, basis unchanged.
- **(iv) No units at the start of the day.** A3 holds no U. Two `SPLIT`s dated `d`, then a
  `BUY` of 100 U on `d`. Quantity **100**, `AVAILABLE`, no flag, because the splits scaled
  nothing.

### RULING 3.3 — Only end-of-day states are meaningful

Intra-day intermediate states are not states and are never validated. The negative-quantity
check (§9) is applied to end-of-day states only.

**Basis is also judged per day, not per `ledger_seq` (1.2).** Same-day order between an
acquisition and a depletion can change which lots a sale consumes. The ledger does not record
execution order. Ruling 0.4.2 therefore puts every same-day acquisition in the lot set that
day's depletions may draw on. Basis output must never depend on `ledger_seq` within a day. The
choice of depletion method itself stays reserved (CP3).

### Example 3-A — Same-date `SPLIT` and `SELL`

Account A1. Listing U (USD).

| seq | Type | Detail | `event_date` |
|---|---|---|---|
| 1 | `DEPOSIT` | A1, 10,000 USD | 2025-01-02 |
| 2 | `BUY` | A1, U, q = 50, a = 7,500 USD | 2025-01-06 |
| 3 | `SELL` | A1, U, q = 100 (post-split units, 100 × 45.00), a = 4,500 USD | 2025-02-03 |
| 4 | `SPLIT` | A1, U, ratio (4, 1) | 2025-02-03 |

Fold order on 2025-02-03 under Ruling 3.1: seq 4 (rank 0), then seq 3.

`S(2025-02-03, 4)`:

- U = 50 × 4 / 1 − 100 = 200 − 100 = **100**.
- A1 USD = 10,000 − 7,500 + 4,500 = **7,000**.
- Basis: 7,500 before the split, unchanged by the split. After selling 100 of a
  **single lot** of 200, the remaining basis is 7,500 × 100 / 200 = **3,750**. FIFO, average
  and specific-lot agree because there is one lot. This is Ruling 0.4.3 case 3: the candidate
  set on 2025-02-03 is the one rescaled lot, and there is no same-day acquisition. The value
  terminates, so it is `AVAILABLE`.

Rejected pure-`ledger_seq` order: 50 − 100 = −50, then × 4 = **−200**. That is wrong, and it
also trips the negative-quantity check.

Commutativity check: move seq 1 to 2025-01-06 and append it after seq 2. `S(2025-01-06)` is
U 50, USD 2,500 either way.

---

## 4. Dividend entitlement: is an ex-date needed in CP1?

### RULING 4.1 — CP1 replay needs no ex-date. A `DIVIDEND` dated on its pay date is sufficient.

A cash dividend changes no quantity. Its only CP1 effect is a cash credit, and that happens on
the pay date (Ruling 1.2). Positions and cash are therefore fully determined without an
ex-date.

A declared or ex-dated dividend that has not yet been paid is a **receivable, not cash**. CP1
records nothing for it.

### RULING 4.2 — Replay must not validate dividend entitlement against pay-date holdings

Entitlement is fixed by holdings at the **ex-date**. A holder who sells between the ex-date and
the pay date is still paid. So a `DIVIDEND` on a listing whose position is zero on the pay date
is legitimate (Example 4-A). Replay must accept it.

A genuine entitlement check needs the ex-date. That is a CP2/CP3 capability.

### RULING 4.3 — Gross dividend with a separate `TAX`, or net dividend alone, but never net with `TAX`

If withholding is recorded as a `TAX` event, the `DIVIDEND.amount` must be the **gross**
amount. If the source shows only the net credit, record the net `DIVIDEND` and **no** `TAX`.
The withholding is then unknown, and it is not fabricated (PRD §8.4, "known taxes").

Cash replay gives the same balance under both valid forms. Only "net plus `TAX`" double-counts
(Example 4-A).

### Where an ex-date is needed, and a recommendation

CP3 needs an ex-date, for two reasons:

- **Income timing.** Price falls on the ex-date. Income recognized on the pay date makes the
  interval between the two dates show a spurious price loss, followed by a gain. GIPS
  recommends accruing dividends as of the ex-dividend date.
- **Entitlement validation.** Ruling 4.2 above.

PRD §11.1 already puts an effective date on the CP2 `CorporateAction` contract. That is one
possible source.

**RECOMMENDATION (finding F5):** add an **optional** `ex_date` to `DIVIDEND` now. It is not
read by CP1 replay. The reason for adding it now is the argument B0b §3.2 made for
`recorded_at`: a user's statement often carries the ex-date at entry time, and an append-only
ledger can never truthfully backfill it later. This is not blocking for CP1. The B0b fixture
contains no dividends.

### Example 4-A — Dividend after a sale, with withholding

Account A2. Listing H (HKD). The dividend is hypothetical: ex-date 2025-05-16, pay date
2025-05-30, 2.00 HKD per share gross, 10% withholding.

| seq | Type | Detail | `event_date` |
|---|---|---|---|
| 1 | `DEPOSIT` | A2, 20,000 HKD | 2025-04-01 |
| 2 | `BUY` | A2, H, q = 500, a = 17,500 HKD | 2025-04-01 |
| 3 | `SELL` | A2, H, q = 500, a = 18,000 HKD | 2025-05-20 (after the ex-date, so still entitled) |
| 4 | `DIVIDEND` | A2, H, a = 1,000 HKD (500 × 2.00) | 2025-05-30 |
| 5 | `TAX` | A2, H, a = 100 HKD (10% × 1,000) | 2025-05-30 |

| `D` | H | A2 HKD | Derivation |
|---|---|---|---|
| 2025-05-25 | 0 | 20,500 | 20,000 − 17,500 + 18,000 |
| 2025-05-30 | 0 | 21,400 | 20,500 + 1,000 − 100 |

Replay accepts seq 4 even though H = 0 on 2025-05-30.

The alternative recordings give:

- **Net form** (`DIVIDEND` 900, no `TAX`): 20,500 + 900 = **21,400**, the same balance.
- **Invalid net-plus-`TAX`** (`DIVIDEND` 900 plus `TAX` 100): 20,500 + 900 − 100 = **21,300**.
  That is 100 HKD short.

---

## 5. Interest charged: `INTEREST_CHARGED` (decided, PD-0024 §2)

### RULING 5.1 — Debit interest is neither `INTEREST` nor `FEE`

**Why not `INTEREST`.** `INTEREST` is a credit (Ruling 0.2), and amounts are positive
magnitudes, so debit interest recorded as `INTEREST` would move cash the wrong way. Making
`INTEREST` bidirectional would break the positive-magnitude rule and net financing cost against
income in the §8.4 "income" bucket, which misstates income.

**Why not `FEE`.** The cash effect would be correct. But `FEE` means a charge for a service,
may carry a `listing_id`, and is the candidate for basis capitalization (Note 1). Folding
financing cost into it loses a distinction CP3 attribution needs.

The owner added the type in PD-0024 §2. Finding F3 is closed.

### RULING 5.2 — Field specification for `INTEREST_CHARGED`

These use `ledger.py`'s `FIELD_RULES` vocabulary.

| Field | Rule | Meaning |
|---|---|---|
| `event_id`, `account_id`, `event_type`, `event_date`, `currency` | required (as for every event) | `currency` is the currency the account was debited in. `event_date` is the booking date of the debit (Ruling 1.2). |
| `amount` | **REQUIRED**, `Money` in `currency`, `> 0` | the interest debited, as the source reports it |
| `listing_id` | **FORBIDDEN** | Debit interest is charged on the account's cash balance, not on a security. A charge attributable to a security is a `FEE`. A stock-borrow fee cannot arise, because short positions are not in V1 (PD-0024 §4). |
| `settlement_date` | OPTIONAL | recorded, never read by replay (Ruling 1.1) |
| `corrects_event_id` | OPTIONAL | as for every correctable type (§2) |
| `source_reference` | OPTIONAL | as for every type |
| `quantity`, `cost_basis`, `split_ratio`, `counterparty_account_id`, `reverses_event_id`, `bought_amount` | **FORBIDDEN** | |

This is the same shape as `_CASH_ONLY` (`DEPOSIT`/`WITHDRAWAL`) in the current module.

### RULING 5.3 — Effect and flow classification

- **Effect:** cash `−a` on `(account, currency)`.
- **Flow class:** **financing cost**. It is a cost inside the portfolio, the same kind as a fee
  or a tax: it reduces value and is **not** an external flow at either portfolio or account
  level. PRD §9.6's external flows are only money that crosses the portfolio boundary
  (`DEPOSIT`, `WITHDRAWAL` and external transfers). Interest paid to the broker is a cost of
  holding the portfolio, not the investor taking money out.
- **Which §8.4 bucket reports it** (fees, or a separate financing line) is a CP3 attribution
  ruling. It is deferred and not decided here.
- **Accrual.** CP1 records the booked debit only. Daily accrual between bookings is an
  income-timing question for CP3, like dividend ex-date accrual (§4).
- **Scope.** Margin accounts are not in V1 (PD-0024 §3). `INTEREST_CHARGED` records a cash fact
  the source reports, such as overdraft or settlement-shortfall interest. It does not make V1
  a model of financing, and nothing computes a rate or a leverage figure from it.

### Example 5-A — Interest on a short-lived shortfall

Account A2. Listing H (HKD).

| seq | Type | Detail | `event_date` |
|---|---|---|---|
| 1 | `DEPOSIT` | A2, 5,000 HKD | 2025-05-02 |
| 2 | `BUY` | A2, H, q = 200, a = 7,000 HKD | 2025-05-05 |
| 3 | `DEPOSIT` | A2, 2,000 HKD | 2025-05-08 |
| 4 | `INTEREST_CHARGED` | A2, a = 3.50 HKD | 2025-05-31 |

| `D` | H | A2 HKD | Derivation |
|---|---|---|---|
| 2025-05-05 | 200 | −2,000 | 5,000 − 7,000 |
| 2025-05-08 | 200 | 0 | −2,000 + 2,000 |
| 2025-05-31 | 200 | −3.50 | 0 − 3.50 |

- **External flows** in the period: +5,000 HKD (seq 1) and +2,000 HKD (seq 3). seq 4 is **not**
  a flow.
- Recorded as `FEE` instead, the cash is the same (−3.50). Only the classification differs.
- Recorded as `INTEREST` it would give **+3.50**, which is wrong.
- The −2,000 and −3.50 balances are valid recorded states (Ruling 1.3). They are not margin
  modelling.

---

## 5A. Currency conversion inside one account: `CURRENCY_CONVERSION` (decided, PD-0024 §1)

The name is suggested; the engineer may choose another. I avoid "FX" in the name because this
event is not an FX observation.

### RULING 5A.1 — One event with two amounts, not two linked legs

A conversion is recorded as **one** event carrying both amounts.

**Why.** A single row is atomic by construction:

- no half-conversion can exist at any ledger version `L` (Ruling 2.3);
- one `REVERSAL` removes both legs (Ruling 5A.6);
- no pairing rule is needed, unlike internal transfers (§6.2).

**Rejected alternative: two linked single-currency events.** Each leg would satisfy the
existing one-currency rule. But pairing, atomic append and paired reversal would all have to be
added as cross-event rules. Each one is a way for the ledger to contain half a conversion.

### RULING 5A.2 — Field specification for `CURRENCY_CONVERSION`

| Field | Rule | Meaning |
|---|---|---|
| `event_id`, `account_id`, `event_type`, `event_date`, `currency` | required | `currency` is the **sold** currency, the one debited. `event_date` is the conversion's trade date (Ruling 5A.3). |
| `amount` | **REQUIRED**, `Money` in `currency`, `> 0` | the **sold** amount debited, as the source reports it |
| `bought_amount` | **REQUIRED** (a new field), `Money` whose currency **≠** `currency`, `> 0` | the **bought** amount credited, in the bought currency, as the source reports it |
| `settlement_date` | OPTIONAL | recorded, never read by replay (Ruling 1.1). FX spot commonly settles T+2 or T+1. |
| `corrects_event_id` | OPTIONAL | §2 |
| `source_reference` | OPTIONAL | |
| `listing_id`, `quantity`, `cost_basis`, `split_ratio`, `counterparty_account_id`, `reverses_event_id` | **FORBIDDEN** | A conversion is between two cash balances of **one** account. A cross-account movement is a transfer (§6), and a transfer never changes currency (Ruling 6.2). |
| any rate field | **does not exist** | Ruling 5A.7 |

**Why the sold currency is the event currency.** Some convention has to be fixed, because the
event carries two currencies and the existing rules key on one. The sold side is the natural
choice for three reasons:

- `amount` keeps the meaning it has on `BUY`, `FEE` and `WITHDRAWAL`: the magnitude leaving
  `(account, event.currency)`.
- The existing deferred rule "a reversal must be in the same currency as its target" then
  refers to one well-defined currency.
- It matches how conversions are instructed ("sell USD 1,000 for HKD").

**Rejected alternative: bought currency as the event currency.** It is equally definable and
has no advantage. The rejection is only so that exactly one convention exists.

**Consequence for `ledger.py` (finding F11).** `bought_amount` is the **only** `Money` on any
event that is **exempt from**, and in fact **must violate**, the rule "every `Money` must be in
the event currency". The module docstring and `_require_event_currency` need an explicit,
type-specific exception. The two currencies must differ (a same-currency conversion is
rejected). `bought_amount` has to be added to `CONDITIONAL_FIELDS`, forbidden on every other
type. `has_same_content` covers it automatically once it is a dataclass field. The persistence
schema needs a second currency column for it.

### RULING 5A.3 — As-of inclusion: both legs on `event_date`, the trade date

Both legs enter `S(D, L)` when `event_date ≤ D`. `settlement_date` is not read.

**Why.** This is the reasoning of Ruling 1.1. If one leg entered on trade date and the other
on settlement date, the state in between would count the converted value twice, or omit it.
Trade date also matches the `BUY` that the conversion typically funds on the same day.

### RULING 5A.4 — Same-date rank 1; no special ordering

Covered in Ruling 3.1. Both legs are additive on distinct cash keys, so order within a day
cannot change the end-of-day state.

### RULING 5A.5 — Flow classification: an internal exchange, never an external flow

A `CURRENCY_CONVERSION` is **not** an external flow, at portfolio level or at account level. It
is not income, not a fee and not a transfer.

**Why.** No value crosses the portfolio boundary. The account exchanges one asset (cash in
currency A) for another (cash in currency B). That is economically the same kind of event as a
`BUY`, which exchanges cash for shares and is not a flow either (PRD §9.6 counts only money
entering or leaving).

**Rejected alternative: `WITHDRAWAL` of the sold amount plus `DEPOSIT` of the bought amount.**
The balances come out the same (Example 5A-A), but two spurious external flows appear. CP3 would
then treat an ordinary conversion as the investor withdrawing and re-contributing money, which
distorts every flow-adjusted return (§9.6).

**What CP3 will see (named, not decided).** In reporting currency, the two legs valued at the
market FX rate of the conversion date will generally differ slightly, because of the dealer's
spread and any intra-day timing. That difference is part of return, as an FX or transaction-cost
effect. It is not a flow. How §8.4 attributes it is a CP3 ruling.

**Fees.** A commission the source reports **separately** is a separate `FEE` event. It is
account-level (no `listing_id`), in the currency charged, with the same `event_date`. The
conversion's `amount` and `bought_amount` are the amounts exchanged.

If the source reports only a debit that **includes** the commission, record that debit as
`amount` and add **no** `FEE`. Recording both would double-count (Example 5A-C). This is the
same pattern as Ruling 4.3.

A cost embedded in the rate (a spread) is **not** separated in CP1. Separating it needs a
market reference rate, which is market data, and inventing one would fabricate a fee.
Whether a conversion `FEE` is capitalized anywhere does not arise, because cash has no basis.
The fee-capitalization question (Note 1) concerns securities only and stays undecided.

### RULING 5A.6 — Reversal and correction

A `REVERSAL` of a conversion removes **both** legs at every `D`, for every `L ≥` the reversal's
sequence (Ruling 2.1). It carries the target's sold currency, which is the deferred same-currency
rule.

Partial reversal of one leg does not exist. A wrong amount on either leg is corrected by
reversing the whole event and appending a replacement `CURRENCY_CONVERSION` with
`corrects_event_id`. The two are appended atomically, with the reversal first (Ruling 2.3,
finding F10).

### RULING 5A.7 — No rate is stored, and a displayed rate is a computed value

Per PD-0024 §1 and Tech Plan §13.E:

1. **Never stored.** No rate field exists on the event or in the ledger schema. The two amounts
   are the facts.
2. **Never an FX observation.** The ratio of the two amounts is never written to, read as, or
   substituted for an `FXObservation`/`FXRate`. It is never used:
   - to convert any other amount;
   - to value any position or balance;
   - to fill a missing FX observation.

   A missing market FX rate stays `MISSING_FX_HISTORY` (Tech Plan §13.E) even when a
   conversion on that date exists.
3. **Not computed in CP1.** Replay does not compute a rate at all.
4. **If a surface later displays one,** it is a **derived value computed at read time** from the
   two stored amounts. The engine computes it and the AI layer never does (P1). It is
   auditable back to the event's two amounts (P9), and its methodology-registry entry states
   the following:
   - **Formula:** `implied_rate = bought_amount.amount / amount.amount`, quoted as *units of
     bought currency per one unit of sold currency*, labelled with both currency codes in that
     order. The inverse quote is a separate, labelled value, not a silent flip.
   - **Arithmetic:** exact `Decimal` division, then rounding to a precision fixed in the
     registry entry. Rounding happens only at the end. The precision is a registry field, not a
     UI choice, so two surfaces cannot show different values (NFR-001).
   - **Judgment class:** Fact about the user's own transaction. It is **not** a market rate and
     must be labelled as implied by the recorded amounts, including any spread. It supports no
     judgment ("you got a bad rate") without a market reference point (P4), and that comparison
     would be CP3-or-later methodology.
   - **It never feeds** any other computation (item 2 above).

### Example 5A-A — Same-date conversion, then a purchase in the bought currency

Account A1, a multi-currency account at a US broker. Listing H@XHKG (HKD). The amounts are
hypothetical.

| seq | Type | Detail | `event_date` |
|---|---|---|---|
| 1 | `DEPOSIT` | A1, 10,000 USD | 2025-04-01 |
| 2 | `CURRENCY_CONVERSION` | A1, `currency` = USD, `amount` = 1,000 USD, `bought_amount` = 7,780 HKD, `settlement_date` 2025-04-04 | 2025-04-02 |
| 3 | `FEE` | A1, a = 2 USD (commission reported separately; no `listing_id`) | 2025-04-02 |
| 4 | `BUY` | A1, H, q = 200, a = 7,000 HKD | 2025-04-02 |

| `D` | A1 USD | A1 HKD | H | Derivation |
|---|---|---|---|---|
| 2025-04-01 | 10,000 | 0 | 0 | seq 1 only |
| 2025-04-02 | 8,998 | 780 | 200, basis 7,000 HKD | USD: 10,000 − 1,000 − 2 = 8,998. HKD: 0 + 7,780 − 7,000 = 780. |
| 2025-04-04 | 8,998 | 780 | 200 | unchanged. Settlement is not read. |

- **Order independence.** Fold seq 4 before seq 2: HKD goes 0 − 7,000 = −7,000 intra-day, then
  + 7,780 = **780**. The end of day is the same. The intra-day −7,000 is not a state.
- **External flows** for the portfolio to 2025-04-04: only +10,000 USD (seq 1). seq 2 is an
  internal exchange. seq 3 is a cost.
- **Rejected `WITHDRAWAL` 1,000 USD + `DEPOSIT` 7,780 HKD.** The balances are identical (8,998
  USD, 780 HKD), but the external flows become +10,000 USD, −1,000 USD and +7,780 HKD, which is
  wrong under §9.6.
- **Implied rate**, only if a surface ever shows it: 7,780 / 1,000 = **7.78 HKD per USD**. It is
  computed from seq 2's two amounts, not stored, and not an FX observation.
- The `BUY`'s basis is **7,000 HKD**, in its event currency. Nothing about the USD paid for
  those HKD attaches to the basis (see open point OI-6).

### Example 5A-B — Correcting a conversion

This continues Example 5A-A. The broker's confirmation shows 7,750 HKD, not 7,780. seq 5 and
seq 6 are appended in one transaction.

| seq | Type | Detail | `event_date` |
|---|---|---|---|
| 5 | `REVERSAL` | `reverses_event_id` = seq 2, `currency` USD | 2025-04-10 |
| 6 | `CURRENCY_CONVERSION` | A1, 1,000 USD → 7,750 HKD, `corrects_event_id` = seq 2 | 2025-04-02 |

| `(D, L)` | A1 USD | A1 HKD | Derivation |
|---|---|---|---|
| (2025-04-02, 4) | 8,998 | 780 | as in Example 5A-A |
| (2025-04-02, 6) | 8,998 | 750 | seq 2 is excluded (both legs). USD: 10,000 − 1,000 − 2 = 8,998. HKD: 7,750 − 7,000 = 750. |

If seq 5 were visible without seq 6 (which the atomic append forbids), the state would be
USD 10,000 − 2 = 9,998 and HKD 0 − 7,000 = −7,000. Both legs disappear together, and neither
leg lingers alone.

### Example 5A-C — Commission inside the reported debit

The source reports "USD 1,002.00 debited, including USD 2.00 commission; HKD 7,780 credited".

| Recording | A1 USD at 2025-04-02 | Valid? |
|---|---|---|
| `amount` 1,002, no `FEE` | 10,000 − 1,002 = **8,998** | yes |
| `amount` 1,000 + `FEE` 2 | 10,000 − 1,000 − 2 = **8,998** | yes |
| `amount` 1,002 + `FEE` 2 | 10,000 − 1,002 − 2 = **8,996** | **no**: the commission is counted twice |

Note the side effect. The implied rate differs between the two valid recordings:
7,780 / 1,002 = 7.76447… (7.7645 at four decimal places) against 7,780 / 1,000 = 7.78. This is one more reason the implied rate
is labelled "implied by the recorded amounts" and never treated as a market rate.

---

## 6. Transfers: internal versus external, and cost basis

### RULING 6.1 — Classification (PRD §9.6)

| Transfer | Portfolio-level flow class | Account-level flow class |
|---|---|---|
| `counterparty_account_id` present (**internal**) | **none**: a movement within the portfolio, never a flow and never a return | external flow of the account |
| absent (**external**), cash form | **external cash flow**, the same class as `DEPOSIT` / `WITHDRAWAL` | external |
| absent (**external**), security form | **external in-kind flow** | external |

An in-kind flow is valued at market on `event_date` for CP3 return purposes. The valuation
convention belongs to CP3's denominator ruling, which is out of scope.

A transfer to a **different portfolio** of the same user has no counterparty inside this
portfolio. It is recorded as external in each portfolio.

### RULING 6.2 — An internal transfer is a matched pair, and "matched" is defined

Two events form an internal pair iff all of the following hold:

- they are in the same portfolio;
- one is `TRANSFER_OUT` and the other is `TRANSFER_IN`;
- each names the other's account as `counterparty_account_id`;
- they have the **same `event_date`**;
- they have the **same `currency`**;
- they have either the same `amount` (cash form) or the same `listing_id` and `quantity`
  (security form).

**Why the same date.** Portfolio-level neutrality (the CP1 mandatory scenario) must hold at
**every** `D`, not only after both legs land. If the in-leg is dated later, every state in
between shows the asset outside the portfolio. That looks exactly like a withdrawal followed by
a deposit (Example 6-D).

**Rejected alternative:** an "in transit" holding between the legs' dates. It is realistic for
multi-day broker transfers, but it adds a state class for no V1 need. If the source reports two
dates, both legs take the `TRANSFER_OUT` date.

**Why the same currency and amount.** A leg pair across currencies would be an unrecorded
currency conversion. It would break the no-conversion rule and native-currency neutrality. A
real conversion is a `CURRENCY_CONVERSION` inside one account (§5A). Money that is both moved
between accounts and converted is recorded as a transfer in one currency plus a conversion in
whichever account the source shows the conversion in.

The persistence step's deferred rule "the matching opposite transfer leg must exist" must use
this definition (finding F1).

### RULING 6.3 — Basis on an internal security transfer is carried, not declared

The receiving account's basis for the moved units is the basis that leaves the source account.
Portfolio-level total basis is therefore unchanged by construction.

An internal `TRANSFER_IN` therefore carries **no** `cost_basis` (finding F2). A declared value
could contradict the carried one, and neither side could be preferred without a rule.

**When the carried basis is determinate is set by Ruling 0.4.5 (1.2):**

- a whole-position move carries every lot intact, for any number of lots;
- a partial move from a single candidate lot carries `c × q`;
- a partial move from two or more candidate lots is unresolved on both sides, because *which*
  lots move is lot selection, which stays reserved.

The portfolio-level total is unchanged by the internal move itself. A same-day sale from two
or more lots can still leave it unresolved (0.4.5 (b)).

### RULING 6.4 — Basis on an external security `TRANSFER_IN`: from the event, or unknown

- If `cost_basis` is present, it is the transferred units' basis, in `event.currency`.
- If it is absent, the basis of those units is **unknown**. It is not zero, not the market value
  on the transfer date, and not inherited from other lots (PRD §9.3).

A position whose units do not all have known basis has **total basis unknown**. Replay may
additionally report the known part and the count of units with unknown basis. It must never
present the known part as the position's basis. Whether a downstream metric presenting the
known part is `LIMITED` or `INSUFFICIENT_DATA` with `MISSING_COST_BASIS` is a CP3 metric-state
ruling.

After a `SELL` from such a mixed position, whether the remaining basis is known depends on lot
selection. It is reported unresolved (Ruling 0.4.4 (b)). A single unknown-basis lot stays
unknown after a sale (0.4.4 (b′)).

### Example 6-A — Internal cash transfer (matches B0b fixture E6)

State before the transfer: A1 USD 2,500, A3 USD 0.

| seq | Type | Detail | `event_date` |
|---|---|---|---|
| k | `TRANSFER_OUT` | A1, a = 1,000 USD, counterparty A3 | 2025-02-10 |
| k+1 | `TRANSFER_IN` | A3, a = 1,000 USD, counterparty A1 | 2025-02-10 |

`S(2025-02-10)`:

- A1 = 2,500 − 1,000 = **1,500**.
- A3 = 0 + 1,000 = **1,000**.
- Portfolio USD = 1,500 + 1,000 = **2,500**, equal to the 2,500 before the transfer.
- Portfolio-level external flows: **none**.

### Example 6-B — External in-kind `TRANSFER_IN` without basis (matches B0b fixture E8)

`TRANSFER_IN` A1, listing M, q = 10, no counterparty, no `cost_basis`, dated 2025-03-10.

`S(2025-03-10)`: M = **10**, basis **unknown** (not 0). Portfolio external in-kind inflow: 10 M
on 2025-03-10.

### Example 6-C — Partial internal security transfer from a single lot

A1 holds U = 150, one lot, basis 5,625 USD.

| Type | Detail | `event_date` |
|---|---|---|
| `TRANSFER_OUT` | A1, U, q = 50, counterparty A3 | 2025-03-15 |
| `TRANSFER_IN` | A3, U, q = 50, counterparty A1, no `cost_basis` | 2025-03-15 |

`S(2025-03-15)`:

- A1: U = 150 − 50 = **100**, basis 5,625 × 100 / 150 = **3,750**.
- A3: U = **50**, basis 5,625 × 50 / 150 = **1,875**.
- Check: 3,750 + 1,875 = 5,625.
- Portfolio: U = **150**, basis **5,625**, both unchanged. Unit basis is 37.50 on both sides.

### Example 6-D — Mixed basis, and mismatched transfer dates (rejected)

**Mixed basis.** A1 holds U = 150, basis 5,625. An external `TRANSFER_IN` of U, q = 20, with no
`cost_basis`, is dated 2025-03-12.

`S(2025-03-12)`: U = **170**. Total basis is **unknown**. The known part is 5,625 on 150 units,
and 20 units have unknown basis. Presenting 5,625 as the basis of 170 units would be wrong.

**Mismatched dates (rejected).** Take Example 6-C with the in-leg dated 2025-03-18. Then
`S(2025-03-16)` has portfolio U = 100 instead of 150, and the portfolio appears to have
withdrawn 50 shares. Under Ruling 6.2 this pair is not valid.

---

## 7. `SPLIT`: can fractional-share treatment be deferred past CP1?

### RULING 7.1 — Yes, it can be deferred, under three conditions

The deferral argument is the same one B0b §3.6 makes for lot depletion. Every candidate
fractional convention agrees whenever the post-split quantity is an integer. The candidates
are:

- round,
- truncate with cash in lieu,
- retain the fraction.

So a fixture that only produces integral results asserts nothing any of them would dispute.

**Conditions.**

1. **The fixture stays bounded.** Every `SPLIT` in any CP1 fixture yields an integral
   account-level quantity, `q × new_units / old_units ∈ ℤ`. B0b fixture E5 does: 50 × 4 / 1 =
   200.
2. **CP1-C must not decide the convention by accident.** When the exact product
   `q × new_units / old_units` for an `(account, listing)` position is not an integer, or not a
   terminating decimal, replay must return an explicit **unresolved-convention condition** for
   that position from the split date on. It must not round, truncate, infer cash in lieu, or
   carry a truncated `Decimal`. The representation of that condition is engineering's choice.
   Its semantics are these:
   - no quantity is presented;
   - it is distinguishable from zero and from an inconsistency (§9).
3. **The test is on the account-level position**, which is what brokers apply splits to. Lot
   quantities may become fractional even when the position is integral: two 1-share lots under
   a 3:2 split become 1.5 + 1.5 = 3. Lot-level treatment is part of the depletion question,
   which is out of scope.

**Basis under a split (not deferred; CP1 needs it and there is no convention to choose).**
Total basis is unchanged. Unit basis is total basis divided by the post-split quantity. Unit
basis is derived and never stored, so no rounding convention enters the state. Unknown basis
stays unknown.

This is PRD §12.4 economic continuity, and it is the CP1 mandatory scenario "split changes
shares but preserves economic value".

**Not proposed here, by instruction.** A candidate for later ratification is to apply the ratio
exactly and record any cash in lieu as a separate `SELL` of the fractional quantity, which is
how brokers commonly report it. It is noted only so the later ruling starts from it.

### Example 7-A

| Input position | Ratio | Exact product | CP1-C result |
|---|---|---|---|
| 50 | (4, 1) | 200 | **200**. All conventions agree. Basis 7,500 is unchanged, and unit basis is 7,500 / 200 = 37.50. |
| 10.5 | (2, 1) | 21 | **21**. All conventions agree, even though the input was fractional. |
| 101 | (3, 2) | 151.5 | **Unresolved.** Round gives 152, truncate with cash in lieu gives 151, retain gives 151.5. |
| 100 | (1, 3) | 33.333… (does not terminate) | **Unresolved.** No exact `Decimal` exists. |

---

## 8. Supporting ruling: the reconstruction horizon for snapshot accounts

**RULING 8.1.** An account with `OPENING_POSITION` or `OPENING_CASH` events has **one** snapshot
date `S`: all its opening events carry the same `event_date`. `S(D, L)` for that account is
**not reconstructable for `D < S`**.

The result for such a `D` is an explicit not-reconstructable condition. It is **not** an empty
state, because an empty state is a claim that nothing was held (PRD §9.2, P5).

Every non-opening, non-`REVERSAL` event in that account must have `event_date > S`, because the
snapshot is the end-of-day state on `S` and already reflects that day's trades (finding F6).
The one exception is a `SPLIT` dated `S`. It is harmless, because it applies at the start of `S`
to zero units.

An account with no opening events is treated as complete from its first event. `S(D)` before
that event is the empty state. That treatment is a claim about the user's data; any
incompleteness surfaces through §9.

**Example 8-A.** A2 has `OPENING_POSITION` H q = 500 with no basis, and `OPENING_CASH` 3,000 HKD,
both dated 2025-06-30.

- `S(2025-06-29)`: **not reconstructable**.
- `S(2025-06-30)`: H **500** (basis unknown), HKD **3,000**.
- A `BUY` in A2 dated 2025-06-30 is rejected at append, because it is already inside the
  snapshot.

---

## 9. Supporting ruling: a negative end-of-day quantity

**RULING 9.1 (confirmed as the V1 rule by PD-0024 §4).** An end-of-day position quantity below
zero means either an incomplete history (a sale of units never recorded as acquired) or a short
position. Short positions are not in V1 (PD-0024 §4), so it is treated as an
**inconsistency**:

- the `(account, listing)` position is flagged from that date;
- no quantity is presented for it;
- it is never clamped to zero;
- the account state is marked as containing an inconsistency.

The cash effect of the offending event stays in the balance. It is a recorded fact, and
removing it would itself be a correction.

**The flag is sticky (stated explicitly in 1.2).** Once an `(account, listing)` position is
flagged at date `d`, it stays flagged for every `D ≥ d` at that ledger version `L`, even if a
later acquisition brings the quantity back to zero or above.

**Why.** Take a history that sold 15 of 10 held units. It is missing at least one acquisition,
so any later quantity it implies is short by an unknown amount. Only a ledger correction clears
the flag: an appended missing acquisition, or a reversal of the offending event, which gives a
new `L`. The position's basis is not presented while the flag stands (Ruling 0.4.4 (f)).

**O2, decided (PD-0024 §4): short positions are not in V1.** This ruling stands. A future
version that admitted shorts would have to replace it and add a borrow-fee type. Nothing in V1
does either.

The cash side is **not** symmetric. A negative *cash* balance is a valid recorded state
(Ruling 1.3, PD-0024 §3). A negative *quantity* is an inconsistency.

**Example 9-A.** A1 holds U = 10. A `SELL` of U, q = 15, is dated 2025-04-01.

`S(2025-04-01)`: 10 − 15 = −5, so the position is flagged inconsistent, with no quantity
presented and no clamp to 0.

---

## 10. Consistency check against the B0b golden fixture (not a ratification)

The fixture is B0b §11.1, events E1–E8. Its assertions are re-derived here under the rulings
above.

| ID | As-of | Hand derivation | Agrees with B0b §11.2 |
|---|---|---|---|
| T1 | 2025-01-05 | E1 only: A1 USD 10,000. AAPL 0. | yes |
| T2 | 2025-01-07 | E1, E2: AAPL 50. A1 USD 10,000 − 7,500 = 2,500. | yes |
| T3 | 2025-01-09 | E3, E4: 0700 500. A2 HKD 20,000 − 17,500 = 2,500. | yes |
| T4 | 2025-02-02 | AAPL 50, basis 7,500 | yes |
| T5 | 2025-02-03 | E5 applies at the start of 02-03 (Ruling 3.2) and is inclusive: 50 × 4 / 1 = 200. Basis 7,500. Unit basis 37.50. | yes |
| T6 | 2025-02-11 | Example 6-A: A1 1,500, A3 1,000. Portfolio USD 2,500 both before and after. | yes |
| T7 | 2025-03-04 | 200 − 50 = 150. Basis 7,500 × 150 / 200 = 5,625 (single lot). A1 USD 1,500 + 2,250 = 3,750 (not asserted in B0b). | yes |
| T8 | 2025-03-11 | Example 6-B: MSFT 10, basis unknown | yes |

**Fixture requirements the conventions add.** These are for CP1-D:

- E6 must be two events with reciprocal counterparties and the same date (Ruling 6.2).
- E8 must carry **no** counterparty. No P1 account holds MSFT, so an internal in-leg would have
  no valid out-leg.
- No event may carry a `settlement_date` whose use would change an assertion. None can, under
  Ruling 1.1.

No convention in this document changes a B0b expected value.

**T5 and T7 disposition under Ruling 0.4 (1.2).**

**T5, as of 2025-02-03. It stays in the fixture as numbers.**

- Quantity **200**, `AVAILABLE`.
- Total basis **7,500 USD**, `AVAILABLE`. There is no depleting event before 2025-02-03, so this
  is case 1 and depletion never enters.
- Unit basis **37.50** is not a replay output (0.4.8). The fixture asserts it as a **derived**
  check computed in the test from two replay outputs: 7,500 / 200 = 37.5, exact and terminating.
- The assertion that carries T5's meaning, "a split preserves economic value", is the pair
  *quantity 200, total basis 7,500 unchanged*. If the fixture prefers not to divide, dropping
  the unit-basis line loses nothing.

**T7, as of 2025-03-04. It stays in the fixture as numbers.**

- Quantity **150**, `AVAILABLE`.
- Remaining basis **5,625 USD**, `AVAILABLE`. The derivation is Example 0.4-A: one lot (E2),
  split by E5, depleted by E7 on 2025-03-03, with no other lot and no same-day acquisition.
  37.5 × 150 = 5,625, which terminates.
- It is **not** substituted with the unresolved state. `LOT_DEPLETION_UNRESOLVED` at T7 is a
  replay defect under 1.2 (finding R1), not an acceptable alternative expected value.

The other basis values derived in this document stay as numbers on the same grounds:

- Example 3-A, **3,750**;
- Example 6-C, **3,750 / 1,875**;
- Example 0.4-F whole move, **2,200**.

---

## 11. Findings on `src/domain/ledger.py`, for the engineer and PM to route (not edits)

| ID | Finding | Blocks CP1-C? |
|---|---|---|
| F1 | `CROSS_EVENT_RULES_DEFERRED` says "the matching opposite transfer leg must exist" but does not define "matching". It should use Ruling 6.2: reciprocal counterparty, same date, same currency, and the same amount or the same (listing, quantity). | yes, for scenario 2 |
| F2 | Internal security `TRANSFER_IN` should forbid `cost_basis`: counterparty present and security form together imply no `cost_basis` (Ruling 6.3). This is checkable within one event. | yes, for basis at portfolio level |
| F3 | **Decided (PD-0024 §2).** Add `INTEREST_CHARGED` with the field spec of Ruling 5.2: cash-only, `listing_id` forbidden. | no, for replay (the cash is the same as `FEE`); yes, for the taxonomy CP1 ships |
| F4 | **Decided (PD-0024 §1): added in CP1.** Add `CURRENCY_CONVERSION` with the field spec of Ruling 5A.2. It needs the new field `bought_amount` and the currency exception in F11. | yes: it is CP1 scope |
| F5 | Recommend an optional `ex_date` on `DIVIDEND` now. CP1 does not read it. It cannot be truthfully backfilled into an append-only ledger (§4). | no |
| F6 | Add a cross-event rule: one snapshot date per account for `OPENING_*`, and other events in that account dated after it (Ruling 8.1). | yes, for snapshot accounts |
| F7 | `ledger_seq`/`ledger_version` must be **commit-stable** per portfolio: no event may become visible below an `L` that has already been read (Ruling 2.3). Gaps are acceptable. | yes, for reproducibility |
| F8 | `SPLIT` is account-scoped. PRD §12.2 calls for *automatic* split support, which points at the CP2 `CorporateAction` feed. Before CP2, decide the single source of split application, or a split can be applied twice (ledger `SPLIT` plus feed). The module docstring's "SPLIT records the ratio as given" is compatible with either choice. | no (CP2) |
| F9 | Nothing links a `FEE` or `TAX` to the trade it belongs to. Any later ruling that capitalizes transaction costs into basis needs that link to be deterministic (Note 1). | no |
| F10 | A `REVERSAL` and its correcting replacement must be appended atomically, with the reversal's `ledger_seq` lower than the replacement's (Ruling 2.3). The deferred rule "corrects_event_id must name an event that is reversed" does not fix that order. | yes, for reproducibility |
| F11 (1.1) | `CURRENCY_CONVERSION` breaks two assumptions in the module as built. First, `bought_amount` is a `Money` that must **not** be in the event currency, so `_require_event_currency` and the module docstring's "every `Money` on an event must be in that currency" need a type-specific exception, plus the rule `bought_amount.currency ≠ currency`. Second, it is the one event that moves two `CashKey`s. `bought_amount` joins `CONDITIONAL_FIELDS`, forbidden on every other type. The schema needs a second currency column. No rate column may exist (Ruling 5A.7). | yes, for F4 |
| F12 (1.3) | Storage admits two live `SPLIT`s for one `(account, listing, event_date)` (review C1C-3). Recommend refusing the second at append (Ruling 3.4). Replay's `LEDGER_INCONSISTENT` flag remains the defense for anything already stored. | no (replay handles it); recommended |

The docstring's list of undecided items (trade or settlement date; the as-of semantics of a
reversal) is answered by §1 and §2 of this document. Split fractional treatment and lot
depletion remain undecided, as stated.

### 11A. Findings on `src/domain/replay.py` as built against 1.1 (1.2; read, not edited)

Scope: the module's treatment of §0–§9. I read the code and did not run it. Each finding cites
the ruling it departs from.

| ID | Finding | Severity |
|---|---|---|
| R1 | **Single-lot remaining basis and determinate carried basis are reported unresolved.** Three places cause it. First, `_Position.remove_units` sets `depleted = True` on every partial removal. Second, `add_units(..., _BASIS_CARRIED, ...)` sets it on every internal in-leg. Third, `_position_state` turns `depleted` into `LOT_DEPLETION_UNRESOLVED`. Under Ruling 0.4.3 case 3 and 0.4.5 (a)(b), these values are determinate and must be emitted. That covers B0b T7 (5,625), Examples 3-A (3,750), 6-C (3,750 / 1,875) and 0.4-F (2,200). The fix needs the lot model of 0.4.1: per-lot units and an exact rational unit cost with a currency. The current per-currency `known` sum plus one `depleted` flag cannot tell one lot from two. | **major**. It blocks CP1-D, because T7 would fail. |
| R2 | **Basis output depends on same-day `ledger_seq` entry order.** `remove_units` resets basis whenever the running quantity hits 0 *within* a day. Take a position of lot A. Same day: `SELL` all, then `BUY` B (in that seq order). Replay emits B's basis as `AVAILABLE`. Entering the same two facts in the opposite order yields `LOT_DEPLETION_UNRESOLVED`. The economic inputs are identical, and the output differs by typing order. That breaks Ruling 3.1 (seq is only a tie-break) and 3.3 (only end-of-day states count), and now 0.4.2. This defect exists **independently of 1.2**. The fix is to evaluate depletions per day against the candidate set and to reset basis only when the position **ends the day** at 0 (0.4.3 case 2). | **major** (correctness) |
| R3 | **A single unknown-basis lot, partly sold,** gets causes `{LOT_DEPLETION_UNRESOLVED, UNKNOWN_COST_BASIS}`. Under 0.4.3 case 3 and 0.4.4 (b′), it is unknown under every method, so only `UNKNOWN_COST_BASIS` (reason `MISSING_COST_BASIS`) applies. With a known lot and an unknown lot and then a sale (0.4.4 (b)), both causes are appropriate. | minor |
| R4 | **Exactness.** The present code performs no division, so its `Inexact` trap is correct for sums. The 1.2 proportional basis must be computed with exact rationals (for example `Fraction`), and a non-terminating result must become an `INSUFFICIENT_DATA` **state** with a cause such as `BASIS_NOT_EXACTLY_REPRESENTABLE`. It must never raise `ReplayInputError` (0.4.6). Termination is tested at the reported `D`. | build note for 1.2 |
| R5 | **Pairing for carried basis.** In-legs and out-legs are folded independently in `ledger_seq` order, so an in-leg can be applied before its out-leg, and the receiver's basis is not linked to the source. Carrying basis (0.4.5) needs the pair (Ruling 6.2) resolved at the out-leg's date, after the source's candidate set for that day is known. The receiver's quantity is unaffected. | build note for 1.2 |
| R6 | `CONVENTION_SET_ID = "ledger-replay/1.1"`. States produced by code that does not implement Ruling 0.4 must not be labelled `ledger-replay/1.2`. The ID changes when R1, R2 and R4 are implemented. | minor (manifest honesty) |
| R7 (1.3; C1C-1) | **Confirmed defect.** When the source ends the day at 0 through a sale plus a move, or through several moves, `_resolve_position` carries basis only for a sole whole move. Under reworded 0.4.5 (a), a single candidate lot carries `c × q` on every out-leg. The test `test_whole_move_plus_another_depletion_is_unresolved_on_the_receiver` pins the wrong expected value. **Correct:** A3 = 600 USD, `AVAILABLE` (Example 0.4-G, G1). The review's P1b gives 300 / 700 (G2). | major for CP1-D; blocks the test |
| R8 (1.3; C1C-3) | Two same-day `SPLIT`s are applied per split in `ledger_seq` order. **Correct:** apply neither, and flag the position `LEDGER_INCONSISTENT` from that date, sticky (Ruling 3.4, Example 3-B). | minor, but the output is order-dependent |
| R9 (1.3; C1C-5) | An inherited carried basis is labelled lot depletion / `UNRESOLVED_CONVENTION` whatever the source's real cause. **Correct:** the source's own reason and detail (0.4.5 (c)): H1 split fraction under `UNRESOLVED_CONVENTION`; H2 `LEDGER_INCONSISTENT` (Example 0.4-H). | minor (auditability) |

**Checked and found consistent with the rulings:**

- the `(D, L)` selection and retroactive reversal (§2.1);
- the sort key and split-first rank (§3.1, §3.2);
- end-of-day-only negative checks (§3.3);
- cash effects for all types, including `INTEREST_CHARGED` and `CURRENCY_CONVERSION`
  (§0.2, §5, §5A);
- no dividend entitlement check (§4.2);
- integral-only splits, sticky unresolved splits, and a split before an opening on `S`
  (§7, §8);
- the snapshot horizon as `NOT_RECONSTRUCTABLE`, not empty (§8);
- a sticky negative-quantity flag with the cash effect kept (§9, now explicit);
- no cross-currency sums (§0.1).

### 11B. Build notes on `src/domain/replay.py` for the `FIFO/1` mode (1.4; read, not edited)

I read the module's lot model and day resolution only, to make Ruling 0.5 implementable against it.
I did not run it, and no value in this document or in `cp3_golden` part 3 comes from it.

| ID | Note |
|---|---|
| B1 | `_Lot` holds units, unit cost and currency. The `FIFO/1` mode also needs the origin `event_id` and its type, the acquisition date, the date kind (`TRADE`/`ENTRY`) and the carry history (0.5.1). The `none` mode must not emit them: its canonical JSON (CP1-D T10) must stay byte-identical. |
| B2 | `_resolve_position` decides basis per day from the candidate set, which is the right place. The `FIFO/1` branch replaces cases 3 and 4 and the multi-lot branch of 0.4.5 with 0.5.4 (groups by date, pro rata within a group) and 0.5.5 (each event's share). Cases 1 and 2 are unchanged. |
| B3 | Relief records must be kept per depleting event, not only the end-of-day lots: CP3's realized gain and the taint of in-kind flows and sales read them (0.5.14). |
| B4 | `_pair_transfers` matches in `ledger_seq` order. In the `FIFO/1` mode, match within each group of identical legs in ascending `event_id` order (0.5.6), so that a hop's in-leg id does not depend on entry order. The `none` mode's values do not depend on pairing (0.4.5), so it may keep its order. |
| B5 | `_Carry` hands lots to the receiver. In the `FIFO/1` mode it hands the out-leg's shares with the hop appended. When the source is flagged or holds an opaque lot, it hands an opaque lot with the source's causes. That is the existing `unresolved` path. |
| B6 | The existing sticky `unresolved_depletion` with `unresolved_causes` is exactly 0.5.9 (b)'s basis-unresolved status. In the `FIFO/1` mode it must be set only by an incoming opaque lot, a same-day cycle or an unrepresentable basis, and **never** by a multi-lot depletion. |
| B7 | `CONVENTION_SET_ID` stays `ledger-replay/1.3` for the `none` mode. A `FIFO/1` state carries `ledger-replay/1.4` and `FIFO/1`. |
| B8 | `performance/taint.py`'s `TODO(ledger-replay/1.4)`: replace the zero-day rule by the end-of-day lot-book rule (0.5.14; `performance/1.5` Ruling 1.1a). |
| B9 (1.5) | In the `FIFO/1` mode, a lot from an `OPENING_POSITION` or external `TRANSFER_IN` carrying `acquired_on` takes `a` = `acquired_on` and the kind `RECORDED` (Ruling 0.6). The `none` mode must not read the field, so its canonical output stays byte-identical. The field itself (ledger, schema migration 0014+) is the engineer's per PD-0036. |

---

## 12. Open issues

- **OI-1.** Reporting-currency cost basis. HG1 round-4 §7.3 committed CP1 to translating basis at
  the **transaction-date** FX rate. CP1-C replay (this document) produces native-currency basis
  plus event dates, which is sufficient input. The translation itself needs dated FX (CP2).
  The PM should confirm that the HG1 commitment is met by "native basis + date carried in CP1,
  translation in CP3", or schedule it differently.
- **OI-2.** CP3 must include ledger events in valuation-time snapshots **by local event date**
  (Ruling 1.2), not by instant. Record this as an input to the CP3 as-of ruling.
- **OI-3.** No taxonomy for genuine economic reversals, such as dividend claw-backs, trade busts
  after settlement and cash in lieu. `REVERSAL` must not be used for them (Ruling 2.4).
- **OI-4.** Pending rulings named as dependencies here, all outside CP1 fixtures:
  - the lot-depletion method, for every case Ruling 0.4 leaves unresolved (0.4.4, 0.4.5 (c),
    §7 condition 3);
  - capitalization of transaction costs (Note 1);
  - the income-timing and attribution bucket for dividends and debit interest (§4, §5);
  - the metric state for partially known basis (§6.4);
  - the fractional-split convention (§7).
- **OI-5.** Output shape for determinism (NFR-001 byte-identical states), for example whether
  zero-quantity positions and zero balances are emitted. This is engineering's to fix and
  document. It is not a methodology choice, but T10 depends on it being fixed.
- **OI-6 (1.1).** Reporting-currency basis of a purchase funded by a conversion. Under OI-1 and
  PRD §8.3, a `BUY` in HKD is translated at the **market** FX rate of the `BUY` date. The rate
  implied by the user's own `CURRENCY_CONVERSION` is never used (Ruling 5A.7, PD-0024 §1). So
  the reporting-currency basis can differ from the USD the user actually gave up, by the
  conversion spread and any date gap. I believe this is correct: the spread is a cost, not
  basis, and linking a conversion to a later purchase would need a funding-attribution rule
  that does not exist. It is stated so CP3 does not rediscover it as a defect. CP1 is
  unaffected.
- **OI-7 (1.1).** The CP1-D fixture has no conversion and no `INTEREST_CHARGED`. If the PM wants
  CP1-D to prove the two new types, Examples 5-A, 5A-A and 5A-B are hand-derived candidates
  that depend on no reserved convention. They use no lot depletion, fee capitalization or
  fractional split. Adding them is a fixture-scope choice for the PM.

- **OI-8 (1.2). A monetary rounding convention for proportional basis.** Under 0.4.6, a
  non-terminating proportional basis is reported insufficient. That happens routinely: any
  single lot whose unit count has a prime factor other than 2 or 5, partly sold. A rounding
  convention would recover a number. It needs two things:
  - an ISO 4217 minor-unit table as reference data;
  - an allocation rule that keeps removed plus remaining equal to the original. One option is to
    round the removed part and define the remaining part as the original minus the removed part.

  This is a Quant ruling, not an owner decision. It is not needed for CP1 fixtures, all of whose
  values terminate. It should be settled before CP3 realized and unrealized figures.
- **OI-9 (1.2).** Whether a multi-lot position whose lots all share one unit cost (0.4.4 (a′))
  should be recognized as determinate. It is excluded in 1.2 for simplicity. It is a candidate
  for a later version if real ledgers make it common, for example several `BUY`s at one price.

- **OI-4, status in 1.4.** The 1.0–1.3 text of OI-4 above is unchanged; it describes the `none`
  mode. Since then:
  - the lot-depletion method is decided: FIFO (PD-0035 §1), specified as the `FIFO/1` mode
    (Ruling 0.5);
  - fee capitalization is ruled: costs are not capitalized (`performance` Ruling 3.6);
  - income timing and buckets are ruled (`performance` §8);
  - the metric state for partly known basis is ruled (`performance` Ruling 3.10);
  - **the fractional-split convention is still reserved** (§7).
- **OI-10 (1.4).** A same-day cycle of internal moves of one listing stays `UNRESOLVED_CONVENTION`
  under `FIFO/1` (0.5.9 (c)). A fixed-point rule could resolve it, but none is standard, and real
  ledgers rarely produce one. It will be revisited only if one is observed.
- **OI-11 (1.4).** `ENTRY` lots (opening positions and external transfers in) are ordered by their
  arrival date, and translated to the reporting currency only when their basis is already in it.
  An optional recorded acquisition date (`performance` PF-1) would fix both. Like `ex_date`, it
  cannot be truthfully backfilled into an append-only ledger, so the earlier it exists the better.
  It is for the PM to route.
  - **(1.5) Answered.** The owner added `acquired_on` (PD-0036 §1). Ruling 0.6 specifies how it is
    used. A later date can still be added by correction (0.6.4), but only from the new `L`.

**Owner decisions: O1, O2 and O3 are decided in PD-0024.**

- **O1, decided:** margin accounts are **not in V1** (PD-0024 §3). Negative cash stays a valid
  recorded state (Ruling 1.3).
- **O2, decided:** short positions are **not in V1** (PD-0024 §4). Ruling 9.1 stands.
- **O3, decided:** a currency-conversion event is **added in CP1** (PD-0024 §1). It is specified
  in §5A.
- **Still open, and not needed now:** a settled-cash view (§1.1) and a knowledge-time view
  (§2.2). Both are possible later features.
- **Still reserved to later rulings, and untouched here** (PD-0024 §5): lot depletion,
  fee capitalization and the fractional-split convention.
