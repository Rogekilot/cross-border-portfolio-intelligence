# HG3 — Professional Analytics Proof

**Status: APPROVED_WITH_CONDITIONS — owner decision recorded 2026-10-19 in PD-0041.**
Prepared 2026-10-18 by the main session. Implementation, independent review,
repairs and full PostgreSQL regression are complete. All reported results below
were executed; limitations and owner decisions remain explicit.
The original technical evidence below remains dated 2026-10-18. The owner's
subsequent decision and CP6 authorization are recorded in §14 and
`../../decisions/product/PD-0041-hg3-approved-with-conditions-and-cp6-start.md`.

## 1. Gate identity

HG3, following CP4 (risk/benchmark) and CP5 (diversification/drift), PRD §38.4.
The designated human product owner decides this gate.

## 2. Objective

Prove that portfolio analytics are mathematically correct, reproducible, properly
referenced and safely unavailable when inputs or authority are insufficient.
Keep synthetic method proof, real-data availability, PM acceptance and human
approval distinct.

## 3. Required deliverables

- CP4 volatility, beta, Jensen alpha, Sharpe, Sortino, downside deviation, maximum
  drawdown, tracking error/information ratio and benchmark comparisons.
- CP5 concentration, country/sector/currency/asset-class exposure, pairwise and
  average correlation, clusters, risk contribution and drift.
- Per major metric: result, method/version, benchmark, lookback, frequency,
  reporting currency, observation count, minimum-data rule, deterministic input,
  independent expected result, tolerance and limitations.
- Edge evidence: short history, missing FX, missing cost basis, cash-only,
  single security, multi-currency, recent listing and missing benchmark.

## 4. Actual deliverables and status

| Deliverable | Artifact | Current status |
|---|---|---|
| CP4 accepted implementation | `../CP4_PM_ACCEPTANCE.md`; `../../src/risk/`; `../../src/risk_service/` | PM accepted 2026-10-03, not HG3 |
| CP4F-16 follow-up | `../TECH_REVIEW.md` §45 | Independently PASS; missing/refused-file controls exercised |
| CP5 contract/registry | `../../methodology/CP5_DIVERSIFICATION_CONVENTIONS.md`; `../../methodology/registry/DIVERSIFICATION_1.0_REGISTRY.json` | `diversification/1.0`; independent findings closed; capital policy remains candidate |
| CP5 independent fixtures | `../../methodology/fixtures/cp5_golden/` | 34 cases; calculator and actual rounding mutant verified |
| CP5 implementation/service | `../../src/diversification/`; `../../src/diversification_service/`; [PM acceptance](../CP5_PM_ACCEPTANCE.md) | `diversification/cp5-0.2`; PM accepted as technical candidate, not HG3 |
| CP3 documentary registry debt | `../../methodology/CP3_REGISTRY_APPENDIX_INVENTORY.md`; `../../src/product_contract/performance_methodology_registry.py` | 24 entries, additive reader and byte-identity checks verified |
| Data decisions | `../HG3_DATA_DECISION_PACKET.md` | Prepared; no source admitted |
| Next-stage dependency inventory | `../NEXT_STAGE_READINESS.md` | Preparation only |

## 5. Runnable examples and outputs

The CP4 golden kit and CP5 independent fixtures are runnable locally; they contain
synthetic portfolios, not the owner's real positions. Root generated the observed
package from repaired `cp5-0.2`: [readable output](HG3_EVIDENCE/synthetic-v002/README.md),
[complete evidence](HG3_EVIDENCE/synthetic-v002/evidence.json). It has 543 actual rows,
29 major metric ids, 34 CP5 cases and 8 edge cases, with 505 independent comparisons
and zero mismatches. 66 supporting-output or independent-expectation gaps are
explicitly listed; no major metric lacks a matching independent example. Root
verified all 252 artifact hashes and 15 implementation hashes. A separate final
read-only audit also resolved all 281 computation references and 834 input pointers
and validated all 242 computation identities/digests. This is synthetic candidate
evidence, not real-source admission or a human decision.

## 6. Tests actually performed

| Run | Actual result | Limit |
|---|---|---|
| Entry default suite, 2026-10-18 | 2312 run; 1992 passed; 320 skipped; 0 failures; 182.937 s | Before CP5 edits; DB not enabled |
| CP4 part-3 guard, main session | 4 passed, 13.711 s | Targeted only |
| CP4 independent review §45 | 4 passed; missing-file and malformed-file probes rejected | No DB/full-suite claim |
| CP5 independent calculator | 33 cases, 199 assertions, 0 differences | Includes specification/state checks; not product integration proof |
| Original DB smoke | 0 tests executed; socket absent, setup error | Environment unavailable, not a product verdict |
| Temporary PG17.11 smoke | 7 passed, 0.100 s | Fresh isolated cluster, not original user cluster |
| CP5 targeted DB service, main session | 4 passed, 1.245 s | Isolated PG17.11/application role; not full regression |
| CP5 DB bundle extension, main session | 5 run, 1 error, 4 passed; 1.137 s | Historical failure, repaired and verified in next row |
| CP5 DB bundle repair, main session | 5 passed, 1.149 s | Explicit missing-benchmark state; independent metrics preserved |
| CP5 fixture v1.1, main session | 34 cases, 226 assertions, 0 differences | H16 discriminates pre-rounded averaging; old cases unchanged |
| CP3 runtime registry/non-regression, main session | 8 passed, 1.377 s | Additive reader; no historic computation changes |
| Independent CP5 review §47 | Historical **HOLD**, 3 MEDIUM and 3 LOW findings | All six closed by §48 after repairs |
| First full default CP5 core regression | 2375 run, 2 failures, 325 skipped; 191.497 s | Accessor triggered old engine-pin inventory; relocated without weakening pins, rerun below |
| Repaired full default regression, main session | **2400 run, 2074 passed, 326 skipped, 0 failures; 191.151 s** | DB opt-ins disabled; precedes two final exporter tests |
| Independent implementation re-review §48 | All six original probes pass; 83 scoped + 6 DB tests pass | One LOW exporter mapping issue, CP5E-1 |
| Independent exporter closure §49 | **PASS**, 11 exporter tests pass; original subset and adversarial guards pass | CP5E-1 closed; core unchanged |
| Final full PostgreSQL regression, main session | **2402 run, 2400 passed, 2 skipped, 0 failures; 198.086 s** | All current tests; PG17.11; two E0 transport preflight opt-ins skipped |

Preserved actual logs and exact commands: [validation record](HG3_EVIDENCE/validation/README.md).
The full PostgreSQL run includes the two exporter tests added after the default run.

## 7. Proof of work and traceability

CP4: 257 independent golden items across four parts; historical pure/DB evidence
is recorded in CP4 acceptance. Today's full regression is separately recorded in
§6; no historical count is relabelled as current.
CP5: Quant authored closed forms and a standalone calculator importing no product
module. The engineer consumes those fixtures; a distinct reviewer checks contracts
and artifacts without the producer's reasoning.

Current CP5 fixture issue `cp5_golden/1.1-part1` SHA-256:
`607d4228c14e9273ac0a16f562a46f858785df8b3a81fdb64bdc6afea930246d`.
Initial 33-case issue is preserved in `cp5_golden_part1_v1_0.json`, SHA-256
`00eca074d6a5ebf1d252486719087165f10d0befbf55170fdd194a48867a6e05`.
Registry SHA-256:
`d149e2077ce316781ea2c436c3aa0b70c23f77f22096a451f4b59917d387a2bf`.
Any later issue/review must record a changed version/hash rather than silently
reusing this evidence.

## 8. Known limitations and incomplete items

- The synthetic export explicitly lists 66 supporting-output or independent-
  expectation gaps: 27 structured checks, 25 fixture rows, 13 additional integrated
  observations and one entry for 12 count-boundary outputs. All major metrics have
  independent matching examples; this does not make every supporting row matched.
- CP5 is accepted as a technical candidate. The full-NAV capital universe still
  needs the owner's decision; dependent service output is withheld without policy.
- Both benchmark and risk-free catalogs have zero admitted entries. Real risk
  availability remains limited by sources and the short existing US history.
- Existing roughly 100-session US data is below CP4 statistical minimums; it can
  demonstrate integration and refusal, not all numeric risk statistics.
- HK/CN prices and calendar registration remain subject to HG2 conditions 3–4.
- PG16 and concurrency beyond existing lock tests remain unverified.
- Production web/AI/proof-packet consumers are later work.

## 9. Deviations from the PRD

None is silently approved here. CP5 is implemented as a candidate pending the
capital-universe product decision below; actual production availability is withheld
where that decision is missing. Any implementation omissions discovered by review
must be added here, not hidden under an aggregate green test result.

## 10. New assumptions and candidate choices

**OD-CP5-01:** full NAV, including cash and receivables, with explicitly labelled
listing-and-cash-bucket concentration and a separate largest-security weight.
Holdings-only versus cash-inclusive denominator was reserved to the owner in CP3
conventions §10 / HG1 round-4 §9 item 5. It is a candidate, not an owner decision.

Current-weight historical covariance risk is distinct from the actual-portfolio
CP4 return history. ETF look-through remains excluded. Clusters require an explicit
method threshold and do not imply a user's risk preference. Targets/baselines must
have explicit provenance; no preferences or warning thresholds are invented.

## 11. Open decisions and risks

- Decide OD-CP5-01 capital universe and labels.
- Decide real total-return benchmark route; attest exact source and data semantics.
- Confirm risk-free sources/calendars, particularly Treasury's publication and
  365/366-day semantics; unresolved HKD/CNY rates stay unavailable.
- Resolve PD-0038 condition 3 before presenting CP4 results as real; register HK/CN
  calendars before using their real data.
- CP5 independent findings are closed (§§48–49); owner acceptance remains separate.
- Preserve internal-only source use; OQ-04b remains an external-display/beta gate.

## 12. Reproduction and inspection

From repository root, use the installed Python 3.12 environment:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-cache --no-sync --frozen --offline python methodology/fixtures/cp5_golden/derivation/cp5_part1_calculator.py
PYTHONDONTWRITEBYTECODE=1 uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_cp4_golden.PartThreeTests
PYTHONDONTWRITEBYTECODE=1 uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .
PYTHONDONTWRITEBYTECODE=1 uv run --no-cache --no-sync --frozen --offline python -m tests.product.hg3_evidence --output /tmp/finweb-hg3-new-inspection
```

Use a new absent output directory; preserve both immutable evidence versions.
Default discovery skips opt-in DB tests. Exact DB environment, startup/shutdown
commands and logs are in [validation instructions](HG3_EVIDENCE/validation/README.md).
DB tests run serially against a disposable `finweb_dev` cluster; temporary schemas
were removed (zero remaining) and the PG17.11 server is now **stopped**. The original
user cluster was unavailable and untouched. Inspect state before any future restart.

## 13. Agent recommendation

**Ready for bounded human inspection.** The implemented candidate, independent
arithmetic, refusal controls and repairs satisfy technical exit. Recommend
reviewing [CP5 acceptance](../CP5_PM_ACCEPTANCE.md) and
[data/policy choices](../HG3_DATA_DECISION_PACKET.md), then explicitly deciding
OD-CP5-01, real-data scope and HG3 (including any binding conditions). The full-NAV
candidate provides a complete denominator with separately labelled cash and
security concentration; adopting it remains the owner's product choice.

An unconditional claim of real multi-market risk readiness is not supported by
empty catalogs and unresolved HG2 conditions. **Clarification, 2026-10-18:**
PD-0039 D1 requires a **decision on the real benchmark route before HG3**, not
completed download or admission before HG3. The earlier wording here overstated
that dependency. A definite route choice can satisfy D1; merely investigating
alternatives cannot. Source admission and each portfolio's explicit primary-
benchmark selection remain separate obligations.

Recommend the four proposed decisions in
[the owner worksheet](../HG3_DATA_DECISION_PACKET.md#6-owner-decision-worksheet-2026-10-18).
If the owner adopts those choices and explicitly approves HG3 with those
conditions, CP6 may implement taxonomy, severity controls and Proof Packets using
labelled synthetic evidence or properly admitted, sufficiently supported real
inputs. Unavailable metrics stay unavailable. Real CN/HK calendar checks, source
attestation, downloads, purchases, external display and later human gates remain
separate. This is a recommendation, not a decision; nothing is preselected below.

## 14. Human decision — recorded 2026-10-19

```text
[ ] APPROVED
[x] APPROVED WITH CONDITIONS
[ ] REVISION REQUIRED
[ ] REJECTED

Human comments (verbatim):
同意上述四项推荐，HG3 有条件通过。记录决定并按所列条件开始 CP6，不恢复夜间自动任务。

Decision date: 2026-10-19 (Asia/Shanghai)
Approver: designated human product owner in this chat
```

Binding choices, conditions and follow-up:
[PD-0041](../../decisions/product/PD-0041-hg3-approved-with-conditions-and-cp6-start.md).
The four recommendations and limits in §13 were adopted; its conditional wording
is retained as the pre-decision recommendation, not a new open gate.
