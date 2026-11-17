# CP6 insight conventions — `insights/1.0`

**Issued:** 2026-10-19. **Author:** Quant/methodology specialist, native Codex,
independent of the CP6 implementation. **Status:** issued method for the bounded
CP6 implementation and independent review; not a new owner decision or human gate.

## 1. Authority and the bounded deliverable

Authority is the PRD P1/P3/P4/P5/P7/P8/P9/P12, §§20–21 and CP6 §38.3;
PD-0006/0007 metric states; PD-0014 comparability and claim consistency; and
PD-0041, the owner's 2026-10-19 HG3 approval with conditions and CP6 authorization.
The capital denominator is now the owner's FULL_NAV, GLOBAL_PRODUCT choice. It
is a product calculation convention, never a personal risk cap or preference.

This method defines four complete deterministic rule families. The PM approved
this bounded inventory during CP6 dispatch. Selecting these families, refusing
ambiguous comparisons, strict equality boundaries, and conservative severity caps
are methodology/implementation choices within the approved product contract.
They do not manufacture user preferences or new market/data authorizations.

| Rule | Class | Basis | Highest severity |
|---|---|---|---|
| `metric_snapshot` | FACT | null; immutable source snapshot context | OBSERVATION |
| `benchmark_underperformance` | FACT | BENCHMARK | OBSERVATION |
| `history_change` | INTERPRETATION | PORTFOLIO_HISTORY | OBSERVATION |
| `user_limit` | PREFERENCE_DEPENDENT | USER_POLICY | WARNING, only under §6 |

No standalone "largest sector" interpretation, universal diversification score,
holdings-count diversification judgment, concentration alarm, forecast, advice,
trade/execution suggestion or invented significance tolerance is issued here.
The current snapshot is not relabelled PORTFOLIO_HISTORY to manufacture a reference
point. Ranking is deferred until a genuine comparison basis is implemented.

## 2. Exact inputs and evidence authority

CP6 consumes immutable CP4/CP5 result objects and their complete manifests. It
does not recalculate a financial metric, select a benchmark, fill a missing price,
change a state, shorten a window, annualize or convert a currency. An adapter may
expose existing CP3-derived financial facts through those results; this is not
independent certification of CP3 values. The originating financial method remains
responsible for its sufficiency and its financial truth.

Before any surfaced claim, verify upstream reproduction AND the canonical stored
result content against the supplied result digest. Checking only a manifest id is
insufficient: the same question can be paired with an altered answer. A CP6 packet
must name the exact metric row, including its subject, from the verified result.
Digest equality establishes integrity relative to the supplied local inputs, not
source admissibility, human consent, a digital signature or production readiness.

Each evidence reference preserves, without invented replacements:

- source engine, metric id/subject, presented Decimal, exact witness, metric state,
  reason, causes/details, caveats and upstream methodology key;
- upstream manifest id and result digest, canonical manifest/result payload;
- portfolio/account, ACTUAL versus model semantics, scenario id, reporting currency,
  as-of date, requested rule/months, effective window, frequency and observations;
- selected benchmark identity, selection/version and return/currency semantics when
  present, capital-universe identity/semantics, and upstream provenance/lineage;
- source timestamps, freshness and temporal comparability actually exposed upstream.
  An unavailable field is explicitly UNKNOWN or null with a limitation. It is not
  synthesized from the as-of date, wall clock or observation count.

CP4/CP5 currently supply ACTUAL results. Scenario ids must be null; scenario or
ACTUAL/HYPOTHETICAL mismatch is refused. A fixed-current-weight historical model
remains explicitly a model of the actual holdings, never actual realized history.
Synthetic provenance is retained in every insight/packet and human-facing claim.

An invalid/tampered proof, missing result row, mismatched subject, state/value
contradiction or incompatible request context yields a typed diagnostic and no
surfaced financial claim. INSUFFICIENT_DATA yields no value anywhere in the
insight; neither an exact witness nor a baseline is an alternate numeric answer.
Diagnostics are not insights and are not counted as successful numeric claims.

## 3. Comparisons, rounding and semantic identity

All decision predicates use the originating exact witness, never a presented
rounded Decimal. Rational witnesses are compared as exact fractions. To compare
`x = s*sqrt(Q)` against rational `L`, compare signs first; for equal nonzero signs
compare `Q` with `L²`, reversing order for negative signs. Two signed square roots
are ordered similarly by their exact squares. No floating point approximation or
new financial estimate is permitted. Mixed sums of radicals without a supported
certified ordering, missing witnesses and inconsistent witnesses are refused.
Copying the originating displayed value into a claim does not redefine the exact
decision boundary. Where display ties but exact values differ, attach an explicit
rounding caveat; the reader must not see unexplained equal numbers called a breach.

Example: exact weight `1500000000001/2500000000000 = 0.6000000000004`, displayed
`0.600000000000`, strictly exceeds a user cap of `3/5`. The equality of the displayed
values must not hide that breach. The limit and its exact comparison remain in
the Proof Packet. Conversely, a displayed value rounded up to a cap is not itself
evidence of a breach.

History requires matching metric source/id/subject and scope, reporting currency,
ACTUAL/model identity, capital universe, relevant frequency and window semantics,
benchmark binding/return basis and all other comparison-relevant method choices.
For CP5 capital snapshot metrics, statistical frequency/window choices have no
effect on the metric and are excluded from its semantic key; their snapshots
still preserve the actual as-of date. For statistical metrics, they are required.
The semantic key is a canonical digest of those structured fields, validated from
the upstream manifests rather than trusted because a caller supplies a string.
It excludes changing as-of dates and the effective bounds of like-for-like rolling
windows, but includes the requested horizon and custom-window choices. An explicit
CUSTOM window is comparable only under the same defined custom-window semantics.
Two different metrics do not become comparable merely by sharing a semantic key.
The initial statistical-history adapter is deliberately narrower: fixed trailing
horizon, equal observation counts and identical requested frequency/horizon/method
choices. MAX_AVAILABLE and SINCE_INCEPTION variable-span statistical comparisons
are deferred, rather than calling a change in span a change in risk. A future
extension requires its own comparability method and independent examples.

An earlier snapshot must have an as-of strictly before the current one. Period
dates may differ as expected for the same rolling horizon; the packet contains both
windows and their observation counts. Differences of coverage, freshness, method
versions and temporal seams remain disclosed. A numerical history comparison is
only a comparison of recorded modeled/historical values, never a forecast or a
claim that a statistically significant risk change has occurred.

## 4. Snapshot and underperformance predicates

`metric_snapshot`: for any explicitly supported scalar CP4/CP5 metric with a
verified value, surface its value/state/caveats as FACT / OBSERVATION. Basis is
null: an unqualified numeric measurement does not assert "good", "bad", "too much",
"diversified", or a comparison to an invented reference. An exact count of
correlation clusters can be a fact; it is not proof of independent economic risks.
LIMITED retains its value and complete limiting caveats. INSUFFICIENT_DATA is
suppressed, not displayed as zero. Structural UNKNOWN classification remains
UNKNOWN and never becomes a known sector/country by name inference.

`benchmark_underperformance`: only CP4 `risk_active_return`, with an explicit
dated primary-benchmark selection and its immutable benchmark reference, is
eligible. Predicate is `exact active_return < 0`; zero and positive values do not
trigger. Class FACT, severity OBSERVATION in every triggering case. This compares
the actual engine-computed relative return over its declared historical window,
not the current market quote or an assumed SPY default. LIMITED sufficiency or
LIMITED temporal comparability remains explicit and cannot upgrade severity.

## 5. Historical change predicate

`history_change`: two eligible verified non-null metrics meeting §3, earlier and
current. Compare their exact witnesses; a strict difference triggers
INTERPRETATION / OBSERVATION with direction INCREASED or DECREASED and the exact
two source refs. Equality does not trigger. It may not claim a "meaningful",
"material", "significant", "unusual" or desirable change without a separately
defined user objective or supported comparison. No delta value is invented by the
explanation: a numerical delta is shown only if it already exists as a verified
upstream metric (e.g. a supported CP5 drift result); otherwise show the two values.
LIMITED historical/current inputs carry both sets of limitations and remain
OBSERVATION. Missing comparison evidence suppresses the comparison, although a
separate valid current snapshot may still be surfaced under its own rule.

## 6. Explicit user constraints, precedence and severity

The bounded numeric policy selectors are CP5 largest-position/security weight,
top-five concentration, HHI and country/sector/currency/asset-class exposure;
CP4 volatility and signed maximum drawdown. Other metrics can be snapshot/history
facts, but unsupported user-policy selectors are refused in this issue. A maximum
drawdown policy uses the upstream signed value literally: `-0.25` breaches MINIMUM
`-0.20`. No absolute-value conversion or guessed risk meaning is applied.

A policy must carry immutable id, version, content digest, nonempty explicit user
confirmation evidence, origin USER_CONFIRMED, exact scope identity, metric/subject,
source, semantic key, exact finite rational limit, direction MAXIMUM or MINIMUM,
and effective-from/until dates. It applies only when `from <= as_of <= until`
(a missing end is open-ended). Equality is within the limit. A MAXIMUM breach is
`x > L`; MINIMUM breach is `x < L`. The user limit is the reference point; no
generic concentration cutoff, regulatory index threshold, holding-count heuristic,
assumed risk tolerance or GLOBAL_PRODUCT denominator is substituted.

Scopes are exact: a portfolio aggregate matches its PORTFOLIO policy; an account
metric matches its ACCOUNT policy. Neither scope silently inherits the other's
cap. A policy's subject must identify the exact exposure bucket/security if the
metric is subject-specific. A policy for TECH does not cover UNKNOWN, and a USD
limit does not cover another currency. Expired/future/unrelated policies cannot
produce a breach. Identical repeated references may be deduplicated; two distinct
active policies with the same selector are a POLICY_CONFLICT and produce no
policy judgment. Do not choose the newest, most severe, broadest, or most convenient
one. The user must resolve contradictory or overlapping personal constraints.

User-policy precedence means a matching explicit user constraint determines the
preference judgment. This issue ships no generic heuristic to compete with it.
Independent factual snapshot/underperformance/history observations can coexist,
but may never contradict or quietly replace the user limit, or borrow its severity.

For a strict breach:

1. AVAILABLE metric, FULL supported freshness and temporal comparability, and a
   fully validated applicable policy -> PREFERENCE_DEPENDENT / WARNING.
2. LIMITED metric, or an AVAILABLE value with LIMITED/UNKNOWN freshness or
   temporal comparability ->
   PREFERENCE_DEPENDENT / ATTENTION, with the exact limitation explicitly in claim
   and packet. The claim is the computed value's relationship to the stated limit;
   it must not assert an established fully supported present risk breach.
3. INSUFFICIENT_DATA, absent/invalid/ambiguous policy, unsupported witness,
   incompatible scope/semantics or integrity failure -> no policy insight.

The rule-level freshness eligibility states FULL/LIMITED/UNKNOWN summarize actual
verified upstream freshness support; they are not a replacement for the canonical
CP3 freshness vector and do not arise from AVAILABLE sufficiency alone. CP4/CP5
outputs lacking the necessary freshness evidence remain UNKNOWN, which caps the
policy judgment at ATTENTION. Unknown source observation/retrieval timestamps are
also disclosed independently; a genuinely reproduced freshness vector can support
the claim without manufacturing those missing timestamp fields.

The PM approved one narrow optional auxiliary: a reproduced CP3 ComputationResult
may supply genuine freshness for a CP5 valuation dependency only when its manifest
id, result digest, portfolio/account scope and Current instant exactly match the
CP5 valuation reference. Preserve the actual source freshness vector and cite the
auxiliary dependency in the packet and reproduction. This is no new financial
rule, source of metrics or permission to infer freshness. An absent auxiliary
leaves UNKNOWN; an offered but mismatched/tampered auxiliary fails closed rather
than being silently ignored. This issue does not add a general CP3-metric adapter
or a CP4 series freshness auxiliary.

No breach means no policy insight, not a claim that the portfolio is safe, suitable,
diversified or globally "within your risk tolerance". No generic path can create
ATTENTION or WARNING. This is a severity ceiling, never a mechanism for an LLM to
raise severity. Warnings arise only from explicit numeric constraints in this issue;
the PRD's unusually severe generic-condition branch is not implemented.

## 7. Proof Packet and deterministic reproduction

Every surfaced insight has a machine-readable packet with all PRD §21 fields:
insight id/type, claim and judgment class/severity, exact metric refs, portfolio
snapshot id, null scenario id, basis/benchmark, period/frequency/observations,
threshold/limit if used, available source timestamps, method versions, freshness,
state/availability, limitations and permitted non-advisory explorations. Examples
are "inspect source evidence", "compare the declared historical window", and
"review your recorded limit". Never "buy", "sell", "rebalance now" or execute.

Packet contents and claim fields are immutable canonical data. Its id/digest bind
the rule/method version, every dependency, policy and comparison, source details,
classification, severity and claim parameters. Cosmetic calculation timestamps
must not change identity. Rule order, input enumeration order or repeated identical
refs must not alter the same logical output. Invalid duplicates that disagree are
not silently discarded. Preserve source values/states and all limiting caveats in
the packet and structured claim. Explanatory text is deterministically rendered
from those fields and cannot change the evidence set, value, count or severity.

Reproduction verifies source inputs and regenerates the rule output. It compares
the exact expected packet/insight digest; merely rerunning without an expected
answer is RESULT_NOT_COMPARED, never REPRODUCED. Any missing/extra/replaced input,
policy, context, limit, claim, severity or caveat prevents a reproduced verdict.
No external LLM, data fetch or mutation is part of reproduction.

## 8. Minimum data, refusal evidence and limitations

CP6 inherits numerical sufficiency from CP4/CP5 and does not introduce observation
thresholds. One supported metric is sufficient for a factual snapshot; a historical
comparison needs exactly the two compatible supported values and their lineage;
underperformance needs the supported relative-return output plus primary benchmark;
a policy judgment needs the supported value plus one valid effective user policy.
This is a count of rule dependencies, not a statistical sample-size claim.

The independent fixtures in `fixtures/cp6_golden/` test rule predicates, scope,
severity and refusal expectations from synthetic symbolic normalized evidence.
They do not themselves demonstrate upstream reproduction or the truth of upstream
financial values. Engineer integration tests must construct real CP4/CP5 results,
verify their reproduction and exercise altered result/manifest/packet cases. The
stdlib calculator imports no product code and cannot bless implementation output.

This issued method does not close the HG3 evidence package's 66 supporting gaps,
approve/admit a real data source, select a portfolio benchmark, implement CP8
scenarios or create AI functionality. Each downstream claim still requires its own
supported dependencies. HG5 and later owner gates remain separate.
