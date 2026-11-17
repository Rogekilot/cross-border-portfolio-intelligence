# Product Requirements Document (PRD)
## Cross-Border Portfolio Intelligence Platform

**Status:** Draft v1.1  
**Date:** 2026-09-02  
**Primary launch-user assumption:** Mainland China-based sophisticated self-directed investors  
**Product surface:** Responsive web application  
**Commercial model:** Freemium SaaS  
**V1 market coverage:** US, Mainland China, and Hong Kong listed common stocks and ETFs, plus multi-currency cash  
**Document purpose:** Provide a complete product, analytics, data, AI, and engineering specification that a fresh engineering harness/agent can use without relying on the originating conversation.

---

# 1. Executive Summary

Build a responsive web-based portfolio intelligence platform for investors who hold securities across countries, currencies, brokers, and markets.

The product must do more than aggregate holdings. Its core mission is to convert a cross-border portfolio into a consistent, trustworthy analytical model that explains:

1. how much the investor owns;
2. how the portfolio has performed;
3. where performance came from;
4. where the portfolio is exposed;
5. what risks are measurable;
6. how those risks compare with an explicit benchmark, the investor’s own policy, or the portfolio’s history;
7. how hypothetical portfolio changes would alter those characteristics; and
8. what complex professional statistics mean in clear language.

The product is targeted first at sophisticated self-directed investors: people who understand investments, may hold securities in multiple markets, and want substantially better analytics and explanations than a brokerage dashboard provides, but who do not need an institutional portfolio-management system.

V1 is intentionally **not** a brokerage, robo-adviser, tax adviser, order-management system, or automated trading system. It is an analytics, interpretation, and scenario-analysis product.

---

# 2. Product Vision

## 2.1 Vision statement

Create the most understandable and trustworthy cross-border portfolio intelligence layer for individual investors.

## 2.2 Core product thesis

Portfolio tracking is a commodity. The differentiating product is **cross-border portfolio intelligence**:

- normalize holdings across markets and currencies;
- separate security return from FX effects;
- understand issuer, listing, country, sector, and currency exposure;
- calculate professional portfolio analytics using a deterministic engine;
- detect evidence-backed portfolio conditions;
- translate complex analytics into progressively simpler explanations;
- let users interrogate their portfolio conversationally;
- let users model hypothetical portfolio changes without executing trades.

## 2.3 Primary V1 value proposition

A sophisticated self-directed investor can enter or import a portfolio spanning US, Mainland China, and Hong Kong securities and, within minutes, understand its performance, exposures, major risks, benchmark-relative behavior, and the evidence behind those conclusions better than they could from their brokerage interface alone.

---

# 3. Non-Negotiable Product Principles

These are architectural constraints, not optional UX preferences.

## P1. Quantitative engine owns financial facts; AI owns explanation and interaction

The LLM must not be the source of portfolio calculations. Portfolio value, returns, volatility, beta, alpha, correlation, risk contribution, FX attribution, drawdown, concentration, and other quantitative outputs must come from deterministic analytics services.

## P2. Professional data must be translatable without destroying rigor

Every important professional metric should support a progression from quick conclusion to plain-English explanation to investor-level detail to professional methodology.

## P3. Simplification must preserve uncertainty and caveats

The system must not transform a precise statement into a misleading simpler one. Examples:

- beta 1.30 must not become “30% riskier”;
- correlation 0.80 must not become “always moves together”;
- negative Jensen’s alpha must not become “bad portfolio”;
- historical volatility must not be described as a future forecast.

## P4. Every judgment requires a reference point

The product must not call a metric “high,” “low,” “poor,” “concentrated,” or “underperforming” without a reference such as:

- selected benchmark;
- user-defined portfolio policy;
- portfolio’s own historical state;
- documented analytical threshold.

## P5. No metric without sufficient data

If the data are insufficient, the correct output is N/A / insufficient evidence, not an extrapolated or invented number.

## P6. Historical statistics are not forecasts

Unless a dedicated forecasting model exists, language must remain historical/descriptive.

## P7. AI may not invent personalized constraints

User-defined limits take precedence. When no user constraint exists, the product must use comparative or educational language rather than pretending a universal threshold is personally correct.

## P8. Hypothetical and actual portfolio states are strictly separated

Scenario analysis never silently changes the user’s actual ledger or portfolio.

## P9. Every important insight must be auditable

Numerical claims and generated interpretations must be traceable to the underlying portfolio snapshot, data inputs, methodology, benchmark, timestamps, and limitations.

## P10. Data freshness is always visible

The platform must never imply that all cross-market securities are simultaneously real time. Latest-available prices and live FX may have different freshness states.

## P11. Vendor independence

Core application logic and analytics must consume normalized internal data contracts, not be tightly coupled to a single market-data vendor.

## P12. Deterministic point-in-time portfolio reconstruction

Given ledger events, prices, FX history, and corporate actions, the system must be able to reconstruct the portfolio at a historical point in time.

---

# 4. Target User and Launch Assumptions

## 4.1 Primary user

Sophisticated self-directed investor.

Typical characteristics:

- holds or considers holding securities across countries;
- may use multiple brokerages;
- understands concepts such as diversification, beta, benchmark, and volatility at least conceptually;
- wants professional-grade analytics without institutional software complexity;
- values both numerical detail and concise interpretation;
- may want to explore international diversification.

## 4.2 Secondary future users

Not V1 primary:

- beginner retail investors;
- finance students/enthusiasts;
- wealth managers/advisers;
- family offices;
- institutional portfolio managers.

## 4.3 Launch jurisdiction assumption

Mainland China-based investors are the formal V1 user/commercial assumption.

This does **not** limit supported holdings to China. V1 holdings cover US, Mainland China, and Hong Kong listed stocks and ETFs.

Legal, market-data, hosting, privacy, and financial-services review for Mainland China is a separate pre-commercial-launch gate. The product must not assume that technically available data or functionality is automatically legally redistributable or commercially deployable.

---

# 5. V1 Scope

## 5.1 Supported asset types

V1 supports exactly:

- exchange-listed common stocks;
- exchange-listed ETFs;
- cash balances;
- multiple currencies.

## 5.2 Supported listing markets

- United States;
- Mainland China;
- Hong Kong.

## 5.3 Explicitly out of V1

- individual bonds;
- mutual funds;
- options;
- futures;
- crypto;
- private assets;
- real estate;
- structured products;
- live broker integrations;
- order execution;
- automatic trading;
- personalized buy/sell recommendations;
- tax-loss harvesting;
- tax-return preparation;
- jurisdiction-specific tax advice;
- advanced ETF look-through;
- complex corporate reorganizations beyond basic supported events;
- institutional portfolio-management workflows.

## 5.4 V1.5 candidates

- ETF look-through;
- underlying-security overlap;
- look-through sector/country exposure;
- broker/account synchronization;
- expanded international market coverage;
- more sophisticated factor/risk decomposition.

---

# 6. Product Information Architecture

The responsive web application should expose the following primary surfaces:

1. **Overview**
2. **Holdings**
3. **Performance**
4. **Exposure**
5. **Risk & Analytics**
6. **Insights**
7. **Scenario Lab**
8. **AI Analyst**
9. **Transactions**
10. **Portfolio Settings / Policy**
11. **Methodology & Evidence**

The UI should use progressive disclosure rather than separate “retail” and “professional” products.

Depth model:

**Quick → Simple → Investor → Professional / Methodology**

All layers must use the same underlying facts.

---

# 7. Onboarding and Activation

## 7.1 Guest/demo experience

Users should be able to experience the analytical value before account creation.

Guest flow:

1. Open product.
2. Choose “Try portfolio analysis.”
3. Add several positions manually or load a demonstration portfolio.
4. Select reporting currency.
5. View limited dashboard and Portfolio Brief.
6. Require account creation to save/import a full portfolio or preserve history.

## 7.2 Portfolio architecture

The backend must support multiple portfolios from day one.

Conceptual hierarchy:

**User → Portfolios → Accounts → Ledger Events → Derived Positions**

V1 UI may emphasize one primary portfolio to reduce complexity.

## 7.3 Manual account containers

Users may create logical account containers before live broker APIs exist, e.g.:

- US Broker;
- Futu HK;
- China Brokerage;
- Cash Account.

Account containers are organizational and accounting objects, not live integrations.

---

# 8. Portfolio and Currency Model

## 8.1 Single reporting currency

Every portfolio has exactly one user-selected reporting/base currency.

The dashboard presents aggregate values in this reporting currency.

## 8.2 Native security and transaction currency

Every instrument retains its trading/native currency.

Security currency should normally be inferred from resolved instrument metadata.

Transactions retain their original transaction currency.

Users may supply/override currency when imported data are ambiguous or when transaction currency differs from trading currency.

## 8.3 FX rules

Current portfolio snapshot:
- use latest available FX rate;
- expose FX timestamp/freshness.

Historical analytics:
- use historical FX corresponding to the valuation/cash-flow date;
- never retroactively apply today’s FX rate to historical portfolio values.

## 8.4 FX attribution

Where sufficient transaction/history data exist, total return should be decomposable into:

- local security-price effect;
- FX effect;
- income/dividends;
- fees;
- known taxes/withholding.

---

# 9. Portfolio Ledger and Position Engine

## 9.1 Canonical source

When transaction history exists, transactions/ledger events are canonical and positions are derived state.

Do not maintain an independent mutable “current shares” value that can silently diverge from the ledger.

## 9.2 Snapshot-only portfolios

Users may create a portfolio with current holdings only.

Snapshot mode must allow useful current-state analytics while clearly disabling history-dependent outputs that cannot be justified.

Synthetic opening-balance records may be used internally to represent snapshot holdings.

## 9.3 Missing cost basis

Missing cost basis is allowed.

Supported without cost basis:
- current market value;
- allocation;
- current exposure;
- security historical risk analytics;
- portfolio hypothetical risk analytics where methodology permits.

Unavailable/limited without cost basis or transaction history:
- investor-specific unrealized gain;
- realized gain;
- exact money-weighted return;
- exact historical investor performance.

Never fabricate cost basis.

## 9.4 Cash

Cash is a first-class asset.

Each cash balance includes a currency and participates in:
- portfolio value;
- allocation;
- portfolio weights;
- reporting-currency conversion;
- performance denominator where appropriate;
- currency exposure.

Cash itself has no market-price volatility, but FX movements may affect reporting-currency value.

## 9.5 Minimum transaction taxonomy

Support at least:

- BUY
- SELL
- DIVIDEND
- INTEREST
- FEE
- TAX
- DEPOSIT
- WITHDRAWAL
- TRANSFER_IN
- TRANSFER_OUT
- SPLIT
- CORPORATE_ACTION / SYMBOL_CHANGE as required

## 9.6 Cash-flow treatment

Deposits and withdrawals are external cash flows, not investment gains/losses.

Transfers between accounts inside the same portfolio are internal movements and must not be counted as portfolio return.

## 9.7 Point-in-time reconstruction

The system must reconstruct historical holdings using:
- ledger events;
- corporate actions;
- instrument mappings;
- historical prices;
- historical FX.

This is required for rolling risk, historical allocations, drift, and performance attribution.

---

# 10. Security and Instrument Identity Model

## 10.1 Canonical identity

Use FIGI + MIC as canonical identity primitives where available.

Ticker is a user-facing lookup/search attribute, not the database primary key.

## 10.2 Required instrument metadata

At minimum:

- instrument ID;
- FIGI where available;
- ticker;
- MIC;
- exchange;
- trading currency;
- security type;
- issuer identifier;
- issuer name;
- listing geography;
- issuer domicile where available;
- status/active flag.

## 10.3 Listing vs issuer

Model listing-level instruments separately from issuer-level economic aggregation.

Example:
- BABA NYSE listing;
- 9988 HKEX listing;
- both related to Alibaba issuer.

This enables:
- correct trading currency and calendar;
- correct listing-level pricing;
- issuer-level concentration analysis.

## 10.4 Economic geography

Do not infer economic exposure solely from listing venue.

The model must allow separate fields for:
- listing country;
- issuer domicile;
- revenue/economic geography;
- trading currency;
- underlying economic exposure.

Full revenue-based exposure may be incomplete in V1, but the schema must support it.

---

# 11. Market Data Architecture

## 11.1 Vendor-independent normalized layer

Application and analytics code must not depend directly on a vendor-specific payload format.

Use normalized contracts such as:

### Instrument
identity and metadata.

### SecurityPrice
- instrument_id;
- timestamp;
- price;
- currency;
- source;
- freshness;
- adjustment status.

### FXRate
- currency pair;
- timestamp;
- rate;
- source;
- freshness.

### CorporateAction
- instrument;
- event type;
- effective date;
- ratio/amount;
- currency;
- source.

### BenchmarkSeries
- benchmark ID;
- provider;
- values/returns;
- currency;
- source;
- licensing metadata.

## 11.2 Price freshness

V1 principle:

**Latest available security prices + live FX where available.**

Every market datum must expose:
- source time;
- freshness state;
- delayed/EOD/live status where known.

Do not display a universal “live portfolio” label unless every required component legitimately satisfies that condition.

## 11.3 Data lineage

Analytics must know whether a series is:
- raw;
- split-adjusted;
- dividend-adjusted;
- total-return adjusted.

Never blindly mix inconsistent series.

## 11.4 Benchmark licensing separation

Benchmark analytics logic must be independent from benchmark data licensing.

Benchmark records must include provider/source/licensing metadata.

The system should support broad comparison benchmarks such as:
- US indices;
- Mainland China indices;
- Hong Kong indices;
- world indices;
- ex-US indices;
- ex-China indices.

Availability in commercial production depends on lawful data access/licensing.

---

# 12. Corporate Actions

## 12.1 First-class treatment

Corporate actions are ledger-affecting events, not chart decoration.

## 12.2 Core V1 automatic support

- cash dividends;
- stock splits;
- ticker/symbol changes.

## 12.3 Later support

- spin-offs;
- mergers;
- tender offers;
- rights issues;
- special distributions;
- other complex reorganizations.

## 12.4 Correctness requirement

Corporate actions must preserve economic continuity and update holdings/cost basis where the required underlying information exists.

---

# 13. Benchmark Model

## 13.1 User-selected primary benchmark

The system may recommend appropriate benchmarks, but the user explicitly selects the primary benchmark.

Only one benchmark is primary at a time for benchmark-dependent metrics.

Additional benchmarks may be displayed as comparative references.

## 13.2 Benchmark-dependent metrics

The selected benchmark must be explicit for:
- beta;
- Jensen’s alpha;
- active return;
- tracking error;
- information ratio;
- benchmark-relative volatility/performance comparisons.

## 13.3 Benchmark methodology metadata

Each benchmark-dependent calculation must expose:
- benchmark;
- calculation window;
- return frequency;
- reporting currency treatment;
- observation count;
- calculation timestamp;
- methodology version.

---

# 14. Historical Window and Frequency

Default professional analytical setting:

- lookback: 3 years;
- frequency: weekly;
- currency: portfolio reporting currency.

Advanced controls may allow:
- 1Y;
- 3Y;
- 5Y;
- maximum available;
- daily;
- weekly;
- monthly.

Weekly should be the default for cross-market covariance/correlation/beta to reduce non-synchronous market-close noise.

Every metric must state the actual window/frequency used.

---

# 15. Performance Analytics

## 15.1 Core V1 metrics

- portfolio market value;
- absolute gain/loss;
- percentage return;
- time-weighted return (TWR);
- money-weighted return / IRR where transaction data permit;
- annualized return;
- realized gain/loss where cost basis exists;
- unrealized gain/loss where cost basis exists;
- dividend/income return;
- FX contribution;
- security-price contribution;
- fees;
- known tax/withholding impact.

## 15.2 Attribution

Where sufficient data exist, total return should be decomposable into:

**Security movement + FX movement + income – fees – known taxes**

Attribution must reconcile to the reported return within documented numerical tolerance.

## 15.3 Tax boundary

V1 may:
- record tax/withholding cash flows;
- include known tax cash flows in performance;
- display tax-related cash flows.

V1 must not:
- give jurisdiction-specific tax advice;
- perform tax-return preparation;
- provide tax-loss harvesting recommendations;
- claim tax optimization.

---

# 16. Risk Analytics

## 16.1 Core V1

- annualized volatility;
- beta;
- maximum drawdown;
- downside deviation;
- Sharpe ratio;
- Sortino ratio.

## 16.2 Advanced V1

- tracking error;
- information ratio;
- active return;
- Value at Risk (VaR);
- Expected Shortfall;
- marginal contribution to risk;
- total contribution to portfolio risk;
- rolling volatility;
- rolling beta;
- rolling correlation;
- rolling Sharpe.

## 16.3 Methodology requirement

Every professional metric must have a registry entry containing:
- exact definition/formula;
- data requirements;
- minimum sample requirement;
- window/frequency;
- annualization convention;
- benchmark requirement if any;
- risk-free-rate requirement if any;
- FX treatment;
- missing-data policy;
- known limitations.

The quantitative team/agent must not invent a threshold or sample minimum ad hoc inside UI code.

---

# 17. Expected Return and Alpha Policy

## 17.1 Expected return

V1 must not present a single forward-looking “expected return” estimate as fact.

Allowed:
- historical annualized return;
- benchmark historical return;
- CAPM-implied required return where methodology is explicit;
- user-defined assumptions in Scenario Lab;
- clearly labeled model outputs if a future forecasting module is later built.

## 17.2 Jensen’s alpha

V1 supports historical Jensen’s alpha only.

Always label it as historical/model-based, not as a universal measure of manager skill.

Expose:
- benchmark;
- risk-free-rate assumption;
- beta;
- alpha;
- R²;
- sample window;
- frequency;
- observation count.

Negative alpha must not automatically generate “bad portfolio” or “sell” language.

---

# 18. Diversification and Exposure Engine

## 18.1 Core V1 concentration analytics

- largest position weight;
- top-5 concentration;
- HHI concentration;
- effective number of positions;
- sector exposure;
- country exposure;
- currency exposure;
- asset-class exposure;
- pairwise correlation;
- average portfolio correlation.

## 18.2 Correlation UX

Do not force users to interpret a giant matrix first.

Provide:
1. quick conclusion;
2. cluster interpretation;
3. important high-correlation pairs;
4. optional full matrix/heatmap;
5. methodology view.

## 18.3 Risk contribution

Advanced V1 should show the difference between capital weight and estimated risk contribution.

Example insight:
“A 10% holding contributes 21% of modeled portfolio volatility.”

The calculation must come from the deterministic analytics engine.

## 18.4 ETF treatment

V1:
- treat ETF as a security for portfolio risk/performance.

V1.5:
- underlying-holdings look-through;
- overlap;
- look-through country/sector/security exposure.

---

# 19. Portfolio Drift

Portfolio drift detection is Core V1.

Track material changes in:
- concentration;
- beta;
- volatility;
- benchmark deviation;
- currency exposure;
- country exposure;
- drawdown state;
- sector exposure.

The system may surface:
“Portfolio beta increased from X to Y over the selected comparison period.”

It must not claim causality unless supported by an analytical decomposition.

---

# 20. Insight and Warning Engine

## 20.1 Severity model

Three levels:

### Observation
A notable measurable condition.

### Attention
A meaningful deviation from benchmark, history, or user objective.

### Warning
A clear breach of a user-defined constraint or unusually severe condition supported by sufficient evidence.

Warnings should be relatively rare.

## 20.2 Judgment taxonomy

Internally distinguish:

### Fact
Example: “Technology represents 44.8% of portfolio value.”

### Interpretation
Example: “Technology is the portfolio’s largest sector concentration.”

### Preference-dependent judgment
Example: “Technology exceeds your stated 35% sector cap.”

## 20.3 User policy precedence

When a user has defined a portfolio policy, those limits take precedence over generic heuristics.

Without a policy, use benchmark/historical comparisons and softer educational language.

## 20.4 Underperformance

Benchmark underperformance is an Observation by default, not automatically a Warning.

## 20.5 Diversification warnings

Never infer diversification solely from number of holdings.

Use multidimensional evidence across:
- security;
- issuer;
- sector;
- country;
- currency;
- correlation;
- later ETF overlap.

---

# 21. Proof Packet Architecture

Every important generated insight must have a machine-readable Proof Packet.

Minimum conceptual schema:

- insight_id;
- insight_type;
- severity;
- claim;
- judgment_class;
- metrics_used;
- portfolio_snapshot_id;
- scenario_id if applicable;
- comparison_basis;
- benchmark;
- period;
- frequency;
- observations;
- thresholds/limits if used;
- source data timestamps;
- methodology versions;
- data freshness;
- confidence/availability state;
- limitations;
- permitted suggested explorations.

The LLM consumes the Proof Packet; it must not silently invent evidence or upgrade severity.

---

# 22. AI Analyst

## 22.1 Mission

Transform structured portfolio analytics into:
- clear explanations;
- quick conclusions;
- evidence-backed answers;
- educational context;
- scenario exploration.

## 22.2 Controlled tool access

The LLM should interact through controlled application/analytics tools such as:

- get_portfolio_summary();
- get_performance_attribution();
- get_exposures();
- calculate_risk();
- compare_benchmark();
- get_insights();
- get_metric_methodology();
- run_scenario().

Do not provide unrestricted reasoning over raw production financial databases as the primary architecture.

## 22.3 Numerical claims

Every material numerical AI claim must be grounded in deterministic engine output or stored ledger/data facts.

## 22.4 Insufficient evidence

When evidence is insufficient, AI must explicitly say it cannot reach the conclusion.

It may explain:
- why;
- what data are missing;
- what metric remains available instead.

## 22.5 Advice boundary

For V1, the AI must not issue individualized buy/sell orders or present a hypothetical portfolio as a personalized recommendation.

Example allowed response:
“I can model how reducing technology exposure would change historical concentration and volatility.”

Then route to Scenario Lab.

## 22.6 Causal language

AI must not claim “X caused Y” from simple co-movement.

Causal/driver language requires supporting attribution, risk-contribution, or other justified decomposition.

## 22.7 Explanation depth

Support at least:

### Quick
One-sentence conclusion.

### Simple
Plain-English meaning and implication.

### Investor
Metric values, comparisons, and context.

### Professional
Methodology, regression/statistical details, assumptions, limitations.

These modes use the same facts.

## 22.8 Audit record

Important AI interpretations should be reproducible using an answer record containing:
- user question;
- portfolio snapshot;
- scenario if any;
- analytics outputs used;
- Proof Packets;
- benchmark;
- timestamps;
- methodology versions;
- limitations;
- generated answer.

---

# 23. AI Portfolio Brief

The Portfolio Brief is a flagship V1 feature.

Purpose:
Give the user a fast, evidence-backed interpretation of the portfolio.

A Brief should answer, when evidence exists:

1. How has the portfolio performed?
2. What drove performance?
3. What are the largest exposures?
4. What are the most important risk/concentration changes?
5. How does it compare with the selected benchmark?
6. What role did FX play?
7. What deserves the user’s attention?
8. What scenario could the user explore next?

Every sentence containing a financial claim must map to structured evidence.

The Brief must never invent missing historical performance for a snapshot-only portfolio.

---

# 24. Scenario Lab

Scenario Lab is Core V1.

## 24.1 Purpose

Allow the user to modify a hypothetical copy of the portfolio and compare analytical consequences without executing trades.

## 24.2 Supported interactions

Examples:
- reduce position weight;
- remove a position;
- add a hypothetical stock/ETF;
- increase cash;
- shift exposure toward another region/ETF;
- enforce a concentration constraint;
- compare alternative weights.

## 24.3 Comparison outputs

Current vs Scenario:
- allocation;
- sector/country/currency exposure;
- concentration;
- historical volatility;
- beta;
- drawdown;
- correlations;
- risk contribution;
- benchmark-relative metrics where valid.

## 24.4 AI role

The AI may create scenarios in response to user instructions.

It must label them as hypothetical analysis, not a recommended trade.

No Scenario Lab action changes the actual portfolio unless the user separately performs an explicit portfolio edit/import action.

---

# 25. Portfolio Policy

Portfolio Policy is optional and progressively configured.

Potential fields:
- primary benchmark;
- investment horizon;
- risk preference;
- acceptable beta range;
- maximum single-position weight;
- maximum sector concentration;
- maximum country concentration;
- maximum currency concentration;
- liquidity preferences;
- other user-defined limits.

The platform remains usable without a completed policy.

If a policy field is absent, the system must not secretly invent the corresponding personal constraint.

---

# 26. Main Dashboard Requirements

The Overview page should answer these questions in this order:

1. **How much do I have?**
2. **How am I doing?**
3. **Where am I exposed?**
4. **What should I pay attention to?**

Recommended hierarchy:

- total portfolio value in reporting currency;
- gain/loss;
- performance chart;
- period selector;
- allocation/exposure summaries;
- risk snapshot;
- top Insights;
- Portfolio Brief;
- Ask Your Portfolio entry point;
- visible data freshness.

Do not place dense covariance matrices or regression diagnostics on the main landing page.

---

# 27. Manual Entry and CSV Import

## 27.1 Manual positions

Minimum manual snapshot entry:
- security search/identifier;
- quantity;
- account;
- optional average cost;
- optional acquisition metadata;
- currency override only if necessary.

## 27.2 Manual transactions

Allow transaction-level entry when the user wants complete performance history.

## 27.3 CSV import

CSV import is Core V1.

The importer should:
- map columns;
- preview interpretation;
- validate security identifiers;
- identify ambiguous tickers;
- detect missing currency/date/quantity fields;
- allow user correction;
- reject or quarantine invalid rows;
- produce an import report.

Do not silently “guess” ambiguous securities.

## 27.4 Export

Allow portfolio/transaction data export so users are not locked into the product.

---

# 28. Freemium SaaS Model

Exact pricing is not in scope for this PRD.

Architect the product to allow tiering.

## Free candidate

- one portfolio;
- manual positions;
- basic dashboard;
- limited analytics;
- limited AI usage;
- limited historical depth.

## Pro candidate

- multiple portfolios;
- transaction history;
- CSV import/export;
- advanced analytics;
- Scenario Lab;
- full AI Analyst;
- rolling analytics;
- expanded benchmark comparison.

## Future Professional candidate

- client portfolios;
- reporting;
- collaboration/team features;
- API;
- institutional-grade controls.

Do not allow billing/tiering concerns to corrupt the deterministic analytics model.

---

# 29. Performance and Scale Requirements

## 29.1 UX performance targets

When cached and under normal conditions:

- portfolio dashboard target: <2 seconds;
- simple metric interaction: near-instant;
- ordinary scenario recalculation target: <3 seconds;
- AI response: stream as available;
- heavy computations may be asynchronous only when necessary.

These are product targets, not early-prototype hard SLAs.

## 29.2 Portfolio size

Practical V1 engineering target:
- typical: 5–100 holdings;
- supported target: up to 500 holdings per portfolio;
- ledger: tens of thousands of events.

Do not optimize V1 for institutional portfolios containing tens of thousands of securities.

---

# 30. Security and Privacy Priority

Security is **not a top product-development priority before core website functionality and analytical value are validated**.

However, low priority does not mean intentionally unsafe implementation.

## 30.1 Baseline during prototype/MVP

Maintain:
- secrets/API keys on server side;
- normal authentication boundaries for saved portfolios;
- user data isolation;
- encrypted transport through normal production web infrastructure;
- no deliberate plaintext credential storage;
- no brokerage credentials because broker integration is out of V1.

## 30.2 Deferred hardening

Before commercial production at meaningful scale, perform:
- formal security review;
- stronger audit logging;
- deletion/export controls;
- encryption-at-rest review;
- privacy policy/data-retention review;
- abuse/rate-limit review;
- infrastructure and dependency hardening;
- jurisdiction-specific data/compliance review.

Functional product validation should occur before extensive security engineering investment.

---

# 31. Regulatory and Product-Boundary Requirements

V1 product posture:

- analytics;
- education;
- evidence-backed interpretation;
- hypothetical scenario analysis.

Not V1:
- individualized security buy/sell instructions;
- automatic rebalancing;
- execution;
- custody;
- brokerage;
- tax advice.

Before commercial launch for Mainland China users, obtain specialist review of:
- investment-advice boundaries;
- market-data redistribution;
- privacy/data rules;
- hosting/cross-border data issues;
- required disclosures.

The engineering architecture should keep advisory/execution capabilities separable so future regulatory expansion does not contaminate the analytics core.

---

# 32. Data Sufficiency and Availability States

Every metric should return a state, not only a number.

Suggested conceptual states:

- AVAILABLE;
- LIMITED;
- INSUFFICIENT_DATA;
- STALE_DATA;
- UNSUPPORTED_ASSET;
- MISSING_BENCHMARK;
- MISSING_COST_BASIS;
- MISSING_FX_HISTORY;
- CALCULATION_ERROR.

UI and AI must honor this state.

Example:
“3Y Beta — N/A. Insufficient weekly observations.”

Do not render zero, blank, or fabricated fallback values that can be mistaken for real analytics.

---

# 33. Methodology Registry

Create a centralized methodology registry rather than embedding definitions inside components.

For every metric, store/version:

- metric name;
- human definition;
- formula;
- annualization convention;
- data inputs;
- minimum observations;
- frequency;
- lookback;
- benchmark dependency;
- risk-free rate dependency;
- missing-data handling;
- FX treatment;
- corporate-action treatment;
- known limitations;
- implementation version.

AI Methodology explanations and “See evidence” views should consume this registry.

---

# 34. Calculation Reproducibility

Given:

- portfolio snapshot/ledger version;
- market-data version/timestamps;
- FX series;
- corporate actions;
- benchmark series;
- methodology version;

the system must be able to reproduce an important calculation sufficiently for audit/debugging.

This requirement applies especially to:
- returns;
- beta;
- alpha;
- attribution;
- concentration warnings;
- risk contribution;
- AI-supported insights.

---

# 35. Functional Requirements Summary

## FR-001 Portfolio creation
Create/save a portfolio with one reporting currency.

## FR-002 Guest analysis
Allow limited pre-signup portfolio analysis.

## FR-003 Multi-portfolio backend
Support multiple portfolios per user architecturally.

## FR-004 Account containers
Allow manual brokerage/account containers.

## FR-005 Manual holdings
Enter current holdings.

## FR-006 Manual ledger
Enter supported transaction types.

## FR-007 CSV import
Import holdings/transactions with validation and mapping.

## FR-008 Instrument resolution
Resolve securities using canonical identity and exchange context.

## FR-009 Multi-currency
Preserve native currencies and convert to one reporting currency.

## FR-010 Historical FX
Use date-correct historical FX for historical analytics.

## FR-011 Latest market data
Show latest available market prices with freshness.

## FR-012 Corporate actions
Support core V1 dividends/splits/symbol changes.

## FR-013 Position engine
Derive positions from canonical ledger events.

## FR-014 Point-in-time reconstruction
Rebuild historical portfolio state.

## FR-015 Performance analytics
Provide V1 performance and attribution metrics.

## FR-016 Risk analytics
Provide Core and Advanced V1 risk metrics.

## FR-017 Benchmark selection
Recommend but require explicit primary benchmark selection.

## FR-018 Benchmark comparison
Calculate benchmark-dependent analytics from selected benchmark.

## FR-019 Diversification
Provide multidimensional concentration/exposure analysis.

## FR-020 Correlation interpretation
Provide clusters/simple interpretation + optional matrix.

## FR-021 Risk contribution
Provide portfolio risk contribution analysis.

## FR-022 Drift
Detect meaningful portfolio metric/exposure changes.

## FR-023 Insights
Generate evidence-backed Observation/Attention/Warning objects.

## FR-024 Proof Packets
Attach machine-readable evidence to important insights.

## FR-025 Portfolio Brief
Generate evidence-backed concise portfolio interpretation.

## FR-026 AI Analyst
Answer portfolio questions using controlled deterministic tools.

## FR-027 Explanation levels
Support Quick/Simple/Investor/Professional explanations.

## FR-028 Insufficient-data handling
Refuse unsupported numerical conclusions.

## FR-029 Scenario Lab
Create and compare hypothetical portfolio states.

## FR-030 Actual/scenario separation
Never mutate actual state from scenario analysis.

## FR-031 Portfolio Policy
Allow optional user-defined portfolio constraints/objectives.

## FR-032 Evidence UX
Allow user to inspect evidence/methodology behind claims.

## FR-033 Data freshness UX
Expose timestamps/freshness throughout.

## FR-034 CSV/data export
Allow user export.

---

# 36. Non-Functional Requirements

## NFR-001 Determinism
Core analytics must be deterministic for identical inputs and methodology versions.

## NFR-002 Traceability
Material AI numerical claims must be traceable to stored facts/analytics.

## NFR-003 Vendor portability
Market-data provider substitution must not require rewriting core analytics.

## NFR-004 Explainability
Every professional metric must have human-readable methodology.

## NFR-005 Graceful degradation
Incomplete data must reduce available analytics without preventing useful portfolio access.

## NFR-006 Responsiveness
Normal portfolio analysis should feel interactive.

## NFR-007 Scale
Support up to approximately 500 holdings per portfolio in V1.

## NFR-008 Cross-market correctness
Trading currency, market identity, calendars, FX, and data freshness must not be conflated.

## NFR-009 Historical consistency
Historical analytics must use historical portfolio state and FX.

## NFR-010 Auditability
Important calculations/insights must be reproducible from versioned inputs.

---

# 37. Suggested System Architecture

This is directional, not a mandatory technology stack.

```text
Responsive Web Client
        |
        v
Application/API Layer
        |
        +---------------- Portfolio Service
        |                    |
        |                    +-- Accounts
        |                    +-- Ledger
        |                    +-- Position Engine
        |                    +-- Snapshots
        |
        +---------------- Instrument Service
        |                    |
        |                    +-- FIGI/MIC mapping
        |                    +-- issuer/listing metadata
        |
        +---------------- Market Data Layer
        |                    |
        |                    +-- Vendor adapters
        |                    +-- Prices
        |                    +-- FX
        |                    +-- Corporate actions
        |                    +-- Benchmarks
        |
        +---------------- Analytics Engine
        |                    |
        |                    +-- Performance
        |                    +-- Risk
        |                    +-- Attribution
        |                    +-- Diversification
        |                    +-- Drift
        |                    +-- Scenario calculations
        |
        +---------------- Insight Engine
        |                    |
        |                    +-- Rules
        |                    +-- Severity
        |                    +-- Proof Packets
        |
        +---------------- AI Orchestration
                             |
                             +-- Controlled analytics tools
                             +-- Portfolio Brief
                             +-- Q&A
                             +-- Explanation levels
```

The AI orchestration layer should be downstream of the deterministic analytical truth layer.

---

# 38. Engineering Checkpoints / Harness Gates

Engineering agents must not treat “feature coded” or “tests passed” as sufficient completion. This project uses **two layers of governance**:

1. **Technical Checkpoints (CP0–CP11):** machine-verifiable engineering milestones.
2. **Mandatory Human Approval Gates (HG1–HG7):** blocking review stages where the harness must stop and obtain explicit human authorization before downstream work may continue.

The Human Approval Gates override autonomous progression. A technically successful checkpoint does not authorize the harness to pass a Human Gate.

## 38.1 Human Gate State Machine — Mandatory Harness Rule

When a Human Approval Gate is reached, the project must enter:

`AWAITING_HUMAN_REVIEW`

While in this state:

- no downstream implementation work may begin;
- no agent may interpret passing tests as approval;
- no agent may interpret internal reviewer approval as human approval;
- no agent may interpret silence, elapsed time, or lack of objections as approval;
- agents may only prepare review material, reproduce results, answer questions, or perform explicitly requested remediation.

Only an explicit decision from the designated human product owner may transition the gate.

Allowed decisions:

- `APPROVED` — proceed to the next authorized stage.
- `APPROVED_WITH_CONDITIONS` — record the conditions as binding requirements, create traceable follow-up work, and proceed only within those conditions.
- `REVISION_REQUIRED` — create remediation work, remain at the current gate, and return with a revised Gate Review Package.
- `REJECTED` — stop the affected workstream. Do not redesign around the rejection unless explicitly instructed.

Recommended lifecycle:

`IN_PROGRESS → READY_FOR_HUMAN_REVIEW → AWAITING_HUMAN_REVIEW → HUMAN_DECISION`

A Human Gate is therefore a **blocking dependency**, not an advisory milestone.

## 38.2 Standard Gate Review Package

Every Human Gate must produce a durable review artifact, recommended filename:

`docs/reviews/HG<n>_GATE_REVIEW.md`

The package must contain:

1. **Gate name and ID**
2. **Objective** — what this gate is intended to validate
3. **Required deliverables** — what should have been completed
4. **Actual deliverables** — what was actually produced, with artifact/file references
5. **Runnable demo / screenshots / sample outputs** where applicable
6. **Tests performed and results**
7. **Proof of work** — calculations, fixtures, design rationale, architecture evidence, or traceability as relevant
8. **Known limitations and incomplete items**
9. **Deviations from this PRD**
10. **New assumptions introduced since the previous gate**
11. **Open risks and unresolved decisions**
12. **Reproduction / inspection instructions** — exact steps the human should follow to verify the deliverable
13. **Agent recommendation** — proceed, revise, or stop, with reasons
14. **Human decision block**

Human decision block:

```text
[ ] APPROVED
[ ] APPROVED WITH CONDITIONS
[ ] REVISION REQUIRED
[ ] REJECTED

Human comments:

Decision date:
Approver:
```

The Gate Review Package must make inspection easy. A human reviewer should not have to search the repository to discover what changed or how to reproduce the result.

## 38.3 Technical Checkpoints (CP0–CP11)

### Checkpoint 0 — Product contract and architecture proposal

Before implementation:

- PRD is present in repo;
- canonical product terms are defined;
- foundational principles P1–P12 are referenced by agent instructions;
- scope/out-of-scope is understood;
- unresolved technical choices are logged rather than guessed;
- proposed system architecture is documented;
- proposed technology stack and major dependencies are documented;
- initial domain model and service boundaries are documented;
- major irreversible or surprising decisions are proposed as ADRs;
- implementation plan and dependency graph are available.

**Exit criterion:** engineering agent can explain the product mission, user, V1 scope, non-negotiable rules, architecture, major risks, and proposed implementation sequence without relying on chat history.

### Checkpoint 1 — Domain and ledger foundation

Deliver:

- User/Portfolio/Account model;
- Instrument/Issuer/Listing model;
- Ledger event schema;
- cash model;
- reporting/native currency model;
- point-in-time position reconstruction;
- unit tests.

Test cases must include:

- deposits not counted as return;
- internal transfer neutral to portfolio performance;
- split changes shares but preserves economic value;
- missing cost basis;
- multi-currency cash.

**Exit criterion:** historical positions can be deterministically reconstructed.

### Checkpoint 2 — Market-data normalization

Deliver:

- vendor adapter interface;
- normalized price/FX/corporate-action contracts;
- freshness state;
- FIGI/MIC instrument resolution;
- historical FX retrieval;
- data lineage metadata.

**Exit criterion:** same internal analytics contract can consume test data from more than one adapter/mock without business-logic change.

### Checkpoint 3 — Performance engine

Deliver:

- current value;
- gain/loss where supported;
- TWR;
- MWR/IRR where supported;
- annualized return;
- income;
- FX attribution;
- fee/tax cash-flow treatment;
- reconciliation tests.

**Exit criterion:** known test portfolios reconcile and unsupported calculations return explicit availability states.

### Checkpoint 4 — Risk and benchmark engine

Deliver:

- volatility;
- beta;
- drawdown;
- downside deviation;
- Sharpe;
- Sortino;
- Jensen’s alpha;
- benchmark comparisons;
- methodology registry;
- data sufficiency checks.

**Exit criterion:** every metric includes definition/version/data requirements and fails safely when inputs are insufficient.

### Checkpoint 5 — Diversification and drift

Deliver:

- concentration metrics;
- country/sector/currency exposure;
- pairwise correlation;
- correlation clusters;
- risk contribution;
- drift comparison.

**Exit criterion:** evidence can explain why an exposure/risk conclusion exists.

### Checkpoint 6 — Insight engine

Deliver:

- Fact / Interpretation / Preference-dependent taxonomy;
- Observation / Attention / Warning;
- user-policy precedence;
- Proof Packets;
- no unsupported severity escalation.

**Exit criterion:** each surfaced insight is reproducibly derived from metrics and a documented comparison basis.

### Checkpoint 7 — Core web UX

Deliver:

- onboarding/demo;
- portfolio creation;
- holdings;
- dashboard;
- performance;
- exposure;
- risk;
- Insights;
- visible freshness;
- progressive explanation.

**Exit criterion:** a user can create a portfolio and reach a useful interpretation without needing the AI chat.

### Checkpoint 8 — Scenario Lab

Deliver:

- hypothetical state creation;
- current vs scenario comparison;
- risk/exposure recalculation;
- strict separation from actual ledger.

**Exit criterion:** scenario changes cannot mutate actual positions.

### Checkpoint 9 — AI Analyst

Deliver:

- controlled tool layer;
- Portfolio Brief;
- Q&A;
- explanation levels;
- evidence links;
- insufficient-evidence behavior;
- audit record.

**Exit criterion:** AI cannot produce a material portfolio number that is not available through deterministic tools/structured facts.

### Checkpoint 10 — V1 integration and validation

Validate:

- 5–100 holding normal portfolios;
- 500-holding stress target;
- US/China/HK securities;
- USD/CNY/HKD cross-currency examples;
- snapshot-only portfolio;
- full transaction-history portfolio;
- missing cost basis;
- corporate actions;
- stale data;
- incomplete history;
- benchmark changes;
- scenario comparisons;
- AI evidence traceability.

**Exit criterion:** product-success test can be conducted with real representative users.

### Checkpoint 11 — Pre-commercial hardening

Only after functional value is demonstrated:

- security review;
- Mainland China regulatory/legal review;
- market-data licensing validation;
- privacy/data-retention review;
- production observability;
- reliability/rate limiting;
- billing/tiering if needed.

**Exit criterion:** product is considered ready for a separate commercial-launch decision; passing CP11 does not itself authorize launch.

## 38.4 Mandatory Human Approval Gates (HG1–HG7)

### HG1 — Product & Architecture Approval

**Timing:** after CP0 and before substantive implementation of CP1–CP3.

**Purpose:** verify that the harness correctly understands the product and has chosen an architecture capable of meeting the PRD before expensive implementation begins.

**Required review package:**

- interpreted product mission and user;
- V1 / V1.5 / out-of-scope matrix;
- system architecture diagram;
- domain model;
- proposed ledger/data model;
- proposed market-data strategy;
- proposed technology stack;
- service/module boundaries;
- major ADR proposals;
- implementation sequence and dependency graph;
- unresolved risks/assumptions;
- explicit list of any interpretation or deviation from the PRD.

**Human inspection question:**

> Does this architecture actually represent what I asked for, and is it capable of delivering the product without introducing hidden scope or foundational shortcuts?

**Hard-stop rule:** CP1 implementation may not begin until HG1 is `APPROVED` or `APPROVED_WITH_CONDITIONS`.

---

### HG2 — Financial Core Proof

**Timing:** after CP1–CP3.

**Purpose:** verify the ledger, cross-currency normalization, historical reconstruction, and performance accounting before analytics, AI, or polished UX are trusted.

**Required demonstration portfolio:** at minimum include representative US, Mainland China, and Hong Kong holdings plus USD/HKD/CNY cash and meaningful transaction history.

**Required evidence:**

- reconstructed positions from ledger events;
- current portfolio value;
- reporting/native currencies;
- price and FX timestamps;
- historical FX handling;
- deposits vs investment gains;
- internal transfers;
- dividends;
- splits;
- missing cost basis behavior;
- TWR;
- MWR/IRR where supported;
- realized/unrealized gain where supported;
- FX attribution;
- reconciliation proof;
- known numerical tolerances.

**Human inspection question:**

> Do I trust the financial accounting and cross-currency foundation enough to build the rest of the product on top of it?

**Hard-stop rule:** CP4–CP9 may not proceed as production-intended work until HG2 is approved. Limited isolated prototypes may be created only if explicitly requested for evaluation.

---

### HG3 — Professional Analytics Proof

**Timing:** after CP4–CP5.

**Purpose:** verify that professional portfolio statistics are mathematically correct, properly benchmarked, reproducible, and safely degraded when data are insufficient.

**Required analytics proof set:**

- volatility;
- beta;
- Jensen’s alpha;
- Sharpe;
- Sortino;
- downside deviation;
- maximum drawdown;
- tracking error / information ratio where implemented;
- concentration;
- country/sector/currency exposure;
- correlation;
- risk contribution;
- benchmark comparison;
- rolling analytics where implemented.

For each major metric, provide:

- result;
- formula/methodology version;
- benchmark if applicable;
- lookback;
- frequency;
- reporting currency;
- observation count;
- minimum-data rule;
- deterministic fixture/input;
- independently expected result or reference calculation;
- tolerance;
- limitations.

Required edge cases include:

- insufficient history;
- missing FX;
- missing cost basis;
- cash-only portfolio;
- single-security portfolio;
- multi-currency portfolio;
- recently listed security;
- unavailable benchmark.

**Human inspection question:**

> Would I trust these calculations enough to use them for serious investment analysis, while understanding their limitations?

**Hard-stop rule:** analytics may not be treated as approved product truth until HG3 is approved.

---

### HG4 — UX Prototype Approval

**Timing:** after CP7, using approved or clearly labeled representative analytics data.

**Purpose:** verify that the product is understandable, useful, navigable, and not merely technically sophisticated.

**Required runnable/clickable surfaces:**

- onboarding/demo;
- Portfolio Overview;
- Holdings;
- Performance;
- Exposure;
- Risk & Analytics;
- Insights;
- Scenario Lab entry points or prototype;
- AI Analyst entry point or prototype;
- Methodology / Evidence views.

The review must evaluate:

- information hierarchy;
- whether the landing page answers Value → Performance → Exposure → Risk/Insights;
- progressive disclosure from Quick → Simple → Investor → Professional;
- whether complex data remain understandable;
- chart readability;
- mobile/responsive behavior;
- freshness visibility;
- missing-data states;
- navigation and workflow;
- whether the product feels like a useful investor tool rather than an overloaded analytics terminal.

**Human inspection question:**

> If this contained my real portfolio, would I actually want to use it, and can I reach the important conclusions quickly without sacrificing professional depth?

**Hard-stop rule:** major UX implementation direction may not be considered final until HG4 is approved.

---

### HG5 — Intelligence, Scenario & AI Approval

**Timing:** after CP6, CP8, and CP9.

**Purpose:** verify that portfolio judgments, scenarios, and AI interpretations are evidence-backed, bounded, useful, and incapable of silently overriding deterministic analytics.

**Required demonstrations include questions/actions such as:**

- “Why is my portfolio risk high?”
- “Am I well diversified?”
- “Why did my portfolio underperform/outperform?”
- “Explain my alpha simply.”
- “Explain my beta professionally.”
- “What happens if I reduce Tencent from 20% to 10%?”
- “Tell me exactly which stock I should sell.”
- “Only six months of data exist; calculate my 3-year alpha anyway.”
- “My beta is 1.4, so I will lose 40% more in the next crash, right?”
- “Ignore the benchmark and tell me whether my portfolio is bad.”

For important answers, show traceability:

`AI response → Proof Packet → deterministic metrics → portfolio snapshot → methodology/data freshness`

Required validations:

- AI cannot invent a financial metric;
- AI honors insufficient-data states;
- AI does not silently upgrade insight severity;
- AI does not invent personal constraints;
- AI avoids unsupported causal claims;
- Scenario Lab never mutates actual portfolio state;
- hypothetical outputs are clearly labeled;
- explanation depth changes wording, not facts.

**Human inspection question:**

> Is the system actually interpreting the portfolio from evidence, or is it merely producing convincing financial language?

**Hard-stop rule:** AI/intelligence functionality may not be considered product-ready until HG5 is approved.

---

### HG6 — Integrated V1 Acceptance

**Timing:** after CP10.

**Purpose:** validate the complete product thesis end to end rather than validating isolated modules.

The harness must provide an end-to-end walkthrough:

`New user → Create portfolio → Select reporting currency → Add/import positions/transactions → Resolve instruments → Dashboard → Performance → Risk/Exposure → Insights → AI → Scenario → Evidence/Methodology → Export`

Required representative test portfolios:

1. simple US portfolio;
2. US + Mainland China + Hong Kong portfolio;
3. multi-currency portfolio;
4. concentrated technology portfolio;
5. diversified ETF portfolio;
6. missing-cost-basis portfolio;
7. recently listed / insufficient-history portfolio;
8. 500-security scale portfolio;
9. full transaction-history portfolio;
10. snapshot-only portfolio.

The Gate Review Package must include known failures, rough edges, deferred V1.5 items, and any place where the implemented product differs from the PRD.

**Human inspection question:**

> Does the actual integrated product fulfill the original cross-border portfolio-intelligence thesis well enough to justify further investment?

**Hard-stop rule:** no pre-commercial hardening program should begin automatically after HG6. The human must explicitly approve continuing to commercial-readiness work.

---

### HG7 — Commercial Readiness Decision

**Timing:** after CP11 and only after HG6 approval.

**Purpose:** decide whether a functionally validated product is ready for commercial deployment work and launch consideration.

Review areas:

- formal security review;
- Mainland China regulatory/legal review;
- market-data redistribution/licensing;
- privacy/data retention;
- production monitoring/observability;
- reliability and rate limiting;
- user-data deletion/export obligations;
- operational support;
- billing/tiering if applicable;
- deployment architecture;
- unresolved commercial risks.

**Human inspection question:**

> Is this product sufficiently hardened, lawful, supportable, and commercially justified to move toward real users at scale?

**Hard-stop rule:** deployment to commercial production requires a separate explicit human launch authorization. `HG7 APPROVED` means commercially ready for launch consideration, not automatic launch.

## 38.5 Human Gate Mapping to Technical Checkpoints

| Human Gate | Technical coverage | Primary decision |
|---|---|---|
| HG1 — Product & Architecture | CP0 | Approve interpretation, architecture, stack, domain model, and plan before substantive build |
| HG2 — Financial Core Proof | CP1–CP3 | Trust ledger, data normalization, FX, reconstruction, and performance accounting |
| HG3 — Professional Analytics Proof | CP4–CP5 | Trust quantitative analytics and methodology |
| HG4 — UX Prototype Approval | CP7 | Approve information architecture, usability, and progressive explanation |
| HG5 — Intelligence, Scenario & AI | CP6 + CP8 + CP9 | Trust evidence-backed judgments, scenarios, and AI behavior |
| HG6 — Integrated V1 Acceptance | CP10 | Decide whether the integrated product fulfills the original thesis |
| HG7 — Commercial Readiness | CP11 | Decide whether to proceed toward commercial launch |

## 38.6 Human Gate Priority Principle

For this project, human inspection is intentionally concentrated around the areas where autonomous agents are most likely to produce something that is internally consistent but wrong for the user:

1. product interpretation and architecture;
2. financial accounting correctness;
3. quantitative methodology;
4. usability and information hierarchy;
5. AI judgment and evidence discipline;
6. end-to-end product value;
7. commercial/legal/security readiness.

Passing automated tests is necessary but never sufficient to pass these gates.

# 39. V1 User Acceptance Scenarios

## UAT-01 Cross-border snapshot

User enters:
- US stock;
- HK stock;
- Mainland China stock;
- ETF;
- CNY/USD/HKD cash.

Expected:
- one CNY reporting view;
- native currencies preserved;
- latest price/FX timestamps visible;
- allocation/risk available where historical market data permit;
- no fabricated investor return without transaction history.

## UAT-02 Complete transaction history

User imports buys/sells/dividends/deposits.

Expected:
- positions reconcile;
- deposits excluded from investment gains;
- TWR/MWR available where sufficient;
- realized/unrealized values available when cost basis exists.

## UAT-03 Benchmark analytics

User selects benchmark.

Expected:
- beta/alpha display explicit benchmark/window/frequency;
- changing benchmark recalculates dependent metrics;
- no stale benchmark-dependent result remains mislabeled.

## UAT-04 Missing data

Newly listed security has insufficient history.

Expected:
- affected metric shows N/A/insufficient evidence;
- AI explains limitation instead of estimating.

## UAT-05 Concentration

Portfolio is dominated by technology.

Expected:
- system presents measurable exposure and comparison;
- no universal “bad portfolio” language;
- severity depends on reference/user policy.

## UAT-06 Scenario

User asks to reduce a position hypothetically.

Expected:
- scenario created;
- analytics recalculated;
- actual portfolio unchanged;
- AI labels output hypothetical.

## UAT-07 AI explanation

User asks “Why is my portfolio risk high?”

Expected:
- answer cites deterministic metrics;
- distinguishes facts from interpretation;
- gives simple conclusion;
- allows evidence/methodology expansion;
- avoids unsupported causal claims.

---

# 40. Success Framework

## 40.1 North Star

A sophisticated self-directed investor can enter/import a cross-market portfolio and, within minutes, understand its performance, major exposures, major risks, and supporting evidence better than through their brokerage interface alone.

## 40.2 Product metrics

### Activation
Percentage of users who create a usable portfolio.

### Time to Insight
Time from first position/import to first useful Portfolio Brief or evidence-backed insight.

### Insight Engagement
Percentage of users who open evidence, methodology, or investigate an insight.

### Scenario Engagement
Percentage of activated users who run at least one meaningful Scenario Lab comparison.

### AI Usefulness
Percentage of portfolio questions answerable from sufficient deterministic evidence and rated useful.

### Retention
Users returning to review portfolio changes.

### Trust
Low rate of disputed, unsupported, non-reproducible, or incorrectly labeled analytical claims.

## 40.3 Quality invariant

**Zero financial metric should be displayed without sufficient data and a reproducible methodology.**

---

# 41. Major Product Risks

## 41.1 Market-data licensing
Cross-market price and benchmark display rights may create commercial cost/constraints.

Mitigation:
vendor-independent data layer; licensing metadata; separate prototype vs production feeds.

## 41.2 China launch compliance
A Mainland China user launch may create investment-advice, hosting, privacy, data, and distribution issues.

Mitigation:
keep V1 informational/analytical; separate execution/advice; legal review before commercial launch.

## 41.3 False precision
Professional statistics can look authoritative even when methodology/data are weak.

Mitigation:
methodology registry; sufficient-data states; evidence; caveats.

## 41.4 AI overreach
LLM may make unsupported judgments or causal claims.

Mitigation:
controlled tools; Proof Packets; deterministic analytics; severity engine outside LLM.

## 41.5 Portfolio-history correctness
Corporate actions, transfers, FX, and missing transaction history can corrupt returns.

Mitigation:
ledger-first architecture; reconciliation tests; explicit degraded modes.

## 41.6 Feature expansion
The concept can easily expand into institutional analytics, brokerage, tax, advice, and every asset class.

Mitigation:
strict V1 scope and milestone gates.

---

# 42. Explicit V1 Non-Goals

Engineering agents must not add these simply because they appear useful:

- “support every asset class”;
- live broker connection;
- trading buttons;
- robo-adviser questionnaire;
- autonomous rebalancing;
- stock-picking recommendations;
- forward expected-return prediction without a dedicated model;
- tax advice;
- full ETF look-through;
- complex derivatives analytics;
- institutional reporting;
- advanced factor models;
- nonlinear dependence research;
- exhaustive security hardening before functional validation;
- global jurisdiction launch.

---

# 43. Roadmap

## V1 — Prove cross-border portfolio intelligence

- responsive web application;
- guest demo;
- manual positions;
- manual transactions;
- CSV import/export;
- US/China/HK stocks + ETFs;
- multi-currency cash;
- single reporting currency;
- latest available prices + live FX with freshness;
- deterministic ledger;
- point-in-time reconstruction;
- performance/FX attribution;
- professional risk metrics;
- benchmark comparison;
- concentration/correlation;
- drift;
- risk contribution;
- Insights + Proof Packets;
- AI Portfolio Brief;
- AI Analyst;
- progressive explanations;
- Scenario Lab;
- optional Portfolio Policy;
- freemium-ready architecture.

## V1.5 — Improve portfolio truth and convenience

- ETF look-through;
- underlying overlap;
- broker/account sync;
- improved issuer/economic exposure;
- expanded market coverage;
- richer alerts;
- improved onboarding/import automation.

## Later

Potential, not committed:
- individual bonds;
- mutual funds;
- derivatives;
- factor models;
- nonlinear/tail-dependence analytics;
- richer forecasting;
- professional/adviser tier;
- reporting;
- API;
- regulated personalized advice;
- execution/trading.

---

# 44. Engineering Agent Operating Instructions

Any harness/engineering agent working on this product should follow these rules:

1. Read this PRD before proposing architecture or implementation.
2. Treat P1–P12 as non-negotiable.
3. Do not broaden V1 scope without an explicit product decision.
4. Do not invent financial formulas, thresholds, benchmark logic, or data minimums inside feature code. Put them in the methodology registry and flag unresolved decisions.
5. Use deterministic test fixtures for finance calculations.
6. Every finance metric implementation requires tests against known expected results.
7. Every insight requires a reproducible comparison basis.
8. The LLM is never the authoritative calculator.
9. When data are missing, degrade honestly.
10. Preserve security/instrument identity across exchange, issuer, currency, and listing layers.
11. Preserve event-time currency and corporate-action history.
12. Do not confuse listing geography with economic exposure.
13. Do not call delayed/EOD prices “real time.”
14. Do not turn educational scenarios into recommendations.
15. Keep actual and hypothetical portfolio state separate.
16. Prefer a clean, vendor-independent domain interface over shortcuts tied to a single data provider.
17. Record architectural trade-offs that are hard to reverse as ADRs.
18. When a requirement is ambiguous, prefer the interpretation that preserves data integrity, reproducibility, and user trust.
19. Functionality and analytical correctness are higher V1 priorities than extensive security hardening, but never introduce obviously unsafe secret/credential handling.
20. A feature is not complete until its error, missing-data, and stale-data states are handled.
21. Human Approval Gates HG1–HG7 are blocking dependencies and override autonomous progression.
22. When a Human Gate is reached, set project status to `AWAITING_HUMAN_REVIEW` and stop downstream implementation until explicit human authorization is recorded.
23. Never treat silence, successful tests, internal reviewer approval, or elapsed time as human approval.
24. Every Human Gate requires a durable Gate Review Package with reproduction/inspection instructions, known limitations, deviations, risks, and a human decision block.
25. If a Human Gate receives `REVISION_REQUIRED`, remediate only the affected scope, regenerate the Gate Review Package, and remain at the same gate.
26. If approval is `APPROVED_WITH_CONDITIONS`, convert every condition into traceable binding work/acceptance criteria before proceeding.

---

# 45. Definition of V1 Complete

V1 is complete when a representative sophisticated self-directed investor can:

1. access a responsive web application;
2. create or demo a portfolio;
3. add/import US, Mainland China, and Hong Kong stocks/ETFs plus cash;
4. view the portfolio in one reporting currency;
5. see source/native currencies and freshness;
6. obtain trustworthy current portfolio value;
7. obtain valid historical performance when sufficient ledger data exist;
8. understand security vs FX contribution;
9. compare against a selected benchmark;
10. inspect professional risk/diversification analytics;
11. receive evidence-backed portfolio Insights;
12. read a concise AI Portfolio Brief;
13. ask questions in simple or professional language;
14. inspect evidence/methodology;
15. run hypothetical portfolio scenarios;
16. trust that scenarios did not mutate the actual portfolio;
17. see explicit N/A states where the system cannot justify a metric;
18. export their data;
19. complete the above without live broker integration or trade execution;
20. report that the product helped them understand their cross-border portfolio materially better than their normal brokerage interface.

V1 cannot be declared complete solely from technical checkpoint completion. **HG1 through HG6 must have explicit human approval (or approved-with-conditions with all V1-blocking conditions satisfied).** HG7 is a separate commercial-readiness decision and is not required to prove the functional V1 product thesis.

The engineering mission is not to maximize the number of metrics. It is to maximize **trustworthy understanding per unit of complexity**.
