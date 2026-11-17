/*
 * data.js — HG1 CP0 prototype mock data.
 *
 * EVERYTHING IN THIS FILE IS SYNTHETIC. No live data, no APIs, no brokerage
 * connection, no real computation. Every number here is hand-typed as if a
 * deterministic engine had already returned it (P1) — this file plays the
 * role of "the engine's output," never the AI, and never a live source.
 *
 * Built from designs/FEATURE_DESIGN.md (D1-D5), specs/FEATURE_PRD.md, and
 * decisions/product/PD-0004..PD-0008. Where the contract has a known,
 * unresolved gap, this file does not quietly pick an answer — see
 * KNOWN_GAPS below, and the inline notes near CALC_ERROR_GAP.
 */

const SYNTHETIC_BANNER =
  "SYNTHETIC DATA — NON-PRODUCTION PROTOTYPE — HG1 UNDECIDED — NOT AN APPROVAL";

const SYNTHETIC_NOTE =
  "All figures on this screen are hand-authored mock data for HG1 inspection only. " +
  "Nothing here was computed, fetched, or verified.";

// The five reason codes that PD-0006's second amendment requires to imply a
// non-AVAILABLE sufficiency state. STALE_DATA is the one exception.
const NON_AVAILABLE_REASON_CODES = [
  "UNSUPPORTED_ASSET",
  "MISSING_BENCHMARK",
  "MISSING_COST_BASIS",
  "MISSING_FX_HISTORY",
  "CALCULATION_ERROR",
];

// source PRD §33 — fifteen required methodology fields, metric name included.
const METHODOLOGY_FIELDS = [
  "metric_name",
  "definition",
  "formula",
  "annualization_convention",
  "data_inputs",
  "minimum_observations",
  "frequency",
  "lookback",
  "benchmark_dependency",
  "risk_free_rate_dependency",
  "missing_data_handling",
  "fx_treatment",
  "corporate_action_treatment",
  "known_limitations",
  "implementation_version",
];

// source PRD §21 — Proof Packet minimum conceptual schema.
const PROOF_PACKET_FIELDS = [
  "insight_id",
  "insight_type",
  "severity",
  "claim",
  "judgment_class",
  "metrics_used",
  "portfolio_snapshot_id",
  "scenario_id",
  "comparison_basis",
  "benchmark",
  "period",
  "frequency",
  "observations",
  "thresholds_limits",
  "source_data_timestamps",
  "methodology_versions",
  "data_freshness",
  "confidence_availability_state",
  "limitations",
  "permitted_suggested_explorations",
];

// ---------------------------------------------------------------------------
// Accounts / holdings
// ---------------------------------------------------------------------------

const ACCOUNTS = [
  { id: "usbroker", name: "US Broker", market: "US", currency: "USD" },
  { id: "futu_hk", name: "Futu HK", market: "HK", currency: "HKD" },
  { id: "cn_broker", name: "China Brokerage", market: "CN", currency: "CNY" },
];

// Seven line items on Holdings, deliberately: this is the portfolio "you hold
// 7 positions" (PD-0008) refers to on the AI Analyst screen.
const HOLDINGS = [
  {
    id: "aapl",
    account: "usbroker",
    kind: "security",
    ticker: "AAPL",
    name: "Apple Inc.",
    market: "US",
    currency: "USD",
    quantity: 120,
    price: 228.5,
    marketValueNative: 27420.0,
    marketValueReporting: 27420.0,
    freshness: { state: "LIVE", axis: "US equity price" },
    gainLoss: {
      state: "AVAILABLE",
      value: 9420.0,
      costBasis: 18000.0,
    },
  },
  {
    id: "msft",
    account: "usbroker",
    kind: "security",
    ticker: "MSFT",
    name: "Microsoft Corp.",
    market: "US",
    currency: "USD",
    quantity: 60,
    price: 415.2,
    marketValueNative: 24912.0,
    marketValueReporting: 24912.0,
    freshness: { state: "LIVE", axis: "US equity price" },
    gainLoss: {
      state: "AVAILABLE",
      value: 8412.0,
      costBasis: 16500.0,
    },
  },
  {
    id: "baba",
    account: "futu_hk",
    kind: "security",
    ticker: "9988.HK",
    name: "Alibaba Group (HK listing)",
    market: "HK",
    currency: "HKD",
    quantity: 800,
    price: 88.4,
    marketValueNative: 70720.0,
    marketValueReporting: 9043.0,
    // AVAILABLE + STALE_DATA: HK market closed while US is open. Renders
    // IDENTICALLY to plain AVAILABLE at the value's own unit — see D3.2.
    freshness: { state: "END_OF_DAY", axis: "HK equity price" },
    gainLoss: {
      state: "AVAILABLE",
      reasonCode: "STALE_DATA",
      value: 10720.0,
      costBasis: 60000.0, // native currency (HKD)
    },
  },
  {
    id: "tencent",
    account: "futu_hk",
    kind: "security",
    ticker: "0700.HK",
    name: "Tencent Holdings",
    market: "HK",
    currency: "HKD",
    quantity: 300,
    price: 392.0,
    marketValueNative: 117600.0,
    marketValueReporting: 15038.0,
    freshness: { state: "END_OF_DAY", axis: "HK equity price" },
    // LIMITED: cost basis is a user-entered estimate, not verified. This is
    // a real, qualified number — not suppressed — per PD-0006/PD-0007.
    gainLoss: {
      state: "LIMITED",
      value: 27600.0, // native currency (HKD), computed off the estimate
      costBasis: 90000.0,
      qualifier:
        "Cost basis is a user-entered estimate (“~HK$300/share, from memory”), not confirmed against broker records.",
    },
  },
  {
    id: "moutai",
    account: "cn_broker",
    kind: "security",
    ticker: "600519.SS",
    name: "Kweichow Moutai",
    market: "CN",
    currency: "CNY",
    quantity: 50,
    price: 1680.0,
    marketValueNative: 84000.0,
    marketValueReporting: 11700.0,
    freshness: { state: "END_OF_DAY", axis: "Mainland China equity price" },
    // INSUFFICIENT_DATA: cost basis was never captured on manual import.
    // No numeric glyph of any kind — see D3.2 row for INSUFFICIENT_DATA.
    gainLoss: {
      state: "INSUFFICIENT_DATA",
      reasonCode: "MISSING_COST_BASIS",
      explanation:
        "Cost basis was never captured when this position was manually imported (§9.5 taxonomy field left blank at entry).",
    },
  },
  {
    id: "cash_usd",
    account: "usbroker",
    kind: "cash",
    ticker: "CASH",
    name: "Cash (USD)",
    market: "US",
    currency: "USD",
    quantity: null,
    price: null,
    marketValueNative: 12500.0,
    marketValueReporting: 12500.0,
    freshness: { state: "LIVE", axis: "US cash balance" },
    gainLoss: null, // cash carries no gain/loss claim — a fact, not a D3 state.
  },
  {
    id: "cash_cny",
    account: "cn_broker",
    kind: "cash",
    ticker: "CASH",
    name: "Cash (CNY)",
    market: "CN",
    currency: "CNY",
    quantity: null,
    price: null,
    marketValueNative: 25000.0,
    marketValueReporting: 3480.0,
    freshness: { state: "END_OF_DAY", axis: "CNY cash / FX fixing" },
    gainLoss: null,
  },
];

const POSITION_COUNT = HOLDINGS.length; // 7 — the PD-0008 "claim" number
const MARKET_COUNT = 3; // US, HK, CN — also a claim, not a selector

// ---------------------------------------------------------------------------
// Metrics (shared claim objects — D2.2). The SAME object is referenced by id
// from more than one surface (e.g. "risk_snapshot_beta" appears on both
// Overview and Risk & Analytics) to make D4.1's "affordance attaches to the
// claim, not the surface" argument concrete: clicking Evidence from either
// surface opens the identical Methodology entry.
// ---------------------------------------------------------------------------

const METRICS = {
  total_portfolio_value: {
    id: "total_portfolio_value",
    label: "Total Portfolio Value",
    unit: "USD",
    state: "AVAILABLE",
    reasonCode: "STALE_DATA",
    value: 104093.0,
    referencePoint: "Reporting currency (USD), current snapshot",
    freshness: {
      leastFreshAxis: "Mainland China / Hong Kong equity price",
      leastFreshState: "END_OF_DAY",
      axes: [
        { axis: "US equity price", state: "LIVE" },
        { axis: "HK equity price", state: "END_OF_DAY" },
        { axis: "Mainland China equity price", state: "END_OF_DAY" },
        { axis: "USD/HKD FX", state: "DELAYED", delay: "15 min" },
        { axis: "USD/CNY FX", state: "END_OF_DAY" },
      ],
    },
    methodologyId: "meth_portfolio_value",
    d4Origin: "overview-item-1",
  },
  portfolio_gain_loss: {
    id: "portfolio_gain_loss",
    label: "Portfolio Gain/Loss (30 days)",
    unit: "USD",
    state: "AVAILABLE",
    value: 3214.55,
    referencePoint: "vs. MSCI ACWI +1.4% over same 30-day period",
    methodologyId: "meth_portfolio_gain_loss",
    d4Origin: "overview-item-2",
  },
  risk_snapshot_beta: {
    id: "risk_snapshot_beta",
    label: "Beta (vs MSCI ACWI)",
    unit: "x",
    state: "LIMITED",
    value: 1.3,
    qualifier: "Thin sample: 18 of 24 required weekly observations.",
    methodologyId: "meth_beta",
    d4Origin: "risk-analytics-core",
  },
  volatility: {
    id: "volatility",
    label: "Historical Volatility (1Y, annualized)",
    unit: "%",
    state: "AVAILABLE",
    value: 14.2,
    referencePoint: "In line with this portfolio's own 3-year average (13.8%)",
    methodologyId: "meth_volatility",
  },
  sharpe: {
    id: "sharpe",
    label: "Sharpe Ratio (1Y)",
    unit: "",
    state: "AVAILABLE",
    value: 0.85,
    referencePoint: "vs. MSCI ACWI Sharpe 0.71 over same window",
    methodologyId: "meth_sharpe",
  },
  sortino: {
    id: "sortino",
    label: "Sortino Ratio (1Y)",
    unit: "",
    state: "AVAILABLE",
    value: 1.05,
    referencePoint: "vs. MSCI ACWI Sortino 0.88 over same window",
    methodologyId: "meth_sortino",
  },
  max_drawdown: {
    id: "max_drawdown",
    label: "Max Drawdown (1Y)",
    unit: "%",
    state: "AVAILABLE",
    value: -18.4,
    referencePoint: "vs. this portfolio's own 3-year worst drawdown (-24.1%)",
    methodologyId: "meth_drawdown",
  },
  effective_n: {
    id: "effective_n",
    label: "Effective N (diversification)",
    unit: "",
    state: "LIMITED",
    value: 4.2,
    qualifier:
      "Small number of positions; the effective-N estimate carries wide uncertainty at this portfolio size.",
    methodologyId: "meth_effective_n",
  },
  hhi: {
    id: "hhi",
    label: "Herfindahl-Hirschman Index (concentration)",
    unit: "",
    state: "AVAILABLE",
    value: 0.21,
    referencePoint: "vs. this portfolio's own 3-year average HHI (0.19)",
    methodologyId: "meth_hhi",
  },
  aapl_weight: {
    id: "aapl_weight",
    label: "Largest single position (AAPL)",
    unit: "%",
    state: "AVAILABLE",
    value: 26.3,
    referencePoint: "vs. your Portfolio Policy limit of 25% (Portfolio Settings)",
    methodologyId: "meth_concentration",
  },
};

// A CALCULATION_ERROR metric exists ONLY inside the Known Gaps panel (below),
// never rendered on a live surface as if a resolution had been chosen. See
// CALC_ERROR_GAP and the "final pass" report text for why.

// ---------------------------------------------------------------------------
// Worked examples — D2.3 depth ladder (Quick -> Simple -> Investor ->
// Professional). Conclusion and caveat are kept as two separate visible
// fields at every level so a viewer can see the caveat survive compression.
// ---------------------------------------------------------------------------

const WORKED_EXAMPLES = [
  {
    id: "beta",
    title: "Beta (vs MSCI ACWI) — worked example 1",
    metricId: "risk_snapshot_beta",
    levels: {
      quick: {
        conclusion:
          "Your portfolio has historically moved more than the market.",
        caveat: "Based on a short history — treat with caution.",
      },
      simple: {
        conclusion:
          "Moves in the same direction as the benchmark and historically amplifies its moves by about 1.3×, over the period measured.",
        caveat:
          "Only 18 of the 24 weekly observations this measure normally requires are available yet, so this reading is provisional.",
      },
      investor: {
        conclusion:
          "Beta = 1.30 vs MSCI ACWI, weekly returns, 18-week window.",
        caveat:
          "Below the 24-observation minimum this metric normally requires — classified LIMITED, not AVAILABLE, until more history accumulates.",
      },
      professional: {
        conclusion:
          "OLS regression of weekly portfolio returns on MSCI ACWI weekly returns; beta (slope) = 1.30, R² = 0.61, n = 18 weekly observations, window opened 2026-04-20 (new brokerage link).",
        caveat:
          "n=18 is below the registry-defined minimum of 24 weekly observations for this metric family; classified LIMITED per PD-0006/§32. The sample-size caveat changes the conclusion's reliability and must not be dropped at any depth (P3).",
      },
    },
    mustNotSay:
      '"30% riskier" — P3’s own named violation. Beta is a linear-regression sensitivity, not a percentage risk increase.',
  },
  {
    id: "correlation",
    title: "Correlation — AAPL vs Tencent (0700.HK) — worked example 2",
    metricId: null,
    levels: {
      quick: {
        conclusion:
          "These two holdings have historically moved in the same direction, strongly, over this period.",
        caveat:
          "Based on the last 12 months only — not a guarantee this holds going forward.",
      },
      simple: {
        conclusion:
          "Strong but not perfect co-movement, historically; the diversification benefit between these two holdings is reduced but not eliminated.",
        caveat:
          "Historical relationship only — correlations can and do shift over time (P6).",
      },
      investor: {
        conclusion:
          "Correlation coefficient = 0.80, daily returns, trailing 12 months.",
        caveat:
          "12-month daily window; short windows can overstate a relationship's stability.",
      },
      professional: {
        conclusion:
          "Pearson correlation of daily log returns, trailing 252 trading days, n = 252, no missing-data adjustment required.",
        caveat:
          "Short window relative to a full market cycle; correlation is not stationary and this estimate should not be extrapolated beyond the measured period (P6).",
      },
    },
    mustNotSay:
      '"Always moves together" — P3’s own named violation; 0.80 is not 1.00. Also corrected here (§design_review NF-2): must not say "moved together most of the time" either — correlation measures co-movement strength, not frequency.',
  },
  {
    id: "alpha",
    title: "Jensen's Alpha (vs MSCI ACWI) — worked example 3",
    metricId: null,
    levels: {
      quick: {
        conclusion:
          "Over this period, returns were below what the benchmark relationship would predict.",
        caveat:
          "A historical description of one period, not a judgment of manager skill.",
      },
      simple: {
        conclusion:
          "After adjusting for how much market risk was taken (beta), actual returns fell short of the model-implied return, in this specific historical window.",
        caveat:
          "This is historical and model-based — not a prediction, and not a statement about anyone's competence.",
      },
      investor: {
        conclusion:
          "Alpha = −0.62% (annualized), beta = 1.30, benchmark = MSCI ACWI, 36-month window.",
        caveat:
          "Historical/model-based measure only. Depends on the beta and benchmark chosen — a different benchmark could show a different alpha.",
      },
      professional: {
        conclusion:
          "Jensen's alpha regression: benchmark = MSCI ACWI, risk-free rate = 3-month US T-bill, beta = 1.30, alpha = −0.62% (annualized), R² = 0.71, monthly frequency, n = 36 observations.",
        caveat:
          "Historical/model-based, not a universal measure of skill (§17.2). Omitting R² or sample size here would make this number unauditable (P9); both are always shown at this depth.",
      },
    },
    mustNotSay:
      '"Bad portfolio" — P3’s and §17.2’s own named violation. Alpha is not a moral or competence judgment.',
  },
];

// ---------------------------------------------------------------------------
// Exposure
// ---------------------------------------------------------------------------

const EXPOSURE = {
  byListingMarket: [
    { label: "US", pct: 45 },
    { label: "Hong Kong", pct: 30 },
    { label: "Mainland China", pct: 12 },
    { label: "Cash", pct: 13 },
  ],
  byEconomicGeography: [
    { label: "United States", pct: 40 },
    { label: "China (incl. HK-listed / ADR exposure)", pct: 47 },
    { label: "Cash", pct: 13 },
  ],
  bySector: [
    { label: "Technology", pct: 58 },
    { label: "Consumer Staples", pct: 15 },
    { label: "Consumer Discretionary", pct: 14 },
    { label: "Cash", pct: 13 },
  ],
  byCurrency: [
    { label: "USD", pct: 61 },
    { label: "HKD", pct: 23 },
    { label: "CNY", pct: 16 },
  ],
};

// ---------------------------------------------------------------------------
// Insights (§20)
// ---------------------------------------------------------------------------

const INSIGHTS = [
  {
    id: "ins_concentration_policy",
    severity: "Warning",
    judgmentClass: "Preference-dependent judgment",
    driftType: null,
    claim:
      "Your single-position concentration in AAPL (26.3%) exceeds your Portfolio Policy limit of 25%.",
    referencePoint: "Your own Portfolio Policy (Portfolio Settings), not a generic threshold — §20.3 precedence.",
    metricsUsed: ["aapl_weight"],
    proofPacketId: "pp_concentration_policy",
  },
  {
    id: "ins_geo_drift",
    severity: "Attention",
    judgmentClass: "Interpretation",
    driftType: "drift (§19)",
    claim:
      "Your China economic-geography exposure increased from 32% to 47% over the last quarter.",
    referencePoint: "This portfolio's own prior-quarter snapshot (drift comparison, not a benchmark).",
    metricsUsed: ["exposure_economic_geography"],
    proofPacketId: "pp_geo_drift",
  },
  {
    id: "ins_vol_observation",
    severity: "Observation",
    judgmentClass: "Fact",
    driftType: null,
    claim:
      "Your portfolio's historical volatility (14.2%) is in line with its own 1-year average.",
    referencePoint: "This portfolio's own historical volatility series.",
    metricsUsed: ["volatility"],
    proofPacketId: "pp_vol_observation",
  },
  {
    id: "ins_missing_cost_basis",
    severity: "Attention",
    judgmentClass: "Fact",
    driftType: null,
    claim:
      "Kweichow Moutai's (600519.SS) cost basis is missing — unrealized gain/loss cannot be shown until it is entered.",
    referencePoint: "§9.5 minimum transaction taxonomy — Transactions surface.",
    metricsUsed: [],
    proofPacketId: "pp_missing_cost_basis",
  },
];

// ---------------------------------------------------------------------------
// AI Analyst (P1 boundary; PD-0008 selector-vs-claim)
// ---------------------------------------------------------------------------

const AI_TOOL_CALLS = {
  risk_snapshot_beta: {
    call: "engine.get_metric('portfolio_beta', benchmark='MSCI_ACWI', as_of='2026-08-29')",
    result:
      "MetricResult(value=1.30, sufficiency_state='LIMITED', reason_code=None, qualifier='18/24 weekly obs')",
  },
  aapl_weight: {
    call: "engine.get_metric('position_weight', ticker='AAPL', as_of='2026-08-29')",
    result: "MetricResult(value=26.3, sufficiency_state='AVAILABLE', reason_code=None)",
  },
  policy_limit: {
    call: "engine.get_policy_field('max_single_position_weight')",
    result: "PolicyValue(value=25.0, set_by_user=True)",
  },
  position_count: {
    call: "engine.count_positions(as_of='2026-08-29')",
    result: "CountResult(value=7, sufficiency_state='AVAILABLE')  # PD-0008: a claim, must be slotted",
  },
  market_count: {
    call: "engine.count_markets(as_of='2026-08-29')",
    result: "CountResult(value=3, sufficiency_state='AVAILABLE')  # PD-0008: a claim, must be slotted",
  },
};

const AI_NARRATIVE = {
  quick:
    "Your portfolio's risk is moderately above the market, driven mainly by your Hong Kong and mainland China holdings.",
  simple:
    "Your beta of {{chip:risk_snapshot_beta}} means your portfolio has historically moved somewhat more than the market benchmark, though that reading is still provisional (see the qualifier on the chip). Your largest single-name exposure, {{chip:aapl_weight}}, is above the {{chip:policy_limit}} limit you set in your Portfolio Policy.",
  investor:
    "Looking at your top 3 holdings by weight, technology names dominate. Beta is {{chip:risk_snapshot_beta}} vs MSCI ACWI (still LIMITED — only 18 of 24 required weekly observations exist). AAPL is {{chip:aapl_weight}} of the portfolio, above your {{chip:policy_limit}} policy limit. You hold {{chip:position_count}} positions across {{chip:market_count}} markets.",
  professional:
    "Methodology note: beta is an OLS regression slope of weekly portfolio returns on MSCI ACWI weekly returns (n=18, below the 24-observation registry minimum — classified LIMITED per PD-0006). Current value: {{chip:risk_snapshot_beta}}. Concentration: {{chip:aapl_weight}} vs a {{chip:policy_limit}} user-set limit (§20.3 precedence over any generic threshold). Portfolio composition: {{chip:position_count}} positions, {{chip:market_count}} markets — both are counts derived from the ledger and delivered as slots per PD-0008, not free-typed.",
};

const AI_SELECTOR_NOTE =
  '"top 3 holdings" above is a SELECTOR (PD-0008): it orders/slices what is being discussed and asserts nothing that could be false, so the AI may free-type it. "You hold 7 positions across 3 markets" is a CLAIM: it states a fact about your portfolio that could be wrong, so it must arrive as a resolved slot (citation chip), never free-typed.';

// ---------------------------------------------------------------------------
// Scenario Lab (P8; §24)
// ---------------------------------------------------------------------------

const SCENARIO = {
  id: "SCN-2026-014",
  description: 'What if I move 20% of my AAPL position into a hypothetical Mainland China broad-market ETF?',
  comparison: [
    {
      metric: "Allocation — US",
      actual: { state: "AVAILABLE", value: "45%" },
      scenario: { state: "AVAILABLE", value: "36%" },
    },
    {
      metric: "Beta (vs MSCI ACWI)",
      actual: { state: "LIMITED", value: "1.30", qualifier: "18/24 weekly obs" },
      scenario: { state: "LIMITED", value: "1.42", qualifier: "18/24 weekly obs (unchanged — same underlying history)" },
    },
    {
      metric: "Largest position concentration",
      actual: { state: "AVAILABLE", value: "26.3% (AAPL)" },
      scenario: { state: "AVAILABLE", value: "20.9% (AAPL)" },
    },
    {
      metric: "Hypothetical CN Broad-Market ETF position",
      actual: { state: null, value: null }, // does not exist in the actual portfolio at all
      scenario: {
        state: "INSUFFICIENT_DATA",
        reasonCode: "UNSUPPORTED_ASSET",
        explanation:
          "No price history exists for this hypothetical instrument in the ledger — a scenario does not exempt a metric from insufficient-data suppression.",
      },
    },
  ],
  proofPacketId: "pp_scenario_beta",
};

// ---------------------------------------------------------------------------
// Portfolio Policy (§25, P7)
// ---------------------------------------------------------------------------

const POLICY = {
  reportingCurrency: "USD",
  accounts: ACCOUNTS,
  fields: [
    { label: "Primary benchmark", value: "MSCI ACWI", set: true },
    { label: "Max single-position weight", value: "25%", set: true },
    { label: "Max sector concentration", value: null, set: false },
    { label: "Risk preference", value: null, set: false },
    { label: "Investment horizon", value: "10+ years", set: true },
  ],
};

// ---------------------------------------------------------------------------
// Methodology & Evidence (§33) — registry ships EMPTY (AC-17). Structure only.
// ---------------------------------------------------------------------------

const METHODOLOGY_REGISTRY_NAMES = [
  "meth_portfolio_value",
  "meth_portfolio_gain_loss",
  "meth_beta",
  "meth_volatility",
  "meth_sharpe",
  "meth_sortino",
  "meth_drawdown",
  "meth_effective_n",
  "meth_hhi",
  "meth_concentration",
  "meth_correlation",
  "meth_fx_conversion",
];

// ---------------------------------------------------------------------------
// Proof Packets — synthetic examples, not real registry content.
// ---------------------------------------------------------------------------

function makeProofPacket(overrides) {
  const base = {
    insight_id: null,
    insight_type: "Insight",
    severity: null,
    claim: null,
    judgment_class: null,
    metrics_used: [],
    portfolio_snapshot_id: "SNAP-2026-08-29",
    scenario_id: null,
    comparison_basis: null,
    benchmark: "MSCI ACWI",
    period: "trailing 12 months",
    frequency: "weekly",
    observations: "n/a",
    thresholds_limits: "n/a",
    source_data_timestamps: "2026-08-29T20:00:00Z (US), 2026-08-29T08:00:00Z (HK/CN, prior close)",
    methodology_versions: "not yet published — registry ships empty in this increment (AC-17)",
    data_freshness: "see D5 per-axis freshness indicator on originating surface",
    confidence_availability_state: null,
    limitations: "Synthetic prototype data — illustrative only.",
    permitted_suggested_explorations: "View methodology (placeholder, empty registry) · View originating surface",
  };
  return Object.assign({}, base, overrides);
}

const PROOF_PACKETS = {
  pp_concentration_policy: makeProofPacket({
    insight_id: "ins_concentration_policy",
    insight_type: "Concentration warning",
    severity: "Warning",
    claim: "AAPL concentration (26.3%) exceeds your Portfolio Policy limit of 25%.",
    judgment_class: "Preference-dependent judgment",
    metrics_used: ["aapl_weight"],
    comparison_basis: "User-defined Portfolio Policy field (not a generic threshold) — §20.3",
    confidence_availability_state: "AVAILABLE",
  }),
  pp_geo_drift: makeProofPacket({
    insight_id: "ins_geo_drift",
    insight_type: "Drift detection (§19)",
    severity: "Attention",
    claim: "China economic-geography exposure rose from 32% to 47% quarter-over-quarter.",
    judgment_class: "Interpretation",
    comparison_basis: "This portfolio's own snapshot, one quarter prior, vs current snapshot.",
    confidence_availability_state: "AVAILABLE",
  }),
  pp_vol_observation: makeProofPacket({
    insight_id: "ins_vol_observation",
    insight_type: "Observation",
    severity: "Observation",
    claim: "1-year historical volatility (14.2%) is in line with the portfolio's own 3-year average.",
    judgment_class: "Fact",
    metrics_used: ["volatility"],
    comparison_basis: "This portfolio's own 3-year volatility history.",
    confidence_availability_state: "AVAILABLE",
  }),
  pp_missing_cost_basis: makeProofPacket({
    insight_id: "ins_missing_cost_basis",
    insight_type: "Data-sufficiency notice",
    severity: "Attention",
    claim: "600519.SS unrealized gain/loss is INSUFFICIENT_DATA — cost basis missing.",
    judgment_class: "Fact",
    confidence_availability_state: "INSUFFICIENT_DATA",
    limitations: "No numeric value exists to show — by design (P5). Synthetic prototype data.",
  }),
  pp_scenario_beta: makeProofPacket({
    insight_id: null,
    insight_type: "Scenario comparison metric",
    severity: null,
    claim: "Scenario beta (vs MSCI ACWI) under SCN-2026-014 is 1.42, LIMITED.",
    judgment_class: "Fact",
    metrics_used: ["risk_snapshot_beta"],
    scenario_id: "SCN-2026-014",
    comparison_basis: "Same methodology and registry entry as the ACTUAL beta — §24.3, no separate scenario methodology.",
    confidence_availability_state: "LIMITED",
  }),
};

// ---------------------------------------------------------------------------
// Known gaps — visible, not silently resolved.
// ---------------------------------------------------------------------------

const KNOWN_GAPS = [
  {
    id: "freshness-slot",
    title: "Freshness has no slot in the shared claim object (D2.2)",
    body:
      "designs/FEATURE_DESIGN.md §D2.2 defines a claim as exactly four fields: conclusion, " +
      "reference point, caveat set, methodology pointer. D5 requires a freshness indicator " +
      "next to the value it qualifies, but neither D2 nor D5 says whether freshness is a " +
      "fifth field, a sibling object, or something else. This prototype renders freshness " +
      "anyway (you can see it on Overview, Holdings, and the AVAILABLE+STALE_DATA examples) " +
      "because the presentation contract is decided — but where that data structurally " +
      "lives is not. CP0_RECONCILIATION.md §3.1: the technical carrier exists (the " +
      "Computation Manifest pins per-market and FX references separately); nothing declares " +
      "it a display-time dependency yet. This is going to HG1 unresolved.",
  },
  {
    id: "caveat-verification",
    title: "Caveat-compression meaning-preservation has no verification checkpoint",
    body:
      "The depth toggle below (and on Risk & Analytics / Exposure) shows the caveat SLOT " +
      "surviving compression at every level — that structural guarantee is real. What is " +
      "not verified anywhere in this increment is whether the compressed wording still " +
      "means what the full caveat means. §D2.2 correctly routes that judgment to " +
      "quant_analyst, but no workflow gate currently requires that review before copy ships. " +
      "This prototype's worked-example wording is illustrative content, not certified copy.",
  },
  {
    id: "calc-error-coherence",
    title: "CALCULATION_ERROR + value-bearing LIMITED: unsettled (NF-5 / N-17)",
    body:
      "PD-0006's second amendment requires CALCULATION_ERROR to imply a non-AVAILABLE state. " +
      "PD-0007's total equivalence requires LIMITED to carry a value. Put together, a " +
      "calculation-errored metric classified LIMITED is REQUIRED to show a number — which " +
      "two independent reviewers flagged as possibly incoherent (does it make sense to show " +
      "a number next to “calculation error”?) without either having authority to settle " +
      "it. quant_analyst has not been engaged in this increment. Below are the two " +
      "mechanically-legal renderings under today's contract — shown side by side, neither " +
      "asserted as correct. This prototype does not pick one, on any live surface.",
    renderings: [
      {
        label: "Rendering A — LIMITED (has a value, as PD-0007 requires for LIMITED)",
        state: "LIMITED",
        value: "0.34",
        reasonCode: "CALCULATION_ERROR",
        qualifier: "Tracking-error regression did not converge; value shown is the last stable estimate.",
      },
      {
        label: "Rendering B — INSUFFICIENT_DATA (no value)",
        state: "INSUFFICIENT_DATA",
        reasonCode: "CALCULATION_ERROR",
        explanation: "Tracking-error regression did not converge; no number is shown.",
      },
    ],
  },
];
