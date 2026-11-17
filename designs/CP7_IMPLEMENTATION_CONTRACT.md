# CP7 implementation contract — approved design reconciled for the first web flow

Date: 2026-10-19. Author: designer. Status: implementation handoff; rendered web
review has not yet occurred. This is an additive reading of already approved
authority, not a new product or gate decision.

## Authority and bounded first increment

Read this contract with `Cross_Border_Portfolio_Intelligence_PRD_v1_1.md` §§7, 21,
27, 30, 32; PD-0012, PD-0013, PD-0017, PD-0030, PD-0035, PD-0041 and PD-0042;
`reviews/gates/HG1_DIRECTION_SELECTION.md`; and the current
`designs/hg1-prototype-v2/` artifact. Higher authority wins over historical wording.

`FEATURE_DESIGN.md` remains the detailed baseline for claim, sufficiency,
freshness and evidence interactions. Its eleven capability destinations are not
eleven current primary navigation tabs. Its Investor/four-depth wording is
superseded by PD-0012. Do not copy these historical statements into production.
The approved prototype remains unchanged and is not production financial code.

PD-0042 authorizes React + TypeScript + Vite and the bounded dependency allowance.
The first increment is a local synthetic guest flow: create a local guest session;
load a demonstration or manually enter supported synthetic holdings and cash;
choose the supported reporting currency; obtain engine valuation/exposure and a
CP6 Observation; open its Proof Packet; request server reproduction. It is a
working increment toward CP7, not CP7 acceptance or a release.

For the initial engineering slice, supported inputs are explicitly synthetic
SYN-A/SYN-B, positive decimal-string quantities, non-negative USD cash and USD
reporting, at the disclosed 2026-01-02 synthetic prices. The form must explain
this boundary before submission and require acknowledgment. It must not invite
real holdings/credentials or imply live market data. Broader data entry is later
CP7 work. CNY reporting remains an approved capability: do not offer a working CNY
conversion until the backend supports adequate FX, and do not relabel USD amounts
as CNY. A USD-only first increment must state that limit clearly: show CNY disabled
with the translated API capability reason `FX_PATH_UNAVAILABLE`, and preserve the
backend's non-USD refusal rather than attempting a browser conversion.

## Current IA and visual continuity

| Primary surface | Approved purpose and contained capabilities | First increment |
|---|---|---|
| Overview / 概览 | Portfolio understanding, valuation, concise exposure/risk and embedded Insights; source-scoped evidence | Engine-backed valuation, exposure summary and CP6 Observation |
| Portfolio / 投资组合 | Holdings, accounts/cash, activity and transactions; manual entry and import/ingestion within this surface | Synthetic manual holdings/cash and creation flow |
| Analytics / 分析 | Performance, risk, exposure and their methodology; same facts as summaries | Available engine-backed exposure and metric detail; unsupported sections explicitly deferred |
| Scenario Lab / 情景实验室 | Isolated hypothetical analysis | Visible unavailable/deferred state; CP8 logic is not implemented by this slice |

AI is contextual/persistent; Insights are embedded into relevant surfaces.
Settings/Policy is outside primary navigation. Evidence & Methodology is reachable
from each claim, with a contextual viewer/side sheet rather than a fifth primary
tab. Do not imply that a deferred navigation destination is implemented, and do
not create hardcoded AI or scenario outcomes to fill the shell.

Retain Direction C's warm, editorial foundation with Direction B's denser
analytical cards: cream background, forest/teal accent, restrained serif headings,
legible body type and tabular numeric alignment. Use the approved prototype's
token/semantic-color behavior as the reference; do not import its simulated
financial computations. Labels and numbers carry meaning independently of color.
Risk level, correlation sign, stale data and genuine gain/loss are separate
semantic vocabularies. Later directional gain/loss views retain the approved
user-selectable color convention, default green gain/red loss.

## One fact set, three explanation depths, two interface languages

Only **Quick / Simple / Professional** (速览 / 简明 / 专业) exist. Investor is removed.
A session default may coexist with per-claim depth controls. Movement is reversible,
and each claim can reach its own Professional detail without forcing other cards.

- Quick: what happened, with the essential scope/reference and any caveat that
  changes the conclusion.
- Simple: the same conclusion, what the measure means and why it matters, in
  plain language. An analogy cannot replace the literal financial definition.
- Professional: the same conclusion plus exact metric/reference identity,
  denominator/scope, method/version, period/frequency/observations where relevant,
  assumptions, source/freshness, limitations and evidence path.

All depths render the same server facts/Proof Packet. Changing depth or language
does not calculate a new financial fact, upgrade severity or remove a limitation.
Professional is not a forecast or trading recommendation. Evidence remains
reachable at every depth. Professional must add inspectable detail rather than
repeat the Simple text under a different heading.

English and 简体中文 cover the whole implemented flow: navigation, forms, validation,
states, reasons, explanations, Evidence, reproduction results and errors. Set the
document language accordingly. Canonical security identifiers, market IDs, source
IDs, digests, metric IDs and currency codes are stable identifiers, not translated
facts. Interface language and reporting currency are independent controls. Review
representative full screens in both languages, including the evidence viewer.

## Financial value, data state and context rendering

The Python engine owns every financial value and decision. The browser renders
server-issued values/decimal strings, units, scope and evidence; no JS portfolio
sum, weight, FX conversion, threshold comparison or severity inference is allowed.
Rounding is display formatting only and cannot decide a claim or comparison.

| Engine state/context | Required presentation |
|---|---|
| AVAILABLE | Display the issued value, unit/currency, scope/reference and relevant freshness |
| AVAILABLE with routine stale input | Same numeric sufficiency treatment, plus separate visible price/FX freshness; do not silently downgrade or call live |
| LIMITED | Display the issued value with an adjacent, persistent, wrapping limitation and human-readable reason; not tooltip-only |
| INSUFFICIENT_DATA | Explicit textual state and reason; no zero, blank or number-shaped dash standing in for an unavailable financial value |
| Unknown metadata/freshness | Explicit unknown/not assessed; never infer a country, sector, price freshness or FX freshness from symbol/currency |
| Local synthetic development | Persistent synthetic/development context in header and relevant evidence; synthetic timestamp is not proof of current/live data |
| ACTUAL versus SCENARIO | Distinct context carried through summary, detail and evidence; hypothetical results never overwrite actual holdings |

Readable reason labels must cover SOURCE_CONFLICT (“Sources disagree” /
“数据源存在冲突”) and MISSING_PRICE_HISTORY (“No price history” / “缺少价格历史”),
as well as the backend vocabulary encountered by this slice. Preserve the canonical
reason code in evidence. These two reasons require a non-AVAILABLE state. Unknown
codes receive an honest fallback plus their canonical identifier; do not suppress
the reason or invent a new meaning.

PD-0035 partial-value rule: if any holding cannot be valued, the true portfolio
total remains insufficient. A separately issued partial metric may be labelled
**“Value of priced holdings (partial)” / “已定价持仓价值（部分）”**, accompanied by
**“Excludes {n} unpriced holdings” / “不含 {n} 项未定价持仓”**. It must never be
called portfolio total/NAV or summed into the suppressed true total. Display only
the server's partial metric and excluded count. If this branch is not implemented
in the first supported fixture, it remains a required later CP7 branch.

PD-0041 FULL_NAV/GLOBAL_PRODUCT remains the approved exposure/concentration basis,
including eligible cash/receivables; separate largest-security weight stays
distinct. Show issued policy/scope and included/excluded coverage. Do not describe
“largest position” as “largest security” or silently switch to holdings-only.
No personal limit exists unless explicitly supplied/confirmed by the user.
Benchmark route approval does not select SPY for an individual portfolio.

Freshness stays separate by security-price market and FX axis. Show source as-of
time/status alongside relevant values and in evidence; a computation timestamp or
page reload is not a market-data timestamp. Historical-window freshness and the
present capital-snapshot freshness are different evidence. A CP3 snapshot witness
does not certify historical covariance legs. UNKNOWN or absent freshness remains
unknown; ordinary stale input is not automatically an insufficient statistic.

## Evidence, reproduction and interaction

Every material metric/Insight has a labelled Evidence/依据 action next to the
claim. It opens the specific metric methodology or Insight Proof Packet, not a
generic unscoped registry home. Long canonical identities/digests wrap or have
deliberate accessible overflow; they cannot hide the limitation text.

The packet view exposes the PRD §21 fields supplied by the engine: insight ID/type,
severity, claim, judgment class, metrics used, portfolio snapshot ID, scenario ID
when applicable, comparison basis, benchmark, period/frequency/observations,
threshold/limit when used, source timestamps, methodology versions, freshness,
availability/confidence state, limitations and permitted explorations. Show absent
or inapplicable fields honestly, not manufactured metadata. Scope and exact source
identity must survive transport. Keep the machine-readable packet inspectable.

“Reproduce” invokes the server on the identified request/evidence and compares
against the expected digest. Show pending, actual REPRODUCED/refusal/error status
and details; never equate an HTTP success with reproduced or render success before
the response. Reproduce does not approve a human gate or certify real-data quality.

Form controls have persistent labels, decimal-input help, understandable errors and
keyboard activation. Announce asynchronous results/errors without moving focus
unexpectedly. The evidence side sheet/dialog has an accessible name, logical
keyboard order, close/Escape behavior and focus return to its opener; modal focus
is contained if modal. Focus is visible. Tables have semantic headers, aligned
numeric columns, wrapping state/reason cells and a discoverable horizontal-scroll
affordance on narrow screens. State/reason information cannot be conveyed by color
alone or clipped out of the viewport.

## Later CP7 obligations and later gates

The first guest/local flow does not waive normal authentication for saved
portfolios, user isolation, durable save/reload/history, full CSV import or export.
CSV remains Core V1: map columns, preview interpretation, validate identities,
resolve ambiguous tickers, detect missing currency/date/quantity, allow correction,
reject/quarantine invalid rows and issue an import report. Do not guess securities.
Account creation is required to save/import a full portfolio or preserve history.

Later performance views use PD-0035's exact daily eight-line attribution and
engine-issued apportioned display values. The first waterfall bar is **“Local
price effect” / “本地价格影响”**, with a separate **“Price–FX interaction” /
“价格与汇率交互影响”** line. Do not reuse the superseded constant-FX label. Period
attribution and since-acquisition decomposition answer different questions and
must be identified separately. FIFO gain labels retain the broker-lot difference
caveat; these are analytics, not tax guidance.

HG1's approved IA/usability/progressive explanation is retained. HG4 still requires
real-data usability validation (PD-0013); HG5 and later gates are separate. Temporary
US-only real validation, CN/HK data/calendar conditions, source admission terms and
the disclosed historical HG3 evidence inventory remain. Synthetic local success
does not close these requirements. No nighttime automation is restored.

## Review boundary

This handoff reconciles written authority only. It does not claim that the React
app has rendered correctly, that browser interaction passed, or that CP7 is done.
After an actual local review origin is provided, design review must exercise the
implemented flow, both languages, three depths, evidence/reproduction and narrow
layout/keyboard behavior, and record observed failures separately from untested
branches. The historical prototype's accepted residual debt is not a pass for a
new production implementation.
