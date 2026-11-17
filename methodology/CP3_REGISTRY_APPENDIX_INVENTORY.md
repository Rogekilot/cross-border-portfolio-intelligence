# CP3 registry appendix inventory

Author: quant-analyst, native Codex, 2026-10-18.

`registry/PERFORMANCE_1.12_REGISTRY.json` contains **24 entries**, one for each existing
`src/performance/registry.py` metric id. It transcribes the accepted
`CP3_PERFORMANCE_CONVENTIONS.md` definitions; it changes no number, state, fixture,
formula, source authorization or owner decision. Registry id is `performance/1.12`;
appendix identity is `performance-registry/1.0`.

The earlier §14 table used suggested dotted identifiers. This appendix maps the
implemented underscore identifiers to those already accepted rulings and completes
the required fifteen PRD §33 fields, state handling, judgment class, reference and
limitations. No missing registry row is a reason to invent a new metric.

| Existing metric id | Definition authority in performance/1.12 |
|---|---|
| `holding_value` | §§1.1, 1.2, 1.8 |
| `cash_value` | §§1.3 |
| `receivable_value` | §§1.3, 8.1 |
| `portfolio_value` | §§1.4 |
| `portfolio_value_priced_holdings` | §§1.4a |
| `gain_absolute` | §§5.1 |
| `return_twr` | §§5.1-5.5 |
| `return_annualized` | §§7.1-7.2 |
| `return_mwr` | §§6.1-6.4 |
| `return_mwr_annualized` | §§6.1-6.4, 7.1-7.2 |
| `income_amount` | §§8.1-8.3, 8.6 |
| `fees_amount` | §§8.4, 8.6 |
| `taxes_amount` | §§8.2, 8.4, 8.6 |
| `financing_amount` | §§8.4, 8.6 |
| `conversion_result_amount` | §§8.5-8.6 |
| `realized_gain` | §§3.7-3.8 |
| `realized_gain_total` | §§3.10 |
| `unrealized_gain` | §§3.9 |
| `unrealized_gain_total` | §§3.10 |
| `remaining_basis` | §§3.9a |
| `since_acquisition` | §§9.7 |
| `attribution_money` | §§9.1-9.3, 9.5 |
| `attribution_return` | §§9.4-9.5 |
| `attribution_breakdown` | §§9.6, 2.4 |

Important transcription details:

- The partial `portfolio_value_priced_holdings` contains **all valued NAV components**,
  including cash and receivables (§1.4a), despite its historical name. It never supplies
  a complete denominator and is not emitted beside an already computable NAV.
- Annualization uses `whole_calendar_months/12 + remaining_days/365` (§7.1), including
  the end-of-month rule; it does not interpolate by days in the last calendar month.
- Income/cost amounts preserve signed lines, and a line with no recorded event is a
  known zero; known taxes never imply complete tax knowledge (§8.6).
- Partial gain aggregates and partial NAV are distinct mechanisms. Gain exclusions
  follow §3.10; the partial NAV is never used to construct them.
- `attribution_breakdown` is a money decomposition apportioned to the parent's
  displayed line, using the §9.6 grouping corrections (receivable belongs to the
  dividend's listing; conversions have no single currency).
- Money attribution may survive a nonpositive return base or a total-loss log failure;
  return attribution may not (§9.5). No blanket suppression joins the two.
- No existing CP3 manifests are rewritten to insert this new appendix digest. A new
  centralized registry consumer may expose it; any manifest identity change requires
  deliberate versioned engineering work and non-regression checks.
- `market-data/1.14` is the currently accepted dependency at CP5. The historical
  performance/1.12 header/§14's market-data/1.11 reference is preserved as history.

Validation scope: JSON shape, 24 unique ids and static equality with the existing
performance metric-id set are checked independently of runtime implementation. All
prior CP3 golden numerical fixtures remain unchanged. Runtime registry consumption,
UI availability and independent review are separate work; this document does not
claim they are complete.

## Appendix re-issue `performance-registry/1.1` (2026-10-24)

Author: `quant-analyst` subagent, dispatched by the main session. Everything above is the
`performance-registry/1.0` record and stays as written.

**Why.** PD-0067 decision 6 moved the code's market-data label to `market-data/1.15`. The 1.0
appendix names `market-data/1.14` in `common.implementation_version`, and its
`historical_version_note` calls 1.14 the "current accepted CP4 dependency". A composed response
prints this registry's id and digest beside conventions that name `market-data/1.15`, so one audit
chain names two versions (review finding M-2 of the code-label move, `reviews/TECH_REVIEW.md`).
`implementation_version` names the labels the code runs, not minimums (`risk` Ruling 9.2 (1.10),
`diversification/1.1` change note). The 1.0 file is not edited (one id, one text: P9).

**The new file:** `registry/PERFORMANCE_1.12_REGISTRY_APPENDIX_1.1.json`. The fields that change, and
nothing else:

- `appendix_id`: `performance-registry/1.0` → `performance-registry/1.1`;
- `issued`: 2026-10-18 → 2026-10-24;
- `change_note`: added (the 1.0 file has none), stating this re-issue;
- `common.implementation_version`: `market-data/1.14` → `market-data/1.15`; the other four items
  unchanged;
- `common.historical_version_note`: now "… market-data/1.15 is the market-data label the code runs
  (PD-0067 decision 6); performance-registry/1.0 cited market-data/1.14, and performance/1.12's
  original §14 cited market-data/1.11."

**`registry_id` stays `performance/1.12`.** No performance ruling changes, so the method keys
(`performance/1.12#<metric_id>`) still name the same definitions. The appendix text is identified by
`appendix_id` (with the digest), as it was at 1.0. The 24 entries, `status`, `authored_by` and every
other field are the 1.0 text. File SHA-256
`3c50b3b72eb6fbff636620d43a1e4656761d2afa71bd150e209aecffdca96c6b`; digest as the loader computes it
(`PerformanceMethodologyRegistry.digest`)
`b2f8af49d582179f2455ffb6e5189f7e22fe7a0092edbb68b7e48e49e98ded69` (1.0:
`c8989e34bcdba31d9b99c7a5eacb5edef8a99108e521d974cbec5685acbf524e`). Computed read only; not an
expected value of any metric.

**`CP3_PERFORMANCE_CONVENTIONS.md` is not edited.** Its header and §14 (1.12) still name
`market-data/1.11` as at the issue of `performance/1.12`. Changing that text would be a new
`performance` id under its own header rule, and would move every `performance/1.12#…` rule id in code,
for a citation that no manifest reads. The appendix, which is the PRD §33 registry for CP3, carries
the running label. The header's stale citation is an open item for the next `performance` version.

**Fixtures.** `cp3_golden` parts 1–4 are unaffected: their `convention_sets` are minimum versions
(`performance` Ruling 11.6), and no value, state, reason or detail changes.

**For the engineer (the label track).** `src/product_contract/performance_methodology_registry.json`
becomes a byte copy of the 1.1 file; the loader's accepted `appendix_id` becomes
`performance-registry/1.1` (it refuses anything else today, as it should). RECOMMENDATION: wherever
the registry's id is printed (for example `web_api/analytics_composer.py`), print `appendix_id` with
it, since two appendix texts now share `registry_id` `performance/1.12` and only the digest tells them
apart.

## Appendix re-issue `performance-registry/1.2` (2026-10-25)

Author: `quant-analyst` subagent, dispatched by the main session. Everything above is the record of
`performance-registry/1.0` and `1.1` and stays as written.

**Why.** The engineer's next increment moves the code's market-data label to `market-data/1.16`
(`market-data/1.16` §11 item 35, and "When a manifest may cite 1.16" point 1). The 1.1 appendix names
`market-data/1.15`, and `implementation_version` names the labels the code runs (`risk` Ruling 9.2
(1.10)). An issued file is not edited, so the appendix is re-issued first. **It is in force from that
label-move increment**; until then the code runs 1.1 with `market-data/1.15`.

**The new file:** `registry/PERFORMANCE_1.12_REGISTRY_APPENDIX_1.2.json`. The fields that change, and
nothing else:

- `appendix_id`: `performance-registry/1.1` → `performance-registry/1.2`;
- `issued`: 2026-10-24 → 2026-10-25;
- `change_note`: the 1.1 → 1.2 note;
- `common.implementation_version`: `market-data/1.15` → `market-data/1.16` (item `[2]`); the other four
  items unchanged;
- `common.historical_version_note`: now "… market-data/1.16 is the market-data label the code runs once
  its label move is made (market-data/1.16 section 11 item 35); performance-registry/1.1 cited
  market-data/1.15 (PD-0067 decision 6), performance-registry/1.0 cited market-data/1.14, and
  performance/1.12's original §14 cited market-data/1.11."

**`registry_id` stays `performance/1.12`**, for the reason given for 1.1. The 24 entries, `status`,
`authored_by` and every other field are unchanged. I built the file by replacing exactly these five
fields in the 1.1 file's text and checked, field by field, that no other value differs. File SHA-256
`ef68208a2f6ca06cd5f6cade006a69dfa072fd661112b95874e05bc6e4df5840`; digest as the loader computes it
(`json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, SHA-256)
`f2aefda7232da0a46be1d1592bb50856becf1d10a237e30cf64d060437891a71` (1.1, recomputed today:
`b2f8af49d582179f2455ffb6e5189f7e22fe7a0092edbb68b7e48e49e98ded69`, as recorded above). Computed read
only; not an expected value of any metric.

**`CP3_PERFORMANCE_CONVENTIONS.md` is not edited**, for the reason given for 1.1.

**Fixtures.** `cp3_golden` parts 1–4 are unaffected: their `convention_sets` are minimum versions
(`performance` Ruling 11.6), and no value, state, reason or detail changes.

**For the engineer (the label-move increment).** `src/product_contract/performance_methodology_registry.json`
becomes a byte copy of the 1.2 file, and the loader's accepted `appendix_id` becomes
`performance-registry/1.2`. Pins over the digest move with the reason "performance-registry/1.2 re-issue
for market-data/1.16 (market-data/1.16 §11 item 35)". The 1.1 RECOMMENDATION on printing `appendix_id`
stands: three appendix texts now share `registry_id` `performance/1.12`.

