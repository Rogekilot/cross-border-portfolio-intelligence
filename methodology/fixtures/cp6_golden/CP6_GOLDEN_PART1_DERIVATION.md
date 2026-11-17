# Independent CP6 rule cases — `cp6_golden/1.0-part1`

Issued 2026-10-19 by the Quant/methodology specialist, independently of the CP6
product author. Authority and exact formulas are `CP6_INSIGHT_CONVENTIONS.md`.
These are synthetic user limits for specification testing, not the real owner's
risk limits. Expected outcomes were authored from the predicates below, never
copied from implementation output. The accompanying stdlib calculator imports no
product modules and checks the issued input/expected pairs; it does not validate
upstream financial facts or prove that implementation adapters enforce integrity.

## Fixture expansion and proof boundaries

Each case expands `defaults.current` with `input.current`. A historical baseline
starts with the current defaults (not the case's modified current), then
`defaults.baseline`, then `input.baseline`. Each listed policy starts with
`defaults.policy`, then its overrides. Missing policies means no personal policy.
All fields are scalar/flat except subjects/limitations. Symbolic identity strings
are explicit test symbols, not SHA-256 results and not real proof records.

`upstream_failure` is the independently stated outcome of an induced upstream
failure. It is not a product input permission, a production boolean to trust, or
proof that tampering was exercised. Engineer tests must reproduce the named real
failure through actual adapters, and report that integration evidence separately.
Fixture reason strings are semantic diagnostic requirements; an implementation
may use a documented equivalent enum without changing the meaning/refusal.

## Hand derivation

1. **S1–S6:** one supported scalar is a fact. LIMITED keeps that fact and caveat.
   A missing value cannot become zero. UNKNOWN is still UNKNOWN. Eight threshold
   correlation components are not eight independent economic risks. Hypothetical
   state/scenario is outside these actual-only adapters and must be refused.
2. **U1–U8:** compare exact active return with zero. `-1/50 < 0`; zero and `1/50`
   do not trigger. `-1/2500000000000 = -0.0000000000004` rounds to displayed zero
   but remains strictly negative. All supported underperformance observations
   stay OBSERVATION, including limited history or temporal seams. No benchmark
   selection and the wrong metric cannot support this rule.
3. **H1–H16:** `3/5 > 1/2` increases; `2/5 < 1/2` decreases; equality produces no
   change. `1250000000001/2500000000000 = 0.5000000000004` exceeds one half behind
   the same displayed number, requiring a rounding caveat. Wrong portfolio,
   account, currency, capital/method semantics, frequency, horizon, model or bucket
   is not the same analytical question. An equal as-of is not earlier. A limited
   value still permits a caveated Observation. Variable-span statistics are
   deliberately deferred rather than interpreting their changing sample span.
4. **P1–P18:** exact `3/5 > 1/2` breaches the synthetic maximum; equality to
   `3/5` and a cap of `7/10` do not. Signed MDD `-1/4 < -1/5` breaches an explicit
   MINIMUM, without absolute values. Available/full evidence yields Warning;
   LIMITED sufficiency or temporal comparability caps it at Attention. No policy
   means no preference judgment. Only exact selector/scope and inclusive effective
   dates match. Identical refs can deduplicate; two different active caps conflict.
   The global FULL_NAV denominator and an empty consent reference are not personal
   risk constraints.
5. **P19:** `1500000000001/2500000000000 - 3/5 = 1/2500000000000 > 0`.
   Displayed equality must not be used to erase the exact breach.
6. **P20:** the positive radical has square
   `2250000000003/6250000000000 = 9/25 + 3/6250000000000`.
   It is strictly greater than `sqrt(9/25)=3/5`. Its increment is approximately
   `0.0000000000004`, so both displayed values round to `0.600000000000`.
   The independent conclusion needs only the rational square comparison, not
   that approximation or a recalculated volatility. P21's square `9/25` is exact
   equality and does not breach. Unsupported mixed radical terms in P22 are
   refused, not numerically estimated.
7. **P23–P26:** the issue's finite whitelist does not make an effective-position
   minimum an implemented personal constraint. Portfolio and account caps never
   inherit each other's scope. A correctly scoped account cap can apply. An
   unavailable current metric cannot produce an alternate numeric policy answer.
8. **P27–P29:** unknown or limited freshness, and unknown temporal comparability,
   each cap a supported synthetic policy breach at Attention. The default FULL
   freshness is a normalized supported rule premise, not an assertion that an
   actual CP4/CP5 adapter has discovered a source timestamp. In production the
   optional CP3 freshness auxiliary is valid only under the complete CP5 linkage
   specified in conventions §6. Integration must demonstrate those dependencies.
9. **I1–I8:** failure of any upstream question/result/policy integrity dependency,
   or mismatched auxiliary valuation manifest/result/scope/Current instant,
   defeats the claim before predicates/severity. Reproduction means both verified
   inputs and exact expected answer comparison, not just a successful rerun.

Each surfaced expected row fixes taxonomy, severity, comparison-basis type and
direction independently. Every source limitation must survive in the resulting
claim/packet. A NOT_TRIGGERED result means only that this rule did not trigger;
it does not mean "safe", "suitable", or "within all user objectives".

Run from any directory with Python >=3.9:

```sh
python3 methodology/fixtures/cp6_golden/derivation/cp6_part1_calculator.py
```

This issue is frozen after delivery. Corrections, if required by review, need a
new fixture issue plus an explicit change log; do not silently replace expected
outcomes to fit product behavior.
