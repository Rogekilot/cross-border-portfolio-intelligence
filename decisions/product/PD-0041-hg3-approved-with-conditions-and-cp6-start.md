# PD-0041 — HG3 approved with conditions; CP6 authorized

**Status:** accepted
**Date:** 2026-10-19 (Asia/Shanghai)
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Gate:** `reviews/gates/HG3_GATE_REVIEW.md`
**Decision material:** `reviews/HG3_DATA_DECISION_PACKET.md` §6 and the immediately
preceding four-option recommendation in this chat.

## Owner decision, verbatim

> 同意上述四项推荐，HG3 有条件通过。记录决定并按所列条件开始 CP6，不恢复夜间自动任务。

**HG3 = APPROVED_WITH_CONDITIONS.** The four accepted recommendations are:

1. **OD-CP5-01:** use FULL_NAV (securities, cash and receivables) as the explicit
   GLOBAL_PRODUCT capital policy. Keep listing-and-cash-bucket concentration labels
   and the separate largest-security weight. This is not a personal risk preference.
2. **PD-0039 D1:** choose the labelled ETF total-return proxy route for the current
   US scope, SPY/USD first, TOTAL_RETURN_GROSS with dividend reinvestment before
   investor withholding. Disclose ETF fees/tracking differences. Source/history
   admission and each portfolio's dated primary-benchmark choice remain separate.
3. **PD-0038 condition 3:** explicitly proceed without CN/HK real-price sources
   for the present phase; real validation is US-only for now. Cross-border V1 scope
   is unchanged. Condition 4 (checked/registered CN/HK calendars before their real
   data) remains binding.
4. Approve HG3 **with conditions**, allowing CP6 implementation in the scope below.

## Binding conditions accepted with the recommendation

The following are the conditions presented to and incorporated by the owner's
confirmation; they are recorded as requirements, not newly invented permissions.

- CP6 may implement fact / interpretation / preference-dependent classification,
  Observation / Attention / Warning, explicit user-policy precedence and reproducible
  Proof Packets.
- Use clearly labelled synthetic data, or admitted real data meeting each metric's
  requirements. Missing data remains uncomputable; unsupported numbers or warnings
  must not be generated.
- Selecting the SPY data route does not make SPY every portfolio's primary benchmark;
  every portfolio still requires an explicit selection.
- The risk-free candidate directions were already decided. Terms, rate semantics,
  calendars and sufficient history must be checked before actual use.
- Procurement, downloads, source registration, publication and later human gates
  remain separately handled. The cancelled overnight automation is not restored.
- The technical evidence supports the scoped method/reproduction/refusal proof.
  All 66 supporting-output/independent-expectation gaps remain disclosed, not
  reclassified as completed checks. Provide additional proof before a new claim
  relies on an uncovered output.
- The full-NAV policy needs a recorded GLOBAL_PRODUCT identity, scope and runtime
  integration with verification. This decision alone does not claim wiring done.
- Source attestation, calendars, admissible prices/actions and sufficient history
  precede supported real analytics. Unsupported rates remain unavailable; no
  HIBOR/SHIBOR or invented constant substitution is authorized.
- Personal/academic internal scope and later gates remain binding. CP6 implementation
  authorization does not establish product readiness, suitability, or deployment approval.

## Consequences and traceable follow-up

| Item | State / owner / next evidence |
|---|---|
| HG3 | APPROVED_WITH_CONDITIONS; PM updates the gate and live status from this decision |
| OD-CP5-01 | Decided FULL_NAV, GLOBAL_PRODUCT; engineer wires an additive immutable policy reference and verifies its scope/provenance |
| Real benchmark route | D1 decided ETF proxy/SPY USD gross TR for US validation; no catalog source admitted by this PD |
| HG2 condition 3 | Resolved for this phase by explicit US-only real validation decision |
| HG2 condition 4 | Still binding before real CN/HK data; sources/calendars not registered here |
| CP6 | Authorized now after recording this PD; methods, implementation and review remain distinct |
| Supporting evidence gaps | Keep the 66-entry HG3 inventory; inspect evidence coverage before each new downstream claim |
| Automation | Remains deleted; no scheduler is created or restored |
| Git / dependencies / external actions | No commit, push, new production dependency, purchase, source admission, real-data download, publication or deployment authorized here |

The immutable `HG3_EVIDENCE/synthetic-v002/` package is historical evidence and is
not overwritten by this decision or the ensuing policy/CP6 implementation.
