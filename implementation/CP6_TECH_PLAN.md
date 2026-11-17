# CP6 deterministic insight slice — 2026-10-19

Authority: PD-0041, PRD §§20–21 and checkpoint 6. This plan is an additive
implementation within HG3's conditions; it does not authorize AI or delivery.

## Boundary and flow

`insight_service` is the public seam. It accepts typed actual CP4 RiskResult and
CP5 diversification Result sources together with their original replay inputs.
For each source it calls the existing reproduction API, requires REPRODUCED,
and compares the complete canonical stored answer with the fresh answer. An
advertised digest alone cannot authenticate a metric payload. Failure returns a
typed refusal before any insight number. Synthetic evidence needs explicit opt-in.

Verified sources are reduced to immutable canonical JSON, retaining the full
upstream manifest, exact numeric witnesses, causes, freshness-related disclosures,
window/frequency/observation counts, benchmark pins, identities, source files,
synthetic flag, actual state and portfolio/account scope. Current mode replays the
recorded instant and derived M_t through the original market-at provider.

`insights` owns deterministic rules and immutable Proof Packets. It computes no
financial metric. The Quant owns the comparison convention, eligible metric set,
severity and independent examples. The agreed bounded families are:

1. Metric snapshot: Fact / Observation, direct verified metric attribution.
2. Negative exact active return with selected benchmark: Fact / Observation.
3. Explicit comparable earlier snapshot: Interpretation / Observation, direction
   only; no invented materiality threshold or delta metric.
4. Explicit applicable user limit: Preference-dependent; an AVAILABLE supported
   breach with verified full relevant freshness/comparability can be Warning.
   LIMITED or unknown freshness/comparability caps the breach at Attention.

Equality never breaches a strict limit. Fraction/signed-root witnesses determine
comparisons. A displayed rounded scalar never determines threshold crossing.
Unsupported radical combinations are refused for comparisons. The FULL_NAV product
denominator is not a personal risk constraint. Different simultaneous personal
limits for one exact selector conflict; scope, dates and provenance are explicit.

The narrow optional CP3 freshness auxiliary is an actual ComputationResult. Its
entire manifest must equal CP5's embedded valuation manifest and its answer digest
must equal CP5's valuation_result_digest. Existing CP3 reproduction plus full
canonical answer equality verifies it. The reporting-total freshness vector then
supports CAPITAL_SNAPSHOT_VALUATION only. It does not attest historical covariance
or constituent-return freshness. Wrong account, ledger, release, instant, scope,
payload or answer refuses the source. Without it, source freshness is UNKNOWN.

Proof Packets carry claim/taxonomy/severity, exact source references, snapshot ids,
actual/scenario separation, comparison basis and policy digests, period/frequency,
observation counts, source date/instant metadata, method versions and registry
hashes, upstream freshness state and caveats, limitations and permitted explorations.
Unavailable source timestamps remain UNKNOWN. The CP6 manifest embeds all source
payloads and complete rule inputs. Reproduction re-verifies sources, regenerates
packets, compares all manifest keys in both directions and compares result digests.

## Evidence boundary

Each surfaced rule family will have independently issued Quant expectations plus
an actual source-adapter integration representative. This is new scoped CP6 proof,
not a claim that all 543 old HG3 rows or its 66 supporting gaps were independently
rechecked. No frozen HG3 package, prior fixture value or engine pin is changed.

Adversarial checks cover changed upstream payload/digest/manifest/input, strict
null and extra manifest fields, exact/equality boundaries, signed maximum drawdown,
LIMITED comparability, cross-portfolio/account semantics, policy conflicts, missing
data, synthetic default refusal, input-order determinism and Current replay.
No new dependencies, database schema, source admission, forecast, frontend or AI
provider is required. Database tests are root-serialized; this engineer runs pure
and in-memory source integration tests only.

## Candidate validation and concrete evidence

Frozen product candidate `insights/cp6-0.1` has the following actual focused run:

```
uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_insight_golden tests.product.test_insight_sources tests.product.test_insight_integration tests.product.test_approved_analytics_policy
```

Observed **101 tests passed, 14.725 seconds**. That consists of 59 independent
normalized Quant predicate cases, one explicit inventory check linking eight
integrity obligations to actual adapter tests, 29 actual source/rule integration
tests, and the separate policy engineer's 12 approved-policy tests. The inventory
is not counted as eight successful synthetic integrity probes. The actual adapter
methods execute those tamper scenarios against real engine results.

Reviewer counterexamples were recorded red before focused repair: malformed
upstream objects gave four errors; malformed nested history gave one error;
classification-taxonomy and cluster-threshold changes each incorrectly surfaced a
history interpretation. The repeated exact counterexamples now pass. Semantic
identity binds relevant taxonomy, financial conventions, benchmark entry, risk-free
reference, drawdown peak rule and correlation cluster threshold; it does not bind
changing snapshot rows as if all historical data had to be identical.

`python -m tests.product.insight_demo --output /tmp/NEW_UNIQUE_DIRECTORY` exports
actual synthetic CP4/CP5 source replays and all four rule families. It includes the
separate verified CP3 freshness Warning example and conservative unknown-freshness
Attention example. `summary.json` is readable; `result.json` contains complete
packets and source evidence; `FILES_SHA256.json` pins artifact bytes. No directory
is overwritten. No personal limit in that example is a real owner preference.

Root full regression and independent review remain separately owned and are not
claimed by this engineer's focused result. The original HG3 supporting-gap inventory
remains in force; any supplementary financial expectations are additive evidence,
never edits to the frozen HG3 package or old fixture values.
