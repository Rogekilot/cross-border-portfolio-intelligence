# CP5 diversification, exposure, correlation, risk contribution and drift

Author: quant-analyst, native Codex delegated role, 2026-10-18.
Convention and registry id: **`diversification/1.2`** (supersedes `diversification/1.1` and earlier; 1.1
issued 2026-10-24 and 1.2 issued 2026-10-25, each by a `quant-analyst` subagent dispatched by the main
session). Status: authored for independent
implementation and review; not HG3 approval, source admission or investment policy.
**The full-NAV capital universe below is a candidate pending owner decision
OD-CP5-01.** CP3 §10 and HG1 Round 4 §9 item 5 reserved this choice to the owner.
The PM authorized implementation/validation of the candidate, not a human choice.

Dependencies are `performance/1.12`, `risk/1.11`, `market-data/1.16`,
`ledger-replay/1.5`, `FIFO/1`, `minor-units/1.1`. Their accepted definitions are
unchanged. CP5 uses the same currency, temporal availability and state machinery.
Any change to this document or its registry gets a new convention id after issuance.
The current registry is `registry/DIVERSIFICATION_1.2_REGISTRY.json`.

**(1.2) When this id is in force.** `diversification/1.2` is in force from the engineer's increment that
moves the code's market-data label to `market-data/1.16` (`market-data/1.16` §11 item 35). Until then
the code runs, and its manifests cite, `diversification/1.1` with `risk/1.10` and `market-data/1.15`;
the text of `diversification/1.1` is this file at commit `ae6dfdc` (SHA-256
`d110af25dbb393c441a26aac9326851d6303a476d02145115e7bc11be9fb9528`).

(As issued for 1.0: "Convention and registry id: **`diversification/1.0`**"; "Dependencies are
`performance/1.12`, `risk/1.9`, `market-data/1.14`, …"; "The current registry is
`registry/DIVERSIFICATION_1.0_REGISTRY.json`". As issued for 1.1: "**`diversification/1.1`**";
"`risk/1.10`, `market-data/1.15`, …"; "`registry/DIVERSIFICATION_1.1_REGISTRY.json`".)

**Change note, 1.1 → 1.2 (2026-10-25).** A label re-issue for the move of the code's market-data label
to `market-data/1.16` (`market-data/1.16` §11 item 35), with `risk` re-issued as `risk/1.11` for the same
reason. It changes no method, no threshold, no state and no wording rule, on the model of the 1.0 → 1.1
note below.

- **Registry (1.2):** `registry/DIVERSIFICATION_1.2_REGISTRY.json`, `registry_id`
  `diversification/1.2`. The fields that change, and nothing else:
  - `registry_id`: `diversification/1.1` → `diversification/1.2`;
  - `issued`: 2026-10-24 → 2026-10-25;
  - `change_note`: the 1.1 → 1.2 note;
  - `common.implementation_version`: `[0]` `diversification/1.1` → `diversification/1.2`, `[2]`
    `risk/1.10` → `risk/1.11`, `[3]` `market-data/1.15` → `market-data/1.16`; the other four items
    unchanged.

  No entry changes. `common.frequency.grid` ("`risk/1.9` section 2 …") and `common.reason_rule`
  ("… `risk/1.9` section 7.3 …") are kept: they cite where those rules are defined, and `risk/1.10` and
  `risk/1.11` leave both sections unchanged (`risk` Ruling 9.2 (1.10), last bullet). `status` and
  `authored_by` are the 1.0 text. I built the file by replacing exactly these six values in the 1.1
  file's text and checked, field by field, that no other value differs. File SHA-256
  `0cd4fbe7d544d865448e734ccf61133fb406a0abda9bbb4876a1cda2513bedaa`; digest by
  `diversification.contracts.digest` `4f27f1e957e36a6c0c749228153d5fb266e0a9ffd0b4f212fc95e8899e852297`
  (the 1.1 file, recomputed today: `d9ad11ba1c39206ec54538a6b27a64b18d3ea168c1651f404455af38791373be`, as
  recorded in the 1.0 → 1.1 note). Computed read only; not an expected value of any metric.
  `DIVERSIFICATION_1.0_REGISTRY.json` and `DIVERSIFICATION_1.1_REGISTRY.json` stay unchanged as records.
- **Kept although stale:** the OD-CP5-01 status line, as in the 1.0 → 1.1 note.
- **Fixtures.** `cp5_golden/1.1-part1` (and the superseded `1.0-part1` record) is **unaffected**: no
  value, state, reason, detail or threshold changes, and its `methodology_id` `diversification/1.0` is a
  minimum, which `diversification/1.2` meets. `cp6-p3-source-reference/1.0` pins this document's 1.0
  text (commit `4c62f3e`), which is unchanged as a record.
- **For the engineer (the label-move increment):** `src/diversification/diversification_registry.json`
  becomes a byte copy of the 1.2 file; method keys read `diversification/1.2#<metric_id>`; baselines and
  pins over CP5 manifests move with the stated reason "diversification/1.2 label re-issue for
  market-data/1.16 (market-data/1.16 §11 item 35)".

**Change note, 1.0 → 1.1 (2026-10-24).** A label re-issue. It changes no method, no threshold, no
state and no wording rule. It answers review finding M-2 of the code-label move
(`reviews/TECH_REVIEW.md`, "Code label to market-data/1.15 — review (2026-10-24)" and its re-review).

- **Why.** PD-0067 decision 6 moved the code's market-data label to `market-data/1.15`, and `risk`
  re-issued its registry as `risk/1.10` for the same reason (`risk` Ruling 9.2 (1.10)). The 1.0
  registry's `common.implementation_version` named `risk/1.9` and `market-data/1.14`, so a CP5 result
  would cite a registry naming versions the code no longer runs (P9, PRD §33). This document's rule
  above forbids editing the issued file, so 1.1 is a new id.
- **What `implementation_version` names** (as `risk` Ruling 9.2 (1.10)): the convention ids the engine
  runs for the entry, `diversification` first, each dependency at the label the code carries. It is
  not a minimum. When a dependency's code label moves, the registry is re-issued under a new id in the
  same increment.
- **Registry (1.1):** `registry/DIVERSIFICATION_1.1_REGISTRY.json`, `registry_id`
  `diversification/1.1`. The fields that change, and nothing else:
  - `registry_id`: `diversification/1.0` → `diversification/1.1`;
  - `issued`: 2026-10-18 → 2026-10-24;
  - `change_note`: added (the 1.0 file has none), stating this re-issue;
  - `common.implementation_version`: `diversification/1.0` → `diversification/1.1`, `risk/1.9` →
    `risk/1.10`, `market-data/1.14` → `market-data/1.15`; the other four items unchanged.

  No entry changes. `common.frequency.grid` ("`risk/1.9` section 2 …") and `common.reason_rule`
  ("… `risk/1.9` section 7.3 …") are kept: they cite where those rules are defined, and `risk/1.10`
  leaves both sections unchanged. `status` and `authored_by` are the 1.0 text. File SHA-256
  `a3f1ac63723f7c3886aeaec13ada7814d98f28a7a934c84ef686618aea2c922a`; digest by
  `diversification.contracts.digest` `d9ad11ba1c39206ec54538a6b27a64b18d3ea168c1651f404455af38791373be`
  (the 1.0 file: `5acfe1bdca02964b49a1ed77e3962220506661437e69d4c819afa630ad18945d`). Computed read
  only; not an expected value of any metric. `DIVERSIFICATION_1.0_REGISTRY.json` stays unchanged as the
  record.
- **Kept although stale (label-only re-issue).** The status line "candidate pending owner decision
  OD-CP5-01", here and in the registry's `status`, predates PD-0041 decision 1, which chose `FULL_NAV`
  as the GLOBAL_PRODUCT capital policy. Correcting it changes the text's content, so it waits for a
  content version. It changes no computation: the capital-universe input still carries its own
  provenance (§2).
- **Fixture policy (1.1, ruled here).** `performance` Ruling 11.6 applies to `cp5_golden`, as `risk`
  Ruling 11.4 applies it to `cp4_golden`: a fixture's `methodology_id` names the **minimum** version it
  was derived and ratified under; a checker accepts the same family at that version or later; a change
  that alters any asserted value, state, reason, detail or threshold needs a new fixture version; and
  every change note names the fixtures it leaves unaffected. CP5 had no such rule before 1.1.
- **Fixtures.** `cp5_golden/1.1-part1` (and the superseded `1.0-part1` record) is **unaffected**: no
  value, state, reason, detail or threshold changes. Its `methodology_id` `diversification/1.0` is its
  minimum, which `diversification/1.1` meets. `cp6-p3-source-reference/1.0` pins
  this document's 1.0 text by SHA-256 `76520201…a89c21`; that text is this file at commit `4c62f3e`, and
  its §§2–6 are unchanged here.
- **For the engineer (the label track):** `src/diversification/diversification_registry.json` becomes
  a byte copy of the 1.1 file; method keys read `diversification/1.1#<metric_id>`
  (`diversification/contracts.py` builds them from a literal `diversification/1.0#` today); baselines
  and pins over CP5 manifests move with the stated reason "diversification/1.1 label re-issue (review
  M-2)".

## 1. Scope, exact arithmetic and input contract

These are descriptive current-capital statistics and a historical covariance model
of **current holdings at fixed current weights**. The latter is not the CP4 return
of the portfolio as actually held, a forecast, or a suggested rebalance. Historical
individual-security returns may predate acquisition; label this explicitly.

All inputs carry immutable ids, source/provenance, as-of/effective dates and content
digests. A manifest pins the ledger version, identity/metadata version and digest,
market-data release, FX and corporate-action sources, current instant if applicable,
registry id/digest, window/grid, every constituent, exact current weights and exact
statistical intermediates. Source admission is inherited; this method admits none.
Direct synthetic return-vector fixtures are identified as synthetic and do not
attest a real series. A bare unversioned number is not auditable production input.

Use exact rational amounts and returns internally. No value is calculated from a
rounded display value. Ratio/share/HHI/effective-count output quantum is 10^-12,
half away from zero; integer cluster counts are exact integers represented as
Decimal. Square roots follow the certified rational-bracket rule in risk §3.4.
An average of square roots uses rational interval sums until its final 10^-12
rounding is certified; an interval straddling a tie below width 10^-40 uses the
existing PRESENTATION_TIE rule. Never average already-rounded correlations.

`INSUFFICIENT_DATA` has no value, exact result, constituent result, cluster membership
or computed intermediate exposed as an alternative answer. Input identifiers and
non-numeric reasons remain auditable. A separate successful metric is not suppressed
by an unrelated failure. Each scalar is a standard metric envelope, including a
subject (bucket/pair/category/baseline/target) where necessary.

## 2. Capital universe and concentration

**No implicit production default.** A capital-universe input must explicitly name
`FULL_NAV` and carry immutable id/digest, scope and provenance. For actual use its
origin is `USER_CONFIRMED` with nonempty owner decision evidence; the engine does
not manufacture that evidence or treat a caller's bare boolean as approval. Until
OD-CP5-01 is answered there is no confirmed actual choice. Synthetic tests may use
`SYNTHETIC_CANDIDATE` with explicit candidate labeling only when all contributing
inputs are verified synthetic. Flipping a marker on actual data is not sufficient.

Absent/unconfirmed/mismatched choice produces INSUFFICIENT_DATA, null value and
`CAPITAL_UNIVERSE_UNCONFIRMED` for the five concentration metrics, all exposure
weights, average correlation, modeled volatility and both risk contributions.
Raw CP3 valuations are unaffected. Pairwise correlation and threshold components
depend on the explicit held-security universe and its histories, not the NAV
denominator, so they remain computable with that provenance. Drift of a refused
source is refused. Drift signatures for dependent metrics include the universe
choice id/semantics and approval provenance. No holdings-only variant is defined
or silently substituted here. HG3 must carry OD-CP5-01 as an open owner decision.

At as-of E use CP3 complete `portfolio_value` in reporting currency R. Its exact NAV
is T. Never use `portfolio_value_priced_holdings` as denominator. Missing cost basis
alone does not affect these calculations. All nonzero capital is represented:

* `SECURITY:<listing_id>`: sum values of this listing across accounts;
* `CASH:<native_currency>`: sum native cash across accounts, translated at E;
* `RECEIVABLE:<native_currency>`: accrued, unpaid ledger income, translated at E.

Listing identity is intentional: multiple listings of one instrument/issuer remain
distinct. The output must say **listing-and-cash-bucket concentration**, disclose
receivable buckets, and must not assert issuer concentration. An ETF remains one
security (PRD §18.4); no underlying security, sector or country look-through.

Zero components are excluded with a ZERO_VALUE exclusion record. Any negative
nonzero component is refused (`NEGATIVE_COMPONENT`, no new reason code), even when
net NAV is positive; unsupported short/margin/netting must not masquerade as long-only
weights. Missing/unvalued components suppress every full-NAV weight. T<=0 suppresses
weights with `NON_POSITIVE_TOTAL`. Component valuation states propagate to all weights.

Let v_i be each nonzero bucket value, w_i=v_i/T, so sum(w_i)=1 exactly.
Sort by decreasing exact w_i, then ascending canonical bucket key (UTF-8 lexical).

| Metric id | Exact definition |
|---|---|
| largest_position_weight | max_i w_i, including cash and receivable buckets |
| largest_security_weight | max over SECURITY buckets; no securities => unavailable, NO_SECURITY_POSITIONS |
| top5_concentration | sum of first min(5,N) bucket weights; not divided by five |
| hhi_concentration | sum_i w_i^2, fraction scale (not 0–10000) |
| effective_positions | 1 / hhi_concentration |

Cash-only with positive cash: largest/top5/HHI/effective=1 for one currency, while
largest-security is unavailable. Effective positions is the equal-weight bucket
count with the same HHI, not a count of independent economic risks. No concentration
alarm, regulatory HHI cutoff or investment preference is inferred.

## 3. Exposure classification

For each dimension d and category c, E[d,c]=sum_{i:class_d(i)=c} w_i.
Every dimension partitions the **same complete T**, including unknown and structural
buckets; sum_c E[d,c]=1 exactly. Zero categories may be omitted; drift uses the union
of explicitly complete maps and assigns 0 only to an absent category in such a map.
Display decompositions use performance §2.4 largest remainder with category key ties.

* Country: security issuer domicile as explicitly supplied in versioned metadata.
  Neither MIC/exchange, listing currency, transaction currency, issuer name nor ETF
  investment geography is a country substitute. The result is **issuer-domicile
  exposure**, not revenue or underlying-market exposure.
* Sector: versioned security classification with taxonomy id and provenance. Missing,
  ambiguous or conflicting classification => `UNKNOWN`, not guessed from names.
  ETFs without actual look-through data have sector `UNKNOWN`; an issuer's asset
  management business is not the fund's sector exposure. CP5 does not use look-through
  data even if supplied, because V1.5 owns that feature.
* Currency: listing's quotation/trading currency for securities; native denomination
  of cash/receivables. The ledger trade currency does not replace quotation currency
  (performance §1.8). This is denomination exposure, not business currency risk or a
  hedge-adjusted net FX exposure.
* Asset class: explicit instrument `COMMON_STOCK` => `EQUITY`; `ETF` => `ETF`.
  The ETF label deliberately asserts nothing about its underlying asset allocation.
  Any unrecognized type => `UNKNOWN`.
* Country and sector: cash => `CASH`; receivable => `RECEIVABLE`. Asset class uses the
  same structural names. Currency keeps their native currency rather than those labels.

`UNKNOWN` is a real category whose amount is still valued, not a missing valuation.
If any positive value is UNKNOWN in a dimension, **every category metric of that
dimension** is LIMITED with `UNKNOWN_CLASSIFICATION`, reason none; known category
numbers remain exact but coverage is incomplete. Report exact classified/unknown
shares and metadata ids. This limitation does not infect other dimensions or HHI.
Missing or ambiguous denomination instead makes its currency category UNKNOWN;
if the same missing identity prevents valuation, the stronger valuation refusal wins.
No new data source or inferred classification is authorized by this convention.

## 4. Historical legs and alignment

Use CP4's DAILY weekday / WEEKLY Friday / MONTHLY calendar-month-end grids, full
periods only, declared stubs, explicit requested window, default request 36 months
WEEKLY. Each listing uses its own market close at the grid date, each currency the
same admitted historical FX fixing used by CP4. The CP4 M_t and Current rules apply.
No close-time shift, forward fill beyond the existing freshness policy, interpolation,
pairwise deletion, listwise deletion, shortened window or new return frequency.

Each security needs a documented **total-return** leg for its listing. The CP4
RAW-close/dividend/split total-return construction may be reused for a security, with
its action-disagreement and FX rules unchanged. A price-only feed is insufficient
(`NOT_TOTAL_RETURN`, no new code); absence of a dividend row is not evidence of
complete corporate-action coverage. Adjusted prices must not also receive actions.
The issuer/instrument/listing and action coverage used are pinned. Unknown action
coverage suppresses the leg with `TOTAL_RETURN_COVERAGE_UNCONFIRMED`.

For native level L and FX X(native→R), the reporting leg is
r_i,k=L_i(g_k)*X_i(g_k)/(L_i(g_(k-1))*X_i(g_(k-1)) - 1.
Thus (1+r_R)=(1+r_native)(1+r_FX); the cross term is retained.
Cash and receivables use a fixed nominal-unit FX-only leg X(g_k)/X(g_(k-1))-1.
In R that leg is identically 0. No risk-free yield is invented; interest, credit,
liquidity and collection/default risk are outside this fixed nominal model.
Cash/receivable model assumptions are always disclosed; their actual historic
bookings remain part of CP4 actual-portfolio TWR, not these current-weight legs.

A pair uses exactly the requested grid and only its two legs. A broken third leg
does not invalidate an otherwise valid pair. The average and clusters require every
positive-weight security leg on that same entire grid. Risk contribution requires
every positive-weight capital bucket leg. Missing data anywhere required suppresses
that aggregate; no surviving-subset estimate or renormalization is allowed.

The CP4 count thresholds apply to correlations, clusters, model volatility and all
risk contributions: DAILY n<259 insufficient, 259–780 LIMITED, >=781 AVAILABLE;
WEEKLY n<51 insufficient, 51–154 LIMITED, >=155 AVAILABLE; MONTHLY n<11 insufficient,
11–34 LIMITED, >=35 AVAILABLE. Period/input states also propagate. A count refusal
does not borrow a lower-severity STALE_DATA code. Non-synchronous closes are disclosed
as CP4 comparability information, not automatically a new state. They may distort
correlations; historical association is not causality or a forecast.

## 5. Correlation and deterministic positive-correlation clusters

For aligned n-period vectors, mean_i=sum r_i/n and S_ij=sum_k
(r_i,k-mean_i)*(r_j,k-mean_j). C_ij=S_ij/(n-1) is sample covariance.
Pairwise Pearson rho_ij=S_ij/sqrt(S_ii*S_jj). Either zero variance makes that pair
INSUFFICIENT_DATA (`ZERO_VARIANCE`), including its diagonal if requested. A nonzero
diagonal is 1; the canonical core emits unordered distinct pairs i<j only.

For the positive-weight SECURITY set S, average_correlation =
sum_{i<j in S}(w_i*w_j*rho_ij) / sum_{i<j in S}(w_i*w_j).
This is capital-pair weighted, excludes cash/receivable pairs, and excludes diagonals.
Record security capital coverage sum_{i in S}w_i, excluded cash/receivable ids and
weights, pair count, numerator and denominator. Fewer than two securities or a zero
pair denominator => INSUFFICIENT_DATA (`TOO_FEW_SECURITIES`). Any unavailable pair
refuses the whole average; a constant-return security is never silently dropped.

Clustering is a deterministic graph method, equivalent to threshold single linkage:
caller supplies exact rational **0 < tau <= 1**; no default and no risk-policy claim.
No threshold => INSUFFICIENT_DATA (`CLUSTER_THRESHOLD_REQUIRED`). Invalid threshold
=> INSUFFICIENT_DATA (`INVALID_CLUSTER_THRESHOLD`). Require the same complete pair
set as the average. An undirected edge exists iff rho_ij>=tau (equality included).
For positive tau compare **S_ij>0 and S_ij^2 >= tau^2*S_ii*S_jj**, entirely exactly;
never compare rounded rho. Connected components, including isolated vertices, are
sorted internally by bucket key and externally by their first key. Their number is
`correlation_cluster_count`, their membership is associated structured output.
Fewer than two securities => unavailable. A component is not a clique: A–B and B–C
can connect A and C without an A–C edge. No automatic claim of economic factors,
causality, hidden exposures or material investment risk follows from a component.

## 6. Current-weight covariance risk model and contribution

Using the full capital universe and one complete grid, Q=w' C w and A=260/52/12 for
DAILY/WEEKLY/MONTHLY. This requires no benchmark, risk-free curve or matrix inversion;
singularity is allowed, and constant legs have zero covariance. Define:

* `modeled_volatility` = sqrt(A*Q), an annualized historical covariance estimate at
  current fixed weights; it is distinct from CP4 `risk_volatility`.
* b_i = w_i*(Cw)_i, an exact contribution to periodic model variance;
* `risk_contribution_share` = b_i/Q;
* `risk_contribution_component` = (b_i/Q)*sqrt(A*Q), annualized volatility points.

Euler's identity gives sum b_i=Q, sum shares=1 and sum components=model volatility.
Shares can be negative or exceed 1, even with nonnegative capital weights. Never clamp
or take absolute values. Negative contribution denotes hedging covariance in this
historical model, not a recommendation. Annualization cancels from the share.
When Q=0, modeled_volatility=0 if the history is sufficient, but shares/components
are INSUFFICIENT_DATA (`ZERO_MODEL_VARIANCE`); do not fabricate a zero allocation.
A genuinely negative exact Q is an invalid covariance construction, not rounding:
refuse (`INVALID_COVARIANCE`). No ridge, shrinkage or positive-definite repair is used.

## 7. Drift against accepted history or an explicit user target

`drift_absolute` is current minus previous accepted snapshot value, in the source
metric's unit. Weight/share changes are **percentage-point differences**, not relative
percentage growth; neither division by baseline nor annualization is performed.
It covers concentration, each exposure category, CP4 beta, volatility, active return,
tracking error, and maximum drawdown. Drawdown is the CP4 signed window statistic;
a more negative change is a deeper within-window maximum decline, not an all-time
peak/current-underwater claim. CP5 does not invent a current drawdown-state metric.

The baseline is an explicit immutable input with id, digest, as-of strictly before
current, `accepted=true` and nonempty acceptance evidence/reference. A supplied but
unaccepted baseline is unavailable (`BASELINE_NOT_ACCEPTED`); missing baseline is
`NO_BASELINE`. The engine never creates acceptance or silently selects another snapshot.
The two snapshots must identify the same actual portfolio, reporting currency,
metric/subject/unit, methodology semantic version, history frequency, lookback rule
and duration, and applicable benchmark/risk-free ids and model definitions. Rolling
windows may have different endpoints by design, but their duration and rule match.
For TRAILING_MONTHS compare requested month count, not elapsed days (leap years and
month lengths differ). For CUSTOM, YTD, SINCE_INCEPTION and MAX_AVAILABLE compare
the exact requested calendar-day duration and the same rule; unequal durations are
incompatible. Full-grid observation counts may differ due to endpoint alignment;
retain both counts and source states. AS_OF capital metrics have no history
signature (NOT_APPLICABLE), rather than an invented window. Semantic units distinguish
FRACTION weights/HHI/exposures/volatility/returns/drawdown, RATIO beta and COUNT
effective positions; retain the actual source envelope's unit as well.
Different ledger versions are expected. Different market-data vintages are disclosed
as possible restatement effects; the delta is an observed difference, never causality.

Exposure maps additionally need the same classification taxonomy and metadata digest;
otherwise `INCOMPATIBLE_BASELINE` avoids calling reclassification an investment change.
Complete category maps may differ because holdings changed; use their union and the
complete-map implicit zeros. An incomplete map cannot supply an implicit zero.
For generic metric snapshots compare a canonical compatibility signature provided by
the pinned computation, not a caller's unverified label. Missing signature fields,
state/value contradictions, future baselines or semantic differences are refused.
Both source values must be computable; worst input state propagates. No new reason
codes are introduced; these conditions are named details.

`drift_target_gap` is current minus a **user-supplied** target, in the source unit.
Target input requires immutable id/digest, explicit user provenance, effective date
<= current as-of, exact value, metric/subject/unit/reporting currency, and a semantic
signature compatible with the source metric (including frequency/window/benchmark
where applicable). Missing target => `NO_USER_TARGET`; generated/recommended/ambiguous
provenance => `TARGET_NOT_USER_DEFINED`; mismatch => `INCOMPATIBLE_TARGET`.
Each explicit target can be compared independently. Missing categories do not become
zero targets, and a partial map is not completed or normalized into a user allocation.
There are **no default materiality thresholds, preferences, breaches, warnings or
rebalancing actions** in CP5. A signed gap is a FACT conditional on a USER_POLICY
reference; severity and policy interpretation belong downstream of HG3.

## 8. State and evidence summary

Start AVAILABLE; combine all applicable causes by worst severity and the existing
performance §1.5 / risk §7.3 same-severity reason priority. Unknown classifications
are LIMITED with no new reason code. Structural invalid/missing inputs, insufficient
counts and degenerate denominators are INSUFFICIENT_DATA with null value and a precise
detail. Real market input failures retain their existing reason codes. Synthetic
lineage is contagious whenever any contributing input is synthetic.

Concentration/exposure need one complete as-of valuation and no historical minimum.
Correlation/cluster/risk metrics use §4's statistical minimum. Drift needs two
compatible computable snapshots or one computable snapshot plus a compatible explicit
user target; it has no independent history floor beyond the source metric's floor.
Every evidence record retains exclusions, denominator, window, n, both thresholds,
reporting currency, state/causes, convention/registry identity, relevant reference,
and the limits described above. A real benchmark missing affects only benchmark-
dependent source drift, not HHI, exposures, correlations or covariance risk.

## 9. Independent sources and correctness evidence

References checked 2026-10-18. They justify mathematics, not source licensing/admission:

* [US DOJ HHI definition](https://www.justice.gov/atr/herfindahl-hirschman-index): sum
  of squared shares. Our unit-fraction rescaling and inverse equal-weight count are
  algebraic transformations; antitrust cutoffs have no portfolio policy meaning.
* [Eric Zivot, University of Washington, Portfolio Theory](https://faculty.washington.edu/ezivot/econ424/introductionPortfolioTheory.pdf):
  portfolio covariance mathematics. Pearson correlation is normalized sample covariance.
* [Dirk Tasche, Capital Allocation: the Euler Principle](https://arxiv.org/abs/0708.2542):
  homogeneous-risk allocation; differentiating sqrt(w'Cw) yields §6 exactly.
* [Federal Reserve FEDS 2010-10, §4.1](https://www.federalreserve.gov/pubs/feds/2010/201010/index.html):
  continuous marginal contributions and the Euler allocation principle.

Fixtures: `fixtures/cp5_golden/cp5_golden_part1.json`; independent closed forms and
stdlib calculator in the adjacent derivation document/directory. No fixture value
was obtained from product code. The calculator imports no product module. Required
mutations include: use priced-only NAV; drop cash; combine listings by issuer; use
trade currency as country; put ETF manager sector into fund exposure; fill missing
returns; use native-only returns; drop FX cross term; use current actual-portfolio
TWR as constituent returns; include diagonal in average; average rounded pairs;
renormalize after dropping a constant/missing leg; strict > rather than >= at cluster
threshold; clip negative contributions; infer zero cash contribution in foreign
currency; fabricate zero risk shares at Q=0; subtract displayed values for drift;
infer a target; accept a future/unaccepted baseline.

## 10. CP3 registry debt

The 24 CP3 metric ids require a machine-readable appendix before HG3 (STATUS's CP4
entry ruling). `registry/PERFORMANCE_1.12_REGISTRY.json` is a documentary transcription
of existing performance rulings, not a new numeric method or a replacement of historic
CP3 manifest ids. Runtime consumption and identity equality remain the engineer's
work. The separate inventory names every id and exact ruling; it must not be counted
as wired merely because this appendix exists.

(1.1) The CP3 appendix in force is `performance-registry/1.1`
(`registry/PERFORMANCE_1.12_REGISTRY_APPENDIX_1.1.json`, `registry_id` still `performance/1.12`). It
names `market-data/1.15`, for the reason of the 1.0 → 1.1 change note above. The 1.0 file stays as the
record (`CP3_REGISTRY_APPENDIX_INVENTORY.md`).

(1.2) From the market-data/1.16 label move, the CP3 appendix in force is `performance-registry/1.2`
(`registry/PERFORMANCE_1.12_REGISTRY_APPENDIX_1.2.json`, `registry_id` still `performance/1.12`). It
names `market-data/1.16`, for the reason of the 1.1 → 1.2 change note above. The 1.0 and 1.1 files stay
as records (`CP3_REGISTRY_APPENDIX_INVENTORY.md`).
